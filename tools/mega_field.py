#!/usr/bin/env python
"""The Mega field: the south-west Rift basin as one hostile Mega farm (the owner, 2026-10-03).

THE OWNER, 2026-10-03, on the map: "everywhere in the red inside the rift should be the mega area, not just spawn one
randomly in the world. the idea is an aggressive and hostile resource farm ... you would go in and fight high level
megas that in theory should require more than one mon to kill and get a reward to spend in the big town next to this
area in the rift." The design it returns to is docs/world-building/SOUTHERN_RIFT_MEGA.md section 13 (2026-09-27), whose
two sites (4090, 116, 5289) and (3738, 87, 5164) are both inside this field; docs/world-building/MEGA_FIELD.md is the
write-up.

This tool AUTHORS; it never builds. The farm's dens are ordinary data/gulch_mine.json `farms[].dens` and are built by
tools/gulch_mine.py's keeper exactly as every other den (step R9S). Ground comes from tools/ground.py, never a world.

  python tools/mega_field.py trace            # the field's polygon from the Rift sculpt's lip ring (prints JSON)
  python tools/mega_field.py map --out <png>  # the heightmap, the field, the gulch and the town, for the owner
  python tools/mega_field.py sites            # the dens' anchors, laid out inside the field (prints JSON)

`trace` and `sites` print what goes into data/gulch_mine.json (`mega_field.polygon`, `farms`); they never write it.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground as G  # noqa: E402
import gulch_mine as GM  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "gulch_mine.json"


class FieldError(Exception):
    pass


def load():
    return json.loads(SPEC.read_text(encoding="utf-8"))


def point_in(poly, x, z):
    """Even-odd test, the same rule as tools/gulch_mine.py point_in, vectorised for numpy arrays of x and z."""
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    res = np.zeros(np.broadcast(x, z).shape, dtype=bool)
    n = len(poly)
    for i in range(n):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % n]
        if z0 == z1:
            continue
        c = (z0 > z) != (z1 > z)
        xi = x0 + (z - z0) * (x1 - x0) / (z1 - z0)
        res ^= c & (x < xi)
    return res


SQUARE_REACH = 3


def trace(spec, source_root=None):
    """The field: the sculpt's lip ring from the gulch zone's south-west end, away from the gulch, round the south-west
    basin and up its west wall to the ring point nearest `cut_near`; then straight across the stem to the gulch zone's
    first vertex (its north-east end) and along the gulch zone's own closing line back to the start, so the two share
    that edge exactly and do not overlap. Along the rim the edge runs `rim_outset` outside the lip, as the gulch zone's
    does (gulch_mine.json zone.trace), so no basin column at the cliff's foot is left out by the simplification."""
    ft = spec["mega_field"]["trace"]
    ring, nrm, _ent = GM.sculpt_ring(source_root)
    T = len(ring)

    def nearest(p):
        return min(range(T), key=lambda k: (ring[k][0] - p[0]) ** 2 + (ring[k][1] - p[1]) ** 2)
    kA = nearest(spec["zone"]["trace"]["to_near"])
    kW = nearest(ft["cut_near"])
    kE = nearest(spec["zone"]["trace"]["from_near"])
    # the arc away from the gulch: from kA the ring's index runs on round the south-west basin (the gulch zone itself
    # is the arc kE..kA, gulch_mine.py trace), so kW must lie on kA's far side before kE comes round again
    if not ((kW - kA) % T < (kE - kA) % T):
        raise FieldError("cut_near's ring point %d is not on the arc from the gulch's south-west end (%d) away from the "
                         "gulch before its north-east end (%d)" % (kW, kA, kE))
    n = (kW - kA) % T + 1
    zp = spec["zone"]["polygon"]
    o = ft["rim_outset"]

    def vertex(i, along_ring):
        k = (kA + i) % T
        x, z = ring[k]
        if not along_ring:
            # the normals point into the basin (gulch_mine.py trace): minus is outward
            return [round(x - nrm[k][0] * o, 1), round(z - nrm[k][1] * o, 1)]
        # the sculpt's normals are smoothed, and where the lip turns sharply one can lie nearly ALONG the lip, so the
        # outset slides down the ring instead of out of it: here the outward direction is taken square to the ring
        # itself (the chord over two points either side), on the side the normal says is outward
        a, b = ring[(k - 2) % T], ring[(k + 2) % T]
        tx, tz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tx, tz) or 1.0
        px, pz = tz / L, -tx / L
        if px * -nrm[k][0] + pz * -nrm[k][1] < 0:
            px, pz = -px, -pz
        return [round(x + px * o, 1), round(z + pz * o, 1)]

    # no lip column is left out (the lip is the basin's edge, so a basin column the polygon misses is a lip column):
    # where the simplification cuts one, its run vertex is kept (the run is simplified in pieces either side of it);
    # where even the unsimplified outset misses one, that vertex is set square to the ring. Both only ever act where a
    # lip column falls outside, so everywhere else the polygon is the plain simplified outset
    keep, square = set(), set()
    while True:
        run = [vertex(i, i in square) for i in range(n)]
        cuts = [0] + sorted(keep) + [n - 1]
        poly = []
        for c0, c1 in zip(cuts, cuts[1:]):
            if c1 > c0:
                piece = GM.simplify(run[c0:c1 + 1], ft["tolerance"])
                poly += piece if not poly else piece[1:]
        poly = poly + [list(zp[0]), list(zp[-1])]
        # the last ring point is the stem cut's own end (the cut line, not the rim), so it is not a lip column to keep
        miss = [i for i in range(n - 1) if not point_in(poly, ring[(kA + i) % T][0] + 0.5, ring[(kA + i) % T][1] + 0.5)
                and not point_in(zp, ring[(kA + i) % T][0] + 0.5, ring[(kA + i) % T][1] + 0.5)]
        if not miss:
            break
        grew = False
        for i in miss:
            if i not in keep:
                keep.add(i)
                grew = True
                continue
            # squared, with SQUARE_REACH ring points either side, so the outset does not fold back on its neighbours
            for j in range(max(0, i - SQUARE_REACH), min(n - 1, i + SQUARE_REACH + 1)):
                if j not in square:
                    square.add(j)
                    keep.add(j)
                    grew = True
        if not grew:
            # nothing left to try: the polygon is returned as it is and the misses named (check reports them; the
            # independent audit, tools/mega_field_audit.py, finds them on the basin itself)
            break
    return {"ring_from": [kA, ring[kA]], "ring_cut": [kW, ring[kW]], "ring_to": [kE, ring[kE]],
            "cut_blocks": round(math.dist(ring[kW], ring[kE]), 1), "lip_kept": sorted((kA + i) % T for i in keep),
            "lip_squared": sorted((kA + i) % T for i in square), "lip_missed": sorted((kA + i) % T for i in miss),
            "polygon": poly}


def columns(poly):
    """(x0, z0, x1, z1, mask) of the polygon's columns: a column counts when its centre is inside."""
    xs = [p[0] for p in poly]
    zs = [p[1] for p in poly]
    x0, z0, x1, z1 = int(math.floor(min(xs))), int(math.floor(min(zs))), int(math.ceil(max(xs))), int(math.ceil(max(zs)))
    gx, gz = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(z0, z1 + 1) + 0.5)
    return x0, z0, x1, z1, point_in(poly, gx, gz)


def draw_map(spec, out, source_root=None, sites=None):
    from PIL import Image, ImageDraw
    g = G.Ground(source_root)
    poly = spec["mega_field"]["polygon"]
    zp = spec["zone"]["polygon"]
    X0, Z0, X1, Z1 = 3440, 4280, 4720, 5480
    S = 0.6
    h = g.heights[Z0:Z1, X0:X1].astype(float)
    gz_, gx_ = np.gradient(h)
    shade = np.clip(0.62 + (-gx_ - gz_) * 0.12, 0.15, 1.0)
    t = np.clip((h - 80.0) / 120.0, 0, 1)
    rgb = np.dstack([(70 + 150 * t) * shade, (75 + 140 * t) * shade, (70 + 110 * t) * shade])
    _x0, _z0, _x1, _z1, m = columns(poly)
    full = np.zeros(h.shape, dtype=bool)
    full[_z0 - Z0:_z1 - Z0 + 1, _x0 - X0:_x1 - X0 + 1] = m
    rgb[full] = rgb[full] * 0.55 + np.array([120, 20, 20]) * 0.45
    # Victory Road's clearance (layout.road_clear): no den inside it, so it shows paler
    lay = spec["mega_field"].get("layout")
    if lay:
        vr0 = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"][lay["road"]]
        near = [p for p in vr0[::2] if X0 - 200 <= p[0] < X1 + 200 and Z0 - 200 <= p[1] < Z1 + 200]
        gx4, gz4 = np.meshgrid(np.arange(X0, X1, 4) + 2, np.arange(Z0, Z1, 4) + 2)
        band = seg_dist(gx4, gz4, near) < lay["road_clear"]
        band = np.repeat(np.repeat(band, 4, axis=0), 4, axis=1)[:h.shape[0], :h.shape[1]] & full
        rgb[band] = rgb[band] * 0.6 + np.array([200, 160, 160]) * 0.4
    img = Image.fromarray(rgb.clip(0, 255).astype(np.uint8)).resize((int((X1 - X0) * S), int((Z1 - Z0) * S)))
    d = ImageDraw.Draw(img)

    def P(x, z):
        return ((x - X0) * S, (z - Z0) * S)
    d.line([P(*p) for p in poly] + [P(*poly[0])], fill=(255, 40, 40), width=2)
    d.line([P(*p) for p in zp] + [P(*zp[0])], fill=(80, 170, 255), width=2)
    d.text(P(4300, 4740), "the gulch (badge 6)", fill=(80, 170, 255))
    sq = spec["town"]["square"]["rect"]
    d.rectangle([P(sq[0], sq[1]), P(sq[2], sq[3])], outline=(0, 255, 255), width=2)
    d.text(P(sq[0] - 40, sq[1] - 22), "Cutters' square", fill=(0, 255, 255))
    vr = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]["victory_road"]
    d.line([P(*p) for p in vr[::3] if X0 <= p[0] < X1 and Z0 <= p[1] < Z1], fill=(255, 255, 255), width=1)
    d.text(P(3560, 5420), "Victory Road (white)", fill=(255, 255, 255))
    marks = spec["mega_field"]["owner_marks"]
    cx, cz = marks["cursor"]
    d.line([P(cx - 18, cz), P(cx + 18, cz)], fill=(255, 255, 0), width=2)
    d.line([P(cx, cz - 18), P(cx, cz + 18)], fill=(255, 255, 0), width=2)
    d.text(P(cx + 20, cz - 20), "owner's cursor", fill=(255, 255, 0))
    for x, _y, z in marks["section_13"]:
        d.rectangle([P(x - 8, z - 8), P(x + 8, z + 8)], outline=(255, 255, 0), width=2)
    for fa in spec.get("farms", []):
        for den in fa["dens"]:
            x, _y, z = den["anchor"]
            L = den.get("leash", 0)
            if fa["id"].startswith("field_") and L:
                d.ellipse([P(x - L, z - L), P(x + L, z + L)], outline=(255, 190, 90), width=1)
            d.ellipse([P(x - 6, z - 6), P(x + 6, z + 6)], fill=(255, 140, 0))
    for fa in spec.get("superseded_farms", []):
        for den in fa["dens"]:
            x, _y, z = den["anchor"]
            if X0 <= x < X1 and Z0 <= z < Z1:
                d.line([P(x - 8, z - 8), P(x + 8, z + 8)], fill=(160, 160, 160), width=2)
                d.line([P(x - 8, z + 8), P(x + 8, z - 8)], fill=(160, 160, 160), width=2)
    for x in range((X0 // 128 + 1) * 128, X1, 128):
        d.text(P(x, Z0 + 3), str(x), fill=(230, 230, 230))
    for z in range((Z0 // 128 + 1) * 128, Z1, 128):
        d.text(P(X0 + 3, z), str(z), fill=(230, 230, 230))
    d.text((6, img.size[1] - 30), "red: the Mega field (pale: Victory Road's clearance, no den)   blue: the gulch zone",
           fill=(255, 255, 255))
    d.text((6, img.size[1] - 16), "yellow: owner's cursor and section-13 sites   orange: dens   grey x: retired dens", fill=(255, 255, 255))
    img.save(out)
    return img.size


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("trace", "map", "sites", "dress", "check", "floor"))
    p.add_argument("--source-root")
    p.add_argument("--out")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    spec = load()
    if a.mode == "check":
        probs = check(spec, a.source_root)
        for pr in probs:
            print("PROBLEM:", pr)
        if probs:
            raise SystemExit("mega_field: %d problem(s)" % len(probs))
        print("mega_field: the committed polygon and farms are what trace and sites derive (%d farms, %d dens)"
              % (len(spec["farms"]), sum(len(f["dens"]) for f in spec["farms"])))
        return 0
    if a.mode == "trace":
        r = trace(spec, a.source_root)
        _x0, _z0, _x1, _z1, m = columns(r["polygon"])
        r["columns"] = int(m.sum())
        print(json.dumps(r))
        return 0
    if a.mode == "map":
        if not a.out:
            raise SystemExit("map needs --out")
        print("wrote %s %s" % (a.out, draw_map(spec, a.out, a.source_root)))
        return 0
    if a.mode == "sites":
        print(json.dumps(sites(spec, a.source_root), indent=1))
        return 0
    if a.mode == "dress":
        print(json.dumps(dress(spec, a.source_root), indent=1))
        return 0
    if a.mode == "floor":
        rows, _M = floor_counts(spec, a.source_root)
        for k, v in rows:
            print("%-72s %8d" % (k, v))
        r = ranges(spec, a.source_root)
        print(json.dumps({k: v for k, v in r.items() if k != "pairs"}))
        return 0
    return 1


def check(spec, source_root=None):
    """Drift, not correctness: the committed mega_field.polygon, farms_grid and farms against a fresh trace and a
    fresh sites run. It is the generator checking its own output was pasted and not edited since; it is NOT the
    independent audit (MEGA_FIELD.md section 5 lists what that must check, from other sources)."""
    probs = []
    t = trace(spec, source_root)
    if t["lip_missed"]:
        probs.append("%d lip column(s) outside the traced field even with their vertices kept and set square to the "
                     "ring, e.g. ring %s" % (len(t["lip_missed"]), t["lip_missed"][:5]))
    if t["polygon"] != spec["mega_field"]["polygon"]:
        probs.append("mega_field.polygon differs from `mega_field.py trace` (%d vertices traced, %d committed)"
                     % (len(t["polygon"]), len(spec["mega_field"]["polygon"])))
        return probs
    s = sites(spec, source_root)
    if s["farms"] != spec["farms"]:
        probs.append("farms differ from `mega_field.py sites` (%d farms derived, %d committed)"
                     % (len(s["farms"]), len(spec["farms"])))
    fg = {k: spec["farms_grid"][k] for k in ("x", "y", "z")}
    if s["farms_grid"] != fg:
        probs.append("farms_grid %s differs from the field's derived %s" % (fg, s["farms_grid"]))
    have = json.loads(DENS.read_text(encoding="utf-8"))["dens"]
    want = dress(spec, source_root)
    if have != want:
        probs.append("data/mega_dens.json dens differ from `mega_field.py dress` (%d derived, %d committed)" % (len(want), len(have)))
    return probs


DENS = ROOT / "data" / "mega_dens.json"
COPY = ("sign", "feature", "feature_r", "dig", "pad", "scrape", "boulder", "path", "signature", "most_visible")


def dress(spec, source_root=None):
    """data/mega_dens.json `dens` records for the field's dens: each takes the lair KIT of one of the seven 2026-10-02
    records (mega_dens.json superseded_dens, by species; mega_field.dressing.kit_of names which), so its sign, feature,
    palettes and signature are hand-authored ones the builder and its audit already know. What is per den is geometry,
    derived as the original records were (mega_dens.json approach_why, feature_why, bounds_why): approach_toward the
    nearest point of the critical path (data/route_paths.json), feature_at feature_r from the anchor on the side away
    from it, write_box the anchor +- 27 and its ground - 8 .. + 14."""
    md = json.loads(DENS.read_text(encoding="utf-8"))
    # the kits are the seven hand-authored records only, never a field den's own (which would copy a copy)
    kits = {r["species"]: r for r in md["superseded_dens"]}
    kit_of = spec["mega_field"]["dressing"]["kit_of"]
    g = G.Ground(source_root)
    paths = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    crit = np.array([p for pts in paths.values() for p in pts], dtype=float)
    out = []
    for fa in spec["farms"]:
        if not fa["id"].startswith("field_"):
            continue
        for d in fa["dens"]:
            ax, ay, az = d["anchor"]
            kit = kits[kit_of[d["species"]]]
            k = int(np.argmin((crit[:, 0] - ax) ** 2 + (crit[:, 1] - az) ** 2))
            tx, tz = int(crit[k][0]), int(crit[k][1])
            L = math.hypot(tx - ax, tz - az) or 1.0
            fr = kit["feature_r"]
            fx, fz = int(round(ax - (tx - ax) / L * fr)), int(round(az - (tz - az) / L * fr))
            gy = g(ax, az)
            if gy != ay - 1:
                raise FieldError("%s: anchor y %d is not round(ground) + 1 = %d" % (d["id"], ay, gy + 1))
            rec = {"den": d["id"], "species": d["species"], "kit": kit["den"]}
            for c in COPY:
                if c in kit:
                    rec[c] = kit[c]
            rec["feature_at"] = [fx, fz]
            rec["approach_toward"] = [tx, tz]
            lr = spec["mega_field"]["layout"]["lair_radius"]
            rec["write_box"] = [ax - lr, gy - 8, az - lr, ax + lr, gy + 14, az + lr]
            out.append(rec)
    return out


def point_dist(px, pz, pts, chunk=16384):
    """Distance from each (px, pz) to the nearest of pts, chunked over both so no matrix outgrows memory."""
    px = np.asarray(px, dtype=float).ravel()
    pz = np.asarray(pz, dtype=float).ravel()
    p = np.asarray(pts, dtype=float).reshape(-1, 2)
    d = np.full(px.shape, np.inf)
    if not len(p):
        return d
    for i in range(0, len(px), chunk):
        a, b = px[i:i + chunk, None], pz[i:i + chunk, None]
        for j in range(0, len(p), 256):
            q = p[j:j + 256]
            d[i:i + chunk] = np.minimum(d[i:i + chunk], np.sqrt((a - q[:, 0]) ** 2 + (b - q[:, 1]) ** 2).min(-1))
    return d


def _coarse(x0, z0, x1, z1, fn, step=2):
    """fn(px, pz) evaluated on a `step` grid over the inclusive box and spread back to every column (nearest cell), so a
    distance is right to within step / sqrt 2 blocks; returns a (z, x) array the shape of the box."""
    xs = np.arange(x0, x1 + 1, step) + step / 2.0
    zs = np.arange(z0, z1 + 1, step) + step / 2.0
    cx, cz = np.meshgrid(xs, zs)
    v = np.asarray(fn(cx.ravel(), cz.ravel())).reshape(cx.shape)
    v = np.repeat(np.repeat(v, step, axis=0), step, axis=1)
    return v[:z1 - z0 + 1, :x1 - x0 + 1]


def others(spec):
    """What inside or beside the field is another system's, as (what, x, z, reach) discs: the Rift zones' walls and
    posts (data/rift_zones.json; 32, the lairs' footprint rule) and the layout's keep_clear. The gulch's zone and block
    box, Victory Road and the critical path are measured as lines and areas in floor()."""
    rz = json.loads((ROOT / "data" / "rift_zones.json").read_text(encoding="utf-8"))
    out = []
    for cut in rz.get("cuts") or []:
        out += [("wall " + cut["id"], c[0], c[1], 32) for c in cut.get("line") or []]
    for zid, zz in rz["zones"].items():
        for post in zz.get("posts") or []:
            if isinstance(post.get("at"), list):
                out.append(("%s post %s" % (zid, post.get("id")), post["at"][0], post["at"][1], 32))
    for kc in spec["mega_field"]["layout"]["keep_clear"]:
        out.append(("keep_clear", kc["at"][0], kc["at"][1], kc["r"]))
    return out


def floor(spec, source_root=None):
    """The field's floor, measured on the canonical heightmap (never a world), column by column, as (z, x) masks over
    the polygon's box: `field` (inside the polygon), `dry` (no painted water: tools/water_mask.py's rule, the sea and
    every lake basin, vectorised), `walk` (no 4-neighbour step over one block), and the distances every rule needs:
    `road` (Victory Road's walked line), `crit` (every critical path), `gulch` (the gulch zone's edge; negative inside),
    `other` (the nearest wall, post or keep_clear disc, less its reach). Returns (box, masks, ground)."""
    import water_mask as WM
    mf = spec["mega_field"]
    lay = mf["layout"]
    poly = mf["polygon"]
    g = G.Ground(source_root)
    x0, z0, x1, z1, field = columns(poly)
    H = g.box(x0, z0, x1, z1)
    gx, gz = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(z0, z1 + 1) + 0.5)
    wet = H < WM.sea_level()
    for _bid, b in WM.bodies().items():
        rings = [r for r in b["basin"] if r]
        if not rings:
            continue
        bx = [p[0] for r in rings for p in r]
        bz = [p[1] for r in rings for p in r]
        if max(bx) < x0 or min(bx) > x1 or max(bz) < z0 or min(bz) > z1:
            continue
        inb = np.zeros(field.shape, dtype=bool)
        for r in rings:
            inb |= point_in(r, gx, gz)
        wet |= inb & (H < b["level_y"])
    steep = np.zeros(field.shape, dtype=bool)
    dz, dx = np.abs(np.diff(H, axis=0)) > 1, np.abs(np.diff(H, axis=1)) > 1
    steep[:-1, :] |= dz
    steep[1:, :] |= dz
    steep[:, :-1] |= dx
    steep[:, 1:] |= dx
    paths = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    reach = 400

    def near(pts):
        return [p for p in pts if x0 - reach <= p[0] <= x1 + reach and z0 - reach <= p[1] <= z1 + reach]
    vr = near(paths[lay["road"]])
    crit = near([p for pts in paths.values() for p in pts])
    zp = spec["zone"]["polygon"]
    road = _coarse(x0, z0, x1, z1, lambda a, b: point_dist(a, b, vr))
    critd = _coarse(x0, z0, x1, z1, lambda a, b: point_dist(a, b, crit))
    gul = _coarse(x0, z0, x1, z1, lambda a, b: edge_dist(zp, a, b) * np.where(point_in(zp, a, b), -1, 1))
    oth = np.full(field.shape, np.inf)
    for _w, ox, oz, r in others(spec):
        if x0 - r - 64 <= ox <= x1 + r + 64 and z0 - r - 64 <= oz <= z1 + r + 64:
            oth = np.minimum(oth, np.hypot(gx - ox, gz - oz) - r)
    bx, bz = spec["grid"]["x"], spec["grid"]["z"]
    in_grid = (gx >= bx[0]) & (gx <= bx[1] + 1) & (gz >= bz[0]) & (gz <= bz[1] + 1)
    return (x0, z0, x1, z1), {"field": field, "dry": ~wet, "walk": ~steep, "road": road, "crit": critd, "gulch": gul,
                              "other": oth, "in_grid": in_grid}, H


def floor_counts(spec, source_root=None):
    """The floor in columns (one column = one square block of floor), each line a subset of the one before it, and
    what each removes. `mega floor` is where a field Mega may stand: dry, walkable, outside the gulch's zone by
    megas.spawn_clear, off every other system's disc and further from Victory Road's walked line than road_clear less
    the leash (no Mega comes nearer). `dressing floor` is where this field's blocks may be written: the lairs' footprint
    rule (tools/mega_dens_audit.py), 128 from every critical path, off the gulch's block box and zone, 32 off a wall or
    post."""
    lay = spec["mega_field"]["layout"]
    _box, M, _H = floor(spec, source_root)
    f = M["field"]
    rows = [("field (inside mega_field.polygon)", f)]
    rows.append(("  dry (no painted water)", rows[-1][1] & M["dry"]))
    rows.append(("  walkable (no step over one block)", rows[-1][1] & M["walk"]))
    walk = rows[-1][1]
    mega = walk & (M["gulch"] >= spec["megas"]["spawn_clear"]) & (M["other"] >= 0) & \
        (M["road"] >= lay["road_clear"] - lay["leash"])
    rows.append(("  mega floor (off the road band, the gulch, the posts and keep_clear)", mega))
    dress = walk & (M["crit"] >= 128) & ~M["in_grid"] & (M["gulch"] > 32) & (M["other"] >= 0)
    rows.append(("  dressing floor (the lairs' footprint rule)", dress))
    out = [(k, int(v.sum())) for k, v in rows]
    # the gulch's own floor, for the record: it is the Cutters' town, the mine and the gate, and holds no field den
    g = G.Ground(source_root)
    zx0, zz0, zx1, zz1, zm = columns(spec["zone"]["polygon"])
    zH = g.box(zx0, zz0, zx1, zz1)
    st = np.zeros(zm.shape, dtype=bool)
    dz, dx = np.abs(np.diff(zH, axis=0)) > 1, np.abs(np.diff(zH, axis=1)) > 1
    st[:-1, :] |= dz
    st[1:, :] |= dz
    st[:, :-1] |= dx
    st[:, 1:] |= dx
    out.append(("the gulch zone (the town, the mine, the gate: no field den)", int(zm.sum())))
    out.append(("  walkable", int((zm & ~st).sum())))
    return out, M


def ranges(spec, source_root=None, M=None):
    """How the dens' ranges (leash discs) lie on the mega floor: covered columns, columns in two or more ranges, and
    every overlapping pair with its overlap depth (2 x leash - distance, blocks along the line between the homes)."""
    lay = spec["mega_field"]["layout"]
    (x0, z0, x1, z1), M2, _H = floor(spec, source_root) if M is None else M
    walk = M2["field"] & M2["dry"] & M2["walk"]
    mega = walk & (M2["gulch"] >= spec["megas"]["spawn_clear"]) & (M2["other"] >= 0) & \
        (M2["road"] >= lay["road_clear"] - lay["leash"])
    gx, gz = np.meshgrid(np.arange(x0, x1 + 1), np.arange(z0, z1 + 1))
    n = np.zeros(mega.shape, dtype=int)
    dens = [d for fa in spec["farms"] if fa["id"].startswith("field_") for d in fa["dens"]]
    for d in dens:
        n += (np.hypot(gx - d["anchor"][0], gz - d["anchor"][2]) <= d["leash"]).astype(int)
    pairs = []
    for i, a in enumerate(dens):
        for b in dens[i + 1:]:
            s = math.hypot(a["anchor"][0] - b["anchor"][0], a["anchor"][2] - b["anchor"][2])
            if s < a["leash"] + b["leash"]:
                pairs.append((a["id"], b["id"], round(s, 1), round(a["leash"] + b["leash"] - s, 1)))
    nb = {d["id"]: sum(1 for p in pairs if d["id"] in p[:2]) for d in dens}
    return {"mega floor": int(mega.sum()), "in a range": int((mega & (n >= 1)).sum()),
            "in two or more": int((mega & (n >= 2)).sum()), "in three or more": int((mega & (n >= 3)).sum()),
            "overlapping pairs": len(pairs), "dens": len(dens),
            "neighbours per den": [min(nb.values()) if nb else 0, max(nb.values()) if nb else 0],
            "overlap depth": [min(p[3] for p in pairs), max(p[3] for p in pairs)] if pairs else None,
            "pairs": pairs}


def _h(x, z, salt):
    """A deterministic 0..1 hash of a column (the order candidates are tried in), from the layout's seed."""
    v = (x * 73856093) ^ (z * 19349663) ^ (salt * 83492791)
    v = (v ^ (v >> 13)) * 1274126177 & 0xFFFFFFFF
    return (v ^ (v >> 16)) / 0xFFFFFFFF


def seg_dist(px, pz, pts):
    """Distance from each (px, pz) to the nearest of pts (a dense walked line: data/route_paths.json is a point per
    block, so the nearest point is the line to within half a block)."""
    p = np.asarray(pts, dtype=float)
    d = np.full(np.shape(px), np.inf)
    for i in range(0, len(p), 512):
        q = p[i:i + 512]
        dd = np.sqrt((np.asarray(px)[..., None] - q[:, 0]) ** 2 + (np.asarray(pz)[..., None] - q[:, 1]) ** 2).min(-1)
        d = np.minimum(d, dd)
    return d


def edge_dist(poly, px, pz):
    """Distance from each point to the polygon's boundary."""
    p = np.asarray(poly, dtype=float)
    a, b = p, np.roll(p, -1, axis=0)
    px = np.asarray(px, dtype=float)[..., None]
    pz = np.asarray(pz, dtype=float)[..., None]
    ab = b - a
    L2 = (ab ** 2).sum(1)
    L2[L2 == 0] = 1e-9
    t = np.clip(((px - a[:, 0]) * ab[:, 0] + (pz - a[:, 1]) * ab[:, 1]) / L2, 0, 1)
    cx, cz = a[:, 0] + t * ab[:, 0], a[:, 1] + t * ab[:, 1]
    return np.sqrt((px - cx) ** 2 + (pz - cz) ** 2).min(-1)


def _clash(a, b, s):
    """Two anchors whose lairs' write boxes would touch: nearer than lair_spacing along BOTH axes (Chebyshev)."""
    return abs(a[0] - b[0]) < s and abs(a[1] - b[1]) < s


def _improve(chosen, cand, s, reach=None, floor=0):
    """Local search on a greedy packing: while some den can be swapped for TWO candidates that clash with nothing else
    chosen nor with each other, swap it (a 1-for-2 exchange; each one adds a den, so it ends). With `reach`, a swap is
    taken only if the dens still cover `floor` usable columns or more. Deterministic: dens and candidates are tried in
    (z, x) order. Returns (chosen, swaps made)."""
    cell = max(1, s)
    chosen = sorted(chosen, key=lambda c: (c[1], c[0]))
    swaps = 0

    def bucket(pts):
        b = {}
        for p in pts:
            b.setdefault((p[0] // cell, p[1] // cell), []).append(p)
        return b

    cb = bucket(cand)

    def near(b, p):
        i, j = p[0] // cell, p[1] // cell
        return [q for di in (-1, 0, 1) for dj in (-1, 0, 1) for q in b.get((i + di, j + dj), [])]

    while True:
        chb = bucket(chosen)
        done = False
        for d in chosen:
            # the candidates that clash with d and with no other chosen den
            only = [c for c in near(cb, d) if _clash(c, d, s)
                    and not any(o is not d and _clash(c, o, s) for o in near(chb, c))]
            only.sort(key=lambda c: (c[1], c[0]))
            rest = [o for o in chosen if o is not d]
            pairs = [(a, b) for i, a in enumerate(only) for b in only[i + 1:] if not _clash(a, b, s)]
            if pairs and reach is not None:
                need = floor - reach.covered(rest)
                pairs = [p for p in pairs if need <= 0 or reach.pair_gain(p[0], p[1]) >= need]
            pair = pairs[0] if pairs else None
            if pair:
                chosen = sorted(rest + list(pair), key=lambda c: (c[1], c[0]))
                swaps += 1
                done = True
                break
        if not done:
            return chosen, swaps


class Reach:
    """The usable floor (inside the polygon, dry, no step over one block: the audit's floor) and which of it the chosen
    dens' ranges cover, as the keeper's own leash test: a column (x, z) is in a range when
    hypot(x + 0.5 - ax, z + 0.5 - az) <= leash."""

    def __init__(self, box, usable, leash):
        self.x0, self.z0, self.x1, self.z1 = box
        self.usable = usable
        self.L = leash
        self.cov = np.zeros(usable.shape, dtype=bool)
        r = int(math.ceil(leash)) + 1
        oz, ox = np.mgrid[-r:r + 1, -r:r + 1]
        self.r = r
        self.disc = np.hypot(ox + 0.5, oz + 0.5) <= leash

    def _win(self, x, z):
        i0, j0 = z - self.r - self.z0, x - self.r - self.x0
        n = 2 * self.r + 1
        a0, b0 = max(0, i0), max(0, j0)
        a1, b1 = min(self.usable.shape[0], i0 + n), min(self.usable.shape[1], j0 + n)
        if a1 <= a0 or b1 <= b0:
            return None
        return (slice(a0, a1), slice(b0, b1)), self.disc[a0 - i0:a1 - i0, b0 - j0:b1 - j0]

    def gain(self, x, z):
        w = self._win(x, z)
        if w is None:
            return 0
        sl, d = w
        return int((d & self.usable[sl] & ~self.cov[sl]).sum())

    def add(self, x, z):
        w = self._win(x, z)
        if w is not None:
            sl, d = w
            self.cov[sl] |= d

    def pair_gain(self, a, b):
        """What two more dens would add together to what is covered now, leaving it unchanged."""
        ga = self.gain(a[0], a[1])
        gb = self.gain(b[0], b[1])
        if abs(a[0] - b[0]) > 2 * self.r or abs(a[1] - b[1]) > 2 * self.r:
            return ga + gb
        keep = self.cov.copy()
        self.add(a[0], a[1])
        gb = self.gain(b[0], b[1])
        self.cov = keep
        return ga + gb

    def covered(self, pts):
        self.cov[:] = False
        for p in pts:
            self.add(p[0], p[1])
        return int((self.cov & self.usable).sum())


def pack(cand, lay, reach=None):
    """The candidate anchors packed, two dens never nearer than lair_spacing along BOTH axes at once (Chebyshev): a
    lair's write box is its anchor +- lair_radius and no two boxes may touch (tools/mega_dens_audit.py record rule), so
    2 x 21 + 1 = 43 is the closest two dens can stand.

    Greedy in a sweep order lays a near-lattice; each order is tried and improved by 1-for-2 swaps (_improve), and the
    one placing most dens wins (ties: the most usable floor in a range, then the first). With `reach` (the usable floor)
    the winner is then worked for REACH, the owner's 'everywhere': each den in turn is moved to the candidate that adds
    most usable floor to the ranges if that beats what it covers where it stands (_relocate), every candidate that still
    fits is added, and 1-for-2 swaps that lose no floor are taken, until a round changes nothing. Returns (chosen,
    notes)."""
    s = lay["lair_spacing"]
    orders = [("rows", lambda c: (c[1], c[0])), ("columns", lambda c: (c[0], c[1])),
              ("rows from the south", lambda c: (-c[1], c[0])), ("columns from the east", lambda c: (-c[0], c[1])),
              ("diagonal", lambda c: (c[0] + c[1], c[0])), ("anti-diagonal", lambda c: (c[0] - c[1], c[1])),
              ("hashed", lambda c: _h(c[0], c[1], lay["seed"]))]
    best, best_key, tried = None, None, []
    for name, key in orders:
        chosen = []
        for c in sorted(cand, key=key):
            if not any(_clash(c, o, s) for o in chosen):
                chosen.append(c)
        n0 = len(chosen)
        chosen, _sw = _improve(chosen, cand, s)
        cov = reach.covered(chosen) if reach is not None else 0
        tried.append("%s: %d -> %d dens, %d columns in a range" % (name, n0, len(chosen), cov))
        if best is None or (len(chosen), cov) > best_key:
            best, best_key = chosen, (len(chosen), cov)
    if reach is None:
        return best, tried
    chosen = sorted(best, key=lambda c: (c[1], c[0]))
    for rnd in range(lay.get("reach_rounds", 12)):
        cov0 = reach.covered(chosen)
        chosen, moves = _relocate(chosen, cand, s, reach, 2 * lay["leash"] - lay["min_overlap"])
        added = 0
        for c in sorted(cand, key=lambda c: (c[1], c[0])):
            if not any(_clash(c, o, s) for o in chosen):
                chosen.append(c)
                added += 1
        floor0 = reach.covered(chosen)
        chosen, swaps = _improve(chosen, cand, s, reach, floor0)
        cov1 = reach.covered(chosen)
        tried.append("reach round %d: %d moved, %d added, %d swapped: %d dens, %d -> %d columns in a range"
                     % (rnd + 1, moves, added, swaps, len(chosen), cov0, cov1))
        if not (moves or added or swaps):
            break
    return chosen, tried


def _relocate(chosen, cand, s, reach, near):
    """One pass of moves for reach: each den in (z, x) order is moved to the candidate (fitting beside every other den)
    whose range would add the most usable floor not in another range, when that is more than the den's own range adds
    where it stands, and only where the moved den and every den that was its neighbour still has a den within `near`
    (each range overlaps another by layout.min_overlap). Returns (chosen, moves)."""
    chosen = sorted(chosen, key=lambda c: (c[1], c[0]))
    moves = 0
    for i in range(len(chosen)):
        d = chosen[i]
        rest = chosen[:i] + chosen[i + 1:]
        reach.covered(rest)
        here = reach.gain(d[0], d[1])
        top, at = here, None
        mates = [o for o in rest if math.hypot(o[0] - d[0], o[1] - d[1]) <= near]
        for c in cand:
            if c is d or any(_clash(c, o, s) for o in rest):
                continue
            g = reach.gain(c[0], c[1])
            if g <= top or not any(math.hypot(o[0] - c[0], o[1] - c[1]) <= near for o in rest):
                continue
            after = rest + [c]
            if any(not any(q is not m and math.hypot(q[0] - m[0], q[1] - m[1]) <= near for q in after) for m in mates):
                continue
            top, at = g, c
        if at is not None:
            chosen[i] = at
            moves += 1
    return sorted(chosen, key=lambda c: (c[1], c[0])), moves


def drop_lonely(chosen, lay, cand=()):
    """The owner's rule that every Mega's range presses on a neighbour's (2026-10-04, 'overlapping ranges'): a den whose
    range overlaps no other den's by layout.min_overlap or more is first given a neighbour (the nearest candidate that
    fits beside every chosen den and overlaps it so), and only if none fits is it dropped, and again until no den is
    alone (dropping one can leave another alone). Returns (kept, dropped, added)."""
    near = 2 * lay["leash"] - lay["min_overlap"]
    s = lay["lair_spacing"]
    kept, dropped, added = list(chosen), [], []

    def alone(c):
        return not any(o is not c and math.hypot(c[0] - o[0], c[1] - o[1]) <= near for o in kept)
    while True:
        lone = sorted((c for c in kept if alone(c)), key=lambda c: (c[1], c[0]))
        if not lone:
            return kept, dropped, added
        c = lone[0]
        fit = sorted((q for q in cand if math.hypot(q[0] - c[0], q[1] - c[1]) <= near
                      and not any(_clash(q, o, s) for o in kept)),
                     key=lambda q: (math.hypot(q[0] - c[0], q[1] - c[1]), q[1], q[0]))
        if fit:
            kept.append(fit[0])
            added.append(fit[0])
        else:
            kept.remove(c)
            dropped.append(c)


def den_id(x, z):
    """A field den's id: its anchor's column, so it is unique (two anchors are 43 or more apart) and says nothing about
    its species. Every system keys the den by this: the keeper's tag cobblers.gm.<id> and its scores, its lair's
    function mega_dens/<id>, its borders <id>__<id>, its retirement."""
    return "gm_mf_%d_%d" % (x, z)


def sites(spec, source_root=None):
    """The field's dens, laid out on the canonical heightmap (never a world) by mega_field.layout's rules, and grouped
    into farms. Returns {"dens": [...], "farms": [...], "counts": {...}}: the farms are what data/gulch_mine.json
    `farms` holds, ready to paste."""
    mf = spec["mega_field"]
    lay = mf["layout"]
    poly = mf["polygon"]
    g = G.Ground(source_root)
    vr = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"][lay["road"]]
    x0, z0, x1, z1, m = columns(poly)
    step = lay["candidate_step"]
    xs = np.arange(x0 + step // 2, x1, step)
    zs = np.arange(z0 + step // 2, z1, step)
    cx, cz = np.meshgrid(xs, zs)
    cx, cz = cx.ravel(), cz.ravel()
    inside = point_in(poly, cx + 0.5, cz + 0.5)
    cx, cz = cx[inside], cz[inside]
    counts = {"candidates": int(len(cx))}
    # the edge measured from the anchor's corner AND its column's centre, the nearer of the two: a range is a disc round
    # the anchor (the leash line's `positioned <anchor>`), and on a 2-block candidate grid half a block decides it
    e = np.minimum(edge_dist(poly, cx + 0.5, cz + 0.5), edge_dist(poly, cx, cz))
    r = seg_dist(cx + 0.5, cz + 0.5, vr)
    # the lair's whole box inside the field (edge_clear), and the Mega's whole leash disc on the field's floor too
    ok = (e >= max(lay["edge_clear"], lay["leash"])) & (r >= lay["road_clear"])
    counts["after edge and road"] = int(ok.sum())
    gz = spec["zone"]["polygon"]
    # the gulch: a lair's write box keeps 32 off its zone, and a leashed Mega keeps megas.spawn_clear off it
    gclear = max(lay["gulch_clear"], lay["leash"] + spec["megas"]["spawn_clear"])
    ok &= edge_dist(gz, cx + 0.5, cz + 0.5) >= gclear
    # another system's wall, post or keep_clear disc: neither a lair's box nor the Mega's leash reaches it
    for _w, ox, oz, rr in others(spec):
        ok &= np.hypot(cx - ox, cz - oz) >= max(rr, lay["leash"] + 1) + (0 if _w == "keep_clear" else lay["lair_radius"])
    # a den's level is its Rift zone's badge cap plus its tier's offset (farm_tiers.field_why), so its anchor must
    # stand in a live zone's boxes (data/rift_zones.json): a den in no zone has no gate and no cap to be levelled by
    rz = json.loads((ROOT / "data" / "rift_zones.json").read_text(encoding="utf-8"))
    zoned = np.zeros(ok.shape, dtype=bool)
    for zz in rz["zones"].values():
        if str(zz.get("status", "")).startswith("SUPERSEDED"):
            continue
        for b in zz.get("boxes") or []:
            zoned |= (cx >= b[0]) & (cx <= b[2]) & (cz >= b[1]) & (cz <= b[3])
    ok &= zoned
    counts["after keep_clear"] = int(ok.sum())
    pr = lay["pad_radius"]
    cand = []
    for x, z, rd in zip(cx[ok], cz[ok], r[ok]):
        box = g.box(x - pr, z - pr, x + pr, z + pr)
        if int(box.max()) - int(box.min()) > lay["pad_relief"]:
            continue
        # the lair round it (data/mega_dens.json) writes at each column's own ground out to its write box: that ground
        # must stay inside the box's vertical span
        lr = lay["lair_radius"]
        # nor may it write inside the gulch's block box (gulch_mine.json grid, a rectangle wider than the gulch's zone)
        bx, bz = spec["grid"]["x"], spec["grid"]["z"]
        if x + lr >= bx[0] and x - lr <= bx[1] and z + lr >= bz[0] and z - lr <= bz[1]:
            continue
        gy = g(x, z)
        lair = g.box(x - lr, z - lr, x + lr, z + lr)
        if int(lair.min()) < gy - lay["lair_below"] or int(lair.max()) > gy + lay["lair_above"]:
            continue
        cand.append((int(x), int(z), float(rd)))
    counts["after pad"] = len(cand)
    (fx0, fz0, fx1, fz1), M, _H = floor(spec, source_root)
    reach = Reach((fx0, fz0, fx1, fz1), M["field"] & M["dry"] & M["walk"], lay["leash"])
    chosen, counts["packing"] = pack(cand, lay, reach)
    counts["packed"] = len(chosen)
    chosen, lonely, partners = drop_lonely(chosen, lay, cand)
    counts["dropped, no neighbour"] = [[c[0], c[1]] for c in lonely]
    counts["added as a neighbour"] = [[c[0], c[1]] for c in partners]
    counts["usable floor"] = int(reach.usable.sum())
    counts["usable floor in a range"] = reach.covered(chosen)
    # no Mega's range reaches another den's home (layout.why.leash): lair_spacing > leash makes it so; refused if not
    for i, a in enumerate(chosen):
        for b in chosen[i + 1:]:
            if math.hypot(a[0] - b[0], a[1] - b[1]) <= lay["leash"]:
                raise FieldError("dens (%d, %d) and (%d, %d): one's range reaches the other's home" % (a[0], a[1], b[0], b[1]))
    counts["dens"] = len(chosen)
    # tier and species, both banded by distance from the Cutters' town (the reward sink): the nearest dens are the
    # outer tier and take the roster's first species, the farthest the deeper tier and its last
    tx, tz = spec["town"]["square"]["centre"]
    dens = []
    for x, z, rd in sorted(chosen, key=lambda c: (math.hypot(c[0] - tx, c[1] - tz), c[1], c[0])):
        town = math.hypot(x - tx, z - tz)
        tier = lay["deeper_tier"] if town >= lay["deeper_from_town"] else lay["outer_tier"]
        dens.append({"x": x, "z": z, "y": g(x, z) + 1, "tier": tier, "road": round(rd), "town": round(town)})
    # the roster DEALT in bands by distance (layout.why.roster), nearest first: den k of n (by distance from the town)
    # takes species floor(k x species / n), so with more dens than species a species holds several neighbouring
    # territories and the order along the distance never goes back. A den is keyed by its own id (gm_mf_<x>_<z>, its
    # anchor's column), never by its species: the keeper's tag, its lair's function, its borders and its retirement
    # all name the den, so one species may hold any number of dens
    ros = lay["roster"]
    every = [sp for sp, _a in ros]
    if len(every) != len(set(every)):
        raise FieldError("a species appears twice in mega_field.layout.roster: the bands would split")
    if len(dens) < len(ros):
        raise FieldError("%d dens and %d species in mega_field.layout.roster: every species holds a den" % (len(dens), len(ros)))
    for k, d in enumerate(dens):
        d["species"], d["aspect"] = ros[k * len(ros) // len(dens)]
    dens.sort(key=lambda d: (d["z"], d["x"]))
    # farms: one per `farm_cell` square of the field the dens fall in, its approach box the dens' bbox plus
    # approach_margin (the old dens' 64 round each anchor) and anchor y - approach_below .. + approach_above
    # the bound every farm coordinate must sit in (data farms_grid, checked by tools/gulch_mine_audit.py): the field's
    # own extent, from its polygon and the ground under it, never from the dens chosen. An approach box is clipped to
    # it: the keeper drives while a player is in the field near a den, not on the plateau beyond its rim
    gr = g.box(x0, z0, x1, z1)[m]
    grid = {"x": [x0, x1], "y": [int(gr.min()) + 1 - lay["approach_below"], int(gr.max()) + 1 + lay["approach_above"]],
            "z": [z0, z1]}
    fc = lay["farm_cell"]
    groups = {}
    for d in dens:
        groups.setdefault(((d["x"] - x0) // fc, (d["z"] - z0) // fc), []).append(d)
    farms = []
    for (i, j), ds in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        fid = "field_%d_%d" % (i, j)
        tiers = sorted({d["tier"] for d in ds})
        mg = lay["approach_margin"]
        # y: the anchors' less approach_below and plus approach_above, widened to hold the ground of every den's whole
        # leash disc (a player fighting the Mega at its leash's edge keeps the keeper running), clipped to farms_grid
        L = lay["leash"]
        disc = [g.box(d["x"] - L, d["z"] - L, d["x"] + L, d["z"] + L) for d in ds]
        ap = [max(grid["x"][0], min(d["x"] for d in ds) - mg),
              max(grid["y"][0], min(min(d["y"] for d in ds) - lay["approach_below"], min(int(b.min()) for b in disc) - 2)),
              max(grid["z"][0], min(d["z"] for d in ds) - mg), min(grid["x"][1], max(d["x"] for d in ds) + mg),
              min(grid["y"][1], max(max(d["y"] for d in ds) + lay["approach_above"], max(int(b.max()) for b in disc) + 4)),
              min(grid["z"][1], max(d["z"] for d in ds) + mg)]
        out = []
        for d in ds:
            out.append({"id": den_id(d["x"], d["z"]), "species": d["species"], "aspect": d["aspect"],
                        "anchor": [d["x"], d["y"], d["z"]], "leash": L, "tier": d["tier"],
                        "road_blocks": d["road"], "town_blocks": d["town"]})
        farms.append({"id": fid, "name": "the Mega field, cell %d %d" % (i, j), "tier": tiers[-1] if len(tiers) == 1 else
                      lay["outer_tier"], "approach": ap, "dens": out})
    counts["farms"] = len(farms)
    counts["by tier"] = {t: sum(1 for d in dens if d["tier"] == t) for t in (lay["outer_tier"], lay["deeper_tier"])}
    return {"counts": counts, "farms_grid": grid, "farms": farms}


if __name__ == "__main__":
    raise SystemExit(main())
