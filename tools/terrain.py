#!/usr/bin/env python
"""Shared heightmap loading for the analysis tools.

Not a framework: a loader, the import mapping, and slope/aspect. Every tool
that touches terrain goes through here so the import parameters live in exactly
one place, data/world.json.

Refuses to load terrain whose world config says the heightmap is unusable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORLD = ROOT / "data" / "world.json"


class TerrainUnavailable(RuntimeError):
    """The world config forbids using the heightmap, or it cannot be verified."""


def load_world(path):
    path = Path(path)
    if not path.is_file():
        raise TerrainUnavailable("world config not found: %s" % path)
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_heightmap(world, world_path, source_root=None):
    """Locate the heightmap and refuse if the config says it is not usable."""
    hm = world.get("heightmap") or {}
    status = hm.get("status")
    if status and status != "ok":
        raise TerrainUnavailable(
            'heightmap.status is "%s"; terrain tools will not run against an '
            "unusable heightmap. Re-export it, set the sha256, and set status "
            'to "ok".' % status
        )
    rel = hm.get("path")
    if not rel:
        raise TerrainUnavailable("heightmap.path is null in %s" % world_path)
    sha = hm.get("sha256")
    if not sha:
        raise TerrainUnavailable(
            "heightmap.sha256 is null in %s; refusing to run against an "
            "unverified heightmap" % world_path
        )

    root = source_root or world.get("source_root") or os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        raise TerrainUnavailable(
            "source_root is unset; set COBBLERS_SOURCE_ROOT or pass --source-root"
        )
    root = Path(root)
    if not root.is_absolute():
        # relative roots resolve against the world config, so a committed
        # config stays portable between machines
        root = Path(world_path).resolve().parent / root
    full = root / rel
    if not full.is_file():
        raise TerrainUnavailable("heightmap not found: %s" % full)

    h = hashlib.sha256()
    with open(full, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual != sha:
        raise TerrainUnavailable(
            "heightmap sha256 mismatch: recorded %s, actual %s" % (sha, actual)
        )
    return full


def sample_to_height(samples, world):
    """Map raw samples to Minecraft Y using the world import block.

    low_in/high_in are fractions of full scale, so the mapping is independent
    of bit depth. low_out/high_out are absolute Y and never scale.
    """
    imp = world.get("import") or {}
    if imp.get("input_units") != "fraction_of_full_scale":
        raise TerrainUnavailable(
            'import.input_units must be "fraction_of_full_scale"'
        )
    depth = (world.get("heightmap") or {}).get("bit_depth") or 16
    full = float((1 << depth) - 1)
    frac = samples.astype(np.float64) / full

    lo_in, hi_in = float(imp["low_in"]), float(imp["high_in"])
    lo_out, hi_out = float(imp["low_out"]), float(imp["high_out"])
    if hi_in <= lo_in:
        raise TerrainUnavailable("import.low_in must be below high_in")

    t = (frac - lo_in) / (hi_in - lo_in)
    y = lo_out + t * (hi_out - lo_out)
    if imp.get("clamp_low", True):
        y = np.maximum(y, lo_out)
    if imp.get("clamp_high", True):
        y = np.minimum(y, hi_out)
    return y


def read_heights(png_path, world):
    img = Image.open(png_path)
    arr = np.array(img)
    if arr.ndim == 3:
        channel = (world.get("heightmap") or {}).get("channel", "gray")
        idx = {"R": 0, "G": 1, "B": 2}.get(channel)
        if idx is None:
            raise TerrainUnavailable(
                "heightmap is multi-channel but heightmap.channel is %r; a "
                "luminance read would corrupt the surface" % channel
            )
        arr = arr[:, :, idx]
    return sample_to_height(arr, world)


def load(world_path=None, source_root=None, heightmap=None):
    """Return (heights, world). heights[z, x] is Minecraft Y as float."""
    world_path = Path(world_path or DEFAULT_WORLD)
    world = load_world(world_path)
    path = Path(heightmap) if heightmap else resolve_heightmap(world, world_path, source_root)
    return read_heights(path, world), world


# ------------------------------------------------------------------ analysis


def gradients(heights):
    """Central-difference gradients in blocks per block. Returns (gx, gz)."""
    gz, gx = np.gradient(heights.astype(np.float64))
    return gx, gz


def slope(heights):
    """Gradient magnitude: rise over run. 1.0 is a 45 degree face."""
    gx, gz = gradients(heights)
    return np.hypot(gx, gz)


def slope_degrees(heights):
    return np.degrees(np.arctan(slope(heights)))


def aspect_degrees(heights):
    """Compass bearing of the downhill direction. 0 N, 90 E, 180 S, 270 W.

    Flat ground has no aspect and is returned as NaN.
    """
    gx, gz = gradients(heights)
    east = -gx
    north = gz
    asp = np.degrees(np.arctan2(east, north)) % 360.0
    asp[np.hypot(gx, gz) == 0] = np.nan
    return asp


def sea_level(world):
    return float((world.get("vertical") or {}).get("sea_level", 62))


def add_common_args(p):
    p.add_argument("--world", default=str(DEFAULT_WORLD),
                   help="world config (default data/world.json)")
    p.add_argument("--source-root", default=None,
                   help="override source root for the heightmap")
    p.add_argument("--heightmap", default=None,
                   help="use this heightmap directly instead of resolving it")
    p.add_argument("--out", default=None, help="output path")
    return p


def load_from_args(args):
    return load(args.world, args.source_root, args.heightmap)


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def provenance(world, world_path):
    hm = world.get("heightmap") or {}
    return {
        "heightmap_path": hm.get("path"),
        "heightmap_sha256": hm.get("sha256"),
        "world_config": str(world_path),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Report the loaded terrain.")
    add_common_args(p)
    a = p.parse_args()
    try:
        h, w = load_from_args(a)
    except TerrainUnavailable as exc:
        raise SystemExit("terrain unavailable: %s" % exc)
    s = slope_degrees(h)
    print("shape        %s" % (h.shape,))
    print("height       min %.1f  max %.1f  mean %.1f" % (h.min(), h.max(), h.mean()))
    print("sea level    %.0f" % sea_level(w))
    print("land         %.1f%%" % (100.0 * (h > sea_level(w)).mean()))
    print("slope (deg)  mean %.2f  p99 %.2f  max %.2f"
          % (s.mean(), np.percentile(s, 99), s.max()))
