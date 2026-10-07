# One leader per gym: the Challenge swap

**Decided** by the owner on 2026-10-07 (`docs/STATE.md` "What is decided", the owner's answers item 6;
`docs/HANDOVER_SESSION.md` section 2b item 6): all thirteen bosses (eight leaders, the Elite Four, the Champion)
stand as **one** person. The Normal spawner stays. The second (Challenge) spawner goes. The spawner's `TrainerIds`
and the standing trainer's `TrainerId` switch to `<id>_challenge` while the nearest player within reach carries the
Challenge tag, and switch back otherwise. They never switch during a battle. **Order:** prove it on Brock in staging,
then widen it to the other twelve.

Built by `tools/challenge_mode.py` (`single_lines`, `retire_lines`, `single_leader_verify`) into
`build/datapacks/cobblers_trainers`. The switch is `data/challenge_mode.json` `single_leader.rollout`. It is
`["kanto_brock"]` today.

## Mechanism rung

**Functions/commands** (rung 6 of CLAUDE.md principle 6), on the trainers clock that already exists. The earlier
rungs do not cover this:

- **Cobblemon native / rctmod (addon):** a `trainer_spawner` cannot choose per player. It shuffles its
  `TrainerIds`, spawns the first id that passes, and checks no series (VERIFIED from source,
  `docs/research/RCT_PER_PLAYER_MODE.md` section 2, "Spawner choice"). One id has one team, so the two modes have to
  be two ids (same section, "Answer to 2"). No rctmod mob field picks a team per player.
- **Configuration:** no rctmod config key does it (`modpack/config/rctmod-server.toml`, read in full for spawner
  and trainer keys).
- **Datapack data alone:** the series data keeps the modes apart (`wrong_series`), but something still has to
  pick which id stands at the one spawner.
- That leaves a command that rewrites the id. This is option R-b of `RCT_PER_PLAYER_MODE.md` section 5, already
  generated for every route trainer (`tools/challenge_mode.py` `swap_lines`). It is applied here to a
  spawner-owned trainer as well.

## What runs, and where state lives

| State | Where | Per player or shared |
| --- | --- | --- |
| A player's mode | the scoreboard tag `cobblers_mode_challenge` (set at Oak, `data/challenge_mode.json` `mode.tag`), plus rctmod series `cobblers_challenge` | per player |
| Which id the leader carries | the spawner block entity's `TrainerIds` and the trainer entity's `TrainerId` | shared (one leader) |
| Badge and defeat | rctmod's per-trainer defeat memory, and `gymN_cleared`, which lists both ids (`data/progression.json`) | per player |

**The swap** (`single_lines`) lives in `cobblers:trainers/challenge/cycle`, which runs every 10 ticks. Every line
first checks that the spawner's chunk is loaded, that the spawner block is there, and that no `kanto_brock` or
`kanto_brock_challenge` within 24 of the spawner reads `InBattle:1b`. Each line then works out the nearest player
**from the spawner's position**, so the block and the trainer always follow the same player:

1. The block: Challenge id if the nearest player within reach has the tag. Normal id if that player lacks the tag,
   or if nobody is within reach. A line only merges when the block holds the other id, so nothing is rewritten
   every cycle.
2. Then the trainer: the same three rules, with `data merge entity` on a trainer that reads `InBattle:0b`.

The block goes first because the trainer's `setTrainerId` notifies its spawner (`notifyChangeTrainerId`,
`RCT_PER_PLAYER_MODE.md` section 2). Both changes happen in one function run, before the world ticks the spawner.
That ordering of the tick is general Minecraft knowledge, not quoted from source.

**Reach: 17 blocks.** `reach()` computes it: rctmod's server-wide `forceBattleMaxDistance` (16.0,
`modpack/config/rctmod-server.toml:122`) plus 1. That is the same `sight + 1` the route swap uses. 16 is the
farthest a trainer starts a battle on sight (`forceBattleOnSight = true`, line 117). So inside 17 blocks the
leader already carries the nearest player's mode, and beyond it no battle can start. Two other distances do not
set this one:

- The spawner's own spawn range (how near a player must be before it spawns) **was not read**. It is not in the
  config. If that range is wider than 17, the spawner may spawn a Normal Brock for a Challenge player who is still
  far away. The swap converts him once that player comes within 17. If it is narrower, the block already holds the
  right id when he spawns.
- The leader hold-off acts at 9 (`tools/route_trainers.py` `leader_cycle_lines`). 17 is wider, so the id is
  settled before the hold-off reads it. A test asserts this.

**Never during a battle.** `InBattle` is rctmod's documented entity tag ("actively participating in a battle",
docs `gameplay/entities/`, recorded in `docs/research/notes/rct-arena-capabilities.md:59`). The `0b`/`1b` byte form
is assumed. **If rctmod never saves that tag, the trainer lines match nothing and Brock stays Normal:** a Challenge
player is refused, never given the wrong team. The block lines would still switch, so the staging read-back below
checks for the tag. Nothing else in our data can detect a battle.

**Mixed group.** The nearest player within 17 decides. rctmod checks eligibility per player at the moment of
interaction: `canBattleAgainst` requires `isOfSeries(currentSeries)` or an existing defeat. So a Normal player at a
Challenge Brock, or the reverse, is refused with the `wrong_series` line. **Source reading, not run:**
`RCT_PER_PLAYER_MODE.md` section 2, the "Eligibility at interaction" row and "Answer to 2". The in-game proof is E2
in section 7. In practice, whoever walks up to Brock becomes the nearest player and gets their own team within 10
ticks. A second player of the other mode is refused until they are the nearest. One leak is known from the same
section: a player who already has a defeat against an id passes the series check for it. The lock at Oak prevents
that.

**Edge cases.** *Late join, or a player who never chose at Oak:* no tag, so Normal. *Death mid-battle, or a
disconnect:* rctmod ends the battle, `InBattle` clears, and the next cycle follows whoever is nearest. *Nobody
near:* both the block and the trainer go back to Normal. *Re-export:* the gym's own build re-sets the spawner to
`["kanto_brock"]`, and the swap takes over from there.

## Retiring the second spawner

A world that ran the earlier build holds Brock's second spawner at **(1830, 155, 3696)**
(`data/challenge_mode.json` `bosses.kanto_brock.spawner.at`, read). The cycle placed it whenever a player came
within 48. `cobblers:trainers/challenge/retire_kanto_brock_challenge` removes it once:

- the redstone block at y154 goes back to `minecraft:stone_bricks`, and the spawner back to
  `minecraft:polished_andesite`. Both blocks are read from gym 1's own voxel model (`tools/gym_buildings.py`
  `build_one`), never from a world. Each change runs only if that cell still holds the Challenge spawner;
- any `kanto_brock_challenge` within 24 of that cell is killed, but never one in a battle, and only while no player
  is within 17. With nobody near, the swap keeps the one leader on the Normal id, so a Challenge-id trainer there
  must belong to the old spawner.

Reapply step **R17L** runs it after R17. The step forceloads a box 24 blocks around both spawners, waits 3 s, runs
the function, then reads the result back (`check single_leader`). `cobblers_trainers` stays EXCLUDED as
self-driving, so `prepare`'s coverage gate is unchanged.

For a template boss (Misty, the League), the rollout fails closed until `single_leader.restore {floor, under}` is
measured from its template. For the League, `single_leader.normal_at` is also needed: no record carries those five
spawners. So `"rollout": "all"` refuses today. A test checks that it does.

## Staging proof for Brock

### (a) RCON, no player (staging only, after install, the restart and R17L)

| # | Command | Must read |
| --- | --- | --- |
| a1 | `forceload add 1806 3672 1856 3720`, then wait 3 s | — |
| a2 | `execute if block 1832 155 3696 rctmod:trainer_spawner` | Test passed (the one spawner; `data/gym_buildings/gym1.json` `leader.spawner`, read) |
| a3 | `data get block 1832 155 3696 TrainerIds` | `["kanto_brock"]` (nobody near) |
| a4 | `execute if block 1830 155 3696 rctmod:trainer_spawner` | Test failed (the second spawner is gone) |
| a5 | `execute if block 1830 155 3696 minecraft:polished_andesite` and `execute if block 1830 154 3696 minecraft:stone_bricks` | Test passed, both |
| a6 | `execute if entity @e[type=rctmod:trainer,x=1830.5,y=155,z=3696.5,distance=..24,nbt={TrainerId:"kanto_brock_challenge"}]` | Test failed |
| a7 | `data merge block 1832 155 3696 {TrainerIds:["kanto_brock_challenge"]}`, then at once `data get block 1832 155 3696 TrainerIds`, then again after 1 s | first the Challenge id (the block accepts the merge), then `["kanto_brock"]` (the nobody-near line put it back) |
| a8 | if a2's trainer stands: `data get entity @e[type=rctmod:trainer,x=1832.5,y=155,z=3696.5,distance=..24,limit=1] InBattle` | a byte (`0b`). **No such tag means the battle guard has nothing to read:** stop and report before (b) |
| a9 | `forceload remove 1806 3672 1856 3720` | — |

The R17L read-back (`single_leader_verify`) covers a2, a3, a4 and a6. a5, a7 and a8 are by hand.

### (b) The owner in game (gym 1, Brock's gallery, spawner (1832, 155, 3696))

| # | Who | Must show |
| --- | --- | --- |
| b1 | Q (Challenge) alone walks in | `data get block 1832 155 3696 TrainerIds` reads the Challenge id; Brock brings the Challenge team (six) |
| b2 | During Q's battle, P (Normal) stands closer to Brock than Q | `data get entity <Brock> TrainerId` stays `kanto_brock_challenge` until the battle ends |
| b3 | Q wins | `rctmod player get defeats kanto_brock_challenge Q` = 1; `gym1_cleared` granted |
| b4 | P alone | Normal team |
| b5 | Mixed: P nearest, Q right-clicks Brock; then the other way round | the farther player is refused with the `wrong_series` line |
| b6 | Throughout | one Brock only: `execute if entity @e[type=rctmod:trainer,x=1832.5,y=155,z=3696.5,distance=..24]` counts 1. A second Brock means the spawner reacted to `notifyChangeTrainerId` (unknown, E7) |

## Not verified

None of this has run in a game. The following are assumed:

- that `data merge` changes a trainer's team, and what a spawner does when its trainer's id changes (E7);
- that the spawner block entity accepts a `TrainerIds` merge (a7 tests this);
- the `InBattle` byte form (a8 tests this);
- the spawner's own spawn range.

The Challenge audit (`tools/challenge_mode_audit.py`, not edited) fails two checks for Brock by design:
`P:count` (0 Challenge spawners) and `R:summon` (the retire function's `kill`). Its owner decides how the audit
treats a single-leader boss.
