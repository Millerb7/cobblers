# Can Oak hand out a mythical at starter strength that grows into itself?

**Answered for:** Cobblemon 1.8.0+1.21.1 (the server's version). Nothing here is checked against 1.7.3.

**Date:** 2026-10-02. **Design-only:** nothing was loaded or run, and no server or world was touched.

**Evidence used.**
- The 1.8.0 jar's species files and class list, extracted to the session scratchpad from
  `C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10/mods/Cobblemon-fabric-1.8.0+1.21.1.jar` (a
  client copy outside the server tree).
- Official source at tag `1.8.0`: `https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/<path>`, shortened below to
  `src:<path>` with the prefix `common/src/main/kotlin/com/cobblemon/mod/common/` dropped.
- Local repo notes.

Source code came through a fetch-and-summarise step. Identifiers, control flow and literal strings were asked for
verbatim. Line numbers are approximate where given.

---

## Short answer

- **Per-species (VERIFIED possible, a poor fit):** a datapack can change Mew's `baseStats` for every Mew, either by
  replacing the species file or through `species_additions`. That nerfs every Mew in the world, the adopted Cobbleverse
  Mew shrine's included.
- **Per-form (VERIFIED mechanism, the right fit):** a datapack can add a new form to Mew with its own `baseStats`,
  selected by an aspect. The aspect is stored on that one Pokémon (`forcedAspects`, in the save codec). Stats are
  recomputed from the form's data every time they are read, so the nerf follows the Pokémon through the party, the PC,
  a trade and a restart, and it ends the moment the aspect is removed.
- **"Growing into itself" (VERIFIED building blocks):** there are four ways to remove the aspect.
  - A form-local `evolutions` entry whose `result` is a properties string on the same species, such as
    `mew unaspect=<x>`. Its `requirements` can include `level` and `advancement`.
  - An `item_interact` evolution.
  - A MoLang callback on `level_up` or `advancement_earned` calling `q.pokemon.apply(...)` or `remove_aspects`.
  - `/pokemonedit`.

  None of these has been run (see the experiments).
- **IVs, EVs and nature alone cannot do it:** at best they pull a 600-BST Mew down to roughly a 496-BST equivalent,
  about a fully evolved starter. The player can undo even that with bottle caps and mints.

---

## 1. Per-species: replacing or patching `species/<name>.json`

**VERIFIED: `species_additions` is a live loader in 1.8.0.**
- The jar has `com/cobblemon/mod/common/pokemon/SpeciesAdditions.class` (scratchpad `classes.txt:364-367`).
- `src:pokemon/SpeciesAdditions.kt` registers `id = cobblemonResource("species_additions")`, `PackType.SERVER_DATA`,
  `resourcePath = id.path`.
- The jar ships no `species_additions` folder of its own. Cobbleverse ships them:
  `COBBLEVERSE-DP-v31.zip` holds `data/cobblemon/species_additions/*.json` (`docs/research/COBBLEVERSE_COMPATIBILITY.md:98`).

**VERIFIED: an addition can set any mutable `Species` property, `baseStats` included.**
- `AdditionParameterAdapter.init` collects every `Species::class.declaredMemberProperties` that is a
  `KMutableProperty` and not `lateinit`.
- `deserialize` reads `"target"` (a resource id, defaulting the namespace), then every other key that names such a
  property, deserialised to that property's type.
- `src:pokemon/Species.kt` declares `var baseStats = hashMapOf<Stat, Int>()`, `var forms = mutableListOf<FormData>()`,
  `var evolutions`, `var labels`, `var implemented`, `var features` and others, all mutable.
- So `baseStats` is an admissible key.
- **NOT RUN:** that a `baseStats` addition deserialises cleanly through the `Stat` adapter.

**VERIFIED: `forms` and `evolutions` append, and every other key replaces.**
- In `reload`: `val appendKeywordsCollection = listOf("forms", "evolutions")`. When the key is one of these, the value
  is `addAll`ed to the existing collection. Otherwise `addition.property.setter.call(species, value)` replaces it.
- Errors are logged per addition (`"Caught exception applying addition {} to {}"`) and skipped.
- An unknown target logs `"Cannot find species {} for addition {}, skipping"`.

**VERIFIED: the order of the species work.**
- In `src:api/pokemon/PokemonSpecies.kt` `init`, `SpeciesAdditions.observable.subscribe { ... }` runs
  `Species::initialize` on every species.
- It then queues the Showdown registry upload (`resetRegistryData("species")`, `sendRegistryData(allShowdownSpecies(),
  "species")`) and emits.
- So additions are applied before initialisation and before Showdown sees the data.

**VERIFIED: how identifiers are keyed and who wins.**
- `src:api/data/JsonDataRegistry.kt` keys every file by **namespace + file name without extension**. Sub-folders are
  dropped. Results go into a `hashMapOf`, so a later key replaces an earlier one.
- Cobblemon's own Mew is `data/cobblemon/species/generation1/mew.json` (fetched at 1.8.0: `"Mew"`, all six base stats
  100, labels `gen1`, `mythical`). Its id is `cobblemon:mew`.
- **Full replacement:** ship the same path in a datapack. Minecraft's pack stack then returns only the top pack's file
  for that path.
- **ASSUMED: a different path with the same file name** (for example `species/mew.json`) gives two resources with the
  same key. Which one wins depends on listing order. Always use the exact path.
- **Two additions for one species:** files at the same namespace and name replace each other by pack order. Files at
  different ids (for example `cobbleverse`'s `cobblemon:celebi` and a hypothetical `cobblers:celebi`) both apply, in
  map iteration order, which is not authored.

**VERIFIED: Cobbleverse adds nothing to Mew.**
- The zip's entry names, which are stored uncompressed, list `species_additions` for 17 mythicals: arceus, celebi,
  darkrai, deoxys, diancie, hoopa, jirachi, keldeo, magearna, manaphy, meltan, pecharunt, phione, shaymin, victini,
  volcanion and zeraora.
- **None for mew, genesect, meloetta, marshadow, melmetal or zarude.** Checked against
  `C:\Users\wnd\Documents\github\cobblers\COBBLEVERSE\datapacks\COBBLEVERSE-DP-v31.zip`.
- So a `cobblers`-namespace Mew addition collides with nothing in Cobbleverse.
- **UNKNOWN:** the contents of those 17 files, which are compressed.

**Why per-species is the wrong lever (VERIFIED consequence):**
- Stats are read from data on every access (§2), so changing Mew's species stats changes every Mew at once.
- That includes the Cobbleverse Mew shrine adopted at `/place template cobbleverse:mythical/mew 7604 142 7082`
  (`data/adopted_legendary_sites.json:51,88`), any raid or trainer Mew, and Showdown's copy.

## 2. Per-form and per-aspect: a "Dormant" Mew

**VERIFIED: a form can carry its own `baseStats`, and stats come from the form.**
- `src:pokemon/FormData.kt`: `@SerializedName("baseStats") _baseStats: MutableMap<Stat, Int>?`, with
  `val baseStats get() = _baseStats ?: species.baseStats`.
- `src:pokemon/stat/CobblemonStatProvider.kt`: `val base = pokemon.form.baseStats[stat]!!`.
- Precedent in the 1.8.0 data:
  - Ursaluna's `Bloodmoon` form (`species/generation8a/ursaluna.json`) has `"aspects": ["bloodmoon"]` and its own
    `baseStats` (113/70/120/135/65/52, against the base 130/140/105/45/80/50).
  - It is driven by the flag feature `species_features/bloodmoon.json` (`{"keys":["bloodmoon"],"type":"flag",
    "isAspect":true,"default":false}`) and assigned by `species_feature_assignments/ursaluna_bloodmoon.json`
    (`{"pokemon":["ursaluna"],"features":["bloodmoon"]}`).
  - Locally, Shaymin's `Sky` form in the jar has its own `aspects` and `baseStats` (scratchpad `species/shaymin.json:152-180`).

**VERIFIED: a datapack can add the form without touching Mew's file.** `forms` appends through `species_additions`
(§1). Then `Species.initialize()` runs:
`this.forms.forEach { it.initialize(this) }; if (this.forms.isNotEmpty() && this.forms.none { it == this.standardForm }) this.forms.add(0, this.standardForm)`.
So Mew, which has no forms today (jar `mew.json` has none), gains its standard form at index 0 followed by ours.

**VERIFIED: how the form is chosen.**
- `Species.getForm(aspects) = forms.lastOrNull { it.aspects.all { it in aspects } } ?: standardForm`.
- `Pokemon.updateForm()` sets `form = species.getForm(aspects)`, and it runs whenever `aspects` changes on the server.
- **Gotcha:** if a Pokémon holds two stage aspects at once, the form listed **later** wins. Every growth step must
  remove the old aspect (`unaspect=`), not only add the new one.

**VERIFIED: a form's aspect can come from a feature or from a plain forced aspect.**
- `Pokemon.updateAspects()`:
  `aspects = AspectProvider.providers.flatMap { it.provide(this) }.toSet() + forcedAspects`.
- `src:pokemon/properties/AspectProperties.kt` defines `aspect=<x>` (`pokemon.forcedAspects += value`) and
  `unaspect=<x>` (`pokemon.forcedAspects -= value`). Both are registered in `src:Cobblemon.kt`:
  `CustomPokemonProperty.register(AspectPropertyType)` and `CustomPokemonProperty.register(UnaspectPropertyType)`.
- A `species_features` flag (as with Bloodmoon) is optional. It only adds the bare-word syntax and the provider.

**VERIFIED: the aspect is saved with the Pokémon.**
- `src:util/codec/internal/PokemonP3.kt` encodes `DataKeys.POKEMON_FORCED_ASPECTS -> forcedAspects` and
  `FEATURES -> features`.
- `PokemonP1.kt` also saves `DataKeys.POKEMON_FORM_ID`.
- `Pokemon.ROOT_CODEC` decodes P1 to P4 and then calls `pokemon.initialize()`.
- The literal NBT key strings were not read.

**VERIFIED: stats are not stored.**
- `Pokemon.kt`: `val attack: Int get() = getStat(Stats.ATTACK)` (the same for HP and every other stat), delegating to
  `Cobblemon.statProvider.getStatForPokemon`.
- No stat-override or stat-modifier field exists. The only "modifier" is `scaleModifier`, which is visual.
- A change of form, or a change to the form's data on `/reload`, takes effect immediately for every Pokémon that has
  it.
- The `form` setter keeps the HP ratio (`val quotient = clamp(currentHealth / maxHealth...)`, then `updateHP(quotient)`).
  It also runs `updateMovesOnFormChange`, clears the evolution proxy and calls `attemptAbilityUpdate()`.

**Trades (VERIFIED):** `src:trade/TradeManager.kt` `performTrade` moves the same object
(`party1.remove(pokemon1)` ... `party2.add(pokemon1)`). The aspect cannot be lost in a trade.

**PC and restart (ASSUMED, strong):**
- PC boxes and party files persist each Pokémon through the same codec that holds `forcedAspects`.
- The PC store's own save path was not read. Experiment E2 settles it.

**ASSUMED: removing our datapack silently un-nerfs every Dormant Mew.** The forced aspect stays, no form matches it,
and `getForm` returns `standardForm`. This follows from the `getForm` code. It was not observed.

**VERIFIED: one hazard.** `form=<name>` exists as a property key (`PokemonProperties.apply`: `pokemon.form = form`). It
sets the form directly, but the next aspect change re-runs `updateForm()` and can revert it. Use `aspect=` and never
`form=`.

## 3. Growing into itself

### 3a. Evolution to the same species (VERIFIED parts, never run)

**What the data can say:**
- `Evolution.result` is a `PokemonProperties` (`src:api/pokemon/evolution/Evolution.kt`).
- `evolutionMethod` does `val sourcePokemon = pokemon.clone(); this.result.apply(pokemon)` on the **same object**.
- Nothing in `test`, `evolve`, `forceEvolve` or `evolutionMethod` requires the species to change.
- So a `result` of `mew unaspect=cobblers_dormant` is admissible by the code. **That it behaves (UI, message, Pokédex)
  is not run (E3).**
- `PokemonProperties.apply` runs `customProperties.forEach { it.apply(pokemon) }`, which is where `aspect=` and
  `unaspect=` act.
- `Pokemon.evolutions = this.form.evolutions.sortedBy { it.optional }`. `FormData.evolutions` is
  `_evolutions ?: mutableSetOf()`, so a form's evolutions are its own and do not fall back to the species'.
- The Dormant form can therefore carry the growth evolution, and standard Mew stays without one.

**Evolution variants in 1.8.0:** `src:pokemon/evolution/adapters/CobbledEvolutionAdapter.kt` registers
`LevelUpEvolution` (`"level_up"`, alias `"passive"`), `TradeEvolution`, `ItemInteractionEvolution` (`"item_interact"`,
field `requiredContext: ItemPredicate`) and `BlockClickEvolution`.
- `LevelUpEvolution`'s no-argument constructor defaults `optional = true` and `consumeHeldItem = true`.
- Poipole's file shows the JSON shape: `"variant": "level_up"`, `"result"`, `"requirements": [{"variant": ...}]`
  (scratchpad `species/poipole.json:122-136`).

**Requirement variants in 1.8.0:** files under `src:pokemon/requirements/`:

> Advancement, Any, Area, AttackDefenceRatio, BattleCriticalHits, Biome, BlocksTraveled, Chance, DamageTaken, Defeat,
> Friendship, HeldItem, Level, MoonPhase, MoveSet, MoveType, OwnerHoldsItem, PartyMember, PokemonProperties,
> PropertyRange, Recoil, StatCompare, StatEqual, Structure, TimeRange, UseMove, Weather, World.

Two are read in full:
- `LevelRequirement`: `ADAPTER_VARIANT = "level"`, fields `minLevel`, `maxLevel`.
- `AdvancementRequirement`: `ADAPTER_VARIANT = "advancement"`, field `requiredAdvancement: ResourceLocation`.
  `checkPlayer` passes when the owner's advancement `isDone`. `checkNPC` always returns `true`, so an NPC-owned copy
  passes.

So "level 20 **and** badge 2" is expressible as a `level_up` evolution with a `level` requirement and an
`advancement` requirement on our own badge advancement.

**UNKNOWN (E3): when a `level_up` evolution is tested.**
- `PassiveEvolution.attemptEvolution` exists, and `evolutionMethod` re-attempts passive evolutions after an evolution.
- The trigger on level-up was **not located**: `Pokemon.addExperience` posts `LEVEL_UP_EVENT` but calls no evolution
  code itself.
- If the test runs only on level-up, a badge earned after the level is reached waits for the next level.

### 3b. Other triggers (VERIFIED existence)

**Item use:**
- `item_interact` evolution: `testContext = requiredContext.test(context.stack)`.
- Reached from `PokemonEntity.attemptItemInteraction` (`lockedEvolutions.filterIsInstance<ItemInteractionEvolution>()`).
- The player uses an item on the sent-out Mew. Requirements such as `advancement` can be added as well.

**MoLang callbacks:**
- `src:events/CallbackHandler.kt` wires `level_up`, `advancement_earned`, `evolution_tested`, `evolution_completed`,
  `starter_chosen`, `trade_event_post`, `pokemon_sent_post` and about 70 more.
- `LevelUpEvent` context: `pokemon` (struct), `old_level`, `new_level`, plus function `set_new_level`.
- `StarterChosenEvent` context: `player`, `pokemon`.
- The Pokémon struct (`src:api/molang/function/PokemonMoLangFunctions.kt`) has `apply`
  (`params.getString(0).toProperties().apply(pokemon)`), `add_aspects`, `remove_aspects`, `set_iv`, `set_ev`,
  `force_evolve`, `can_evolve` and `owner`.
- Callbacks must sit under the `cobblemon` namespace (`docs/research/notes/level-cap-catch-block.md:27-32`, EXP-042).
- **ASSUMED:** `q.pokemon.owner` yields a player value with `has_advancement` (`PlayerMoLangFunctions` per
  `level-cap-catch-block.md:72-75`). The chain was not read.

**Command:**
- `src:command/PokemonEditCommand.kt`: literal `pokemonedit`, alias `pokeedit`, with a variant for another player.
  Arguments are slot then properties. The body runs `properties.apply(pokemon)`. Permissions are
  `POKEMON_EDIT_SELF` and `POKEMON_EDIT_OTHER`.
- `testpartyslot <player> <slot 1-6> <properties>` returns 1 or 0, so `execute if` can use it.
- The exact argument order of the "other" form is ASSUMED. Check it with `/help pokemonedit`.
- Commands can run from functions or from NPC dialogue. NPC script internals were not read.

**Advancement criterion:** the jar has `advancement/criterion/AspectCriterion` (class only), so an advancement may be
able to detect "owns a Pokémon with aspect X". Its JSON fields were not read.

## 4. Per-instance levers and the arithmetic

**Formula (VERIFIED, `src:pokemon/stat/CobblemonStatProvider.kt`):**
- Non-HP: `effectiveNature.modifyStat(stat, ((2*base + iv + ev/4) * level) / 100 + 5)`, integer arithmetic.
- HP: `truncate(truncate(2*base + iv + truncate(ev/4) + 100) * level / 100 + 10)`.
- Shedinja is fixed at 1.
- `iv = ivs.getEffectiveBattleIV(stat)`, so hyper-trained IVs count.

**Levers that exist (VERIFIED):**
- `PokemonProperties` keys `<stat>_iv`, `<stat>_ev`, `nature`, `level`, `held_item`, `min_perfect_ivs`, `tradeable`.
  The stat-name spelling inside `<stat>_iv` was not read.
- MoLang `set_iv`, `set_ev`, `hyper_train_iv`.
- The save codec holds `nature` **and** `mintedNature` (P2).
- No per-instance stat multiplier exists (§2).
- The RCT level cap stops experience at the cap for every Pokémon alike (`level-cap-catch-block.md:3-4`). It is not
  specific to Mew.

**Arithmetic at level 50:** the opponent and the starters have IV 31, EV 0 and a neutral nature.

| Pokémon | BST | HP | Atk | Def | SpA | SpD | Spe | non-HP sum |
|---|---|---|---|---|---|---|---|---|
| Charmander (39/52/43/60/50/65) | 309 | 114 | 72 | 63 | 80 | 70 | 85 | 370 |
| Charizard (78/84/78/109/85/100) | 534 | 153 | 104 | 98 | 129 | 105 | 120 | 556 |
| Mew, IV 31, neutral | 600 | 175 | 120 | 120 | 120 | 120 | 120 | 600 |
| Mew, IV 0, EV 0, hindering nature on one stat | 600 | 160 | 105 | 105 | 105 | 105 | 94 | 514 |

- Converted back to an IV-31 base, the fully nerfed Mew is about 84.5 in HP and four stats and about 74 in the
  hindered one: **roughly 496 BST equivalent**.
- That is level with a fully evolved starter and nowhere near a basic one (309 to 320).
- It also does not hold:
  - EVs come back from every battle (`Generation8EvCalculator`, `BattleEvSource` in the jar).
  - The pack ships **Only Bottle Caps** (`base-pack/inventory/mod_inventory.json:2144-2149`), which ASSUMED raises
    effective IVs.
  - Mints change the effective nature (`mintedNature`). ASSUMED: mints are obtainable here.

**Verdict:** IVs, EVs and nature are flavour, not a nerf. Only the form's `baseStats` can move Mew to starter tier.

Illustrative stage totals (a design choice, not research):
- About 320 BST at the start, matching the basic starters.
- About 420 in the middle, matching the middle stages.
- Then either the standard 600 Mew, or a final form near 530 if Mew should never outclass a fully grown starter.

## 5. The starter config

**VERIFIED: a starter entry is a full properties string.**
- `src:config/starter/StarterCategory.kt`: `val pokemon: List<PokemonProperties>`.
- `CobbledStarterHandler.chooseStarter`: `val pokemon = properties.create(player)`. The only change afterwards is
  shiny, under the `SHINY_STARTERS` gamerule.
- Existing working instances (one instance each, not a schema):
  - `base-pack/cobbleverse/config/cobblemon/starters.json:82` `"Cyndaquil region_bias=hisui level=5 pokeball=ancient_poke_ball"`.
  - `:118` `"Pikachu level=5 cosplay=belle"`.

**ASSUMED:** `"mew level=5 aspect=cobblers_dormant"` creates a Dormant Mew. `aspect` is a registered custom property
and `create` applies properties. Not run (E1).

**VERIFIED: the screen previews `asRenderablePokemon()`.** **ASSUMED:** it renders the base Mew model, because the
aspect has no model variation.

How the list is loaded and merged is in `docs/research/notes/starter-selection.md`. Oak could instead give Mew by
command or dialogue, with the same properties string.

## 6. Battles and clients

**Showdown uses the form's stats (VERIFIED chain).**
- `PokemonSpecies.allShowdownSpecies()` sends one Showdown species per non-standard form.
  - It is named `"<Species>-<form.name>"`.
  - `baseStats` comes from `form?.baseStats?.get(...) ?: species.baseStats[...]`.
  - This is resent on every reload (§1).
- `BattleRegistry.packTeam` writes `pk.showdownId()`. For a non-standard form that is `form.showdownId()` (species id
  plus form id). It also writes nature, EVs, IVs, level and current HP. It sends no computed stats.
- So Showdown computes the battle stats from the form's base stats.
- **ASSUMED:** the form name must make a unique alphanumeric id (`mewdormant`). Not run (E4).

**Clients need no datapack (VERIFIED).**
- `PokemonSpecies.sync` sends `SpeciesRegistrySyncPacket(species.toList())`.
- `Species.encode` writes `baseStats` and `forms`. `FormData.encode` writes `name`, `aspects` and `baseStats` (among
  others).
- A player's client therefore receives the server's merged species, our added form included.
- `SpeciesAdditions.sync` is empty because the additions are already in the synced species.
- **ASSUMED:** the summary screen and stats show the nerfed values, and the Pokédex stats widget shows standard Mew's
  (the custom form has no `dex_entries` entry). The form-name label may show a raw translation key. All of this is E4.

## 7. Side effects

**Global override (file or `species_additions` `baseStats`):**
- Every Mew changes: the shrine Mew (`data/adopted_legendary_sites.json:88`), any Cobbleverse RCT or raid Mew, the
  Pokédex.
- A full file replacement also freezes Mew at our copy across Cobblemon updates.

**Form approach:**
- Only aspect-bearing Mews change.
- `FormData.labels` is `_labels ?: species.labels` (VERIFIED), so the Dormant form stays `mythical` unless it lists its
  own labels.
- `moves`, `abilities` and `pokedex` likewise fall back to the species unless set.

**Other addons:**
- No authored file in this repo matches `label=mythical` or `"mythical"`, outside `base-pack/` (grep 2026-10-02).
- The Cobbleverse configs mention neither word in a relevant way. `rctmod-server.toml:97` is a dimension blacklist.
- Mega Showdown, LumyMon, Legendary Monuments and the compressed Cobbleverse/RCT datapacks were **not** inspected for
  Mew or label rules. **UNKNOWN.**
- Mew has no mega, so a Mega Showdown collision is unlikely. ASSUMED.

**Breeding:** Mew is `eggGroups: ["undiscovered"]` (jar `mew.json:21-23`).

**Which mythicals render on this pack:**
- **Mew** (Cobblemon native, `implemented: true` in the bare jar) and **Zarude** (`implemented: true`) are not in the
  doll list.
- Dolls, until the client fix ships (`docs/STATE.md:502-506`, `docs/research/CLIENT_MODEL_FIXES.md:96-104`):
  - jirachi, manaphy, phione and pecharunt have no resolver;
  - magearna and zeraora have only a mega resolver.
- celebi, deoxys, darkrai, shaymin, arceus, victini, keldeo, diancie, hoopa, volcanion and meltan are enabled by
  Cobbleverse additions and were not flagged. ASSUMED to render.
- genesect, meloetta, marshadow and melmetal have no Cobbleverse addition and `implemented` is not true in the bare jar.
  ASSUMED unimplemented.

**Mew is the safest candidate.**

## 8. Existing per-instance stat scaling in the pack

**None found:**
- No description in `base-pack/inventory/mod_inventory.json` mentions stat scaling.
- The closest are Only Bottle Caps (which raises IVs, the opposite direction) and Raid Dens. The raid bosses' scaling
  does not touch player Pokémon and was not examined.
- Cobblemon 1.8.0 itself has no stat multiplier.
- **UNKNOWN:** whether 1.8's alpha flag (`isAlpha`, P3) changes stats.

---

## Experiments needed before building (designed, not run)

**E1. Load and create (the gate).**
- **Objective:** Mew gains a Dormant form from a data-only addition, and a starter or command can create it.
- **Steps:**
  1. On a staging server, add `data/cobblers/species_additions/mew.json`: `target` `cobblemon:mew`, `forms` holding one
     form, `name` `Dormant`, `aspects` `["cobblers_dormant"]`, `baseStats` totalling about 320, `evolutions` `[]`.
  2. Boot, and grep the log for `Caught exception applying addition` and `Finished additions`.
  3. Run `/pokegive <p> mew level=5 aspect=cobblers_dormant` and a plain `mew level=5`.
- **Pass:**
  - No addition error.
  - The summary screen shows the nerfed stats on the first Mew only.
  - Stats match the formula with the form's bases.
- **Fail:** an exception, or both Mews identical.

**E2. Persistence.**
- **Objective:** the nerf survives the PC, a trade, a restart and `/reload`.
- **Steps:**
  1. Box the Dormant Mew, restart the server, take it out.
  2. Trade it between two players with Cobblemon trade.
  3. Run `/reload`.
- **Pass:** stats identical after each step.
- **Fail:** standard stats at any point.

**E3. Growth trigger.**
- **Objective:** a same-species "evolution" removes the aspect, and we learn when it fires.
- **Steps:**
  1. Give the Dormant form a `level_up` evolution with `result` `mew unaspect=cobblers_dormant`, requirements `level`
     `minLevel` 10 and `advancement` on a test advancement.
  2. Level it to 10 without the advancement, grant the advancement, then level again.
  3. Repeat with an `item_interact` variant.
  4. Repeat with a `cobblemon` callback on `level_up` calling `q.pokemon.apply('unaspect=cobblers_dormant')`.
- **Record:**
  - whether the evolve prompt or button appears (optional);
  - whether the evolution waits for the next level;
  - the message text ("evolved into Mew");
  - whether moves or ability change.
- **Pass:** stats become standard exactly once, at the intended moment.
- **Fail:** no trigger, a crash, or a loop.

**E4. Battle and client.**
- **Objective:** Showdown and the clients agree with the server.
- **Steps:**
  1. Battle the Dormant Mew against a fixed NPC and compare the damage taken and dealt with a calculator using the
     Dormant bases.
  2. Join with a client that has no extra datapack, and screenshot the summary, the Pokédex and the battle HP.
- **Pass:** the damage matches the Dormant bases, and the client stats equal the server's.
- **Fail:** standard-Mew damage, which would mean Showdown used the base species.

**E5. Starter entry.**
- **Steps:** add `"mew level=5 aspect=cobblers_dormant"` to a staging `starters.json` category and choose it.
- **Pass:** a Dormant Mew in the party, previewed with the normal Mew model.

**E6. Side effects.**
- **Steps:**
  1. With the addition loaded, spawn a Mew from the shrine chain and a plain `/pokespawn mew`.
  2. Confirm both have standard stats.
  3. Grep the Mega Showdown, LumyMon, Legendary Monuments and RCT jars and datapacks (entry names) for `mew` and
     `mythical`.

Per the brief, these were not added to `docs/research/EXPERIMENT_BACKLOG.md` or `CAPABILITY_MATRIX.md`. That remains to do.

## Verdict

A nerfed mythical that grows **looks possible with data alone**, on Cobblemon-native mechanisms and in the
preferred order: Cobblemon native, then datapack.
- A `cobblers`-namespace `species_additions` file appends one or more low-stat forms to Mew, each keyed by a forced
  aspect.
- Oak, or the starter config, hands out `mew level=5 aspect=cobblers_dormant`.
- Stats are recomputed from the form on every read, and the aspect is saved with that one Pokémon, so the nerf follows
  it through the PC, trades and restarts. Every other Mew is untouched.
- Showdown and the clients receive the form's base stats from the server.
- Growth is a same-species `level_up` or `item_interact` "evolution" whose result removes the aspect, gated by `level`
  and `advancement` requirements. A `level_up` MoLang callback or `/pokemonedit` is the fallback.

Every link of that chain is VERIFIED in the 1.8.0 source. **The whole has never been loaded.** E1 (the addition
loads and the form takes effect) and E3 (when and how the same-species evolution fires) decide it. Until they pass,
treat the feature as feasible-on-paper, not working.

Sources (1.8.0): the files named above under
`https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/` and
`.../common/src/main/resources/data/cobblemon/`. Directory listings came from
`https://gitlab.com/api/v4/projects/cable-mc%2Fcobblemon/repository/tree?ref=1.8.0`.
