# Rivers and lake outflows: graded by descent

**Status: derived, imported and exported, 2026-09-14.**
- **Planned on** the authored heightmap `acdc3d1d…` (`land_8k_16_eroded.png`).
- **Cut into** `land_8k_16_eroded_rivers.png` (`861d10ac…`), which `data/world.json` now imports
  (`heightmap.derived_from` records the authored file).
- **Data:** `data/rivers.json`. **Tools:** `tools/grade_rivers.py`, built on the descent
  search in `tools/route_path.py` and the drainage in `tools/drainage.py`.

**Two passes the same day:**
- **The first pass (sections up to "Rivers: the carves against descent"):** can water descend
  at all, and where?
- **The second pass (from "Second pass" on):** redrawn rivers, character by reach, the major
  river, water fill and re-export.

## Why the method changed

The carved beds of 2026-09-14 follow the ground. They rise by up to 59 blocks (Viltri's Path) on
the way to their low end, so no water can run along them (`TERRAIN_2026-09-14.md` §4).
Repairing those carves by hand would repeat the mistake. Instead, the terrain is asked whether
a descending course exists at all.

## Method

**Rule:** a bed never rises in the direction of flow.
- Along any path, the water surface at a station is the lowest ground met so far, and never
  below sea level (y62).
- Ground standing above that surface needs a **cut** of (ground − surface).
- A lake on the path is flat at its painted level. A course may drop into a lake at or below its
  surface, but can never be cut into a lake that stands above it.

**Search** (`route_path.py`), on 4-block cells min-pooled so a one-block channel survives:

| Function | What it finds |
| --- | --- |
| `descend_min_cut` | The smallest worst cut any descending path to the goal needs. Exact label-setting search on (worst cut, surface). |
| `descend_route` | The cheapest path whose every cut stays within an allowance: the minimum plus 2 blocks. It prefers valley floors (local relief) and shallow cuts. |

**Sources and goals** (`grade_rivers.py plan`):
1. **Lakes first, lowest level first.** Each starts at its painted water level, from every water
   cell. The goal is open sea, or a lower lake or a course already graded. Joining one inherits
   that body's remaining cut.
2. **Then inland river ends, lowest first.** A carved channel end counts as a source only when it
   is not within 150 blocks of a lake, not within 150 blocks of open sea (a mouth), and not
   within 100 blocks of another carved axis (a confluence).
3. **The 20-block rule:** a course whose least worst cut is over 20 blocks is **no river**. It is
   reported, not graded and not cut.
4. **Canals:** a course that descends only by cutting more than 3 blocks along more than half its
   length is marked a **canal**. It is graded but not cut unless asked (`--include-canals`).
5. **Re-measured at full resolution:** every graded course is re-measured on the full heightmap
   (lowest ground within 2 blocks of the centreline).

**Along the carve** (per river): the same minimum-cut search, confined to a band 100 blocks
either side of the carved axis. It asks: can water run where the channel was drawn?

**Output:** a graded polyline per valid course, `[x, z, surface_y, floor_y]`. It is simplified
so the plan stays within 1.5 blocks and the floor within 0.5 blocks of the dense course.
- `floor_y` = `surface_y` − channel depth.
- In the first pass the channel was fixed (depth 2 or 3, flat bed, 1:1 banks). The second pass
  sizes and shapes every reach from the terrain (below).

## Lakes: every one has a real outflow

The painted level is one block below each basin's spill. For every lake, a descending course
from that level to the sea exists, and its only cut is the rim freeboard (0.8–1.9 blocks). No
lake is an artificial pit.

| Lake | Level | Spill | Least worst cut | Outflow goes to | Course length | Drop |
| --- | --- | --- | --- | --- | --- | --- |
| Lake Tilpey | 77 | 77.9 | 0.8 | the east coast (6970, 3970) | 352 | 15 |
| Watering Hole | 95 | 96.0 | 0.9 | the south coast (2582, 6494) | 1,312 | 33 |
| Arrow Lake | 100 | 101.2 | 1.2 (routed 1.3) | Watering Hole | 361 | 5.5 |
| Marshy Marsh | 100 | 101.6 | 1.6 (routed 2.4) | the north-east coast (5662, 1598) | 395 | 38 |
| Lake Viltri | 103 | 104.8 | 1.8 (routed 1.9) | the north-west coast (674, 1846) | 1,711 | 41 |
| Peak Pond | 105 | 106.1 | 1.1 (routed 1.4) | the north coast (4498, 966) | 545 | 43 |
| Shrew Lake | 106 | 107.3 | 1.3 | Arrow Lake | 231 | 6.1 |
| Pond west of Mt Clay | 119 | 120.1 | 1.1 (routed 1.2) | Lake Viltri's outflow at (858, 2062) | 1,261 | 30.8 |
| Tarn at the head of the Peak Pond ravine (added 2026-09-14, third pass) | 127 | 128.3 | 1.3 (routed 2.0) | the north coast (3298, 434) | 401 | 65 |

**The tarn was missed** by the annotation and left dry by the first two passes. It is a closed
hollow 23 blocks deep (floor y105) at the head of the dry ravine above Peak Pond, found from the
air on the 2026-09-14 flight. It is `ravine_head_tarn` in `landmarks.json`. The ravine still
cannot carry its water to Peak Pond, since that needs a 7-block cut along the carve. Its real
outflow leaves the north-west rim at (3289, 848) and falls straight to the north coast.

**Chains:**
- **Shrew Lake → Arrow Lake → Watering Hole → the south coast.** This follows the carved creek
  south of Arrow Lake.
- **Pond west of Mt Clay → Lake Viltri's outflow → the north-west coast.**

**The rivers these outflows make do not follow the carves** except below Arrow Lake. The
drainage goes where the terrain slopes, which is mostly short, direct lines to the nearest coast.

## Rivers: the carves against descent

| Carved channel | Along the carve | Terrain's own course from its source | Verdict |
| --- | --- | --- | --- |
| **Viltri's Path** (Lake Viltri → Mouth of Viltri) | Needs a **31.5-block** cut | Lake Viltri drains north-west instead: 1.8 cut, 1,711 blocks | **No river along the drawn course.** The lake's real outflow runs to the north-west coast. Running it to the Mouth only works along the coastal lowland, which is a shoreline ditch, not a river. |
| **River of Shrews** (Shrew Lake ↔ inland end 1642, 4650) | Shrew Lake → inland end: 3.2 cut. Inland end → Shrew Lake: impossible, since the end (y98) is below the lake (y106) | From the inland end, the only descent is a 1,777-block trench at y98→97, cut up to 11.3 blocks along 94% of its length | **Canal, not a river.** Water could leave Shrew Lake westward, but from the inland end it has nowhere to go. Shrew Lake's real outflow is south-west into Arrow Lake. Graded; not cut. |
| **Creek into Peak Pond** (unannotated) | Needs 28.3 blocks (to the pond) or 29.0 (from it) | Least worst cut from its head (y105.7) is **22.5** | **No river.** The head is less than a block above the pond, with a 22-block rise between. |
| **Creek, Marshy Marsh → Tilpey** (unannotated) | Needs **31.7 blocks** | The marsh drains north-east to the sea (1.6) | **No river along the drawn course.** |
| **Creek south of Arrow Lake** (unannotated) | **1.2 cut**: water can run along it | Arrow Lake → Watering Hole → the south coast | **Works.** Graded as the Arrow Lake and Watering Hole outflows. |
| **Its south-east branch** (unannotated) | Confluence → south-east coast needs **26.9 blocks** | Its head is the confluence with the creek above, already drained by it | **No river along the drawn course.** |
| **Channel south-west of Tilpey** (unannotated) | Inland end → Tilpey: **3.1 cut**. Tilpey → inland end: 41.3 | Runs into Tilpey: 3.4 cut, 484 blocks, drop 38 | **Works as an inflow creek, not as an outlet.** Graded and cut. |

**Plainly: Viltri's Path, the Peak Pond creek, the Marsh–Tilpey creek and the south-east branch
cannot be rivers where they are drawn.** Each needs more than 20 blocks of cut. That is the
terrain telling us there should not be a river there, so none of them is forced. The River of
Shrews stays under 20 blocks, but only as a trench across flat ground. It is recorded and left
uncut.

## Second pass: what the rivers are

### Redrawn, left dry, left uncut

| Landmark | Now | Why |
| --- | --- | --- |
| `viltris_path` (Viltri's Path) | **river**, on Lake Viltri's real outflow north-west to the coast, 1,711 blocks | a 1.8-block notch at the rim instead of a 31.5-block gouge on the drawn course |
| `viltri_ravine` (new) | **dry ravine**, the original carve to the Mouth of Viltri | a fine landform; no water |
| `marsh_outflow` (new) | **river**, Marshy Marsh north-east to the coast, 395 blocks | a 1.6-block notch instead of 31.7 |
| `marsh_to_tilpey` | **dry ravine** | as above |
| `peak_pond_creek`, `arrow_lake_south_east_branch` | **dry ravines** | 22.5 and 26.9 blocks of cut needed |
| `river_of_shrews` | **planned, canal candidate**, not cut | 94% of its length would be cut |
| `tilpey_south_west_outlet` | **river**, renamed the creek into Lake Tilpey from the south-west | water runs into Tilpey, not out |
| `arrow_lake_south` | **river**: the Arrow Lake and Watering Hole outflows | works where carved |
| `major_river` (new) | **the major river** | below |

Ravines are painted with the old gravel floor; rivers are painted from `data/rivers.json`.

### Character, computed per reach

**Every graded course is split into 64-block reaches.** Each reach is sized and shaped from
the terrain:
- **Catchment:** D8 drainage on the priority-flooded 4-block grid, with every cut course
  burned in, so flow follows the courses. It never decreases downstream.
- **Grade:** the drop of the graded surface over the reach, plus 64 blocks either side.

**Then:**

| Property | Rule (exact text in `rivers.json` `parameters.character`) |
| --- | --- |
| Width | (3 + 4.5·√catchment km²) × speed, 3–19, where speed = (grade/0.005)^−0.2, 0.75–1.3, so slow water spreads wider |
| Centre depth | 1 + 1.1·catchment^0.45, 1–4.5. The bed is a parabola, one block deep at the edge |
| Bank slope | 0.4 (1:2.5) at grade ≤ 0.001, rising on log(grade) to 2.0 (steep) at ≥ 0.0316 |
| Bed | gravel at grade ≥ 0.01, sand ≥ 0.0025, clay (silt) below |
| Incision | the water sits 1 block under the lowest ground, so there are banks. Never below the next lake or the end level, and grown at most 0.02 per block below a lake |

**What each river became:**

| Course | Length | Catchment km² | Width | Depth | Banks | Beds | Why it looks like that |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| Viltri's Path (`lake_viltri_outflow`) | 1,711 | 0.14 → 3.35 | 4 → 10 | 1.4 → 2.9 | 0.4–2.0 | gravel 47%, sand 27%, clay 26% | The most varied river. It leaves a small lake narrow and fills out downstream as the Mt Clay pond's creek joins (0.4 → 3.2 km²). It runs steep through the hills in gravel and slows over the coastal flats in sand and clay |
| Creek from the pond west of Mt Clay | 1,261 | 0.44 → 3.17 | 5 → 10 | 1.8 → 2.8 | 1.2–2.0 | gravel 82%, sand 18% | A fast mountain stream, mostly gravel with steep banks. It widens where it gathers the Tri Peaks' slopes |
| Watering Hole outflow | 1,312 | 4.35 → 4.73 | 10 → 11 | 3.1 → 3.2 | 1.3–2.0 | gravel 80%, sand 20% | The biggest ordinary river: Shrew, Arrow and the Watering Hole all drain through it. Steep to the south coast, so gravel and steep banks |
| Arrow Lake outflow | 361 | 3.0 → 3.2 | 8 → 11 | 2.8 → 2.9 | 1.1–2.0 | sand 72%, gravel 28% | Short and gentle between two lakes, so mostly sand |
| Shrew Lake outflow | 231 | 2.5 | 8 → 10 | 2.7 | 1.3–2.0 | gravel 72%, sand 28% | A short, fairly steep link from Shrew Lake down to Arrow Lake |
| Marsh outflow | 395 | 1.0 | 6 → 10 | 2.1 | 0.4–2.0 | gravel 84%, clay 16% | Slack and clay-bedded as it leaves the marsh, then a steep gravel run to the sea |
| Peak Pond outflow | 545 | 0.55 → 0.66 | 5 → 9 | 1.8 → 1.9 | 0.4–2.0 | gravel 64%, clay 24%, sand 12% | A small stream: a quiet start at the pond, then a steep drop to the north coast |
| Tarn outflow (`ravine_head_tarn_outflow`) | 401 | 0.16 → 0.17 | 4 (6 in the tarn) | 1.5 | 2.0 | gravel | A narrow, steep mountain stream: 65 blocks of drop over 401 to the north coast |
| Creek into Tilpey from the south-west | 484 | 0.08 → 0.11 | 3 → 6 | 1.3 → 1.4 | 0.5–2.0 | gravel 60%, clay 27%, sand 13% | The smallest: a narrow hill creek falling 38 blocks into Tilpey |
| River of Shrews (not cut) | 1,777 | 0.02 → 3.18 | 5 → 14 | 1.2 → 2.9 | 0.4–1.2 | clay 89%, sand 11% | Would be a slow, clay-bedded ditch across flat ground. On file only |

### The major river

**Picked by catchment.** Every system that reaches the sea was ranked:

| Mouth | Catchment km² | Longest descending path | Tributaries ≥ 0.25 km² |
| --- | ---: | ---: | ---: |
| **East coast (6964, 3964), the Tilpey system** | **14.03** | **3,389** | **8** |
| South coast (2584, 6492), the Watering Hole system | 4.73 | 2,862 | 4 |
| North-west coast (676, 1848), Viltri's Path | 3.36 | 2,550 | 3 |

**2026-09-15: the head moved down 1,661 blocks.** From the air, a channel ran across a mountain near (2583, 1546).
- **Neither the GIMP river layer nor erosion made it.** The authored `land_8k_16_eroded.png` has no trench there:
  no column sits more than 4 blocks below its 10-block surroundings within 700 blocks. The cut file lowered up to
  6 blocks there.
- **The channel came from `tools/grade_rivers.py`.** It started the trunk at the far end of the longest descending
  path, where the catchment is 0.009 km².
- **The first 720 blocks were cut along the mountainside.** Within 250 blocks, the downhill side never rises 10
  blocks. The uphill side rises 22–57 blocks within 14–44 blocks.
- **Below that, a 3–6-block creek ran on the floor of the Glacial Tear trough.** Its walls are 19–57 blocks high,
  92–184 blocks either side, and its catchment stayed at 0.06–0.12 km².

**First rule, since replaced.** The trunk started where its path first drained 0.13 km², the smallest catchment
feeding any lake outflow. That also removed the trough-floor creek, so it was replaced the next day.

**The rule now: valley walls (2026-09-16, not exported yet).** The trunk starts at the first station that begins
three consecutive samples, 48 blocks apart, where the authored ground on both sides rises at least 10 blocks above the
water within 250 blocks. The constants are `WALL_RISE`, `WALL_REACH`, `WALL_RUN` and `WALL_STEP` in
`tools/grade_rivers.py`.
- **Where it starts:** (3135, 1635), 817 blocks down the path, on the Glacial Tear trough floor. The flank channel
  stays gone and the meltwater creek comes back.
- **Below the head, nothing else moves.** The course is kept as routed from the path head, and sized from the whole
  path with the hillside above counted in its drainage.
  - Routing again from the head moved the lower valley 11–23 blocks sideways. Re-binning the reaches shifted
    widths by up to 6 blocks. Both were tried and dropped.
  - The lower river matches the original course within 2 blocks. Its reaches are identical but for one depth
    (7.5 against 7.6).
  - Against the original cut, about 1,200 columns change by half a block or more, the most by 3 blocks.
- **The creek:** 5–6 wide and 2.8–2.9 deep for about 780 blocks, then the river widens to 18–28 with floodplain and
  terraces.
- **Other courses: none affected.** The survey (`major_river.head_rule_survey_other_courses`) found the only other
  non-lake heads, River of Shrews and the south-west creek into Tilpey, walled from their first sample. The rule
  would move neither.
- **A sizing fix that came with it:** the major-river scale now ignores stations within `VALLEY_CLEAR` (150 blocks)
  of a lake. One reach at Lake Tilpey's edge, where tributaries converge, had shrunk the whole lower river to 9–16
  wide.
- **Over the cavern:** the creek crosses the Displaced City cavern footprint with its graded floor at y95.9–97.6.
  In 8 columns that leaves 23 blocks of rock over a y72 ceiling, so the cavern ceiling drops to y71 there.

**Checked on every cut course.** 581 stations at 16-block spacing, excluding lake basins, on the graded floor, the
heightmap bed, the world bed and the world water surface: no rise anywhere, before or after the change.

**Original selection text** (the head it describes is the old one):

**All three measures agree.** The trunk runs from the farthest ground that falls, without any
rise, to Lake Tilpey:
- it starts at (2504, 1444), y171, on the flank above Merian;
- it goes down the Merian cirque and the full length of the Glacial Tear into Lake Tilpey;
- it leaves Tilpey by its outflow to the east coast.
- **Length:** 3,085 blocks to the lake, then 352 to the sea.
- **Terrain allowance:** only 0.8 blocks of cut is needed to make it descend.
- **The Rift stays dry.** Its closed basin is a tributary on the drainage map, but a course
  cannot cross its floor without cutting its rim, so the trunk does not go there.

**Whether the terrain can carry it: yes, easily.** The Glacial Tear is a U-shaped glacial
trough 396 blocks wide rim to rim, with a floor that falls without counter-slope, so a
30-block river with a valley fits inside it.

**What it is, reach by reach:**
- **Headwater (first 1,620 blocks):** a 3–6-block gravel creek with steep banks.
- **Lower trunk:** a big tributary joins (catchment 0.12 → 1.05 km²). From there the river is
  18–26 wide and 7–9 deep, set 6–8 blocks below its floodplain.
  - **Floodplain:** 19–28 blocks each side.
  - **Terraces:** two, each 5 blocks high, as far as 150 blocks from Tilpey.
  - **Beds:** sand where it slows, gravel elsewhere.
- **Tilpey outflow:** 22–32 wide and 9 deep, a confined gravel gorge to the sea. It gets no
  floodplain or terraces: it is steep, and a valley cut there carved an amphitheatre into
  the lake rim.

**Cost:**

| Course | Removed | Deepest | Widest reach from centre |
| --- | ---: | ---: | ---: |
| Trunk | 1,316,951 blocks | 19.7 | 121 |
| Tilpey outflow | 88,406 blocks | 15.1 | 25 |
| **All ten cut courses** | **1,601,157 blocks**, 281,347 columns | 19.7 | |

**A landmark and a barrier** (`major_river`, working name only; naming is yours).
- **Sabrina to Blaine** (`route_07_sabrina_to_blaine`, roughly 2,050 blocks on the canonical routes) crosses at
  the mandatory bridge waypoint (6632, 3904). It was 2,021 blocks in the 2026-09-14 routing.
- **Without crossing** the river or the lake, the same leg was 9,496 blocks, back around the
  river's head (2026-09-14 routing on 8-block cells; not re-measured).
- **Upstream it is a creek.** The northern route (Surge → Erika, `route_04_surge_to_erika`) now passes
  the river's head and records no water crossing at all. The barrier exists only where it is big.
- **Not a hard wall:** 30 blocks of still water can be swum. What makes it a barrier is the
  detour and the drop to the water; a bridge or boat is the intended crossing.

### Channel fill

**`tools/paint_maps.py`** now reads the cut courses from `rivers.json`. For each course it
writes a per-column water-level crop (`river_<course>.png`): `floor(surface + 0.01)` within the
reach's half width.

**It also paints:**
- the reach's bed material, with sand or gravel banks two blocks wide;
- the `river` biome (`frozen_river` among cold biomes);
- no trees, plants or frost on the water. Moving water does not freeze, and an iced river
  would not be a barrier.

**Guards:**
- It refuses a `rivers.json` whose cut is not the imported heightmap.
- `paint.js` only ever raises water, so a river never lowers a lake or the sea.

**Verified in the exported region files** (four sampled stretches, `world_heights.extract`):

| Stretch | Planned water columns | At the planned level | 1 block higher | Dry |
| --- | ---: | ---: | ---: | ---: |
| Major river, lower Glacial Tear | 19,617 | 18,557 | 1,060 | **0** |
| Tilpey outflow gorge | 9,014 | 8,737 | 277 | **0** |
| Viltri's Path, middle | 7,463 | 7,463 | 0 | **0** |
| Major river headwater | 1,507 | 1,507 | 0 | **0** |

The columns 1 block higher are inside Lake Tilpey's basin outline, which raises water to 77.

**Where each course meets its lake, the river surface is one block below the lake** (for
example, Tilpey at 77 and its outflow at 76). In game, lake water will pour a block into the
channel there. **Not checked in game:** how that step and the 1-block steps along each river
behave when the water updates.

### Re-import and re-measure

- `data/world.json` imports `land_8k_16_eroded_rivers.png` (`861d10ac…`). The authored file is
  in `derived_from`, and the validator checks `rivers.json` against both.
- `data/cells.json`: recomputed with `cell_stats.py --write-cells`, and the validator reports
  no drift.
- **`data/regions.json`:** the measured blocks were recomputed from the committed polygons by
  the new `tools/region_measure.py` on the cut heightmap.
  - **83 records moved by up to about 2 blocks of elevation and 3% of area.** Almost all of
    that is the method: the region plan measured scratch label rasters, which the repo does not
    keep.
  - **The cut itself changed 18 records.** The largest are the upper trough (p10 −4.1,
    mean slope +1.6°), the Glacial Tear (p10 −2.8), the lower trough and Tilpey's east shore
    (under 1 block).
- **`data/landmarks.json`:** river landmarks now point at their `graded_courses`, lakes carry
  their `outflow`, and basin measurements stay on the authored heightmap.

**To regenerate after a terrain edit:** edit `land_8k_16_eroded.png`, then run:

```bash
python tools/grade_rivers.py plan
```

```bash
python tools/grade_rivers.py cut --replace
```

After that, update `heightmap.sha256` and `derived_from.sha256` in `data/world.json` and re-run
`cell_stats.py --write-cells`, `region_measure.py --write` and `paint_maps.py`. The plan and the
cut are deterministic: repeated runs wrote the same `861d10ac…`.

### Still not done

- **Composition:** meanders, gravel bars, pools, bank detail. That is Axiom work. The graded
  polylines are straight 4-block routes.
- **In game:** the water behaviour at steps, the river biome's spawns, and how the barrier
  plays.
