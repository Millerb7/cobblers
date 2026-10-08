#!/usr/bin/env python
"""The refillable mining caves (docs/mechanics/ECONOMY_OVERHAUL.md section 3, BUILD LIST U3), from data/mining_caves.json.

Two shared caves of vanilla ore that grow back: an early chamber of 3 galleries by the Route 1 old mine, and a deep cave
of 8 galleries at Fossick (the Craters' mining town). Each cave is a mouth with a timber frame, an incline of stairs down
`drop` blocks and a straight hall; each gallery is a body of host rock with that variant's ore in it, set into the hall's
wall behind a one-block shell of a contrasting rock. Netherite gets no refill (section 3.4).

The restore is tools/mines.py's, reused rather than invented (ECONOMY_OVERHAUL.md 3.1):

  frame         mines.frame (tools/mines.py:104): the cave's (u, d) frame from its mouth and the side a player comes from
  the mix       mines.h32 / mines.sid (tools/mines.py:86, :97): every choice is a hash of the seed, an id and a position
  the writes    mines.column_runs (tools/mines.py:603): vertical runs per column; with a tag, filtered fills even for one
                cell, so a player's chest left in a gallery survives
  the guard     the check function of mines.driver_files (tools/mines.py:719-731), line for line: the period has passed,
                the guard box's four corners are loaded (`execute unless loaded ... run return 0`), and no player and no
                cobblemon:pokemon stands inside the body and shell grown by one (`execute if entity ... run return 0`).
                The occupancy guard is mandatory: a gallery is never restored on top of anyone
  the restore   mines.py:732-753: the formation back over the resettable tag first, then a variant other than the last
                (`random value 0..7`, moved on by one if it repeats), the last restore's game time, and the sibling rule
                that keeps a cave's galleries staggered after an idle spell brought them due together
  the variants  mines.py:759: each ore by `execute if block <host> run setblock`, so an ore goes only into rock the fill
                put back, never over a player's block
  the driver    mines.py:699-708: one counter a tick; every `every_ticks` the work, and only for a cave a player is near

What differs from a stone face: a gallery holds several ores per variant (data/mining_caves.json `yields`, whose
per_variant counts are placed exactly), its scores and functions are its own (cobblers:mining_caves, objectives mcv.*)
so nothing collides with cobblers_mines, and its tag is #cobblers:cave_resettable: data/mines.json's resettable list read
as it stands plus the fourteen vanilla ores (the stone faces' tag and audit are left untouched).

Where a cave may stand (checked by `report` and `build`; searched by `site` and `author`): the ground is the canonical
heightmap, rounded (tools/ground.py), never a world. Every written column keeps data/mining_caves.json `keep_clear`'s
distances from the town footprints, the routed legs and route paths, the routes' spawn-corridor boxes, every x/z another
data file authors (tools/southern_residents.py authored_points), every earthwork's columns and placed template, every
other built pack's fills, setblocks and templates, painted water and the water export's changed columns; a surface
column also keeps clear of painted trees. The hall and galleries keep `cover_min` of ground over their top; the mouth's
approach is level within `approach_tolerance`.

Spawn conditions: coal, iron, redstone and diamond ore are named by data/spawn_blocks.json (Rolycoly's line and
Torkoal; Aron's line and the Alolan Geodude line; Klink's line; Carbink, Sableye and Glimmet). The owner allowed
spawn-condition blocks on 2026-10-05; data/spawn_block_policy.json carries an entry scoped to mining_caves, and `build`
refuses any spawn condition it places that no entry scoped to mining_caves allows.

  python tools/mining_caves.py site <cave id> [--top N]    candidate mouths for a cave, best first; nothing written
  python tools/mining_caves.py author [<cave id>] [--resite]  site every cave with no entry yet into data/mining_caves.json
  python tools/mining_caves.py report                      every cave's checks and counts; nothing written
  python tools/mining_caves.py build                       -> build/datapacks/cobblers_mining_caves, derived/mining_caves/plan.json

  --inputs-root <full checkout>  where build/datapacks, build/paint, derived/routes and derived/water_shape are read
                                 (default: this checkout). Run once per export by tools/reapply.py step R9OC.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402
import mines as M              # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "mining_caves.json"
PACK = "cobblers_mining_caves"
OUT = ROOT / "build" / "datapacks" / PACK
PLAN = ROOT / "derived" / "mining_caves" / "plan.json"
NS = "cobblers"
FOLDER = "mining_caves"
F = "%s:%s" % (NS, FOLDER)
T_, LAST, VAR = "mcv.t", "mcv.last", "mcv.var"
AIR = "minecraft:air"
LANTERN = "minecraft:lantern[hanging=true,waterlogged=false]"
SIDES = {"left": -1, "right": 1}
FRONTS = M.FRONTS
CONTAINERS = ("chest", "barrel", "shulker", "hopper", "furnace", "dispenser", "dropper", "smoker", "crafter")
SOLID_ROLES = ("floor", "stair", "fill", "skin", "shell", "body", "post", "beam")
TEMPLATE_REACH = 24
POLICY_SCOPE = "mining_caves"


class CaveError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def base(block):
    return block.split("[")[0].split("{")[0]


# ------------------------------------------------------------------ the shape

def slots(cave):
    return max(g["slot"] for g in cave["galleries"]) + 1


def extent(spec, cave):
    """(u reach, d reach): how far any write of the cave stands from its mouth, across and along."""
    geo = spec["geometry"]
    hw = geo["passage_half_width"]
    return hw + 2 + geo["gallery_depth"], cave["drop"] + 2 + slots(cave) * (geo["gallery_width"] + 2)


def mouth_floor(spec, cave, ground, anchor=None, front=None):
    """y0: the lower median of the ground over row d = -1, u = -(hw+1) .. hw+1 (mines.floor_y's rule)."""
    hw = spec["geometry"]["passage_half_width"]
    e = cave.get("entry") or {}
    xz = M.frame(tuple(anchor or e["anchor"]), front or e["front"])
    gs = sorted(ground(*xz(u, -1)) for u in range(-hw - 1, hw + 2))
    return gs[(len(gs) - 1) // 2]


def geometry(spec, cave, ground, anchor=None, front=None):
    """Everything a cave writes, from its mouth and the ground: {"cells": {(x, y, z): role}, "galleries": [...], ...}.

    Roles: air, floor, stair, fill, skin, shell, body, post, beam, lantern. Every broken rule is a problem."""
    geo = spec["geometry"]
    e = cave.get("entry") or {}
    anchor = tuple(anchor or e["anchor"])
    front = front or e["front"]
    xz = M.frame(anchor, front)
    hw, PH = geo["passage_half_width"], geo["passage_height"]
    W, D, H = geo["gallery_width"], geo["gallery_depth"], geo["gallery_height"]
    cover = geo["cover_min"]
    drop = cave["drop"]
    y0 = mouth_floor(spec, cave, ground, anchor, front)
    yh = y0 - drop
    cells, probs = {}, []
    rows = {}                                   # d -> (floor top, air top, tunnel?)
    # the mouth (d = 0) and the incline (d = 1 .. drop)
    for d in range(0, drop + 1):
        ft = y0 if d == 0 else y0 - d + 1
        at = ft + PH
        gmin = min(ground(*xz(u, d)) for u in range(-hw - 1, hw + 2))
        tunnel = gmin >= at + 1 + cover
        rows[d] = (ft, at, tunnel)
        for u in range(-hw, hw + 1):
            x, z = xz(u, d)
            g = ground(x, z)
            if ft - 1 - g > geo["max_fill"]:
                probs.append("incline column (%d, %d): built up %d under its floor, over %d" % (x, z, ft - 1 - g, geo["max_fill"]))
            for y in range(g + 1, ft):
                cells[(x, y, z)] = "fill"
            cells[(x, ft, z)] = "floor" if d == 0 else "stair"
            top = at if tunnel else max(g, at) + geo["clear_above"]
            for y in range(ft + 1, top + 1):
                cells[(x, y, z)] = "air"
    # the hall
    slot_len = W + 2
    hall0 = drop + 1
    hall1 = hall0 + slots(cave) * slot_len - 1
    for d in range(hall0, hall1 + 1):
        rows[d] = (yh, yh + PH, True)
        for u in range(-hw, hw + 1):
            x, z = xz(u, d)
            cells[(x, yh, z)] = "floor"
            for y in range(yh + 1, yh + PH + 1):
                cells[(x, y, z)] = "air"
    # the galleries: body and shell, each its own slot of W + 2 rows on its side
    gals = []
    for gal in cave["galleries"]:
        s = SIDES[gal["side"]]
        d0 = hall0 + gal["slot"] * slot_len + 1
        body, shell = [], []
        for dd in range(d0 - 1, d0 + W + 1):
            for k in range(0, D + 1):
                u = s * (hw + 1 + k)
                x, z = xz(u, dd)
                for y in range(yh, yh + H + 2):
                    inside = d0 <= dd < d0 + W and k < D and yh < y <= yh + H
                    c = (x, y, z)
                    if c in cells:
                        probs.append("%s: cell %s already written as %s" % (gal["id"], c, cells[c]))
                    if inside:
                        cells[c] = "body"
                        body.append((x, y, z, k, dd - d0))
                    else:
                        cells[c] = "shell"
                        shell.append(c)
        xs, ys, zs = zip(*([b[:3] for b in body] + shell))
        bounds = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]
        gals.append({"gallery": gal, "body": sorted(body), "shell": sorted(shell), "bounds": bounds,
                     "guard": [bounds[0] - 1, bounds[1] - 1, bounds[2] - 1, bounds[3] + 1, bounds[4] + 1, bounds[5] + 1]})
    # the timber frame at the mouth: posts at |u| = hw + 1, a beam over the opening
    timber = cave["timber"]
    axis = "x" if front in ("north", "south") else "z"
    for u in (-hw - 1, hw + 1):
        x, z = xz(u, 0)
        g = ground(x, z)
        for y in range(g + 1, y0 + 1):
            cells[(x, y, z)] = "fill"
        for y in range(y0 + 1, y0 + PH + 1):
            cells[(x, y, z)] = "post"
    for u in range(-hw - 1, hw + 2):
        x, z = xz(u, 0)
        cells[(x, y0 + PH + 1, z)] = "beam"
    # the skin: every natural cell next to the air, at or under its column's ground (mines.geometry's rule)
    skin = {}
    for (x, y, z), role in cells.items():
        if role != "air":
            continue
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0), (0, 1, 0)):
            c = (x + dx, y + dy, z + dz)
            if c not in cells and c not in skin and c[1] <= ground(c[0], c[2]):
                skin[c] = "skin"
    cells.update(skin)
    # lanterns: down the middle every lantern_every rows, hanging from a ceiling that holds them
    every = geo["lantern_every"]
    for d in sorted(rows):
        if d % every != every // 2:
            continue
        _ft, at, _tunnel = rows[d]
        x, z = xz(0, d)
        above = cells.get((x, at + 1, z))
        if cells.get((x, at, z)) == "air" and above in SOLID_ROLES:
            cells[(x, at, z)] = "lantern"
    # the rules on the ground
    for u in range(-hw - 1, hw + 2):
        for d in range(-geo["approach_rows"], 0):
            x, z = xz(u, d)
            if abs(ground(x, z) - y0) > geo["approach_tolerance"]:
                probs.append("approach column (%d, %d): ground y%d is more than %d from the mouth floor y%d"
                             % (x, z, ground(x, z), geo["approach_tolerance"], y0))
    tops = {}
    for (x, y, z) in cells:
        tops[(x, z)] = max(tops.get((x, z), -999), y)
    under = set()
    for d in range(hall0, hall1 + 2):
        for u in range(-(hw + 2 + D), hw + 3 + D):
            under.add(xz(u, d))
    # (an incline row is a tunnel only where its own least ground clears its roof by cover_min, decided above; the
    # first tunnel row behind an open cutting carries the cutting's back wall up to the ground, so it is not re-checked)
    for c in sorted(under):
        if c in tops and ground(*c) - tops[c] < cover:
            probs.append("column (%d, %d): %d of ground over its top write y%d, under %d" % (c[0], c[1], ground(*c) - tops[c], tops[c], cover))
    surface = sorted({(x, z) for (x, y, z) in cells if y > ground(x, z) or (y == ground(x, z) and cells[(x, y, z)] == "air")})
    xs, ys, zs = zip(*cells)
    stand = xz(0, -2)
    return {"cells": cells, "galleries": gals, "problems": probs, "y0": y0, "yh": yh, "front": front, "anchor": list(anchor),
            "stand": [stand[0], y0 + 1, stand[1]], "hall_stand": [xz(0, hall0)[0], yh + 1, xz(0, hall0)[1]],
            "bounds": [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)],
            "columns": sorted({(x, z) for x, _y, z in cells}), "surface": surface,
            "dug": sum(1 for (x, y, z), r in cells.items() if r in ("air", "lantern") and y <= ground(x, z))}


# ------------------------------------------------------------------ the ore

def yields(spec, cave):
    return spec["yields"][cave["yield"]]


def ore_cells(spec, cave, g, k, gm):
    """[((x, y, z), ore)] of variant k in one gallery. Cells ordered by h32(seed, gallery, k, x, y, z) (mines.ore_cells'
    order); a `hidden_only` ore takes cells at least 2 into the body; the first `visible_min` of the others take cells on
    the face (depth 0) at eye height (yh+2, yh+3), away from the ends; the rest take the next free cell."""
    yl = yields(spec, cave)
    gid = g["gallery"]["id"]
    fid = M.sid(gid)
    seed = spec["seed"]
    yh, W = gm["yh"], spec["geometry"]["gallery_width"]
    order = sorted(g["body"], key=lambda c: (M.h32(seed, fid, k, c[0], c[1], c[2]), c))
    hidden_only = list(yl.get("hidden_only") or [])
    seq = [o for o in yl["ores"] if o in hidden_only] + [o for o in yl["ores"] if o not in hidden_only]
    used, out = set(), []
    left = yl.get("visible_min", 0)
    for ore in seq:
        n = yl["ores"][ore]["per_variant"][k]
        for _ in range(n):
            pick = None
            if ore in hidden_only:
                pick = next((c for c in order if c[:3] not in used and c[3] >= 2), None)
            elif left > 0:
                pick = next((c for c in order if c[:3] not in used and c[3] == 0 and c[1] in (yh + 2, yh + 3)
                             and 0 < c[4] < W - 1), None)
                if pick is not None:
                    left -= 1
            if pick is None and ore not in hidden_only:
                pick = next((c for c in order if c[:3] not in used), None)
            if pick is None:
                raise CaveError("%s variant %d: no cell left for %s" % (gid, k, ore))
            used.add(pick[:3])
            out.append((pick[:3], ore))
    return out


def yield_problems(spec):
    out = []
    nv = spec["restore"]["variants"]
    for name, yl in spec["yields"].items():
        for ore, y in yl["ores"].items():
            pv = y["per_variant"]
            if len(pv) != nv:
                out.append("yields %s %s: %d per_variant counts, not %d" % (name, ore, len(pv), nv))
            elif abs(sum(pv) - y["mean"] * nv) > 1e-9:
                out.append("yields %s %s: per_variant sums to %d, not %s x %d (the design's mean)" % (name, ore, sum(pv), y["mean"], nv))
            if any(v < 0 for v in pv):
                out.append("yields %s %s: a negative count" % (name, ore))
        for o in yl.get("hidden_only") or []:
            if o not in yl["ores"]:
                out.append("yields %s: hidden_only %s is not one of its ores" % (name, o))
    return out


# ------------------------------------------------------------------ where a cave may stand

def resettable(spec):
    out = list(M.load()["restore"]["resettable"])
    for b in spec["restore"]["resettable_add"]:
        if b not in out:
            out.append(b)
    return out


class Clearance:
    """(x, z) -> why a cave may not write there, or None, over one box; built from other systems' data and packs only."""

    def __init__(self, spec, box, g0, inputs_root=None, own_pack=PACK, need_packs=False):
        ir = Path(inputs_root or ROOT)
        kc = spec["keep_clear"]
        self.box = x0, z0, x1, z1 = [int(v) for v in box]
        shape = (z1 - z0 + 1, x1 - x0 + 1)
        self.code = np.zeros(shape, np.int16)
        self.reasons = [None]
        self.notes = []
        self.pack_why = {}

        def mark(mask, why):
            self.reasons.append(why)
            self.code[(self.code == 0) & mask] = len(self.reasons) - 1

        def put_rect(m, xa, za, xb, zb):
            xa, xb = max(xa, x0), min(xb, x1)
            za, zb = max(za, z0), min(zb, z1)
            if xa <= xb and za <= zb:
                m[za - z0:zb - z0 + 1, xa - x0:xb - x0 + 1] = True
            return m

        def rect(xa, za, xb, zb):
            return put_rect(np.zeros(shape, bool), xa, za, xb, zb)

        def grown(mask, n):
            return M._dilate2(mask, n) if n > 0 else mask

        def raster(polys, pad):
            """Polylines rasterised over the box grown by pad, returned as a padded mask."""
            m = np.zeros((shape[0] + 2 * pad, shape[1] + 2 * pad), bool)
            for pts in polys:
                for (ax, az), (bx, bz) in zip(pts, pts[1:] or pts):
                    if max(ax, bx) < x0 - pad or min(ax, bx) > x1 + pad or max(az, bz) < z0 - pad or min(az, bz) > z1 + pad:
                        continue
                    n = int(max(abs(bx - ax), abs(bz - az))) + 1
                    for i in range(n + 1):
                        t = i / max(n, 1)
                        x, z = round(ax + (bx - ax) * t), round(az + (bz - az) * t)
                        if x0 - pad <= x <= x1 + pad and z0 - pad <= z <= z1 + pad:
                            m[z - z0 + pad, x - x0 + pad] = True
            return m

        # towns
        for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]:
            f = t.get("footprint") or {}
            if f.get("min_x") is None:
                continue
            m = kc["town_margin"]
            mark(rect(f["min_x"] - m, f["min_z"] - m, f["max_x"] + m, f["max_z"] + m), "town %s's footprint + %d" % (t["id"], m))
        # routed legs and route paths
        rc = kc["road_clear"]
        legs_p = ir / "derived" / "routes" / "critical_legs.json"
        if not legs_p.is_file():
            raise CaveError("no %s: the routed legs are a keep-clear rule, and a missing file is a failure, not a pass" % legs_p)
        legs = [l.get("polyline") or [] for l in json.loads(legs_p.read_text(encoding="utf-8"))["legs"]]
        paths = list(json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"].values())
        r = raster(legs + paths, rc)
        mark(grown(r, rc)[rc:-rc, rc:-rc], "within %d of a routed leg or a route path" % rc)
        # the routes' spawn-corridor boxes, filled
        cc = kc["corridor_clearance"]
        for rt in json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))["routes"]:
            for b in (rt.get("spawn_scope") or {}).get("boxes") or []:
                mark(rect(b["min_x"] - cc, b["min_z"] - cc, b["max_x"] + cc, b["max_z"] + cc),
                     "within %d of route %s's corridor box %s" % (cc, rt["id"], b.get("id")))
        # painted water (elder_trees.painted_water's reading, tools/elder_trees.py:151, from --inputs-root) and trees
        import terrain as T
        paint = ir / "build" / "paint"
        man_p = paint / "manifest.json"
        if not man_p.is_file():
            raise CaveError("no %s: painted water and trees are keep-clear rules; a missing map is a failure" % man_p)
        from PIL import Image
        man = json.loads(man_p.read_text(encoding="utf-8"))
        n = kc["water_reach"]
        sub = (slice(max(0, z0 - n), z1 + n + 1), slice(max(0, x0 - n), x1 + n + 1))
        wet = np.asarray(g0.heights)[sub] <= T.sea_level(g0.world)
        wox, woz = max(0, x0 - n), max(0, z0 - n)
        for w in man["water"]:
            key = "levels" if "levels" in w else "mask"
            mm = np.asarray(Image.open(paint / w[key])) > 0
            self._stamp(wet, mm, w["x"] - wox, w["z"] - woz)
        wet = grown(wet, n)
        mark(self._crop(wet, wox, woz), "within %d of painted water" % n)
        tr = kc["tree_reach"]
        trees = np.zeros((shape[0] + 2 * tr, shape[1] + 2 * tr), bool)
        for layer in man.get("objects") or []:
            mm = np.asarray(Image.open(paint / layer["map"])) > 0
            self._stamp(trees, mm, -(x0 - tr), -(z0 - tr))
        self.trees = grown(trees, tr)[tr:-tr, tr:-tr] if tr else trees
        # the pending water export's changed columns (mines.py Occupancy's rule)
        wc = ir / "derived" / "water_shape" / "changed.npy"
        if not wc.is_file():
            raise CaveError("no %s: the water export's changed columns are a keep-clear rule, and a missing map is a "
                            "failure, not a pass" % wc)
        n = kc["water_changed_reach"]
        ch = np.load(wc, mmap_mode="r")
        sub = np.array(ch[max(0, z0 - n):z1 + n + 1, max(0, x0 - n):x1 + n + 1])
        mark(self._crop(grown(sub, n), max(0, x0 - n), max(0, z0 - n)), "within %d of a column the water export changes" % n)
        # placements: earthwork commands and placed templates
        import town_dressing as TD
        doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
        eg, pr = kc["earthwork_gap"], kc["placement_reach"]
        for p in doc["placements"]:
            if p.get("commands"):
                cols = TD.command_columns(p["commands"])
                m = np.zeros((shape[0] + 2 * eg, shape[1] + 2 * eg), bool)
                for (x, z) in cols:
                    if x0 - eg <= x <= x1 + eg and z0 - eg <= z <= z1 + eg:
                        m[z - z0 + eg, x - x0 + eg] = True
                if m.any():
                    m = grown(m, eg)[eg:m.shape[0] - eg, eg:m.shape[1] - eg]
                    mark(m, "within %d of earthwork %s" % (eg, p["id"]))
            pos = p.get("position") or {}
            if isinstance(pos, dict) and isinstance(pos.get("x"), (int, float)) and isinstance(pos.get("z"), (int, float)):
                px, pz = int(pos["x"]), int(pos["z"])
                if px + pr < x0 or px - pr > x1 or pz + pr < z0 or pz - pr > z1:
                    continue
                mark(rect(px - pr, pz - pr, px + pr, pz + pr), "within %d of placement %s" % (pr, p["id"]))
        # every x/z another data file authors
        import southern_residents as SR
        ac = kc["authored_clearance"]
        m = np.zeros(shape, bool)
        first = {}
        for ax, az, f in SR.authored_points({"residents": []}, own_file=SPEC):
            if x0 - ac <= ax <= x1 + ac and z0 - ac <= az <= z1 + ac:
                ax, az = int(round(ax)), int(round(az))
                xa, xb, za, zb = max(x0, ax - ac), min(x1, ax + ac), max(z0, az - ac), min(z1, az + ac)
                if xa > xb or za > zb:
                    continue
                zz, xx = np.ogrid[za - az:zb - az + 1, xa - ax:xb - ax + 1]
                disc = zz * zz + xx * xx <= ac * ac
                if disc.any():
                    first.setdefault(f, (ax, az))
                    m[za - z0:zb - z0 + 1, xa - x0:xb - x0 + 1] |= disc
        if m.any():
            mark(m, "within %d of an x/z another data file authors (%s)" % (ac, ", ".join("%s %s" % kv for kv in sorted(first.items()))))
        # every other built pack's writes
        packs = ir / "build" / "datapacks"
        others = [p for p in sorted(packs.iterdir()) if p.is_dir() and p.name != own_pack] if packs.is_dir() else []
        if not others:
            if need_packs:
                raise CaveError("no built packs under %s: the other packs' writes are a keep-clear rule (pass "
                                "--inputs-root <a full checkout>)" % packs)
            self.notes.append("the other packs' writes: NOT CHECKED (no built packs under %s)" % packs)
        else:
            pg = kc["pack_gap"]
            for p in others:
                m = np.zeros(shape, bool)
                for (xa, za, xb, zb) in pack_boxes(p):
                    if xb < x0 - pg or xa > x1 + pg or zb < z0 - pg or za > z1 + pg:
                        continue
                    put_rect(m, xa - pg, za - pg, xb + pg, zb + pg)
                if m.any():
                    self.pack_why[p.name] = int(m.sum())
                    mark(m, "within %d of pack %s's writes" % (pg, p.name))
            self.notes.append("the other packs' writes: %d packs read under %s" % (len(others), packs))

    @staticmethod
    def _stamp(dst, src, ox, oz):
        """dst |= src placed with its corner at (ox, oz) in dst's index space (clipped)."""
        h, w = src.shape
        za, xa = max(0, oz), max(0, ox)
        zb, xb = min(dst.shape[0], oz + h), min(dst.shape[1], ox + w)
        if za < zb and xa < xb:
            dst[za:zb, xa:xb] |= src[za - oz:zb - oz, xa - ox:xb - ox]

    def _crop(self, arr, ax0, az0):
        x0, z0, x1, z1 = self.box
        out = np.zeros(self.code.shape, bool)
        sub = arr[z0 - az0:z1 - az0 + 1, x0 - ax0:x1 - ax0 + 1]
        out[:sub.shape[0], :sub.shape[1]] = sub
        return out

    def inside(self, x, z):
        return self.box[0] <= x <= self.box[2] and self.box[1] <= z <= self.box[3]

    def why(self, x, z):
        if not self.inside(x, z):
            return "outside the cave's checked box"
        c = self.code[z - self.box[1], x - self.box[0]]
        return self.reasons[c] if c else None

    def tree(self, x, z):
        return self.inside(x, z) and bool(self.trees[z - self.box[1], x - self.box[0]])


WRITE = re.compile(r"(?:^|\brun\s+)(fill|setblock|place\s+template\s+\S+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)"
                   r"(?:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+))?", re.M)


def pack_boxes(pack_dir):
    """[(x0, z0, x1, z1)] of every absolute fill, setblock and template origin (held TEMPLATE_REACH round) in a pack."""
    out = []
    for f in sorted((pack_dir / "data").rglob("*.mcfunction")) if (pack_dir / "data").is_dir() else []:
        for m in WRITE.finditer(f.read_text(encoding="utf-8", errors="replace")):
            kind = m.group(1)
            x, z = int(m.group(2)), int(m.group(4))
            if kind == "fill" and m.group(5) is not None:
                xb, zb = int(m.group(5)), int(m.group(7))
                out.append((min(x, xb), min(z, zb), max(x, xb), max(z, zb)))
            elif kind.startswith("place"):
                out.append((x - TEMPLATE_REACH, z - TEMPLATE_REACH, x + TEMPLATE_REACH, z + TEMPLATE_REACH))
            else:
                out.append((x, z, x, z))
    return out


def check_box(spec, cave):
    """The box a cave's clearance is computed over: its host anchor, its ring and its own reach."""
    ur, dr = extent(spec, cave)
    r = cave["ring"]["max"] + max(ur, dr) + 8
    hx, hz = cave["host_anchor"]
    return (hx - r, hz - r, hx + r, hz + r)


def cave_problems(spec, cave, gm, clear):
    probs = list(gm["problems"])
    hx, hz = cave["host_anchor"]
    ax, az = gm["anchor"]
    dist = math.hypot(ax - hx, az - hz)
    if not cave["ring"]["min"] <= dist <= cave["ring"]["max"]:
        probs.append("the mouth is %.0f from its host anchor, outside the ring %s" % (dist, cave["ring"]))
    bad = {}
    for c in gm["columns"]:
        w = clear.why(*c)
        if w:
            bad.setdefault(w, []).append(c)
    for c in gm["surface"]:
        if clear.tree(*c):
            bad.setdefault("within %d of a painted tree (a surface column)" % spec["keep_clear"]["tree_reach"], []).append(c)
    for w, cs in sorted(bad.items()):
        probs.append("%d written column(s) %s, e.g. %s" % (len(cs), w, cs[0]))
    return probs


# ------------------------------------------------------------------ the search (an authoring aid)

def search(spec, cave, g0, clear, top=8):
    """Candidate mouths, best first: [(score, anchor, front, y0, dug)]. Anchors on a 2-block grid inside the ring whose
    whole footprint is free; a quick cover estimate; then the full checks. Score: the distance from the host anchor
    plus a tenth of the cells dug (nearer reads as the place's; less cut is less scar)."""
    geo = spec["geometry"]
    ur, dr = extent(spec, cave)
    hx, hz = cave["host_anchor"]
    x0, z0, x1, z1 = clear.box
    ground = M.BoxGround(g0, x0 - 8, z0 - 8, x1 + 8, z1 + 8)
    garr = ground.arr
    gx0, gz0 = ground.x0, ground.z0
    free = clear.code == 0
    sat = np.zeros((free.shape[0] + 1, free.shape[1] + 1), np.int32)
    sat[1:, 1:] = np.cumsum(np.cumsum(~free, 0), 1)

    def clear_rect(xa, za, xb, zb):
        if xa < x0 or za < z0 or xb > x1 or zb > z1:
            return False
        i0, j0, i1, j1 = za - z0, xa - x0, zb - z0 + 1, xb - x0 + 1
        return sat[i1, j1] - sat[i0, j1] - sat[i1, j0] + sat[i0, j0] == 0

    hw, PH, H, cover, drop = geo["passage_half_width"], geo["passage_height"], geo["gallery_height"], geo["cover_min"], cave["drop"]
    rmin, rmax = cave["ring"]["min"], cave["ring"]["max"]
    cands = []
    for front in FRONTS:
        for cz in range(hz - rmax, hz + rmax + 1, 2):
            for cx in range(hx - rmax, hx + rmax + 1, 2):
                dist = math.hypot(cx - hx, cz - hz)
                if not rmin <= dist <= rmax:
                    continue
                xz = M.frame((cx, cz), front)
                (ax_, az_), (bx_, bz_) = xz(-ur, -geo["approach_rows"]), xz(ur, dr)
                if not clear_rect(min(ax_, bx_), min(az_, bz_), max(ax_, bx_), max(az_, bz_)):
                    continue
                row = sorted(int(garr[xz(u, -1)[1] - gz0, xz(u, -1)[0] - gx0]) for u in range(-hw - 1, hw + 2))
                y0 = row[(len(row) - 1) // 2]
                (ax_, az_), (bx_, bz_) = xz(-ur, drop + 1), xz(ur, dr - 1)
                zone = garr[min(az_, bz_) - gz0:max(az_, bz_) + 1 - gz0, min(ax_, bx_) - gx0:max(ax_, bx_) + 1 - gx0]
                if int(zone.min()) < y0 - drop + max(PH, H) + 1 + cover:
                    continue
                cands.append((dist, (cx, cz), front))
    cands.sort()
    out = []
    for dist, anchor, front in cands[:4000]:
        gm = geometry(spec, cave, ground, anchor, front)
        if cave_problems(spec, cave, gm, clear):
            continue
        out.append((round(dist + 0.1 * gm["dug"], 1), list(anchor), front, gm["y0"], gm["dug"]))
        if top and len(out) >= top * 4:
            break
    out.sort(key=lambda o: (o[0], o[1], o[2]))
    return out[:top] if top else out


# ------------------------------------------------------------------ the model

def model(spec=None, source_root=None, inputs_root=None, need_packs=False):
    """(plan, problems, notes): every cave's geometry, galleries and variants, and its approach box."""
    spec = spec or load()
    g0 = G.Ground(source_root)
    probs = yield_problems(spec)
    notes = []
    plan = []
    seen = set()
    period = spec["restore"]["period_ticks"]
    for cave in spec["caves"]:
        for g in cave["galleries"]:
            if g["id"] in seen:
                probs.append("gallery %s: a duplicate id" % g["id"])
            seen.add(g["id"])
            if g["side"] not in SIDES:
                probs.append("gallery %s: side %r is not left or right" % (g["id"], g["side"]))
        offs = [int(g["offset_ticks"]) % period for g in cave["galleries"]]
        if len(set(offs)) != len(offs):
            probs.append("%s: two galleries share an offset modulo the period" % cave["id"])
        pairs = {(g["side"], g["slot"]) for g in cave["galleries"]}
        if len(pairs) != len(cave["galleries"]):
            probs.append("%s: two galleries share a side and slot" % cave["id"])
        if cave["yield"] not in spec["yields"]:
            probs.append("%s: yield %r is not in yields" % (cave["id"], cave["yield"]))
            continue
        if not cave.get("entry"):
            probs.append("%s: no entry (python tools/mining_caves.py author)" % cave["id"])
            continue
        clear = Clearance(spec, check_box(spec, cave), g0, inputs_root, need_packs=need_packs)
        notes += ["%s: %s" % (cave["id"], n) for n in clear.notes]
        gm = geometry(spec, cave, g0)
        probs += ["%s: %s" % (cave["id"], p) for p in cave_problems(spec, cave, gm, clear)]
        nv = spec["restore"]["variants"]
        gals = []
        for g in gm["galleries"]:
            try:
                variants = [ore_cells(spec, cave, g, k, gm) for k in range(nv)]
            except CaveError as exc:
                probs.append(str(exc))
                variants = [[] for _ in range(nv)]
            gals.append(dict(g, variants=variants))
        guards = [g["guard"] for g in gals]
        rs = spec["restore"]
        m, up, down = rs["approach_margin"], rs["approach_up"], rs["approach_down"]
        approach = [min(b[0] for b in guards) - m, min(b[1] for b in guards) - down, min(b[2] for b in guards) - m,
                    max(b[3] for b in guards) + m, max(b[4] for b in guards) + up, max(b[5] for b in guards) + m]
        plan.append({"cave": cave, "geometry": gm, "galleries": gals, "approach": approach})
    return plan, probs, notes


# ------------------------------------------------------------------ the pack

def role_block(cave, role, front):
    if role in ("fill", "skin"):
        return cave["wall"]
    if role == "floor":
        return cave["floor"]
    if role == "stair":
        return "%s[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (cave["stair"], front)
    if role == "shell":
        return cave["shell"]
    if role == "post":
        return "%s[axis=y]" % cave["timber"]
    if role == "beam":
        return "%s[axis=%s]" % (cave["timber"], "x" if front in ("north", "south") else "z")
    if role == "lantern":
        return LANTERN
    return AIR


def host(spec, cave):
    return yields(spec, cave)["host"]


def formation(spec, cave, g):
    """{cell: block} of one gallery's formation (what the restore puts back first): body as host, shell as shell."""
    out = {c[:3]: host(spec, cave) for c in g["body"]}
    out.update({c: cave["shell"] for c in g["shell"]})
    return out


def build_lines(spec, entry):
    """The cave's build function: the air first, then every solid (floor, stairs, fill, skin, shell, body as host),
    the galleries' ore at variant 0, then the frame and the lanterns."""
    cave, gm = entry["cave"], entry["geometry"]
    front = gm["front"]
    air, solid, last = {}, {}, {}
    for c, role in gm["cells"].items():
        if role == "air":
            air[c] = AIR
        elif role in ("post", "beam", "lantern"):
            last[c] = role_block(cave, role, front)
        elif role == "body":
            solid[c] = host(spec, cave)
        else:
            solid[c] = role_block(cave, role, front)
    for g in entry["galleries"]:
        for c, ore in g["variants"][0]:
            solid[c] = ore
    head = ["# Generated by tools/mining_caves.py from data/mining_caves.json: %s (%s) at %s" % (cave["name"], cave["id"], cave["place"]),
            "# the air first, then the floor, the stairs, the fill, the skin, the galleries' shell and body, the ore at",
            "# variant 0; then the mouth's timber frame and the lanterns"]
    return head + M.column_runs(air) + M.column_runs(solid) + M.column_runs(last)


def driver_files(spec, plan):
    """tools/mines.py driver_files (mines.py:683-761) for galleries: the same load, tick, drive, check, restore and
    variant functions, under cobblers:mining_caves and the mcv.* objectives."""
    rs = spec["restore"]
    period = rs["period_ticks"]
    nv = rs["variants"]
    tag = "#%s:%s" % (NS, rs["resettable_tag"])
    fn = {}
    load_ = ["# the mining caves' driver state (tools/mining_caves.py): scores live in the world's scoreboard, so a restore",
             "# that has happened is not repeated after a restart; a gallery with no score yet is due",
             "scoreboard objectives add %s dummy" % T_, "scoreboard objectives add %s dummy" % LAST,
             "scoreboard objectives add %s dummy" % VAR,
             "scoreboard players set #period %s %d" % (T_, period), "scoreboard players set #variants %s %d" % (T_, nv)]
    for e in plan:
        for g in e["galleries"]:
            gid = g["gallery"]["id"]
            load_.append("execute unless score #%s %s matches -2147483648.. run scoreboard players set #%s %s %d"
                         % (gid, LAST, gid, LAST, -int(g["gallery"]["offset_ticks"])))
            load_.append("execute unless score #%s %s matches -2147483648.. run scoreboard players set #%s %s 0"
                         % (gid, VAR, gid, VAR))
    fn["load"] = load_
    fn["tick"] = ["# every tick one counter; every %d ticks the work, which runs only where a player is near" % rs["every_ticks"],
                  "scoreboard players add #clock %s 1" % T_,
                  "execute if score #clock %s matches %d.. run function %s/drive" % (T_, rs["every_ticks"], F)]
    drive = ["scoreboard players set #clock %s 0" % T_,
             "execute store result score #now %s run time query gametime" % T_]
    for e in plan:
        a = e["approach"]
        drive.append("execute if entity @a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d] run function %s/near_%s"
                     % (a[0], a[1], a[2], a[3] - a[0], a[4] - a[1], a[5] - a[2], F, e["cave"]["id"]))
    fn["drive"] = drive
    for e in plan:
        cave = e["cave"]
        fn["near_%s" % cave["id"]] = ["# a player is within the approach box of %s: check each gallery" % cave["name"]] + \
            ["function %s/galleries/check_%s" % (F, g["gallery"]["id"]) for g in e["galleries"]]
        for g in e["galleries"]:
            gid = g["gallery"]["id"]
            gx0, gy0, gz0, gx1, gy1, gz1 = g["guard"]
            vol = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (gx0, gy0, gz0, gx1 - gx0, gy1 - gy0, gz1 - gz0)
            fn["galleries/check_%s" % gid] = [
                "# restore on approach (tools/mines.py's check): the period has passed, the guard box's four corners are",
                "# loaded, and nobody and no Pokemon stands in the gallery or one block round it (the mandatory guard)",
                "scoreboard players operation #d %s = #now %s" % (T_, T_),
                "scoreboard players operation #d %s -= #%s %s" % (T_, gid, LAST),
                "execute if score #d %s < #period %s run return 0" % (T_, T_),
                "execute unless loaded %d %d %d run return 0" % (gx0, gy0, gz0),
                "execute unless loaded %d %d %d run return 0" % (gx1, gy0, gz0),
                "execute unless loaded %d %d %d run return 0" % (gx0, gy0, gz1),
                "execute unless loaded %d %d %d run return 0" % (gx1, gy0, gz1),
                "execute if entity @a[%s] run return 0" % vol,
                "execute if entity @e[type=cobblemon:pokemon,%s] run return 0" % vol,
                "function %s/galleries/restore_%s" % (F, gid)]
            restore = ["# the whole formation back first (body and shell, over the resettable tag only: a player's chest",
                       "# survives), then a variant other than the last one: random value 0..%d, moved on by one if it repeats" % (nv - 1),
                       "function %s/galleries/%s_rock" % (F, gid),
                       "execute store result score #v %s run random value 0..%d" % (T_, nv - 1),
                       "execute if score #v %s = #%s %s run scoreboard players add #v %s 1" % (T_, gid, VAR, T_),
                       "scoreboard players operation #v %s %%= #variants %s" % (T_, T_),
                       "scoreboard players operation #%s %s = #v %s" % (gid, VAR, T_)]
            for k in range(nv):
                restore.append("execute if score #v %s matches %d run function %s/galleries/%s_v%d" % (T_, k, F, gid, k))
            restore.append("scoreboard players operation #%s %s = #now %s" % (gid, LAST, T_))
            # the cave's other galleries: due no sooner than their stagger after this restore (mines.py's sibling rule)
            for o in e["galleries"]:
                og = o["gallery"]
                if og["id"] == gid:
                    continue
                delta = (int(og["offset_ticks"]) - int(g["gallery"]["offset_ticks"])) % period
                restore += ["scoreboard players operation #sib %s = #now %s" % (T_, T_),
                            "scoreboard players remove #sib %s %d" % (T_, period - delta),
                            "scoreboard players operation #%s %s > #sib %s" % (og["id"], LAST, T_)]
            fn["galleries/restore_%s" % gid] = restore
            fn["galleries/%s_rock" % gid] = ["# chunks-loaded-by: %s/galleries/check_%s (execute if loaded, the guard box's four corners)"
                                             % (F, gid)] + M.column_runs(formation(spec, cave, g), tag)
            hb = host(spec, cave)
            for k, ores in enumerate(g["variants"]):
                body = ["# chunks-loaded-by: %s/galleries/check_%s (execute if loaded, the guard box's four corners)" % (F, gid)]
                for (x, y, z), ore in sorted(ores):
                    body.append("execute if block %d %d %d %s run setblock %d %d %d %s" % (x, y, z, hb, x, y, z, ore))
                fn["galleries/%s_v%d" % (gid, k)] = body
    return fn


def build_functions(spec=None):
    """The build function names step R9OC runs, in order, from the committed data (not from a built pack)."""
    spec = spec or load()
    return ["%s/build_%s" % (F, c["id"]) for c in spec["caves"]]


def placed_blocks(spec, plan):
    out = set()
    for e in plan:
        for line in build_lines(spec, e):
            t = line.split()
            if t and t[0] == "setblock":
                out.add(base(t[4]))
            elif t and t[0] == "fill":
                out.add(base(t[7]))
        for g in e["galleries"]:
            for v in g["variants"]:
                out |= {base(o) for _c, o in v}
    return out


def pack_problems(spec, plan):
    """Static rules: the tag, and every spawn condition placed allowed by a policy entry scoped to the caves."""
    out = []
    tag = resettable(spec)
    for need in ("minecraft:air", "minecraft:cave_air"):
        if need not in tag:
            out.append("the resettable tag lacks %s: a dug cell would never be restored" % need)
    for v in tag:
        if any(c in v for c in CONTAINERS):
            out.append("the resettable tag holds %s, a container: a restore would delete it and what it holds" % v)
    for cave in spec["caves"]:
        yl = yields(spec, cave) if cave["yield"] in spec["yields"] else {"ores": {}, "host": None}
        for b in [yl["host"], cave["shell"]] + list(yl["ores"]):
            if b not in tag:
                out.append("%s: %s is not in the resettable tag, so the restore cannot put it back or clear it" % (cave["id"], b))
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    allowed = {b for w in policy["whitelist"] if POLICY_SCOPE in (w.get("scope") or "") for b in w["blocks"]}
    for b in sorted((placed_blocks(spec, plan) & spawn) - allowed):
        out.append("places %s, a spawn condition (data/spawn_blocks.json), and no data/spawn_block_policy.json entry "
                   "scoped to %s allows it" % (b, POLICY_SCOPE))
    return out


def write(spec, plan):
    if OUT.exists():
        shutil.rmtree(OUT)
    base_ = OUT / "data" / NS
    fdir = base_ / "function" / FOLDER
    fdir.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: the refillable mining caves (tools/mining_caves.py, data/mining_caves.json)"}},
                                     indent=2) + "\n", encoding="utf-8")
    counts = {}
    for e in plan:
        name = "build_%s" % e["cave"]["id"]
        body = FL.ensure_loaded(build_lines(spec, e))
        bad = FL.check_lines(body, name)
        if bad:
            raise CaveError("function %s would be refused: %s" % (name, bad[:3]))
        (fdir / (name + ".mcfunction")).write_text("\n".join(body) + "\n", encoding="utf-8")
        counts[name] = len(body)
    for name, body in sorted(driver_files(spec, plan).items()):
        bad = FL.check_lines(body, name)
        if bad:
            raise CaveError("function %s would be refused: %s" % (name, bad[:3]))
        p = fdir / (name + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(body) + "\n", encoding="utf-8")
    tags = OUT / "data" / "minecraft" / "tags" / "function"
    tags.mkdir(parents=True)
    (tags / "load.json").write_text(json.dumps({"values": ["%s/load" % F]}, indent=2) + "\n", encoding="utf-8")
    (tags / "tick.json").write_text(json.dumps({"values": ["%s/tick" % F]}, indent=2) + "\n", encoding="utf-8")
    bt = base_ / "tags" / "block"
    bt.mkdir(parents=True)
    (bt / ("%s.json" % spec["restore"]["resettable_tag"])).write_text(
        json.dumps({"values": resettable(spec)}, indent=2) + "\n", encoding="utf-8")
    return counts


def plan_json(spec, plan, counts):
    caves = {}
    for e in plan:
        gm = e["geometry"]
        gals = {}
        for g in e["galleries"]:
            per = {}
            for k, v in enumerate(g["variants"]):
                for _c, ore in v:
                    per.setdefault(ore, [0] * len(g["variants"]))[k] += 1
            gals[g["gallery"]["id"]] = {"side": g["gallery"]["side"], "slot": g["gallery"]["slot"],
                                        "offset_ticks": g["gallery"]["offset_ticks"], "bounds": g["bounds"],
                                        "guard": g["guard"], "body_cells": len(g["body"]), "shell_cells": len(g["shell"]),
                                        "ore_per_variant": {o: per[o] for o in sorted(per)}}
        caves[e["cave"]["id"]] = {"place": e["cave"]["place"], "anchor": gm["anchor"], "front": gm["front"],
                                  "mouth_floor": gm["y0"], "hall_floor": gm["yh"], "stand": gm["stand"],
                                  "hall_stand": gm["hall_stand"], "bounds": gm["bounds"], "approach": e["approach"],
                                  "dug": gm["dug"], "galleries": gals}
    return {"schema": "cobblers.derived.mining-caves/1", "build_functions": build_functions(spec), "commands": counts,
            "period_ticks": spec["restore"]["period_ticks"], "resettable_tag": "#%s:%s" % (NS, spec["restore"]["resettable_tag"]),
            "caves": caves}


def author(spec, only=None, source_root=None, inputs_root=None, resite=False):
    """Site every cave with no entry yet (or every cave, with --resite): the best candidate search() returns. Writes
    data/mining_caves.json; a cave that cannot be sited stops the run and nothing is written."""
    g0 = G.Ground(source_root)
    for cave in spec["caves"]:
        if only and cave["id"] != only:
            continue
        if cave.get("entry") and not resite:
            continue
        clear = Clearance(spec, check_box(spec, cave), g0, inputs_root, need_packs=True)
        best = search(spec, cave, g0, clear, 1)
        if not best:
            raise SystemExit("%s: no mouth passes every rule; nothing written" % cave["id"])
        cave["entry"] = {"anchor": best[0][1], "front": best[0][2],
                         "sited_by": "tools/mining_caves.py author: the best of search() (distance from host_anchor + "
                                     "a tenth of the cells dug) over the canonical heightmap and the keep_clear rules"}
        print("%s: mouth %s front %s floor y%d (score %s, %d dug)" % (cave["id"], best[0][1], best[0][2], best[0][3],
                                                                      best[0][0], best[0][4]))
    SPEC.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", SPEC.relative_to(ROOT))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("site", "author", "report", "build"))
    p.add_argument("cave", nargs="?")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--resite", action="store_true")
    p.add_argument("--source-root")
    p.add_argument("--inputs-root", help="a full checkout holding build/datapacks, build/paint, derived/routes and "
                                         "derived/water_shape (default: this checkout)")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    spec = load()
    if a.mode == "author":
        return author(spec, a.cave, a.source_root, a.inputs_root, a.resite)
    if a.mode == "site":
        cave = next((c for c in spec["caves"] if c["id"] == a.cave), None)
        if cave is None:
            raise SystemExit("no cave %r" % a.cave)
        g0 = G.Ground(a.source_root)
        clear = Clearance(spec, check_box(spec, cave), g0, a.inputs_root, need_packs=True)
        for o in search(spec, cave, g0, clear, a.top):
            print(json.dumps(o))
        return 0
    try:
        plan, probs, notes = model(spec, a.source_root, a.inputs_root)
    except CaveError as exc:
        raise SystemExit("FAILED: %s; nothing written" % exc)
    probs += pack_problems(spec, plan)
    for e in plan:
        gm = e["geometry"]
        print("  %-14s mouth %s front %-5s floor y%d hall y%d  %d cells, %d dug  galleries %d" % (
            e["cave"]["id"], gm["anchor"], gm["front"], gm["y0"], gm["yh"], len(gm["cells"]), gm["dug"], len(e["galleries"])))
    for n in notes:
        print("  NOTE:", n)
    if probs:
        for pr in probs:
            print("PROBLEM:", pr)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    if a.mode == "report":
        print("report: %d caves, %d galleries, 0 problems" % (len(plan), sum(len(e["galleries"]) for e in plan)))
        return 0
    counts = write(spec, plan)
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan_json(spec, plan, counts), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print("wrote %s: %d caves, %d galleries; plan %s" % (OUT.relative_to(ROOT), len(plan),
                                                         sum(len(e["galleries"]) for e in plan), PLAN.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
