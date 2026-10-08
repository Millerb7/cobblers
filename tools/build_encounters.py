#!/usr/bin/env python
"""Expand data/encounter_design.json into data/spawns.json's generated sections.

docs/mechanics/ENCOUNTER_DESIGN.md is the rule book and data/encounter_design.json the authored tables. This tool
does the arithmetic between them and data/spawns.json, which tools/compile_spawns.py compiles exactly as before.
It owns three parts of data/spawns.json and nothing else:

  sub-region rosters   for every design table: the entries with mechanism spawn_json_coordinate_boxes scoped to that
                       sub-region, and the subregions[] record's entries mirror and level_band
  Victory Road pools   for every vrc_* pool in the design's habitats: its habitats[] record's entries and level_band,
                       and its habitat_block entries
  route selection      route_species_selection, per route, from the sub-regions its corridor crosses
  held items           the held_items field of every spawn_pool_world entry (sub-region, marine, waterway), generated
                       or copied through, from rules.held_items (the owner, 2026-10-05: wild held items, a find and not
                       a farm); tools/compile_spawns.py writes it as the Cobblemon 1.8.0 spawn detail's heldItems.
                       Fails closed on an item the jar does not name, a listed species that spawns in no such entry,
                       a species past max_total_percent, and held_items on a habitat-block entry

Every other entry and habitat (the elder and sapling bird nests, the Route 1 mansion, the unplaced pools, the Windward
Sea's marine bands, the Mt Clay outflow waterway) is copied through untouched, in its place.

The expansion (ENCOUNTER_DESIGN.md sections 2-4, 7a):

  family     the named species walked FORWARD through the Cobblemon jar's evolutions; a branch splits its stage's
             weight evenly among the branches that survive. Naming an evolved species starts the family there. A
             family keeps its form: a plain Koffing never branches into Galarian Weezing, an Alolan Sandshrew's line
             stays Alolan.
  levels     the table's band is its tier's band, or the table's own `levels` inside it. A stage spawns from the level
             it evolves at (or the band's floor) to stage_overlap_levels past the level it would evolve at again (or
             the band's top); a stage whose range is empty is not spawned. A find (and everything after a non-level
             evolution) spawns only in the upper half of the band.
  methods    an evolution is "level" when it is a level_up with a level requirement and nothing but time, stat or
             property requirements beside it; a trade appears in the wild from tier 7, every other non-level method
             from tier 6, and never below.
  weights    the role's weight (or an explicit third element) is the family's; maturity[tier] of it goes to the
             evolved stages, the final one taking (tier - 3) / 6 of that, held to [0.2, 0.9]; a family with one
             surviving stage puts it all there. Rounded to 0.1; a stage that rounds to nothing is dropped.
  position   tools/position_types.choose() for land families. A family in a table's `water` half stands in the water:
             the stage's most-used upstream water position, else the named species', else "submerged" -- unless the
             design gives it neededNearbyBlocks water, which is the design asking for the shore (grounded).
             An authored spawnable_position_authored in the existing file is carried by (scope, species).
  biomes     none: a sub-region is the place identity, so the old biome filters are dropped (biomes: []).
  conditions passed through from the design's family entries; only keys and blocks already in the data
             (timeRange, isRaining, maxY, neededNearbyBlocks water, neededBaseBlocks sand), contract C4.

hearts (ENCOUNTER_DESIGN.md section 10): a design table's optional `heart`, a summit (minY, a verified Cobblemon
1.8.0 condition key, set here on the heart's entries only) or a focus (a data/landmarks.json landmark, or an x, z with
a why, and a radius). Its entries carry the heart's geometry for tools/compile_spawns.py, which lays them over the
heart's cells only and never into a corridor. Its families name the bigger stage, spawn on the upper half of the band
from the level they evolve at, matured rules.hearts.maturity_step tiers further; its presences (uncommon) run from
the band's top, or the level they evolve at, to rules.hearts.next_cap. Fails closed on a presence in a base table, a
presence in the common bucket, a presence past the next cap, a find in a heart, and a heart whose share of spawn
chance above the cap (base and heart rows together, the audit's chance rule) exceeds rules.hearts.above_cap_max_share.
Every heart entry carries "alpha": rules.hearts.alpha (the owner, 2026-10-05: the bosses are alphas), which
tools/compile_spawns.py writes as alpha=true; fails closed on a copied-through heart entry whose flag differs, and on
an alpha flag outside a heart. A native alpha re-levels to a nearby player's party (rules.hearts.alpha_level_matching).

route_species_selection: per route, the sub-regions data/routes.json's geography transitions cross; from each such
table only families in rules.corridor_roles (never a find), plus rules.corridor_rare_min of the crossed on-path
tables' rare- and ultra-role species, reserved first (the owner, 2026-10-05: every area has a rare and an ultra-rare). Each species is scored by its chance in the
table (the audit's rule: bucket share renormalised over the buckets its context holds, times weight over the bucket's
weight) times the corridor length in that table; every crossed table's water species and its corridor_table_min
likeliest land species are kept (past corridor_species_limit if need be, up to corridor_species_ceiling), then the
rest by score until corridor_species_limit. tools/compile_spawns.py then compiles a corridor species only if it is listed.

Fails closed (exit 1, a message per problem): a species not in the jar; a species the client draws as the substitute
doll (modpack/manifest/client-pack-atm-subset.json species); a spawn above its tier's cap or outside its band; a table
band outside its tier's; a design table that is not a data/regions.json sub-region, or a sub-region with no design
table; a condition outside the vocabulary; one species twice in a table with different positions or buckets; a
habitat species with a space (a habitat pool species is a bare id); a corridor whose kept water species exceed the
limit.

  python tools/build_encounters.py            # rewrite data/spawns.json's generated sections
  python tools/build_encounters.py --check    # exit 1 if data/spawns.json is not what the design produces
  python tools/build_encounters.py --jar <Cobblemon-fabric-1.8.0+1.21.1.jar>

Reads data/encounter_design.json, data/spawns.json, data/regions.json, data/routes.json, the client-doll list and the
Cobblemon jar (tools/battle_sim.py find_jar). Writes data/spawns.json only. It decides no position in the world and
reads no world. Proves validity of the data, not behaviour in game.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import battle_sim  # noqa: E402
import position_types  # noqa: E402

DESIGN = ROOT / "data" / "encounter_design.json"
SPAWNS = ROOT / "data" / "spawns.json"
REGIONS = ROOT / "data" / "regions.json"
ROUTES = ROOT / "data" / "routes.json"
DOLLS = ROOT / "modpack" / "manifest" / "client-pack-atm-subset.json"
LANDMARKS = ROOT / "data" / "landmarks.json"

SURFACE = "spawn_json_coordinate_boxes"
HABITAT = "habitat_block"
WATER_POS = ("submerged", "surface", "seafloor")
BUCKET_P = {"common": 88.5, "uncommon": 10.0, "rare": 1.2, "ultra-rare": 0.3}
LEVEL_SIDE_REQUIREMENTS = {"level", "time_range", "stat_compare", "stat_equal", "properties"}
# contract C4: the condition keys and blocks already in the data (ENCOUNTER_DESIGN.md section 9)
CONDITION_VOCAB = {"timeRange": {"night"}, "isRaining": {True}, "maxY": int,
                   "neededNearbyBlocks": {"minecraft:water"}, "neededBaseBlocks": {"#minecraft:sand", "#c:sand"}}
ASPECT_ADJ = {"alolan": "Alolan", "galarian": "Galarian", "hisuian": "Hisuian", "paldean": "Paldean"}

# This tool decides nowhere anything goes; it reads no world.
WORLD_READS = set()


class DesignError(Exception):
    pass


def dumps(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# ------------------------------------------------------------------ the jar

# The vanilla items CobblemonHeldItemManager remaps to a Showdown item (docs/research/ITEMS_ABILITY_EV_HELD_MEGA.md
# section 3: Items.BONE -> thickclub, Items.SNOWBALL -> snowball, Items.GOLD_BLOCK -> bignugget). A minecraft: item
# outside these has no battle effect, so rules.held_items may not name one.
VANILLA_HELD = {"minecraft:bone", "minecraft:snowball", "minecraft:gold_block"}
# the Nether's tables (data/encounter_design.json "nether"): one per (table, ring), keyed on the dimension, a biome or a
# structure, and the ring's boxes; compiled to spawn_pool_world/nether/ by tools/compile_spawns.py build_nether
NETHER = "nether_ring_boxes"
# the spawn mechanisms tools/compile_spawns.py writes as spawn_pool_world details, which carry heldItems
POOL_WORLD = (SURFACE, "marine_coordinate_boxes", "waterway_coordinate_boxes", NETHER)
# The blocks a Nether heart may need nearby (Cobblemon 1.8.0 AreaTypeSpawningCondition.neededNearbyBlocks: the position
# fails unless one listed block is among its nearby blocks, within maxNearbyBlocksHorizontalRange 4 and
# maxNearbyBlocksVerticalRange 2 in our config/cobblemon/main.json; docs/research/notes/spawn-dimension-condition-1.8.0.md).
# Outside the overworld vocabulary of contract C4 on purpose: every condition naming one also names
# "dimensions": ["minecraft:the_nether"], so a shroomlight or bone block placed in the overworld or the pocket decides
# no encounter there. tests/test_nether_encounters.py holds that pairing.
NETHER_NEARBY = {"minecraft:lava", "minecraft:weeping_vines", "minecraft:weeping_vines_plant", "minecraft:shroomlight",
                 "minecraft:bone_block", "minecraft:magma_block"}
NETHER_KEYS = ("biomes", "structures")


def jar_items(jar):
    """{"cobblemon:<path>"} for every item the jar names in its English lang file (item.cobblemon.<path>)."""
    import zipfile
    with zipfile.ZipFile(jar) as z:
        lang = json.loads(z.read("assets/cobblemon/lang/en_us.json"))
    return {"cobblemon:" + k[len("item.cobblemon."):] for k in lang
            if k.startswith("item.cobblemon.") and "." not in k[len("item.cobblemon."):]}


def held_items_by_species(rules, dex):
    """({species: [{"item", "percentage"}]}, problems) from rules.held_items (the owner, 2026-10-05: wild held items,
    "rare enough to be a find rather than a farm"). Fails closed on an item the jar does not name (or a vanilla item
    Cobblemon does not remap), a class with no percent, and a species whose items sum past max_total_percent."""
    hr = rules.get("held_items")
    if not hr:
        return {}, []
    problems, out = [], {}
    if hr.get("field") != "heldItems":
        problems.append("rules.held_items.field is heldItems (the Cobblemon 1.8.0 PokemonSpawnDetail field), not %r"
                        % hr.get("field"))
    pct = hr.get("percent") or {}
    cap = hr.get("max_total_percent")
    for i, rec in enumerate(hr.get("items") or []):
        item, cls = rec.get("item"), rec.get("class")
        where = "rules.held_items.items[%d] (%s)" % (i, item)
        if cls not in pct or not isinstance(pct[cls], (int, float)) or not 0 < pct[cls] <= 100:
            problems.append("%s: class %r has no percent in (0, 100] in rules.held_items.percent" % (where, cls))
            continue
        ok = item in VANILLA_HELD if str(item).startswith("minecraft:") else item in dex.items
        if not ok:
            problems.append("%s: not an item the Cobblemon jar names%s" % (
                where, " nor a vanilla item it remaps to a held item" if str(item).startswith("minecraft:") else ""))
            continue
        for sp in rec.get("species") or []:
            if not dex.has(sp):
                problems.append("%s: %s is not a species in the Cobblemon jar" % (where, sp))
                continue
            if any(h["item"] == item for h in out.get(sp, [])):
                problems.append("%s: %s holds %s twice" % (where, sp, item))
                continue
            out.setdefault(sp, []).append({"item": item, "percentage": pct[cls]})
    for sp, hs in sorted(out.items()):
        total = sum(h["percentage"] for h in hs)
        if not isinstance(cap, (int, float)) or total > cap:
            problems.append("rules.held_items: %s's items sum to %s%%, past max_total_percent %r" % (sp, total, cap))
    return out, problems


def stamp_held_items(entries, held):
    """Set (or clear) held_items on every entry from the rule: the rule owns the field. Returns (problems, stamped
    species). A habitat-block entry never carries one (its pool spawn is another format)."""
    problems, used = [], set()
    for e in entries:
        if e.get("mechanism") not in POOL_WORLD:
            if "held_items" in e:
                problems.append("%s: held_items on a %s entry; rules.held_items reaches spawn_pool_world entries only"
                                % (e["id"], e.get("mechanism")))
            continue
        hs = held.get(e["species"])
        if hs and e.get("ambient") and e.get("weight", 0) > 0:
            e["held_items"] = [dict(h) for h in hs]
            used.add(e["species"])
        else:
            e.pop("held_items", None)
    return problems, used


class Dex:
    """Species, forms, evolutions and roots from the Cobblemon jar."""

    def __init__(self, jar):
        self.species, _, _ = battle_sim.load_pack(jar)
        self.pre = {}
        for k, sp in self.species.items():
            for ev in sp.get("evolutions") or []:
                r = battle_sim.key((ev.get("result") or "").split()[0])
                if r in self.species and r != k:
                    self.pre.setdefault(r, k)
        self.positions = position_types.upstream_positions(jar)
        self.items = jar_items(jar)

    def split(self, name):
        parts = name.split()
        return battle_sim.key(parts[0]), [p for p in parts[1:] if "=" not in p]

    def has(self, name):
        base, aspects = self.split(name)
        if base not in self.species:
            return False
        return not aspects or self.form(name) is not None

    def form(self, name):
        base, aspects = self.split(name)
        if not aspects:
            return None
        for f in self.species[base].get("forms") or []:
            if set(aspects) <= set(f.get("aspects") or []):
                return f
        return None

    def record(self, name):
        """(species record, form record or None)."""
        base, _ = self.split(name)
        return self.species[base], self.form(name)

    def display(self, name):
        sp, f = self.record(name)
        _, aspects = self.split(name)
        if f is not None and aspects:
            return "%s %s" % (ASPECT_ADJ.get(aspects[0], aspects[0].title()), sp["name"])
        return sp["name"]

    def types(self, name):
        sp, f = self.record(name)
        src = f if f is not None and f.get("primaryType") else sp
        return [t.lower() for t in (src.get("primaryType"), src.get("secondaryType")) if t]

    def family(self, name):
        k, seen = self.split(name)[0], set()
        while k in self.pre and k not in seen:
            seen.add(k)
            k = self.pre[k]
        return k

    def evolutions(self, name):
        """[(result name, method, level, how)] -- one per result species, the most permissive method kept.

        method is "level", "other" or "trade". how is a short text for the eligibility reason.
        """
        sp, f = self.record(name)
        evs = (f.get("evolutions") if f is not None and f.get("evolutions") is not None else sp.get("evolutions")) or []
        best = {}
        for ev in evs:
            res = " ".join(t for t in (ev.get("result") or "").split() if "=" not in t)
            # a family keeps its form: Koffing does not branch into Galarian Weezing, Alolan Sandshrew stays Alolan
            if not res or not self.has(res) or set(self.split(res)[1]) != set(self.split(name)[1]):
                continue
            reqs = ev.get("requirements") or []
            kinds = {r.get("variant") for r in reqs}
            lv = next((r.get("minLevel") for r in reqs if r.get("variant") == "level"), None)
            if ev.get("variant") == "level_up" and lv is not None and kinds <= LEVEL_SIDE_REQUIREMENTS:
                cand = ("level", int(lv), "at level %d" % lv)
            elif ev.get("variant") == "trade":
                cand = ("trade", None, "by trade" + (" holding %s" % _item(reqs) if _item(reqs) else ""))
            else:
                cand = ("other", None, _how(ev, reqs))
            rank = {"level": 0, "other": 1, "trade": 2}
            old = best.get(res)
            if old is None or rank[cand[0]] < rank[old[0]] or (cand[0] == old[0] == "level" and cand[1] < old[1]):
                best[res] = cand
        return [(res, m, lv, how) for res, (m, lv, how) in best.items()]

    def position(self, name, water, nearby_water, named):
        """(position, reason) for one stage."""
        pos, why = position_types.choose(name, self.positions)
        if not water or nearby_water:
            return pos, why
        for cand in (name, named):
            c = self.positions.get(cand.split()[0].lower()) or {}
            wet = [k for k in WATER_POS if c.get(k)]
            if wet:
                best = max(wet, key=lambda k: c[k])
                return best, "a water family: %s's most-used upstream water position" % cand
        return "submerged", "a water family with no upstream water data: submerged"


def _item(reqs):
    r = next((r for r in reqs if r.get("variant") == "held_item"), None)
    return (r.get("itemCondition") or "").split(":")[-1].replace("_", " ") if r else ""


def _how(ev, reqs):
    if ev.get("variant") == "item_interact":
        return "using %s" % (ev.get("requiredContext") or "an item").split(":")[-1].replace("_", " ")
    kinds = [r.get("variant") for r in reqs if r.get("variant") not in ("time_range",)]
    if "friendship" in kinds:
        return "by friendship"
    if "held_item" in kinds:
        return "holding %s" % _item(reqs)
    if "has_move" in kinds or "has_move_type" in kinds:
        return "knowing a move"
    return "by %s" % ", ".join(sorted(set(k for k in kinds if k))) if kinds else "not by level"


# ------------------------------------------------------------------ expansion

def tier_rules(rules, tier):
    t = rules["tiers"].get(str(tier))
    if t is None:
        raise DesignError("tier %s is not in rules.tiers" % tier)
    return t["cap"], tuple(t["band"])


def final_share(rules, tier):
    fs = rules["final_share"]
    return max(fs["min"], min(fs["max"], (tier - 3) / 6.0))


def parse_family(item, rules, where):
    """(species, role, weight override or None, conditions)."""
    if not isinstance(item, list) or len(item) < 2:
        raise DesignError("%s: a family is [species, role, (weight), (conditions)]: %r" % (where, item))
    species, role, weight, cond = item[0], item[1], None, {}
    if role not in rules["roles"]:
        raise DesignError("%s: %s has role %r, not one of %s" % (where, species, role, sorted(rules["roles"])))
    for extra in item[2:]:
        if isinstance(extra, (int, float)) and not isinstance(extra, bool):
            weight = float(extra)
        elif isinstance(extra, dict):
            cond = dict(extra)
        else:
            raise DesignError("%s: %s carries %r, neither a weight nor conditions" % (where, species, extra))
    for k, v in cond.items():
        allowed = CONDITION_VOCAB.get(k)
        if allowed is None:
            raise DesignError("%s: %s uses condition %r, not in the data's vocabulary %s (contract C4)"
                              % (where, species, k, sorted(CONDITION_VOCAB)))
        vals = v if isinstance(v, list) else [v]
        if allowed is int:
            if not all(isinstance(x, int) and not isinstance(x, bool) for x in vals):
                raise DesignError("%s: %s %s=%r is not a whole number" % (where, species, k, v))
        elif not set(vals) <= allowed:
            raise DesignError("%s: %s %s=%r is outside the data's vocabulary %s (contract C4)"
                              % (where, species, k, v, sorted(map(str, allowed))))
    return species, role, weight, cond


def expand_family(dex, rules, tier, band, species, role, weight, where, mtier=None):
    """[(stage name, lo, hi, weight, reason)] for one family. mtier is the tier whose maturity and final share apply
    (an off-path table is matured rules.off_path_maturity_step tiers further, ENCOUNTER_DESIGN.md section 6)."""
    if not dex.has(species):
        raise DesignError("%s: %s is not a species in the Cobblemon jar" % (where, species))
    lo_b, hi_b = band
    half = (lo_b + hi_b + 1) // 2
    overlap = rules["stage_overlap_levels"]
    min_tier = rules["non_level_evolution_min_tier"]
    # a find and an ultra-rare family both spawn on the upper half of the band: the reward for looking (section 4)
    find = role in ("find", "ultra")
    w = weight if weight is not None else float(rules["roles"][role]["weight"])
    # walk forward: node = (name, depth, floor, lo, parent, reason)
    nodes, frontier = [], [(species, 0, half if find else lo_b, half if find else lo_b, None, None)]
    seen = set()
    while frontier:
        name, depth, floor, lo, parent, how = frontier.pop(0)
        if name in seen:
            continue
        seen.add(name)
        evs = dex.evolutions(name)
        lv_next = [lv for _, m, lv, _ in evs if m == "level"]
        hi = min(hi_b, min(lv_next) + overlap) if lv_next else hi_b
        nodes.append({"name": name, "depth": depth, "lo": lo, "hi": hi, "parent": parent, "how": how})
        for res, m, lv, h in evs:
            if m == "level":
                frontier.append((res, depth + 1, floor, max(floor, lv), name, (m, lv, h)))
            elif tier >= min_tier["trade" if m == "trade" else "other"]:
                nf = max(floor, half)
                frontier.append((res, depth + 1, nf, nf, name, (m, None, h)))
    alive = [n for n in nodes if n["lo"] <= n["hi"]]
    depths = sorted({n["depth"] for n in alive})
    mt = mtier or tier
    m = rules["maturity"][str(mt)]
    f = final_share(rules, mt)
    share = {}
    if len(depths) == 1:
        share[depths[0]] = 1.0
    else:
        evolved = [d for d in depths if d > 0]
        pool = 1.0
        if 0 in depths:
            share[0] = 1.0 - m
            pool = m
        if len(evolved) == 1:
            share[evolved[0]] = pool
        else:
            share[evolved[-1]] = pool * f
            for d in evolved[:-1]:
                share[d] = pool * (1 - f) / (len(evolved) - 1)
    out = []
    for n in alive:
        peers = [x for x in alive if x["depth"] == n["depth"]]
        sw = round(w * share[n["depth"]] / len(peers), 1)
        if sw <= 0:
            continue
        if n["parent"] is None:
            reason = ("find: the reason to leave the path, rare bucket, top half of the band (%d-%d)" % (n["lo"], n["hi"])
                      if role == "find" else
                      "ultra-rare: the place's rarest family, ultra-rare bucket, top half of the band (%d-%d)" % (n["lo"], n["hi"])
                      if role == "ultra" else "named %s family, tier %d: the family starts here" % (role, tier))
        else:
            meth, lv, how = n["how"]
            parent = dex.display(n["parent"])
            if meth == "level":
                reason = "evolves from %s at level %d: spawns %d-%d, inside the tier %d band %d-%d" % (
                    parent, lv, n["lo"], n["hi"], tier, lo_b, hi_b)
            else:
                reason = ("evolves from %s %s, not by level: in the wild from tier %d, in the upper half of the band "
                          "(%d-%d)" % (parent, how, min_tier["trade" if meth == "trade" else "other"], n["lo"], n["hi"]))
        out.append((n["name"], n["lo"], n["hi"], sw, reason))
    return out


def drop_stages(stages, t, tid, used):
    """A family's stages with the table's `drop_stages` taken out (the owner, 2026-10-04: wrong-country spawns).

    A family is walked forward through the jar's evolutions, so a place that fits the first stage can be handed a
    later one that does not -- Crabrawler belongs on a southern strand, Crabominable (its ice-stone evolution, native
    only to Cobblemon's is_peak) does not. `drop_stages` maps such a stage to the reason it is out; its weight goes
    to the family's last kept stage, so the family keeps the weight its role gives it and the table's tier and
    shape stay whole. A dropped stage that no family in the table produces is stale and fails closed (see the
    check after the table is built). It applies to the table's base families only: a heart names its species
    itself, so a heart that does not want one leaves it out."""
    drops = t.get("drop_stages") or {}
    if not drops:
        return stages
    kept = [s for s in stages if s[0] not in drops]
    gone = [s for s in stages if s[0] in drops]
    if not gone:
        return stages
    if not kept:
        raise DesignError("%s: drop_stages takes every stage of a family (%s); drop the family instead"
                          % (tid, ", ".join(s[0] for s in gone)))
    used.update(s[0] for s in gone)
    name, lo, hi, w, reason = kept[-1]
    lost = round(sum(s[3] for s in gone), 1)
    kept[-1] = (name, lo, hi, round(w + lost, 1), "%s; takes the weight of %s, dropped here: %s" % (
        reason, ", ".join(s[0] for s in gone), "; ".join(drops[s[0]] for s in gone)))
    return kept


def check_drops_used(t, tid, used):
    stale = sorted(set(t.get("drop_stages") or {}) - used)
    if stale:
        raise DesignError("%s: drop_stages names %s, which no family in the table produces; remove the stale entry"
                          % (tid, ", ".join(stale)))


def build_table(dex, rules, tid, t, kind, extra_families=()):
    """[(row dict)] for one table: the generic fields of both an entry and its mirror."""
    tier = t["tier"]
    cap, tband = tier_rules(rules, tier)
    band = tuple(t.get("levels") or tband)
    if not (tband[0] <= band[0] <= band[1] <= tband[1]):
        raise DesignError("%s: levels %s are not inside the tier %d band %s" % (tid, list(band), tier, list(tband)))
    mtier = min(9, tier + rules.get("off_path_maturity_step", 0)) if t.get("placement") == "off" else tier
    fams = [(item, "land") for item in t.get("land") or []] + [(item, "water") for item in t.get("water") or []]
    fams += list(extra_families)
    rows = []
    used = set()
    for item, half, *prio in [(f[0], f[1]) + tuple(f[2:]) for f in fams]:
        species, role, weight, cond = parse_family(item, rules, tid)
        if role == "presence":
            raise DesignError("%s: %s is a presence; a presence lives only in a heart (section 10)" % (tid, species))
        priority = prio[0] if prio else role
        if kind == HABITAT and " " in species:
            raise DesignError("%s: %s has a space; a habitat pool species is a bare id" % (tid, species))
        nearby_water = "minecraft:water" in (cond.get("neededNearbyBlocks") or [])
        stages = drop_stages(expand_family(dex, rules, tier, band, species, role, weight, tid, mtier), t, tid, used)
        for name, lo, hi, w, reason in stages:
            if " " in name and kind == HABITAT:
                raise DesignError("%s: stage %s has a space; a habitat pool species is a bare id" % (tid, name))
            if hi > cap or lo < band[0] or hi > band[1]:
                raise DesignError("%s: %s spawns %d-%d, outside band %s or over the tier %d cap %d"
                                  % (tid, name, lo, hi, list(band), tier, cap))
            pos, _ = dex.position(name, half == "water", nearby_water, species)
            rows.append({"name": name, "bucket": rules["roles"][role]["bucket"], "level": "%d-%d" % (lo, hi),
                         "weight": w, "conditions": dict(cond), "reason": reason, "position": pos,
                         "family": dex.family(species), "priority": priority, "role": role, "half": half})
    # one species twice in a table: merge only where nothing but weight and levels differ
    merged, order = {}, []
    for r in rows:
        k = r["name"]
        if k not in merged:
            merged[k] = r
            order.append(k)
            continue
        a = merged[k]
        if (a["position"], a["bucket"], a["conditions"]) != (r["position"], r["bucket"], r["conditions"]):
            raise DesignError("%s: %s comes twice, as %s/%s/%s and %s/%s/%s; the compiled spawn ids would collide"
                              % (tid, k, a["half"], a["position"], a["bucket"], r["half"], r["position"], r["bucket"]))
        alo, ahi = map(int, a["level"].split("-"))
        blo, bhi = map(int, r["level"].split("-"))
        a["level"] = "%d-%d" % (min(alo, blo), max(ahi, bhi))
        a["weight"] = round(a["weight"] + r["weight"], 1)
        a["reason"] += "; also " + r["reason"]
    check_drops_used(t, tid, used)
    return [merged[k] for k in order], band


# ------------------------------------------------------------------ hearts (ENCOUNTER_DESIGN.md section 10)

def above_cap_fraction(level, cap):
    """The share of a level range above the cap, every level in the range taken as equally likely (an assumption
    about Cobblemon 1.8.0's level draw, stated in section 10)."""
    lo, hi = map(int, str(level).split("-"))
    return max(0, hi - max(lo, cap + 1) + 1) / float(hi - lo + 1)


def heart_geometry(tid, heart, landmarks, hrules):
    """The record tools/compile_spawns.py clips a heart's entries to, from the design's heart."""
    clear = hrules["clear_of_path_blocks"]
    if heart.get("kind") == "summit":
        if not isinstance(heart.get("minY"), int) or isinstance(heart.get("minY"), bool):
            raise DesignError("%s: a summit heart needs a whole-number minY" % tid)
        return {"kind": "summit", "minY": heart["minY"], "clear_of_path_blocks": clear}
    if heart.get("kind") == "focus":
        at = heart.get("at") or {}
        if "landmark" in at:
            lm = landmarks.get(at["landmark"])
            if lm is None:
                raise DesignError("%s: heart landmark %s is not in data/landmarks.json" % (tid, at["landmark"]))
            x, z = lm["anchor"]["x"], lm["anchor"]["z"]
        elif isinstance(at.get("x"), int) and isinstance(at.get("z"), int) and at.get("why"):
            x, z = at["x"], at["z"]
        else:
            raise DesignError("%s: a focus heart is at a landmark, or at an x, z with a why" % tid)
        r = heart.get("radius")
        if not isinstance(r, int) or r <= 0:
            raise DesignError("%s: a focus heart needs a whole-number radius" % tid)
        return {"kind": "focus", "x": x, "z": z, "radius": r, "clear_of_path_blocks": clear}
    raise DesignError("%s: a heart is kind summit or focus, not %r" % (tid, heart.get("kind")))


def presence_levels(dex, rules, tier, band, species, where):
    """(lo, hi, how) for a presence: from the band's top, or the level it evolves at if later, to the next leg's cap."""
    hrules = rules["hearts"]
    hi = int(hrules["next_cap"][str(tier)])
    lo, how = band[1], "a presence, from the band's top"
    base = dex.split(species)[0]
    pre = dex.pre.get(base)
    if pre is not None:
        ev = next(((m, lv, h) for res, m, lv, h in dex.evolutions(pre) if dex.split(res)[0] == base), None)
        if ev is not None:
            m, lv, h = ev
            if m == "level":
                if lv > lo:
                    lo, how = lv, "a presence, from the level it evolves at (%d)" % lv
            else:
                need = rules["non_level_evolution_min_tier"]["trade" if m == "trade" else "other"]
                if tier + 1 < need:
                    raise DesignError("%s: presence %s evolves %s, in the wild from tier %d; a presence is the next "
                                      "leg's (tier %d)" % (where, species, h, need, tier + 1))
    if lo > hi:
        raise DesignError("%s: presence %s cannot spawn: from %d is past the next leg's cap %d" % (where, species, lo, hi))
    return lo, hi, how


def build_heart(dex, rules, tid, t, band, mtier, top=9):
    """[(row dict)] for one table's heart: its families on the upper half of the table's band, matured a step
    further than the table (never past tier `top`: 9 on the overworld, the Nether's top tier there), and its presences
    from the band's top to the next leg's cap. A Nether heart (kind "nearby") puts its blocks, and its maxY if it has
    one, into every heart row's conditions."""
    hrules = rules["hearts"]
    tier = t["tier"]
    cap, _ = tier_rules(rules, tier)
    heart = t["heart"]
    half = (band[0] + band[1] + 1) // 2
    hband = (half, band[1])
    hmtier = min(top, mtier + hrules["maturity_step"])
    rows = []
    for item, side in [(f, "land") for f in heart.get("land") or []] + [(f, "water") for f in heart.get("water") or []]:
        species, role, weight, cond = parse_family(item, rules, tid + " heart")
        if role == "find":
            raise DesignError("%s: a heart holds no find; a find is the table's own (section 6)" % tid)
        nearby_water = "minecraft:water" in (cond.get("neededNearbyBlocks") or [])
        if heart.get("kind") == "summit":
            cond = dict(cond, minY=heart["minY"])
        elif heart.get("kind") == "nearby":
            cond = dict(cond, neededNearbyBlocks=list(heart["blocks"]), **({"maxY": heart["maxY"]} if "maxY" in heart else {}))
        if role == "presence":
            if not dex.has(species):
                raise DesignError("%s heart: %s is not a species in the Cobblemon jar" % (tid, species))
            lo, hi, how = presence_levels(dex, rules, tier, band, species, tid + " heart")
            w = weight if weight is not None else float(rules["roles"]["presence"]["weight"])
            stages = [(species, lo, hi, w, "%s, %d-%d against the tier %d cap %d: seen on this leg, caught on the next "
                       "(next cap %d)" % (how, lo, hi, tier, cap, hrules["next_cap"][str(tier)]))]
        else:
            # a heart names the bigger stage itself; it spawns from the level it evolves at, never below
            fband = hband
            pre = dex.pre.get(dex.split(species)[0])
            ev = next(((m, lv) for res, m, lv, _ in dex.evolutions(pre) if dex.split(res)[0] == dex.split(species)[0]),
                      None) if pre is not None else None
            if ev is not None and ev[0] == "level" and ev[1] > fband[0]:
                fband = (ev[1], fband[1])
                if fband[0] > fband[1]:
                    raise DesignError("%s heart: %s evolves at %d, past the band's top %d" % (tid, species, ev[1], fband[1]))
            stages = expand_family(dex, rules, tier, fband, species, role, weight, tid + " heart", hmtier)
            stages = [(n, lo, hi, w, "heart: " + why) for n, lo, hi, w, why in stages]
        for name, lo, hi, w, reason in stages:
            if role != "presence" and hi > cap:
                raise DesignError("%s heart: %s spawns %d-%d over the tier %d cap %d; only a presence may" % (tid, name, lo, hi, tier, cap))
            pos, _ = dex.position(name, side == "water", nearby_water, species)
            rows.append({"name": name, "bucket": rules["roles"][role]["bucket"], "level": "%d-%d" % (lo, hi),
                         "weight": w, "conditions": dict(cond), "reason": reason, "position": pos,
                         "family": dex.family(species), "priority": role, "role": role, "half": side})
    merged, order = {}, []
    for r in rows:
        k = r["name"]
        if k in merged:
            raise DesignError("%s heart: %s comes twice; the compiled heart ids would collide" % (tid, k))
        merged[k] = r
        order.append(k)
    return [merged[k] for k in order]


def heart_above_cap(base_rows, heart_rows, cap):
    """{context: share of the heart's spawn chance above the cap}, the heart being its base rows and its own, by the
    audit's chance rule (buckets renormalised over those present in the context, weight within the bucket)."""
    out = {}
    rows = [("b", r) for r in base_rows] + [("h", r) for r in heart_rows]
    for ctx in ("land", "water"):
        rs = [r for _, r in rows if (r["position"] in WATER_POS) == (ctx == "water")]
        if not rs:
            continue
        buckets = {}
        for r in rs:
            buckets.setdefault(r["bucket"], []).append(r)
        tb = sum(BUCKET_P[b] for b in buckets)
        share = 0.0
        for b, brs in buckets.items():
            tw = sum(r["weight"] for r in brs) or 1
            share += sum(BUCKET_P[b] / tb * r["weight"] / tw * above_cap_fraction(r["level"], cap) for r in brs)
        out[ctx] = round(share, 4)
    return out


def entry_of(dex, r, scope, kind, authored, heart=None, alpha=False):
    sid = r["name"].replace(" ", "_")
    e = {"id": ("surface.%s.%s" if kind == SURFACE else "habitat.%s.%s") % (scope, ("heart." + sid) if heart else sid),
         "species": r["name"], "bucket": r["bucket"], "level": r["level"], "weight": r["weight"], "ambient": True,
         "scope": scope, "mechanism": kind, "conditions": r["conditions"], "eligibility_reason": r["reason"]}
    if heart:
        e["heart"] = heart
        # rules.hearts.alpha (the owner, 2026-10-05: "the boss pokemon are alphas"); tools/compile_spawns.py writes
        # it into the spawn's PokemonProperties string as alpha=true
        e["alpha"] = alpha
    if kind == SURFACE:
        e["biomes"] = []
    e["spawnable_position"] = r["position"]
    auth = authored.get((scope, r["name"]))
    if auth:
        e["spawnable_position"] = auth["position"]
        e["spawnable_position_authored"] = auth
    return e


def mirror_of(dex, r):
    return {"species": dex.display(r["name"]), "pokemon": r["name"], "types": dex.types(r["name"]),
            "family": r["family"], "family_priority": r["priority"], "ambient": True,
            "eligibility_reason": r["reason"], "level": r["level"], "bucket": r["bucket"], "weight": r["weight"],
            "conditions": r["conditions"]}


def table_chances(rows):
    """{species: chance} within the table, by the audit's rule (contexts apart, buckets renormalised)."""
    out = {}
    for ctx in ("land", "water"):
        rs = [r for r in rows if (r["position"] in WATER_POS) == (ctx == "water")]
        buckets = {}
        for r in rs:
            buckets.setdefault(r["bucket"], []).append(r)
        tb = sum(BUCKET_P[b] for b in buckets)
        for b, brs in buckets.items():
            tw = sum(r["weight"] for r in brs) or 1
            for r in brs:
                out[r["name"]] = out.get(r["name"], 0) + BUCKET_P[b] / tb * r["weight"] / tw
    return out


def route_selection(routes, generated, rules, placement=None):
    """{route id: {"species": [...]}} from the crossed tables' corridor-role families.

    rules.corridor_rare_min (the owner, 2026-10-05: "every area should have a rare, ultra rare") reserves, per role,
    that many of the best-scoring rare-role and ultra-role species of the crossed ON-PATH tables (placement "path")
    before the rest is filled by score. An off-path table's rare families never reach a corridor: they may be its
    find (section 6), and a find belongs to whoever leaves the path."""
    allowed_roles = set(rules["corridor_roles"])
    rare_min = dict(rules.get("corridor_rare_min") or {})
    table_min = int(rules.get("corridor_table_min") or 0)
    placement = placement or {}
    limit = rules["corridor_species_limit"]
    out = {}
    for rt in routes["routes"]:
        tr = rt["geography"]["transitions"]
        total = rt["corridor"]["polyline"][-1]["at_distance_blocks"]
        length = {}
        for i, t in enumerate(tr):
            end = tr[i + 1]["at_distance_blocks"] if i + 1 < len(tr) else total
            for s in t["subregions"]:
                length[s] = length.get(s, 0.0) + max(0.0, end - t["at_distance_blocks"])
        score, keep, rscore, floor = {}, set(), {k: {} for k in rare_min}, {}
        for sub in sorted(length):
            rows = generated[sub]
            chance = table_chances(rows)
            # rules.corridor_table_min: a box compiles only the listed species of ITS table, so a table whose
            # species all lose the route-wide ranking left boxes of one species (Pallet's stretch of Route 1 was
            # Caterpie alone, play test 2026-10-05, review 85)
            own = sorted({r["name"] for r in rows if r["role"] in allowed_roles and r["half"] != "water"},
                         key=lambda s: (-chance[s], s))
            floor[sub] = own
            for r in rows:
                if r["role"] in rare_min:
                    if placement.get(sub) == "path":
                        rs = rscore[r["role"]]
                        rs[r["name"]] = rs.get(r["name"], 0.0) + chance[r["name"]] * max(length[sub], 1.0)
                    continue
                if r["role"] not in allowed_roles:
                    continue
                score[r["name"]] = score.get(r["name"], 0.0) + chance[r["name"]] * max(length[sub], 1.0)
                if r["half"] == "water":
                    keep.add(r["name"])
        for role, n in sorted(rare_min.items()):
            cands = sorted((s for s in rscore[role] if s not in keep), key=lambda s: (-rscore[role][s], s))
            keep.update(cands[:n])
        for sub in sorted(floor):
            keep.update(floor[sub][:table_min])
        # the kept species may pass corridor_species_limit (which then only stops the fill by score): a route that
        # crosses many tables keeps each one's minimum rather than shrinking it to one species a stretch
        ceiling = rules.get("corridor_species_ceiling", limit)
        if len(keep) > ceiling:
            raise DesignError("%s: %d water, reserved rare and per-table species to keep, over the corridor ceiling %d: %s"
                              % (rt["id"], len(keep), ceiling, sorted(keep)))
        rest = sorted((s for s in score if s not in keep), key=lambda s: (-score[s], s))
        chosen = set(keep) | set(rest[:max(0, limit - len(keep))])
        spaced = sorted(s for s in chosen if " " in s)
        if spaced:
            # tools/compile_spawns.py compile_route puts the species into the spawn id as it is
            raise DesignError("%s: corridor species with a form aspect %s would put a space in a route spawn id"
                              % (rt["id"], spaced))
        out[rt["id"]] = {"species": sorted(chosen)}
    return out


EVOLUTION_POLICY = {
    "source": "docs/mechanics/ENCOUNTER_DESIGN.md sections 2-4 and 7a",
    "design": "data/encounter_design.json",
    "generator": "tools/build_encounters.py",
    "rule": ("A table lists families by the species first met there; the generator walks the Cobblemon jar's "
             "evolutions forward. A stage spawns from the level it evolves at (or the band's floor) to four past its "
             "next level evolution (or the band's top), and not at all if that range is empty. maturity[tier] of a "
             "family's weight goes to its evolved stages, the final one taking (tier - 3) / 6 of it, held to "
             "[0.2, 0.9]. Evolutions not by level appear only from tier 6 (a trade from tier 7), in the upper half of "
             "the band."),
    "retired": ("2026-10-02: the band-minimum rule (level evolutions only when every threshold is at or below the "
                "band minimum; special evolutions authored-only) and its fixed stage splits."),
}

ROUTE_NOTE = ("Generated by tools/build_encounters.py from data/encounter_design.json (docs/mechanics/"
              "ENCOUNTER_DESIGN.md section 6): per route, the families in rules.corridor_roles (never a find) of every "
              "sub-region its corridor crosses (data/routes.json geography transitions), at most "
              "corridor_species_limit: every crossed table's water species kept, rules.corridor_rare_min of the "
              "crossed on-path tables' rare- and ultra-role species reserved (the owner, 2026-10-05), and the rest by "
              "chance times corridor length. tools/compile_spawns.py reads this list and does not choose. Do not edit "
              "by hand.")


def victory_road_roster_problems(dex, rules, tables, pid, rows):
    """rules.victory_road_roster (the owner, 2026-10-06: "final starter evos and pseudo legendaries or bangers"):
    every row of a vrc_ pool is a final stage in the jar, totals at least bst_min, carries none of excluded_labels,
    is not one the owner named out, and is not of a family some sub-region table holds as a find (section 6: "a
    find is never the base of a Victory Road family"). Fails closed: no rule recorded is a problem, not a pass."""
    vr = rules.get("victory_road_roster")
    if not isinstance(vr, dict) or not isinstance(vr.get("bst_min"), int):
        return ["%s: rules.victory_road_roster with an integer bst_min is missing; Victory Road cannot be checked" % pid]
    finds = {dex.family(parse_family(f, rules, tid)[0]) for tid, t in tables.items()
             for f in (t.get("land") or []) + (t.get("water") or []) if f[1] == "find"}
    out = []
    for r in rows:
        name = r["name"]
        sp, _ = dex.record(name)
        bst = sum((sp.get("baseStats") or {}).values())
        labels = set(sp.get("labels") or []) & set(vr.get("excluded_labels") or [])
        if vr.get("final_only") and dex.evolutions(name):
            out.append("%s: %s evolves further; Victory Road holds final stages only" % (pid, name))
        if bst < vr["bst_min"]:
            out.append("%s: %s totals %d, under rules.victory_road_roster bst_min %d" % (pid, name, bst, vr["bst_min"]))
        if labels:
            out.append("%s: %s is %s" % (pid, name, ", ".join(sorted(labels))))
        if dex.split(name)[0] in set(vr.get("owner_named_out") or []):
            out.append("%s: %s is one the owner named out of Victory Road" % (pid, name))
        if r["family"] in finds:
            out.append("%s: %s is of the %s family, a find off the path (section 6)" % (pid, name, r["family"]))
    # the owner, 2026-10-06: "thats to agressive on starters ... we need variety": at most starter_finals_max_per_zone
    # starter families in one pool
    starters = sorted({r["family"] for r in rows if r["family"] in set(vr.get("starter_families") or [])})
    cap = vr.get("starter_finals_max_per_zone")
    if isinstance(cap, int) and len(starters) > cap:
        out.append("%s: %d starter families %s, over rules.victory_road_roster starter_finals_max_per_zone %d"
                   % (pid, len(starters), starters, cap))
    return out


# ------------------------------------------------------------------ the Nether (docs/mechanics/NETHER_ENCOUNTERS.md)

def nether_rules(rules, nether):
    """A copy of the overworld rules with the Nether's tiers added (cap, band, maturity, next cap). The overworld's
    rules object is never changed, so no overworld table can read a Nether tier."""
    r = json.loads(json.dumps(rules))
    for k, t in (nether.get("tiers") or {}).items():
        if k in r["tiers"]:
            raise DesignError("nether.tiers %s is already an overworld tier" % k)
        r["tiers"][k] = {"cap": t["cap"], "band": list(t["band"])}
        r["maturity"][k] = t["maturity"]
        r["hearts"]["next_cap"][k] = t["next_cap"]
    return r


class _StopDex:
    """The Dex with the evolutions of a table's stop_evolving species hidden: the design spawns them as themselves.

    drop_stages cannot say this in the deep ring: at maturity 1.0 an unevolved stage's weight rounds to nothing, so
    dropping Onix's Steelix there would drop the whole family. A stopped species is the family's last stage, and the
    walk gives it the family's weight."""

    def __init__(self, dex, stop):
        self._dex, self._stop = dex, set(stop)

    def __getattr__(self, name):
        return getattr(self._dex, name)

    def evolutions(self, name):
        return [] if self._dex.split(name)[0] in self._stop else self._dex.evolutions(name)


def _box_overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1] and a[2] <= b[3] and b[2] <= a[3]


def nether_heart_geometry(tid, heart):
    """The record a Nether heart's entries carry: kind nearby, its blocks, its maxY. No position: the Nether has no
    heightmap, and positions are never read from a world (CLAUDE.md, "Ground comes from the heightmap")."""
    if heart.get("kind") != "nearby":
        raise DesignError("%s: a Nether heart is kind nearby (a block it stands beside), not %r" % (tid, heart.get("kind")))
    blocks = heart.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise DesignError("%s: a nearby heart names its blocks" % tid)
    bad = sorted(set(blocks) - NETHER_NEARBY)
    if bad:
        raise DesignError("%s: heart blocks %s are outside the Nether vocabulary %s" % (tid, bad, sorted(NETHER_NEARBY)))
    geo = {"kind": "nearby", "blocks": list(blocks)}
    if "maxY" in heart:
        if not isinstance(heart["maxY"], int) or isinstance(heart["maxY"], bool):
            raise DesignError("%s: a heart's maxY is a whole number" % tid)
        geo["maxY"] = heart["maxY"]
    return geo


def nether_entry(r, scope, key, base_cond, heart=None, alpha=False):
    sid = r["name"].replace(" ", "_")
    cond = dict(base_cond)
    cond.update(r["conditions"])
    e = {"id": "nether.%s.%s" % (scope, ("heart." + sid) if heart else sid), "species": r["name"], "bucket": r["bucket"],
         "level": r["level"], "weight": r["weight"], "ambient": True, "scope": scope, "mechanism": NETHER,
         "conditions": cond, "eligibility_reason": r["reason"]}
    if heart:
        e["heart"] = heart
        e["alpha"] = alpha
    e["biomes"] = list(key.get("biomes") or [])
    e["spawnable_position"] = r["position"]
    return e


def generate_nether(design, dex, dolls):
    """({(NETHER, scope): [entries]}, [table records], [problems]) for data/encounter_design.json "nether".

    Every table is expanded once per ring, as a table of the ring's tier (build_table and build_heart, the overworld's
    arithmetic, over the Nether's tiers). Each entry's conditions carry "dimensions": [the Nether] and the table's
    structures; its biomes are the table's. Fails closed on: a key that is neither biomes nor structures; a doll or an
    excluded species; a Fire type outside the fire rule's biomes without a written fire_exception (types from the jar);
    a heart presence above the cap in the common bucket, or a heart over rules.hearts.above_cap_max_share; ring boxes
    that overlap."""
    nether = design.get("nether")
    if not nether:
        return {}, [], []
    rules = nether_rules(design["rules"], nether)
    top = max(int(k) for k in nether["tiers"])
    dim = nether["dimension"]
    fire_biomes = set(nether["fire_rule"]["biomes"])
    excluded = nether.get("excluded_species") or {}
    alpha = rules["hearts"]["alpha"]
    problems, gen, records = [], {}, []
    rings = nether["rings"]
    allboxes = [(rid, tuple(b)) for rid, ring in rings.items() for b in ring["boxes"]]
    for i, (ra, a) in enumerate(allboxes):
        for rb, b in allboxes[i + 1:]:
            if _box_overlap(a, b):
                problems.append("nether rings: box %s (%s) overlaps box %s (%s)" % (list(a), ra, list(b), rb))
    for tid, t in nether["tables"].items():
        key = t.get("key") or {}
        if not key or set(key) - set(NETHER_KEYS) or not all(isinstance(v, list) and v for v in key.values()):
            problems.append("nether %s: key is biomes and/or structures, each a non-empty list, not %r" % (tid, key))
            continue
        in_fire_biome = bool(key.get("biomes")) and set(key["biomes"]) <= fire_biomes
        stop = t.get("stop_evolving") or {}
        unknown = sorted(s for s in stop if not dex.has(s))
        if unknown:
            problems.append("nether %s: stop_evolving names %s, not species in the jar" % (tid, unknown))
            continue
        tdex = _StopDex(dex, stop) if stop else dex
        named = set()
        for rid, ring in rings.items():
            scope = "%s_%s" % (tid, rid)
            tt = {k: v for k, v in t.items() if k != "placement"}
            tt["tier"] = ring["tier"]
            try:
                rows, band = build_table(tdex, rules, scope, tt, NETHER)
                hrows, geo = [], None
                if t.get("heart"):
                    geo = nether_heart_geometry(scope, t["heart"])
                    hrows = build_heart(tdex, rules, scope, tt, band, ring["tier"], top)
            except DesignError as ex:
                problems.append(str(ex))
                continue
            cap, _ = tier_rules(rules, ring["tier"])
            named.update(dex.split(r["name"])[0] for r in rows)
            for where, rs in (("", rows), (" heart", hrows)):
                for r in rs:
                    base = dex.split(r["name"])[0]
                    if base in dolls:
                        problems.append("nether %s%s: %s is drawn by the client as the substitute doll" % (scope, where, r["name"]))
                    if base in excluded:
                        problems.append("nether %s%s: %s is excluded: %s" % (scope, where, r["name"], excluded[base]))
                    if "fire" in dex.types(r["name"]) and not in_fire_biome and not t.get("fire_exception"):
                        problems.append("nether %s%s: %s is Fire (%s) outside %s, with no fire_exception (the fire rule)"
                                        % (scope, where, r["name"], "/".join(dex.types(r["name"])), sorted(fire_biomes)))
            share = {}
            if hrows:
                for r in hrows:
                    if above_cap_fraction(r["level"], cap) > 0 and r["bucket"] == "common":
                        problems.append("nether %s heart: %s is above the cap in the common bucket" % (scope, r["name"]))
                share = heart_above_cap(rows, hrows, cap)
                for ctx, s in share.items():
                    if s > rules["hearts"]["above_cap_max_share"]:
                        problems.append("nether %s heart: %.1f%% of its %s spawns are above the cap, over the %.1f%% allowed"
                                        % (scope, 100 * s, ctx, 100 * rules["hearts"]["above_cap_max_share"]))
            base_cond = {"dimensions": [dim]}
            if key.get("structures"):
                base_cond["structures"] = list(key["structures"])
            gen[(NETHER, scope)] = ([nether_entry(r, scope, key, base_cond) for r in rows]
                                    + [nether_entry(r, scope, key, base_cond, geo, alpha) for r in hrows])
            rec = {"id": scope, "table": tid, "ring": rid, "tier": ring["tier"],
                   "level_band": {"minimum": band[0], "maximum": band[1], "cap": cap,
                                  "next_cap": rules["hearts"]["next_cap"][str(ring["tier"])]},
                   "dimension": dim, "key": key, "boxes": [list(b) for b in ring["boxes"]],
                   "species": [r["name"] for r in rows]}
            if t.get("fire_exception"):
                rec["fire_exception"] = t["fire_exception"]
            if geo:
                rec["heart"] = dict(geo, why=t["heart"].get("why", ""), alpha=alpha, above_cap_share=share,
                                    species=[r["name"] for r in hrows])
            rec["roster_basis"] = ("Generated by tools/build_encounters.py from data/encounter_design.json nether.tables.%s, "
                                   "ring %s (tier %d). Do not edit by hand." % (tid, rid, ring["tier"]))
            records.append(rec)
        stale = sorted({battle_sim.key(s) for s in stop} - named)
        if stale:
            problems.append("nether %s: stop_evolving names %s, which no ring of the table spawns" % (tid, stale))
    return gen, records, problems


def generate(design, spawns, regions, routes, dex, dolls, landmarks=None):
    rules = design["rules"]
    landmarks = {lm["id"]: lm for lm in (landmarks or {}).get("landmarks") or []}
    problems = []
    sub_ids = [s["id"] for s in regions["subregions"]]
    tables = design["tables"]
    for tid in tables:
        if tid not in sub_ids:
            problems.append("design table %s is not a sub-region in data/regions.json" % tid)
    for sid in sub_ids:
        if sid not in tables:
            problems.append("sub-region %s has no design table in data/encounter_design.json" % sid)
    pools = {k: v for k, v in design["habitats"].items() if not k.startswith("_")}
    hab_ids = {h["id"] for h in spawns["habitats"]}
    for pid in pools:
        if pid not in hab_ids:
            problems.append("design pool %s is not a habitat in data/spawns.json" % pid)
    if problems:
        raise DesignError("\n".join(problems))

    authored = {(e["scope"], e["species"]): e["spawnable_position_authored"] for e in spawns["entries"]
                if isinstance(e.get("spawnable_position_authored"), dict)}
    gen_rows, bands = {}, {}
    for tid in sub_ids:
        try:
            gen_rows[tid], bands[tid] = build_table(dex, rules, tid, tables[tid], SURFACE)
        except DesignError as ex:
            problems.append(str(ex))
    staple = [(item, "land", "staple") for item in design["habitats"].get("_staple") or []]
    for pid, p in pools.items():
        extra = []
        t = dict(p)
        if p.get("core_of"):
            zone = pools.get(p["core_of"])
            if zone is None:
                problems.append("%s: core_of %s is not a design pool" % (pid, p["core_of"]))
                continue
            if any(parse_family(f, rules, pid)[1] in ("rare", "find") for f in (zone.get("land") or []) + (zone.get("water") or [])):
                problems.append("%s: its zone %s has a rare family; the prize must be the only one" % (pid, p["core_of"]))
            t["land"], t["water"] = zone.get("land") or [], zone.get("water") or []
            extra.append(([p["prize"], "find", 2], "water" if any(p["prize"] == f[0] for f in t["water"]) else "land", "prize"))
            if not dex.has(p["prize"]):
                problems.append("%s: prize %s is not a species in the Cobblemon jar" % (pid, p["prize"]))
                continue
        if p.get("staple"):
            extra = staple + extra
        try:
            gen_rows[pid], bands[pid] = build_table(dex, rules, pid, t, HABITAT, extra)
        except DesignError as ex:
            problems.append(str(ex))
            continue
        if pid.startswith("vrc_"):
            problems += victory_road_roster_problems(dex, rules, tables, pid, gen_rows[pid])
    if problems:
        raise DesignError("\n".join(problems))
    heart_rows, heart_geo = {}, {}
    for tid in sub_ids:
        t = tables[tid]
        if not t.get("heart"):
            continue
        try:
            heart_geo[tid] = heart_geometry(tid, t["heart"], landmarks, rules["hearts"])
            mtier = min(9, t["tier"] + rules.get("off_path_maturity_step", 0)) if t.get("placement") == "off" else t["tier"]
            heart_rows[tid] = build_heart(dex, rules, tid, t, bands[tid], mtier)
        except DesignError as ex:
            problems.append(str(ex))
            continue
        cap, _ = tier_rules(rules, t["tier"])
        for r in heart_rows[tid]:
            if above_cap_fraction(r["level"], cap) > 0 and r["bucket"] == "common":
                problems.append("%s heart: %s is above the cap in the common bucket; a presence is never common" % (tid, r["name"]))
        for ctx, share in heart_above_cap(gen_rows[tid], heart_rows[tid], cap).items():
            if share > rules["hearts"]["above_cap_max_share"]:
                problems.append("%s heart: %.1f%% of its %s spawns are above the cap, over the %.1f%% allowed"
                                % (tid, 100 * share, ctx, 100 * rules["hearts"]["above_cap_max_share"]))
    if problems:
        raise DesignError("\n".join(problems))
    for pid, rows in list(gen_rows.items()) + [(k + " heart", v) for k, v in heart_rows.items()]:
        for r in rows:
            if dex.split(r["name"])[0] in dolls:
                problems.append("%s: %s is drawn by the client as the substitute doll "
                                "(modpack/manifest/client-pack-atm-subset.json)" % (pid, r["name"]))
    if problems:
        raise DesignError("\n".join(problems))

    alpha = rules["hearts"].get("alpha")
    if not isinstance(alpha, bool):
        raise DesignError("rules.hearts.alpha is true or false (ENCOUNTER_DESIGN.md section 10), not %r" % (alpha,))
    out = json.loads(json.dumps(spawns))
    gen_entries = {}
    for tid in sub_ids:
        gen_entries[(SURFACE, tid)] = [entry_of(dex, r, tid, SURFACE, authored) for r in gen_rows[tid]]
        gen_entries[(SURFACE, tid)] += [entry_of(dex, r, tid, SURFACE, authored, heart_geo[tid], alpha)
                                        for r in heart_rows.get(tid, [])]
    for pid in pools:
        gen_entries[(HABITAT, pid)] = [entry_of(dex, r, pid, HABITAT, authored) for r in gen_rows[pid]]
    nether_gen, nether_records, nether_problems = generate_nether(design, dex, dolls)
    if nether_problems:
        raise DesignError("\n".join(nether_problems))
    gen_entries.update(nether_gen)
    # a Nether entry in the file that the design no longer produces is dropped, not copied through
    stale_nether = {(e["mechanism"], e["scope"]) for e in spawns["entries"] if e["mechanism"] == NETHER} - set(nether_gen)
    entries, done = [], set()
    for e in spawns["entries"]:
        k = (e["mechanism"], e["scope"])
        if k in stale_nether:
            continue
        if k in gen_entries:
            if k not in done:
                entries += gen_entries[k]
                done.add(k)
            continue
        # a copy: stamp_held_items below sets fields on it, and the caller's spawns must stay what was read
        entries.append(json.loads(json.dumps(e)))
    for k in sorted(gen_entries):
        if k not in done:
            entries += gen_entries[k]
    out["entries"] = entries
    # a heart entry copied through untouched (a marine band's, a waterway's) is authored in data/spawns.json; it must
    # carry the same alpha flag as the generated ones, and no entry outside a heart may carry one
    for e in entries:
        if e.get("heart") and e.get("alpha") is not alpha:
            problems.append("%s: a heart entry has alpha %r; rules.hearts.alpha is %r" % (e["id"], e.get("alpha"), alpha))
        elif not e.get("heart") and "alpha" in e:
            problems.append("%s: alpha belongs to a heart entry only (section 10)" % e["id"])
    # rules.held_items (the owner, 2026-10-05: wild held items, a find and not a farm): stamped on every
    # spawn_pool_world entry of a listed species, generated or copied through; a listed species that spawns in no
    # such entry is a stale rule
    held, hp = held_items_by_species(rules, dex)
    problems += hp
    sp_problems, used = stamp_held_items(entries, held)
    problems += sp_problems
    for sp in sorted(set(held) - used):
        problems.append("rules.held_items: %s spawns in no spawn_pool_world entry; remove it from the rule" % sp)
    if problems:
        raise DesignError("\n".join(problems))
    route_ids ={int(r["id"][6:8]): r["id"] for r in routes["routes"] if r["id"].startswith("route_")}
    for rec in out["subregions"]:
        t = tables[rec["id"]]
        lo, hi = bands[rec["id"]]
        rec["level_band"] = {"minimum": lo, "maximum": hi,
                             "basis_route": route_ids.get(t["tier"], "victory_road" if t["tier"] == 9 else None),
                             "tier": t["tier"]}
        rec["entries"] = [mirror_of(dex, r) for r in gen_rows[rec["id"]]]
        rec.pop("conditions_note", None)
        rec.pop("heart", None)
        if rec["id"] in heart_rows:
            cap, _ = tier_rules(rules, t["tier"])
            rec["heart"] = dict(heart_geo[rec["id"]], why=t["heart"].get("why", ""), alpha=alpha,
                                above_cap_share=heart_above_cap(gen_rows[rec["id"]], heart_rows[rec["id"]], cap),
                                entries=[mirror_of(dex, r) for r in heart_rows[rec["id"]]])
        rec["roster_basis"] = ("Generated by tools/build_encounters.py from data/encounter_design.json tables.%s: tier %d, "
                               "%s the path, themes %s%s. Do not edit by hand." % (
                                   rec["id"], t["tier"], "on or near" if t.get("placement") == "path" else "off",
                                   ", ".join(t.get("themes") or []),
                                   ("; " + t["tier_why"]) if t.get("tier_why") else ""))
    for rec in out["habitats"]:
        if rec["id"] in pools:
            lo, hi = bands[rec["id"]]
            rec["level_band"] = {"minimum": lo, "maximum": hi}
            rec["entries"] = [mirror_of(dex, r) for r in gen_rows[rec["id"]]]
    if nether_records:
        out["nether_tables"] = nether_records
    else:
        out.pop("nether_tables", None)
    out["evolution_policy"] = EVOLUTION_POLICY
    out["route_species_selection_note"] = ROUTE_NOTE
    out["route_species_selection"] = route_selection(routes, gen_rows, rules,
                                                     {k: v.get("placement") for k, v in tables.items()})
    return out, gen_rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--design", default=str(DESIGN))
    p.add_argument("--spawns", default=str(SPAWNS))
    p.add_argument("--regions", default=str(REGIONS))
    p.add_argument("--routes", default=str(ROUTES))
    p.add_argument("--dolls", default=str(DOLLS))
    p.add_argument("--landmarks", default=str(LANDMARKS))
    p.add_argument("--jar", default=None, help="Cobblemon 1.8 jar; defaults to tools/battle_sim.py find_jar()")
    p.add_argument("--check", action="store_true", help="exit 1 if data/spawns.json differs from what the design produces")
    a = p.parse_args(argv)
    load = lambda f: json.loads(Path(f).read_text(encoding="utf-8"))  # noqa: E731
    spawns_path = Path(a.spawns)
    dolls = set(load(a.dolls).get("species") or []) if Path(a.dolls).is_file() else set()
    try:
        dex = Dex(a.jar or battle_sim.find_jar())
        out, rows = generate(load(a.design), load(spawns_path), load(a.regions), load(a.routes), dex, dolls,
                             load(a.landmarks))
    except DesignError as ex:
        print("FAIL: the design does not expand:", file=sys.stderr)
        for line in str(ex).splitlines():
            print("  " + line, file=sys.stderr)
        return 1
    text = dumps(out)
    n_sub = sum(1 for e in out["entries"] if e["mechanism"] == SURFACE)
    n_hab = sum(len(rows[k]) for k in rows if k.startswith("vrc_"))
    sel = out["route_species_selection"]
    summary = "%d sub-region tables, %d entries; %d Victory Road pools, %d entries; %d routes, %s species" % (
        sum(1 for k in rows if not k.startswith("vrc_")), n_sub, sum(1 for k in rows if k.startswith("vrc_")), n_hab,
        len(sel), "/".join(str(len(v["species"])) for v in sel.values()))
    summary += "; %d Nether tables, %d entries" % (len(out.get("nether_tables") or []),
                                                  sum(1 for e in out["entries"] if e["mechanism"] == NETHER))
    if a.check:
        same = spawns_path.read_text(encoding="utf-8") == text
        print("%s: %s" % ("identical" if same else "DIFFERS from the design", summary))
        return 0 if same else 1
    spawns_path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %s: %s" % (spawns_path, summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
