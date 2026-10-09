#!/usr/bin/env python
"""The Sundown Watch on Sunset Isle, from data/sunset_watch.json: a paved terrace on the isle's western shoulder with a
stone dial, a Sun Gate on the lip, benches facing it, a keeper's lamp house, a lamp mast, wind-bent acacias, and one
waymark sign at the isle's ferry landing.

The owner, 2026-10-09 (relayed): "SUNSET ISLAND: something special. It is empty, and it needs a reason to sail there."
The reason is a TIME, not a creature or a chest: for the dusk window of the clock (ticks 11834-13701, read from the 1.8.0
jar's TimeRange; about 93 seconds of a 20-minute day) an activated Habitat Block in the dial's plinth draws the Dreepy
line, the Dusk-form Lycanroc and, rarely, a Drakloak above the leg's cap; at any other time of day the block has
nothing to offer. Every part is an existing, proven piece; nothing here is new machinery:

  the blocks    vanilla 1.21.1, seated the repository's way (tools/old_orchard.py, tools/lopunny_house.py): the terrace
                at the HIGHEST ground under it with stone-brick foundation to each column's own ground, the hut floor on
                max(ground under its walls) + 1, every post, tree and stair on its own column's ground. Ground from
                tools/ground.py (the canonical heightmap, rounded), never a world.
  the pools     NOT in this pack: two ACTIVATED Habitat Blocks in data/habitat_blocks.json (placed by
                tools/habitat_blocks.py with every other block, R9E), one in the dial's plinth (dusk pool) and one in the
                mast's second log (day pool), on Habitat pools in data/spawns.json with `timeRange` entries
                (tools/compile_spawns.py compile_habitat carries timeRange). This pack writes the plinth and the log, so it
                runs BEFORE R9E.
  the keeper    NOT in this pack: a conversation in data/dialogue.json compiled into cobblers_dialogue, placed by
                tools/reapply.py's "npc" action from npc_placements() (step R18SW, after R17N).
  the find      a cache (data/rewards.json sunset_watch_lamp_store, ADR-002, tools/rewards_pack.py): the pack writes the
                barrel, the cache grants.

  python tools/sunset_watch.py build   [--source-root R] [--out DIR]   write the pack
  python tools/sunset_watch.py plan    [--source-root R]               print the numbers and the steps; writes nothing
  python tools/sunset_watch.py report  [--source-root R]               the same as plan
  python tools/sunset_watch.py records [--write] [--source-root R]     the Habitat Blocks, pools, reward, probes it owns
                                                                       in the shared data files (printed, or replaced)

The re-application: placement_steps() is step R9SW (before R9E); npc_placements() is step R18SW (after R17N).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "sunset_watch.json"
SPAWNS = ROOT / "data" / "spawns.json"
HABITATS = ROOT / "data" / "habitat_blocks.json"
REWARDS = ROOT / "data" / "rewards.json"
PROBES = ROOT / "data" / "world_probes.json"
SPAWN_BLOCKS = ROOT / "data" / "spawn_blocks.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_sunset_watch"
SCHEMA = "cobblers.sunset-watch/1"
NS = "cobblers"
FN = "sunset_watch"
PACK_FORMAT = 48  # Minecraft 1.21.1
LEAVES = "minecraft:acacia_leaves[persistent=true,waterlogged=false]"
CLEAR_TAGS = ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable")
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class WatchError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise WatchError("%s: schema must be %s" % (path, SCHEMA))
    sb = json.loads(SPAWN_BLOCKS.read_text(encoding="utf-8"))["blocks"]
    allowed = set(doc["blocks"].get("spawn_conditions_allowed") or {})
    bad = [b for b in doc["blocks"]["ids"] if b in sb and b not in allowed]
    if bad:
        raise WatchError("blocks.ids holds spawn-condition blocks (data/spawn_blocks.json) the record does not declare: %s"
                         % bad)
    if doc["hut"]["half"] < 2:
        raise WatchError("the hut needs an interior a player can stand in")
    return doc


def _base(state):
    return state.split("[")[0].split("{")[0]


def hash01(x, z, salt=0):
    """A fixed pseudo-random number in [0, 1) for a column: the same column always gives the same number."""
    h = (x * 73856093) ^ (z * 19349663) ^ (salt * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0x1000000)


def sign_text(lines):
    return ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])


def wall_sign(facing, lines):
    return "minecraft:spruce_wall_sign[facing=%s,waterlogged=false]{front_text:{messages:[%s]}}" % (facing, sign_text(lines))


def standing_sign(rotation, lines):
    return "minecraft:spruce_sign[rotation=%d,waterlogged=false]{front_text:{messages:[%s]}}" % (rotation, sign_text(lines))


def stairs(base, facing, half="bottom"):
    return "minecraft:%s_stairs[facing=%s,half=%s,shape=straight,waterlogged=false]" % (base, facing, half)


def wall_state(conn):
    sides = ",".join("%s=%s" % (d, "low" if d in conn else "none") for d in ("east", "north", "south", "west"))
    return "minecraft:stone_brick_wall[%s,up=true,waterlogged=false]" % sides


FENCE = "minecraft:spruce_fence[east=false,west=false,north=false,south=false,waterlogged=false]"


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """Blocks in two passes, {(x, y, z): state}: the structure (bottom up), then what hangs on or stands on it (top
    down): a lantern, a sign, a plant. Doors are their own ordered pairs. A later put of a cell replaces an earlier
    one in either pass."""

    def __init__(self, doc, g):
        self.doc, self.g = doc, g
        self.solid, self.hung, self.doors, self.clears = {}, {}, [], []
        self.allowed = set(doc["blocks"]["ids"])
        self.used = set()          # columns a feature stands on: the foliage keeps off them
        cx, cz = doc["site"]["centre"]
        self.cx, self.cz = cx, cz

    def W(self, lx, lz):
        return self.cx + lx, self.cz + lz

    def _check(self, state):
        if _base(state) not in self.allowed:
            raise WatchError("%s is not in data/sunset_watch.json blocks.ids" % _base(state))

    def put(self, x, y, z, state):
        self._check(state)
        self.hung.pop((x, y, z), None)
        self.solid[(x, y, z)] = state

    def hang(self, x, y, z, state):
        self._check(state)
        self.solid.pop((x, y, z), None)
        self.hung[(x, y, z)] = state

    def door(self, x, y, z, facing, hinge="left"):
        for half, d in (("lower", 0), ("upper", 1)):
            st = "minecraft:spruce_door[facing=%s,half=%s,hinge=%s,open=false,powered=false]" % (facing, half, hinge)
            self._check(st)
            self.solid.pop((x, y + d, z), None)
            self.hung.pop((x, y + d, z), None)
            self.doors.append(((x, y + d, z), st))

    def clear(self, x0, z0, x1, z1, y0, y1, tags=CLEAR_TAGS):
        self.clears.append(((min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1)), tags))

    def blocks(self):
        out = dict(self.solid)
        out.update(self.hung)
        out.update(dict(self.doors))
        return out


# --------------------------------------------------------------------------------------------------------- the terrace
def terrace_level(p):
    """P: the terrace's paved Y, the HIGHEST ground under its footprint."""
    t = p.doc["terrace"]
    return max(p.g(*p.W(a, b)) for a in range(t["lx"][0], t["lx"][1] + 1) for b in range(t["lz"][0], t["lz"][1] + 1))


def dial_block(doc, lx, lz):
    """The dial's block at a terrace cell, or None outside the dial."""
    d = doc["dial"]
    dx, dz = lx - d["centre"][0], lz - d["centre"][1]
    r = math.hypot(dx, dz)
    if r < 0.5:
        return "minecraft:chiseled_stone_bricks"
    if d["ring"][0] <= r <= d["ring"][1]:
        return "minecraft:smooth_stone"
    if r < d["ring"][0]:
        ang = math.degrees(math.atan2(dz, dx)) % 360.0
        step = 360.0 / d["marks"]
        diff = abs(ang - round(ang / step) * step)
        if d["mark_radii"][0] <= r <= d["mark_radii"][1] and math.radians(diff) * r < 0.55:
            return "minecraft:chiseled_stone_bricks"
        return "minecraft:polished_andesite"
    return None


def paving(p, P):
    doc = p.doc
    t = doc["terrace"]
    gate_h = doc["gate"]["height"]
    lo = min(p.g(*p.W(a, b)) for a in range(t["lx"][0], t["lx"][1] + 1) for b in range(t["lz"][0], t["lz"][1] + 1))
    x0, z0 = p.W(t["lx"][0], t["lz"][0])
    x1, z1 = p.W(t["lx"][1], t["lz"][1])
    p.clear(x0, z0, x1, z1, lo + 1, P + max(gate_h, doc["mast"]["height"]) + 6)
    for a in range(t["lx"][0], t["lx"][1] + 1):
        for b in range(t["lz"][0], t["lz"][1] + 1):
            x, z = p.W(a, b)
            p.used.add((x, z))
            for y in range(p.g(x, z) + 1, P):
                p.put(x, y, z, "minecraft:stone_bricks")
            st = dial_block(doc, a, b)
            if st is None:
                h = hash01(x, z, 5)
                st = "minecraft:cracked_stone_bricks" if h < 0.10 else (
                    "minecraft:mossy_stone_bricks" if h < 0.35 else "minecraft:stone_bricks")
            p.put(x, P, z, st)
    for lx0, lz0, lx1, lz1 in t.get("extra_paving", []):
        for a in range(lx0, lx1 + 1):
            for b in range(lz0, lz1 + 1):
                x, z = p.W(a, b)
                if p.g(x, z) > P:
                    raise WatchError("extra paving at %s lies above the terrace's level y%d" % ((x, z), P))
                p.used.add((x, z))
                p.clear(x, z, x, z, p.g(x, z) + 1, P + 4)
                for y in range(p.g(x, z) + 1, P):
                    p.put(x, y, z, "minecraft:stone_bricks")
                p.put(x, P, z, "minecraft:mossy_stone_bricks" if hash01(x, z, 5) < 0.35 else "minecraft:stone_bricks")
    dcx, dcz = p.W(*doc["dial"]["centre"])
    p.put(dcx, P + 1, dcz, "minecraft:chiseled_stone_bricks")        # the plinth: the dusk Habitat Block's mimic


def gate(p, P):
    doc = p.doc
    gt = doc["gate"]
    h = gt["height"]
    for lx in range(gt["lx"][0], gt["lx"][1] + 1):
        for lo, hi in gt["pillar_lz"]:
            for lz in range(lo, hi + 1):
                x, z = p.W(lx, lz)
                for dy in range(1, h + 1):
                    if dy == 1 or dy == h:
                        st = "minecraft:chiseled_stone_bricks"
                    else:
                        st = "minecraft:mossy_stone_bricks" if hash01(x, z, dy) < 0.3 else "minecraft:stone_bricks"
                    p.put(x, P + dy, z, st)
        lo_all = min(a for a, _b in gt["pillar_lz"])
        hi_all = max(b for _a, b in gt["pillar_lz"])
        for lz in range(lo_all, hi_all + 1):
            x, z = p.W(lx, lz)
            p.put(x, P + h + 1, z, "minecraft:stone_bricks")
            p.put(x, P + h + 2, z, "minecraft:stone_brick_slab[type=bottom,waterlogged=false]")
    lx = gt["lx"][1]
    for lz in gt["lantern_lz"]:
        x, z = p.W(lx, lz)
        p.hang(x, P + h, z, "minecraft:chain[axis=y,waterlogged=false]")
        p.hang(x, P + h - 1, z, "minecraft:lantern[hanging=true,waterlogged=false]")


def parapet(p, P):
    doc = p.doc
    pa = doc["parapet"]
    t = doc["terrace"]
    lz0, lz1 = t["lz"]
    gap = set(range(pa["gap_lz"][0], pa["gap_lz"][1] + 1))
    cells = [lz for lz in range(lz0, lz1 + 1) if lz not in gap]
    have = set(cells)
    for lz in cells:
        conn = set()
        if lz - 1 in have:
            conn.add("north")
        if lz + 1 in have:
            conn.add("south")
        x, z = p.W(pa["lx"], lz)
        p.put(x, P + 1, z, wall_state(conn))


def stair_run(p, P):
    """The way down from the lip, through the parapet's gap: stone-brick stairs one lower each column (facing east, up
    towards the terrace) on a foundation to the column's own ground, stopping where the stair meets the ground; then a
    dirt path. Returns [(lx, y of stair)] for the middle row."""
    doc = p.doc
    sr = doc["stair_run"]
    out = []
    k = 0
    while True:
        lx = sr["from_lx"] - k
        y = P - k
        stop = False
        for lz in range(sr["lz"][0], sr["lz"][1] + 1):
            x, z = p.W(lx, lz)
            gg = p.g(x, z)
            if y <= gg:
                stop = True
                break
        if stop or k > 60:
            break
        for lz in range(sr["lz"][0], sr["lz"][1] + 1):
            x, z = p.W(lx, lz)
            gg = p.g(x, z)
            p.used.add((x, z))
            p.clear(x, z, x, z, gg + 1, y + 4)
            for yy in range(gg + 1, y):
                p.put(x, yy, z, "minecraft:stone_bricks")
            p.put(x, y, z, stairs("stone_brick", "east"))
        out.append((lx, y))
        k += 1
    for j in range(sr["path_after"]):
        lx = sr["from_lx"] - k - j
        for lz in range(sr["lz"][0], sr["lz"][1] + 1):
            x, z = p.W(lx, lz)
            y = p.g(x, z)
            p.used.add((x, z))
            p.put(x, y, z, "minecraft:dirt_path" if (lx + lz) % 2 == 0 else "minecraft:grass_block[snowy=false]")
            p.clear(x, z, x, z, y + 1, y + 3, ("#minecraft:replaceable",))
    return out


def benches(p, P):
    b = p.doc["benches"]
    for lx in b["rows_lx"]:
        for lo, hi in b["groups_lz"]:
            for lz in range(lo, hi + 1):
                x, z = p.W(lx, lz)
                p.put(x, P + 1, z, stairs("stone_brick", "east"))


def lantern_post(p, x, y, z):
    """Two spruce fence posts and a standing lantern on them, from y."""
    p.put(x, y, z, FENCE)
    p.put(x, y + 1, z, FENCE)
    p.hang(x, y + 2, z, "minecraft:lantern[hanging=false,waterlogged=false]")


def lamp_posts(p, P):
    doc = p.doc
    t = doc["terrace"]
    for lx, lz in doc["lamp_posts"]["at"]:
        x, z = p.W(lx, lz)
        inside = t["lx"][0] <= lx <= t["lx"][1] and t["lz"][0] <= lz <= t["lz"][1]
        y = (P if inside else p.g(x, z)) + 1
        if not inside:
            p.clear(x, z, x, z, y, y + 3)
        p.used.add((x, z))
        lantern_post(p, x, y, z)


def mast(p, P):
    doc = p.doc
    m = doc["mast"]
    x, z = p.W(*m["at"])
    p.used.add((x, z))
    for dy in range(1, m["height"] + 1):
        p.put(x, P + dy, z, "minecraft:spruce_log[axis=y]")
    ay = P + m["arm_y"]
    for s in (-1, 1):
        for r in range(1, m["arm_reach"] + 1):
            p.put(x + s * r, ay, z, "minecraft:spruce_fence[east=%s,west=%s,north=false,south=false,waterlogged=false]"
                  % ("true" if (s == -1 or r < m["arm_reach"]) else "false",
                     "true" if (s == 1 or r < m["arm_reach"]) else "false"))
        ex = x + s * m["arm_reach"]
        p.hang(ex, ay - 1, z, "minecraft:chain[axis=y,waterlogged=false]")
        p.hang(ex, ay - 2, z, "minecraft:lantern[hanging=true,waterlogged=false]")
    p.hang(x, P + m["height"] + 1, z, "minecraft:lantern[hanging=false,waterlogged=false]")
    return (x, P + 2, z)


# ------------------------------------------------------------------------------------------------------------ the hut
def hut(p, P):
    """The keeper's lamp house. Returns (floor y, ridge y, barrel position, trigger box)."""
    doc = p.doc
    ht = doc["hut"]
    hx, hz = p.W(*ht["centre"])
    h, top, over = ht["half"], ht["wall_height"], ht["roof_overhang"]
    walls = [(hx + a, hz + b) for a in range(-h, h + 1) for b in range(-h, h + 1)]
    hf = max(p.g(x, z) for x, z in walls) + 1
    rise = h + over
    ridge = top + 1 + rise
    p.clear(hx - h - over, hz - h - over, hx + h + over, hz + h + over + 2, hf, hf + ridge + 1)
    for x, z in walls:
        p.used.add((x, z))
    for a in range(-h - 1, h + 2):
        for b in range(-h - 1, h + 3):
            p.used.add((hx + a, hz + b))

    def put(a, dy, b, st):
        p.put(hx + a, hf + dy, hz + b, st)

    def hang(a, dy, b, st):
        p.hang(hx + a, hf + dy, hz + b, st)

    for a in range(-h, h + 1):
        for b in range(-h, h + 1):
            ring = max(abs(a), abs(b)) == h
            put(a, 0, b, "minecraft:stone_bricks" if ring else "minecraft:spruce_planks")
            for y in range(p.g(hx + a, hz + b) + 1, hf):
                p.put(hx + a, y, hz + b, "minecraft:stone_bricks")
            if not ring:
                continue
            corner = abs(a) == h and abs(b) == h
            for dy in range(1, top + 1):
                if dy == 1:
                    put(a, dy, b, "minecraft:mossy_stone_bricks" if hash01(hx + a, hz + b, dy) < 0.3
                        else "minecraft:stone_bricks")
                elif corner:
                    put(a, dy, b, "minecraft:spruce_log[axis=y]")
                else:
                    put(a, dy, b, "minecraft:spruce_planks")
    # windows, and the door in the south wall
    for a in (-2, 2):
        for dy in (2, 3):
            put(a, dy, h, "minecraft:air")
    for a in (-1, 1):
        for dy in (2, 3):
            put(a, dy, -h, "minecraft:air")
    for dy in (2, 3):
        put(-h, dy, 0, "minecraft:air")
        put(h, dy, 0, "minecraft:air")
    put(0, 1, h, "minecraft:air")
    put(0, 2, h, "minecraft:air")
    p.door(hx, hf + 1, hz + h, "north")
    # the roof: a gable whose ridge runs east-west
    for k in range(0, rise + 1):
        dy = top + 1 + k
        r = rise - k
        for a in range(-h - over, h + over + 1):
            if r == 0:
                put(a, dy, 0, "minecraft:spruce_planks")
                continue
            put(a, dy, -r, stairs("spruce", "south"))
            put(a, dy, r, stairs("spruce", "north"))
        for b in range(-(r - 1), r):
            for a in (-h, h):
                put(a, dy, b, "minecraft:spruce_planks")                   # the gable ends
    # the inside: the find, casks, a lectern with no book, a crafting table, a rain cauldron
    ni = h - 1
    put(ni, 1, -ni, "minecraft:barrel[facing=up,open=false]")
    for a in range(-ni, 1):
        put(a, 1, -ni, "minecraft:barrel[facing=south,open=false]")
    for a in (-ni, -ni + 1):
        put(a, 2, -ni, "minecraft:barrel[facing=south,open=false]")
    put(-ni, 1, 0, "minecraft:lectern[facing=east,has_book=false,powered=false]")
    put(-ni, 1, ni, "minecraft:crafting_table")
    put(ni, 1, ni, "minecraft:cauldron")
    for dy in range(ridge - 3, ridge):
        hang(0, dy, 0, "minecraft:chain[axis=y,waterlogged=false]")
    hang(0, ridge - 4, 0, "minecraft:lantern[hanging=true,waterlogged=false]")
    hang(1, 2, h + 1, wall_sign("south", ht["door_sign"]))
    barrel = (hx + ni, hf + 1, hz - ni)
    trigger = {"min": [hx + ni - 1, hf + 1, hz - ni], "max": [hx + ni, hf + 2, hz - ni + 1]}
    return hf, hf + ridge, barrel, trigger


# ------------------------------------------------------------------------------------------- the trees and the margin
def acacia(p, x, z):
    doc = p.doc
    tr = doc["trees"]
    t = tr["trunk"]
    r = tr["crown_radius"]
    y0 = p.g(x, z) + 1
    p.used.add((x, z))
    p.used.add((x + 1, z))
    cols = [(x + a, z + b) for a in range(-r, r + 2) for b in range(-r, r + 1)]
    p.clear(x - r, z - r, x + r + 1, z + r, min(p.g(a, b) for a, b in cols) + 1, y0 + t + 3)
    for dy in range(0, 3):
        p.put(x, y0 + dy, z, "minecraft:acacia_log[axis=y]")
    for dy in range(3, t):
        p.put(x + 1, y0 + dy, z, "minecraft:acacia_log[axis=y]")
    cx_, top = x + 1, y0 + t - 1
    for dy, rr in ((0, r), (1, r - 1)):
        for a in range(-rr, rr + 1):
            for b in range(-rr, rr + 1):
                if abs(a) == rr and abs(b) == rr and rr > 1:
                    continue
                if max(abs(a), abs(b)) == rr and hash01(cx_ + a, z + b, top + dy) < 0.15:
                    continue
                k = (cx_ + a, top + dy, z + b)
                if k in p.solid and _base(p.solid[k]) == "minecraft:acacia_log":
                    continue
                p.put(k[0], k[1], k[2], LEAVES)


def approach(p):
    ap = p.doc["approach"]
    z = p.cz + ap["lz"]
    for lx in range(ap["lx"][0], ap["lx"][1] + 1):
        x = p.cx + lx
        y = p.g(x, z)
        p.used.add((x, z))
        p.put(x, y, z, "minecraft:dirt_path" if lx % 2 == 0 else "minecraft:grass_block[snowy=false]")
        p.clear(x, z, x, z, y + 1, y + 3, ("#minecraft:replaceable",))


def foliage(p):
    doc = p.doc
    f = doc["foliage"]
    x0, z0 = p.W(f["box"][0], f["box"][1])
    x1, z1 = p.W(f["box"][2], f["box"][3])
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if (x, z) in p.used or hash01(x, z, 11) >= f["share"]:
                continue
            y = p.g(x, z)
            if y <= 62:
                continue
            if any(k in p.solid or k in p.hung for k in ((x, y, z), (x, y + 1, z), (x, y + 2, z))):
                continue
            pick, acc = hash01(x, z, 13), 0.0
            for plant, share in f["plants"]:
                acc += share
                if pick < acc:
                    p.put(x, y, z, "minecraft:grass_block[snowy=false]")
                    p.hang(x, y + 1, z, plant)
                    break


def landing_post(p):
    lp = p.doc["landing_post"]
    x, z = lp["at"]
    y = p.g(x, z) + 1
    p.clear(x - 1, z - 1, x + 2, z + 1, y, y + 4)
    for dx in (0, 1):
        p.used.add((x + dx, z))
    p.put(x, y, z, "minecraft:stripped_spruce_log[axis=y]")
    p.hang(x, y + 1, z, standing_sign(8, lp["sign"]))
    if lp.get("lantern"):
        p.put(x + 1, y, z, "minecraft:stripped_spruce_log[axis=y]")
        p.hang(x + 1, y + 1, z, "minecraft:lantern[hanging=false,waterlogged=false]")
    return (x, y + 1, z)


def plan(doc, g):
    p = Plan(doc, g)
    P = terrace_level(p)
    paving(p, P)
    gate(p, P)
    parapet(p, P)
    run = stair_run(p, P)
    benches(p, P)
    lamp_posts(p, P)
    day_block = mast(p, P)
    hf, ridge_y, barrel, trigger = hut(p, P)
    for x, z in doc["trees"]["at"]:
        acacia(p, *p.W(x, z))
    approach(p)
    sign = landing_post(p)
    foliage(p)
    blocks = p.blocks()
    dx, dz = p.W(*doc["dial"]["centre"])
    dusk_block = (dx, P + 1, dz)
    if blocks.get(dusk_block) != doc["dusk"]["mimic"]:
        raise WatchError("the dial's plinth at %s is not %s" % (dusk_block, doc["dusk"]["mimic"]))
    if _base(blocks.get(day_block, "")) != _base(doc["day"]["mimic"]):
        raise WatchError("the mast's second log at %s is not %s" % (day_block, doc["day"]["mimic"]))
    nx, nz = p.W(*doc["npc"]["at"])
    npc = (nx, P + 1, nz)
    for k in (npc, (npc[0], npc[1] + 1, npc[2])):
        if blocks.get(k, "minecraft:air") != "minecraft:air":
            raise WatchError("the keeper's spot %s is not two blocks of air" % (npc,))
    return {"plan": p, "P": P, "hf": hf, "ridge_y": ridge_y, "barrel": barrel, "trigger": trigger, "run": run,
            "dusk_block": dusk_block, "day_block": day_block, "npc": npc, "sign": sign, "blocks": blocks}


# ---------------------------------------------------------------------------------------------------------- the pack
def _runs(blocks, top_down=False):
    """setblock and fill lines for {(x, y, z): state}, one fill per run of one state along x, bottom up (or top down:
    a lantern hangs from a chain that is hung itself, so what hangs is written from the top)."""
    out = []
    keys = sorted(blocks, key=lambda k: (-k[1] if top_down else k[1], k[2], k[0]))
    i = 0
    while i < len(keys):
        x, y, z = keys[i]
        st = blocks[keys[i]]
        j = i
        while (j + 1 < len(keys) and keys[j + 1] == (keys[j][0] + 1, y, z) and blocks[keys[j + 1]] == st
               and "{" not in st):
            j += 1
        if j == i:
            out.append("setblock %d %d %d %s" % (x, y, z, st))
        else:
            out.append("fill %d %d %d %d %d %d %s" % (x, y, z, keys[j][0], y, z, st))
        i = j + 1
    return out


def build_lines(doc, pl):
    p = pl["plan"]
    out = ["# Generated by tools/sunset_watch.py from data/sunset_watch.json. Re-run to rebuild; do not edit.",
           "# The Sundown Watch on Sunset Isle: terrace, dial, Sun Gate, benches, lamp house, mast, acacias, waymark.",
           "# Run BEFORE R9E: the Habitat Blocks sunset_watch_dial_ward and sunset_watch_mast_ward sit in blocks this writes.",
           "# 1. clear trees, leaves and plants over each feature's box"]
    for (x0, y0, z0, x1, y1, z1), tags in p.clears:
        for tag in tags:
            out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the structure, bottom up")
    over = set(p.hung) | {k for k, _st in p.doors}
    out += _runs({k: st for k, st in p.solid.items() if k not in over})
    out.append("# 3. what hangs on it or stands on it, from the top: chains, lanterns, signs, plants")
    out += _runs(p.hung, top_down=True)
    out.append("# 4. the door, lower half then upper")
    out += ["setblock %d %d %d %s" % (k + (st,)) for k, st in p.doors]
    return out


def files(doc, g):
    pl = plan(doc, g)
    lines = function_limits.ensure_loaded(build_lines(doc, pl))
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise WatchError("build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    out = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Sundown Watch on Sunset Isle (tools/sunset_watch.py)"}},
                                  indent=2) + "\n",
        "data/%s/function/%s/build.mcfunction" % (NS, FN): "\n".join(lines) + "\n",
    }
    return out, pl


def hold_boxes(doc):
    out = []
    for bid in ("sunset_watch_all", "sunset_watch_landing_box"):
        b = [x for x in doc["site"]["bounding_boxes"] if x["id"] == bid][0]
        out.append("%d %d %d %d" % (b["min"][0], b["min"][1], b["max"][0], b["max"][1]))
    return out


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, step R9SW BEFORE R9E: hold the chunks, build, release (R9LH's and R9SO's shape)."""
    doc = doc or load()
    holds = hold_boxes(doc)
    return ([("cmd", "forceload add " + h) for h in holds] + [("wait", 3), ("fn", "%s:%s/build" % (NS, FN))]
            + [("cmd", "forceload remove " + h) for h in holds])


def npc_placements(doc=None, g=None):
    """[(conversation id, (x, y, z), npc class)] for tools/reapply.py's "npc" action (step R18SW): the keeper stands on
    the terrace's paved floor + 1."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    conv = next((c for c in dl["conversations"] if c["id"] == doc["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        raise WatchError("%s is not a conversation with an NPC in data/dialogue.json" % doc["npc"]["conversation"])
    p = Plan(doc, g)
    x, z = p.W(*doc["npc"]["at"])
    return [(conv["id"], (x, terrace_level(p) + 1, z), "%s:%s" % (doc["namespace"], conv["npc_id"]))]


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


# ------------------------------------------------------------------------------------------------------- the records
def _display(sp):
    return " ".join(w.capitalize() for w in reversed(sp.split())) if " " in sp else sp.capitalize()


def records(doc, pl, positions=None):
    """(habitat block records, [pool {habitat, entries}], the reward record, the probes) this place owns in the shared
    data files. `positions` is {species: spawnable position}; without it, the position is read from data/spawns.json's
    own copy of the pool, and failing that is grounded (every species here has dry-land spawns in the 1.8.0 jar)."""
    spawns = json.loads(SPAWNS.read_text(encoding="utf-8"))
    rar = spawns["rarity"]
    old = {e["species"]: e.get("spawnable_position") for e in spawns["entries"]}
    habs, pools = [], []
    for key, style_why in (("dusk", "the dial's centre plinth"), ("day", "the lamp mast's second log")):
        d = doc[key]
        pid = d["habitat"]
        lo, hi = d["band"]
        level = "%d-%d" % (lo, hi)
        pos = pl["dusk_block"] if key == "dusk" else pl["day_block"]
        habs.append({
            "id": d["block"],
            "place": "the Sundown Watch on Sunset Isle (data/sunset_watch.json): %s at (%d, %d, %d)" % ((style_why,) + pos),
            "pool": "cobblers:%s" % pid,
            "style": "activated",
            "replace_spawns": False,
            "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
            "mimic": d["mimic"],
            "activated": {"spawn_range": d["spawn_range"], "chance": 1.0, "trigger": "TICK", "cancel_range": -1,
                          "max_spawns_per_activation": d["max_spawns_per_activation"], "max_spawns": d["max_spawns"]},
            "status": "planned",
            "why": "written by tools/sunset_watch.py records --write from the plan (data/sunset_watch.json %s). %s "
                   "ACTIVATED, the orchard's and the den's pattern; cancel_range -1 leaves natural spawning alone. The "
                   "position is %s as the generator seats it (the terrace's paved Y %d from the heightmap), in a block "
                   "that pack writes, so the pack must run BEFORE R9E (R9SW) or it writes the block back over this one."
                   % (key, d["why"], style_why, pl["P"]),
            "mimic_why": "the block the pack writes at that cell (%s), so the Habitat Block is one more of them." % d["mimic"],
        })
        hab_entries, entries = [], []
        for sp, role, why, fam in d["entries"]:
            bucket = rar[role]["bucket"]
            weight = rar[role]["family_weight"]
            lvl = "%d-%d" % tuple(d["above_band"]) if (key == "dusk" and sp == "drakloak") else level
            cond = {"timeRange": d["time_range"]}
            position = (positions or {}).get(sp) or old.get(sp) or "grounded"
            hab_entries.append({"species": _display(sp), "pokemon": sp, "family": fam,
                                "family_priority": role, "ambient": True, "eligibility_reason": why, "level": lvl,
                                "bucket": bucket, "weight": weight, "conditions": cond})
            entries.append({"id": "habitat.%s.%s" % (pid, sp.replace(" ", "_")), "species": sp, "bucket": bucket,
                            "level": lvl, "weight": weight, "ambient": True, "scope": pid, "mechanism": "habitat_block",
                            "conditions": cond, "eligibility_reason": why, "spawnable_position": position})
        habitat = {"id": pid, "display_name": "the Sundown Watch, %s" % key,
                   "intended_location": "the Sundown Watch on Sunset Isle (data/sunset_watch.json): one activated Habitat "
                                        "Block, %s in data/habitat_blocks.json, in %s at (%d, %d, %d), keeping up to %d "
                                        "alive within %d" % (d["block"], style_why, pos[0], pos[1], pos[2], d["max_spawns"],
                                                             d["spawn_range"]),
                   "mechanism": "habitat_block", "replace_spawns": False,
                   "level_band": {"minimum": lo, "maximum": hi},
                   "level_band_why": "the band of sunset_west (data/spawns.json subregions: 28-38, tier 5, basis "
                                     "route_05_erika_to_koga, cap 40), the sub-region the Watch stands in "
                                     "(data/regions.json polygons)." + (
                                         " The one entry above it, Drakloak at %d-%d, is the place's nest: the creature the "
                                         "place is for, strong enough that meeting it early is a mistake (5-8 over the "
                                         "cap); rare, so a visit is mostly Dreepy." % tuple(d["above_band"])
                                         if key == "dusk" else ""),
                   "why": d["why"], "entries": hab_entries,
                   "placement_status": "authored: data/habitat_blocks.json %s, status planned" % d["block"]}
        pools.append({"habitat": habitat, "entries": entries})
    f = doc["find"]
    reward = {"id": f["reward"], "kind": "cache",
              "place": "the Sundown Watch on Sunset Isle (data/sunset_watch.json): the guild's store barrel in the lamp "
                       "house's north-east corner",
              "contents": [{"item": it, "count": n,
                            "verification": "assets/cobblemon/models/item/%s.json in Cobblemon-fabric-1.8.0+1.21.1.jar"
                                            % it.split(":", 1)[1]} for it, n in f["contents"]],
              "message": f["message"], "why": f["why"],
              "built_by": "tools/sunset_watch.py (the barrel, in cobblers_sunset_watch's build, reapply step R9SW)",
              "trigger": pl["trigger"],
              "container": {"block": "minecraft:barrel", "at": list(pl["barrel"])}}
    return habs, pools, reward, probes(doc, pl)


def probes(doc, pl):
    """data/world_probes.json places.sunset_watch: presence checks read back over RCON by tools/presence_audit.py."""
    p = pl["plan"]
    P = pl["P"]
    out = []

    def blk(what, x, y, z, state):
        out.append({"what": what, "block": [x, y, z, state], "expect": True})
    dx, dz = p.W(*doc["dial"]["centre"])
    rx, rz = p.W(doc["dial"]["centre"][0] + 8, doc["dial"]["centre"][1])
    blk("the dial's smooth-stone ring", rx, P, rz, "minecraft:smooth_stone")
    blk("the dial's plinth (the dusk Habitat Block's mimic)", dx, P + 1, dz, "minecraft:chiseled_stone_bricks")
    gx, gz = p.W(doc["gate"]["lx"][0], doc["gate"]["pillar_lz"][0][0])
    blk("the Sun Gate's north pillar, foot", gx, P + 1, gz, "minecraft:chiseled_stone_bricks")
    gx2, gz2 = p.W(doc["gate"]["lx"][0], doc["gate"]["pillar_lz"][1][0])
    blk("the Sun Gate's other pillar, foot", gx2, P + 1, gz2, "minecraft:chiseled_stone_bricks")
    lx, lz = p.W(doc["gate"]["lx"][0], 0)
    blk("the Sun Gate's lintel", lx, P + doc["gate"]["height"] + 1, lz, "minecraft:stone_bricks")
    bx, bz = p.W(doc["benches"]["rows_lx"][0], doc["benches"]["groups_lz"][0][0])
    blk("a bench (stone-brick stairs)", bx, P + 1, bz, "minecraft:stone_brick_stairs[facing=east]")
    mx, mz = p.W(*doc["mast"]["at"])
    blk("the lamp mast's foot", mx, P + 1, mz, "minecraft:spruce_log")
    blk("the lamp mast's crown lantern", mx, P + doc["mast"]["height"] + 1, mz, "minecraft:lantern")
    hx, hz = p.W(*doc["hut"]["centre"])
    blk("the lamp house's floor", hx, pl["hf"], hz, "minecraft:spruce_planks")
    blk("the lamp house's door (lower)", hx, pl["hf"] + 1, hz + doc["hut"]["half"], "minecraft:spruce_door[half=lower]")
    blk("the lamp house's door (upper)", hx, pl["hf"] + 2, hz + doc["hut"]["half"], "minecraft:spruce_door[half=upper]")
    blk("the find's barrel", *pl["barrel"], "minecraft:barrel")
    blk("the lamp house's ridge", hx, pl["ridge_y"], hz, "minecraft:spruce_planks")
    sx, sy, sz = pl["sign"]
    blk("the waymark sign at the isle's landing", sx, sy, sz, "minecraft:spruce_sign")
    nx, ny, nz = pl["npc"]
    out.append({"what": "the keeper", "entity": "@e[type=cobblemon:npc,x=%d,y=%d,z=%d,distance=..2]" % (nx, ny, nz),
                "count": 1, "hold": [nx, ny, nz]})
    return out


def jar_positions(doc):
    """{species: spawnable position} from the Cobblemon jar's own spawn files (tools/position_types.py choose())."""
    import battle_sim
    import position_types as PT
    up = PT.upstream_positions(battle_sim.find_jar())
    return {row[0]: PT.choose(row[0], up)[0] for k in ("dusk", "day") for row in doc[k]["entries"]}


def _dump(path, d):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")


def _replace_record_text(path, array_key, record):
    """Put `record` into the array `array_key` of a hand-formatted JSON file as text (a re-dump would rewrite every
    record): replacing the one with its id if there is one, appending to the end of the array if not."""
    text = path.read_text(encoding="utf-8")
    want = json.loads(text)
    want[array_key] = [r for r in want[array_key] if r.get("id") != record["id"]] + [record]
    rec = "\n".join("    " + ln for ln in json.dumps(record, indent=2, ensure_ascii=False).splitlines())
    lines = text.split("\n")
    key = '      "id": "%s",' % record["id"]
    if key in lines:
        i = lines.index(key) - 1
        j = i
        while lines[j] not in ("    },", "    }"):
            j += 1
        comma = "," if lines[j].endswith(",") else ""
        lines[i:j + 1] = (rec + comma).split("\n")
        text = "\n".join(lines)
    else:
        end = text.rindex("\n  ]\n}")
        text = text[:end] + ",\n" + rec + text[end:]
    if json.loads(text) != want:
        raise WatchError("%s: the text insertion does not parse to the intended records" % path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_records(habs, pools, reward, probe_list):
    hd = json.loads(HABITATS.read_text(encoding="utf-8"))
    ids = {h["id"] for h in habs}
    hd["blocks"] = [b for b in hd["blocks"] if b.get("id") not in ids] + habs
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    for pool in pools:
        pid = pool["habitat"]["id"]
        sd["habitats"] = [h for h in sd["habitats"] if h.get("id") != pid] + [pool["habitat"]]
        sd["entries"] = [e for e in sd["entries"] if e.get("scope") != pid] + pool["entries"]
    _dump(HABITATS, hd)
    _dump(SPAWNS, sd)
    _replace_record_text(REWARDS, "rewards", reward)
    wp = json.loads(PROBES.read_text(encoding="utf-8"))
    wp["places"]["sunset_watch"] = probe_list
    _dump(PROBES, wp)


# ---------------------------------------------------------------------------------------------------------- the CLI
def sightline(g, a, b, step=2.0):
    """The least height of the straight line from a (x, y, z) to b over the heightmap ground, its ends excluded."""
    (x0, y0, z0), (x1, y1, z1) = a, b
    d = math.hypot(x1 - x0, z1 - z0)
    n = max(2, int(d / step))
    worst = None
    for i in range(1, n):
        t = i / n
        x, z = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
        c = y0 + (y1 - y0) * t - max(g(int(round(x)), int(round(z))), 62)
        worst = c if worst is None else min(worst, c)
    return worst, round(d)


def report(doc, pl, g):
    b = pl["blocks"]
    p = pl["plan"]
    xs = [k[0] for k in b]
    zs = [k[2] for k in b]
    ys = [k[1] for k in b]
    t = doc["terrace"]
    cols = [p.g(*p.W(a, c)) for a in range(t["lx"][0], t["lx"][1] + 1) for c in range(t["lz"][0], t["lz"][1] + 1)]
    land = json.loads((ROOT / "data" / "ferries.json").read_text(encoding="utf-8"))
    dock = [d for d in land["docks"] if d["id"] == "sunset_isle_landing"][0]
    lx, ly, lz = dock["landing"]["at"]
    cx, cz = doc["site"]["centre"]
    mast_top = (p.W(*doc["mast"]["at"])[0], pl["P"] + doc["mast"]["height"] + 1, p.W(*doc["mast"]["at"])[1])
    sea = sightline(g, (cx - 550, 65.6, cz), mast_top)
    hx, hz = p.W(*doc["hut"]["centre"])
    return ["terrace paved y%d (highest ground under it); ground y%d-y%d (range %d); hut floor y%d, ridge y%d; "
            "barrel %s, trigger %s" % (pl["P"], min(cols), max(cols), max(cols) - min(cols), pl["hf"], pl["ridge_y"],
                                       pl["barrel"], json.dumps(pl["trigger"])),
            "stair run: %d columns, from lx %d y%d down to y%d" % (len(pl["run"]), pl["run"][0][0], pl["run"][0][1],
                                                                    pl["run"][-1][1]) if pl["run"] else "stair run: none",
            "blocks written: %d (air %d); writes x%d..%d y%d..%d z%d..%d; clears %d"
            % (len(b), sum(1 for s in b.values() if s == "minecraft:air"), min(xs), max(xs), min(ys), max(ys),
               min(zs), max(zs), len(p.clears)),
            "dusk Habitat Block %s (plinth); day Habitat Block %s (mast second log); keeper stands at %s; waymark sign %s"
            % (pl["dusk_block"], pl["day_block"], pl["npc"], pl["sign"]),
            "from the isle's landing (%d, %d, %d) to the terrace's centre: %.0f blocks straight; to the hut %.0f"
            % (lx, ly, lz, math.hypot(cx - lx, cz - lz), math.hypot(hx - lx, hz - lz)),
            "from a boat's eye (y65.6) 550 blocks west of the terrace's centre to the mast crown %s: least clearance over the ground %.1f over %d blocks"
            % (mast_top, sea[0], sea[1]),
            "steps R9SW (before R9E): %s" % json.dumps([list(s) for s in placement_steps(doc)]),
            "step R18SW (after R17N): %s" % json.dumps([[n[0], list(n[1]), n[2]] for n in npc_placements(doc, g)])]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", choices=("build", "plan", "report", "records"), default="plan")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--write", action="store_true", help="records: replace this place's records in the shared files")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.cmd == "records":
        pl = plan(doc, g)
        habs, pools, reward, probe_list = records(doc, pl, jar_positions(doc))
        if a.write:
            write_records(habs, pools, reward, probe_list)
            print("sunset_watch: wrote %d habitat blocks, %d pools with %d entries, 1 reward, %d probes"
                  % (len(habs), len(pools), sum(len(x["entries"]) for x in pools), len(probe_list)))
        else:
            print(json.dumps({"habitat_blocks": habs, "pools": pools, "reward": reward, "probes": probe_list}, indent=1))
        return 0
    out_files, pl = files(doc, g)
    if a.cmd in ("plan", "report"):
        print("\n".join(report(doc, pl, g)))
        return 0
    write(out_files, a.out)
    n = sum(1 for l in out_files["data/%s/function/%s/build.mcfunction" % (NS, FN)].splitlines()
            if l and not l.startswith("#"))
    print("sunset_watch: %d files -> %s (build: %d commands)" % (len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
