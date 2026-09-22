# EXP-027: a won leader battle sets that player's badge flag

## Objective

Nothing set `gymN_cleared`: the flags existed as data (`data/progression.json`) and a generator
(`tools/progression_pack.py`, whose trigger and command syntax loaded in EXP-020), but the pack was never installed and
never fired with a player. The Rift guards, the trader tiers, the waystone unlocks and the mainline quest beats all
read these flags. This experiment wires the flags into the re-application and proves, on the staging export, that:

1. beating a leader sets that leader's flag for the player who won, and the Champion sets `champion_cleared`;
2. a loss or a forfeit sets nothing;
3. setting rctmod progress by command sets nothing (only a won battle does);
4. the flag is per player: a second player's flags are untouched;
5. the flag survives a restart, and a re-export (`tools/carry_players.py`).

## How a defeat is recorded (read from the jars, 2026-09-21)

Mod set: Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, rctmod-fabric 0.19.0-beta, rctapi 0.16.0-beta,
CobbleverseBadges 1.3, COBBLEVERSE-RCT-DP v20. Bytecode read with `javap -c`, not decompiled source.

- **The leader.** `COBBLEVERSE-RCT-DP-v20` defines each Kanto leader as an rctmod trainer (`data/rctmod/trainers/kanto_brock.json`
  and so on, series `kanto`, `maxTrainerDefeats: 1`, `spawnWeightFactor: 0`: they never spawn naturally). The badge is
  an item in the leader's loot table (`loot_table/trainers/single/kanto_brock.json`: `cobbleversebadges:kanto_boulder_badge`
  under the condition `rctmod:defeat_count == 1`). CobbleverseBadges 1.3 holds only items and recipes: no event, no
  advancement. So the badge item is the only thing the pack records, and an item can be dropped, traded or lost.
- **The event.** `com.gitlab.srcmc.rctmod.server.ModServer` subscribes to Cobblemon's `CobblemonEvents.BATTLE_VICTORY`.
  `onBattleVictory` looks the battle up by the winners' actor ids (`removeBattleFromInitiator(winners, true)`) and
  then the losers' (`false`), and calls `TrainerBattle.distributeRewards(initiatorWon)`.
- **The record.** `distributeRewards` takes the winning side's players and the losing side's trainer mobs. For each
  pair it calls `TrainerPlayerData.addProgressDefeat(trainerId)` (the player's series progress, level cap),
  `TrainerBattleMemory.addDefeatedBy(trainerId, player)` (the trainer's per-player defeat count), and then fires the
  advancement trigger `rctmod:defeat_count` for that player. When the trainer's side wins, the winning side has no
  players, so nothing is recorded or fired.
- **The trigger.** `DefeatCountTriggerInstance.matches(player, mob)`: with `trainer_ids` set, true when the mob's trainer
  id is in the list and `getDefeatByCount(trainerId, player) >= count`. The defeat is added before the trigger fires, so
  `count: 1` matches on the first win.
- **Saved where.** The flag is a vanilla advancement, `cobblers:flag/<id>`, saved per player in the world's
  `advancements/<uuid>.json`. rctmod's own records are `data/rctmod.player.<uuid>.stat.dat` and
  `data/rctmod.trainers.*.mem`.
- **Commands.** `/rctmod player set defeats <trainerId> <value> <targets>` and `/rctmod player add progress` change
  rctmod's records without a battle; they do not go through `distributeRewards`, so they should not set a flag
  (checked below).

Not read: whether Cobblemon fires `BATTLE_VICTORY` on a forfeit (the source says a forfeit ends the battle with the
other side as winner; tested below).

## Implementation

- `tools/progression_pack.py`: one advancement per flag on `rctmod:defeat_count` with the leader's `trainer_ids` and
  `count: 1`; `--report <stopped world>` lists each player's flags (fails when the world has no player).
- `tools/reapply.py`: `prepare` builds `cobblers_progression`, `install` installs it (it is in `SERVER_PACKS`).
- `tools/carry_players.py`: copies every player's state from the stopped old world into the fresh export (advancements,
  playerdata, stats, Cobblemon player data, Pokedex, party and PC, CobbleDollars, rctmod's player and trainer records,
  the scoreboard), refuses to overwrite, checks each file by sha256, and fails when there is nobody to carry.
- Tests: `tests/test_progression_pack.py`, `tests/test_carry_players.py`.

## Test instructions (staging export `cobblers-dryrun4`)

Brock (`kanto_brock`, team level 16-20) and Blue (`kanto_champion_blue`, six level-100 Pokemon) stand on the League's
forecourt, `/tp @s 3576 86 2724`. The player is in survival, series `kanto`.

1. **Loss.** Party: one level-5 Magikarp. Challenge Brock and lose. Check `gym1_cleared` is false.
2. **Forfeit.** Challenge Brock again and forfeit. Check it is still false.
3. **Command progress.** `/rctmod player set defeats kanto_misty 1 <player>`. Check `gym2_cleared` is false.
4. **Win.** Party: two level-25 Pokemon (the level cap before Brock is 25). Beat Brock. Check `gym1_cleared` is true and
   no other flag is.
5. **Champion.** Mark the eight leaders and the Elite Four defeated by command (step 3 shows this sets no flag), give
   a level-100 team, beat Blue. Check `champion_cleared` is true and gym 2-8 flags are still false.
6. **Second player.** A second account joins; its flags are all false.
7. **Restart.** Stop, `progression_pack.py --report`, boot, check the flags in game.
8. **Re-export.** Carry the players into a fresh world with `carry_players.py`, boot it, check the flags in game.

## Results

Not yet run: this needs a player to battle. Recorded here when it has.

## Limitations

- One leader and the Champion are battled. The other seven leaders' advancements are the same generated form, checked
  by `tests/test_progression_pack.py`, not by a battle each.
- Multi-player battles (two players against one trainer) would set the flag for both winners, by the same code path;
  not tested.
