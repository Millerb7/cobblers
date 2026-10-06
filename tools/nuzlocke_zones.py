#!/usr/bin/env python
"""The Nuzlocke catch zones: one zone per distinct encounter table a player can meet, written to data/nuzlocke_zones.json.

The owner, 2026-10-06: "Finish determining the regions a Nuzlocke player uses as catch zones, and make the location
titles pop up in game so a player knows when they have entered a new one."

THE RULE. A Nuzlocke player takes the first encounter in each AREA; an area here is one encounter table, because a
table is what makes one place's encounters different from the next. Every fact below is read from data/ when this
tool runs and recorded in the output's "derivation", so the rule can be re-checked rather than trusted:

  land       each data/regions.json sub-region is one table (data/encounter_design.json "tables" has exactly the
             sub-region ids). A route leg is NOT a zone: its corridor carries only species of the sub-regions it
             crosses (data/spawns.json route_species_selection is chosen from those tables by tools/build_encounters.py,
             and the compiled route files tag every entry with its sub-region), so one leg crosses 2 to 7 tables and
             each is its own zone. A sub-region with no column at or above sea level (round(ground) >= sea level on
             the canonical heightmap, sampled at its 32-block raster cell centres) has nowhere a land table can spawn:
             it is listed under not_zones, not titled.
  sea        each band of each data/spawns.json marine_zones entry is one table (its own roster and level band).
  waterway   each data/waterways.json waterway with ambient entries is one table.
  cave       each of Victory Road's zones (data/vr_caves.json zones) is one table, carried by Habitat Blocks
             (data/habitat_blocks.json); a zone's "_core" pool is its heart, not a second area.
  site       a placed Habitat Block pool that is not Victory Road's, not an elder tree's and not a sapling's: a
             building or hollow with a table of its own (the Route 1 mansion). Titled by its settlement's title.

NOT ZONES (each listed in the output with its reason): a heart (ENCOUNTER_DESIGN.md section 10: a rarer spot inside
an area, never a first-encounter area); an elder tree's or sapling's Habitat Block pool (a few blocks inside its
sub-region, named for it: an encounter there is that sub-region's); a Habitat Block pool with no placed block (not in
the world yet; it becomes a zone when placed); settlements (titled, but spawn-free or part of their sub-region).

  python tools/nuzlocke_zones.py              # writes data/nuzlocke_zones.json, prints the counts
  python tools/nuzlocke_zones.py --check      # exit 1 if data/nuzlocke_zones.json is stale
  python tools/nuzlocke_zones.py audit [--pack build/datapacks/cobblers_spawns]
                                              # the zones against the COMPILED spawn pack (an independent reading)

WHAT THIS DOES NOT COVER. Cobbleverse's own spawn pools outside our sub-regions, the Rift's own systems, raids and
dens; how the game rolls rates. A zone list is not proof a player meets these encounters in game.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
OUT = ROOT / "data" / "nuzlocke_zones.json"
GRID = 32                       # the sub-region raster compile_spawns uses (SUBREGION_GRID)
VR_SUBTITLE = "Victory Road"
MICRO_SITE = re.compile(r"^(elder|sapling)_|_sapling_")


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def vr_pool(zone_id, core=False):
    """Victory Road's Habitat Block pool for a zone, as tools/vr_caves.py names it (line 'pool = "vrc_cave" if ...')."""
    if zone_id == "the_dark":
        return "vrc_cave"
    return "vrc_%s_core" % zone_id if core else "vrc_%s" % zone_id


def level_span(spawns, scope):
    """[lowest, highest] level of a scope's ambient entries ("a-b" strings in data/spawns.json)."""
    lo, hi = [], []
    for e in spawns["entries"]:
        if e["scope"] == scope and e.get("ambient") and e.get("weight", 0) > 0:
            a, _, b = str(e["level"]).partition("-")
            lo.append(int(a))
            hi.append(int(b or a))
    return [min(lo), max(hi)] if lo else None


def settlement_at(x, z):
    """(id, name) of the titled settlement whose box holds the column, from tools/location_titles.py's own list."""
    import location_titles as LT
    for s in LT.settlements(LT.regions()):
        x0, z0, x1, z1 = s["box"]
        if x0 <= x <= x1 and z0 <= z <= z1:
            return s["id"], s["name"], s["region"]
    return None, None, None


def land_share(polygons, ground, sea):
    """The share of the sub-region's 32-block raster cells whose centre is ground at or above sea level."""
    import subregion_boxes as SB
    cells, x0, z0, _, _ = SB.rasterise(polygons, GRID)
    pts = [(x0 + i * GRID + GRID // 2, z0 + j * GRID + GRID // 2) for i, j in cells]
    if not pts:
        return 0.0
    land = sum(1 for x, z in pts if 0 <= x < 8192 and 0 <= z < 8192 and ground(x, z) >= sea)
    return round(land / len(pts), 3)


def build(ground=None):
    """The data/nuzlocke_zones.json document."""
    import subregion_boxes as SB
    regions = load("regions.json")
    design = load("encounter_design.json")
    spawns = load("spawns.json")
    routes = sorted(load("routes.json")["routes"], key=lambda r: int(r["order"]))
    paths = load("route_paths.json")["paths"]
    waterways = load("waterways.json")["waterways"]
    vr = load("vr_caves.json")
    habitat = load("habitat_blocks.json")["blocks"]
    world = load("world.json")
    sea = int(world["vertical"]["sea_level"])
    if ground is None:
        import ground as G
        ground = G.load()

    region_name = {r["id"]: r["display_name"] for r in regions["regions"]}
    subs = regions["subregions"]
    sub_ids = [s["id"] for s in subs]
    tables = design["tables"]
    sp_sub = {x["id"]: x for x in spawns["subregions"]}
    ambient = {}
    for e in spawns["entries"]:
        if e.get("ambient") and e.get("weight", 0) > 0 and not e.get("heart"):
            ambient.setdefault(e["scope"], set()).add(e["species"])

    # ---------------------------------------------------------------- the derivation, measured
    if set(tables) != set(sub_ids):
        raise SystemExit("data/encounter_design.json tables %s and data/regions.json sub-regions differ: %s"
                         % (len(tables), sorted(set(tables) ^ set(sub_ids))))
    corridor = []
    for r in routes:
        crossed = r["geography"]["subregions"]
        chosen = set(spawns["route_species_selection"][r["id"]]["species"])
        pool = set().union(*({e["pokemon"] for e in sp_sub[c]["entries"]} for c in crossed))
        corridor.append({"route": r["id"], "tables_crossed": len(crossed), "corridor_species": len(chosen),
                         "species_from_no_crossed_table": sorted(chosen - pool)})
    stray = [c for c in corridor if c["species_from_no_crossed_table"]]
    if stray:
        raise SystemExit("a route corridor carries species no crossed sub-region table has, so a leg WOULD be a table "
                         "of its own; the zone rule no longer holds: %s" % stray)

    # ---------------------------------------------------------------- legs: the order a player meets the land zones
    met, legs, met_on = set(), [], {}
    for r in routes:
        seen, order = set(), []
        for t in r["geography"]["transitions"]:
            for sid in t["subregions"]:
                if sid not in seen:
                    seen.add(sid)
                    order.append({"zone": sid, "at_distance_blocks": round(float(t["at_distance_blocks"]), 1),
                                  "new": sid not in met})
                    met_on.setdefault(sid, []).append(r["id"])
        met |= seen
        legs.append({"route": r["id"], "name": r["display_name"], "zones": order,
                     "new_zones": sum(1 for o in order if o["new"])})

    placed = {}
    for b in habitat:
        if b.get("status") == "placed":
            placed.setdefault(b["pool"].split(":", 1)[1], []).append(b)
    # an elder tree's or sapling's pool belongs to the sub-region its placed blocks stand in (by position, not name)
    sites_in = {}
    for pool, blocks in placed.items():
        if not MICRO_SITE.search(pool):
            continue
        for b in blocks:
            x, z = b["position"]["x"], b["position"]["z"]
            sid = next((s["id"] for s in subs if any(SB.point_in_polygon(x, z, poly) for poly in s["polygons"])), None)
            sites_in.setdefault(sid, set()).add(pool)

    zones, not_zones = [], []
    # ---------------------------------------------------------------- land
    for s in subs:
        share = land_share(s["polygons"], ground, sea)
        t = tables[s["id"]]
        z = {"zone": s["id"], "kind": "land", "name": s["display_name"], "subtitle": region_name[s["parent"]],
             "region": s["parent"], "table": "data/encounter_design.json tables.%s" % s["id"],
             "tier": t.get("tier"), "levels": t.get("levels"), "species": len(ambient.get(s["id"], ())),
             "geometry": "data/regions.json subregions.%s polygons, %d-block raster" % (s["id"], GRID),
             "land_share": share, "legs": met_on.get(s["id"], []), "sites": sorted(sites_in.get(s["id"], ()))}
        if share == 0.0:
            not_zones.append({"zone": s["id"], "what": "sub-region table", "why": "no raster cell of %s has ground at "
                              "or above sea level (y%d) on the canonical heightmap: it is under the sea, a land table "
                              "has nowhere to spawn and a title would show over open water" % (s["display_name"], sea)})
            continue
        zones.append(z)

    # ---------------------------------------------------------------- sea
    for mz in spawns.get("marine_zones") or []:
        for b in mz["bands"]:
            n = len(ambient.get(b["id"], ()))
            if not n:
                continue
            lv = b.get("level_band") or {}
            zones.append({"zone": b["id"], "kind": "sea", "name": b["display_name"], "subtitle": mz["display_name"],
                          "region": mz.get("marine_region"),
                          "table": "data/spawns.json marine_zones.%s bands.%s" % (mz["id"], b["id"]),
                          "tier": None, "levels": [lv.get("minimum"), lv.get("maximum")], "species": n,
                          "geometry": "tools/compile_spawns.py marine_bands (open sea %s-%s blocks from land)"
                                      % (b["from_blocks"], b.get("to_blocks") if b.get("to_blocks") is not None else "the border"),
                          "legs": [], "access": "a Pokemon that carries a player on water"})

    # ---------------------------------------------------------------- waterways
    for w in waterways:
        n = len(ambient.get(w["id"], ()))
        if not n:
            continue
        lv = level_span(spawns, w["id"])
        zones.append({"zone": w["id"], "kind": "waterway", "name": w["display_name"], "subtitle": "Waterway",
                      "region": None, "table": "data/spawns.json entries scope %s (waterway_coordinate_boxes)" % w["id"],
                      "tier": None, "levels": lv, "species": n,
                      "geometry": "data/waterways.json %s polyline, half_width %s (tools/waterways.py boxes_by_segment)"
                                  % (w["id"], w["half_width"]),
                      "legs": [r["id"] for r in routes if _line_hits(paths.get(r["id"], ()), w)]})

    # ---------------------------------------------------------------- Victory Road's caves
    hab = design.get("habitats") or {}
    vr_pools = set()
    for vz in vr["zones"]:
        pools = [p for p in dict.fromkeys((vr_pool(vz["id"]), vr_pool(vz["id"], core=True))) if p in placed]
        vr_pools |= {vr_pool(vz["id"]), vr_pool(vz["id"], core=True)}
        if not pools:
            not_zones.append({"zone": vz["id"], "what": "Victory Road zone", "why": "no placed Habitat Block carries its pool"})
            continue
        h = hab.get(vr_pool(vz["id"])) or {}
        zones.append({"zone": "vr_" + vz["id"], "kind": "cave", "name": vz["name"], "subtitle": VR_SUBTITLE,
                      "region": "the_rift", "table": "data/encounter_design.json habitats.%s" % vr_pool(vz["id"]),
                      "pools": pools, "tier": h.get("tier"), "levels": h.get("levels"),
                      "species": len(ambient.get(vr_pool(vz["id"]), set()) | ambient.get(vr_pool(vz["id"], True), set())),
                      "geometry": "data/habitat_blocks.json positions of %s, each +-range_of_influence" % " and ".join(pools),
                      "legs": ["victory_road"], "blocks": sum(len(placed[p]) for p in pools)})

    # ---------------------------------------------------------------- the other Habitat Block pools
    for pool in sorted({e["scope"] for e in spawns["entries"] if e["mechanism"] == "habitat_block"}):
        if pool in vr_pools:
            continue
        if MICRO_SITE.search(pool):
            continue                         # counted under its sub-region's "sites"
        if pool not in placed:
            not_zones.append({"zone": pool, "what": "Habitat Block pool", "why": "no placed block in "
                              "data/habitat_blocks.json: not in the world, so nobody meets it; it becomes a zone when placed"})
            continue
        p0 = placed[pool][0]["position"]
        sid, sname, sregion = settlement_at(p0["x"], p0["z"])
        if sid is None:
            raise SystemExit("site pool %s has a placed block at (%d, %d) in no titled settlement: give the site a "
                             "title of its own before it can be a zone" % (pool, p0["x"], p0["z"]))
        zones.append({"zone": pool, "kind": "site", "name": sname, "subtitle": sregion, "region": None,
                      "settlement": sid,
                      "table": "data/spawns.json entries scope %s (habitat_block)" % pool, "tier": None,
                      "levels": level_span(spawns, pool),
                      "species": len(ambient.get(pool, ())),
                      "geometry": "data/habitat_blocks.json positions of %s, each +-range_of_influence" % pool,
                      "legs": [], "blocks": len(placed[pool]), "titled_by": "settlement"})
    micro = sorted({p for p in placed if MICRO_SITE.search(p)})
    not_zones.append({"zone": "elder_* / sapling_*", "what": "%d placed elder-tree and sapling Habitat Block pools" % len(micro),
                      "why": "a few blocks inside the sub-region each is named for: an encounter there is that "
                             "sub-region's, listed under its zone's \"sites\""})
    not_zones.append({"zone": "hearts", "what": "every <area>_h<n> heart entry",
                      "why": "docs/mechanics/ENCOUNTER_DESIGN.md section 10: a rarer spot inside an area, never a "
                             "first-encounter area"})

    kinds = {}
    for z in zones:
        kinds[z["kind"]] = kinds.get(z["kind"], 0) + 1
    return {
        "schema": "cobblers.nuzlocke_zones/1",
        "generated_by": "tools/nuzlocke_zones.py from data/regions.json, encounter_design.json, spawns.json, "
                        "routes.json, route_paths.json, waterways.json, vr_caves.json, habitat_blocks.json and the "
                        "canonical heightmap. Do not edit by hand: change the inputs and regenerate.",
        "rule": "One catch zone per distinct encounter table a player can meet; the first encounter in a zone is the "
                "player's catch there, whether it comes from the zone's table or a site inside it (an elder tree, a "
                "sapling, a heart). A route leg is not a zone: it crosses several. docs/mechanics/NUZLOCKE_ZONES.md.",
        "titles": "Every zone is titled on entry by cobblers_titles (tools/location_titles.py): land, sea, waterway "
                  "and cave zones by their own name over their subtitle; a site zone by its settlement's title.",
        "counts": dict(sorted(kinds.items()), total=len(zones), not_zones=len(not_zones)),
        "derivation": {
            "tables_are_subregions": "data/encounter_design.json has %d tables and data/regions.json %d sub-regions, "
                                     "the same ids" % (len(tables), len(sub_ids)),
            "corridors_carry_crossed_tables": corridor,
            "sea_level": sea,
        },
        "legs": legs,
        "zones": zones,
        "not_zones": not_zones,
    }


def _line_hits(points, waterway):
    """Whether a route's walked line passes within the waterway's half width of its polyline (box test)."""
    import waterways as W
    boxes = [b for _, _, bs in W.boxes_by_segment(waterway["polyline"], waterway["half_width"], 16) for b in bs]
    return any(b[0] <= x <= b[1] and b[2] <= z <= b[3] for x, z in points[::4] for b in boxes)


def dumps(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def audit(pack):
    """The zones against the compiled spawn pack, read through tools/nuzlocke_map.py's own reader. Returns problems."""
    import nuzlocke_map as N
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    areas = N.build_areas(N.read_pack(pack), N.subregion_names(), N.route_names())
    want = {}
    for z in doc["zones"]:
        key = {"land": "sub/%s", "sea": "marine/%s", "waterway": "waterways/%s"}.get(z["kind"])
        if key:
            want[key % z["zone"]] = z
    sunk = {"sub/" + n["zone"] for n in doc["not_zones"] if n["what"] == "sub-region table"}
    problems = []
    for aid in sorted(set(areas) - set(want) - sunk):
        problems.append("compiled area %s is no zone and not listed under not_zones" % aid)
    for aid in sorted(set(want) - set(areas)):
        problems.append("zone %s has no compiled spawn file" % aid)
    for aid in sorted(sunk & set(areas)):
        problems.append("KNOWN %s compiles a land table under the sea (no zone, no title)" % aid)
    return problems, len(areas)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", nargs="?", default="write", choices=("write", "audit"))
    p.add_argument("--check", action="store_true", help="exit 1 if data/nuzlocke_zones.json is stale")
    p.add_argument("--pack", default=str(ROOT / "build" / "datapacks" / "cobblers_spawns"))
    a = p.parse_args(argv)
    if a.cmd == "audit":
        problems, n = audit(a.pack)
        bad = [x for x in problems if not x.startswith("KNOWN")]
        for x in problems:
            print(x)
        print("audit: %d compiled areas, %d problems, %d known" % (n, len(bad), len(problems) - len(bad)))
        return 1 if bad else 0
    doc = build()
    text = dumps(doc)
    if a.check:
        old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        print("data/nuzlocke_zones.json is %s" % ("current" if old == text else "STALE: run python tools/nuzlocke_zones.py"))
        return 0 if old == text else 1
    OUT.write_text(text, encoding="utf-8")
    print("wrote %s: %s" % (OUT.relative_to(ROOT), doc["counts"]))
    for leg in doc["legs"]:
        print("  %-28s %d zones, %d new" % (leg["route"], len(leg["zones"]), leg["new_zones"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
