#!/usr/bin/env python
"""Generate the deterministic synthetic heightmap the analysis tools are tested on.

The surface is built from features with hand-computable properties, so a test
can assert an exact expected value rather than a golden file.

  base      flat ground at y=100 everywhere
  plateau   x 16..47, z 16..47 raised to y=120 with a step edge
  cone      centre (192, 64), apex y=140, flanks at exactly 1.0 rise/run
  ridge     crest x=112 over z 90..170, apex y=140, flanks at exactly 1.0
  trench    centred z=200, floor y=85, walls at exactly 1.0
  sea       z 235..255 dropped to y=40, below sea level 62

The import mapping is chosen so samples are exactly invertible: full-scale
fractions map 0..1 onto y 0..255, and 65535 = 255 * 257, so sample = y * 257.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

SIZE = 256
BASE = 100.0
SEA_LEVEL = 62
PLATEAU = dict(x0=16, x1=47, z0=16, z1=47, height=120.0)
CONE = dict(cx=192, cz=64, radius=40, apex=140.0)
RIDGE = dict(cx=112, z0=90, z1=170, halfwidth=40, apex=140.0)
TRENCH = dict(cz=200, halfwidth=15, floor=85.0)
SEA = dict(z0=235, z1=255, height=40.0)

SCALE = 257  # 65535 // 255


def build_heights():
    z, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    h = np.full((SIZE, SIZE), BASE)

    # plateau: a flat step, interior slope exactly 0
    p = PLATEAU
    h[p["z0"]:p["z1"] + 1, p["x0"]:p["x1"] + 1] = p["height"]

    # cone: h = apex - r, so the flank gradient magnitude is exactly 1
    c = CONE
    r = np.hypot(x - c["cx"], z - c["cz"])
    cone = c["apex"] - r
    h = np.maximum(h, np.where(r <= c["radius"], cone, -np.inf))

    # ridge: constant along z inside its band, triangular in x, flanks exactly 1
    g = RIDGE
    dx = np.abs(x - g["cx"])
    band = (z >= g["z0"]) & (z <= g["z1"]) & (dx <= g["halfwidth"])
    h = np.maximum(h, np.where(band, g["apex"] - dx, -np.inf))

    # trench: constant along x, V cross-section, walls exactly 1
    t = TRENCH
    dz = np.abs(z - t["cz"])
    cut = dz <= t["halfwidth"]
    h = np.where(cut, np.minimum(h, t["floor"] + dz), h)

    # sea: flat floor well below sea level
    s = SEA
    h[s["z0"]:s["z1"] + 1, :] = s["height"]
    return h


def to_samples(h):
    s = np.rint(h * SCALE)
    if s.min() < 0 or s.max() > 65535:
        raise ValueError("fixture heights do not fit 16-bit at this scale")
    return s.astype(np.uint16)


def write_png(path, samples):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.frombytes("I;16", (samples.shape[1], samples.shape[0]),
                          samples.astype("<u2").tobytes())
    img.save(path)
    back = np.array(Image.open(path))
    if back.dtype != np.uint16 or not np.array_equal(back, samples):
        raise RuntimeError("16-bit PNG did not round-trip; refusing to ship a lossy fixture")
    return path


def world_config(png_path, samples):
    sha = hashlib.sha256(png_path.read_bytes()).hexdigest()
    return {
        "schema": "cobblers.world/1",
        "name": "fixture",
        "seed": 0,
        "source_root": ".",
        "heightmap": {
            "path": png_path.name,
            "width": int(samples.shape[1]),
            "height": int(samples.shape[0]),
            "channel": "gray",
            "bit_depth": 16,
            "sha256": sha,
            "status": "ok",
        },
        "import": {
            "input_units": "fraction_of_full_scale",
            "low_in": 0.0,
            "high_in": 1.0,
            "low_out": 0,
            "high_out": 255,
            "water_level": SEA_LEVEL,
            "clamp_low": True,
            "clamp_high": True,
        },
        "bounds": {"min_x": 0, "min_z": 0, "max_x": SIZE - 1, "max_z": SIZE - 1},
        "vertical": {"min_y": 0, "max_y": 255, "sea_level": SEA_LEVEL},
        "grid": {
            "kind": "square", "cell_size": 64, "columns": 4, "rows": 4,
            "origin_x": 0, "origin_z": 0,
            "row_labels": ["A", "B", "C", "D"],
            "column_labels": ["1", "2", "3", "4"],
        },
        "features": {
            "base": BASE, "plateau": PLATEAU, "cone": CONE,
            "ridge": RIDGE, "trench": TRENCH, "sea": SEA,
        },
        "notes": ["Synthetic test surface. Not terrain. See tools/make_fixture.py."],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(Path(__file__).resolve().parent.parent
                                        / "tests" / "fixtures" / "terrain"))
    a = p.parse_args(argv)
    out = Path(a.out)

    h = build_heights()
    samples = to_samples(h)
    png = write_png(out / "land_fixture.png", samples)
    cfg = world_config(png, samples)
    (out / "world.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    print("wrote %s  (%dx%d, 16-bit)" % (png, samples.shape[1], samples.shape[0]))
    print("wrote %s" % (out / "world.json"))
    print("height min %.0f max %.0f" % (h.min(), h.max()))
    print("sha256 %s" % cfg["heightmap"]["sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
