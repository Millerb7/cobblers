# EXP-079: XT1, how long is an NPC fight at 2, 4 and 6 opposing members, caps 20, 45 and 100, and a 3-stage chain?

**Status: RCON PART PASSED; owner part OPEN (every timing) (2026-10-08).** Probe XT1 (new) of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
The clock (4.1) is computed from the spine's length and a fight budget that is *planning*. XT1 measures real fights as
a score, not a stopwatch: game ticks from the battle's start to the `battle_victory` callback, for nine NPC fights (2,
4 and 6 opposing Pokemon at caps 20, 45 and 100) and for a 3-stage chain at cap 45 (each stage and the whole, with
its 60-tick gaps).

## Success criteria
Twelve readings are recorded with the owner's party beside each: `#c20m2` .. `#c100m6`, `#k1`, `#k2`, `#k3` and `#chain`
in `dpxt1.tk` (ticks), each with `dpxt1.res` 1 (won) or -1 (lost). There is no PASS threshold: the numbers feed 4.1.

## Dependencies
As C1 (spawn, start, victory callback). Timing is `time query gametime` at `go` and in the callback's function: game
ticks, the unit the clock counts in; under lag they run slower than wall time, as the clock does.

## Implementation
`cobblers_dg_probes:xt1/*`; objectives `dpxt1.st`, `dpxt1.r`, `dpxt1.tk`, `dpxt1.res`. Area x 3584..3839; pen at
(3616, 96, -640); the stand (3616.5, 96, -636.5). Classes (`data/dungeon_probes.json` `xt1.teams`, timing fixtures
not balance; every species, move and item id read from the 1.8.0 jar): `xt1_c<cap>_m<n>` take the first n of the
cap's six (cap 20: pidgeotto 19, raticate, ivysaur, wartortle, charmeleon, pikachu 20; cap 45: arcanine, golem 44,
starmie, alakazam, gengar, gyarados; cap 100: tyranitar, garchomp, salamence, metagross, dragonite, gyarados, all
100), NPC skill 3 / 4 / 5 by cap. The chain: `xt1_k1..k3`, one Gengar at 43, 44, 45, each a different moveset and
held item (3.2's stage rule).
- `fight/<id>` (as the owner): spawns the class at the stand, starts it 20 ticks later (`#t0` stamped there).
- `chain` (as the owner): the three stages, C1's chain machinery with a 60-tick gap.
- The callback (`cobblers_dg_probes_xt1.molang`) runs `xt1/won` or `xt1/lost_cb` as the NPC: `#dt = gametime - #t0` is
  stored at once under the fight's name.

## Test instructions
### (a) RCON, no player
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | grep the boot log for `cobblers_dg_probes` | no `Failed to load`; no NPC class load error naming `xt1_` | a class failed: its line says why |
| 2 | `function cobblers_dg_probes:xt1/setup`; wait 15 s; `scoreboard players get #ready dpxt1.st` | 1 | |

Fight length needs a player; nothing else of XT1 runs without one.

### (b) The owner in game
For each cap he brings a party at that cap (staging: however he builds it), and plays as he would in a run: no
stalling, no fleeing. For each fight id in the order `c20m2 c20m4 c20m6 c45m2 c45m4 c45m6 c100m2 c100m4 c100m6`:

| # | The owner does | The session runs | Reading |
|---|---|---|---|
| 1 | (once) stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:xt1/enter` | in the pen |
| 2 | waits | `execute as <owner> at @s run function cobblers_dg_probes:xt1/fight/<id>` | `returned 1`; the battle opens |
| 3 | fights it out; heals between fights as he likes | after it: `scoreboard players get #<id> dpxt1.tk`, `scoreboard players get #<id> dpxt1.res` | ticks (divide by 20 for seconds at full TPS); 1 or -1. Record his party (species, levels) beside it |
| 4 | (after the nine) brings a cap-45 party | `execute as <owner> at @s run function cobblers_dg_probes:xt1/chain` | three battles back to back, 60 ticks apart |
| 5 | | `scoreboard players get #k1 dpxt1.tk`, `#k2`, `#k3`, `#chain` (each `... dpxt1.tk`), `scoreboard players get #chain dpxt1.res` | per-stage ticks; the whole chain including gaps; 1 |
| 6 | | `execute as <owner> run function cobblers_dg_probes:xt1/leave`, `function cobblers_dg_probes:xt1/cleanup` | |

A fight that will not start (`fight/<id>` returns 0) means a previous one is still armed: wait for its result, or
`function cobblers_dg_probes:xt1/cleanup` and setup again. `scoreboard players get #refused dpxt1.r` above 0 means a
start was refused.

## Results

### RCON, no player (2026-10-08, main session)

Run 2026-10-08 22:46-22:58 by the main session over RCON, staging-2026-10-01 (staging only), pack `cobblers_dg_probes` from `tools/dungeon_probes.py` (installed by hand, plain restart, no /reload), no player online. Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, rctmod 0.19.0-beta / rctapi 0.16.1-beta, Mega Showdown 1.0.2, the server's full mod set (MobsBeGone 0.0.7 among it), Java 21, -Xmx16G.

| Step | Reading |
|---|---|
| 1 | no `Failed to load` and no NPC class error naming `xt1_` in the boot log |
| 2 | `#ready` 1 |

No fight timed: XT1 is the owner's. Until it runs, every clock value is tunable data, not a decided number.

## Limitations
One owner, one party per cap, one run each: a sample of one per cell. A fight's length depends heavily on the party and
on how fast he picks moves. The cap-100 teams are strong fixed sets, not the game's.

## Decision
Feeds the clock (4.1), not a gate. If a cap-100 six-member fight runs far past the band's fight budget, the band's
stands drop to fewer members, or the clock grows, and the owner chooses.

## Follow-up
None.
