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

Habitat files (habitat_pools/<habitat>.json): every ambient entry scoped to the habitat.

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


def dumps(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def box_condition(min_x, max_x, min_z, max_z, entry):
    """The spawn condition for one box: the box, the entry's biomes, then whatever it authored.

    An entry with no biomes leaves the key out rather than sending an empty list, which would match
    no biome at all. The waterway rosters rely on that: a creek is defined by its water, not its biome.
    """
    cond = {"minX": min_x, "maxX": max_x, "minZ": min_z, "maxZ": max_z, "canSeeSky": True}
    if entry.get("biomes"):
        cond["biomes"] = list(entry["biomes"])
    cond.update(entry.get("conditions") or {})
    return cond


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
                                   "weight": e["weight"], "condition": cond})
                    species.add(e["species"])
    doc = {"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [], "spawns": spawns}
    summary = {"route_id": route["id"], "source_box_count": len(boxes), "compiled_entry_count": len(spawns),
               "route_species_count": len(species), "route_species": sorted(species),
               "output": "spawn_pool_world/routes/%s.json" % route["id"],
               "subregion_box_memberships": dict(sorted(memberships.items())),
               "multi_subregion_boxes": sum(1 for v in assigned.values() if len(v) > 1),
               "recorded_gap_boxes": len(gap_boxes), "simplified_centreline_fallback_boxes": fallback}
    return doc, summary


def compile_subregion(sub, entries, exclude, grid, waterways=()):
    """A sub-region's roster over its own polygon, minus the route corridor boxes.

    Until 2026-09-17 a roster reached the world only where a route corridor passed through it, so 35
    of 71 sub-regions compiled to nothing. The corridor cells are excluded rather than overlaid: both
    tables would otherwise spawn in the same place and double the weights.
    """
    boxes = subregion_boxes.boxes_for(sub["polygons"], grid, exclude, waterways)
    spawns = []
    for n, b in enumerate(boxes):
        for e in entries:
            cond = box_condition(b[0], b[1], b[2], b[3], e)
            spawns.append({"id": "%s_b%04d_%s" % (sub["id"], n, e["species"].replace(" ", "_")), "pokemon": e["species"],
                           "type": "pokemon", "spawnablePositionType": position_type(e),
                           "bucket": e["bucket"], "level": e["level"], "weight": e["weight"], "condition": cond})
    doc = {"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [], "spawns": spawns}
    summary = {"subregion_id": sub["id"], "box_count": len(boxes), "compiled_entry_count": len(spawns),
               "species": sorted({e["species"] for e in entries}),
               "covered_blocks": subregion_boxes.area(boxes),
               "corridor_blocks_excluded": subregion_boxes.area(subregion_boxes.boxes_for(sub["polygons"], grid)) - subregion_boxes.area(boxes),
               "output": "spawn_pool_world/subregions/%s.json" % sub["id"]}
    return doc, summary


def compile_habitat(h, entries):
    display = {e["pokemon"]: e["species"] for e in h["entries"]}
    compiled = [e for e in entries if e["ambient"] and e["weight"] > 0]
    # the species id, never the display name: a display name is not always an id ("Farfetch'd" made the server read
    # cobblemon:farfetch'd, an invalid location, and the whole data load stopped on staging, 2026-09-26)
    # a habitat pool spawn takes a timeRange of its own (Cobblemon 1.8.0 HabitatSpawn, and the jar's own
    # habitat_pools/abandoned_village_house.json): an entry's conditions.timeRange carries through, so a night bird
    # is a night bird in a tree too
    doc = {"name": "cobblers.habitat.%s.name" % h["id"], "type": "cobblemon:natural",
           "spawns": [dict({"species": e["species"], "bucket": e["bucket"],
                            "spawnablePositionType": position_type(e),
                            "weight": e["weight"], "levelRange": e["level"], "phases": "1-25"},
                           **({"timeRange": e["conditions"]["timeRange"]}
                              if (e.get("conditions") or {}).get("timeRange") else {})) for e in compiled]}
    compiled_names = {display.get(e["species"], e["species"]) for e in compiled}
    summary = {"habitat_id": h["id"], "authored_species_count": len(h["entries"]), "compiled_species_count": len(compiled),
               "deferred_species": [e["species"] for e in h["entries"] if e["species"] not in compiled_names and e.get("bucket") == "authored-only"],
               "output": "habitat_pools/%s.json" % h["id"]}
    return doc, summary


def build_waterways(spawns, waterways, grid=WATERWAY_GRID):
    """A named river's roster along its centreline, thinning by the authored weight ramp.

    Boxes come from tools/waterways.py, which gives each segment its own disjoint rectangles, so a
    block is never covered twice and a weight is never doubled.
    """
    by_scope = {}
    for e in spawns["entries"]:
        if e["mechanism"] == "waterway_coordinate_boxes" and e["ambient"] and e["weight"] > 0:
            by_scope.setdefault(e["scope"], []).append(e)
    files, summaries = {}, []
    for w in waterways["waterways"]:
        ents = by_scope.get(w["id"], [])
        if not ents:
            continue
        spawns_out, boxes = [], 0
        for i, frac, bs in waterways_mod.boxes_by_segment(w["polyline"], w["half_width"], grid):
            mult = waterways_mod.ramp(w["weight_ramp"], frac)
            for n, b in enumerate(bs):
                boxes += 1
                for e in ents:
                    spawns_out.append({"id": "%s_s%03d_b%02d_%s" % (w["id"], i, n, e["species"].replace(" ", "_")),
                                       "pokemon": e["species"], "type": "pokemon",
                                       "spawnablePositionType": position_type(e),
                                       "bucket": e["bucket"], "level": e["level"],
                                       "weight": round(e["weight"] * mult, 3),
                                       "condition": box_condition(b[0], b[1], b[2], b[3], e)})
        doc = {"enabled": True, "neededInstalledMods": [], "neededUninstalledMods": [], "spawns": spawns_out}
        files["data/cobblers/spawn_pool_world/waterways/%s.json" % w["id"]] = dumps(doc)
        summaries.append({"waterway_id": w["id"], "box_count": boxes, "compiled_entry_count": len(spawns_out),
                          "species": sorted({e["species"] for e in ents}),
                          "weight_multiplier": [round(waterways_mod.ramp(w["weight_ramp"], 0.0), 3),
                                                round(waterways_mod.ramp(w["weight_ramp"], 1.0), 3)],
                          "output": "spawn_pool_world/waterways/%s.json" % w["id"]})
    return files, summaries


def build(spawns, routes):
    by_scope = {}
    for e in spawns["entries"]:
        if e["mechanism"] == "spawn_json_coordinate_boxes" and e["ambient"] and e["weight"] > 0:
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
    for sub in regions["subregions"]:
        ents = by_scope.get(sub["id"], [])
        if not ents:
            continue
        doc, summ = compile_subregion(sub, ents, corridor, grid, waterways)
        if not doc["spawns"]:
            continue
        files["data/cobblers/spawn_pool_world/subregions/%s.json" % sub["id"]] = dumps(doc)
        summaries.append(summ)
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
        waterfiles, ws = build_waterways(spawns, waterdoc)
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
    ss = []
    if not a.no_subregions:
        regions = json.loads(Path(a.regions).read_text(encoding="utf-8"))
        subfiles, ss = build_subregions(spawns, routes, regions, a.grid, water_boxes)
        files.update(subfiles)
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
                "inputs": {k: hashlib.sha256(Path(v).read_bytes()).hexdigest() for k, v in (("data/spawns.json", a.spawns), ("data/routes.json", a.routes))},
                "files": {rel: hashlib.sha256(text.encode("utf-8")).hexdigest() for rel, text in sorted(files.items())},
                "route_files": rs, "habitat_files": hs, "subregion_files": ss, "waterway_files": ws,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
