#!/usr/bin/env python
"""Close the sub-region polygon gaps that route corridors cross, so every route sample has a sub-region.

The sub-region polygons were simplified at a 24-block tolerance, which leaves slivers of land between neighbours
(about 2.9% of land on the 2026-09-16 heightmap). A route crossing a sliver has a stretch with no sub-region, and
coordinate-box spawns cannot be compiled for it. This tool fills only the slivers inside route corridors:

  - land (above sea level) within a --band-wide strip along a route's dense path that no sub-region polygon covers is a gap pixel
  - each gap pixel goes to the nearest covering sub-region, by growing the neighbouring labels one block at a time
    (4-connected) through the gap
  - each sub-region's new pixels are merged into CELL-block squares and then into rectangles (row runs merged
    vertically), and appended to its polygons as axis-aligned rings

Existing polygons are never moved or removed. Every run is recorded in regions.json geometry.gap_closures.

  python tools/close_route_gaps.py --source-root <root> --paths build/routes/paths.json [--write]
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import terrain as T

ROOT = T.ROOT
CELL = 4
GROW = 64


def in_ring(xs, zs, ring):
    """Vectorised even-odd ray casting with the same edge rule as build_routes.point_in_poly."""
    inside = np.zeros(len(xs), bool)
    n = len(ring)
    for i in range(n):
        xi, zi = ring[i]
        xj, zj = ring[i - 1]
        crosses = (zi > zs) != (zj > zs)
        if not crosses.any():
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (xj - xi) * (zs - zi) / (zj - zi) + xi
        inside ^= crosses & (xs < xint)
    return inside


def rects_from_mask(mask):
    """Row runs merged vertically into (x0, x1, z0, z1) inclusive cell rectangles."""
    h, w = mask.shape
    active, rects = {}, []
    for z in range(h):
        row = mask[z]
        runs, x = [], 0
        while x < w:
            if not row[x]:
                x += 1
                continue
            a = x
            while x + 1 < w and row[x + 1]:
                x += 1
            runs.append((a, x))
            x += 1
        keep = set(runs)
        for run, (z0, z1) in list(active.items()):
            if run not in keep:
                rects.append((run[0], run[1], z0, z1))
                del active[run]
        for run in runs:
            active[run] = (active[run][0], z) if run in active else (z, z)
    rects.extend((run[0], run[1], z0, z1) for run, (z0, z1) in active.items())
    return sorted(rects, key=lambda r: (r[2], r[0]))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--paths", default=str(ROOT / "build" / "routes" / "paths.json"), help="dense route paths from build_routes.py")
    p.add_argument("--routes", default=str(ROOT / "data" / "routes.json"), help="for corridor widths")
    p.add_argument("--regions", default=str(ROOT / "data" / "regions.json"))
    p.add_argument("--band", type=int, default=16,
                   help="width in blocks of the band around each dense route path to close (the spawn compiler and the hole "
                        "count read the centreline; the full corridor width would add rings nothing reads)")
    p.add_argument("--write", action="store_true")
    a = p.parse_args(argv)

    heights, world = T.load_from_args(a)
    H, W = heights.shape
    land = heights > float(T.sea_level(world))
    cache = json.loads(Path(a.paths).read_text(encoding="utf-8"))
    if cache["heightmap_sha256"] != world["heightmap"]["sha256"]:
        raise SystemExit("paths were routed on %s, not %s" % (cache["heightmap_sha256"][:8], world["heightmap"]["sha256"][:8]))
    widths = {r["id"]: r["corridor"]["width_blocks"] for r in json.loads(Path(a.routes).read_text(encoding="utf-8"))["routes"]}
    regions = json.loads(Path(a.regions).read_text(encoding="utf-8"))
    subs = regions["subregions"]

    corridor = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(corridor)
    for rid, path in cache["paths"].items():
        d.line([tuple(q) for q in path], fill=1, width=int(min(a.band, widths[rid])), joint="curve")
    corridor = np.asarray(corridor, dtype=bool)
    # the growth below needs labels around the band too; test membership exactly as build_routes.py does (ray casting,
    # so a polygon's right and lower edges are outside), on the band grown by GROW blocks
    grow = corridor.copy()
    for _ in range(GROW):
        g2 = grow.copy()
        g2[1:, :] |= grow[:-1, :]; g2[:-1, :] |= grow[1:, :]; g2[:, 1:] |= grow[:, :-1]; g2[:, :-1] |= grow[:, 1:]
        grow = g2
    zz, xx = np.nonzero(grow)
    label = np.zeros((H, W), np.int16)
    for i, s in enumerate(subs, 1):
        inside = np.zeros(len(xx), bool)
        for ring in s["polygons"]:
            inside |= in_ring(xx, zz, ring)
        sel = inside & (label[zz, xx] == 0)
        label[zz[sel], xx[sel]] = i
    gap = corridor & land & (label == 0)
    print("gap pixels inside route corridors: %d" % gap.sum())

    # grow neighbouring labels into the gap, one block per pass, 4-connected, lowest label index wins ties
    fill = np.where(gap, 0, label).astype(np.int16)
    todo = gap.copy()
    passes = 0
    while todo.any():
        grown = fill.copy()
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            src = np.roll(np.roll(fill, dz, axis=0), dx, axis=1)
            take = todo & (grown == 0) & (src > 0)
            grown[take] = src[take]
        newly = todo & (grown > 0)
        if not newly.any():
            break
        fill, todo = grown, todo & ~newly
        passes += 1
    unfilled = int(todo.sum())
    print("filled in %d passes; %d gap pixels have no neighbouring sub-region (enclosed by sea)" % (passes, unfilled))

    added, record = {}, []
    ncz, ncx = math.ceil(H / CELL), math.ceil(W / CELL)
    for i, s in enumerate(subs, 1):
        mine = gap & (fill == i)
        if not mine.any():
            continue
        pad = np.zeros((ncz * CELL, ncx * CELL), bool)
        pad[:H, :W] = mine
        cells = pad.reshape(ncz, CELL, ncx, CELL).any(axis=(1, 3))
        rings = []
        for x0, x1, z0, z1 in rects_from_mask(cells):
            # exclusive far edges: under ray casting a ring's right and lower edges are outside, so the ring
            # [x0, x1 + 1) x [z0, z1 + 1) covers blocks x0..x1, z0..z1 exactly
            bx0, bz0 = x0 * CELL, z0 * CELL
            bx1, bz1 = min(W, (x1 + 1) * CELL), min(H, (z1 + 1) * CELL)
            rings.append([[bx0, bz0], [bx1, bz0], [bx1, bz1], [bx0, bz1]])
        added[s["id"]] = rings
        record.append({"subregion": s["id"], "gap_pixels": int(mine.sum()), "rings_added": len(rings)})
    print("rings to add: %d across %d sub-regions" % (sum(len(v) for v in added.values()), len(added)))
    for r in record:
        print("  %-26s %6d px  %4d rings" % (r["subregion"], r["gap_pixels"], r["rings_added"]))

    if a.write:
        for s in subs:
            if s["id"] in added:
                s["polygons"].extend(added[s["id"]])
        runs = regions["geometry"].pop("gap_closures", None) or []
        if "gap_closure" in regions["geometry"]:              # the first run's single record
            runs.insert(0, regions["geometry"].pop("gap_closure"))
        regions["geometry"]["gap_closures"] = runs
        runs.append({
            "date": datetime.date.today().isoformat(), "generator": "tools/close_route_gaps.py",
            "heightmap_sha256": world["heightmap"]["sha256"],
            "method": "land within a %d-block band along each dense route path covered by no sub-region polygon, assigned to the nearest covering sub-region by "
                      "4-connected growth, merged into %d-block rectangles and appended to that sub-region's polygons; no existing ring "
                      "was moved" % (a.band, CELL),
            "gap_pixels": int(gap.sum()), "unfilled_pixels_enclosed_by_sea": unfilled, "subregions": record,
            "note": "Rings appended after each sub-region's original polygons are the closures; measured blocks are re-derived by tools/region_measure.py.",
        })
        Path(a.regions).write_text(json.dumps(regions, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", a.regions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
