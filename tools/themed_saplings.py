#!/usr/bin/env python
"""Themed saplings: a world-tree sapling shaped by the country it grows in, and the one bird that nests in it.

The owner, 2026-09-26: "i think there should be themed saplings per region", a palm by the sea for a sea bird, a tree
by a lake for a water bird, "a scorch sapling for fire types in the south near craters", one in the tundra. The idea
is the elders' (tools/elder_trees.py, docs/world-building/SAPLING_BIRDS.md) carried out of the woods: a tree a player
sees from a distance and knows what lives in it, "similar to like seeing a volcano and knowing a fire type would be
there". An elder only grows in woodland and never within 24 blocks of water, so none of these countries has one.

Seven themes, each a tree shape and a bird (the pools are data/spawns.json habitats `sapling_<theme>_<subregion>`):

  palm       sea coasts of the warm isles and the east dunes   a curved jungle-log palm, drooping fronds    Wingull
  lakeshore  lake banks                                       a weeping mangrove over the water             Ducklett
  scorched   the crater country in the south-east             a charred basalt giant, ember seams           Fletchinder
  frost      Frostpeak and the glacier's foot                 a snow-loaded spruce spire                    Delibird
  storm      the Rift, under its permanent thunderstorm       a split, lightning-scarred oak with a rod     Wattrel
  crag       the high peaks                                   a windswept pine with flat, leaning pads      Skarmory
  desert     the dunes and the badlands                       a bleached dead tree of bone                  Vullaby

Siting, one tree per listed sub-region, on the heightmap's ground (tools/ground.py), never a world:
  pad       9x9 around the trunk centre, relief at most the theme's limit
  water     palm: the sea within 6-32 blocks of the trunk and none on the pad; lakeshore: a painted lake (not the sea)
            within 5-28 and none on the pad; every other theme: no water within 16
  spacing   220 from every elder, landmark tree and other themed sapling; clear of landmark glades by 80
  path      at least 40 from a routed leg centreline (they are meant to be seen), within 700 of one where the region
            allows it; at least 120 from a town centre and 100 from every building in data/placements.json
  inside    the theme's inset inside the sub-region polygon
Sites are pinned in data/themed_saplings.json on the first run and placed from the pins after that (--repick to
choose again): a re-pick would move a tree out from under its nest blocks, as it did once for the elders.

Each shape records its nest points: cells of its own trunk or crown, solid on all six faces, where the activated
Habitat Blocks go (the elders' nests, data/habitat_blocks.json, `records --write`).

  python tools/themed_saplings.py [--repick]            prefabs, pins, derived/sites/themed_saplings.json and
                                                        build/themed_saplings/themed_saplings.mcfunction (not run)
  python tools/themed_saplings.py records [--write]     the nest blocks for data/habitat_blocks.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import terrain as T
import structure_nbt as S
import function_limits
from landmark_trees import _ball, _rng
from place_town import rotate
from elder_trees import region_mask, seg_distance, footprint, ROTATIONS

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "data" / "themed_saplings.json"
PREFABS = ROOT / "kits" / "structures" / "prefabs" / "trees" / "themed"
SITES = ROOT / "derived" / "sites" / "themed_saplings.json"
FUNCTION = ROOT / "build" / "themed_saplings" / "themed_saplings.mcfunction"
MANIFEST = ROOT / "data" / "habitat_blocks.json"

PAD, GRID = 4, 8
SPACING, GLADE_CLEAR, OFF_TOWN, OFF_LEG, NEAR_LEG = 220, 80, 120, 40, 700
OFF_BUILT = 100              # from every placement in data/placements.json (a town's houses reach past its centre's 120)
NEST = {"spawn_range": 16, "chance": 1.0, "trigger": "TICK", "cancel_range": -1, "max_spawns": 8,
        "max_spawns_per_activation": 2}

THEMES = {
    "palm": {"regions": ["sunset_east", "sunset_west", "east_coast_dunes"], "water": ("sea", 6, 32),
             "relief": 3.0, "inset": 12, "bird": "Wingull"},
    "lakeshore": {"regions": ["arrow_lake_shores", "tilpey_south_shore"], "water": ("lake", 5, 28),
                  "relief": 3.0, "inset": 16, "bird": "Ducklett"},
    "scorched": {"regions": ["great_crater", "crater_rim_north_west", "east_cones"], "water": ("dry", 16),
                 "relief": 4.0, "inset": 24, "bird": "Fletchinder"},
    "frost": {"regions": ["frostpeak", "frostpeak_strand", "glacier_foot_fields"], "water": ("dry", 16),
              "relief": 4.0, "inset": 24, "bird": "Delibird"},
    "storm": {"regions": ["rift_trunk", "rift_west_spur", "rift_foot"], "water": ("dry", 16),
              "relief": 4.0, "inset": 24, "bird": "Wattrel"},
    "crag": {"regions": ["the_crags", "mt_vessu", "the_tri_peaks"], "water": ("dry", 16),
             "relief": 5.0, "inset": 24, "bird": "Skarmory"},
    "desert": {"regions": ["south_east_dunes", "plateau_west", "long_isle_north"], "water": ("dry", 16),
               "relief": 3.0, "inset": 24, "bird": "Vullaby"},
}


# ------------------------------------------------------------------ drawing
def _disc(b, cx, y, cz, r, block, props=None):
    ri = int(math.ceil(r))
    for dx in range(-ri - 1, ri + 2):
        for dz in range(-ri - 1, ri + 2):
            if (dx + (cx - round(cx))) ** 2 + (dz + (cz - round(cz))) ** 2 <= r * r + 0.3:
                b.set(round(cx) + dx, y, round(cz) + dz, block, props)


def _line(b, a, c, r, block, axial=True, taper=0.45, soft=False):
    """A thick branch of `block` from a to c, radius r tapering by `taper`; axis-oriented when `axial`."""
    d = math.dist(a, c)
    n = max(2, int(d * 1.6))
    dx, dy, dz = (c[i] - a[i] for i in range(3))
    axis = "y" if abs(dy) >= max(abs(dx), abs(dz)) else ("x" if abs(dx) >= abs(dz) else "z")
    props = {"axis": axis} if axial else None
    put = b.setdefault if soft else b.set
    for i in range(n + 1):
        t = i / n
        px, py, pz = a[0] + dx * t, a[1] + dy * t, a[2] + dz * t
        rr = max(0.5, r * (1 - taper * t))
        ri = int(math.ceil(rr))
        for ox in range(-ri, ri + 1):
            for oy in range(-ri, ri + 1):
                for oz in range(-ri, ri + 1):
                    if ox * ox + oy * oy + oz * oz <= rr * rr + 0.25:
                        put(round(px + ox), round(py + oy), round(pz + oz), block, props)


def _roots(b, n, radius, top, block, rng, axial=True):
    for k in range(n):
        ang = 2 * math.pi * (k + rng.uniform(-0.2, 0.2)) / n
        L = radius * rng.uniform(0.7, 1.1)
        for i in range(int(L)):
            h = int(round(top * (1 - i / max(L, 1))))
            x, z = round(math.cos(ang) * i), round(math.sin(ang) * i)
            for y in range(-2, h + 1):
                b.set(x, y, z, block, {"axis": "y"} if axial else None)


def _leaf(kind):
    return ("minecraft:%s_leaves" % kind, {"distance": "1", "persistent": "true", "waterlogged": "false"})


def _nest_points(b, wants, material_prefix):
    """For each wanted (x, y, z), the nearest cell within 3 blocks whose block starts with material_prefix and whose
    six neighbours are all solid (so the Habitat Block is hidden and no bird stands on it)."""
    out = []
    for wx, wy, wz in wants:
        best = None
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                for dz in range(-3, 4):
                    p = (round(wx) + dx, round(wy) + dy, round(wz) + dz)
                    name = b.get(*p)
                    if not name or not name.startswith(material_prefix):
                        continue
                    if not all(b.get(p[0] + ox, p[1] + oy, p[2] + oz)
                               for ox, oy, oz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))):
                        continue
                    d = dx * dx + dy * dy + dz * dz
                    if best is None or d < best[0]:
                        best = (d, p)
        if best is None:
            raise SystemExit("no buried %s cell near %s" % (material_prefix, (wx, wy, wz)))
        out.append({"at": list(best[1]), "mimic": b.get(*best[1])})
    return out


def palm(rng):
    b = S.Builder()
    log = "minecraft:jungle_log"
    H = int(rng.integers(50, 56))
    lean, ang = rng.uniform(7, 10), rng.uniform(0, 2 * math.pi)
    centre = {}
    for y in range(-2, H + 1):
        off = lean * (max(y, 0) / H) ** 2
        cx, cz = math.cos(ang) * off, math.sin(ang) * off
        r = 2.3 if y < 3 else (1.7 if y < H * 0.55 else 1.3)
        _disc(b, cx, y, cz, r, log, {"axis": "y"})
        centre[y] = (cx, cz)
    _roots(b, 7, 6, 2, log, rng)
    tx, tz = centre[H]
    _ball(b, tx, H + 1, tz, 3.4, 2.6, 3.4, _leaf("jungle"), rng, ragged=0.1)
    n = int(rng.integers(10, 13))
    for k in range(n):
        a = 2 * math.pi * k / n + rng.uniform(-0.18, 0.18)
        L, rise, droop = rng.uniform(15, 19), rng.uniform(2.5, 4), rng.uniform(10, 14)
        steps = int(L * 2)
        for s in range(steps + 1):
            u = s / steps
            d = u * L
            y = H + 2 + 2 * rise * u - (2 * rise + droop) * u * u
            x, z = tx + math.cos(a) * d, tz + math.sin(a) * d
            b.setdefault(round(x), round(y), round(z), *_leaf("jungle"))
            if u < 0.8:                                               # leaflets either side of the rib
                px, pz = -math.sin(a), math.cos(a)
                for side in (-1, 1):
                    b.setdefault(round(x + px * side), round(y - 0.4), round(z + pz * side), *_leaf("jungle"))
            if u > 0.55:
                b.setdefault(round(x), round(y) - 1, round(z), *_leaf("jungle"))
    # coconuts: cocoa pods hung on the trunk just under the head, each facing the log it grows on
    ix, iz = round(tx), round(tz)
    for y in (H - 2, H - 3):
        for dx, dz, facing in ((2, 0, "west"), (-2, 0, "east"), (0, 2, "north"), (0, -2, "south")):
            if b.get(ix + dx, y, iz + dz) is None and (b.get(ix + dx - (dx > 0) + (dx < 0), y, iz + dz - (dz > 0) + (dz < 0)) or "").endswith("jungle_log") and rng.random() < 0.6:
                b.set(ix + dx, y, iz + dz, "minecraft:cocoa", {"age": "2", "facing": facing})
    nests = _nest_points(b, [(*_xz(centre, 10), ), (*_xz(centre, 28), ), (*_xz(centre, 44), )],
                         "minecraft:jungle_log") + _nest_points(b, [(tx, H + 1, tz)], "minecraft:jungle_leaves")
    return b, nests, H + 4


def _xz(centre, y):
    cx, cz = centre[y]
    return cx, y, cz


def lakeshore(rng):
    b = S.Builder()
    log, leaf = "minecraft:mangrove_log", _leaf("mangrove")
    lean = rng.uniform(0, 2 * math.pi)
    for y in range(-2, 27):
        f = 1.0 if y < 12 else 1 - 0.35 * (y - 12) / 15
        _disc(b, math.cos(lean) * y * 0.08, y, math.sin(lean) * y * 0.08, 3.0 * f, log, {"axis": "y"})
    # arching prop roots, as a mangrove stands in the shallows
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.uniform(-0.2, 0.2)
        reach = rng.uniform(7, 11)
        pts = [(math.cos(a) * (2 + reach * t), 7 * math.sin(math.pi * t * 0.9) - 3 * t, math.sin(a) * (2 + reach * t))
               for t in np.linspace(0, 1, 14)]
        for p in pts:
            b.setdefault(round(p[0]), round(p[1]), round(p[2]), "minecraft:mangrove_roots", {"waterlogged": "false"})
    top = 46
    for k in range(6):
        a = 2 * math.pi * k / 6 + rng.uniform(-0.3, 0.3)
        tip = (math.cos(a) * rng.uniform(10, 14), rng.uniform(33, 39), math.sin(a) * rng.uniform(10, 14))
        _line(b, (0, 24, 0), tip, 1.4, log)
    R = 22.0
    for dx in range(-23, 24):
        for dz in range(-23, 24):
            d = math.hypot(dx, dz)
            if d > R:
                continue
            crown = top - int((d / R) ** 2 * 12)
            thick = 4 if d < R - 4 else 2
            for y in range(crown - thick, crown + 1):
                if d > R - 1.2 and rng.random() < 0.3:
                    continue
                b.setdefault(dx, y, dz, *leaf)
            if d > R - 5 and rng.random() < 0.6:                       # the weeping curtain, nearly to the water
                length = int(rng.integers(8, max(9, crown - thick - 2)))
                for y in range(crown - thick - 1, max(2, crown - thick - 1 - length), -1):
                    b.setdefault(dx, y, dz, *leaf)
    nests = _nest_points(b, [(0, 8, 0), (0, 22, 0)], "minecraft:mangrove_log") \
        + _nest_points(b, [(0, top - 2, 0)], "minecraft:mangrove_leaves")
    return b, nests, top


def scorched(rng):
    b = S.Builder()
    trunk = "minecraft:polished_basalt"
    H = int(rng.integers(54, 60))
    for y in range(-2, H):
        r = 3.2 * (1 - 0.6 * max(0, y - 6) / H)
        _disc(b, 0, y, 0, r, trunk, {"axis": "y"})
    for x in range(-2, 3):                                            # a broken, jagged top
        for z in range(-2, 3):
            for y in range(H, H + int(rng.integers(0, 6))):
                if x * x + z * z <= 4:
                    b.set(x, y, z, trunk, {"axis": "y"})
    _roots(b, 9, 9, 3, trunk, rng)
    for k in range(7):
        a = 2 * math.pi * k / 7 + rng.uniform(-0.3, 0.3)
        y0 = rng.uniform(18, 44)
        reach = rng.uniform(10, 16) * (1 - (y0 - 18) / 60)
        tip = (math.cos(a) * reach, y0 + rng.uniform(5, 11), math.sin(a) * reach)
        _line(b, (0, y0, 0), tip, 1.3, trunk)
        for j in range(2):
            a2 = a + rng.uniform(-0.9, 0.9)
            sub = (tip[0] + math.cos(a2) * rng.uniform(4, 7), tip[1] + rng.uniform(1, 5), tip[2] + math.sin(a2) * rng.uniform(4, 7))
            _line(b, tip, sub, 0.7, trunk)
    for k in range(40):                                               # a charcoal heap at the foot
        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(3, 7)
        b.setdefault(round(math.cos(a) * d), 0, round(math.sin(a) * d),
                     "minecraft:coal_block" if rng.random() < 0.35 else "minecraft:blackstone")
    # ember seams: magma only where trunk stands above it, so nothing can stand on a magma block
    for (x, y, z), (name, _) in list(b.blocks.items()):
        if name == trunk and 2 < y < H - 6 and x * x + z * z >= 5 and rng.random() < 0.09 \
                and b.get(x, y + 1, z) == trunk:
            b.set(x, y, z, "minecraft:magma_block")
    nests = _nest_points(b, [(0, 10, 0), (0, 28, 0), (0, 46, 0)], trunk)
    return b, nests, H + 5


def frost(rng):
    b = S.Builder()
    log, leaf = "minecraft:spruce_log", _leaf("spruce")
    H = int(rng.integers(72, 78))
    for y in range(-2, H - 2):
        r = 2.4 if y < H * 0.7 else 1.4
        _disc(b, 0, y, 0, r, log, {"axis": "y"})
    _roots(b, 8, 7, 3, log, rng)
    base = 18
    for y in range(H + 2, base - 1, -1):
        f = (H + 2 - y) / (H + 2 - base)
        r = 1.5 + 14 * f ** 0.9
        step = (H + 2 - y) % 5
        rr = r if step == 0 else r * (0.5 if step in (2, 3) else 0.38)
        for dx in range(-int(rr) - 1, int(rr) + 2):
            for dz in range(-int(rr) - 1, int(rr) + 2):
                d = math.hypot(dx, dz)
                if d <= rr and not (d > rr - 1.3 and rng.random() < 0.3):
                    b.setdefault(dx, y, dz, *leaf)
                    if step == 0 and d > rr - 2 and rng.random() < 0.5:
                        b.setdefault(dx, y - 1, dz, *leaf)
        if step == 0 and y < H - 8:
            for a in rng.uniform(0, 2 * math.pi, 4):
                _line(b, (0, y - 1, 0), (math.cos(a) * (r - 2), y - 2, math.sin(a) * (r - 2)), 0.6, log)
    for (x, y, z), (name, _) in list(b.blocks.items()):                # snow lying on every open ledge
        if name == leaf[0] and b.get(x, y + 1, z) is None and rng.random() < 0.85:
            b.set(x, y + 1, z, "minecraft:snow", {"layers": str(int(rng.integers(1, 4)))})
    nests = _nest_points(b, [(0, 12, 0), (0, 34, 0), (0, 56, 0)], log)
    return b, nests, H + 4


def storm(rng):
    b = S.Builder()
    log, leaf = "minecraft:oak_log", _leaf("dark_oak")
    for y in range(-2, 31):
        _disc(b, 0, y, 0, 3.3 * (1 - 0.25 * max(0, y - 10) / 20), log, {"axis": "y"})
    _roots(b, 10, 10, 4, log, rng)
    a = rng.uniform(0, 2 * math.pi)
    tipA = (math.cos(a) * 6, 64, math.sin(a) * 6)                     # the taller leader carries the rod
    tipB = (math.cos(a + 2.6) * 7, 52, math.sin(a + 2.6) * 7)
    _line(b, (0, 28, 0), tipA, 2.4, log, taper=0.5)
    _line(b, (0, 28, 0), tipB, 2.0, log, taper=0.5)
    # the strike's scar: a stripped, charred seam down the side that faces the rod leader, and a charred cleft
    sx, sz = math.cos(a), math.sin(a)
    for y in range(0, 34):
        for w in (-1, 0, 1):
            x, z = round(sx * 3 - sz * w), round(sz * 3 + sx * w)
            if b.get(x, y, z) == log:
                b.set(x, y, z, "minecraft:blackstone" if (y + w) % 3 == 0 else "minecraft:stripped_oak_log",
                      None if (y + w) % 3 == 0 else {"axis": "y"})
    for dx in range(-1, 2):
        for dz in range(-1, 2):
            b.set(dx, 30, dz, "minecraft:blackstone")
    for tip, rad in ((tipA, 7.0), (tipB, 5.5)):
        _ball(b, tip[0], tip[1] - 2, tip[2], rad, rad * 0.55, rad, leaf, rng, ragged=0.45)
        for j in range(3):                                            # bare, broken limbs through the thin crown
            a2 = rng.uniform(0, 2 * math.pi)
            _line(b, (tip[0], tip[1] - 6, tip[2]),
                  (tip[0] + math.cos(a2) * 8, tip[1] - rng.uniform(0, 6), tip[2] + math.sin(a2) * 8), 0.7, log)
    ax, az = round(tipA[0]), round(tipA[2])
    top = max(y for (x, y, z) in b.blocks if (x, z) == (ax, az))
    for y in range(int(tipA[1]), top + 2):                             # the leader rises clear of its own leaves
        b.set(ax, y, az, log, {"axis": "y"})
    b.set(ax, top + 2, az, "minecraft:lightning_rod", {"facing": "up", "powered": "false", "waterlogged": "false"})
    mid = ((tipA[0]) * 0.55, 28 + (tipA[1] - 28) * 0.55, (tipA[2]) * 0.55)
    nests = _nest_points(b, [(0, 10, 0), (0, 24, 0), mid], "minecraft:oak_log")
    return b, nests, top + 2


def crag(rng):
    b = S.Builder()
    log, leaf = "minecraft:spruce_log", _leaf("spruce")
    H = int(rng.integers(44, 50))
    wind = rng.uniform(0, 2 * math.pi)
    wx, wz = math.cos(wind), math.sin(wind)
    centre = {}
    for y in range(-2, H + 1):
        t = max(y, 0) / H
        off = 6 * t * t + 2.5 * math.sin(t * math.pi * 1.5)          # an S-bend leaning downwind
        cx, cz = wx * off, wz * off
        _disc(b, cx, y, cz, 2.3 if y < 8 else (1.7 if y < H * 0.6 else 1.2), log, {"axis": "y"})
        centre[y] = (cx, cz)
    _roots(b, 9, 10, 3, log, rng)                                     # long roots gripping the rock
    for py, rad in ((24, 9), (32, 11), (39, 10), (H, 8)):
        cx, cz = centre[min(py, H)]
        px, pz = cx + wx * rad * 0.45, cz + wz * rad * 0.45
        _line(b, (cx, py - 2, cz), (px, py, pz), 0.9, log)
        _ball(b, px, py + 1, pz, rad, 1.8, rad * 0.8, leaf, rng, ragged=0.25)
    nests = _nest_points(b, [_xz(centre, 10), _xz(centre, 22), _xz(centre, 34)], log)
    return b, nests, H + 3


def desert(rng):
    b = S.Builder()
    bone = "minecraft:bone_block"
    H = 36
    for y in range(-2, H):
        _disc(b, 0, y, 0, 2.6 * (1 - 0.4 * max(0, y - 4) / H), bone, {"axis": "y"})
    _roots(b, 7, 8, 2, bone, rng)

    def branch(a, c, r, depth):
        _line(b, a, c, r, bone)
        if depth == 0:
            return
        base = math.atan2(c[2] - a[2], c[0] - a[0])
        for j in range(2):
            a2 = base + rng.uniform(-0.9, 0.9)
            L = math.dist(a, c) * rng.uniform(0.55, 0.75)
            nxt = (c[0] + math.cos(a2) * L, c[1] + L * rng.uniform(0.3, 0.8), c[2] + math.sin(a2) * L)
            branch(c, nxt, r * 0.62, depth - 1)

    for k in range(4):
        a = 2 * math.pi * k / 4 + rng.uniform(-0.35, 0.35)
        y0 = rng.uniform(20, 32)
        branch((0, y0, 0), (math.cos(a) * rng.uniform(9, 12), y0 + rng.uniform(7, 12), math.sin(a) * rng.uniform(9, 12)),
               1.5, 2)
    branch((0, H - 2, 0), (rng.uniform(-2, 2), H + 10, rng.uniform(-2, 2)), 1.5, 2)
    nests = _nest_points(b, [(0, 10, 0), (0, 22, 0), (0, 32, 0)], bone)
    top = max(y for (_, y, _) in b.blocks)
    return b, nests, top


SHAPES = {"palm": palm, "lakeshore": lakeshore, "scorched": scorched, "frost": frost, "storm": storm, "crag": crag,
          "desert": desert}


def write_prefab(theme, b, nests, height):
    PREFABS.mkdir(parents=True, exist_ok=True)
    name = "sapling_%s" % theme
    data, shift = b.to_bytes()
    (PREFABS / (name + ".nbt")).write_bytes(data)
    lo, hi = b.bounds()
    side = {"schema": "cobblers.prefab/1", "template_id": "cobblers:kits/trees/themed/%s" % name, "kind": "trees",
            "set": "themed", "name": name, "author": "tools/themed_saplings.py",
            "source": {"file": "generated", "size": (hi - lo + 1).tolist(), "blocks": len(b.blocks)},
            "entrance": None, "grade_layer": None, "trunk_origin": [int(v) for v in shift], "tier": "themed_sapling",
            "theme": theme, "height": int(height),
            "nests": [{"at": n["at"], "mimic": n["mimic"]} for n in nests],
            "notes": "the trunk centre's base is builder (0, 0, 0): template trunk_origin; nest `at` is in builder "
                     "coordinates (add trunk_origin for template coordinates)"}
    (PREFABS / (name + ".json")).write_text(json.dumps(side, indent=1) + "\n", encoding="utf-8")
    return side


def build_prefabs():
    return {t: write_prefab(t, *f(_rng("themed_sapling_%s" % t))) for t, f in SHAPES.items()}


# ------------------------------------------------------------------ siting
def water_masks(heights, world):
    sea = heights <= T.sea_level(world)
    man = json.loads((ROOT / "build" / "paint" / "manifest.json").read_text(encoding="utf-8"))
    lake = np.zeros_like(sea)
    for w in man["water"]:
        key = "levels" if "levels" in w else "mask"
        m = np.asarray(Image.open(ROOT / "build" / "paint" / w[key])) > 0
        lake[w["z"]:w["z"] + m.shape[0], w["x"]:w["x"] + m.shape[1]] |= m
    return sea, lake & ~sea


def pick_sites(heights, world, ground_of):
    subs = {s["id"]: s for s in json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["subregions"]}
    foliage = json.loads((ROOT / "data" / "foliage.json").read_text(encoding="utf-8"))
    towns = [(t["centre"]["x"], t["centre"]["z"]) for t in
             json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
             if (t.get("centre") or {}).get("x") is not None]
    glades = [(t["site"][0], t["site"][1], t["glade_radius"]) for t in foliage["landmark_trees"]]
    built = [(p["position"]["x"], p["position"]["z"]) for p in
             json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
             if isinstance(p.get("position"), dict) and p["position"].get("x") is not None]
    elders =json.loads((ROOT / "derived" / "sites" / "elder_trees.json").read_text(encoding="utf-8"))
    taken = [(s["x"], s["z"]) for r in elders["regions"] for s in r["sites"]] + [(g[0], g[1]) for g in glades]
    grove = ROOT / "derived" / "sites" / "tree_grove_foothill_woods.json"
    if grove.is_file():
        taken += [(e["x"], e["z"]) for e in json.loads(grove.read_text(encoding="utf-8")).get("elders") or []]
    legs = json.loads((ROOT / "derived" / "routes" / "critical_legs.json").read_text(encoding="utf-8"))["legs"]
    pts = np.concatenate([np.asarray(l["polyline"], float) for l in legs])
    breaks = np.cumsum([len(l["polyline"]) for l in legs])[:-1]
    keep = np.ones(len(pts) - 1, bool)
    keep[breaks - 1] = False
    a, bb = pts[:-1][keep], pts[1:][keep]
    segs = (a, bb - a, np.maximum(((bb - a) ** 2).sum(1), 1e-9))
    sea, lake = water_masks(heights, world)
    n = heights.shape[0]
    out, notes = [], []
    for theme, spec in THEMES.items():
        kind = spec["water"][0]
        for sid in spec["regions"]:
            sub = subs[sid]
            bnd = sub["measured"]["bounds"]
            m = 48
            x0, z0, x1, z1 = bnd["min_x"] - m, bnd["min_z"] - m, bnd["max_x"] + m, bnd["max_z"] + m
            cx0, cz0, cx1, cz1 = max(0, x0), max(0, z0), min(n - 1, x1), min(n - 1, z1)
            g = np.full((z1 - z0 + 1, x1 - x0 + 1), -30001, dtype=int)
            g[cz0 - z0:cz1 - z0 + 1, cx0 - x0:cx1 - x0 + 1] = ground_of.box(cx0, cz0, cx1, cz1)
            s_m = np.zeros_like(g, bool)
            l_m = np.zeros_like(g, bool)
            s_m[cz0 - z0:cz1 - z0 + 1, cx0 - x0:cx1 - x0 + 1] = sea[cz0:cz1 + 1, cx0:cx1 + 1]
            l_m[cz0 - z0:cz1 - z0 + 1, cx0 - x0:cx1 - x0 + 1] = lake[cz0:cz1 + 1, cx0:cx1 + 1]
            wet = s_m | l_m
            inside = region_mask(sub, x0, z0, g.shape[1], g.shape[0])
            ins = spec["inset"]
            cands = []
            for relax in (False, True):
                for z in range(bnd["min_z"], bnd["max_z"] + 1, GRID):
                    for x in range(bnd["min_x"], bnd["max_x"] + 1, GRID):
                        lx, lz = x - x0, z - z0
                        if not inside[max(0, lz - ins):lz + ins + 1, max(0, lx - ins):lx + ins + 1].all():
                            continue
                        pad = g[lz - PAD:lz + PAD + 1, lx - PAD:lx + PAD + 1]
                        if pad.min() <= -30000 or wet[lz - PAD:lz + PAD + 1, lx - PAD:lx + PAD + 1].any():
                            continue
                        relief = float(pad.max() - pad.min())
                        if relief > spec["relief"]:
                            continue
                        if kind == "dry":
                            r = spec["water"][1]
                            if wet[lz - r:lz + r + 1, lx - r:lx + r + 1].any():
                                continue
                        else:
                            lo, hi = spec["water"][1], spec["water"][2]
                            mask = s_m if kind == "sea" else l_m
                            win = mask[lz - hi:lz + hi + 1, lx - hi:lx + hi + 1]
                            ys, xs = np.nonzero(win)
                            if not len(xs):
                                continue
                            dw = float(np.hypot(xs - hi, ys - hi).min())
                            if dw < lo:
                                continue
                        if any(math.hypot(tx - x, tz - z) < OFF_TOWN for tx, tz in towns):
                            continue
                        if any(abs(bx - x) < OFF_BUILT and abs(bz - z) < OFF_BUILT
                               and math.hypot(bx - x, bz - z) < OFF_BUILT for bx, bz in built):
                            continue
                        if any(math.hypot(gx - x, gz - z) < gr + GLADE_CLEAR for gx, gz, gr in glades):
                            continue
                        if any(math.hypot(px - x, pz - z) < SPACING for px, pz in taken):
                            continue
                        dleg = seg_distance(x, z, *segs)
                        if dleg < OFF_LEG or (dleg > NEAR_LEG and not relax):
                            continue
                        cands.append((x, z, relief, int(g[lz, lx]), dleg))
                if cands:
                    if relax:
                        notes.append("%s: no site within %d of a leg; placed farther" % (sid, NEAR_LEG))
                    break
            if not cands:
                notes.append("%s (%s): no site passes" % (sid, theme))
                continue
            # the flattest pad, then the nearest to a leg: a landmark that is found, not stumbled over
            x, z, relief, gy, dleg = min(cands, key=lambda c: (round(c[2]), c[4]))
            rng = _rng("themed_sapling_site_%s" % sid)
            out.append({"id": "sapling_%s_%s" % (theme, sid), "theme": theme, "subregion": sid, "x": x, "z": z,
                        "ground_y": gy, "rotation": ROTATIONS[int(rng.integers(4))],
                        "pad_relief": round(relief, 1), "distance_to_nearest_leg": round(dleg)})
            taken.append((x, z))
    return out, notes


# ------------------------------------------------------------------ placement
def place(site, side):
    """(template pos, rotated footprint) for one pinned site: the trunk centre's base lands on (x, ground + 1, z)."""
    ox, oy, oz = side["trunk_origin"]
    qx, qz = rotate(ox, oz, site["rotation"])
    px, pz = site["x"] - qx, site["z"] - qz
    sx, _, sz = side["source"]["size"]
    return (px, site["ground_y"] + 1 - oy, pz), footprint(px, pz, sx, sz, site["rotation"])


def nest_world(site, side, nest):
    """World position of a nest point: builder coordinates -> template -> rotated -> world."""
    ox, oy, oz = side["trunk_origin"]
    (px, py, pz), _ = place(site, side)
    tx, ty, tz = nest["at"][0] + ox, nest["at"][1] + oy, nest["at"][2] + oz
    rx, rz = rotate(tx, tz, site["rotation"])
    return {"x": px + rx, "y": py + ty, "z": pz + rz}


def load_pins():
    return json.loads(PINS.read_text(encoding="utf-8"))["saplings"] if PINS.is_file() else None


def sides():
    return {t: json.loads((PREFABS / ("sapling_%s.json" % t)).read_text(encoding="utf-8")) for t in SHAPES}


def records(pins, sd):
    out = []
    for s in pins:
        side = sd[s["theme"]]
        for i, nest in enumerate(side["nests"]):
            label = ("low", "mid", "high", "top")[i] if i < 4 else str(i)
            out.append({"id": "%s_%s" % (s["id"], label),
                        "place": "the %s sapling %s: inside its %s" % (s["theme"], s["id"],
                                                                       "crown" if "leaves" in nest["mimic"] else "trunk"),
                        "pool": "cobblers:%s" % s["id"], "style": "activated", "replace_spawns": False,
                        "position": nest_world(s, side, nest), "mimic": nest["mimic"], "activated": dict(NEST),
                        "status": "planned",
                        "why": "A nest in a themed sapling (tools/themed_saplings.py; the owner, 2026-09-26: themed "
                               "saplings per region, each the home of one bird). The point is a cell of the tree's own "
                               "%s, solid on all six faces in the prefab %s, so the block is hidden. Up to 8 of the "
                               "tree's bird alive within 16 blocks of it, as in the elders' nests."
                               % ("crown" if "leaves" in nest["mimic"] else "trunk", side["template_id"])})
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("cmd", nargs="?", default="build", choices=["build", "records"])
    p.add_argument("--repick", action="store_true")
    p.add_argument("--write", action="store_true", help="records: merge the nest blocks into data/habitat_blocks.json")
    a = p.parse_args(argv)
    if a.cmd == "records":
        pins, sd = load_pins(), sides()
        recs = records(pins, sd)
        if a.write:
            doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
            old = {b["id"]: b for b in doc["blocks"] if b["id"].startswith("sapling_")}
            for r in recs:                                             # a block already placed keeps its status
                if r["id"] in old and old[r["id"]]["position"] == r["position"]:
                    r["status"] = old[r["id"]]["status"]
            doc["blocks"] = [b for b in doc["blocks"] if not b["id"].startswith("sapling_")] + recs
            MANIFEST.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"nest_blocks": len(recs), "written": a.write}, indent=1))
        return 0
    heights, world = T.load_from_args(a)
    import ground as G
    ground_of = G.load(a.source_root) if a.source_root else G.load()
    sd = build_prefabs()
    pins, notes = load_pins(), []
    if pins is None or a.repick:
        pins, notes = pick_sites(heights, world, ground_of)
        PINS.write_text(json.dumps({
            "schema": "cobblers.themed-saplings/1",
            "note": "Pinned sites of the themed saplings (tools/themed_saplings.py picked them; placed from here after "
                    "that, so a tree never moves out from under its nest blocks). ground_y is tools/ground.py's.",
            "saplings": pins}, indent=2) + "\n", encoding="utf-8")
    cmds = ["# themed saplings: %d trees (tools/themed_saplings.py); run with no players near these columns" % len(pins)]
    for s in pins:
        side = sd[s["theme"]]
        (px, py, pz), (lo_x, lo_z, hi_x, hi_z) = place(s, side)
        cmds += ["# %s" % s["id"], "forceload add %d %d %d %d" % (lo_x - 16, lo_z - 16, hi_x + 16, hi_z + 16),
                 "place template %s %d %d %d %s none 1.0 0" % (side["template_id"], px, py, pz, s["rotation"]),
                 "forceload remove %d %d %d %d" % (lo_x - 16, lo_z - 16, hi_x + 16, hi_z + 16)]
    FUNCTION.parent.mkdir(parents=True, exist_ok=True)
    FUNCTION.write_text("\n".join(function_limits.ensure_loaded(cmds)) + "\n", encoding="utf-8")
    T.write_json(str(SITES), {"generator": "tools/themed_saplings.py", "provenance": T.provenance(world, Path(a.world)),
                              "ground_from": "heightmap, rounded (tools/ground.py)",
                              "themes": {t: dict(v, prefab=sd[t]["template_id"], height=sd[t]["height"])
                                         for t, v in THEMES.items()},
                              "notes": notes, "saplings": pins, "function": str(FUNCTION.relative_to(ROOT))})
    print(json.dumps({"saplings": len(pins), "by_theme": {t: [s["subregion"] for s in pins if s["theme"] == t]
                                                          for t in THEMES},
                      "heights": {t: sd[t]["height"] for t in sd}, "notes": notes}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
