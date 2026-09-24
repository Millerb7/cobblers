"""The Rift's whole perimeter as stations: position, inward normal, arc length, and the profile at each.

The prototype sculpted one straight stretch between two points (tools/rift_fracture.py's Frame). The full Rift is a
closed polygon — `the_rift` in data/regions.json, 28 points, 2.221 km2 — so the rim has to be walked rather than
parameterised by a line. This module densifies that boundary to one station per block of arc length and gives each
station the same things a stretch station had: where the lip is, how far down the floor is, which way is out.

Ground comes from the canonical heightmap (tools/ground.py), never from a world.

    python tools/rift_perimeter.py --source-root <root>          # measure and report
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
WORLD_READS = ()          # heightmap and data only


class PerimeterError(Exception):
    pass


def rift_polygon():
    """The Rift's boundary, as the region data draws it."""
    doc = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    regions = doc["regions"] if isinstance(doc, dict) and "regions" in doc else doc
    if isinstance(regions, dict):
        regions = list(regions.values())
    r = next(x for x in regions if x["id"] == "the_rift")
    if len(r["polygons"]) != 1:
        raise PerimeterError("the Rift is drawn as %d polygons; the rim walk assumes one" % len(r["polygons"]))
    return [(float(x), float(z)) for x, z in r["polygons"][0]]


def densify(poly, step=1.0):
    """The closed boundary at one point per `step` blocks, with the arc length of each."""
    pts, s = [], 0.0
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]
        bx, bz = poly[(i + 1) % n]
        seg = math.hypot(bx - ax, bz - az)
        k = max(1, int(round(seg / step)))
        for j in range(k):
            f = j / k
            pts.append((ax + (bx - ax) * f, az + (bz - az) * f, s + seg * f, i))
        s += seg
    return pts, s


def normals(pts, total, smooth=24):
    """The inward unit normal at each station, from a tangent averaged over `smooth` blocks either way so a polygon
    corner does not swing the rim through a right angle."""
    n = len(pts)
    out = []
    cx = sum(p[0] for p in pts) / n
    cz = sum(p[1] for p in pts) / n
    for i in range(n):
        ax, az, _, _ = pts[(i - smooth) % n]
        bx, bz, _, _ = pts[(i + smooth) % n]
        tx, tz = bx - ax, bz - az
        L = math.hypot(tx, tz) or 1.0
        tx, tz = tx / L, tz / L
        nx, nz = -tz, tx
        px, pz, _, _ = pts[i]
        if (cx - px) * nx + (cz - pz) * nz < 0:      # point it inwards, towards the Rift's middle
            nx, nz = -nx, -nz
        out.append((nx, nz))
    return out


def profile(g, pts, nrm, inward=200, outward=90):
    """At each station: the lip's ground, the plateau behind it, and how far the floor is below.

    `floor` is the lowest ground within `inward` blocks along the inward normal, which is what the scarp has to
    reach; `plateau` is the mean ground just outside, which is what the rim is built on.
    """
    def at(x, z):
        try:
            return g(x, z)
        except (IndexError, ValueError):
            return None

    sts = []
    for (px, pz, s, seg), (nx, nz) in zip(pts, nrm):
        gy = at(px, pz)
        ins = [v for v in (at(px + nx * d, pz + nz * d) for d in range(4, inward, 4)) if v is not None]
        outs = [v for v in (at(px - nx * d, pz - nz * d) for d in range(2, outward, 4)) if v is not None]
        if gy is None or not ins or not outs:
            continue
        floor = min(ins)
        sts.append({"x": px, "z": pz, "s": s, "seg": seg, "nx": nx, "nz": nz,
                    "lip_y": gy, "plateau": sum(outs) / len(outs), "floor": floor, "depth": gy - floor})
    return sts


def load_ground(source_root):
    import ground
    return ground.Ground(source_root) if hasattr(ground, "Ground") else ground


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    g = G.load(a.source_root) if hasattr(G, "load") else G
    poly = rift_polygon()
    pts, total = densify(poly)
    nrm = normals(pts, total)
    sts = profile(g, pts, nrm)
    print("the Rift's boundary: %d corners, %.0f blocks around, %d stations" % (len(poly), total, len(sts)))
    if not sts:
        raise PerimeterError("no station has ground on both sides: the polygon may not match the heightmap")
    dep = sorted(s["depth"] for s in sts)
    lip = sorted(s["lip_y"] for s in sts)
    pl = sorted(s["plateau"] for s in sts)

    def pct(v, p):
        return v[int(len(v) * p)]
    print("  lip ground      y%.0f .. y%.0f (median y%.0f)" % (lip[0], lip[-1], pct(lip, .5)))
    print("  plateau behind  y%.0f .. y%.0f (median y%.0f)" % (pl[0], pl[-1], pct(pl, .5)))
    print("  depth to floor  %.0f .. %.0f (median %.0f, p10 %.0f)" % (dep[0], dep[-1], pct(dep, .5), pct(dep, .1)))
    shallow = sum(1 for d in dep if d < 20)
    print("  stations under 20 deep: %d (%.0f%%) -- there the scarp has little to cut" % (
        shallow, 100.0 * shallow / len(dep)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
