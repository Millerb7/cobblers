#!/usr/bin/env python
"""Audit: a rod catches only what we author, and every water column has exactly the one table the guide shows.

THE OWNER, 2026-10-22: "i dont want another moment of my friend getting a mon he doesnt want in an area." Three
properties, each checked from something other than the code that produced it:

  A. EVERY WATER COLUMN HAS EXACTLY ONE TABLE. The compiled fishing details (tools/compile_spawns.py build_fishing,
     compiled here in memory) are read as the game reads them: a detail fits a bobber at (x, z) when minX <= x <= maxX
     and minZ <= z <= maxZ. Their boxes are rasterised on a 4-block stride and each column of water is looked up there.
     Water comes from the canonical heightmap by its own test (round(ground) < sea level, the margin outside the map
     being sea; the painted lakes by water_mask.in_polygons, a point test; the river courses at their stations), NOT
     from tools/fishing_cover.py's raster, so a fault in the plan's water mask shows here. A column in a spawn-free
     zone must have none.
  B. THE GUIDE SHOWS THAT TABLE. Every area that owns a water column is a section of docs/player/fishing.html, and the
     species the compiled details name for it are the species that section lists (the page drops legendary-class
     species by its own rule; nothing else may differ).
  C. NOTHING INHERITED. Given a built tools/suppress_inherited_spawns.py pack (--suppress-pack) no enabled file in it
     holds a fishing detail; given the server too (--server, --world) every inherited path whose effective source holds
     one is overridden by a file that is disabled or holds none. Without them C is NOT_EXECUTED, said so.

  python tools/fishing_audit.py [--suppress-pack DIR --server DIR --world DIR] > report 2>&1

Exit 1 on any problem. NOT covered: what a running Cobblemon does with these details (nothing here was cast in game),
water the heightmap and data/landmarks.json do not hold (a pool a town or a dungeon builds), and fishing a dungeon's own
pools hand out inside the dungeon.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

STRIDE = 4
WORLD_MIN, WORLD_MAX = -1024, 9215
SIDE = (WORLD_MAX - WORLD_MIN + 1) // STRIDE


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def compiled_details(fill="default"):
    """{area: [(minX, maxX, minZ, maxZ), ...]} and {area: {species}} read back from the compiled fishing files."""
    import compile_spawns as C
    import fishing_cover as FC
    spawns, regions, routes = _load("spawns.json"), _load("regions.json"), _load("routes.json")
    doc = FC.load() if fill == "default" else fill
    files, _ = C.build_fishing(spawns, regions, routes, C.waterway_boxes(), C.SUBREGION_GRID, doc)
    boxes, species = {}, {}
    for rel, text in files.items():
        area = Path(rel).stem
        for d in json.loads(text)["spawns"]:
            c = d["condition"]
            boxes.setdefault(area, set()).add((c["minX"], c["maxX"], c["minZ"], c["maxZ"]))
            species.setdefault(area, set()).add(d["pokemon"])
    return {a: sorted(b) for a, b in boxes.items()}, species


def owner_raster(boxes):
    """int16 [z, x] on the 4-block stride: how many areas' boxes hold the column at the stride's centre."""
    import numpy as np
    cnt = np.zeros((SIDE, SIDE), dtype=np.int16)
    for area, bs in boxes.items():
        seen = np.zeros((SIDE, SIDE), dtype=bool)
        for x0, x1, z0, z1 in bs:
            seen[(z0 - WORLD_MIN) // STRIDE:(z1 - WORLD_MIN) // STRIDE + 1,
                 (x0 - WORLD_MIN) // STRIDE:(x1 - WORLD_MIN) // STRIDE + 1] = True
        cnt += seen
    return cnt


def owner_index(boxes):
    """The same raster holding the area's index (the last, where several), for the guide check."""
    import numpy as np
    names = sorted(boxes)
    idx = np.full((SIDE, SIDE), -1, dtype=np.int16)
    for i, area in enumerate(names):
        for x0, x1, z0, z1 in boxes[area]:
            idx[(z0 - WORLD_MIN) // STRIDE:(z1 - WORLD_MIN) // STRIDE + 1,
                (x0 - WORLD_MIN) // STRIDE:(x1 - WORLD_MIN) // STRIDE + 1] = i
    return idx, names


def water_samples():
    """(sea mask [z, x] on the stride, lake points [(x, z)], river station points [(x, z)]), from the heightmap."""
    import numpy as np
    import ground as G
    import water_mask as WM
    g = G.load()
    h = np.round(g.heights)
    sea = np.ones((SIDE, SIDE), dtype=bool)                  # outside the heightmap: sea
    centre = WORLD_MIN + STRIDE // 2
    zs = np.arange(SIDE) * STRIDE + centre - g.oz
    xs = np.arange(SIDE) * STRIDE + centre - g.ox
    zin, xin = (zs >= 0) & (zs < h.shape[0]), (xs >= 0) & (xs < h.shape[1])
    sub = np.zeros((SIDE, SIDE), dtype=bool)
    sub[np.ix_(zin, xin)] = h[np.ix_(zs[zin], xs[xin])] < WM.sea_level()
    sea[np.ix_(zin, xin)] = sub[np.ix_(zin, xin)]
    lakes = []
    for b in WM.bodies().values():
        if not b["basin"]:
            continue
        xs_ = [q[0] for r in b["basin"] for q in r]
        zs_ = [q[1] for r in b["basin"] for q in r]
        for z in range(min(zs_) - min(zs_) % 8, max(zs_) + 1, 8):
            for x in range(min(xs_) - min(xs_) % 8, max(xs_) + 1, 8):
                if 0 <= x - g.ox < h.shape[1] and 0 <= z - g.oz < h.shape[0] and h[z - g.oz, x - g.ox] < b["level_y"] \
                        and WM.in_polygons(b["basin"], x, z):
                    lakes.append((x, z))
    rivers = []
    import grade_rivers as GR
    doc = _load("rivers.json")
    cut = set((doc.get("cut") or {}).get("courses_cut", []))
    for c in doc["courses"]:
        if c["id"] in cut:
            pts, chain = GR.densify_chained(c["graded_polyline"])
            for (x, z, _s, _f), ch in list(zip(pts, chain))[::8]:
                if not GR.at_chainage(c["reaches"], ch)["water_body"]:
                    rivers.append((int(round(x)), int(round(z))))
    return sea, lakes, rivers


def zones_cells():
    import compile_spawns as C
    return C.spawn_free_zones()


def check_columns(boxes, problems, notes):
    import numpy as np
    cnt = owner_raster(boxes)
    zones = zones_cells()
    sea, lakes, rivers = water_samples()
    # a spawn-free zone cuts every 32-block cell it touches out of every fishing table (compile_spawns build_fishing)
    cut = np.zeros((SIDE, SIDE), dtype=bool)
    for a, b, c, d in zones:
        x0, x1 = (a - WORLD_MIN) // 32 * 32, (b - WORLD_MIN) // 32 * 32 + 31
        z0, z1 = (c - WORLD_MIN) // 32 * 32, (d - WORLD_MIN) // 32 * 32 + 31
        cut[z0 // STRIDE:z1 // STRIDE + 1, x0 // STRIDE:x1 // STRIDE + 1] = True
    bad_zone = int(((cnt > 0) & cut).sum())
    if bad_zone:
        problems.append("%d raster columns inside a cell a spawn-free zone touches still have a fishing table" % bad_zone)
    wet = sea & ~cut

    def touched(px, pz):
        ix, iz = (px - WORLD_MIN) // STRIDE, (pz - WORLD_MIN) // STRIDE
        return bool(cut[iz, ix])

    no = many = 0
    first = []
    z, x = np.nonzero(wet & (cnt != 1))
    for zz, xx in zip(z.tolist(), x.tolist()):
        if cnt[zz, xx] > 1:
            many += 1
        else:
            no += 1
        if len(first) < 3:
            first.append((WORLD_MIN + xx * STRIDE + STRIDE // 2, WORLD_MIN + zz * STRIDE + STRIDE // 2, int(cnt[zz, xx])))
    lakes = [pt for pt in lakes if not touched(*pt)]
    rivers = [pt for pt in rivers if not touched(*pt)]
    for kind, pts in (("lake", lakes), ("river", rivers)):
        for px, pz in pts:
            n = int(cnt[(pz - WORLD_MIN) // STRIDE, (px - WORLD_MIN) // STRIDE])
            if n != 1:
                if n > 1:
                    many += 1
                else:
                    no += 1
                if len(first) < 6:
                    first.append((px, pz, n, kind))
    total = int(wet.sum()) + len(lakes) + len(rivers)
    notes.append("water sample: %d sea columns on a %d-block stride, %d lake points, %d river stations"
                 % (int(wet.sum()), STRIDE, len(lakes), len(rivers)))
    if no or many:
        problems.append("water without exactly one table: %d with none, %d with several, of %d sampled (first %s)"
                        % (no, many, total, first))
    return cnt, wet, lakes, rivers


def check_guide(boxes, species, cnt, wet, lakes, rivers, problems, notes):
    import numpy as np
    import player_guide_fishing as PG
    idx, names = owner_index(boxes)
    owning = set()
    z, x = np.nonzero(wet & (cnt >= 1))
    owning |= {names[int(i)] for i in np.unique(idx[z, x]) if i >= 0}
    for px, pz in lakes + rivers:
        i = idx[(pz - WORLD_MIN) // STRIDE, (px - WORLD_MIN) // STRIDE]
        if i >= 0:
            owning.add(names[int(i)])
    page = (ROOT / "docs" / "player" / "fishing.html").read_text(encoding="utf-8")
    ids = set(re.findall(r'<article class="area" id="([^"]+)"', page))
    guide = {}
    m = PG.collect()
    for r in m["regions"]:
        for a in r["areas"]:
            guide[a["id"]] = {e["species"] for e in a["rows"]}
    for a in sorted(owning):
        if a not in ids:
            problems.append("area %s owns water and has no section in docs/player/fishing.html" % a)
        elif guide.get(a) != {s for s in species[a] if not PG.is_legend(s)}:
            problems.append("area %s: the page lists %s, the compiled details name %s"
                            % (a, sorted(guide.get(a) or []), sorted(s for s in species[a] if not PG.is_legend(s))))
    notes.append("%d areas own sampled water; each is a section of the guide" % len(owning))


FISHING_RE = re.compile(r'"(?:spawnablePositionType|context)"\s*:\s*"fishing"', re.I)


def check_inherited(pack, server, world, problems, notes):
    """C. Reads the built pack's files and, when given the server, the sources they override."""
    live = []
    for f in sorted(Path(pack).rglob("*.json")):
        if f.name in ("manifest.json",):
            continue
        text = f.read_text(encoding="utf-8")
        try:
            enabled = json.loads(text).get("enabled", True) is not False
        except ValueError:
            problems.append("%s does not parse" % f)
            continue
        if enabled and FISHING_RE.search(text):
            live.append(f.relative_to(pack).as_posix())
    if live:
        problems.append("%d enabled files in %s still hold a fishing detail (first %s)" % (len(live), pack, live[:3]))
    notes.append("suppression pack %s: %d enabled files hold a fishing detail" % (pack, len(live)))
    if server:
        import suppress_inherited_spawns as SIS
        eff = {}
        for src, path, raw in SIS.collect(Path(server), Path(world) if world else Path("no-such-world")):
            eff[path] = raw
        unhandled = []
        for path, raw in eff.items():
            text = raw.decode("utf-8", "replace")
            if not FISHING_RE.search(text):
                continue
            try:
                if json.loads(text).get("enabled", True) is False:
                    continue
            except ValueError:
                pass
            ns, rel = path.split(":", 1)
            f = Path(pack) / "data" / ns / "spawn_pool_world" / rel
            if not f.is_file():
                unhandled.append(path)
        if unhandled:
            problems.append("%d inherited paths hold a fishing detail the pack does not override (first %s)"
                            % (len(unhandled), unhandled[:3]))
        notes.append("%d inherited paths hold fishing details; %d unhandled" % (
            sum(1 for r in eff.values() if FISHING_RE.search(r.decode("utf-8", "replace"))), len(unhandled)))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--suppress-pack", help="a built tools/suppress_inherited_spawns.py pack (checks C)")
    p.add_argument("--server", help="the server dir the pack was built from (checks every inherited path)")
    p.add_argument("--world", help="a DISPOSABLE world dir; never the live one")
    a = p.parse_args(argv)
    problems, notes = [], []
    boxes, species = compiled_details()
    notes.append("compiled fishing: %d areas, %d boxes" % (len(boxes), sum(len(v) for v in boxes.values())))
    cnt, wet, lakes, rivers = check_columns(boxes, problems, notes)
    check_guide(boxes, species, cnt, wet, lakes, rivers, problems, notes)
    if a.suppress_pack:
        check_inherited(a.suppress_pack, a.server, a.world, problems, notes)
    else:
        notes.append("C (nothing inherited): NOT_EXECUTED, no --suppress-pack given")
    for n in notes:
        print(n)
    for q in problems:
        print("PROBLEM: " + q)
    print("fishing audit: %s" % ("FAIL, %d problems" % len(problems) if problems else "ok"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
