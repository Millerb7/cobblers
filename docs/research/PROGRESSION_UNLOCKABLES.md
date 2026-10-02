# What this pack can hand out a rung at a time

**Question.** Across every mod in the pack, what could a player unlock
incrementally as they travel — so they advance materially without ever building
a house, living out of a backpack that gets better, bought and upgraded in town
markets?

**Answered for:** the overlay mod set in `modpack/manifest/overlay.json`
(Cobblemon 1.8.0 target) over the Cobbleverse **1.7.42** snapshot in
`base-pack/cobbleverse/`.

---

## 0. Evidence basis, and the hole in it

**The mod jars are not on this machine.** Checked, all absent:

| Path | Result |
| --- | --- |
| `base-pack/cobbleverse/mods/` | does not exist (snapshot holds only `config/`, `licenses/`, `resourcepacks/`, `shaderpacks/`) |
| `modpack/mods/` | exists, contains `README.md` only |
| `C:/Users/wnd/Documents/cobblers-local/` | `README.md` and `kits/` only |

So **no `fabric.mod.json`, no `data/<ns>/recipe/*.json`, no `assets/**/lang/en_us.json`
was read.** Nothing in this document is a recipe read out of a jar. Every recipe
claim below is marked ASSUMED and is the single biggest gap in this audit; the
server tree was deliberately not touched (out of scope for this task).

What was read instead, and what each source actually proves:

| Source | Proves | Version it speaks for |
| --- | --- | --- |
| `base-pack/inventory/mod_inventory.json` (138 entries, jar-derived) | modid, version, environment, declared deps, and a `file_hints.has_recipes` boolean per jar | Cobbleverse 1.7.42 |
| `base-pack/cobbleverse/config/**` | real config keys and their shipped values | Cobbleverse 1.7.42 |
| `base-pack/cobbleverse/config/roughlyenoughitems/collapsible.json5` | **literal item ids present in the installed mod set** — the pack's own REI grouping index (~17k minecraft + ~16k modded entries) | Cobbleverse 1.7.42 / Cobblemon 1.7.3 |
| `modpack/manifest/overlay.json` | which mods our overlay keeps, replaces, removes | our target |

Two limits on the REI index, stated once and binding everywhere below:

1. It is a **grouping** config. An id appearing in it proves the item exists.
   An id *not* appearing proves nothing — `ironchest:` and `toms_storage:` have
   zero entries, yet both mods are installed.
2. It is the **1.7.42** index. Thirteen mods are version-replaced for Cobblemon
   1.8 in our overlay (`cobblemon`, `tmcraft`, `mega_showdown`, `obc`,
   `cobblenav`, `rctmod`, `rctapi`, `capture_xp`, `tim_core`, `cobbreeding`,
   `playerxp`, `zamega`, `fightorflight`). A 1.7.42 id is evidence the item
   existed then, **not proof it still exists under 1.8**.

**Gateability vocabulary** used throughout:

| Rating | Means |
| --- | --- |
| **EASY** | a recipe exists and a datapack can suppress or replace it; no code, no config |
| **MEDIUM** | config-only — server-wide, same for every player, needs a restart or reload |
| **HARD** | would need functions/commands fighting the mod, or is coded in |
| **NONE** | not gateable with what the pack has |

**The delivery channel is verified.** `base-pack/cobbleverse/config/global_packs.toml`
declares `[datapacks] required = ["datapacks/"]`, so a datapack we drop in the
instance's `datapacks/` folder loads globally for every world. That is the rung
every EASY item below sits on.

**One mechanism is ASSUMED and must be tested before the ladder is designed on
top of it:** that a later-loading datapack can make a mod's recipe not load
(the Fabric resource-conditions approach, `fabric:load_conditions`). It is
standard Fabric practice, it was **not** tested in this pack, and no existing
datapack in this repo does it — `modpack/datapacks/` contains only
`cobblers_height` (a dimension type). **EXP needed.** If recipe suppression
turns out not to work, every EASY rating below drops to NONE and the ladder has
to be built out of shops and given items instead.

---

## 1. The backpack: Sophisticated Backpacks

### 1.1 Which mod it is

| Field | Value | Source |
| --- | --- | --- |
| Name | Sophisticated Backpacks | `mod_inventory.json` |
| modid | `sophisticatedbackpacks` | `mod_inventory.json` |
| Version in snapshot | `1.21.1-3.23.4.3.106` | `mod_inventory.json` |
| Environment | `*` (both sides) | `mod_inventory.json` |
| Licence | GPL-3.0 (unofficial Fabric port) | `mod_inventory.json` |
| Hard dependency | `sophisticatedcore` `>=1.2.9.15 <1.22` (itself needs `forgeconfigapiport >=21.1.3` and bundles 12 nested `porting_lib` jars) | `COBBLEVERSE_COMPATIBILITY.md` lines 343-344 |

**It is in our overlay.** It appears in neither `remove`, `replace` nor
`server_exclude` in `modpack/manifest/overlay.json`, so the overlay inherits
the base pack's jar unchanged, on **both** client and server. Its 1.8 status in
`docs/research/COBBLEVERSE_COMPATIBILITY.md` is `LIKELY WORKING / PRESERVE FOR
BOOT`; it declares no Cobblemon dependency at all, so Cobblemon 1.8 is not a
risk to it. (VERIFIED: manifest + compatibility table.)

Its sibling `sophisticatedstorage` (`1.21.1-1.3.7.9.139`) and the shared
`sophisticatedcore` are also in the overlay. Storage is treated separately in
§2.8 because it is furniture, and furniture is the thing the owner wants the
player not to need.

### 1.2 Every tier and upgrade it has

**Six backpack tiers**, ids VERIFIED present in the REI index:

| Tier | Item id | Inventory slots | Upgrade slots |
| --- | --- | --- | --- |
| 1 | `sophisticatedbackpacks:backpack` (leather) | 27 | 1 |
| 2 | `sophisticatedbackpacks:copper_backpack` | 45 | 1 |
| 3 | `sophisticatedbackpacks:iron_backpack` | **81** (mod default 54) | **7** (mod default 2) |
| 4 | `sophisticatedbackpacks:gold_backpack` | **96** (default 81) | **8** (default 3) |
| 5 | `sophisticatedbackpacks:diamond_backpack` | 108 | **9** (default 5) |
| 6 | `sophisticatedbackpacks:netherite_backpack` | 120 | **10** (default 7) |

Slot counts VERIFIED from `base-pack/cobbleverse/config/sophisticatedbackpacks-server.toml`
lines 25-90; each block prints the mod's own default next to the shipped value,
which is how the deviations above are known.

**Finding, and it bites the ladder directly: Cobbleverse has already flattened
its own curve.** Iron jumps from 1 upgrade slot to **7** and from 45 to 81
inventory slots in one step. Everything after iron is a rounding error — gold,
diamond and netherite add 15, 12 and 12 inventory slots and one upgrade slot
each. As shipped, a four-rung ladder above iron has almost nothing left to give.
If the campaign wants six meaningful rungs, this file is ours to retune (it is a
config in the base snapshot; our overlay would ship its own copy under
`modpack/config/`, as it already does for `rctmod-server.toml`).

**Fifty-six upgrade items**, all ids VERIFIED in the REI index. They are the
real ladder, and they form tiers of their own:

- **The gate on all of them:** `sophisticatedbackpacks:upgrade_base`. Every
  upgrade is built from it. (ASSUMED — standard for this mod; recipe not read.)
  Suppressing that one recipe would gate every upgrade at once.
- **Basic -> advanced pairs** (12): `pickup_upgrade` / `advanced_pickup_upgrade`,
  and the same for `magnet`, `filter`, `deposit`, `restock`, `refill`,
  `feeding`, `compacting`, `void`, `tool_swapper`, `pump`, `jukebox`.
- **Stack upgrades, a numbered 6-rung ladder**:
  `stack_upgrade_starter_tier`, `stack_upgrade_tier_1` … `tier_4`,
  `stack_upgrade_omega_tier`. Config caps these at three per backpack:
  `maxUpgradesPerStorage = ["stack_upgrades|3", "jukebox_upgrades|1", "furnace_upgrades|1"]`
  (VERIFIED, line 12). There are also `stack_downgrade_tier_1..3`.
- **Portable workstations — the single most on-brief group in the whole pack**:
  `crafting_upgrade`, `anvil_upgrade`, `smithing_upgrade`, `stonecutter_upgrade`.
  These are literally "you do not need to go home".
- **Portable cooking**: `smelting_upgrade`, `smoking_upgrade`, `blasting_upgrade`
  and their `auto_` variants (capped `furnace_upgrades|1`).
- **Logistics and endgame**: `inception_upgrade` (backpacks in backpacks),
  `tank_upgrade`, `battery_upgrade`, `xp_pump_upgrade`, `everlasting_upgrade`,
  `infinity_upgrade`, `survival_infinity_upgrade`.

### 1.3 How a player obtains each tier as the pack ships

**Crafting, and nothing else.** This is the strongest finding in the audit,
because it means the entire supply is recipe-shaped and therefore ours. All
VERIFIED from `sophisticatedbackpacks-common.toml` and `-server.toml`:

| Possible source | Shipped value | Effect |
| --- | --- | --- |
| Vanilla chest loot | `chestLootEnabled = false` (common.toml) | no backpack is ever in a chest |
| Mobs spawning with one | `[server.entityBackpackAdditions] chance = 0.0` | never happens |
| Mobs dropping one | `backpackDropChance = 0.0`, `lootingChanceIncreasePerLevel = 0.0` | never drops |
| Entity loot list | `entityLootTableList = []` | empty |
| Crafting | recipes ship in the jar (`file_hints.has_recipes = true`) | **the only channel** |

So: tier 1 is crafted from leather, and each tier above is ASSUMED to be the
previous tier plus that metal (the mod's standard upgrade recipe shape) — **the
recipe files were not read and this must be confirmed against the jar.** The
practical consequence does not depend on the shape: there is exactly one tap,
and it is the recipe book.

The mob-drop path being off also means **nothing in the pack hands a player a
backpack tier behind our back.** (VERIFIED.)

### 1.4 Can we gate it

**Yes — EASY, with one caveat, and better than EASY if we use the shop.**

| Lever | Rung (CLAUDE.md preference order) | Rating | Evidence |
| --- | --- | --- | --- |
| Suppress a tier's recipe in our global datapack | datapack | **EASY** | delivery VERIFIED via `global_packs.toml`; suppression mechanism **ASSUMED, untested** |
| Sell the tier in a town market instead | configuration | **EASY, and preferred** | `cobbledollars/default_shop.json` is a per-item price list, VERIFIED (§2.1) |
| Retune what each tier is worth | configuration | **EASY** | `inventorySlotCount` / `upgradeSlotCount` per tier, VERIFIED |
| Cap upgrades per backpack | configuration | **MEDIUM** (server-wide) | `maxUpgradesPerStorage`, VERIFIED |
| Ban specific items from backpacks | configuration | **MEDIUM** | `disallowedItems = []`, VERIFIED |
| Per-player gate from an advancement | — | **NONE** | see below |

**Is there a config for tiers?** Yes, but only for *how good each tier is*
(`inventorySlotCount`, `upgradeSlotCount`), never for *who may have it*. There is
no `enabled` flag per tier, no unlock list, and no requirement expression
anywhere in either toml. (VERIFIED by reading both files end to end: 4 lines and
538 lines.)

**Does it read advancements?** **No evidence that it does, and no key for it.**
Neither config mentions advancements, permissions, or any gating predicate.
Treat "gate a backpack tier on an advancement" as **not supported**. Per-player
gating has to come from *not giving the player the item* — a shop that does not
stock it yet, or a reward not yet earned — not from the mod refusing it.

**What would a player see if a tier's recipe simply is not there yet?** ASSUMED,
and worth one minute of a boot test: the item stays registered, so it still
exists, can be `/give`n, can be sold by a merchant, and renders normally. What
disappears is the recipe — REI (`roughlyenoughitems`, in the overlay) shows the
item with **no recipe**, and the vanilla recipe book never unlocks it. There is
no "locked" affordance and no explanatory text: to the player it looks like an
item that cannot be made, which reads as a mystery rather than as a goal. **The
ladder must supply its own legibility** — a shop slot the player can see and not
yet afford says "later" far better than an absent recipe does.

**The clean shape this suggests** (a design observation, not a decision): remove
the metal upgrade recipes entirely and make every tier above leather a **market
purchase**. Then the tap is one JSON file of prices, the gate is money plus which
town the player has reached, and the player sees the whole ladder laid out above
them in the shop. That uses only existing configuration — rung 4 of the
preference order, no datapack and no code.

---

## 2. The rest of the pack, ranked by what the ladder can use

### 2.1 CobbleDollars — `cobbledollars` 2.0.0+Beta-5.1 — **EASY**, the market itself

This is the mechanism for the owner's "town markets are where that happens", and
it is pure config. `base-pack/cobbleverse/config/cobbledollars/default_shop.json`
(119 lines) is a list of named categories, each a list of `{item, price}`:

- *Cobble Ball*: `cobblemon:poke_ball` 400, the five coloured balls 400 each,
  `cobblemon:great_ball` 750, `cobblemon:ultra_ball` 1000, `cobblemon:luxury_ball` 4000
- *Potions*: `cobblemon:potion` 600, `super_potion` 900, `hyper_potion` 1600, `revive` 3000
- *Mob Drops*: `minecraft:egg` 250 … `minecraft:ender_pearl` 1600
- *Cards*: `rctmod:trainer_card` 500, `lumymon:store_card` 999

`bank.json` (323 lines) is the other side of the counter, including
`minecraft:elytra` at 25000, `cobblemon:relic_coin` 50 / `relic_coin_pouch` 475 /
`relic_coin_sack` 4500, and the full potion range at sell prices.
`common.json`: `earnCobbleDollarsFromNPC: true`,
`earnCobbleDollarsFromWildPokemon: true`, `cobbleDollarsIncomeMultiplier: 0.5`,
`playerDataSaveFrequency: 15`. All VERIFIED.

**Why it ranks first after the backpack:** a price list is the cheapest possible
ladder. Any item in the pack can be a rung simply by appearing in a shop, with
no recipe work at all, and the player can *see* the rung before reaching it.

**NOT VERIFIED, and it decides the design:** whether `defaultShop` is one global
shop shared by every merchant, or a fallback that per-merchant data (datapack or
NPC NBT) can override. A **per-town** stock list is what the ladder wants; a
single global shop would mean price is the only gate and geography is not one.
This is the highest-value open question in the audit. CobbleDollars 2.0 is a
beta; check its merchant data format before building on per-town stock.

### 2.2 TMCraft — `tmcraft` (overlay pins 1.4.19+1.8.0) — **EASY**, six clean rungs

The largest tier structure in the pack. **Six material grades x four forms**,
all 24 ids VERIFIED in the REI index:

`{copper, iron, gold, emerald, diamond, netherite}_blank_{disc, book, egg, star}`

and then 930 moves in each of four families: `tmcraft:tm_<move>` (930),
`tmcraft:tutor_<move>` (930), `tmcraft:egg_<move>` (930), `tmcraft:star_<move>`
(930) — 3,745 `tmcraft:` ids in the index.

**ASSUMED** (not read from the jar): that the blank's material grade determines
which moves it can imprint, with higher grades reaching stronger moves. The
*structure* is verified; the *semantics* are not. TMCraft ships no config file at
all (none in `base-pack/cobbleverse/config/`), so **everything here is
recipe-shaped** — which makes it EASY to gate and leaves nothing to tune.

**Why it ranks this high:** six grades of blank, obtained by crafting, is a
ready-made six-town ladder for move access, and move access is campaign power
rather than convenience. Note Cobblemon 1.8 also adds native TMs; whether the
two systems overlap or conflict is **NOT VERIFIED** and belongs to the Cobblemon
researcher, not here.

### 2.3 Waystones — `waystones` 21.1.37 — **EASY + MEDIUM**, the travel ladder. **WORLD-CRITICAL.**

Movement is the other half of "advance as you travel". 47 ids VERIFIED, and they
are already a ladder:

- **Stations**: `waystones:waystone` plus 9 material variants (`mossy_`,
  `sandy_`, `deepslate_`, `blackstone_`, `prismarine_`, `purpur_`, `end_stone_`,
  `mud_bricks_`, `red_nether_bricks_`); `waystones:warp_plate`;
  `waystones:*_sharestone` and `*_portstone` in 16 colours each.
- **Consumables and keys**: `blank_scroll`, `bound_scroll`, `return_scroll`,
  `warp_scroll`, `portal_scroll`.

Config (`waystones-common.toml`, VERIFIED) is unusually gate-friendly — it has a
small **requirement expression language**:

```
warpRequirements = [
    "[is_not_interdimensional] scaled_add_xp_cost(distance, 0.01)",
    "[is_interdimensional] add_xp_cost(27)",
    "[source_is_warp_plate] multiply_xp_cost(0)",
    "[target_is_global] multiply_xp_cost(0)",
    "[target_is_fleeting_memorial] multiply_xp_cost(0)",
    "min_xp_cost(0)", "max_xp_cost(27)",
    "[source_is_inventory_button] add_cooldown(inventory_button, 300)"
]
```

with `enableCosts = false`, `enableCooldowns = false`, `enableModifiers = false`,
`defaultVisibility = "ACTIVATION"`, `restrictedWaystones = ["PLAYER"]`,
`transportPets = "DISABLED"`, `transportLeashed = "ENABLED"`,
`scrollUseTime = 32`, `warpPlateUseTime = 15`.

`defaultVisibility = "ACTIVATION"` is already the ladder we want: a waystone
works only once the player has walked to it. **Travel is the unlock, with no
work from us.** The scroll items on top of that are recipe-gated (EASY), and the
cost/cooldown curve is config (MEDIUM). What the expression language gates is
**cost**, not **permission**, and its predicates are about distance and source,
not about the player — so it cannot express "this player may not warp yet".

**World-critical flags:** `chunksBetweenWildWaystones = 25` is worldgen, and
`has_worldgen` / `has_structures` are both true in the inventory. Our world is a
pre-exported WorldPainter map inside its border, so wild waystones in new chunks
are mostly moot — but an activated waystone is **persistent player world state**,
and `COBBLEVERSE_COMPATIBILITY.md` line 356 already says so. Removing or
replacing this mod after map development begins breaks saves. Principle 11
applies with full force.

### 2.4 Mega Showdown — `mega_showdown` (overlay pins 1.0.2) — **EASY on items, MEDIUM-to-NONE on mechanics**

The key-item ladder. VERIFIED ids include a single gate item per mechanic:
`mega_showdown:mega_bracelet` (plus 6 colours) and `mega_showdown:mega_ring` for
Mega Evolution; `*_z_power_ring` (Gladion, Hapu, Nanu, Olivia, Rocket variants)
and 20-odd `*ium_z` crystals for Z-moves; 19 `*_tera_shard` types plus
`stellar_tera_shard` and `tera_pouch_*` for Terastallization; character items
(`korrina_glove`, `lysandre_ring`, `may_bracelet`, `brendan_mega_cuff`,
`archie_anchor`, `maxie_glasses`); plus plates, memories and drives.

Config (`mega_showdown/config.json`, VERIFIED): `mega`, `zMoves`,
`teralization`, `dynamax` are **global booleans**, with
`teraShardRequired = 50`, `minBondingRequired = 200`, `teraShardDropRate = 10.0`,
`stellarShardDropRate = 1.0`, `powerSpotRange = 32`, `dynamaxAnywhere = false`,
`multipleMegas = true`, `outSideMega = true`.

So: **the mechanic cannot be gated per player (NONE)**, but the *key item* can be
(EASY) — withholding `mega_bracelet` withholds Mega Evolution from that player
exactly as the games do. `teraShardRequired = 50` and `minBondingRequired = 200`
are grind-length dials (MEDIUM). No `dynamax_band`-style id appears in the
1.7.42 index; how Dynamax is keyed to an item is **NOT VERIFIED**.

### 2.5 CobbleverseBadges — `cobbleversebadges` 1.3 — **EASY**, the rung tokens

40 ids VERIFIED: eight badges per region for Kanto, Johto, Hoenn and Sinnoh
(e.g. `cobbleversebadges:kanto_boulder_badge` … `kanto_earth_badge`), plus
`<region>_badge_box` and `<region>_league_trophy`. No config file ships.

These are plain items. They are not themselves an upgrade, which is exactly why
they matter: **a badge is the cheapest thing in the pack to test for** when
deciding whether a player has earned the next rung, and the campaign already uses
the Kanto eight. Rung: datapack/functions check the item.

### 2.6 Bottle Caps — `obc` (overlay pins 1.5.0) — **EASY + MEDIUM**, two rungs

`obc-common.toml` (VERIFIED, 6 lines):

```
[minecraft-treasure]  silverBottleCap = 0.03   goldBottleCap = 0.0
[cobblemon-treasure]  silverBottleCap = 0.05   goldBottleCap = 0.0
```

Silver cap = hyper-train one IV, gold = all IVs (ASSUMED, the mod's premise).
**Gold caps are currently unobtainable from treasure** (both rates 0.0), so gold
is already a reward the campaign controls completely — hand it out, or sell it
late. Drop rates are config (MEDIUM); obtaining by crafting is recipe (EASY).

### 2.7 Portable comfort — `comforts` 9.0.5+1.21.1 — **EASY**. **WORLD-CRITICAL.**

`comforts:sleeping_bag` and hammocks in 16 colours (32 `comforts:` ids in the
index). A sleeping bag passes the night and sets no spawn point — this is the
item that makes "never build a house" literally work. Config (VERIFIED):
`sleepingBagUse = "DAY_OR_NIGHT"`, `hammockUse = "DAY_OR_NIGHT"`,
`restMultiplier = 2.0`, `sleepingBagBreakChance = 0`,
`sleepingBagEffects = []`, `hammocksStopPhantoms = true`,
`sleepingBagsStopPhantoms = true`, `restrictSleeping = false`.

`sleepingBagEffects = []` is a **free rung**: effects on waking are config, so a
later-tier bedroll could grant a buff with no code at all. These are blocks when
placed, so world-critical.

### 2.8 Portable storage above the backpack — `sophisticatedstorage` 1.21.1-1.3.7.9.139 — **EASY**

`sophisticatedstorage-server.toml` (VERIFIED) enumerates the same six materials
across barrels, chests and **shulker boxes** — `ShulkerBox`, `CopperShulkerBox`,
`IronShulkerBox`, `GoldShulkerBox`, `DiamondShulkerBox`, `NetheriteShulkerBox` —
plus `LimitedBarrel I`–`IV` in all six materials (49 blockstates per the
inventory). 977 ids in the REI index.

Tiered **shulker boxes** are the part that fits the brief: portable, not
furniture. The barrels and chests are the house we are trying not to need; they
are worth a rung only as a town stash.

### 2.9 CobbleCuisine — `cobblecuisine` 2.0.1 — **EASY + MEDIUM**

`cobblecuisine.json` (VERIFIED) already has a three-rung friendship ladder as
plain numbers: `beanFriendship: 1`, `pokepuffFriendship: 6`,
`malasadaFriendship: 12`, plus camp boosts (`expBoostMultiplier: 2.0`,
`catchRateMultiplier: 2.0`, `shinyBoostMultiplier: 48.0`,
`effectDistanceBlocks: 40.0`, `ivMinValue: 20`, `ivMaxValue: 31`,
`teraBoostChance: 0.95`, `natureBoostChance: 0.95`).
156 `cobblecuisine:` ids in the index. Consumables, so recipe-gateable, and the
potency numbers are config. A good mid-ladder "your camp is better now" rung.

### 2.10 Tom's Storage — `toms_storage` 2.3.0 (MIT) — **EASY**, late-game logistics

`toms_storage.json` (VERIFIED) shows a **beacon-level** progression for remote
access: `wirelessRange: 32`, `advWirelessRange: 512`,
`wirelessTermBeaconLvl: 1`, `wirelessTermBeaconLvlCrossDim: 4`,
`invLinkBeaconLvl: 0`, `invLinkBeaconLvlSameDim: 1`,
`invLinkBeaconLvlCrossDim: 2`, `invLinkBeaconRange: 4096`.

A wireless terminal that reaches a stash from the road is on-brief as a *final*
rung. Items absent from the REI index (see §0 limit 1), so ids are unknown.
Gating is recipe (EASY) and the beacon requirement is config (MEDIUM).

### 2.11 Lumymon — `lumymon` 0.6.6 — **MEDIUM**. **WORLD-CRITICAL.**

`lumymon.json` (VERIFIED) ships `remotePcEnabled: true` — a **remote PC**, i.e.
Pokémon storage without walking to a box. Directly on-brief, and currently on for
everyone from minute one. There is no per-player key: it is a single boolean
(MEDIUM). `lumymon:store_card` (999 CobbleDollars in the shop) exists and may be
an access item, but **whether the card gates the remote PC is NOT VERIFIED** — if
it does, this becomes an EASY rung and a good one. Worth checking.

### 2.12 Iron Chests — `ironchest` 2.0.4 (MIT) — **EASY**, but off-brief

Tiered chests, `has_recipes` true, no config file ships. Ids absent from the REI
index. Furniture; recorded only for completeness.

---

## 3. What already hands out tiers without us asking

The brief asks for this explicitly, because anything here quietly skips the
ladder.

### 3.1 Radical Cobblemon Trainers runs a full progression system already — **the big one**

`modpack/config/rctmod-server.toml` (**our overlay**, VERIFIED):

```
[Players]
    initialLevelCap = 20
    relativeLevelCap = 0
    initialSeries = "kanto"
    freeroamRequiresCompletedSeries = true
    allowOverLeveling = false
[Spawning]
    spawningRequiresTrainerCard = true
```

This is a second ladder already running: a **level cap** that advances through a
series, a **series** the player must complete before free roam, and
`rctmod:trainer_card` (500 CobbleDollars in the shop) as an **access item that
already exists** — without the card, trainers do not spawn at all.

Two consequences for the design:

1. **Any new ladder must be reconciled with this one, not layered on it.** Two
   systems advancing a player on different schedules is exactly the kind of
   cross-system collision CLAUDE.md warns about.
2. The trainer card is a working precedent for "an item unlocks a system",
   bought in a market. Copy that shape rather than inventing one.

### 3.2 Things that are on for everyone from the start

| Mod | What it already gives | Rating |
| --- | --- | --- |
| `lumymon` | `remotePcEnabled: true` — remote Pokémon storage, day one | MEDIUM |
| `mega_showdown` | `mega`, `zMoves`, `teralization`, `dynamax` all `true` globally | MEDIUM mechanic / EASY item |
| `pasture-loot` | passive item income: `drop_chance_per_minute: 0.15` per pastured Pokémon, blacklist only (`PastureLoot.json`) | MEDIUM |
| `capture_xp` + `tim_core` | `enableExpAll: true`, `expAllMultiplier: 0.1` — party XP from captures | MEDIUM |
| `playerxp` | player XP from battles (`baseXP: 0.8`, `shouldGiveLevels: false`, `enableDailyCap: false`) feeding enchanting. Note it appears in **both** `replace` and `server_exclude` in the overlay manifest, which is worth a second look. | MEDIUM |

### 3.3 Things that are already OFF, and should stay off

Recorded so nobody turns them on by accident: backpack chest loot and mob drops
(§1.3), `obc` gold bottle caps (§2.6), Waystones costs and cooldowns (§2.3),
`comforts` sleeping-bag break chance (§2.7). Each is a tap the ladder would
rather own itself.

### 3.4 `advancementdisable`

`advancementdisable.toml` (VERIFIED): `disabledMods = ["beautify", "rctmod", "repurposed_structures"]`.
No mod in the pack was found that *grants* an item on a vanilla advancement, but
this confirms advancements are already being managed pack-side — relevant if the
ladder ever keys on them.

---

## 4. Not gateable, or not available

| Thing | Why |
| --- | --- |
| Mega / Z / Tera / Dynamax **mechanics** per player | global booleans in `mega_showdown/config.json`. Gate the key item instead (§2.4). |
| Backpack tiers from an **advancement** | no advancement, permission or requirement key exists in either backpack config (both read in full). |
| **Raid den tiers** | `cobblemonraiddens` has a 7-tier config (`tier_one` … `tier_seven`, `dimension_tier_weights = [10,16,20,24,22,6,2]`, `required_energy: 100`) and **our overlay removes the mod**: it calls the removed `GraalShowdownService.getContext()` and aborts world load on Cobblemon 1.8, with `world_save_risk: HIGH`. A seven-rung raid ladder is **not available** to this campaign. |
| **Per-region** tiering via raid dens | even if the mod returned, weights are per *dimension*, not per biome or region — geography is not expressible. |
| `legendarymonuments` seal/stake progression | `firescourge`/`grasswither`/`groundblight`/`icerend` `_seal` and `_stake` ids VERIFIED, plus `origin_ingot`, `distortion_origin_ore` and a `distortion_world` dimension — and **no config file ships**. The sequence looks coded in: **HARD**, and world-critical (worldgen + structures + a dimension). The items are recipe-gateable (EASY) even where the mechanic is not. |
| Per-player anything, generally | **this is the structural finding.** Not one mod in the pack exposes a per-player gate. Every lever is server-wide config or a recipe. The only per-player mechanism the pack has is **possession of an item** — which is precisely why the backpack, the badges, the trainer card and the mega bracelet matter more than any config key. |

---

## 5. Where the ladder would need something the pack does not have

Reported as findings, not proposals. Principle 9 — no mod is being suggested.

1. **No per-player unlock state exists anywhere.** Not in the backpack, not in
   Waystones, not in Mega Showdown. If the ladder needs "this player has reached
   rung 4", the pack cannot store that for us; it has to be inferred from items
   held (badges, cards, key items) or from campaign-side data. Nothing needs
   adding for that, but it does need deciding.
2. **Per-town shop stock is unconfirmed** (§2.1). If CobbleDollars has one global
   shop, geography cannot gate purchases and the whole "town markets are where
   that happens" design rests on price alone.
3. **Recipe suppression is untested in this pack** (§0). Everything rated EASY
   depends on it.
4. **No scripting layer exists** (CLAUDE.md). Anything needing per-player
   conditional logic falls to datapack functions and commands — rung 6 of the
   preference order — or further down.

---

## 6. What to test before designing the ladder

Smallest first, each cheap, none of them run here:

1. **Does a datapack suppress a mod recipe?** Suppress one
   `sophisticatedbackpacks` tier recipe, boot, open REI, confirm the item shows
   no recipe and still exists. Settles every EASY rating in this document.
2. **Read the actual recipes.** Open `sophisticatedbackpacks`, `tmcraft` and
   `comforts` with `zipfile` once jars are on the machine, and replace every
   ASSUMED recipe claim above with the real `data/<ns>/recipe/*.json`. **Nothing
   in this audit read a recipe file.**
3. **Is `defaultShop` global or per-merchant?** §2.1. Decides whether towns can
   differ.
4. **Does `lumymon:store_card` gate the remote PC?** §2.11.
5. **Re-verify every item id against the 1.8 jars.** All ids here are 1.7.42
   (§0 limit 2), and thirteen mods are version-replaced.
6. **Confirm the Cobbleverse backpack slot curve is ours to retune**, and whether
   flattening at iron was deliberate (§1.2).
