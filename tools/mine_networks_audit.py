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
 11  nests      (2026-10-23) 1 or 2 nest rooms a network: each one activated Habitat Block record (`mine_nest_` ids) in the floor
                cell under the record's centre, mimicking the floor's rock; 12 to 20 across by its radii; every column of the room
                open three high and holding only air; no carved cell within 3 of it but the room and its spur (a dead end);
                nothing but the room in the spawner's box; reached from an adit; its pool's levels inside the band of the
                sub-region it stands in. These blocks' own (x, z) are the only points excused from step 5
 12  live       (2026-10-23) the cells of the pass-1 carve sections (up to the next section marker, so the nest rooms' section is
                not in them) are data's live_carve (count and sha256), and every one is in the replayed carved volume

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
# entrance_trails.json, fishing_fill.json and underground_spawns.json (2026-10-22) are not places to keep clear:
# the trails END at the mouths by design, the fill is water cells, the pools are the caves' own boxes
SKIP_FILES = {"mine_networks.json", "mine_crew_trainers.json", "world.json", "regions.json", "cells.json", "entrance_trails.json", "fishing_fill.json", "underground_spawns.json"}
NEST_PREFIX = "mine_nest_"
NESTS = (1, 2)                 # the brief: 1 to 2 nest rooms a network
ROOM_ACROSS = (12, 20)         # the brief: a room 12 to 20 across


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
    # the networks' own nest-room Habitat Blocks stand in the floor of rooms this pack carves: their exact (x, z) are not an
    # authored place here (step 11 proves each is where a room is); nothing else is excused
    own = {(b["position"]["x"], b["position"]["z"]) for b in nest_blocks()}
    return sorted(p for p in pts if p not in own), sorted(rects), sorted(segs)


def nest_blocks():
    return [b for b in jload("habitat_blocks.json")["blocks"] if str(b.get("id", "")).startswith(NEST_PREFIX)]


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


# ------------------------------------------------------------------ 11 and 12: the 2026-10-23 nest rooms, the live carve

def band_at(x, z):
    """(sub-region, min, max) of a point, from data/regions.json polygons and data/spawns.json bands, read here for itself."""
    sp = {s["id"]: s for s in jload("spawns.json")["subregions"]}
    for r in jload("regions.json")["subregions"]:
        if r["id"] in sp and any(in_ring(np.array([float(x)]), np.array([float(z)]), poly)[0] for poly in r["polygons"]):
            b = sp[r["id"]]["level_band"]
            return r["id"], int(b["minimum"]), int(b["maximum"])
    return None, None, None


def check_nests(spec, net, state, carved, openc, seen, stats):
    """Each recorded room: its Habitat Block in the floor under the middle, the room's shape open as declared, nothing carved within
    3 of it but its own spur (a dead end), nothing else in the spawner's box, reached from an adit, its pool in its sub-region's band."""
    out = []
    rooms = net.get("nest_rooms") or []
    if not NESTS[0] <= len(rooms) <= NESTS[1]:
        out.append("nests: %d rooms (%d to %d wanted)" % (len(rooms), NESTS[0], NESTS[1]))
    blocks = {b["id"]: b for b in jload("habitat_blocks.json")["blocks"]}
    mine = [b for b in blocks.values() if str(b["id"]).startswith(NEST_PREFIX + net["id"] + "_")]
    if len(mine) != len(rooms):
        out.append("nests: %d Habitat Blocks for %d rooms" % (len(mine), len(rooms)))
    habs = {h["id"]: h for h in jload("spawns.json")["habitats"]}
    stats["nest_rooms"] = []
    for r in rooms:
        rid = r["id"]
        b = blocks.get(rid + "_block")
        if b is None:
            out.append("nest %s: no Habitat Block record" % rid)
            continue
        bx, by, bz = (b["position"][k] for k in "xyz")
        cx, yf, cz = r["centre"]
        a, bb = r["radius"]
        dx, dz = r["d"]
        px, pz = -dz, dx
        ex, ez = r["end"]
        tall, sh, ls = int(r["tall"]), int(r["spur_height"]), int(r["spur_len"])
        msgs = []
        if (bx, by, bz) != (cx, yf - 1, cz):
            msgs.append("the block %s is not the floor cell under the room's middle" % ((bx, by, bz),))
        if b.get("style") != "activated" or b.get("mimic") != ("minecraft:deepslate" if by < 0 else "minecraft:stone"):
            msgs.append("not an activated block mimicking the floor's rock")
        if (bx, by, bz) in carved or (bx, by + 1, bz) not in openc or (bx, by + 2, bz) not in openc:
            msgs.append("the block is not a rock cell under two open cells")
        if base(state.get((bx, by, bz), "rock")) != "rock":
            msgs.append("the pack writes %s at the block" % state[(bx, by, bz)])
        if 2 * min(a, bb) < ROOM_ACROSS[0] or 2 * max(a, bb) > ROOM_ACROSS[1]:
            msgs.append("%s by %s across, not %d to %d" % (2 * a, 2 * bb, ROOM_ACROSS[0], ROOM_ACROSS[1]))

        def uv(x, z):
            return (x - cx) * dx + (z - cz) * dz, (x - cx) * px + (z - cz) * pz

        def rho(x, z):
            u, v = uv(x, z)
            return math.sqrt((u / a) ** 2 + (v / bb) ** 2)

        def in_spur(x, z):
            s = (x - ex) * dx + (z - ez) * dz
            l = (x - ex) * px + (z - ez) * pz
            return 1 <= s <= ls + 2 and -1 <= l <= 1

        def own(x, y, z):
            return (yf <= y < yf + tall and rho(x, z) < 1) or (yf <= y < yf + sh and in_spur(x, z))
        R = int(math.ceil(max(a, bb))) + 4
        near = [(x, y, z) for x in range(cx - R, cx + R + 1) for z in range(cz - R, cz + R + 1) for y in range(yf - 4, yf + tall + 4)
                if (x, y, z) in carved]
        lim = 1 + 3.0 / max(a, bb)
        foreign = [c for c in near if not own(*c) and yf - 3 <= c[1] <= yf + 5 and rho(c[0], c[2]) <= lim]
        if foreign:
            msgs.append("%d carved cells within 3 of the room are neither room nor spur (first %s)" % (len(foreign), foreign[0]))
        miss = [(x, z) for x in range(cx - R, cx + R + 1) for z in range(cz - R, cz + R + 1)
                if rho(x, z) < 1 and not all((x, yf + k, z) in openc for k in range(3))]
        if miss:
            msgs.append("%d columns of the room are not open three high (first %s)" % (len(miss), miss[0]))
        fitted = [c for c in near if own(*c) and base(state.get(c, "")) != "minecraft:air"]
        if fitted:
            msgs.append("%d cells of the room or spur hold %s" % (len(fitted), state[fitted[0]]))
        sr = int(b["activated"]["spawn_range"])
        boxed = [c for c in near if abs(c[0] - bx) <= sr and abs(c[1] - by) <= sr and abs(c[2] - bz) <= sr and not own(*c)]
        if boxed:
            msgs.append("the spawn box (spawn_range %d) holds %d carved cells outside the room" % (sr, len(boxed)))
        if (bx, by + 1, bz) not in seen:
            msgs.append("the room's middle is not reached from an adit")
        sub, lo, hi = band_at(bx, bz)
        h = habs.get(str(b["pool"]).split(":", 1)[-1])
        if h is None or not h.get("entries"):
            msgs.append("pool %s missing or empty" % b["pool"])
        else:
            for e in h["entries"]:
                lv = [int(q) for q in str(e["level"]).split("-")]
                if lo is None or min(lv) < lo or max(lv) > hi:
                    msgs.append("%s at %s is outside the band of %s (%s-%s)" % (e["pokemon"], e["level"], sub, lo, hi))
        out += ["nest %s: %s" % (rid, q) for q in msgs]
        stats["nest_rooms"].append({"id": rid, "block": [bx, by, bz], "subregion": sub, "band": [lo, hi],
                                    "species": ["%s %s" % (e["pokemon"], e["level"]) for e in (h or {}).get("entries", [])]})
    return out


def check_live(spec, net, tiles, carved, stats):
    """The live 2026-10-22 carve: the cells of every pass-1 carve section (up to the next section marker, so the nest rooms' section
    is not in it) must be the data's live_carve, and every one of them must be in the replayed carved volume."""
    rec = ((spec.get("live_carve") or {}).get("networks") or {}).get(net["id"])
    if not rec:
        return ["live: data/mine_networks.json live_carve has no record for this network"]
    cells = set()
    for t, (_ops, lines) in tiles.items():
        on = False
        for raw in lines:
            s = raw.strip()
            if s.startswith("# ---"):
                on = s.startswith("# --- pass 1: carve")
                continue
            if not on:
                continue
            m = FILL.match(s)
            if m and base(m.group(7)) == "minecraft:air" and m.group(8) is None:
                v = [int(q) for q in m.groups()[:6]]
                cells.update(cells_of((min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]), max(v[2], v[5]))))
            m = SET.match(s)
            if m and base(m.group(4)) == "minecraft:air":
                cells.add(tuple(int(q) for q in m.groups()[:3]))
    import hashlib
    a = np.array(sorted(cells), np.int64).reshape(-1, 3)
    dg = hashlib.sha256(np.ascontiguousarray(a).astype("<i4").tobytes()).hexdigest()
    stats["live_cells"] = len(a)
    stats["added_cells"] = len(carved - cells)
    out = []
    if len(a) != rec["cells"] or dg != rec["sha256"]:
        out.append("live: the pass-1 carve writes %d cells (sha256 %s...), not the live carve's %d (%s...)" % (len(a), dg[:12], rec["cells"], rec["sha256"][:12]))
    lost = cells - carved
    if lost:
        out.append("live: %d live cells are not in the replayed carved volume" % len(lost))
    return out


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
    # -- 11 nest rooms and 12 the live carve
    out += check_nests(spec, net, state, carved, openc, seen, stats)
    out += check_live(spec, net, tiles, carved, stats)
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


# ------------------------------------------------------------------ 13: the ore that goes into the rock (2026-10-23)

ORE_FILTER = "#minecraft:base_stone_overworld"
ORE_REACH = 8          # within 8 (Chebyshev) of a carved cell; the generator keeps 7 (Euclid) of a wall cell
ORE_WATER = 3          # and a column at least 3 from the sea or a lake (the carve keeps 12)


def read_layer(pack, net_id):
    """{(tx, tz): ops} of the network's `<net>_o_<tx>_<tz>` functions (veins and hidden ore), each op like read_pack's."""
    d = Path(pack) / "data" / "cobblers" / "function" / "mine_networks"
    out, problems = {}, []
    for f in sorted(d.glob("%s_o_*_*.mcfunction" % net_id)):
        t = tuple(int(v) for v in f.stem[len(net_id) + 3:].split("_"))
        lines = f.read_text(encoding="utf-8").splitlines()
        for n, cmd, why in FL.check_lines(lines, str(f)):
            problems.append("limits: %s line %d: %s" % (f.name, n, why))
        ops = []
        for ln, raw in enumerate(lines, start=1):
            s = raw.strip()
            if not s or s.startswith("#") or s.startswith("forceload "):
                continue
            m = FILL.match(s)
            if m:
                v = [int(x) for x in m.groups()[:6]]
                ops.append(("fill", (v[0], v[1], v[2], v[3], v[4], v[5]), m.group(7), m.group(8), ln))
            else:
                problems.append("layer: %s line %d is not a fill: %s" % (f.name, ln, s[:70]))
        out[t] = ops
    return out, problems


def check_layer(spec, net, layer, state, carved, g):
    """Every ore of the layer, read from the BUILT functions with this audit's own derivation: one cell, a spec ore, written with the
    rock-only filter, not in the carved volume, not on a cell the carve functions wrote (a fitting or a base ore), not on a nest
    room's Habitat Block, deepslate only under y8 and stone only from y0, under cover_min of ground, west of x_min is not allowed,
    within ORE_REACH of a carved cell and ORE_WATER of no sea or lake column. Returns (problems, stats)."""
    out, rows = [], []
    rules = spec["rules"]
    types = {}
    for o in spec["ores"]["table"]:
        types[o["stone"]] = ("stone", o["id"])
        types[o["deepslate"]] = ("deepslate", o["id"])
    rooms = {tuple(r["block"]) for r in (net.get("nest_rooms") or [])}
    seen = set()
    per_tile = {}
    for t, ops in sorted(layer.items()):
        for op in ops:
            b, blk, flt = op[1], base(op[2]), op[3]
            if b[0:3] != b[3:6]:
                out.append("layer: tile %s has a fill that is not one cell: %s" % (t, b))
                continue
            c = (b[0], b[1], b[2])
            if flt != ORE_FILTER:
                out.append("layer: ore %s at %s is written with filter %r, not %s (it could replace air, water, a fitting or another ore)" % (blk, c, flt, ORE_FILTER))
            if blk not in types:
                out.append("layer: %s at %s is not an ore of the spec" % (blk, c))
                continue
            kind = types[blk][0]
            if (kind == "deepslate" and c[1] >= 8) or (kind == "stone" and c[1] < 0):
                out.append("layer: %s at %s is the wrong variant for its height" % (blk, c))
            if c in carved:
                out.append("layer: ore %s at %s is inside a carved cell" % (blk, c))
            if c in state:
                out.append("layer: ore %s at %s is on a cell the carve functions wrote (a fitting or a base ore)" % (blk, c))
            if c in rooms:
                out.append("layer: ore %s at %s is on a nest room's Habitat Block" % (blk, c))
            if c in seen:
                out.append("layer: ore at %s is written twice" % (c,))
            if c[0] < rules["x_min"]:
                out.append("layer: ore at %s is west of x_min" % (c,))
            seen.add(c)
            rows.append((c, types[blk][1]))
            per_tile.setdefault(t, []).append(c)
    if not rows:
        return out, {"cells": 0}
    xs = np.array([r[0][0] for r in rows])
    zs = np.array([r[0][2] for r in rows])
    ys = np.array([r[0][1] for r in rows])
    x0, x1, z0, z1 = int(xs.min()) - 8, int(xs.max()) + 8, int(zs.min()) - 8, int(zs.max()) + 8
    H = g.box(x0, z0, x1, z1).astype(np.int32)
    cov = H[zs - z0, xs - x0] - ys
    low = cov < rules["cover_min"]
    if low.any():
        i = int(np.argmax(low))
        out.append("layer: %d ore cells have under %d of ground over them (first %s: %d)" % (int(low.sum()), rules["cover_min"], rows[i][0], int(cov[i])))
    # reach, tile by tile
    C = np.array(sorted(carved), np.int64)
    T = 128
    halo = ORE_REACH
    for (tx, tz), cs in sorted(per_tile.items()):
        ax, az = tx * T, tz * T
        sel = (C[:, 0] >= ax - halo) & (C[:, 0] < ax + T + halo) & (C[:, 2] >= az - halo) & (C[:, 2] < az + T + halo)
        if not sel.any():
            out.append("layer: tile %d,%d has ore and no carved cell within %d" % (tx, tz, halo))
            continue
        S = C[sel]
        oy = int(S[:, 1].min()) - halo
        ny = int(S[:, 1].max()) + halo - oy + 1
        arr = np.zeros((ny, T + 2 * halo, T + 2 * halo), bool)
        arr[S[:, 1] - oy, S[:, 2] - (az - halo), S[:, 0] - (ax - halo)] = True
        reach = arr
        for axis in (0, 1, 2):
            acc = reach.copy()
            for s_ in range(1, ORE_REACH + 1):
                a = [slice(None)] * 3
                b_ = [slice(None)] * 3
                a[axis] = slice(s_, None)
                b_[axis] = slice(None, -s_)
                acc[tuple(a)] |= reach[tuple(b_)]
                acc[tuple(b_)] |= reach[tuple(a)]
            reach = acc
        reach = reach[:, halo:halo + T, halo:halo + T]
        far = sum(1 for (x, y, z) in cs if not (0 <= y - oy < ny and reach[y - oy, z - az, x - ax]))
        if far:
            out.append("layer: tile %d,%d has %d ore cells more than %d from any carved cell" % (tx, tz, far, ORE_REACH))
    # water: the sea and the lake basins, within ORE_WATER of an ore column
    cols = sorted({(r[0][0], r[0][2]) for r in rows})
    cx = np.array([c[0] for c in cols], np.float64)
    cz = np.array([c[1] for c in cols], np.float64)
    sea_level = int(jload("world.json")["vertical"]["sea_level"])
    sea = H <= sea_level
    hit = np.zeros(len(cols), bool)
    for dx in range(-ORE_WATER, ORE_WATER + 1):
        for dz in range(-ORE_WATER, ORE_WATER + 1):
            if dx * dx + dz * dz <= ORE_WATER * ORE_WATER:
                hit |= sea[(cz + dz - z0).astype(int), (cx + dx - x0).astype(int)]
    if hit.any():
        out.append("layer: %d ore columns within %d of the sea" % (int(hit.sum()), ORE_WATER))
    for l in jload("landmarks.json")["landmarks"]:
        for ring in (l.get("water_body") or {}).get("basin_polygons") or []:
            rx = [q[0] for q in ring]
            rz = [q[1] for q in ring]
            if max(rx) < x0 or min(rx) > x1 or max(rz) < z0 or min(rz) > z1:
                continue
            bad = in_ring(cx, cz, ring)
            for a, b_ in zip(ring, ring[1:] + ring[:1]):
                bad |= seg_dist(cx, cz, a[0], a[1], b_[0], b_[1]) <= ORE_WATER
            if bad.any():
                out.append("layer: %d ore columns in or within %d of lake %s" % (int(bad.sum()), ORE_WATER, l["id"]))
    # the report: exposed (a carved cell beside it) against hidden, by ore
    ex = 0
    by = {}
    for (c, tid) in rows:
        e_ = any((c[0] + d[0], c[1] + d[1], c[2] + d[2]) in carved for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))
        ex += e_
        d = by.setdefault(tid, [0, 0])
        d[0 if e_ else 1] += 1
    return out, {"cells": len(rows), "exposed": ex, "hidden": len(rows) - ex, "by_ore_exposed_hidden": by}


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
        layer, lprobs = read_layer(pack, net["id"])
        problems += ["%s: %s" % (net["id"], p) for p in lprobs]
        lout, lstats = check_layer(spec, net, layer, state, carved, g)
        problems += ["%s: %s" % (net["id"], p) for p in lout[:8]]
        if len(lout) > 8:
            problems.append("%s: layer: %d ore-layer problems in all" % (net["id"], len(lout)))
        stats["ore_layer"] = lstats
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
