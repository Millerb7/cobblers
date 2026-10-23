#!/usr/bin/env python
"""Walked trails from the towns to the cave and mine entrances, a signpost at each start, and the guides' waypoint functions.

The owner, 2026-10-22: "i think if its near a town, add a path to it" and "an npc to give a waypoint to a mine would be
cool." data/entrance_trails.json is the table (which town, which street end, which entrance, what the sign says, which
guide offers which waypoint); this tool turns it into two packs, build/datapacks/cobblers_entrance_trails (the trails) and cobblers_entrance_guides (the offers):

  trails/<trail id>        a 3-wide ribbon (dirt_path centre, gravel and coarse_dirt flanks) laid on the heightmap's ground,
                           vegetation cleared 4 blocks up, a spruce-fence post with a lantern on it every 24 blocks beside
                           the ribbon, and a two-faced signpost near the start (the front names the entrance and the
                           distance, the back the town), in the format tools/signposts.py writes
  guides/<system id>       run as the player by the guide's dialogue transition: one tellraw offering a shareable Xaero's
                           waypoint to the entrance, the form of the "Next gym" offer (tools/progression_pack.py xaero_share)

How a trail is found (all from tools/ground.py, the canonical heightmap, rounded; never from a world): an eight-connected
A* over a window round start and goal. A cell is open when it and its eight neighbours are not steeper than 40 degrees
(tools/build_routes.py's router limit), not water or within `water_clear` of it, and not within `building_clear` of an
authored point, box or short polyline in data/*.json (the water and authored rasters of tools/mine_nets_world.py, with
the route files left out so a trail can cross a road). An edge costs its length plus six times its climb, and may not
rise or fall more than one block in rounded ground. The found line is smoothed (a moving average, checked cell by cell
against the same rules, falling back to the raw line), then the ribbon, the lanterns and the sign are laid on it.

WHAT THIS DOES NOT COVER (CLAUDE.md "Our list is not the world"). It does not know a tree, pond, marsh or rock outcrop
the world holds and no data file carries (vegetation in the ribbon is cleared, nothing else is), a structure a mod or
the world generator placed, or a path another generator lays after it; the audit (tools/entrance_trails_audit.py) checks
the other generated packs' writes when build/ holds them. It bridges nothing: a trail that would have to cross water is
refused. Nothing here has been applied to any world.

  python tools/entrance_trails.py plan [<trail id>]   find the lines and print lengths and checks; nothing written
  python tools/entrance_trails.py build               -> build/datapacks/cobblers_entrance_trails (+ cobblers_entrance_guides), derived/entrance_trails/plan.json
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import terrain as T  # noqa: E402
from terrain import env_source_root  # noqa: E402
import mine_nets_world as W  # noqa: E402
import function_limits  # noqa: E402

DATA = ROOT / "data" / "entrance_trails.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_entrance_trails"
FUNCS = PACK / "data" / "cobblers" / "function"
# the guides' functions are called at play time (a dialogue runs them), so they are a pack of their own: the trails are one-shot
# placement (tools/reapply.py R16T) and `reapply.py strip` can move that pack out; a pack with one reachable function cannot go
GUIDE_PACK = ROOT / "build" / "datapacks" / "cobblers_entrance_guides"
GUIDE_FUNCS = GUIDE_PACK / "data" / "cobblers" / "function"
REPORT = ROOT / "derived" / "entrance_trails" / "plan.json"
PAD = 90                       # blocks of window round the start-goal box
CLIMB_WEIGHT = 6.0             # blocks of walking one block of climb costs the A*
NEIGH = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
# the ground rule (tools/ground_rule.py): nothing here reads a world to decide a position
WORLD_READS = set()


class TrailError(Exception):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load():
    return load_json(DATA)


def entrances():
    """{mouth/adit id: {x, z, system, kind}} from data/cave_systems.json and data/mine_networks.json."""
    out = {}
    for s in load_json(ROOT / "data" / "cave_systems.json")["systems"]:
        for m in s["mouths"]:
            out[m["id"]] = {"x": m["x"], "z": m["z"], "system": s["id"], "kind": "cave", "name": s["name"]}
    for n in load_json(ROOT / "data" / "mine_networks.json")["networks"]:
        for a in n["adits"]:
            out[a["id"]] = {"x": a["portal"][0], "z": a["portal"][1], "system": n["id"], "kind": "mine", "name": n["name"]}
    return out


def towns():
    return {t["id"]: t for t in load_json(ROOT / "data" / "towns.json")["towns"]}


# ------------------------------------------------------------------ the rasters


def authored_obstacles(box, rules, skip_town):
    """bool [z, x] raster of what a trail keeps `building_clear` from: every authored point (disc), box and short
    polyline of data/*.json outside the skipped files, and every town footprint but the one the trail starts in."""
    skip = set(rules["skip_files"])
    pts, rects, segs = [], [], []
    for p in sorted((ROOT / "data").glob("*.json")):
        if p.name in skip:
            continue
        W._walk(load_json(p), pts, rects, segs)
    clear = int(rules["building_clear"])
    m = box.zeros()
    foot = towns()[skip_town]["footprint"] if skip_town else None
    own = (foot["min_x"], foot["min_z"], foot["max_x"], foot["max_z"]) if foot else None
    for x, z in set((int(round(a)), int(round(b))) for a, b in pts):
        if box.x0 - clear <= x <= box.x1 + clear and box.z0 - clear <= z <= box.z1 + clear:
            box.put_rect(m, x - 2, z - 2, x + 2, z + 2)
    for x0, z0, x1, z1 in set((int(a), int(b), int(c), int(d)) for a, b, c, d in rects):
        if (x0, z0, x1, z1) == own:
            continue
        # a box is a building or an area: a box wider than 220 is an area (a spawn box, a region), not a building
        if x1 - x0 > 220 or z1 - z0 > 220:
            continue
        if x1 < box.x0 or x0 > box.x1 or z1 < box.z0 or z0 > box.z1:
            continue
        box.put_rect(m, x0, z0, x1, z1)
    for a, b, c, e in set((int(round(a)), int(round(b)), int(round(c)), int(round(e))) for a, b, c, e in segs):
        if max(a, c) < box.x0 or min(a, c) > box.x1 or max(b, e) < box.z0 or min(b, e) > box.z1:
            continue
        box.put_segment(m, a, b, c, e)
    for t in towns().values():
        f = t["footprint"]
        if (own and (f["min_x"], f["min_z"], f["max_x"], f["max_z"]) == own) or t["id"] == skip_town:
            continue
        box.put_rect(m, f["min_x"], f["min_z"], f["max_x"], f["max_z"])
    return W.dilate_sq(m, clear)


class Window:
    """The ground, water and authored rasters of one trail's search window."""

    def __init__(self, g, spec, rules, ent):
        sx, sz = spec["from_at"]
        gx, gz = ent["x"], ent["z"]
        x0, x1 = min(sx, gx) - PAD, max(sx, gx) + PAD
        z0, z1 = min(sz, gz) - PAD, max(sz, gz) + PAD
        self.box = W.Box(max(x0, g.ox), max(z0, g.oz), min(x1, g.ox + g.heights.shape[1] - 1), min(z1, g.oz + g.heights.shape[0] - 1))
        b = self.box
        self.raw = g.heights[b.z0 - g.oz:b.z1 - g.oz + 1, b.x0 - g.ox:b.x1 - g.ox + 1].astype(np.float64)
        self.hr = np.round(self.raw).astype(int)
        slope = T.slope_degrees(self.raw.astype(np.float32))
        self.steep = slope > float(rules["max_edge_degrees"])
        wet = W.water_seed(b, self.hr, {"sea_near": rules["sea_near"], "river_corridor": rules["river_corridor"]})
        self.wet = W.dilate_sq(wet, int(rules["water_clear"]) + 1)      # +1: the ribbon's own half width
        self.obst = authored_obstacles(b, rules, spec.get("from_town"))
        self.start = (sx, sz)
        self.goal = (gx, gz)
        base = self.steep | self.wet | self.obst
        # a centre cell needs all eight neighbours open: the ribbon is a plus round it
        self.bad = W.dilate_sq(base, 1)
        self.start_open, self.goal_open = int(rules["start_open"]), int(rules["goal_open"])

    def idx(self, x, z):
        return z - self.box.z0, x - self.box.x0

    def blocked(self, x, z):
        """True when a centre cell at (x, z) is not open, with the start and goal neighbourhoods relaxed for the
        slope and the authored rasters (never for water)."""
        if not self.box.inside(x, z):
            return True
        iz, ix = self.idx(x, z)
        if self.wet[iz, ix]:
            return True
        if math.hypot(x - self.start[0], z - self.start[1]) <= self.start_open or \
                math.hypot(x - self.goal[0], z - self.goal[1]) <= self.goal_open:
            return False
        return bool(self.bad[iz, ix])


def edge_ok(win, a, b, rules):
    """The edge a -> b: rounded ground changes by at most `max_step`, and the raw ground by no more than 40 degrees."""
    (ax, az), (bx, bz) = a, b
    ia, ib = win.idx(ax, az), win.idx(bx, bz)
    if abs(int(win.hr[ib]) - int(win.hr[ia])) > int(rules["max_step"]):
        return False
    run = math.hypot(bx - ax, bz - az)
    climb = abs(float(win.raw[ib]) - float(win.raw[ia]))
    return math.degrees(math.atan2(climb, run)) <= float(rules["max_edge_degrees"]) + 1e-9


def astar(win, rules):
    sx, sz = win.start
    gx, gz = win.goal
    stop = float(rules["stop_short"])
    h, w = win.box.shape
    ox, oz = win.box.x0, win.box.z0
    if win.blocked(sx, sz):
        raise TrailError("start %s is not open ground" % (win.start,))

    def heur(x, z):
        dx, dz = abs(x - gx), abs(z - gz)
        return max(0.0, (dx + dz) - (2 - math.sqrt(2)) * min(dx, dz) - stop)

    best = {(sx, sz): 0.0}
    came = {}
    pq = [(heur(sx, sz), 0.0, sx, sz)]
    seen = set()
    while pq:
        _, cost, x, z = heapq.heappop(pq)
        if (x, z) in seen:
            continue
        seen.add((x, z))
        if math.hypot(x - gx, z - gz) <= stop:
            path = [(x, z)]
            while path[-1] in came:
                path.append(came[path[-1]])
            return path[::-1]
        for dx, dz in NEIGH:
            nx, nz = x + dx, z + dz
            if (nx, nz) in seen or win.blocked(nx, nz):
                continue
            if not edge_ok(win, (x, z), (nx, nz), rules):
                continue
            run = math.hypot(dx, dz)
            climb = abs(float(win.raw[win.idx(nx, nz)]) - float(win.raw[win.idx(x, z)]))
            nc = cost + run + CLIMB_WEIGHT * climb
            if nc < best.get((nx, nz), 1e18):
                best[(nx, nz)] = nc
                came[(nx, nz)] = (x, z)
                heapq.heappush(pq, (nc + heur(nx, nz), nc, nx, nz))
    raise TrailError("no open line from %s to within %d of %s (water, a building, or ground steeper than 40 degrees in the way)"
                     % (win.start, int(stop), win.goal))


def bresenham(a, b):
    (x0, z0), (x1, z1) = a, b
    n = max(abs(x1 - x0), abs(z1 - z0))
    if n == 0:
        return [a]
    out = []
    for i in range(n + 1):
        c = (int(round(x0 + (x1 - x0) * i / n)), int(round(z0 + (z1 - z0) * i / n)))
        if not out or out[-1] != c:
            out.append(c)
    return out


def line_ok(win, cells, rules):
    for i, c in enumerate(cells):
        if win.blocked(*c):
            return False
        if i and (max(abs(c[0] - cells[i - 1][0]), abs(c[1] - cells[i - 1][1])) > 1
                  or not edge_ok(win, cells[i - 1], c, rules)):
            return False
    return True


def smooth(win, path, rules):
    """The raw A* line with its jags taken out: a moving average over +-w cells, re-laid cell by cell and kept only if it
    passes the same open-cell and edge rules; the largest window that passes, else the raw line."""
    for w in (7, 5, 3):
        if len(path) < 2 * w + 3:
            continue
        pts = [path[0]]
        for i in range(1, len(path) - 1):
            lo, hi = max(0, i - w), min(len(path) - 1, i + w)
            k = min(i - lo, hi - i)
            seg = path[i - k:i + k + 1]
            pts.append((sum(p[0] for p in seg) / len(seg), sum(p[1] for p in seg) / len(seg)))
        pts.append(path[-1])
        cells = []
        for a, b in zip(pts, pts[1:]):
            for c in bresenham((int(round(a[0])), int(round(a[1]))), (int(round(b[0])), int(round(b[1])))):
                if not cells or cells[-1] != c:
                    cells.append(c)
        if line_ok(win, cells, rules):
            return cells, w
    return path, 0


def length(cells):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(cells, cells[1:]))


def ribbon(cells):
    """{(x, z): is_centre}: the centre cells and the four neighbours of each."""
    out = {}
    for c in cells:
        out[c] = True
    for x, z in cells:
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            out.setdefault((x + dx, z + dz), False)
    return out


def flank_block(rules, x, z):
    h = int(hashlib.sha256(("%d,%d" % (x, z)).encode()).hexdigest()[:4], 16)
    return rules["flank"][h % len(rules["flank"])]


# ------------------------------------------------------------------ the plan


def plan_trail(g, spec, rules, ents):
    ent = ents[spec["to"]]
    win = Window(g, spec, rules, ent)
    raw = astar(win, rules)
    cells, w = smooth(win, raw, rules)
    arc = length(cells)
    if arc > float(rules["max_length_blocks"]):
        raise TrailError("%s: %.0f blocks, past the %d a trail is laid for" % (spec["id"], arc, rules["max_length_blocks"]))
    rb = ribbon(cells)
    # lanterns: a post every `lantern_every` blocks of arc on the right of the line, `lantern_offset` from the centre
    posts, acc, nxt = [], 0.0, float(rules["lantern_every"])
    taken = set(rb)
    for i in range(1, len(cells) - 1):
        acc += math.hypot(cells[i][0] - cells[i - 1][0], cells[i][1] - cells[i - 1][1])
        if acc < nxt:
            continue
        a, b = cells[max(0, i - 2)], cells[min(len(cells) - 1, i + 2)]
        dx, dz = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dz) or 1.0
        dx, dz = dx / d, dz / d
        spot = None
        for k in (rules["lantern_offset"], rules["lantern_offset"] + 0.5, rules["lantern_offset"] + 1.0):
            for side in (1, -1):
                px = int(round(cells[i][0] - dz * k * side))
                pz = int(round(cells[i][1] + dx * k * side))
                if (px, pz) in taken or not win.box.inside(px, pz) or win.wet[win.idx(px, pz)]:
                    continue
                # a post stands clear of the ribbon: two blocks or more from every centre cell, not touching its corner
                if min(math.hypot(px - cx, pz - cz) for cx, cz in cells[max(0, i - 6):i + 7]) < 2.0:
                    continue
                spot = (px, pz)
                break
            if spot:
                break
        if spot:
            posts.append(spot)
            taken.add(spot)
            nxt = acc + float(rules["lantern_every"])
    return {"win": win, "cells": cells, "raw_cells": len(raw), "smooth_window": w, "arc": arc, "ribbon": rb, "posts": posts}


def sign_lines(spec, rules, n_blocks, town_name):
    n = int(round(n_blocks / 10.0) * 10)
    front = list(spec["sign"]) + ["%s %d blocks" % (spec["kind"], n)]
    if len(front) > 4:
        raise TrailError("%s: sign front has %d lines" % (spec["id"], len(front)))
    back = [town_name, "%d blocks" % n]
    for t in front + back:
        if len(t) > 15:
            raise TrailError("%s: sign line %r is longer than a sign's 15 characters" % (spec["id"], t))
    pad = lambda ls: (list(ls) + [""] * 4)[:4]
    return pad(front), pad(back), n


def place_sign(plan, g, rules, seats):
    """(x, y, z, rotation) of the signpost: beside the line `sign_index` cells from its start, `sign_offset` to the
    right of the traveller, on dry ground clear of the ribbon, the posts and any seated NPC."""
    import signposts as SP
    cells, win = plan["cells"], plan["win"]
    taken = set(plan["ribbon"]) | set(plan["posts"])
    base = min(int(rules["sign_index"]), len(cells) - 3)
    for i in list(range(base, min(len(cells) - 2, base + 30))) + list(range(base - 1, 1, -1)):
        a, b = cells[max(0, i - 2)], cells[min(len(cells) - 1, i + 2)]
        dx, dz = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dz) or 1.0
        dx, dz = dx / d, dz / d
        x = int(round(cells[i][0] - dz * rules["sign_offset"]))
        z = int(round(cells[i][1] + dx * rules["sign_offset"]))
        if (x, z) in taken or not win.box.inside(x, z) or win.wet[win.idx(x, z)]:
            continue
        y = g(x, z) + 1
        if SP.seat_clash(x, y, z, seats):
            continue
        return x, y, z, SP.rotation(-dx, -dz)
    raise TrailError("no dry ground for the signpost")


def build_plans(g=None, only=None, source_root=None):
    import ground as G
    g = g or G.Ground(source_root or env_source_root())
    doc = load()
    rules = doc["rules"]
    ents = entrances()
    import signposts as SP
    SP.SUBNAMES.update(SP._subnames())
    names = SP.place_names()
    seats = SP.npc_seats()
    out = []
    for spec in doc["trails"]:
        if only and spec["id"] != only:
            continue
        if spec["to"] not in ents:
            raise TrailError("%s: no entrance %r in data/cave_systems.json or data/mine_networks.json" % (spec["id"], spec["to"]))
        spec = dict(spec, kind=ents[spec["to"]]["kind"])
        plan = plan_trail(g, spec, rules, ents)
        if spec.get("from_town"):
            label = names.get(spec["from_town"], spec["from_town"])
        else:
            label = load_json(ROOT / "data" / "signposts.json")["route_labels"][spec["from_route"]]
        front, back, n = sign_lines(spec, rules, plan["arc"], label)
        plan.update(spec=spec, front=front, back=back, sign_n=n, sign=place_sign(plan, g, rules, seats), ent=ents[spec["to"]])
        out.append(plan)
    return out, g, rules


# ------------------------------------------------------------------ commands


def runs(xs):
    xs = sorted(xs)
    out, start = [], None
    for i, x in enumerate(xs):
        if start is None:
            start = prev = x
        elif x == prev + 1:
            prev = x
        else:
            out.append((start, prev))
            start = prev = x
    if start is not None:
        out.append((start, prev))
    return out


def trail_commands(plan, g, rules):
    import signposts as SP
    spec = plan["spec"]
    cmds = ["# Generated by tools/entrance_trails.py from data/entrance_trails.json (%s). Re-run to rebuild." % spec["id"],
            "# %s: %s -> %s (%s), %.0f blocks, %d lanterns, sign at %s"
            % (spec["id"], spec.get("from_town") or spec["from_route"], spec["to"], spec["kind"], plan["arc"],
               len(plan["posts"]), plan["sign"][:3])]
    by_z = {}
    for (x, z), centre in plan["ribbon"].items():
        by_z.setdefault(z, {})[x] = centre
    clear = int(rules["clear_height"])
    for z in sorted(by_z):
        for x0, x1 in runs(by_z[z]):
            ys = [g(x, z) for x in range(x0, x1 + 1)]
            lo, hi = min(ys) + 1, max(ys) + clear
            cmds.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:replaceable" % (x0, lo, z, x1, hi, z))
            for tag in ("#minecraft:logs", "#minecraft:leaves"):
                cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, lo, z, x1, hi, z, tag))
    for z in sorted(by_z):
        for x in sorted(by_z[z]):
            blk = rules["centre"] if by_z[z][x] else flank_block(rules, x, z)
            cmds.append("setblock %d %d %d %s" % (x, g(x, z), z, blk))
    for px, pz in plan["posts"]:
        y = g(px, pz) + 1
        cmds.append("fill %d %d %d %d %d %d minecraft:air" % (px, y, pz, px, y + 3, pz))
        cmds.append("setblock %d %d %d %s" % (px, y, pz, rules["post"]))
        cmds.append("setblock %d %d %d %s" % (px, y + 1, pz, rules["post"]))
        cmds.append("setblock %d %d %d %s[hanging=false]" % (px, y + 2, pz, rules["lamp"]))
    x, y, z, rot = plan["sign"]
    cmds.append("fill %d %d %d %d %d %d minecraft:air" % (x, y, z, x, y + 2, z))
    cmds.append("setblock %d %d %d %s" % (x, y, z, rules["post"]))
    p = {"rotation": rot, "front": plan["front"], "back": plan["back"]}
    cmds.append("setblock %d %d %d %s" % (x, y + 1, z, SP.sign_nbt(p, rules["sign_wood"])))
    return cmds


def guide_commands(guide, ents, g):
    from progression_pack import xaero_share
    ent = ents[guide["goes_to"]]
    m = guide["marker"]
    share = xaero_share({"name": m["name"], "initials": m["initials"], "x": ent["x"], "y": g(ent["x"], ent["z"]) + 1,
                         "z": ent["z"], "color": m["color"]})
    text = ["", {"text": "%s. " % m["name"], "color": "gold"},
            {"text": "Add it to your map: ", "color": "gray"}, {"text": share, "color": "dark_gray"}]
    return ["# Generated by tools/entrance_trails.py from data/entrance_trails.json (%s). Run as the player by the guide's dialogue." % guide["id"],
            "tellraw @s " + json.dumps(text)], share


def build(a):
    plans, g, rules = build_plans(source_root=a.source_root)
    return write_packs(plans, g, rules)


def write_packs(plans, g, rules, pack=None, guide_pack=None, report_path=None):
    """Write the trails' pack and the guides' pack for planned `plans`; the defaults are the build/ locations."""
    pack, guide_pack = Path(pack or PACK), Path(guide_pack or GUIDE_PACK)
    report_path = Path(report_path or REPORT)
    funcs, guide_funcs = pack / "data" / "cobblers" / "function", guide_pack / "data" / "cobblers" / "function"
    doc = load()
    ents = entrances()
    if pack.exists():
        shutil.rmtree(pack)
    if guide_pack.exists():
        shutil.rmtree(guide_pack)
    (funcs / "trails").mkdir(parents=True)
    (guide_funcs / "guides").mkdir(parents=True)
    (pack / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                      "Cobblers: trails to the caves and mines (tools/entrance_trails.py)"}}, indent=2) + "\n", encoding="utf-8")
    (guide_pack / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                            "Cobblers: the entrance guides' waypoint offers (tools/entrance_trails.py)"}}, indent=2) + "\n", encoding="utf-8")
    report = {"trails": [], "guides": []}
    names = []
    for p in plans:
        cmds = function_limits.ensure_loaded(trail_commands(p, g, rules))
        refused = function_limits.check_lines(cmds, p["spec"]["id"])
        if refused:
            raise SystemExit("%s: %d command(s) the server would refuse: %s" % (p["spec"]["id"], len(refused), refused[:3]))
        (funcs / "trails" / ("%s.mcfunction" % p["spec"]["id"])).write_text("\n".join(cmds) + "\n", encoding="utf-8", newline="\n")
        names.append(p["spec"]["id"])
        report["trails"].append({"id": p["spec"]["id"], "from": p["spec"].get("from_town") or p["spec"]["from_route"], "to": p["spec"]["to"],
                                 "from_at": p["spec"]["from_at"], "length_blocks": round(p["arc"], 1), "sign_n": p["sign_n"],
                                 "centre_cells": len(p["cells"]), "lanterns": len(p["posts"]), "sign": list(p["sign"][:3]),
                                 "rotation": p["sign"][3], "front": p["front"], "back": p["back"],
                                 "smooth_window": p["smooth_window"], "commands": len(cmds)})
        print("%-30s %-18s -> %-16s %5.0f blocks  %2d lanterns  smooth w%d  %d commands"
              % (p["spec"]["id"], p["spec"].get("from_town") or p["spec"]["from_route"], p["spec"]["to"], p["arc"], len(p["posts"]), p["smooth_window"], len(cmds)))
    (funcs / "trails" / "index.txt").write_text("\n".join(names) + "\n", encoding="utf-8", newline="\n")
    gnames = []
    for gd in doc["guides"]:
        cmds, share = guide_commands(gd, ents, g)
        (guide_funcs / "guides" / ("%s.mcfunction" % gd["id"])).write_text("\n".join(cmds) + "\n", encoding="utf-8", newline="\n")
        gnames.append(gd["id"])
        report["guides"].append({"id": gd["id"], "goes_to": gd["goes_to"], "share": share})
    (guide_funcs / "guides" / "index.txt").write_text("\n".join(gnames) + "\n", encoding="utf-8", newline="\n")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("wrote", pack, "and", guide_pack)
    return 0


def plan_cmd(a):
    plans, g, rules = build_plans(only=a.trail, source_root=a.source_root)
    for p in plans:
        print("%-30s %5.0f blocks (raw %d cells, smooth w%d), %d lanterns, sign at %s, %s"
              % (p["spec"]["id"], p["arc"], p["raw_cells"], p["smooth_window"], len(p["posts"]), p["sign"][:3], p["front"][:3]))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("trail", nargs="?")
    pl.add_argument("--source-root", default=env_source_root())
    bd = sub.add_parser("build")
    bd.add_argument("--source-root", default=env_source_root())
    a = ap.parse_args(argv)
    try:
        return {"plan": plan_cmd, "build": build}[a.cmd](a)
    except TrailError as e:
        print("REFUSED: %s" % e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
