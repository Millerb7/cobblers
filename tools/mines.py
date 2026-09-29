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

def frame(anchor, front):
    """xz(u, d) for a face's anchor (the middle column of its face line) and the side a player works it from.

    u runs along the face (0 at the anchor), d into the rock (0 is the face line); d < 0 is in front of the face, row
    r being d = -r. North: the player stands north and the rock runs +z; south: -z; west: +x; east: -x. u runs +x on a
    north or south face and +z on a west or east face."""
    ax, az = anchor
    if front == "north":
        return lambda u, d: (ax + u, az + d)
    if front == "south":
        return lambda u, d: (ax + u, az - d)
    if front == "west":
        return lambda u, d: (ax + d, az + u)
    if front == "east":
        return lambda u, d: (ax - d, az + u)
    raise MineError("front %r is not one of %s" % (front, ", ".join(FRONTS)))


def half_width(face, seed, geo):
    """Half the face's width: the width is width_min .. width_max by h32(seed, face), rounded down to odd."""
    w = geo["width_min"] + h32(seed, sid(face["id"]), 1) % (geo["width_max"] - geo["width_min"] + 1)
    return w // 2


def setback(face, seed, u):
    """0 or 1: how far column u of the face line stands back into the rock (the line is broken, not ruled)."""
    return h32(seed, sid(face["id"]), 2, u) % 3 == 0


def jitter(face, seed, u, d):
    """-1, 0 or +1 on the formation's top at (u, d)."""
    return h32(seed, sid(face["id"]), 3, u, d) % 3 - 1


# ------------------------------------------------------------------ one face's geometry

def floor_y(face, ground, geo):
    """The floor: the natural ground in front of the face, the lower median of the first apron row (never lowered
    further: a player walks onto a face, never down into one)."""
    xz = frame(face["anchor"], face["front"])
    hw = geo["width_max"] // 2 + geo["apron_margin"]
    gs = sorted(ground(*xz(u, -1)) for u in range(-hw, hw + 1))
    return gs[(len(gs) - 1) // 2]


def geometry(face, ground, geo, seed, bedrock=False):
    """Everything a face writes, from its anchor, its front and the ground: a dict of cell -> role.

    The formation (data/mines.json geometry.rules). F is the floor (floor_y). The body is `body_depth` deep behind a
    face line that stands back 0 or 1 per column (setback), `height` rows high (F+2 .. F+height+1) over a bottom course
    of the contrasting rock at F+1. The formation's top over the body is T0 = F+height+2 (one row of cover) plus 0 or 1
    of jitter; round the body it falls `fall` per block of distance, out to `knoll_side` beside and `knoll_back` behind,
    plus -1..+1 of jitter. A column is built up (rock, then its cap) only where the natural ground is under that top: on
    a slope the face is a cut and nothing is built; on flat ground the formation is an outcrop. In front, `apron_rows`
    rows (and the set-back cells) are made level with F, dug or filled, with air `clear_above` over the higher of the
    ground and F. Every natural cell the air exposes becomes formation rock (the skin).

    Roles: body, bottom, rock, cap, floor, fill, air, bedrock. Every broken rule is a problem in the result."""
    xz = frame(face["anchor"], face["front"])
    H, BD = geo["height"], geo["body_depth"]
    A, M = geo["apron_rows"], geo["apron_margin"]
    KS, KB, fall = geo["knoll_side"], geo["knoll_back"], geo["fall"]
    hw = half_width(face, seed, geo)
    F = floor_y(face, ground, geo)
    T0 = F + H + 2
    cells, problems = {}, []
    sb = {u: (1 if abs(u) < hw and setback(face, seed, u) else 0) for u in range(-hw, hw + 1)}
    body = {(u, d) for u in sb for d in range(sb[u], sb[u] + BD)}
    front_cells = {(u, d) for u in sb for d in range(0, sb[u])}      # the set-back: part of the cut
    for u in range(-hw - KS, hw + KS + 1):
        for d in range(0, BD + 1 + KB):
            if (u, d) in front_cells:
                continue
            x, z = xz(u, d)
            g = ground(x, z)
            if (u, d) in body:
                top = T0 + (jitter(face, seed, u, d) > 0)
                cells[(x, F + 1, z)] = "bottom"
                for y in range(F + 2, F + H + 2):
                    cells[(x, y, z)] = "body"
                for y in range(g + 1, F + 1):
                    cells[(x, y, z)] = "rock"                    # the formation's foot, where the ground dips under F
            else:
                out = max(0, abs(u) - hw) + max(0, d - (BD - 1))
                top = T0 + jitter(face, seed, u, d) - int(out * fall + 0.5)
            if top > g:
                if top - g > geo["max_build"]:
                    problems.append("formation column (%d, %d): built up %d, over %d" % (x, z, top - g, geo["max_build"]))
                for y in range(max(g + 1, F + H + 2 if (u, d) in body else g + 1), top):
                    cells[(x, y, z)] = "rock"
                cells[(x, top, z)] = "cap"
    # the apron and the set-back: level with F, air over it
    for u in range(-hw - M, hw + M + 1):
        for d in list(range(-A, 0)) + [dd for (uu, dd) in front_cells if uu == u]:
            x, z = xz(u, d)
            g = ground(x, z)
            if g - F > geo["max_cut"] and not bedrock:
                problems.append("apron column (%d, %d): dug %d, over %d" % (x, z, g - F, geo["max_cut"]))
            if F - g > geo["max_fill"]:
                problems.append("apron column (%d, %d): built up %d, over %d" % (x, z, F - g, geo["max_fill"]))
            for y in range(g + 1, F):
                cells[(x, y, z)] = "fill"
            if g != F:
                cells[(x, F, z)] = "floor"
            # in a cavern's wall (a bedrock site) the cut is a bay under a rock ceiling at the formation's height, not an
            # open slot to the mountain's surface
            air_top = min(max(g, F) + geo["clear_above"], T0 + 1) if bedrock else max(g, F) + geo["clear_above"]
            for y in range(F + 1, air_top + 1):
                cells[(x, y, z)] = "air"
    # the skin: every natural cell next to the cut's air, at or under its column's ground
    skin = {}
    for (x, y, z), role in cells.items():
        if role != "air":
            continue
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0), (0, 1, 0)):
            c = (x + dx, y + dy, z + dz)
            if c not in cells and c not in skin and c[1] <= ground(c[0], c[2]):
                skin[c] = "rock"
    cells.update(skin)
    if bedrock:
        # one shell round the body and its bottom course, beside, behind and below, never in front, never at or over
        # the ground: the seam ends near an authored void (STONE_ECONOMY.md 6.4)
        for (u, d) in body:
            for n in ((u + 1, d), (u - 1, d), (u, d + 1)):
                if n in body or n in front_cells or n[1] < 0:
                    continue
                x, z = xz(*n)
                for y in range(F, F + H + 3):
                    if (x, y, z) not in cells and y < ground(x, z):
                        cells[(x, y, z)] = "bedrock"
            x, z = xz(u, d)
            if (x, F, z) not in cells and F < ground(x, z):
                cells[(x, F, z)] = "bedrock"
    for (u, d) in body:
        x, z = xz(u, d)
        if cells.get((x, F + H + 2, z)) not in ("rock", "cap") and ground(x, z) < F + H + 2:
            problems.append("body column (%d, %d): no cover over the body" % (x, z))
    stand = xz(0, -2)
    xs, ys, zs = zip(*cells)
    return {"cells": cells, "problems": problems, "floor": F, "stand": [stand[0], F + 1, stand[1]],
            "bounds": [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)],
            "body": sorted((xz(u, d)[0], xz(u, d)[1], d - sb[u], u) for (u, d) in body),
            "columns": sorted({(x, z) for x, _y, z in cells}),
            "built": sum(1 for (x, y, z), r in cells.items() if r in ("rock", "cap", "body", "bottom") and y > ground(x, z)),
            "dug": sum(1 for (x, y, z), r in cells.items() if r == "air" and y <= ground(x, z))}


def ore_cells(face, k, seed, geo, yld, gm):
    """[(x, y, z)] of variant k's ore: `visible_min` on the face line at eye height (rows F+2 and F+3, the visible tell,
    STONE_ECONOMY.md 5.2) away from the ends, the rest at least 1 deep and under the body's top row. How many:
    ore_min + h32(seed, face, k) mod (ore_max - ore_min + 1); which cells: ordered by h32(seed, face, k, x, y, z)."""
    fid = sid(face["id"])
    F, H = gm["floor"], geo["height"]
    hw = half_width(face, seed, geo)
    n = yld["ore_min"] + h32(seed, fid, k) % (yld["ore_max"] - yld["ore_min"] + 1)
    cells = [(x, y, z, dd, u) for x, z, dd, u in gm["body"] for y in range(F + 2, F + H + 2)]
    order = sorted(cells, key=lambda c: h32(seed, fid, k, c[0], c[1], c[2]))
    visible = [c for c in order if c[3] == 0 and c[1] in (F + 2, F + 3) and abs(c[4]) <= hw - 1]
    hidden = [c for c in order if c[3] >= 1 and c[1] < F + H + 1]
    vis = visible[:yld.get("visible_min", 1)]
    picked = vis + hidden[:n - len(vis)]
    return [(x, y, z) for x, y, z, _d, _u in picked]


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
            # the siting ring round the town's centre (found, not walked past: the owner, 2026-09-28), not the town's
            # own reach
            t = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}[s]
            r = site["ring"][1] + 16
            self.box = (t["centre"]["x"] - r, t["centre"]["z"] - r, t["centre"]["x"] + r, t["centre"]["z"] + r)
        # clearance from every street, the plaza and every routed leg: `road_clear` blocks (Chebyshev)
        x0, z0, x1, z1 = self.box
        rc = site.get("road_clear", keep["road_clear"])
        tp = TD.town_plan(s)
        roads = set()
        for st in (tp.get("streets") or {}).values():
            for zz, _y, xa, xb in st.get("cells") or []:
                roads |= {(xx, zz) for xx in range(xa, xb + 1)}
        if tp.get("plaza"):
            roads |= TD.rect_cells(tp["plaza"]["rect"])
        roads |= TD.leg_cells((x0 - rc, z0 - rc, x1 + rc, z1 + rc))
        near = np.zeros((z1 - z0 + 1 + 2 * rc, x1 - x0 + 1 + 2 * rc), bool)
        for xx, zz in roads:
            if x0 - rc <= xx <= x1 + rc and z0 - rc <= zz <= z1 + rc:
                near[zz - z0 + rc, xx - x0 + rc] = True
        self.roads = _dilate2(near, rc)[rc:-rc, rc:-rc]
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
        self.road_clear = rc

    def blocked(self, x, z):
        if not (self.box[0] <= x <= self.box[2] and self.box[1] <= z <= self.box[3]):
            return "outside the site's reach"
        if (x, z) in self.why:
            return self.why[(x, z)]
        w = self.mask.why.get((x, z))
        if w:
            return w
        if self.roads[z - self.box[1], x - self.box[0]]:
            return "within %d of a street, the plaza or a routed leg" % self.road_clear
        if not self.cavern:
            w = self.mask.wet(x, z) if self.mask.wet is not None else None
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


def town_centre(site, occ):
    if site.get("ground") == "cavern_floor":
        x0, z0, x1, z1 = occ.box
        return ((x0 + x1) / 2, (z0 + z1) / 2)
    t = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}[site["settlement"]]
    return (t["centre"]["x"], t["centre"]["z"])


def face_problems(spec, site, face, ground, occ, taken=()):
    geo = spec["geometry"]
    gm = geometry(face, ground, geo, spec["seed"], site.get("bedrock_skin", False))
    probs = list(gm["problems"])
    if site.get("ring"):
        cx, cz = town_centre(site, occ)
        r = math.hypot(face["anchor"][0] - cx, face["anchor"][1] - cz)
        if not site["ring"][0] <= r <= site["ring"][1]:
            probs.append("the anchor is %.0f from the town's centre, outside the ring %s" % (r, site["ring"]))
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
        self.arr = np.asarray(g.box(x0, z0, x1, z1)).astype(int)
        self.a = self.arr.tolist()

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


def footprint(front, cx, cz, geo):
    """The rectangle (xa, za, xb, zb) every write of a face anchored at (cx, cz) stays inside, at the widest width."""
    xz = frame((cx, cz), front)
    hw = geo["width_max"] // 2 + max(geo["knoll_side"], geo["apron_margin"]) + 1
    (xa, za), (xb, zb) = xz(-hw, -geo["apron_rows"] - 1), xz(hw, geo["body_depth"] + geo["knoll_back"] + 2)
    return min(xa, xb), min(za, zb), max(xa, xb), max(za, zb)


def search(spec, site, top=8, source_root=None, taken_faces=(), near=None, ctx=None):
    """Candidate faces for a site, best first: [(score, anchor, front, built, dug)]. Anchors on a grid inside the
    site's ring whose whole footprint is free; ranked first by an estimate of the rock the formation would build
    (natural rise needs less), then checked in full by face_problems until `top` pass. The score is the rock built plus
    half the ground dug, plus three per block from `near` (a place's later faces stand as bays of one working), plus
    `siting.centre_pull` per block from the town's centre (flight finding 2, the owner 2026-09-28: a face must read as
    that town's, so of two legal sites the nearer to the town wins even when it costs more rock to build)."""
    geo = spec["geometry"]
    pull = float((spec.get("siting") or {}).get("centre_pull", 0) or 0)
    ctx = ctx or search_context(spec, site, source_root)
    ground, occ, free = ctx["ground"], ctx["occ"], ctx["free"].copy()
    x0, z0, x1, z1 = occ.box
    bedrock = site.get("bedrock_skin", False)
    taken = set()
    for f in taken_faces:
        taken |= set(tuple(c) for c in geometry(f, ground, geo, spec["seed"], bedrock)["columns"])
    gap = spec["keep_clear"]["face_gap"]
    for c in taken:
        for dx in range(-gap, gap + 1):
            for dz in range(-gap, gap + 1):
                if x0 <= c[0] + dx <= x1 and z0 <= c[1] + dz <= z1:
                    free[c[1] + dz - z0, c[0] + dx - x0] = False
    sat = np.zeros((free.shape[0] + 1, free.shape[1] + 1), np.int32)
    sat[1:, 1:] = np.cumsum(np.cumsum(~free, 0), 1)

    def clear(xa, za, xb, zb):
        if xa < x0 or za < z0 or xb > x1 or zb > z1:
            return False
        i0, j0, i1, j1 = za - z0, xa - x0, zb - z0 + 1, xb - x0 + 1
        return sat[i1, j1] - sat[i0, j1] - sat[i1, j0] + sat[i0, j0] == 0
    centre = town_centre(site, occ)
    ring = site.get("ring")
    step = site.get("search_step", 3)
    garr, gx0, gz0 = ground.arr, ground.x0, ground.z0
    H, BD, hwm = geo["height"], geo["body_depth"], geo["width_max"] // 2
    cands = []
    for front in FRONTS:
        for cz in range(z0, z1 + 1, step):
            for cx in range(x0, x1 + 1, step):
                if ring and not ring[0] <= math.hypot(cx - centre[0], cz - centre[1]) <= ring[1]:
                    continue
                if near is not None and max(abs(cx - near[0]), abs(cz - near[1])) > NEAR_WINDOW:
                    continue
                if not clear(*footprint(front, cx, cz, geo)):
                    continue
                xz = frame((cx, cz), front)
                (ax, az), (bx, bz) = xz(-hwm, -1), xz(hwm, -1)
                ap = garr[min(az, bz) - gz0:max(az, bz) + 1 - gz0, min(ax, bx) - gx0:max(ax, bx) + 1 - gx0]
                F = int(np.sort(ap, axis=None)[(ap.size - 1) // 2])
                (ax, az), (bx, bz) = xz(-hwm, 0), xz(hwm, BD - 1)
                bd = garr[min(az, bz) - gz0:max(az, bz) + 1 - gz0, min(ax, bx) - gx0:max(ax, bx) + 1 - gx0]
                est = int(np.clip(F + H + 2 - bd, 0, None).sum())
                if near is not None:
                    est += 3 * math.hypot(cx - near[0], cz - near[1])
                if pull:
                    est += pull * math.hypot(cx - centre[0], cz - centre[1])
                cands.append((est, (cx, cz), front))
    cands.sort(key=lambda c: c[0])
    out = []
    for est, anchor, front in cands[:1500]:
        face = {"id": "probe", "anchor": list(anchor), "front": front}
        probs, gm = face_problems(spec, site, face, ground, occ, taken)
        if probs:
            continue
        score = gm["built"] + 0.5 * gm["dug"]
        if near is not None:
            score += 3 * math.hypot(anchor[0] - near[0], anchor[1] - near[1])
        if pull:
            score += pull * math.hypot(anchor[0] - centre[0], anchor[1] - centre[1])
        out.append((round(score, 1), list(anchor), front, gm["built"], gm["dug"]))
        if top and len(out) >= top * 4:
            break
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
            if not face.get("anchor"):
                probs.append("face %s: no anchor (python tools/mines.py author)" % face["id"])
                continue
            p, gm = face_problems(spec, site, face, ground, occ, taken)
            probs += ["%s/%s: %s" % (site["id"], face["id"], x) for x in p]
            taken |= set(gm["columns"])
            yld = face["yield"]
            variants = [ore_cells(face, k, spec["seed"], geo, yld, gm) for k in range(spec["restore"]["variants"])]
            faces.append({"face": face, "geometry": gm, "variants": variants})
        if not faces:
            probs.append("%s: no face" % site["id"])
            continue
        bs = [f["geometry"]["bounds"] for f in faces]
        m, up, down = spec["restore"]["approach_margin"], spec["restore"]["approach_up"], spec["restore"]["approach_down"]
        approach = [min(b[0] for b in bs) - m, min(b[1] for b in bs) - down, min(b[2] for b in bs) - m,
                    max(b[3] for b in bs) + m, max(b[4] for b in bs) + up, max(b[5] for b in bs) + m]
        plan.append({"site": site, "faces": faces, "approach": approach})
    return plan, probs


# ------------------------------------------------------------------ the pack

def column_runs(cells, replace=None):
    """fill/setblock lines for {cell: block}, in vertical runs of one block per column; with `replace`, filtered fills
    (`fill ... replace <tag>`) even for one cell, so a player's own block in the way survives."""
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
            if replace:
                out.append("fill %d %d %d %d %d %d %s replace %s" % (x, y0, z, x, y1, z, b, replace))
            elif y1 > y0:
                out.append("fill %d %d %d %d %d %d %s" % (x, y0, z, x, y1, z, b))
            else:
                out.append("setblock %d %d %d %s" % (x, y0, z, b))
            n = k + 1
    return out


ROCK_ROLES = ("body", "bottom", "rock", "cap")


def role_block(site, face, role):
    if role in ("body", "rock", "fill"):
        return face["host"]
    if role == "bottom":
        return face["bottom"]
    if role == "cap":
        return face.get("cap") or site.get("cap") or face["host"]
    if role == "floor":
        return face.get("floor") or site["floor_block"]
    if role == "bedrock":
        return "minecraft:bedrock"
    return AIR


def formation(site, face, gm):
    """{cell: block} of the face's formation rock (what the restore puts back): body, bottom course, rock, cap."""
    return {c: role_block(site, face, r) for c, r in gm["cells"].items() if r in ROCK_ROLES}


def build_lines(spec, entry):
    """The site's build function body: every face's air, then its rock, floor and fill, the ore at variant 0,
    then lanterns."""
    site = entry["site"]
    geo = spec["geometry"]
    solid, air = {}, {}
    lanterns = []
    for f in entry["faces"]:
        face, gm = f["face"], f["geometry"]
        for c, role in gm["cells"].items():
            if role == "air":
                air[c] = AIR
            else:
                solid[c] = role_block(site, face, role)
        for c in f["variants"][0]:
            solid[c] = face["ore"]
        if site.get("lanterns"):
            xz = frame(face["anchor"], face["front"])
            hw = half_width(face, spec["seed"], geo)
            for u in (-hw - 1, hw + 1):
                x, z = xz(u, -geo["apron_rows"])
                lanterns.append("setblock %d %d %d %s" % (x, gm["floor"] + 1, z, LANTERN))
    head = ["# Generated by tools/mines.py from data/mines.json: the stone faces of %s (%s)" % (site["settlement"], site["id"]),
            "# the cut's air first, then the formation (body, bottom course, rock, cap), the apron's floor and fill, the",
            "# faces at variant 0, lanterns"]
    return head + column_runs(air) + column_runs(solid) + lanterns


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
            gx0, gy0, gz0, gx1, gy1, gz1 = f["geometry"]["bounds"]
            gx0, gy0, gz0, gx1, gy1, gz1 = gx0 - 1, gy0 - 1, gz0 - 1, gx1 + 1, gy1 + 1, gz1 + 1
            vol = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (gx0, gy0, gz0, gx1 - gx0, gy1 - gy0, gz1 - gz0)
            fn["faces/check_%s" % fid] = [
                "# restore on approach (STONE_ECONOMY.md 5.3): the period has passed, the formation's four corners are",
                "# loaded, and nobody and no Pokemon stands in it or one block round it (the mandatory guard)",
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
            restore = ["# the whole formation back first (its rock, the bottom course and the cap, over the resettable tag",
                       "# only: a player's chest survives), then a variant other than the last one: random value 0..7,",
                       "# moved on by one if it repeats",
                       "function %s/faces/%s_rock" % (F, fid),
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
            fn["faces/%s_rock" % fid] = ["# chunks-loaded-by: %s/faces/check_%s (execute if loaded, the formation's four corners)"
                                         % (F, fid)] + column_runs(formation(site, face, f["geometry"]), tag)
            for k, ores in enumerate(f["variants"]):
                body = ["# chunks-loaded-by: %s/faces/check_%s (execute if loaded, the formation's four corners)" % (F, fid)]
                for (x, y, z) in sorted(ores):
                    body.append("execute if block %d %d %d %s run setblock %d %d %d %s" % (x, y, z, face["host"], x, y, z, face["ore"]))
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
            for key in ("bottom", "cap"):
                b = f.get(key) or (s.get(key) if key == "cap" else None)
                if key == "bottom" and not b:
                    out.append("%s: no bottom block (the course that shows where the ore ends)" % f["id"])
                elif b and b not in rs["resettable"]:
                    out.append("%s: %s %s is not resettable, so the restore could not put it back" % (f["id"], key, b))
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
    """Site every face that has no anchor yet, best first by search(): each later face of a site keeps clear of the
    ones already sited there and is drawn toward the site's first face, so a place's faces stand as bays of one
    working. Writes data/mines.json; a face that cannot be sited stops the run and nothing is written."""
    for site in spec["sites"]:
        if only and site["id"] != only:
            continue
        todo = [f for f in site["faces"] if not f.get("anchor")]
        if not todo:
            continue
        ctx = search_context(spec, site, source_root)
        for f in todo:
            done = [g for g in site["faces"] if g.get("anchor")]
            near = tuple(done[0]["anchor"]) if done else None
            best = search(spec, site, 1, source_root, done, near, ctx)
            if not best:
                raise SystemExit("%s/%s: no place for the face passes every rule; nothing written" % (site["id"], f["id"]))
            f["anchor"], f["front"] = best[0][1], best[0][2]
            print("%s/%s: anchor %s front %s (score %s, %d built, %d dug)"
                  % (site["id"], f["id"], f["anchor"], f["front"], best[0][0], best[0][3], best[0][4]))
    SPEC.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", SPEC.relative_to(ROOT))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("site", "author", "report", "build"))
    p.add_argument("site", nargs="?")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--source-root")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    spec = load()
    if a.mode == "author":
        return author(spec, a.site, a.source_root)
    if a.mode == "site":
        site = next((s for s in spec["sites"] if s["id"] == a.site), None)
        if site is None:
            raise SystemExit("no site %r" % a.site)
        for o in search(spec, site, a.top, a.source_root):
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
            b = gm["bounds"]
            print("  %-14s %-8s %-5s floor y%-3d built %4d dug %4d  %dx%dx%d  %s  ore/variant %s" % (
                f["face"]["id"], f["face"]["stone"], f["face"]["front"], gm["floor"], gm["built"], gm["dug"],
                b[3] - b[0] + 1, b[4] - b[1] + 1, b[5] - b[2] + 1,
                " ".join("%s %d" % kv for kv in sorted(roles.items())), [len(v) for v in f["variants"]]))
    if probs:
        for pr in probs:
            print("PROBLEM:", pr)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    if a.mode == "report":
        return 0
    counts = write(spec, plan)
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    out = {"schema": "cobblers.derived.mines/2", "build_functions": build_functions(spec), "commands": counts,
           "sites": {e["site"]["id"]: {"approach": e["approach"],
                                       "faces": {f["face"]["id"]: {"anchor": f["face"]["anchor"], "front": f["face"]["front"],
                                                                   "floor": f["geometry"]["floor"],
                                                                   "bounds": f["geometry"]["bounds"],
                                                                   "stand": f["geometry"]["stand"],
                                                                   "built": f["geometry"]["built"],
                                                                   "ore_per_variant": [len(v) for v in f["variants"]]}
                                                 for f in e["faces"]}} for e in plan}}
    PLAN.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("wrote %s: %d sites, %d faces; plan %s" % (OUT.relative_to(ROOT), len(plan), sum(len(e["faces"]) for e in plan),
                                                     PLAN.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
