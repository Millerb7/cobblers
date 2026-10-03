#!/usr/bin/env python
"""Offline audit of the shore, the wrecks and Rift debris, and the two sea caves (tools/sea_life.py ->
build/datapacks/cobblers_sea_life).

Independent of tools/sea_life.py: nothing is imported from it and nothing is read from derived/sea_life/plan.json. The
pack's functions are parsed and REPLAYED in index order (tools/water_life_replay.py) over a world made only from the
canonical heightmap (tools/ground.py, rounded) and tools/water_mask.py's painting rule, and checked against data/ and
the OTHER packs' functions:

  flora     kelp, kelp stems, seagrass and tall seagrass only in cells that held sea water, on a full block (or their
            own stem / lower half), every stem under kelp, every kelp top at age 25; seagrass inside a flats box of
            data/water_shape.json coasts; kelp tops never within 2 of the surface (WATER_LIFE 3: "never within 2 of
            the surface", i.e. at most sea - 3), and at most sea - 3 inside a gate's clearance
  coral     every coral block, coral, fan and pickle stands inside the Relic reef platform (coasts.relic_reef: its
            sector widened by sector_fade_deg, out to outer_radius max + drop_width_blocks) on 3+ deep ground
            (min_depth); every coral block touches water; every plant and fan is waterlogged on a full block
  finds     the build writes away from the caves clustered (link distance: half of the closest two finds the data
            allows, debris_line_spacing_blocks[0] - 2 x debris_line_jitter_blocks); a cluster whose lowest footprint
            ground is at least bands.surf.depth[0] deep is a find. Each is seated (its base within 2 of its lowest
            footprint ground + 1), wholly under the surface, and at most sea - 3 inside coasts.gate_line_clearance_
            blocks of a gate crossing; counts per band measured from the clusters: total in finds.total, the Surf
            share in finds.surf_share, a cache share in finds.cache_share; every Surf find carries a light or a mast
  flooded   no air written outside the caves, and nothing in a water cell that leaves it dry (a door, a bed, a fence
            gate, a waterloggable block without waterlogged=true): a dry cell under water is a place to breathe
  cut       nothing opens natural ground except the two caves (rock pools are rims, never cuts)
  clear     no write in a town (footprint + water_shape margin), Pacifidlog (data/sea_town.json rects and data/
            towns.json sea_town, + pacifidlog_margin_blocks), Driftmouth Isle (+ skirt) or a column the sea drift
            pack writes (+ drift_margin_blocks), a ferry stop (+ dock_margin_blocks) or lane, a dive portal (+ margin)
            or a column the portals pack writes, a legendary's spawn_free_zone or mouth (+ legendary_margin_blocks)
            or a column the legendaries pack writes, a placement (+ margin), the Deep (+ margin), a lake basin
  surfacing the Windward Sink: every breach of open water is at one mouth (at most max_mouth_cells, at the data's
            mouth, 20-40 deep); no breach into air (the crack is glass); rock shell >= 4 (and the data's own cover,
            shell + export_tolerance + natural_seabed) round every opened cell except the mouth's and the crack's
            neighbourhood; fluids bounded (no water beside or over air) and the chamber pool's surface one flat y;
            every dry floor cell reachable on foot from the pool; a lower bound on the underwater path from the open
            surface to the pool longer than a Surf player swims before the knockout, computed from data/blackout.json
            (surf_bonus_ticks + vanilla's 300 air ticks + one pulse_ticks, the second hit) at data/ferries.json's
            measured swim speed
  seacave   the waterline cave: no breach into sea water and no opened cell within water_clearance of it (roofed cells
            the full shell); a roofed cell's rock cover straight up at least shell + export_tolerance; every floor cell
            reachable on foot from the beach, from a mouth column at the tide line
  light     block light from the pack's lanterns reaches every roofed dry floor cell of both caves (a dark floor
            spawns hostiles)
  cache     every barrel has a data/rewards.json record whose container is it and whose trigger box holds it (and a
            place a player can be); every sea_life_* record's container is a barrel; every item in them is one another
            record already carries
  blocks    no light block, bubble column, soul sand or magma block
  foreign   no cell in common with cobblers_lake_life, cobblers_sea_drift, cobblers_portals, cobblers_legendaries, and
            no column in common unless over a sealed roof of theirs
  limits    tools/function_limits.py finds nothing the server would refuse

What this does NOT cover: whether kelp, seagrass and coral live there in game (P6), whether an air chamber at depth
stays dry (P1), whether a lantern is seen from the surface (P4), the swim itself (EXP-042's speed is relayed, a line in
data/ferries.json), and every gate line whose endpoints the data does not state directly (see gate_lines()).

  python tools/sea_life_audit.py [--source-root DIR] [--pack DIR]   writes derived/sea_life/audit.json; exit 1 on any
                                                                    problem
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from collections import defaultdict, deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL       # noqa: E402
import water_life_replay as R      # noqa: E402

ROOT = R.ROOT
PACK = ROOT / "build" / "datapacks" / "cobblers_sea_life"
FN = ("data", "cobblers", "function", "sea_life")
OUT = ROOT / "derived" / "sea_life" / "audit.json"
FOREIGN = ("cobblers_lake_life", "cobblers_sea_drift", "cobblers_portals", "cobblers_legendaries")
VANILLA_AIR_TICKS = 300        # Entity.getMaxAirSupply() in vanilla 1.21.1
N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
H4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
CHECKS = ("parse", "flora", "coral", "finds", "flooded", "cut", "clear", "surfacing", "seacave", "light", "cache",
          "blocks", "foreign", "limits")
CORAL = ("tube", "brain", "bubble", "fire", "horn")


def bearing(dx, dz):
    """Compass bearing in degrees, 0 north (-z), 90 east (+x)."""
    return math.degrees(math.atan2(dx, -dz)) % 360.0


def in_sector(b, lo, hi, widen):
    lo, hi = (lo - widen) % 360.0, (hi + widen) % 360.0
    return lo <= b <= hi if lo <= hi else (b >= lo or b <= hi)


class Ctx:
    def __init__(self, terrain, spec, shape, blackout, swim_speed, rewards=(), towns=(), keep_out=(), lanes=(),
                 gate_lines=(), foreign=None, drift=None):
        self.t = terrain
        self.spec, self.shape, self.blackout = spec, shape, blackout
        self.swim_speed = float(swim_speed)
        self.rewards = list(rewards)
        self.towns = list(towns)               # [(id, box)]
        self.keep_out = list(keep_out)         # [(label, box)] every other excluded box, already grown
        self.lanes = list(lanes)               # [(label, [(x, z)], half)]
        self.gate_lines = list(gate_lines)     # [(id, (x, z), (x, z))]
        self.foreign = foreign or {}
        self.drift = drift                     # data/sea_drift.json or None

    @property
    def sea(self):
        return self.t.sea


def _rects(o, out):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "rect" and isinstance(v, list) and len(v) == 4 and all(isinstance(q, (int, float)) for q in v):
                out.append(tuple(int(q) for q in v))
            else:
                _rects(v, out)
    elif isinstance(o, list):
        for v in o:
            _rects(v, out)
    return out


def _region_land(t, polys, step=1):
    pts = [p for ring in polys for p in ring]
    x0, z0 = int(min(p[0] for p in pts)), int(min(p[1] for p in pts))
    x1, z1 = int(max(p[0] for p in pts)), int(max(p[1] for p in pts))
    m = R.raster_polygons(polys, x0, z0, x1, z1)
    g = t.g.box(x0, z0, x1, z1) if hasattr(t.g, "box") else None
    land = m & (g >= t.sea)
    wet = g < t.sea
    shore = land & (np.roll(wet, 1, 0) | np.roll(wet, -1, 0) | np.roll(wet, 1, 1) | np.roll(wet, -1, 1))
    zz, xx = np.nonzero(shore)
    return np.stack([xx[::step] + x0, zz[::step] + z0], axis=1) if len(xx) else np.zeros((0, 2), int)


def gate_lines(t, shape, regions, sea_town_centre):
    """[(id, a, b)] the crossings data/water_shape.json declares gates (require_after.gate). Endpoints: `points` as the
    data states them; `shortest` as the closest pair of shore columns (land beside sea, ground >= sea level) inside
    the two regions' polygons; `to_town` from the re-sited town's centre to the nearest land column. A kind not
    modelled is returned as (id, None, None) and reported, never silently dropped."""
    out = []
    for c in shape["crossings"]:
        if not (c.get("require_after") or {}).get("gate"):
            continue
        k = c["kind"]
        if k == "points":
            out.append((c["id"], tuple(c["from"]), tuple(c["to"])))
        elif k == "shortest":
            A = _region_land(t, regions[c["from_region"]], 1)
            B = _region_land(t, regions[c["to_region"]], 1)
            if not len(A) or not len(B):
                out.append((c["id"], None, None))
                continue
            best = (float("inf"), None)
            for s in range(0, len(A), 2000):
                a = A[s:s + 2000]
                d2 = ((a[:, None, 0] - B[None, :, 0]) ** 2 + (a[:, None, 1] - B[None, :, 1]) ** 2)
                i = int(np.argmin(d2))
                if d2.flat[i] < best[0]:
                    ia, ib = divmod(i, len(B))
                    best = (float(d2.flat[i]), (tuple(int(v) for v in a[ia]), tuple(int(v) for v in B[ib])))
            out.append((c["id"],) + best[1])
        elif k == "to_town" and sea_town_centre:
            cx, cz = sea_town_centre
            for r in (200, 400, 800, 1600):
                x0, z0, x1, z1 = cx - r, cz - r, cx + r, cz + r
                g = t.g.box(x0, z0, x1, z1)
                zz, xx = np.nonzero(g >= t.sea)
                if len(xx):
                    d2 = (xx + x0 - cx) ** 2 + (zz + z0 - cz) ** 2
                    i = int(np.argmin(d2))
                    if d2[i] <= r * r:
                        out.append((c["id"], (cx, cz), (int(xx[i] + x0), int(zz[i] + z0))))
                        break
            else:
                out.append((c["id"], None, None))
        else:
            out.append((c["id"], None, None))
    return out


def load_ctx(source_root=None, with_gates=True):
    import ground as G
    import water_mask as WM
    t = R.Terrain(G.load(source_root), WM.sea_level(), WM.bodies())
    spec = R.load("sea_life.json")
    shape = R.load("water_shape.json")
    prot = shape["protect"]
    ex = spec["exclusions"]
    towns = R.town_boxes(R.load("towns.json"), prot)
    keep = []
    # Pacifidlog: every rect of data/sea_town.json and data/towns.json sea_town's footprint, grown
    pm = int(ex["pacifidlog_margin_blocks"])
    st = R.load("sea_town.json")
    for r in _rects(st, []):
        keep.append(("pacifidlog rect %s" % (r,), (min(r[0], r[2]) - pm, min(r[1], r[3]) - pm,
                                                   max(r[0], r[2]) + pm, max(r[1], r[3]) + pm)))
    for tid, box in R.town_boxes(R.load("towns.json"), {"town_margin_blocks": pm}):
        if tid == "sea_town":
            keep.append(("pacifidlog old footprint", box))
    # docks: ferries.json and ferry_docks.json points, + dock_margin
    dm = int(ex["dock_margin_blocks"])
    stops = {}
    fdoc = R.load("ferries.json")
    for d in fdoc["docks"]:
        # data/sea_life.json exclusions.dock_sources: "data/ferries.json docks (landing.at, else near)"
        pt = (d.get("landing") or {}).get("at") or d.get("near")
        if pt:
            stops[d["id"]] = (pt[0], pt[-1])
            keep.append(("ferry stop %s" % d["id"], R.chebyshev_box(pt[0], pt[-1], dm)))
    for d in R.load("ferry_docks.json")["docks"]:
        for p in ([d["near"]] if d.get("near") else []) + ([d["shore"]["at"]] if (d.get("shore") or {}).get("at") else []):
            keep.append(("ferry dock %s" % d["id"], R.chebyshev_box(p[0], p[1], dm)))
    lanes = []
    lh = int(ex["ferry_lane_half_width_blocks"])
    for ln in fdoc["lines"]:
        if ln.get("status") == "retired" or ln.get("retired"):
            continue
        pts = [stops[s] for s in ln.get("stops", []) if s in stops]
        if len(pts) >= 2:
            lanes.append(("ferry lane %s" % ln["id"], pts, lh))
    # portals
    pg = int(ex["portal_margin_blocks"])
    for p in R.load("portals.json")["portals"]:
        keep.append(("portal %s" % p["id"], R.chebyshev_box(p["at"][0], p["at"][1], 2 + pg)))
    # legendaries
    lg = int(ex["legendary_margin_blocks"])
    for e in R.load("legendaries.json")["encounters"]:
        z = e.get("spawn_free_zone")
        if z:
            keep.append(("legendary %s spawn_free_zone" % e["id"], (z[0] - lg, z[1] - lg, z[2] + lg, z[3] + lg)))
        if e.get("mouth"):
            keep.append(("legendary %s mouth" % e["id"], R.chebyshev_box(e["mouth"][0], e["mouth"][1], lg)))
    # every adopted site, scheduled or not (tools/adopted_sites.py): a scheduled site's position is in
    # data/placements.json, and reading `placement` alone dropped it from this keep-out
    import adopted_sites
    for s in adopted_sites.sites(R.load("adopted_legendary_sites.json")):
        x0, z0, x1, z1 = adopted_sites.footprint(s, R.load("placements.json")["placements"])
        keep.append(("adopted legendary %s" % s.get("id"), (x0 - lg, z0 - lg, x1 + lg, z1 + lg)))
    # placements
    plm = int(ex["placement_margin_blocks"])
    for p in R.load("placements.json")["placements"]:
        pos = p.get("position")
        if pos and "x" in pos:
            keep.append(("placement %s" % p["id"], R.chebyshev_box(pos["x"], pos["z"], plm)))
    # the Deep
    dpm = int(ex["deep_margin_blocks"])
    b = R.load("rift_regions.json")["regions"]["the_deep"]["bbox"]
    keep.append(("the Deep", (b[0] - dpm, b[1] - dpm, b[2] + dpm, b[3] + dpm)))
    # First Cast's hole
    h = shape["coasts"]["first_cast_hole"]
    keep.append(("first cast hole", R.chebyshev_box(h["centre"][0], h["centre"][1],
                                                    int(h["radius"]) + int(ex["first_cast_hole_margin_blocks"]))))
    # Driftmouth Isle: its square out to radius + skirt, grown by the drift margin
    drift = R.load("sea_drift.json")
    isl = drift["island"]
    rr = int(isl["radius"]) + int(isl["skirt"]) + int(ex["drift_margin_blocks"])
    keep.append(("driftmouth isle", R.chebyshev_box(isl["centre"]["x"], isl["centre"]["z"], rr)))
    for i, v in enumerate(drift["route"]["vertices"]):
        keep.append(("sea drift vertex %d" % i, R.chebyshev_box(v[0], v[1], int(ex["drift_margin_blocks"]))))
    lanes.append(("sea drift route", [tuple(v) for v in drift["route"]["vertices"]],
                  int(drift["tube"]["r"]) + int(drift["shell_r"]) + int(ex["drift_margin_blocks"])))
    gates = []
    if with_gates:
        rdoc = R.load("regions.json")
        regions = {r["id"]: r["polygons"] for r in rdoc["regions"] if r.get("polygons")}
        gates = gate_lines(t, shape, regions, tuple(st["site"]["centre"]))
    swim = float(fdoc["swim_model"]["speed_blocks_per_second"])
    foreign = {name: R.pack_columns(ROOT / "build" / "datapacks" / name) for name in FOREIGN}
    return Ctx(t, spec, shape, R.load("blackout.json"), swim, R.load("rewards.json")["rewards"], towns, keep, lanes,
               gates, foreign, drift)


# ------------------------------------------------------------------------------------------------- the world


def opened_cells(ctx, W):
    """Cells the pack leaves non-full where the heightmap world had ground, or where it had itself written a full
    block first: the caves' voids."""
    full_before = set()
    out = set()
    for cmd, cell, grp, prev in W.landed:
        if R.is_full(cmd.block):
            full_before.add(cell)
    for cell, b in W.w.items():
        if not R.is_full(b) and (ctx.t.base(*cell) == R.NATURAL or cell in full_before):
            out.add(cell)
    return out


def components(cells):
    cells = set(cells)
    seen, comps = set(), []
    for c in cells:
        if c in seen:
            continue
        comp, dq = [], deque([c])
        seen.add(c)
        while dq:
            x, y, z = dq.popleft()
            comp.append((x, y, z))
            for a, b, d in N6:
                q = (x + a, y + b, z + d)
                if q in cells and q not in seen:
                    seen.add(q)
                    dq.append(q)
        comps.append(comp)
    return comps


def outside(ctx, W, cell, cave):
    """True for a cell that is open to the outside world: unwritten water or air, or a written non-full cell that is
    not part of this cave."""
    if cell in cave:
        return False
    b = W.w.get(cell)
    if b is None:
        return ctx.t.base(*cell) != R.NATURAL
    return not R.is_full(b)


def passable(b):
    i = R.bid(b)
    return R.is_air(b) or i.endswith("rail") or i.endswith("_carpet")


def floor_ok(b):
    i = R.bid(b)
    return R.is_full(b) or i.endswith("_slab") or i.endswith("_stairs") or i == "minecraft:barrel"


def walk(W, starts, allowed):
    """Standing cells reachable on foot from `starts`: a standing cell is passable at the feet and the head with a
    floor under it; a move goes to a 4-neighbour at most one block up or down, with headroom for the jump or the
    drop. `allowed(cell)` limits the search."""
    def stand(c):
        x, y, z = c
        return passable(W.at(x, y, z)) and passable(W.at(x, y + 1, z)) and floor_ok(W.at(x, y - 1, z))
    seen = set(s for s in starts if stand(s))
    dq = deque(seen)
    while dq:
        x, y, z = dq.popleft()
        for a, c in H4:
            for dy in (0, 1, -1):
                q = (x + a, y + dy, z + c)
                if q in seen or not allowed(q) or not stand(q):
                    continue
                if dy == 1 and not passable(W.at(x, y + 2, z)):
                    continue
                if dy == -1 and not passable(W.at(q[0], q[1] + 2, q[2])):
                    continue
                seen.add(q)
                dq.append(q)
    return seen


def floor_cells(W, cave):
    out = set()
    for (x, y, z) in cave:
        if passable(W.at(x, y, z)) and passable(W.at(x, y + 1, z)) and floor_ok(W.at(x, y - 1, z)):
            out.add((x, y, z))
    return out


def light_flood(W, sources, transparent):
    light = {}
    for c, lv in sources:
        light[c] = max(light.get(c, 0), lv)
    frontier = sorted(sources, key=lambda s: -s[1])
    buckets = defaultdict(list)
    for c, lv in sources:
        buckets[lv].append(c)
    for lv in range(15, 0, -1):
        for (x, y, z) in buckets.get(lv, []):
            if light.get((x, y, z), 0) != lv:
                continue
            for a, b, d in N6:
                q = (x + a, y + b, z + d)
                if lv - 1 > light.get(q, 0) and transparent(W.at(*q)):
                    light[q] = lv - 1
                    buckets[lv - 1].append(q)
    del frontier
    return light


def surf_air_blocks(ctx):
    w = ctx.blackout["water"]
    ticks = int(w["surf_bonus_ticks"]) + VANILLA_AIR_TICKS + int(w["pulse_ticks"])
    return ticks / 20.0 * ctx.swim_speed, ticks


# ------------------------------------------------------------------------------------------------------- checks


def check_flora(ctx, W, P, gate_ix):
    sea = ctx.sea
    kspec = ctx.spec["shore"]["kelp"]
    flats = [tuple(f["box"]) for f in ctx.shape["coasts"]["flats"]]
    bad = defaultdict(list)
    n = defaultdict(int)
    tops_minus_sea = defaultdict(int)
    for (x, y, z), b in W.w.items():
        i = R.bid(b)
        if i not in ("minecraft:kelp", "minecraft:kelp_plant", "minecraft:seagrass", "minecraft:tall_seagrass"):
            continue
        n[i] += 1
        gy, lv, body = ctx.t.column(x, z)
        if body != "sea" or not (gy < y <= lv):
            bad[i].append(((x, y, z), "not in a cell of sea water (ground y%d, body %s)" % (gy, body)))
            continue
        below = W.at(x, y - 1, z)
        if i == "minecraft:seagrass" or (i == "minecraft:tall_seagrass" and R.props(b).get("half") == "lower"):
            if not R.is_full(below):
                bad[i].append(((x, y, z), "on %s" % below))
            if not any(R.in_box(f, x, z) for f in flats):
                bad[i].append(((x, y, z), "outside every flats box (seagrass is on the sandy flats only)"))
        if i == "minecraft:tall_seagrass":
            half = R.props(b).get("half")
            other = W.at(x, y + (1 if half == "lower" else -1), z)
            if not (R.bid(other) == i and R.props(other).get("half") != half):
                bad[i].append(((x, y, z), "%s half without its other half" % half))
        if i in ("minecraft:kelp", "minecraft:kelp_plant"):
            if not (R.is_full(below) or R.bid(below) == "minecraft:kelp_plant"):
                bad[i].append(((x, y, z), "on %s" % below))
            if i == "minecraft:kelp_plant" and R.bid(W.at(x, y + 1, z)) not in ("minecraft:kelp", "minecraft:kelp_plant"):
                bad[i].append(((x, y, z), "a stem with %s above it" % W.at(x, y + 1, z)))
        if i == "minecraft:kelp":
            tops_minus_sea[y - sea] += 1
            if R.props(b).get("age") != "25":
                bad[i].append(((x, y, z), "age %s, not 25: it grows toward the surface" % R.props(b).get("age")))
            if y > sea - 3:
                bad["kelp top within 2 of the surface"].append(((x, y, z), "top y%d, %d under the surface y%d"
                                                                % (y, sea - y, sea)))
            if (x, z) in gate_ix and y > sea - 3:
                bad["kelp top in a gate's clearance"].append(((x, y, z), "top y%d" % y))
    for i, lst in sorted(bad.items()):
        for c, why in lst[:3]:
            P["flora"].append("%s at %s: %s" % (i, c, why))
        if len(lst) > 3:
            P["flora"].append("... %d %s problems in all" % (len(lst), i))
    return {"counts": dict(n), "kelp_top_minus_sea": dict(sorted(tops_minus_sea.items()))}


def is_coral(b):
    i = R.bid(b)
    return any(i.startswith("minecraft:%s_coral" % c) or i.startswith("minecraft:dead_%s_coral" % c) for c in CORAL) \
        or i == "minecraft:sea_pickle"


def check_coral(ctx, W, P):
    rf = ctx.shape["coasts"]["relic_reef"]
    cx, cz = rf["centre"]
    rmax = float(rf["outer_radius"][1]) + float(rf["drop_width_blocks"])
    lo, hi = rf["sector_bearing_deg"]
    fade = float(rf["sector_fade_deg"])
    mind = int(rf["min_depth"])
    bad = defaultdict(list)
    far = []
    n = 0
    for (x, y, z), b in W.w.items():
        if not is_coral(b):
            continue
        n += 1
        r = math.hypot(x - cx, z - cz)
        gy, lv, body = ctx.t.column(x, z)
        if r > rmax:
            bad["beyond the reef's outermost radius %.0f (outer_radius max + drop_width_blocks)" % rmax].append(
                (x, y, z))
            far.append((r, ctx.sea - gy))
        if not in_sector(bearing(x - cx, z - cz), lo, hi, fade):
            bad["outside the reef's sector %s widened by sector_fade_deg %g" % (rf["sector_bearing_deg"], fade)].append(
                (x, y, z))
        if body != "sea" or ctx.sea - gy < mind:
            bad["on ground shallower than min_depth %d" % mind].append((x, y, z))
        i = R.bid(b)
        if i.endswith("_coral_block"):
            if not any(R.holds_water(W.at(x + a, y + c, z + d)) for a, c, d in N6):
                bad["a coral block with no water on any face (it dies)"].append((x, y, z))
        else:
            if R.props(b).get("waterlogged") != "true":
                bad["not waterlogged (it dies)"].append((x, y, z))
            if not R.is_full(W.at(x, y - 1, z)):
                bad["not on a full block"].append((x, y, z))
    for k, lst in sorted(bad.items()):
        P["coral"].append("%d coral writes %s, e.g. %s" % (len(lst), k, lst[0]))
    res = {"coral_writes": n}
    if far:
        res["beyond_radius"] = {"r": [round(min(f[0] for f in far), 1), round(max(f[0] for f in far), 1)],
                                "ground_depth": [min(f[1] for f in far), max(f[1] for f in far)]}
    return res


def find_clusters(ctx, W, exclude):
    spec = ctx.spec["finds"]
    link = (int(spec["debris_line_spacing_blocks"][0]) - 2 * int(spec["debris_line_jitter_blocks"])) // 2
    cells = [c for c, g in W.group.items() if g in ("3build", "5fittings") and c not in exclude]
    # union by column grid buckets of size link
    cols = defaultdict(list)
    for c in cells:
        cols[(c[0], c[2])].append(c)
    keys = list(cols)
    parent = {k: k for k in keys}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    grid = defaultdict(list)
    for k in keys:
        grid[(k[0] // link, k[1] // link)].append(k)
    for (gx, gz), ks in grid.items():
        near = [q for a in (-1, 0, 1) for b in (-1, 0, 1) for q in grid.get((gx + a, gz + b), [])]
        for k in ks:
            for q in near:
                if max(abs(k[0] - q[0]), abs(k[1] - q[1])) <= link:
                    ra, rb = find(k), find(q)
                    if ra != rb:
                        parent[ra] = rb
    groups = defaultdict(list)
    for k in keys:
        groups[find(k)] += cols[k]
    return list(groups.values()), link


def check_finds(ctx, W, P, caves, gate_ix):
    spec = ctx.spec["finds"]
    sea = ctx.sea
    exclude = set()
    for cave in caves:
        for (x, y, z) in cave:
            for a in range(-6, 7):
                for b in range(-6, 7):
                    for c in range(-6, 7):
                        exclude.add((x + a, y + b, z + c))
    clusters, link = find_clusters(ctx, W, exclude)
    surf_lo, surf_hi = spec["bands"]["surf"]["depth"]
    dive_lo, dive_hi = spec["bands"]["dive"]["depth"]
    finds, shore, odd = [], [], []
    for cl in clusters:
        cols = {(c[0], c[2]) for c in cl}
        gmin = min(ctx.t.column(x, z)[0] for x, z in cols)
        depth = sea - gmin
        if depth >= surf_lo:
            finds.append((cl, cols, gmin, depth))
        elif depth <= 2:
            shore.append(cl)
        else:
            odd.append((cl, depth))
    for cl, depth in odd[:5]:
        P["finds"].append("a cluster of %d build writes at %s on ground %d deep: neither a find (%d+ deep) nor a shore "
                          "feature" % (len(cl), min(cl), depth, surf_lo))
    surf = dive = 0
    with_cache = 0
    for cl, cols, gmin, depth in finds:
        base = min(c[1] for c in cl)
        top = max(c[1] for c in cl if not R.bid(W.w[c]).startswith("minecraft:kelp"))
        where = min(cl)
        if surf_lo <= depth <= surf_hi:
            surf += 1
            band = "surf"
        elif dive_lo <= depth <= dive_hi:
            dive += 1
            band = "dive"
        else:
            band = None
            P["finds"].append("the find at %s is %d deep, in no band" % (where, depth))
        if abs(base - (gmin + 1)) > 2:
            P["finds"].append("the find at %s is not seated: base y%d, lowest footprint ground y%d" % (where, base, gmin))
        if top > sea - 1:
            P["finds"].append("the find at %s breaks the surface: top y%d" % (where, top))
        if any(c in gate_ix for c in cols) and top > sea - 3:
            P["finds"].append("the find at %s tops out at y%d, within 2 of the surface, inside a gate's clearance"
                              % (where, top))
        if any(R.bid(W.w[c]) == "minecraft:barrel" for c in cl):
            with_cache += 1
        if band == "surf":
            lit = any(R.light_level(W.w[c]) > 0 for c in cl)
            mast = any(R.props(W.w[c]).get("axis") == "y" or R.bid(W.w[c]).endswith("_fence") for c in cl)
            if not (lit or mast):
                P["finds"].append("the Surf find at %s carries no light and no mast" % (where,))
    total = len(finds)
    lo, hi = spec["total"]
    if not lo <= total <= hi:
        P["finds"].append("%d finds, outside finds.total %s" % (total, spec["total"]))
    if total:
        s0, s1 = spec["surf_share"]
        if not s0 <= surf / float(total) <= s1:
            P["finds"].append("the Surf share is %d of %d (%.2f), outside finds.surf_share %s"
                              % (surf, total, surf / float(total), spec["surf_share"]))
        c0, c1 = spec["cache_share"]
        if not c0 <= with_cache / float(total) <= c1:
            P["finds"].append("%d of %d finds carry a barrel (%.2f), outside finds.cache_share %s"
                              % (with_cache, total, with_cache / float(total), spec["cache_share"]))
    return {"link_blocks": link, "finds": total, "surf": surf, "dive": dive, "with_cache": with_cache,
            "shore_clusters": len(shore), "unclassified": len(odd),
            "depths": sorted(d for _, _, _, d in finds)}


def check_flooded(ctx, W, P, cave_cells):
    """No dry cell in the sea outside the caves: a non-full block that holds no water, written where the sea was or
    beside a cell that holds water (set into the bed under the sea), is a pocket to breathe in. Air written into the
    sea outside the caves is counted, not failed: sea water beside it flows back in."""
    dry, air = [], []
    for (x, y, z), b in W.w.items():
        if (x, y, z) in cave_cells:
            continue
        base = ctx.t.base(x, y, z)
        if R.is_air(b):
            if base == R.WATER:
                air.append((x, y, z))
            continue
        if R.is_full(b) or R.holds_water(b):
            continue
        wet_beside = any(R.holds_water(W.at(x + a, y + c, z + d)) for a, c, d in N6)
        if base == R.WATER or (base == R.NATURAL and wet_beside):
            dry.append(((x, y, z), b))
    kinds = defaultdict(list)
    for c, b in dry:
        kinds[R.bid(b)].append(c)
    for k, cs in sorted(kinds.items()):
        P["flooded"].append("%d %s in sea water with no water in the cell, e.g. %s: a dry cell under water is a place "
                            "to breathe" % (len(cs), k, cs[0]))
    return {"dry_cells": len(dry), "air_outside_caves": len(air),
            "dry_at": sorted((c, ctx.sea - c[1]) for c, _b in dry)}


def check_cut(ctx, W, opened, caves, P):
    """Nothing opens natural ground outside the two caves into a dry void. A waterlogged partial block set into the
    seabed's top (a find's stair or fence seated one block in) holds water and is counted, not failed."""
    in_caves = set().union(*caves) if caves else set()
    cuts = [c for c in opened if c not in in_caves]
    dry = [c for c in cuts if not R.holds_water(W.w[c])]
    if dry:
        P["cut"].append("%d cells of natural ground opened dry outside the two caves, e.g. %s (%s)"
                        % (len(dry), min(dry), W.w[min(dry)]))
    return {"opened_outside_caves": len(cuts), "of_them_dry": len(dry)}


def check_clear(ctx, W, P):
    cols = {(c[0], c[2]) for c in W.w}
    ix = R.ColumnIndex(cols)
    hits = defaultdict(set)
    for tid, box in ctx.towns:
        for c in ix.in_box(box):
            hits["town %s" % tid].add(c)
    for label, box in ctx.keep_out:
        for c in ix.in_box(box):
            hits[label].add(c)
    for label, pts, half in ctx.lanes:
        for c in R.near_polyline(ix, pts, half):
            hits[label].add(c)
    lake = [c for c in cols if ctx.t.column(*c)[2] not in (None, "sea")]
    if lake:
        hits["a lake basin (the lake pack's)"] |= set(lake)
    for label, cs in sorted(hits.items()):
        P["clear"].append("%d write columns in %s, e.g. %s" % (len(cs), label, min(cs)))
    return {"write_columns": len(cols)}


def _surf_cave(ctx, caves):
    sc = ctx.spec["surfacing_cave"]
    cx, cz = sc["chamber"]["centre"]
    for cave in caves:
        if any(abs(x - cx) <= sc["chamber"]["half_x"] and abs(z - cz) <= sc["chamber"]["half_z"] for x, _, z in cave):
            return set(cave)
    return None


def check_surfacing(ctx, W, P, caves, res_light):
    sc = ctx.spec["surfacing_cave"]
    sea = ctx.sea
    cave = _surf_cave(ctx, caves)
    if not cave:
        P["surfacing"].append("no opened void at the data's chamber %s: the surfacing cave does not exist"
                              % (sc["chamber"]["centre"],))
        return {}
    res = {"cells": len(cave)}
    shell = int(sc["shell"])
    if shell < 4:
        P["surfacing"].append("data shell %d is under WATER_BUILD_PLAN 6.4's 4" % shell)
    cover = shell + int(sc["export_tolerance"]) + int(sc["natural_seabed"])
    # breaches
    wbreach, abreach = set(), set()
    for (x, y, z) in cave:
        for a, b, d in N6:
            q = (x + a, y + b, z + d)
            if q in cave or q in W.w:
                continue
            base = ctx.t.base(*q)
            if base == R.WATER:
                wbreach.add((x, y, z))
            elif base == R.AIR:
                abreach.add((x, y, z))
    res["water_breach_cells"] = len(wbreach)
    res["air_breach_cells"] = len(abreach)
    if abreach:
        P["surfacing"].append("%d opened cells touch open air, e.g. %s: the view must be sealed" % (len(abreach),
                                                                                                min(abreach)))
    mx, mz = sc["mouth"]
    r = int(sc["tube"]["r"])
    if not wbreach:
        P["surfacing"].append("no opened cell touches open water: there is no mouth")
    else:
        far = [c for c in wbreach if max(abs(c[0] - mx), abs(c[2] - mz)) > r + 1]
        if far:
            P["surfacing"].append("%d cells open into the sea away from the data's mouth %s, e.g. %s"
                                  % (len(far), sc["mouth"], min(far)))
        if len(wbreach) > int(sc["max_mouth_cells"]):
            P["surfacing"].append("%d mouth cells, over max_mouth_cells %d" % (len(wbreach), int(sc["max_mouth_cells"])))
        ys = [sea - c[1] for c in wbreach]
        res["mouth_depths"] = [min(ys), max(ys)]
        if min(ys) < 20 or max(ys) > 40:
            P["surfacing"].append("the mouth is %d-%d deep, not within WATER_LIFE 5's 20-40" % (min(ys), max(ys)))
    glass = [c for c, b in W.w.items() if R.bid(b) == "minecraft:glass"]
    # shell: no outside cell within `shell` (and the data's cover) of an opened cell, except near the mouth and crack
    near_ok = set()
    for c in list(wbreach) + [g for g in glass if any((g[0] + a, g[1] + b, g[2] + d) in cave for a, b, d in N6)]:
        x, y, z = c
        for a in range(-cover, cover + 1):
            for b in range(-cover, cover + 1):
                for d in range(-cover, cover + 1):
                    near_ok.add((x + a, y + b, z + d))
    worst = None
    thin = []
    for (x, y, z) in cave:
        if (x, y, z) in near_ok:
            continue
        best = None
        for a in range(-cover, cover + 1):
            for b in range(-cover, cover + 1):
                for d in range(-cover, cover + 1):
                    if (a or b or d) and outside(ctx, W, (x + a, y + b, z + d), cave):
                        dd = max(abs(a), abs(b), abs(d)) - 1
                        best = dd if best is None else min(best, dd)
        if best is not None:
            worst = best if worst is None else min(worst, best)
            if best < shell:
                thin.append(((x, y, z), best))
    res["shell_min_measured"] = worst
    if thin:
        P["surfacing"].append("%d opened cells with under %d blocks of rock to the outside, e.g. %s at %d"
                              % (len(thin), shell, thin[0][0], thin[0][1]))
    elif worst is not None and worst < cover:
        P["surfacing"].append("the cover is %d somewhere, under the data's claimed shell + tolerance + seabed = %d"
                              % (worst, cover))
    # fluids bounded and the pool flat
    water = {c for c in cave if R.holds_water(W.at(*c)) and not R.is_full(W.at(*c))}
    airc = {c for c in cave if R.is_air(W.at(*c))}
    surface_ys = set()
    spill = []
    for (x, y, z) in water:
        for a, b, d in N6:
            q = (x + a, y + b, z + d)
            if R.is_air(W.at(*q)):
                if (a, b, d) == (0, 1, 0):
                    surface_ys.add(y)
                else:
                    spill.append(((x, y, z), q))
    res["pool_surface_ys"] = sorted(surface_ys)
    if spill:
        P["surfacing"].append("%d water cells beside or over air, e.g. %s next to %s: the water flows"
                              % (len(spill), spill[0][0], spill[0][1]))
    if len(surface_ys) != 1:
        P["surfacing"].append("the cave's water meets air at %d heights %s, not one flat pool"
                              % (len(surface_ys), sorted(surface_ys)[:6]))
    elif int(sc["pool_level"]) not in surface_ys:
        P["surfacing"].append("the pool's surface is y%d, not the data's pool_level y%d" % (min(surface_ys),
                                                                                          int(sc["pool_level"])))
    # walk from the pool
    py = min(surface_ys) if surface_ys else int(sc["pool_level"])
    pool = {c for c in water if c[1] == py and R.is_air(W.at(c[0], c[1] + 1, c[2]))}
    starts = set()
    for (x, y, z) in pool:
        for a, c in H4:
            for dy in (1, 2):
                starts.add((x + a, py + dy, z + c))
    reach = walk(W, starts, lambda q: q in cave)
    floors = floor_cells(W, airc)
    traps = floors - reach
    res["floor_cells"], res["floor_reached"] = len(floors), len(floors & reach)
    if not floors:
        P["surfacing"].append("the cave has no dry floor")
    if traps:
        P["surfacing"].append("%d dry floor cells not reachable on foot from the pool, e.g. %s" % (len(traps),
                                                                                               min(traps)))
    # the underwater path: a lower bound from the open surface to the pool
    need, ticks = surf_air_blocks(ctx)
    res["surf_air_blocks"] = need
    res["surf_air_ticks"] = ticks
    if wbreach and pool:
        ratio = R.octile3_worst_ratio()
        dist = {}
        pq = []
        for b in wbreach:
            if b in water:
                d0 = 0.0
                dist[b] = d0
                heapq.heappush(pq, (d0, b))
        targets = set(pool)
        found = None
        while pq:
            d, c = heapq.heappop(pq)
            if d > dist.get(c, 1e18):
                continue
            if c in targets:
                found = (d, c)
                break
            x, y, z = c
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    for e in (-1, 0, 1):
                        if not (a or b or e):
                            continue
                        q = (x + a, y + b, z + e)
                        if q not in water:
                            continue
                        nd = d + math.sqrt(a * a + b * b + e * e)
                        if nd < dist.get(q, 1e18):
                            dist[q] = nd
                            heapq.heappush(pq, (nd, q))
        if found is None:
            P["surfacing"].append("no underwater path from the mouth to the pool: the pool is not the way in")
        else:
            # every path enters at a mouth cell; from the surface to that cell is at least the shallowest mouth cell's
            # depth under the sea, and from the mouth to the pool at least the 26-connected length over the ratio
            lower = (sea - max(b[1] for b in wbreach)) + found[0] / ratio
            res["underwater_path_lower_bound"] = round(lower, 1)
            res["octile_ratio"] = round(ratio, 4)
            if lower <= need:
                P["surfacing"].append("the underwater path to the pool is at least %.1f blocks, not longer than a Surf "
                                      "player's %.1f (data/blackout.json: %d ticks at %.1f blocks/s)"
                                      % (lower, need, ticks, ctx.swim_speed))
    # the cache and the crack
    barrels = [c for c in cave_adjacent(W, cave) if R.bid(W.w[c]) == "minecraft:barrel"]
    res["barrels"] = len(barrels)
    if not barrels:
        P["surfacing"].append("no barrel in the cave")
    crack = [g for g in glass if any((g[0] + a, g[1] + b, g[2] + d) in cave for a, b, d in N6)]
    if not crack:
        P["surfacing"].append("no glass crack beside the cave: no sealed view out")
    else:
        run = components_from(glass, crack)
        if not any(ctx.t.base(g[0] + a, g[1] + b, g[2] + d) == R.AIR and (g[0] + a, g[1] + b, g[2] + d) not in W.w
                   for g in run for a, b, d in N6):
            P["surfacing"].append("the glass crack never meets open air: the view sees rock")
    res["reach"] = reach
    return res


def cave_adjacent(W, cave):
    out = set()
    for (x, y, z) in cave:
        for a, b, d in N6:
            q = (x + a, y + b, z + d)
            if q in W.w and q not in cave:
                out.add(q)
    return out


def components_from(cells, seeds):
    cells = set(cells)
    seen = set(seeds)
    dq = deque(seeds)
    while dq:
        x, y, z = dq.popleft()
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                for d in (-1, 0, 1):
                    q = (x + a, y + b, z + d)
                    if q in cells and q not in seen:
                        seen.add(q)
                        dq.append(q)
    return seen


def check_seacave(ctx, W, P, caves, surf):
    sc = ctx.spec["shore"]["sea_cave"]
    sea = ctx.sea
    box = next(tuple(s["box"]) for s in ctx.shape["coasts"]["skerries"] if s["id"] == sc["coast_box"])
    cand = [set(c) for c in caves if (surf is None or not (set(c) & surf))
            and any(R.in_box(box, x, z) for x, _, z in c)]
    if not cand:
        P["seacave"].append("no opened void in the %s box: the waterline cave does not exist" % sc["coast_box"])
        return {}
    cave = max(cand, key=len)
    res = {"cells": len(cave), "other_voids_in_box": len(cand) - 1}
    clear = int(sc["descent"]["water_clearance"])
    shell = int(sc["shell"])
    roofed = {c for c in cave if any(R.is_full(W.at(c[0], yy, c[2])) for yy in range(c[1] + 1, c[1] + 40))}
    near_water = []
    for (x, y, z) in cave:
        # the data's rule: a roofed cell has the full shell from the sea; an open cleft cell at or under the sea
        # level keeps water_clearance from it; an open cell above the sea level is beach
        if (x, y, z) in roofed:
            lim = shell
        elif y <= sea:
            lim = clear
        else:
            continue
        for a in range(-lim, lim + 1):
            for b in range(-lim, lim + 1):
                for d in range(-lim, lim + 1):
                    q = (x + a, y + b, z + d)
                    if q not in W.w and q not in cave and ctx.t.base(*q) == R.WATER:
                        near_water.append(((x, y, z), q))
                        break
                else:
                    continue
                break
            else:
                continue
            break
    if near_water:
        P["seacave"].append("%d cave cells within their clearance of sea water, e.g. %s near %s"
                            % (len(near_water), near_water[0][0], near_water[0][1]))
    tol = int(sc["export_tolerance"])
    thin = []
    for (x, y, z) in roofed:
        if (x, y + 1, z) in cave:
            continue
        k, yy = 0, y + 1
        while R.is_full(W.at(x, yy, z)) and k < shell + tol + 1:
            k += 1
            yy += 1
        if k < shell + tol:
            thin.append(((x, y, z), k))
    if thin:
        P["seacave"].append("%d roofed cells with under %d blocks of rock over them, e.g. %s with %d"
                            % (len(thin), shell + tol, thin[0][0], thin[0][1]))
    # the walk from the beach
    starts, mouth_ok = set(), False
    for (x, y, z) in cave:
        for a, c in H4:
            q = (x + a, z + c)
            gy, lv, body = ctx.t.column(*q)
            if body is None and floor_ok(W.at(q[0], gy, q[1])) and passable(W.at(q[0], gy + 1, q[1])) \
                    and passable(W.at(q[0], gy + 2, q[1])):
                starts.add((q[0], gy + 1, q[1]))
                if gy in (sea, sea + 1) and any(ctx.t.column(q[0] + e, q[1] + f)[2] == "sea" for e, f in H4):
                    mouth_ok = True
    allowed = lambda q: q in cave or q in starts      # noqa: E731
    reach = walk(W, starts, allowed)
    floors = floor_cells(W, cave)
    traps = floors - reach
    res["floor_cells"], res["floor_reached"], res["beach_starts"] = len(floors), len(floors & reach), len(starts)
    if not floors:
        P["seacave"].append("the cave has no floor to walk")
    if traps:
        P["seacave"].append("%d floor cells not reachable on foot from the beach, e.g. %s" % (len(traps), min(traps)))
    if not mouth_ok:
        P["seacave"].append("no mouth column at the tide line (ground at the sea level or one above, beside the sea)")
    res["reach"] = reach
    res["cave"] = cave
    return res


def check_light(ctx, W, P, caves):
    srcs = [(c, R.light_level(b)) for c, b in W.w.items() if R.light_level(b) > 0]
    transparent = lambda b: not R.is_full(b) or R.bid(b) == "minecraft:glass"    # noqa: E731
    lit = light_flood(W, srcs, transparent)
    dark = []
    n = 0
    per = []
    for cave in caves:
        d0 = len(dark)
        for c in floor_cells(W, set(cave)):
            x, y, z = c
            if not any(R.is_full(W.at(x, yy, z)) for yy in range(y + 2, y + 40)):
                continue
            n += 1
            if lit.get(c, 0) < 1:
                dark.append(c)
        per.append({"cave_at": list(min(cave)), "dark": len(dark) - d0})
    if dark:
        P["light"].append("%d roofed floor cells of the caves at block light 0, e.g. %s" % (len(dark), min(dark)))
    return {"roofed_floor_cells": n, "dark": len(dark), "per_cave": per}


def check_cache(ctx, W, P, reach_sets, cave_sets=()):
    barrels = [c for c, b in W.w.items() if R.bid(b) == "minecraft:barrel"]
    recs = [r for r in ctx.rewards if r["id"].startswith("sea_life")]
    at = {tuple(r["container"]["at"]): r for r in recs if (r.get("container") or {}).get("at")}
    reach = set().union(*reach_sets) if reach_sets else set()
    for c in barrels:
        r = at.get(c)
        if r is None:
            P["cache"].append("the barrel at %s has no data/rewards.json record" % (c,))
            continue
        lo, hi = r["trigger"]["min"], r["trigger"]["max"]
        inside = lambda q: all(lo[i] <= q[i] <= hi[i] for i in range(3))       # noqa: E731
        if not inside(c):
            P["cache"].append("%s's trigger box does not hold its barrel %s" % (r["id"], c))
        box_cells = [(x, y, z) for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1)
                     for z in range(lo[2], hi[2] + 1)]
        in_cave = any((c[0] + a, c[1] + b_, c[2] + d) in cv for cv in cave_sets for a, b_, d in N6)
        if in_cave:
            ok = any(q in reach for q in box_cells)
            why = "no place reached on foot"
        else:
            ok = any(q != c and (R.holds_water(W.at(*q)) or (passable(W.at(*q)) and passable(
                W.at(q[0], q[1] + 1, q[2])) and floor_ok(W.at(q[0], q[1] - 1, q[2])))) for q in box_cells)
            why = "no water cell and no place to stand"
        if not ok:
            P["cache"].append("%s's trigger box holds %s: nobody gets there" % (r["id"], why))
    for r in recs:
        c = tuple((r.get("container") or {}).get("at") or ())
        if c not in barrels:
            P["cache"].append("%s's container %s is not a barrel this pack writes" % (r["id"], c))
    others = {it["item"] for r in ctx.rewards if not r["id"].startswith("sea_life") for it in r.get("contents") or []}
    for r in recs:
        for it in r.get("contents") or []:
            if it["item"] not in others:
                P["cache"].append("%s gives %s, which no other record carries" % (r["id"], it["item"]))
    return {"barrels": len(barrels), "records": len(recs)}


def check_blocks(ctx, W, P):
    seen = defaultdict(int)
    for b in W.w.values():
        if R.bid(b) in R.FORBIDDEN:
            seen[R.bid(b)] += 1
    for i, n in sorted(seen.items()):
        P["blocks"].append("%d %s written" % (n, i))
    cond = R.load("spawn_blocks.json")["blocks"]
    return {"spawn_condition_blocks": sorted({R.bid(b) for b in W.w.values() if R.bid(b) in cond})}


def check_foreign(ctx, W, P):
    ours = set(W.w)
    res = {}
    for name in FOREIGN:
        fc = ctx.foreign.get(name)
        if fc is None:
            res[name] = "absent: not checked"
            continue
        cells, sealed, open_ = R.foreign_overlap(ours, fc)
        res[name] = {"cells": len(cells), "columns_over_a_sealed_roof": len(sealed), "columns_open": len(open_)}
        if cells:
            P["foreign"].append("%d columns where we write a cell %s also writes, e.g. %s" % (len(cells), name,
                                                                                            cells[0]))
        if open_:
            P["foreign"].append("%d columns in common with %s not over a sealed roof of it, e.g. %s"
                                % (len(open_), name, sorted(open_)[0]))
    return res


def gate_index(ctx):
    cl = int(ctx.shape["coasts"]["gate_line_clearance_blocks"])
    cols = set()
    missing = []
    for gid, a, b in ctx.gate_lines:
        if a is None:
            missing.append(gid)
            continue
        x0, z0 = min(a[0], b[0]) - cl, min(a[1], b[1]) - cl
        x1, z1 = max(a[0], b[0]) + cl, max(a[1], b[1]) + cl
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if R.seg_dist(x, z, a[0], a[1], b[0], b[1]) <= cl:
                    cols.add((x, z))
    return cols, missing


def audit(ctx, pack=PACK):
    P = {k: [] for k in CHECKS}
    fn_dir = Path(pack).joinpath(*FN)
    try:
        parsed, unlisted = R.parse_pack(fn_dir)
    except R.ReplayError as e:
        P["parse"].append(str(e))
        return {"problems": P}
    for u in unlisted:
        P["parse"].append("%s.mcfunction is on disk but not in the index: it never runs" % u)
    W = R.World(ctx.t)
    try:
        n = R.replay(W, parsed)
    except R.ReplayError as e:
        P["parse"].append(str(e))
        return {"problems": P}
    res = {"functions": len(parsed), "commands": n, "cells": len(W.w), "dead_writes": len(W.dead)}
    gate_ix, missing = gate_index(ctx)
    res["gate_lines"] = [(g, a, b) for g, a, b in ctx.gate_lines]
    res["gate_lines_not_modelled"] = missing
    opened = opened_cells(ctx, W)
    caves = [set(c) for c in components(opened)]
    res["voids"] = sorted(len(c) for c in caves)
    surf = _surf_cave(ctx, caves)
    sea_cave_res = check_seacave(ctx, W, P, caves, surf)
    the_caves = [c for c in (surf, sea_cave_res.get("cave")) if c]
    cave_cells = set().union(*the_caves) if the_caves else set()
    res["flora"] = check_flora(ctx, W, P, gate_ix)
    res["coral"] = check_coral(ctx, W, P)
    res["finds"] = check_finds(ctx, W, P, the_caves, gate_ix)
    res["flooded"] = check_flooded(ctx, W, P, cave_cells)
    res["cut"] = check_cut(ctx, W, opened, the_caves, P)
    res["clear"] = check_clear(ctx, W, P)
    sres = check_surfacing(ctx, W, P, caves, None)
    reach_sets = [sres.pop("reach", set()), sea_cave_res.pop("reach", set())]
    sea_cave_res.pop("cave", None)
    res["surfacing"] = sres
    res["seacave"] = sea_cave_res
    res["light"] = check_light(ctx, W, P, the_caves)
    res["cache"] = check_cache(ctx, W, P, reach_sets, the_caves)
    res["blocks"] = check_blocks(ctx, W, P)
    res["foreign"] = check_foreign(ctx, W, P)
    for name, _cmds in parsed:
        lines = (fn_dir / (name + ".mcfunction")).read_text(encoding="utf-8").splitlines()
        for pr in FL.check_lines(lines, name)[:3]:
            P["limits"].append(str(pr))
    res["problems"] = P
    return res


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=None)
    p.add_argument("--pack", default=str(PACK))
    a = p.parse_args(argv)
    ctx = load_ctx(a.source_root)
    res = audit(ctx, Path(a.pack))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, indent=1, default=str) + "\n")
    probs = [(k, v) for k, lst in res["problems"].items() for v in lst]
    print(json.dumps({k: v for k, v in res.items() if k not in ("problems",)}, default=str)[:2500])
    for k, v in probs[:60]:
        print("PROBLEM [%s] %s" % (k, v))
    print("%d problems -> %s" % (len(probs), OUT.relative_to(ROOT)))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
