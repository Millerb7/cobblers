# Water life: what was designed, what is built, what is still bare

**Status:** measured 2026-10-04 on the canonical heightmap (`d1bc68d3…`, the applied water export) and committed data;
no world was read. One tranche built offline the same day (`cobblers_sea_floor`, below): not installed, not seen in
game, and its independent audit is not written yet.

Units: a **column** is one (x, z) block column; **sea** is every column whose rounded ground is below y62 and
which is not in a lake basin (`tools/water_mask.py`'s rule; the lake mask is `tools/water_shape.py`'s). Everything
here is inside the 8192 heightmap. The 37.7 km² border margin (OCEAN.md section 3) has no heightmap and is not
counted.

## Designed

| Source | What it asks for in the water |
|---|---|
| `OCEAN.md` section 4 "Kelp, seagrass, coral" | kelp on the seabed y28-58 (cold, temperate and lukewarm water, seamount tops), seagrass y40-60 on every shelf outside frozen water, coral reefs, fans and pickles on the Southern Shallows' warm shelf y46-60, one or two bleached dead-coral patches |
| `data/regions.json` `marine_regions[].flora` | the same per region: Frostwater kelp forests and seagrass (none under frozen water north of z1300, 120+ out); Windward kelp on the shelf and upper slope, seagrass; Eastern Reach kelp and seagrass; Southern Shallows seagrass across the shelf, coral reefs within 220 of land, no kelp there |
| `WATER_BUILD_PLAN.md` 3.3 | the river and lake skin: weed beds, silt in slow pools, river stones in riffles, drift logs at bends, reeds on slow banks, flowing riffles; the Viltri Ravine's dry half dressed |
| `WATER_BUILD_PLAN.md` 5.2, 6.2, 7.2 | the shore before Dive; the Dive sea (forge ruin, three wreck coves, the trench, three or more underwater caves, one surfacing); 40-60 wrecks and Rift debris |
| `regions.json` marine `content` | iceberg habitats in the Frostwater, cold and warm ocean ruins, reef habitats |

## Built before today (2026-10-02, `docs/mechanics/WATER_LIFE.md`)

| Pack | Covers, measured from each tool's own `report` today |
|---|---|
| `cobblers_lake_life` | all 9 painted lakes skinned: 946,593 cells written over 1,684,892 wet lake columns, and 8 hooks |
| `cobblers_sea_life` | five shaped coasts to 40 blocks from land, the Relic reef, 8 rock pools, a beached wreck, 48 wrecks and debris, two sea caves. Its flora: 33,176 kelp + 28,645 seagrass + 12,665 reef columns. **70,695 sea columns carry its flora (0.33% of the sea)** |
| `cobblers_sea_drift`, portals, ferries | not flora: the Drift and Driftmouth Isle, the dive portals, the docks |

## The gap, measured (before today's tranche)

| Water | Columns | Dressed | Bare |
|---|---:|---:|---:|
| Sea, all | 21,105,566 | 70,695 (0.33%) | 99.7% |
| of which within its region's shelf width of land, outside every exclusion, not frozen | 10,830,236 | the same 70,695 | 99.3% |
| Lakes (9) | 1,684,892 wet | all 9 skinned (946,593 cells) | the skin is by zone, not a carpet; no gap the design names |
| Rivers (12 graded courses, 11,045 blocks long) | about 113,700 (width x length from `data/rivers.json` reaches, not a raster) | 0 | 100% |

By region (sea columns; `python tools/sea_floor.py report`): Frostwater Shelf 7,167,712 (10,794 dressed by
`sea_life`), Southern Shallows 10,574,350 (32,167), Eastern Reach 1,990,629 (0), Windward Sea 1,372,875 (27,734).
The depth profile: 1.2M columns 1-2 deep, 10.1M 3-12, 2.9M 13-16, 2.9M 17-34, 4.7M 35-52.

## Built today: the open sea's floor (`cobblers_sea_floor`)

`tools/sea_floor.py`, `data/sea_floor.json`, `reapply.py` step **R9SF** after R9SL, prepare job `sea_floor:build`.
Kelp forests and seagrass meadows on the shelf of all four marine regions, by each region's own flora rule and shelf
width (read from `regions.json`, not restated):

| Region | Kelp columns | Seagrass columns (tall) |
|---|---:|---:|
| Frostwater Shelf | 95,356 | 465,683 (17,428) |
| Southern Shallows (kelp only beyond 220 of land) | 90,049 | 933,220 (35,345) |
| Eastern Reach | 28,913 | 128,185 (4,928) |
| Windward Sea | 17,208 | 56,745 (2,287) |
| **All** | **231,526** | **1,583,833 (59,988)** |

**1,815,359 columns dressed: the sea goes from 0.33% to 8.9% carrying flora, and 16.8% of the reachable shelf.**
Patchy on purpose (forests and meadows, not a carpet), and bounded by the command budget below.

- Kelp on seabed y28-58, tops at most y59 (sea - 3, the threshold both water-life audits hold), age 25 so it never
  grows nearer; seagrass on y40-60, never inside a gate line's clearance.
- **Every write is `fill ... replace minecraft:water`**, so it can only turn sea water into a plant: nothing another
  pack or a donor template put in the sea is overwritten ("Our list is not the world").
- Exclusions: all of `tools/sea_life.py`'s (towns, routes, bridges, the Rift, Victory Road, lakes, docks, ferry
  lanes, gate lines, portals, legendaries, adopted sites, placements including the six underwater ruins, Pacifidlog,
  the First Cast hole, the Relic swim lines, the Drift and Driftmouth Isle, the Deep) and, so the two packs share no
  column: every cell `sea_life` writes plus 3, its five coasts to 48 of land, the Relic reef plus 10. 1,059,636 sea
  columns excluded. There is no "water-mount route" in the data (`data/water_mounts.json` lists species only); the
  ferry lanes are the routes there are.
- Size: 844,904 fill commands in 1,000 functions (128-block tiles), 16,946 chunks force-loaded once each; every
  function passes `tools/function_limits.py`. Budget 900,000, fail-closed.
- Spawn conditions: `kelp_plant` is a `neededNearbyBlocks` block for dragalge and skrelp, `seagrass` for pincurchin
  and herds (`data/spawn_blocks.json`). Our own `data/spawns.json` entries for skrelp and pincurchin carry no block
  condition; whether the base pack's own sea spawns are still live in this world was not checked. Neither block is in
  the spawn-block policy's whitelist, which governs templates; `sea_life` and `lake_life` already place both.
- Tests (the builder's own): `tests/test_sea_floor.py`, 14. **The independent audit is not written.**

## Still unbuilt, and why

| Piece | Why not today |
|---|---|
| **Coral reefs on the Southern Shallows warm shelf** (the only Corsola/Cursola habitat the design names), sea pickles, bleached patches | `data/spawn_block_policy.json` whitelists live coral for `cobblers_sea_life`'s Relic reef only; dead coral not at all. Widening it is the owner's call. The shelf within 220 of land in the south is where it would go |
| **River and stream beds** (weed beds, stones, drift logs, reeds; flowing riffles) | No tool knows a river's water surface per column: `tools/water_mask.py` covers lakes and the sea only, and `rivers.json` gives a fractional `surface_y` per station. Placing seagrass from that guess risks plants in air. The rule comes first; flowing riffles also wait on proof P3 |
| Viltri Ravine's dry half | held by the owner (`WATER_BUILD_PLAN.md` decision 4) |
| The Dive sea's sites: forge ruin, three wreck coves, the Lugia trench, two more underwater caves (one built), the sunken Pallet fragment | coves and ruin need EXP-014's template capture; the trench waits on an owner decision; the caves are a build of their own |
| Seamounts and kelp on their tops | all five seamounts sit in the border margin, outside the heightmap |
| Iceberg habitats, ocean ruins on the Frostwater slope and the Eastern Reach shelf | not designed beyond a line in `regions.json`; six underwater ruins are already placements |
| The bare shelf between today's patches | the budget: coverage costs commands linearly. Lower the `patch_over` thresholds in `data/sea_floor.json` and raise the budget together, after the owner has seen this tranche in game |

## Not verified

Nothing here ran in a game: that kelp and seagrass placed by command hold in these biomes (proof P6), that a
`fill ... replace` run of 1,000 functions finishes in reasonable time on the staging server, and that the 0.15% of
columns where `round(h)` is not the exported ground leave no seagrass floating.
