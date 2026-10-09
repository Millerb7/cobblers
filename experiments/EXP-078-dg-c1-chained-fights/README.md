# EXP-078: C1, the first chained fight: a macro `spawnnpcat` after a plain restart, and three follow-ups in a row

**Status: PART ONE PASSED (spawn after a plain restart, by macro); the chain OPEN (2026-10-08).** Probe C1 (new) of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
Heaven's Arena proved spawn, start, win, loss, re-roll and remove one at a time, and never chained one fight into the
next (F3); `docs/STATE.md` lists the in-function spawn as NOT proven. Every stand (3.1) and the staged boss (3.2) rest
on both. C1 proves (1) `spawnnpcat` from a MACRO line in a function after a plain restart with no `/reload`, beside a
PLAIN line for comparison (EXP-046 found a plain `spawnpokemonat` does nothing until a reload; whether `spawnnpcat`
shares that is the question), and (2) a victory's follow-up starting the next battle 60 ticks later, three times in a
row (four stages).

## Success criteria
- Part 1: `c1/spawn_macro` returns 1 on the first call after a plain restart. `c1/spawn_plain` is recorded (1 or 0, or
  absent from the boot as unparseable).
- Part 2: four battles, each started with no click; `#won` 4, `#follow` 3, `#refused` 0, `#lost` 0, `#done` 1, and
  `#gap_last` 60 (game ticks from the keeper seeing the win with `in_battle` 0 to the next start).

## Dependencies
Cobblemon 1.8.0 `spawnnpcat`, `runmolang`, `q.npc.start_battle`, `q.player.in_battle`, the `battle_victory` callback
(the arena probe's callback, PASS in game 2026-10-03); NPC classes load only at a restart.

## Implementation
`cobblers_dg_probes:c1/*`; objectives `dpc1.st`, `dpc1.r`; classes `cobblers_dg_probes:c1_s1..c1_s4` (one Pokemon each,
`rattata 5`, `pidgey 6`, `zubat 7`, `caterpie 8`); callback
`data/cobblemon/callbacks/battle_victory/cobblers_dg_probes_c1.molang` (tags the winner `dpc1.won`, or the loser
`dpc1.lost`, only when the NPC carries `dpc1.npc`). Area x 3328..3583; pen at (3360, 96, -640), box
`x=3351,y=95,z=-649,dx=18,dy=3,dz=18`.
- `npc_at`: `$spawnnpcat $(x) $(y) $(z) $(cls) $(level)` (the arena's macro, absolute coordinates).
- `spawn_macro`: class `c1_s1` at (3365.5, 96, -636.5) through `npc_at`; `spawn_plain`: the same with a literal
  `spawnnpcat 3355.5 96 -636.5 cobblers_dg_probes:c1_s1 5`. Each returns how many it claimed.
- `chain` (as the owner): stage 1 at the stand (3360.5, 96, -636.5); `go` starts it 20 ticks later. On a win the
  keeper's next pass with `in_battle` 0 runs `next`: the stage is killed, "He gets up again.", stage k+1 spawned 40
  ticks later and started 20 after that (60 in all), until four are won.

## Test instructions
Install: copy the pack in, then a PLAIN restart (stop, start). No `/reload` at any point before step 3.

### (a) RCON, no player (part 1)
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | grep the boot log for `cobblers_dg_probes:c1/` | no `Failed to load` (or only `c1/spawn_plain`: record it, that is part 1's plain answer) | `c1/npc_at` or `c1/spawn_macro` failed to load |
| 2 | `function cobblers_dg_probes:c1/setup`; wait 15 s; `scoreboard players get #ready dpc1.st` | 1 | |
| 3 | `function cobblers_dg_probes:c1/spawn_macro` | `returned 1` | `returned 0`: a macro spawn did nothing after a plain restart; the engine's stands cannot be built this way |
| 4 | `data get entity @e[tag=dpc1.t1,limit=1] NPCClass` (or the whole entity if that key is absent) | names `cobblers_dg_probes:c1_s1` | |
| 5 | `function cobblers_dg_probes:c1/spawn_plain` | record `returned 1` or `returned 0` | |
| 6 | `function cobblers_dg_probes:c1/clear_tests` | `returned 1` | |

### (b) The owner in game (part 2; a party able to beat four level 5-8 Pokemon)
| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:c1/enter` | in the pen |
| 2 | waits | `execute as <owner> at @s run function cobblers_dg_probes:c1/chain` | `returned 1`; a battle opens within a second |
| 3 | wins | | the title "He gets up again."; about 3 s later the next battle opens on its own |
| 4 | wins stages 2, 3 and 4 the same way | | three follow-ups; after the fourth win "The chain is over." |
| 5 | | `scoreboard players get #won dpc1.r`, `#follow`, `#refused`, `#lost`, `#done`, `#gap_last` (each `... dpc1.r`) | 4, 3, 0, 0, 1, 60 |
| 6 | | `execute as <owner> run function cobblers_dg_probes:c1/leave`, `function cobblers_dg_probes:c1/cleanup` | |

If a follow-up does not start: `#refused` 1 means `start_battle` returned 0 (the player was still in a battle, or had no
Pokemon able); `#won` below the stage reached means the callback did not tag the win.

## Results

### RCON, no player (2026-10-08, main session)

Run 2026-10-08 22:46-22:58 by the main session over RCON, staging-2026-10-01 (staging only), pack `cobblers_dg_probes` from `tools/dungeon_probes.py` (installed by hand, plain restart, no /reload), no player online. Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, rctmod 0.19.0-beta / rctapi 0.16.1-beta, Mega Showdown 1.0.2, the server's full mod set (MobsBeGone 0.0.7 among it), Java 21, -Xmx16G.

| Step | Reading |
|---|---|
| 1 | boot log: **`Failed to load function cobblers_dg_probes:c1/spawn_plain`: "You need to include a valid NPC identifier. at position 83: ...obes:c1_s1<--[HERE]"**. A plain function naming a datapack NPC class fails to PARSE at load (the classes are not registered when functions parse). `c1/npc_at` and `c1/spawn_macro` loaded |
| 2 | `#ready` 1 |
| 3 | `c1/spawn_macro` returned 1 after a plain restart: **PASS** |
| 4 | the spawned NPC (`Rift Warden 1`) reads `NPCClass` "cobblers_dg_probes:c1_s1": **PASS** |
| 5 | `Unknown function cobblers_dg_probes:c1/spawn_plain` (consistent with step 1) |
| 6 | clear_tests returned 1 |

**Engine rule: every `spawnnpcat` naming one of our classes goes on a macro line.** The victory-hook chain (three fights,
60 ticks apart) needs the owner.

## Limitations
One player; two players chaining at once is XD8's. A forfeit or flee between stages sends no result (DM 1.4): the
chain stalls with the stage standing, as designed for a stand. The callback's run_command and the keeper's queued
command add up to a pass of latency; `#gap_last` measures from the keeper's sighting, not from the KO.

## Decision
Gates every stand (3.1) and the staged boss (3.2, F3). Part 1 FAIL: the engine spawns NPCs only from RCON-run steps
(a reapply-time spawn and a kept NPC per stand), never from the keeper, and the stand becomes a pre-placed NPC hidden
until the approach. Part 2 FAIL: the boss becomes one battle per entry with a staged party (DM 3.2 a, rejected for
order) or separate re-entries per stage; the owner is asked.

## Follow-up
XT1 times the chain.
