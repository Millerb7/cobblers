# EXP-080: V1, is a rip seen from 32, 64 and 128 blocks; `force` mode; a plume?

**Status: designed 2026-10-08, NOT_EXECUTED.** Probe V1 (new) of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
A rip (7.1) is a frame, `block_display` torn edges, a dark opening, an interaction entity, and keeper particles
(`reverse_portal` drawn inward and `portal`) re-emitted every 10 ticks while a player is within 48 blocks. Particles
render only near the viewer by default and `force`'s reach is ASSUMED. V1 settles what is seen from 32, 64 and 128.

**A conflict in the design, found while building this:** emitting only while a player is within 48 blocks means a
player at 64 or 128 is sent no particles at all, whatever the mode. Mode 3 below is the design as written, so the
reading shows it; a rip meant to be seen from the approach needs the emission gate at least as far as the distance it
must be seen from, or a non-particle plume.

## Success criteria
A table, per distance (32, 64, 128) and per mode (0 normal, 1 force, 2 force + plume, 3 the design's 48-block gate):
particles seen / not seen, displays seen / not seen, frame seen / not seen. Over RCON, the server half: whether a
`normal` particle is sent to a player at that distance at all.

## Dependencies
Vanilla particles, `block_display` (`view_range`), interaction entities.

## Implementation
`cobblers_dg_probes:v1/*`; objectives `dpv1.st`, `dpv1.r`. Area x 3840..4095. The rip's plane at x 3856: an obsidian
frame (z -642..-638, y 96..102; the Rift palette is world-content-dev's) with a black-concrete opening; a railed
walkway east along z -644..-636 to x 3992, coloured marks across it at x 3888 (32, lime), 3920 (64, yellow), 3984 (128,
red).
- `dress`: six block displays at the opening's edges (purple glass and crying obsidian slivers, `view_range` 3.0,
  full brightness) and an interaction filling the opening. Returns the display count.
- `mode0`..`mode3` arm the emitter (every 10 ticks) at the opening's centre (3857.0, 99, -639.5); mode 2 adds a plume
  (`campfire_signal_smoke` at y 103 and an `end_rod` column to y 110 and above, force); `off` stops it.
- `at32`, `at64`, `at128` (as the owner): onto a mark, facing the rip.

## Test instructions
### (a) RCON, no player
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:v1/setup`; wait 15 s; `function cobblers_dg_probes:v1/dress` | `returned 6` | fewer: a display's NBT did not parse |
| 2 | `execute in cobblers:pocket run particle minecraft:portal 3857.0 99 -639.5 0 0 0 0 1 normal` | `The particle was not visible for anybody` (no player: the command's own failure, proves the reading works) | |

### (b) The owner in game (his usual video settings; record render distance and the particle setting)
| # | The owner does | The session runs | Reading |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:v1/enter` | on the 32 mark, facing the rip |
| 2 | looks at the rip | `function cobblers_dg_probes:v1/mode0` | seen / not seen: particles, displays, frame |
| 3 | | `execute in cobblers:pocket run particle minecraft:portal 3857.0 99 -639.5 0 0 0 0 1 normal`, then the same with `force` | server half: "Displaying particle" or "not visible for anybody", for each |
| 4 | repeats 2-3 with `mode1`, `mode2`, `mode3` | `function cobblers_dg_probes:v1/mode1` etc. | the same list |
| 5 | moves to 64 | `execute as <owner> run function cobblers_dg_probes:v1/at64` | repeat steps 2-4 |
| 6 | moves to 128 | `execute as <owner> run function cobblers_dg_probes:v1/at128` | repeat steps 2-4 |
| 7 | | `function cobblers_dg_probes:v1/off`, `execute as <owner> run function cobblers_dg_probes:v1/leave`, `function cobblers_dg_probes:v1/cleanup` | |

## Results
NOT_EXECUTED.

## Limitations
One client's settings decide the client half; a player with particles on "minimal" sees fewer. The pocket is lit at
noon (`fixed_time` 6000) and empty; a rip in the overworld at dusk against terrain will read differently.

## Decision
Gates the rip's legibility (7.1). The engine's emission gate is set to the farthest distance at which the chosen mode
was seen (not 48 if that is beyond 48), and the plume is built if no particle mode reads at the approach's distance.
If displays at `view_range` 3.0 are not seen at 128, the rip's far cue is the plume alone.

## Follow-up
The rip's palette and approach distance per dungeon are world-content-dev's.
