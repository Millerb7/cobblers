#!/usr/bin/env python
"""Birds across the height of every bird tree: extra Habitat Block nests seated from the Cobblemon spawn rule, and the
spawn pools that give each tree its own species line by height.

THE FAULT (docs/world-building/SAPLING_BIRDS.md "Where the birds stand"; tools/habitat_spawn_model.py has the rule and
its bytecode citations). Every nest of the 52 elders and 14 themed saplings is buried in solid wood so nobody breaks
it. Cobblemon's Spawner.constrainArea does not spawn round a buried block: it moves the zone to the nearest AIR in the
block's own column (up first, at most maxVerticalCorrectionBlocks = 64 away) and drops the spawn when there is none.
So an elder's three trunk nests (ground +12, +35, +58) and its crown nest (+74) all spawn in the crown (+45..+83), and
a themed sapling's lowest nest, 12 above ground in a trunk 80 tall, spawns nothing at all. The storeys, 20 to 44 above
the ground, never get a bird of their own.

THE MECHANISM. Cobblemon native (CLAUDE.md principle 6, rung 1): MORE of the same Habitat Block, each seated where the
rule gives its own zone to a different storey. A new nest is a cell of a LIMB (log on all six faces, so it stays hidden
and a mimic of the limb's own wood), a few blocks out from the trunk where the limb's top is 1 to 4 above the cell: the
column above it reaches air within 4, so the zone is centred on the limb top, 16 each way. No keeper, no function, no
new mod. It writes one block per nest, through the placement manifest the apply already runs (tools/habitat_blocks.py).

BANDS. data/tree_bird_species.json (the species designer's, PROPOSED) names, per tree, the species of three bands:
  low   -> the new nest on the first storey        pool tbird_<tree>_low
  mid   -> the new nest on the second storey       pool tbird_<tree>_mid
  crown -> the tree's four existing nests, which the rule puts in the crown   pool <tree> (its existing id)
The world tree (not in that file) takes data/world_tree_bird_species.json: the owner's set of classics (2026-10-21), four
bands by height, the owner's deliberate exception to the one-line rule.

  python tools/tree_birds.py plan              # nests from the tree geometry -> data/tree_bird_nests.json
  python tools/tree_birds.py merge             # tbird_* records -> data/habitat_blocks.json (status planned)
  python tools/tree_birds.py spawns            # the species -> data/spawns.json (entries scope=<pool>, habitats[])
  python tools/tree_birds.py <cmd> --check     # compare with what is committed (exit 1 if different)

WHAT THIS DOES NOT COVER (and says so in the plan's "uncovered")
  - the 4 Foothill grove elders when derived/sites/tree_grove_foothill_woods.json is absent: their rotation is in that
    gitignored file only, and a nest cell depends on it. They get the crown pool only;
  - terrain and neighbouring trees (the model has a flat floor at ground_y and the tree's own blocks).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import habitat_spawn_model as M  # noqa: E402
import tree_geometry as TG  # noqa: E402

PLAN = ROOT / "data" / "tree_bird_nests.json"
HABITATS = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
SPECIES = ROOT / "data" / "tree_bird_species.json"
WORLD_SPECIES = ROOT / "data" / "world_tree_bird_species.json"
SCHEMA = "cobblers.tree-bird-nests/1"
PREFIX = "tbird_"
WORLD_TREE = "world_tree_foothill_woods"
SPAWN_RANGE = 16
NEST = {"spawn_range": SPAWN_RANGE, "chance": 1.0, "trigger": "TICK", "cancel_range": -1,
        "max_spawns": 8, "max_spawns_per_activation": 2}
WORLD_NEST = dict(NEST, max_spawns=5)
# an elder's / themed sapling's added nests: (band, lowest and highest zone-centre height above the ground). The centre
# is the y the rule re-centres the zone on (the air over the limb), not the block. The first storey's limbs top out
# 23-27 above the ground and the second's 41-45 (tools/tree_grove.TIERS["elder"]: floor 20, gap 18): a zone centred at
# 24-30 covers the first storey, one at 41-47 the second storey and the upper limbs.
SMALL_TARGETS = (("low", 24, 30), ("mid", 41, 47))
# the world tree (tools/tree_grove.TIERS["world"]): storeys at 56 + 38 i over the builder's ground + 1, limbs 5 thick;
# two nests a storey, on opposite sides, each centred 3-14 over the storey; then three in the canopy's leaves.
WORLD_STOREY_BASE = tuple(57 + 38 * i for i in range(8))
WORLD_STOREY_WINDOW = (3, 18)
WORLD_CROWN_WINDOWS = ((376, 386), (392, 402), (408, 418))
WORLD_BANDS = (("low", 0, 110), ("mid", 110, 250), ("high", 250, 345), ("crown", 345, 10 ** 6))
MIN_SEPARATION = 33     # two nests of one storey stand at least a box apart, so their zones do not share limbs
MAX_DROP = 4            # a nest sits at most this far under its zone centre: a thin limb, not a trunk
NEIGHBOURS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
BAND_ORDER = ("low", "mid", "crown")
STAGE_BUCKETS = (("common", 24.0), ("uncommon", 6.0), ("rare", 2.0))


class TreeBirdsError(SystemExit):
    pass


# ------------------------------------------------------------------------------------------------------- the nests
def hidden(solid, x, y, z):
    return all((x + dx, y + dy, z + dz) in solid for dx, dy, dz in NEIGHBOURS)


def candidates(t, names, lo, hi):
    """Hidden cells of the tree whose block is one of `names` and whose zone centre lies in [ground+lo, ground+hi]:
    sorted (distance to the trunk axis, y, x, z, centre y)."""
    g = t["ground"]
    w = M.World(t["solid"], g)
    cx, cz = t["centre"]
    out = []
    for (x, y, z), n in t["names"].items():
        if n not in names or (x, y, z) not in t["solid"] or not (g + lo - MAX_DROP <= y <= g + hi):
            continue
        if not hidden(t["solid"], x, y, z):
            continue
        cy = M.centre_y(w, x, y, z)
        if cy is None or not (g + lo <= cy <= g + hi) or not (0 < cy - y <= MAX_DROP):
            continue
        out.append((math.hypot(x - cx, z - cz), y, x, z, cy))
    return sorted(out)


def trees_and_pools(habitats_doc=None):
    """{tree id: {"pool", "nests": [existing records], "mimics": {wood names}}} from the manifest's elder_ and sapling_
    records (the 66 bird trees): the existing nests only, never a tbird_ record."""
    doc = habitats_doc or json.loads(HABITATS.read_text(encoding="utf-8"))
    out = {}
    for b in doc["blocks"]:
        bid = b["id"]
        if not bid.startswith(("elder_", "sapling_")):
            continue
        tree = b["pool"].split(":", 1)[1]
        e = out.setdefault(tree, {"pool": b["pool"], "nests": [], "mimics": set()})
        e["nests"].append(b)
        if not bid.endswith("_top"):         # the top nest is in the crown's leaves (or its themed skin), not wood
            e["mimics"].add(b["mimic"])
    return out


def zone_summary(t, x, y, z):
    w = M.World(t["solid"], t["ground"])
    cy, cells = M.zone_cells(w, x, y, z, SPAWN_RANGE)
    return cy, cells


def nest_entry(t, band, pick):
    d, y, x, z, cy = pick
    _cy, cells = zone_summary(t, x, y, z)
    return {"band": band, "position": {"x": x, "y": y, "z": z}, "mimic": t["names"][(x, y, z)],
            "centre_above_ground": cy - t["ground"], "axis_distance": round(d, 1), "cells": len(cells),
            "floor_cells": M.off_ground(cells, t["ground"]),
            "cells_by_band": {str(k): round(v, 3) for k, v in M.profile(cells, t["ground"], 8).items()}}


def plan_small(t, info):
    """The added nests of one elder or themed sapling."""
    res = []
    for band, lo, hi in SMALL_TARGETS:
        cand = candidates(t, info["mimics"], lo, hi)
        if not cand:
            res.append({"band": band, "problem": "no hidden wood cell of %s has its zone centre %d..%d over the ground"
                                                  % (sorted(info["mimics"]), lo, hi)})
            continue
        res.append(nest_entry(t, band, cand[0]))
    return res


def world_band(centre_above_ground):
    for name, lo, hi in WORLD_BANDS:
        if lo <= centre_above_ground < hi:
            return name
    raise TreeBirdsError("no world-tree band for %r" % centre_above_ground)


def plan_world(t):
    """Two nests on each of the 8 storeys' limbs and three in the canopy's leaves; each carries its pool band."""
    out = []
    for i, base in enumerate(WORLD_STOREY_BASE):
        cand = candidates(t, {"minecraft:oak_log"}, base + WORLD_STOREY_WINDOW[0], base + WORLD_STOREY_WINDOW[1])
        picks = cand[:1]
        if picks:
            # the second on the far side: nearest the axis among cells a full box away from the first, else the farthest
            # cell at least half a box away (the upper storeys' limbs are short: tools/tree_grove.TIERS["world"] reach 58,
            # shrinking 12 % a storey, so they have no cell a full box from the first)
            away = [(math.hypot(c[2] - picks[0][2], c[3] - picks[0][3]), c) for c in cand]
            full = [c for d, c in away if d >= MIN_SEPARATION]
            half = [(d, c) for d, c in away if d >= MIN_SEPARATION // 2]
            if full:
                picks.append(full[0])
            elif half:
                picks.append(max(half, key=lambda dc: (dc[0], -dc[1][0]))[1])
        for k, c in enumerate(picks):
            e = nest_entry(t, world_band(c[4] - t["ground"]), c)
            e["label"] = "s%d%s" % (i + 1, "ab"[k])
            e["pair"] = len(picks) == 2
            out.append(e)
        if not picks:
            out.append({"label": "s%d" % (i + 1), "problem": "no hidden limb cell with a zone centre %d..%d over the ground"
                        % (base + WORLD_STOREY_WINDOW[0], base + WORLD_STOREY_WINDOW[1])})
    for k, (lo, hi) in enumerate(WORLD_CROWN_WINDOWS):
        cand = candidates(t, {"minecraft:oak_leaves"}, lo, hi)
        if not cand:
            out.append({"label": "c%d" % (k + 1), "problem": "no hidden leaf cell with a zone centre %d..%d over the ground" % (lo, hi)})
            continue
        e = nest_entry(t, world_band(cand[0][4] - t["ground"]), cand[0])
        e["label"] = "c%d" % (k + 1)
        out.append(e)
    return out


def plan():
    pools = trees_and_pools()
    trees, uncovered = {}, []
    for tid, info in sorted(pools.items()):
        base = next(n for n in info["nests"] if n["id"] == tid or n["id"].endswith("_low"))
        t = TG.load(tid, (base["position"]["x"], base["position"]["z"]))
        if t is None:
            uncovered.append({"tree": tid, "why": "no geometry here: a grove elder's seat (variant, rotation) is in "
                                                  "derived/sites/tree_grove_foothill_woods.json (absent)"})
            continue
        # the new nests refill as fast as the tree's own (elders 6 a pass since the owner's 2026-10-20 change, themed 2)
        trees[tid] = {"kind": t["kind"], "template": t["template"], "ground": t["ground"],
                      "per_activation": base["activated"]["max_spawns_per_activation"], "new": plan_small(t, info),
                      "existing": []}
        for n in info["nests"]:
            p = n["position"]
            cy, cells = zone_summary(t, p["x"], p["y"], p["z"])
            trees[tid]["existing"].append({"id": n["id"], "above_ground": p["y"] - t["ground"],
                                           "centre_above_ground": None if cy is None else cy - t["ground"],
                                           "cells": len(cells)})
    wt = TG.world_tree()
    trees[WORLD_TREE] = {"kind": "world", "template": wt["template"], "ground": wt["ground"], "centre": list(wt["centre"]),
                         "new": plan_world(wt), "existing": []}
    return {"schema": SCHEMA,
            "note": "Generated by tools/tree_birds.py from the tree prefabs and the Cobblemon 1.8.2 spawn rule "
                    "(tools/habitat_spawn_model.py). Never edit: rerun `python tools/tree_birds.py plan`.",
            "model": {"max_vertical_correction_blocks": M.config()[0], "min_distance_between_entities": M.config()[1],
                      "spawn_range": SPAWN_RANGE},
            "trees": trees, "uncovered": uncovered}


# ---------------------------------------------------------------------------------------------- the habitat records
def records(plan_doc, habitats_doc=None):
    """The tbird_ Habitat Block records of the plan: planned, hidden, a mimic of the cell's own block."""
    out = []
    for tid, t in sorted(plan_doc["trees"].items()):
        world = t["kind"] == "world"
        for n in t["new"]:
            if "problem" in n:
                continue
            label = n["label"] if world else n["band"]
            band = n["band"]
            pool = "cobblers:%s%s_%s" % (PREFIX, tid, band)
            out.append({
                "id": "%s%s_%s" % (PREFIX, tid, label),
                "place": "%s %s: inside its limb, %d over the ground (the zone is centred on the limb top)"
                         % ("the world tree" if world else "the tree", tid, n["position"]["y"] - t["ground"]),
                "pool": pool, "style": "activated", "replace_spawns": False, "position": n["position"],
                "mimic": n["mimic"],
                # placed for every tree (the owner, 2026-10-21: "add spawns up the tree"; the world tree's species are the
                # owner's set, data/world_tree_bird_species.json)
                "status": "placed",
                "activated": dict(WORLD_NEST if world else NEST,
                                  **({} if world else {"max_spawns_per_activation": t["per_activation"]})),
                "why": "An added nest (tools/tree_birds.py, data/tree_bird_nests.json). Cobblemon 1.8.2 re-centres a buried "
                       "block's spawn zone on the nearest air in its column (docs/world-building/SAPLING_BIRDS.md, 'Where "
                       "the birds stand'), so this block is a cell of a limb %.1f from the trunk axis whose zone is centred "
                       "%d over the ground and holds %d standing cells; it spawns the %s band's species."
                       % (n["axis_distance"], n["centre_above_ground"], n["cells"], band)})
    return out


def merged_manifest(plan_doc):
    doc = json.loads(HABITATS.read_text(encoding="utf-8"))
    keep = [b for b in doc["blocks"] if not b["id"].startswith(PREFIX)]
    doc["blocks"] = keep + records(plan_doc)
    return doc


# --------------------------------------------------------------------------------------------------- the species
def jar_path(explicit=None):
    if explicit:
        return Path(explicit)
    for root in (os.environ.get("COBBLERS_SERVER_ROOT"),):
        if root and sorted(Path(root, "mods").glob("Cobblemon-fabric-*.jar")):
            return sorted(Path(root, "mods").glob("Cobblemon-fabric-*.jar"))[-1]
    try:
        import battle_sim
        for c in battle_sim.JAR_CANDIDATES:
            if Path(c).is_file():
                return Path(c)
    except Exception:
        pass
    raise TreeBirdsError("no Cobblemon jar: pass --jar or set COBBLERS_SERVER_ROOT (the species facts come from the jar)")


class Jar:
    """Species facts read from the jar's own species files: display name, types, the level it evolves at."""

    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.index = {n.rsplit("/", 1)[1][:-5]: n for n in self.z.namelist()
                      if n.startswith("data/cobblemon/species/") and n.endswith(".json")}
        self.cache = {}

    def get(self, sid):
        if sid not in self.cache:
            if sid not in self.index:
                raise TreeBirdsError("species %r is not in the Cobblemon jar" % sid)
            self.cache[sid] = json.loads(self.z.read(self.index[sid]))
        return self.cache[sid]

    def implemented(self, sid):
        return bool(self.get(sid).get("implemented"))

    def form(self, sid):
        """The species file's `forms` entry a spawn id like "articuno galarian" names (by aspect), or None for the plain
        species. A form that does not exist in the jar is an error: a spawn naming it would never load."""
        parts = sid.split(" ", 1)
        if len(parts) == 1:
            return None
        hit = [f for f in self.get(parts[0]).get("forms") or [] if parts[1] in (f.get("aspects") or [])]
        if not hit:
            raise TreeBirdsError("species %r has no form with the aspect %r in the Cobblemon jar" % (parts[0], parts[1]))
        return hit[0]

    def types(self, sid):
        d = self.get(sid.split(" ", 1)[0])
        f = self.form(sid) or {}
        return [t.lower() for t in (f.get("primaryType") or d.get("primaryType"),
                                    f.get("secondaryType") or (None if f.get("primaryType") else d.get("secondaryType"))) if t]

    def name(self, sid):
        d = self.get(sid.split(" ", 1)[0])
        return d["name"] if " " not in sid else "%s (%s)" % (d["name"], sid.split(" ", 1)[1].capitalize())

    def evolves_into_at(self, sid):
        """The minimum level `sid` is reached at by a level-up evolution of its pre-evolution, or None (it is a base
        stage, or reached by an item, trade or friendship)."""
        pre = self.get(sid).get("preEvolution")
        if not pre:
            return None
        levels = []
        for e in self.get(pre.split()[0]).get("evolutions", []):
            # a regional or pattern form is the species plus a property string ("decidueye hisuian", Vivillon's patterns)
            if e.get("result", "").split()[:1] == [sid]:
                levels += [int(r["minLevel"]) for r in e.get("requirements", []) if r.get("variant") == "level"]
        return min(levels) if levels else None


def load_species():
    """(trees, source): {tree id: {"line": [...], "bands": {band: [species]}, "levels": {band: "lo-hi"}, "why": str}}
    from the designer's file, plus the world tree's file (data/world_tree_bird_species.json) (its own explicit entries)."""
    if not SPECIES.is_file():
        raise TreeBirdsError("%s is missing: the species come from it (the designer's file)" % SPECIES)
    doc = json.loads(SPECIES.read_text(encoding="utf-8"))
    trees = {}
    for tid, v in doc["trees"].items():
        lv = {b: v["levels"] for b in BAND_ORDER}
        if v.get("crown_levels"):
            lv["crown"] = v["crown_levels"]
        trees[tid] = {"line": v["line"], "bands": v["bands"], "levels": lv, "why": v["why"]}
    return trees


def lo_hi(level):
    lo, hi = (int(x) for x in str(level).split("-"))
    return lo, hi


def band_entries(jar, tree_id, line, band, species, level):
    """(scope entries, habitat entries, problems) of one band's pool. The base stage spawns over the band's levels; an
    evolved stage from its evolution level to the band's top, and only if that level is at or under the top."""
    lo, hi = lo_hi(level)
    flat, rich, problems, rank = [], [], [], 0
    for sid in species:
        evo = jar.evolves_into_at(sid)
        if sid != line[0] and evo is None:
            problems.append("%s %s: %s is not the base stage and no level-up evolution reaches it" % (tree_id, band, sid))
            continue
        if evo is not None and evo > hi:
            problems.append("%s %s: %s evolves at %d, over the band's top %d" % (tree_id, band, sid, evo, hi))
            continue
        a, b = (max(lo, evo), hi) if evo is not None else (lo, hi)
        bucket, weight = STAGE_BUCKETS[min(rank, len(STAGE_BUCKETS) - 1)]
        rank += 1
        why = "base stage" if evo is None else "level evolution eligible (%d <= %d, Cobblemon jar)" % (evo, hi)
        flat.append({"species": sid, "bucket": bucket, "level": "%d-%d" % (a, b), "weight": weight, "ambient": True,
                     "eligibility_reason": why})
        rich.append(dict(flat[-1], pokemon=sid, species=jar.name(sid), types=jar.types(sid), family=line[0],
                         family_priority="anchor"))
    for sid in line:
        if sid in species:
            continue
        evo = jar.evolves_into_at(sid)
        reason = ("evolution requires level %d; band begins at %d" % (evo, lo) if evo is not None and sid != line[0]
                  else "evolution by a method that is not a level" if sid != line[0] else "base stage not in this band")
        # the scope entry's bucket must be one of Cobblemon's four (validate_data's schema); the habitats[] copy of an
        # unplaced stage says "authored-only", as every existing pool's does
        flat.append({"species": sid, "bucket": "ultra-rare", "level": "%d-%d" % (lo, hi), "weight": 0, "ambient": False,
                     "eligibility_reason": reason})
        rich.append(dict(flat[-1], pokemon=sid, species=jar.name(sid), types=jar.types(sid), family=line[0],
                         family_priority="anchor", bucket="authored-only"))
    return flat, rich, problems


def pool_defs(jar, plan_doc):
    """{pool id: {"band", "tree", "flat", "rich", "level_band", "why"}} for every pool the species file and the plan
    name, and the problems found. The existing pool <tree> takes the crown band; tbird_<tree>_low / _mid the others."""
    species = load_species()
    out, problems = {}, []
    for tid, v in sorted(species.items()):
        for band in BAND_ORDER:
            pool = tid if band == "crown" else "%s%s_%s" % (PREFIX, tid, band)
            if band != "crown" and tid not in plan_doc["trees"]:
                continue           # no nest for it here (a grove elder): the band has nowhere to spawn
            flat, rich, pr = band_entries(jar, tid, v["line"], band, v["bands"][band], v["levels"][band])
            problems += pr
            lo, hi = lo_hi(v["levels"][band])
            out[pool] = {"band": band, "tree": tid, "flat": flat, "rich": rich, "level_band": {"minimum": lo, "maximum": hi},
                         "why": "%s band of the tree's unique line (%s) from data/tree_bird_species.json (PROPOSED, "
                                "2026-10-21): %s" % (band, " > ".join(v["line"]), v["why"])}
    return out, problems


def world_species():
    """The world tree's species: the owner's explicit entries per band (data/world_tree_bird_species.json)."""
    return json.loads(WORLD_SPECIES.read_text(encoding="utf-8"))


def world_pool_defs(jar):
    doc = world_species()
    out = {}
    for band, spec in doc["bands"].items():
        pool = "%s%s_%s" % (PREFIX, WORLD_TREE, band)
        flat, rich = [], []
        for e in spec["entries"]:
            sid = e["species"]
            jar.form(sid)            # a form the jar does not have is an error here, not a spawn that never loads
            why = "the owner's set (data/world_tree_bird_species.json): %s" % e["note"]
            if e.get("legendary_exemption"):
                why += " | NAMED EXEMPTION to 'no legendary in a nest pool': %s" % e["legendary_exemption"]
            f = {"species": sid, "bucket": e["bucket"], "level": e.get("levels", spec["levels"]), "weight": float(e["weight"]),
                 "ambient": True, "eligibility_reason": why}
            flat.append(f)
            rich.append(dict(f, pokemon=sid, species=jar.name(sid), types=jar.types(sid), family=e["family"],
                             family_priority="anchor"))
        lo, hi = lo_hi(spec["levels"])
        out[pool] = {"band": band, "tree": WORLD_TREE, "flat": flat, "rich": rich,
                     "level_band": {"minimum": lo, "maximum": hi},
                     "why": "the world tree's %s band (%s): the owner's species, levels %s, from "
                            "data/world_tree_bird_species.json (not the one-line-per-tree rule: the owner's classics)."
                            % (band, spec["height"], spec["levels"])}
    return out


def apply_spawns(spawns_doc, defs):
    """spawns_doc with the habitat entries of every pool in `defs` replaced (scope = the pool id) and its habitats[]
    defs added or refreshed. Returns a new dict; nothing outside those pools changes."""
    doc = json.loads(json.dumps(spawns_doc))
    scopes = set(defs)
    first = next((i for i, e in enumerate(doc["entries"]) if e["mechanism"] == "habitat_block" and e["scope"] in scopes), None)
    kept = [e for e in doc["entries"] if not (e["mechanism"] == "habitat_block" and e["scope"] in scopes)]
    new = []
    for pool, d in sorted(defs.items()):
        for e in d["flat"]:
            new.append({"id": "habitat.%s.%s" % (pool, e["species"]), "species": e["species"], "bucket": e["bucket"],
                        "level": e["level"], "weight": e["weight"], "ambient": e["ambient"], "scope": pool,
                        "mechanism": "habitat_block", "conditions": {}, "eligibility_reason": e["eligibility_reason"],
                        "spawnable_position": "grounded"})
    at = first if first is not None else next(i for i, e in enumerate(kept) if e["mechanism"] == "habitat_block")
    doc["entries"] = kept[:at] + new + kept[at:]
    habs = {h["id"]: h for h in doc["habitats"]}
    out = []
    for h in doc["habitats"]:
        if h["id"].startswith(PREFIX):
            continue                       # regenerated below
        if h["id"] in defs:
            h = dict(h, entries=defs[h["id"]]["rich"], level_band=defs[h["id"]]["level_band"], why=defs[h["id"]]["why"])
        out.append(h)
        for pool, d in sorted(defs.items()):
            if pool.startswith(PREFIX) and d["tree"] == h["id"]:
                out.append(_new_habitat(pool, d, h))
    have = {h["id"] for h in out}
    for pool, d in sorted(defs.items()):
        if pool.startswith(PREFIX) and pool not in have:            # the world tree: no habitat to sit beside
            out.append(_new_habitat(pool, d, {"display_name": "World tree (Foothill Woods)"}))
    doc["habitats"] = out
    return doc


def _new_habitat(pool, d, tree_h):
    return {"id": pool, "display_name": "%s, %s band" % (tree_h["display_name"], d["band"]),
            "intended_location": "the %s band's nests of %s (data/tree_bird_nests.json, tbird_ records in "
                                 "data/habitat_blocks.json)" % (d["band"], d["tree"]),
            "mechanism": "habitat_block", "replace_spawns": False, "level_band": d["level_band"], "why": d["why"],
            "entries": d["rich"], "placement_status": "pending_or_authored_world_asset"}


def all_defs(jar, plan_doc):
    defs, problems = pool_defs(jar, plan_doc)
    defs.update(world_pool_defs(jar))
    return defs, problems


# ---------------------------------------------------------------------------------------------------------- the CLI
def dumps(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=["plan", "merge", "spawns"])
    p.add_argument("--check", action="store_true")
    p.add_argument("--jar")
    a = p.parse_args(argv)
    plan_doc = json.loads(PLAN.read_text(encoding="utf-8")) if a.cmd != "plan" else plan()
    if a.cmd == "plan":
        target, text = PLAN, json.dumps(plan_doc, indent=1) + "\n"
    elif a.cmd == "merge":
        target, text = HABITATS, dumps(merged_manifest(plan_doc))
    else:
        jar = Jar(jar_path(a.jar))
        defs, problems = all_defs(jar, plan_doc)
        for m in problems:
            print("PROBLEM", m)
        if problems:
            return 1
        target, text = SPAWNS, dumps(apply_spawns(json.loads(SPAWNS.read_text(encoding="utf-8")), defs))
    if a.check:
        same = target.read_text(encoding="utf-8") == text
        print("%s %s the committed %s" % (a.cmd, "matches" if same else "DIFFERS from", target.name))
        return 0 if same else 1
    target.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %s" % target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
