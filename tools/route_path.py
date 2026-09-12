#!/usr/bin/env python
"""Route a path between two points, paying for climb so it follows contours.

A* on the block grid, eight-connected. Step cost is horizontal distance plus
slope_weight times the absolute height change, so a high slope weight makes the
router go around a ridge rather than over it.

Produces a candidate polyline. A human decides whether that is the road.

  python tools/route_path.py --world tests/fixtures/terrain/world.json \
      --from 60,130 --to 170,130 --slope-weight 12
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
from pathlib import Path

import numpy as np

import terrain as T

NEIGHBOURS = [(-1, 0), (1, 0), (0, -1), (0, 1),
              (-1, -1), (-1, 1), (1, -1), (1, 1)]


def parse_point(s):
    x, z = s.split(",")
    return int(x), int(z)


def route(heights, passable, start, goal, slope_weight):
    h, w = heights.shape
    sx, sz = start
    gx, gz = goal
    if not passable[sz, sx]:
        raise SystemExit("start (%d,%d) is not passable" % start)
    if not passable[gz, gx]:
        raise SystemExit("goal (%d,%d) is not passable" % goal)

    def heuristic(x, z):
        dx, dz = abs(x - gx), abs(z - gz)
        return (dx + dz) - (2 - math.sqrt(2)) * min(dx, dz)

    start_i, goal_i = sz * w + sx, gz * w + gx
    best = {start_i: 0.0}
    came = {}
    pq = [(heuristic(sx, sz), 0.0, start_i)]
    seen = set()

    while pq:
        _, cost, cur = heapq.heappop(pq)
        if cur in seen:
            continue
        seen.add(cur)
        if cur == goal_i:
            break
        cz, cx = divmod(cur, w)
        ch = heights[cz, cx]
        for dx, dz in NEIGHBOURS:
            nx, nz = cx + dx, cz + dz
            if not (0 <= nx < w and 0 <= nz < h) or not passable[nz, nx]:
                continue
            ni = nz * w + nx
            if ni in seen:
                continue
            flat = math.sqrt(2.0) if dx and dz else 1.0
            climb = abs(float(heights[nz, nx]) - float(ch))
            nc = cost + flat + slope_weight * climb
            if nc < best.get(ni, float("inf")):
                best[ni] = nc
                came[ni] = cur
                heapq.heappush(pq, (nc + heuristic(nx, nz), nc, ni))

    if goal_i not in best:
        return None, None
    path, cur = [], goal_i
    while cur != start_i:
        cz, cx = divmod(cur, w)
        path.append((cx, cz))
        cur = came[cur]
    path.append((sx, sz))
    path.reverse()
    return path, best[goal_i]


def simplify(points, tolerance=0.6):
    """Drop collinear interior points so the polyline is readable."""
    if len(points) < 3:
        return list(points)
    out = [points[0]]
    for prev, cur, nxt in zip(points, points[1:], points[2:]):
        ax, az = cur[0] - prev[0], cur[1] - prev[1]
        bx, bz = nxt[0] - cur[0], nxt[1] - cur[1]
        if abs(ax * bz - az * bx) > tolerance or (ax, az) != (bx, bz):
            out.append(cur)
    out.append(points[-1])
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--from", dest="start", required=True, metavar="X,Z")
    p.add_argument("--to", dest="goal", required=True, metavar="X,Z")
    p.add_argument("--slope-weight", type=float, default=8.0,
                   help="cost per block of climb; 0 gives a straight line")
    p.add_argument("--max-slope", type=float, default=40.0,
                   help="terrain steeper than this is impassable, in degrees")
    p.add_argument("--allow-water", action="store_true",
                   help="allow routing below sea level")
    p.add_argument("--id", default="route", help="identifier for the output file")
    a = p.parse_args(argv)

    try:
        heights, world = T.load_from_args(a)
    except T.TerrainUnavailable as exc:
        raise SystemExit("terrain unavailable: %s" % exc)

    slope = T.slope_degrees(heights)
    passable = slope <= a.max_slope
    if not a.allow_water:
        passable &= heights > T.sea_level(world)

    start, goal = parse_point(a.start), parse_point(a.goal)
    path, cost = route(heights, passable, start, goal, a.slope_weight)
    if path is None:
        raise SystemExit("no route from %s to %s under these constraints" % (a.start, a.goal))

    ys = [float(heights[z, x]) for x, z in path]
    climb = sum(abs(b - a_) for a_, b in zip(ys, ys[1:]))
    flat_len = sum(math.hypot(x2 - x1, z2 - z1)
                   for (x1, z1), (x2, z2) in zip(path, path[1:]))
    straight = math.hypot(goal[0] - start[0], goal[1] - start[1])

    payload = {
        "schema": "cobblers.derived.path/1",
        "id": a.id,
        "parameters": {
            "from": list(start), "to": list(goal),
            "slope_weight": a.slope_weight, "max_slope_degrees": a.max_slope,
            "allow_water": a.allow_water,
        },
        "source": T.provenance(world, a.world),
        "stats": {
            "cost": round(float(cost), 3),
            "length_blocks": round(flat_len, 2),
            "straight_line_blocks": round(straight, 2),
            "detour_ratio": round(flat_len / straight, 3) if straight else None,
            "total_climb": round(climb, 2),
            "min_y": round(min(ys), 2),
            "max_y": round(max(ys), 2),
        },
        "polyline": [[int(x), int(z)] for x, z in simplify(path)],
        "dense_point_count": len(path),
    }
    out = Path(a.out) if a.out else T.ROOT / "derived" / "paths" / ("%s.json" % a.id)
    T.write_json(out, payload)
    s = payload["stats"]
    print("route %s -> %s: %.1f blocks (straight %.1f, detour x%.2f), climb %.1f, "
          "max y %.0f -> %s" % (a.start, a.goal, s["length_blocks"],
                                s["straight_line_blocks"], s["detour_ratio"] or 0,
                                s["total_climb"], s["max_y"], out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
