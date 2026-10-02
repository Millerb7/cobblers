#!/usr/bin/env python
"""The Old Orchard on Sunset Isle, from data/old_orchard.json: the rows round the Orchard Sleeper, the press-house with
its collapsed roof and its cellar, the kitchen garden, the hives, the racks and the lantern posts.

The owner, 2026-10-02 (relayed): "the south needs places, not just creatures. Somewhere to find, something in it."
Built round Codex's resident orchard_sleeper (data/resident_encounters.json, a Slaking at (2816, 7080)); this pack
writes nothing within data/old_orchard.json resident.no_write_within of its anchor and never its ground. Every part
is an existing, proven piece; nothing here is new machinery:

  the blocks    vanilla 1.21.1, seated the repository's way (tools/lopunny_house.py, tools/shrines.py): a tree on its
                own column's ground + 1, the press-house floor on max(ground under its walls) + 1, every wall column,
                stand and post on its own ground + 1. Ground from tools/ground.py (the canonical heightmap, rounded),
                never a world. Trees, leaves and plants are cleared over each feature's box first.
  the cellar    a 7 by 7 room, 3 high, under the press-house floor, reached only by a ladder from a trapdoor; every
                block of it written, solid or air, with `under_fill` rows of stone under its floor. The find's barrel
                is scenery (data/rewards.json old_orchard_cellar, a cache: ADR-002, tools/rewards_pack.py).
  Applin        NOT in this pack: an ACTIVATED Habitat Block in data/habitat_blocks.json (placed by
                tools/habitat_blocks.py with every other block, R9E) in the trunk of one living tree, disguised as its
                log, on a Habitat pool in data/spawns.json. This pack writes that trunk, so it runs BEFORE R9E.
  the keeper    NOT in this pack: a conversation in data/dialogue.json compiled into cobblers_dialogue, placed by
                tools/reapply.py's "npc" action from npc_placements() (step R18SO, after R17N), as the den's watcher is.

  python tools/old_orchard.py build [--source-root R] [--out DIR]   write the pack
  python tools/old_orchard.py plan  [--source-root R]               print the numbers and the steps; writes nothing
  python tools/old_orchard.py --report [--source-root R]            the same as plan

The re-application: placement_steps() is step R9SO (before R9E); npc_placements() is step R18SO (after R17N).
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

DATA = ROOT / "data" / "old_orchard.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_old_orchard"
SCHEMA = "cobblers.old-orchard/1"
NS = "cobblers"
FN = "old_orchard"
PACK_FORMAT = 48  # Minecraft 1.21.1
LEAVES = "minecraft:oak_leaves[persistent=true,waterlogged=false]"
LOG = "minecraft:oak_log[axis=y]"
CLEAR_TAGS = ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable")
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class OrchardError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise OrchardError("%s: schema must be %s" % (path, SCHEMA))
    if doc["cellar"]["interior_half"] + 1 >= doc["press_house"]["half"]:
        raise OrchardError("the cellar's walls must stand inside the press-house's")
    if doc["cellar"]["air_height"] < 2:
        raise OrchardError("a player needs two blocks of air to stand in the cellar")
    return doc


def _base(state):
    return state.split("[")[0].split("{")[0]


def hash01(x, z, salt=0):
    """A fixed pseudo-random number in [0, 1) for a column: the same column always gives the same number."""
    h = (x * 73856093) ^ (z * 19349663) ^ (salt * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0x1000000)


def wall_sign(facing, lines):
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
    return "minecraft:oak_wall_sign[facing=%s,waterlogged=false]{front_text:{messages:[%s]}}" % (facing, q)


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """Blocks in two passes, {(x, y, z): state}: the structure (bottom up), then what hangs on or stands on it (top
    down): a lantern, a sign, a ladder, a trapdoor, a plant. Doors are their own ordered pairs. A later put of a cell
    replaces an earlier one in either pass."""

    def __init__(self, doc, g):
        self.doc, self.g = doc, g
        self.solid, self.hung, self.doors, self.clears = {}, {}, [], []
        self.allowed = set(doc["blocks"]["ids"])
        self.used = set()          # columns a feature stands on: the overgrowth keeps off them

    def _check(self, state):
        if _base(state) not in self.allowed:
            raise OrchardError("%s is not in data/old_orchard.json blocks.ids" % _base(state))

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
            st = "minecraft:oak_door[facing=%s,half=%s,hinge=%s,open=false,powered=false]" % (facing, half, hinge)
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


# ------------------------------------------------------------------------------------------------------------ the rows
def tree_kind(doc, x, z):
    v = doc["orchard"]["variants"]
    for kind in ("stump", "dead", "fallen", "bent"):
        if [z, x] in v[kind]:
            return kind
    return "alive"


def crown(p, cx, y0, cz, r, overgrown):
    """Leaves round (cx, cz) from y0 + 2: two courses r wide without the corners, one r - 1 wide, a cap; ragged."""
    t = p.doc["orchard"]["tree"]["trunk"]
    layers = [(t - 1, r, True), (t, r, True), (t + 1, r - 1, False), (t + 2, 0, False)]
    for dy, rr, cut in layers:
        for a in range(-rr, rr + 1):
            for b in range(-rr, rr + 1):
                if cut and abs(a) == rr and abs(b) == rr:
                    continue
                edge = max(abs(a), abs(b)) == rr and rr > 0
                if edge and hash01(cx + a, cz + b, y0 + dy) < 0.18:      # ragged
                    continue
                k = (cx + a, y0 + dy, cz + b)
                if k in p.solid and _base(p.solid[k]) == "minecraft:oak_log":
                    continue
                p.put(k[0], k[1], k[2], LEAVES)
    if rr == 0:
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p.put(cx + a, y0 + t + 2, cz + b, LEAVES)
    if overgrown:                                                       # leaves let down round the trunk
        for a in range(-1, 2):
            for b in range(-1, 2):
                if (a, b) != (0, 0) and hash01(cx + a, cz + b, 7) < 0.6:
                    p.put(cx + a, y0 + t - 2, cz + b, LEAVES)


def tree(p, x, z):
    doc, g = p.doc, p.g
    kind = tree_kind(doc, x, z)
    r = doc["orchard"]["tree"]["crown_radius"]
    t = doc["orchard"]["tree"]["trunk"]
    y0 = g(x, z) + 1
    p.used.add((x, z))
    reach_x = 6 if kind == "fallen" else (r + 1 if kind == "bent" else r)
    cols = [(x + a, z + b) for a in range(-r, reach_x + 1) for b in range(-r - 1, r + 1)]
    lo = min(g(a, b) for a, b in cols) + 1
    p.clear(x - r, z - r - 1, x + reach_x, z + r, lo, y0 + t + 4)
    if kind == "stump":
        p.put(x, y0, z, LOG)
        p.hang(x, y0 + 1, z, "minecraft:moss_carpet")
        return
    if kind == "dead":
        for dy in range(0, t + 1):
            p.put(x, y0 + dy, z, LOG)
        p.put(x + 1, y0 + t - 1, z, "minecraft:oak_log[axis=x]")
        return
    if kind == "fallen":
        p.put(x, y0, z, LOG)
        for a in range(2, 6):                                            # the trunk, lying east towards the sleeper
            p.put(x + a, g(x + a, z) + 1, z, "minecraft:oak_log[axis=x]")
            p.used.add((x + a, z))
        p.put(x + 6, g(x + 6, z) + 1, z, LEAVES)                         # what is left of its crown
        p.put(x + 6, g(x + 6, z) + 1, z - 1, LEAVES)
        p.used.update({(x + 6, z), (x + 6, z - 1)})
        return
    if kind == "bent":                                                   # storm-bent: the top steps north-east
        for dy in range(0, t - 1):
            p.put(x, y0 + dy, z, LOG)
        p.put(x + 1, y0 + t - 1, z - 1, LOG)
        crown(p, x + 1, y0, z - 1, r, False)
        return
    for dy in range(0, t):
        p.put(x, y0 + dy, z, LOG)
    crown(p, x, y0, z, r, hash01(x, z, 3) < 0.5)


def habitat_position(doc, g):
    """The trunk cell the Applin Habitat Block replaces: the second log of its living tree."""
    z, x = doc["applin"]["tree"]
    return (x, g(x, z) + 2, z)


def track(p):
    doc, g = p.doc, p.g
    tr = doc["orchard"]["track"]
    z = tr["z"]
    cols = [(x, z) for x in range(tr["x"][0], tr["x"][1] + 1)]
    cols += [(tr["spur_x"], zz) for zz in range(tr["spur_z"][0], tr["spur_z"][1] + 1)]
    for x, zz in cols:
        p.used.add((x, zz))
        y = g(x, zz)
        if (x + zz) % 2 == 0:
            p.put(x, y, zz, "minecraft:dirt_path")
        else:
            p.put(x, y, zz, "minecraft:grass_block[snowy=false]")
        p.clear(x, zz, x, zz, y + 1, y + 2, ("#minecraft:replaceable",))


def overgrowth(p):
    doc, g = p.doc, p.g
    box = [b for b in doc["site"]["bounding_boxes"] if b["id"] == "old_orchard_rows_box"][0]
    og = doc["orchard"]["overgrowth"]
    r = doc["orchard"]["tree"]["crown_radius"]
    near_trunk = set()
    for z in doc["orchard"]["rows_z"]:
        for x in doc["orchard"]["cols_x"]:
            near_trunk.update((x + a, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1))
    for x in range(box["min"][0], box["max"][0] + 1):
        for z in range(box["min"][1], box["max"][1] + 1):
            if (x, z) in p.used or (x, z) in near_trunk or hash01(x, z, 11) >= og["share"]:
                continue
            y = g(x, z)
            if any(k in p.solid or k in p.hung for k in ((x, y, z), (x, y + 1, z), (x, y + 2, z))):
                continue                                                 # a crown let down to the ground here
            pick, acc = hash01(x, z, 13), 0.0
            for plant, share in og["plants"]:
                acc += share
                if pick < acc:
                    p.put(x, y, z, "minecraft:grass_block[snowy=false]")
                    p.hang(x, y + 1, z, plant)
                    break
    return r


# ------------------------------------------------------------------------------------------------------ the press-house
def press_house(p):
    doc, g = p.doc, p.g
    ph = doc["press_house"]
    cx, cz = ph["centre"]
    h, top, over = ph["half"], ph["wall_height"], ph["roof_overhang"]
    cut = ph["collapse_from_lx"]
    walls = [(cx + a, cz + b) for a in range(-h, h + 1) for b in range(-h, h + 1)]
    hf = max(g(x, z) for x, z in walls) + 1
    rise = h + over
    ridge = top + 1 + rise
    p.clear(cx - h - over, cz - h - over, cx + h + over, cz + h + over + 1, hf, hf + ridge + 1)
    for x, z in walls:
        p.used.add((x, z))

    def put(lx, dy, lz, st):
        p.put(cx + lx, hf + dy, cz + lz, st)

    def hang(lx, dy, lz, st):
        p.hang(cx + lx, hf + dy, cz + lz, st)

    # the floor: a cobblestone ring under the walls, oak boards inside; a foundation down to any lower ground
    for lx in range(-h, h + 1):
        for lz in range(-h, h + 1):
            ring = max(abs(lx), abs(lz)) == h
            put(lx, 0, lz, "minecraft:cobblestone" if ring else "minecraft:oak_planks")
            for y in range(g(cx + lx, cz + lz) + 1, hf):
                p.put(cx + lx, y, cz + lz, "minecraft:cobblestone")
    # the walls: cobblestone with moss where the damp got in, stone-brick quoins; the room's air
    for lx in range(-h, h + 1):
        for lz in range(-h, h + 1):
            ring = max(abs(lx), abs(lz)) == h
            for dy in range(1, top + 1):
                if not ring:
                    put(lx, dy, lz, "minecraft:air")
                elif abs(lx) == h and abs(lz) == h:
                    put(lx, dy, lz, "minecraft:mossy_stone_bricks" if dy % 2 else "minecraft:stone_bricks")
                else:
                    mossy = hash01(cx + lx, cz + lz, dy) < 0.35
                    put(lx, dy, lz, "minecraft:mossy_cobblestone" if mossy else "minecraft:cobblestone")
    # the storm broke the east wall's top courses
    for lz in range(-h + 1, h):
        if hash01(cx + h, cz + lz, 21) < 0.5:
            put(h, top, lz, "minecraft:air")
            if hash01(cx + h, cz + lz, 22) < 0.4:
                put(h, top - 1, lz, "minecraft:air")
    # window holes, and the door in the south wall
    for lx in (-3, 3):
        for lz in (-h, h):
            for dy in (2, 3):
                put(lx, dy, lz, "minecraft:air")
    for lz in (-2, 2):
        for dy in (2, 3):
            put(-h, dy, lz, "minecraft:air")
    put(0, 1, h, "minecraft:air")
    put(0, 2, h, "minecraft:air")
    p.door(cx, hf + 1, cz + h, "north")
    put(0, 0, h + 1, "minecraft:cobblestone_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]")
    p.used.add((cx, cz + h + 1))
    # the roof: a gable whose ridge runs east-west. West of `cut` it stands whole; east of it only the north eaves
    for k in range(0, rise + 1):
        dy = top + 1 + k
        r = rise - k
        for lx in range(-h - over, h + over + 1):
            standing = lx <= cut
            if r == 0:
                if standing:
                    put(lx, dy, 0, "minecraft:oak_planks")
                continue
            if standing or k <= 1:
                put(lx, dy, -r, "minecraft:oak_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]")
            if standing:
                put(lx, dy, r, "minecraft:oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]")
        for lz in range(-(r - 1), r):
            for lx in range(-h, h + 1):
                if lx == -h:
                    put(lx, dy, lz, "minecraft:oak_planks")                 # the west gable end
                elif lx <= cut:
                    put(lx, dy, lz, "minecraft:air")
    # two bare rafters over the open half, one whole, one broken off and fallen in
    for lz in range(-h, h + 1):
        put(3, top + 1, lz, "minecraft:stripped_oak_log[axis=z]")
    for lz in range(-h, 1):
        put(5, top + 1, lz, "minecraft:stripped_oak_log[axis=z]")
    for a in range(1, 5):
        put(a, 1, 3, "minecraft:stripped_oak_log[axis=x]")                 # the fallen half, across the floor
    # rubble under the hole in the roof
    for lx, lz, st in ((2, 1, "minecraft:mossy_cobblestone"), (4, 0, "minecraft:cobblestone_slab[type=bottom,waterlogged=false]"),
                       (5, 2, "minecraft:mossy_cobblestone_slab[type=bottom,waterlogged=false]"),
                       (3, -1, "minecraft:cobblestone_slab[type=bottom,waterlogged=false]"),
                       (5, 4, "minecraft:cobblestone"), (4, 4, "minecraft:oak_slab[type=bottom,waterlogged=false]")):
        put(lx, 1, lz, st)
    # the press, in the open half: two posts, a beam, the screw and the cauldron it pressed into
    for lx in (1, 4):
        for dy in (1, 2, 3):
            put(lx, dy, -3, "minecraft:stripped_oak_log[axis=y]")
    for lx in range(1, 5):
        put(lx, 4, -3, "minecraft:oak_log[axis=x]")
    put(2, 1, -3, "minecraft:cauldron")
    put(2, 2, -3, "minecraft:oak_fence[east=false,west=false,north=false,south=false,waterlogged=false]")
    put(2, 3, -3, "minecraft:oak_fence[east=false,west=false,north=false,south=false,waterlogged=false]")
    put(3, 1, -4, "minecraft:composter[level=7]")
    put(4, 1, -5, "minecraft:hay_block[axis=y]")
    # the intact west half: casks on the north wall, a bench, stores
    for lx in (-5, -4):
        put(lx, 1, -5, "minecraft:barrel[facing=south,open=false]")
        put(lx, 2, -5, "minecraft:barrel[facing=south,open=false]")
    put(-1, 1, -5, "minecraft:barrel[facing=south,open=false]")
    put(-5, 1, 0, "minecraft:crafting_table")
    put(-5, 1, 2, "minecraft:barrel[facing=east,open=false]")
    put(-5, 1, 3, "minecraft:barrel[facing=up,open=false]")
    # a lantern on a chain from the standing ridge, and the door sign
    for dy in range(ridge - 3, ridge):
        hang(-3, dy, 0, "minecraft:chain[axis=y,waterlogged=false]")
    hang(-3, ridge - 4, 0, "minecraft:lantern[hanging=true,waterlogged=false]")
    hang(-2, 2, h + 1, wall_sign("south", ph["door_sign"]))
    return hf, ridge


def cellar(p, hf):
    doc = p.doc
    cx, cz = doc["press_house"]["centre"]
    c = doc["cellar"]
    n, air = c["interior_half"], c["air_height"]
    floor = -(air + 2)                       # the floor block's dy: the ceiling is dy -1, the air under it

    def put(lx, dy, lz, st):
        p.put(cx + lx, hf + dy, cz + lz, st)

    def hang(lx, dy, lz, st):
        p.hang(cx + lx, hf + dy, cz + lz, st)

    for lx in range(-n - 1, n + 2):
        for lz in range(-n - 1, n + 2):
            edge = max(abs(lx), abs(lz)) == n + 1
            for dy in range(floor, 0):
                if edge:
                    mossy = hash01(cx + lx, cz + lz, dy + 40) < 0.4
                    put(lx, dy, lz, "minecraft:mossy_stone_bricks" if mossy else "minecraft:stone_bricks")
                elif dy == floor:
                    put(lx, dy, lz, "minecraft:stone_bricks")
                elif dy == -1:
                    put(lx, dy, lz, "minecraft:stripped_oak_log[axis=x]" if lz in (-2, 2) else "minecraft:oak_planks")
                else:
                    put(lx, dy, lz, "minecraft:air")
            if not edge:
                for dy in range(floor - c["under_fill"], floor):
                    put(lx, dy, lz, "minecraft:stone")
    feet = floor + 1
    # casks on the north wall, two courses; a cauldron
    for lx in range(0, n + 1):
        put(lx, feet, -n, "minecraft:barrel[facing=south,open=false]")
    for lx in (2, 3):
        put(lx, feet + 1, -n, "minecraft:barrel[facing=south,open=false]")
    put(-n, feet, n, "minecraft:cauldron")
    # the find: the barrel in the south-east corner (data/rewards.json old_orchard_cellar)
    put(n, feet, n, "minecraft:barrel[facing=west,open=false]")
    # the way down: a ladder on the west wall in the north-west corner, through the ceiling, under the trapdoor
    for dy in range(feet, 0):
        hang(-n, dy, -n, "minecraft:ladder[facing=east,waterlogged=false]")
    hang(-n, 0, -n, "minecraft:oak_trapdoor[facing=east,half=top,open=false,powered=false,waterlogged=false]")
    hang(0, -2, 0, "minecraft:lantern[hanging=true,waterlogged=false]")
    hang(1, feet + 1, n, wall_sign("north", c["sign"]))
    return hf + floor


# ---------------------------------------------------------------------------------------------------- the yard pieces
def _walls_state(base, conn):
    sides = ",".join("%s=%s" % (d, "low" if d in conn else "none") for d in ("east", "north", "south", "west"))
    return "%s[%s,up=true,waterlogged=false]" % (base, sides)


def kitchen_garden(p):
    doc, g = p.doc, p.g
    kg = doc["kitchen_garden"]
    cx, cz = kg["centre"]
    hx, hz = kg["half_x"], kg["half_z"]
    cols = [(cx + a, cz + b) for a in range(-hx, hx + 1) for b in range(-hz, hz + 1)]
    lo, hi = min(g(x, z) for x, z in cols), max(g(x, z) for x, z in cols)
    p.clear(cx - hx, cz - hz, cx + hx, cz + hz, lo + 1, hi + 3)
    ring = {(x, z) for x, z in cols if abs(x - cx) == hx or abs(z - cz) == hz}
    gate = (cx + hx, cz)
    for x, z in sorted(ring):
        p.used.add((x, z))
        if (x, z) == gate:
            continue
        y = g(x, z) + 1
        conn = set()
        for d, (a, b) in (("east", (1, 0)), ("west", (-1, 0)), ("north", (0, -1)), ("south", (0, 1))):
            nb = (x + a, z + b)
            if (nb in ring and nb != gate and g(nb[0], nb[1]) == g(x, z)) or (nb == gate and g(*gate) == g(x, z)):
                conn.add(d)
        mossy = hash01(x, z, 31) < 0.4
        p.put(x, y, z, _walls_state("minecraft:mossy_cobblestone_wall" if mossy else "minecraft:cobblestone_wall", conn))
    p.put(gate[0], g(*gate) + 1, gate[1],
          "minecraft:oak_fence_gate[facing=east,in_wall=true,open=false,powered=false]")
    # inside: two beds of berries on coarse dirt, a melon bed, a rooted-dirt path, the composter and the rain cauldron
    for a in range(-hx + 1, hx):
        for b in range(-hz + 1, hz):
            x, z = cx + a, cz + b
            y = g(x, z)
            p.used.add((x, z))
            if b == 0:
                p.put(x, y, z, "minecraft:rooted_dirt")
            elif b in (-3, -2) and -5 <= a <= 4:
                p.put(x, y, z, "minecraft:coarse_dirt")
                if (a + b) % 2 == 0 or hash01(x, z, 33) < 0.3:
                    p.hang(x, y + 1, z, "minecraft:sweet_berry_bush[age=3]")
            elif b in (2, 3) and -5 <= a <= 4:
                p.put(x, y, z, "minecraft:coarse_dirt")
                if hash01(x, z, 35) < 0.35:
                    p.put(x, y + 1, z, "minecraft:melon")
            else:
                p.put(x, y, z, "minecraft:grass_block[snowy=false]")
                if hash01(x, z, 37) < 0.45:
                    p.hang(x, y + 1, z, "minecraft:short_grass")
    x, z = cx - hx + 1, cz - hz + 1
    p.put(x, g(x, z) + 1, z, "minecraft:composter[level=3]")
    x, z = cx - hx + 1, cz + hz - 1
    p.put(x, g(x, z) + 1, z, "minecraft:cauldron")


def beehives(p):
    g = p.g
    for x, z in p.doc["beehives"]["at"]:
        y = g(x, z) + 1
        p.clear(x, z, x, z, y, y + 2)
        p.used.add((x, z))
        p.put(x, y, z, LOG)
        p.put(x, y + 1, z, "minecraft:beehive[facing=south,honey_level=5]")


def drying_racks(p):
    g = p.g
    n = p.doc["drying_racks"]["length"]
    for x0, z in p.doc["drying_racks"]["at"]:
        cols = [(x0 + a, z) for a in range(n)]
        top = max(g(x, zz) for x, zz in cols) + 2
        p.clear(x0, z, x0 + n - 1, z, min(g(x, zz) for x, zz in cols) + 1, top + 1)
        for i, (x, zz) in enumerate(cols):
            p.used.add((x, zz))
            if i in (0, n - 1):
                for y in range(g(x, zz) + 1, top + 1):
                    p.put(x, y, zz, "minecraft:oak_fence[east=false,west=false,north=false,south=false,waterlogged=false]")
            else:
                p.put(x, g(x, zz) + 1, zz, "minecraft:hay_block[axis=x]")
                p.hang(x, top, zz, "minecraft:spruce_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]")


def lantern_posts(p):
    g = p.g
    for x, z in p.doc["lantern_posts"]["at"]:
        y = g(x, z) + 1
        p.clear(x, z, x, z, y, y + 3)
        p.used.add((x, z))
        for d in (0, 1):
            p.put(x, y + d, z, "minecraft:oak_fence[east=false,west=false,north=false,south=false,waterlogged=false]")
        p.hang(x, y + 2, z, "minecraft:lantern[hanging=false,waterlogged=false]")


def plan(doc, g):
    p = Plan(doc, g)
    track(p)
    for z in doc["orchard"]["rows_z"]:
        for x in doc["orchard"]["cols_x"]:
            tree(p, x, z)
    hf, ridge = press_house(p)
    floor_y = cellar(p, hf)
    kitchen_garden(p)
    beehives(p)
    drying_racks(p)
    lantern_posts(p)
    overgrowth(p)
    nx, nz = doc["npc"]["at"]
    npc = (nx, g(nx, nz) + 1, nz)
    blocks = p.blocks()
    for k in (npc, (npc[0], npc[1] + 1, npc[2])):
        if blocks.get(k, "minecraft:air") != "minecraft:air":
            raise OrchardError("the keeper's spot %s is not two blocks of air" % (npc,))
    hb = habitat_position(doc, g)
    if blocks.get(hb) != LOG:
        raise OrchardError("the Applin tree's trunk at %s is not a log" % (hb,))
    cx, cz = doc["press_house"]["centre"]
    n = doc["cellar"]["interior_half"]
    return {"plan": p, "hf": hf, "ridge_y": hf + ridge, "floor_y": floor_y, "npc": npc, "habitat_block": hb,
            "barrel": (cx + n, floor_y + 1, cz + n), "blocks": blocks}


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
    out = ["# Generated by tools/old_orchard.py from data/old_orchard.json. Re-run to rebuild; do not edit.",
           "# The Old Orchard on Sunset Isle: the rows, the press-house and its cellar, the garden, hives, racks, posts.",
           "# Run BEFORE R9E: the Habitat Block old_orchard_rows_ward sits in a trunk this writes.",
           "# 1. clear trees, leaves and plants over each feature's box"]
    for (x0, y0, z0, x1, y1, z1), tags in p.clears:
        for tag in tags:
            out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the structure, bottom up")
    over = set(p.hung) | {k for k, _st in p.doors}
    out += _runs({k: st for k, st in p.solid.items() if k not in over})
    out.append("# 3. what hangs on it or stands on it, from the top: chain, lanterns, signs, ladder, trapdoor, plants")
    out += _runs(p.hung, top_down=True)
    out.append("# 4. the door, lower half then upper")
    out += ["setblock %d %d %d %s" % (k + (st,)) for k, st in p.doors]
    return out


def files(doc, g):
    pl = plan(doc, g)
    lines = function_limits.ensure_loaded(build_lines(doc, pl))
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise OrchardError("build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    out = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Old Orchard on Sunset Isle (tools/old_orchard.py)"}}, indent=2) + "\n",
        "data/%s/function/%s/build.mcfunction" % (NS, FN): "\n".join(lines) + "\n",
    }
    return out, pl


def hold_box(doc):
    b = [x for x in doc["site"]["bounding_boxes"] if x["id"] == "old_orchard_all"][0]
    return "%d %d %d %d" % (b["min"][0], b["min"][1], b["max"][0], b["max"][1])


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, step R9SO BEFORE R9E: hold the chunks, build, release (R9LH's shape)."""
    doc = doc or load()
    hold = hold_box(doc)
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (NS, FN)),
            ("cmd", "forceload remove " + hold)]


def npc_placements(doc=None, g=None):
    """[(conversation id, (x, y, z), npc class)] for tools/reapply.py's "npc" action (step R18SO): the keeper stands on
    her column's heightmap ground + 1."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    conv = next((c for c in dl["conversations"] if c["id"] == doc["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        raise OrchardError("%s is not a conversation with an NPC in data/dialogue.json" % doc["npc"]["conversation"])
    x, z = doc["npc"]["at"]
    return [(conv["id"], (x, g(x, z) + 1, z), "%s:%s" % (doc["namespace"], conv["npc_id"]))]


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


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
    xs = [k[0] for k in b]
    zs = [k[2] for k in b]
    ax, az = doc["resident"]["anchor"]
    near = min(math.hypot(k[0] - ax, k[2] - az) for k in b)
    land = json.loads((ROOT / "data" / "ferries.json").read_text(encoding="utf-8"))
    dock = [d for d in land["docks"] if d["id"] == "sunset_isle_landing"][0]
    lx, ly, lz = dock["landing"]["at"]
    eye = (lx, ly + 1.62, lz)
    palm = sightline(g, eye, (2840, 134, 7080))
    house = sightline(g, eye, (doc["press_house"]["centre"][0], pl["ridge_y"], doc["press_house"]["centre"][1]))
    return ["press-house floor y%d (max ground under the walls + 1), ridge y%d; cellar floor y%d; find barrel %s"
            % (pl["hf"], pl["ridge_y"], pl["floor_y"], pl["barrel"]),
            "blocks written: %d (air %d); writes x%d..%d z%d..%d; nearest write to the resident's anchor %s: %.1f"
            % (len(b), sum(1 for s in b.values() if s == "minecraft:air"), min(xs), max(xs), min(zs), max(zs),
               (ax, az), near),
            "Applin Habitat Block (a trunk's second log): %s; the keeper stands at %s" % (pl["habitat_block"], pl["npc"]),
            "from the landing %s: to the palm's crown (2840, 134, 7080) %d blocks, least clearance over the ground %.1f; "
            "to the press-house ridge %d blocks, least clearance %.1f" % ((lx, ly, lz), palm[1], palm[0], house[1], house[0]),
            "steps R9SO (before R9E): %s" % json.dumps([list(s) for s in placement_steps(doc)]),
            "step R18SO (after R17N): %s" % json.dumps([[n[0], list(n[1]), n[2]] for n in npc_placements(doc, g)])]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", choices=("build", "plan"), default=None)
    ap.add_argument("--report", action="store_true", help="the same as plan: print, write nothing")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, pl = files(doc, g)
    if a.report or a.cmd in (None, "plan"):
        print("\n".join(report(doc, pl, g)))
        return 0
    write(out_files, a.out)
    n = sum(1 for l in out_files["data/%s/function/%s/build.mcfunction" % (NS, FN)].splitlines()
            if l and not l.startswith("#"))
    print("old_orchard: %d files -> %s (build: %d commands)" % (len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
