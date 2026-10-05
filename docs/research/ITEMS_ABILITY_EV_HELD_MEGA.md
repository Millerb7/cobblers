# Shop items: ability changers, EV items, held items, and a Mega without its stone

Researched 2026-10-04 for the owner's shop economy (CobbleDollars merchants sell configured item stacks).

**Versions and sources.** The runtime is Cobblemon **1.8.0+1.21.1** (`docs/STATE.md`, "Runtime"), so Cobblemon facts come
from the GitLab tag `1.8.0` (raw files, linked per claim). Mega Showdown (MSD) is pinned at
`mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar` (`modpack/manifest/overlay.json:215`). Its GitHub repo has **no
tags**, so MSD code was read on `main` (`yajatkaul/CobblemonMegaShowdown`, `mod_version=1.1.3+1.8+1.21.1`,
`docs/research/notes/wild-mega-pokemon.md:11`). **Every MSD code fact below is VERIFIED for `main` and ASSUMED for
1.0.2.** One exception: a jar read of 1.0.2 confirmed that the data folder `data/mega_showdown/mega_showdown/mega/`
exists (`experiments/EXP-045-mega-bracelet/README.md:18`).

**Method caveat.** Source files were read through a fetch tool that summarises. Code quoted in backticks below was
requested and returned verbatim. The long item lists in section 3 are the tool's extraction from `CobblemonItems.kt`,
which is too long to print whole. Lines in that list were spot-checked, but the list may be incomplete. Nothing here was
run in Minecraft unless an experiment is cited.

`[CI]` below is https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/CobblemonItems.kt

---

## 1. Ability changers

### Items (VERIFIED, Cobblemon 1.8.0)

| Item id | Definition `[CI]` | Effect |
|---|---|---|
| `cobblemon:ability_capsule` | `ABILITY_CAPSULE = this.create("ability_capsule", AbilityChangeItem(AbilityChanger.COMMON_ABILITY))` | Works only on a Pokemon whose current ability is a regular one. It changes it to a **different regular ability** of the same form |
| `cobblemon:ability_patch` | `ABILITY_PATCH = this.create("ability_patch", AbilityChangeItem(AbilityChanger.HIDDEN_ABILITY))` | On a regular ability, it changes to a hidden ability. **On a hidden ability, it changes back to a regular ability chosen at random** |

**The mechanism, VERIFIED** from [`AbilityTypeChanger.kt`](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/item/interactive/ability/AbilityTypeChanger.kt)
and [`AbilityChanger.kt`](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/item/ability/AbilityChanger.kt):
- `COMMON_ABILITY` = `AbilityTypeChanger(CommonAbilityType) { other -> other == CommonAbilityType }`. A capsule therefore refuses
  to work on a hidden ability.
- `HIDDEN_ABILITY` = `AbilityTypeChanger(HiddenAbilityType) { other -> other == CommonAbilityType || other == HiddenAbilityType }`.
- `queryPossible`: `val targetType = if (currentType == HiddenAbilityType) CommonAbilityType else this.type`, then it keeps
  the form's abilities `it.type == targetType && it.template != pokemon.ability.template`.
- `performChange`: `val picked = possible.randomOrNull() ?: return false`. **The pick is random among the candidates.** In
  practice a form has at most two regular abilities and one hidden one, so with the current ability excluded there is
  usually exactly one candidate. **The capsule is then a deterministic swap, and it fails on a species with one regular
  ability.** The only real randomness is the Patch used on a hidden ability, which rolls a random regular ability when
  the form has two.
- A **forced** ability (`pokemon.ability.forced`) makes `findCurrent` return `null`, so both items refuse to work on it.
- The owner must use the item: `accepted = setOf(PokemonEntityInteraction.Ownership.OWNER)`
  ([`AbilityChangeItem.kt`](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/item/interactive/ability/AbilityChangeItem.kt)).
- The source carries a comment: `// TODO Polish me down the line when we actually release the item in the mod, we need a way to select the ability`.
- 1.8.0 changelog: *"Ability Capsules can now be brewed from Medicinal Brew and Dragon Breath."* and *"Using an Ability
  Capsule will now return an Empty Bottle."* ([CHANGELOG](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/CHANGELOG.md)).
  The changelog says nothing about how the Ability Patch is obtained. No recipe file was found at the obvious paths
  (`data/cobblemon/recipe/ability_patch.json` returned 404; recipes may be generated elsewhere). For a shop this does
  not matter: a merchant sells the stack.

**The answer to "an item that randomises a Pokemon's ability": no native item does it.** Neither item can give an
ability outside the species' own list, and the capsule is normally deterministic.

### Base pack (VERIFIED, local)
- `base-pack/inventory/` has no mod about abilities. A narrow grep for `abilit|randomi|pokemonedit` matches only unrelated
  descriptions and the library `item_abilities` (`mod_inventory.json:10134`, a porting library).
- The 1.7.42 REI groups (`base-pack/cobbleverse/config/roughlyenoughitems/collapsible.json5`) list `ability_shield`
  (`:1043`) but neither `ability_capsule` nor `ability_patch`. A REI collapsible-groups file is not a full item index, so
  this absence is weak evidence (ASSUMED meaning: players have not met these items in Cobbleverse).

### Routes to a real randomiser
| Route | Status | Evidence |
|---|---|---|
| **Command `pokemonedit` / `pokemoneditother`.** Syntax: `pokemoneditother <player> <slot> <properties>`, aliases `pokeedit`, `pokeeditother`. It runs `properties.apply(pokemon)` | **VERIFIED** (source) | [`PokemonEditCommand.kt`](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/command/PokemonEditCommand.kt); permission `CobblemonPermissions.POKEMON_EDIT_OTHER` |
| The `ability=<id>` property sets **any** ability. If the ability is not one of the form's own, it is created **forced** | **VERIFIED** (source) | [`PokemonProperties.kt`](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/pokemon/PokemonProperties.kt): `parseStringOfRegistry(keyPairs, listOf("ability"))`; `createAbility`: `form.abilities.firstOrNull { ... } ?: return ability.create(true)` |
| A "ticket" item bought from the shop, redeemed at an NPC or command block. The redeem function picks at random with vanilla `/random value` and applies `ability=<id>` through a function macro | **ASSUMED**. `/random` and macros exist in 1.21.1 (not fetched this session). The per-species ability lists, or a global pool, would have to be generated by our tools | none run |
| Molang: `apply(properties: String)` on a Pokemon, *"Applies the properties to the Pokémon. Returns 1.0."* | **ASSUMED for 1.8.0**: the wiki page is unversioned and was last edited 19 April 2025 | [wiki](https://wiki.cobblemon.com/index.php/Molang_Pok%C3%A9mon_Functions) |
| Addon "Cobblemon Randomizer" (randomises *wild spawn* abilities, not a usable item; needs Cobblemon Party Extras) | **ASSUMED** (search-result summary only; mod page not read); wrong shape for this request and a new dependency | [CurseForge](https://www.curseforge.com/minecraft/mc-mods/cobblemon-randomizer/files/7833442) |

**A design caution (ASSUMED).** A "fully random" ability, drawn from all abilities, produces a *forced* ability. After
that, neither the Capsule nor the Patch works on that Pokemon (`findCurrent` returns `null`). Whether a forced ability
survives evolution was not traced. Randomising within the species' own list keeps the ability non-forced.

---

## 2. EV training

All entries are VERIFIED (Cobblemon 1.8.0 source). The caps come from
[`EVs.kt`](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/pokemon/EVs.kt):
`MAX_STAT_VALUE = 252` and `MAX_TOTAL_VALUE = 510`, and `add` clamps to both.

| Item ids | Class `[CI]` | Effect |
|---|---|---|
| `cobblemon:hp_up`, `protein`, `iron`, `calcium`, `zinc`, `carbos` (HP, Atk, Def, SpA, SpD, Spe) | `VitaminItem(Stats.X)` → `EVIncreaseItem(stat, 10)` | **+10 EVs per use.** The only gate is `pokemon.evs.getOrDefault(stat) < EVs.MAX_STAT_VALUE`, so there is **no 100-EV vitamin cap**: vitamins alone reach 252. Each use returns a glass bottle ([VitaminItem](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/item/interactive/VitaminItem.kt), [EVIncreaseItem](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/item/interactive/EVIncreaseItem.kt)) |
| `cobblemon:health_feather`, `muscle_feather`, `resist_feather`, `genius_feather`, `clever_feather`, `swift_feather` | `FeatherItem(stat)` → `EVIncreaseItem(stat, 1)` | **+1 EV** per use ([FeatherItem](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/item/interactive/FeatherItem.kt)) |
| `cobblemon:health_mochi`, `muscle_mochi`, `resist_mochi`, `genius_mochi`, `clever_mochi`, `swift_mochi` | `MochiItem(stat)` → `EVIncreaseItem(stat, 4)` | **+4 EVs** per use, and it also calls `pokemon.feedPokemon(1)` ([MochiItem](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/item/interactive/MochiItem.kt)) |
| **`cobblemon:fresh_start_mochi`** | `FreshStartMochiItem()` | **EV reset:** `pokemon.evs.forEach { pokemon.setEV(it.key, 0) }`. It can only be used if any EV is above 0 ([FreshStartMochiItem](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/item/interactive/FreshStartMochiItem.kt)) |
| `cobblemon:power_weight` (HP), `power_bracer` (Atk), `power_belt` (Def), `power_lens` (SpA), `power_band` (SpD), `power_anklet` (Spe) | `heldItem("power_*")` | Held in battle: **+8 EVs** in its stat on each EV award (a flat bonus, not a multiplier). It is matched by **item tag** (`CobblemonItemTags.POWER_WEIGHT`, ...) |
| `cobblemon:pomeg_berry`, `kelpsy_berry`, `qualot_berry`, `hondew_berry`, `grepa_berry`, `tamato_berry` (HP, Atk, Def, SpA, SpD, Spe) | `FriendshipRaisingBerryItem(block, stat)` | Each raises friendship and **lowers that EV by `evLowerAmount`**, which is **`"10"`** in `data/cobblemon/mechanics/berries.json`, a Molang value that a datapack can override ([berry item](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/item/berry/FriendshipRaisingBerryItem.kt), [berries.json](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/resources/data/cobblemon/mechanics/berries.json)) |
| **Macho Brace** | — | **Not present.** No `macho` string occurs in `CobblemonItems.kt` 1.8.0 `[CI]` |

The power-item code, VERIFIED, from
[`EvCalculator.kt`](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/pokemon/stats/EvCalculator.kt)
`Generation8EvCalculator`:
`val boost = if (!heldItem.isEmpty && heldItem.`is`(powerItems[stat])) 8 else 0`, applied inside
`for ((stat, value) in opponentPokemon.originalPokemon.form.evYield)`. ASSUMED: `evYield` lists all six stats, some at 0, so the +8 applies
even against a Pokemon that yields no EVs in that stat (mainline behaviour). If the map holds only the non-zero stats,
it does not. This was not checked.

**Also native, and relevant to a stat shop (VERIFIED `[CI]`):** IV "hyper training" candies
`cobblemon:health_candy`, `mighty_candy`, `tough_candy`, `smart_candy`, `courage_candy`, `quick_candy` give +1 effective
IV each. `sickly_candy`, `weak_candy`, `brittle_candy`, `numb_candy`, `coward_candy`, `slow_candy` give -1. Each is defined as
`hyperTrainingItem("<name>", ±1, setOf(Stats.X), 0..IVs.MAX_VALUE)`, and the class calls
`pokemon.hyperTrainIV(stat, effectiveIV + ivIncreaseAmount)`
([HyperTrainingItem](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/item/interactive/HyperTrainingItem.kt)).
These overlap with Only Bottle Caps (`obc:bottle_cap*`, `docs/research/notes/reward-item-inventory.md:314-324`).
`reward-item-inventory.md:305` lists these candies as "UNKNOWN what these do"; that is now answered.

---

## 3. Held items

### How an item reaches the battle (VERIFIED, Cobblemon 1.8.0)
- [`BaseCobblemonHeldItemManager.kt`](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/pokemon/helditem/BaseCobblemonHeldItemManager.kt)
  `load()` covers **only `identifier.namespace == Cobblemon.MODID`** items. An item is mapped when its path with `_`
  removed is in `HeldItems.showdownItems`. Example: `cobblemon:choice_band` becomes `choiceband`.
- [`CobblemonHeldItemManager.kt`](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/pokemon/helditem/CobblemonHeldItemManager.kt)
  checks four things in order: the `HELD_ITEM_EFFECT` component, the item remaps (`Items.BONE → "thickclub"`,
  `Items.SNOWBALL → "snowball"`, `Items.GOLD_BLOCK → "bignugget"`), the registered stack remaps (MSD uses one, see §4),
  and then the namespace lookup above.
- [`HeldItems.kt`](https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/item/HeldItems.kt):
  `showdownItems` is filled from `ShowdownService.service.getRegistryData("heldItem")` after datapack
  `held_items/*.js` scripts are sent to Showdown. **A datapack can therefore add a Showdown item script.** ASSUMED: the
  registry data includes all of Showdown's built-in items, not only the datapack ones. Choice items work in play,
  which suggests it does, but the call was not traced.
- **Consequence (VERIFIED by the rule above):** a `cobblemon:` item has a battle effect only if its de-underscored path
  is a Showdown item id, or if it is remapped. `CHARCOAL = heldItem("charcoal_stick", remappedName = "charcoal")` exists
  because `charcoalstick` is not an id.

### The items (VERIFIED as registered `[CI]`; the battle effect is ASSUMED to follow the Showdown item of the same name)

| Group | Item ids (`cobblemon:`) |
|---|---|
| Asked for, all present | `choice_band`, `choice_specs` (both `wearableItem`), `choice_scarf`, `life_orb`, `leftovers` (`compostableHeldItem`), `focus_sash`, `assault_vest`, `rocky_helmet`, `expert_belt`, `eviolite` |
| Other competitive items | `air_balloon`, `weakness_policy`, `blunder_policy` (both `itemNameBlockItem`, so they have block forms too), `heavy_duty_boots`, `black_sludge`, `flame_orb`, `toxic_orb`, `loaded_dice`, `white_herb`, `power_herb`, `mental_herb`, `mirror_herb`, `throat_spray`, `muscle_band`, `wise_glasses`, `scope_lens`, `wide_lens`, `zoom_lens`, `quick_claw`, `bright_powder`, `shell_bell`, `covert_cloak`, `protective_pads`, `safety_goggles`, `utility_umbrella`, `ability_shield`, `clear_amulet`, `red_card`, `eject_button`, `eject_pack`, `absorb_bulb`, `cell_battery`, `luminous_moss`, `room_service`, `punching_glove`, `metronome`, `sticky_barb`, `iron_ball`, `lagging_tail`, `ring_target`, `float_stone`, `binding_band`, `grip_claw`, `shed_shell`, `focus_band`, `kings_rock`, `light_clay`, `terrain_extender`, `damp_rock`, `heat_rock`, `icy_rock`, `smooth_rock`, `electric_seed`, `grassy_seed`, `misty_seed`, `psychic_seed`, `light_ball`, `metal_powder`, `quick_powder` |
| Type boosters | `black_belt`, `black_glasses`, `charcoal_stick` (→ `charcoal`), `dragon_fang`, `fairy_feather`, `hard_stone`, `magnet`, `miracle_seed`, `mystic_water`, `never_melt_ice`, `poison_barb`, `sharp_beak`, `silk_scarf`, `silver_powder`, `soft_sand`, `spell_tag` (`itemNameBlockItem`), `twisted_spoon` |
| Type gems | 18 `*_gem`, e.g. `FIRE_GEM = this.create("fire_gem", GemItem(Item.Properties(), CobblemonBlocks.TYPE_GEM_CLUSTER_FIRE))`. They are TM crafting material (changelog: *"TMs are made from elemental type gems"*). As held items: ASSUMED to work through `firegem`, but this was not tested, and gems are "Past" items in Showdown's Gen 9 data (from memory) |
| **Type plates** | **None in Cobblemon** (no `plate` string `[CI]`). Mega Showdown ships 17 Arceus plates `mega_showdown:*_plate` (`reward-item-inventory.md:416`). Their battle effect would come through MSD's stack remap (`ShowdownItem` component, §4); ASSUMED, not read per plate |
| Mostly out-of-battle effects | `exp_share` (`wearableItem`), `lucky_egg`, `everstone`, `soothe_bell`, `destiny_knot`, `smoke_ball`, `cleanse_tag`. Their Cobblemon effect (EXP, evolution, friendship) is outside Showdown. ASSUMED: they do nothing in battle |
| EV | the six `power_*` (§2) |
| **Not present** | `macho_brace`, all `*_plate`, any `*ite` Mega Stone (those are `mega_showdown:`) |

This is the fetch tool's list of every `heldItem(`, `wearableItem(` and `compostableHeldItem(` call, plus the
`itemNameBlockItem` items looked up by name. A held item missing from it is not proof that the item is absent. The
1.7.42 REI groups (`collapsible.json5:991-1093`, as summarised in `reward-item-inventory.md:209-229`) agree on every
item named above.

### RCT trainers' held items
- **VERIFIED (RCT docs `latest`, unversioned; we run 0.19.0-beta).** `heldItem` is *"A single item or a list of items
  possibly held by the pokemon (if one item is not found, the next is checked)"*. The docs' example is
  `["mega_showdown:electrium-z", "life_orb"]`, and they add *"Mega Evolutions or Z-Moves will be activated by
  corresponding held items"* ([RCT trainers](https://srcmc.gitlab.io/rct/docs/latest/configuration/data_pack/trainers/)).
  These are **Minecraft item ids**, with or without a namespace.
- **VERIFIED (local).** `data/trainers.json` uses bare paths (`"heldItem": "life_orb"`), and every one of its 26 values
  has a matching `cobblemon:` item (`reward-item-inventory.md:249-261`).
- **ASSUMED.** RCT resolves a bare path to the `cobblemon:` namespace, and the battle effect then follows the same
  `CobblemonHeldItemManager` path as a player's item. So a shop item and a trainer's item are the same thing. The
  resolution code was not read.

---

## 4. A Mega in the party without holding its stone

### What Mega Showdown requires (VERIFIED, MSD `main`)
- **Eligibility is the held item.**
  [`MegaGimmick.canMega`](https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/java/com/github/yajatkaul/mega_showdown/gimmick/MegaGimmick.java):
  `MegaGimmick megaGimmick = RegistryLocator.getComponent(MegaGimmick.class, heldItem);` and then
  `if (!pokemon.getSpecies().getName().equals("Rayquaza") && megaGimmick == null) return false;`.
  **The only stoneless case is Rayquaza with `dragonascent` in its four moves.** It also requires the player to have
  the gimmick (`GimmickTurnCheck.hasGimmick(...MEGA_EVOLUTION, player)`), which is the bracelet in the Accessories slot
  (EXP-045).
- **A Mega definition is datapack data.** The dynamic registry is `mega_showdown:mega`
  (`ResourceKey.createRegistryKey(... "mega")`,
  [`MegaShowdownDatapackRegister`](https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/java/com/github/yajatkaul/mega_showdown/datapack/MegaShowdownDatapackRegister.java)),
  and its files live at `data/<ns>/mega_showdown/mega/<name>.json`. Example,
  [`gengarite.json`](https://raw.githubusercontent.com/yajatkaul/CobblemonMegaShowdown/main/common/src/main/resources/data/mega_showdown/mega_showdown/mega/gengarite.json):
  `{"showdown_id": "gengarite", "pokemons": ["Gengar"], "aspect_conditions": {"apply": {"aspects": ["mega_evolution=mega"]}, "revert": {"aspects": ["mega_evolution=none"]}}}`.
- **An item links to a definition through two persistent data components**,
  `mega_showdown:registry_type_component` (string, `"mega"`) and `mega_showdown:registry_location_component`
  (a resource location) ([`RegistryLocator`](https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/java/com/github/yajatkaul/mega_showdown/utils/RegistryLocator.java),
  `MegaShowdownDataComponents`). The component ids are as the fetch tool reported them; the namespace is ASSUMED to be
  `mega_showdown` because they are registered through `DeferredRegister.create(MegaShowdown.MOD_ID, ...)`.
- **The battle sees the stone, not the item.** MSD registers
  `CobblemonHeldItemManager.INSTANCE.registerStackRemap(...)`, which returns `megaGimmick.showdown_id()` for any stack
  carrying the mega components. One stack reports one Showdown id. **Putting the components on a Leftovers turns it into a
  Gengarite in battle, not Leftovers plus a Gengarite.** No data route lets a Pokemon hold a different battle item and
  still Mega Evolve in battle.
- **Every MSD revert and "already Mega" check keys on the persistent flag `is_mega`, not on the form.** `IS_MEGA_TAG =
  "is_mega"`. `isMega`, `hasMega` and `megaToggle` test `getPersistentData().getBoolean(IS_MEGA_TAG)`. The battle-start
  revert runs only `if (pokemon.getPersistentData().getBoolean(MegaGimmick.IS_MEGA_TAG))`
  ([`AspectUtils.revertPokemonsIfRequired`](https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/java/com/github/yajatkaul/mega_showdown/utils/AspectUtils.java)).
  The held-item-change revert also requires the *returning* item to be that species' Mega item and `isMega(pokemon)`
  ([`CobbleEvents.heldItemChange`](https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/java/com/github/yajatkaul/mega_showdown/event/CobbleEvents.java)).
- **Config (VERIFIED local, Cobbleverse 1.7.42 file).** `base-pack/cobbleverse/config/mega_showdown/config.json` has 22
  keys; the Mega ones are `"mega": true`, `"multipleMegas": true` and `"outSideMega": true` (`:3, :5, :16`). **None is
  a "Mega without stone" flag.** No item, config key or datapack field for this was found.

### The route that does exist: a permanent Mega form set by Cobblemon, with no `is_mega` flag
- **VERIFIED (Cobblemon 1.8.0).** The Mega form is the species feature `mega_evolution` (`mega`, `mega_x`, `mega_y`; MSD
  adds `mega_z`), and it is settable as a Pokemon property (`docs/research/notes/wild-mega-pokemon.md:31-46, 72-76`).
  `pokemoneditother <player> <slot> mega_evolution=mega` applies properties to a party Pokemon (§1, `PokemonEditCommand`).
- **VERIFIED in game, for a wild Pokemon (EXP-036).** A Charizard spawned with `mega_evolution=mega_x` and no stone had
  the form `megax` and the ability `toughclaws`. The battle started and *"mega stayed"*
  (`experiments/EXP-036-wild-mega/README.md:12-22`). Showdown therefore accepts a Pokemon that is already Mega
  without its stone.
- **ASSUMED (strong, from the source above).** A *player's* Pokemon set this way carries no `is_mega` flag, so MSD
  never reverts it: not at battle start, not at battle end, and not when its held item changes. It would stay Mega
  permanently and hold anything, e.g. Leftovers. It also does not count toward `hasMega`, so it does not block a
  normal Mega Evolution of another party member. `multipleMegas` is `true` here anyway.
- **What the shop would sell (ASSUMED design).** CobbleDollars sells item stacks, not commands. So the shop sells a
  **"Mega Charm" ticket** at about three Mega Stones' price, and an NPC or command block redeems it by running a
  function with `pokemoneditother @p <slot> mega_evolution=<mega|mega_x|mega_y>`. The function must check that the
  species has that choice: `mega` on a Charizard matches no form (`wild-mega-pokemon.md:86-90`). How a slot is chosen
  is a design problem (a fixed slot 1, or one ticket per species).

### Not possible, or not known
- **Not possible from data:** a Mega Evolution *in battle* (the button) without the stone component on the held item.
  The only exception is Rayquaza with Dragon Ascent, which is hard-coded. Changing that needs code (an MSD mixin or a
  fork), which principle 6 puts last.
- **Unknown (experiment candidates; the backlog was not edited because the brief allowed one file only):**
  1. `pokemonedit 1 mega_evolution=mega` on an owned Gengar: does the model change, and does it battle as Mega Gengar
     (Shadow Tag, Mega stats) with Leftovers held? Does it stay Mega after the battle, a relog and a server restart?
  2. Does Showdown still offer that player a Mega Evolution for a *second* party member holding a stone? Does the
     permanent Mega behave in an RCT trainer battle?
  3. Does it survive storing it in the PC, healing at a healer, and evolution (n/a for most)? Can it be traded, given
     that `setTradeable(false)` is only called by MSD's own `megaEvolve`?
  4. Does MSD 1.0.2 match `main` on `is_mega`, `canMega` and the stack remap? This needs a jar read.
  5. Is the shop ticket (a renamed or `custom_data` item) safe from forgery, given that players can rename items in an
     anvil? This decides whether redemption must check `custom_data` rather than the name.

---

## Other experiment candidates (not added to `EXPERIMENT_BACKLOG.md`; one-file brief)
- **Ability.** Use `ability_patch` on a hidden-ability Pokemon that has two regular abilities, and confirm it rolls
  one at random. Use `ability_capsule` on a single-regular-ability species and confirm it fails. Set a random ability
  through a `/random` + macro function with `pokemoneditother ... ability=<id>`, and record whether it comes out forced.
- **EV.** Confirm the vitamin's +10 per use and that 26 uses reach 252. Measure the +8 power-item bonus against a
  Pokemon whose EV yield is zero in that stat.
- **Held.** Check that a `cobblemon:fire_gem` held in battle triggers the Gem (it should not, if Gen 9 rules exclude
  Past items). Check a `mega_showdown:*_plate` on Arceus.
- **RCT.** Check that a bare `heldItem: "leftovers"` resolves to `cobblemon:leftovers` on 0.19.0-beta.
