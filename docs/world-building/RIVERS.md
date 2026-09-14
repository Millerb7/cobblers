# Rivers and lake outflows: graded by descent

**Status: derived, 2026-09-14.** Computed from heightmap `acdc3d1d…` (`land_8k_16_eroded.png`).
The data is `data/rivers.json`; the tool is `tools/grade_rivers.py`, built on the descent search
in `tools/route_path.py`. The cut heightmap exists but is **not yet imported**: the live world is
unchanged.

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
- Channel depth is 2 blocks for outflows and creeks, 3 for rivers.

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

## The cut

**`python tools/grade_rivers.py cut`** writes `land_8k_16_eroded_rivers.png` beside the source
heightmap, which it never overwrites.

**Geometry:**
- a flat bed at `floor_y`, 2 × half-width + 1 blocks wide: 9 for rivers, 7 for outflows, 5 for
  creeks;
- banks at 1:1 up to natural ground;
- samples are only ever lowered.

| | |
| --- | --- |
| Courses cut | the 8 lake outflows and the channel south-west of Tilpey |
| Not cut | `river_of_shrews_from_high_end` (canal) |
| Columns lowered | 72,844 |
| Lowered | max 5.4 blocks, mean 2.0 |
| Output sha256 | `9deec4a6d9528f9175365f9da1614297ece6ab62af7aefb16180d3a572b74255` (recorded in `rivers.json` `cut`) |
| Regenerated | a second run wrote an identical file |

**Checks on the written file:**
- **Built-in:** at every block of every cut course, the lowest ground across the bed sits on the
  planned floor. Neither the floor nor that ground ever rises: 0.000 on all 9 courses.
- **Independent:** the minimum-cut search was re-run from every lake and source on both files.

  | Source | Before | After |
  | --- | --- | --- |
  | 8 lake outflows | 0.8–1.8 | **0.0** |
  | Channel south-west of Tilpey | 3.1 | **0.0** |
  | River of Shrews (not cut) | 11.25 | 11.25 |
  | Peak Pond creek (no river) | 22.5 | 22.5 |

  For the chained lakes (Shrew, Arrow), the search lets a channel bed sit up to its depth below
  the level of the lake it enters. Without that allowance it reports a false 1.2: the bed is 2
  blocks under the lake surface it runs into.

**To regenerate after a terrain change:**

```bash
python tools/grade_rivers.py plan
```

```bash
python tools/grade_rivers.py cut --replace
```

Then record the new output sha256. `cut` refuses a plan computed from a different heightmap.
`tools/validate_data.py` fails if `rivers.json` is stale, or if any graded polyline rises or
drops below sea level.

## Not done in this pass

- **Composition:** banks, meanders, gravel bars, pools. That is Axiom work.
- **Importing the cut heightmap.** `data/world.json` still pins the uncut file, and landmarks,
  regions, cells and the paint maps are measured from it. Switching the import means a new
  sha256 there, re-measuring and re-painting.
- **Water in the channels.** `tools/paint_maps.py` paints lake water only. Until it also paints
  each graded course at its `surface_y`, cut channels would export dry.
- **Decisions for you:**
  - Viltri's Path and the Marsh–Tilpey creek as named: re-draw them where the terrain drains,
    keep them as dry ravines, or re-shape the terrain.
  - Whether the River of Shrews canal should be cut (`--include-canals`).
