#!/usr/bin/env python
"""Audit the water-shape copy offline, failing closed.

The implementer's audit for data/water_shape.json and tools/water_shape.py (independent tests are a test author's,
later: .claude/rules/testing.md). It compares the copy derived/water_shape/<name>.png with the canonical heightmap
data/world.json pins, column by column, against footprints and expectations it derives itself from the design and
the committed data, never from the generator's plan or report:

  A  inputs      the canonical file hashes to data/world.json; the copy hashes to its manifest; the manifest is complete
  B  footprint   every changed column lies inside a declared feature's footprint; everything else is bit-identical
  C  protected   no changed column in a town footprint, on a road, in the Rift (its region grown 24 and every column
                 the Rift sculpt changed), under Victory Road, under a bridge, the islet, the sea town, or a built water
                 event site
  D  swim rates  a sea column 3 or more deep before is under 3 after only inside a coast feature that declares rest
                 ground (principle P4), so no ferry line gains rest ground by accident
  E  lakes       wet area at the level unchanged; no column at or above level - 1 changed and none raised to the level;
                 wadeable share, distance to rest and deep area against the design's targets; keep zones untouched
  F  rivers      every course in data/rivers.json is in the revised courses; painted as tools/paint_maps.py paints,
                 surfaces never rise, steps over a block only at declared falls, every station is wet, each course ends
                 where it should, no new leak; each meander window's sinuosity inside its target, measured on the result
  G  the stream  starts at the pass, reaches the sea, drains; the ravine's lake half untouched
  H  seabed      fill only, never above y59, never a column shallower than 4 before; the windward deep band keeps its
                 deep-spawn water (y36 or below wherever it was)
  I  crossings   the fatigue walk (data/blackout.json's constants) calibrated on the canonical heightmap against
                 WATER_BUILD_PLAN 11.1 (hard for contract C3's lines); then every requirement after
  J  nonempty    each declared feature changed something; nothing changed at all is a failure

    python tools/water_shape_audit.py --source-root <root>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import terrain as T  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
ROOT = T.ROOT
SEA = 62
WORLD_READS = ()          # heightmap and data only; never a world


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Audit:
    def __init__(self):
        self.results = []

    def check(self, code, name, ok, detail=""):
        self.results.append({"code": code, "check": name, "ok": bool(ok), "detail": detail})
        print("  %s %-4s %s%s" % ("ok  " if ok else "FAIL", code, name, (": " + str(detail)) if detail else ""), flush=True)
        return ok

    @property
    def clean(self):
        return bool(self.results) and all(r["ok"] for r in self.results)


# ---------------------------------------------------------------------------------------------------- geometry


def ground(raw, world):
    out = np.empty(raw.shape, np.int16)
    for z in range(0, raw.shape[0], 512):
        out[z:z + 512] = np.round(T.sample_to_height(raw[z:z + 512], world).astype(np.float32)).astype(np.int16)
    return out


def cbox(x0, z0, x1, z1, n):
    return max(0, int(x0)), max(0, int(z0)), min(n, int(x1)), min(n, int(z1))


def S_(b):
    return slice(b[1], b[3]), slice(b[0], b[2])


def poly_mask(rings, b):
    img = Image.new("L", (max(1, b[2] - b[0]), max(1, b[3] - b[1])), 0)
    d = ImageDraw.Draw(img)
    for ring in rings:
        if len(ring) >= 3:
            d.polygon([(p[0] - b[0], p[1] - b[1]) for p in ring], fill=1)
    return np.array(img).astype(bool)


def line_mask(lines, b, width):
    img = Image.new("L", (max(1, b[2] - b[0]), max(1, b[3] - b[1])), 0)
    d = ImageDraw.Draw(img)
    r = width / 2.0
    for line in lines:
        pts = [(p[0] - b[0], p[1] - b[1]) for p in line]
        if len(pts) >= 2:
            d.line(pts, fill=1, width=max(1, int(round(width))))
        for x, z in pts:
            d.ellipse([x - r, z - r, x + r, z + r], fill=1)
    return np.array(img).astype(bool)


def chamfer(src, through=None, max_iter=100000):
    offs = [(0, 1, 1.0), (1, 0, 1.0), (0, -1, 1.0), (-1, 0, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142),
            (-1, -1, 1.4142), (1, 2, 2.2361), (2, 1, 2.2361), (-1, 2, 2.2361), (-2, 1, 2.2361), (1, -2, 2.2361),
            (2, -1, 2.2361), (-1, -2, 2.2361), (-2, -1, 2.2361)]
    d = np.where(src, 0.0, np.inf).astype(np.float32)
    thr = np.ones(src.shape, bool) if through is None else (through | src)
    H, W = d.shape
    for _ in range(max_iter):
        ch = False
        for dz, dx, w in offs:
            a0, a1, b0, b1 = max(0, dz), H + min(0, dz), max(0, dx), W + min(0, dx)
            if a1 <= a0 or b1 <= b0:
                continue
            t = d[a0:a1, b0:b1]
            c = d[a0 - dz:a1 - dz, b0 - dx:b1 - dx] + np.float32(w)
            m = (c < t) & thr[a0:a1, b0:b1]
            if m.any():
                np.copyto(t, c, where=m)
                ch = True
        if not ch:
            break
    return d


def grown(mask, r):
    return chamfer(mask, None, int(r) + 2) <= r


def coarse_distance(src, through, f):
    H, W = src.shape
    h, w = -(-H // f), -(-W // f)
    sp = np.zeros((h * f, w * f), bool)
    tp = np.zeros((h * f, w * f), bool)
    sp[:H, :W] = src
    tp[:H, :W] = through
    d = chamfer(sp.reshape(h, f, w, f).any(axis=(1, 3)), tp.reshape(h, f, w, f).any(axis=(1, 3))) * f
    return np.repeat(np.repeat(d, f, 0), f, 1)[:H, :W]


def dil4(m):
    o = m.copy()
    o[1:] |= m[:-1]
    o[:-1] |= m[1:]
    o[:, 1:] |= m[:, :-1]
    o[:, :-1] |= m[:, 1:]
    return o


def regions():
    doc = load("regions.json")
    out = {r["id"]: r for r in doc["regions"]}
    for r in doc.get("marine_regions", []):
        out[r["id"]] = r
    return out


def region_grown(reg, rid, grow_by, n):
    rings = reg[rid]["polygons"]
    xs = [p[0] for r in rings for p in r]
    zs = [p[1] for r in rings for p in r]
    b = cbox(min(xs) - grow_by - 4, min(zs) - grow_by - 4, max(xs) + grow_by + 5, max(zs) + grow_by + 5, n)
    m = poly_mask(rings, b)
    return b, (grown(m, grow_by) if grow_by else m)


# ---------------------------------------------------------------------------------------------------- the walk


def cells_of(a, b):
    (x0, z0), (x1, z1) = a, b
    n = int(max(abs(x1 - x0), abs(z1 - z0)))
    out = []
    for i in range(n + 1):
        c = (int(round(x0 + (x1 - x0) * i / max(1, n))), int(round(z0 + (z1 - z0) * i / max(1, n))))
        if not out or out[-1] != c:
            out.append(c)
    return out, math.dist(a, b) / max(1, len(out) - 1)


def swim(depths, step, trained, K, resting=False):
    """Hits along the line at 5 blocks per second with the pack's constants: a sample every sample_ticks; deep water
    (deep_water_blocks or more) gains gain_deep, 2 deep gains gain_shallow, halved when trained; land or 1 deep
    recovers; the first hit at collapse, then one every pulse_ticks. `resting` waits on every rest stretch of 6+."""
    per = K["sample_ticks"]
    f, pos, t, nxt = 0.0, 0.0, 0, None
    hits, peak = [], 0.0
    total = len(depths) * step
    run, rr = 0, [0] * len(depths)
    for i in range(len(depths) - 1, -1, -1):
        run = run + 1 if depths[i] <= 1 else 0
        rr[i] = run
    while pos < total:
        pos += 5.0 * per / 20.0
        t += per
        i = min(len(depths) - 1, int(pos / step))
        d = depths[i]
        if d <= 1:
            f = 0.0 if (resting and rr[i] * step >= 6) else max(0.0, f - K["recover_per_tick"] * per)
            continue
        g = K["gain_deep_per_tick"] if d >= K["deep_water_blocks"] else K["gain_shallow_per_tick"]
        f = min(float(K["cap_ticks"]), f + g * per * (0.5 if trained else 1.0))
        peak = max(peak, f)
        if f >= K["collapse_ticks"] and (nxt is None or t >= nxt):
            hits.append(pos)
            nxt = t + K["pulse_ticks"]
    return hits, peak


def verdict(hits):
    return "no hit" if not hits else ("hit" if len(hits) == 1 else "knocked out")


def profile(G, over, a, b):
    cells, step = cells_of(a, b)
    depth = [SEA - over.get((x, z), int(G[z, x])) for x, z in cells]
    wet = [i for i, d in enumerate(depth) if d > 1]
    if not wet:
        return None
    d = depth[wet[0]:wet[-1] + 1]
    runs, cur, deep, curd = 0, 0, 0, 0
    for v in d:
        cur = 0 if v <= 1 else cur + 1
        runs = max(runs, cur)
        curd = curd + 1 if v >= 3 else 0
        deep = max(deep, curd)
    return {"depths": d, "step": step, "swim": runs * step, "deep": sum(1 for v in d if v >= 3) * step,
            "deepest": max(d), "max_deep_run": deep * step}


def overlays(world, G, names):
    out = {}
    if "relic_island" in names:
        import islet as I
        cx, cz = I.CENTRE
        r = I.RADIUS
        top, _ = I.island_top(G[cz - r:cz + r + 1, cx - r:cx + r + 1].astype(float), SEA)
        top = np.asarray(top, float)
        for z, x in zip(*np.nonzero(~np.isnan(top))):
            out[(cx - r + int(x), cz - r + int(z))] = int(np.round(top[z, x]))
    if "sea_town" in names:
        import sea_town
        level, deck = sea_town.deck_ground(world)
        for x, z in deck:
            out[(int(x), int(z))] = int(level)
    return out


def endpoints(c, G, reg, n):
    if c["kind"] == "points":
        return tuple(c["from"]), tuple(c["to"])
    if c["kind"] == "to_region":
        b, m = region_grown(reg, c["to_region"], 24, n)
        zs, xs = np.nonzero(m & (G[S_(b)] >= SEA))
        fx, fz = c["from"]
        i = int(np.argmin((xs + b[0] - fx) ** 2 + (zs + b[1] - fz) ** 2))
        return (fx, fz), (int(xs[i]) + b[0], int(zs[i]) + b[1])
    if c["kind"] == "row":
        z = int(c["z"])
        ba, ma = region_grown(reg, c["from_region"], 24, n)
        bb, mb = region_grown(reg, c["to_region"], 24, n)
        la = [ba[0] + int(x) for x in np.nonzero(ma[z - ba[1]] & (G[z, ba[0]:ba[2]] >= SEA))[0]]
        lb = [bb[0] + int(x) for x in np.nonzero(mb[z - bb[1]] & (G[z, bb[0]:bb[2]] >= SEA))[0]]
        x1 = min(x for x in lb if x > min(la)) if any(x > min(la) for x in lb) else min(lb)
        x0 = max((x for x in la if x < x1), default=min(la))
        return (x0, z), (x1, z)
    if c["kind"] == "shortest":
        ba, ma = region_grown(reg, c["from_region"], 24, n)
        bb, mb = region_grown(reg, c["to_region"], 24, n)
        sa = ma & (G[S_(ba)] >= SEA) & dil4(G[S_(ba)] < SEA)
        sb = mb & (G[S_(bb)] >= SEA) & dil4(G[S_(bb)] < SEA)
        za, xa = np.nonzero(sa)
        zb, xb = np.nonzero(sb)
        xa, za, xb, zb = xa + ba[0], za + ba[1], xb + bb[0], zb + bb[1]
        best = (float("inf"), None)
        for s in range(0, len(xa), 1500):
            d2 = (xa[s:s + 1500, None] - xb[None, :]) ** 2 + (za[s:s + 1500, None] - zb[None, :]) ** 2
            i = int(np.argmin(d2))
            if d2.flat[i] < best[0]:
                ia, ib = divmod(i, len(xb))
                best = (float(d2.flat[i]), ((int(xa[s + ia]), int(za[s + ia])), (int(xb[ib]), int(zb[ib]))))
        return best[1]
    raise ValueError(c["kind"])


# ---------------------------------------------------------------------------------------------------- rivers


def densify(poly):
    out = []
    for (x0, z0, s0, f0), (x1, z1, s1, f1) in zip(poly, poly[1:]):
        k = max(1, int(math.ceil(math.hypot(x1 - x0, z1 - z0))))
        for i in range(k):
            t = i / k
            out.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, s0 + (s1 - s0) * t))
    out.append(tuple(poly[-1][:3]))
    ch = [0.0]
    for a, b in zip(out, out[1:]):
        ch.append(ch[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return out, ch


def reach_at(reaches, c):
    for r in reaches:
        if c <= r["to_m"]:
            return r
    return reaches[-1]


def painted(G, course, n):
    """(box, wet, level) of a course painted as tools/paint_maps.py paint_rivers paints it."""
    pts, ch = densify(course["graded_polyline"])
    pad = max(r["width"] for r in course["reaches"]) // 2 + 4
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    b = cbox(min(xs) - pad, min(zs) - pad, max(xs) + pad + 1, max(zs) + pad + 1, n)
    H, W = b[3] - b[1], b[2] - b[0]
    best = np.full((H, W), np.inf, np.float32)
    lv = np.zeros((H, W), np.int32)
    for (x, z, s), c in zip(pts, ch):
        r = reach_at(course["reaches"], c)
        if r["water_body"]:
            continue
        hw = r["width"] / 2.0
        rr = int(math.ceil(hw)) + 1
        a0, a1 = max(b[1], int(z) - rr), min(b[3], int(z) + rr + 2)
        b0, b1 = max(b[0], int(x) - rr), min(b[2], int(x) + rr + 2)
        if a1 <= a0 or b1 <= b0:
            continue
        zz, xx = np.mgrid[a0:a1, b0:b1]
        d = np.hypot(xx - x, zz - z).astype(np.float32)
        sl = (slice(a0 - b[1], a1 - b[1]), slice(b0 - b[0], b1 - b[0]))
        m = (d <= hw) & (d < best[sl])
        best[sl] = np.where(m, d, best[sl])
        lv[sl] = np.where(m, int(math.floor(s + 0.01)), lv[sl])
    g = G[S_(b)]
    wet = (lv > 0) & (g < lv)
    return b, wet, lv, pts, ch


def leaks(g, wet, lv):
    n = 0
    for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        a = (slice(max(0, dz), g.shape[0] + min(0, dz)), slice(max(0, dx), g.shape[1] + min(0, dx)))
        b = (slice(max(0, -dz), g.shape[0] + min(0, -dz)), slice(max(0, -dx), g.shape[1] + min(0, -dx)))
        nw = np.zeros_like(wet)
        nl = np.zeros_like(lv)
        nw[a] = wet[b]
        nl[a] = lv[b]
        n += int((nw & ~wet & (g < nl)).sum())
    return n


# ---------------------------------------------------------------------------------------------------- the audit


def run(source_root, world_path=None):
    A = Audit()
    spec = load("water_shape.json")
    world_path = Path(world_path or (ROOT / "data" / "world.json"))
    world = T.load_world(world_path)
    out = ROOT / spec["output"]["dir"]
    man_p = out / "manifest.json"
    print("A inputs")
    if not A.check("A1", "manifest present", man_p.is_file(), str(man_p)):
        return A, None
    man = json.loads(man_p.read_text(encoding="utf-8"))
    A.check("A2", "the design applies to the pinned heightmap",
            spec["applies_to"]["heightmap_sha256"] == world["heightmap"]["sha256"] == man["input"]["sha256"])
    hm = T.resolve_heightmap(world, world_path, source_root)
    copy_p = out / man["output"]["path"]
    copy_sha = sha(copy_p) if copy_p.is_file() else None
    A.check("A3", "the copy hashes to its manifest", copy_sha == man["output"]["sha256"], (copy_sha or "missing")[:12])
    A.check("A4", "the copy is complete (every family ran)", man.get("complete") is True, man.get("families"))
    A.check("A5", "the design file is the one the copy was made from", sha(ROOT / "data" / "water_shape.json") == man["spec_sha256"])
    if copy_sha is None:
        return A, None
    raw0 = np.array(Image.open(hm))
    raw1 = np.array(Image.open(copy_p))
    if not A.check("A6", "same size and depth", raw0.shape == raw1.shape and raw1.dtype == np.uint16):
        return A, copy_sha
    n = raw0.shape[0]
    G0, G1 = ground(raw0, world), ground(raw1, world)
    diff = raw0 != raw1
    moved = G0 != G1
    A.check("J0", "something changed", diff.any(), int(diff.sum()))
    A.check("A7", "every rewritten sample changed its ground (no silent re-quantising)", not (diff & ~moved).any(),
            int((diff & ~moved).sum()))
    reg = regions()
    lms = {l["id"]: l for l in load("landmarks.json")["landmarks"]}
    rivers = load("rivers.json")
    courses = {c["id"]: c for c in rivers["courses"]}

    # ------------------------------------------------------------------ footprints (from the design and data only)
    full = (0, 0, n, n)
    fp = {}
    rv = spec["rivers"]
    ch_half = int(rv["defaults"]["corridor_half_width_blocks"])
    m = np.zeros((n, n), bool)
    for e in rv["meanders"] + rv["cascades"]:
        pts, ch = densify(courses[e["course"]]["graded_polyline"])
        sel = [(p[0], p[1]) for p, c in zip(pts, ch) if e["from_m"] - 8 <= c <= e["to_m"] + 8]
        if len(sel) >= 2:
            m |= line_mask([sel], full, 2 * ch_half + 1)
    fp["rivers"] = m
    st = spec["viltri_ravine_stream"]
    axis = next(a for a in lms["viltri_ravine"]["axes"] if a["id"] == "channel")["polyline"]
    px, pz = st["pass"]
    k = int(np.argmin([math.hypot(p[0] - px, p[1] - pz) for p in axis]))
    sea_half = [(px, pz)] + [tuple(p) for p in axis[k + 1:]]
    lake_half = [tuple(p) for p in axis[:max(1, k - 1)]]
    m = line_mask([sea_half], full, 2 * st["corridor_half_width_blocks"] + 1)
    ex = st["to_sea"]["max_extension_blocks"] + st["corridor_half_width_blocks"]
    lx, lz = sea_half[-1]
    m |= line_mask([[(lx, lz), (lx, lz)]], full, 2 * ex + 1)
    fp["stream"] = m
    lake_masks = {}
    m = np.zeros((n, n), bool)
    for lm in lms.values():
        wb = lm.get("water_body")
        if not wb:
            continue
        rings = wb["basin_polygons"]
        xs = [p[0] for r in rings for p in r]
        zs = [p[1] for r in rings for p in r]
        b = cbox(min(xs) - 4, min(zs) - 4, max(xs) + 5, max(zs) + 5, n)
        pm = poly_mask(rings, b)
        lake_masks[lm["id"]] = (b, pm, int(wb["level_y"]))
        m[S_(b)] |= pm
    fp["lakes"] = m
    lake_all = m
    co = spec["coasts"]
    m = np.zeros((n, n), bool)
    rest_ok = np.zeros((n, n), bool)
    for f in co["flats"]:
        x0, z0, x1, z1 = f["box"]
        m[z0:z1 + 1, x0:x1 + 1] = True
        rest_ok[z0:z1 + 1, x0:x1 + 1] = True
    for s in co["skerries"]:
        x0, z0, x1, z1 = s["box"]
        m[max(0, z0):z1 + 1, max(0, x0):x1 + 1] = True
        rest_ok[max(0, z0):z1 + 1, max(0, x0):x1 + 1] = True
    fb = co["fungal_bar_chain"]
    fungal_c = next(c for c in spec["crossings"] if c["id"] == "fungal_from_the_pallet_coast")
    fa, fbp = endpoints(fungal_c, G0, reg, n)
    # 4 blocks wider than the generator's corridor: the endpoint is recomputed here and may differ by a column
    fm = line_mask([[fa, fbp]], full, 2 * (fb["corridor_half_width_blocks"] + 4) + 1)
    m |= fm
    rest_ok |= fm
    rf = co["relic_reef"]
    R = rf["outer_radius"][1] + rf["drop_width_blocks"] + 8
    cx, cz = rf["centre"]
    reef_box = cbox(cx - R, cz - R, cx + R + 1, cz + R + 1, n)
    m[S_(reef_box)] = True
    h = co["first_cast_hole"]
    hb = cbox(h["centre"][0] - h["radius"] - 2, h["centre"][1] - h["radius"] - 2, h["centre"][0] + h["radius"] + 3,
              h["centre"][1] + h["radius"] + 3, n)
    m[S_(hb)] = True
    fp["coasts"] = m
    sb = spec["seabed"]
    zm = np.zeros((n, n), bool)
    for z in sb["zones"]:
        zm |= poly_mask(reg[z["region"]]["polygons"], full)
    for e in sb["exclude"]:
        if "box" in e:
            x0, z0, x1, z1 = e["box"]
            zm[max(0, z0):z1 + 1, max(0, x0):x1 + 1] = False
    zm &= ~lake_all & (G0 < SEA)
    fp["seabed"] = zm
    union = np.zeros((n, n), bool)
    for v in fp.values():
        union |= v
    print("B footprint")
    stray = diff & ~union
    A.check("B1", "every changed column is inside a declared footprint", not stray.any(),
            "%d stray columns%s" % (stray.sum(), (" e.g. at %s" % str(tuple(np.argwhere(stray)[0][::-1]))) if stray.any() else ""))

    # ------------------------------------------------------------------ protected
    print("C protected")
    towns = load("towns.json")["towns"]
    pm = np.zeros((n, n), bool)
    for t in towns:
        f = t.get("footprint") or {}
        if f.get("min_x") is not None:
            pm[max(0, f["min_z"]):f["max_z"] + 1, max(0, f["min_x"]):f["max_x"] + 1] = True
    A.check("C1", "no town footprint changed", not (diff & pm).any(), int((diff & pm).sum()))
    lines = []
    for r in load("routes.json")["routes"]:
        pts = [(q["x"], q["z"]) for q in (r.get("corridor") or {}).get("polyline") or [] if isinstance(q, dict)]
        if len(pts) >= 2:
            lines.append(pts)
    road = line_mask(lines, full, 9)
    A.check("C2", "no road (4 blocks either side of every route line) changed", not (diff & road).any(), int((diff & road).sum()))
    del road
    bm = np.zeros((n, n), bool)
    for b in load("bridges.json")["bridges"]:
        w = int(b.get("walkway_half_width", 2)) + 2
        if b["axis"] == "z":
            bm[b["along_from"]:b["along_to"] + 1, b["centre"] - w:b["centre"] + w + 1] = True
        else:
            bm[b["centre"] - w:b["centre"] + w + 1, b["along_from"]:b["along_to"] + 1] = True
    A.check("C3", "no bridge span changed", not (diff & bm).any(), int((diff & bm).sum()))
    rb, rm = region_grown(reg, "the_rift", 24, n)
    A.check("C4", "nothing in the Rift region grown 24", not (diff[S_(rb)] & rm).any(), int((diff[S_(rb)] & rm).sum()))
    base = world["heightmap"].get("rift_sculpted_from") or {}
    pre = hm.parent / base.get("path", "")
    if A.check("C5a", "the pre-Rift heightmap is present and pinned", pre.is_file() and sha(pre) == base.get("sha256")):
        rp = np.array(Image.open(pre))
        rift_cols = rp != raw0
        del rp
        A.check("C5", "no column the Rift sculpt changed", not (diff & rift_cols).any(), int((diff & rift_cols).sum()))
    vr = load("vr_caves.json")["guide"]
    vrm = line_mask([vr["points"]], full, 2 * vr["band"] + 1)
    A.check("C6", "nothing over Victory Road's band", not (diff & vrm).any(), int((diff & vrm).sum()))
    import islet as I
    icx, icz = I.CENTRE
    A.check("C7", "nothing under the islet", not diff[icz - I.RADIUS:icz + I.RADIUS + 1, icx - I.RADIUS:icx + I.RADIUS + 1].any())
    ev = np.zeros((n, n), bool)
    for s in spec["protect"]["event_sites"]:
        x0, z0, x1, z1 = s["box"]
        ev[z0:z1 + 1, x0:x1 + 1] = True
    A.check("C8", "nothing under a built water event site", not (diff & ev).any(), int((diff & ev).sum()))

    # ------------------------------------------------------------------ swim-rate invariance
    print("D swim rates")
    sea0 = (G0 < SEA) & ~lake_all
    became_shallow = sea0 & (G0 <= SEA - 3) & (G1 > SEA - 3)
    bad = became_shallow & ~rest_ok
    A.check("D1", "a sea column 3+ deep became shallower than 3 only inside a rest-ground coast feature", not bad.any(),
            "%d columns%s" % (bad.sum(), (" e.g. at %s" % str(tuple(np.argwhere(bad)[0][::-1]))) if bad.any() else ""))
    reef_sel = diff[S_(reef_box)] & sea0[S_(reef_box)]
    A.check("D2", "the reef is never shallower than %d where it changed" % rf["min_depth"],
            not (reef_sel & ((SEA - G1[S_(reef_box)]) < rf["min_depth"]) & ~rest_ok[S_(reef_box)]).any())

    # ------------------------------------------------------------------ lakes
    print("E lakes")
    rungs = spec["lakes"]["rungs"]
    for body in spec["lakes"]["bodies"]:
        b, pm_, L = lake_masks[body["id"]]
        g0, g1, d_ = G0[S_(b)].astype(int), G1[S_(b)].astype(int), diff[S_(b)] & pm_
        w0, w1 = pm_ & (g0 < L), pm_ & (g1 < L)
        A.check("E1", "%s: wet area at level %d unchanged" % (body["id"], L), np.array_equal(w0, w1), int((w0 ^ w1).sum()))
        A.check("E2", "%s: nothing at or above level - 1 changed, nothing raised to the level" % body["id"],
                not (d_ & ((g0 >= L - 1) | (g1 >= L))).any())
        A.check("E3", "%s: the lake changed" % body["id"], d_.any(), int(d_.sum()))
        dep1 = np.where(w1, L - g1, 0)
        dep0 = np.where(w0, L - g0, 0)
        wshare = float((dep1[w1] <= 1).mean()) if w1.any() else 0.0
        lo, hi = body["wadeable_target"]
        A.check("E4", "%s: wadeable share %.3f in %s" % (body["id"], wshare, body["wadeable_target"]), lo <= wshare <= hi)
        anc = lms[body["id"]]["anchor"]
        az, ax = int(anc["z"]) - b[1], int(anc["x"]) - b[0]
        excl = np.zeros(w1.shape, bool)
        keeps = {}
        for kz in body.get("keep", []):
            if "core_depth" in kz:
                core = w0 & (dep0 >= kz["core_depth"])
                if core.any():
                    if not core[az, ax]:
                        zs, xs = np.nonzero(core)
                        i = int(np.argmin((zs - az) ** 2 + (xs - ax) ** 2))
                        az2, ax2 = zs[i], xs[i]
                    else:
                        az2, ax2 = az, ax
                    comp = np.zeros_like(core)
                    comp[az2, ax2] = True
                    while True:
                        nx_ = dil4(comp) & core
                        if nx_.sum() == comp.sum():
                            break
                        comp = nx_
                    keeps[kz["id"]] = comp
            else:
                zz, xx = np.mgrid[0:w1.shape[0], 0:w1.shape[1]]
                keeps[kz["id"]] = np.hypot(zz - az, xx - ax) <= kz["radius"]
        for kid, km in keeps.items():
            A.check("E5", "%s: keep zone %s untouched" % (body["id"], kid), not (d_ & km).any(), int((d_ & km).sum()))
        for kid in body.get("max_to_rest_excludes", []):
            excl |= keeps.get(kid, np.zeros_like(excl))
        f = 1 if w1.size <= 400000 else (2 if w1.size <= 2500000 else 4)
        dist = coarse_distance(~w1 | (dep1 <= 1), w1, max(1, f))
        obj = w1 & ~excl
        mx = float(dist[obj].max()) if obj.any() else 0.0
        tgt = rungs[body["rung"]]["max_to_rest_blocks"]
        A.check("E6", "%s: farthest water from rest %.0f <= %s (%s rung)" % (body["id"], mx, tgt, body["rung"]), mx <= tgt + f)
        deep0, deep1 = int((dep0 >= 9).sum()), int((dep1 >= 9).sum())
        share = spec["lakes"]["defaults"]["deep_area_min_share"]
        A.check("E7", "%s: deep water (9+) %d of %d kept (at least %.0f%%)" % (body["id"], deep1, deep0, share * 100),
                deep1 >= share * deep0)

    # ------------------------------------------------------------------ rivers
    print("F rivers")
    rp_ = out / "rivers_revised.json"
    if not A.check("F0", "revised courses present", rp_.is_file()):
        return A, copy_sha
    rev = {c["id"]: c for c in json.loads(rp_.read_text(encoding="utf-8"))["courses"]}
    missing = [c for c in courses if c not in rev]
    A.check("F1", "every course in data/rivers.json is in the revised courses", not missing, missing)
    cut = set((rivers.get("cut") or {}).get("courses_cut", []))
    windows = {}
    for e in rv["meanders"] + rv["cascades"]:
        windows.setdefault(e["course"], []).append(e)
    for cid, c in courses.items():
        if cid not in rev or cid not in cut:
            continue
        r = rev[cid]
        if "water_shape" not in r:
            b0_, w0_, l0_, _, _ = painted(G0, c, n)
            b1_, w1_, l1_, _, _ = painted(G1, r, n)
            A.check("F2", "%s (unchanged course): painted water unchanged" % cid, np.array_equal(w0_, w1_) and np.array_equal(l0_, l1_),
                    int((w0_ ^ w1_).sum()))
            continue
        b, wet, lv, pts, ch = painted(G1, r, n)
        levels = [math.floor(p[2] + 0.01) for p in pts]
        rises = sum(1 for a_, b_ in zip(levels, levels[1:]) if b_ > a_)
        A.check("F3", "%s: the surface never rises downstream" % cid, rises == 0, rises)
        falls_decl = sum(len(e.get("falls", [])) for e in windows.get(cid, []))
        big = [(i, levels[i - 1] - levels[i]) for i in range(1, len(levels)) if levels[i - 1] - levels[i] > 1]
        maxfall = max([f["drop"] for e in windows.get(cid, []) for f in e.get("falls", [])] or [1])
        A.check("F4", "%s: steps over a block only at declared falls (%d found, %d declared, largest %s)" % (
            cid, len(big), falls_decl, max([d for _, d in big] or [0])), len(big) <= falls_decl and all(d <= maxfall for _, d in big))
        dry = 0
        for (x, z, s), c_ in zip(pts, ch):
            if reach_at(r["reaches"], c_)["water_body"]:
                continue
            if G1[int(round(z)), int(round(x))] >= math.floor(s + 0.01):
                dry += 1
        A.check("F5", "%s: every station's centre column holds water" % cid, dry == 0, dry)
        end = c.get("ends_in")
        if end == "open_sea":
            A.check("F6", "%s: ends at the sea" % cid, levels[-1] == SEA, levels[-1])
        elif end in lake_masks:
            A.check("F6", "%s: ends at or above %s's level" % (cid, end), levels[-1] >= lake_masks[end][2], levels[-1])
        b0_, w0_, l0_, _, _ = painted(G0, c, n)
        lk0 = leaks(G0[S_(b0_)].astype(int), w0_, l0_)
        lk1 = leaks(G1[S_(b)].astype(int), wet, lv)
        A.check("F7", "%s: no new leak (dry columns below the water beside it: %d before, %d after)" % (cid, lk0, lk1), lk1 <= lk0)
        opts, och = densify(c["graded_polyline"])
        rx = np.array([p[0] for p in pts])
        rz = np.array([p[1] for p in pts])
        rch = np.array(ch)
        for e in windows.get(cid, []):
            if e not in rv["meanders"]:
                continue
            ia = int(np.argmin(np.abs(np.array(och) - e["from_m"])))
            ib = int(np.argmin(np.abs(np.array(och) - e["to_m"])))
            ja = int(np.argmin((rx - opts[ia][0]) ** 2 + (rz - opts[ia][1]) ** 2))
            jb = int(np.argmin((rx - opts[ib][0]) ** 2 + (rz - opts[ib][1]) ** 2))
            chord = math.hypot(opts[ib][0] - opts[ia][0], opts[ib][1] - opts[ia][1])
            sn = (rch[jb] - rch[ja]) / max(1.0, chord)
            s0 = (och[ib] - och[ia]) / max(1.0, chord)
            lo, hi = e["sinuosity_target"]
            A.check("F8", "%s: sinuosity %.2f (before %.2f) in %s" % (e["id"], sn, s0, e["sinuosity_target"]), lo <= sn <= hi)

    # ------------------------------------------------------------------ the stream
    print("G stream")
    s = rev.get(st["course_id"])
    if A.check("G1", "the Viltri Ravine stream is a revised course", s is not None):
        b, wet, lv, pts, ch = painted(G1, s, n)
        levels = [math.floor(p[2] + 0.01) for p in pts]
        A.check("G2", "it starts within 40 blocks of the pass", math.hypot(pts[0][0] - px, pts[0][1] - pz) <= 40)
        A.check("G3", "it ends at the sea", levels[-1] == SEA and G1[int(round(pts[-1][1])), int(round(pts[-1][0]))] < SEA)
        A.check("G4", "its surface never rises", all(b_ <= a_ for a_, b_ in zip(levels, levels[1:])))
        big = [levels[i - 1] - levels[i] for i in range(1, len(levels)) if levels[i - 1] - levels[i] > 1]
        A.check("G5", "steps over a block only at its declared falls", len(big) <= len(st.get("falls", [])) and
                all(d <= max(f["drop"] for f in st["falls"]) for d in big), big)
        dry = sum(1 for (x, z, sv) in pts if G1[int(round(z)), int(round(x))] >= math.floor(sv + 0.01))
        A.check("G6", "every station holds water", dry == 0, dry)
        lk = line_mask([lake_half], full, 81) if len(lake_half) >= 2 else np.zeros((n, n), bool)
        A.check("G7", "the ravine's lake half is untouched (dry by design)", not (diff & lk).any(), int((diff & lk).sum()))

    # ------------------------------------------------------------------ seabed
    print("H seabed")
    only_seabed = diff & fp["seabed"] & ~(fp["rivers"] | fp["stream"] | fp["lakes"] | fp["coasts"])
    A.check("H1", "seabed changes fill only", not (only_seabed & (G1 < G0)).any(), int((only_seabed & (G1 < G0)).sum()))
    A.check("H2", "seabed never above y%d" % sb["cap_y"], not (only_seabed & (G1 > sb["cap_y"])).any())
    A.check("H3", "seabed never touches a column shallower than %d" % sb["min_depth_to_edit"],
            not (only_seabed & (G0 > SEA - sb["min_depth_to_edit"])).any())
    A.check("H4", "the seabed changed", only_seabed.any(), int(only_seabed.sum()))
    f16 = 16
    k16 = n // f16
    land16 = (G0[:k16 * f16, :k16 * f16] >= SEA).reshape(k16, f16, k16, f16).any(axis=(1, 3))
    far = ~grown(land16, 256 // f16)
    far_full = np.repeat(np.repeat(far, f16, 0), f16, 1)
    ww = np.zeros((n, n), bool)
    ww[2592:5216, 0:992] = True
    deep_keep = ww & far_full & (G0 <= 36)
    A.check("H5", "the windward deep band keeps its deep-spawn water (y36 or below where it was)",
            not (deep_keep & (G1 > 36)).any(), int((deep_keep & (G1 > 36)).sum()))

    # ------------------------------------------------------------------ crossings
    print("I crossings")
    K = load("blackout.json")["surface"]
    for c in spec["crossings"]:
        a, b = endpoints(c, G0, reg, n)
        ov0 = overlays(world, G0, c.get("overlays", []))
        ov1 = overlays(world, G1, c.get("overlays", []))
        p0, p1 = profile(G0, ov0, a, b), profile(G1, ov1, a, b)
        if p0 is None or p1 is None:
            A.check("I0", "%s: there is water on the line" % c["id"], False, (a, b))
            continue
        pb = c["plan_before"]
        u0 = verdict(swim(p0["depths"], p0["step"], False, K)[0])
        t0 = verdict(swim(p0["depths"], p0["step"], True, K)[0])
        calib = abs(p0["swim"] - pb["swim"]) <= 0.1 * pb["swim"] + 2 and u0 == pb["unaided"] and t0 == pb["trained"]
        detail = "swim %.0f (plan %s), unaided %s (plan %s), trained %s (plan %s)" % (
            p0["swim"], pb["swim"], u0, pb["unaided"], t0, pb["trained"])
        if c.get("contract"):
            A.check("I1", "%s: the walk reproduces the plan on the canonical heightmap (contract %s)" % (c["id"], c["contract"]),
                    calib, detail)
        elif not calib:
            print("        note %s: the walk differs from the plan's measurement: %s" % (c["id"], detail))
        req = c.get("require_after") or {}
        hu, pu = swim(p1["depths"], p1["step"], False, K)
        ht, _ = swim(p1["depths"], p1["step"], True, K)
        hur, _ = swim(p1["depths"], p1["step"], False, K, resting=True)
        htr, _ = swim(p1["depths"], p1["step"], True, K, resting=True)
        u1, t1 = verdict(hu), verdict(ht)
        d = "after: unaided %s (peak %.0f), trained %s, resting %s/%s, swim %.0f, longest 3+ run %.0f" % (
            u1, pu, t1, verdict(hur), verdict(htr), p1["swim"], p1["max_deep_run"])
        if req.get("gate"):
            A.check("I2", "%s stays a gate" % c["id"], u1 == t1 == verdict(hur) == verdict(htr) == "knocked out", d)
        if req.get("unchanged"):
            A.check("I3", "%s unchanged" % c["id"], p0["depths"] == p1["depths"], d)
        if req.get("unaided") == "no hit":
            A.check("I4", "%s: unaided, no hit" % c["id"], u1 == "no hit", d)
        if req.get("unaided") == "hit or worse":
            A.check("I5", "%s: still a row for the unaided" % c["id"], u1 != "no hit", d)
        if req.get("trained") == "no hit":
            A.check("I6", "%s: trained, no hit" % c["id"], t1 == "no hit", d)
        if "max_deep_run" in req:
            A.check("I7", "%s: no 3-deep run over %s blocks" % (c["id"], req["max_deep_run"]), p1["max_deep_run"] <= req["max_deep_run"], d)
        if req.get("report_only"):
            print("        report %s: %s" % (c["id"], d))
    if c := next((c for c in spec["crossings"] if c["id"] == "fungal_from_the_pallet_coast"), None):
        p1 = profile(G1, {}, fa, fbp)
        if p1:
            _, peak = swim(p1["depths"], p1["step"], False, K)
            A.check("I8", "Fungal Isle is crossed with warnings (peak fatigue %.0f >= warn %s)" % (peak, K["warn_ticks"]),
                    peak >= K["warn_ticks"])

    # ------------------------------------------------------------------ nonempty
    print("J nonempty")
    for fam in ("rivers", "stream", "lakes", "coasts", "seabed"):
        A.check("J1", "%s changed something" % fam, (diff & fp[fam]).any(), int((diff & fp[fam]).sum()))
    for f in co["flats"]:
        x0, z0, x1, z1 = f["box"]
        A.check("J2", "%s changed something" % f["id"], diff[z0:z1 + 1, x0:x1 + 1].any())
    for s_ in co["skerries"]:
        x0, z0, x1, z1 = s_["box"]
        A.check("J3", "%s raised something above the sea" % s_["id"],
                ((G1 >= SEA) & (G0 < SEA))[max(0, z0):z1 + 1, max(0, x0):x1 + 1].any())
    A.check("J4", "the reef changed", diff[S_(reef_box)].any())
    A.check("J5", "the Fungal chain changed", (diff & fm).any())
    return A, copy_sha


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root")
    ap.add_argument("--world", default=str(ROOT / "data" / "world.json"))
    a = ap.parse_args(argv)
    try:
        A, copy_sha = run(a.source_root, a.world)
    except (T.TerrainUnavailable, FileNotFoundError, KeyError, ValueError) as e:
        print("water_shape_audit: cannot audit: %s" % e, file=sys.stderr)
        return 2
    spec = load("water_shape.json")
    out = ROOT / spec["output"]["dir"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps({"clean": A.clean, "copy_sha256": copy_sha, "checks": A.results},
                                               indent=1, default=str), encoding="utf-8")
    bad = [r for r in A.results if not r["ok"]]
    print("%d checks, %d failed: %s" % (len(A.results), len(bad), "CLEAN" if A.clean else "NOT CLEAN"))
    return 0 if A.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
