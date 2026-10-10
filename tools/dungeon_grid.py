#!/usr/bin/env python
"""A block grid for one dungeon room, and the walk check over it (tools/dungeon_rooms.py).

The pocket is a void dimension, so a room is exactly what its ops write: replaying the ops onto a numpy grid gives
the room's blocks without a server. The walk check is a breadth-first search over standable cells for a player two
blocks tall and one wide. Every edge it takes is REVERSIBLE (a step of at most one block up or down, or a jump that is
feasible in both directions), so a cell reachable from the door in is reachable back; "walkable back" is the same
search, not a second one.

Ops are tuples:
  ("fill", (x0, y0, z0, x1, y1, z1), block)                     replace everything
  ("fill", box, block, "keep")                                  only where the cell is air
  ("fill", box, block, "replace minecraft:stone")                only where the cell is that block (any state)
  ("set",  (x, y, z), block)

Block classes. PASS: no collision a player is stopped by (air, plants, light, carpets, torches, small decor). WATER:
passable. SOLID: everything else, which is the safe default for an unknown id. HAZARD: a block that hurts or traps
(lava, fire, magma, cactus, berry bushes, cobweb, powder snow, pointed dripstone, campfires): never allowed.
GRAVITY blocks (sand, gravel, anvils) would fall into the void and concrete is banned (contract C4): never allowed.
"""
from __future__ import annotations

import re
from collections import deque

import numpy as np

PASS, SOLID, WATER, HAZARD = 0, 1, 2, 3

AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
PASSABLE = AIR | {
    "minecraft:light", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern", "minecraft:large_fern",
    "minecraft:seagrass", "minecraft:tall_seagrass", "minecraft:kelp", "minecraft:kelp_plant", "minecraft:vine",
    "minecraft:glow_lichen", "minecraft:moss_carpet", "minecraft:sea_pickle", "minecraft:small_dripleaf",
    "minecraft:torch", "minecraft:wall_torch", "minecraft:soul_torch", "minecraft:soul_wall_torch",
    "minecraft:candle", "minecraft:lever", "minecraft:stone_button", "minecraft:oak_button",
    "minecraft:stone_pressure_plate", "minecraft:oak_pressure_plate", "minecraft:hanging_roots",
    "minecraft:poppy", "minecraft:dandelion", "minecraft:blue_orchid", "minecraft:azure_bluet",
    "minecraft:red_tulip", "minecraft:oxeye_daisy", "minecraft:lily_of_the_valley", "minecraft:pink_petals",
    "minecraft:brown_mushroom", "minecraft:red_mushroom", "minecraft:oak_sign", "minecraft:oak_wall_sign",
    "minecraft:red_carpet", "minecraft:brown_carpet", "minecraft:green_carpet", "minecraft:gray_carpet",
    "minecraft:black_carpet", "minecraft:cyan_carpet", "minecraft:white_carpet", "minecraft:lime_carpet",
    "minecraft:cave_vines", "minecraft:cave_vines_plant",      # glow berries: no collision box, like a vine
}
WATERS = {"minecraft:water"}
HAZARDS = {
    "minecraft:lava", "minecraft:magma_block", "minecraft:fire", "minecraft:soul_fire", "minecraft:campfire",
    "minecraft:soul_campfire", "minecraft:cactus", "minecraft:sweet_berry_bush", "minecraft:wither_rose",
    "minecraft:powder_snow", "minecraft:pointed_dripstone", "minecraft:cobweb", "minecraft:tnt",
    "minecraft:bubble_column", "minecraft:sculk_shrieker", "minecraft:sculk_sensor",
}
GRAVITY = {"minecraft:sand", "minecraft:red_sand", "minecraft:gravel", "minecraft:anvil", "minecraft:dragon_egg",
           "minecraft:suspicious_sand", "minecraft:suspicious_gravel"}
CONCRETE = re.compile(r"^minecraft:.*concrete(_powder)?$")


def base(block):
    return block.split("[", 1)[0]


def classify(block):
    b = base(block)
    if b in HAZARDS:
        return HAZARD
    if b in WATERS or b in ("minecraft:kelp", "minecraft:seagrass", "minecraft:tall_seagrass", "minecraft:kelp_plant"):
        return WATER if b in WATERS else PASS
    if b in PASSABLE:
        # a waterlogged pickle is still a pickle; carpets and plants are passable either way
        return PASS
    return SOLID


def forbidden(block):
    b = base(block)
    return b in GRAVITY or bool(CONCRETE.match(b))


def norm_box(b):
    x0, y0, z0, x1, y1, z1 = b
    return (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1))


class Grid:
    """Dense block ids over an inclusive box; index 0 is air."""

    def __init__(self, box):
        self.box = norm_box(box)
        x0, y0, z0, x1, y1, z1 = self.box
        self.shape = (x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1)
        self.a = np.zeros(self.shape, dtype=np.int16)
        self.pal = ["minecraft:air"]
        self.idx = {"minecraft:air": 0}
        self.codes = [PASS]

    def pid(self, block):
        i = self.idx.get(block)
        if i is None:
            i = len(self.pal)
            self.pal.append(block)
            self.idx[block] = i
            self.codes.append(classify(block))
        return i

    def _slice(self, b):
        x0, y0, z0 = self.box[:3]
        bx0, by0, bz0, bx1, by1, bz1 = norm_box(b)
        lo = (max(bx0, x0) - x0, max(by0, y0) - y0, max(bz0, z0) - z0)
        hi = (min(bx1, self.box[3]) - x0 + 1, min(by1, self.box[4]) - y0 + 1, min(bz1, self.box[5]) - z0 + 1)
        if any(h <= l for l, h in zip(lo, hi)):
            return None
        return tuple(slice(l, h) for l, h in zip(lo, hi))

    def apply(self, op):
        if op[0] == "set":
            x, y, z = op[1]
            sl = self._slice((x, y, z, x, y, z))
            if sl is not None:
                self.a[sl] = self.pid(op[2])
            return
        sl = self._slice(op[1])
        if sl is None:
            return
        mode = op[3] if len(op) > 3 else None
        new = self.pid(op[2])
        if mode is None:
            self.a[sl] = new
        elif mode == "keep":
            sub = self.a[sl]
            sub[sub == 0] = new
        elif mode.startswith("replace "):
            want = base(mode.split(None, 1)[1])
            ids = [i for i, p in enumerate(self.pal) if base(p) == want]
            if want in AIR:
                ids.append(0)
            sub = self.a[sl]
            sub[np.isin(sub, ids)] = new
        else:
            raise ValueError("unknown fill mode %r" % mode)

    def cls(self):
        return np.array(self.codes, dtype=np.int8)[self.a]

    def block_at(self, x, y, z):
        x0, y0, z0 = self.box[:3]
        return self.pal[int(self.a[x - x0, y - y0, z - z0])]

    def local(self, x, y, z):
        x0, y0, z0 = self.box[:3]
        return (x - x0, y - y0, z - z0)

    def inside(self, x, y, z):
        return (self.box[0] <= x <= self.box[3] and self.box[1] <= y <= self.box[4] and self.box[2] <= z <= self.box[5])

    def names(self):
        used = np.unique(self.a)
        return {self.pal[int(i)] for i in used}


def standable(cls):
    """A bool grid: the cell below is solid, the cell and the one above it are passable (a 2-high player)."""
    p = (cls == PASS) | (cls == WATER)
    s = cls == SOLID
    st = np.zeros(cls.shape, dtype=bool)
    st[:, 1:-1, :] = s[:, :-2, :] & p[:, 1:-1, :] & p[:, 2:, :]
    return st, p


JUMP_FLAT_MAX = 4      # cells from take-off to landing: a flat gap of at most 3 blocks (DUNGEONS.md V6)
JUMP_RISE_MAX = 3      # a rise of one with a gap of at most 2


def walk(grid, starts, jumps=False, cls=None):
    """The set of local (ix, iy, iz) standable cells reachable from the local start cells, on reversible edges only."""
    cls = grid.cls() if cls is None else cls
    st, p = standable(cls)
    nx, ny, nz = st.shape
    seen = set()
    q = deque()
    for s in starts:
        if 0 <= s[0] < nx and 0 <= s[1] < ny and 0 <= s[2] < nz and st[s]:
            seen.add(s)
            q.append(s)
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    while q:
        x, y, z = q.popleft()
        for dx, dz in dirs:
            ax, az = x + dx, z + dz
            if not (0 <= ax < nx and 0 <= az < nz):
                continue
            for dy in (0, 1, -1):
                by = y + dy
                if not (0 < by < ny - 2) or not st[ax, by, az]:
                    continue
                if dy == 1 and not p[x, y + 2, z]:
                    continue
                if dy == -1 and not p[ax, y + 1, az]:
                    continue
                c = (ax, by, az)
                if c not in seen:
                    seen.add(c)
                    q.append(c)
                break
            if not jumps:
                continue
            for n in range(2, JUMP_FLAT_MAX + 1):
                tx, tz = x + dx * n, z + dz * n
                if not (0 <= tx < nx and 0 <= tz < nz):
                    break
                for dy in (0, 1, -1):
                    if dy != 0 and n > JUMP_RISE_MAX:
                        continue
                    by = y + dy
                    if not (0 < by < ny - 3) or not st[tx, by, tz]:
                        continue
                    top = max(y, by)
                    clear = all(p[x + dx * k, top + 1, z + dz * k] and p[x + dx * k, top + 2, z + dz * k]
                                for k in range(1, n))
                    if dy == 1:
                        clear = clear and p[x, y + 2, z] and p[x, y + 3, z]
                    if clear:
                        c = (tx, by, tz)
                        if c not in seen:
                            seen.add(c)
                            q.append(c)


    return seen


def column_ok(grid, cls, x, z, y_from, max_drop):
    """True when going down from local y_from in column (x, z) meets a solid cell within max_drop cells."""
    for k in range(max_drop + 1):
        y = y_from - k
        if y < 0:
            return False
        if cls[x, y, z] == SOLID:
            return True
    return False
