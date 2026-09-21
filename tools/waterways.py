#!/usr/bin/env python
"""Turn a waterway centreline from data/waterways.json into spawn boxes with a weight ramp along it.

A river is a line and a habitat block is a sphere, so a habitat block is the wrong tool: covering the
1,300-block Mt Clay outflow at range 48 would take fourteen blocks and turn a 96-block-wide disc of
forest into Wooper country for the creek's whole length. Coordinate boxes follow the line instead,
and `neededNearbyBlocks: ["minecraft:water"]` on the entries keeps the spawns at the water's edge, so
the boxes can be generous without the banks becoming river.

Each grid cell within `half_width` of the centreline is assigned to its nearest segment, and each
segment's cells are merged into rectangles on their own, so no two boxes overlap and no block gets a
doubled weight. A segment's weight multiplier is interpolated from `weight_ramp` by how far along the
line it sits, which is how a roster thins downstream.

  python tools/waterways.py                     # report the boxes each waterway compiles to

Ownership: geometry only, for tools/compile_spawns.py. Rosters live in data/spawns.json, scoped to
the waterway id.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import subregion_boxes

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRID = 16


def seg_distance(px, pz, ax, az, bx, bz):
    """(distance from the point to the segment, how far along the segment the nearest point is, 0..1)."""
    dx, dz = bx - ax, bz - az
    den = dx * dx + dz * dz
    t = 0.0 if not den else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / den))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz)), t


def segments(polyline):
    """[(ax, az, bx, bz, length, distance of its start along the whole line)]."""
    out, run = [], 0.0
    for (ax, az), (bx, bz) in zip(polyline, polyline[1:]):
        length = math.hypot(bx - ax, bz - az)
        out.append((ax, az, bx, bz, length, run))
        run += length
    return out


def boxes_by_segment(polyline, half_width, grid=DEFAULT_GRID):
    """[(segment index, fraction along the line, [(minX, maxX, minZ, maxZ)])], boxes disjoint."""
    segs = segments(polyline)
    total = sum(s[4] for s in segs) or 1.0
    xs = [p[0] for p in polyline]
    zs = [p[1] for p in polyline]
    x0 = (min(xs) - half_width) // grid * grid
    z0 = (min(zs) - half_width) // grid * grid
    nx = int((max(xs) + half_width - x0) // grid) + 1
    nz = int((max(zs) + half_width - z0) // grid) + 1
    owned = {}
    for iz in range(nz):
        for ix in range(nx):
            cx = x0 + ix * grid + grid / 2.0
            cz = z0 + iz * grid + grid / 2.0
            best = None
            for i, (ax, az, bx, bz, length, run) in enumerate(segs):
                d, t = seg_distance(cx, cz, ax, az, bx, bz)
                if d <= half_width and (best is None or d < best[0]):
                    best = (d, i, (run + t * length) / total)
            if best:
                owned.setdefault(best[1], (best[2], set()))[1].add((ix, iz))
    out = []
    for i in sorted(owned):
        frac, cells = owned[i]
        boxes = [(int(x0 + a * grid), int(x0 + (b + 1) * grid - 1),
                  int(z0 + c * grid), int(z0 + (d + 1) * grid - 1))
                 for a, b, c, d in subregion_boxes.merge_rectangles(cells)]
        out.append((i, frac, sorted(boxes)))
    return out


def ramp(weight_ramp, frac):
    """The weight multiplier at `frac` along the line, interpolated between the authored ends."""
    head = float(weight_ramp.get("head", 1.0))
    mouth = float(weight_ramp.get("mouth", 1.0))
    return head + (mouth - head) * frac


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--waterways", default=str(ROOT / "data" / "waterways.json"))
    p.add_argument("--grid", type=int, default=DEFAULT_GRID)
    a = p.parse_args(argv)
    doc = json.loads(Path(a.waterways).read_text(encoding="utf-8"))
    for w in doc["waterways"]:
        segs = boxes_by_segment(w["polyline"], w["half_width"], a.grid)
        boxes = [b for _, _, bs in segs for b in bs]
        area = subregion_boxes.area(boxes)
        length = sum(s[4] for s in segments(w["polyline"]))
        print("%-22s %d segments, %d boxes, %s blocks, centreline %d long, weight %.2f -> %.2f"
              % (w["id"], len(segs), len(boxes), format(area, ","), round(length),
                 ramp(w["weight_ramp"], 0.0), ramp(w["weight_ramp"], 1.0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
