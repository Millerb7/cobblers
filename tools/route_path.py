#!/usr/bin/env python
"""Route a path between two points, paying for climb so it follows contours.

A* on the block grid, eight-connected. Step cost is horizontal distance plus
slope_weight times the absolute height change, so a high slope weight makes the
router go around a ridge rather than over it.

Produces a candidate polyline. A human decides whether that is the road.

The same module holds the descent searches used for rivers (descend_min_cut,
descend_route): paths whose bed never rises, and the cut needed to force one.
tools/grade_rivers.py runs them.

  python tools/route_path.py --world tests/fixtures/terrain/world.json \
      --from 60,130 --to 170,130 --slope-weight 12
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
from array import array
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


# ------------------------------------------------------- monotonic descent
#
# A river bed may never rise in the direction of flow. A path of cells carries a
# surface profile P: at each cell P is the lowest ground met so far, because the
# bed can be cut down to P but never raised. Where the ground stands above P the
# path needs a cut of (ground - P) to keep descending. Water bodies on the path
# are flat at their level: a river may drop into one (level <= P) but can never
# be cut into one that stands above it.
#
# descend_min_cut finds the smallest worst cut any descending path needs.
# descend_route then finds the cheapest path that stays within a cut allowance.
# Both work on a grid of cell heights; the caller picks the resolution.


def _descent_step(g, wl, ni, P, water_tol):
    """(cut, new P) for stepping into cell ni from surface P, or None if blocked."""
    lv = wl[ni] if wl is not None else None
    if lv is not None and lv == lv:              # a water body: flat at its level
        if lv > P + water_tol:
            return None
        return 0.0, (lv if lv < P else P)
    gv = g[ni]
    if gv > P:
        return gv - P, P
    return 0.0, gv


def _trace(lab_cell, lab_P, lab_parent, lid, w):
    cells, prof = [], []
    while lid >= 0:
        z, x = divmod(lab_cell[lid], w)
        cells.append((x, z))
        prof.append(lab_P[lid])
        lid = lab_parent[lid]
    cells.reverse()
    prof.reverse()
    return cells, prof


def descend_min_cut(ground, sources, source_level, goal, water=None, goal_cut=None,
                    cap=64.0, water_tol=0.5, cell_size=1.0):
    """Least worst-cut descending path from any source cell to any goal cell.

    Exact label-setting search on (worst cut so far, surface P): labels leave the
    queue in order of worst cut, so a cell's earlier label always has a smaller or
    equal cut, and a later label survives only if it keeps a higher surface.

    ground      2-D array of bed heights per cell
    sources     iterable of (x, z) cells, all starting at surface source_level
    goal        2-D bool mask; reaching any goal cell ends the search
    water       2-D array: level of a water body, NaN where there is none
    goal_cut    2-D array: cut still needed downstream of a goal cell (NaN = none)
    cap         cuts deeper than this are never taken

    Returns None when no path exists within cap, otherwise a dict with the worst
    cut, the path cells, the surface profile and the index of the worst cut.
    """
    h, w = ground.shape
    g = ground.astype(np.float64).ravel().tolist()
    wl = water.astype(np.float64).ravel().tolist() if water is not None else None
    gl = goal.ravel().tolist()
    gc = goal_cut.astype(np.float64).ravel().tolist() if goal_cut is not None else None
    settled = [-math.inf] * (h * w)
    lab_cell, lab_P, lab_parent = array("l"), array("d"), array("l")
    pq = []
    for x, z in sources:
        i = z * w + x
        c0 = 0.0
        if gl[i] and gc is not None and gc[i] == gc[i] and gc[i] > 0:
            if gc[i] > cap:
                continue
            c0 = gc[i]
        lab_cell.append(i)
        lab_P.append(float(source_level))
        lab_parent.append(-1)
        heapq.heappush(pq, (c0, -float(source_level), 0.0, len(lab_cell) - 1))
    diag = math.sqrt(2.0) * cell_size
    while pq:
        c, negP, dist, lid = heapq.heappop(pq)
        cur = lab_cell[lid]
        P = -negP
        if P <= settled[cur]:
            continue
        settled[cur] = P
        if gl[cur]:
            cells, prof = _trace(lab_cell, lab_P, lab_parent, lid, w)
            return {"cut": c, "cells": cells, "profile": prof,
                    "length": dist, "labels": len(lab_cell)}
        cz, cx = divmod(cur, w)
        for dx, dz in NEIGHBOURS:
            nx, nz = cx + dx, cz + dz
            if nx < 0 or nz < 0 or nx >= w or nz >= h:
                continue
            ni = nz * w + nx
            step = _descent_step(g, wl, ni, P, water_tol)
            if step is None:
                continue
            cut, nP = step
            if cut > cap or nP <= settled[ni]:
                continue
            nc = c if c >= cut else cut
            if gl[ni] and gc is not None:
                extra = gc[ni]
                if extra == extra and extra > nc:
                    if extra > cap:
                        continue
                    nc = extra
            lab_cell.append(ni)
            lab_P.append(nP)
            lab_parent.append(lid)
            heapq.heappush(pq, (nc, -nP, dist + (diag if dx and dz else cell_size), len(lab_cell) - 1))
    return None


def descend_route(ground, sources, source_level, goal, max_cut, penalty=None, water=None,
                  heuristic=None, cut_weight=1.0, water_tol=0.5, level_eps=0.5, cell_size=1.0):
    """Cheapest descending path whose every cut stays within max_cut.

    A* on cost. Each step costs its length times (1 + penalty of the cell entered +
    cut_weight * cut there), so the router prefers low valley ground and shallow
    cuts. A cell keeps a later, costlier label only if that label holds a surface
    more than level_eps higher; that makes the search exact to level_eps blocks.

    penalty     2-D array >= 0, extra cost per block of length (None = 0)
    heuristic   2-D array, an underestimate of the remaining length (None = 0)
    """
    h, w = ground.shape
    g = ground.astype(np.float64).ravel().tolist()
    wl = water.astype(np.float64).ravel().tolist() if water is not None else None
    gl = goal.ravel().tolist()
    pen = penalty.astype(np.float64).ravel().tolist() if penalty is not None else None
    hl = heuristic.astype(np.float64).ravel().tolist() if heuristic is not None else None
    settled = [-math.inf] * (h * w)
    lab_cell, lab_P, lab_parent = array("l"), array("d"), array("l")
    pq = []
    for x, z in sources:
        i = z * w + x
        lab_cell.append(i)
        lab_P.append(float(source_level))
        lab_parent.append(-1)
        heapq.heappush(pq, (hl[i] if hl else 0.0, 0.0, len(lab_cell) - 1))
    while pq:
        _, cost, lid = heapq.heappop(pq)
        cur = lab_cell[lid]
        P = lab_P[lid]
        if settled[cur] != -math.inf and P <= settled[cur] + level_eps:
            continue
        settled[cur] = max(settled[cur], P)
        if gl[cur]:
            cells, prof = _trace(lab_cell, lab_P, lab_parent, lid, w)
            return {"cost": cost, "cells": cells, "profile": prof, "labels": len(lab_cell)}
        cz, cx = divmod(cur, w)
        for dx, dz in NEIGHBOURS:
            nx, nz = cx + dx, cz + dz
            if nx < 0 or nz < 0 or nx >= w or nz >= h:
                continue
            ni = nz * w + nx
            step = _descent_step(g, wl, ni, P, water_tol)
            if step is None:
                continue
            cut, nP = step
            if cut > max_cut:
                continue
            if settled[ni] != -math.inf and nP <= settled[ni] + level_eps:
                continue
            length = cell_size * (math.sqrt(2.0) if dx and dz else 1.0)
            nc = cost + length * (1.0 + (pen[ni] if pen else 0.0) + cut_weight * cut)
            lab_cell.append(ni)
            lab_P.append(nP)
            lab_parent.append(lid)
            heapq.heappush(pq, (nc + (hl[ni] if hl else 0.0), nc, len(lab_cell) - 1))
    return None


def worst_cut(ground_profile):
    """Along an ordered bed profile, the deepest cut a non-rising bed needs, and where."""
    run, worst, at = math.inf, 0.0, None
    for i, y in enumerate(ground_profile):
        if y < run:
            run = y
        elif y - run > worst:
            worst, at = y - run, i
    return worst, at


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
