#!/usr/bin/env python
"""What a wild alpha pays when it is beaten: no candies, and type gems that grow with its level (the owner, 2026-10-08:
"Option C for alphas. Candies out, gems in, paid by alpha level"), from data/alpha_spoils.json, as the world pack
build/datapacks/cobblers_alpha_spoils. Design: docs/mechanics/DROPS_PROGRESSION_SPLIT.md section 3 (option C, 3.5).

  python tools/alpha_spoils.py check    # the data against the jar it overrides; writes nothing
  python tools/alpha_spoils.py build    # check, then -> build/datapacks/cobblers_alpha_spoils

WHAT THE PACK SHIPS
  data/cobblemon/loot_table/alpha/alpha_rewards_tier{1..4}.json   each {"type": "minecraft:chest", "pools": []},
      at the jar's own path, so the jar's callback still runs and still asks for its tier table, and the table now
      yields nothing. An empty table is safe on its own: if the callback below never loads, the game is at the
      design's option A (no candies, the jar's gem rolls only).
  data/cobblemon/callbacks/battle_fainted/cobblers_alpha_spoils.molang   our callback, BESIDE the jar's
      pokemon_alpha_drops.molang, never over it (.claude/rules/datapacks.md: a callback fires only from
      data/cobblemon/callbacks/<event>/, and Cobblemon's own files are never overridden; EXP-042). Every file in the
      folder runs (CobblemonCallbacks.reload, DROPS_PROGRESSION_SPLIT.md 3.2, relayed).

WHAT THE CALLBACK DOES: on a battle faint of a wild alpha, the certain extra rolls of the jar's per-type tables
(cobblemon:alpha/types/<type>_rewards_tier<1|2>) that data/alpha_spoils.json `bands` names for the alpha's level, at the
type tier the jar's callback uses. `secondary` is the alpha's second type, or its only one; `primary` is its first.
The jar's callback probably never rolls a dual-type alpha's second type (it tests q.length of the one-entry list it
has just built: pokemon_alpha_drops.molang, the design's 3.3, REASONED, experiment X5); ours reads the length of the
Pokemon's own type list, so it pays the second type either way.

THE MOLANG IT USES, verified in Cobblemon-fabric-1.8.0+1.21.1.jar (javap, 2026-10-08), never assumed:
  - every member it reads (c.pokemon.actor.is_wild, .pokemon, .is_alpha, .entity, .world, .level, .types, .x/.y/.z,
    .spawn_loot_table_items, q.length) is one the jar's own callback reads; `check` fails on any other;
  - `types` (PokemonMoLangFunctions, lambda$21) is FormData.getTypes() mapped to ElementalType.getShowdownId() and
    returned as an ArrayStruct keyed "0", "1" (MoLangExtensionsKt.asArrayValue), so t.x[1] is the second type;
  - q.length (GeneralMoLangFunctions holder$lambda$23) returns a VariableStruct's map size (ArrayStruct extends
    VariableStruct), so a dual type reads 2 and a single type 1;
  - spawn_loot_table_items(id, x, y, z) (WorldMoLangFunctions) looks the table up in the server's reloadable loot
    registry, rolls it with an ORIGIN-only context and drops each non-empty stack as an item entity there: an empty
    table drops nothing.
  - a number joined to a string prints without a decimal (DoubleValue.asString, "%d" for an integral value), which
    the jar's own '_rewards_tier' + t.type_tier relies on too.

WHAT IS CHECKED (`check`), each from the jar, never from our output: the jar's callback still names exactly our four
tier tables at their level thresholds, its type-table pattern and its type tier; each tier table still carries exactly
the items recorded; every type the jar ships a table for is in our list, each table names its own gem, and the gem
is a registered item (a model in the jar); and each band's gems a KO, recomputed from the jar's type tables (the
jar's two 1-in-2 rolls plus ours), is the design's figure.

What is NOT verified: that the server loads the callback and the empty tables, or that any gem drops. Valid files
and the jar's code read above are the most this tool can claim; experiments/EXP-066-alpha-spoils is the proof.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "alpha_spoils.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_alpha_spoils"
PACK = "cobblers_alpha_spoils"
EMPTY = {"type": "minecraft:chest", "pools": []}
ROLLS = ("secondary", "primary")


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_jar():
    import player_guide_battles as PB
    return Path(PB.find_jar())


def table_path(rid):
    ns, path = rid.split(":", 1)
    return "data/%s/loot_table/%s.json" % (ns, path)


def type_table(doc, typ, tier):
    return doc["type_tables"]["pattern"].replace("<type>", typ).replace("<tier>", str(tier))


# ------------------------------------------------------------------------------------------------ the callback


def callback(doc):
    """The MoLang text of our callback, from the bands. Written only in forms the jar's own callback uses."""
    bands = doc["bands"]
    tt = doc["type_tables"]
    base = tt["pattern"].split("<type>")[0]
    suffix = tt["pattern"].split("<type>")[1].split("<tier>")[0]

    def flags(b):
        return ["t.cs_roll_%s = %d;" % (r, 1 if r in b["extra_rolls"] else 0) for r in ROLLS]

    L = ["c.pokemon.actor.is_wild ? {",
         "  t.cs_pokemon = c.pokemon.pokemon;",
         "  t.cs_pokemon.is_alpha ? {",
         "    t.cs_entity = t.cs_pokemon.entity;",
         "    t.cs_world = t.cs_entity.world;",
         "    t.cs_types = t.cs_pokemon.types;",
         "    t.cs_primary = t.cs_types[0];",
         "    t.cs_secondary = t.cs_types[0];",
         "    (q.length(t.cs_types) >= 2) ? {",
         "      t.cs_secondary = t.cs_types[1];",
         "    };",
         "    t.cs_tier = (t.cs_pokemon.level >= %d) ? 2 : 1;" % tt["tier2_from_level"]]
    L += ["    " + s for s in flags(bands[0])]
    for b in bands[1:]:
        L.append("    (t.cs_pokemon.level >= %d) ? {" % b["from_level"])
        L += ["      " + s for s in flags(b)]
        L.append("    };")
    for r in ROLLS:
        L += ["    (t.cs_roll_%s == 1) ? {" % r,
              "      t.cs_world.spawn_loot_table_items('%s' + t.cs_%s + '%s' + t.cs_tier, t.cs_entity.x, t.cs_entity.y, "
              "t.cs_entity.z);" % (base, r, suffix),
              "    };"]
    L += ["  };", "};"]
    return "\n".join(L) + "\n"


def members(script):
    """Every name read after a '.' that is not one of our own t.cs_ variables."""
    return {m for m in re.findall(r"\.([a-z_]+)", script) if not m.startswith("cs_")}


# ------------------------------------------------------------------------------------------------ the jar


def count_mean(entry):
    """The mean stack count of a loot entry: set_count with an int or a {min, max} uniform (inclusive ints)."""
    n = 1.0
    for f in entry.get("functions", []):
        if f.get("function", "").split(":")[-1] == "set_count":
            c = f["count"]
            if isinstance(c, (int, float)):
                n = float(c)
            elif isinstance(c, dict) and c.get("type", "minecraft:uniform").split(":")[-1] == "uniform":
                n = (int(c["min"]) + int(c["max"])) / 2.0
            else:
                raise ValueError("count %r" % (c,))
    return n


def item_mean(table, item):
    """Expected count of `item` per roll of a table whose every pool rolls once."""
    total = 0.0
    for p in table.get("pools", []):
        if p.get("rolls", 1) != 1:
            raise ValueError("a pool rolls %r, not 1" % (p.get("rolls"),))
        ents = p["entries"]
        w = sum(e.get("weight", 1) for e in ents)
        total += sum(e.get("weight", 1) / w * count_mean(e) for e in ents if e.get("name") == item)
    return total


def table_items(table):
    return [e["name"] for p in table.get("pools", []) for e in p.get("entries", []) if "name" in e]


def jar_read(jar):
    with zipfile.ZipFile(jar) as z:
        names = set(z.namelist())
        tables = {n: json.loads(z.read(n).decode("utf-8")) for n in names
                  if n.startswith("data/cobblemon/loot_table/alpha/") and n.endswith(".json")}
        cb = z.read("data/cobblemon/callbacks/battle_fainted/pokemon_alpha_drops.molang").decode("utf-8")
        gems = {n.split("/")[-1][:-5] for n in names
                if n.startswith("assets/cobblemon/models/item/") and n.endswith("_gem.json")}
    return {"names": names, "tables": tables, "callback": cb, "gem_models": gems}


def check(doc, jar=None):
    problems = []
    if doc.get("schema") != "cobblers.alpha_spoils/1":
        problems.append("schema is %r" % doc.get("schema"))
    j = jar if jar is not None else jar_read(find_jar())
    cb = j["callback"]
    if doc["jar_callback"] == doc["callback"]:
        problems.append("our callback is at the jar's path: never override Cobblemon's own callback")
    if Path(doc["callback"]).parent != Path(doc["jar_callback"]).parent:
        problems.append("our callback is not beside the jar's (%s): it would not fire on battle_fainted" % doc["callback"])
    # the jar's callback still asks for exactly our tier tables, at the recorded thresholds
    named = re.findall(r"'(cobblemon:alpha/alpha_rewards_tier\d)'", cb)
    if sorted(set(named)) != sorted(t["id"] for t in doc["candy_tables"]):
        problems.append("the jar's callback names %s, the data %s" % (sorted(set(named)),
                                                                     sorted(t["id"] for t in doc["candy_tables"])))
    for t in doc["candy_tables"]:
        if t["jar_from_level"] > 1 and ("(t.pokemon.level >= %d) ? {\n      t.loot_table = '%s';"
                                        % (t["jar_from_level"], t["id"])) not in cb:
            problems.append("the jar's callback no longer picks %s from level %d" % (t["id"], t["jar_from_level"]))
        got = j["tables"].get(table_path(t["id"]))
        if got is None:
            problems.append("the jar has no %s" % table_path(t["id"]))
        elif table_items(got) != t["items_as_read"]:
            problems.append("%s now carries %s, not the recorded %s" % (t["id"], table_items(got), t["items_as_read"]))
    tt = doc["type_tables"]
    if "t.type_tier = (t.pokemon.level >= %d) ? 2 : 1;" % tt["tier2_from_level"] not in cb:
        problems.append("the jar's callback no longer uses type tier 2 from level %d" % tt["tier2_from_level"])
    base = tt["pattern"].split("<type>")[0]
    if ("'%s' + t.type_name + '_rewards_tier' + t.type_tier" % base) not in cb or tt["pattern"] != base + "<type>_rewards_tier<tier>":
        problems.append("the jar's callback no longer rolls %s" % tt["pattern"])
    jr = doc["jar_rolls"]
    if cb.count("(math.random_integer(1, 2) == 1) ? {") != jr["type_rolls"] or jr["chance_each"] != 0.5:
        problems.append("the jar's callback no longer makes %d 1-in-2 type rolls" % jr["type_rolls"])
    # the types: the jar's list, each table names its own gem, the gem is an item
    jar_types = sorted({m.group(1) for n in j["tables"] for m in [re.fullmatch(
        r"data/cobblemon/loot_table/alpha/types/([a-z]+)_rewards_tier[12]\.json", n)] if m})
    if jar_types != sorted(tt["types"]):
        problems.append("the jar ships type tables for %s, the data lists %s" % (jar_types, sorted(tt["types"])))
    per_roll = {1: set(), 2: set()}
    for typ in tt["types"]:
        gem = tt["gem"].replace("<type>", typ)
        if gem.split(":", 1)[1] not in j["gem_models"]:
            problems.append("%s is not a registered item (no model in the jar)" % gem)
        for tier in (1, 2):
            tab = j["tables"].get(table_path(type_table(doc, typ, tier)))
            if tab is None:
                problems.append("the jar has no %s" % type_table(doc, typ, tier))
                continue
            try:
                m = item_mean(tab, gem)
            except (ValueError, KeyError) as e:
                problems.append("%s: %s" % (type_table(doc, typ, tier), e))
                continue
            if m <= 0:
                problems.append("%s gives no %s" % (type_table(doc, typ, tier), gem))
            per_roll[tier].add(round(m, 9))
    for tier, ms in per_roll.items():
        if len(ms) > 1:
            problems.append("type tier %d tables give different gem means %s: gems_per_ko is not one figure" % (tier, ms))
    # the bands: ascending, from 1, never straddling the type tier, each figure recomputed from the jar
    bands = doc["bands"]
    lv = [b["from_level"] for b in bands]
    if not bands or lv[0] != 1 or lv != sorted(set(lv)):
        problems.append("bands must start at level 1 and ascend: %s" % lv)
    if tt["tier2_from_level"] not in lv:
        problems.append("type tier 2 starts at %d, which no band starts at: a band would pay two figures"
                        % tt["tier2_from_level"])
    for b in bands:
        er = b["extra_rolls"]
        if any(r not in ROLLS for r in er) or len(er) != len(set(er)):
            problems.append("band %d: extra_rolls %s (each of %s at most once)" % (b["from_level"], er, ROLLS))
            continue
        tier = 2 if b["from_level"] >= tt["tier2_from_level"] else 1
        if len(per_roll[tier]) != 1:
            continue
        mean = next(iter(per_roll[tier]))
        got = (jr["type_rolls"] * jr["chance_each"] + len(er)) * mean
        if abs(got - b["gems_per_ko"]) > 0.001:
            problems.append("band %d: %.4f gems a KO from the jar's tables, the data says %s"
                            % (b["from_level"], got, b["gems_per_ko"]))
    # the callback reads only what the jar's own callback reads
    extra = sorted(members(callback(doc)) - set(re.findall(r"\.([a-z_]+)", cb)))
    if extra:
        problems.append("our callback reads %s, which the jar's own callback never does: verify before using" % extra)
    return problems


# ------------------------------------------------------------------------------------------------ the pack


def files(doc):
    out = {table_path(t["id"]): json.dumps(EMPTY, indent=2) + "\n" for t in doc["candy_tables"]}
    out[doc["callback"]] = callback(doc)
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: alphas pay type gems by level, no candies (tools/alpha_spoils.py)"}},
                                    indent=2) + "\n"
    return out


def build(doc):
    if OUT.exists():
        shutil.rmtree(OUT)
    n = 0
    for rel, text in files(doc).items():
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("check", "build"))
    a = ap.parse_args(argv)
    doc = load()
    problems = check(doc)
    for p in problems:
        print("PROBLEM", p)
    if problems:
        print("alpha_spoils check: %d problem(s)" % len(problems))
        return 1
    if a.cmd == "check":
        print("alpha_spoils check: ok: %d candy tables emptied, %d bands, %d types"
              % (len(doc["candy_tables"]), len(doc["bands"]), len(doc["type_tables"]["types"])))
        return 0
    n = build(doc)
    print("alpha_spoils build: %d files -> %s" % (n, OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
