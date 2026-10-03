#!/usr/bin/env python
"""The Copperway Khan in the south-east dunes, from data/dune_ruin.json: a half-buried caravanserai, its dug-out hall,
the sealed master's store under it, and the milestones of the dead freight road that lead to it from Fossick.

The owner, 2026-10-02: "the south needs places, not just creatures. Somewhere to find, something in it. The mansion
and the Ursaluna cave are the model." Every part is an existing, proven piece; nothing here is new machinery:

  the Khan      vanilla 1.21.1 blocks, seated the repository's way: the sand line S is max(ground under the outer
                walls), ground from tools/ground.py (the canonical heightmap, rounded), never a world. The Khan's
                original floor F is S - bury, so its arches are buried and their lintels lie flush with the sand. The
                buried rooms and the courtyard are NOT written: their sand is the dune's own (sand is a spawn
                condition, for Sandygast, and the ground there is sand already). What is written is the
                masonry, the gate passage's air at the sand line, the dug-out hall, the trench down to it, a solid
                corner tower with a copper cap and a lantern, and the lantern posts.
  the store     a 9 by 9 vault, 4 high, under the hall's west end: every block written, solid or air, including
                under_fill rows beneath its floor, so the Habitat Block's spawn box (a cube of spawn_range round the
                block) holds no air but the vault's. Reached through a bricked doorway in the hall's west wall, the
                sealed stair-head room behind it and a ladder under a trapdoor (the Lopunny cellar's way in).
  Cofagrigus    NOT in this pack: an ACTIVATED Habitat Block in data/habitat_blocks.json (placed by
                tools/habitat_blocks.py with every other block, R9E) in the middle of the vault floor, disguised as
                the floor, and a pool in data/spawns.json. This pack writes the floor it sits in, so it must run BEFORE
                R9E: run after, it would write sandstone over the block.
  the find      NOT in this pack: an ADR-002 cache in data/rewards.json (tools/rewards_pack.py), its trigger box
                beside the strongbox barrel this pack writes.
  Dessa Varn    NOT in this pack: a conversation in data/dialogue.json (compiled into cobblers_dialogue) and its
                ambient quest; placed by R18DU from npc_placements(), as the den keeper is.
  the road      the Copperway's milestones from outside Fossick's south edge to the gate, each on its own ground + 1.

  python tools/dune_ruin.py build  [--source-root R] [--out DIR]   write the pack
  python tools/dune_ruin.py report [--source-root R]               print the numbers, bounds and steps; writes nothing

The re-application (tools/reapply.py): placement_steps() is R9DU, BEFORE R9E; npc_placements() is R18DU.
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

DATA = ROOT / "data" / "dune_ruin.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_dune_ruin"
SCHEMA = "cobblers.dune-ruin/1"
NS = "cobblers"
FN = "dune_ruin"
PACK_FORMAT = 48  # Minecraft 1.21.1
CLEAR_MARGIN = 3
CLEAR_OVER = 4          # the clearing reaches this far over the highest block written in a column box
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class RuinError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise RuinError("%s: schema must be %s" % (path, SCHEMA))
    k, u = doc["khan"], doc["undercroft"]
    if not (0 < k["arcade"] < k["half"] - 2):
        raise RuinError("the arcade ring must stand inside the outer wall with rooms between")
    if u["air_height"] < 3 or u["air_height"] > u["interior_half"]:
        raise RuinError("the vault needs 3 to interior_half blocks of air: its spawn box is a cube of interior_half")
    if k["bury"] != 4:
        raise RuinError("bury is 4: the arches are 3 high and their lintels lie on the sand line")
    return doc


def _base(state):
    return state.split("[")[0].split("{")[0]


def _text(lines):
    return ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])


def wall_sign(facing, lines):
    return "minecraft:acacia_wall_sign[facing=%s,waterlogged=false]{front_text:{messages:[%s]}}" % (facing, _text(lines))


def standing_sign(rotation, lines):
    return "minecraft:acacia_sign[rotation=%d,waterlogged=false]{front_text:{messages:[%s]}}" % (rotation, _text(lines))


def weathered(lx, lz, mod):
    """A fixed pattern of missing blocks: one in `mod`, the same on every rebuild."""
    return (lx * 7 + lz * 13 + 101) % mod == 0


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """Two passes of blocks, {(x, y, z): state}: the structure, then what hangs on it or stands on it (a sign, a
    ladder, a trapdoor, a lantern, a carpet), so nothing attached is placed before what holds it up."""

    def __init__(self, doc, g):
        self.doc, self.g = doc, g
        self.cx, self.cz = doc["site"]["centre"]
        H = self.H = doc["khan"]["half"]
        self.A = doc["khan"]["arcade"]
        walls = [(self.cx + a, self.cz + b) for a in range(-H, H + 1) for b in range(-H, H + 1)
                 if max(abs(a), abs(b)) == H]
        self.S = max(g(x, z) for x, z in walls)
        self.F = self.S - doc["khan"]["bury"]
        self.solid, self.hung = {}, {}
        self.allowed = set(doc["blocks"]["ids"])

    def _put(self, into, x, y, z, state):
        if _base(state) not in self.allowed:
            raise RuinError("%s is not in data/dune_ruin.json blocks.ids" % _base(state))
        into[(x, y, z)] = state

    def put(self, lx, y, lz, state):
        self._put(self.solid, self.cx + lx, y, self.cz + lz, state)

    def hang(self, lx, y, lz, state):
        self._put(self.hung, self.cx + lx, y, self.cz + lz, state)

    def ground(self, lx, lz):
        return self.g(self.cx + lx, self.cz + lz)

    def blocks(self):
        out = dict(self.solid)
        out.update(self.hung)
        return out


def khan(p):
    """The outer wall, the arcade ring, the spurs between the ranges and the ranges' roofs."""
    b = p.doc["blocks"]
    H, A, F, S = p.H, p.A, p.F, p.S
    wall, trim, orn = b["wall"], b["trim"], b["ornament"]
    for lx in range(-H, H + 1):
        for lz in range(-H, H + 1):
            m = max(abs(lx), abs(lz))
            if m == H:
                # the outer wall: a footing under the floor, two courses over the sand, merlons on alternate blocks
                p.put(lx, F - 1, lz, trim)
                for y in range(F, F + 6):
                    p.put(lx, y, lz, wall)
                p.put(lx, F + 6, lz, trim)
                if (lx + lz) % 2 == 0 and not weathered(lx, lz, 5):
                    p.put(lx, F + 7, lz, wall)
            elif m == A:
                t = lz if abs(lx) == A else lx          # the coordinate along this side of the ring
                if abs(lx) == A and abs(lz) == A or t % 4 == 2:
                    for y in range(F, F + 4):              # a pier
                        p.put(lx, y, lz, wall)
                else:
                    # openings are left to the sand (F+1..F+3); where the dune lies lower, packed drift under the lintel
                    for y in range(max(p.ground(lx, lz) + 1, F + 1), F + 4):
                        p.put(lx, y, lz, b["under_fill"])
                # the lintel course flush with the sand line
                p.put(lx, F + 4, lz, orn if t % 4 == 0 else trim)
                p.put(lx, F + 5, lz, wall)
            elif m > A:
                spur = (abs(lz) == A and abs(lx) > A) or (abs(lx) == A and abs(lz) > A)
                if spur:
                    for y in range(F, F + 5):
                        p.put(lx, y, lz, wall)
                    p.put(lx, F + 5, lz, wall)
                elif not (weathered(lx, lz, 7) and p.ground(lx, lz) == S):
                    p.put(lx, F + 5, lz, wall)         # the range's roof, over the dune's own sand
                    # where the dune lies under the sand line, packed drift up to it: no dark gap under a roof
                    for y in range(max(p.ground(lx, lz) + 1, F + 1), S + 1):
                        p.put(lx, y, lz, b["under_fill"])


def gate(p):
    """The gatehouse over the north range's middle, and the passage at the sand line through it to the courtyard."""
    b = p.doc["blocks"]
    H, A, F = p.H, p.A, p.F
    top = p.doc["khan"]["gatehouse_top"]
    air = p.doc["khan"]["gate_air"]
    wall, trim, orn, cu = b["wall"], b["trim"], b["ornament"], b["copper"]
    lo, hi = F + 5, F + 5 + air - 1                     # the passage's air: over the sand that fills its lower half
    # the gatehouse: solid masonry lx -3..3, lz -H-1..-H+3, from the footing to its top
    for lx in range(-3, 4):
        for lz in range(-H - 1, -H + 4):
            for y in range(F - 1, F + top + 1):
                p.put(lx, y, lz, wall)
            perim = abs(lx) == 3 or lz in (-H - 1, -H + 3)
            if perim:
                p.put(lx, F + top, lz, cu)
                if (lx + lz) % 2 == 0:
                    p.put(lx, F + top + 1, lz, wall)
    # the passage through it, the north range and the arcade's gate bay
    for lx in (-1, 0, 1):
        for lz in range(-H - 1, -A + 1):
            for y in range(F + 1, F + 5):
                p.solid.pop((p.cx + lx, y, p.cz + lz), None)    # the lower half is the dune's sand, unwritten
            for y in range(lo, hi + 1):
                p.put(lx, y, lz, "minecraft:air")
            if lz > -H + 3:
                p.put(lx, hi + 1, lz, trim)                  # the passage's ceiling past the gatehouse
    for lz in range(-H + 4, -A):
        for side in (-2, 2):
            for y in range(F, hi + 2):
                p.put(side, y, lz, wall)
    # the arcade's gate bay: its piers carried up, a lintel over the passage
    for side in (-2, 2):
        for y in range(F, hi + 2):
            p.put(side, y, -A, wall)
    for lx in (-1, 0, 1):
        p.put(lx, hi + 1, -A, orn if lx == 0 else trim)
        p.put(lx, F + 4, -A, trim)
    # the north face: a chiseled frame, a cut lintel with a copper keystone
    face = -H - 1
    for y in range(lo, hi + 1):
        p.put(-2, y, face, orn)
        p.put(2, y, face, orn)
    for lx in (-1, 0, 1):
        p.put(lx, hi + 1, face, cu if lx == 0 else trim)
        p.put(lx, hi + 2, face, orn)


def tower(p):
    """A solid masonry tower on the north-west corner, a copper cap, a lantern on top."""
    b = p.doc["blocks"]
    t = p.doc["khan"]["tower"]
    tx, tz = t["corner"]
    h = t["half"]
    F = p.F
    top = F + t["top"]
    cu = b["copper"]
    for lx in range(tx - h, tx + h + 1):
        for lz in range(tz - h, tz + h + 1):
            for y in range(F - 1, top + 1):
                band = (y - F) % 5 == 4
                edge = max(abs(lx - tx), abs(lz - tz)) == h
                p.put(lx, y, lz, b["ornament"] if band and edge else b["trim"])
    stairs_face = {(0, -1): "south", (0, 1): "north", (-1, 0): "east", (1, 0): "west"}
    for lx in range(tx - h, tx + h + 1):
        for lz in range(tz - h, tz + h + 1):
            dx, dz = lx - tx, lz - tz
            if max(abs(dx), abs(dz)) < h:
                p.put(lx, top + 1, lz, cu)
            elif abs(dx) == h and abs(dz) == h:
                p.put(lx, top + 1, lz, cu)
            else:
                key = (0 if abs(dx) != h else (1 if dx > 0 else -1), 0 if abs(dz) != h else (1 if dz > 0 else -1))
                p.put(lx, top + 1, lz, "minecraft:waxed_oxidized_cut_copper_stairs[facing=%s,half=bottom,shape=straight,"
                      "waterlogged=false]" % stairs_face[key])
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx == 0 and dz == 0:
                p.put(tx, top + 2, tz, cu)
            elif dx == 0 or dz == 0:
                p.put(tx + dx, top + 2, tz + dz, "minecraft:waxed_oxidized_cut_copper_stairs[facing=%s,half=bottom,"
                      "shape=straight,waterlogged=false]" % stairs_face[(dx, dz)])
            else:
                p.put(tx + dx, top + 2, tz + dz, cu)
    p.hang(tx, top + 3, tz, "minecraft:lantern[hanging=false,waterlogged=false]")
    return top + 3


def hall(p):
    """The dug-out hall: floor, air, its cross walls; the salvager's camp."""
    doc = p.doc
    b = doc["blocks"]
    F = p.F
    (x0, x1), (z0, z1) = doc["hall"]["x"], doc["hall"]["z"]
    for lx in range(x0, x1 + 1):
        for lz in range(z0, z1 + 1):
            edge = lx in (x0, x1) or lz in (z0, z1)
            p.put(lx, F, lz, b["trim"] if edge else b["wall"])
            for y in range(F + 1, F + 5):
                p.put(lx, y, lz, "minecraft:air")
            p.put(lx, F + 5, lz, b["wall"])
    # the cross walls at each end
    for lz in range(z0, z1 + 1):
        for lx in (x0 - 1, x1 + 1):
            for y in range(F, F + 6):
                p.put(lx, y, lz, b["wall"])
    # light: three lanterns on chains from the roof
    for lx in (-6, 0, 6):
        p.hang(lx, F + 4, 13, "minecraft:lantern[hanging=true,waterlogged=false]")
    # the camp, east of the arch: a bedroll, stores, a bench, the salvage
    for lz in (14, 15):
        p.hang(8, F + 1, lz, "minecraft:red_carpet")
    p.put(9, F + 1, 11, "minecraft:barrel[facing=up,open=false]")
    p.hang(9, F + 2, 11, "minecraft:lantern[hanging=false,waterlogged=false]")
    p.put(9, F + 1, 12, "minecraft:barrel[facing=west,open=false]")
    p.put(9, F + 1, 15, "minecraft:barrel[facing=up,open=false]")
    p.put(2, F + 1, 15, "minecraft:crafting_table")
    p.put(3, F + 1, 15, "minecraft:smithing_table")
    p.put(5, F + 1, 15, "minecraft:waxed_oxidized_cut_copper")
    p.put(6, F + 1, 15, "minecraft:waxed_weathered_cut_copper")
    p.put(6, F + 2, 15, "minecraft:waxed_cut_copper")
    p.put(7, F + 1, 15, "minecraft:waxed_oxidized_cut_copper")
    for lx in range(2, 6):
        p.hang(lx, F + 1, 12, "minecraft:brown_carpet")
    # the west end: two pots by the bricked door, and the company's plate over it
    p.put(-9, F + 1, 11, "minecraft:decorated_pot[cracked=false,facing=south,waterlogged=false]")
    p.put(-9, F + 1, 15, "minecraft:decorated_pot[cracked=true,facing=north,waterlogged=false]")
    p.hang(x0, F + 3, 12, wall_sign("east", doc["signs"]["store"]))


def trench(p):
    """The salvager's cut from the courtyard's sand down to the hall's middle arch, and the arch itself opened."""
    doc = p.doc
    b = doc["blocks"]
    F, S, A = p.F, p.S, p.A
    (x0, x1), (z0, z1) = doc["trench"]["x"], doc["trench"]["z"]
    for lx in range(x0, x1 + 1):
        for k, lz in enumerate(range(z0, z1 + 1)):
            step = F + 3 - k                              # z0: F+3 ... z1: F (the old paving)
            if lz == z1:
                p.put(lx, step, lz, b["wall"])
            else:
                p.put(lx, step, lz, "minecraft:sandstone_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]")
            for y in range(step + 1, S + 1):
                p.put(lx, y, lz, "minecraft:air")
        # the arch: open, paved
        p.put(lx, F, A, b["wall"])
        for y in range(F + 1, F + 4):
            p.put(lx, y, A, "minecraft:air")
    # lantern posts at its head, and the salvager's board
    for lx in (x0 - 1, x1 + 1):
        lz = z0 - 1
        y = p.ground(lx, lz)
        p.put(lx, y + 1, lz, "minecraft:acacia_fence[east=false,west=false,north=false,south=false,waterlogged=false]")
        p.hang(lx, y + 2, lz, "minecraft:lantern[hanging=false,waterlogged=false]")
    lx, lz = x1 + 2, z0 - 1
    p.hang(lx, p.ground(lx, lz) + 1, lz, standing_sign(8, doc["signs"]["dig"]))


def courtyard(p):
    """The choked well-head at the courtyard's middle, and the gate's lantern posts outside."""
    S = p.S
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx or dz:
                p.put(dx, p.ground(dx, dz) + 1, dz, "minecraft:sandstone_wall[east=none,north=none,south=none,"
                      "up=true,waterlogged=false,west=none]")
    for lx in (-3, 3):
        lz = -p.H - 3
        y = p.ground(lx, lz)
        p.put(lx, y + 1, lz, "minecraft:acacia_fence[east=false,west=false,north=false,south=false,waterlogged=false]")
        p.hang(lx, y + 2, lz, "minecraft:lantern[hanging=false,waterlogged=false]")
    return S


def undercroft(p):
    """The master's store: the vault, its stair-head room, the bricked doorway, the ladder and the strongbox."""
    doc = p.doc
    b = doc["blocks"]
    u = doc["undercroft"]
    F = p.F
    ux, uz = u["centre_local"]
    n = u["interior_half"]
    air = u["air_height"]
    floor = F - air - 1                                    # the ceiling is F, the air under it, the floor under that
    # the ceiling: the Khan's floor level over the whole vault, wall to wall
    for lx in range(ux - n - 1, ux + n + 2):
        for lz in range(uz - n - 1, uz + n + 2):
            p.put(lx, F, lz, b["wall"])
            edge = max(abs(lx - ux), abs(lz - uz)) == n + 1
            for y in range(floor, F):
                if edge:
                    p.put(lx, y, lz, b["vault_wall"])
                elif y == floor:
                    ring = max(abs(lx - ux), abs(lz - uz)) == n
                    p.put(lx, y, lz, "minecraft:terracotta" if ring else b["vault_floor"])
                else:
                    p.put(lx, y, lz, "minecraft:air")
            if not edge:
                for y in range(floor - u["under_fill"], floor):
                    p.put(lx, y, lz, b["under_fill"])
    p.put(ux, floor, uz, b["vault_floor"])                 # the Habitat Block's cell: the floor it is disguised as
    # four pillars, two soul lanterns from the ceiling
    for dx in (-2, 2):
        for dz in (-2, 2):
            for y in range(floor + 1, F):
                p.put(ux + dx, y, uz + dz, b["ornament"] if y in (floor + 1, F - 1) else b["trim"])
    for dx in (-2, 2):
        p.hang(ux + dx, F - 1, uz, "minecraft:soul_lantern[hanging=true,waterlogged=false]")
    # the strongbox, pots, the master's plate
    bx, bz = doc["find"]["barrel_local"]
    p.put(bx, floor + 1, bz, "minecraft:barrel[facing=west,open=false]")
    p.put(ux - n, floor + 1, uz - n, "minecraft:decorated_pot[cracked=false,facing=south,waterlogged=false]")
    p.put(ux + n, floor + 1, uz - n, "minecraft:decorated_pot[cracked=true,facing=south,waterlogged=false]")
    p.put(ux + n, floor + 1, uz + n, "minecraft:decorated_pot[cracked=false,facing=north,waterlogged=false]")
    for lx in range(ux - 1, ux + 2):
        p.put(lx, floor + 1, uz - n, "minecraft:orange_terracotta")
    p.hang(ux, floor + 2, uz - n, wall_sign("south", doc["signs"]["vault"]))
    # the stair-head room in the south-west corner: floor, air, roof; sealed
    (ax0, ax1), (az0, az1) = u["antechamber"]["x"], u["antechamber"]["z"]
    for lx in range(ax0, ax1 + 1):
        for lz in range(az0, az1 + 1):
            p.put(lx, F, lz, b["wall"])
            for y in range(F + 1, F + 5):
                p.put(lx, y, lz, "minecraft:air")
            p.put(lx, F + 5, lz, b["wall"])
    p.hang(ax1 - 1, F + 1, az0 + 1, "minecraft:soul_lantern[hanging=false,waterlogged=false]")
    # the bricked doorway in the hall's west wall: plain sandstone in a chiseled frame
    dx_, dz_ = u["bricked_door_local"]
    for y in (F + 1, F + 2):
        p.put(dx_, y, dz_, b["patch"])
    for y in (F + 1, F + 2, F + 3):
        p.put(dx_, y, dz_ - 1, b["ornament"])
        p.put(dx_, y, dz_ + 1, b["ornament"])
    p.put(dx_, F + 3, dz_, b["trim"])
    # the ladder down the vault's west wall, under the trapdoor in the stair-head room's floor
    tx, tz = u["trapdoor_local"]
    for y in range(floor + 1, F):
        p.hang(tx, y, tz, "minecraft:ladder[facing=east,waterlogged=false]")
    p.hang(tx, F, tz, "minecraft:acacia_trapdoor[facing=east,half=top,open=false,powered=false,waterlogged=false]")
    p.solid.pop((p.cx + tx, F, p.cz + tz), None)
    return floor


def road(p):
    """The Copperway's milestones from outside Fossick to the gate: [(x, z, ground)]."""
    doc = p.doc
    r = doc["road"]
    b = doc["blocks"]
    x0, z0 = r["from"]
    x1, z1 = p.cx, p.cz - p.H - 3
    L = math.hypot(x1 - x0, z1 - z0)
    n = int(math.ceil(L / r["spacing"]))                  # even steps, none longer than spacing; the gate is the last
    posts = []
    for k in range(n):
        f = k / n
        x, z = int(round(x0 + (x1 - x0) * f)), int(round(z0 + (z1 - z0) * f))
        y = p.g(x, z)
        p._put(p.solid, x, y + 1, z, b["ornament"])
        p._put(p.solid, x, y + 2, z, b["trim"])
        if k % r["lantern_every"] == 0:
            p._put(p.hung, x, y + 3, z, "minecraft:lantern[hanging=false,waterlogged=false]")
        if k == 0:
            p._put(p.hung, x, y + 2, z - 1, wall_sign("north", doc["signs"]["road"]))
        posts.append((x, z, y))
    return posts


def plan(doc, g):
    p = Plan(doc, g)
    khan(p)
    gate(p)
    tower_top = tower(p)
    hall(p)
    trench(p)
    courtyard(p)
    floor = undercroft(p)
    posts = road(p)
    nx, nz = doc["npc"]["at_local"]
    npc = (p.cx + nx, p.F + 1, p.cz + nz)
    blocks = p.blocks()
    if any(blocks.get((npc[0], npc[1] + d, npc[2]), "minecraft:air") != "minecraft:air" for d in (0, 1)):
        raise RuinError("Dessa Varn's spot %s is not two blocks of air" % (npc,))
    ux, uz = doc["undercroft"]["centre_local"]
    H = p.H
    road_cells = {k for k in blocks if max(abs(k[0] - p.cx), abs(k[2] - p.cz)) > H + 3}
    khan_cells = set(blocks) - road_cells

    def box(cells):
        xs, ys, zs = zip(*cells)
        return {"min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]}
    tx0, tz0 = doc["find"]["trigger_local"]["x"], doc["find"]["trigger_local"]["z"]
    bx, bz = doc["find"]["barrel_local"]
    return {"plan": p, "S": p.S, "F": p.F, "vault_floor": floor, "tower_top": tower_top, "posts": posts, "npc": npc,
            "habitat_block": (p.cx + ux, floor, p.cz + uz), "blocks": blocks,
            "bounds": {"khan": box(khan_cells), "road": box(road_cells)},
            "barrel": (p.cx + bx, floor + 1, p.cz + bz),
            "trigger": {"min": [p.cx + tx0[0], floor + 1, p.cz + tz0[0]], "max": [p.cx + tx0[1], floor + 2, p.cz + tz0[1]]}}


# ---------------------------------------------------------------------------------------------------------- the pack
def _runs(blocks, top_down=False):
    """setblock and fill lines for {(x, y, z): state}, one fill per run of one state along x, bottom up (or top down)."""
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


def clear_boxes(pl):
    """[(x0, y0, z0, x1, y1, z1)]: the Khan's box and one per milestone, from the ground up past what is written."""
    p = pl["plan"]
    kb = pl["bounds"]["khan"]
    x0, z0 = kb["min"][0] - CLEAR_MARGIN, kb["min"][2] - CLEAR_MARGIN
    x1, z1 = kb["max"][0] + CLEAR_MARGIN, kb["max"][2] + CLEAR_MARGIN
    low = min(p.g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    out = [(x0, low + 1, z0, x1, kb["max"][1] + CLEAR_OVER, z1)]
    for x, z, y in pl["posts"]:
        low = min(p.g(x + a, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1))
        out.append((x - 1, low + 1, z - 1, x + 1, y + 3 + CLEAR_OVER, z + 1))
    return out


def build_lines(doc, pl):
    p = pl["plan"]
    out = ["# Generated by tools/dune_ruin.py from data/dune_ruin.json. Re-run to rebuild; do not edit.",
           "# The Copperway Khan: the half-buried caravanserai, its dug-out hall, the sealed master's store, the milestones.",
           "# Run BEFORE R9E: the Habitat Block dune_ruin_undercroft_ward sits in the vault floor this writes.",
           "# 1. clear the plants, cacti and any tree over everything this writes"]
    for (x0, y0, z0, x1, y1, z1) in clear_boxes(pl):
        for tag in ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable", "minecraft:cactus"):
            out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the structure, bottom up (the vault first, so its ceiling is in before the sand over it is touched)")
    out += _runs({k: st for k, st in p.solid.items() if k not in p.hung})
    out.append("# 3. what hangs on it or stands on it, from the top: lanterns, signs, ladder, trapdoor, carpets")
    out += _runs(p.hung, top_down=True)
    return out


def files(doc, g):
    pl = plan(doc, g)
    lines = function_limits.ensure_loaded(build_lines(doc, pl))
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise RuinError("build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    out = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Copperway Khan in the south-east dunes (tools/dune_ruin.py)"}},
                                  indent=2) + "\n",
        "data/%s/function/%s/build.mcfunction" % (NS, FN): "\n".join(lines) + "\n",
    }
    return out, pl


def hold_box(pl):
    """The x/z box the re-application force-loads: everything written and cleared."""
    bs = clear_boxes(pl)
    return (min(b[0] for b in bs), min(b[2] for b in bs), max(b[3] for b in bs), max(b[5] for b in bs))


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, as R9DU BEFORE R9E: hold the chunks, build, release (R9LH's shape)."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    pl = plan(doc, g)
    hold = "%d %d %d %d" % hold_box(pl)
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (NS, FN)),
            ("cmd", "forceload remove " + hold)]


def npc_placements(doc=None, g=None):
    """[(conversation id, (x, y, z), npc class)] for tools/reapply.py's "npc" action (R18DU)."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    conv = next((c for c in dl["conversations"] if c["id"] == doc["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        raise RuinError("%s is not a conversation with an NPC in data/dialogue.json" % doc["npc"]["conversation"])
    pl = plan(doc, g)
    return [(conv["id"], pl["npc"], "%s:%s" % (doc["namespace"], conv["npc_id"]))]


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def report(doc, pl, g):
    b = pl["blocks"]
    p = pl["plan"]
    posts = pl["posts"]
    ys = [y for _x, _z, y in posts]
    lines = ["site %s: sand line S y%d (max ground under the outer walls), Khan floor F y%d, vault floor y%d, tower lantern y%d"
             % (doc["site"]["centre"], pl["S"], pl["F"], pl["vault_floor"], pl["tower_top"]),
             "blocks written: %d (air %d)" % (len(b), sum(1 for s in b.values() if s == "minecraft:air")),
             "bounds: %s" % json.dumps(pl["bounds"]),
             "habitat block (vault floor centre): %s; Dessa Varn stands at %s" % (pl["habitat_block"], pl["npc"]),
             "find: barrel %s, trigger %s" % (pl["barrel"], json.dumps(pl["trigger"])),
             "road: %d milestones, ground y%d..%d, first %s, last %s" % (len(posts), min(ys), max(ys), posts[0], posts[-1]),
             "steps (R9DU, before R9E): %s" % json.dumps([list(s) for s in placement_steps(doc, g)])]
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "report"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, pl = files(doc, g)
    if a.cmd == "report":
        print("\n".join(report(doc, pl, g)))
        return 0
    write(out_files, a.out)
    n = sum(1 for l in out_files["data/%s/function/%s/build.mcfunction" % (NS, FN)].splitlines()
            if l and not l.startswith("#"))
    print("dune_ruin: %d files -> %s (build: %d commands)" % (len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
