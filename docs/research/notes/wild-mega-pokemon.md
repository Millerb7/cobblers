# Wild Mega Pokémon: can the southern Rift's mega stone mine have wild, uncatchable, enraged Megas?

Researched 2026-09-25 for the owner's request (EXP-035 item 22,
`experiments/EXP-035-first-playtest/README.md:48`; `docs/STATE.md:99`).

**Versions the answer is for, and the sources actually read:**

| Component | Pinned in this pack | Source read | Gap |
|---|---|---|---|
| Cobblemon | 1.8.0+1.21.1 | GitLab tag `1.8.0` (code and stock data) | none |
| Mega Showdown (MSD) | `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar` (`modpack/manifest/overlay.json:215`) | GitHub `yajatkaul/CobblemonMegaShowdown` branch `main` @ `c17d327`, whose `gradle.properties` says `mod_version=1.1.3+1.8+1.21.1-release`, `cobblemon_version=1.8.0+1.21.1` | **The repo has no tags**, so 1.0.2 source was not reachable. Every MSD code fact below is VERIFIED for 1.1.3 `main` and ASSUMED for 1.0.2 |
| Fight or Flight Reborn (FoF) | `fightorflight-fabric-0.11.0.jar` (`overlay.json:482-492`) | GitHub `LyquidQrystal/fightorflight` branch `master` @ `cff0fdef`, `mod_version=0.11.1`, `cobblemon_version=1.8.1+1.21.1` | 0.11.0 not tagged; same caveat. Config values come from the Cobbleverse 0.10.9 file (`base-pack/cobbleverse/config/fightorflight.json5`) |
| RCT | 0.19.0-beta | RCT docs `latest` (no version printed) and `0.16` | docs version ≠ pinned version |

**The jars were not opened in this session** (no shell tool was available; mod jars are
gitignored). Jar-level facts below are quoted from earlier repo reads that did open them
(`docs/world-building/WORLDGEN_FEATURES.md`). Nothing here has been run in Minecraft.

## Verdicts

| # | Question | Answer | Status |
|---|---|---|---|
| 1 | Can a wild Pokémon exist in Mega form? | **Yes at the data level.** A Mega is not a species and not only a battle event: it is the species feature `mega_evolution` (a choice: `mega`, `mega_x`, `mega_y`, plus `mega_z` in MSD `main`), which Cobblemon 1.8.0 itself defines and assigns to 46 species, and whose aspect selects a Mega form. A spawn's `pokemon` string can set it (`charizard mega_evolution=mega_x`); nothing in MSD reverts a wild Pokémon | Mechanism VERIFIED in source; never spawned or battled in game |
| 2 | Uncatchable from a spawn pool, not only a command? | **Yes, by the same mechanism**: `uncatchable` is a Cobblemon property, and a spawn's `pokemon` field is a property string. In this pack FoF also refuses Poké Balls thrown at a wild Pokémon that is currently hostile | Property VERIFIED (EXP-023 proved it via command); spawn-pool form ASSUMED (strong) |
| 3 | Enraged | **Yes, with one config line and a dark mine.** FoF's `always_aggro_aspects` matches `pokemon.getAspects()`, so adding `mega`, `mega_x`, `mega_y` makes every Mega-form wild Pokémon hostile. Unprovoked attack still needs level ≥ 25 and darkness in this pack's config. FoF has no per-entity or per-area switch except biome lists and a global Y threshold. A battle on contact is `force_wild_battle_on_player_hurt` (global, off today) | VERIFIED in FoF source + local config; behaviour not run |
| 4 | Stones, species, ores | 46 classic Mega species natively; MSD 1.0.2 ships 83 Mega Stones (Z-A ones included). Stones are **crafted** from raw `mega_showdown:mega_stone`, which drops only from the `mega_stone_crystal` block. That block is the mine's natural "ore". Spawn conditions can require nearby or base blocks, so a spawn can be tied to that block | VERIFIED (repo jar reads + source); the block-condition JSON syntax is ASSUMED |
| 5 | Alternatives | Ranked below. The true wild Mega is the most faithful option and among the cheapest. It rests on one unknown: how a Mega-form wild behaves once a battle starts | ranking is a judgement (ASSUMED) |

---

## 1. How Mega forms are represented

- **VERIFIED (Cobblemon 1.8.0).** `data/cobblemon/species_features/mega_evolution.json` is
  `"type": "choice", "keys": ["mega_evolution"], "default": "none", "choices": ["mega", "mega_x", "mega_y"], "isAspect": true, "aspectFormat": "{{choice}}"`
  ([feature][cfeat]). `species_feature_assignments/mega_evolution.json` assigns it to 46
  species: venusaur, charizard, blastoise, beedrill, pidgeot, alakazam, slowbro, gengar,
  kangaskhan, pinsir, gyarados, aerodactyl, mewtwo, ampharos, steelix, scizor, heracross,
  houndoom, tyranitar, sceptile, blaziken, swampert, gardevoir, sableye, mawile, aggron, medicham,
  manectric, sharpedo, camerupt, altaria, banette, absol, glalie, salamence, metagross, latias,
  latios, rayquaza, lopunny, garchomp, lucario, abomasnow, gallade, audino, diancie ([assign][cassign]).
- **VERIFIED (Cobblemon 1.8.0).** The Mega forms are ordinary forms in the stock species files.
  `generation1/charizard.json` has `Mega-X` with `"aspects": ["mega_x"]` and `Mega-Y` with
  `["mega_y"]`, both `"battleOnly": true` ([charizard][cchar]). `FormData.kt` 1.8.0 has **no**
  `battleOnly` field, so Cobblemon's form class does not read that key. Whether any other
  Cobblemon code reads it was not traced (GitLab code search needs a login). A form's
  `showdownId()` is species id + form name, so Mega-X gives `charizardmegax` ([FormData][cform]).
- **VERIFIED (MSD `main`).** MSD overrides the same file and adds a fourth choice, `mega_z`
  ([msd feature][msdfeat]). It adds Z-A Megas as `species_additions` that attach the feature and
  a form `"aspects": ["mega"]`, for example `dragonite_mega.json` ([msd dragonite][msddrag]). In
  this pack the Z-A set arrives through `zamega` 1.7.7+1.8 (`overlay.json:476`). Which Z-A files
  are in MSD 1.0.2 and which are in zamega was not checked.
- **VERIFIED (MSD `main`), how MSD Mega-evolves.** `MegaGimmick.megaEvolve` applies the
  held stone's aspects (e.g. `mega_evolution=mega`) through `AspectUtils.applyAspects`. That
  method splits on `=` and applies a `StringSpeciesFeature`. It then sets persistent-data flag
  `is_mega` and makes the Pokémon untradeable. `unmegaEvolve` applies `mega_evolution=none`
  ([MegaGimmick][msdgim], [AspectUtils][msdasp]).
- **VERIFIED (MSD `main`): reverting only ever touches players' Pokémon.** Battle end:
  `battle.getPlayers().forEach(AspectUtils::revertPokemonsIfRequiredBattleEnd)`. Battle start:
  `event.getBattle().getPlayers()` → `revertPokemonsIfRequiredBattleStart(playerPartyStore)`,
  which reverts only if `is_mega` is set. `MinecraftEvents` has no entity spawn or load hook
  ([CobbleEvents][msdcev], [MinecraftEvents][msdmev]). **Consequence: a wild Pokémon spawned
  with the feature has no `is_mega` flag and is outside every revert path. It should stay Mega
  indefinitely** (ASSUMED: persistence of species features across unload/restart is not tested
  here, although EXP-023 saw a spawn property survive a restart,
  `experiments/EXP-023-sleeping-celebi/README.md:50`).
- **VERIFIED (local config, 1.7.42).** `"outSideMega": true` (`base-pack/cobbleverse/config/mega_showdown/config.json:16`).
  The key name suggests that players' Megas also exist outside battle. Its behaviour was not
  read (ASSUMED).

### Can a spawn produce one?

- **VERIFIED (Cobblemon 1.8.0), parsing.** `PokemonProperties` builds key pairs; a bare token
  is `(token, null)`; custom properties match when `it.first.lowercase() in property.keys`
  ([PokemonProperties][cprops]). `ChoiceSpeciesFeatureProvider.fromString(value)` returns a
  feature only if `value` is in `choices` ([Choice][cchoice]). So `mega_evolution=mega_x` is the
  form. Bare `mega_x` is not a key and is ASSUMED to be ignored.
- **VERIFIED precedent in shipped data.** MSD's own `spawn_pool_world/0774_minior.json` uses
  `"pokemon": "minior meteor_shield=meteor"`, which sets another choice feature from a spawn
  entry ([minior][msdminior]).
- **ASSUMED (strong): route/`spawn_pool_world` entry:**
  `"pokemon": "charizard mega_evolution=mega_x uncatchable"` spawns a wild Mega Charizard X.
  **Habitat pool entry:** `"species": "Charizard", "modifiers": "mega_evolution=mega_x uncatchable"`.
  `modifiers` is typed `PokemonProperties` (`docs/research/notes/habitat-blocks-underground.md:95`),
  and the Habitat Block also has a block-wide `Modifiers` NBT key (`…habitat-blocks-underground.md:139-141`).
  **Command:** `spawnpokemonat <pos> charizard level=60 mega_evolution=mega_x uncatchable`.
- **Pitfall (VERIFIED from the data above).** The value must match the species' form aspect:
  `mega` for single-Mega species, `mega_x`/`mega_y` for Charizard and Mewtwo. `mega` on a
  Charizard matches no form: it would render in base form but still carry the `mega` aspect,
  so it would still be enraged (§3). A block-wide `Modifiers: "mega_evolution=mega"` on a Habitat
  Block therefore breaks those two species.
- **Our generator today (VERIFIED).** Route and sub-region entries copy `e["species"]` straight
  into `"pokemon"` (`tools/compile_spawns.py:213, 239`), so a property string would pass through.
  The id at `:211` is built from the raw string, so an id containing `=` and spaces is possible.
  Whether Cobblemon accepts such ids is not verified. `compile_habitat` emits no `modifiers`
  (`tools/compile_spawns.py:254-257`), so the habitat route needs a generator change.

## 2. Uncatchable

- **VERIFIED (Cobblemon 1.8.0).** `pokemon/properties/UncatchableProperty.kt` registers
  `"uncatchable"`, a flag property. `isCatchable` is `!PokemonProperties.parse(keys.first()).matches(pokemonEntity)`
  ([Uncatchable][cunc]).
- **VERIFIED in game (EXP-023, Cobblemon 1.8.0 + COBBLEVERSE stack).** `spawnpokemonat … uncatchable`
  refuses the ball with "it cannot be caught" and survives a restart
  (`experiments/EXP-023-sleeping-celebi/README.md:26-31, 50`).
- **ASSUMED (strong)**: the same token in a spawn-pool `pokemon` string or habitat `modifiers`
  has the same effect, because both are parsed as `PokemonProperties`. Not yet run.
- **VERIFIED (FoF `master`) second lock:** with `aggressive_pokemon_catchable` false (this pack:
  `fightorflight.json5:13`), `EmptyPokeBallEntityMixin` calls `drop(); ci.cancel();` when
  `shouldFightTarget(pokemonEntity) && getTarget(pokemonEntity) != null`. This covers only a
  Pokémon that is hostile right now ([FoF ball mixin][fofball]). It is not a substitute for
  `uncatchable`.
- **Why uncatchable is mandatory, not flavour (ASSUMED, from §1):** a wild-spawned Mega has no
  `is_mega` flag, so if it were ever caught, MSD would never revert it. The player would own a
  permanent Mega with no stone.

## 3. Enraged: what makes a wild Pokémon attack in this stack

**VERIFIED (FoF `master`), decision order** in `CobblemonFightOrFlight.getFightOrFlightCoefficient`
([FoF main][fofmain]):

1. `do_pokemon_attack` false → peaceful.
2. `alpha_always_aggressive && pokemon.isAlpha()` → aggressive. This key is new in `master`, is
   absent from the 0.10.9 config, and is unverified for 0.11.0.
3. species in `never_aggro` or `always_flee` → peaceful.
4. species in `always_aggro`, **or any of `pokemon.getAspects()` in `always_aggro_aspects`**,
   or `y < always_aggro_below` → aggressive.
5. biome registered name in `peaceful_biome` / `neutral_biome` / `aggressive_biome`.
6. otherwise the calculated score: level, attack−defence, nature, light for Dark/Ghost, size.

**VERIFIED (FoF `master`), gates on the unprovoked attack itself**, applied after the score
([sensor][fofsensor], [PokemonUtils][fofutils]):
- `do_pokemon_attack_unprovoked`, `!isPlayerOwned()`, and `level >= minimum_attack_unprovoked_level`;
- when `light_dependent_unprovoked_attack` is on, no attack if
  `entity.getLightLevelDependentMagicValue() >= 0.5f`. **This gate applies even to an
  `always_aggro` Pokémon.** ASSUMED from memory of vanilla's brightness curve: 0.5 falls at a
  raw light of about 12, so the mine must stay at light ≤ 11 where a Mega should attack.
- targets are players not in creative or spectator mode.

**This pack's values (VERIFIED local, Cobbleverse 1.7.42 file for FoF 0.10.9):**
`do_pokemon_attack_unprovoked: true` (`fightorflight.json5:5`),
`light_dependent_unprovoked_attack: true` (`:7`), `minimum_attack_unprovoked_level: 25` (`:17`),
`always_aggro_below: -99.0` (`:41`), `always_aggro_aspects: ["alpha"]` (`:98-100`),
`always_aggro` includes `gyarados`, `beedrill` among others (`:102-121`),
`force_wild_battle_on_player_hurt: false` (`:231`), `force_wild_battle_on_pokemon_hurt: true` (`:227`).
**Finding:** `aggressive_biome` is malformed: `["", "minecraft", ":deep_dark", ""]`
(`:91-96`). No biome registered name equals any of those strings, so the deep dark is **not**
forced aggressive in this pack. The intent was surely `"minecraft:deep_dark"`.

**Answers:**
- **Does FoF treat Megas specially?** No. The source has no Mega logic and no config key
  containing `mega` (VERIFIED, config model). A Mega is judged by species and aspects like
  anything else.
- **Recommended lever (VERIFIED mechanism, not run):** add `"mega"`, `"mega_x"`, `"mega_y"`
  (and `"mega_z"` if MSD 1.0.2 has it) to `always_aggro_aspects`. Wild Megas exist only where we
  spawn them, so this is effectively area-scoped. Player-owned Megas are excluded from
  unprovoked attack by `!isPlayerOwned()`. Keep the mine dark (≤ 11) and every Mega at level
  ≥ 25, or both gates block it.
- **Per spawn / per area, other levers:** `always_aggro_below` (global Y: every Pokémon below
  that Y, pack-wide); `aggressive_biome` (needs a mine-only biome; EXP-011 is still proposed);
  `always_aggro` by species (global, hits every wild member of the species). **FoF has no
  per-entity NBT, tag or datapack switch.** `data/behavior/PokemonBehaviorData` (datapack folder
  `fof_behavior_data/normal`) is marked `@Deprecated` in source and was not used as evidence
  ([behavior][fofbeh]).
- **Forced battle on contact:** `force_wild_battle_on_player_hurt` → `pokemonTryForceEncounter`
  → `BattleBuilder.pve(player, wild, …, GEN_9_SINGLES)` if `canBattlePlayer` ([PokemonUtils][fofutils]).
  It is global: every wild Pokémon that hits a player anywhere starts a battle. Off in this pack.
  A mine-only forced battle has no FoF switch; it would need a command or function trigger.
- **Cobblemon-native aggression (VERIFIED wiki, updated 2026-09-18; 1.8.0 changelog):** Alphas
  "will always attempt to defend themselves… They do not attack unprovoked"; the changelog says
  "more aggressive" ([Alpha wiki][alpha], [changelog][cchg]). Property keys `alpha` / `is_alpha`
  ([PokemonProperties][cprops]). Alphas get aspect `alpha`, which this pack's FoF config already
  lists in `always_aggro_aspects`. Alphas also scale "+4 to +20 levels" above the party's highest
  level (wiki), which fights a level-capped campaign.
- **Risk, VERIFIED in game on this stack:** a player can kill a Pokémon entity with a sword
  (`experiments/EXP-023-sleeping-celebi/README.md:39-45`). FoF also lets player Pokémon kill wild
  ones outside battle for 0.25× EXP (`fightorflight.json5:173`). Enraged Megas will be fought in
  the overworld as often as in battles.

## 4. Stones, species and the mine's blocks

- **VERIFIED (jar read of MSD 1.0.2, `docs/world-building/WORLDGEN_FEATURES.md:59-61`):** 83 Mega
  Stones, each *crafted* from `mega_showdown:mega_stone` plus a type item, iron and a diamond. Raw
  `mega_stone` drops only from the `mega_showdown:mega_stone_crystal` block, found only in the
  `mega_site` template. The Key Stone comes only from `mega_showdown:keystone_ore` in `megaroid`.
  The Mega Bracelet is crafted from the Key Stone, white apricorns, diamond and iron.
- **VERIFIED (MSD `main` generated loot tables):** `mega_stone_crystal` drops
  `mega_showdown:mega_stone` (itself with Silk Touch) ([crystal loot][msdcrys]).
  `mega_meteorid_fire_ore` drops **`cobblemon:fire_stone`**, not a Mega Stone ([meteorid loot][msdmet]).
  The ten meteorid ores are evolution-stone ores ASSUMED by analogy (only fire was read).
- The 47 stone ids in the 1.7.42 index are listed at `docs/research/notes/reward-item-inventory.md:375-385`.
  Z-A stones make up the rest of the 83 (not enumerated here).
- **Mine palette:** `mega_stone_crystal` as the "ore" (the only real Mega Stone source),
  `keystone_ore` for one Key Stone vein, and `mega_meteorid_*` blocks and bricks as decoration
  (`reward-item-inventory.md:425-428`). **WorldPainter worldgen does not place any of these**
  (`WORLDGEN_FEATURES.md:6-9, 71-72`). They must be placed, and pasted templates keep their
  blocks (EXP-013, `WORLDGEN_FEATURES.md:72`).
- **Can blocks decide spawns? Yes, in route pools (VERIFIED field exists, Cobblemon 1.8.0):**
  area conditions have `neededNearbyBlocks`; `grounded` has `neededBaseBlocks`
  (`docs/research/notes/underground-biomes.md:111-113`). The JSON form (array of block ids or
  `#tags`) and the "nearby" radius are ASSUMED/not traced. Habitat pools cannot carry these
  conditions (`habitat-blocks-underground.md:105-110`). Their only gates are
  `timeRange`, `minLight` and `maxLight`.
- MSD's own advancements use `location_check` on structures and will not fire at pasted sites
  (`WORLDGEN_FEATURES.md:73-75`).

## 5. Alternatives, ranked (ASSUMED judgement; mechanisms cited above)

| Rank | Option | Fidelity | Effort | Proven parts | Main risk |
|---|---|---|---|---|---|
| 1 | **True wild Megas from a route `spawn_pool_world` file** bounded to the mine (coordinate box and/or `neededNearbyBlocks: mega_stone_crystal`), `pokemon: "<species> mega_evolution=<choice> uncatchable"`, plus `always_aggro_aspects += mega, mega_x, mega_y`, mine lit ≤ 11, levels ≥ 25 | Full | Low: data plus one overlay config line (`modpack/config/fightorflight.json5` does not exist yet) | `uncatchable` (EXP-023); FoF aspect match (source) | **What a Mega-form wild does in battle** (Showdown receives e.g. `charizardmegax` as a starting species: does it fight as the Mega, revert, or error?). Untested |
| 2 | Same, via a Habitat Block pool with per-spawn `modifiers` | Full | Low-medium: `compile_habitat` must emit `modifiers` | Habitat Block influence (EXP-021); underground spawning (EXP-028/033) | as 1; plus the sphere-shaped influence in a winding mine |
| 3 | Placed "guardian" Megas from a re-applied function (`spawnpokemonat … mega_evolution=… uncatchable`, `PersistenceRequired`) | Full for set-pieces, not ambient | Low: scenes pack already does this (`tools/scenes_pack.py:12, 35, 220`) | command path (EXP-023/034) | as 1; killable by sword (EXP-023) |
| 4 | Base-form wild **holding its Mega Stone** (`held_item=mega_showdown:<stone>`) in the hope it Mega-evolves in battle | Medium | Low | property key `held_item` (source) | Whether the wild battle AI chooses to Mega-evolve is unknown. ASSUMED risk: MSD's `megaEvolution` handler passes `pokemon.getOwnerPlayer()` (null for a wild Pokémon) to an advancement helper. A null guard was not seen, but the helper itself was not read ([CobbleEvents][msdcev]). The stone may also leak as loot (not verified) |
| 5 | **Alpha** base-form Pokémon (`alpha`), already hostile via this pack's `always_aggro_aspects: ["alpha"]` | Low (not a Mega) | Lowest | native 1.8.0 | level scaling above the party breaks caps; Alphas lead herds |
| 6 | **RCT trainer** in the mine whose team holds Mega Stones | Medium (a real Mega evolution, but a trainer) | Medium: `data/trainers.json` plus placement | RCT docs: "Mega Evolutions or Z-Moves will be activated by corresponding held items" ([RCT latest][rct], 0.16 same) | docs are not versioned to 0.19.0-beta; not wild, not aggressive |
| 7 | Cobblemon NPC scripted encounter | Medium | High | none | no evidence gathered |

## Unknown / experiment candidates

Proposed **EXP-036 Wild Mega encounter** (added to `EXPERIMENT_BACKLOG.md`). On a disposable
world with the pinned 1.8 stack:

1. `spawnpokemonat ~ ~ ~ gengar level=40 mega_evolution=mega uncatchable` and
   `charizard mega_evolution=mega_x`. Does it render as the Mega model? Read back aspects and the
   species feature. Unload the chunk, restart, and check again.
2. Battle it. Does the battle start? Does the wild fight with Mega stats and ability (Gengar-Mega
   has Shadow Tag), revert, or throw a Showdown error? After the battle, is it still Mega? Is
   anything in the log from MSD?
3. Throw a ball. `uncatchable` should refuse it.
4. One-entry route `spawn_pool_world` file with the same string, sampled with `/checkspawn` and
   real spawns. Then one habitat pool entry with `modifiers`. Record the exact accepted id format.
5. Overlay `always_aggro_aspects` with `mega`, `mega_x`, `mega_y`: unprovoked attack at light ≤ 11
   and none at light ≥ 12. Check that a player-owned Mega nearby is unaffected.
6. `held_item=mega_showdown:gengarite` on a base-form wild: does it Mega-evolve in battle? Any
   exception? Is the stone dropped on KO?
7. Read the 1.0.2 jar to confirm `mega_z` presence, the `CobbleEvents` handlers, and that the
   `species_features/mega_evolution.json` override matches `main`.
8. `neededNearbyBlocks` with `mega_showdown:mega_stone_crystal`: accepted syntax and radius.

## Sources

[cfeat]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/species_features/mega_evolution.json
[cassign]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/species_feature_assignments/mega_evolution.json
[cchar]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/species/generation1/charizard.json
[cform]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/pokemon/FormData.kt
[cprops]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/pokemon/PokemonProperties.kt
[cchoice]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/pokemon/feature/ChoiceSpeciesFeatureProvider.kt
[cunc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/pokemon/properties/UncatchableProperty.kt
[cchg]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/CHANGELOG.md
[alpha]: https://wiki.cobblemon.com/index.php/Pok%C3%A9mon/Alpha
[msdfeat]: https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/resources/data/cobblemon/species_features/mega_evolution.json
[msddrag]: https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/resources/data/cobblemon/species_additions/dragonite_mega.json
[msdminior]: https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/resources/data/cobblemon/spawn_pool_world/0774_minior.json
[msdgim]: https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/java/com/github/yajatkaul/mega_showdown/gimmick/MegaGimmick.java
[msdasp]: https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/java/com/github/yajatkaul/mega_showdown/utils/AspectUtils.java
[msdcev]: https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/java/com/github/yajatkaul/mega_showdown/event/CobbleEvents.java
[msdmev]: https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/main/java/com/github/yajatkaul/mega_showdown/event/MinecraftEvents.java
[msdcrys]: https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/generated/data/mega_showdown/loot_table/blocks/mega_stone_crystal.json
[msdmet]: https://github.com/yajatkaul/CobblemonMegaShowdown/blob/main/common/src/generated/data/mega_showdown/loot_table/blocks/mega_meteorid_fire_ore.json
[fofmain]: https://github.com/LyquidQrystal/fightorflight/blob/master/common/src/main/java/me/rufia/fightorflight/CobblemonFightOrFlight.java
[fofsensor]: https://github.com/LyquidQrystal/fightorflight/blob/master/common/src/main/java/me/rufia/fightorflight/entity/ai/sensors/PokemonWildProactiveSensor.java
[fofutils]: https://github.com/LyquidQrystal/fightorflight/blob/master/common/src/main/java/me/rufia/fightorflight/utils/PokemonUtils.java
[fofball]: https://github.com/LyquidQrystal/fightorflight/blob/master/common/src/main/java/me/rufia/fightorflight/mixin/EmptyPokeBallEntityMixin.java
[fofbeh]: https://github.com/LyquidQrystal/fightorflight/blob/master/common/src/main/java/me/rufia/fightorflight/data/behavior/PokemonBehaviorData.java
[rct]: https://srcmc.gitlab.io/rct/docs/latest/configuration/data_pack/trainers/
