#!/usr/bin/env python
"""Route the critical path legs as candidate polylines, and report how much of each leg crosses each sub-region.

Legs run between consecutive critical settlements in data/towns.json (route order), terrain-weighted A* on
8-block cells (tools/route_path.py), avoiding open sea. The League leg is Victory Road as towns.json describes
it: up the Rift's south-west arm and trunk (data/landmarks.json rift axes). The output is derived data for siting checks
(foliage, landmark trees, sightlines), not a road: a human decides the road.

  python tools/critical_legs.py --source-root <root> --out derived/routes/critical_legs.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import terrain as T
import route_path as RP

CELL = 8
SLOPE_WEIGHT = 0.5      # one block of climb costs half an 8-block step


def coarse(heights, cell=CELL):
    n = heights.shape[0] // cell
    return heights[:n * cell, :n * cell].reshape(n, cell, n, cell).mean(axis=(1, 3))


def victory_road(a, b, landmarks_doc):
    """Giovanni's town to the Rift's south-west arm, up the arm to the fork, up the trunk to the apex, to the League."""
    rift = next((l for l in landmarks_doc["landmarks"] if l["id"] == "rift"), None)
    if not rift:
        return None
    ax = {x["id"]: x["polyline"] for x in rift.get("axes") or []}
    if "south_west_arm" not in ax or "trunk" not in ax:
        return None
    arm = list(reversed(ax["south_west_arm"]))          # foot of the arm first, fork last
    trunk = list(reversed(ax["trunk"]))                  # fork first, apex last
    return [[a["centre"]["x"], a["centre"]["z"]]] + arm + trunk[1:] + [[b["centre"]["x"], b["centre"]["z"]]]


def legs(towns_doc, heights, sea_level, landmarks_doc=None):
    hc = coarse(heights)
    passable = hc > sea_level - 0.5
    crit = sorted([t for t in towns_doc["towns"] if t.get("tier") == "critical"], key=lambda t: t["order"])
    out = []
    for a, b in zip(crit, crit[1:]):
        if b.get("role") == "league" and landmarks_doc:
            vr = victory_road(a, b, landmarks_doc)
            if vr:
                p = np.array(vr, float)
                out.append({"from": a["id"], "to": b["id"], "victory_road": True,
                            "length_blocks": round(float(np.hypot(*np.diff(p, axis=0).T).sum())), "polyline": vr})
                continue
        s = (int(a["centre"]["x"]) // CELL, int(a["centre"]["z"]) // CELL)
        g = (int(b["centre"]["x"]) // CELL, int(b["centre"]["z"]) // CELL)
        path, cost = RP.route(hc, passable, s, g, SLOPE_WEIGHT)
        if path is None:
            out.append({"from": a["id"], "to": b["id"], "polyline": None})
            continue
        pts = [[x * CELL + CELL // 2, z * CELL + CELL // 2] for x, z in path]
        length = float(sum(np.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)))
        out.append({"from": a["id"], "to": b["id"], "length_blocks": round(length),
                    "polyline": [pts[i] for i in range(0, len(pts), 2)] + [pts[-1]]})
    return out


def crossings(leg_rows, regions_doc, n):
    """Blocks of each leg inside each sub-region (polylines rasterised 12 blocks wide at 4-block resolution)."""
    f = 4
    res = {}
    for s in regions_doc["subregions"]:
        im = Image.new("L", (n // f, n // f), 0)
        d = ImageDraw.Draw(im)
        for ring in s["polygons"]:
            d.polygon([(x / f, z / f) for x, z in ring], fill=1)
        mask = np.asarray(im) > 0
        for leg in leg_rows:
            if not leg.get("polyline"):
                continue
            p = np.array(leg["polyline"], float)
            seg = np.hypot(*np.diff(p, axis=0).T)
            mids = (p[1:] + p[:-1]) / 2 / f
            inside = mask[np.clip(mids[:, 1].astype(int), 0, n // f - 1), np.clip(mids[:, 0].astype(int), 0, n // f - 1)]
            blocks = float(seg[inside].sum())
            if blocks > 0:
                res.setdefault(s["id"], {})["%s->%s" % (leg["from"], leg["to"])] = round(blocks)
    return res


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--towns", default=str(T.ROOT / "data" / "towns.json"))
    p.add_argument("--regions", default=str(T.ROOT / "data" / "regions.json"))
    a = p.parse_args(argv)
    a.out = a.out or str(T.ROOT / "derived" / "routes" / "critical_legs.json")
    heights, world = T.load_from_args(a)
    towns = json.loads(Path(a.towns).read_text(encoding="utf-8"))
    regions = json.loads(Path(a.regions).read_text(encoding="utf-8"))
    landmarks = json.loads((T.ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
    rows = legs(towns, heights, T.sea_level(world), landmarks)
    doc = {"generator": "tools/critical_legs.py", "cell_blocks": CELL, "slope_weight": SLOPE_WEIGHT,
           "provenance": T.provenance(world, Path(a.world)), "legs": rows,
           "subregion_blocks": crossings(rows, regions, heights.shape[0])}
    T.write_json(a.out, doc)
    for r in rows:
        print("%-12s -> %-12s %s" % (r["from"], r["to"], r.get("length_blocks")))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
