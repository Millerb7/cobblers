# Heaven's Arena: per-player opponents spawned and started by command

**Question.** Can the arena spawn a trainer in front of one player, start that player's battle by command
(no walking up), learn whether that player won or lost, remove the opponent, chain the next fight, and do it
for two players at once without their fights touching? The owner's brief: "a battle zone where a player can go
in and always find a cool battle or gauntlet ... early levels single battles, then back to back ... each player
has their own progress and their opponent is spawned in front of them."

**Answered for:** Cobblemon **1.8.0+1.21.1** (Fabric, the server's runtime), rctmod 0.19.0-beta / rctapi
0.16.1-beta from earlier reads only. 2026-10-03.

## How this was read

- **Jar entry names** come from the 1.8.0 jar in this worktree,
  `experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods/Cobblemon-fabric-1.8.0+1.21.1.jar`. A zip's
  entry names are stored uncompressed, so a ripgrep over the jar lists them. File **contents** are deflated
  and could not be read that way.
- **This session had no shell**, so the brief's Python `zipfile` read could not run. The contents below
  were read from Cobblemon's public source at git tag **`1.8.0`**
  (`https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/common/src/main/...`), paired with the jar entry
  that proves the same file ships.
  - **Gap:** a tag is not byte-identical proof of the release jar.
  - **Gap:** the WebFetch tool returns source through a summarising model. Every code quote below came back
    when asked for it verbatim. Two quotes are long: `PoolPartyProvider.formulateParty` and
    `BattleBuilder.pvn`. Re-read those two from the jar with a shell before building on a detail.
- **The rctmod jar is not in this worktree.** Reading it from the live server's `mods/` would be touching the
  runtime, which needs the lock, so it was not read. rctmod facts are quoted from
  `docs/research/notes/rct-arena-capabilities.md` and the rctmod docs.

---

## 0. The plain answer

**Use Cobblemon 1.8.0's own NPCs (`cobblemon:npc`), not rctmod.** Everything the owner asked for has a
verified mechanism in the 1.8.0 source, and the uncertain parts are few enough for one short in-game proof to
settle:

| Need | Mechanism | Status |
| --- | --- | --- |
| Spawn in front of a player | `execute as <p> at @s rotated ~ 0 positioned ^ ^ ^4 run spawnnpcat ~ ~ ~ <class> <level>` | command VERIFIED in source; `spawnnpcat` used in this repo (EXP-022, R9F) |
| A team chosen per fight | NPC class `party` of type `pool` with `"isStatic": false`. A fresh team is rolled at every challenge, filtered by the NPC's level (`npcLevels`) | VERIFIED in source; not run |
| Start the battle by command | `runmolang "q.npc.start_battle(q.player, 'singles');" <player> <npc>` | function and command VERIFIED in source; not run |
| Learn win or loss per player | our own `data/cobblemon/callbacks/battle_victory/*.molang`, or the NPC's `player_win_command` / `player_lose_command` config | hook VERIFIED in source and proven in game for our blackout callback; arena use not run |
| Remove the opponent | `kill @e[type=cobblemon:npc,tag=<owner tag>]` | vanilla; not run on an arena NPC |
| Back-to-back fights | re-run `start_battle` on the same NPC (new team every time), or kill and spawn the next; heal or not with `start_battle`'s 5th argument | VERIFIED in source; not run |
| Two players at once | one NPC per player, matched to its owner by a tag or score; the NPC battles only the player named in the command | VERIFIED in source (a battle is built for one named player); not run with two accounts |

rctmod can spawn by command but has **no documented start-battle command**. It allows one trainer per
identity within 151 blocks, and its only result hook fires on wins alone. It is the worse engine for this
(§6).

---

## 1. Spawning a trainer in front of a specific player

### VERIFIED

| Claim | Source |
| --- | --- |
| Cobblemon 1.8.0 has `SpawnNPCCommand`, `NPCEditCommand` and `NPCDeleteCommand`, and **no** Cobblemon command whose name starts a battle (the command classes are listed in full; the only battle ones are `SpectateBattleCommand` and `StopBattleCommand`) | jar entries `com/cobblemon/mod/common/command/*Command.class` |
| `spawnnpc <class> [level]` spawns at **the command source's position**; `spawnnpcat <pos: vec3> <class> [level]` at a given position. Both create `NPCEntity`, `moveTo(pos)`, set `npc = class`, call `initialize(level)`, `addFreshEntity`; level defaults to 1 and has a minimum of 1. The command returns only a success count, not the entity | `SpawnNPCCommand.kt` @1.8.0, `register()` and `execute()` |
| `spawnnpcat` is the command this repo already uses for placement (`tools/reapply.py:1990`, `tools/compile_dialogue.py:402`) | repo |
| **NPC classes load only at server start**: a class added by `/reload` is unknown, and a function naming a class fails to parse at load | `experiments/EXP-022-native-dialogue-runtime/README.md:39` (run in game) |
| NPC class fields (Kotlin defaults): `names`, `aspects`, `hitbox`, `battleConfiguration`, `interaction` (null), `canDespawn = true`, `variations`, `config`, `variables`, `party` (null), `skill = 0`, `autoHealParty = true`, `randomizePartyOrder = false`, `battleTheme`, `behaviours` (JSON alternates `behaviors`, `ai`), `isMovable = true`, `isInvulnerable = false`, `isLeashable = true`, `allowProjectileHits = true`, `hideNameTag = false` | `api/npc/NPCClass.kt` @1.8.0 |
| `battleConfiguration` has one live field, `canChallenge` (default **false**); `simultaneousBattles` and `healAfterwards` are `@Deprecated("This is not likely to get used")` | `api/npc/configuration/NPCBattleConfiguration.kt` @1.8.0 |
| An NPC with `canDespawn: true` is not persistence-required (`isPersistenceRequired() = super... \|\| !npc.canDespawn`) | `entity/npc/NPCEntity.kt` @1.8.0 |
| Behaviours are applied in a class as `"ai": [{"type": "apply_behaviours", "presets": ["cobblemon:kitchen_sink"]}]` | `data/cobblemon/npcs/kitchen_sink.json` @1.8.0 (entry in jar) |
| Shipped behaviours include `battler` (battling-activity tasks `switch_npc_from_battle`, `look_at_target`, `look_at_battling_pokemon`, `exit_battle_when_hurt`; idle task `switch_npc_to_battle`), `battle_commands`, `battle_scripts`, `party_configuration`, `looks_at_players`, `stationary` | jar entries `data/cobblemon/behaviours/*.json`; `battler.json` @1.8.0 |

**Spawning in front.** `execute as <player> at @s rotated ~ 0 positioned ^ ^ ^4 run spawnnpcat ~ ~ ~ <class>
<level>` puts the NPC four blocks ahead on the player's horizontal facing.
- **VERIFIED:** relative coordinates in a vec3 argument resolve against the executing position (vanilla
  `execute`).
- **VERIFIED:** `spawnnpc` would do the same, since it uses the source position.

Because the command does not return the entity, a second line tags the NPC that was just created. For
example, `tag @e[type=cobblemon:npc,tag=!arena,distance=..1,limit=1] add arena`, run at the same position.
Then `tp @s ~ ~ ~ facing entity <player>` turns it towards the player.

### ASSUMED

- **The arena's class line must be a macro.** By analogy with EXP-046, where a `spawnpokemonat` line fails
  but a macro line works, the line naming the class should be `$spawnnpcat ~ ~ ~ $(class) $(level)`. The
  premise is EXP-022's finding that a function naming a class fails to parse at load. **Not run for
  `spawnnpcat`.**
- **The NPC may despawn.** With `canDespawn` left at true, a mob despawn rule could remove an arena NPC.
  Set `"canDespawn": false` and remove NPCs ourselves.

---

## 2. The team: chosen per fight

### VERIFIED

| Claim | Source |
| --- | --- |
| Party provider types in 1.8.0: `SimplePartyProvider`, `PoolPartyProvider`, `ComposedPoolPartyProvider`, `ScriptPartyProvider`; also `PartyPool`, `PartyComposition` | jar entries `api/npc/partyproviders/*.class`, `api/npc/*.class` |
| JSON for the pool provider: `"type": "pool"`, `minPokemon`, `maxPokemon` (MoLang expressions, defaults 1 and 6), **`isStatic` (read with `json.get("isStatic").asBoolean`, so it must be present)**, optional `useFixedRandom`, and `pool`, a list of strings or objects | `PoolPartyProvider.loadFromJSON` @1.8.0; example `npc_presets/battler_test.json` |
| A pool entry object has `pokemon` (a properties string), `levelVariation` (default 0), `level` (optional), `npcLevels` ("a-b", default 1-100), `selectableTimes` (default 1) and `weight` (default 1). The last three are MoLang expressions | same |
| **A non-static party is rolled at every challenge.** `getPartyForChallenge(players)` returns the stored party if one exists; else, if `isStatic == false`, it returns `npc.party.provide(this, level, players)`. `initialize(level)` stores a party only when `isStatic` is true | `NPCEntity.getPartyForChallenge`, `NPCEntity.initialize` @1.8.0 |
| **The NPC's level picks the tier.** `formulateParty` keeps only entries with `level in npcLevels`. Each Pokémon's level is its own `level=` property if set, else the entry's `level`, else NPC level + `0..levelVariation` | `PoolPartyProvider.formulateParty` @1.8.0 |
| **The player is visible to the roll.** With exactly one player, `formulateParty` sets `q.player` (and `q.players`, `q.level`, `q.npc`) in the runtime that evaluates `weight`, `selectableTimes`, `minPokemon` and `maxPokemon` | same |
| `can_battle` is 1 for a non-static party even with no stored party | `NPCMoLangFunctions.kt` @1.8.0, `map["can_battle"]` |
| The simple provider is `"type": "simple"` with `"pokemon": [<properties strings>]` | `data/cobblemon/npcs/standard.json` @1.8.0 |
| `moveset_builders/alpha.json` and `wild.json` ship in the jar | jar entries |

**What this gives the arena.** One class per opponent type, never one per tier.
- **The tier is the spawn level.** `spawnnpcat ... cobblers:arena_ace 35` draws only from that class's
  entries whose `npcLevels` include 35.
- **The team is new every fight.** A gauntlet can even re-challenge the same NPC and get a different team.
- **Weights can read the player.** They are MoLang with `q.player` set, so they could read our per-player
  fields; for example, avoid species the player has already beaten.

### ASSUMED

- That `q.player.data` resolves inside a pool `weight` expression. The player struct is set, so it should;
  **not run.**
- How `composed_pool` and `party_pools` / `party_compositions` are written. The classes exist, but **their
  JSON was not read** and the jar ships no example files under those folders. Use `pool` until they are read.
- Whether a class edited by `/reload` changes its pool. Classes load only at start (EXP-022), so plan on
  restarts for team changes.

---

## 3. Starting the battle by command

### VERIFIED

| Claim | Source |
| --- | --- |
| `runmolang <molang: string> [player] [npc: entity] [pokemon]` binds `q.player` to the player and `q.npc` to the NPC's `struct` | `RunMolangCommand.kt` @1.8.0 |
| `q.npc.start_battle(opponent, format?, level?, clone?, healFirst?, rules?)` exists on the NPC struct. It is registered in `NPCServerDelegate.addToStruct` together with `is_in_battle_with`, `was_hurt_by`, `is_in_battle`, `run_dialogue` and `save_data` | `entity/npc/NPCServerDelegate.kt` @1.8.0 |
| Cobblemon's own scripts call it exactly this way: `q.npc.start_battle(q.player);` and `q.npc.start_battle(q.player, 'double');` | `molang/npc/instant_battle_interaction.molang`, `dialogues/npc-example.json` @1.8.0 (both in the jar) |
| Argument 0 takes a player struct, a UUID string or a name. Argument 1 is a format id: `single`/`singles`/`single_battle`, `double`/`doubles`/`double_battle`, `triple`/`triples`/`triple_battle`; anything else means singles | `NPCServerDelegate.kt`; `BattleFormat.fromFormatIdentifier` @1.8.0 |
| It calls `BattleBuilder.pvn(player, npcEntity, format, cloneParties, healFirst)` and returns the battle struct on success, 0 on failure | same |
| `pvn` refuses when the player has too few healthy Pokémon, **is already in a battle**, has a Pokémon that is busy, or the NPC has no party. **The NPC's own "already in battle" check is commented out**, and `BATTLE_IDS` is a set: one NPC can be in several battles | `BattleBuilder.pvn` @1.8.0 |
| `pvn` does **not** read `canChallenge` or any cooldown. `canChallenge` gates player-initiated challenges, not this path | same (no reference) |
| `healFirst` (argument 4) heals the player's team as it is built (`toBattleTeam(clone, healPokemon = healFirst)`). `cloneParties` (argument 3) battles with copies | same |
| A player's `q.player.start_battle` is **PvP only** (`BattleBuilder.pvp1v1`) | `PlayerMoLangFunctions.kt` @1.8.0 |
| `q.run_command` runs as the server; `q.player.run_command` runs as the player and needs their permission. Under `/runmolang` a nested command is queued, not immediate | EXP-022 README:34-35 (bytecode and in game) |

### Two source findings: risks, not blockers

1. **The level argument changes a shared format.** `start_battle` assigns `format.adjustLevel = setLevel`
   to the object `fromFormatIdentifier` returns, which is the shared `GEN_9_SINGLES` / `DOUBLES` /
   `TRIPLES` constant.
   - **Rule:** never pass argument 2. Every call without it writes -1 back.
   - **Rule:** with argument 2 set, `cloneParties` is forced true.
2. **The call drops the format's default rules.** With no rules argument, `rules` is `emptySet()`, and
   `setBattleRules` then builds the format with `ruleSet = emptySet`. That drops `OBTAINABLE`, `PAST` and
   `UNOBTAINABLE`, which `GEN_9_SINGLES` otherwise carries. Arena battles are therefore laxer about move and
   item legality than a right-click NPC battle. **Effect in game not checked.**

### ASSUMED

- That a battle started from RCON or a function opens the player's battle UI the same way a click does.
  Cobblemon's own `instant_battle_interaction` uses the same call from a script interaction, so it is
  likely; **not run**.
- That `execute store result` can capture `runmolang`'s outcome. Not read. Instead, check
  `q.player.in_battle` (a documented player function) a tick later to detect a refused start.

---

## 4. Learning the result per player

### VERIFIED

| Claim | Source |
| --- | --- |
| Cobblemon ships `data/cobblemon/callbacks/battle_victory/npc_battle_end_scripts.molang` | jar entry |
| **The loss side.** For each `t.loser` in `c.scriptable_losers` whose `config.player_win_command` is not blank, it builds a command and runs `q.run_command`. The command replaces `{{player}}` (`t.player_winner.player.username`), `{{player_id}}` (uuid), `{{npc}}` (`t.loser.name`) and `{{npc_id}}` (`t.loser.uuid`), for each `t.player_winner` in `c.player_winners`. It first runs the MoLang in `config.on_defeat` and `config.on_player_wins` | that file @1.8.0 |
| **The win side.** It does the same for `c.scriptable_winners` × `c.player_losers` with `config.player_lose_command`, `on_victory` and `on_player_loses`, and also replaces `{{pokemon_id}}` | same |
| **The per-player cooldown.** If `t.npc_actor.npc.config.challenge_cooldown != 0`, it stores `last_challenged_time` in **each player's** `get_npc_data(<npc uuid>)` and saves | same |
| These config variables are declared by the shipped behaviours `battle_commands` (`player_win_command`, `player_lose_command`, TEXT, default "") and `battle_scripts` (`on_defeat`, `on_victory`, `on_player_wins`, `on_player_loses`) | `behaviours/battle_commands.json`, `battle_scripts.json` @1.8.0 |
| An entity's `config` is filled from its registered variables' defaults (`initializeScripting`) and saved in its NBT | `entity/MoLangScriptingEntity.kt` @1.8.0 |
| **Our own `battle_victory` callback works in game.** `cobblers_blackout` reads `c.scriptable_winners` (`.is_npc`, `.is_pokemon`, `.uuid`), `c.player_losers` (`.player`) and `c.scriptable_losers`, and runs functions with `q.run_command`. Callbacks must live under `data/cobblemon/callbacks/` | `tools/blackout_pack.py:1033-1063`; `docs/STATE.md` (EXP-042, "Callbacks must sit under `data/cobblemon/callbacks/`") |
| Per-player persistent fields through `q.player.data()` / `save_data()` are in use and survive restarts | EXP-022 README:32; `tools/route_trainers.py:335` |

**Recommended hook: our own callback, beside Cobblemon's.** Add
`data/cobblemon/callbacks/battle_victory/cobblers_arena.molang`.
- **On a win:** for every loser that `is_npc`, and every player winner, it runs
  `execute as <npc uuid> if entity @s[tag=arena] as <player uuid> run function cobblers:arena/won`.
- **On a loss:** the mirror image runs `.../lost`.
- **Why:** it needs no per-NPC configuration, every name in it is already proven in the blackout callback,
  and the tag check means it ignores every other NPC battle in the world.
- **Alternative, Cobblemon's intended path:** apply `cobblemon:battle_commands` to the class and set
  `player_win_command` to `execute as {{player_id}} run function cobblers:arena/won`.

### ASSUMED

- **How the alternative gets its value.** `player_win_command` needs a value on each spawned NPC. A class
  `config` entry with that `variableName` and a `defaultValue` (as `standard.json` does for
  `challenge_cooldown`) should supply it; that route is **not traced end to end**.
- **What a flee or forfeit fires.** Whether it raises `battle_victory` (with the NPC as winner) or only
  `BATTLE_FLED` is unknown. The blackout work found that running from a wild battle is not a loss
  (STATE, EXP-042); an NPC battle was not tested. The arena's tick must treat "the NPC is no longer
  `in_battle` and no result arrived" as abandoned.
- **Whether a win pays money.** CobbleDollars' `earnCobbleDollarsFromNPC` paid on rctmod wins
  (rct-arena note §4). That it pays for `cobblemon:npc` battles is not checked.

---

## 5. Despawn, back-to-back, and two players

### VERIFIED

| Claim | Source |
| --- | --- |
| Entity MoLang functions include `discard`, `add_tag`, `remove_tag`, `has_tag`, `uuid`; NPCs also have `in_battle`, `battles`, `stop_battles` | `EntityMoLangFunctions.kt`, `NPCMoLangFunctions.kt` @1.8.0 |
| `pvn` keys the battle to the one player passed in; the NPC side is `NPCBattleActor(npcEntity, npcParty, skill)` | `BattleBuilder.pvn` @1.8.0 |
| A non-static party is a new `NPCPartyStore` per challenge, not stored on the NPC (`provide(...)` returns one; `getPartyForChallenge` does not assign it) | `NPCEntity.getPartyForChallenge` @1.8.0 |
| `StopBattleCommand` exists | jar entry |

**Removal.** Kill the arena NPC with `kill @e[type=cobblemon:npc,tag=arena,...]`. The repo already counts and
kills `cobblemon:npc` this way in `tools/research_station.py:1285`, though that is not shown to have run.
Schedule the kill a second or two after the result rather than inside the callback.

**Gauntlet.**
- **Next opponent:** on `won`, either re-run `start_battle` on the same NPC, which rolls a new team, or kill
  it and spawn the next class or level.
- **Healing:** the fifth argument chooses whether the player's team is healed first.
- **Progress:** the player's position in the gauntlet is ours to keep, in `q.player.data()` or a score;
  §4's callback advances it.

**Two players.**
- **Give every player their own NPC.** It is spawned in front of them, tagged `arena`, and matched to its
  owner. A per-player score copied onto the NPC works (`arena_id`); so does a macro tag naming the owner.
- **Start with the owner's selector.** `runmolang` is always called with the owner as `player` and their own
  NPC as `npc`.
- **Battles are per player.** A battle is built for the one player named, and a non-static team is a fresh
  store per challenge, so the two fights share no Cobblemon state.
- **A shared opponent might also work, but do not rely on it.** One NPC fighting both players at once looks
  possible: the NPC's busy check is commented out. Its behaviour (look-at targets, `exit_battle_when_hurt`,
  and a static party shared by two battles) is unknown. Use one NPC per player.

### ASSUMED

- **Others clicking an NPC.** That `canChallenge: false` with no `interaction` stops a passing player from
  clicking into someone else's opponent, or challenging it by sending out a Pokémon. The flag defaults to
  false, but where it is read was not traced.
- **The level cap.** An arena NPC is not an rctmod trainer, so rctmod's `over_level_cap` refusal will not
  apply. Assumed rctmod does not hook every Cobblemon battle.
- **XP.** Battles still give XP, and the arena is an XP faucet (rct-arena note §6) unless it is priced or
  capped on purpose. `cloneParties` (argument 3) would make fights consequence-free. Whether it also gives
  no XP is not read.

---

## 6. rctmod, for comparison

- **Spawn: VERIFIED.** `rctmod trainer summon <trainerId> [<position>] [<nbt>]` is documented
  (`https://srcmc.gitlab.io/rct/docs/latest/gameplay/commands/`, "latest", not pinned to 0.19.0).
  `summon_persistent` is in use for 63 seats (`docs/STATE.md`).
- **Start: none documented.** The commands page lists no command that starts a battle. Battles start by
  right-click or by eye contact ("looking at one for a few moments"). So a trainer spawned facing the player
  might start the fight by itself.
  - **ASSUMED:** whether eye contact fires reliably for a summoned trainer.
  - **ASSUMED:** whether the `forceBattle` settings apply.
- **Per player: blocked.** "It is impossible for multiple trainers with the same identity to spawn", within
  `uniqueTrainerRadius = 151` (rct-arena note §3). Two players fighting the same tier at once would need a
  copy of every trainer id per concurrent player.
- **Teams: static.** A literal `team` array with no pool and no level scaling (rct-arena note §2).
- **Result: wins only.** The `rctmod:defeat_count` advancement fires on wins only, once per grant. A loss
  has no rctmod hook. EXP-039 left open whether RCT battles appear in `battle_victory`.
- **Conclusion: native NPCs** (principle 6 order: Cobblemon native first).
- **What rctmod keeps:** the per-player level cap, and the CobbleDollars payout already measured on its
  trainers. A design that needs rctmod's cap refusal must add its own check before the fight.

---

## 7. The smallest in-game proof (proposed EXP: arena per-player NPC)

**Prerequisite.** Install a probe datapack world-local in staging, then **restart**, because classes load at
start (EXP-022). Every field in the class is one listed in §1 and §2 from `NPCClass.kt` or a shipped
example; nothing else is invented.

`data/cobblers/npcs/arena_probe.json`:
```json
{
  "hitbox": "player",
  "names": ["Arena Challenger"],
  "canDespawn": false,
  "isInvulnerable": true,
  "isMovable": false,
  "battleConfiguration": { "canChallenge": false },
  "skill": 3,
  "ai": [ { "type": "apply_behaviours", "presets": ["cobblemon:battler", "cobblemon:looks_at_players"] } ],
  "party": { "type": "pool", "minPokemon": "1", "maxPokemon": "2", "isStatic": false,
             "pool": [ { "pokemon": "geodude", "npcLevels": "1-100" },
                       { "pokemon": "zubat",   "npcLevels": "1-100" },
                       { "pokemon": "machop",  "npcLevels": "1-100" } ] }
}
```
`data/cobblemon/callbacks/battle_victory/cobblers_arena_probe.molang`:
```
for_each(t.l, c.scriptable_losers, { t.l.is_npc ? { for_each(t.w, c.player_winners, {
  q.run_command('execute as ' + t.l.uuid + ' if entity @s[tag=arena_probe] run tag ' + t.w.player.username + ' add arena_won');
}); }; });
for_each(t.w, c.scriptable_winners, { t.w.is_npc ? { for_each(t.p, c.player_losers, {
  q.run_command('execute as ' + t.w.uuid + ' if entity @s[tag=arena_probe] run tag ' + t.p.player.username + ' add arena_lost');
}); }; });
```

**Steps over RCON.** Player `P` stands on open ground.

1. **Spawn in front.**
   `execute as P at @s rotated ~ 0 positioned ^ ^ ^4 run spawnnpcat ~ ~ ~ cobblers:arena_probe 12`, then
   `execute as P at @s rotated ~ 0 positioned ^ ^ ^4 run tag @e[type=cobblemon:npc,distance=..1,limit=1] add arena_probe`,
   then `execute as @e[tag=arena_probe] at @s run tp @s ~ ~ ~ facing entity P`.
   **Must show:** one NPC four blocks in front of P, facing P. `execute if entity @e[tag=arena_probe]`
   answers 1.
2. **Start without a click.**
   `runmolang "q.npc.start_battle(q.player, 'singles');" P @e[tag=arena_probe,limit=1]`.
   **Must show:** P's battle screen opens and the opponent is level 12, one or two of the three species.
   Note anything in the log.
3. **Win.** P wins; then run `tag P list`.
   **Must show:** `arena_won`, and no `arena_lost`.
4. **New team, then a loss.** Run step 2 again on the same NPC; P loses on purpose (or forfeits, recorded
   separately). **Must show:** the team differs from step 2's, as a non-static roll per challenge, or is
   recorded as the same; and `arena_lost` after the loss, or nothing after a forfeit (§4 unknown).
5. **Remove.** `kill @e[type=cobblemon:npc,tag=arena_probe]`. **Must show:** the NPC is gone, nothing drops
   and no error is logged.
6. **Two players.** With P and Q, repeat step 1 for each, tagging `arena_p` / `arena_q` as well, and start
   both battles within a few seconds. P wins and Q loses.
   **Must show:**
   - both battles run at once;
   - `arena_won` only on P and `arena_lost` only on Q;
   - killing Q's NPC after its result leaves P's state untouched;
   - Q right-clicking P's NPC does not start a battle (`canChallenge: false`).

**What two players need beyond one.**
- **Identity:** a second account. EXP-034 is gated on the same thing.
- **Ownership:** a per-player marker on each NPC (a score or owner tag), so every command selects the
  owner's NPC and never `@e[...,limit=1]` across the room.
- **Layout:** each player's spawn point clear of the other's line of sight in the building, which is cosmetic.

**Out of scope for the proof, worth a later run:** a macro function doing step 1 (§1 assumption), the heal
argument, doubles, and a player logging out mid-fight (the NPC must be swept).

---

## Unknown: experiment candidates (also in `EXPERIMENT_BACKLOG.md`)

- **The core loop.** Spawn in front, start by `runmolang`, see the result through the callback, kill: the
  proof above.
- **Flee, forfeit and logout:** which event, if any, reaches the callback.
- **One shared NPC in two battles at once:** is it a failure, or harmless?
- **Function form:** `spawnnpcat` naming a datapack class from a macro function, after a restart.
- **Team-by-player:** a pool `weight` reading `q.player.data.<field>`.
- **Format:** the empty rule set (§3) — does an arena battle accept something a normal battle rejects?
- **Money:** CobbleDollars on a `cobblemon:npc` win.


## 8. RESULT, run in game 2026-10-03 (staging-2026-10-01, the owner playing, one player)

The probe pack of section 7 was installed world-local (`cobblers_arena_probe`, staging only) and the server restarted.
- **Spawn: PASS.** `spawnnpcat X Y Z cobblers:arena_probe 12` with ABSOLUTE coordinates spawns the class at level 12
  (`data get ... Level` -> 12); the relative form `execute ... positioned ^ ^ ^4 run spawnnpcat ~ ~ ~ ...` spawned
  nothing and printed nothing. Command output is empty either way: find the NPC by position and tag it.
- **Start without a click: PASS.** `runmolang "q.npc.start_battle(q.player, 'singles');" @s <npc>` run as the player
  opened the battle screen immediately ("opened immediately", the owner). It returns the battle's UUID on success and
  **0 when refused**: it returned 0 while the player had no Pokemon (Cobblemon's `standard` class refused the same
  way), and a UUID once `givepokemonother` had given one.
- **Win: PASS.** The `battle_victory` callback added `arena_won` and not `arena_lost` (twice).
- **Loss: PASS.** `arena_lost` and not `arena_won`. **The loss also fired our blackout** (the player was sent home to
  (1461, 118, 5306)): the arena needs its own blackout exception (data/arena_fights.json open question 4).
- **Re-roll: PASS.** Fight 1 and 2 Machop, fight 3 Zubat: the non-static pool re-rolls per challenge (a repeat is
  chance in a three-entry pool).
- **Remove: PASS.** `kill` by tag; no error. The NPC unloads with its chunk when the player leaves (a teleport home
  after a loss): cleanup must load the chunk or run while the player is near.
- Not run: two players at once (needs a second account), a forfeit/run, `canChallenge: false` against a click.
