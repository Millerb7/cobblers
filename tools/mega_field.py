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
    run = []
    for i in range((kW - kA) % T + 1):
        k = (kA + i) % T
        x, z = ring[k]
        # the normals point into the basin (gulch_mine.py trace): minus is outward
        run.append([round(x - nrm[k][0] * ft["rim_outset"], 1), round(z - nrm[k][1] * ft["rim_outset"], 1)])
    poly = GM.simplify(run, ft["tolerance"])
    zp = spec["zone"]["polygon"]
    poly = poly + [list(zp[0]), list(zp[-1])]
    return {"ring_from": [kA, ring[kA]], "ring_cut": [kW, ring[kW]], "ring_to": [kE, ring[kE]],
            "cut_blocks": round(math.dist(ring[kW], ring[kE]), 1), "polygon": poly}


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
    d.text((6, img.size[1] - 30), "red: the Mega field   blue: the gulch zone   yellow: owner's marks   orange: dens   grey x: retired dens",
           fill=(255, 255, 255))
    img.save(out)
    return img.size


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("trace", "map", "sites"))
    p.add_argument("--source-root")
    p.add_argument("--out")
    a = p.parse_args(argv)
    spec = load()
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
    return 1


def sites(spec, source_root=None):
    raise FieldError("sites: not written yet")


if __name__ == "__main__":
    raise SystemExit(main())
