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

route_species_selection: per route, the sub-regions data/routes.json's geography transitions cross; from each such
table only families in rules.corridor_roles (never rare, never a find). Each species is scored by its chance in the
table (the audit's rule: bucket share renormalised over the buckets its context holds, times weight over the bucket's
weight) times the corridor length in that table; every crossed table's water species are kept, then the rest by
score until corridor_species_limit. tools/compile_spawns.py then compiles a corridor species only if it is listed.

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
    find = role == "find"
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
                      if find else "named %s family, tier %d: the family starts here" % (role, tier))
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
    for item, half, *prio in [(f[0], f[1]) + tuple(f[2:]) for f in fams]:
        species, role, weight, cond = parse_family(item, rules, tid)
        priority = prio[0] if prio else role
        if kind == HABITAT and " " in species:
            raise DesignError("%s: %s has a space; a habitat pool species is a bare id" % (tid, species))
        nearby_water = "minecraft:water" in (cond.get("neededNearbyBlocks") or [])
        for name, lo, hi, w, reason in expand_family(dex, rules, tier, band, species, role, weight, tid, mtier):
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
    return [merged[k] for k in order], band


def entry_of(dex, r, scope, kind, authored):
    sid = r["name"].replace(" ", "_")
    e = {"id": ("surface.%s.%s" if kind == SURFACE else "habitat.%s.%s") % (scope, sid),
         "species": r["name"], "bucket": r["bucket"], "level": r["level"], "weight": r["weight"], "ambient": True,
         "scope": scope, "mechanism": kind, "conditions": r["conditions"], "eligibility_reason": r["reason"]}
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


def route_selection(routes, generated, rules):
    """{route id: {"species": [...]}} from the crossed tables' corridor-role families."""
    allowed_roles = set(rules["corridor_roles"])
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
        score, keep = {}, set()
        for sub in sorted(length):
            rows = generated[sub]
            chance = table_chances(rows)
            for r in rows:
                if r["role"] not in allowed_roles:
                    continue
                score[r["name"]] = score.get(r["name"], 0.0) + chance[r["name"]] * max(length[sub], 1.0)
                if r["half"] == "water":
                    keep.add(r["name"])
        if len(keep) > limit:
            raise DesignError("%s: %d water species to keep, over the corridor limit %d: %s"
                              % (rt["id"], len(keep), limit, sorted(keep)))
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
              "ENCOUNTER_DESIGN.md section 6): per route, the families in rules.corridor_roles (never rare, never a "
              "find) of every sub-region its corridor crosses (data/routes.json geography transitions), at most "
              "corridor_species_limit, every crossed table's water species kept and the rest by chance times corridor "
              "length. tools/compile_spawns.py reads this list and does not choose. Do not edit by hand.")


def generate(design, spawns, regions, routes, dex, dolls):
    rules = design["rules"]
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
            extra.append(([p["prize"], "rare", 2], "water" if any(p["prize"] == f[0] for f in t["water"]) else "land", "prize"))
            if not dex.has(p["prize"]):
                problems.append("%s: prize %s is not a species in the Cobblemon jar" % (pid, p["prize"]))
                continue
        if p.get("staple"):
            extra = staple + extra
        try:
            gen_rows[pid], bands[pid] = build_table(dex, rules, pid, t, HABITAT, extra)
        except DesignError as ex:
            problems.append(str(ex))
    if problems:
        raise DesignError("\n".join(problems))
    for pid, rows in gen_rows.items():
        for r in rows:
            if dex.split(r["name"])[0] in dolls:
                problems.append("%s: %s is drawn by the client as the substitute doll "
                                "(modpack/manifest/client-pack-atm-subset.json)" % (pid, r["name"]))
    if problems:
        raise DesignError("\n".join(problems))

    out = json.loads(json.dumps(spawns))
    gen_entries = {}
    for tid in sub_ids:
        gen_entries[(SURFACE, tid)] = [entry_of(dex, r, tid, SURFACE, authored) for r in gen_rows[tid]]
    for pid in pools:
        gen_entries[(HABITAT, pid)] = [entry_of(dex, r, pid, HABITAT, authored) for r in gen_rows[pid]]
    entries, done = [], set()
    for e in spawns["entries"]:
        k = (e["mechanism"], e["scope"])
        if k in gen_entries:
            if k not in done:
                entries += gen_entries[k]
                done.add(k)
            continue
        entries.append(e)
    for k in sorted(gen_entries):
        if k not in done:
            entries += gen_entries[k]
    out["entries"] = entries
    route_ids = {int(r["id"][6:8]): r["id"] for r in routes["routes"] if r["id"].startswith("route_")}
    for rec in out["subregions"]:
        t = tables[rec["id"]]
        lo, hi = bands[rec["id"]]
        rec["level_band"] = {"minimum": lo, "maximum": hi,
                             "basis_route": route_ids.get(t["tier"], "victory_road" if t["tier"] == 9 else None),
                             "tier": t["tier"]}
        rec["entries"] = [mirror_of(dex, r) for r in gen_rows[rec["id"]]]
        rec.pop("conditions_note", None)
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
    out["evolution_policy"] = EVOLUTION_POLICY
    out["route_species_selection_note"] = ROUTE_NOTE
    out["route_species_selection"] = route_selection(routes, gen_rows, rules)
    return out, gen_rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--design", default=str(DESIGN))
    p.add_argument("--spawns", default=str(SPAWNS))
    p.add_argument("--regions", default=str(REGIONS))
    p.add_argument("--routes", default=str(ROUTES))
    p.add_argument("--dolls", default=str(DOLLS))
    p.add_argument("--jar", default=None, help="Cobblemon 1.8 jar; defaults to tools/battle_sim.py find_jar()")
    p.add_argument("--check", action="store_true", help="exit 1 if data/spawns.json differs from what the design produces")
    a = p.parse_args(argv)
    load = lambda f: json.loads(Path(f).read_text(encoding="utf-8"))  # noqa: E731
    spawns_path = Path(a.spawns)
    dolls = set(load(a.dolls).get("species") or []) if Path(a.dolls).is_file() else set()
    try:
        dex = Dex(a.jar or battle_sim.find_jar())
        out, rows = generate(load(a.design), load(spawns_path), load(a.regions), load(a.routes), dex, dolls)
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
    if a.check:
        same = spawns_path.read_text(encoding="utf-8") == text
        print("%s: %s" % ("identical" if same else "DIFFERS from the design", summary))
        return 0 if same else 1
    spawns_path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %s: %s" % (spawns_path, summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
