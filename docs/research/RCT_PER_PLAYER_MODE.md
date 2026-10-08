# Per-player Normal / Challenge mode on Radical Cobblemon Trainers

**Question.** Each player picks Normal or Challenge at Professor Oak; from then on every trainer that player
fights uses that mode's team. Can rctmod do that with data and commands only, and how?

**Answered for:** rctmod **0.19.0-beta**, rctapi **0.16.1-beta** (the server's, `docs/STATE.md` "World
facts"), Cobblemon 1.8.0, Minecraft 1.21.1 Fabric. 2026-10-04.

## How this was read

- **Source at the exact tags.** rctmod tag `v0.19.0-beta` = commit `97177cd5`; rctapi tag `v0.16.1-beta`
  (both from the GitLab tags API, `https://gitlab.com/api/v4/projects/srcmc%2Frct%2Fmod/repository/tags`).
  Files were read as `https://gitlab.com/srcmc/rct/mod/-/raw/v0.19.0-beta/common/src/main/java/com/gitlab/srcmc/rctmod/<path>`;
  below, **`R/<path>`** abbreviates that prefix.
- **Gap: quotes came through a summarising fetch tool.** Each quote below was returned when asked for verbatim
  code, but the tool's line numbers disagreed between two reads of the same file, so claims cite the **file and
  method**, not a line. A tag is also not byte-identical proof of the release jar. One read (sibling
  symmetry in `SeriesManager`) came back as fragments only and is marked as such.
- **Docs** (`https://srcmc.gitlab.io/rct/docs/latest/...`) are published as `latest` only, not pinned to
  0.19.0. Source wins where they differ.
- **Not read:** the upstream `COBBLEVERSE-RCT-DP-v20` mob files. The zip is not in this worktree or the main
  checkout (`base-pack/cobbleverse/datapacks/*` matched nothing). What upstream's Kanto mob files carry
  (`series`, `requiredDefeats`) is **relayed** from `docs/mechanics/LEAGUE_LEVEL_CAP.md:38-42`.

---

## 0. The answer

**rctmod has no per-player team and no difficulty-mode feature, but it has per-player series, and a series
is enough to build both modes. You need data and two commands; no mod.**

1. **Series is per player and set by command.** VERIFIED. The command is
   `rctmod player set series <seriesId> [<targets>]` (op 2). **Any** call clears the player's progress,
   even one naming the series they are already in. So run it once, at Oak, before the first required win.
2. **A team belongs to a trainer id, and an id has one team.** VERIFIED. So Challenge must be **separate
   ids**, for example `kanto_brock_challenge`. Give them a series of their own. **rctmod then refuses each
   mode's trainers to the other mode's players** by itself (`wrong_series`).
3. **A `trainer_spawner` cannot choose per player.** VERIFIED. It shuffles its `TrainerIds` and spawns the
   first one that passes spawn checks. It looks at no series and no `requiredDefeats`. So a gym needs **a
   second spawner** holding the Challenge id. That id needs a different `identity`, or the spawner's
   uniqueness rule stops it appearing beside Normal Brock.
4. **The level cap reproduces exactly.** VERIFIED from `LevelUtils`. The cap is the team's highest level plus
   `relativeLevelCap`, where the trainer's own value beats the series' and the config's. The Challenge ids
   give the same cap if their ace matches the Normal one (it does for Brock: 20 and 20). Where it does not,
   set a per-trainer `relativeLevelCap` to the difference.
5. **Badge flags need one more id in a list.** VERIFIED. The `rctmod:defeat_count` trigger matches **any**
   id in `trainer_ids`.

---

## 1. Can a player be in a different series, set by command? Does it reset progress?

### VERIFIED

| Claim | Source |
| --- | --- |
| The command tree is `rctmod player set series <seriesId>` with two optional parts. `[<targets>]` is `EntityArgument.players()`. `[completed <count>]` is `IntegerArgumentType.integer(0)`. The `set` node `.requires(css -> css.hasPermission(2))`, and the root `rctmod` requires 1 | `R/commands/PlayerCommands.java`, `register` (the `set` → `series` builder chain) |
| **Without `<targets>`, the source must be a player** (`context.getSource().getEntity() instanceof Player`). Otherwise it fails with `COMMANDS_ERRORS_CALLER_NOT_A_PLAYER`. The `<targets>` form loops over `EntityArgument.getPlayers(context, "targets")` | `PlayerCommands.player_set_current_series`, `player_set_current_series_targets` |
| `empty` maps to `""`, and `freeroam` is the other special id | `PlayerCommands.player_set_current_series`; `R/api/service/SeriesManager.java` constants `EMPTY_SERIES_ID = "empty"`, `FREEROAM_SERIES_ID = "freeroam"` |
| **An unknown series is refused**, with `COMMANDS_ERRORS_UNKNOWN_SERIES` sent to the player. A series counts as known if it has a file **or** any trainer lists it in `series`: the graph is created by `seriesGraphs.computeIfAbsent(sid, SeriesGraph::new)` while trainers are read | `R/api/data/save/TrainerPlayerData.java` `setCurrentSeries(String, boolean)`; `SeriesManager` `onLoad` |
| **Progress is cleared on every call except a freeroam pause or resume.** `setCurrentSeries(id)` passes `keepProgress = seriesPaused \|\| seriesContinued`, which is true only when switching to `freeroam`, or from `freeroam` back to the previous series. Otherwise `if(!keepProgress) { this.removeProgressDefeats(true); ...currentSeriesCompleted = false }`. The clear sits **outside** the `if(!seriesId.equals(this.currentSeries))` block, so **re-setting the series a player is already in also wipes their progress** | `TrainerPlayerData.setCurrentSeries(String)` and `(String, boolean)` |
| What is cleared is the player's **progress defeats** (`defeatedTrainerIds`, saved as `progressDefeats`). These drive the level cap and `requiredDefeats`. `completedSeries` is kept | `TrainerPlayerData` fields and save keys `progressDefeats`, `completedSeries`, `currentSeries`, `previousSeries`, `currentSeriesCompleted`; `removeProgressDefeats(boolean)` |
| The **per-trainer defeat counts** are a separate store, so a series switch does not touch them. `rctmod player get defeats`, the `defeat_count` loot condition and the advancement trigger all read them. They live in `TrainerBattleMemory`, one saved file per trainer id (`TrainerManager.getBattleMemory(level, trainerId)` → `dds.computeIfAbsent(..., TrainerBattleMemory.filePath(trainerId, ver))`) | `R/api/service/TrainerManager.java` `getBattleMemory`; `R/api/data/save/TrainerBattleMemory.java` |
| New players start in `initialSeries = "kanto"` | `modpack/config/rctmod-server.toml:159` |
| A dialogue action's `q.run_command` runs as the **server**, and it runs at once inside a dialogue action. `q.player.run_command` would need the player to be op | `experiments/EXP-022-native-dialogue-runtime/README.md:34-35`; the pattern `q.run_command('tag ' + q.player.username + ' add ...')` is already emitted at `tools/compile_dialogue.py:497` |

**So the Oak line is** `q.run_command('rctmod player set series cobblers_challenge ' + q.player.username);`.
It uses the `<targets>` form, because the server source is not a player. Every part of that is read from
source except the series id, which is ours to create (§5).

### Consequences

- **Lock the choice.** A second Challenge click, or a later "switch to Normal", clears progress. The level
  cap then drops to `initialLevelCap` (20). Every party member over 20 then gets the player refused by
  **every** rctmod trainer (`over_level_cap`; `canBattleAgainst` checks
  `tm.getPlayerLevel(player) <= tpd.getLevelCap()`, `R/world/entities/TrainerMob.java`). Oak's dialogue
  must offer the choice once, guarded by our own quest field or tag.
- **Normal needs no command.** Normal players stay in `kanto`, the initial series. Running
  `set series kanto` would only risk the wipe.
- **A deliberate mid-game switch can be repaired.** `rctmod player set progress [<players>] (before|after)
  <trainerId>` exists. Its `before` body clears progress and then re-adds the trainer's prerequisites that
  belong to the current series (`PlayerCommands.player_set_progress_before`). The exact argument order
  comes from the docs page `gameplay/commands/` (latest), not from the builder chain. **ASSUMED, not run.**

---

## 2. One id with per-player teams, or separate ids? Spawners, and keeping the modes apart

### VERIFIED

| Claim | Source |
| --- | --- |
| A trainer's team is `TrainerMobData.trainerTeam`: one `TrainerTeam` per trainer id, loaded from `trainers/<id>.json`. No field in the mob data selects a team by player, series or difficulty. The whole field list is `type`, `signatureItem`, `requiredDefeats`, `requiredSeries`, `series`, `substitutes`, `optional`, `maxTrainerWins`, `maxTrainerDefeats`, `battleCooldownTicks`, `relativeLevelCap`, `spawnWeightFactor`, `biomeTagBlacklist`, `biomeTagWhitelist`, the four `forceBattle*` fields and `winCommands` | `R/api/data/pack/TrainerMobData.java`, field declarations |
| rctapi's `TrainerModel` holds `name`, `ai`, `bag`, `team`, `battleTheme`: one literal team | `https://gitlab.com/srcmc/rct/api/-/raw/v0.16.1-beta/common/src/main/java/com/gitlab/srcmc/rctapi/api/models/TrainerModel.java` |
| **Eligibility at interaction, in full:** `getCooldown()==0`, not in battle, player not in battle, active Pokémon > 0, player level `<=` level cap, mob `requiredSeries` met, missing `requiredDefeats` (**filtered to required ids that are of the player's current series**) empty, **`(tmd.isOfSeries(tpd.getCurrentSeries()) \|\| bm.getDefeatByCount(this.getTrainerId(), player) > 0)`**, and `couldBattleAgainst` | `R/world/entities/TrainerMob.java` `canBattleAgainst` |
| `isOfSeries(id)` is `this.series.isEmpty() \|\| this.series.contains(id)`. A **seriesless** trainer battles players of every series | `TrainerMobData.isOfSeries` |
| The persistence bypass is only in `couldBattleAgainst` (`isPersistenceRequired() \|\| ...`), so **a `summon_persistent` trainer still enforces series and requirements** | `TrainerMob.couldBattleAgainst`, `canBattleAgainst` |
| **Spawner choice:** `attemptSpawn` copies `getTrainerIds()`, calls `Collections.shuffle`, then for each nearby player tries each id with `attemptSpawnFor(player, trainerId, pos, true, true, guaruantee, 1.0, 1.0)` and keeps the first that spawns | `R/world/blocks/entities/TrainerSpawnerBlockEntity.java` `attemptSpawn`; NBT keys `TrainerIds`, `OwnerUUID` |
| `attemptSpawnFor` checks: a valid id, spawnable position, `canSpawnFor` (counts, player level > 0, trainer card if configured), `isUnique(identity)`, and chance unless boosted. **No series, no `requiredDefeats`, no `isOfSeries`** | `R/api/service/TrainerSpawner.java` `attemptSpawnFor` (3 overloads), `canSpawnFor`, `isUnique`, `computeChance` |
| `isUnique` refuses a spawn when any `TrainerMob` with the same **identity** stands within a box of side `2*uniqueTrainerRadius`. Ours is 151 | `TrainerSpawner.isUnique`; `modpack/config/rctmod-server.toml:55` |
| `identity` is a field of the trainer (team) file. When absent it is derived from the trainer's name. Docs: "Defines the persona this trainer represents (if not defined falls back to `displayName`)" | `R/api/data/pack/TrainerTeam.java` (fields `identity`, `battleFormat`, `battleRules`; `getIdentity()` fills it from the name; read as a summary, not verbatim); docs `configuration/data_pack/trainers/` |
| `rctmod trainer summon` / `summon_persistent` check **no** identity and no series. They strip a `TrainerId` from the NBT argument and call `setTrainerId(id)` | `R/commands/TrainerCommands.java` `summonTrainer` |
| The trainer entity saves and **loads** `TrainerId`. `readAdditionalSaveData` calls `setTrainerId(...)`, which notifies the spawner (`notifyChangeTrainerId`) and re-runs `updateTrainerNPC(trainerId)` | `TrainerMob.addAdditionalSaveData`, `readAdditionalSaveData`, `setTrainerId` |
| Who gets credit: on a player win, `distributeRewards` calls `tpd.addProgressDefeat(mob.getTrainerId())`, `btm.addDefeatedBy(mob.getTrainerId(), player)` and `DEFEAT_COUNT.trigger(player, mob)` for each winning player and losing mob. Credit goes to **whatever id the entity carries at the end of the battle** | `R/api/data/TrainerBattle.java` `distributeRewards` |
| No rctmod changelog from 0.17.0 to 0.19.2 mentions difficulty, modes or per-player variants. 0.18.0 added mob `requiredSeries` and TBCS win commands | Modrinth API `https://api.modrinth.com/v2/project/rctmod/version` (changelogs) |

**Answer to 2:**
- **Separate ids.** One id cannot carry two teams.
- **A single spawner cannot serve both modes.** With both ids in `TrainerIds`, a random one appears, and the
  other mode's players are refused until it despawns.
- **Series keeps the modes apart with no extra work.** Put the Challenge ids in a Challenge series and leave
  the Normal ids in `kanto`. `canBattleAgainst` then refuses a Normal player at Challenge Brock and the
  reverse, with the `wrong_series` dialog key (key name: `docs/world-building/NAVIGATION.md:153`, from a jar
  read).
- **One leak:** a player who already has a defeat on record against an id passes the series check for it
  (`bm.getDefeatByCount(...) > 0`). That cannot happen if the mode is locked at Oak.

### ASSUMED

- **That `data merge entity <trainer> {TrainerId:"<id>"}` swaps a live trainer's team.** The load path calls
  `setTrainerId` (VERIFIED). Vanilla `data merge entity` re-loading the entity is general Minecraft
  knowledge, not quoted here. Our `{Cooldown:40}` merge works on these entities through the same
  `readAdditionalSaveData` (`tools/route_trainers.py:63-66`). What `notifyChangeTrainerId` does to a
  spawner-owned mob was **not read**. Experiment E7.
- **`substitutes` (undocumented) as an alternative.** `SeriesManager` Stage 3 adds each `getSubstitutes()` id
  as a `sibling`. Read in fragments only: `TrainerNode.isDefeated` is true if `trainerIds.contains(id) ||
  siblings.anyMatch(isDefeated) || ancestors.anyMatch(isDefeated)`, and `addProgressDefeat` records the node
  **and its non-alone siblings**. Two ids in **one** series with `substitutes` would let either one's defeat
  count for both. Whether siblings are added symmetrically was not readable. The bigger problem: in one
  series rctmod does **not** stop a player fighting the other mode's copy. Not recommended.

---

## 3. The level cap in each design

### VERIFIED (`R/api/utils/LevelUtils.java`)

- **The cap:** `levelCap(player)` = `max(initialLevelCap(sid), min over sm.getGraph(sid).getNext(defeats) of
  trainerLevel(sid, id))`, else `maxLevel()` = 100. It is cached per (series, progress-defeat set).
- **A trainer's level:** `trainerLevel(sid, id)` = `max(min(100, max(0, highest team level +
  relativeLevelCap(sid, id))), max over getRequiredDefeats of trainerLevel(sid, req))`.
- **`relativeLevelCap(sid, id)`** takes the trainer's mob `relativeLevelCap` first, then the series file's,
  then the server config's (ours is 0, `modpack/config/rctmod-server.toml:153`). The range is -100..100,
  clamped (`TrainerMobData.getRelativeLevelCap`).
- **`initialLevelCap(sid)`:** the series file's value, else the config's (20, `rctmod-server.toml:144`).
- **What `getNext(defeats)` skips:** it is `getNext(defeats, false, false)`, so it leaves out **optional**
  nodes and **alone** nodes (no edges) (`SeriesManager` `SeriesGraph.getNext`).
- **Seriesless trainers are in every series graph:** `SeriesManager.onLoad` stage 2 puts every trainer with
  empty `series` into each graph. Ours are `optional: true` with no edges (`tools/route_trainers.py:372`),
  so they never set a cap. That stays true if a route trainer is given a series and keeps `optional: true`
  and no `requiredDefeats`.

**Two series:**
- A Normal player's cap is unchanged: same series, same ids.
- A Challenge player's cap comes from the Challenge chain.
- **Matching the Normal curve** (`gym_ace_levels` 20..55, `data/trainers.json:14-23`) takes three
  conditions:
  1. each Challenge id's **highest team level + its `relativeLevelCap`** equals the Normal ace;
  2. the Challenge `requiredDefeats` chain mirrors Kanto's (the `max over requiredDefeats` term then agrees);
  3. the Challenge series file sets no `initialLevelCap` or `relativeLevelCap` that differ from Kanto's.
- **Brock:** Normal top level 20 (`data/trainers.json:85`); the Challenge team's top level is 20
  (`data/trainers.json:360-373`). Same cap with no offset.
- **Every record:** each carries one record-level `ace_level` (`data/trainers.json:93, 547, 1012, ...`). A
  generator should **assert** that each mode's team maximum equals it, and emit
  `relativeLevelCap = ace_level - team max` only where they differ.
- The League (E4 aces 60, Blue 62) and the "100 after Blue" end (`docs/mechanics/LEAGUE_LEVEL_CAP.md:50-56`)
  carry over if the 5 League ids are mirrored too: **13 Challenge ids**, not 8.

**Single series with id swapping (E7):** the cap stays Kanto's, because the series never changes. The
progress credit, however, goes to whichever id the entity carried at the end. A swapped Challenge copy that
is not in Kanto's graph gives **no progress defeat** (`addDefeatedBy` only records the progress defeat
`if(... getGraph(currentSeries).contains(trainerId))`, `TrainerBattleMemory.addDefeatedBy`). The cap
would then never rise. So swapping suits **seriesless, optional** trainers only (routes), never bosses.

**Cache:** the trainer-level cache is not cleared on `/reload`
(`docs/mechanics/LEAGUE_LEVEL_CAP.md:34-35`, read from the same file at the same tag). **Restart** after
installing the Challenge ids.

---

## 4. Badge flags

### VERIFIED

- The `defeat_count` codec is `trainer_ids` (list, default `[]`), `trainer_type` (default `""`) and
  `count` (default 1) (`R/advancements/criteria/DefeatCountTriggerInstance.java`, `CODEC`).
- `matches` returns `getDefeatByCount(mob.getTrainerId(), player) >= count` when
  `trainerIds.contains(mob.getTrainerId())`. So **any listed id** satisfies the criterion, counted against
  that id's own record (same file, `matches`).
- It fires from `distributeRewards` for winning players only (above).
- Our flags list ids per region key: `data/progression.json:55-63` has `"trainer_ids": {"kanto":
  ["kanto_brock"], ...}`. `tools/progression_pack.py:106-111, 273-274` writes that list straight into the
  criterion.

### What changes

- **Flags:** add the Challenge id to each Kanto list, e.g. `["kanto_brock", "kanto_brock_challenge"]`. No
  new flag, and everything that reads `gymN_cleared` keeps working.
- **Naming clash:** `data/progression.json`'s `series`/`active` (`kanto`, `johto`, ...) is the
  campaign's **region** key, not rctmod's per-player series. A Challenge player is in rctmod series
  `cobblers_challenge` and in campaign region `kanto` at once. Name the new series so nobody confuses the two.

### Every other system keyed on a Normal leader id needs the Challenge id

("Our list is not the world.")

- **The leader rematch hold-off** (`tools/route_trainers.py:447-486`) builds lines per leader spawner and
  badge flag. A second spawner needs its own lines. Because it tests the badge flag, it works unchanged once
  the flag lists both ids.
- **Loot:** upstream leader loot tables are emptied (`upstream_neutralised`, `tools/route_trainers.py:457-459`).
  The Challenge ids need explicit `{"pools": []}` tables. **ASSUMED:** without one, the three-tier fallback
  (`single/` → `groups/` → default, docs `configuration/fallback_data_system/`) may hand a new id a default
  table.
- **The rest:** `first_win` rewards, `tools/legendaries_audit.py` `rct_caps`, `tools/battle_sim.py` and
  `tools/challenge_guide.py` all key on leader ids and must learn the second.

---

## 5. The smallest design that works (data + two commands)

**Normal: no change.** Series `kanto`, upstream ids, our team overrides, today's spawners.

**Challenge:**

1. **Series file** `data/rctmod/series/cobblers_challenge.json`.
   - Docs: series live at `data/<namespace>/series/<id>.json`, and the file name is the id (docs
     `configuration/data_pack/series/`).
   - Fields: `SeriesMetaData` record: `title`, `description`, `difficulty` (1..10), `initialLevelCap`,
     `relativeLevelCap`, `hideTrainerIdentities`, `requiredSeries` (`R/api/data/pack/SeriesMetaData.java`).
   - Write `title`, `description` and `difficulty` only. Leave both caps unset so the config's 20 and 0 apply,
     as for Kanto.
   - **ASSUMED:** that `rctmod` is the right namespace. `SeriesManager` takes the id from the file name and
     the namespace was not traced. Our trainer files already use `data/rctmod/`.
2. **Thirteen Challenge ids**, `<upstream id>_challenge`, generated from each record's
   `modes.challenge.rct` (64 of 64 records carry a `challenge` mode: `grep -c` on `data/trainers.json`).
   For each id:
   - `trainers/<id>.json`: the Challenge team, `battleFormat`, and a **distinct `identity`** so it can
     stand beside the Normal leader;
   - `mobs/trainers/single/<id>.json`: upstream's mob fields, with `"series": ["cobblers_challenge"]` and
     `requiredDefeats` re-pointed to the Challenge ids, plus `relativeLevelCap` only where §3 needs it;
   - `dialogs/trainers/single/<id>.json`, including a `wrong_series` line for Normal players;
   - an empty loot table.
3. **At Oak**, once, guarded by our own field:
   - Challenge: `q.run_command('rctmod player set series cobblers_challenge ' + q.player.username);`
   - Normal: nothing.
4. **Gyms:** a second `rctmod:trainer_spawner{TrainerIds:["kanto_brock_challenge"]}` next to each leader's
   spawner, in our gym build (`data/gym_buildings/gym*.json` `leader.spawner`). Gym 2 is a template spawner
   (`tools/route_trainers.py:478-486`), so we place an extra block there.
   - **League:** the five spawners belong to the upstream `kanto_league` template
     (`tools/route_trainers.py:41-50`), so place five more by `setblock` in our reapply.
   - **Both leaders stand in every gym.** Each refuses the other mode. Whether that is acceptable fiction,
     or the Challenge spawner should be placed only when a Challenge player exists, is **the owner's
     call**.
5. **Flags:** append the Challenge ids to `data/progression.json` `trainer_ids.kanto`. Extend the hold-off
   cycle and the audits (§4).
6. **Route and placed trainers** (seriesless, `summon_persistent`). They do not move the cap, so either
   choice is safe for the cap:
   - **R-a, all mechanisms verified:** a second seat entity per trainer. Normal copy `"series": ["kanto"]`,
     Challenge copy `"series": ["cobblers_challenge"]`, both `optional: true`, no `requiredDefeats`, so
     neither enters the cap (§3). Cost: twice the entities on every route, each refusing half the players.
   - **R-b, one entity, needs E7:** the existing 10-tick cycle merges `TrainerId` to the nearest player's
     mode, never while `InBattle`. Cheap and clean for one player. In mixed co-op the nearest player
     decides.
   - Either way, the per-trainer advancement (`tools/route_trainers.py:398-400`) lists both ids, so
     `quest.<id>.defeated` is set by either.

**Rejected:**
- **One spawner holding both ids:** random leader, no series check.
- **One series with `substitutes`:** the mode is not enforced, and the semantics were only partly read.
- **Bosses as Cobblemon NPCs** (`docs/research/notes/arena-per-player-opponents.md`): this loses rctmod's
  cap refusal, the `defeat_count` badge flags and the gym loot wiring.

---

## 6. Side finding (bears on EXP-A1 in `notes/rct-arena-capabilities.md` §7)

`requiredDefeats` on a **seriesless** trainer should gate from source:
- The required id is seriesless, so `isOfSeries(current)` is true and the requirement survives the filter in
  `canBattleAgainst`.
- Seriesless trainers are nodes in every series graph (§3).
- A required node has an ancestor, so it is not alone, and `addProgressDefeat` records it.

Two exceptions:
- in series `empty`, `addProgressDefeat` returns false and the gate can never open;
- in `freeroam` it records nothing unless resuming.

The record is a **progress** defeat, so **a series switch re-locks** such a gate. Source reading only; EXP-A1
is still the proof.

---

## 7. What must be proven in game, and the experiment

Staging only, after a restart with the probe data installed: series `cobblers_challenge`, `kanto_brock_challenge`
and `kanto_misty_challenge` (mirroring Brock and Misty), flag lists extended. Players: **P** (Normal) and **Q**
(Challenge); one account can play both in sequence.

| # | Step (exact commands) | Must show |
| --- | --- | --- |
| E1 | Fresh Q: `rctmod player get series Q`; then, from a test dialogue action, `q.run_command('rctmod player set series cobblers_challenge ' + q.player.username)`; then `get series Q`, `get level_cap Q`, `get progress Q` | `kanto`, then `cobblers_challenge`; cap 20; empty progress; no unknown-series error |
| E2 | Summon both leaders at a gym; P right-clicks Challenge Brock, Q right-clicks Normal Brock | each refused with the `wrong_series` line; each battles their own |
| E3 | Q beats `kanto_brock_challenge`; `rctmod player get level_cap Q`, `get progress Q`, `get defeats kanto_brock_challenge Q` | cap 25 (Challenge Misty's ace); progress lists the Challenge id; defeats 1. The same for P on the Normal ids |
| E4 | after E3 | `gym1_cleared` granted to Q (`advancement` list); `first_win` reward fires once |
| E5 | two spawners in one gym, distinct identities | both leaders spawn and coexist; then the same identity: only one spawns (proves the uniqueness rule both ways) |
| E6 | Q (with Brock beaten) runs `rctmod player set series cobblers_challenge Q` **again** | progress empties and cap returns to 20 (the source reading of "re-set wipes"; the reason for the Oak lock) |
| E7 | one persistent seated route trainer; `data merge entity <uuid> {TrainerId:"<id>_challenge"}`; Q battles it | the Challenge team appears; `get defeats <id>_challenge Q` = 1; the advancement listing both ids fires; no log error. Then the same on a **spawner-owned** leader, to see what `notifyChangeTrainerId` does |
| E8 | Q (cap 25) has a level-24 Pokémon; P loses nothing | no `over_level_cap` surprise from the mode switch done before any win |

---

## 8. Unknown (not written to `EXPERIMENT_BACKLOG.md`; the brief limited writes to this file)

- The sibling symmetry of `substitutes` (read in fragments).
- `notifyChangeTrainerId` on a spawner-owned mob.
- The `rctmod` namespace for the series file.
- The fallback loot for a new id.
- The upstream Kanto mob files' exact `series` and `requiredDefeats` values (relayed, not read).
- Whether a Normal player's view of two leaders is acceptable (owner).
