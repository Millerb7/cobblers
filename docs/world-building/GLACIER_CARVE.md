# Glacier Valley carve specification

> **Superseded 2026-09-14.** The glacier has since been hand-carved as the Glacial Tear; it measures as a continuous U-shaped trough ([`TERRAIN_2026-09-14.md`](TERRAIN_2026-09-14.md) §3). This spec is kept for history.

**Status: planned.** This is the spec for a WorldPainter hand-carve after region
assignment. No terrain has been edited. The machine-readable copy is the `carve_spec`
block of `glacier_corridor` in `data/landmarks.json`; where the two differ, fix one of
them, because the landmark is what tools read.

All distances `d` are blocks along the trough axis from the head, following
`glacier_corridor.trough` in `data/landmarks.json`.

## Where it is

The drawn outline is the ground truth. It runs **north-west to south-east**, from the
Northern Range's south-east flank to the lake beside the rift's north-east arm:
x3128-6504, z1680-4192.

The written brief said the glacier ran north-east from the rift, with the lake at its
south-west end, at x4800-7000, z2400-4400. That box covers only the lower half of the
drawing, and the direction is reversed. The drawing wins, as the brief instructed. The
floor confirms which end is which: it falls from y99 at the north-west end to y44.7 in
the lake.

| Feature | Location | State |
| --- | --- | --- |
| Head | (3268, 1908), against the range, headwall rims y155-183 | built: a hollow at y99 |
| Upper trough | d0-1700, bearing east-south-east | partial |
| Saddle | d1792, (4784, 2719), floor y107, 4 blocks deep | the trough nearly disappears here |
| Lower trough | d1900-3200, bearing south-east | partial: the flat floor at y67-78 |
| Meltwater lake | centroid (6025, 3810), 0.22 km² below y62, floor y44.5 | built: an enclosed basin |
| Terminal moraine | crest arc (6291, 4099) → (6425, 3945) → (6489, 3751) | planned: no ridge exists |
| Meltwater river | (6448, 3944) → (6784, 3944) → (6920, 3960), 480 blocks to the east sea | planned: the lake has no outlet |

## What is there now

`tools/cross_section.py --landmark glacier_corridor --axis trough`: 32 stations every
128 blocks, transects 1,600 blocks wide.

| Measure | Now |
| --- | --- |
| Shapes | U 10, V 7, flat-floored 3, asymmetric 11, none 1 |
| Wall angle, median (range) | 5.5° (1.4-18.9°) |
| Depth below the lower rim, median (range) | 19.6 (4.0-64.4) |
| Floor width, median | 160 |
| Rim to rim, median | 548 |
| Long profile | 19 downhill steps, 11 uphill |

Selected stations:

| d | Where | Floor | Rims | Depth | Walls | Shape |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | head | 99.0 | 157 / 155 | 56 | 5.5 / 18.9° | asymmetric |
| 512 | upper trough | 85.8 | 108 / 110 | 22 | 4.7 / 3.7° | V |
| 1024 | upper trough | 93.6 | 105 / 127 | 11 | 4.7 / 4.1° | asymmetric |
| 1792 | saddle | 106.7 | 111 / 120 | 4 | none | none |
| 2688 | lower flats | 79.9 | 108 / 104 | 24 | 11.6 / 12.8° | flat-floored |
| 3072 | above the lake | 66.9 | 102 / 93 | 26 | 9.0 / 2.1° | U |
| 3584 | lake | 44.7 | 83 / 69 | 24 | 3.3 / 8.8° | U |
| 3968 | terminus | 70.7 | 109 / 84 | 13 | 4.5 / 3.1° | asymmetric |

It is a shallow, broad depression with gentle sides, not a trough. Its rims sit 300 or
more blocks out, across slopes of about 5°.

## Target

### Long profile of the floor

| d | Floor y | Shoulder y |
| --- | --- | --- |
| 0 (head) | 100 | 145 |
| 1400 | 90 | 128 |
| 2300 | 84 | 120 |
| 3050 | 66 | 104 |
| 3200 | 58 | — |
| 3700 | 58 | — |
| 3760 (lake outlet) | 62 | 94 |

Between the stations the floor and shoulders are interpolated linearly. The lake basin
already lies below its target floor, so the carve leaves it alone.

### Cross-section

- **Floor:** 120 blocks flat, then a 70-block parabolic toe on each side.
- **Walls:** 34° from the toe up to the shoulder height.
- **Beyond the shoulder:** a 150-block ramp that only raises ground back down to the existing
  terrain.
- **Carving:** ground above the target is cut. Within the shoulder band, ground below the
  shoulder is filled up to it.
- **Head:** a cirque bowl, floor y100, rising into the range. Existing ground at the head is
  y99, so the floor is left as it is.
- **Terminus:** the lake at y62 held behind the moraine.

### Moraine

| | |
| --- | --- |
| Crest height | y78-82 |
| Base width | 80-120 blocks |
| Outer face (downstream) | 20° |
| Inner face (lake side) | 28° |
| Material | gravel, cobble, coarse dirt, boulders |
| Breach | 16 blocks wide at (6448, 3944), bed y62 |

### Meltwater river

| | |
| --- | --- |
| Bed | y61-62 |
| Width | 8-16 blocks |
| Deepest cut | 14 blocks; the route crosses nothing above y75 |
| Length | 480 blocks, to open sea at (6920, 3960) |

## What the spec does to the terrain

The spec was applied to the heightmap in memory only; nothing was written back. The script
is not committed.

| | Lowered | Raised |
| --- | --- | --- |
| Area | 0.53 km² | 1.87 km² |
| Volume | 5.9 million blocks | 24.1 million blocks |
| Typical depth | median 9.7, 95th percentile 24.4 | 95th percentile 34.9 |
| Deepest | 28.6, at (4964, 2989), the saddle | 51.4 |

Re-measured with the same tool afterwards:

| Measure | Now | After the carve |
| --- | --- | --- |
| Shapes | U 10, V 7, flat 3, asym 11, none 1 | flat-floored 30, V 1, asymmetric 1 |
| Wall angle, median | 5.5° | 29.0° |
| Depth, median | 19.6 | 38.1 |
| Floor width, median | 160 | 180 |
| Rim to rim, median | 548 | 306 |
| Wall curvature exponent b, median | 1.4 | 4.5 |
| Long profile | 19 down, 11 up | 25 down, 3 up |

`cross_section.py` classifies the result as **flat-floored**, not U. Its line between
the two is a floor wider than 40% of the rim-to-rim width. The carved floor is 59% of
it, and the walls are strongly concave (b 4.5), which is a U-trough with a flat
floor. The wide floor is deliberate: it is the only building ground in the valley.

### Why the spec raises ground, not only cuts it

Three variants that only cut were tried first. They lowered the floor by up to 45
blocks and set the walls at 33-38°. The median wall only rose to 7-13°, and 16-17 of the
32 stations still read V or asymmetric. The corridor has no confining walls: above a
carved lower wall, the old 5° slopes continue to the rims. Steep walls need the
shoulders built up.

| Variant | Floor width | Walls | Cut | Fill | Result median wall | Result shapes |
| --- | --- | --- | --- | --- | --- | --- |
| cut only, floor y100→58 | 200 | 33° | 8.1M | 0 | 7.2° | U 7, V 5, flat 8, asym 12 |
| cut only, deeper | 180 | 35° | 12.4M | 0 | 9.8° | U 6, V 4, flat 9, asym 13 |
| cut only, deepest | 160 | 38° | 13.4M | 0 | 12.8° | U 7, V 4, flat 9, asym 12 |
| cut + shoulders | 200 | 34° | 8.4M | 33.1M | 33.4° | flat 30, V 1, asym 1 |
| **cut + shoulders (this spec)** | **120 + toes** | **34°** | **5.9M** | **24.1M** | **29.0°** | **flat 30, V 1, asym 1** |
| cut + shoulders, narrow floor | 40 + toes | 34° | 3.5M | 25.8M | 27.0° | flat 30, V 1, asym 1 |

### Consequences to decide with

1. **Building ground shrinks.**
   - Before the carve, the valley holds the map's largest flat square below y190: 139 blocks
     at (5646, 3302), y75-78. Next are 104 at (5881, 3378) and 103 at (5063, 2724).
   - After the carve, the largest square on the valley floor is 124 blocks at (3543, 2008),
     y97-98, near the head. Next are 122, 122, 104, 102 and 101.
   - The lower-trough flats become a floor sloping from y84 to y66 and lose their largest
     squares.
   - The narrow-floor variant leaves nothing over 54 blocks.
2. **There is no view down the whole valley.**
   - The axis bends about 35° between d900 and d1700.
   - From the head, at eye heights 1.6, 20 and 45 blocks, the lake, the moraine and the lower
     flats are hidden, both before and after the carve.
   - Once the shoulders are raised, the inner shoulder of the bend blocks the view at every
     height tested.
   - Views along the valley exist only within each straight reach. A lake-to-head vista would
     need the bend cut back, which is a design change to the outline.
3. **Snow below the treeline.** The valley floor sits at y58-100 and the walls at up to y145,
   below the y165 treeline. Snow there is a deliberate exception: glacier ice and cold air
   draining from the range.
4. **Water.** WorldPainter fills water wherever terrain lies below the map's water level,
   y62 in `data/world.json`. The floor target stays at or above y62 outside the lake basin,
   so no accidental flooding follows. **Not verified in an export.**

## Acceptance after the carve

1. Re-export the heightmap, update `heightmap.sha256` in `data/world.json`, and rerun the
   section:

   ```bash
   python tools/cross_section.py --source-root <source root> --landmark glacier_corridor --axis trough --sample-step 4 --level 62
   ```

2. The carve passes when:
   - at least 75% of stations are U or flat-floored;
   - the median wall is at least 25°;
   - the median depth is at least 30;
   - no station is `none`;
   - there are at most 4 uphill floor steps outside the lake basin (d3200-3750).
3. When it passes, set `glacier_corridor` to `built`. Once the moraine and river exist, set
   `terminal_moraine` and `meltwater_river` to `built` as well.
