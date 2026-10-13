#!/usr/bin/env python
"""Independent audit of the Scar Tarn (data/scar_tarn.json, pack cobblers_scar_tarn, step R9ST).

Written by an agent that built none of it. It imports NOTHING from tools/scar_tarn.py and calls none of its functions:
the pack is read as the text the server would run (`build.mcfunction`), the ground is the canonical heightmap
(tools/ground.py, rounded), and every rule below is this file's own.

  water     REPLAY the emitted function over a world made of the heightmap alone (round(h) and everything under it
            solid, air above), with the unwritten ground 0, 1 and 2 blocks under the heightmap. Each write honours
            its mode (keep = only into air, `replace <block>` = only over that block) and must land in a chunk a
            preceding `forceload add` holds. Gravel and sand then fall. Every water block must have water or a
            HOLDING block on its four sides and below; a water block that does not is a LEAK, and the water is then
            FLOWED (vanilla's shape, over-approximated: down first, sideways up to 7 from a source or a landing, a source
            also spreading sideways over a drop) to say how far it goes and whether it leaves the record's window.
            The pond itself, drop 0: a flood of the heightmap from the record's seed at its water level (4-connected,
            ground <= level - 1) must equal the water columns the replay leaves, with water from the bed to the level in
            every one (a trunk or anything else standing in the water fails here); no water above the level; the
            hollow's own spill at least SPILL_MARGIN over the water; every rim column holding at bank_lift_to.
  wards     each scar_tarn_* Habitat Block (data/habitat_blocks.json) stands on its mimic in the replayed world; a
            water ward has water over it, a land ward two passable cells.
  alphas    each pool's entries (data/spawns.json entries and habitats, or a `scar_tarn.py records` dump): the species
            is an implemented species file in the Cobblemon 1.8.0 jar; the band is not under the level its
            pre-evolution evolves into it at, not over its own level evolution, and not over the next leg's cap of the
            tier of the sub-region the ward stands in (data/regions.json polygon -> data/spawns.json subregion tier ->
            data/encounter_design.json rules.tiers / rules.hearts.next_cap); `alpha=true` on every entry.
  overlaps  every x/z point, line and box any OTHER data/*.json record authors, measured against the columns the
            function writes: a point or line within rules.authored_clearance, a box a written column falls in; the
            Scar's pad (data/sculpt.json pads the_scar, radius) and every route path (data/route_paths.json) and the
            Scar's streets (data/placements.json settlements.the_scar.plan.streets) never under a written column.

WHAT THIS DOES NOT COVER. Validity is not behaviour. The world is the HEIGHTMAP, not the save: a cave, a carve or a
donor template under the pond, or a live world that predates the Scar's pad (docs/STATE.md 'Pads in the world'), is
not seen here. Leaves, slabs, carpets and plants are counted as passable (stricter than vanilla, which keeps flowing
water out of a waterloggable block). Ice, freezing and the in-game alpha flag and its re-levelling are not checked.

  python tools/scar_tarn_audit.py [--pack DIR] [--records FILE] [--jar JAR] [--source-root DIR] [-v]

Without --pack the generator's CLI builds the pack into a temporary directory (`python tools/scar_tarn.py build
--out TMP`). Exit 1 on any finding, including anything it could not check.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data"
RECORD = DATA / "scar_tarn.json"
FUNCTION = "data/cobblers/function/scar_tarn/build.mcfunction"
JAR_GLOB = "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0*.jar"
DROPS = (0, 1, 2)
GATED_LEAK_DROPS = (0, 1)
# SCAR_TARN.md 'the two-block spill margin': the hollow must hold water two blocks over the level, so a column the
# export left one block low (tools/ground.py: round(h) or one low at water edges) still keeps one.
SPILL_MARGIN = 2
SPREAD = 7          # vanilla water: a source or a landing spreads 7 blocks on the flat
MARGIN = 96         # heightmap read round the record's window, for the flow
FLOW_CAP = 200_000

AIR = "minecraft:air"
WATER = "minecraft:water"
GROUND = "audit:ground"     # an unwritten cell under the (dropped) heightmap
# This audit's own rule, not the generator's: full cubes and logs HOLD water; everything else passes it.
HOLDS = {GROUND, "minecraft:stone", "minecraft:dirt", "minecraft:coarse_dirt", "minecraft:podzol", "minecraft:moss_block",
         "minecraft:mud", "minecraft:clay", "minecraft:gravel", "minecraft:sand", "minecraft:cobblestone",
         "minecraft:mossy_cobblestone", "minecraft:stone_bricks", "minecraft:mossy_stone_bricks",
         "minecraft:cracked_stone_bricks", "minecraft:spruce_log", "minecraft:birch_log", "minecraft:oak_log",
         "minecraft:grass_block", "minecraft:snow_block", "minecraft:packed_ice", "minecraft:ice"}
PASSES = {AIR, "minecraft:cave_air", WATER, "minecraft:snow", "minecraft:fern", "minecraft:large_fern",
          "minecraft:short_grass", "minecraft:azalea", "minecraft:moss_carpet", "minecraft:spruce_leaves",
          "minecraft:birch_leaves", "minecraft:mossy_stone_brick_slab"}
FALLS = {"minecraft:gravel", "minecraft:sand"}
D4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

NUM = r"(-?\d+)"
RE_SET = re.compile(r"^setblock %s %s %s (\S+)(?: (keep|replace|destroy))?$" % (NUM, NUM, NUM))
RE_FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)(?: (keep|replace|destroy|hollow|outline)(?: (\S+))?)?$" % ((NUM,) * 6))
RE_FORCE = re.compile(r"^forceload (add|remove) %s %s(?: %s %s)?$" % ((NUM,) * 4))


def base(state):
    return state.split("[")[0].split("{")[0]


def jload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Report:
    def __init__(self):
        self.findings, self.notes = [], []

    def err(self, part, msg):
        self.findings.append("%s: %s" % (part, msg))

    def note(self, part, msg):
        self.notes.append("%s: %s" % (part, msg))


# ------------------------------------------------------------------------------------------------------- the ground
class Heights:
    """Rounded ground Y over an inclusive box; outside it is unknown (the flow treats reaching it as an escape)."""

    def __init__(self, A, x0, z0):
        self.A, self.x0, self.z0 = np.asarray(A, int), int(x0), int(z0)
        self.x1, self.z1 = self.x0 + self.A.shape[1] - 1, self.z0 + self.A.shape[0] - 1

    def has(self, x, z):
        return self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1

    def __call__(self, x, z):
        return int(self.A[z - self.z0, x - self.x0])


def heights_from_heightmap(window, source_root=None, margin=MARGIN):
    import ground
    g = ground.load(source_root)
    x0, z0, x1, z1 = window
    X0, Z0, X1, Z1 = x0 - margin, z0 - margin, x1 + margin, z1 + margin
    return Heights(g.box(X0, Z0, X1, Z1), X0, Z0)


# ------------------------------------------------------------------------------------------------------- the replay
class World:
    """The heightmap world with the function written into it. `drop`: the unwritten ground stands this far under h."""

    def __init__(self, H, drop):
        self.H, self.drop = H, drop
        self.cells = {}
        self.written = set()        # every (x, y, z) a command targeted, whatever it changed
        self.loaded = set()

    def get(self, x, y, z):
        st = self.cells.get((x, y, z))
        if st is not None:
            return st
        if not self.H.has(x, z):
            return None
        return GROUND if y <= self.H(x, z) - self.drop else AIR

    def holds(self, x, y, z):
        st = self.get(x, y, z)
        return st is not None and base(st) in HOLDS


def replay(lines, H, drop, rep=None):
    """The world after the function, then gravity. Returns (world, problems) where problems are lines the replay could
    not run (an unknown command, a write outside a held chunk)."""
    W = World(H, drop)
    probs = []
    unloaded = 0
    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = RE_FORCE.match(line)
        if m:
            op = m.group(1)
            a, b = int(m.group(2)), int(m.group(3))
            c, d = (int(m.group(4)), int(m.group(5))) if m.group(4) is not None else (a, b)
            ch = {(cx, cz) for cx in range(min(a, c) >> 4, (max(a, c) >> 4) + 1)
                  for cz in range(min(b, d) >> 4, (max(b, d) >> 4) + 1)}
            W.loaded = (W.loaded | ch) if op == "add" else (W.loaded - ch)
            continue
        m = RE_SET.match(line)
        if m:
            x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
            box = (x, y, z, x, y, z)
            state, mode, filt = m.group(4), m.group(5) or "replace", None
        else:
            m = RE_FILL.match(line)
            if not m:
                probs.append("line %d: not a command this replay knows: %s" % (n, line[:80]))
                continue
            v = [int(m.group(i)) for i in range(1, 7)]
            box = (min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]), max(v[2], v[5]))
            state, mode, filt = m.group(7), m.group(8) or "replace", m.group(9)
            if mode in ("hollow", "outline"):
                probs.append("line %d: fill mode %s is not replayed" % (n, mode))
                continue
        x0, y0, z0, x1, y1, z1 = box
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if (x >> 4, z >> 4) not in W.loaded:
                    unloaded += 1
                    if unloaded <= 3:
                        probs.append("line %d: writes (%d, %d) in a chunk no preceding forceload add holds" % (n, x, z))
                    continue
                for y in range(y0, y1 + 1):
                    W.written.add((x, y, z))
                    cur = W.get(x, y, z)
                    if cur is None:
                        probs.append("line %d: writes (%d, %d, %d), outside the heightmap read" % (n, x, y, z))
                        continue
                    if mode == "keep" and base(cur) != AIR:
                        continue
                    if filt is not None and base(cur) != base(filt):
                        continue
                    W.cells[(x, y, z)] = state
    if unloaded > 3:
        probs.append("%d writes in all land in chunks no forceload holds" % unloaded)
    settle(W)
    return W, probs


def settle(W):
    """Gravel and sand with a free cell under them fall until they rest (a free cell: anything that does not hold)."""
    for (x, y, z) in sorted([p for p, st in W.cells.items() if base(st) in FALLS], key=lambda p: p[1]):
        st = W.cells.get((x, y, z))
        if st is None or base(st) not in FALLS:
            continue
        yy = y
        while yy - 1 > -64 and not W.holds(x, yy - 1, z) and W.get(x, yy - 1, z) is not None:
            yy -= 1
        if yy != y:
            W.cells[(x, y, z)] = AIR
            W.cells[(x, yy, z)] = st


def water_cells(W):
    return {p for p, st in W.cells.items() if base(st) == WATER}


def open_faces(W, water):
    """[(water cell, open neighbour, 'side'|'floor')]: a neighbour that is neither water nor a holding block."""
    out = []
    for (x, y, z) in sorted(water):
        for dx, dz in D4:
            n = (x + dx, y, z + dz)
            if n not in water and not W.holds(*n):
                out.append(((x, y, z), n, "side"))
        n = (x, y - 1, z)
        if n not in water and not W.holds(*n):
            out.append(((x, y, z), n, "floor"))
    return out


def flow(W, water, window):
    """Where the placed water goes. Over-approximates vanilla: a cell with a free cell under it flows down (a source also
    sideways); a landed cell spreads sideways up to SPREAD. Returns {reached: set of cells outside the placed water,
    falls: reached cells over a free cell, escaped: reached a column outside the window or the heightmap read}."""
    x0, z0, x1, z1 = window
    free = lambda p: (p not in water) and W.get(*p) is not None and not W.holds(*p)
    best = {}
    stack = [(p, 0, True) for p in water]
    reached, falls, escaped, outside = set(), set(), False, set()
    while stack:
        (x, y, z), d, source = stack.pop()
        below = (x, y - 1, z)
        nxt = []
        if free(below):
            nxt.append((below, 0, False))
            if source:
                nxt += [((x + dx, y, z + dz), 1, False) for dx, dz in D4]
        elif d + 1 <= SPREAD:
            nxt += [((x + dx, y, z + dz), d + 1, False) for dx, dz in D4]
        for p, dd, _s in nxt:
            if p in water:
                continue
            if W.get(*p) is None:
                escaped = True
                outside.add(p)
                continue
            if not free(p):
                continue
            if p in best and best[p] <= dd:
                continue
            best[p] = dd
            reached.add(p)
            if not (x0 <= p[0] <= x1 and z0 <= p[2] <= z1):
                escaped = True
                outside.add(p)
            if free((p[0], p[1] - 1, p[2])):
                falls.add(p)
            if len(reached) > FLOW_CAP:
                return {"reached": reached, "falls": falls, "escaped": True, "outside": outside, "capped": True}
            stack.append((p, dd, False))
    return {"reached": reached, "falls": falls, "escaped": escaped, "outside": outside, "capped": False}


# -------------------------------------------------------------------------------------------------------- the pond
def flood(H, seed, level, window):
    """(columns, escaped): 4-connected columns from seed with ground <= level - 1, inside the window."""
    x0, z0, x1, z1 = window
    sx, sz = seed
    if H(sx, sz) > level - 1:
        return set(), False
    seen, st, escaped = {(sx, sz)}, [(sx, sz)], False
    while st:
        x, z = st.pop()
        for dx, dz in D4:
            n = (x + dx, z + dz)
            if n in seen:
                continue
            if not (x0 <= n[0] <= x1 and z0 <= n[1] <= z1):
                escaped = True
                continue
            if H(*n) <= level - 1:
                seen.add(n)
                st.append(n)
    return seen, escaped


def highest_held(H, seed, window, start, top=60):
    """The highest water level the hollow holds from seed without its flood reaching the window's edge."""
    lvl = start
    while lvl < start + top:
        _c, esc = flood(H, seed, lvl + 1, window)
        if esc:
            return lvl
        lvl += 1
    return lvl


def check_water(lines, H, doc, rep, drops=DROPS):
    P = doc["pond"]
    level, seed, window = P["water_level"], tuple(P["seed"]), tuple(P["window"])
    lift = P["bank_lift_to"]
    out = {}
    for drop in drops:
        W, probs = replay(lines, H, drop)
        for p in probs[:6]:
            rep.err("replay drop %d" % drop, p)
        water = water_cells(W)
        if not water:
            rep.err("water", "drop %d: the function leaves no water block at all" % drop)
            continue
        faces = open_faces(W, water)
        fl = flow(W, water, window)
        out[drop] = {"water": len(water), "open_faces": len(faces), "reached": len(fl["reached"]),
                     "falls": len(fl["falls"]), "escaped": fl["escaped"]}
        if faces:
            sample = ", ".join("%s->%s %s" % (a, b, k) for a, b, k in faces[:4])
            msg = ("drop %d: %d water face(s) open, e.g. %s; flowed, the water reaches %d cell(s) outside the placed water, "
                   "%d of them over a free cell, %s" % (drop, len(faces), sample, len(fl["reached"]), len(fl["falls"]),
                                                       "and LEAVES the window" if fl["escaped"] else "inside the window"))
            if fl["reached"]:
                rx = sorted(fl["reached"])
                msg += "; reached x%d..%d y%d..%d z%d..%d" % (
                    min(p[0] for p in rx), max(p[0] for p in rx), min(p[1] for p in rx), max(p[1] for p in rx),
                    min(p[2] for p in rx), max(p[2] for p in rx))
            if drop in GATED_LEAK_DROPS or fl["escaped"] or fl["falls"]:
                rep.err("water", msg)
            else:
                rep.note("water", msg + " (held: no fall, no escape)")
        if drop == 0:
            check_pond(W, water, H, doc, rep)
    return out


def check_pond(W, water, H, doc, rep):
    P = doc["pond"]
    level, seed, window, lift = P["water_level"], tuple(P["seed"]), tuple(P["window"]), P["bank_lift_to"]
    cols, esc = flood(H, seed, level, window)
    if not cols:
        rep.err("pond", "the seed %s (ground y%d) is not under the water level y%d" % (seed, H(*seed), level))
        return
    if esc:
        rep.err("pond", "a flood of the heightmap at y%d from %s reaches the window's edge" % (level, seed))
    held = highest_held(H, seed, window, level)
    if held - level < SPILL_MARGIN:
        rep.err("pond", "the hollow holds water only to y%d: %d block(s) over the level y%d, the margin is %d"
                % (held, held - level, level, SPILL_MARGIN))
    rep.note("pond", "%d columns at y%d; the hollow holds to y%d (margin %d)" % (len(cols), level, held, held - level))
    above = sorted(p for p in water if p[1] > level)
    if above:
        rep.err("pond", "%d water block(s) over the level y%d, e.g. %s" % (len(above), level, above[:3]))
    wcols = {(x, z) for x, _y, z in water}
    extra = sorted(wcols - cols)
    if extra:
        rep.err("pond", "%d water column(s) outside the heightmap's pond, e.g. %s" % (len(extra), extra[:4]))
    gaps = []
    for (x, z) in sorted(cols):
        g = H(x, z)
        for y in range(g + 1, level + 1):
            st = W.get(x, y, z)
            if base(st) != WATER:
                gaps.append((x, y, z, base(st)))
        if not W.holds(x, g, z):
            gaps.append((x, g, z, "bed " + base(W.get(x, g, z))))
    if gaps:
        rep.err("pond", "%d cell(s) of the pond are not water (or the bed does not hold), e.g. %s" % (len(gaps), gaps[:4]))
    rim = sorted({(x + dx, z + dz) for (x, z) in cols for dx, dz in D4} - cols)
    low = [(x, lift, z, base(W.get(x, lift, z))) for (x, z) in rim if not W.holds(x, lift, z)]
    if low:
        rep.err("pond", "%d rim column(s) of %d do not hold at bank_lift_to y%d, e.g. %s" % (len(low), len(rim), lift, low[:4]))


# ------------------------------------------------------------------------------------------------------- the wards
def tarn_wards(habitat_blocks):
    return [b for b in habitat_blocks if str(b.get("id", "")).startswith("scar_tarn_")]


def check_wards(lines, H, wards, rep):
    if not wards:
        rep.err("wards", "no scar_tarn_* Habitat Block record")
        return
    W, _p = replay(lines, H, 0)
    for b in wards:
        p = b.get("position") or {}
        x, y, z = p.get("x"), p.get("y"), p.get("z")
        if None in (x, y, z):
            rep.err("wards", "%s has no position" % b["id"])
            continue
        st = W.get(x, y, z)
        if st is None or base(st) != b.get("mimic"):
            rep.err("wards", "%s at (%d, %d, %d) is %s in the replayed world, its mimic is %s" % (b["id"], x, y, z, st and base(st), b.get("mimic")))
        above = [base(W.get(x, y + k, z) or "?") for k in (1, 2)]
        if "waters" in b.get("pool", ""):
            if above[0] != WATER:
                rep.err("wards", "%s: a water ward with %s over it, not water" % (b["id"], above[0]))
        elif any(a in HOLDS or a == WATER for a in above):
            rep.err("wards", "%s: a land ward with %s over it" % (b["id"], above))


# ------------------------------------------------------------------------------------------------------- the alphas
class Jar:
    def __init__(self, path):
        self.path = path
        z = zipfile.ZipFile(path)
        self.species = {}
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                try:
                    self.species[Path(n).stem] = json.loads(z.read(n))
                except ValueError:
                    continue
        self.into = {}      # species -> [(pre, method, minLevel)]
        for name, d in self.species.items():
            for ev in d.get("evolutions") or []:
                res = str(ev.get("result", "")).split()[0].lower()
                lv = next((r.get("minLevel") for r in ev.get("requirements") or [] if r.get("variant") == "level"), None)
                self.into.setdefault(res, []).append((name, ev.get("variant"), lv))

    def evolves_at(self, name):
        """(min level, how) of this species' own level evolutions, or (None, '')."""
        lvls = [next((r.get("minLevel") for r in ev.get("requirements") or [] if r.get("variant") == "level"), None)
                for ev in self.species[name].get("evolutions") or []]
        lvls = [v for v in lvls if v is not None]
        return (min(lvls), "level") if lvls else (None, "")


def find_jar(arg=None):
    if arg:
        return Path(arg) if Path(arg).exists() else None
    hits = sorted(glob.glob(JAR_GLOB))
    return Path(hits[0]) if hits else None


def point_in_rings(x, z, rings):
    inside = False
    for ring in rings:
        n = len(ring)
        for i in range(n):
            (ax, az), (bx, bz) = ring[i][:2], ring[(i + 1) % n][:2]
            if (az > z) != (bz > z) and x < ax + (z - az) * (bx - ax) / (bz - az):
                inside = not inside
    return inside


def area_tier(x, z, regions, spawns):
    """[(subregion id, tier)] of every sub-region whose rings hold (x, z) and whose spawns.json table names a tier."""
    tiers = {s["id"]: (s.get("level_band") or {}).get("tier") for s in spawns.get("subregions") or []}
    return [(s["id"], tiers.get(s["id"])) for s in regions.get("subregions") or []
            if point_in_rings(x, z, s.get("polygons") or [])]


def parse_level(v):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(v))
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^\s*(\d+)\s*$", str(v))
    return (int(m.group(1)),) * 2 if m else None


def is_alpha(mods):
    for tok in str(mods or "").split():
        k, _, v = tok.partition("=")
        if k.lower() in ("alpha", "is_alpha") and v.lower() in ("true", "yes", ""):
            return True
    return False


def pool_entries(wards, spawns):
    """{pool id: [(source, entry)]} for each ward's pool, from spawns.json entries (scope) and habitats (id)."""
    out = {}
    for b in wards:
        pid = str(b.get("pool", "")).split(":", 1)[-1]
        if pid in out:
            continue
        rows = [("spawns.json entries", e) for e in spawns.get("entries") or [] if e.get("scope") == pid]
        for h in spawns.get("habitats") or []:
            if h.get("id") == pid:
                rows += [("spawns.json habitats", e) for e in h.get("entries") or []]
        out[pid] = rows
    return out


def records_inputs(path):
    """(wards, spawns-shaped dict) from a `scar_tarn.py records` dump."""
    d = jload(path)
    pools = d.get("pools") or []
    return d.get("habitat_blocks") or [], {"entries": [e for p in pools for e in p.get("entries") or []],
                                          "habitats": [p["habitat"] for p in pools if p.get("habitat")]}


def check_alphas(wards, spawns, regions, design, jar, rep):
    if not wards:
        rep.err("alphas", "no scar_tarn_* ward, so no pool to check")
        return
    rules = design["rules"]
    tiers_seen = set()
    for b in wards:
        p = b.get("position") or {}
        hits = area_tier(p.get("x", 0), p.get("z", 0), regions, spawns)
        named = sorted({t for _s, t in hits if t is not None})
        if len(named) != 1:
            rep.err("alphas", "%s at (%s, %s) stands in sub-region(s) %s: not exactly one tier" % (b["id"], p.get("x"), p.get("z"), hits))
            continue
        tiers_seen.add((b["pool"], named[0], ",".join(s for s, _t in hits)))
    pools = pool_entries(wards, spawns)
    for pid, rows in sorted(pools.items()):
        if not rows:
            rep.err("alphas", "pool %s has no entry in data/spawns.json" % pid)
            continue
        tiers = {t for pool, t, _s in tiers_seen if pool.split(":", 1)[-1] == pid}
        if len(tiers) != 1:
            rep.err("alphas", "pool %s: its wards stand at tier(s) %s, not one" % (pid, sorted(tiers)))
            continue
        tier = tiers.pop()
        cap = rules["tiers"][str(tier)]["cap"]
        nxt = rules["hearts"]["next_cap"][str(tier)]
        for src, e in rows:
            sp = str(e.get("pokemon") or e.get("species") or "").lower().split()[0] if (e.get("pokemon") or e.get("species")) else ""
            where = "%s %s %s" % (src, pid, sp or "?")
            if not is_alpha(e.get("modifiers")):
                rep.err("alphas", "%s: modifiers %r carry no alpha=true" % (where, e.get("modifiers")))
            band = parse_level(e.get("level"))
            if band is None:
                rep.err("alphas", "%s: level %r is not a band" % (where, e.get("level")))
                continue
            lo, hi = band
            if lo > hi:
                rep.err("alphas", "%s: level %r is not [low, high]" % (where, e.get("level")))
            if hi > nxt:
                rep.err("alphas", "%s: level %d-%d is over tier %d's next cap %d (cap %d; ENCOUNTER_DESIGN.md section 10: "
                                  "above the cap only to the next leg's cap)" % (where, lo, hi, tier, nxt, cap))
            elif hi > cap:
                rep.note("alphas", "%s: %d-%d, %d level(s) over tier %d's cap %d: uncatchable on this leg "
                                   "(data/level_cap.json), under the next cap %d" % (where, lo, hi, hi - max(lo, cap + 1) + 1, tier, cap, nxt))
            if jar is None:
                continue
            if sp not in jar.species:
                rep.err("alphas", "%s: no species file in the Cobblemon 1.8.0 jar" % where)
                continue
            if jar.species[sp].get("implemented") is False:
                rep.err("alphas", "%s: the jar's species is not implemented" % where)
            for pre, how, lv in jar.into.get(sp, []):
                if lv is not None and lo < lv:
                    rep.err("alphas", "%s: spawns from %d, under the level %d %s evolves into it at" % (where, lo, lv, pre))
            own, _h = jar.evolves_at(sp)
            if own is not None and hi >= own:
                rep.err("alphas", "%s: spawns to %d, at or past its own evolution level %d" % (where, hi, own))


# ------------------------------------------------------------------------------------------------------ overlaps
def written_columns(lines, H):
    W, _p = replay(lines, H, 0)
    return sorted({(x, z) for x, _y, z in W.written})


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _xz(p):
    return isinstance(p, list) and len(p) in (2, 3) and all(_num(v) for v in p) and 0 <= p[0] <= 8192 and 0 <= p[-1] <= 8192


SKIP_FILES = {"scar_tarn.json", "cells.json", "regions.json", "world.json"}   # planning labels, not things
OWN = re.compile(r"scar_tarn")


def authored_geometry(data_dir=DATA):
    """[(file, json path, kind, geometry)]: points (x, z), lines [(x, z), ...] and boxes (x0, z0, x1, z1) that any
    data file other than this place's authors. Records whose path or id names scar_tarn are this place's own."""
    out = []

    def walk(o, path, f):
        if OWN.search(path):
            return
        if isinstance(o, dict):
            if OWN.search(str(o.get("id", ""))) or OWN.search(str(o.get("scope", ""))):
                return
            if _num(o.get("x")) and _num(o.get("z")):
                out.append((f, path, "point", (o["x"], o["z"])))
            for a, b, c, d in (("min_x", "min_z", "max_x", "max_z"), ("x0", "z0", "x1", "z1")):
                if all(_num(o.get(k)) for k in (a, b, c, d)):
                    out.append((f, path, "box", (o[a], o[b], o[c], o[d])))
            for k, v in o.items():
                walk(v, "%s.%s" % (path, k), f)
        elif isinstance(o, list):
            if _xz(o):
                out.append((f, path, "point", (o[0], o[-1])))
                return
            if len(o) >= 2 and all(_xz(p) for p in o):
                out.append((f, path, "line", [(p[0], p[-1]) for p in o]))
                return
            for i, v in enumerate(o):
                walk(v, "%s[%d]" % (path, i), f)

    for fn in sorted(Path(data_dir).glob("*.json")):
        if fn.name in SKIP_FILES:
            continue
        try:
            walk(jload(fn), "", fn.name)
        except ValueError:
            continue
    return out


def _seg_dist(C, a, b):
    """Distance from each column in C (n x 2) to the segment a-b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ab = b - a
    L = float(ab @ ab)
    t = np.zeros(len(C)) if L == 0 else np.clip(((C - a) @ ab) / L, 0, 1)
    P = a + t[:, None] * ab
    return np.hypot(*(C - P).T)


def check_overlaps(cols, doc, rep, data_dir=DATA):
    if not cols:
        rep.err("overlaps", "the function writes no column")
        return
    C = np.asarray(cols, float)
    m = doc["rules"]["authored_clearance"]
    bx0, bz0, bx1, bz1 = C[:, 0].min(), C[:, 1].min(), C[:, 0].max(), C[:, 1].max()
    rep.note("overlaps", "written box x%d..%d z%d..%d, %d columns" % (bx0, bx1, bz0, bz1, len(cols)))
    near_box = lambda x, z, r: bx0 - r <= x <= bx1 + r and bz0 - r <= z <= bz1 + r
    for f, path, kind, geo in authored_geometry(data_dir):
        if kind == "point":
            x, z = geo
            if not near_box(x, z, m):
                continue
            d = float(np.hypot(C[:, 0] - x, C[:, 1] - z).min())
            if d < m:
                rep.err("overlaps", "data/%s%s (%d, %d) is %.0f block(s) from a written column (clearance %d)" % (f, path, x, z, d, m))
        elif kind == "line":
            pts = geo
            if not any(near_box(x, z, m + 400) for x, z in pts):
                continue
            d = min(float(_seg_dist(C, a, b).min()) for a, b in zip(pts, pts[1:]))
            if d < m:
                rep.err("overlaps", "data/%s%s, a line, passes %.0f block(s) from a written column (clearance %d)" % (f, path, d, m))
        else:
            x0, z0, x1, z1 = geo
            if (x1 - x0) * (z1 - z0) > 1024 * 1024:
                continue        # a region-scale bound is a label, not a thing
            if any(list(e["box"]) == [x0, z0, x1, z1] for e in (doc["rules"].get("authored_box_exempt") or [])):
                rep.note("overlaps", "data/%s%s box %s is exempt (rules.authored_box_exempt): checked by the forest rules instead" % (f, path, geo))
                continue
            inside = int(((C[:, 0] >= x0) & (C[:, 0] <= x1) & (C[:, 1] >= z0) & (C[:, 1] <= z1)).sum())
            if inside:
                rep.err("overlaps", "data/%s%s box %s holds %d written column(s)" % (f, path, geo, inside))
            else:
                dx = np.maximum(np.maximum(x0 - C[:, 0], C[:, 0] - x1), 0)
                dz = np.maximum(np.maximum(z0 - C[:, 1], C[:, 1] - z1), 0)
                d = float(np.hypot(dx, dz).min())
                if d < m:
                    rep.note("overlaps", "data/%s%s box %s is %.0f block(s) from a written column (a box, not a thing: "
                                         "named, not failed)" % (f, path, geo, d))


def check_paths(cols, doc, rep, data_dir=DATA, pad_cols=None):
    """The Scar's pad and streets, and every route path: never under a written column. `pad_cols` (default: cols) are the columns
    the pad's radius rule applies to: with growth.arms, the TARN's own function only, because the arms grow in the pad's
    outskirts on purpose (the owner, 2026-10-12: envelop some of the Scar) and check_forest holds them to the city's own geometry."""
    C = np.asarray(cols, float)
    if not len(C):
        return
    sculpt = jload(Path(data_dir) / "sculpt.json")
    towns = jload(Path(data_dir) / "towns.json")
    pad = next((p for p in sculpt.get("pads") or [] if p.get("site") == "the_scar"), None)
    town = next((t for t in towns.get("towns") or [] if t.get("id") == "the_scar"), None)
    if pad is None or town is None:
        rep.err("paths", "no Scar pad (data/sculpt.json pads) or town centre (data/towns.json)")
    else:
        cx, cz = town["centre"]["x"], town["centre"]["z"]
        PC = C if pad_cols is None else (np.asarray(pad_cols, float) if len(pad_cols) else C[:0])
        d = float(np.hypot(PC[:, 0] - cx, PC[:, 1] - cz).min()) if len(PC) else 1e9
        if d <= pad["radius"]:
            rep.err("paths", "a written column is %.0f from the Scar's centre (%d, %d), inside the pad's radius %d" % (d, cx, cz, pad["radius"]))
        if d <= pad["radius"] + pad.get("feather", 0):
            rep.note("paths", "the nearest written column is %.0f from the Scar's centre: inside the pad's feather (%d..%d), "
                              "terrain the live world does not have until the re-export (docs/STATE.md 'Pads in the world')"
                     % (d, pad["radius"], pad["radius"] + pad.get("feather", 0)))
    pl = jload(Path(data_dir) / "placements.json")
    streets = (((pl.get("settlements") or {}).get("the_scar") or {}).get("plan") or {}).get("streets") or []
    if not streets:
        rep.err("paths", "no Scar streets in data/placements.json to check against")
    for s in streets:
        pts = s["polyline"]
        d = min(float(_seg_dist(C, a, b).min()) for a, b in zip(pts, pts[1:]))
        if d <= s.get("width", 1) / 2.0 + 1:
            rep.err("paths", "the Scar's %s passes %.1f from a written column (width %s)" % (s["id"], d, s.get("width")))
        rep.note("paths", "the Scar's %s: nearest written column %.0f" % (s["id"], d))
    rp = jload(Path(data_dir) / "route_paths.json").get("paths") or {}
    if not rp:
        rep.err("paths", "no route paths in data/route_paths.json")
    best = None
    for rid, pts in rp.items():
        P = np.asarray([p[:2] for p in pts], float)
        if not len(P):
            continue
        # nearest route point to the written box first (cheap), then exact against every written column there
        d = float(np.hypot(P[:, 0] - C[:, 0].mean(), P[:, 1] - C[:, 1].mean()).min())
        if best is None or d < best[0]:
            best = (d, rid)
        if d < 400:
            dd = min(float(np.hypot(C[:, 0] - x, C[:, 1] - z).min()) for x, z in P[np.hypot(P[:, 0] - C[:, 0].mean(), P[:, 1] - C[:, 1].mean()) < 400])
            if dd < 1:
                rep.err("paths", "route %s runs under a written column" % rid)
    if best:
        rep.note("paths", "nearest route path: %s, %.0f blocks from the written columns' mean" % (best[1], best[0]))


# ----------------------------------------------------------------------------------------------------------- the forest
# The owner, 2026-10-12: the wood should expand toward the Scar, envelop some of it, and go down the back and side of the
# mountain (data/scar_tarn.json growth.arms: one function each, `arm_<lobe>.mcfunction`). Everything below is this file's
# own derivation, from the emitted functions, the heightmap and the OTHER records' geometry: nothing is read from
# tools/scar_tarn.py.
STREET_MARGIN = 4        # a written column is at least half a street's width + this from its centre line
RUIN_MARGIN = 8          # nothing written within this of a ruin footprint or the plaza
CORE_MARGIN = 3          # the city's core box (the three house-lot bands and their ends) is grown by this
THUNDURUS_ZONE_CLEAR = 20
THUNDURUS_PORTAL_CLEAR = 24
TRUNK_RELIEF_MAX = 3     # the tarn's own wood rule: nothing steeper than this under any trunk, in any function
LOG_STATES = ("minecraft:spruce_log", "minecraft:birch_log")
STRUCTURE = {"minecraft:spruce_log", "minecraft:birch_log", "minecraft:cobblestone", "minecraft:mossy_cobblestone",
             "minecraft:mossy_stone_bricks", "minecraft:cracked_stone_bricks", "minecraft:mossy_stone_brick_slab"}
LIGHT_WORDS = ("torch", "lantern", "glowstone", "shroomlight", "sea_lantern", "froglight", "campfire", "minecraft:light",
               "lava", "fire", "magma", "redstone_lamp", "jack_o_lantern", "beacon", "end_rod", "candle")


def read_functions(pack):
    """{function name: lines} for build and every arm_*, build first, arms in name order; None if build is missing."""
    d = Path(pack) / "data" / "cobblers" / "function" / "scar_tarn"
    if not (d / "build.mcfunction").exists():
        return None
    names = ["build"] + sorted(p.stem for p in d.glob("arm_*.mcfunction"))
    return {n: (d / (n + ".mcfunction")).read_text(encoding="utf-8").splitlines() for n in names}


def audit_window(doc):
    """The box the audit reads the heightmap over: the pond's window and the arms' window together."""
    x0, z0, x1, z1 = doc["pond"]["window"]
    arms = (doc.get("growth") or {}).get("arms")
    if arms:
        a0, b0, a1, b1 = arms["window"]
        x0, z0, x1, z1 = min(x0, a0), min(z0, b0), max(x1, a1), max(z1, b1)
    return x0, z0, x1, z1


def ring_inside(x, z, ring):
    """Even-odd ray cast, point (x, z) against a polygon ring [(x, z), ...]."""
    inside = False
    n = len(ring)
    for i in range(n):
        (ax, az), (bx, bz) = ring[i], ring[(i + 1) % n]
        if (az > z) != (bz > z) and x < (bx - ax) * (z - az) / (bz - az) + ax:
            inside = not inside
    return inside


def relief3(H, x, z):
    vals = [H(x + a, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if H.has(x + a, z + b)]
    return max(vals) - min(vals)


def log_columns(lines):
    """{(x, z): lowest y} of every upright log (`axis=y`) a function writes: a tree's trunk, not a fallen log."""
    out = {}
    for raw in lines:
        line = raw.strip()
        m = RE_SET.match(line)
        if m:
            x0, y0, z0 = int(m.group(1)), int(m.group(2)), int(m.group(3))
            x1, y1, z1, state = x0, y0, z0, m.group(4)
        else:
            m = RE_FILL.match(line)
            if not m:
                continue
            v = [int(m.group(i)) for i in range(1, 7)]
            x0, y0, z0, x1, y1, z1, state = min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]), max(v[2], v[5]), m.group(7)
        if base(state) in LOG_STATES and "axis=y" in state:
            for x in range(x0, x1 + 1):
                for z in range(z0, z1 + 1):
                    out[(x, z)] = min(out.get((x, z), y0), y0)
    return out


def scar_geometry(data_dir):
    """The Scar's streets, plaza, ruin footprints and the city's core box, from placements.json and ruins.json."""
    pl = jload(Path(data_dir) / "placements.json")["settlements"]["the_scar"]["plan"]
    streets = {s["id"]: s for s in pl["streets"]}
    lots = pl["house_lots"]
    reach = lots["setback"] + lots["size"][1]
    corners = []
    for rid in lots["along"]:
        s = streets[rid]
        (ax, az), (bx, bz) = s["polyline"][0], s["polyline"][-1]
        half = s["width"] / 2.0 + reach
        end = lots["size"][0] + lots["gap"]
        x0, x1 = min(ax, bx) - end - CORE_MARGIN, max(ax, bx) + end + CORE_MARGIN
        z0, z1 = min(az, bz) - half - CORE_MARGIN, max(az, bz) + half + CORE_MARGIN
        corners += [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    core = hull(corners)
    ruins = [tuple(r["footprint"]) for r in jload(Path(data_dir) / "ruins.json")["sites"]["the_scar"]["ruins"]]
    return {"streets": list(streets.values()), "plaza": tuple(pl["plaza"]["rect"]), "ruins": ruins, "core": core}


def hull(points):
    """Convex hull (monotone chain) of [(x, z), ...], counter-clockwise."""
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


def inside_polygon(C, ring):
    """Boolean per row of C (n x 2): the cell centre (x + 0.5, z + 0.5) is inside the polygon (even-odd)."""
    x, z = C[:, 0] + 0.5, C[:, 1] + 0.5
    inside = np.zeros(len(C), bool)
    n = len(ring)
    for i in range(n):
        (ax, az), (bx, bz) = ring[i], ring[(i + 1) % n]
        if az == bz:
            continue
        inside ^= ((az > z) != (bz > z)) & (x < (bx - ax) * (z - az) / (bz - az) + ax)
    return inside


def _box_dist(C, box):
    x0, z0, x1, z1 = box
    dx = np.maximum(np.maximum(x0 - C[:, 0], C[:, 0] - x1), 0)
    dz = np.maximum(np.maximum(z0 - C[:, 1], C[:, 1] - z1), 0)
    return np.hypot(dx, dz)


def check_forest(functions, H, doc, rep, data_dir=DATA):
    """The arms (growth.arms) against the ground and against everything else that stands on Mt Vessu."""
    arms = (doc.get("growth") or {}).get("arms")
    if not arms:
        return {}
    names = [n for n in functions if n.startswith("arm_")]
    want = ["arm_" + lb["id"] for lb in arms["lobes"]]
    if sorted(names) != sorted(want):
        rep.err("forest", "the pack's arm functions %s are not the record's lobes %s" % (sorted(names), sorted(want)))
    lines = [l for n in ["build"] + sorted(names) for l in functions.get(n, [])]
    W, probs = replay(lines, H, 0)
    for p in probs[:4]:
        rep.err("forest", "replay: " + p)
    cols = np.asarray(sorted({(x, z) for x, _y, z in W.written}), float)
    if not len(cols):
        rep.err("forest", "the functions write no column")
        return {}
    stats = {}
    # 1. the trunks: standing on ground a tree can stand on, and not under the sea
    cap = int(arms["max_relief_3x3"])
    steep = []
    for n in sorted(names):
        trunks = log_columns(functions[n])
        stats[n] = {"trunks": len(trunks), "functions_lines": len([l for l in functions[n] if l and not l.startswith("#")])}
        if not trunks:
            rep.err("forest", "%s writes no tree" % n)
        for (x, z), y in sorted(trunks.items()):
            if relief3(H, x, z) > cap:
                steep.append((n, x, z, relief3(H, x, z)))
            if H(x, z) < arms["min_ground_y"]:
                rep.err("forest", "%s: a trunk at (%d, %d) stands on ground y%d, under the record's floor y%d" % (n, x, z, H(x, z), arms["min_ground_y"]))
            if y != H(x, z) + 1:
                rep.err("forest", "%s: the trunk at (%d, %d) starts at y%d, not on the ground (y%d)" % (n, x, z, y, H(x, z)))
    if steep:
        rep.err("forest", "%d arm trunk(s) on ground steeper than the 3x3 relief %d, e.g. %s" % (len(steep), cap, steep[:3]))
    allsteep = [(x, z) for (x, z) in log_columns(functions["build"]) if relief3(H, x, z) > TRUNK_RELIEF_MAX]
    if allsteep:
        rep.err("forest", "%d tarn trunk(s) on 3x3 relief over %d, e.g. %s" % (len(allsteep), TRUNK_RELIEF_MAX, allsteep[:3]))
    # 2. every column an arm writes is inside the mountain's outline
    lm = next(l for l in jload(Path(data_dir) / "landmarks.json")["landmarks"] if l["id"] == arms["inside_landmark"])
    ring = [tuple(p) for p in lm["extent"]["polygons"][0]]
    arm_cols = set()
    for n in sorted(names):
        for raw in functions[n]:
            m = RE_SET.match(raw.strip())
            if m:
                arm_cols.add((int(m.group(1)), int(m.group(3))))
                continue
            m = RE_FILL.match(raw.strip())
            if m:
                v = [int(m.group(i)) for i in range(1, 7)]
                for x in range(min(v[0], v[3]), max(v[0], v[3]) + 1):
                    for z in range(min(v[2], v[5]), max(v[2], v[5]) + 1):
                        arm_cols.add((x, z))
    outside = [c for c in sorted(arm_cols) if not ring_inside(c[0] + 0.5, c[1] + 0.5, ring)]
    if outside:
        rep.err("forest", "%d arm column(s) outside the %s outline, e.g. %s" % (len(outside), arms["inside_landmark"], outside[:3]))
    # 3. the Scar: its streets, plaza, ruins and core are the city, and the city stays readable
    G = scar_geometry(data_dir)
    for s in G["streets"]:
        pts = s["polyline"]
        d = min(float(_seg_dist(cols, a, b).min()) for a, b in zip(pts, pts[1:]))
        need = s["width"] / 2.0 + STREET_MARGIN
        if d < need:
            rep.err("forest", "a written column is %.1f from the Scar's %s (needs half its width %s + %d)" % (d, s["id"], s["width"] / 2.0, STREET_MARGIN))
        rep.note("forest", "the Scar's %s: nearest written column %.0f" % (s["id"], d))
    for what, box in [("the plaza", G["plaza"])] + [("a ruin at %s" % (f[:2],), f) for f in G["ruins"]]:
        d = float(_box_dist(cols, box).min())
        if d < RUIN_MARGIN:
            rep.err("forest", "a written column is %.1f from %s %s (needs %d)" % (d, what, box, RUIN_MARGIN))
    inner = int(inside_polygon(cols, G["core"]).sum())
    if inner:
        rep.err("forest", "%d written column(s) inside the city's core, the hull of the three house-lot bands and their ends %s" % (inner, G["core"]))
    rep.note("forest", "the city's core hull %s holds %d written column(s)" % (G["core"], inner))
    # 4. Thundurus: the sealed chamber's plug, shaft and approach (the spawn-free box and the portal)
    th = next(e for e in jload(Path(data_dir) / "legendaries.json")["encounters"] if e["id"] == "thundurus")
    dz_ = float(_box_dist(cols, tuple(th["spawn_free_zone"])).min())
    if dz_ < THUNDURUS_ZONE_CLEAR:
        rep.err("forest", "a written column is %.1f from Thundurus's spawn-free box %s (needs %d)" % (dz_, th["spawn_free_zone"], THUNDURUS_ZONE_CLEAR))
    dp = float(np.hypot(cols[:, 0] - th["portal"][0], cols[:, 1] - th["portal"][1]).min())
    if dp < THUNDURUS_PORTAL_CLEAR:
        rep.err("forest", "a written column is %.1f from Thundurus's portal %s (needs %d)" % (dp, th["portal"], THUNDURUS_PORTAL_CLEAR))
    rep.note("forest", "Thundurus: nearest written column %.0f from its spawn-free box, %.0f from its portal" % (dz_, dp))
    # 5. no light, no fire, no spawn-condition block but the whitelisted water
    text = "\n".join(l for l in lines if not l.startswith("#"))
    found = sorted({w for w in LIGHT_WORDS if w in text})
    if found:
        rep.err("forest", "the functions write light or fire blocks: %s (the Scar is dark by design, data/scar_tarn.json place.dark_by_design)" % found)
    spawn = set(jload(Path(data_dir) / "spawn_blocks.json")["blocks"])
    ok = {b for w in jload(Path(data_dir) / "spawn_block_policy.json")["whitelist"] if "scar_tarn" in (w.get("scope") or "")
          for b in w.get("blocks") or []}
    written = set(re.findall(r"minecraft:[a-z_]+", text))
    extra = sorted(written & spawn - ok)
    if extra:
        rep.err("forest", "spawn-condition blocks written that the policy does not allow for scar_tarn: %s" % extra)
    rep.note("forest", "spawn-condition blocks written (allowed): %s" % sorted(written & spawn & ok))
    # 6. each function inside the server's limits
    import function_limits
    for n, ls in functions.items():
        bad = function_limits.check_lines(ls, n)
        if bad:
            rep.err("forest", "%s: %d command(s) the server would refuse, e.g. %s" % (n, len(bad), bad[:2]))
    return stats


# ------------------------------------------------------------------------------------------------------------ run
def build_pack(out):
    """The generator's CLI, not its functions."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "scar_tarn.py"), "build", "--out", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("scar_tarn.py build failed: %s" % (r.stderr or r.stdout)[-400:])
    return Path(out)


def read_function(pack):
    """Every function of the pack as one run of lines: build, then each arm in name order (each holds its own chunks)."""
    fns = read_functions(pack)
    return None if fns is None else [l for ls in fns.values() for l in ls]


def audit(lines, H, doc, wards, spawns, regions, design, jar, data_dir=DATA, drops=DROPS, functions=None):
    rep = Report()
    if not lines:
        rep.err("pack", "no build.mcfunction to replay")
        return rep, {}
    stats = check_water(lines, H, doc, rep, drops)
    check_wards(lines, H, wards, rep)
    if jar is None:
        rep.err("alphas", "no Cobblemon 1.8.0 jar: species and evolution levels NOT checked")
    check_alphas(wards, spawns, regions, design, jar, rep)
    cols = written_columns(lines, H)
    check_overlaps(cols, doc, rep, data_dir)
    pad_cols = None
    if functions is not None and (doc.get("growth") or {}).get("arms"):
        pad_cols = written_columns(functions["build"], H)
    check_paths(cols, doc, rep, data_dir, pad_cols)
    if functions is not None:
        stats["forest"] = check_forest(functions, H, doc, rep, data_dir)
    return rep, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", help="a built cobblers_scar_tarn; default: build one with the generator's CLI into a temp dir")
    ap.add_argument("--records", help="a `scar_tarn.py records` JSON dump to audit instead of data/habitat_blocks.json + spawns.json")
    ap.add_argument("--data", default=str(RECORD))
    ap.add_argument("--jar")
    ap.add_argument("--source-root")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    doc = jload(a.data)
    with tempfile.TemporaryDirectory(prefix="scar_tarn_audit_") as tmp:
        pack = Path(a.pack) if a.pack else build_pack(Path(tmp) / "pack")
        functions = read_functions(pack)
        lines = read_function(pack)
    H = heights_from_heightmap(audit_window(doc), a.source_root)
    if a.records:
        wards, spawns = records_inputs(a.records)
        spawns["subregions"] = jload(DATA / "spawns.json").get("subregions")
    else:
        wards = tarn_wards(jload(DATA / "habitat_blocks.json")["blocks"])
        spawns = jload(DATA / "spawns.json")
    jp = find_jar(a.jar)
    jar = Jar(jp) if jp else None
    rep, stats = audit(lines, H, doc, wards, spawns, jload(DATA / "regions.json"), jload(DATA / "encounter_design.json"), jar,
                       functions=functions)
    forest = stats.pop("forest", {})
    for n, v in sorted(forest.items()):
        print("forest %s: %d trunks, %d commands" % (n, v["trunks"], v["functions_lines"]))
    for d, s in sorted(stats.items()):
        print("drop %d: %d water, %d open face(s), flow reaches %d cell(s), %d over a free cell, %s"
              % (d, s["water"], s["open_faces"], s["reached"], s["falls"], "ESCAPES the window" if s["escaped"] else "inside the window"))
    if a.verbose:
        for n in rep.notes:
            print("  note  " + n)
    for f in rep.findings:
        print("FINDING " + f)
    print("scar_tarn_audit: %d finding(s), %d note(s)" % (len(rep.findings), len(rep.notes)))
    return 1 if rep.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
