# EXP-076: L1, are a glowing sleeper, lanterns, a bubble column and a beacon readable from a gantry 40 above the bed?

**Status: RCON PART: 3 PASS, 1 FAIL (the glow); owner part OPEN (2026-10-08).** Probe L1 of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
The legendary lake must be OBVIOUS from the gantry (3.7): a legendary dressed sleeping and `glowing` on the bed of a
40-deep shaft, lanterns on the bed, a bubble column rising from it, keeper particles above the water. All vanilla, all
ASSUMED to read through 40 blocks of water. L1 builds the shaft and the owner reports what he sees.

## Success criteria
From the gantry, without moving off it, the owner sees: the sleeper's glow outline; at least one lantern; the bubble
column's stream at the surface and below; the beacon's beam; the steam particles. Each is reported seen / not seen.

## Dependencies
Vanilla glowing, lanterns (waterlogged), soul sand bubble columns, beacons; Cobblemon `spawnpokemonat`; the dormant
dressing proven by EXP-023/046 (`tools/legendaries.py` DORMANT).

## Implementation
`cobblers_dg_probes:l1/*`; objectives `dpl1.st`, `dpl1.r`. Area x 2816..3071. The shaft: 7 x 7 water, x 2845..2851,
z -643..-637, bed blocks at y 95, water y 96..135 (40 deep), stone-brick walls, a glass rail on the rim (a fall into
40 of water is the water ladder's harsh rule, not a swim). The gantry: planks at y 135, z -650..-645, railed; arrival
(2848.5, 136, -647.5). On the bed: a beacon on a 3 x 3 iron pyramid at (2850, 96, -638); waterlogged lanterns at
(2845, 96, -643), (2851, 96, -643), (2845, 96, -637); soul sand at (2846, 95, -638) under the water.
- `sleeper`: `lapras level=50 uncatchable` (a stand-in: no legendary is spawned on staging) by macro at
  (2847.5, 96, -640.5), dressed DORMANT and given `glowing` (infinite).
- `steam_on` / `steam_off`: `minecraft:cloud` particles (force) over the surface every 10 ticks.

## Test instructions
### (a) RCON, no player
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:l1/setup`; wait 15 s; `function cobblers_dg_probes:l1/sleeper` | `returned 1` | 0 |
| 2 | `execute in cobblers:pocket if block 2846 120 -638 minecraft:bubble_column` | `Test passed` (the column reached mid-shaft) | `Test failed`: it did not form from a setblock under existing water |
| 3 | `execute in cobblers:pocket if block 2850 96 -638 minecraft:beacon`; `execute in cobblers:pocket run data get block 2850 96 -638` | passed; record the block entity (a levels value of 1 or more, if the field is present, means the pyramid counts; the field name is ASSUMED) | |
| 4 | `data get entity @e[tag=dpl1.sl,limit=1] PoseType`; `data get entity @e[tag=dpl1.sl,limit=1] active_effects` | `"SLEEP"`; glowing listed | |
| 5 | `function cobblers_dg_probes:l1/steam_on` | `returned 1` | |

### (b) The owner in game (video settings as he plays)
| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:l1/enter` | on the gantry |
| 2 | looks down into the shaft from the gantry, then from the rim rail | | reports, each seen / not seen: glow outline; lanterns; bubble stream; beacon beam; steam |
| 3 | walks to the far end of the gantry (about 8 from the rim) and looks again | | same list |
| 4 | | `function cobblers_dg_probes:l1/steam_off`; `execute as <owner> run function cobblers_dg_probes:l1/leave`; `function cobblers_dg_probes:l1/cleanup` | |

Do NOT jump into the shaft: without a Dive partner the water ladder's deep rule applies at 5 down.

## Results

### RCON, no player (2026-10-08, main session)

Run 2026-10-08 22:46-22:58 by the main session over RCON, staging-2026-10-01 (staging only), pack `cobblers_dg_probes` from `tools/dungeon_probes.py` (installed by hand, plain restart, no /reload), no player online. Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, rctmod 0.19.0-beta / rctapi 0.16.1-beta, Mega Showdown 1.0.2, the server's full mod set (MobsBeGone 0.0.7 among it), Java 21, -Xmx16G.

| Step | Reading |
|---|---|
| 1 | `l1/sleeper` returned 1 |
| 2 | a bubble column at (2846, 120, -638), mid-shaft: **PASS** (it forms from a setblock under standing water) |
| 3 | the beacon block entity reads `Levels: 1`: the pyramid counts: **PASS** |
| 4 | the Lapras's `PoseType` "SLEEP": **PASS**; `active_effects` EMPTY: **the glow did NOT apply: FAIL as built** |
| 5 | `steam_on` returned 1 |

The glow: `effect give @s minecraft:glowing infinite 0 true` in the same function as the macro spawn missed the new
Pokemon. Given afterwards over RCON (`effect give @e[tag=dpl1.sl,limit=1] ...`) it applied and held (`duration: -1`
three seconds later). **Engine rule: apply effects to a macro-spawned Pokemon a tick after the spawn**, not in the same
function. Whether all four read as obvious from the gantry is the owner's half.

## Limitations
Visual and one client's settings (render distance, particles, shaders). The membrane and the real species are not
built. Daytime only (the pocket's `fixed_time` 6000).

## Decision
Gates "obvious" (3.7). Each cue that is not seen is dropped from the design or replaced: the glow by a light column of
`end_rod` particles, the beam by a taller lantern stack, the bubbles by particles. If none reads through the water,
the lake's legendary is shown in a dry, lit chamber visible through glass (the L2 fallback) and the owner is asked.

## Follow-up
L2 (a battle under water).
