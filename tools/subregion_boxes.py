#!/usr/bin/env python
"""Turn a sub-region polygon from data/regions.json into the axis-aligned boxes a Cobblemon spawn
condition can carry.

Why this exists: a Cobblemon spawn condition constrains position with minX/maxX/minZ/maxZ, so an
authored sub-region reaches the world only as a set of rectangles. Until 2026-09-17 the only boxes
that existed were the route corridor boxes in data/routes.json, so a sub-region no route passed
through compiled to nothing at all (35 of 71 scopes, 350 entries).

The decomposition rasterises the polygon on a grid, drops cells already covered by a route corridor
box (the corridor keeps its own finer table; without this both tables would spawn in the same place
and the weights would double), and greedily merges the remaining cells into maximal rectangles.

  python tools/subregion_boxes.py                 # report boxes per sub-region
  python tools/subregion_boxes.py --grid 32       # coarser, fewer boxes

Ownership: a pure geometry helper for tools/compile_spawns.py; it makes no roster decisions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRID = 16


def point_in_polygon(x, z, poly):
    """Ray casting; poly is [[x, z], ...] and is treated as closed."""
    inside = False
    n = len(poly)
    for i in range(n):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % n]
        if (z0 > z) != (z1 > z):
            xint = x0 + (z - z0) * (x1 - x0) / (z1 - z0)
            if x < xint:
                inside = not inside
    return inside


def rasterise(polygons, grid):
    """{(cx, cz)} of grid cells whose centre lies in any polygon, plus the cell-space origin."""
    xs = [p[0] for poly in polygons for p in poly]
    zs = [p[1] for poly in polygons for p in poly]
    x0 = (min(xs) // grid) * grid
    z0 = (min(zs) // grid) * grid
    nx = int((max(xs) - x0) // grid) + 1
    nz = int((max(zs) - z0) // grid) + 1
    cells = set()
    for iz in range(nz):
        for ix in range(nx):
            cx = x0 + ix * grid + grid / 2.0
            cz = z0 + iz * grid + grid / 2.0
            if any(point_in_polygon(cx, cz, poly) for poly in polygons):
                cells.add((ix, iz))
    return cells, x0, z0, nx, nz


def covered_by(cells, x0, z0, grid, boxes):
    """Cells whose centre falls inside one of the given world-space boxes."""
    out = set()
    for ix, iz in cells:
        cx = x0 + ix * grid + grid / 2.0
        cz = z0 + iz * grid + grid / 2.0
        for b in boxes:
            if b[0] <= cx <= b[1] and b[2] <= cz <= b[3]:
                out.add((ix, iz))
                break
    return out


def merge_rectangles(cells):
    """Greedy maximal rectangles over a set of (ix, iz) cells: [(ix0, ix1, iz0, iz1)] inclusive."""
    todo = set(cells)
    out = []
    while todo:
        ix0, iz0 = min(todo, key=lambda c: (c[1], c[0]))
        ix1 = ix0
        while (ix1 + 1, iz0) in todo:
            ix1 += 1
        iz1 = iz0
        while all((ix, iz1 + 1) in todo for ix in range(ix0, ix1 + 1)):
            iz1 += 1
        for iz in range(iz0, iz1 + 1):
            for ix in range(ix0, ix1 + 1):
                todo.discard((ix, iz))
        out.append((ix0, ix1, iz0, iz1))
    return out


def boxes_for(polygons, grid=DEFAULT_GRID, exclude=()):
    """World-space [(minX, maxX, minZ, maxZ)] covering the polygons, minus the excluded boxes."""
    cells, x0, z0, _, _ = rasterise(polygons, grid)
    if exclude:
        cells -= covered_by(cells, x0, z0, grid, exclude)
    out = []
    for ix0, ix1, iz0, iz1 in merge_rectangles(cells):
        out.append((int(x0 + ix0 * grid), int(x0 + (ix1 + 1) * grid - 1),
                    int(z0 + iz0 * grid), int(z0 + (iz1 + 1) * grid - 1)))
    return sorted(out)


def area(boxes):
    return sum((b[1] - b[0] + 1) * (b[3] - b[2] + 1) for b in boxes)


def route_boxes(routes):
    out = []
    for r in routes["routes"]:
        for b in r["spawn_scope"]["boxes"]:
            out.append((b["min_x"], b["max_x"], b["min_z"], b["max_z"]))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--regions", default=str(ROOT / "data" / "regions.json"))
    p.add_argument("--routes", default=str(ROOT / "data" / "routes.json"))
    p.add_argument("--grid", type=int, default=DEFAULT_GRID)
    p.add_argument("--no-exclude", action="store_true", help="keep cells the route corridors already cover")
    a = p.parse_args(argv)
    regions = json.loads(Path(a.regions).read_text(encoding="utf-8"))
    routes = json.loads(Path(a.routes).read_text(encoding="utf-8"))
    ex = () if a.no_exclude else route_boxes(routes)
    total_boxes = total_area = 0
    print("%-30s %6s %10s %10s" % ("sub-region", "boxes", "blocks", "corridor"))
    for s in regions["subregions"]:
        full = boxes_for(s["polygons"], a.grid)
        kept = boxes_for(s["polygons"], a.grid, ex)
        total_boxes += len(kept)
        total_area += area(kept)
        print("%-30s %6d %10s %10s" % (s["id"], len(kept), format(area(kept), ","),
                                       format(area(full) - area(kept), ",")))
    print("\n%d sub-regions, %d boxes, %s blocks" % (len(regions["subregions"]), total_boxes, format(total_area, ",")))


if __name__ == "__main__":
    main()
