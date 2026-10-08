"""A small synthetic server for tools/tm_gate.py: jars and a datapack written with zipfile, and a recipe-book model.

Shared by tests/test_tm_gate.py and the C22 contract in tests/test_system_contracts.py. Nothing here is read from a real
jar: every recipe, advancement and function is written below, so the tests' expectations (what a fresh player's book
must hold, which TM unlocks at which badge) are stated here by hand, not computed by the generator under test.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETS = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))

# the 23 shelf TMs' gem types, by the gym that sells them (Brock's two normal moves are in his own pool)
SHELF_GEM = {
    "bide": "normal", "headbutt": "normal", "rocktomb": "rock", "rockslide": "rock",
    "bubblebeam": "water", "waterpulse": "water", "scald": "water",
    "thunderbolt": "electric", "shockwave": "electric", "thunder": "electric",
    "megadrain": "grass", "gigadrain": "grass",
    "toxic": "poison", "poisonjab": "poison", "poisonfang": "poison", "poisongas": "poison",
    "psywave": "psychic", "calmmind": "psychic", "skillswap": "psychic",
    "overheat": "fire", "fireblast": "fire", "fissure": "ground", "earthquake": "ground",
}
# discs chosen so the grade envelope is easy to state: diamond 3 (Thunder), emerald 5 (Toxic), netherite 7 (Overheat)
SHELF_DISC = {"thunder": "diamond", "earthquake": "diamond", "overheat": "netherite", "fissure": "netherite",
              "toxic": "emerald", "calmmind": "emerald"}
# unlisted TMs (no shelf line, no outlier group) and the badge the power rule gives them, worked by hand from the
# move's Showdown fields with docs/mechanics/TM_POWER_GATE.md 2 and the bands of 3 (badge 1 below 35; tops 54, 64, 74,
# 84, 94, 104 inclusive; badge 8 above). Neither the type nor the disc grade enters: the gems and discs below only make
# the recipes look like TMCraft's.
UNLISTED = {
    "icebeam": ("ice", "diamond", None, 6),        # 90 + 10% freeze x 30 = 93
    "tackle": ("normal", "copper", None, 2),       # 40
    "heatwave": ("fire", "gold", None, 6),         # 90% x (95 + 10% burn x 30) = 88.2
    "hurricane": ("flying", "netherite", None, 5),  # 70% x (110 + 30% confusion x 12) = 79.5
    "shadowball": ("ghost", "gold", None, 5),      # 80 + 20% x one sp.def stage x 8 = 81.6 (badge 8 under the old rule)
    "hydropump": ("water", "netherite", None, 5),  # 80% x 110 x 0.95 (5 PP) = 83.6
    "howl": ("normal", None, "tackle", 2),         # +1 attack: 35, not below 35 (a chain TM: tackle in, no floor)
    "flareblitz": ("fire", None, "icebeam", 7),    # 120 x (1 - 0.5 x 33/100) + 10% burn x 30 = 103.2
}
MSD_JAR = "mega_showdown-fabric-fixture.jar"
MSD_MOVES = "assets/mega_showdown/showdown/moves.js"
MSD_TEXT = "const Moves = {}; // the fixture's moves.js: the committed score table is bound to it by score_table()\n"
ORDINARY = ["minecraft:oak_planks", "minecraft:stick", "cobblemon:poke_ball", "cobblemon:great_ball",
            "handcrafted:oak_chair", "cobblemon:to_nowhere"]
WITH_ADV = {"minecraft:oak_planks", "minecraft:stick"}   # the rest have no unlock advancement: doLimitedCrafting alone
SPECIAL = ["minecraft:firework_rocket"]                  # would strand them
DEVICES = ["minecraft:crafter", "carved_wood:spruce_crafter", "toms_storage:crafting_terminal"]


def shelf_from_markets():
    """{tmcraft item: gate_badge}, read here from data/markets.json, not through the generator."""
    out = {}
    for counter in MARKETS["counters"]:
        for key in ("stock", "held_stock"):
            for line in counter.get(key) or []:
                if str(line.get("item", "")).startswith("tmcraft:tm_") and isinstance(line.get("gate_badge"), int):
                    out[line["item"]] = line["gate_badge"]
    return out


def score_table():
    """The committed score table (docs/mechanics/TM_POWER_GATE.json), with its moves_sha256 set to the fixture's own
    moves.js: the fixture server says its battles run the moves the table was scored from. Every score is the real one."""
    t = json.loads((ROOT / "docs" / "mechanics" / "TM_POWER_GATE.json").read_text(encoding="utf-8"))
    t["moves_sha256"] = hashlib.sha256(MSD_TEXT.encode("utf-8")).hexdigest()
    return t


def _shapeless(result, *items):
    return {"type": "minecraft:crafting_shapeless", "ingredients": [{"item": i} for i in items],
            "result": {"id": result, "count": 1}}


def _shaped(result, key):
    return {"type": "minecraft:crafting_shaped", "pattern": ["AB"], "key": {k: {"item": v} for k, v in key.items()},
            "result": {"id": result, "count": 1}}


def _unlock(rid, item):
    return {"parent": "minecraft:recipes/root",
            "criteria": {"has": {"trigger": "minecraft:inventory_changed", "conditions": {"items": [{"items": item}]}},
                         "has_the_recipe": {"trigger": "minecraft:recipe_unlocked", "conditions": {"recipe": rid}}},
            "requirements": [["has", "has_the_recipe"]], "rewards": {"recipes": [rid]}}


def _jar(path, files, mod_id=None):
    with zipfile.ZipFile(path, "w") as z:
        if mod_id:
            z.writestr("fabric.mod.json", json.dumps({"id": mod_id}))
        for rel, body in files.items():
            z.writestr(rel, body if isinstance(body, str) else json.dumps(body))


def _p(rid, kind="recipe"):
    ns, path = rid.split(":")
    return "data/%s/%s/%s.json" % (ns, kind, path)


def build_server(tmp, extra_functions=None, extra_advancements=None):
    """A server dir and a vanilla jar. Returns (server_dir, vanilla_jar, expected) where expected names every loaded
    recipe id by role, stated by this fixture."""
    tmp = Path(tmp)
    server = tmp / "server"
    (server / "mods").mkdir(parents=True)
    (server / "datapacks").mkdir()
    vanilla = tmp / "vanilla.jar"
    _jar(vanilla, {
        _p("minecraft:oak_planks"): _shapeless("minecraft:oak_planks", "minecraft:oak_log"),
        _p("minecraft:recipes/building_blocks/oak_planks", "advancement"): _unlock("minecraft:oak_planks",
                                                                                   "minecraft:oak_log"),
        _p("minecraft:stick"): _shaped("minecraft:stick", {"A": "minecraft:oak_planks", "B": "minecraft:oak_planks"}),
        _p("minecraft:recipes/misc/stick", "advancement"): _unlock("minecraft:stick", "minecraft:oak_planks"),
        _p("minecraft:crafter"): _shaped("minecraft:crafter", {"A": "minecraft:iron_ingot", "B": "minecraft:dropper"}),
        _p("minecraft:recipes/redstone/crafter", "advancement"): _unlock("minecraft:crafter", "minecraft:dropper"),
        _p("minecraft:firework_rocket"): {"type": "minecraft:crafting_special_firework_rocket"},
        _p("minecraft:iron_ingot_from_smelting"): {"type": "minecraft:smelting", "ingredient": {"item": "x:y"},
                                                   "result": {"id": "minecraft:iron_ingot"}},
    })
    _jar(server / "mods" / "cobblemon.jar", {
        _p("cobblemon:poke_ball"): _shaped("cobblemon:poke_ball", {"A": "cobblemon:red_apricorn",
                                                                   "B": "minecraft:iron_ingot"}),
        _p("cobblemon:great_ball"): _shaped("cobblemon:great_ball", {"A": "cobblemon:blue_apricorn",
                                                                     "B": "minecraft:iron_ingot"}),
        # a recipe dropped by a load condition on a mod that is not loaded: never in the book, never counted
        _p("cobblemon:gone"): dict(_shapeless("cobblemon:gone", "minecraft:dirt"), **{
            "fabric:load_conditions": [{"condition": "fabric:all_mods_loaded", "values": ["not_a_mod"]}]}),
        _p("cobblemon:to_nowhere"): _shapeless("cobblemon:to_nowhere", "minecraft:dirt"),
    }, "cobblemon")
    _jar(server / "mods" / "handcrafted.jar", {
        _p("handcrafted:oak_chair"): _shaped("handcrafted:oak_chair", {"A": "minecraft:oak_planks",
                                                                       "B": "minecraft:stick"}),
    }, "handcrafted")
    _jar(server / "mods" / "carved_wood.jar", {
        _p("carved_wood:spruce_crafter"): _shaped("carved_wood:spruce_crafter", {"A": "minecraft:iron_ingot",
                                                                                 "B": "minecraft:dropper"}),
        _p("carved_wood:recipes/redstone/spruce_crafter", "advancement"): _unlock("carved_wood:spruce_crafter",
                                                                                  "minecraft:dropper"),
        _p("carved_wood:wooden_crafter"): {"type": "carved_wood:crafting_special_crafter"},
    }, "carved_wood")
    _jar(server / "mods" / "toms.jar", {
        _p("toms_storage:crafting_terminal"): _shaped("toms_storage:crafting_terminal", {
            "A": "toms_storage:terminal", "B": "minecraft:crafting_table"}),
    }, "toms_storage")
    tm = {}
    tm_ids, conversions = {}, []
    for move, gem in SHELF_GEM.items():
        rid = "tmcraft:tm_" + move
        tm[_p(rid)] = _shapeless(rid, "tmcraft:%s_blank_disc" % SHELF_DISC.get(move, "gold"), "cobblemon:%s_gem" % gem)
        tm[_p("tmcraft:recipes/misc/tm_" + move, "advancement")] = _unlock(rid, "cobblemon:%s_gem" % gem)
        tm_ids[rid] = rid
    for move, (gem, disc, inp, _) in UNLISTED.items():
        rid = "tmcraft:tm_" + move
        first = "tmcraft:%s_blank_disc" % disc if disc else "tmcraft:tm_" + inp
        tm[_p(rid)] = _shapeless(rid, first, "cobblemon:%s_gem" % gem)
        tm[_p("tmcraft:recipes/misc/tm_" + move, "advancement")] = _unlock(rid, "cobblemon:%s_gem" % gem)
        tm_ids[rid] = rid
    for rid in list(tm_ids):
        conv = "tmcraft:cobblemon/to_cobblemon_" + rid.split(":")[1]
        tm[_p(conv)] = {"type": "minecraft:crafting_shapeless", "ingredients": [{"item": rid}],
                        "result": {"id": "cobblemon:technical_machine"}}
        conversions.append(conv)
    tm[_p("tmcraft:simpletms/from_simpletms_tm_tackle")] = dict(
        _shapeless("tmcraft:tm_tackle", "simpletms:tm_tackle"),
        **{"fabric:load_conditions": [{"condition": "fabric:all_mods_loaded", "values": ["simpletms"]}]})
    tm[_p("tmcraft:copper_blank_disc")] = _shapeless("tmcraft:copper_blank_disc", "minecraft:copper_ingot")
    tm[_p("tmcraft:recipes/misc/copper_blank_disc", "advancement")] = _unlock("tmcraft:copper_blank_disc",
                                                                             "minecraft:copper_ingot")
    _jar(server / "mods" / "tmcraft.jar", tm, "tmcraft")
    _jar(server / "mods" / MSD_JAR, {MSD_MOVES: MSD_TEXT}, "mega_showdown")
    dp = {"pack.mcmeta": {"pack": {"pack_format": 48, "description": "x"}},
          "data/cobbleverse/function/starter_pack.mcfunction": "give @s cobblemon:poke_ball 5\nrecipe give @s *\n",
          "data/cobblemon/advancement/root.json": {"criteria": {"picked_starter": {"trigger": "cobblemon:pick_starter"}},
                                                   "rewards": {"function": "cobbleverse:starter_pack"}}}
    for rel, text in (extra_functions or {}).items():
        dp[rel] = text
    for rel, body in (extra_advancements or {}).items():
        dp[rel] = body
    _jar(server / "datapacks" / "COBBLEVERSE-DP.zip", dp)
    expected = {
        "ordinary": ORDINARY + ["tmcraft:copper_blank_disc"],
        "with_adv": WITH_ADV | {"tmcraft:copper_blank_disc"},
        "special": SPECIAL,
        "devices": ["minecraft:crafter", "carved_wood:spruce_crafter", "toms_storage:crafting_terminal"],
        "tms": sorted(tm_ids),
        "conversions": conversions,
        "unlisted_badge": {"tmcraft:tm_" + m: v[3] for m, v in UNLISTED.items()},
        "tm_advancements": sorted("tmcraft:recipes/misc/tm_" + m for m in list(SHELF_GEM) + list(UNLISTED)),
        "device_advancements": ["minecraft:recipes/redstone/crafter", "carved_wood:recipes/redstone/spruce_crafter"],
    }
    expected["book_all"] = set(expected["ordinary"] + expected["devices"] + expected["tms"] + conversions
                               + ["minecraft:iron_ingot_from_smelting"] + SPECIAL)
    # `recipe give @s *` never adds a special recipe (ServerRecipeBook.addRecipes skips isSpecial)
    expected["book_all"] -= set(SPECIAL)
    return server, vanilla, expected


class Player:
    """The recipe book, advancements and score of one player, driven by the pack's own function text."""

    def __init__(self, book=(), flags=(), adv=()):
        self.book = set(book)
        self.adv = set(adv) | {"cobblers:flag/" + f for f in flags}
        self.score = None


def run(files, fn, player, all_recipes, depth=0):
    assert depth < 8, fn
    ns, path = fn.split(":", 1)
    text = files["data/%s/function/%s.mcfunction" % (ns, path)]
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"recipe (give|take) @s (\S+)", line)
        if m:
            ids = set(all_recipes) if m.group(2) == "*" else {m.group(2)}
            if m.group(1) == "give":
                player.book |= ids
            else:
                player.book -= ids
            continue
        m = re.fullmatch(r"execute unless entity @s\[advancements=\{(\S+)=true\}\] run function (\S+)", line)
        if m:
            if m.group(1) not in player.adv:
                run(files, m.group(2), player, all_recipes, depth + 1)
            continue
        m = re.fullmatch(r"advancement revoke @s only (\S+)", line)
        if m:
            player.adv.discard(m.group(1))
            continue
        m = re.fullmatch(r"scoreboard players set @s cobblers\.tmgate (\d+)", line)
        if m:
            player.score = int(m.group(1))
            continue
        if line == "scoreboard players reset @s cobblers.tmgate":
            player.score = None
            continue
        raise AssertionError("the model does not know the command %r in %s" % (line, fn))


def tick(files, player, all_recipes):
    """One server tick: the pack's tick function, then the player's minecraft:tick advancements (earn/<flag>)."""
    t = files["data/cobblers/function/tm_gate/tick.mcfunction"]
    m = re.search(r"execute as @a unless score @s cobblers\.tmgate matches (\d+) run function (\S+)", t)
    assert m, t
    if player.score != int(m.group(1)):
        run(files, m.group(2), player, all_recipes)
    for rel, body in sorted(files.items()):
        mm = re.fullmatch(r"data/cobblers/advancement/(tm_gate/earn/[a-z0-9_]+)\.json", rel)
        if not mm:
            continue
        aid = "cobblers:" + mm.group(1)
        doc = json.loads(body)
        crit = doc["criteria"]["held"]
        assert crit["trigger"] == "minecraft:tick", crit
        need = crit["conditions"]["player"][0]["predicate"]["type_specific"]["advancements"]
        if aid not in player.adv and all((a in player.adv) == v for a, v in need.items()):
            player.adv.add(aid)
            run(files, doc["rewards"]["function"], player, all_recipes)


def pick_starter(files, player, all_recipes, ours_first=False):
    """Cobbleverse's cobblemon:root fires (its starter pack gives every recipe) and so does every pack advancement on
    cobblemon:pick_starter; the order of the two rewards is not fixed, so the caller runs both."""
    if not ours_first:
        player.book |= set(all_recipes)
    for rel, body in sorted(files.items()):
        doc = json.loads(body) if rel.endswith(".json") and "/advancement/" in rel else None
        if doc and any(c.get("trigger") == "cobblemon:pick_starter" for c in (doc.get("criteria") or {}).values()):
            run(files, doc["rewards"]["function"], player, all_recipes)
    if ours_first:
        player.book |= set(all_recipes)
