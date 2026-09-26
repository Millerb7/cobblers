# Keeping habitat-nest Pokémon in their tree

**Question.** Can wild Pokémon spawned by an *activated* Habitat Block be kept on the limbs and crown
of the tree they spawn in, instead of wandering to the forest floor or drifting away as a herd,
without changing the species everywhere in the world?

**Answered for Cobblemon 1.8.0 on MC 1.21.1 Fabric.** Researched 2026-09-26 after the staging
Fletchling tree (about 23 birds) emptied onto the forest floor or drifted off in a group within a
minute.

**Sources.** The GitLab tag `1.8.0` of `cable-mc/cobblemon` (Kotlin source and the stock data under
`common/src/main/resources/data/cobblemon/`). **The jar at
`experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods/Cobblemon-fabric-1.8.0+1.21.1.jar` was
not opened**: this session had no shell, so Python `zipfile` and `javap` could not run. Everything
below comes from the tagged source, which should match the 1.8.0 release jar. That has not been
checked byte for byte. Links are at the end. "VERIFIED" means read in the 1.8.0 tagged source. It
does not mean seen working in game.

## Short answer

Yes, very probably, with a small datapack and no custom code. Nothing in 1.8.0 does this out of the
box, and there is no "home" field on a spawn. There is also no per-spawn behaviour field in a
habitat pool. But four verified pieces fit together:

1. `aspect=<name>` is a PokemonProperties key that adds a *forced aspect* to one Pokémon. The block's
   `Modifiers` accepts it, and so does a pool entry's `modifiers`.
2. Any datapack can add a file under `behaviours/pokemon/auto/`, and it is applied to every Pokémon
   whose form has no `baseAI`. Fletchling has none.
3. The stock wander tasks respect a per-tick **wander control** memory. Its centre and maximum range
   can be set from a Molang script. The stock bee behaviour does exactly this to keep bees near
   their hive.
4. `q.entity.has_aspect(...)` and a persisted per-entity `q.entity.data` struct are available to that
   script.

So an unconditional auto behaviour can add one `run_script` task. The script does nothing unless the
Pokémon is wild and carries the aspect `nest`. For those Pokémon it records a nest point once, then
re-centres the wander control there on every tick. Other Fletchling in the world are not touched.
Herding needs one extra step, covered in §3.

---

## 1. How brains are assigned in 1.8

VERIFIED:

- **Per form, with a global default.** `PokemonBrain.applyBrain` builds the configuration list as
  `(pokemon.form.baseAI ?: CobblemonBehaviours.autoPokemonBehaviours.flatMap { it.configurations }) + pokemon.form.ai`
  ([PokemonBrain.kt][pb]). A form with no `baseAI` gets **every** auto behaviour, plus its own `ai`
  list. `Species.kt` declares `var baseAI: MutableList<BehaviourConfig>? = null` and
  `var ai = mutableListOf<BehaviourConfig>()` ([Species.kt][sp]). The Fletchling species JSON has
  neither key ([fletchling.json][fl]).
- **The auto folder works in any namespace.** `CobblemonBehaviours.reload` puts every file whose path
  contains `"pokemon/auto/"` into `autoPokemonBehaviours`. It registers every file under the ID
  `namespace:<file name without extension>`, so **subfolders are dropped from the ID**
  ([CobblemonBehaviours.kt][cb]). In practice `data/cobblers/behaviours/pokemon/auto/nest_perch.json`
  becomes auto behaviour `cobblers:nest_perch`, and file names must be unique within a namespace.
- **The stock auto set** (1.8.0): `pokemon_core`, `pokemon_combat`, `pokemon_herdable`,
  `pokemon_no_underwater`, `pokemon_non_party`, `pokemon_owned` ([behaviours tree][bt]).
  `pokemon_core` adds `pokemon_wander_control` to `minecraft:idle` at priority 0 ([pokemon_core][pc]).
  `pokemon_non_party` applies `cobblemon:wanders` when `walk.can_walk`, and `cobblemon:wanders_hover`
  (**not** `wanders_air`) when `fly.can_fly`. Both are conditioned on `!q.entity.is_in_party`
  ([pokemon_non_party][pnp]). Fletchling can walk and can fly, so it gets both wander tasks.
- **Auto files lose their own `onAdd`.** Only their `configurations` are flattened in.
  `CobblemonBehaviour.onAdd` runs only through `CobblemonBehaviour.configure`, which is used when a
  behaviour is applied by `apply_behaviours` ([CobblemonBehaviour.kt][cbh], [ApplyBehaviours.kt][ab]).
- **Per entity: `BehavioursAreCustom`.** If `entity.behavioursAreCustom`, the whole list is replaced
  by `ApplyBehaviours(entity.behaviours)` ([PokemonBrain.kt][pb]). Four values are saved to and loaded
  from entity NBT by `saveScriptingToNBT` and `loadScriptingFromNBT`: `BehavioursAreCustom` (bool),
  `Behaviours` (list of IDs), `ScriptingData` and `ScriptingConfig` ([MoLangScriptingEntity.kt][mse],
  [DataKeys.kt][dk]). `PokemonEntity` calls `remakeBrain()` after loading ([PokemonEntity.kt][pe]).
  Auto files are also registered as ordinary behaviours (for example `cobblemon:pokemon_core`), so a
  custom list can name them.
- **When the brain is built.** It is built in the `PokemonEntity` `init` block, again whenever
  `pokemon` is reassigned, and on NBT load ([PokemonEntity.kt][pe]). It is **not** rebuilt when
  aspects change.

Candidate routes to a different behaviour for one entity:

| Route | Status | Notes |
|---|---|---|
| PokemonProperties `aspect=nest`, in the block `Modifiers` or a pool entry `modifiers` | VERIFIED key | `AspectPropertyType`, keys `{"aspect"}`, applicator `pokemon.forcedAspects += value` ([AspectProperties.kt][ap]). `unaspect=` removes one. The NBT key `ForcedAspects` exists ([DataKeys.kt][dk]). |
| An auto behaviour that checks the aspect | VERIFIED primitives | `q.entity.has_aspect('x')` is registered as `DoubleValue(it.getString(0) in pokemonEntity.aspects)` ([PokemonEntityMoLangFunctions.kt][pemf]). See the timing caveat below. |
| An entity NBT or data command | VERIFIED keys, ASSUMED effect | `/data merge entity … {BehavioursAreCustom:1b,Behaviours:[…]}` should rebuild the brain through `load`. This is manual, one entity at a time, and not automatic on spawn. |
| A spawn-detail or habitat-pool field for behaviours | **Does not exist** | See §6. |
| PokemonProperties `no_ai=true` | VERIFIED key | `NoAIProperty` sets `pokemonEntity.isNoAi` through an **entity** applicator ([NoAIProperty.kt][nai]). See §5. |

**Timing caveat (important).**

- VERIFIED: the aspect gets onto the Pokémon at different moments depending on where it is written.
  - **Pool-entry `modifiers`** become the spawn detail's `pokemon` properties
    ([HabitatSpawn.kt][hs] `createSpawnDetail`). `PokemonSpawnAction.createEntity` calls
    `props.createEntity`, which is `create(player)` (it calls `apply(pokemon)`) followed by
    `PokemonEntity(world, pokemon)` ([PokemonSpawnAction.kt][psa], [PokemonProperties.kt][pp]). The
    aspect is therefore on the Pokémon **before** the brain is built.
  - **Block `Modifiers`** are applied by `ActivatedHabitatSpawningInfluence.affectSpawn`
    ([ActivatedHabitatSpawningInfluence.kt][ahsi]). That runs from the spawn action's `entity.emit`,
    which comes **after** `createEntity` and `setPos` ([SingleEntitySpawnAction.kt][sesa]). The brain
    has already been built at that point.
- VERIFIED: `PokemonEntity.aspects` reads synced entity data (`entityData.get(ASPECTS)`). The server
  delegate copies `trackedAspects` into it ([PokemonEntity.kt][pe], [PokemonServerDelegate.kt][psd]).
- ASSUMED: that copy happens in the per-tick tracked-value update, so `has_aspect` is still false while
  the brain is built in `init`. Not traced to the exact function.
- **Consequence.** Test the aspect **inside a script task on each tick**, not in an
  `apply_behaviours` `condition`. Then it works for both the block `Modifiers` and pool-entry
  `modifiers`, and it keeps working after a chunk reload.

## 2. `stationary`, wander, air-wander and the wander control

VERIFIED contents (1.8.0):

- **`stationary.json`** adds the memory `minecraft:walk_target` and one idle task at priority 1:
  `run_script` → `cobblemon:home_walk_task`. It declares the variables `home_x`, `home_y` and `home_z`
  (default `"0"`) and `home_radius` (default `"2"`) ([stationary.json][st]). The script
  `home_walk_task.molang` runs every 20 game ticks while idle with no walk target. If
  `q.entity.distance_to_pos(home) > home_radius` and the home is not `0,0,0`, it calls
  `q.entity.walk_to(home)` ([home_walk_task.molang][hw]). **It does not stop wandering.** It walks the
  Pokémon back afterwards. The home comes from `q.entity.config.home_*`, which is per-entity
  configuration persisted as `ScriptingConfig`. **No stock code sets it for a wild spawn**, so
  applied as-is the home is `0,0,0` and the task does nothing.
- **`wanders.json`** adds `wander` at idle priority 7 ([wanders.json][wa]). `WanderTaskConfig`
  variables: `wanders` (true), `wander_chance` (1/120 per tick), `horizontal_wander_range` (10),
  `vertical_wander_range` (5), walk speed 0.35, `avoidTargetingAir` (true), `minimumHeight` (0),
  `maximumHeight` (−1) ([WanderTaskConfig.kt][wt]).
  - It picks a target with `LandRandomPos`, `HoverRandomPos` (when `maximumHeight != -1`), a swim or a
    surface position.
  - It skips targets outside a pasture tether (`tethering?.canRoamTo`).
  - It accepts a target only if `wanderControl.isSuitable(pos)`, retrying up to
    `wanderControl.maxAttempts` (4) times.
- **`wanders_hover.json`**, which is what flyers actually get, adds `cobblemon:wander` at priority 7
  with `hover_wander_minimum_height` 0, `hover_wander_maximum_height` 6 and `avoidTargetingAir: false`
  ([wanders_hover.json][wh]). It is the same `WanderTaskConfig` class, so it **respects the wander
  control centre**.
- **`wanders_air.json`** adds `cobblemon:air_wander` (priority 7) and `cobblemon:fly_in_circles`
  (priority 9) ([wanders_air.json][wair]). `AirWanderTaskConfig` has `air_wanders`,
  `air_wander_chance` (1/20), `horizontal_wander_range` (20) and `vertical_wander_range` (5). It calls
  `HoverRandomPos.getPos` directly and **does not read the wander control** ([AirWanderTaskConfig.kt][awt]).
  `FlyInCirclesTaskConfig` sets angular velocity, speed and duration only
  ([FlyInCirclesTaskConfig.kt][fic]). No auto file read here applies `wanders_air`: `pokemon_combat`,
  `pokemon_no_underwater` and `pokemon_owned` were not read. So wild Fletchling should not be running
  either task.
- **`FindRestingPlaceTaskConfig`** has `horizontalSearchDistance` 16 and `verticalSearchDistance` 5
  ([FindRestingPlaceTaskConfig.kt][frp]). It is added only by `pokemon_sleeps`, which is conditioned on
  `q.entity.behaviour.resting.can_sleep` ([pokemon_core][pc], [pokemon_sleeps.json][ps]). Fletchling's
  `resting` block sets `willSleepOnBed`, `drowsyChance` and `rouseChance` but not `canSleep`
  ([fletchling.json][fl]). ASSUMED: `canSleep` defaults to false, so resting is not the cause here.
- **`CobblemonWanderControl`** (the leash that exists). Fields: `center: WanderCenter(x, y, z,
  minRange, maxRange)`, `maxAttempts` 4, `allowLand`, `allowWater`, `allowAir`, `pathCooldownTicks`
  100 and `wanderSpeed` 0.35. `isSuitable` is **3D**: `sqrt(centerPos.distSqr(position))` between
  `minRange` and `maxRange`. From Molang, `set_center(x, y, z[, minRange[, maxRange]])`,
  `set_max_attempts`, `set_path_cooldown_ticks`, `set_wander_speed` and `reset` are available
  ([CobblemonWanderControl.kt][wc]). `pokemon_wander_control` (idle priority 0) **resets it on every
  tick**, and recomputes `allowLand`, `allowWater` and `allowAir` from the species behaviour
  ([PokemonWanderControlTaskConfig.kt][pwc]). Anything that sets a centre must therefore run on every
  tick, after priority 0 and before the wander at priority 7.
- **The stock precedent.** `pokemon_bee.json` adds, at idle priority 1, a `run_script` →
  `cobblemon:wander_around_hive`, with the comment "This tweaks the wander control to set a center
  point around the hive location to keep it from walking too far" ([pokemon_bee.json][bee]). The
  script calls `q.entity.get_wander_control_memory()` and then
  `t.wander_control.set_center(x, y, z, 2, 32)` ([wander_around_hive.molang][wah]). This is the
  pattern a nest behaviour would copy.
- ASSUMED: tasks of lower priority run earlier in the same tick. The bee design depends on that order,
  but Brain task ordering was not read.

**Why the staging tree emptied.**

- VERIFIED: every candidate a stock wander produces is filtered only by pasture tethering and by the
  wander control. With no centre set, `isSuitable` returns true ([WanderTaskConfig.kt][wt],
  [CobblemonWanderControl.kt][wc]). `LandRandomPos` with ranges 10/5 and hover wander with ranges 10/5
  (maximum height 6) therefore walk and hop birds off the crown freely.
- VERIFIED: herd followers bypass the wander control entirely (§3).
- ASSUMED: the ground under a crown is simply where most random walkable positions are.

## 3. Herding

VERIFIED:

- `pokemon_herdable` (auto) applies `cobblemon:pokemon_herds` when
  `!q.entity.is_in_party && q.entity.behaviour.herd.has_tolerated_leaders`. It adds the memory
  `cobblemon:herd_size` when `max_size > 0` ([pokemon_herdable][ph]).
- `pokemon_herds` adds to idle `find_herd_leader` (priority 8, `checkTicks` 20), `switch_to_herd` and
  `count_followers` (priority 9). In activity `cobblemon:pokemon_herd` it adds `switch_from_herd`
  (priority 1) and `follow_herd_leader` and `maintain_herd_leader` (priority 2) ([pokemon_herds][phs]).
- A leader is any visible, non-party Pokémon matched by `toleratedLeaders`, below its herd `maxSize`,
  and not drowsy. A higher tier wins. Alphas get +9001 tier. Wild and pastured Pokémon can mix
  ([FindHerdLeaderTaskConfig.kt][fhl], [HerdBehaviour.kt][hb]). Fletchling tolerates `fletchling`
  (tier 1) and `fletchinder` (tier 2), with `maxSize` 9 ([fletchling.json][fl]).
- `FollowHerdLeaderTask` sets its **own** walk targets. When farther than `tooFar` (the follow
  distance, default 4..8) it walks to the leader plus an offset. It follows a flying leader if it can
  fly. With probability 1/60 per tick it copies the leader's walk target ([FollowHerdLeaderTask.kt][fhlt]).
  **None of this reads the wander control.** It also only runs in the herd activity, where the idle
  wander tasks do not.

What this means:

- ASSUMED, strongly: **herding would pull a group away.** A follower goes wherever its leader goes. A
  wild Fletchling or Fletchinder spawned elsewhere and passing by can recruit nest birds, and a
  Fletchinder always outranks a Fletchling. A nest bird that becomes a leader is only held if its own
  wander is centred.
- Per entity or per spawn, herding cannot be switched off by a spawn field or property. It can be done
  in three ways:
  1. **Species-wide:** set `herd.maxSize` 0 with no `toleratedLeaders`, in a species override (§5).
  2. **Per entity, at run time:** add the nest script to activity `cobblemon:pokemon_herd` at a
     priority before 1, and have it call `q.entity.erase_memory('cobblemon:herd_leader')` for nest
     birds. `erase_memory` exists in `LivingEntityMoLangFunctions` ([LivingEntityMoLangFunctions.kt][lemf]),
     but its argument format is ASSUMED from `get_position_memory('cobblemon:hive_location')`.
     ASSUMED: `switch_from_herd` then returns the bird to idle. Side effect (ASSUMED):
     `find_herd_leader` has already called `adjustHerdSize(1)` on the leader, so leaders may churn.
  3. **Overriding `pokemon_herdable.json`** and adding `&& !<nest test>` to its condition. The
     condition is evaluated when the brain is built, so `has_aspect` is probably false at that moment
     (§1 caveat). This would need a condition that reads `q.entity.aspects` (the Pokémon's own set,
     attached through `PokemonMoLangFunctions`) with a loop. Whether a `condition` accepts a
     multi-statement script is **unknown**.

## 4. A 1.8 "stay near spawn / near the block" feature

- VERIFIED: **none for wild spawns.** The activated style's settings are `chance`, `trigger`,
  `cancelledNaturalSpawningRange`, `spawnRange`, `maxSpawns` and `maxSpawnsPerActivation`
  ([ActivatedHabitatSpawning.kt][ahs]). Its influence only applies `modifiers` and records the entity
  ID ([ActivatedHabitatSpawningInfluence.kt][ahsi]). Nothing sets a home, a tether or a leash.
- VERIFIED: the only built-in leashes are (a) pasture `tethering`, which is set by a Pasture block,
  (b) the wander control centre, used by bees and (c) `stationary` with `config.home_*`. A Molang
  function list of `LivingEntityMoLangFunctions` shows no `restrict`, `home` or `leash` function
  ([LivingEntityMoLangFunctions.kt][lemf]).
- VERIFIED: `entity.spawnCause` holds the `FixedAreaSpawner`, whose `position` is the Habitat Block
  ([PokemonSpawnAction.kt][psa], [ActivatedHabitatSpawning.kt][ahs]). **UNKNOWN**: whether any Molang
  query exposes it, and whether it survives a save. It was not found in the function lists read.
- VERIFIED, side finding: `spawnedEntityIDs` is a `mutableSetOf<Int>()` of runtime entity IDs. It is
  pruned by `world.getEntity(id)?.isAlive != true` ([HabitatBlockEntity.kt][hbe]).
  - ASSUMED: birds in unloaded chunks are pruned as "not alive", so the block refills.
  - ASSUMED: several blocks per trunk also add up.
  - Either could explain about 23 birds against `MaxSpawns: 7`.

## 5. Options, from least to most invasive

**A. Datapack nest leash (recommended to test first).** It is per spawn and leaves every other Pokémon
untouched. VERIFIED building blocks; the combination is ASSUMED until tested.

- Block `Modifiers:"aspect=nest"`, or pool-entry `"modifiers": "aspect=nest"`.
- `data/cobblers/behaviours/pokemon/auto/nest_perch.json`: one `add_tasks_to_activity` on
  `minecraft:idle` at priority `"1"` with `{"type": "run_script", "script": "cobblers:nest_perch"}`,
  and, for herding, the same task on `cobblemon:pokemon_herd` at priority `"0"`. It has no
  `condition`, because the aspect test lives in the script (§1 caveat).
- `data/cobblers/molang/nest_perch.molang`, using only functions seen in 1.8.0 source:
  `q.entity.is_wild`, `q.entity.has_aspect`, `q.entity.data.*` (persisted per entity as
  `ScriptingData`), `q.entity.x`, `q.entity.y`, `q.entity.z`, `q.entity.get_wander_control_memory()`
  → `set_center`, `q.entity.distance_to_pos`, `q.entity.walk_to`, `q.entity.has_walk_target`,
  `q.entity.world.game_time` and `q.entity.erase_memory`. The script:
  1. Returns at once unless the Pokémon is wild and has the aspect.
  2. The first time, stores its position in `data.nest_x`, `nest_y` and `nest_z`.
  3. On every tick calls `set_center(nest, 0, R)`, so both wander tasks only pick targets within a
     3D radius `R` of the nest.
  4. Every 20 ticks, if the bird is farther than `R` and has no walk target, calls `walk_to(nest)`,
     like `home_walk_task`.
  5. Erases `cobblemon:herd_leader`.
- ASSUMED: reading an unset `data` key yields 0. Not read in source.
- **The nest point is the spawn position, not the block.** The spawner is a box, `verticalRadius` and
  `horizontalRadius` both equal to `spawnRange` around the block ([ActivatedHabitatSpawning.kt][ahs]).
  If the box reaches the forest floor, some birds will nest on the floor. Put the block in the crown
  with a `SpawnRange` smaller than the crown's height above the floor. Then choose `R` so the 3D
  sphere does not reach the floor either. An alternative is to encode the block coordinates in the
  aspect (for example `aspect=nest_<x>_<y>_<z>`) and parse them with `for_each` over `q.entity.aspects`
  plus `split_string` and `to_number` (present in `GeneralMoLangFunctions` ([GeneralMoLangFunctions.kt][gmf])).
  Their signatures were not read, so this is ASSUMED.
- **Cost.** One cheap Molang call per non-busy wild Pokémon per idle tick. Every species gets the
  task, but it exits at once without the aspect. ASSUMED to be negligible; not measured.
- **Caught birds.** `is_wild` gates the script. The `nest` aspect stays on a caught Pokémon: forced
  aspects persist as `ForcedAspects`, which is ASSUMED. An aspect with no matching model variation is
  ASSUMED to render as the default model.

**B. `no_ai=true` in `Modifiers`.** This is the bluntest route. VERIFIED: it sets vanilla `NoAI` on the
entity ([NoAIProperty.kt][nai]), through `modifiers.apply(entity)` for the block or
`applyCustomProperties` for a pool entry ([PokemonProperties.kt][pp]). ASSUMED consequences: the brain
does not tick, so the bird stays exactly where it spawned. That may be the floor (the same geometry
problem as A). It will not look at players or animate idling. Its behaviour in a battle and during
capture is unknown. This is good as a control in the experiment, and poor as the design.

**C. Per-entity custom behaviour list by command.** Run
`/data merge entity <bird> {BehavioursAreCustom:1b,Behaviours:["cobblemon:pokemon_core","cobblemon:pokemon_combat","cobblemon:pokemon_non_party","cobblemon:stationary"]}`,
without `pokemon_herdable`, then set `home_*` in `ScriptingConfig`. The keys are VERIFIED. Whether
`/data merge` reaches `PokemonEntity.load` is ASSUMED (vanilla behaviour). The NBT shape of
`ScriptingConfig`, written by `MoLangFunctions.writeMoValueToNBT`, is **unknown**. This is manual per
entity and does nothing for new spawns, so it is not a nest mechanism.

**D. Species-wide overrides.** These change the species everywhere. VERIFIED what they would touch:

- *Override `data/cobblemon/species/generation6/fletchling.json`* (a whole-file replacement; it must
  carry every field):
  - `herd: {maxSize: 0, toleratedLeaders: []}` means no Fletchling herds anywhere.
  - `fly.canFly: false` removes `wanders_hover` from every wild Fletchling.
  - A `baseAI` list replaces the auto set for Fletchling only. It is the cleanest species-scoped
    variant, but it also bypasses any future auto files.
  - ASSUMED: Cobbleverse datapacks may already override this file. That was not checked, because the
    zips are not in the repository.
  - Whether 1.8 `species_additions` can add `ai` or `behaviour` without replacing the file is
    **unknown**.
- *Override the stock `pokemon_herdable.json` or `pokemon_non_party.json`* at the same path. This
  changes the auto rule for **every species**. It is precise only if the condition can recognise nest
  birds when the brain is built (see the §3 caveat).
- *A custom form* ("nest" Fletchling with its own `behaviour` and `baseAI`, selected by an aspect) is
  ASSUMED possible from `pokemon.form.baseAI`. It needs a form definition and client-side model
  resolution, and was not investigated. It is heavier than A.

## 6. Habitat pool entry format and behaviour

VERIFIED ([HabitatSpawn.kt][hs]; the field table in `docs/research/notes/habitat-blocks-underground.md`
§2):

- A habitat pool entry has exactly `species`, `spawnablePositionType`, `bucket`, `weight`, `levelRange`,
  `modifiers`, `phases`, `timeRange`, `minLight` and `maxLight`.
- The only field that can reach the spawned Pokémon is **`modifiers`**, a PokemonProperties string. It
  is copied into the spawn detail's `pokemon` properties. It can carry any properties key, including
  `aspect=…`, `unaspect=…` and `no_ai=…` as well as ordinary ones.
- There is **no** behaviour, AI, home or leash field.
- The 55 stock pool files were not re-read in this session. The earlier note read four of them and saw
  only `modifiers` strings like `"galarian"`.

## Unknown / experiment candidates

Recorded as **EXP-037** in `docs/research/EXPERIMENT_BACKLOG.md`.

1. Does `aspect=nest` plus the auto `run_script` actually hold a Fletchling within `R`? Measure the
   distance from the nest every 30 s over 10 minutes, for 5 birds, against 5 birds without the aspect.
2. Does `has_aspect` see a block-`Modifiers` aspect at run time? Compare it with a pool-entry aspect.
   This settles the §1 timing assumption.
3. Does erasing `cobblemon:herd_leader` from the herd activity keep nest birds out of herds, without
   errors or runaway leader herd sizes?
4. `no_ai=true` as a control: does the bird stay in place, is it affected by gravity, and can it be
   battled and caught normally?
5. How does `ScriptingData` look in `/data get entity` (for debugging), and does it survive a chunk
   reload and a restart?
6. Why ~23 birds against `MaxSpawns: 7`: count the blocks per tree, then reload the chunk and count
   again.

[pb]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/pokemon/ai/PokemonBrain.kt
[sp]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/pokemon/Species.kt
[fl]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/species/generation6/fletchling.json
[cb]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/CobblemonBehaviours.kt
[bt]: https://gitlab.com/cable-mc/cobblemon/-/tree/1.8.0/common/src/main/resources/data/cobblemon/behaviours
[pc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/behaviours/pokemon/auto/pokemon_core.json
[pnp]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/behaviours/pokemon/auto/pokemon_non_party.json
[ph]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/behaviours/pokemon/auto/pokemon_herdable.json
[phs]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/behaviours/pokemon/pokemon_herds.json
[ps]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/behaviours/pokemon/pokemon_sleeps.json
[bee]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/behaviours/pokemon/pokemon_bee.json
[st]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/behaviours/stationary.json
[wa]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/behaviours/wanders.json
[wh]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/behaviours/wanders_hover.json
[wair]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/behaviours/wanders_air.json
[hw]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/molang/home_walk_task.molang
[wah]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/molang/wander_around_hive.molang
[cbh]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/ai/CobblemonBehaviour.kt
[ab]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/ai/config/ApplyBehaviours.kt
[wc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/ai/CobblemonWanderControl.kt
[pwc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/ai/config/task/PokemonWanderControlTaskConfig.kt
[wt]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/ai/config/task/WanderTaskConfig.kt
[awt]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/ai/config/task/AirWanderTaskConfig.kt
[fic]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/ai/config/task/FlyInCirclesTaskConfig.kt
[frp]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/ai/config/task/FindRestingPlaceTaskConfig.kt
[fhl]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/ai/config/task/FindHerdLeaderTaskConfig.kt
[fhlt]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/entity/ai/FollowHerdLeaderTask.kt
[hb]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/pokemon/ai/HerdBehaviour.kt
[mse]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/entity/MoLangScriptingEntity.kt
[pe]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/entity/pokemon/PokemonEntity.kt
[psd]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/entity/pokemon/PokemonServerDelegate.kt
[dk]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/util/DataKeys.kt
[ap]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/pokemon/properties/AspectProperties.kt
[nai]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/pokemon/properties/NoAIProperty.kt
[pp]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/pokemon/PokemonProperties.kt
[pemf]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/molang/function/PokemonEntityMoLangFunctions.kt
[lemf]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/molang/function/LivingEntityMoLangFunctions.kt
[gmf]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/molang/function/GeneralMoLangFunctions.kt
[hs]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/habitats/HabitatSpawn.kt
[ahs]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/habitats/spawningstyle/ActivatedHabitatSpawning.kt
[ahsi]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/habitats/ActivatedHabitatSpawningInfluence.kt
[hbe]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/block/habitat/HabitatBlockEntity.kt
[psa]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/detail/PokemonSpawnAction.kt
[sesa]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/detail/SingleEntitySpawnAction.kt
