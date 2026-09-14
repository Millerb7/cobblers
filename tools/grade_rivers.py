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
CHANNEL = {                # cut geometry, by river kind
    "river": {"half_width": 4, "depth": 3, "bank_slope": 1.0},
    "creek": {"half_width": 2, "depth": 2, "bank_slope": 1.0},
    "outflow": {"half_width": 3, "depth": 2, "bank_slope": 1.0},
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
    """Each carved river, with each end classified: at a lake, at the sea, or inland (a possible source)."""
    rivers = []
    for lm in landmarks:
        if lm.get("kind") != "river":
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
                if other is lm or other.get("kind") != "river":
                    continue
                oax = next((a for a in other.get("axes") or [] if a.get("id") == "channel"), {})
                if polyline_distance(oax.get("polyline") or [], e["x"], e["z"]) <= CORRIDOR:
                    e["at"], e["confluence_with"] = "confluence", other["id"]
                    break
        rivers.append({
            "id": lm["id"], "name": lm.get("name"),
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


def run_course(ctx, sources, start_level, own_body=None):
    """Minimum worst cut to the nearest sea, then, within the gouge limit, the graded course.

    Earlier valid bodies (lakes with a real outflow, rivers already graded) are goals too: a course
    that reaches one at or below its own surface joins it and inherits its downstream cut.
    """
    ymin, levels, ids, bodies = ctx["ymin"], ctx["levels"], ctx["ids"], ctx["bodies"]

    def goals(limit):
        goal = ctx["open_sea"].copy()
        goal_cut = np.full(ymin.shape, np.nan)
        for b in bodies:
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


def plan(args):
    heights, world = T.load(args.world, args.source_root, args.heightmap)
    sea = T.sea_level(world)
    lm_doc = json.loads(Path(args.landmarks).read_text(encoding="utf-8"))
    landmarks = lm_doc["landmarks"]
    ymin, penalty, open_sea = coarse_grids(heights, sea)
    lakes, levels, ids = water_bodies(landmarks, ymin)
    lake_levels = levels.copy()
    ctx = {"heights": heights, "sea": sea, "ymin": ymin, "penalty": penalty, "open_sea": open_sea,
           "bodies": lakes, "levels": levels, "ids": ids, "cap": args.cap, "max_gouge": args.max_gouge}
    rivers = rivers_from_landmarks(landmarks, lakes, open_sea)
    by_id = {lk["id"]: lk for lk in lakes}
    courses, lake_rows = [], []

    def add_course(cid, river, source, channel, result, graded):
        chain = result.pop("_chain_cut", None)
        row = {"id": cid, "river": river, "source": source, "channel": CHANNEL[channel], **result}
        if graded:
            st, surface = graded
            depth = CHANNEL[channel]["depth"]
            pts = [(s[0], s[1], round(y, 2), round(y - depth, 2)) for s, y in zip(st, surface)]
            row["graded_polyline"] = [list(p) for p in simplify_graded(pts)]
            row["graded_polyline_fields"] = ["x", "z", "surface_y", "floor_y"]
            stamp_course(ctx, cid, st, surface, chain)
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

    for rv in rivers:
        rv["courses"] = [e["course"] for e in rv["ends"] if e.get("course")] + \
            [lake_id + "_outflow" for lake_id in rv["lakes_at_ends"]]
        rv["along_carve"] = along_channel(ctx, rv, by_id, lake_levels)
        rv.pop("_axis", None)
        for row in (rv["along_carve"] or {}).get("directions", []):
            print("  along carve %-28s %-34s -> %-30s %s" % (rv["id"], row["from"], row["to"], row["verdict"]))
    payload = {
        "schema": SCHEMA,
        "status": "derived",
        "computed_from_sha256": (world.get("heightmap") or {}).get("sha256"),
        "generated": datetime.date.today().isoformat(),
        "generator": "tools/grade_rivers.py plan",
        "rule": "a bed never rises in the direction of flow; the surface at each station is the lowest ground "
                "met so far, never below sea level; cut = ground above that surface",
        "parameters": {"grid_blocks": FACTOR, "max_gouge": args.max_gouge, "slack": SLACK, "cap": args.cap,
                       "bed_radius": BED_RADIUS, "near_lake": NEAR_LAKE, "near_sea": NEAR_SEA,
                       "destination_radius": DEST_RADIUS, "corridor_half_width": CORRIDOR,
                       "canal_pct": CANAL_PCT, "sea_level": sea, "channels": CHANNEL},
        "lakes": lake_rows,
        "rivers": rivers,
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
    out.append(tuple(polyline[-1]))
    return out


def cut(args):
    world_path = Path(args.world)
    world = T.load_world(world_path)
    src = T.resolve_heightmap(world, world_path, args.source_root) if not args.heightmap \
        else T.verify_file(args.heightmap, world, world_path)
    doc = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    sha = (world.get("heightmap") or {}).get("sha256")
    if doc.get("computed_from_sha256") != sha:
        raise SystemExit("plan was computed from %s but the heightmap is %s; rerun plan"
                         % (doc.get("computed_from_sha256"), sha))
    samples = np.array(Image.open(src))
    if samples.dtype != np.uint16:
        samples = samples.astype(np.uint16)
    n = samples.shape[0]
    out = samples.copy()
    lowered = np.zeros(samples.shape, bool)
    skipped = []
    for c in doc["courses"]:
        if not c.get("valid") or not c.get("graded_polyline"):
            continue
        if (c.get("canal") and not args.include_canals) or c["id"] in (args.exclude or []):
            skipped.append(c["id"])
            continue
        ch = c["channel"]
        hw, slope = ch["half_width"], ch["bank_slope"]
        top = float(world["import"]["high_out"])
        limit = hw + (int(math.ceil((top - min(p[3] for p in c["graded_polyline"])) / slope)) + 2 if slope > 0 else 0)
        for x, z, _surface, floor in densify(c["graded_polyline"]):
            # widen the window until the bank meets natural ground inside it, so no step is left at its edge
            reach = min(limit, hw + 16)
            while True:
                x0, x1 = max(0, int(x) - reach), min(n, int(x) + reach + 2)
                z0, z1 = max(0, int(z) - reach), min(n, int(z) + reach + 2)
                zz, xx = np.mgrid[z0:z1, x0:x1]
                d = np.hypot(xx - x, zz - z)
                target = floor + slope * np.maximum(0.0, d - hw)
                ts = height_to_sample_floor(target, world).astype(np.uint16)
                win = out[z0:z1, x0:x1]
                lower = ts < win
                if reach >= limit or not (lower & (d >= reach - 1)).any():
                    break
                reach = min(limit, reach * 2)
            if lower.any():
                win[lower] = ts[lower]
                lowered[z0:z1, x0:x1] |= lower
    dest = src.with_name(args.out_name)
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
    # re-measure every graded course on the written file: the bed must sit at or below the planned floor,
    # and the planned floor must never rise
    checks = []
    for c in doc["courses"]:
        if not c.get("valid") or not c.get("graded_polyline") or c["id"] in skipped:
            continue
        r = max(1, c["channel"]["half_width"] - 1)
        above, floors, thalweg = 0.0, [], []
        for x, z, _s, floor in densify(c["graded_polyline"]):
            xi, zi = int(round(x)), int(round(z))
            low = float(T.sample_to_height(written[max(0, zi - r):zi + r + 1, max(0, xi - r):xi + r + 1], world).min())
            above = max(above, low - floor)
            floors.append(floor)
            thalweg.append(max(low, floor - 0.5))     # deeper natural ground (a lake bed) is not a rise
        rise, _ = R.worst_cut(floors)
        trise, _ = R.worst_cut(thalweg)
        checks.append({"course": c["id"], "thalweg_above_floor_max": round(above, 3),
                       "floor_rise_max": round(rise, 3), "thalweg_rise_max": round(trise, 3)})
    doc["cut"] = {
        "generated": datetime.date.today().isoformat(),
        "generator": "tools/grade_rivers.py cut",
        "from_heightmap": {"path": Path(src).name, "sha256": sha},
        "output": {"path": dest.name, "sha256": h},
        "courses_cut": [ck["course"] for ck in checks],
        "courses_not_cut": skipped,
        "columns_lowered": int(lowered.sum()),
        "lowered_blocks": {"max": round(float(removed.max()), 2) if removed.size else 0,
                           "mean": round(float(removed.mean()), 2) if removed.size else 0},
        "check": {"method": "on the written file, at every block of each course: the lowest ground across the "
                            "bed (half width - 1) against the planned floor; the largest rise of the planned floor; "
                            "and the largest rise of that lowest ground (clamped half a block under the floor, "
                            "so a lake bed on the course does not count as a rise)",
                  "courses": checks},
    }
    T.write_json(args.plan, doc)
    print("wrote %s  sha256 %s  columns lowered %d" % (dest, h, lowered.sum()))
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
            s.add_argument("--include-canals", action="store_true",
                           help="also cut courses the plan marked as canals")
            s.add_argument("--exclude", nargs="*", metavar="COURSE", help="course ids not to cut")
    a = p.parse_args(argv)
    return plan(a) if a.cmd == "plan" else cut(a)


if __name__ == "__main__":
    raise SystemExit(main())
