#!/usr/bin/env python
"""The Pallet crushed house (Hank and Lena), from data/crushed_house.json: a 9 by 9 cottage with its east half caved in, a
fallen oak across the broken wall, a blocked front door, and one safe opening at the foot of the south wall that a player
walks through to reach Lena.

The mechanism ladder (CLAUDE.md principle 6): configuration and datapack functions only. Nothing here is a mod, a script or
a companion. It is the repository's own block-pass pattern (tools/lopunny_house.py, tools/sanctuaries.py): ground from
tools/ground.py (the canonical heightmap, rounded; no world is ever read), a pack of one build function written with every
chunk it writes force-loaded, a step in tools/reapply.py that holds the chunks, runs it and releases them.

  the house     vanilla blocks only, none a spawn condition (data/spawn_blocks.json, checked at load). The floor sits on
                F = max(ground under the lot) (117), the walls and gable on F + 1 upward. Every cell of the house volume is
                written (air included), so a rebuild over its own output leaves nothing of an earlier run inside it.
  the pocket    a 3 by 3 room, two blocks high, in the middle of a sealed block of rubble (the "shell"), reached only by
                a one-wide crawl whose mouth is the opening in the south wall. Lena's inside stand is in it.
  the seal      the front door is filled by a fallen lintel and a pile; the windows are panes or one-block holes; every
                other wall cell is solid. The collapsed east half is open to the sky but the shell's ceiling is complete,
                so the only walkable way to Lena is the opening. tests/test_crushed_house_build.py walks the BUILT function
                (parsed back, not the plan) and shuts the opening to prove it.
  the restore   cobblers:crushed_house/restore puts the lot's columns back to the heightmap's ground (grass at the floor,
                air above, up to the clear box's roof). An operator's undo, run by hand with nobody in the box; no step runs
                it. To change the design run the restore, then the build: the build overwrites the house volume completely
                but leaves a stale apron/debris cell of an earlier design where the new design has none.

  python tools/crushed_house.py build  [--source-root R] [--out DIR]   write the pack
  python tools/crushed_house.py plan   [--source-root R]               print the numbers and the steps; writes nothing
  python tools/crushed_house.py probes [--write]                       print (or write) data/world_probes.json's crushed_house
                                                                       places; `build` refuses a drifted committed set

The re-application: placement_steps() is step R16CH in tools/reapply.py, after the town passes and the shrines and before
R17N (Hank) and R18CH (Lena). It must follow R7 (hometown) so nothing re-levels the lot under it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "crushed_house.json"
SEATS = ROOT / "data" / "npc_seats.json"
SPAWN_BLOCKS = ROOT / "data" / "spawn_blocks.json"
PROBES = ROOT / "data" / "world_probes.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_crushed_house"
SCHEMA = "cobblers.crushed_house/1"
NS = "cobblers"
FN = "crushed_house"
PACK_FORMAT = 48  # Minecraft 1.21.1
PROBE_PLACE = "crushed_house"
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()

N = 9                       # the lot is 9 by 9
OPENING = (4, 8)            # lx, lz of the safe opening (the south wall's cell)
POCKET = [(x, z) for x in (3, 4, 5) for z in (3, 4, 5)]
CRAWL = [(4, 6), (4, 7)]
SHELL_RECT = (2, 6, 2, 7)   # lx0, lx1, lz0, lz1: the sealed block the pocket and the crawl are carved in
HOUSE_DY = 8                # the house volume is dy 0..7 (the ridge is dy 7)


class HouseError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise HouseError("%s: schema must be %s" % (path, SCHEMA))
    s = doc.get("structure")
    if not s:
        raise HouseError("%s has no structure block" % path)
    lot = doc["site"]["lot"]
    if lot["x"][1] - lot["x"][0] + 1 != N or lot["z"][1] - lot["z"][0] + 1 != N:
        raise HouseError("the lot must be %d by %d" % (N, N))
    if OPENING != (4, 8) or (lot["x"][0] + OPENING[0], lot["z"][0] + OPENING[1]) != tuple(doc["side_opening"]["at"]):
        raise HouseError("data/crushed_house.json side_opening.at must be the lot's (4, 8) cell: %s"
                         % ((lot["x"][0] + 4, lot["z"][0] + 8),))
    door = doc["front"]["door"]
    if (door[0], door[1]) != (lot["x"][0], lot["z"][0] + 4):
        raise HouseError("front.door must be the west wall's middle cell (lx 0, lz 4)")
    spawn = set(json.loads(SPAWN_BLOCKS.read_text(encoding="utf-8"))["blocks"])
    bad = [b for b in s["blocks"]["ids"] if b in spawn]
    if bad:
        raise HouseError("blocks.ids names spawn-condition block(s) (data/spawn_blocks.json): %s" % bad)
    return doc


def _base(state):
    return state.split("[")[0].split("{")[0]


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """{(x, y, z): state} for what the house writes, in a local frame (lx, lz, dy) over the lot. `put` lays a cell by the
    house's floor (F + 1 + dy); `putg` lays a cell by its own column's ground (debris round the house)."""

    def __init__(self, doc, g):
        self.doc, self.g = doc, g
        s = doc["structure"]
        lot = doc["site"]["lot"]
        self.ox, self.oz = lot["x"][0], lot["z"][0]
        self.F = max(g(self.ox + i, self.oz + j) for i in range(N) for j in range(N))
        self.y0 = self.F + 1
        self.seed = s["seed"]
        self.allowed = set(s["blocks"]["ids"])
        self.b = {}
        self.gravity = set()

    def h(self, *key):
        """A stable pseudo-random integer for a cell: the same cell always draws the same number."""
        d = hashlib.md5(("%s:%s" % (self.seed, ":".join(str(k) for k in key))).encode()).digest()
        return int.from_bytes(d[:4], "big")

    def _set(self, x, y, z, state):
        if _base(state) not in self.allowed:
            raise HouseError("%s is not in data/crushed_house.json structure.blocks.ids" % _base(state))
        self.b[(x, y, z)] = state
        if _base(state) in ("minecraft:gravel",):
            self.gravity.add((x, y, z))

    def put(self, lx, dy, lz, state):
        self._set(self.ox + lx, self.y0 + dy, self.oz + lz, state)

    def putg(self, lx, dy, lz, state):
        x, z = self.ox + lx, self.oz + lz
        self._set(x, self.g(x, z) + 1 + dy, z, state)

    def get(self, lx, dy, lz):
        return self.b.get((self.ox + lx, self.y0 + dy, self.oz + lz), "minecraft:air")


COB, MOSSY, PLANKS = "minecraft:cobblestone", "minecraft:mossy_cobblestone", "minecraft:oak_planks"
WALL, BRICKS, GLASS = "minecraft:white_terracotta", "minecraft:bricks", "minecraft:glass_pane"
AIR = "minecraft:air"
LOG_Y, LOG_X, LOG_Z = "minecraft:oak_log[axis=y]", "minecraft:oak_log[axis=x]", "minecraft:oak_log[axis=z]"


def stairs(kind, facing, half="bottom"):
    return "minecraft:%s_stairs[facing=%s,half=%s]" % (kind, facing, half)


def floor(p):
    """The floor at dy -1: cobblestone under the walls, planks inside. A column lower than the floor gets a cobblestone
    foundation up to it, so nothing hangs over a hollow."""
    for lx in range(N):
        for lz in range(N):
            perimeter = lx in (0, N - 1) or lz in (0, N - 1)
            p.put(lx, -1, lz, COB if perimeter else PLANKS)
            x, z = p.ox + lx, p.oz + lz
            for y in range(p.g(x, z) + 1, p.F):
                p._set(x, y, z, COB)


# how many blocks of each wall cell still stand (dy 0..h-1), by (lx, lz)
def _wall_heights():
    hts = {}
    for lx, h in {0: 3, 1: 3, 2: 3, 3: 3, 4: 3, 5: 2, 6: 2, 7: 1, 8: 2}.items():
        hts[(lx, 0)] = h                                  # north: whole in the west, broken in the east
    for lx in range(N):
        hts[(lx, 8)] = 3                                  # south: stands, bar the opening and one pane
    hts[(7, 8)] = 2
    for lz in range(1, 8):
        hts[(0, lz)] = 3                                  # west: the front
    for lz, h in {1: 3, 2: 2, 3: 1, 4: 1, 5: 2, 6: 2, 7: 3}.items():
        hts[(8, lz)] = h                                  # east: broken
    return hts


def walls(p):
    hts = _wall_heights()
    for (lx, lz), height in hts.items():
        for dy in range(height):
            exposed = dy <= 1 and p.h("brick", lx, lz, dy) % 100 < 24      # plaster fallen off, the brick showing
            p.put(lx, dy, lz, BRICKS if exposed else WALL)
    # corner posts (the snapped NE one is shorter than the others)
    for (lx, lz) in ((0, 0), (8, 0), (0, 8), (8, 8)):
        for dy in range(hts[(lx, lz)]):
            p.put(lx, dy, lz, LOG_Y)
    # windows: a pane in the west wall and the north wall, one in the south; the others are one-block holes
    for lx, lz in ((0, 2), (2, 0), (1, 8)):
        p.put(lx, 1, lz, GLASS)
    for lx, lz in ((0, 6), (7, 8)):
        p.put(lx, 1, lz, AIR)


def roof(p):
    """A gable over the lot, ridge east-west at lz 4. Standing for lx 0..3; the north slope only at lx 4; gone east of it."""
    for lx in range(N):
        north = lx <= 4
        south = lx <= 3
        for dy, lz_n, lz_s in ((3, 0, 8), (4, 1, 7), (5, 2, 6), (6, 3, 5)):
            if north:
                p.put(lx, dy, lz_n, stairs("brick", "south"))
            if south:
                p.put(lx, dy, lz_s, stairs("brick", "north"))
        if north:
            p.put(lx, 7, 4, BRICKS)
    for dy, lo, hi in ((3, 1, 7), (4, 2, 6), (5, 3, 5), (6, 4, 4)):       # the standing west gable
        for lz in range(lo, hi + 1):
            p.put(0, dy, lz, WALL)


def rubble(p, lx, lz, dy):
    """One block of fallen house: weighted toward timber, plaster-less brick and cobble, never a gravity block floating."""
    r = p.h("rubble", lx, lz, dy) % 12
    if r in (0, 1, 2):
        return PLANKS
    if r in (3, 4):
        return COB
    if r == 5:
        return MOSSY
    if r in (6, 7):
        return BRICKS
    if r == 8:
        return "minecraft:coarse_dirt"
    if r == 9:
        return LOG_X if p.h("axis", lx, lz, dy) % 2 else LOG_Z
    if r == 10:
        return "minecraft:gravel" if dy == 0 else PLANKS     # gravel only on the floor, so it cannot fall
    return stairs("brick", ("north", "south", "east", "west")[p.h("face", lx, lz, dy) % 4])


def shell(p):
    """The sealed block of rubble round the pocket and its crawl, three high (dy 0..2), top layer planks."""
    x0, x1, z0, z1 = SHELL_RECT
    for lx in range(x0, x1 + 1):
        for lz in range(z0, z1 + 1):
            if (lx, lz) in POCKET or (lx, lz) in CRAWL:
                continue
            for dy in range(3):
                if dy == 2:
                    p.put(lx, dy, lz, PLANKS)
                elif (lx, lz) == (2, 4):
                    p.put(lx, dy, lz, "minecraft:bookshelf")          # the cupboard
                else:
                    p.put(lx, dy, lz, rubble(p, lx, lz, dy))


def pocket(p):
    """Carve the room, the crawl and the opening; give them their ceiling, beam and fittings."""
    for lx, lz in POCKET + CRAWL + [OPENING]:
        for dy in (0, 1):
            p.put(lx, dy, lz, AIR)
    for lx, lz in POCKET + CRAWL:
        p.put(lx, 2, lz, PLANKS)
    for lx in (3, 4, 5):
        p.put(lx, 2, 4, LOG_X)                                       # the beam that missed her
    p.put(4, 2, 8, LOG_X)                                            # the lintel of the opening
    p.put(3, 0, 3, "minecraft:barrel")
    p.put(3, 1, 3, "minecraft:lantern[hanging=false]")               # the light she has kept
    p.put(5, 0, 3, "minecraft:bookshelf")
    p.put(5, 1, 3, "minecraft:bookshelf")
    p.put(5, 0, 5, stairs("oak", "west"))                            # an overturned chair


RING_HEIGHT = {}
for _lz, _h in {1: 3, 2: 4, 3: 4, 4: 5, 5: 3, 6: 3, 7: 2}.items():
    RING_HEIGHT[(7, _lz)] = _h                                       # east strip: the roof came down here
for _lx, _h in {2: 1, 3: 2, 4: 3, 5: 3, 6: 4}.items():
    RING_HEIGHT[(_lx, 1)] = _h                                       # north strip, deeper in the east
for _lz, _h in {1: 1, 2: 1, 3: 2, 4: 2, 5: 2, 6: 1, 7: 1}.items():
    RING_HEIGHT[(1, _lz)] = _h                                       # west strip: low, under the standing roof


def ring(p):
    """The one-wide strip of floor between the outer walls and the shell: rubble, deeper where the roof fell."""
    for (lx, lz), height in RING_HEIGHT.items():
        for dy in range(height):
            if dy >= 3 and p.h("frag", lx, lz, dy) % 3 == 0:
                p.put(lx, dy, lz, stairs("brick", ("north", "south", "east", "west")[p.h("f", lx, lz, dy) % 4]))
            else:
                p.put(lx, dy, lz, rubble(p, lx, lz, dy))


def front(p):
    """The blocked front door: posts, the sagging lintel and the jam; the pile in front of it."""
    for lz in (3, 5):
        p.put(0, 0, lz, LOG_Y)
        p.put(0, 1, lz, LOG_Y)
    for lz in (3, 4, 5):
        p.put(0, 2, lz, LOG_Z)                                       # the lintel, dropped
    p.put(0, 0, 4, PLANKS)                                           # the door's planks
    p.put(0, 1, 4, LOG_X)                                            # the beam wedged in the frame
    for lz, height in {2: 1, 3: 2, 4: 2, 5: 2, 6: 1}.items():
        for dy in range(height):
            p.putg(-1, dy, lz, rubble(p, -1, lz, dy))
    p.putg(-1, 1, 4, LOG_Z)                                          # the fallen lintel's end
    p.putg(-2, 0, 3, "minecraft:gravel")
    p.putg(-2, 0, 5, "minecraft:coarse_dirt")


def exterior(p):
    """The spill east of the broken wall, debris north of it, and the wall panel leaning off the south wall's foot."""
    for (lx, lz), height in {(9, 2): 1, (9, 3): 2, (9, 4): 2, (9, 5): 1, (10, 4): 1}.items():
        for dy in range(height):
            p.putg(lx, dy, lz, rubble(p, lx, lz, dy))
    for lx, state in ((2, WALL), (3, BRICKS), (4, COB), (5, PLANKS)):
        p.putg(lx, 0, -1, state)
    for lx in (1, 2, 3):                                             # leans against the south wall, west of the opening
        p.putg(lx, 0, 9, WALL)
        p.putg(lx, 1, 9, WALL)
        p.putg(lx, 0, 10, WALL)
    for lz in (9, 10):
        p.putg(-1, 0, lz, "minecraft:oak_fence")                     # what is left of the garden fence


# the fallen oak: trunk along z at lx 6, rising from the root plate over the broken north wall onto the shell's top
TRUNK = {-3: (0,), -2: (0, 1), -1: (1, 2), 0: (2,), 1: (2, 3), 2: (3,), 3: (3,), 4: (3,), 5: (3,), 6: (3,), 7: (3,)}


def tree(p):
    for (lx, lz, dy, state) in ((5, -4, 0, "minecraft:dirt"), (6, -4, 0, "minecraft:rooted_dirt"),
                                (6, -4, 1, "minecraft:rooted_dirt"), (7, -4, 0, "minecraft:coarse_dirt"),
                                (5, -3, 0, "minecraft:coarse_dirt"), (7, -3, 0, "minecraft:coarse_dirt")):
        p.putg(lx, dy, lz, state)
    for lz, dys in TRUNK.items():
        for dy in dys:
            if lz < 0:
                p.putg(6, dy, lz, LOG_Z)
            else:
                p.put(6, dy, lz, LOG_Z)
    p.put(5, 3, 3, LOG_X)                                            # broken branches
    p.put(7, 3, 5, LOG_X)
    p.put(5, 3, 6, LOG_X)
    p.put(6, 4, 4, LOG_Y)


def plan(doc, g):
    p = Plan(doc, g)
    floor(p)
    walls(p)
    roof(p)
    ring(p)
    shell(p)
    pocket(p)
    front(p)
    exterior(p)
    tree(p)
    problems = check_plan(doc, p)
    if problems:
        raise HouseError("crushed house plan refused:\n  " + "\n  ".join(problems))
    x0, x1 = p.ox + doc["structure"]["clear"]["x"][0], p.ox + doc["structure"]["clear"]["x"][1]
    z0, z1 = p.oz + doc["structure"]["clear"]["z"][0], p.oz + doc["structure"]["clear"]["z"][1]
    return {"plan": p, "F": p.F, "y0": p.y0, "blocks": dict(p.b), "clear": (x0, z0, x1, z1),
            "clear_y": (p.y0, p.y0 + doc["structure"]["clear"]["up"]),
            "stands": stands(doc)}


def stands(doc):
    """Where the three NPC stands are, read from data/npc_seats.json (feet y, so the head is y + 1)."""
    seats = json.loads(SEATS.read_text(encoding="utf-8"))
    hank = next(s for s in seats["seats"] if s["id"] == "npc_pallet_crushed_house_hank")["at"]
    m = seats["markers"]
    return {"hank": tuple(hank), "lena_in": tuple(m[doc["pocket"]["marker"]]["at"]),
            "lena_out": tuple(m[doc["after_rescue"]["marker"]]["at"])}


def check_plan(doc, p):
    """What the builder itself refuses (the independent walk of the built function is the test's)."""
    out = []
    st = stands(doc)
    for name, (x, y, z) in st.items():
        for dy in (0, 1):
            if p.b.get((x, y + dy, z), AIR) != AIR:
                out.append("the %s stand (%d, %d, %d) is not clear at y%d: %s" % (name, x, y, z, y + dy, p.b[(x, y + dy, z)]))
    if st["lena_in"][1] != p.y0 or st["hank"][1] != p.y0 or st["lena_out"][1] != p.y0:
        out.append("the stands' feet y (%s) must be F + 1 = %d (the lot's highest ground %d); re-seat them (tools/npc_seats.py)"
                   % ([st[k][1] for k in st], p.y0, p.F))
    for (x, y, z) in p.gravity:
        if p.b.get((x, y - 1, z), AIR) == AIR and y - 1 > p.g(x, z):
            out.append("gravel at (%d, %d, %d) has air under it and would fall" % (x, y, z))
    for (x, y, z), s in p.b.items():
        if y <= p.g(x, z) and not (p.ox <= x < p.ox + N and p.oz <= z < p.oz + N) and _base(s) != AIR:
            out.append("%s at (%d, %d, %d) is inside the ground (y%d)" % (_base(s), x, y, z, p.g(x, z)))
    # the line from the opening to Lena's stand is air at both heights (the pocket's corners hold its fittings)
    for lx, lz in [OPENING] + CRAWL + [(4, 5), (4, 4)]:
        for dy in (0, 1):
            if p.get(lx, dy, lz) != AIR:
                out.append("pocket/crawl cell (%d, %d, dy %d) is not air: %s" % (lx, lz, dy, p.get(lx, dy, lz)))
    return out[:12]


# ---------------------------------------------------------------------------------------------------------- the pack
def _runs(blocks):
    """setblock and fill lines for {(x, y, z): state}, one fill per run of one state along x, bottom up."""
    out = []
    keys = sorted(blocks, key=lambda k: (k[1], k[2], k[0]))
    i = 0
    while i < len(keys):
        x, y, z = keys[i]
        st = blocks[keys[i]]
        j = i
        while (j + 1 < len(keys) and keys[j + 1] == (keys[j][0] + 1, y, z) and blocks[keys[j + 1]] == st):
            j += 1
        if j == i:
            out.append("setblock %d %d %d %s" % (x, y, z, st))
        else:
            out.append("fill %d %d %d %d %d %d %s" % (x, y, z, keys[j][0], y, z, st))
        i = j + 1
    return out


def build_lines(doc, pl):
    p = pl["plan"]
    x0, z0, x1, z1 = pl["clear"]
    y0, y1 = pl["clear_y"]
    hx0, hz0 = p.ox, p.oz
    out = ["# Generated by tools/crushed_house.py from data/crushed_house.json. Re-run to rebuild; do not edit.",
           "# The Pallet crushed house (Hank and Lena): a cottage with its east half fallen in, a blocked front door and one safe",
           "# opening at the foot of the south wall (%d, %d..%d, %d). Run by R16CH, BEFORE R17N seats Hank and R18CH seats Lena."
           % (p.ox + OPENING[0], p.y0, p.y0 + 1, p.oz + OPENING[1]),
           "# To undo it run %s:%s/restore by hand with nobody in the box, then build again." % (NS, FN),
           "# 1. clear the trees, plants and snow layers over everything this writes"]
    for tag in ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable"):
        out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the whole house volume, air: a rebuild leaves nothing of an earlier run inside it")
    out.append("fill %d %d %d %d %d %d minecraft:air" % (hx0, p.y0, hz0, hx0 + N - 1, p.y0 + HOUSE_DY - 1, hz0 + N - 1))
    out.append("# 3. the structure, bottom up; the lantern last, on the barrel it stands on")
    lamp = {k: v for k, v in pl["blocks"].items() if _base(v) == "minecraft:lantern"}
    out += _runs({k: v for k, v in pl["blocks"].items() if k not in lamp})
    out += _runs(lamp)
    return out


def restore_lines(doc, pl):
    """Put the clear box back to the heightmap's ground: air above each column's ground, the floor columns' surface block
    at the floor. Guarded: a player in the box stops it (a held player would be buried)."""
    p = pl["plan"]
    x0, z0, x1, z1 = pl["clear"]
    top = pl["clear_y"][1]
    surface = doc["structure"]["terrain"]["surface"]
    low = min(p.g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    out = ["# Generated by tools/crushed_house.py from data/crushed_house.json. Re-run to rebuild; do not edit.",
           "# The crushed house's undo: ground back to the heightmap's, air above it, in the build's clear box. An operator's",
           "# function, run by hand over RCON; no re-apply step runs it. It stops if a player stands in the box.",
           "execute if entity @a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d] run return 0"
           % (x0, low - 4, z0, x1 - x0, top - low + 8, z1 - z0)]
    for z in range(z0, z1 + 1):                          # air above each column's ground, one fill per run of equal ground
        x = x0
        while x <= x1:
            gy = p.g(x, z)
            xe = x
            while xe + 1 <= x1 and p.g(xe + 1, z) == gy:
                xe += 1
            out.append("fill %d %d %d %d %d %d minecraft:air" % (x, gy + 1, z, xe, top, z))
            x = xe + 1
    out.append("# the floor's columns: the surface block at the floor y, nothing under it was written below the floor")
    for lz in range(N):
        z = p.oz + lz
        x = p.ox
        while x < p.ox + N:
            gy = p.g(x, z)
            xe = x
            while xe + 1 < p.ox + N and p.g(xe + 1, z) == gy:
                xe += 1
            if gy == p.F:
                out.append("fill %d %d %d %d %d %d %s" % (x, p.F, z, xe, p.F, z, surface))
            else:
                out.append("fill %d %d %d %d %d %d minecraft:air" % (x, gy + 1, z, xe, p.F, z))
            x = xe + 1
    return out


def files(doc, g):
    pl = plan(doc, g)
    out = {"pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                               "Cobblers: the Pallet crushed house (tools/crushed_house.py)"}}, indent=2) + "\n"}
    for name, lines in (("build", build_lines(doc, pl)), ("restore", restore_lines(doc, pl))):
        lines = function_limits.ensure_loaded(lines)
        bad = function_limits.check_lines(lines, name)
        if bad:
            raise HouseError("%s: %d command(s) the server would refuse: %s" % (name, len(bad), bad[:3]))
        out["data/%s/function/%s/%s.mcfunction" % (NS, FN, name)] = "\n".join(lines) + "\n"
    return out, pl


def placement_steps(doc=None, g=None):
    """For tools/reapply.py (R16CH): hold the chunks, build, release. The box comes from the heightmap and the committed data
    alone, so listing the step needs no derived/ or build/."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    p = Plan(doc, g)
    c = doc["structure"]["clear"]
    hold = "%d %d %d %d" % (p.ox + c["x"][0], p.oz + c["z"][0], p.ox + c["x"][1], p.oz + c["z"][1])
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (NS, FN)), ("cmd", "forceload remove " + hold)]


# ----------------------------------------------------------------------------------------------------------- the probes
def probes(doc, pl):
    """Blocks that prove, in a world, that the house stands and the opening is open (tools/presence_audit.py reads them from
    data/world_probes.json). Each is a cell the plan fixes by ROLE, not by chance, with the state the plan puts there."""
    p = pl["plan"]
    o = (p.ox, p.y0, p.oz)

    def at(lx, dy, lz):
        return [o[0] + lx, o[1] + dy, o[2] + lz]

    def blk(what, lx, dy, lz, state=None, expect=True):
        cell = at(lx, dy, lz)
        want = state if state is not None else p.get(lx, dy, lz)
        return {"what": what, "block": cell + [want], "expect": expect}

    hx, hy, hz = pl["stands"]["hank"]
    lx_, ly_, lz_ = pl["stands"]["lena_out"]
    return [
        blk("the floor's planks under the pocket", 4, -1, 4),
        blk("the north-west corner post", 0, 0, 0),
        blk("the west gable's ridge course", 0, 6, 4),
        blk("the ridge brick over the west half", 1, 7, 4),
        blk("the opening (feet)", 4, 0, 8, "minecraft:air"),
        blk("the opening (head)", 4, 1, 8, "minecraft:air"),
        blk("the opening's lintel", 4, 2, 8),
        blk("the crawl (feet)", 4, 0, 7, "minecraft:air"),
        blk("the crawl (head)", 4, 1, 6, "minecraft:air"),
        blk("Lena's pocket (feet)", 4, 0, 4, "minecraft:air"),
        blk("Lena's pocket (head)", 4, 1, 4, "minecraft:air"),
        blk("the pocket's beam", 4, 2, 4),
        blk("the pocket's lantern", 3, 1, 3),
        blk("the front doorway is filled (feet)", 0, 0, 4, "minecraft:air", expect=False),
        blk("the front doorway is filled (head)", 0, 1, 4, "minecraft:air", expect=False),
        blk("the dropped lintel", 0, 2, 4),
        blk("the fallen oak on the shell", 6, 3, 4),
        {"what": "Hank's stand is clear (feet)", "block": [hx, hy, hz, "minecraft:air"], "expect": True},
        {"what": "Hank's stand is clear (head)", "block": [hx, hy + 1, hz, "minecraft:air"], "expect": True},
        {"what": "Lena's stand after the rescue is clear (feet)", "block": [lx_, ly_, lz_, "minecraft:air"], "expect": True},
        {"what": "Lena's stand after the rescue is clear (head)", "block": [lx_, ly_ + 1, lz_, "minecraft:air"], "expect": True},
    ]


def committed_probes():
    doc = json.loads(PROBES.read_text(encoding="utf-8"))
    return doc["places"].get(PROBE_PLACE)


def probe_problems(doc, pl):
    want = probes(doc, pl)
    have = committed_probes()
    if have != want:
        return ["data/world_probes.json places.%s drifted from the plan (%s vs %s probes); run: python tools/crushed_house.py probes --write"
                % (PROBE_PLACE, "absent" if have is None else len(have), len(want))]
    return []


def write_probes(doc, pl):
    d = json.loads(PROBES.read_text(encoding="utf-8"))
    d["places"][PROBE_PLACE] = probes(doc, pl)
    PROBES.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def report(doc, pl):
    b = pl["blocks"]
    p = pl["plan"]
    kinds = {}
    for s in b.values():
        kinds[_base(s)] = kinds.get(_base(s), 0) + 1
    top = ", ".join("%s %d" % (k.split(":")[1], n) for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])[:6])
    return ["lot x%d..%d z%d..%d: floor y%d (max ground under the lot), house volume y%d..%d"
            % (p.ox, p.ox + N - 1, p.oz, p.oz + N - 1, p.F, p.y0, p.y0 + HOUSE_DY - 1),
            "blocks written: %d (%s); clear box x%d..%d z%d..%d y%d..%d" % (len(b), top, *pl["clear"][0:1], pl["clear"][2],
                                                                           pl["clear"][1], pl["clear"][3], *pl["clear_y"]),
            "opening: (%d, %d..%d, %d); Lena in (%d, %d, %d); Hank %s; Lena after %s"
            % (p.ox + OPENING[0], p.y0, p.y0 + 1, p.oz + OPENING[1], *pl["stands"]["lena_in"], pl["stands"]["hank"],
               pl["stands"]["lena_out"]),
            "steps: %s" % json.dumps([list(s) for s in placement_steps(doc, p.g)])]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "plan", "probes"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--write", action="store_true", help="probes: write data/world_probes.json")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, pl = files(doc, g)
    if a.cmd == "plan":
        print("\n".join(report(doc, pl)))
        return 0
    if a.cmd == "probes":
        if a.write:
            write_probes(doc, pl)
            print("crushed_house: wrote %d probes to %s" % (len(probes(doc, pl)), PROBES.relative_to(ROOT)))
        else:
            print(json.dumps(probes(doc, pl), indent=1))
        return 0
    drift = probe_problems(doc, pl)
    if drift:
        raise HouseError("crushed_house: " + "; ".join(drift))
    write(out_files, a.out)
    n = {k.rsplit("/", 1)[1]: sum(1 for l in v.splitlines() if l and not l.startswith("#"))
         for k, v in out_files.items() if k.endswith(".mcfunction")}
    print("crushed_house: %d files -> %s (commands: %s)" % (len(out_files), a.out, ", ".join("%s %d" % kv for kv in sorted(n.items()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
