# Level cap: can a Poké Ball be refused above the thrower's RCT cap?

**Question.** The level-cap trap (`experiments/EXP-035-first-playtest/README.md:34`, options at `:109-118`): rctmod
stops experience at the cap but not catching, and refuses every trainer battle while a party member is over it. The
owner decided (2026-09-28) to block catching above the cap entirely. Which mechanism can refuse a capture when the
target's level exceeds the throwing player's RCT level cap?

**Versions.** Cobblemon 1.8.0+1.21.1 (source at GitLab ref `1.8.0`; class names checked in the local jar
`.claude/worktrees/cobblemon-campaign-setup-64929d/experiments/EXP-000-cobblemon-1.8-compat/runtime/replacements/Cobblemon-fabric-1.8.0+1.21.1.jar`),
rctmod 0.19.0-beta (source at GitLab tag `v0.19.0-beta`), Minecraft 1.21.1 Fabric. Nothing here was run in game.

## Answer in one paragraph

Cobblemon 1.8.0 exposes the capture result to datapack MoLang: a script at
`data/cobblemon/callbacks/poke_ball_capture_calculated/cobblers_level_cap.molang` receives the thrower, the target
entity (with its `level`) and a `set_shakes` function that replaces the capture result, in and out of battle, after
the ball's own calculation (so a Master Ball too). rctmod 0.19.0 exposes the cap as a command whose return value *is*
the cap, so `execute store result score ... run rctmod player get level_cap` puts it on a scoreboard. MoLang cannot
read a score, but it can run a command synchronously and then read a vanilla entity tag, so the callback asks a
function "is this level over my cap?" and reads the answer back as a tag. Every link is in source; the chain is not
run. Confidence: high that the hooks exist, medium that the chain works end to end until the proof below passes.

## 1. A capture event reachable from a datapack

VERIFIED (Cobblemon 1.8.0 source):

- **How callbacks load.** `CobblemonCallbacks.reload` lists every `callbacks/**/*.molang` (and the old `flows/`), and
  keys each file by *its own namespace* plus the folder above the file: `ResourceLocation.fromNamespaceAndPath(identifier.namespace, event)`.
  `run(...)` binds the event's context and functions as query functions (`q.<name>`) and runs every script under the
  key. https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/CobblemonCallbacks.kt
  - This explains EXP-042's finding (`docs/STATE.md:36`, `.claude/rules/datapacks.md:75`): Cobblemon fires
    `cobblemon:<event>`, so a file under `data/cobblers/callbacks/` registers as `cobblers:<event>` and never fires.
- **Which events are wired.** `CallbackHandler.setup()` subscribes about 80 events, including these four about
  catching (quoted):
  ```
  CobblemonEvents.THROWN_POKEBALL_HIT.subscribe { CobblemonCallbacks.run(cobblemonResource("thrown_pokeball_hit"), emptyMap(), functions = it.functions) }
  CobblemonEvents.POKE_BALL_CAPTURE_CALCULATED.subscribe { CobblemonCallbacks.run(cobblemonResource("poke_ball_capture_calculated"), it.context, it.functions) }
  CobblemonEvents.POKEMON_CATCH_RATE.subscribe { CobblemonCallbacks.run(cobblemonResource("pokemon_catch_rate_calculated"), it.context, it.functions) }
  CobblemonEvents.POKEMON_CAPTURED.subscribe { CobblemonCallbacks.run(cobblemonResource("pokemon_captured"), it.context) }
  ```
  https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/events/CallbackHandler.kt
  (the class `com/cobblemon/mod/common/events/CallbackHandler.class` is in the local 1.8.0 jar). The repo already uses
  four of the wired events from this same list: `player_tick_pre`, `battle_victory`, `battle_fainted`,
  `pokemon_captured` (`tools/blackout_pack.py:954-1033`).
- **The jar ships no script for any catch event.** Its `data/cobblemon/callbacks/` holds only `battle_fainted`,
  `battle_victory`, `bobber_spawn_pokemon_post`, `fossil_revived`, `player_tick_pre`, `pokemon_captured`,
  `pokemon_entity_spawn` scripts (file names read from the local 1.8.0 jar's directory). Nothing in
  `base-pack/inventory/` mentions a callback.

### `poke_ball_capture_calculated` (recommended)

VERIFIED (source, `PokeBallCaptureCalculatedEvent.kt` at 1.8.0,
https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/events/pokeball/PokeBallCaptureCalculatedEvent.kt):

- Javadoc: "Event fired when a Poké Ball has completed its capture calculation and is about to begin shaking or
  breaking free. The result of the capture can be changed by replacing [captureResult]."
- Context (becomes `q.`): `thrower`, `pokemon` (the entity's `struct`), `poke_ball`, `is_successful_capture`,
  `is_critical_capture`.
- Functions: `set_shakes(numShakes, successful?)`, where `successful` defaults to `numShakes == 4` and critical is set
  false; `set_critical_capture(...)` forces success.
- `EmptyPokeBallEntity` posts it right after `Cobblemon.config.captureCalculator.processCapture(...)` and uses
  `event.captureResult` for the shakes; when shakes run out and the result is not successful it calls `breakFree()`,
  which completes `captureFuture` with `false` (the battle's capture action waits on that future). So the override
  applies in battle and out of it, and after any ball's own maths.
  https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/entity/pokeball/EmptyPokeBallEntity.kt
- `PokemonCatchRateEvent`'s own Javadoc says so: "If you want to prevent a Pokémon from being caught, you should be
  handling the [PokeBallCaptureCalculatedEvent] event instead."
  https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/events/pokeball/PokemonCatchRateEvent.kt
- `q.pokemon.level` exists: the `PokemonEntity` struct is built with `.addPokemonFunctions(pokemon)`
  (`PokemonEntity.kt` at 1.8.0), and `PokemonMoLangFunctions` has `map["level"] = { DoubleValue(pokemon.level.toDouble()) }`.
  https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/molang/function/PokemonMoLangFunctions.kt
- `q.thrower` for a player is `Player.asMoLangValue()`, which carries `EntityMoLangFunctions`,
  `LivingEntityMoLangFunctions` and `PlayerMoLangFunctions` (`MoLangFunctions.kt` at 1.8.0). Entity functions include
  `has_tag`, `add_tag`, `remove_tag` (`thisEntity.tags.contains(tag)`); player functions include `uuid`, `username`,
  `is_player`, `in_battle`, `run_command`, `has_advancement`, `data`/`save_data`.

The cost of this hook: the ball is used up and the player sees it break free, like a normal failed throw.

### `thrown_pokeball_hit` (cancel; out of battle only)

VERIFIED (source, `ThrownPokeballHitEvent.kt` and `Cancelable.kt` at 1.8.0):

- "Cancelling this event prevents the capture being started." Its functions are `pokeball`, `pokemon` and
  `cancelFunc`, which is `"cancel" to { cancel(); DoubleValue.ONE }`. So a callback can call `q.cancel()`; `q.pokeball`
  has `thrower`, `ball_type`, `capture_state`, `aspects`.
- On cancel, `EmptyPokeBallEntity.onHitEntity` calls `drop()`: the ball entity is discarded and the ball item dropped
  back (not in creative). That is the gentler outcome.
- **But in a battle** the same method has already added a `BattleCaptureAction` and called
  `throwerActor.forceChoose(ForcePassActionResponse())` *before* posting the event, and `drop()` neither completes
  `captureFuture` nor touches the capture action. ASSUMED risk, from reading the source: a cancel mid-battle may leave
  the battle waiting on a capture that never resolves. Use `thrown_pokeball_hit` only with `q.pokeball.thrower.in_battle`
  false, if at all.

### `pokemon_catch_rate_calculated` (not recommended)

VERIFIED: `set_catch_rate(rate)` exists with context `thrower`, `poke_ball_entity`, `pokemon_entity`, `catch_rate`.
ASSUMED: a rate of 0 may still let a ball that ignores the rate (Master Ball) or a critical capture through; the
Javadoc above points away from it.

## 2. Reading the player's RCT level cap

- **Command: VERIFIED.** rctmod 0.19.0-beta registers `rctmod player get level_cap [<target>]`, requiring permission
  level 1 (`Commands.literal(ModCommon.MOD_ID).requires(css -> css.hasPermission(1)).then(literal("player").then(literal("get").then(literal("level_cap")...`).
  Both executors end `return level_cap;`, the value from `RCTMod.getInstance().getTrainerManager().getData(player).getLevelCap()`.
  https://gitlab.com/srcmc/rct/mod/-/raw/v0.19.0-beta/common/src/main/java/com/gitlab/srcmc/rctmod/commands/PlayerCommands.java
  Also documented (0.18 docs): https://srcmc.gitlab.io/rct/docs/0.18/gameplay/commands/
- **Into a score: VERIFIED by composition.** `execute store result` "Stores the final subcommand's `result` or
  `success` value somewhere" (https://minecraft.wiki/w/Commands/execute), and the command's result is the cap.
- **How the cap is computed** (VERIFIED, `LevelUtils.levelCap` at v0.19.0-beta,
  https://gitlab.com/srcmc/rct/mod/-/raw/v0.19.0-beta/common/src/main/java/com/gitlab/srcmc/rctmod/api/utils/LevelUtils.java):
  `max(initialLevelCap, min over the series' next trainers of their level)`, where a trainer's level is its team's
  highest level plus `relativeLevelCap`. It **returns 0 while the player's state is loading**; a check must treat a
  cap of 0 as "unknown, allow".
- **The refusal it must match** (VERIFIED): `TrainerMob.replyTo` refuses when `tm.getPlayerLevel(player) > tpd.getLevelCap()`
  and replies with the dialog key `over_level_cap`; `getPlayerLevel` is the highest level in the party, fainted or
  not (`TrainerManager.java` at v0.19.0-beta). So "over the cap" is strictly greater: a Pokémon *at* the cap is safe to
  catch. Side finding for row 13: the refusal is not silent in code; it sends `over_level_cap` dialog, and whether our
  trainers' dialog carries that key decides whether the player sees anything (`docs/world-building/NAVIGATION.md:153,214`).
- **Not available** (VERIFIED absent in 1.8.0 source): no MoLang function reads a scoreboard (`PlayerMoLangFunctions`,
  `GeneralMoLangFunctions`, `EntityMoLangFunctions` listed in full), and `q.run_command` returns nothing to the script.
  No RCT scoreboard, placeholder or MoLang binding was found in the 0.18 docs page or the files read above. rctmod has
  no catch restriction of its own; `rctmod-server.toml` has only `initialLevelCap` / `relativeLevelCap`
  (`base-pack/cobbleverse/config/rctmod-server.toml:144,150`).
- **The bridge.** `q.run_command` runs as the server (`server()!!.commands.performPrefixedCommand(server()!!.createCommandSourceStack(), command)`,
  `GeneralMoLangFunctions.kt` at 1.8.0), so the non-op player's permission level does not matter. A function run that
  way can set a vanilla tag on the thrower, and the script reads it with `q.thrower.has_tag(...)` straight after.
  ASSUMED: the command runs to completion before `run_command` returns (vanilla runs a command immediately when no
  other command is executing; a ball hit is an entity tick, not a command). The blackout pack relies on the same
  call, but never on reading its result back.

## 3. How the repo refuses a ball for the Megas (M-4)

- The Mega guardians are spawned with the Cobblemon **`uncatchable`** property:
  `spawnpokemonat ... <species> <aspect> uncatchable level=<L>` (`tools/gulch_mine.py:1005-1006`,
  `tools/gulch_mine_audit.py:606`, design `docs/world-building/SOUTHERN_RIFT_MEGA.md:263,269`); scenes use
  `level=%d uncatchable no_ai` (`tools/scenes_pack.py:220`).
- VERIFIED in source (1.8.0 `UncatchableProperty.kt`): a flag property; `EmptyPokeBallEntity.onHitEntity` checks
  `UncatchableProperty.isCatchable(pokemonEntity)` *before* the hit event and, if not, sends `capture.cannot_be_caught`
  and `drop()`s the ball.
- VERIFIED in game on Cobblemon 1.8.0: "the Poké Ball is refused, 'it cannot be caught'"
  (`experiments/EXP-023-sleeping-celebi/README.md:31`); EXP-036 saw the flag carried on a Mega (`:20`). M-4 itself
  (a ball refused on the Mega, `SOUTHERN_RIFT_MEGA.md:512`) is not yet run.
- **Does not generalise to the cap.** It is a property of the Pokémon, the same for every player. With players on
  different caps, one flag would wrongly block, or wrongly allow, someone. It could be set on a spawn from the
  `pokemon_entity_spawn` callback (`apply` is listed in `PokemonMoLangFunctions`; its property-string behaviour is
  ASSUMED), but there is no single thrower at spawn time.

## 4. Fallbacks and whether each exists in 1.8.0

| Fallback | Exists? | Why not first |
|---|---|---|
| `thrown_pokeball_hit` + `q.cancel()` | VERIFIED | Battle-path risk above; fine as an out-of-battle add-on that saves the ball |
| `uncatchable` on over-cap spawns near players | VERIFIED property; per-spawn application ASSUMED | Per Pokémon, not per player; misses fishing and bait spawns unless each hook is covered; re-evaluated only at spawn |
| `pokemon_catch_rate_calculated` + `q.set_catch_rate(0)` | VERIFIED function | Master Ball and critical capture may bypass (ASSUMED); upstream Javadoc recommends the capture-calculated hook |
| Spawn pools below the next cap | already built (`EXP-035` `:116`) | Does not cover raids, fishing or events |
| A Cobbleverse dependency | none found | No catch or level-cap mod in `base-pack/inventory/`; Capture XP is incompatible with 1.8 (`mod_inventory.md:55`) |

## Recommended mechanism

A `poke_ball_capture_calculated` MoLang callback plus one function. Sketch only: not run, and the exact MoLang
string handling is the first thing the proof checks.

`data/cobblemon/callbacks/poke_ball_capture_calculated/cobblers_level_cap.molang`:
```
q.thrower.is_player ? {
  q.run_command('data modify storage cobblers:catch lv set value ' + q.pokemon.level);
  q.run_command('execute as ' + q.thrower.uuid + ' run function cobblers:levelcap/check');
  q.thrower.has_tag('cobblers.overcap') ? {
    q.set_shakes(0);
    q.thrower.remove_tag('cobblers.overcap');
  };
};
```
`cobblers:levelcap/check` (vanilla plus the RCT command):
```
tag @s remove cobblers.overcap
execute store result score @s cobblers.cap run rctmod player get level_cap @s
execute store result score @s cobblers.lv run data get storage cobblers:catch lv
execute if score @s cobblers.cap matches 1.. if score @s cobblers.lv > @s cobblers.cap run tag @s add cobblers.overcap
execute if entity @s[tag=cobblers.overcap] run tellraw @s {"text":"Over your level cap: it breaks free. The next gym would not battle you with it.","color":"red"}
```
Notes: the level goes through storage so that `25` and `25.0` both work (`data get` of a double returns its integer
part); a cap of 0 (RCT still loading) allows the catch; the tag is cleared at both ends. Scoreboard objectives must be
created at load. The file must sit under `data/cobblemon/callbacks/`, named `cobblers_*` (repo rule).

## Unknown / experiment candidates

1. The whole chain in game: callback fires for this event, `run_command` is synchronous, the tag is visible the
   same tick, `set_shakes(0)` breaks free in and out of battle, a Master Ball is also refused.
2. MoLang string + number: what `' ... ' + q.pokemon.level` yields (`25`, `25.0`, or an error). If it errors,
   `q.to_string(...)` is listed in `GeneralMoLangFunctions` (behaviour not read).
3. `q.thrower.is_player` on a non-player thrower (an NPC) returns 0 rather than erroring (ASSUMED).
4. `set_shakes(0)` versus `set_shakes(1)`: both unsuccessful by source; 0 goes straight to break-free (read, not run).
5. Paths that give a Pokémon without a thrown ball: raid den rewards, trades, gifts from our functions, eggs. Not
   covered by this hook; each needs its own check (unknown for Cobblemon Raid Dens).
6. Whether RCT's `sendSuccess` line per throw is noisy in the server log (it is sent without broadcast to ops).

## Smallest proof

Staging or a disposable world (never live), one player, the callback and function above in a proof datapack:

1. `/rctmod player get level_cap` prints N (expect 20 on a fresh player: `initialLevelCap = 20`).
2. `spawnpokemonat ~ ~ ~ rattata level=<N+5>` and one at `level=<N>`. Throw a Master Ball at each, out of battle:
   the over-cap one breaks free with the red message; the at-cap one is caught.
3. Battle a second over-cap Rattata, throw a Master Ball: it breaks free, the battle continues to the next turn (no
   hang), running away works.
4. Deop yourself and repeat step 2's over-cap throw: still refused (the command runs as the server).
5. After each throw `tag @s list` shows no `cobblers.overcap`; `latest.log` shows no callback error.

Pass = all five. Record the versions, the log lines and step 2's two outcomes.
