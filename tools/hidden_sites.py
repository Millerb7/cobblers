#!/usr/bin/env python
"""Hidden legendary sites: find, and re-check, places a pasted catalogue template is STUMBLED ON rather than shown.

The owner, 2026-10-03: "I do not want a row of landmarks - I want places you stumble on ... Spread them so finding
one is an event." This tool measures that brief on the canonical heightmap (tools/ground.py, rounded) and on the
authored data, never on a world.

  python tools/hidden_sites.py check                  every hidden site against every rule below; exit 1 on a problem
  python tools/hidden_sites.py search <WxHxD> <x0> <z0> <x1> <z1> [--stride N] [--top N]
                                                       candidate footprints in a box, most enclosed first

THE RULES a hidden site is held to (`check`), each with where its number comes from:

  clearance   no authored x/z within CLEARANCE (96) blocks of the footprint EDGE, from EVERY data/*.json and
              data/*/*.json: any dict with numeric x and z, and any list of 2 or 3 numbers that reads as [x, z] or
              [x, y, z] inside the map. That deliberately includes route and river vertices and region outlines:
              a site 96 blocks from a road is not hidden. The site's own two records (its adopted-site entry and
              its data/placements.json donor record) are skipped, and nothing else is.
  keep_out    outside the Mega farm box x3450..4250, z4700..5450, and at least KEEP_OUT_RADIUS from the three new
              southern places (3556, 6112), (4530, 5850), (3708, 5716): the brief of 2026-10-03.
  portals     at least data/portals.json rules.min_from_legendary_mouth from every portal, footprint edge to
              portal point, the same measure tests/test_adopted_legendary_sites.py uses.
  spread      at least SPREAD (800) blocks, centre to centre, from every OTHER legendary site: the adopted sites
              (resolved through tools/adopted_sites.py, scheduled or not) and every data/legendaries.json
              encounter with a mouth or portal.
  dry         every footprint column above data/world.json sea level.

What this does NOT cover (CLAUDE.md "Our list is not the world"): anything in the world that no file in data/
authors -- a donor template's own outbuildings, a mod's placement, an earlier pass's leftovers. The clearance is
from our records, not from the world.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import adopted_sites  # noqa: E402

CLEARANCE = 96
SPREAD = 800
KEEP_OUT_BOX = (3450, 4700, 4250, 5450)            # x0, z0, x1, z1: the Mega farm, 2026-10-03
KEEP_OUT_POINTS = ((3556, 6112), (4530, 5850), (3708, 5716))
KEEP_OUT_RADIUS = 300
MAP = 8192


def _is_xz_list(v):
    if not isinstance(v, list) or len(v) not in (2, 3) or not all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in v):
        return False
    x, z = v[0], v[-1]
    if len(v) == 3 and not -64 <= v[1] <= 640:
        return False
    return 0 <= x < MAP and 0 <= z < MAP


def _walk(obj, out, src, skip_ids):
    if isinstance(obj, dict):
        if obj.get("id") in skip_ids:
            return
        if all(isinstance(obj.get(k), (int, float)) and not isinstance(obj.get(k), bool) for k in ("x", "z")):
            if 0 <= obj["x"] < MAP and 0 <= obj["z"] < MAP:
                out.append((float(obj["x"]), float(obj["z"]), src))
        for v in obj.values():
            _walk(v, out, src, skip_ids)
    elif isinstance(obj, list):
        if _is_xz_list(obj):
            out.append((float(obj[0]), float(obj[-1]), src))
            return
        for v in obj:
            _walk(v, out, src, skip_ids)


def authored_points(skip_ids=()):
    """[(x, z, file)] for every authored coordinate in data/*.json and data/*/*.json, minus the records named."""
    out = []
    files = sorted(glob.glob(str(ROOT / "data" / "*.json"))) + sorted(glob.glob(str(ROOT / "data" / "*" / "*.json")))
    for f in files:
        doc = json.loads(Path(f).read_text(encoding="utf-8"))
        _walk(doc, out, os.path.relpath(f, ROOT).replace("\\", "/"), set(skip_ids))
    return out


def edge_distance(box, x, z):
    x0, z0, x1, z1 = box
    return math.hypot(max(x0 - x, 0, x - x1), max(z0 - z, 0, z - z1))


def nearest_authored(box, points):
    """(distance from the footprint edge, x, z, file) of the nearest authored point, or None."""
    import numpy as np
    if not points:
        return None
    xs = np.array([p[0] for p in points])
    zs = np.array([p[1] for p in points])
    x0, z0, x1, z1 = box
    dx = np.maximum(np.maximum(x0 - xs, 0), xs - x1)
    dz = np.maximum(np.maximum(z0 - zs, 0), zs - z1)
    d = np.hypot(dx, dz)
    i = int(d.argmin())
    return float(d[i]), points[i][0], points[i][1], points[i][2]


def keep_out_problems(box):
    bad = []
    bx0, bz0, bx1, bz1 = KEEP_OUT_BOX
    x0, z0, x1, z1 = box
    if not (x1 < bx0 or x0 > bx1 or z1 < bz0 or z0 > bz1):
        bad.append("footprint overlaps the Mega farm box x%d..%d z%d..%d" % (bx0, bx1, bz0, bz1))
    for px, pz in KEEP_OUT_POINTS:
        d = edge_distance(box, px, pz)
        if d < KEEP_OUT_RADIUS:
            bad.append("%.0f blocks from the new southern place (%d, %d); the brief keeps %d" % (d, px, pz, KEEP_OUT_RADIUS))
    return bad


def portal_rule():
    doc = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))
    return doc["rules"]["min_from_legendary_mouth"], [(q["id"], q["at"]) for q in doc["portals"]]


def legendary_centres(exclude_site=None, placements=None):
    """{name: (x, z)} for every adopted site but the one excluded, and every data/legendaries.json encounter
    whose mouth or portal is a coordinate."""
    out = {}
    for s in adopted_sites.sites():
        if s["id"] == exclude_site:
            continue
        out[s["id"]] = tuple(adopted_sites.centre(s, placements))
    legend = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))["encounters"]
    for e in legend:
        for k in ("mouth", "portal"):
            v = e.get(k)
            if isinstance(v, list) and len(v) >= 2 and all(isinstance(n, (int, float)) for n in v):
                out["legendaries.json:" + e["id"]] = (v[0], v[-1])
                break
    return out


def hidden_ids():
    doc = json.loads(adopted_sites.SITES.read_text(encoding="utf-8"))
    return [s["id"] for s in doc["sites"] if s.get("hidden")]


def problems(site, ground, points=None, placements=None):
    """[problem] for one adopted site against every rule in the module docstring."""
    import numpy as np
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    sea = world["vertical"]["sea_level"]
    box = adopted_sites.footprint(site, placements)
    skip = {site["id"], site.get("scheduled_as")}
    pts = points if points is not None else authored_points(skip)
    bad = []
    near = nearest_authored(box, [p for p in pts])
    if near and near[0] < CLEARANCE:
        bad.append("authored (%d, %d) in %s is %.0f from the footprint edge; the rule is %d"
                   % (near[1], near[2], near[3], near[0], CLEARANCE))
    bad += keep_out_problems(box)
    rule, portals = portal_rule()
    for pid, (px, pz) in portals:
        d = edge_distance(box, px, pz)
        if d < rule:
            bad.append("portal %s is %.0f from the footprint edge; the rule is %d" % (pid, d, rule))
    c = adopted_sites.centre(site, placements)
    for name, (x, z) in legendary_centres(site["id"], placements).items():
        d = math.hypot(c[0] - x, c[1] - z)
        if d < SPREAD:
            bad.append("%s is %.0f from this site's centre; the spread is %d" % (name, d, SPREAD))
    h = ground.box(*box)
    if int(h.min()) <= sea:
        bad.append("ground as low as y%d against sea level y%d" % (int(h.min()), sea))
    return bad


def enclosure(ground, cx, cz, seat, radii=(64, 96, 128, 160), rays=24, rise=12):
    """(fraction of rays walled, mean rise): along each of `rays` bearings, the highest ground at any of `radii` that
    stands `rise` or more above the seat counts that bearing as walled. 1.0 is a pit; 0.0 a summit or a plain."""
    walled, rises = 0, []
    for i in range(rays):
        a = 2 * math.pi * i / rays
        top = max(ground(int(cx + r * math.cos(a)), int(cz + r * math.sin(a))) for r in radii)
        rises.append(top - seat)
        if top - seat >= rise:
            walled += 1
    return walled / rays, sum(rises) / rays


ROUTE_FILES = ("data/route_paths.json", "data/routes.json")


def sightings(ground, box, top_y, points=None, radius=1200, eye=2, step=4):
    """(route points within `radius` that see the template's top, route points within `radius`, nearest route point
    distance): a bare-terrain line of sight from a walker's eye on every route vertex to the top occupied layer over
    the footprint's centre. Trees, buildings and weather are NOT modelled, so this over-counts what a player sees:
    a site with no sighting here is hidden by the land itself."""
    pts = points if points is not None else authored_points()
    x0, z0, x1, z1 = box
    cx, cz = (x0 + x1) / 2.0, (z0 + z1) / 2.0
    seen, near, nearest = 0, 0, None
    for x, z, src in pts:
        if src not in ROUTE_FILES:
            continue
        d = math.hypot(x - cx, z - cz)
        nearest = d if nearest is None or d < nearest else nearest
        if d > radius:
            continue
        near += 1
        ey = ground(int(x), int(z)) + eye
        n = max(1, int(d // step))
        clear = True
        for i in range(1, n):
            t = i / n
            sx, sz = x + (cx - x) * t, z + (cz - z) * t
            if x0 <= sx <= x1 and z0 <= sz <= z1:
                break  # inside the footprint: the template itself is what is seen
            if ground(int(sx), int(sz)) > ey + (top_y - ey) * t:
                clear = False
                break
        seen += clear
    return seen, near, (round(nearest) if nearest is not None else None)


def seat(heights):
    """(y, cut, fill): the cheapest bottom layer in the measured range, ties to the lowest."""
    import numpy as np
    best = None
    for y in range(int(heights.min()), int(heights.max()) + 1):
        cut = int(np.clip(heights - y, 0, None).sum())
        fill = int(np.clip(y - heights, 0, None).sum())
        if best is None or cut + fill < best[1] + best[2]:
            best = (y, cut, fill)
    return best


def search(ground, size, bbox, stride=16, top=15, max_spread=8):
    sx, sy, sz = size
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    sea = world["vertical"]["sea_level"]
    pts = authored_points()
    rule, portals = portal_rule()
    legend = legendary_centres()
    x0, z0, x1, z1 = bbox
    found = []
    for z in range(z0, z1 - sz + 1, stride):
        for x in range(x0, x1 - sx + 1, stride):
            box = (x, z, x + sx - 1, z + sz - 1)
            h = ground.box(*box)
            if int(h.min()) <= sea or int(h.max() - h.min()) > max_spread:
                continue
            if keep_out_problems(box):
                continue
            if any(edge_distance(box, *p) < rule for _, p in portals):
                continue
            cx, cz = x + sx // 2, z + sz // 2
            if any(math.hypot(cx - a, cz - b) < SPREAD for a, b in legend.values()):
                continue
            near = nearest_authored(box, pts)
            if near and near[0] < CLEARANCE:
                continue
            y, cut, fill = seat(h)
            frac, rise = enclosure(ground, cx, cz, y)
            found.append({"corner": [x, z], "y": y, "cut": cut, "fill": fill, "spread": int(h.max() - h.min()),
                          "enclosed": round(frac, 2), "mean_rise": round(rise, 1), "nearest_authored": round(near[0]) if near else None,
                          "nearest_src": near[3] if near else None})
    found.sort(key=lambda r: (-r["enclosed"], -r["mean_rise"], r["cut"] + r["fill"]))
    return found[:top]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    s = sub.add_parser("search")
    s.add_argument("size")
    s.add_argument("box", nargs=4, type=int)
    s.add_argument("--stride", type=int, default=16)
    s.add_argument("--top", type=int, default=12)
    s.add_argument("--max-spread", type=int, default=8)
    a = ap.parse_args(argv)
    import ground as G
    g = G.load()
    if a.cmd == "search":
        size = tuple(int(n) for n in a.size.split("x"))
        for r in search(g, size, tuple(a.box), a.stride, a.top, a.max_spread):
            print(json.dumps(r))
        return 0
    placements = json.loads(adopted_sites.PLACEMENTS.read_text(encoding="utf-8"))["placements"]
    ids = hidden_ids()
    if not ids:
        print("no site in data/adopted_legendary_sites.json is marked hidden")
        return 1
    rc = 0
    for sid in ids:
        site = adopted_sites.site(sid)
        bad = problems(site, g, placements=placements)
        box = adopted_sites.footprint(site, placements)
        print("%-28s %s %s" % (sid, box, "OK" if not bad else "PROBLEMS"))
        for b in bad:
            print("    " + b)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
