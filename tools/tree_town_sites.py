#!/usr/bin/env python
"""Candidate sites for a town built in giant trees. Produces candidates; a human picks.

Every land cell on a 128-block grid is tested against the settlement rules in data/towns.json and scored:

  off_path       at least 250 blocks from every routed critical leg (major towns and outposts), and within
                 900 so a player can find it
  spacing        at least 600 blocks from any town or rest stop, 300 from any outpost
  peak_pond      at least 500 blocks outside Peak Pond Hollow, which already carries the old growth and gym 4
  forest         the sub-region's forest type (data/foliage.json) carries at least 30 stems per hectare, so the
                 giants read as the oldest trees of a real wood, not planted on open ground
  ground         a 192-block grove square: mean slope under 12 degrees, at most 35% open water and none within 24
                 blocks of its centre
  wet            share of the grove square within 5 blocks above the nearest standing or running water: ground
                 that floods is a reason to live off it
  seen           share of leg points within 900 blocks that can see a target 40 blocks above the grove centre
                 (terrain plus planned canopy)

  python tools/tree_town_sites.py --source-root <root> [--top 8]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import terrain as T
from sightlines import cast

ROOT = Path(__file__).resolve().parent.parent
GRID = 128
GROVE = 192


def seg_distance(px, pz, poly):
    p = np.asarray(poly, float)
    a, b = p[:-1], p[1:]
    ab = b - a
    t = np.clip(((px - a[:, 0]) * ab[:, 0] + (pz - a[:, 1]) * ab[:, 1]) / np.maximum((ab ** 2).sum(1), 1e-9), 0, 1)
    q = a + ab * t[:, None]
    return float(np.min(np.hypot(q[:, 0] - px, q[:, 1] - pz)))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--top", type=int, default=8)
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    sea = T.sea_level(world)
    n = heights.shape[0]
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    legs = json.loads((ROOT / "derived" / "routes" / "critical_legs.json").read_text(encoding="utf-8"))["legs"]
    regions = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    foliage = json.loads((ROOT / "data" / "foliage.json").read_text(encoding="utf-8"))
    landmarks = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))["landmarks"]
    manifest = json.loads((ROOT / "build" / "paint" / "manifest.json").read_text(encoding="utf-8"))

    # sub-region index and forest type per sub-region
    img = Image.new("I", (n // 8, n // 8), 0)
    d = ImageDraw.Draw(img)
    subs = regions["subregions"]
    for i, s in enumerate(subs, start=1):
        for ring in s["polygons"]:
            d.polygon([(x / 8, z / 8) for x, z in ring], fill=i)
    sub_idx = np.asarray(img)
    def forest_of(s):
        if s["id"] in foliage["assign"]:
            return foliage["assign"][s["id"]]["type"]
        return foliage["preset_defaults"].get((s.get("paint") or {}).get("preset"))
    pph = next(s for s in subs if s["id"] == "peak_pond_hollow")
    pmask = Image.new("L", (n // 8, n // 8), 0)
    ImageDraw.Draw(pmask).polygon([(x / 8, z / 8) for x, z in pph["polygons"][0]], fill=1)
    pph_cells = np.argwhere(np.asarray(pmask) > 0) * 8 + 4

    # water: lake basins and painted river water
    wet = Image.new("L", (n, n), 0)
    dw = ImageDraw.Draw(wet)
    levels = []
    for lm in landmarks:
        wb = lm.get("water_body")
        for ring in (wb or {}).get("basin_polygons") or []:
            dw.polygon([tuple(q) for q in ring], fill=1)
    water = np.asarray(wet).astype(bool)
    for w in manifest["water"]:
        if "levels" in w:
            lv = np.asarray(Image.open(ROOT / "build" / "paint" / w["levels"])) > 0
            water[w["z"]:w["z"] + lv.shape[0], w["x"]:w["x"] + lv.shape[1]] |= lv
    canopy = None
    cp = ROOT / "build" / "paint" / "canopy.npz"
    if cp.exists():
        canopy = np.load(cp)["canopy"]
    surface = np.maximum(heights, canopy) if canopy is not None and canopy.shape == heights.shape else heights
    slope = T.slope_degrees(heights[::4, ::4])          # 4-block cells

    critical = [t for t in towns if t.get("critical_path")]
    rows = []
    half = GROVE // 2
    for cz in range(half, n - half, GRID):
        for cx in range(half, n - half, GRID):
            if heights[cz, cx] <= sea + 2:
                continue
            dleg = min(seg_distance(cx, cz, l["polyline"]) for l in legs)
            if not (250 <= dleg <= 900):
                continue
            ok = True
            for t in towns:
                c = t.get("centre") or {}
                if c.get("x") is None:
                    continue
                dist = math.hypot(c["x"] - cx, c["z"] - cz)
                need = 300 if t.get("tier") == "outpost" else 600
                if dist < need:
                    ok = False
                    break
            if not ok:
                continue
            dpph = float(np.min(np.hypot(pph_cells[:, 1] - cx, pph_cells[:, 0] - cz)))
            if dpph < 500:
                continue
            si = int(sub_idx[cz // 8, cx // 8])
            if not si:
                continue
            sub = subs[si - 1]
            ftype = forest_of(sub)
            stems = (foliage["types"].get(ftype) or {}).get("stems_per_ha", 0) if ftype else 0
            if stems < 30:
                continue
            box = heights[cz - half:cz + half, cx - half:cx + half]
            wbox = water[cz - half:cz + half, cx - half:cx + half] | (box <= sea)
            if wbox.mean() > 0.35 or wbox[half - 24:half + 24, half - 24:half + 24].any():
                continue                                    # open water may run through the grove, not its centre
            sl = slope[(cz - half) // 4:(cz + half) // 4, (cx - half) // 4:(cx + half) // 4]
            if sl.mean() >= 12:
                continue
            # height above the nearest water within 300 blocks
            wz, wx = np.nonzero(water[max(0, cz - 300):cz + 300, max(0, cx - 300):cx + 300])
            if len(wz):
                wz, wx = wz + max(0, cz - 300), wx + max(0, cx - 300)
                sample = np.argwhere(np.ones((GROVE // 16, GROVE // 16))) * 16 + [cz - half + 8, cx - half + 8]
                wet_n = 0
                for sz, sx in sample:
                    k = int(np.argmin(np.hypot(wx - sx, wz - sz)))
                    if heights[sz, sx] - heights[wz[k], wx[k]] <= 5 and math.hypot(wx[k] - sx, wz[k] - sz) <= 300:
                        wet_n += 1
                wet_share = wet_n / len(sample)
                d_water = float(np.min(np.hypot(wx - cx, wz - cz)))
            else:
                wet_share, d_water = 0.0, None
            # seen from the legs
            pts = []
            for l in legs:
                pl = np.asarray(l["polyline"], float)
                for (ax, az), (bx, bz) in zip(pl[:-1], pl[1:]):
                    L = math.hypot(bx - ax, bz - az)
                    for t_ in np.arange(0, L, 48):
                        x, z = ax + (bx - ax) * t_ / L, az + (bz - az) * t_ / L
                        if math.hypot(x - cx, z - cz) <= 900:
                            pts.append((x, z))
            seen = sum(1 for o in pts if cast(heights, o, 2.0, {"x": cx, "z": cz}, 40.0, step=2.0, surface=surface)["visible"])
            rows.append({"x": cx, "z": cz, "ground_y": round(float(heights[cz, cx]), 1), "subregion": sub["id"],
                         "region": sub["parent"], "forest": ftype, "stems_per_ha": stems,
                         "off_path_blocks": round(dleg), "from_peak_pond_hollow": round(dpph),
                         "grove_slope_mean_deg": round(float(sl.mean()), 1), "grove_water_share": round(float(wbox.mean()), 2), "grove_relief": round(float(box.max() - box.min()), 1),
                         "wet_share": round(wet_share, 2), "nearest_water_blocks": round(d_water) if d_water is not None else None,
                         "leg_points_within_900": len(pts), "seen_share": round(seen / len(pts), 2) if pts else 0.0})
    for r in rows:
        r["score"] = round(r["seen_share"] * 2 + r["wet_share"] * 1.5 + min(r["stems_per_ha"], 110) / 110 - r["grove_slope_mean_deg"] / 20
                           - abs(r["off_path_blocks"] - 450) / 900, 3)
    rows.sort(key=lambda r: -r["score"])
    # one per sub-region in the shortlist
    short, seen_sub = [], set()
    for r in rows:
        if r["subregion"] in seen_sub:
            continue
        seen_sub.add(r["subregion"])
        short.append(r)
    out = {"generator": "tools/tree_town_sites.py", "provenance": T.provenance(world, Path(a.world)), "grid_blocks": GRID,
           "grove_blocks": GROVE, "passing_cells": len(rows), "shortlist": short[:a.top], "all": rows}
    T.write_json(a.out or str(ROOT / "derived" / "sites" / "tree_town.json"), out)
    print(json.dumps({k: v for k, v in out.items() if k != "all"}, indent=1))


if __name__ == "__main__":
    main()
