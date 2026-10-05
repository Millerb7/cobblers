#!/usr/bin/env python
"""Independent audit of the town squares (R13) and the traders who stand on them (R17M).

Written by an agent that built neither tools/plaza_centre.py nor the market stalls. The owner, 2026-10-03: "Market
squares, stalls, the civic centre of each town ... places with a middle ... more traders, and new ones ... reading as
the place ... every town should have somewhere a player goes to spend money."

WHAT IT READS (expectations), and never from the builders' helpers:
  data/plaza_centres.json      the declared squares (rect, y), stalls (at, facing, keeper_at, sells) -- the CONTRACT
  data/placements.json         the settlements' plans (plaza, streets, anchors) and every placement (position,
                               rotation, template file); footprints are computed HERE from the template's NBT size
                               (tools/nbt.py, a generic reader) and the record's rotation
  derived/towns/<town>_plan.json   tools/town_plan.py's plan (street cells with their y, lots, anchors, lamps). If it
                               is missing the audit says so and names `python tools/town_plan.py <town>`
  data/towns.json              each town's footprint
  tools/ground.py              the heightmap, rounded (tools/ground.for_settlement for the sea town's decks)
  data/spawn_blocks.json, data/spawn_block_policy.json   blocks that decide encounters, and the policy's substitutions
  data/markets.json            the stalls' and counters' stock, gates, income_basis
  data/traders.json            the Mart's three items (stock_policy.mart)
  docs/world-building/TOWN_SQUARES_SURVEY.md section 0   the towns that had nowhere to spend money
  the jars                     minecraft: ids from the 1.21.1 client jar's lang file (the jar the builder names:
                               ModrinthApp meta versions 1.21.1-0.19.5); other namespaces from a folder of mod jars
                               (experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods/ or <server>/mods)

WHAT IT READS (the built result):
  build/datapacks/cobblers_plaza_centres/.../plaza_centres/<town>.mcfunction, VOXELISED in index.txt order: every
  `fill` and `setblock` applied to a block model; any other command is a problem (it would be unmodelled). The derived
  report (derived/plaza_centres/*.json) is NOT read: the function is what the server runs.
  The R17M step: tools/reapply.steps()'s R17M when it can be built (a full checkout after prepare); else what R17M
  composes (markets.npc_placements + markets.stall_placements for the `npc` actions, cobblers:markets/load and
  markets.MERCHANTS_FN for the `fn` ones), and the report says which. Its `npc` actions are the counters' dialogue
  clerks; its `fn` ids are FOLLOWED through the markets pack (build/datapacks/cobblers_markets, else markets.build()
  in memory, said so) via `function`, `schedule function` and `execute ... run function`, and every `summon` and
  `kill @e[type=cobblemon:npc,...]` in them is read with MY OWN parser (snbt() below; not traders.to_snbt, not
  markets.shop_offers). A stall's merchant is known by its tag <stall_merchant.tag>_<stall id>.
  That is reading the artifact under test, not computing an expectation from it.

THE CHECKS (each named in the output; P = problem, K = known defect, recorded in KNOWN below):
  square    every square inside its town's data/towns.json footprint; a planned town's square IS its plan's plaza
  ground    no block written on a street cell (plan cells, or Pallet's authored road polylines rasterised here at
            width/2 Euclidean), a lot, an anchor or a building footprint; nothing within 2 of Pallet's crossroads
            sign; every standing block inside the square's rect
  reach     the square reachable on foot from the Pokemon Center's and the Mart's doors, and every stall's customer
            cell from both. A door is NOT read from the template's jigsaw: the start is any cell one outside the
            middle half of the footprint's `facing` edge (the side the record says the building faces). Floor: the
            square's y on the square, a plan street cell's y, else round(heightmap); below sea level is water and not
            walked; a step changes the floor by at most 1; building footprints and every column with a non-carpet
            block written at standing height are walls
  stall     MY reading of the tent (the owner, 2026-10-04: "the stalls all block the villager from access ... more
            like pokemon ... slateport where there is a tent with wares"): a solid table is written at `at`; the
            keeper stands IN FRONT of it, at at + step(facing), on the table's y; feet and head are air in the model
            (written or cleared by the function); the block under the feet is floor (written, the square's y on the
            square, a street's y, or round(heightmap) off it); the yaw faces the CUSTOMERS, step(facing) (Minecraft
            yaw: x = -sin, z = cos, within 22.5 degrees); the customer's cell, at + 2 step(facing), has nothing solid
            at feet or head (a carpet is walked over) and is on the keeper's floor: nothing between player and keeper.
            The customer cell is the one `reach` walks to
  spawn     no written block is in data/spawn_blocks.json, is water or waterlogged, or is a `from` of
            data/spawn_block_policy.json's substitutions
  light     MY rule, not the generator's: real emission (lantern, sea lantern, froglight, campfire, glowstone 15;
            end rod and torch 14; soul lantern 10), Manhattan distance in 3D, no occlusion, light at a cell's standing
            block (floor + 1) at least 1 (hostile mobs need block light 0 since 1.18). Lights: every emitter the
            functions write, the plan's lamps (the lamp_block one below the plan's `at`) and earthwork lanterns.
            Cells: every square cell no standing piece covers, street cells over the square INCLUDED (the generator
            leaves those to the street lamps; I do not)
  staff     every contract stall has exactly one R17M keeper -- a counter's dialogue clerk (`npc` action) or a stall's
            merchant (a summon in the functions R17M runs) -- at its keeper_at with its yaw (the merchant's
            Rotation[0]); every keeper stands at a contract keeper_at, or is in a declared fallback town (Fossick
            mining_town, Northlight, Redbrow tableland_stop, the Deep's city deep_city); a record's `sells` is its
            stall's theme word; every sited stall has exactly one merchant summon with its tag, an unsited one none;
            no R17M `npc` action is a cobblers:npc_stall_* dialogue keeper and no followed function summons a
            cobblemon:npc; each merchant's functions kill type=cobblemon:npc centred on its own block (the dialogue
            keeper it replaces), with a radius that reaches no counter clerk
  merchant  each merchant summon is cobbledollars:cobble_merchant, centred on its block (x.5, whole y, z.5), NoAI and
            PersistenceRequired 1b, named its keeper's name
  shop      each merchant's CobbleMerchantShop is ONE category equal to its stall's non-empty `category`; one offer per
            stall line (data/markets.json stock), Item count 1, Price a whole-number string with Price x the line's
            count = the line's price; no offer without a line; and no sited stall line gated (a merchant shows one
            list to every player: a gated line belongs on a counter)
  items     every item on an emitted stall or counter exists in a jar (NOT CHECKED, said so, without the jar); none
            places a spawn-condition block (my own item -> block map, PLACES_BLOCK); none is a ball, a battle item or
            a boost unless gated on a badge (my own vocabulary: any non-vanilla id outside the convenience namespaces,
            every *_ball, and the vanilla power list POWER_VANILLA)
  theme     every stall line fits its theme by THEME_WORDS below; lines judged by hand are HAND_JUDGED, with why
  spend     every town TOWN_SQUARES_SURVEY section 0 lists as having nowhere to spend money now has an emitted stall or
            counter selling something other than the Mart's three items
  curve     the critical path's ask, recomputed from income_basis.counts' own words (critical towns from data/towns.json
            critical_path; every counter line; a stall's GATED lines only; a pick-one group at its dearest; stretch
            excluded), shown per badge, within target_ratio, and equal to BASELINE_CURVE (the curve at 31e9b2a, before
            any stall existed): the stalls moved no money

INDEPENDENCE, PROVEN BY MUTATING THE GENERATORS (tests/test_town_squares_audit.py; data untouched):
  - tools/plaza_centre.py piece_stall made to drop its counter block: the builder's own checks pass (they compare the
    record with the piece's position, not with the blocks), and this audit names every stall's missing counter
  - tools/plaza_centre.py piece_lamp_post's lantern swapped for a chain AND lights_of taught that a chain is a light
    (a shared derivation): the builder still reports every cell lit; this audit names the dark cells
  Run 2026-10-04 at 7a7272d: both caught (see the tests). Re-run at 06e22fb (the tent and the merchants): still caught,
  and three more:
  - tools/plaza_centre.py plan_town made to drop each tent's footprint clear (`fill ... minecraft:air`): the builder's
    checks pass (they read the piece, not the function), and this audit names the keeper's feet "never written or
    cleared" at all 43 stalls -- in the world, the old booth's counter log left where the keeper now stands
  - tools/markets.py position() made to seat each contract keeper on its table, turned to face it (the old booth's
    convention): markets.merchant_problems PASSES it (it reads the seat through position()), and this audit names all
    43 stalls unstaffed
  - tools/markets.py merchant_shop() made to double every Price: this audit names every sited stall line's price, and
    nothing else (markets.merchant_problems catches this one too; the mutation proves this reader reads the text)
  Not mutable on the plaza side: shifting the tent's keeper inside piece_stall, or putting a block in its or the
  customer's cell, is refused by plaza_centre's own build (its record-drift and face-to-face checks), so no such
  function can be emitted to audit.

NOT COVERED: anything at runtime -- that a merchant or NPC spawns, stays, faces, or sells; that the merchant's screen
charges its Price (docs: not yet observed); that the _done step's kill actually removes the old keeper; that a dialogue option charges; real
light with occlusion and skylight; real pathfinding (doors, stairs, slabs, fences: a fence is treated as a wall only
when written at standing height); what the world already holds round the square (other packs' blocks, donors); the
Deep's city's stalls (unsited, declared no_counter).

  python tools/town_squares_audit.py [--source-root R] [--server-dir S | --jar-dir D] [--vanilla-jar J] [--json OUT]
exit 1 on any problem; known defects are printed and do not fail the run.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import zipfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

FUNC_DIR = ROOT / "build" / "datapacks" / "cobblers_plaza_centres" / "data" / "cobblers" / "function" / "plaza_centres"
PLAN_DIR = ROOT / "derived" / "towns"
SURVEY = ROOT / "docs" / "world-building" / "TOWN_SQUARES_SURVEY.md"
DEFAULT_JAR_DIR = ROOT / "experiments" / "EXP-000-cobblemon-1.8-compat" / "runtime" / "server" / "mods"
DEFAULT_VANILLA = Path(os.environ.get("APPDATA", "")) / "ModrinthApp" / "meta" / "versions" / "1.21.1-0.19.5" / "1.21.1-0.19.5.jar"

STEP = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
FALLBACK_TOWNS = {"mining_town", "northlight", "tableland_stop", "deep_city"}
# a stand outside any town (2026-10-05): its keeper stands where its own place's record says, never anywhere else --
# {markets `town` value: (data file, key of the stand record whose `feet` is the keeper's cell)}
PLACE_STANDS = {"pokemon_farm": ("pokemon_farm.json", "stand_keeper")}
# TOWN_SQUARES_SURVEY.md section 0, "Places where a player can spend nothing beyond the Mart clerk's three items"
SURVEY_NO_SPEND = {"Sunset West": "sunset_west", "Pacifidlog": "sea_town", "Pallet": "hometown",
                   "Redbrow": "tableland_stop", "The Deep's city": "deep_city"}

EMISSION = {"minecraft:lantern": 15, "minecraft:sea_lantern": 15, "minecraft:glowstone": 15,
            "minecraft:ochre_froglight": 15, "minecraft:verdant_froglight": 15, "minecraft:pearlescent_froglight": 15,
            "minecraft:jack_o_lantern": 15, "minecraft:shroomlight": 15, "minecraft:campfire": 15,
            "minecraft:end_rod": 14, "minecraft:torch": 14, "minecraft:wall_torch": 14,
            "minecraft:soul_lantern": 10, "minecraft:soul_campfire": 10, "minecraft:soul_torch": 10}
# blocks a player walks over or through at standing height (not walls)
PASSABLE = re.compile(r"minecraft:(?:air|.*_carpet|moss_carpet|.*_pressure_plate|.*_button|rail|.*_sign|.*_wall_sign)$")

# the block an item puts down when it is not its own id
PLACES_BLOCK = {"minecraft:wheat_seeds": "minecraft:wheat", "minecraft:beetroot_seeds": "minecraft:beetroots",
                "minecraft:melon_seeds": "minecraft:melon_stem", "minecraft:pumpkin_seeds": "minecraft:pumpkin_stem",
                "minecraft:torchflower_seeds": "minecraft:torchflower_crop", "minecraft:pitcher_pod": "minecraft:pitcher_crop",
                "minecraft:potato": "minecraft:potatoes", "minecraft:carrot": "minecraft:carrots",
                "minecraft:sweet_berries": "minecraft:sweet_berry_bush", "minecraft:glow_berries": "minecraft:cave_vines",
                "minecraft:cocoa_beans": "minecraft:cocoa", "minecraft:redstone": "minecraft:redstone_wire",
                "minecraft:string": "minecraft:tripwire", "minecraft:torch": "minecraft:wall_torch",
                "minecraft:water_bucket": "minecraft:water", "minecraft:lava_bucket": "minecraft:lava",
                "minecraft:bone_meal": "minecraft:poppy"}   # bone meal on grass grows flowers: judged as placing one
# ...and what a placed block grows into (a stem fruits)
GROWS = {"minecraft:pumpkin_stem": "minecraft:pumpkin", "minecraft:melon_stem": "minecraft:melon",
         "minecraft:torchflower_crop": "minecraft:torchflower", "minecraft:pitcher_crop": "minecraft:pitcher_plant"}
CONVENIENCE_NS = {"sophisticatedbackpacks", "comforts", "waystones"}
POWER_VANILLA = re.compile(r"minecraft:(?:potion|splash_potion|lingering_potion|tipped_arrow|golden_apple|"
                           r"enchanted_golden_apple|totem_of_undying|ender_pearl|experience_bottle|enchanted_book|"
                           r".*_spawn_egg|diamond_.*|netherite_.*|elytra|trident)$")

# ---- the theme vocabulary: per theme word, the item paths (minecraft: assumed) that read as that stall's goods.
COOKED = {"bread", "baked_potato", "cooked_beef", "cooked_chicken", "cooked_mutton", "cooked_porkchop", "cooked_rabbit",
          "cooked_cod", "cooked_salmon", "rabbit_stew", "mushroom_stew", "beetroot_soup", "pumpkin_pie"}
THEME_WORDS = {
    # 2026-10-05, Arrow Creeks Farm's stand: what the owner's farm makes ("milk, leather, yadda yadda") and its fields
    "farm goods": {"milk_bucket", "white_wool", "leather", "honey_bottle", "honeycomb", "egg", "feather", "carrot",
                   "potato", "beetroot", "wheat", "hay_block"},
    "workstations": {"stonecutter", "smithing_table", "grindstone", "anvil", "crafting_table", "loom", "fletching_table",
                     "cartography_table", "barrel", "composter", "blast_furnace", "smoker"},
    "tools": {"iron_pickaxe", "iron_shovel", "iron_axe", "iron_hoe", "stone_pickaxe", "stone_shovel", "stone_axe",
              "shears", "flint_and_steel", "brush", "torch", "lantern", "stonecutter", "grindstone", "anvil"},
    "seeds": {"wheat_seeds", "beetroot_seeds", "melon_seeds", "pumpkin_seeds", "potato", "carrot", "bone_meal",
              "flower_pot", "composter", "oak_sapling", "birch_sapling", "spruce_sapling", "cherry_sapling"},
    "herbs": {"sweet_berries", "glow_berries", "brown_mushroom", "red_mushroom", "fern", "glistering_melon_slice",
              "cocoa_beans"},
    "mulch": {"coarse_dirt", "rooted_dirt", "podzol", "dirt", "composter", "bone_meal", "moss_block", "mud"},
    "game": {"cooked_rabbit", "rabbit", "cooked_chicken", "chicken", "cooked_mutton", "mutton", "cooked_beef",
             "cooked_porkchop", "leather", "rabbit_hide", "rabbit_foot", "feather", "lead", "rabbit_stew"},
    "galley": COOKED,
    "field_kitchen": COOKED,
    "provisions": COOKED | {"cookie", "dried_kelp"},
    "storm_gear": {"spyglass", "lantern", "compass", "clock", "leather_boots", "leather_chestplate", "copper_ingot"},
    "fish": {"cod", "salmon", "cooked_cod", "cooked_salmon", "dried_kelp", "kelp", "fishing_rod"},
    "exotic_fish": {"tropical_fish", "pufferfish", "glow_ink_sac", "ink_sac", "nautilus_shell", "prismarine_shard",
                    "prismarine_crystals"},
    "produce": {"apple", "melon_slice", "beetroot", "carrot", "potato", "wheat", "sweet_berries", "pumpkin", "bread"},
    "sweets": {"cookie", "pumpkin_pie", "honey_bottle", "sugar", "sweet_berries"},
    "reeds": {"sugar_cane", "bamboo", "paper", "scaffolding", "kelp", "dried_kelp"},
    "balls": set(),        # a ball is power; an ungated stall may not sell one, so nothing fits this theme ungated
    "archive": {"paper", "book", "writable_book", "map", "compass", "ink_sac", "feather", "lectern", "bookshelf"},
    "smithy": {"anvil", "grindstone", "chain", "iron_boots", "iron_helmet", "iron_chestplate", "iron_leggings", "coal",
               "charcoal", "flint_and_steel", "iron_ingot", "smithing_table", "blast_furnace", "shield"},
    "core_samples": {"tuff", "smooth_basalt", "basalt", "calcite", "brush", "raw_copper", "raw_gold", "deepslate",
                     "blackstone", "dripstone_block", "obsidian"},
    "packs": {"chest", "barrel", "leather", "string", "bundle"},
    "rods": {"fishing_rod", "string", "oak_boat", "birch_boat", "spruce_boat", "jungle_boat"},
    "tea": {"honey_bottle", "cookie", "sugar", "milk_bucket"},
    "cold-weather kit": {"spyglass", "compass", "leather_boots", "leather_helmet", "leather_chestplate",
                         "leather_leggings", "cooked_salmon", "cooked_cod", "campfire"},
    "light": {"lantern", "torch", "soul_lantern"},
    "food": COOKED,
}
# lines judged by hand (the vocabulary does not carry them): (stall id, item) -> why it was accepted
HAND_JUDGED = {
    ("stoneford_masons_yard", "minecraft:stone_bricks"): "the masons' yard sells its dressed stone with the tools",
    ("fossick_pit_tools", "minecraft:minecart"): "a pit's tool: the ore cart",
    ("greenhollow_seed_cart", "minecraft:shears"): "a flower cart's cutting shears",
    ("highwire_relay_spares", "minecraft:redstone"): "the relay's radio parts (the contract's own words)",
    ("sunset_net_loft", "minecraft:lead"): "a mooring line in a net loft",
    ("pacifidlog_fishers_row", "minecraft:jungle_boat"): "a fishing trader on a raft town sells the boat",
    ("pacifidlog_fishers_row", "minecraft:turtle_helmet"): "a diver's shell for the sea town's fishers",
    ("viltri_strange_catch", "minecraft:salmon"): "an uncommon catch on a lake",
    ("northlight_field_kit", "minecraft:cooked_salmon"): "trail food is kit",
    ("holdfast_garrison_provisions", "minecraft:torch"): "rations and light for Victory Road",
    ("holdfast_pack_store", "minecraft:red_bed"): "a bedroll for the pack",
    ("tilpey_market_kitchen", "minecraft:bread"): "produce baked",
    ("cinderlee_field_kitchen", "minecraft:baked_potato"): "field kitchen food (in COOKED already; listed for clarity)",
}

# KNOWN defects: the audit's finding list must equal this set exactly (a new one fails, a fixed one fails until it is
# removed here). Each: (check, key) -> why it is recorded rather than fixed.
KNOWN = {
    ("theme", "stoneford_bakehouse:minecraft:bread"): "bakery goods on the contract's `game` stall ('small game')",
    ("theme", "stoneford_bakehouse:minecraft:baked_potato"): "as above",
    ("theme", "stoneford_bakehouse:minecraft:pumpkin_pie"): "as above",
    ("theme", "viltri_boatwright:minecraft:oak_boat"): "a boatwright on the contract's `galley` ('the chef's galley')",
    ("theme", "viltri_boatwright:minecraft:fishing_rod"): "as above",
    ("theme", "viltri_boatwright:minecraft:lead"): "as above",
    ("theme", "fenhide_apothecary:minecraft:honey_bottle"): "an apothecary on the contract's `reeds`",
    ("theme", "fenhide_apothecary:minecraft:milk_bucket"): "as above",
    ("theme", "fenhide_apothecary:minecraft:golden_carrot"): "as above",
    ("theme", "fenhide_ball_bench:minecraft:copper_ingot"): "a `balls` stall that sells no ball (by its own design)",
    ("theme", "fenhide_ball_bench:minecraft:spyglass"): "as above",
    ("theme", "tilpey_market_kitchen:minecraft:cooked_beef"): "a cooked meal on the contract's `produce`",
    ("theme", "tilpey_market_kitchen:minecraft:pumpkin_pie"): "as above",
    ("theme", "cinderlee_rim_provisions:minecraft:cooked_mutton"): "a meal on the contract's `smithy`",
    ("theme", "holdfast_garrison_provisions:minecraft:shield"): "a shield on the contract's `provisions` ('rations')",
    ("items", "greenhollow_seed_cart:minecraft:bone_meal:spawn"): "bone meal on grass grows flowers (spawn blocks); the "
                                                                   "builder left this line knowingly (stalls_basis "
                                                                   "left_out) and kept it off the new mulch stalls",
    ("light", "gym1_town:street"): "(1737, 3640), the square's south-west corner where approach_sw enters: 15 from "
                                   "the nearest light (plan lamp 1736,138,3627 and a stall lantern), block light 0. "
                                   "The generator leaves street cells to the street lamps; town_plan's spacing misses it",
    ("power", "steepside:cobblecuisine:sweet_malasada"): "ungated friendship food on Steepside's counter (strand power)",
    ("power", "steepside:cobblecuisine:sweet_pokepuff"): "as above",
    ("power", "steepside:cobblecuisine:mint_pokepuff"): "as above",
    ("power", "steepside:cobblemon:thunder_stone"): "2026-10-05 (obtainability sweep, the owner's 'evolution stones actually purchasable'): the ten stones ungated at Steepside, as docs/mechanics/PROGRESSION_LADDER.md 5.4 designs them and tools/markets_audit.py (independent) requires; this rule and that design disagree. OWNER: gate or not (docs/OVERNIGHT_REVIEW_2026-10-06.md N39)",
    ("power", "steepside:cobblemon:water_stone"): "as thunder_stone",
    ("power", "steepside:cobblemon:fire_stone"): "as thunder_stone",
    ("power", "steepside:cobblemon:leaf_stone"): "as thunder_stone",
    ("power", "steepside:cobblemon:moon_stone"): "as thunder_stone",
    ("power", "steepside:cobblemon:sun_stone"): "as thunder_stone",
    ("power", "steepside:cobblemon:shiny_stone"): "as thunder_stone",
    ("power", "steepside:cobblemon:dusk_stone"): "as thunder_stone",
    ("power", "steepside:cobblemon:dawn_stone"): "as thunder_stone",
    ("power", "steepside:cobblemon:ice_stone"): "as thunder_stone",
    ("power", "steepside:cobblecuisine:citrus_pokepuff"): "as above",
    ("power", "steepside:cobblecuisine:mocha_pokepuff"): "as above",
    ("power", "pacifidlog:cobblemon:dive_ball"): "ungated balls on Pacifidlog's counter (travel as the gate, "
                                                 "PROGRESSION_LADDER 5.4): the brief's rule says badge-gated",
    ("power", "pacifidlog:cobblemon:net_ball"): "as above",
    ("power", "pacifidlog:cobblemon:lure_ball"): "as above",
    ("power", "redbrow:cobblemon:soft_sand"): "an ungated held battle item at Redbrow",
    ("power", "redbrow:cobblemon:heavy_ball"): "an ungated ball at Redbrow",
    ("spend", "deep_city"): "the Deep's city: its two stalls are unsited (markets.json no_counter: story-gated)",
    ("square", "sea_town"): "data/towns.json places Pacifidlog at x7020-7280 z6704-7238 (centre 7210, 6960); the "
                            "settlement, data/sea_town.json and the square are at (5160, 7380): towns.json is stale",
    # 2026-10-05, the hamlets' and the summit town's squares (the squares' builder, recorded, not fixed): the reach rule
    # walks from a Centre AND a Mart, and these places have no Mart (or neither). Their reach is NOT VERIFIED here: the
    # builder walks from the Centre and from data/plaza_centres.json `walk_from` (the Displaced City's summit stair, the
    # Dig's finds shed), which this audit does not read. Whether the rule should walk from a declared arrival instead is
    # the audit owner's question, not a slack to take here
    ("reach", "gorge_hamlet:pokemart"): "Bridgekeep is a hamlet with a Centre and no Mart: Mart reach unanswerable",
    ("reach", "tableland_stop:pokemart"): "Redbrow, a rest stop with a Centre and no Mart: as above",
    ("reach", "rift_rim_stop:pokemart"): "Rimwatch, a rangers' post with a Centre and no Mart: as above",
    ("reach", "merian_hut:pokemart"): "Merian Hut, a rest stop with a Centre and no Mart: as above",
    ("reach", "rift_dig_camp:pokecenter"): "the West Spur Dig has no Centre and no Mart: its square's reach is unverified "
                                          "by this audit (the builder walks from the finds shed's door)",
    ("reach", "rift_dig_camp:pokemart"): "as above",
    ("square", "rift_rim_stop"): "data/towns.json places Rimwatch at x3790-3838 z3767-3815 (centre 3814, 3791); the "
                                 "settlement's plan, its Centre (3729, 3945) and the square (3746-3772, 3948-3956) are "
                                 "170 blocks south-south-west of that centre: towns.json is stale, as for sea_town",
}



def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def name_of(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def rect_cells(r, m=0):
    return {(x, z) for x in range(r[0] - m, r[2] + m + 1) for z in range(r[1] - m, r[3] + m + 1)}


def in_rect(r, x, z, m=0):
    return r[0] - m <= x <= r[2] + m and r[1] - m <= z <= r[3] + m


# ------------------------------------------------------------------------------------------- the emitted functions
COORD = r"(-?\d+)"


def voxelise(lines):
    """({(x, y, z): state}, problems) from a function's commands applied in order. `fill ... air replace
    #minecraft:replaceable` sets air where the model holds nothing or air (what it would replace); a plain fill and a
    setblock overwrite."""
    model, problems = {}, []
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or s.startswith("#") or s.startswith("forceload "):
            continue
        # a state may carry block-entity NBT with spaces ({front_text:{messages:[...]}}): the mode, if any, is the
        # word after the state's last closing brace or bracket
        m = re.fullmatch(r"setblock %s %s %s (minecraft:[a-z0-9_]+(?:\[[^\]]*\])?(?:\{.*\})?)(?: (replace|keep|destroy))?"
                         % (COORD, COORD, COORD), s)
        if m:
            x, y, z = (int(m.group(k)) for k in (1, 2, 3))
            if m.group(5) == "keep" and (x, y, z) in model and name_of(model[(x, y, z)]) != "minecraft:air":
                continue
            model[(x, y, z)] = m.group(4)
            continue
        m = re.fullmatch(r"fill %s %s %s %s %s %s (\S+)(?: (replace)(?: (\S+))?| (keep|hollow|outline|destroy))?"
                         % ((COORD,) * 6), s)
        if m:
            a = [int(m.group(k)) for k in range(1, 7)]
            state, filt = m.group(7), m.group(9)
            for x in range(min(a[0], a[3]), max(a[0], a[3]) + 1):
                for y in range(min(a[1], a[4]), max(a[1], a[4]) + 1):
                    for z in range(min(a[2], a[5]), max(a[2], a[5]) + 1):
                        cur = model.get((x, y, z))
                        if filt is None or (filt == "#minecraft:replaceable" and
                                            (cur is None or name_of(cur) == "minecraft:air")):
                            model[(x, y, z)] = state
                        elif filt not in (None, "#minecraft:replaceable"):
                            problems.append("line %d: a fill filter this model does not know: %s" % (i, s[:120]))
            continue
        problems.append("line %d: a command this model does not know: %s" % (i, s[:120]))
    return model, problems


def solid(state):
    return state is not None and not PASSABLE.fullmatch(name_of(state))


# ------------------------------------------------------------------------------------------------- the town's plan
class TownGeo:
    """Everything that is not the square, from the plan and the placements (never from plaza_centre)."""

    def __init__(self, settlement, sq, doc, ground, sea):
        import nbt
        self.settlement = settlement
        self.rect = tuple(sq["rect"])
        self.y = int(sq["y"])
        self.ground = ground
        self.sea = sea
        s = doc["settlements"][settlement]
        self.planned = bool(s.get("plan"))
        self.plan, self.plan_missing = {}, False
        if self.planned:
            p = PLAN_DIR / ("%s_plan.json" % settlement)
            if p.is_file():
                self.plan = load(p)
            else:
                self.plan_missing = True
        self.street = {}
        for st in (self.plan.get("streets") or {}).values():
            for z, y, xa, xb in st.get("cells") or []:
                for x in range(xa, xb + 1):
                    self.street[(x, z)] = int(y)
        if not self.planned:
            for r in s.get("roads") or []:
                pts = r.get("polyline")
                if not pts:
                    continue
                h = r["width"] / 2.0
                for (ax, az), (bx, bz) in zip(pts, pts[1:]):
                    for x in range(int(min(ax, bx) - h - 1), int(max(ax, bx) + h + 2)):
                        for z in range(int(min(az, bz) - h - 1), int(max(az, bz) + h + 2)):
                            if seg_dist(x, z, ax, az, bx, bz) <= h:
                                self.street[(x, z)] = None
        self.lots = [(l["id"], tuple(l["rect"])) for l in self.plan.get("lots") or []]
        self.anchors = [(a["id"], tuple(a["rect"]), a.get("role")) for a in self.plan.get("anchors") or []]
        self.lamps = []
        lamp_e = EMISSION.get(self.plan.get("lamp_block") or "", 15)
        for L in self.plan.get("lamps") or []:
            self.lamps.append((L["at"][0], L["at"][1] - 1, L["at"][2], lamp_e))
        self.footprints = {}            # id -> (rect, facing, role)
        self.sign = None
        for q in doc["placements"]:
            if q.get("settlement") != settlement:
                continue
            if q.get("kind") == "earthwork":
                for c in q.get("commands") or []:
                    m = re.match(r"\s*setblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(minecraft:[a-z_]+)", c)
                    if m and m.group(4) in EMISSION:
                        self.lamps.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), EMISSION[m.group(4)]))
                continue
            if not q.get("file") or not q.get("position"):
                continue
            path = ROOT / q["file"]
            if not path.is_file():
                raise SystemExit("%s: template %s is missing (hydrate kits: python tools/local_inputs.py hydrate)"
                                 % (q["id"], q["file"]))
            sx, _sy, sz = nbt.load(path)[1]["size"]
            w, d = (sz, sx) if q.get("rotation") in ("clockwise_90", "counterclockwise_90") else (sx, sz)
            px, pz = q["position"]["x"], q["position"]["z"]
            rect = (px, pz, px + w - 1, pz + d - 1)
            role = ("pokecenter" if "pokecenter" in q["id"] else "pokemart" if "pokemart" in q["id"] else q.get("kind"))
            if q.get("kind") == "town_centre":
                self.sign = (q["id"], rect)
            else:
                self.footprints[q["id"]] = (rect, q.get("facing"), role)
        for aid, r, role in self.anchors:          # a donor placed by resource id (the gyms): its anchor is its wall
            if role == "gym" and not any(v[2] == "gym" for v in self.footprints.values()):
                self.footprints[aid] = (r, None, "gym")

    def floor(self, x, z):
        if self.planned and in_rect(self.rect, x, z):
            return self.y
        if (x, z) in self.street and self.street[(x, z)] is not None:
            return self.street[(x, z)]
        return self.ground(x, z)


def seg_dist(px, pz, ax, az, bx, bz):
    vx, vz = bx - ax, bz - az
    L = vx * vx + vz * vz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * vx + (pz - az) * vz) / L))
    return math.hypot(px - (ax + t * vx), pz - (az + t * vz))


# ------------------------------------------------------------------------------------------------------ the checks
def columns(model):
    """{(x, z): [(y, state)]} of every non-air block the function leaves."""
    out = {}
    for (x, y, z), s in model.items():
        if name_of(s) != "minecraft:air":
            out.setdefault((x, z), []).append((y, s))
    return out


def town_checks(settlement, rec, geo, model, towns_fp, spawn, subs):
    P = []        # (check, key, message)
    sq = rec["square"]
    r = geo.rect
    fp = towns_fp.get(settlement)
    if fp is None or not (fp[0] <= r[0] and fp[1] <= r[1] and r[2] <= fp[2] and r[3] <= fp[3]):
        P.append(("square", settlement, "the square %s is not inside data/towns.json's footprint %s" % (list(r), fp)))
    if geo.plan_missing:
        P.append(("plan", settlement, "no derived/towns/%s_plan.json: run python tools/town_plan.py %s"
                  % (settlement, settlement)))
    if geo.plan:
        pz = geo.plan.get("plaza") or {}
        if list(pz.get("rect") or []) != list(r) or pz.get("y") != geo.y:
            P.append(("square", settlement + ":plaza", "the square %s y%d is not the plan's plaza %s y%s"
                      % (list(r), geo.y, pz.get("rect"), pz.get("y"))))
    cols = columns(model)
    standing = set()
    for (x, z), ys in cols.items():
        top = max(y for y, _s in ys)
        floor = geo.floor(x, z)
        if any(y > floor and solid(s) for y, s in ys if y <= floor + 2):
            standing.add((x, z))
        if top > geo.y and not in_rect(r, x, z):
            P.append(("ground", "%s:%d,%d:outside" % (settlement, x, z),
                      "%s: a block stands at (%d, %d), outside the square %s" % (settlement, x, z, list(r))))
        if (x, z) in geo.street:
            P.append(("ground", "%s:%d,%d:street" % (settlement, x, z),
                      "%s: a block is written on street cell (%d, %d)" % (settlement, x, z)))
        for lid, lr in geo.lots:
            if in_rect(lr, x, z):
                P.append(("ground", "%s:%d,%d:lot" % (settlement, x, z), "%s: a block on lot %s at (%d, %d)"
                          % (settlement, lid, x, z)))
        for aid, ar, _role in geo.anchors:
            if in_rect(ar, x, z):
                P.append(("ground", "%s:%d,%d:anchor" % (settlement, x, z), "%s: a block on anchor %s at (%d, %d)"
                          % (settlement, aid, x, z)))
        for bid, (br, _f, _role) in geo.footprints.items():
            if in_rect(br, x, z):
                P.append(("ground", "%s:%d,%d:building" % (settlement, x, z),
                          "%s: a block inside building %s's footprint %s at (%d, %d)" % (settlement, bid, list(br), x, z)))
        if geo.sign and in_rect(geo.sign[1], x, z, 2):
            P.append(("ground", "%s:%d,%d:sign" % (settlement, x, z),
                      "%s: a block within 2 of the crossroads sign %s at (%d, %d)" % (settlement, list(geo.sign[1]), x, z)))
        for y, s in ys:
            n = name_of(s)
            if n in spawn:
                P.append(("spawn", "%s:%s" % (settlement, n), "%s: spawn-condition block %s at (%d, %d, %d)"
                          % (settlement, n, x, y, z)))
            if "water" in n or "waterlogged=true" in s:
                P.append(("spawn", "%s:water" % settlement, "%s: water at (%d, %d, %d): %s" % (settlement, x, y, z, s)))
            if n in subs:
                P.append(("spawn", "%s:%s:policy" % (settlement, n), "%s: %s, which data/spawn_block_policy.json "
                          "substitutes with %s" % (settlement, n, subs[n])))
    return P, standing


def light_checks(settlement, geo, model, standing):
    lights = [(x, y, z, EMISSION[name_of(s)]) for (x, y, z), s in model.items()
              if name_of(s) in EMISSION and "lit=false" not in s]
    lights += geo.lamps
    dark, street_dark = [], []
    for x, z in rect_cells(geo.rect):
        if (x, z) in standing:
            continue
        y = geo.floor(x, z) + 1
        lvl = max([e - (abs(lx - x) + abs(ly - y) + abs(lz - z)) for lx, ly, lz, e in lights] or [0])
        if lvl < 1:
            (street_dark if (x, z) in geo.street else dark).append((x, z))
    P = []
    if dark:
        P.append(("light", settlement, "%s: %d square cell(s) at block light 0, e.g. %s" % (settlement, len(dark), dark[:4])))
    if street_dark:
        P.append(("light", settlement + ":street", "%s: %d street cell(s) over the square at block light 0, e.g. %s"
                  % (settlement, len(street_dark), street_dark[:4])))
    return P, len(lights)


def walk(geo, starts, walls, box):
    seen = {}
    q = deque()
    for s in starts:
        if s not in walls and geo.floor(*s) >= geo.sea:
            seen[s] = 0
            q.append(s)
    while q:
        c = q.popleft()
        y = geo.floor(*c)
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dz)
            if n in seen or n in walls or not in_rect(box, *n):
                continue
            fy = geo.floor(*n)
            if fy < geo.sea or abs(fy - y) > 1:
                continue
            seen[n] = seen[c] + 1
            q.append(n)
    return seen


def door_starts(rect, facing):
    x0, z0, x1, z1 = rect
    if facing in ("north", "south"):
        z = z0 - 1 if facing == "north" else z1 + 1
        q = (x1 - x0) // 4
        return [(x, z) for x in range(x0 + q, x1 - q + 1)]
    x = x0 - 1 if facing == "west" else x1 + 1
    q = (z1 - z0) // 4
    return [(x, z) for z in range(z0 + q, z1 - q + 1)]


def reach_checks(settlement, rec, geo, standing):
    P, info = [], {}
    walls = set(standing)
    for _bid, (br, _f, _r) in geo.footprints.items():
        walls |= rect_cells(br)
    r = geo.rect
    box = (r[0] - 100, r[1] - 100, r[2] + 100, r[3] + 100)
    square = rect_cells(r)
    for role in ("pokecenter", "pokemart"):
        found = [(bid, v) for bid, v in geo.footprints.items() if v[2] == role]
        if not found:
            P.append(("reach", "%s:%s" % (settlement, role), "%s: no %s placement with a template" % (settlement, role)))
            continue
        bid, (br, facing, _r) = found[0]
        if facing not in STEP:
            P.append(("reach", "%s:%s" % (settlement, role), "%s: %s has no facing" % (settlement, bid)))
            continue
        seen = walk(geo, door_starts(br, facing), walls - set(door_starts(br, facing)), box)
        on = [seen[c] for c in square if c in seen]
        if not on:
            P.append(("reach", "%s:%s" % (settlement, role), "%s: the square cannot be reached on foot from %s's %s side"
                      % (settlement, bid, facing)))
            continue
        info[role] = min(on)
        for st in rec["stalls"]:
            cust = customer_cell(st)
            if cust not in seen:
                P.append(("reach", "%s:%s:%s" % (settlement, st["id"], role), "%s: %s's customer cell %s is not reached "
                          "on foot from %s" % (settlement, st["id"], cust, bid)))
    return P, info


def yaw_vec(yaw):
    a = math.radians(yaw)
    return -math.sin(a), math.cos(a)


def customer_cell(st):
    """The tent rule (the owner, 2026-10-04, "a tent with wares", Slateport): the table at `at`, the keeper one step
    out on the customers' side, the customer one step further: (x, z) of at + 2 step(facing)."""
    dx, dz = STEP[st["facing"]]
    return st["at"][0] + 2 * dx, st["at"][2] + 2 * dz


def stall_checks(settlement, rec, geo, model):
    """The tent, read from the voxel model against MY rule: a solid table at `at`; the keeper at at + step(facing),
    in the open front, feet and head air (written or cleared), on a floor, turned to the customers (the yaw within
    22.5 degrees of step(facing)); the customer at at + 2 step(facing), feet and head not solid, on the keeper's own
    floor, so nothing stands between them."""
    P = []
    for st in rec["stalls"]:
        sid = st["id"]
        ax, ay, az = st["at"]
        if not solid(model.get((ax, ay, az))):
            P.append(("stall", sid + ":counter", "%s: no table block at its `at` %s in the function (found %s)"
                      % (sid, st["at"], model.get((ax, ay, az)))))
        dx, dz = STEP[st["facing"]]
        kx, ky, kz, yaw = st["keeper_at"]
        if (kx, ky, kz) != (ax + dx, ay, az + dz):
            P.append(("stall", sid + ":front", "%s: keeper_at %s is not in the tent's open front, at the table's %s "
                      "(expected %s)" % (sid, st["keeper_at"][:3], st["facing"], [ax + dx, ay, az + dz])))
        for y in (ky, ky + 1):
            s = model.get((kx, y, kz))
            if s is None or name_of(s) != "minecraft:air":
                P.append(("stall", sid + ":air%d" % (y - ky), "%s: the keeper's %s (%d, %d, %d) is %s in the function, "
                          "not air" % (sid, "feet" if y == ky else "head", kx, y, kz, s or "never written or cleared")))
        under = model.get((kx, ky - 1, kz))
        if under is not None:
            ok = solid(under)
        else:
            ok = geo.floor(kx, kz) == ky - 1
        if not ok:
            P.append(("stall", sid + ":floor", "%s: no floor under the keeper at (%d, %d, %d): function %s, plan/ground %d"
                      % (sid, kx, ky - 1, kz, under, geo.floor(kx, kz))))
        vx, vz = yaw_vec(yaw)
        if vx * dx + vz * dz < math.cos(math.radians(22.5)):
            P.append(("stall", sid + ":yaw", "%s: yaw %s does not face its customers (to the %s)"
                      % (sid, yaw, st["facing"])))
        # the customer, face to face with the keeper: an open cell on the same floor (a carpet is walked over)
        cx, cz = kx + dx, kz + dz
        for y in (ky, ky + 1):
            s = model.get((cx, y, cz))
            if solid(s):
                P.append(("stall", sid + ":customer%d" % (y - ky), "%s: %s stands at the customer's %s (%d, %d, %d), "
                          "between player and keeper" % (sid, s, "feet" if y == ky else "head", cx, y, cz)))
        cu = model.get((cx, ky - 1, cz))
        cfloor_ok = solid(cu) if cu is not None else geo.floor(cx, cz) == ky - 1
        if not cfloor_ok:
            P.append(("stall", sid + ":customer_floor", "%s: the customer's cell (%d, %d) is not on the keeper's floor "
                      "y%d: function %s, plan/ground %d" % (sid, cx, cz, ky - 1, cu, geo.floor(cx, cz))))
    return P


# ------------------------------------------------------------------------------------------------- the traders
def contract_stalls(plazas):
    return {s["id"]: dict(s, _town=t) for t, rec in plazas["towns"].items() for s in rec["stalls"]}


def r17m_list():
    """([(npc class, (x, y, z), yaw)], [function ids R17M runs], where they came from)."""
    why = "no R17M step"
    try:
        import reapply
        for sid, _what, acts in reapply.steps():
            if sid == "R17M":
                return ([(a[1][2], tuple(a[1][1]), a[1][3]) for a in acts if a[0] == "npc"],
                        [a[1] for a in acts if a[0] == "fn"], "tools/reapply.steps() R17M")
    except (SystemExit, Exception) as e:         # reapply.steps() needs a prepared build/ (the Rift's index)
        why = str(e)[:120]
    import markets
    doc = markets.load()
    acts = markets.npc_placements(doc) + markets.stall_placements(doc)
    fns = ["cobblers:markets/load"]
    if any(s.get("status") == "sited" for s in doc.get("stalls") or []):
        fns.append(markets.MERCHANTS_FN)
    return ([(a[2], tuple(a[1]), a[3]) for a in acts], fns,
            "markets.npc_placements + markets.stall_placements + markets/load + MERCHANTS_FN, as R17M composes them "
            "(reapply.steps() unavailable: %s)" % why)


# ------------------------------------------------------------------- the merchants, read from the emitted functions
MERCHANT_KIND = "cobbledollars:cobble_merchant"      # the owner, 2026-10-04: "the cobbleverse ones that have nice ui"
MARKETS_PACK = ROOT / "build" / "datapacks" / "cobblers_markets"
_TOKEN = re.compile(r"[A-Za-z0-9_.+\-]+")


def snbt(text):
    """My own SNBT reader (not tools/traders.py's writer, not markets.shop_offers): compounds, lists (typed arrays
    too), quoted strings with backslash escapes, numbers with their b/s/l/f/d suffix (bytes and ints to int, the rest
    to float), anything else a bare string. Raises ValueError on text it cannot read."""
    try:
        v, i = _snbt(text, 0)
    except IndexError:
        raise ValueError("SNBT ends early")
    if text[i:].strip():
        raise ValueError("SNBT has trailing text at %d" % i)
    return v


def _skip(s, i):
    while i < len(s) and s[i] in " \t":
        i += 1
    return i


def _quoted(s, i):
    q, i, out = s[i], i + 1, []
    while s[i] != q:
        if s[i] == "\\":
            i += 1
        out.append(s[i])
        i += 1
    return "".join(out), i + 1


def _snbt(s, i):
    i = _skip(s, i)
    c = s[i]
    if c == "{":
        out, i = {}, _skip(s, i + 1)
        if s[i] == "}":
            return out, i + 1
        while True:
            i = _skip(s, i)
            if s[i] in "\"'":
                k, i = _quoted(s, i)
            else:
                m = _TOKEN.match(s, i)
                if not m:
                    raise ValueError("no key at %d" % i)
                k, i = m.group(0), m.end()
            i = _skip(s, i)
            if s[i] != ":":
                raise ValueError("no ':' after %r" % k)
            out[k], i = _snbt(s, i + 1)
            i = _skip(s, i)
            if s[i] == ",":
                i += 1
            elif s[i] == "}":
                return out, i + 1
            else:
                raise ValueError("unexpected %r at %d" % (s[i], i))
    if c == "[":
        i += 1
        m = re.compile(r"[BIL];").match(s, i)
        if m:
            i = m.end()
        out, i = [], _skip(s, i)
        if s[i] == "]":
            return out, i + 1
        while True:
            v, i = _snbt(s, i)
            out.append(v)
            i = _skip(s, i)
            if s[i] == ",":
                i += 1
            elif s[i] == "]":
                return out, i + 1
            else:
                raise ValueError("unexpected %r at %d" % (s[i], i))
    if c in "\"'":
        return _quoted(s, i)
    m = _TOKEN.match(s, i)
    if not m:
        raise ValueError("unexpected %r at %d" % (c, i))
    tok = m.group(0)
    if re.fullmatch(r"-?\d+[bBsSlL]?", tok):
        return int(tok.rstrip("bBsSlL")), m.end()
    if re.fullmatch(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?[fFdD]?", tok):
        return float(tok.rstrip("fFdD")), m.end()
    if tok in ("true", "false"):
        return int(tok == "true"), m.end()
    return tok, m.end()


def pack_files(pack=None):
    """{relative path: lines} of a datapack folder's functions, or None when it holds none."""
    pack = Path(pack or MARKETS_PACK)
    root = pack / "data"
    if not root.is_dir():
        return None
    return {p.relative_to(pack).as_posix(): p.read_text(encoding="utf-8").splitlines()
            for p in root.rglob("*.mcfunction")}


def fn_path(fid):
    ns, path = fid.split(":", 1)
    return "data/%s/function/%s.mcfunction" % (ns, path)


SUMMON = re.compile(r"(?:^|\brun )summon (\S+) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)(?: (.+))?$")
CALLS = re.compile(r"(?:^|\brun |^schedule )function ([a-z0-9_.\-]+:[a-z0-9_./\-]+)")


def r17m_merchants(files, fns):
    """(summons, kills, problems) from the functions R17M runs, followed through `function`, `schedule function` and
    `execute ... run function` inside the pack. A summon: {kind, pos (x, y, z floats), block, nbt, file}; a kill of
    type=cobblemon:npc: (file, centre (x, y, z), radius)."""
    summons, kills, P, seen = [], [], [], set()
    todo = list(fns)
    while todo:
        fid = todo.pop(0)
        if fid in seen:
            continue
        seen.add(fid)
        rel = fn_path(fid)
        if rel not in files:
            P.append(("staff", "fn:" + fid, "R17M runs %s, which the markets pack does not hold (%s)" % (fid, rel)))
            continue
        for n, raw in enumerate(files[rel], 1):
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            todo += [m.group(1) for m in CALLS.finditer(s)]
            m = SUMMON.search(s)
            if m:
                x, y, z = (float(m.group(k)) for k in (2, 3, 4))
                try:
                    data = snbt(m.group(5)) if m.group(5) else {}
                except ValueError as e:
                    P.append(("merchant", "%s:%d:snbt" % (rel, n), "%s line %d: unreadable SNBT (%s)" % (rel, n, e)))
                    data = {}
                summons.append({"kind": m.group(1), "pos": (x, y, z), "block": (math.floor(x), math.floor(y),
                                math.floor(z)), "nbt": data, "file": rel})
            for sel in re.findall(r"kill @e\[([^\]]*)\]", s):
                args = dict(a.split("=", 1) for a in sel.split(",") if "=" in a)
                if args.get("type") == "cobblemon:npc" and all(k in args for k in ("x", "y", "z", "distance")):
                    r = re.fullmatch(r"\.\.(\d+(?:\.\d+)?)", args["distance"])
                    if r:
                        kills.append((rel, (float(args["x"]), float(args["y"]), float(args["z"])), float(r.group(1))))
    return summons, kills, P


def merchant_stall(m, stall_ids, prefix):
    """The stall id a summon's tags name (prefix_<id>), or None."""
    tags = m["nbt"].get("Tags") if isinstance(m["nbt"].get("Tags"), list) else []
    named = [t[len(prefix) + 1:] for t in tags if isinstance(t, str) and t.startswith(prefix + "_")
             and t[len(prefix) + 1:] in stall_ids]
    return named[0] if len(named) == 1 else None


def same_yaw(a, b):
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0) < 0.01


def staff_checks(plazas, markets_doc, npcs, summons=(), kills=()):
    """Every contract stall staffed exactly once at its keeper_at with its yaw, by a counter's dialogue clerk (an R17M
    `npc` action) or a stall's merchant (a summon in the functions R17M runs, known by its tag); no stall keeper is a
    Cobblemon dialogue NPC any more; every keeper stands at a seat or in a declared fallback town; each merchant
    removes the dialogue keeper it replaces, and that removal reaches no counter clerk."""
    P = []
    cs = contract_stalls(plazas)
    prefix = (markets_doc.get("stall_merchant") or {}).get("tag") or "cobblers_stall"
    stalls = {s["id"]: s for s in markets_doc.get("stalls") or []}
    recs = {}
    for c in markets_doc["counters"]:
        recs["cobblers:npc_market_%s" % c["id"]] = c
    for s in stalls.values():
        recs["cobblers:npc_stall_%s" % s["id"]] = s
    keepers = []              # (label, block, yaw, markets record or None, kind)
    for cls, pos, yaw in npcs:
        if re.fullmatch(r"cobblers:npc_stall_.+", cls):
            P.append(("staff", cls + ":dialogue", "R17M still places %s, a Cobblemon dialogue stall keeper (every stall "
                      "keeper is a CobbleDollars merchant since 2026-10-04)" % cls))
        keepers.append((cls, tuple(pos), yaw, recs.get(cls), "npc"))
    per_stall = {}
    for m in summons:
        if m["kind"] == "cobblemon:npc":
            P.append(("staff", "%s:%d,%d,%d:dialogue" % ((m["file"],) + m["block"]), "%s summons a cobblemon:npc at "
                      "%s" % (m["file"], list(m["block"]))))
            continue
        sid = merchant_stall(m, stalls, prefix)
        label = "merchant %s" % (sid or "%s@%s" % (m["kind"], list(m["block"])))
        rot = m["nbt"].get("Rotation")
        yaw = rot[0] if isinstance(rot, list) and rot and isinstance(rot[0], (int, float)) else None
        keepers.append((label, m["block"], yaw, stalls.get(sid), "merchant"))
        if sid is None:
            P.append(("staff", label + ":tag", "%s in %s carries no tag %s_<stall id> naming one stall: %s"
                      % (label, m["file"], prefix, m["nbt"].get("Tags"))))
            continue
        per_stall.setdefault(sid, []).append(m)
    for sid, s in sorted(stalls.items()):
        want = 1 if s.get("status") == "sited" else 0
        got = len(per_stall.get(sid, []))
        if got != want:
            P.append(("staff", sid + ":merchants", "stall %s (%s): %d merchant summon(s) carry its tag, not %d"
                      % (sid, s.get("status"), got, want)))
    by_pos = {}
    for k in keepers:
        by_pos.setdefault(k[1], []).append(k)
    for sid, st in sorted(cs.items()):
        k = tuple(st["keeper_at"][:3])
        here = by_pos.get(k, [])
        if len(here) != 1:
            P.append(("staff", sid, "%s: %d R17M keeper(s) at its keeper_at %s (%s)" % (sid, len(here), list(k),
                                                                                         [h[0] for h in here])))
        elif here[0][2] is None or not same_yaw(here[0][2], st["keeper_at"][3]):
            P.append(("staff", sid + ":yaw", "%s: its keeper's yaw %s is not the contract's %s"
                      % (sid, here[0][2], st["keeper_at"][3])))
        else:
            rec = here[0][3]
            if rec is not None and rec.get("sells") is not None and rec.get("sells") != st["sells"]:
                P.append(("staff", sid + ":sells", "%s: its keeper %s sells %r, the stall's theme is %r"
                          % (sid, rec["id"], rec.get("sells"), st["sells"])))
    seats = {tuple(s["keeper_at"][:3]) for s in cs.values()}
    for label, pos, _yaw, rec, kind in keepers:
        if rec is None:
            if kind == "npc":
                P.append(("staff", label, "R17M places %s, which no markets record describes" % label))
            continue
        if rec["town"] in PLACE_STANDS:
            fname, key = PLACE_STANDS[rec["town"]]
            feet = json.loads((ROOT / "data" / fname).read_text(encoding="utf-8"))[key]["feet"]
            if [int(v) for v in pos[:3]] != [int(v) for v in feet[:3]]:
                P.append(("staff", label + ":place", "%s (%s) stands at %s, not at %s's declared stand %s"
                          % (rec["id"], label, list(pos), fname, feet)))
            continue
        if pos not in seats and rec["town"] not in FALLBACK_TOWNS:
            P.append(("staff", label + ":seat", "%s (%s) stands at %s, no contract keeper_at, in %s, not a declared "
                      "fallback town" % (rec["id"], label, list(pos), rec["town"])))
    # the removal is MEANT to take a dialogue stall keeper; it must take no counter clerk
    clerks = [(cls, pos) for cls, pos, _y in npcs if not re.fullmatch(r"cobblers:npc_stall_.+", cls)]
    for sid, ms in sorted(per_stall.items()):
        bx, by, bz = ms[0]["block"]
        centre = (bx + 0.5, by, bz + 0.5)
        mine = [(c, r) for _f, c, r in kills if math.dist(c, centre) < 0.01]
        if not mine:
            P.append(("staff", sid + ":replaces", "stall %s: no `kill @e[type=cobblemon:npc,...]` centred on its "
                      "merchant at %s, so the dialogue keeper it replaces stays in the world" % (sid, list(centre))))
        for c, r in mine:
            for cls, (nx, ny, nz) in clerks:
                if math.dist(c, (nx + 0.5, ny, nz + 0.5)) <= r:
                    P.append(("staff", "%s:kills:%s" % (sid, cls), "stall %s: its removal (radius %s round %s) "
                              "reaches the counter clerk %s at %s" % (sid, r, list(c), cls, [nx, ny, nz])))
    return P


def merchant_checks(markets_doc, summons):
    """Each stall merchant as summoned: the CobbleDollars entity, centred on its block, NoAI and PersistenceRequired
    (a merchant with AI walks off its stall), named as its keeper; and its CobbleMerchantShop equal to its stall's
    lines: one category, the stall's `category`; one offer per line, Item count 1, Price a whole number that times the
    line's count is the line's price; no other offer. And no stall line gated (a merchant shows one list to everyone)."""
    P = []
    prefix = (markets_doc.get("stall_merchant") or {}).get("tag") or "cobblers_stall"
    stalls = {s["id"]: s for s in markets_doc.get("stalls") or []}
    for s in stalls.values():
        if s.get("status") != "sited":
            continue
        for it in s.get("stock") or []:
            if it.get("gate"):
                P.append(("shop", "%s:%s:gated" % (s["id"], it["item"]), "stall %s: %s is gated on %r, but its "
                          "merchant shows every line to every player" % (s["id"], it["item"], it["gate"])))
    for m in summons:
        sid = merchant_stall(m, stalls, prefix)
        if sid is None or m["kind"] == "cobblemon:npc":
            continue                                   # staff_checks names it
        s, d, w = stalls[sid], m["nbt"], "merchant " + sid
        if m["kind"] != MERCHANT_KIND:
            P.append(("merchant", sid + ":kind", "%s summons %s, not %s" % (w, m["kind"], MERCHANT_KIND)))
        x, y, z = m["pos"]
        if x - math.floor(x) != 0.5 or z - math.floor(z) != 0.5 or y != math.floor(y):
            P.append(("merchant", sid + ":centre", "%s at %s is not centred on its block, feet on a whole y" % (w, [x, y, z])))
        for flag in ("NoAI", "PersistenceRequired"):
            if d.get(flag) != 1:
                P.append(("merchant", "%s:%s" % (sid, flag), "%s: %s is %r, not 1b" % (w, flag, d.get(flag))))
        try:
            name = json.loads(d.get("CustomName") or "null")
            name = name.get("text") if isinstance(name, dict) else name
        except ValueError:
            name = d.get("CustomName")
        if name != (s.get("keeper") or {}).get("name"):
            P.append(("merchant", sid + ":name", "%s is named %r, its keeper %r" % (w, name, (s.get("keeper") or {}).get("name"))))
        shop = d.get("CobbleMerchantShop")
        if not isinstance(shop, list) or len(shop) != 1 or not isinstance(shop[0], dict):
            P.append(("shop", sid + ":categories", "%s: CobbleMerchantShop is not one category: %r" % (w, shop)))
            continue
        cat = shop[0].get("Category")
        if not s.get("category") or cat != s.get("category"):
            P.append(("shop", sid + ":category", "%s: category %r, the stall's %r" % (w, cat, s.get("category"))))
        offers = list(shop[0].get("Offers") or [])
        for it in s.get("stock") or []:
            hit = [o for o in offers if isinstance(o, dict) and isinstance(o.get("Item"), dict)
                   and o["Item"].get("id") == it["item"]]
            if not hit:
                P.append(("shop", "%s:%s:missing" % (sid, it["item"]), "%s: no offer for %s" % (w, it["item"])))
                continue
            o = hit[0]
            offers.remove(o)
            if o["Item"].get("count") != 1:
                P.append(("shop", "%s:%s:count" % (sid, it["item"]), "%s: %s offered %r at a time, not 1"
                          % (w, it["item"], o["Item"].get("count"))))
            p = o.get("Price")
            if not (isinstance(p, str) and p.isdigit()) or int(p) * int(it["count"]) != int(it["price"]):
                P.append(("shop", "%s:%s:price" % (sid, it["item"]), "%s: %s at %r each; the line is %s for $%s"
                          % (w, it["item"], p, it["count"], it["price"])))
        for o in offers:
            P.append(("shop", "%s:%s:extra" % (sid, ((o or {}).get("Item") or {}).get("id")), "%s: an offer no stall "
                      "line has: %r" % (w, o)))
    return P


def jar_index(vanilla, jar_dir):
    """({namespace: set(paths)}, notes)."""
    ids, notes = {}, []

    def read_lang(zf, name):
        try:
            lang = json.loads(zf.read(name).decode("utf-8", "replace"))
        except (KeyError, ValueError):
            return
        for key in lang:
            m = re.fullmatch(r"(?:item|block)\.([a-z0-9_.\-]+)\.([a-z0-9_/.\-]+)", key)
            if m:
                ids.setdefault(m.group(1), set()).add(m.group(2))

    def scan(zf, depth=0):
        for name in zf.namelist():
            if re.fullmatch(r"assets/[^/]+/lang/en_us\.json", name):
                read_lang(zf, name)
            elif depth == 0 and name.startswith("META-INF/jars/") and name.endswith(".jar"):
                import io
                try:
                    scan(zipfile.ZipFile(io.BytesIO(zf.read(name))), 1)
                except zipfile.BadZipFile:
                    pass

    if vanilla and Path(vanilla).is_file():
        with zipfile.ZipFile(vanilla) as zf:
            read_lang(zf, "assets/minecraft/lang/en_us.json")
        notes.append("minecraft ids from %s" % vanilla)
    else:
        notes.append("NOT CHECKED: minecraft ids (no vanilla jar at %s)" % vanilla)
    if jar_dir and Path(jar_dir).is_dir():
        jars = sorted(Path(jar_dir).glob("*.jar"))
        for j in jars:
            try:
                with zipfile.ZipFile(j) as zf:
                    scan(zf)
            except zipfile.BadZipFile:
                notes.append("unreadable jar %s" % j.name)
        notes.append("mod ids from %d jar(s) in %s" % (len(jars), jar_dir))
    else:
        notes.append("NOT CHECKED: mod ids (no jar folder at %s)" % jar_dir)
    return ids, notes


def item_checks(markets_doc, spawn, ids):
    P, unchecked = [], set()
    recs = [("counter", c) for c in markets_doc["counters"] if c.get("status") == "sited"]
    recs += [("stall", s) for s in markets_doc.get("stalls") or [] if s.get("status") == "sited"]
    for kind, rec in recs:
        for it in rec.get("stock") or []:
            item = it["item"]
            ns, path = item.split(":", 1)
            if ns in ids:
                if path not in ids[ns]:
                    P.append(("items", "%s:%s:exists" % (rec["id"], item), "%s %s: %s is in no jar's lang file"
                              % (kind, rec["id"], item)))
            else:
                unchecked.add(ns)
            placed = PLACES_BLOCK.get(item, item)
            for b in {placed, GROWS.get(placed, placed)}:
                if b in spawn:
                    P.append(("items", "%s:%s:spawn" % (rec["id"], item), "%s %s: %s puts down %s, a spawn-condition "
                              "block" % (kind, rec["id"], item, b)))
            power = (ns == "cobblemon" and path.endswith("_ball")) or path.endswith("poke_ball") or \
                    (ns not in ("minecraft",) and ns not in CONVENIENCE_NS) or bool(POWER_VANILLA.fullmatch(item))
            gated = bool(it.get("gate")) and isinstance(rec.get("badge"), int) and rec["badge"] >= 1
            if power and not gated:
                P.append(("power", "%s:%s" % (rec["id"], item), "%s %s: %s is a ball, battle item or boost and is not "
                          "badge-gated" % (kind, rec["id"], item)))
    return P, unchecked


def theme_checks(markets_doc):
    P = []
    for s in markets_doc.get("stalls") or []:
        words = THEME_WORDS.get(s.get("sells"))
        if words is None:
            P.append(("theme", s["id"], "%s: theme %r has no vocabulary here" % (s["id"], s.get("sells"))))
            continue
        for it in s.get("stock") or []:
            item = it["item"]
            path = item.split(":", 1)[1] if item.startswith("minecraft:") else None
            if path in words or (s["id"], item) in HAND_JUDGED:
                continue
            P.append(("theme", "%s:%s" % (s["id"], item), "%s (%s): %s does not read as %r"
                      % (s["id"], s.get("sells"), item, s.get("sells"))))
    return P


def spend_checks(markets_doc, traders):
    P = []
    mart = set(traders["stock_policy"]["mart"]["items"])
    recs = [r for r in markets_doc["counters"] + list(markets_doc.get("stalls") or []) if r.get("status") == "sited"]
    for label, town in SURVEY_NO_SPEND.items():
        if not any(r["town"] == town and any(it["item"] not in mart for it in r.get("stock") or []) for r in recs):
            P.append(("spend", town, "%s (%s): no sited stall or counter sells anything beyond the Mart's %s"
                      % (label, town, sorted(mart))))
    return P


def curve(markets_doc, towns):
    """[(badge, cumulative ask, cumulative income, ratio)] from income_basis.counts' words."""
    critical = {t["id"] for t in towns["towns"] if t.get("critical_path")}
    lines_by_badge = {}
    recs = [(r, False) for r in markets_doc["counters"]] + [(r, True) for r in markets_doc.get("stalls") or []]
    for rec, is_stall in recs:
        if rec.get("town") not in critical or not isinstance(rec.get("badge"), int):
            continue
        groups = {}
        for it in rec.get("stock") or []:
            if it.get("stretch") or (is_stall and not it.get("gate")):
                continue
            k = it.get("group") or it["id"]
            groups[k] = max(groups.get(k, 0), int(it["price"]))
        lines_by_badge[rec["badge"]] = lines_by_badge.get(rec["badge"], 0) + sum(groups.values())
    out, cum = [], 0
    inc = markets_doc["income_basis"]["cumulative_by_badge"]
    for b in range(0, 9):
        cum += lines_by_badge.get(b, 0)
        if b:
            out.append((b, cum, int(inc[str(b)]), round(cum / int(inc[str(b)]), 4)))
    return out


# measured 2026-10-04 by curve() on `git show 31e9b2a:data/markets.json` (no `stalls` key existed), towns at HEAD:
# (badge, cumulative ask, cumulative income). The same numbers came out of 5407171^ and of HEAD 7a7272d
BASELINE_CURVE = [(1, 6550, 9475), (2, 11450, 17023), (3, 20000, 28655), (4, 29800, 45615), (5, 41300, 60905),
                  (6, 54800, 82275), (7, 71000, 109038), (8, 99500, 145078)]


def curve_checks(markets_doc, towns):
    P = []
    rows = curve(markets_doc, towns)
    target = float(markets_doc["income_basis"]["target_ratio"])
    for b, ask, inc, ratio in rows:
        if ratio > target:
            P.append(("curve", "badge%d" % b, "badge %d: ask %d of %d earned, %.3f over %.2f" % (b, ask, inc, ratio, target)))
    if [(b, a, i) for b, a, i, _r in rows] != BASELINE_CURVE:
        P.append(("curve", "baseline", "the curve %s is not the pre-stall curve %s"
                  % ([(b, a, i) for b, a, i, _r in rows], BASELINE_CURVE)))
    return P, rows


# --------------------------------------------------------------------------------------------------------- the run
def audit(source_root=None, jar_dir=None, vanilla=None, npcs=None, r17m_fns=None, markets_files=None):
    """npcs/r17m_fns: R17M's `npc` actions and `fn` ids (default: read from R17M); markets_files: {pack path: lines}
    of the markets pack (default: build/datapacks/cobblers_markets, else markets.build() in memory)."""
    import ground as G
    import terrain as T
    plazas = load(ROOT / "data" / "plaza_centres.json")
    doc = load(ROOT / "data" / "placements.json")
    towns = load(ROOT / "data" / "towns.json")
    mk = load(ROOT / "data" / "markets.json")
    traders = load(ROOT / "data" / "traders.json")
    spawn = set(load(ROOT / "data" / "spawn_blocks.json")["blocks"])
    subs = {s["from"]: s["to"] for s in load(ROOT / "data" / "spawn_block_policy.json").get("substitutions") or []}
    towns_fp = {t["id"]: (t["footprint"]["min_x"], t["footprint"]["min_z"], t["footprint"]["max_x"],
                          t["footprint"]["max_z"]) for t in towns["towns"] if t.get("footprint")}
    notes, P, rows = [], [], {}
    idx = FUNC_DIR / "index.txt"
    if not idx.is_file():
        raise SystemExit("no %s: run python tools/plaza_centre.py build first" % idx)
    order = [l.strip() for l in idx.read_text(encoding="utf-8").splitlines() if l.strip()]
    if sorted(order) != sorted(plazas["towns"]):
        P.append(("square", "index", "index.txt lists %s, data/plaza_centres.json declares %s"
                  % (order, list(plazas["towns"]))))
    base = G.Ground(source_root)
    sea = int(T.sea_level(base.world))
    for settlement in order:
        rec = plazas["towns"].get(settlement)
        if rec is None:
            continue
        g = G.for_settlement(settlement, source_root, doc, base=G.Ground(source_root)) \
            if (doc["settlements"][settlement].get("ground")) else base
        geo = TownGeo(settlement, rec["square"], doc, g, sea)
        model, mp = voxelise((FUNC_DIR / ("%s.mcfunction" % settlement)).read_text(encoding="utf-8").splitlines())
        P += [("function", "%s:%d" % (settlement, i), m) for i, m in enumerate(mp)]
        tp, standing = town_checks(settlement, rec, geo, model, towns_fp, spawn, subs)
        lp, nlights = light_checks(settlement, geo, model, standing)
        rp, reach = reach_checks(settlement, rec, geo, standing)
        sp = stall_checks(settlement, rec, geo, model)
        P += tp + lp + rp + sp
        rows[settlement] = {"blocks": sum(1 for s in model.values() if name_of(s) != "minecraft:air"),
                            "stalls": len(rec["stalls"]), "lights": nlights, "reach": reach,
                            "kept_off": {"street cells": len(geo.street), "lots": len(geo.lots),
                                         "anchors": len(geo.anchors), "buildings": len(geo.footprints),
                                         "sign": bool(geo.sign)}}
    if npcs is None:
        npcs, fns, src = r17m_list()
    else:
        fns, src = (r17m_fns or []), "given"
    if markets_files is None:
        markets_files, msrc = pack_files(), str(MARKETS_PACK)
        if markets_files is None:
            import markets
            built, _n = markets.build(markets.load())
            markets_files = {k: v for k, v in built.items() if isinstance(v, list)}
            msrc = "markets.build() in memory (no %s: python tools/markets.py build)" % MARKETS_PACK
    else:
        msrc = "given"
    summons, kills, fp = r17m_merchants(markets_files, fns)
    notes.append("R17M dialogue clerks (%d) from %s; merchant summons (%d) from %s, following %s"
                 % (len(npcs), src, len(summons), msrc, fns))
    P += fp + staff_checks(plazas, mk, npcs, summons, kills) + merchant_checks(mk, summons)
    ids, jn = jar_index(vanilla, jar_dir)
    notes += jn
    ip, unchecked = item_checks(mk, spawn, ids)
    if unchecked:
        notes.append("NOT CHECKED: ids in namespaces with no jar read: %s" % sorted(unchecked))
    P += ip + theme_checks(mk) + spend_checks(mk, traders)
    cp, crow = curve_checks(mk, towns)
    P += cp
    known = {(c, k) for c, k, _m in P if (c, k) in KNOWN}
    problems = [p for p in P if (p[0], p[1]) not in KNOWN]
    fixed = sorted(set(KNOWN) - known)
    return {"problems": problems, "known": [p for p in P if (p[0], p[1]) in KNOWN], "known_fixed": fixed,
            "towns": rows, "curve": crow, "notes": notes, "hand_judged": sorted("%s %s" % k for k in HAND_JUDGED)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source-root")
    ap.add_argument("--server-dir", help="read <server>/mods for mod ids")
    ap.add_argument("--jar-dir")
    ap.add_argument("--vanilla-jar", default=str(DEFAULT_VANILLA))
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    jar_dir = a.jar_dir or (str(Path(a.server_dir) / "mods") if a.server_dir else str(DEFAULT_JAR_DIR))
    res = audit(a.source_root, jar_dir, a.vanilla_jar)
    for t, r in res["towns"].items():
        print("%-12s %4d blocks, %d stalls, %3d lights, steps to the square: %s; kept off %s"
              % (t, r["blocks"], r["stalls"], r["lights"], r["reach"], r["kept_off"]))
    print("curve (badge, ask, earned, ratio):", " ".join("%d:%d/%d=%.3f" % row for row in res["curve"]))
    for n in res["notes"]:
        print("note:", n)
    for c, k, m in res["known"]:
        print("KNOWN %-8s %s" % (c, m))
    for k in res["known_fixed"]:
        print("FIXED? a KNOWN entry no longer found (remove it from KNOWN): %s" % (k,))
    for c, k, m in res["problems"]:
        print("PROBLEM %-8s %s" % (c, m))
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1, default=list), encoding="utf-8")
    bad = len(res["problems"]) + len(res["known_fixed"])
    print("town squares audit: %d problem(s), %d known, %d known no longer found" % (len(res["problems"]),
                                                                                     len(res["known"]), len(res["known_fixed"])))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
