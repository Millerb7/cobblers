# The Surveyors' Benchmark

A place to find in the Rift Foot (cell F4, sub-region `rift_foot`, region `southern_coast`, paint `savanna`), on a low
rise beside Victory Road between Giovanni's town and the Rift entry: a stone-brick trig pillar with a lantern on its
cap ("BM 1, do not move"), the survey party's acacia hut with its barrel, cartography table and empty lectern, and a
line of lit sighting stakes pointing at the Rift entry. The Rift's surveyor already stands at that entry
(`data/npc_seats.json` `npc_main_rift_surveyor`); this is where his people took the Rift's levels from.

- Record: `data/survey_benchmark.json` (hand-authored; every Y derived from the heightmap)
- Generator: `tools/survey_benchmark.py` -> `build/datapacks/cobblers_survey_benchmark` (`--report` writes nothing),
  on `tools/wayside_kit.py`
- Re-apply: **R9BM** (a block pass before R9E: hold, build, release)
- Shared record: the cache `survey_benchmark_store` (`data/rewards.json`): an Everstone, 2 Sitrus Berries
- Independent audit: **owed** (below). Tests: none of its own yet.

Status: generated 2026-10-03. **Not audited, not applied to any world, not seen in game.**

## Why here

Measured 2026-10-03 (the table in `CHALLENGERS_CAIRN.md`): Victory Road from (3606, 5755) to (3609, 5629) is the
only stretch of any southern route with nothing authored within 300 blocks of any of its points, and (3728, 5488) is
234 blocks from the nearest authored thing. (4784, 5328) measured 6 blocks emptier but shares the Dry Cistern's
sub-region 650 blocks away and stands 151 off Route 8; this one is beside the road. The site, (3708, 5716), is the
last high ground (y113-115) before the road drops toward the Rift entry, which is where a survey would set a
benchmark.

Measured by the report: the pillar's lantern (3708, 121, 5716) is in sight of a standing eye from 98 of Victory
Road's walked points (every 4th within 250 blocks); the write box is 86 blocks from the nearest.

## What is built

Plinth y115 (3 by 3, cobblestone foundation), pillar to y119, chiselled cap y120, lantern y121. Hut x3712-3718
z5714-5718, floor y116, walls 4 high, slab roof y121, door in the west wall at z5716 with a two-step acacia ramp.
Stakes (lantern blocks) at (3703, 117, 5705), (3699, 116, 5694), (3694, 116, 5683). 270 blocks written, x3694-3719
z5683-5719 y114-121. Nothing carved.

## What an audit must check

Another agent writes it; it must not import `tools/survey_benchmark.py` or `tools/wayside_kit.py` geometry.

1. Every written block is in `blocks.ids`; none is a spawn condition (`data/spawn_blocks.json`) unscoped by
   `data/spawn_block_policy.json` for `survey_benchmark`; no chest, no bed, no lightning rod (a condition).
2. The plinth and the hut each stand on max(ground under them) + 1 from `tools/ground.py`, with a foundation down to
   the ground under every column; each stake's first fence post stands on its own column's ground.
3. The hut is enterable: two air blocks in the west doorway, a ramp whose every step is one block and whose last is
   above the ground, three or more air above the hut floor inside, and a solid roof.
4. The stakes lie on the line from the pillar to (3548, 5322), 12 blocks apart.
5. The barrel at `survey_benchmark_store` `container.at`; the trigger box standable air inside the hut touching it.
6. Hung blocks (lanterns, signs) written after what holds them; every write inside the function's and R9BM's
   force-load box and `bbox.writes`.
7. Re-measure the lantern's sightline from Victory Road and the clearance from every other build's box, the Rift
   polygon and every Habitat Block.
8. A GENERATOR mutation (the hut a block high, the door walled, a stake off its line) is caught.
