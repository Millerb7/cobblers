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
FAMILIES = ("rivers", "stream", "lakes", "seabed", "bank", "coasts")
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


def running_max2d(a, r):
    """The maximum over a (2r+1)-square window, edges padded (separable)."""
    a = np.asarray(a, np.float64)
    if r <= 0:
        return a.copy()
    p = np.pad(a, ((r, r), (0, 0)), mode="edge")
    a1 = np.lib.stride_tricks.sliding_window_view(p, 2 * r + 1, axis=0).max(axis=-1)
    p = np.pad(a1, ((0, 0), (r, r)), mode="edge")
    return np.lib.stride_tricks.sliding_window_view(p, 2 * r + 1, axis=1).max(axis=-1)


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

    def write(self, k, box, new, mask, over=()):
        """Propose ground `new` (over the box) where `mask`. Protected columns and columns another feature already
        owns are held off and counted, except a declared family's in `over` (the bank reshapes the sea floor's fill
        round the removed island); the rest are written and owned by feature k."""
        s = sl(box)
        cur, own, prot = self.G1[s], self.owner[s], self.P[s]
        want = mask & (new != cur)
        held = want & prot
        clash = want & ~prot & (own != 0) & (own != k)
        if over:
            idx = [i for i, f in enumerate(self.features) if f.get("family") in over]
            clash &= ~np.isin(own, idx)
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


def islet_footprint(margin):
    """Relic Island's islet as tools/islet.py builds it (its top is not NaN), grown by `margin`, over the square of
    half side RADIUS + margin round its centre. The square's corners beyond the outline are plain seabed."""
    import islet as I
    top, _ = I.island_top(None, SEA)
    on = ~np.isnan(np.asarray(top, float))
    out = np.zeros((on.shape[0] + 2 * margin, on.shape[1] + 2 * margin), bool)
    out[margin:margin + on.shape[0], margin:margin + on.shape[1]] = on
    return grow(out, margin) if margin > 0 else out


def build_protect(ctx):
    spec = ctx.spec["protect"]
    N = ctx.N
    parts = {}

    def add(name, box, mask):
        ctx.P[sl(box)] |= mask
        parts[name] = parts.get(name, 0) + int(mask.sum())

    towns = load("towns.json")["towns"]
    m = int(spec["town_margin_blocks"])
    released = {r["town"] for r in spec.get("release_towns", [])}
    for t in towns:
        fp = t.get("footprint") or {}
        if fp.get("min_x") is None or t["id"] in released:
            continue
        mt = int(spec.get("town_margin_overrides", {}).get(t["id"], m))
        box = clip_box(fp["min_x"] - mt, fp["min_z"] - mt, fp["max_x"] + mt + 1, fp["max_z"] + mt + 1, N)
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
    mg = int(spec["islet"]["margin_blocks"])
    r = I.RADIUS + mg
    box = clip_box(cx - r, cz - r, cx + r + 1, cz + r + 1, N)
    add("islet", box, islet_footprint(mg))

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
    if "sea_town_resite" in names:
        import sea_town
        level, deck = sea_town.deck_ground(ctx.world, resite=True)
        for x, z in deck:
            out[(int(x), int(z))] = int(level)
    return out


def land_mask(ctx, G, when):
    """Dry ground for a crossing's endpoints: before the revision the Jungle Isle's land is left out (it is removed,
    so it cannot be the far shore of a crossing measured for after)."""
    m = G >= SEA
    if when == "before" and ctx.spec.get("jungle_isle_bank"):
        bbox, isl = bank_island(ctx)
        m = m.copy()
        m[sl(bbox)] &= ~isl
    return m


def to_town_endpoints(ctx, c, G, when):
    """The nearest pair of a dry column (anywhere, the removed island left out) and a cell of the re-sited town: a
    deck cell, or, after the revision, 1-deep rest ground within the town's zone."""
    deck = resited_town(ctx)["deck"]            # the town itself: its mainland jetty is on the far shore
    xs = np.array([p[0] for p in deck])
    zs = np.array([p[1] for p in deck])
    pad = 1600
    box = clip_box(xs.min() - pad, zs.min() - pad, xs.max() + pad + 1, zs.max() + pad + 1, ctx.N)
    tm = np.zeros((box[3] - box[1], box[2] - box[0]), bool)
    tm[zs - box[1], xs - box[0]] = True
    if when == "after" and getattr(ctx, "bank_run", None) is not None:
        br = ctx.bank_run
        bb = br["box"]
        a0, a1 = max(box[1], bb[1]), min(box[3], bb[3])
        b0, b1 = max(box[0], bb[0]), min(box[2], bb[2])
        tz = br["town_zone"][a0 - bb[1]:a1 - bb[1], b0 - bb[0]:b1 - bb[0]]
        rest = (G[a0:a1, b0:b1] >= SEA - 1)
        tm[a0 - box[1]:a1 - box[1], b0 - box[0]:b1 - box[0]] |= tz & rest
    land = land_mask(ctx, G, when)[sl(box)] & ~tm
    d = distance_scaled(tm, None, 4)
    dl = np.where(land, d, np.inf)
    iz, ix = np.unravel_index(int(np.argmin(dl)), dl.shape)
    lx, lz = ix + box[0], iz + box[1]
    tz_, tx_ = np.nonzero(tm)
    j = int(np.argmin((tx_ + box[0] - lx) ** 2 + (tz_ + box[1] - lz) ** 2))
    return (int(lx), int(lz)), (int(tx_[j] + box[0]), int(tz_[j] + box[1]))


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
        if c["kind"] == "to_town":
            a, b = to_town_endpoints(ctx, c, G, when)
            ctx.crossing_lines[c["id"]] = (a, b)
        elif when == "before":
            a, b = crossing_endpoints(ctx, c, G)
            ctx.crossing_lines[c["id"]] = (a, b)
        else:
            a, b = ctx.crossing_lines[c["id"]]
        if when == "before" and c.get("measure_before") is False:
            res[c["id"]] = {"from": list(a), "to": list(b),
                            "not_measured": "the line runs over the Jungle Isle's land before the revision"}
            continue
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


def gate_lines(ctx, only_gates=False):
    out = []
    for c in ctx.spec["crossings"]:
        req = c.get("require_after") or {}
        if req.get("gate") or (not only_gates and (req.get("unchanged") or req.get("rates_unchanged"))):
            if only_gates and c.get("strait_trough") is False:
                continue
            if c["id"] in ctx.crossing_lines:
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
    rise = float(e.get("room_rise_blocks", dflt.get("room_rise_blocks", 3)))
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
    # a station whose water reaches within 3 blocks of a lake basin is the lake's: never swung, never re-stepped
    near_lake = np.zeros(n, bool)
    for i in range(n):
        rr = int(width[i] / 2.0) + 3
        zi, xi = int(round(Z[i])), int(round(X[i]))
        near_lake[i] = bool(ctx.lake_mask[max(0, zi - rr):zi + rr + 1, max(0, xi - rr):xi + rr + 1].any())
    # tributary mouths: a meander must pass through the column where another cut course joins this one
    doc = load("rivers.json")
    cut_ids = set((doc.get("cut") or {}).get("courses_cut", []))
    junctions = []
    for c2 in doc["courses"]:
        if c2.get("ends_in") == course["id"] and c2["id"] in cut_ids and c2.get("graded_polyline"):
            ex_, ez_ = c2["graded_polyline"][-1][:2]
            junctions.append(float(C[int(np.argmin((X - ex_) ** 2 + (Z - ez_) ** 2))]))
    rep["junctions_m"] = [round(j, 1) for j in junctions]
    # planform smoothing: a gentle curve through the graded course's vertex kinks (no loops), inside the room the
    # valley gives; the meander windows then swing about the smoothed line
    for e in entries:
        if kind_of(e) != "smooth":
            continue
        win = (C >= e["from_m"]) & (C <= e["to_m"]) & ~wb & ~near_lake
        ii = np.nonzero(win)[0]
        if len(ii) < 20:
            raise ShapeError("%s: the window %s-%s holds no river stations" % (e["id"], e["from_m"], e["to_m"]))
        sig = float(e["sigma_blocks"])
        k = np.arange(-int(3 * sig), int(3 * sig) + 1)
        ker = np.exp(-0.5 * (k / sig) ** 2)
        ker /= ker.sum()
        Xs = np.convolve(np.pad(X[ii], len(k) // 2, mode="edge"), ker, mode="valid")
        Zs = np.convolve(np.pad(Z[ii], len(k) // 2, mode="edge"), ker, mode="valid")
        Ys = (Xs - X[ii]) * nx[ii] + (Zs - Z[ii]) * nz[ii]
        a, b = C[ii[0]], C[ii[-1]]
        t = np.clip(np.minimum(C[ii] - a, b - C[ii]) / (2.0 * sig), 0.0, 1.0)
        for cj in junctions:
            t = np.minimum(t, np.clip((np.abs(C[ii] - cj) - 6.0) / (2.0 * sig), 0.0, 1.0))
        Ys = Ys * (0.5 - 0.5 * np.cos(np.pi * t))
        A = allowed_amplitude(ctx, X[ii], Z[ii], nx[ii], nz[ii], S[ii], width[ii] / 2.0, [rat[i] for i in ii],
                              dict(e, belt="measured"), dflt)
        Ys = np.clip(Ys, -A, A)
        Ys = running(Ys, int(sig), "mean")
        Yoff[ii] += Ys
        rep["windows"].append({"id": e["id"], "kind": "smooth", "from_m": float(a), "to_m": float(b),
                               "sigma": sig, "offset_max": round(float(np.abs(Ys).max()), 1),
                               "offset_median": round(float(np.median(np.abs(Ys))), 1),
                               "kink_before_deg": round(float(np.degrees(np.abs(np.diff(np.unwrap(np.arctan2(np.diff(Z[ii]), np.diff(X[ii])))))).max()), 1)})
    for e in entries:
        if kind_of(e) != "meander":
            continue
        win = (C >= e["from_m"]) & (C <= e["to_m"]) & ~wb & ~near_lake
        ii = np.nonzero(win)[0]
        if len(ii):
            # the longest unbroken run: a window never swings through a lake's basin
            cuts = np.nonzero(np.diff(ii) > 1)[0]
            runs = np.split(ii, cuts + 1)
            ii = max(runs, key=len)
        if len(ii) < 20:
            raise ShapeError("%s: the window %s-%s holds no river stations" % (e["id"], e["from_m"], e["to_m"]))
        a, b = C[ii[0]], C[ii[-1]]
        hw = width[ii] / 2.0
        Xb, Zb = X[ii] + nx[ii] * Yoff[ii], Z[ii] + nz[ii] * Yoff[ii]
        A = allowed_amplitude(ctx, Xb, Zb, nx[ii], nz[ii], S[ii], hw, [rat[i] for i in ii], e, dflt)
        omega = math.radians(e["omega_deg"])
        cn_t, yn_t, ratio, sin_nom, u0 = shape_table(omega)
        wmed = float(np.median(width[ii]))
        lam = float(np.clip(np.median(A) / max(ratio, 1e-6), e["wavelength_widths"][0] * wmed,
                            e["wavelength_widths"][1] * wmed))
        A = running(running(A, lam / 4.0, "min"), lam / 8.0, "mean")
        t = np.clip(np.minimum(C[ii] - a, b - C[ii]) / (lam / 2.0), 0.0, 1.0)
        for cj in junctions:
            t = np.minimum(t, np.clip((np.abs(C[ii] - cj) - 6.0) / (lam / 2.0), 0.0, 1.0))
        A = np.clip(A * (0.5 - 0.5 * np.cos(np.pi * t)), 0.0, float(e["max_amplitude_blocks"]))
        # no two loops alike: the wavelength wanders and the amplitude breathes along the window (a fixed sine reads
        # as drawn, not as a river); amplitude only ever shrinks from the room allowed
        sw = C[ii] - a
        jl = float(e.get("wavelength_jitter", 0.3))
        ja = float(e.get("amplitude_jitter", 0.35))
        nl = value_noise(sw, np.zeros_like(sw), lam * 1.3, seed_of("meander_l", e["id"]))
        na = value_noise(sw, np.full_like(sw, 17.0), lam * 0.9, seed_of("meander_a", e["id"]))
        lam_s = lam * (1.0 + jl * (2.0 * nl - 1.0))
        phase = u0 + np.concatenate([[0.0], np.cumsum(np.diff(sw) / lam_s[1:])])
        A = A * (1.0 - ja * na)
        Yoff[ii] = Yoff[ii] + A * np.interp(phase % 1.0, cn_t, yn_t)
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
        jj = np.array([j for j in jj if not rat[min(n - 1, int(np.searchsorted(C, cn[j])))]["water_body"]
                       and not near_lake[min(n - 1, int(np.searchsorted(C, cn[j])))]], int)
        if len(jj):
            runs = np.split(jj, np.nonzero(np.diff(jj) > 1)[0] + 1)
            jj = max(runs, key=len)
        if len(jj) < 8:
            raise ShapeError("%s: fewer than 8 stations in its window" % e["id"])
        touched[jj] = True
        if kind == "smooth":
            continue
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


def course_footprints(ctx):
    """Every cut course's painted water (its non-lake stations, half width plus 2), as (box, mask) per course, from
    data/rivers.json: what no other feature may fill or seal (a lake shelf across an outlet, a meander's old-channel
    fill over a tributary's mouth)."""
    if getattr(ctx, "course_fp", None) is not None:
        return ctx.course_fp
    import grade_rivers as GR
    doc = load("rivers.json")
    cut = set((doc.get("cut") or {}).get("courses_cut", []))
    out = {}
    for c in doc["courses"]:
        if c["id"] not in cut or not c.get("graded_polyline"):
            continue
        pts, chain = GR.densify_chained(c["graded_polyline"])
        xs = np.array([p[0] for p in pts])
        zs = np.array([p[1] for p in pts])
        hws = np.array([GR.at_chainage(c["reaches"], ch)["width"] / 2.0 + 2.0 for ch in chain])
        keep = np.array([not GR.at_chainage(c["reaches"], ch)["water_body"] for ch in chain])
        if not keep.any():
            continue
        pad = int(hws.max()) + 3
        box = clip_box(xs.min() - pad, zs.min() - pad, xs.max() + pad + 1, zs.max() + pad + 1, ctx.N)
        ii = np.nonzero(keep)[0]
        best, _i, _l = stamp((xs[ii], zs[ii], np.zeros(len(ii)), np.zeros(len(ii))), box, lambda j: float(hws[ii[j]]))
        out[c["id"]] = (box, np.isfinite(best))
    ctx.course_fp = out
    return out


def footprint_in(ctx, box, skip=()):
    """The union of the course footprints over `box`, leaving out the courses in `skip`."""
    m = np.zeros((box[3] - box[1], box[2] - box[0]), bool)
    for cid, (b, fm) in course_footprints(ctx).items():
        if cid in skip:
            continue
        a0, a1 = max(box[1], b[1]), min(box[3], b[3])
        c0, c1 = max(box[0], b[0]), min(box[2], b[2])
        if a1 > a0 and c1 > c0:
            m[a0 - box[1]:a1 - box[1], c0 - box[0]:c1 - box[0]] |= fm[a0 - b[1]:a1 - b[1], c0 - b[0]:c1 - b[0]]
    return m


def carve_course(ctx, k, r, course, corridor_half, entries):
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
    # the audit's footprint: the original centreline over each window (8 blocks either side), grown by corridor_half
    corr = np.zeros((box[3] - box[1], box[2] - box[0]), bool)
    in_win = np.zeros(len(r["C"]), bool)
    for e in entries:
        in_win |= (r["C"] >= e["from_m"]) & (r["C"] <= e["to_m"])
        oi = np.nonzero((r["C"] >= e["from_m"] - 8) & (r["C"] <= e["to_m"] + 8))[0]
        for i in oi[::2]:
            a0, a1 = max(0, int(r["Z"][i]) - corridor_half - box[1]), min(corr.shape[0], int(r["Z"][i]) + corridor_half + 2 - box[1])
            b0, b1 = max(0, int(r["X"][i]) - corridor_half - box[0]), min(corr.shape[1], int(r["X"][i]) + corridor_half + 2 - box[0])
            if a1 > a0 and b1 > b0:
                zz, xx = np.mgrid[a0:a1, b0:b1]
                corr[a0:a1, b0:b1] |= np.hypot(xx + box[0] - r["X"][i], zz + box[1] - r["Z"][i]) <= corridor_half
    # the lakes are the lake pass's (P5), whatever a river window touches
    corr &= ~ctx.lake_mask[sl(box)]
    # the new channel
    sel = jt
    stations = (xn[sel], zn[sel], r["nxn"][sel], r["nzn"][sel])
    best, idx, lat = stamp(stations, box, lambda j: float(Rj[sel[j]]))
    has = idx >= 0
    J = np.where(has, sel[np.maximum(idx, 0)], 0)
    lv = level[J].astype(float)
    # cut to the lowest level of the stations either side: a column at a step may paint with either station's level,
    # and it must hold water under both
    lcut = running(level.astype(float), 5, "min")
    fl = np.minimum(floor[J], lcut[J] - 1.0)
    hw = hwn[J]
    off = r["offset"][J]
    inner = has & (best <= hw)
    e_side = np.where(lat >= off, hw, -hw)
    den = np.where(np.abs(e_side - off) < 1e-6, 1e-6, e_side - off)
    tpar = np.clip((lat - off) / den, 0.0, 1.0)
    edge = lcut[J] - 1.0
    ts_in = np.minimum(fl + (edge - fl) * tpar ** 2, edge)
    # the bank rises from the water's edge at the reach's bank slope; ground above that line is cut back (a cut bank
    # where a bend swings into a terrace), ground below it is left alone
    ts_out = (lv - 1) + (best - hw) * bank[J]
    target = np.floor(np.where(has, np.where(inner, ts_in, ts_out), 0.0) + 0.5)
    cut_zone = has & (best <= hw + 2.0 / bank[J] + 1.0)
    cur = ctx.G1[sl(box)].astype(np.int32)
    new = cur.copy()
    # water that must stay water: the course's untouched stretches beside the windows and every other course's
    # painted channel (a tributary's mouth) are never filled and never get a lip across them
    tset = set(int(j) for j in jt)
    ut = np.array([j for j in np.nonzero(~np.array([rr["water_body"] for rr in r["rat_new"]]))[0] if int(j) not in tset], int)
    others = footprint_in(ctx, box, skip=(course["id"],))
    if len(ut):
        ubest, uidx, _ul = stamp((xn[ut], zn[ut], r["nxn"][ut], r["nzn"][ut]), box, lambda j: float(hwn[ut[j]] + 1.0))
        u_any = uidx >= 0
        u_core = u_any & (ubest <= hwn[ut[np.maximum(uidx, 0)]])
    else:
        u_any = u_core = np.zeros(best.shape, bool)
    keep_wet = u_any | others
    no_lip = u_core | others
    # the old channel, where a window abandoned it
    olds = np.nonzero(in_win & ~r["wb"])[0]
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
        fill = old_wet & ~(has & (best <= hw + 1.0)) & ~keep_wet
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
            raise_m = nb_wet & ~wet & (new < nb_lv) & ~standing & ~no_lip
            new = np.where(raise_m, np.maximum(new, nb_lv).astype(np.int32), new)
    # another course's channel is changed only where this course's own new channel runs through it (a junction)
    mask = corr & (new != cur) & ~(others & ~inner)
    ok = ctx.write(k, box, new.astype(np.int16), mask)
    return int(ok.sum())


def revised_record(course, r):
    import grade_rivers as GR
    rev = copy.deepcopy(course)
    sg, cn = r["sg"], r["cn"]
    # untouched stretches keep the canonical course's own stations, exactly (full precision, the original
    # surfaces): resampled at the reshaped course's arc length they sat a fraction of a block along, and a channel
    # whose half width is a whole number painted a column narrower on each side (the first run's new leaks)
    opts, och = GR.densify_chained(course["graded_polyline"])
    touched = r["touched"]
    runs = []
    j = 0
    while j < len(sg):
        if touched[j]:
            k = j
            while k + 1 < len(sg) and touched[k + 1]:
                k += 1
            runs.append((j, k))
            j = k + 1
        else:
            j += 1
    verts, oldc = [], []
    i = 0
    for a, b in runs:
        ca, cb = float(cn[a]), float(cn[b])
        while i < len(opts) and och[i] < ca:
            p = opts[i]
            verts.append([float(p[0]), float(p[1]), float(p[2]), float(p[3])])
            oldc.append(float(och[i]))
            i += 1
        for jj_ in range(a, b + 1):
            verts.append([round(float(r["xn"][jj_]), 3), round(float(r["zn"][jj_]), 3), float(r["level"][jj_]),
                          round(float(r["floor"][jj_]), 2)])
            oldc.append(float(cn[jj_]))
        while i < len(opts) and och[i] <= cb:
            i += 1
    while i < len(opts):
        p = opts[i]
        verts.append([float(p[0]), float(p[1]), float(p[2]), float(p[3])])
        oldc.append(float(och[i]))
        i += 1
    rev["graded_polyline"] = verts
    cn = np.maximum.accumulate(np.array(oldc))
    # the reach boundaries in the chainage the painter will measure along these vertices (chords of the rounded
    # vertices, a little shorter than the arc length sg on a bend: over a long course sg drifts several blocks and
    # a width change would land on the wrong stations)
    px_ = np.array([p[0] for p in rev["graded_polyline"]])
    pz_ = np.array([p[1] for p in rev["graded_polyline"]])
    ch_paint = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(px_), np.diff(pz_)))])
    new_reaches = []
    for rc in course["reaches"]:
        q = dict(rc)
        q["from_m"] = round(float(np.interp(rc["from_m"], cn, ch_paint)), 2)
        q["to_m"] = round(float(np.interp(rc["to_m"], cn, ch_paint)), 2)
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
    entries = [dict(e, _kind="smooth") for e in spec.get("smooth", [])] + \
        [dict(e, _kind="meander") for e in spec["meanders"]] + [dict(e, _kind="cascades") for e in spec["cascades"]]
    by_course = {}
    for e in entries:
        by_course.setdefault(e["course"], []).append(e)
    for cid, es in by_course.items():
        course = course_by_id(doc, cid)
        k = ctx.feature("river:" + cid, "rivers", entries=[e["id"] for e in es])
        r = reshape_course(ctx, GR, course, es, dflt, lambda e: e["_kind"])
        written = carve_course(ctx, k, r, course, int(dflt["corridor_half_width_blocks"]), es)
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


def ravine_axis(st):
    """(pass, sea half polyline, lake half polyline) of the Viltri Ravine: its channel axis in data/landmarks.json split
    at the pass, each half running away from the pass."""
    lm = next(l for l in load("landmarks.json")["landmarks"] if l["id"] == "viltri_ravine")
    axis = next(a for a in lm["axes"] if a["id"] == "channel")["polyline"]
    px, pz = st["pass"]
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
    sea = [(px, pz)] + [tuple(p) for p in axis[bi + 1:]]
    lake = [(px, pz)] + [tuple(p) for p in axis[:bi + 1][::-1]]
    return (px, pz), sea, lake


def _densify(poly, step):
    xs, zs = [], []
    for (ax, az), (bx, bz) in zip(poly, poly[1:]):
        kk = max(1, int(math.ceil(math.hypot(bx - ax, bz - az))))
        for s in range(kk):
            xs.append(ax + (bx - ax) * s / kk)
            zs.append(az + (bz - az) * s / kk)
    xs.append(poly[-1][0])
    zs.append(poly[-1][1])
    return np.array(xs)[::step], np.array(zs)[::step]


def stream_half(ctx, st, hf):
    """One of the Viltri Ravine's two streams, rising at a spring beside the pass and running away from it: the sea
    half to the Mouth of Viltri, the lake half to Lake Viltri. The surface never rises downstream and is never held
    above ground it could spill over; where the floor dips below the surface the water stands as a pool (the lake
    half's counter-rises), deepest at the dips and no deeper than max_pool_depth below the lowest floor upstream,
    except where the lake itself holds it; where a rise would hold more, the lip is cut."""
    cfg = dict(st)
    cfg.update(hf)
    (px, pz), sea_poly, lake_poly = ravine_axis(st)
    poly = sea_poly if hf["direction"] == "to_sea" else lake_poly
    step = int(cfg["station_step_blocks"])
    xs, zs = _densify(poly, step)
    n = len(xs)
    tx, tz = np.gradient(xs), np.gradient(zs)
    tl = np.hypot(tx, tz)
    tl[tl == 0] = 1
    nx, nz = -tz / tl, tx / tl
    G = ctx.G0
    reach = int(cfg["thalweg_search_blocks"])
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
    ext = []
    end_level = SEA
    if hf["direction"] == "to_sea":
        # to the sea: steepest non-rising ground from the low end
        cx, cz = int(round(sx[-1])), int(round(sz[-1]))
        seen = {(cx, cz)}
        for _ in range(int(cfg["to_sea"]["max_extension_blocks"])):
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
                             "(stopped at (%d, %d), ground y%d)" % (cfg["to_sea"]["max_extension_blocks"], cx, cz, G[cz, cx]))
    else:
        # toward the lake: stop at the first station in the lake's own water, or in the painted channel of the course
        # the stream joins before it (join_course: the ravine's lake end is Viltri's Path's own channel, which flows
        # out of the lake), and end at that water's level
        lb = ctx.lake_bodies[hf["lake"]]
        end_level = int(lb["level"])
        join = hf.get("join_course")
        jfp = course_footprints(ctx).get(join) if join else None
        if jfp is not None:
            # the joined course's water as the painter lays it (its footprint is two blocks wider than its water)
            jc = ctx.revised_courses.get(join) or ctx.revised_courses_original[join]
            jb = jfp[0]
            jw, jlv = paint_water(ctx.G1, jc, jb)
        cut = None
        for i in range(n):
            zi, xi = int(round(sz[i])), int(round(sx[i]))
            if ctx.lake_mask[zi, xi] and G[zi, xi] < end_level:
                cut = i
                break
            if jfp is not None and jb[0] <= xi < jb[2] and jb[1] <= zi < jb[3] and jw[zi - jb[1], xi - jb[0]]:
                end_level = int(jlv[zi - jb[1], xi - jb[0]])
                cut = i
                break
        if cut is None:
            raise ShapeError("the ravine's lake half never reaches %s's water" % hf["lake"])
        sx, sz = sx[:cut + 1], sz[:cut + 1]
        ctx.stream_join = getattr(ctx, "stream_join", {})
        ctx.stream_join[hf["id"]] = {"joins": join if jfp is not None and not ctx.lake_mask[int(round(sz[-1])), int(round(sx[-1]))] else hf["lake"],
                                     "at": [int(round(sx[-1])), int(round(sz[-1]))], "level": end_level}
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
    inc = float(cfg["incision_blocks"])
    if hf["direction"] == "to_sea":
        surf = np.minimum.accumulate(flo - inc)
        surf = np.maximum(surf, SEA)
    else:
        # pools: fill every dip to its downstream lip (from the lake up), but never more than max_pool_depth over the
        # lowest floor upstream (the rest of a rise is cut), and never below the lake the stream feeds
        Lf = flo - inc
        Lf[-1] = end_level
        for i in range(m - 2, -1, -1):
            Lf[i] = max(Lf[i], Lf[i + 1])
        M = np.minimum.accumulate(flo - inc)
        surf = np.minimum(Lf, M + float(cfg["max_pool_depth_blocks"]))
        surf = np.minimum.accumulate(surf)
        surf = np.maximum(surf, end_level)
    Lold = np.floor(surf + 0.01).astype(int)
    Lold[-1] = end_level
    Lold = np.minimum.accumulate(Lold)
    jj = np.arange(m)
    rng = rng_for("stream", hf["id"])
    spacing = float(cfg["gather_every_blocks"])
    gathers = [0.0]
    while gathers[-1] < sg[-1]:
        gathers.append(gathers[-1] + spacing * (1.0 + 0.15 * (2 * rng.random() - 1)))
    gathers = np.array(gathers)
    placed = step_plan(sg, Lold, jj, gathers, 1, cfg.get("falls", []), rng)
    L0 = int(Lold[0])
    pos = np.array([p[0] for p in placed]) if placed else np.zeros(0)
    amt = np.array([p[1] for p in placed]) if placed else np.zeros(0)
    level = np.array([L0 - int(amt[pos <= v].sum()) for v in sg]) if len(pos) else np.full(m, L0)
    level = np.minimum(level, Lold)
    level = np.maximum(level, end_level)
    level[-1] = end_level
    # no step over one block but at a declared fall: where the end's level would make one (the mouth), the stations
    # above it come down a block a station (a short staircase of riffles; the water is only ever let down)
    allow = np.ones(m)
    for p, a_, kd in placed:
        if kd == "fall":
            jf = int(np.searchsorted(sg, p))
            for jj_ in (jf - 2, jf - 1, jf, jf + 1):
                if 0 <= jj_ < m:
                    allow[jj_] = max(allow[jj_], float(a_))
    once = False
    for j in range(m - 2, -1, -1):
        cap_ = allow[j]
        if cap_ > 1 and level[j] - level[j + 1] > 1:
            if once:
                cap_ = 1.0          # one fall a declared fall, however many stations it spans
            once = True
        level[j] = min(level[j], level[j + 1] + cap_)
    extra = np.zeros(m)
    zone = np.full(m, 3, np.int8)
    for p, a_, kd in placed:
        j = int(np.searchsorted(sg, p))
        extra[j:j + 5] = np.maximum(extra[j:j + 5], float(cfg["plunge_pool_extra_depth"]))
        zone[j:j + 5] = 5
        if kd == "fall" and j < m:
            zone[j] = 4
    # width grows downstream; pools take the width of the water the dip holds (never wider than the corridor)
    w0, w1 = cfg["width_blocks"] if isinstance(cfg["width_blocks"], list) else (cfg["width_blocks"], cfg["width_blocks"])
    width = w0 + (w1 - w0) * (sg / max(1.0, sg[-1]))
    ang = np.arctan2(np.gradient(zn), np.gradient(xn))
    nxn, nzn = -np.sin(ang), np.cos(ang)
    pool = (level - flo) >= 1.0
    cap = float(cfg.get("pool_max_width_blocks", 2 * cfg["corridor_half_width_blocks"]))
    for j in np.nonzero(pool)[0]:
        span = []
        for sgn in (1, -1):
            k = 0
            while k < cap / 2:
                x, z = int(round(xn[j] + sgn * nxn[j] * (k + 1))), int(round(zn[j] + sgn * nzn[j] * (k + 1)))
                if G[z, x] >= level[j]:
                    break
                k += 1
            span.append(k)
        width[j] = max(width[j], 2 * max(span) + 1)
        zone[j] = 1
    width = running(running(width, 9, "min"), 9, "mean") if len(width) > 9 else width
    width = np.maximum(width, w0 + (w1 - w0) * (sg / max(1.0, sg[-1])))
    hw = width / 2.0
    dmax = float(cfg["max_depth_blocks"])
    floor = level - np.maximum(1.0, np.minimum(dmax + extra, dmax + extra))
    floor = np.minimum(floor, np.where(pool, flo, floor))
    k = ctx.feature("stream:viltri_ravine_%s" % hf["id"], "stream")
    corridor = int(cfg["corridor_half_width_blocks"])
    pad = corridor + 12
    box = clip_box(xn.min() - pad, zn.min() - pad, xn.max() + pad + 1, zn.max() + pad + 1, ctx.N)
    best, idx, lat = stamp((xn, zn, nxn, nzn), box, lambda j: hw[j] + 4.0)
    has = idx >= 0
    J = np.maximum(idx, 0)
    lv = level[J].astype(float)
    hwJ = hw[J]
    inner = has & (best <= hwJ)
    lcut = running(level.astype(float), 5, "min")[J]
    fl = np.minimum(floor[J], lcut - 1.0)
    ts_in = np.minimum(fl + (lcut - 1 - fl) * np.clip(best / np.maximum(hwJ, 0.5), 0, 1) ** 2, lcut - 1)
    ts_out = lv - 1 + (best - hwJ) * 2.0
    target = np.floor(np.where(has, np.where(inner, ts_in, ts_out), 0.0) + 0.5).astype(np.int32)
    cur = ctx.G1[sl(box)].astype(np.int32)
    new = np.where(has & (best <= hwJ + 2.0), np.minimum(cur, target), cur)
    # the spring pool, eight blocks down from the pass
    sp = cfg["spring_pool"]
    j0 = min(m - 1, 8)
    zz, xx = np.mgrid[box[1]:box[3], box[0]:box[2]]
    rr = np.hypot(xx - xn[j0], zz - zn[j0])
    spool = rr <= float(sp["radius"])
    new = np.where(spool, np.minimum(new, (level[j0] - sp["depth"] + (rr / float(sp["radius"])) ** 2).astype(np.int32)), new)
    wet = (inner | spool) & (new < np.where(spool, level[j0], lv))
    lvl = np.where(spool, float(level[j0]), np.where(has, lv, -1e9))
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
    # a lake's own columns are the lake pass's (P5) and another course's painted channel is that course's: the stream
    # stops at their water and writes nothing inside them
    # (their painted water, not their footprint's two-block margin: the lake half meets Viltri's Path across it)
    others = np.zeros(cur.shape, bool)
    for cid, (fb_, _fm) in course_footprints(ctx).items():
        if fb_[0] < box[2] and box[0] < fb_[2] and fb_[1] < box[3] and box[1] < fb_[3]:
            crs = ctx.revised_courses.get(cid) or ctx.revised_courses_original.get(cid)
            if crs is not None:
                others |= paint_water(ctx.G1, crs, box)[0]
    ok = ctx.write(k, box, new.astype(np.int16), (new != cur) & ~ctx.lake_mask[sl(box)] & ~others)
    names = {1: "pool", 3: "cascade", 4: "fall", 5: "plunge_pool"}
    # reaches: one per run of equal (rounded) width, so the painter lays each pool as wide as its water
    # the course starts at the spring: the stations above it stand on the divide itself, dry by nature
    wr = np.rint(width).astype(int)
    s0 = float(sg[j0])
    reaches = []
    a0 = j0
    for j in range(j0 + 1, m + 1):
        if j == m or wr[j] != wr[a0]:
            reaches.append({"from_m": round(float(sg[a0]) - s0, 2), "to_m": round(float(sg[j - 1]) - s0, 2) if j < m else int(math.ceil(sg[-1] - s0)),
                            "catchment_km2": None, "grade": None, "water_body": False, "bank_slope": 2.0,
                            "bed": cfg["bed"], "width": int(wr[a0]), "depth": dmax, "incision": inc})
            a0 = j
    for r0, r1 in zip(reaches, reaches[1:]):
        r0["to_m"] = r1["from_m"]
    rec = {
        "id": hf["course_id"], "river": "viltri_ravine", "kind": "stream", "valid": True,
        "source": {"kind": "spring", "at": [round(float(xn[j0]), 1), round(float(zn[j0]), 1)], "level_y": int(level[j0]),
                   "pool": sp},
        "ends_in": "open_sea" if hf["direction"] == "to_sea" else hf["lake"],
        "end_at": {"x": int(round(xn[-1])), "z": int(round(zn[-1]))},
        "graded_polyline": [[round(float(xn[j]), 2), round(float(zn[j]), 2), float(level[j]), round(float(floor[j]), 2)]
                            for j in range(j0, m)],
        "graded_polyline_fields": ["x", "z", "surface_y", "floor_y"],
        "reaches": reaches,
        "water_shape": {"generator": "tools/water_shape.py", "half": hf["id"],
                        "steps": [{"s": round(p, 1), "drop": int(a), "kind": kd} for p, a, kd in placed],
                        "zones": [{"at_m": round(float(sg[j]), 1), "zone": names.get(int(zone[j]), "cascade")}
                                  for j in range(0, m, 10)],
                        "falls_declared": cfg.get("falls", [])},
    }
    ctx.revised_courses[hf["course_id"]] = rec
    # seal: the water as tools/paint_maps.py lays it (the reach widths, rounded) must not stand beside lower dry ground;
    # each such column is raised to the water's level (a bank), a few passes until none is left
    sealed = 0
    for _ in range(5):
        pw, plv = paint_water(ctx.G1, rec, box)
        g_ = ctx.G1[sl(box)].astype(np.int32)
        nl = np.zeros(g_.shape)
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a = (slice(max(0, dz), g_.shape[0] + min(0, dz)), slice(max(0, dx), g_.shape[1] + min(0, dx)))
            b = (slice(max(0, -dz), g_.shape[0] + min(0, -dz)), slice(max(0, -dx), g_.shape[1] + min(0, -dx)))
            sh = np.zeros(g_.shape)
            sh[a] = plv[b]
            nl = np.maximum(nl, sh)
        leak = ~pw & (g_ < nl) & (g_ >= SEA) & ~ctx.lake_mask[sl(box)] & ~others
        if not leak.any():
            break
        okl = ctx.write(k, box, np.where(leak, nl, g_).astype(np.int16), leak)
        sealed += int(okl.sum())
        if not okl.any():
            break
    pools = []
    j = 0
    while j < m:
        if pool[j]:
            e = j
            while e < m and pool[e]:
                e += 1
            pools.append({"from_m": round(float(sg[j]), 1), "to_m": round(float(sg[e - 1]), 1),
                          "level": int(level[j]), "deepest": int((level[j:e] - flo[j:e]).max()),
                          "widest": int(width[j:e].max())})
            j = e
        else:
            j += 1
    cutlip = np.maximum(0, flo - inc - surf)
    rep = {"course_id": hf["course_id"], "direction": hf["direction"], "length": round(float(sg[-1]), 1),
           "from_level": int(level[0]), "to_level": int(level[-1]), "spring_at": rec["source"]["at"],
           "extension_to_sea_blocks": len(ext), "steps": len(placed), "falls": [p for p in placed if p[2] == "fall"],
           "width": [round(float(width.min()), 1), round(float(np.median(width)), 1), round(float(width.max()), 1)],
           "pools": pools, "lip_cut_max_blocks": round(float(cutlip.max()), 1), "sealed_bank_columns": sealed,
           "ends": (getattr(ctx, "stream_join", {}) or {}).get(hf["id"]),
           "columns_written": int(ok.sum()), "held_protected": ctx.features[k]["held_protected"]}
    run = {"xn": xn, "zn": zn, "sg": sg, "level": level, "floor": floor, "flo": flo, "width": width}
    return rep, run


def stream_pass(ctx):
    ctx.report["stream"] = {}
    ctx.stream_run = {}
    st = ctx.spec.get("viltri_ravine_stream")
    if not st:
        # the ravine is on hold (data/water_shape.json viltri_ravine): nothing is shaped there
        ctx.report["stream"] = {}
        ctx.report["notes"].append("the Viltri Ravine is on hold: no stream is shaped (data/water_shape.json viltri_ravine)")
        return
    for hf in st["halves"]:
        rep, run = stream_half(ctx, st, hf)
        ctx.report["stream"][hf["id"]] = rep
        ctx.stream_run[hf["id"]] = run


# ---------------------------------------------------------------------------------------------------- lakes


def lake_measure(g, L, inside, factor, exclude=None, scope=None):
    wet = inside & (g < L)
    if not wet.any():
        return None
    depth = np.where(wet, L - g, 0)
    rest = ~wet | (depth <= 1)
    dist = distance_scaled(rest, wet, factor)
    obj = wet & ~(exclude if exclude is not None else np.zeros_like(wet))
    if scope is not None:
        obj &= scope
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


def site_toward_anchor(site, depth0, wet, anchor_zx, box):
    """(z, x) in the box of a site given by rule: the old water nearest to `toward_anchor_from` (a world point on the
    shore side), then along the line from there toward the lake's anchor until the old bed is `at_old_depth` deep."""
    fx, fz = site["toward_anchor_from"]
    zs, xs = np.nonzero(wet)
    i = int(np.argmin((xs + box[0] - fx) ** 2 + (zs + box[1] - fz) ** 2))
    z0, x0 = float(zs[i]), float(xs[i])
    az, ax = anchor_zx
    L = max(1.0, math.hypot(az - z0, ax - x0))
    for s in range(int(L) + 1):
        z = int(round(z0 + (az - z0) * s / L))
        x = int(round(x0 + (ax - x0) * s / L))
        if wet[z, x] and depth0[z, x] >= float(site["at_old_depth"]):
            return z, x
    return int(az), int(ax)


def keep_zone(kz, depth0, wet, anchor_zx, box_shape, box=None):
    az, ax = anchor_zx
    if "site" in kz:
        az, ax = site_toward_anchor(kz["site"], depth0, wet, anchor_zx, box)
    if "core_depth" in kz:
        return component_near(wet & (depth0 >= kz["core_depth"]), az, ax)
    zz, xx = np.mgrid[0:box_shape[0], 0:box_shape[1]]
    return np.hypot(zz - az, xx - ax) <= float(kz["radius"])


def rest_scope(body, wet, dshore0, brg, keeps):
    """Where a lake's rest budget applies as a farthest-point limit: the whole lake, or (a body's rest_scope, decision 8
    read literally) the water within `within_blocks_of_shore` of the shore in named bearing sectors. A rest_scope's
    dive_sites are held to the budget differently: each needs a rest point within the budget (dive_site_reach)."""
    sc = body.get("rest_scope")
    if not sc:
        return wet.copy()
    m = np.zeros(wet.shape, bool)
    secs = {s["id"]: s for s in body.get("sectors", [])}
    for s in sc.get("sectors", []):
        m |= in_bearing(brg, secs[s["sector"]]["bearing_from_anchor_deg"]) & (dshore0 <= float(s["within_blocks_of_shore"]))
    return m & wet


def dive_site_reach(zone, rest, wet, factor):
    """Blocks from a dive site's edge to the nearest ground a swimmer can stand on (through water)."""
    if not zone.any():
        return None
    d = distance_scaled(rest, wet | rest, factor)
    return float(d[zone].min())


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
    # never shape under a river's painted channel: a shelf across an outlet would seal the lake
    prot = ctx.P[sl(box)] | (ctx.owner[sl(box)] != 0) | footprint_in(ctx, box)
    editable = wet & (depth0 >= 2) & ~prot
    factor = 1 if H * W <= 400000 else (2 if H * W <= 2500000 else 4)
    anc = lb["landmark"]["anchor"]
    anchor_zx = (int(anc["z"]) - box[1], int(anc["x"]) - box[0])
    rng = rng_for("lake", body["id"])
    dshore = distance_scaled(~wet, wet, factor)
    B = 1.0 - box_mean(wet, int(dflt["bay_radius_blocks"]))
    wmin, wmax = body["shelf_width"]
    # how enclosed the SHORE is, carried out over the water beside it: a column 20 blocks out takes the bayness of
    # the shore it belongs to, not its own (its own window is mostly water, so every shelf came out at the narrow end)
    shore = wet & dilate4(~wet)
    rs = int(max(wmax, max((s["shelf_width"][1] for s in body.get("sectors", [])), default=0))) + 4
    den = box_mean(shore, rs)
    Bs = np.where(den > 1e-9, box_mean(np.where(shore, B, 0.0), rs) / np.maximum(den, 1e-9), B)
    bay = np.clip((Bs - 0.35) / 0.30, 0.0, 1.0)
    Wsh = wmin + (wmax - wmin) * bay
    zz, xx = np.mgrid[0:H, 0:W]
    brg = bearing_deg(xx - anchor_zx[1], zz - anchor_zx[0])
    for sec in body.get("sectors", []):
        m = in_bearing(brg, sec["bearing_from_anchor_deg"])
        a, b = sec["shelf_width"]
        Wsh = np.where(m, a + (b - a) * bay, Wsh)
    # the shelf's edge wanders: a ring of one width reads as a swimming pool's step, not a lake's shelf
    swn = float(dflt.get("shelf_width_noise", 0.3))
    nsh = value_noise(xx + box[0], zz + box[1], float(dflt.get("shelf_noise_scale_blocks", 56)), seed_of("shelf", body["id"]))
    Wsh = Wsh * (1.0 + swn * (2.0 * nsh - 1.0))
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
    # two octaves: broad swells and a little fine ripple (one octave at 24 read as speckle where the floor sat on a
    # colour band's edge)
    nz = value_noise(xx + box[0], zz + box[1], dflt["floor_noise_scale_blocks"], seed_of("lakefloor", body["id"]))
    nz2 = value_noise(xx + box[0], zz + box[1], float(dflt.get("floor_fine_scale_blocks", 20)), seed_of("lakefloor2", body["id"]))
    Tf = np.maximum(dd, Tf + (nz - 0.5) * 2.0 * float(dflt["floor_noise_blocks"])
                    + (nz2 - 0.5) * 2.0 * float(dflt.get("floor_fine_blocks", 0.5)))
    Tt = np.where(floor_m, Tf, Tt)
    # an arm or a bay that was shallow stays shallower than the main basin: the drop-off and floor never go more
    # than local_deepen_blocks below the deepest old bed within local_radius_blocks (a narrow arm 6 deep is not
    # dug out to the basin's drop_depth)
    lr = int(dflt.get("local_radius_blocks", 32))
    Dloc = running_max2d(depth0.astype(np.float64), lr)
    Tt = np.minimum(Tt, np.maximum(2.0, Dloc + float(dflt.get("local_deepen_blocks", 2))))
    zone = np.where(dshore <= Wsh, np.where(Bs > 0.6, 6, 1), np.where(drop, 2, 3)).astype(np.uint8)
    # keep zones and flattened zones
    keeps = {}
    keep_all = np.zeros((H, W), bool)
    for kz in body.get("keep", []):
        km = keep_zone(kz, depth0, wet, anchor_zx, (H, W), box)
        keeps[kz["id"]] = km
        keep_all |= km
    if keep_all.any():
        # a kept pit is the old bed exactly; round it the floor eases back to the old bed over keep_blend_blocks,
        # both ways (the first run eased only where the design was deeper, so a pit ringed by a shallower new floor
        # read as a hard-edged dark blob). The pit keeps its walls because the old bed round it is its own slope
        kbl = float(body.get("keep_blend_blocks", dflt.get("keep_blend_blocks", 32)))
        wk = np.clip(distance_scaled(keep_all, None, factor) / kbl, 0.0, 1.0)
        Tt = np.where(floor_m | drop, depth0 + (Tt - depth0) * smoothstep(wk), Tt)
    Tt = np.where(keep_all, depth0.astype(float), Tt)
    zone[keep_all & wet] = 7
    for fz in body.get("flatten", []):
        fm = keep_zone(fz, depth0, wet, anchor_zx, (H, W), box)
        keeps[fz["id"]] = fm
        # a flattened floor fades into the floor round it over its blend (a disc set to one depth read as a stamp)
        fbl = float(fz.get("blend_blocks", 24))
        wf = 1.0 - smoothstep(distance_scaled(fm, None, factor) / fbl)
        wf = np.where(fm, 1.0, wf) * (floor_m | drop)
        Tt = Tt + (float(fz["to_depth"]) - Tt) * wf * ~keep_all
        zone[fm & ~keep_all] = 3
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
        # a hump is an irregular swell, not a cone: its radius wobbles with the bearing
        ang = np.arctan2(zz - z, xx - x)
        wob = 1.0 + 0.3 * (value_noise(np.cos(ang) * 2.0 + x, np.sin(ang) * 2.0 + z, 1.3, seed_of("hump", body["id"], x, z)) - 0.5)
        d = np.hypot(zz - z, xx - x) / wob
        mound = top + (Tt - top) * smoothstep(d / r)
        m = (d <= r) & ~keep_all
        zone[m & (mound < Tt - 0.5)] = 4
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
    # shoals: sunken islands. The declared ones first (a rest point by a dive site), then the lake's natural ones
    # (where the old floor was already highest), then only as many as the rest budget still needs
    sd = dflt["shoal"]
    shoals = []
    size_lo, size_hi = body.get("shoal_size", sd.get("size", [8, 20]))

    def shoal_profile(z, x, R, rs):
        """An irregular sunken island round (z, x), about R blocks across its crest: a warped, lobed outline (two
        octaves of noise on the radius, a mild random elongation at any angle), a crest 1 deep with 2-deep saddles, a
        sand apron to 3 deep and a flank to the floor whose steepness varies from shoal to shoal. The first run's
        elongated crests on one trend read as streaks; these read as islands that did not quite reach the surface."""
        ang = rs.uniform(0.0, math.pi)
        asp = rs.uniform(1.0, 1.7)
        du = (xx - x) * math.cos(ang) + (zz - z) * math.sin(ang)
        dv = -(xx - x) * math.sin(ang) + (zz - z) * math.cos(ang)
        rho = np.hypot(du / (R * math.sqrt(asp)), dv / (R / math.sqrt(asp)))
        s0 = seed_of("shoal", body["id"], int(x), int(z))
        n1 = value_noise(xx + box[0], zz + box[1], max(4.0, R * 0.9), s0)
        n2 = value_noise(xx + box[0], zz + box[1], max(3.0, R * 0.35), s0 + 1)
        rho = rho * (1.0 + 0.55 * (n1 - 0.5) + 0.3 * (n2 - 0.5))
        c = rs.uniform(0.4, 0.65)
        out = np.maximum(0.0, rho - c) * R
        sa = rs.uniform(0.45, 0.8)
        fl_lo, fl_hi = body.get("shoal_flank", [sd.get("flank_min", 0.35), sd.get("flank_max", 0.8)])
        sf = rs.uniform(float(fl_lo), float(fl_hi))
        run_a = 2.0 / sa
        v = np.where(out <= run_a, 1.0 + out * sa, 3.0 + (out - run_a) * sf)
        n3 = value_noise(xx + box[0], zz + box[1], max(3.0, R * 0.3), s0 + 2)
        v = np.where((out <= 0) & (rho > c * 0.55) & (n3 > 0.62), 2.0, v)
        return v, out, run_a

    # a shoal's flank fades out beside a kept pit (a ring of shoals round the pit's rim left it hard-edged); only a
    # declared shoal, a rest point placed there on purpose, keeps its full flank
    kmargin = float(sd.get("keep_margin_blocks", 40))
    kdist = distance_scaled(keep_all, None, factor) if keep_all.any() else np.full((H, W), 1e9, np.float32)
    kfade = smoothstep(kdist / max(1.0, kmargin))
    kfade_declared = smoothstep(kdist / 16.0)

    def put_shoal(z, x, why, R=None, declared=False):
        rs = rng_for("shoal", body["id"], int(x), int(z))
        R = float(R if R is not None else size_lo + (size_hi - size_lo) * rs.random() ** 1.5)
        v, out, run_a = shoal_profile(z, x, R, rs)
        v = np.where(v < Tt, Tt + (v - Tt) * (kfade_declared if declared else kfade), v)
        m = ~keep_all & (v < Tt) & wet
        zone[m & (out <= run_a)] = 5
        crest = int((m & (v <= 1.0)).sum())
        return np.where(m, np.minimum(Tt, v), Tt), {"at": [int(x) + box[0], int(z) + box[1]], "why": why,
                                                    "size": round(R, 1), "crest_columns": crest}

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
        Tt, rec = put_shoal(zs_[i], xs_[i], s.get("why", "near %s" % s["target"]), R=s.get("size"), declared=True)
        shoals.append(rec)
    nat = body.get("natural_shoals")
    if nat:
        # the open water's own islands: where the old floor stood highest (broadly, not a single column), far from
        # the shore and from each other
        hi_ground = box_mean(np.where(wet, depth0, 0.0), 12) / np.maximum(box_mean(wet, 12), 1e-6)
        okn = editable & ~keep_all & floor_m & (dshore >= float(nat["min_from_shore_blocks"]))
        kd = distance_scaled(keep_all | excl, None, factor) if (keep_all | excl).any() else np.full((H, W), 1e9)
        okn &= kd >= float(nat.get("min_from_kept_blocks", 60))
        taken = []
        for _ in range(int(nat["count"])):
            if not okn.any():
                break
            vals = np.where(okn, hi_ground, 1e9)
            z, x = np.unravel_index(int(np.argmin(vals)), vals.shape)
            R = rng.uniform(*nat["size"])
            Tt, rec = put_shoal(z, x, "a natural island of the open lake: the old floor's broad high at %.0f deep" % depth0[z, x], R=R)
            rec["natural"] = True
            shoals.append(rec)
            taken.append((z, x))
            okn &= np.hypot(zz - z, xx - x) >= float(nat["min_spacing_blocks"])
    rung = lakes["rungs"][body["rung"]]
    target = float(body.get("max_to_rest_blocks", rung["max_to_rest_blocks"]))
    auto = any(s["kind"] == "auto" for s in body.get("shoals", []))
    scope = rest_scope(body, wet, dshore, brg, keeps)
    site_reach = {}
    for sid in (body.get("rest_scope") or {}).get("dive_sites", []):
        zm = keeps.get(sid)
        if zm is None or not zm.any():
            raise ShapeError("%s: dive site %s is not a declared zone" % (body["id"], sid))
        r0 = dive_site_reach(zm, ~wet | (Tt <= 1.0), wet, factor)
        if r0 is not None and r0 > target:
            dz_ = distance_scaled(zm, None, factor)
            okd = editable & ~keep_all & (dz_ >= 10) & (dz_ <= 30)
            if okd.any():
                zs_, xs_ = np.nonzero(okd)
                i = int(np.argmin(dshore[zs_, xs_]))
                Tt, rec = put_shoal(zs_[i], xs_[i], "rest point for the dive site %s (it was %.0f from rest)" % (sid, r0),
                                    declared=True)
                shoals.append(rec)
        site_reach[sid] = dive_site_reach(zm, ~wet | (Tt <= 1.0), wet, factor)
    fcoarse = max(2, factor)
    for it in range(int(body.get("max_shoals", sd["max_count"]))):
        if not auto:
            break
        rest = ~wet | (Tt <= 1.0)
        dist = distance_scaled(rest, wet, fcoarse)
        obj = scope & ~excl
        if not obj.any() or float(dist[obj].max()) <= target:
            break
        over = obj & (dist > target)
        # fewer, better-placed shoals: of a sample of candidates in the far water, take the one that brings the most
        # over-budget water within reach (the farthest-point rule the first run used needed many more)
        rs = rng_for("shoal_pick", body["id"], it)
        R = size_lo + (size_hi - size_lo) * rs.random() ** 1.5
        oz, ox = np.nonzero(over[::4, ::4])
        oz, ox = oz * 4, ox * 4
        best, bz, bx = -1.0, None, None
        reach = target + R * 0.6
        near_kept = False
        # away from the kept pits first; only if nothing there reaches the far water, anywhere editable (and then the
        # shoal keeps its full flank, or it would not reach the surface)
        for pass_i, okc in enumerate((editable & ~keep_all & (dist > target * 0.5) & (kdist >= kmargin),
                                      editable & ~keep_all & (dist > target * 0.5))):
            if not okc.any():
                continue
            cz, cx = np.nonzero(okc)
            pick = [rs.randrange(len(cz)) for _ in range(min(160, len(cz)))]
            for i in pick:
                z, x = int(cz[i]), int(cx[i])
                cover = float(((oz - z) ** 2 + (ox - x) ** 2 <= reach * reach).sum())
                natural = 1.0 - min(1.0, depth0[z, x] / max(1.0, Dmax))
                score = cover * (1.0 + 0.5 * natural)
                if score > best:
                    best, bz, bx = score, z, x
            if best > 0:
                near_kept = pass_i == 1
                break
        if bz is None:
            break
        Tt, rec = put_shoal(bz, bx, "rest point: the farthest water in scope from anywhere to stand was %.0f blocks"
                            % dist[obj].max(), R=R, declared=near_kept)
        shoals.append(rec)
    # ease back to the old bed toward protected ground (a platform's box, a river's channel): the run left each
    # event site's box a sharp rectangle of old bed in the new floor
    if prot.any():
        wpb = smoothstep(distance(prot, None, max_iter=int(dflt.get("protect_blend_blocks", 12)) + 2)
                         / float(dflt.get("protect_blend_blocks", 12)))
        Tt = np.where(editable, depth0 + (Tt - depth0) * wpb, Tt)
    Ti = np.clip(np.rint(Tt), 1, None).astype(np.int32)
    new = np.where(editable, L - Ti, g0)
    new = np.minimum(new, np.where(wet, L - 1, new))
    k = ctx.feature("lake:" + body["id"], "lakes")
    before = lake_measure(g0, L, inside, factor)
    ok = ctx.write(k, box, new.astype(np.int16), editable)
    g1 = ctx.G1[sl(box)].astype(np.int32)
    after = lake_measure(g1, L, inside, factor, exclude=excl, scope=scope if body.get("rest_scope") else None)
    if body.get("rest_scope"):
        whole = lake_measure(g1, L, inside, factor, exclude=excl)
        after["whole_lake_max_to_rest"] = whole["max_to_rest"]
    dv = g1 - g0
    zone[~wet] = 0
    ctx.zone_maps["lake_" + body["id"]] = {"box": box, "zones": zone}
    ctx.report["lakes"][body["id"]] = {
        "level": L, "rung": body["rung"], "stage": body["stage"], "box": list(box),
        "before": before, "after": after,
        "rest_scope": body.get("rest_scope") or "the whole lake", "scope_columns": int(scope.sum()),
        "dive_site_to_rest": {k: (round(v, 1) if v is not None else None) for k, v in site_reach.items()},
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
        # the region polygons stop short of the beach (Pallet's by 25-40 blocks): grown only 24, the shore itself was
        # not a source, the water beside it measured 200+ blocks from shore, and the first run laid bars on a
        # sixth of the coast. The region is grown far enough to take in its own beach
        rb, rm = ctx.region_mask(f["shore_region"], int(f.get("shore_region_grow_blocks", 96)))
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
    seed = seed_of("flats", f["id"])
    bump = np.zeros((H, W))
    # a bar wanders in and out along the shore and swells and thins: bars at fixed offsets read on the maps as
    # contour lines drawn round the coast
    wav = float(bars.get("wander_blocks", 6.0))
    seg_scale = float(bars.get("segment_scale_blocks", 0.0))
    for i, o in enumerate(bars["offsets_blocks"]):
        wo = (2.0 * value_noise(xx, zz, 110.0, seed + 31 + i) - 1.0) * wav
        # crescents: a second, shorter wander bends each bar seaward and back between its gaps
        wo = wo + (2.0 * value_noise(xx, zz, 45.0, seed + 61 + i) - 1.0) * wav * 0.6
        sg = sig * (0.65 + 0.7 * value_noise(xx, zz, 70.0, seed + 47 + i))
        b_i = np.exp(-((dl - o - wo) / sg) ** 2)
        if seg_scale > 0:
            # a bar is a string of segments, each ending in a rounded tip, with gaps where the rip current runs: a
            # noise along the coast switches it on and off (the run's unbroken bars read as contour streaks)
            on = value_noise(xx, zz, seg_scale * (1.0 + 0.25 * i), seed + 73 + i)
            b_i = b_i * smoothstep((on - float(bars.get("segment_gap_under", 0.42))) / 0.16)
        bump = np.maximum(bump, b_i)
    crest, runnel = float(bars["crest_depth"]), float(bars["runnel_depth"])
    Tt = runnel - (runnel - crest) * bump
    if seg_scale > 0:
        # the rips are the gaps: water runs out through them, a block deeper than the runnel, and fades out seaward
        # soft-edged: strongest in the middle of a gap and across the bar's own line, fading out on every side (the
        # first cut of this made hard-cornered patches of 3-deep water)
        strength = np.zeros(bump.shape)
        for i, o in enumerate(bars["offsets_blocks"]):
            on = value_noise(xx, zz, seg_scale * (1.0 + 0.25 * i), seed + 73 + i)
            g_ = smoothstep((float(bars.get("segment_gap_under", 0.42)) - 0.02 - on) / 0.12)
            strength = np.maximum(strength, g_ * np.exp(-((dl - o) / (2.2 * sig)) ** 2))
        rip = strength > 0.5
        Tt = Tt + (np.maximum(Tt, float(bars["rip_depth"])) - Tt) * strength
    else:
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
    # bars ease back into the old bed toward an exclusion or the box's edge instead of stopping square
    edge_src = ex | ~inbox | ctx.P[sl(box)]
    # over 48 blocks with a wandering reach (12 still read as the box's straight edge on the south strand's east end)
    ew = 48.0 * (0.6 + 0.8 * value_noise(xx, zz, 40.0, seed + 91))
    wfe = np.clip(distance(edge_src, None, max_iter=80) / ew, 0.0, 1.0)
    Tt = depth0 + (Tt - depth0) * smoothstep(wfe)
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
    ok = ctx.write(k, box, new.astype(np.int16), zone, over=("seabed",))
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
    nb0 = max(1, int(math.ceil(Lw / (maxrun + (lo_l + hi_l) / 2.0))))
    result, best = None, None
    # decision 7 wants the crossing made WITH warnings: too many or too long bars rest the swimmer so often that
    # the fatigue never shows. Try the fewest bars first; take the first layout with no run over the limit, no
    # hit and a warning; failing that, the one with no hit and the highest peak
    plans = [(n, t) for n in range(max(1, nb0 - 1), nb0 + 6) for t in range(3)]
    for attempt, (nb, _t) in enumerate(plans):
        bars = []
        Tt = np.full(g0.shape, 99.0)
        for i in range(nb):
            c = s0 + (i + 0.5) * Lw / nb
            ln = rng.uniform(lo_l, hi_l)
            wd = rng.uniform(lo_w, hi_w)
            off = fb["stagger_blocks"] * (1 if i % 2 else -1)
            # an elongated, lobed crest (a sand bar, not a domino): an ellipse whose rim wobbles, skewed a little
            # across the line so no two bars sit square to it
            skew = rng.uniform(-0.25, 0.25)
            uu = (U - c) + skew * (V - off)
            ring = np.hypot(uu / (ln / 2.0 * 0.7), (V - off) / (wd / 2.0 * 0.7))
            wob = value_noise(xx, zz, 7.0, seed_of("fungal_bar", attempt, i))
            ring = ring * (1.0 + 0.3 * (wob - 0.5))
            out = np.maximum(0.0, ring - 1.0) * (wd / 2.0 * 0.7)
            v = float(fb["crest_depth"]) + out / fr
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
        cand = (new, want, bars, mx * step, hits, peak)
        if mx * step <= maxrun and not hits:
            if peak >= S["warn_ticks"]:
                result = cand
                break
            if best is None or peak > best[5]:
                best = cand
    if result is None:
        if best is None:
            raise ShapeError("no Fungal bar layout keeps every 3-deep run within %s blocks without a hit" % maxrun)
        result = best
    new, want, bars, mx, hits, peak = result
    k = ctx.feature("coast:fungal_bar_chain", "coasts")
    ok = ctx.write(k, box, new.astype(np.int16), want, over=("seabed",))
    g1 = ctx.G1[sl(box)].astype(np.int32)
    ctx.report["coasts"]["fungal_bar_chain"] = {
        "line": [list(a), list(b)], "bars": bars, "bar_count": len(bars), "max_deep_run_planned": round(mx, 1),
        "unaided_walk_planned": outcome(hits), "unaided_peak_planned": round(peak), "peak_word": peak_word(peak, S),
        "columns_written": int(ok.sum()), "fill_blocks": int((g1 - g0)[ok].sum()),
        "held_protected": ctx.features[k]["held_protected"],
        "note": "the walk here is the generator's own planning check; the audit re-walks the line on the written copy"}
    ctx.features[k]["columns_written"] = int(ok.sum())


def reef_pass(ctx):
    """The Relic reef platform on the islet's south and west apron, as ground that grew there: it starts at the islet's
    own edge (its apron stands at sea - 4, so the platform meets it with no moat), shoals gently outward to an
    irregular outer rim, falls to the old bed down a reef wall of varying width, fades out over the sector's ends
    instead of stopping on a bearing, and carries patch reefs where two octaves of noise stand highest. The run's
    platform started at a fixed radius 34 and read as a sickle cut against the deep basin, its knolls as crosses."""
    rf = ctx.spec["coasts"]["relic_reef"]
    cx, cz = rf["centre"]
    R = rf["outer_radius"][1] + rf["drop_width_blocks"] * 3 + 24
    box = clip_box(cx - R, cz - R, cx + R + 1, cz + R + 1, ctx.N)
    zz, xx = np.mgrid[box[1]:box[3], box[0]:box[2]]
    b = bearing_deg(xx - cx, zz - cz)
    lo, hi = rf["sector_bearing_deg"]
    fade_deg = float(rf.get("sector_fade_deg", 40))
    # inside the sector the weight is 1; it falls to 0 over fade_deg beyond each end (the end wobbles with distance)
    beyond = np.minimum(((lo - b) % 360), ((b - hi) % 360))
    inside = in_bearing(b, rf["sector_bearing_deg"])
    wob = (value_noise(xx, zz, 50.0, seed_of("reef_end")) - 0.5) * fade_deg * 0.6
    w_ang = np.where(inside, 1.0, 1.0 - smoothstep((beyond + wob) / fade_deg))
    g0 = ctx.G1[sl(box)].astype(np.int32)
    depth0 = SEA - g0
    sea = sea_in_box(ctx, box)
    # distance from the islet's own outline (tools/islet.py), not from its centre
    import islet as I
    top, _ = I.island_top(None, SEA)
    on = ~np.isnan(np.asarray(top, float))
    isl = np.zeros(g0.shape, bool)
    ix0, iz0 = I.CENTRE[0] - I.RADIUS - box[0], I.CENTRE[1] - I.RADIUS - box[1]
    isl[iz0:iz0 + on.shape[0], ix0:ix0 + on.shape[1]] = on
    di = distance(isl, None, max_iter=R + 10)
    nzv = value_noise(xx, zz, 36.0, seed_of("reef"))
    nz2 = value_noise(xx, zz, 13.0, seed_of("reef2"))
    ro = (rf["outer_radius"][0] - rf["inner_radius"]) + (rf["outer_radius"][1] - rf["outer_radius"][0]) * (0.75 * nzv + 0.25 * nz2)
    t = np.clip(di / np.maximum(1.0, ro), 0.0, 1.0)
    top_in, top_out = float(rf["top_depth_inner"]), float(rf["top_depth_outer"])
    Tp = top_in + (top_out - top_in) * smoothstep(t) ** 0.8 + (value_noise(xx, zz, 22.0, seed_of("reef3")) - 0.5) * 2.0
    plat = sea & (di <= ro) & (w_ang > 0)
    dw = float(rf["drop_width_blocks"]) * (1.0 + 1.6 * value_noise(xx, zz, 28.0, seed_of("reef_wall")))
    wall = sea & (di > ro) & (di <= ro + dw) & (w_ang > 0)
    tw = np.clip((di - ro) / np.maximum(1.0, dw), 0.0, 1.0)
    Tt = np.where(plat, Tp, np.where(wall, top_out + (depth0 - top_out) * smoothstep(tw), 99.0))
    # patch reefs: where two octaves of noise stand highest on the platform, rising up to rise_blocks above it
    pr = rf["knolls"]
    pn = 0.65 * value_noise(xx, zz, float(pr.get("scale_blocks", 16)), seed_of("patch")) + \
        0.35 * value_noise(xx, zz, 6.0, seed_of("patch2"))
    thr = float(pr.get("noise_over", 0.68))
    rise = np.clip((pn - thr) / max(1e-6, 1.0 - thr), 0.0, 1.0) * float(pr.get("rise_blocks", 4))
    Tt = np.where(plat, Tt - rise, Tt)
    Tt = np.maximum(Tt, float(rf["min_depth"]))
    # the sector's ends ease back into the old bed; so does the ground beside protected columns, except at the islet
    # itself, whose apron the platform is meant to meet
    Tt = np.where(Tt < depth0, depth0 - (depth0 - Tt) * w_ang, Tt)
    Pb = ctx.P[sl(box)]
    if Pb.any():
        wp = np.clip((distance(Pb, None, max_iter=16) - 1.0) / 8.0, 0.0, 1.0)
        near_islet = distance(isl, None, max_iter=8) <= 5
        wp = np.where(near_islet, 1.0, wp)
        Tt = np.where(Tt < depth0, depth0 - (depth0 - Tt) * smoothstep(wp), Tt)
    want = sea & (plat | wall) & (Tt < depth0) & (depth0 >= rf["min_depth"])
    new = np.where(want, SEA - np.rint(Tt).astype(np.int32), g0)
    k = ctx.feature("coast:relic_reef", "coasts")
    ok = ctx.write(k, box, new.astype(np.int16), want, over=("seabed",))
    g1 = ctx.G1[sl(box)].astype(np.int32)
    patches = plat & (rise >= 1.0)
    ctx.report["coasts"]["relic_reef"] = {
        "platform_columns": int((plat & sea).sum()), "columns_written": int(ok.sum()),
        "fill_blocks": int((g1 - g0)[ok].sum()), "shallowest_depth_after": int((SEA - g1)[ok].min()) if ok.any() else None,
        "patch_reef_columns": int(patches.sum()),
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
    ok = ctx.write(k, box, new.astype(np.int16), want_m, over=("seabed",))
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
    ok = ctx.write(k, box, new.astype(np.int16), want, over=("seabed",))
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


# ---------------------------------------------------------------------------------------------------- the bank


def bank_island(ctx):
    """(box, island mask) of the land data/water_shape.json jungle_isle_bank removes: the region's polygons grown
    region_grow_blocks, where the canonical ground stands at or above the sea. Cached."""
    if getattr(ctx, "_bank_island", None) is not None:
        return ctx._bank_island
    bk = ctx.spec["jungle_isle_bank"]
    pad = int(bk["apron_blocks"]) + 48
    rb, rm = ctx.region_mask(bk["region"], int(bk["region_grow_blocks"]))
    box = clip_box(rb[0] - pad, rb[1] - pad, rb[2] + pad, rb[3] + pad, ctx.N)
    m = np.zeros((box[3] - box[1], box[2] - box[0]), bool)
    m[rb[1] - box[1]:rb[3] - box[1], rb[0] - box[0]:rb[2] - box[0]] = rm
    island = m & (ctx.G0[sl(box)] >= SEA)
    ctx._bank_island = (box, island)
    return ctx._bank_island


def bank_footprint(ctx):
    """The bank's footprint over bank_island's box: the island grown by its apron."""
    if getattr(ctx, "_bank_fp", None) is not None:
        return ctx._bank_fp
    bk = ctx.spec["jungle_isle_bank"]
    box, I = bank_island(ctx)
    ctx._bank_fp = distance_scaled(I, None, 2) <= float(bk["apron_blocks"])
    return ctx._bank_fp


def resited_town(ctx):
    """The re-sited sea town's elements and buildings (data/sea_town.json resite, translated by tools/sea_town.py),
    by district: {district: [rects]}, and the deck cells. Pure geometry; cached."""
    if getattr(ctx, "_town", None) is not None:
        return ctx._town
    import sea_town as ST
    plan = ST.load(resite=True)
    by_d = {}
    deck = set()
    for e in ST.elements(plan):
        if e["district"] == "mainland_jetty":
            continue
        by_d.setdefault(e["district"], []).append((e["kind"], e["rect"], e["min_depth"]))
        if not e["decor"]:
            deck |= ST.cells(e["rect"])
    for b in plan["buildings"]:
        by_d.setdefault(b["district"], []).append((b["type"], b["rect"], 1))
    ctx._town = {"plan": plan, "by_district": by_d, "deck": deck}
    return ctx._town


def bank_pass(ctx):
    """The Jungle Isle removed to a shallow sea bank, with Pacifidlog's shallows and its blue hole (the owner's
    decision of 2026-09-27; data/water_shape.json jungle_isle_bank). The island's land goes down to a bank whose
    depth follows the old island's own relief (its high ground the bank's crown, its coast the bank's edge), the old
    shore apron is cut to continue the bank's edge out to the sea floor, the town's footprint is shaped for its posts
    (rafts over 3-5, sand shallows 1-2 round the Stilt Quarter and the yard) and fades into the bank, and a blue hole
    opens off Fishers' Row's head. Nothing is left at or above the sea."""
    bk = ctx.spec["jungle_isle_bank"]
    box, I = bank_island(ctx)
    g0 = ctx.G1[sl(box)].astype(np.float64)
    G0b = ctx.G0[sl(box)].astype(np.float64)
    H, W = I.shape
    zz, xx = np.mgrid[box[1]:box[3], box[0]:box[2]]
    d0 = SEA - g0
    dp = bk["depth"]
    crest, edge = float(dp["crest"]), float(dp["edge"])
    # inland distance from the old coast, and seaward distance from it
    din = distance_scaled(~I, I, 4)
    dout = distance_scaled(I, ~I, 2)
    # the old island's relief, smoothed and ranked: high ground becomes the crown
    hs = box_mean(np.where(I, G0b, 0.0), 24) / np.maximum(box_mean(I.astype(float), 24), 1e-6)
    lo_h, hi_h = np.percentile(hs[I], 10), np.percentile(hs[I], 90)
    rel = np.clip((hs - lo_h) / max(1.0, hi_h - lo_h), 0.0, 1.0)
    ramp = smoothstep(din / float(dp["inland_ramp_blocks"]))
    rn = value_noise(xx, zz, float(dp["relief_scale_blocks"]), seed_of("bank_relief"))
    rn2 = value_noise(xx, zz, float(dp["relief_scale_blocks"]) * 0.35, seed_of("bank_relief2"))
    relief = ((rn - 0.5) * 2.0 * 0.75 + (rn2 - 0.5) * 2.0 * 0.25) * float(dp["relief_blocks"])
    d_in = edge - (edge - crest) * (rel ** 0.8) * ramp + relief * ramp
    d_in = np.clip(d_in, float(dp["min_off_town"]), None)
    # the old shore apron: continue the bank's edge outward at edge_slope until it meets the (filled) sea floor
    sw = value_noise(xx, zz, 60.0, seed_of("bank_edge")) * 0.6 + 0.7
    # capped a few blocks under the edge: it only takes away the old island's beach ramp (shallower than the bank),
    # never digs a moat into the sea floor's fill round it
    d_out = edge + np.minimum(dout * float(dp["edge_slope"]) * sw, float(dp.get("apron_max_extra", 4))) + relief * 0.5
    T = np.where(I, d_in, np.maximum(d_out, d0))
    apron = ~I & (dout <= float(bk["apron_blocks"])) & (d0 < d_out)
    # the town: rafts over raft_depth, the shallows under the Stilt Quarter and the yard, faded into the bank
    tw = bk["town"]
    town = resited_town(ctx)
    raft_m = np.zeros((H, W), bool)
    shal_m = np.zeros((H, W), bool)
    need = np.zeros((H, W))                              # the least depth each deck cell's kind allows
    for dist_, items in town["by_district"].items():
        for kind, (x0, z0, x1, z1), mind in items:
            a0, a1 = max(0, z0 - box[1]), min(H, z1 - box[1] + 1)
            b0, b1 = max(0, x0 - box[0]), min(W, x1 - box[0] + 1)
            if a1 <= a0 or b1 <= b0:
                continue
            if dist_ in tw["shallows_for"]:
                shal_m[a0:a1, b0:b1] = True
            else:
                raft_m[a0:a1, b0:b1] = True
            need[a0:a1, b0:b1] = np.maximum(need[a0:a1, b0:b1], float(mind))
    # the shallows are a sand flat of their own shape, not the buildings' outline grown: their reach wanders on noise
    sgw = float(tw["shallows_grow_blocks"])
    sn = value_noise(xx, zz, 24.0, seed_of("town_shallows")) * 0.7 + value_noise(xx, zz, 8.0, seed_of("town_shallows2")) * 0.3
    shal_zone = distance(shal_m, None, max_iter=int(sgw * 1.8) + 2) <= sgw * (0.35 + 1.4 * sn)
    shal_zone |= shal_m
    # the boatwright's slipway steps down a block a block into the water (tools/sea_town.py): under it, and a short
    # dredged slip beyond its foot, the bed stands a block under each step (the Sound's deep water gave it that)
    sw_ = (town["plan"].get("yard") or {}).get("slipway")
    slip = np.zeros((H, W), bool)
    if sw_:
        sx0, sz0, sx1, sz1 = sw_["rect"]
        run_ = int(tw.get("slip_basin_blocks", 10))
        for x in range(sx0 - run_, sx1 + 1):
            k_ = sx1 - x
            dneed = min(k_, sx1 - sx0) + 2
            a0, a1 = max(0, sz0 - 2 - box[1]), min(H, sz1 + 3 - box[1])
            b_ = x - box[0]
            if 0 <= b_ < W and a1 > a0:
                need[a0:a1, b_] = np.maximum(need[a0:a1, b_], float(dneed))
                slip[a0:a1, b_] = True
        shal_zone &= ~slip
    town_zone = distance(raft_m | shal_m, None, max_iter=int(tw["grow_blocks"]) + 2) <= float(tw["grow_blocks"])
    rd0, rd1 = tw["raft_depth"]
    sd0, sd1 = tw["shallows_depth"]
    tn = value_noise(xx, zz, 18.0, seed_of("town_bed"))
    Ttown = np.where(shal_zone, sd0 + (sd1 - sd0) * (tn > 0.5), rd0 + (rd1 - rd0) * tn)
    Ttown = np.maximum(Ttown, need)
    wt = 1.0 - smoothstep(distance(town_zone, None, max_iter=int(tw["blend_blocks"]) + 2) / float(tw["blend_blocks"]))
    wt = np.where(town_zone, 1.0, wt)
    T = np.where(I | apron, T + (Ttown - T) * wt, T)
    # the blue hole off Fishers' Row's head
    bh = bk["blue_hole"]
    head = next(w for w in town["plan"]["walks"] if w["id"] == bh["at_walk"])
    hx = head["rect"][0] - float(bh["radius"]) * float(bh.get("offset_of_radius", 0.85))
    hz = (head["rect"][1] + head["rect"][3]) / 2.0
    ang = np.arctan2(zz - hz, xx - hx)
    wob = 1.0 + 0.35 * (value_noise(np.cos(ang) * 2.0 + hx, np.sin(ang) * 2.0 + hz, 1.2, seed_of("blue_hole")) - 0.5) \
        + 0.2 * (value_noise(xx, zz, 9.0, seed_of("blue_hole2")) - 0.5)
    rr = np.hypot(xx - hx, zz - hz) / (float(bh["radius"]) * wob)
    # a sand lip, a steep wall with a ledge part way down, and a bowl floor
    shape = np.where(rr <= 0.45, 1.0, np.where(rr <= 0.7, 0.62 + 0.38 * smoothstep((0.7 - rr) / 0.25),
                                                 0.62 * smoothstep((1.0 - rr) / 0.3)))
    hole = T + (float(bh["depth"]) - T) * shape
    in_hole = rr <= 1.0
    T = np.where(in_hole & (I | apron), np.maximum(T, hole), T)
    T = np.maximum(T, float(bk["never_shallower_than"]))
    want = I | apron | (in_hole & (T > d0))
    new = np.where(want, SEA - np.rint(T), g0).astype(np.int32)
    new = np.minimum(new, SEA - 1)
    mask = want & (new != g0.astype(np.int32))
    k = ctx.feature("bank:jungle_isle", "bank")
    ok = ctx.write(k, box, new.astype(np.int16), mask, over=("seabed",))
    g1 = ctx.G1[sl(box)].astype(np.int32)
    dep = SEA - g1
    town_band = wt > 0.0                                   # the town's zone and the band its bed fades over
    off_town = I & ~town_band & ~in_hole
    ctx.report["bank"] = {
        "island_columns_removed": int(I.sum()), "apron_columns_cut": int((ok & apron).sum()),
        "columns_written": int(ok.sum()), "cut_blocks": int((g0.astype(np.int32) - g1)[ok & (g1 < g0)].sum()),
        "fill_blocks": int((g1 - g0.astype(np.int32))[ok & (g1 > g0)].sum()),
        "held_protected": ctx.features[k]["held_protected"], "held_clash": ctx.features[k]["held_clash"],
        "left_at_or_above_sea": int((I & (g1 >= SEA)).sum()),
        "bank_depth_off_town": {"min": int(dep[off_town].min()), "p10": float(np.percentile(dep[off_town], 10)),
                                "median": float(np.median(dep[off_town])), "p90": float(np.percentile(dep[off_town], 90)),
                                "max": int(dep[off_town].max())},
        "town_zone_depth": {"min": int(dep[town_zone & I].min()), "max": int(dep[town_zone & I].max())},
        "rest_ground_columns": int((I & (dep <= 1)).sum()),
        "rest_ground_outside_town": int((I & (dep <= 1) & ~town_band).sum()),
        "blue_hole": {"centre": [round(hx), round(hz)], "deepest": int(dep[in_hole].max())},
        "town_footprint_depth_under_decks": None}
    ctx.bank_run = {"box": box, "I": I, "town_zone": town_zone, "town_band": town_band, "hole_centre": (hx, hz)}
    ctx.features[k]["columns_written"] = int(ok.sum())


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
    land_full = G0 >= SEA
    if ctx.spec.get("jungle_isle_bank"):
        # the Jungle Isle is removed by the bank pass: it is not land for the sea floor's profile
        bbox, isl = bank_island(ctx)
        land_full[sl(bbox)] &= ~isl
    land_c = land_full[:n * f, :n * f].reshape(n, f, n, f).any(axis=(1, 3))
    del land_full
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
    # the ferry's straits: a soft trough under each gate line instead of an excluded channel (the run kept each strait
    # at its old depth, and on the overview they read as cut channels across the new shelf). The target sinks by up to
    # depth_blocks along a wandering centreline and fades out over sigma_blocks either side; the fill is fill-only and
    # capped at y59, so no column's swim rate changes and every gate stays a gate (P4)
    st_rep = []
    tr = sb.get("strait_trough")
    if tr:
        cz_, cx_ = np.mgrid[0:n, 0:n]
        px_, pz_ = (cx_ + 0.5) * f, (cz_ + 0.5) * f
        sink = np.zeros((n, n))
        for (ax, az), (bx, bz) in gate_lines(ctx, only_gates=True):
            vx, vz = bx - ax, bz - az
            L2 = max(1e-9, vx * vx + vz * vz)
            t_ = np.clip(((px_ - ax) * vx + (pz_ - az) * vz) / L2, 0.0, 1.0)
            ox_, oz_ = ax + vx * t_, az + vz * t_
            L = math.sqrt(L2)
            nxl, nzl = -vz / L, vx / L
            wob = (value_noise(px_, pz_, float(tr["wander_scale_blocks"]), seed_of("strait", ax, az)) - 0.5) * 2.0 * float(tr["wander_blocks"])
            dd = (px_ - ox_) * nxl + (pz_ - oz_) * nzl - wob
            sg_ = float(tr["sigma_blocks"]) * (0.8 + 0.4 * value_noise(px_, pz_, 300.0, seed_of("strait_w", ax, az)))
            # the trough fades out toward each shore (the run cut a notch into the beach at a line's end)
            ends = smoothstep(np.minimum(t_, 1.0 - t_) * L / float(tr.get("end_taper_blocks", 160)))
            sink = np.maximum(sink, float(tr["depth_blocks"]) * np.exp(-(dd / sg_) ** 2) * ends)
            st_rep.append({"line": [[ax, az], [bx, bz]]})
        Pc = np.where(np.isfinite(Pc), Pc - sink, Pc)
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
    # fade out toward the outer edge of the zones too (the full-resolution zone mask below is a hard cut)
    wzone_c = np.clip((wsum - 0.5) * 2.0, 0.0, 1.0)
    wc = np.where(sea_c & np.isfinite(Pc), wex_c * wshore_c * wzone_c, 0.0)
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
        # canyons are measured on the canonical seabed: G1 above this band is already filled, and a blur that read
        # it drew a line along every band boundary (the first run's seabed map was striped every 256 rows)
        g = ctx.G0[a0:a1].astype(np.float64)
        blur = box_mean(g, br)[zb - a0:zb - a0 + (ze - zb)]
        gb = ctx.G1[zb:ze].astype(np.int32)
        inc = np.maximum(0.0, blur - ctx.G0[zb:ze].astype(np.float64))
        inc = box_mean(np.where(inc >= minc, inc, 0.0), 3)
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
                            "excluded_coarse_cells": ex_rep, "strait_troughs": st_rep, "held_protected": ctx.features[k]["held_protected"],
                            "held_clash": ctx.features[k]["held_clash"],
                            "margin": {"status": sb["margin"]["status"], "seamounts": ctx.region("the_outer_deep")["features"]["seamounts"]}}
    ctx.features[k]["columns_written"] = written
    ctx.seabed_coarse = {"sea": sea_c, "dl": dl_c, "P": Pc, "w": wc, "ex": ex_c, "f": f}
    print("  seabed: written %d columns in %.1f s" % (written, time.time() - t0), flush=True)


HEADLAND_SIGMAS = (0.0, 3.0, 6.0, 12.0, 24.0, 40.0, 64.0, 96.0)


def _blur1d(v, sigma):
    """A 1-D Gaussian blur of an edge row, its ends held (numpy only)."""
    if sigma <= 0:
        return v.astype(np.float64).copy()
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    return np.convolve(np.pad(v.astype(np.float64), r, mode="edge"), k / k.sum(), mode="valid")


def _headland_field(prof, s, d, X, Z, hl, side, N):
    """Ground outside one edge of the copy, carried off as headlands instead of combed straight out (the owner's
    close-ups, 2026-09-27: copying each edge column outward left parallel streaks). `prof` is the edge row blurred
    along itself at each of HEADLAND_SIGMAS; `s` the position along the edge and `d` the distance off it. Farther out
    the edge is read more blurred (a narrow ridge tapers to a point, a broad shoulder holds), at a position that
    wanders (the outline is not a ruled line), and each stretch of coast reaches out its own distance before it rounds
    over to the sea (a long headland here, a short one there, bays between). Returns (land ground, the edge read there
    for the sea floor): at d = 1 both are the edge column itself, so the
    margin meets the copy within a block (audit M4)."""
    t = smoothstep(d / float(hl["settle_blocks"]))
    seed = seed_of("headland", side)
    warp = float(hl["warp_blocks"]) * t * (2.0 * value_noise(s, d, float(hl["warp_scale_blocks"]), seed) - 1.0)
    s2 = np.clip(s + warp, 0, N - 1)
    si = np.rint(s2).astype(np.int64)
    raw = prof[0][np.clip(np.rint(s).astype(np.int64), 0, N - 1)]

    def read(rate):
        lev = np.interp(rate * d, HEADLAND_SIGMAS, np.arange(len(HEADLAND_SIGMAS), dtype=np.float64))
        i0 = np.floor(lev).astype(np.int64)
        i1 = np.minimum(i0 + 1, len(HEADLAND_SIGMAS) - 1)
        f = lev - i0
        return raw * (1 - t) + (prof[i0, si] * (1 - f) + prof[i1, si] * f) * t

    e = read(float(hl["blur_per_block"]))
    # the sea floor is read blurred faster than the land: a step in the heightmap's own edge (shelf to deep water) is
    # otherwise carried outward as a hard line
    e_sea = read(float(hl["seabed_blur_per_block"]))
    lo, hi = hl["reach_range"]
    L = lo + (hi - lo) * value_noise(s2, np.zeros_like(s2), float(hl["reach_scale_blocks"]), seed + 1) ** 0.7
    u = d / L
    # land holds its height and rounds over at its own reach to a tip two blocks under the sea (so ground barely above
    # the sea sinks at once instead of spreading a flat skirt), then the bed falls away under water
    tip = SEA - 2.0
    above = np.maximum(e - tip, 0.0)
    y = np.where(u <= 1.0, tip + above * (1.0 - np.clip(u, 0, 1) ** float(hl["tip_power"])),
                 tip - float(hl["underwater_fall"]) * (d - L))
    # blended, not switched, where the edge sits about the tip's height: a switch leaves a seam as long as the reach
    w = np.clip((e - tip) / 4.0, 0.0, 1.0)
    y = w * y + (1.0 - w) * (e - float(hl["underwater_fall"]) * d)
    lift = np.clip((y - SEA) / 12.0, 0.0, 1.0) * t
    y = y + float(hl["relief_blocks"]) * (2.0 * value_noise(X, Z, float(hl["relief_scale_blocks"]), seed + 2) - 1.0) * lift
    return y, e_sea


def margin_relief(ctx):
    """The margin relief image (owner question 1, option A, designed 2026-09-27): a 16-bit image the size of the
    export's canvas (the heightmap plus export_margin_blocks on every side), on the heightmap's own import line, that
    tools/worldpainter/export_world.js imports in place of its blank margin. Zero over the heightmap's square (the
    margin import only raises and only creates missing tiles, so the landmass is untouched); outside it the revised
    copy's edge carried outward (the sea floor fading to the y10 floor over fade_blocks, land at the edge carried off
    as headlands that fall to the sea instead of a cliff: _headland_field), and the five seamounts of the_outer_deep. Returns (raw uint16 image,
    report, preview at 1/16)."""
    mg = ctx.spec["seabed"]["margin"]
    rel = mg["relief"]
    M = int(ctx.world["export"]["export_margin_blocks"])
    N = ctx.N
    side = N + 2 * M
    fade = float(rel["fade_blocks"])
    hl = rel["headlands"]
    G1 = ctx.G1
    profs = {k: np.stack([_blur1d(v, sg) for sg in HEADLAND_SIGMAS])
             for k, v in {"n": G1[0], "s": G1[-1], "w": G1[:, 0], "e": G1[:, -1]}.items()}
    floor_y = float(ctx.world["import"]["low_out"])
    cap = float(rel["sea_cap_y"])
    seam = ctx.region("the_outer_deep")["features"]["seamounts"]
    shape = mg["seamount_shape"]
    rng = rng_for("seamounts")
    mounts = []
    for s_ in seam:
        R = rng.uniform(*shape["radius_blocks"])
        mounts.append((float(s_["x"]), float(s_["z"]), float(s_["summit_y"]), R, float(shape["summit_plateau_radius"])))
    out = np.zeros((side, side), np.uint16)
    prev = np.zeros((-(-side // 16), -(-side // 16)), np.float32)
    ymax_margin = 0.0
    edge_err = 0.0
    for z0 in range(0, side, 512):
        z1 = min(side, z0 + 512)
        wz = np.arange(z0, z1)[:, None] - M
        wx = np.arange(0, side)[None, :] - M
        cz = np.clip(wz, 0, N - 1)
        cx = np.clip(wx, 0, N - 1)
        outside = (wz < 0) | (wz >= N) | (wx < 0) | (wx >= N)
        dx = np.maximum(np.maximum(-wx, wx - (N - 1)), 0)
        dz = np.maximum(np.maximum(-wz, wz - (N - 1)), 0)
        d = np.hypot(dx, dz).astype(np.float64)
        ye = ctx.G1[cz, cx].astype(np.float64)
        X = np.broadcast_to(wx, d.shape).astype(np.float64)
        Z = np.broadcast_to(wz, d.shape).astype(np.float64)
        # each margin column belongs to the edge it is farthest past (a corner to the side it leaves by most)
        ns = dz >= dx
        sides = {"n": ns & (wz < 0), "s": ns & (wz >= N), "w": ~ns & (wx < 0), "e": ~ns & (wx >= N)}
        y_land = np.full(d.shape, floor_y)
        y_edge = ye.copy()
        for k, m in sides.items():
            if not m.any():
                continue
            along = (np.broadcast_to(cx, d.shape) if k in "ns" else np.broadcast_to(cz, d.shape))[m].astype(np.float64)
            yl, ee = _headland_field(profs[k], along, d[m], X[m], Z[m], hl, k, N)
            y_land[m] = yl
            y_edge[m] = ee
        y_sea = floor_y + (np.minimum(y_edge, cap) - floor_y) * (1.0 - smoothstep(d / fade))
        y = np.maximum(y_sea, y_land)
        for mx, mz, top, R, pl in mounts:
            r = np.hypot(X - mx, Z - mz)
            if r.min() > R * 1.3:
                continue
            ang = np.arctan2(Z - mz, X - mx)
            wob = 1.0 + 0.25 * (value_noise(np.cos(ang) * 2.5 + mx, np.sin(ang) * 2.5 + mz, 1.1, seed_of("seamount", mx, mz)) - 0.5)
            t = np.clip((r / wob - pl) / max(1.0, R - pl), 0.0, 1.0)
            ym = top - (top - floor_y) * smoothstep(t) ** 0.7
            y = np.maximum(y, np.where(r <= R * 1.3, ym, floor_y))
        y = np.where(outside, y, floor_y)
        raw = np.where(outside, raw_of_ground(y, ctx.world), 0).astype(np.uint16)
        out[z0:z1] = raw
        if outside.any():
            ymax_margin = max(ymax_margin, float(y[outside & (d > 0)].max()) if (outside & (d > 0)).any() else 0.0)
            # continuity: the first margin column against the copy's edge column
            ring = outside & (d <= 1.0)
            if ring.any():
                edge_err = max(edge_err, float(np.abs(y[ring] - ye[ring]).max()))
        prev[z0 // 16:(z1 + 15) // 16] = y[::16, ::16]
    rep = {"side": side, "margin_blocks": M, "fade_blocks": fade, "headlands": hl,
           "highest_margin_y": round(ymax_margin, 1), "edge_step_max_blocks": round(edge_err, 1),
           "seamounts": [{"at": [int(a), int(b)], "summit_y": t, "radius": round(R, 1)} for a, b, t, R, _pl in mounts],
           "edge_land_columns": {"north": int((ctx.G1[0] >= SEA).sum()), "south": int((ctx.G1[-1] >= SEA).sum()),
                                 "west": int((ctx.G1[:, 0] >= SEA).sum()), "east": int((ctx.G1[:, -1] >= SEA).sum())}}
    return out, rep, prev


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


def with_overlay(ctx, G, box, names):
    """The integer ground over a box with the islet's top (or a town's decks) laid over."""
    g = G[sl(box)].copy()
    for (x, z), y in overlay_ground(ctx, G, names).items():
        if box[0] <= x < box[2] and box[1] <= z < box[3]:
            g[z - box[1], x - box[0]] = y
    return g


def bank_maps(ctx, mdir, legend):
    """The Jungle Isle before and after, with the re-sited town's decks, the blue hole, the new jetty and the ferry
    line drawn; and the town's own close-up."""
    made = []
    import sea_town as ST
    plan = ST.load(resite=True)
    _lv, deck = ST.deck_ground(ctx.world, resite=True)
    for name, box, f in (("jungle_isle_bank", (4000, 6300, 6300, 8191), 2), ("pacifidlog_bank_town", (4880, 7200, 5320, 7720), 1)):
        box = clip_box(*box, ctx.N)
        gb = ctx.G0[sl(box)][::f, ::f]
        ga = ctx.G1[sl(box)][::f, ::f]
        b = render(gb, SEA)
        a = render(ga, SEA)
        d = ImageDraw.Draw(a)
        for x, z in deck:
            if box[0] <= x < box[2] and box[1] <= z < box[3]:
                d.point(((x - box[0]) // f, (z - box[1]) // f), fill=(150, 90, 40))
        for bd in plan["buildings"]:
            x0, z0, x1, z1 = bd["rect"]
            d.rectangle([(x0 - box[0]) // f, (z0 - box[1]) // f, (x1 - box[0]) // f, (z1 - box[1]) // f], fill=(110, 60, 30))
        line = next((v for k, v in ctx.crossing_lines.items() if k == "pacifidlog_ferry_line"), None)
        if line:
            (ax, az), (bx, bz) = line
            d.line([((ax - box[0]) / f, (az - box[1]) / f), ((bx - box[0]) / f, (bz - box[1]) / f)], fill=(220, 40, 40), width=1)
        img = panel([b, a], ["%s before: the Jungle Isle" % name if f == 2 else "%s before" % name,
                             "after: the bank, Pacifidlog's decks (brown), the new jetty, the ferry line (red)"],
                    fit_scale(gb.shape[1] * 2, gb.shape[0], 1800), legend)
        p = mdir / ("%s.png" % name)
        img.save(p)
        made.append(str(p.relative_to(ROOT)))
    # the Long Isle's new split (the owner, 2026-09-27: 'half jungle half desert'): paint, not shape, drawn here with
    # the rest of Part B. The desert sub-regions tinted sand, the jungle green; the old line red, the new one white
    subs = {s["id"]: s for s in load("regions.json")["subregions"]}
    box = clip_box(6700, 4300, 8192, 8100, ctx.N)
    f = 4
    base = render(ctx.G1[sl(box)][::f, ::f], SEA)
    tint = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(tint)
    lines = {}
    for sid, col in (("long_isle_north", (230, 200, 90, 90)), ("long_isle_middle", (230, 200, 90, 90)),
                     ("long_isle_south", (40, 150, 60, 110))):
        for ring in subs[sid]["polygons"]:
            d.polygon([((x - box[0]) / f, (z - box[1]) / f) for x, z in ring], fill=col)
        for b in subs[sid].get("boundaries", []):
            if b.get("line"):
                lines["new"], lines["old"] = b["line"], b.get("previous_line")
    img = Image.alpha_composite(base.convert("RGBA"), tint).convert("RGB")
    d = ImageDraw.Draw(img)
    if lines.get("old"):
        d.line([((x - box[0]) / f, (z - box[1]) / f) for x, z in lines["old"]], fill=(220, 40, 40), width=2)
    if lines.get("new"):
        d.line([((x - box[0]) / f, (z - box[1]) / f) for x, z in lines["new"]], fill=(255, 255, 255), width=2)
    area = {sid: subs[sid]["measured"]["area_km2"] for sid in ("long_isle_north", "long_isle_middle", "long_isle_south")}
    img = panel([img], ["Long Isle: desert (north + middle) %.3f km2, jungle (south) %.3f km2; old line red, new white" % (
        area["long_isle_north"] + area["long_isle_middle"], area["long_isle_south"])], 2.0, None)
    p = mdir / "long_isle_split.png"
    img.save(p)
    made.append(str(p.relative_to(ROOT)))
    return made


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
    for hid, r in (getattr(ctx, "stream_run", None) or {}).items():
        cid = ctx.report["stream"][hid]["course_id"]
        ch = chart([(r["sg"], r["flo"], (140, 140, 140), "ravine floor (lowest within 2)"),
                    (r["sg"], r["level"], (20, 90, 200), "stream surface"),
                    (r["sg"], r["floor"], (160, 100, 40), "stream bed")],
                   [(SEA, (0, 160, 200))], "Viltri Ravine %s half, pass to %s" % (hid, "sea" if hid == "sea" else "Lake Viltri"),
                   "blocks from the pass", "y")
        p = sdir / ("viltri_ravine_%s_long_profile.png" % hid)
        ch.save(p)
        made.append(str(p.relative_to(ROOT)))
        pad = 60
        box = clip_box(r["xn"].min() - pad, r["zn"].min() - pad, r["xn"].max() + pad, r["zn"].max() + pad, ctx.N)
        wb_ = paint_water(ctx.G0, ctx.revised_courses_original[cid], box) if cid in ctx.revised_courses_original else None
        wa_ = paint_water(ctx.G1, ctx.revised_courses[cid], box)
        lvl = float(ctx.lake_bodies["lake_viltri"]["level"])
        lake_or_sea = (ctx.G1[sl(box)] < SEA) | (ctx.lake_mask[sl(box)] & (ctx.G1[sl(box)] < lvl))
        lvmap = np.where(wa_[0], wa_[1], np.where(ctx.lake_mask[sl(box)], lvl, float(SEA)))
        lv0 = np.where(ctx.lake_mask[sl(box)], lvl, float(SEA))
        img = panel([render(ctx.G0[sl(box)], lv0, (ctx.G0[sl(box)] < SEA) | ctx.lake_mask[sl(box)]),
                     render(ctx.G1[sl(box)], lvmap, wa_[0] | lake_or_sea)],
                    ["Viltri Ravine %s half before (dry)" % hid, "after: spring, stream, pools and riffles, cascades"],
                    fit_scale((box[2] - box[0]) * 2, box[3] - box[1], 1800), legend)
        p = mdir / ("viltri_ravine_%s.png" % hid)
        img.save(p)
        made.append(str(p.relative_to(ROOT)))
    coast_boxes = [("southern_coast", (400, 4300, 4300, 6900), 0.25), ("pallet_and_relic", (850, 5150, 1450, 5750), 1.0),
                   ("pallet_flats", (860, 5200, 1760, 5800), 1.0), ("south_strand", (2200, 5800, 4300, 6800), 0.5),
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
        # Relic Island's islet is built over the seabed, not in the heightmap: drawn over both so the map shows what
        # a player sees (the run's maps showed its column of seabed as a dark hole in the reef)
        gb = with_overlay(ctx, ctx.G0, box, ["relic_island"])[::f, ::f]
        ga = with_overlay(ctx, ctx.G1, box, ["relic_island"])[::f, ::f]
        nolake = ~ctx.lake_mask[sl(box)][::f, ::f]          # lakes stand above the sea: not drawn as sea
        img = panel([render(gb, SEA, nolake), render(ga, SEA, nolake)], ["%s before" % name, "after"], fit_scale(gb.shape[1] * 2, gb.shape[0], 1800), legend)
        p = mdir / ("coast_%s.png" % name)
        img.save(p)
        made.append(str(p.relative_to(ROOT)))
    if getattr(ctx, "bank_run", None) is not None:
        made += bank_maps(ctx, mdir, legend)
    if getattr(ctx, "margin", None) is not None:
        prev = ctx.margin[2]
        M = ctx.margin[1]["margin_blocks"]
        img = render(np.rint(prev), SEA)
        d = ImageDraw.Draw(img)
        d.rectangle([M // 16, M // 16, (M + ctx.N) // 16, (M + ctx.N) // 16], outline=(255, 140, 0))
        for sm in ctx.margin[1]["seamounts"]:
            x, z = (sm["at"][0] + M) // 16, (sm["at"][1] + M) // 16
            d.ellipse([x - 3, z - 3, x + 3, z + 3], outline=(220, 40, 40))
        big = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
        ImageDraw.Draw(big).text((6, 6), "margin relief (1 px = 8 blocks): the heightmap square outlined (drawn flat: "
                                          "the image is zero there); seamounts circled", fill=(255, 255, 255))
        p = mdir / "margin_relief.png"
        big.save(p)
        made.append(str(p.relative_to(ROOT)))
    f = 8
    gb = ctx.G0[::f, ::f]
    ga = ctx.G1[::f, ::f]
    nolake = ~ctx.lake_mask[::f, ::f]
    img = panel([render(gb, SEA, nolake), render(ga, SEA, nolake)], ["seabed before (1 px = 8 blocks)", "after"], 1.0,
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
        if "walk" not in after:
            continue
        series = []
        for who, col_b, col_a in (("unaided", (200, 150, 150), (200, 30, 30)), ("trained", (150, 150, 200), (30, 30, 200))):
            if "walk" in before:
                tb = before["walk"][who]["trace"]
                series.append(([t[0] for t in tb], [t[1] for t in tb], col_b, "%s before" % who))
            ta = after["walk"][who]["trace"]
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
                and (a["walk"]["trained"]["resting_on_rest_ground"] == "knocked out" or not req.get("resting_trained_gate", True))
        if req.get("unchanged"):
            ok = ok and a.get("depths") == bef.get(c["id"], {}).get("depths")
        if req.get("rates_unchanged"):
            cls = lambda d: [0 if v <= 1 else (1 if v < S["deep_water_blocks"] else 2) for v in d]  # noqa: E731
            ok = ok and cls(a.get("depths", [])) == cls(bef.get(c["id"], {}).get("depths", []))
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
    if ctx.report.get("bank"):
        bk = ctx.report["bank"]
        out.append(("bank jungle_isle", "left at or above the sea %d; bank depth off the town %s; rest ground outside the town %d" % (
            bk["left_at_or_above_sea"], bk["bank_depth_off_town"], bk["rest_ground_outside_town"]),
            bk["left_at_or_above_sea"] == 0 and bk["bank_depth_off_town"]["min"] >= ctx.spec["jungle_isle_bank"]["depth"]["min_off_town"]))
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


def feature_volumes(ctx):
    """Fill and cut blocks per feature, from the ownership map (every changed column has one owner)."""
    nf = len(ctx.features)
    fill = np.zeros(nf)
    cut = np.zeros(nf)
    cols = np.zeros(nf)
    for z in range(0, ctx.N, 512):
        d = ctx.G1[z:z + 512].astype(np.int32) - ctx.G0[z:z + 512].astype(np.int32)
        o = ctx.owner[z:z + 512].ravel()
        dv = d.ravel()
        fill += np.bincount(o, weights=np.maximum(dv, 0), minlength=nf)[:nf]
        cut += np.bincount(o, weights=np.maximum(-dv, 0), minlength=nf)[:nf]
        cols += np.bincount(o, weights=(dv != 0), minlength=nf)[:nf]
    for k, f in enumerate(ctx.features):
        if k:
            f["columns_changed"], f["fill_blocks"], f["cut_blocks"] = int(cols[k]), int(fill[k]), int(cut[k])


def write_report(ctx, out, made):
    rep = ctx.report
    feature_volumes(ctx)
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
          "| Crossing | Swim before/after | 3+ deep before/after | Longest 3+ deep run after | Unaided before -> after | Trained before -> after | After, resting on rest ground (unaided / trained) | After, Slowness counted (unaided / trained) |",
          "|---|---|---|---|---|---|---|---|"]
    for c in ctx.spec["crossings"]:
        b = rep["crossings"]["before"].get(c["id"], {})
        a = rep["crossings"]["after"].get(c["id"], {})
        if "walk" not in b or "walk" not in a:
            L.append("| %s | no swimming on the line | | | | |" % c["id"])
            continue
        L.append("| %s | %s / %s | %s / %s | %s | %s (%s) -> %s (%s) | %s -> %s | %s / %s | %s / %s |" % (
            c["id"], b["swim"], a["swim"], b["deep"], a["deep"], a["max_deep_run"],
            b["walk"]["unaided"]["outcome"], b["walk"]["unaided"]["peak_word"],
            a["walk"]["unaided"]["outcome"], a["walk"]["unaided"]["peak_word"],
            b["walk"]["trained"]["outcome"], a["walk"]["trained"]["outcome"],
            a["walk"]["unaided"]["resting_on_rest_ground"], a["walk"]["trained"]["resting_on_rest_ground"],
            a["walk"]["unaided"]["with_slowness"], a["walk"]["trained"]["with_slowness"]))
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
        L += ["", "## The Viltri Ravine's two streams", ""]
        for hid, st_ in rep["stream"].items():
            L.append("- **%s half** (`%s`): %s blocks from the spring (level y%s) to y%s; width %s; %s steps, falls %s; "
                     "pools %s; lip cut at most %s blocks; %s blocks of extension beyond the axis; held off by protected ground %s." % (
                         hid, st_["course_id"], st_["length"], st_["from_level"], st_["to_level"], st_["width"], st_["steps"],
                         st_["falls"], st_["pools"], st_["lip_cut_max_blocks"], st_["extension_to_sea_blocks"], st_["held_protected"]))
    if rep.get("bank"):
        L += ["", "## The Jungle Isle's bank and Pacifidlog's site", "", "```", json.dumps(rep["bank"], indent=1, default=str), "```"]
    L += ["", "## Coasts", ""]
    for cid, r in rep["coasts"].items():
        L.append("- **%s**: %s" % (cid, json.dumps({k: v for k, v in r.items() if k not in ("bars", "placed", "knolls")}, default=str)))
    if rep.get("seabed"):
        s = rep["seabed"]
        L += ["", "## Seabed", "", "%d columns filled, %d blocks. Per zone (coarse, excluded water left out):" % (s["columns_written"], s["fill_blocks"])]
        for z, v in s["zones"].items():
            if "cells" in v:
                L.append("- %s: seabed y p10/median/p90 before %s, after %s" % (z, v["before_p10_median_p90"], v["after_p10_median_p90"]))
    L += ["", "## Cut and fill by feature", "", "| Feature | Family | Columns changed | Fill blocks | Cut blocks | Held off (protected) | Held off (another feature) |", "|---|---|---|---|---|---|---|"]
    for f in ctx.features[1:]:
        L.append("| %s | %s | %s | %s | %s | %s | %s |" % (f["id"], f["family"], f.get("columns_changed", ""), f.get("fill_blocks", ""),
                                                   f.get("cut_blocks", ""), f["held_protected"], f["held_clash"]))
    L.append("| **total** | | %d | %d | %d | | |" % (sum(f.get("columns_changed", 0) for f in ctx.features[1:]),
                                                     sum(f.get("fill_blocks", 0) for f in ctx.features[1:]),
                                                     sum(f.get("cut_blocks", 0) for f in ctx.features[1:])))
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
    # the sea floor first, then the bank (its edge runs down to the filled floor), then the coast features, which
    # build on the filled floor (the run filled round them afterwards and had to keep boxes of old deep water about
    # them: the Southern home waters' rectangle)
    if "seabed" in fams:
        seabed_pass(ctx)
        print("seabed done (%.1f s)" % (time.time() - t0), flush=True)
    if "bank" in fams:
        bank_pass(ctx)
        print("bank done (%.1f s)" % (time.time() - t0), flush=True)
    if "coasts" in fams:
        coasts_pass(ctx)
        print("coasts done (%.1f s)" % (time.time() - t0), flush=True)
    ctx.report["crossings"]["after"] = crossings_pass(ctx, "after", ctx.G1)
    ctx.families = fams
    if (spec["seabed"].get("margin") or {}).get("relief") and "seabed" in fams:
        ctx.margin = margin_relief(ctx)
        ctx.report["margin_relief"] = ctx.margin[1]
        print("margin relief done (%.1f s)" % (time.time() - t0), flush=True)
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
    margin_man = None
    if getattr(ctx, "margin", None) is not None:
        mimg, mrep, _prev = ctx.margin
        mdest = out / spec["seabed"]["margin"]["relief"]["image_name"]
        Image.fromarray(mimg, mode="I;16").save(mdest)
        margin_man = {"path": mdest.name, "sha256": sha256_file(mdest), "side": int(mimg.shape[0]),
                      "margin_blocks": mrep["margin_blocks"], "zero_inside_heightmap": True}
        ctx.report["margin_relief"]["image"] = margin_man
    made = maps_pass(ctx, out) if maps else []
    write_report(ctx, out, made)
    manifest = {
        "generator": "tools/water_shape.py", "spec": "data/water_shape.json", "spec_sha256": sha256_file(SPEC),
        "input": {"path": ctx.hm_path.name, "sha256": ctx.world["heightmap"]["sha256"]},
        "output": {"path": dest.name, "sha256": sha}, "families": list(ctx.families),
        "complete": tuple(ctx.families) == FAMILIES, "columns_changed": int(changed.sum()),
        "features": [{"index": i, "id": f["id"], "family": f["family"]} for i, f in enumerate(ctx.features) if i],
        "zones": zman, "maps": made, "margin_relief": margin_man,
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
    text = text[:brace] + json.dumps(hm, indent=2) + text[i + 1:]
    mr = man.get("margin_relief")
    if mr:
        # the margin relief goes beside the heightmap and is pinned where tools/reexport.py reads it
        msrc = out / mr["path"]
        if sha256_file(msrc) != mr["sha256"]:
            raise ShapeError("the margin relief changed since it was audited")
        mdest = current.parent / mr["path"]
        if mdest.exists():
            raise ShapeError("%s exists; refusing to overwrite a source file" % mdest)
        mdest.write_bytes(msrc.read_bytes())
        start = text.index('"export"')
        brace = text.index("{", start)
        text = text[:brace + 1] + '\n  "margin_relief": %s,' % json.dumps(
            {"path": mr["path"], "sha256": mr["sha256"], "side": mr["side"], "generator": "python tools/water_shape.py --apply",
             "note": "owner question 1, option A: read by tools/worldpainter/export_world.js in place of the blank margin"}) + text[brace + 1:]
    world_path.write_text(text, encoding="utf-8")
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
