#!/usr/bin/env python
"""The Drovers' Hollow in the Rift Foot, from data/drovers_hollow.json: a longbarn, its fold, the spring, the well
behind it and the old working under the bank that holds the find.

The owner, 2026-10-02 (relayed): "the southern map is empty ... the south needs places, not just creatures. Somewhere
to find, something in it." The brief's idea was a cave-barn cut into the Rift's south wall; measured, there is no such
wall outside the Rift's sculpted rim (data/drovers_hollow.json site.why_not_the_wall), so the barn is BUILT in the dry
ravine's hollow, and only the working under it is carved. Every part is a proven pattern; nothing here is new machinery:

  the barn      vanilla 1.21.1 blocks, seated the repository's way (tools/lopunny_house.py, tools/shrines.py): the
                floor on max(ground under the walls) + 1 with a cobblestone foundation down to the ground, ground from
                tools/ground.py (the canonical heightmap, rounded), never a world. Trees, leaves and replaceable plants
                over it are cleared first. Stalls, a hay loft, a spring trough of water cauldrons, ramps at both doors.
  the working   carved the Ursaluna den's way (tools/ursaluna_cave.py): a stone shell filled SOLID first, `margin`
                blocks beyond every void block and never in the top `keep_natural_top` blocks of a column, then the
                void (a one-block well shaft, a level drift, a store) cut out of it. Reached by a ladder down the well
                from a trapdoor behind the trough. A barrel in the store is the scenery of the find.
  the find      NOT in this pack: a cache in data/rewards.json (drovers_hollow_store), granted once per player by
                tools/rewards_pack.py's advancement when they reach the store's east end (ADR-002).
  the herd      NOT in this pack: an ACTIVATED Habitat Block in data/habitat_blocks.json (drovers_hollow_fold_ward,
                placed by tools/habitat_blocks.py at R9E) in the fold's floor, and its pool in data/spawns.json. This
                pack writes the fold floor the block sits in, so it runs BEFORE R9E (step R9HF).
  the drover    NOT in this pack: a conversation in data/dialogue.json compiled into cobblers_dialogue by
                tools/compile_dialogue.py --all; npc_placements() names where R18HF (after R17N) puts him.

  python tools/drovers_hollow.py [build] [--source-root R] [--out DIR]   write the pack
  python tools/drovers_hollow.py --report [--source-root R]             the numbers, cover and steps; writes nothing
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "drovers_hollow.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_drovers_hollow"
SCHEMA = "cobblers.drovers-hollow/1"
NS = "cobblers"
FN = "drovers_hollow"
PACK_FORMAT = 48  # Minecraft 1.21.1
CLEAR_MARGIN = 3
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class HollowError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise HollowError("%s: schema must be %s" % (path, SCHEMA))
    w = doc["working"]
    if w["tunnel"]["height"] < 2 or w["chamber"]["height"] < 2:
        raise HollowError("a player needs two blocks of air to walk the working")
    if w["floor_below_barn_floor"] < 3:
        raise HollowError("the working is under the barn floor, not in it")
    b = doc["barn"]
    if not (b["loft"]["above_floor"] >= 4 and b["loft"]["above_floor"] < b["wall_height"] + 1):
        raise HollowError("the loft floor needs three blocks of headroom under it and must stand inside the walls")
    return doc


def _base(state):
    return state.split("[")[0].split("{")[0]


def wall_sign(facing, lines):
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
    return "minecraft:spruce_wall_sign[facing=%s]{front_text:{messages:[%s]}}" % (facing, q)


def fence(e=False, w=False, n=False, s=False, kind="minecraft:spruce_fence"):
    return "%s[east=%s,west=%s,north=%s,south=%s,waterlogged=false]" % (
        kind, str(e).lower(), str(w).lower(), str(n).lower(), str(s).lower())


def lantern(hanging):
    return "minecraft:lantern[hanging=%s,waterlogged=false]" % ("true" if hanging else "false")


def stair(facing):
    return "minecraft:spruce_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]" % facing


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """Two passes of blocks, {(x, y, z): state} in world coordinates: the structure (the shell, the voids, the barn, the
    fold), then what hangs on it (a ladder, a lantern, a chain, a sign, the trapdoor), so nothing attached is placed
    before what holds it."""

    def __init__(self, doc, g):
        self.doc, self.g = doc, g
        b = doc["barn"]
        self.x0, self.x1 = b["x"]
        self.z0, self.z1 = b["z"]
        self.zc = (self.z0 + self.z1) // 2
        self.bf = max(g(x, z) for x in range(self.x0, self.x1 + 1) for z in range(self.z0, self.z1 + 1)) + 1
        self.wf = self.bf - doc["working"]["floor_below_barn_floor"]
        self.solid, self.hung = {}, {}
        self.allowed = set(doc["blocks"]["ids"])

    def _chk(self, state):
        if _base(state) not in self.allowed:
            raise HollowError("%s is not in data/drovers_hollow.json blocks.ids" % _base(state))

    def put(self, x, y, z, state):
        self._chk(state)
        self.solid[(x, y, z)] = state

    def hang(self, x, y, z, state):
        self._chk(state)
        self.hung[(x, y, z)] = state

    def blocks(self):
        out = dict(self.solid)
        out.update(self.hung)
        return out


# --------------------------------------------------------------------------------------------------------- the working
def working_voids(doc, p):
    """The set of (x, y, z) the working cuts: the well shaft, the drift and the store."""
    w = doc["working"]
    out = set()
    t, c = w["tunnel"], w["chamber"]
    for box, h in ((t, t["height"]), (c, c["height"])):
        for x in range(box["x"][0], box["x"][1] + 1):
            for z in range(box["z"][0], box["z"][1] + 1):
                for y in range(p.wf + 1, p.wf + 1 + h):
                    out.add((x, y, z))
    wx, wz = doc["well"]["at"]
    for y in range(p.wf + 1, p.bf):
        out.add((wx, y, wz))
    return out


def working_shell(doc, p, voids):
    """Every block within `margin` (Chebyshev, all three axes) of a void, at or below its column's ground minus
    keep_natural_top, that is not itself a void: filled solid before the void is cut."""
    w = doc["working"]
    m, keep = int(w["margin"]), int(w["keep_natural_top"])
    shell = set()
    cols = {}
    for (x, y, z) in voids:
        for dx in range(-m, m + 1):
            for dz in range(-m, m + 1):
                cx, cz = x + dx, z + dz
                top = cols.get((cx, cz))
                if top is None:
                    top = cols[(cx, cz)] = p.g(cx, cz) - keep
                for dy in range(-m, m + 1):
                    if y + dy <= top:
                        shell.add((cx, y + dy, cz))
    return shell - voids


def working(doc, p):
    w = doc["working"]
    voids = working_voids(doc, p)
    for k in sorted(working_shell(doc, p, voids)):
        p.put(*k, "minecraft:stone")
    t, c = w["tunnel"], w["chamber"]
    wf = p.wf
    # the floors: gravel in the drift, cobblestone in the store, under every void column of each
    for x in range(t["x"][0], t["x"][1] + 1):
        for z in range(t["z"][0], t["z"][1] + 1):
            p.put(x, wf, z, "minecraft:gravel")
    for x in range(c["x"][0], c["x"][1] + 1):
        for z in range(c["z"][0], c["z"][1] + 1):
            p.put(x, wf, z, "minecraft:cobblestone")
    # props: stripped spruce posts standing IN the drift's walls and a beam across its roof, every 5 blocks; beams across
    # the store's roof. Shell positions only: a prop never stands in the air the working walks through
    th = t["height"]
    for x in range(t["x"][0] + 4, t["x"][1], 5):
        for z in (t["z"][0] - 1, t["z"][1] + 1):
            for y in range(wf + 1, wf + 1 + th):
                p.put(x, y, z, "minecraft:stripped_spruce_log[axis=y]")
        for z in range(t["z"][0] - 1, t["z"][1] + 2):
            p.put(x, wf + 1 + th, z, "minecraft:stripped_spruce_log[axis=z]")
    ch = c["height"]
    for x in (c["x"][0] + 2, c["x"][1] - 2):
        for z in range(c["z"][0] - 1, c["z"][1] + 2):
            p.put(x, wf + 1 + ch, z, "minecraft:stripped_spruce_log[axis=z]")
    # the void, cut last of the structure
    for k in voids:
        p.put(*k, "minecraft:air")
    # the store: the barrel (scenery: the find is data/rewards.json's cache), hay, the sign over the barrel
    cz = (c["z"][0] + c["z"][1]) // 2
    ex = c["x"][1]
    p.put(ex, wf + 1, cz, "minecraft:barrel[facing=west,open=false]")
    for z, dy in ((c["z"][0], 1), (c["z"][0] + 1, 1), (c["z"][0], 2), (c["z"][1], 1)):
        p.put(c["x"][0] + 1, wf + dy, z, "minecraft:hay_block[axis=y]")
    p.hang(ex, wf + 2, cz, wall_sign("west", doc["blocks"]["signs"]["store"]))
    # light: lanterns hanging from the drift's roof every 7 blocks and two in the store
    tz = (t["z"][0] + t["z"][1]) // 2
    for x in range(t["x"][0] + 6, t["x"][1] + 1, 7):
        p.hang(x, wf + th, tz, lantern(True))
    p.hang(c["x"][0] + 2, wf + ch, c["z"][0] + 2, lantern(True))
    p.hang(c["x"][1] - 2, wf + ch, c["z"][1] - 2, lantern(True))
    # the way down: a ladder up the well's west face, under the trapdoor in the barn floor
    wx, wz = doc["well"]["at"]
    for y in range(wf + 1, p.bf):
        p.hang(wx, y, wz, "minecraft:ladder[facing=east,waterlogged=false]")
    p.hang(wx, p.bf, wz, "minecraft:spruce_trapdoor[facing=east,half=top,open=false,powered=false,waterlogged=false]")
    return voids


# ------------------------------------------------------------------------------------------------------------ the barn
def ramp(p, cols, dx, dz, facing, top):
    """Steps down from a doorway sill at `top` (the floor block's y) over the columns `cols`, one block a step in the
    (dx, dz) direction, each a spruce stair on a cobblestone foot, until a step would be at or under the ground."""
    for j in range(0, 16):
        y = top - j
        done = True
        for (x, z) in cols:
            sx, sz = x + dx * (j + 1), z + dz * (j + 1)
            if y <= p.g(sx, sz):
                continue
            done = False
            for fy in range(p.g(sx, sz) + 1, y):
                p.put(sx, fy, sz, "minecraft:cobblestone")
            p.put(sx, y, sz, stair(facing))
        if done:
            return


def barn(doc, p):
    b = doc["barn"]
    x0, x1, z0, z1, zc, bf = p.x0, p.x1, p.z0, p.z1, p.zc, p.bf
    wh = b["wall_height"]
    over = b["roof_overhang"]
    a0, a1 = b["aisle_z"]
    lx0, lx1 = b["loft"]["x"]
    loft_y = bf + b["loft"]["above_floor"]
    # the foundation, down to the ground under every column of the footprint
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            for y in range(p.g(x, z) + 1, bf):
                p.put(x, y, z, "minecraft:cobblestone")
    # the floor: a cobblestone ring and aisle, coarse dirt in the stalls, cobblestone under the loft
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            ring = x in (x0, x1) or z in (z0, z1)
            stalls = not ring and not (a0 <= z <= a1) and x < lx0
            p.put(x, bf, z, "minecraft:coarse_dirt" if stalls else "minecraft:cobblestone")
    posts_x = set(range(x0, x1 + 1, 4)) | {x1}
    posts_z = {z0, zc, z1}
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            ring = x in (x0, x1) or z in (z0, z1)
            for dy in range(1, wh + 1):
                y = bf + dy
                if not ring:
                    p.put(x, y, z, "minecraft:air")
                elif dy == 1:
                    p.put(x, y, z, "minecraft:mossy_cobblestone" if (x + z) % 3 == 0 else "minecraft:cobblestone")
                elif (z in (z0, z1) and x in posts_x) or (x in (x0, x1) and z in posts_z):
                    p.put(x, y, z, "minecraft:stripped_spruce_log[axis=y]")
                elif dy == wh:
                    p.put(x, y, z, "minecraft:stripped_spruce_log[axis=%s]" % ("x" if z in (z0, z1) else "z"))
                else:
                    p.put(x, y, z, "minecraft:spruce_planks")
    # slatted vents in the long walls: a fence in a one-block opening
    for x in (x0 + 6, x0 + 14, x0 + 22):
        if x0 < x < x1 and x not in posts_x:
            for z in (z0, z1):
                p.put(x, bf + 3, z, fence())
    # the cattle doorway in the west gable, open (the doors are long gone), and the man's doorway to the fold
    dz0, dz1 = b["west_doorway_z"]
    for z in range(dz0, dz1 + 1):
        for dy in range(1, b["west_doorway_height"] + 1):
            p.put(x0, bf + dy, z, "minecraft:air")
    sx = b["south_doorway_x"]
    for dy in (1, 2):
        p.put(sx, bf + dy, z1, "minecraft:air")
    # the roof: a gable whose ridge runs east-west, a stair a row up and in, from the overhang to the ridge
    h = zc - z0
    rise = h + over
    for k in range(0, rise + 1):
        y = bf + wh + 1 + k
        r = rise - k
        for x in range(x0 - over, x1 + over + 1):
            if r == 0:
                p.put(x, y, zc, "minecraft:spruce_planks")
            else:
                p.put(x, y, zc - r, stair("south"))
                p.put(x, y, zc + r, stair("north"))
        for z in range(zc - (r - 1), zc + r):
            for x in range(x0, x1 + 1):
                p.put(x, y, z, "minecraft:spruce_planks" if x in (x0, x1) else "minecraft:air")
    ridge = bf + wh + 1 + rise
    # stalls: fence partitions from each long wall to the aisle, a manger (hay) at the back of each stall
    for x in b["stall_partitions_x"]:
        for zs in ((z0 + 1, a0 - 1), (a1 + 1, z1 - 1)):
            for z in range(zs[0], zs[1] + 1):
                p.put(x, bf + 1, z, fence(n=z > zs[0] or zs[0] == z0 + 1, s=z < zs[1] or zs[1] == z1 - 1))
    parts = sorted(b["stall_partitions_x"])
    for xa, xb in zip(parts, parts[1:]):
        mx = (xa + xb) // 2
        p.put(mx, bf + 1, z0 + 1, "minecraft:hay_block[axis=y]")
        if not (xa < sx < xb):
            p.put(mx, bf + 1, z1 - 1, "minecraft:hay_block[axis=y]")
    p.put(x0 + 1, bf + 1, z1 - 1, "minecraft:composter[level=0]")
    # the loft: a plank floor over the east third, railed on its open west edge but for the ladder's landing
    for x in range(lx0, lx1 + 1):
        for z in range(z0 + 1, z1):
            p.put(x, loft_y, z, "minecraft:spruce_planks")
    rail = [z for z in range(z0 + 3, z1)]
    for z in rail:
        p.put(lx0, loft_y + 1, z, fence(n=z > rail[0], s=z < rail[-1] or z == z1 - 1))
    for x in range(lx1 - 1, lx1 + 1):
        for z in range(z0 + 2, z1 - 1):
            p.put(x, loft_y + 1, z, "minecraft:hay_block[axis=y]")
    for z in range(z0 + 3, zc):
        p.put(lx1, loft_y + 2, z, "minecraft:hay_block[axis=y]")
    # the spring: a trough of full water cauldrons across the aisle's end, under the loft
    for z in range(doc["spring"]["trough_z"][0], doc["spring"]["trough_z"][1] + 1):
        p.put(doc["spring"]["trough_x"], bf + 1, z, doc["spring"]["block"])
    # the well-head behind it: a ring of mossy stone-brick slabs round the trapdoor
    wx, wz = doc["well"]["at"]
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx or dz:
                p.put(wx + dx, bf + 1, wz + dz, "minecraft:mossy_stone_brick_slab[type=bottom,waterlogged=false]")
    # ramps down from both doorways to the ground
    ramp(p, [(x0, z) for z in range(dz0, dz1 + 1)], -1, 0, "east", bf)
    ramp(p, [(sx, z1)], 0, 1, "north", bf)
    # --- what hangs
    lx = b["loft"]["x"][0] - 1
    for y in range(bf + 1, loft_y + 2):
        p.hang(lx, y, z0 + 1, "minecraft:ladder[facing=south,waterlogged=false]")
    # over the aisle, on long chains from the ridge so they hang at the walls' top and light the stalls' floors
    for x in (x0 + 3, x0 + 9, x0 + 14):
        for y in range(bf + wh + 1, ridge):
            p.hang(x, y, zc, "minecraft:chain[axis=y,waterlogged=false]")
        p.hang(x, bf + wh, zc, lantern(True))
    # one over the loft, on a shorter chain so it hangs clear of the hay
    for y in range(ridge - 3, ridge):
        p.hang(x1 - 4, y, zc, "minecraft:chain[axis=y,waterlogged=false]")
    p.hang(x1 - 4, ridge - 4, zc, lantern(True))
    p.hang(doc["spring"]["trough_x"] - 2, loft_y - 1, zc, lantern(True))
    for z in (z0 + 2, z1 - 2):
        p.hang(x1 - 2, loft_y - 1, z, lantern(True))       # the corners under the loft, either side of the well
    p.hang(lx0 + 1, loft_y + 1, z1 - 2, lantern(False))
    signs = doc["blocks"]["signs"]
    p.hang(x1 - 1, bf + 2, wz - 2, wall_sign("west", signs["spring"]))
    p.hang(x1 - 1, bf + 2, wz + 2, wall_sign("west", signs["well"]))
    p.hang(x0 - 1, bf + 3, dz0 - 1, wall_sign("west", signs["door"]))
    # lanterns on posts either side of the cattle doorway, on the ground's own height
    for z in (dz0 - 3, dz1 + 3):
        x = x0 - 2
        gy = p.g(x, z)
        p.put(x, gy + 1, z, fence())
        p.put(x, gy + 2, z, fence())
        p.hang(x, gy + 3, z, lantern(False))
    return ridge


# ------------------------------------------------------------------------------------------------------------ the fold
def fold(doc, p):
    f = doc["fold"]
    fx0, fx1 = f["x"]
    fz0, fz1 = f["z"]
    gate = (f["gate_x"], fz0)
    ring = [(x, z) for x in range(fx0, fx1 + 1) for z in range(fz0, fz1 + 1)
            if x in (fx0, fx1) or z in (fz0, fz1)]
    # the trodden floor in the ground's own top block, inside and under the ring
    for x in range(fx0, fx1 + 1):
        for z in range(fz0, fz1 + 1):
            p.put(x, p.g(x, z), z, "minecraft:coarse_dirt")
    posts = {(x, p.g(x, z) + 1, z) for x, z in ring}
    gy = p.g(*gate) + 1
    for (x, y, z) in sorted(posts):
        if (x, z) == gate:
            p.put(x, y, z, "minecraft:spruce_fence_gate[facing=north,open=false,in_wall=false,powered=false]")
            continue

        def link(nx, nz, axis):
            q = (nx, y, nz)
            if (nx, nz) == gate:
                return y == gy and axis == "x"
            return q in posts
        p.put(x, y, z, fence(e=link(x + 1, z, "x"), w=link(x - 1, z, "x"), n=link(x, z - 1, "z"), s=link(x, z + 1, "z")))
    # lanterns on the four corner posts
    for x, z in ((fx0, fz0), (fx1, fz0), (fx0, fz1), (fx1, fz1)):
        p.hang(x, p.g(x, z) + 2, z, lantern(False))
    # the lane from the barn's south doorway ramp to the gate, and where the drover stands: a path in the ground's top
    sx = doc["barn"]["south_doorway_x"]
    for z in range(p.z1 + 1, fz0):
        if (sx, p.g(sx, z) + 1, z) not in p.solid and (sx, p.g(sx, z), z) not in p.solid:
            p.put(sx, p.g(sx, z), z, "minecraft:dirt_path")
    nx, nz = doc["npc"]["at_xz"]
    p.put(nx, p.g(nx, nz), nz, "minecraft:dirt_path")
    cx, cz = (fx0 + fx1) // 2, (fz0 + fz1) // 2
    return (cx, p.g(cx, cz), cz)


def plan(doc, g):
    p = Plan(doc, g)
    ridge = barn(doc, p)
    voids = working(doc, p)
    hb = fold(doc, p)
    nx, nz = doc["npc"]["at_xz"]
    npc = (nx, g(nx, nz) + 1, nz)
    blocks = p.blocks()
    for q in (npc, (npc[0], npc[1] + 1, npc[2])):
        if blocks.get(q, "minecraft:air") != "minecraft:air":
            raise HollowError("the drover's spot %s is not two blocks of air" % (npc,))
    c = doc["working"]["chamber"]
    cz = (c["z"][0] + c["z"][1]) // 2
    barrel = (c["x"][1], p.wf + 1, cz)
    above = [(x, z) for (x, y, z), st in blocks.items() if y > g(x, z)]
    xs = [k[0] for k in above]
    zs = [k[1] for k in above]
    clear = (min(xs) - CLEAR_MARGIN, min(zs) - CLEAR_MARGIN, max(xs) + CLEAR_MARGIN, max(zs) + CLEAR_MARGIN)
    low = min(g(x, z) for x in range(clear[0], clear[2] + 1) for z in range(clear[1], clear[3] + 1))
    ks = list(blocks)
    bbox = (min(k[0] for k in ks), min(k[2] for k in ks), max(k[0] for k in ks), max(k[2] for k in ks))
    return {"plan": p, "bf": p.bf, "wf": p.wf, "ridge": ridge, "voids": voids, "habitat_block": hb, "npc": npc,
            "barrel": barrel, "clear": clear, "clear_y": (low + 1, ridge + 2), "blocks": blocks, "bbox": bbox,
            "y_range": (min(k[1] for k in ks), max(k[1] for k in ks))}


def cover(pl, g):
    """{void (x, y, z): ground over its column minus the void block's y}, for every void block whose column is outside
    the barn's footprint (inside it the barn's floor and foundation stand over the working)."""
    p = pl["plan"]
    out = {}
    for (x, y, z) in pl["voids"]:
        if p.x0 <= x <= p.x1 and p.z0 <= z <= p.z1:
            continue
        out[(x, y, z)] = g(x, z) - y
    return out


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
    x0, z0, x1, z1 = pl["clear"]
    y0, y1 = pl["clear_y"]
    out = ["# Generated by tools/drovers_hollow.py from data/drovers_hollow.json. Re-run to rebuild; do not edit.",
           "# The Drovers' Hollow: the longbarn, its fold, the spring, the well and the old working under the bank.",
           "# Run BEFORE R9E (step R9HF): the Habitat Block drovers_hollow_fold_ward sits in the fold floor this writes.",
           "# 1. clear the trees, plants and snow layers over everything this writes above the ground"]
    for tag in ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable"):
        out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out.append("# 2. the structure, bottom up: the working's shell, its void, the barn, the fold")
    out += _runs({k: st for k, st in p.solid.items() if k not in p.hung})
    out.append("# 3. what hangs on it, from the top: chains, lanterns, signs, ladders, the trapdoor")
    out += _runs(p.hung, top_down=True)
    return out


def files(doc, g):
    pl = plan(doc, g)
    lines = function_limits.ensure_loaded(build_lines(doc, pl))
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise HollowError("build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    out = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Drovers' Hollow (tools/drovers_hollow.py)"}}, indent=2) + "\n",
        "data/%s/function/%s/build.mcfunction" % (NS, FN): "\n".join(lines) + "\n",
    }
    return out, pl


# ---------------------------------------------------------------------------------------------- the re-application
def _hold(pl):
    x0, z0, x1, z1 = pl["bbox"]
    c = pl["clear"]
    return min(x0, c[0]), min(z0, c[1]), max(x1, c[2]), max(z1, c[3])


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, step R9HF BEFORE R9E: hold the chunks, build, release (R9LH's shape)."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    pl = plan(doc, g)
    hold = "%d %d %d %d" % _hold(pl)
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (NS, FN)),
            ("cmd", "forceload remove " + hold)]


def npc_placements(doc=None, g=None):
    """[(conversation id, (x, y, z), npc class)] for tools/reapply.py's "npc" action (R18HF): the drover's feet one
    above the ground at at_xz, his class the conversation's npc_id."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    conv = next((c for c in dl["conversations"] if c["id"] == doc["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        raise HollowError("%s is not a conversation with an NPC in data/dialogue.json" % doc["npc"]["conversation"])
    x, z = doc["npc"]["at_xz"]
    return [(conv["id"], (x, g(x, z) + 1, z), "%s:%s" % (NS, conv["npc_id"]))]


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------------------------------------- report
def sightline(g, frm, to, eye=1.62):
    """The least clearance (blocks) of the straight line from a standing eye at frm (x, z) to the point `to` (x, y, z)
    over the heightmap's ground, sampled every half block; negative means the ground hides it."""
    fx, fz = frm
    ey = g(fx, fz) + 1 + eye
    tx, ty, tz = to
    n = int(math.hypot(tx - fx, tz - fz) * 2)
    worst = 1e9
    for i in range(1, n):
        t = i / float(n)
        x, z = fx + (tx - fx) * t, fz + (tz - fz) * t
        y = ey + (ty + 0.5 - ey) * t
        worst = min(worst, y - (g(int(math.floor(x)), int(math.floor(z))) + 1))
    return worst


SIGHT_RANGE = 250


def visible_from_route(g, path, target, step=4):
    """(how many of the path's points within SIGHT_RANGE see `target` with a clear line, (best point, its clearance))."""
    n, best = 0, (None, -1e9)
    for x, z in path[::step]:
        if math.hypot(x - target[0], z - target[2]) > SIGHT_RANGE:
            continue
        c = sightline(g, (x, z), target)
        if c > 0:
            n += 1
        if c > best[1]:
            best = ((x, z), c)
    return n, best


def report(doc, pl, g):
    p = pl["plan"]
    cv = cover(pl, g)
    m = doc["working"]["margin"]
    worst = min(cv.items(), key=lambda kv: kv[1]) if cv else (None, None)
    routes = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    pts = np.array([q for k in ("route_08_blaine_to_giovanni", "victory_road") for q in routes[k]], dtype=float)
    x0, z0, x1, z1 = pl["bbox"]
    xs, zs = np.clip(pts[:, 0], x0, x1), np.clip(pts[:, 1], z0, z1)
    d_route = float(np.min(np.hypot(pts[:, 0] - xs, pts[:, 1] - zs)))
    ridge_pt = (p.x0 + 4, pl["ridge"], p.zc)
    seen_n, seen_best = visible_from_route(g, routes["route_08_blaine_to_giovanni"], ridge_pt)
    res = json.loads((ROOT / "data" / "resident_encounters.json").read_text(encoding="utf-8"))
    near_res = min((math.hypot(max(x0 - e["location"]["x"], 0, e["location"]["x"] - x1),
                               max(z0 - e["location"]["z"], 0, e["location"]["z"] - z1)), e["id"])
                   for e in res["encounters"])
    lines = ["barn x%d..%d z%d..%d: floor y%d (max ground under the walls + 1), loft y%d, ridge y%d"
             % (p.x0, p.x1, p.z0, p.z1, pl["bf"], pl["bf"] + doc["barn"]["loft"]["above_floor"], pl["ridge"]),
             "working floor y%d; void blocks %d; least cover outside the barn %s at %s (margin %d needs %d)"
             % (pl["wf"], len(pl["voids"]), worst[1], worst[0], m, m + 1),
             "blocks written %d (air %d); bbox x%d..%d z%d..%d y%d..%d; clear box %s y%s"
             % (len(pl["blocks"]), sum(1 for s in pl["blocks"].values() if s == "minecraft:air"), x0, x1, z0, z1,
                pl["y_range"][0], pl["y_range"][1], pl["clear"], pl["clear_y"]),
             "habitat block (fold floor centre) %s; drover at %s; barrel %s" % (pl["habitat_block"], pl["npc"],
                                                                             pl["barrel"]),
             "nearest walked path (Route 8 / Victory Road) %.0f blocks from the bbox; nearest resident %s %.0f blocks"
             % (d_route, near_res[1], near_res[0]),
             "the ridge %s is in sight of a standing eye from %d of Route 8's walked points within %d blocks; the "
             "clearest, %s, sees it %.1f blocks over the ground between" % ((ridge_pt, seen_n, SIGHT_RANGE)
                                                                           + seen_best),
             "steps R9HF: %s" % json.dumps([list(s) for s in placement_steps(doc, g)])]
    try:
        lines.append("npc R18HF: %s" % (npc_placements(doc, g),))
    except HollowError as e:
        lines.append("npc: NOT PLACEABLE: %s" % e)
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build",))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the numbers, the cover and the steps; write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, pl = files(doc, g)
    if a.report:
        print("\n".join(report(doc, pl, g)))
        return 0
    write(out_files, a.out)
    n = sum(1 for l in out_files["data/%s/function/%s/build.mcfunction" % (NS, FN)].splitlines()
            if l and not l.startswith("#"))
    print("drovers_hollow: %d files -> %s (build: %d commands)" % (len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
