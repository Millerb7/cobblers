# The cave systems (western half)

Status: **built and audited offline on 2026-10-22; nothing is applied to any world.** Every number below is from
`python tools/cave_systems.py build` and `python tools/cave_systems_audit.py` run in a worktree against the canonical heightmap and
`data/`; nothing here has been seen in game.

The owner's brief (2026-10-21): "with no caves people wont be incentivized to mine at all ... i need some to be thousands long ... a few
hunderd block caves wont be enoughfor 10 people ... its looking more like 6 now". The pre-exported world has essentially no natural caves
and the cave kits are a hundred blocks each. These are three networks of a few thousand blocks of passage each, all at x < 4000.

| | | | |
|---|---|---|---|
| system | id | centre, radius | centreline |
| The Old Seams | `old_seams` | (2100, 5000), 520 | 3,733 blocks |
| The Hollow Reach | `hollow_reach` | (2300, 3300), 540 | 4,616 blocks |
| The Frostpeak Deeps | `frostpeak_deeps` | (904, 616), 520 | 3,931 blocks |

Pictures (top-down, one block a pixel; passages coloured by their shallowest floor, red tint = kept clear, ring = mouth, C = cavern):

- `cave_systems/west_map.png`: the whole western half, the three systems, the towns and the x 4032 line
- `cave_systems/old_seams.png`, `cave_systems/hollow_reach.png`, `cave_systems/frostpeak_deeps.png`

Regenerate them with `python tools/cave_systems.py map`.

## Mouths (surface entrances), each 82 to 115 blocks from the thing it is near

- Old Seams: `seams_oak_n` (1914, 5142) and `seams_oak_s` (1806, 5302) by the Great Oak; `seams_mansion` (1650, 4950) by the Route 1 mansion
- Hollow Reach: `reach_tea_n` (2486, 3410), `reach_tea_e` (2678, 3394), `reach_tea_s` (2446, 3610) by Tea Town; `reach_brock` (1930, 3490) by Brock's town;
  `reach_r2` (1878, 3202) and `reach_r2n` (1894, 3010) by route 2
- Frostpeak Deeps: `peak_e` (806, 478), `peak_s` (610, 518), `peak_n` (766, 246), `peak_w` (542, 334), all by the Frostpeak shrine

A mouth is a ramp cut down into the hill (no frame, no cut stone), four lanterns inside it, and nothing else lit anywhere.

## What each system holds

Three to seven caverns (34 to 80 across, 14 to 39 tall) joined by passages 3 to 7 wide, four levels (upper y66, middle y30, deep y-8,
abyss y-30, each drifting a few blocks) joined by slopes of at most 0.5, dead ends, loops, and ore in exposed wall cells: coal, iron, copper,
lapis, gold, redstone and diamond, deepslate variants under y0. Ore is richer deeper under the surface and farther from a town (audit:
density per 1,000 wall cells 15 to 22 within 45 blocks of the surface against 37 to 44 beyond 90). About 3,400 to 4,600 ore blocks a system.

## The rules and how each is checked

| Rule | Where it is held | Where it is checked |
|---|---|---|
| >= 8 blocks of rock over every carved cell, except within 46 of a mouth | the plan keeps 11 and clips cells that fail | the audit, from the pack's `fill ... air` lines and `tools/ground.py` (min cover outside mouths: 15 to 17) |
| nothing within 12 of water (sea, lake basins, river courses) | the blocked grid, +4 slack | the audit, from the heightmap, `data/landmarks.json` through `tools/water_mask.py`, and `data/rivers.json` |
| nothing within 32 of anything authored | every x/z, footprint, command box, route and the Rift in `data/**/*.json`, +4 slack, three exclusion discs | the audit, from `tools/southern_residents.py authored_points` and its own walker |
| every WRITE at x <= 4032 | carve stops at x 4000; the shell reaches at most 5 past | the audit, from the pack's commands |
| water and lava two cells round every carved cell become stone, and the passage is carved again | per-tile functions: shell first everywhere, then carve, shell, carve, dress | the audit replays the writes in order with last-write times |
| server limits | every fill <= 32,768, every function <= 65,536 commands, every tile <= 144 chunks held | `tools/function_limits.py check_lines` in the build and the audit |

The audit does not import the generator. `tests/test_cave_systems.py` mutates the GENERATOR (the ground it believes in, water and
authored clearance ignored, a shell one cell thin, no second carve, carves run before shells) and requires the audit to report each.

## Size

Total 838,400 blocks carved over 137 functions and 63,054 command lines, longest single run 7,948 commands. Longest walk from a mouth:
1,542 to 2,208 steps; floor columns reachable on foot 20,790 to 36,519; every mouth reaches every other.

## Apply (not tonight)

`reapply.py prepare` builds and audits the pack (jobs `cave_systems:build`, `cave_systems_audit`); step `R9CS` then holds each 192-block tile,
runs it and releases it, every shell tile first and every carve tile after. The pack is blocks only: `strip` takes it out of the heap after the run.

## Not covered

Only `data/` is kept clear of: another pack's writes, `build/paint`'s trees and water raster, `derived/routes`' legs and the pending
water export do not exist in a fresh checkout and were not read. A tarn or pond that is built by another tool and is in no landmark basin
is covered only by that tool's own x/z points. Trees over a mouth are not cleared. Sand and gravel above a passage can fall. Dark
passages will spawn what the dark spawns, and the ore blocks are Pokemon spawn conditions (`data/spawn_block_policy.json`, new entry
scoped `cave_systems`, decided by the implementing session and on the review list). Behaviour in game is not verified.

## For the owner to decide

- the Displaced City's footprint in `data/towns.json` (2904..3035, 1645..1776) and its centre in `data/placements.json` (3366, 1755) disagree by about 400
  blocks; both are kept clear (`rules.exclusion_discs`)
- whether the ore should draw Pokemon here at all (the policy entry), and whether the Frostpeak system, whose mouths are 85 blocks from the shrine, is wanted
  that early in the route
