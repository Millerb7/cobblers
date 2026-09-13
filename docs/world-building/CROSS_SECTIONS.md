# Cross-section report: the glacier corridor and the rift

Measured with `tools/cross_section.py` against `land_8k_16_eroded.png`
(sha256 `526fe220…a860f6`), along the axes stored in `data/landmarks.json`.

All sections use stations every 128 blocks and samples every 4 blocks.

| Feature | Transect width | Floor searched within | Also measured |
| --- | --- | --- | --- |
| Glacier | 1,600 | 800 | width below y62 |
| Rift | 2,400 | 1,200 | width below y62 |

Each axis is the lowest path through the annotated outline.

## How a profile is read

| Term | Meaning |
| --- | --- |
| floor | The lowest ground on the transect near the axis |
| rim | The top of each wall. Walking outward, the wall ends where the ground falls away, or where it flattens below 3° over 48 blocks once half that side's relief has been climbed. A bench partway up a wall does not end it; gently rising country beyond the wall is not part of it. |
| depth | Lower rim minus floor |
| floor width | Width within max(2 blocks, 10% of depth) of the floor |
| rim to rim | Width below the lower rim |
| wall angle | Mean slope between 20% and 80% of the depth |
| b | Exponent of (height above floor / depth) = (distance / half-width)^b. About 1 for a straight V wall, about 2 or more for a U wall |
| shapes | **flat_floored** if the floor is at least 40% of rim to rim; **U** if b ≥ 1.5; otherwise **V**; **asymmetric** if the rims differ by half the higher wall, or the walls by 10° and a factor of 2; **none** if depth < 6 |

The synthetic tests in `tests/test_cross_section.py` check every term against profiles
with known answers.

## Glacier corridor

**Under-carved, not absent.** A trough runs the length of the outline. Per-cell
statistics could not see it, because a 20-block depression spread 550 blocks wide
changes a 1,024-block cell's mean elevation very little.

| Measure | Value |
| --- | --- |
| Axis length | 4,016 blocks, head (3268, 1908) to terminus (6500, 3988) |
| Shapes (32 stations) | U 10, V 7, flat-floored 3, asymmetric 11, none 1 |
| Floor | y44.7 (lake) to y110.1 (below the saddle) |
| Depth, median (range) | 19.6 (4.0-64.4) |
| Floor width, median | 160 |
| Rim to rim, median | 548 |
| Wall angle, median (range) | 5.5° (1.4-18.9°) |
| b, median | 1.4 |
| Long profile | 19 downhill steps, 11 uphill |

**Along the axis:**

- **Head, d0-128:** deep (56-64 blocks) under the range rims. Walls reach 16-19° on one
  side only.
- **Upper trough, d256-1664:** 11-25 blocks deep with 3-10° walls. The floor wanders
  between y86 and y101.
- **Saddle, d1792 at (4784, 2719):** 4 blocks deep, shape none. The glacier is broken in
  two here.
- **Lower trough, d1920-3072:** the floor falls from y110 to y67, 14-26 blocks deep, with
  walls up to 13°. It is widest and flattest at d2688-2816 (floor width 336).
- **Lake basin, d3200-3712:** floor y44.7-58, 19-28 blocks below rims of y69-91.
- **Terminus, d3840-3968:** the floor rises back to y70. There is a lip, but no ridge.

**What a glacier would measure** (a design target, not a Minecraft rule):

- U or flat-floored at most stations;
- walls of 25-35°;
- 30-50 blocks deep;
- a floor falling from head to lake, with at most small steps.

The corridor fails on wall angle, depth and continuity. The carve that closes the gap is
specified in `GLACIER_CARVE.md`.

## Rift

**Wall to wall, the rift is about equally wide everywhere.** Its floor sits at y44-62, a median
52-66 blocks below the rims.

| Arm | Length | Floor | Depth, median | Rim to rim, median (range) | Width below y62, median (range) | Wall, median | Shapes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| North-west arm | 1,365 | 46.0-54.0 | 65.8 | 624 (492-916) | 372 (280-560) | 26.5° | U 4, flat 6, asym 1 |
| West arm | 644 | 47.1-53.4 | 63.4 | 584 (568-628) | 360 (328-372) | 26.9° | U 3, flat 2, asym 1 |
| Trunk | 1,842 | 46.8-61.6 | 60.7 | 536 (492-904) | 160 (40-848) | 33.2° | U 3, flat 8, asym 2, none 2 |
| North-east arm | 419 | 43.6-47.5 | 57.0 | 618 (588-660) | 402 (360-452) | 22.9° | U 1, flat 2, asym 1 |
| South-east arm | 1,635 | 45.3-59.0 | 51.6 | 476 (408-1,292) | 304 (208-704) | 25.5° | U 1, flat 9, asym 3 |

- **Total axis length** is 5,905 blocks, with two junctions: west (2860, 3940) and
  east (4660, 3908).
- **The trunk is the most dramatic section:**
  - its walls are the steepest (median 33°; 32-39° at d512-1280);
  - its rims are the highest (y130-156 at d512-1280);
  - it is the most consistently flat-floored.
- **The two "none" stations** (d1536-1664) are where the transect runs along the east
  junction instead of across a wall.
- **Rim to rim across the trunk centre** (d384-1280) is 508-712 blocks.

### Why it looked widest at the ends and narrowest at D4

**Neither erosion nor the painted width. It was a measurement of the floor's depth.**

1. **The 172-block figure measured the wrong thing.** The previous pass measured how wide
   the ground below y62 is, because it treated the rift as a flooded lake.
   - Across the trunk centre that width is 40-120 blocks.
   - At the arms and junctions it is 280-850.
   - Wall to wall, the trunk centre is 508-712 blocks, the same as the arms (476-624 by
     median).
2. **The trunk floor is shallower than the arms.** It sits at y57-62 against y44-54 in the
   arms, so the strip of ground below y62 is narrow there. The painted outline's width is
   close to uniform; its depth is not. That the trunk was stroked shallower is an
   inference, not something the files record.
3. **It is not erosion.**
   - `land_8k_16_eroded.png` differs from the pre-erosion export `land_8k_16.png` by at most
     0.77 blocks anywhere: 99.9% within 0.25, mean change on land −0.005.
   - No block on the map changed height by one block or more.
   - On both files, floors and depths agree within 0.4 blocks, and widths within one 4-block
     sample.
4. **The rift was added between Gaea and the pre-erosion export.** In `Export.png`, the
   1,024-pixel Gaea output (fitted to block heights, correlation 0.94), the rift axes
   show no rift: depth 3.7-8.6 blocks, shape none or V. The pipeline in `data/world.json`
   runs Gaea → GIMP → TerreSculptor, so the rift was painted in GIMP. The glacier trough
   is faintly present in the Gaea export (median depth 8 blocks) and was deepened in the
   same step.

**The erosion pass did nothing measurable.** If `land_8k_16_eroded.png` was expected to
carry TerreSculptor erosion, it does not. The pinned heightmap is effectively the
pre-erosion export.

### The rift floor above sea level

`data/landmarks.json` makes ground below y62 inside the rift void, never water. Not all
of the rift's low ground is below y62:

| Inside the rift outline | Area | Share |
| --- | --- | --- |
| y40-62: void floor | 1.70 km² | 45% |
| y62-70 | 0.50 km² | 13% |
| y70-80 | 0.28 km² | 8% |
| y80-100 | 0.55 km² | 15% |
| y100-200: upper walls and rim | 0.73 km² | 20% |

**0.78 km² of floor and low shelf lies between y62 and y80** and would render as visible
ground; 29% of the ground between y62 and y75 is under 5°. The flat patches include 84 and 66-block squares at y69-73 near
(4043, 3866). The brief says the floor must never be a visible surface. The floor
treatment therefore has to reach up to about y80: carve it below y62, or cover it with
the same void or light layer.

### Natural descents

**No natural walk-down ramp was found.** No station on any arm has a wall under 12°
with more than 20 blocks of depth. The only two that pass that filter sit at the east
junction, where the transect runs along the trunk instead of across a wall.

Stations are 128 blocks apart, so a ramp narrower than that could fall between them.
Descents should be treated as authored, not found.

## Reproducing

```bash
python tools/cross_section.py --source-root <source root> --landmark glacier_corridor --axis trough --sample-step 4 --level 62
python tools/cross_section.py --source-root <source root> --landmark rift --axis trunk --sample-step 4 --level 62
# likewise --axis west_arm_nw, west_arm_w, east_arm_ne, east_arm_se
```

Output goes to `derived/sections/<landmark>.<axis>.json`, with every station's profile
measurements. The Gaea and pre-erosion comparisons read those two files directly with
the world import mapping. They are provenance, not the pinned heightmap, so they are not
hash-checked, and that script is not committed.
