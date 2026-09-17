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

**Observations, not decisions:**
- **No listed leg measures zero** now that the two legs that never saw their tree are gone.
- **The Weeping Elder is no longer a landmark.** It measured 25 of 148 leg points (16.9%; 9% from Blaine to
  Giovanni), and every Lake Tilpey site that measures better (29–38%) is dry shore, which loses the island it exists
  for. It was demoted on 2026-09-16: it still stands, painted on its island with its glade, but makes no viewpoint
  claim and is not an outpost (`data/foliage.json` `landmark: false`). The best of those shore sites, (5216, 5024)
  at 38.5%, is on file in `landmark_candidates` as a possible future Route 8 landmark, not a replacement.
- **The Sentinel's ring (22 of 24)** still reads once a player reaches the clearing.

## Other visibility claims in `data/`, measured

Every claim in the data that something can or cannot be seen from somewhere is now a measured record in
`data/visibility.json`, re-measured by `tools/validate_data.py` (check `visibility`) and refreshed by
`tools/visibility_claims.py --write`. The check fails when a count drifts, when a claim measures false, when the
planned canopy's hash changes, or when the record that states a claim does not cite it as `visibility:<id>`
(and say "fragile" if it is). The table below is that registry at this revision; the validator, not this table,
is the authority.

Three claims measured false and were corrected in their records before the registry existed: the major river from
Koga's town, the major river from Route 5, and the gorge hamlet from the Tilpey crossing. Each now records the
negative, so a future change that makes it visible also fails the check.

| Claim | Surface | Measured | Fragile |
| --- | --- | --- | --- |
| `great_oak_from_route_01`: The Great Oak's crown is seen from the first leg. | canopy | 26 of 42 observer points | no |
| `great_oak_from_hometown_edges`: The Great Oak is seen from the edge of the hometown. | canopy | 34 of 34 observer points | no |
| `sentinel_from_route_04`: The Sentinel's spire shows over the old growth from the Surge-to-Erika leg. | canopy | 34 of 72 observer points | no |
| `sentinel_from_clearing_ring`: The Sentinel reads from the edge of its clearing. | canopy | 22 of 24 observer points | no |
| `patriarch_from_victory_road`: The Patriarch breaks the skyline above Victory Road. | canopy | 58 of 164 observer points | no |
| `cherry_elder_from_route_01`: The Cherry Elder is pink against the plateau from the first leg. | canopy | 25 of 42 observer points | no |
| `cherry_elder_from_victory_road`: The Cherry Elder is seen from Victory Road's climb. | canopy | 46 of 110 observer points | no |
| `mt_vessu_summit_from_surge_town`: Mt Vessu's summit is in view from Surge's town. | terrain | 73 of 144 observer points | no |
| `glacial_tear_from_koga_town`: Part of the Glacial Tear is visible from Koga's town. | terrain | 30 of 213 target samples | no |
| `major_river_not_from_koga_town`: The major river is not visible from Koga's town. | terrain | 0 of 16 target samples | no |
| `major_river_not_from_route_05`: Route 5 does not have the major river in view. | terrain | 0 of 66 observer points | no |
| `gorge_hamlet_not_from_crossing`: The gorge hamlet is not visible from the Tilpey crossing. | terrain | 0 of 41 observer points | no |
| `relic_island_from_hometown_coast`: Relic Island's house is visible from the hometown's coast. | terrain | 1 of 1 observer points | **yes** |
| `array_mast_from_nosepass_signs`: The array mast clears the modelled canopy from the Nosepass signs. | canopy model | margin 4.3 blocks | no |
| `merian_hut_from_its_leg_terrain`: The merian hut is visible from its leg (8-block roofline, over bare terrain). | terrain | 86 of 216 observer points | no |
| `merian_hut_from_its_leg_canopy`: The merian hut is visible from its leg (8-block roofline, over the planned canopy). | canopy | 35 of 216 observer points | no |
| `gorge_hamlet_from_its_leg_terrain`: The gorge hamlet is visible from its leg (8-block roofline, over bare terrain). | terrain | 55 of 129 observer points | no |
| `gorge_hamlet_from_its_leg_canopy`: The gorge hamlet is visible from its leg (8-block roofline, over the planned canopy). | canopy | 1 of 129 observer points | **yes** |
| `tableland_stop_from_its_leg_terrain`: The tableland stop is visible from its leg (8-block roofline, over bare terrain). | terrain | 88 of 191 observer points | no |
| `tableland_stop_from_its_leg_canopy`: The tableland stop is visible from its leg (8-block roofline, over the planned canopy). | canopy | 5 of 191 observer points | **yes** |
| `rift_rim_stop_from_its_leg_terrain`: The rift rim stop is visible from its leg (8-block roofline, over bare terrain). | terrain | 60 of 328 observer points | no |
| `rift_rim_stop_from_its_leg_canopy`: The rift rim stop is visible from its leg (8-block roofline, over the planned canopy). | canopy | 2 of 328 observer points | **yes** |

A claim is fragile when it holds on 10 or fewer points or under 5% of them (a sightline margin: under 2 blocks).
Relic Island's is fragile because it is measured from a single coast point, not because the view is poor.

## Why the rescale barely touches these sites

This section depends only on the heightmaps, not on the lost counts. The pre-rescale column reads `land_8k_16_sculpted_relief.png` (`fd0db59b…`) under the import line in `data/world.json` at `41c736c^`; the canonical column reads the current heightmap. Both were re-measured for this revision.

**All five giants (four landmarks and the demoted Weeping Elder) stand at or below y146.7,** where the rescale curve is flat (gain 1.00 at y145), so their own ground
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
