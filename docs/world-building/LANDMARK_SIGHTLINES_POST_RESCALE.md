# Landmark sightlines: the reproducible survey (2026-09-16)

**Status: current survey, replacing every earlier count.** The counts previously in this document and in `FOLIAGE.md`
cannot be regenerated. They were cast at 00:36 on 2026-09-16 from the retired 8-block legs
(`derived/routes/critical_legs.json`), over a `build/paint/canopy.npz` that the paint rerun overwrote at 08:02 the
same day. With every other input restored (same tools, library, foliage data, legs file and heightmap), the
available canopy gives different counts. Only the canopy is missing, so the earlier figures are withdrawn rather than
kept as a baseline.

## How to reproduce this

Run both commands from the repository at the revision that adds this document:

```
python tools/paint_maps.py --source-root <root> --out build/paint
python tools/landmark_trees.py check --source-root <root>
```

| Input | Value |
| --- | --- |
| Heightmap | `land_8k_16_rescaled_b145_pads.png`, sha256 `5b9635676bb0…` (canonical, `data/world.json`) |
| Canopy | `build/paint/canopy.npz` from the first command, 4-block cells, sha256 `ce7da822b7d14a7260a4fb431710b805b9c0aa7023c619d2d90edbdd64e56741`. Painting twice gives the same bytes (seed 20260914) |
| Legs | `data/routes.json` polylines, which `landmark_trees.py` now reads by default |
| Sites, trees, observers | `data/foliage.json` `landmark_trees`, `kits/structures/foliage/library.json` heights |
| Output | `derived/foliage/landmark_sightlines.json`. Two runs are identical |

The canopy check is the reproduction check. If the first command writes a different sha256, the paint inputs
(`data/regions.json`, `landmarks.json`, `rivers.json`, `foliage.json`, `towns.json`, the library or the heightmap) have
changed since this survey, and the counts below are stale.

What the cast does: eye height 1.6 at every leg point (spacing per `seen_from`), a ray to the crown top less 3
blocks, over the heightmap raised to the planned canopy. The tree's own 24-block glade is lowered back to ground, so
the tree cannot hide itself.

## Results

| Landmark | Tree | Seen from | Share | Nearest / farthest seen |
| --- | --- | ---: | ---: | ---: |
| `great_oak_pallet` | 40 tall, ground y103.5 | 26 of 42 leg points | 61.9% | 340 / 1,146 |
| `sentinel_spruce_tarn` | 75 tall, ground y129.7 | 34 of 72 leg points; 22 of 24 on the 60-block ring | 47.2%; 91.7% | 391 / 1,532 |
| `patriarch_wedge` | 30 tall, ground y146.7 | 58 of 164 leg points | 35.4% | 248 / 2,964 |
| `cherry_elder_shrew` | 26 tall, ground y143.5 | 71 of 152 leg points | 46.7% | 619 / 2,668 |
| `weeping_elder_tilpey` | 35 tall, ground y81.1 | 25 of 148 leg points | 16.9% | 863 / 1,510 |

### Per leg

The tool adds a landmark's legs together. These are the same inputs, each leg cast as its own `seen_from` entry. The
two legs that saw nothing (`gym4→gym5` for the Sentinel, `gym1→gym2` for the Cherry Elder, 0 of 22 and 0 of 20) were
removed from `data/foliage.json`, so they are no longer listed.

| Landmark | Leg | Points | Seen | Share |
| --- | --- | ---: | ---: | ---: |
| `great_oak_pallet` | `hometown→gym1_town` | 42 | 26 | 62% |
| `sentinel_spruce_tarn` | `gym3_town→gym4_town` | 72 | 34 | 47% |
| `patriarch_wedge` | `gym8_town→league` | 164 | 58 | 35% |
| `cherry_elder_shrew` | `hometown→gym1_town` | 42 | 25 | 60% |
| `cherry_elder_shrew` | `gym8_town→league` | 110 | 46 | 42% |
| `weeping_elder_tilpey` | `gym5_town→gym6_town` | 41 | 10 | 24% |
| `weeping_elder_tilpey` | `gym6_town→gym7_town` | 43 | 9 | 21% |
| `weeping_elder_tilpey` | `gym7_town→gym8_town` | 64 | 6 | 9% |

**Observations, not decisions:**
- **No listed leg measures zero** now that the two legs that never saw their tree are gone.
- **The Weeping Elder is the weakest site:** 16.9% overall, and 9% from the Blaine-to-Giovanni leg. Whether that
  is enough for a lake-island landmark reached by boat is a siting question for
  `landmark_trees.py candidates --kind headland`, not something this survey decides.
- **The Sentinel's ring (22 of 24)** still reads once a player reaches the clearing.

## Other visibility claims in `data/`, measured

The same cast (eye 1.62, terrain, and the planned canopy where noted) against every other claim in `data/` that
something can be seen from somewhere. A claim that measured false was corrected in the record.

| Claim | Where recorded | Measured | Record |
| --- | --- | --- | --- |
| Mt Vessu's summit is in view from Surge's town | `towns.json` gym3_town | the summit top is seen from 73 of 144 points on a 5-block grid over the footprint; from the exact centre the line grazes by 0.02 blocks | stands |
| The Glacial Tear is visible from Koga's town | `towns.json` gym5_town | 30 of 213 extent samples | stands |
| The major river's valley is visible from Koga's town | `towns.json` gym5_town | 0 of the 16 trunk course points within 1,200 blocks | **corrected** |
| Route 5 has the major river's valley in view | `routes.json` route_05 | no sampled route point (56) sees any trunk course point | **corrected** |
| The gorge hamlet is visible from the crossing | `towns.json` gorge_hamlet | 0 of 138 route points within 60 blocks of the crossings, terrain only | **corrected** |
| Rest stops are visible from their leg | `SETTLEMENTS.md` | roof +8, over terrain / over canopy: Merian hut 140 / 61 of 355, gorge hamlet 92 / 2 of 209, Tableland stop 144 / 8 of 304, Rift rim post 110 / 2 of 558 | stands, but three are barely visible over the canopy; `SETTLEMENTS.md` now says so |
| Relic Island is visible from the hometown's coast | `towns.json` relic_island | the coast point toward the island sees the islet crown plus an 8-block house | stands |
| The Great Oak is seen from the edge of town | `towns.json` great_oak_pallet | 34 of 34 points on the hometown's east and north edges, over canopy with the glade lowered | stands |
| The array mast is visible from the Nosepass sign site | `landmarks.json` surge_signal_array | see `nosepass_sightline.py`: canopy margin 1.5 at the signs | stands |

## Why the rescale barely touches these sites

This section depends only on the heightmaps, not on the lost counts. The pre-rescale column reads `land_8k_16_sculpted_relief.png` (`fd0db59b…`) under the import line in `data/world.json` at `41c736c^`; the canonical column reads the current heightmap. Both were re-measured for this revision.

**All five trees stand at or below y146.7,** where the rescale curve is flat (gain 1.00 at y145), so their own ground
did not move. The curve rises slowly and then steeply:

| Old ground | New ground | Rise | Local gain |
| ---: | ---: | ---: | ---: |
| y145 | y145.00 | 0.00 | 1.00 |
| y150 | y150.16 | 0.16 | 1.09 |
| y155 | y156.20 | 1.20 | 1.35 |
| y160 | y163.85 | 3.85 | 1.73 |
| y170 | y185.97 | 15.97 | 2.73 |
| y180 | y218.66 | 38.66 | 3.80 |
| y190 | y261.20 | 71.20 | 4.65 |
| y200 | y310.00 | 110.00 | 5.00 |

A line that crosses y148 gains a few hundredths of a block. What predicts a lost sightline is an occluder high on
that curve, and only the Sentinel has one: the massif around its tarn.

| Radius from (3264, 1008) | Highest ground, pre-rescale | Highest ground, canonical heightmap |
| ---: | ---: | ---: |
| 200 | y169.6 | y174.1 |
| 400 | y181.2 | y203.6 |
| 800 | y193.1 | y263.3 |
| 1200 | y194.0 | y280.3 (the Scar pad) |
| 1600 | y200.0 | y300.0 |

The Sentinel's crown is y204.7, so risen ground 800 blocks out stands 60 blocks over it. Its surviving lines come
in over the low corridor from `gym3→gym4`. If a future change is costed, cost the height of the binding occluder,
not the count of lines crossing y145.

## Limitations

- **This is a heightmap survey, not a world survey.** It uses the planned canopy from the paint maps, not the
  WorldPainter project's placed objects (the project records 77,750; this paint plans 77,307) or the exported
  world. Nothing was read from `cobblers-10240`.
- **Leaves count as solid** and crown tops are the object heights in the library, not what WorldPainter picks per
  variant at export.
- **The built elders and the grove are not in the canopy.** They are placed by `tools/elder_trees.py` and
  `tools/tree_grove.py`, not the paint.
