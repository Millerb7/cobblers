#!/usr/bin/env python
"""Shape the water into a COPY of the canonical heightmap, from data/water_shape.json (Phase B of the water build).

Everything the water needs that is a height goes here, in one revision, so the full re-export rehearsal is paid once
(docs/mechanics/WATER_BUILD_PLAN.md decision 5):

  rivers   meanders on the low-grade reaches, pools and riffles, cascades and small falls on the steep creeks
  stream   the Viltri Ravine's underfit stream, from a spring at the pass down the sea half only
  lakes    littoral shelves, drop-offs, a basin floor, humps and shoals (rest points), keep zones left exactly
  coasts   bars, runnels and a lagoon on the south flats, the Fungal Isle bar chain, the Relic reef platform,
           skerries and sea stacks
  seabed   OCEAN.md section 4's shelf, break, slope and basin, filled up to the profile with the canyons carried
           through, and two ridges

It reads the canonical heightmap data/world.json pins (never a world: tools/ground.py's rule) and writes a new file
under derived/water_shape/, never over the source. Every column no feature writes stays bit-identical. Protected
columns (towns, roads, the Rift, Victory Road, bridges, the islet, the sea town, built water event sites) are never
written; a feature that wanted one is reported as held off.

Alongside the copy it writes, for the owner: before/after maps of every lake, the rivers, the southern coast, the
Fungal chain, the reef and the seabed; cross-sections; a walk of every crossing in WATER_BUILD_PLAN 11.1 with the swim
fatigue constants read from data/blackout.json; lake wadeable shares and rest spacing; river sinuosity; cut and fill
per feature (derived/water_shape/REPORT.md and report.json).

    python tools/water_shape.py --source-root <root>                   # build the copy, maps and measurements
    python tools/water_shape.py --source-root <root> --only lakes      # one family, for iterating (partial copy)
    python tools/water_shape.py --source-root <root> --no-maps         # skip the PNGs
    python tools/water_shape.py --source-root <root> --apply           # the owner-approved step; refuses unless
                                                                       # tools/water_shape_audit.py passed this copy

Then: python tools/water_shape_audit.py --source-root <root>
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import sys
import time
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import terrain as T  # noqa: E402
import rescale as RS  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

ROOT = T.ROOT
SPEC = ROOT / "data" / "water_shape.json"
SEA = 62
FAMILIES = ("rivers", "stream", "lakes", "coasts", "seabed")
WORLD_READS = ()          # heightmap and data only; never a world

SQ2, SQ5 = math.sqrt(2.0), math.sqrt(5.0)
OFFSETS = ((0, 1, 1.0), (1, 0, 1.0), (0, -1, 1.0), (-1, 0, 1.0),
           (1, 1, SQ2), (1, -1, SQ2), (-1, 1, SQ2), (-1, -1, SQ2),
           (1, 2, SQ5), (2, 1, SQ5), (-1, 2, SQ5), (-2, 1, SQ5),
           (1, -2, SQ5), (2, -1, SQ5), (-1, -2, SQ5), (-2, -1, SQ5))


class ShapeError(Exception):
    pass


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rng_for(*key):
    """A random stream fixed by its key. crc32, not hash(): Python randomises string hashes per process."""
    return random.Random(zlib.crc32(repr(key).encode()) & 0xFFFFFFFF)


def seed_of(*key):
    return zlib.crc32(repr(key).encode()) & 0x7FFFFFFF


# ---------------------------------------------------------------------------------------------------- small tools


def _hash01(ix, iz, seed):
    h = (ix.astype(np.int64) * 73856093) ^ (iz.astype(np.int64) * 19349663) ^ (int(seed) * 83492791)
    h = h & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float64) / float(0xFFFFFF)


def value_noise(X, Z, scale, seed):
    """Smooth value noise in [0, 1] at world columns X, Z. Deterministic: the same column always gets the same value."""
    fx = np.asarray(X, np.float64) / float(scale)
    fz = np.asarray(Z, np.float64) / float(scale)
    ix = np.floor(fx).astype(np.int64)
    iz = np.floor(fz).astype(np.int64)
    tx, tz = fx - ix, fz - iz
    sx, sz = tx * tx * (3 - 2 * tx), tz * tz * (3 - 2 * tz)
    a, b = _hash01(ix, iz, seed), _hash01(ix + 1, iz, seed)
    c, d = _hash01(ix, iz + 1, seed), _hash01(ix + 1, iz + 1, seed)
    return (a * (1 - sx) + b * sx) * (1 - sz) + (c * (1 - sx) + d * sx) * sz


def clip_box(x0, z0, x1, z1, n):
    """A half-open box [x0, x1) x [z0, z1) clipped to the map."""
    return max(0, int(x0)), max(0, int(z0)), min(n, int(x1)), min(n, int(z1))


def sl(box):
    x0, z0, x1, z1 = box
    return slice(z0, z1), slice(x0, x1)


def raster_polygons(rings, box):
    x0, z0, x1, z1 = box
    img = Image.new("L", (max(1, x1 - x0), max(1, z1 - z0)), 0)
    d = ImageDraw.Draw(img)
    for ring in rings:
        pts = [(float(p[0]) - x0, float(p[1]) - z0) for p in ring]
        if len(pts) >= 3:
            d.polygon(pts, fill=1)
    return np.array(img).astype(bool)


def raster_lines(lines, box, width):
    """Polylines drawn `width` blocks wide, with round joins."""
    x0, z0, x1, z1 = box
    img = Image.new("L", (max(1, x1 - x0), max(1, z1 - z0)), 0)
    d = ImageDraw.Draw(img)
    r = width / 2.0
    for line in lines:
        pts = [(float(p[0]) - x0, float(p[1]) - z0) for p in line]
        if len(pts) >= 2:
            d.line(pts, fill=1, width=max(1, int(round(width))))
        for px, pz in pts:
            d.ellipse([px - r, pz - r, px + r, pz + r], fill=1)
    return np.array(img).astype(bool)


def distance(src, through=None, max_iter=100000):
    """Chamfer distance (1, sqrt 2, sqrt 5; within about 2% of Euclidean) from the `src` cells, spreading only into
    `through` cells. Iterated to a fixed point, so it needs no scipy."""
    d = np.where(src, 0.0, np.inf).astype(np.float32)
    thr = np.ones(src.shape, bool) if through is None else (through | src)
    H, W = d.shape
    for _ in range(max_iter):
        changed = False
        for dz, dx, w in OFFSETS:
            a0, a1 = max(0, dz), H + min(0, dz)
            b0, b1 = max(0, dx), W + min(0, dx)
            if a1 <= a0 or b1 <= b0:
                continue
            tgt = d[a0:a1, b0:b1]
            cand = d[a0 - dz:a1 - dz, b0 - dx:b1 - dx] + np.float32(w)
            m = (cand < tgt) & thr[a0:a1, b0:b1]
            if m.any():
                np.copyto(tgt, cand, where=m)
                changed = True
        if not changed:
            break
    return d


def distance_scaled(src, through, factor):
    """distance() on a grid `factor` times coarser (a coarse cell is a source if any of its columns is), in blocks."""
    if factor <= 1:
        return distance(src, through)
    H, W = src.shape
    h, w = -(-H // factor), -(-W // factor)
    sp = np.zeros((h * factor, w * factor), bool)
    tp = np.zeros((h * factor, w * factor), bool)
    sp[:H, :W] = src
    tp[:H, :W] = True if through is None else through
    s = sp.reshape(h, factor, w, factor).any(axis=(1, 3))
    t = tp.reshape(h, factor, w, factor).any(axis=(1, 3))
    dc = distance(s, t) * factor
    return np.repeat(np.repeat(dc, factor, 0), factor, 1)[:H, :W]


def grow(mask, r):
    if r <= 0:
        return mask.copy()
    return distance(mask, None, max_iter=int(r) + 2) <= r


def box_mean(a, r):
    a = np.asarray(a, np.float64)
    p = np.pad(a, r, mode="constant")
    c = np.pad(p, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    k = 2 * r + 1
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s / float(k * k)


def dilate4(m):
    o = m.copy()
    o[1:, :] |= m[:-1, :]
    o[:-1, :] |= m[1:, :]
    o[:, 1:] |= m[:, :-1]
    o[:, :-1] |= m[:, 1:]
    return o


def component_near(mask, z, x):
    """The 4-connected piece of `mask` holding (z, x), or the piece nearest to it."""
    if not mask.any():
        return mask.copy()
    if not mask[z, x]:
        zs, xs = np.nonzero(mask)
        i = int(np.argmin((zs - z) ** 2 + (xs - x) ** 2))
        z, x = int(zs[i]), int(xs[i])
    comp = np.zeros(mask.shape, bool)
    comp[z, x] = True
    while True:
        nxt = dilate4(comp) & mask
        if nxt.sum() == comp.sum():
            return comp
        comp = nxt


def running(a, w, fn):
    """A running min or mean over a centred window of w samples (edges padded)."""
    w = max(1, int(w))
    if w <= 1 or len(a) < 2:
        return np.asarray(a, np.float64).copy()
    h = w // 2
    p = np.pad(np.asarray(a, np.float64), (h, h), mode="edge")
    v = np.lib.stride_tricks.sliding_window_view(p, 2 * h + 1)
    return v.min(axis=1) if fn == "min" else v.mean(axis=1)


def line_cells(a, b):
    """The columns of a straight line, one per step, and the step length (tests/test_system_contracts.py's walk)."""
    (x0, z0), (x1, z1) = a, b
    n = int(max(abs(x1 - x0), abs(z1 - z0)))
    out = []
    for i in range(n + 1):
        c = (int(round(x0 + (x1 - x0) * i / max(1, n))), int(round(z0 + (z1 - z0) * i / max(1, n))))
        if not out or out[-1] != c:
            out.append(c)
    return out, math.dist(a, b) / max(1, len(out) - 1)


def bearing_deg(dx, dz):
    """Compass bearing, 0 north (-z), 90 east (+x)."""
    return np.degrees(np.arctan2(dx, -dz)) % 360.0


def in_bearing(b, rng_deg):
    lo, hi = rng_deg
    return (b >= lo) & (b <= hi) if lo <= hi else (b >= lo) | (b <= hi)


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------------------------------- heightmap i/o


def ground_of_raw(raw, world, band=512):
    """The integer ground tools/ground.py gives: the import line, float32, rounded."""
    out = np.empty(raw.shape, np.int16)
    for z in range(0, raw.shape[0], band):
        y = T.sample_to_height(raw[z:z + band], world).astype(np.float32)
        out[z:z + band] = np.round(y).astype(np.int16)
    return out


def raw_of_ground(g, world):
    imp = world["import"]
    h = RS.h_of_y(np.asarray(g, np.float64), imp, float(imp["high_out"]))
    return np.clip(np.rint(h), 0, 65535).astype(np.uint16)


# ---------------------------------------------------------------------------------------------------- the context


class Ctx:
    def __init__(self, world, spec, raw, G0, hm_path):
        self.world, self.spec, self.raw, self.G0, self.hm_path = world, spec, raw, G0, hm_path
        self.N = G0.shape[0]
        self.G1 = G0.copy()
        self.owner = np.zeros(G0.shape, np.uint8)
        self.features = [{"id": "(none)", "family": None}]
        self.P = np.zeros(G0.shape, bool)
        self.protect_parts = {}
        self.report = {"features": {}, "crossings": {}, "lakes": {}, "rivers": {}, "coasts": {}, "seabed": {},
                       "notes": []}
        self.revised_courses = {}
        self.zone_maps = {}
        self.lake_mask = None
        self.gate_lines = []
        self.crossing_lines = {}
        self.regions = None

    def feature(self, fid, family, **info):
        if len(self.features) >= 255:
            raise ShapeError("more than 254 features: the ownership map is one byte")
        self.features.append({"id": fid, "family": family, "held_protected": 0, "held_clash": 0, **info})
        return len(self.features) - 1

    def write(self, k, box, new, mask):
        """Propose ground `new` (over the box) where `mask`. Protected columns and columns another feature already
        owns are held off and counted; the rest are written and owned by feature k."""
        s = sl(box)
        cur, own, prot = self.G1[s], self.owner[s], self.P[s]
        want = mask & (new != cur)
        held = want & prot
        clash = want & ~prot & (own != 0) & (own != k)
        ok = want & ~prot & ~clash
        np.copyto(cur, np.asarray(new, np.int16), where=ok)
        own[ok] = k
        f = self.features[k]
        f["held_protected"] += int(held.sum())
        f["held_clash"] += int(clash.sum())
        return ok

    def region(self, rid):
        if self.regions is None:
            doc = load("regions.json")
            self.regions = {r["id"]: r for r in doc["regions"]}
            for r in doc.get("marine_regions", []):
                self.regions[r["id"]] = r
        if rid not in self.regions:
            raise ShapeError("no region %s in data/regions.json" % rid)
        return self.regions[rid]

    def region_mask(self, rid, grow_by, pad=4):
        """(box, mask) of a region's polygons grown by grow_by blocks."""
        r = self.region(rid)
        rings = r.get("polygons") or []
        if not rings:
            raise ShapeError("region %s has no polygons" % rid)
        xs = [p[0] for ring in rings for p in ring]
        zs = [p[1] for ring in rings for p in ring]
        box = clip_box(min(xs) - grow_by - pad, min(zs) - grow_by - pad, max(xs) + grow_by + pad + 1,
                       max(zs) + grow_by + pad + 1, self.N)
        m = raster_polygons(rings, box)
        if grow_by > 0:
            m = grow(m, grow_by)
        return box, m


# ---------------------------------------------------------------------------------------------------- protection


def build_protect(ctx):
    spec = ctx.spec["protect"]
    N = ctx.N
    parts = {}

    def add(name, box, mask):
        ctx.P[sl(box)] |= mask
        parts[name] = parts.get(name, 0) + int(mask.sum())

    towns = load("towns.json")["towns"]
    m = int(spec["town_margin_blocks"])
    for t in towns:
        fp = t.get("footprint") or {}
        if fp.get("min_x") is None:
            continue
        box = clip_box(fp["min_x"] - m, fp["min_z"] - m, fp["max_x"] + m + 1, fp["max_z"] + m + 1, N)
        add("towns", box, np.ones((box[3] - box[1], box[2] - box[0]), bool))

    lines = []
    for r in load("routes.json")["routes"]:
        pts = []
        for q in (r.get("corridor") or {}).get("polyline") or []:
            if isinstance(q, dict) and "x" in q:
                pts.append((q["x"], q["z"]))
            elif isinstance(q, (list, tuple)) and len(q) >= 2:
                pts.append((q[0], q[1]))
        if len(pts) >= 2:
            lines.append(pts)
    full = (0, 0, N, N)
    add("roads", full, raster_lines(lines, full, 2 * spec["road_half_width_blocks"] + 1))

    bm = int(spec["bridge_margin_blocks"])
    for b in load("bridges.json")["bridges"]:
        hw = int(b.get("walkway_half_width", 2)) + 2
        if b["axis"] == "z":
            box = (b["centre"] - hw - bm, b["along_from"] - bm, b["centre"] + hw + bm + 1, b["along_to"] + bm + 1)
        else:
            box = (b["along_from"] - bm, b["centre"] - hw - bm, b["along_to"] + bm + 1, b["centre"] + hw + bm + 1)
        box = clip_box(*box, N)
        add("bridges", box, np.ones((box[3] - box[1], box[2] - box[0]), bool))

    rs = spec["rift"]
    box, rm = ctx.region_mask(rs["region"], int(rs["grow_blocks"]))
    add("rift_region", box, rm)
    base = ctx.world["heightmap"].get("rift_sculpted_from")
    if not base:
        raise ShapeError("data/world.json has no heightmap.rift_sculpted_from: cannot find the columns the Rift changed")
    pre = ctx.hm_path.parent / base["path"]
    if not pre.is_file() or sha256_file(pre) != base["sha256"]:
        raise ShapeError("the pre-Rift heightmap %s is missing or does not hash to %s: the Rift's columns cannot be "
                         "protected, so nothing is shaped" % (pre, base["sha256"][:12]))
    raw_pre = np.array(Image.open(pre))
    x0, z0, x1, z1 = box
    rbox = clip_box(x0 - 200, z0 - 200, x1 + 200, z1 + 200, N)
    diff = raw_pre[sl(rbox)] != ctx.raw[sl(rbox)]
    del raw_pre
    add("rift_sculpt", rbox, grow(diff, 8))

    vr = load("vr_caves.json")
    band = int(vr["guide"]["band"]) + int(spec["victory_road"]["extra_blocks"])
    add("victory_road", full, raster_lines([vr["guide"]["points"]], full, 2 * band + 1))

    import islet as I
    cx, cz = I.CENTRE
    r = I.RADIUS + int(spec["islet"]["margin_blocks"])
    box = clip_box(cx - r, cz - r, cx + r + 1, cz + r + 1, N)
    add("islet", box, np.ones((box[3] - box[1], box[2] - box[0]), bool))

    for site in spec.get("event_sites", []):
        x0, z0, x1, z1 = site["box"]
        box = clip_box(x0, z0, x1 + 1, z1 + 1, N)
        add("event_sites", box, np.ones((box[3] - box[1], box[2] - box[0]), bool))

    ctx.protect_parts = parts
    ctx.report["protect"] = {"columns_by_part": parts, "columns_total": int(ctx.P.sum())}


def build_lake_mask(ctx):
    ctx.lake_mask = np.zeros(ctx.G0.shape, bool)
    ctx.lake_bodies = {}
    for lm in load("landmarks.json")["landmarks"]:
        wb = lm.get("water_body")
        if not wb:
            continue
        rings = wb["basin_polygons"]
        xs = [p[0] for ring in rings for p in ring]
        zs = [p[1] for ring in rings for p in ring]
        box = clip_box(min(xs) - 4, min(zs) - 4, max(xs) + 5, max(zs) + 5, ctx.N)
        m = raster_polygons(rings, box)
        ctx.lake_mask[sl(box)] |= m
        ctx.lake_bodies[lm["id"]] = {"landmark": lm, "box": box, "inside": m, "level": int(wb["level_y"])}


# ---------------------------------------------------------------------------------------------------- swim fatigue


def fatigue_constants():
    s = load("blackout.json")["surface"]
    keys = ("sample_ticks", "gain_shallow_per_tick", "gain_deep_per_tick", "recover_per_tick", "warn_ticks",
            "slow_ticks", "exhausted_ticks", "collapse_ticks", "pulse_ticks", "cap_ticks", "deep_water_blocks")
    missing = [k for k in keys if k not in s]
    if missing:
        raise ShapeError("data/blackout.json surface lacks %s" % missing)
    return {k: s[k] for k in keys}


def walk(depths, step, qual, S, speed=5.0, slowness=False, rest_wait=False):
    """Swim a depth profile at `speed` with the pack's constants. Returns hits (block positions), peak fatigue, and
    the fatigue trace (position, fatigue) per sample."""
    per = S["sample_ticks"]
    fac = 0.5 if qual else 1.0
    f, peak, pos, t = 0.0, 0.0, 0.0, 0
    total = len(depths) * step
    hits, trace, next_hit = [], [], None
    rest_run = np.zeros(len(depths), int)
    run = 0
    for i in range(len(depths) - 1, -1, -1):
        run = run + 1 if depths[i] <= 1 else 0
        rest_run[i] = run
    while pos < total:
        spd = speed
        if slowness:
            spd *= 0.7 if f >= S["exhausted_ticks"] else (0.85 if f >= S["slow_ticks"] else 1.0)
        pos += spd * per / 20.0
        i = min(len(depths) - 1, int(pos / step))
        d = depths[i]
        t += per
        if d <= 1:
            if rest_wait and rest_run[i] * step >= 6:
                f = 0.0
            else:
                f = max(0.0, f - S["recover_per_tick"] * per)
            trace.append((pos, f))
            continue
        gain = S["gain_deep_per_tick"] if d >= S["deep_water_blocks"] else S["gain_shallow_per_tick"]
        f = min(float(S["cap_ticks"]), f + gain * per * fac)
        peak = max(peak, f)
        if f >= S["collapse_ticks"]:
            if next_hit is None or t >= next_hit:
                hits.append(round(pos, 1))
                next_hit = t + S["pulse_ticks"]
        trace.append((pos, f))
    return hits, peak, trace


def outcome(hits):
    return "no hit" if not hits else ("hit" if len(hits) < 2 else "knocked out")


def peak_word(peak, S):
    if peak >= S["collapse_ticks"]:
        return "collapsed"
    if peak >= S["exhausted_ticks"]:
        return "exhausted"
    if peak >= S["slow_ticks"]:
        return "slowed"
    if peak >= S["warn_ticks"]:
        return "warned"
    return "fresh"


# ---------------------------------------------------------------------------------------------------- crossings


def overlay_ground(ctx, G, names):
    """The integer ground with Relic Island's islet and the sea town's decks laid over (tools/ground.py for_settlement)."""
    g = G
    out = {}
    if "relic_island" in names:
        import islet as I
        cx, cz = I.CENTRE
        r = I.RADIUS
        bed = g[cz - r:cz + r + 1, cx - r:cx + r + 1].astype(float)
        top, _ = I.island_top(bed, SEA)
        top = np.asarray(top, float)
        ok = ~np.isnan(top)
        zs, xs = np.nonzero(ok)
        for z, x in zip(zs, xs):
            out[(cx - r + int(x), cz - r + int(z))] = int(np.round(top[z, x]))
    if "sea_town" in names:
        import sea_town
        level, deck = sea_town.deck_ground(ctx.world)
        for x, z in deck:
            out[(int(x), int(z))] = int(level)
    return out


def region_land_cells(ctx, G, rid, grow_by=24):
    box, m = ctx.region_mask(rid, grow_by)
    land = m & (G[sl(box)] >= SEA)
    zs, xs = np.nonzero(land)
    return box, land, xs + box[0], zs + box[1]


def shore_of(land, g_box):
    """Land cells beside real water (not merely beside the edge of the region's polygon)."""
    return land & dilate4(g_box < SEA)


def crossing_endpoints(ctx, c, G):
    kind = c["kind"]
    if kind == "points":
        return tuple(c["from"]), tuple(c["to"])
    if kind == "to_region":
        _box, _land, xs, zs = region_land_cells(ctx, G, c["to_region"])
        if not len(xs):
            raise ShapeError("%s: no land in %s" % (c["id"], c["to_region"]))
        fx, fz = c["from"]
        i = int(np.argmin((xs - fx) ** 2 + (zs - fz) ** 2))
        return (fx, fz), (int(xs[i]), int(zs[i]))
    if kind == "row":
        z = int(c["z"])
        ba, la, _, _ = region_land_cells(ctx, G, c["from_region"])
        bb, lb, _, _ = region_land_cells(ctx, G, c["to_region"])
        xa = [ba[0] + int(x) for x in np.nonzero(la[z - ba[1]])[0]] if ba[1] <= z < ba[3] else []
        xb = [bb[0] + int(x) for x in np.nonzero(lb[z - bb[1]])[0]] if bb[1] <= z < bb[3] else []
        if not xa or not xb:
            raise ShapeError("%s: no land of both regions on row z%d" % (c["id"], z))
        if min(xb) > max(xa):
            x1 = min(xb)
            x0 = max(x for x in xa if x < x1)
        else:
            x0 = max(xa)
            later = [x for x in xb if x > x0]
            if not later:
                x1 = max(xb)
                x0 = min(x for x in xa if x > x1) if any(x > x1 for x in xa) else x0
            else:
                x1 = min(later)
        return (x0, z), (x1, z)
    if kind == "shortest":
        ba, la, _, _ = region_land_cells(ctx, G, c["from_region"])
        bb, lb, _, _ = region_land_cells(ctx, G, c["to_region"])
        za, xa = np.nonzero(shore_of(la, G[sl(ba)]))
        zb, xb = np.nonzero(shore_of(lb, G[sl(bb)]))
        if not len(xa) or not len(xb):
            raise ShapeError("%s: a region has no shore" % c["id"])
        xa, za = xa[::2] + ba[0], za[::2] + ba[1]
        xb, zb = xb + bb[0], zb + bb[1]
        best = (float("inf"), None)
        for s in range(0, len(xa), 2000):
            ax, az = xa[s:s + 2000, None], za[s:s + 2000, None]
            d2 = (ax - xb[None, :]) ** 2 + (az - zb[None, :]) ** 2
            i = int(np.argmin(d2))
            v = float(d2.flat[i])
            if v < best[0]:
                ia, ib = divmod(i, len(xb))
                best = (v, ((int(ax[ia, 0]), int(az[ia, 0])), (int(xb[ib]), int(zb[ib]))))
        return best[1]
    raise ShapeError("unknown crossing kind %s" % kind)


def measure_line(G, over, a, b):
    cells, step = line_cells(a, b)
    depth = [SEA - over.get((x, z), int(G[z, x])) for x, z in cells]
    wet = [i for i, d in enumerate(depth) if d > 1]
    if not wet:
        return {"cells": cells, "step": step, "depths": [], "all_depths": depth, "dry_from": True, "dry_to": True}
    d = depth[wet[0]:wet[-1] + 1]
    runs, cur, deep_run, curd = [], 0, 0, 0
    for v in d:
        cur = 0 if v <= 1 else cur + 1
        runs.append(cur)
        curd = curd + 1 if v >= 3 else 0
        deep_run = max(deep_run, curd)
    return {"cells": cells, "step": step, "depths": d, "all_depths": depth,
            "length": round(len(cells) * step), "swim": round(max(runs) * step),
            "deep": round(sum(1 for v in d if v >= 3) * step), "deepest": int(max(d)),
            "max_deep_run": round(deep_run * step), "dry_from": depth[0] <= 1, "dry_to": depth[-1] <= 1}


def walk_line(m, S):
    out = {}
    for who, q in (("unaided", 0), ("trained", 1)):
        hits, peak, trace = walk(m["depths"], m["step"], q, S)
        hits_s, _, _ = walk(m["depths"], m["step"], q, S, slowness=True)
        hits_r, _, _ = walk(m["depths"], m["step"], q, S, rest_wait=True)
        out[who] = {"outcome": outcome(hits), "first_hit_at": hits[0] if hits else None, "peak": round(peak),
                    "peak_word": peak_word(peak, S), "with_slowness": outcome(hits_s),
                    "resting_on_rest_ground": outcome(hits_r), "trace": trace}
    return out


def crossings_pass(ctx, when, G):
    S = fatigue_constants()
    res = {}
    for c in ctx.spec["crossings"]:
        over = overlay_ground(ctx, G, c.get("overlays", []))
        if when == "before":
            a, b = crossing_endpoints(ctx, c, G)
            ctx.crossing_lines[c["id"]] = (a, b)
        else:
            a, b = ctx.crossing_lines[c["id"]]
        m = measure_line(G, over, a, b)
        entry = {"from": list(a), "to": list(b)}
        if m["depths"]:
            entry.update({k: m[k] for k in ("length", "swim", "deep", "deepest", "max_deep_run", "dry_from", "dry_to")})
            entry["walk"] = walk_line(m, S)
            entry["depths"] = m["depths"]
            entry["step"] = m["step"]
        else:
            entry["no_swimming"] = True
        if when == "after" and c["kind"] in ("to_region", "shortest"):
            try:
                a2, b2 = crossing_endpoints(ctx, c, G)
                if (a2, b2) != (a, b):
                    m2 = measure_line(G, over, a2, b2)
                    if m2["depths"]:
                        entry["recomputed_line"] = {"from": list(a2), "to": list(b2), "swim": m2["swim"],
                                                    "walk": {k: {kk: vv for kk, vv in v.items() if kk != "trace"}
                                                             for k, v in walk_line(m2, S).items()}}
            except ShapeError as e:
                entry["recomputed_line"] = {"error": str(e)}
        res[c["id"]] = entry
    return res


def gate_lines(ctx):
    out = []
    for c in ctx.spec["crossings"]:
        if (c.get("require_after") or {}).get("gate") or (c.get("require_after") or {}).get("unchanged"):
            out.append(ctx.crossing_lines[c["id"]])
    return out


# ---------------------------------------------------------------------------------------------------- rivers


def shape_table(omega):
    """One wavelength of a sine-generated curve (the planform real meanders follow): the lateral offset, normalised
    to [-1, 1], as a function of the along-valley fraction; its amplitude over wavelength; and its sinuosity."""
    n = 4000
    s = (np.arange(n) + 0.5) / n
    th = omega * np.sin(2 * np.pi * s)
    c = np.concatenate([[0.0], np.cumsum(np.cos(th)) / n])
    y = np.concatenate([[0.0], np.cumsum(np.sin(th)) / n])
    L = c[-1]
    cn = c / L
    y = y - 0.5 * (y.max() + y.min())
    amp = float(np.abs(y).max())
    yn = y / amp
    sign = np.sign(yn)
    ups = np.nonzero((sign[:-1] <= 0) & (sign[1:] > 0))[0]
    u0 = float(cn[ups[0]]) if len(ups) else 0.0
    return cn, yn, amp / L, 1.0 / L, u0


def course_by_id(doc, cid):
    for c in doc["courses"]:
        if c["id"] == cid:
            return c
    raise ShapeError("no course %s in data/rivers.json" % cid)


def allowed_amplitude(ctx, xs, zs, nx, nz, S, hw, reaches_at, e, dflt):
    n = len(xs)
    cap = float(e["max_amplitude_blocks"])
    margin = float(dflt["bank_margin_blocks"])
    pc = float(dflt["protect_clearance_blocks"])
    rise = float(dflt.get("room_rise_blocks", 3))
    maxd = int(cap + hw.max() + margin + pc + 3)
    N = ctx.N
    free = np.full(n, float(maxd))
    room = [np.full(n, float(maxd)), np.full(n, float(maxd))]
    alive = [np.ones(n, bool), np.ones(n, bool)]
    for d in range(1, maxd + 1):
        for si, sgn in enumerate((1.0, -1.0)):
            px = np.clip(np.rint(xs + sgn * nx * d).astype(int), 0, N - 1)
            pz = np.clip(np.rint(zs + sgn * nz * d).astype(int), 0, N - 1)
            bad = ctx.P[pz, px] | (ctx.lake_mask[pz, px] & (d > hw + 1))
            free = np.where(bad & (free > d), float(d), free)
            ok = ctx.G0[pz, px] <= S + rise
            stop = alive[si] & ~ok
            room[si] = np.where(stop, float(d - 1), room[si])
            alive[si] &= ok
    a_prot = free - hw - pc - 1.0
    if e["belt"] == "measured":
        a_belt = np.minimum(room[0], room[1]) - hw - margin
    else:
        a_belt = np.empty(n)
        for i in range(n):
            r = reaches_at[i]
            v = r.get("valley")
            if not v:
                a_belt[i] = min(room[0][i], room[1][i]) - hw[i] - margin
                continue
            ext = 2.0 / max(0.2, r["bank_slope"]) + v["floodplain_width"]
            if "first_tread" in e["belt"] and v.get("terraces"):
                t0 = v["terraces"][0]
                ext += t0["rise"] / max(0.2, v["riser_slope"]) + t0["tread"]
            a_belt[i] = ext - margin
    return np.clip(np.minimum(a_belt, a_prot), 0.0, cap)


def stamp(stations, box, radius_of):
    """For every column of the box within its station's radius: the nearest station's index, distance and signed
    lateral offset (positive to the left of the direction of flow)."""
    x0, z0, x1, z1 = box
    H, W = z1 - z0, x1 - x0
    best = np.full((H, W), np.inf, np.float32)
    idx = np.full((H, W), -1, np.int32)
    lat = np.zeros((H, W), np.float32)
    xs, zs, nxs, nzs = stations
    for j in range(len(xs)):
        r = radius_of(j)
        a0, a1 = max(z0, int(zs[j] - r) - 1), min(z1, int(zs[j] + r) + 2)
        b0, b1 = max(x0, int(xs[j] - r) - 1), min(x1, int(xs[j] + r) + 2)
        if a1 <= a0 or b1 <= b0:
            continue
        zz, xx = np.mgrid[a0:a1, b0:b1]
        dx, dz = xx - xs[j], zz - zs[j]
        d = np.hypot(dx, dz).astype(np.float32)
        s = (slice(a0 - z0, a1 - z0), slice(b0 - x0, b1 - x0))
        m = (d <= r) & (d < best[s])
        best[s] = np.where(m, d, best[s])
        idx[s] = np.where(m, j, idx[s])
        lat[s] = np.where(m, (dx * nxs[j] + dz * nzs[j]).astype(np.float32), lat[s])
    return best, idx, lat


def step_plan(sg, Lold, jj, gathers, apart, falls, rng):
    """Where a window's surface steps: every natural one-block step moved UP-stream to the gather point at or above
    it (never down-stream: the water may only be let down, never held above its old surface), spread `apart` blocks
    below that point; a fall takes up to its drop from the steepest window as one multi-block step."""
    taken = set()
    placed = []                       # (position s, amount, kind)
    steps = [(int(j), int(Lold[j - 1] - Lold[j])) for j in jj[1:] if Lold[j - 1] > Lold[j]]
    for f in falls:
        wl = float(f["window_blocks"])
        best, bj = -1, None
        for j0 in jj:
            j1 = int(np.searchsorted(sg, sg[j0] + wl))
            j1 = min(j1, int(jj[-1]))
            drop = int(Lold[j0] - Lold[j1])
            if drop > best:
                best, bj = drop, (int(j0), j1)
        if bj is None or best <= 0:
            continue
        want = int(f["drop"])
        got = 0
        for j, d in steps:
            if bj[0] < j <= bj[1] and j not in taken and got < want:
                take = min(d, want - got)
                got += take
                if take == d:
                    taken.add(j)
                else:
                    steps = [(jj_, (dd - take) if jj_ == j else dd) for jj_, dd in steps]
        if got:
            placed.append((float(sg[bj[0]]), got, "fall"))
    groups = {}
    for j, d in steps:
        if j in taken or d <= 0:
            continue
        k = int(np.searchsorted(gathers, sg[j], side="right")) - 1
        k = max(0, k)
        groups[k] = groups.get(k, 0) + d
    for k, d in sorted(groups.items()):
        g = float(gathers[k])
        for i in range(d):
            placed.append((g + i * apart, 1, "step"))
    return placed


def reshape_course(ctx, GR, course, entries, dflt, kind_of):
    """Meander and/or gather the steps of one graded course. Returns the revised course and a report."""
    pts, chain = GR.densify_chained(course["graded_polyline"])
    X = np.array([p[0] for p in pts], float)
    Z = np.array([p[1] for p in pts], float)
    S = np.array([p[2] for p in pts], float)
    C = np.array(chain, float)
    reaches = course["reaches"]
    rat = [GR.at_chainage(reaches, c) for c in C]
    width = np.array([r["width"] for r in rat], float)
    wb = np.array([bool(r["water_body"]) for r in rat])
    D = np.asarray(GR.depth_profile(reaches, C), float)
    n = len(X)
    k6 = 6
    ia = np.clip(np.arange(n) - k6, 0, n - 1)
    ib = np.clip(np.arange(n) + k6, 0, n - 1)
    tx, tz = X[ib] - X[ia], Z[ib] - Z[ia]
    tl = np.hypot(tx, tz)
    tl[tl == 0] = 1.0
    tx, tz = tx / tl, tz / tl
    nx, nz = -tz, tx
    Yoff = np.zeros(n)
    rep = {"course": course["id"], "windows": []}
    for e in entries:
        if kind_of(e) != "meander":
            continue
        win = (C >= e["from_m"]) & (C <= e["to_m"]) & ~wb
        ii = np.nonzero(win)[0]
        if len(ii) < 20:
            raise ShapeError("%s: the window %s-%s holds no river stations" % (e["id"], e["from_m"], e["to_m"]))
        a, b = C[ii[0]], C[ii[-1]]
        hw = width[ii] / 2.0
        A = allowed_amplitude(ctx, X[ii], Z[ii], nx[ii], nz[ii], S[ii], hw, [rat[i] for i in ii], e, dflt)
        omega = math.radians(e["omega_deg"])
        cn_t, yn_t, ratio, sin_nom, u0 = shape_table(omega)
        wmed = float(np.median(width[ii]))
        lam = float(np.clip(np.median(A) / max(ratio, 1e-6), e["wavelength_widths"][0] * wmed,
                            e["wavelength_widths"][1] * wmed))
        A = running(running(A, lam / 4.0, "min"), lam / 8.0, "mean")
        t = np.clip(np.minimum(C[ii] - a, b - C[ii]) / (lam / 2.0), 0.0, 1.0)
        A = np.clip(A * (0.5 - 0.5 * np.cos(np.pi * t)), 0.0, float(e["max_amplitude_blocks"]))
        Yoff[ii] = A * np.interp(((C[ii] - a) / lam + u0) % 1.0, cn_t, yn_t)
        rep["windows"].append({"id": e["id"], "kind": "meander", "from_m": float(a), "to_m": float(b),
                               "wavelength": round(lam, 1), "amplitude_median": round(float(np.median(A)), 1),
                               "amplitude_max": round(float(A.max()), 1), "omega_deg": e["omega_deg"],
                               "nominal_sinuosity_at_full_amplitude": round(sin_nom, 3)})
    X2, Z2 = X + nx * Yoff, Z + nz * Yoff
    seg = np.hypot(np.diff(X2), np.diff(Z2))
    s_new = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s_new[-1])
    sg = np.concatenate([np.arange(0.0, total, 1.0), [total]])
    xn, zn, cn = np.interp(sg, s_new, X2), np.interp(sg, s_new, Z2), np.interp(sg, s_new, C)
    m = len(sg)
    ia = np.clip(np.arange(m) - k6, 0, m - 1)
    ib = np.clip(np.arange(m) + k6, 0, m - 1)
    tx2, tz2 = xn[ib] - xn[ia], zn[ib] - zn[ia]
    tl2 = np.hypot(tx2, tz2)
    tl2[tl2 == 0] = 1.0
    tx2, tz2 = tx2 / tl2, tz2 / tl2
    nxn, nzn = -tz2, tx2
    Sn = np.interp(cn, C, S)
    Lold = np.floor(Sn + 0.01).astype(int)
    level = Lold.copy()
    zone = np.zeros(m, np.int8)             # 0 as before, 1 pool, 2 riffle, 3 cascade, 4 fall, 5 plunge
    mult = np.ones(m)
    extra = np.zeros(m)
    offset = np.zeros(m)
    steps_all = []
    hwn = np.interp(cn, C, width) / 2.0
    Dn = np.interp(cn, C, D)
    touched = np.zeros(m, bool)
    for e in entries:
        kind = kind_of(e)
        jj = np.nonzero((cn >= e["from_m"]) & (cn <= e["to_m"]))[0]
        jj = np.array([j for j in jj if not rat[min(n - 1, int(np.searchsorted(C, cn[j])))]["water_body"]], int)
        if len(jj) < 8:
            raise ShapeError("%s: fewer than 8 stations in its window" % e["id"])
        touched[jj] = True
        rng = rng_for("rivers", e["id"])
        if kind == "meander":
            pr = dict(dflt["pools_riffles"])
            pr.update(e.get("pools_riffles") or {})
            spacing = pr["spacing_widths"] * float(np.median(hwn[jj] * 2))
            apart = int(pr["step_apart_blocks"])
            falls = []
        else:
            spacing = float(e["gather_every_blocks"])
            apart = 1
            falls = e.get("falls", [])
        gathers = [float(sg[jj[0]])]
        while gathers[-1] < sg[jj[-1]]:
            gathers.append(gathers[-1] + spacing * (1.0 + (0.2 if kind == "meander" else 0.15) * (2 * rng.random() - 1)))
        gathers = np.array(gathers)
        placed = step_plan(sg, Lold, jj, gathers, apart, falls, rng)
        L0 = int(Lold[jj[0]])
        pos = np.array([p[0] for p in placed]) if placed else np.zeros(0)
        amt = np.array([p[1] for p in placed]) if placed else np.zeros(0)
        for j in jj:
            level[j] = L0 - int(amt[pos <= sg[j]].sum()) if len(pos) else L0
        viol = int((level[jj] > Lold[jj]).sum())
        level[jj] = np.minimum(level[jj], Lold[jj])
        for p, a_, kd in placed:
            steps_all.append({"s": round(p, 1), "drop": int(a_), "kind": kd, "window": e["id"]})
        # zones and bed
        for j in jj:
            s = sg[j]
            k = max(0, int(np.searchsorted(gathers, s, side="right")) - 1)
            g0 = gathers[k]
            g1 = gathers[k + 1] if k + 1 < len(gathers) else sg[jj[-1]]
            if kind == "meander":
                psi = (s - g0) / max(1.0, g1 - g0)
                mult[j] = pr["riffle_depth_mult"] + (pr["pool_depth_mult"] - pr["riffle_depth_mult"]) * \
                    (0.5 - 0.5 * math.cos(2 * math.pi * psi))
                zone[j] = 2 if psi < 0.12 or psi > 0.88 else 1
            else:
                zone[j] = 3
        for p, a_, kd in placed:
            j = int(np.searchsorted(sg, p))
            if kind != "meander":
                for jb in range(j, min(m, j + 5)):
                    if jb in set(jj.tolist()):
                        extra[jb] = max(extra[jb], float(e.get("plunge_pool_extra_depth", 1.0)))
                        zone[jb] = 5
            if kd == "fall" and j < m:
                zone[j] = 4
        if kind == "meander":
            th = np.unwrap(np.arctan2(tz2[jj], tx2[jj]))
            kap = np.gradient(running(th, 9, "mean"))
            km = float(np.abs(kap).max()) or 1.0
            offset[jj] = -float(pr["thalweg_shift_of_half_width"]) * hwn[jj] * np.clip(kap / km, -1, 1)
        w = rep["windows"]
        rec = next((r for r in w if r["id"] == e["id"]), None)
        if rec is None:
            rec = {"id": e["id"], "kind": "cascades", "from_m": float(cn[jj[0]]), "to_m": float(cn[jj[-1]])}
            w.append(rec)
        rec.update({"steps_placed": int(sum(p[1] for p in placed)), "falls": [p for p in placed if p[2] == "fall"],
                    "gather_points": len(gathers), "level_violations_clamped": viol,
                    "old_steps": int(Lold[jj[0]] - Lold[jj[-1]])})
        # sinuosity over the window
        new_len = float(sg[jj[-1]] - sg[jj[0]])
        old_len = float(cn[jj[-1]] - cn[jj[0]])
        chord = math.hypot(xn[jj[-1]] - xn[jj[0]], zn[jj[-1]] - zn[jj[0]])
        old_chord = chord
        rec["sinuosity"] = {"channel_over_old_channel": round(new_len / max(1.0, old_len), 3),
                            "before_over_chord": round(old_len / max(1.0, old_chord), 3),
                            "after_over_chord": round(new_len / max(1.0, chord), 3)}
    depth_eff = np.minimum(Dn * mult, Dn + 3.0) + extra
    floor = level - np.maximum(1.0, depth_eff)
    # rasterise the touched stretches
    jt = np.nonzero(touched)[0]
    rep["stations_new"] = int(m)
    rep["length_before"] = round(float(C[-1]), 1)
    rep["length_after"] = round(total, 1)
    ends = math.hypot(X[-1] - X[0], Z[-1] - Z[0])
    rep["sinuosity_course"] = {"before": round(float(C[-1]) / max(1.0, ends), 3),
                               "after": round(total / max(1.0, ends), 3)}
    rep["steps"] = steps_all
    new_rat = [GR.at_chainage(reaches, c) for c in cn]
    return {"X": X, "Z": Z, "C": C, "S": S, "width": width, "wb": wb, "xn": xn, "zn": zn, "cn": cn, "sg": sg,
            "nxn": nxn, "nzn": nzn, "level": level, "Lold": Lold, "floor": floor, "hwn": hwn, "offset": offset,
            "zone": zone, "touched": touched, "jt": jt, "rat_new": new_rat, "rep": rep}


def carve_course(ctx, k, r, course, corridor_half):
    """Write a reshaped course's stretches into the ground: fill the abandoned channel, cut the new one, hold a bank
    lip at the water's level wherever the new water would spill."""
    jt = r["jt"]
    if not len(jt):
        return 0
    xn, zn, hwn, level, floor = r["xn"], r["zn"], r["hwn"], r["level"], r["floor"]
    bank = np.array([max(0.2, r["rat_new"][j]["bank_slope"]) for j in range(len(xn))])
    Rj = hwn + 2.0 / bank + 3.0
    pad = int(Rj[jt].max()) + corridor_half + 4
    box = clip_box(min(xn[jt].min(), r["X"].min()) - pad, min(zn[jt].min(), r["Z"].min()) - pad,
                   max(xn[jt].max(), r["X"].max()) + pad + 1, max(zn[jt].max(), r["Z"].max()) + pad + 1, ctx.N)
    # the audit's footprint: the original centreline, over the touched stretches, grown by corridor_half
    cmin, cmax = r["cn"][jt].min() - 8, r["cn"][jt].max() + 8
    oi = np.nonzero((r["C"] >= cmin) & (r["C"] <= cmax))[0]
    corr = np.zeros((box[3] - box[1], box[2] - box[0]), bool)
    for i in oi[::2]:
        a0, a1 = max(0, int(r["Z"][i]) - corridor_half - box[1]), min(corr.shape[0], int(r["Z"][i]) + corridor_half + 2 - box[1])
        b0, b1 = max(0, int(r["X"][i]) - corridor_half - box[0]), min(corr.shape[1], int(r["X"][i]) + corridor_half + 2 - box[0])
        if a1 > a0 and b1 > b0:
            zz, xx = np.mgrid[a0:a1, b0:b1]
            corr[a0:a1, b0:b1] |= np.hypot(xx + box[0] - r["X"][i], zz + box[1] - r["Z"][i]) <= corridor_half
    # the new channel
    sel = jt
    stations = (xn[sel], zn[sel], r["nxn"][sel], r["nzn"][sel])
    best, idx, lat = stamp(stations, box, lambda j: float(Rj[sel[j]]))
    has = idx >= 0
    J = np.where(has, sel[np.maximum(idx, 0)], 0)
    lv = level[J].astype(float)
    fl = floor[J]
    hw = hwn[J]
    off = r["offset"][J]
    inner = has & (best <= hw)
    e_side = np.where(lat >= off, hw, -hw)
    den = np.where(np.abs(e_side - off) < 1e-6, 1e-6, e_side - off)
    tpar = np.clip((lat - off) / den, 0.0, 1.0)
    ts_in = np.minimum(fl + (lv - 1 - fl) * tpar ** 2, lv - 1)
    # the bank rises from the water's edge at the reach's bank slope; ground above that line is cut back (a cut bank
    # where a bend swings into a terrace), ground below it is left alone
    ts_out = (lv - 1) + (best - hw) * bank[J]
    target = np.floor(np.where(inner, ts_in, ts_out) + 0.5)
    cut_zone = has & (best <= hw + 2.0 / bank[J] + 1.0)
    cur = ctx.G1[sl(box)].astype(np.int32)
    new = cur.copy()
    # the old channel, where it is abandoned
    olds = np.nonzero((r["C"] >= cmin) & (r["C"] <= cmax) & ~r["wb"])[0]
    if len(olds):
        Lo = np.floor(r["S"] + 0.01).astype(int)
        ox, oz = r["X"][olds], r["Z"][olds]
        otx = np.gradient(ox)
        otz = np.gradient(oz)
        ol = np.hypot(otx, otz)
        ol[ol == 0] = 1
        ostat = (ox, oz, -otz / ol, otx / ol)
        obest, oidx, _ = stamp(ostat, box, lambda j: float(r["width"][olds[j]] / 2.0 + 0.5))
        ohas = oidx >= 0
        OJ = np.where(ohas, olds[np.maximum(oidx, 0)], 0)
        old_wet = ohas & (cur < Lo[OJ])
        fill = old_wet & ~(has & (best <= hw + 1.0))
        new = np.where(fill, np.maximum(new, Lo[OJ] + 1), new)
    new = np.where(cut_zone, np.minimum(new, target.astype(np.int32)), new)
    # bank lip: a dry column beside new water, lower than that water's level, is raised to it
    wet = inner & (new < lv)
    lvl = np.where(has, lv, -1e9)
    # the sea and the lakes are water whatever this course does: never raise a lip in them
    standing = (cur < SEA) | ctx.lake_mask[sl(box)]
    for _ in range(2):
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb_wet = np.zeros_like(wet)
            nb_lv = np.full(lv.shape, -1e9)
            a = (slice(max(0, dz), wet.shape[0] + min(0, dz)), slice(max(0, dx), wet.shape[1] + min(0, dx)))
            b = (slice(max(0, -dz), wet.shape[0] + min(0, -dz)), slice(max(0, -dx), wet.shape[1] + min(0, -dx)))
            nb_wet[a] = wet[b]
            nb_lv[a] = lvl[b]
            raise_m = nb_wet & ~wet & (new < nb_lv) & ~standing
            new = np.where(raise_m, np.maximum(new, nb_lv).astype(np.int32), new)
    mask = corr & (new != cur)
    ok = ctx.write(k, box, new.astype(np.int16), mask)
    return int(ok.sum())


def revised_record(course, r):
    rev = copy.deepcopy(course)
    sg, cn = r["sg"], r["cn"]
    rev["graded_polyline"] = [[round(float(r["xn"][j]), 2), round(float(r["zn"][j]), 2), float(r["level"][j]),
                               round(float(r["floor"][j]), 2)] for j in range(len(sg))]
    new_reaches = []
    for rc in course["reaches"]:
        q = dict(rc)
        q["from_m"] = round(float(np.interp(rc["from_m"], cn, sg)))
        q["to_m"] = round(float(np.interp(rc["to_m"], cn, sg)))
        new_reaches.append(q)
    rev["reaches"] = new_reaches
    names = {0: "as_before", 1: "pool", 2: "riffle", 3: "cascade", 4: "fall", 5: "plunge_pool"}
    zones, cur, start = [], None, 0
    for j in range(len(sg)):
        z = int(r["zone"][j])
        if z != cur:
            if cur not in (None, 0):
                zones.append({"from_m": round(float(sg[start]), 1), "to_m": round(float(sg[j - 1]), 1), "zone": names[cur]})
            cur, start = z, j
    if cur not in (None, 0):
        zones.append({"from_m": round(float(sg[start]), 1), "to_m": round(float(sg[-1]), 1), "zone": names[cur]})
    rev["water_shape"] = {"generator": "tools/water_shape.py", "windows": r["rep"]["windows"],
                          "steps": r["rep"]["steps"], "zones": zones,
                          "note": "graded_polyline is one vertex a block; surface_y is the integer water level, so "
                                  "tools/paint_maps.py's floor(surface + 0.01) paints exactly it"}
    return rev


def rivers_pass(ctx):
    import grade_rivers as GR
    spec = ctx.spec["rivers"]
    dflt = spec["defaults"]
    doc = load("rivers.json")
    entries = [dict(e, _kind="meander") for e in spec["meanders"]] + [dict(e, _kind="cascades") for e in spec["cascades"]]
    by_course = {}
    for e in entries:
        by_course.setdefault(e["course"], []).append(e)
    for cid, es in by_course.items():
        course = course_by_id(doc, cid)
        k = ctx.feature("river:" + cid, "rivers", entries=[e["id"] for e in es])
        r = reshape_course(ctx, GR, course, es, dflt, lambda e: e["_kind"])
        written = carve_course(ctx, k, r, course, int(dflt["corridor_half_width_blocks"]))
        ctx.revised_courses[cid] = revised_record(course, r)
        rep = r["rep"]
        rep["columns_written"] = written
        ctx.report["rivers"][cid] = rep
        ctx.features[k]["columns_written"] = written
        ctx.river_runs = getattr(ctx, "river_runs", {})
        ctx.river_runs[cid] = r
    for c in doc["courses"]:
        if c["id"] not in ctx.revised_courses:
            ctx.revised_courses[c["id"]] = copy.deepcopy(c)


# ---------------------------------------------------------------------------------------------------- the stream


def stream_pass(ctx):
    st = ctx.spec["viltri_ravine_stream"]
    lm = next(l for l in load("landmarks.json")["landmarks"] if l["id"] == "viltri_ravine")
    axis = next(a for a in lm["axes"] if a["id"] == "channel")["polyline"]
    px, pz = st["pass"]
    # the sea half: from the pass along the axis to its low end
    best, bi = None, 0
    for i in range(len(axis) - 1):
        (ax, az), (bx, bz) = axis[i], axis[i + 1]
        vx, vz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((px - ax) * vx + (pz - az) * vz) / max(1e-9, vx * vx + vz * vz)))
        d = math.hypot(ax + vx * t - px, az + vz * t - pz)
        if best is None or d < best:
            best, bi = d, i
    if best > 40:
        raise ShapeError("the pass (%d, %d) is %.0f blocks off the ravine's axis" % (px, pz, best))
    poly = [(px, pz)] + [tuple(p) for p in axis[bi + 1:]]
    xs, zs = [], []
    for (ax, az), (bx, bz) in zip(poly, poly[1:]):
        kk = max(1, int(math.ceil(math.hypot(bx - ax, bz - az))))
        for s in range(kk):
            xs.append(ax + (bx - ax) * s / kk)
            zs.append(az + (bz - az) * s / kk)
    xs.append(poly[-1][0])
    zs.append(poly[-1][1])
    xs, zs = np.array(xs), np.array(zs)
    step = int(st["station_step_blocks"])
    xs, zs = xs[::step], zs[::step]
    n = len(xs)
    tx, tz = np.gradient(xs), np.gradient(zs)
    tl = np.hypot(tx, tz)
    tl[tl == 0] = 1
    nx, nz = -tz / tl, tx / tl
    G = ctx.G0
    reach = int(st["thalweg_search_blocks"])
    tx_, tz_ = [], []
    for i in range(n):
        cand = []
        for d in range(-reach, reach + 1):
            x, z = int(round(xs[i] + nx[i] * d)), int(round(zs[i] + nz[i] * d))
            cand.append((int(G[z, x]), abs(d), x, z))
        cand.sort()
        tx_.append(cand[0][2])
        tz_.append(cand[0][3])
    sx = running(np.array(tx_, float), 5, "mean")
    sz = running(np.array(tz_, float), 5, "mean")
    # to the sea: steepest non-rising ground from the low end
    ext = []
    cx, cz = int(round(sx[-1])), int(round(sz[-1]))
    seen = {(cx, cz)}
    for _ in range(int(st["to_sea"]["max_extension_blocks"])):
        if G[cz, cx] < SEA and not ctx.lake_mask[cz, cx]:
            break
        opts = []
        for dz in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dz == 0:
                    continue
                x, z = cx + dx, cz + dz
                if (x, z) in seen or ctx.P[z, x]:
                    continue
                opts.append((int(G[z, x]), abs(dx) + abs(dz), x, z))
        if not opts:
            break
        opts.sort()
        if opts[0][0] > G[cz, cx] + 1:
            break
        cx, cz = opts[0][2], opts[0][3]
        seen.add((cx, cz))
        ext.append((cx, cz))
    if G[cz, cx] >= SEA:
        raise ShapeError("the Viltri Ravine stream does not reach the sea within %d blocks of the axis's low end "
                         "(stopped at (%d, %d), ground y%d)" % (st["to_sea"]["max_extension_blocks"], cx, cz, G[cz, cx]))
    ex = np.array([p[0] for p in ext], float)
    ez = np.array([p[1] for p in ext], float)
    X = np.concatenate([sx, running(ex, 5, "mean") if len(ex) else ex])
    Z = np.concatenate([sz, running(ez, 5, "mean") if len(ez) else ez])
    seg = np.hypot(np.diff(X), np.diff(Z))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    sg = np.concatenate([np.arange(0.0, s[-1], 1.0), [s[-1]]])
    xn, zn = np.interp(sg, s, X), np.interp(sg, s, Z)
    m = len(sg)
    flo = np.array([int(G[max(0, int(round(z)) - 2):int(round(z)) + 3, max(0, int(round(x)) - 2):int(round(x)) + 3].min())
                    for x, z in zip(xn, zn)], float)
    surf = np.minimum.accumulate(flo - float(st["incision_blocks"]))
    surf = np.maximum(surf, SEA)
    Lold = np.floor(surf + 0.01).astype(int)
    Lold[-1] = SEA
    Lold = np.minimum.accumulate(Lold)
    jj = np.arange(m)
    rng = rng_for("stream")
    spacing = float(st["gather_every_blocks"])
    gathers = [0.0]
    while gathers[-1] < sg[-1]:
        gathers.append(gathers[-1] + spacing * (1.0 + 0.15 * (2 * rng.random() - 1)))
    gathers = np.array(gathers)
    placed = step_plan(sg, Lold, jj, gathers, 1, st.get("falls", []), rng)
    L0 = int(Lold[0])
    pos = np.array([p[0] for p in placed]) if placed else np.zeros(0)
    amt = np.array([p[1] for p in placed]) if placed else np.zeros(0)
    level = np.array([L0 - int(amt[pos <= v].sum()) for v in sg]) if len(pos) else np.full(m, L0)
    level = np.minimum(level, Lold)
    extra = np.zeros(m)
    zone = np.full(m, 3, np.int8)
    for p, a_, kd in placed:
        j = int(np.searchsorted(sg, p))
        extra[j:j + 5] = np.maximum(extra[j:j + 5], float(st["plunge_pool_extra_depth"]))
        zone[j:j + 5] = 5
        if kd == "fall" and j < m:
            zone[j] = 4
    floor = level - np.maximum(1.0, np.minimum(float(st["max_depth_blocks"]) + extra, 1.5 + extra))
    hw = float(st["width_blocks"]) / 2.0
    ang = np.arctan2(np.gradient(zn), np.gradient(xn))
    nxn, nzn = -np.sin(ang), np.cos(ang)
    k = ctx.feature("stream:viltri_ravine", "stream")
    corridor = int(st["corridor_half_width_blocks"])
    pad = corridor + 12
    box = clip_box(xn.min() - pad, zn.min() - pad, xn.max() + pad + 1, zn.max() + pad + 1, ctx.N)
    best, idx, lat = stamp((xn, zn, nxn, nzn), box, lambda j: hw + 4.0)
    has = idx >= 0
    J = np.maximum(idx, 0)
    lv = level[J].astype(float)
    inner = has & (best <= hw)
    ts_in = np.minimum(floor[J] + (lv - 1 - floor[J]) * np.clip(best / hw, 0, 1) ** 2, lv - 1)
    ts_out = lv - 1 + (best - hw) * 2.0
    target = np.floor(np.where(inner, ts_in, ts_out) + 0.5).astype(np.int32)
    cur = ctx.G1[sl(box)].astype(np.int32)
    new = np.where(has & (best <= hw + 2.0), np.minimum(cur, target), cur)
    # the spring pool, eight blocks down the sea side of the pass
    sp = st["spring_pool"]
    j0 = min(m - 1, 8)
    zz, xx = np.mgrid[box[1]:box[3], box[0]:box[2]]
    rr = np.hypot(xx - xn[j0], zz - zn[j0])
    pool = rr <= float(sp["radius"])
    new = np.where(pool, np.minimum(new, (level[j0] - sp["depth"] + (rr / float(sp["radius"])) ** 2).astype(np.int32)), new)
    wet = (inner | pool) & (new < np.where(pool, level[j0], lv))
    lvl = np.where(pool, float(level[j0]), np.where(has, lv, -1e9))
    standing = (cur < SEA) | ctx.lake_mask[sl(box)]
    for _ in range(2):
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb_wet = np.zeros_like(wet)
            nb_lv = np.full(lv.shape, -1e9)
            a = (slice(max(0, dz), wet.shape[0] + min(0, dz)), slice(max(0, dx), wet.shape[1] + min(0, dx)))
            b = (slice(max(0, -dz), wet.shape[0] + min(0, -dz)), slice(max(0, -dx), wet.shape[1] + min(0, -dx)))
            nb_wet[a] = wet[b]
            nb_lv[a] = lvl[b]
            raise_m = nb_wet & ~wet & (new < nb_lv) & ~standing
            new = np.where(raise_m, np.maximum(new, nb_lv).astype(np.int32), new)
    ok = ctx.write(k, box, new.astype(np.int16), new != cur)
    names = {3: "cascade", 4: "fall", 5: "plunge_pool"}
    rec = {
        "id": st["course_id"], "river": "viltri_ravine", "kind": "stream", "valid": True,
        "source": {"kind": "spring", "at": [round(float(xn[j0]), 1), round(float(zn[j0]), 1)], "level_y": int(level[j0]),
                   "pool": sp},
        "ends_in": "open_sea", "end_at": {"x": int(round(xn[-1])), "z": int(round(zn[-1]))},
        "graded_polyline": [[round(float(xn[j]), 2), round(float(zn[j]), 2), float(level[j]), round(float(floor[j]), 2)]
                            for j in range(m)],
        "graded_polyline_fields": ["x", "z", "surface_y", "floor_y"],
        "reaches": [{"from_m": 0, "to_m": int(math.ceil(sg[-1])), "catchment_km2": None, "grade": None,
                     "water_body": False, "bank_slope": 2.0, "bed": st["bed"], "width": int(st["width_blocks"]),
                     "depth": float(st["max_depth_blocks"]), "incision": float(st["incision_blocks"])}],
        "water_shape": {"generator": "tools/water_shape.py", "steps": [{"s": round(p, 1), "drop": int(a), "kind": kd}
                                                                     for p, a, kd in placed],
                        "zones": [{"at_m": round(float(sg[j]), 1), "zone": names.get(int(zone[j]), "cascade")}
                                  for j in range(0, m, 10)],
                        "falls_declared": st.get("falls", [])},
    }
    ctx.revised_courses[st["course_id"]] = rec
    ctx.report["stream"] = {"length": round(float(sg[-1]), 1), "from_level": int(level[0]), "to_level": int(level[-1]),
                            "spring_at": rec["source"]["at"], "extension_to_sea_blocks": len(ext),
                            "steps": len(placed), "falls": [p for p in placed if p[2] == "fall"],
                            "columns_written": int(ok.sum())}
    ctx.stream_run = {"xn": xn, "zn": zn, "sg": sg, "level": level, "floor": floor, "flo": flo}


# ---------------------------------------------------------------------------------------------------- lakes


def lake_measure(g, L, inside, factor, exclude=None):
    wet = inside & (g < L)
    if not wet.any():
        return None
    depth = np.where(wet, L - g, 0)
    rest = ~wet | (depth <= 1)
    dist = distance_scaled(rest, wet, factor)
    obj = wet & ~(exclude if exclude is not None else np.zeros_like(wet))
    lv = []
    for a, b in (((slice(None), slice(1, None)), (slice(None), slice(None, -1))),
                 ((slice(1, None), slice(None)), (slice(None, -1), slice(None)))):
        both = wet[a] & wet[b]
        dd = np.abs(g[a].astype(int) - g[b].astype(int))[both]
        lv.append(dd)
    dd = np.concatenate(lv) if lv else np.zeros(0)
    n = max(1, dd.size)
    return {"wet_columns": int(wet.sum()), "deepest": int(depth.max()),
            "wadeable_share": round(float((depth[wet] <= 1).mean()), 3),
            "max_to_rest": round(float(dist[obj].max()), 1) if obj.any() else 0.0,
            "within_30_of_rest_share": round(float((dist[wet] <= 30).mean()), 3),
            "deep_9_plus_columns": int((depth >= 9).sum()),
            "neighbours_level_1step_steeper": [round(float((dd == 0).sum()) / n, 3), round(float((dd == 1).sum()) / n, 3),
                                               round(float((dd >= 2).sum()) / n, 3)],
            "depth_histogram": {str(b): int(((depth >= lo) & (depth <= hi) & wet).sum())
                                for b, (lo, hi) in {"1": (1, 1), "2": (2, 2), "3-5": (3, 5), "6-10": (6, 10),
                                                    "11-20": (11, 20), "21-35": (21, 35), "36+": (36, 999)}.items()}}


def keep_zone(kz, depth0, wet, anchor_zx, box_shape):
    az, ax = anchor_zx
    if "core_depth" in kz:
        return component_near(wet & (depth0 >= kz["core_depth"]), az, ax)
    zz, xx = np.mgrid[0:box_shape[0], 0:box_shape[1]]
    return np.hypot(zz - az, xx - ax) <= float(kz["radius"])


def lake_pass_one(ctx, body):
    lb = ctx.lake_bodies.get(body["id"])
    if lb is None:
        raise ShapeError("no water_body for lake %s in data/landmarks.json" % body["id"])
    lakes = ctx.spec["lakes"]
    dflt = lakes["defaults"]
    L = lb["level"]
    box = lb["box"]
    inside = lb["inside"]
    g0 = ctx.G1[sl(box)].astype(np.int32)
    H, W = g0.shape
    wet = inside & (g0 < L)
    depth0 = np.where(wet, L - g0, 0)
    prot = ctx.P[sl(box)] | (ctx.owner[sl(box)] != 0)
    editable = wet & (depth0 >= 2) & ~prot
    factor = 1 if H * W <= 400000 else (2 if H * W <= 2500000 else 4)
    anc = lb["landmark"]["anchor"]
    anchor_zx = (int(anc["z"]) - box[1], int(anc["x"]) - box[0])
    rng = rng_for("lake", body["id"])
    dshore = distance_scaled(~wet, wet, factor)
    B = 1.0 - box_mean(wet, int(dflt["bay_radius_blocks"]))
    wmin, wmax = body["shelf_width"]
    Wsh = wmin + (wmax - wmin) * np.clip((B - 0.35) / 0.30, 0.0, 1.0)
    zz, xx = np.mgrid[0:H, 0:W]
    brg = bearing_deg(xx - anchor_zx[1], zz - anchor_zx[0])
    for sec in body.get("sectors", []):
        m = in_bearing(brg, sec["bearing_from_anchor_deg"])
        a, b = sec["shelf_width"]
        Wsh = np.where(m, a + (b - a) * np.clip((B - 0.35) / 0.30, 0.0, 1.0), Wsh)
    wf = float(dflt["wade_fraction_of_shelf"])
    dd, dw = float(body["drop_depth"]), float(body["drop_width"])
    Tt = np.where(dshore <= Wsh * wf, 1.0, 2.0)
    drop = (dshore > Wsh) & (dshore <= Wsh + dw)
    Tt = np.where(drop, 2.0 + (dd - 2.0) * smoothstep((dshore - Wsh) / dw), Tt)
    floor_m = dshore > Wsh + dw
    ring = floor_m & (dshore <= Wsh + dw + 2)
    d_edge = float(np.median(depth0[ring])) if ring.any() else dd
    Dmax = float(depth0.max())
    tt = np.clip((depth0 - d_edge) / max(1.0, Dmax - d_edge), 0.0, 1.0)
    gamma = float(dflt["floor_gamma"])
    Tf = dd + (Dmax - dd) * tt ** gamma
    nz = value_noise(xx + box[0], zz + box[1], dflt["floor_noise_scale_blocks"], seed_of("lakefloor", body["id"]))
    Tf = np.maximum(dd, Tf + (nz - 0.5) * 2.0 * float(dflt["floor_noise_blocks"]))
    Tt = np.where(floor_m, Tf, Tt)
    zone = np.where(dshore <= Wsh, np.where(B > 0.6, 6, 1), np.where(drop, 2, 3)).astype(np.uint8)
    # keep zones and flattened zones
    keeps = {}
    keep_all = np.zeros((H, W), bool)
    for kz in body.get("keep", []):
        km = keep_zone(kz, depth0, wet, anchor_zx, (H, W))
        keeps[kz["id"]] = km
        keep_all |= km
    for fz in body.get("flatten", []):
        fm = keep_zone(fz, depth0, wet, anchor_zx, (H, W))
        keeps[fz["id"]] = fm
        Tt = np.where(fm, float(fz["to_depth"]), Tt)
        zone[fm] = 3
    Tt = np.where(keep_all, depth0.astype(float), Tt)
    zone[keep_all & wet] = 7
    # humps
    hs = dflt["hump"]
    placed_h = []
    cand = np.argwhere(floor_m & editable & ~keep_all)
    if len(cand) and body.get("humps", 0):
        order = list(range(len(cand)))
        rng.shuffle(order)
        kd = distance_scaled(keep_all, None, factor) if keep_all.any() else np.full((H, W), 1e9, np.float32)
        for i in order:
            z, x = cand[i]
            if kd[z, x] < 20 or any(math.hypot(z - a, x - b) < hs["min_spacing_blocks"] for a, b, _, _ in placed_h):
                continue
            r = rng.uniform(*hs["radius"])
            top = rng.uniform(*hs["top_depth"])
            placed_h.append((int(z), int(x), r, top))
            if len(placed_h) >= int(body["humps"]):
                break
    for z, x, r, top in placed_h:
        d = np.hypot(zz - z, xx - x)
        mound = top + (Tt - top) * (d / r) ** 2
        m = (d <= r) & ~keep_all
        zone[m & (mound < Tt)] = 4
        Tt = np.where(m, np.minimum(Tt, mound), Tt)
    sh_h = body.get("shelf_humps")
    placed_sh = []
    if sh_h:
        cands = np.argwhere(editable & ~keep_all & (dshore >= Wsh * 0.5) & (dshore <= Wsh + dw))
        order = list(range(len(cands)))
        rng.shuffle(order)
        for i in order:
            z, x = cands[i]
            if any(math.hypot(z - a, x - b) < 24 for a, b, _ in placed_sh):
                continue
            placed_sh.append((int(z), int(x), rng.uniform(*sh_h["radius"])))
            if len(placed_sh) >= int(sh_h["count"]):
                break
        for z, x, r in placed_sh:
            d = np.hypot(zz - z, xx - x)
            m = (d <= r * 2.0) & ~keep_all
            v = float(sh_h["top_depth"]) + np.maximum(0.0, d - r) / 1.5
            zone[m & (d <= r)] = 5
            Tt = np.where(m, np.minimum(Tt, v), Tt)
    # shoals: the declared ones first, then enough to bring every point within the rung's budget
    sd = dflt["shoal"]
    shoals = []

    def put_shoal(z, x, why):
        rc = float(sd["crest_radius"])
        fr = float(sd["flank_run_per_block"])
        d = np.hypot(zz - z, xx - x)
        v = np.where(d <= rc, 1.0, 1.0 + (d - rc) / fr)
        m = ~keep_all & (v < Tt)
        zone[m & (d <= rc)] = 5
        return np.where(m, v, Tt), {"at": [int(x) + box[0], int(z) + box[1]], "why": why}

    excl = np.zeros((H, W), bool)
    for kid in body.get("max_to_rest_excludes", []):
        excl |= keeps.get(kid, np.zeros((H, W), bool))
    for s in body.get("shoals", []):
        if s["kind"] != "near":
            continue
        if s["target"] == "anchor":
            dist_t = np.hypot(zz - anchor_zx[0], xx - anchor_zx[1])
            lo, hi = s["distance"]
        else:
            km = keeps.get(s["target"])
            if km is None or not km.any():
                raise ShapeError("%s: shoal target %s is not a declared zone" % (body["id"], s["target"]))
            dist_t = distance_scaled(km, None, factor)
            lo, hi = s["distance_from_edge"]
        ok = editable & ~keep_all & (dist_t >= lo) & (dist_t <= hi)
        if not ok.any():
            ctx.report["notes"].append("%s: no room for the shoal near %s at %s-%s blocks" % (body["id"], s["target"], lo, hi))
            continue
        zs_, xs_ = np.nonzero(ok)
        i = int(np.argmin(dshore[zs_, xs_]))
        Tt, rec = put_shoal(zs_[i], xs_[i], s.get("why", "near %s" % s["target"]))
        shoals.append(rec)
    rung = lakes["rungs"][body["rung"]]
    target = float(rung["max_to_rest_blocks"])
    auto = any(s["kind"] == "auto" for s in body.get("shoals", []))
    for _ in range(int(sd["max_count"])):
        if not auto:
            break
        rest = ~wet | (Tt <= 1.0)
        dist = distance_scaled(rest, wet, max(2, factor))
        obj = wet & ~excl
        if not obj.any() or float(dist[obj].max()) <= target:
            break
        vals = np.where(obj, dist, -1.0)
        z, x = np.unravel_index(int(np.argmax(vals)), vals.shape)
        if not (editable[z, x] and not keep_all[z, x]):
            okm = editable & ~keep_all
            if not okm.any():
                break
            zs_, xs_ = np.nonzero(okm)
            i = int(np.argmin((zs_ - z) ** 2 + (xs_ - x) ** 2))
            z, x = zs_[i], xs_[i]
        Tt, rec = put_shoal(z, x, "rest point: the farthest water from anywhere to stand was %.0f blocks" % dist[obj].max())
        shoals.append(rec)
    Ti = np.clip(np.rint(Tt), 1, None).astype(np.int32)
    new = np.where(editable, L - Ti, g0)
    new = np.minimum(new, np.where(wet, L - 1, new))
    k = ctx.feature("lake:" + body["id"], "lakes")
    before = lake_measure(g0, L, inside, factor)
    ok = ctx.write(k, box, new.astype(np.int16), editable)
    g1 = ctx.G1[sl(box)].astype(np.int32)
    after = lake_measure(g1, L, inside, factor, exclude=excl)
    dv = g1 - g0
    zone[~wet] = 0
    ctx.zone_maps["lake_" + body["id"]] = {"box": box, "zones": zone}
    ctx.report["lakes"][body["id"]] = {
        "level": L, "rung": body["rung"], "stage": body["stage"], "box": list(box),
        "before": before, "after": after,
        "targets": {"max_to_rest": target, "wadeable": body["wadeable_target"],
                    "deep_area_min_share": dflt["deep_area_min_share"]},
        "shoals": shoals, "humps": [{"at": [x + box[0], z + box[1]], "radius": round(r, 1), "top_depth": round(t, 1)}
                                    for z, x, r, t in placed_h],
        "shelf_humps": [{"at": [x + box[0], z + box[1]], "radius": round(r, 1)} for z, x, r in placed_sh],
        "keep": {kid: int(m.sum()) for kid, m in keeps.items()},
        "columns_written": int(ok.sum()), "fill_blocks": int(dv[dv > 0].sum()), "cut_blocks": int(-dv[dv < 0].sum()),
        "held_protected": ctx.features[k]["held_protected"], "floor_edge_depth": round(d_edge, 1),
    }
    ctx.features[k]["columns_written"] = int(ok.sum())


def lakes_pass(ctx):
    for body in ctx.spec["lakes"]["bodies"]:
        t0 = time.time()
        lake_pass_one(ctx, body)
        print("  lake %-22s %6.1f s" % (body["id"], time.time() - t0), flush=True)


# ---------------------------------------------------------------------------------------------------- coasts


def gate_mask(ctx, box, clearance):
    lines = [[a, b] for a, b in gate_lines(ctx)]
    return raster_lines(lines, box, 2 * clearance + 1)


def relic_corridor_mask(ctx, box):
    rc = ctx.spec["coasts"]["relic_corridors"]
    return raster_lines(rc["lines"], box, 2 * rc["half_width_blocks"] + 1)


def reef_footprint(spec, box):
    rf = spec["coasts"]["relic_reef"]
    cx, cz = rf["centre"]
    x0, z0, x1, z1 = box
    zz, xx = np.mgrid[z0:z1, x0:x1]
    r = np.hypot(xx - cx, zz - cz)
    b = bearing_deg(xx - cx, zz - cz)
    return in_bearing(b, rf["sector_bearing_deg"]) & (r >= rf["inner_radius"] - 2) & \
        (r <= rf["outer_radius"][1] + rf["drop_width_blocks"] + 6)


def fungal_corridor_mask(ctx, box):
    fb = ctx.spec["coasts"]["fungal_bar_chain"]
    a, b = ctx.fungal_line
    return raster_lines([[a, b]], box, 2 * fb["corridor_half_width_blocks"] + 1)


def hole_mask(spec, box):
    h = spec["coasts"]["first_cast_hole"]
    x0, z0, x1, z1 = box
    zz, xx = np.mgrid[z0:z1, x0:x1]
    return np.hypot(xx - h["centre"][0], zz - h["centre"][1]) <= h["radius"] + 2


def sea_in_box(ctx, box):
    g = ctx.G0[sl(box)]
    return (g < SEA) & ~ctx.lake_mask[sl(box)]


def flats_pass(ctx, f):
    N = ctx.N
    x0, z0, x1, z1 = f["box"]
    pad = f["band_blocks"] + 16
    box = clip_box(x0 - pad, z0 - pad, x1 + pad + 1, z1 + pad + 1, N)
    g = ctx.G1[sl(box)].astype(np.int32)
    sea = sea_in_box(ctx, box)
    land = ~sea & (g >= SEA)
    if f.get("shore_region"):
        rb, rm = ctx.region_mask(f["shore_region"], 24)
        shore_src = np.zeros(g.shape, bool)
        a0, a1 = max(box[1], rb[1]), min(box[3], rb[3])
        b0, b1 = max(box[0], rb[0]), min(box[2], rb[2])
        if a1 > a0 and b1 > b0:
            shore_src[a0 - box[1]:a1 - box[1], b0 - box[0]:b1 - box[0]] = rm[a0 - rb[1]:a1 - rb[1], b0 - rb[0]:b1 - rb[0]]
        shore_src &= land
    else:
        shore_src = land
    dl = distance(shore_src, sea, max_iter=f["band_blocks"] + 20)
    H, W = g.shape
    zz, xx = np.mgrid[box[1]:box[3], box[0]:box[2]]
    inbox = (xx >= x0) & (xx <= x1) & (zz >= z0) & (zz <= z1)
    depth0 = SEA - g
    zone = sea & inbox & (dl <= f["band_blocks"]) & (depth0 <= 4)
    ex = np.zeros((H, W), bool)
    for e in f.get("exclude", []):
        if e == "relic_corridors":
            ex |= relic_corridor_mask(ctx, box)
        elif e == "relic_reef":
            ex |= reef_footprint(ctx.spec, box)
        elif e == "fungal_bar_chain":
            ex |= fungal_corridor_mask(ctx, box)
        elif e == "first_cast_hole":
            ex |= hole_mask(ctx.spec, box)
    ex |= gate_mask(ctx, box, ctx.spec["coasts"]["gate_line_clearance_blocks"])
    zone &= ~ex
    bars = f["bars"]
    sig = float(bars["sigma_blocks"])
    bump = np.zeros((H, W))
    for o in bars["offsets_blocks"]:
        bump = np.maximum(bump, np.exp(-((dl - o) / sig) ** 2))
    crest, runnel = float(bars["crest_depth"]), float(bars["runnel_depth"])
    Tt = runnel - (runnel - crest) * bump
    seed = seed_of("flats", f["id"])
    sp = float(np.mean(bars["rip_every_blocks"]))
    nu = value_noise(xx, zz, sp, seed)
    rip = np.abs(nu - 0.5) < (bars["rip_width_blocks"] / (2.0 * sp)) * 1.5
    Tt = np.where(rip & (dl > bars["offsets_blocks"][0] - 2 * sig), float(bars["rip_depth"]), Tt)
    dry = (value_noise(xx, zz, 40.0, seed + 1) > bars["dry_crest_noise_over"]) & (bump > 0.85) & ~rip
    Tt = np.where(dry, 0.0, Tt)
    inner = dl < bars["offsets_blocks"][0] - 2 * sig
    Tt = np.where(inner, np.minimum(depth0, Tt), Tt)
    outer_edge = bars["offsets_blocks"][-1] + 2 * sig
    blend = np.clip((dl - outer_edge) / 8.0, 0.0, 1.0)
    Tt = Tt * (1 - blend) + depth0 * blend
    lag = f.get("lagoon")
    lag_rep = None
    if lag:
        Tt, lag_rep = lagoon(ctx, f, lag, box, dl, sea, inbox & ~ex, depth0, Tt, xx, zz, seed, shore_src)
        zone |= lag_rep.pop("_mask")
    new = np.clip(np.rint(SEA - Tt).astype(np.int32), g - 2, g + 3)
    if lag_rep:
        new = np.where(lag_rep["_barrier"], np.maximum(new, SEA - np.rint(Tt).astype(np.int32)), new)
        lag_rep.pop("_barrier")
    k = ctx.feature("coast:" + f["id"], "coasts")
    ok = ctx.write(k, box, new.astype(np.int16), zone)
    g1 = ctx.G1[sl(box)].astype(np.int32)
    wet0 = zone & (depth0 >= 1)
    rep = {"box": f["box"], "columns_written": int(ok.sum()),
           "wadeable_share_in_band": {"before": round(float((depth0[zone] <= 1).mean()), 3) if zone.any() else None,
                                      "after": round(float(((SEA - g1)[zone] <= 1).mean()), 3) if zone.any() else None},
           "new_dry_columns": int((ok & (g1 >= SEA) & (g < SEA)).sum()),
           "fill_blocks": int((g1 - g)[ok & (g1 > g)].sum()), "cut_blocks": int((g - g1)[ok & (g1 < g)].sum()),
           "held_protected": ctx.features[k]["held_protected"], "wet_columns_in_band": int(wet0.sum())}
    if lag_rep:
        rep["lagoon"] = lag_rep
    ctx.report["coasts"][f["id"]] = rep
    ctx.features[k]["columns_written"] = int(ok.sum())


def lagoon(ctx, f, lag, box, dl, sea, allowed, depth0, Tt, xx, zz, seed, shore_src):
    flats = sea & allowed & (dl <= 64) & (depth0 <= 2)
    shore = allowed & shore_src & dilate4(sea)
    zs, xs = np.nonzero(shore)
    if not len(zs):
        raise ShapeError("%s: no mainland shore in its box for the lagoon" % f["id"])
    half = lag["length_blocks"] / 2.0
    fz, fx = np.nonzero(flats)
    best, bc = -1, None
    for i in range(0, len(zs), 40):
        c = int(((fz - zs[i]) ** 2 + (fx - xs[i]) ** 2 <= half * half).sum())
        if c > best:
            best, bc = c, (int(zs[i]), int(xs[i]))
    cz, cx = bc
    H, W = dl.shape
    gz, gx = np.mgrid[0:H, 0:W]
    rr = np.hypot(gz - cz, gx - cx)
    near = sea & allowed & (rr <= half)
    lo, hi = lag["barrier_offset_blocks"]
    off = lo + (hi - lo) * value_noise(xx, zz, 90.0, seed + 7)
    width = float(lag["barrier_width_blocks"])
    barrier = near & (dl >= off) & (dl <= off + width)
    lagm = near & (dl < off)
    taper = np.clip(1.0 - rr / half, 0.0, 1.0)
    crest_depth = -(lag["barrier_crest_y"] - SEA) * np.clip(taper * 3.0, 0.0, 1.0) + 1.0 * (1 - np.clip(taper * 3.0, 0.0, 1.0))
    Tt = np.where(barrier, crest_depth, Tt)
    ldep = np.where(value_noise(xx, zz, 30.0, seed + 9) > 0.5, float(lag["lagoon_depth"][1]), float(lag["lagoon_depth"][0]))
    Tt = np.where(lagm, ldep, Tt)
    if barrier.any():
        bz, bx = np.nonzero(barrier)
        i = int(np.argmin((bz - cz) ** 2 + (bx - cx) ** 2))
        inlet = barrier & (np.hypot(gz - bz[i], gx - bx[i]) <= lag["inlet_width_blocks"] / 2.0 + 0.5)
        inlet = grow(inlet, 3) & (barrier | lagm | (near & (dl <= off + width + 6)))
        Tt = np.where(inlet, float(lag["inlet_depth"]), Tt)
        inlet_at = [int(bx[i]) + box[0], int(bz[i]) + box[1]]
    else:
        inlet = np.zeros_like(barrier)
        inlet_at = None
    return Tt, {"centre_shore": [cx + box[0], cz + box[1]], "barrier_columns": int(barrier.sum()),
                "lagoon_columns": int(lagm.sum()), "inlet_at": inlet_at,
                "_mask": barrier | lagm | inlet, "_barrier": barrier & ~inlet}


def fungal_pass(ctx):
    fb = ctx.spec["coasts"]["fungal_bar_chain"]
    S = fatigue_constants()
    a, b = ctx.fungal_line
    cells, step = line_cells(a, b)
    L = len(cells)
    ux, uz = (b[0] - a[0]) / math.dist(a, b), (b[1] - a[1]) / math.dist(a, b)
    vx, vz = -uz, ux
    half = int(fb["corridor_half_width_blocks"])
    box = clip_box(min(a[0], b[0]) - half - 40, min(a[1], b[1]) - half - 40, max(a[0], b[0]) + half + 41,
                   max(a[1], b[1]) + half + 41, ctx.N)
    zz, xx = np.mgrid[box[1]:box[3], box[0]:box[2]]
    U = (xx - a[0]) * ux + (zz - a[1]) * uz
    V = (xx - a[0]) * vx + (zz - a[1]) * vz
    g0 = ctx.G1[sl(box)].astype(np.int32)
    sea = sea_in_box(ctx, box)
    corridor = fungal_corridor_mask(ctx, box)
    depth_line = [SEA - int(ctx.G1[z, x]) for x, z in cells]
    wet = [i for i, d in enumerate(depth_line) if d > 1]
    if not wet:
        raise ShapeError("the Fungal line has no water")
    s0, s1 = wet[0] * step, wet[-1] * step
    Lw = s1 - s0
    rng = rng_for("fungal")
    lo_l, hi_l = fb["bar_length_blocks"]
    lo_w, hi_w = fb["bar_width_blocks"]
    maxrun = float(fb["max_deep_run_blocks"])
    fr = float(fb["flank_run_per_block"])
    nb = max(1, int(math.ceil(Lw / (maxrun + (lo_l + hi_l) / 2.0))))
    result = None
    for attempt in range(12):
        bars = []
        Tt = np.full(g0.shape, 99.0)
        for i in range(nb):
            c = s0 + (i + 0.5) * Lw / nb
            ln = rng.uniform(lo_l, hi_l)
            wd = rng.uniform(lo_w, hi_w)
            off = fb["stagger_blocks"] * (1 if i % 2 else -1)
            du = np.abs(U - c) - ln / 2.0 * 0.7
            dv = np.abs(V - off) - wd / 2.0 * 0.7
            out = np.hypot(np.maximum(du, 0), np.maximum(dv, 0))
            v = np.where((du <= 0) & (dv <= 0), float(fb["crest_depth"]), float(fb["crest_depth"]) + out / fr)
            Tt = np.minimum(Tt, v)
            bars.append({"centre_along": round(c, 1), "length": round(ln, 1), "width": round(wd, 1), "offset": off,
                         "at": [round(a[0] + ux * c + vx * off), round(a[1] + uz * c + vz * off)]})
        depth0 = SEA - g0
        want = sea & corridor & (Tt < depth0)
        new = np.where(want, SEA - np.rint(Tt).astype(np.int32), g0)
        prof = []
        for x, z in cells:
            zi, xi = z - box[1], x - box[0]
            prof.append(SEA - int(new[zi, xi]) if 0 <= zi < new.shape[0] and 0 <= xi < new.shape[1] else SEA - int(ctx.G1[z, x]))
        w2 = [i for i, d in enumerate(prof) if d > 1]
        d = prof[w2[0]:w2[-1] + 1] if w2 else []
        run, mx = 0, 0
        for v in d:
            run = run + 1 if v >= 3 else 0
            mx = max(mx, run)
        hits, peak, _ = walk(d, step, 0, S) if d else ([], 0, [])
        ok_walk = not hits and peak >= S["warn_ticks"]
        result = (new, want, bars, mx * step, hits, peak)
        if mx * step <= maxrun and not hits:
            break
        nb += 1
    new, want, bars, mx, hits, peak = result
    k = ctx.feature("coast:fungal_bar_chain", "coasts")
    ok = ctx.write(k, box, new.astype(np.int16), want)
    g1 = ctx.G1[sl(box)].astype(np.int32)
    ctx.report["coasts"]["fungal_bar_chain"] = {
        "line": [list(a), list(b)], "bars": bars, "bar_count": len(bars), "max_deep_run_planned": round(mx, 1),
        "unaided_walk_planned": outcome(hits), "unaided_peak_planned": round(peak), "peak_word": peak_word(peak, S),
        "columns_written": int(ok.sum()), "fill_blocks": int((g1 - g0)[ok].sum()),
        "held_protected": ctx.features[k]["held_protected"],
        "note": "the walk here is the generator's own planning check; the audit re-walks the line on the written copy"}
    ctx.features[k]["columns_written"] = int(ok.sum())


def reef_pass(ctx):
    rf = ctx.spec["coasts"]["relic_reef"]
    cx, cz = rf["centre"]
    R = rf["outer_radius"][1] + rf["drop_width_blocks"] + 8
    box = clip_box(cx - R, cz - R, cx + R + 1, cz + R + 1, ctx.N)
    zz, xx = np.mgrid[box[1]:box[3], box[0]:box[2]]
    r = np.hypot(xx - cx, zz - cz)
    b = bearing_deg(xx - cx, zz - cz)
    lo, hi = rf["sector_bearing_deg"]
    span = (hi - lo) % 360
    rel = ((b - lo) % 360) / max(1.0, span)
    in_sec = in_bearing(b, rf["sector_bearing_deg"])
    edge = np.clip(np.minimum(rel, 1 - rel) * span / 20.0, 0.0, 1.0)
    nzv = value_noise(xx, zz, 36.0, seed_of("reef"))
    ro = rf["outer_radius"][0] + (rf["outer_radius"][1] - rf["outer_radius"][0]) * nzv
    ri = float(rf["inner_radius"])
    ro = ri + (ro - ri) * smoothstep(edge)
    g0 = ctx.G1[sl(box)].astype(np.int32)
    depth0 = SEA - g0
    sea = sea_in_box(ctx, box)
    plat = in_sec & (r >= ri) & (r <= ro)
    t = np.clip((r - ri) / np.maximum(1.0, ro - ri), 0, 1)
    Tt = np.where(plat, rf["top_depth_inner"] + (rf["top_depth_outer"] - rf["top_depth_inner"]) * t, 99.0)
    dw = float(rf["drop_width_blocks"])
    wall = in_sec & (r > ro) & (r <= ro + dw)
    Tt = np.where(wall, rf["top_depth_outer"] + (depth0 - rf["top_depth_outer"]) * np.clip((r - ro) / dw, 0, 1), Tt)
    rng = rng_for("reef")
    knolls = []
    zs, xs = np.nonzero(plat & sea)
    for _ in range(int(rf["knolls"]["count"]) * 20):
        if len(knolls) >= rf["knolls"]["count"] or not len(zs):
            break
        i = rng.randrange(len(zs))
        z, x = int(zs[i]), int(xs[i])
        if any(math.hypot(z - a, x - b_) < 16 for a, b_, _ in knolls):
            continue
        knolls.append((z, x, rng.uniform(*rf["knolls"]["radius"])))
    gz, gx = np.mgrid[0:g0.shape[0], 0:g0.shape[1]]
    for z, x, rk in knolls:
        d = np.hypot(gz - z, gx - x)
        Tt = np.where(plat & (d <= rk * 2), np.minimum(Tt, rf["knolls"]["top_depth"] + np.maximum(0, d - rk) / 1.0), Tt)
    Tt = np.maximum(Tt, float(rf["min_depth"]))
    want = sea & (plat | wall) & (Tt < depth0) & (depth0 >= rf["min_depth"])
    new = np.where(want, SEA - np.rint(Tt).astype(np.int32), g0)
    k = ctx.feature("coast:relic_reef", "coasts")
    ok = ctx.write(k, box, new.astype(np.int16), want)
    g1 = ctx.G1[sl(box)].astype(np.int32)
    ctx.report["coasts"]["relic_reef"] = {
        "platform_columns": int((plat & sea).sum()), "columns_written": int(ok.sum()),
        "fill_blocks": int((g1 - g0)[ok].sum()), "shallowest_depth_after": int((SEA - g1)[ok].min()) if ok.any() else None,
        "knolls": [{"at": [x + box[0], z + box[1]], "radius": round(rk, 1)} for z, x, rk in knolls],
        "held_protected": ctx.features[k]["held_protected"]}
    ctx.features[k]["columns_written"] = int(ok.sum())


def skerry_pass(ctx, sk):
    x0, z0, x1, z1 = sk["box"]
    box = clip_box(x0 - 120, z0 - 120, x1 + 121, z1 + 121, ctx.N)
    g0 = ctx.G1[sl(box)].astype(np.int32)
    sea = sea_in_box(ctx, box)
    land = ~sea & (g0 >= SEA)
    dl = distance(land, sea, max_iter=140)
    zz, xx = np.mgrid[box[1]:box[3], box[0]:box[2]]
    inbox = (xx >= x0) & (xx <= x1) & (zz >= z0) & (zz <= z1)
    depth0 = SEA - g0
    ex = gate_mask(ctx, box, ctx.spec["coasts"]["gate_line_clearance_blocks"]) | ctx.P[sl(box)] | \
        (ctx.owner[sl(box)] != 0)
    ok_c = sea & inbox & ~ex & (depth0 >= sk["water_depth"][0]) & (depth0 <= sk["water_depth"][1]) & \
        (dl >= sk["distance_from_land"][0]) & (dl <= sk["distance_from_land"][1])
    cz, cx = np.nonzero(ok_c)
    sel = np.arange(0, len(cz), 3)
    rng = rng_for("skerries", sk["id"])
    order = list(sel)
    rng.shuffle(order)
    chosen = []
    want = [("stack", sk["stacks"])] * int(sk["stacks"]["count"]) + [("skerry", sk["skerries"])] * int(sk["skerries"]["count"])
    wi = 0
    for i in order:
        if wi >= len(want):
            break
        z, x = int(cz[i]), int(cx[i])
        if any(math.hypot(z - a, x - b) < sk["min_spacing_blocks"] for a, b, _, _ in chosen):
            continue
        kind, p = want[wi]
        chosen.append((z, x, kind, p))
        wi += 1
    gz, gx = np.mgrid[0:g0.shape[0], 0:g0.shape[1]]
    prof = np.full(g0.shape, -999.0)
    recs = []
    for z, x, kind, p in chosen:
        d = np.hypot(gz - z, gx - x)
        ang = np.arctan2(gz - z, gx - x)
        nz_ = value_noise(np.cos(ang) * 3 + x, np.sin(ang) * 3 + z, 1.5, seed_of("skerry", x, z))
        r = rng.uniform(*p["radius"]) * (0.8 + 0.4 * nz_)
        top = rng.uniform(*p["top_y"])
        if kind == "skerry":
            plat = r * 0.6
            v = top - np.maximum(0.0, d - plat) / float(p["flank_run_per_block"])
        else:
            plat = rng.uniform(*p["plateau_radius"])
            body = top - np.maximum(0.0, d - plat) / float(p["flank_run_per_block"])
            body = np.where(d <= r, body, -999.0)
            skirt_top = rng.uniform(*p["skirt_top_y"])
            skirt = skirt_top - np.maximum(0.0, d - (r + p["skirt_radius_extra"])) / 1.5
            v = np.maximum(body, skirt)
        prof = np.maximum(prof, v)
        recs.append({"kind": kind, "at": [x + box[0], z + box[1]], "top_y": round(float(top), 1),
                     "radius": round(float(np.mean(r)), 1), "water_depth": int(depth0[z, x])})
    want_m = sea & (prof > g0) & ~ex & inbox
    new = np.where(want_m, np.rint(prof).astype(np.int32), g0)
    k = ctx.feature("coast:" + sk["id"], "coasts")
    ok = ctx.write(k, box, new.astype(np.int16), want_m)
    g1 = ctx.G1[sl(box)].astype(np.int32)
    ctx.report["coasts"][sk["id"]] = {"placed": recs, "columns_written": int(ok.sum()),
                                      "new_land_columns": int((ok & (g1 >= SEA)).sum()),
                                      "fill_blocks": int((g1 - g0)[ok].sum()),
                                      "held_protected": ctx.features[k]["held_protected"],
                                      "candidates": int(ok_c.sum())}
    ctx.features[k]["columns_written"] = int(ok.sum())


def hole_pass(ctx):
    h = ctx.spec["coasts"]["first_cast_hole"]
    cx, cz = h["centre"]
    r = float(h["radius"])
    box = clip_box(cx - r - 2, cz - r - 2, cx + r + 3, cz + r + 3, ctx.N)
    zz, xx = np.mgrid[box[1]:box[3], box[0]:box[2]]
    d = np.hypot(xx - cx, zz - cz)
    g0 = ctx.G1[sl(box)].astype(np.int32)
    sea = sea_in_box(ctx, box)
    tgt = SEA - (h["depth"] - (d / r) ** 2 * (h["depth"] - 2))
    want = sea & (d <= r) & (np.rint(tgt) < g0)
    new = np.where(want, np.rint(tgt).astype(np.int32), g0)
    k = ctx.feature("coast:first_cast_hole", "coasts")
    ok = ctx.write(k, box, new.astype(np.int16), want)
    ctx.report["coasts"]["first_cast_hole"] = {"columns_written": int(ok.sum()), "status": h["status"],
                                              "held_protected": ctx.features[k]["held_protected"]}
    ctx.features[k]["columns_written"] = int(ok.sum())


def coasts_pass(ctx):
    c = ctx.spec["coasts"]
    fb = c["fungal_bar_chain"]
    t0 = time.time()
    fungal_pass(ctx)
    reef_pass(ctx)
    hole_pass(ctx)
    for f in c["flats"]:
        flats_pass(ctx, f)
    for sk in c["skerries"]:
        skerry_pass(ctx, sk)
    print("  coasts %.1f s" % (time.time() - t0), flush=True)
    return fb


# ---------------------------------------------------------------------------------------------------- seabed


def flood_border(below):
    n0, n1 = below.shape
    sea = np.zeros_like(below)
    stack = [(z, x) for z in range(n0) for x in (0, n1 - 1) if below[z, x]] + \
            [(z, x) for x in range(n1) for z in (0, n0 - 1) if below[z, x]]
    for z, x in stack:
        sea[z, x] = True
    while stack:
        z, x = stack.pop()
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = z + dz, x + dx
            if 0 <= a < n0 and 0 <= b < n1 and below[a, b] and not sea[a, b]:
                sea[a, b] = True
                stack.append((a, b))
    return sea


def upsample_bilinear(c, f, z0, z1, N):
    """Rows z0..z1 of a coarse grid (cell f, value at cell centres) upsampled to full resolution."""
    h, w = c.shape
    zc = (np.arange(z0, z1) + 0.5) / f - 0.5
    xc = (np.arange(N) + 0.5) / f - 0.5
    iz = np.clip(np.floor(zc).astype(int), 0, h - 2)
    ix = np.clip(np.floor(xc).astype(int), 0, w - 2)
    tz = np.clip(zc - iz, 0, 1)[:, None]
    tx = np.clip(xc - ix, 0, 1)[None, :]
    a = c[iz][:, ix]
    b = c[iz][:, ix + 1]
    cc = c[iz + 1][:, ix]
    d = c[iz + 1][:, ix + 1]
    return (a * (1 - tx) + b * tx) * (1 - tz) + (cc * (1 - tx) + d * tx) * tz


def seabed_profile(dl, z):
    after = z["_after"]
    s0, s1, W = float(z["shelf_start_y"]), float(z["shelf_end_y"]), float(z["shelf_width"])
    y = np.where(dl <= W, s0 + (s1 - s0) * dl / W, 0.0)
    d = dl - W
    bw, sw, bb = float(after["break_width"]), float(after["slope_width"]), float(after["basin_width"])
    y = np.where((dl > W) & (d <= bw), s1 + (after["break_to_y"] - s1) * d / bw, y)
    d2 = d - bw
    y = np.where((d > bw) & (d2 <= sw), after["break_to_y"] + (after["slope_to_y"] - after["break_to_y"]) * d2 / sw, y)
    d3 = d2 - sw
    y = np.where((d2 > sw) & (d3 <= bb), after["slope_to_y"] + (after["basin_to_y"] - after["slope_to_y"]) * d3 / bb, y)
    y = np.where(d3 > bb, float(after["then"]), y)
    return y


def seabed_pass(ctx):
    sb = ctx.spec["seabed"]
    N = ctx.N
    f = int(sb["coarse_cell_blocks"])
    n = N // f
    t0 = time.time()
    G0 = ctx.G0
    cmax = G0[:n * f, :n * f].reshape(n, f, n, f).max(axis=(1, 3))
    land_c = cmax >= SEA
    lake_c = ctx.lake_mask[:n * f, :n * f].reshape(n, f, n, f).any(axis=(1, 3))
    sea_c = flood_border(~land_c & ~lake_c)
    dl_c = distance(land_c, ~land_c) * f
    print("  seabed: coarse sea and distance %.1f s" % (time.time() - t0), flush=True)
    # zones and their blend
    zones = []
    wsum = np.zeros((n, n))
    ysum = np.zeros((n, n))
    rb = int(sb["zone_blend_blocks"]) // f
    for z in sb["zones"]:
        zz = dict(z)
        zz["_after"] = sb["profile_after_shelf"]
        reg = ctx.region(z["region"])
        rings = reg.get("polygons") or []
        m = raster_polygons([[(p[0] / f, p[1] / f) for p in ring] for ring in rings], (0, 0, n, n)).astype(float)
        w = box_mean(m, rb)
        y = seabed_profile(dl_c, zz)
        wsum += w
        ysum += w * y
        zones.append((z["region"], m > 0.5))
    Pc = np.where(wsum > 1e-6, ysum / np.maximum(wsum, 1e-6), np.nan)
    # ridges, on the coarse grid
    ridge_rep = []
    for rd in sb.get("ridges", []):
        zmask = next((m for r, m in zones if r == rd["zone"]), None)
        if zmask is None:
            continue
        cz, cx = np.mgrid[0:n, 0:n]
        nzv = value_noise(cx * f, cz * f, rd["gap_noise_scale_blocks"], seed_of("ridge", rd["id"]))
        gap = nzv < rd["gap_noise_under"]
        hgt = rd["rise_blocks"][0] + (rd["rise_blocks"][1] - rd["rise_blocks"][0]) * value_noise(cx * f, cz * f, 90.0, seed_of("ridgeh", rd["id"]))
        if "polyline" in rd:
            line = raster_lines([[(p[0] / f, p[1] / f) for p in rd["polyline"]]], (0, 0, n, n), max(1.0, rd["width_blocks"] / f))
            dist_c = distance(line, None, max_iter=int(rd["width_blocks"] / f) + 2) * f
            prof = np.clip(1.0 - dist_c / (rd["width_blocks"] / 2.0), 0, 1)
        else:
            W = next(z["shelf_width"] for z in sb["zones"] if z["region"] == rd["zone"])
            at = W + 40
            prof = np.clip(1.0 - np.abs(dl_c - at) / (rd["width_blocks"] / 2.0), 0, 1)
        prof = smoothstep(prof)
        raise_c = np.where(zmask & ~gap & sea_c, prof * hgt, 0.0)
        Pc = np.where(raise_c > 0, np.maximum(Pc, np.minimum(Pc + raise_c, float(rd["crest_cap_y"]))), Pc)
        ridge_rep.append({"id": rd["id"], "coarse_cells_raised": int((raise_c > 0.5).sum())})
    # exclusions, with a feather
    ex_c = np.zeros((n, n), bool)
    ex_rep = {}
    for e in sb["exclude"]:
        if "box" in e:
            x0, z0, x1, z1 = e["box"]
            m = np.zeros((n, n), bool)
            m[max(0, z0 // f):min(n, z1 // f + 1), max(0, x0 // f):min(n, x1 // f + 1)] = True
        elif e["id"] == "coast_features":
            m = np.zeros((n, n), bool)
            g = int(e.get("grow_blocks", 0))
            boxes = [fl["box"] for fl in ctx.spec["coasts"]["flats"]] + [s["box"] for s in ctx.spec["coasts"]["skerries"]]
            rf = ctx.spec["coasts"]["relic_reef"]
            R = rf["outer_radius"][1] + rf["drop_width_blocks"]
            boxes.append([rf["centre"][0] - R, rf["centre"][1] - R, rf["centre"][0] + R, rf["centre"][1] + R])
            if getattr(ctx, "fungal_line", None):
                (ax, az), (bx, bz) = ctx.fungal_line
                boxes.append([min(ax, bx) - 40, min(az, bz) - 40, max(ax, bx) + 40, max(az, bz) + 40])
            for x0, z0, x1, z1 in boxes:
                m[max(0, (z0 - g) // f):min(n, (z1 + g) // f + 1), max(0, (x0 - g) // f):min(n, (x1 + g) // f + 1)] = True
        elif e["id"] == "lake_basins":
            m = lake_c.copy()
        elif e["id"] == "gate_straits":
            g = int(e.get("grow_blocks", 0))
            m = raster_lines([[(a[0] / f, a[1] / f), (b[0] / f, b[1] / f)] for a, b in gate_lines(ctx)],
                             (0, 0, n, n), max(1.0, (2 * g + 1) / f))
        elif e["id"] == "river_corridors":
            lines = []
            for c in load("rivers.json")["courses"]:
                if c.get("graded_polyline"):
                    lines.append([(p[0] / f, p[1] / f) for p in c["graded_polyline"]])
            gw = int(e.get("grow_blocks", 0))
            m = raster_lines(lines, (0, 0, n, n), max(1.0, 2 * (gw + 16) / f))
        else:
            continue
        ex_rep[e["id"]] = int(m.sum())
        ex_c |= m
    Pm = ctx.P[:n * f, :n * f].reshape(n, f, n, f).any(axis=(1, 3))
    ex_c |= Pm
    feather = float(sb["exclusion_feather_blocks"])
    dex = distance(ex_c, None, max_iter=int(feather / f) + 3) * f
    wex_c = np.clip(dex / feather, 0.0, 1.0)
    wex_c[ex_c] = 0.0
    nsb = float(sb["near_shore_buffer_blocks"])
    wshore_c = np.clip((dl_c - nsb) / max(1.0, nsb), 0.0, 1.0)
    wc = np.where(sea_c & np.isfinite(Pc), wex_c * wshore_c, 0.0)
    Pc = np.where(np.isfinite(Pc), Pc, 0.0)
    print("  seabed: profile and exclusions %.1f s" % (time.time() - t0), flush=True)
    # full-resolution bounds: only inside a zone polygon, never inside an excluded box (the coarse feather alone would
    # leak a few percent of the fill into an excluded box's edge cells)
    zone_full = raster_polygons([ring for z in sb["zones"] for ring in (ctx.region(z["region"]).get("polygons") or [])],
                                (0, 0, N, N))
    excl_full = np.zeros((N, N), bool)
    for e in sb["exclude"]:
        if "box" in e:
            x0, z0, x1, z1 = e["box"]
            excl_full[max(0, z0):z1 + 1, max(0, x0):x1 + 1] = True
    k = ctx.feature("seabed", "seabed")
    cap = int(sb["cap_y"])
    mind = int(sb["min_depth_to_edit"])
    br = int(sb["canyon"]["blur_radius_blocks"])
    minc = float(sb["canyon"]["min_incision_blocks"])
    band = 256
    written, fill = 0, 0
    zone_stats = {r: {"before": [], "after": []} for r, _ in zones}
    for zb in range(0, N, band):
        ze = min(N, zb + band)
        a0, a1 = max(0, zb - br), min(N, ze + br)
        g = ctx.G1[a0:a1].astype(np.float64)
        blur = box_mean(g, br)[zb - a0:zb - a0 + (ze - zb)]
        gb = ctx.G1[zb:ze].astype(np.int32)
        inc = np.maximum(0.0, blur - gb)
        inc = np.where(inc >= minc, inc, 0.0)
        P = upsample_bilinear(Pc, f, zb, ze, N)
        w = upsample_bilinear(wc, f, zb, ze, N)
        seac = np.repeat(np.repeat(sea_c[zb // f:(ze + f - 1) // f], f, 0), f, 1)[:ze - zb, :N]
        tgt = P - inc
        newv = gb + w * np.maximum(0.0, tgt - gb)
        newv = np.minimum(np.rint(newv), cap).astype(np.int32)
        m = seac & (gb <= SEA - mind) & (newv > gb) & (w > 0) & ~ctx.lake_mask[zb:ze] & zone_full[zb:ze] & \
            ~excl_full[zb:ze]
        box = (0, zb, N, ze)
        ok = ctx.write(k, box, newv.astype(np.int16), m)
        written += int(ok.sum())
        fill += int((newv - gb)[ok].sum())
    # per-zone medians of the sea floor, before and after, on the coarse grid
    for r, zm in zones:
        sel = zm & sea_c & ~ex_c
        if not sel.any():
            continue
        cb = G0[:n * f, :n * f].reshape(n, f, n, f)[:, 3, :, 3][sel]
        ca = ctx.G1[:n * f, :n * f].reshape(n, f, n, f)[:, 3, :, 3][sel]
        zone_stats[r] = {"before_p10_median_p90": [float(np.percentile(cb, q)) for q in (10, 50, 90)],
                         "after_p10_median_p90": [float(np.percentile(ca, q)) for q in (10, 50, 90)],
                         "cells": int(sel.sum())}
    ctx.report["seabed"] = {"columns_written": written, "fill_blocks": fill, "zones": zone_stats, "ridges": ridge_rep,
                            "excluded_coarse_cells": ex_rep, "held_protected": ctx.features[k]["held_protected"],
                            "held_clash": ctx.features[k]["held_clash"],
                            "margin": {"status": sb["margin"]["status"], "seamounts": ctx.region("the_outer_deep")["features"]["seamounts"]}}
    ctx.features[k]["columns_written"] = written
    ctx.seabed_coarse = {"sea": sea_c, "dl": dl_c, "P": Pc, "w": wc, "ex": ex_c, "f": f}
    print("  seabed: written %d columns in %.1f s" % (written, time.time() - t0), flush=True)


# ---------------------------------------------------------------------------------------------------- maps


def hillshade(g):
    g = g.astype(np.float64)
    gz, gx = np.gradient(g)
    s = 0.55 + 0.35 * np.clip((-gx - gz) / 3.0, -1, 1)
    return np.clip(s, 0, 1)


DEPTH_STOPS = [(0, (205, 232, 200)), (1, (182, 226, 214)), (2, (140, 206, 214)), (3, (96, 176, 206)),
               (6, (60, 140, 196)), (11, (40, 104, 172)), (21, (28, 72, 140)), (36, (18, 44, 100)), (60, (8, 20, 60))]


def depth_rgb(depth):
    out = np.zeros(depth.shape + (3,), np.float64)
    ds = [d for d, _ in DEPTH_STOPS]
    for ch in range(3):
        out[..., ch] = np.interp(depth, ds, [c[ch] for _, c in DEPTH_STOPS])
    return out


def render(g, level, water_mask=None):
    """Land by hillshade, water by depth colour: the map the owner reads."""
    sh = hillshade(g)
    depth = level - g.astype(np.float64)
    wet = (depth >= 1) if water_mask is None else (water_mask & (depth >= 1))
    land = np.stack([120 + 100 * sh, 110 + 90 * sh, 80 + 70 * sh], -1)
    water = depth_rgb(np.where(wet, depth, 0)) * (0.8 + 0.2 * sh[..., None])
    rest = wet & (depth <= 1)
    water[rest] = np.array([232, 220, 150]) * (0.8 + 0.2 * sh[rest][..., None])
    img = np.where(wet[..., None], water, land)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


ZONE_COLOURS = {0: (0, 0, 0), 1: (230, 214, 150), 2: (150, 150, 150), 3: (120, 96, 72), 4: (200, 120, 60),
                5: (250, 240, 120), 6: (90, 170, 90), 7: (200, 60, 200)}


def zones_image(z):
    img = np.zeros(z.shape + (3,), np.uint8)
    for k, c in ZONE_COLOURS.items():
        img[z == k] = c
    return Image.fromarray(img, "RGB")


def panel(images, titles, scale, legend=None):
    ims = [im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.NEAREST) for im in images]
    w = sum(im.width for im in ims) + 10 * (len(ims) + 1)
    h = max(im.height for im in ims) + 40 + (40 if legend else 0)
    out = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(out)
    x = 10
    for im, t in zip(ims, titles):
        out.paste(im, (x, 30))
        d.text((x, 8), t, fill=(0, 0, 0))
        x += im.width + 10
    if legend:
        d.text((10, h - 34), legend, fill=(0, 0, 0))
    return out


def fit_scale(w, h, maxpx=820):
    s = maxpx / float(max(w, h))
    return min(4.0, s)


def chart(series, hlines, title, xlabel, ylabel, size=(1000, 380), markers=()):
    W, H = size
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    L, R, Tp, B = 60, 20, 30, 40
    xs = np.concatenate([np.asarray(s[0], float) for s in series if len(s[0])]) if series else np.array([0, 1])
    ys = np.concatenate([np.asarray(s[1], float) for s in series if len(s[1])] + [np.array([h[0] for h in hlines])]) \
        if series else np.array([0, 1])
    ys = ys[np.isfinite(ys)]
    x0, x1 = float(xs.min()), float(xs.max()) if xs.max() > xs.min() else float(xs.min()) + 1
    y0, y1 = float(ys.min()) - 1, float(ys.max()) + 1

    def px(x, y):
        return L + (x - x0) / (x1 - x0) * (W - L - R), H - B - (y - y0) / (y1 - y0) * (H - Tp - B)

    d.rectangle([L, Tp, W - R, H - B], outline=(0, 0, 0))
    for i in range(6):
        yv = y0 + (y1 - y0) * i / 5
        _, py = px(x0, yv)
        d.line([L - 4, py, L, py], fill=(0, 0, 0))
        d.text((4, py - 6), "%.0f" % yv, fill=(0, 0, 0))
        xv = x0 + (x1 - x0) * i / 5
        pxx, _ = px(xv, y0)
        d.line([pxx, H - B, pxx, H - B + 4], fill=(0, 0, 0))
        d.text((pxx - 12, H - B + 6), "%.0f" % xv, fill=(0, 0, 0))
    for yv, col in hlines:
        a, py = px(x0, yv)
        b, _ = px(x1, yv)
        d.line([a, py, b, py], fill=col)
    for xs_, ys_, col, lab in series:
        pts = [px(float(a), float(b)) for a, b in zip(xs_, ys_) if np.isfinite(b)]
        if len(pts) >= 2:
            d.line(pts, fill=col, width=2)
    for xv, lab, col in markers:
        a, _ = px(xv, y0)
        d.line([a, Tp, a, H - B], fill=col)
        d.text((a + 2, Tp + 2), lab, fill=col)
    d.text((L, 8), title, fill=(0, 0, 0))
    d.text((W // 2 - 40, H - 18), xlabel, fill=(0, 0, 0))
    lx = W - R - 260
    for i, (_, _, col, lab) in enumerate(series):
        d.line([lx, 12 + 12 * i, lx + 20, 12 + 12 * i], fill=col, width=2)
        d.text((lx + 24, 6 + 12 * i), lab, fill=(0, 0, 0))
    return img


def section_samples(G, a, b):
    cells, step = line_cells(a, b)
    dist = [i * step for i in range(len(cells))]
    ys = [int(G[z, x]) for x, z in cells]
    return dist, ys, cells


def maps_pass(ctx, out):
    mdir = out / "maps"
    sdir = out / "sections"
    mdir.mkdir(parents=True, exist_ok=True)
    sdir.mkdir(parents=True, exist_ok=True)
    made = []
    legend = "sand yellow = 1 deep (wade, rest); pale cyan 2; blues deeper: 3-5, 6-10, 11-20, 21-35, 36+"
    for lid, rep in ctx.report["lakes"].items():
        box = tuple(rep["box"])
        L = rep["level"]
        inside = ctx.lake_bodies[lid]["inside"]
        b = render(ctx.G0[sl(box)], L, inside)
        a = render(ctx.G1[sl(box)], L, inside)
        z = zones_image(ctx.zone_maps["lake_" + lid]["zones"])
        s = fit_scale(b.width * 3, b.height, 1800)
        img = panel([b, a, z], ["%s before (level %d)" % (lid, L), "after", "bed zones: shelf, bay weed, drop-off, floor, hump, shoal, kept"], s, legend)
        p = mdir / ("lake_%s.png" % lid)
        img.save(p)
        made.append(str(p.relative_to(ROOT)))
    for cid, r in getattr(ctx, "river_runs", {}).items():
        jt = r["jt"]
        if not len(jt):
            continue
        pad = 40
        box = clip_box(min(r["xn"][jt].min(), r["X"].min()) - pad, min(r["zn"][jt].min(), r["Z"].min()) - pad,
                       max(r["xn"][jt].max(), r["X"].max()) + pad, max(r["zn"][jt].max(), r["Z"].max()) + pad, ctx.N)
        # water from the courses, as paint would lay it
        wb_ = paint_water(ctx.G0, ctx.revised_courses_original[cid], box)
        wa_ = paint_water(ctx.G1, ctx.revised_courses[cid], box)
        b = render(ctx.G0[sl(box)], wb_[1], wb_[0])
        a = render(ctx.G1[sl(box)], wa_[1], wa_[0])
        s = fit_scale(b.width * 2, b.height, 1800)
        img = panel([b, a], ["%s before" % cid, "after: meanders, pools and riffles, cascades"], s, legend)
        p = mdir / ("river_%s.png" % cid)
        img.save(p)
        made.append(str(p.relative_to(ROOT)))
        ch = chart([(r["C"], np.floor(r["S"] + 0.01), (140, 140, 140), "surface before"),
                    (r["cn"], r["level"], (20, 90, 200), "surface after"),
                    (r["cn"], r["floor"], (160, 100, 40), "bed after (thalweg)")],
                   [], "%s long profile (x: old chainage)" % cid, "blocks along the old course", "y")
        p = sdir / ("river_%s_long_profile.png" % cid)
        ch.save(p)
        made.append(str(p.relative_to(ROOT)))
    if getattr(ctx, "stream_run", None):
        r = ctx.stream_run
        ch = chart([(r["sg"], r["flo"], (140, 140, 140), "ravine floor (lowest within 2)"),
                    (r["sg"], r["level"], (20, 90, 200), "stream surface"),
                    (r["sg"], r["floor"], (160, 100, 40), "stream bed")],
                   [(SEA, (0, 160, 200))], "Viltri Ravine stream, pass to sea", "blocks from the pass", "y")
        p = sdir / "viltri_ravine_stream_long_profile.png"
        ch.save(p)
        made.append(str(p.relative_to(ROOT)))
        pad = 60
        box = clip_box(r["xn"].min() - pad, r["zn"].min() - pad, r["xn"].max() + pad, r["zn"].max() + pad, ctx.N)
        wa_ = paint_water(ctx.G1, ctx.revised_courses["viltri_ravine_stream"], box)
        lvmap = np.where(wa_[0], wa_[1], float(SEA))
        img = panel([render(ctx.G0[sl(box)], SEA), render(ctx.G1[sl(box)], lvmap, wa_[0] | (ctx.G1[sl(box)] < SEA))],
                    ["Viltri Ravine sea half before", "after: spring, stream, cascades"], fit_scale((box[2] - box[0]) * 2, box[3] - box[1], 1800), legend)
        p = mdir / "viltri_ravine_stream.png"
        img.save(p)
        made.append(str(p.relative_to(ROOT)))
    coast_boxes = [("southern_coast", (400, 4300, 4300, 6900), 0.25), ("pallet_and_relic", (850, 5150, 1450, 5750), 1.0),
                   ("fungal_chain", None, 1.0), ("windward_skerries", (0, 2600, 800, 5200), 0.4),
                   ("north_west_skerries", (250, 1350, 1050, 2650), 0.5)]
    for name, box, scale in coast_boxes:
        if name == "fungal_chain":
            if not getattr(ctx, "fungal_line", None):
                continue
            (ax, az), (bx, bz) = ctx.fungal_line
            box = (min(ax, bx) - 80, min(az, bz) - 80, max(ax, bx) + 80, max(az, bz) + 80)
        box = clip_box(*box, ctx.N)
        f = max(1, int(round(1 / scale)))
        gb = ctx.G0[sl(box)][::f, ::f]
        ga = ctx.G1[sl(box)][::f, ::f]
        img = panel([render(gb, SEA), render(ga, SEA)], ["%s before" % name, "after"], fit_scale(gb.shape[1] * 2, gb.shape[0], 1800), legend)
        p = mdir / ("coast_%s.png" % name)
        img.save(p)
        made.append(str(p.relative_to(ROOT)))
    f = 8
    gb = ctx.G0[::f, ::f]
    ga = ctx.G1[::f, ::f]
    img = panel([render(gb, SEA), render(ga, SEA)], ["seabed before (1 px = 8 blocks)", "after"], 1.0,
                "depth colours as above; the margin outside 0-8191 is not in the heightmap (seamounts: owner question)")
    if getattr(ctx, "seabed_coarse", None):
        d = ImageDraw.Draw(img)
        sc = ctx.seabed_coarse
        for r in ctx.spec["seabed"]["ridges"]:
            if "polyline" in r:
                pts = [(10 + 1024 + 10 + p[0] / f, 30 + p[1] / f) for p in r["polyline"]]
                d.line(pts, fill=(255, 80, 80), width=1)
        for e in ctx.spec["seabed"]["exclude"]:
            if "box" in e:
                x0, z0, x1, z1 = e["box"]
                for off in (10, 10 + 1024 + 10):
                    d.rectangle([off + x0 / f, 30 + z0 / f, off + x1 / f, 30 + z1 / f], outline=(255, 140, 0))
    p = mdir / "seabed_overview.png"
    img.save(p)
    made.append(str(p.relative_to(ROOT)))
    # cross-sections
    lms = {l["id"]: l for l in load("landmarks.json")["landmarks"]}
    rows = ["section,distance,before_y,after_y"]
    for sec in ctx.spec["sections"]:
        if "through" in sec:
            lid = sec["through"].split()[0]
            an = lms[lid]["anchor"]
            br = math.radians(sec["bearing_deg"])
            hx, hz = math.sin(br) * sec["half_length"], -math.cos(br) * sec["half_length"]
            a = (int(an["x"] - hx), int(an["z"] - hz))
            b = (int(an["x"] + hx), int(an["z"] + hz))
            level = ctx.lake_bodies[lid]["level"] if lid in ctx.lake_bodies else SEA
        elif "crossing" in sec:
            if sec["crossing"] not in ctx.crossing_lines:
                continue
            a, b = ctx.crossing_lines[sec["crossing"]]
            level = SEA
        else:
            a, b = tuple(sec["from"]), tuple(sec["to"])
            level = SEA
        a = (max(0, min(ctx.N - 1, a[0])), max(0, min(ctx.N - 1, a[1])))
        b = (max(0, min(ctx.N - 1, b[0])), max(0, min(ctx.N - 1, b[1])))
        dist, yb, _ = section_samples(ctx.G0, a, b)
        _, ya, _ = section_samples(ctx.G1, a, b)
        ch = chart([(dist, yb, (140, 140, 140), "ground before"), (dist, ya, (20, 90, 200), "ground after")],
                   [(level, (0, 170, 220))], "%s  %s -> %s (water at y%d)" % (sec["id"], a, b, level), "blocks", "y")
        p = sdir / ("%s.png" % sec["id"])
        ch.save(p)
        made.append(str(p.relative_to(ROOT)))
        for i in range(0, len(dist), 2):
            rows.append("%s,%.1f,%d,%d" % (sec["id"], dist[i], yb[i], ya[i]))
    (sdir / "sections.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    made.append(str((sdir / "sections.csv").relative_to(ROOT)))
    # crossing fatigue traces
    S = fatigue_constants()
    for cid, after in ctx.report["crossings"].get("after", {}).items():
        before = ctx.report["crossings"]["before"].get(cid, {})
        if "walk" not in after or "walk" not in before:
            continue
        series = []
        for who, col_b, col_a in (("unaided", (200, 150, 150), (200, 30, 30)), ("trained", (150, 150, 200), (30, 30, 200))):
            tb = before["walk"][who]["trace"]
            ta = after["walk"][who]["trace"]
            series.append(([t[0] for t in tb], [t[1] for t in tb], col_b, "%s before" % who))
            series.append(([t[0] for t in ta], [t[1] for t in ta], col_a, "%s after" % who))
        ch = chart(series, [(S["warn_ticks"], (230, 200, 0)), (S["exhausted_ticks"], (230, 120, 0)),
                            (S["collapse_ticks"], (200, 0, 0))],
                   "%s: fatigue along the line (warn, exhausted, collapse)" % cid, "blocks swum", "fatigue")
        p = sdir / ("crossing_%s.png" % cid)
        ch.save(p)
        made.append(str(p.relative_to(ROOT)))
    return made


def paint_water(G, course, box):
    """(wet mask, level map) of a course over the box, the way tools/paint_maps.py paints it."""
    import grade_rivers as GR
    x0, z0, x1, z1 = box
    H, W = z1 - z0, x1 - x0
    best = np.full((H, W), np.inf, np.float32)
    level = np.zeros((H, W), np.float64)
    pts, chain = GR.densify_chained(course["graded_polyline"])
    for (x, z, surface, _f), ch in zip(pts, chain):
        r = GR.at_chainage(course["reaches"], ch)
        if r["water_body"]:
            continue
        hw = r["width"] / 2.0
        rr = int(math.ceil(hw)) + 1
        a0, a1 = max(z0, int(z) - rr), min(z1, int(z) + rr + 2)
        b0, b1 = max(x0, int(x) - rr), min(x1, int(x) + rr + 2)
        if a1 <= a0 or b1 <= b0:
            continue
        zz, xx = np.mgrid[a0:a1, b0:b1]
        d = np.hypot(xx - x, zz - z).astype(np.float32)
        s = (slice(a0 - z0, a1 - z0), slice(b0 - x0, b1 - x0))
        m = (d <= hw) & (d < best[s])
        best[s] = np.where(m, d, best[s])
        level[s] = np.where(m, math.floor(surface + 0.01), level[s])
    g = G[sl(box)]
    wet = (level > 0) & (g < level)
    return wet, np.where(wet, level, 0.0)


# ---------------------------------------------------------------------------------------------------- report


def verdicts(ctx):
    """The design's own checks, for the report. The binding checks are tools/water_shape_audit.py's."""
    out = []
    S = fatigue_constants()
    bef, aft = ctx.report["crossings"].get("before", {}), ctx.report["crossings"].get("after", {})
    for c in ctx.spec["crossings"]:
        req = c.get("require_after") or {}
        a = aft.get(c["id"], {})
        if "walk" not in a:
            out.append((c["id"], "NO SWIMMING ON THE LINE", False))
            continue
        u, t = a["walk"]["unaided"]["outcome"], a["walk"]["trained"]["outcome"]
        ok = True
        if req.get("gate"):
            ok = u == "knocked out" and t == "knocked out" and a["walk"]["unaided"]["resting_on_rest_ground"] == "knocked out" \
                and a["walk"]["trained"]["resting_on_rest_ground"] == "knocked out"
        if req.get("unchanged"):
            ok = a.get("depths") == bef.get(c["id"], {}).get("depths")
        if "unaided" in req and req["unaided"] == "no hit":
            ok = ok and u == "no hit"
        if req.get("unaided") == "hit or worse":
            ok = ok and u != "no hit"
        if req.get("trained") == "no hit":
            ok = ok and t == "no hit"
        if "max_deep_run" in req:
            ok = ok and a.get("max_deep_run", 1e9) <= req["max_deep_run"]
        if req.get("report_only"):
            ok = True
        out.append((c["id"], "unaided %s (%s), trained %s" % (u, a["walk"]["unaided"]["peak_word"], t), ok))
    for lid, r in ctx.report["lakes"].items():
        af = r["after"]
        tg = r["targets"]
        ok = af is not None and af["max_to_rest"] <= tg["max_to_rest"] and tg["wadeable"][0] <= af["wadeable_share"] <= tg["wadeable"][1] \
            and af["deep_9_plus_columns"] >= tg["deep_area_min_share"] * max(1, r["before"]["deep_9_plus_columns"])
        out.append(("lake " + lid, "max to rest %s (target %s), wadeable %s (target %s)" % (
            af["max_to_rest"] if af else None, tg["max_to_rest"], af["wadeable_share"] if af else None, tg["wadeable"]), ok))
    for e in ctx.spec["rivers"]["meanders"]:
        rep = ctx.report["rivers"].get(e["course"], {})
        w = next((x for x in rep.get("windows", []) if x["id"] == e["id"]), None)
        if not w:
            continue
        sn = w["sinuosity"]["after_over_chord"]
        ok = e["sinuosity_target"][0] <= sn <= e["sinuosity_target"][1]
        out.append(("meander " + e["id"], "sinuosity %.2f (before %.2f; target %s)" % (
            sn, w["sinuosity"]["before_over_chord"], e["sinuosity_target"]), ok))
    return out


def write_report(ctx, out, made):
    rep = ctx.report
    rep["feature_table"] = [{k: v for k, v in f.items() if k not in ("family",)} | {"family": f["family"]}
                            for f in ctx.features[1:]]
    rep["verdicts"] = [{"what": a, "result": b, "ok": c} for a, b, c in verdicts(ctx)]
    for when in ("before", "after"):
        for cid, e in rep["crossings"].get(when, {}).items():
            for who in ("unaided", "trained"):
                if "walk" in e:
                    e["walk"][who].pop("trace", None)
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)),
                                     encoding="utf-8")
    L = ["# Water shape: measured report (generated by tools/water_shape.py; do not edit)", "",
         "Input heightmap sha256 `%s`; output `%s` sha256 `%s`." % (rep["input_sha256"], rep["output_name"], rep["output_sha256"]),
         "", "## The design's own verdicts (the binding checks are tools/water_shape_audit.py's)", "",
         "| What | Result | Meets the design |", "|---|---|---|"]
    for v in rep["verdicts"]:
        L.append("| %s | %s | %s |" % (v["what"], v["result"], "yes" if v["ok"] else "**NO**"))
    L += ["", "## Crossings (WATER_BUILD_PLAN 11.1), before and after", "",
          "| Crossing | Swim before/after | 3+ deep before/after | Longest 3+ deep run after | Unaided before -> after | Trained before -> after |",
          "|---|---|---|---|---|---|"]
    for c in ctx.spec["crossings"]:
        b = rep["crossings"]["before"].get(c["id"], {})
        a = rep["crossings"]["after"].get(c["id"], {})
        if "walk" not in b or "walk" not in a:
            L.append("| %s | no swimming on the line | | | | |" % c["id"])
            continue
        L.append("| %s | %s / %s | %s / %s | %s | %s (%s) -> %s (%s) | %s -> %s |" % (
            c["id"], b["swim"], a["swim"], b["deep"], a["deep"], a["max_deep_run"],
            b["walk"]["unaided"]["outcome"], b["walk"]["unaided"]["peak_word"],
            a["walk"]["unaided"]["outcome"], a["walk"]["unaided"]["peak_word"],
            b["walk"]["trained"]["outcome"], a["walk"]["trained"]["outcome"]))
    L += ["", "## Lakes", "", "| Lake | Wadeable before -> after | Deepest point to rest before -> after | Within 30 of rest after | 9+ deep columns before -> after | Level/1-step/steeper neighbours before -> after | Shoals | Humps | Fill / cut blocks |",
          "|---|---|---|---|---|---|---|---|---|"]
    for lid, r in rep["lakes"].items():
        b, a = r["before"], r["after"]
        L.append("| %s | %s -> %s | %s -> %s | %s | %s -> %s | %s -> %s | %d | %d | %d / %d |" % (
            lid, b["wadeable_share"], a["wadeable_share"], b["max_to_rest"], a["max_to_rest"], a["within_30_of_rest_share"],
            b["deep_9_plus_columns"], a["deep_9_plus_columns"], b["neighbours_level_1step_steeper"],
            a["neighbours_level_1step_steeper"], len(r["shoals"]), len(r["humps"]), r["fill_blocks"], r["cut_blocks"]))
    L += ["", "## Rivers", "", "| Course | Window | Kind | Sinuosity before -> after (over the chord) | Wavelength | Amplitude median/max | Steps gathered | Falls |", "|---|---|---|---|---|---|---|---|"]
    for cid, r in rep["rivers"].items():
        for w in r["windows"]:
            si = w.get("sinuosity", {})
            L.append("| %s | %s %.0f-%.0f | %s | %s -> %s | %s | %s / %s | %s | %s |" % (
                cid, w["id"], w["from_m"], w["to_m"], w["kind"], si.get("before_over_chord"), si.get("after_over_chord"),
                w.get("wavelength", ""), w.get("amplitude_median", ""), w.get("amplitude_max", ""), w.get("steps_placed"),
                len(w.get("falls", []))))
    if "stream" in rep:
        s = rep["stream"]
        L += ["", "## The Viltri Ravine stream", "", "%s blocks from the spring (level y%s) to the sea (y%s); %s steps, falls %s; %s blocks of extension beyond the axis to reach the sea." % (
            s["length"], s["from_level"], s["to_level"], s["steps"], s["falls"], s["extension_to_sea_blocks"])]
    L += ["", "## Coasts", ""]
    for cid, r in rep["coasts"].items():
        L.append("- **%s**: %s" % (cid, json.dumps({k: v for k, v in r.items() if k not in ("bars", "placed", "knolls")}, default=str)))
    if rep.get("seabed"):
        s = rep["seabed"]
        L += ["", "## Seabed", "", "%d columns filled, %d blocks. Per zone (coarse, excluded water left out):" % (s["columns_written"], s["fill_blocks"])]
        for z, v in s["zones"].items():
            if "cells" in v:
                L.append("- %s: seabed y p10/median/p90 before %s, after %s" % (z, v["before_p10_median_p90"], v["after_p10_median_p90"]))
    L += ["", "## Cut and fill by feature", "", "| Feature | Family | Columns written | Held off (protected) | Held off (another feature) |", "|---|---|---|---|---|"]
    for f in ctx.features[1:]:
        L.append("| %s | %s | %s | %s | %s |" % (f["id"], f["family"], f.get("columns_written", ""), f["held_protected"], f["held_clash"]))
    L += ["", "## Maps and sections", ""] + ["- `%s`" % m for m in made]
    if rep["notes"]:
        L += ["", "## Notes", ""] + ["- %s" % n for n in rep["notes"]]
    (out / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------------------- main


def build(source_root, only=None, world_path=None, maps=True):
    t0 = time.time()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    world_path = Path(world_path or (ROOT / "data" / "world.json"))
    world = T.load_world(world_path)
    if world["heightmap"]["sha256"] != spec["applies_to"]["heightmap_sha256"]:
        raise ShapeError("data/world.json pins %s but the design applies to %s: re-derive the design first" % (
            world["heightmap"]["sha256"][:12], spec["applies_to"]["heightmap_sha256"][:12]))
    hm = T.resolve_heightmap(world, world_path, source_root)
    raw = np.array(Image.open(hm))
    if raw.dtype != np.uint16:
        raise ShapeError("the heightmap is not 16-bit")
    G0 = ground_of_raw(raw, world)
    ctx = Ctx(world, spec, raw, G0, hm)
    print("loaded %s in %.1f s" % (hm.name, time.time() - t0), flush=True)
    build_protect(ctx)
    build_lake_mask(ctx)
    ctx.report["crossings"]["before"] = crossings_pass(ctx, "before", ctx.G0)
    fb = spec["coasts"]["fungal_bar_chain"]
    fl = ctx.crossing_lines.get("fungal_from_the_pallet_coast")
    ctx.fungal_line = fl
    ctx.revised_courses_original = {c["id"]: c for c in load("rivers.json")["courses"]}
    fams = FAMILIES if not only else tuple(only)
    print("protected %d columns; crossings measured (%.1f s)" % (ctx.P.sum(), time.time() - t0), flush=True)
    if "rivers" in fams:
        rivers_pass(ctx)
        print("rivers done (%.1f s)" % (time.time() - t0), flush=True)
    else:
        ctx.revised_courses.update({k: copy.deepcopy(v) for k, v in ctx.revised_courses_original.items()})
    if "stream" in fams:
        stream_pass(ctx)
        print("stream done (%.1f s)" % (time.time() - t0), flush=True)
    if "lakes" in fams:
        lakes_pass(ctx)
        print("lakes done (%.1f s)" % (time.time() - t0), flush=True)
    if "coasts" in fams:
        coasts_pass(ctx)
        print("coasts done (%.1f s)" % (time.time() - t0), flush=True)
    if "seabed" in fams:
        seabed_pass(ctx)
        print("seabed done (%.1f s)" % (time.time() - t0), flush=True)
    ctx.report["crossings"]["after"] = crossings_pass(ctx, "after", ctx.G1)
    ctx.families = fams
    return ctx


def write_outputs(ctx, maps=True):
    spec = ctx.spec
    out = ROOT / spec["output"]["dir"]
    out.mkdir(parents=True, exist_ok=True)
    changed = ctx.G1 != ctx.G0
    raw_new = ctx.raw.copy()
    raw_new[changed] = raw_of_ground(ctx.G1[changed], ctx.world)
    back = np.round(T.sample_to_height(raw_new[changed], ctx.world).astype(np.float32)).astype(np.int16)
    if not np.array_equal(back, ctx.G1[changed]):
        raise ShapeError("the written samples do not read back as the planned ground")
    dest = out / spec["output"]["heightmap_name"]
    if dest.resolve() == ctx.hm_path.resolve():
        raise ShapeError("refusing to write over the source heightmap")
    Image.fromarray(raw_new, mode="I;16").save(dest)
    if not np.array_equal(np.array(Image.open(dest)), raw_new):
        raise ShapeError("the written heightmap does not read back identically")
    sha = sha256_file(dest)
    np.save(out / "changed.npy", changed)
    np.save(out / "owner.npy", ctx.owner)
    (out / "rivers_revised.json").write_text(json.dumps({
        "schema": "cobblers.rivers/1", "status": "derived by tools/water_shape.py for review; the courses paint_maps.py "
                                                 "would read after the water revision is applied",
        "from_heightmap_sha256": ctx.world["heightmap"]["sha256"], "water_shaped_sha256": sha,
        "courses": list(ctx.revised_courses.values())}, indent=1), encoding="utf-8")
    zdir = out / "zones"
    zdir.mkdir(exist_ok=True)
    zman = {}
    for name, z in ctx.zone_maps.items():
        Image.fromarray(z["zones"]).save(zdir / ("%s.png" % name))
        zman[name] = {"box": list(z["box"]), "map": "zones/%s.png" % name}
    ctx.report["input_sha256"] = ctx.world["heightmap"]["sha256"]
    ctx.report["output_name"] = dest.name
    ctx.report["output_sha256"] = sha
    made = maps_pass(ctx, out) if maps else []
    write_report(ctx, out, made)
    manifest = {
        "generator": "tools/water_shape.py", "spec": "data/water_shape.json", "spec_sha256": sha256_file(SPEC),
        "input": {"path": ctx.hm_path.name, "sha256": ctx.world["heightmap"]["sha256"]},
        "output": {"path": dest.name, "sha256": sha}, "families": list(ctx.families),
        "complete": tuple(ctx.families) == FAMILIES, "columns_changed": int(changed.sum()),
        "features": [{"index": i, "id": f["id"], "family": f["family"]} for i, f in enumerate(ctx.features) if i],
        "zones": zman, "maps": made,
        "blocks_moved": int(np.abs(ctx.G1.astype(np.int32) - ctx.G0.astype(np.int32)).sum()),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("wrote %s (%s), %d columns changed; report %s" % (dest.relative_to(ROOT), sha[:12], changed.sum(),
                                                             (out / "REPORT.md").relative_to(ROOT)))
    return manifest


def apply(source_root, world_path=None):
    """The owner-approved step: write the revision beside the canonical heightmap and repin data/world.json. Refuses
    unless tools/water_shape_audit.py passed this exact copy."""
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    out = ROOT / spec["output"]["dir"]
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    aud_p = out / "audit.json"
    if not aud_p.is_file():
        raise ShapeError("no audit: run tools/water_shape_audit.py first")
    aud = json.loads(aud_p.read_text(encoding="utf-8"))
    if not aud.get("clean") or aud.get("copy_sha256") != man["output"]["sha256"] or not man.get("complete"):
        raise ShapeError("the audit is not clean for this copy (or the copy is partial): nothing is applied")
    world_path = Path(world_path or (ROOT / "data" / "world.json"))
    world = T.load_world(world_path)
    current = T.resolve_heightmap(world, world_path, source_root)
    src = out / man["output"]["path"]
    if sha256_file(src) != man["output"]["sha256"]:
        raise ShapeError("the copy changed since it was audited")
    dest = current.parent / man["output"]["path"]
    if dest.exists():
        raise ShapeError("%s exists; refusing to overwrite a source file" % dest)
    dest.write_bytes(src.read_bytes())
    text = world_path.read_text(encoding="utf-8")
    doc = json.loads(text)
    hm = doc["heightmap"]
    old = {"path": hm["path"], "sha256": hm["sha256"]}
    hm["water_shaped_from"] = {**old, "generator": "python tools/water_shape.py --apply", "spec": "data/water_shape.json",
                               "spec_sha256": man["spec_sha256"], "columns_changed": man["columns_changed"],
                               "blocks_moved": man["blocks_moved"],
                               "note": "Rivers, the Viltri Ravine stream, lake beds, coasts and the seabed (docs/world-building/WATER_SHAPE.md). Columns outside the declared features are bit-identical."}
    hm["previous_sha256"] = [old["sha256"]] + [s for s in hm.get("previous_sha256", []) if s != old["sha256"]]
    hm["path"], hm["sha256"] = man["output"]["path"], man["output"]["sha256"]
    start = text.index('"heightmap"')
    brace = text.index("{", start)
    depth, i = 0, brace
    while True:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    world_path.write_text(text[:brace] + json.dumps(hm, indent=2) + text[i + 1:], encoding="utf-8")
    print("applied: %s is canonical; data/world.json repinned. Next: data/rivers.json from derived/water_shape/"
          "rivers_revised.json, the paint, the dependents (WATER_SHAPE.md 'After the apply')." % dest.name)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root")
    ap.add_argument("--world", default=str(ROOT / "data" / "world.json"))
    ap.add_argument("--only", nargs="*", choices=FAMILIES)
    ap.add_argument("--no-maps", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.apply:
            return apply(a.source_root, a.world)
        ctx = build(a.source_root, a.only, a.world, maps=not a.no_maps)
        write_outputs(ctx, maps=not a.no_maps)
    except (ShapeError, T.TerrainUnavailable) as e:
        print("water_shape: %s" % e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
