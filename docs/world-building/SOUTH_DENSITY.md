# How thin is the south?

The owner, 2026-10-04: "the southern map, still the thinnest." Measured here before anything was built against it, by
`python tools/south_density.py` (reproducible from `data/` and the canonical heightmap; nothing reads a world).

## The method

Every 1024-block cell of `data/world.json`'s grid (rows A-H north to south, columns 1-8 west to east) is counted for
what a player meets: places, residents, trainers, shrines, encounters' hearts (Habitat Blocks, the Mega dens, the
gulch), caches, legendary sites, NPCs, landmarks and towns. The file-to-category map is in the tool's docstring. Points
are snapped to one per 32-block bucket per file, so a place's twenty signs count once. Density is things per km² of
**land** (heightmap above the sea, sampled every 8 blocks), because half of row H is sea.

**What it does not count** (CLAUDE.md "Our list is not the world"): what a donor template or a mod places (gym
healers, Repurposed Structures), wild spawns (a table, not a point) and route geometry. It is a count of our own
records, not of the world.

**A fault found and fixed while measuring.** The residents-format files (`southern_residents.json`,
`northern_residents.json`) place their pieces by relative offsets under the key `at`, which the shared extraction
(`tools/poi_heatmap.py`'s) reads as absolute coordinates: four "residents" were counted in A1, near the map's origin.
The tool now counts one thing per resident site at its centre, and drops any other point with both x and z under 64.
`tools/poi_heatmap.py` still has the fault; its heatmap shows a false hot spot in A1's corner. Not fixed there (not this
unit's file); worth one line when someone next touches it.

## The numbers (before this unit's places, 2026-10-04)

| Band | Things | Land | Per km² of land |
| --- | --- | --- | --- |
| North, rows A-E | 727 | 30.13 km² | **24.1** |
| South, rows F-H | 218 | 14.63 km² | **14.9** |

The south is 62% as dense per km² of land as the north. Among cells with at least 40% land the median is **7.1** a km²
in the south against **18.1** in the north. By category the gap is not even: **trainers 12 against 92** (7.7 times
fewer, against 2 times less land), shrines 1 against 5, caches 13 against 22, residents 12 against 16, encounters 32
against 142. Places (88 against 257) and towns (13 against 50) are close to the land share.

Most of the south's count sits in four cells: G3 (56.6 a km²), G4 (39.9), F7 (29.6) and F5 (Route 8 and the Dry
Cistern's brow, 25.7). Away from them it is nearly empty.

## The emptiest southern cells (40% land or more), before

| Cell | Land | Things | Per km² | Terrain (sub-region / paint preset; land ground p10-p90, measured from the heightmap every 4 blocks) |
| --- | --- | --- | --- | --- |
| H3 | 71% | 1 | 1.3 | Sunset East flower meadow, y70-101; Sunset Isle, no route |
| G5 | 43% | 1 | 2.2 | the plateau's south rim (plateau_west / badlands_top, plateau_south / badlands_eroded) falling to the sea, y66-156 |
| F1 | 75% | 2 | 2.5 | the Fungal Isle (mushroom), y66-142; Grandmother Cap and the adopted Zapdos tower already stand there |
| H2 | 76% | 2 | 2.5 | Sunset West savanna, y74-137 |
| F3 | 100% | 3 | 2.9 | the Arrow Creeks savanna, y93-136, gentle and dry, 750-1,000 blocks from any route |
| G7 | 66% | 2 | 2.9 | the south-east dunes (desert), y72-147 |
| F6 | 100% | 6 | 5.7 | the plateau's eroded south (badlands_eroded), y125-168, dead flat on top; four of the six are Route 8 trainers |
| G6 | 51% | 3 | 5.7 | dunes falling from the plateau to the south-east coast (desert), y67-161 |

The northern rows have emptier cells too (C7 0.0, C1 1.8, A8 4.2), but they are coast and sea fringes; the south's
emptiness is in whole land cells: F3 and F6 are 100% land with three and six things each.

## The emptiest ground in each chosen cell

From the tool's candidates (every 32 blocks, outside the Rift and its rim sculpt's reach, outside towns and place boxes):

| Cell | Point | Distance to anything counted | Off the nearest route |
| --- | --- | --- | --- |
| F3 | (2416, 5136) | 530 | Route 1, 948 |
| F6 | (5168, 6128) | 494 | Route 8, 722 |
| G6 | (5552, 6160) | 634 | Route 8, 877 |
| G7 | (6640, 6832) | 584 | Route 8, 1,877 |
| H3 | (3056, 7984) | 735 | Route 8, 1,600 |

Almost nothing in these cells is within 250 blocks of a walked route: the south has three roads (Route 8, Victory Road
and the end of Route 1), and its emptiness is the country between them.

## What was built against it

Five places, one each in F3, F6, G6, G7 and H3: `docs/world-building/FAR_SOUTH.md`. G5, F1 and H2 were passed over:
F6's site stands 205 blocks from G5's emptiest high ground and serves it; F1 already has a named resident and a
legendary site on an island of 0.78 km² (data/regions.json fungal_isle); H2 shares Sunset Isle with H3, and the isle's one encounter heart is the Old
Orchard's. They are the next candidates.

After the five (same tool, 2026-10-04): south **226 things, 15.4 a km²** (north 727, 24.1). F3 2.9 → 3.8, F6 5.7 → 7.6,
G6 5.7 → 9.4, G7 2.9 → 4.3, H3 1.3 → 4.0. Five places do not close a gap of 9 a km²; the trainer gap (12 against 92)
is the largest single difference and is the next lever, not more places.
