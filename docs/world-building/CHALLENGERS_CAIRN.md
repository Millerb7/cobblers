# The Challengers' Cairn

A place to find on the south strand (cell F4, sub-region `south_strand`, region `southern_coast`, paint `coast_scrub`):
a field-stone cairn on a flat rise beside the foot of Victory Road, a ring of marker stones round it, and under it a
stone-lined cist reached by a stair cut down from the south. A sign at the stair head gives the road's custom, "add a
stone and go on"; the cist holds what earlier challengers left for the next.

- Record: `data/challengers_cairn.json` (hand-authored; every Y derived from the heightmap)
- Generator: `tools/challengers_cairn.py` -> `build/datapacks/cobblers_challengers_cairn` (`--report` writes nothing),
  on the shared pieces in `tools/wayside_kit.py`
- Re-apply: **R9CN** (a block pass before R9E: hold, build, release)
- Shared record: the cache `challengers_cairn_cist` (`data/rewards.json`): 2 Revives, 3 Super Potions
- Independent audit: **owed** (below). Tests: none of its own yet.

Status: generated 2026-10-03. **Not audited, not applied to any world, not seen in game.**

## Why here

The owner, 2026-10-03: "the southern map, still the thinnest part of the world." Measured that day on a grid every 32
blocks over rows E-H, land only, within 160 blocks of a walked path in `data/route_paths.json`, the Rift's polygon left
out, against every x/z point a `data/*.json` record carries (abstract records such as rift zones, spawn tables and
regions left out; the method of `tools/poi_heatmap.py`). The three emptiest:

| Point | Nearest authored thing | Off which path | Region / paint |
| --- | --- | --- | --- |
| (3504, 6064) | 354 blocks | Victory Road, 139 | south_strand / coast_scrub |
| (4496, 5904) | 296 blocks | Route 8, 139 | plateau_west / badlands_top |
| (4784, 5328) | 240 blocks | Route 8, 151 | plateau_west / badlands_top |
| (3728, 5488) | 234 blocks | Victory Road, 147 | rift_foot / savanna |

The first is this place. The fourth was taken over the third (6 blocks less empty) for the Surveyors' Benchmark,
because the third shares the Dry Cistern's sub-region and stands further off its road, and Victory Road from (3606,
5755) to (3609, 5629) is the only stretch of any southern route with nothing authored within 300 blocks.

The site is a dead-flat terrace, ground y109 over 50 by 50 blocks round (3556, 6112), the highest ground on this
stretch. Victory Road leaves Giovanni's town 370 blocks south and passes 75 blocks east: this is the first rise a
challenger walks by after the eighth badge, where a road's custom of adding a stone would start. Measured by the
report: the capstone lantern (3556, 118, 6112) is in sight of a standing eye from 119 of Victory Road's walked points
(every 4th within 250 blocks).

## What is built

Cairn crown y116, chiselled capstone y117, lantern y118. Cist floor y102, a 5 by 5 room 3 high (y103-105), at least 4
blocks of ground under the cairn over it; a 7-step stair (3 roofed with 2 or more blocks over them, 4 an open trench
between stone-brick walls) with a stone-brick face over the mouth. Seven marker stones at 9 blocks (the south one is
left out for the stair). 1,047 blocks written, x3547-3565 z6103-6123 y101-118.

## What an audit must check

Another agent writes it; it must not import `tools/challengers_cairn.py` or `tools/wayside_kit.py` geometry.

1. Every written block is in `blocks.ids`, and none is a spawn condition in `data/spawn_blocks.json` that no
   `data/spawn_block_policy.json` entry scoped to `challengers_cairn` allows; no chest, no bed.
2. The cist: floor = min ground over the 5 by 5 footprint minus 7, from `tools/ground.py` itself; every cist void has
   at least 4 blocks of ground over it, every roofed stair void at least 2; every void is air in the replayed function.
3. The stair is walkable: each step one block above the last, every step a stair facing south, at least 3 air above
   every step, and the last step level with the ground (no one-block jump at the top).
4. The shell: every non-void block within 2 (Chebyshev) of a void and below the column's top block is solid.
5. The cairn stands on each column's own ground (no floating block, no gap under it).
6. The barrel stands at `data/rewards.json` `challengers_cairn_cist` `container.at`, and the trigger box is air a
   player can stand in, touching the barrel.
7. Every lantern and sign hangs on a solid block written before it (top-down order for what hangs).
8. Every write is inside the force-loaded box of the function and of R9CN, and inside `bbox.writes`.
9. Independently re-measure: the lantern's sightline from Victory Road, and that nothing in `data/placements.json`,
   `data/towns.json`, `data/habitat_blocks.json` or another build's bbox overlaps the write box.
10. A mutation of the GENERATOR (a thinner shell, a step two high, a missing barrel) is caught.
