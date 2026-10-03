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
    p.add_argument("mode", choices=("trace", "map", "sites", "dress", "check"))
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
            rec["write_box"] = [ax - 27, gy - 8, az - 27, ax + 27, gy + 14, az + 27]
            out.append(rec)
    return out


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
    e = edge_dist(poly, cx + 0.5, cz + 0.5)
    r = seg_dist(cx + 0.5, cz + 0.5, vr)
    ok = (e >= lay["edge_clear"]) & (r >= lay["road_clear"])
    counts["after edge and road"] = int(ok.sum())
    gz = spec["zone"]["polygon"]
    ok &= edge_dist(gz, cx + 0.5, cz + 0.5) >= lay["gulch_clear"]
    for kc in lay["keep_clear"]:
        ok &= np.hypot(cx - kc["at"][0], cz - kc["at"][1]) >= kc["r"]
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
    cand.sort(key=lambda c: _h(c[0], c[1], lay["seed"]))
    chosen = []
    for x, z, rd in cand:
        if all((x - a) ** 2 + (z - b) ** 2 >= lay["spacing"] ** 2 for a, b, _r in chosen):
            chosen.append((x, z, rd))
    counts["dens"] = len(chosen)
    # tier by distance from the road: the further from Victory Road's walked line, the deeper
    dens = []
    for x, z, rd in sorted(chosen, key=lambda c: (c[1], c[0])):
        tier = lay["deeper_tier"] if rd >= lay["deeper_from_road"] else lay["outer_tier"]
        dens.append({"x": x, "z": z, "y": g(x, z) + 1, "tier": tier, "road": round(rd)})
    # species: each tier's roster dealt in turn along the dens sorted north to south, so neighbours differ
    # ONE den per species: tools/mega_dens.py names a lair's function after its species (mega_dens/<species>), so two
    # dens of one species would write one file; a tier with more dens than roster entries is refused, not wrapped
    deal = {t: 0 for t in lay["roster"]}
    for d in dens:
        ros = lay["roster"][d["tier"]]
        if deal[d["tier"]] >= len(ros):
            raise FieldError("%s has more dens than species in mega_field.layout.roster.%s (%d): one den per species"
                             % (d["tier"], d["tier"], len(ros)))
        d["species"], d["aspect"] = ros[deal[d["tier"]]]
        deal[d["tier"]] += 1
    every = [sp for t in lay["roster"] for sp, _a in lay["roster"][t]]
    if len(every) != len(set(every)):
        raise FieldError("a species appears twice in mega_field.layout.roster: one den per species")
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
        ap = [max(grid["x"][0], min(d["x"] for d in ds) - mg), min(d["y"] for d in ds) - lay["approach_below"],
              max(grid["z"][0], min(d["z"] for d in ds) - mg), min(grid["x"][1], max(d["x"] for d in ds) + mg),
              max(d["y"] for d in ds) + lay["approach_above"], min(grid["z"][1], max(d["z"] for d in ds) + mg)]
        out = []
        for k, d in enumerate(ds):
            out.append({"id": "gm_%s_%d" % (fid, k + 1), "species": d["species"], "aspect": d["aspect"],
                        "anchor": [d["x"], d["y"], d["z"]], "leash": lay["leash"], "tier": d["tier"],
                        "road_blocks": d["road"]})
        farms.append({"id": fid, "name": "the Mega field, cell %d %d" % (i, j), "tier": tiers[-1] if len(tiers) == 1 else
                      lay["outer_tier"], "approach": ap, "dens": out})
    counts["farms"] = len(farms)
    counts["by tier"] = {t: sum(1 for d in dens if d["tier"] == t) for t in lay["roster"]}
    return {"counts": counts, "farms_grid": grid, "farms": farms}


if __name__ == "__main__":
    raise SystemExit(main())
