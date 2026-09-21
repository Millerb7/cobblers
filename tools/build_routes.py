#!/usr/bin/env python
"""Derive the critical-path routes from terrain: data/routes.json and each destination town's approach length.

Committed form of the 2026-09-15 one-off orchestration around tools/route_path.py (recorded in routes.json
derivation_record). What it does, unchanged:

  - full-resolution eight-connected A*; cost = horizontal length x (25 on authored water, else 1) + 8 x |climb|
  - edges steeper than 40 degrees are refused; columns steeper than 40 degrees or at/below sea level are impassable
  - authored mandatory waypoints (routes.json routing.mandatory_waypoints) are visited in order
  - elevation, grade, water crossings and sub-region membership sampled along the dense path
  - an 8-block corridor raster merged into exact rectangles for coordinate-box spawns

What changed, and why:

  - Victory Road's control points come from routes.json routing.mandatory_waypoints (the measured Rift entry, fork and
    apex). The one-off read them from the previous output's simplified polyline, so every rerun would have pinned the
    route to its own last path.
  - Corridor widths and waypoints are read from data, not constants in the script.
  - Dense paths are cached (build/routes/paths.json) so --geography-only can recompute sub-region membership and holes
    after data/regions.json changes without re-running A*.

  python tools/build_routes.py --source-root C:/Users/wnd/Documents              # write data/routes.json and towns
  python tools/build_routes.py --source-root ... --geography-only                # reuse cached paths
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
import route_path as RP

ROOT = T.ROOT
CACHE = ROOT / "build" / "routes" / "paths.json"


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def point_in_poly(x, z, poly):
    inside = False
    j = len(poly) - 1
    for i, (xi, zi) in enumerate(poly):
        xj, zj = poly[j]
        if ((zi > z) != (zj > z)) and x < (xj - xi) * (z - zi) / (zj - zi) + xi:
            inside = not inside
        j = i
    return inside


def seg_dist(px, pz, a, b):
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    den = dx * dx + dz * dz
    t = 0 if not den else max(0, min(1, ((px - ax) * dx + (pz - az) * dz) / den))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))


class Router:
    def __init__(self, heights, sea, water_mask):
        self.h = heights
        self.H, self.W = heights.shape
        self.passable = (T.slope_degrees(heights) <= 40.0) & (heights > sea)
        self.water = water_mask

    def edge(self, start, goal):
        h, W, H, passable, water = self.h, self.W, self.H, self.passable, self.water
        sx, sz = start
        gx, gz = goal
        if not passable[sz, sx]:
            raise RuntimeError("start %s is not passable (slope over 40 degrees or at sea level)" % (start,))
        if not passable[gz, gx]:
            raise RuntimeError("goal %s is not passable (slope over 40 degrees or at sea level)" % (goal,))

        def heuristic(x, z):
            dx, dz = abs(x - gx), abs(z - gz)
            return (dx + dz) - (2 - math.sqrt(2)) * min(dx, dz)

        si, gi = sz * W + sx, gz * W + gx
        best = {si: 0.0}
        came = {}
        pq = [(heuristic(sx, sz), 0.0, si)]
        seen = set()
        while pq:
            _, cost, cur = heapq.heappop(pq)
            if cur in seen:
                continue
            seen.add(cur)
            if cur == gi:
                break
            cz, cx = divmod(cur, W)
            ch = float(h[cz, cx])
            for dx, dz in RP.NEIGHBOURS:
                nx, nz = cx + dx, cz + dz
                if nx < 0 or nz < 0 or nx >= W or nz >= H or not passable[nz, nx]:
                    continue
                ni = nz * W + nx
                if ni in seen:
                    continue
                run = math.sqrt(2.0) if dx and dz else 1.0
                climb = abs(float(h[nz, nx]) - ch)
                if math.degrees(math.atan2(climb, run)) > 40.0:
                    continue
                nc = cost + run * (25.0 if water[nz, nx] else 1.0) + 8.0 * climb
                if nc < best.get(ni, float("inf")):
                    best[ni] = nc
                    came[ni] = cur
                    heapq.heappush(pq, (nc + heuristic(nx, nz), nc, ni))
        if gi not in best:
            raise RuntimeError("no route %s -> %s" % (start, goal))
        path = []
        cur = gi
        while cur != si:
            z, x = divmod(cur, W)
            path.append((x, z))
            cur = came[cur]
        path.append(tuple(start))
        path.reverse()
        return path, best[gi]


def cumulative(path):
    vals = [0.0]
    for a, b in zip(path, path[1:]):
        vals.append(vals[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return vals


def boxes_from_mask(mask, prefix, W, H):
    h, w = mask.shape
    active, rects = {}, []
    for z in range(h):
        row = mask[z]
        runs = []
        x = 0
        while x < w:
            if not row[x]:
                x += 1
                continue
            a = x
            while x + 1 < w and row[x + 1]:
                x += 1
            runs.append((a, x))
            x += 1
        runs_set = set(runs)
        for run, (z0, z1) in list(active.items()):
            if run not in runs_set:
                rects.append((run[0], run[1], z0, z1))
                del active[run]
        for run in runs:
            active[run] = (active[run][0], z) if run in active else (z, z)
    for run, (z0, z1) in active.items():
        rects.append((run[0], run[1], z0, z1))
    rects.sort(key=lambda q: (q[2], q[0], q[3], q[1]))
    return [{"id": "%s_b%04d" % (prefix, i), "min_x": x0 * 8, "max_x": min(W - 1, (x1 + 1) * 8 - 1),
             "min_z": z0 * 8, "max_z": min(H - 1, (z1 + 1) * 8 - 1)} for i, (x0, x1, z0, z1) in enumerate(rects, 1)]


def corridor_mask(path, width, W, H):
    img = Image.new("1", (W // 8, H // 8), 0)
    draw = ImageDraw.Draw(img)
    pts = [(min(W // 8 - 1, max(0, x // 8)), min(H // 8 - 1, max(0, z // 8))) for x, z in path]
    draw.line(pts, fill=1, width=max(1, math.ceil(width / 8)), joint="curve")
    return np.asarray(img, dtype=bool)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--geography-only", action="store_true", help="reuse build/routes/paths.json; recompute membership")
    p.add_argument("--reroute", nargs="*", default=None, metavar="ROUTE_ID",
                   help="route only these legs again and reuse the cached paths for the rest (same heightmap required)")
    p.add_argument("--date", default=datetime.date.today().isoformat())
    p.add_argument("--out-dir", default=None, help="write routes.json, towns.json and the path cache here instead of data/ and build/")
    a = p.parse_args(argv)

    heights, world = T.load_from_args(a)
    hm_path = T.resolve_heightmap(world, Path(a.world), a.source_root) if not a.heightmap else Path(a.heightmap)
    sea = float(T.sea_level(world))
    H, W = heights.shape
    D = ROOT / "data"
    old = json.loads((D / "routes.json").read_text(encoding="utf-8"))
    regions = json.loads((D / "regions.json").read_text(encoding="utf-8"))
    rivers = json.loads((D / "rivers.json").read_text(encoding="utf-8"))
    landmarks = json.loads((D / "landmarks.json").read_text(encoding="utf-8"))
    towns = json.loads((D / "towns.json").read_text(encoding="utf-8"))
    waypoints = {k: [tuple(q) for q in v["points"]] for k, v in old["routing"]["mandatory_waypoints"].items()}
    endpoints = {k: v for k, v in (old["routing"].get("endpoints") or {}).items()}

    sub_defs, sub_display, sub_parent = [], {}, {}
    for s in regions["subregions"]:
        sub_defs.append((s["id"], s["measured"]["bounds"], s["polygons"]))
        sub_display[s["id"]] = s["display_name"]
        sub_parent[s["id"]] = s["parent"]

    def membership(x, z):
        return tuple(sorted(sid for sid, b, polys in sub_defs
                            if b["min_x"] <= x <= b["max_x"] and b["min_z"] <= z <= b["max_z"]
                            and any(point_in_poly(x, z, q) for q in polys)))

    lake_defs = [(lm["id"], lm.get("name", lm["id"]), lm["water_body"]["basin_polygons"])
                 for lm in landmarks["landmarks"] if (lm.get("water_body") or {}).get("basin_polygons")]
    river_defs = [(c["id"], c.get("river"), [(q[0], q[1]) for q in c["graded_polyline"]],
                   float(max(c.get("character", {}).get("width", [6])))) for c in rivers["courses"]]
    img = Image.new("1", (W, H), 0)
    draw = ImageDraw.Draw(img)
    for _, _, polys in lake_defs:
        for poly in polys:
            draw.polygon([(int(x), int(z)) for x, z in poly], fill=1)
    for _, _, pts, width in river_defs:
        draw.line([(int(x), int(z)) for x, z in pts], fill=1, width=max(1, int(round(width))), joint="curve")
    water_mask = np.asarray(img, dtype=bool) | (heights <= sea)
    del draw, img

    def water_features(x, z):
        out = []
        if float(heights[z, x]) <= sea:
            out.append(("open_sea", "open sea", "sea"))
        for lid, name, polys in lake_defs:
            if any(point_in_poly(x, z, q) for q in polys):
                out.append((lid, name, "lake"))
        for cid, parent, pts, width in river_defs:
            t = width / 2
            if any(min(u[0], v[0]) - t <= x <= max(u[0], v[0]) + t and min(u[1], v[1]) - t <= z <= max(u[1], v[1]) + t
                   and seg_dist(x, z, u, v) <= t for u, v in zip(pts, pts[1:])):
                out.append((cid, parent or cid, "river"))
        return out

    town_by = {t["id"]: t for t in towns["towns"]}
    old_by = {r["id"]: r for r in old["routes"]}
    out_dir = Path(a.out_dir) if a.out_dir else None
    cache_path = out_dir / "paths.json" if out_dir else CACHE
    if a.geography_only:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if cache["heightmap_sha256"] != world["heightmap"]["sha256"]:
            raise SystemExit("cached paths were routed on %s, not the canonical %s: route again"
                             % (cache["heightmap_sha256"][:8], world["heightmap"]["sha256"][:8]))
        paths = {k: [tuple(q) for q in v] for k, v in cache["paths"].items()}
    else:
        router = Router(heights, sea, water_mask)
        paths = {}
        if a.reroute:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            if cache["heightmap_sha256"] != world["heightmap"]["sha256"]:
                raise SystemExit("cached paths were routed on another heightmap: route every leg")
            paths = {k: [tuple(q) for q in v] for k, v in cache["paths"].items() if k not in a.reroute}
        for r in old["routes"]:
            rid = r["id"]
            if rid in paths:
                continue
            start = (town_by[r["from_town"]]["centre"]["x"], town_by[r["from_town"]]["centre"]["z"])
            goal = (town_by[r["to_town"]]["centre"]["x"], town_by[r["to_town"]]["centre"]["z"])
            # a town plan can put a road's end somewhere other than the town's centre: Victory Road leaves
            # Giovanni's town from the gate square, past the gym, not from the middle of town
            ends = endpoints.get(rid) or {}
            start = tuple(ends.get("start") or start)
            goal = tuple(ends.get("goal") or goal)
            pts = [start] + waypoints.get(rid, []) + [goal]
            print("route", rid, "via", waypoints.get(rid, []), flush=True)
            path = []
            for u, v in zip(pts, pts[1:]):
                q, _ = router.edge(u, v)
                path.extend(q[1:] if path else q)
            paths[rid] = path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"heightmap_sha256": world["heightmap"]["sha256"], "paths": paths}), encoding="utf-8")

    out_routes, all_holes, route_masks = [], [], {}
    for r in old["routes"]:
        rid = r["id"]
        path = paths[rid]
        start, goal = path[0], path[-1]
        cums = cumulative(path)
        ys = [float(heights[z, x]) for x, z in path]
        grades, exceed = [], []
        for i, (u, v) in enumerate(zip(path, path[1:])):
            run = math.hypot(v[0] - u[0], v[1] - u[1])
            g = math.degrees(math.atan2(abs(ys[i + 1] - ys[i]), run))
            grades.append(g)
            if g > 35:
                exceed.append({"from": {"x": u[0], "y": round(ys[i], 2), "z": u[1]}, "to": {"x": v[0], "y": round(ys[i + 1], 2), "z": v[1]},
                               "grade_degrees": round(g, 2), "at_distance_blocks": round(cums[i], 2)})
        members = [membership(x, z) for x, z in path]
        transitions, prev = [], None
        for i, m in enumerate(members):
            if m != prev:
                transitions.append({"at_distance_blocks": round(cums[i], 2), "at": {"x": path[i][0], "z": path[i][1]},
                                    "subregions": list(m), "from_subregions": list(prev or ())})
                prev = m
        holes, i = [], 0
        while i < len(path):
            if members[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(path) and not members[j + 1]:
                j += 1
            holes.append({"start": {"x": path[i][0], "z": path[i][1], "at_distance_blocks": round(cums[i], 2)},
                          "end": {"x": path[j][0], "z": path[j][1], "at_distance_blocks": round(cums[j], 2)},
                          "length_blocks": round(cums[j] - cums[i], 2), "dense_samples": j - i + 1})
            i = j + 1
        all_holes.extend({"route_id": rid, **x} for x in holes)
        subs = sorted({s for m in members for s in m})
        geo = {"regions": sorted({sub_parent[s] for s in subs}), "subregions": subs, "transitions": transitions,
               "unassigned_path_pct": round(100 * sum(x["length_blocks"] for x in holes) / cums[-1], 3) if cums[-1] else 0,
               "unassigned_intervals": holes}
        by_feature = {}
        for i, (x, z) in enumerate(path):
            for f in water_features(x, z):
                by_feature.setdefault(f, []).append(i)
        water = []
        for (fid, name, kind), idxs in by_feature.items():
            runs, s0, pv = [], idxs[0], idxs[0]
            for i in idxs[1:]:
                if i > pv + 1:
                    runs.append((s0, pv))
                    s0 = i
                pv = i
            runs.append((s0, pv))
            for u, v in runs:
                mid = (u + v) // 2
                water.append({"id": fid, "name": name, "kind": kind,
                              "start": {"x": path[u][0], "z": path[u][1], "at_distance_blocks": round(cums[u], 2)},
                              "end": {"x": path[v][0], "z": path[v][1], "at_distance_blocks": round(cums[v], 2)},
                              "at": {"x": path[mid][0], "y": round(float(heights[path[mid][1], path[mid][0]]), 2), "z": path[mid][1]},
                              "crossing_length_blocks": round(cums[v] - cums[u], 2)})
        water.sort(key=lambda w: w["start"]["at_distance_blocks"])
        notable = []
        for t in transitions[1:]:
            notable.append({"kind": "subregion_boundary", "at": {**t["at"], "y": round(float(heights[t["at"]["z"], t["at"]["x"]]), 2)},
                            "at_distance_blocks": t["at_distance_blocks"], "from": t["from_subregions"], "to": t["subregions"],
                            "name": " / ".join(sub_display.get(s, s) for s in t["subregions"]) if t["subregions"] else "unassigned regions.json gap"})
        for w in water:
            notable.append({"kind": "water_crossing", "water": w["id"], "name": w["name"], "at": w["at"],
                            "at_distance_blocks": w["start"]["at_distance_blocks"], "crossing_length_blocks": w["crossing_length_blocks"]})
        notable.sort(key=lambda n: n["at_distance_blocks"])
        width = r["corridor"]["width_blocks"]
        mask = corridor_mask(path, width, W, H)
        route_masks[rid] = mask
        boxes = boxes_from_mask(mask, "vr" if rid == "victory_road" else "r%02d" % r["order"], W, H)
        index = {q: i for i, q in enumerate(path)}
        poly = [{"x": q[0], "y": round(float(heights[q[1], q[0]]), 2), "z": q[1], "at_distance_blocks": round(cums[index[q]], 2),
                 "corridor_width_blocks": width} for q in RP.simplify(path)]
        barriers = []
        for b in r.get("barriers", []):
            src = b.get("source_coordinate") or {"x": b["at"]["x"], "z": b["at"]["z"]}
            q = min(path, key=lambda c: (c[0] - src["x"]) ** 2 + (c[1] - src["z"]) ** 2)
            barriers.append({**b, "at": {"x": q[0], "y": round(float(heights[q[1], q[0]]), 2), "z": q[1]}, "source_coordinate": src})
        straight = math.hypot(goal[0] - start[0], goal[1] - start[1])
        previous = r["distance"]["computed_walked_blocks"]
        out_routes.append({
            "id": rid, "order": r["order"], "display_name": r["display_name"], "status": "derived_candidate",
            "from_town": r["from_town"], "to_town": r["to_town"], "chapter": r["chapter"],
            "distance": {"computed_walked_blocks": round(cums[-1]), "computed_walked_blocks_exact": round(cums[-1], 2),
                         "straight_line_blocks": round(straight, 2), "detour_ratio": round(cums[-1] / straight, 3),
                         "previous_recorded_blocks": previous, "correction_blocks": round(cums[-1] - previous, 2),
                         "method": "full-resolution eight-connected A*; cost = horizontal length + 8 x absolute elevation change; mandatory waypoints from routing.mandatory_waypoints"},
            "party_level_band": r["party_level_band"],
            "corridor": {"derivation": "A* dense path simplified only for storage; y sampled from the canonical heightmap",
                         "width_meaning": "Total ambient-spawn influence corridor, not literal road width.",
                         "width_blocks": width, "polyline": poly},
            "elevation": {"min_y": round(min(ys), 2), "max_y": round(max(ys), 2),
                          "total_climb_blocks": round(sum(max(0, v - u) for u, v in zip(ys, ys[1:])), 2),
                          "total_descent_blocks": round(sum(max(0, u - v) for u, v in zip(ys, ys[1:])), 2),
                          "max_grade_degrees": round(max(grades), 2), "comfort_limit_degrees": 35, "router_hard_limit_degrees": 40,
                          "segments_above_comfort_limit": exceed,
                          "segments_above_router_limit": sum(1 for g in grades if g > 40 + 1e-6),
                          "walkability_verdict": "walkable under router hard limit" if max(grades) <= 40 + 1e-6 else "NOT WALKABLE"},
            "geography": geo, "notable_crossings": notable, "water_crossings": water, "barriers": barriers,
            "landmarks": r.get("landmarks", []),
            "spawn_scope": {"mechanism": "spawn_json_coordinate_boxes", "common_conditions": {"canSeeSky": True},
                            "coordinate_box_semantics": "inclusive X/Z bounds; compile with route biome tags",
                            "box_count": len(boxes),
                            "coverage": {"method": "8-block raster of every dense A* segment, converted to exact vertically merged rectangles",
                                         "sample_step_blocks": 8, "corridor_area_coverage_pct": 100.0,
                                         "box_area_outside_corridor_pct_of_corridor": 0.0, "centreline_coverage_pct": 100.0,
                                         "note": "Exact raster rectangles remove bend overspill; box count is the compilation cost."},
                            "boxes": boxes},
        })
        print("  %-30s %6.0f blocks (was %s), %d boxes, %d holes" % (rid, cums[-1], previous, len(boxes), len(holes)), flush=True)

    adj = []
    for u, v in zip(out_routes, out_routes[1:]):
        cells = int((route_masks[u["id"]] & route_masks[v["id"]]).sum())
        item = {"routes": [u["id"], v["id"]], "shared_town": u["to_town"], "overlap_area_blocks2": cells * 64,
                "overlap_pct_of_smaller_corridor": round(100 * cells / min(route_masks[u["id"]].sum(), route_masks[v["id"]].sum()), 2)}
        adj.append(item)
        u["spawn_scope"]["adjacent_route_overlaps"] = [item]
    union = np.zeros((H // 8, W // 8), dtype=bool)
    for m in route_masks.values():
        union |= m
    land = heights[4::8, 4::8] > sea
    land_cells, route_land = int(land.sum()), int((union & land).sum())
    land_pct = 100 * route_land / land_cells

    for r in out_routes:
        ap = town_by[r["to_town"]]["approach"]
        oldn, newn = ap.get("route_length_blocks"), r["distance"]["computed_walked_blocks"]
        ap["route_length_blocks"] = newn
        ap["route_length_source"] = r["id"]
        ap["route_length_method"] = "full-resolution A* on the canonical heightmap (tools/build_routes.py)"
        if oldn is not None and isinstance(ap.get("text"), str):
            ap["text"] = ap["text"].replace("{:,}".format(oldn), "{:,}".format(newn)).replace(str(oldn), str(newn))
        ap["water_crossings"] = [{"kind": w["kind"], "id": w["id"], "x": w["at"]["x"], "z": w["at"]["z"]} for w in r["water_crossings"]]
    towns["critical_path_geometry"]["victory_road_blocks"] = next(r["distance"]["computed_walked_blocks"] for r in out_routes if r["id"] == "victory_road")

    inputs = {rel: sha256_file(D / rel.split("/")[-1]) for rel in ("data/world.json", "data/regions.json", "data/rivers.json", "data/landmarks.json")}
    inputs["town_centres_canonical_json"] = hashlib.sha256(json.dumps(
        {t["id"]: [t["centre"]["x"], t["centre"]["z"]] for t in towns["towns"]}, sort_keys=True).encode()).hexdigest()
    inputs["heightmap"] = world["heightmap"]["sha256"]
    payload = dict(old)
    payload.update({
        "status": "terrain_derived_candidate", "generated_on": a.date,
        "source_of_truth": {"heightmap": world["heightmap"]["path"], "heightmap_sha256": world["heightmap"]["sha256"],
                            "world": "data/world.json", "regions": "data/regions.json", "towns": "data/towns.json",
                            "rivers": "data/rivers.json", "landmarks": "data/landmarks.json"},
        "coordinates": {"system": "Minecraft block coordinates", "horizontal": ["x", "z"], "vertical": "y from the canonical heightmap"},
        "box_generation": dict(old["box_generation"], total_box_count=sum(r["spawn_scope"]["box_count"] for r in out_routes)),
        "landmass_route_coverage": {"land_definition": "heightmap y > sea level %g" % sea, "sample_cell_blocks": 8,
                                    "land_cells": land_cells, "route_land_cells": route_land,
                                    "landmass_inside_any_route_corridor_pct": round(land_pct, 3), "one_third_limit_pct": 33.333,
                                    "verdict": "PASS" if land_pct <= 33.333 else "FAIL: corridors are too wide"},
        "routes": out_routes, "adjacent_route_overlaps": adj,
        "subregion_holes": {"count": len(all_holes), "intervals": all_holes,
                            "blocking_note": "Close these regions.json polygon gaps before compiling coordinate-box spawn files." if all_holes
                            else "None: every dense path sample lies inside a sub-region polygon."},
        "derivation_record": {"executed_command": "python tools/build_routes.py --source-root <root>" + (" --geography-only" if a.geography_only else ""),
                              "executed_on": a.date, "generator": "tools/build_routes.py", "base_router": "tools/route_path.py",
                              "generator_sha256": sha256_file(Path(__file__)), "base_router_sha256": sha256_file(Path(RP.__file__)),
                              "input_sha256": inputs,
                              "output_summary": {"route_distances_blocks": {r["id"]: r["distance"]["computed_walked_blocks"] for r in out_routes},
                                                 "total_coordinate_boxes": sum(r["spawn_scope"]["box_count"] for r in out_routes),
                                                 "landmass_inside_route_corridors_pct": round(land_pct, 3),
                                                 "subregion_hole_intervals": len(all_holes)}},
    })
    dest = out_dir or D
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "routes.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (dest / "towns.json").write_text(json.dumps(towns, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote data/routes.json (%d routes, %d boxes, %d holes, landmass %.2f%%) and town approach lengths"
          % (len(out_routes), payload["box_generation"]["total_box_count"], len(all_holes), land_pct))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
