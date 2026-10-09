# EXP-070: B1, a per-member bossbar re-named every second from scores, a relog, and a clear

**Status: RCON PART PASSED; owner part OPEN (2026-10-08).** Probe B1 of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes` (`tools/dungeon_probes.py`, `data/dungeon_probes.json`), staging only.

## Objective
DUNGEONS.md 2.2 shows each member's clock as their own bossbar, `players` set to that member, `value` set every pass,
and the NAME rebuilt every pass with score components (`Rift 18:20 · x1.25 · ~14:40 left · taken 6`), relying on a
score inside the name being resolved when the command runs (DM 1.2). It also relies on the bar's `players` being a
stored list, so a bar left set shows again at reconnect, and an emptied and removed bar does not. B1 settles all three.

## Success criteria
- Each pass (20 ticks) the bar's name shows the clock's own mm:ss, the real time left and `taken 6`, all resolved
  against the executing entity (`@s`), and `value` equals the clock score.
- The owner sees the bar; after a relog it is back with no command; after `clear` and a relog it is gone.

## Dependencies
Vanilla `bossbar`, score text components; this pack installed, restarted.

## Implementation
`cobblers_dg_probes:b1/*`; objectives `dpb1.st`, `dpb1.r`, `dpb1.clk`, `dpb1.rate`, `dpb1.tk`, and `dpb1.m`, `dpb1.s10`,
`dpb1.s1`, `dpb1.rm`, `dpb1.rs10`, `dpb1.rs1` (the digits). Bar `cobblers_dg_probes:b1_m1`, max 4800 (one minute in
quarter-ticks, 2.1). Area x 1280..1535; pen at (1312, 96, -640).
- `proxy`: a marker is the member (`dpb1.mk`), clock 4800, rate 5 (x1.25), taken 6; the keeper starts.
- `join` (as the owner): the owner is the member and the bar's only player.
- `keeper` every 20 ticks runs `pass` as the member: clock -= 20 x rate; mm:ss of `clk / 80` and of `clk / (20 x rate)`;
  `bossbar set ... name [...{"score":{"name":"@s",...}}...]`; `execute store result bossbar ... value`; colour by rate.
- `clear`: players emptied, bar removed.

## Test instructions
Install as EXP-069 (copy the pack into the staging world's `datapacks/`, plain restart).

### (a) RCON, no player
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:b1/setup` | `returned 1` | |
| 2 | wait 15 s; `function cobblers_dg_probes:b1/proxy` | `returned 1` | `returned 0`: not ready |
| 3 | wait about 3 s; `bossbar list` | `[Rift 0:5x · x1.25 · ~0:4y left · taken 6]`: after n passes the clock is 4800 - 100n, so 0:58 / ~0:47 after one, 0:57 / ~0:46 after two | the name shows `Rift` only, empty scores, or `taken` with no number: the score did not resolve against `@s` |
| 4 | `bossbar get cobblers_dg_probes:b1_m1 value` twice, 2 s apart | the second is 200 lower (two passes x 100) | unchanged |
| 5 | `scoreboard players get @e[type=minecraft:marker,tag=dpb1.mk,limit=1] dpb1.clk` | equals step 4's value | differs |
| 6 | `bossbar get cobblers_dg_probes:b1_m1 players` | `... has no players currently online` | |

### (b) The owner in game
| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:b1/enter`, then `execute as <owner> run function cobblers_dg_probes:b1/join` | `returned 1` twice |
| 2 | reads the bar at the top of the screen for 10 s | `bossbar get cobblers_dg_probes:b1_m1 players` | `has 1 players currently online: <owner>`; the time falls a second a second, `~` time faster (x1.25), yellow bar |
| 3 | logs out, waits 10 s, logs in | `bossbar get cobblers_dg_probes:b1_m1 players` while out, then after | while out `has no players currently online`; on return the bar is back with no command, showing the time it had at the logout (this keeper runs `@a[tag=dpb1.m]`, which finds no offline player, so the clock holds while he is away) |
| 4 | | `function cobblers_dg_probes:b1/clear`, then `bossbar list` | `There are no custom bossbars active` |
| 5 | logs out and in | | no bar |
| 6 | | `execute as <owner> run function cobblers_dg_probes:b1/leave`, `function cobblers_dg_probes:b1/cleanup` | home |

Step 3's clock note: this probe's keeper charges only a present member, as DUNGEONS.md 2.6 does; the absence charge is
LO1's.

## Results

### RCON, no player (2026-10-08, main session)

Run 2026-10-08 22:46-22:58 by the main session over RCON, staging-2026-10-01 (staging only), pack `cobblers_dg_probes` from `tools/dungeon_probes.py` (installed by hand, plain restart, no /reload), no player online. Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, rctmod 0.19.0-beta / rctapi 0.16.1-beta, Mega Showdown 1.0.2, the server's full mod set (MobsBeGone 0.0.7 among it), Java 21, -Xmx16G.

| Step | Reading |
|---|---|
| 1-2 | setup and proxy returned 1 |
| 3 | `bossbar list`: `[Rift 0:56 · x1.25 · ~0:45 left · taken 6]`: the scores resolved against the marker as `@s`: **PASS** |
| 4 | value 4500, then 4300 two seconds later (two passes x 100): **PASS** |
| 5 | the marker's `dpb1.clk` 4300 = the bar's value: **PASS** |
| 6 | `has no players currently online` |

Per-player visibility, logout/login and the clear need the owner.

## Limitations
- One bar, one member. Per-member bars for several members, and other packs' actionbar use, are not tested.
- The multiplier label in the name is fixed text (`x1.25`); a per-rate label is a branch per rate, not a mechanism.
- Readings of the name over RCON come from `bossbar list`, which prints the stored (already resolved) name.

## Decision
Gates the display (2.2, engine: the clock and the bar). If the score does not resolve against `@s`, the engine renders
the name from a per-member storage string by a macro (one macro call per member per pass) and B1 is re-run on that. If
the bar does not come back after a relog, the engine re-sets `players` on the first pass that finds a returning member
(2.6 already finds them). If `clear` leaves a bar at relog, the engine's every-exit path removes the bar, not only
empties it.

## Follow-up
None.
