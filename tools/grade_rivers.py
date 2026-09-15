#!/usr/bin/env python
"""Grade rivers and lake outflows so every bed descends to the sea, then cut them.

A river bed may never rise in the direction of flow. The earlier carves followed
the ground and rose by up to 59 blocks, so no water could run along them. This
tool does not repair those carves. It asks the terrain whether a descending
course exists at all (tools/route_path.py, descend_min_cut / descend_route):

  plan  From every lake (starting at its painted water level) and every inland
        end of a carved river, find the smallest worst cut any descending path to
        the nearest open sea needs. Lakes go lowest first, then inland ends, so a
        later course may join a lake or course that already reaches the sea. A
        course whose worst cut exceeds --max-gouge is no river and is never
        graded. For the rest, route the cheapest descending course within the
        allowance, re-measure it at full resolution, and write a graded polyline:
        x, z, water surface, bed floor. Separately, for each carved river, test
        whether water can run inside a band along the axis that was drawn.
        Writes data/rivers.json.
  cut   Lower the heightmap along every graded course that is still valid:
        a flat bed of the recorded width at the floor, banks at the recorded
        slope up to natural ground. Only ever lowers. Writes a new 16-bit PNG
        beside the source heightmap (never over it) and records its sha256.
        Then re-measures every course on the new file.

Banks, meanders, gravel bars and pools are composition and are left to Axiom.

  python tools/grade_rivers.py plan
  python tools/grade_rivers.py cut --out-name land_8k_16_eroded_rivers.png
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import heapq
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import terrain as T
import drainage as D
import route_path as R

FACTOR = 4                 # routing grid: 4-block cells, min-pooled so a one-block channel survives
MAX_GOUGE = 20.0           # a worst cut deeper than this means the terrain does not want a river
SLACK = 2.0                # extra cut the cost router may spend beyond the minimum, for a natural course
BED_RADIUS = 2             # full-res bed at a station: lowest ground within this radius
NEAR_LAKE = 150            # a river end this close to a lake belongs to that lake
NEAR_SEA = 150             # a river end this close to open sea is a mouth, not a source
DEST_RADIUS = 400          # a sea end of a carve: open sea within this distance of it
CORRIDOR = 100             # half width of the band around a carved axis when testing the carve itself
CANAL_PCT = 50             # a course cut along more than this share of its length is a canal
BURN = 100.0               # courses are lowered this much on the planning grid so drainage follows them
TRIBUTARY_KM2 = 0.25       # a stream draining at least this much counts as a tributary
WALL_RISE = 10.0           # a valley wall: ground at least this far above the water surface ...
WALL_REACH = 250           # ... within this many blocks of the channel, on each side (the Glacial Tear is 396 wide)
WALL_RUN = 3               # the head is the first of this many consecutive walled stations ...
WALL_STEP = 48             # ... sampled this far apart along the path (so a 96-block confined stretch at least)
REACH = 64                 # reach length along a course, blocks
MAJOR_VALLEY_WIDTH = 16    # the major river gets a floodplain and terraces once it is this wide
VALLEY_MAX_GRADE = 0.02    # steeper reaches are confined: steep banks, no floodplain or terraces
VALLEY_CLEAR = 150         # no floodplain or terraces within this many blocks of a lake on the course
FREEBOARD = 1.0           # every river's surface sits this far under the lowest ground, so it has banks
MAJOR_INCISION = 8.0       # the major river is let down up to this far, scaled by sqrt(catchment share)
INCISION_TAPER = 0.02      # below a lake outlet the incision grows at most this much per block
GRADE_WINDOW = 128         # surface drop is measured over this much course around a reach
CHARACTER_RULES = {
    "catchment": "D8 accumulation on the priority-flooded planning grid with every cut course burned in; "
                 "a station takes the largest catchment within one cell, never less than upstream",
    "grade": "drop of the graded surface over the reach and half a grade window either side, per block",
    "width": "rivers: (3 + 4.5 * sqrt(catchment km2)) * speed, 3..19; on the major river the larger of that and "
             "30 * sqrt(catchment / the course's largest dry catchment) * speed, up to 32; "
             "speed = (grade / 0.005) ** -0.2 clamped 0.75..1.3, so slow water is wider",
    "depth": "centre depth, rivers: 1 + 1.1 * catchment ** 0.45, 1..4.5; on the major river the larger of that and "
             "9 * (catchment / largest dry catchment) ** 0.4; the bed is a parabola to one block deep at the edge",
    "bank_slope": "rise per run, interpolated on log10(grade) from -3.0 to -1.5: 0.4 at grade 0.001 or less, "
                  "2.0 at 0.0316 or more",
    "bed": "GRAVEL at grade >= 0.01, SAND at >= 0.0025, CLAY (silt) below",
    "incision": "the water surface is the lowest ground met so far minus the incision, kept non-rising: 1 block on "
                "every river, up to 8 on the major river scaled by sqrt(catchment share); never below the level the "
                "course ends in, zero on lakes, and below a lake outlet it grows at most 0.02 per block",
    "valley": "major river reaches at least 16 wide, with grade under 0.02 and more than 150 blocks from a lake on "
              "the course: floodplain one block above the water, width "
              "10 + 0.6 * width * sqrt(0.01 / grade) (10..48); two terraces of 5 blocks, treads 0.6 and 0.4 of the "
              "floodplain; valley wall 0.6 beyond",
}
SCHEMA = "cobblers.rivers/1"


# ----------------------------------------------------------------- grids

def coarse_grids(heights, sea):
    n = heights.shape[0] // FACTOR
    H = heights[:n * FACTOR, :n * FACTOR].reshape(n, FACTOR, n, FACTOR)
    ymin = H.min(axis=(1, 3)).astype(np.float64)
    ymean = H.mean(axis=(1, 3)).astype(np.float64)
    # local relief: height above the mean of a 100-block box; valley floors are <= 0
    k = 100 // FACTOR // 2
    pad = np.pad(ymean, k + 1, mode="edge")
    cs = pad.cumsum(0).cumsum(1)
    box = (cs[2 * k + 1:, 2 * k + 1:] - cs[:-2 * k - 1, 2 * k + 1:]
           - cs[2 * k + 1:, :-2 * k - 1] + cs[:-2 * k - 1, :-2 * k - 1]) / (2 * k + 1) ** 2
    relief = ymean - box[:n, :n]
    penalty = np.clip(relief, 0, 30) / 10.0
    return ymin, penalty, open_sea_mask(ymin < sea)


def open_sea_mask(below):
    """Cells below sea level that connect to the map edge (4-connected), by flood fill from a padded border."""
    img = Image.fromarray(np.pad(below, 1, constant_values=True).astype(np.uint8) * 255).copy()
    ImageDraw.floodfill(img, (0, 0), 128)
    return (np.array(img) == 128)[1:-1, 1:-1]


def water_bodies(landmarks, ymin):
    """Lakes painted with water: id -> (level, coarse mask), plus a level grid."""
    n = ymin.shape[0]
    levels = np.full((n, n), np.nan)
    ids = np.full((n, n), -1, np.int32)
    lakes = []
    for lm in landmarks:
        wb = lm.get("water_body")
        if not isinstance(wb, dict) or wb.get("level_y") is None:
            continue
        im = Image.new("L", (n, n), 0)
        d = ImageDraw.Draw(im)
        for poly in wb.get("basin_polygons") or []:
            d.polygon([(x / FACTOR, z / FACTOR) for x, z in poly], fill=1)
        mask = (np.array(im) > 0) & (ymin < wb["level_y"])
        if not mask.any():
            continue
        lakes.append({"id": lm["id"], "name": lm.get("name"), "level": float(wb["level_y"]),
                      "spill": (lm.get("measured") or {}).get("basin_spill_y"), "mask": mask})
        levels[mask] = wb["level_y"]
        ids[mask] = len(lakes) - 1
    return lakes, levels, ids


def distance_heuristic(goal, coarse=4):
    """Underestimate of path length in blocks to the nearest goal cell (octile on 16-block cells)."""
    n = goal.shape[0]
    m = n // coarse
    g = goal[:m * coarse, :m * coarse].reshape(m, coarse, m, coarse).any(axis=(1, 3))
    dist = [math.inf] * (m * m)
    pq = []
    for z, x in zip(*np.nonzero(g)):
        i = int(z) * m + int(x)
        dist[i] = 0.0
        pq.append((0.0, i))
    heapq.heapify(pq)
    while pq:
        d, i = heapq.heappop(pq)
        if d > dist[i]:
            continue
        z, x = divmod(i, m)
        for dx, dz in R.NEIGHBOURS:
            nx, nz = x + dx, z + dz
            if 0 <= nx < m and 0 <= nz < m:
                nd = d + (1.4142135623730951 if dx and dz else 1.0)
                j = nz * m + nx
                if nd < dist[j]:
                    dist[j] = nd
                    heapq.heappush(pq, (nd, j))
    block = FACTOR * coarse
    h = np.array(dist).reshape(m, m) * block / 1.0824 - block * math.sqrt(2)
    h = np.maximum(h, 0)
    h = np.repeat(np.repeat(h, coarse, 0), coarse, 1)
    out = np.zeros(goal.shape)
    out[:h.shape[0], :h.shape[1]] = h
    return out


# ------------------------------------------------------------- measuring

def dense_course(heights, cells, levels, ids, lakes, sea):
    """Stations at one-block spacing along a coarse path, with the full-res bed at each."""
    n = heights.shape[0]
    centres = [(x * FACTOR + FACTOR // 2, z * FACTOR + FACTOR // 2) for x, z in cells]
    stations = []
    for i, (x0, z0) in enumerate(centres):
        if i + 1 < len(centres):
            x1, z1 = centres[i + 1]
            k = max(1, int(math.ceil(math.hypot(x1 - x0, z1 - z0))))
        else:
            x1, z1, k = x0, z0, 1
        for s in range(k):
            x = int(round(x0 + (x1 - x0) * s / k))
            z = int(round(z0 + (z1 - z0) * s / k))
            if stations and stations[-1][:2] == (x, z):
                continue
            cx, cz = cells[i]
            lake = int(ids[cz, cx])
            if levels[cz, cx] == levels[cz, cx]:      # a lake, or a river graded earlier: flat at its surface
                bed = float(levels[cz, cx])
            else:
                r = BED_RADIUS
                bed = float(heights[max(0, z - r):min(n, z + r + 1), max(0, x - r):min(n, x + r + 1)].min())
            stations.append((x, z, bed, lake))
    return stations


def grade(stations, sea, start_level=None):
    beds = [s[2] for s in stations]
    if start_level is not None:
        beds[0] = min(beds[0], start_level)
    surface, run = [], math.inf
    for b in beds:
        run = min(run, b)
        surface.append(max(run, sea))
    worst, at = R.worst_cut([max(b, sea) for b in beds])   # ground below sea level is never a rise
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(stations, stations[1:]))
    return beds, surface, worst, at, length


def simplify_graded(points, planar_tol=1.5, vertical_tol=0.5):
    """Douglas-Peucker on (x, z, floor): keep a vertex when the plan or the grade needs it."""
    if len(points) < 3:
        return list(points)
    dist = [0.0]
    for a, b in zip(points, points[1:]):
        dist.append(dist[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        ax, az, _, af = points[i]
        bx, bz, _, bf = points[j]
        seg = math.hypot(bx - ax, bz - az) or 1e-9
        worst, wk = 0.0, None
        for k in range(i + 1, j):
            px, pz, _, pf = points[k]
            planar = abs((bx - ax) * (az - pz) - (ax - px) * (bz - az)) / seg
            t = (dist[k] - dist[i]) / ((dist[j] - dist[i]) or 1e-9)
            vertical = abs(af + (bf - af) * t - pf)
            e = max(planar / planar_tol, vertical / vertical_tol)
            if e > worst:
                worst, wk = e, k
        if worst > 1.0:
            keep[wk] = True
            stack += [(i, wk), (wk, j)]
    return [p for p, k in zip(points, keep) if k]


def station_ref(st, i):
    if i is None:
        return None
    return {"x": st[i][0], "z": st[i][1]}


# ------------------------------------------------------------------ plan

def nearest_lake(lakes, x, z):
    best = None
    for lk in lakes:
        zz, xx = np.nonzero(lk["mask"])
        d = float(np.min(np.hypot(xx * FACTOR + FACTOR // 2 - x, zz * FACTOR + FACTOR // 2 - z)))
        if d <= NEAR_LAKE and (best is None or d < best[1]):
            best = (lk["id"], d)
    return best[0] if best else None


def near_open_sea(open_sea, x, z):
    r = NEAR_SEA // FACTOR
    cx, cz = x // FACTOR, z // FACTOR
    return bool(open_sea[max(0, cz - r):cz + r + 1, max(0, cx - r):cx + r + 1].any())


def disk(shape, x, z, radius):
    n = shape[0]
    zz, xx = np.mgrid[0:n, 0:n]
    return np.hypot(xx - x / FACTOR, zz - z / FACTOR) <= radius / FACTOR


def polyline_distance(polyline, x, z):
    best = math.inf
    for (ax, az), (bx, bz) in zip(polyline, polyline[1:]):
        dx, dz = bx - ax, bz - az
        t = ((x - ax) * dx + (z - az) * dz) / float(dx * dx + dz * dz or 1)
        t = min(1.0, max(0.0, t))
        best = min(best, math.hypot(ax + t * dx - x, az + t * dz - z))
    return best


def rivers_from_landmarks(landmarks, lakes, open_sea):
    """Each carved river or dry ravine, with each end classified: at a lake, at the sea, or inland (a possible
    source). Rivers already redrawn on a graded course (their axis is the course) are listed but are not
    sources and not confluence targets: the plan made them."""
    rivers = []

    def derived(lm):
        ax = next((a for a in lm.get("axes") or [] if a.get("id") == "channel"), {})
        return str(ax.get("basis", "")).startswith("graded course")

    for lm in landmarks:
        if lm.get("kind") not in ("river", "ravine"):
            continue
        meas = lm.get("measured") or {}
        ends = []
        for which in ("high_end", "low_end"):
            e = meas.get(which)
            if not e:
                continue
            lake = nearest_lake(lakes, e["x"], e["z"])
            at = "lake" if lake else ("sea" if near_open_sea(open_sea, e["x"], e["z"]) else "inland")
            ends.append({"end": which, "x": e["x"], "z": e["z"], "bed_y": e.get("bed"), "at": at, "lake": lake})
        axis = next((a for a in lm.get("axes") or [] if a.get("id") == "channel"), {})
        for e in ends:
            if e["at"] != "inland":
                continue
            for other in landmarks:
                if other is lm or other.get("kind") not in ("river", "ravine") or derived(other):
                    continue
                oax = next((a for a in other.get("axes") or [] if a.get("id") == "channel"), {})
                if polyline_distance(oax.get("polyline") or [], e["x"], e["z"]) <= CORRIDOR:
                    e["at"], e["confluence_with"] = "confluence", other["id"]
                    break
        if derived(lm):
            for e in ends:
                if e["at"] == "inland":
                    e["at"] = "graded_source"
        rivers.append({
            "id": lm["id"], "name": lm.get("name"),
            "landmark_kind": lm["kind"],
            "graded_courses": lm.get("graded_courses"),
            "kind": "creek" if lm.get("annotated") is False else "river",
            "annotated": lm.get("annotated", True) is not False,
            "ends": ends,
            "lakes_at_ends": sorted({e["lake"] for e in ends if e["lake"]}),
            "_axis": axis.get("polyline") or [],
        })
    return rivers


def corridor_mask(shape, polyline, half_width):
    im = Image.new("L", (shape[1], shape[0]), 0)
    d = ImageDraw.Draw(im)
    pts = [(x / FACTOR, z / FACTOR) for x, z in polyline]
    w = max(1, int(round(2 * half_width / FACTOR)))
    d.line(pts, fill=1, width=w)
    r = half_width / FACTOR
    for x, z in pts:
        d.ellipse((x - r, z - r, x + r, z + r), fill=1)
    return np.array(im) > 0


def run_course(ctx, sources, start_level, own_body=None, only=None):
    """Minimum worst cut to the nearest sea, then, within the gouge limit, the graded course.

    Earlier valid bodies (lakes with a real outflow, rivers already graded) are goals too: a course
    that reaches one at or below its own surface joins it and inherits its downstream cut.
    only: a list of body ids; when given, those bodies are the only goals.
    """
    ymin, levels, ids, bodies = ctx["ymin"], ctx["levels"], ctx["ids"], ctx["bodies"]

    def goals(limit):
        goal = ctx["open_sea"].copy() if only is None else np.zeros(ymin.shape, bool)
        goal_cut = np.full(ymin.shape, np.nan)
        for b in bodies:
            if only is not None and b["id"] not in only:
                continue
            if b is own_body or b.get("chain_cut") is None or b["chain_cut"] > limit:
                continue
            goal |= b["mask"]
            goal_cut[b["mask"]] = b["chain_cut"]
        return goal, goal_cut

    goal, goal_cut = goals(ctx["max_gouge"])
    best = R.descend_min_cut(ymin, sources, start_level, goal, water=levels, goal_cut=goal_cut,
                             cap=ctx["cap"], cell_size=FACTOR)
    out = {"min_worst_cut": None, "valid": False}
    if best is None:
        out["verdict"] = "no river: no descending course within a %.0f-block cut" % ctx["cap"]
        return out, None
    end_cell = best["cells"][-1]
    end_body = int(ids[end_cell[1], end_cell[0]])
    st = dense_course(ctx["heights"], best["cells"], levels, ids, bodies, ctx["sea"])
    _, _, _, at_full, _ = grade(st, ctx["sea"], start_level)
    out.update({
        "min_worst_cut": round(best["cut"], 1),
        "min_worst_cut_basis": "%d-block grid, including any cut still needed below the body it joins" % FACTOR,
        "ends_in": bodies[end_body]["id"] if end_body >= 0 else "open_sea",
        "end_at": {"x": st[-1][0], "z": st[-1][1]},
    })
    if best["cut"] > ctx["max_gouge"]:
        out["verdict"] = "no river: the least-cut descending course still needs a %.1f-block cut" % best["cut"]
        out["worst_cut_at"] = station_ref(st, at_full)
        return out, None
    allowance = min(ctx["max_gouge"], best["cut"] + SLACK)
    goal2, _ = goals(allowance)
    routed = R.descend_route(ymin, sources, start_level, goal2, allowance, penalty=ctx["penalty"], water=levels,
                             heuristic=distance_heuristic(goal2), cut_weight=0.5, cell_size=FACTOR)
    if routed is None:            # the cost search is exact only to level_eps; fall back to the min-cut course
        routed = best
    st = dense_course(ctx["heights"], routed["cells"], levels, ids, bodies, ctx["sea"])
    beds, surface, worst, at, length = grade(st, ctx["sea"], start_level)
    end_cell = routed["cells"][-1]
    end_body = int(ids[end_cell[1], end_cell[0]])
    downstream = (bodies[end_body].get("chain_cut") or 0.0) if end_body >= 0 else 0.0
    crossed = []
    for s in st:
        if s[3] >= 0 and bodies[s[3]]["id"] not in crossed:
            crossed.append(bodies[s[3]]["id"])
    cut_pct = round(100.0 * sum(1 for b, s in zip(beds, surface) if b > s + 0.5) / len(st), 1)
    out.update({
        "ends_in": bodies[end_body]["id"] if end_body >= 0 else "open_sea",
        "end_at": {"x": st[-1][0], "z": st[-1][1]},
        "routed": {
            "length_blocks": round(length),
            "surface_start_y": round(surface[0], 1),
            "surface_end_y": round(surface[-1], 1),
            "total_drop": round(surface[0] - surface[-1], 1),
            "worst_cut": round(worst, 1),
            "worst_cut_basis": "full resolution, lowest ground within %d blocks of the centreline" % BED_RADIUS,
            "worst_cut_at": station_ref(st, at),
            "worst_cut_to_sea": round(max(worst, downstream), 1),
            "stations_needing_cut_pct": cut_pct,
            "water_bodies_on_course": crossed,
        },
    })
    if worst > ctx["max_gouge"]:
        out["verdict"] = ("no river: the grid said %.1f but the course needs a %.1f-block cut at full resolution"
                          % (best["cut"], worst))
        return out, None
    out["valid"] = True
    if cut_pct > CANAL_PCT and worst > 3.0:
        out["canal"] = True
        out["verdict"] = ("canal, not a river: descends only by cutting up to %.1f blocks along %.0f%% of its "
                          "length; graded but not cut unless asked" % (worst, cut_pct))
    else:
        out["verdict"] = "descends" if worst <= 1.0 else "descends with a cut of up to %.1f blocks" % worst
    out["_chain_cut"] = max(worst, downstream)
    return out, (st, surface)


def stamp_course(ctx, course_id, stations, surface, chain_cut):
    """Make a graded course a flat body at its surface, so later courses can join it."""
    levels, ids = ctx["levels"], ctx["ids"]
    cell_surface = {}
    for s, y in zip(stations, surface):
        key = (s[1] // FACTOR, s[0] // FACTOR)
        cell_surface[key] = min(cell_surface.get(key, math.inf), y)
    body = {"id": course_id, "kind": "course", "chain_cut": chain_cut, "mask": np.zeros(levels.shape, bool)}
    ctx["bodies"].append(body)
    k = len(ctx["bodies"]) - 1
    for (cz, cx), y in cell_surface.items():
        if levels[cz, cx] != levels[cz, cx]:
            levels[cz, cx] = y
            ids[cz, cx] = k
            body["mask"][cz, cx] = True


def along_channel(ctx, rv, by_id, lake_levels):
    """Can water run where the channel was carved? Least worst cut inside a band around its axis,
    from each end that could be a source (a lake at its level, an inland end at its ground) to the other end."""
    ymin, open_sea, cap = ctx["ymin"], ctx["open_sea"], ctx["cap"]
    if len(rv["ends"]) < 2 or not rv["_axis"]:
        return None
    band = corridor_mask(ymin.shape, rv["_axis"], CORRIDOR)
    for e in rv["ends"]:
        if e["at"] == "lake":
            band |= by_id[e["lake"]]["mask"]
    ground = np.where(band, ymin, 1e9)
    rows = []
    for src in rv["ends"]:
        if src["at"] == "sea":
            continue
        dst = next(o for o in rv["ends"] if o is not src)
        if dst["at"] == "sea":
            goal = open_sea & disk(ymin.shape, dst["x"], dst["z"], DEST_RADIUS)
        elif dst["at"] == "lake":
            goal = by_id[dst["lake"]]["mask"].copy()
        else:
            goal = disk(ymin.shape, dst["x"], dst["z"], 60) & np.isnan(lake_levels)
        if src["at"] == "lake":
            lk = by_id[src["lake"]]
            if dst.get("lake") == lk["id"]:
                continue
            cells = [(int(x), int(z)) for z, x in zip(*np.nonzero(lk["mask"]))]
            level, name = lk["level"], lk["id"]
        else:
            x, z = src["x"] // FACTOR, src["z"] // FACTOR
            cells, level, name = [(x, z)], float(ymin[z, x]), "%s end %d,%d" % (src["at"], src["x"], src["z"])
        best = R.descend_min_cut(ground, cells, level, goal, water=lake_levels, cap=cap, cell_size=FACTOR)
        to = dst["lake"] if dst["at"] == "lake" else "%s end %d,%d" % (dst["at"], dst["x"], dst["z"])
        row = {"from": name, "from_y": round(level, 1), "to": to,
               "min_worst_cut": round(best["cut"], 1) if best else None}
        if best is None:
            row["verdict"] = "no descending course inside the band within a %.0f-block cut" % cap
        elif best["cut"] > ctx["max_gouge"]:
            row["verdict"] = "no river along the carve: needs a %.1f-block cut" % best["cut"]
        else:
            row["verdict"] = "water can run along the carve with a cut of up to %.1f blocks" % best["cut"]
        rows.append(row)
    return {"band_half_width": CORRIDOR, "basis": "%d-block grid, inside the band around the carved axis" % FACTOR,
            "directions": rows}


def base_heightmap(world, world_path, source_root, explicit=None):
    """The authored heightmap the rivers are planned on: heightmap.derived_from when the import is a
    derived file (the cut output), else the heightmap itself. Returns (path, sha256); the hash is checked."""
    hm = world.get("heightmap") or {}
    der = hm.get("derived_from")
    base = dict(world, heightmap=dict(hm, path=der["path"], sha256=der["sha256"])) if der else world
    if explicit:
        return T.verify_file(explicit, base, world_path), base["heightmap"]["sha256"]
    return T.resolve_heightmap(base, world_path, source_root), base["heightmap"]["sha256"]


# ------------------------------------------------------------ character


def walled_stations(heights, st, surface, step=WALL_STEP, reach=WALL_REACH, rise=WALL_RISE):
    """Along a dense course: (distance, x, z, walled) every `step` blocks, walled when the ground rises `rise` blocks
    above the water surface within `reach` blocks on both sides of the channel (authored heights)."""
    chain = [0.0]
    for a, b in zip(st, st[1:]):
        chain.append(chain[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    out, nz, nx = [], heights.shape[0], heights.shape[1]
    t = np.arange(4, reach + 1, 2, dtype=np.float64)
    k = 0
    for i, s_ in enumerate(st):
        if chain[i] < k * step:
            continue
        k = int(chain[i] // step) + 1
        j0, j1 = max(0, i - 6), min(len(st) - 1, i + 6)
        dx, dz = st[j1][0] - st[j0][0], st[j1][1] - st[j0][1]
        L = math.hypot(dx, dz) or 1.0
        px, pz = -dz / L, dx / L
        sides = []
        for sign in (-1, 1):
            xs = np.clip(np.rint(s_[0] + sign * px * t).astype(int), 0, nx - 1)
            zs = np.clip(np.rint(s_[1] + sign * pz * t).astype(int), 0, nz - 1)
            sides.append(float(heights[zs, xs].max()) - surface[i] >= rise)
        out.append((round(chain[i]), int(s_[0]), int(s_[1]), all(sides)))
    return out


def valley_head(heights, st, surface, run=WALL_RUN):
    """Index into st of the first station that starts `run` consecutive walled samples, or None."""
    rows = walled_stations(heights, st, surface)
    for a in range(len(rows) - run + 1):
        if all(r[3] for r in rows[a:a + run]):
            d = rows[a][0]
            chain = 0.0
            for i in range(1, len(st)):
                chain += math.hypot(st[i][0] - st[i - 1][0], st[i][1] - st[i - 1][1])
                if chain >= d:
                    return i, d, rows
            return 0, d, rows
    return None, None, rows

def drainage_for(ctx, course_ids):
    """Catchment on the planning grid with the given courses burned in, so flow follows them."""
    burn = ctx["ymin"].copy()
    for cid in course_ids:
        for cz, cx in {(s[1] // FACTOR, s[0] // FACTOR) for s in ctx["dense"][cid][0]}:
            burn[cz, cx] -= BURN
    filled, order = D.priority_flood(burn, ctx["open_sea"], ctx["sea"])
    dirs = D.d8(filled, ctx["open_sea"])
    acc = D.accumulation(dirs, order)
    return {"km2": acc * FACTOR * FACTOR / 1e6, "dirs": dirs, "filled": filled, "burn": burn, "order": order}


def coastal_systems(ctx, dr, min_km2=0.4):
    """Every river system that reaches the sea: catchment at the mouth, the longest descending flow
    path (steps inside filled basins are flats, not flow, and are not counted), its head, and the
    tributaries of at least TRIBUTARY_KM2 joining the main stem."""
    km2, dirs, filled, burn, order = dr["km2"], dr["dirs"], dr["filled"], dr["burn"], dr["order"]
    n = km2.shape[0]
    flat = (filled - burn).ravel() > 0.5
    up = np.zeros(n * n)
    head = np.arange(n * n)
    dl = dirs.ravel()
    for i in reversed(order):
        k = dl[i]
        if k < 0:
            continue
        dz, dx = D.NB[k]
        j = i + dz * n + dx
        step = 0.0 if flat[i] else FACTOR * (1.4142135623730951 if dz and dx else 1.0)
        if up[i] + step > up[j]:
            up[j] = up[i] + step
            head[j] = head[i]
    sea = ctx["open_sea"]
    out = []
    for z, x in zip(*np.nonzero(~sea & (km2 >= min_km2))):
        r = D.receiver(dirs, z, x)
        if r and not sea[r]:
            continue
        if not r and not sea[max(0, z - 1):z + 2, max(0, x - 1):x + 2].any():
            continue                      # a sink inland; a cell level with the sea beside it is a mouth
        stem, tribs, cz, cx = 0, 0, z, x
        while True:
            donors = [(km2[cz - dz, cx - dx], cz - dz, cx - dx) for k, (dz, dx) in enumerate(D.NB)
                      if 0 <= cz - dz < n and 0 <= cx - dx < n and dirs[cz - dz, cx - dx] == k]
            if not donors:
                break
            donors.sort(reverse=True)
            tribs += sum(1 for d_ in donors[1:] if d_[0] >= TRIBUTARY_KM2)
            _, cz, cx = donors[0]
            stem += 1
        hz, hx = divmod(int(head[z * n + x]), n)
        out.append({"mouth": {"x": int(x) * FACTOR, "z": int(z) * FACTOR}, "catchment_km2": round(float(km2[z, x]), 2),
                    "longest_descending_path_blocks": round(float(up[z * n + x])),
                    "tributaries": tribs, "head": {"x": hx * FACTOR, "z": hz * FACTOR, "ground_y": round(float(ctx["ymin"][hz, hx]), 1)},
                    "_cell": (int(z), int(x)), "_head_cell": (hz, hx)})
    out.sort(key=lambda s: -s["catchment_km2"])
    return out


def farthest_descending_source(ctx, start_cells):
    """The cell farthest (along the ground) from which water can run down to start_cells without any
    rise: a search outward from the start over ground that never falls, lakes flat at their level.
    Returns ((z, x), distance in blocks)."""
    ymin, levels, sea = ctx["ymin"], ctx["levels"], ctx["open_sea"]
    h, w = ymin.shape
    eff = np.where(levels == levels, levels, ymin).ravel().tolist()
    blocked = sea.ravel().tolist()
    dist = {}
    pq = []
    for z, x in start_cells:
        i = z * w + x
        dist[i] = 0.0
        pq.append((0.0, i))
    heapq.heapify(pq)
    far, far_d = start_cells[0][0] * w + start_cells[0][1], 0.0
    while pq:
        dcur, i = heapq.heappop(pq)
        if dcur > dist.get(i, math.inf):
            continue
        if dcur > far_d:
            far, far_d = i, dcur
        z, x = divmod(i, w)
        e = eff[i]
        for dz, dx in D.NB:
            nz, nx = z + dz, x + dx
            if 0 <= nz < h and 0 <= nx < w:
                j = nz * w + nx
                if blocked[j] or eff[j] < e:
                    continue
                nd = dcur + FACTOR * (1.4142135623730951 if dz and dx else 1.0)
                if nd < dist.get(j, math.inf):
                    dist[j] = nd
                    heapq.heappush(pq, (nd, j))
    return divmod(far, w), far_d


def characterise(ctx, cid, km2, major=False):
    """Reaches of a graded course, each sized from its catchment and shaped by its grade. On the major
    river, size is relative to the course's own largest catchment, so each of its courses reaches the
    major scale at its lower end and narrows upstream."""
    st, surface = ctx["dense"][cid]
    bodies = ctx["bodies"]
    chain = [0.0]
    for a, b in zip(st, st[1:]):
        chain.append(chain[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    run, catch = 0.0, []
    for s in st:
        cz, cx = s[1] // FACTOR, s[0] // FACTOR
        a = float(km2[max(0, cz - 1):cz + 2, max(0, cx - 1):cx + 2].max())
        run = max(run, a)
        catch.append(run)
    water = [s[3] >= 0 and bodies[s[3]].get("kind") != "course" for s in st]
    total = chain[-1]
    # the major scale is the largest catchment on open river: stations within VALLEY_CLEAR of a lake on the course are
    # left out, because tributaries converge at a lake's edge and one reach there would shrink everything upstream
    wet_chain = [c for c, w in zip(chain, water) if w]
    open_catch = [a for a, c, w in zip(catch, chain, water)
                  if not w and all(abs(c - wc) >= VALLEY_CLEAR for wc in wet_chain)]
    major_mouth_km2 = (max(open_catch or [a for a, w in zip(catch, water) if not w] or catch) or None) if major else None
    reaches, i0 = [], 0
    while i0 < len(st) - 1:
        i1 = i0
        while i1 < len(st) - 1 and chain[i1] - chain[i0] < REACH and water[i1] == water[i0]:
            i1 += 1
        lo = max(0, next(k for k in range(i0, -1, -1) if chain[i0] - chain[k] >= GRADE_WINDOW / 2 or k == 0))
        hi = next((k for k in range(i1, len(st)) if chain[k] - chain[i1] >= GRADE_WINDOW / 2), len(st) - 1)
        g = max(1e-4, (surface[lo] - surface[hi]) / max(1.0, chain[hi] - chain[lo]))
        A = catch[i1]
        reaches.append(reach_character(chain[i0], chain[i1], A, g, water[i0], major_mouth_km2))
        i0 = i1
    # a floodplain and terraces belong to open valley, not to the mouth of a lake: none within VALLEY_CLEAR of one
    wet = [r for r in reaches if r["water_body"]]
    for r in reaches:
        if "valley" in r and any(min(abs(r["from_m"] - w["to_m"]), abs(w["from_m"] - r["to_m"])) < VALLEY_CLEAR
                                 for w in wet):
            del r["valley"]
            r["valley_omitted"] = "within %d blocks of a lake" % VALLEY_CLEAR
    return reaches, chain, total


def reach_character(c0, c1, A, g, water, major_mouth_km2=None):
    lg = math.log10(g)
    bank = float(np.interp(lg, [-3.0, -1.5], [0.4, 2.0]))          # rise per run: shallow where slow, steep where fast
    speed = float(np.clip((g / 0.005) ** -0.2, 0.75, 1.3))          # same flow, slower water: wider section
    bed = "GRAVEL" if g >= 0.01 else ("SAND" if g >= 0.0025 else "CLAY")
    row = {"from_m": round(c0), "to_m": round(c1), "catchment_km2": round(A, 3), "grade": round(g, 4),
           "water_body": bool(water), "bank_slope": round(bank, 2), "bed": bed}
    width = float(np.clip((3.0 + 4.5 * math.sqrt(A)) * speed, 3.0, 19.0))
    depth = float(np.clip(1.0 + 1.1 * A ** 0.45, 1.0, 4.5))
    if major_mouth_km2:
        f = min(1.0, A / major_mouth_km2)
        width = max(width, float(np.clip(30.0 * math.sqrt(f) * speed, 3.0, 32.0)))
        depth = max(depth, float(np.clip(9.0 * f ** 0.4, 1.0, 9.0)))
        if width >= MAJOR_VALLEY_WIDTH and g < VALLEY_MAX_GRADE:
            fp = float(np.clip(10.0 + 0.6 * width * math.sqrt(0.01 / g), 10.0, 48.0))
            row["valley"] = {"floodplain_width": round(fp), "floodplain_above_water": 1,
                             "terraces": [{"rise": 5, "tread": round(fp * 0.6)}, {"rise": 5, "tread": round(fp * 0.4)}],
                             "riser_slope": round(max(bank, 0.8), 2), "wall_slope": 0.6}
    row["width"] = int(round(width))
    row["depth"] = round(depth, 1)
    row["incision"] = round(max(FREEBOARD, MAJOR_INCISION * math.sqrt(f)) if major_mouth_km2 else FREEBOARD, 1)
    return row


def at_chainage(reaches, c):
    for r in reaches:
        if c <= r["to_m"]:
            return r
    return reaches[-1]


def depth_profile(reaches, chain):
    """Centre depth per station, eased between reach midpoints so the bed has no steps."""
    mids = [(r["from_m"] + r["to_m"]) / 2.0 for r in reaches]
    vals = [r["depth"] for r in reaches]
    return np.interp(chain, mids, vals)


def finalize_course(ctx, row, reaches, chain, total):
    """Water surface and bed per station. The surface is let down below the lowest ground by the reach's
    incision, so the river has banks, but never below the next lake downstream (or the level the course
    ends in), and below any lake on the course only gradually from its edge, so no lake drains into its
    own outlet. Lake stations keep the lake's level."""
    st, surface = ctx["dense"][row["id"]]
    bodies = ctx["bodies"]
    water = [s[3] >= 0 and bodies[s[3]].get("kind") != "course" for s in st]
    target = np.interp(chain, [(r["from_m"] + r["to_m"]) / 2.0 for r in reaches], [r["incision"] for r in reaches])
    down = [surface[-1]] * len(st)          # level of the next lake downstream, or the end level
    nxt = surface[-1]
    for k in range(len(st) - 1, -1, -1):
        if water[k]:
            nxt = surface[k]
        down[k] = nxt
    level, run, shore, after_lake = [], math.inf, None, False
    for y, ch, wet, inc, dn in zip(surface, chain, water, target, down):
        if wet:
            i, after_lake = 0.0, True
        else:
            if after_lake:                      # the first dry station below a lake: the taper starts here
                shore, after_lake = ch, False
            i = min(inc, max(0.0, y - dn))
            if shore is not None:
                i = min(i, INCISION_TAPER * max(0.0, ch - shore))
        run = min(run, y - i)
        level.append(run)
    depth = depth_profile(reaches, chain)
    floor, run = [], math.inf
    for y, dpt in zip(level, depth):
        run = min(run, y - dpt)
        floor.append(run)
    pts = [(s[0], s[1], round(y, 2), round(f, 2)) for s, y, f in zip(st, level, floor)]
    poly = simplify_graded(pts)
    # reach chainages are measured on the dense course; rescale them to the simplified polyline
    ps = [0.0]
    for a, b in zip(poly, poly[1:]):
        ps.append(ps[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    k = ps[-1] / total if total else 1.0
    for r in reaches:
        r["from_m"], r["to_m"] = round(r["from_m"] * k), round(r["to_m"] * k)
    row["graded_polyline"] = [list(p) for p in poly]
    row["graded_polyline_fields"] = ["x", "z", "surface_y", "floor_y"]
    row["reaches"] = reaches
    dry = [r for r in reaches if not r["water_body"]] or reaches
    row["character"] = summarise(dry, row)


def summarise(reaches, row):
    w = [r["width"] for r in reaches]
    d = [r["depth"] for r in reaches]
    beds = {}
    for r in reaches:
        beds[r["bed"]] = beds.get(r["bed"], 0) + (r["to_m"] - r["from_m"])
    tot = sum(beds.values()) or 1
    return {"width": [min(w), max(w)], "depth": [min(d), max(d)],
            "bank_slope": [min(r["bank_slope"] for r in reaches), max(r["bank_slope"] for r in reaches)],
            "catchment_km2": [reaches[0]["catchment_km2"], reaches[-1]["catchment_km2"]],
            "bed_share_pct": {k: round(100.0 * v / tot) for k, v in sorted(beds.items())}}


def plan(args):
    world_path = Path(args.world)
    world = T.load_world(world_path)
    base_path, base_sha = base_heightmap(world, world_path, args.source_root, args.heightmap)
    heights = T.read_heights(base_path, world).astype(np.float32)
    sea = T.sea_level(world)
    lm_doc = json.loads(Path(args.landmarks).read_text(encoding="utf-8"))
    landmarks = lm_doc["landmarks"]
    ymin, penalty, open_sea = coarse_grids(heights, sea)
    lakes, levels, ids = water_bodies(landmarks, ymin)
    lake_levels = levels.copy()
    ctx = {"heights": heights, "sea": sea, "ymin": ymin, "penalty": penalty, "open_sea": open_sea,
           "bodies": lakes, "levels": levels, "ids": ids, "cap": args.cap, "max_gouge": args.max_gouge,
           "dense": {}}
    for lk in lakes:
        lk["kind"] = "lake"
    rivers = rivers_from_landmarks(landmarks, lakes, open_sea)
    by_id = {lk["id"]: lk for lk in lakes}
    courses, lake_rows = [], []

    def add_course(cid, river, source, kind, result, graded):
        chain = result.pop("_chain_cut", None)
        row = {"id": cid, "river": river, "source": source, "kind": kind, **result}
        if graded:
            st, surface = graded
            ctx["dense"][cid] = (st, surface)
            stamp_course(ctx, cid, st, surface, chain)
            ctx["bodies"][-1]["ends_in"] = result.get("ends_in")
        courses.append(row)
        print("%-44s %-6s cut %-5s -> %-26s %s" % (cid, "VALID" if result["valid"] else "-",
                                                  result.get("min_worst_cut"), result.get("ends_in"),
                                                  result["verdict"]), flush=True)
        return chain

    # lakes, lowest first: a higher lake may drain into a lower one that already has a real outflow
    for lk in sorted(lakes, key=lambda l: l["level"]):
        cells = [(int(x), int(z)) for z, x in zip(*np.nonzero(lk["mask"]))]
        result, graded = run_course(ctx, cells, lk["level"], own_body=lk)
        chain = add_course(lk["id"] + "_outflow", None, {"kind": "lake_outflow", "lake": lk["id"], "level_y": lk["level"]},
                           "outflow", result, graded)
        lk["chain_cut"] = chain if result["valid"] else None
        lk["ends_in"] = result.get("ends_in")
        lake_rows.append({
            "id": lk["id"], "level_y": lk["level"], "spill_y": lk["spill"],
            "freeboard": round(lk["spill"] - lk["level"], 1) if lk["spill"] is not None else None,
            "outflow": "real" if result["valid"] else "artificial_pit",
            "min_worst_cut": result["min_worst_cut"], "ends_in": result.get("ends_in"),
            "course": lk["id"] + "_outflow",
        })

    # inland river ends, lowest first, so a higher source can join a lower course
    inland = [(rv, e) for rv in rivers for e in rv["ends"] if e["at"] == "inland"]
    inland.sort(key=lambda p: float(ymin[p[1]["z"] // FACTOR, p[1]["x"] // FACTOR]))
    for rv, e in inland:
        x, z = e["x"] // FACTOR, e["z"] // FACTOR
        if levels[z, x] == levels[z, x]:
            e["note"] = "on %s, which already drains it" % ctx["bodies"][int(ids[z, x])]["id"]
            continue
        level = float(ymin[z, x])
        cid = "%s_from_%s" % (rv["id"], e["end"])
        result, graded = run_course(ctx, [(x, z)], level)
        add_course(cid, rv["id"], {"kind": "inland_end", "end": e["end"], "x": e["x"], "z": e["z"],
                                   "ground_y": round(level, 1)}, rv["kind"], result, graded)
        e["course"] = cid

    def cuttable():
        return [c["id"] for c in courses if c.get("valid") and not c.get("canal") and c["id"] in ctx["dense"]]

    # the major river: the system with the largest catchment, traced from the head of its longest descending path
    dr = drainage_for(ctx, cuttable())
    systems = coastal_systems(ctx, dr)
    # for the three largest systems: the graded bodies at the mouth (the course reaching the sea there and
    # the lake it leaves), and the farthest ground that falls to them without a rise
    for s in systems[:3]:
        mz, mx = s["_cell"]
        near = [c for c in courses if c.get("valid") and c.get("ends_in") == "open_sea"
                and math.hypot(c["end_at"]["x"] - mx * FACTOR, c["end_at"]["z"] - mz * FACTOR) <= 300]
        s["_bodies"] = []
        for c in near:
            s["_bodies"].append(c["id"])
            if (c.get("source") or {}).get("lake"):
                s["_bodies"].append(c["source"]["lake"])
        starts = [(int(z), int(x)) for b in ctx["bodies"] if b["id"] in s["_bodies"]
                  for z, x in zip(*np.nonzero(b["mask"]))] or [s["_cell"]]
        (hz, hx), far = farthest_descending_source(ctx, starts)
        s["longest_descending_path_blocks"] = round(far)
        s["head"] = {"x": int(hx) * FACTOR, "z": int(hz) * FACTOR, "ground_y": round(float(ymin[hz, hx]), 1)}
        s["_head_cell"] = (int(hz), int(hx))
        s["path_basis"] = "farthest ground falling without a rise to %s" % (", ".join(s["_bodies"]) or "the mouth")
    for s in systems[3:]:
        s["longest_descending_path_blocks"] = None
        s["head"] = None
    top = systems[0]
    ranks = {k: sorted(range(min(3, len(systems))), key=lambda i: -(systems[i][k] or 0)).index(0)
             for k in ("catchment_km2", "longest_descending_path_blocks", "tributaries")}
    hz, hx = top["_head_cell"]
    trunk_id = "major_river_trunk"
    major_ids = []
    result, graded = run_course(ctx, [(hx, hz)], float(ymin[hz, hx]), only=top["_bodies"] or None)
    # the trunk starts where its path first runs between valley walls, not at the path's far end on an open
    # hillside: the flat catchment threshold used before removed a creek from a glacial trough floor
    head_rule = {"rule": "valley_walls", "wall_rise_blocks": WALL_RISE, "wall_reach_blocks": WALL_REACH,
                 "consecutive_stations": WALL_RUN, "station_spacing_blocks": WALL_STEP, "path_head": dict(top["head"])}
    if graded:
        st_p, surf_p = graded
        i_head, d_head, _ = valley_head(ctx["heights"], st_p, surf_p)
        head_rule["moved_blocks_along_path"] = d_head
        if i_head:
            # keep the graded course below the head as it was routed from the path head: routing again from the
            # new head takes another grid line and moves the whole lower valley sideways
            st_t, surf_t = st_p[i_head:], surf_p[i_head:]
            hx, hz = int(st_t[0][0] // FACTOR), int(st_t[0][1] // FACTOR)
            beds_t = [max(b[2], ctx["sea"]) for b in st_t]
            worst_t, at_t = R.worst_cut(beds_t)
            length_t = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(st_t, st_t[1:]))
            result["routed"].update({
                "length_blocks": round(length_t), "surface_start_y": round(surf_t[0], 1),
                "total_drop": round(surf_t[0] - surf_t[-1], 1), "worst_cut": round(worst_t, 1),
                "worst_cut_at": station_ref(st_t, at_t),
                "stations_needing_cut_pct": round(100.0 * sum(1 for b, y in zip(beds_t, surf_t) if b > y + 0.5) / len(st_t), 1)})
            graded = (st_t, surf_t)
            # the hillside above still drains to the head overland: count it when sizing, but cut no channel there
            ctx["dense"]["_trunk_upper"] = (st_p[:i_head + 1], surf_p[:i_head + 1])
            # the river below the head keeps the reaches it has as part of the whole path
            ctx["dense"]["_trunk_full"] = (st_p, surf_p)
            ctx["trunk_head_chain"] = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(st_p[:i_head], st_p[1:i_head + 1]))
    top["head"] = {"x": hx * FACTOR, "z": hz * FACTOR, "ground_y": round(float(ymin[hz, hx]), 1)}
    print("major river head:", json.dumps(head_rule), flush=True)
    add_course(trunk_id, "major_river", {"kind": "system_head", "x": hx * FACTOR, "z": hz * FACTOR,
                                         "ground_y": round(float(ymin[hz, hx]), 1)}, "major", result, graded)
    cur = trunk_id if result["valid"] else None
    by_course = {c["id"]: c for c in courses}
    while cur and cur in by_course and by_course[cur].get("valid"):
        major_ids.append(cur)
        nxt = by_course[cur].get("ends_in")
        if nxt == "open_sea" or nxt is None:
            break
        cur = nxt if nxt in by_course else nxt + "_outflow"
    major = {
        "selection": "the coastal system with the largest catchment; its trunk follows the system's longest "
                     "descending flow path to the sea, starting where that path first runs between valley walls",
        "head_rule": head_rule,
        "systems_ranked": [{k: v for k, v in s.items() if not k.startswith("_")} for s in systems[:5]],
        "chosen_rank_by": {k: v + 1 for k, v in ranks.items()},
        "metrics_agree": all(v == 0 for v in ranks.values()),
        "courses": major_ids,
    }
    print("major river:", json.dumps({k: v for k, v in major.items() if k != "systems_ranked"}), flush=True)

    # size every cut course from its catchment, with the trunk burned in too (and the path above its head)
    dr = drainage_for(ctx, cuttable() + (["_trunk_upper"] if "_trunk_upper" in ctx["dense"] else []))
    mouth_km2 = max(float(dr["km2"][top["_cell"]]), top["catchment_km2"])
    for c in courses:
        if c["id"] not in ctx["dense"]:
            continue
        is_major = c["id"] in major_ids
        if is_major:
            c["kind"] = "major"
        reaches, chain, total = characterise(ctx, c["id"], dr["km2"], is_major)
        if c["id"] == trunk_id and "_trunk_full" in ctx["dense"]:
            full, _, _ = characterise(ctx, "_trunk_full", dr["km2"], True)
            d0 = ctx["trunk_head_chain"]
            reaches = []
            for r in full:
                if r["to_m"] <= d0:
                    continue
                r = dict(r, from_m=max(0, round(r["from_m"] - d0)), to_m=round(r["to_m"] - d0))
                reaches.append(r)
        finalize_course(ctx, c, reaches, chain, total)
    major["mouth_catchment_km2"] = round(mouth_km2, 2)
    # the same rule, surveyed (not applied) on every other course whose head is not a lake
    survey = []
    for c in courses:
        if c["id"] == trunk_id or (c.get("source") or {}).get("kind") == "lake_outflow" or c["id"] not in ctx["dense"]:
            continue
        st_c, surf_c = ctx["dense"][c["id"]]
        i_c, d_c, rows_c = valley_head(ctx["heights"], st_c, surf_c)
        survey.append({"course": c["id"], "source_kind": (c.get("source") or {}).get("kind"),
                       "walled_from_start": bool(rows_c and all(r[3] for r in rows_c[:WALL_RUN])),
                       "rule_would_move_head_blocks": d_c, "walled_samples": sum(1 for r in rows_c if r[3]), "samples": len(rows_c)})
    major["head_rule_survey_other_courses"] = survey

    for rv in rivers:
        rv["courses"] = rv.get("graded_courses") or ([e["course"] for e in rv["ends"] if e.get("course")] +
                                                     [lake_id + "_outflow" for lake_id in rv["lakes_at_ends"]])
        rv["along_carve"] = along_channel(ctx, rv, by_id, lake_levels)
        rv.pop("_axis", None)
        for row in (rv["along_carve"] or {}).get("directions", []):
            print("  along carve %-28s %-34s -> %-30s %s" % (rv["id"], row["from"], row["to"], row["verdict"]))
    payload = {
        "schema": SCHEMA,
        "status": "derived",
        "computed_from_sha256": base_sha,
        "generated": datetime.date.today().isoformat(),
        "generator": "tools/grade_rivers.py plan",
        "rule": "a bed never rises in the direction of flow; the surface at each station is the lowest ground "
                "met so far, never below sea level; cut = ground above that surface",
        "parameters": {"grid_blocks": FACTOR, "max_gouge": args.max_gouge, "slack": SLACK, "cap": args.cap,
                       "bed_radius": BED_RADIUS, "near_lake": NEAR_LAKE, "near_sea": NEAR_SEA,
                       "destination_radius": DEST_RADIUS, "corridor_half_width": CORRIDOR,
                       "canal_pct": CANAL_PCT, "sea_level": sea, "reach_blocks": REACH,
                       "grade_window_blocks": GRADE_WINDOW, "tributary_km2": TRIBUTARY_KM2, "valley_head": {"wall_rise": WALL_RISE, "wall_reach": WALL_REACH, "run": WALL_RUN, "step": WALL_STEP},
                       "character": CHARACTER_RULES},
        "lakes": lake_rows,
        "rivers": rivers,
        "major_river": major,
        "courses": courses,
        "cut": None,
    }
    T.write_json(args.out, payload)
    print("wrote", args.out)
    return 0


# ------------------------------------------------------------------- cut

def height_to_sample_floor(y, world):
    imp = world["import"]
    full = float((1 << ((world.get("heightmap") or {}).get("bit_depth") or 16)) - 1)
    t = (np.asarray(y, np.float64) - float(imp["low_out"])) / (float(imp["high_out"]) - float(imp["low_out"]))
    frac = float(imp["low_in"]) + t * (float(imp["high_in"]) - float(imp["low_in"]))
    return np.clip(np.floor(frac * full), 0, full)


def densify(polyline):
    out = []
    for (x0, z0, s0, f0), (x1, z1, s1, f1) in zip(polyline, polyline[1:]):
        k = max(1, int(math.ceil(math.hypot(x1 - x0, z1 - z0))))
        for s in range(k):
            t = s / k
            out.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, s0 + (s1 - s0) * t, f0 + (f1 - f0) * t))
    out.append(tuple(polyline[-1][:4]))
    return out


def densify_chained(polyline):
    pts = densify(polyline)
    chain = [0.0]
    for a, b in zip(pts, pts[1:]):
        chain.append(chain[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return pts, chain


def cross_section(reach, surface, floor):
    """Lateral profile of a reach as (knot distances, knot heights, slope beyond the last knot, half width).
    Inside the half width the bed is a parabola: floor at the centre, one block under the water at the edge."""
    hw = reach["width"] / 2.0
    s = reach["bank_slope"]
    edge = surface - 1.0
    ks, ys = [hw], [edge]
    wall = s
    v = reach.get("valley")
    if v:
        fp = surface + v["floodplain_above_water"]
        ks.append(ks[-1] + (fp - edge) / s)
        ys.append(fp)
        ks.append(ks[-1] + v["floodplain_width"])
        ys.append(fp)
        for t in v["terraces"]:
            ks.append(ks[-1] + t["rise"] / v["riser_slope"])
            ys.append(ys[-1] + t["rise"])
            ks.append(ks[-1] + t["tread"])
            ys.append(ys[-1])
        wall = v["wall_slope"]
    return ks, ys, wall, hw


def lateral(d, surface, floor, reach):
    ks, ys, wall, hw = cross_section(reach, surface, floor)
    inner = floor + (surface - 1.0 - floor) * np.minimum(d / hw, 1.0) ** 2
    outer = np.interp(d, ks, ys)
    outer = np.where(d > ks[-1], ys[-1] + wall * (d - ks[-1]), outer)
    return np.where(d <= hw, np.minimum(inner, surface - 1.0), outer)


def cut(args):
    world_path = Path(args.world)
    world = T.load_world(world_path)
    src, base_sha = base_heightmap(world, world_path, args.source_root, args.heightmap)
    doc = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if doc.get("computed_from_sha256") != base_sha:
        raise SystemExit("plan was computed from %s but the heightmap is %s; rerun plan"
                         % (doc.get("computed_from_sha256"), base_sha))
    samples = np.array(Image.open(src))
    if samples.dtype != np.uint16:
        samples = samples.astype(np.uint16)
    n = samples.shape[0]
    out = samples.copy()
    lowered = np.zeros(samples.shape, bool)
    skipped = []
    top = float(world["import"]["high_out"])
    imp = world["import"]
    per_sample = (float(imp["high_out"]) - float(imp["low_out"])) / \
        ((float(imp["high_in"]) - float(imp["low_in"])) * float((1 << ((world.get("heightmap") or {}).get("bit_depth") or 16)) - 1))
    cost = {}
    for c in doc["courses"]:
        if not c.get("valid") or not c.get("graded_polyline"):
            continue
        if (c.get("canal") and not args.include_canals) or c["id"] in (args.exclude or []):
            skipped.append(c["id"])
            continue
        own = cost.setdefault(c["id"], {"volume": 0.0, "deepest": 0.0, "widest_half": 0.0})
        pts, chain = densify_chained(c["graded_polyline"])
        for (x, z, surface, floor), ch in zip(pts, chain):
            reach = at_chainage(c["reaches"], ch)
            if reach["water_body"]:
                continue
            ks, ys, wall, hw = cross_section(reach, surface, floor)
            limit = int(math.ceil(ks[-1] + max(0.0, top - ys[-1]) / wall)) + 2
            size = min(limit, int(ks[-1]) + 8)
            # widen the window until the profile meets natural ground inside it, so no step is left at its edge
            while True:
                x0, x1 = max(0, int(x) - size), min(n, int(x) + size + 2)
                z0, z1 = max(0, int(z) - size), min(n, int(z) + size + 2)
                zz, xx = np.mgrid[z0:z1, x0:x1]
                d = np.hypot(xx - x, zz - z)
                ts = height_to_sample_floor(lateral(d, surface, floor, reach), world).astype(np.uint16)
                win = out[z0:z1, x0:x1]
                lower = ts < win
                if size >= limit or not (lower & (d >= size - 1)).any():
                    break
                size = min(limit, size * 2)
            if lower.any():
                delta = (samples[z0:z1, x0:x1][lower].astype(np.int64) - ts[lower].astype(np.int64)) * per_sample
                own["volume"] += float((win[lower].astype(np.int64) - ts[lower].astype(np.int64)).sum()) * per_sample
                own["deepest"] = max(own["deepest"], float(delta.max()))
                own["widest_half"] = max(own["widest_half"], float(d[lower].max()))
                win[lower] = ts[lower]
                lowered[z0:z1, x0:x1] |= lower
    dest = (Path(args.out_dir) if args.out_dir else Path(src).parent) / args.out_name
    if dest.resolve() == Path(src).resolve():
        raise SystemExit("refusing to overwrite the source heightmap")
    if dest.exists() and not args.replace:
        raise SystemExit("%s exists; pass --replace to regenerate it" % dest)
    Image.fromarray(out).save(dest)
    h = hashlib.sha256(dest.read_bytes()).hexdigest()
    written = np.array(Image.open(dest))
    if not np.array_equal(written, out):
        raise SystemExit("written heightmap does not read back identically")
    removed = (T.sample_to_height(samples[lowered], world) - T.sample_to_height(written[lowered], world))
    # re-measure every graded course on the written file: the bed must reach the planned floor at the
    # centreline, and neither the floor nor that lowest ground may ever rise
    checks = []
    for c in doc["courses"]:
        if not c.get("valid") or not c.get("graded_polyline") or c["id"] in skipped:
            continue
        pts, chain = densify_chained(c["graded_polyline"])
        above, floors, thalweg = 0.0, [], []
        for (x, z, _s, floor), ch in zip(pts, chain):
            if at_chainage(c["reaches"], ch)["water_body"]:
                continue
            xi, zi = int(round(x)), int(round(z))
            low = float(T.sample_to_height(written[max(0, zi - 1):zi + 2, max(0, xi - 1):xi + 2], world).min())
            above = max(above, low - floor)
            floors.append(floor)
            thalweg.append(max(low, floor - 0.5))     # deeper natural ground is not a rise
        rise, _ = R.worst_cut(floors)
        trise, _ = R.worst_cut(thalweg)
        checks.append({"course": c["id"], "thalweg_above_floor_max": round(above, 3),
                       "floor_rise_max": round(rise, 3), "thalweg_rise_max": round(trise, 3)})
    doc["cut"] = {
        "generated": datetime.date.today().isoformat(),
        "generator": "tools/grade_rivers.py cut",
        "from_heightmap": {"path": Path(src).name, "sha256": base_sha},
        "output": {"path": dest.name, "sha256": h},
        "courses_cut": [ck["course"] for ck in checks],
        "courses_not_cut": skipped,
        "cost_by_course": {k: {"volume_blocks": int(round(v["volume"])), "deepest_cut_blocks": round(v["deepest"], 1),
                               "widest_cut_half_width_blocks": round(v["widest_half"])} for k, v in cost.items()},
        "cost_basis": "volume is what each course removed beyond the courses cut before it; deepest is the most any "
                      "column it touched was lowered from the source heightmap; widest is the farthest column it "
                      "lowered from its centreline",
        "columns_lowered": int(lowered.sum()),
        "lowered_blocks": {"max": round(float(removed.max()), 2) if removed.size else 0,
                           "mean": round(float(removed.mean()), 2) if removed.size else 0,
                           "volume": int(round(float(removed.sum())))},
        "check": {"method": "on the written file, at every block of each course outside lakes: the lowest ground "
                            "within one block of the centreline against the planned floor; the largest rise of the "
                            "planned floor; and the largest rise of that lowest ground (clamped half a block under "
                            "the floor)",
                  "courses": checks},
    }
    T.write_json(args.plan, doc)
    print("wrote %s  sha256 %s  columns lowered %d  volume %d" % (dest, h, lowered.sum(), doc["cut"]["lowered_blocks"]["volume"]))
    for ck in checks:
        print("  %-40s thalweg above floor %.3f  floor rise %.3f  thalweg rise %.3f"
              % (ck["course"], ck["thalweg_above_floor_max"], ck["floor_rise_max"], ck["thalweg_rise_max"]))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "cut"):
        s = sub.add_parser(name)
        s.add_argument("--world", default=str(T.DEFAULT_WORLD))
        s.add_argument("--source-root", default=None)
        s.add_argument("--heightmap", default=None)
        if name == "plan":
            s.add_argument("--landmarks", default=str(T.ROOT / "data" / "landmarks.json"))
            s.add_argument("--out", default=str(T.ROOT / "data" / "rivers.json"))
            s.add_argument("--max-gouge", type=float, default=MAX_GOUGE)
            s.add_argument("--cap", type=float, default=64.0,
                           help="deepest cut the min-cut search will consider, for reporting")
        else:
            s.add_argument("--plan", default=str(T.ROOT / "data" / "rivers.json"))
            s.add_argument("--out-name", default="land_8k_16_eroded_rivers.png")
            s.add_argument("--replace", action="store_true")
            s.add_argument("--out-dir", default=None, help="write the cut heightmap here instead of beside the source")
            s.add_argument("--include-canals", action="store_true",
                           help="also cut courses the plan marked as canals")
            s.add_argument("--exclude", nargs="*", metavar="COURSE", help="course ids not to cut")
    a = p.parse_args(argv)
    return plan(a) if a.cmd == "plan" else cut(a)


if __name__ == "__main__":
    raise SystemExit(main())
