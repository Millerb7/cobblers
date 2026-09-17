#!/usr/bin/env python
"""Landmark trees: a handful of giant, hand-sited trees that are discovery sites, not foliage.

designs()  the giants as structure builders, one per landmark (seeded, so they regenerate identically).
           tools/foliage_objects.py generate writes them to kits/structures/foliage/.
check      for each site in data/foliage.json landmark_trees, cast sightlines to the crown from the points it
           is meant to draw people from (critical-path legs, a clearing edge, the sea), over terrain plus the
           planned canopy (build/paint/canopy.npz from tools/paint_maps.py), and report what can see it. Legs are
           the data/routes.json polylines unless --legs names another file of {"legs": [{from, to, polyline}]}.
candidates rank sites for a kind (route, clearing, ridge, headland) by how much of the target they are
           seen from. A human picks: the chosen sites are written into data/foliage.json by hand.

  python tools/landmark_trees.py check --source-root <root>
  python tools/landmark_trees.py candidates --kind ridge --subregions wedge_north --legs gym8_town->league
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

import structure_nbt as S

ROOT = Path(__file__).resolve().parent.parent


def _rng(name):
    return np.random.default_rng(int(hashlib.sha256(name.encode()).hexdigest()[:12], 16))


def _leaves(kind):
    return ("minecraft:%s_leaves" % kind, {"distance": "1", "persistent": "true", "waterlogged": "false"})


def _log(kind, axis="y"):
    return ("minecraft:%s_log" % kind, {"axis": axis})


def _ball(b, cx, cy, cz, rx, ry, rz, block, rng, ragged=0.25):
    for dx in range(-int(rx) - 1, int(rx) + 2):
        for dy in range(-int(ry) - 1, int(ry) + 2):
            for dz in range(-int(rz) - 1, int(rz) + 2):
                e = (dx / rx) ** 2 + (dy / ry) ** 2 + (dz / rz) ** 2
                if e > 1.0 or (e > 0.7 and rng.random() < ragged):
                    continue
                b.setdefault(round(cx + dx), round(cy + dy), round(cz + dz), *block)


def _limb(b, a, c, r, kind):
    """A thick branch from a to c, radius r (blocks), logs oriented along the dominant axis."""
    ax, ay, az = a
    cx, cy, cz = c
    d = math.dist(a, c)
    n = max(2, int(d * 1.5))
    dx, dy, dz = cx - ax, cy - ay, cz - az
    axis = "y" if abs(dy) >= max(abs(dx), abs(dz)) else ("x" if abs(dx) >= abs(dz) else "z")
    for i in range(n + 1):
        t = i / n
        px, py, pz = ax + dx * t, ay + dy * t, az + dz * t
        rr = r * (1 - 0.45 * t)
        ri = int(math.ceil(rr))
        for ox in range(-ri, ri + 1):
            for oy in range(-ri, ri + 1):
                for oz in range(-ri, ri + 1):
                    if ox * ox + oy * oy + oz * oz <= rr * rr + 0.25:
                        b.set(round(px + ox), round(py + oy), round(pz + oz), *_log(kind, axis))


def _roots(b, cx, cz, radius, n, kind, rng, top=3):
    for k in range(n):
        ang = 2 * math.pi * (k + rng.uniform(-0.2, 0.2)) / n
        L = radius * rng.uniform(0.7, 1.1)
        for i in range(int(L)):
            t = i / max(L, 1)
            h = int(round(top * (1 - t)))
            x, z = round(cx + math.cos(ang) * i), round(cz + math.sin(ang) * i)
            for y in range(-1, h + 1):
                b.set(x, y, z, *_log(kind))


def great_oak(name="landmark_great_oak"):
    """A broad old oak: 4x4 trunk, buttress roots, five limbs carrying leaf clouds, crown about 36 across."""
    rng = _rng(name)
    b = S.Builder()
    kind = "oak"
    for y in range(-2, 16):
        for x in range(4):
            for z in range(4):
                if y > 11 and (x in (0, 3) and z in (0, 3)):
                    continue
                b.set(x, y, z, *_log(kind))
    _roots(b, 1.5, 1.5, 7, 7, kind, rng)
    tips = []
    for k in range(5):
        ang = 2 * math.pi * k / 5 + rng.uniform(-0.3, 0.3)
        reach = rng.uniform(9, 13)
        top = rng.uniform(24, 33)
        tip = (1.5 + math.cos(ang) * reach, top, 1.5 + math.sin(ang) * reach)
        _limb(b, (1.5, 13, 1.5), tip, 1.4, kind)
        tips.append(tip)
        for j in range(3):
            a2 = ang + rng.uniform(-0.9, 0.9)
            sub = (tip[0] + math.cos(a2) * rng.uniform(3, 6), tip[1] + rng.uniform(-2, 4), tip[2] + math.sin(a2) * rng.uniform(3, 6))
            _limb(b, tip, sub, 0.6, kind)
            _ball(b, *sub, rng.uniform(3.5, 5), rng.uniform(2.2, 3), rng.uniform(3.5, 5), _leaves(kind), rng)
        _ball(b, *tip, rng.uniform(5, 6.5), rng.uniform(3, 4), rng.uniform(5, 6.5), _leaves(kind), rng)
    _ball(b, 1.5, 34, 1.5, 7, 4, 7, _leaves(kind), rng)
    return b


def sentinel_spruce(name="landmark_sentinel_spruce"):
    """A lone giant spruce: 3x3 trunk to 70 blocks, bare for the first 22, then a narrow layered spire."""
    rng = _rng(name)
    b = S.Builder()
    kind = "spruce"
    H = 72
    for y in range(-2, H - 2):
        w = 3 if y < H * 0.7 else 2
        for x in range(w):
            for z in range(w):
                b.set(x, y, z, *_log(kind))
    _roots(b, 1, 1, 5, 6, kind, rng, top=2)
    base = 22
    for y in range(H + 2, base - 1, -1):
        f = (H + 2 - y) / (H + 2 - base)
        r = 1.5 + 10.5 * f ** 0.9
        step = (H + 2 - y) % 4
        rr = r if step == 0 else r * (0.55 if step == 2 else 0.4)
        for dx in range(-int(rr) - 1, int(rr) + 2):
            for dz in range(-int(rr) - 1, int(rr) + 2):
                d = math.hypot(dx - 1, dz - 1)
                if d <= rr and not (d > rr - 1.3 and rng.random() < 0.35):
                    b.setdefault(dx, y, dz, *_leaves(kind))
                    if step == 0 and d > rr - 1.5 and rng.random() < 0.5:
                        b.setdefault(dx, y - 1, dz, *_leaves(kind))
        if step == 0 and y < H - 8:
            for ang in rng.uniform(0, 2 * math.pi, 4):
                L = r - 2
                _limb(b, (1, y - 1, 1), (1 + math.cos(ang) * L, y - 2, 1 + math.sin(ang) * L), 0.5, kind)
    return b


def patriarch_dark_oak(name="landmark_patriarch_dark_oak"):
    """A squat, enormous dark oak on a ridge: 5x5 trunk, limbs reaching sideways, a flat dense crown."""
    rng = _rng(name)
    b = S.Builder()
    kind = "dark_oak"
    for y in range(-2, 14):
        for x in range(5):
            for z in range(5):
                if (x in (0, 4) and z in (0, 4)) and y > 3:
                    continue
                b.set(x, y, z, *_log(kind))
    _roots(b, 2, 2, 8, 8, kind, rng, top=4)
    for k in range(7):
        ang = 2 * math.pi * k / 7 + rng.uniform(-0.25, 0.25)
        reach = rng.uniform(10, 15)
        tip = (2 + math.cos(ang) * reach, rng.uniform(18, 24), 2 + math.sin(ang) * reach)
        _limb(b, (2, 11, 2), tip, 1.3, kind)
        _ball(b, *tip, rng.uniform(5, 7), rng.uniform(2.5, 3.5), rng.uniform(5, 7), _leaves(kind), rng, ragged=0.15)
    _ball(b, 2, 25, 2, 12, 4.5, 12, _leaves(kind), rng, ragged=0.15)
    return b


def kapok(name="landmark_kapok"):
    """A jungle emergent: 3x3 trunk with plank-buttress fins, bare to 44, an umbrella crown 40 across."""
    rng = _rng(name)
    b = S.Builder()
    kind = "jungle"
    H = 50
    for y in range(-2, H):
        for x in range(3):
            for z in range(3):
                b.set(x, y, z, *_log(kind))
    for k in range(6):
        ang = 2 * math.pi * k / 6
        for i in range(1, 8):
            h = int(9 * (1 - i / 8))
            x, z = round(1 + math.cos(ang) * (i + 1)), round(1 + math.sin(ang) * (i + 1))
            for y in range(-2, h + 1):
                b.set(x, y, z, *_log(kind))
    for k in range(8):
        ang = 2 * math.pi * k / 8 + rng.uniform(-0.2, 0.2)
        reach = rng.uniform(12, 17)
        tip = (1 + math.cos(ang) * reach, H + rng.uniform(-1, 3), 1 + math.sin(ang) * reach)
        _limb(b, (1, H - 6, 1), tip, 0.9, kind)
        _ball(b, *tip, rng.uniform(5, 7), 2.2, rng.uniform(5, 7), _leaves(kind), rng, ragged=0.2)
    _ball(b, 1, H + 1, 1, 10, 3, 10, _leaves(kind), rng, ragged=0.2)
    # vines on the trunk faces (each vine names the face it clings to)
    for y in range(8, H - 6, 3):
        for (x, z, face) in ((-1, 1, "east"), (3, 1, "west"), (1, -1, "south"), (1, 3, "north")):
            if rng.random() < 0.6:
                b.setdefault(x, y, z, "minecraft:vine", {face: "true"})
    return b


def cherry_elder(name="landmark_cherry_elder"):
    """An old cherry in a vale: a leaning 3x3 trunk, lobed pink crown about 34 across, petals under it."""
    rng = _rng(name)
    b = S.Builder()
    kind = "cherry"
    for y in range(-2, 12):
        lean = int(y * 0.25)
        for x in range(3):
            for z in range(3):
                b.set(x + lean, y, z, *_log(kind))
    _roots(b, 1, 1, 5, 5, kind, rng, top=2)
    for k in range(6):
        ang = 2 * math.pi * k / 6 + rng.uniform(-0.3, 0.3)
        reach = rng.uniform(8, 13)
        tip = (4 + math.cos(ang) * reach, rng.uniform(16, 23), 1 + math.sin(ang) * reach)
        _limb(b, (4, 10, 1), tip, 0.9, kind)
        _ball(b, *tip, rng.uniform(4.5, 6), rng.uniform(2.5, 3.5), rng.uniform(4.5, 6), _leaves(kind), rng)
        for i in range(12):
            px, pz = round(tip[0] + rng.uniform(-6, 6)), round(tip[2] + rng.uniform(-6, 6))
            b.setdefault(px, 0, pz, "minecraft:pink_petals",
                         {"flower_amount": str(int(rng.integers(1, 5))), "facing": ["north", "south", "east", "west"][int(rng.integers(0, 4))]})
    _ball(b, 4, 22, 1, 7, 3.5, 7, _leaves(kind), rng)
    return b


def weeping_elder(name="landmark_weeping_elder"):
    """A lake-island giant: 3x3 trunk, limbs to a broad dome about 36 across, and curtains of leaves hanging
    from the dome's rim almost to the ground (leaves, not vines: vine chains need a solid face to hang on)."""
    rng = _rng(name)
    b = S.Builder()
    kind = "oak"
    for y in range(-2, 18):
        for x in range(3):
            for z in range(3):
                b.set(x, y, z, *_log(kind))
    _roots(b, 1, 1, 6, 6, kind, rng, top=2)
    for k in range(6):
        ang = 2 * math.pi * k / 6 + rng.uniform(-0.3, 0.3)
        reach = rng.uniform(8, 12)
        tip = (1 + math.cos(ang) * reach, rng.uniform(24, 29), 1 + math.sin(ang) * reach)
        _limb(b, (1, 15, 1), tip, 1.0, kind)
    R, top = 17.0, 34
    for dx in range(-18, 20):
        for dz in range(-18, 20):
            d = math.hypot(dx - 1, dz - 1)
            if d > R:
                continue
            crown = top - int((d / R) ** 2 * 10)
            thick = 3 if d < R - 3 else 2
            for y in range(crown - thick, crown + 1):
                if d > R - 1.2 and rng.random() < 0.3:
                    continue
                b.setdefault(dx, y, dz, *_leaves(kind))
            if d > R - 4 and rng.random() < 0.55:
                length = int(rng.integers(6, max(7, crown - thick - 4)))
                for y in range(crown - thick - 1, max(3, crown - thick - 1 - length), -1):
                    b.setdefault(dx, y, dz, *_leaves(kind))
    return b


def designs():
    return {
        "landmark_weeping_elder": ("landmark_weeping_elder", weeping_elder()),
        "landmark_great_oak": ("landmark_great_oak", great_oak()),
        "landmark_sentinel_spruce": ("landmark_sentinel_spruce", sentinel_spruce()),
        "landmark_patriarch_dark_oak": ("landmark_patriarch_dark_oak", patriarch_dark_oak()),
        "landmark_kapok": ("landmark_kapok", kapok()),
        "landmark_cherry_elder": ("landmark_cherry_elder", cherry_elder()),
    }


# ------------------------------------------------------------------ sightlines


def _surface(heights, canopy_path):
    if canopy_path and Path(canopy_path).exists():
        c = np.load(canopy_path)["canopy"]
        f = heights.shape[0] // c.shape[0]
        up = np.repeat(np.repeat(c, f, axis=0), f, axis=1)[:heights.shape[0], :heights.shape[1]]
        return np.maximum(heights, up.astype(np.float32))
    return heights


def visibility(heights, surface, site, height, observers, eye=1.6, step=2.0):
    import sightlines as SL
    target = {"x": site[0], "z": site[1]}
    seen = []
    for (ox, oz) in observers:
        # the target is the crown top less a few blocks, so a ray grazing the tip does not count as seeing the tree;
        # 3 blocks at the observer end are excluded so standing under one's own tree does not blind the check
        r = SL.cast(heights, (ox, oz), eye, target, height - 3, step=step, margin=3.0, surface=surface)
        seen.append((r["visible"], r["distance"]))
    vis = [d for v, d in seen if v]
    return {"observers": len(seen), "visible": len(vis), "share": round(len(vis) / max(len(seen), 1), 3),
            "nearest_visible": round(min(vis)) if vis else None, "farthest_visible": round(max(vis)) if vis else None}


def leg_points(legs_doc, names, spacing=48):
    pts = []
    for leg in legs_doc["legs"]:
        if "%s->%s" % (leg["from"], leg["to"]) not in names or not leg.get("polyline"):
            continue
        p = np.array(leg["polyline"], float)
        seg = np.hypot(*np.diff(p, axis=0).T)
        cum = np.concatenate([[0], np.cumsum(seg)])
        for d in np.arange(0, cum[-1], spacing):
            i = min(np.searchsorted(cum, d, side="right") - 1, len(seg) - 1)
            t = (d - cum[i]) / max(seg[i], 1e-6)
            pts.append((float(p[i, 0] + (p[i + 1, 0] - p[i, 0]) * t), float(p[i, 1] + (p[i + 1, 1] - p[i, 1]) * t)))
    return pts


def legs_from_routes(routes_doc):
    """data/routes.json as a legs document: one {from, to, polyline [[x, z], ...]} per critical route."""
    return {"legs": [{"from": r["from_town"], "to": r["to_town"],
                      "polyline": [[p["x"], p["z"]] for p in r["corridor"]["polyline"]]} for r in routes_doc["routes"]]}


def ring_points(site, radius, n=24):
    return [(site[0] + math.cos(2 * math.pi * k / n) * radius, site[1] + math.sin(2 * math.pi * k / n) * radius) for k in range(n)]


def observers_for(spec, legs_doc):
    obs = []
    for o in spec["seen_from"]:
        if o["kind"] == "legs":
            obs.append((o, leg_points(legs_doc, set(o["legs"]), o.get("spacing", 48))))
        elif o["kind"] == "ring":
            obs.append((o, ring_points(spec["site"], o["radius"], o.get("n", 24))))
        elif o["kind"] == "points":
            obs.append((o, [tuple(p) for p in o["points"]]))
    return obs


def check(foliage_doc, heights, surface, legs_doc, library):
    heights_by_obj = {r["name"]: r["height"] for r in library["objects"]}
    rows = []
    for spec in foliage_doc.get("landmark_trees") or []:
        h = heights_by_obj.get(spec["object"])
        x, z = spec["site"]
        # the tree's own crown and glade are in the canopy surface; they must not hide the tree
        g = int(spec.get("glade_radius", 24))
        win = (slice(max(0, z - g), z + g + 1), slice(max(0, x - g), x + g + 1))
        saved = surface[win].copy()
        surface[win] = heights[win]
        try:
            row = _check_one(spec, h, x, z, heights, surface, legs_doc)
        finally:
            surface[win] = saved
        rows.append(row)
    return rows


def _check_one(spec, h, x, z, heights, surface, legs_doc):
    row = {"id": spec["id"], "object": spec["object"], "site": spec["site"], "tree_height": h,
           "ground_y": round(float(heights[z, x]), 1), "crown_top_y": round(float(heights[z, x]) + (h or 0), 1),
           "seen_from": []}
    for o, pts in observers_for(spec, legs_doc):
        v = visibility(heights, surface, (x, z), h or 0, pts)
        row["seen_from"].append(dict({k: o[k] for k in o if k != "points"}, **v))
    return row


def candidates(heights, surface, legs_doc, masks, kind, legs, height, dist_range, grid=32, top=8):
    """Rank sites inside the mask by the share of leg points that see a crown of the given height."""
    pts = leg_points(legs_doc, set(legs), 64)
    P = np.array(pts)
    zs, xs = np.nonzero(masks[::grid, ::grid])
    cand = []
    for zi, xi in zip(zs, xs):
        x, z = int(xi * grid), int(zi * grid)
        d = np.hypot(P[:, 0] - x, P[:, 1] - z).min() if len(P) else 1e9
        if not (dist_range[0] <= d <= dist_range[1]):
            continue
        local = heights[max(0, z - 150):z + 150:8, max(0, x - 150):x + 150:8]
        prominence = float(heights[z, x] - local.mean())
        cand.append((x, z, d, prominence))
    if kind in ("ridge", "headland"):
        cand.sort(key=lambda c: -c[3])
        cand = cand[:200]
    rng = np.random.default_rng(1)
    if len(cand) > 200:
        cand = [cand[i] for i in rng.choice(len(cand), 200, replace=False)]
    scored = []
    for x, z, d, prom in cand:
        v = visibility(heights, surface, (x, z), height, pts, step=3.0)
        scored.append({"site": [x, z], "distance_to_leg": round(d), "prominence": round(prom, 1), **v})
    scored.sort(key=lambda r: (-r["share"], -(r["farthest_visible"] or 0)))
    return scored[:top]


def main(argv=None):
    import terrain as T
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "candidates"):
        s = sub.add_parser(name)
        T.add_common_args(s)
        s.add_argument("--foliage", default=str(ROOT / "data" / "foliage.json"))
        s.add_argument("--legs", default=None, help="legs file; default: the data/routes.json polylines")
        s.add_argument("--canopy", default=str(ROOT / "build" / "paint" / "canopy.npz"))
        s.add_argument("--library", default=str(ROOT / "kits" / "structures" / "foliage" / "library.json"))
        if name == "candidates":
            s.add_argument("--kind", required=True, choices=["route", "clearing", "ridge", "headland"])
            s.add_argument("--subregions", nargs="+", required=True)
            s.add_argument("--leg", nargs="+", required=True, dest="leg_names")
            s.add_argument("--height", type=float, default=40)
            s.add_argument("--min-dist", type=float, default=100)
            s.add_argument("--max-dist", type=float, default=600)
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    surface = _surface(heights, a.canopy)
    if a.legs:
        legs_doc = json.loads(Path(a.legs).read_text(encoding="utf-8"))
    else:
        legs_doc = legs_from_routes(json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8")))
    if a.cmd == "check":
        doc = json.loads(Path(a.foliage).read_text(encoding="utf-8"))
        lib = json.loads(Path(a.library).read_text(encoding="utf-8"))
        rows = check(doc, heights, surface, legs_doc, lib)
        out = a.out or str(ROOT / "derived" / "foliage" / "landmark_sightlines.json")
        T.write_json(out, {"generator": "tools/landmark_trees.py check", "canopy": a.canopy if Path(a.canopy).exists() else None,
                           "legs": a.legs or "data/routes.json",
                           "provenance": T.provenance(world, Path(a.world)), "landmarks": rows})
        print(json.dumps(rows, indent=1))
    else:
        from PIL import Image, ImageDraw
        regions = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
        im = Image.new("L", heights.shape[::-1], 0)
        d = ImageDraw.Draw(im)
        for s in regions["subregions"]:
            if s["id"] in a.subregions:
                for ring in s["polygons"]:
                    d.polygon([tuple(q) for q in ring], fill=1)
        mask = (np.asarray(im) > 0) & (heights > T.sea_level(world) + 2) & (T.slope_degrees(heights) < 14)
        rows = candidates(heights, surface, legs_doc, mask, a.kind, a.leg_names, a.height, (a.min_dist, a.max_dist))
        print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
