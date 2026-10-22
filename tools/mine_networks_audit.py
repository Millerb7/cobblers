#!/usr/bin/env python
"""Audit of the long mine networks, from the BUILT FUNCTIONS (build/datapacks/cobblers_mine_networks) and nothing of the
generator's geometry.

tools/mine_networks.py decides where a drift goes from its own rasters; this tool does not import it. It reads the
`fill` and `setblock` commands the generator wrote, replays them into a block map, and checks every carved cell against
the canonical heightmap (tools/ground.py, rounded) and against the data files directly, with its own derivation of
water, authored places and distance (Euclidean, where the generator grows with a square margin). A rule the generator
broke shows up here whatever the generator believed. tests/test_mine_networks.py proves that by MUTATING THE GENERATOR
(not the data): a generator that over-reads the ground, one that forgets the water, one that drops the shell, one that
ignores the authored places must each be caught.

What is checked (the number is the audit step):

  1  limits     every function passes tools/function_limits.py check_lines (fill <= 32,768, forceload <= 256 chunks)
  2  bounds     no carved cell west of the data's x_min, under y_floor_min, or outside the world
  3  cover      >= cover_min (8) of canonical ground over every written cell, but the first `exempt` cells of an adit
  4  water      no carved column within water_clear (12, Euclid) of the sea (ground <= sea level), a lake basin
                (landmarks water_body.basin_polygons), a river corridor (graded centreline + the water-shape corridor
                + half the widest reach) or a waterway
  5  authored   no carved column within authored_clear (32, Euclid) of any x/z, box or short polyline another data file
                authors (the files the generator also skips excepted: this file, world, regions, cells)
  6  shell      every cell within `shell` (2) of a carved cell is covered by a `replace minecraft:water` fill AND a
                `replace minecraft:lava` fill; in every function the carving is done again after the last shell fill
  7  walk       every carved cell is reached from an adit's portal over open cells (air, ladder, rail, lantern);
                every ladder has a solid block behind it and a ladder above and below it; every stair faces uphill, has
                air over it and a floor under; every rail stands on cobblestone with air over it
  8  fittings   vanilla blocks only, the ones the data names; ore only in rock (never in a carved cell), under cover,
                deepslate ore only under y8 and stone ore only from y0 up
  9  policy     every spawn-condition block placed is allowed by a data/spawn_block_policy.json entry scoped to mine_networks
 10  scale      the independent drift estimate (carved columns of height 4 or less, a third of them) is >= 2,000; networks
                stand `network_gap` apart

NOT CHECKED (CLAUDE.md "Our list is not the world"): the world. Rock under the surface is assumed to be rock; a natural
cave, a mod structure, a placed trader or water the data does not carry is invisible to every step above except the
shell (which replaces fluid within 2 blocks of a carved box and nothing further). Whether the stairs, ladders, rails and
lanterns come out as written in a running game is not verified here. derived/routes and build/paint are generated and
absent from a fresh checkout, so routed legs are not part of the authored places.

  python tools/mine_networks_audit.py [--pack build/datapacks/cobblers_mine_networks] [--only <network id>]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "mine_networks.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_mine_networks"
FACES = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
OPEN_BASES = ("minecraft:air", "minecraft:ladder", "minecraft:rail", "minecraft:lantern")
NUM = r"(-?\d+)"
FILL = re.compile(r"fill %s %s %s %s %s %s (\S+)(?: replace (\S+))?$" % ((NUM,) * 6))
SET = re.compile(r"setblock %s %s %s (\S+)$" % ((NUM,) * 3))
SKIP_FILES = {"mine_networks.json", "mine_crew_trainers.json", "world.json", "regions.json", "cells.json"}


def base(b):
    return b.split("[")[0]


def facing(b):
    m = re.search(r"facing=(\w+)", b)
    return m.group(1) if m else None


# ------------------------------------------------------------------ reading the build

def read_pack(pack, net_id):
    """{(tx, tz): [parsed ops]} for one network, each op ('fill', box, block, filter) or ('set', cell, block) in order."""
    d = Path(pack) / "data" / "cobblers" / "function" / "mine_networks"
    out, problems = {}, []
    for f in sorted(d.glob("%s_t_*_*.mcfunction" % net_id)):
        t = tuple(int(v) for v in f.stem[len(net_id) + 3:].split("_"))
        ops = []
        lines = f.read_text(encoding="utf-8").splitlines()
        bad = FL.check_lines(lines, str(f))
        for n, cmd, why in bad:
            problems.append("limits: %s line %d: %s" % (f.name, n, why))
        for ln, raw in enumerate(lines, start=1):
            s = raw.strip()
            if not s or s.startswith("#") or s.startswith("forceload "):
                continue
            m = FILL.match(s)
            if m:
                v = [int(x) for x in m.groups()[:6]]
                ops.append(("fill", (min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]), max(v[2], v[5])),
                            m.group(7), m.group(8), ln))
                continue
            m = SET.match(s)
            if m:
                ops.append(("set", tuple(int(x) for x in m.groups()[:3]), m.group(4), None, ln))
                continue
            problems.append("limits: %s line %d: command not recognised: %s" % (f.name, ln, s[:70]))
        out[t] = (ops, lines)
    return out, problems


def cells_of(box):
    x0, y0, z0, x1, y1, z1 = box
    return ((x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1))


def replay(tiles):
    """(state {cell: block}, carved set): every non-filtered write in order; carved is every cell any air fill emptied."""
    state, carved = {}, set()
    for t in sorted(tiles):
        for op in tiles[t][0]:
            if op[0] == "fill" and op[3] is None:
                for c in cells_of(op[1]):
                    state[c] = op[2]
                if base(op[2]) == "minecraft:air":
                    carved.update(cells_of(op[1]))
            elif op[0] == "set":
                state[op[1]] = op[2]
                if base(op[2]) == "minecraft:air":
                    carved.add(op[1])
    return state, carved


# ------------------------------------------------------------------ the data, read directly

def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def authored_places():
    """([points], [rects], [segments]) every data file but the skipped ones carries; read with its own walker."""
    pts, rects, segs = set(), set(), set()

    def isnum(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    for p in sorted((ROOT / "data").glob("*.json")):
        if p.name in SKIP_FILES:
            continue
        stack = [json.loads(p.read_text(encoding="utf-8"))]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                if isnum(o.get("x")) and isnum(o.get("z")):
                    pts.add((o["x"], o["z"]))
                if all(isnum(o.get(k)) for k in ("min_x", "min_z", "max_x", "max_z")) and o["max_x"] - o["min_x"] < 2000 \
                        and o["max_z"] - o["min_z"] < 2000:
                    rects.add((o["min_x"], o["min_z"], o["max_x"], o["max_z"]))
                for k, v in o.items():
                    if not (isinstance(k, str) and k.startswith("nearest_")):
                        stack.append(v)
            elif isinstance(o, list):
                nums = [isnum(v) for v in o]
                if len(o) == 2 and all(nums):
                    pts.add((o[0], o[1]))
                elif len(o) == 3 and all(nums):
                    pts.update({(o[0], o[2]), (o[0], o[1])})
                elif len(o) == 4 and all(nums):
                    if o[2] >= o[0] and o[3] >= o[1] and o[2] - o[0] < 2000 and o[3] - o[1] < 2000:
                        rects.add(tuple(o))
                else:
                    pairs = [v for v in o if isinstance(v, list) and len(v) >= 2 and isnum(v[0]) and isnum(v[1])]
                    if len(pairs) == len(o) and len(o) >= 3:
                        for a, b in zip(o, o[1:]):
                            if math.hypot(b[0] - a[0], b[1] - a[1]) <= 120:
                                segs.add((a[0], a[1], b[0], b[1]))
                    stack.extend(o)
    return sorted(pts), sorted(rects), sorted(segs)


def seg_dist(px, pz, ax, az, bx, bz):
    """Euclidean distance from arrays of points to one segment."""
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    if L2 == 0:
        return np.hypot(px - ax, pz - az)
    t = np.clip(((px - ax) * dx + (pz - az) * dz) / L2, 0, 1)
    return np.hypot(px - (ax + t * dx), pz - (az + t * dz))


def in_ring(px, pz, ring):
    """Even-odd inside test of arrays of points against one polygon ring."""
    inside = np.zeros(px.shape, bool)
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, zi = ring[i][0], ring[i][1]
        xj, zj = ring[j][0], ring[j][1]
        if zi != zj:
            cond = ((zi > pz) != (zj > pz)) & (px < (xj - xi) * (pz - zi) / float(zj - zi) + xi)
            inside ^= cond
        j = i
    return inside


# ------------------------------------------------------------------ the audit

def audit_network(spec, net, tiles, state, carved, g):
    rules = spec["rules"]
    out = []
    stats = {}
    if not carved:
        return ["%s: nothing is carved" % net["id"]], stats
    cover = rules["cover_min"]
    # -- bounds
    xs = [c[0] for c in carved]
    ys = [c[1] for c in carved]
    zs = [c[2] for c in carved]
    if min(xs) < rules["x_min"]:
        out.append("bounds: a carved cell at x%d, west of x_min %d" % (min(xs), rules["x_min"]))
    if min(ys) < rules["y_floor_min"]:
        out.append("bounds: a carved cell at y%d, under y_floor_min %d" % (min(ys), rules["y_floor_min"]))
    box = net["box"]
    if min(xs) < box[0] or max(xs) > box[2] or min(zs) < box[1] or max(zs) > box[3]:
        out.append("bounds: carved cells reach outside the network's box %s" % (box,))
    # -- the heightmap under every written cell
    x0, x1, z0, z1 = min(xs) - 40, max(xs) + 40, min(zs) - 40, max(zs) + 40
    H = g.box(x0, z0, x1, z1).astype(np.int32)
    exempt = set()
    for a in net["adits"]:
        px, pz = a["portal"]
        dx, dz = FACES[a["heading"]]
        for i in range(int(a.get("exempt", spec["geometry"]["adit_exempt"])) + 1):
            for l in range(-2, 3):
                exempt.add((px + dx * i - dz * l, pz + dz * i + dx * l))
        if int(a.get("exempt", spec["geometry"]["adit_exempt"])) > rules["adit_exempt_max"]:
            out.append("cover: adit %s exempts %s cells, over adit_exempt_max %d" % (a["id"], a.get("exempt"), rules["adit_exempt_max"]))
    bad = 0
    worst = 99999
    for (x, y, z) in state:
        if (x, z) in exempt:
            continue
        c = int(H[z - z0, x - x0]) - y
        worst = min(worst, c)
        if c < cover:
            bad += 1
            if bad <= 3:
                out.append("cover: cell (%d, %d, %d) has %d of ground over it, under %d" % (x, y, z, c, cover))
    if bad > 3:
        out.append("cover: ... %d cells in all under %d of cover" % (bad, cover))
    stats["least_cover"] = worst
    # -- the carved columns
    cols = sorted({(c[0], c[2]) for c in carved})
    cx = np.array([c[0] for c in cols], np.float64)
    cz = np.array([c[1] for c in cols], np.float64)
    clear_w = rules["water_clear"]
    # sea: any column with ground at or under the sea level within the clearance (Euclid)
    sea_level = int(jload("world.json")["vertical"]["sea_level"])
    sea = H <= sea_level
    ix = (cx - x0).astype(int)
    iz = (cz - z0).astype(int)
    r = int(clear_w)
    hit = np.zeros(len(cols), bool)
    for dx in range(-r, r + 1):
        for dz in range(-r, r + 1):
            if dx * dx + dz * dz <= r * r:
                hit |= sea[iz + dz, ix + dx]
    if hit.any():
        k = int(np.argmax(hit))
        out.append("water: %d carved columns within %d of the sea (first (%d, %d), ground y%d)" %
                   (int(hit.sum()), clear_w, cols[k][0], cols[k][1], int(H[int(cz[k]) - z0, int(cx[k]) - x0])))
    # lakes
    lakes = 0
    for l in jload("landmarks.json")["landmarks"]:
        for ring in (l.get("water_body") or {}).get("basin_polygons") or []:
            rx = [q[0] for q in ring]
            rz = [q[1] for q in ring]
            if max(rx) < x0 or min(rx) > x1 or max(rz) < z0 or min(rz) > z1:
                continue
            lakes += 1
            bad = in_ring(cx, cz, ring)
            for a, b in zip(ring, ring[1:] + ring[:1]):
                bad |= seg_dist(cx, cz, a[0], a[1], b[0], b[1]) <= clear_w
            if bad.any():
                k = int(np.argmax(bad))
                out.append("water: %d carved columns inside or within %d of lake %s's basin (first (%d, %d))" %
                           (int(bad.sum()), clear_w, l["id"], cols[k][0], cols[k][1]))
    # rivers: the graded centreline, the water-shape corridor and half the widest reach, then the clearance
    corridor = float(jload("water_shape.json")["rivers"]["defaults"]["corridor_half_width_blocks"])
    for c in jload("rivers.json")["courses"]:
        w = max([q.get("width", 0) for q in c.get("reaches") or []] + [0]) / 2.0
        pts = c["graded_polyline"]
        near = np.zeros(len(cols), bool)
        for a, b in zip(pts, pts[1:]):
            if max(a[0], b[0]) < x0 - 200 or min(a[0], b[0]) > x1 + 200 or max(a[1], b[1]) < z0 - 200 or min(a[1], b[1]) > z1 + 200:
                continue
            near |= seg_dist(cx, cz, a[0], a[1], b[0], b[1]) <= corridor + w + clear_w
        if near.any():
            k = int(np.argmax(near))
            out.append("water: %d carved columns within %d of river %s's corridor (first (%d, %d))" %
                       (int(near.sum()), clear_w, c["id"], cols[k][0], cols[k][1]))
    for w in jload("waterways.json")["waterways"]:
        pts = w["polyline"]
        near = np.zeros(len(cols), bool)
        for a, b in zip(pts, pts[1:]):
            near |= seg_dist(cx, cz, a[0], a[1], b[0], b[1]) <= w.get("half_width", 8) + clear_w
        if near.any():
            out.append("water: %d carved columns within %d of the waterway %s" % (int(near.sum()), clear_w, w["id"]))
    stats["lake_basins_in_reach"] = lakes
    # -- authored places
    pts, rects, segs = authored_places()
    ac = float(rules["authored_clear"])
    near = np.zeros(len(cols), bool)
    first = None
    P = np.array([p for p in pts if x0 - 200 <= p[0] <= x1 + 200 and z0 - 200 <= p[1] <= z1 + 200], np.float64).reshape(-1, 2)
    for i in range(0, len(cols), 4000):
        sl = slice(i, i + 4000)
        if len(P):
            d2 = (cx[sl, None] - P[None, :, 0]) ** 2 + (cz[sl, None] - P[None, :, 1]) ** 2
            m = (d2 <= ac * ac).any(axis=1)
            near[sl] |= m
            if first is None and m.any():
                first = "a point at (%d, %d)" % tuple(P[int(np.argmax((d2 <= ac * ac)[int(np.argmax(m))]))])
    for (ax, az, bx, bz) in rects:
        if bx < x0 - 100 or ax > x1 + 100 or bz < z0 - 100 or az > z1 + 100:
            continue
        ddx = np.maximum(np.maximum(ax - cx, cx - bx), 0)
        ddz = np.maximum(np.maximum(az - cz, cz - bz), 0)
        m = np.hypot(ddx, ddz) <= ac
        if m.any() and first is None:
            first = "the box %s" % ((ax, az, bx, bz),)
        near |= m
    for (ax, az, bx, bz) in segs:
        if max(ax, bx) < x0 - 100 or min(ax, bx) > x1 + 100 or max(az, bz) < z0 - 100 or min(az, bz) > z1 + 100:
            continue
        m = seg_dist(cx, cz, ax, az, bx, bz) <= ac
        if m.any() and first is None:
            first = "the polyline piece %s" % ((ax, az, bx, bz),)
        near |= m
    if near.any():
        out.append("authored: %d carved columns within %d of an authored place (first: %s)" % (int(near.sum()), int(ac), first))
    # -- the shell
    shell = rules["shell"]
    water_cov, lava_cov = set(), set()
    pre_post_bad = 0
    for t, (ops, _lines) in tiles.items():
        idx_shell = [i for i, op in enumerate(ops) if op[0] == "fill" and op[3]]
        for op in ops:
            if op[0] == "fill" and op[3] == "minecraft:water":
                water_cov.update(cells_of(op[1]))
            elif op[0] == "fill" and op[3] == "minecraft:lava":
                lava_cov.update(cells_of(op[1]))
        if not idx_shell:
            if any(op[0] == "fill" and base(op[2]) == "minecraft:air" for op in ops):
                pre_post_bad += 1          # carves with no shell round it
            continue
        first_s, last_s = idx_shell[0], idx_shell[-1]
        before, after = set(), set()
        for i, op in enumerate(ops):
            if op[0] == "fill" and op[3] is None and base(op[2]) == "minecraft:air":
                if i < first_s:
                    before.update(cells_of(op[1]))
                elif i > last_s:
                    after.update(cells_of(op[1]))
        if before and not before <= after:
            pre_post_bad += 1          # a shell-only function (a tile the margin reaches into) carves nothing and is fine
    if pre_post_bad:
        out.append("shell: %d function(s) do not carve again after the last water/lava replace" % pre_post_bad)
    dil = set(carved)
    for axis in range(3):
        nxt = set()
        for c in dil:
            for s in range(-shell, shell + 1):
                d = list(c)
                d[axis] += s
                nxt.add(tuple(d))
        dil = nxt
    miss_w = sum(1 for c in dil if c not in water_cov)
    miss_l = sum(1 for c in dil if c not in lava_cov)
    if miss_w or miss_l:
        out.append("shell: %d cells within %d of a carved cell are not covered by a water replace and %d not by a lava replace"
                   % (miss_w, shell, miss_l))
    stats["shell_cells"] = len(dil)
    # -- the walk
    openc = {c for c in carved if base(state[c]) in OPEN_BASES}
    starts = []
    for a in net["adits"]:
        px, pz = a["portal"]
        fy = int(g(px, pz)) + 1
        if (px, fy, pz) not in openc:
            out.append("walk: adit %s: the portal cell (%d, %d, %d) is not open" % (a["id"], px, fy, pz))
        else:
            starts.append((px, fy, pz))
    seen = set(starts)
    stack = list(starts)
    while stack:
        x, y, z = stack.pop()
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            c = (x + d[0], y + d[1], z + d[2])
            if c in openc and c not in seen:
                seen.add(c)
                stack.append(c)
    if len(seen) != len(openc):
        out.append("walk: %d of %d open cells are not reached from an adit" % (len(openc) - len(seen), len(openc)))
    for c, b in state.items():
        bb = base(b)
        if bb == "minecraft:ladder":
            f = facing(b)
            vx, vz = FACES[f]
            behind = (c[0] - vx, c[1], c[2] - vz)
            if behind in openc:
                out.append("walk: ladder at %s faces %s with open air behind it" % (c, f))
            up = (c[0], c[1] + 1, c[2])
            dn = (c[0], c[1] - 1, c[2])
            # a ladder column is whole: open air or ladder above it (its top reaches the drift), ladder or a floor under it
            if not (base(state.get(up, "")) == "minecraft:ladder" or up in openc):
                out.append("walk: ladder at %s ends in rock above (nothing open over it)" % (c,))
            if not (base(state.get(dn, "")) == "minecraft:ladder" or dn not in openc):
                out.append("walk: ladder at %s hangs over open air with no ladder under it" % (c,))
        elif bb.endswith("_stairs"):
            f = facing(b)
            vx, vz = FACES[f]
            x, y, z = c
            up_n = (x + vx, y + 1, z + vz)
            down_n = (x - vx, y - 1, z - vz)
            if (x, y + 1, z) not in openc or (x, y + 2, z) not in openc:
                out.append("walk: stair at %s has no air over it" % (c,))
            if (x, y - 1, z) in openc:
                out.append("walk: stair at %s has an open cell under it" % (c,))
            if (x + vx, y, z + vz) in openc:
                out.append("walk: stair at %s faces %s but the cell uphill of it is open at its own height" % (c, f))
            if not (up_n in openc or base(state.get(up_n, "")).endswith("_stairs")):
                out.append("walk: stair at %s faces %s but nothing rises uphill of it" % (c, f))
        elif bb == "minecraft:rail":
            below = (c[0], c[1] - 1, c[2])
            if base(state.get(below, "")) != "minecraft:cobblestone":
                out.append("walk: rail at %s does not stand on cobblestone" % (c,))
            if (c[0], c[1] + 1, c[2]) not in openc:
                out.append("walk: rail at %s has no air over it" % (c,))
        elif bb == "minecraft:lantern":
            if (c[0], c[1] + 1, c[2]) in openc:
                out.append("walk: lantern at %s hangs from open air" % (c,))
    # -- fittings
    mat = spec["materials"]
    allowed = {"minecraft:air", "minecraft:stone", "minecraft:deepslate", base(mat["bed"]), base(mat["stair"]), base(mat["post"]),
               base(mat["beam"]), base(mat["lantern"]), base(mat["rail"]), base(mat["ladder"])}
    ores = {}
    for o in spec["ores"]["table"]:
        ores[o["stone"]] = ("stone", o["id"])
        ores[o["deepslate"]] = ("deepslate", o["id"])
    kinds = {}
    for c, b in state.items():
        bb = base(b)
        if bb in ores:
            kinds[ores[bb][1]] = kinds.get(ores[bb][1], 0) + 1
            if c in carved:
                out.append("fittings: ore at %s is inside a carved cell" % (c,))
            if ores[bb][0] == "deepslate" and c[1] >= 8:
                out.append("fittings: deepslate ore at %s, over y8" % (c,))
            if ores[bb][0] == "stone" and c[1] < 0:
                out.append("fittings: stone ore at %s, under y0" % (c,))
        elif bb not in allowed:
            out.append("fittings: %s at %s is not a block the data names" % (bb, c))
        if len(out) > 60:
            break
    stats["ore_blocks"] = dict(sorted(kinds.items()))
    # -- the policy
    spawn = set(jload("spawn_blocks.json")["blocks"])
    allowed_spawn = {b for w in jload("spawn_block_policy.json")["whitelist"] if "mine_networks" in (w.get("scope") or "") for b in w["blocks"]}
    placed = {base(b) for b in state.values()}
    for b in sorted((placed & spawn) - allowed_spawn):
        out.append("policy: %s is a spawn condition and no policy entry scoped to mine_networks allows it" % b)
    # -- scale
    percol = {}
    for c in carved:
        percol.setdefault((c[0], c[2]), []).append(c[1])
    crossings = 0                      # tunnel crossings of a column: a contiguous run of carved cells 4 high or less
    for yl in percol.values():
        yl.sort()
        start = prev = yl[0]
        for y in yl[1:] + [None]:
            if y is None or y != prev + 1:
                if prev - start + 1 <= 4:
                    crossings += 1
                if y is not None:
                    start = y
            if y is not None:
                prev = y
    est = crossings / 3.0
    stats["drift_estimate_blocks"] = int(est)
    stats["carved_cells"] = len(carved)
    stats["blocks_written"] = len(state)
    if est < 2000:
        out.append("scale: the independent drift estimate is %d blocks, under 2,000" % est)
    stats["columns"] = cols
    return out, stats


def audit(spec=None, pack=PACK, only=None, source_root=None):
    spec = spec or json.loads(SPEC.read_text(encoding="utf-8"))
    g = G.Ground(source_root)
    problems, allstats, cols_by_net = [], {}, {}
    for net in spec["networks"]:
        if only and net["id"] != only:
            continue
        tiles, probs = read_pack(pack, net["id"])
        problems += ["%s: %s" % (net["id"], p) for p in probs]
        if not tiles:
            problems.append("%s: no functions in %s" % (net["id"], pack))
            continue
        state, carved = replay(tiles)
        out, stats = audit_network(spec, net, tiles, state, carved, g)
        problems += ["%s: %s" % (net["id"], p) for p in out]
        cols_by_net[net["id"]] = np.array(stats.pop("columns", []), np.float64).reshape(-1, 2)
        allstats[net["id"]] = stats
    ids = sorted(cols_by_net)
    gap = spec["rules"]["network_gap"]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            A, B = cols_by_net[a], cols_by_net[b]
            if len(A) and len(B):
                best = min(float(np.min(np.hypot(A[j:j + 2000, None, 0] - B[None, :, 0], A[j:j + 2000, None, 1] - B[None, :, 1])))
                           for j in range(0, len(A), 2000))
                if best < gap:
                    problems.append("scale: networks %s and %s come within %d blocks (gap %d)" % (a, b, best, gap))
    return problems, allstats


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default=str(PACK))
    p.add_argument("--only")
    p.add_argument("--source-root")
    p.add_argument("--inputs-root", help="accepted for tools/reapply.py prepare's sake; the pack under --pack is what is read")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    problems, stats = audit(None, Path(a.pack), a.only, a.source_root)
    for n, s in sorted(stats.items()):
        print("%s: %d carved cells, %d blocks written, drift estimate %d blocks, least cover %s, ore %s" % (
            n, s["carved_cells"], s["blocks_written"], s["drift_estimate_blocks"], s["least_cover"], s["ore_blocks"]))
    for pr in problems[:60]:
        print("PROBLEM:", pr)
    print("%d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
