#!/usr/bin/env python
"""Wrong-country spawns: does every wild spawn in the COMPILED pack live where its species lives?

The owner, 2026-10-04: "WRONG-COUNTRY SPAWNS. Crabominable in the southern map ... Sweep every live roster for
species that do not belong where they are ... against what is actually compiled now."

What it reads, and what it does NOT read:

  build/datapacks/cobblers_spawns   the compiled pack (tools/compile_spawns.py; compiled here first if absent):
                                    every spawn_pool_world entry, its place, position and conditions
  the Cobblemon 1.8 jar             each species' OWN natural spawn data (data/cobblemon/spawn_pool_world, herds
                                    included) and Cobblemon's biome tags; regional forms kept apart
  data/regions.json                 the place: each sub-region's paint preset; the marine regions' temperature
  data/waterways.json               the waterway polylines (which sub-regions a creek crosses)
  data/spawns.json marine_zones     which marine region a marine band file belongs to
  docs/mechanics/ENCOUNTER_DESIGN.md  section 11's table: the owner's starter placements (JUDGED, quoted)

It never reads data/encounter_design.json's rosters or reasons as an expectation, and never imports
tools/build_encounters.py or tools/compile_spawns.py to judge (compile_spawns is only RUN, to make the pack when
build/ has none). The climate classes, the place climates and the water kinds are this file's own tables below.

The judgement, per compiled entry (grouped by place, species, position and conditions):

  species natives   the vanilla biomes the species' jar entries name (tags resolved through Cobblemon's tags and
                    vanilla 1.21.1's, optional modded entries dropped); is_volcanic, which Cobblemon fills only with
                    modded biomes, counts as arid. A species with no vanilla native at all is judged by TYPE (ice is
                    cold, fire is hot) and its egg groups, and the row says so.
  climate           cold < cool < temperate < hot (warm = hot and humid, arid = hot and dry). A species fits a
                    place whose climate is within ONE step of a climate it is native to (cold-cool, cool-temperate,
                    temperate-warm, temperate-arid, warm-arid). Two steps is the wrong country: an alpine ice crab on
                    a temperate strand, a desert shrew on a snowy mountain.
  water             a water entry (submerged, surface, seafloor) or a shore entry (neededNearbyBlocks water) is also
                    judged salt against fresh: a species whose own WATER natives are only sea (oceans, beaches,
                    stony shore) does not fit a lake, and one whose water natives are only fresh (rivers, swamps,
                    land-biome lakes) does not fit the sea.
  water places      a sub-region has fresh water, and the sea too when one of its boundaries is a coast and it is an
                    island or lies within twice the polygon tolerance of a marine region's polygon; marine bands are
                    sea; the waterway is a creek, judged in every sub-region its polyline crosses.
  conditions        canSeeSky false or a maxY under the place's ground (p10) makes a land entry underground (cave
                    natives fit there); an entry `biomes` list replaces the place's paint. minY cannot change the
                    country: every preset's height bands share one climate here. Fits only after that narrowing ->
                    FIT-BY-CONDITION. On the 2026-10-04 pack no entry needed it (0 rows).

  FIT               fits as the place is painted
  FIT-BY-CONDITION  fits only within its own conditions
  JUDGED            does not fit, and is an owner placement: section 11's starter families, the row quoted
  KNOWN             does not fit, no owner placement covers it, and this audit's ruling is recorded in KNOWN below
                    (a defect for the content side to fix; never fixed here). A KNOWN that no longer misfits is
                    STALE and fails, so the list cannot outlive its defect.
  MISFIT            does not fit and nothing judges it: the audit FAILS (exit 1)

Independence, proven by MUTATING THE GENERATOR (2026-10-04): with `drop_stages` in tools/build_encounters.py
replaced by `return stages` (data/encounter_design.json untouched), build_encounters regenerated a scratch copy of
data/spawns.json, compile_spawns compiled it to a scratch pack, and this audit failed on Crabominable at
south_strand (cold-native, two steps from the strand's temperate paint). tests/test_spawn_habitat_audit.py repeats
that mutation on every run. Run on the pack compiled from be0bc12^'s data/spawns.json (before the builder's habitat
fixes), it named every fixed species the pack compiled: Crabominable, Sandshrew, Sandslash (base and heart), Crustle,
Wailord and Gastrodon (Shellos itself compiled nowhere at tier 7); on the fixed pack none of them remains.

  python tools/spawn_habitat_audit.py                  # judge build/datapacks/cobblers_spawns
  python tools/spawn_habitat_audit.py --pack <dir> --jar <Cobblemon-fabric-1.8.0+1.21.1.jar> --json <out>

Not covered: the Victory Road Habitat pools (habitat_pools/, cave tiles, not a climate question); whether a species
SPAWNS in game (validity, not behaviour); the modded biomes Cobblemon's optional tag entries name (none loaded);
weather, time and light conditions (no bearing on country).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
DEFAULT_PACK = ROOT / "build" / "datapacks" / "cobblers_spawns"
DESIGN_DOC = ROOT / "docs" / "mechanics" / "ENCOUNTER_DESIGN.md"

# ------------------------------------------------------------------------------------------- climate classes
# Ladder positions: a fit is a native climate within one step of the place's. warm and arid are both "hot"; the
# humidity split between them is one step, so a jungle species in a desert is a near fit, never a far one.
LADDER = {"cold": 0, "cool": 1, "temperate": 2, "warm": 3, "arid": 3}


def distance(a, b):
    if a == b:
        return 0
    if {a, b} == {"warm", "arid"}:
        return 1
    return abs(LADDER[a] - LADDER[b])


# Vanilla 1.21.1 overworld biomes -> climate (the species side). Snow and ice biomes and every peak are cold
# (Cobblemon's own is_cold includes is_peak, so stony_peaks is cold here); taiga, windswept hills and stony shore
# cool; the green middle temperate; jungle, mangrove and the lukewarm/warm seas warm; desert, savanna and badlands
# arid. The three cave biomes are None: underground has no country.
BIOME_CLIMATE = {
    **dict.fromkeys(["snowy_plains", "ice_spikes", "snowy_taiga", "snowy_slopes", "frozen_peaks", "jagged_peaks",
                     "stony_peaks", "grove", "frozen_river", "snowy_beach", "frozen_ocean", "deep_frozen_ocean",
                     "cold_ocean", "deep_cold_ocean"], "cold"),
    **dict.fromkeys(["taiga", "old_growth_pine_taiga", "old_growth_spruce_taiga", "windswept_hills",
                     "windswept_gravelly_hills", "windswept_forest", "stony_shore"], "cool"),
    **dict.fromkeys(["plains", "sunflower_plains", "forest", "flower_forest", "birch_forest", "old_growth_birch_forest",
                     "dark_forest", "meadow", "cherry_grove", "river", "swamp", "mushroom_fields", "beach", "ocean",
                     "deep_ocean"], "temperate"),
    **dict.fromkeys(["jungle", "sparse_jungle", "bamboo_jungle", "mangrove_swamp", "lukewarm_ocean",
                     "deep_lukewarm_ocean", "warm_ocean"], "warm"),
    **dict.fromkeys(["desert", "savanna", "savanna_plateau", "windswept_savanna", "badlands", "eroded_badlands",
                     "wooded_badlands"], "arid"),
    **dict.fromkeys(["lush_caves", "dripstone_caves", "deep_dark"], None),
}
CAVE_BIOMES = {"lush_caves", "dripstone_caves", "deep_dark"}
SALT_BIOMES = {"ocean", "deep_ocean", "frozen_ocean", "deep_frozen_ocean", "cold_ocean", "deep_cold_ocean",
               "lukewarm_ocean", "deep_lukewarm_ocean", "warm_ocean", "beach", "snowy_beach", "stony_shore"}
FRESH_BIOMES = {"river", "frozen_river", "swamp", "mangrove_swamp"}
BRACKISH = {"mangrove_swamp"}                                  # both kinds

# Vanilla 1.21.1 biome tags that Cobblemon's tags include (data/minecraft/tags/worldgen/biome). The Minecraft jar is
# not in this repository, so these are written out here; they are the stock tag contents for 1.21.1.
VANILLA_TAGS = {
    "is_badlands": ["badlands", "eroded_badlands", "wooded_badlands"],
    "is_beach": ["beach", "snowy_beach"],
    "is_deep_ocean": ["deep_frozen_ocean", "deep_cold_ocean", "deep_ocean", "deep_lukewarm_ocean"],
    "is_ocean": ["#is_deep_ocean", "frozen_ocean", "ocean", "cold_ocean", "lukewarm_ocean", "warm_ocean"],
    "is_end": [],
    "is_nether": [],
    "is_forest": ["forest", "flower_forest", "birch_forest", "old_growth_birch_forest", "dark_forest", "grove"],
    "is_hill": ["windswept_hills", "windswept_forest", "windswept_gravelly_hills"],
    "is_jungle": ["bamboo_jungle", "jungle", "sparse_jungle"],
    "is_mountain": ["meadow", "frozen_peaks", "jagged_peaks", "stony_peaks", "snowy_slopes", "cherry_grove"],
    "is_river": ["river", "frozen_river"],
    "is_savanna": ["savanna", "savanna_plateau", "windswept_savanna"],
    "is_taiga": ["taiga", "snowy_taiga", "old_growth_pine_taiga", "old_growth_spruce_taiga"],
    "is_overworld": [b for b in BIOME_CLIMATE],
}
# Cobblemon tags whose vanilla resolution is empty but whose meaning is a country: a species native to them is
# given that climate rather than falling to the type rule.
TAG_CLIMATE = {"cobblemon:is_volcanic": "arid"}

# The place side, this audit's own table: paint preset (data/regions.json paint_presets) -> climate, per band where
# the preset has height bands. Every preset in regions.json must be here (an unknown one fails closed).
PRESET_CLIMATE = {
    **dict.fromkeys(["alpine_peaks", "snowy_peak", "glacier_trough", "glacier_foot", "cirque", "crags",
                     "snowy_taiga"], "cold"),
    **dict.fromkeys(["taiga_dense", "taiga_sparse", "mixed_woods", "rift_floor"], "cool"),
    **dict.fromkeys(["heath_shrub", "coast_scrub", "swamp", "swamp_edge", "forest", "forest_sparse", "birch_woods",
                     "birch_shore", "dark_forest", "flower_meadow", "blossom", "plains", "sunflower_plains", "lake",
                     "mushroom"], "temperate"),
    **dict.fromkeys(["jungle", "sparse_jungle"], "warm"),
    # the Craters are volcanic: hot and dry whatever biome id the paint borrows for them
    **dict.fromkeys(["savanna", "desert", "badlands_top", "badlands_eroded", "volcanic", "volcanic_rim",
                     "desert_isle", "sandstone_uplands"], "arid"),
}
# The water a place's water entries can stand in. Every sub-region has fresh water (its lakes, ponds, tarns, creeks,
# marshes); it has the SEA too when one of its data/regions.json boundaries is a coast (a land/water edge with no
# neighbour) and the sub-region is on an island or lies within twice the polygon tolerance of a marine region's
# polygon (each polygon is simplified by up to geometry.polygon_tolerance_blocks, so two outlines of one coastline
# can stand that far apart, twice). A coast that is not near the sea is a lake shore. Marine bands are salt only;
# waterways fresh only.
WATER_POSITIONS = {"submerged", "surface", "seafloor", "fishing"}
MARINE_TEMPERATURE = {"cold": "cold", "temperate": "temperate", "warm": "warm"}

REGIONAL = [("alolan", ("alolan", "alola")), ("galarian", ("galarian", "galar")), ("hisuian", ("hisuian", "hisui")),
            ("paldean", ("paldean", "paldea")), ("valencian", ("valencian",))]

# ------------------------------------------------------------------------------------------- the rulings
# (place, species) -> this audit's ruling on a misfit no owner placement covers. Each is a defect for the content
# side (data/encounter_design.json), recorded rather than fixed (the auditor does not edit data). Filled from the
# 2026-10-04 run; a ruling whose entry now fits is STALE and fails.
_SEALS = ("defect (data/encounter_design.json lower_trough water + heart): Spheal's line is native in the jar only to "
          "is_frozen_ocean / is_cold_ocean, a SEA species, and the Lower Trough's lake is fresh -- the trough's "
          "sub-region lies 1,193 blocks from the nearest marine region polygon and drains to Lake Tilpey. The builder "
          "kept it for judgement; it is not an owner placement (section 5's table is the design's, not the owner's). "
          "Piplup's line, beside it, FITS: its own natives include fresh cold water")
_RIFT = ("defect (data/encounter_design.json, the Rift tables): native only to is_desert / is_badlands (arid) in the "
         "jar, and the Rift floor is painted rift_floor = windswept_gravelly_hills, a cool gravel country two steps "
         "from arid. The builder kept it for judgement; no owner placement covers it")
_SKARMORY = ("defect (data/encounter_design.json): Skarmory is native in the jar only to is_badlands / is_desert / "
             "is_sky -- arid -- and stands here on a cold alpine summit, three steps away. Not in the builder's sweep; "
             "a mountain bird by the games' lore, but this audit's standard is the jar, and an exception is the "
             "owner's to declare")
_CREEK = ("defect (data/spawns.json, the hand-authored mt_clay_outflow waterway entries, which build_encounters copies "
          "through untouched): Paldean Wooper and Clodsire are native in the jar only to is_savanna / is_arid / "
          "has_block/mud -- hot -- and the creek runs through foothill_woods (mixed_woods, cool), two steps away, as "
          "well as north_west_coast (temperate, which alone would fit). Not in the builder's sweep")
KNOWN = {
    ("lower_trough", "spheal"): _SEALS,
    ("lower_trough", "sealeo"): _SEALS,
    ("lower_trough", "walrein"): _SEALS,
    ("rift_south_west_arm", "cubone"): _RIFT,
    ("rift_south_west_arm", "marowak"): _RIFT,
    ("rift_south_west_arm", "hippowdon"): _RIFT + " (Hippowdon, the arm's heart presence, was not on the builder's list)",
    ("rift_south_east_arm", "flygon"): _RIFT,
    ("rift_trunk", "garganacl"): _RIFT,
    ("the_crags", "skarmory"): _SKARMORY,
    ("the_tri_peaks", "skarmory"): _SKARMORY,
    ("mt_clay_outflow", "clodsire"): _CREEK,
    ("mt_clay_outflow", "wooper paldean"): _CREEK,
}


class AuditError(Exception):
    pass


def regional(tokens):
    for name, stems in REGIONAL:
        for t in tokens:
            t = t.lower()
            if t in stems or t.startswith("region_bias=") and t.split("=", 1)[1] in stems or \
                    any(t == s + "bias" for s in stems):
                return name
    return None


def species_key(pokemon):
    """'sandshrew alolan' -> ('sandshrew', 'alolan'); every other aspect (alpha, held items, colours) is not a
    country and is dropped."""
    parts = pokemon.split()
    return parts[0].lower(), regional(parts[1:])


# ------------------------------------------------------------------------------------------- the jar
class Jar:
    def __init__(self, path):
        self.path = Path(path)
        self.z = zipfile.ZipFile(self.path)
        self.names = self.z.namelist()
        self._tags = {}
        self.natives = defaultdict(lambda: {"biomes": set(), "water_biomes": set(), "cave": False,
                                            "climates": set(), "entries": 0})
        self.species = {}
        self.presets = {}
        for n in self.names:
            if n.startswith("data/cobblemon/spawn_detail_presets/") and n.endswith(".json"):
                try:
                    self.presets[Path(n).stem] = self._json(n)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        self._load_species()
        self._load_spawns()

    def _json(self, name):
        return json.loads(self.z.read(name).decode("utf-8"))

    def _load_species(self):
        for n in self.names:
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                try:
                    d = self._json(n)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                key = Path(n).stem.lower()
                rec = {"types": {d.get("primaryType"), d.get("secondaryType")} - {None},
                       "eggs": set(d.get("eggGroups") or []), "evolutions": d.get("evolutions") or [],
                       "forms": {}}
                for f in d.get("forms") or []:
                    reg = regional(f.get("aspects") or [])
                    if reg:
                        rec["forms"][reg] = {"types": {f.get("primaryType", d.get("primaryType")),
                                                       f.get("secondaryType")} - {None}}
                self.species[key] = rec

    def tag(self, ref):
        """Resolve a biome reference to vanilla biome ids (without namespace)."""
        ref = ref.lstrip("#")
        if ref in self._tags:
            return self._tags[ref]
        self._tags[ref] = set()                       # cycle guard
        ns, path = ref.split(":", 1) if ":" in ref else ("minecraft", ref)
        out = set()
        if ns == "minecraft" and path in VANILLA_TAGS:
            for v in VANILLA_TAGS[path]:
                out |= self.tag("minecraft:" + v[1:]) if v.startswith("#") else {v}
        elif ns == "cobblemon":
            name = "data/cobblemon/tags/worldgen/biome/%s.json" % path
            if name in self.names:
                for v in self._json(name)["values"]:
                    if isinstance(v, dict):
                        if v.get("required", True) is False:
                            continue
                        v = v["id"]
                    out |= self.biome_ref(v)
        self._tags[ref] = out
        return out

    def biome_ref(self, v):
        if v.startswith("#"):
            return self.tag(v)
        ns, path = v.split(":", 1) if ":" in v else ("minecraft", v)
        return {path} if ns == "minecraft" and path in BIOME_CLIMATE else set()

    def _load_spawns(self):
        for n in self.names:
            if not (n.startswith("data/cobblemon/spawn_pool_world/") and n.endswith(".json")):
                continue
            try:
                doc = self._json(n)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if doc.get("enabled") is False:
                continue
            for s in doc.get("spawns") or []:
                who = [s["pokemon"]] if s.get("pokemon") else [h["pokemon"] for h in s.get("herdablePokemon") or []]
                for p in who:
                    self._add(species_key(p), s)

    def _add(self, key, s):
        c = s.get("condition") or {}
        refs = list(c.get("biomes") or [])
        for pr in s.get("presets") or []:            # a preset's condition is part of the entry's (salt, lava, ...)
            refs += ((self.presets.get(pr) or {}).get("condition") or {}).get("biomes") or []
        biomes, climates = set(), set()
        for r in refs:
            got = self.biome_ref(r)
            biomes |= got
            if not got and r.lstrip("#") in TAG_CLIMATE:
                climates.add(TAG_CLIMATE[r.lstrip("#")])
        nat = self.natives[key]
        nat["entries"] += 1
        nat["biomes"] |= biomes
        nat["climates"] |= climates | {BIOME_CLIMATE[b] for b in biomes if BIOME_CLIMATE[b]}
        if s.get("spawnablePositionType") in WATER_POSITIONS:
            nat["water_biomes"] |= biomes
        if biomes & CAVE_BIOMES or s.get("spawnablePositionType", "grounded") == "grounded" and (
                c.get("canSeeSky") is False or c.get("maxSkyLight", 15) <= 7 or
                (c.get("maxY") is not None and c["maxY"] <= 50)):
            nat["cave"] = True

    def info(self, key):
        """(climates, water kinds, cave capable, basis) for a species key; falls back to the base form's natives
        only when the form has no spawn data of its own, and says so."""
        name, reg = key
        nat = self.natives.get(key)
        basis = "jar natives"
        if (nat is None or not nat["climates"]) and reg:
            base = self.natives.get((name, None))
            if base and base["climates"]:
                nat, basis = base, "jar natives of the base form (the %s form has none)" % reg
        if nat and nat["climates"]:
            return nat["climates"], water_kinds(nat), nat["cave"], basis
        if nat and nat["biomes"] and nat["biomes"] <= CAVE_BIOMES:
            return set(LADDER), water_kinds(nat), True, "jar natives are caves only (%s): underground has no country" % (
                "/".join(sorted(nat["biomes"])))
        rec = self.species.get(name)
        if rec is None:
            raise AuditError("species %r is not in the jar" % name)
        types = rec["forms"].get(reg, rec)["types"] if reg else rec["types"]
        clim = {"cold", "cool", "temperate", "warm", "arid"}
        if "ice" in types:
            clim = {"cold", "cool"}
        elif "fire" in types:
            clim = {"temperate", "warm", "arid"}
        eggs = rec["eggs"]
        kinds = set()
        if eggs and eggs <= {"water_1", "water_2", "water_3"} and "water" in types:
            kinds = {"salt", "fresh"}
        return clim, kinds, (nat or {}).get("cave", False), \
            "type and egg group (no vanilla natural spawn: types %s, eggs %s)" % (
                "/".join(sorted(types)), "/".join(sorted(eggs)) or "none")

    def family(self, name):
        """name and everything it evolves into, walked forward through the jar."""
        out, todo = set(), [name]
        while todo:
            n = todo.pop()
            if n in out or n not in self.species:
                continue
            out.add(n)
            todo += [e["result"].split()[0].lower() for e in self.species[n]["evolutions"] if e.get("result")]
        return out


def water_kinds(nat):
    """The waters a species is native to: from its water-position entries, else from all its entries' biomes where
    those are water biomes. Land-biome water entries are lakes, so fresh. Empty = no opinion."""
    kinds = set()
    if nat["water_biomes"]:
        for b in nat["water_biomes"]:
            if b in SALT_BIOMES:
                kinds.add("salt")
            elif BIOME_CLIMATE.get(b, "x") is not None:
                kinds.add("fresh")
            if b in BRACKISH:
                kinds |= {"salt", "fresh"}
        return kinds
    for b in nat["biomes"]:
        if b in SALT_BIOMES:
            kinds.add("salt")
        if b in FRESH_BIOMES:
            kinds.add("fresh")
        if b in BRACKISH:
            kinds |= {"salt", "fresh"}
    return kinds


# ------------------------------------------------------------------------------------------- the places
def point_in(x, z, ring):
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, zi = ring[i]
        xj, zj = ring[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi:
            inside = not inside
        j = i
    return inside


def seg_distance(px, pz, a, b):
    ax, az = a
    dx, dz = b[0] - ax, b[1] - az
    n = dx * dx + dz * dz
    t = 0.0 if n == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / n))
    return ((px - ax - t * dx) ** 2 + (pz - az - t * dz) ** 2) ** 0.5


def ring_distance(ring, others):
    """The least distance from any vertex of `ring` to any edge of the rings in `others`."""
    best = float("inf")
    for x, z in ring:
        for o in others:
            for i in range(len(o)):
                best = min(best, seg_distance(x, z, o[i], o[(i + 1) % len(o)]))
    return best


class Places:
    def __init__(self, regions, waterways=None, spawns=None):
        presets = regions["paint_presets"]
        unknown = sorted(set(presets) - set(PRESET_CLIMATE))
        if unknown:
            raise AuditError("paint presets with no climate in this audit's table: %s" % ", ".join(unknown))
        self.presets = presets
        self.sub = {s["id"]: s for s in regions["subregions"]}
        self.marine_region = {m["id"]: m for m in regions.get("marine_regions") or []}
        self.band_region = {}
        for zone in (spawns or {}).get("marine_zones") or []:
            for b in zone.get("bands") or []:
                self.band_region[b["id"]] = zone.get("marine_region")
        self.waterways = {w["id"]: w for w in (waterways or {}).get("waterways") or []}
        reach = 2 * regions["geometry"]["polygon_tolerance_blocks"]
        islands = {s for g in regions["regions"] if g.get("region_class") == "island" for s in g.get("subregions") or []}
        sea_rings = [ring for m in regions.get("marine_regions") or [] for ring in m.get("polygons") or []]
        self.sea = set()
        for sid, s in self.sub.items():
            if not any(b.get("basis") == "coast" for b in s.get("boundaries") or []):
                continue
            if sid in islands or any(ring_distance(r, sea_rings) <= reach for r in s["polygons"]):
                self.sea.add(sid)

    def sub_ids(self):
        return sorted(self.sub, key=len, reverse=True)

    def place(self, kind, pid):
        """{'climates': {climate}, 'water': {'salt', 'fresh'}, 'ground_p10': y or None, 'label': str}"""
        if kind == "subregions":
            s = self.sub.get(pid)
            if s is None:
                raise AuditError("compiled place %s is not a data/regions.json sub-region" % pid)
            preset = s["paint"]["preset"]
            return {"climates": {PRESET_CLIMATE[preset]}, "water": {"fresh", "salt"} if pid in self.sea else {"fresh"},
                    "ground_p10": (s.get("measured") or {}).get("elevation", {}).get("p10"),
                    "label": "%s (%s, %s)" % (pid, preset, PRESET_CLIMATE[preset])}
        if kind == "marine":
            reg = self.marine_region.get(self.band_region.get(pid))
            if reg is None:
                raise AuditError("marine band %s names no marine region" % pid)
            t = (reg.get("climate") or {}).get("temperature")
            if t not in MARINE_TEMPERATURE:
                raise AuditError("marine region %s has temperature %r, not one this audit classes" % (reg["id"], t))
            return {"climates": {MARINE_TEMPERATURE[t]}, "water": {"salt"}, "ground_p10": None,
                    "label": "%s (%s sea, %s)" % (pid, reg["id"], t)}
        if kind == "waterways":
            w = self.waterways.get(pid)
            if w is None:
                raise AuditError("waterway %s is not in data/waterways.json" % pid)
            crossed = set()
            for x, z in w["polyline"]:
                for sid, s in self.sub.items():
                    if any(point_in(x, z, ring) for ring in s["polygons"]):
                        crossed.add(sid)
            if not crossed:
                raise AuditError("waterway %s crosses no sub-region" % pid)
            clim = {PRESET_CLIMATE[self.sub[c]["paint"]["preset"]] for c in crossed}
            return {"climates": clim, "water": {"fresh"}, "ground_p10": None,
                    "label": "%s (creek through %s)" % (pid, ", ".join(sorted(crossed)))}
        raise AuditError("compiled folder %s is not one this audit knows" % kind)


# ------------------------------------------------------------------------------------------- the owner's starters
def owner_starters(doc_text, jar, families=27):
    """{species: quote} for every family in ENCOUNTER_DESIGN.md section 11's table (the owner, 2026-10-02)."""
    m = re.search(r"^## 11\..*?(?=^## |\Z)", doc_text, re.S | re.M)
    if not m:
        raise AuditError("ENCOUNTER_DESIGN.md has no section 11 (the owner's starters)")
    out = {}
    for line in m.group(0).splitlines():
        row = re.match(r"^\|\s*(\d)\s*\|(.*)\|\s*$", line)
        if not row:
            continue
        for name, where in re.findall(r"([A-Z][a-z]+): ([^.]+)", row.group(2)):
            quote = "section 11, leg %s: \"%s: %s.\"" % (row.group(1), name, where.strip())
            for sp in jar.family(name.lower()):
                out.setdefault(sp, quote)
    if len(set(out.values())) != families:
        raise AuditError("section 11 names %d starter families, not %d" % (len(set(out.values())), families))
    return out


# ------------------------------------------------------------------------------------------- the pack
HEART = re.compile(r"_h\d{4}_")


def load_pack(pack, sub_ids):
    """[(kind, place, entry, heart?)] for every spawn_pool_world entry; a route entry's place is the sub-region its
    id names."""
    base = Path(pack) / "data" / "cobblers" / "spawn_pool_world"
    if not base.is_dir():
        raise AuditError("%s has no data/cobblers/spawn_pool_world" % pack)
    out = []
    for f in sorted(base.rglob("*.json")):
        kind = f.parent.name
        for s in json.loads(f.read_text(encoding="utf-8"))["spawns"]:
            if kind == "routes":
                place = next((x for x in sub_ids if "_%s_" % x in s["id"]), None)
                if place is None:
                    raise AuditError("route entry %s names no sub-region" % s["id"])
                out.append(("subregions", place, s, False))
            else:
                out.append((kind, f.stem, s, bool(HEART.search(s["id"]))))
    if not out:
        raise AuditError("%s compiles no spawn entries" % pack)
    return out


HABITAT_KEYS = ("minY", "maxY", "canSeeSky", "biomes", "neededNearbyBlocks")


def env_of(place, cond, position, jar):
    """(climates, water?, underground?) the entry can reach, from the place and the entry's own conditions.

    minY and maxY move an entry between countries only by taking it underground: every preset's height bands share
    one climate in PRESET_CLIMATE (alpine_peaks is grove, snowy slopes and jagged peaks, all cold; badlands_top is
    badlands and wooded badlands, both arid), so a summit line keeps the place's climate."""
    hi = cond.get("maxY")
    climates = set(place["climates"])
    if cond.get("biomes"):
        named = set()
        for b in cond["biomes"]:
            named |= jar.biome_ref(b)
        climates = {BIOME_CLIMATE[b] for b in named if BIOME_CLIMATE[b]} or climates
    water = position in WATER_POSITIONS or "minecraft:water" in (cond.get("neededNearbyBlocks") or [])
    under = position not in WATER_POSITIONS and (cond.get("canSeeSky") is False or (
        hi is not None and place["ground_p10"] is not None and hi < place["ground_p10"]))
    return climates, water, under


def judge_env(info, climates, water, under, water_kind):
    """(fits?, why) for one environment."""
    nat_clim, kinds, cave, _basis = info
    if under:
        if cave:
            return True, "underground, and the species is cave-native"
    far = []
    for c in sorted(climates, key=LADDER.get):
        best = min(distance(n, c) for n in nat_clim)
        if best > 1:
            far.append("%s place, %d steps from its nearest native climate" % (c, best))
    if far:
        return False, "; ".join(far)
    if water and kinds and not kinds & water_kind:
        return False, "%s water only, and its own water natives are only %s" % (
            "/".join(sorted(water_kind)), "/".join(sorted(kinds)))
    return True, "native to %s" % "/".join(sorted(nat_clim, key=LADDER.get))


def audit(pack, jar, regions, waterways, spawns, doc_text, known=None, starter_families=27):
    """(rows, stale KNOWN keys). Every compiled entry group gets one row with its class and why."""
    known = KNOWN if known is None else known
    places = Places(regions, waterways, spawns)
    starters = owner_starters(doc_text, jar, starter_families)
    groups = defaultdict(lambda: {"count": 0, "heart": False, "ids": []})
    for kind, pid, s, heart in load_pack(pack, places.sub_ids()):
        cond = {k: v for k, v in (s.get("condition") or {}).items() if k in HABITAT_KEYS}
        key = (kind, pid, s["pokemon"], s.get("spawnablePositionType") or "grounded", json.dumps(cond, sort_keys=True))
        g = groups[key]
        g["count"] += 1
        g["heart"] |= heart
        if len(g["ids"]) < 3:
            g["ids"].append(s["id"])
    rows, used_known = [], set()
    for (kind, pid, pokemon, pos, condj), g in sorted(groups.items()):
        cond = json.loads(condj)
        place = places.place(kind, pid)
        skey = species_key(pokemon)
        info = jar.info(skey)
        wkind = place["water"]
        base_water = pos in WATER_POSITIONS or "minecraft:water" in (cond.get("neededNearbyBlocks") or [])
        ok, why = judge_env(info, place["climates"], base_water, False, wkind)
        cls = "FIT"
        if not ok:
            ok2, why2 = judge_env(info, *env_of(place, cond, pos, jar), wkind)
            if ok2:
                cls, why = "FIT-BY-CONDITION", "%s; within its conditions %s: %s" % (why, condj, why2)
            elif skey[0] in starters:
                cls, why = "JUDGED", "%s; the owner's placement, %s" % (why, starters[skey[0]])
            elif (pid, pokemon) in known:
                cls, why = "KNOWN", "%s; ruling: %s" % (why, known[(pid, pokemon)])
                used_known.add((pid, pokemon))
            else:
                cls = "MISFIT"
        rows.append({"class": cls, "kind": kind, "place": place["label"], "place_id": pid, "species": pokemon,
                     "position": pos, "conditions": cond, "heart": g["heart"], "entries": g["count"],
                     "basis": info[3], "native_climates": sorted(info[0], key=LADDER.get),
                     "water_kinds": sorted(info[1]), "why": why, "example_ids": g["ids"]})
    stale = sorted(set(known) - used_known)
    return rows, stale


def find_jar():
    sys.path.insert(0, str(TOOLS))
    import battle_sim                                   # only its jar search; nothing it computes is used
    return battle_sim.find_jar()


def ensure_pack(pack):
    """Compile the pack with the repo's compiler when build/ has none (it is gitignored)."""
    if (Path(pack) / "data" / "cobblers" / "spawn_pool_world").is_dir():
        return False
    r = subprocess.run([sys.executable, str(TOOLS / "compile_spawns.py"), "--out", str(pack)], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode:
        raise AuditError("compile_spawns.py failed:\n%s" % (r.stdout[-1500:] + r.stderr[-1500:]))
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default=str(DEFAULT_PACK))
    p.add_argument("--jar", default=None)
    p.add_argument("--regions", default=str(ROOT / "data" / "regions.json"))
    p.add_argument("--waterways", default=str(ROOT / "data" / "waterways.json"))
    p.add_argument("--spawns", default=str(ROOT / "data" / "spawns.json"))
    p.add_argument("--design-doc", default=str(DESIGN_DOC))
    p.add_argument("--json", default=None, help="write every row here")
    p.add_argument("--show", default="MISFIT,KNOWN,JUDGED,STALE",
                   help="classes to print row by row (comma separated; ALL for every row)")
    a = p.parse_args(argv)
    load = lambda f: json.loads(Path(f).read_text(encoding="utf-8"))  # noqa: E731
    try:
        compiled = ensure_pack(a.pack) if Path(a.pack) == DEFAULT_PACK else False
        jar = Jar(a.jar or find_jar())
        rows, stale = audit(a.pack, jar, load(a.regions), load(a.waterways), load(a.spawns),
                            Path(a.design_doc).read_text(encoding="utf-8"))
    except AuditError as ex:
        print("FAIL: %s" % ex)
        return 1
    if compiled:
        print("compiled %s first (it was absent)" % a.pack)
    if a.json:
        Path(a.json).write_text(json.dumps({"rows": rows, "stale_known": [list(k) for k in stale]}, indent=1),
                                encoding="utf-8")
    counts = defaultdict(int)
    for r in rows:
        counts[r["class"]] += 1
    show = set(x.strip() for x in a.show.split(","))
    for r in rows:
        if "ALL" in show or r["class"] in show:
            print("%-16s %-44s %-20s %-9s %s" % (r["class"], r["place"], r["species"] + (" (heart)" if r["heart"] else ""),
                                                 r["position"], r["why"]))
    for k in stale:
        print("STALE            KNOWN ruling for %s at %s: the entry no longer misfits (or is gone); remove it" % (k[1], k[0]))
    by_type = sum(1 for r in rows if r["basis"].startswith("type"))
    print("judged %d compiled entry groups (%d entries) from %s against %s: %s; %d judged by type (no vanilla native)"
          % (len(rows), sum(r["entries"] for r in rows), a.pack, Path(jar.path).name,
             ", ".join("%s %d" % (c, counts[c]) for c in ("FIT", "FIT-BY-CONDITION", "JUDGED", "KNOWN", "MISFIT")),
             by_type))
    bad = counts["MISFIT"] + len(stale)
    print("FAIL: %d unjudged misfit(s), %d stale ruling(s)" % (counts["MISFIT"], len(stale)) if bad else
          "OK: no unjudged misfit")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
