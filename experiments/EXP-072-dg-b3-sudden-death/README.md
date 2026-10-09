# EXP-072: B3, sudden death: the clock holds at 0 mid-battle and the kill lands when `in_battle` reads 0

**Status: designed 2026-10-08, NOT_EXECUTED.** Probe B3 of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
DUNGEONS.md 2.5: a timeout during a battle holds the clock at 0 and kills the player the moment
`q.player.in_battle` reads 0, never mid-battle, "because what Cobblemon does with the battle and the NPC is unread".
B3 settles that the keeper can read `in_battle` through `runmolang` each pass, that it reads 1 while the battle runs,
and that the kill lands within a pass of the battle's end.

## Success criteria
- No player: the clock runs to 0 and holds; nobody is killed (`#killed` 0).
- The owner: the clock reaches 0 while he is in the battle; `#held` counts at least one pass at 0 in battle; he wins;
  within about a second he dies (`#killed` 1, `dpb3.d` 1); nothing happens mid-battle.

## Dependencies
Cobblemon 1.8.0 `spawnnpcat`, `runmolang` with `q.player.in_battle` (PlayerMoLangFunctions, jar),
`q.npc.start_battle` (the arena's start, PASS in game 2026-10-03); the blackout.

## Implementation
`cobblers_dg_probes:b3/*`; objectives `dpb3.st`, `dpb3.r`, `dpb3.d` (`deathCount`). Area x 1792..2047; pen at
(1824, 96, -640), box `x=1817,y=95,z=-647,dx=14,dy=3,dz=14`. Class `cobblers_dg_probes:b3_stand` (one `magikarp
level=5`: it only splashes, so the owner can hold the battle open as long as he likes).
- `proxy`: clock 1200 units (15 s at x1), no player.
- `fight` (as the owner): spawns the stand by macro at (1824.5, 96, -636.5), claims it, starts the clock; `go` 20 ticks
  later starts the battle.
- `keeper` (20 ticks): clock -= 80; at 0 holds and stamps `#zero_at`; then each pass `runmolang` on the owner:
  `in_battle == 0` queues `b3/out` (the kill), `== 1` adds to `#held`. `#killmode` 1 (default) kills with `kill @s`;
  `nokill` sets 0 and only says so.

## Test instructions
### (a) RCON, no player (arithmetic only)
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:b3/setup`; wait 15 s; `function cobblers_dg_probes:b3/proxy` | `returned 1` | |
| 2 | wait 20 s; `scoreboard players get #clk dpb3.st`, `... #zero_at dpb3.r`, `... #killed dpb3.r`, `... #absent dpb3.r` | 0; a gametime; 0; 1 or more | the clock went below 0, or `#killed` above 0 |

### (b) The owner in game
| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:b3/enter` | in the pen |
| 2 | waits | `execute as <owner> at @s run function cobblers_dg_probes:b3/fight` | `returned 1`; a battle opens within a second with Magikarp |
| 3 | does NOT win yet: picks moves that do not KO, or waits in the menu, until the actionbar says "The clock is at 0" (15 s) and five more seconds | `scoreboard players get #held dpb3.r` | 1 or more; he is alive and in the battle |
| 4 | wins | | battle ends normally (victory screen); then within about a second he dies; blackout once |
| 5 | | `scoreboard players get #killed dpb3.r`, `... #kill_at dpb3.r`, `... #zero_at dpb3.r`, `scoreboard players get <owner> dpb3.d`, `scoreboard players get #refused dpb3.r` | 1; `#kill_at` > `#zero_at`; 1; 0 |
| 6 | | `function cobblers_dg_probes:b3/cleanup` | |

FAIL: he dies while the battle screen is open (killed mid-battle), or never dies (`in_battle` never read 0), or
`#refused` is 1 (the start was refused; then nothing else counts). If he loses instead, the blackout takes him out and
`#left` counts; that run proves nothing about the kill.

## Results
NOT_EXECUTED.

## Limitations
- `runmolang`'s nested command is queued, not immediate (EXP-022), so the kill lands on the queue's next run, not in
  the keeper's own tick. The reading is "within a pass", not "the same tick".
- A flee or forfeit sends no result; whether `in_battle` reads 0 after one is LO1-adjacent and not run here.

## Decision
Gates sudden death (2.5, engine: timeout and sudden death). If `in_battle` cannot be read this way (step 3 `#held` 0
with the battle open), the engine falls back to the victory callback's flag plus a fixed delay, and the owner is told
that a timeout during a flee cannot be detected. If the kill lands mid-battle, the engine must not kill at all during a
battle and re-runs B3 with the callback route.

## Follow-up
None.
