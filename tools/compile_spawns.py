#!/usr/bin/env python
"""Compile data/spawns.json and data/routes.json into Cobblemon 1.8 spawn and Habitat pool files.

data/spawns.json is the authored source (rosters, buckets, weights, level bands, eligibility). data/routes.json holds
the derived route boxes and the geography intervals along each route. This tool only translates: every decision is
already in those two files.

Route files (spawn_pool_world/routes/<route>.json), per spawns.json compilation.box_assignment:
  - sample the stored (simplified) route polyline every 4 blocks; a sample's sub-region is the geography interval its
    distance falls in; a sample in a recorded polygon gap takes the nearest adjacent sub-region along the route
  - a box receives one biome-constrained entry set for every sub-region its samples fall in, sub-regions sorted by id
  - a box no sample falls in takes the sub-region of the nearest polyline segment
  - an entry is every ambient spawns.json entry scoped to that sub-region, with its biomes and conditions

Sub-region files (spawn_pool_world/subregions/<sub>.json): every ambient entry scoped to the sub-region over its
polygon, corridor excluded; an entry carrying a "heart" (docs/mechanics/ENCOUNTER_DESIGN.md section 10) only over the
heart's cells (heart_boxes), and never in a route file. A heart entry with "alpha" true compiles as a native alpha
(heart_pokemon: "<species> alpha=true"), in sub-region, waterway and marine files alike. An entry carrying
"held_items" compiles them as the spawn detail's heldItems (held_items()) in route, sub-region, waterway and marine
files alike, never in a habitat pool.

Habitat files (habitat_pools/<habitat>.json): every ambient entry scoped to the habitat.

The Mega field's dens (data/gulch_mine.json mega_field.families, 2026-10-05): each den's evolution line, plain and
catchable, over a box round its anchor, appended to the file of the sub-region holding the anchor (mega_den_spawns).

Marine files (spawn_pool_world/marine/<band>.json), from spawns.json marine_zones: open sea no sub-region, route or
waterway covers, split into bands by distance from land (marine_bands below); every ambient entry scoped to a band
(mechanism marine_coordinate_boxes). The first is the Windward Sea off Route 1 (2026-09-26).

  python tools/compile_spawns.py                          # write build/datapacks/cobblers_spawns
  python tools/compile_spawns.py --out <dir>              # write elsewhere
  python tools/compile_spawns.py --routes <routes.json> --check <dir>   # compare with an existing compilation

Ownership: the output is generated and lives in build/ (gitignored); data/spawns.json and data/routes.json are the
source. Until 2026-09-16 a hand-committed copy lived in data/cobblemon/ with no generator; on the routes it was built
from, this tool reproduces its Habitat files and pack.mcmeta byte for byte and 6,479 of its 6,526 route entries (the
rest are 15 of 1,269 boxes on sub-region boundaries, a sampling detail that was never recorded). Each route's species
list (at most 20) is authored in spawns.json route_species_selection; this tool never chooses species.

Not installed live. Inherited-pool suppression is a separate generator, tools/suppress_inherited_spawns.py (EXP-012). Habitat
files define rosters only; placing Habitat Blocks and their ReplaceSpawns NBT is world work (EXP-021).

Schema evidence: the route key set was checked against Cobblemon 1.8 SpawningCondition.class and stock
data/cobblemon/spawn_pool_world/*.json; the Habitat key set against stock data/cobblemon/habitat_pools/abandoned_fortress.json,
abandoned_village_house.json, HabitatPool.class and HabitatSpawn.class in Cobblemon-fabric-1.8.0+1.21.1.jar (sha256
a6228f3291c70ed6348b9a47beadabc79cb241b6522312e7e2b56d428dc9ec31). That verifies field names, not loading or behaviour.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import subregion_boxes
import waterways as waterways_mod

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_spawns"
PACK_MCMETA = {"pack": {"pack_format": 48, "description": "Cobblers compiled encounter candidates (not runtime-proven)"}}
SAMPLE_STEP = 4.0
SUBREGION_GRID = 32
WATERWAY_GRID = 16
MARINE_GRID = 32
OVERWORLD = "minecraft:overworld"


def dumps(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def box_condition(min_x, max_x, min_z, max_z, entry):
    """The spawn condition for one box: the box, the entry's biomes, then whatever it authored.

    An entry with no biomes leaves the key out rather than sending an empty list, which would match
    no biome at all. The waterway rosters rely on that: a creek is defined by its water, not its biome.

    canSeeSky is forced only on entries that stand on land or on the water's surface. Cobblemon 1.8.0 takes a
    column's sky flag once, at the top of the spawning zone around the player (see marine_condition), so under a
    deep lake it is false and a forced canSeeSky empties every submerged and seafloor entry: on staging
    2026-09-26 /checkspawn on the floor of Lake Viltri and Shrew Lake found nothing at all.

    Nor is it forced on an entry bound off the overworld (open_sky_forced): under the Nether's roof no column sees the
    sky, so a forced canSeeSky empties every grounded Nether entry (review N154).
    """
    cond = {"minX": min_x, "maxX": max_x, "minZ": min_z, "maxZ": max_z}
    if open_sky_forced(entry):
        cond["canSeeSky"] = True
    if entry.get("biomes"):
        cond["biomes"] = list(entry["biomes"])
    cond.update(entry.get("conditions") or {})
    return cond


def open_sky_forced(entry):
    """Whether box_condition adds canSeeSky true: a land or surface entry on the overworld only.

    The dimension is read from the entry's own conditions.dimensions, the Cobblemon 1.8.0 SpawningCondition field
    (a list of dimension ids; an empty or absent list restricts nothing; docs/research/notes/
    spawn-dimension-condition-1.8.0.md). An entry with no dimensions is an overworld entry, as every one compiled
    before 2026-10-08 was, and keeps the sky. An entry whose dimensions name anything but minecraft:overworld (the
    Nether, the End, or an empty list, which Cobblemon reads as every dimension) gets no forced sky; it may still
    author canSeeSky in its conditions."""
    if position_type(entry) in ("submerged", "seafloor"):
        return False
    dims = (entry.get("conditions") or {}).get("dimensions")
    if dims is None:
        return True
    if not isinstance(dims, list) or not all(isinstance(d, str) and ":" in d for d in dims):
        raise SystemExit("%s: conditions.dimensions must be a list of dimension ids, not %r" % (entry.get("species"), dims))
    return bool(dims) and set(dims) == {OVERWORLD}


def heart_pokemon(entry):
    """The PokemonProperties string of a heart entry: the species, plus alpha=true when the entry carries "alpha"
    (data/encounter_design.json rules.hearts.alpha; the owner, 2026-10-05: "the boss pokemon are alphas").

    alpha is a PokemonProperties key in Cobblemon 1.8.0 (PokemonProperties$Companion registers "alpha" and
    "is_alpha"), and the jar's own alpha spawns write it this way in the pokemon string, e.g.
    data/cobblemon/spawn_pool_world/herds/0023_fearow_alpha.json "fearow held_item=cobblemon:flying_gem alpha=true"
    (Cobblemon-fabric-1.8.0+1.21.1.jar). tools/build_encounters.py fails closed on a heart entry without the flag."""
    return entry["species"] + (" alpha=true" if entry.get("alpha") is True else "")


def held_items(entry):
    """{"heldItems": [...]} for an entry carrying held_items (tools/build_encounters.py stamps them from
    data/encounter_design.json rules.held_items; the owner, 2026-10-05: wild held items, a find and not a farm), else {}.

    heldItems is the Cobblemon 1.8.0 PokemonSpawnDetail field (List<PossibleHeldItem>, each {"item", "percentage"},
    read through PossibleHeldItemAdapter); createSpawnAction gives no item with chance 1 - sum(percentage) / 100.
    Verified from the jar's bytecode, not in game. Written on spawn_pool_world details only: a habitat pool spawn and a
    Mega field den row (mega_den_spawns, from data/gulch_mine.json) never carry one."""
    hs = entry.get("held_items")
    if not hs:
        return {}
    return {"heldItems": [{"item": h["item"], "percentage": h["percentage"]} for h in hs]}


def position_type(entry):
    """Where the spawn is allowed to stand.

    Until 2026-09-17 every compiled entry said "grounded", so the 28 authored species that never
    spawn on dry land upstream (Magikarp, Gyarados, Basculin, Goldeen, Barboach, Whiscash, Shellder,
    Surskit and the rest) were asked to stand on the ground and never appeared. The value is authored
    per entry in data/spawns.json as spawnable_position; tools/position_types.py derives it from the
    installed Cobblemon jar.
    """
    return entry.get("spawnable_position") or "grounded"


def interval_subregions(route):
    """[(start, end, [subregions], is_gap)] in route order."""
    tr = route["geography"]["transitions"]
    return [(t["at_distance_blocks"], tr[i + 1]["at_distance_blocks"] if i + 1 < len(tr) else float("inf"),
             list(t["subregions"]), not t["subregions"]) for i, t in enumerate(tr)]


def subregions_at(intervals, d):
    """(subregions, is_gap) at distance d; inside a recorded gap, the nearer adjacent interval's sub-regions."""
    i = 0
    for k, iv in enumerate(intervals):
        if iv[0] <= d + 1e-9:
            i = k
        else:
            break
    start, end, subs, gap = intervals[i]
    if not gap:
        return subs, False
    prev = next((intervals[j] for j in range(i - 1, -1, -1) if not intervals[j][3]), None)
    nxt = next((intervals[j] for j in range(i + 1, len(intervals)) if not intervals[j][3]), None)
    if prev and (nxt is None or d - start <= end - d):
        return prev[2], True
    return (nxt[2] if nxt else []), True


def samples(polyline, mode="segment"):
    """Points along the polyline every SAMPLE_STEP blocks, restarting at each vertex ("segment") or continuous."""
    pts = [(p["x"], p["z"], p["at_distance_blocks"]) for p in polyline]
    out = []
    if mode == "segment":
        for (x0, z0, d0), (x1, z1, d1) in zip(pts, pts[1:]):
            seg = math.hypot(x1 - x0, z1 - z0)
            n = max(1, int(math.ceil(seg / SAMPLE_STEP)))
            for k in range(n):
                t = k / n
                out.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, d0 + (d1 - d0) * t))
        out.append(pts[-1])
        return out
    d, total, k = 0.0, pts[-1][2], 0
    while d <= total + 1e-9:
        while k + 1 < len(pts) - 1 and pts[k + 1][2] < d:
            k += 1
        (x0, z0, d0), (x1, z1, d1) = pts[k], pts[k + 1]
        t = (d - d0) / (d1 - d0) if d1 > d0 else 0.0
        out.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, d))
        d += SAMPLE_STEP
    if out[-1][2] < total:
        out.append(pts[-1])
    return out


def seg_point(px, pz, a, b):
    ax, az, ad = a
    bx, bz, bd = b
    dx, dz = bx - ax, bz - az
    den = dx * dx + dz * dz
    t = 0 if not den else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / den))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz)), ad + (bd - ad) * t


def spawn_free_zones(doc=None):
    """[(minX, maxX, minZ, maxZ)] where no wild Pokemon spawns at all (data/spawn_suppression.json
    spawn_free_zones). The League precinct is the first: nothing wanders the champion's forecourt."""
    if doc is None:
        path = ROOT / "data" / "spawn_suppression.json"
        doc = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return [(z["box"][0], z["box"][2], z["box"][1], z["box"][3]) for z in doc.get("spawn_free_zones") or []]


def subtract(box, zones):
    """The parts of an inclusive (minX, maxX, minZ, maxZ) box outside every zone, as up to four boxes a zone."""
    parts = [box]
    for zx0, zx1, zz0, zz1 in zones:
        nxt = []
        for x0, x1, z0, z1 in parts:
            if x1 < zx0 or x0 > zx1 or z1 < zz0 or z0 > zz1:
                nxt.append((x0, x1, z0, z1))
                continue
            if z0 < zz0:
                nxt.append((x0, x1, z0, zz0 - 1))
            if z1 > zz1:
                nxt.append((x0, x1, zz1 + 1, z1))
            mz0, mz1 = max(z0, zz0), min(z1, zz1)
            if x0 < zx0:
                nxt.append((x0, zx0 - 1, mz0, mz1))
            if x1 > zx1:
                nxt.append((zx1 + 1, x1, mz0, mz1))
        parts = nxt
    return parts


def compile_route(route, entries_by_scope, allowed=None, zones=()):
    intervals = interval_subregions(route)
    boxes = route["spawn_scope"]["boxes"]
    smp = samples(route["corridor"]["polyline"])
    assigned = {b["id"]: [] for b in boxes}
    gap_boxes, fallback = set(), 0
    for x, z, d in smp:
        subs, gap = subregions_at(intervals, d)
        for b in boxes:
            if b["min_x"] <= x <= b["max_x"] and b["min_z"] <= z <= b["max_z"]:
                if gap:
                    gap_boxes.add(b["id"])
                for s in subs:
                    if s not in assigned[b["id"]]:
                        assigned[b["id"]].append(s)
    pts = [(p["x"], p["z"], p["at_distance_blocks"]) for p in route["corridor"]["polyline"]]
    for b in boxes:
        if assigned[b["id"]]:
            continue
        cx, cz = (b["min_x"] + b["max_x"]) / 2, (b["min_z"] + b["max_z"]) / 2
        _, d = min((seg_point(cx, cz, u, v) for u, v in zip(pts, pts[1:])), key=lambda q: q[0])
        subs, gap = subregions_at(intervals, d)
        if gap:
            gap_boxes.add(b["id"])
        assigned[b["id"]] = list(subs)
        fallback += 1
    spawns, species, memberships = [], set(), {}
    for b in boxes:
        for s in sorted(assigned[b["id"]]):
            memberships[s] = memberships.get(s, 0) + 1
            for e in entries_by_scope.get(s, []):
                if allowed is not None and e["species"] not in allowed:
                    continue
                pieces = subtract((b["min_x"], b["max_x"], b["min_z"], b["max_z"]), zones)
                for k, (x0, x1, z0, z1) in enumerate(pieces):
                    cond = box_condition(x0, x1, z0, z1, e)
                    cond.update(e.get("conditions") or {})
                    sid = "%s_%s_%s" % (b["id"], s, e["species"]) if len(pieces) == 1 and pieces[0] == (b["min_x"], b["max_x"], b["min_z"], b["max_z"]) \
                        else "%s_p%d_%s_%s" % (b["id"], k, s, e["species"])
                    spawns.append({"id": sid, "pokemon": e["species"], "type": "pokemon",
                                   "spawnablePositionType": position_type(e), "bucket": e["bucket"], "level": e["level"],
                                   "weight": e["weight"], "condition": cond, **held_items(e)})
                    species.add(e["species"])
    doc = {"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [], "spawns": spawns}
    summary = {"route_id": route["id"], "source_box_count": len(boxes), "compiled_entry_count": len(spawns),
               "route_species_count": len(species), "route_species": sorted(species),
               "output": "spawn_pool_world/routes/%s.json" % route["id"],
               "subregion_box_memberships": dict(sorted(memberships.items())),
               "multi_subregion_boxes": sum(1 for v in assigned.values() if len(v) > 1),
               "recorded_gap_boxes": len(gap_boxes), "simplified_centreline_fallback_boxes": fallback}
    return doc, summary


def box_gap(a, b):
    """The Chebyshev gap between two inclusive (minX, maxX, minZ, maxZ) boxes, 0 where they overlap."""
    dx = max(0, a[0] - b[1], b[0] - a[1])
    dz = max(0, a[2] - b[3], b[2] - a[3])
    return max(dx, dz)


def heart_boxes(sub, heart, grid, exclude, waterways=()):
    """World-space boxes of a sub-region's heart (docs/mechanics/ENCOUNTER_DESIGN.md section 10).

    The heart's cells are the sub-region's own cells after the same exclusions as its roster (corridor by centre,
    waterway and spawn-free zone by any overlap), minus every cell within heart["clear_of_path_blocks"] of a route
    corridor box (Chebyshev gap, as section 1 measures "within 128 blocks of a route"), so the band beside the path
    keeps the base table alone; a focus heart further keeps only the cells whose centre lies within heart["radius"] of
    (heart["x"], heart["z"]). A summit heart keeps every remaining cell: its height line is the entries' minY.
    """
    cells, x0, z0, _, _ = subregion_boxes.rasterise(sub["polygons"], grid)
    if exclude:
        cells -= subregion_boxes.covered_by(cells, x0, z0, grid, exclude)
    if waterways:
        cells -= subregion_boxes.covered_by(cells, x0, z0, grid, waterways, whole_cell=True)
    import numpy as np
    clear = heart.get("clear_of_path_blocks") or 0
    cand = []
    for ix, iz in sorted(cells):
        cx0, cz0 = x0 + ix * grid, z0 + iz * grid
        if heart["kind"] == "focus" and math.hypot(cx0 + grid / 2.0 - heart["x"], cz0 + grid / 2.0 - heart["z"]) > heart["radius"]:
            continue
        cand.append((ix, iz))
    keep = set(cand)
    if clear and cand and exclude:
        # box_gap for every candidate cell against every corridor box at once
        c = np.array([(x0 + ix * grid, x0 + ix * grid + grid - 1, z0 + iz * grid, z0 + iz * grid + grid - 1)
                      for ix, iz in cand], dtype=np.int64)
        b = np.array([bx[:4] for bx in exclude], dtype=np.int64)
        dx = np.maximum(0, np.maximum(c[:, None, 0] - b[None, :, 1], b[None, :, 0] - c[:, None, 1]))
        dz = np.maximum(0, np.maximum(c[:, None, 2] - b[None, :, 3], b[None, :, 2] - c[:, None, 3]))
        near = (np.maximum(dx, dz) <= clear).any(axis=1)
        keep = {cell for cell, n in zip(cand, near.tolist()) if not n}
    return sorted((int(x0 + ix0 * grid), int(x0 + (ix1 + 1) * grid - 1), int(z0 + iz0 * grid), int(z0 + (iz1 + 1) * grid - 1))
                  for ix0, ix1, iz0, iz1 in subregion_boxes.merge_rectangles(keep))


def focus_heart_boxes(boxes, heart, grid, corridor, whole_boxes=False):
    """The heart of a marine band or a waterway (the owner, 2026-10-05: "every area should have a rare, ultra rare,
    and boss table"; docs/mechanics/ENCOUNTER_DESIGN.md section 10): a subset of the area's own base boxes, so a
    heart's entries ADD to the base roster there. A focus heart keeps the grid cells (whole_boxes: the boxes) whose
    centre lies within heart["radius"] of (heart["x"], heart["z"]) and whose Chebyshev gap to every route corridor box
    exceeds heart["clear_of_path_blocks"] -- section 10's 128 blocks, so the band beside the path stays the base
    table. Only a focus heart is defined here; a summit line has no meaning at sea or along a creek."""
    import numpy as np
    if heart.get("kind") != "focus":
        raise SystemExit("a marine or waterway heart is kind focus, not %r" % heart.get("kind"))
    clear = heart.get("clear_of_path_blocks") or 0
    b = np.array([c[:4] for c in corridor], dtype=np.int64) if corridor else np.zeros((0, 4), dtype=np.int64)

    def clear_of_path(x0, x1, z0, z1):
        if not len(b):
            return True
        dx = np.maximum(0, np.maximum(x0 - b[:, 1], b[:, 0] - x1))
        dz = np.maximum(0, np.maximum(z0 - b[:, 3], b[:, 2] - z1))
        return bool((np.maximum(dx, dz) > clear).all())

    def near_focus(x0, x1, z0, z1):
        return math.hypot((x0 + x1 + 1) / 2.0 - heart["x"], (z0 + z1 + 1) / 2.0 - heart["z"]) <= heart["radius"]

    if whole_boxes:
        return [bx for bx in boxes if near_focus(*bx[:4]) and clear_of_path(*bx[:4])]
    cells = set()
    for x0, x1, z0, z1 in boxes:
        for cx in range(x0, x1 + 1, grid):
            for cz in range(z0, z1 + 1, grid):
                cell = (cx, min(cx + grid - 1, x1), cz, min(cz + grid - 1, z1))
                if near_focus(*cell) and clear_of_path(*cell):
                    cells.add((cx // grid, cz // grid))
    return sorted((int(ix0 * grid), int((ix1 + 1) * grid - 1), int(iz0 * grid), int((iz1 + 1) * grid - 1))
                  for ix0, ix1, iz0, iz1 in subregion_boxes.merge_rectangles(cells))


def one_heart(area, hearts):
    geoms = {json.dumps(e["heart"], sort_keys=True) for e in hearts}
    if len(geoms) != 1:
        raise SystemExit("%s: heart entries disagree on the heart's geometry: %s" % (area, sorted(geoms)))
    return hearts[0]["heart"]


def compile_subregion(sub, entries, exclude, grid, waterways=()):
    """A sub-region's roster over its own polygon, minus the route corridor boxes.

    Until 2026-09-17 a roster reached the world only where a route corridor passed through it, so 35
    of 71 sub-regions compiled to nothing. The corridor cells are excluded rather than overlaid: both
    tables would otherwise spawn in the same place and double the weights.

    An entry carrying a "heart" (tools/build_encounters.py, ENCOUNTER_DESIGN.md section 10) is laid over the heart's
    boxes only (heart_boxes), on top of the base roster there, with ids <sub>_h<n>_<species>; a table without one
    compiles exactly as before.
    """
    base = [e for e in entries if not e.get("heart")]
    hearts = [e for e in entries if e.get("heart")]
    boxes = subregion_boxes.boxes_for(sub["polygons"], grid, exclude, waterways)
    spawns = []
    for n, b in enumerate(boxes):
        for e in base:
            cond = box_condition(b[0], b[1], b[2], b[3], e)
            spawns.append({"id": "%s_b%04d_%s" % (sub["id"], n, e["species"].replace(" ", "_")), "pokemon": e["species"],
                           "type": "pokemon", "spawnablePositionType": position_type(e),
                           "bucket": e["bucket"], "level": e["level"], "weight": e["weight"], "condition": cond,
                           **held_items(e)})
    hboxes = []
    if hearts:
        geoms = {json.dumps(e["heart"], sort_keys=True) for e in hearts}
        if len(geoms) != 1:
            raise SystemExit("%s: heart entries disagree on the heart's geometry: %s" % (sub["id"], sorted(geoms)))
        hboxes = heart_boxes(sub, hearts[0]["heart"], grid, exclude, waterways)
        for n, b in enumerate(hboxes):
            for e in hearts:
                cond = box_condition(b[0], b[1], b[2], b[3], e)
                spawns.append({"id": "%s_h%04d_%s" % (sub["id"], n, e["species"].replace(" ", "_")), "pokemon": heart_pokemon(e),
                               "type": "pokemon", "spawnablePositionType": position_type(e),
                               "bucket": e["bucket"], "level": e["level"], "weight": e["weight"], "condition": cond,
                               **held_items(e)})
    doc = {"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [], "spawns": spawns}
    summary = {"subregion_id": sub["id"], "box_count": len(boxes), "compiled_entry_count": len(spawns),
               "species": sorted({e["species"] for e in base}),
               "covered_blocks": subregion_boxes.area(boxes),
               "corridor_blocks_excluded": subregion_boxes.area(subregion_boxes.boxes_for(sub["polygons"], grid)) - subregion_boxes.area(boxes),
               "output": "spawn_pool_world/subregions/%s.json" % sub["id"]}
    if hearts:
        summary["heart"] = dict(hearts[0]["heart"], box_count=len(hboxes), covered_blocks=subregion_boxes.area(hboxes),
                                species=sorted({e["species"] for e in hearts}))
    return doc, summary


def compile_habitat(h, entries):
    display = {e["pokemon"]: e["species"] for e in h["entries"]}
    compiled = [e for e in entries if e["ambient"] and e["weight"] > 0]
    # the species id, never the display name: a display name is not always an id ("Farfetch'd" made the server read
    # cobblemon:farfetch'd, an invalid location, and the whole data load stopped on staging, 2026-09-26)
    # a habitat pool spawn takes a timeRange of its own (Cobblemon 1.8.0 HabitatSpawn, and the jar's own
    # habitat_pools/abandoned_village_house.json): an entry's conditions.timeRange carries through, so a night bird
    # is a night bird in a tree too.
    # A regional form ("corsola galarian") is the species plus `modifiers`: HabitatSpawn.species is a Species, not a
    # properties string, so "corsola galarian" there would be an invalid species and fail the data load; the form goes
    # in `modifiers` (a PokemonProperties), as the jar's own habitat pools write it ("modifiers": "galarian";
    # docs/research/notes/habitat-blocks-underground.md, HabitatSpawn.kt). 2026-10-05, tools/desert_wreck.py's pool.
    doc = {"name": "cobblers.habitat.%s.name" % h["id"], "type": "cobblemon:natural",
           "spawns": [dict({"species": e["species"].split()[0], "bucket": e["bucket"],
                            "spawnablePositionType": position_type(e),
                            "weight": e["weight"], "levelRange": e["level"], "phases": "1-25"},
                           **({"modifiers": " ".join(e["species"].split()[1:])} if len(e["species"].split()) > 1 else {}),
                           **({"timeRange": e["conditions"]["timeRange"]}
                              if (e.get("conditions") or {}).get("timeRange") else {})) for e in compiled]}
    compiled_names = {display.get(e["species"], e["species"]) for e in compiled}
    summary = {"habitat_id": h["id"], "authored_species_count": len(h["entries"]), "compiled_species_count": len(compiled),
               "deferred_species": [e["species"] for e in h["entries"] if e["species"] not in compiled_names and e.get("bucket") == "authored-only"],
               "output": "habitat_pools/%s.json" % h["id"]}
    return doc, summary


def build_waterways(spawns, waterways, grid=WATERWAY_GRID, routes=None):
    """A named river's roster along its centreline, thinning by the authored weight ramp.

    Boxes come from tools/waterways.py, which gives each segment its own disjoint rectangles, so a
    block is never covered twice and a weight is never doubled. An entry carrying a "heart" (focus_heart_boxes) is laid
    only over the boxes of the heart, at its authored weight (no ramp), with ids <waterway>_h<n>_<species>.
    """
    by_scope = {}
    for e in spawns["entries"]:
        if e["mechanism"] == "waterway_coordinate_boxes" and e["ambient"] and e["weight"] > 0:
            by_scope.setdefault(e["scope"], []).append(e)
    corridor = subregion_boxes.route_boxes(routes) if routes else []
    files, summaries = {}, []
    for w in waterways["waterways"]:
        allents = by_scope.get(w["id"], [])
        ents = [e for e in allents if not e.get("heart")]
        hearts = [e for e in allents if e.get("heart")]
        if not ents:
            continue
        spawns_out, boxes, all_boxes = [], 0, []
        for i, frac, bs in waterways_mod.boxes_by_segment(w["polyline"], w["half_width"], grid):
            mult = waterways_mod.ramp(w["weight_ramp"], frac)
            for n, b in enumerate(bs):
                boxes += 1
                all_boxes.append(tuple(b[:4]))
                for e in ents:
                    spawns_out.append({"id": "%s_s%03d_b%02d_%s" % (w["id"], i, n, e["species"].replace(" ", "_")),
                                       "pokemon": e["species"], "type": "pokemon",
                                       "spawnablePositionType": position_type(e),
                                       "bucket": e["bucket"], "level": e["level"],
                                       "weight": round(e["weight"] * mult, 3),
                                       "condition": box_condition(b[0], b[1], b[2], b[3], e), **held_items(e)})
        hboxes = []
        if hearts:
            hboxes = focus_heart_boxes(all_boxes, one_heart(w["id"], hearts), grid, corridor, whole_boxes=True)
            if not hboxes:
                raise SystemExit("%s: its heart covers no box clear of the path" % w["id"])
            for n, b in enumerate(hboxes):
                for e in hearts:
                    spawns_out.append({"id": "%s_h%04d_%s" % (w["id"], n, e["species"].replace(" ", "_")),
                                       "pokemon": heart_pokemon(e), "type": "pokemon",
                                       "spawnablePositionType": position_type(e),
                                       "bucket": e["bucket"], "level": e["level"], "weight": e["weight"],
                                       "condition": box_condition(b[0], b[1], b[2], b[3], e), **held_items(e)})
        doc = {"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [], "spawns": spawns_out}
        files["data/cobblers/spawn_pool_world/waterways/%s.json" % w["id"]] = dumps(doc)
        summaries.append({"waterway_id": w["id"], "box_count": boxes, "compiled_entry_count": len(spawns_out),
                          "species": sorted({e["species"] for e in ents}),
                          "weight_multiplier": [round(waterways_mod.ramp(w["weight_ramp"], 0.0), 3),
                                                round(waterways_mod.ramp(w["weight_ramp"], 1.0), 3)],
                          "output": "spawn_pool_world/waterways/%s.json" % w["id"]})
        if hearts:
            summaries[-1]["heart"] = dict(hearts[0]["heart"], box_count=len(hboxes), covered_blocks=subregion_boxes.area(hboxes),
                                          species=sorted({e["species"] for e in hearts}))
    return files, summaries


def build(spawns, routes):
    by_scope = {}
    for e in spawns["entries"]:
        # a heart entry never reaches a corridor (ENCOUNTER_DESIGN.md section 10: the path is always catchable)
        if e["mechanism"] == "spawn_json_coordinate_boxes" and e["ambient"] and e["weight"] > 0 and not e.get("heart"):
            by_scope.setdefault(e["scope"], []).append(e)
    files, route_summaries, habitat_summaries = {"pack.mcmeta": dumps(PACK_MCMETA)}, [], []
    for r in routes["routes"]:
        sel = (spawns.get("route_species_selection") or {}).get(r["id"])
        doc, summ = compile_route(r, by_scope, set(sel["species"]) if sel else None, spawn_free_zones())
        if sel:
            # an authored species the corridor no longer reaches (its sub-region left the route) compiles to nothing
            summ["selected_species_not_reached"] = sorted(set(sel["species"]) - set(summ["route_species"]))
            outside = set(summ["route_species"]) - set(sel["species"])
            if outside or set(summ["route_species"]) | set(summ["selected_species_not_reached"]) != set(sel["species"]):
                raise SystemExit("route %s compiled species outside its authored selection: %s" % (r["id"], sorted(outside)))
            summ["selection_reproduced"] = "exact: compiled species plus unreached species equal the authored list, nothing outside it"
        files["data/cobblers/spawn_pool_world/routes/%s.json" % r["id"]] = dumps(doc)
        route_summaries.append(summ)
    for h in spawns["habitats"]:
        ents = [e for e in spawns["entries"] if e["mechanism"] == "habitat_block" and e["scope"] == h["id"]]
        doc, summ = compile_habitat(h, ents)
        files["data/cobblers/habitat_pools/%s.json" % h["id"]] = dumps(doc)
        habitat_summaries.append(summ)
    return files, route_summaries, habitat_summaries


def build_subregions(spawns, routes, regions, grid=SUBREGION_GRID, waterways=()):
    """The sub-region half of the pack: every authored roster over its own polygon.

    Kept separate from build() so the route compilation keeps its shape; a sub-region file and a
    route file never cover the same block, because the corridor cells are excluded here. A waterway's
    cells are excluded the same way, so the water's edge belongs to the river's roster alone and the
    forest around it does not dilute it.
    """
    by_scope = {}
    for e in spawns["entries"]:
        if e["mechanism"] == "spawn_json_coordinate_boxes" and e["ambient"] and e["weight"] > 0:
            by_scope.setdefault(e["scope"], []).append(e)
    corridor = subregion_boxes.route_boxes(routes)
    # a spawn-free zone takes every cell it touches, as a waterway does: excluded by centre, a 32-block cell
    # overlapping the League zone's edge by 8 blocks kept its roster (80 details on the first compile)
    waterways = list(waterways) + spawn_free_zones()
    files, summaries = {}, []
    subs = {s["id"]: s for s in regions["subregions"]}
    dens, den_summ = mega_den_spawns(regions, corridor, spawns,
                                     base_boxes=lambda sid: subregion_boxes.boxes_for(subs[sid]["polygons"], grid, corridor, waterways))
    for sub in regions["subregions"]:
        ents = by_scope.get(sub["id"], [])
        extra = dens.get(sub["id"], [])
        if not ents and not extra:
            continue
        if ents:
            doc, summ = compile_subregion(sub, ents, corridor, grid, waterways)
        else:
            doc = {"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [], "spawns": []}
            summ = {"subregion_id": sub["id"], "box_count": 0, "compiled_entry_count": 0, "species": [],
                    "covered_blocks": 0, "corridor_blocks_excluded": 0,
                    "output": "spawn_pool_world/subregions/%s.json" % sub["id"]}
        if extra:
            # the Mega field's dens' lines (mega_den_spawns), over each den's own box, on top of the roster there
            doc["spawns"] += extra
            summ["compiled_entry_count"] += len(extra)
            summ["mega_dens"] = den_summ[sub["id"]]
        if not doc["spawns"]:
            continue
        files["data/cobblers/spawn_pool_world/subregions/%s.json" % sub["id"]] = dumps(doc)
        summaries.append(summ)
    return files, summaries


GULCH = ROOT / "data" / "gulch_mine.json"


def mega_den_spawns(regions, corridor, spawns, gulch=None, base_boxes=None):
    """({sub-region id: [spawn details]}, {sub-region id: summary}): each Mega field den's evolution line, in plain
    form and catchable, over a box round the den's anchor (data/gulch_mine.json mega_field.families, its why: the
    owner, 2026-10-05). The box is the anchor +- families.box_half, less the route corridor boxes and the spawn-free
    zones (as every sub-region roster is); the details go into the file of the sub-region whose polygon holds the
    anchor, after its own roster. A species in families.held is not compiled. Levels: inside that sub-region's
    level_band (data/spawns.json; the line is catchable, so never past the cap), the final stage its top
    families.band, each stage below (maximum - minimum - band) // (n - 1) lower; weights:
    families.family_weight split from the bottom stage up (stage k of n weighs n - k shares). Translation only: every
    number is the data's."""
    if gulch is None:
        if not GULCH.is_file():
            return {}, {}
        gulch = json.loads(GULCH.read_text(encoding="utf-8"))
    fam = (gulch.get("mega_field") or {}).get("families")
    if not fam:
        return {}, {}
    held = fam.get("held") or {}
    bands = {s["id"]: s.get("level_band") for s in spawns.get("subregions") or []}
    zones = spawn_free_zones()
    cut = list(zones) + [tuple(b[:4]) for b in corridor]
    out, summ, base_cache = {}, {}, {}
    for fa in gulch.get("farms", []):
        for d in fa["dens"]:
            ax, _ay, az = d["anchor"]
            home = [s for s in regions["subregions"]
                    if any(subregion_boxes.point_in_polygon(ax + 0.5, az + 0.5, poly) for poly in s["polygons"])]
            if not home:
                raise SystemExit("mega den %s: its anchor (%d, %d) is in no data/regions.json sub-region" % (d["id"], ax, az))
            sub = sorted(home, key=lambda s: s["id"])[0]["id"]
            h = fam["box_half"]
            boxes = subtract((ax - h, ax + h, az - h, az + h), cut)
            if base_boxes is not None:
                # only on top of the sub-region's own roster boxes (its corridor and water cells excluded whole, as
                # compile_subregion lays them): a den line never spawns where the base roster does not
                if sub not in base_cache:
                    base_cache[sub] = base_boxes(sub)
                boxes = [(max(b[0], c[0]), min(b[1], c[1]), max(b[2], c[2]), min(b[3], c[3]))
                         for b in boxes for c in base_cache[sub]
                         if max(b[0], c[0]) <= min(b[1], c[1]) and max(b[2], c[2]) <= min(b[3], c[3])]
            line = [sp for sp in fam["lines"][d["species"]] if sp not in held]
            n = len(fam["lines"][d["species"]])
            band = bands.get(sub)
            if not band:
                raise SystemExit("mega den %s: sub-region %s has no level_band in data/spawns.json" % (d["id"], sub))
            lo, hi = band["minimum"], band["maximum"]
            step = (hi - lo - fam["band"]) // (n - 1) if n > 1 else 0
            shares = n * (n + 1) / 2.0
            rows = []
            for k, sp in enumerate(fam["lines"][d["species"]]):
                if sp in held:
                    continue
                top = hi - (n - 1 - k) * step
                lv = "%d-%d" % (top - fam["band"], top)
                w = round(fam["family_weight"] * (n - k) / shares, 3)
                for bi, b in enumerate(boxes):
                    rows.append({"id": "%s_%s_b%d_%s" % (sub, d["id"], bi, sp), "pokemon": sp, "type": "pokemon",
                                 "spawnablePositionType": "grounded", "bucket": fam["bucket"], "level": lv, "weight": w,
                                 "condition": box_condition(b[0], b[1], b[2], b[3], {})})
            out.setdefault(sub, []).extend(rows)
            s = summ.setdefault(sub, {"dens": 0, "entries": 0, "species": set()})
            s["dens"] += 1
            s["entries"] += len(rows)
            s["species"] |= set(line)
    for s in summ.values():
        s["species"] = sorted(s["species"])
    return out, summ


def _grid_cells_of(sub, grid):
    """{(gx, gz)} global grid cells a sub-region's raster holds (the same raster compile_subregion uses)."""
    cells, x0, z0, _, _ = subregion_boxes.rasterise(sub["polygons"], grid)
    return {((x0 + ix * grid) // grid, (z0 + iz * grid) // grid) for ix, iz in cells}


def marine_bands(spawns, regions, routes, waterways=(), grid=MARINE_GRID):
    """{band id: [(minX, maxX, minZ, maxZ)]} for every marine zone in data/spawns.json marine_zones.

    A marine zone is open sea no sub-region roster reaches: the grid cells whose centre lies in the zone's clip box,
    minus every land sub-region's raster cell, every cell whose centre a route corridor box covers, and every cell a
    waterway or spawn-free zone touches (the same exclusions compile_subregion applies, so a marine box and a
    sub-region, route or waterway box never cover the same block and no weight doubles). Each remaining cell goes to
    the first band whose [from_blocks, to_blocks) holds its distance from land: the distance from the cell's centre to
    the nearest land sub-region cell's centre, less half a cell. The land sub-region polygons were drawn to the
    coast; measured 2026-09-26 over 3,959 Windward Sea cells (to z5199) against the heightmap coast (tools/ground.py,
    heightmap 0d9b5f1e, land = ground >= y62 on an 8-block raster), this distance is the coast distance within
    -20 / 0 / +41 blocks at p5 / p50 / p95, so the bands need no heightmap at compile time.
    """
    zones = spawns.get("marine_zones") or []
    if not zones:
        return {}
    import numpy as np
    land = set()
    for sub in regions["subregions"]:
        land |= _grid_cells_of(sub, grid)
    corridor = subregion_boxes.route_boxes(routes)
    narrow = list(waterways) + spawn_free_zones()
    out = {}
    for zone in zones:
        x0, x1, z0, z1 = zone["clip_box"]["min_x"], zone["clip_box"]["max_x"], zone["clip_box"]["min_z"], zone["clip_box"]["max_z"]
        cells = []
        for gx in range(x0 // grid, x1 // grid + 1):
            for gz in range(z0 // grid, z1 // grid + 1):
                mx, mz = gx * grid + grid / 2.0, gz * grid + grid / 2.0
                if not (x0 <= mx <= x1 and z0 <= mz <= z1) or (gx, gz) in land:
                    continue
                if any(b[0] <= mx <= b[1] and b[2] <= mz <= b[3] for b in corridor):
                    continue
                cx0, cz0 = gx * grid, gz * grid
                if any(not (b[1] < cx0 or cx0 + grid - 1 < b[0] or b[3] < cz0 or cz0 + grid - 1 < b[2]) for b in narrow):
                    continue
                cells.append((gx, gz))
        bands = zone["bands"]
        reach = max(b["from_blocks"] for b in bands) + grid
        near = [(gx, gz) for gx, gz in land
                if x0 - reach <= gx * grid <= x1 + reach and z0 - reach <= gz * grid <= z1 + reach]
        by_band = {b["id"]: set() for b in bands}
        if cells:
            pts = np.array([(gx * grid + grid / 2.0, gz * grid + grid / 2.0) for gx, gz in cells])
            lp = np.array([(gx * grid + grid / 2.0, gz * grid + grid / 2.0) for gx, gz in near]) if near else None
            dist = np.full(len(cells), float("inf"))
            if lp is not None:
                for i in range(0, len(pts), 1024):
                    d = np.sqrt(((pts[i:i + 1024, None, :] - lp[None, :, :]) ** 2).sum(-1)).min(1) - grid / 2.0
                    dist[i:i + 1024] = d
            for (gx, gz), d in zip(cells, dist):
                for b in bands:
                    if b["from_blocks"] <= d < (b.get("to_blocks") if b.get("to_blocks") is not None else float("inf")):
                        by_band[b["id"]].add((gx, gz))
                        break
        for bid, bc in by_band.items():
            out[bid] = sorted((int(ix0 * grid), int((ix1 + 1) * grid - 1), int(iz0 * grid), int((iz1 + 1) * grid - 1))
                              for ix0, ix1, iz0, iz1 in subregion_boxes.merge_rectangles(bc))
    return out


def marine_condition(min_x, max_x, min_z, max_z, entry):
    """A marine spawn condition: the box and whatever the entry authored, and nothing forced.

    Unlike box_condition this does not add canSeeSky: the marine rosters spawn only in water, where there is no cave
    to keep them out of, and Cobblemon 1.8.0's CobblemonSpawningZoneGenerator records a column's sky flag once, at
    the top of the spawning zone (bytecode: the world sky test is called at IntProgression.getFirst of the zone's
    reversed Y range). Whether that flag reads true under 20 or more blocks of water is not known, and a forced
    canSeeSky could silently empty every deep entry. Surface entries author canSeeSky themselves.
    """
    cond = {"minX": min_x, "maxX": max_x, "minZ": min_z, "maxZ": max_z}
    if entry.get("biomes"):
        cond["biomes"] = list(entry["biomes"])
    cond.update(entry.get("conditions") or {})
    return cond


def build_marine(spawns, regions, routes, waterways=()):
    """The marine half of the pack: each marine band's roster over its own boxes; an entry carrying a "heart"
    (focus_heart_boxes) only over the heart's cells of the band, with ids <band>_h<n>_<species>."""
    bands = marine_bands(spawns, regions, routes, waterways)
    corridor = subregion_boxes.route_boxes(routes)
    by_scope = {}
    for e in spawns["entries"]:
        if e["mechanism"] == "marine_coordinate_boxes" and e["ambient"] and e["weight"] > 0:
            by_scope.setdefault(e["scope"], []).append(e)
    unknown = sorted(set(by_scope) - set(bands))
    if unknown:
        raise SystemExit("marine entries name bands no marine zone defines: %s" % unknown)
    files, summaries = {}, []
    for bid, boxes in sorted(bands.items()):
        allents = by_scope.get(bid, [])
        ents = [e for e in allents if not e.get("heart")]
        hearts = [e for e in allents if e.get("heart")]
        if not ents or not boxes:
            continue
        spawns_out = []
        for n, b in enumerate(boxes):
            for e in ents:
                spawns_out.append({"id": "%s_b%04d_%s" % (bid, n, e["species"].replace(" ", "_")), "pokemon": e["species"],
                                   "type": "pokemon", "spawnablePositionType": position_type(e),
                                   "bucket": e["bucket"], "level": e["level"], "weight": e["weight"],
                                   "condition": marine_condition(b[0], b[1], b[2], b[3], e), **held_items(e)})
        hboxes = []
        if hearts:
            hboxes = focus_heart_boxes(boxes, one_heart(bid, hearts), MARINE_GRID, corridor)
            if not hboxes:
                raise SystemExit("%s: its heart covers no cell of the band clear of the path" % bid)
            for n, b in enumerate(hboxes):
                for e in hearts:
                    spawns_out.append({"id": "%s_h%04d_%s" % (bid, n, e["species"].replace(" ", "_")), "pokemon": heart_pokemon(e),
                                       "type": "pokemon", "spawnablePositionType": position_type(e),
                                       "bucket": e["bucket"], "level": e["level"], "weight": e["weight"],
                                       "condition": marine_condition(b[0], b[1], b[2], b[3], e), **held_items(e)})
        doc = {"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [], "spawns": spawns_out}
        files["data/cobblers/spawn_pool_world/marine/%s.json" % bid] = dumps(doc)
        summaries.append({"band_id": bid, "box_count": len(boxes), "compiled_entry_count": len(spawns_out),
                          "species": sorted({e["species"] for e in ents}), "covered_blocks": subregion_boxes.area(boxes),
                          "output": "spawn_pool_world/marine/%s.json" % bid})
        if hearts:
            summaries[-1]["heart"] = dict(hearts[0]["heart"], box_count=len(hboxes), covered_blocks=subregion_boxes.area(hboxes),
                                          species=sorted({e["species"] for e in hearts}))
    return files, summaries


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--spawns", default=str(ROOT / "data" / "spawns.json"))
    p.add_argument("--routes", default=str(ROOT / "data" / "routes.json"))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--regions", default=str(ROOT / "data" / "regions.json"))
    p.add_argument("--grid", type=int, default=SUBREGION_GRID,
                   help="grid the sub-region polygons are rasterised on before being merged into boxes")
    p.add_argument("--waterways", default=str(ROOT / "data" / "waterways.json"))
    p.add_argument("--no-subregions", action="store_true",
                   help="compile route corridors only, as before 2026-09-17")
    p.add_argument("--check", default=None, help="compare with the compilation in this directory instead of writing")
    a = p.parse_args(argv)
    spawns = json.loads(Path(a.spawns).read_text(encoding="utf-8"))
    routes = json.loads(Path(a.routes).read_text(encoding="utf-8"))
    files, rs, hs = build(spawns, routes)
    ws, water_boxes = [], []
    if Path(a.waterways).is_file():
        waterdoc = json.loads(Path(a.waterways).read_text(encoding="utf-8"))
        waterfiles, ws = build_waterways(spawns, waterdoc, routes=routes)
        files.update(waterfiles)
        for wdef in waterdoc["waterways"]:
            for _, _, bs in waterways_mod.boxes_by_segment(wdef["polyline"], wdef["half_width"], WATERWAY_GRID):
                water_boxes.extend(bs)
        zones = spawn_free_zones()
        for rel in [r for r in files if "/waterways/" in r]:
            d = json.loads(files[rel])
            if any(subtract((s["condition"]["minX"], s["condition"]["maxX"], s["condition"]["minZ"], s["condition"]["maxZ"]), zones)
                   != [(s["condition"]["minX"], s["condition"]["maxX"], s["condition"]["minZ"], s["condition"]["maxZ"])]
                   for s in d["spawns"] if "minX" in s["condition"]):
                raise SystemExit("%s reaches into a spawn-free zone; cut the waterway short of it" % rel)
    ss, ms = [], []
    if not a.no_subregions:
        regions = json.loads(Path(a.regions).read_text(encoding="utf-8"))
        subfiles, ss = build_subregions(spawns, routes, regions, a.grid, water_boxes)
        files.update(subfiles)
        marinefiles, ms = build_marine(spawns, regions, routes, water_boxes)
        files.update(marinefiles)
    if a.check:
        base = Path(a.check)
        same = diff = missing = 0
        for rel, text in files.items():
            f = base / rel
            if not f.is_file():
                missing += 1
                print("missing", rel)
            elif f.read_bytes() == text.encode("utf-8"):
                same += 1
            else:
                diff += 1
                print("differs", rel)
        extra = [q.relative_to(base).as_posix() for q in base.rglob("*.json") if q.relative_to(base).as_posix() not in files]
        print("identical %d, different %d, missing %d, extra %s" % (same, diff, missing, extra))
        return 0 if not diff and not missing and not extra else 1
    for rel, text in sorted(files.items()):
        if "/spawn_pool_world/" not in rel:
            continue
        ids = [q.get("id") for q in json.loads(text).get("spawns") or []]
        repeated = {i for i in ids if ids.count(i) > 1}
        if repeated:
            # a file whose details share an id parses and loads in silence; it cost an in-game test
            # run on 2026-09-18 to notice. tools/validate_data.py --pack checks a written pack too.
            raise SystemExit("%s: %d spawn ids are used more than once, e.g. %s"
                             % (rel, len(repeated), sorted(repeated)[0]))
    out = Path(a.out)
    for rel, text in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    manifest = {"generator": "tools/compile_spawns.py",
                "inputs": {k: hashlib.sha256(Path(v).read_bytes()).hexdigest() for k, v in (("data/spawns.json", a.spawns), ("data/routes.json", a.routes))
                           + ((("data/gulch_mine.json", GULCH),) if GULCH.is_file() and not a.no_subregions else ())},
                "files": {rel: hashlib.sha256(text.encode("utf-8")).hexdigest() for rel, text in sorted(files.items())},
                "route_files": rs, "habitat_files": hs, "subregion_files": ss, "waterway_files": ws,
                "marine_files": ms,
                "subregion_grid": a.grid,
                "subregion_box_count": sum(q["box_count"] for q in ss),
                "subregion_spawn_entry_count": sum(q["compiled_entry_count"] for q in ss),
                "route_box_count": sum(r["source_box_count"] for r in rs), "route_spawn_entry_count": sum(r["compiled_entry_count"] for r in rs)}
    (out / "manifest.json").write_text(dumps(manifest), encoding="utf-8", newline="\n")
    print("wrote %d files to %s: %d route boxes, %d route entries, %d sub-regions, %d sub-region boxes, %d sub-region entries"
          % (len(files), out, manifest["route_box_count"], manifest["route_spawn_entry_count"],
             len(ss), manifest["subregion_box_count"], manifest["subregion_spawn_entry_count"]))
    for q in ws:
        print("  waterway %s: %d boxes, %d entries, weight x%.2f at the head to x%.2f at the mouth"
              % (q["waterway_id"], q["box_count"], q["compiled_entry_count"], *q["weight_multiplier"]))
    for q in ms:
        print("  marine %s: %d boxes, %d entries, %s blocks" % (q["band_id"], q["box_count"], q["compiled_entry_count"],
                                                            format(q["covered_blocks"], ",")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
