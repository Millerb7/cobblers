# EXP-073: R1, does `minecraft.mined` count in adventure mode with the rift pick under `can_break`?

**Status: RCON PART PASSED; owner part OPEN (2026-10-08).** Probe R1 of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
In co-op the seam's exact per-player count is the `minecraft.mined` stat, one objective per ore id (3.3). The run is
in adventure mode and the only tool that breaks anything is the rift pick (`minecraft:can_break` lists the seam's
ores). Whether the stat counts a block broken that way is ASSUMED. R1 settles it, against the world's own count of
what is gone.

## Success criteria
`dpr1.coal` and `dpr1.iron` equal the number of coal and iron ore blocks the owner broke, as counted from the world by
`r1/read`'s per-kind holders; `dpr1.stone` stays 0.

## Dependencies
Vanilla stats and adventure mode; the rift pick's component syntax (ASSUMED, the R2 class: if `r1/pick` fails to load,
the boot log names it and R2's RCON parse step says why).

## Implementation
`cobblers_dg_probes:r1/*`; objectives `dpr1.st`, `dpr1.r`, `dpr1.coal` (`minecraft.mined:minecraft.coal_ore`),
`dpr1.iron` (`...iron_ore`), `dpr1.stone` (`...stone`). Area x 2048..2303; pen at (2080, 96, -640). The face is two
courses (y 96 and 97) at z -635, x 2076..2084: coal, iron, coal, iron, coal, iron, stone, glass, dirt.
- `kit` (as the owner): adventure mode and the pick (`r1/pick`: an iron pickaxe with `custom_data {cobblers_dg:"pick"}`,
  `unbreakable`, `can_break {predicates:[{blocks:["minecraft:coal_ore","minecraft:iron_ore"]}]}`).
- `zero` (as the owner): the three counters to 0. `read`: counts what is gone, per kind, into `#gone_<id> dpr1.r`.
- `unkit`: survival, and the pick taken by its component (`r1/take_pick`).

## Test instructions
### (a) RCON, no player
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:r1/setup`; wait 15 s; `scoreboard players get #ready dpr1.st` | 1 | |
| 2 | `scoreboard objectives list` | lists `dpr1.coal`, `dpr1.iron`, `dpr1.stone` | missing: the stat criterion did not parse |
| 3 | `function cobblers_dg_probes:r1/read` | `returned 0`; nothing gone yet | |

Nothing else of R1 can be read without a player: the stat is a player's.

### (b) The owner in game
| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:r1/enter`, `execute as <owner> run function cobblers_dg_probes:r1/kit`, `execute as <owner> run function cobblers_dg_probes:r1/zero` | in the pen, adventure, holding the rift pick |
| 2 | with the rift pick, breaks 3 coal ore and 2 iron ore (any course) | `function cobblers_dg_probes:r1/read`, then `scoreboard players get #gone_coal_ore dpr1.r`, `... #gone_iron_ore dpr1.r` | 3 and 2 |
| 3 | | `scoreboard players get <owner> dpr1.coal`, `... dpr1.iron`, `... dpr1.stone` | 3, 2, 0: the stat counts in adventure under `can_break` |
| 4 | | `execute as <owner> run function cobblers_dg_probes:r1/unkit`, `execute as <owner> run function cobblers_dg_probes:r1/leave`, `function cobblers_dg_probes:r1/cleanup` | survival; no rift pick left (`clear` by component) |

FAIL: step 3 below step 2's counts. Then co-op credit cannot use the stat; DUNGEONS.md 3.3's marker count (exact in
solo, nearest member in co-op) is all there is.

## Results

### RCON, no player (2026-10-08, main session)

Run 2026-10-08 22:46-22:58 by the main session over RCON, staging-2026-10-01 (staging only), pack `cobblers_dg_probes` from `tools/dungeon_probes.py` (installed by hand, plain restart, no /reload), no player online. Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, rctmod 0.19.0-beta / rctapi 0.16.1-beta, Mega Showdown 1.0.2, the server's full mod set (MobsBeGone 0.0.7 among it), Java 21, -Xmx16G.

| Step | Reading |
|---|---|
| 1 | `#ready` 1 |
| 2 | `dpr1.coal`, `dpr1.iron`, `dpr1.stone` all exist (`scoreboard players get #x dpr1.coal`: "none is set", against "Unknown scoreboard objective" for a missing one): the `minecraft.mined:` criteria parse: **PASS** |
| 3 | `r1/read` returned 0 (nothing mined) |

Whether the stat counts in adventure mode is the owner's half.

## Limitations
One player; the stat is per player by construction, but a co-op split is XD8's. Silk touch and a wrong tool are not
tried (DM's R1 listed them; the rift pick is the only tool that breaks anything in adventure).

## Decision
Gates co-op seam credit (3.3, "the stat is added when co-op is enabled"). Fail: co-op credits the nearest member
(approximate, DM 2.1), and the owner is told.

## Follow-up
R2 (the pick breaks only the seam).
