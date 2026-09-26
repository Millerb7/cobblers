#!/usr/bin/env python
"""Layout plans for a town: the data a human composes from, not a build.

Reads a settlement's "plan" block from data/placements.json (authored: streets, plaza, anchor lots for the
Center, Mart and gym, piers, entries and exits, paving) and computes:

  profiles   each street's longitudinal ground profile and a graded profile no steeper than its max_grade
             (cut and fill per station)
  lots       candidate house lots along the streets that ask for them: size, setback, gap, facing the street,
             inside the footprint, clear of streets, plaza and anchor lots, and on ground whose relief across the
             lot is at most max_lot_relief (the placer's foundations handle the rest)
  lamps      light positions along streets so no street block is more than 14 Manhattan blocks from a light
             (overworld monsters spawn only at block light 0; a light of 15 reaches 1 at 14 blocks)
  prep       terrain-prep commands at or below ground level only: cut street and plaza volumes down to their
             graded surface, fill below it, lay the paving; flatten the gym lot to its level. Written as a
             vanilla function (fill), plus the equivalent WorldEdit selections, NOT run.
  checks     overlaps, footprint bounds, steepest street grade before and after, cut and fill volumes

  python tools/town_plan.py gym1_town --source-root <root>          # ground from the heightmap, never a world
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

import terrain as T
import function_limits

ROOT = Path(__file__).resolve().parent.parent
LIGHT_REACH = 14


def densify(poly, step=1.0):
    out, cum = [], 0.0
    for (ax, az), (bx, bz) in zip(poly, poly[1:]):
        L = math.hypot(bx - ax, bz - az)
        k = max(1, int(math.ceil(L / step)))
        for i in range(k):
            t = i / k
            out.append((ax + (bx - ax) * t, az + (bz - az) * t, cum + L * t))
        cum += L
    out.append((poly[-1][0], poly[-1][1], cum))
    return out


def graded_profile(ground, max_grade):
    """Smallest total cut and fill profile within max_grade: clamp a smoothed ground line to the grade limit."""
    g = np.asarray(ground, float)
    k = 9
    sm = np.convolve(np.pad(g, k, mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]
    y = sm.copy()
    for _ in range(3):                                   # forward and backward passes enforce the slope limit
        for i in range(1, len(y)):
            y[i] = min(max(y[i], y[i - 1] - max_grade), y[i - 1] + max_grade)
        for i in range(len(y) - 2, -1, -1):
            y[i] = min(max(y[i], y[i + 1] - max_grade), y[i + 1] + max_grade)
    return np.rint(y).astype(int)


HEADROOM = 3            # blocks of air kept over every street and plaza cell, whatever the export put there
CANOPY = 24             # how high a tree standing on a street or square is cleared


def clear_above(x0, z0, x1, z1, y):
    """Commands that leave a paved box walkable: air for HEADROOM blocks over it, and any tree over it gone.

    A fresh export carries its natural foliage, and nothing cleared it from a street: the prep cut the ground down
    to grade and paved it, and a tree or a flower standing on the old ground stayed standing on the new road. The
    disposable world never showed it, because the ground restore there had already cleared everything. The staging
    run of 2026-09-21 found trunks on three towns' streets and flowers on the Rift rim trail."""
    out = ["fill %d %d %d %d %d %d minecraft:air" % (x0, y + 1, z0, x1, y + HEADROOM, z1)]
    for tag in ("#minecraft:logs", "#minecraft:leaves"):
        out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y + 1, z0, x1, y + CANOPY, z1, tag))
    return out


def rect_overlap(a, b, pad=0):
    return not (a[2] + pad < b[0] or b[2] + pad < a[0] or a[3] + pad < b[1] or b[3] + pad < a[1])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("settlement")
    p.add_argument("--placements", default=str(ROOT / "data" / "placements.json"))
    p.add_argument("--surface-world", default=None, help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    doc = json.loads(Path(a.placements).read_text(encoding="utf-8"))
    s = doc["settlements"][a.settlement]
    plan = s["plan"]
    towns = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}
    # a place with no town record (the Route 1 mansion) must name its own footprint in its plan
    fp = (towns.get(a.settlement) or {}).get("footprint") or {"min_x": 0, "min_z": 0, "max_x": 0, "max_z": 0}
    fbox = (fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"])
    if a.settlement not in towns and not plan.get("footprint"):
        raise SystemExit("%s has no data/towns.json record, so its plan must name its footprint" % a.settlement)
    if plan.get("footprint"):
        # a town that is not on its recorded site's ground: the Displaced City's record is the surface entrance, and
        # the town is on the cavern floor 350 blocks east, so its plan names the box it is built in
        fbox = tuple(plan["footprint"]["rect"])

    if a.surface_world:
        raise SystemExit("--surface-world is gone: a plan's ground comes from the heightmap (tools/ground.py), "
                         "never from a world, which holds the last build")
    # Rounded, not floored. floor(h) was a block low across 48% of the map (measured against a fresh
    # export, see tools/ground.py), which put every lot's measured ground range one block under the
    # ground WorldPainter actually writes.
    import ground as G
    _g = G.for_settlement(a.settlement, getattr(a, "source_root", None), doc)

    def ground(x, z):
        return _g(int(round(x)), int(round(z)))
    ground_basis = "heightmap %s, rounded (tools/ground.py)" % world["heightmap"]["sha256"][:12]

    report = {"settlement": a.settlement, "footprint": fbox, "ground_basis": ground_basis, "streets": {}, "lots": [],
              "anchors": [], "lamps": [], "checks": {}}
    occupied = []                                        # (id, box) of streets, plaza, anchors
    cmds = ["# Terrain prep for %s, generated by tools/town_plan.py from data/placements.json. Nothing above ground level." % a.settlement]
    we = []
    cut_total = fill_total = 0

    # streets
    street_cells = {}
    for r in plan["streets"]:
        pts = densify(r["polyline"])
        gr = [ground(x, z) for x, z, _ in pts]
        target = graded_profile(gr, r.get("max_grade", 0.1))
        half = r["width"] // 2
        steep_before = max((abs(gr[i + 8] - gr[i]) / 8 for i in range(0, len(gr) - 8)), default=0)
        steep_after = max((abs(int(target[i + 8]) - int(target[i])) / 8 for i in range(0, len(target) - 8)), default=0)
        cells = {}
        for (x, z, _), y in zip(pts, target):
            for dx in range(-half, half + 1):
                for dz in range(-half, half + 1):
                    c = (int(round(x)) + dx, int(round(z)) + dz)
                    cells[c] = min(cells.get(c, 10 ** 6), int(y))
        cut = sum(max(0, ground(cx, cz) - y) for (cx, cz), y in cells.items())
        fill = sum(max(0, y - ground(cx, cz)) for (cx, cz), y in cells.items())
        cut_total += cut
        fill_total += fill
        street_cells[r["id"]] = cells
        xs = [c[0] for c in cells]; zs = [c[1] for c in cells]
        occupied.append((r["id"], (min(xs), min(zs), max(xs), max(zs)), "street"))
        report["streets"][r["id"]] = {"width": r["width"], "surface": r["surface"], "length_blocks": round(pts[-1][2]),
                                      "ground_range": [min(gr), max(gr)], "graded_range": [int(target.min()), int(target.max())],
                                      "steepest_grade_before_per_8": round(steep_before, 3), "steepest_grade_after_per_8": round(steep_after, 3),
                                      "cut_blocks": cut, "fill_blocks": fill,
                                      "profile_every_16": [[round(x), round(z), int(y)] for (x, z, _), y in list(zip(pts, target))[::16]]}
        # prep: per column, air from the graded surface + 1 up to the ground (cut), dirt below the surface (fill), paving on top
        by_row = {}
        for (cx, cz), y in cells.items():
            by_row.setdefault((cz, y), []).append(cx)
        # every paved run, [z, y, x0, x1], so tools/town_audit.py can check the world against the plan cell by cell
        report["streets"][r["id"]]["cells"] = runs = []
        for (cz, y), xs_ in sorted(by_row.items()):
            xs_.sort()
            run = [xs_[0]]
            for xx in xs_[1:] + [None]:
                if xx is not None and xx == run[-1] + 1:
                    run.append(xx)
                    continue
                top = max(ground(q, cz) for q in run)
                low = min(ground(q, cz) for q in run)
                if top > y:
                    cmds.append("fill %d %d %d %d %d %d minecraft:air" % (run[0], y + 1, cz, run[-1], top, cz))
                if low < y - 1:
                    cmds.append("fill %d %d %d %d %d %d minecraft:dirt replace #minecraft:replaceable" % (run[0], low + 1, cz, run[-1], y - 1, cz))
                cmds.append("fill %d %d %d %d %d %d %s" % (run[0], y, cz, run[-1], y, cz, r["surface"]))
                cmds += clear_above(run[0], cz, run[-1], cz, y)
                runs.append([cz, int(y), run[0], run[-1]])
                if xx is not None:
                    run = [xx]
        # lamps: every 2 * LIGHT_REACH - width blocks along the centreline
        spacing = 2 * LIGHT_REACH - r["width"] - 1
        for (x, z, c), y in zip(pts, target):
            if int(c) % spacing == 0:
                c = (int(round(x)), int(round(z)))
                # the cell's own paving level, which can sit a block under this point's profile
                report["lamps"].append({"street": r["id"], "at": [c[0], cells.get(c, int(y)) + 1, c[1]]})

    # plaza
    pz = plan.get("plaza")
    if pz:
        x0, z0, x1, z1 = pz["rect"]
        y = pz["y"]
        occupied.append(("plaza", (x0, z0, x1, z1), "plaza"))
        cut = sum(max(0, ground(x, z) - y) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
        fill = sum(max(0, y - ground(x, z)) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
        cut_total += cut
        fill_total += fill
        top = max(ground(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
        low = min(ground(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
        if top > y:
            cmds.append("fill %d %d %d %d %d %d minecraft:air" % (x0, y + 1, z0, x1, top, z1))
        if low < y - 1:
            cmds.append("fill %d %d %d %d %d %d minecraft:dirt replace #minecraft:replaceable" % (x0, low + 1, z0, x1, y - 1, z1))
        cmds.append("fill %d %d %d %d %d %d %s" % (x0, y, z0, x1, y, z1, pz["surface"]))
        cmds += clear_above(x0, z0, x1, z1, y)
        we.append("plaza: //pos1 %d,%d,%d  //pos2 %d,%d,%d  //set air ; //pos1 %d,%d,%d //pos2 %d,%d,%d //set %s"
                  % (x0, y + 1, z0, x1, max(top, y + 1), z1, x0, y, z0, x1, y, z1, pz["surface"]))
        report["plaza"] = {"rect": pz["rect"], "y": y, "ground_range": [low, top], "cut_blocks": cut, "fill_blocks": fill,
                           "surface": pz["surface"]}
        for cx in range(x0, x1 + 1, 2 * LIGHT_REACH - 1):
            for cz in range(z0, z1 + 1, 2 * LIGHT_REACH - 1):
                report["lamps"].append({"street": "plaza", "at": [cx, y + 1, cz]})

    # lamps: a light set flush into the paving at each spot, after all the paving so no later street
    # overwrites one. Flush, because the spots are on the centreline and a post there blocks the road.
    # Until 2026-09-21 the spots were computed and nothing lit them: Brock's 23 were all dark.
    lamp = (plan.get("paving") or {}).get("lamp", "minecraft:sea_lantern")
    if lamp == "none":
        # a place meant to be dark: the Scar's ruins are lit by nothing
        report["lamps"] = []
    report["lamp_block"] = lamp
    for L in report["lamps"]:
        lx, ly, lz = L["at"]
        cmds.append("setblock %d %d %d %s" % (lx, ly - 1, lz, lamp))

    # anchor lots: services, gym, piers (authored positions)
    for lot in plan["anchors"]:
        x0, z0, x1, z1 = lot["rect"]
        box = (x0, z0, x1, z1)
        gr = [ground(x, z) for x in range(x0, x1 + 1, 2) for z in range(z0, z1 + 1, 2)]
        row = {"id": lot["id"], "role": lot["role"], "rect": lot["rect"], "facing": lot["facing"], "why": lot.get("why"),
               "ground_range": [min(gr), max(gr)], "template": lot.get("template")}
        clash = [o[0] for o in occupied if rect_overlap(box, o[1]) and o[2] != "street"]
        street_hits = sum(1 for cells in street_cells.values() for (cx, cz) in cells if x0 <= cx <= x1 and z0 <= cz <= z1)
        row["overlaps"] = clash
        row["street_blocks_inside"] = street_hits
        row["inside_footprint"] = fbox[0] <= x0 and fbox[1] <= z0 and x1 <= fbox[2] and z1 <= fbox[3]
        if lot.get("level") is not None:
            yl = lot["level"]
            cut = sum(max(0, ground(x, z) - yl) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
            fill = sum(max(0, yl - ground(x, z)) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
            cut_total += cut
            fill_total += fill
            top = max(ground(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
            low = min(ground(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
            if top > yl:
                cmds.append("fill %d %d %d %d %d %d minecraft:air" % (x0, yl + 1, z0, x1, top, z1))
            if low < yl:
                cmds.append("fill %d %d %d %d %d %d minecraft:dirt replace #minecraft:replaceable" % (x0, low + 1, z0, x1, yl, z1))
                cmds.append("fill %d %d %d %d %d %d minecraft:grass_block replace minecraft:dirt" % (x0, yl, z0, x1, yl, z1))
            if lot.get("surface"):
                # an open lot that is a square, not a building plot: Sabrina's market is paved at its level
                cmds.append("fill %d %d %d %d %d %d %s" % (x0, yl, z0, x1, yl, z1, lot["surface"]))
                # and walkable, as a street or the plaza is: headroom, and any tree over it gone. Without it an
                # export-painted cherry at the Rift rim post stood its trunk and leaves on the overlook's planks
                # (EXP-026 run 4: 4 cells). From the plan's rect and level, never from a world
                cmds += clear_above(x0, z0, x1, z1, yl)
                row["surface"] = lot["surface"]
            row.update({"level": yl, "cut_blocks": cut, "fill_blocks": fill})
        occupied.append((lot["id"], box, "anchor"))
        report["anchors"].append(row)

    # candidate house lots along streets
    lp = plan.get("house_lots") or {}
    lw, ld = lp.get("size", [12, 14])
    wet = None
    if lp.get("avoid_water") is not None:
        # tools/place_town.py clears every fluid within two blocks of a house's footprint, so a lot at a river's edge
        # would drain the river: a plan that asks refuses any lot with painted water within this many blocks
        from elder_trees import painted_water
        wet = painted_water(_g.heights, _g.world)
        wm = int(lp["avoid_water"])
    setback, gap, max_relief = lp.get("setback", 3), lp.get("gap", 4), lp.get("max_lot_relief", 4)
    n = 0
    refused = {}                                         # why candidate lots were refused, so a thin plan can be read
    for sid in lp.get("along", []):
        r = next(q for q in plan["streets"] if q["id"] == sid)
        half = r["width"] // 2
        pts = densify(r["polyline"], 1.0)
        c = 0.0
        while c < pts[-1][2]:
            i = min(range(len(pts)), key=lambda k: abs(pts[k][2] - c))
            j = min(len(pts) - 1, i + 2)
            dx, dz = pts[j][0] - pts[max(0, i - 2)][0], pts[j][1] - pts[max(0, i - 2)][1]
            L = math.hypot(dx, dz) or 1.0
            ux, uz = dx / L, dz / L
            for side in (-1, 1):
                nx, nz = -uz * side, ux * side
                off = half + setback + ld / 2
                cx, cz = pts[i][0] + nx * off, pts[i][1] + nz * off
                along_x = abs(ux) >= abs(uz)
                w, d = (lw, ld) if along_x else (ld, lw)
                box = (int(round(cx - w / 2)), int(round(cz - d / 2)), int(round(cx + w / 2)) - 1, int(round(cz + d / 2)) - 1)
                if not (fbox[0] <= box[0] and fbox[1] <= box[1] and box[2] <= fbox[2] and box[3] <= fbox[3]):
                    refused["outside the footprint"] = refused.get("outside the footprint", 0) + 1
                    continue
                if any(rect_overlap(box, o[1], gap) for o in occupied if o[2] != "street"):
                    refused["too close to another lot or anchor"] = refused.get("too close to another lot or anchor", 0) + 1
                    continue
                if any(box[0] <= sx <= box[2] and box[1] <= sz <= box[3] for cells in street_cells.values() for (sx, sz) in cells):
                    refused["on a street"] = refused.get("on a street", 0) + 1
                    continue
                if wet is not None and wet[box[1] - wm - _g.oz:box[3] + wm + 1 - _g.oz, box[0] - wm - _g.ox:box[2] + wm + 1 - _g.ox].any():
                    refused["water within avoid_water"] = refused.get("water within avoid_water", 0) + 1
                    continue
                gr = [ground(x, z) for x in range(box[0], box[2] + 1, 2) for z in range(box[1], box[3] + 1, 2)]
                if max(gr) - min(gr) > max_relief:
                    refused["relief over max_lot_relief"] = refused.get("relief over max_lot_relief", 0) + 1
                    continue
                facing = ("north" if nz > 0 else "south") if along_x else ("west" if nx > 0 else "east")
                row = {"along": sid, "rect": list(box), "facing": facing, "ground_range": [min(gr), max(gr)]}
                if lp.get("level_lots"):
                    # A terrace: the lot cut and filled level at its own median, held within a step of the street in
                    # front of it so the door is reachable, and refused if that needs more than max_cut_fill blocks
                    # of either anywhere. This is the Displaced City's summit terracing on a floor with +-3 of noise.
                    full = [ground(x, z) for x in range(box[0], box[2] + 1) for z in range(box[1], box[3] + 1)]
                    sy = street_cells[sid].get(min(street_cells[sid], key=lambda q: (q[0] - pts[i][0]) ** 2 + (q[1] - pts[i][1]) ** 2))
                    yl = int(min(max(int(np.median(full)), sy - 1), sy + 2))
                    worst_cut, worst_fill = max(full) - yl, yl - min(full)
                    if max(worst_cut, worst_fill) > lp.get("max_cut_fill", 4):
                        refused["cut or fill over max_cut_fill"] = refused.get("cut or fill over max_cut_fill", 0) + 1
                        continue
                    x0_, z0_, x1_, z1_ = box
                    if worst_cut > 0:
                        cmds.append("fill %d %d %d %d %d %d minecraft:air" % (x0_, yl + 1, z0_, x1_, max(full), z1_))
                    if worst_fill > 0:
                        cmds.append("fill %d %d %d %d %d %d minecraft:dirt replace #minecraft:replaceable" % (x0_, min(full) + 1, z0_, x1_, yl, z1_))
                        cmds.append("fill %d %d %d %d %d %d minecraft:grass_block replace minecraft:dirt" % (x0_, yl, z0_, x1_, yl, z1_))
                    cut_total += sum(max(0, q - yl) for q in full)
                    fill_total += sum(max(0, yl - q) for q in full)
                    row.update({"level": yl, "cut_max": worst_cut, "fill_max": worst_fill})
                n += 1
                lid = "%s_lot_%02d" % (sid, n)
                report["lots"].append(dict(row, id=lid))
                occupied.append((lid, box, "lot"))
            c += (lw if abs(ux) >= abs(uz) else lw) + gap

    report["checks"] = {"anchor_overlaps": {r["id"]: r["overlaps"] for r in report["anchors"] if r["overlaps"]},
                        "anchors_outside_footprint": [r["id"] for r in report["anchors"] if not r["inside_footprint"] and r["role"] not in ("pier", "waterfront_gym")],
                        "anchors_on_street_blocks": {r["id"]: r["street_blocks_inside"] for r in report["anchors"] if r["street_blocks_inside"]},
                        "cut_blocks_total": cut_total, "fill_blocks_total": fill_total, "house_lots": len(report["lots"]),
                        "lamps": len(report["lamps"]), "prep_commands": len(cmds), "lots_refused": refused}
    for r in plan["streets"]:
        pts = r["polyline"]
        we.append("%s: WorldEdit has no graded-line brush; select each %d-block run from the prep function's fill boxes, "
                  "//set air above the graded surface, //replace air dirt below it, //set %s on it" % (r["id"], r["width"], r["surface"]))
    report["worldedit_equivalent"] = we
    out = ROOT / "derived" / "towns" / ("%s_plan.json" % a.settlement)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    fn = ROOT / "build" / "town_prep" / ("prep_%s.mcfunction" % a.settlement)
    fn.parent.mkdir(parents=True, exist_ok=True)
    fn.write_text("\n".join(function_limits.ensure_loaded(cmds)) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("lots", "lamps")}, indent=1))
    print("house lots:", len(report["lots"]), "lamps:", len(report["lamps"]), "->", out, fn)


if __name__ == "__main__":
    main()
