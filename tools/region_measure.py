#!/usr/bin/env python
"""Re-measure regions and sub-regions of data/regions.json on the current heightmap.

The measured block of each region and sub-region (area, bounds, elevation percentiles, slope) is
recomputed from its polygons on 8-block cells: mean height per cell, slope from that surface. This is
the method the region plan used, with the polygons (rather than the plan's label rasters) as the
masks, so a re-measure on unchanged terrain reproduces the recorded numbers to within the polygon
simplification. Polygons, boundaries, paint and encounter slots are not touched.

  python tools/region_measure.py --source-root <root>            # report differences
  python tools/region_measure.py --source-root <root> --write    # also rewrite measured and the sha
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import terrain as T

F = 8


def grids(heights):
    n = heights.shape[0] // F
    y = heights[:n * F, :n * F].reshape(n, F, n, F).mean(axis=(1, 3)).astype(np.float64)
    gz, gx = np.gradient(y, float(F))
    return y, np.degrees(np.arctan(np.hypot(gx, gz)))


def mask_of(polygons, n):
    im = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(im)
    for ring in polygons:
        if len(ring) >= 3:
            d.polygon([(x / F, z / F) for x, z in ring], fill=1)
    return np.array(im) > 0


def measure(mask, y, slope):
    h, s = y[mask], slope[mask]
    zz, xx = np.nonzero(mask)
    return {"area_km2": round(len(h) * F * F / 1e6, 3),
            "bounds": {"min_x": int(xx.min() * F), "min_z": int(zz.min() * F),
                       "max_x": int((xx.max() + 1) * F) - 1, "max_z": int((zz.max() + 1) * F) - 1},
            "elevation": {"p10": round(float(np.percentile(h, 10)), 1), "median": round(float(np.median(h)), 1),
                          "p90": round(float(np.percentile(h, 90)), 1), "max": round(float(h.max()), 1)},
            "slope_degrees": {"mean": round(float(s.mean()), 1), "p90": round(float(np.percentile(s, 90)), 1),
                              "flat_under_5_pct": round(float((s < 5).mean() * 100), 1)}}


def diff(old, new):
    out = {}
    for group in ("elevation", "slope_degrees"):
        for k, v in new[group].items():
            o = (old.get(group) or {}).get(k)
            if o is not None and abs(o - v) >= 0.05:
                out["%s.%s" % (group, k)] = [o, v]
    if abs((old.get("area_km2") or 0) - new["area_km2"]) >= 0.001:
        out["area_km2"] = [old.get("area_km2"), new["area_km2"]]
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--regions", default=str(T.ROOT / "data" / "regions.json"))
    p.add_argument("--write", action="store_true")
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    y, slope = grids(heights)
    path = Path(a.regions)
    doc = json.loads(path.read_text(encoding="utf-8"))
    report = {}
    for coll in ("regions", "subregions"):
        for rec in doc[coll]:
            m = mask_of(rec["polygons"], y.shape[0])
            if not m.any():
                continue
            new = measure(m, y, slope)
            dd = diff(rec.get("measured") or {}, new)
            if dd:
                report[rec["id"]] = dd
            if a.write:
                keep = {k: v for k, v in (rec.get("measured") or {}).items() if k not in new}
                rec["measured"] = dict(new, **keep)
    print(json.dumps({"heightmap_sha256": world["heightmap"]["sha256"], "changed": report}, indent=1))
    if a.write:
        doc["computed_from_sha256"] = world["heightmap"]["sha256"]
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
