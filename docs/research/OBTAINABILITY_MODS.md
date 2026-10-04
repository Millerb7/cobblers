# Obtainability sweep: the mods (everything except vanilla and Cobblemon)

**Question (the owner, 2026-10-04).** The world is pre-generated, so nothing that normally comes from
worldgen exists: no modded ores, no structure loot, no generated villages. Every item must come from a
trader, a drop, a craft, or our own hands. What is unobtainable, what does that silently break, what do
we depend on, and how should each thing get into the game?

**Share.** Every mod in the pack except vanilla and Cobblemon itself (another sweep owns those and the
Cobbleverse datapack's own content). Where a Cobblemon item gates a *mod's* feature (type gems gate
TMCraft) it is named here and marked as the other sweep's to confirm.

**Status.** Research, 2026-10-04. Nothing built. No server, world or staging was touched.

---

## 0. Method, and what is and is not verified

**Evidence.**

| Source | What it is | Status |
|---|---|---|
| `%APPDATA%/ModrinthApp/profiles/Fabric 1.21.10/mods/` | 137 jars; the 1.8 set by name and version: `Cobblemon-fabric-1.8.0`, `mega_showdown-fabric-1.0.2+1.8`, `tmcraft-1.4.19+1.8.0`, `Cobbreeding-2.3.0`, `zamega-1.7.7+1.8`, `rctmod-0.19.0`, no Raid Dens (matches `modpack/manifest/overlay.json`) | read with Python `zipfile`; **ASSUMED byte-identical to the server's jars** (hashes not compared: the server tree was not touched) |
| the same profile's `datapacks/` | `COBBLEVERSE-DP-v31`, `-Loot-DP-v11`, `-RCT-DP-v20`, `PokeCenterPCs-DP`, `No Ender Dragon`, `No Hunger`; region packs under `extra/` | the six top-level packs are **ASSUMED** to be the server's enabled set (Cobbleverse's `global_packs` default; region packs off per CLAUDE.md). Our patched DP-v31 differs only in riding seats |
| `data/*.json` in this repo | our supply: `markets.json`, `rewards.json`, `quests.json`, `research_station.json`, `progression.json` `first_win_rewards`, `gulch_mine.json`, `traders.json`, `portals.json` | read; **in the data is not in the game**: most of it is staging-only or unrun (`docs/STATE.md`) |
| `base-pack/cobbleverse/config/` | `mega_showdown/config.json`, `mobsbegone-blacklist.json` (81 entities), `rctmod-server.toml` via `modpack/config/` | read |

**The fixpoint.** One script (scratch, not committed) indexed every jar's and enabled datapack's recipes
(a datapack file overrides the jar file at the same path; `fabric:load_conditions` on absent mods drop
the recipe), item tags, loot tables, worldgen and structure templates, Cobblemon species drops and our
data, then iterated: an item is obtainable when a route reaches it from obtainable inputs. Routes were
graded into three classes, because "obtainable once" is not "obtainable":

| Class | Routes counted | Character |
|---|---|---|
| **Core** | our markets, rewards, quest/first-win grants and the gulch drops; crafting, smelting, smithing, Rechiseled's chisel; block drops of obtainable blocks; Pokemon drops (Cobblemon species files); code drops found in the jars (Mega Showdown tera shards, `teraShardDropRate` 10; CobbleCuisine bean seeds injected into `minecraft:blocks/short_grass`, VERIFIED by the class `CobbleCuisineLootInjector`) | renewable or deliberately ours |
| **Bonus** | ambient RCT trainers for trainer-card holders (`spawningRequiresTrainerCard = true`; 33 group/single trainers with `spawnWeightFactor` > 0 and no non-Kanto series); Nether chests (`bastion_*`, `nether_bridge`, `ruined_portal`) that the Loot-DP stocks | random, biome-whitelisted, mostly **one defeat per player** (`maxTrainerDefeats: 1` on most groups); the Nether is **ASSUMED** reachable by a player-built portal |
| **One-shot** | loot kept in placed donor templates (`tools/place_donor.py` keeps loot unless `clear_loot`): `gym6_observatory` (`mega_showdown:observatory`), `dig_site_a`/`_b` (`archaeological_site_a/_b`) | finite, shared by the whole server, first come first served |

**Not handled, and why.** Vanilla items were treated as obtainable (the other sweep's share), with one
exception that matters to the mods: MobsBeGone removes 81 entities, every hostile **and** cows, sheep,
chickens, pigs, blazes, endermen and ghasts, so a vanilla mob drop exists only as a Pokemon drop
(VERIFIED: ender pearl 20 species, blaze powder 23, leather 15, string 31; **blaze rod, ghast tear,
glowstone dust: 0 species**). Item counts come from `assets/*/models/item/`, which over-counts
(`*_3d` models, spawn eggs, Cobblenav "flicker" variants, Cobbreeding's per-type egg models), so the
per-mod totals below are upper bounds; the named items are real.

---

## 1. What breaks, in priority order

Priority is "what a player meets that silently does nothing". P1 breaks a system the campaign already
offers; P2 breaks something we hand out or plan; P3 is a feature nobody can reach but nothing points at.

| P | Mod | Item | What needs it | Why unreachable | Proposed route | Cost |
|---|---|---|---|---|---|---|
| **P1** | TMCraft (gate is Cobblemon's) | **type gems** (`cobblemon:*_gem`, 18) | every one of TMCraft's ~930 `tm_*` recipes: `diamond_blank_disc` + a gem + a themed item (e.g. `tm_thunderbolt` = disc + `electric_gem` + `electirizer`, VERIFIED `data/tmcraft/recipe/tm_thunderbolt.json`); also Cobblemon's own TM Machine | gems come from gem clusters (worldgen) and structure loot. **Core: 16 of 18 have no route** (fighting and poison only as a legendary's drop). Bonus: the ambient `expert` group (plains biomes) and dig-site sand (one-shot) | sell gems: a "gem cutter" stall per gym town selling that gym's type, or the Mining Town Exchange selling all 18 behind badges. Or skip crafting: sell finished TMs at counters, as the leaders already give them | data: stall lines in `markets.json` (owner sets price/gate). The owner decides which TM grammar the campaign teaches (`reward-item-inventory.md` 1) |
| **P1** | TMCraft | TMs as a whole | movesets | without gems, **core TMs = the 23 leader first-win TMs** (`progression.json` `first_win_rewards`). Bonus: all 869 plain TMs sit in one Rocket loot table (`rctmod:generic/team_rocket/tms`) reached by the ambient `team_rocket_general` (badlands, one defeat per player) and by Nether bastion chests (`minecraft:cobblemon/tms`, Loot-DP) | as above; or set game rule `consumeMoveItemOnUse false` so each given TM is a permanent unlock (VERIFIED rule name in the jar's lang) | one game rule, or market data |
| **P1** | Mega Showdown | Z-Ring (`z_ring`) and blank Z (`blank_z`) | Z-Moves; **our own reward**: `rewards.json` `vr_raw_tear` gives `dragonium_z`, which does nothing without a Z-Ring | Z-Ring = `sparkling_stone_light` + white apricorn + iron. The stone is in the `archaeological_site_rare` table: **one suspicious block per dig-site template** (VERIFIED, NBT), two placed, rolling light or dark: **at most two stones server-wide, perhaps one light**. `blank_z`: one in the `observatory` template (`gym6_observatory`), one each in the Dawn/Dusk towers if pasted with loot; otherwise only the `minecraft:mega_showdown/crystals` table, which nothing live references | decide Z in or out. **In:** a Z-Ring per player as a quest grant (`grant_reward_once`), crystals as regional caches. **Out:** `zMoves: false` in the Mega Showdown config and swap the Raw Tear's crystal for a Mega Stone | in: one quest record + caches; out: one config overlay + one reward edit |
| **P1** | Mega Showdown | Dynamax: wishing star, Dynamax Band, Power Spot, Max Mushroom | Dynamax/Gigantamax; Max Soup/Honey, Dynamax Candy; 52 max/gmax TMs | wishing star only from `wishing_star_crystal` in the unplaced `wishing_weald`; max mushroom is worldgen-only; **and `dynamaxAnywhere: false` with `powerSpotRange: 32`**, so even a Band needs a Power Spot block (wishing star + max mushroom) within 32 blocks | **cut**: `dynamax: false` in an overlay of `config/mega_showdown/config.json`; consequence: no Dynamax anywhere, the max/gmax TMs and the Max items stay unreachable, nothing else depends on them | one config file |
| **P2** | Mega Showdown | Tera Orb | Terastallization | crafts from blaze powder, diamond, ender pearl, **glowstone dust**, amethyst shard (VERIFIED recipe). Glowstone has no Pokemon drop and no overworld source: **the Nether only**. Shards are fine: a code drop on wild defeats (10%), 50 to change type | sell the Tera Orb (or glowstone) at a late counter; or confirm the Nether is part of the game | one stall line |
| **P2** | Mega Showdown | form-change items for species we offer | **Groudon** (`legendaries.json`): `red_orb`, no source anywhere, Primal Groudon dead. **Silvally** (Type: Null starter): 17 memories, only in RCT `generic/unique/memories`, which no spawning trainer references; Silvally stays Normal. **Hoopa**: `prison_bottle`, one-shot (observatory dome chest via `desert_pyramid` archaeology). **Necrozma**: N-Solarizer/Lunarizer craft (sun/moon stone), `ultranecrozium_z` bonus only. **Giratina**: Griseous Orb bonus only | hand each item with its species (the same quest that grants or seats the legendary); cut the ones whose species we never offer | quest data per species |
| **P2** | LumyMon | `ancient_dna` | given by **Giovanni's first win** (`progression.json:3124`) | Mewtwo's Cobbleverse fossil (`data/cobblemon/fossils/mewtwo.json`, DP-v31) needs `ancient_dna` **and** `cloning_catalyst`; the catalyst only drops from `team_rocket_admin_atena` (`spawnWeightFactor` 0, never spawns). Mewtwo is in no campaign table: **a reward that does nothing** | either drop it from Giovanni's grant, or add the catalyst beside it if Mewtwo is meant to be revivable | one reward edit |
| **P2** | LumyMon | gym "locator" items: `onyx_stone`, `cerulean_star`, ... `boss_ring` (9, Kanto) | nothing of ours | **obtainable, and broken**: DP-v31 recipes (e.g. stone + `hard_stone` + coal, and Stoneford sells hard stone) make a locator whose `lumymon:structure_name` is `cobbleverse:brock`, a gym that never generates. ASSUMED: using it searches for a structure that is not there (a locate into nothing, or into ungenerated chunks past the border) | override the nine recipes empty at their DP paths, as `progression.json` `upstream_neutralised` already does for the gym-map loot tables | a recipe-override list in the progression pack (generator change, small) |
| **P2** | Only Bottle Caps | plain `bottle_cap` and the six stat caps | hyper-training one stat | only `rctmod:generic/unique/bottlecaps`, referenced by no spawning trainer. The **gold** cap is sold at Holdfast (gym 8, 6000) | sell plain caps (they craft into stat caps) at Holdfast or Northlight, or accept gold-only | one stall line |
| **P3** | Mega Showdown | Key Stone, `keystone_block` | coloured bracelets, `mega_ring`, `omni_ring` and character accessories (`may_bracelet`, `korrina_glove`, `lysandre_ring`...) | `keystone_ore` exists only in the unplaced `megaroid`. **Mega Evolution itself is unaffected**: the plain `mega_bracelet` is sold at Fenhide (gym 5, 7500) | none needed; cosmetic. Optionally the Key Stone as a League reward | none |
| P3 | Mega Showdown | 32 of 92 keyed stones | Megas whose Pokemon cannot be caught here | the Cutters offer only the 60 whose Pokemon exist (decision 11, `gulch_mine.json` `cutters`) | intended | none |
| P3 | Mega Showdown | plates (17), drives (4, bonus only), `rusted_sword`/`_shield`, masks, `gracidea_flower`, `reveal_glass`, `adamant_crystal`, `lustrous_globe`, `griseous_core`, `deoxys_meteorite`, `zygarde_cell` (one-shot) | form changes of species we do not offer | structure loot, raid-den loot, Cobbleverse leaders' loot (weight 0), or nothing | cut; revisit if one of those species is added | none |
| P3 | LumyMon | 5 relics (`cryo`/`draco`/`metal`/`pebble`/`spark_relic`); legendary radars; `locator_chip`; most of the 188 | radars point at legendary structures that are not generated; relics have **no recipe that uses them** (VERIFIED: none in jars or enabled DPs) | worldgen type ores; Hoenn/Johto/Sinnoh content | cut; harmless | none |
| P3 | Legendary Monuments | Galar particle chain, Distortion World blocks, griseous keys | Eternatus radar, Galarian torch, Giratina's dimension | Galar particle ore is worldgen-only; Distortion blocks live in its dimension | cut unless Eternatus/Giratina are planned | none |
| P3 | TMCraft | blank eggs/books/stars; egg, tutor and star move items (932 each) | recording egg/tutor/star moves | no recipe and no loot in any jar or DP; `MoveTutorTable` and `PokemonBreederTable` classes exist and **may** make them (UNKNOWN) | experiment: craft both tables, see what they accept | one in-game check |

---

## 2. What we depend on

| Dependency | State | Evidence |
|---|---|---|
| **Mega Evolution** (players) | **Supplied, in staging, never seen**: bracelet at Fenhide's counter; raw stones from the seven gulch farms (15% outer, 30% deeper, owner-only drop); three Cutters trade 2 raw + 1 diamond for a keyed stone, unlimited | `markets.json:187`, `gulch_mine.json` `drops`, `cutters`; STATE "open-air Mega farms" |
| **TMs** | **23 leader TMs** are the only core supply; everything else rests on type gems (P1) | above |
| **Key Stone** | not needed: the sold bracelet is the key | `mega_showdown:mega_bracelet` recipe takes the Key Stone; buying skips it |
| **Badges** | Kanto badges and the badge box via `first_win_rewards`; the other 27 CobbleverseBadges items have no source and are not needed | `progression.json` |
| **Kubfu's scrolls** | supplied as data (`rewards.json`); a one-shot Scroll of Darkness can also roll in the observatory's dome chest | see note below |
| **Backpacks** | sold town by town; their recipes are disabled by our overlay so the shop is the only route | `markets.json` `recipe_overlay` |
| **Trainer card** (gate to every bonus route) | one Mart clerk, data only | `traders.json` `stock_policy.trainer_card` |
| **Fossils** | Cobblemon's: the other sweep. Two Cobbleverse fossils are LumyMon items: Mewtwo (P2 above) and Type: Null (`fossilized_helmet`, bonus only from the ambient Rocket scientist); Type: Null is a mythical starter instead | DP-v31 `data/cobblemon/fossils/` |

**Kubfu note (VERIFIED, both jars).** Mega Showdown 1.0.2 ships its own
`data/cobblemon/species/generation8/kubfu.json`, overriding Cobblemon 1.8.0's. Both evolve by
`item_interact` with the scrolls, but **Cobblemon says `consumeHeldItem: false` and Mega Showdown says
`true`**. Which file wins depends on load order (UNKNOWN). If Mega Showdown's wins, each scroll is spent
on one evolution, so the research station must hand out one per Kubfu, not one per player.

---

## 3. Per mod

Counts: core-obtainable / items (model count, an upper bound). "Bonus" = reachable only through ambient
RCT trainers, the Nether or a one-shot donor.

| Mod | Core | Bonus adds | What is left, and whether it matters |
|---|---:|---:|---|
| Mega Showdown 1.0.2 | 149 / 339 | 64 | P1 Z and Dynamax; P2 Tera Orb, Red Orb, memories; P3 Key Stone, plates, orbs. Mega works through our data |
| TMCraft 1.4.19 | 205 / 4,686 | 1,550 | P1 gems; 2,796 egg/tutor/star items wait on the table experiment; 52 max/gmax TMs die with Dynamax |
| LumyMon 0.6.6 | 31 / 219 | 16 | our legendary items (feathers, dews, crown, shaderoot) are supplied by the research station; P2 DNA and locators; the rest is Hoenn/Johto/Sinnoh content and P3 |
| Legendary Monuments | 6 / 54 | 4 | the Ruinous four's seals are Nether-chest loot (consistent with "the Ruinous four stay Nether-generated"); Galar and Distortion content P3 |
| CobbleCuisine 2.0.1 | 95 / 178 | 54 | beans come from short grass, so the curries and cakes craft; the rest wait on Cobblemon worldgen ingredients (galarica nuts, tasty tail, saccharine) |
| Only Bottle Caps 1.5.0 | 2 / 15 | 0 | P2: gold only |
| CobbleverseBadges 1.3 | 13 / 40 | 0 | other regions' badges: not needed |
| Sophisticated Backpacks / Storage / Core | 55 / 64, 101 / 117, 0 / 3 | 0 | sold; the gaps are Chipped-compat, infinity and pump upgrades, disabled or creative |
| Waystones 21.1.37 | 53 / 60 | 0 | **the opposite problem**: waystones, sharestones, portstones and warp stones all **craft** (warp stone = amethyst + ender pearl + emerald), which bypasses "waystones only, gated by gym flags" (STATE, Navigation). Owner's call whether to disable those recipes |
| Cobbreeding 2.3.0 | 0 / 326 | 0 | all egg models; eggs are made by pasture breeding (code). Not a gap |
| Cobblenav 2.4.1 | 24 / 189 | 2 | navigators craft; the rest are colour/model variants |
| ZAMega 1.7.7 | 11 / 12 | 0 | 11 stones via the Cutters |
| Pokeblocks 1.4.0 | 1 / 325 | 0 | figurines and dolls: no recipe for a base doll, source UNKNOWN. Decoration we place; players cannot obtain it |
| CobbleFurnies 1.2 | 325 / 367 | 0 | apricorn and saccharine furniture need those planks (apricorn logs from grown trees: the other sweep); 32 "dark" chairs/stools have no recipe |
| Cozy Home, Carved Wood, Moar Concrete, VanillaBackport | 255/284, 285/312, 144/160, 0/98 | 0 | ominous/undead/glass variants, pale oak (VanillaBackport's pale garden is worldgen-only), 16 concrete textures, spawn eggs: decoration only |
| Handcrafted, Beautify, Rechiseled, Comforts, Iron Chests, Tom's Storage, Battle Positions, Fight or Flight, rctmod | all or all but one | 0 | fully craftable |
| Cobblemon Raid Dens | removed | | its loot (drives, rusted sword, Max items, tera shards, held items) has no source; already recorded |
| CobbleDollars | currency is a number, not an item | | not an obtainability question |

---

## 4. Recommendations, cheapest first

1. **Cut Dynamax by config** (`dynamax: false`). It is dead three ways (no wishing star, no max
   mushroom, no Power Spot) and a config line makes that honest instead of silent.
2. **Decide Z-Moves now**, because a reward already depends on them (`vr_raw_tear`). If out, `zMoves:
   false` and swap the crystal. If in, a per-player Z-Ring grant; two rare sand blocks cannot serve a
   co-op group.
3. **Give type gems a counter**, or stop relying on crafted TMs. This is the largest single break in the
   mods: the TM economy the pack ships is a gem economy, and the world has no gems.
4. **Sell the Tera Orb** (or glowstone), unless the Nether is in the game; it is the orb's only
   glowstone.
5. **Neutralise the nine LumyMon Kanto locator recipes**, as the gym maps already are.
6. **Hand form-change items with their species** (Red Orb with Groudon, memories with Silvally) or say
   in the species' record that the form is cut.
7. **Remove Ancient DNA from Giovanni's grant**, or add the Cloning Catalyst.

**Not built.** Each fix above sets a price, a gate or a scope decision (which gimmicks the campaign
keeps), so none is "obviously right" for an agent to make; all are one-file data or config edits once
decided.

## 5. Experiments this names

- TMCraft's Move Tutor and Breeder tables: do they make blank books, eggs and stars?
- Kubfu's scroll: consumed or kept (which `kubfu.json` wins)?
- A LumyMon locator used in our world: does it search, lag, or point past the border?
- An ambient RCT trainer for a card holder in plains or badlands: does one spawn at all in our biomes,
  and does its loot drop?
- `teraShardDropRate`: do shards drop from wild defeats under 1.8.0?
