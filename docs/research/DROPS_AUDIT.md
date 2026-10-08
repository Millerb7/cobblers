# Cobblemon drops: what our world drops, where to farm it, and what it does to the economy

**Status: AUDIT AND DESIGN ONLY (2026-10-08, escalated unit: the economy's arbitrage plus a design with no runnable
check).** Nothing is built and no data, config, world or server was changed. Inputs were read only: the offline
snapshot `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05` (102 jars, the global datapacks, its
`config/`), the vanilla 1.21.1 jar under `%APPDATA%/ModrinthApp/meta/versions/1.21.1-0.19.5/`, and this commit's
`data/` and `modpack/config/`. The machine-readable table is `docs/research/notes/drops-1.8.0.json` (every species
and form, every entry's effective rate, its ranch rate and its places in our tables). The site agent's per-species
drops page reads the jar directly; this JSON is not its source.

Labels follow `.claude/rules/research.md`: **VERIFIED** is read from a jar, a config or our data at the cited place;
**ASSUMED** is not; *relayed* marks a figure taken from another document and not re-measured here; **REASONED** is
design argument. Bytecode is cited as `Class.method` with javap offsets, in
`Cobblemon-fabric-1.8.0+1.21.1.jar` unless another jar is named.

---

## 0. The answer in short

1. **Drops roll on entity death, from any cause, for wild Pokemon only** (VERIFIED, section 2.2). A battle KO is the
   usual death, but environmental damage (fall, magma, drowning, lava) also kills a wild Pokemon and drops its table,
   and fightorflight lets a player's own Pokemon kill wild ones outside battle. Players cannot hit them
   (`playerDamagePokemon: false`). **Drops are therefore not bounded by battle time**, which is the one fact the
   economy has not priced.
2. **The percentage in the species file is not the drop rate.** `amount` is a number of passes and each pass takes the
   first entry that rolls; a 5% entry behind a 100% one on a six-pass table drops 21-23% of the time (section 2.1).
   Every rate below is the exact effective one.
3. **Alphas defeated in battle drop type gems and Exp. Candies** through a Cobblemon callback none of our sweeps found
   (section 2.4). We author 288 alpha hearts covering all 18 types. **The P0 "no renewable type gem" gap is closed by
   battle**, and so is the source of Exp. Candies, which the level-cap design meant to cut. Both need owner calls
   (section 9).
4. **Pasture Loot keeps ONE entry of each roll, not the whole roll** (VERIFIED, section 2.6). The bank's ranch figures
   assumed the whole roll. They are right for single-entry tables (Gimmighoul, Archaludon) and about 2x too high for
   Thievul. **No item the bank buys can be ranched today:** all 13 bought drop items are on our blacklist (VERIFIED).
5. **What the ranch does do is collapse evolution-stone scarcity.** Every Eeveelution drops its own stone at 25% (one
   of 2 passes): a pastured Jolteon makes 3.74 Thunder Stones an hour, unattended. Espeon, Umbreon and Sylveon need no
   stone to evolve, so Sun, Moon and Shiny Stones start for free. Eevee entered the rosters on 2026-10-02
   (`data/spawns.json:18916`, commit `ba504705`), after `STONE_ECONOMY.md` recorded it as absent.
6. **The efficiency item already exists natively: the Custap Berry.** Used as Poke Rod bait or as a Poke Snack
   seasoning, it gives the attracted Pokemon the `drops_reroll` aspect, and that Pokemon's death rolls its drop table
   twice (VERIFIED, section 2.3). It comes from a four-step berry-mutation chain whose five inputs are all species
   drops. Nothing raises drops otherwise: no Looting, luck, Amulet Coin or Pickup hook exists in any jar.
7. **Economy verdict** (section 8): **emerald ($400) is the one drop that must not stay both dropped and bought.**
   Thievul at tier 4 pays $90.50 a KO in emeralds. **Meat is not "dormant"** as `data/bank.json:99` says: 61 live
   species drop raw chicken, which cooks to $20, from leg 1, so it belongs in the Produce Buyer's capped crate. Ores
   and diamond can stay. Everything else that drops is a crafting or evolution input and must never be bought.

---

## 1. Method

- **Tables.** Every `data/<ns>/species/**.json` and `species_additions/**.json` in every jar and global datapack zip
  of the snapshot (1,119 files): Cobblemon's 1,025 species, 929 with a `drops` block and 53 forms with their own; Mega
  Showdown's 53 replacement species files (identical drops except Kyurem, which loses its table) and 2 additions
  (Meltan, Virizion); ZAMega's 1 (Floette's form); COBBLEVERSE-DP-v31's 14 species files and 24 additions. An
  addition's `drops` replaces the base table. **No `cobblers_*` pack touches drops** (VERIFIED: none has a species or
  species_additions file). `data/mythical_starters.json` names drops only inside an evolution block (Ninjask's Shedinja
  shell), not a species table, and owned Pokemon never drop (2.2).
- **Rates.** The bytecode's algorithm (2.1) was computed exactly over every reachable selected set, and cross-checked
  against a 200,000-draw replica of the bytecode on Sableye, Onix, Flareon, Thievul and Pikachu (agreement within
  0.003).
- **Item validity.** An id counts as registered when some jar or the vanilla jar has its item model or lang key
  (15,008 ids).
- **Places.** Every `data/spawns.json` entry with weight above zero (1,920 entries, 695 species, `ambient` and hearts
  alike, Nether rings, Habitat pools, marine, waterway and placement sites). A species' **share** in a scope is the
  bucket weight (`server/config/mods/cobblemon/spawning/best-spawner-config.json:9-27`: world common 94, uncommon 5,
  rare 0.5, ultra-rare 0.2, boss 0.3; activated-habitat and Poke Snack 83.25 / 11.25 / 4.125 / 1.375) times its weight
  over its bucket's weight **among our entries in that scope**. It ignores biome and block conditions, and the
  inherited stock pools that still spawn in the 36 `signature_overlay_keep_defaults` sub-regions and the off-route
  wilderness (`data/spawn_suppression.json` `retain_defaults`). **It is an upper bound.** The spawn rate per hour has
  never been measured in this world, so per-hour figures are **ASSUMED**: 25 KOs an hour of a target that makes up
  10% or more of a scope's spawns.
- **Economy.** Bank prices are `tools/bank.py prices()` at this commit (41 items). The fight hour is
  `data/markets.json` `income_basis.leg_by_badge` divided by `effort_model.max_leg_hours` 4 (*relayed*, model
  unmeasured in game). The rules are `data/bank.json:237-238`: parity at the fight hour, the upper hour at 1.5x it.

Scratch scripts produced the JSON. They are not committed, as the 2026-10-05 sweep's were not. Re-running them needs
only the snapshot and the vanilla jar.

---

## 2. How drops work (VERIFIED from the bytecode unless marked)

### 2.1 The roll

`DropTable.getDrops(amount, pokemon)` (bytecode 7-351): N = `amount.random()` (an int in every file here; `IntRangeAdapter`
reads `"6"` as 6..6). The possible entries are those with `quantity <= N` that `canDrop`. Then, until N points are
spent or nothing is left:

- walk the possible entries **in file order**; take the **first** whose `nextFloat()*100 < percentage` (offsets
  220-245);
- a pass that takes nothing still spends one point (offset 264);
- a taken entry spends its `quantity` (default 1) and leaves the pool once taken `maxSelectableTimes` (default 1)
  times (the `removeIf` lambda).

`ItemDropEntry` defaults to percentage 100, quantity 1 and maxSelectableTimes 1 (`<init>` 5-17). Its count is
`quantityRange` (uniform and inclusive, so `"0-2"` can give nothing) or else `quantity`. No file in the pack sets
`quantity` or `maxSelectableTimes`. So **N is passes, not items**, and the order matters:

| Species (N) | Entry as written | Effective per wild death |
|---|---|---|
| Onix (6) | stone 100% 1-3, hard stone 2.5% | hard stone **11.9%** |
| Sableye (6) | amethyst 100% 0-2, then wide lens, diamond, emerald, roseli at 5% | diamond **21.7%**, emerald **20.8%** |
| Thievul (6) | sweet berries 100% 2-4, emerald 5% | emerald **22.6%** |
| Pikachu (3) | light ball, thunder stone, oran at 5% | thunder stone **13.6%** |
| Flareon (2) | fire stone 25%, charcoal 10% | fire stone **43.8%** |
| Duraludon (1) | metal alloy 75% | 75% |

The nominal "2.5-10% per KO" used by `OBTAINABILITY_VANILLA_COBBLEMON.md` row 14 understates every multi-pass table.

### 2.2 When drops happen

- `PokemonServerDelegate.updatePostDeath` calls `doDeathDrops` at the end of the death animation (offsets 436-443,
  `dropAfterDeathAnimation: true`, `modpack/config/cobblemon/main.json:7`).
- `doDeathDrops` (1-222) runs only when the Pokemon has **no owner** and the `doPokemonLoot` gamerule is true (it
  defaults to true; our world's value was not read, ASSUMED). It **drops the held item first**, then the entity's or
  form's table, then a **second full roll if the forced aspect `drops_reroll` is set** (offsets 136-166), and posts
  `LootDroppedEvent` with the killer.
- **Nothing checks the cause of death.** `PokemonEntity.isInvulnerableTo` (`method_5679`) refuses damage while the
  Pokemon is in battle, in a beam, and from a player when `playerDamagePokemon` is false (`main.json:71`, false), and
  otherwise defers to vanilla. **Fall, drowning, fire, lava, magma and cactus kill wild Pokemon, and those deaths
  drop.** Lava and cactus also destroy the items, which land `on-entity` (`main.json:6`). fightorflight sets
  `suffocation_immunity: true` (`server/config/mods/fightorflight.json5:189`).
- **fightorflight:** player Pokemon defend proactively (`:167`), can be commanded with the Poke Staff (`:303`), and
  earn 0.25x EXP for out-of-battle kills (`:177`). A kill by a player's Pokemon is an entity death, so it drops. That
  such a kill is common in play is ASSUMED.
- The **battle KO path** itself (a fainted wild Pokemon's entity dies) is the standard Cobblemon behaviour. The death
  to drop path is VERIFIED; the step from faint to entity death was not traced (ASSUMED).
- **Wild battles pay no CobbleDollars** (`modpack/config/cobbledollars/common.json:3`,
  `earnCobbleDollarsFromWildPokemon: false`). Drops are the only income from wild Pokemon, and only through the bank.

### 2.3 `drops_reroll`: the native drop multiplier

- `data/cobblemon/spawn_bait_effects/berries/custap_berry.json`: `{"type": "cobblemon:drops_reroll", "chance": 1.0}`.
  It is the only bait with that effect (VERIFIED: the string appears in no other data file).
- **Fishing:** `FishingSpawnCause.affectSpawn` applies `SpawnBaitInfluence`, whose effect function
  `FishingSpawnCause$Companion.saveDropsReroll` adds the aspect (ldc at 22).
- **Poke Snacks:** `PokeSnackSpawnerFactory` builds a `SpawnBaitInfluence` from the snack's bait effects, and
  `tags/item/recipe_filters/bait_seasoning.json` admits `#cobblemon:berries`. So a Custap-seasoned snack should mark
  its spawns (VERIFIED by code path; not seen in game). A snack has a `bites` property of 0-8, spawns 1 Pokemon a
  bite within radius 8, and waits 2 random ticks between spawns (`PokeSnackBlock` static init;
  `PokeSnackBlockEntity` constants). That is about 9 spawns over roughly 20 minutes at `randomTickSpeed` 3 (REASONED
  from vanilla random-tick odds). **It is consumable, not a spawner.**
- **Pasture Loot ignores it:** the mod calls `getDrops` directly (2.6).

### 2.4 Alpha rewards: the gem and candy source nobody had found

`data/cobblemon/callbacks/battle_fainted/pokemon_alpha_drops.molang`: when a **wild alpha faints in battle** it spawns
`cobblemon:alpha/alpha_rewards_tier{1..4}` (tier 2 at level 31, 3 at 51, 4 at 66), then **two independent 50%
rolls**, one per type slot (a mono-type uses its type twice), of `alpha/types/<type>_rewards_tier{1|2}` (tier 2 at
51). From the loot tables (VERIFIED, summarised in the JSON's `alpha_rewards`):

| Table | Contents |
|---|---|
| tier 1 (L<31) | 1 roll: Exp. Candy XS 56% (1-3), S 33% (1-2), M 11% |
| tier 2 | 1-2 rolls: S 44% (1-3), M 39% (1-2), L 17% |
| tier 3 | 1-2 rolls of M/L, plus one roll of the six EV candies (71%, 1-2) |
| tier 4 (L66+) | 2-3 rolls: L 39%, XL 50%, **Rare Candy 11%**; plus 1-2 EV-candy rolls |
| `<type>` tier 1 / 2 | 75% **that type's gem** (1-2 / 2-3), 25% its resist berry |

So **one alpha KO yields 1.125 gems below level 51 and 1.875 at 51 or above** (mono-type: all of its type; dual-type:
half each). The callback fires on `battle_fainted`, so **only battle KOs pay it**: no out-of-battle kill and no ranch
does. Our 288 alpha hearts (`data/spawns.json`, `"alpha": true`; compiled as `alpha=true` by `tools/compile_spawns.py`)
cover every type, most first at tiers 1-4:

| Type | Earliest alpha (level, place, bucket) | Most frequent alpha (share of that scope) |
|---|---|---|
| bug | Metapod L7 Pallet Meadows, common | Spidops, Glacier Foot Fields 15.7% |
| fire / flying | Growlithe L10 South West Fields; Butterfree L10 Route 1 maze | Fletchinder, North Shore Downs 15.7% |
| grass / poison | Oddish L9 Route 1 maze, uncommon | Sawsbuck, Northgate East 15.7%; Haunter, Wedge North 13.4% |
| water | Staryu L9 West Shore, uncommon | Seismitoad, Marshy Marsh 10.4% |
| rock / steel / dragon | Graveler L25 Mt Clay; Duraludon L24 Tri Peaks | Lycanroc, Mt Clay 13.4%; Duraludon 13.4% |
| psychic / ice | Lunatone L25 Mt Vessu; Jynx L30 Merian Cirque | Abomasnow, North Pine Isle 15.7% |
| ground | Diggersby L20 Viltri Plateau | Piloswine, Frostpeak 15.7% |
| normal / fairy / electric / fighting / dark / ghost | L15, L6, L11, L26, L30, L38 | Sawsbuck 15.7%; Shiinotic (Nether) 10.4%; Heliolisk 0.6%; Toxicroak 10.4%; Houndoom (Nether) 13.4%; Haunter 13.4% |

Stock alpha herds (the `boss` bucket, 0.3% of world spawns, 396 inherited pool files) also hold a gem as their held
item (for example `0003_venusaur_alpha.json`, `held_item=cobblemon:grass_gem`). They live wherever inherited pools are
not suppressed. Twenty-nine of our alpha hearts carry 5% held items.

### 2.5 Mega Showdown

`CobbleEvents.dropShardPokemon` listens to `LootDroppedEvent` and adds a Tera Shard of the Pokemon's Tera type at
`teraShardDropRate` 10% (and Stellar 1%) (`config/mega_showdown/config.json:14-15`). It adds no other drop, and no Mega
Showdown item raises drops.

### 2.6 Pasture Loot 1.0.5 (`PokemonPastureBlockEntityMixin.lambda$tick$0`)

Each tick, for each tethered, non-fainted Pokemon: with probability `drop_chance_per_minute / tick_per_minute`
(0.15/1200, `modpack/config/PastureLoot.json:2-3`), it rolls the form's table with `getDrops`, **takes ONE entry of
the result uniformly** (`List.get(random.nextInt(size))`, offsets 96-111), and drops it with its `quantityRange`
unless `item_blacklist` names it (offsets 136-158). **A blacklisted pick drops nothing; it is not re-picked.** That
makes 9 procs an hour per pastured Pokemon while the pasture's chunk ticks. Up to 16 Pokemon per pasture
(`main.json:83`); `pastureMaxPerChunk` is 4.0 (`:86`, its exact meaning not read). It ignores `drops_reroll`, alpha
rewards and Tera Shards.

**The correction:** `data/bank.json:49` ("If Pasture Loot pays a whole roll (ASSUMED)") and N145
(`docs/OVERNIGHT_REVIEW_2026-10-06.md:154`, "a pasture of 16 makes ~$13,030/h in emeralds (Thievul)") assumed the
whole roll. The real Thievul figure is 9 x 16 x 0.106 x $400 = **$6,110 an hour**. It is moot now that emerald is
blacklisted (`PastureLoot.json:48`). The single-entry figures (Gimmighoul's relic coins, N145's Archaludon iron,
$10,692 an hour) stand.

### 2.7 Broken ids: drops that drop nothing

`ItemDropEntry.drop` looks the id up and logs an error when it is absent, so these entries are selected (spending a
pass, or a ranch pick) and yield nothing. Ten ids in 17 tables (VERIFIED against the item registry):

- **COBBLEVERSE-DP-v31 additions:**
  - Helioptile and Heliolisk: `minecraft:sun_stone`. These are their only entries, so both drop nothing; the intended
    Sun Stone route is dead.
  - Spritzee: `minecraft:kebia_berry`, its only entry. It replaced Cobblemon's Fairy Feather drop.
  - Blipbug, Dottler and Orbeetle: `cobblemon:apple` and `minecraft:razz_berry`.
  - Pancham: `cobblemon:bamboo`. Pangoro: `cobblemon:string`.
  - Gulpin and Swalot: `minecraft:oran_berry`. Delcatty: `minecraft:raw_cod`.
- **Cobblemon's own:** Deoxys `minecraft:eye_of_ender` (the id is `ender_eye`); Entei and Ho-Oh
  `cobblemon:sacred_ash` (not an item in 1.8.0).

Fixing them is a species_additions file in our pack at the same path, the native datapack rung. Not built.

---

## 3. The drop table

`docs/research/notes/drops-1.8.0.json`: 938 species tables (forms included) and 256 distinct items. **219 items have
at least one dropper in our live tables.** Of the 695 species in our tables, 679 have a table. Twelve have none:
Porygon, Staryu, Starmie, Smeargle, Corphish, Crawdaunt, Rotom, Clauncher, Clawitzer, Pincurchin, Hydrapple and
Wiglett. Four are regional forms keyed by name in our data (Alolan Sandshrew and Vulpix, Galarian Corsola and Yamask),
whose form tables are in the JSON. Per species, the JSON gives each entry's `per_defeat`, `p_at_least_one`,
`ranch_per_hour` and blacklist flag, and every place we spawn it, with bucket, level, tier, heart, alpha flag and
share. Per item, it gives the bank price, the evolutions that need it, the number of recipes that use it, and every
dropper.

---

## 4. What matters

### 4.1 Evolution items (35 dropped items are some evolution's requirement; the rostered ones here)

"Per spawn" is per_defeat x share at the best place: the item's yield per Pokemon spawned there, an upper bound.
Leg is the scope's tier where it has one; VR is Victory Road (after badge 8).

| Item | Evolves (rostered) | Best farm | Per KO | Per spawn | Earliest source |
|---|---|---|---:|---:|---|
| Metal Coat | Onix, Scyther | Skarmory, the Crags sapling Habitat (L28-30) | 0.136 | 0.113 | same |
| King's Rock | Poliwhirl, Slowpoke | Hawlucha, Jungle East elder (L25-30) | 0.143 | 0.119 | Krabby, West Shore L6-12 |
| Razor Fang | Gligar | Gligar, South East Dunes desert sapling (L25-30) | 0.094 | 0.078 | Gligar, Mt Clay (rare) |
| Razor Claw | Sneasel | Weavile, Nether deep icerend | 0.185 | 0.174 | Kabuto, Arrow Lake (uncommon, L18-28) |
| Reaper Cloth | Dusclops | Dusknoir, Wedge South leg 8 | 0.249 | 0.035 | Duskull, Route 1 mansion |
| Protector | Rhydon | Rhyperior, Nether deep | 0.190 | 0.080 | Rhyhorn, Mt Clay (uncommon) |
| Magmarizer | Magmar | Magmortar, VR slagworks | 0.249 | 0.057 | Magmar, Great Crater L43-53 |
| Dragon Scale | Seadra | Kingdra, VR drowned | 0.410 | 0.045 | Horsea, Windward Shallows |
| Prism Scale | Feebas | Finneon, North West Coast leg 3 | 0.068 | 0.007 | same |
| Deep Sea Tooth / Scale | Clamperl | Basculin, Peak Pond Hollow / Chinchou, Driftmouth | 0.09 / 0.05 | 0.019 / 0.021 | Carvanha L20 / Luvdisc (rare) |
| Oval Stone | Happiny (not rostered) | Blissey, gym 6 training ground | 0.188 | 0.039 | Exeggcute, Viltri's Path L13 |
| Black Augurite | Scyther (Kleavor) | Gigalith, Nether deep | 0.357 | 0.067 | Roggenrola, Mt Clay L20 |
| Peat Block | Ursaring | Teddiursa, Ursaluna den outskirts Habitat | 0.116 | 0.097 | Teddiursa, Route 1 maze (rare) |
| Sweet / Tart / Syrupy Apple | Applin | Applin, Old Orchard rows Habitat | 0.12 / 0.10 / 0.08 | 0.10 / 0.08 / 0.06 | Applin, Route 1 maze L6 |
| Metal Alloy | Duraludon | Duraludon, Tri Peaks heart alpha | 0.750 | 0.101 | same |
| Dark Oak / Oak sapling | Grotle's forms | Shiftry / Turtwig | 1.5 / 1.0 | 0.18 / 0.008 | Seedot L8 |
| **Electirizer** | **Electabuzz** | Electivire, Arrow Creeks (uncommon) | 0.344 | **0.0019** | Electabuzz, Arrow Creeks (0.0006) |
| **Auspicious / Malicious Armor** | **Charcadet** | Armarouge / Ceruledge, Plateau East and Nether deep (rare) | 0.178 | **0.0004** | rare only |
| Upgrade | Porygon | **no live dropper** (Porygon2, End stock pool only) | | | sold at our counters (`data/markets.json`) |
| Dubious Disc | Porygon2 | **no live dropper** (Porygon-Z, End stock) | | | sold at our counters |

### 4.2 Evolution stones

| Stone | Live droppers (best) | Per KO | Ranch per hour (one pastured) |
|---|---|---:|---|
| Thunder | Pikachu, South West Fields leg 1, common | 0.136 | Jolteon **3.74**; Pikachu 1.11 |
| Moon / Sun | Lunatone / Solrock, Mt Vessu leg 3, heart alpha | 0.098 | Umbreon / Espeon **3.74** (both evolve by friendship, no stone); Clefable 2.01 |
| Dusk | Aegislash (Nether deep); Litwick line from the Route 1 mansion | 0.38 | Chandelure 1.41 |
| Dawn | Gardevoir and Gallade, VR raw tear; Froslass | 0.41 | Gallade 1.46 |
| Shiny | Togepi only, Shrew Lake, **rare** (0.0002 per spawn) | 0.071 | Sylveon **3.74** (evolves by affection, no stone) |
| Fire / Water / Leaf / Ice | **none live** (Eeveelutions, the elemental monkeys, Galarian Darmanitan) | | Flareon / Vaporeon / Leafeon / Glaceon **3.74** each |

Every Eeveelution's table is one entry: its stone at 25% over 2 passes (VERIFIED, JSON). **Pasture Loot does not
blacklist any stone.** One Eevee (South West Fields, rare, L10-14, leg 1) and either 2,100 at Steepside
(`OBTAINABILITY_SWEEP_2026-10-05.md:71-72`, *relayed*) or no stone at all makes a permanent stone ranch: about 90 a
day per Pokemon, against the whole campaign's demand of about 120 for four completionists
(`docs/mechanics/STONE_ECONOMY.md:338-339`, *relayed*). The bank refuses stones, so this prints no money. What it
does is make the mining faces, the Assayer and the counters' stone lines pointless after the first stone.

`STONE_ECONOMY.md:331` ("Fire: none") and `:336` ("Eevee is still absent from the rosters (VERIFIED: no `eevee`
row)") are both stale. Eevee, Growlithe and Kanto Vulpix are live today.

### 4.3 Items the bank buys that species drop

All 13 are on our Pasture Loot blacklist, so **no ranch sells to the bank** (VERIFIED: bank prices intersected with
dropped, non-blacklisted ids is empty). But wild deaths have no blacklist:

| Item ($) | Live droppers | Best $ per wild death, and where |
|---|---:|---|
| emerald (400) | 2 | **Thievul $90.50**, North East Downs, tier 4, common 15.7%; Sableye $109 (emerald and diamond), ultra-rare in the Route 1 mansion, uncommon in the Nether bastion rings |
| diamond (120) | 2 | Carbink $17, Rift south-west arm, tier 9, common; Sableye as above |
| iron ingot (9) | 1 | Archaludon $74 (1-32 ingots at 50%, a Cobbleverse addition), the Victory Road Habitat pools, uncommon |
| raw iron (8), coal (4), raw copper (2), redstone (2) | 16 / 4 / 4 / 2 | $12, $6, $3, $3 at most (Aggron and Klinklang in VR, Coalossal in the Rift, Gigalith) |
| chicken, beef, porkchop, mutton, rabbit (10; cooked 20) | 61 / 3 / 7 / 7 / 5 | **leg 1:** Pidgey (chicken 1.0, 20.9% of Pallet Meadows), Wooloo and Mareep (mutton 1.5): $15-30 a KO cooked. Miltank $20 raw (Drovers' Hollow fold, 55%) |

### 4.4 Materials the sweeps marked as gaps, and drops that close them

| Material | What needs it | Drop route (VERIFIED tables, our places) |
|---|---|---|
| **Type gems (18)** | 805 TM recipes; the Griseous Orb; FishingNav | **Alpha KOs in battle**, every type (2.4). Species drops: only Virizion and Okidogi, neither obtainable |
| **Exp. Candies, Rare Candy** | levelling | Alpha KOs (candies from level 1; Rare Candy only from alphas at L66+, the Nether deep rings) |
| Dragon's breath | Ability Capsule by brewing | Dratini (rare, 0.007 per spawn), Dragonair heart alpha (uncommon); ranch Dragonair **6.8 an hour** |
| Ender pearl | Link Cable, eyes | 13 live droppers; Abra at Pallet Meadows (rare) to Gardevoir in VR (0.34 per spawn); ranch Alakazam 9.4 an hour |
| Blaze powder | brewing fuel (not the stand) | 16 live; Litleo at North Shore Downs, uncommon; Charizard in VR 0.34 per spawn |
| Amethyst shard | Blank TM, tinted glass | Glimmora at the Rift (0.27 per spawn), Sableye; ranch Glimmora 7.8 an hour (it left the bank, `data/bank.json` buys_removed) |
| Heart of the Sea, nautilus shell, prismarine | conduit | Lapras (rare, 0.002 per spawn); Omastar at Arrow Creeks (0.10); Horsea at the station pool (0.42) |
| Echo shard | recovery compass | Poipole at the Dawn/Dusk towers (rare); ranch Poipole, a mythical-starter option, **13.5 an hour** |
| Nether star | beacon | Groudon's whole table (1 a death); ranch **9 an hour** once caught (`data/legendaries.json`, gated at 8 badges, *relayed* from `DUNGEON_PLACEMENT.md` Q4) |
| String, slime, leather, feather, bone, spider eye, ink, egg, honeycomb, phantom membrane, scutes | vanilla crafting whose mobs are all on the mobsbegone blacklist | all have common live droppers (JSON). Habitat pools make several near-pure: feathers and chicken at the elders (83%), leather and beef at Drovers' Hollow (55%) |

**Still no drop route:** gunpowder (Voltorb and Electrode are only in the inherited overworld pools, not our tables);
blaze rod, ghast tear, wither skull, glowstone, quartz, nether wart, pink petals, sculk, cobweb, wind charge and breeze
rod; fossils; mint leaves and seeds; Ability Capsule, Ability Patch and PP Up (Virizion and Okidogi only); Whipped
Dream and Sachet; the Fire, Water, Leaf and Ice Stones by hunting.

### 4.5 Drop-only items

Cobblemon items that **no recipe makes and our data never hands out**, so a drop (or an alpha reward) is the only
route: Auspicious and Malicious Armor, Black Augurite, Syrupy Apple, Light Ball, Lucky Egg, Quick and Metal Powder
(Ditto, ultra-rare), Medicinal Leek (Farfetch'd; 18 recipes), Black Sludge, Shed Shell, Smoke Ball, Grip Claw,
Sticky Barb, Absorb Bulb, Mental Herb, Quick Claw, Lagging Tail and Float Stone. Add the type gems and Rare Candy
(no recipe; alpha loot only). Add also the 33 berries that drops seed: berry trees are worldgen, `data/traders.json`
sells only the six EV berries, and `data/rewards.json` hands out Oran, Pecha and Sitrus once. In vanilla's namespace, every mob material in 4.4 is drop-only, because MobsBeGone removes its mob.

---

## 5. The obtainability sweep, cross-referenced

**Did it look at drops?** Yes, as tier B: "drops of species `data/spawns.json` names (684 rostered; Pasture Loot farms
them)" (`OBTAINABILITY_SWEEP_2026-10-05.md:39`). It asked whether a dropper is rostered. It did not ask:

- **at what rate.** It used the nominal percentage (`OBTAINABILITY_VANILLA_COBBLEMON.md` row 14: "2.5-10% per KO");
- **how rare the dropper is.** Every rostered dropper counted, so the Electirizer and the Charcadet armours (0.0019
  and 0.0004 per spawn) read as reachable;
- **whether the id is real** (2.7);
- **what the ranch does with stones** (4.2) or with any item the bank does not buy;
- **the alpha callback.** Tier F says "Cobblemon alpha rewards ... The alpha trigger was not found in the jar"
  (`OBTAINABILITY_VANILLA_COBBLEMON.md:65`). It is `callbacks/battle_fainted/pokemon_alpha_drops.molang`;
- **non-battle deaths** (2.2).

| Sweep row | Status with drops |
|---|---|
| P0 type gems ("NC: bastion ... F: alpha rewards", `:148`) | **Closed by battle**: our own 288 alpha hearts, every type, from leg 1 (2.4). `DUNGEONS.md:263` and `ITEM_ROUTES.md:362-363` ("nothing in our world drops them") are wrong |
| P0 fossils, P0 mint seeds | Not closed: no table drops either |
| P1 Ability Capsule | Not by a drop (Virizion and Okidogi only). The brewing route's dragon's breath is farmable; the stand's blaze rod is still NC |
| P1 Exp. Candies, Rare Candy (`:155`, "cut deliberately") | **Not cut: alphas hand out Exp. Candies on every battle KO**, and Rare Candy from L66 alphas |
| P1 brewing stand (blaze rod) | Not closed |
| P2 Dubious Disc, Upgrade | Not by a drop (no live dropper; Porygon has no table). Closed by our counters |
| P2 gunpowder (`OBTAINABILITY_VANILLA_COBBLEMON.md` row 16) | Only through inherited Voltorb pools in the wilderness (ASSUMED reachable) |
| Row 14 rostered evolution items | True, but **Electirizer and the two armours are effectively unobtainable** by hunting (6.2) |
| Row 8 amethyst | True: Glimmora and Sableye; the ranch is unattended (already out of the bank) |

---

## 6. Farming: where to go, and what should exist

### 6.1 Where a player farms (best place first, the earliest leg in brackets)

The ASSUMED rate of 25 KOs an hour applies only where the target is 10% or more of the scope. Elsewhere, scale it by
the share.

| Drop | Go to | Yield |
|---|---|---|
| Thunder Stone | South West Fields, Pikachu (leg 1) | 0.018 per spawn, ~3 an hour |
| Moon or Sun Stone | Mt Vessu, Lunatone and Solrock alphas (leg 3), which also drop psychic, rock and fire gems | 0.012 per spawn each |
| Metal Coat | the Crags sapling Habitat, Skarmory 83% (L28-30) | ~3.4 an hour |
| King's Rock | the Jungle East elder, Hawlucha (L25-30) | ~3.6 an hour |
| Peat Block | the Ursaluna den outskirts, Teddiursa | ~2.9 an hour |
| Apples (Applin's three) | the Old Orchard rows, Applin 83% (L43-53) | ~3, 2.4, 1.9 an hour |
| Ender pearl, blaze powder, Dawn Stone | Victory Road's raw tear and slagworks pools | 0.34, 0.34 and 0.09 per spawn |
| Type gems | the 63 common alpha hearts (2.4); Frostpeak, North Pine Isle, Northgate East and Glacier Foot Fields at 15.7% alpha | ~1.1-1.9 gems per alpha KO |
| Meat and leather | Pallet Meadows (leg 1); Drovers' Hollow fold (leg 6-8) | 1-2 a KO |
| Feathers and chicken | any elder bird pool (83%) | 1 a KO |

**A species that is rare everywhere still becomes farmable once caught once:** Pasture Loot makes its drops at 9 picks
an hour, so rarity gates the first individual and nothing after it. The exceptions are blacklisted items and
everything the battle-only alpha callback pays.

### 6.2 Effectively unobtainable by hunting (under 0.005 per spawn at the best place, needed by a live evolution)

| Item | Best per spawn | Data-only fix (Cobblemon native rung) |
|---|---:|---|
| Electirizer | 0.0019 | an Electabuzz heart at common or uncommon on the Arrow Creeks power line, or in the Night Shift mine (6.3) |
| Auspicious / Malicious Armor | 0.0004 | an Armarouge and Ceruledge heart (uncommon) on Plateau East; or a counter line each, priced as an evolution item |
| Shiny Stone | 0.0002 | none needed: our counters sell it, and Sylveon ranches it |
| Heart of the Sea | 0.0023 | low priority (a conduit); Lapras at Driftmouth is rare |
| Dragon's breath | 0.0069 | acceptable: one Dratini caught ranches it |

### 6.3 Purpose-built farms

**Most drops already have one. The Habitat pools are farms:** an elder, a sapling or a site pool holds one species at
83% of its spawns (`activatedHabitatBuckets` common 83.25), and several sit on exactly the drops that matter: Skarmory
(Metal Coat), Hawlucha (King's Rock), Teddiursa (Peat Block), Applin (apples), Gligar (Razor Fang), the Lopunny
cellar's Buneary, and Drovers' Hollow's Miltank and Tauros. **Recommend no new place for those.**

**One justified purpose-built farm: the two drops a rostered evolution needs that no place supplies** (Electirizer;
the Charcadet armours). The cheapest form is a heart in `data/encounter_design.json` (data only, rung 1). Only if the
owner wants it to be a place, give it to the dungeon design as a **fourth leg kind, the den**: one natural Habitat
Block room in the pocket (ReplaceSpawns, EXP-021), whose pool is the run's signature dropper at uncommon, KO'd in
battle (REASONED; the leg kinds are `DUNGEONS.md:170-195`):

- **Night Shift** (dungeon 1, 0 badges): the mine's powerhouse holds Electabuzz and Electivire, for the Electirizer
  and redstone. It fits the theme's "the lamps down there are still lit".
- **The Temple Calendar** (dungeon 5): Armarouge and Ceruledge, sun and moon, for the two armours.

The den obeys the dungeon reward rule as written (`DUNGEONS.md:250-258`): neither item is bought or sold. Its yield is
bounded by the run's lockout, and the seam leg keeps the mining.

---

## 7. The efficiency item

**What the pack already offers** (each VERIFIED by reading the classes that roll drops):

| Candidate | Exists? |
|---|---|
| Looting on a weapon | **No effect possible:** players cannot damage Pokemon (`playerDamagePokemon: false`), and `getDrops` and `ItemDropEntry.drop` read only `Random` and the entry: no enchantment, attribute or luck call |
| Luck potion or luck attribute | **No:** no reference in the drop classes |
| Amulet Coin or a similar held item | **No:** the string `amulet_coin` is in no jar, datapack or config of the snapshot |
| Pickup | **No loot generator:** `PickUpItemTask` is AI behaviour (a Pokemon picks up a ground item) |
| Mega Showdown, other addons | **No:** Tera Shards only (2.5). `cobblemon-battle-extras`, `MoreCobblemonTweaks` and `capturexp` have no drop hook (no reference to `DropTable` or `LootDroppedEvent` outside Cobblemon, Mega Showdown, Pasture Loot and Cobblenav's read-only spawn data) |
| Pasture Loot options | server-wide `drop_chance_per_minute` and the blacklist only |
| **Custap Berry** (`drops_reroll`) | **Yes: Cobblemon native.** As Poke Rod bait, every fished Pokemon (chance 1.0); as a Poke Snack seasoning, each of the snack's ~9 spawns. **Each marked Pokemon's death rolls the table twice**: x2 expected drops. The held item, alpha rewards and Tera Shards are not doubled |
| Poke Snack (any) | raises rare to 4.125% (8x the world's 0.5%) and ultra-rare to 1.375% (7x): **the native answer to "rare everywhere"** |

**So nothing needs inventing.** Where the Custap Berry sits (all VERIFIED in the jar's `berries/*.json` mutation
tables):

- **What it needs:** Pecha x Persim gives Mago; Mago x Nanab gives Magost; Magost x Tanga gives Watmel; Watmel x
  Chilan gives Custap.
- **Every input is a drop:** Chilan from Pidgey (2.5% per pass, Pallet Meadows, leg 1); Nanab from Fidough (leg 1);
  Tanga from Spoink (leg 1) and Exeggcute (leg 2); Pecha (40 droppers, and a `data/rewards.json` grant) and Persim
  are common drops.
- **None of the chain's berries is sold:** `data/markets.json` sells no berry, and `data/traders.json` carries only
  the six EV berries (Pomeg to Tamato). The bank buys none (`afk_rule.groups` berries).

The gate is therefore **time and know-how**, four generations of berry growth, not money. It is a **mid-game
investment** (REASONED: reachable from gym 2-3, used from then on) that **multiplies effort, never AFK**: Pasture Loot
ignores the aspect, and both the bait and the snack need a player there.

**Recommendation:** no shop line and no new item. Give the chain a hint (a herbalist's dialogue line at
Steepside or Greenhollow). The cost is one dialogue line. If the owner wants a sold version anyway, sell **one Custap
Berry** (a tree once planted) at a gym 6+ counter, at or above one leg-7 fight hour (~$11,000, *relayed* income
model): a late convenience, because the tree is renewable.

**If a held or worn item is wanted later** (the owner's "held, worn or carried"): the native lever is the forced
aspect itself. A `pokemon_entity_spawn` callback that adds `drops_reroll` while a nearby player carries a token would
sit on the datapack-callback rung, which we already ship (`cobblers_dialogue/.../callbacks/starter_chosen`,
`cobblers_lopunny_house/.../player_tick_pre`). Whether Molang can set a forced aspect is **not verified**
(experiment X4). No mod is needed.

---

## 8. What drops do to the economy

The rule the bank enforces is `data/bank.json:81-108`: buy nothing an unattended farm makes. On top of that, gathering
pays at parity with the fight hour, and its upper hour at 1.5x (`:237-238`). The fight hours (*relayed*, model B / 4h),
leg 1 to 8: **$1,008, 1,144, 2,492, 4,104, 5,358, 8,427, 11,050, 17,126**.

Drops reach the bank by four routes, at four speeds:

| Route | Bound | Status |
|---|---|---|
| Battle KO | battle time; ASSUMED 20-30 an hour | effort |
| Battle KO with a Custap Berry | x2 | effort, needs the berry chain |
| Out-of-battle kill (a fightorflight Poke Staff, a defender, environmental damage the player causes) | spawn rate only; ASSUMED 60-120 an hour | attended, fast. **Never measured** |
| Unattended kill floor (spawns walk or are pushed onto magma or into a fall with hoppers below) and Pasture Loot | Pasture Loot: 9 picks an hour per Pokemon, VERIFIED. The kill floor: ASSUMED possible, **never tried** | AFK |

### 8.1 The AFK math, by item

| Item (bank $) | Worst case | $ per KO | KOs an hour to reach parity / upper | Verdict |
|---|---|---:|---|---|
| **emerald (400)** | Thievul, North East Downs, tier 4, 15.7% | 90.5 | 45 / 68 (leg 4 $4,104 / $6,156) | battle (10-25 Thievul an hour) is 22-55% of parity: fine. **Out-of-battle kills at 60+ break the upper hour. A kill floor breaks the AFK rule.** Plus Sableye at $109 (ultra-rare at leg 1) |
| **cooked meat (20)**, raw (10) | Pidgey, Wooloo, Mareep, Pallet Meadows, leg 1 | 20-30 cooked | 34-50 / 50-76 (leg 1 $1,008 / $1,512) | battle at 25: 50-74% of parity. **With Custap: at or past parity. Kills at 60+: 1.2-3.6x the fight hour, past upper. A kill floor breaks the rule** |
| iron ingot (9) | Archaludon, VR, uncommon 3.2% | 74 | 167 at VR ($49,341 / 4h, *relayed*) | fine: rare and late |
| diamond (120) | Carbink, tier 9, common | 17 | 500+ | fine |
| raw iron, coal, copper, redstone | VR, Rift and Nether | 3-12 | 700+ | fine |
| Pasture Loot of any bought item | | 0 | | closed: all 13 blacklisted (VERIFIED) |

### 8.2 Verdict per drop item

- **Sell at the bank (effort-bounded; price unchanged):** diamond, iron ingot, raw iron, raw copper, coal, redstone.
  Their drop yield per KO is small and late against the mining hour the prices were set on.
- **Must not stay both a drop and a $400 bank line: emerald.** Choose one:
  - **(a, recommended)** a `species_additions` file in our pack that re-authors Thievul's, Nickit's and Sableye's
    tables without the emerald (Carbink's and Sableye's diamond can stay). That is the Cobblemon-native data rung, at
    the namespace path, upstream untouched. The miner's emerald keeps its price.
  - **(b)** take emerald off the bank.
  - Either way, the barter villager's emerald use (EXP-055) is unaffected.
- **Move to the Produce Buyer's capped crate, off the bank:** chicken, beef, porkchop, mutton and rabbit, their
  cooked forms, and rabbit stew. `data/bank.json:99` keeps them as "dormant: their animals are on the mobsbegone
  blacklist and their items on Pasture Loot's". That misses the 61 live species that drop chicken, and the 7, 7, 5 and
  3 that drop mutton, porkchop, rabbit and beef. They are live income from leg 1. The Produce Buyer's allowance
  (`data/produce_buyer.json` `schedule`, campaign cap $3,600) bounds them whatever the kill rate. ECONOMY_OVERHAUL 2.2
  already names a "ranch goods x16" crate for this.
- **Crafting and evolution inputs only: never bought, at any price:**
  - every evolution item and stone (the bank already refuses stones);
  - type gems, Exp. and Rare Candies, Tera Shards;
  - dragon's breath, ender pearl, blaze powder, amethyst, relic coins (one pastured Gholdengo is 324 coins an hour);
  - berries, apricorns and apples;
  - feather, string, leather, bone, slime, gunpowder, honeycomb, phantom membrane, echo shard, nether star, heart of
    the sea, nautilus shell, prismarine, scutes, wool;
  - and every battle held item.

  Each is either unattended through Pasture Loot (4.2-4.4) or would be the first item a kill floor makes. The current
  bank buys none of them. Keep it that way, and add to `afk_rule` the reason "a wild death drops it" beside "a ranch
  makes it".
- **Pasture Loot blacklist additions (a config line each; owner's call, not cash):**
  - the ten evolution stones, which keeps the stone economy (4.2) and leaves battle drops as the effort route;
  - optionally relic coins, which make Gholdengo's 999-coin evolution trivial.
  - Exp. Candies and gems need nothing: no ranch makes them.

### 8.3 What the economy audit should add (for `test-author`; not written here)

`tools/bank.py ranch_drops` covers the ranch. **Nothing covers wild-death drops.** A check should name every bought
item that a live species drops, with its $ per KO and the fight hour of the earliest tier that drops it, and fail
when $/KO x 60 (ASSUMED out-of-battle kill rate) exceeds 1.5x that fight hour. Today it would name emerald (Thievul,
tier 4) and cooked meat (leg 1), and nothing else.

---

## 9. Open questions for the owner

1. **Emerald:** strip it from Thievul, Nickit and Sableye (a), or take it off the bank (b)?
2. **Meat:** off the bank and into the Produce Buyer's capped crate?
3. **Stones:** blacklist the ten stones in Pasture Loot, or accept Eeveelution stone ranches? Accepting them makes the
   faces, the Assayer and the stone counters early-game only.
4. **Alpha Exp. Candies:** keep them? Whether rctmod's level cap stops a candy from levelling past the cap is not
   known (X3). If it does not, every alpha KO is a cap bypass. Keep or neutralise the
   `alpha_rewards_tier*` tables? Overriding a loot table at its path is data.
5. **Alpha gems:** gems are renewable by battle now. Since TMs at counters are priced above the income gate
   (2026-10-09), should crafted TMs stay possible? The sweep's "none of the 3,596 TM recipes is craftable" has to be
   re-run with gems at B. Also, the dungeon's "gems are the spine" rationale (`DUNGEONS.md:262-265`) loses its
   exclusivity.
6. **The two near-unobtainable evolution items:** a data heart (Electabuzz; Armarouge and Ceruledge), counter lines,
   or a dungeon den leg?
7. **The Custap chain:** leave it to discovery with a hint, or also sell a tree late?
8. **The broken Cobbleverse ids** (2.7): fix them in our pack? Helioptile's Sun Stone is the only one with an economy
   effect, and it would add a Sun Stone dropper.

## 10. Experiments owed (none run)

- **X1. Non-battle deaths drop.** Kill wild Pokemon, on a disposable copy, by magma floor, fall and a fightorflight
  Poke Staff command. Confirm the drops and measure kills an hour at one spot with one player. This sets the 60-120
  in section 8.
- **X2. Pasture Loot as read:** one pick per proc and no re-pick on a blacklisted item, then about 9 an hour from a
  pastured Jolteon.
- **X3. Exp. and Rare Candy against rctmod's cap.**
- **X4. A Custap Poke Snack's spawns drop twice.** Also: whether a Molang callback can add a forced aspect.
- **X5. Alpha rewards in our world:** a heart alpha KO'd in battle drops candies and gems as tabled.

## 11. Disagreements found (for whoever owns each document)

| Document | Says | Actually |
|---|---|---|
| `docs/mechanics/STONE_ECONOMY.md:331`, `:336` | no Fire Stone line rostered; Eevee absent (VERIFIED) | Eevee (`data/spawns.json:18916`, since `ba504705`), Growlithe and Kanto Vulpix are live |
| `docs/research/OBTAINABILITY_VANILLA_COBBLEMON.md:65` | "The alpha trigger was not found in the jar" | `data/cobblemon/callbacks/battle_fainted/pokemon_alpha_drops.molang` |
| `OBTAINABILITY_SWEEP_2026-10-05.md:148`; `DUNGEONS.md:263`; `ITEM_ROUTES.md:362-363` | gems have no renewable source; nothing in our world drops them | alpha battle KOs, 288 hearts |
| `data/bank.json:99` | meats dormant | 61 or more live droppers |
| `data/bank.json:49`, `:286`; N145 | Pasture Loot pays a whole roll (ASSUMED) | one entry per proc (VERIFIED); multi-entry estimates about 2x high |
| `OBTAINABILITY_VANILLA_COBBLEMON.md:67-70`; `MINECRAFT_PLAY_LOOPS.md:118` | Pasture Loot's behaviour ASSUMED | VERIFIED from the mixin, except that it runs in our world |
| COBBLEVERSE-DP-v31 additions | Helioptile and Heliolisk drop Sun Stones, and seven more | ten ids are not items (2.7) |
