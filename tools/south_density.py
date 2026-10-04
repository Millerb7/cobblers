#!/usr/bin/env python
"""How thin is the south? What a player meets, counted per 1024-block cell (data/world.json grid: rows A-H north to
south, columns 1-8 west to east), and the emptiest walkable ground in the southern rows.

The owner, 2026-10-04: "the southern map, still the thinnest." This measures it, so the claim and the places built
against it rest on a number (docs/world-building/SOUTH_DENSITY.md).

WHAT IS COUNTED: every x/z point a record carries in the files below (the extraction of tools/poi_heatmap.py: an
object's own x/z, or its centre/center/position/anchor/site/seat/at/placement), snapped to a 32-block bucket per file so
that one place's twenty sign positions count once, plus one point per place record with a `bbox.writes` (the wayside
places, the Khan, the Orchard...). Each category is a kind of thing a player meets:

  places      data/placements.json, data/structures.json, data/ruins.json, data/mines.json, data/markets.json,
              data/far_south.json and every place record with bbox.writes
  residents   data/resident_encounters.json, data/southern_residents.json, data/northern_residents.json
  trainers    data/trainers.json, route_trainers.json, vr_trainers.json, late_route_trainers.json, arena_trainers.json,
              gym_trainers.json
  shrines     data/shrines.json
  encounters  data/habitat_blocks.json (the hearts a Habitat Block holds), data/mega_dens.json, data/gulch_mine.json
  caches      data/rewards.json
  legendary   data/legendaries.json, data/adopted_legendary_sites.json
  npcs        data/npc_seats.json, data/traders.json
  landmarks   data/landmarks.json, data/signposts.json, data/elder_trees.json, data/themed_saplings.json
  towns       data/towns.json

The three residents-format files (southern, northern, far south) count one thing per site, at its centre: as a
resident where the site has a named Pokemon or an NPC, else as a place. Their pieces' relative offsets are not points.
Any other point with both x and z under 64 is taken for a relative offset and dropped.

NOT counted, said here so the count is not read as the world (CLAUDE.md "Our list is not the world"): what a donor
template or a mod placed (gym templates' healers, Repurposed Structures), wild spawns (an abstract table, no point),
and route geometry (routes.json, rivers.json, route_paths.json: lines, not things).

THE GAPS: every 32 blocks over the southern rows, land only (ground above the sea), outside the Rift polygon and its rim
sculpt's reach, outside every town footprint and every place's bbox.writes, within 250 blocks of a walked path
(data/route_paths.json) so a player passes it (and, as candidates, up to four per cell walked or not): the distance to the nearest counted point. Ground from tools/ground.py
(the canonical heightmap); nothing reads a world.

  python tools/south_density.py [--source-root R] [--json OUT]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
WORLD_READS: set = set()
BUCKET = 32
GAP_STEP = 32
WALK_REACH = 250
SOUTH_ROWS = ("F", "G", "H")

CATEGORY = {
    "placements.json": "places", "structures.json": "places", "ruins.json": "places", "mines.json": "places",
    "markets.json": "places", "far_south.json": "residents",
    "resident_encounters.json": "residents", "southern_residents.json": "residents",
    "northern_residents.json": "residents",
    "trainers.json": "trainers", "route_trainers.json": "trainers", "vr_trainers.json": "trainers",
    "late_route_trainers.json": "trainers", "arena_trainers.json": "trainers", "gym_trainers.json": "trainers",
    "shrines.json": "shrines",
    "habitat_blocks.json": "encounters", "mega_dens.json": "encounters", "gulch_mine.json": "encounters",
    "rewards.json": "caches",
    "legendaries.json": "legendary", "adopted_legendary_sites.json": "legendary",
    "npc_seats.json": "npcs", "traders.json": "npcs",
    "landmarks.json": "landmarks", "signposts.json": "landmarks", "elder_trees.json": "landmarks",
    "themed_saplings.json": "landmarks",
    "towns.json": "towns",
}
# files in the residents format (a list of sites, each with a centre and pieces placed by relative offsets)
RESIDENT_FILES = ("southern_residents.json", "northern_residents.json", "far_south.json")
# relative offsets elsewhere (a piece's `at`, a template's anchor) are small numbers; nothing authored stands within 64
# blocks of the map's north-west corner, so a point there is an offset, not a place, and is dropped
ORIGIN_GUARD = 64
CATS = ("places", "residents", "trainers", "shrines", "encounters", "caches", "legendary", "npcs", "landmarks", "towns")
KEYS = ("centre", "center", "position", "anchor", "site", "seat", "at", "placement")


def points(obj, out, size=8192):
    """tools/poi_heatmap.py's extraction: every x/z an object carries, recursively."""
    if isinstance(obj, dict):
        x = z = None
        if isinstance(obj.get("x"), (int, float)) and isinstance(obj.get("z"), (int, float)):
            x, z = obj["x"], obj["z"]
        if x is None:
            for k in KEYS:
                c = obj.get(k)
                if isinstance(c, dict) and isinstance(c.get("x"), (int, float)) and isinstance(c.get("z"), (int, float)):
                    x, z = c["x"], c["z"]
                    break
                if isinstance(c, list) and len(c) in (2, 3) and all(isinstance(v, (int, float)) for v in c):
                    x, z = c[0], c[-1]
                    break
        if x is not None and 0 <= x < size and 0 <= z < size:
            out.append((float(x), float(z)))
        for v in obj.values():
            points(v, out, size)
    elif isinstance(obj, list):
        for v in obj:
            points(v, out, size)


def place_boxes(data=DATA):
    """{file name: (x0, z0, x1, z1)} for every record with bbox.writes."""
    out = {}
    for f in sorted(Path(data).glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        b = d.get("bbox") if isinstance(d, dict) else None
        w = b.get("writes") if isinstance(b, dict) else None
        if isinstance(w, dict) and "x" in w and "z" in w:
            out[f.name] = (w["x"][0], w["z"][0], w["x"][1], w["z"][1])
    return out


def counted(data=DATA):
    """{category: [(x, z, source file)]}, deduplicated to one per 32-block bucket per file."""
    out = collections.defaultdict(list)
    for name, cat in CATEGORY.items():
        f = Path(data) / name
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if name in RESIDENT_FILES:
            # a residents-format file: one thing per site at its centre. Its pieces carry RELATIVE offsets under the
            # same keys the generic extraction reads (`at`), which would count as points near the map's origin
            for r in d["residents"]:
                x, z = r["site"]["centre"]
                out["residents" if (r.get("pokemon") or r.get("npc")) else "places"].append((float(x), float(z), name))
            continue
        p = []
        points(d, p)
        seen = set()
        for x, z in p:
            if x < ORIGIN_GUARD and z < ORIGIN_GUARD:
                continue
            k = (int(x) // BUCKET, int(z) // BUCKET)
            if k not in seen:
                seen.add(k)
                out[cat].append((x, z, name))
    for name, (x0, z0, x1, z1) in place_boxes(data).items():
        if name in CATEGORY:
            continue
        out["places"].append(((x0 + x1) / 2.0, (z0 + z1) / 2.0, name))
    # legendary sites: data/legendaries.json carries a sited chamber's way in as `mouth` or `portal` (keys the generic
    # extraction does not read), and an adopted site is a data/placements.json donor whose id starts legendary_
    for e in json.loads((Path(data) / "legendaries.json").read_text(encoding="utf-8"))["encounters"]:
        at = e.get("mouth") or e.get("portal")
        if e.get("status") == "sited" and isinstance(at, list):
            out["legendary"].append((float(at[0]), float(at[-1]), "legendaries.json"))
    pl = {(int(p["position"]["x"]) // BUCKET, int(p["position"]["z"]) // BUCKET)
          for p in json.loads((Path(data) / "placements.json").read_text(encoding="utf-8"))["placements"]
          if p["id"].startswith("legendary_") and isinstance(p.get("position"), dict)}
    keep = []
    for x, z, src in out["places"]:
        if src == "placements.json" and (int(x) // BUCKET, int(z) // BUCKET) in pl:
            out["legendary"].append((x, z, src))
        else:
            keep.append((x, z, src))
    out["places"] = keep
    return out


def cell_of(x, z, grid):
    s = grid["cell_size"]
    c, r = int(x - grid["origin_x"]) // s, int(z - grid["origin_z"]) // s
    if 0 <= c < grid["columns"] and 0 <= r < grid["rows"]:
        return grid["row_labels"][r] + grid["column_labels"][c]
    return None


def inside(poly, x, z):
    n, hit = len(poly), False
    for i in range(n):
        x1, z1 = poly[i]
        x2, z2 = poly[(i + 1) % n]
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) * (x2 - x1) / float(z2 - z1):
            hit = not hit
    return hit


def seg_dist(px, pz, a, b):
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))


def poly_dist(poly, x, z):
    return min(seg_dist(x, z, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def subregion_at(regions, x, z):
    for s in regions["subregions"]:
        if any(inside(pg, x, z) for pg in s.get("polygons") or []):
            return s["id"], (s.get("paint") or {}).get("preset")
    return None, None


def measure(g, data=DATA):
    world = json.loads((Path(data) / "world.json").read_text(encoding="utf-8"))
    grid = world["grid"]
    import terrain as T
    sea = T.sea_level(world)
    regions = json.loads((Path(data) / "regions.json").read_text(encoding="utf-8"))
    rift = [r for r in regions["regions"] if r["id"] == "the_rift"][0]["polygons"][0]
    reach = json.loads((Path(data) / "rift_sculpt.json").read_text(encoding="utf-8"))["rim"]["reach"]
    pts = counted(data)
    s = grid["cell_size"]
    cells = {}
    h = g.heights
    for r, rl in enumerate(grid["row_labels"]):
        for c, cl in enumerate(grid["column_labels"]):
            block = h[r * s:(r + 1) * s:8, c * s:(c + 1) * s:8]
            cells[rl + cl] = {"land_pct": round(100.0 * float((np.round(block) > sea).mean()), 1),
                              "rift_pct": 0.0, "counts": {k: 0 for k in CATS}, "total": 0}
    # Rift share, sampled every 64 blocks
    for r, rl in enumerate(grid["row_labels"]):
        for c, cl in enumerate(grid["column_labels"]):
            n = hit = 0
            for z in range(r * s + 32, (r + 1) * s, 64):
                for x in range(c * s + 32, (c + 1) * s, 64):
                    n += 1
                    hit += inside(rift, x, z)
            cells[rl + cl]["rift_pct"] = round(100.0 * hit / n, 1)
    for cat, lst in pts.items():
        for x, z, _src in lst:
            k = cell_of(x, z, grid)
            if k:
                cells[k]["counts"][cat] += 1
                cells[k]["total"] += 1
    for k, v in cells.items():
        km2 = (v["land_pct"] / 100.0) * (s * s) / 1e6
        v["land_km2"] = round(km2, 3)
        v["per_land_km2"] = round(v["total"] / km2, 1) if km2 > 0.05 else None
    # the gaps
    allp = np.array([(x, z) for lst in pts.values() for x, z, _ in lst], dtype=float)
    boxes = list(place_boxes(data).values())
    for t in json.loads((Path(data) / "towns.json").read_text(encoding="utf-8"))["towns"]:
        fp = t.get("footprint") or {}
        if all(k in fp for k in ("min_x", "min_z", "max_x", "max_z")):
            boxes.append((fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"]))
    paths = json.loads((Path(data) / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    walk = np.array([(x, z, i) for i, (n, p) in enumerate(sorted(paths.items())) for x, z in p], dtype=float)
    names = sorted(paths)
    rows = [grid["row_labels"].index(r) for r in SOUTH_ROWS]
    gaps = []
    for r in rows:
        for z in range(r * s + GAP_STEP // 2, (r + 1) * s, GAP_STEP):
            for x in range(GAP_STEP // 2, grid["columns"] * s, GAP_STEP):
                if g(x, z) <= sea:
                    continue
                dw = np.hypot(walk[:, 0] - x, walk[:, 1] - z)
                i = int(dw.argmin())
                if any(b[0] - 40 <= x <= b[2] + 40 and b[1] - 40 <= z <= b[3] + 40 for b in boxes):
                    continue
                if inside(rift, x, z) or poly_dist(rift, x, z) < reach + 40:
                    continue
                dn = float(np.hypot(allp[:, 0] - x, allp[:, 1] - z).min())
                sub, paint = subregion_at(regions, x, z)
                bx = g.box(x - 16, z - 16, x + 16, z + 16)
                gaps.append({"walked": bool(dw[i] <= WALK_REACH), "relief_33": int(bx.max() - bx.min()),
                             "x": x, "z": z, "cell": cell_of(x, z, grid), "nearest_counted": round(dn),
                             "path": names[int(walk[i, 2])], "off_path": round(float(dw[i])), "ground": g(x, z),
                             "subregion": sub, "paint": paint})
    best, picks = {}, collections.defaultdict(list)
    for gp in sorted(gaps, key=lambda d: -d["nearest_counted"]):
        if gp["walked"] and gp["cell"] not in best:
            best[gp["cell"]] = gp
        lst = picks[gp["cell"]]
        if len(lst) < 4 and all(math.hypot(gp["x"] - o["x"], gp["z"] - o["z"]) >= 300 for o in lst):
            lst.append(gp)
    return {"cells": cells, "categories": {k: len(v) for k, v in pts.items()}, "emptiest_per_cell": best, "candidates": dict(picks),
            "top_gaps": sorted(gaps, key=lambda d: -d["nearest_counted"])[:40], "sea": sea}


def bands(cells):
    out = {}
    for name, rows in (("north A-E", "ABCDE"), ("south F-H", "FGH")):
        tot = sum(v["total"] for k, v in cells.items() if k[0] in rows)
        km2 = sum(v["land_km2"] for k, v in cells.items() if k[0] in rows)
        out[name] = {"things": tot, "land_km2": round(km2, 2), "per_land_km2": round(tot / km2, 1),
                     "by_category": {c: sum(v["counts"][c] for k, v in cells.items() if k[0] in rows) for c in CATS}}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    import ground as G
    g = G.load(a.source_root)
    m = measure(g)
    m["bands"] = bands(m["cells"])
    if a.json:
        Path(a.json).write_text(json.dumps(m, indent=1), encoding="utf-8")
    for k, v in m["bands"].items():
        print("%-10s %4d things over %6.2f km2 of land: %5.1f a km2  %s" % (k, v["things"], v["land_km2"],
                                                                           v["per_land_km2"], v["by_category"]))
    print("cell  land%  rift%  total  /km2  " + " ".join("%-5s" % c[:5] for c in CATS))
    for k in sorted(m["cells"], key=lambda k: (k[0], int(k[1:]))):
        v = m["cells"][k]
        print("%-4s %6.1f %6.1f %6d %5s  %s" % (k, v["land_pct"], v["rift_pct"], v["total"], v["per_land_km2"],
                                               " ".join("%-5d" % v["counts"][c] for c in CATS)))
    print("emptiest walkable point per southern cell:")
    for k in sorted(m["emptiest_per_cell"]):
        gp = m["emptiest_per_cell"][k]
        print("  %s (%d, %d) y%d: %d from anything counted; %s %d off; %s / %s"
              % (k, gp["x"], gp["z"], gp["ground"], gp["nearest_counted"], gp["path"], gp["off_path"],
                 gp["subregion"], gp["paint"]))
    print("up to four candidates per southern cell, 300 apart, walked or not:")
    for k in sorted(m["candidates"]):
        for gp in m["candidates"][k]:
            print("  %s (%d, %d) y%d relief %d: %d from anything counted; %s %d off%s; %s / %s"
                  % (k, gp["x"], gp["z"], gp["ground"], gp["relief_33"], gp["nearest_counted"], gp["path"],
                     gp["off_path"], "" if gp["walked"] else " (UNWALKED)", gp["subregion"], gp["paint"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
