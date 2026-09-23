# What this pack has to give: an inventory of placeable rewards

**Question.** For optional themed regions inside Victory Road (late game, player level cap
60, after eight badges): what items actually exist in this pack that are worth finding, with
real ids, and how would the campaign place one?

**Answered for:** Cobblemon **1.8.0**+1.21.1 Fabric, the overlay mod set in
`modpack/manifest/overlay.json`. Where an id comes from the Cobbleverse **1.7.42** snapshot
it is labelled as such; a 1.7.42 id is evidence that the item existed then, not proof it
still exists under 1.8.0.

---

## 0. How this was evidenced, and what it does not cover

Bash was disabled for this session, so **no jar or datapack zip was opened, and nothing
under `cobblers-server/` was read** (the mandated process/port check and coordination lock
could not be performed, so the server tree was left alone entirely). Evidence is:

| Source | What it proves | Version it applies to |
| --- | --- | --- |
| `base-pack/cobbleverse/config/roughlyenoughitems/collapsible.json5` | the pack's own REI item index: literal item ids present in the installed mod set | **Cobbleverse 1.7.42 / Cobblemon 1.7.3** |
| Cobblemon source, `gitlab.com/cable-mc/cobblemon` `main` branch, `common/src/main/kotlin/com/cobblemon/mod/common/CobblemonItems.kt` and `CobblemonItemComponents.kt` | registry names and data components | `main`, i.e. at or after 1.8.0 |
| TMCraft source, `github.com/KiwiFlavoredApollo/tm-craft` `master` | TM item id construction | current master |
| `data/structures.json`, `docs/world-building/WORLDGEN_FEATURES.md` | jar-derived scans made in this repo against the **1.8** jar set | Cobblemon 1.8.0, Mega Showdown 1.0.2 |
| `modpack/manifest/overlay.json`, `base-pack/inventory/mod_inventory.md` | which mods are installed and at what version | the 1.8 target |

**Not covered:** no id below has been resolved in a running game. `/give` is the only proof
that an id exists; nothing here has had that done to it.

---

## 1. TMs — which mechanism is live, and the id form

**Both are installed. This is the headline finding.**

- **VERIFIED** TMCraft is carried forward to the 1.8 target as `tmcraft-1.4.19+1.8.0.jar`
  (`modpack/manifest/overlay.json:48-60`), with `tim_core` as its required library
  (`overlay.json:107,110-113`). It is flagged `needs_functional_test`
  (`overlay.json:631-633`): *"1.8-targeted replacement must be tested for table recipes,
  machine interaction, and teaching a move"*.
- **VERIFIED** Cobblemon 1.8.0 adds native TMs: *"Technical Machines (TM's) are consumable
  items that are used to teach a move to a compatible Pokémon"*, *"introduced in version
  1.8.0"*, *"TM's are consumed on use"*
  (https://wiki.cobblemon.com/index.php/Technical_Machine).

So the pack has **two independent TM systems running at once**. Nothing in the repo records
a decision about which one the campaign uses.

### Cobblemon native TM (1.8.0)

- **VERIFIED (source, `main` branch)** the item is a **single registered item carrying a
  component**, not one item per move:
  - `@JvmField val TECHNICAL_MACHINE = this.create("technical_machine", TechnicalMachineItem(Properties()))`
  - `@JvmField val BLANK_TM = this.create("blank_tm", CobblemonItem(Item.Properties()))`
  - type gems: `NORMAL_GEM = this.create("normal_gem", GemItem(...))`, `FIRE_GEM`, `WATER_GEM`, … (one per type)
  — `common/src/main/kotlin/com/cobblemon/mod/common/CobblemonItems.kt`
- **VERIFIED (source)** the component is registered as `"cobblemon:tm_move"` →
  `DataComponentType<TMMoveComponent>` (`CobblemonItemComponents.kt`), and `TMMoveComponent`'s
  codec is `Codec.STRING.fieldOf("move")`
  (`common/src/main/kotlin/com/cobblemon/mod/common/item/components/TMMoveComponent.kt`).
- **ASSUMED** the give syntax is therefore
  `/give @p cobblemon:technical_machine[cobblemon:tm_move={move:"thunderbolt"}]`.
  The id and the component and field names are verified; the **exact 1.21.1 component
  argument spelling has not been executed**, and the accepted spelling of a move name
  (`thunderbolt` vs `THUNDERBOLT` vs `thunder_bolt`) is not verified. Treat this as a
  command to test, not a command to ship.
- **VERIFIED** single-use: *"TM's are consumed on use"* (wiki, 1.8.0).
- **VERIFIED** obtainable in the world two ways:
  1. the **TM Machine** block, *"a utility block used to create Technical Machines (TM's) by
     burning unlocked TM recipes onto Blank TM disks"*, needing a blank TM, a matching **Type
     Gem** and up to two more ingredients; recipes unlock by owning a Pokémon that knows the
     move, or by right-clicking a **Data Monitor** holding a TM
     (https://wiki.cobblemon.com/index.php/TM_Machine).
  2. **ruin loot**: *"TM's can also be found inside Gimmighoul Chests in ruins generated
     throughout the world"* (wiki, Technical Machine). The 1.8.0 changelog adds that *"All
     ruin structures' gilded chest loot tables have been updated to include a guaranteed TM
     not learned naturally by any Pokémon through their level-up moveset, and each ruin gets
     its own specific TM"*, and that shipwreck cove treasure guarantees an elemental Hyper
     Beam TM — Blast Burn in magma coves, Frenzy Plant in lush coves, Hydro Cannon in
     submerged coves. Those loot table ids are visible in this repo's own jar scan:
     `cobblemon:shipwreck_coves/gilded_chests/big_treasure_frenzyplant`,
     `…/big_treasure_blastburn`, `…/big_treasure_hydrocannon`, `…/lesser_treasure`
     (`data/structures.json:4756-4758, 4829-4830, 4977-4979`).
- **This is the single most reusable finding for Victory Road caches.** Cobblemon 1.8 has
  already established the pattern "one named structure = one guaranteed TM that nothing
  learns naturally". A themed region whose cache is a **gilded chest** holding one named TM
  is not an invention; it is the mod's own reward grammar. Gilded chest block/item ids are
  verified present: `cobblemon:gilded_chest`, `blue_`, `black_`, `white_`, `yellow_`,
  `pink_`, `green_gilded_chest`, plus `cobblemon:gimmighoul_chest`
  (`base-pack/cobbleverse/config/roughlyenoughitems/collapsible.json5:682-691`;
  `data/structures.json:6538-6539`).
- **UNKNOWN** there is no published list of which moves exist as native TMs. The wiki page
  shows only that TMs exist across all 18 types. Getting the list means reading
  `data/cobblemon/tm_recipe/` (folder name unverified) out of the 1.8.0 jar.

### TMCraft TM

- **VERIFIED (source)** one **registered item per move**, id built as
  `Identifier.of(TMCraft.MOD_ID, String.format("tm_%s", name))`
  (`src/main/java/kiwiapollo/tmcraft/item/tmmove/TMMoveItem.java`), with the moves
  hardcoded as static fields, e.g. `register("absorb", ElementalTypes.INSTANCE.getGRASS())`.
  So the form is **`tmcraft:tm_<movename>`**, the move name lowercased with no separators.
- **VERIFIED (local, 1.7.42)** the pack's REI index lists the whole set literally, e.g.
  `tmcraft:tm_10000000voltthunderbolt`, `tmcraft:tm_absorb`, `tmcraft:tm_accelerock`,
  `tmcraft:tm_aerialace`, `tmcraft:tm_earthquake`, `tmcraft:tm_drillrun`,
  `tmcraft:tm_dynamaxcannon`
  (`collapsible.json5:1404-1419, 1598-1609`). **This is the discoverable list the question
  asked for**: the "TM Moves" group runs `collapsible.json5:1402-2336`, roughly **930
  ids**; "Tutor Moves" `2337-3271`; "Egg Moves" `4070-5004`. Reading those three ranges
  gives a complete, copy-pasteable move catalogue — for 1.7.42. The 1.4.19+1.8.0 jar's set
  is **ASSUMED** to be the same or a superset; not verified.
- **VERIFIED (source)** consumed on use, but gated by a game rule:
  `if (shouldConsumeItemByGameRule(player.getServerWorld()) && !player.isCreative()) { itemStack.decrement(1); }`
  (`MoveTeachingItem.java`), with the rule named `consumeMoveItemOnUse`
  (https://modrinth.com/mod/tmcraft). So **the campaign can make TMs reusable with one game
  rule** — relevant to whether a TM in a cache is a one-shot or a permanent unlock.
- **VERIFIED (source/Modrinth)** TMCraft TMs are **crafted only**; the mod explicitly
  *"Removed wild Pokémon TM drops"* and TMs *"cannot teach egg moves or tutor moves"*
  (README, master). Blank discs are tiered by move power: copper `[0-30)` through netherite
  `[120+)`, emerald for status. Blank ids verified locally:
  `tmcraft:copper_blank_disc` … `tmcraft:netherite_blank_disc`, plus `_blank_egg`,
  `_blank_book`, `_blank_star` in the same six materials
  (`collapsible.json5:3328-3351`), and `tmcraft:move_upgrade_smithing_template`
  (`collapsible.json5:6732`).

**Reward shape.** A netherite-tier TMCraft TM (`tmcraft:tm_closecombat`-class, power 120+)
is expensive to craft and cheap to place, which is exactly the "worth a detour" property.
A native `cobblemon:technical_machine` in a gilded chest matches the mod's own idiom. Both
work; the campaign has to pick one so players learn one grammar.

---

## 2. Evolution stones and evolution items

**VERIFIED (source, `main`)** — `CobblemonItems.kt`, all with `noSettingsItem(...)` so the
ids are exactly these, namespaced `cobblemon:`:

`fire_stone`, `water_stone`, `thunder_stone`, `leaf_stone`, `ice_stone`, `sun_stone`,
`moon_stone`, `shiny_stone`, `dawn_stone`, `dusk_stone`.

Evolution items (same file): `link_cable` (`create("link_cable", LinkCableItem())` — this is
Cobblemon's stand-in for trade evolution), `metal_coat`, `upgrade`, `dubious_disc`,
`deep_sea_scale`, `deep_sea_tooth`. **VERIFIED (1.8.0 changelog)** *"Upgrade and Dubious
Disc can be inserted into a Data Monitor for obtaining Porygon"*
(https://wiki.cobblemon.com/index.php/1.8.0). Further evolution-relevant items verified in
the 1.7.42 REI index: `cobblemon:razor_claw`, `razor_fang`, `kings_rock`, `everstone`,
`black_augurite` is **not** present in that index (`collapsible.json5:991-1093`).

### Are stones already obtainable? Mostly no, and this matters a lot

- **VERIFIED (local)** Cobblemon ships **stone ore blocks**, and the pack indexes them:
  `cobblemon:fire_stone_ore`, `deepslate_fire_stone_ore`, `nether_fire_stone_ore`,
  `water_stone_ore`, `deepslate_water_stone_ore`, `thunder_stone_ore`,
  `deepslate_thunder_stone_ore`, `moon_stone_ore`, `deepslate_moon_stone_ore`,
  `dripstone_moon_stone_ore`, `dawn_stone_ore`, `deepslate_dawn_stone_ore`,
  `dusk_stone_ore`, `deepslate_dusk_stone_ore`, `sun_stone_ore`, `deepslate_sun_stone_ore`,
  `terracotta_sun_stone_ore`, `leaf_stone_ore`, `deepslate_leaf_stone_ore`,
  `ice_stone_ore`, `deepslate_ice_stone_ore`, `shiny_stone_ore`,
  `deepslate_shiny_stone_ore` (`collapsible.json5:139-161`).
- **VERIFIED (this repo, against the 1.8 jars)** **none of them generate in this world.**
  `docs/world-building/WORLDGEN_FEATURES.md:5-9`: *"A WorldPainter export writes every chunk
  as already generated, so no feature runs inside it: no ores, apricorn trees, berries,
  mints, fossils or wild waystones."* Cobblemon 1.8.0 contributes 103 placed features
  including **42 evolution-stone ore features**, all absent from the export
  (`WORLDGEN_FEATURES.md:25`). The Nether keeps its features, so
  `nether_fire_stone_ore` is the one exception (`WORLDGEN_FEATURES.md:7-8`).

**Consequence:** in the campaign world as it exists, an evolution stone in a cache is a
*real* reward, not a shortcut — the scatter pass that would restore ore is specified but not
written (`WORLDGEN_FEATURES.md:102, 128`). If the scatter pass lands first, stones become
mining chores and stop being cache-worthy. Flag this dependency to the owner.

### Which catchable families are gated behind one

Grepped `data/spawns.json` for stone- and item-gated pre-evolutions. **VERIFIED present in
the campaign's rosters** (species strings found in `data/spawns.json`):

| Gate | Species in the rosters |
| --- | --- |
| Fire Stone | `vulpix` |
| Thunder Stone | `pikachu` |
| Water Stone | `poliwhirl`, `shellder`, `staryu`, `lombre` |
| Leaf Stone | `gloom`, `nuzleaf` |
| Sun Stone | `gloom`, `petilil`, `cottonee`, `helioptile` |
| Ice Stone | `crabrawler` |
| Shiny Stone | `roselia`, `togetic`, `minccino` |
| Dusk Stone | `murkrow`, `misdreavus` |
| Dawn Stone | `kirlia`, `snorunt` |
| Moon Stone | `nidorina`, `nidorino` |
| Link Cable (trade) | `machoke`, `haunter`, `boldore`, `phantump` |
| Link Cable + item | `onix` + Metal Coat, `scyther` + Metal Coat, `rhydon` + Protector, `magmar` + Magmarizer, `dusclops` + Reaper Cloth, `porygon` + Upgrade |
| Razor Claw | `sneasel` |
| Friendship / other | `riolu`, `togepi`, `budew`, `chansey`-line absent, `sliggoo`, `inkay`, `magneton`, `nosepass` |

**ASSUMED** — the *mapping* from species to gate is mainline-Pokémon knowledge, not read out
of Cobblemon's own `species/*.json` evolution blocks. Cobblemon is known to substitute Link
Cable for trading (VERIFIED by the `LinkCableItem` registration), but per-species
requirements in 1.8.0 have not been read. Before a cache is justified as "Kirlia needs this",
confirm the gate in the species file.

**Notable absence:** `eevee` does not appear in `data/spawns.json` at all, so the whole
eeveelution stone economy currently has no consumer.

---

## 3. Held items that matter at level 60

**VERIFIED (local, 1.7.42 REI index, `collapsible.json5:991-1093`)** — every item the
question named resolves to a real registered item in the pack, all `cobblemon:`:

`leftovers`, `focus_sash`, `choice_band`, `choice_specs`, `choice_scarf`, `life_orb`,
`assault_vest`, `eviolite`, `rocky_helmet`, `air_balloon`, `weakness_policy`,
`heavy_duty_boots`, `black_sludge`, `flame_orb`, `toxic_orb`, `loaded_dice`, `white_herb`,
`power_herb`, `mental_herb`, `mirror_herb`, `throat_spray`, `expert_belt`, `muscle_band`,
`wise_glasses`, `scope_lens`, `wide_lens`, `zoom_lens`, `quick_claw`, `bright_powder`,
`shell_bell`, `covert_cloak`, `protective_pads`, `safety_goggles`, `utility_umbrella`,
`ability_shield`, `red_card`, `eject_button`, `eject_pack`, `absorb_bulb`, `cell_battery`,
`room_service`, `blunder_policy`, `punching_glove`, `metronome`, `sticky_barb`, `iron_ball`,
`ring_target`, `float_stone`, `binding_band`, `smoke_ball`, `cleanse_tag`, `destiny_knot`,
`exp_share`, `lucky_egg`, `light_ball`, `metal_powder`, `quick_powder`, `big_root`,
`medicinal_leek`, `light_clay`, `terrain_extender`, the four weather rocks
(`damp_rock`, `heat_rock`, `icy_rock`, `smooth_rock`), the four terrain seeds
(`electric_seed`, `grassy_seed`, `misty_seed`, `psychic_seed`), the type boosters
(`black_belt`, `black_glasses`, `charcoal_stick`, `dragon_fang`, `fairy_feather`,
`hard_stone`, `magnet`, `miracle_seed`, `mystic_water`, `never_melt_ice`, `poison_barb`,
`sharp_beak`, `silk_scarf`, `silver_powder`, `soft_sand`, `spell_tag`, `twisted_spoon`),
and the six EV power items (`power_weight`, `power_anklet`, `power_band`, `power_belt`,
`power_bracer`, `power_lens`).

**VERIFIED (source, `main`)** the same ids survive into the 1.8 line:
`LEFTOVERS = compostableHeldItem("leftovers", …)`, `FOCUS_SASH = heldItem("focus_sash")`,
`CHOICE_BAND = wearableItem("choice_band")`, `CHOICE_SPECS`, `CHOICE_SCARF`,
`LIFE_ORB = itemNameBlockItem("life_orb", …)`, `ASSAULT_VEST`, `EVIOLITE`, `ROCKY_HELMET`,
`AIR_BALLOON`, `WEAKNESS_POLICY` (`CobblemonItems.kt`). Note `life_orb` and
`weakness_policy` are `itemNameBlockItem` — they have block forms too, which makes them
usable as decoration in a vault.

**Type-resist berries — VERIFIED (local, `collapsible.json5:516-587`)**: `occa_berry`,
`passho_berry`, `wacan_berry`, `rindo_berry`, `yache_berry`, `chople_berry`, `kebia_berry`,
`shuca_berry`, `coba_berry`, `payapa_berry`, `tanga_berry`, `charti_berry`, `kasib_berry`,
`haban_berry`, `colbur_berry`, `babiri_berry`, `chilan_berry`, `roseli_berry`, plus the
pinch berries (`liechi`, `ganlon`, `salac`, `petaya`, `apicot`, `lansat`, `starf`,
`micle`, `custap`, `jaboca`, `rowap`, `kee`, `maranga`, `enigma`) and the staples
(`oran`, `sitrus`, `lum`, `leppa`, `cheri`, `chesto`, `pecha`, `rawst`, `aspear`, `persim`).

### A correction the owner needs

**`data/trainers.json` `heldItem` values are NOT Minecraft item ids.** They are Showdown
item slugs inside RCT/Showdown team data — `"heldItem": "eviolite"`, `"heldItem": "life_orb"`
(`data/trainers.json:64, 253`, and the rule at `docs/story/TRAINER_RULES.json:27`
*"items: heldItem and max_item_uses fields"*). That a leader's Starmie holds `life_orb` in
battle is **not** proof that `cobblemon:life_orb` can be given to a player. The good news is
that every one of the 26 distinct slugs used in `data/trainers.json` — `oran_berry`,
`eviolite`, `muscle_band`, `weakness_policy`, `damp_rock`, `mystic_water`, `rindo_berry`,
`life_orb`, `magnet`, `air_balloon`, `heat_rock`, `focus_sash`, `coba_berry`,
`rocky_helmet`, `shuca_berry`, `throat_spray`, `black_sludge`, `colbur_berry`, `leftovers`,
`choice_band`, `sitrus_berry`, `white_herb`, `assault_vest`, `choice_scarf`, `power_herb`,
`heavy_duty_boots`, `flame_orb`, `loaded_dice`, `lum_berry` — **does** have a matching
`cobblemon:` item in the REI index. So the two vocabularies happen to coincide here. They
are still different vocabularies.

### Obtainable already, or only if placed?

- **VERIFIED** berries do **not** grow in this world: berry groves are a placed feature and
  the export has none (`WORLDGEN_FEATURES.md:5-9, 106`). Every type-resist berry is
  "only if placed" until the scatter/Custom Objects pass runs.
- **ASSUMED** most competitive held items have crafting recipes or are structure-chest loot
  in Cobblemon 1.8; `tools/worldgen_features.py` classified 87 worldgen-placed items as
  "loot only" (59), "loot and crafting" (11), "crafting only" (1), "none" (16)
  (`WORLDGEN_FEATURES.md:35-48`) — but that tool only covers items *placed by a worldgen
  feature*, so it says nothing about Leftovers or Assault Vest. **The obtainability of the
  competitive held items in this world is UNCONFIRMED.** That is the biggest hole in this
  inventory and the one most worth closing before the owner designs around it.
- **VERIFIED** the campaign is currently *removing* such items from circulation: the trader
  stock policy withholds the categories `Pokéballs, Combat, Treatments, Remedies, Boosts`
  and the items `cobblemon:revival_herb`, `cobblemon:energy_root`, `cobblemon:heal_powder`,
  `cobblemon:big_root` (`data/traders.json:227-245`), and every donor building is placed
  with `clear_loot: true` — *"a bca building's barrels and chests are stocked by loot table;
  nothing is handed out before the badge-gated stock lands"* (`data/placements.json:8607-8609,
  9012-9014, 9420-9422`). So right now **a placed cache is very nearly the only source of
  anything competitive in the whole world.**

---

## 4. Consumables worth finding

All **VERIFIED (local, `collapsible.json5`)** unless marked; all `cobblemon:`.

- **Level and XP** (`979-986`): `rare_candy`, `exp_candy_xs`, `exp_candy_s`, `exp_candy_m`,
  `exp_candy_l`, `exp_candy_xl`. **VERIFIED (source)**
  `RARE_CANDY = candyItem("rare_candy", Rarity.RARE) { _, pokemon -> pokemon.getExperienceToNextLevel() }`
  — one Rare Candy is exactly one level (`CobblemonItems.kt`).
  **Caution:** the player level cap at Victory Road is 60 and is enforced by rctmod; a stack
  of Rare Candies is the most direct way a player breaks the intended curve. Recommend
  placing exp candies, not rare candies, or none.
- **EVs** (`803-812`): `protein`, `iron`, `calcium`, `zinc`, `carbos`, `hp_up`, plus
  `pp_up`, `pp_max`. **VERIFIED (source)** each is a `VitaminItem(Stats.X, …)`.
  Also the Scarlet/Violet Mochi (`6795-6802`): `health_mochi`, `muscle_mochi`,
  `resist_mochi`, `genius_mochi`, `clever_mochi`, `swift_mochi`, `fresh_start_mochi`,
  `potato_mochi` — `fresh_start_mochi` is an EV reset, which is a genuinely useful
  late-game find. And the "Poké Candies" (`6809-6820`), which look like the Aprijuice/
  friendship tier: `mighty_candy`, `smart_candy`, `quick_candy`, `tough_candy`,
  `health_candy`, `courage_candy`, and their negatives `weak_candy`, `sickly_candy`,
  `brittle_candy`, `numb_candy`, `coward_candy`, `slow_candy`. **UNKNOWN** what these do;
  not documented anywhere consulted.
- **Abilities — VERIFIED (source, `main`)**:
  `ABILITY_CAPSULE = this.create("ability_capsule", AbilityChangeItem(AbilityChanger.COMMON_ABILITY))`,
  `ABILITY_PATCH = this.create("ability_patch", AbilityChangeItem(AbilityChanger.HIDDEN_ABILITY))`.
  So `cobblemon:ability_capsule` and `cobblemon:ability_patch`. **These are absent from the
  1.7.42 REI index**, which is consistent with them being new in the 1.8 line — a genuinely
  novel reward the players have never seen. An Ability Patch is arguably the best single
  cache item in this list: rare, permanent, and it cannot be farmed.
- **IVs — Bottle Caps come from a mod, not Cobblemon.** **VERIFIED (local,
  `collapsible.json5:6474-6488`)**, mod `obc` (Only Bottle Caps, carried to
  `Only Bottle Caps-1.5.0-fabric.jar`, `overlay.json:320-344`):
  `obc:bottle_cap`, `obc:bottle_cap_gold`, and per-stat
  `obc:bottle_cap_hp` / `_attack` / `_defence` / `_special_attack` / `_special_defence` /
  `_speed`, each with a `_withered` variant that zeroes the stat instead.
  **VERIFIED (Modrinth)** silver caps max one IV to 31, gold caps max all IVs, withered caps
  set to 0; *"Right click a Pokemon you own to use the Bottle Cap"*; silver and gold are
  obtained **by fishing** with a rod or PokeRod, stat caps by crafting a silver cap with mint
  leaves, withered by combining with a wither rose
  (https://modrinth.com/mod/only-bottle-caps).
  A **Gold Bottle Cap** is a clean, high-value, non-curve-breaking Victory Road reward.
- **Natures** (`819-853`): all 21 mints, `cobblemon:adamant_mint` … `cobblemon:sassy_mint`,
  plus mint leaves and seeds in six colours. **VERIFIED (source)**
  `ADAMANT_MINT = mintItem("adamant_mint", MintItem(Natures.ADAMANT))`. **VERIFIED** mint
  *plants* are one of the 16 items whose only source in data is worldgen
  (`WORLDGEN_FEATURES.md:43`), and worldgen does not run in this export — so mints are
  "only if placed".
- **Balls** (`719-750`): `poke_ball`, `great_ball`, `ultra_ball`, `master_ball`,
  `premier_ball`, `heal_ball`, `net_ball`, `dive_ball`, `nest_ball`, `repeat_ball`,
  `timer_ball`, `luxury_ball`, `dusk_ball`, `quick_ball`, `cherish_ball`, `safari_ball`,
  `sport_ball`, `park_ball`, `fast_ball`, `level_ball`, `lure_ball`, `heavy_ball`,
  `love_ball`, `friend_ball`, `moon_ball`, `dream_ball`, `beast_ball`, and the apricorn
  colours `azure_ball`, `citrine_ball`, `roseate_ball`, `slate_ball`, `verdant_ball`.
  16 Hisuian `ancient_*_ball` variants at `697-712`, including `ancient_origin_ball`.
- **Healing** (`757-778`): `potion`, `super_potion`, `hyper_potion`, `max_potion`,
  `full_restore`, `revive`, `max_revive`, `ether`, `max_ether`, `elixir`, `max_elixir`,
  `full_heal`, `antidote`, `burn_heal`, `ice_heal`, `paralyze_heal`, `awakening`,
  `remedy`, `fine_remedy`, `superb_remedy`, `revival_herb`, `heal_powder`.
- **X-items** (`594-601`): `x_attack`, `x_defence`, `x_special_attack`,
  `x_special_defence`, `x_speed`, `x_accuracy`, `dire_hit`, `guard_spec`.

### What ball tier to place at Victory Road

**VERIFIED** apricorn trees do not generate in this export (`WORLDGEN_FEATURES.md:5-9`) and
are named *"the highest-priority feature"* precisely because *"Apricorns sit underneath Poké
Balls and three of the four [Mega/Z/Dynamax] mechanics"* (`WORLDGEN_FEATURES.md:76-77,
101`). **VERIFIED** traders are forbidden to sell Pokéballs under the interim policy
(`data/traders.json:231-237`). So **ball supply in this world is currently structurally
tight**, and balls are a more meaningful reward here than in vanilla Cobblemon.

Recommendation, marked **ASSUMED** because it is a design judgement, not a fact:
- **Ultra Balls** as the ordinary Victory Road cache filler (a handful, not a stack).
- **One situational ball per themed region** as the distinctive item — `dusk_ball` in a dark
  region, `net_ball` at water, `timer_ball` at a long-fight arena, `heavy_ball` in a rock
  region. This costs nothing and gives each region a flavour.
- **`cobblemon:master_ball`: place at most one, and not inside Victory Road.** A Master Ball
  before the League removes the tension from every authored legendary
  (`docs/STATE.md` "Legendary side content"). If one exists it should be the League reward or
  a postgame find.
- **`cobblemon:cherish_ball` / `ancient_origin_ball`** are trophy balls: no mechanical power,
  high visual distinctiveness. Good per-region signature items.

---

## 5. What the pack adds that is specific and interesting

### Mega Showdown 1.0.2 (`mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar`)

The richest source of "distinctive per-region item" in the whole pack.

- **Mega Stones — VERIFIED (local, `collapsible.json5:13435-13481`)**, 47 ids in the 1.7.42
  index: `mega_showdown:abomasite`, `absolite`, `aerodactylite`, `aggronite`, `alakazite`,
  `altarianite`, `ampharosite`, `audinite`, `banettite`, `beedrillite`, `blastoisinite`,
  `blazikenite`, `cameruptite`, `charizardite_x`, `charizardite_y`, `diancite`, `galladite`,
  `garchompite`, `gardevoirite`, `gengarite`, `glalitite`, `gyaradosite`, `heracronite`,
  `houndoominite`, `kangaskhanite`, `latiasite`, `latiosite`, `lopunnite`, `lucarionite`,
  `manectite`, `mawilite`, `medichamite`, `metagrossite`, `mewtwonite_x`, `mewtwonite_y`,
  `pidgeotite`, `pinsirite`, `sablenite`, `salamencite`, `sceptilite`, `scizorite`,
  `sharpedonite`, `slowbronite`, `steelixite`, `swampertite`, `tyranitarite`, `venusaurite`.
  This repo's own read of the **1.0.2** jar counts **83** mega stones
  (`WORLDGEN_FEATURES.md:59`), so the 1.8 jar has more than the 1.7.42 index shows.
- **VERIFIED (jar read, `WORLDGEN_FEATURES.md:57-68`)** the chain:
  each mega stone is *crafted from `mega_showdown:mega_stone` plus a type item, iron and a
  diamond*; raw `mega_stone` drops only from the `mega_showdown:mega_stone_crystal` block,
  found only in the `mega_site` structure; the **Key Stone** comes only from
  `mega_showdown:keystone_ore` in the `megaroid` structure; the **wishing star** (Dynamax
  Band) only from `wishing_star_crystal` in `wishing_weald`; the **sparkling stone**
  (Z-Ring) only from the `mega_showdown:archaeological_site/archaeological_site_rare` loot
  table at an `archaeological_site`. **None of these structures generate in a WorldPainter
  export** — they have to be placed, and two already are:
  `mega_showdown:archaeological_site/archaeological_site_a` and `_b` at the Rift dig camp
  (`data/placements.json:8449, 8478`), placed with their suspicious sand's loot intact
  (`data/placements.json:8469`).
- **Z-Crystals — VERIFIED (local, `collapsible.json5:6495-6530`)**: `mega_showdown:blank_z`,
  the 18 type crystals (`normalium_z`, `buginium_z`, `darkinium_z`, `dragonium_z`,
  `electrium_z`, `fairium_z`, `fightinium_z`, `firium_z`, `flyinium_z`, `ghostium_z`,
  `grassium_z`, `groundium_z`, `icium_z`, `poisonium_z`, `psychium_z`, `rockium_z`,
  `steelium_z`, `waterium_z`), and 17 species-exclusive ones (`aloraichium_z`, `decidium_z`,
  `eevium_z`, `incinium_z`, `kommonium_z`, `lunalium_z`, `lycanium_z`, `marshadium_z`,
  `mewnium_z`, `mimikium_z`, `pikanium_z`, `pikashunium_z`, `primarium_z`, `snorlium_z`,
  `solganium_z`, `tapunium_z`, `ultranecrozium_z`).
  **A species-exclusive Z-crystal is the ideal themed-region trophy**: unique, visibly
  special, and useless to anyone who did not build for it.
- **Z-Rings** (`6620-6634`): `z_ring` plus six colours, `z_power_ring`, and the named ones
  (`olivias_z_ring`, `hapus_z_ring`, `rocket_z_power_ring`, `gladion_z_power_ring`,
  `nanu_z_power_ring`, `olivia_z_power_ring`, `hapu_z_power_ring`).
- **Mega Bracelets / Key Stone accessories** (`6537-6557`): `mega_bracelet` + six colours;
  `mega_ring`, `may_bracelet`, `lysandre_ring`, `brendan_mega_cuff`, `korrina_glove`,
  `maxie_glasses`, `archie_anchor`, `lisia_mega_tiara`. These are **Accessories-slot items**
  (the `accessories` library is a hard dependency, `mod_inventory.md:43`), so they are
  wearables — a strong, visible "you found the thing" reward.
- **Arceus Plates** (`6564-6580`): 17 `mega_showdown:*_plate`.
  **Silvally Memory Discs** (`6587-6603`): 17 `*_memory`.
  **Genesect Drives** (`6610-6613`): `burn_drive`, `chill_drive`, `douse_drive`,
  `shock_drive`. All perfect "one per themed region" items with no balance cost unless the
  species exists.
- **Tera Shards** (`3290-3308`): 19, one per type plus `stellar_tera_shard`;
  **Tera Pouches** in 16 colours (`13639-13654`).
  **VERIFIED (jar read)** the Tera Orb is *"crafted from vanilla items"* and needs nothing
  placed (`WORLDGEN_FEATURES.md:68`).
- **Mega Ores / meteorid blocks** (`3274-3283`, `6853-6858`):
  `mega_showdown:mega_meteorid_{dawn,dusk,fire,ice,leaf,moon,shiny,sun,thunder,water}_ore`
  and the decorative `mega_meteorid_block`, `_radiated_block`, `_brick`, `chiseled_*`,
  `polished_*` — a ready-made "this region is meteorite country" palette.
- **Oricorio nectars** (`5071-5074`): `pink_nectar`, `purple_nectar`, `red_nectar`,
  `yellow_nectar`.

### LumyMon 0.6.6 — the pack's own gym-leader relics

**VERIFIED (local, `collapsible.json5:6641-6688`)**. Grouped as "League Locator Items". The
Kanto set matches this campaign's eight leaders exactly:

`lumymon:onyx_stone` (Brock), `cerulean_star` (Misty), `lieutenant_medal` (Surge),
`nature_fan` (Erika), `ninja_poison` (Koga), `hypnotic_whip` (Sabrina),
`cinnabar_glasses` (Blaine), `boss_ring` (Giovanni), `rival_sling`.

Johto, Hoenn and Sinnoh sets follow at `6656-6708`. **UNKNOWN** what these items *do* —
the name "locator" suggests they point at a legendary or a structure, but nothing consulted
says. **This is the strongest candidate for "a distinctive item per themed region"** if the
function turns out to be benign, because the naming already carries the campaign's story.
LumyMon also contributes 5 worldgen type-ore features (dragon, electron, ice, rock, steel)
whose relics — cryo, draco, metal, pebble, spark — are **worldgen-only, and worldgen does
not run here** (`WORLDGEN_FEATURES.md:28, 47`), i.e. those five relics are currently
unobtainable by any means except placement.

**Licence caution:** LumyMon is CC BY-NC-ND 4.0 and pack-specific
(`base-pack/inventory/mod_inventory.md:25`). Using its items by id at runtime is fine;
copying its assets is not.

### CobbleverseBadges 1.3

**VERIFIED (local, `collapsible.json5:6739-6788`)**: `cobbleversebadges:kanto_boulder_badge`,
`kanto_cascade_badge`, `kanto_thunder_badge`, `kanto_rainbow_badge`, `kanto_soul_badge`,
`kanto_marsh_badge`, `kanto_volcano_badge`, `kanto_earth_badge`, plus full Johto, Hoenn and
Sinnoh sets. *"Once given to players they persist in inventories"*
(`mod_inventory.md:16`). Pure items, 0 Cobblemon API refs — safe to hand out.

### Others

- **LegendaryMonuments** — **VERIFIED (jar scan, `data/structures.json:6437, 6482`)** it
  ships loot tables `legendarymonuments:chests/stark_mountain` and
  `legendarymonuments:chests/turnback_cave_chest`, and the block
  `legendarymonuments:pokemon_trial_spawner`. Contents **UNKNOWN**. Its Galar particle ore
  is worldgen-only and therefore absent (`WORLDGEN_FEATURES.md:46`).
- **CobbleDollars** — currency plus merchant NPCs (`mod_inventory.md:13`). **UNKNOWN** item
  id; no `cobbledollars:` id appears anywhere in the tracked configs. If the currency is a
  scoreboard/player-data number rather than an item, it cannot be put in a chest at all.
  Worth resolving, because "a purse of 20,000 CobbleDollars" is an excellent cache that
  breaks nothing.
- **Pokeblocks 1.4.0** — **VERIFIED (`mod_inventory.md:116`)** 314 blockstates of *"Pokemon
  figurines, baskets, etc. — decorative blocks"*. **It is decoration, not a reward
  economy.** A rare figurine is still a fine trophy.
- **cobblemon-additions 4.1.6** — **VERIFIED (`mod_inventory.md:60`)** *"Pokemon-themed
  villages/structures (datapack-turned-mod), spawn pools"*, CC0. No `cobblemon-additions:`
  item id appears in the REI index; it looks like structures and spawns only, not items.
- **CobbleCuisine 2.0.1** — food/snack items and a bean crop (`mod_inventory.md:59`); the
  REI index's "Poké Shakes / Cakes / Malasadas / Sandwiches / Salads / Puffs / Curries"
  groups (`collapsible.json5:6890-7079`) are its and Cobblemon's cooking output. Flavour,
  not power.
- **Cobblemon fossils** (`collapsible.json5:608-622`): 15 ids including `helix_fossil`,
  `dome_fossil`, `old_amber_fossil`, `sail_fossil`, `jaw_fossil`. **VERIFIED** the 23 fossil
  *sites* are worldgen features and absent from the export (`WORLDGEN_FEATURES.md:25, 110`),
  so a fossil in a Victory Road cache is currently the only fossil a player will ever see.
  Combined with a resurrection machine at a town, that is a whole optional questline for
  free.
- **Raid dens are gone.** **VERIFIED** `cobblemonraiddens` is removed for Cobblemon 1.8
  incompatibility (`overlay.json:527-535`): *"Raid battles and generated raid-den structures
  are unavailable in the 1.8 target."* Any reward the owner remembers from raid loot tables
  no longer has a source.

---

## 6. How this campaign places a reward today

**Plainly: there is no chest, cache or loot mechanism. None.**

- **VERIFIED** `data/placements.json` has no cache or chest record. Its `kind` vocabulary is
  exactly `town_centre`, `service`, `lab`, `house`, `gym`, `league`, `civic`, `landmark`,
  `donor`, `earthwork` — no reward kind exists.
- **VERIFIED** `data/events.json` **does not exist**. The file-ownership table lists it as
  "Future `data/events.json`" (`docs/STATE.md:140`). The only event material is the retired
  note `data/notes/legacy_events.md`, which mentions an `e4-cache` *"rocket_cache … a hidden
  stash rather than a fight"* (`legacy_events.md:33`) as an idea, with nothing implemented.
- **VERIFIED** `kits/` contains no loot table and no chest prefab; the only match for
  "chest" in the whole of `kits/` is prose in `kits/structures/prefabs/README.md`.
- **VERIFIED** the only loot code in `tools/` **deletes** loot. `tools/place_donor.py:115-128`
  (`loot_commands`) emits `data remove block <x> <y> <z> LootTable` for every container in a
  donor template when the record sets `clear_loot`; `tools/place_town.py:95, 362` does the
  same for houses. `tools/progression_pack.py:233-235` writes **empty** loot tables
  (`{"pools": []}`) to neutralise upstream ones. The campaign's entire relationship with
  loot so far is suppression.
- **VERIFIED** the one reward mechanism that exists is **per-player, via dialogue**:
  `data/quests.json` defines a `grant_reward_once` transition with a `claim_field` and an
  `idempotency_key` (`quests.json:298-302, 578-582`), and a reward is a list of item stacks
  given to the triggering player:
  ```
  "contents": [
    { "item": "cobblemon:black_glasses", "count": 1,
      "verification": "Cobblemon-fabric-1.8.0+1.21.1.jar assets/cobblemon/models/item/black_glasses.json and lang item.cobblemon.black_glasses" },
    { "item": "minecraft:music_disc_cat", "count": 1, "verification": "vanilla Minecraft 1.21.1 item" },
    { "item": "cobblemon:poke_ball", "count": 5, "verification": "..." }
  ]
  ```
  (`data/quests.json:345-361`). Note the `verification` field: **this repo already has a
  convention for proving an item id is real — name the jar path where its model and lang key
  live.** Any new reward data should carry the same field.
  `quests.json:379` even settles the multiplayer question for containers:
  `"shared_chest": "decoration_only"`.

### What a Victory Road cache would have to be built on

Three mechanisms exist in the repo that a cache could use, none of them yet used for loot:

1. **`setblock` + `data merge block` from a generated function.** Proven for Habitat Blocks:
   `tools/habitat_blocks.py:103-104` writes
   `setblock <pos> cobblemon:habitat_block[...] replace` then
   `data merge block <pos> {SpawningStyle:"cobblemon:natural",...}`. The same two commands
   with `minecraft:chest` / `cobblemon:gilded_chest` and an `Items:[...]` payload would place
   a fixed-contents chest. **Cost:** a chest is shared world state. The first player empties
   it. `data/quests.json:374-381` already decided rewards are per-player, so a shared chest
   contradicts the established model for anything that matters.
2. **A `LootTable` on the block instead of `Items`.** Vanilla re-rolls a loot table per
   player only for containers the game treats that way; a plain chest does not. This needs
   research before it is assumed.
3. **`grant_reward_once` behind a dialogue NPC or a trigger.** The only mechanism already
   proven per-player and idempotent (EXP-022). A "cache" could be a visible container that is
   scenery, with the actual grant fired by proximity or by interacting with an NPC/marker.

The re-export problem bites here too: **VERIFIED** a re-export regenerates every region and
entity file, so anything placed by hand is erased (`data/traders.json:4`). Every cache must
therefore be a record in `data/` re-applied by `tools/reapply.py` after each export, exactly
like traders and Habitat Blocks.

---

## Unknowns worth an experiment

1. **Which TM system ships.** TMCraft and native TMs both installed; no decision on file.
   A test must show: does a `cobblemon:technical_machine` teach a move; does a
   `tmcraft:tm_*` still teach under 1.8.0 (`overlay.json:631-633` says untested); do both
   appear in REI at once and confuse players.
2. **The native TM give syntax.** `/give @p cobblemon:technical_machine[cobblemon:tm_move={move:"thunderbolt"}]`
   must be executed. The item id, component id and field name are verified from source; the
   command form and the move-name spelling are not.
3. **The native TM move list.** Read `data/cobblemon/**` out of `Cobblemon-fabric-1.8.0+1.21.1.jar`
   for the TM recipe files; there is no published list.
4. **Are competitive held items obtainable without placement?** Leftovers, Focus Sash,
   Assault Vest, Eviolite, Choice items, Life Orb. Search the 1.8.0 jar for recipes and
   non-structure loot tables. This decides whether a cache is a shortcut or the only source.
5. **CobbleDollars: item or number?** If it is a scoreboard value it cannot go in a chest.
6. **LumyMon League Locator items: what do they do?** Nine Kanto-leader-themed items with
   no documentation, and the best available "one distinctive item per region" candidate.
7. **Per-player caches.** Whether a chest can be made to give each player its contents once
   (loot table re-roll, or a container-shaped `grant_reward_once`). The whole design of
   "caches in Victory Road" turns on this, on a co-op server.
8. **Does the scatter pass land before or after the caches?** If evolution stones, berries,
   mints and apricorns get scattered into the world (`WORLDGEN_FEATURES.md:4`), every one of
   them stops being a reward. Sequence matters.
