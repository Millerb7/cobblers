#!/usr/bin/env python
"""Offline audit of the open sea's floor (tools/sea_floor.py -> build/datapacks/cobblers_sea_floor).

INDEPENDENT of tools/sea_floor.py: nothing is imported from it, nothing is read from derived/sea_floor/plan.json, and
it does not use tools/sea_life.py's Exclusions (the builder's source of exclusions). Every expectation comes from:

  the design   docs/world-building/OCEAN.md section 4 'Kelp, seagrass, coral' (the depth bands, parsed from its table)
               and data/regions.json marine_regions[] (each region's biome rules, parsed from their text, and its
               seabed_plan.shelf_width_blocks), data/world.json vertical.sea_level, docs/mechanics/WATER_LIFE.md's
               'never within 2 of the surface' (a kelp top at most sea - 3)
  the ground   the canonical heightmap (tools/ground.py, rounded) and tools/water_mask.py's rule: a column is sea if its
               ground is below sea level and it is in no lake basin whose level is above its ground
  exclusions   tools/sea_life_audit.load_ctx(), the sea_life pack's INDEPENDENT audit's derivation from data/towns.json,
               data/sea_town.json, data/ferries.json + data/ferry_docks.json (stops and lanes), data/portals.json,
               data/legendaries.json, data/adopted_legendary_sites.json, data/placements.json, data/rift_regions.json
               (the Deep), data/water_shape.json (First Cast's hole, the gate crossings, recomputed from the
               heightmap), data/sea_drift.json (Driftmouth Isle and the drift route); data/sea_life.json's margins
  ownership    the EMITTED cobblers_sea_life functions (every column they write, and data/sea_floor.json
               ownership.sea_life_margin_blocks round it), the coasts data/sea_life.json shore.coasts names (their
               data/water_shape.json boxes, out to sea_life's own shore.kelp.from_land_blocks, measured as an exact
               Euclidean distance to land), the Relic reef (data/water_shape.json coasts.relic_reef: outer_radius max +
               drop_width_blocks, + ownership.reef_margin_blocks), and every other water pack built (lake_life,
               sea_drift, portals, legendaries)
  policy       data/spawn_blocks.json and data/spawn_block_policy.json

The pack's functions are PARSED (every fill expanded to its cells; nothing else is allowed) and checked:

  parse     only comments, `forceload add|remove` and `fill ... <plant> replace minecraft:water`; every function on disk
            is in index.txt and every index entry exists
  blocks    only kelp (age=25: growth stopped), kelp_plant, seagrass, tall_seagrass[half=lower|upper]
  water     every cell is sea water before the pack runs: a sea column (not a lake), above its ground, below sea level
  cells     no cell written twice (the second write's `replace minecraft:water` would match nothing)
  seabed    every column is ONE plant standing on its ground: kelp = stems from ground + 1 up to an age-25 head;
            seagrass one cell at ground + 1; tall seagrass lower at ground + 1, upper on top of it
  bands     kelp ground in OCEAN.md's kelp band, seagrass ground in its seagrass band; every kelp top at most sea - 3
  regions   per marine region (its polygon in data/sea_life.json finds.region_order's order; a column in none takes
            the nearest polygon): no flora where the region's rules make the biome frozen_ocean or deep_frozen_ocean,
            no kelp where they make it warm_ocean (OCEAN.md: kelp 'not warm or frozen', seagrass 'every ocean except
            frozen'), and no flora farther from land than the region's shelf width. Distances are EXACT Euclidean
            distances to the nearest land column (ground >= sea level)
  clear     no column in a town, Pacifidlog, a ferry stop or lane, a dive portal, a legendary's zone, an adopted site,
            a placement, the Deep, First Cast's hole, Driftmouth Isle or the drift route, a lake; no seagrass inside a
            gate crossing's clearance (only the crossings whose endpoints data/water_shape.json STATES; the derived
            ones, northgate_shortest and pacifidlog_nearest_land, are listed as not modelled: see gate_points())
  owned     no column within ownership.sea_life_margin_blocks (Chebyshev) of a column cobblers_sea_life writes; none in
            a sea_life coast box within its kelp reach of land; none inside the reef disc; no cell another water pack
            writes
  policy    every spawn-condition block written (data/spawn_blocks.json) has a data/spawn_block_policy.json entry whose
            scope names sea_floor
  forceload per function: the adds and removes are the same set, and every fill's chunks are added before it
  limits    tools/function_limits.py finds nothing the server would refuse

Independence, proved by MUTATING THE GENERATOR (2026-10-04; tools/sea_floor.py's source edited in memory, every data
file untouched, the mutant's pack built to a scratch directory and audited):
  M1 drop the sea_life margin (`X = X | near` -> `pass` in exclusion()): owned reports 883 columns within 3 of
     cobblers_sea_life and 148 cells it also writes (baseline 0 and 0)
  M2 drop the warm-south kelp rule (`& (dl > ru["kelp_beyond"])`): regions reports 108,144 kelp columns in warm_ocean,
     the nearest 180.83 from land (baseline 460, nearest 214.16)
  M3 `min(top, tmax_all)` -> `min(top, tmax_all + 2)`: no change, and correctly so: top = g + share x (tmax_all - g)
     with share <= 1 never exceeds tmax_all, so the cap is redundant and the mutant equivalent. The kelp-top check
     itself is exercised by tests/test_sea_floor_audit.py

What this does NOT cover: whether kelp and seagrass survive in game (kelp needs water above and a full block below;
the heightmap's ground is assumed full, not seen), whether a Dragalge, Skrelp or Pincurchin then spawns there, the
exclusions sea_life.py has that its audit does not derive (routes, bridges, Victory Road, the Rift, the Relic swim
lines: all on land or covered by other masks, not re-derived here), and anything in the sea no data file lists (the
`replace minecraft:water` filter is what protects those, and it is checked, not the world).

  python tools/sea_floor_audit.py [--source-root DIR] [--pack DIR]   writes derived/sea_floor/audit.json; exit 1 on any
                                                                     problem
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL       # noqa: E402
import water_life_replay as R      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "build" / "datapacks" / "cobblers_sea_floor"
FN = ("data", "cobblers", "function", "sea_floor")
OUT = ROOT / "derived" / "sea_floor" / "audit.json"
SEA_LIFE_PACK = ROOT / "build" / "datapacks" / "cobblers_sea_life"
CHECKS = ("parse", "blocks", "water", "cells", "seabed", "bands", "regions", "clear", "owned", "policy", "forceload",
          "limits")
WATER = "minecraft:water"
KELP_TOP = "minecraft:kelp[age=25]"
K_STEM, K_TOP, K_GRASS, K_TL, K_TU = 1, 2, 3, 4, 5
KINDS = {"minecraft:kelp_plant": K_STEM, KELP_TOP: K_TOP, "minecraft:seagrass": K_GRASS,
         "minecraft:tall_seagrass[half=lower]": K_TL, "minecraft:tall_seagrass[half=upper]": K_TU}
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: (replace|keep|destroy|hollow|outline)"
                  r"(?: (\S+))?)?$")
FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+))?$")


class AuditError(Exception):
    pass


# ------------------------------------------------------------------------------------------- the design, parsed


def ocean_bands(text):
    """{'kelp': (lo, hi), 'seagrass': (lo, hi)} from OCEAN.md section 4's flora table, and the two vanilla-biome
    sentences the region rule rests on."""
    out = {}
    for name in ("Kelp", "Seagrass"):
        m = re.search(r"^\| %s \|([^\n]*)\| y(\d+)[–-](\d+) \|\s*$" % name, text, re.M)
        if not m:
            raise AuditError("OCEAN.md has no '| %s | ... | yA-B |' row in its flora table" % name)
        out[name.lower()] = (int(m.group(2)), int(m.group(3)))
        out[name.lower() + "_biomes"] = m.group(1)
    if "not warm or frozen" not in out["kelp_biomes"]:
        raise AuditError("OCEAN.md's kelp row no longer says 'not warm or frozen'; the region rule needs re-reading")
    if "except frozen" not in out["seagrass_biomes"]:
        raise AuditError("OCEAN.md's seagrass row no longer says 'except frozen'; the region rule needs re-reading")
    return out


def _num(pat, rules, rid):
    for r in rules:
        m = re.search(pat, r)
        if m:
            return int(m.group(1))
    raise AuditError("data/regions.json %s: no biome rule matches %r" % (rid, pat))


def region_rules(regions_doc):
    """{id: {'rings', 'reach', and the numbers its biome rules state}} for every marine region with polygons."""
    out = {}
    for r in regions_doc["marine_regions"]:
        if not r.get("polygons"):
            continue
        rules = r["biomes"]["rules"]
        e = {"rings": r["polygons"], "reach": float(r["seabed_plan"]["shelf_width_blocks"])}
        if any(x.startswith("frozen_ocean:") for x in rules):
            e["frozen_north_of_z"] = _num(r"^frozen_ocean: north of z(\d+)", rules, r["id"])
            e["frozen_from_land"] = _num(r"^frozen_ocean: .*?(\d+) or more blocks from land", rules, r["id"])
        if any(x.startswith("deep_frozen_ocean:") for x in rules):
            e["deep_frozen_north_of_z"] = _num(r"^deep_frozen_ocean: north of z(\d+)", rules, r["id"])
            e["deep_frozen_at_or_below_y"] = _num(r"^deep_frozen_ocean: .*at or below y(\d+)", rules, r["id"])
        if any(x.startswith("warm_ocean:") for x in rules):
            e["warm_within"] = _num(r"^warm_ocean: shelf within (\d+) blocks of land", rules, r["id"])
            # a deep variant listed BEFORE warm_ocean takes its columns first (the rules read in order)
            deep = [x for x in rules[:[i for i, x in enumerate(rules) if x.startswith("warm_ocean:")][0]]
                    if x.startswith("deep_")]
            e["warm_deeper_than_y"] = _num(r"at or below y(\d+)", deep, r["id"]) if deep else None
        out[r["id"]] = e
    return out


# ------------------------------------------------------------------------------------------- geometry


def points_in_rings(rings, xs, zs):
    """Even-odd point-in-polygon for arrays of columns (the column's corner, as tools/water_life_replay.raster_polygons
    and tools/water_mask.in_polygons read it)."""
    inside = np.zeros(len(xs), bool)
    for ring in rings:
        P = np.asarray(ring, float)
        Q = np.roll(P, 1, axis=0)
        for (xi, zi), (xj, zj) in zip(P, Q):
            sel = (zi > zs) != (zj > zs)
            if not sel.any():
                continue
            xc = (xj - xi) * (zs[sel] - zi) / (zj - zi) + xi
            hit = np.zeros(len(xs), bool)
            hit[np.nonzero(sel)[0][xc > xs[sel]]] = True
            inside ^= hit
    return inside


def dist_to_rings(rings, xs, zs):
    best = np.full(len(xs), np.inf)
    for ring in rings:
        P = np.asarray(ring, float)
        Q = np.roll(P, -1, axis=0)
        for (ax, az), (bx, bz) in zip(P, Q):
            dx, dz = bx - ax, bz - az
            L2 = dx * dx + dz * dz
            t = np.zeros(len(xs)) if L2 == 0 else np.clip(((xs - ax) * dx + (zs - az) * dz) / L2, 0, 1)
            best = np.minimum(best, np.hypot(xs - (ax + t * dx), zs - (az + t * dz)))
    return best


def seg_dists(xs, zs, a, b):
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = np.zeros(len(xs)) if L2 == 0 else np.clip(((xs - ax) * dx + (zs - az) * dz) / L2, 0, 1)
    return np.hypot(xs - (ax + t * dx), zs - (az + t * dz))


class LandIndex:
    """Exact 'is there a land column within Euclidean r' over a ground raster, by a summed-area table: a Chebyshev box
    settles most columns, the rest are tested row by row across the disc (an exact integer disc)."""

    def __init__(self, land):
        self.land = land
        self.N = land.shape[0]
        self.M = land.shape[1]
        S = np.zeros((self.N + 1, self.M + 1), np.int32)
        np.cumsum(land, axis=0, dtype=np.int32, out=S[1:, 1:])
        np.cumsum(S[1:, 1:], axis=1, dtype=np.int32, out=S[1:, 1:])
        self.S = S

    def _count(self, z0, z1, x0, x1):
        """land in rows [z0, z1) and columns [x0, x1), all arrays, clipped to the raster."""
        z0 = np.clip(z0, 0, self.N)
        z1 = np.clip(z1, 0, self.N)
        x0 = np.clip(x0, 0, self.M)
        x1 = np.clip(x1, 0, self.M)
        S = self.S
        return S[z1, x1] - S[z0, x1] - S[z1, x0] + S[z0, x0]

    def within(self, xs, zs, r2):
        """bool per column: a land column (dx, dz) away with dx*dx + dz*dz <= r2 exists."""
        xs = np.asarray(xs, np.int64)
        zs = np.asarray(zs, np.int64)
        out = np.zeros(len(xs), bool)
        if not len(xs):
            return out
        R = int(math.isqrt(int(r2)))
        inner = int(math.isqrt(int(r2) // 2))       # a square of half-side inner lies wholly inside the disc
        sure = self._count(zs - inner, zs + inner + 1, xs - inner, xs + inner + 1) > 0
        out |= sure
        maybe = ~sure & (self._count(zs - R, zs + R + 1, xs - R, xs + R + 1) > 0)
        idx = np.nonzero(maybe)[0]
        if len(idx):
            x, z = xs[idx], zs[idx]
            hit = np.zeros(len(idx), bool)
            for dz in range(-R, R + 1):
                w = int(math.isqrt(int(r2) - dz * dz))
                hit |= self._count(z + dz, z + dz + 1, x - w, x + w + 1) > 0
            out[idx] = hit
        return out

    def distance(self, x, z, cap):
        """The exact Euclidean distance from (x, z) to the nearest land column, or None if none lies within cap."""
        x0, x1 = max(0, x - cap), min(self.M, x + cap + 1)
        z0, z1 = max(0, z - cap), min(self.N, z + cap + 1)
        zz, xx = np.nonzero(self.land[z0:z1, x0:x1])
        if not len(zz):
            return None
        d = float(np.sqrt((((xx + x0 - x) ** 2) + ((zz + z0 - z) ** 2)).min()))
        return d if d <= cap else None

    def worst(self, xs, zs, cap, largest, k=400):
        """Over (at most k of) the columns, the largest (or smallest) exact distance to land: how far a rule is
        broken by, measured."""
        ds = [self.distance(int(a), int(b), cap) for a, b in list(zip(xs, zs))[:k]]
        ds = [d for d in ds if d is not None]
        if not ds:
            return None
        return round(max(ds) if largest else min(ds), 2)


def dilate(mask, r):
    out = mask.copy()
    for axis in (0, 1):
        cur = out.copy()
        for k in range(1, r + 1):
            if axis == 0:
                cur[k:, :] |= out[:-k, :]
                cur[:-k, :] |= out[k:, :]
            else:
                cur[:, k:] |= out[:, :-k]
                cur[:, :-k] |= out[:, k:]
        out = cur
    return out


# ------------------------------------------------------------------------------------------- the environment


class Env:
    """Everything the audit compares the pack against. `ground` is the rounded heightmap as an (N, N) int array,
    indexed [z, x] from (0, 0); `lakes` [(level, rings, box)]; `towns` / `keep_out` [(label, box)]; `lanes`
    [(label, pts, half)]; `gates` [(id, a, b)] with `gate_clearance`; `sea_life_cols` an (N, N) bool raster or None;
    `coasts` [(id, box)] with `coast_reach`; `reef` (cx, cz, R) or None; `foreign` {pack: pack_columns() or None}."""

    def __init__(self, ground, sea, bands, regions, region_order, lakes=(), towns=(), keep_out=(), lanes=(), gates=(),
                 gate_clearance=0, sea_life_cols=None, sea_life_margin=3, coasts=(), coast_reach=0, reef=None,
                 foreign=None, spawn_blocks=(), policy=None, kelp_top_below=3):
        self.ground = ground
        self.N = ground.shape[0]
        self.sea = int(sea)
        self.bands = bands
        self.regions = regions
        self.order = [r for r in region_order if r in regions] + [r for r in regions if r not in region_order]
        self.lakes = list(lakes)
        self.towns, self.keep_out, self.lanes = list(towns), list(keep_out), list(lanes)
        self.gates, self.gate_clearance = list(gates), float(gate_clearance)
        self.sea_life_cols = sea_life_cols
        self.sea_life_margin = int(sea_life_margin)
        self.coasts, self.coast_reach = list(coasts), int(coast_reach)
        self.reef = reef
        self.foreign = foreign or {}
        self.spawn_blocks = set(spawn_blocks)
        self.policy = policy or {"whitelist": []}
        self.kelp_top_below = int(kelp_top_below)
        self._land = None

    @property
    def land(self):
        if self._land is None:
            self._land = LandIndex(self.ground >= self.sea)
        return self._land


def gate_points(shape):
    """([(id, a, b)], [id]) the gate crossings of data/water_shape.json whose endpoints the data STATES (kind
    'points'), and the ids of those whose endpoints are derived (shortest, to_town). The derived ones are not checked:
    tools/water_shape.py derives them on the water export's INPUT heightmap, and sea_life_audit's re-derivation on the
    canonical one puts northgate_shortest at (5657, 1598)-(4730, 379), a different line from the builder's; a check
    on it would report the derivations' disagreement, not the pack."""
    stated, derived = [], []
    for c in shape["crossings"]:
        if not (c.get("require_after") or {}).get("gate"):
            continue
        if c["kind"] == "points":
            stated.append((c["id"], tuple(c["from"]), tuple(c["to"])))
        else:
            derived.append(c["id"])
    return stated, derived


def load_env(source_root=None):
    import sea_life_audit as SLA
    ctx = SLA.load_ctx(source_root, with_gates=False)
    g = ctx.t.g
    if (g.ox, g.oz) != (0, 0):
        raise AuditError("the heightmap's origin is not (0, 0); this audit indexes ground from there")
    ground = np.round(g.heights).astype(np.int16)
    sea = ctx.sea
    bands = ocean_bands((ROOT / "docs" / "world-building" / "OCEAN.md").read_text(encoding="utf-8"))
    regions = region_rules(R.load("regions.json"))
    order = R.load("sea_life.json")["finds"]["region_order"]
    lakes = []
    for k, b in ctx.t.bodies.items():
        lakes.append((b["level"], b["rings"], b["box"]))
    floor = R.load("sea_floor.json")
    own = floor["ownership"]
    sl_spec = R.load("sea_life.json")
    shape = R.load("water_shape.json")
    boxes = {f["id"]: f["box"] for f in shape["coasts"]["flats"]}
    boxes.update({s["id"]: s["box"] for s in shape["coasts"]["skerries"]})
    coasts = [(c["id"], boxes[c["id"]]) for c in sl_spec["shore"]["coasts"]]
    rr = shape["coasts"]["relic_reef"]
    reef = (float(rr["centre"][0]), float(rr["centre"][1]),
            float(max(rr["outer_radius"]) + rr["drop_width_blocks"] + own["reef_margin_blocks"]))
    slc = R.pack_columns(SEA_LIFE_PACK)
    sl_cols = None
    if slc is not None:
        sl_cols = np.zeros(ground.shape, bool)
        for (x, z) in slc:
            if 0 <= x < ground.shape[1] and 0 <= z < ground.shape[0]:
                sl_cols[z, x] = True
    foreign = dict(ctx.foreign)
    foreign["cobblers_sea_life"] = slc
    spawn = set(R.load("spawn_blocks.json")["blocks"])
    stated, derived = gate_points(shape)
    e = Env(ground, sea, bands, regions, order, lakes, ctx.towns, ctx.keep_out, ctx.lanes, stated,
            shape["coasts"]["gate_line_clearance_blocks"], sl_cols, own["sea_life_margin_blocks"], coasts,
            sl_spec["shore"]["kelp"]["from_land_blocks"], reef, foreign, spawn, R.load("spawn_block_policy.json"), 3)
    e.gates_derived = derived
    return e


# ------------------------------------------------------------------------------------------- the pack


def parse_pack(fn_dir, P):
    """(fills as an (F, 6) int array, block strings per fill, per-function forceload results). Problems go to P."""
    fn_dir = Path(fn_dir)
    idx = fn_dir / "index.txt"
    if not idx.is_file():
        P["parse"].append("no index.txt in %s" % fn_dir)
        return np.zeros((0, 6), np.int64), [], {}
    names = [n.strip() for n in idx.read_text(encoding="utf-8").splitlines() if n.strip()]
    on_disk = {f.stem for f in fn_dir.glob("*.mcfunction")}
    for n in sorted(on_disk - set(names)):
        P["parse"].append("%s.mcfunction is on disk but not in index.txt: it never runs" % n)
    for n in sorted(set(names) - on_disk):
        P["parse"].append("index.txt lists %s, which is not on disk" % n)
    if len(names) != len(set(names)):
        P["parse"].append("index.txt lists a function twice")
    boxes, blocks = [], []
    fl = {"functions": 0, "chunks_added": 0}
    every = set()
    for n in names:
        f = fn_dir / (n + ".mcfunction")
        if not f.is_file():
            continue
        fl["functions"] += 1
        lines = f.read_text(encoding="utf-8").splitlines()
        for pr in FL.check_lines(lines, n)[:3]:
            P["limits"].append(str(pr))
        added, removed, loaded = [], [], set()
        for no, ln in enumerate(lines, 1):
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            m = FORCELOAD.match(s)
            if m:
                a = [int(v) for v in m.groups()[1:] if v is not None]
                if len(a) == 2:
                    a = a + a
                rect = (min(a[0], a[2]) >> 4, min(a[1], a[3]) >> 4, max(a[0], a[2]) >> 4, max(a[1], a[3]) >> 4)
                if m.group(1) == "add":
                    added.append(rect)
                    for cx in range(rect[0], rect[2] + 1):
                        for cz in range(rect[1], rect[3] + 1):
                            loaded.add((cx, cz))
                else:
                    removed.append(rect)
                continue
            m = FILL.match(s)
            if not m:
                P["parse"].append("%s:%d is neither a fill nor a forceload: %s" % (n, no, s[:80]))
                continue
            x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
            blk, mode, flt = m.group(7), m.group(8), m.group(9)
            if mode != "replace" or flt != WATER:
                P["water"].append("%s:%d does not end `replace %s`: %s" % (n, no, WATER, s[:80]))
                continue
            for cx in range(min(x0, x1) >> 4, (max(x0, x1) >> 4) + 1):
                for cz in range(min(z0, z1) >> 4, (max(z0, z1) >> 4) + 1):
                    if (cx, cz) not in loaded:
                        P["forceload"].append("%s:%d writes chunk %s before it is force-loaded" % (n, no, (cx, cz)))
            boxes.append((min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1)))
            blocks.append(blk)
        if sorted(added) != sorted(removed):
            P["forceload"].append("%s: forceload add %d rects, remove %d, not the same set" % (n, len(added),
                                                                                              len(removed)))
        fl["chunks_added"] += len(loaded)
        every |= loaded
    fl["chunks_unique"] = len(every)
    return np.asarray(boxes, np.int64).reshape(-1, 6), blocks, fl


def expand(boxes, codes):
    """(x, y, z, code) per cell of every fill."""
    if not len(boxes):
        e = np.zeros(0, np.int64)
        return e, e, e, e
    wx = boxes[:, 3] - boxes[:, 0] + 1
    wy = boxes[:, 4] - boxes[:, 1] + 1
    wz = boxes[:, 5] - boxes[:, 2] + 1
    n = wx * wy * wz
    fi = np.repeat(np.arange(len(boxes)), n)
    starts = np.concatenate([[0], np.cumsum(n)[:-1]])
    k = np.arange(int(n.sum())) - starts[fi]
    x = boxes[fi, 0] + k % wx[fi]
    rem = k // wx[fi]
    y = boxes[fi, 1] + rem % wy[fi]
    z = boxes[fi, 2] + rem // wy[fi]
    return x, y, z, codes[fi]


def _ex(xs, zs, sel, k=1):
    i = np.nonzero(sel)[0][:k]
    return ", ".join("(%d, %d)" % (int(xs[j]), int(zs[j])) for j in i)


# ------------------------------------------------------------------------------------------- the checks


def audit(env, pack=PACK):
    P = {k: [] for k in CHECKS}
    res = {}
    boxes, blocks, fl = parse_pack(Path(pack).joinpath(*FN), P)
    res["functions"] = fl.get("functions", 0)
    res["commands"] = len(blocks)
    res["forceloaded_chunks"] = fl.get("chunks_added", 0)      # summed per function: a chunk two functions load
    res["forceloaded_chunks_unique"] = fl.get("chunks_unique", 0)
    uniq = sorted(set(blocks))
    for b in uniq:
        if b not in KINDS:
            P["blocks"].append("%s is written (%d fills): only kelp_plant, kelp[age=25], seagrass and tall_seagrass "
                               "halves are expected" % (b, blocks.count(b)))
    # policy: base ids against the spawn-condition list
    base = {R.bid(b) for b in uniq}
    white = {bk for w in env.policy.get("whitelist") or [] if "sea_floor" in (w.get("scope") or "")
             for bk in w.get("blocks") or []}
    for bk in sorted((base & env.spawn_blocks) - white):
        P["policy"].append("%s is a spawn condition (data/spawn_blocks.json) and no data/spawn_block_policy.json entry "
                           "scoped to sea_floor allows it" % bk)
    codes = np.asarray([KINDS.get(b, 0) for b in blocks], np.int64)
    x, y, z, c = expand(boxes, codes)
    res["cells"] = int(len(x))
    N, sea = env.N, env.sea
    oob = (x < 0) | (z < 0) | (x >= N) | (z >= N)
    if oob.any():
        P["water"].append("%d cells outside the heightmap, e.g. %s" % (int(oob.sum()), _ex(x, z, oob)))
        x, y, z, c = x[~oob], y[~oob], z[~oob], c[~oob]
    # cells: no cell twice
    key = (z * N + x) * 1024 + (y + 512)
    order = np.argsort(key, kind="stable")
    x, y, z, c, key = x[order], y[order], z[order], c[order], key[order]
    dup = np.zeros(len(key), bool)
    dup[1:] = key[1:] == key[:-1]
    if dup.any():
        P["cells"].append("%d cells written twice (the second `replace minecraft:water` finds no water), e.g. %s"
                          % (int(dup.sum()), _ex(x, z, dup)))
    g = env.ground[z, x].astype(np.int64)
    # water: a sea column, above ground, below the sea level
    bad = (y <= g) | (y >= sea)
    if bad.any():
        P["water"].append("%d cells are not water in the heightmap world (at or under ground, or at or above sea "
                          "level y%d), e.g. %s" % (int(bad.sum()), sea, _ex(x, z, bad)))
    # columns
    col = z * N + x
    starts = np.nonzero(np.r_[True, col[1:] != col[:-1]])[0] if len(col) else np.zeros(0, np.int64)
    ends = np.r_[starts[1:], len(col)] if len(starts) else np.zeros(0, np.int64)
    cnt = ends - starts
    cx, cz, cg = x[starts], z[starts], g[starts]
    ymin = y[starts]
    ymax = y[ends - 1]
    top = c[ends - 1]
    nk = {k: (np.add.reduceat((c == k).astype(np.int64), starts) if len(starts) else np.zeros(0, np.int64))
          for k in (K_STEM, K_TOP, K_GRASS, K_TL, K_TU)}
    kelp = (nk[K_TOP] == 1) & (top == K_TOP) & (nk[K_STEM] == cnt - 1)
    grass = (cnt == 1) & (top == K_GRASS)
    tall = (cnt == 2) & (nk[K_TL] == 1) & (top == K_TU)
    shape_bad = ~(kelp | grass | tall) | (ymax - ymin + 1 != cnt)
    if shape_bad.any():
        P["seabed"].append("%d columns are not one whole plant (kelp stems under an age-25 head, a seagrass, or a "
                           "tall seagrass's two halves in order), e.g. %s" % (int(shape_bad.sum()),
                                                                             _ex(cx, cz, shape_bad)))
    floating = ymin != cg + 1
    if floating.any():
        P["seabed"].append("%d columns do not stand on their ground (lowest cell not at ground + 1), e.g. %s"
                           % (int(floating.sum()), _ex(cx, cz, floating)))
    # lakes: a column in a basin under its level is lake water, not sea
    inlake = np.zeros(len(cx), bool)
    for level, rings, (bx0, bz0, bx1, bz1) in env.lakes:
        sel = (cx >= bx0) & (cx <= bx1) & (cz >= bz0) & (cz <= bz1) & (cg < level)
        if sel.any():
            i = np.nonzero(sel)[0]
            inlake[i[points_in_rings(rings, cx[i].astype(float), cz[i].astype(float))]] = True
    if inlake.any():
        P["water"].append("%d columns are in a lake basin, not the sea, e.g. %s" % (int(inlake.sum()),
                                                                                  _ex(cx, cz, inlake)))
    # bands
    kb, gb = env.bands["kelp"], env.bands["seagrass"]
    kout = kelp & ((cg < kb[0]) | (cg > kb[1]))
    if kout.any():
        P["bands"].append("%d kelp columns on ground outside OCEAN.md's y%d-%d, e.g. %s"
                          % (int(kout.sum()), kb[0], kb[1], _ex(cx, cz, kout)))
    gout = (grass | tall) & ((cg < gb[0]) | (cg > gb[1]))
    if gout.any():
        P["bands"].append("%d seagrass columns on ground outside OCEAN.md's y%d-%d, e.g. %s"
                          % (int(gout.sum()), gb[0], gb[1], _ex(cx, cz, gout)))
    tmax = sea - env.kelp_top_below
    high = kelp & (ymax > tmax)
    if high.any():
        P["bands"].append("%d kelp tops above y%d (within %d of the surface), e.g. %s"
                          % (int(high.sum()), tmax, env.kelp_top_below - 1, _ex(cx, cz, high)))
    res["kelp_columns"] = int(kelp.sum())
    res["seagrass_columns"] = int((grass | tall).sum())
    res["tall_seagrass"] = int(tall.sum())
    res["kelp_top_highest"] = int(ymax[kelp].max()) if kelp.any() else None
    res["kelp_ground_range"] = [int(cg[kelp].min()), int(cg[kelp].max())] if kelp.any() else None
    res["seagrass_ground_range"] = [int(cg[grass | tall].min()), int(cg[grass | tall].max())] \
        if (grass | tall).any() else None
    flora = kelp | grass | tall
    res["regions"] = check_regions(env, P, cx, cz, cg, kelp, flora)
    res["clear"] = check_clear(env, P, cx, cz, grass | tall)
    res["owned"] = check_owned(env, P, cx, cz, x, y, z)
    res["problems"] = P
    return res


def labels(env, cx, cz):
    """Region index into env.order per column: the first polygon in order that holds it, else the nearest."""
    lab = np.full(len(cx), -1, np.int64)
    fx, fz = cx.astype(float), cz.astype(float)
    for i, rid in enumerate(env.order):
        free = np.nonzero(lab < 0)[0]
        if not len(free):
            break
        inside = points_in_rings(env.regions[rid]["rings"], fx[free], fz[free])
        lab[free[inside]] = i
    rest = np.nonzero(lab < 0)[0]
    nearest = np.zeros(len(cx), bool)
    if len(rest):
        d = np.stack([dist_to_rings(env.regions[rid]["rings"], fx[rest], fz[rest]) for rid in env.order])
        lab[rest] = np.argmin(d, axis=0)
        nearest[rest] = True
    return lab, nearest


def check_regions(env, P, cx, cz, cg, kelp, flora):
    lab, nearest = labels(env, cx, cz)
    out = {}
    for i, rid in enumerate(env.order):
        ru = env.regions[rid]
        sel = flora & (lab == i)
        out[rid] = {"kelp_columns": int((kelp & (lab == i)).sum()), "seagrass_columns": int((sel & ~kelp).sum()),
                    "by_nearest_polygon": int((sel & nearest).sum())}
        idx = np.nonzero(sel)[0]
        if not len(idx):
            P["regions"].append("%s: no flora at all" % rid)
            continue
        X, Z, G, K = cx[idx], cz[idx], cg[idx], kelp[idx]
        # the shelf: every column within the region's shelf width of land
        r = int(ru["reach"])
        far = ~env.land.within(X, Z, r * r)
        if far.any():
            P["regions"].append("%s: %d flora columns farther than its shelf width %d from land, e.g. %s"
                                % (rid, int(far.sum()), r, _ex(X, Z, far)))
        out[rid]["beyond_shelf"] = int(far.sum())
        if far.any():
            out[rid]["beyond_shelf_farthest"] = env.land.worst(X[far], Z[far], r + 64, largest=True)
        if "deep_frozen_north_of_z" in ru:
            df = (Z < ru["deep_frozen_north_of_z"]) & (G <= ru["deep_frozen_at_or_below_y"])
            out[rid]["in_deep_frozen_ocean"] = int(df.sum())
            if df.any():
                P["regions"].append("%s: %d flora columns where its rules make deep_frozen_ocean (north of z%d, "
                                    "seabed at or below y%d; OCEAN.md: kelp 'not warm or frozen'), e.g. %s"
                                    % (rid, int(df.sum()), ru["deep_frozen_north_of_z"],
                                       ru["deep_frozen_at_or_below_y"], _ex(X, Z, df)))
        if "frozen_north_of_z" in ru:
            north = np.nonzero(Z < ru["frozen_north_of_z"])[0]
            f = ru["frozen_from_land"]
            fr = np.zeros(len(X), bool)
            # 'f or more blocks from land': no land strictly nearer than f, i.e. none with d*d <= f*f - 1
            fr[north] = ~env.land.within(X[north], Z[north], f * f - 1)
            fr &= ~((Z < ru.get("deep_frozen_north_of_z", -10 ** 9)) & (G <= ru.get("deep_frozen_at_or_below_y", -1)))
            out[rid]["in_frozen_ocean"] = int(fr.sum())
            if fr.any():
                out[rid]["in_frozen_ocean_farthest"] = env.land.worst(X[fr], Z[fr], f + 64, largest=True)
            if fr.any():
                P["regions"].append("%s: %d flora columns in frozen_ocean (north of z%d, %d or more from land), e.g. %s"
                                    % (rid, int(fr.sum()), ru["frozen_north_of_z"], f, _ex(X, Z, fr)))
        if "warm_within" in ru:
            w = ru["warm_within"]
            cand = K.copy()
            if ru.get("warm_deeper_than_y") is not None:
                cand &= G > ru["warm_deeper_than_y"]
            ci = np.nonzero(cand)[0]
            warm = np.zeros(len(X), bool)
            warm[ci] = env.land.within(X[ci], Z[ci], w * w)
            out[rid]["kelp_in_warm_ocean"] = int(warm.sum())
            if warm.any():
                out[rid]["kelp_in_warm_ocean_nearest"] = env.land.worst(X[warm], Z[warm], w, largest=False)
            if warm.any():
                P["regions"].append("%s: %d kelp columns in warm_ocean (within %d of land; OCEAN.md: no kelp in warm), "
                                    "e.g. %s" % (rid, int(warm.sum()), w, _ex(X, Z, warm)))
    return out


def _cols_raster(env, cx, cz):
    m = np.zeros((env.N, env.N), bool)
    m[cz, cx] = True
    return m


def _box_hits(cx, cz, box):
    x0, z0, x1, z1 = box
    return (cx >= x0) & (cx <= x1) & (cz >= z0) & (cz <= z1)


def _lane_hits(cx, cz, pts, half):
    hit = np.zeros(len(cx), bool)
    h = int(math.ceil(half))
    for a, b in zip(pts[:-1], pts[1:]):
        sel = _box_hits(cx, cz, (min(a[0], b[0]) - h, min(a[1], b[1]) - h, max(a[0], b[0]) + h, max(a[1], b[1]) + h))
        i = np.nonzero(sel & ~hit)[0]
        if len(i):
            hit[i[seg_dists(cx[i].astype(float), cz[i].astype(float), a, b) <= half]] = True
    return hit


def check_clear(env, P, cx, cz, grass):
    out = {}
    for label, box in [("town %s" % t, b) for t, b in env.towns] + list(env.keep_out):
        h = _box_hits(cx, cz, box)
        if h.any():
            P["clear"].append("%d columns in %s, e.g. %s" % (int(h.sum()), label, _ex(cx, cz, h)))
    for label, pts, half in env.lanes:
        h = _lane_hits(cx, cz, [tuple(p) for p in pts], half)
        if h.any():
            P["clear"].append("%d columns in %s (%g either side), e.g. %s" % (int(h.sum()), label, half,
                                                                            _ex(cx, cz, h)))
    gated = np.zeros(len(cx), bool)
    missing = []
    for gid, a, b in env.gates:
        if a is None:
            missing.append(gid)
            continue
        gated |= _lane_hits(cx, cz, [tuple(a), tuple(b)], env.gate_clearance)
    out["gate_lines_not_modelled"] = missing + list(getattr(env, "gates_derived", []))
    out["kelp_columns_in_gate_clearance"] = int((gated & ~grass).sum())
    gg = gated & grass
    if gg.any():
        P["clear"].append("%d seagrass columns inside a gate crossing's clearance (%g), e.g. %s"
                          % (int(gg.sum()), env.gate_clearance, _ex(cx, cz, gg)))
    out["boxes_checked"] = len(env.towns) + len(env.keep_out)
    out["lanes_checked"] = len(env.lanes)
    out["gates_checked"] = len(env.gates) - len(missing)
    return out


def check_owned(env, P, cx, cz, x, y, z):
    out = {}
    if env.sea_life_cols is None:
        P["owned"].append("build/datapacks/cobblers_sea_life is absent: the margin round its writes cannot be checked")
    else:
        near = dilate(env.sea_life_cols, env.sea_life_margin)
        h = near[cz, cx]
        out["within_margin_of_sea_life"] = int(h.sum())
        if h.any():
            P["owned"].append("%d columns within %d (Chebyshev) of a column cobblers_sea_life writes, e.g. %s"
                              % (int(h.sum()), env.sea_life_margin, _ex(cx, cz, h)))
        del near
    inbox = np.zeros(len(cx), bool)
    for cid, box in env.coasts:
        inbox |= _box_hits(cx, cz, tuple(box))          # inclusive of the far edge: the stricter reading
    i = np.nonzero(inbox)[0]
    r = env.coast_reach
    near = np.zeros(len(cx), bool)
    near[i] = env.land.within(cx[i], cz[i], r * r)
    out["in_sea_life_coast_boxes"] = int(inbox.sum())
    if near.any():
        P["owned"].append("%d columns in a coast cobblers_sea_life dresses, within its kelp reach %d of land, e.g. %s"
                          % (int(near.sum()), r, _ex(cx, cz, near)))
    if env.reef:
        rx, rz, R_ = env.reef
        h = np.hypot(cx - rx, cz - rz) <= R_
        if h.any():
            P["owned"].append("%d columns inside the Relic reef disc (r %g), e.g. %s" % (int(h.sum()), R_,
                                                                                       _ex(cx, cz, h)))
        out["nearest_to_reef_centre"] = round(float(np.hypot(cx - rx, cz - rz).min()), 1) if len(cx) else None
    fres = {}
    for name, cols in sorted(env.foreign.items()):
        if cols is None:
            fres[name] = "absent: not checked"
            continue
        shared_cols = 0
        shared_cells = 0
        ex = None
        theirs = np.zeros((env.N, env.N), bool)
        for (fx, fz) in cols:
            if 0 <= fx < env.N and 0 <= fz < env.N:
                theirs[fz, fx] = True
        sel = np.nonzero(theirs[z, x])[0]
        del theirs
        ours = {}
        for xx, yy, zz in zip(x[sel].tolist(), y[sel].tolist(), z[sel].tolist()):
            ours.setdefault((xx, zz), []).append(yy)
        for k, ys in ours.items():
            shared_cols += 1
            for (y0, y1, _b) in cols[k]:
                hit = [v for v in ys if y0 <= v <= y1]
                if hit:
                    shared_cells += len(hit)
                    ex = ex or (k[0], hit[0], k[1])
        fres[name] = {"shared_columns": shared_cols, "shared_cells": shared_cells}
        if shared_cells:
            P["owned"].append("%d cells %s also writes, e.g. %s" % (shared_cells, name, ex))
    out["foreign"] = fres
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=None)
    p.add_argument("--pack", default=str(PACK))
    p.add_argument("--out", default=str(OUT))
    a = p.parse_args(argv)
    t0 = time.time()
    env = load_env(a.source_root)
    res = audit(env, Path(a.pack))
    res["seconds"] = round(time.time() - t0, 1)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, indent=1, default=str) + "\n")
    probs = [(k, v) for k, lst in res["problems"].items() for v in lst]
    print(json.dumps({k: v for k, v in res.items() if k != "problems"}, default=str)[:2500])
    for k, v in probs[:60]:
        print("PROBLEM [%s] %s" % (k, v))
    print("%d problems -> %s" % (len(probs), out))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
