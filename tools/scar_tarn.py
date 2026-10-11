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

OUR LIST IS NOT THE WORLD. The clearance sweep covers every x/z any data/*.json authors (tools/southern_residents.py
authored_points), not what a donor template, a mod or a player put there; the Scar's own ruins are 120+ blocks south.

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
        self.X0, self.Z0, self.X1, self.Z1 = doc["pond"]["window"]
        self.A = g.box(self.X0, self.Z0, self.X1, self.Z1)
        self.ops = {p: [] for p in self.PHASES}      # phase -> [(x, y, z, state, mode)]
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
        return int(self.A[z - self.Z0, x - self.X0])

    def inside(self, x, z):
        return self.X0 <= x <= self.X1 and self.Z0 <= z <= self.Z1

    def put(self, phase, x, y, z, state, mode="replace"):
        if not self.inside(x, z) or self.blocked(x, z):
            return                                     # inside an authored point's clearance: nothing is written
        self.ops[phase].append((x, y, z, state, mode))
        self.cols.add((x, z))
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
        return bool(self.mask[z - self.Z0, x - self.X0])


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
            if not plan.inside(*n):
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
    plan.trees.append({"kind": kind, "x": x, "z": z, "y0": g + 1, "h": h})
    plan.count("tree_" + kind)


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


def plan(doc=None, g=None, source_root=None):
    import ground as G
    doc = doc or load()
    g = g or G.load(source_root)
    pl = Plan(doc, g)
    pl.mask = pl.keepout()
    pl.pond = build_pond(pl)
    build_growth(pl)
    build_wards(pl)
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


def phase_cells(pl, phase):
    cells = {}
    for (x, y, z, state, mode) in pl.ops[phase]:
        if mode == "keep":
            if (x, y, z) in cells:
                continue
        cells[(x, y, z)] = (state, mode)
    return cells


def build_lines(pl):
    head = ["# Generated by tools/scar_tarn.py from data/scar_tarn.json. Re-run to rebuild; do not edit.",
            "# The Scar Tarn: the pond, its bank, the growth round it and the four Habitat Block mimics.",
            "# Run BEFORE R9E (step R9ST): the four activated Habitat Blocks scar_tarn_*_ward stand in cells this writes."]
    out = list(head)
    for ph in Plan.PHASES:
        cells = phase_cells(pl, ph)
        out.append("# %s (%d cells)" % (ph, len(cells)))
        out += compact(cells)
    return out


def box(pl):
    xs = [c[0] for c in pl.cols]
    zs = [c[1] for c in pl.cols]
    return min(xs), min(zs), max(xs), max(zs)


def files(doc=None, g=None, pl=None, check=True):
    pl = pl or plan(doc, g)
    if check and pl.problems:
        raise TarnError("scar_tarn: %d problem(s): %s" % (len(pl.problems), "; ".join(pl.problems[:4])))
    lines = function_limits.ensure_loaded(build_lines(pl))
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise TarnError("build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    out = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Scar Tarn (tools/scar_tarn.py)"}}, indent=2) + "\n",
        "data/%s/function/%s/build.mcfunction" % (NS, FN): "\n".join(lines) + "\n",
    }
    return out, pl


def write(out_files, out=OUT):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def placement_steps(doc=None, g=None, pl=None):
    """For tools/reapply.py, step R9ST BEFORE R9E: hold the box, build, release (the Drovers' Hollow's shape)."""
    pl = pl or plan(doc, g)
    hold = "%d %d %d %d" % box(pl)
    return [("cmd", "forceload add " + hold), ("wait", WAIT_SECONDS), ("fn", "%s:%s/build" % (NS, FN)),
            ("cmd", "forceload remove " + hold)]


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
    written = {base(st) for ph in pl.ops.values() for (_x, _y, _z, st, _m) in ph}
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
           if pl.X0 - 60 <= x <= pl.X1 + 60 and pl.Z0 - 60 <= z <= pl.Z1 + 60
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
                      if base(st) in ("minecraft:moss_block", "minecraft:podzol") and y == pl.gr(x, z) and (x, y, z) not in wards}.items())
    step = max(1, len(painted) // pr["ground"])
    for (x, y, z), b in painted[::step][:pr["ground"]]:
        row("painted ground", x, y, z, b)
    return {pr["key"]: rows}


# --------------------------------------------------------------------------------------------------------- the CLI
def report(pl):
    P = pl.pond
    a = box(pl)
    xs = [c[0] for c in pl.W]
    zs = [c[1] for c in pl.W]
    fns = build_lines(pl)
    n = sum(1 for l in fns if l and not l.startswith("#"))
    lines = ["pond: seed %s, water y%d, %d columns, %d water blocks, deepest %d, bbox x%d..%d z%d..%d; the lowest natural rim "
             "column is y%d (bank lifted to y%d on %d of %d rim columns)"
             % (P["seed"], P["level"], P["columns"], pl.counts["water_blocks"], P["max_depth"], min(xs), max(xs), min(zs), max(zs),
                P["natural_rim_min"], pl.doc["pond"]["bank_lift_to"], pl.counts["bank_lifted"], pl.counts["bank_columns"]),
             "containment: %d leak(s) at drop 0, %d at drop 1" % (len(containment(pl, 0)), len(containment(pl, 1))),
             "growth: %s" % ", ".join("%s %d" % kv for kv in sorted(pl.counts.items()) if kv[0].startswith(("tree_", "brick", "boulder", "fallen", "plants", "painted"))),
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
