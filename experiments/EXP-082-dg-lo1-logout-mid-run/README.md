# EXP-082: LO1, logging out mid-run: the absence charge, the slot deadline, the dead-run check, a server stop

**Status: RCON PART PASSED; owner part OPEN (2026-10-08).** Probe LO1 (new) of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
DUNGEONS.md 2.6: a run goes on without a player who leaves, and their clock keeps falling at their rate. The keeper
cannot change an offline player's score, so it charges the absence on return from an uptime counter: `gap = #up -
seen - 20`, and `gap x rate` comes off the clock before anything else. The slot holds the member's deadline
`#up + clock / rate` and is freed when `#up` passes it with the member away. A player back to a dead run is killed on
their first pass. Uptime does not advance while the server is stopped, ASSUMED vanilla. LO1 runs that mechanism as
written, and also reads what Cobblemon does with a battle and its NPC across a logout.

## Success criteria
- Short absence: on return `#post = #pre - #charged`, `#charged = #gap x 4`, `#gap` close to the seconds away x 20;
  `#dead` 0.
- Long absence (longer than the clock left): `#freed` 1 with `#freed_at` within a pass after `#dl`; on return `#dead`
  1, the title "The rift closed without you", and the kill if `killmode` is on.
- Server stop: the time the server was down is not charged (`#gap` counts only server-up ticks while away); the
  keeper resumes after the restart (`#up` rises) or, if not, `lo1/resume` restarts it (a finding either way).
- Battle logout: the battle state and the NPC before and after are recorded.

## Dependencies
Vanilla scoreboard and `schedule`; Cobblemon `runmolang` with `q.player.in_battle` and `q.npc.in_battle`
(NPCMoLangFunctions, jar).

## Implementation
`cobblers_dg_probes:lo1/*`; objectives `dplo1.st` (`#up`, `#own`, `#dl`, `#arm`, `#killmode`), `dplo1.r` (the
readings), `dplo1.clk`, `dplo1.seen`, `dplo1.rate`. Area x 4096..4351; pen at (4128, 96, -640). One slot, one member.
- `join` (as the owner): clock 9,600 units (2 minutes at x1, rate 4), `seen = #up`, slot owned, keeper armed.
- `keeper` (20 ticks): `#up += 20`; `member` for the owner if he stands in the pen; `free` when the slot is owned, he
  is offline or away, and `#up > #dl`.
- `member`: the gap and `charge` first; then the dead-run check (`#own` 0 or clock at or below 0: `dead`); then the
  pass (clock -= 20 x rate, `seen`, `#dl`), and `timeout` at 0.
- `killmode` turns the kill on (default off: the title and `#dead` are the reading). `resume`. `battle` (as the owner):
  a stand NPC (`lo1_npc`, one Magikarp 5) and the battle started.

## Test instructions
### (a) RCON, no player
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:lo1/setup`; wait 15 s; `scoreboard players get #ready dplo1.st` | 1 | |

Everything else needs a player who logs out; RCON reads each value by name while he is away.

### (b) The owner in game
**Leg A, a short absence.**
| # | The owner does | The session runs | Reading |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:lo1/enter`, `execute as <owner> run function cobblers_dg_probes:lo1/join` | `returned 1` |
| 2 | stays 10 s, logs out | at once: `scoreboard players get <owner> dplo1.clk`, `scoreboard players get #up dplo1.st`; note the wall time | about 8,800; U1 |
| 3 | stays out 30 s, logs back in (he appears in the pen) | 3 s later: `scoreboard players get #gap dplo1.r`, `#pre`, `#charged`, `#post`, `#dead` (each `... dplo1.r`) | `#gap` about 600 (30 s); `#charged` = 4 x `#gap`; `#post` = `#pre` - `#charged`; `#dead` 0; "The rift did not wait." on the actionbar |

**Leg B, a long absence.**
| # | The owner does | The session runs | Reading |
|---|---|---|---|
| 4 | | `execute as <owner> run function cobblers_dg_probes:lo1/join` (a fresh 2-minute run) | |
| 5 | logs out at once | `scoreboard players get #dl dplo1.st`, `scoreboard players get #up dplo1.st` | the deadline, about `#up` + 2,400 |
| 6 | stays out 2.5 minutes | at 2 minutes and 10 s: `scoreboard players get #freed dplo1.r`, `#freed_at` (`... dplo1.r`), `scoreboard players get #own dplo1.st` | 1; `#freed_at` between `#dl` + 1 and `#dl` + 20; 0 |
| 7 | logs back in | `scoreboard players get #dead dplo1.r`, `#dead_at` | 1; `#dead_at` is the first pass after his return; the title "The rift closed without you" |
| 8 | (optional, costs the blackout's money) | `function cobblers_dg_probes:lo1/killmode`, then repeat 4-7 | he dies on his first pass back, once |

**Leg C, a server stop.**
| # | The owner does | The session runs | Reading |
|---|---|---|---|
| 9 | | `execute as <owner> run function cobblers_dg_probes:lo1/join` | |
| 10 | logs out after 10 s | `scoreboard players get #up dplo1.st` (U1), wall time | |
| 11 | | stops the staging server, waits 60 s, starts it (detached, the process checked) | |
| 12 | | `scoreboard players get #up dplo1.st` twice, 5 s apart | rising: the schedule survived the restart. Unchanged: it did not; run `function cobblers_dg_probes:lo1/resume` and record that |
| 13 | logs in within 20 s of the server being up | `scoreboard players get #gap dplo1.r` | about (server-up seconds while he was away) x 20: the 60 s stop is NOT in it |

**Leg D, a battle logout.**
| # | The owner does | The session runs | Reading |
|---|---|---|---|
| 14 | | `execute as <owner> at @s run function cobblers_dg_probes:lo1/battle` | a battle opens |
| 15 | mid-battle, logs out | `runmolang "return q.npc.in_battle;" @e[type=cobblemon:npc,tag=dplo1.npc,limit=1]` | record 1 or 0 (does the NPC still think it is battling?) |
| 16 | stays out 30 s, logs in | `runmolang "return q.player.in_battle;" <owner>`, `execute in cobblers:pocket if entity @e[type=cobblemon:npc,tag=dplo1.npc]`, step 15's read | record: the battle ended or resumed; the NPC stands or not. He also says what he sees |
| 17 | | `execute as <owner> run function cobblers_dg_probes:lo1/leave`, `function cobblers_dg_probes:lo1/cleanup` | |

## Results

### RCON, no player (2026-10-08, main session)

Run 2026-10-08 22:46-22:58 by the main session over RCON, staging-2026-10-01 (staging only), pack `cobblers_dg_probes` from `tools/dungeon_probes.py` (installed by hand, plain restart, no /reload), no player online. Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, rctmod 0.19.0-beta / rctapi 0.16.1-beta, Mega Showdown 1.0.2, the server's full mod set (MobsBeGone 0.0.7 among it), Java 21, -Xmx16G.

| Step | Reading |
|---|---|
| 1 | `#ready` 1 |

Everything else needs the owner to log out.

## Limitations
One member, one slot; the co-op deadline (the latest of several members) is XD8's. The engine's eject and escrow are
not built here. `#up` counts the keeper's passes, so a lagging server charges by passes, not wall seconds; the gap is
in the same unit as the clock.

## Decision
Gates the logout rule (2.6, engine: the absence gap, the slot deadline and the dead-run check, run first). Leg A or B
FAIL is an arithmetic defect to fix before the engine copies it. Leg C: if the schedule does not survive a restart, the
engine re-schedules its keeper from a load function (Entei's pattern, `tools/entei_boss.py` load). Leg D decides 3.1's
forfeit case: if the NPC is left "in battle", the engine kills and re-spawns a stand's NPC on the player's return.

## Follow-up
DX1 (death and claims inside a run) after E1.
