# Region layout, third revision: terrain character and sub-regions

**Status: draft for review (2026-09-14).**
- **Schemas:** `data/regions.json` is on `cobblers.regions/3` (proposed); `data/landmarks.json`
  stays on `cobblers.landmarks/1`.
- **Terrain:** the 2026-09-14 carve, measured in [`TERRAIN_2026-09-14.md`](TERRAIN_2026-09-14.md).
- **Painted:** biomes and vegetation, as a rough preview (§6).
- **Not assigned:** encounter lists, towns and routes.

The second revision (14 regions, biome coverage as a primary constraint) was built on the old
terrain and is superseded. It remains in git history.

## 1. Design basis

| Then | Now |
| --- | --- |
| Every loaded biome placed, so every spawn reference is reachable | **Not a constraint.** Spawns will be curated per sub-region, so a region needs a terrain character a player recognises, not a biome quota |
| Region = spawn unit | **Region = terrain character; sub-region = spawn unit**, sized to one stretch of travel |
| Feature locations partly from the brief | **Only from the paint.** Every landmark extent is the annotated outline (the previous pass missed the glacier by following prose) |

## 2. Method

**Output:** labels on an 8-block raster, traced to polygons.

1. **Hard regions from terrain and the annotation:**
   - the massif (ground above y138 around the Tri Peaks, Vessu and Clay);
   - the Glacial Tear (trough outline widened ~100 blocks to its walls, plus Merian and the
     crags above the head);
   - the Rift outline;
   - Lake Tilpey's basin;
   - the Craters outline;
   - the south-east plateau above y140;
   - each island.
2. **Seeded regions for the remaining mainland,** grown by terrain-weighted distance:
   - each step costs its length times (1 + 0.35 × climb);
   - crossing a carved channel adds a fixed cost;
   - water is impassable.

   Borders therefore settle where fronts meet over ridges, channels and coasts.
3. **Sub-regions grown the same way** inside each region, from hand-placed seeds.
4. **Clean-up and measurement:**
   - disconnected pieces join the neighbour they share most border with;
   - polygons are simplified to 24 blocks;
   - elevation, slope, bounds and area are measured per region and per sub-region.

## 3. Regions (21) and sub-regions (62)

| Region | Class | Area km² | Median y | Sub-regions (km²) | Painted biomes |
| --- | --- | ---: | ---: | --- | --- |
| **The Tri Peaks** (`tri_peaks`) | terrain | 1.69 | 164 | The Tri Peaks (0.63), Mt Vessu (0.73), Mt Clay (0.33) | grove, snowy_slopes, jagged_peaks |
| **Frostpeak Point** (`frostpeak_point`) | terrain | 1.27 | 105 | Frostpeak (0.88), Frostpeak Strand (0.39) | snowy_taiga, snowy_slopes, frozen_peaks |
| **The Glacial Tear** (`glacial_tear`) | terrain | 2.79 | 109 | Merian Cirque (0.54), The Crags (0.42), Upper Trough (0.82), Lower Trough (1.01) | snowy_plains, snowy_slopes, grove, stony_peaks |
| **The Northern Downs** (`northern_downs`) | terrain | 1.93 | 111 | Peak Pond Hollow (1.16), North Shore Downs (0.46), North-East Downs (0.31) | old_growth_spruce_taiga, meadow, taiga |
| **The Marsh Country** (`marsh_country`) | terrain | 3.27 | 112 | Marshy Marsh (0.94), Marsh Creek (0.72), Eastern Moor (1.15), Glacier Foot Fields (0.46) | swamp, meadow, plains |
| **Tilpey Lakeland** (`tilpey_lakeland`) | terrain | 3.29 | 95 | Tilpey North Shore (0.56), Tilpey Waters (0.78), Tilpey South Shore (1.01), Tilpey West Meadows (0.26), Tilpey East Shore (0.69) | birch_forest, river, forest, flower_forest |
| **The Wedge** (`the_wedge`) | terrain | 0.75 | 124 | Wedge North (0.27), Wedge South (0.47) | dark_forest, forest |
| **The Rift** (`the_rift`) | terrain | 2.25 | 110 | Rift Trunk (0.57), Rift West Spur (0.53), Rift South-West Arm (0.55), Rift South-East Arm (0.61) | windswept_gravelly_hills (custom biome still wanted) |
| **Viltri Woods** (`viltri_woods`) | terrain | 5.84 | 113 | Lake Viltri Hollow (0.81), Viltri's Path Valley (0.88), Foothill Woods (1.95), North-West Coast (1.10), Viltri Plateau (1.09) | forest, windswept_forest, old_growth_birch_forest, plains |
| **The Shrew Lakes** (`shrew_lakes`) | terrain | 2.73 | 115 | Shrew Lake Shores (1.16), Arrow Lake Shores (0.56), River of Shrews Vale (1.01) | cherry_grove, flower_forest, plains |
| **Pallet Fields** (`pallet_fields`) | terrain | 1.80 | 115 | Pallet Meadows (0.78), West Shore (0.80), South-West Fields (0.22) | plains, sunflower_plains |
| **The Southern Coast** (`southern_coast`) | terrain | 3.60 | 106 | Arrow Creeks (1.85), South Strand (1.00), Rift Foot (0.75) | savanna, plains |
| **The Scorched Plateau** (`scorched_plateau`) | terrain | 1.65 | 152 | Plateau West (0.87), Plateau South (0.66), Plateau East (0.13) | badlands, wooded_badlands, eroded_badlands |
| **The Craters** (`the_craters`) | terrain | 1.31 | 143 | North-West Rim (0.30), Great Crater (0.61), East Cones (0.40) | stony_peaks, savanna_plateau |
| **The Eastern Dunes** (`eastern_dunes`) | terrain | 2.31 | 124 | East Coast Dunes (0.89), South-East Dunes (1.42) | desert |
| **Northgate Isle** (`northgate_isle`) | island | 0.93 | 101 | Northgate West (0.42), Northgate East (0.50) | old_growth_spruce_taiga, taiga |
| **The Pine Isles** (`pine_isles`) | island | 1.97 | 91 | North Pine Isle (0.79), South Pine Isle (1.18) | snowy_taiga |
| **Fungal Isle** (`fungal_isle`) | island | 0.80 | 113 | Fungal North (0.41), Fungal South (0.39) | mushroom_fields |
| **Sunset Isle** (`sunset_isle`) | island | 2.58 | 97 | Sunset West (1.35), Sunset East (1.23) | savanna, flower_forest |
| **Jungle Isle** (`jungle_isle`) | island | 1.26 | 110 | Jungle West (0.61), Jungle East (0.65) | jungle, sparse_jungle |
| **The Long Isle** (`long_isle`) | island | 2.58 | 105 | Long Isle North (0.65), Long Isle Middle (0.85), Long Isle South (1.09) | taiga, forest, sparse_jungle |

**Size:**
- Sub-regions are 0.13–1.95 km². Most are 0.4–1.2 km², roughly 600–1,100 blocks across: one
  stretch of travel.
- **Two are large enough to split** if routes need it: Foothill Woods (1.95) and Arrow Creeks
  (1.85).
- **One is a sliver** that should merge: Plateau East (0.13).

**Pieces:** every region is one piece except the Pine Isles, which is two islands by design.

## 4. Sub-region schema (proposed)

Each record in `subregions[]`:

| Field | Holds |
| --- | --- |
| `id` | stable snake_case id, unique across all sub-regions. The spawn unit's key |
| `display_name` | player-facing name |
| `parent` | region id; each region also lists its `subregions` |
| `polygons` | block x, z rings |
| `measured` | area, bounds, elevation p10/median/p90/max, slope mean/p90/flat share |
| `boundaries` | every neighbour, with the measured basis of the shared edge and its length (below) |
| `encounters` | `{ "table": null, "status": "empty" }`, the slot for the encounter table. **Not populated:** the spawn philosophy is open |
| `paint` | `{ "preset": … }`, a key into `paint_presets` |

### Boundary legibility (measured)

**How each shared edge is classified:**
- **creek or trench:** at least 25% of the edge on carved ground;
- **ridge:** the edge stands 3+ blocks above both sides;
- **coast;**
- **painted change of cover:** a treeline, snowline or ground change, because the two sides use
  different presets;
- **open ground:** otherwise.

| Basis | Edge length (blocks, both sides counted) |
| --- | ---: |
| Painted change of cover | 195,700 |
| Coast | 157,200 |
| Open ground: not legible | 25,100 |
| Creek or trench | 8,400 |
| Ridge | 0 |

**Where edges fail to read:**
- **Seams that follow high ground are not detected as ridges.** The distance growth drew them
  along slopes and cols rather than along crests, so the classifier finds no ridge anywhere.
  Most inland edges are legible only because the two sides are painted differently.
- **Open-ground edges over 25% of a sub-region's inland edge:**
  - **Fungal Isle's halves**, both painted mushroom fields: merge them;
  - **the four Rift arms** and **the three massif summits**, split at valley forks and cols
    between same-preset neighbours: legible on the ground as separate arms and peaks, but the
    classifier cannot see it;
  - **the Great Crater and the East Cones;**
  - **Plateau East, Pallet Meadows and the East Coast Dunes.**
- **Fix:** vary their cover slightly, or mark the edge with a path or sign when routes are
  drawn.

## 5. Biomes

**38 vanilla overworld biomes are painted.**

**14 are unused:**
- bamboo_jungle, mangrove_swamp, old_growth_pine_taiga;
- windswept_hills, windswept_savanna, ice_spikes;
- beach, snowy_beach, stony_shore (shores are painted as terrain, not biome);
- frozen_river, lukewarm_ocean;
- and the three cave biomes: deep_dark, dripstone_caves, lush_caves.

**The cave biomes are planned** in `underground_biomes`, remapped to the new region ids: lush
under the Shrew Lakes and Jungle Isle, deep dark under the Tri Peaks, sulfur caves (optional)
under the Craters. **Nothing underground is painted**: the exported world has no caves yet.

**Pale Garden is not painted.** WorldPainter lists it, but Minecraft 1.21.1 does not have it.

## 6. Paint

`tools/paint_maps.py` turns each sub-region's preset into maps, and
`tools/worldpainter/paint.js` applies them during the export.

**Each preset sets:**
- a biome, or biome bands by height;
- base terrain, noise patches, terrain above or below a height, and rock on steep ground;
- tree layers with a density range;
- plant sets with a coverage;
- frost.

**Density follows two-octave noise between each preset's minimum and maximum, with
clearings**, so no forest is uniform. The rules across all sub-regions:

| Feature | Rule |
| --- | --- |
| Snow line | frost above y136 (alpine) or y140 (crags); snow terrain above y146, deep snow above y172; biome bands grove → snowy slopes → jagged peaks. Band edges wobble ±8 blocks so they are not contour lines |
| Forests | deciduous (oak/birch), pine, swamp and jungle layers; dense dark forest in the Wedge, old-growth birch on the Viltri Plateau, mixed pine and oak in the Foothill Woods |
| Shrubland | shrub plants (sweet berry, azalea, large fern, tall grass) at 18–22% coverage in the Northern Downs, Eastern Moor and coastal scrub |
| Desert | desert terrain (sand, cactus, dead bush) on the Eastern Dunes |
| Mesa | terracotta bands and red sand, with scattered trees on the plateau top |
| Swamp | swamp trees, mud patches, orchids and ferns around Marshy Marsh, thinning along its creek |
| Glacier | deep snow and frost on the trough floor, bare rock on walls steeper than 26° |
| The Rift | stone and gravel, gravel floor below y96, almost no trees |
| Craters | basalt and blackstone with specks of magma |
| Lakes | water raised to one block below each spill; clay and gravel beds, sand banks |
| Carved channels | dry gravel beds 10 blocks wide, no trees |
| Coast | beach terrain on gentle shore within 3 blocks of sea level, gravel on cold shores |
| Sea | frozen, cold, temperate and warm oceans north to south; deep variants below y34 |

**WorldPainter note:** its "Short Grass" plant writes `minecraft:grass`, a block Minecraft
1.21.1 no longer has, so the plant sets avoid it.

## 7. Spawn capacity reserved underground and off-world

**Source:** every spawn entry the server loads (5,195 entries, 1,019 species ids). Each species
is classified by where its entries can place it:
- **Nether or End:** by biome tag.
- **Cave:** cave biomes, `canSeeSky: false`, `maxY` below 50, or a sky-light cap of 7 or less.
- **Surface:** everything else.

| Where the pack lets a species spawn | Species | Share |
| --- | ---: | ---: |
| Surface only | 525 | 51.5% |
| Surface and also cave, Nether or End | 368 | 36.1% |
| Cave only | 57 | 5.6% |
| Cave and/or other dimension, never surface | 15 | 1.5% |
| End only | 11 | 1.1% |
| Nether only | 2 | 0.2% |
| Only in unresolved non-vanilla dimensions (e.g. Aether tags) | 41 | 4.0% |

Species with at least one entry anywhere underground or off-world: cave 354, Nether 114,
End 52.

**Recommended reservation when curating:** roughly **60% surface, 22% caves, 12% Nether, 6%
End** of the species the campaign uses.
- **Committed first:** the 85 species that can never be surface. They go underground or
  off-world.
- **The rest comes from the flexible pool:** the 368 species that can spawn in both places.
  Assign about 120 cave-capable species to caves, 70 Nether-capable to the Nether and 30
  End-capable to the End, and keep them off surface tables.
- **The surface then keeps about 670 species** (893 surface-capable minus the 220 reserved) to
  spread across 62 sub-regions: about eleven per sub-region with no repeats, which suits
  "roughly 10–20 deliberate species" per area.

**Caveat:** this is a budget, not a list. Encounter lists stay empty until the spawn philosophy
is decided.

## 8. Open items

- **Rivers:** grade, step or keep dry ([`TERRAIN_2026-09-14.md`](TERRAIN_2026-09-14.md) §4).
- **Marshy Marsh:** fill to a shallow bowl if it should read as a marsh.
- **Merges:** Fungal Isle's halves and Plateau East.
- **Rift custom biome:** still wanted; it is painted as windswept gravelly hills for now.
- **Marine regions:** carried from revision 2 without re-measurement.
- **Superseded companion reports:** [`CROSS_SECTIONS.md`](CROSS_SECTIONS.md),
  [`GLACIER_CARVE.md`](GLACIER_CARVE.md), [`SIGHTLINES.md`](SIGHTLINES.md),
  [`BIOME_COVERAGE.md`](BIOME_COVERAGE.md) and [`BIOME_COVERAGE_MATRIX.md`](BIOME_COVERAGE_MATRIX.md)
  describe the 2026-09-13 terrain.
