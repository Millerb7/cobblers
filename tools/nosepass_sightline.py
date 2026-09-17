#!/usr/bin/env python
"""Can the Route 3 Nosepass signs see the mast of Surge's signal array? Margins along leg 3.

For every dense leg-3 point in a range, casts the line from eye height (1.62) to the top of the array mast
(data/landmarks.json surge_signal_array: anchor ground + site.mast_blocks) and reports, beyond a clearing radius
around the observer:

  terrain_margin   the least clearance over the heightmap along the whole line, observer's end included (so it can be
                   just the eye height over rising ground at the observer's feet: see terrain_tightest_from_observer)
  model_margin     the recorded canopy_clear model: over forested ground the line must clear the p90 object height of
                   the forest type data/foliage.json assigns the sub-region (below that preset's treeline)
  paint_margin     the same line over build/paint/canopy.npz (tools/paint_maps.py), the planned canopy top
  near_m           distance to --near points (e.g. a built tree trunk), to keep it outside the clearing

Reads build/routes/paths.json (tools/build_routes.py, the dense paths data/routes.json is simplified from).

  python tools/nosepass_sightline.py --source-root <root> [--from 1440 --to 1530] [--near 2236,1622] [--mast 20]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import build_routes as B
import terrain as T

ROOT = Path(__file__).resolve().parent.parent
EYE = 1.62
LEG = "route_03_misty_to_surge"
BOX = (1400, 1100, 2500, 3000)   # x0, z0, x1, z1 of the model canopy raster; covers every leg-3 line to the array


def model_canopy(heights, regions, foliage, library):
    """The canopy_clear model as a 4-block raster over BOX: p90 object height of each forested sub-region's type."""
    heights_by_group = {}
    objs = library.get("objects") or library
    for o in (objs.values() if isinstance(objs, dict) else objs):
        if o.get("group"):
            heights_by_group.setdefault(o["group"], []).append(o.get("height") or 0)
    p90 = {g: float(np.percentile(v, 90)) for g, v in heights_by_group.items()}

    def type_canopy(name):
        t = (foliage.get("types") or {}).get(name) or {}
        groups = {c["group"] for c in t.get("classes") or []
                  if any(isinstance(v, (int, float)) and v > 0 for k, v in c.items() if k not in ("group", "spacing"))}
        return max((p90[g] for g in groups if g in p90), default=0.0)

    x0, z0, x1, z1 = BOX
    w, h = (x1 - x0) // 4, (z1 - z0) // 4
    canopy = np.zeros((h, w), np.float32)
    for s in regions["subregions"]:
        preset = s["paint"]["preset"]
        treeline = regions["paint_presets"].get(preset, {}).get("treeline_y")
        ftype = (foliage["assign"].get(s["id"]) or {}).get("type") or foliage["preset_defaults"].get(preset)
        top = type_canopy(ftype) if ftype else 0.0
        if top <= 0:
            continue
        im = Image.new("1", (w, h), 0)
        d = ImageDraw.Draw(im)
        for poly in s["polygons"]:
            d.polygon([((q[0] - x0) / 4, (q[1] - z0) / 4) for q in poly], fill=1)
        zz, xx = np.nonzero(np.array(im, dtype=bool))
        forested = np.ones(len(zz), bool) if treeline is None else heights[z0 + zz * 4, x0 + xx * 4] < treeline
        canopy[zz[forested], xx[forested]] = np.maximum(canopy[zz[forested], xx[forested]], top)
    return canopy


def margins(heights, model, paint, grid, x, z, ax, az, top_y, clearing):
    oy = float(heights[z, x]) + EYE
    dist = math.hypot(ax - x, az - z)
    n = int(dist)
    f = np.arange(1, n) / n
    xs = np.rint(x + (ax - x) * f).astype(int)
    zs = np.rint(z + (az - z) * f).astype(int)
    line = oy + (top_y - oy) * f
    ground = line - heights[zs, xs]
    beyond = dist * f > clearing
    x0, z0, x1, z1 = BOX
    inside = (xs >= x0) & (xs < x1) & (zs >= z0) & (zs < z1)
    cap = np.zeros(len(xs), np.float32)
    cap[inside] = model[(zs[inside] - z0) // 4, (xs[inside] - x0) // 4]
    k = int(ground.argmin())
    out = {"terrain_margin": float(ground.min()), "terrain_tightest_from_observer": float(dist * f[k]),
           "model_margin": float((ground[beyond] - cap[beyond]).min())}
    if paint is not None:
        out["paint_margin"] = float((line[beyond] - np.maximum(heights[zs, xs], paint[zs // grid, xs // grid])[beyond]).min())
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--paths", default=str(ROOT / "build" / "routes" / "paths.json"))
    p.add_argument("--canopy", default=str(ROOT / "build" / "paint" / "canopy.npz"))
    p.add_argument("--from", dest="lo", type=float, default=1440)
    p.add_argument("--to", dest="hi", type=float, default=1530)
    p.add_argument("--clearing", type=float, default=None,
                   help="blocks along the line kept free of canopy; default: the sign site's clearing along_sightline_blocks")
    p.add_argument("--mast", type=float, default=None, help="mast height to test instead of site.mast_blocks")
    p.add_argument("--near", action="append", default=[], help="x,z of a point to report distance to (repeatable)")
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    D = ROOT / "data"
    leg = [tuple(q) for q in json.loads(Path(a.paths).read_text(encoding="utf-8"))["paths"][LEG]]
    cums = B.cumulative(leg)
    arr = next(l for l in json.loads((D / "landmarks.json").read_text(encoding="utf-8"))["landmarks"] if l["id"] == "surge_signal_array")
    ax, az = arr["anchor"]["x"], arr["anchor"]["z"]
    mast = a.mast if a.mast is not None else arr["site"]["mast_blocks"]
    if a.clearing is None:
        clearing = (arr["site"]["nosepass_view"]["canopy_clear"]["sign_site"].get("clearing") or {})
        a.clearing = float(clearing.get("along_sightline_blocks", 40))
    print("clearing %g blocks along the line" % a.clearing)
    top_y = float(heights[az, ax]) + mast
    print("mast %g blocks, top y%.1f" % (mast, top_y))
    model = model_canopy(heights, json.loads((D / "regions.json").read_text(encoding="utf-8")),
                         json.loads((D / "foliage.json").read_text(encoding="utf-8")),
                         json.loads((ROOT / "kits" / "structures" / "foliage" / "library.json").read_text(encoding="utf-8")))
    paint = grid = None
    if Path(a.canopy).exists():
        c = np.load(a.canopy)
        paint, grid = c["canopy"], int(c["grid_blocks"])
        print("paint canopy %s sha256 %s" % (a.canopy, hashlib.sha256(Path(a.canopy).read_bytes()).hexdigest()))
    near = [tuple(int(v) for v in s.split(",")) for s in a.near]
    for i, (x, z) in enumerate(leg):
        if not a.lo <= cums[i] <= a.hi:
            continue
        m = margins(heights, model, paint, grid, x, z, ax, az, top_y, a.clearing)
        row = {"along": round(cums[i], 1), "fraction": round(cums[i] / cums[-1], 3), "remaining": round(cums[-1] - cums[i]),
               "at": [x, z], "y": round(float(heights[z, x]), 1), **{k: round(v, 1) for k, v in m.items()}}
        for k, (nx, nz) in enumerate(near):
            row["near_%d" % k] = round(math.hypot(x - nx, z - nz), 1)
        print(json.dumps(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
