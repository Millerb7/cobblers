#!/usr/bin/env python
"""Bridges: each crossing in data/bridges.json, fitted to the heightmap and the committed water, as one function.

  function   build/datapacks/cobblers_bridges (cobblers:bridges/<id>, and an index.txt) and derived/bridges/<id>.json
  audit      read the function back and check it against the heightmap and the water, offline: the deck is continuous
             bank to bank, each end meets the heightmap ground within one block, the water under the deck has the
             clearance, nothing at or below a water level is written except the piers (and no water anywhere), no
             pier touches two water levels, every lantern stands on a post and no light block is used, and nothing
             comes within the margin of a town's footprint, lot or building

  python tools/bridges.py function --source-root <root>
  python tools/bridges.py audit --source-root <root>

THE GROUND. From tools/ground.py (the canonical heightmap, rounded), never from a world. The water is what
tools/paint_maps.py paints for the export, computed the same way from the same committed data: a lake's basin
polygons at its level (data/landmarks.json water_body), each cut river course at floor(surface + 0.01) within its
reach's half width, nearest station winning (data/rivers.json), and the sea at data/world.json's sea level. Two
masks come of it:

  wet        h < level: every column the paint marks as water (a superset of the export's water)
  definite   round(h) < level: the ground block is below the water level, so the export stands water on it

A column that is wet but not definite (the lake's low shore at y76.5-76.9 under a level of 77) may or may not hold
water in the export: nothing is written there at or below its level, but it needs no clearance.

THE SHAPE, for a bridge along `axis` at `centre`, walkway 2*walkway_half_width+1 wide with a curb and rail each side:
the rows with definite water in any column of the band, one contiguous run through the waypoint, carry a level deck
at clearance_air_blocks of air over the highest water in the band; the first dry row either side is an abutment at
deck height on masonry; from each abutment a ramp falls ramp_fall_per_row a row (a bottom slab on a half, a full
block on a whole) until the next row's ground is at or above it. The authored piers stand in their rows the full width
of the bridge, from one block under the bed to the deck. Lantern posts stand on the curbs at both abutments, the
first row of each pier, between those wherever the gap exceeds max_post_spacing_rows, and at both ramp feet.

The audit derives none of its expectations from the plan: it parses the function's block writes and holds them to the
heightmap, the water and the town data, and to the bridge record's band and piers.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)
PACK = ROOT / "build" / "datapacks" / "cobblers_bridges"
FN_DIR = PACK / "data" / "cobblers" / "function" / "bridges"
REPORT = ROOT / "derived" / "bridges"

# The ground rule (tools/ground_rule.py): nothing here reads a world.
WORLD_READS = set()

AIR = "minecraft:air"
WALKABLE_FULL = ("planks", "stone_bricks", "stone", "bricks")


def load(name="bridges.json"):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ water


def water(heights, world, box, landmarks=None, rivers=None):
    """(level, wet, definite) over the inclusive box (x0, z0, x1, z1), each a (z, x) array: the water level y (0 where
    none), the paint's water (h < level) and the export's certain water (round(h) < level). See the module note."""
    import grade_rivers as G
    from PIL import Image, ImageDraw
    x0, z0, x1, z1 = box
    ox, oz = world["grid"]["origin_x"], world["grid"]["origin_z"]
    h = heights[z0 - oz:z1 - oz + 1, x0 - ox:x1 - ox + 1].astype(np.float64)
    shape = h.shape
    level = np.zeros(shape, int)
    wet = np.zeros(shape, bool)
    sea = int(round(float((world.get("vertical") or {}).get("sea_level", 62))))
    s_wet = h < sea
    level = np.where(s_wet, sea, level)
    wet |= s_wet
    landmarks = landmarks if landmarks is not None else load("landmarks.json")
    for lm in landmarks["landmarks"]:
        wb = lm.get("water_body")
        if not wb:
            continue
        img = Image.new("L", (shape[1], shape[0]), 0)
        d = ImageDraw.Draw(img)
        for ring in wb["basin_polygons"]:
            d.polygon([(x - x0, z - z0) for x, z in ring], fill=1)
        lw = (np.asarray(img).astype(bool)) & (h < wb["level_y"])
        level = np.where(lw, np.maximum(level, int(wb["level_y"])), level)
        wet |= lw
    rivers = rivers if rivers is not None else load("rivers.json")
    cut = set((rivers.get("cut") or {}).get("courses_cut") or [])
    zz, xx = np.mgrid[z0:z1 + 1, x0:x1 + 1]
    for c in rivers["courses"]:
        if c["id"] not in cut:
            continue
        pts, chain = G.densify_chained(c["graded_polyline"])
        best = np.full(shape, np.inf)
        rl = np.zeros(shape, int)
        pad = max(r["width"] for r in c["reaches"]) / 2.0 + 2
        for (x, z, surface, _floor), ch in zip(pts, chain):
            if not (x0 - pad <= x <= x1 + pad and z0 - pad <= z <= z1 + pad):
                continue
            r = G.at_chainage(c["reaches"], ch)
            if r["water_body"]:
                continue
            dist = np.hypot(xx - x, zz - z)
            hit = (dist <= r["width"] / 2.0) & (dist < best)
            best = np.where(hit, dist, best)
            rl = np.where(hit, int(math.floor(surface + 0.01)), rl)
        rw = (rl > 0) & (h < rl)
        level = np.where(rw, np.maximum(level, rl), level)
        wet |= rw
    definite = wet & (np.round(h) < level)
    return level, wet, definite


# ------------------------------------------------------------------ geometry


class Frame:
    """Along/across coordinates for a bridge: u runs along the axis, v across it."""

    def __init__(self, b):
        self.axis = b["axis"]
        if self.axis not in ("x", "z"):
            raise SystemExit("bridge %s: axis must be x or z" % b["id"])
        self.c = int(b["centre"])
        self.hw = int(b["walkway_half_width"])

    def xz(self, u, v):
        return (self.c + v, u) if self.axis == "z" else (u, self.c + v)

    def across(self):
        """Every v of the bridge: the walkway and the curb either side."""
        return list(range(-self.hw - 1, self.hw + 2))

    def walkway(self):
        return list(range(-self.hw, self.hw + 1))

    def uv(self, x, z):
        return (z, x - self.c) if self.axis == "z" else (x, z - self.c)


def surface_block(s):
    """(y, kind) of the block whose top is at s: a bottom slab at floor(s) on a half, a full block at s-1 on a whole."""
    if abs(s * 2 - round(s * 2)) > 1e-9:
        raise ValueError("surface %s is not on a half block" % s)
    if abs(s - round(s)) < 1e-9:
        return int(round(s)) - 1, "full"
    return int(math.floor(s)), "slab"


def plan(b, defaults, ground, level, wet, definite, box):
    """The bridge as {"rows": [...], "blocks": {(x, y, z): state}, "report": {...}}. `level`, `wet`, `definite` are
    (z, x) arrays over `box` (x0, z0, x1, z1); `ground` is tools/ground.Ground."""
    f = Frame(b)
    cfg = dict(defaults)
    cfg.update({k: v for k, v in b.items() if k in defaults})
    mat = b["materials"]
    x0, z0 = box[0], box[1]

    def at(arr, u, v):
        x, z = f.xz(u, v)
        return arr[z - z0, x - x0]

    def g(u, v):
        x, z = f.xz(u, v)
        return ground(x, z)

    # the water rows: a contiguous run through the waypoint of rows with definite water in any column
    wu = f.uv(*b["crossing"]["waypoint"])[0]
    lo, hi = int(b["along_from"]), int(b["along_to"])
    has = {u: any(at(definite, u, v) for v in f.across()) for u in range(lo, hi + 1)}
    start = min((u for u in range(lo, hi + 1) if has[u]), key=lambda u: abs(u - wu), default=None)
    if start is None:
        raise SystemExit("bridge %s: no water in the band between %d and %d" % (b["id"], lo, hi))
    a = start
    while a - 1 >= lo and has[a - 1]:
        a -= 1
    e = start
    while e + 1 <= hi and has[e + 1]:
        e += 1
    if a - 1 <= lo or e + 1 >= hi:
        raise SystemExit("bridge %s: the water runs to the edge of the search (%d-%d): widen along_from/along_to"
                         % (b["id"], lo, hi))
    top_water = max(int(at(level, u, v)) for u in range(a, e + 1) for v in f.across() if at(definite, u, v))
    deck_y = top_water + 1 + int(cfg["clearance_air_blocks"])
    S = deck_y + 1.0                                               # the deck's walking surface

    rows = [{"u": u, "kind": "abutment" if u in (a - 1, e + 1) else "deck", "s": S} for u in range(a - 1, e + 2)]
    fall = float(cfg["ramp_fall_per_row"])
    feet = []
    for sign, from_u in ((-1, a - 1), (1, e + 1)):
        k = 1
        while True:
            u = from_u + sign * k
            s = S - fall * k
            gtop = max(g(u, v) + 1 for v in f.across())
            if s <= gtop:
                break
            if any(at(definite, u, v) for v in f.across()):
                raise SystemExit("bridge %s: the ramp would stand in water at row %d" % (b["id"], u))
            if not (lo <= u <= hi):
                raise SystemExit("bridge %s: the ramp runs past the search at row %d" % (b["id"], u))
            rows.append({"u": u, "kind": "ramp", "s": s})
            k += 1
        feet.append(from_u + sign * (k - 1))
    rows.sort(key=lambda r: r["u"])
    by_u = {r["u"]: r for r in rows}

    pier_rows = set()
    for p in b.get("piers") or []:
        for u in range(int(p["from"]), int(p["to"]) + 1):
            if not (a <= u <= e):
                raise SystemExit("bridge %s: pier row %d is not over the water (%d-%d)" % (b["id"], u, a, e))
            pier_rows.add(u)

    air, solid = {}, {}
    headroom = int(cfg["headroom_blocks"])
    for r in rows:
        u, s = r["u"], r["s"]
        top = int(math.ceil(s))
        for v in f.across():
            x, z = f.xz(u, v)
            for y in range(top, top + headroom):
                air[(x, y, z)] = AIR
    for r in rows:
        u, s = r["u"], r["s"]
        yb, kind = surface_block(s)
        curb_y = int(math.ceil(s)) - 1
        for v in f.across():
            x, z = f.xz(u, v)
            edge = abs(v) == f.hw + 1
            yt = curb_y if edge else yb
            if r["kind"] == "deck":
                block = mat["curb"] if edge else mat["deck"]
            elif r["kind"] == "abutment":
                block = mat["curb"] if edge else mat["deck"]
            else:
                block = mat["curb"] if edge else (mat["ramp_full"] if kind == "full" else mat["ramp_slab"])
            solid[(x, yt, z)] = block
            if r["kind"] in ("abutment", "ramp"):
                for y in range(ground(x, z) + 1, yt):               # masonry on dry ground only
                    solid[(x, y, z)] = mat["support"]
    pier_cells = set()
    for u in sorted(pier_rows):
        for v in f.across():
            x, z = f.xz(u, v)
            lv = int(at(level, u, v))
            for y in range(ground(x, z) - 1, deck_y):
                block = mat["pier_cap"] if y == deck_y - 1 else (mat["pier_wet"] if y <= max(lv, top_water) else mat["pier"])
                solid[(x, y, z)] = block
                pier_cells.add((x, y, z))

    # rails and posts
    posts = {a - 1, e + 1}
    for u in sorted(pier_rows):
        if u - 1 not in pier_rows:
            posts.add(u)
    gap = int(cfg["max_post_spacing_rows"])
    changed = True
    while changed:
        changed = False
        deckposts = sorted(p for p in posts if a - 1 <= p <= e + 1)
        for p, q in zip(deckposts, deckposts[1:]):
            if q - p > gap:
                posts.add((p + q) // 2)
                changed = True
    lanterns = []
    for r in rows:
        u, s = r["u"], r["s"]
        top = int(math.ceil(s))
        for v in (-f.hw - 1, f.hw + 1):
            x, z = f.xz(u, v)
            if r["kind"] == "ramp":
                if u in feet:
                    solid[(x, top, z)] = mat["post_ramp"]
                    solid[(x, top + 1, z)] = mat["post_ramp"]
                    solid[(x, top + 2, z)] = mat["lantern"]
                    lanterns.append((x, top + 2, z))
                else:
                    solid[(x, top, z)] = mat["rail_ramp"]
            elif u in posts:
                solid[(x, top, z)] = mat["post_deck"]
                solid[(x, top + 1, z)] = mat["post_deck"]
                solid[(x, top + 2, z)] = mat["lantern"]
                lanterns.append((x, top + 2, z))
            else:
                solid[(x, top, z)] = mat["rail_deck"]

    blocks = dict(air)
    blocks.update(solid)
    removed = sum(1 for (x, y, z) in pier_cells
                  if definite[z - z0, x - x0] and ground(x, z) < y <= level[z - z0, x - x0])
    ext = [f.xz(r["u"], v) for r in rows for v in f.across()]
    report = {
        "id": b["id"],
        "water_rows": [a, e],
        "water_row_count": e - a + 1,
        "top_water_y": top_water,
        "deck_y": deck_y,
        "deck_surface": S,
        "rows": [feet[0], feet[1]],
        "length_blocks": feet[1] - feet[0] + 1,
        "walkway_blocks": 2 * f.hw + 1,
        "overall_width_blocks": 2 * f.hw + 3,
        "feet": feet,
        "piers": sorted(pier_rows),
        "posts": sorted(posts | set(feet)),
        "lanterns": len(lanterns),
        "water_blocks_replaced_by_piers": removed,
        "extent": [min(p[0] for p in ext), min(p[1] for p in ext), max(p[0] for p in ext), max(p[1] for p in ext)],
        "bank_ground": {"north_or_west": sorted({g(a - 1, v) for v in f.across()}),
                        "south_or_east": sorted({g(e + 1, v) for v in f.across()})},
    }
    return {"rows": rows, "blocks": blocks, "report": report, "air_first": air, "solid": solid}


def commands(p, b):
    """Air first, then the build: vertical runs of one state become one fill, the rest setblocks."""
    out = ["# %s (tools/bridges.py, data/bridges.json): %s" % (b["id"], b.get("working_name", "")),
           "# route %s, rows %s, deck y%d; generated from the canonical heightmap, never from a world"
           % (b["route"], p["report"]["rows"], p["report"]["deck_y"])]
    ext = p["report"]["extent"]
    out.append("forceload add %d %d %d %d" % (ext[0], ext[1], ext[2], ext[3]))
    for part in (p["air_first"], p["solid"]):
        cols = {}
        for (x, y, z), st in part.items():
            cols.setdefault((x, z), []).append((y, st))
        for (x, z) in sorted(cols):
            run = sorted(cols[(x, z)])
            i = 0
            while i < len(run):
                j = i
                while j + 1 < len(run) and run[j + 1][0] == run[j][0] + 1 and run[j + 1][1] == run[i][1]:
                    j += 1
                y0, st = run[i]
                y1 = run[j][0]
                if y1 > y0:
                    out.append("fill %d %d %d %d %d %d %s" % (x, y0, z, x, y1, z, st))
                else:
                    out.append("setblock %d %d %d %s" % (x, y0, z, st))
                i = j + 1
    out.append("forceload remove %d %d %d %d" % (ext[0], ext[1], ext[2], ext[3]))
    return out


# ------------------------------------------------------------------ audit

WRITE = re.compile(r"^(fill|setblock)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+))?\s+(\S+)(?:\s+(\S+))?\s*$")


def parse(lines):
    """{(x, y, z): state} after the function has run (a later write wins). Fill modes other than replace refuse."""
    out = {}
    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("forceload"):
            continue
        m = WRITE.match(line)
        if not m:
            raise ValueError("line %d: not a block write this audit reads: %s" % (n, line[:80]))
        what, a1, a2, a3, b1, b2, b3, state, mode = m.groups()
        if mode not in (None, "replace"):
            raise ValueError("line %d: fill mode %s is not audited" % (n, mode))
        if what == "setblock":
            if b1 is not None:
                raise ValueError("line %d: malformed setblock" % n)
            out[(int(a1), int(a2), int(a3))] = state
            continue
        xs = sorted((int(a1), int(b1)))
        ys = sorted((int(a2), int(b2)))
        zs = sorted((int(a3), int(b3)))
        for x in range(xs[0], xs[1] + 1):
            for y in range(ys[0], ys[1] + 1):
                for z in range(zs[0], zs[1] + 1):
                    out[(x, y, z)] = state
    return out


def _surface(state, y):
    """The walking surface a written block gives, or None when it is not one to walk on."""
    name = state.split("[", 1)[0]
    if name.endswith("_slab"):
        return y + 0.5 if "type=bottom" in state else y + 1.0
    if name.split(":")[-1].endswith(WALKABLE_FULL) or name.endswith("_planks"):
        return y + 1.0
    return None


def town_boxes(towns, placements):
    """[(what, (x0, z0, x1, z1))]: every town footprint, every plan footprint, plaza, anchor, earthwork and street
    corridor, and every placed building's position."""
    out = []
    for t in towns["towns"]:
        fp = t.get("footprint") or {}
        if {"min_x", "min_z", "max_x", "max_z"} <= set(fp):
            out.append(("town %s footprint" % t["id"], (fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"])))
    for sid, s in placements["settlements"].items():
        plan_ = s.get("plan") or {}
        if (plan_.get("footprint") or {}).get("rect"):
            out.append(("%s plan footprint" % sid, tuple(plan_["footprint"]["rect"])))
        if (plan_.get("plaza") or {}).get("rect"):
            out.append(("%s plaza" % sid, tuple(plan_["plaza"]["rect"])))
        for an in plan_.get("anchors") or []:
            if an.get("rect"):
                out.append(("%s %s" % (sid, an.get("id")), tuple(an["rect"])))
        for st in plan_.get("streets") or []:
            pts = st.get("polyline") or []
            if pts:
                w = int(st.get("width", 3))
                xs, zs = [q[0] for q in pts], [q[1] for q in pts]
                out.append(("%s street %s" % (sid, st.get("id")), (min(xs) - w, min(zs) - w, max(xs) + w, max(zs) + w)))
    for q in placements["placements"]:
        pos = q.get("position") or {}
        if "x" in pos and "z" in pos:
            out.append(("placement %s" % q["id"], (pos["x"], pos["z"], pos["x"], pos["z"])))
    return out


def audit_bridge(b, defaults, lines, ground, level, wet, definite, box, towns, placements):
    """[(check, ok, detail)] for one bridge's function lines. Fails closed on an empty function."""
    f = Frame(b)
    cfg = dict(defaults)
    cfg.update({k: v for k, v in b.items() if k in defaults})
    x0, z0, x1, z1 = box
    res = []
    try:
        vox = parse(lines)
    except ValueError as e:
        return [("parse", False, str(e))]
    solid = {k: s for k, s in vox.items() if s != AIR}
    if not solid:
        return [("nonempty", False, "the function writes no block")]
    res.append(("nonempty", True, "%d blocks written, %d of them not air" % (len(vox), len(solid))))

    def inbox(x, z):
        return x0 <= x <= x1 and z0 <= z <= z1

    outside = [k for k in vox if not inbox(k[0], k[2])]
    res.append(("inside the water window", not outside,
                "every write inside %s" % (box,) if not outside else "%d writes outside %s" % (len(outside), box)))
    if outside:
        return res

    # the walkway, row by row: its surface is the top walkable write in each walkway column
    def top_surface(x, z):
        ys = sorted((y for (xx, y, zz) in solid if xx == x and zz == z), reverse=True)
        for y in ys:
            s = _surface(solid[(x, y, z)], y)
            if s is not None:
                return s, y
        return None, None

    by_col = {}
    for (x, y, z) in solid:
        by_col.setdefault((x, z), []).append(y)
    wu = f.uv(*b["crossing"]["waypoint"])[0]
    surf = {}
    lo, hi = int(b["along_from"]), int(b["along_to"])
    for u in range(lo, hi + 1):
        row = []
        for v in f.walkway():
            x, z = f.xz(u, v)
            s, y = top_surface(x, z) if (x, z) in by_col else (None, None)
            if s is not None:
                clear = all(vox.get((x, yy, z)) == AIR for yy in range(y + 1, y + 3))
                row.append(s if clear else None)
            else:
                row.append(None)
        surf[u] = row
    built = [u for u in range(lo, hi + 1) if all(s is not None for s in surf[u])]
    if not built:
        return res + [("deck", False, "no row of the walkway has a surface with headroom")]
    near = min(built, key=lambda u: abs(u - wu))
    a = near
    while a - 1 in built:
        a -= 1
    e = near
    while e + 1 in built:
        e += 1
    steps_bad = []
    for u in range(a, e + 1):
        row = surf[u]
        if max(row) - min(row) > 1e-9:
            steps_bad.append("row %d is not level across the walkway: %s" % (u, row))
        if u < e and abs(surf[u + 1][0] - row[0]) > 0.5 + 1e-9:
            steps_bad.append("rows %d-%d step %.1f" % (u, u + 1, surf[u + 1][0] - row[0]))
    # every row with water in the band lies inside the walked run, with dry rows beyond
    wet_rows = [u for u in range(lo, hi + 1)
                if any(definite[f.xz(u, v)[1] - z0, f.xz(u, v)[0] - x0] for v in f.across())]
    uncovered = [u for u in wet_rows if not (a < u < e)]
    ok = not steps_bad and not uncovered and bool(wet_rows)
    res.append(("deck continuous bank to bank", ok,
                "rows %d-%d walkable, no step over half a block, covering water rows %d-%d (%d rows)"
                % (a, e, wet_rows[0], wet_rows[-1], len(wet_rows)) if ok and wet_rows else
                "; ".join(steps_bad[:4] + (["water rows outside the deck: %s" % uncovered[:8]] if uncovered else [])
                          + ([] if wet_rows else ["no water rows found in the band"]))))

    # each end meets the ground: the first row beyond the walked run
    ends_bad, ends = [], []
    for end, beyond in ((a, a - 1), (e, e + 1)):
        for i, v in enumerate(f.walkway()):
            x, z = f.xz(beyond, v)
            gs = ground(x, z) + 1
            d = surf[end][i] - gs
            ends.append(d)
            if abs(d) > 1.0 + 1e-9:
                ends_bad.append("row %d column %d: end surface %.1f, ground surface %d beyond it" % (end, v, surf[end][i], gs))
    res.append(("ends meet the heightmap ground within one block", not ends_bad,
                "largest step from an end onto the ground: %.1f" % max(abs(d) for d in ends) if not ends_bad
                else "; ".join(ends_bad[:4])))

    # piers: the authored rows, across the bridge
    pier_rows = {u for p in b.get("piers") or [] for u in range(int(p["from"]), int(p["to"]) + 1)}
    pier_cols = {f.xz(u, v) for u in pier_rows for v in f.across()}

    # clearance over definite water, outside the piers
    top_water = 0
    clear_bad, least = [], None
    for (x, z) in {(k[0], k[2]) for k in vox}:
        if (x, z) in pier_cols or not definite[z - z0, x - x0]:
            continue
        lv = int(level[z - z0, x - x0])
        top_water = max(top_water, lv)
        ys = [y for y in by_col.get((x, z), []) if y > lv]
        if not ys:
            continue
        gap_ = min(ys) - lv - 1
        least = gap_ if least is None else min(least, gap_)
        if gap_ < int(cfg["clearance_air_blocks"]):
            clear_bad.append("(%d, %d): %d air over water at %d" % (x, z, gap_, lv))
    res.append(("clearance over the water", not clear_bad and least is not None,
                "least air over water under the bridge: %s blocks (need %d)" % (least, int(cfg["clearance_air_blocks"]))
                if not clear_bad else "; ".join(clear_bad[:4])))

    # water: nothing written at or below a wet column's level except in the piers; no water written anywhere
    water_bad, removed = [], 0
    for (x, y, z), st in vox.items():
        if "water" in st or "light" == st.split(":")[-1].split("[")[0]:
            water_bad.append("%s at %s" % (st, (x, y, z)))
            continue
        if wet[z - z0, x - x0] and y <= level[z - z0, x - x0]:
            if (x, z) not in pier_cols:
                water_bad.append("%s at %s, at or below the water level %d" % (st, (x, y, z), level[z - z0, x - x0]))
            elif definite[z - z0, x - x0] and y > ground(x, z):
                removed += 1
    res.append(("water untouched but for the piers", not water_bad,
                "%d water blocks replaced, all by the piers in rows %s" % (removed, sorted(pier_rows)) if not water_bad
                else "; ".join(water_bad[:4])))

    # a pier touches one water level (a step beside it would pour when its blocks update)
    step_bad = []
    for (x, z) in pier_cols:
        levels = set()
        for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, zz = x + dx, z + dz
            if inbox(xx, zz) and definite[zz - z0, xx - x0]:
                levels.add(int(level[zz - z0, xx - x0]))
        if len(levels) > 1:
            step_bad.append("(%d, %d) touches levels %s" % (x, z, sorted(levels)))
    if step_bad:
        res.append(("each pier in one water level", False, "; ".join(step_bad[:4])))
    else:
        res.append(("each pier in one water level", True, "piers in rows %s, each in one level" % sorted(pier_rows)))

    # lanterns on posts, no light blocks
    lan = [k for k, s in solid.items() if s.split("[")[0] == "minecraft:lantern"]
    lan_bad = [k for k in lan if not any(t in solid.get((k[0], k[1] - 1, k[2]), "") for t in ("_log", "_wall", "_fence"))]
    res.append(("lanterns on posts", bool(lan) and not lan_bad,
                "%d lanterns, each on a post" % len(lan) if lan and not lan_bad else
                "no lantern" if not lan else "lanterns off a post at %s" % lan_bad[:4]))

    # towns
    margin = int(cfg["town_margin_blocks"])
    xs = [k[0] for k in vox]
    zs = [k[2] for k in vox]
    ext = (min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin)
    hits = [w for w, (a0, b0, a1, b1) in town_boxes(towns, placements)
            if not (a1 < ext[0] or a0 > ext[2] or b1 < ext[1] or b0 > ext[3])]
    res.append(("clear of every town lot", not hits,
                "nothing within %d blocks of the bridge's extent %s" % (margin, (min(xs), min(zs), max(xs), max(zs)))
                if not hits else "touches %s" % hits[:4]))
    return res


def window(b):
    f = Frame(b)
    m = 8
    lo, hi = int(b["along_from"]), int(b["along_to"])
    xa, za = f.xz(lo, -f.hw - 1 - m)
    xb, zb = f.xz(hi, f.hw + 1 + m)
    return (min(xa, xb), min(za, zb), max(xa, xb), max(za, zb))


# ------------------------------------------------------------------ commands


def function(a):
    import ground as GR
    import function_limits
    doc = load()
    g = GR.Ground(a.source_root)
    FN_DIR.mkdir(parents=True, exist_ok=True)
    for old in FN_DIR.glob("*.mcfunction"):
        old.unlink()
    REPORT.mkdir(parents=True, exist_ok=True)
    names = []
    for b in doc["bridges"]:
        box = window(b)
        level, wet, definite = water(g.heights, g.world, box)
        p = plan(b, doc["defaults"], g, level, wet, definite, box)
        cmds = commands(p, b)
        refused = function_limits.check_lines(cmds, "bridges/%s" % b["id"])
        if refused:
            raise SystemExit("bridge %s: the server would refuse: %s" % (b["id"], refused[:2]))
        (FN_DIR / ("%s.mcfunction" % b["id"])).write_text("\n".join(cmds) + "\n", encoding="utf-8", newline="\n")
        (REPORT / ("%s.json" % b["id"])).write_text(json.dumps(p["report"], indent=1) + "\n", encoding="utf-8")
        names.append(b["id"])
        r = p["report"]
        print("%s: rows %d-%d (%d long), water rows %d-%d, deck y%d over water at y%d, %d lanterns, %d water blocks "
              "replaced by piers" % (b["id"], r["rows"][0], r["rows"][1], r["length_blocks"], r["water_rows"][0],
                                     r["water_rows"][1], r["deck_y"], r["top_water_y"], r["lanterns"],
                                     r["water_blocks_replaced_by_piers"]))
    (FN_DIR / "index.txt").write_text("\n".join(names) + "\n", encoding="utf-8", newline="\n")
    (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                                           "Cobblers: bridges (tools/bridges.py, data/bridges.json)"}})
                                      + "\n", encoding="utf-8")
    print("wrote %d bridge function(s): %s" % (len(names), FN_DIR))
    return 0


def audit(a):
    import ground as GR
    doc = load()
    g = GR.Ground(a.source_root)
    towns, placements = load("towns.json"), load("placements.json")
    failed = 0
    if not doc["bridges"]:
        print("no bridges in data/bridges.json")
        return 1
    for b in doc["bridges"]:
        path = FN_DIR / ("%s.mcfunction" % b["id"])
        if not path.is_file():
            print("%s: NO FUNCTION at %s (run `tools/bridges.py function` first)" % (b["id"], path))
            failed += 1
            continue
        box = window(b)
        level, wet, definite = water(g.heights, g.world, box)
        res = audit_bridge(b, doc["defaults"], path.read_text(encoding="utf-8").splitlines(), g, level, wet, definite,
                           box, towns, placements)
        bad = [r for r in res if not r[1]]
        failed += bool(bad)
        print("%s: %s" % (b["id"], "CLEAN" if not bad else "%d PROBLEM(S)" % len(bad)))
        for name, ok, detail in res:
            print("  %-4s %-48s %s" % ("ok" if ok else "FAIL", name, detail))
    return 1 if failed else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("function", "audit"):
        q = sub.add_parser(name)
        q.add_argument("--source-root", default=env_source_root())
    a = p.parse_args(argv)
    return {"function": function, "audit": audit}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
