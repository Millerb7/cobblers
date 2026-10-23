#!/usr/bin/env python
"""Every water the playable world has fishes one authored table: the cover of tools/compile_spawns.py build_fishing.

THE OWNER, 2026-10-22: "go through the fishing spawns and sure that up, i dont want another moment of my friend
getting a mon he doesnt want in an area." On 2026-10-21 a friend fishing off Pallet's west shore hooked a Pyukumuku
that the fishing guide lists nowhere near it. Cause, measured (docs/mechanics/FISHING.md section 4b): the authored
fishing lists lie over the sub-region rasters and the sea bands' boxes, and between them sat 599 cells of sea and 25 of
lake water (about 0.6 km2) that no list reaches; the COBBLEVERSE datapack's own 599 fishing details (Pyukumuku's
"pyukumuku-4": ocean and beach, weight 2) stayed live there. tools/suppress_inherited_spawns.py now drops every
inherited fishing detail everywhere, so the rod catches ONLY what we author, and this module makes sure no water is
left with nothing to catch.

THE RULE. The playable world (-1024..9215 on both axes, inside the 10,240-block border) is cut into the 32-block cells
the sub-region rasters and the sea bands already use. Every cell, except one a spawn-free zone touches (nothing
spawns there at all), belongs to exactly ONE fishing area:

  - a cell one area covers stays with it
  - a cell two areas cover (a coarse sea-band cell that took in a strip of a coast sub-region's raster; 946 cells
    before this change) goes to the sea band when it holds open sea, else to the sub-region: the band's list is
    what swims there, the sub-region's is what lies on its bank. The loser CEDES the cell
  - a cell no area covers (the shore gaps between a polygon and a band, corridor cells, the dry sub-regions' own
    ground, the border margin) is FILLED from the nearest area of the right kind: a cell holding open sea takes the
    nearest SEA BAND, every other cell the nearest SUB-REGION that has a fishing list (chessboard distance over the
    cells, the order of the eight neighbours breaking a tie)

"Open sea" is the sea tools/open_water.py finds (below y62 and connected to the world border), dilated one 16-block
cell, with the heightmap's own below-sea columns inside the 32-block cell; the margin outside the heightmap is sea by
construction (docs/STATE.md "World facts").

The result is data/fishing_fill.json, status "derived" like data/rivers.json: `fill` and `cede` are boxes per area.
tools/compile_spawns.py build_fishing reads it with no heightmap (apply + verify_total fail closed on a stale file),
and the player guide (tools/player_guide_fishing.py) reads the same tables, so the guide stays the truth.

  python tools/fishing_cover.py plan      # (re)write data/fishing_fill.json from the heightmap
  python tools/fishing_cover.py check     # the file is what plan would write today (needs the heightmap)
  python tools/fishing_cover.py measure   # before/after: water columns per owner count (needs the heightmap)

NOT covered: a fishing list a DUNGEON carries (its own pools inside the dungeon), and water in a cell a spawn-free
zone touches (the gyms, the League, the relic hall, Heaven's Arena, the burrow, the Old Rafts), which catch nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import subregion_boxes  # noqa: E402

GRID = 32
WORLD_MIN, WORLD_MAX = -1024, 9215          # the playable limits inside the 10,240-block border (tools/open_water.py)
N = (WORLD_MAX - WORLD_MIN + 1) // GRID     # 320 cells a side
FILL = ROOT / "data" / "fishing_fill.json"
SCHEMA = "cobblers.fishing-fill/1"
SEA, FRESH = "sea", "fresh"


class CoverError(SystemExit):
    pass


# ------------------------------------------------------------------------------------------------ cells and boxes


def cell(v):
    return (int(v) - WORLD_MIN) // GRID


def box_cells(box):
    """{(ix, iz)} of the 32-block cells an inclusive (minX, maxX, minZ, maxZ) box holds; it must lie on the grid."""
    x0, x1, z0, z1 = box
    for v in (x0, z0):
        if (v - WORLD_MIN) % GRID:
            raise CoverError("fishing box %s is not on the %d-block grid" % (list(box), GRID))
    for v in (x1, z1):
        if (v + 1 - WORLD_MIN) % GRID:
            raise CoverError("fishing box %s is not on the %d-block grid" % (list(box), GRID))
    return {(ix, iz) for ix in range(cell(x0), cell(x1) + 1) for iz in range(cell(z0), cell(z1) + 1)}


def cells_to_boxes(cells):
    """World boxes (minX, maxX, minZ, maxZ) for a set of (ix, iz) cells: greedy maximal rectangles, sorted."""
    out = []
    for ix0, ix1, iz0, iz1 in subregion_boxes.merge_rectangles(cells):
        out.append((WORLD_MIN + ix0 * GRID, WORLD_MIN + (ix1 + 1) * GRID - 1,
                    WORLD_MIN + iz0 * GRID, WORLD_MIN + (iz1 + 1) * GRID - 1))
    return sorted(out)


def free_cells(zones):
    """Cells a spawn-free zone touches: no fishing list lies over them (compile_spawns cuts them out everywhere)."""
    out = set()
    for z in zones:
        out |= {(ix, iz) for ix in range(cell(z[0]), cell(z[1]) + 1) for iz in range(cell(z[2]), cell(z[3]) + 1)}
    return out


def owners(area_boxes):
    """{(ix, iz): [area, ...]} sorted by area id, from {area: [box, ...]}."""
    own = {}
    for area, boxes in area_boxes.items():
        for b in boxes:
            for c in box_cells(b):
                own.setdefault(c, []).append(area)
    for c in own:
        own[c].sort()
    return own


# ------------------------------------------------------------------------------------------------ the plan


def sea_cells(ground=None):
    """{(ix, iz)} of 32-block cells holding open sea, from the canonical heightmap (never a world)."""
    import numpy as np
    import open_water as OW
    import ground as G
    g = ground or G.load()
    _, sea16 = OW.cells(g)                                   # 16-block cells, [cz, cx], origin WORLD_MIN
    near = sea16.copy()
    near[1:, :] |= sea16[:-1, :]
    near[:-1, :] |= sea16[1:, :]
    near[:, 1:] |= sea16[:, :-1]
    near[:, :-1] |= sea16[:, 1:]
    n16 = sea16.shape[0]
    below = np.ones((n16 * 16, n16 * 16), dtype=bool)        # outside the heightmap is sea
    h = np.round(g.heights)
    oz, ox = g.oz - WORLD_MIN, g.ox - WORLD_MIN
    below[oz:oz + h.shape[0], ox:ox + h.shape[1]] = h < OW.SEA_LEVEL
    cell_below = below.reshape(N, GRID, N, GRID).any(axis=(1, 3))
    cell_near = near.reshape(N, 2, N, 2).any(axis=(1, 3))
    m = cell_below & cell_near
    return {(int(ix), int(iz)) for iz, ix in zip(*m.nonzero())}


def _nearest(sources, targets):
    """{target cell: source area} by chessboard distance; sources is {(ix, iz): area}. Ties break by the order of
    the eight neighbours, so the plan is the same on every run."""
    import numpy as np
    if not sources:
        raise CoverError("no source cells to fill from")
    lab = np.full((N, N), -1, dtype=np.int32)
    names = sorted(set(sources.values()))
    ids = {a: i for i, a in enumerate(names)}
    for (ix, iz), a in sources.items():
        lab[iz, ix] = ids[a]
    shifts = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    while (lab < 0).any():
        new = lab.copy()
        for dz, dx in shifts:
            sh = np.full_like(lab, -1)
            zs, xs = slice(max(dz, 0), N + min(dz, 0)), slice(max(dx, 0), N + min(dx, 0))
            zd, xd = slice(max(-dz, 0), N + min(-dz, 0)), slice(max(-dx, 0), N + min(-dx, 0))
            sh[zd, xd] = lab[zs, xs]
            take = (new < 0) & (sh >= 0)
            new[take] = sh[take]
        if (new == lab).all():
            raise CoverError("the fill cannot reach every cell")
        lab = new
    return {c: names[int(lab[c[1], c[0]])] for c in targets}


def resolve(area_boxes, kinds, sea, free, wet):
    """(cede, fill): {area: {cell}} each. area_boxes {area: boxes}; kinds {area: 'band'|'subregion'}; sea the open-sea
    cells; free the spawn-free cells; wet the cells that hold any water column."""
    own = owners(area_boxes)
    cede, fill = {}, {}
    chosen = {}
    for c, who in own.items():
        if c in free:
            raise CoverError("area(s) %s reach spawn-free cell %s: compile_spawns cuts those out" % (who, c))
        if len(who) == 1:
            chosen[c] = who[0]
            continue
        want = "band" if c in sea else "subregion"
        pref = [a for a in who if kinds[a] == want] or who
        chosen[c] = pref[0]
        for a in who:
            if a != chosen[c]:
                cede.setdefault(a, set()).add(c)
    gaps = sorted(c for c in wet if c not in own and c not in free)
    for want, label in (("band", SEA), ("subregion", FRESH)):
        src = {c: a for c, a in chosen.items() if kinds[a] == want}
        tgt = [c for c in gaps if (c in sea) == (label == SEA)]
        if tgt:
            for c, a in _nearest(src, tgt).items():
                fill.setdefault(a, set()).add(c)
    return cede, fill


def plan(ground=None, areas=None):
    """The full record data/fishing_fill.json holds."""
    import compile_spawns as C
    spawns = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    regions = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    routes = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))
    areas = areas or C.fishing_areas(spawns, regions, routes, C.waterway_boxes(), C.SUBREGION_GRID)
    kinds = {a: ("band" if k == "marine" else "subregion") for a, (k, _) in areas.items()}
    boxes = {a: b for a, (_, b) in areas.items()}
    free = free_cells(C.spawn_free_zones())
    sea = sea_cells(ground)
    wet = wet_cells(water_columns(ground))
    cede, fill = resolve(boxes, kinds, sea, free, wet)
    doc = {
        "schema": SCHEMA,
        "status": "derived",
        "generator": "python tools/fishing_cover.py plan",
        "why": "the owner, 2026-10-22: no player gets a Pokemon the area should not have. See the module docstring of "
               "tools/fishing_cover.py and docs/mechanics/FISHING.md section 4b.",
        "rule": "every 32-block cell of the playable world (-1024..9215) except those a spawn-free zone touches belongs to "
                "exactly one fishing area. cede: cells two areas covered go to the sea band when they hold open sea, else "
                "the sub-region (the loser lists them here). fill: cells no area covered go to the nearest sea band "
                "(open-sea cells) or the nearest sub-region with a fishing list (all others), chessboard distance.",
        "grid": GRID, "world": [WORLD_MIN, WORLD_MAX],
        "areas_planned_over": len(boxes),
        "cede": {a: [list(b) for b in cells_to_boxes(cs)] for a, cs in sorted(cede.items())},
        "fill": {a: [list(b) for b in cells_to_boxes(cs)] for a, cs in sorted(fill.items())},
        "totals": {"ceded_cells": sum(len(v) for v in cede.values()), "filled_cells": sum(len(v) for v in fill.values()),
                   "fill_boxes": sum(len(cells_to_boxes(v)) for v in fill.values()),
                   "cede_boxes": sum(len(cells_to_boxes(v)) for v in cede.values()),
                   "filled_sea_cells": sum(1 for v in fill.values() for c in v if c in sea),
                   "free_cells": len(free)},
    }
    return doc


# ------------------------------------------------------------------------------------------------ applying it


def load(path=None):
    p = Path(path) if path else FILL
    if not p.is_file():
        raise CoverError("%s is missing: run python tools/fishing_cover.py plan" % p)
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise CoverError("%s: schema %r, expected %s" % (p, doc.get("schema"), SCHEMA))
    return doc


def apply(area_boxes, doc):
    """{area: boxes} after the fill file: ceded cells cut out, filled cells added. Fails closed on a stale file (a ceded
    cell the area does not hold, a filled cell it already holds, a named area that has no list)."""
    out = {}
    for a in list(doc["cede"]) + list(doc["fill"]):
        if a not in area_boxes:
            raise CoverError("data/fishing_fill.json names %s, which has no fishing list: re-run tools/fishing_cover.py plan" % a)
    for area, boxes in area_boxes.items():
        gone = set()
        for b in doc["cede"].get(area, []):
            gone |= box_cells(tuple(b))
        add = set()
        for b in doc["fill"].get(area, []):
            add |= box_cells(tuple(b))
        held = set()
        keep = []
        for b in boxes:
            cs = box_cells(b)
            held |= cs
            hit = cs & gone
            if hit:
                keep.extend(cells_to_boxes(cs - hit))
            else:
                keep.append(tuple(b))
        if gone - held:
            raise CoverError("data/fishing_fill.json cedes cells %s does not hold: stale, re-run tools/fishing_cover.py plan" % area)
        if add & held:
            raise CoverError("data/fishing_fill.json fills cells %s already holds: stale, re-run tools/fishing_cover.py plan" % area)
        out[area] = sorted(keep + cells_to_boxes(add))
    return out


def overlaps(area_boxes, zones):
    """(multiply covered {cell: [areas]}, fishing cells inside a spawn-free zone). Independent of how the boxes came
    about: it reads only the boxes."""
    own = owners(area_boxes)
    free = free_cells(zones)
    return {c: w for c, w in own.items() if len(w) > 1}, sorted(c for c in own if c in free)


def verify_exclusive(area_boxes, zones):
    """Fail closed unless no cell has two fishing tables and none lies in a spawn-free zone. Needs no heightmap, so
    compile_spawns runs it; that every WATER cell has a table is checked against the heightmap (check_water)."""
    multi, inside_free = overlaps(area_boxes, zones)
    problems = []
    if multi:
        problems.append("%d cells belong to two fishing areas (first %s)" % (len(multi), sorted(multi.items())[:2]))
    if inside_free:
        problems.append("%d fishing cells lie in a spawn-free zone" % len(inside_free))
    if problems:
        raise CoverError("fishing cover is not exclusive: %s; re-run python tools/fishing_cover.py plan" % "; ".join(problems))


def uncovered_water(area_boxes, wet, zones):
    """The water cells (a set from wet_cells) no area holds and no spawn-free zone touches."""
    own = owners(area_boxes)
    free = free_cells(zones)
    return sorted(c for c in wet if c not in own and c not in free)


# ------------------------------------------------------------------------------------------------ measuring


def water_columns(ground=None):
    """Boolean [z, x] over the playable square: sea (round(h) < sea level, the margin included) or a painted lake
    (tools/water_mask.py basins). Rivers are not in it (their water is in the sub-regions' cells either way)."""
    import numpy as np
    import ground as G
    import water_mask as WM
    from PIL import Image, ImageDraw
    g = ground or G.load()
    side = N * GRID
    h = np.zeros((side, side), dtype=np.float32)               # the margin is sea: ground 0
    hh = np.round(g.heights).astype(np.float32)
    oz, ox = g.oz - WORLD_MIN, g.ox - WORLD_MIN
    h[oz:oz + hh.shape[0], ox:ox + hh.shape[1]] = hh
    wet = h < WM.sea_level()
    for b in WM.bodies().values():
        if not b["basin"]:
            continue
        img = Image.new("L", (side, side), 0)
        d = ImageDraw.Draw(img)
        for ring in b["basin"]:
            d.polygon([(q[0] - WORLD_MIN, q[1] - WORLD_MIN) for q in ring], fill=1)
        wet |= np.asarray(img).astype(bool) & (h < b["level_y"])
    wet |= river_columns(side)
    return wet


def river_columns(side):
    """Boolean [z, x]: the channel of every graded river course (data/rivers.json), a disc of half the reach's width
    round each station, as tools/paint_maps.py paint_rivers stamps it. A lake reach (water_body) is the lake's own."""
    import math
    import numpy as np
    import grade_rivers as GR
    doc = json.loads((ROOT / "data" / "rivers.json").read_text(encoding="utf-8"))
    cut = set((doc.get("cut") or {}).get("courses_cut", []))
    out = np.zeros((side, side), dtype=bool)
    for c in doc["courses"]:
        if c["id"] not in cut:
            continue
        pts, chain = GR.densify_chained(c["graded_polyline"])
        for (x, z, _s, _f), ch in zip(pts[::2], chain[::2]):
            r = GR.at_chainage(c["reaches"], ch)
            if r["water_body"]:
                continue
            hw = r["width"] / 2.0 + 1
            x0, x1 = int(math.floor(x - hw)) - WORLD_MIN, int(math.ceil(x + hw)) - WORLD_MIN + 1
            z0, z1 = int(math.floor(z - hw)) - WORLD_MIN, int(math.ceil(z + hw)) - WORLD_MIN + 1
            x0, z0, x1, z1 = max(x0, 0), max(z0, 0), min(x1, side), min(z1, side)
            zz, xx = np.mgrid[z0:z1, x0:x1]
            out[z0:z1, x0:x1] |= np.hypot(xx + WORLD_MIN - x, zz + WORLD_MIN - z) <= hw
    return out


def wet_cells(wet):
    """{(ix, iz)} of the 32-block cells holding any water column of the [z, x] mask."""
    m = wet.reshape(N, GRID, N, GRID).any(axis=(1, 3))
    return {(int(ix), int(iz)) for iz, ix in zip(*m.nonzero())}


def count_by_owners(area_boxes, wet, zones):
    """{owner count: water columns} where the owner count is how many areas hold the column's cell; spawn-free cells
    are their own key 'free'."""
    import numpy as np
    own = owners(area_boxes)
    cnt = np.zeros((N, N), dtype=np.int16)
    for (ix, iz), w in own.items():
        if 0 <= ix < N and 0 <= iz < N:
            cnt[iz, ix] = len(w)
    free = np.zeros((N, N), dtype=bool)
    for ix, iz in free_cells(zones):
        free[iz, ix] = True
    per_cell = wet.reshape(N, GRID, N, GRID).sum(axis=(1, 3))
    out = {}
    for k in (0, 1, 2):
        out[k] = int(per_cell[(cnt == k) & ~free].sum())
    out["more"] = int(per_cell[(cnt > 2) & ~free].sum())
    out["free"] = int(per_cell[free].sum())
    return out


def measure():
    import compile_spawns as C
    spawns = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    regions = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    routes = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))
    areas = C.fishing_areas(spawns, regions, routes, C.waterway_boxes(), C.SUBREGION_GRID)
    before = {a: b for a, (_, b) in areas.items()}
    after = apply(before, load())
    zones = C.spawn_free_zones()
    wet = water_columns()
    print("water columns (sea, painted lakes, river channels): %d" % wet.sum())
    for label, ab in (("before", before), ("after ", after)):
        c = count_by_owners(ab, wet, zones)
        print("%s: no table %d, exactly one %d, two %d, more %d, in a spawn-free cell %d"
              % (label, c[0], c[1], c[2], c["more"], c["free"]))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=("plan", "check", "measure"))
    a = p.parse_args(argv)
    if a.cmd == "measure":
        return measure()
    doc = plan()
    text = json.dumps(doc, indent=1) + "\n"
    if a.cmd == "check":
        cur = FILL.read_text(encoding="utf-8") if FILL.is_file() else ""
        if cur != text:
            print("data/fishing_fill.json is not what plan writes today: run python tools/fishing_cover.py plan")
            return 1
        print("data/fishing_fill.json is current: %s" % doc["totals"])
        return 0
    FILL.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %s: %s" % (FILL, doc["totals"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
