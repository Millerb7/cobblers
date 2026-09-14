# Sightline report: the annotated landmarks

> **Superseded 2026-09-14.** Computed on the 2026-09-13 terrain and landmark ids (`glacier_corridor`, `northern_range`, ...) that no longer exist in `data/landmarks.json`. `data/checks/sightlines.json` needs its references updated before `tools/sightlines.py --plan` is rerun.

Raycasts from `tools/sightlines.py --plan data/checks/sightlines.json` against
`land_8k_16_eroded.png` (sha256 `526fe220…a860f6`). Every observer and target is a
landmark reference or a measured site; nothing is typed as a coordinate of a feature.

## How to read it

- **Observers** stand at a player's eye height (1.62 blocks) unless marked "rooftop"
  (12 blocks, a 10-block building plus eye height).
- **Hub observers** are each hub region's largest flat site (4°, below y190), not a
  town. No town has been placed.
- **A `landmark*` target** is the whole feature: its outline sampled every 64 blocks
  plus its 40 highest points. It counts as visible if any sample is; the count shows
  how much.
- **A named anchor** is a single point. The four cones and most range summits are clipped
  flat at y200, so their centres are hidden by their own rims from anywhere below. For
  those, the extent result is the one that means something.
- **Terrain only.** No trees, buildings or fog. Distant Horizons renders LODs to 4,096
  blocks with the shipped client config; vanilla chunks are 160 blocks at server view
  distance 10. Beyond that, "visible" means visible as an LOD silhouette.
- **Clearance** is how far the sightline passes above the ground at its closest point. A
  clearance of 0.00-0.15 is a grazing line: one tree or a 1-block terrain change flips it.

## The checks the brief asked for

### Lake to range

From the meltwater lake's east shore (6304, 3880), y64:

| Target | Distance | Result |
| --- | --- | --- |
| Northern Range, whole | 3,471 | visible: 1 of 164 samples, (3632, 1664) |
| B4 east summit, y183 | 3,518 | visible, clearance 0.05 |
| B3 summit, y200 | 4,307 | blocked by y97 ground 1,020 blocks out, (5443, 3334) |
| B2 summit | 5,081 | blocked by y86, 811 blocks out |
| A3 summit | 5,292 | blocked by y94, 1,155 blocks out |
| A1 summit | 6,529 | blocked by y81, 812 blocks out |

**Barely.** One point of the range, the B4 east summit, grazes into view over the lake's
own north-west rim. The main massif is hidden behind the ground 800-1,150 blocks up the
valley.

### Glacier head down the valley

From the glacier head (3268, 1908), y101: the lake, the moraine site, the lower flats and
the saddle are all **blocked**. The blockers are y90-104 ground 900-1,100 blocks out,
where the corridor bends. A simulation of the planned carve keeps them blocked at eye
heights 1.6, 20 and 45 blocks; see `GLACIER_CARVE.md`.

### Downs to cones

The brief's "Downs" was one region in the previous plan. The Glacier Valley has since
split it three ways, so all three parts were checked.

| Observer | Region now | Cones, whole | Best named cone |
| --- | --- | --- | --- |
| (6446, 3527), y93, 107-block site | Eastern Downs | visible at 1,178: 17 of 129 samples | all four centres blocked: three by their own flat tops (y194-199, 12-90 blocks short), cone 2 by cone 1's flank |
| (6805, 4407), y109, 104-block site | Stillwater Basin | visible at 355: 6 of 129 samples | all four blocked: three by their own tops, cone 2 by cone 1's flank |
| (3149, 2768), y125, 106-block site | Rim Uplands | **blocked at 3,775**: 0 of 129 samples, by the rift's near, north rim (y145-147 near (3883, 3587)) | blocked |

From the east, the cones show as flat-topped silhouettes. From the Rim Uplands on the
far side of the rift they are hidden, except from a rooftop, where 3 of 129 samples
graze into view.

### Rift rim to opposite rim

| Across | From → to | Distance | Result |
| --- | --- | --- | --- |
| Trunk, d1024 | (3877, 3708) y149 → (3877, 4360) y147 | 624 | visible, clearance 0.15 |
| North-west arm, d512 | (2863, 3104) → (1820, 3314) y128 | 724 | visible, clearance 0.03 |
| South-east arm, d768 | (5094, 4378) → (4477, 4906) y121 | 524 | blocked, 2 blocks before the target at its own rim edge: effectively visible |

Across every measured section the far wall is in view. With the floor below fog, the
view across is wall to wall.

### Each hub to its nearest landmark

"Nearest" is by distance to the landmark's outline.

| Hub (site) | Nearest landmarks | Ground eye | Rooftop eye |
| --- | --- | --- | --- |
| Leeward Plateau (1224, 4170), y136 | rift 932, range 1,820 | rift visible at 2,490 (7 of 205); range **blocked** | rift visible at 1,861 (24 of 205); range visible at 1,832 (3 of 164) |
| Rim Uplands (3149, 2768), y125 | rift 353, glacier 526 | rift visible at 783 (12 of 205); glacier visible (15 of 171); range visible (7 of 164); cones blocked | rift 35 of 205; glacier 42 of 171; range 13 of 164; cones graze (3 of 129) |
| Stillwater Basin (6805, 4407), y109 | cones 349, glacier 455 | cones visible (6 of 129); rift visible (51 of 205); glacier visible (37 of 171); lake **blocked** | all four visible; lake 18 of 62 |
| Eastern Downs (6446, 3527), y93 | glacier 317, lake 380 | glacier visible (37 of 171); cones visible (17 of 129); range visible at 3,351 (3 of 164); lake **blocked** by y94 ground 45 blocks away | lake visible at 514 (32 of 62) |

Every hub sees at least one landmark from the ground, and from a rooftop sees all of
the ones checked. The ground-level misses are close:

- the Leeward Plateau site is blocked by ground **22-74 blocks** away that rises 1-2 blocks
  above eye level;
- the Stillwater site is blocked by ground **about 30 blocks** away;
- the Eastern Downs site is blocked by ground **45 blocks** away.

That is micro-relief on a gentle site, not a ridge. Where a town's buildings stand will decide
those views, not the terrain.

### The old Stillwater hub site

From (5646, 3302), y78, the site that earned Stillwater Basin hub tier last pass, now
inside the Glacier Valley:

| Target | Result |
| --- | --- |
| Lake | visible at 605, 9 of 62 samples; east shore visible at 876 |
| Rift | visible at 1,638, 7 of 205 samples |
| Cones | visible at 1,566, 17 of 129 samples |
| Range | blocked at 3,446 |

## What this means for the plan

1. **The rift reads from everywhere near it.** All three hubs checked against it see part
   of it from the ground, out to 2.5 km.
2. **The range is the weakest landmark in the east.** From the lake and the Eastern Downs
   only 1-3 samples of it are visible, at 3.3-3.5 km: silhouettes on the DH horizon.
3. **The cones read from the east and south-east but not across the rift.** The rift's
   north rim, on the near side, hides them from the Rim Uplands.
4. **The glacier cannot be read end to end.** Its axis bends, so the lake is never in view
   from the head, even after the planned carve. Any "see the lake from the glacier" moment
   has to be placed on the lower reach.

## Reproducing

```bash
python tools/sightlines.py --source-root <source root> --plan data/checks/sightlines.json
```

Output goes to `derived/sightlines/sightlines.json`, with the blocker, clearance and sample
counts for every target.
