# Foliage: forest identity, density and landmark trees

**Status: draft, painted and exported 2026-09-14.** The design lives in `data/foliage.json`, the objects in
`kits/structures/foliage/`, placement in `tools/foliage.py`, called by `tools/paint_maps.py`.

The previous paint used WorldPainter's four tree layers (Deciduous, Pine, Swamp, Jungle) at a noise-modulated
density per preset. Every forest came out as one uniform layer: the same few tree shapes, packed, with a
polygon for an edge. This pass replaces that completely.

## 1. What WorldPainter 2.27.1 supports, and the approach

Verified on this install, not assumed:

- **Custom objects.** `CustomObjectManager` loads `bo2, bo3, schematic, nbt, schem` files. A `Bo2Layer` (the
  Custom Objects layer) takes a list of objects, each with a frequency, random rotation, spawn rules, an offset,
  "extend foundation" and a vertical offset. The layers can be built from a script: `tools/worldpainter/paint.js`
  `paintObjects`.
- **Placement rule**, read from `Bo2LayerExporter`'s bytecode. At every column where `x % gridX == 0`,
  `z % gridY == 0` and the layer value `v > 0`, it places one object when `Random.nextInt(density x 64) <= v x v`.
  - With grid 1 and density 1, any `v >= 8` places exactly one object. So a map with 15 at chosen columns
    places objects at exactly those columns, and Python decides spacing, species and size.
  - Which variant of a group lands is WorldPainter's weighted random pick.
- **Rendering.** Above the terrain an object only fills air and plants. It never cuts into a hillside or
  another tree. "Extend foundation" carries the lowest layer's solid blocks down to uneven ground, so trunks
  on slopes do not float.
- **Water.** A flooded column puts the object *on the water surface*, so nothing is placed in water.
  - Plant layers skip flooded columns; the export was checked for this.
- **Rotation turns an object about the painted column.** Measured on the export: 120 sampled 2x2 trunks
  landed in all four quadrants around their column.
  - Placement therefore checks the whole square of each group's `ground_radius` around the column. That is
    every non-leaf block in the object's lowest two layers, so 1 for a 2x2 trunk, 4 for a boulder and 10 for
    the longest fallen log.
  - No blocked column (water margin, bank, creek bed, settlement) is under any rotation.
- **Tested end to end** on a 256-block scratch export before the real one:
  - on flat ground and on a slope, the trunk base landed on the marked column, one block above the ground;
  - every block of an oak, two 2x2 spruces, an ancient spruce, a landmark giant with sunken roots, a sunk
    boulder, a fallen log, a bush and a leaf-litter patch was present.

**So the approach is Custom Objects, not the vanilla tree layers**, which cannot vary size, spacing or
understory by zone.

The objects:

| Source | Count | What |
| --- | --- | --- |
| Vanilla captures | 148 in 19 groups | `/place feature` on scratch pads over RCON, read back from the region files. A powered structure block in SAVE mode writes no file on 1.21.1, which was tried first. Every capture is a different real tree: spruce 6-11 tall, mega spruce 17-27, mega jungle 14-31, fancy oak 5-16, and so on |
| Generated | 53 in 17 groups | Seeded code, byte-identical on rerun: ancient 2x2 spruce 36-51 tall, ancient pine, conifer and broadleaf snags, fallen logs with moss and a root plate, mossy boulders, wind-flagged krummholz, bushes, leaf-litter patches, and six landmark giants |

**Leaf litter, bush, firefly bush and wildflowers** are 1.21.5 blocks. They exist on this server because
VanillaBackport registers them as `minecraft:leaf_litter` and so on, which was checked with `setblock` and
`execute if block`. Litter is used only inside objects. The WorldPainter plant sets use 1.21.1 plants.

## 2. Density: driven by masks, biased low

For each forest type, over the sub-regions assigned to it, on a 4-block grid (`data/foliage.json`
`density_model`):

| Input | Effect |
| --- | --- |
| Distance to the type's own boundary | Density ramps from 0 at the edge to full at `edge_width` blocks in |
| Ragged noise on that distance (96-block scale, +-`ragged` blocks) | The edge and the boundary itself become a torn line, not the polygon |
| Glade noise (320-block scale) | Removes `glade_share` of the area as soft-edged clearings |
| Clump noise (72-block scale) | Gathers stems into groves for copse-like types |
| Slope | Thins from `slope_lo` to `slope_hi` degrees; nothing on cliffs over 40 |
| Elevation | Thins over the 24 blocks below the preset's `treeline_y` |
| Water | Nothing within 3 blocks. Riparian types gain density near water |
| Lone trees | Drawn past the edge into open ground, thinning with the square of distance, up to `reach` |
| Spacing | Every stem keeps (its spacing + the other's) / 2 from every other stem, across types. Big classes go first, so saplings fill gaps rather than crowd giants |
| Size by zone | Each class has core and edge weights, so giants stand in the core and small trees at the edges |
| Understory by zone | Core, mid and edge each set a plant set and coverage, and can clear the grass and flowers under a closed core |
| Floor | Above a core threshold, grass becomes the type's floor mix (podzol, moss, coarse dirt) |
| Clearances | Settlement footprints plus 16 blocks (landmark-tree outposts use their glade instead), and every object's ground square kept 3 blocks from water at block resolution |

**How far you can see**, measured per type: the mean free sightline at eye height in the core, from each
object's solid width one block above its base (`tools/foliage_objects.py` `eye_width`). The previous paint had
no such measure. For scale, vanilla forest reaches about 250 stems per hectare and dark forest over 600.

## 3. Forest identity

Every forest region has its own character, and the difference is built into species, spacing, understory and
floor, not only the biome. Stems are per hectare (10,000 square blocks). "Core" is at least 0.9 of the way
to full density.

| Type | Where | What it is | What you notice inside it | Core stems/ha | Eye-level sightline |
| --- | --- | --- | --- | ---: | ---: |
| **Old-growth spruce** | Peak Pond Hollow | A cathedral of giant 2x2 spruce and pine over a dark mossy floor | Trunks two blocks thick, 20-50 tall and a dozen or more apart; moss, podzol, coarse dirt, boulders, fallen logs, snags; long views along the floor | 17 | 212 |
| **Spruce thicket** | Northgate Isle | Close-set spruce and pine, dark and plentiful, the old growth's opposite | Trunks every few blocks, crowns touching, ferns and berries; you thread through | 129 | 26 |
| Spruce heath | north-east downs | The old growth's ragged fringe: lone spruces over heath | A tree every 30 blocks, rocks and bushes | 9 | 369 |
| Snowbound pines | the Pine Isles | Tall pines standing apart in snow | White ground, dark trunks, scrub at the edges | 35 | 97 |
| Krummholz | Frostpeak strand | Knee- to head-high wind-flagged spruce among boulders | Nothing above your head; everything leans one way | 36 | 48 (you see over it) |
| Treeline scatter | massif and glacier flanks | A thin spray of krummholz up to the snowline | Mostly rock and snow | 5 | 376 |
| Foothill mixed | Viltri foothills | Species sorted by height: oak and birch in hollows, spruce on rises | The wood changes as you climb | 55 | 88 |
| Birch plateau | Viltri Plateau (gym 1) | Tall white birch columns over a flower floor | Pale trunks, lily of the valley, long upland views | 51 | 188 |
| Riparian woods | Lake Viltri hollow, Viltri's Path valley | Oak, birch and azalea crowding the water | Thickest at the bank, open grass upslope | 41 | 154 |
| Dark wood | the Wedge, north | Dark oak roof over giant mushrooms, moss and litter | Dim, but trunks 6-8 apart so you see along the floor | 68 | 63 |
| Broken oakwood | the Wedge, south | The dark wood's lighter slope | Sky patches, ferns, dark oaks thinning out | 47 | 128 |
| Oak parkland | Tilpey south shore | Great spreading oaks alone in long grass | Always the next oak in view | 8 | 637 |
| Birch shore | Tilpey north shore | A bright birch fringe open to the lake | The lake between white trunks | 37 | 261 |
| Copses | Tilpey east shore | Tight oak and birch clumps in meadow | Crossing open grass from grove to grove | 27 | 269 |
| Drowned swamp | Marshy Marsh | Vine-hung swamp oaks crowding the rim of dark water | Crowns to the water's edge, pale snags among them | 26 | 387 |
| Snag fen | Marsh creek | Open wet grass with dead standing trunks | Snags against the sky, bushes, few live trees | 10 | 898 |
| Cherry vale | Shrew Lake shores | Cherry groves in petal lawns | Pink clusters with open grass around each | 13 | 786 |
| Coastal spruce | Long Isle north | Storm-thinned spruce, flagged scrub at the margins | Loose ranks of mid-height conifers | 47 | 67 |
| Mossy broadleaf | Long Isle middle | Big oaks and dark oaks over moss and ferns | Green everywhere, mossy fallen logs | 50 | 98 |
| Emergent jungle | Jungle Isle west | Giant jungle trees over a sea of bushes | You look up at 2x2 trunks, not through a wall | 29 | 214 |
| Jungle edge | Jungle Isle east, Long Isle south | Small jungle trees breaking into grass | Patchy cover, bushes everywhere | 20 | 367 |
| Open country, savanna, heath, badlands, rim, Rift, islets | the plains, coasts and dry uplands | Lone trees and bushes: a tree to walk to | Grass to the horizon | 0.6-5 | kilometres |

### Why the old growth is Peak Pond Hollow

- **The most walked forest on the map.** `tools/critical_legs.py` routes the critical path. It crosses Peak
  Pond Hollow for 1,369 blocks (599 on the gym 3 to 4 leg, 770 on 4 to 5), and gym 4's town stands in it.
  The next most-crossed forest, the Viltri foothills, sees 752.
- **Big enough not to be a novelty patch.** 1.16 km2, 112 ha painted, 58 ha of core.
- **Gentle.** Mean slope 5.4 degrees at y113, so the floor is walkable and seen from underneath.
- **Already spruce country.** It is cold, northern and next to the tarn and the dry ravine.
- **Its contrast is in sight.** Northgate Isle's thicket, the deliberate opposite, is across the strait.
- **Numbers, not vibe.** 17 stems/ha in the core against the thicket's 129; an eye-level sightline of 212
  blocks against 26. 229 ancient spruce (36-51 tall), 76 ancient pine, 738 mega spruce, 355 mega pine. The
  biome is `old_growth_pine_taiga`, previously unused.

## 4. Landmark trees

Five giants, placed by hand from tool candidates and registered as outposts in `data/towns.json`
(`kind: landmark_tree`, no waystone, nothing gated). They are discovery sites, not foliage. Each has a glade
no other stem enters.

- **Siting.** `tools/landmark_trees.py` and a candidate search filtered sites to:
  - at least 250 blocks off the critical path (the 2026-09-14 legs; the validator's rule for landmark trees is now
    200, measured on `data/routes.json`);
  - at least 300 from any settlement;
  - flat ground.
  Candidates were then ranked by how much of the route they are meant to draw people from can see the crown.
- **Sightlines.** `tools/landmark_trees.py check` casts from eye height (1.62) over the terrain *plus the
  planned canopy* (`build/paint/canopy.npz`), to the crown top less 3 blocks. It writes
  `derived/foliage/landmark_sightlines.json`.

| Landmark | Tree | Site | What it does | Off the path | Seen from | Farthest seen |
| --- | --- | --- | --- | ---: | --- | ---: |
| The Great Oak | 40 tall, crown 46 across | (1800, 5184) Pallet Meadows | **Visible from a route.** The first giant a new trainer sees, in open meadow east of the first leg, 355 blocks from the hometown | 339 | 26 of 42 points on the first leg | 1,146 |
| The Sentinel | 75-block spruce | (3264, 1008) Peak Pond Hollow | **A clearing worth finding.** Its spire shows over the old growth from the gym 3 to 4 leg. The clearing, the hidden tarn 142 blocks away and the ravine head are found only by walking in | 390 | 34 of 72 points on leg 3-4; 22 of 24 directions from the clearing's edge at 60 blocks | 1,532 |
| The Patriarch | dark oak, crown 43 across | (4272, 3600) the Wedge ridge | **On a ridge.** Breaks the skyline above the Rift; climbing out of Victory Road to reach it is the discovery | 247 | 58 of 164 points on Victory Road | 2,964 |
| The Cherry Elder | leaning cherry, crown 42 across | (3408, 3840) above Shrew Lake | A colour landmark: pink against the plateau from the first leg and Victory Road's climb | 531 | 71 of 152 points on two legs | 2,668 |
| The Weeping Elder | domed oak with leaf curtains | (5640, 4176) island in Lake Tilpey | **A headland in water.** Open water on every side, seen across the lake; reached by boat or surf | 861 | 25 of 148 points on legs 5-6, 6-7, 7-8 | 1,510 |

*Off the path* is measured on the regenerated `data/routes.json`. *Seen from* and *Farthest seen* are the
reproducible 2026-09-16 survey: `data/routes.json` legs, the canonical heightmap, and the canopy that
`tools/paint_maps.py` writes (sha256 `ce7da822…`). Inputs, per-leg figures and the reproduction check are in
`LANDMARK_SIGHTLINES_POST_RESCALE.md`. Earlier counts in this table could not be regenerated and were replaced.

A sixth design, a jungle kapok, is in the library unused. No jungle headland had useful sightlines: the
best was seen from 11% of its route.

## 5. Limits and what is not verified

- **Canopy estimates.** The canopy used for sightlines is each group's mean height and crown, because
  WorldPainter picks the variant at export.
- **Sightlines.** They are rays over a height surface, not a render; leaves are treated as solid.
- **Density is not yet checked in game.** The flight is that check. The export was checked in the region
  files; see `REEXPORT.md`.
- **Encounters.** Unchanged: spawn tables are still deferred.
