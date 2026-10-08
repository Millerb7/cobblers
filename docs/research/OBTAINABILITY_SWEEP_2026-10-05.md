# Obtainability sweep, 2026-10-05: the server's own jars, with the Nether in

**Question (the owner).** "Our world is pre-generated, so nothing from worldgen exists -- no ores in chunks, no
structure loot, no chest spawns. Audit every mod for items with no route to a player's hands, what they silently
break, and what our own systems assume a player can get. Then propose how each gets in. Build the cheap and obvious
ones. The stone shard gate is one instance of this; find the rest." And from the play test: "the stone shard gate,
so evolution stones are actually purchasable".

**Builds on, does not redo:** `OBTAINABILITY_MODS.md` and `OBTAINABILITY_VANILLA_COBBLEMON.md` (2026-10-04). Their
rows stand unless this document says otherwise. **What is new here:** (1) the inputs are now the server's own jars
and global datapacks, so their biggest ASSUMED is settled; (2) the owner's ruling of 2026-10-05 that **the Nether
exists** and some items are netherite-gated, which supersedes their "no Nether" branch; (3) a scan of what our own
`data/` hands out or relies on; (4) three routes built (ten evolution stones and the Ability Capsule on counters, a
Z-Ring in a reward cache) and four prize ids verified.

**Status.** Research plus three data commits. No server, world, staging or the server folder was touched.

---

## 0. Inputs and method

| Input | What it is | Status |
|---|---|---|
| `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/` | the server's 102 jars | read with Python `zipfile`. **101 of 102 are byte-identical (sha256) to the Modrinth profile `Fabric 1.21.10` the 2026-10-04 sweeps used**; the odd one is `worldedit-mod-7.3.8.jar`, server-only and itemless for players. So the earlier sweeps' "ASSUMED identical to the server's jars" is now **VERIFIED** |
| the snapshot's `datapacks/` | the six Cobbleverse/PokeCenter zips plus our global `cobblers_*` packs | five zips identical to the profile's; `COBBLEVERSE-DP-v31.zip` differs (our riding-seat patch, known). `extra/` (Hoenn, Johto, Sinnoh, Terralith) is off and was not read |
| the snapshot's `config/` | `mobsbegone-blacklist.json`, `mega_showdown/config.json`, `cobbledollars/*`, `repurposed_structures.json` | read |
| the vanilla 1.21.1 jar | `%APPDATA%/ModrinthApp/meta/versions/1.21.1-0.19.5/1.21.1-0.19.5.jar` | vanilla recipes, loot and tags |
| `data/*.json` | our supply: `markets.json`, `traders.json`, `rewards.json`, `quests.json`, `progression.json`, `research_station.json`, `mines.json`, `gulch_mine.json`, `apricorn_farm.json`; and the installed `cobblers_vendors` / `cobblers_rewards` functions in the snapshot | world-local packs (`cobblers_markets`, `cobblers_mines`) are not in a global snapshot, so they are read from `data/` |

**The model** (scratch scripts, not committed: index every recipe, loot table, tag, species drop and lang-registered
item; then a fixpoint). An item is reached when a route reaches it from reached inputs. Tags merge across archives;
recipes carrying `fabric:load_conditions` on absent mods are dropped; furnace, blast furnace, smoker, campfire,
stonecutter, smithing table, campfire pot and brewing stand recipes need their station; Rechiseled's chiseling groups
convert among themselves with the chisel. Tiers, earliest wins:

| Tier | Route | Character |
|---|---|---|
| **A** | vanilla terrain, block drops, fishing; crafting and the stations; our shops (`markets.json` counters and stalls, the installed `cobblers_vendors` shops, the Assayer's stones), the stone faces (`mines.json`), the gulch Cutters, the apricorn farm's fruiting trees (not yet applied) | renewable or ours |
| **B** | drops of species `data/spawns.json` names (684 rostered; Pasture Loot farms them); two code drops read by the 2026-10-04 sweep: CobbleCuisine's bean seeds from short grass, Mega Showdown's tera shards on wild defeats (`teraShardDropRate` 10) | renewable once caught |
| **N** | the Nether's blocks and ores (quartz, glowstone, magma, ancient debris and netherite, nether wart, `cobblemon:nether_fire_stone_ore`) | renewable, a portal away |
| **NC** | Nether structure chests: vanilla bastion/fortress/ruined-portal, Cobblemon's injections into them, Repurposed Structures' Nether cities, mineshafts, outposts, strongholds, shipwrecks, and Legendary Monuments' Stark Mountain and Turnback Cave | **finite per structure**; how many structures the Nether holds inside our border is NOT measured |
| **E** | one-off grants in installed packs and our data (rewards, quests, first wins, the research station) | not renewable |
| **F** | ambient RCT trainer loot, Cobblemon alpha rewards, species not in our roster | random or ASSUMED |
| **NONE** | no route at all | |

**What the model does not see** (it errs toward NONE): tree growth (apricorn and saccharine wood), block
interactions beyond water on dirt, evolution-event drops (Shell Helmet), colour-variant items whose base id has no
lang key (Cobblenav's navigators), Repurposed Structures' `importModdedItems: true` (it adds modded items to its
chests at runtime, so NC is an undercount), and whether a rostered species actually spawns in our painted biomes. Its
vanilla seed is generous (every natural block and every block-drop counts as A, minus a hand list of worldgen-only
things: sculk, amethyst, cobweb, trial and End items), because vanilla is the other sweep's share.

---

## 1. The stone shard gate

**There is no shard in the evolution-stone chain, in any jar or datapack the server loads.** Every lang-registered
`*shard*` item was read: Mega Showdown's 19 tera shards, Waystones' `attuned_shard`, `crumbling_attuned_shard`,
`deepslate_shard` and `dormant_shard`, and LumyMon's `corrupted_shard`. None is an input to any recipe that makes an
evolution stone. The 76 recipes that make the ten stones are all of one kind: smelt or blast an ore block (Cobblemon's
`*_stone_ore`, `deepslate_*`, `dripstone_moon_stone_ore`, `terracotta_sun_stone_ore`, `nether_fire_stone_ore`, and
Mega Showdown's `mega_meteorid_*_ore`), or unpack a stone block. No ore generates in our overworld (STATE), so **the
gate is the ore**, and the only routes in were:

| Route | Where | Proven? |
|---|---|---|
| the 22 faces at seven places | `data/mines.json`, R9O | in staging, not seen in game |
| the Assayer, all ten at 2,100 | `data/traders.json mining_assayer`, the Mining Town, **leg 8** | generated (the installed `vendors_mining_town_place` carries `water_stone ... Price:"2100"`); that a CobbleDollars merchant with an authored shop sells is **proof P-7, never run** |
| `nether_fire_stone_ore` | the Nether (`#minecraft:is_nether`, `has_ore/ore_fire_stone_nether.json`) | new with the owner's Nether ruling: Fire only |

So the only seller was late and unproven. **Built:** the tea town's Steepside counter (leg 2, off the critical path,
"we don't ask for badges") now sells all ten stones at 2,100 each through the counters' dialogue purchase, which is
the ferries' checked-payment sequence (balance read EXP-040, macro charge EXP-042). One price everywhere (the
Assayer's, open decision O-6); `data/bank.json` already refuses to buy any stone back, so neither a face nor a
counter prints money. Off the critical path, so it is outside the price curve, where `stalls_basis.budget` already
puts stones. **Not verified:** that a counter purchase completes in game (`data/markets.json` status: "NOT run in
game"), and that a 16-option dialogue menu (15 lines and Leave) displays well; the longest before was 8.

---

## 2. The Nether is in, its mobs are not

The owner's ruling resolves the Nether-block items; MobsBeGone resolves nothing else, because **every Nether mob is
on the server's blacklist** (VERIFIED, `config/mobsbegone-blacklist.json`, 81 entities): blaze, ghast, wither
skeleton, wither, piglin, piglin brute, hoglin, zoglin, magma cube, strider, zombified piglin, enderman.

| Now reachable (N) | What it unlocks | Still dead, and why |
|---|---|---|
| quartz | **Link Cable** (solo trade evolutions; 18 rostered families, relayed from `OBTAINABILITY_VANILLA_COBBLEMON.md` row 6) | **blaze rod**: no blazes and no Pokemon drops one. Only Repurposed Structures' Nether city and Nether stronghold storage chests (NC). One rod is enough for a brewing stand for good |
| glowstone | **Tera Orb** (Mega Showdown), Upgrade (redstone lamp) | **ghast tear** (Destiny Knot): NC only (RS Nether ruins, monuments, shipwrecks; Turnback Cave) |
| magma block | Magmarizer recipe | **wither skeleton skull**, hence the Wither and the nether star: NONE |
| ancient debris, netherite | TMCraft's six `netherite_blank_*`, Sophisticated Storage's netherite tiers, netherite gear: the owner's "netherite grind" | **piglin bartering** (soul speed, crying obsidian, ender pearls): no piglins |
| `nether_fire_stone_ore` | Fire Stones | gems, candies, Ability Patch, PP Up, Ancient balls: Nether chests only (NC), finite |

**Brewing (a hinge the earlier sweeps did not draw).** `cobblemon:ability_capsule` brews from `minecraft:dragon_breath`
over `cobblemon:medicinal_brew` (`data/cobblemon/recipe/brewing_stand/ability_capsule.json`), and **four rostered
species drop dragon's breath** (Dratini, Dragonair, Deino, Drampa). So one blaze rod from a Nether chest gives a
brewing stand and with it renewable Ability Capsules. PP Up still needs `cobblemon:vivichoke` (F), so PP Up and the
six brewed vitamins stay out of reach by brewing.

---

## 3. Counts by mod

Lang-registered items (block items included, spawn eggs left out). NONE is "no route at all"; F and NC are routes
that exist but are random or finite. Libraries and client mods with no items are not listed (Fabric API, Kotlin,
Architectury, owo, geckolib, Cloth, YACL, Iceberg, Balm, Resourceful Lib, Athena, Platform, ForgeConfigAPIPort,
Lithium, ModernFix, FerriteCore, ScalableLux, Debugify, Neruina, NotEnoughCrashes, Packet Fixer, EntityCulling,
DistantHorizons, Xaero's maps, REI, FancyMenu, Konkrete, Melody, Particular, Sound Physics, Ping Wheel, Highlight,
Not Enough Animations, Default Options, Global Packs, Configurable, fzzy_config, midnightlib, libjf, Respackopts,
Fusion, StackDeobfuscator, NoChatRestrictions, MobsBeGone, advancementdisable, forgivingvoid, netherportalfix,
nethermap, Axiom, WorldEdit, villagerconfig, timcore, capturexp, Safe Pastures, Pasture Loot, lenientdeath,
battle-extras, MoreCobblemonTweaks, Trinkets, accessories).

| Mod (namespace) | Items | A | B | N | NC | E | F | **NONE** | What the NONE are |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Cobblemon 1.8.0 (`cobblemon`) | 725 | 223 | 117 | 4 | 161 | 8 | 125 | **87** | mint seeds (6), saccharine and apricorn wood (growth, model gap), gimmighoul chest, habitat block, poke cake/puff and the regional sweets, Cherish Ball, Shell Helmet (an evolution-event drop, model gap) |
| Mega Showdown 1.0.2 | 316 | 114 | 37 | 2 | 17 | 3 | 70 | **73** | Z-Ring and its variants, `blank_z`, sparkling stones, Dynamax (band, wishing star, max mushroom, power spot, soups), plates, `red_orb`/`blue_orb`, masks, rusted sword/shield, `prison_bottle`, 6 species mega stones |
| TMCraft 1.4.19 | 36 + per-move TMs | 3 | 5 | 1 | 0 | 0 | 0 | **27** | blank eggs, books, stars and their move items and recorders. **Not one of the 3,596 TM recipes is craftable from A, B or N inputs** (section 4, row 1) |
| LumyMon 0.6.6 | 215 | 6 | 4 | 1 | 15 | 9 | 18 | **162** | other regions' radars, altars, relics, keys; our own legendary items are E (the research station) |
| Legendary Monuments | 53 | 2 | 0 | 0 | 5 | 0 | 0 | **46** | Distortion World and Galar particle blocks (we place them; players never need them); the Ruinous seals are NC |
| CobbleCuisine 2.0.1 | 177 | 5 | 88 | 0 | 1 | 2 | 71 | **10** | dishes whose ingredient is a NONE Cobblemon food |
| ZAMega 1.7.7 | 46 | 11 | 0 | 0 | 0 | 0 | 0 | **35** | mega stones for species the Cutters do not serve (decision 11) |
| Only Bottle Caps 1.5.0 (`obc`) | 15 | 2 | 0 | 0 | 0 | 0 | 12 | **1** | plain `bottle_cap`; the stat caps are F; gold is sold at Holdfast |
| CobbleverseBadges 1.3 | 40 | 4 | 0 | 0 | 0 | 9 | 27 | 0 | other regions' badges are F and unneeded |
| Waystones 21.1.37 | 58 | 5 | 29 | 18 | 0 | 0 | 0 | **6** | attuned shards, warp portal, bound scroll, end-stone waystone, memorial |
| Sophisticated Backpacks / Storage / Core | 57 / 109 / 1 | 44 / 82 / 0 | 6 / 3 | 2 / 14 | 2 / 0 | | 1 / 0 | **2 / 10 / 1** | infinity (creative), pump and storage-network parts |
| Cobblenav 2.4.1 | 4 | | | | 1 | | | 3 | lang base ids only; the coloured navigators craft (model gap). FishingNav needs a water gem (NC) |
| Cobbreeding 2.3.0 | 329 | | | | | | | 329 | egg models; eggs come from pasture breeding (code). Not a gap |
| Pokeblocks 1.4.0 | 325 | 1 | | | | | | 324 | figurines and dolls: decoration we place |
| CobbleFurnies 1.2 | 369 | 323 | | | | 2 | | 44 | apricorn and saccharine furniture (wood growth), the "dark" chairs and stools |
| Cozy Home | 277 | 183 | 15 | 52 | | | | 27 | ominous, undead, end-stone and glass variants |
| Carved Wood | 311 | 263 | | 24 | | | | 24 | pale oak (VanillaBackport's pale garden is worldgen) |
| Rechiseled | 2,418 | 1,780 | 162 | 416 | | | | 60 | variants of NONE base blocks |
| Handcrafted, Beautify, Moar Concrete, Iron Chests, Comforts, Tom's Storage, Battle Positions, Fight or Flight, rctmod | 285, 56, 144, 36, 34, 22, 4, 2, 3 | all or all but one | | | | | | 1, 0, 0, 0, 1, 1, 0, 0, 0 | `comforts:no_sleep`, Tom's painted trim |
| cobblemon-additions (`bca`) | 2 | | | | | | | 2 | Pokemon spawners: admin blocks |
| vanilla (`minecraft`) | 1,527 | 1,105 | 37 | 84 | 68 | 2 | 48 | 183 | the other sweep's; the ones that matter are in section 2 |

---

## 4. What breaks, in priority order

P0: a system or progression chain is dead. P1: a feature is dead or rests on finite/random loot. P2: one evolution,
form or convenience. P3: cosmetic. "Ours" names the files in `data/` that hand out or rely on the item.

| P | Item(s) | Natural route | What breaks | Ours | Proposed route | Cost |
|---|---|---|---|---|---|---|
| **P0** | **18 type gems** (`cobblemon:*_gem`) | NC: `bastion_other` (by Cobblemon's injection), Stark Mountain; F: alpha rewards | **every crafted TM**: of the 3,596 TM recipes the server loads (TMCraft's jar: 2,184 making `tmcraft:tm_*` and 929 making `cobblemon:technical_machine`; Cobbleverse DP-v31: 483), **none** has all its inputs at A, B or N; 805 name a type gem outright, the rest wait on NC or NONE inputs. Also the FishingNav (water gem) | none | the owner asked for "a TM seller after every few gyms" (play test 7): **sell finished TMs** (`cobblemon:technical_machine` with its move component, the shape `rewards.json` already gives at Victory Road) on the gym counters, or sell gems per gym type | data, but it prices every TM in the game and touches the curve: the owner's. Not built |
| **P0** | **Fossils** (14 of 15) | F only (`cobblemon:fossils/*` are worldgen suspicious blocks) | the Resurrection Machine; fossil families not caught wild | `quests`, `rewards`: one Old Amber | fossil faces in the `mines.json` pattern (placed suspicious gravel naming `cobblemon:fossils/rare/<fossil>`), or a counter at the Mining Town's fossil lab | a generator change plus a world placement: not built (brief) |
| **P0** | **Mint seeds** (`cobblemon:red_mint` ... `white_mint`, 6) and so 21 mints and the 6 Power items | NONE (seeds); leaves F | natures; Power items | none | six counter lines of the SEEDS (renewable once planted). The tea town's Steepside is the fiction (a tea-house herb), but it now carries 15 lines | six lines; the price and gate are a power-rung call, so not built |
| **P1** | **Z-Moves**: `z_ring`, `blank_z`, sparkling stones | NONE | the server runs `zMoves: true`, and **our Raw Tear cache gave a Dragonium Z no one could use** | `rewards` `vr_raw_tear` | **built**: the cache now gives a Z-Ring with the crystal (section 6). The owner still decides Z in or out; out = `zMoves: false` and a Mega Stone in that cache | done for the one cache |
| **P1** | **Dynamax**: band, wishing star, max mushroom, power spot | NONE (`dynamaxAnywhere: false`, `powerSpotRange: 32`, VERIFIED in the server config) | Dynamax and Gigantamax, max/gmax TMs | `structures` names `wishing_star_crystal` (a placed block) | `dynamax: false` in a Mega Showdown overlay (one config line), or a Power Spot plus a band as a late reward | owner decision; unchanged from 2026-10-04 |
| **P1** | **Ability Capsule** | NC (bastion, ruined portal); brewable from dragon's breath (B) once a brewing stand exists (blaze rod: NC) | ability swaps; the owner asked for it (play test 8) | none | **built**: Northlight's Station Supply, gym 6, PROPOSED 10,000 | done |
| **P1** | **Brewing stand** (`minecraft:blaze_rod`) | NC: Repurposed Structures' Nether city and stronghold storage chests only | Ability Capsule by brewing; vanilla potions | `research_station`, `gym_interiors`, `town_dressing` place one as scenery | one counter line of the stand itself (a single purchase unlocks it for good) | one line; not built (it is a power key, and the critical counters have no curve room) |
| **P1** | **Exp. Candies, Rare Candy, Ability Patch, PP Up / PP Max** | NC only (bastions, ruined portals, Turnback Cave) | levelling against the cap; hidden abilities | `arena_fights` gives `ability_patch` at rank 7 and streak 50 | as 2026-10-04: cut the candies deliberately (the level cap); the Ability Patch stays a prize | none |
| **P2** | **Ancient balls** (15), Beast Ball | NC (Nether fortress via injection, Stark Mountain) | Hisui-style balls | `rewards` gives two | cut, or a late counter line | none |
| **P2** | **`lumymon:ancient_dna`** | E (Giovanni's first win) | Mewtwo's fossil also needs `cloning_catalyst` (F: a never-spawning admin trainer) | `progression` | drop it from the grant, or add the catalyst | one reward edit; the owner's |
| **P2** | **Plain bottle cap** | NONE (the stat caps are F) | one-stat hyper-training | `arena_fights` and `rewards` give gold caps | sell plain caps beside gold at Holdfast | one line |
| **P2** | **Red Orb, memories, plates, Prison Bottle, Griseous items** | NONE / NC / one-shot | Primal Groudon (we offer Groudon), Silvally types, Hoopa, Giratina forms | `legendaries` (Groudon) | hand each with its species | quest data per species |
| **P2** | **Dubious Disc, Sachet, Chipped Pot, Masterpiece Teacup** | NC / F | Porygon-Z, Aromatisse, Sinistcha/Polteageist forms | none | one cache each if wanted | low |
| **P3** | LumyMon's nine Kanto gym locators | crafted from obtainable items | a locator pointing at a gym that never generates | none | empty their recipes at the upstream paths: needs a recipe kind in `progression_pack.py upstream_neutralised` (today loot tables and functions only) | generator change |
| **P3** | Legendary Monuments Distortion and Galar blocks, LumyMon altars and statues | NONE | nothing a player needs | `rift_skin`, `deep_city`, `vr_caves`, `adopted_legendary_sites` place them | none: they are ours to place | none |

**Was 2026-10-04's, now settled by the Nether:** Link Cable, Tera Orb, Upgrade, Magmarizer, netherite. **Was "no
Pokemon drop", still true:** blaze rod, ghast tear, glowstone (now N), wither skull.

---

## 5. What our own systems assume

Every item id in `data/*.json` that is not reachable at A, B or N, by file (from the model; scenery blocks we place
ourselves left out):

- **Handed out once (E), and that is the design:** the eight Kanto badges and the trophy, the Master Ball and Origin
  Ball (`progression`), Kubfu's two scrolls, the legendary feathers, dews, crown and shaderoot (`research_station`,
  `quests`, `rewards`), Moomoo Milk and Old Amber (`quests`, `rewards`).
- **Handed out, and broken:** `mega_showdown:dragonium_z` with no Z-Ring anywhere (fixed); `lumymon:ancient_dna`
  with no Cloning Catalyst (recorded).
- **Prize ids recorded as NOT VERIFIED:** `arena_fights` named `choice_scarf`, `life_orb` and `ability_patch` "NOT
  VERIFIED as an item id". All three are in the server's Cobblemon jar (lang and item model): fixed.
- **Relied on, and NC/F:** `blackout.json` lists many NC/F items (X items, Ancient balls, elixirs) as categories a
  wild victor may claim: it takes, it does not supply, so nothing breaks. `traders.json` withholds `energy_root`
  (F): withholding, not supplying.
- **Gym and League first wins** name 23 distinct `tmcraft:tm_*` items (`data/progression.json`, counted): today these
  and the Victory Road TM (`rewards`) are the **only** TMs a player can be sure of holding, since no TM recipe is
  craftable from renewable inputs (section 4 row 1).

---

## 6. What was built

| Commit | What | Where it appears in game | Steps to reach the world |
|---|---|---|---|
| `Markets: the ten evolution stones ...` | `data/markets.json`: Steepside (tea town) sells all ten stones at 2,100, ungated; Northlight's Station Supply sells `cobblemon:ability_capsule`, gym 6, PROPOSED 10,000; both greetings say so | the keeper beside the tea town Mart, (2604, 115, 3596); the station keeper at Northlight, (7277, 117, 1540) | `tools/markets.py build` (a prepare job), install `cobblers_markets` (world-local), restart (the keepers' NPC classes load at boot), then R17M |
| `Rewards: the Raw Tear's Dragonium Z comes with a Z-Ring` | `data/rewards.json vr_raw_tear` gives `mega_showdown:z_ring` too | the barrel at the back of the Raw Tear, Victory Road, (3462, 45, 2685); each player once | `tools/rewards_pack.py` (prepare), install `cobblers_rewards`, `/reload` |
| `Arena prizes: ... verified` | `data/arena_fights.json`: four verification strings | none (text) | none |

**Checks run:** `markets.py audit --skip-dressing` 0 problems (with `derived/towns` copied in); `markets.py ids`
**160 of 160 sold ids found** in the snapshot's jars plus the vanilla jar; `markets.py report` unchanged on the
critical path (the new lines are off it); pytest `test_markets_audit`, `test_town_squares_audit`,
`test_compile_dialogue_all`, `test_traders` 91 passed, 6 skipped (they need a built plaza pack); `test_rewards_pack`
223 passed; the arena suites 87 passed, 1 skipped. `rewards_pack.py` writes `give @s mega_showdown:z_ring 1`.

**Not verified:** any purchase from a counter in game; the 16-option menu at Steepside; that a Z-Ring held or worn
lets a Z-Move fire under Mega Showdown 1.0.2 (whether it must sit in an accessory slot is unread); the capsule price.

**Refused and left:** `rewards_pack.py --server-dir <snapshot>` refused to read the snapshot's jars without the
coordination lock ("runtime_guard: refusing to read the server's mod jars without the coordination lock"). It treats
any server-shaped directory as the live server. The Z-Ring id was verified from the snapshot jar by hand instead
(`assets/mega_showdown/models/item/z_ring.json`, `data/mega_showdown/recipe/z_ring.json`); the pack was built
without the jar check.

---

## 7. Proposed, not built (each needs a price, a gate or a placement)

1. **A TM counter** (play test 7) selling finished TMs, which answers the gem gap without pricing 18 gems. Needs the
   move list per counter and the curve.
2. **Mint seeds**, six lines; one purchase each makes natures renewable.
3. **A brewing stand** line (one per player is enough): makes Ability Capsules renewable from dragon's breath.
4. **Fossil faces**, in the `mines.json` restore pattern.
5. **The Z and Dynamax decisions** (config), then the plain bottle cap, Red Orb with Groudon, and the Giovanni DNA.
6. **A recipe kind in `upstream_neutralised`** for LumyMon's Kanto locators.

## 8. Defects recorded (not chased)

- `docs/STATE.md` "Every Cobblemon item is obtainable without crafting ... No audit of which items lack a natural
  source exists yet": this sweep is that audit for crafting-allowed routes (Cobblemon: 87 items with no route, 125
  random-only, 161 Nether-chest-only). A no-crafting audit is still owed. STATE is not edited here.
- `OBTAINABILITY_VANILLA_COBBLEMON.md` counts "the Exchange's ten stones" at tier A; that route is proof P-7, never
  run.
- `tools/progression_pack.py upstream_neutralised` cannot empty a recipe.
- `rewards_pack.py`'s jar check cannot be pointed at an offline snapshot (above).
