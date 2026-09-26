#!/usr/bin/env python
"""Themed saplings: world-tree saplings in the countries elders cannot grow in, each the nest of one flying Pokemon.

The owner, 2026-09-26: themed saplings per region (a palm by the sea, one by a lake, "a scorch sapling for fire types in
the south near craters", tundra), so a player sees a tree on the horizon and wants to find what lives in it. The first
pass (20 trees, one bird per theme) was rejected: "pasted in randomly", too close, "not reminiscent of the saplings or
the world tree", the same bird over and over. This is plan v2 of docs/world-building/SAPLING_BIRDS.md:

  shape     every themed sapling IS an elder: tools/tree_grove.py big_tree at the `elder` tier (rounded tapering trunk,
            two storeys of near-level limbs, bare trunk, crown), re-skinned per theme; the silhouette is the family's
  skin      palm (jungle, frond crown), lakeshore (mangrove, weeping crown, prop roots), scorched (basalt, ember seams,
            a smouldering nether-wart crown), frost (spruce, snow on every ledge), storm (oak, a scar, the crown split,
            a lightning rod), crag (spruce, the crown swept downwind in pads), desert (bone, a bare-branch crown)
  setting   young trees of the same kind round it and a dressed ground under it, seated on the heightmap
  birds     one line per tree, from SITES below (the pools are data/spawns.json habitats of the same id)

Siting, one tree per listed sub-region, on the heightmap's ground (tools/ground.py), never a world:
  pad       9x9 around the trunk centre within the theme's relief
  water     palm: the sea 6-32 from the trunk, none on the pad; lakeshore: a painted lake 5-28, none on the pad; the
            rest: no water within 16
  spacing   800 from every other themed sapling, 400 from every elder, 220 from landmark trees and the grove
  clear     120 from a town centre, 100 from every building in data/placements.json, 40 from a leg centreline
  seen      among the passing cells, the one whose crown top is seen from the most routed-leg points within 1,200
            blocks (tools/sightlines.py over the heightmap; the canopy is not counted), then the flattest
Sites are pinned in data/themed_saplings.json; --repick chooses again (a re-pick moves a tree from under its nests).

  python tools/themed_saplings.py [--repick]            prefabs, pins, derived/sites/themed_saplings.json and
                                                        build/themed_saplings/themed_saplings.mcfunction (not run)
  python tools/themed_saplings.py records [--write]     the nest blocks for data/habitat_blocks.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import terrain as T
import structure_nbt as S
import function_limits
from landmark_trees import _ball, _rng, leg_points
from place_town import rotate
from elder_trees import region_mask, seg_distance, footprint, ROTATIONS
from tree_grove import big_tree, TIERS

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "data" / "themed_saplings.json"
PREFABS = ROOT / "kits" / "structures" / "prefabs" / "trees" / "themed"
SITES_OUT = ROOT / "derived" / "sites" / "themed_saplings.json"
FUNCTION = ROOT / "build" / "themed_saplings" / "themed_saplings.mcfunction"
MANIFEST = ROOT / "data" / "habitat_blocks.json"

PAD, GRID = 4, 16
THEMED_SPACING, ELDER_SPACING, LANDMARK_SPACING = 800, 400, 220
GLADE_CLEAR, OFF_TOWN, OFF_BUILT, OFF_LEG = 80, 120, 100, 40
SEEN_WITHIN, OBSERVER_STEP, SHORTLIST = 1200, 96, 30
COMPANIONS, DRESS_R = 5, 20
NEST = {"spawn_range": 16, "chance": 1.0, "trigger": "TICK", "cancel_range": -1, "max_spawns": 8,
        "max_spawns_per_activation": 2}

THEMES = {
    "palm": {"wood": "jungle", "water": ("sea", 6, 32), "relief": 3.0, "inset": 12},
    "lakeshore": {"wood": "mangrove", "water": ("lake", 5, 28), "relief": 3.0, "inset": 16},
    "scorched": {"wood": "dark_oak", "water": ("dry", 16), "relief": 4.0, "inset": 24},
    "frost": {"wood": "spruce", "water": ("dry", 16), "relief": 4.0, "inset": 24},
    "storm": {"wood": "oak", "water": ("dry", 16), "relief": 4.0, "inset": 24},
    "crag": {"wood": "spruce", "water": ("dry", 16), "relief": 5.0, "inset": 24},
    "desert": {"wood": "birch", "water": ("dry", 16), "relief": 3.0, "inset": 24},
}
# (sub-region, theme): the tree's bird line, as SAPLING_BIRDS.md plan v2 gives it
SITES = [("sunset_east", "palm"), ("sunset_west", "palm"), ("east_coast_dunes", "palm"),
         ("arrow_lake_shores", "lakeshore"), ("tilpey_south_shore", "lakeshore"),
         ("great_crater", "scorched"),
         ("frostpeak", "frost"), ("glacier_foot_fields", "frost"),
         ("rift_trunk", "storm"), ("rift_foot", "storm"),
         ("the_crags", "crag"), ("mt_vessu", "crag"),
         ("south_east_dunes", "desert"), ("long_isle_north", "desert")]
# ground dressing: (block, share of columns) tried in order; only natural ground is replaced
DRESS = {"palm": [("minecraft:sand", 0.55)], "lakeshore": [("minecraft:moss_block", 0.35), ("minecraft:mud", 0.15)],
         "scorched": [("minecraft:coarse_dirt", 0.35), ("minecraft:basalt", 0.2), ("minecraft:blackstone", 0.1)],
         "frost": [("minecraft:snow_block", 0.6), ("minecraft:powder_snow", 0.04)],
         "storm": [("minecraft:coarse_dirt", 0.3), ("minecraft:blackstone", 0.06)],
         "crag": [("minecraft:stone", 0.25), ("minecraft:andesite", 0.15), ("minecraft:cobblestone", 0.05)],
         "desert": [("minecraft:coarse_dirt", 0.3), ("minecraft:sand", 0.25)]}
NATURAL = ("#minecraft:dirt", "#minecraft:sand", "minecraft:grass_block", "minecraft:snow_block", "minecraft:gravel")


# ------------------------------------------------------------------ drawing helpers
def _leaf(kind):
    return ("minecraft:%s_leaves" % kind, {"distance": "1", "persistent": "true", "waterlogged": "false"})


def _line(b, a, c, r, block, axial=True, taper=0.45):
    d = math.dist(a, c)
    n = max(2, int(d * 1.6))
    dx, dy, dz = (c[i] - a[i] for i in range(3))
    axis = "y" if abs(dy) >= max(abs(dx), abs(dz)) else ("x" if abs(dx) >= abs(dz) else "z")
    props = {"axis": axis} if axial else None
    for i in range(n + 1):
        t = i / n
        px, py, pz = a[0] + dx * t, a[1] + dy * t, a[2] + dz * t
        rr = max(0.5, r * (1 - taper * t))
        ri = int(math.ceil(rr))
        for ox in range(-ri, ri + 1):
            for oy in range(-ri, ri + 1):
                for oz in range(-ri, ri + 1):
                    if ox * ox + oy * oy + oz * oz <= rr * rr + 0.25:
                        b.set(round(px + ox), round(py + oy), round(pz + oz), block, props)


def _disc(b, cx, y, cz, r, block, props=None):
    ri = int(math.ceil(r))
    for dx in range(-ri - 1, ri + 2):
        for dz in range(-ri - 1, ri + 2):
            if (dx + (cx - round(cx))) ** 2 + (dz + (cz - round(cz))) ** 2 <= r * r + 0.3:
                b.set(round(cx) + dx, y, round(cz) + dz, block, props)


def _swap(b, test, name, keep_props=True, share=1.0, rng=None):
    for k, (n, props) in list(b.blocks.items()):
        if test(n, k) and (share >= 1.0 or rng.random() < share):
            b.blocks[k] = (name, props if keep_props else ())


def _drop(b, test, share=1.0, rng=None):
    for k, (n, _) in list(b.blocks.items()):
        if test(n, k) and (share >= 1.0 or rng.random() < share):
            del b.blocks[k]


def _nest_points(b, wants, prefix):
    """The nearest cell to each wanted point (within 3) of a block starting with `prefix`, with all six faces solid."""
    out = []
    for w in wants:
        best = None
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                for dz in range(-3, 4):
                    p = (round(w[0]) + dx, round(w[1]) + dy, round(w[2]) + dz)
                    name = b.get(*p)
                    if not name or not name.startswith(prefix):
                        continue
                    if not all(b.get(p[0] + ox, p[1] + oy, p[2] + oz) for ox, oy, oz in
                               ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))):
                        continue
                    d = dx * dx + dy * dy + dz * dz
                    if best is None or d < best[0]:
                        best = (d, p)
        if best is not None:
            out.append({"at": list(best[1]), "mimic": b.get(*best[1])})
    return out


# ------------------------------------------------------------------ the saplings: an elder, re-skinned
def elder_shape(wood):
    """tools/tree_grove.py's elder, moved so the trunk centre's base is builder (0, 0, 0)."""
    b0, dims = big_tree(wood, "a", "elder")
    R = TIERS["elder"]["trunk_r"]
    b = S.Builder()
    for (x, y, z), state in b0.blocks.items():
        b.blocks[(x - R, y, z - R)] = state
    return b, dims


def is_log(n, _k=None):
    return n.endswith("_log") or n.endswith("_wood")


def is_leaf(n, _k=None):
    return n.endswith("_leaves")


def skin(theme, rng):
    wood = THEMES[theme]["wood"]
    b, dims = elder_shape(wood)
    cb, top = dims["crown_y"]
    crown_nest = (0, cb + 8, 0)
    trunk_nests = [(0, 11, 0), (0, 34, 0)]
    if theme == "palm":
        _drop(b, is_leaf)
        head = cb + 7
        _ball(b, 0, head, 0, 5.5, 3.5, 5.5, _leaf("jungle"), rng, ragged=0.1)
        for tier, (n, L, rise, droop, y0) in enumerate(((16, 25, 4, 17, head + 1), (11, 17, 3, 11, head + 4))):
            for k in range(n):
                a = 2 * math.pi * k / n + rng.uniform(-0.15, 0.15) + tier * 0.3
                ln, dr = L * rng.uniform(0.85, 1.1), droop * rng.uniform(0.85, 1.15)
                steps = int(ln * 2)
                for s in range(steps + 1):
                    u = s / steps
                    y = y0 + 2 * rise * u - (2 * rise + dr) * u * u
                    x, z = math.cos(a) * u * ln, math.sin(a) * u * ln
                    b.setdefault(round(x), round(y), round(z), *_leaf("jungle"))
                    if u < 0.85:
                        for side in (-1, 1):
                            b.setdefault(round(x - math.sin(a) * side), round(y - 0.4), round(z + math.cos(a) * side),
                                         *_leaf("jungle"))
                    if u > 0.5:
                        b.setdefault(round(x), round(y) - 1, round(z), *_leaf("jungle"))
        for y in (head - 4, head - 5):
            for dx, dz, facing in ((2, 0, "west"), (-2, 0, "east"), (0, 2, "north"), (0, -2, "south")):
                if b.get(dx, y, dz) is None and is_log(b.get(dx // 2, y, dz // 2) or "") and rng.random() < 0.7:
                    b.set(dx, y, dz, "minecraft:cocoa", {"age": "2", "facing": facing})
        crown_nest = (0, head, 0)
        top = head + 8
    elif theme == "lakeshore":
        leaves = [k for k, (n, _) in b.blocks.items() if is_leaf(n)]
        cols = {}
        for x, y, z in leaves:
            if x * x + z * z > 100:
                cols[(x, z)] = min(y, cols.get((x, z), 10 ** 6))
        for (x, z), y in cols.items():                                # the weeping curtain from the crown's underside
            if rng.random() < 0.55:
                for yy in range(y - 1, max(5, y - int(rng.integers(8, 30))), -1):
                    b.setdefault(x, yy, z, *_leaf("mangrove"))
        for k in range(11):                                           # prop roots arching into the bank
            a = 2 * math.pi * k / 11 + rng.uniform(-0.2, 0.2)
            reach = rng.uniform(9, 14)
            for t in np.linspace(0, 1, 18):
                x, z = math.cos(a) * (3 + reach * t), math.sin(a) * (3 + reach * t)
                b.setdefault(round(x), round(9 * math.sin(math.pi * t * 0.9) - 3 * t), round(z),
                             "minecraft:mangrove_roots", {"waterlogged": "false"})
    elif theme == "scorched":
        _swap(b, is_log, "minecraft:polished_basalt")
        _swap(b, is_leaf, "minecraft:nether_wart_block", keep_props=False)
        _drop(b, lambda n, k: n == "minecraft:nether_wart_block" and k[0] ** 2 + k[2] ** 2 > 144, 0.35, rng)
        _swap(b, lambda n, k: n == "minecraft:nether_wart_block", "minecraft:shroomlight", keep_props=False,
              share=0.07, rng=rng)
        for (x, y, z), (n, _) in list(b.blocks.items()):              # ember seams, never under open sky
            if n == "minecraft:polished_basalt" and 2 < y < cb - 4 and x * x + z * z >= 5 \
                    and b.get(x, y + 1, z) == "minecraft:polished_basalt" and rng.random() < 0.08:
                b.set(x, y, z, "minecraft:magma_block")
        for k in range(60):                                           # a charcoal foot
            a, d = rng.uniform(0, 2 * math.pi), rng.uniform(4, 9)
            b.setdefault(round(math.cos(a) * d), 0, round(math.sin(a) * d),
                         "minecraft:coal_block" if rng.random() < 0.3 else "minecraft:blackstone")
    elif theme == "frost":
        for (x, y, z), (n, _) in list(b.blocks.items()):
            if (is_leaf(n) or is_log(n)) and b.get(x, y + 1, z) is None and y > 3 and rng.random() < 0.85:
                b.set(x, y + 1, z, "minecraft:snow", {"layers": str(int(rng.integers(1, 4)))})
        for (x, y, z), (n, _) in list(b.blocks.items()):              # ice hanging under the storeys
            if is_log(n) and b.get(x, y - 1, z) is None and y > 12 and rng.random() < 0.12:
                b.set(x, y - 1, z, "minecraft:packed_ice")
    elif theme == "storm":
        _swap(b, is_leaf, "minecraft:dark_oak_leaves")
        a = rng.uniform(0, 2 * math.pi)
        sa, ca = math.sin(a), math.cos(a)
        _drop(b, lambda n, k: k[1] >= cb - 3 and abs(k[0] * sa - k[2] * ca) < 2.6 and not (k[0] == 0 and k[2] == 0))
        _drop(b, lambda n, k: is_leaf(n) and k[0] ** 2 + k[2] ** 2 > 169, 0.3, rng)
        for y in range(0, cb):                                        # the strike's scar down the trunk
            for w in (-1, 0, 1):
                x, z = round(ca * 3 - sa * w), round(sa * 3 + ca * w)
                if is_log(b.get(x, y, z) or ""):
                    b.set(x, y, z, "minecraft:blackstone" if (y + w) % 3 == 0 else "minecraft:stripped_oak_log",
                          None if (y + w) % 3 == 0 else {"axis": "y"})
        lx, lz = round(-sa * 7), round(ca * 7)                        # the taller leader, clear of its own leaves
        hi = max(y for (x, y, z) in b.blocks)
        _line(b, (0, cb - 2, 0), (lx, hi - 4, lz), 1.3, "minecraft:oak_log")
        for y in range(hi - 4, hi + 3):
            b.set(lx, y, lz, "minecraft:oak_log", {"axis": "y"})
        b.set(lx, hi + 3, lz, "minecraft:lightning_rod", {"facing": "up", "powered": "false", "waterlogged": "false"})
        top = hi + 3
        crown_nest = (lx * 0.5, cb + 6, lz * 0.5)
    elif theme == "crag":
        wind = rng.uniform(0, 2 * math.pi)
        wx, wz = math.cos(wind), math.sin(wind)
        moved = {}
        for (x, y, z), state in b.blocks.items():                     # the crown sheared downwind, in flat pads
            if y >= cb - 6 and (is_leaf(state[0]) or (x * x + z * z > 9)):
                if is_leaf(state[0]) and (y - cb) % 5 in (3, 4):
                    continue
                s = 0.45 * (y - cb + 6)
                moved[(round(x + wx * s), y, round(z + wz * s))] = state
            else:
                moved[(x, y, z)] = state
        b.blocks = moved
        crown_nest = (wx * 0.45 * 14, cb + 8, wz * 0.45 * 14)
    elif theme == "desert":
        _swap(b, is_log, "minecraft:bone_block")
        _drop(b, is_leaf)

        def twig(a, c, r, depth):
            _line(b, a, c, r, "minecraft:bone_block")
            if depth:
                base = math.atan2(c[2] - a[2], c[0] - a[0])
                for j in range(2):
                    a2 = base + rng.uniform(-0.8, 0.8)
                    L = math.dist(a, c) * rng.uniform(0.5, 0.7)
                    twig(c, (c[0] + math.cos(a2) * L, c[1] + L * rng.uniform(0.2, 0.7), c[2] + math.sin(a2) * L),
                         r * 0.6, depth - 1)

        for k in range(8):                                            # the crown's outline in bare branches
            a = 2 * math.pi * k / 10 + rng.uniform(-0.2, 0.2)
            twig((0, cb - 2, 0), (math.cos(a) * 12, cb + rng.uniform(6, 12), math.sin(a) * 12), 0.8, 2)
        for k in range(25):
            a, d = rng.uniform(0, 2 * math.pi), rng.uniform(5, 16)
            b.setdefault(round(math.cos(a) * d), 0, round(math.sin(a) * d), "minecraft:dead_bush")
        top = max(y for (x, y, z) in b.blocks)
        crown_nest = None
    trunk_prefix = "minecraft:" + {"scorched": "polished_basalt", "desert": "bone_block"}.get(theme, wood + "_log")
    nests = _nest_points(b, trunk_nests, trunk_prefix)
    if crown_nest is not None:
        crown_block = {"scorched": "minecraft:nether_wart_block", "storm": "minecraft:dark_oak_leaves"}.get(
            theme, "minecraft:%s_leaves" % wood)
        nests += _nest_points(b, [crown_nest], crown_block)
    if len(nests) < 3:                                                # a crownless tree gets a third trunk nest
        nests += _nest_points(b, [(0, 22, 0)], trunk_prefix)
    return b, nests, int(max(y for (x, y, z) in b.blocks))


def young(theme, rng):
    """A young tree of the kind, 7-16 tall, for the setting round a sapling."""
    b = S.Builder()
    wood = THEMES[theme]["wood"]
    log = "minecraft:%s_log" % wood
    if theme == "palm":
        H, ang, lean = int(rng.integers(12, 17)), rng.uniform(0, 6.3), rng.uniform(2, 4)
        for y in range(-1, H + 1):
            off = lean * (max(y, 0) / H) ** 2
            b.set(round(math.cos(ang) * off), y, round(math.sin(ang) * off), log, {"axis": "y"})
        tx, tz = round(math.cos(ang) * lean), round(math.sin(ang) * lean)
        _ball(b, tx, H + 1, tz, 2.2, 1.6, 2.2, _leaf("jungle"), rng, ragged=0.1)
        for k in range(7):
            a = 2 * math.pi * k / 7 + rng.uniform(-0.2, 0.2)
            for s in range(15):
                u = s / 14
                b.setdefault(round(tx + math.cos(a) * u * 7), round(H + 2 + 3 * u - 8 * u * u),
                             round(tz + math.sin(a) * u * 7), *_leaf("jungle"))
    elif theme == "lakeshore":
        H = int(rng.integers(7, 10))
        for y in range(-1, H):
            b.set(0, y, 0, log, {"axis": "y"})
        _ball(b, 0, H + 1, 0, 5, 2.5, 5, _leaf("mangrove"), rng, ragged=0.2)
        for x in range(-5, 6):
            for z in range(-5, 6):
                if 12 < x * x + z * z <= 25 and rng.random() < 0.5:
                    for y in range(H - 1, max(1, H - int(rng.integers(3, 8))), -1):
                        b.setdefault(x, y, z, *_leaf("mangrove"))
    elif theme in ("scorched", "desert"):
        mat = "minecraft:polished_basalt" if theme == "scorched" else "minecraft:bone_block"
        H = int(rng.integers(7, 12))
        for y in range(-1, H):
            b.set(0, y, 0, mat, {"axis": "y"})
        for k in range(3):
            a = rng.uniform(0, 6.3)
            y0 = rng.uniform(H * 0.4, H - 1)
            _line(b, (0, y0, 0), (math.cos(a) * rng.uniform(3, 5), y0 + rng.uniform(2, 4), math.sin(a) * rng.uniform(3, 5)),
                  0.6, mat)
        if theme == "scorched":
            b.set(0, H, 0, "minecraft:nether_wart_block")
    elif theme == "frost":
        H = int(rng.integers(12, 17))
        for y in range(-1, H - 1):
            b.set(0, y, 0, log, {"axis": "y"})
        for y in range(3, H + 1):
            r = 0.5 + 4 * (H + 1 - y) / (H - 2)
            if (H - y) % 3 == 2:
                r *= 0.5
            for x in range(-5, 6):
                for z in range(-5, 6):
                    if x * x + z * z <= r * r:
                        b.setdefault(x, y, z, *_leaf("spruce"))
        for (x, y, z), (n, _) in list(b.blocks.items()):
            if is_leaf(n) and b.get(x, y + 1, z) is None and rng.random() < 0.8:
                b.set(x, y + 1, z, "minecraft:snow", {"layers": "1"})
    elif theme == "storm":
        H = int(rng.integers(8, 12))
        for y in range(-1, H):
            b.set(0, y, 0, "minecraft:stripped_oak_log" if y % 3 == 0 else log, {"axis": "y"})
        _ball(b, 0, H + 1, 0, 4, 2.5, 4, _leaf("dark_oak"), rng, ragged=0.4)
    elif theme == "crag":
        H, wind = int(rng.integers(8, 12)), rng.uniform(0, 6.3)
        for y in range(-1, H):
            off = 2.5 * (max(y, 0) / H) ** 2
            b.set(round(math.cos(wind) * off), y, round(math.sin(wind) * off), log, {"axis": "y"})
        for py, rad in ((H - 3, 4), (H + 1, 3)):
            _ball(b, math.cos(wind) * 3, py, math.sin(wind) * 3, rad, 1.2, rad * 0.8, _leaf("spruce"), rng, ragged=0.25)
    return b


def write_prefab(name, b, extra):
    PREFABS.mkdir(parents=True, exist_ok=True)
    data, shift = b.to_bytes()
    (PREFABS / (name + ".nbt")).write_bytes(data)
    lo, hi = b.bounds()
    side = dict({"schema": "cobblers.prefab/1", "template_id": "cobblers:kits/trees/themed/%s" % name, "kind": "trees",
                 "set": "themed", "name": name, "author": "tools/themed_saplings.py",
                 "source": {"file": "generated", "size": (hi - lo + 1).tolist(), "blocks": len(b.blocks)},
                 "entrance": None, "grade_layer": None, "trunk_origin": [int(v) for v in shift],
                 "notes": "the trunk centre's base is builder (0, 0, 0), template trunk_origin; nest `at` is in builder "
                          "coordinates (add trunk_origin for template coordinates)"}, **extra)
    (PREFABS / (name + ".json")).write_text(json.dumps(side, indent=1) + "\n", encoding="utf-8")
    return side


def build_prefabs():
    for old in PREFABS.glob("*"):                                     # retired first-pass prefabs go with them
        old.unlink()
    sides = {}
    for t in THEMES:
        b, nests, height = skin(t, _rng("themed_sapling_v2_%s" % t))
        sides[t] = write_prefab("sapling_%s" % t, b, {"tier": "themed_sapling", "theme": t, "height": height,
                                                      "nests": nests})
        for v in "ab":
            sides["%s_young_%s" % (t, v)] = write_prefab("young_%s_%s" % (t, v), young(t, _rng("young_%s_%s" % (t, v))),
                                                         {"tier": "themed_young", "theme": t})
    return sides


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


def pick_sites(heights, world, ground_of, height_of):
    import sightlines as SL
    subs = {s["id"]: s for s in json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["subregions"]}
    foliage = json.loads((ROOT / "data" / "foliage.json").read_text(encoding="utf-8"))
    towns = [(t["centre"]["x"], t["centre"]["z"]) for t in
             json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
             if (t.get("centre") or {}).get("x") is not None]
    built = [(p["position"]["x"], p["position"]["z"]) for p in
             json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
             if isinstance(p.get("position"), dict) and p["position"].get("x") is not None]
    glades = [(t["site"][0], t["site"][1], t["glade_radius"]) for t in foliage["landmark_trees"]]
    elders = json.loads((ROOT / "derived" / "sites" / "elder_trees.json").read_text(encoding="utf-8"))
    elder_pts = [(s["x"], s["z"]) for r in elders["regions"] for s in r["sites"]]
    grove = ROOT / "derived" / "sites" / "tree_grove_foothill_woods.json"
    landmark_pts = [(g[0], g[1]) for g in glades]
    if grove.is_file():
        elder_pts += [(e["x"], e["z"]) for e in json.loads(grove.read_text(encoding="utf-8")).get("elders") or []]
    legs_doc = json.loads((ROOT / "derived" / "routes" / "critical_legs.json").read_text(encoding="utf-8"))
    legs = legs_doc["legs"]
    observers = np.asarray(leg_points(legs_doc, {"%s->%s" % (l["from"], l["to"]) for l in legs}, OBSERVER_STEP))
    pts = np.concatenate([np.asarray(l["polyline"], float) for l in legs])
    breaks = np.cumsum([len(l["polyline"]) for l in legs])[:-1]
    keep = np.ones(len(pts) - 1, bool)
    keep[breaks - 1] = False
    a, bb = pts[:-1][keep], pts[1:][keep]
    segs = (a, bb - a, np.maximum(((bb - a) ** 2).sum(1), 1e-9))
    sea, lake = water_masks(heights, world)
    n = heights.shape[0]
    out, notes, themed_pts = [], [], []
    for sid, theme in SITES:
        spec = THEMES[theme]
        kind = spec["water"][0]
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
                    win = (s_m if kind == "sea" else l_m)[lz - hi:lz + hi + 1, lx - hi:lx + hi + 1]
                    ys, xs = np.nonzero(win)
                    if not len(xs) or float(np.hypot(xs - hi, ys - hi).min()) < lo:
                        continue
                near = lambda P, d: any(abs(px - x) < d and abs(pz - z) < d and math.hypot(px - x, pz - z) < d
                                        for px, pz in P)
                if near(towns, OFF_TOWN) or near(built, OFF_BUILT) or near(themed_pts, THEMED_SPACING) \
                        or near(elder_pts, ELDER_SPACING) or near(landmark_pts, LANDMARK_SPACING):
                    continue
                if any(math.hypot(gx - x, gz - z) < gr + GLADE_CLEAR for gx, gz, gr in glades):
                    continue
                dleg = seg_distance(x, z, *segs)
                if dleg < OFF_LEG:
                    continue
                cands.append((x, z, relief, int(g[lz, lx]), dleg))
        if not cands:
            notes.append("%s (%s): no site passes the rules" % (sid, theme))
            continue
        # the shortlist nearest a road, then the one seen from the most leg points within SEEN_WITHIN
        short = sorted(cands, key=lambda c: (round(c[2]), c[4]))[:SHORTLIST]
        scored = []
        for x, z, relief, gy, dleg in short:
            d = np.hypot(observers[:, 0] - x, observers[:, 1] - z)
            obs = observers[(d < SEEN_WITHIN) & (d > 24)]
            seen = 0
            for ox, oz in obs:
                r = SL.cast(heights, (float(ox), float(oz)), 1.6, {"x": x, "z": z}, 1 + height_of[theme] - 3,
                            step=2.0, margin=3.0, surface=heights)
                seen += bool(r["visible"])
            scored.append((seen, -relief, -dleg, x, z, gy, dleg, len(obs)))
        seen, _, _, x, z, gy, dleg, nobs = max(scored)
        if seen == 0:
            notes.append("%s (%s): no passing site is seen from a leg within %d; the nearest-road site is used"
                         % (sid, theme, SEEN_WITHIN))
        rng = _rng("themed_sapling_v2_site_%s" % sid)
        out.append({"id": "sapling_%s_%s" % (theme, sid), "theme": theme, "subregion": sid, "x": x, "z": z,
                    "ground_y": gy, "rotation": ROTATIONS[int(rng.integers(4))], "distance_to_nearest_leg": round(dleg),
                    "seen_from_leg_points": seen, "leg_points_within": nobs})
        themed_pts.append((x, z))
    return out, notes


# ------------------------------------------------------------------ placement
def place(site, side, x=None, z=None, ground_y=None, rotation=None):
    """(template pos, rotated footprint): the trunk centre's base lands on (x, ground + 1, z)."""
    x = site["x"] if x is None else x
    z = site["z"] if z is None else z
    gy = site["ground_y"] if ground_y is None else ground_y
    rot = site["rotation"] if rotation is None else rotation
    ox, oy, oz = side["trunk_origin"]
    qx, qz = rotate(ox, oz, rot)
    px, pz = x - qx, z - qz
    sx, _, sz = side["source"]["size"]
    return (px, gy + 1 - oy, pz), footprint(px, pz, sx, sz, rot)


def nest_world(site, side, nest):
    ox, oy, oz = side["trunk_origin"]
    (px, py, pz), _ = place(site, side)
    tx, ty, tz = nest["at"][0] + ox, nest["at"][1] + oy, nest["at"][2] + oz
    rx, rz = rotate(tx, tz, site["rotation"])
    return {"x": px + rx, "y": py + ty, "z": pz + rz}


def setting(site, sd, ground_of):
    """Commands for the setting round one sapling: young trees and dressed ground, each seated on the heightmap."""
    rng = _rng("themed_setting_%s" % site["id"])
    cmds = []
    t = site["theme"]
    for k in range(COMPANIONS):
        a = 2 * math.pi * k / COMPANIONS + rng.uniform(-0.35, 0.35)
        d = rng.uniform(24, 36)
        x, z = round(site["x"] + math.cos(a) * d), round(site["z"] + math.sin(a) * d)
        side = sd["%s_young_%s" % (t, "ab"[k % 2])]
        rot = ROTATIONS[int(rng.integers(4))]
        (px, py, pz), _ = place(site, side, x, z, ground_of(x, z), rot)
        cmds.append("place template %s %d %d %d %s none 1.0 0" % (side["template_id"], px, py, pz, rot))
    for dx in range(-DRESS_R, DRESS_R + 1):
        for dz in range(-DRESS_R, DRESS_R + 1):
            d = math.hypot(dx, dz)
            if d > DRESS_R or rng.random() < (d / DRESS_R) ** 2:          # thinning towards the edge
                continue
            roll, acc = rng.random(), 0.0
            for block, share in DRESS[t]:
                acc += share
                if roll < acc:
                    x, z = site["x"] + dx, site["z"] + dz
                    y = ground_of(x, z)
                    cmds += ["fill %d %d %d %d %d %d %s replace %s" % (x, y, z, x, y, z, block, nat) for nat in NATURAL]
                    break
    return cmds


def load_pins():
    return json.loads(PINS.read_text(encoding="utf-8"))["saplings"] if PINS.is_file() else None


def sides():
    out = {}
    for t in THEMES:
        out[t] = json.loads((PREFABS / ("sapling_%s.json" % t)).read_text(encoding="utf-8"))
        for v in "ab":
            out["%s_young_%s" % (t, v)] = json.loads((PREFABS / ("young_%s_%s.json" % (t, v))).read_text(encoding="utf-8"))
    return out


def records(pins, sd):
    out = []
    for s in pins:
        side = sd[s["theme"]]
        for i, nest in enumerate(side["nests"]):
            label = ("low", "mid", "top", "extra")[min(i, 3)]
            where = "crown" if not nest["mimic"].endswith(("_log", "basalt", "bone_block")) else "trunk"
            out.append({"id": "%s_%s" % (s["id"], label),
                        "place": "the %s sapling %s: inside its %s" % (s["theme"], s["id"], where),
                        "pool": "cobblers:%s" % s["id"], "style": "activated", "replace_spawns": False,
                        "position": nest_world(s, side, nest), "mimic": nest["mimic"], "activated": dict(NEST),
                        "status": "planned",
                        "why": "A nest in a themed sapling (tools/themed_saplings.py; SAPLING_BIRDS.md plan v2). The "
                               "point is a cell of the tree's own %s, solid on all six faces in the prefab %s, so the "
                               "block is hidden. Up to 8 of the tree's bird alive within 16 blocks of it, as in the "
                               "elders' nests." % (where, side["template_id"])})
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("cmd", nargs="?", default="build", choices=["build", "records"])
    p.add_argument("--repick", action="store_true")
    p.add_argument("--write", action="store_true", help="records: merge the nest blocks into data/habitat_blocks.json")
    a = p.parse_args(argv)
    if a.cmd == "records":
        recs = records(load_pins(), sides())
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
        pins, notes = pick_sites(heights, world, ground_of, {t: sd[t]["height"] for t in THEMES})
        PINS.write_text(json.dumps({
            "schema": "cobblers.themed-saplings/2",
            "note": "Pinned sites of the themed saplings, plan v2 of docs/world-building/SAPLING_BIRDS.md "
                    "(tools/themed_saplings.py picked them; placed from here after that, so a tree never moves out from "
                    "under its nest blocks). ground_y is tools/ground.py's.",
            "saplings": pins}, indent=2) + "\n", encoding="utf-8")
    cmds = ["# themed saplings: %d trees and their settings (tools/themed_saplings.py)" % len(pins)]
    for s in pins:
        side = sd[s["theme"]]
        (px, py, pz), (lo_x, lo_z, hi_x, hi_z) = place(s, side)
        box = "%d %d %d %d" % (min(lo_x, s["x"] - 40) - 16, min(lo_z, s["z"] - 40) - 16,
                               max(hi_x, s["x"] + 40) + 16, max(hi_z, s["z"] + 40) + 16)
        cmds += ["# %s" % s["id"], "forceload add " + box] + setting(s, sd, ground_of) + \
                ["place template %s %d %d %d %s none 1.0 0" % (side["template_id"], px, py, pz, s["rotation"]),
                 "forceload remove " + box]
    FUNCTION.parent.mkdir(parents=True, exist_ok=True)
    FUNCTION.write_text("\n".join(function_limits.ensure_loaded(cmds)) + "\n", encoding="utf-8")
    T.write_json(str(SITES_OUT), {"generator": "tools/themed_saplings.py", "provenance": T.provenance(world, Path(a.world)),
                                  "ground_from": "heightmap, rounded (tools/ground.py)",
                                  "themes": {t: dict(v, prefab=sd[t]["template_id"], height=sd[t]["height"],
                                                     nests=len(sd[t]["nests"])) for t, v in THEMES.items()},
                                  "notes": notes, "saplings": pins, "function": str(FUNCTION.relative_to(ROOT))})
    print(json.dumps({"saplings": len(pins), "sites": {s["id"]: [s["x"], s["z"], s["seen_from_leg_points"] if
                                                               "seen_from_leg_points" in s else None] for s in pins},
                      "heights": {t: sd[t]["height"] for t in THEMES},
                      "nests": {t: len(sd[t]["nests"]) for t in THEMES}, "notes": notes}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
