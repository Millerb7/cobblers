# Region layout: rationale and gap list

**Status: draft for review.** The schema of `data/regions.json` is proposed and not
yet approved. No terrain has been edited and no biomes have been painted.

Everything below was measured from `land_8k_16_eroded.png`
(sha256 `526fe220…a860f6`) with the tools in `tools/`. Where the brief and the
terrain disagreed, the terrain won, and each disagreement is listed.

## Where the terrain disagrees with the brief

| Brief said | Terrain measures | Consequence |
| --- | --- | --- |
| Rift floor above sea level | Floor y43.6-54.5, below sea level 62 | The rift is a flooded lake, not a dry canyon |
| Rift sheer-walled | Walls average 21° within 64 blocks of the water; steepest block step on the map is 1.3 blocks | Steep-sided, not sheer |
| Rift widest at its centre | Widest at the **ends** (1,873 and 1,357 blocks); narrowest at the centre, **172 blocks** at D4 | Two basins joined by a strait; the strait is the natural crossing |
| Volcanic cones in the west-centre | Four cones in **E7/F6/F7**, south-east. Nothing in the west-centre exceeds y157 | Volcanic region placed south-east |
| Glacial valley with moraine and meltwater basin | A descending corridor ends at an enclosed lake in D6 (floor y44.5), but its watershed does **not** reach the range, the cross-section is not U-shaped, and no moraine ridge was found | Represented as a lake basin, not a glacial valley |
| Mountain range north / north-west | Confirmed: A1-A3, B2-B4, including a separate massif on the A1 peninsula | As briefed |
| Island chains on the perimeter | Seven islands, 0.71-2.57 km² each | As briefed |
| A flat coastal lowland exists or can be left | None exists. The largest low, flat, coastal body is 0.023 km² | Designated one; flattening is a gap |

Two further facts shape everything downstream:

- **Every summit is clipped flat at y200.** The four cones and the northern peaks have flat tops of 60-110 blocks radius at exactly the ceiling. None has a crater. The cones read as mesas.
- **The playable world has not been rebuilt from this heightmap.** The server world and its Distant Horizons LOD store were exported from the rejected `erosion_land_8k.png`.

## How boundaries were drawn

No boundary is a coordinate or a cell edge. Each is one of these terrain features,
recorded per region in `boundary_basis`:

| Basis | Meaning |
| --- | --- |
| `contour` | A smoothed elevation threshold (radius ~40 blocks) |
| `rim` | Distance to a water body combined with slope |
| `watershed` | A drainage divide from priority-flood routing, so every block is assigned to the water it actually drains into, with hollows filled rather than trapped |
| `coastline` | Distance to open sea combined with elevation |
| `ridge` | A measured crest line |
| `strip_width` | Width of land pinned between two features |
| `nearest_high_core` | Proximity to the nearer of two high cores |
| `land_body` | A separate island |

First drafts that used coordinate cuts produced a rectangular plateau, a flat-bottomed
range and a ruler-straight vale boundary. All were discarded.

## Prevailing wind and rain shadow

**Wind from the west-northwest.** At z3500 a coastal ridge crests at y149, 13-20 blocks
above the interior, and the northern range reaches y167 to its north. Moisture falls on
both, so:

- the **Windward Coast** and the range's northern flanks are wet: dark forest, old spruce, frozen summits;
- the **Leeward Plateau** in their shelter is dry: savanna tableland with a desert core;
- the **Ember Highlands**, leeward and warm, carry no snow even above the treeline.

The coastal ridge is not continuous. North of z3100 there is no ridge, and the plateau's
northern half is sheltered by the range instead.

**Treeline y165** everywhere. **Snowline y165** in the north; none on the Ember Highlands.

## Region rationale

Areas include water. Slope is the mean over land; "flat" is the share of land under 5°.

| Region | Tier | Area | Median y | Flat | Boundary |
| --- | --- | --- | --- | --- | --- |
| Northern Range | wilderness | 5.16 | 131 | 26% | contour y128, A1 massif contour y110, foreshore by strip width |
| Windward Coast | route | 2.85 | 104 | 46% | watershed to the west sea |
| Leeward Plateau | hub | 2.89 | 130 | 72% | contour y120 |
| Sunken Rift | route | 3.77 | 89 | 15% | rim |
| Stillwater Basin | hub | 3.15 | 94 | 60% | watershed of the D6 lake |
| Eastern Downs | hub | 8.61 | 109 | 56% | watersheds to the north and east seas |
| Ember Highlands | wilderness | 3.46 | 149 | 60% | contour y135 around the cones |
| Lakeshore Vale | route | 5.82 | 117 | 60% | watershed to the south sea |
| Strand Flats | route | 0.77 | 85 | 38% | coastline |
| Northern Isles | wilderness | 2.72 | 90 | 26% | three land bodies |
| Jungle Isle | wilderness | 2.51 | 104 | 20% | one land body |
| Southern Isles | wilderness | 4.71 | 102 | 29% | three land bodies |

**Northern Range.** The main massif is the smoothed y128 contour: the B4 foothill peaks
join it at y128 and separate at y132, so that threshold keeps them together. The A1
summit never joins by any contour down to y90 because its neck is low, so it is bounded
by its own y110 contour and its shore is included to keep the region contiguous. A thin
y120-128 halo the plateau contour would otherwise wrap around the range is reassigned
by nearest high core. The north-shore strip between the mountains and the sea belongs
here as foreshore. It is a compromise, explained in the gap list.

**Windward Coast.** Land draining to the western sea. Its inland edge is therefore the
real drainage divide, which follows the coastal ridge where one exists.

**Leeward Plateau.** The y120 contour around the D2 tableland. The flattest region on the
map and the clearest rain-shadow case.

**Sunken Rift.** The flooded rift plus the walls enclosing it: land within 240 blocks of
the water that is steeper than 9° or lower than y100. The rim measures near y99. The
strait at D4 is the only narrow crossing.

**Stillwater Basin.** Exactly the land that drains into the enclosed D6 lake. Its northern
edge contains straight segments where priority-flood crosses flat spill ground; those
are an artifact of the method on flats, not a design choice.

**Eastern Downs.** Land draining to the north and east seas plus the rift's north shore.
The largest region, and the one most at risk of reading as generic.

**Ember Highlands.** The y135 contour connected to the four cones, which takes in the y150
tableland in F5 they stand on.

**Lakeshore Vale.** Land draining to the south sea plus the rift's south shore, less the
Strand Flats.

**Strand Flats.** The lowest south-coast ground: y100 or lower, within 700 blocks of the
sea. The mask is eroded by 64 blocks to remove the thin beach ribbon along the rest of
the coast and regrown by the same amount, leaving the one genuinely wide body.

**Islands.** Grouped by position and climate: cold windward isles in the north, a single
long jungle island in the east, warm isles in the south and west. The F1 islet is
mushroom fields, deliberately.

## Buildable sites

`tools/find_sites.py` was run over the whole map for flat squares at least 48 blocks
across, no steeper than 4°, and at least 2 blocks above sea level.

**The raw ranking is dominated by clipped summits.** Five of the top seven, including
the largest (334 blocks square) and second (251), are mountain and cone tops sitting at
exactly y200. Clipping flattened them into the largest level ground on the map. The tool
now takes `--max-y`, and the list below uses `--max-y 190`.

| Rank | Size | Centre | Cell | Height | Region |
| --- | --- | --- | --- | --- | --- |
| 1 | 139 | 5646, 3302 | D6 | y75-78 | Stillwater Basin |
| 2 | 114 | 1224, 4170 | E2 | y133-137 | Leeward Plateau |
| 3 | 111 | 4841, 5816 | F5 | y162-164 | Ember Highlands |
| 4 | 107 | 6446, 3527 | D7 | y92-94 | Eastern Downs |
| 5 | 106 | 3149, 2768 | C4 | y122-126 | Eastern Downs |
| 6 | 104 | 5881, 3378 | D6 | y67-71 | Stillwater Basin |
| 7 | 104 | 1426, 3837 | D2 | y131-134 | Leeward Plateau |
| 8 | 104 | 6805, 4407 | E7 | y107-109 | Eastern Downs |
| 9 | 103 | 5063, 2724 | C5 | y108-112 | Stillwater Basin |
| 10 | 103 | 5188, 2872 | C6 | y105-108 | Stillwater Basin |

Of the top fifteen, six fall in Stillwater Basin, five in the Eastern Downs, three on the
Leeward Plateau and one in the Ember Highlands. **Lakeshore Vale holds none** and the
Strand Flats hold none.

Tiering follows this. Stillwater Basin, the Eastern Downs and the Leeward Plateau are the
three hubs because they contain the level ground a settlement needs. Lakeshore Vale was
first tiered as a hub on its 60% flat share, then moved to route: its flat ground comes in
small patches, with no square of 99 blocks or more.

## Distinguishable at 128 blocks

Grass and foliage colour in Minecraft is driven by biome, so a region's biome set is
itself its first signature. Each region's `distinctness` block names ground palette,
vegetation density, water and sightlines. The closest pairs, and what separates them:

| Neighbours | Separated by |
| --- | --- |
| Eastern Downs / Lakeshore Vale | Open grassland with long views, against closed forest canopy |
| Lakeshore Vale / Windward Coast | Bright forest with flower glades, against a dark, mossy closed canopy |
| Leeward Plateau / Windward Coast | Dry yellow treeless tableland, against the densest wet forest |
| Northern Range / Eastern Downs | Snow and slope, against level green grass |

## Biome tag coverage

Spawn conditions key off biome tags, so every tag the spawn tables use has to appear
somewhere. Tag membership was resolved from the game and mod jars actually loaded,
not from documentation: vanilla 1.21.1, all mods, and the required `datapacks/`
folder. The optional `datapacks/extra/` packs, including Terralith, are not loaded.

| | Tags |
| --- | --- |
| Overworld tags referenced by spawn conditions | 58 |
| Covered by the painted biomes alone | 48 |
| Covered once the five tag overlays exist | 53 |

**Eight overworld spawn tags cannot be reached by any vanilla biome.** Five of them are
covered here by adding a region-exclusive biome to the tag in our generated datapack:

| Tag | Spawn entries | Overlay biome | Region |
| --- | --- | --- | --- |
| `#cobblemon:is_tropical_island` | 324 | jungle, bamboo_jungle, sparse_jungle | Jungle Isle, Southern Isles |
| `#cobblemon:is_lush` | 194 | flower_forest | Lakeshore Vale |
| `#cobblemon:is_snowy_forest` | 125 | grove | Northern Range |
| `#cobblemon:is_volcanic` | 81 | eroded_badlands | Ember Highlands |
| `#cobblemon:is_thermal` | 35 | eroded_badlands | Ember Highlands |

Without these overlays the Ember Highlands would spawn **no** volcanic-tagged Pokémon at
all. The overlay biomes are each used by exactly one region, which the design check
enforces.

## Gap list

### Biome tags not covered

| Tag | Spawn entries | Why |
| --- | --- | --- |
| `#cobblemon:is_sky` | 186 | Only on Terralith skylands. No overworld surface equivalent. |
| `#cobblemon:is_dripstone` | 70 | Underground cave biome |
| `#cobblemon:is_deep_dark` | 59 | Underground cave biome |
| `#cobblemon:is_cave` | 10 | Underground cave biomes |
| `#cobblemon:is_shrubland` | 4 | Modded biomes only; no region-exclusive vanilla candidate |

The three cave tags need biomes placed underground. Whether WorldPainter can paint 3D
cave biomes into a 1.21.1 export is **unverified** and should become an experiment
before cave design starts. Also note five more tags are covered only by the overlays,
so spawn design depends on that datapack work landing.

### Cells with no region

**C8** only. It is open sea.

### Terrain that resists a sensible assignment

1. **No flat coastal lowland exists.** Strand Flats is designated for the role but only 38% of its land is under 5°. Meeting the brief needs a terrain flattening pass, which is out of scope here.
2. **Summits clipped at y200.** The cones read as flat mesas and have no craters. Fixing it needs headroom above y200 in the export, which conflicts with the decided playable band.
3. **Islands cannot be contiguous.** Northern Isles and Southern Isles are three bodies each.
4. **The range's north foreshore is a compromise.** It is 0.93 km² of median-y97 lowland, only 9% of it touching mountain ground. It drains north and is cut off from the Windward Coast by the A1 massif, and leaving it in the Downs stretched that region across almost the entire map width.
5. **The Eastern Downs is the largest region at 8.61 km².** If it proves unidentifiable in play, split it along the divide between its north and east watersheds.
6. **Straight watershed segments** on Stillwater Basin's northern edge, from flat spill ground.
7. **A thin rift-wall finger** reaches into Stillwater Basin in E5-E6.
8. **The glacial valley in the brief is not in the terrain** and is not represented.
9. **Flat building ground is scarce everywhere.** The largest genuinely flat square below the ceiling is 139 blocks across. Settlements larger than that will need terracing or local flattening.

## Proposed `regions.json` schema

Top level:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string | `cobblers.regions/1` |
| `schema_status` | enum | `proposed` until approved |
| `status` | enum | `draft`, `approved` |
| `computed_from_sha256` | string | Heightmap the measurements and polygons came from |
| `geometry` | object | Raster resolution, polygon tolerance, coverage statement |
| `climate` | object | `prevailing_wind_from`, `basis`, `treeline_y`, `snowline` |
| `sea_biomes` | object | Ocean biome shares and the rules producing them |
| `tag_overlays` | array | `{tag, add_biomes, scoped_to, reason}` |
| `tag_coverage` | object | Counts and the uncovered list |
| `regions` | array | One entry per region |

Each region:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable snake_case id |
| `display_name` | string | Player-facing name |
| `tier` | enum | `hub`, `route`, `wilderness` |
| `character` | string | One-sentence identity |
| `contiguous`, `pieces` | bool, int | False only for archipelagos |
| `cells` | array | Cell ids ordered by share |
| `cell_share` | object | Fraction of the region in each cell |
| `bounds` | object | Block bounding box |
| `climate` | object | `exposure`, `moisture`, `temperature` |
| `boundary_basis` | array | `{basis, detail}`, one of the bases above |
| `measured` | object | Area, elevation percentiles, slope, treeline share, distance to sea |
| `biomes` | object | `primary`, `secondary`, and `bands` of `{biome, share, rule}` |
| `biome_tags` | array | Resolved `is_*` tags the region carries, overlays included |
| `tag_overlays_required` | array | `{tag, biome}` this region depends on |
| `distinctness` | object | `ground`, `vegetation`, `water`, `sightlines`, `signature_at_128_blocks` |
| `notes` | array | Caveats |
| `polygons` | array | Outer rings as `[x, z]` block coordinates, one per piece |

Once approved, `tools/validate_data.py` should check: ids unique; cells valid; biome ids
present in the loaded registry; band shares sum to one; `pieces` equals the polygon
count; `computed_from_sha256` matches `data/world.json`; every overlay biome used by
exactly one region; and every land block inside exactly one polygon.

## Reproducing the measurements

```bash
python tools/cell_stats.py --source-root <source root>
python tools/landforms.py  --source-root <source root>
python tools/find_sites.py --source-root <source root> --min-size 32 --max-slope 4
```

All three verify the heightmap hash before reading it. Their output goes to `derived/`.
