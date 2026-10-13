#!/usr/bin/env python
"""The Scar Tarn: a pond in the hollow on Mt Vessu's north-north-west shoulder, grown over with spruce and birch, and
held by alpha Pokemon, from data/scar_tarn.json.

The owner, 2026-10-11: "I like the Scar thematically, but I think we need something or an environment inhabiting the
area now. It feels weird to see the big mountain completely empty. I thought the north-west side of the mountain has a
cool recessed point, where some water could make for a pond, and we can plop some trees and alpha mons down to have
taken over the afflicted area of the Scar or something." Rungs, in CLAUDE.md principle 6's order:

  the hollow    FOUND, not dug: a priority-flood fill of the canonical heightmap over Mt Vessu (tools/ground.py, rounded)
                finds a closed bowl at x1965..2071 z686..744 whose lowest rim is y239. The pond is the connected set of
                columns under the record's water_level that the flood reaches from the seed, so its shape is the
                terrain's own. The generator REFUSES a water level that escapes the window, or whose natural spill (the
                level two blocks higher) escapes it, and lifts every rim column under bank_lift_to so a world one block
                under the heightmap still holds the water (tools/ground.py: 'one block low at water edges').
  the growth    a block pass of vanilla blocks (functions, rung 5): spruce and birch, dead snags, fallen logs, mossy
                boulders, moss and podzol with ferns, and a few brick stubs in the Scar's own palette. Every Y is
                round(ground) from tools/ground.py. Nothing is read from a world. NOT data/foliage.json: that feeds the
                WorldPainter export and the world is already exported.
  the alphas    NOT in this pack: four ACTIVATED Habitat Blocks (records this tool writes into data/habitat_blocks.json
                and data/spawns.json, `records --write`), placed by tools/habitat_blocks.py at R9E with the others. The
                alpha is the pool entry's `modifiers` ("alpha=true"), a PokemonProperties the Cobblemon 1.8.0 jar copies
                into the spawn (HabitatSpawn.createSpawnDetail; tools/compile_spawns.py compile_habitat writes it). This
                pack runs BEFORE R9E (step R9ST) because the four blocks stand in cells it writes.

  the arms      2026-10-12, the owner: "The forest should expand toward the Scar, maybe envelop some of it, and then down the
                back and side of the mountain." Layer 2 (data/scar_tarn.json growth.arms), written AFTER the tarn's own wood
                (layer 1, unchanged: its function is byte for byte what it was) and after the wards, one function each
                (arm_<lobe>.mcfunction, held in its own forceload by step R9ST). A lobe is a spine of (x, z, radius) knots read
                off the heightmap; the tree probability falls from `max_probability` at the spine to 0 at the radius. Every
                tree is checked against a keep-clear net (the authored 24 round every x/z, line and box another record
                authors, the avoid boxes round Thundurus's plug, the city's core hull, everything outside the Mt Vessu
                outline) dilated by its canopy, and against slope (3x3 relief <= growth.arms.max_relief_3x3), so the wood
                thins out at the cliffs and the city and does not cross them.

OUR LIST IS NOT THE WORLD. The clearance sweep covers every x/z any data/*.json authors (tools/southern_residents.py
authored_points), not what a donor template, a mod or a player put there. The Scar's own ruins are covered for the arms by the
city's own geometry (placements.json streets and house lots, ruins.json footprints), which is what data/ says stands there,
not what is in the world.

  python tools/scar_tarn.py build   [--out DIR]        write build/datapacks/cobblers_scar_tarn
  python tools/scar_tarn.py report                      numbers, containment, counts; nothing written
  python tools/scar_tarn.py records [--write]           the Habitat Block and pool records
  python tools/scar_tarn.py probes  [--write]           presence probes into data/world_probes.json

The re-application (tools/reapply.py): placement_steps() is R9ST, BEFORE R9E.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "scar_tarn.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_scar_tarn"
HABITATS = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
PROBES = ROOT / "data" / "world_probes.json"
SCHEMA = "cobblers.scar-tarn/1"
NS, FN = "cobblers", "scar_tarn"
PACK_FORMAT = 48  # Minecraft 1.21.1
WAIT_SECONDS = 3
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()

AIR, WATER = "minecraft:air", "minecraft:water"
NOT_SOLID = {AIR, WATER, "minecraft:fern", "minecraft:large_fern", "minecraft:short_grass", "minecraft:azalea",
             "minecraft:moss_carpet", "minecraft:spruce_leaves", "minecraft:birch_leaves"}
SPRUCE_SEQ = [0, 1, 1, 2, 1, 2, 3, 2, 3, 4, 3, 4, 5, 4, 5, 6, 5, 6]
D8 = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
D4 = D8[:4]


class TarnError(SystemExit):
    pass


def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise TarnError("%s: schema must be %s" % (path, SCHEMA))
    P = doc["pond"]
    if P["bank_lift_to"] < P["water_level"] + 1:
        raise TarnError("the bank must stand at least one block over the water")
    if doc["alphas"]["band"][0] > doc["alphas"]["band"][1]:
        raise TarnError("alphas.band is [low, high]")
    return doc


def base(state):
    return state.split("[")[0].split("{")[0]


def h32(*parts):
    return int.from_bytes(hashlib.sha256("/".join(str(p) for p in parts).encode()).digest()[:4], "big")


def frac(*parts):
    return h32(*parts) / 4294967296.0


def pick(table, *parts):
    """A key of {key: weight}, by the seeded fraction."""
    total = float(sum(table.values()))
    t = frac(*parts) * total
    acc = 0.0
    for k in sorted(table):
        acc += table[k]
        if t < acc:
            return k
    return sorted(table)[-1]


def rsq(r):
    """The cells of a rounded square of radius r: a diamond-cut square that is a plus at 1 and a cone's disc above."""
    lim = int(r * 1.5)
    return [(dx, dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1) if abs(dx) + abs(dz) <= max(lim, r)]


# ------------------------------------------------------------------------------------------------------------- plan
class Plan:
    """Every block the pack writes, in phases, plus the world as the pack leaves it (`final`): the ground column is solid
    up to round(ground) and air above; a `replace` write sets a cell, a `keep` write sets it only if it is still air."""

    PHASES = ("bank", "bed", "water", "paint", "clear", "structures", "leaves", "plants", "wards")

    def __init__(self, doc, g):
        self.doc, self.g = doc, g
        self.X0, self.Z0, self.X1, self.Z1 = doc["pond"]["window"]        # the POND's window (layer 1, and the water's flood)
        arms = doc["growth"].get("arms")
        ux0, uz0, ux1, uz1 = arms["window"] if arms else (self.X0, self.Z0, self.X1, self.Z1)
        self.UX0, self.UZ0, self.UX1, self.UZ1 = min(self.X0, ux0), min(self.Z0, uz0), max(self.X1, ux1), max(self.Z1, uz1)
        self.A = g.box(self.UX0, self.UZ0, self.UX1, self.UZ1)             # ground over the union of the pond's and the arms' windows
        self.lim = (self.X0, self.Z0, self.X1, self.Z1)  # the box a write may land in: the pond's window for layer 1, the union for the arms
        self.mask_org = (self.X0, self.Z0)
        self.units = {"build": {p: [] for p in self.PHASES}}   # function -> phase -> [(x, y, z, state, mode)]
        self.unit_cols = {"build": set()}
        self.unit = "build"
        self.ops = self.units["build"]
        self.arm_trees = []                            # layer 2: {"kind", "x", "z", "y0", "h", "lobe"}
        self.arm_lobe_counts = {}
        self.l1_paint = set()                          # columns layer 1 painted
        self.arm_paint = set()                         # columns an arm painted (layer 1's probe rows are drawn from the rest)
        self.final = {}
        self.cols = set()                              # every column a write lands in
        self.solid_cols = set()                        # columns a trunk, boulder, log or brick stands in
        self.W = set()
        self.ring8 = set()
        self.ring4 = set()
        self.trees = []
        self.stubs = []
        self.wards = {}
        self.plants = []
        self.counts = {}
        self.seed = doc["growth"]["seed"]

    def gr(self, x, z):
        return int(self.A[z - self.UZ0, x - self.UX0])

    def inside(self, x, z):
        x0, z0, x1, z1 = self.lim
        return x0 <= x <= x1 and z0 <= z <= z1

    def inside_pond(self, x, z):
        return self.X0 <= x <= self.X1 and self.Z0 <= z <= self.Z1

    def begin(self, unit):
        """Start writing into function `unit` (layer 2: one function per arm)."""
        self.units.setdefault(unit, {p: [] for p in self.PHASES})
        self.unit_cols.setdefault(unit, set())
        self.unit, self.ops = unit, self.units[unit]

    def put(self, phase, x, y, z, state, mode="replace"):
        if not self.inside(x, z) or self.blocked(x, z):
            return                                     # inside an authored point's clearance: nothing is written
        self.ops[phase].append((x, y, z, state, mode))
        self.cols.add((x, z))
        self.unit_cols[self.unit].add((x, z))
        if mode == "keep":
            cur = self.final.get((x, y, z))
            if cur is not None or y <= self.gr(x, z):
                return
            self.final[(x, y, z)] = state
        elif mode == "snow":
            return
        else:
            self.final[(x, y, z)] = state

    def count(self, k, n=1):
        self.counts[k] = self.counts.get(k, 0) + n

    def keepout(self):
        """A (z, x) boolean array over the window: True within rules.authored_clearance of an x/z another data file authors.
        The growth never writes there, so the sweep in check_plan has nothing to find (and still runs on the result)."""
        import southern_residents as SR
        m = self.doc["rules"]["authored_clearance"]
        pts = [(x, z) for x, z, f in SR.authored_points({"residents": []}, own_file=DATA)
               if self.X0 - m <= x <= self.X1 + m and self.Z0 - m <= z <= self.Z1 + m
               and f != "habitat_blocks.json"]
        zz, xx = np.mgrid[self.Z0:self.Z1 + 1, self.X0:self.X1 + 1]
        mask = np.zeros(zz.shape, bool)
        for (px, pz) in pts:
            mask |= np.hypot(xx - px, zz - pz) < m + 1.5
        return mask

    def blocked(self, x, z):
        ox, oz = self.mask_org
        return bool(self.mask[z - oz, x - ox])


def flood(plan, seed, level, limit=None):
    """(cells, escaped): the 4-connected columns reachable from seed whose ground is at most level - 1 (so a water block at
    y=level stands over each), inside the window; escaped when the fill reaches the window's edge."""
    sx, sz = seed
    if plan.gr(sx, sz) > level - 1:
        return set(), False
    seen = {(sx, sz)}
    st = [(sx, sz)]
    escaped = False
    while st:
        x, z = st.pop()
        for dx, dz in D4:
            n = (x + dx, z + dz)
            if n in seen:
                continue
            if not plan.inside_pond(*n):
                escaped = True
                continue
            if plan.gr(*n) <= level - 1:
                seen.add(n)
                st.append(n)
    return seen, escaped


def build_pond(plan):
    doc = plan.doc
    P = doc["pond"]
    yS = P["water_level"]
    seed = tuple(P["seed"])
    W, escaped = flood(plan, seed, yS)
    if not W:
        raise TarnError("the seed %s is not under the water level y%d (ground y%d)" % (seed, yS, plan.gr(*seed)))
    if escaped:
        raise TarnError("water at y%d from %s reaches the window's edge: it would spill" % (yS, seed))
    spill, spilled = flood(plan, seed, yS + 2)
    if spilled:
        raise TarnError("the hollow's own spill is under y%d: a water level of y%d has less than two blocks of natural "
                        "freeboard" % (yS + 2, yS))
    plan.W = W
    ring8 = set()
    ring4 = set()
    for (x, z) in W:
        for dx, dz in D8:
            n = (x + dx, z + dz)
            if n in W:
                continue
            ring8.add(n)
            if (dx == 0 or dz == 0):
                ring4.add(n)
    plan.ring8, plan.ring4 = ring8, ring4
    natural = min(plan.gr(*c) for c in ring4)
    if natural < yS:
        raise TarnError("a rim column stands at y%d, under the water level y%d" % (natural, yS))
    lift, depth = P["bank_lift_to"], P["lining_depth"]
    seed_h = doc["growth"]["seed"]
    # the bank: every rim column to the lift, dirt under a shore block
    lifted = 0
    for (x, z) in sorted(ring8):
        g = plan.gr(x, z)
        top = pick(P["bank"], seed_h, "bank", x // 2, z // 2)
        if g < lift:
            for y in range(g - depth + 1, lift):
                plan.put("bank", x, y, z, "minecraft:dirt")
            plan.put("bank", x, lift, z, "minecraft:" + top)
            lifted += 1
        else:
            plan.put("bank", x, g, z, "minecraft:" + top)
    plan.count("bank_lifted", lifted)
    plan.count("bank_columns", len(ring8))
    # the bed and the water
    for (x, z) in sorted(W):
        g = plan.gr(x, z)
        plan.put("bed", x, g, z, "minecraft:" + pick(P["bed"], seed_h, "bed", x // 2, z // 2))
        for k in range(1, depth):
            plan.put("bed", x, g - k, z, "minecraft:mud" if k == 1 else "minecraft:clay")
        for y in range(g + 1, yS + 1):
            plan.put("water", x, y, z, WATER)
    plan.count("water_columns", len(W))
    plan.count("water_blocks", sum(yS - plan.gr(x, z) for (x, z) in W))
    return {"seed": seed, "level": yS, "columns": len(W), "natural_rim_min": natural,
            "max_depth": max(yS - plan.gr(x, z) for (x, z) in W)}


def water_distance(plan, pts):
    """{point: distance to the nearest water column} for points (x, z), in chunks."""
    Wa = np.array(sorted(plan.W), float)
    out = {}
    P = list(pts)
    for i in range(0, len(P), 512):
        blk = np.array(P[i:i + 512], float)
        d = np.hypot(blk[:, None, 0] - Wa[None, :, 0], blk[:, None, 1] - Wa[None, :, 1]).min(axis=1)
        for p, v in zip(P[i:i + 512], d):
            out[p] = float(v)
    return out


def relief3(plan, x, z):
    vals = [plan.gr(x + a, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if plan.inside(x + a, z + b)]
    return max(vals) - min(vals)


def leaf_layer(plan, y, x, z, r, state):
    for dx, dz in rsq(r):
        plan.put("leaves", x + dx, y, z + dz, state, "keep")


def place_tree(plan, kind, x, z, h):
    g = plan.gr(x, z)
    if kind in ("spruce", "elder"):
        log, lv = "minecraft:spruce_log[axis=y]", "minecraft:spruce_leaves[persistent=true]"
        for y in range(g + 1, g + h + 1):
            plan.put("structures", x, y, z, log)
        top = g + h + 1
        rmax = 2 + h // 6
        i = 0
        y = top
        while y >= g + 3:
            leaf_layer(plan, y, x, z, min(rmax, SPRUCE_SEQ[min(i, len(SPRUCE_SEQ) - 1)]), lv)
            y -= 1
            i += 1
    elif kind == "birch":
        log, lv = "minecraft:birch_log[axis=y]", "minecraft:birch_leaves[persistent=true]"
        for y in range(g + 1, g + h + 1):
            plan.put("structures", x, y, z, log)
        top = g + h
        for y, r in ((top - 3, 1), (top - 2, 2), (top - 1, 2), (top, 1), (top + 1, 1)):
            leaf_layer(plan, y, x, z, r, lv)
    else:  # snag: a dead spruce
        for y in range(g + 1, g + h + 1):
            plan.put("structures", x, y, z, "minecraft:spruce_log[axis=y]")
        for k, dy in enumerate((2, 4)):
            ax = "x" if h32(plan.seed, "sx", x, z, k) % 2 else "z"
            sgn = 1 if h32(plan.seed, "ss", x, z, k) % 2 else -1
            sx_, sz_ = (x + sgn, z) if ax == "x" else (x, z + sgn)
            plan.put("structures", sx_, g + h - dy, sz_, "minecraft:spruce_log[axis=%s]" % ax, "keep")
    plan.solid_cols.add((x, z))
    if plan.unit == "build":
        plan.trees.append({"kind": kind, "x": x, "z": z, "y0": g + 1, "h": h})
        plan.count("tree_" + kind)
    else:
        plan.arm_trees.append({"kind": kind, "x": x, "z": z, "y0": g + 1, "h": h, "unit": plan.unit})
        plan.count("arm_tree_" + kind)


def build_growth(plan):
    doc = plan.doc
    G = doc["growth"]
    P = doc["pond"]
    yS = P["water_level"]
    seed = plan.seed
    R, cell = G["radius"], G["cell"]
    xs = [c[0] for c in plan.W]
    zs = [c[1] for c in plan.W]
    gx0, gx1, gz0, gz1 = min(xs) - R, max(xs) + R, min(zs) - R, max(zs) + R
    gx0, gz0 = max(gx0, plan.X0 + 2), max(gz0, plan.Z0 + 2)
    gx1, gz1 = min(gx1, plan.X1 - 2), min(gz1, plan.Z1 - 2)
    cands = []
    for cx in range(gx0, gx1, cell):
        for cz in range(gz0, gz1, cell):
            x = cx + h32(seed, "jx", cx, cz) % cell
            z = cz + h32(seed, "jz", cx, cz) % cell
            if not plan.inside(x, z) or plan.blocked(x, z) or (x, z) in plan.W or (x, z) in plan.ring8:
                continue
            cands.append((x, z))
    dist = water_distance(plan, cands)
    # trees
    for (x, z) in cands:
        d = dist[(x, z)]
        g = plan.gr(x, z)
        if d > R or d <= G["trunk_clear"] or g < yS + 2 or relief3(plan, x, z) > G["max_relief_3x3"]:
            continue
        p = G["max_probability"] * (1.0 - d / R) ** G["falloff"]
        if frac(seed, "tp", x, z) >= p:
            continue
        t = frac(seed, "tk", x, z)
        if t < G["snag_share"]:
            kind, h = "snag", G["snag_height"][0] + h32(seed, "th", x, z) % (G["snag_height"][1] - G["snag_height"][0] + 1)
        elif t < G["snag_share"] + G["elder_share"] and d > 6:
            kind, h = "elder", G["elder_height"][0] + h32(seed, "th", x, z) % (G["elder_height"][1] - G["elder_height"][0] + 1)
        elif d <= G["birch_within"] and frac(seed, "tb", x, z) < G["birch_share"]:
            kind, h = "birch", G["birch_height"][0] + h32(seed, "th", x, z) % (G["birch_height"][1] - G["birch_height"][0] + 1)
        else:
            kind, h = "spruce", G["spruce_height"][0] + h32(seed, "th", x, z) % (G["spruce_height"][1] - G["spruce_height"][0] + 1)
        place_tree(plan, kind, x, z, h)
    # brick stubs: the Scar's own palette
    near = [c for c in cands if G["ruin_distance"][0] <= dist[c] <= G["ruin_distance"][1] and c not in plan.solid_cols]
    near.sort(key=lambda c: h32(seed, "rs", c[0], c[1]))
    for (x, z) in near:
        if len(plan.stubs) >= G["ruin_stubs"]:
            break
        if any(math.hypot(x - s["x"], z - s["z"]) < 24 for s in plan.stubs):
            continue
        ax = "x" if h32(seed, "ra", x, z) % 2 else "z"
        length = 5 + h32(seed, "rl", x, z) % 5
        line = [(x + i, z) if ax == "x" else (x, z + i) for i in range(length)]
        if not all(plan.inside(*c) and not plan.blocked(*c) and c not in plan.W and c not in plan.ring8
                   and plan.gr(*c) >= yS + 2 for c in line):
            continue
        gs = [plan.gr(*c) for c in line]
        if max(gs) - min(gs) > 2:
            continue
        for i, (cx_, cz_) in enumerate(line):
            if (cx_, cz_) in plan.solid_cols:
                continue
            gg = plan.gr(cx_, cz_)
            top = 1 + h32(seed, "rt", cx_, cz_) % 3
            for y in range(gg + 1, gg + top + 1):
                blk = "minecraft:mossy_stone_bricks" if h32(seed, "rb", cx_, y, cz_) % 100 < 55 else "minecraft:cracked_stone_bricks"
                plan.put("structures", cx_, y, cz_, blk)
            if top >= 2 and h32(seed, "rc", cx_, cz_) % 4 == 0:
                plan.put("structures", cx_, gg + top + 1, cz_, "minecraft:mossy_stone_brick_slab[type=bottom,waterlogged=false]")
            plan.solid_cols.add((cx_, cz_))
        plan.stubs.append({"x": x, "z": z, "axis": ax, "length": length})
        plan.count("brick_stub")
    # boulders
    free = [c for c in cands if c not in plan.solid_cols and dist[c] > 4 and plan.gr(*c) >= yS + 2]
    free.sort(key=lambda c: h32(seed, "bo", c[0], c[1]))
    made = 0
    for (x, z) in free:
        if made >= G["boulders"]:
            break
        rr = 1 + h32(seed, "br", x, z) % 2
        cols = [(x + a, z + b, rr - int(math.hypot(a, b) + 0.5)) for a in range(-rr, rr + 1) for b in range(-rr, rr + 1)]
        cols = [(cx_, cz_, hh) for cx_, cz_, hh in cols if hh >= 1 and plan.inside(cx_, cz_) and not plan.blocked(cx_, cz_)
                and (cx_, cz_) not in plan.solid_cols
                and (cx_, cz_) not in plan.ring8 and (cx_, cz_) not in plan.W]
        if not cols:
            continue
        for cx_, cz_, hh in cols:
            gg = plan.gr(cx_, cz_)
            for y in range(gg + 1, gg + hh + 1):
                plan.put("structures", cx_, y, cz_, "minecraft:mossy_cobblestone" if h32(seed, "bm", cx_, y, cz_) % 3 else "minecraft:cobblestone")
            plan.solid_cols.add((cx_, cz_))
        made += 1
    plan.count("boulder", made)
    # fallen logs
    made = 0
    for (x, z) in sorted(free, key=lambda c: h32(seed, "fl", c[0], c[1])):
        if made >= G["fallen_logs"]:
            break
        ax = "x" if h32(seed, "fa", x, z) % 2 else "z"
        length = 5 + h32(seed, "fn", x, z) % 4
        line = [(x + i, z) if ax == "x" else (x, z + i) for i in range(length)]
        if not all(plan.inside(*c) and not plan.blocked(*c) and c not in plan.solid_cols and c not in plan.ring8
                   and c not in plan.W and plan.gr(*c) >= yS + 2 for c in line):
            continue
        gs = [plan.gr(*c) for c in line]
        if max(gs) - min(gs) > 1:
            continue
        for (cx_, cz_), gg in zip(line, gs):
            plan.put("structures", cx_, gg + 1, cz_, "minecraft:spruce_log[axis=%s]" % ax)
            plan.solid_cols.add((cx_, cz_))
            if h32(seed, "fm", cx_, cz_) % 100 < 40:
                plan.put("plants", cx_, gg + 2, cz_, "minecraft:moss_carpet", "keep")
        made += 1
    plan.count("fallen_log", made)
    # the ground: moss, podzol and coarse dirt round the water, thinning with distance
    painted = {}
    pr = G["paint_radius"]
    for x in range(gx0, gx1 + 1):
        for z in range(gz0, gz1 + 1):
            if plan.blocked(x, z) or (x, z) in plan.W or (x, z) in plan.ring8 or (x, z) in plan.solid_cols:
                continue
            g = plan.gr(x, z)
            if g < yS + 1:
                continue
            painted[(x, z)] = None
    pd = water_distance(plan, list(painted))
    for (x, z) in sorted(painted):
        d = pd[(x, z)]
        if d > pr:
            continue
        if frac(seed, "pp", x // 3, z // 3) >= 0.92 * (1.0 - d / pr):
            continue
        blk = pick(G["paint"], seed, "pb", x // 3, z // 3)
        plan.put("paint", x, plan.gr(x, z), z, "minecraft:" + blk)
        plan.l1_paint.add((x, z))
        painted[(x, z)] = blk
    plan.count("painted_columns", sum(1 for v in painted.values() if v))
    # plants on the dirt-tag ground only
    nplant = 0
    for (x, z) in sorted(painted):
        blk = painted[(x, z)]
        if blk not in ("moss_block", "podzol", "coarse_dirt") or (x, z) in plan.solid_cols:
            continue
        if frac(seed, "pl", x, z) >= G["plant_share"]:
            continue
        g = plan.gr(x, z)
        kind = pick(G["plants"], seed, "pk", x, z)
        plan.put("clear", x, g + 1, z, AIR, "snow")
        if kind == "large_fern":
            plan.put("plants", x, g + 1, z, "minecraft:large_fern[half=lower]", "keep")
            plan.put("plants", x, g + 2, z, "minecraft:large_fern[half=upper]", "keep")
        else:
            plan.put("plants", x, g + 1, z, "minecraft:" + kind, "keep")
        plan.plants.append((x, g + 1, z, kind))
        nplant += 1
    plan.count("plants", nplant)


def free_column(plan, target, avoid_water=True, bound=14):
    """The nearest column to target that no tree, boulder, log or brick stands in and that is dry land two over the water."""
    yS = plan.doc["pond"]["water_level"]
    tx, tz = target
    best = None
    for r in range(0, bound + 1):
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if max(abs(dx), abs(dz)) != r:
                    continue
                c = (tx + dx, tz + dz)
                if not plan.inside(*c) or plan.blocked(*c) or c in plan.solid_cols or c in plan.W or c in plan.ring8:
                    continue
                if plan.gr(*c) < yS + 2:
                    continue
                best = c
                break
            if best:
                break
        if best:
            return best
    raise TarnError("no free column within %d of %s for a Habitat Block" % (bound, target))


def build_wards(plan):
    doc = plan.doc
    Wd = doc["wards"]
    lobes = doc["pond"]["lobe_seeds"]
    for w in Wd["land"]:
        x, z = free_column(plan, w["target"])
        plan.solid_cols.add((x, z))
        plan.put("wards", x, plan.gr(x, z), z, w["mimic"])
        plan.wards[w["id"]] = (x, plan.gr(x, z), z)
    for w in Wd["water"]:
        sx, sz = lobes[w["lobe"]]
        cells = [c for c in plan.W if math.hypot(c[0] - sx, c[1] - sz) <= 8]
        if not cells:
            raise TarnError("lobe %d has no water within 8 of %s" % (w["lobe"], (sx, sz)))
        x, z = min(cells, key=lambda c: (plan.gr(*c), c))
        plan.put("wards", x, plan.gr(x, z), z, w["mimic"])
        plan.wards[w["id"]] = (x, plan.gr(x, z), z)


# ------------------------------------------------------------------------------------------------------- layer 2: the arms
# The owner, 2026-10-12: "The forest should expand toward the Scar, maybe envelop some of it, and then down the back and
# side of the mountain." Layer 1 above is the tarn's own wood and is not touched; the arms are laid along spines in
# data/scar_tarn.json growth.arms, one function each, with the same kinds, heights, paint and plants.
SKIP_FILES = {"scar_tarn.json", "cells.json", "regions.json", "world.json"}   # planning labels, not things (the audit's list)
OWN = re.compile(r"scar_tarn")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _xz(p):
    return isinstance(p, list) and len(p) in (2, 3) and all(_num(v) for v in p) and 0 <= p[0] <= 8192 and 0 <= p[-1] <= 8192


def authored_lines_boxes(window, m, exempt_boxes=()):
    """(lines, boxes) any OTHER data/*.json authors near `window` (within m + 400 for a line, m for a box): a line is a list of
    two or more [x, z] / [x, y, z] points; a box is a dict carrying min_x/min_z/max_x/max_z or x0/z0/x1/z1. Records whose path
    or id names scar_tarn are this place's own. A box over 1024 x 1024 is a region label, not a thing."""
    x0, z0, x1, z1 = window
    lines, boxes = [], []

    def walk(o, path):
        if OWN.search(path):
            return
        if isinstance(o, dict):
            if OWN.search(str(o.get("id", ""))) or OWN.search(str(o.get("scope", ""))):
                return
            for a, b, c, d in (("min_x", "min_z", "max_x", "max_z"), ("x0", "z0", "x1", "z1")):
                if all(_num(o.get(k)) for k in (a, b, c, d)):
                    boxes.append((o[a], o[b], o[c], o[d]))
            for k, v in o.items():
                walk(v, "%s.%s" % (path, k))
        elif isinstance(o, list):
            if _xz(o):
                return
            if len(o) >= 2 and all(_xz(p) for p in o):
                pts = [(p[0], p[-1]) for p in o]
                if any(x0 - m - 400 <= x <= x1 + m + 400 and z0 - m - 400 <= z <= z1 + m + 400 for x, z in pts):
                    lines.append(pts)
                return
            for i, v in enumerate(o):
                walk(v, "%s[%d]" % (path, i))

    for fn in sorted((ROOT / "data").glob("*.json")):
        if fn.name in SKIP_FILES:
            continue
        try:
            walk(json.loads(fn.read_text(encoding="utf-8")), "")
        except ValueError:
            continue
    ex = {tuple(b) for b in exempt_boxes}
    boxes = [b for b in boxes if tuple(b) not in ex and (b[2] - b[0]) * (b[3] - b[1]) <= 1024 * 1024
             and not (b[2] < x0 - m or b[0] > x1 + m or b[3] < z0 - m or b[1] > z1 + m)]
    return lines, boxes


def seg_dist_grid(xx, zz, a, b):
    """Distance from every cell of the (xx, zz) mesh to the segment a-b."""
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    L = float(dx * dx + dz * dz)
    t = np.zeros(xx.shape) if L == 0 else np.clip(((xx - ax) * dx + (zz - az) * dz) / L, 0, 1)
    return np.hypot(xx - (ax + t * dx), zz - (az + t * dz))


def polygon_mask(xx, zz, ring):
    """True where the cell centre is inside the polygon ring (even-odd)."""
    inside = np.zeros(xx.shape, bool)
    n = len(ring)
    for i in range(n):
        (ax, az), (bx, bz) = ring[i], ring[(i + 1) % n]
        if az == bz:
            continue
        cross = ((az > zz) != (bz > zz)) & (xx < (bx - ax) * (zz - az) / (bz - az) + ax)
        inside ^= cross
    return inside


def dilate_square(mask, r):
    """The mask grown by r columns each way (a square, which holds every canopy the generator draws)."""
    out = mask.copy()
    for _ in range(r):
        a = out.copy()
        a[1:, :] |= out[:-1, :]
        a[:-1, :] |= out[1:, :]
        b = a.copy()
        b[:, 1:] |= a[:, :-1]
        b[:, :-1] |= a[:, 1:]
        out = b
    return out


def convex_hull(points):
    """Counter-clockwise convex hull (monotone chain) of [(x, z), ...]."""
    pts = sorted(set(points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def scar_core(margin):
    """The city's core: the convex hull of the rectangles its house lots fill along the three roads (the road's width/2 + the
    lots' setback + their depth each side, and one lot + gap past each end), grown by margin. Read from data/placements.json
    settlements.the_scar.plan, so a re-laid city moves it."""
    pl = jload("placements.json")["settlements"]["the_scar"]["plan"]
    streets = {s_["id"]: s_ for s_ in pl["streets"]}
    lots = pl["house_lots"]
    corners = []
    for rid in lots["along"]:
        st = streets[rid]
        (ax, az), (bx, bz) = st["polyline"][0], st["polyline"][-1]
        half = st["width"] / 2.0 + lots["setback"] + lots["size"][1] + margin
        end = lots["size"][0] + lots["gap"] + margin
        x0, x1, z0, z1 = min(ax, bx) - end, max(ax, bx) + end, min(az, bz) - half, max(az, bz) + half
        corners += [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    return convex_hull(corners)


def arms_mask(plan):
    """A (z, x) boolean array over the union window: True where an arm may write nothing. The authored clearance from every
    x/z, line and box another record authors (the same 24 the tarn's own wood keeps), the avoid boxes, everything outside the
    Mt Vessu outline and every column whose ground is under min_ground_y."""
    import southern_residents as SR
    doc = plan.doc
    AR = doc["growth"]["arms"]
    m = doc["rules"]["authored_clearance"]
    x0, z0, x1, z1 = plan.UX0, plan.UZ0, plan.UX1, plan.UZ1
    zz, xx = np.mgrid[z0:z1 + 1, x0:x1 + 1]
    mask = np.zeros(zz.shape, bool)
    mine = {(w[0], w[2]) for w in plan.wards.values()}
    for (px, pz, f) in SR.authored_points({"residents": []}, own_file=DATA):
        if not (x0 - m <= px <= x1 + m and z0 - m <= pz <= z1 + m):
            continue
        if f == "habitat_blocks.json" and (px, pz) in mine:
            continue
        mask |= np.hypot(xx - px, zz - pz) < m + 1.5
    lines, boxes = authored_lines_boxes((x0, z0, x1, z1), m, [e["box"] for e in doc["rules"].get("authored_box_exempt") or []])
    for pts in lines:
        for a, b in zip(pts, pts[1:]):
            if max(a[0], b[0]) < x0 - m or min(a[0], b[0]) > x1 + m or max(a[1], b[1]) < z0 - m or min(a[1], b[1]) > z1 + m:
                continue
            mask |= seg_dist_grid(xx, zz, a, b) < m + 0.5
    for (bx0, bz0, bx1, bz1) in boxes:
        mask |= (xx >= bx0 - m) & (xx <= bx1 + m) & (zz >= bz0 - m) & (zz <= bz1 + m)
    for ab in AR["avoid_boxes"]:
        bx0, bz0, bx1, bz1 = ab["box"]
        mask |= (xx >= bx0) & (xx <= bx1) & (zz >= bz0) & (zz <= bz1)
    core = AR.get("keep_clear_core")
    if core:
        mask |= polygon_mask(xx + 0.5, zz + 0.5, scar_core(core["margin"]))
    lm = next(l for l in jload("landmarks.json")["landmarks"] if l["id"] == AR["inside_landmark"])
    ring = [tuple(p) for p in lm["extent"]["polygons"][0]]
    mask |= ~polygon_mask(xx + 0.5, zz + 0.5, ring)
    mask |= plan.A < AR["min_ground_y"]
    return mask


def relief_grid(A, window_ok=None):
    """Max - min of each cell's 3 x 3 (edge cells repeat the border)."""
    P = np.pad(A, 1, mode="edge")
    mx = np.full(A.shape, -10 ** 9)
    mn = np.full(A.shape, 10 ** 9)
    for a in (0, 1, 2):
        for b in (0, 1, 2):
            s = P[a:a + A.shape[0], b:b + A.shape[1]]
            mx = np.maximum(mx, s)
            mn = np.minimum(mn, s)
    return mx - mn


def lobe_p(lobe, xx, zz):
    """The lobe's tree probability over the mesh: pmax * (1 - u) ** falloff, u = distance to the spine over its radius there."""
    best = np.full(xx.shape, 9.0)
    k = lobe["spine"]
    for (ax, az, ar), (bx, bz, br) in zip(k, k[1:]):
        dx, dz = bx - ax, bz - az
        L = float(dx * dx + dz * dz)
        t = np.clip(((xx - ax) * dx + (zz - az) * dz) / L, 0, 1)
        d = np.hypot(xx - (ax + t * dx), zz - (az + t * dz))
        best = np.minimum(best, d / (ar + t * (br - ar)))
    return np.where(best < 1.0, lobe["max_probability"] * (1.0 - np.minimum(best, 1.0)) ** lobe["falloff"], 0.0)


def canopy_radius(kind, h):
    return {"spruce": 2 + h // 6, "elder": 2 + h // 6, "birch": 2, "snag": 1}[kind]


def build_arms(plan):
    doc = plan.doc
    G = doc["growth"]
    AR = G["arms"]
    P_ = doc["pond"]
    yS = P_["water_level"]
    seed = AR["seed"]
    cell = AR["cell"]
    rmax_relief = AR["max_relief_3x3"]
    plan.lim = (plan.UX0, plan.UZ0, plan.UX1, plan.UZ1)
    plan.mask, plan.mask_org = arms_mask(plan), (plan.UX0, plan.UZ0)
    M = plan.mask
    ox, oz = plan.UX0, plan.UZ0
    zz, xx = np.mgrid[oz:plan.UZ1 + 1, ox:plan.UX1 + 1]
    lobes = AR["lobes"]
    Pbest = np.zeros(zz.shape)
    LI = np.full(zz.shape, -1)
    for i, lb in enumerate(lobes):
        Pi = lobe_p(lb, xx, zz)
        better = Pi > Pbest
        Pbest = np.where(better, Pi, Pbest)
        LI = np.where(better, i, LI)
    R3 = relief_grid(plan.A)
    DIL = {r: dilate_square(M, r) for r in range(0, 7)}
    edge = 8
    cands = []
    for cx in range(plan.UX0 + edge, plan.UX1 - edge, cell):
        for cz in range(plan.UZ0 + edge, plan.UZ1 - edge, cell):
            x = cx + h32(seed, "jx", cx, cz) % cell
            z = cz + h32(seed, "jz", cx, cz) % cell
            iz, ix = z - oz, x - ox
            if Pbest[iz, ix] <= 0 or M[iz, ix] or (x, z) in plan.W or (x, z) in plan.ring8 or (x, z) in plan.solid_cols:
                continue
            if R3[iz, ix] > rmax_relief:
                continue
            cands.append((x, z))
    # water distance only where the tarn is within reach
    wx = [c[0] for c in plan.W]
    wz = [c[1] for c in plan.W]
    near = [c for c in cands if min(wx) - 70 <= c[0] <= max(wx) + 70 and min(wz) - 70 <= c[1] <= max(wz) + 70]
    dist = {c: 999.0 for c in cands}
    dist.update(water_distance(plan, near))
    counts = {lb["id"]: {"trees": 0} for lb in lobes}
    pool = {lb["id"]: [] for lb in lobes}            # candidates a tree did not take: boulders, logs, stubs
    for (x, z) in cands:
        iz, ix = z - oz, x - ox
        li = int(LI[iz, ix])
        lb = lobes[li]
        d = dist[(x, z)]
        g = plan.gr(x, z)
        if d <= G["trunk_clear"]:
            continue
        p = Pbest[iz, ix]
        t = frac(seed, "tk", x, z)
        if t < G["snag_share"]:
            kind, h = "snag", G["snag_height"][0] + h32(seed, "th", x, z) % (G["snag_height"][1] - G["snag_height"][0] + 1)
        elif t < G["snag_share"] + G["elder_share"] and d > 6:
            kind, h = "elder", G["elder_height"][0] + h32(seed, "th", x, z) % (G["elder_height"][1] - G["elder_height"][0] + 1)
        elif d <= G["birch_within"] and frac(seed, "tb", x, z) < G["birch_share"]:
            kind, h = "birch", G["birch_height"][0] + h32(seed, "th", x, z) % (G["birch_height"][1] - G["birch_height"][0] + 1)
        else:
            kind, h = "spruce", G["spruce_height"][0] + h32(seed, "th", x, z) % (G["spruce_height"][1] - G["spruce_height"][0] + 1)
        if DIL[canopy_radius(kind, h)][iz, ix]:
            continue
        if frac(seed, "tp", x, z) >= p:
            pool[lb["id"]].append((x, z))
            continue
        plan.begin("arm_" + lb["id"])
        place_tree(plan, kind, x, z, h)
        counts[lb["id"]]["trees"] += 1

    def usable(c):
        x, z = c
        return (plan.inside(x, z) and not plan.blocked(x, z) and c not in plan.solid_cols and c not in plan.W
                and c not in plan.ring8 and R3[z - oz, x - ox] <= 3)

    for i, lb in enumerate(lobes):
        unit = "arm_" + lb["id"]
        plan.begin(unit)
        free = [c for c in pool[lb["id"]] if usable(c) and dist[c] > 4]
        # brick stubs: the Scar's own palette, a few to a lobe that runs along the city
        made = []
        for (x, z) in sorted(free, key=lambda c: h32(seed, "rs", lb["id"], c[0], c[1])):
            if len(made) >= lb.get("ruin_stubs", 0):
                break
            if any(math.hypot(x - s[0], z - s[1]) < 24 for s in made):
                continue
            ax = "x" if h32(seed, "ra", x, z) % 2 else "z"
            length = 5 + h32(seed, "rl", x, z) % 5
            line = [(x + k, z) if ax == "x" else (x, z + k) for k in range(length)]
            if not all(usable(c) for c in line):
                continue
            gs = [plan.gr(*c) for c in line]
            if max(gs) - min(gs) > 2:
                continue
            for (cx_, cz_) in line:
                gg = plan.gr(cx_, cz_)
                top = 1 + h32(seed, "rt", cx_, cz_) % 3
                for y in range(gg + 1, gg + top + 1):
                    blk = "minecraft:mossy_stone_bricks" if h32(seed, "rb", cx_, y, cz_) % 100 < 55 else "minecraft:cracked_stone_bricks"
                    plan.put("structures", cx_, y, cz_, blk)
                if top >= 2 and h32(seed, "rc", cx_, cz_) % 4 == 0:
                    plan.put("structures", cx_, gg + top + 1, cz_, "minecraft:mossy_stone_brick_slab[type=bottom,waterlogged=false]")
                plan.solid_cols.add((cx_, cz_))
            made.append((x, z))
            plan.count("arm_brick_stub")
        counts[lb["id"]]["stubs"] = len(made)
        # boulders
        nb = 0
        for (x, z) in sorted(free, key=lambda c: h32(seed, "bo", lb["id"], c[0], c[1])):
            if nb >= lb.get("boulders", 0):
                break
            if (x, z) in plan.solid_cols:
                continue
            rr = 1 + h32(seed, "br", x, z) % 2
            cols = [(x + a, z + b, rr - int(math.hypot(a, b) + 0.5)) for a in range(-rr, rr + 1) for b in range(-rr, rr + 1)]
            cols = [(cx_, cz_, hh) for cx_, cz_, hh in cols if hh >= 1 and usable((cx_, cz_))]
            if not cols:
                continue
            for cx_, cz_, hh in cols:
                gg = plan.gr(cx_, cz_)
                for y in range(gg + 1, gg + hh + 1):
                    plan.put("structures", cx_, y, cz_, "minecraft:mossy_cobblestone" if h32(seed, "bm", cx_, y, cz_) % 3 else "minecraft:cobblestone")
                plan.solid_cols.add((cx_, cz_))
            nb += 1
        plan.count("arm_boulder", nb)
        counts[lb["id"]]["boulders"] = nb
        # fallen logs
        nl = 0
        for (x, z) in sorted(free, key=lambda c: h32(seed, "fl", lb["id"], c[0], c[1])):
            if nl >= lb.get("fallen_logs", 0):
                break
            ax = "x" if h32(seed, "fa", x, z) % 2 else "z"
            length = 5 + h32(seed, "fn", x, z) % 4
            line = [(x + k, z) if ax == "x" else (x, z + k) for k in range(length)]
            if not all(usable(c) for c in line):
                continue
            gs = [plan.gr(*c) for c in line]
            if max(gs) - min(gs) > 1:
                continue
            for (cx_, cz_), gg in zip(line, gs):
                plan.put("structures", cx_, gg + 1, cz_, "minecraft:spruce_log[axis=%s]" % ax)
                plan.solid_cols.add((cx_, cz_))
                if h32(seed, "fm", cx_, cz_) % 100 < 40:
                    plan.put("plants", cx_, gg + 2, cz_, "minecraft:moss_carpet", "keep")
            nl += 1
        plan.count("arm_fallen_log", nl)
        counts[lb["id"]]["fallen_logs"] = nl
    # the ground: moss, podzol and coarse dirt thinning with the trees; plants on the dirt-tag ground only
    gain = AR["paint_gain"]
    npaint = nplant = 0
    iz_s, ix_s = np.nonzero(Pbest > 0)
    for iz, ix in sorted(zip(iz_s.tolist(), ix_s.tolist()), key=lambda t: (t[1], t[0])):
        x, z = ix + ox, iz + oz
        if M[iz, ix] or (x, z) in plan.W or (x, z) in plan.ring8 or (x, z) in plan.solid_cols or (x, z) in plan.l1_paint:
            continue
        if R3[iz, ix] > 3 or plan.gr(x, z) < yS + 1:
            continue
        if frac(seed, "pp", x // 3, z // 3) >= min(0.92, gain * Pbest[iz, ix]):
            continue
        blk = pick(G["paint"], seed, "pb", x // 3, z // 3)
        plan.begin("arm_" + lobes[int(LI[iz, ix])]["id"])
        g = plan.gr(x, z)
        plan.put("paint", x, g, z, "minecraft:" + blk)
        plan.arm_paint.add((x, z))
        npaint += 1
        if blk not in ("moss_block", "podzol", "coarse_dirt") or frac(seed, "pl", x, z) >= G["plant_share"]:
            continue
        kind = pick(G["plants"], seed, "pk", x, z)
        plan.put("clear", x, g + 1, z, AIR, "snow")
        if kind == "large_fern":
            plan.put("plants", x, g + 1, z, "minecraft:large_fern[half=lower]", "keep")
            plan.put("plants", x, g + 2, z, "minecraft:large_fern[half=upper]", "keep")
        else:
            plan.put("plants", x, g + 1, z, "minecraft:" + kind, "keep")
        nplant += 1
    plan.count("arm_painted_columns", npaint)
    plan.count("arm_plants", nplant)
    plan.arm_lobe_counts = counts
    plan.begin("build")
    plan.lim = (plan.X0, plan.Z0, plan.X1, plan.Z1)


def plan(doc=None, g=None, source_root=None):
    import ground as G
    doc = doc or load()
    g = g or G.load(source_root)
    pl = Plan(doc, g)
    pl.mask = pl.keepout()
    pl.pond = build_pond(pl)
    build_growth(pl)
    build_wards(pl)
    if doc["growth"].get("arms"):
        build_arms(pl)
    pl.problems = check_plan(pl)
    return pl


# ---------------------------------------------------------------------------------------------------------- the pack
def compact(cells):
    """setblock/fill lines for {(x, y, z): (state, mode)}: runs along x at constant (y, z), then runs of equal runs up y."""
    rows = {}
    for (x, y, z), sm in cells.items():
        rows.setdefault((y, z, sm), []).append(x)
    runs = {}
    for (y, z, sm), xs in rows.items():
        xs.sort()
        s = p = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == p + 1:
                p = x
                continue
            runs.setdefault((s, p, z, sm), []).append(y)
            if x is not None:
                s = p = x
    boxes = []
    for (x0, x1, z, sm), ys in runs.items():
        ys.sort()
        a = b = ys[0]
        for y in ys[1:] + [None]:
            if y is not None and y == b + 1:
                b = y
                continue
            boxes.append((a, z, x0, b, x1, sm))
            if y is not None:
                a = b = y
    boxes.sort()
    out = []
    for (y0, z, x0, y1, x1, (state, mode)) in boxes:
        if mode == "snow":
            out.append("fill %d %d %d %d %d %d minecraft:air replace minecraft:snow" % (x0, y0, z, x1, y1, z))
            continue
        suffix = " keep" if mode == "keep" else ""
        if x0 == x1 and y0 == y1:
            out.append("setblock %d %d %d %s%s" % (x0, y0, z, state, suffix))
        else:
            out.append("fill %d %d %d %d %d %d %s%s" % (x0, y0, z, x1, y1, z, state, suffix))
    return out


def phase_cells(pl, phase, unit="build"):
    cells = {}
    for (x, y, z, state, mode) in pl.units[unit][phase]:
        if mode == "keep":
            if (x, y, z) in cells:
                continue
        cells[(x, y, z)] = (state, mode)
    return cells


def build_lines(pl, unit="build"):
    if unit == "build":
        head = ["# Generated by tools/scar_tarn.py from data/scar_tarn.json. Re-run to rebuild; do not edit.",
                "# The Scar Tarn: the pond, its bank, the growth round it and the four Habitat Block mimics.",
                "# Run BEFORE R9E (step R9ST): the four activated Habitat Blocks scar_tarn_*_ward stand in cells this writes."]
    else:
        head = ["# Generated by tools/scar_tarn.py from data/scar_tarn.json growth.arms. Re-run to rebuild; do not edit.",
                "# The Scar Tarn's wood, %s: an arm of the same wood (spruce, birch, snags, moss and ferns), laid along the" % unit[len("arm_"):],
                "# heightmap. Writes no water and no Habitat Block mimic; run in step R9ST, BEFORE R9E."]
    out = list(head)
    for ph in Plan.PHASES:
        cells = phase_cells(pl, ph, unit)
        out.append("# %s (%d cells)" % (ph, len(cells)))
        out += compact(cells)
    return out


def box(pl, unit="build"):
    cols = pl.unit_cols[unit]
    xs = [c[0] for c in cols]
    zs = [c[1] for c in cols]
    return min(xs), min(zs), max(xs), max(zs)


def units(pl):
    """The functions the pack holds: build first (the tarn and its own wood), then each arm that wrote anything, in the record's order."""
    order = ["build"] + ["arm_" + lb["id"] for lb in (pl.doc["growth"].get("arms") or {}).get("lobes", [])]
    return [u for u in order if u in pl.units and pl.unit_cols.get(u)]


def files(doc=None, g=None, pl=None, check=True):
    pl = pl or plan(doc, g)
    if check and pl.problems:
        raise TarnError("scar_tarn: %d problem(s): %s" % (len(pl.problems), "; ".join(pl.problems[:4])))
    out = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Scar Tarn (tools/scar_tarn.py)"}}, indent=2) + "\n",
    }
    for u in units(pl):
        lines = function_limits.ensure_loaded(build_lines(pl, u))
        bad = function_limits.check_lines(lines, u)
        if bad:
            raise TarnError("%s: %d command(s) the server would refuse: %s" % (u, len(bad), bad[:3]))
        out["data/%s/function/%s/%s.mcfunction" % (NS, FN, u)] = "\n".join(lines) + "\n"
    return out, pl


def write(out_files, out=OUT):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def hold_boxes(b):
    """The box (x0, z0, x1, z1) as `forceload add` boxes of at most 256 chunks each (the command's limit), split along z."""
    x0, z0, x1, z1 = b
    cw = x1 // 16 - x0 // 16 + 1
    rows = max(1, 256 // cw)
    out = []
    cz = z0 // 16
    last = z1 // 16
    while cz <= last:
        cz1 = min(last, cz + rows - 1)
        out.append((x0, max(z0, cz * 16), x1, min(z1, cz1 * 16 + 15)))
        cz = cz1 + 1
    return out


def placement_steps(doc=None, g=None, pl=None):
    """For tools/reapply.py, step R9ST BEFORE R9E: for each function (the tarn's build, then each arm of the wood) hold its
    box, run it, release (the Drovers' Hollow's shape). The tarn's own first step is the one this step always had."""
    pl = pl or plan(doc, g)
    steps = []
    for u in units(pl):
        holds = ["forceload add %d %d %d %d" % b for b in hold_boxes(box(pl, u))]
        steps += [("cmd", h) for h in holds] + [("wait", WAIT_SECONDS), ("fn", "%s:%s/%s" % (NS, FN, u))]
        steps += [("cmd", h.replace("add", "remove", 1)) for h in holds]
    return steps


# ------------------------------------------------------------------------------------------------------ the checks
def solid(pl, x, y, z, drop):
    """Is the cell a solid block when the world's ground is `drop` blocks under the heightmap everywhere the pack does
    not write? Water, plants and leaves are not solid."""
    st = pl.final.get((x, y, z))
    if st is not None:
        return base(st) not in NOT_SOLID
    return y <= pl.gr(x, z) - drop


def containment(pl, drop):
    """Water blocks with an open side or floor, when the unwritten ground is `drop` under the heightmap."""
    leaks = []
    for (x, y, z), st in pl.final.items():
        if st != WATER:
            continue
        for dx, dz in D4:
            n = (x + dx, y, z + dz)
            if pl.final.get(n) == WATER:
                continue
            if not solid(pl, *n, drop):
                leaks.append((x, y, z, "side", n))
        below = (x, y - 1, z)
        if pl.final.get(below) != WATER and not solid(pl, *below, drop):
            leaks.append((x, y, z, "floor", below))
    return leaks


def check_plan(pl):
    """The builder's guards (not an audit): the palette, spawn-condition blocks, concrete, containment at drop 0 and 1,
    the wards' mimics, the map margin and the authored-points clearance."""
    doc = pl.doc
    probs = []
    allowed = set(doc["blocks"]["ids"])
    written = {base(st) for ops in pl.units.values() for ph in ops.values() for (_x, _y, _z, st, _m) in ph}
    for b in sorted(written - allowed):
        probs.append("writes %s, not in blocks.ids" % b)
    spawn = set(jload("spawn_blocks.json")["blocks"])
    ok = {b for w in jload("spawn_block_policy.json")["whitelist"] if "scar_tarn" in (w.get("scope") or "")
          for b in w.get("blocks") or []}
    for b in sorted(written & spawn - ok):
        probs.append("writes %s, a block a spawn condition names (data/spawn_blocks.json) and no data/spawn_block_policy.json "
                     "entry scoped to scar_tarn allows it" % b)
    for b in sorted(written):
        if "concrete" in b:
            probs.append("writes %s: no concrete (contract C4)" % b)
    for drop in (0, 1):
        leaks = containment(pl, drop)
        if leaks:
            probs.append("%d water block(s) with an open side or floor when the unwritten ground is %d under the heightmap, "
                         "e.g. %s" % (len(leaks), drop, leaks[:2]))
    for w in doc["wards"]["land"] + doc["wards"]["water"]:
        pos = pl.wards.get(w["id"])
        st = pl.final.get(tuple(pos)) if pos else None
        if st is None or base(st) != w["mimic"]:
            probs.append("ward %s: the cell %s is %s, the mimic is %s" % (w["id"], pos, st and base(st), w["mimic"]))
    m = doc["rules"]["map_margin"]
    edge = [c for c in pl.cols if not (m <= c[0] < 8192 - m and m <= c[1] < 8192 - m)]
    if edge:
        probs.append("%d written column(s) within %d blocks of the map edge" % (len(edge), m))
    for kind in ("spruce", "elder", "birch", "snag"):
        pass
    if pl.counts.get("tree_spruce", 0) == 0:
        probs.append("the growth placed no spruce")
    if pl.counts.get("brick_stub", 0) == 0:
        probs.append("the growth placed no brick stub")
    probs += authored_sweep(pl)
    return probs


def authored_sweep(pl):
    import southern_residents as SR
    mine = {(w[0], w[2]) for w in pl.wards.values()}
    pts = [(x, z, f) for x, z, f in SR.authored_points({"residents": []}, own_file=DATA)
           if pl.UX0 - 60 <= x <= pl.UX1 + 60 and pl.UZ0 - 60 <= z <= pl.UZ1 + 60
           and not (f == "habitat_blocks.json" and (x, z) in mine)]
    if not pts:
        return []
    P = np.array([(a, b) for a, b, _f in pts], float)
    C = np.array(sorted(pl.cols), float)
    m = pl.doc["rules"]["authored_clearance"]
    for i in range(0, len(C), 4096):
        blk = C[i:i + 4096]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(int(np.argmin(d)), d.shape)
        if d[j] < m:
            return ["(%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                    % (blk[j[0]][0], blk[j[0]][1], d[j], pts[j[1]][2], m)]
    return []


# ----------------------------------------------------------------------------------------------- shared-file records
def pool_species_positions():
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    pos = {}
    for e in sd["entries"]:
        pos.setdefault(e["species"], e.get("spawnable_position") or "grounded")
    return pos


def records(pl):
    """(habitat block records, [pool {habitat, entries}]) this place owns in the shared files."""
    doc = pl.doc
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    rar = sd["rarity"]
    A = doc["alphas"]
    lo, hi = A["band"]
    habs, pools = [], []
    by_pool = {}
    for w in doc["wards"]["land"] + doc["wards"]["water"]:
        by_pool.setdefault(w["pool"], []).append(w)
    for pid, spec in A["pools"].items():
        wards = by_pool[pid]
        water = pid.endswith("waters")
        act = doc["wards"]["water_activated" if water else "land_activated"]
        for w in wards:
            x, y, z = pl.wards[w["id"]]
            habs.append({
                "id": w["id"],
                "place": "the Scar Tarn (data/scar_tarn.json): %s" % w["place"],
                "pool": "cobblers:%s" % pid,
                "style": "activated",
                "replace_spawns": False,
                "position": {"x": x, "y": y, "z": z},
                "mimic": w["mimic"],
                "activated": dict(act),
                "status": "planned",
                "why": "written by tools/scar_tarn.py records --write from the plan (data/scar_tarn.json wards). An activated block keeps "
                       "up to %d of the pool alive within %d blocks and refills as they are beaten, caught or despawn; the pool's "
                       "entries carry modifiers \"alpha=true\", so what it keeps is a wild ALPHA (owner, 2026-10-11: alpha mons "
                       "taken over the afflicted ground). cancel_range -1: Mt Vessu's own spawns continue round it. Stands in a cell "
                       "the pack writes (%s), so the pack runs BEFORE R9E. UNPROVEN in game: that the habitat spawn carries the "
                       "alpha (read from the jar's bytecode, data/scar_tarn.json alphas.how)." % (act["max_spawns"], act["spawn_range"], w["mimic"]),
                "mimic_why": "the block the pack writes at that position: %s" % w["place"]})
        positions = pool_species_positions()
        hab_entries, entries = [], []
        for r in spec["entries"]:
            bucket = rar[r["role"]]["bucket"]
            weight = rar[r["role"]]["family_weight"]
            fam = r["species"]
            cond = {}
            hab_entries.append({"species": r["species"].capitalize(), "pokemon": r["species"], "family": fam,
                                "family_priority": r["role"], "ambient": True, "eligibility_reason": r["why"],
                                "level": "%d-%d" % (lo, hi), "bucket": bucket, "weight": weight, "conditions": cond,
                                "modifiers": A["modifiers"]})
            entries.append({"id": "habitat.%s.%s" % (pid, r["species"]), "species": r["species"], "bucket": bucket,
                            "level": "%d-%d" % (lo, hi), "weight": weight, "ambient": True, "scope": pid,
                            "mechanism": "habitat_block", "conditions": cond, "eligibility_reason": r["why"],
                            "spawnable_position": r.get("position") or positions.get(r["species"], "grounded"),
                            "modifiers": A["modifiers"]})
        habitat = {"id": pid, "display_name": spec["display_name"],
                   "intended_location": "the Scar Tarn on Mt Vessu's north-north-west shoulder (data/scar_tarn.json): %d activated Habitat "
                                        "Block(s), %s in data/habitat_blocks.json, keeping up to %d alive within %d each"
                                        % (len(wards), ", ".join(w["id"] for w in wards), act["max_spawns"], act["spawn_range"]),
                   "mechanism": "habitat_block", "replace_spawns": False,
                   "level_band": {"minimum": lo, "maximum": hi}, "level_band_why": A["band_why"],
                   "why": "Alpha Pokemon (entries carry modifiers %r) that have taken over the Scar Tarn: %s"
                          % (A["modifiers"], "; ".join("%s: %s" % (r["species"], r["why"]) for r in spec["entries"])),
                   "entries": hab_entries,
                   "placement_status": "authored: data/habitat_blocks.json %s, status planned" % ", ".join(w["id"] for w in wards)}
        pools.append({"habitat": habitat, "entries": entries})
    return habs, pools


def write_records(habs, pools):
    def dump(path, d):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    hd = json.loads(HABITATS.read_text(encoding="utf-8"))
    ids = {h["id"] for h in habs}
    hd["blocks"] = [b for b in hd["blocks"] if b.get("id") not in ids] + habs
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    pids = {p["habitat"]["id"] for p in pools}
    sd["habitats"] = [h for h in sd["habitats"] if h.get("id") not in pids] + [p["habitat"] for p in pools]
    sd["entries"] = [e for e in sd["entries"] if e.get("scope") not in pids] + [e for p in pools for e in p["entries"]]
    dump(HABITATS, hd)
    dump(SPAWNS, sd)


def presence_probes(pl):
    """{place id: [probe]} in data/world_probes.json's shape, read from the plan and never from a world."""
    pr = pl.doc["probes"]
    rows = []

    def row(what, x, y, z, state, expect=True):
        rows.append({"what": what, "block": [x, y, z, state], "expect": expect})

    wards = {tuple(w) for w in pl.wards.values()}
    yS = pl.doc["pond"]["water_level"]
    # the water: the deepest column's surface, then a spread of columns, each an expected water block at the level
    cols = sorted(pl.W)
    deepest = min(cols, key=lambda c: (pl.gr(*c), c))
    row("the tarn's surface over its deepest column (bed y%d)" % pl.gr(*deepest), deepest[0], yS, deepest[1], WATER)
    step = max(1, len(cols) // pr["water"])
    for (x, z) in cols[::step][:pr["water"]]:
        row("tarn water at the surface", x, yS, z, WATER)
    row("the water is held: no water one block over the surface", deepest[0], yS + 1, deepest[1], WATER, False)
    # the rim: lifted bank columns are solid at the lift, and carry no water
    lift = pl.doc["pond"]["bank_lift_to"]
    ring = sorted(pl.ring4)
    step = max(1, len(ring) // pr["bank"])
    for (x, z) in ring[::step][:pr["bank"]]:
        row("rim of the tarn is not water", x, yS, z, WATER, False)
        st = pl.final.get((x, lift, z))
        if st is not None and (x, lift, z) not in wards:
            row("rim of the tarn, a lifted bank block", x, lift, z, base(st))
    # trees: the base log of a spread of trunks
    trees = sorted(pl.trees, key=lambda t: (t["x"], t["z"]))
    step = max(1, len(trees) // pr["trunks"])
    for t in trees[::step][:pr["trunks"]]:
        row("a %s's trunk" % t["kind"], t["x"], t["y0"], t["z"], "minecraft:spruce_log" if t["kind"] != "birch" else "minecraft:birch_log")
    # the ground painted round it
    painted = sorted({(x, y, z): base(st) for (x, y, z), st in pl.final.items()
                      if base(st) in ("minecraft:moss_block", "minecraft:podzol") and y == pl.gr(x, z) and (x, y, z) not in wards
                      and (x, z) not in pl.arm_paint}.items())
    step = max(1, len(painted) // pr["ground"])
    for (x, y, z), b in painted[::step][:pr["ground"]]:
        row("painted ground", x, y, z, b)
    # layer 2, the arms: appended after the tarn's own rows so those stay as they were. A few trunks and painted columns each
    for u in units(pl):
        if u == "build":
            continue
        trees = sorted((t for t in pl.arm_trees if t["unit"] == u), key=lambda t: (t["x"], t["z"]))
        if trees:
            step = max(1, len(trees) // pr["arm_trunks"])
            for t in trees[::step][:pr["arm_trunks"]]:
                row("the %s wood, a %s's trunk" % (u[len("arm_"):], t["kind"]), t["x"], t["y0"], t["z"],
                    "minecraft:spruce_log" if t["kind"] != "birch" else "minecraft:birch_log")
        mine = sorted({(x, y, z): base(st) for (x, y, z), st in pl.final.items()
                       if base(st) in ("minecraft:moss_block", "minecraft:podzol") and y == pl.gr(x, z)
                       and (x, z) in pl.unit_cols[u] and (x, z) in pl.arm_paint}.items())
        if mine:
            step = max(1, len(mine) // pr["arm_ground"])
            for (x, y, z), b in mine[::step][:pr["arm_ground"]]:
                row("the %s wood, painted ground" % u[len("arm_"):], x, y, z, b)
    return {pr["key"]: rows}


# --------------------------------------------------------------------------------------------------------- the CLI
def report(pl):
    P = pl.pond
    a = box(pl)
    xs = [c[0] for c in pl.W]
    zs = [c[1] for c in pl.W]
    fns = [l for u in units(pl) for l in build_lines(pl, u)]
    n = sum(1 for l in fns if l and not l.startswith("#"))
    lines = ["pond: seed %s, water y%d, %d columns, %d water blocks, deepest %d, bbox x%d..%d z%d..%d; the lowest natural rim "
             "column is y%d (bank lifted to y%d on %d of %d rim columns)"
             % (P["seed"], P["level"], P["columns"], pl.counts["water_blocks"], P["max_depth"], min(xs), max(xs), min(zs), max(zs),
                P["natural_rim_min"], pl.doc["pond"]["bank_lift_to"], pl.counts["bank_lifted"], pl.counts["bank_columns"]),
             "containment: %d leak(s) at drop 0, %d at drop 1" % (len(containment(pl, 0)), len(containment(pl, 1))),
             "growth: %s" % ", ".join("%s %d" % kv for kv in sorted(pl.counts.items()) if kv[0].startswith(("tree_", "brick", "boulder", "fallen", "plants", "painted"))),
             "arms: %s" % ", ".join("%s %d" % kv for kv in sorted(pl.counts.items()) if kv[0].startswith("arm_")),
             "arm lobes: %s" % json.dumps(pl.arm_lobe_counts),
             "units: %s" % ", ".join("%s box x%d..%d z%d..%d %d columns" % (u, box(pl, u)[0], box(pl, u)[2], box(pl, u)[1], box(pl, u)[3], len(pl.unit_cols[u])) for u in units(pl)),
             "wards: %s" % json.dumps({k: list(v) for k, v in pl.wards.items()}),
             "written box x%d..%d z%d..%d (%d columns); %d commands" % (a[0], a[2], a[1], a[3], len(pl.cols), n),
             "steps R9ST: %s" % json.dumps([list(s) for s in placement_steps(pl=pl)]),
             "problems: %s" % (pl.problems or "none")]
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "report", "records", "probes"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--write", action="store_true", help="records, probes: replace this place's records in the shared files")
    a = ap.parse_args(argv)
    pl = plan(doc=load(Path(a.data)), source_root=a.source_root)
    if a.cmd == "report":
        print("\n".join(report(pl)))
        return 1 if pl.problems else 0
    if a.cmd == "records":
        habs, pools = records(pl)
        if a.write:
            write_records(habs, pools)
            print("scar_tarn: wrote %d habitat blocks, %d pools with %d entries"
                  % (len(habs), len(pools), sum(len(p["entries"]) for p in pools)))
        else:
            print(json.dumps({"habitat_blocks": habs, "pools": pools}, indent=1))
        return 0
    if a.cmd == "probes":
        pr = presence_probes(pl)
        if a.write:
            d = json.loads(PROBES.read_text(encoding="utf-8"))
            d["places"].update(pr)
            with open(PROBES, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
            print("scar_tarn: wrote %d probes into data/world_probes.json (%s)" % (sum(len(v) for v in pr.values()), ", ".join(pr)))
        else:
            for k, v in pr.items():
                print(k, len(v), "probes")
        return 0
    written, _pl = files(pl=pl)
    write(written, a.out)
    n = sum(1 for rel, t in written.items() if rel.endswith(".mcfunction") for l in t.splitlines() if l and not l.startswith("#"))
    print("scar_tarn: %d files -> %s (%d commands)" % (len(written), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
