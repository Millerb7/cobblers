#!/usr/bin/env python
"""The ground, water and authored-place rasters tools/mine_networks.py sites and grows its drifts on.

Everything here comes from the canonical heightmap (tools/ground.py, rounded) and from committed data; no world is
read (CLAUDE.md "Ground comes from the heightmap, never from a world"). A raster is a numpy bool/int array indexed
[z - z0, x - x0] over a box.

WHAT THIS DOES NOT COVER (CLAUDE.md "Our list is not the world"). The water it knows is the sea (ground at or under
`sea_near`), the lakes' basin polygons in data/landmarks.json, the river courses of data/rivers.json (the whole
water-shape corridor round each graded centreline, not just the water) and the waterways of data/waterways.json. It
does NOT know a pond or marsh no landmark carries a basin for, water a mod or the world generator placed, the
hidden water and lava pockets in the rock (the build's 2-thick shell exists for those), or derived/routes critical legs
and build/paint, which are generated and absent from a fresh checkout. The authored places it keeps clear of are every
x/z, box and short polyline any data/*.json file carries (regions.json, cells.json, world.json excluded): a place that
exists only in a world, in a mod's generated structures, or in a generated pack and nowhere in data/ is not in it.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# mine_crew_trainers.json (2026-10-22, tools/mine_crews.py) holds seats INSIDE the networks, generated from their own
# geometry; scanned as an authored place it would make each network keep 32 blocks from its own crew and regrow differently
# once the file existed (found the first time it was written: the main-line cells vanished)
# entrance_trails.json, fishing_fill.json and underground_spawns.json (2026-10-22) are not places to keep clear:
# the trails END at the mouths by design, the fill is water cells, the pools are the caves' own boxes
SKIP_FILES = {"mine_networks.json", "mine_crew_trainers.json", "world.json", "regions.json", "cells.json", "entrance_trails.json", "fishing_fill.json", "underground_spawns.json"}
NEST_PREFIX = "mine_nest_"


# ------------------------------------------------------------------ rasters

def _boxsum(a, r, axis):
    n = a.shape[axis]
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad), axis=axis, dtype=np.int32)
    hi = [slice(None), slice(None)]
    lo = [slice(None), slice(None)]
    hi[axis] = slice(2 * r + 1, 2 * r + 1 + n)
    lo[axis] = slice(0, n)
    return c[tuple(hi)] - c[tuple(lo)]


def dilate_sq(mask, r):
    """Chebyshev dilation of a bool raster by r: every cell within r blocks along both axes of a set cell."""
    if r <= 0:
        return mask.copy()
    return _boxsum(_boxsum(mask.astype(np.int32), r, 0), r, 1) > 0


def min_filter(a, r):
    """The least value in the (2r+1) square round each cell; the border reads as 0 (so it refuses)."""
    out = np.pad(a, r, constant_values=0)
    cur = out
    for axis in (0, 1):
        acc = cur.copy()
        for s in range(1, r + 1):
            lo = np.roll(cur, s, axis=axis)
            hi = np.roll(cur, -s, axis=axis)
            acc = np.minimum(acc, np.minimum(lo, hi))
        cur = acc
    return cur[r:-r, r:-r] if r else cur


class Box:
    """A box in block coordinates and the conversion to raster indices."""

    def __init__(self, x0, z0, x1, z1):
        self.x0, self.z0, self.x1, self.z1 = int(x0), int(z0), int(x1), int(z1)
        self.shape = (self.z1 - self.z0 + 1, self.x1 - self.x0 + 1)

    def zeros(self, dtype=bool):
        return np.zeros(self.shape, dtype)

    def inside(self, x, z):
        return self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1

    def put_rect(self, m, xa, za, xb, zb, val=True):
        xa, xb = max(int(xa), self.x0), min(int(xb), self.x1)
        za, zb = max(int(za), self.z0), min(int(zb), self.z1)
        if xa <= xb and za <= zb:
            m[za - self.z0:zb - self.z0 + 1, xa - self.x0:xb - self.x0 + 1] = val

    def put_point(self, m, x, z):
        x, z = int(round(x)), int(round(z))
        if self.inside(x, z):
            m[z - self.z0, x - self.x0] = True

    def put_segment(self, m, ax, az, bx, bz):
        n = int(max(abs(bx - ax), abs(bz - az))) + 1
        for i in range(n + 1):
            t = i / max(n, 1)
            self.put_point(m, ax + (bx - ax) * t, az + (bz - az) * t)


# ------------------------------------------------------------------ authored places

_AUTH_CACHE = {}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _walk(o, pts, rects, segs):
    if isinstance(o, dict):
        if str(o.get("id", "")).startswith(NEST_PREFIX):
            # the networks' own nest-room Habitat Blocks (tools/nest_rooms.py) sit inside them: scanned as authored places they
            # would make each network keep 32 from its own rooms and regrow, as mine_crew_trainers.json would have
            return
        if _num(o.get("x")) and _num(o.get("z")):
            pts.append((o["x"], o["z"]))
        if all(_num(o.get(k)) for k in ("min_x", "max_x", "min_z", "max_z")):
            if o["max_x"] - o["min_x"] < 2000 and o["max_z"] - o["min_z"] < 2000:
                rects.append((o["min_x"], o["min_z"], o["max_x"], o["max_z"]))
        for k, v in o.items():
            if isinstance(k, str) and k.startswith("nearest_"):
                continue
            _walk(v, pts, rects, segs)
    elif isinstance(o, list):
        if len(o) == 2 and all(_num(v) for v in o):
            pts.append((o[0], o[1]))
        elif len(o) == 3 and all(_num(v) for v in o):
            pts.append((o[0], o[2]))
            pts.append((o[0], o[1]))
        elif len(o) == 4 and all(_num(v) for v in o):
            x0, z0, x1, z1 = o
            if x1 >= x0 and z1 >= z0 and x1 - x0 < 2000 and z1 - z0 < 2000:
                rects.append((x0, z0, x1, z1))
        else:
            pairs = [v for v in o if isinstance(v, list) and len(v) >= 2 and _num(v[0]) and _num(v[1])]
            if len(pairs) == len(o) and len(o) >= 3:
                for a, b in zip(o, o[1:]):
                    if math.hypot(b[0] - a[0], b[1] - a[1]) <= 120:
                        segs.append((a[0], a[1], b[0], b[1]))
            for v in o:
                _walk(v, pts, rects, segs)


def authored(data_dir=None):
    """(points, rects, segments) every data/*.json (the skipped files aside) authors, cached."""
    d = Path(data_dir or DATA)
    key = str(d)
    if key not in _AUTH_CACHE:
        pts, rects, segs = [], [], []
        for p in sorted(d.glob("*.json")):
            if p.name in SKIP_FILES:
                continue
            _walk(json.loads(p.read_text(encoding="utf-8")), pts, rects, segs)
        _AUTH_CACHE[key] = (sorted(set((int(round(x)), int(round(z))) for x, z in pts)),
                            sorted(set((int(x0), int(z0), int(x1), int(z1)) for x0, z0, x1, z1 in rects)),
                            sorted(set((int(round(a)), int(round(b)), int(round(c)), int(round(e))) for a, b, c, e in segs)))
    return _AUTH_CACHE[key]


def authored_seed(box):
    """A bool raster of the authored places themselves (no margin): points, filled boxes, polyline cells."""
    pts, rects, segs = authored()
    m = box.zeros()
    for x, z in pts:
        box.put_point(m, x, z)
    for x0, z0, x1, z1 in rects:
        if x1 < box.x0 or x0 > box.x1 or z1 < box.z0 or z0 > box.z1:
            continue
        box.put_rect(m, x0, z0, x1, z1)
    for a, b, c, e in segs:
        if max(a, c) < box.x0 or min(a, c) > box.x1 or max(b, e) < box.z0 or min(b, e) > box.z1:
            continue
        box.put_segment(m, a, b, c, e)
    return m


# ------------------------------------------------------------------ water

def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def water_seed(box, hbox, rules):
    """A bool raster of where there is, or may be, water: the sea, every lake basin, every river corridor, every waterway."""
    from PIL import Image, ImageDraw
    m = hbox <= int(rules["sea_near"])
    img = Image.new("L", (box.shape[1], box.shape[0]), 0)
    dr = ImageDraw.Draw(img)

    def to_px(x, z):
        return (x - box.x0, z - box.z0)

    for l in _load("landmarks.json")["landmarks"]:
        for ring in (l.get("water_body") or {}).get("basin_polygons") or []:
            dr.polygon([to_px(q[0], q[1]) for q in ring], fill=1)
    half = int(rules["river_corridor"])
    for c in _load("rivers.json")["courses"]:
        w = max([r.get("width", 0) for r in c.get("reaches") or []] + [0]) / 2.0
        rad = int(math.ceil(half + w + 4))
        pts = [to_px(p[0], p[1]) for p in c["graded_polyline"]]
        for a, b in zip(pts, pts[1:]):
            dr.line([a, b], fill=1, width=2 * rad + 1)
        for p in pts:
            dr.ellipse([p[0] - rad, p[1] - rad, p[0] + rad, p[1] + rad], fill=1)
    for w in _load("waterways.json")["waterways"]:
        rad = int(math.ceil(w.get("half_width", 8) + 6))
        pts = [to_px(p[0], p[1]) for p in w["polyline"]]
        for a, b in zip(pts, pts[1:]):
            dr.line([a, b], fill=1, width=2 * rad + 1)
        for p in pts:
            dr.ellipse([p[0] - rad, p[1] - rad, p[0] + rad, p[1] + rad], fill=1)
    return m | (np.asarray(img) > 0)
