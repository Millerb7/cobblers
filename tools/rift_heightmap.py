#!/usr/bin/env python
"""Sculpt the whole Rift into the canonical heightmap, so it lands in the live world's next export.

The prototype built one stretch as a block pass. That cannot reach the live world without being re-applied after
every export, and it cannot be what `tools/ground.py` calls ground. This tool puts the *shape* where shape belongs:

  - the lip is the boundary of the low-ground basin inside the_rift (data/rift_sculpt.json basin), not the region
    polygon, which is not the rim: 57% of its stations sit under 20 blocks above the floor
  - a band just inside the lip drops to the local floor, so the lip is a sheer riser
  - outside it the rim is shoved up: a continuous parapet everywhere, with crags, broken plates and sheer stretches
    by character, and high peaks where the Rift should look forbidding
  - the named entrances stay open, and their ramps are cut in

Everything that cannot be a height stays a block pass (tools/rift_skin.py): materials, veins, the sky tear, the
portal sheets, the biome. Nothing here passes the y310 ceiling, so nothing needs re-applying after an export.

Like tools/press_pads.py, it always starts from the un-sculpted heightmap recorded in data/world.json, so running
it twice never sculpts a sculpt.

    python tools/rift_heightmap.py --source-root <root>            # measure and report, write nothing
    python tools/rift_heightmap.py --source-root <root> --apply    # write the heightmap and data/world.json
    python tools/rift_heightmap.py --source-root <root> --plan     # write only derived/rift_sculpt/

--plan rebuilds the plan and masks the block passes read (rift_skin, gulch_mine, the audits) in a checkout that has
the heightmap but not derived/, such as a fresh clone or an agent's worktree. It never writes the heightmap or
data/world.json.

--plan MEASURES the applied sculpt rather than recomputing it from today's data. The plan's ring, normals and masks
are what the block passes BUILD AGAINST, so they have to describe the lip the heightmap really has: recomputed from
data that has moved since the sculpt was applied they would seat skin, mines and audits against a lip that is not
there. So the entrances -- the one part of the sculpt that follows data outside data/rift_sculpt.json, because they
snap to a route -- are read off the applied rim: outside the lip the sculpt only ever RAISES, and it skips an
entrance's 2*gap+1 stations, so an applied entrance is exactly a window of that width in which nothing outside the
basin was raised (measured_entrances). Victory Road was re-routed after the sculpt (35f2a56) and its gap had moved
47 stations; with the gap measured instead of re-snapped, the sculpt reproduces the applied heightmap pixel for
pixel again, so the proof that the plan describes a real file is kept rather than traded away.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import zlib
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

import terrain as T
import rescale as RS

ROOT = T.ROOT
SPEC = ROOT / "data" / "rift_sculpt.json"
OUT_NAME = "land_8k_16_rescaled_b145_pads_rift.png"
PLAN = ROOT / "derived" / "rift_sculpt" / "plan.json"
MASK = ROOT / "derived" / "rift_sculpt"

WORLD_READS = ()          # heightmap and data only; never a world


class SculptError(Exception):
    pass


def rng_for(seed, *k):
    """A random stream fixed by the seed and the key. crc32, not hash(): Python randomises string hashes per
    process, so a rebuild would otherwise lay a different Rift."""
    import random
    return random.Random(zlib.crc32(repr((seed,) + k).encode()) & 0xFFFFFFFF)


# ---------------------------------------------------------------- the basin and its lip


def region_polygon(region_id):
    doc = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    regions = doc["regions"] if isinstance(doc, dict) and "regions" in doc else doc
    if isinstance(regions, dict):
        regions = list(regions.values())
    r = next(x for x in regions if x["id"] == region_id)
    if len(r["polygons"]) != 1:
        raise SculptError("%s is drawn as %d polygons; the rim walk assumes one" % (region_id, len(r["polygons"])))
    return [(float(x), float(z)) for x, z in r["polygons"][0]]


def rasterise(poly, X0, Z0, shape):
    zz, xx = np.mgrid[Z0:Z0 + shape[0], X0:X0 + shape[1]]
    inside = np.zeros(shape, bool)
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]
        bx, bz = poly[(i + 1) % n]
        cond = (az > zz) != (bz > zz)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (bx - ax) * (zz - az) / (bz - az + 1e-12) + ax
        inside ^= cond & (xx < xint)
    return inside


def largest_piece(mask):
    lab = np.zeros(mask.shape, np.int32)
    cur, best, best_n = 0, 0, 0
    for sz in range(mask.shape[0]):
        row = mask[sz]
        for sx in np.nonzero(row)[0]:
            if lab[sz, sx]:
                continue
            cur += 1
            q = deque([(sz, sx)])
            lab[sz, sx] = cur
            n = 0
            while q:
                z, x = q.popleft()
                n += 1
                for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nz, nx = z + dz, x + dx
                    if 0 <= nz < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[nz, nx] and not lab[nz, nx]:
                        lab[nz, nx] = cur
                        q.append((nz, nx))
            if n > best_n:
                best, best_n = cur, n
    return lab == best, best_n


MOORE = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))


def trace_outline(mask):
    """The mask's outer boundary as one ordered ring of (z, x), by Moore-neighbour tracing."""
    start = None
    for z in range(mask.shape[0]):
        xs = np.nonzero(mask[z])[0]
        if len(xs):
            start = (z, int(xs[0]))
            break
    if start is None:
        raise SculptError("the basin is empty")
    ring = [start]
    cur, back = start, 6                       # came from the west
    for _ in range(8 * mask.size):
        found = False
        for k in range(8):
            d = (back + 1 + k) % 8
            nz, nx = cur[0] + MOORE[d][0], cur[1] + MOORE[d][1]
            if 0 <= nz < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[nz, nx]:
                back = (d + 5) % 8             # the direction we came from, at the new cell
                cur = (nz, nx)
                found = True
                break
        if not found:
            break
        if cur == start and len(ring) > 2:
            break
        ring.append(cur)
    if len(ring) < 64:
        raise SculptError("the traced lip is only %d columns: tracing failed" % len(ring))
    return ring


def smooth_normals(ring, mask, span=26):
    """The inward unit normal at each ring point, from a tangent averaged over `span` points either way.

    Which way is "in" is decided by the mask, not by the centroid. The Rift is a long branching shape, and on an
    arm's far side the centroid lies across the gap: orienting by it pointed 39% of the ring outwards, so the
    sculpt sampled its floor on the plateau and its plateau on the floor (found 2026-09-22).
    """
    n = len(ring)
    cz = sum(p[0] for p in ring) / n
    cx = sum(p[1] for p in ring) / n
    H, W = mask.shape
    out = []
    for i in range(n):
        az, ax = ring[(i - span) % n]
        bz, bx = ring[(i + span) % n]
        tz, tx = bz - az, bx - ax
        L = math.hypot(tz, tx) or 1.0
        nz, nx = -tx / L, tz / L
        pz, px = ring[i]

        def hits(sz, sx):
            k = 0
            for d in (3, 6, 10, 15):
                z2, x2 = int(round(pz + sz * d)), int(round(px + sx * d))
                if 0 <= z2 < H and 0 <= x2 < W and mask[z2, x2]:
                    k += 1
            return k

        fwd, back = hits(nz, nx), hits(-nz, -nx)
        if back > fwd:
            nz, nx = -nz, -nx
        elif back == fwd and (cz - pz) * nz + (cx - px) * nx < 0:
            nz, nx = -nz, -nx           # a tie (a neck, or a corner): fall back to the centroid
        out.append((nz, nx))
    return out


def nearest_station(shape, ring, reach):
    """For every column within `reach` of the lip: the index of the nearest ring point, and the true distance.

    A breadth-first sweep carries the index outward; the distance is then computed from that point's coordinates,
    so it is Euclidean rather than the sweep's own metric.
    """
    idx = np.full(shape, -1, np.int32)
    q = deque()
    for i, (z, x) in enumerate(ring):
        if idx[z, x] < 0:
            idx[z, x] = i
            q.append((z, x, 0))
    while q:
        z, x, d = q.popleft()
        if d >= reach:
            continue
        src = idx[z, x]
        for dz, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nz, nx = z + dz, x + dx
            if 0 <= nz < shape[0] and 0 <= nx < shape[1] and idx[nz, nx] < 0:
                idx[nz, nx] = src
                q.append((nz, nx, d + 1))
    return idx


# ---------------------------------------------------------------- the rim's character


def segments(spec, total, seed):
    """Stretches of character along the lip: crags, sheer, broken plates, in irregular runs."""
    rim = spec["rim"]
    kinds = list(rim["mix"])
    wts = [rim["mix"][k] for k in kinds]
    r = rng_for(seed, "segments")
    out, s, prev = [], 0.0, None
    while s < total:
        ln = r.uniform(*rim["segment_length"])
        k = r.choices(kinds, wts)[0]
        if k == prev:
            k = r.choices(kinds, wts)[0]
        out.append((s, min(total, s + ln), k))
        prev, s = k, s + ln
    return out


def kind_at(segs, i, total):
    for a, b, k in segs:
        if a <= i < b:
            return k
    return "sheer"


def route_points(route_id):
    doc = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))
    rt = next(r for r in doc["routes"] if r["id"] == route_id)
    pts = (rt.get("corridor") or {}).get("polyline") or []
    out = []
    for q in pts:
        if isinstance(q, dict) and "x" in q:
            out.append((float(q["x"]), float(q["z"])))
        elif isinstance(q, (list, tuple)) and len(q) >= 2:
            out.append((float(q[0]), float(q[1])))
    if not out:
        raise SculptError("route %s has no corridor polyline to snap an entrance to" % route_id)
    return out


def entrance_targets(e):
    """The world points an entrance snaps to: its route's whole corridor, or its one named point."""
    if e.get("snap_route"):
        return route_points(e["snap_route"])
    ex, ez = e["near"]
    return [(float(ex), float(ez))]


def entrance_indices(spec, ring, X0, Z0, at=None):
    """Each named entrance's ring index, and how far that station is from the point it snaps to.

    An entrance that names a route snaps to where that route actually meets the lip, not to a hand-picked point:
    a gap 152 blocks off Victory Road's crossing would leave the route facing the lethal lip it is meant to pass.

    `at` is {entrance id: ring index}: the gap the heightmap ACTUALLY holds, as measured_entrances() read it off
    the applied rim. --plan passes it, so the plan describes the sculpt that was applied rather than the one
    today's routes would ask for; --apply passes nothing and snaps to the data as it stands. The distance is
    computed for whichever station is used, so the report still says how far the gap is from the route.
    """
    out = []
    for e in spec["entrances"]:
        pts = entrance_targets(e)

        def d2(i, pts=pts):
            z, x = ring[i]
            wx, wz = x + X0, z + Z0
            return min((wx - px) ** 2 + (wz - pz) ** 2 for px, pz in pts)

        if at is not None and e["id"] in at:
            bi = int(at[e["id"]]) % len(ring)
            out.append((bi, e, math.sqrt(d2(bi))))
            continue
        best, bi = None, 0
        for i in range(len(ring)):
            d = d2(i)
            if best is None or d < best:
                best, bi = d, i
        out.append((bi, e, math.sqrt(best)))
    return out


def peak_indices(spec, ring, segs, total, seed, ent):
    """Where the high peaks stand: on crag stretches, spread out, and away from an entrance."""
    pk = spec["peaks"]
    r = rng_for(seed, "peaks")
    crag = [i for i in range(total) if kind_at(segs, i, total) == "crags"]
    if not crag:
        raise SculptError("no crag stretch: the peaks would have nowhere to stand")
    placed = []
    for _ in range(pk["count"] * 60):
        if len(placed) >= pk["count"]:
            break
        i = crag[r.randrange(len(crag))]
        if any(min(abs(i - j), total - abs(i - j)) < pk["apart"] for j in placed):
            continue
        if any(min(abs(i - b), total - abs(i - b)) < e["gap"] + 60 for b, e, _ in ent):
            continue
        placed.append(i)
    return sorted(placed)


# ---------------------------------------------------------------- the sculpt


def town_footprints():
    """[id, min_x, max_x, min_z, max_z] of every town in data/towns.json with a footprint: what --apply protects."""
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    return [[t["id"], *(int(t["footprint"][k]) for k in ("min_x", "max_x", "min_z", "max_z"))]
            for t in towns if (t.get("footprint") or {}).get("min_x") is not None]


def build(source_root, world_path=None, footprints=None, ent_at=None):
    """The sculpt. `footprints` are the town footprints it leaves untouched: data/towns.json's today when None (what
    --apply would write now), or the list the last --apply recorded (what the heightmap holds; --plan).

    `ent_at` is {entrance id: ring index} measured off the applied rim; see entrance_indices(). --apply passes
    neither and so always computes the sculpt today's data asks for."""
    world = T.load_world(world_path or str(ROOT / "data" / "world.json"))
    current = T.resolve_heightmap(world, Path(world_path or str(ROOT / "data" / "world.json")), source_root)
    base = world["heightmap"].get("rift_sculpted_from")
    if base:
        src = current.parent / base["path"]
        if hashlib.sha256(src.read_bytes()).hexdigest() != base["sha256"]:
            raise SculptError("rift_sculpted_from %s does not hash to %s" % (src, base["sha256"][:8]))
        base_ref = {"path": base["path"], "sha256": base["sha256"]}
    else:
        src = current
        base_ref = {"path": world["heightmap"]["path"], "sha256": world["heightmap"]["sha256"]}

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    seed = spec["seed"]
    imp = world["import"]
    hi_out = imp["high_out"]
    raw = np.array(Image.open(src)).astype(np.uint16)
    ox, oz = world["grid"]["origin_x"], world["grid"]["origin_z"]

    poly = region_polygon(spec["basin"]["region"])
    xs = [p[0] for p in poly]
    zs = [p[1] for p in poly]
    X0, X1 = int(min(xs)), int(max(xs))
    Z0, Z1 = int(min(zs)), int(max(zs))
    pad = spec["rim"]["reach"] + 60
    X0, X1, Z0, Z1 = X0 - pad, X1 + pad, Z0 - pad, Z1 + pad
    shape = (Z1 - Z0 + 1, X1 - X0 + 1)

    sub = raw[Z0 - oz:Z1 - oz + 1, X0 - ox:X1 - ox + 1]
    if sub.shape != shape:
        raise SculptError("the Rift's box runs off the heightmap: %s vs %s" % (sub.shape, shape))
    Y = RS.y_of_h(sub.astype(np.float64), imp, hi_out)

    inside = rasterise(poly, X0, Z0, shape)
    candidate = inside & (Y <= spec["basin"]["ground_at_or_below"])
    print("  region %d columns, low ground %d, candidate basin %d" % (
        inside.sum(), (Y <= spec["basin"]["ground_at_or_below"]).sum(), candidate.sum()), flush=True)
    if not candidate.any():
        raise SculptError("no column is inside the region and under the basin height: nothing to sculpt")
    basin, n_basin = largest_piece(candidate)
    if n_basin < 0.5 * candidate.sum():
        raise SculptError("the basin's largest piece is only %d of %d columns: it is not one basin" % (
            n_basin, candidate.sum()))
    ring = trace_outline(basin)
    total = len(ring)
    nrm = smooth_normals(ring, basin)
    segs = segments(spec, total, seed)
    ent = entrance_indices(spec, ring, X0, Z0, at=ent_at)
    peaks = peak_indices(spec, ring, segs, total, seed, ent)

    # the floor each station's cut drops to
    fp, reach = spec["cut"]["floor_percentile"], spec["cut"]["floor_reach"]
    floor = np.zeros(total)
    for i, (z, x) in enumerate(ring):
        nz, nx = nrm[i]
        vals = []
        for d in range(6, reach, 6):
            zz, xx = int(round(z + nz * d)), int(round(x + nx * d))
            if 0 <= zz < shape[0] and 0 <= xx < shape[1] and basin[zz, xx]:
                vals.append(Y[zz, xx])
        floor[i] = np.percentile(vals, fp * 100) if vals else Y[z, x]

    reach_out = spec["rim"]["reach"]
    cut_w = spec["cut"]["width"]
    idx = nearest_station(shape, ring, max(reach_out, cut_w[1]) + 4)

    # per-station rim profile
    rim = spec["rim"]
    par, cr, pl = rim["parapet"], rim["crags"], rim["plates"]
    ph = rng_for(seed, "parapet").uniform(0, 6.283)
    ph2 = rng_for(seed, "parapet2").uniform(0, 6.283)
    pkspec = spec["peaks"]
    ceil_y = spec["ceiling"]["peak_max_y"]

    top = np.zeros(total)            # how high the rim stands over the lip's own ground at each station
    width = np.zeros(total)
    plateau = np.zeros(total)
    for i, (z, x) in enumerate(ring):
        nz, nx = nrm[i]
        outs = []
        for d in range(4, 60, 4):
            zz, xx = int(round(z - nz * d)), int(round(x - nx * d))
            if 0 <= zz < shape[0] and 0 <= xx < shape[1]:
                outs.append(Y[zz, xx])
        plateau[i] = float(np.median(outs)) if outs else Y[z, x]
        k = kind_at(segs, i, total)
        f = 0.5 + 0.5 * math.sin(ph + i / par["wave"])
        h = par["height"][0] + (par["height"][1] - par["height"][0]) * f
        w = par["width"][0] + (par["width"][1] - par["width"][0]) * (0.5 + 0.5 * math.sin(ph2 + i / (par["wave"] * 0.7)))
        if k in ("crags", "plates"):
            p = cr if k == "crags" else pl
            r = rng_for(seed, "slab", k, i // int((p["every"][0] + p["every"][1]) / 2))
            lobe = 0.5 + 0.5 * math.sin(i / max(1.0, r.uniform(*p["length"]) / 3.14))
            h = max(h, r.randint(*p["height"]) * (0.35 + 0.65 * lobe))
            w = max(w, r.randint(*p["width"]))
        top[i] = h
        width[i] = w
    for i in peaks:
        rad = rng_for(seed, "peak", i).randint(*pkspec["radius"])
        span = rad * 6
        hi = rng_for(seed, "peakh", i).randint(*pkspec["height_over_plateau"])
        for j in range(-span, span + 1):
            k = (i + j) % total
            rr = abs(j) / span
            top[k] = max(top[k], hi * (1 - rr ** 1.7))
            width[k] = max(width[k], rad * (1 - rr ** 2) + 6)

    # gaps at the entrances
    open_at = np.zeros(total, bool)
    for bi, e, _ in ent:
        for j in range(-e["gap"], e["gap"] + 1):
            open_at[(bi + j) % total] = True

    # apply
    newY = Y.copy()
    zz, xx = np.nonzero(idx >= 0)
    ii = idx[zz, xx]
    rz = np.array([ring[k][0] for k in ii], np.float64)
    rx = np.array([ring[k][1] for k in ii], np.float64)
    dist = np.hypot(zz - rz, xx - rx)
    in_basin = basin[zz, xx]

    lip_y = np.array([Y[ring[k][0], ring[k][1]] for k in ii])
    # outside the lip: raise
    w_i = width[ii]
    t_i = top[ii]
    open_i = open_at[ii]
    out_m = (~in_basin) & (dist <= np.maximum(w_i, 1)) & (~open_i)
    taper = np.clip(1 - (dist / np.maximum(w_i, 1)), 0, 1)
    jag = np.array([rng_for(seed, "jag", int(a), int(b)).uniform(-2.5, 2.5) for a, b in zip(xx[out_m], zz[out_m])])
    rise = lip_y[out_m] + t_i[out_m] * (0.45 + 0.55 * taper[out_m]) + jag
    rise = np.minimum(rise, ceil_y)
    newY[zz[out_m], xx[out_m]] = np.maximum(newY[zz[out_m], xx[out_m]], rise)

    # inside the lip: drop to the local floor, so the lip is a riser
    cw = cut_w[0] + (cut_w[1] - cut_w[0]) * (0.5 + 0.5 * np.sin(ii / spec["cut"]["wave"]))
    cut_m = in_basin & (dist <= cw) & (~open_i)
    newY[zz[cut_m], xx[cut_m]] = np.minimum(newY[zz[cut_m], xx[cut_m]], floor[ii[cut_m]])

    # the entrance ramps: a clean descent from the plateau to the floor through the gap
    ramps = 0
    for bi, e, _ in ent:
        for j in range(-e["gap"], e["gap"] + 1):
            k = (bi + j) % total
            z, x = ring[k]
            nz, nx = nrm[k]
            f = 1 - abs(j) / (e["gap"] + 1)                    # deepest at the middle of the gap
            for d in range(-int(width[k]) - 6, int(cw.max()) + 8):
                zz2, xx2 = int(round(z + nz * d)), int(round(x + nx * d))
                if not (0 <= zz2 < shape[0] and 0 <= xx2 < shape[1]):
                    continue
                span = float(width[k]) + cw.max() + 14
                g = (d + float(width[k]) + 6) / span            # 0 outside, 1 inside
                want = plateau[k] * (1 - g) + floor[k] * g
                newY[zz2, xx2] = newY[zz2, xx2] * (1 - f) + min(newY[zz2, xx2], want) * f
                ramps += 1

    newY = np.clip(newY, imp.get("world_low", 10), spec["ceiling"]["world_max_y"])

    # nothing already placed moves. A town was sited on ground that existed; if the sculpt lifted or dropped its
    # footprint its buildings would hang or bury. rift_dig_camp sits right on the western lip and was moved 3.9
    # blocks before this guard existed.
    protect = np.zeros(shape, bool)
    margin = spec.get("protect_margin", 8)
    kept, footprints_used = [], []
    for tid, fx0, fx1, fz0, fz1 in (town_footprints() if footprints is None else footprints):
        a = max(0, fz0 - margin - Z0)
        b = min(shape[0], fz1 + margin + 1 - Z0)
        c = max(0, fx0 - margin - X0)
        d = min(shape[1], fx1 + margin + 1 - X0)
        if a < b and c < d:
            n = int((newY[a:b, c:d] != Y[a:b, c:d]).sum())
            if n:
                kept.append((tid, n))
            protect[a:b, c:d] = True
            footprints_used.append([tid, fx0, fx1, fz0, fz1])
    newY = np.where(protect, Y, newY)
    changed = newY != Y
    return {"world": world, "src": src, "current": current, "base_ref": base_ref, "raw": raw, "Y": Y, "newY": newY,
            "changed": changed, "box": (X0, X1, Z0, Z1), "shape": shape, "basin": basin, "ring": ring,
            "segs": segs, "ent": ent, "peaks": peaks, "spec": spec, "imp": imp, "hi_out": hi_out,
            "ox": ox, "oz": oz, "n_basin": n_basin, "top": top, "width": width, "plateau": plateau,
            "floor": floor, "nrm": nrm, "ramps": ramps, "protected": kept,
            "footprints": footprints_used, "idx": idx}


def report(b):
    Y, newY, ch = b["Y"], b["newY"], b["changed"]
    spec = b["spec"]
    up = (newY > Y) & ch
    down = (newY < Y) & ch
    print("basin: %d columns (ground <= %d); lip: %d columns" % (
        b["n_basin"], spec["basin"]["ground_at_or_below"], len(b["ring"])))
    print("character: %d stretches; %d peaks; %d entrances" % (len(b["segs"]), len(b["peaks"]), len(b["ent"])))
    for bi, e, d in b["ent"]:
        print("    %-24s ring %6d, %.0f blocks from its named point" % (e["id"], bi, d))
    if b["protected"]:
        print("settlements the sculpt was held off: %s" % ", ".join(
            "%s (%d columns)" % kv for kv in sorted(b["protected"], key=lambda kv: -kv[1])))
    print("columns changed: %d (raised %d, lowered %d)" % (ch.sum(), up.sum(), down.sum()))
    if up.any():
        r = (newY - Y)[up]
        print("  raised by:  median %.0f, p90 %.0f, max %.0f" % (
            np.median(r), np.percentile(r, 90), r.max()))
        print("  top y:      median %.0f, max %.0f (ceiling %d)" % (
            np.median(newY[up]), newY[up].max(), spec["ceiling"]["peak_max_y"]))
    if down.any():
        d = (Y - newY)[down]
        print("  lowered by: median %.0f, p90 %.0f, max %.0f" % (
            np.median(d), np.percentile(d, 90), d.max()))
    over = (newY > spec["ceiling"]["world_max_y"]).sum()
    print("columns over the world ceiling: %d (must be 0)" % over)
    if over:
        raise SculptError("the sculpt passes the heightmap's ceiling: it would clip on export")
    blocks = int(np.abs(newY - Y).sum())
    print("blocks of shape moved: %d" % blocks)
    return blocks


def sculpted(b):
    """The whole heightmap with the Rift's changed columns written in."""
    X0, X1, Z0, Z1 = b["box"]
    out = b["raw"].copy()
    h = np.clip(np.rint(RS.h_of_y(b["newY"], b["imp"], b["hi_out"])), 0, RS.FULL).astype(np.uint16)
    region = out[Z0 - b["oz"]:Z1 - b["oz"] + 1, X0 - b["ox"]:X1 - b["ox"] + 1]
    region[b["changed"]] = h[b["changed"]]
    return out


def write_plan(b, sha, blocks):
    """derived/rift_sculpt/: the plan (ring, segments, entrances) and the changed and basin masks."""
    X0, X1, Z0, Z1 = b["box"]
    MASK.mkdir(parents=True, exist_ok=True)
    np.save(MASK / "changed.npy", b["changed"])
    np.save(MASK / "basin.npy", b["basin"])
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps({
        "box": [X0, X1, Z0, Z1],
        "ring": [[int(x) + X0, int(z) + Z0] for z, x in b["ring"]],
        "normals": [[round(nx, 4), round(nz, 4)] for nz, nx in b["nrm"]],
        "segments": [[round(s, 1), round(e, 1), k] for s, e, k in b["segs"]],
        "peaks": b["peaks"],
        "entrances": [{"ring": bi, **{k: v for k, v in e.items() if k != "why"}} for bi, e, _ in b["ent"]],
        "top": [round(float(v), 1) for v in b["top"]],
        "width": [round(float(v), 1) for v in b["width"]],
        "floor": [round(float(v), 1) for v in b["floor"]],
        "plateau": [round(float(v), 1) for v in b["plateau"]],
        "heightmap": OUT_NAME, "sha256": sha, "blocks_moved": blocks, "footprints": b["footprints"],
    }), encoding="utf-8")


def applied_box(b, have):
    """The applied sculpt's own heights over the Rift's box: the ground that is really there, in y."""
    X0, X1, Z0, Z1 = b["box"]
    if have.shape != b["raw"].shape:
        raise SculptError("the applied sculpt is %s and the heightmap it was made from is %s: they are not the same "
                          "map, so nothing can be measured against it" % (have.shape, b["raw"].shape))
    sub = have[Z0 - b["oz"]:Z1 - b["oz"] + 1, X0 - b["ox"]:X1 - b["ox"] + 1]
    return RS.y_of_h(sub.astype(np.float64), b["imp"], b["hi_out"])


def measured_entrances(b, appY):
    """{entrance id: ring index} as the APPLIED sculpt holds them, read off the rim and not off data/routes.json.

    An entrance is the one part of the sculpt that follows data outside data/rift_sculpt.json: it snaps to where its
    route meets the lip. Victory Road was re-routed after the sculpt was applied (35f2a56), so re-snapping now moves
    its gap 47 stations and the plan would hand rift_skin, gulch_mine and the audits a way down that the heightmap
    does not have. Measuring it instead makes them agree with the world.

    The signal is the rim, and it is exact rather than fitted. Outside the lip the sculpt only ever RAISES -- the
    parapet is written with np.maximum -- and it skips every station of an entrance (`~open_i`). So an applied
    entrance is precisely a window of 2*gap+1 consecutive stations in which NO column outside the basin was raised,
    and the width comes from data/rift_sculpt.json's own `gap`, not from a tolerance. Where more than one such
    window exists the one nearest the station the data would snap to is taken, so a sculpt that has not drifted
    measures back to exactly what it was built from.
    """
    ring, basin, idx, Y = b["ring"], b["basin"], b["idx"], b["Y"]
    total = len(ring)
    zz, xx = np.nonzero((idx >= 0) & (~basin))
    rose = (appY[zz, xx] - Y[zz, xx]) > 0.5
    raised = np.bincount(idx[zz, xx], weights=rose.astype(np.float64), minlength=total) > 0
    if not raised.any():
        raise SculptError("no column outside the lip stands higher in %s than in the heightmap it was sculpted "
                          "from: that file holds no rim, so its entrances cannot be measured" % OUT_NAME)
    # a window that wraps the ring is one slice of the doubled prefix sum
    cs = np.concatenate([[0], np.cumsum(np.concatenate([raised, raised]).astype(np.int64))])

    def clear(bi, gap):
        s = (bi - gap) % total
        return cs[s + 2 * gap + 1] - cs[s] == 0

    at, spans = {}, []
    for bi0, e, _ in b["ent"]:
        gap = int(e["gap"])
        cand = [bi for bi in range(total) if clear(bi, gap)]
        if not cand:
            raise SculptError("%s: no window of %d stations in %s has an unraised rim, so the heightmap holds no gap "
                              "for this entrance. The applied sculpt is not the one data/rift_sculpt.json describes; "
                              "re-run --apply." % (e["id"], 2 * gap + 1, OUT_NAME))
        bi = min(cand, key=lambda i: (min(abs(i - bi0), total - abs(i - bi0)), i))
        at[e["id"]] = bi
        spans.append((e["id"], bi, gap, bi0))
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            (ai, abi, ag, _), (bj, bbi, bg, _) = spans[i], spans[j]
            if min(abs(abi - bbi), total - abs(abi - bbi)) <= ag + bg:
                raise SculptError("%s and %s both measure to the same gap in %s (stations %d and %d): the heightmap "
                                  "holds fewer ways in than data/rift_sculpt.json names, and a plan that says "
                                  "otherwise would route two descents through one. Re-run --apply."
                                  % (ai, bj, OUT_NAME, abi, bbi))
    for eid, bi, gap, bi0 in sorted(spans, key=lambda s: -min(abs(s[1] - s[3]), total - abs(s[1] - s[3]))):
        d = min(abs(bi - bi0), total - abs(bi - bi0))
        print("    %-24s applied gap at ring %6d%s" % (
            eid, bi, "" if not d else ", %d stations from the %d today's data would snap it to" % (d, bi0)))
    return at


def differ_where(b, have, out):
    """Where the recomputed sculpt and the applied file part company, named by the nearest entrance: a refusal that
    says only how many columns differ sends the next session to re-derive what this one already knows."""
    X0, X1, Z0, Z1 = b["box"]
    d = (have != out)[Z0 - b["oz"]:Z1 - b["oz"] + 1, X0 - b["ox"]:X1 - b["ox"] + 1]
    zz, xx = np.nonzero(d)
    bits = []
    for bi, e, _ in b["ent"]:
        rz, rx = b["ring"][bi]
        n = int((np.hypot(zz - rz, xx - rx) < 400).sum())
        if n:
            bits.append("%s %d" % (e["id"], n))
    far = int(len(zz) - sum(int(p.rsplit(" ", 1)[1]) for p in bits))
    if far > 0:
        bits.append("away from every entrance %d" % far)
    return "; ".join(bits) or "nowhere near the lip"


def plan_only(source_root, world_path):
    """Write the plan for the heightmap data/world.json already names, measured from the sculpt it applied.

    It sculpts with the town footprints the last --apply recorded, not today's data/towns.json: a town sited or moved
    since (the rim post moved 178 blocks after the sculpt) would otherwise change the answer. For the same reason the
    entrances are measured off the applied rim rather than re-snapped to today's routes (measured_entrances)."""
    world = T.load_world(world_path)
    rec = world["heightmap"].get("rift_sculpted_from") or {}
    if "footprints" not in rec:
        raise SculptError("data/world.json heightmap.rift_sculpted_from records no footprints: the sculpt cannot be "
                          "reproduced from it")
    b = build(source_root, world_path, footprints=rec["footprints"])
    hm = b["world"]["heightmap"]
    target, target_sha, via = plan_target(hm, b["current"])
    have = np.array(Image.open(target)).astype(np.uint16)
    at = measured_entrances(b, applied_box(b, have))
    if any(at[e["id"]] != bi for bi, e, _ in b["ent"]):
        # the gap moved, so the rim profile, the ramps and the peaks that avoid an entrance all move with it
        print("  re-sculpting with the gaps the heightmap holds", flush=True)
        b = build(source_root, world_path, footprints=rec["footprints"], ent_at=at)
    blocks = report(b)
    was = rec.get("blocks_moved")
    if was is not None:
        print("blocks moved, against the %d data/world.json recorded when it was applied: %s" % (
            was, "the same" if was == blocks else "DIFFERENT by %d" % (blocks - was)))
    out = sculpted(b)
    if have.shape != out.shape:
        raise SculptError("%s is %s, the sculpt %s" % (target.name, have.shape, out.shape))
    differ = int((have != out).sum())
    if differ:
        raise SculptError("the sculpt differs from %s in %d columns even with its entrances measured off the rim "
                          "(%s): something other than the entrances has moved since the last --apply -- the region "
                          "polygon, data/rift_sculpt.json, or the sculpt's own code -- and reconciling that is a "
                          "decision for --apply, not --plan"
                          % (target.name, differ, differ_where(b, have, out)))
    write_plan(b, target_sha, blocks)
    print("wrote %s for %s (%s)%s; the heightmap and data/world.json are untouched"
          % (PLAN.relative_to(ROOT), OUT_NAME, target_sha[:12], via))
    return 0


def plan_target(hm, current):
    """(file, sha256, note) the plan must be verified against: the sculpt's own output, wherever it now sits.

    `--plan` proves the sculpt reproduces a real file before describing it, and that check is the whole value of
    the mode. It used to compare against the heightmap data/world.json PINS, which was the same file only while the
    sculpt was the last pass over the heightmap. The water export (2026-09-29) added a pass on top, so the pin
    became land_8k_16_rescaled_b145_pads_rift_water.png and `--plan` refused -- in EVERY checkout, not just an
    agent's, which left derived/rift_sculpt/ unreproducible and the Rift's block passes resting on a folder nothing
    could rebuild (docs/research/AGENT_WORKTREE_INPUTS.md).

    The sculpt's output is still on disk and data/world.json still names AND hashes it, as one of the heightmap's
    provenance entries -- `water_shaped_from` today. So the target is found by asking the data which entry names
    OUT_NAME, rather than by hardcoding one hop: another pass layered on later moves the pin again and this keeps
    working. The sha is checked, so a plan can never describe a file that is not the one the chain recorded.
    """
    if current.name == OUT_NAME:
        return current, hm["sha256"], ""
    named = sorted(k for k, v in hm.items()
                   if isinstance(v, dict) and v.get("path") == OUT_NAME and v.get("sha256"))
    if not named:
        raise SculptError(
            "data/world.json pins %s, and no heightmap provenance entry names the sculpt %s, so there is nothing to "
            "verify the plan against. --apply records the sculpt; a later pass over the heightmap must record what "
            "it consumed (path and sha256) or the sculpt becomes unreproducible."
            % (current.name, OUT_NAME))
    shas = {hm[k]["sha256"] for k in named}
    if len(shas) > 1:
        # Found by this function's test author: `sorted(named)[0]` picked one silently and ignored the
        # rest. Two entries claiming the sculpt with DIFFERENT hashes means the chain disagrees with
        # itself about what was applied, and guessing which is right is exactly the kind of quiet choice
        # that let the hand-edited plan sha hide a drift for two days.
        raise SculptError("data/world.json has %d heightmap provenance entries naming the sculpt %s with "
                          "DIFFERENT sha256s (%s): the chain disagrees with itself about what was applied, "
                          "and --plan will not guess which one. Reconcile them."
                          % (len(named), OUT_NAME, ", ".join("%s=%s" % (k, hm[k]["sha256"][:12]) for k in named)))
    key = named[0]
    sha = hm[key]["sha256"]
    # the entry records a filename only, so the sculpt output is expected beside the pinned heightmap;
    # every pass in the chain writes into that one directory (docs/world-building/HEIGHTMAP_PROVENANCE.md)
    target = current.parent / OUT_NAME
    if not target.exists():
        raise SculptError("data/world.json's %s names %s, which is not beside %s. The sculpt output is the one file "
                          "--plan can be verified against; without it, re-run --apply."
                          % (key, OUT_NAME, current.name))
    got = hashlib.sha256(target.read_bytes()).hexdigest()
    if got != sha:
        raise SculptError("%s hashes to %s, but data/world.json's %s records %s: the file beside the heightmap is "
                          "not the sculpt the chain recorded." % (OUT_NAME, got[:12], key, sha[:12]))
    return target, sha, ", reached through heightmap.%s because the pin has moved on to %s" % (key, current.name)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root")
    ap.add_argument("--world", default=str(ROOT / "data" / "world.json"))
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write the heightmap, the plan and data/world.json")
    mode.add_argument("--plan", action="store_true",
                      help="write only derived/rift_sculpt/, for the heightmap data/world.json already names")
    a = ap.parse_args(argv)
    if a.plan:
        return plan_only(a.source_root, a.world)
    b = build(a.source_root, a.world)
    blocks = report(b)
    if not a.apply:
        print("(dry run -- pass --apply, or --plan)")
        return 0

    dest = b["current"].parent / OUT_NAME
    Image.fromarray(sculpted(b), mode="I;16").save(dest)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    write_plan(b, sha, blocks)

    wpath = Path(a.world)
    text = wpath.read_text(encoding="utf-8")
    doc = json.loads(text)
    hm = doc["heightmap"]
    old_sha = hm["sha256"]
    hm["path"], hm["sha256"] = OUT_NAME, sha
    hm["rift_sculpted_from"] = {**b["base_ref"], "generator": "python tools/rift_heightmap.py --apply",
                           "spec": "data/rift_sculpt.json", "blocks_moved": blocks,
                           "columns_changed": int(b["changed"].sum()), "footprints": b["footprints"],
                           "note": "The Rift's shape: the lip of the low-ground basin, a cut band inside it, and the "
                                   "upthrust rim outside. Columns outside the Rift's box are bit-identical."}
    if old_sha != sha and old_sha not in hm.get("previous_sha256", []):
        hm["previous_sha256"] = [old_sha] + hm.get("previous_sha256", [])
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
    wpath.write_text(text[:brace] + json.dumps(hm, indent=2)[0:] + text[i + 1:], encoding="utf-8")
    print("wrote %s (%s) and data/world.json" % (dest.name, sha[:12]))
    print("wrote %s" % PLAN.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
