#!/usr/bin/env python
"""Export slope and aspect masks as PNGs for WorldPainter.

  slope.png   8-bit, 0 = flat, 255 = --max-degrees or steeper
  aspect.png  8-bit, compass bearing of the downhill direction scaled 0..255
              (0 = north, 64 = east, 128 = south, 192 = west); flat ground is 0
  land.png    8-bit mask, 255 where terrain is above sea level

  python tools/slope_masks.py --world tests/fixtures/terrain/world.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

import terrain as T


def to_png(arr8, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr8, mode="L").save(path)
    return path


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--max-degrees", type=float, default=60.0,
                   help="slope mapped to 255 (default 60)")
    p.add_argument("--no-aspect", action="store_true")
    p.add_argument("--no-land", action="store_true")
    a = p.parse_args(argv)

    try:
        heights, world = T.load_from_args(a)
    except T.TerrainUnavailable as exc:
        raise SystemExit("terrain unavailable: %s" % exc)

    outdir = Path(a.out) if a.out else T.ROOT / "derived" / "slope"
    outdir.mkdir(parents=True, exist_ok=True)
    written = {}

    deg = T.slope_degrees(heights)
    scaled = np.clip(deg / a.max_degrees, 0.0, 1.0) * 255.0
    written["slope"] = str(to_png(np.rint(scaled).astype(np.uint8), outdir / "slope.png"))

    if not a.no_aspect:
        asp = T.aspect_degrees(heights)
        flat = np.isnan(asp)
        asp = np.nan_to_num(asp, nan=0.0)
        vals = np.rint(asp / 360.0 * 256.0) % 256
        vals[flat] = 0
        written["aspect"] = str(to_png(vals.astype(np.uint8), outdir / "aspect.png"))

    if not a.no_land:
        land = (heights > T.sea_level(world)).astype(np.uint8) * 255
        written["land"] = str(to_png(land, outdir / "land.png"))

    payload = {
        "schema": "cobblers.derived.masks/1",
        "parameters": {"max_degrees": a.max_degrees},
        "source": T.provenance(world, a.world),
        "shape": {"width": int(heights.shape[1]), "height": int(heights.shape[0])},
        "slope_degrees": {
            "mean": round(float(deg.mean()), 3),
            "max": round(float(deg.max()), 3),
            "p99": round(float(np.percentile(deg, 99)), 3),
        },
        "land_fraction": round(float((heights > T.sea_level(world)).mean()), 4),
        "written": written,
    }
    T.write_json(outdir / "masks.json", payload)
    for k, v in written.items():
        print("  %-7s %s" % (k, v))
    print("slope mean %.2f deg, max %.2f deg, land %.1f%%"
          % (payload["slope_degrees"]["mean"], payload["slope_degrees"]["max"],
             100 * payload["land_fraction"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
