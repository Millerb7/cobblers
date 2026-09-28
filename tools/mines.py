#!/usr/bin/env python
"""The evolution-stone faces (docs/mechanics/STONE_ECONOMY.md, ADR-003 as amended), from data/mines.json.

Ten stones at seven places, two faces per stone per place, each face a 9 x 5 x 6 box of host rock holding a few of
Cobblemon's own stone ores (rung 1: the ore drops its stone to whoever breaks it, by Cobblemon's own loot table). The
rest is rung 7, a generated datapack, `cobblers_mines`:

  the cut       each face is opened from the town's side: a level apron of `apron_rows` rows in front of the face, then
                a ramp of rows that climbs or falls one block a row until it meets the natural ground within one; the
                cut is dug to air from its floor up to the ground (plus `clear_above`, which takes the plants off), a
                built-up row is filled with host rock; every natural cell the cut exposes is skinned in host rock
  the backing   two blocks of host rock round every hidden side of the box, and bedrock one block further out where the
                site says (only in the Displaced City's shell: STONE_ECONOMY.md 6.4, near an authored void)
  the restore   on approach (5.3): the pack's tick counts to `every_ticks`, and while a player is inside the site's
                approach box each face whose period has passed, whose four corners are loaded, and in whose box (grown
                by one) no player and no Pokemon stands, is restored: a fill of host rock over the tag
                #cobblers:face_resettable only (5.4: a player's chest survives), then that variant's ore by guarded
                setblocks. Eight variants; `random value 0..7`, moved on by one if it repeats the last
  the build     `cobblers:mines/build_<site>` per site, run once per export by tools/reapply.py step R9O: the cut, the
                skin, the backing, the bedrock and the faces at variant 0

Where a face may stand (checked here, and by the audit, which recomputes all of it from other files' data):
  ground        the canonical heightmap, rounded (tools/ground.py); the Displaced City's cavern floor from the cavern's
                own plan (tools/ground.py for_settlement); never a world
  cover         every box column's ground at least `backing` over the box top; every backing column's at least one
  occupancy     no written column on the town's plan (tools/town_dressing.py Mask: streets and verges, plaza, lots,
                anchors, buildings grown by 3, earthworks, lamps, the waystone, traders, signposts, scene props and
                event sites, routed legs grown by 3) or outside the town's reach (footprint + 24); none on painted
                water or within 4 of a painted tree trunk; none on or within `water_changed_reach` of a column the
                pending water export changes (derived/water_shape/changed.npy: missing is a failure, not a pass); none
                within `dressing_reach` of a dressing piece or `ambient_reach` of a working Pokemon's station or route;
                in the cavern, none within `tree_reach` of a cavern tree, `light_reach` of a cavern light write or
                `tunnel_reach` of the tunnel's line; and no two faces' writes within `face_gap`
  the cut       the ramp ends within `ramp_max` rows; no column is dug more than `max_cut` or built up more than
                `max_fill`

  python tools/mines.py site <site id> [--stone s] [--top N] [--prefer x,z,window]
                                                                candidate boxes for a site, best first; nothing written
  python tools/mines.py author [<site id>]                      site every face with no box yet (the site's
                                                                `prefer_near` hint, then near its first face) and
                                                                write the boxes into data/mines.json
  python tools/mines.py report                                  every face's checks and counts; nothing written
  python tools/mines.py build                                   -> build/datapacks/cobblers_mines, derived/mines/plan.json

The offline audit, independent of this tool's model, is tools/mines_audit.py.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "mines.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_mines"
PLAN = ROOT / "derived" / "mines" / "plan.json"
WATER_CHANGED = ROOT / "derived" / "water_shape" / "changed.npy"
CAVERN_PLAN = ROOT / "derived" / "cavern" / "plan.json"
CAVERN_LIGHT = ROOT / "build" / "datapacks" / "cobblers_cavern" / "data" / "cobblers" / "function" / "cavern" / "40_light.mcfunction"
NS = "cobblers"
FOLDER = "mines"
F = "%s:%s" % (NS, FOLDER)
AIR = "minecraft:air"
LANTERN = "minecraft:lantern[hanging=false,waterlogged=false]"
FRONTS = ("north", "south", "west", "east")
NEAR_WINDOW = 64                 # a later face of a site is sought within this many blocks of the first


class MineError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def h32(*vals):
    """FNV-style 32-bit mix of integers (the same mix tools/rift_mines.py uses)."""
    a = 0x811C9DC5
    for v in vals:
        a = ((a ^ (int(v) & 0xFFFFFFFF)) * 0x01000193) & 0xFFFFFFFF
        a ^= a >> 15
        a = (a * 0x2C1B3C6D) & 0xFFFFFFFF
        a ^= a >> 12
    return a


def sid(s):
    """A string as an integer for h32: its length and the sum of its code points."""
    return len(s) * 1000003 + sum(ord(c) * (i + 1) for i, c in enumerate(s))


# ------------------------------------------------------------------ the face's frame

def frame(box, front):
    """(xz(u, d), W, D) for a box and the side a player works it from.

    u runs along the face (0 .. W-1), d into the rock (0 is the front plane, D-1 the back); d < 0 is in front of the
    face, row r being d = -r. North: the front plane is z0 and the rock runs +z; south: z1, -z; west: x0, +x;
    east: x1, -x. u runs +x on a north or south face and +z on a west or east face."""
    x0, _y0, z0, x1, _y1, z1 = box
    if front == "north":
        return (lambda u, d: (x0 + u, z0 + d)), x1 - x0 + 1, z1 - z0 + 1
    if front == "south":
        return (lambda u, d: (x0 + u, z1 - d)), x1 - x0 + 1, z1 - z0 + 1
    if front == "west":
        return (lambda u, d: (x0 + d, z0 + u)), z1 - z0 + 1, x1 - x0 + 1
    if front == "east":
        return (lambda u, d: (x1 - d, z0 + u)), z1 - z0 + 1, x1 - x0 + 1
    raise MineError("front %r is not one of %s" % (front, ", ".join(FRONTS)))


def box_for(front, cx, cz, y0, geo):
    """The box whose front plane's middle column is (cx, cz): W along the face, D deep, H high."""
    W, D, H = geo["width"], geo["depth"], geo["height"]
    h = W // 2
    if front == "north":
        return [cx - h, y0, cz, cx - h + W - 1, y0 + H - 1, cz + D - 1]
    if front == "south":
        return [cx - h, y0, cz - D + 1, cx - h + W - 1, y0 + H - 1, cz]
    if front == "west":
        return [cx, y0, cz - h, cx + D - 1, y0 + H - 1, cz - h + W - 1]
    return [cx - D + 1, y0, cz - h, cx, y0 + H - 1, cz - h + W - 1]


# ------------------------------------------------------------------ one face's geometry

def geometry(face, ground, geo, bedrock=False):
    """Everything a face writes, from its box, its front and the ground: a dict of cell -> role, plus the cut's rows.

    Roles: box, backing, bedrock, floor, fill, air, skin. Raises MineError when a rule of the cut or the cover fails."""
    box = face["box"]
    x0, y0, z0, x1, y1, z1 = box
    xz, W, D = frame(box, face["front"])
    H = y1 - y0 + 1
    if (W, D, H) != (geo["width"], geo["depth"], geo["height"]):
        raise MineError("%s: the box is %d wide, %d deep and %d high along its %s front; the geometry says %d x %d x %d"
                        % (face["id"], W, D, H, face["front"], geo["width"], geo["depth"], geo["height"]))
    B, A, M = geo["backing"], geo["apron_rows"], geo["apron_margin"]
    cells = {}
    problems = []
    for u in range(W):
        for d in range(D):
            x, z = xz(u, d)
            if ground(x, z) < y1 + B:
                problems.append("box column (%d, %d): ground y%d, under the box top y%d + %d of backing"
                                % (x, z, ground(x, z), y1, B))
            for y in range(y0, y1 + 1):
                cells[(x, y, z)] = "box"
    for u in range(-B, W + B):
        for d in range(0, D + B):
            x, z = xz(u, d)
            inside = 0 <= u < W and d < D
            if not inside and ground(x, z) < y1 + 1:
                problems.append("backing column (%d, %d): ground y%d, under the box top y%d + 1" % (x, z, ground(x, z), y1))
            for y in range(y0 - B, y1 + B + 1):
                if (x, y, z) not in cells:
                    cells[(x, y, z)] = "backing"
    if bedrock:
        for u in range(-B - 1, W + B + 1):
            for d in range(1, D + B + 1):
                x, z = xz(u, d)
                for y in range(y0 - B - 1, y1 + B + 2):
                    edge = u in (-B - 1, W + B) or d == D + B or y in (y0 - B - 1, y1 + B + 1)
                    if edge and (x, y, z) not in cells:
                        if y > ground(x, z) - 1:
                            problems.append("bedrock at (%d, %d, %d) would stand at or over the ground y%d"
                                            % (x, y, z, ground(x, z)))
                        cells[(x, y, z)] = "bedrock"
    # the cut: the apron, then the ramp
    rows = []
    t = y0 - 1
    r = 1
    while True:
        cols = [xz(u, -r) for u in range(-M, W + M)]
        gs = [ground(x, z) for x, z in cols]
        if r > A:
            if all(abs(g - t) <= 1 for g in gs):
                break                                     # this row is natural ground a player steps onto
            if r > A + geo["ramp_max"]:
                problems.append("the ramp does not meet the ground within %d rows (row %d: ground %s, floor y%d)"
                                % (geo["ramp_max"], r, sorted(set(gs)), t))
                break
            med = sorted(gs)[len(gs) // 2]
            t += (med > t) - (med < t)
        rows.append((r, t))
        for (x, z), g in zip(cols, gs):
            if g - t > geo["max_cut"]:
                problems.append("cut column (%d, %d): dug %d, over %d" % (x, z, g - t, geo["max_cut"]))
            if t - g > geo["max_fill"]:
                problems.append("cut column (%d, %d): built up %d, over %d" % (x, z, t - g, geo["max_fill"]))
            for y in range(g + 1, t):
                cells[(x, y, z)] = "fill"
            cells[(x, t, z)] = "floor"
            top = max(g, t) + geo["clear_above"]
            if r <= A:
                top = max(top, y1 + 1)
            for y in range(t + 1, top + 1):
                cells[(x, y, z)] = "air"
        r += 1
    # the skin: every natural cell next to the cut's air, at or under its column's ground
    skin = {}
    for (x, y, z), role in cells.items():
        if role != "air":
            continue
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)):
            c = (x + dx, y + dy, z + dz)
            if c not in cells and c not in skin and c[1] <= ground(c[0], c[2]):
                skin[c] = "skin"
    cells.update(skin)
    stand = xz(W // 2, -1)
    return {"cells": cells, "rows": rows, "problems": problems, "stand": [stand[0], y0, stand[1]],
            "columns": sorted({(x, z) for x, _y, z in cells})}


def ore_cells(face, k, seed, geo, yld):
    """[(x, y, z)] of variant k's ore: one on the front plane's bottom row away from the corners (the visible tell,
    STONE_ECONOMY.md 5.2), the rest at least 2 deep and under the top row. How many: ore_min + h32(seed, face,
    k) mod (ore_max - ore_min + 1); which cells: the cells ordered by h32(seed, face, k, x, y, z)."""
    box = face["box"]
    x0, y0, z0, x1, y1, z1 = box
    xz, W, D = frame(box, face["front"])
    fid = sid(face["id"])
    n = yld["ore_min"] + h32(seed, fid, k) % (yld["ore_max"] - yld["ore_min"] + 1)
    cells = [(u, d, y) for u in range(W) for d in range(D) for y in range(y0, y1 + 1)]

    def key(c):
        x, z = xz(c[0], c[1])
        return h32(seed, fid, k, x, c[2], z)
    order = sorted(cells, key=key)
    visible = [c for c in order if c[1] == 0 and c[2] == y0 and 1 <= c[0] <= W - 2]
    hidden = [c for c in order if c[1] >= 2 and c[2] < y1]
    vis = visible[:yld.get("visible_min", 1)]
    picked = vis + hidden[:n - len(vis)]
    return [(xz(u, d)[0], y, xz(u, d)[1]) for u, d, y in picked]


# ------------------------------------------------------------------ where a face may stand

def _dilate2(a, n):
    out = a.copy()
    for _ in range(n):
        s = out.copy()
        s[1:, :] |= out[:-1, :]
        s[:-1, :] |= out[1:, :]
        s[:, 1:] |= out[:, :-1]
        s[:, :-1] |= out[:, 1:]
        s[1:, 1:] |= out[:-1, :-1]
        s[1:, :-1] |= out[:-1, 1:]
        s[:-1, 1:] |= out[1:, :-1]
        s[:-1, :-1] |= out[1:, 1:]
        out = s
    return out


def _segment_cells(pts, reach):
    out = set()
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        n = int(max(abs(bx - ax), abs(bz - az))) + 1
        for i in range(n + 1):
            t = i / max(n, 1)
            x, z = round(ax + (bx - ax) * t), round(az + (bz - az) * t)
            for dx in range(-reach, reach + 1):
                for dz in range(-reach, reach + 1):
                    out.add((x + dx, z + dz))
    return out


class Occupancy:
    """(x, z) -> why a face may not write there, or None, for one site; built from other systems' data only."""

    def __init__(self, spec, site, ground, doc, wet):
        import town_dressing as TD
        keep = spec["keep_clear"]
        self.site = site
        self.mask = TD.Mask(site["settlement"], doc, None if site.get("ground") == "cavern_floor" else wet)
        self.why = {}
        s = site["settlement"]
        if site.get("ground") == "cavern_floor":
            cav = json.loads(CAVERN_PLAN.read_text(encoding="utf-8"))
            cx0, cz0, cx1, cz1 = cav["cavern"]
            r = keep["cavern_reach"]
            self.box = (cx0 - r, cz0 - r, cx1 + r, cz1 + r)
            for tr in cav.get("tree_positions") or []:
                x, _y, z = tr["at"]
                for c in _segment_cells([(x, z), (x, z)], keep["tree_reach"]):
                    self.why.setdefault(c, "cavern tree at %d,%d" % (x, z))
            if not CAVERN_LIGHT.is_file():
                raise MineError("no %s: the cavern's light writes are what the faces keep clear of (run tools/cavern_plan.py)"
                                % CAVERN_LIGHT.relative_to(ROOT))
            import town_dressing
            lit = town_dressing.command_columns([l for l in CAVERN_LIGHT.read_text(encoding="utf-8").splitlines()
                                                 if not l.startswith("forceload")])
            for c in _segment_cells(sorted(lit), 0):
                for dx in range(-keep["light_reach"], keep["light_reach"] + 1):
                    for dz in range(-keep["light_reach"], keep["light_reach"] + 1):
                        self.why.setdefault((c[0] + dx, c[1] + dz), "cavern light")
            for c in _segment_cells(cav["tunnel"]["waypoints"], keep["tunnel_reach"]):
                self.why.setdefault(c, "the cavern's tunnel")
        else:
            self.box = self.mask.box
        if not WATER_CHANGED.is_file():
            raise MineError("no %s: the pending water export's changed columns are a keep-clear rule, and a missing map "
                            "is a failure, not a pass" % WATER_CHANGED.relative_to(ROOT))
        x0, z0, x1, z1 = self.box
        n = keep["water_changed_reach"]
        ch = np.load(WATER_CHANGED, mmap_mode="r")
        sub = np.array(ch[max(0, z0 - n):z1 + n + 1, max(0, x0 - n):x1 + n + 1])
        self.water = _dilate2(sub, n)
        self.wox, self.woz = max(0, x0 - n), max(0, z0 - n)
        dress = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))["towns"].get(s) or {}
        for p in ([dress["landmark"]] if dress.get("landmark") else []) + list(dress.get("pieces") or []):
            for c in _segment_cells([tuple(p["at"][:2]), tuple(p["at"][:2])], keep["dressing_reach"]):
                self.why.setdefault(c, "dressing piece %s" % p.get("id"))
        amb = json.loads((ROOT / "data" / "ambient.json").read_text(encoding="utf-8"))
        for w in amb["workers"]:
            if w["settlement"] != s:
                continue
            pts = [tuple(p) for p in w.get("route") or []] or ([tuple(w["at"])] if w.get("at") else [])
            if len(pts) == 1:
                pts = pts * 2
            for c in _segment_cells(pts, keep["ambient_reach"]):
                self.why.setdefault(c, "working Pokemon %s" % w["id"])
        self.cavern = site.get("ground") == "cavern_floor"

    def blocked(self, x, z):
        if not (self.box[0] <= x <= self.box[2] and self.box[1] <= z <= self.box[3]):
            return "outside the site's reach"
        if (x, z) in self.why:
            return self.why[(x, z)]
        if self.cavern:
            w = self.mask.why.get((x, z))
            if w:
                return w
        else:
            w = self.mask.blocked(x, z)
            if w:
                return w
            if self.water[z - self.woz, x - self.wox]:
                return "within the reach of a column the water export changes"
        return None


def site_ground(site, g0=None, source_root=None):
    """The heightmap, or for the Displaced City the heightmap with the cavern floor over the cavern (tools/ground.py
    for_settlement, on its own copy: it rewrites the heights it is given)."""
    if site.get("ground") == "cavern_floor":
        return G.for_settlement(site["settlement"], source_root)
    return g0 or G.Ground(source_root)


def face_problems(spec, site, face, ground, occ, taken=()):
    geo = spec["geometry"]
    try:
        gm = geometry(face, ground, geo, site.get("bedrock_skin", False))
    except MineError as e:
        return [str(e)], None
    probs = list(gm["problems"])
    bad = {}
    for c in gm["columns"]:
        w = occ.blocked(*c)
        if w:
            bad.setdefault(w, []).append(c)
    for w, cs in bad.items():
        probs.append("%d written column(s) %s, e.g. %s" % (len(cs), w, cs[0]))
    gap = spec["keep_clear"]["face_gap"]
    near = {(x + dx, z + dz) for x, z in taken for dx in range(-gap, gap + 1) for dz in range(-gap, gap + 1)}
    hit = [c for c in gm["columns"] if c in near]
    if hit:
        probs.append("%d column(s) within %d of another face's writes, e.g. %s" % (len(hit), gap, hit[0]))
    return probs, gm


# ------------------------------------------------------------------ the site search (an authoring aid)

class BoxGround:
    """The same ground as `g` (rounded, tools/ground.py), read from one array over a box: the search asks for millions
    of columns, and numpy's per-call round was most of its time. Outside the box it asks `g`."""

    def __init__(self, g, x0, z0, x1, z1):
        self.g, self.x0, self.z0, self.x1, self.z1 = g, x0, z0, x1, z1
        self.a = g.box(x0, z0, x1, z1).tolist()

    def __call__(self, x, z):
        if self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1:
            return self.a[z - self.z0][x - self.x0]
        return self.g(x, z)


def search_context(spec, site, source_root=None):
    g0 = G.Ground(source_root)
    ground = site_ground(site, g0, source_root)
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    import town_dressing as TD
    wet = None if site.get("ground") == "cavern_floor" else TD.wet_fn(g0)
    occ = Occupancy(spec, site, ground, doc, wet)
    x0, z0, x1, z1 = occ.box
    free = np.ones((z1 - z0 + 1, x1 - x0 + 1), bool)
    for z in range(z0, z1 + 1):
        for x in range(x0, x1 + 1):
            if occ.blocked(x, z):
                free[z - z0, x - x0] = False
    return {"ground": BoxGround(ground, x0 - 48, z0 - 48, x1 + 48, z1 + 48), "occ": occ, "free": free}


def search(spec, site, stone=None, top=8, source_root=None, taken_faces=(), near=None, ctx=None):
    geo = spec["geometry"]
    ctx = ctx or search_context(spec, site, source_root)
    ground, occ, free = ctx["ground"], ctx["occ"], ctx["free"].copy()
    x0, z0, x1, z1 = occ.box
    taken = set()
    for f in taken_faces:
        taken |= set(tuple(c) for c in geometry(f, ground, geo, site.get("bedrock_skin", False))["columns"])
    towns = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}
    centre = ((x0 + x1) / 2, (z0 + z1) / 2) if site.get("ground") == "cavern_floor" else \
        (towns[site["settlement"]]["centre"]["x"], towns[site["settlement"]]["centre"]["z"])
    out = []
    W, D, B, A = geo["width"], geo["depth"], geo["backing"], geo["apron_rows"]
    step = site.get("search_step", 2)
    # a siting hint from the data: where the place's working is (the Mining Town's faces at its mine head), searched
    # within prefer_window of it and scored by the distance to it
    pn = site.get("prefer_near")
    prefer = tuple(pn["at"]) if pn else None
    prefer_window = pn["window"] if pn else 0
    gap = spec["keep_clear"]["face_gap"]
    for c in taken:
        for dx in range(-gap, gap + 1):
            for dz in range(-gap, gap + 1):
                if x0 <= c[0] + dx <= x1 and z0 <= c[1] + dz <= z1:
                    free[c[1] + dz - z0, c[0] + dx - x0] = False
    sat = np.zeros((free.shape[0] + 1, free.shape[1] + 1), np.int32)
    sat[1:, 1:] = np.cumsum(np.cumsum(~free, 0), 1)

    def clear(xa, za, xb, zb):
        xa, xb, za, zb = min(xa, xb), max(xa, xb), min(za, zb), max(za, zb)
        if xa < x0 or za < z0 or xb > x1 or zb > z1:
            return False
        i0, j0, i1, j1 = za - z0, xa - x0, zb - z0 + 1, xb - x0 + 1
        return sat[i1, j1] - sat[i0, j1] - sat[i1, j0] + sat[i0, j0] == 0
    for front in FRONTS:
        for cz in range(z0, z1 + 1, step):
            for cx in range(x0, x1 + 1, step):
                if near is not None and max(abs(cx - near[0]), abs(cz - near[1])) > NEAR_WINDOW:
                    continue
                if prefer is not None and max(abs(cx - prefer[0]), abs(cz - prefer[1])) > prefer_window:
                    continue
                b = box_for(front, cx, cz, 0, geo)
                xz, _W, _D = frame(b, front)
                # the whole of the box, its backing, the apron and a block of skin, free before anything is computed
                (xa, za), (xb, zb) = xz(-B - 1, D + B), xz(W + B, -A - 1)
                if not clear(xa, za, xb, zb):
                    continue
                # F: the higher of "the box sits backing under the lowest box column" and "the apron is the ground"
                boxg = min(ground(*xz(u, d)) for u in range(W) for d in range(D))
                apron = sorted(ground(*xz(u, -1)) for u in range(-1, W + 1))
                f_top = boxg - B - (geo["height"] - 1)
                y0 = min(f_top, apron[len(apron) // 2] + 1)
                face = {"id": "probe", "box": box_for(front, cx, cz, y0, geo), "front": front}
                try:
                    gm = geometry(face, ground, geo, site.get("bedrock_skin", False))
                except MineError:
                    continue
                # the free grid is the occupancy (plus the faces already sited, grown by the gap), computed once;
                # model() checks the chosen boxes column by column again
                if gm["problems"] or any(not (x0 <= x <= x1 and z0 <= z <= z1) or not free[z - z0, x - x0]
                                         for x, z in gm["columns"]):
                    continue
                cells = gm["cells"]
                dug = sum(1 for (x, y, z), r in cells.items() if r == "air" and y <= ground(x, z))
                built = sum(1 for r in cells.values() if r == "fill")
                fx, fz = xz(W // 2, -1)
                dx, dz = centre[0] - fx, centre[1] - fz
                ox, oz = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}[front]
                away = (dx * ox + dz * oz) < 0
                score = dug + 3 * built + 5 * len(gm["rows"]) + (400 if away else 0) + 0.2 * math.hypot(dx, dz)
                if near is not None:
                    score += 3 * math.hypot(fx - near[0], fz - near[1])
                if prefer is not None:
                    score += 3 * math.hypot(fx - prefer[0], fz - prefer[1])
                out.append((round(score, 1), face["box"], front, len(gm["rows"]), dug, built, away))
    out.sort(key=lambda o: o[0])
    return out[:top] if top else out


# ------------------------------------------------------------------ the model of every face

def model(spec=None, source_root=None):
    """(plan, problems): every site's faces with their geometry, the variants' ore, and the site's approach box."""
    spec = spec or load()
    geo = spec["geometry"]
    g0 = G.Ground(source_root)
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    import town_dressing as TD
    wet = TD.wet_fn(g0)
    stones = spec["stones"]
    plan, probs = [], []
    seen = set()
    for site in spec["sites"]:
        ground = site_ground(site, g0, source_root)
        occ = Occupancy(spec, site, ground, doc, wet)
        taken = set()
        faces = []
        for face in site["faces"]:
            if face["id"] in seen:
                probs.append("face %s: a duplicate id" % face["id"])
            seen.add(face["id"])
            st = stones.get(face["stone"])
            if st is None:
                probs.append("face %s: stone %r is not in stones" % (face["id"], face["stone"]))
                continue
            if face["ore"] not in st["ores"]:
                probs.append("face %s: %s is not one of the %s stone's ores %s" % (face["id"], face["ore"], face["stone"], st["ores"]))
            p, gm = face_problems(spec, site, face, ground, occ, taken)
            probs += ["%s/%s: %s" % (site["id"], face["id"], x) for x in p]
            if gm is None:
                continue
            taken |= set(gm["columns"])
            yld = face["yield"]
            variants = [ore_cells(face, k, spec["seed"], geo, yld) for k in range(spec["restore"]["variants"])]
            faces.append({"face": face, "geometry": gm, "variants": variants})
        xs = [c for f in faces for c in (f["face"]["box"][0], f["face"]["box"][3])]
        zs = [c for f in faces for c in (f["face"]["box"][2], f["face"]["box"][5])]
        ys = [c for f in faces for c in (f["face"]["box"][1], f["face"]["box"][4])]
        if not faces:
            probs.append("%s: no face" % site["id"])
            continue
        m, up, down = spec["restore"]["approach_margin"], spec["restore"]["approach_up"], spec["restore"]["approach_down"]
        approach = [min(xs) - m, min(ys) - down, min(zs) - m, max(xs) + m, max(ys) + up, max(zs) + m]
        plan.append({"site": site, "faces": faces, "approach": approach})
    return plan, probs


# ------------------------------------------------------------------ the pack

def column_runs(cells):
    """fill/setblock lines for {cell: block}, in vertical runs of one block per column."""
    cols = {}
    for (x, y, z), b in cells.items():
        cols.setdefault((x, z), []).append((y, b))
    out = []
    for (x, z) in sorted(cols):
        ys = sorted(cols[(x, z)])
        n = 0
        while n < len(ys):
            y0, b = ys[n]
            k = n
            while k + 1 < len(ys) and ys[k + 1][0] == ys[k][0] + 1 and ys[k + 1][1] == b:
                k += 1
            y1 = ys[k][0]
            out.append("fill %d %d %d %d %d %d %s" % (x, y0, z, x, y1, z, b) if y1 > y0 else "setblock %d %d %d %s" % (x, y0, z, b))
            n = k + 1
    return out


def build_lines(spec, entry):
    """The site's build function body: every face's cut, skin, backing, bedrock and box at variant 0, then lanterns."""
    site = entry["site"]
    solid, air = {}, {}
    lanterns = []
    for f in entry["faces"]:
        face = f["face"]
        host = face["host"]
        for c, role in f["geometry"]["cells"].items():
            if role in ("box", "backing", "fill", "skin"):
                solid[c] = host
            elif role == "bedrock":
                solid[c] = "minecraft:bedrock"
            elif role == "floor":
                solid[c] = face.get("floor") or site["floor_block"]
            elif role == "air":
                air[c] = AIR
        for c in f["variants"][0]:
            solid[c] = face["ore"]
        if site.get("lanterns"):
            xz, W, _D = frame(face["box"], face["front"])
            A = spec["geometry"]["apron_rows"]
            y0 = face["box"][1]
            for u in (-1, W):
                x, z = xz(u, -A)
                lanterns.append("setblock %d %d %d %s" % (x, y0, z, LANTERN))
    head = ["# Generated by tools/mines.py from data/mines.json: the stone faces of %s (%s)" % (site["settlement"], site["id"]),
            "# the cut and its air first, then the rock (skin, backing, bedrock, fill, floor), the faces at variant 0, lanterns"]
    body = column_runs(air) + column_runs(solid) + lanterns
    return head + body


def text(s, **style):
    return json.dumps(dict({"text": s}, **style), ensure_ascii=False)


def driver_files(spec, plan):
    rs = spec["restore"]
    period = rs["period_ticks"]
    tag = "#%s:%s" % (NS, rs["resettable_tag"])
    fn = {}
    load_ = ["# the stone faces' driver state (tools/mines.py): scores live in the world's scoreboard, so a restore that",
             "# has happened is not repeated after a restart (STONE_ECONOMY.md P-4); a face with no score yet is due",
             "scoreboard objectives add mn.t dummy", "scoreboard objectives add mn.last dummy", "scoreboard objectives add mn.var dummy",
             "scoreboard players set #period mn.t %d" % period, "scoreboard players set #eight mn.t 8"]
    for e in plan:
        for f in e["faces"]:
            fid = f["face"]["id"]
            load_.append("execute unless score #%s mn.last matches -2147483648.. run scoreboard players set #%s mn.last %d"
                         % (fid, fid, -int(f["face"]["offset_ticks"])))
            load_.append("execute unless score #%s mn.var matches -2147483648.. run scoreboard players set #%s mn.var 0" % (fid, fid))
    fn["load"] = load_
    fn["tick"] = ["# every tick one counter; every %d ticks the work, which runs only where a player is near" % rs["every_ticks"],
                  "scoreboard players add #clock mn.t 1",
                  "execute if score #clock mn.t matches %d.. run function %s/drive" % (rs["every_ticks"], F)]
    drive = ["scoreboard players set #clock mn.t 0",
             "execute store result score #now mn.t run time query gametime"]
    for e in plan:
        a = e["approach"]
        drive.append("execute if entity @a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d] run function %s/site_%s"
                     % (a[0], a[1], a[2], a[3] - a[0], a[4] - a[1], a[5] - a[2], F, e["site"]["id"]))
    fn["drive"] = drive
    for e in plan:
        site = e["site"]
        fn["site_%s" % site["id"]] = ["# a player is within the approach box of %s: check each face" % site["settlement"]] + \
            ["function %s/faces/check_%s" % (F, f["face"]["id"]) for f in e["faces"]]
        for f in e["faces"]:
            face = f["face"]
            fid = face["id"]
            x0, y0, z0, x1, y1, z1 = face["box"]
            gx0, gy0, gz0, gx1, gy1, gz1 = x0 - 1, y0 - 1, z0 - 1, x1 + 1, y1 + 1, z1 + 1
            vol = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (gx0, gy0, gz0, gx1 - gx0, gy1 - gy0, gz1 - gz0)
            fn["faces/check_%s" % fid] = [
                "# restore on approach (STONE_ECONOMY.md 5.3): the period has passed, the box's four corners are loaded, and",
                "# nobody and no Pokemon stands in the box or one block round it (the mandatory guard)",
                "scoreboard players operation #d mn.t = #now mn.t",
                "scoreboard players operation #d mn.t -= #%s mn.last" % fid,
                "execute if score #d mn.t < #period mn.t run return 0",
                "execute unless loaded %d %d %d run return 0" % (gx0, gy0, gz0),
                "execute unless loaded %d %d %d run return 0" % (gx1, gy0, gz0),
                "execute unless loaded %d %d %d run return 0" % (gx0, gy0, gz1),
                "execute unless loaded %d %d %d run return 0" % (gx1, gy0, gz1),
                "execute if entity @a[%s] run return 0" % vol,
                "execute if entity @e[type=cobblemon:pokemon,%s] run return 0" % vol,
                "function %s/faces/restore_%s" % (F, fid)]
            restore = ["# a variant other than the last one: random value 0..7, moved on by one if it repeats",
                       "execute store result score #v mn.t run random value 0..7",
                       "execute if score #v mn.t = #%s mn.var run scoreboard players add #v mn.t 1" % fid,
                       "scoreboard players operation #v mn.t %= #eight mn.t",
                       "scoreboard players operation #%s mn.var = #v mn.t" % fid]
            for k in range(rs["variants"]):
                restore.append("execute if score #v mn.t matches %d run function %s/faces/%s_v%d" % (k, F, fid, k))
            restore.append("scoreboard players operation #%s mn.last = #now mn.t" % fid)
            # the other face of the same stone at this place: due no sooner than its stagger after this restore, so
            # the two stay apart even after an idle spell brought both due together (the gulch's sibling rule)
            for g2 in e["faces"]:
                o = g2["face"]
                if o["id"] == fid or o["stone"] != face["stone"]:
                    continue
                delta = (int(o["offset_ticks"]) - int(face["offset_ticks"])) % period
                restore += ["scoreboard players operation #sib mn.t = #now mn.t",
                            "scoreboard players remove #sib mn.t %d" % (period - delta),
                            "scoreboard players operation #%s mn.last > #sib mn.t" % o["id"]]
            fn["faces/restore_%s" % fid] = restore
            for k, ores in enumerate(f["variants"]):
                body = ["# chunks-loaded-by: %s/faces/check_%s (execute if loaded, the box's four corners)" % (F, fid),
                        "fill %d %d %d %d %d %d %s replace %s" % (x0, y0, z0, x1, y1, z1, face["host"], tag)]
                for (x, y, z) in sorted(ores):
                    body.append("execute if block %d %d %d %s run setblock %d %d %d %s" % (x, y, z, tag, x, y, z, face["ore"]))
                fn["faces/%s_v%d" % (fid, k)] = body
    return fn


def write(spec, plan):
    if OUT.exists():
        shutil.rmtree(OUT)
    base = OUT / "data" / NS
    fdir = base / "function" / FOLDER
    fdir.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: the evolution-stone faces (tools/mines.py, data/mines.json)"}}, indent=2) + "\n",
                                     encoding="utf-8")
    counts = {}
    for e in plan:
        name = "build_%s" % e["site"]["id"]
        body = FL.ensure_loaded(build_lines(spec, e))
        bad = FL.check_lines(body, name)
        if bad:
            raise MineError("function %s would be refused: %s" % (name, bad[:3]))
        (fdir / (name + ".mcfunction")).write_text("\n".join(body) + "\n", encoding="utf-8")
        counts[name] = len(body)
    for name, body in driver_files(spec, plan).items():
        bad = FL.check_lines(body, name)
        if bad:
            raise MineError("function %s would be refused: %s" % (name, bad[:3]))
        p = fdir / (name + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(body) + "\n", encoding="utf-8")
    tags = OUT / "data" / "minecraft" / "tags" / "function"
    tags.mkdir(parents=True)
    (tags / "load.json").write_text(json.dumps({"values": ["%s/load" % F]}, indent=2) + "\n", encoding="utf-8")
    (tags / "tick.json").write_text(json.dumps({"values": ["%s/tick" % F]}, indent=2) + "\n", encoding="utf-8")
    bt = base / "tags" / "block"
    bt.mkdir(parents=True)
    (bt / ("%s.json" % spec["restore"]["resettable_tag"])).write_text(
        json.dumps({"values": spec["restore"]["resettable"]}, indent=2) + "\n", encoding="utf-8")
    return counts


def build_functions(spec=None):
    """The build function names step R9O runs, in order, from the committed data (not from a built pack)."""
    spec = spec or load()
    return ["%s/build_%s" % (F, s["id"]) for s in spec["sites"]]


def pack_problems(spec):
    """Static rules on the data alone (no ground): ids, stones, yields, the tag."""
    out = []
    rs = spec["restore"]
    for need in ("minecraft:air", "minecraft:cave_air"):
        if need not in rs["resettable"]:
            out.append("the resettable tag lacks %s: a dug cell would never be restored" % need)
    stones_used = {}
    for s in spec["sites"]:
        for f in s["faces"]:
            if f["host"] not in rs["resettable"]:
                out.append("%s: host %s is not resettable, so the restore could not refill its own rock" % (f["id"], f["host"]))
            if f["ore"] not in rs["resettable"]:
                out.append("%s: ore %s is not resettable, so an ore left standing would stay through a restore" % (f["id"], f["ore"]))
            y = f["yield"]
            if not (1 <= y["ore_min"] <= y["ore_max"]) or y.get("visible_min", 1) > y["ore_min"]:
                out.append("%s: yield %s" % (f["id"], y))
            stones_used.setdefault(f["stone"], []).append(f["id"])
    for st in spec["stones"]:
        if st not in stones_used:
            out.append("stone %s has no face" % st)
    return out


def author(spec, only=None, source_root=None):
    """Site every face that has no box yet, best first by search(): each later face of a site keeps clear of the ones
    already sited there and is drawn toward the site's first face, so a place's faces stand as bays of one working.
    Writes data/mines.json; a face that cannot be sited stops the run and nothing is written."""
    geo = spec["geometry"]
    for site in spec["sites"]:
        if only and site["id"] != only:
            continue
        todo = [f for f in site["faces"] if not f.get("box")]
        if not todo:
            continue
        ctx = search_context(spec, site, source_root)
        for f in todo:
            done = [g for g in site["faces"] if g.get("box")]
            near = None
            if done:
                xz, W, _D = frame(done[0]["box"], done[0]["front"])
                near = xz(W // 2, -1)
            best = search(spec, site, f["stone"], 1, source_root, done, near, ctx)
            if not best:
                raise SystemExit("%s/%s: no place for the face passes every rule; nothing written" % (site["id"], f["id"]))
            f["box"], f["front"] = best[0][1], best[0][2]
            print("%s/%s: %s front %s (score %s, %d cut rows, %d dug, %d built)"
                  % (site["id"], f["id"], f["box"], f["front"], best[0][0], best[0][3], best[0][4], best[0][5]))
    SPEC.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", SPEC.relative_to(ROOT))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("site", "author", "report", "build"))
    p.add_argument("site", nargs="?")
    p.add_argument("--stone")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--prefer", help="site: x,z,window, a trial of a prefer_near hint")
    p.add_argument("--source-root")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    spec = load()
    if a.mode == "author":
        return author(spec, a.site, a.source_root)
    if a.mode == "site":
        site = next((s for s in spec["sites"] + spec.get("search_only", []) if s["id"] == a.site), None)
        if site is None:
            raise SystemExit("no site %r" % a.site)
        others = [f for f in site.get("faces") or [] if f.get("stone") != a.stone and f.get("box")] if a.stone else []
        if a.prefer:
            px, pz, pw = (int(v) for v in a.prefer.split(","))
            site = dict(site, prefer_near={"at": [px, pz], "window": pw})
        for o in search(spec, site, a.stone, a.top, a.source_root, others):
            print(json.dumps(o))
        return 0
    probs = pack_problems(spec)
    plan, mp = model(spec, a.source_root)
    probs += mp
    for e in plan:
        for f in e["faces"]:
            gm = f["geometry"]
            roles = {}
            for r in gm["cells"].values():
                roles[r] = roles.get(r, 0) + 1
            print("  %-22s %-8s %-5s y%-3d rows %2d  %s  ore/variant %s" % (
                f["face"]["id"], f["face"]["stone"], f["face"]["front"], f["face"]["box"][1], len(gm["rows"]),
                " ".join("%s %d" % kv for kv in sorted(roles.items())), [len(v) for v in f["variants"]]))
    if probs:
        for pr in probs:
            print("PROBLEM:", pr)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    if a.mode == "report":
        return 0
    counts = write(spec, plan)
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    out = {"schema": "cobblers.derived.mines/1", "build_functions": build_functions(spec), "commands": counts,
           "sites": {e["site"]["id"]: {"approach": e["approach"],
                                       "faces": {f["face"]["id"]: {"box": f["face"]["box"], "stand": f["geometry"]["stand"],
                                                                   "cut_rows": len(f["geometry"]["rows"]),
                                                                   "ore_per_variant": [len(v) for v in f["variants"]]}
                                                 for f in e["faces"]}} for e in plan}}
    PLAN.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("wrote %s: %d sites, %d faces; plan %s" % (OUT.relative_to(ROOT), len(plan), sum(len(e["faces"]) for e in plan),
                                                     PLAN.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
