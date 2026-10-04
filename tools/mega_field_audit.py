#!/usr/bin/env python
"""Independent audit of the Mega field (data/gulch_mine.json `mega_field`, `farms`, `superseded_farms`), the gulch
pack's keeper for its dens (step R9S), their lairs (cobblers_mega_dens, step R9MD) and the retirement step R9SX.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/mega_field.py, and
takes no geometry from tools/gulch_mine.py or tools/mega_dens.py. Every expectation comes from somewhere else:

  the owner's design   docs/world-building/SOUTHERN_RIFT_MEGA.md section 13 and 13.1 (parsed from the text: the two
                       site coordinates, "if cap after gym 5 is 50 ... lvl 60", the outer/deeper table, 13.1's
                       "outer: level 60, 15%, 10 min; deeper: level 67, 30%, 15 min", the raw-stone currency and its
                       2-stone price); the owner's cursor from docs/world-building/MEGA_FIELD.md's relayed description
  the floor            derived/rift_sculpt/basin.npy (the sculpt's basin mask, in plan.json's box), NOT the lip ring
                       the polygon was traced from; the heightmap (tools/ground.py, rounded); painted water
                       (tools/water_mask.py)
  the level cap        rctmod's rule as docs/mechanics/LEAGUE_LEVEL_CAP.md section 1 records it, computed here from
                       modpack/config/rctmod-server.toml and the gym and League teams in data/trainers.json; the gate
                       of the zone each den stands in from data/rift_zones.json
  the critical path    data/route_paths.json, every point of every path (mega_dens_audit.py's 128 footprint rule)
  spawn conditions     data/spawn_blocks.json and data/spawn_block_policy.json
  broken Mega models   docs/research/CLIENT_MODEL_FIXES.md ("7 megas")
  the borders          data/mega_borders.json's declared rules (blocks, palettes, kill threshold, keep, cap), each den's
                       own palettes in data/mega_dens.json dens; the overlaps are measured here from data/gulch_mine.json
                       homes and leashes. tools/mega_borders.py is never imported for geometry: its lens, its sides and
                       its dressing floor are what is being checked

What is checked is the generators' OUTPUT: the polygon and farms as committed (or as a test's mutated generator
emits them), the built gulch functions and battle_fainted callback, the built lair functions, and the steps R9SX and
R9MD run (taken from the generators as output, as mega_dens_audit.py does).

  area      the polygon holds the owner's cursor and both section-13 points; overlaps the gulch zone by 0 columns;
            every basin column of the field's floor (the basin flooded from the owner's points, stopped by the gulch
            zone and the declared stem cut, trace.cut_near to the gulch zone's first vertex) is inside it, every basin
            column inside it is that floor, and no column of it lies more than rim_outset + tolerance outside the floor
  den       each field den: anchor inside the polygon and on the basin; y = round(ground) + 1; dry (no painted water
            within the pad); standable (its 3x3 within 1 block); its leash reaches neither the gulch zone nor
            any Rift zone's post or guard line; its whole range (leash disc) inside the polygon (layout.why.edge_clear:
            "a Mega's whole range is the field's floor");
            at least 128 from every critical-path point; its id names no other den (a den is keyed by its id, never its
            species: since 2026-10-04 a species may hold several dens, and every lair, border, keeper function and
            retirement below is keyed by the den's id); a species whose stone (the aspect's, X or Y included) the Cutters sell; none on the broken-model list
  crowding  THE OWNER, 2026-10-04: "Megas clashing over territory ... pressing against each other for space ...
            overlapping ranges". (Until 2026-10-04 this audit REFUSED overlapping leash discs, the spacing-64 design's
            rule; the owner's brief reverses it.) Measured here from the homes and leashes alone: every den's range
            overlaps at least one other den's, and its deepest such overlap is at least layout.min_overlap (declared:
            below it the lens is a sliver the border cannot dress); no range reaches another den's home (layout.why.leash: "no Mega's range
            reaches its neighbour's home"). A range is the keeper's own test, the built leash line `positioned <anchor>
            unless entity @s[distance=..L]`: a Mega on column (x, z) stands at its centre, so it is in range when
            hypot(x + 0.5 - ax, z + 0.5 - az) <= L
  floor     the usable floor computed here from the heightmap and the polygon (never mega_field.floor): inside the
            polygon, dry (tools/water_mask.py's sea and lake rule), no 4-neighbour step over one block. Reported: its
            size, the fraction any range covers, the farthest usable column from every range. Not a pass/fail number:
            the owner asked for "as much ... as the terrain allows" and gave no fraction
  tiers     a den is the deeper tier exactly when its home is layout.deeper_from_town or more from town.square.centre;
            the roster is dealt by distance (layout.why.roster: "BANDED by distance from the town, nearest first"); the
            BUILT level is farm_tiers[tier].level as declared, and also the cap rule below
  level     the den's zone gate (data/rift_zones.json boxes) gives the badges; the rctmod cap for those badges plus
            the owner's offset (13.1's level less the owner's cap of 50) is the level in the BUILT spawn function;
            spawn_at spawns uncatchable
  borders   the BUILT cobblers_mega_borders functions (tools/mega_borders.py, data/mega_borders.json): exactly one border
            per pair of overlapping ranges measured above and none for any other pair, named <den id>__<den id> (never
            by species); a border that writes nothing is right only when its lens has no free dressing column by this
            audit's own rules (free_columns: in both ranges, on the usable floor, clear of anchors, lairs, the other
            borders and every footprint rule below), else it is a problem; every column a border writes lies
            inside BOTH dens' ranges (dressed AT the overlap); every block in blocks.ids, none a spawn condition
            (data/spawn_blocks.json) that no data/spawn_block_policy.json entry scoped to mega_borders whitelists; every
            block from round(ground) to round(ground) + max_rise; the scar (ground-level writes) only the shared scar
            palette or the two dens' own scrape palettes (data/mega_dens.json dens), and never the OTHER den's own
            scrape block on a den's side of the border (the radical line); rock above the scar from the two dens'
            boulder blocks and rubble.loose_blocks; a carcass (one skeleton skull) on every border whose ranges overlap
            by kill.min_overlap or more and on no other; no column written by two borders, within keep.anchor_clear of
            any anchor or keep.lair_clear of any column a BUILT lair writes; no column outside the polygon, in the
            gulch's zone or block box, under painted water, within 128 of the critical path, within 32 of a Rift zone
            wall, post or guard point or a placement, or in a town's footprint; the written columns at most
            coverage_cap of the usable floor inside any range (the floor above); R9MB holds each border's columns,
            runs it once, and releases every hold
  drops     per field den, the built load sets gm.pct and gm.resp to 13.1's numbers for its tier (outer 15% 10 min,
            deeper 30% 15 min; within section 13's 25-35%); bind_ hit_ roll_ slain_ hitter_ exist; the battle_fainted
            callback calls drops/fainted, which rolls every field den; give drops the raw stone section 13 names,
            owner-only; every Cutters trade buys that stone at section 13's price
  keeper    the leash returns each Mega to its own anchor at its den's leash; the farm's approach box holds the whole
            leash disc and its ground, so a player fighting the Mega keeps its keeper running
  retire    megas/retire kills exactly the per-den tag of every superseded den (the tag scheme read off a live den's
            bind) and clears its drop storage; no other function names a retired den; R9SX holds anchor +- leash of
            every retired den (each hold under 256 chunks), runs megas/retire after a wait, and releases every hold
  lairs     one lair per field den, mega_dens/<den id>, and none for a retired one; no lair writes a spawn condition no mega_dens policy
            whitelists; every lair write is inside the field polygon and 128 or more from every critical-path point;
            no two lairs write one column (their dens now stand as close as the lairs allow); R9MD runs exactly the
            field dens' lairs
  order     reapply.steps: R9S < R9SX < R9MD < R9MB < R9E; prepare: mega_field:check < gulch_mine:build,
            mega_dens:build < mega_borders:build, and this audit after gulch_mine:build, mega_dens:build and
            mega_borders:build; cobblers_mega_borders is a server pack

NOT covered (needs the server, EXP-054): that a Mega spawns and stands at the anchor, that FoF makes it hostile, that
the roll runs after a real win, that the item is refused to another player, that R9SX's forceload loads the retired
Megas' entities in its wait, and the tick cost of megas/watch. Nor (needs the owner in game): whether the borders READ
as contested ground from the air or on foot, which is the owner's actual ask; that two neighbours' Megas, both up,
behave as rivals (nothing makes them fight: the crowding is dressing and geometry, not behaviour); that a player in an
overlap is not pulled by two keepers at once in a way that feels wrong.

  python tools/mega_field_audit.py [--source-root R] [--gulch-pack DIR] [--dens-pack DIR] [--borders-pack DIR]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
DOCS = ROOT / "docs"
GULCH_PACK = ROOT / "build" / "datapacks" / "cobblers_gulch_mine"
DENS_PACK = ROOT / "build" / "datapacks" / "cobblers_mega_dens"
GULCH_FN = "data/cobblers/function/gulch_mine"
DENS_FN = "data/cobblers/function/mega_dens"
BORDERS_PACK = ROOT / "build" / "datapacks" / "cobblers_mega_borders"
BORDERS_FN = "data/cobblers/function/mega_borders"
KILL_BLOCKS = ("minecraft:skeleton_skull", "minecraft:bone_block", "minecraft:chain", "minecraft:iron_bars")
CALLBACK = "data/cobblemon/callbacks/battle_fainted/cobblers_gulch_drops.molang"
SCULPT = ROOT / "derived" / "rift_sculpt"
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*?)$")
TICKS_PER_MINUTE = 1200


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, check, msg):
        self.errors.append("%s: %s" % (check, msg))

    def note(self, msg):
        self.notes.append(msg)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _need(pattern, text, what, flags=re.S):
    m = re.search(pattern, text, flags)
    if not m:
        raise SystemExit("mega_field_audit: cannot read %s from the design text (pattern %r): the audit's source moved"
                         % (what, pattern))
    return m


# ---------------------------------------------------------------------------------------------- the owner's design
def design(docs=DOCS):
    """The numbers the owner's design states, read from the text itself."""
    s13 = (docs / "world-building" / "SOUTHERN_RIFT_MEGA.md").read_text(encoding="utf-8")
    # section 13 and 13.1 only: earlier sections hold the superseded numbers (4 raw stones, the old floor)
    s13 = s13[_need(r"^## 13\. ", s13, "section 13", re.M).start():]
    mf = (docs / "world-building" / "MEGA_FIELD.md").read_text(encoding="utf-8")
    cm = (docs / "research" / "CLIENT_MODEL_FIXES.md").read_text(encoding="utf-8")
    m = _need(r"around \*\*\((\d+), (\d+), (\d+)\)\*\* and \*\*\((\d+), (\d+), (\d+)\)\*\*", s13, "section 13's sites")
    v = [int(x) for x in m.groups()]
    sites = [(v[0], v[2]), (v[3], v[5])]
    cur = _need(r"the cursor\s+at X (\d+) Z (\d+)", mf, "the owner's cursor")
    ref = _need(r"if cap after gym 5 is (\d+)\s.*?lvl (\d+) or so", s13, "the owner's level rule")
    built = _need(r"outer: level (\d+), (\d+)%, (\d+) min; deeper: level (\d+), (\d+)%, (\d+) min", s13,
                  "13.1's farm tiers")
    o_lv, o_pct, o_min, d_lv, d_pct, d_min = (int(x) for x in built.groups())
    deep = _need(r"\| Deeper \| (\d+)-(\d+),.*?\| higher, (\d+)-(\d+)%", s13, "section 13's deeper row")
    outer = _need(r"\| Outer \|[^\n]*\| (\d+)% \|", s13, "section 13's outer row")
    raw = _need(r"The currency is the raw `([a-z_]+:[a-z_]+)`", s13, "the currency")
    price = _need(r"takes \*\*(\d+) raw stones\*\*", s13, "the price")
    broken = _need(r"\*\*7 megas:\*\*[^.]*?0%\.\s+([a-z,\s]+)\.", cm, "the broken Mega models")
    cap_ref = int(ref.group(1))
    return {
        "cursor": (int(cur.group(1)), int(cur.group(2))),
        "sites": sites,
        "cap_ref": cap_ref,
        "owner_outer_level": int(ref.group(2)),
        "tiers": {"field_outer": {"offset": o_lv - cap_ref, "pct": o_pct, "ticks": o_min * TICKS_PER_MINUTE},
                  "field_deeper": {"offset": d_lv - cap_ref, "pct": d_pct, "ticks": d_min * TICKS_PER_MINUTE}},
        "deeper_band": (int(deep.group(1)) - cap_ref, int(deep.group(2)) - cap_ref),
        "deeper_pct_band": (int(deep.group(3)), int(deep.group(4))),
        "outer_pct": int(outer.group(1)),
        "raw": raw.group(1),
        "price": int(price.group(1)),
        "broken": {w.strip() for w in broken.group(1).replace("\n", " ").split(",") if w.strip()},
    }


# ---------------------------------------------------------------------------------------------- the level cap
def cap_table(data=DATA, toml=ROOT / "modpack" / "config" / "rctmod-server.toml"):
    """badges -> the rctmod cap (LEAGUE_LEVEL_CAP.md section 1): max(initialLevelCap, the next trainer's level), a
    trainer's level being max(its team's top + relativeLevelCap, its required defeats' levels), and the Kanto chain
    being the eight gyms, the four, the Champion in order; with no next trainer, 100."""
    t = Path(toml).read_text(encoding="utf-8")
    init = int(_need(r"^\s*initialLevelCap\s*=\s*(-?\d+)", t, "initialLevelCap", re.M).group(1))
    rel = int(_need(r"^\s*relativeLevelCap\s*=\s*(-?\d+)", t, "relativeLevelCap", re.M).group(1))
    tr = load_json(Path(data) / "trainers.json")["trainers"]

    def by(cls):
        return sorted((x for x in tr if x["class"] == cls), key=lambda x: x["order"])
    chain = by("gym_leader") + by("elite_four") + by("champion")
    if len(by("gym_leader")) != 8:
        raise SystemExit("mega_field_audit: data/trainers.json has %d gym leaders, not 8" % len(by("gym_leader")))
    caps, run = {}, 0
    for b, x in enumerate(chain):
        run = max(run, min(100, max(0, max(p["level"] for p in x["team"]) + rel)))
        caps[b] = max(init, run)
    caps[len(chain)] = 100
    return caps


# ---------------------------------------------------------------------------------------------- geometry
def raster(poly, x0, z0, x1, z1, off=0.5):
    """(z, x) bool mask of the columns x0..x1, z0..z1 whose point (x + off, z + off) is inside poly (even-odd): the
    centre by default; off=0 is tools/water_mask.py's own test, which casts from the column's integer corner."""
    xs = np.arange(x0, x1 + 1) + off
    zs = np.arange(z0, z1 + 1) + off
    res = np.zeros((len(zs), len(xs)), bool)
    n = len(poly)
    for i in range(n):
        xa, za = poly[i]
        xb, zb = poly[(i + 1) % n]
        if za == zb:
            continue
        rows = np.nonzero((za > zs) != (zb > zs))[0]      # only the rows this edge crosses
        if not len(rows):
            continue
        xi = xa + (zs[rows] - za) * (xb - xa) / (zb - za)
        res[rows] ^= xs[None, :] < xi[:, None]
    return res


def _in_poly_pt(poly, x, z):
    inside, j = False, len(poly) - 1
    for i in range(len(poly)):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi:
            inside = not inside
        j = i
    return inside


def seg_dist(poly, x, z):
    """Distance from (x, z) to the polygon's boundary."""
    best = math.inf
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]
        bx, bz = poly[(i + 1) % n]
        dx, dz = bx - ax, bz - az
        L2 = dx * dx + dz * dz
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L2))
        best = min(best, math.hypot(x - ax - t * dx, z - az - t * dz))
    return best


def near_points(cols, pts):
    """Min distance from any of cols [(x, z)] to any of pts [(x, z)], exact."""
    c = np.asarray(sorted(cols), dtype=float)
    p = np.asarray(pts, dtype=float)
    best = math.inf
    for i in range(0, len(c), 256):
        cc = c[i:i + 256]
        d = np.sqrt((cc[:, None, 0] - p[None, :, 0]) ** 2 + (cc[:, None, 1] - p[None, :, 1]) ** 2)
        best = min(best, float(d.min()))
    return best


def dilate(m, k):
    """Chessboard dilation by k."""
    out = m.copy()
    for _ in range(k):
        n = out.copy()
        n[1:, :] |= out[:-1, :]
        n[:-1, :] |= out[1:, :]
        n[:, 1:] |= out[:, :-1]
        n[:, :-1] |= out[:, 1:]
        n[1:, 1:] |= out[:-1, :-1]
        n[1:, :-1] |= out[:-1, 1:]
        n[:-1, 1:] |= out[1:, :-1]
        n[:-1, :-1] |= out[1:, 1:]
        out = n
    return out


def load_basin(sculpt=SCULPT):
    plan = load_json(Path(sculpt) / "plan.json")
    X0, X1, Z0, Z1 = plan["box"]
    B = np.load(Path(sculpt) / "basin.npy")
    if B.shape != (Z1 - Z0 + 1, X1 - X0 + 1):
        raise SystemExit("mega_field_audit: basin.npy %s does not match plan.json's box %s" % (B.shape, plan["box"]))
    return B, (X0, Z0)


def basin_at(basin, x, z):
    B, (X0, Z0) = basin
    i, j = int(z) - Z0, int(x) - X0
    return 0 <= i < B.shape[0] and 0 <= j < B.shape[1] and bool(B[i, j])


# ---------------------------------------------------------------------------------------------- the checks
def field_dens(spec):
    return [(fa, d) for fa in spec["farms"] if fa["id"].startswith("field_") for d in fa["dens"]]


def check_area(spec, basin, D, R):
    mf = spec["mega_field"]
    poly = mf["polygon"]
    zone = spec["zone"]["polygon"]
    B, (BX0, BZ0) = basin
    for name, (x, z) in [("the owner's cursor", D["cursor"])] + [("section 13's site", p) for p in D["sites"]]:
        if not _in_poly_pt(poly, x + 0.5, z + 0.5):
            R.err("area", "%s (%d, %d) is not inside mega_field.polygon" % (name, x, z))
    xs = [p[0] for p in poly] + [p[0] for p in zone]
    zs = [p[1] for p in poly] + [p[1] for p in zone]
    m = 8
    x0, z0 = int(math.floor(min(xs))) - m, int(math.floor(min(zs))) - m
    x1, z1 = int(math.ceil(max(xs))) + m, int(math.ceil(max(zs))) + m
    F = raster(poly, x0, z0, x1, z1)
    Zm = raster(zone, x0, z0, x1, z1)
    ov = int((F & Zm).sum())
    if ov:
        R.err("area", "the field overlaps the gulch zone by %d column(s)" % ov)
    # the basin over this window
    Bw = np.zeros(F.shape, bool)
    i0, j0 = max(0, z0 - BZ0), max(0, x0 - BX0)
    i1, j1 = min(B.shape[0], z1 - BZ0 + 1), min(B.shape[1], x1 - BX0 + 1)
    Bw[i0 - (z0 - BZ0):i1 - (z0 - BZ0), j0 - (x0 - BX0):j1 - (x0 - BX0)] = B[i0:i1, j0:j1]
    # the declared stem cut: trace.cut_near to the gulch zone's first vertex (its north-east end)
    a, b = mf["trace"]["cut_near"], zone[0]
    bar = np.zeros(F.shape, bool)
    n = int(math.hypot(b[0] - a[0], b[1] - a[1]) * 4) + 2
    for t in np.linspace(0.0, 1.0, n):
        x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        for dx in (0, 1):
            for dz in (0, 1):
                bi, bj = int(math.floor(z)) + dz - z0, int(math.floor(x)) + dx - x0
                if 0 <= bi < bar.shape[0] and 0 <= bj < bar.shape[1]:
                    bar[bi, bj] = True
    free = Bw & ~Zm & ~bar
    reach = np.zeros(F.shape, bool)
    q = deque()
    for name, (x, z) in [("the owner's cursor", D["cursor"])] + [("section 13's site", p) for p in D["sites"]]:
        i, j = z - z0, x - x0
        if not (0 <= i < F.shape[0] and 0 <= j < F.shape[1]) or not free[i, j]:
            R.err("area", "%s (%d, %d) is not on the basin's floor (derived/rift_sculpt/basin.npy)" % (name, x, z))
            continue
        if not reach[i, j]:
            reach[i, j] = True
            q.append((i, j))
    H, W = F.shape
    while q:
        i, j = q.popleft()
        for u, v in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= u < H and 0 <= v < W and free[u, v] and not reach[u, v]:
                reach[u, v] = True
                q.append((u, v))
    if reach[0, :].any() or reach[-1, :].any() or reach[:, 0].any() or reach[:, -1].any():
        R.err("area", "the basin floored from the owner's points leaks past the field's bounds: the gulch zone and the "
                      "stem cut do not close it")
        return
    left = list(zip(*np.nonzero(reach & ~F)))
    if left:
        groups = []
        for i, j in left:
            p = (int(j + x0), int(i + z0))
            g = next((gg for gg in groups if max(abs(p[0] - gg[0][0]), abs(p[1] - gg[0][1])) <= 8), None)
            (g.append(p) if g else groups.append([p]))
        R.err("area", "%d basin column(s) of the field's floor are outside mega_field.polygon, in %d place(s): %s"
              % (len(left), len(groups), "; ".join("%d at %s" % (len(g), g[0]) for g in groups)))
    stray = list(zip(*np.nonzero(F & Bw & ~reach & ~bar)))
    if stray:
        i, j = stray[0]
        R.err("area", "%d basin column(s) inside the polygon are not the field's floor (another basin), e.g. (%d, %d)"
              % (len(stray), j + x0, i + z0))
    # the edge runs rim_outset outside the lip, simplified within tolerance: no column further out than their sum
    k = int(math.floor(mf["trace"]["rim_outset"] + mf["trace"]["tolerance"]))
    far = list(zip(*np.nonzero(F & ~dilate(reach | bar, k))))
    if far:
        i, j = far[0]
        R.err("area", "%d column(s) of the polygon lie more than %d (rim_outset + tolerance) from the field's floor, "
                      "e.g. (%d, %d)" % (len(far), k, j + x0, i + z0))
    R.note("area: polygon %d columns, the floor %d, outside the polygon %d" % (int(F.sum()), int(reach.sum()), len(left)))


def zone_of(rz, x, z):
    """[(zone id, pass)] of the live Rift zones whose boxes hold the column."""
    out = []
    for zid, zz in rz["zones"].items():
        if str(zz.get("status", "")).startswith("SUPERSEDED"):
            continue
        for b in zz.get("boxes") or []:
            if b[0] <= x <= b[2] and b[1] <= z <= b[3]:
                out.append((zid, zz["pass"]))
                break
    return out


def check_dens(spec, g, basin, D, R, sold, data=DATA):
    poly = spec["mega_field"]["polygon"]
    zone = spec["zone"]["polygon"]
    route = [tuple(p) for pts in load_json(Path(data) / "route_paths.json")["paths"].values() for p in pts]
    import water_mask
    bodies, sea = water_mask.bodies(), water_mask.sea_level()
    # where a zone's guard stands or its line crosses: a field Mega's leash never reaches one (data/rift_zones.json)
    posts = []
    for zid, zz in load_json(Path(data) / "rift_zones.json")["zones"].items():
        if str(zz.get("status", "")).startswith("SUPERSEDED"):
            continue
        posts += [("%s post %s" % (zid, p.get("id")), p["at"]) for p in zz.get("posts") or [] if isinstance(p.get("at"), list)]
        gd = zz.get("guard") or {}
        posts += [("%s guard %s" % (zid, k), gd[k][:2]) for k in ("edge_at", "inside_at") if isinstance(gd.get(k), list)]

    def gr(x, z):
        return int(round(g(x, z)))
    dens = field_dens(spec)
    if not dens:
        R.err("den", "no field den in data/gulch_mine.json farms")
    seen = {}
    for _fa, d in dens:
        did, sp = d["id"], d["species"]
        ax, ay, az = d["anchor"]
        if not _in_poly_pt(poly, ax + 0.5, az + 0.5):
            R.err("den", "%s (%s) at (%d, %d) is outside mega_field.polygon" % (did, sp, ax, az))
        if not basin_at(basin, ax, az):
            R.err("den", "%s (%s) at (%d, %d) is not on the basin floor (basin.npy)" % (did, sp, ax, az))
        if ay != gr(ax, az) + 1:
            R.err("den", "%s: anchor y%d is not round(ground) + 1 = y%d" % (did, ay, gr(ax, az) + 1))
        wet = [(x, z) for x in range(ax - 3, ax + 4) for z in range(az - 3, az + 4)
               if water_mask.level_at(x, z, gr, bodies, sea)[0] is not None]
        if wet:
            R.err("den", "%s: painted water within 3 of the anchor, e.g. %s" % (did, wet[0]))
        nb = [gr(x, z) for x in range(ax - 1, ax + 2) for z in range(az - 1, az + 2)]
        if max(nb) - min(nb) > 1:
            R.err("den", "%s: the anchor's 3x3 spans %d blocks: not standable" % (did, max(nb) - min(nb)))
        if seg_dist(poly, ax, az) < d["leash"]:
            R.err("den", "%s: its range (leash %d) crosses the field's edge (%.1f from it): the field's floor must hold "
                         "a Mega's whole range" % (did, d["leash"], seg_dist(poly, ax, az)))
        if _in_poly_pt(zone, ax + 0.5, az + 0.5) or seg_dist(zone, ax + 0.5, az + 0.5) <= d["leash"]:
            R.err("den", "%s: its leash (%d) reaches the gulch zone (%.0f from it)"
                  % (did, d["leash"], seg_dist(zone, ax + 0.5, az + 0.5)))
        for what, (px, pz) in posts:
            if math.hypot(px - ax, pz - az) <= d["leash"]:
                R.err("den", "%s: its leash (%d) reaches the Rift zones' %s at (%d, %d)" % (did, d["leash"], what, px, pz))
        dr = near_points([(ax, az)], route)
        if dr < 128:
            R.err("den", "%s: anchor %.0f from the critical path (data/route_paths.json): under 128" % (did, dr))
        # a den is its id, not its species (2026-10-04: a species may hold several dens); its tag, scores, keeper
        # functions, lair and borders are all named by the id, so two dens with one id would be one Mega to the keeper
        if did in seen:
            R.err("den", "%s is the id of two dens, at %s and %s: a den's tag, scores, lair and borders are named by "
                         "its id" % (did, seen[did], (ax, az)))
        seen[did] = (ax, az)
        if sp in D["broken"]:
            R.err("den", "%s: %s is on CLIENT_MODEL_FIXES.md's broken Mega models" % (did, sp))
        asp = d["aspect"]
        m = re.fullmatch(r"mega_evolution=mega(?:_([xy]))?", asp)
        if not m:
            R.err("den", "%s: aspect %r is not a Mega aspect" % (did, asp))
        else:
            want = [s for s in sold if s.startswith(sp[:5]) and (s.endswith("_" + m.group(1)) if m.group(1)
                                                                   else not re.search(r"_[xy]$", s))]
            if not want:
                R.err("den", "%s: no %s stone for %s on any Cutters bench: not a Mega the pack has" % (did, asp, sp))


# ---------------------------------------------------------------------------------------------- crowding and floor
def in_range(d, x, z):
    """Column (x, z) is in den d's range: the keeper's built leash test, from the anchor's block corner to a Mega
    standing at the column's centre (see the module's `crowding`)."""
    return math.hypot(x + 0.5 - d["anchor"][0], z + 0.5 - d["anchor"][2]) <= d["leash"]


def overlaps(spec):
    """[(a, b, homes apart, overlap)] for every two field dens whose ranges overlap, measured from the homes alone."""
    ds = [d for _fa, d in field_dens(spec)]
    out = []
    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            s = math.hypot(a["anchor"][0] - b["anchor"][0], a["anchor"][2] - b["anchor"][2])
            if s < a["leash"] + b["leash"]:
                out.append((a, b, s, a["leash"] + b["leash"] - s))
    return out


def check_crowding(spec, R):
    ds = [d for _fa, d in field_dens(spec)]
    pairs = overlaps(spec)
    for i, a in enumerate(ds):
        for b in ds[i + 1:]:
            s = math.hypot(a["anchor"][0] - b["anchor"][0], a["anchor"][2] - b["anchor"][2])
            if s <= max(a["leash"], b["leash"]):
                R.err("crowding", "%s and %s are %.1f apart: one's range (%d) reaches the other's home"
                      % (a["id"], b["id"], s, max(a["leash"], b["leash"])))
    touched = {d["id"] for a, b, _s, _o in pairs for d in (a, b)}
    # the declared depth (layout.min_overlap and its why: "every den's range overlaps another's by at least this many
    # blocks ... Below it a lens is a sliver the border dressing cannot use"); absent, only "overlaps one" is held
    need = ((spec.get("mega_field") or {}).get("layout") or {}).get("min_overlap")
    deepest = {}
    for a, b, _s, o in pairs:
        for d in (a, b):
            deepest[d["id"]] = max(deepest.get(d["id"], 0.0), o)
    if need is not None:
        for d in ds:
            if d["id"] in deepest and deepest[d["id"]] < need:
                R.err("crowding", "%s: its deepest overlap with another den's range is %.1f, under layout.min_overlap %s"
                      % (d["id"], deepest[d["id"]], need))
    for d in ds:
        if d["id"] in touched:
            continue
        near = min(((math.hypot(d["anchor"][0] - e["anchor"][0], d["anchor"][2] - e["anchor"][2]), e) for e in ds
                    if e is not d), key=lambda t: t[0], default=(None, None))
        R.err("crowding", "%s: its range overlaps no other den's: the nearest, %s, is %.1f away and the two ranges "
                          "reach %d" % (d["id"], near[1]["id"] if near[1] else "none", near[0] or 0,
                                        d["leash"] + (near[1]["leash"] if near[1] else 0)))
    # the groups of dens whose ranges touch, for the report
    grp = {d["id"]: d["id"] for d in ds}

    def root(i):
        while grp[i] != i:
            i = grp[i]
        return i
    for a, b, _s, _o in pairs:
        grp[root(a["id"])] = root(b["id"])
    sizes = {}
    for d in ds:
        sizes[root(d["id"])] = sizes.get(root(d["id"]), 0) + 1
    if pairs:
        R.note("crowding: %d dens, %d overlapping pairs, overlaps %.1f..%.1f blocks, %d group(s) of touching ranges %s"
               % (len(ds), len(pairs), min(p[3] for p in pairs), max(p[3] for p in pairs), len(sizes),
                  sorted(sizes.values(), reverse=True)))
    return pairs


def usable_floor(spec, g):
    """The field's usable floor, computed here: (box, floor mask, distance-past-every-range array). Inside the polygon,
    dry by tools/water_mask.py's rule (under the sea level, or inside a lake body's basin ring below its level, the ring
    cast from the column's integer corner as water_mask.in_polygons does), and no 4-neighbour step over one block on
    the rounded heightmap."""
    import water_mask
    poly = spec["mega_field"]["polygon"]
    x0, z0 = int(math.floor(min(p[0] for p in poly))), int(math.floor(min(p[1] for p in poly)))
    x1, z1 = int(math.ceil(max(p[0] for p in poly))), int(math.ceil(max(p[1] for p in poly)))
    F = raster(poly, x0, z0, x1, z1)
    H = np.asarray(g.box(x0, z0, x1, z1))
    wet = H < water_mask.sea_level()
    for _bid, b in water_mask.bodies().items():
        rings = [r for r in b["basin"] if r]
        xs = [p[0] for r in rings for p in r]
        zs = [p[1] for r in rings for p in r]
        if not rings or max(xs) < x0 or min(xs) > x1 or max(zs) < z0 or min(zs) > z1:
            continue
        inb = np.zeros(F.shape, bool)
        for r in rings:
            inb |= raster(r, x0, z0, x1, z1, off=0.0)
        wet |= inb & (H < b["level_y"])
    step = np.zeros(F.shape, bool)
    vz, vx = np.abs(np.diff(H, axis=0)) > 1, np.abs(np.diff(H, axis=1)) > 1
    step[:-1, :] |= vz
    step[1:, :] |= vz
    step[:, :-1] |= vx
    step[:, 1:] |= vx
    floor = F & ~wet & ~step
    gx, gz = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(z0, z1 + 1) + 0.5)
    past = np.full(F.shape, np.inf)
    for _fa, d in field_dens(spec):
        past = np.minimum(past, np.hypot(gx - d["anchor"][0], gz - d["anchor"][2]) - d["leash"])
    return (x0, z0, x1, z1), floor, past


def check_floor(spec, g, R):
    (x0, z0, _x1, _z1), floor, past = usable_floor(spec, g)
    n = int(floor.sum())
    cov = floor & (past <= 0)
    if not n:
        R.err("floor", "the field has no usable floor (inside the polygon, dry, no step over one block)")
        return (x0, z0), floor, cov
    far = np.where(floor, past, -np.inf)
    i, j = np.unravel_index(int(np.argmax(far)), far.shape)
    R.note("floor: %d usable columns (inside the polygon, dry, no step over one block); the %d dens' ranges cover %d "
           "of them (%.1f%%); the usable column farthest from every range is %.0f past the nearest, at (%d, %d); "
           "dens %d, roster %d" % (n, len(field_dens(spec)), int(cov.sum()), 100.0 * cov.sum() / n, far[i, j],
                                   j + x0, i + z0, len(field_dens(spec)), len(spec["mega_field"]["layout"]["roster"])))
    return (x0, z0), floor, cov


def check_tiers(spec, fns, R):
    lay = spec["mega_field"]["layout"]
    tx, tz = spec["town"]["square"]["centre"]
    ds = [d for _fa, d in field_dens(spec)]
    for d in ds:
        far = math.hypot(d["anchor"][0] - tx, d["anchor"][2] - tz)
        want = lay["deeper_tier"] if far >= lay["deeper_from_town"] else lay["outer_tier"]
        if d["tier"] != want:
            R.err("tiers", "%s is %.0f from the Cutters' square: %s by deeper_from_town %d, but it is %s"
                  % (d["id"], far, want, lay["deeper_from_town"], d["tier"]))
        lvl = spec["farm_tiers"].get(d["tier"], {}).get("level")
        m = re.search(r"spawn_at \{[^}]*species:\"%s\"[^}]*level:(\d+)\}" % re.escape(d["species"]),
                      "\n".join(read_fn(fns, "megas/spawn_%s" % d["id"])))
        if lvl is None or not m or int(m.group(1)) != lvl:
            R.err("tiers", "%s: built level %s, farm_tiers.%s.level declares %s"
                  % (d["id"], m and m.group(1), d["tier"], lvl))
    # the roster dealt by distance, nearest first (ties: the roster order is the generator's own, so equal distances
    # are not judged)
    order = [sp for sp, _a in lay["roster"]]
    by = sorted(ds, key=lambda d: math.hypot(d["anchor"][0] - tx, d["anchor"][2] - tz))
    rank = [order.index(d["species"]) if d["species"] in order else -1 for d in by]
    if -1 in rank:
        R.err("tiers", "a field den's species is not in mega_field.layout.roster")
    elif any(rank[k] > rank[k + 1] for k in range(len(rank) - 1)
             if math.hypot(by[k]["anchor"][0] - tx, by[k]["anchor"][2] - tz) <
             math.hypot(by[k + 1]["anchor"][0] - tx, by[k + 1]["anchor"][2] - tz)):
        R.err("tiers", "the roster is not dealt by distance from the Cutters' square: nearest first is %s"
              % [d["species"] for d in by])


def read_fn(fns, name):
    return fns.get(name) or []


def check_keeper(spec, fns, callback, g, D, caps, R, data=DATA):
    rz = load_json(Path(data) / "rift_zones.json")
    for fa, d in field_dens(spec):
        did = d["id"]
        ax, ay, az = d["anchor"]
        tier = d.get("tier", fa["tier"])
        if tier not in D["tiers"]:
            R.err("level", "%s: tier %r is not one of section 13's outer/deeper field tiers" % (did, tier))
            continue
        T = D["tiers"][tier]
        zs = zone_of(rz, ax, az)
        if not zs:
            R.err("level", "%s at (%d, %d) is in no Rift zone: no badge gate, so no cap to set its level by" % (did, ax, az))
            continue
        badges = [p.get("threshold") for _z, p in zs if p.get("kind") == "badges"]
        if not badges:
            R.err("level", "%s: its zone %s is not gated on badges" % (did, [z for z, _p in zs]))
            continue
        cap = caps[min(max(badges), max(caps))]
        want = cap + T["offset"]
        body = "\n".join(read_fn(fns, "megas/spawn_%s" % did))
        m = re.search(r"spawn_at \{x:(-?\d+),y:(-?\d+),z:(-?\d+),species:\"([a-z_]+)\",aspect:\"([^\"]+)\",level:(\d+)\}", body)
        if not m:
            R.err("level", "%s: no megas/spawn_%s calling spawn_at in the built pack" % (did, did))
            continue
        x, y, z, sp, asp, lv = m.groups()
        if (int(x), int(y), int(z)) != (ax, ay, az) or sp != d["species"] or asp != d["aspect"]:
            R.err("level", "%s: spawns %s %s at (%s, %s, %s), not its %s %s at %s"
                  % (did, sp, asp, x, y, z, d["species"], d["aspect"], d["anchor"]))
        if int(lv) != want:
            R.err("level", "%s: built level %s, but its zone %s gates %d badges, cap %d, and the owner's %s offset is "
                           "+%d: want %d" % (did, lv, zs[0][0], max(badges), cap, tier, T["offset"], want))
        R.note("%s: zone %s, %d badges, cap %d, %s, level %s" % (did, zs[0][0], max(badges), cap, tier, lv))
        # drops and respawn, as load sets them
        load = "\n".join(read_fn(fns, "load"))
        pct = re.search(r"scoreboard players set #%s gm\.pct (\d+)" % re.escape(did), load)
        resp = re.search(r"scoreboard players set #%s gm\.resp (\d+)" % re.escape(did), load)
        if not pct or int(pct.group(1)) != T["pct"]:
            R.err("drops", "%s: drop chance %s, section 13.1's %s is %d%%" % (did, pct and pct.group(1), tier, T["pct"]))
        if not resp or int(resp.group(1)) != T["ticks"]:
            R.err("drops", "%s: respawn %s ticks, section 13.1's %s is %d" % (did, resp and resp.group(1), tier, T["ticks"]))
        for part in ("megas/bind_", "megas/hit_", "drops/roll_", "drops/slain_", "drops/hitter_"):
            if not read_fn(fns, part + did):
                R.err("drops", "%s: no %s%s in the built pack" % (did, part, did))
        for part in ("drops/roll_", "drops/slain_"):
            b = "\n".join(read_fn(fns, part + did))
            if b and not (re.search(r"random value 1\.\.100", b) and "#%s gm.pct" % did in b):
                R.err("drops", "%s: %s%s does not roll 1..100 against its gm.pct" % (did, part, did))
        if not re.search(r"\bdrops/roll_%s\b" % re.escape(did), "\n".join(read_fn(fns, "drops/fainted"))):
            R.err("drops", "%s: drops/fainted never rolls it" % did)
        # the leash
        lb = "\n".join(l for k, v in fns.items() if k.startswith("leash") for l in v)
        lm = re.search(r"tag=[\w.]*\.%s\] positioned (-?\d+) (-?\d+) (-?\d+) unless entity @s\[distance=\.\.(\d+)\] "
                       r"run tp @s (-?\d+) (-?\d+) (-?\d+)" % re.escape(did), lb)
        if not lm:
            R.err("keeper", "%s: no leash line returns its Mega" % did)
        else:
            v = [int(t) for t in lm.groups()]
            if v[:3] != [ax, ay, az] or v[4:] != [ax, ay, az] or v[3] != d["leash"]:
                R.err("keeper", "%s: the leash holds %s within %d, not its anchor within %d" % (did, v[:3], v[3], d["leash"]))
        # the approach box the keeper drives on holds the leash disc and its ground
        ap = fa["approach"]
        L = d["leash"]
        if not (ap[0] <= ax - L and ax + L <= ap[3] and ap[2] <= az - L and az + L <= ap[5]):
            R.err("keeper", "%s: its leash disc leaves its farm's approach box %s" % (did, ap))
        else:
            hs = [int(round(g(x, z))) for x in range(ax - L, ax + L + 1, 4) for z in range(az - L, az + L + 1, 4)
                  if math.hypot(x - ax, z - az) <= L]
            if min(hs) + 1 < ap[1] or max(hs) + 2 > ap[4]:
                R.err("keeper", "%s: ground in its leash disc runs y%d..%d, outside its approach box's y%d..%d"
                      % (did, min(hs), max(hs), ap[1], ap[4]))
    sa = "\n".join(read_fn(fns, "megas/spawn_at"))
    if "uncatchable" not in sa:
        R.err("level", "megas/spawn_at does not spawn uncatchable (section 13: 'Megas stay uncatchable')")
    if "drops/fainted" not in (callback or ""):
        R.err("drops", "the battle_fainted callback does not call drops/fainted")
    give = "\n".join(read_fn(fns, "drops/give"))
    item = re.findall(r'summon minecraft:item [^{]*\{Item:\{id:"([^"]+)",count:(\d+)\}', give)
    if [i for i, _c in item] != [D["raw"]] or spec["cutters"]["offer"]["raw"] != D["raw"]:
        R.err("drops", "drops/give summons %s, cutters.offer.raw is %s; section 13's currency is %s"
              % (item, spec["cutters"]["offer"]["raw"], D["raw"]))
    if "Owner set from entity @s UUID" not in give:
        R.err("drops", "drops/give does not make the dropped stone owner-only")
    cut = "\n".join(read_fn(fns, "cutters_place"))
    buys = re.findall(r'buy:\{id:"([^"]+)",count:(\d+)\}', cut)
    if not buys or {(i, int(c)) for i, c in buys} != {(D["raw"], D["price"])}:
        R.err("drops", "the Cutters' trades buy %s, not section 13's %d %s" % (sorted(set(buys)), D["price"], D["raw"]))


def tag_scheme(fns, live_id):
    """The per-den tag, as a live den's bind writes it: 'tag @s add <prefix><id>'."""
    for l in read_fn(fns, "megas/bind_%s" % live_id):
        m = re.fullmatch(r"tag @s add (\S+)" + re.escape(live_id), l.strip())
        if m:
            return m.group(1)
    return None


def check_retire(spec, fns, r9sx, R):
    live = {d["id"] for fa in spec["farms"] for d in fa["dens"]}
    gone = {d["id"]: d for fa in spec.get("superseded_farms", []) for d in fa["dens"] if d["id"] not in live}
    if not gone:
        R.err("retire", "data/gulch_mine.json superseded_farms names no retired den")
        return
    fd = field_dens(spec)
    prefix = tag_scheme(fns, fd[0][1]["id"]) if fd else None
    if prefix is None:
        R.err("retire", "cannot read the per-den tag off a live den's bind")
        return
    body = read_fn(fns, "megas/retire")
    killed = set(re.findall(r"^kill @e\[type=cobblemon:pokemon,tag=(\S+?)\]$", "\n".join(body), re.M))
    want = {prefix + i for i in gone}
    if killed != want:
        R.err("retire", "megas/retire kills %s; the retired dens' tags are %s (missing %s, extra %s)"
              % (len(killed), len(want), sorted(want - killed), sorted(killed - want)))
    for i in gone:
        if not any(l.startswith("data remove storage") and '{id:"%s"}' % i in l for l in body):
            R.err("retire", "megas/retire does not clear %s's drop storage" % i)
    for name, lines in fns.items():
        if name == "megas/retire":
            continue
        hit = [i for i in gone if any(re.search(r"\b%s\b" % re.escape(i), l) for l in lines)]
        if hit:
            R.err("retire", "%s still names retired den(s) %s" % (name, hit))
    # R9SX
    steps = [tuple(s) for s in r9sx]
    fn = [k for k, s in enumerate(steps) if s[0] == "fn" and s[1].endswith("/megas/retire")]
    if len(fn) != 1:
        R.err("retire", "R9SX runs megas/retire %d time(s), not once" % len(fn))
        return
    k = fn[0]
    adds = [tuple(int(v) for v in s[1].split()[2:]) for s in steps[:k] if s[0] == "cmd" and s[1].startswith("forceload add")]
    rems = [tuple(int(v) for v in s[1].split()[2:]) for s in steps[k + 1:] if s[0] == "cmd" and s[1].startswith("forceload remove")]
    if not any(s[0] == "wait" and s[1] >= 1 for s in steps[:k]):
        R.err("retire", "R9SX does not wait between its forceload and megas/retire (the entities must load)")
    if sorted(adds) != sorted(rems):
        R.err("retire", "R9SX releases %d of the %d holds it adds" % (len(set(adds) & set(rems)), len(adds)))
    for h in adds:
        cx = abs((max(h[0], h[2]) >> 4) - (min(h[0], h[2]) >> 4)) + 1
        cz = abs((max(h[1], h[3]) >> 4) - (min(h[1], h[3]) >> 4)) + 1
        if cx * cz > 256:
            R.err("retire", "R9SX hold %s is %d chunks: the server refuses a forceload over 256" % (h, cx * cz))
    for i, d in gone.items():
        x, _y, z = d["anchor"]
        L = d.get("leash", 32)
        if not any(min(h[0], h[2]) <= x - L and x + L <= max(h[0], h[2]) and min(h[1], h[3]) <= z - L
                   and z + L <= max(h[1], h[3]) for h in adds):
            R.err("retire", "R9SX holds no box covering %s's anchor +- its leash %d" % (i, L))


def replay(lines):
    state = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = FILL.match(line)
        if m and not m.group(8):
            x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        state[(x, y, z)] = m.group(7)
            continue
        m = SETBLOCK.match(line)
        if m:
            state[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = m.group(4)
    return state


def check_lairs(spec, rec, lairs, r9md, R, data=DATA):
    poly = spec["mega_field"]["polygon"]
    fd = {d["id"]: d for _fa, d in field_dens(spec)}
    gone = {d["id"] for fa in spec.get("superseded_farms", []) for d in fa["dens"]} - set(fd)
    have = {r["den"]: r for r in rec["dens"]}
    for i in sorted(set(fd) - set(have)):
        R.err("lairs", "field den %s has no lair record (data/mega_dens.json dens)" % i)
    for i in sorted(set(have) - set(fd)):
        R.err("lairs", "lair record %s is not a field den%s" % (i, " (it is retired)" if i in gone else ""))
    spawn = set(load_json(Path(data) / "spawn_blocks.json")["blocks"])
    policy = load_json(Path(data) / "spawn_block_policy.json")
    white = {b for w in policy.get("whitelist") or [] if "mega_dens" in (w.get("scope") or "") for b in w["blocks"]}
    route = [tuple(p) for pts in load_json(Path(data) / "route_paths.json")["paths"].values() for p in pts]
    owner = {}
    # a lair is keyed by its DEN's id (mega_dens/<den id>), never its species: a species may hold several dens
    for i, d in sorted(fd.items()):
        sp = d["species"]
        if i in have and have[i]["species"] != sp:
            R.err("lairs", "%s is a %s in the farms and a %s in its lair record" % (i, sp, have[i]["species"]))
        if i not in lairs:
            R.err("lairs", "no built lair mega_dens/%s for %s (%s)" % (i, i, sp))
            continue
        st = replay(lairs[i])
        bad = sorted({s.split("[")[0].split("{")[0] for s in st.values()} & spawn - white)
        if bad:
            R.err("lairs", "%s's lair writes %s, a spawn condition (data/spawn_blocks.json) no mega_dens policy allows"
                  % (i, bad))
        cols = {(x, z) for (x, _y, z) in st}
        if not cols:
            R.err("lairs", "%s's lair writes nothing" % i)
            continue
        shared = sorted(c for c in cols if c in owner)
        if shared:
            R.err("lairs", "%s's and %s's lairs both write %d column(s), e.g. %s"
                  % (owner[shared[0]], i, len(shared), shared[0]))
        for c in cols:
            owner.setdefault(c, i)
        out = [c for c in sorted(cols) if not _in_poly_pt(poly, c[0] + 0.5, c[1] + 0.5)]
        if out:
            R.err("lairs", "%s's lair writes %d column(s) outside the field, e.g. %s" % (i, len(out), out[0]))
        dmin = near_points(cols, route)
        if dmin < 128:
            R.err("lairs", "%s's lair writes %.1f from the critical path (data/route_paths.json): under 128 "
                           "(tools/mega_dens_audit.py footprint rule)" % (i, dmin))
        R.note("lair %s (%s): %d cells, %d columns, nearest critical path %.1f" % (i, sp, len(st), len(cols), dmin))
    extra = sorted(set(lairs) - set(fd))
    if extra:
        R.err("lairs", "built lairs for no field den: %s%s"
              % (extra, " (retired: %s)" % sorted(set(extra) & gone) if set(extra) & gone else ""))
    ran = sorted(s[1].rsplit("/", 1)[-1] for s in (tuple(x) for x in r9md) if s[0] == "fn")
    want = sorted(fd)
    if ran != want:
        R.err("lairs", "R9MD runs lairs %s, the field's dens are %s (missing %s, extra %s)"
              % (len(ran), len(want), sorted(set(want) - set(ran)), sorted(set(ran) - set(want))))
    return set(owner)


# ---------------------------------------------------------------------------------------------- the borders
def world_marks(spec, g, data=DATA):
    """What a border must keep off, from the data (the lair audit's footprint rule, tools/mega_dens_audit.py): the
    critical path's points, the Rift zones' wall columns, posts and guard points, placements, town footprints, and a
    painted-water test on the rounded heightmap."""
    import water_mask
    bodies, sea = water_mask.bodies(), water_mask.sea_level()
    rz = load_json(Path(data) / "rift_zones.json")
    built = []
    for cut in rz.get("cuts") or []:
        built += [(c[0], c[1], "wall " + cut["id"]) for c in cut.get("line") or []]
    for zid, zz in rz["zones"].items():
        if str(zz.get("status", "")).startswith("SUPERSEDED"):
            continue
        built += [(p["at"][0], p["at"][1], "%s post %s" % (zid, p.get("id"))) for p in zz.get("posts") or []
                  if isinstance(p.get("at"), list)]
        gd = zz.get("guard") or {}
        built += [(gd[k][0], gd[k][1], "%s guard %s" % (zid, k)) for k in ("edge_at", "inside_at")
                  if isinstance(gd.get(k), list)]
    built += [(p["position"]["x"], p["position"]["z"], "placement " + p["id"])
              for p in load_json(Path(data) / "placements.json")["placements"] if isinstance(p.get("position"), dict)]
    towns = [(t["id"], t["footprint"]) for t in load_json(Path(data) / "towns.json")["towns"]
             if all(k in (t.get("footprint") or {}) for k in ("min_x", "min_z", "max_x", "max_z"))]

    def gr(x, z):
        return int(round(g(x, z)))
    return {"route": [tuple(p) for pts in load_json(Path(data) / "route_paths.json")["paths"].values() for p in pts],
            "built": built, "towns": towns,
            "wet": lambda x, z: water_mask.level_at(x, z, gr, bodies, sea)[0] is not None,
            "spawn": set(load_json(Path(data) / "spawn_blocks.json")["blocks"]),
            "white": {b for w in load_json(Path(data) / "spawn_block_policy.json").get("whitelist") or []
                      if "mega_borders" in (w.get("scope") or "") for b in w["blocks"]}}


def base(state):
    return state.split("[")[0].split("{")[0]


def check_borders(spec, bdoc, bfns, dens_rec, lair_cols, g, floor, R, marks):
    """bfns: {"<a>__<b>": lines} of the built border functions. floor: check_floor's ((x0, z0), floor, covered)."""
    # keyed by the DEN's id, never its species (2026-10-04: two dens of one species may share a border)
    dens = {d["id"]: d for _fa, d in field_dens(spec)}
    pal = {r["den"]: r for r in dens_rec["dens"]}
    want = {frozenset((a["id"], b["id"])): (a, b, s, o) for a, b, s, o in overlaps(spec)}
    have = {}
    for name, lines in sorted(bfns.items()):
        parts = name.split("__")
        if len(parts) != 2 or parts[0] == parts[1] or not all(p in dens for p in parts):
            R.err("borders", "border function %s names no two field dens" % name)
            continue
        if frozenset(parts) in have:
            R.err("borders", "%s and %s are both built for one pair of dens" % (have[frozenset(parts)][0], name))
            continue
        have[frozenset(parts)] = (name, replay(lines))
    for k in sorted(set(want) - set(have), key=sorted):
        a, b, _s, o = want[k]
        R.err("borders", "%s and %s overlap %.1f blocks and no border is built between them" % (a["id"], b["id"], o))
    for k in sorted(set(have) - set(want), key=sorted):
        R.err("borders", "border %s is built between two dens whose ranges do not overlap" % have[k][0])
    ids = set(bdoc["blocks"]["ids"])
    shared_scar = set(bdoc["scar"])
    loose = set(bdoc["rubble"]["loose_blocks"])
    kmin = bdoc["kill"]["min_overlap"]
    keep = bdoc["keep"]
    anchors = [(d["anchor"][0], d["anchor"][2]) for d in dens.values()]
    poly, zone, grid = spec["mega_field"]["polygon"], spec["zone"]["polygon"], spec["grid"]
    by_col, kills, empty = {}, 0, []
    for k in sorted(have, key=sorted):
        if k not in want:
            continue
        name, st = have[k]
        a, b, s, ov = want[k]
        if not st:
            # judged below, once every other border's columns are known: empty is right only where the lens has no
            # free dressing column at all
            empty.append((name, a, b, ov))
            continue
        cols = sorted({(x, z) for (x, _y, z) in st})
        for c in cols:
            if c in by_col:
                R.err("borders", "%s and %s both write column %s" % (by_col[c], name, c))
            by_col.setdefault(c, name)
        out = [c for c in cols if not (in_range(a, *c) and in_range(b, *c))]
        if out:
            R.err("borders", "%s: %d of its %d columns lie outside the overlap of the two ranges (not inside both), "
                             "e.g. %s" % (name, len(out), len(cols), out[0]))
        gy = {c: int(round(g(*c))) for c in cols}
        high = [(x, y, z) for (x, y, z) in st if not gy[(x, z)] <= y <= gy[(x, z)] + bdoc["max_rise"]]
        if high:
            R.err("borders", "%s: %d block(s) off round(ground) .. +%d, e.g. %s (ground y%d)"
                  % (name, len(high), bdoc["max_rise"], high[0], gy[(high[0][0], high[0][2])]))
        bases = {base(v) for v in st.values()}
        if bases - ids:
            R.err("borders", "%s writes %s, not in data/mega_borders.json blocks.ids" % (name, sorted(bases - ids)))
        bad = sorted(bases & marks["spawn"] - marks["white"])
        if bad:
            R.err("borders", "%s writes %s, a spawn condition (data/spawn_blocks.json) no mega_borders policy allows"
                  % (name, bad))
        # the scar: the ground itself, from the shared palette or the two dens' own; never the other side's own block
        pa, pb = pal.get(a["id"]), pal.get(b["id"])
        if not pa or not pb:
            R.err("borders", "%s: no data/mega_dens.json lair record for %s" % (name, a["id"] if not pa else b["id"]))
            continue
        sa, sb = set(pa["scrape"]), set(pb["scrape"])
        scar = {(x, z): base(v) for (x, y, z), v in st.items() if y == gy[(x, z)]}
        if not scar:
            R.err("borders", "%s scars no ground" % name)
        stray = sorted({v for v in scar.values()} - shared_scar - sa - sb)
        if stray:
            R.err("borders", "%s's scar writes %s, in neither den's scrape palette nor the shared scar" % (name, stray))
        wrong, own = [], {a["id"]: 0, b["id"]: 0}
        for (x, z), v in scar.items():
            # the radical line of the two ranges: the side whose range the column is deeper inside
            pwr_a = (x + 0.5 - a["anchor"][0]) ** 2 + (z + 0.5 - a["anchor"][2]) ** 2 - a["leash"] ** 2
            pwr_b = (x + 0.5 - b["anchor"][0]) ** 2 + (z + 0.5 - b["anchor"][2]) ** 2 - b["leash"] ** 2
            if pwr_a == pwr_b:
                continue
            mine, theirs, who = (sa, sb, a["id"]) if pwr_a < pwr_b else (sb, sa, b["id"])
            if v in theirs - mine - shared_scar:
                wrong.append(((x, z), v))
            if v in mine:
                own[who] += 1
        if wrong:
            R.err("borders", "%s: %d scar column(s) take the OTHER den's own scrape block on this den's side, e.g. %s"
                  % (name, len(wrong), wrong[0]))
        for who, n in own.items():
            if not n:
                R.err("borders", "%s: no scar column on %s's side is from its own scrape palette" % (name, who))
        rock = {(x, y, z): base(v) for (x, y, z), v in st.items() if y > gy[(x, z)] and base(v) not in KILL_BLOCKS}
        stones = set(pa.get("boulder") or []) | set(pb.get("boulder") or []) | loose
        if not rock:
            R.err("borders", "%s: no broken rock above the scar" % name)
        elif set(rock.values()) - stones:
            R.err("borders", "%s: rock %s is neither den's boulder block nor rubble.loose_blocks"
                  % (name, sorted(set(rock.values()) - stones)))
        skulls = [p for p, v in st.items() if base(v) == "minecraft:skeleton_skull"]
        bones = [p for p, v in st.items() if base(v) == "minecraft:bone_block"]
        if ov >= kmin and len(skulls) != 1:
            R.err("borders", "%s: ranges overlap %.1f (kill.min_overlap %s) and it carries %d carcass skull(s), not one"
                  % (name, ov, kmin, len(skulls)))
        if ov < kmin and (skulls or bones):
            R.err("borders", "%s: ranges overlap only %.1f, under kill.min_overlap %s, and it carries a kill"
                  % (name, ov, kmin))
        kills += 1 if skulls else 0
        # where it may not write
        near_a = [c for c in cols if any(math.hypot(c[0] - x, c[1] - z) <= keep["anchor_clear"] for x, z in anchors)]
        if near_a:
            R.err("borders", "%s writes %d column(s) within anchor_clear %s of a den's anchor, e.g. %s"
                  % (name, len(near_a), keep["anchor_clear"], near_a[0]))
        r = keep["lair_clear"]
        near_l = [c for c in cols if any((c[0] + i, c[1] + j) in lair_cols for i in range(-r, r + 1)
                                         for j in range(-r, r + 1) if math.hypot(i, j) <= r)]
        if near_l:
            R.err("borders", "%s writes %d column(s) within lair_clear %s of a column a lair writes, e.g. %s"
                  % (name, len(near_l), r, near_l[0]))
        footprint(name, cols, poly, zone, grid, marks, R)
    (fx0, fz0), F, cov = floor
    for name, a, b, ov in empty:
        free = free_columns(a, b, floor, anchors, keep, lair_cols, by_col, poly, zone, grid, marks)
        if free:
            R.err("borders", "%s writes nothing, but its lens (overlap %.1f) has %d free dressing column(s), e.g. %s: "
                             "in both ranges, on the usable floor, clear of every anchor, lair, other border and "
                             "footprint rule" % (name, ov, len(free), free[0]))
        else:
            R.note("borders: %s writes nothing; its lens (overlap %.1f) has no free dressing column" % (name, ov))
    n = int(cov.sum())
    frac = len(by_col) / float(n or 1)
    if frac > bdoc["coverage_cap"]:
        R.err("borders", "the borders write %d columns, %.1f%% of the %d usable columns inside a range: over "
                         "coverage_cap %.1f%%" % (len(by_col), 100 * frac, n, 100 * bdoc["coverage_cap"]))
    R.note("borders: %d built, %d kills, %d columns written, %.1f%% of the %d usable columns inside a range (cap %.1f%%); "
           "%d write nothing" % (len(have), kills, len(by_col), 100 * frac, n, 100 * bdoc["coverage_cap"], len(empty)))
    return {name: sorted({(x, z) for (x, _y, z) in st}) for name, st in have.values()}


def footprint(name, cols, poly, zone, grid, marks, R):
    out = [c for c in cols if not _in_poly_pt(poly, c[0] + 0.5, c[1] + 0.5)]
    if out:
        R.err("borders", "%s writes %d column(s) outside the field's polygon, e.g. %s" % (name, len(out), out[0]))
    inz = [c for c in cols if _in_poly_pt(zone, c[0] + 0.5, c[1] + 0.5)]
    if inz:
        R.err("borders", "%s writes inside the gulch's zone, e.g. %s" % (name, inz[0]))
    ing = [c for c in cols if grid["x"][0] <= c[0] <= grid["x"][1] and grid["z"][0] <= c[1] <= grid["z"][1]]
    if ing:
        R.err("borders", "%s writes inside the gulch's block box (gulch_mine.json grid), e.g. %s" % (name, ing[0]))
    for tid, fp in marks["towns"]:
        if any(fp["min_x"] <= c[0] <= fp["max_x"] and fp["min_z"] <= c[1] <= fp["max_z"] for c in cols):
            R.err("borders", "%s writes inside %s's footprint" % (name, tid))
    if marks["route"]:
        dr = near_points(cols, marks["route"])
        if dr < 128:
            R.err("borders", "%s writes %.1f from the critical path (data/route_paths.json): under 128" % (name, dr))
    xs, zs = [c[0] for c in cols], [c[1] for c in cols]
    for px, pz, what in marks["built"]:
        if min(xs) - 32 <= px <= max(xs) + 32 and min(zs) - 32 <= pz <= max(zs) + 32 and \
                near_points(cols, [(px, pz)]) < 32:
            R.err("borders", "%s writes within 32 of %s at (%d, %d)" % (name, what, px, pz))
    wet = [c for c in cols if marks["wet"](*c)]
    if wet:
        R.err("borders", "%s writes %d column(s) under painted water, e.g. %s" % (name, len(wet), wet[0]))


def free_columns(a, b, floor, anchors, keep, lair_cols, taken, poly, zone, grid, marks):
    """The columns a border between dens a and b could dress, by this audit's own rules (never tools/mega_borders.py's
    dressing floor): in both ranges (in_range); on the usable floor computed here (check_floor); beyond keep.anchor_clear
    of every anchor and keep.lair_clear of every column a built lair writes; written by no other border; and passing
    every footprint rule a written border column is held to (footprint()). Sorted."""
    (fx0, fz0), F, _cov = floor
    ax, az, la = a["anchor"][0], a["anchor"][2], a["leash"]
    bx, bz, lb = b["anchor"][0], b["anchor"][2], b["leash"]
    x0, x1 = int(math.floor(max(ax - la, bx - lb))) - 1, int(math.ceil(min(ax + la, bx + lb))) + 1
    z0, z1 = int(math.floor(max(az - la, bz - lb))) - 1, int(math.ceil(min(az + la, bz + lb))) + 1
    ac, lc = keep["anchor_clear"], keep["lair_clear"]
    out = []
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if not (in_range(a, x, z) and in_range(b, x, z)) or (x, z) in taken:
                continue
            i, j = z - fz0, x - fx0
            if not (0 <= i < F.shape[0] and 0 <= j < F.shape[1] and F[i, j]):
                continue
            if any(math.hypot(x - px, z - pz) <= ac for px, pz in anchors):
                continue
            if any((x + u, z + v) in lair_cols for u in range(-lc, lc + 1) for v in range(-lc, lc + 1)
                   if math.hypot(u, v) <= lc):
                continue
            probe = Report()
            footprint("probe", [(x, z)], poly, zone, grid, marks, probe)
            if not probe.errors:
                out.append((x, z))
    return out


def check_border_steps(cols_by, r9mb, R):
    """R9MB: each border run once, while a hold covering all its columns is in force, every hold released."""
    held, adds, rems, ran = [], [], [], {}
    waited = False
    for s in (tuple(x) for x in r9mb):
        if s[0] == "cmd" and s[1].startswith("forceload add"):
            h = tuple(int(v) for v in s[1].split()[2:])
            held.append(h)
            adds.append(h)
            waited = False
        elif s[0] == "cmd" and s[1].startswith("forceload remove"):
            h = tuple(int(v) for v in s[1].split()[2:])
            rems.append(h)
            if h in held:
                held.remove(h)
        elif s[0] == "wait":
            waited = waited or s[1] >= 1
        elif s[0] == "fn":
            name = s[1].rsplit("/", 1)[-1]
            ran[name] = ran.get(name, 0) + 1
            cols = cols_by.get(name)
            if cols is None:
                R.err("order", "R9MB runs %s, which is no built border" % s[1])
                continue
            if not cols:
                continue    # a border that writes nothing (judged in check_borders) needs no hold
            if not any(all(min(h[0], h[2]) <= x <= max(h[0], h[2]) and min(h[1], h[3]) <= z <= max(h[1], h[3])
                           for x, z in cols) for h in held):
                R.err("order", "R9MB runs %s with no hold covering every column it writes" % name)
            if not waited:
                R.err("order", "R9MB runs %s without a wait after its hold" % name)
    for name in cols_by:
        if ran.get(name, 0) != 1:
            R.err("order", "R9MB runs border %s %d time(s), not once" % (name, ran.get(name, 0)))
    if sorted(adds) != sorted(rems) or held:
        R.err("order", "R9MB leaves %d hold(s) of %d unreleased" % (len(held), len(adds)))
    for h in adds:
        cx = abs((max(h[0], h[2]) >> 4) - (min(h[0], h[2]) >> 4)) + 1
        cz = abs((max(h[1], h[3]) >> 4) - (min(h[1], h[3]) >> 4)) + 1
        if cx * cz > 256:
            R.err("order", "R9MB hold %s is %d chunks: the server refuses a forceload over 256" % (h, cx * cz))


def check_order(reapply_src, prepare_names, R):
    body = reapply_src[reapply_src.index("def steps("):]
    pos = {}
    for sid in ("R9S", "R9SX", "R9MD", "R9MB", "R9E"):
        m = re.search(r'\(\s*"%s"\s*,' % sid, body)
        pos[sid] = m.start() if m else None
    if None in pos.values() or not pos["R9S"] < pos["R9SX"] < pos["R9MD"] < pos["R9MB"] < pos["R9E"]:
        R.err("order", "reapply.steps does not run R9S < R9SX < R9MD < R9MB < R9E: %s" % pos)
    if not re.search(r'\(\s*"R9MB"[^\n]*\n\s*mega_borders\.placement_steps\(\)\)', body):
        R.err("order", "R9MB does not run mega_borders.placement_steps()")
    m = re.search(r"^SERVER_PACKS = \(", reapply_src, re.M)
    code = "\n".join(l.split("#", 1)[0] for l in reapply_src[m.end():].splitlines()) if m else ""
    if '"cobblers_mega_borders"' not in code[:code.find(")")]:
        R.err("order", "cobblers_mega_borders is not in reapply.SERVER_PACKS: the borders would never be installed")
    if not re.search(r'\(\s*"R9SX"[^\n]*\n\s*gulch_mine\.retire_steps\(\)\)', body):
        R.err("order", "R9SX does not run gulch_mine.retire_steps()")
    n = list(prepare_names)

    def at(name):
        return n.index(name) if name in n else None
    a, b, c, d = at("mega_field:check"), at("gulch_mine:build"), at("mega_dens:build"), at("mega_field_audit")
    e = at("mega_borders:build")
    if a is None or b is None or not a < b:
        R.err("order", "prepare does not run mega_field:check before gulch_mine:build")
    if c is None or e is None or not c < e:
        R.err("order", "prepare does not run mega_borders:build after mega_dens:build (it keeps clear of the lairs)")
    if d is None or b is None or c is None or e is None or not (d > b and d > c and d > e):
        R.err("order", "prepare does not run mega_field_audit after gulch_mine:build, mega_dens:build and "
                       "mega_borders:build")


def audit(spec, g, basin, fns, callback, rec, lairs, r9sx, r9md, reapply_src=None, prepare_names=None, D=None, caps=None,
          borders=None):
    """borders: (data/mega_borders.json, {"<a>__<b>": built lines}, R9MB's steps). Without it the borders are not
    audited, and that is itself a problem: the field is not clean while its borders are unchecked."""
    R = Report()
    D = D or design()
    caps = caps or cap_table()
    sold = re.findall(r'sell:\{id:"mega_showdown:([a-z_]+)"', "\n".join(read_fn(fns, "cutters_place")))
    check_area(spec, basin, D, R)
    check_dens(spec, g, basin, D, R, sold)
    check_crowding(spec, R)
    floor = check_floor(spec, g, R)
    check_tiers(spec, fns, R)
    check_keeper(spec, fns, callback, g, D, caps, R)
    check_retire(spec, fns, r9sx, R)
    lair_cols = check_lairs(spec, rec, lairs, r9md, R)
    if borders is None:
        R.err("borders", "not audited: no data/mega_borders.json, built border functions and R9MB steps were given")
    else:
        bdoc, bfns, r9mb = borders
        cols_by = check_borders(spec, bdoc, bfns, rec, lair_cols, g, floor, R, world_marks(spec, g))
        check_border_steps(cols_by, r9mb, R)
    if reapply_src is not None:
        check_order(reapply_src, prepare_names or [], R)
    for t, v in D["tiers"].items():
        if t == "field_deeper" and not (D["deeper_band"][0] <= v["offset"] <= D["deeper_band"][1]
                                        and D["deeper_pct_band"][0] <= v["pct"] <= D["deeper_pct_band"][1]):
            R.err("design", "13.1's deeper tier (+%d, %d%%) is outside section 13's table (+%d..+%d, %d-%d%%)"
                  % ((v["offset"], v["pct"]) + D["deeper_band"] + D["deeper_pct_band"]))
        if t == "field_outer" and (v["pct"] != D["outer_pct"] or v["offset"] != D["owner_outer_level"] - D["cap_ref"]):
            R.err("design", "13.1's outer tier (+%d, %d%%) is not section 13's (+%d, %d%%)"
                  % (v["offset"], v["pct"], D["owner_outer_level"] - D["cap_ref"], D["outer_pct"]))
    return R


# ---------------------------------------------------------------------------------------------- inputs from disk
def pack_functions(pack, folder):
    base = Path(pack) / folder
    if not base.is_dir():
        raise SystemExit("mega_field_audit: no %s: build the pack first" % base)
    return {p.relative_to(base).with_suffix("").as_posix(): p.read_text(encoding="utf-8").splitlines()
            for p in base.rglob("*.mcfunction")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root")
    ap.add_argument("--gulch-pack", default=str(GULCH_PACK))
    ap.add_argument("--dens-pack", default=str(DENS_PACK))
    ap.add_argument("--borders-pack", default=str(BORDERS_PACK))
    a = ap.parse_args(argv)
    import types
    import ground as G
    g = G.load(a.source_root)
    spec = load_json(DATA / "gulch_mine.json")
    rec = load_json(DATA / "mega_dens.json")
    fns = pack_functions(a.gulch_pack, GULCH_FN)
    cb = Path(a.gulch_pack) / CALLBACK
    callback = cb.read_text(encoding="utf-8") if cb.is_file() else ""
    lairs = pack_functions(a.dens_pack, DENS_FN)
    # the re-application steps are the generators' OUTPUT, checked here, never their geometry
    import gulch_mine
    import mega_borders
    import mega_dens
    import reapply
    r9sx = gulch_mine.retire_steps(spec)
    r9md = mega_dens.placement_steps(g=g)
    r9mb = mega_borders.placement_steps()
    bfns = pack_functions(a.borders_pack, BORDERS_FN)
    names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root=a.source_root or "", server_dir=""))]
    R = audit(spec, g, load_basin(), fns, callback, rec, lairs, r9sx, r9md,
              (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8"), names,
              borders=(load_json(DATA / "mega_borders.json"), bfns, r9mb))
    for n in R.notes:
        print("note: %s" % n)
    # KNOWN findings, reported and owned by the builder (tests/test_mega_field_audit.py KNOWN, strict xfail there): printed
    # as KNOWN and not failed here, so prepare runs while the fix is owed; a NEW problem still fails it. EMPTY since
    # 2026-10-04: the per-den field closed both findings of the species-keyed one; add a pattern only with its xfail
    known = []
    unk = [e for e in R.errors if not any(k.search(e) for k in known)]
    for e in R.errors:
        print("%s %s" % ("PROBLEM" if e in unk else "KNOWN", e))
    print("mega_field_audit: %s (%d problem(s), %d known)" % ("clean" if not unk else "FAILED", len(unk),
                                                             len(R.errors) - len(unk)))
    return 1 if unk else 0


if __name__ == "__main__":
    raise SystemExit(main())
