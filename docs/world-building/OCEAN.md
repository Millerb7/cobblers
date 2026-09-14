# The ocean: depth, seabed, marine regions and what lies underneath

> **Note 2026-09-14.** The coastline changed with the carved terrain revision. The marine regions below are carried into `cobblers.regions/3` unchanged and have not been re-measured.

**Status: section 2 (the revised import) is applied.** Since 2026-09-13 the world
`cobblers-10240` uses it; `REEXPORT.md` has the export and the measured seabed. Everything
else here is still a proposal: no seabed pass, no biome painting, no content. The measurements come from the pinned heightmap
(`land_8k_16_eroded.png`, sha256 `526fe220…`) sampled on the 8-block raster the region
plan uses. Planned regions are in `data/regions.json` under `marine_regions`, all with
status `planned`.

## 1. How deep the sea is today

The import in `data/world.json` maps heightmap value `f` to
`y = 40 + (f − 0.156863) / 0.839215 × 160` and clamps the result to 40–200. The clamp
matters: every sea column whose source value is below 0.156863 lands on exactly y40.

| Seabed measure (sea columns inside 0–8191) | Current import | Same line, extended below y40 |
| --- | ---: | ---: |
| Share of the 8192 map that is sea | 30.8% | 30.8% |
| Columns sitting at exactly y40 | **75.9%** | none |
| Median seabed | y40 | **y21.5** |
| 5th / 25th / 75th / 95th percentile | 40 / 40 / 40 / 57 | 10 / 14 / 39 / 57 |
| Seabed at or below y20 | 0% | 46.9% |
| Seabed at or below y30 | 0% | 63.6% |
| Median water column | 22 blocks | 40.5 blocks |

By distance from land:

| Distance from land | Current median | Extended: 10th / median / 90th percentile |
| --- | ---: | --- |
| 0–64 blocks | y54 | 47 / 54 / 60 |
| 64–128 | y40 | 31 / 38 / 45 |
| 128–256 | y40 | 16 / 21 / 29 |
| 256–512 | y40 | 10 / 13 / 16 |
| 512 and beyond | y40 | 10 / 10 / 10 |

**What this means:**
- **Three quarters of the seabed is a flat plain 22 blocks down.** Nothing on it is out of
  reach of one breath, and it reads the same everywhere.
- **The source heightmap already has real depth.** The clamp threw it away. The erosion
  simulation carved a coastal slope and channels that the clamp flattened into the y40
  floor.
- **The source has its own floor too.** Beyond about 400 blocks from land the source value
  is near zero, so even the extended mapping gives a flat plain at y10. The deep basin needs
  authored relief either way.
- **The natural shelf is narrow.** The water deepens to y38 within 128 blocks of the coast
  and to y21 within 256.

## 2. The revised import

**Proposal:** keep the land exactly as it is and extend the same straight line down to
`f = 0`:

| Parameter | Now | Proposed |
| --- | --- | --- |
| `low_in` | 0.156863 | 0.0 |
| `low_out` | 40 | 10.093 |
| `high_in` | 0.996078 | 0.996078 (unchanged) |
| `high_out` | 200 | 200 (unchanged) |
| `water_level` | 62 | 62 (unchanged) |

- **Open water reaches y20 or below.** The median sea column goes from y40 to y21.5, and
  nearly half the sea is at y20 or lower.
- **The land does not move.** At 8-block sampling, no land or rift column has a source
  value below 0.156863. Every land column therefore sits on the part of the line that does
  not change. Rounding moves 0.02% of land columns by one block.
- **Integer `low_out` costs something.** If WorldPainter's import dialog only takes whole
  numbers (not verified), `low_out` 10 shifts 4.3% of land columns by exactly one block.
  To avoid that, write a derived 16-bit heightmap with a fixed 1/256-block mapping. Land
  pixels would carry their current Y exactly and sea pixels the extended Y. That file lives
  in `source/` like the original, with its sha256 recorded in `world.json`.
- **The 10.093 floor is not the design floor.** The seabed pass in section 4 shapes the
  shelf, basin and features on top of this surface.

### What changes if we re-import

| Area | Change |
| --- | --- |
| Land, rift, inland lakes | None at 8-block sampling. Check at full resolution with a height diff before accepting |
| Sea columns | 76% get deeper, by up to 30 blocks. WorldPainter floods everything below y62 as before |
| The 10240 canvas | The export has to cover the 1024-block border margin (see `DIMENSIONS_AND_BORDERS.md`). The margin source value is 0, so it imports as a y10 plain for the seabed pass to shape |
| World seed | A new import gets a new seed unless the current one is set. The seed decides where the Nether, the End and every candidate structure position fall, so it must be carried over or everything that depends on it recomputed |
| `data/world.json` | The import block changes, plus a new `border` entry and the derived-heightmap hash if that route is used |
| Derived measures | Anything that reads water depth (cell stats, landforms, cross sections through the sea) is recomputed. Land statistics and region polygons stay the same |
| Ocean biome rules | The deep variants follow depth, so the depth has to be settled **before the biome pass** |
| Spawns | The `is_deep_ocean` entries with `maxY 48` (Relicanth, Huntail, Gorebyss, Clamperl) go from 8 blocks of qualifying water to 20–38. Entries with `maxY 13` become physically possible where the basin is deep enough |
| Existing saves | None carry over; the live world is replaced by the re-export anyway |

### Could a WorldPainter pass deepen it instead?

**It could, but it is the worse option.** WorldPainter's lower and flatten brushes, or a
`wpscript` that sets height per column, can cut the seabed of the existing `.world`
without re-importing.

The catch is that the existing world stores the clamped surface. The erosion detail below
y40 is not in it, so a WorldPainter pass would invent depth from distance to land. It could
not recover the channels and slopes the source already has. Re-importing also keeps any
painted layers only through WorldPainter's import-into-existing-world path, which is not
verified.

Nothing has been painted yet, so there is nothing to lose. **Re-import first, then use
WorldPainter or a script only for the authored relief** in section 4.

## 3. The ocean as design space

With the 10240 border the world is 104.9 km²:

| | km² | Share of the world |
| --- | ---: | ---: |
| Landmass (every region, rift included) | 46.4 | 44% |
| Sea inside the 0–8191 box | 20.7 | 20% |
| Sea in the border margin | 37.7 | 36% |
| **All sea** | **58.4** | **56%** |

The sea is 31% of the 8192 map, roughly the "third" the brief assumes. With the margin it
becomes **more than half** of the world. It cannot be filler at that size, so it is split
into five marine regions. They sit alongside the fourteen land regions rather than inside
them.

| Marine region | Tier | Where | Area km² (inside box / margin) | Temperature | Shelf | Named content |
| --- | --- | --- | --- | --- | ---: | --- |
| **Frostwater Shelf** | wilderness | north of z2600, under the Northern Range and the Northern Isles | 12.0 (7.5 / 4.5) | cold, frozen north of z1300 | 240 | kelp forest, iceberg habitats, shipwreck cove |
| **Windward Deep** | wilderness | the exposed west | 5.8 (1.4 / 4.5) | temperate | 160 | ocean monument; deep water closest to shore |
| **Eastern Reach** | route | east, off the Eastern Downs | 6.5 (2.1 / 4.5) | lukewarm | 320 | sea lane; Misty's gym on the shelf if reused |
| **Southern Shallows** | route | south of z5200 and around Jungle Isle | 14.2 (9.7 / 4.5) | warm | 400 | coral reefs, buried treasure |
| **The Outer Deep** | destination | 512–1024 blocks beyond the landmass, to the border | 19.9 (0 / 19.9) | graded north to south | none | abyssal plain, seamounts, the trench set piece |

**How the zones follow the land plan:**
- **Temperature follows the land climate.** Cold under the cold regions, warm under the warm
  isles. The windward west stays temperate but deep, matching the wet exposed coast and its
  coastal ridge.
- **The two route zones are the sea lanes** between hubs on the east and south coasts.
- **The Outer Deep is the edge of the world.** Nothing in it is visible from the surface,
  and the border wall ends it.

## 4. The seabed pass

This is its own terrain pass, done after the re-import and before the biome pass. It is
specified here and not built.

### Profile

Every zone uses the same four-part profile, with the shelf width set per zone.

| Part | Depth | Width |
| --- | --- | --- |
| Shelf | y60 at the shore to y46 | 160–400 blocks, by zone |
| Shelf break | y46 to y28 | 80 blocks |
| Slope | y28 to y18 | 400 blocks |
| Basin | y18 to y10 | 600 blocks, then flat |
| Abyssal plain (Outer Deep only) | y8 | to the border |

The planned seabed per zone, from that profile:

| Zone | 10th pct | Median | 90th pct | Extended import (inside the box), median |
| --- | ---: | ---: | ---: | ---: |
| Frostwater Shelf | y20 | y42 | y57 | y23 |
| Windward Deep | y14 | y22 | y49 | y19 |
| Eastern Reach | y16 | y26 | y54 | y13 |
| Southern Shallows | y23 | y51 | y58 | y24 |
| Outer Deep | y8 | y8 | y8 | n/a |

**What the pass does:**
- **Widens the shelf.** Where the planned shelf is shallower than the imported surface, the
  pass fills up to it. This happens mostly in the warm south, where the natural shelf is
  narrow.
- **Keeps the natural relief elsewhere.** Where the imported surface is deeper than the
  profile, the pass keeps the imported surface. The erosion channels survive as submarine
  canyons.

### Features

| Feature | Where | Shape |
| --- | --- | --- |
| **The trench** | south-east margin, curving with the border from (9000, 5200) through (8200, 7400) to (6200, 8900) | 60–120 blocks wide, floor y−20 to y−40 in deepslate; the only water below y0 |
| **Seamounts** (5) | (−600, 2200), (−500, 6000), (4200, −700), (9000, 1800), (1500, 8900) | summits y46–54, so each one's top sits in sunlit water above a dark plain; kelp on top |
| **Ridges** | one along the shelf break under the Windward Coast, one across the Frostwater Shelf between the range and the isles | 10–20 blocks above the surrounding slope, with gaps that act as passages |
| **Submarine canyons** | kept from the imported erosion channels where they cross the shelf | no new cutting |

The positions are geometry for review, recorded under `the_outer_deep.features`. None of
them has been checked against sightlines or the concealment model (Step 3).

### Biomes

The shares are area-weighted over all five zones. Each zone's own rules are in
`regions.json`.

| Biome | Share of the sea | Where |
| --- | ---: | --- |
| `deep_lukewarm_ocean` | 27.6% | Eastern Reach and Southern Shallows basins; south half of the Outer Deep |
| `deep_frozen_ocean` | 20.0% | Frostwater north of z1300; north of the Outer Deep |
| `deep_ocean` | 12.6% | Windward Deep; west-central Outer Deep |
| `warm_ocean` | 10.8% | Southern Shallows shelf within 220 blocks of land |
| `lukewarm_ocean` | 10.8% | Eastern Reach shelf; outer Southern Shallows shelf |
| `cold_ocean` | 6.7% | Frostwater shelf |
| `deep_cold_ocean` | 5.3% | Frostwater z1300–2600; Outer Deep band z1500–3500 |
| `frozen_ocean` | 4.5% | Frostwater north of z1300, 120+ blocks out |
| `ocean` | 1.8% | Windward shelf |

**How this changes the earlier sea plan:**
- **All nine ocean biomes are still planned.** Spawn coverage in `BIOME_COVERAGE.md` is
  unaffected. `tools/spawn_biomes.py` reads `sea_biomes.shares`, which now holds these
  totals, with the old plan kept under `previous_plan`.
- **The deep variants rise from 14% to 66% of the sea.** The old plan assumed a shallow sea
  with no margin; this one is mostly open water.

### Kelp, seagrass, coral

A WorldPainter export generates none of these. Each has to be placed by a WorldPainter
layer or the post-export scatter script (see `WORLDGEN_FEATURES.md`). Where each goes
follows vanilla's own temperature rules, so the ocean reads correctly and the spawn
conditions that look at these blocks work.

| Flora | Vanilla biomes | Planned in | Depth |
| --- | --- | --- | --- |
| Kelp | ocean, lukewarm, cold, and their deep variants; not warm or frozen | Frostwater Shelf cold water, Windward shelf and upper slope, Eastern Reach shelf, seamount summits | y28–58 |
| Seagrass | every ocean except frozen | every shelf outside frozen water | y40–60 |
| Coral reefs, coral fans, sea pickles | warm_ocean only | Southern Shallows warm shelf | y46–60 |
| Dead coral | none naturally | one or two bleached patches on the reef edge | y46–58 |

**Coral is not decoration.** Corsola spawns need `#minecraft:corals` or
`#minecraft:coral_blocks` nearby, and Cursola needs `#cobblemon:dead_coral` (read from the
spawn files). No reef means no Corsola line.

**Ice:** frozen oceans freeze at the surface because of their temperature. Ice sheets
north of z1300 are expected to form on their own, but not verified.

## 5. Underwater discovery

**The principle:** nothing below is visible from the surface, so the ocean rewards
systematic search. The sea is lit, then dim, then dark, and each step down needs more
equipment. That gates content without any authored lock.

### Depth as gating

| Tier | Depth | What the player faces | What gets them there | Earliest |
| --- | --- | --- | --- | --- |
| 0 Sunlit | shelf, y46–62 | one breath covers it | nothing | from the start |
| 1 Dim | break and slope, y28–46 | the bottom is dark and air runs out on the way back | Respiration, a turtle shell, air pockets under doors or signs | early to mid game |
| 2 Dark | basin, y8–28 | beyond one breath; sky light is gone | Water Breathing potions (Nether wart), or a conduit | after gym 7, the first Nether trip |
| 3 Abyss | the trench, below y0 | a long descent in total darkness | Water Breathing plus light, or a conduit chain | late game |

**How light drops off:**
- Water is expected to cut sky light by one level per block, so light is gone about 15
  blocks down. This is not verified in game.
- The spawn files already use this. Relicanth's rare entry needs sky light 0–7 below y48,
  and several species split `canSeeSky` from sky light 8–15.
- Cobblemon's own spawn data draws the line at y48. Mantine, Mantyke and Pyukumuku need
  `minY 48` (the shelf). The deep-ocean entries need `maxY 48`. The shelf break is therefore
  also the boundary between two spawn pools.

**Two things could undo this gating** and need proof before relying on it:
- **Pokémon riding.** Whether a ridden water Pokémon lets a player breathe or descend fast
  underwater is not verified. That is a proposed EXP-015.
- **Hearts of the sea.** A conduit gives unlimited breath in range. Hearts of the sea should
  sit only in tier-2 sites. Every buried-treasure chest is a hand-placed loot table, so this
  is controllable.

### What goes down there

The content per marine region adds up to 34 of the 150 scatter placements (see
`STRUCTURE_DECISIONS.md`), plus named sites and the set piece.

| Tier | Frostwater Shelf | Windward Deep | Eastern Reach | Southern Shallows | Outer Deep |
| --- | --- | --- | --- | --- | --- |
| 0 | iceberg habitat ×2, fishing-boat wreck | fishing-boat wreck | fishing-boat wreck ×2, Misty's gym (if reused) | reef habitats ×3, beached shipwreck ×2, buried treasure ×3 (no heart) | seamount-summit kelp gardens |
| 1 | cold ocean ruins ×3, shipwreck ×2 | shipwreck ×3, ocean ruined portal, Cobblemon underwater fissure fossil | warm ocean ruins ×2, ocean ruined portal, deep sea spire habitat | warm ocean ruins ×3, submerged-spike fossil | nothing |
| 2 | shipwreck cove (lush) | **ocean monument**, submerged forge ruins | shipwreck cove (submerged) | buried treasure with a heart of the sea ×2 | shipwreck cove (magma), a sunken RS ocean pyramid |
| 3 | | | | | **the trench set piece** |

**Fossils underwater:** Cobblemon ships ocean fossil features (submerged impact, submerged
spike, underwater fissure, hydrothermal vents). They are templates with suspicious blocks,
placed as objects (see `WORLDGEN_FEATURES.md`). They make the slope a fossil-hunting ground
that is separate from the Mining Town's underground fossils.

### The set piece: The Maelstrom Trench

A single authored descent at the end of the south-east margin, where the Outer Deep
curves along the border.

**The approach:**
- On the surface there is nothing, only a slightly darker patch of open water beyond the
  last seamount.
- The seamount at (9000, 1800) is the distance cue: a summit at y46 with a ring of sea
  lanterns, visible to anyone already diving there. This follows the concealment rule,
  "signposted at distance, concealed at close range", with the sign underwater.

**The descent:**
- The trench walls are deepslate and dark prismarine, spiralling down.
- Glow lichen traces a route that can only be seen from inside the trench.
- Three sealed air-pocket chambers break the descent. Each holds a conduit frame that is
  missing its heart.

**The bottom (y−30 to y−40):**
- A flooded shrine with three door locks.
- Each lock takes a key item kept in one of the three shipwreck coves, one in each of
  three different marine regions. Finding them is the systematic search.
- Opening the shrine gives the encounter: Lugia, if the legendary recommendation in
  `STRUCTURE_DECISIONS.md` is accepted, otherwise the campaign's own sea guardian. It also
  gives the last heart of the sea, so the player can build a conduit at the bottom.

**What it needs:**
- It is gated by depth (tier 3) and by the key search, not by a badge.
- It stays after the League, but players can reach it as soon as they can breathe
  underwater.
- The build method follows Step 3's decision. Per EXP-013, it cannot use structure data.
  Any spawn or check keyed to structures has to be replaced with position-based conditions
  or Habitat Blocks.

### Which ocean structures the pack expects, and can they be hand-placed?

EXP-013 settles the general question. No in-game placement method writes structure data.
`/place template` at an explicit Y lands correctly, while `/place structure` and
`/place jigsaw` bury rigid pieces at seed-terrain height. So every ocean structure can be
pasted as blocks, and every system that reads structure data will ignore it.

| Structure | Source | Built from | Hand-placeable? | What stops working |
| --- | --- | --- | --- | --- |
| Ocean monument | vanilla | code, no template | **Not as a template.** Capture one generated in a disposable world in structure-block tiles (it is 58 blocks wide, over the 48-block limit), or try `/place structure` (monuments sit at sea level, not on the heightmap; not tested) | guardian spawning (a structure spawn override), elder guardians unless pasted as entities, the Qwilfish and Overqwil monument entries, explorer maps |
| Ocean ruins, cold and warm | vanilla | templates | yes | the ocean-ruins preset (Dratini line, Relicanth entries), treasure maps in their chests |
| Shipwrecks and beached shipwrecks | vanilla | templates | yes | Dhelmise's `#minecraft:shipwreck` entries, treasure maps |
| Buried treasure | vanilla | code, one chest | yes, as a chest with a loot table | its treasure-map targets |
| Ruined portal (ocean) | vanilla | templates | yes | nothing that matters |
| Shipwreck coves: lush, magma, submerged | Cobblemon | jigsaw (depth 20) | yes; assemble the pieces once in a disposable world, then capture them | 84, 7 and 131 spawn entries (many need `maxY 13`, so they need real depth as well as structure data); the trial spawners and starter-move chests still work as blocks |
| Fishing boats (beach, deep, warm) | Cobblemon | templates | yes | nothing: loot barrel only |
| Deep sea spire, drifting icebergs | Cobblemon habitats | templates | yes | nothing: Habitat Blocks are block entities and do not read structure data |
| Submerged forge ruins | Cobblemon | template | yes | 29 `#cobblemon:ruin` entries |
| Misty's gym | Cobbleverse | template | yes (EXP-013: templates keep the RCT spawner) | `gym_map` and LumyMon's cartographer map |
| RS ocean ancient city, mineshaft, outpost, pyramid, temple, village | Repurposed Structures | jigsaw, RS type | yes after capture | RS's ocean village carries `#minecraft:village` (185 entries) |

**Pasted builds also carry jigsaw blocks.** Captured jigsaw assemblies have to be flattened
first: EXP-014 found WorldPainter pastes `minecraft:jigsaw` blocks verbatim.

### Water-gated species: do they have a real home?

From the spawn files the server actually loads (weight above 0):

| Group | Species | What they need | Home under the current world | Home under this plan |
| --- | --- | --- | --- | --- |
| Ocean only | Alomomola, Finizen, Palafin, Lapras, Wailmer, Wailord | any ocean biome (surface, submerged or fishing) | yes, but in a 22-block sea | yes, in every marine region |
| Ocean only, warm | Bruxish | `warm_ocean` | only if the biome pass paints warm_ocean | the Southern Shallows reef shelf |
| Ocean only, shallow warm | Mantine, Mantyke | lukewarm or warm ocean, `minY 48` | yes | Eastern Reach and Southern Shallows shelves |
| Ocean only, deep or warm | Luvdisc | deep oceans or warm_ocean | shallowly | the basins and the reefs |
| Ocean, structure-gated | Dhelmise | mostly `#minecraft:shipwreck` or a shipwreck cove below y13; one rare entry with no structure | **rare entry only** | rare entry only, until structure entries are replaced |
| Deep, `maxY 48` | Relicanth, Huntail, Gorebyss, Clamperl | `is_deep_ocean` below y48; Relicanth also sky light 0–7 anywhere in the overworld | 8 blocks of qualifying water | 20–38 blocks in the basins, and total darkness at tier 2 |
| Coral-bound | Corsola, Cursola | coral blocks, or dead coral, nearby | **none**: the export has no coral | the Southern Shallows reefs and the dead-coral patches |
| Warm seafloor and beaches | Pyukumuku (`minY 48` or warm), Mareanie, Toxapex (warm_ocean and beaches) | shelf and shore | partly | the warm shelf |
| Ultra-rare | Nihilego (submerged), Tornadus (surface) | any ocean | yes | yes; the Outer Deep is the natural stage |
| Shipwreck-cove pools | 41 species through `#cobblemon:shipwreck_cove`, below y13 | a cove with structure data and deep water | none | depth yes; structure data no. These are the entries to replace with position-based or Habitat Block spawns |

**What the data says:**
- **No water species depends only on a structure.** Every one has at least one entry keyed
  to a biome alone. Structure-only species are listed in `TOWNS_AND_VILLAGES.md`: the
  Sinistea and Poltchageist lines, plus land and Nether species.
- **Two species truly lack a home today.** Corsola and Cursola need coral, which does not
  exist in the export.
- **Two groups are thin.** The deep species have only 8 blocks of qualifying water. The
  cove pools are unreachable, because they need both depth and structure data.

## Open questions and experiments

1. Can WorldPainter's import take a fractional `low_out`? If not, use the derived-heightmap
   route (section 2).
2. How does WorldPainter extend the canvas to 10240 with the landmass kept at world
   0–8191: an import offset, padding the PNG, or shifting the world? Not verified.
3. EXP-015 (proposed): does riding a water Pokémon grant breath or fast descent?
4. Can `/place structure minecraft:monument` land correctly on painted terrain? Monuments
   use sea level, not the heightmap; not tested.
5. Do frozen-ocean surfaces freeze in a WorldPainter export? Expected yes from biome
   temperature; not verified.
6. Does water cut sky light by one level per block? Measure it in game before the dark
   tiers are tuned.
