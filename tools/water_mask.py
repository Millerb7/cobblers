#!/usr/bin/env python
"""Where water is ACTUALLY painted, for every tool that checks a thing claims to stand in water.

THE BUG THIS EXISTS TO CLOSE (F7, docs/FLIGHT_FINDINGS_2026-09-29.md). `tools/portals.py`'s
`water_check` tested a dive portal against its landmark's `extent.polygons`. Water is not painted
there. `tools/paint_maps.py`'s lake pass (the loop over `landmarks` that builds `water_<id>.png`)
rasterises the landmark's `water_body.basin_polygons`, takes `wet = basin & (heights < level_y)`,
and `tools/worldpainter/paint.js` raises the water level to `level_y` on every column of that mask.
`extent` is the landmark's label outline -- what the place IS, for prose, routes and signage -- and
the two sets disagree in BOTH directions. Measured on the canonical heightmap (`python
tools/water_mask.py gap`, 2026-09-30):

    landmark                lev    extent     basin   painted  in extent, NOT painted
    lake_tilpey              77   1163705   1190445   1133789                  219737
    peak_pond               105     46801     75607     57647                   10116
    lake_viltri             103     19431     36125     33232                    6142
    shrew_lake              106    151003    197951    183470                   23543
    arrow_lake              100    110017    117853    113781                   11033
    watering_hole            95     20334     24555     22684                    5695
    pond_west_of_mt_clay    119     50351     35139     32851                   20457
    ravine_head_tarn        127     43981     43981     29926                   14055
    marshy_marsh            100    134935    147283    129833                   64554

Two hundred thousand dry columns inside Lake Tilpey's extent polygon would have passed the old
check; `pond_west_of_mt_clay`'s extent is larger than its basin outright. The gap runs the other way
too: `tilpey_sabrina_dock`'s whole 15-column jetty is painted lake water and sits OUTSIDE
`lake_tilpey.extent`, so an extent test would also have refused a dock that is genuinely afloat.

THE RULE HERE, and it fails closed. A column is under water if

  - it is inside one of a landmark's `water_body.basin_polygons` AND its ground is below that body's
    `level_y`  (a lake, pond, tarn or marsh), or
  - its ground is below `data/world.json` `vertical.sea_level` (the sea).

Ground comes from `tools/ground.py` (the canonical heightmap, rounded) -- CLAUDE.md's ground rule --
never from a world save. Rounded is also the STRICTER reading: paint compares the float height, so a
column at h=76.6 under a level of y77 is in paint's mask while the exported world puts its ground
block at y77, level with the surface and holding no water. Rounding refuses that column.

THE POINT TEST vs THE RASTER. `claim()` uses an even-odd ray cast, because a point test must not
need an 8192x8192 raster (the portals' own unit tests run with no heightmap at all). PIL's polygon
fill, which paint_maps uses, agrees with the ray cast across a polygon's interior and can differ by
a pixel on its boundary. Two things keep that from mattering: a claim must have EVERY column of its
footprint inside the basin, not just its centre, and a claim carries a submersion margin in blocks.
`python tools/water_mask.py gap` re-checks every sited claim against the real raster and reports any
column where the two disagree; it reported none on 2026-09-30.

WHAT THIS DOES NOT PROVE. That water reached the world. The mask is what the export was TOLD to
paint; a column can be in it and still be dry in the save if the export did not run, ran against
another heightmap, or a later carve raised the floor. Only a world read (tools/town_audit.py's
style, or eyes in game) settles that, and the F5 lake-bed repair is the standing proof that a world
can disagree with its own paint.

  python tools/water_mask.py gap    [--source-root R]   # the table above, and the claim cross-check
  python tools/water_mask.py claims [--source-root R]   # every sited water claim, point-wise
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class WaterError(Exception):
    pass


def bodies(path=None):
    """{landmark id: {"level_y", "basin", "extent"}} for every landmark with an authored water body.

    A body with a level but no basin polygons is an authoring error, not a body to skip: without a
    basin nothing is painted, so anything claiming to be in it is dry. It is returned with an empty
    basin and `claim()` refuses every column of it."""
    doc = json.loads((Path(path) if path else ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
    out = {}
    for l in doc["landmarks"]:
        wb = l.get("water_body") or {}
        if wb.get("level_y") is None:
            continue
        out[l["id"]] = {"level_y": int(wb["level_y"]),
                        "basin": [[tuple(q) for q in r] for r in (wb.get("basin_polygons") or [])],
                        "extent": [[tuple(q) for q in r] for r in ((l.get("extent") or {}).get("polygons") or [])]}
    return out


def sea_level(path=None):
    """The sea's water level from data/world.json. The import's `water_level` must agree with it."""
    w = json.loads((Path(path) if path else ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    sea = int(w["vertical"]["sea_level"])
    imp = w.get("import", {}).get("water_level")
    if imp is not None and int(imp) != sea:
        raise WaterError("data/world.json: vertical.sea_level y%d but import.water_level y%d; the export paints "
                         "the import's, so a sea claim cannot be checked until they agree" % (sea, int(imp)))
    return sea


def in_polygons(polys, x, z):
    """Even-odd ray cast against a list of rings. False for an empty list: nothing contains nothing."""
    inside = False
    for poly in polys:
        n, c, j = len(poly), False, len(poly) - 1
        for i in range(n):
            xi, zi = poly[i][0], poly[i][1]
            xj, zj = poly[j][0], poly[j][1]
            if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / float(zj - zi) + xi):
                c = not c
            j = i
        if c:
            return True
    return False


def claim(body, columns, ground, min_submersion=0, bodies_=None, label=None):
    """[problem] for a thing that claims every one of `columns` stands under `body`'s painted water.

    `body` is a landmark id, or the string "sea". `columns` is an iterable of (x, z); EVERY one must
    be under water, because a footprint half out of the lake is half dry. `min_submersion` is how
    far below the surface the ground must be, in blocks: 0 means "any water at all", which is enough
    for a boat and nowhere near enough for a structure.

    Fails closed on every unknown: an unnamed body, a body with no basin, a column outside the
    basin, a column whose ground is at or above the surface, a column short of the margin."""
    who = (label or body) + ": "
    cols = list(columns)
    if not cols:
        return [who + "a water claim with no columns proves nothing"]
    if body == "sea":
        level, basin = sea_level(), None
    else:
        bb = (bodies_ if bodies_ is not None else bodies()).get(body)
        if bb is None:
            return [who + "no water body %r with an authored level_y in data/landmarks.json" % body]
        level, basin = bb["level_y"], bb["basin"]
        if not basin:
            return [who + "%s has a level y%d but no basin_polygons, so tools/paint_maps.py paints no water "
                          "in it at all" % (body, level)]
    out = []
    for x, z in cols:
        if basin is not None and not in_polygons(basin, x, z):
            out.append(who + "(%d, %d) is outside %s's basin_polygons, which is the only place "
                             "tools/paint_maps.py paints its water" % (x, z, body))
            break
    need = max(int(min_submersion), 1)   # 0 still means one block of water: ground LEVEL with the
    for x, z in cols:                    # surface holds none, and `>= level` is the dry case
        gy = ground(x, z)
        if level - gy < need:
            out.append(who + "(%d, %d) has ground at y%d, %d under %s's surface y%d (min %d)"
                             % (x, z, gy, level - gy, body, level, need))
            break
    return out


def level_at(x, z, ground, bodies_=None, sea=None):
    """(body id, surface y) for the painted water over one column, or (None, None) if it is dry.

    Lakes first, then the sea, matching paint.js's "only ever raise" order at a column both claim."""
    best = (None, None)
    for bid, b in (bodies_ if bodies_ is not None else bodies()).items():
        if b["basin"] and ground(x, z) < b["level_y"] and in_polygons(b["basin"], x, z):
            if best[1] is None or b["level_y"] > best[1]:
                best = (bid, b["level_y"])
    if best[0] is not None:
        return best
    s = sea_level() if sea is None else sea
    return ("sea", s) if ground(x, z) < s else (None, None)


# ------------------------------------------------------------------------------------------- the CLI


def sited_claims():
    """[(label, body, [columns], min_submersion)] for everything in data/ that asserts it is in water.

    Read-only: this names the claims, it does not own the tools that make them. The dive portals are
    checked by tools/portals.py and tools/portals_audit.py, which call claim() above.

    The ferry docks are listed because they assert water too, and their rule is modelled here exactly
    as tools/ferry_docks.py states it (its over-water block, "every deck cell past the root must stand
    over water on the heightmap, and the head must have at least `min_head_depth` blocks of it"): the
    whole 3-wide deck at a margin of 0, and the head column alone at `min_head_depth`. A dock's
    shoreward root is land on purpose and is not claimed. tools/ferry_docks.py does NOT call claim()
    -- it takes its lake level from the record's own `water.level` with no basin test at all, which is
    the same fail-open shape F7 found in the portals. That tool is not this change's to edit; the gap
    is reported instead, and `python tools/water_mask.py claims` is what covers those docks until it is.
    The `quay_head` and `host` docks have no deck of their own (another tool built the pier they stand
    on) and make no claim here."""
    out = []
    p = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))
    sub = p["rules"]["min_submersion"]
    for s in p["portals"]:
        if s["gate"] != "dive":
            continue
        x, z = s["at"]
        cols = [(x + dx, z + dz) for dx in range(-2, 3) for dz in range(-2, 3)]   # the 5 by 5 apron
        out.append(("portal %s" % s["id"], s["water_body"], cols, sub))
    step = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
    marks = bodies()
    f = json.loads((ROOT / "data" / "ferry_docks.json").read_text(encoding="utf-8"))
    for d in f["docks"]:
        if d.get("structure") != "jetty":
            continue
        w = d.get("water") or {}
        sx, sz = (d.get("shore") or {}).get("at") or d["near"]
        ax, az = step[d["out"]]
        px, pz = -az, ax
        n, half = int(d.get("length", 0)), (int(d.get("width", 3)) - 1) // 2
        if not n:
            continue
        deck = [(sx + ax * i + px * k, sz + az * i + pz * k)
                for i in range(1, n + 1) for k in range(-half, half + 1)]
        head = (sx + ax * n, sz + az * n)
        if w.get("kind") == "sea":
            body = "sea"
        else:
            hit = [b for b, v in marks.items() if v["level_y"] == w.get("level") and in_polygons(v["basin"], *head)]
            body = hit[0] if hit else "no landmark basin with level y%s holds the head %s" % (w.get("level"), list(head))
        out.append(("dock %s deck" % d["id"], body, deck, 0))
        out.append(("dock %s head" % d["id"], body, [head], int(d.get("min_head_depth", 0))))
    return out


def cmd_claims(a):
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as G
    g = G.Ground(a.source_root)
    bad = []
    for label, body, cols, sub in sited_claims():
        probs = claim(body, cols, g, sub, label=label)
        print("%-34s %-18s %3d columns  min %d  %s"
              % (label, body, len(cols), sub, "OK" if not probs else "PROBLEM"))
        bad += probs
    for b in bad:
        print("  " + b)
    print("%d claims, %d problems" % (len(sited_claims()), len(bad)))
    return 1 if bad else 0


def cmd_gap(a):
    """The size of the hole the old extent test left, and a raster cross-check of every claim."""
    import numpy as np
    from PIL import Image, ImageDraw
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as G
    g = G.Ground(a.source_root)
    H, ox, oz = g.heights, g.ox, g.oz

    def raster(rings):
        img = Image.new("L", (H.shape[1], H.shape[0]), 0)
        d = ImageDraw.Draw(img)
        for r in rings:
            d.polygon([(q[0] - ox, q[1] - oz) for q in r], fill=1)
        return np.asarray(img).astype(bool)

    bb = bodies()
    print("%-22s %5s %9s %9s %9s %9s" % ("landmark", "lev", "extent", "basin", "painted", "ext-painted"))
    wet_all = {}
    for bid, b in bb.items():
        ext, bas = raster(b["extent"]), raster(b["basin"])
        wet = bas & (H < b["level_y"])
        wet_all[bid] = wet
        print("%-22s %5d %9d %9d %9d %9d"
              % (bid, b["level_y"], ext.sum(), bas.sum(), wet.sum(), (ext & ~wet).sum()))
    sea = sea_level()
    disagree = 0
    for label, body, cols, _sub in sited_claims():
        for x, z in cols:
            r = (H[z - oz, x - ox] < sea) if body == "sea" else bool(wet_all.get(body, np.zeros((1, 1), bool))[z - oz, x - ox]) \
                if body in wet_all else False
            pw = not claim(body, [(x, z)], g, 0, bodies_=bb, label=label)
            if r != pw:
                disagree += 1
                print("  disagree %s (%d, %d): raster %s, point test %s" % (label, x, z, r, pw))
    print("%d sited claim columns where the raster and the point test disagree" % disagree)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("gap", cmd_gap), ("claims", cmd_claims)):
        s = sub.add_parser(name)
        s.add_argument("--source-root")
        s.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
