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

Not installed, not runtime-proven. Inherited-pool suppression is deliberately omitted (it needs EXP-012). Habitat files
define rosters only; placing Habitat Blocks and their ReplaceSpawns NBT is world work.

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

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_spawns"
PACK_MCMETA = {"pack": {"pack_format": 48, "description": "Cobblers compiled encounter candidates (not runtime-proven)"}}
SAMPLE_STEP = 4.0


def dumps(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


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


def compile_route(route, entries_by_scope, allowed=None):
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
                cond = {"minX": b["min_x"], "maxX": b["max_x"], "minZ": b["min_z"], "maxZ": b["max_z"], "canSeeSky": True,
                        "biomes": list(e["biomes"])}
                cond.update(e.get("conditions") or {})
                spawns.append({"id": "%s_%s_%s" % (b["id"], s, e["species"]), "pokemon": e["species"], "type": "pokemon",
                               "spawnablePositionType": "grounded", "bucket": e["bucket"], "level": e["level"],
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


def compile_habitat(h, entries):
    display = {e["pokemon"]: e["species"] for e in h["entries"]}
    compiled = [e for e in entries if e["ambient"] and e["weight"] > 0]
    doc = {"name": "cobblers.habitat.%s.name" % h["id"], "type": "cobblemon:natural",
           "spawns": [{"species": display.get(e["species"], e["species"]), "bucket": e["bucket"], "spawnablePositionType": "grounded",
                       "weight": e["weight"], "levelRange": e["level"], "phases": "1-25"} for e in compiled]}
    compiled_names = {display.get(e["species"], e["species"]) for e in compiled}
    summary = {"habitat_id": h["id"], "authored_species_count": len(h["entries"]), "compiled_species_count": len(compiled),
               "deferred_species": [e["species"] for e in h["entries"] if e["species"] not in compiled_names and e.get("bucket") == "authored-only"],
               "output": "habitat_pools/%s.json" % h["id"]}
    return doc, summary


def build(spawns, routes):
    by_scope = {}
    for e in spawns["entries"]:
        if e["mechanism"] == "spawn_json_coordinate_boxes" and e["ambient"] and e["weight"] > 0:
            by_scope.setdefault(e["scope"], []).append(e)
    files, route_summaries, habitat_summaries = {"pack.mcmeta": dumps(PACK_MCMETA)}, [], []
    for r in routes["routes"]:
        sel = (spawns.get("route_species_selection") or {}).get(r["id"])
        doc, summ = compile_route(r, by_scope, set(sel["species"]) if sel else None)
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


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--spawns", default=str(ROOT / "data" / "spawns.json"))
    p.add_argument("--routes", default=str(ROOT / "data" / "routes.json"))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--check", default=None, help="compare with the compilation in this directory instead of writing")
    a = p.parse_args(argv)
    spawns = json.loads(Path(a.spawns).read_text(encoding="utf-8"))
    routes = json.loads(Path(a.routes).read_text(encoding="utf-8"))
    files, rs, hs = build(spawns, routes)
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
    out = Path(a.out)
    for rel, text in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    manifest = {"generator": "tools/compile_spawns.py",
                "inputs": {k: hashlib.sha256(Path(v).read_bytes()).hexdigest() for k, v in (("data/spawns.json", a.spawns), ("data/routes.json", a.routes))},
                "files": {rel: hashlib.sha256(text.encode("utf-8")).hexdigest() for rel, text in sorted(files.items())},
                "route_files": rs, "habitat_files": hs,
                "route_box_count": sum(r["source_box_count"] for r in rs), "route_spawn_entry_count": sum(r["compiled_entry_count"] for r in rs)}
    (out / "manifest.json").write_text(dumps(manifest), encoding="utf-8", newline="\n")
    print("wrote %d files to %s: %d route boxes, %d route entries" % (len(files), out, manifest["route_box_count"], manifest["route_spawn_entry_count"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
