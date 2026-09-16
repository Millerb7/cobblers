# Raising the mountains: costing a vertical rescale (2026-09-15)

**Verdict: B, a non-linear remap above y145, applied to the heightmap and re-exported. Not A, and not in place.**

The world tops out at y201 and the world tree reaches y535. That is 2.66 times the tallest peak, and it reads
wrong. The target is a peak around y300–320, which puts the tree at about 1.7x.

Three numbers decide this, and none of them is about the mountains.

| | Measured |
| --- | ---: |
| Highest ground under anything built | **y144.4** (an elder tree at 3928, 4272) |
| Highest river bed, lake level or water anywhere | **y127.0** (the ravine-head tarn) |
| The ridge that binds the Pallet → world tree sightline | **y139.0** at (1752, 3684) |

Everything that has been built, planned, graded or sighted sits below y145. The top **9.34% of land** sits above
it. So the whole rescale can be confined to ground nobody has touched — and option A, which stretches every
elevation including sea level's neighbours, moves all of it for no design gain.

Nothing measured here was changed. No file was re-exported, no block was placed, the server was not stopped.

## 1. What the terrain actually is

From `land_8k_16_sculpted_relief.png` (`fd0db59b…`, 8192², 16-bit) at the current import line.

| | |
| --- | ---: |
| Land columns (above y62) | 46,252,012 — **68.92%** of the map |
| Land elevation, mean | y111.99 |
| p25 / p50 / p75 | y95.3 / **y111.8** / y127.6 |
| p90 / p95 / p99 | **y144.1** / y155.1 / y187.3 |
| p99.9 / max | y198.2 / **y200.0** |

**The maximum is a clamp, not a mountain.** `import.high_in` is 0.996078431, i.e. sample 65278, and everything
above it is flattened to y200. The source's own maximum is sample 65532, which the line would put at y200.739 —
which is why the world measures y201 and `world.json` records `measured_ceiling_y: 201`. The clipped plateau is
**20,561 columns**, 0.044% of land. There is 0.74 blocks of real relief hiding above the clamp and no more: no
pixel in the file is at full scale. **Unclamping recovers nothing.** The summits are genuinely flat.

Those 20,561 columns sit in three places:

| Where | Columns at y200 |
| --- | ---: |
| **Frostpeak Point**, x512–1023 z0–511 | 9,898 |
| **The Craters**, x5632–6655 z4608–5631 | 8,302 |
| **Tri Peaks**, x1536–2047 z512–1023 | 595 |

**Land area above each candidate threshold.** This is the dial the whole decision turns on.

| Above | Columns | km² | Share of land |
| ---: | ---: | ---: | ---: |
| y120 | 16,439,654 | 16.44 | 35.54% |
| y130 | 10,322,354 | 10.32 | 22.32% |
| y135 | 8,113,514 | 8.11 | 17.54% |
| y140 | 6,020,747 | 6.02 | 13.02% |
| **y145** | **4,319,653** | **4.32** | **9.34%** |
| y150 | 3,030,603 | 3.03 | 6.55% |
| y160 | 1,793,613 | 1.79 | 3.88% |
| y180 | 730,539 | 0.73 | 1.58% |
| y190 | 330,436 | 0.33 | 0.71% |

The land elevation histogram peaks in the y110–120 bin (17.59% of land) and falls away steadily above it. There is
no natural break in the distribution to hang a threshold on. The threshold has to come from the content.

## 2. Option A: full re-import at a new linear mapping

### The two-point fit, and why `min_y` goes negative

The current line is `y = 10.093458 + (frac / 0.996078431) × 189.906542`, i.e. **190.654206 blocks per unit
fraction**. Sea level y62 therefore falls at fraction **0.2722549**, sample **17842.2**.

Holding that sample at y62 while putting the clamp at y315 fixes both ends of the new line:

```
b = (315 − 62) / (0.996078431 − 0.2722549) = 349.5327 blocks per unit fraction
a = 62 − b × 0.2722549 = −33.162
```

so `import.low_out` becomes **−33.162** and `high_out` becomes **315**, and in terms of the elevations we already
have:

> **y′ = 1.833333 · y − 51.666667**   (exactly 11/6 · y − 155/3)

Every land elevation is stretched by **1.8333x about sea level**. The sea floor goes with it.

| Now | Under A | Change |
| ---: | ---: | ---: |
| y10.09 (deepest seabed) | **y−33.16** | −43.3 |
| y62 (sea level, held) | y62.0 | 0 |
| y70 shore | y76.7 | **+6.7** |
| y100 hill | y131.7 | **+31.7** |
| y118 town | y164.7 | **+46.7** |
| y139 (the Pallet ridge) | y203.2 | +64.2 |
| y160 ridge | y241.7 | **+81.7** |
| y201 peak | **y316.8** | +115.8 |

**The sea floor.** The flat margin seabed inside the border drops from y10 to y−33, giving 95 blocks of water to
sea level, and 31 blocks of rock down to bedrock at y−64. That is legal under `cobblers_height` (y−64..y575) but
it doubles ocean depth everywhere and leaves the deep seabed in permanent darkness. 22.6 million columns below sea
level all move.

**Not doing the two-point fit is worse.** Setting `high_out` to 315 and leaving `low_out` at 10.093458 gives a
multiplier of 1.6056, which puts today's y62 at **y93.4**. Sea level is an absolute Y and does not move, so the
coastline migrates out to whatever used to be **y42.4**. Land goes from 68.92% to **78.05%** of the map —
**6,123,801 columns of seabed become land**. Every coast, every beach, every shore material, every harbour and the
whole ocean plan in `OCEAN.md` is destroyed. The two-point fit is not optional.

### What A breaks, beyond the arithmetic

**The world tree goes over the build limit.** Foothill Woods ground y116 → **y161.0**. The tree is built blocks,
not terrain: it is re-placed by `tree_grove.py` at whatever ground it finds, and it is 418 blocks tall (419 from
ground to crown top). 161 + 419 = **y580**, against a build limit of **y575**. **Over by 5.** A forces one of:
another `cobblers_height` raise, a shorter tree, or a lower site. None of those is free — `BUILT.md` records that
the first limb storey is at +56 specifically to clear the giants below it, so the tree's proportions are not a
free parameter.

**The cavern has to be redesigned, not just rebuilt.**

| | Now | Under A |
| --- | ---: | ---: |
| Surface over the chamber (min/median/max) | 95.9 / 102.5 / 134.7 | **124.1 / 136.3 / 195.3** |
| Ceiling (`ground − 24`) | 71.9 / 78.5 / 110.7 | 100.1 / 112.3 / 171.3 |
| Floor | y22–52, median 27 | unchanged — the floor is set by the **lava field at y15 and below**, not by the surface |
| Headroom, median | 51.5 | **85.3** |
| Excavated | 1,940,587 | **≈3.2M** (×1.66) |

The chamber's proportions — "min 25, median 49, max 85", the reason the rebuild reads as a cave and not a lid —
become "min ~59, median ~85". That is a different room.

**The tunnel goes illegal.** Mouth ground y119.1 → y166.7; the arrival stays at y26 because the floor does. The
drop goes from 99 to 140.7 over the same 404 blocks: **grade 0.245 → 0.348**, against a 0.25 limit the generator
now refuses to exceed. Holding 0.25 needs **563 blocks, +39%**, and a re-route.

**Every river must be re-graded.** All 9 lakes, all 12 graded courses and all their beds are between y53 and y127
today and every one of them moves: lake Tilpey y77 → y89.5, the tarn y127 → y181.2, the major river trunk bed
y68–101 → y73–133. The monotonic-bed rule survives a linear stretch mathematically, but the cut channels, the
catchment-sized widths and the "min_worst_cut" figures are all re-derived from block depths that have changed, so
`grade_rivers.py plan` and `cut` both run again and `rivers_bed_check` is re-measured from scratch.

**Every landmark tree moves**: Great Oak +34.6, Sentinel +56.4, Patriarch +70.6, Cherry Elder +67.9, Weeping Elder
+15.9. All 48 elder trees move. All 30 settlements move. The terrain under every one of the 9 routed legs moves.

**Slopes steepen everywhere, by 1.83x.** Land p99 gradient goes 0.657 → 1.205; the share of land steeper than
45° goes **0.18% → 2.65%**. That is 1.2 million columns that become cliff.

## 3. Option B: a non-linear remap above a threshold

### The curve

Identity below the threshold, a smoothly ramped vertical gain above it:

```
T = 145        threshold          (identity at and below)
W = 55         blend width        (= 200 − T, so the ramp spans the whole band)
G = 5.0        terminal gain
s(y) = clamp((y − T)/W, 0, 1)
g(y) = 1 + (G − 1)(3s² − 2s³)                     the local vertical gain (smoothstep)
y′   = y                                          for y ≤ T
y′   = y + W(G − 1)(s³ − s⁴/2)                    for y > T
```

`y′` is the integral of `g`, so **g(T) = 1 and g′(T) = 0**: the curve is not merely C1 at the join, it is **C2**.
There is no kink to see, and there is no first-derivative step either — the gain eases in from nothing.

The whole family collapses to one identity. With a band of width `D = 200 − T` and a required gain of `Δ` blocks
at the top:

> **Δ = (G − 1)(D − W/2)**

which means the *average* vertical multiplier across the band is `1 + Δ/D`, **no matter what functional form you
choose**. A quadratic, a power law, a spline — all of them must average the same. The only real levers are the
threshold and the target. And note where that leads: push T down to sea level and D becomes 138, giving an average
multiplier of 1.80 — which is option A. **Option A is option B with the threshold at sea level.** The threshold is
the dial between "stretch everything a little" and "stretch a little of it a lot".

### Why T = 145, derived not guessed

Five independent measurements land within 6 blocks of each other:

| Constraint | Measured | Below 145? |
| --- | ---: | :---: |
| 90th percentile of land elevation | y144.14 | yes |
| Highest of the 48 elder trees (`shrew_lake_shores`, 3928/4272) | y144.4 | yes |
| Highest settlement footprint that is not a deliberate summit site (`mining_town`) | y144.3 | yes |
| **The binding occluder on the Pallet → world tree line**, (1752, 3684) | **y139.0** | yes |
| Highest ground over the Displaced City cavern | y134.7 | yes |
| Highest river bed, lake level or water column anywhere | y127.0 | yes |
| Foothill Woods grove and the world tree | y114.9–118.1 | yes |

y145 is the lowest threshold that clears all of them. It is also, to within a block, the p90 of land elevation —
so the curve touches exactly the **top tenth** of the land and nothing else.

### The numbers it produces

G = 5.0 puts the design clamp at **y310** and the real ceiling (the y200.739 columns that render as y201) at
**y313.7**. The world tree's y535 crown is then **1.70x** the tallest peak, against 2.66x today.

| Old | New | Change |
| ---: | ---: | ---: |
| y62 … y144 | unchanged | **0.0** |
| y145 | y145.0 | 0.0 |
| y150 | y150.2 | +0.2 |
| y160 | y163.9 | +3.9 |
| y170 | y186.0 | +16.0 |
| y180 | y218.7 | +38.7 |
| y190 | y261.2 | +71.2 |
| y200 | y310.0 | +110.0 |
| y201 | **y313.7** | +113.7 |

**The cost is steeper mountains, and it is real.** In the band above y145:

| Gradient | Now | Under B |
| --- | ---: | ---: |
| p90 | 0.432 (23.4°) | **1.091 (47.5°)** |
| p99 | 0.748 (36.8°) | **2.593 (68.9°)** |
| Share over 1.0 (≥45°, where whole-block risers stack) | 0.27% | **11.57%** |
| Share over 2.0 | 0.04% | 2.36% |

The top tenth of the land becomes genuinely alpine — about 500,000 columns steeper than 45°. That is the price of
the target, and no curve avoids it; a lower threshold only spreads it over more ground.

### The threshold/width trade, measured

Target 310 at the clamp in every row. `raised` counts columns that move more than half a block.

| T | W | G | p90 slope | p99 slope | ≥45° | Raised columns | Blocks |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **145** | **55** | **5.00** | **1.091** | **2.593** | **11.6%** | **2,689,220** | **67,995,101** |
| 145 | 41.25 | 4.20 | 1.150 | 2.617 | 12.6% | 2,789,525 | 76,954,353 |
| 145 | 27.5 | 3.67 | 1.220 | 2.538 | 14.0% | 2,965,421 | 90,615,864 |
| 140 | 60 | 4.67 | 0.916 | 2.308 | 8.7% | 3,414,133 | 77,370,809 |
| 135 | 65 | 4.39 | 0.778 | 2.079 | 6.7% | 4,750,348 | 88,807,519 |
| 130 | 70 | 4.14 | 0.679 | 1.909 | 5.4% | 6,233,201 | 102,644,504 |
| 120 | 80 | 3.75 | 0.514 | 1.614 | 3.5% | 9,944,649 | 138,972,348 |

**Two results worth reading twice.** First, **a wider blend is strictly better within a threshold**: W = 55 has the
highest terminal gain (5.0) but the *lowest* slope damage and the *fewest* blocks moved, because the gain stays
near 1 through the lower half of the band and only reaches 5.0 at the summits — which are flat plateaus, where a
multiplier meets nothing to multiply. Do not trade W down to make G look smaller.

Second, lowering the threshold buys gentler slopes and costs content: T = 135 halves the ≥45° share but reaches
down past the elder trees, the Pallet occluder and `mining_town`. **T = 145 is where the two curves cross** — it is
the lowest threshold that still clears every piece of authored content.

**There is no free fallback below it.** T = 140/W = 60 cuts the ≥45° share from 11.6% to 8.7%, but it puts two
elder trees (y144.4 and y141.9) and `mining_town`'s footprint (to y144.3) inside the band. They would move by
fractions of a block — the gain at y144.4 with T = 140 is under 0.1 — so it is a small concession rather than a
real cost, but it is a concession, and it turns "nothing authored moves" into "almost nothing authored moves".
Take it only if the flight says the alpine slopes are too harsh.

### What moves under B, and what does not

**Does not move at all — zero blocks, zero re-measurement of position:**

- all 48 elder trees (highest y144.4) and the whole `elder_trees.json` site set;
- the Foothill Woods grove, its 7 giants and 4 elders (y114.9–118.1), and the world tree at (2016, 2280) ground
  y116 — crown stays at **y535**, 40 blocks under the build limit;
- the Displaced City cavern (surface y95.9–134.7), its ceiling line, its floor, its **404-block tunnel at grade
  0.245**, and its mouth at ground y119.1;
- all 9 lakes (levels y77–127) and all 12 graded river courses (beds y53–127), so **no river needs re-grading**;
- the hometown (y109.3–118.1) with its streets, waystone and spawn, and all 9 placed structures;
- 25 of the 30 settlements, including every critical-path gym town except gym 3, and both prepped gym towns;
- 6 of the 9 routed legs entirely;
- four of the five landmark trees, and the fifth only nominally (see below).

**Moves:**

| What | Ground now | Under B | Built? |
| --- | ---: | ---: | --- |
| `gym3_town` (footprint wholly above T) | y186.3–193.6 | centre y190.5 → **y263.5** | no — plan only |
| `the_scar` outpost | y187.5–194.1 | centre y194.0 → **y280.3** | no |
| `frostpeak_shrine` outpost | y198.2–200.0 | centre y200.0 → **y310.0** | no |
| `tableland_stop` rest stop | y157.7–162.4 | centre y160.7 → **y165.2** | no |
| `patriarch_wedge` landmark tree | y146.7 | y146.7 → **y146.706** | yes, painted |
| leg `gym2→gym3` | 15 of 100 points | max y190.7 → y264.4 | no — polyline only |
| leg `gym3→gym4` | 47 of 156 points | max y195.3 → y286.5 | no |
| leg `gym7→gym8` | 48 of 154 points | max y156.6 → y158.4 | no |
| Painted foliage objects | — | **1,802 of 76,400** (2.36%) | yes, painted |

**The patriarch tree moves by six thousandths of a block.** Its ground is y146.7, 1.7 blocks into the band, and
because g′(T) = 0 the gain there is **0.0064**; its glade spans y142.8–148.0, where the largest gain anywhere is
0.035. That is the C2 join paying for itself: a curve that merely matched slopes at the join would have lifted the
tree by a block or more.

**Not one moved thing has been built.** gym 3, the Scar, Frostpeak Shrine and Tableland Stop are `status:
proposed` in `towns.json`, which itself says *"Nothing is built."* The three legs are planned polylines, not roads.
The only *built* content the curve reaches is 1,802 painted trees and one painted landmark tree that moves by a
centimetre.

## 4. What a re-export destroys

Both options need one. Option A needs it because the heightmap import line changes; option B needs it because the
curve has to be baked into a derived heightmap (it is non-linear, so it cannot be expressed as WorldPainter import
levels) and because the elevation-keyed paint — frost, scree bands, biome masks — is wrong above the threshold
either way.

`tools/reexport.py` writes a **new world folder** and carries only seven `level.dat` keys (`WorldGenSettings`,
`DataPacks`, `GameRules`, `Difficulty`, `DifficultyLocked`, `GameType`, `allowCommands`, `hardcore`). Everything
else in `cobblers-10240/` is left behind.

### Two exports of the same terrain are not the same world. Verified here.

`TOWN_ITERATION.md` §1 records this from an 8-block ring. It was re-measured for this note on whole chunks, between
the sculpt export (before the town was copied in) and the relief export, at Pallet Meadows — where the relief pass
did not touch the heightmap at all, so the surface is identical:

| Chunk | Cells compared | Differing | Below y60 | At/above y60 |
| --- | ---: | ---: | ---: | ---: |
| `r.2.9` (22, 23) | 49,152 | **6,494 (13.21%)** | 4,422 | 2,072 |
| `r.2.10` (22, 0) | 49,152 | **7,900 (16.07%)** | 5,401 | 2,499 |

The differences are `stone↔dirt` (2,871 and 2,379), `deepslate↔gravel`, `gravel↔diorite`, `coal_ore↔stone`,
`dirt↔granite` — the substrate mix and the Resources ore field, re-rolled per export and symmetric in both
directions. **This is worse than the record said** (6.3% in the ring; 13–16% in whole chunks). The consequence is
unchanged and decisive: **cross-world chunk copying always seams, so nothing is carried across — everything is
re-placed from its tool.**

### The rebuild list, and whether each piece is recoverable

| What | Blocks | Tool | Recoverable? |
| --- | ---: | --- | --- |
| Displaced City cavern | 1,940,587 | `tools/cavern_plan.py` → 9 functions (`00_seal`…`60_biome`, 46,871 commands) | **yes**, but the plan is read from the *live world's* ground and lava field, so it is re-planned, not replayed |
| World tree | 1,264,724 | `tools/tree_grove.py` → 4 `fill_runs` functions, 118,234 commands | **yes, byte-identically** — geometry is seeded from sha256 of its name, and two runs were proved identical |
| Foothill Woods grove (7 giants, 4 elders) | — | `tree_grove.py` | **yes** |
| 48 elder trees over 20 sub-regions | — | `tools/elder_trees.py` → `build/elders/elders.mcfunction` | **yes**; sites read the live world's ground, which B does not change |
| Hometown (town + 9 structures + waystone + spawn) | — | `tools/place_town.py` → `build/datapacks/cobblers_towns/…/hometown.mcfunction` | **yes** — it was re-placed, not copied, for the creek export: 0 gaps in 36 corners and 1,670 columns |
| Gym 1 and gym 2 town prep | — | `tools/town_plan.py` → `prep_gym1_town.mcfunction` (17,938 B), `prep_gym2_town.mcfunction` (8,893 B) | **yes** |
| `cobblers_worldtree` datapack (10.6 MB of mcfunction) | — | lives **inside the world folder**, not in the repo | **yes**, regenerable — but copy it out first or it goes with the world |
| `cobblers_height` (y−64..y575) | — | `modpack/datapacks/cobblers_height` | **yes**, it is in the repo |
| Distant Horizons LOD (608 MB) | — | `dh pregen …` | **yes**, 7–14 minutes |
| `data/waystones.dat` | — | re-registered on placement | yes |
| Player data (1 account: inventory, Pokédex, PC store, TM moves, CobbleDollars, advancements, stats) | — | none | **no** — it must be copied across by hand, or it is gone |

### Is anything hand-made and therefore unrecoverable?

**No. This is the finding that makes a re-export acceptable, and it was checked, not assumed.**

Every block-state palette in all **484 region files** was scanned for blocks a WorldPainter terrain export and its
foliage objects would never place — lanterns, chains, paths, stone brick, planks, stairs, slabs, doors, beds,
chests, signs, waystones, concrete. Every chunk that contains one falls inside a tool-built footprint:

| Block | Cavern + tunnel | Hometown | Gym 1 prep | Unexplained |
| --- | ---: | ---: | ---: | ---: |
| `lantern` | 53 + 16 | 13 | — | **0** |
| `chain` | 42 | 2 | — | **0** |
| `dirt_path` | — | 30 + 1 | — | **0** |
| `stone_bricks` | — | 3 | 12 | **0** |
| `polished_andesite` | — | 2 | 22 | **0** |
| `chest`, `bookshelf`, `bed`, `furnace`, `barrel`, `waystone`, concrete, stairs, slabs | — | all | — | **0** |

The 24 chunks that first read as unexplained are all at x3024–3136, z1568–1700 — the **cavern tunnel**, whose mouth
is at (3035, 125, 1700), outside the 200×200 chamber box; and one `dirt_path` chunk at (1456, 5152), which is
`route_north` leaving the hometown. **Nothing man-made exists anywhere else in the world.**

Corroborating this: `axiom` appears in `latest.log` only in four mod-loading lines, never in an operation.
`BUILT.md`'s "Axiom in game has not been used yet" holds.

**One caveat.** The re-planned pieces are reproducible but not identical. `cavern_plan.py` reads the live ground
*and the lava field* — and the lava field is re-rolled by the export, so the floor that currently bottoms at y22
with "6 blocks of rock over the highest lava cell" is re-derived and may sit a block or two differently. That is a
re-run and a re-check, not a loss.

## 5. Does option B need a re-export? The in-place arithmetic

The alternative is to leave the world alone and raise the terrain columns in place with `fill`. **Nothing built is
above y145**, so unlike A this operation would not touch a single authored block. The arithmetic:

| | |
| --- | ---: |
| Columns raised by more than half a block | **2,689,220** (4.01% of the map, 2.69 km²) |
| Blocks to add | **67,995,101** |
| Mean rise on a raised column | 24.8 blocks; max 110 |
| Columns raised more than 50 blocks | 593,978 |
| Chunks touched | 11,289 |
| Region files touched | 38 of 484 |
| `fill` commands (one vertical run per column) | **2,689,220** |
| Functions needed at `maxCommandChainLength` 65536 | **42** |
| `forceload` boxes needed (256-chunk cap) | ~45, run in sequence |

For scale: the cavern moved **1.94M** blocks in 11,705 excavate commands, and the world tree **1.26M** in 118,234.
This is **35 times the cavern's block count** and **23 times the world tree's command count.**

**It is arithmetically tractable and qualitatively wrong.** What 68M blocks of stone fill produces is a bare stone
shell over the old ground. Everything the old surface carried is buried under it:

- **1,802 painted foliage objects** stand on ground above y145 and would be entombed;
- **1,642,342 frost/snow columns** are above y145, painted at the old surface — the snow line ends up 100 blocks
  below the summits;
- scree bands, shore and slope materials, and the per-column biome are all keyed to the old elevation;
- 2,689,220 surface caps would have to be re-laid with the right material to make it look like ground at all.

So the honest comparison is not "68M blocks versus a re-export". It is **68M blocks plus a full hand-rolled
surface re-dress, versus a re-export in which WorldPainter re-dresses the surface for free and the rebuild is
1.94M + 1.26M + the groves and the town, about 3.5M blocks of scripted re-runs that have all been run once
already.** The re-export moves roughly **20x fewer blocks** and gets a correct result.

**In place is the answer that saves everything only if the surface does not matter. It does.**

For completeness, the same operation under option A: **66,450,508 columns change — 99.02% of the map — and 2.49
billion block-moves.** Option A in place is absurd and is not costed further.

## 6. What has to be re-measured

**Under B.** Everything in the band, and nothing below it.

| Check | Current acceptance | Under B |
| --- | --- | --- |
| Cavern: ≥24 blocks of rock over the ceiling | 24 min, 31 median | geometry unchanged, but **re-verify** — the substrate and the 884 air cells in the y32–72 band are re-rolled |
| Cavern floor over lava | 4,203 lava cells, floor y22 leaves 6 blocks | **re-derive**: the lava field is re-rolled |
| Tunnel grade | 0.245 against 0.25 | **unchanged**; re-verify after rebuild |
| River beds decrease monotonically | 508 stations, 0 rises | **unchanged** (all beds ≤ y127); re-run `rivers_bed_check` as a cheap confirmation |
| Lake levels and freeboard | 9 lakes, y77–127 | **unchanged** |
| Town street grades, gym lot at y141 | 0 solid blocks 2 above any street | **unchanged** — no built town is above y145 |
| Terrace treads and tread CV | median tread 3.72, CV median 0.249 | **invalid in the band**; treads there compress by up to 5x. Note these were last measured on `924253ad…`, **two heightmaps ago** — they are already stale |
| `max_neighbour_step_blocks` | 3.77 | **must be re-measured**; it rises with the gain in the band |
| Region measured blocks (slope/flat shares) | `regions.json` `measured` | **re-run `region_measure.py`** for the four alpine regions |
| Spawn-tag paint shares | 98.85% / 98.17% inside the Craters | **re-run**: the Craters hold 8,302 of the clipped summit columns |
| Paint maps (frost, scree, biome bands) | — | **must be regenerated**: every band is elevation-keyed |
| Heightmap integrity | 0 tears, 0.39% multiples of 257, 0 duplicate rows | **re-run `heightmap_check.py`** on the new derived PNG |
| Site search for the 4 alpine settlements | largest square, slope < 8° | **re-run `find_sites.py`** — their footprints now sit on 5x steeper ground |
| Routing for 3 legs | slope-weighted | **re-run `critical_legs.py`** |

**Under A, add:** every one of the above plus the river plan and cut, every lake, every settlement footprint, all
48 elder sites, all 5 landmark trees, the whole coast and ocean plan, the cavern design (not just its check), the
tunnel route, and the world tree's height or the build limit.

## 7. Sightlines

Taller mountains are seen further and hide more. Both effects need checking, and B's threshold was chosen so that
the one line that matters today does not move at all.

**The Pallet composition line, measured on the terrain profile.** Observer at the town exit (1461, 5226), eye
y119.31; target the world tree at (2016, 2280); 2,998 sampled points over 2,997.8 blocks.

| | Now | Option A | Option B |
| --- | ---: | ---: | ---: |
| Eye | y119.31 | y165.72 | **y119.31** |
| Binding occluder | (1752, 3684) y139.0, 1,569 out | same point, **y203.1** | same point, **y139.0** |
| Required height at the tree | y156.8 | **y237.1** | **y156.8** |
| Tree top | y535 | y580 (rebuilt at ground y161) | y535 |
| Clearance | 378.2 | 342.9 — **but y580 is 5 blocks over the y575 limit** | **378.2** |

**The entire profile maxes at y139.0. Not one of its 2,998 points is above y145.** Under option B this sightline is
unchanged bit for bit. That is the strongest single argument for putting the threshold at 145 rather than lower:
at T = 135 the ridge rises and the view has to be re-proved; at T = 145 it cannot change.

**The landmark-tree survey (`derived/foliage/landmark_sightlines.json`, `landmark_trees.py check`) does need
rechecking, selectively.** Counting observer lines whose terrain profile crosses above y145:

| Landmark | Observers | Visible now | Lines crossing >y145 | Verdict under B |
| --- | ---: | ---: | ---: | --- |
| `great_oak_pallet` | 37 | 26 | **0** | **untouched** — highest ground on any line is y138.7 |
| `cherry_elder_shrew` | 160 | 62 | 2 | re-run, expect no change |
| `patriarch_wedge` | 155 | 70 | 7 | re-run |
| `weeping_elder_tilpey` | 144 | 37 | 30 | re-run |
| `sentinel_spruce_tarn` | 81 | 27 | **56** | **re-run and expect a loss** |

The Sentinel is the casualty to watch. Its ground is y129.7 and does not move, so its crown stays at y204.7 —
while the mountains it is seen across rise to y264 and beyond. It is likely to lose visibility from the
`gym3→gym4` leg. Under option A all five surveys are void, because every ground and every eye moves.

## 8. Recommendation

**Do B. Bake the curve into a derived heightmap, re-export, re-run the build tools.**

| | A: linear refit | B: remap above y145 |
| --- | --- | --- |
| Peak | y316.8 | **y313.7** |
| Tree : peak | 1.83x, **and illegal by 5 blocks** | **1.70x, legal with 40 to spare** |
| Land that moves | **100%** | **9.34%**, none of it built |
| Sea floor | **−43 blocks**, deepest to y−33 | unchanged |
| Coastline | unchanged *if* the two-point fit is done; destroyed if not | unchanged, unconditionally |
| Rivers and lakes | all 21 re-graded and re-cut | **none** |
| Cavern | redesigned; tunnel re-routed +39% | **unchanged** |
| World tree | **breaks the build limit** | unchanged |
| Pallet sightline | requirement y156.8 → y237.1 | **identical** |
| Landmark surveys | all 5 void | 1 of 5 at real risk |
| Alpine slopes | +83% everywhere | +5x on the top tenth |
| Re-export | required | required |
| Rebuild after re-export | same list, against **different ground** | same list, against **identical ground** |

The two options cost the same re-export and the same rebuild. They differ in what the rebuild lands on. Under B
every tool re-runs against ground it has already been calibrated to, so the cavern plan, the elder sites, the town
seating and the grove come back as they were; the re-run is a re-run. Under A every one of them is a fresh design
problem, and one of them — the world tree against y575 — has no solution that does not change something the design
already settled.

**The single thing B buys that A cannot: option A's gain is spread over ground that is already the right height.
Nobody complained that the shore is too low.**

### Sequence, if approved

1. Derive `land_8k_16_sculpted_relief_raised.png` from `fd0db59b…` by applying the curve; record it in
   `world.json` `heightmap.derived_from` with the previous sha in `previous_sha256`.
2. Set `import.high_out` to 310 and `vertical.max_y` to 310. `low_out`, `low_in`, `high_in`, `water_level` and
   `sea_level` are **unchanged**.
3. `heightmap_check.py`, then re-run `region_measure.py`, `cell_stats.py`, `terrace_measure.py`, `slope_masks.py`,
   `find_sites.py` (4 alpine sites), `critical_legs.py` (3 legs).
4. `paint_maps.py` — mandatory, the frost/scree/biome bands are elevation-keyed.
5. Copy `cobblers-10240/datapacks/cobblers_worldtree/` and the player data out of the world **before** retiring it.
6. Retire the world, `reexport.py` (last export: 2,255 s), carry the seed, confirm `seed_match`.
7. Re-place: hometown, gym 1 and gym 2 prep, cavern, world tree and grove, 48 elders. Re-check each against the
   acceptance numbers in §6.
8. `dh pregen`, move the client LOD cache aside, clear stale waystone entries.

## Not verified

- **The exact WorldPainter import arithmetic for the new line.** `world.json` records that WorldPainter takes only
  whole-number *world* levels, which is why 10.093458 was written as image level −32.125 → y10. The same trick
  should carry `high_out: 310`, but it was not tried.
- **The slope figures are first-order.** New gradient = `g(h) × old gradient`. That is exact for a smooth surface
  and approximate where the gain changes fast across one column. The direction and magnitude are right; the exact
  p99 is not.
- **Nothing was rendered.** Whether a top-tenth band at 47° p90 reads as "mountains" or as "a wall" is a flight
  question, not a measurement.
- **Option A's cavern excavation figure (≈3.2M)** is scaled from the median headroom ratio, not re-planned.
- **`minecraft:light` still appears in the palettes of 20 chunks** around the cavern and tunnel. `BUILT.md` reports
  0 live light blocks in the chamber and a palette entry survives block removal, so the two are consistent — but
  this was not re-verified at block level.
- **Pre-existing, unrelated:** `relic_island` is recorded in `towns.json` with centre (1092, 5532) at ground
  **y35.3**, footprint y35.0–36.0 — 27 blocks *below* sea level. On the current heightmap that outpost is seabed,
  not an island. It is a survivor of the deleted EXP-001 `f4-local-1000` world (see
  `events/F4_RELIC_ISLAND_ASH_HOUSE.md`). Neither option makes it worse; it needs re-siting regardless.
