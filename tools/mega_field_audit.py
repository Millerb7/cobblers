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

What is checked is the generators' OUTPUT: the polygon and farms as committed (or as a test's mutated generator
emits them), the built gulch functions and battle_fainted callback, the built lair functions, and the steps R9SX and
R9MD run (taken from the generators as output, as mega_dens_audit.py does).

  area      the polygon holds the owner's cursor and both section-13 points; overlaps the gulch zone by 0 columns;
            every basin column of the field's floor (the basin flooded from the owner's points, stopped by the gulch
            zone and the declared stem cut, trace.cut_near to the gulch zone's first vertex) is inside it, every basin
            column inside it is that floor, and no column of it lies more than rim_outset + tolerance outside the floor
  den       each field den: anchor inside the polygon and on the basin; y = round(ground) + 1; dry (no painted water
            within the pad); standable (its 3x3 within 1 block); its leash reaches neither the gulch zone nor
            any Rift zone's post or guard line;
            at least 128 from every critical-path point; no two dens' leash discs overlap; one den per species; a
            species whose stone (the aspect's, X or Y included) the Cutters sell; none on the broken-model list
  level     the den's zone gate (data/rift_zones.json boxes) gives the badges; the rctmod cap for those badges plus
            the owner's offset (13.1's level less the owner's cap of 50) is the level in the BUILT spawn function;
            spawn_at spawns uncatchable
  drops     per field den, the built load sets gm.pct and gm.resp to 13.1's numbers for its tier (outer 15% 10 min,
            deeper 30% 15 min; within section 13's 25-35%); bind_ hit_ roll_ slain_ hitter_ exist; the battle_fainted
            callback calls drops/fainted, which rolls every field den; give drops the raw stone section 13 names,
            owner-only; every Cutters trade buys that stone at section 13's price
  keeper    the leash returns each Mega to its own anchor at its den's leash; the farm's approach box holds the whole
            leash disc and its ground, so a player fighting the Mega keeps its keeper running
  retire    megas/retire kills exactly the per-den tag of every superseded den (the tag scheme read off a live den's
            bind) and clears its drop storage; no other function names a retired den; R9SX holds anchor +- leash of
            every retired den (each hold under 256 chunks), runs megas/retire after a wait, and releases every hold
  lairs     one lair per field den and none for a retired one; no lair writes a spawn condition no mega_dens policy
            whitelists; every lair write is inside the field polygon and 128 or more from every critical-path point;
            R9MD runs exactly the field dens' lairs
  order     reapply.steps: R9S < R9SX < R9MD < R9E; prepare: mega_field:check < gulch_mine:build, and this audit after
            gulch_mine:build and mega_dens:build

NOT covered (needs the server, EXP-054): that a Mega spawns and stands at the anchor, that FoF makes it hostile, that
the roll runs after a real win, that the item is refused to another player, that R9SX's forceload loads the retired
Megas' entities in its wait, and the tick cost of megas/watch.

  python tools/mega_field_audit.py [--source-root R] [--gulch-pack DIR] [--dens-pack DIR]
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
def raster(poly, x0, z0, x1, z1):
    """(z, x) bool mask of the columns x0..x1, z0..z1 whose centre is inside poly (even-odd)."""
    xs = np.arange(x0, x1 + 1) + 0.5
    zs = np.arange(z0, z1 + 1) + 0.5
    X, Z = np.meshgrid(xs, zs)
    res = np.zeros(X.shape, bool)
    n = len(poly)
    for i in range(n):
        xa, za = poly[i]
        xb, zb = poly[(i + 1) % n]
        if za == zb:
            continue
        c = (za > Z) != (zb > Z)
        with np.errstate(divide="ignore", invalid="ignore"):
            xi = xa + (Z - za) * (xb - xa) / (zb - za)
        res ^= c & (X < xi)
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
        if _in_poly_pt(zone, ax + 0.5, az + 0.5) or seg_dist(zone, ax + 0.5, az + 0.5) <= d["leash"]:
            R.err("den", "%s: its leash (%d) reaches the gulch zone (%.0f from it)"
                  % (did, d["leash"], seg_dist(zone, ax + 0.5, az + 0.5)))
        for what, (px, pz) in posts:
            if math.hypot(px - ax, pz - az) <= d["leash"]:
                R.err("den", "%s: its leash (%d) reaches the Rift zones' %s at (%d, %d)" % (did, d["leash"], what, px, pz))
        dr = near_points([(ax, az)], route)
        if dr < 128:
            R.err("den", "%s: anchor %.0f from the critical path (data/route_paths.json): under 128" % (did, dr))
        if sp in seen:
            R.err("den", "%s and %s are both %s: one den per species (the lair is named after it)" % (seen[sp], did, sp))
        seen[sp] = did
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
    for (fa, d), (fb, e) in [(p, q) for i, p in enumerate(dens) for q in dens[i + 1:]]:
        s = math.hypot(d["anchor"][0] - e["anchor"][0], d["anchor"][2] - e["anchor"][2])
        if s < d["leash"] + e["leash"]:
            R.err("den", "%s and %s are %.0f apart: their leash discs overlap" % (d["id"], e["id"], s))


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
    for i, d in sorted(fd.items()):
        sp = d["species"]
        if i in have and have[i]["species"] != sp:
            R.err("lairs", "%s is a %s in the farms and a %s in its lair record" % (i, sp, have[i]["species"]))
        if sp not in lairs:
            R.err("lairs", "no built lair mega_dens/%s for %s" % (sp, i))
            continue
        st = replay(lairs[sp])
        bad = sorted({s.split("[")[0].split("{")[0] for s in st.values()} & spawn - white)
        if bad:
            R.err("lairs", "%s's lair writes %s, a spawn condition (data/spawn_blocks.json) no mega_dens policy allows"
                  % (sp, bad))
        cols = {(x, z) for (x, _y, z) in st}
        if not cols:
            R.err("lairs", "%s's lair writes nothing" % sp)
            continue
        out = [c for c in sorted(cols) if not _in_poly_pt(poly, c[0] + 0.5, c[1] + 0.5)]
        if out:
            R.err("lairs", "%s's lair writes %d column(s) outside the field, e.g. %s" % (sp, len(out), out[0]))
        dmin = near_points(cols, route)
        if dmin < 128:
            R.err("lairs", "%s's lair writes %.1f from the critical path (data/route_paths.json): under 128 "
                           "(tools/mega_dens_audit.py footprint rule)" % (sp, dmin))
        R.note("lair %s: %d cells, %d columns, nearest critical path %.1f" % (sp, len(st), len(cols), dmin))
    extra = sorted(set(lairs) - {d["species"] for d in fd.values()})
    if extra:
        R.err("lairs", "built lairs for no field den: %s" % extra)
    ran = sorted(s[1].rsplit("/", 1)[-1] for s in (tuple(x) for x in r9md) if s[0] == "fn")
    want = sorted(d["species"] for d in fd.values())
    if ran != want:
        R.err("lairs", "R9MD runs lairs %s, the field's dens are %s" % (ran, want))


def check_order(reapply_src, prepare_names, R):
    body = reapply_src[reapply_src.index("def steps("):]
    pos = {}
    for sid in ("R9S", "R9SX", "R9MD", "R9E"):
        m = re.search(r'\(\s*"%s"\s*,' % sid, body)
        pos[sid] = m.start() if m else None
    if None in pos.values() or not pos["R9S"] < pos["R9SX"] < pos["R9MD"] < pos["R9E"]:
        R.err("order", "reapply.steps does not run R9S < R9SX < R9MD < R9E: %s" % pos)
    if not re.search(r'\(\s*"R9SX"[^\n]*\n\s*gulch_mine\.retire_steps\(\)\)', body):
        R.err("order", "R9SX does not run gulch_mine.retire_steps()")
    n = list(prepare_names)

    def at(name):
        return n.index(name) if name in n else None
    a, b, c, d = at("mega_field:check"), at("gulch_mine:build"), at("mega_dens:build"), at("mega_field_audit")
    if a is None or b is None or not a < b:
        R.err("order", "prepare does not run mega_field:check before gulch_mine:build")
    if d is None or b is None or c is None or not (d > b and d > c):
        R.err("order", "prepare does not run mega_field_audit after gulch_mine:build and mega_dens:build")


def audit(spec, g, basin, fns, callback, rec, lairs, r9sx, r9md, reapply_src=None, prepare_names=None, D=None, caps=None):
    R = Report()
    D = D or design()
    caps = caps or cap_table()
    sold = re.findall(r'sell:\{id:"mega_showdown:([a-z_]+)"', "\n".join(read_fn(fns, "cutters_place")))
    check_area(spec, basin, D, R)
    check_dens(spec, g, basin, D, R, sold)
    check_keeper(spec, fns, callback, g, D, caps, R)
    check_retire(spec, fns, r9sx, R)
    check_lairs(spec, rec, lairs, r9md, R)
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
    import mega_dens
    import reapply
    r9sx = gulch_mine.retire_steps(spec)
    r9md = mega_dens.placement_steps(g=g)
    names = [n for n, _f in reapply.prepare_jobs(types.SimpleNamespace(source_root=a.source_root or "", server_dir=""))]
    R = audit(spec, g, load_basin(), fns, callback, rec, lairs, r9sx, r9md,
              (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8"), names)
    for n in R.notes:
        print("note: %s" % n)
    for e in R.errors:
        print("PROBLEM %s" % e)
    print("mega_field_audit: %s (%d problem(s))" % ("clean" if not R.errors else "FAILED", len(R.errors)))
    return 1 if R.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
