# Region layout: rationale and gap list

**Status: draft for review, second revision.** The schemas of `data/regions.json`
(`cobblers.regions/2`) and `data/landmarks.json` (`cobblers.landmarks/1`) are proposed and
not yet approved. No terrain has been edited and no biomes have been painted. Gym towns,
routes and events are not assigned.

Everything was measured from `land_8k_16_eroded.png` (sha256 `526fe220…a860f6`) with the
tools in `tools/`. Feature locations come from the annotated copy
`land_8k_16_eroded_annotated.png` (sha256 `52793443…2c3142`), recorded in
`data/landmarks.json`.

Companion reports:

| Report | Covers |
| --- | --- |
| [`CROSS_SECTIONS.md`](CROSS_SECTIONS.md) | glacier and rift profiles; the rift-width question |
| [`GLACIER_CARVE.md`](GLACIER_CARVE.md) | the planned carve |
| [`SIGHTLINES.md`](SIGHTLINES.md) | what can be seen from where |
| [`BIOME_COVERAGE.md`](BIOME_COVERAGE.md) | biome and tag coverage analysis |
| [`BIOME_COVERAGE_MATRIX.md`](BIOME_COVERAGE_MATRIX.md) | the full reference table |
| [`../mechanics/SPAWN_PHILOSOPHY.md`](../mechanics/SPAWN_PHILOSOPHY.md) | curated versus full-dex spawning |

## What changed since the first draft

| Change | Result |
| --- | --- |
| The annotation is ground truth for feature locations | `data/landmarks.json` holds 7 landmarks with outlines, axes and anchors. Tools look features up instead of inferring them |
| The rift is neither water nor dry | New region class `anomaly`. Biome and spawn table deferred, custom biome required, water policy `never`. `landforms.py` and `cell_stats.py` classify its floor as void; the only inland water left on the map is the meltwater lake |
| The glacier is a planned carve | New region **Glacier Valley**, status `partial`, with a carve spec. It cuts the Eastern Downs in three |
| Biome coverage is a primary constraint | All 55 loaded overworld biomes are placed; 73 of 73 spawn references are covered, with overlays and underground biomes |
| Status on regions and landmarks | `built` / `partial` / `planned`. `partial`: Glacier Valley, Strand Flats, glacier corridor. `planned`: moraine, meltwater river |
| Region count | 12 → 14: Glacier Valley and Rim Uplands added; Sunken Rift renamed The Rift |

## Where the brief and the terrain disagree

| Brief says | Terrain measures | Consequence |
| --- | --- | --- |
| Glacier runs **north-east** from the rift, x4800-7000, z2400-4400, lake at its **south-west** end | The drawn outline runs **north-west to south-east**, x3128-6504, z1680-4192. Its floor falls from y99 at the range to y44.7 in the lake, which sits at the **south-east** end beside the rift's north-east arm | The drawing was used, as instructed |
| Glacier faintly present, under-carved | Confirmed. Median wall 5.5°, depth 19.6, rim to rim 548. Shapes: U 10, V 7, flat 3, asymmetric 11, none 1. A saddle at d1792 is 4 blocks deep | Status `partial`; carve specified |
| **Stillwater Basin (D6) is unrelated to the glacier** | **It is not.** Its enclosed lake is the glacier's meltwater lake, and all six of its ranked hub sites (139, 104, 103, 103, 100, 99) lie inside the glacier trough | Kept as its own hub as directed, now justified by other ground; see [the Stillwater decision](#stillwater-basin-needs-your-decision) |
| Rift: floor below sea level, never water, never visible | 1.70 km² lies below y62. Another **0.78 km² of floor and shelf lies at y62-80** and would render as visible ground | The floor treatment has to reach about y80, not only y62 |
| Rift painted widest at the centre, measured narrowest at D4 (172) | Rim to rim, the trunk centre (508-712) is as wide as the arms (476-624 by median). The 172 figure was the width below y62; the trunk floor sits at y57-62 against y44-54 in the arms | A floor-depth effect, not width. See `CROSS_SECTIONS.md` |
| The rift is an erosion feature, or was changed by erosion | The erosion pass changed no block by as much as one block (max 0.77) | The rift was painted between the Gaea export and the pre-erosion export. **The "eroded" heightmap carries no erosion** |
| Volcanic cones | As annotated, south-east. Clipped flat at y200, no craters | Unchanged gap |
| A large flat coastal lowland | Still none. The Strand Flats have 38% of land under 5° | Status `partial` |

## How boundaries were drawn

No boundary is a coordinate or a cell edge. Each region's `boundary_basis` names one or
more of these:

| Basis | Meaning |
| --- | --- |
| `contour` | A smoothed elevation threshold |
| `rim` | Distance to the rift combined with slope |
| `watershed` | A priority-flood drainage divide |
| `coastline` | Distance to open sea combined with elevation |
| `ridge` | A measured crest line |
| `strip_width` | Width of land pinned between two features |
| `nearest_high_core` | Proximity to the nearer of two high cores |
| `land_body` | A separate island |
| `valley` | **New.** Inside the annotated glacier outline, ground no higher than the lower rim of its nearest cross-section station (smoothed over three stations) less 2 blocks |
| `lake` | **New.** An enclosed water body |
| `planned_feature` | **New.** A buffer around a planned landmark's axis: 90 blocks for the moraine crest, 72 for the river channel |
| `split` | **New.** A piece of a former region cut off by another region, assigned by which features bound it |

## Prevailing wind and rain shadow

**Unchanged.** Wind from the west-northwest; treeline and snowline y165. The Windward
Coast and range are wet, the Leeward Plateau dry, and the Ember Highlands warm and leeward.

**One deliberate exception:** the Glacier Valley carries snow on its floor and walls below
the treeline. That comes from the glacier ice and cold air draining from the range.

## Regions

Areas include water and void. "Flat" is the share of land under 5°.

| Region | Class | Tier | Status | Area km² | Median y | Flat | Biome bands |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Northern Range | terrain | wilderness | built | 5.15 | 131 | 26% | windswept_forest 44, grove 22, snowy_slopes 13, frozen_peaks 12, jagged_peaks 8 |
| Windward Coast | terrain | route | built | 2.85 | 104 | 46% | dark_forest 59, old_growth_spruce_taiga 24, stony_shore 10, pale_garden 7 |
| Leeward Plateau | terrain | hub | built | 2.89 | 130 | 72% | savanna_plateau 38, savanna 38, desert 18, windswept_savanna 6 |
| **Rim Uplands** | terrain | hub | built | 2.60 | 121 | 71% | windswept_hills 78, old_growth_pine_taiga 22 |
| **The Rift** | **anomaly** | **destination** | built | 3.77 (void 1.70) | 89 | 15% | **deferred**: custom biome required |
| **Glacier Valley** | terrain | route | **partial** | 3.03 | 99 | 56% | snowy_taiga 44, taiga 26, frozen_river 19, river 8, windswept_gravelly_hills 3 |
| Stillwater Basin | terrain | hub | built | 2.57 | 101 | 46% | cherry_grove 76, swamp 18, stony_shore 6 |
| Eastern Downs | terrain | hub | built | 3.58 | 104 | 54% | plains 50, meadow 25, birch_forest 18, stony_shore 6 |
| Ember Highlands | terrain | wilderness | built | 3.46 | 149 | 60% | eroded_badlands 42, badlands 25, wooded_badlands 21, stony_peaks 12 |
| Lakeshore Vale | terrain | route | built | 5.82 | 117 | 60% | flower_forest 48, forest 38, old_growth_birch_forest 10, beach 3 |
| Strand Flats | terrain | route | **partial** | 0.77 | 85 | 38% | sunflower_plains 54, beach 33, mangrove_swamp 13 |
| Northern Isles | terrain | wilderness | built | 2.72 | 90 | 26% | snowy_plains 62, snowy_beach 20, ice_spikes 18 |
| Jungle Isle | terrain | wilderness | built | 2.51 | 104 | 20% | jungle 53, bamboo_jungle 30, beach 17 |
| Southern Isles | terrain | wilderness | built | 4.71 | 102 | 29% | sparse_jungle 70, mushroom_fields 18, beach 12 |

**Underground biomes** (planned; the WorldPainter method is verified in source, not tested
in an export):

| Biome | Where |
| --- | --- |
| dripstone_caves | under every region except the rift |
| lush_caves | Lakeshore Vale, Jungle Isle |
| deep_dark | Northern Range |
| sulfur_caves | Ember Highlands, optional |

### The new and changed regions

**The Rift** (renamed from the Sunken Rift)
- *Geometry:* the same, bounded by its rim.
- *Class and biome:* region class `anomaly`, tier `destination`. No biome and no spawn table
  are assigned; no ocean or vanilla default either. The river, gravelly hills and mangroves
  it held last draft moved to the Glacier Valley and the Strand Flats.
- *Water:* its landmark's water policy is `never`, so tools count its sub-sea floor as void.

**Glacier Valley** (new, `partial`)
- *Extent:* the measured trough inside the annotated outline, the meltwater lake, and
  buffers around the planned moraine and river.
- *Taken from:* Stillwater Basin (1.23 km²), the Eastern Downs (1.56 km²) and a sliver of
  the range head (0.01 km²).
- *Biomes:* follow the glacier landform. `frozen_river` and `river` need the carve before
  they are painted.

**Rim Uplands** (new)
- *Extent:* the piece of the old Eastern Downs west of the glacier valley, north of the rift
  and south-east of the range.
- *Character:* high (median y121), flat (71% under 5°), far from the sea (median 1,888
  blocks).
- *Tier:* hub. It holds the 106 and 100-block sites at C4 that made the Downs a hub.

**Stillwater Basin**
- *Extent:* what remains of the D6 lake's drainage basin outside the glacier valley, plus the
  east-coast piece of the Downs south of the valley mouth, which it borders.
- *Biomes:* unchanged palette: cherry grove, swamp low ground, stony shore on the new coast.

**Eastern Downs**
- *Extent:* the north-east piece: land draining to the north and east seas beyond the
  glacier valley. 3.58 km², down from 8.61, so the "largest and most generic region" gap is
  closed.
- *Tier:* stays hub on a 107-block site at (6446, 3527).

**Other region changes:**

| Region | Change |
| --- | --- |
| Leeward Plateau | Gains `savanna` on its lower tableland |
| Ember Highlands | Gains `badlands` and `wooded_badlands`; loses `windswept_savanna`, which no longer fits any of its ground |
| Lakeshore Vale | Gains `old_growth_birch_forest` |
| Windward Coast | Gains `pale_garden` (VanillaBackport) |
| Northern Isles | Gains `ice_spikes`, Kyurem's only biome in the pack |
| Strand Flats | Gains `mangrove_swamp` |
| Sea | Gains `deep_frozen_ocean` |

## Stillwater Basin needs your decision

You asked to keep Stillwater Basin (D6) as its own region with hub tier, as unrelated to
the glacier. The region is kept separate and tiered hub. The premise, though, does not hold:

- **The "still water" is the glacier's meltwater lake:** the enclosed basin at (6025, 3810),
  floor y44.5, at the drawn glacier's south-east end.
- **Every site that earned it hub tier lies inside the glacier trough:**
  - 139 blocks square at (5646, 3302), the largest flat ground on the map below y190;
  - 104 at (5881, 3378), 103, 103 and 100.
- **Without the trough, its original basin area's best site is 96 blocks**, below the
  99-block bar that kept Lakeshore Vale a route.
- **As now drawn, the hub tier is honest for a different reason.** The east-coast land
  inherited from the Downs holds a 104-block site at (6805, 4407).

**Options:**

| | Option | Effect |
| --- | --- | --- |
| **A** | Keep the current proposal | Stillwater is a hub on the east coast; its name no longer describes its ground |
| **B** | Make the Glacier Valley floor the hub | The largest flat ground on the map is there. The carve as specified still leaves 122-124-block squares on the floor, but not near the lake. The lower flats become a sloping floor |
| **C** | Leave the lower trough uncarved | Keep the 139-block flats near the lake as the hub. The glacier reads as a glacier only from the saddle up |

## The Rift as a destination: Victory Road or the League?

This is an assessment. Nothing is assigned.

**What the rift offers:**

- **Layout:** five arms (5.9 km of axis) meeting at two junctions, with 476-624 blocks
  between rims.
- **Descent:** walls median 23-33°, falling a median 52-66 blocks.
- **Floor:** 1.70 km² that will never be seen, plus 0.78 km² of low shelf that also needs
  the floor treatment.
- **Neighbours:** six regions border it — Rim Uplands, Leeward Plateau, Lakeshore Vale,
  Stillwater Basin, Ember Highlands and Glacier Valley.
- **Visibility:**
  - The rims are visible from every hub checked against them.
  - A structure rising 130 blocks from either junction floor is visible from all four hubs'
    sites at 1.2-4.0 km.
- **Entry:** no natural walk-down ramp was found, so every descent would be authored.

| | Victory Road | The League |
| --- | --- | --- |
| Shape it needs | A long, branching, hostile traversal just before the end | One climactic place, arrived at, not wandered |
| Fit | **Strong.** Five arms and two junctions make a natural branching gauntlet. The descent is a threshold, and the hidden floor and custom biome make it feel unlike anywhere else | **Partial.** There is no ground to build on, since the floor is void by design. A League here is a built structure: suspended, bridged rim to rim, or standing on the unseen floor and rising through the fog. The trunk has the steepest walls (33°) and highest rims (y130-156), the most dramatic setting |
| Visibility | Being seen early is a promise; the rift shows from the hubs | A tower at a junction is seen from every hub, a long-running "that is where we are going" |
| Sequence-break risk | **High.** The rift is open along its whole rim. Players can dig, pillar or build down anywhere, so authored descents only gate a traversal if descending elsewhere is prevented or pointless | Lower. A structure can be locked |
| Terrain work | Floor treatment up to about y80, authored descents, custom biome | The same, plus a structure with no terrain to sit on |

**Assessment:** the rift suits **Victory Road naturally** and the **League only as
architecture**. The two are compatible: a Victory Road through the arms that ends at a
League structure at the east junction, where the south-east and north-east arms meet the
trunk. Two things decide which is realistic:

1. whether the rim can be made non-traversable except at authored descents;
2. whether the custom biome's fog and light read as the brief intends.

Both are experiments, not decisions.

## Buildable sites by region

Largest flat squares, at most 4° slope, at least y64 and at most y190. They were found with
`tools/find_sites.py`'s functions applied to each region's mask by a design script; the
command-line tool only takes a bounding box. Tiers use a 99-block bar.

| Region | Largest | Second | Third |
| --- | --- | --- | --- |
| Glacier Valley | 139 at (5646, 3302) y75-78 | 104 at (5881, 3378) y67-71 | 103 at (5063, 2724) y108-112 |
| Leeward Plateau | 114 at (1224, 4170) y133-137 | 104 at (1426, 3837) | 100 at (912, 3936) |
| Ember Highlands | 111 at (4841, 5816) y162-164 | 93 | 92 |
| Eastern Downs | 107 at (6446, 3527) y92-94 | 99 at (6209, 2738) | 89 |
| Rim Uplands | 106 at (3149, 2768) y122-126 | 100 at (3401, 2951) | 92 |
| Stillwater Basin | 104 at (6805, 4407) y107-109 | 96 at (6205, 4791) | 79 |
| Lakeshore Vale | 96 | 93 | 93 |
| Windward Coast | 95 | 88 | 82 |
| Northern Range | 92 | 82 | 76 |
| Southern Isles | 91 | 81 | 77 |
| The Rift | 85 at y97-99 on a wall shelf | 84 at y69-73 on the floor shelf | |
| Jungle Isle | 83 | 74 | 71 |
| Northern Isles | 81 | 78 | 73 |
| Strand Flats | 76 | 72 | 68 |

The Ember Highlands clear the bar but stay wilderness; their ground is a hot, remote
tableland. The Glacier Valley's figures are before the carve; afterwards its largest is
124.

## Distinguishable at 128 blocks

New neighbour pairs, and what separates them:

| Neighbours | Separated by |
| --- | --- |
| Rim Uplands / Eastern Downs | Bare wind-cut hills and old pines, against green grassland and birch; the glacier valley between them |
| Rim Uplands / Leeward Plateau | Grey-green windswept grass and stone, against yellow savanna and sand |
| Glacier Valley / Northern Range | A white flat valley floor between snowy spruce walls, against open snow slopes and bare peaks |
| Glacier Valley / Eastern Downs | Snow and spruce, against green grass |
| Stillwater Basin / Eastern Downs | Pink cherry canopy, against open grass |
| The Rift / anything | Fog and portal particles rising from a trench |

## Biome coverage, in brief

The full analysis is in `BIOME_COVERAGE.md`.

- **Every loaded overworld biome has a place:** all 55, including two from VanillaBackport.
- **The pack's spawn references:**
  - 73 of 73 are covered with overlays and underground biomes;
  - 66 are covered by painted surface biomes alone;
  - 67 are covered with the `is_lush` fallback and no underground biomes.
- **Six tags have no loaded member and need overlays.** Four are for identity
  (`is_tropical_island`, `is_snowy_forest`, `is_volcanic`, `is_thermal`) and two are
  optional (`is_sky`, `is_shrubland`). A seventh overlay, the `is_lush` fallback, stays
  until underground `lush_caves` is proven.
- **No species depends on an overlay.**
- **Underground biomes are the real dependency.** Without them and without the fallback,
  29 species are unreachable, including every fossil.

## Gap list

1. **Stillwater Basin's premise.** See the decision above.
2. **The glacier carve.** 5.9M blocks cut, 24.1M raised. It shrinks the valley's building
   ground, and cannot open a head-to-lake view because the valley bends.
3. **Rift floor treatment.** It must cover 0.78 km² of ground between y62 and y80 as well
   as the 1.70 km² void. The custom biome needs a datapack biome JSON and an in-game test;
   WorldPainter can write a custom biome ID (source verified, not tested).
4. **Underground biomes.** An export test must come first. 29 species depend on it, or
   6 with the `is_lush` fallback.
5. **The erosion pass did nothing.** If erosion was intended, the heightmap needs
   re-exporting from TerreSculptor, and every measurement here must be rerun against the
   new hash.
6. **No flat coastal lowland.** The Strand Flats still need flattening, now also for
   mangroves.
7. **Summits clipped at y200.** Cones have no craters, and summit anchors hide their own
   centres.
8. **Islands cannot be contiguous.** Northern and Southern Isles are three bodies each.
9. **Range north foreshore compromise.** Unchanged.
10. **The Stillwater east-coast strip** runs about 250 blocks wide beside the Ember
    Highlands.
11. **Cobbleverse legendary-structure spawns** reference 30 `cobbleverse:custom_spawn/...`
    biome IDs that no loaded pack defines. **Not verified in game.**
12. **Only cell C8 has no region.** It is open sea.

## Proposed schemas

### `data/regions.json`: `cobblers.regions/2`

Top level:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string | `cobblers.regions/2` |
| `schema_status` | enum | `proposed` until approved |
| `status` | enum | `draft`, `approved` |
| `computed_from_sha256` | string | Heightmap the measurements came from |
| `landmarks` | string | Path of the landmarks file the plan was built against |
| `geometry` | object | Raster resolution, polygon tolerance, coverage statement |
| `enums` | object | Meaning of each `region_class`, `tier` and `status` value |
| `climate` | object | `prevailing_wind_from`, `basis`, `treeline_y`, `snowline` |
| `sea_biomes` | object | `shares` and `rules` |
| `underground_biomes` | array | `{biome, regions, status, method, note, optional?}` |
| `tag_overlays` | array | `{tag, add_biomes, scoped_to, kind: identity or optional or fallback, reason, only_through_this_overlay}` |
| `tag_coverage` | object | Coverage by plan layer and scope, and single-home species, from `tools/spawn_biomes.py` |
| `regions` | array | One entry per region |

Each region:

| Field | Type | Meaning |
| --- | --- | --- |
| `id`, `display_name` | string | Stable id and player-facing name |
| `region_class` | enum | `terrain`, `anomaly` |
| `tier` | enum | `hub`, `route`, `wilderness`, `destination` |
| `status` | enum | `built`, `partial`, `planned` |
| `character` | string | One-sentence identity |
| `contiguous`, `pieces` | bool, int | False only for archipelagos |
| `cells`, `cell_share` | array, object | Cells by share, at least 0.5% |
| `bounds` | object | Block bounding box |
| `climate` | object | `exposure`, `moisture`, `temperature` |
| `boundary_basis` | array | `{basis, detail}` |
| `measured` | object | Area, land, water, void, elevation percentiles, slope, treeline share, distance to sea |
| `biomes` | object | `deferred`; `primary`, `secondary`, `bands` of `{biome, share, rule}`; for anomalies, `custom_biome` |
| `spawn_table` | object | Anomalies only: `{status: deferred}` |
| `biome_tags` | array | Spawn-referenced tags its biomes resolve into, overlays included |
| `tag_overlays_required` | array | `{tag, biome, kind}` |
| `underground_biomes` | array | Biome ids planned beneath it |
| `distinctness` | object | `ground`, `vegetation`, `water`, `sightlines`, `signature_at_128_blocks` |
| `notes` | array | Caveats |
| `polygons` | array | Outer rings as `[x, z]`, one per piece |

Changes from `/1`:

- new fields: `region_class`, `status`, `spawn_table`, `underground_biomes`, `measured.void_km2`,
  `biomes.deferred`, `biomes.custom_biome`, `enums`, `landmarks`;
- tier value `destination`;
- `tag_overlays` gains `kind` and `only_through_this_overlay`;
- `tag_coverage` is restructured.

### `data/landmarks.json`: `cobblers.landmarks/1`

The validator already registered this schema; this revision extends it. It now requires
`id`, `name`, `kind`, `anchor` and `status`.

| Field | Values |
| --- | --- |
| `kind` | now also `glacier`, `moraine`, `river` |
| `status` | `built`, `partial`, `planned` |
| `water` | `allowed`, `never` |

Each landmark also carries:

| Field | Meaning |
| --- | --- |
| `status_basis` | Why it has that status |
| `anchors` | Named points; tools address them as `landmark.anchor` |
| `extent.polygons` | The outline |
| `axes` | `{id, polyline, section_width, basis, measured}` |
| `carve_spec` | The glacier's planned carve |
| `spec` | Moraine and river specifications |
| `custom_biome`, `surface`, `role` | The rift's anomaly requirements |
| `annotation` (top level) | The source image's path and hash, and the disagreement between drawing and text |

### Validation once approved

**Already enforced for landmarks:** `tools/validate_data.py` checks the required fields and
enums above.

**For regions, once the schema is approved, it should check that:**

- ids are unique;
- biome ids are present in the loaded registry, via `tools/spawn_biomes.py`;
- band shares sum to one;
- `pieces` equals the polygon count;
- `computed_from_sha256` matches `data/world.json`;
- each overlay biome is painted only in its `scoped_to` regions;
- every land and void block lies inside exactly one polygon;
- deferred regions carry no bands;
- every region with `status` other than `built` explains itself in `notes`.

## Reproducing

```bash
python tools/landforms.py     --source-root <source root>
python tools/cell_stats.py    --source-root <source root>
python tools/cross_section.py --source-root <source root> --landmark glacier_corridor --axis trough --sample-step 4 --level 62
python tools/cross_section.py --source-root <source root> --landmark rift --axis trunk --sample-step 4 --level 62
python tools/sightlines.py    --source-root <source root> --plan data/checks/sightlines.json
python tools/spawn_biomes.py  --server-dir <server dir> --regions data/regions.json --markdown docs/world-building/BIOME_COVERAGE_MATRIX.md
python tools/find_sites.py    --source-root <source root> --min-size 48 --max-slope 4 --above-sea 2 --max-y 190   # whole map
```

The terrain tools verify the heightmap hash before reading it. The landmark-aware tools read
`data/landmarks.json`, and refuse to run if it is malformed unless `--no-landmarks` is
passed.

The region raster, band assignment, glacier trough mask and carve simulation were built by
design scripts outside the repository. The rules they applied are recorded in each region's
`boundary_basis` and band `rule`. Those scripts are not committed, so the polygons cannot yet
be regenerated from `tools/` alone.
