#!/usr/bin/env python
"""Victory Road's five regions: themed rooms off forks in the road, built from data/vr_regions.json.

The road itself (tools/victory_road.py, data/victory_road.json) is never rewritten here. Each region hangs off one of
the road's caverns by a fork: a 5 x 5 side passage whose mouth opens through the cavern's rim. Everything is built
as one voxel model per region and fork, checked as a whole, and only then written out:

  shell     every cell of every region and fork is set to its wall block first
  air       the rooms and passages
  floor     every solid that is not wall: floors, pillars, lips, stems, caps, props, crystal
  fluid     water and lava, written straight into sealed wall cells, never into carved air
  fittings  what needs a floor or a roof to stand on, and the lava falls last, into a pool already full

and written PASS-MAJOR across every tile (all shell, then all air, ...), not tile-major like the road: a tile
written whole before its neighbour would put water beside rock the next tile has not sealed yet.

Checks, all on the model before anything is written (the build stops on any of them):
  cover        at least cover.min of canonical ground over every shell (tools/ground.py, never a world)
  clearance    rock between each region and the road's carved space, the Deep's traced pit, the other regions
               and the EXP-033 rig; Habitat Block ranges that neither overlap nor reach the road
  spawn policy every spawn-conditioning block in a region's palette is whitelisted in
               data/spawn_block_policy.json with a reason, under the "Victory Road regions" scope
  seal         every carved or fluid cell has all six neighbours inside the model, except a fork's mouth into the
               road: no face of any region touches unauthored rock or cave
  fluid        every water and lava cell is bounded by its own fluid or a solid on every side but up, and the lava
               falls' sources on every side but down
  walk-out     from each fork's mouth, every place a player can walk, swim or fall to can get back to the mouth,
               every floor cell of the region is reachable, and no walkable floor cell touches lava without a lip
  records      data/habitat_blocks.json holds each region's block where the model puts it, and data/rewards.json
               each cache's trigger where the model puts the cache

  python tools/vr_regions.py build  [--source-root DIR] [--server-dir DIR]   -> build/datapacks/cobblers_vr_regions
  python tools/vr_regions.py report [--source-root DIR]                      the checks, nothing written
  python tools/vr_regions.py verify --world <stopped world copy>             the plan's sample cells, in a world
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL                                     # noqa: E402
from victory_road import dome, installed_blocks, pick, unit     # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "vr_regions.json"
ROAD = ROOT / "data" / "victory_road.json"
ROAD_PLAN = ROOT / "derived" / "victory_road" / "plan.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_vr_regions"
PLAN = ROOT / "derived" / "vr_regions" / "plan.json"
TILE = 64
PART = 3500
PASSES = ("shell", "air", "floor", "fluid", "fittings")
AIR, WATER, LAVA = "minecraft:air", "minecraft:water", "minecraft:lava"
SCOPE = "Victory Road regions"

# The ground rule (tools/ground_rule.py): verify reads a stopped world copy to CHECK the build, never to place it.
WORLD_READS = {"verify", "verify_full", "main"}

# Cells a player (and a fluid) can be in. Everything else in the model is solid.
OPEN = {AIR, WATER, LAVA, "minecraft:rail", "minecraft:moss_carpet", "minecraft:cave_vines",
        "minecraft:cave_vines_plant", "minecraft:spore_blossom"}
# Of those, what a player can stand in (the rest is fluid)
PASSABLE = OPEN - {LAVA}


class RegionError(Exception):
    pass


def base(block):
    return block.split("[", 1)[0]


# ------------------------------------------------------------------ the model

class Part:
    """One region or one fork: its cells, final state, and which pass writes each."""

    def __init__(self, owner, wall):
        self.owner, self.wall = owner, wall
        self.shell = {}                 # (x, y, z) -> wall block, for every cell this part owns
        self.cells = {}                 # (x, y, z) -> (block, pass) for every cell that is not wall
        self.interior = set()           # (x, z) columns inside the room (a fork's other parts skip them)
        self.fall_air = set()           # cells a lava fall will flow through: not checked in a world
        self.floor_h = {}               # (x, z) -> the y a player stands at, for every interior column

    def box(self, x, z, y0, y1, block=None):
        for y in range(y0, y1 + 1):
            self.shell[(x, y, z)] = block or self.wall

    def put(self, x, y, z, block, pas):
        self.shell.setdefault((x, y, z), self.wall)
        self.cells[(x, y, z)] = (block, pas)

    def block(self, p):
        c = self.cells.get(p)
        if c:
            return c[0]
        return self.shell.get(p)


def outline(seed, R):
    """The room's radius at an angle: a disc pushed in and out so it does not read as a compass circle."""
    p1 = unit(seed, 1, 0, 11) * 2 * math.pi
    p2 = unit(seed, 2, 0, 12) * 2 * math.pi
    return lambda th: R * (1 + 0.10 * math.sin(3 * th + p1) + 0.06 * math.sin(5 * th + p2))


def room_columns(cx, cz, R, seed, ring=2):
    """{(x, z): (rr, d)} for the room and a `ring`-block shell round it; rr is the fraction of the local radius,
    d the blocks outside the outline (<= 0 inside)."""
    f = outline(seed, R)
    out = {}
    rmax = int(math.ceil(R * 1.17)) + ring + 1
    for x in range(cx - rmax, cx + rmax + 1):
        for z in range(cz - rmax, cz + rmax + 1):
            dx, dz = x - cx, z - cz
            th = math.atan2(dz, dx)
            r = math.hypot(dx, dz)
            loc = f(th)
            d = r - loc
            if d <= ring:
                out[(x, z)] = (r / loc, d)
    return out


def smooth_heights(h, cols, passes=6):
    """Clamp a floor so no column is more than one block above any neighbour: a broken floor, never a wall."""
    for _ in range(passes):
        changed = False
        for (x, z) in cols:
            lo = min(h.get((x + dx, z + dz), h[(x, z)]) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if h[(x, z)] > lo + 1:
                h[(x, z)] = lo + 1
                changed = True
        if not changed:
            break
    return h


# ------------------------------------------------------------------ the regions

def carve_room(part, r, cols, floor_h, floor_block, bottom):
    """The shared shape: the shell from `bottom` to two over the dome, air from each column's floor to the dome."""
    y0, H = r["floor_y"], r["height"]
    part.floor_h = {c: floor_h[c] for c, (_rr, d) in cols.items() if d <= 0}
    ceil = {c: dome(y0, H, min(rr, 1.0)) for c, (rr, _d) in cols.items()}
    for (x, z), (rr, d) in cols.items():
        c = ceil[(x, z)]
        # near the rim the dome falls several blocks between neighbours: a column's shell has to cover the highest
        # ceiling within two of it, or the room's side opens above the lower column's shell
        top = max(ceil.get((x + dx, z + dz), c) for dx in range(-2, 3) for dz in range(-2, 3))
        part.box(x, z, bottom, top + 2)
        if d <= 0:
            part.interior.add((x, z))
            f = floor_h[(x, z)]
            part.put(x, f - 1, z, floor_block, "floor")
            for y in range(f, c + 1):
                part.put(x, y, z, AIR, "air")
    return ceil


def region_drowned(part, r, pal, cols, seed, toward):
    fm = r["form"]
    y0, cx, cz = r["floor_y"], r["at"][0], r["at"][1]
    bottom = y0 - 3 - fm["centre_depth"]
    floor_h = {c: y0 for c in cols}
    ceil = carve_room(part, r, cols, floor_h, pal["floor"], bottom)
    lake_rr = fm["lake_rr"]
    extra = {}
    for (x, z) in part.interior:
        rr = cols[(x, z)][0]
        if rr > lake_rr:
            continue
        if math.hypot(x - cx, z - cz) <= fm["island_radius"]:
            # the island: a pedestal from the lake bed to the surface, the floor on top
            for y in range(bottom + 1, y0 - 1):
                part.put(x, y, z, pal["pillar"], "floor")
            continue
        dep = fm["edge_depth"] + int(round((fm["centre_depth"] - fm["edge_depth"]) * (1 - rr / lake_rr)))
        part.put(x, y0 - dep - 1, z, pal["lake_bed"], "floor")
        for y in range(y0 - dep, y0):
            part.put(x, y, z, WATER, "fluid")
        extra[(x, z)] = dep
    # pillars stand in the lake, from the bed to the roof
    n = fm["pillars"]
    for i in range(n):
        th = 2 * math.pi * i / n + unit(seed, i, 5, 21) * 0.5
        rrp = 0.40 + 0.12 * unit(seed, i, 6, 22)
        px = cx + int(round(math.cos(th) * rrp * r["radius"]))
        pz = cz + int(round(math.sin(th) * rrp * r["radius"]))
        for dx in range(-1, 2):
            for dz in range(-1, 2):
                X, Z = px + dx, pz + dz
                if (X, Z) not in part.interior:
                    continue
                dep = extra.get((X, Z), 0)
                for y in range(y0 - dep - 1, ceil[(X, Z)] + 1):
                    part.put(X, y, Z, pal["pillar"], "floor")
                part.put(X, ceil[(X, Z)], Z, pal["pillar_cap"], "floor")
    # three lights on the lake bed, and nothing else
    lights = []
    for i in range(fm["deep_lights"]):
        th = 2 * math.pi * (i + 0.5) / fm["deep_lights"] + unit(seed, i, 7, 23)
        X = cx + int(round(math.cos(th) * 0.28 * r["radius"]))
        Z = cz + int(round(math.sin(th) * 0.28 * r["radius"]))
        if (X, Z) in extra and part.cells.get((X, y0 - extra[(X, Z)] - 1), (None,))[0] == pal["lake_bed"]:
            part.put(X, y0 - extra[(X, Z)] - 1, Z, pal["light"], "floor")
            lights.append((X, y0 - extra[(X, Z)] - 1, Z))
    cache = (cx, y0, cz)
    habitat = (cx - 1, y0 - 1, cz)
    return {"cache": cache, "habitat": habitat, "lights": lights, "bottom": bottom}


def region_slagworks(part, r, pal, cols, seed, toward):
    fm = r["form"]
    y0, cx, cz, R = r["floor_y"], r["at"][0], r["at"][1], r["radius"]
    bottom = y0 - 4 - fm["pool_depth"]
    away = toward + math.pi
    px = cx + int(round(math.cos(away) * fm["pool_at_rr"] * R))
    pz = cz + int(round(math.sin(away) * fm["pool_at_rr"] * R))
    pr = fm["pool_radius"]
    # the magma shelf: an arc a quarter-turn round from the pool, raised two, with a one-block step round it
    mid = away + math.pi / 2
    half = math.radians(fm["shelf_arc_degrees"]) / 2
    lo_rr, hi_rr = fm["shelf_rr"]
    shelf = set()
    for (x, z), (rr, d) in cols.items():
        if d > 0 or not (lo_rr <= rr <= hi_rr):
            continue
        a = math.atan2(z - cz, x - cx)
        if abs((a - mid + math.pi) % (2 * math.pi) - math.pi) <= half and math.hypot(x - px, z - pz) > pr + 4:
            shelf.add((x, z))
    step = {(x, z) for (x, z), (rr, d) in cols.items() if d <= 0 and (x, z) not in shelf and any(
        (x + dx, z + dz) in shelf for dx in (-1, 0, 1) for dz in (-1, 0, 1))}
    rise = fm["shelf_rise"]
    floor_h = {c: y0 + (rise if c in shelf else 1 if c in step else 0) for c in cols}
    ceil = carve_room(part, r, cols, floor_h, pal["floor"], bottom)
    for (x, z) in shelf | step:
        top = floor_h[(x, z)] - 1
        for y in range(y0 - 1, top):
            part.put(x, y, z, pal["step"], "floor")
        part.put(x, top, z, pal["shelf"] if (x, z) in shelf else pal["step"], "floor")
    # the pool: lava flush with the floor, a one-block lip all the way round it
    pool = set()
    for (x, z) in part.interior:
        dd = math.hypot(x - px, z - pz)
        if dd <= pr:
            pool.add((x, z))
            part.put(x, y0 - fm["pool_depth"] - 1, z, pal["pool_bed"], "floor")
            for y in range(y0 - fm["pool_depth"], y0):
                part.put(x, y, z, LAVA, "fluid")
        elif dd <= pr + 1:
            part.put(x, y0, z, pal["lip"], "floor")
    if len(pool) < 100:
        raise RegionError("the Slagworks pool is %d columns: it ran into the room's wall" % len(pool))
    # the falls: a source in the roof over the pool, at the height of the highest ceiling round it so every side
    # but down is rock, and the column under it opened up to it
    falls = []
    for i in range(fm["falls"]):
        a = away + (i - 0.5) * 1.6
        fx = px + int(round(math.cos(a) * 2))
        fz = pz + int(round(math.sin(a) * 2))
        top = max(ceil[(fx + dx, fz + dz)] for dx in (-1, 0, 1) for dz in (-1, 0, 1))
        for y in range(ceil[(fx, fz)] + 1, top + 1):
            part.put(fx, y, fz, AIR, "air")
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                part.box(fx + dx, fz + dz, top + 1, top + 3) if (fx + dx, fz + dz) != (fx, fz) else None
                for y in range(ceil[(fx + dx, fz + dz)] + 3, top + 4):
                    part.shell.setdefault((fx + dx, y, fz + dz), part.wall)
        part.put(fx, top + 1, fz, LAVA, "fittings")
        falls.append((fx, top + 1, fz))
        for y in range(y0, top + 1):
            part.fall_air.add((fx, y, fz))
    # the find at the end of the shelf furthest round from the way in
    end = max(shelf, key=lambda c: abs((math.atan2(c[1] - cz, c[0] - cx) - toward + math.pi) % (2 * math.pi) - math.pi)
              - abs(cols[c][0] - 0.75))
    cache = (end[0], floor_h[end], end[1])
    habitat = (cx, y0 - 1, cz)
    if (cx, cz) in pool or math.hypot(cx - px, cz - pz) <= pr + 1:
        raise RegionError("the Slagworks' Habitat Block would sit in its pool or lip")
    return {"cache": cache, "habitat": habitat, "falls": falls, "pool": [px, y0, pz, pr], "bottom": bottom,
            "shelf": len(shelf)}


def region_tear(part, r, pal, cols, seed, toward):
    fm = r["form"]
    y0, cx, cz, R = r["floor_y"], r["at"][0], r["at"][1], r["radius"]
    bottom = y0 - 4
    p, q = unit(seed, 3, 0, 31) * 6, unit(seed, 4, 0, 32) * 6
    ex = cx + math.cos(toward) * R
    ez = cz + math.sin(toward) * R
    floor_h = {}
    for (x, z) in cols:
        g = 1.4 * math.sin(x * 0.17 + p) * math.sin(z * 0.13 + q) + 0.9 * math.sin((x + z) * 0.07 + p)
        if math.hypot(x - ex, z - ez) < 10:
            g = 0.0                                      # level where the fork comes in
        floor_h[(x, z)] = y0 + max(-1, min(fm["terrace"], int(round(g))))
    floor_h = smooth_heights(floor_h, cols)
    # and up as well as down: the same clamp on the negated field
    neg = smooth_heights({c: -v for c, v in floor_h.items()}, cols)
    floor_h = {c: -v for c, v in neg.items()}
    ceil = carve_room(part, r, cols, floor_h, pal["floor"], bottom)
    # veins of the tear's own light across the floor, and patches of its crystal in the walls
    lights = []
    for k in range(4):
        th = toward + math.pi + (k - 1.5) * 0.9 + unit(seed, k, 8, 33) * 0.4
        for s in range(3, int(R * 1.1)):
            X = cx + int(round(math.cos(th + 0.25 * math.sin(s * 0.3 + k)) * s))
            Z = cz + int(round(math.sin(th + 0.25 * math.sin(s * 0.3 + k)) * s))
            if (X, Z) in part.interior and s % 2 == 0:
                part.put(X, floor_h[(X, Z)] - 1, Z, pal["vein"], "floor")
                lights.append((X, floor_h[(X, Z)] - 1, Z))
    for (x, y, z) in list(part.shell):
        if (x, y, z) in part.cells:
            continue
        if any(part.cells.get((x + dx, y + dy, z + dz), (None,))[0] == AIR
               for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))):
            u = unit(x, y, z, 34)
            if u < 0.18:
                part.put(x, y, z, pal["crystal"], "floor")
            elif u < 0.21:
                part.put(x, y, z, pal["vein"], "floor")
    # spires up from the floor and teeth down from the roof, clear of the way in and the middle
    placed = 0
    for i in range(400):
        if placed >= fm["spires"]:
            break
        th = unit(seed, i, 9, 35) * 2 * math.pi
        rr = 0.25 + 0.55 * unit(seed, i, 10, 36)
        X, Z = cx + int(round(math.cos(th) * rr * R)), cz + int(round(math.sin(th) * rr * R))
        if (X, Z) not in part.interior or math.hypot(X - ex, Z - ez) < 12:
            continue
        hgt = 3 + int(6 * unit(seed, i, 11, 37))
        f = floor_h[(X, Z)]
        top = min(f + hgt - 1, ceil[(X, Z)] - 3)
        for y in range(f, top + 1):
            part.put(X, y, Z, pal["crystal"], "floor")
        placed += 1
    placed = 0
    for i in range(400):
        if placed >= fm["stalactites"]:
            break
        th = unit(seed, i, 12, 38) * 2 * math.pi
        rr = 0.1 + 0.6 * unit(seed, i, 13, 39)
        X, Z = cx + int(round(math.cos(th) * rr * R)), cz + int(round(math.sin(th) * rr * R))
        if (X, Z) not in part.interior:
            continue
        ln = 3 + int(5 * unit(seed, i, 14, 40))
        c = ceil[(X, Z)]
        bottom_y = max(c - ln + 1, floor_h[(X, Z)] + 4)
        for y in range(bottom_y, c + 1):
            part.put(X, y, Z, pal["crystal"], "floor")
        placed += 1
    # the find: in a seam at the back, away from the way in
    back = (cx + int(round(math.cos(toward + math.pi) * 0.82 * R)), cz + int(round(math.sin(toward + math.pi) * 0.82 * R)))
    if back not in part.interior:
        raise RegionError("the Raw Tear's seam fell outside its room")
    cache = (back[0], floor_h[back], back[1])
    for y in range(floor_h[back], floor_h[back] + 3):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (back[0] + dx, back[1] + dz) in part.interior and part.cells.get(
                    (back[0] + dx, y, back[1] + dz), (None,))[0] == pal["crystal"]:
                part.put(back[0] + dx, y, back[1] + dz, AIR, "air")
    habitat = (cx, floor_h[(cx, cz)] - 1, cz)
    return {"cache": cache, "habitat": habitat, "lights": lights, "bottom": bottom}


def region_bloom(part, r, pal, cols, seed, toward):
    fm = r["form"]
    y0, cx, cz, R = r["floor_y"], r["at"][0], r["at"][1], r["radius"]
    bottom = y0 - 4
    floor_h = {c: y0 for c in cols}
    ceil = carve_room(part, r, cols, floor_h, pal["floor"], bottom)
    ex = cx + math.cos(toward) * R
    ez = cz + math.sin(toward) * R
    for (x, z) in part.interior:
        if unit(x, y0, z, 41) < 0.15:
            part.put(x, y0 - 1, z, pal["floor_alt"], "floor")
    taken = {}

    def free(X, Z, rad):
        return all(math.hypot(X - a, Z - b) > rad + ra for (a, b), ra in taken.items())

    # three puddles, one block deep, flush with the floor
    puddles, i = 0, 0
    while puddles < fm["puddles"] and i < 300:
        th = unit(seed, i, 15, 42) * 2 * math.pi
        rr = 0.3 + 0.4 * unit(seed, i, 16, 43)
        X, Z = cx + int(round(math.cos(th) * rr * R)), cz + int(round(math.sin(th) * rr * R))
        rad = 2 + int(2 * unit(seed, i, 17, 44))
        i += 1
        if not free(X, Z, rad + 1) or math.hypot(X - cx, Z - cz) < 6 or math.hypot(X - ex, Z - ez) < 10:
            continue
        cells = [(X + dx, Z + dz) for dx in range(-rad, rad + 1) for dz in range(-rad, rad + 1)
                 if math.hypot(dx, dz) <= rad + 0.3]
        if not all(c in part.interior and cols[c][0] < 0.85 for c in cells):
            continue
        for (x, z) in cells:
            part.put(x, y0 - 2, z, pal["puddle_bed"], "floor")
            part.put(x, y0 - 1, z, WATER, "fluid")
        taken[(X, Z)] = rad
        puddles += 1
    # giant mushrooms: a stem and a flat cap with light in it; the find under the largest
    mush = []
    i = 0
    while len(mush) < fm["mushrooms"] and i < 400:
        th = unit(seed, i, 18, 45) * 2 * math.pi
        rr = 0.25 + 0.5 * unit(seed, i, 19, 46)
        X, Z = cx + int(round(math.cos(th) * rr * R)), cz + int(round(math.sin(th) * rr * R))
        rc = 3 + int(2 * unit(seed, i, 20, 47))
        i += 1
        if not free(X, Z, rc + 2) or math.hypot(X - cx, Z - cz) < 5 or math.hypot(X - ex, Z - ez) < 9:
            continue
        foot = [(X + dx, Z + dz) for dx in range(-rc, rc + 1) for dz in range(-rc, rc + 1) if math.hypot(dx, dz) <= rc]
        if not all(c in part.interior for c in foot):
            continue
        hs = min(9, min(ceil[c] for c in foot) - y0 - 1)
        if hs < 5:
            continue
        cap = pal["cap_red"] if unit(seed, i, 21, 48) < 0.5 else pal["cap_brown"]
        for y in range(y0, y0 + hs):
            part.put(X, y, Z, pal["stem"], "floor")
        for (x, z) in foot:
            edge = math.hypot(x - X, z - Z) > rc - 1
            part.put(x, y0 + hs, z, cap, "floor")
            if edge and hs > 5:
                part.put(x, y0 + hs - 1, z, cap, "floor")
            elif not edge and unit(x, y0, z, 49) < 0.25 and (x, z) != (X, Z):
                part.put(x, y0 + hs, z, pal["cap_light"], "floor")
        taken[(X, Z)] = rc
        mush.append((rc, hs, X, Z))
    if not mush:
        raise RegionError("no mushroom fitted in the Bloom")
    rc, hs, MX, MZ = max(mush)
    cache = (MX + 1, y0, MZ)
    # the roof: glow berries and blossoms; the floor: moss carpet and bushes
    fits = []
    i = n = 0
    while n < fm["vines"] and i < 600:
        X = cx + int(round((unit(seed, i, 22, 50) * 2 - 1) * R))
        Z = cz + int(round((unit(seed, i, 23, 51) * 2 - 1) * R))
        i += 1
        # one string per column: two in one column overlap, and the game turns the upper string's tip into stem
        # (found by verify --full on the staging world, 2026-09-23)
        if (X, Z) not in part.interior or any(f[0] == X and f[2] == Z for f in fits):
            continue
        c = ceil[(X, Z)]
        ln = 2 + int(4 * unit(seed, i, 24, 52))
        if c - ln < y0 + 2 or any(part.cells.get((X, y, Z), (AIR,))[0] != AIR for y in range(c - ln, c + 1)):
            continue
        for k, y in enumerate(range(c, c - ln, -1)):
            tip = k == ln - 1
            fits.append((X, y, Z, "minecraft:cave_vines[age=25,berries=true]" if tip else
                         "minecraft:cave_vines_plant[berries=%s]" % ("true" if unit(X, y, Z, 53) < 0.4 else "false")))
        n += 1
    i = n = 0
    while n < fm["blossoms"] and i < 300:
        X = cx + int(round((unit(seed, i, 25, 54) * 2 - 1) * R * 0.7))
        Z = cz + int(round((unit(seed, i, 26, 55) * 2 - 1) * R * 0.7))
        i += 1
        if (X, Z) not in part.interior or part.cells.get((X, ceil[(X, Z)], Z), (None,))[0] != AIR:
            continue
        if any(f[0] == X and f[2] == Z for f in fits):
            continue
        fits.append((X, ceil[(X, Z)], Z, "minecraft:spore_blossom"))
        n += 1
    i = n = 0
    while n < fm["bushes"] and i < 300:
        X = cx + int(round((unit(seed, i, 27, 56) * 2 - 1) * R * 0.85))
        Z = cz + int(round((unit(seed, i, 28, 57) * 2 - 1) * R * 0.85))
        i += 1
        if (X, Z) not in part.interior or part.cells.get((X, y0, Z), (None,))[0] != AIR or not free(X, Z, 1):
            continue
        if part.cells.get((X, y0 - 1, Z), (None,))[0] not in (pal["floor"], pal["floor_alt"]):
            continue
        if math.hypot(X - ex, Z - ez) < 6 or math.hypot(X - cx, Z - cz) < 3:
            continue
        fits.append((X, y0, Z, "minecraft:flowering_azalea" if unit(seed, i, 29, 58) < 0.4 else "minecraft:azalea"))
        taken[(X, Z)] = 0.5
        n += 1
    busy = {(f[0], f[1], f[2]) for f in fits}
    for (x, z) in part.interior:
        if (x, y0, z) in busy or part.cells.get((x, y0, z), (None,))[0] != AIR:
            continue
        if part.cells.get((x, y0 - 1, z), (None,))[0] == pal["floor"] and unit(x, y0, z, 59) < 0.3:
            fits.append((x, y0, z, pal["carpet"]))
    for (x, y, z, b) in fits:
        part.put(x, y, z, b, "fittings")
    habitat = (cx, y0 - 1, cz)
    return {"cache": cache, "habitat": habitat, "bottom": bottom, "mushrooms": len(mush), "fittings": len(fits)}


def region_gallery(part, r, pal, cols_unused, seed, toward):
    """The Abandoned Cut: a straight working along x, not a round room."""
    fm = r["form"]
    y0, cx, cz, R, H = r["floor_y"], r["at"][0], r["at"][1], r["radius"], r["height"]
    sign = 1 if math.cos(toward) < 0 else -1          # the far end, away from the fork
    top = y0 + H - 1
    bottom = y0 - 3
    hw = {}
    for u in range(-R, R + 1):
        hw[u] = fm["width"] // 2 + (1 if unit(seed, u, 30, 60) < 0.3 else -1 if unit(seed, u, 31, 61) < 0.2 else 0)
    cols = {}
    for u in range(-R - 2, R + 3):
        w = hw.get(max(-R, min(R, u)), fm["width"] // 2)
        for v in range(-w - 2, w + 3):
            x, z = cx + sign * u, cz + v
            inside = -R <= u <= R and abs(v) <= w
            cols[(x, z)] = inside
            part.box(x, z, bottom, top + 2)
            if inside:
                part.interior.add((x, z))
                part.floor_h[(x, z)] = y0
                part.put(x, y0 - 1, z, pal["floor"], "floor")
                for y in range(y0, top + 1):
                    part.put(x, y, z, AIR, "air")
    # the collapse fills the far end to the roof, as a slope a player can climb
    col = fm["collapse"]
    for u in range(R - col + 1, R + 1):
        rise = int(round((u - (R - col)) * H / float(col)))
        for v in range(-hw[u], hw[u] + 1):
            x, z = cx + sign * u, cz + v
            for y in range(y0, min(top, y0 + rise - 1) + 1):
                part.put(x, y, z, pal["spoil"] if unit(x, y, z, 62) < 0.6 else pal["spoil_alt"], "floor")
    # props every six blocks: two posts and a beam across the roof
    fits = []
    beams = []
    for u in range(-R + 3, R - col - 1, fm["prop_every"]):
        w = min(hw[u], hw.get(u + 1, hw[u]), hw.get(u - 1, hw[u]))
        x = cx + sign * u
        for v in (-w, w):
            for y in range(y0, top):
                part.put(x, y, cz + v, pal["post"] + "[axis=y]", "floor")
        for v in range(-w, w + 1):
            part.put(x, top, cz + v, pal["beam"] + "[axis=z]", "floor")
        beams.append(x)
    for k, x in enumerate(beams):
        if k % 2 == 0:
            fits.append((x, top - 1, cz, pal["lamp"] + "[hanging=true]"))
    # spoil heaps against the walls
    for k in range(5):
        u = -R + 6 + int((2 * R - col - 12) * (k + 0.5) / 5)
        v = (hw[u] - 2) * (1 if k % 2 else -1)
        for du in range(-2, 3):
            for dv in range(-2, 3):
                hgt = 2 - int(math.hypot(du, dv))
                x, z = cx + sign * (u + du), cz + v + dv
                if hgt <= 0 or (x, z) not in part.interior:
                    continue
                for y in range(y0, y0 + hgt):
                    if part.cells.get((x, y, z), (None,))[0] == AIR:
                        part.put(x, y, z, pal["spoil"] if unit(x, y, z, 63) < 0.5 else pal["spoil_alt"], "floor")
    # the rail down the middle, broken in places
    for u in range(-R + 1, R - col - 1):
        x = cx + sign * u
        if unit(x, y0, cz, 64) < 0.12 or part.cells.get((x, y0, cz), (None,))[0] != AIR:
            continue
        fits.append((x, y0, cz, pal["rail"] + "[shape=east_west]"))
    # what the diggers left: barrels by the collapse (scenery, empty)
    for k, v in enumerate((-3, 3, -2)):
        u = R - col - 2 - k
        x = cx + sign * u
        if part.cells.get((x, y0, cz + v), (None,))[0] == AIR:
            fits.append((x, y0, cz + v, "minecraft:barrel[facing=up]"))
    for (x, y, z, b) in fits:
        part.put(x, y, z, b, "fittings")
    npc = (cx + sign * (R - col - 4), y0, cz + 2)
    habitat = (cx, y0 - 1, cz - 3)
    entry = (cx - sign * (R - 2), cz)
    return {"npc": npc, "habitat": habitat, "bottom": bottom, "beams": len(beams), "entry": entry,
            "gallery": [cx - R, cz - fm["width"] // 2, cx + R, cz + fm["width"] // 2]}


BUILDERS = {"lake": region_drowned, "lava": region_slagworks, "tear": region_tear, "bloom": region_bloom,
            "gallery": region_gallery}


# ------------------------------------------------------------------ the forks

def densify(pts):
    out = []
    for (ax, ay, az), (bx, by, bz) in zip(pts, pts[1:]):
        n = max(abs(bx - ax), abs(bz - az), abs(by - ay), 1)
        for k in range(n):
            f = k / float(n)
            out.append((int(round(ax + (bx - ax) * f)), int(round(ay + (by - ay) * f)), int(round(az + (bz - az) * f))))
    out.append(tuple(pts[-1]))
    return out


def carve_fork(part, path, fk, lintel):
    """A side passage: rock round it, air through it, one floor per column at its nearest step, and the mouth framed."""
    w, h, sh = fk["width"], fk["height"], fk["shell"]
    half = w // 2
    near = {}
    for k, (cx, cy, cz) in enumerate(path):
        for dx in range(-half - sh, half + sh + 1):
            for dz in range(-half - sh, half + sh + 1):
                X, Z = cx + dx, cz + dz
                inner = abs(dx) <= half and abs(dz) <= half
                d = abs(dx) + abs(dz)
                rec = near.setdefault((X, Z), {"lo": cy - 3, "hi": cy + h + 1, "floor": None, "top": None})
                rec["lo"] = min(rec["lo"], cy - 3)
                rec["hi"] = max(rec["hi"], cy + h + 1)
                if inner:
                    if rec["floor"] is None or d < rec["floor"][0]:
                        rec["floor"] = (d, cy - 1)
                    rec["top"] = max(rec["top"] or -999, cy + h - 1)
    for (X, Z), rec in near.items():
        part.box(X, Z, rec["lo"], rec["hi"])
        if rec["floor"] is not None:
            fy = rec["floor"][1]
            part.put(X, fy, Z, None, "floor")            # the floor block is the region's; set in compose
            for y in range(fy + 1, rec["top"] + 1):
                part.put(X, y, Z, AIR, "air")
    # the lintel: a frame of the region's own material across the passage, three blocks in from the mouth
    (ax, ay, az), (bx, _by, bz) = path[3], path[4]
    ux, uz = bx - ax, bz - az
    n = math.hypot(ux, uz) or 1.0
    px, pz = -uz / n, ux / n
    for t in range(-half - 1, half + 2):
        X, Z = int(round(ax + px * t)), int(round(az + pz * t))
        if abs(t) == half + 1:
            for y in range(ay - 1, ay + h + 1):
                part.put(X, y, Z, lintel, "floor")
        else:
            part.put(X, ay + h, Z, lintel, "floor")
    return near


# ------------------------------------------------------------------ the road, and what must stay clear of it

class Road:
    def __init__(self):
        if not ROAD_PLAN.is_file():
            raise RegionError("no %s: build Victory Road first (python tools/victory_road.py build)" % ROAD_PLAN)
        p = json.loads(ROAD_PLAN.read_text(encoding="utf-8"))
        spec = json.loads(ROAD.read_text(encoding="utf-8"))
        self.h = spec["corridor"]["height"]
        self.half = spec["corridor"]["width"] // 2
        self.chambers = {k: tuple(v) for k, v in p["chambers"].items()}
        self.heights = {c["at"]: c["height"] for c in spec["chambers"]}
        self.route = {}
        for x, y, z in p["route"]:
            self.route.setdefault((x, z), []).append(y)
        self.cols = np.array(sorted(self.route), dtype=float)
        self.landmark = spec["landmark"]
        self.vein_cols = set()
        rc = set(self.route)
        for name, (cx, cy, cz, R) in self.chambers.items():
            if next(c for c in spec["chambers"] if c["at"] == name)["kind"] != "landmark":
                continue
            for dx in range(-R, R + 1):
                for dz in range(-R, R + 1):
                    rr = math.hypot(dx, dz) / float(R)
                    X, Z = cx + dx, cz + dz
                    if 0.55 <= rr <= 1.0 and unit(X, cy, Z, 232) < 0.04 and not any(
                            (X + a, Z + b) in rc for a in range(-3, 4) for b in range(-3, 4)):
                        self.vein_cols.add((X, Z))

    def space(self, x, y, z):
        """True inside the road's own carved space or its walls: a fork may open into it, nothing may write it."""
        for cx, cy, cz, R in self.chambers.values():
            if math.hypot(x - cx, z - cz) <= R and cy - 1 <= y:
                return True
        for dx in range(-self.half - 1, self.half + 2):
            for dz in range(-self.half - 1, self.half + 2):
                for ry in self.route.get((x + dx, z + dz), ()):
                    if ry - 1 <= y <= ry + self.h:
                        return True
        return False

    def distance(self, x, z):
        """Horizontal blocks from (x, z) to the nearest carved column of the road (corridor edge or cavern rim)."""
        d = float(np.hypot(self.cols[:, 0] - x, self.cols[:, 1] - z).min()) - self.half - 1
        for cx, _cy, cz, R in self.chambers.values():
            d = min(d, math.hypot(x - cx, z - cz) - R)
        return d


# ------------------------------------------------------------------ build

def whitelisted():
    pol = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    out = {}
    for w in pol.get("whitelist") or []:
        if SCOPE.lower() in str(w.get("scope", "")).lower():
            for b in w["blocks"]:
                out[b] = w["why"]
    return out


def triggers():
    return json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]


def build(source_root=None, server_dir=None, strict=True):
    import os
    import ground as G
    import rift_deep as RD
    source_root = source_root or os.environ.get("COBBLERS_SOURCE_ROOT")
    if not source_root:
        raise RegionError("no --source-root and no COBBLERS_SOURCE_ROOT: the heightmap lives under it")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    have = installed_blocks(server_dir)
    g = G.load(source_root)
    road = Road()
    fk = spec["fork"]
    counts, report = {}, []
    parts, info, forks = [], {}, {}

    for r in spec["regions"]:
        pal = dict(r["palette"])
        for k, b in list(pal.items()):
            pal[k] = pick(b, (r.get("fallbacks") or {}).get(b, b), have)
        seed = spec["seed"] + sum(ord(c) for c in r["id"])
        cx, cz = r["at"]
        ch = road.chambers[r["fork_from"]]
        toward = math.atan2(ch[2] - cz, ch[0] - cx)      # from the region toward the cavern it forks from
        part = Part(r["id"], pal["wall"])
        cols = room_columns(cx, cz, r["radius"], seed) if r["form"]["kind"] != "gallery" else None
        inf = BUILDERS[r["form"]["kind"]](part, r, pal, cols, seed, toward)
        inf["toward"] = toward
        if "cache" in inf:
            x, y, z = inf["cache"]
            part.put(x, y, z, "minecraft:barrel[facing=up]", "fittings")
        inf["pal"] = pal
        info[r["id"]] = inf
        parts.append(part)

        # the fork: from inside the cavern's rim to inside the room, bent once
        chx, chy, chz, chR = ch
        # mouth_turn: degrees to swing the mouth round the cavern's rim, off the straight line to the region, where
        # something of the road's own stands in the way
        ax = math.atan2(cz - chz, cx - chx) + math.radians(r.get("mouth_turn", 0))
        mouth = (chx + int(round(math.cos(ax) * (chR - 3))), chy, chz + int(round(math.sin(ax) * (chR - 3))))
        if "entry" in inf:
            ex, ez = inf["entry"]
        else:
            ex = cx + int(round(math.cos(toward) * 0.8 * r["radius"]))
            ez = cz + int(round(math.sin(toward) * 0.8 * r["radius"]))
        end = (ex, r["floor_y"], ez)
        mx, mz = (mouth[0] + end[0]) / 2.0, (mouth[2] + end[2]) / 2.0
        L = math.hypot(end[0] - mouth[0], end[2] - mouth[2])
        nx, nz = -(end[2] - mouth[2]) / L, (end[0] - mouth[0]) / L
        bend = (int(round(mx + nx * r["bend"])), int(round((mouth[1] + end[1]) / 2.0)), int(round(mz + nz * r["bend"])))
        path = densify([mouth, bend, end])
        grade = abs(end[1] - mouth[1]) / max(1.0, L)
        if grade > fk["max_grade"]:
            raise RegionError("%s's fork climbs %.2f, over %s" % (r["id"], grade, fk["max_grade"]))
        # the landmark's vein columns stand inside the_vein up to its rim: none may stand in a fork's way in
        blocked = [(x, z) for (x, _y, z) in path for dx in range(-3, 4) for dz in range(-3, 4)
                   if (x + dx, z + dz) in road.vein_cols]
        if blocked:
            raise RegionError("%s's fork runs into the landmark's vein column at %s; move its bend" % (r["id"], blocked[0]))
        fpart = Part(r["id"] + ":fork", pal["wall"])
        carve_fork(fpart, path, fk, pal["lintel"])
        forks[r["id"]] = {"part": fpart, "path": path, "mouth": list(mouth), "length": len(path), "grade": round(grade, 2)}

    # ---- compose: the regions own their cells; a fork fills in round them and never writes the road
    model, wall_of, owner = {}, {}, {}
    for part in parts:
        for p, wb in part.shell.items():
            wall_of[p] = wb
            owner[p] = part.owner
        for p, c in part.cells.items():
            model[p] = c
    region_cols = set().union(*[p.interior for p in parts])
    floor_of = {r["id"]: info[r["id"]]["pal"]["floor"] for r in spec["regions"]}
    skipped = 0
    for rid, f in forks.items():
        part = f["part"]
        for p, wb in part.shell.items():
            x, y, z = p
            if (x, z) in region_cols or road.space(x, y, z):
                skipped += 1
                continue
            if p in model and model[p][1] != "shell":
                continue
            wall_of.setdefault(p, wb)
            owner.setdefault(p, part.owner)
        for p, (b, pas) in part.cells.items():
            x, y, z = p
            if (x, z) in region_cols or road.space(x, y, z):
                continue
            if b is None:
                b = floor_of[rid]
            if p in model and pas == "air" and model[p][0] != AIR:
                continue
            model[p] = (b, pas)
            wall_of.setdefault(p, part.wall)
            owner.setdefault(p, part.owner)
    counts["cells in the model"] = len(wall_of)
    counts["fork cells left to the road"] = skipped

    def final(p):
        c = model.get(p)
        if c:
            return c[0]
        return wall_of.get(p)

    # ---- cover
    tops = {}
    for (x, y, z) in wall_of:
        tops[(x, z)] = max(tops.get((x, z), -999), y)
    thin = []
    for (x, z), t in tops.items():
        c = int(g.box(x, z, x, z)[0, 0]) - t
        if c < spec["cover"]["min"]:
            thin.append((x, z, c))
    covers = {}
    for r in spec["regions"]:
        cs = [int(g.box(x, z, x, z)[0, 0]) - tops[(x, z)] for (x, z) in tops if owner.get((x, tops[(x, z)], z)) == r["id"]]
        covers[r["id"]] = min(cs) if cs else None
    if thin:
        raise RegionError("%d columns with less than %d of rock over the shell, e.g. %s"
                          % (len(thin), spec["cover"]["min"], thin[:3]))

    # ---- clearance
    cl = spec["clearance"]
    pit, (X0, Z0, _X1, _Z1), _n = RD.region_mask("the_deep", source_root)
    pz_, px_ = np.nonzero(pit)
    pit_x, pit_z = px_ + X0, pz_ + Z0
    rig = next(b for b in [{"x": 3470, "z": 2880, "range": 16}])
    clear = {}
    region_shell_cols = {}
    for part in parts:
        cols = {(x, z) for (x, _y, z) in part.shell}
        region_shell_cols[part.owner] = cols
        edge = [c for c in cols if any((c[0] + a, c[1] + b) not in cols for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
        ds = min(road.distance(x, z) for x, z in edge)
        dp = min(float(np.hypot(pit_x - x, pit_z - z).min()) for x, z in edge[::3])
        clear[part.owner] = {"road": round(ds), "pit": round(dp)}
        if ds < cl["spine"]:
            raise RegionError("%s's shell comes within %.0f of the road (minimum %d)" % (part.owner, ds, cl["spine"]))
        if dp < cl["pit"]:
            raise RegionError("%s's shell comes within %.0f of the Deep's pit (minimum %d)" % (part.owner, dp, cl["pit"]))
    owners = list(region_shell_cols)
    for i, a in enumerate(owners):
        for b in owners[i + 1:]:
            A = np.array(sorted(region_shell_cols[a]), dtype=float)
            dmin = min(float(np.hypot(A[:, 0] - x, A[:, 1] - z).min()) for x, z in list(region_shell_cols[b])[::7])
            if dmin < cl["regions"]:
                raise RegionError("%s and %s are %.0f apart (minimum %d)" % (a, b, dmin, cl["regions"]))
    hab = []
    for r in spec["regions"]:
        hx, hy, hz = info[r["id"]]["habitat"]
        rng = r["habitat_range"]
        dr = road.distance(hx, hz)
        if dr <= rng:
            raise RegionError("%s's Habitat Block reaches the road: %d range, the road %.0f away" % (r["id"], rng, dr))
        if math.hypot(hx - rig["x"], hz - rig["z"]) < rng + rig["range"]:
            raise RegionError("%s's Habitat Block range overlaps the EXP-033 rig's" % r["id"])
        hab.append((r["id"], hx, hz, rng))
        clear[r["id"]]["habitat_to_road"] = round(dr)
    for i, a in enumerate(hab):
        for b in hab[i + 1:]:
            if math.hypot(a[1] - b[1], a[2] - b[2]) < a[3] + b[3]:
                raise RegionError("Habitat Block ranges of %s and %s overlap" % (a[0], b[0]))

    # ---- spawn policy
    trig, ok = triggers(), whitelisted()
    policy = {}
    for part in parts + [f["part"] for f in forks.values()]:
        rid = part.owner.split(":")[0]
        used = {base(b) for b in part.shell.values()} | {base(b) for (b, _p) in part.cells.values() if b}
        for b in sorted(used):
            if b in trig:
                if b not in ok:
                    raise RegionError("%s uses %s, which conditions spawns (%s) and is not whitelisted under %r in "
                                      "data/spawn_block_policy.json" % (rid, b, trig[b][0], SCOPE))
                policy.setdefault(rid, set()).add(b)

    # ---- seal and fluids
    def neighbours(p):
        x, y, z = p
        return ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1))
    open_cells = [p for p, (b, _pas) in model.items() if base(b) in OPEN]
    leaks = []
    for p in open_cells:
        for q in neighbours(p):
            if q not in wall_of and not road.space(*q):
                leaks.append((p, q))
    if leaks:
        raise RegionError("%d open faces touch unauthored rock, e.g. %s -> %s" % (len(leaks), leaks[0][0], leaks[0][1]))
    falls = {tuple(f) for inf in info.values() for f in inf.get("falls", [])}
    spill = []
    for p, (b, _pas) in model.items():
        if b not in (WATER, LAVA):
            continue
        x, y, z = p
        for q, side in zip(neighbours(p), ("x", "x", "up", "down", "z", "z")):
            fq = final(q)
            if fq is None or base(fq) == b or base(fq) not in OPEN:
                continue
            if side == "up" and base(fq) == AIR and p not in falls:
                continue
            if side == "down" and p in falls and base(fq) == AIR:
                continue
            spill.append((p, side, fq))
    if spill:
        raise RegionError("%d fluid faces open onto %s, e.g. %s" % (len(spill), spill[0][2], spill[0][:2]))
    counts["water cells"] = sum(1 for b, _ in model.values() if b == WATER)
    counts["lava cells"] = sum(1 for b, _ in model.values() if b == LAVA)

    # ---- walk-out
    walk = {}
    for r in spec["regions"]:
        walk[r["id"]] = walkout(r, forks[r["id"]], final, road, parts, info[r["id"]])
        if walk[r["id"]]["traps"] or walk[r["id"]]["unreached_floor"] or walk[r["id"]]["lava_without_lip"]:
            raise RegionError("%s walk-out: %s" % (r["id"], json.dumps(walk[r["id"]])))

    # ---- records: the Habitat Blocks and the caches must be where the model put them
    records = check_records(spec, info, strict)

    # ---- the lines, pass by pass
    lines = {pas: [] for pas in PASSES}
    by_col = {}
    for (x, y, z), wb in wall_of.items():
        by_col.setdefault((x, z), []).append((y, wb))
    for (x, z), ys in sorted(by_col.items()):
        lines["shell"] += runs(x, z, sorted(ys))
    per = {pas: {} for pas in ("air", "floor", "fluid")}
    fits = []
    for (x, y, z), (b, pas) in model.items():
        if pas == "fittings":
            fits.append((x, y, z, b))
        elif pas in per:
            per[pas].setdefault((x, z), []).append((y, b))
    for pas in ("air", "floor", "fluid"):
        for (x, z), ys in sorted(per[pas].items()):
            lines[pas] += runs(x, z, sorted(ys))
    # fittings top-down, so a hanging vine always has what it hangs from; the lava falls last of all
    fits.sort(key=lambda f: (f[3] == LAVA, f[0] // TILE, f[2] // TILE, -f[1], f[0], f[2]))
    lines["fittings"] = ["setblock %d %d %d %s" % f for f in fits]

    checks = sample_checks(model, wall_of, info, forks, spec)
    skip = excluded_cells(info, spec) | {tuple(f) for f in falls}
    plan = {"lines": lines, "counts": counts, "checks": checks, "clearance": clear, "cover": covers,
            "policy": {k: sorted(v) for k, v in policy.items()}, "walk": walk, "records": records,
            "regions": {rid: {k: v for k, v in inf.items() if k not in ("pal",)} for rid, inf in info.items()},
            "forks": {rid: {k: v for k, v in f.items() if k != "part"} for rid, f in forks.items()},
            # the whole model, for verify --full; never written to the plan file
            "_model": {p: base(final(p)) for p in wall_of}, "_skip": skip}
    return plan, spec


def runs(x, z, ys):
    """fill commands for one column: consecutive cells of the same block as one fill."""
    out = []
    i = 0
    while i < len(ys):
        y0, b = ys[i]
        j = i
        while j + 1 < len(ys) and ys[j + 1][0] == ys[j][0] + 1 and ys[j + 1][1] == b:
            j += 1
        y1 = ys[j][0]
        out.append("fill %d %d %d %d %d %d %s" % (x, y0, z, x, y1, z, b) if y1 > y0 else
                   "setblock %d %d %d %s" % (x, y0, z, b))
        i = j + 1
    return out


def walkout(r, fork, final, road, parts, inf):
    """From the fork's mouth: where can a player walk, swim or fall, and can they always get back."""
    def blk(p):
        b = final(p)
        if b is None:
            return AIR if road.space(*p) else "rock"
        return base(b)

    def passable(p):
        return blk(p) in PASSABLE

    def solid(p):
        return blk(p) not in OPEN

    def stand(p):
        return passable(p) and passable((p[0], p[1] + 1, p[2])) and (solid((p[0], p[1] - 1, p[2])) or blk(p) == WATER)

    def settle(p):
        x, y, z = p
        for _ in range(40):
            if blk((x, y, z)) == LAVA:
                return None
            if stand((x, y, z)):
                return (x, y, z)
            if not passable((x, y - 1, z)) and blk((x, y - 1, z)) != LAVA:
                return None
            y -= 1
        return None

    mx, my, mz = fork["path"][4]
    start = settle((mx, my, mz))
    if start is None:
        return {"error": "no footing at the fork's mouth %s" % ((mx, my, mz),), "traps": 1,
                "unreached_floor": 0, "lava_without_lip": 0}
    exits = set()
    edges = {}
    seen = {start}
    dq = deque([start])
    while dq:
        p = dq.popleft()
        x, y, z = p
        out = []
        if road.space(x, y, z) or road.space(x, y - 1, z):
            exits.add(p)
            edges[p] = []
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y, z + dz)
            if passable(q) and passable((q[0], y + 1, q[2])):
                s = settle(q)
                if s:
                    out.append(s)
            q = (x + dx, y + 1, z + dz)
            if stand(q) and passable((x, y + 2, z)):
                out.append(q)
        if blk(p) == WATER:
            for q in ((x, y + 1, z), (x, y - 1, z)):
                if passable(q) and passable((q[0], q[1] + 1, q[2])):
                    out.append(q)
        edges[p] = out
        for q in out:
            if q not in seen and abs(q[0] - mx) + abs(q[2] - mz) < 400:
                seen.add(q)
                dq.append(q)
    exits.add(start)
    back = {}
    for p, qs in edges.items():
        for q in qs:
            back.setdefault(q, []).append(p)
    home = set(exits)
    dq = deque(exits)
    while dq:
        q = dq.popleft()
        for p in back.get(q, ()):
            if p not in home:
                home.add(p)
                dq.append(p)
    traps = [p for p in seen if p not in home]
    # every floor cell of the room reachable: a cell with air over a room floor block
    part = next(pp for pp in parts if pp.owner == r["id"])
    # the room's own floor, at the height the room was carved to stand on; the tops of spires, stems, heaps and
    # lips are not floor, and a column whose floor is taken by a fluid or a fitting is skipped by stand()
    floors = [(x, y, z) for (x, z), y in part.floor_h.items() if stand((x, y, z))]
    unreached = [p for p in floors if p not in seen]
    nolip = []
    for p in seen:
        x, y, z = p
        if blk(p) == WATER or not solid((x, y - 1, z)):
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if blk((x + dx, y, z + dz)) == LAVA or blk((x + dx, y - 1, z + dz)) == LAVA:
                nolip.append(p)
    return {"reachable": len(seen), "traps": len(traps), "trap_sample": traps[:3],
            "floor_cells": len(floors), "unreached_floor": len(unreached), "unreached_sample": unreached[:3],
            "lava_without_lip": len(nolip), "nolip_sample": nolip[:3]}


def check_records(spec, info, strict=True):
    """data/habitat_blocks.json and data/rewards.json must hold what the model placed, where it placed it."""
    hb = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))
    by = {b["id"]: b for b in hb.get("blocks") or []}
    rw_path = ROOT / "data" / "rewards.json"
    rw = json.loads(rw_path.read_text(encoding="utf-8")) if rw_path.is_file() else {"rewards": []}
    rby = {x["id"]: x for x in rw.get("rewards") or []}
    out = {}
    for r in spec["regions"]:
        rid = r["id"]
        hx, hy, hz = info[rid]["habitat"]
        want = {"x": hx, "y": hy, "z": hz}
        b = by.get("vr_%s" % rid)
        problems = []
        if not b:
            problems.append("no data/habitat_blocks.json record vr_%s" % rid)
        else:
            if b.get("position") != want:
                problems.append("vr_%s is at %s, the model puts it at %s" % (rid, b.get("position"), want))
            if b.get("pool") != "cobblers:%s" % r["roster"] or b.get("range_of_influence") != r["habitat_range"]:
                problems.append("vr_%s pool or range differs from data/vr_regions.json" % rid)
        if "cache" in info[rid]:
            cx, cy, cz = info[rid]["cache"]
            x = rby.get("vr_%s" % rid)
            if not x:
                problems.append("no data/rewards.json record vr_%s" % rid)
            elif x.get("container", {}).get("at") != [cx, cy, cz]:
                problems.append("vr_%s's container is at %s, the model puts the cache at %s"
                                % (rid, x.get("container", {}).get("at"), [cx, cy, cz]))
        if "npc" in info[rid]:
            x = rby.get("vr_%s" % rid)
            if not x or x.get("kind") != "npc_grant" or x.get("npc_at") != list(info[rid]["npc"]):
                problems.append("vr_%s must be an npc_grant at %s in data/rewards.json" % (rid, list(info[rid]["npc"])))
        out[rid] = problems
    bad = {k: v for k, v in out.items() if v}
    if bad and strict:
        raise RegionError("records disagree with the model: %s" % json.dumps(bad))
    return {k: (v or "ok") for k, v in out.items()}


def excluded_cells(info, spec):
    """Cells the world will not hold as built: the lava falls' columns and the sheet a fall spreads over its pool
    (flowing lava, not air), and each Habitat Block's cell (placed by tools/habitat_blocks.py over the floor)."""
    fall_air = set()
    floor_y = {r["id"]: r["floor_y"] for r in spec["regions"]}
    for rid, inf in info.items():
        for (fx, fy, fz) in inf.get("falls", []):
            for y in range(floor_y[rid], fy + 1):
                fall_air.add((fx, y, fz))
        if "pool" in inf:
            px, py, pz, pr = inf["pool"]
            for dx in range(-pr, pr + 1):
                for dz in range(-pr, pr + 1):
                    for y in (py, py + 1):
                        fall_air.add((px + dx, y, pz + dz))
        fall_air.add(tuple(inf["habitat"]))
    return fall_air


def sample_checks(model, wall_of, info, forks, spec):
    """Cells to look at in a world: a spread of every kind the build writes, and every named thing."""
    fall_air = excluded_cells(info, spec)
    out = []
    items = sorted(model.items())
    for k in range(0, len(items), max(1, len(items) // 1500)):
        (x, y, z), (b, pas) = items[k]
        if (x, y, z) in fall_air or b == LAVA and pas == "fittings":
            continue
        out.append([x, y, z, [base(b)], pas])
    shell = sorted(wall_of.items())
    for k in range(0, len(shell), max(1, len(shell) // 800)):
        p, wb = shell[k]
        if p not in model:
            out.append([p[0], p[1], p[2], [base(wb)], "shell"])
    for rid, inf in info.items():
        if "cache" in inf:
            x, y, z = inf["cache"]
            out.append([x, y, z, ["minecraft:barrel"], "cache"])
        for (x, y, z) in inf.get("falls", []):
            out.append([x, y, z, [LAVA], "fall source"])
    return out


# ------------------------------------------------------------------ write

def write(plan, out=None):
    import shutil
    out = out or OUT
    if out.exists():
        shutil.rmtree(out)
    fn = out / "data" / "cobblers" / "function" / "vr_regions"
    fn.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "Cobblers: Victory Road's regions"}}, indent=2) + "\n", encoding="utf-8")
    order = []
    for k, pas in enumerate(PASSES):
        tiles = {}
        for n, ln in enumerate(plan["lines"][pas]):
            t = ln.split()
            tiles.setdefault((int(t[1]) // TILE, int(t[3]) // TILE), []).append(ln)
        for t in sorted(tiles):
            body = tiles[t]
            for j in range(0, len(body), PART):
                name = "%d%s_%d_%d%s" % (k + 1, pas, t[0], t[1], "" if j == 0 else "_%d" % (j // PART + 1))
                part = FL.ensure_loaded(["# Generated by tools/vr_regions.py: pass %s, tile %d %d" % (pas, t[0], t[1])]
                                        + body[j:j + PART])
                probs = FL.check_lines(part, name)
                if probs:
                    raise RegionError("function %s would be refused: %s" % (name, probs[:3]))
                (fn / (name + ".mcfunction")).write_text("\n".join(part) + "\n", encoding="utf-8")
                order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps({k: v for k, v in plan.items() if k != "lines" and not k.startswith("_")}),
                    encoding="utf-8")
    return order


def verify_full(world, source_root):
    """Every cell of the model against the world: the seal is only as good as the world matching the model."""
    import build_audit
    import runtime_guard
    runtime_guard.check(world, "read")
    plan, _spec = build(source_root, None, strict=False)
    W = build_audit.World(world)
    bad, n = {}, 0
    for p, want in plan["_model"].items():
        if p in plan["_skip"]:
            continue
        n += 1
        got = W.block(*p)
        if got != want:
            bad.setdefault((want, got), []).append(p)
    for (want, got), ps in sorted(bad.items(), key=lambda kv: -len(kv[1])):
        print("  %6d cells: planned %s, world has %s   e.g. %s" % (len(ps), want, got, ps[:2]))
    total = sum(len(v) for v in bad.values())
    print("Victory Road regions, every cell: %d of %d as planned%s"
          % (n - total, n, "" if total == 0 else ", %d MISMATCHES" % total))
    return 0 if total == 0 else 1


def verify(world):
    import build_audit
    import runtime_guard
    runtime_guard.check(world, "read")
    if not PLAN.is_file():
        print("FAIL: no derived/vr_regions/plan.json: run the build first")
        return 1
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    W = build_audit.World(world)
    by, bad = {}, {}
    for x, y, z, allowed, what in p["checks"]:
        got = W.block(x, y, z)
        ok = got in allowed
        by.setdefault(what, [0, 0])[0 if ok else 1] += 1
        if not ok:
            bad.setdefault(what, []).append((x, y, z, got))
    for k in sorted(by):
        good, wrong = by[k]
        print("%-12s %7d of %7d as planned%s" % (k, good, good + wrong, ("   e.g. %s" % bad[k][:2]) if wrong else ""))
    total = sum(b for _, b in by.values())
    print("Victory Road regions: %s" % ("clean" if total == 0 else "%d MISMATCHES" % total))
    return 0 if total == 0 else 1


def show(plan):
    for k, v in sorted(plan["counts"].items()):
        print("  %-36s %9d" % (k, v))
    for rid in plan["regions"]:
        inf, f, w = plan["regions"][rid], plan["forks"][rid], plan["walk"][rid]
        print("  %-16s cover %3s  road %3s  pit %4s  hab->road %3s  fork %3d blocks grade %.2f  walk %5d reachable, "
              "%d floor, 0 traps  policy %s"
              % (rid, plan["cover"][rid], plan["clearance"][rid]["road"], plan["clearance"][rid]["pit"],
                 plan["clearance"][rid]["habitat_to_road"], f["length"], f["grade"], w["reachable"], w["floor_cells"],
                 ",".join(b.split(":")[1] for b in plan["policy"].get(rid, [])) or "-"))
        extras = {k: v for k, v in inf.items() if k in ("cache", "npc", "habitat", "falls", "pool", "entry")}
        print("  %-16s %s" % ("", json.dumps(extras)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "report", "verify"))
    ap.add_argument("--source-root")
    ap.add_argument("--server-dir")
    ap.add_argument("--world")
    ap.add_argument("--full", action="store_true", help="verify: every cell of the model, not the plan's sample")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        if not a.world:
            ap.error("verify needs --world")
        return verify_full(a.world, a.source_root) if a.full else verify(a.world)
    try:
        plan, _spec = build(a.source_root, a.server_dir, strict=a.cmd != "report")
    except RegionError as exc:
        print("vr_regions: %s" % exc)
        return 1
    show(plan)
    for rid, v in plan["records"].items():
        if v != "ok":
            print("  records %s: %s" % (rid, "; ".join(v)))
    if a.cmd == "report":
        return 0
    order = write(plan)
    n = sum(len(v) for v in plan["lines"].values())
    print("Victory Road regions: %d functions, %d commands" % (len(order), n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
