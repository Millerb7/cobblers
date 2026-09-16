# Landmark sightlines after the vertical rescale (2026-09-16)

**Verdict: all five sites stand. The rescale cost two sightlines in total, both of them the Sentinel's, and the
other four surveys came back identical line for line.** The costing in `VERTICAL_RESCALE.md` §7 expected the
Sentinel to be the casualty. It is the casualty, but the bill was 2 lines, not the 56 the risk column implied.

Re-run: `python tools/landmark_trees.py check --source-root "C:/Users/wnd/Documents"` against
`land_8k_16_rescaled_b145.png` (`3eb0edee…`); the recorded prior run was against `land_8k_16_sculpted_relief.png`
(`fd0db59b…`). The prior result was copied aside before the re-run, so old and new are a true diff and not a
memory. Nothing was written to the world, no block was placed, the server was not touched, and
`data/foliage.json` is unchanged. The only repository file the run itself changed is
`derived/foliage/landmark_sightlines.json`, which is its output.

## Before and after

| Landmark | Observers | Seen before | Seen after | Share | Nearest / farthest seen | Change |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `great_oak_pallet` | 37 | 26 | **26** | 70.3% → **70.3%** | 340 / 1157 | **none, bit for bit** |
| `sentinel_spruce_tarn` (legs) | 81 | 27 | **25** | 33.3% → **30.9%** | 399 / 1348 | **−2** |
| `sentinel_spruce_tarn` (ring 60) | 24 | 23 | **23** | 95.8% → **95.8%** | 60 / 60 | none |
| `patriarch_wedge` | 155 | 70 | **70** | 45.2% → **45.2%** | 266 / 2964 | none |
| `cherry_elder_shrew` | 160 | 62 | **62** | 38.8% → **38.8%** | 609 / 2668 | none |
| `weeping_elder_tilpey` | 144 | 37 | **37** | 25.7% → **25.7%** | 765 / 1649 | none |

Ground under every tree is unchanged to two decimals — y103.49, y129.72, y146.67, y143.51, y81.10 — which is the
threshold working: every landmark tree sits at or within two blocks of y145, so none of them moved.

### The same numbers per leg, which is what actually matters

The tool aggregates a landmark's legs into one row, and that hides the real shape of two of these sites. Measured
ray by ray, old heightmap against new:

| Landmark | Leg | Lines | Seen before | Seen after |
| --- | --- | ---: | ---: | ---: |
| `great_oak_pallet` | `hometown→gym1_town` | 37 | 26 (70%) | **26 (70%)** |
| `sentinel_spruce_tarn` | `gym3_town→gym4_town` | 59 | 27 (46%) | **25 (42%)** |
| `sentinel_spruce_tarn` | `gym4_town→gym5_town` | 22 | **0 (0%)** | **0 (0%)** |
| `patriarch_wedge` | `gym8_town→league` | 155 | 70 (45%) | **70 (45%)** |
| `cherry_elder_shrew` | `hometown→gym1_town` | 37 | 22 (59%) | **22 (59%)** |
| `cherry_elder_shrew` | `gym1_town→gym2_town` | 19 | **0 (0%)** | **0 (0%)** |
| `cherry_elder_shrew` | `gym8_town→league` | 104 | 40 (38%) | **40 (38%)** |
| `weeping_elder_tilpey` | `gym5_town→gym6_town` | 41 | 9 (22%) | **9 (22%)** |
| `weeping_elder_tilpey` | `gym6_town→gym7_town` | 39 | 19 (49%) | **19 (49%)** |
| `weeping_elder_tilpey` | `gym7_town→gym8_town` | 64 | 9 (14%) | **9 (14%)** |

**Two legs score zero and always did.** The Sentinel is invisible from all 22 points of `gym4→gym5`, and the
Cherry Elder from all 19 points of `gym1→gym2`. Neither is the rescale's doing — both were zero on the old
heightmap too — but both are in the `seen_from` list, so the aggregate share understates the sites that work and
credits legs that never worked. `sentinel_spruce_tarn` reads 30.9% overall and **42% on the only leg it is
actually seen from.**

## Why the bill was 2 and not 56

**Terrain rise on the sightlines themselves, measured along every ray:**

| Landmark | Highest ground on any of its lines (old) | Most that ground rose |
| --- | ---: | ---: |
| `great_oak_pallet` | y137.9 | **0.00** |
| `patriarch_wedge` | y151.9 | **0.00** |
| `cherry_elder_shrew` | y151.4 | **0.00** |
| `weeping_elder_tilpey` | y157.9 | **0.3** |
| `sentinel_spruce_tarn` | y196.3 | **88.3**, at (1929, 1245) |

Four of the five landmarks have **no ground anywhere on any sightline that rose by as much as a block.** That is
the curve, not luck. The gain is C1 at the threshold, so the first stretch above y145 buys almost nothing:

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

**The costing counted the wrong thing, and said so.** Its column was headed *lines crossing >y145* — a risk count,
every line with any ground above the threshold — and 56 of the Sentinel's 81 qualified. But a line crossing y148
gains 0.03 blocks. The number that predicts a loss is the *height of the binding occluder*, and only the Sentinel
had occluders in the range where the gain is steep. Read that way the table is right about which tree to watch and
wrong by a factor of 28 about the damage. If the costing is repeated for a future change, cost the occluder, not
the crossing.

**And a mountain beside a tree does not hide it.** Around the tarn:

| Radius from (3264, 1008) | Highest ground before | Highest ground after |
| ---: | ---: | ---: |
| 200 | y169.6 | y174.1 |
| 400 | y181.2 | y203.6 |
| 800 | y193.1 | **y263.3** |
| 1200 | y194.0 | y277.4 |
| 1600 | y200.0 | y300.0 |

The y264 the costing worried about is real — it is 800 blocks out. The Sentinel's crown is y204.7 and it is now
ringed by ground 60 blocks over its head. But the `gym3→gym4` leg does not approach across that ground: the lines
that survive run in over the low corridor, where the profile tops out at y136.4 and y162.6 and did not move. Only
the two westernmost observers, at (2084, 1260) and (2132, 1260), look across the risen flank:

| Lost line | Distance | Highest ground on the line before | After |
| --- | ---: | ---: | ---: |
| (2084, 1260) | 1207 | y186.3 | **y231.9** (+45.6) |
| (2132, 1260) | 1160 | y185.4 | **y228.7** (+43.3) |

Those two were going to go and they went. Nothing else on that leg crosses ground high enough to matter.

## Verdict per site

- **`great_oak_pallet` — keep, untouched.** See the confirmation section below.
- **`sentinel_spruce_tarn` — keep. It does not need relocating.** It kept 25 of its 27 lines from the leg it is
  meant to draw people from, 42% of that leg's 59 points, and 23 of 24 points on the 60-block ring around it, so
  it still reads as a landmark both from the route and once you are under it. The site's weakness is older than
  the rescale: it has never been visible from a single point of `gym4→gym5`. If that leg is meant to see it,
  that is a separate design question and a `landmark_trees.py candidates --kind clearing` run, not a rescale
  repair. No candidate sites were generated here, because moving a tree that lost 2 of 27 lines would cost more
  than it buys.
- **`patriarch_wedge` — keep, unchanged.** 70 of 155, identical. Its ground is y146.7, two blocks over the
  threshold, and it rose 0.00 blocks.
- **`cherry_elder_shrew` — keep, unchanged.** 62 of 160, identical.
- **`weeping_elder_tilpey` — keep, unchanged.** 37 of 144, identical. It sits at y81 on a lake island and the
  worst rise anywhere on its 144 lines is 0.3 blocks; the costing's 30 at-risk lines all cross the threshold by a
  few blocks and gain nothing.

## `great_oak_pallet`: confirmed unaffected, three ways

Asked for independently, and it holds.

1. **Its survey row is identical in every field** — 37 observers, 26 visible, share 0.703, nearest 340, farthest
   1157, ground y103.5, crown y143.5. Diffing the old and new result files, the only numbers that differ anywhere
   in the document are the Sentinel's `visible` and `share`.
2. **Ray by ray, 26 of 37 before and the same 26 after** — 0 lost, 0 gained.
3. **The heightmap itself does not change there.** Comparing `land_8k_16_rescaled_b145.png` against
   `land_8k_16_sculpted_relief.png` under its own import line: over x1000–2600, z4400–6000 — a 1600 × 1600 box
   covering the tree, the town and the whole leg — the maximum difference is **0.00 blocks**. The highest ground
   in that box is y148.6 and the highest on any Pallet sightline is y137.9.

Map-wide, the same comparison says the rescale did what it claimed: peak y200.00 → **y309.99**, 1,654,232 columns
up by more than a block, 467,276 up by more than 50, and at or below y145 a maximum difference of **0.004 blocks
with 0 of 62,789,211 columns changing integer elevation.** Whatever else is true, the floor is intact.

## Limitations — what this does not prove

- **This is a heightmap survey, not a world survey.** Every number here is cast over the rescaled heightmap plus
  the planned canopy. Nothing was read out of `cobblers-10240`, and no in-world screenshot backs any of it. The
  re-exported world was **not verified** here.
- **The canopy map is pre-rescale.** `build/paint/canopy.npz` was written on 2026-09-15 from the old terrain and
  stores absolute crown tops, so where the ground rose the stored tops are too low. Measured, this is negligible:
  of 484,506 non-empty canopy cells, **366 (0.08%) sit over ground that rose more than a block**, and **0** are
  buried under the new ground. On risen slopes the check therefore understates tree occlusion very slightly.
- **The old heights were reconstructed, not reloaded.** `land_8k_16_sculpted_relief.png` was read under the
  previous import line (`low_out 10.093458`, `high_out 200`) to get the pre-rescale surface. It reproduces the
  recorded run exactly — same ground heights, same visible counts on four of five trees — which is the check on
  the reconstruction.
- **`data/world.json`'s export block still records the 2026-09-15 export** and `measured_ceiling_y: 201`. Both
  are pre-rescale. Not checked here.
