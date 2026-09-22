# Caught-count gates and Cobblemon NPCs as walkway guards

Answered for **Cobblemon 1.8.0 on Minecraft 1.21.1 Fabric** (researched 2026-09-21). Unless stated otherwise, the source is
the Cobblemon repository at tag `1.8.0` (tagged 2026-09-06; `1.8.1` followed on 2026-09-13 and was not checked):
`https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/<path>`. The paths below are relative to `common/src/main/`.
The local jars in `cobblers-server/mods` were **not** read. This session had no shell, so it could not do the
server-safety process/port check and lock that must come before anything touches the server tree. Every source fact
here comes from the upstream source at the tag, not from the jar that is actually deployed.

## Summary

**Q1: caught-count gates are possible with no custom mod.** Cobblemon 1.8.0 has three native mechanisms:
- **Distinct species owned:** the Molang call `q.player.pokedex.caught_count` (VERIFIED key, ASSUMED call form). It
  counts species whose Pokedex knowledge is `OWNED`. Starters, trades, gifts and eggs count too, not only ball catches.
- **Total ball captures, advancement:** the trigger `cobblemon:catch_pokemon` with the conditions `{"count": N}` and an
  optional `"type"`. Its `count` is compared with the player's running capture total (VERIFIED). A reward function can
  then add a tag.
- **Total ball captures, statistic:** the custom stat `cobblemon:captured`, readable in Molang as
  `q.player.get_custom_stat('cobblemon:captured')` (VERIFIED) and, ASSUMED, as the scoreboard criterion
  `minecraft.custom:cobblemon.captured`.
- **Recommendation:** have the gate NPC's dialogue check the count at the moment the player talks, using
  `q.player.pokedex.caught_count` for species gates or `get_custom_stat` for capture gates. Both read stored totals, so
  they include catches made before the gate existed and need no background ticking. Use the advancement only when
  something must happen as soon as the player crosses the threshold. Scoreboard stat objectives are the weakest
  option, because they probably do not include catches made before the objective was created.

**Q2: a Cobblemon NPC is a poor physical wall.**
- `isInvulnerable` defaults to `false` and `isMovable` to `true` (VERIFIED). Both can be set per NPC class. The
  project's compiler already sets `isInvulnerable: true`, `isMovable: false`, `canDespawn: false`, `isLeashable: false`
  and `allowProjectileHits: false`.
- NPCs have no default wander behaviour (VERIFIED). A class with no `behaviours`/`ai` entries stays in place.
- `NPCEntity` does not override `canBeCollidedWith`. ASSUMED from vanilla: it therefore has only the soft push of a mob,
  not a solid box, and `isMovable: false` only makes it unpushable. Whether a player can squeeze past it in a 1-wide
  walkway is **unknown and needs an experiment**. Pistons and ridden Pokemon (flying over) are other likely ways past.
- NPC dialogue can run server commands: `q.run_command('...')` runs as the server (VERIFIED in source and in game in
  EXP-022), `q.player.run_command` runs as the player, and there is a native `q.player.teleport(x, y, z)`. A guard that
  teleports qualifying players, backed by a real block barrier, is the robust design.

## Question 1: caught count per player

### VERIFIED

- **The per-player Pokedex exists and is stored as instanced player data.** `PokedexManager` implements
  `InstancedPlayerData` with `type = PlayerInstancedDataStoreTypes.POKEDEX`. Its codec has the fields `uuid` and
  `speciesRecords` (a map of species id to `SpeciesDexRecord`).
  Source: `kotlin/com/cobblemon/mod/common/api/pokedex/PokedexManager.kt` @1.8.0.
- **What counts as "caught" in the Pokedex.** `PokedexHandler` calls `getPokedexData(...).catch(pokemon)` on
  `POKEMON_GAINED` and on `POKEMON_ASPECTS_CHANGED`. Sightings (`POKEMON_SEEN`) call `encounter()`. So Pokedex
  ownership covers any Pokemon the player gains, not only ball captures.
  Source: `kotlin/com/cobblemon/mod/common/events/PokedexHandler.kt` @1.8.0.
- **Molang Pokedex functions.** `PlayerMoLangFunctions` has the entry `map["pokedex"] = { player.pokedex().struct }`.
  `PokedexMoLangFunctions` defines the following functions:

  | Function | What it does | Parameters |
  |---|---|---|
  | `caught_count` | `DoubleValue(pokedex.getGlobalCalculatedValue(CaughtCount))` | none |
  | `seen_count` | `SeenCount` | none |
  | `caught_percent` | percentage caught | none |
  | `seen_percent` | percentage seen | none |
  | `has_caught` | whether a species (or form) is owned | species id, optional form name |
  | `has_seen` | whether a species (or form) is seen | species id, optional form name |
  | `get_species_record` | the species record | species id |

  Player Pokedexes also have `player_id`, `see` and `catch`. Note that `catch` and `see` **write** to the Pokedex.
  Sources: `kotlin/com/cobblemon/mod/common/api/molang/function/PlayerMoLangFunctions.kt` and
  `.../function/PokedexMoLangFunctions.kt` @1.8.0.
- **`caught_count` counts distinct species.** `CaughtCount.calculate` is
  `dexManager.speciesRecords.values.count { it.getKnowledge() == PokedexEntryProgress.OWNED }`. `SeenCount` counts
  every record whose knowledge is not `UNREGISTERED`, so seen includes owned.
  Source: `kotlin/com/cobblemon/mod/common/api/pokedex/PokedexValueCalculator.kt` @1.8.0.
- **Advancement triggers.** `CobblemonCriteria` registers `catch_pokemon` (codec `CaughtPokemonCriterion.CODEC`),
  `catch_shiny_pokemon` and `catch_alpha_pokemon` (both `CountableCriterion.CODEC`), and among others
  `pokemon_defeated`, `battles_won`, `trade_pokemon`, `eggs_hatched`, `level_up`, `party` and `pick_starter`.
  Source: `kotlin/com/cobblemon/mod/common/advancement/CobblemonCriteria.kt` @1.8.0.
- **`cobblemon:catch_pokemon` conditions.** The codec fields are `player` (optional entity predicate), `type` (string,
  default `"any"`) and `count` (int, default `0`). The criterion matches when `context.times >= count` and
  (`context.type == type` or `type == "any"`).
  Sources: `advancement/criterion/CatchPokemonCriterion.kt` and `CountableCriterion.kt` @1.8.0.
- **What `times` is.** On `PokemonCapturedEvent`, `AdvancementHandler.onCapture` calls
  `advancementData.updateTotalCaptureCount()` and triggers
  `CATCH_POKEMON(CountablePokemonTypeContext(advancementData.totalCaptureCount, "any"))`. It also fires once for each
  of the Pokemon's types with that type's own capture total and `it.showdownId` (for example `fire`). So `count` is the
  player's **cumulative ball-capture total**, and it is checked only when a capture happens.
  Source: `kotlin/com/cobblemon/mod/common/events/AdvancementHandler.kt` @1.8.0.
- **Shipped example.** `data/cobblemon/advancement/catching/first_catch.json` uses
  `"trigger": "cobblemon:catch_pokemon", "conditions": {"count": 1, "species": "any"}`. The `species` key is not a codec
  field. It is presumably ignored, and the only filter is `type`. A condition for "caught N of species X" **does not
  exist**.
- **Custom statistics.** `CobblemonStats` defines stats in namespace `cobblemon`, including `captured`,
  `shinies_captured`, `released`, `evolved`, `level_up`, `battles_won`, `battles_lost`, `battles_fled`,
  `battles_total`, `dex_entries`, `eggs_collected`, `eggs_hatched`, `traded`, `fossils_revived` and `times_ridden`.
  Source: `kotlin/com/cobblemon/mod/common/api/stats/CobblemonStats.kt` @1.8.0.
- **How the capture stats are awarded.** `StatHandler.onCapture(PokemonCapturedEvent)` calls
  `awardStat(getStat(CAPTURED))` with no condition. `onDexEntryGain(PokemonGainedEvent)` awards `DEX_ENTRIES` on
  **every** Pokemon gained. Despite its name, `dex_entries` is therefore not a count of distinct species.
  Source: `kotlin/com/cobblemon/mod/common/events/StatHandler.kt` @1.8.0.
- **Molang can read any custom stat.** `q.player.get_custom_stat('<ns:path>')` resolves the id in
  `BuiltInRegistries.CUSTOM_STAT` and returns `player.stats.getValue(stat)`. An unknown id returns 0.
  Source: `PlayerMoLangFunctions.kt` @1.8.0.
- **Molang can read advancements.** `q.player.has_advancement('<id>')` returns 1 if that advancement is done, otherwise
  0. Source: `PlayerMoLangFunctions.kt` @1.8.0.
- **Dialogue can already act on these reads.** Dialogue Molang can read per-player state and then act through
  `q.run_command`, with the command taking effect immediately inside dialogue actions. Source:
  `experiments/EXP-022-native-dialogue-runtime/README.md`, lines 32-35, run on 1.8.0.

### ASSUMED

- **Call form.** Writing `q.player.pokedex.caught_count` (or `q.player.pokedex().caught_count()`) returns the number.
  The `struct` returned by `pokedex()` is presumed to carry the `PokedexMoLangFunctions` entries through
  `addPokedexFunctions`, which exists in `api/molang/MoLangFunctions.kt`. The exact zero-argument call syntax was not
  run. EXP-022 used `q.player.data()` with parentheses.
- **The stat is registered.** `cobblemon:captured` is in the `CUSTOM_STAT` registry, because `getStat` throws when it
  is missing and runs on every capture. The registration call itself was not located.
- **Scoreboard criterion name.** The criterion is `minecraft.custom:cobblemon.captured`. This is vanilla custom-stat
  naming, with `:` in the stat id becoming `.`, and was not checked in this pack.
- **Scoreboard objectives do not backfill.** A vanilla stat objective only adds increments made after the objective
  exists, so it does not include earlier catches. Molang `get_custom_stat` reads the full stored value and has no such
  gap.
- **The advancement does not fire retroactively.** A player who already has N or more captures when the advancement is
  added gets it only on their next capture.
- **Evolution and the species count.** An evolution likely marks the new species owned through the gained or
  aspect-change paths, which would inflate a species count. This was not traced.

### Unknown and experiment candidates

- **Pokedex count probe:** in a disposable world, `runmolang` `q.player.pokedex.caught_count` before and after catching
  a new species, a duplicate, a trade-in and an evolution. Record which of these change the count.
- **Advancement threshold:** a datapack advancement `cobblemon:catch_pokemon` with `{"count": 3}` whose reward function
  tags the player. It must be granted on the third ball capture and not after `/pokegive`.
- **Stat read:** `q.player.get_custom_stat('cobblemon:captured')` and a `minecraft.custom:cobblemon.captured`
  objective, compared after catches made both before and after the objective was created.

## Question 2: Cobblemon NPCs as walkway guards

### VERIFIED

- **NPC class fields and defaults.** `api/npc/NPCClass.kt` @1.8.0, lines 30-46 (as rendered):

  | Field | Default | Notes |
  |---|---|---|
  | `hitbox` | `EntityDimensions.scalable(0.6F, 1.8F).withEyeHeight(1.62F)` | the shipped classes write it as `"hitbox": "player"` |
  | `canDespawn` | `true` | |
  | `interaction` | `null` | |
  | `behaviours` | empty | `@SerializedName("behaviours", alternate = ["behaviors", "ai"])` |
  | `isMovable` | `true` | |
  | `isInvulnerable` | `false` | |
  | `isLeashable` | `true` | |
  | `allowProjectileHits` | `true` | |
  | `hideNameTag` | `false` | |

  The class also has `names`, `aspects`, `modelScale` (0.9375), `battleConfiguration`, `config`, `variables`, `party`,
  `skill` and `autoHealParty`.
- **How the entity applies those fields.** In `entity/npc/NPCEntity.kt` @1.8.0 (`class NPCEntity : AgeableMob(...)`):

  | Method | Implementation |
  |---|---|
  | `isPushable()` | `isMovable ?: npc.isMovable` |
  | `isInvulnerableTo(source)` | `(isInvulnerable ?: npc.isInvulnerable) && !source.is(BYPASSES_INVULNERABILITY)` |
  | `canBeLeashed()` | `isLeashable ?: npc.isLeashable` |
  | `canBeHitByProjectile()` | `allowProjectileHits ?: npc.allowProjectileHits` |
  | `isPersistenceRequired()` | `super.isPersistenceRequired() \|\| !npc.canDespawn` |

  The entity has nullable per-instance overrides of these four flags. How they are set per entity was not traced.
  **Not overridden:** `canBeCollidedWith`, `isPickable`, `push`, anything about knockback resistance, and any passenger
  or riding method. Its attributes are `createMobAttributes()` plus `ATTACK_DAMAGE` 1.0 and `ATTACK_KNOCKBACK`.
- **No wandering by default.** `NPCBrain.configure` applies `CobblemonBehaviours.autoNPCBehaviours` plus the class's
  `behaviours`. The only auto behaviour, `data/cobblemon/behaviours/npc/auto/npc_core.json`, adds one idle task:
  `q.entity.get_wander_control_memory.reset()`. The shipped `data/cobblemon/npcs/standard.json` has no `ai` block.
  Movement therefore comes only from behaviour presets the class opts into (for example
  `"ai": [{"type": "apply_behaviours", "presets": [...]}]` in `kitchen_sink.json`).
- **The project's current NPC class.** `tools/compile_dialogue.py:289-293` emits `hitbox: "player"`,
  `canDespawn: false`, `isInvulnerable: true`, `isMovable: false`, `isLeashable: false`,
  `allowProjectileHits: false` and a dialogue `interaction`. In EXP-022 that class spawned and ran a full conversation.
  NPC classes load only at server start (`experiments/EXP-022-native-dialogue-runtime/README.md:39`).
- **Dialogue can run commands and teleport.**
  - `q.run_command(cmd)` (`GeneralMoLangFunctions.kt`) runs
    `performPrefixedCommand(server.createCommandSourceStack(), cmd)`, which means as the server with full permission.
  - `q.player.run_command(cmd)` (`PlayerMoLangFunctions.kt`) uses `player.createCommandSourceStack()`, which means with
    the player's own permission.
  - `q.player.teleport(x, y, z[, particles])` calls `player.randomTeleport(x, y, z, particles)`.
  - EXP-022 ran `q.run_command('execute as ' + q.player.uuid + ' ...')` from dialogue actions in game, and the effect
    applied immediately (`EXP-022 README:34-35`).

### ASSUMED

These are vanilla 1.21.1 behaviours from memory, not checked in source.
- **No solid collision.** With `canBeCollidedWith()` left at the `Entity` default (`false`), the NPC is not a solid box.
  A player cannot stand on it, and it only blocks through the mob soft push.
- **Soft push only.** With `isPushable() == false`, the player does not push the NPC, but the NPC's own client-side
  push still nudges the player away. The push is small, so a player may be able to force through a 0.6-wide NPC in a
  1-wide corridor. This is the key risk.
- **Jumping.** The 1.8-tall hitbox is higher than a normal 1.25-block jump. Since there is no solid collision, jumping
  "over" it is not the real question; walking through it is.
- **No knockback.** An invulnerable NPC takes no knockback from attacks, because `LivingEntity.hurt` returns early when
  `isInvulnerableTo` is true. `/kill` and void damage still apply (`BYPASSES_INVULNERABILITY`).
- **Pistons.** Pistons move entities regardless of `isPushable` (`getPistonPushReaction` is not overridden, so
  `NORMAL`). Keep pistons away from guard posts.
- **Riding.** Players cannot mount the NPC: there is no riding override, and right-click goes to `mobInteract`
  (dialogue).
- **Ridden Pokemon.** Cobblemon riding (1.7+) may let a flying mount pass over the NPC or the walkway entirely.
- **`q.player.teleport`.** It uses `randomTeleport`, which may refuse or adjust unsafe destinations. For exact
  placement, `q.run_command('execute as <uuid> run tp @s x y z')` is the predictable form.

### Unknown and experiment candidates

- **Guard pass-through:** spawn the compiler's invulnerable, immovable NPC in a 1-wide, 2-high corridor on a disposable
  world. Try to walk, sprint, sprint-jump and crouch past it, push it with a piston, and fly over on a ridden Pokemon.
  Pass means none of these gets a player through.
- **Hitbox format:** `"hitbox"` accepts `"player"`. Whether it also accepts explicit dimensions (so the NPC could be
  2 wide or 3 tall) needs its JSON adapter, which was not read. Do not author other forms until then.
- **Fallback design (no experiment needed to adopt):** the real barrier is a block (for example a barrier block or a
  gate) behind or under the NPC. The NPC's dialogue checks the gate condition. Qualifying players are moved past with
  `q.run_command('execute as ' + q.player.uuid + ' run tp @s X Y Z')`, or given a tag that another mechanism uses to
  open the gate.

## Sources

- Cobblemon tags list: https://gitlab.com/api/v4/projects/cable-mc%2Fcobblemon/repository/tags
- Source files at tag 1.8.0, all under `https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/`:
  - `kotlin/com/cobblemon/mod/common/api/npc/NPCClass.kt`
  - `kotlin/com/cobblemon/mod/common/entity/npc/NPCEntity.kt`, `NPCBrain.kt`
  - `kotlin/com/cobblemon/mod/common/CobblemonBehaviours.kt`
  - `resources/data/cobblemon/behaviours/npc/auto/npc_core.json`
  - `resources/data/cobblemon/npcs/standard.json`, `kitchen_sink.json`
  - `kotlin/com/cobblemon/mod/common/api/molang/function/PlayerMoLangFunctions.kt`, `PokedexMoLangFunctions.kt`,
    `GeneralMoLangFunctions.kt`
  - `kotlin/com/cobblemon/mod/common/api/pokedex/PokedexManager.kt`, `PokedexValueCalculator.kt`
  - `kotlin/com/cobblemon/mod/common/advancement/CobblemonCriteria.kt`, `criterion/CatchPokemonCriterion.kt`,
    `criterion/CountableCriterion.kt`
  - `resources/data/cobblemon/advancement/catching/first_catch.json`
  - `kotlin/com/cobblemon/mod/common/events/AdvancementHandler.kt`, `StatHandler.kt`, `PokedexHandler.kt`
  - `kotlin/com/cobblemon/mod/common/api/stats/CobblemonStats.kt`
- Local sources: `experiments/EXP-022-native-dialogue-runtime/README.md` and `tools/compile_dialogue.py`.
- Third-party stat addons exist ([Cobblemon Scoremons](https://modrinth.com/mod/cobblemon-scoremons),
  [More Cobblemon Stats](https://www.curseforge.com/minecraft/mc-mods/more-cobblemon-stats)), but the native stats
  above make them unnecessary.
