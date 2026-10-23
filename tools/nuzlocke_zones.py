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

  dungeon    (2026-10-23, the owner) each data/dungeons.json dungeon is ONE encounter, whatever its level; they are listed
             under the output's top-level "dungeons", not in "zones", so every consumer of the area zones is unchanged.
  legendaries (2026-10-23, the owner: "nuzlocke page should show dungeons and legendaries per area, so a player can
             count those"; named, on the Nuzlocke page only) every legendary-class encounter OUR data authors
             (legendary_register() lists its sources) is a row under "legendaries" of the zone whose ground holds it.
             Starters and gifts are not wild encounters and get no row; see LEGEND_NOT_COVERED.

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
# fungal_*: the Fungal Isle's three nest pools (tools/fungal_isle.py), each a few dozen blocks inside fungal_north or
# fungal_south and untitled by any settlement, so once placed they would otherwise raise below
# cave_*: the cave kit's pools (tools/caves.py, data/caves.json), each a few dozen blocks inside the sub-region its chamber is in;
# sanctuary_*: the legendary sanctuaries' court pools that replaced them on 2026-10-12 (tools/sanctuaries.py), the same kind of site
# mine_nest_*: the mine networks' nest rooms (tools/mine_networks.py, 2026-10-22), the same kind of site as the cave kit's
MICRO_SITE = re.compile(r"^(elder|sapling|fungal|scar_tarn|cave|sanctuary|tbird|mine_nest)_|_sapling_")  # tbird_: a tree's storey nests (tools/tree_birds.py), part of their tree


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
    for s in LT.settlements(LT.regions(), with_y=False):      # the column box only: no derived/cavern plan needed
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
    not_zones.append({"zone": "nether/*", "what": "every Nether biome table (data/spawns.json nether)",
                      "why": "the Nether's tables are the 2026-10-13 balance pass's draft; whether the Nether counts "
                             "as nuzlocke first-encounter areas is the owner's call, not yet made"})

    kinds = {}
    for z in zones:
        kinds[z["kind"]] = kinds.get(z["kind"], 0) + 1
    # ---------------------------------------------------------------- legendaries per zone, and the dungeon zones
    by_zone, legend_report = legendary_register(zones)
    for z in zones:
        if by_zone.get(z["zone"]):
            z["legendaries"] = by_zone[z["zone"]]
    dungeon_zones = dungeons()
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
        "counts": dict(sorted(kinds.items()), total=len(zones), not_zones=len(not_zones),
                       dungeons=len(dungeon_zones), legendaries=legend_report["rows"],
                       legendary_species=legend_report["species"]),
        "derivation": {
            "tables_are_subregions": "data/encounter_design.json has %d tables and data/regions.json %d sub-regions, "
                                     "the same ids" % (len(tables), len(sub_ids)),
            "corridors_carry_crossed_tables": corridor,
            "sea_level": sea,
        },
        "legs": legs,
        "zones": zones,
        "dungeon_rule": DUNGEON_RULE,
        "dungeons": dungeon_zones,
        "legendary_register": legend_report["register"],
        "not_zones": not_zones,
    }


# ------------------------------------------------------------------------------------------------ legendaries, dungeons
LEGEND_LABELS = {"legendary", "mythical", "ultra_beast", "paradox"}      # the labels the site never names elsewhere
DUNGEON_RULE = ("The owner, 2026-10-23: \"i think it shouldnt do the rift site necessarily, just dungeon name so like if "
                "im doing the night shift, i have 1 encounter no matter the level.\" Each data/dungeons.json dungeon is "
                "ONE encounter zone, whatever band the run is drawn at and wherever its rift opened. A legendary-class "
                "boss or prize inside a dungeon belongs to that one encounter and is not a row of its own.")
# data/adopted_legendary_sites.json site id -> the species its altar or tower holds. The record's `legendary` is display
# text ("Calyrex, with Spectrier", "Necrozma (Dawn Wings)"), so the species ids are typed here and each is checked
# against that text when the register is built; a new site with no entry here stops the build.
SITE_SPECIES = {
    "adopted_mew_temple": ["mew"], "adopted_crown_cemetery": ["calyrex", "spectrier"],
    "adopted_zapdos_tower": ["zapdos"], "adopted_articuno_shrine": ["articuno"],
    "adopted_dawn_tower": ["necrozma"], "adopted_dusk_tower": ["necrozma"], "adopted_moltres_tower": ["moltres"],
    "adopted_crown_spire": ["glastrier"], "sweep_newmoon_island": ["darkrai"],
}
# data/dungeon_prize_roster.json lists these as `placed`, but the place is a dungeon's prize pool (its `where` says so)
DUNGEON_PRIZES = ("volcanion", "zarude", "regidrago")
# roster species that are neither a row, a dungeon's, nor a starter line, each with why
EXCLUDED = {
    "mewtwo": "a gift: the COBBLEVERSE-DP fossil revive (the owner: \"Mewtwo stays on the fossil route\"); no place to count it in",
    "entei": "a boss fight in a pocket dimension entered from the Nether (data/entei_boss.json); the Nether is not a catch zone here and the fight is a dungeon-type boss",
    "eternatus": "OUT by the owner until a Galar Particle supply exists (data/adopted_legendary_sites.json owner_decisions_2026_10_02)",
    "lugia": "data/legendaries.json lugia is BLOCKED (the trench cannot exist): nowhere in the world",
    "wochien": "a Nether shrine that stays where Cobbleverse generates it; the Nether is not a catch zone here",
    "chienpao": "a Nether shrine that stays where Cobbleverse generates it; the Nether is not a catch zone here",
    "tinglu": "a Nether shrine that stays where Cobbleverse generates it; the Nether is not a catch zone here",
    "chiyu": "a Nether shrine that stays where Cobbleverse generates it; the Nether is not a catch zone here",
}
LEGEND_NOT_COVERED = [
    "Dungeon bosses and prizes (data/dungeon_prize_roster.json status to_dungeon, and the prize pools of data/dungeons.json): the dungeon is one encounter, so its legendary is that encounter, not a row.",
    "Starters and gifts: every species of a data/mythical_starters.json line (the starter screen and its evolutions), the fossil revive, rideable mounts (data/water_mounts.json) and quest or shop items. A species that also has a WILD entry in data/spawns.json (Poipole at the two Necrozma towers) is a row through that entry.",
    "The Nether and its tables, the Nether boss pockets (Entei) and the Nether shrines Cobbleverse generates.",
    "Anything Cobbleverse's own datapacks or mods spawn that this repository's data does not name: inherited legendary spawn presets not switched off by data/spawn_suppression.json, structures that generate on their own, Cobblemon raid dens, Terapagos on amethyst in caves. This register is read from OUR data, not from the world (CLAUDE.md 'Our list is not the world').",
    "Hidden rows of the same site: a row is the species at its authored site; nothing here says a site is built, gated open or findable in a running game.",
]


_LEGEND = []


def compact(s):
    """A species id in the jar's spelling: first word, lower case, letters and digits ("articuno galarian" -> articuno,
    "cobblemon:hoopa" -> hoopa, "Type: Null" -> typenull is the caller's job)."""
    return re.sub(r"[^a-z0-9]", "", (str(s).split() or [""])[0].split(":")[-1].lower())


def legend_class():
    """The Cobblemon jar's species ids whose labels include legendary, mythical, ultra_beast or paradox."""
    if not _LEGEND:
        import zipfile
        import player_guide_battles as PB
        z = zipfile.ZipFile(PB.find_jar())
        out = set()
        for n in z.namelist():
            m = re.fullmatch(r"data/cobblemon/species/[^/]+/([a-z0-9_]+)\.json", n)
            if m and set(json.loads(z.read(n).decode("utf-8")).get("labels") or []) & LEGEND_LABELS:
                out.add(m.group(1))
        if len(out) < 100:
            raise SystemExit("only %d legendary-class species in the Cobblemon jar: wrong jar?" % len(out))
        _LEGEND.append(out)
    return _LEGEND[0]


class Locator:
    """The zone a world column belongs to: the sub-region polygon holding it, else the sea band whose boxes hold it
    (the same boxes the spawn pack and the titles use). A column in neither is an error, not a guess."""

    def __init__(self, zones):
        self.subs = load("regions.json")["subregions"]
        self.ids = {z["zone"] for z in zones}
        self.bands = None

    def zone(self, x, z):
        """The zone id, or None when the column is in a sub-region that is not a zone (under the sea)."""
        import subregion_boxes as SB
        for s in self.subs:
            if any(SB.point_in_polygon(x, z, poly) for poly in s["polygons"]):
                return s["id"] if s["id"] in self.ids else None
        if self.bands is None:
            import location_titles as LT
            self.bands = LT._marine_bands()
        for bid, boxes in self.bands.items():
            if bid in self.ids and any(b[0] <= x <= b[1] and b[2] <= z <= b[3] for b in boxes):
                return bid
        raise SystemExit("column (%d, %d) is in no sub-region polygon and no sea band: no zone holds it" % (x, z))


def dungeons():
    """One encounter zone per data/dungeons.json dungeon, by its player-facing name."""
    out = [{"zone": "dungeon_" + d["id"], "dungeon": d["id"], "name": d["name"],
            "table": "data/dungeons.json dungeons.%s" % d["id"]} for d in load("dungeons.json")["dungeons"]]
    if len({d["name"] for d in out}) != len(out):
        raise SystemExit("two dungeons share a player-facing name")
    return out


def legendary_register(zones, loc=None):
    """({zone id: [row]}, report): every legendary-class encounter OUR data authors, placed in the zone whose ground holds it.

    A row is {species, sources}; no coordinate is written (see the comment at the end). The zone is the one holding the
    column its source gives (Locator): for an encounter in a pocket dimension or underground, the column of its entrance
    or the surface above it. Sources, each read from its own file:
      data/legendaries.json            sited chambers, grottos and the tree crown, and the Celebi wake (sapling_celebi.json)
      data/adopted_legendary_sites.json  every adopted and sweep site, its footprint centre (tools/adopted_sites.py)
      data/sanctuaries.json            each occupant and co-occupant, at the sanctuary's centre
      data/spawns.json                 every ambient, non-heart entry of a legendary-class species, by its scope
      hoopa_cradle, frostpeak_keep(_quest), coldwater_station, rayquaza_sky, research_station
                                       the authored one-off encounters, each at the position its own file gives
    The register is then checked against data/dungeon_prize_roster.json (a record of every legendary-class species and
    its one home): a roster species that is none of a row, a dungeon's, a starter's or a listed exclusion stops the build.
    """
    import adopted_sites as A
    legend = legend_class()
    loc = loc or Locator(zones)
    found, not_placed = {}, []

    def put(zid, species, source, at):
        sp = compact(species)
        if sp not in legend:
            raise SystemExit("%s names %r, which the Cobblemon jar does not label legendary-class" % (source, species))
        row = found.setdefault((zid, sp), {"species": sp, "sources": [], "at": at})
        if row["at"] is None:
            row["at"] = at
        if source not in row["sources"]:
            row["sources"].append(source)

    def add(species, x, z, source):
        zid = loc.zone(int(x), int(z))
        if zid is None:
            not_placed.append({"species": compact(species), "what": source,
                               "why": "its column (%d, %d) is in a sub-region under the sea, which is not a zone" % (x, z)})
            return
        put(zid, species, source, [int(x), int(z)])

    # ---- data/legendaries.json
    for r in load("legendaries.json")["encounters"]:
        src = "data/legendaries.json %s (%s)" % (r["id"], r["kind"])
        if r["status"] == "sited":
            at = r["mouth"] if r["kind"] == "lake_grotto" else r["portal"]
            add(r["species"], at[0], at[1], src)
        elif r["status"] == "gate_only" and r["kind"] == "sapling_wake":
            pos = load("sapling_celebi.json")["position"]
            add(r["species"], pos[0], pos[2], src + " at data/sapling_celebi.json position")
        else:
            not_placed.append({"species": compact(r["species"]), "what": src,
                               "why": "status %s (%s): not in the world" % (r["status"], r.get("blocked_by") or "not built")})
    # ---- data/adopted_legendary_sites.json
    placements = load("placements.json")["placements"]
    sites = A.sites()
    if set(SITE_SPECIES) != {s["id"] for s in sites}:
        raise SystemExit("adopted sites and tools/nuzlocke_zones.py SITE_SPECIES differ: %s"
                         % sorted(set(SITE_SPECIES) ^ {s["id"] for s in sites}))
    site_at = {}
    for s in sites:
        x, z = A.centre(s, placements)
        site_at[s.get("scheduled_as") or s["id"]] = (x, z)
        for sp in SITE_SPECIES[s["id"]]:
            if sp not in re.sub(r"[^a-z0-9 ]", " ", s["legendary"].lower()).split():
                raise SystemExit("%s: SITE_SPECIES says %s, its legendary text says %r" % (s["id"], sp, s["legendary"]))
            add(sp, x, z, "data/adopted_legendary_sites.json %s" % s["id"])
    # ---- data/sanctuaries.json
    for s in load("sanctuaries.json")["sanctuaries"]:
        occ = s["occupant"]
        for sp in [occ["species"]] + list(occ.get("co_occupants") or []):
            add(sp, s["site"]["centre"][0], s["site"]["centre"][1], "data/sanctuaries.json %s (%s)" % (s["id"], occ["mode"]))
    # ---- data/spawns.json: wild entries of a legendary-class species, by scope
    spawns = load("spawns.json")
    zone_by = {z["zone"]: z for z in zones}
    pool_zone = {p: z["zone"] for z in zones for p in z.get("pools") or ()}
    sunk = {s["id"] for s in load("regions.json")["subregions"]} - set(zone_by)
    sites_by_id = {p["id"]: p for p in spawns.get("placement_sites") or []}
    placed = {}
    for b in load("habitat_blocks.json")["blocks"]:
        if b.get("status") == "placed":
            placed.setdefault(b["pool"].split(":", 1)[1], []).append(b)
    for e in spawns["entries"]:
        if not (e.get("ambient") and e.get("weight", 0) > 0 and not e.get("heart")) or compact(e["species"]) not in legend:
            continue
        sc, src = e["scope"], "data/spawns.json entry %s in %s" % (e["species"], e["scope"])
        if sc in zone_by:
            put(sc, e["species"], src, None)
        elif sc in sunk:
            not_placed.append({"species": compact(e["species"]), "what": src, "why": "its sub-region is under the sea and not a zone"})
        elif sc in pool_zone:
            put(pool_zone[sc], e["species"], src, None)
        elif sc in sites_by_id:
            x, z = site_at[sites_by_id[sc]["placement"]]
            add(e["species"], x, z, src)
        elif sc in placed:
            p = placed[sc][0]["position"]
            add(e["species"], p["x"], p["z"], src)
        elif e["mechanism"] == "habitat_block":
            not_placed.append({"species": compact(e["species"]), "what": src, "why": "no placed Habitat Block carries the pool: not in the world yet"})
        else:
            raise SystemExit("%s: a legendary-class wild entry whose scope is no zone, site or pool this tool knows" % src)
    # ---- the authored one-offs, each at its own file's position
    h = load("hoopa_cradle.json")
    add(h["species"], h["spot"][0], h["spot"][2], "data/hoopa_cradle.json spot (underground, at the surface above it)")
    g = load("frostpeak_keep_quest.json")["giratina"]
    c = load("frostpeak_keep.json")["site"]["centre"]
    add(g["species"], c[0], c[1], "data/frostpeak_keep_quest.json giratina at data/frostpeak_keep.json site.centre")
    cw = load("coldwater_station.json")["site"]
    add("kyogre", cw["corner"][0] + cw["size"] // 2, cw["corner"][1] + cw["size"] // 2,
        "data/kyogre_cave.json, entered from the Coldwater Station (data/coldwater_station.json site)")
    ry = load("rayquaza_sky.json")["site"]["summit"]
    add("rayquaza", ry["x"], ry["z"], "data/rayquaza_sky.json site.summit")
    sh = load("research_station.json")["shrine"]
    for sp in ("latias", "latios"):
        add(sp, sh[sp]["at"][0], sh[sp]["at"][1], "data/research_station.json shrine.%s" % sp)
    for row in found.values():
        row["sources"].sort()

    # ---- the roster cross-check: every legendary-class species has one home, and this tool must know which
    roster = load("dungeon_prize_roster.json")["species"]
    rows_species = {sp for _z, sp in found}
    starters = {compact(s) for ln in load("mythical_starters.json")["lines"] for s in ln.get("learnset_from") or []}
    held = sorted(sp for sp, v in roster.items() if v.get("status") == "to_dungeon" or sp in DUNGEON_PRIZES)
    excluded = []
    for sp, v in sorted(roster.items()):
        if sp in rows_species or sp in held:
            continue
        if sp in starters:
            excluded.append({"species": sp, "why": "a starter line (data/mythical_starters.json) or a gift, not a wild encounter"})
        elif sp in EXCLUDED:
            excluded.append({"species": sp, "why": EXCLUDED[sp]})
        else:
            raise SystemExit("data/dungeon_prize_roster.json gives %s a home (%s: %s) that neither a row, a dungeon, a "
                             "starter line nor EXCLUDED in tools/nuzlocke_zones.py covers: add it to the register"
                             % (sp, v.get("status"), v.get("where") or v.get("home")))
    bad = [sp for sp in DUNGEON_PRIZES if sp not in roster]
    if bad:
        raise SystemExit("DUNGEON_PRIZES names species the roster does not hold: %s" % bad)
    # a species that has a row from another source is not "missing": the pool's entry is the same encounter
    not_placed = [n for n in not_placed if n["species"] not in rows_species]
    # Rows carry NO coordinates. Other tools read every data/*.json for "authored places" to keep clear of (tools/
    # frostpeak_keep.py found the Giratina keep's own centre in this file and refused its site): a position belongs to the
    # file that authors it, and the zone a row is in already says where it was placed.
    by_zone = {}
    for (zid, _sp), row in sorted(found.items()):
        by_zone.setdefault(zid, []).append({"species": row["species"], "sources": row["sources"]})
    report = {"rows": len(found), "species": len(rows_species),
              "register": {"rule": "A legendary-class encounter our data authors is one row in the zone whose ground "
                                   "holds it, with its own checkbox on the Nuzlocke page: the area's catch is still its "
                                   "first ordinary encounter, and a player counts the legendary beside it. Named on the "
                                   "Nuzlocke page only (the owner, 2026-10-23: \"Named ... Only on the Nuzlocke page; the map and other pages keep hiding them\").",
                           "not_covered": LEGEND_NOT_COVERED, "not_placed": not_placed, "excluded": excluded,
                           "dungeon_held": held}}
    return by_zone, report


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
    prefixes = tuple(n["zone"][:-1] for n in doc["not_zones"] if n["zone"].endswith("/*"))
    declared = {a for a in areas if prefixes and a.startswith(prefixes)}
    problems = []
    for aid in sorted(set(areas) - set(want) - sunk - declared):
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
