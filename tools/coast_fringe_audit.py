#!/usr/bin/env python
"""Independent audit of the coast fringe (U61/N2): does the COMPILED pack's coast-fringe content cover the coast it was
built for, stay out of every place nothing may spawn, and keep the encounter design's rules near the path?

Written by the test author (2026-10-09), not by the session that built tools/coast_fringe.py. Independence: it NEVER
imports tools/coast_fringe.py or tools/compile_spawns.py. It reads the compiled spawn pack
(build/datapacks/cobblers_spawns/data/<ns>/spawn_pool_world/<kind>/<area>.json) with its own parsing, the canonical
heightmap through tools/terrain.py (the loader, not a derivation), and the authored data files directly. Open sea and
coast distance are computed here by their own algorithms (run labelling for the sea, an exact two-pass city-block
distance transform), not by tools/coast_measure.py. A fringe entry is recognised by the compiled id contract the
compiler's docstring states ("ids <sub>_c<n>_<species>"), in that sub-region's own file.

COVERAGE (measured, reported, not a pass/fail threshold). Land = round(h) >= sea level (data/world.json); open sea =
round(h) < sea, 4-connected to the map's edge; coast land = land within city-block distance 1..32 of open sea (the
unit's own statement of its target, "land columns within 32 of open sea"). Uncovered = coast land under no grounded
box of a non-marine compiled area and outside every spawn-free zone; reported before (the pack with the fringe ids
removed) and after, plus the part under marine boxes only.

THE CHECKS (exit 1 if any fails). Every number is from a named source; none was tuned to the data.

  F1 exclusions   no fringe box shares a block with: a spawn-free zone (data/spawn_suppression.json: the League
                  precinct, the eight gyms, Hoopa's relic, the Heavens Arena); Victory Road's corridor boxes
                  (data/routes.json route victory_road); the Rift's extent (data/landmarks.json rift.extent.polygons);
                  any non-fringe box of another compiled sub-region, waterway or marine area (the fringe must fill a
                  gap, never double a table's weights). Habitat Blocks (data/habitat_blocks.json): a fringe box inside
                  the square of radius range_of_influence round a block with replace_spawns FALSE fails (the fringe
                  would mix into its pool); with replace_spawns true the block replaces the spawns (EXP-021, as
                  data/spawn_suppression.json habitat_blocks records), so the overlap is counted and reported only.
  F2 cap near     a fringe cell within 128 blocks (Chebyshev gap, ENCOUNTER_DESIGN.md section 1 "within 128 blocks"; the
     the path     heart rule's reading of the same number) of a route corridor box carries no level above the cap of the
                  EARLIEST leg among those routes (section 2: "everything a player meets on a leg can be caught on that
                  leg"; section 10: "the path is always catchable"). Leg = route `order` (victory_road is 9). Caps from
                  section 2's table: 20, 25, ... 55 for legs 1-8, 60 at 9. The same against a critical-path settlement
                  (data/towns.json, `order` 0-9; a town of order k is reached on leg max(k, 1)): within 128 of its
                  footprint, no level above that leg's cap.
  F3 finds near   a fringe cell of an OFF-path table (data/encounter_design.json placement "off") is not within 128 of a
     the path     route box: an off-path table carries a find (section 4 "find ... off-path only"; target 4 requires one
                  on every off-path table), so its roster beside a path puts the find beside it.
  F4 tier floor   REPORTED, NOT A FAILURE. Section 1: "A tier is never below the nearest route's leg" -- for an off-path
                  table, raised by barriers and island crossings (`tier_why`). Every fringe cell is off the path (the
                  nearest route is hundreds of blocks away), and which leg reaches an off-path coast cell is that
                  barrier judgement, not a nearest-box distance: no number derivable from the data decides it, so a
                  check would be a tuned threshold. Reported per owner: cells whose nearest route is a LATER leg than
                  the one nearest the owner's own boxes (with the margin by which it is nearer), and cells whose owner
                  table is already below its own nearest leg (the table's tier, not the fringe's doing).
  F5 owner        every fringe cell's owner is the sub-region whose polygon is nearest the cell's centre (the unit's
                  stated rule), with distances computed here; a tie within 0.5 block passes either way.
  F6 coast        every fringe cell holds coast land (above) that no OTHER grounded table covers: the fringe exists to
                  fill the coast's gap, so a cell that fills none of it (an inland cell, a second ring) is outside the
                  unit's purpose. The 32 is the unit's own coast definition.
  F7 base only    no fringe entry is a heart (no alpha, no minY) and each owner's fringe entries are exactly its base
                  entries (species, level, bucket, weight, position) once per fringe box.
  F8 waters       a fringe cell of a table named for a body of water (lake, waters, river, pond, creek, tarn: the
                  word list of tools/spawn_tiers_audit.py) carries no water-position entry: that lake's fish would be
                  laid on the open-sea coast (section 5, "every lake and coast has its own fish").

NOT COVERED (validity is not runtime behaviour): whether Cobblemon draws these entries in game; whether the inherited
Cobblemon/Cobbleverse pools are suppressed over the fringe (that is tools/suppress_inherited_spawns.py's box set, read
by a separate check in tests/test_coast_fringe_audit.py, not by this audit); a habitat block's true influence shape
(the square bounds any sphere or cube of that radius); lake shores and inland land (not the unit's scope); starter
families (a fringe replicates its owner's table, so a starter appears only at its owner's tier, which F2-F4 bound).

  python tools/coast_fringe_audit.py [--pack DIR] [--out FILE]
Exit 0: every check passes. Exit 1: a failure (listed). Exit 2: no compiled pack.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

PACK = ROOT / "build" / "datapacks" / "cobblers_spawns"
GRID = 32                 # the sub-region grid the fringe is drawn on (data/coast_fringe.json "grid")
COAST_REACH = 32          # the unit's coast: land within 32 of open sea
NEAR = 128                # ENCOUNTER_DESIGN.md section 1
CAPS = {1: 20, 2: 25, 3: 30, 4: 35, 5: 40, 6: 45, 7: 50, 8: 55, 9: 60}   # ENCOUNTER_DESIGN.md section 2
WATER_POS = {"surface", "submerged", "seafloor"}
WATER_WORDS = ("lake", "waters", "river", "pond", "creek", "tarn")
FRINGE_ID = re.compile(r"_c\d{4}_")


def rd(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- terrain measurement (own algorithms)

def open_sea(ground, sea):
    """bool mask: ground < sea, 4-connected to the array's edge. Row runs, union by label propagation."""
    wet = ground < sea
    nz, nx = wet.shape
    pad = np.zeros((nz, nx + 2), dtype=bool)
    pad[:, 1:-1] = wet
    d = np.diff(pad.astype(np.int8), axis=1)
    sz, sx = np.nonzero(d == 1)          # run starts (x)
    ez, ex = np.nonzero(d == -1)         # run ends (exclusive x)
    order_s = np.lexsort((sx, sz))
    order_e = np.lexsort((ex, ez))
    rz, x0, x1 = sz[order_s], sx[order_s], ex[order_e] - 1
    R = len(rz)
    if R == 0:
        return np.zeros_like(wet)
    row_start = np.searchsorted(rz, np.arange(nz + 1))
    ea, eb = [], []
    for z in range(nz - 1):
        a0, a1 = row_start[z], row_start[z + 1]
        b0, b1 = row_start[z + 1], row_start[z + 2]
        if a0 == a1 or b0 == b1:
            continue
        bx0, bx1 = x0[b0:b1], x1[b0:b1]
        lo = np.searchsorted(bx1, x0[a0:a1], side="left")
        hi = np.searchsorted(bx0, x1[a0:a1], side="right")
        cnt = np.maximum(hi - lo, 0)
        if cnt.sum() == 0:
            continue
        ai = np.repeat(np.arange(a0, a1), cnt)
        offs = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        bi = np.repeat(lo, cnt) + offs + b0
        ea.append(ai)
        eb.append(bi)
    lab = np.arange(R)
    if ea:
        a = np.concatenate(ea)
        b = np.concatenate(eb)
        while True:
            m = np.minimum(lab[a], lab[b])
            new = lab.copy()
            np.minimum.at(new, a, m)
            np.minimum.at(new, b, m)
            for _ in range(8):
                new = new[new]
            if np.array_equal(new, lab):
                break
            lab = new
    edge = (rz == 0) | (rz == nz - 1) | (x0 == 0) | (x1 == nx - 1)
    open_lab = np.zeros(R, dtype=bool)
    open_lab[np.unique(lab[edge])] = True
    is_open = open_lab[lab]
    starts = np.zeros(wet.shape, dtype=bool)
    starts[rz, x0] = True
    idx = np.cumsum(starts.ravel(), dtype=np.int32).reshape(wet.shape) - 1
    out = wet & is_open[np.clip(idx, 0, R - 1)]
    return out


def cityblock(src, cap):
    """Exact city-block distance to the nearest True of `src`, saturated at cap + 1 (two-pass, 4-neighbour)."""
    big = cap + 1
    d = np.where(src, 0, big).astype(np.int32)
    for x in range(1, d.shape[1]):
        np.minimum(d[:, x], d[:, x - 1] + 1, out=d[:, x])
    for x in range(d.shape[1] - 2, -1, -1):
        np.minimum(d[:, x], d[:, x + 1] + 1, out=d[:, x])
    for z in range(1, d.shape[0]):
        np.minimum(d[z], d[z - 1] + 1, out=d[z])
    for z in range(d.shape[0] - 2, -1, -1):
        np.minimum(d[z], d[z + 1] + 1, out=d[z])
    return np.minimum(d, big)


def coast_land(ground, sea, reach=COAST_REACH):
    land = ground >= sea
    d = cityblock(open_sea(ground, sea), reach)
    return land & (d >= 1) & (d <= reach)


# ---------------------------------------------------------------- the compiled pack

def read_pack(pack):
    """[{kind, area, id, pokemon, pos, level, bucket, weight, box, alpha, minY}] for every boxed detail."""
    out = []
    for f in sorted(Path(pack).glob("data/*/spawn_pool_world/*/*.json")):
        kind, area = f.parent.name, f.stem
        for s in json.loads(f.read_text(encoding="utf-8")).get("spawns") or []:
            c = s.get("condition") or {}
            if "minX" not in c:
                continue
            lv = str(s.get("level", "0"))
            lo, _, hi = lv.partition("-")
            out.append({"kind": kind, "area": area, "id": s.get("id", ""), "pokemon": s.get("pokemon", ""),
                        "pos": s.get("spawnablePositionType"), "level": (int(lo), int(hi or lo)),
                        "bucket": s.get("bucket"), "weight": s.get("weight"),
                        "box": (int(c["minX"]), int(c["maxX"]), int(c["minZ"]), int(c["maxZ"])),
                        "alpha": "alpha" in s.get("pokemon", ""), "minY": "minY" in c})
    return out


def is_fringe(e):
    return e["kind"] == "subregions" and e["id"].startswith(e["area"] + "_c") and bool(FRINGE_ID.search(e["id"][len(e["area"]):]))


def is_heart(e):
    return e["kind"] == "subregions" and bool(re.match(re.escape(e["area"]) + r"_h\d", e["id"]))


def paint(shape, boxes):
    m = np.zeros(shape, dtype=bool)
    nz, nx = shape
    for x0, x1, z0, z1 in boxes:
        a0, a1, b0, b1 = max(0, x0), min(nx - 1, x1), max(0, z0), min(nz - 1, z1)
        if a1 >= a0 and b1 >= b0:
            m[b0:b1 + 1, a0:a1 + 1] = True
    return m


def coverage(near, entries, free_boxes):
    """{before, after}: coast land under no grounded non-marine box (outside spawn-free zones), and under marine only."""
    shape = near.shape
    free = paint(shape, free_boxes)
    marine = paint(shape, {e["box"] for e in entries if e["kind"] == "marine"})
    out = {"coast_land_columns": int(near.sum())}
    for label, keep in (("before", lambda e: not is_fringe(e)), ("after", lambda e: True)):
        g = paint(shape, {e["box"] for e in entries if e["kind"] != "marine" and e["pos"] == "grounded" and keep(e)})
        gap = near & ~g & ~free
        out[label] = {"no_grounded_table": int((gap & ~marine).sum()), "under_marine_only": int((gap & marine).sum())}
    return out


# ---------------------------------------------------------------- geometry

def overlaps(a, b):
    return not (a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2])


def gap(a, b):
    """Chebyshev gap in blocks between inclusive boxes (0 when they touch or overlap)."""
    dx = max(b[0] - a[1], a[0] - b[1], 0)
    dz = max(b[2] - a[3], a[2] - b[3], 0)
    return max(dx, dz)


def point_in_poly(x, z, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]
        bx, bz = poly[(i + 1) % n]
        if (az > z) != (bz > z) and x < (bx - ax) * (z - az) / (bz - az) + ax:
            inside = not inside
    return inside


def seg_dist(px, pz, poly):
    """Distance from (px, pz) to the polygon's boundary (its closed ring of edges)."""
    a = np.asarray(poly, dtype=float)
    b = a[list(range(1, len(a))) + [0]]
    dx, dz = b[:, 0] - a[:, 0], b[:, 1] - a[:, 1]
    den = dx * dx + dz * dz
    t = np.where(den == 0, 0.0, ((px - a[:, 0]) * dx + (pz - a[:, 1]) * dz) / np.where(den == 0, 1.0, den))
    t = np.clip(t, 0.0, 1.0)
    return float(np.sqrt((px - a[:, 0] - t * dx) ** 2 + (pz - a[:, 1] - t * dz) ** 2).min())


def box_meets_polys(box, polys, step=4):
    """True if any sampled point of the box (every `step` blocks, edges included) lies in a polygon, or a polygon
    vertex lies in the box."""
    x0, x1, z0, z1 = box
    for poly in polys:
        if any(x0 <= p[0] <= x1 and z0 <= p[1] <= z1 for p in poly):
            return True
        for x in list(range(x0, x1 + 1, step)) + [x1]:
            for z in list(range(z0, z1 + 1, step)) + [z1]:
                if point_in_poly(x + 0.5, z + 0.5, poly):
                    return True
    return False


def cells_of(box, grid=GRID):
    x0, x1, z0, z1 = box
    return {(gx, gz) for gx in range(x0 // grid, x1 // grid + 1) for gz in range(z0 // grid, z1 // grid + 1)}


def water_named(area):
    toks = set(area.split("_"))
    return any(w in toks or (w + "s") in toks for w in WATER_WORDS)


# ---------------------------------------------------------------- the checks

def audit(entries, *, routes, towns, design, regions, free_zones, habitat_blocks, rift_polys, near=None,
          other_cover=None, grid=GRID):
    """(failures: [str], info: dict). `near` is the coast-land mask (F6); `other_cover` the non-fringe grounded mask."""
    fails, info = [], {}
    fr = [e for e in entries if is_fringe(e)]
    others = [e for e in entries if not is_fringe(e)]
    # per owner: its cells, the levels and positions there
    cells = {}
    for e in fr:
        for c in cells_of(e["box"], grid):
            k = cells.setdefault(c, {"owner": e["area"], "hi": 0, "water": False, "owners": set()})
            k["owners"].add(e["area"])
            k["hi"] = max(k["hi"], e["level"][1])
            k["water"] = k["water"] or e["pos"] in WATER_POS
    info["fringe_entries"] = len(fr)
    info["fringe_cells"] = len(cells)
    info["fringe_owners"] = len({e["area"] for e in fr})
    for c, k in cells.items():
        if len(k["owners"]) > 1:
            fails.append("F7 cell %s carries the fringe of %s" % (c, sorted(k["owners"])))
    fboxes = sorted({(e["area"], e["box"]) for e in fr})

    # F1 exclusions
    vr = [(b["min_x"], b["max_x"], b["min_z"], b["max_z"]) for r in routes if r["id"] == "victory_road"
          for b in r["spawn_scope"]["boxes"]]
    other_boxes = {(e["kind"], e["area"], e["box"]) for e in others if e["kind"] in ("subregions", "waterways", "marine")}
    hab_soft = []
    for area, b in fboxes:
        for zid, z in free_zones:
            if overlaps(b, z):
                fails.append("F1 %s fringe box %s overlaps spawn-free zone %s" % (area, b, zid))
        if any(overlaps(b, v) for v in vr):
            fails.append("F1 %s fringe box %s overlaps Victory Road's corridor" % (area, b))
        if rift_polys and box_meets_polys(b, rift_polys):
            fails.append("F1 %s fringe box %s meets the Rift's extent" % (area, b))
        for kind, oa, ob in other_boxes:
            if overlaps(b, ob):
                fails.append("F1 %s fringe box %s overlaps %s/%s box %s" % (area, b, kind, oa, ob))
        for hb in habitat_blocks:
            p, r = hb["position"], int(hb.get("range_of_influence") or 0)
            hbox = (p["x"] - r, p["x"] + r, p["z"] - r, p["z"] + r)
            if overlaps(b, hbox):
                if hb.get("replace_spawns"):
                    hab_soft.append([area, hb["id"]])
                else:
                    fails.append("F1 %s fringe box %s inside habitat block %s (replace_spawns false)" % (area, b, hb["id"]))
    info["habitat_replace_overlaps"] = hab_soft

    # route boxes with legs, town footprints with legs
    rboxes = [((b["min_x"], b["max_x"], b["min_z"], b["max_z"]), int(r["order"])) for r in routes
              for b in r["spawn_scope"]["boxes"]]
    rb = np.array([b for b, _ in rboxes]) if rboxes else np.zeros((0, 4))
    rleg = np.array([l for _, l in rboxes])
    tboxes = []
    for t in towns:
        if t.get("order") is None or not t.get("footprint"):
            continue
        f = t["footprint"]
        tboxes.append(((f["min_x"], f["max_x"], f["min_z"], f["max_z"]), max(int(t["order"]), 1), t["id"]))
    tables = design["tables"]
    near_path_cells = 0
    worst = {}
    table_below = {}
    leg_flips = {}
    towns_near = {}
    own_boxes = {}
    for e in others:
        if e["kind"] == "subregions" and not is_heart(e):
            own_boxes.setdefault(e["area"], set()).add(e["box"])
    leg_memo = {}

    def owner_leg(area):
        """The leg of the route nearest the owner's OWN (non-fringe) compiled boxes: the leg its table was tiered by."""
        if area not in leg_memo:
            best = None
            for ob in own_boxes.get(area, ()):
                if not len(rb):
                    break
                dx = np.maximum.reduce([rb[:, 0] - ob[1], ob[0] - rb[:, 1], np.zeros(len(rb))])
                dz = np.maximum.reduce([rb[:, 2] - ob[3], ob[2] - rb[:, 3], np.zeros(len(rb))])
                gg = np.maximum(dx, dz)
                i = int(np.argmin(gg))
                if best is None or gg[i] < best[0]:
                    best = (gg[i], int(rleg[i]))
            leg_memo[area] = None if best is None else best[1]
        return leg_memo[area]
    for (gx, gz), k in sorted(cells.items()):
        cb = (gx * grid, gx * grid + grid - 1, gz * grid, gz * grid + grid - 1)
        owner = k["owner"]
        tab = tables.get(owner)
        if tab is None:
            fails.append("F2 %s has a fringe but no data/encounter_design.json table" % owner)
            continue
        tier = int(tab["tier"])
        if len(rb):
            dx = np.maximum.reduce([rb[:, 0] - cb[1], cb[0] - rb[:, 1], np.zeros(len(rb))])
            dz = np.maximum.reduce([rb[:, 2] - cb[3], cb[2] - rb[:, 3], np.zeros(len(rb))])
            g = np.maximum(dx, dz)
            close = g <= NEAR
        else:
            g, close = np.zeros(0), np.zeros(0, dtype=bool)
        if close.any():
            near_path_cells += 1
            leg = int(rleg[close].min())
            if k["hi"] > CAPS[leg]:
                fails.append("F2 %s fringe cell (%d, %d): level %d within %d of a leg-%d route (cap %d); owner tier %d"
                             % (owner, cb[0], cb[2], k["hi"], int(g[close].min()), leg, CAPS[leg], tier))
                worst[owner] = max(worst.get(owner, 0), k["hi"] - CAPS[leg])
            if tab.get("placement") == "off":
                fails.append("F3 %s (off-path table) fringe cell (%d, %d) is %d from a route: its find is beside the path"
                             % (owner, cb[0], cb[2], int(g[close].min())))
        elif len(g):
            leg = int(rleg[int(np.argmin(g))])
            if tier < leg:
                own = owner_leg(owner)
                if own is not None and leg > own:
                    # the cell's nearest route is a later leg than the owner's: by how much nearer is it?
                    at_own = float(g[rleg == own].min()) if (rleg == own).any() else float("inf")
                    r = leg_flips.setdefault(owner, {"cells": 0, "tier": tier, "owner_leg": own, "cell_legs": set(),
                                                     "min_gap_later_leg": 10 ** 9, "max_margin": 0})
                    r["cells"] += 1
                    r["cell_legs"].add(leg)
                    r["min_gap_later_leg"] = min(r["min_gap_later_leg"], int(g.min()))
                    r["max_margin"] = max(r["max_margin"], int(at_own - g.min()))
                else:
                    table_below[owner] = table_below.get(owner, 0) + 1
        for t in towns:
            f = t.get("footprint")
            if f and gap(cb, (f["min_x"], f["max_x"], f["min_z"], f["max_z"])) <= NEAR:
                r = towns_near.setdefault(t["id"], {"cells": 0, "max_level": 0, "owners": set(), "overlap": 0})
                r["cells"] += 1
                r["max_level"] = max(r["max_level"], k["hi"])
                r["owners"].add(owner)
                r["overlap"] += overlaps(cb, (f["min_x"], f["max_x"], f["min_z"], f["max_z"]))
        for tb, tleg, tid in tboxes:
            if gap(cb, tb) <= NEAR and k["hi"] > CAPS[tleg]:
                fails.append("F2 %s fringe cell (%d, %d): level %d within %d of %s (leg %d, cap %d)"
                             % (owner, cb[0], cb[2], k["hi"], gap(cb, tb), tid, tleg, CAPS[tleg]))
        # F5 nearest owner
        cx, cz = gx * grid + grid / 2.0, gz * grid + grid / 2.0
        dists = {}
        for s in regions["subregions"]:
            dists[s["id"]] = min(seg_dist(cx, cz, p) for p in s["polygons"])
        best = min(dists.values())
        if dists.get(owner, float("inf")) > best + 0.5:
            nearest = min(dists, key=dists.get)
            fails.append("F5 fringe cell (%d, %d) is given to %s (%.1f) but %s is nearest (%.1f)"
                         % (cb[0], cb[2], owner, dists[owner], nearest, best))
        # F6 fills a coast gap
        if near is not None:
            sl = (slice(cb[2], cb[3] + 1), slice(cb[0], cb[1] + 1))
            fill = near[sl] if other_cover is None else (near[sl] & ~other_cover[sl])
            if not fill.any():
                fails.append("F6 %s fringe cell (%d, %d) holds no uncovered coast land" % (owner, cb[0], cb[2]))
        # F8
        if k["water"] and water_named(owner):
            fails.append("F8 %s (a body of water) lays water-position entries on the coast at (%d, %d)"
                         % (owner, cb[0], cb[2]))
    info["near_path_cells"] = near_path_cells
    info["over_cap_by_owner"] = worst
    # off-path fringe cells whose owner TABLE is already below its own nearest route's leg (section 1's floor read
    # naively; islands are tiered by the crossing, `tier_why`): the table's tier, not the fringe's doing
    info["towns_within_128"] = {k: dict(v, owners=sorted(v["owners"])) for k, v in sorted(towns_near.items())}
    info["off_path_cells_owner_table_below_nearest_leg"] = table_below
    info["off_path_cells_nearer_a_later_leg_than_owner"] = {k: dict(v, cell_legs=sorted(v["cell_legs"]))
                                                            for k, v in leg_flips.items()}

    # F7 base only
    for e in fr:
        if e["alpha"] or e["minY"]:
            fails.append("F7 fringe entry %s carries heart content" % e["id"])
    base = {}
    for e in others:
        if e["kind"] == "subregions" and not is_heart(e):
            base.setdefault(e["area"], {})
            sig = (e["pokemon"], e["level"], e["bucket"], e["weight"], e["pos"])
            base[e["area"]].setdefault(sig, set()).add(e["box"])
    per_box = {}
    for e in fr:
        per_box.setdefault((e["area"], e["box"]), []).append((e["pokemon"], e["level"], e["bucket"], e["weight"], e["pos"]))
    for (area, b), sigs in sorted(per_box.items()):
        want = sorted(base.get(area, {}))
        if sorted(sigs) != want:
            fails.append("F7 %s fringe box %s: %d entries, base table has %d (or they differ)" % (area, b, len(sigs), len(want)))
    return fails, info


def load_context():
    sup = rd("spawn_suppression.json")
    free_zones = [(z["id"], (z["box"][0], z["box"][2], z["box"][1], z["box"][3])) for z in sup.get("spawn_free_zones") or []]
    lm = rd("landmarks.json")["landmarks"]
    rift = [x for x in lm if x.get("id") == "rift"]
    rift_polys = rift[0]["extent"]["polygons"] if rift else []
    return {"routes": rd("routes.json")["routes"], "towns": rd("towns.json")["towns"], "design": rd("encounter_design.json"),
            "regions": rd("regions.json"), "free_zones": free_zones, "habitat_blocks": rd("habitat_blocks.json")["blocks"],
            "rift_polys": rift_polys}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default=str(PACK))
    p.add_argument("--out", default=None, help="write the full result (failures, info, coverage) as JSON here")
    p.add_argument("--no-terrain", action="store_true", help="skip coverage and F6 (no heightmap read)")
    a = p.parse_args(argv)
    if not any(Path(a.pack).glob("data/*/spawn_pool_world")):
        print("coast_fringe_audit: no compiled pack at %s" % a.pack)
        return 2
    entries = read_pack(a.pack)
    ctx = load_context()
    near = other = None
    cover = None
    if not a.no_terrain:
        import terrain as T
        h, world = T.load(str(ROOT / "data" / "world.json"))
        ground = np.round(h)
        near = coast_land(ground, T.sea_level(world))
        other = paint(near.shape, {e["box"] for e in entries
                                   if e["kind"] != "marine" and e["pos"] == "grounded" and not is_fringe(e)})
        cover = coverage(near, entries, [z for _, z in ctx["free_zones"]])
    fails, info = audit(entries, near=near, other_cover=other, **ctx)
    res = {"failures": fails, "info": info, "coverage": cover}
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
    by = {}
    for f in fails:
        by[f.split()[0]] = by.get(f.split()[0], 0) + 1
    print("coast_fringe_audit: %d fringe entries, %d cells, %d owners; %d failures %s; coverage %s"
          % (info["fringe_entries"], info["fringe_cells"], info["fringe_owners"], len(fails), json.dumps(by),
             json.dumps(cover)))
    for f in fails[:40]:
        print("  " + f)
    if len(fails) > 40:
        print("  ... %d more (--out)" % (len(fails) - 40))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
