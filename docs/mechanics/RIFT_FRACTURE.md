# The Rift as a fracture: aura and scenery (second pass)

**Status: design for the owner's review, with one prototype stretch built on a fresh staging export
(`cobblers-dryrun5`) by `tools/rift_fracture.py` from `data/rift_fracture.json`. Nothing full-scale, nothing in the
live world.** It replaces the first pass (`data/rift.json` and `tools/rift_build.py`, removed 2026-09-22, in git history: a rim wall with regular spires,
a purple biome over whole chunks, floor specks), which read as a fence, vanished at range, leaked its sky outside the
rim, looked the same everywhere, and read as noise and as vanilla obsidian.

Gating (zones, guards, the zone check) stays as `docs/mechanics/RIFT_ZONES.md` designs it; this document only says
where the scenery meets it.

## 1. What the world is (measured, 2026-09-22)

**Geometry** (canonical heightmap, a cross-section every 100 blocks along each branch):

- **Floor** y82-88 the whole length, flat and 58-282 blocks wide (403 at the spur's mouth).
- **Rims** y91-151. The trunk's east rim is the high one (146-151 between the fork and the spur); the west rim is
  113-148.
- **Depth** 17-63. Deepest in the trunk between the fork and the spur, 53-63 at x3900-4110 z3580-3800; 29-33 at the
  League; shallow at the apex (7-23) and along the spur (16-22), and nearly nothing where the spur opens into the
  trunk.
- **Width**, rim to rim: narrowest 229-238, at the apex and just above the arms' split (3949, 4781); widest 525-648,
  where the spur meets the trunk (x3600-3700 z3216-3377).
- **Walls** average 13-22 degrees, and the steepest 4-block step anywhere is 45. It is a valley, not a fracture.
- **The two southern arms share their first 850 blocks** (RIFT_ZONES section 1).

**Spawns.**
- **How they're assigned:** by sub-region, in exclusive curated coordinate-box pools. The four Rift sub-regions
  (`rift_trunk`, `rift_west_spur`, `rift_south_west_arm`, `rift_south_east_arm`) have 10 entries each. Every entry is
  conditioned on the biome `minecraft:windswept_gravelly_hills`.
- **The route pool:** Victory Road's pool takes its entries from the sub-regions it passes through. In the compiled
  pack, 2,120 spawn records in the Rift carry that biome condition: 1,326 in the sub-region pools and 794 in Victory
  Road's.
- **Blocks that condition spawns** (`data/spawn_blocks.json`, 259 blocks), and must never be placed:

  | Block | Species it calls | Who's on the Rift rosters |
  | --- | --- | --- |
  | `amethyst_block`, `budding_amethyst` | Glimmet, Glimmora, Sableye | Glimmet and Glimmora (south-west arm) |
  | `purple_concrete`, `magenta_concrete` | Varoom, Revavroom | both (west spur) |
  | `magma_block` | Gible, Magmar | |
  | every Cobblemon gem block and cluster | the gem species | |

- **Clean:** amethyst clusters and buds, the froglights, crying obsidian, glass, basalt, tuff, calcite, blackstone,
  obsidian and every block this design uses.

**What stands in or on the Rift.**
- **The League** (`cobbleverse:kanto_league`, 111 x 159 x 120, top y243): the Elite Four and the Champion, with an
  elevator. It is the "Elite Four tower", on the trunk floor at (3636, 84, 2591), lot x3517-3636 z2591-2701. Victory
  Road ends at its forecourt (3576, 2762).
- **The dig camp:** on the west spur's floor.
- **The rim post:** on the east rim at (3734, 3951), with a stepped trail up from Victory Road.
- **Hoopa's cradle:** unbuilt and unsited. It must stand in the Victory Road zone (RIFT_ZONES section 2a).
- **Mini towns:** the repo has no plan, site or note for any: a question for the owner (the report).

**Long range.**
- **Landmarks:** the world tree's crown is y457-535 at (2044, 2282). The League's top is y243. The terrain peaks at
  y310.
- **View distances:**
  - The pack's default view distance is 8 chunks (128 blocks), and the server's is 10.
  - Distant Horizons draws 256 chunks (4,096 blocks), with its own clouds and LOD beacon beams (widened at distance,
    to y6000).
  - Display entities are only seen within entity render distance.
- **Shaders:** Iris with Complementary is on by default in Cobbleverse (`enableShaders=true`).

**Pipeline.**
- **The world:** it is exported from the heightmap by WorldPainter (`tools/reexport.py`). The heightmap is changed
  only by recorded operations (`data/sculpt.json`, `tools/press_pads.py`), which pin a new sha256.
- **The re-application:** everything built is generated functions, installed and run by `tools/reapply.py` (R2-R16),
  then audited fail-closed.
- **Custom biomes:** a world datapack (like `cobblers_height`) plus a `/fillbiome` step. The cavern's `60_biome` is
  the precedent.
- **Players:** carried by `reapply.py carry`.

## 2. Decisions for the owner

### 2.1 Re-sculpt the walls: recommended

**The scarps are the barrier.**
- **The problem today:** at 13-22 degrees anyone can walk into the Rift anywhere. That is why the first pass needed a
  rim wall, and a rim wall is exactly what read as a fence.
- **The fix:** cut the walls into scarps. The lip becomes a sheer riser of 23+ blocks, a fall no player survives
  (fall damage is height - 3), wherever the depth reaches 52. Below it, the steps are 11-18-block risers to the floor.
- **The result:** no slope is walkable, so the Rift is sealed by its own ground. The descents become the only ways in,
  and they are where the guards stand. Scenery and gating are one thing, and no wall is needed anywhere on the rim.

**How.**
- **For the export:** a heightmap operation for the big forms (the lip riser, the steps, the treads). A heightmap
  cannot do overhangs, so a generated volume pass after the export adds:
  - undercut lips;
  - side fissures;
  - tilted plates;
  - cracks;
  - the veins.
- **For the prototype:** it is all a block pass (cut-only) on the staging export, which gives the same forms without a
  new export.

**What it costs against what is placed** (the wall band = inside the outline at y92 or above, plus a 16-block ring
outside the lip):

| What | In the band | What the re-sculpt means for it |
| --- | --- | --- |
| The walls | 1,491,572 of the 2,044,636 columns inside the outline (73%) | re-shaped |
| Victory Road | 33 of 486 polyline points | its descents only: re-routed through the gate descents (the south-west tip; the rim post's trail) |
| The League's town box | 18,520 columns (57%); the building's box touches the band | an exclusion mask: no cut within 16 blocks of the building; its plaza and approach are on the floor |
| The rim post | 64,543 columns (70%); its trail climbs the wall | its trail becomes a cut descent: a way in, so a gate (a fifth guard, or part of Victory Road's zone) |
| The dig camp | 298 columns (7%); dig site B at the spur's end | the end of the spur becomes the rock face the dig works into; the camp's floor is untouched |
| Foliage objects, trainers, signposts | none in the band | |
| The floor, the rim line, the spawn boxes, the sub-region polygons | unchanged (cut-only keeps the rim and the floor edge) | |

- **Volume:** about 1,660 blocks per metre of wall on each side. That is about 13.7M blocks for the whole Rift as a
  block pass (5 x the maze forest), and free as a heightmap operation, since the live re-export has not run yet. The
  prototype stretch cuts 118k columns and removes 2.04M blocks (1.69M of them rock; the rest is a 3-block clearance
  above the old ground).
- **Without the re-sculpt:** blocks and light on 13-22 degree walls. From the rim it reads as a valley with glowing
  lines; from across the map, as a darker smudge with purple points. There is no torn edge, and the Rift is still
  walkable everywhere, so it needs a wall again. I'd put the fracture read at a third of the re-sculpted one, at best.

### 2.2 The sky fracture and the world tree

A crack at y360-400 following the whole plan would, from the towns (measured):
- sit 4-15 degrees above the horizon;
- span 35-100 degrees of it: from the hometown 47 degrees, from Brock's town 69, from the tea town 104;
- sit as high as or higher than the world tree's crown, which is a single point 4-10 degrees up.

They are 50-80 degrees apart from most towns, but only 19-36 from Giovanni's, Koga's and Blaine's.

- **For:** it is the long-range beacon. It is the one thing that says "wound" at 3,000 blocks, it glows at night when
  the tree is dark, and it is story (the tear goes all the way up).
- **Against:** a line across half the sky is the loudest thing in the world. It competes with the tree in the same
  register (both above the terrain), and from three gym towns the two sit together.
- **Both on purpose:** make them a pair and keep them apart in kind.
  - **The tree** is day, mass, green and highest (y535).
  - **The crack** is night, line, emission and lower (y360-400).
  - **Where it runs:** rooted over the apex, where the tear began, and running only as far as the trunk's end (about
    1,200 blocks) instead of the whole plan, so it spans about a third of those angles. From the south it reads as a
    crack ahead, beyond the League.
- **Recommended:** that shorter crack. The prototype carries a 391-block sample over the stretch so it can be judged
  from 3,000 blocks before anything is decided.
- **The alternative:** Distant Horizons' LOD beacon beams (widened at distance, to y6000) through purple glass,
  rising from the deepest wounds. They are nearly free, and nothing else carries so far. But they are vertical lines,
  and a few of them risk reading as posts.

### 2.3 Shaders: a question for you

**Does everyone who plays run shaders?** Cobbleverse ships them on, but anyone can switch them off.
- **With shaders:** Complementary gives its own glow to the vanilla emissive blocks it knows. The sea lantern,
  froglight and crying obsidian are all in its lists; the modded galar particle block may not be, and display
  entities may not bloom as blocks do. The prototype has both, to compare.
- **Without shaders:** a glowing seam is a bright texture that lights the rock round it. The design holds up there
  because it rests on three things:
  - form (the scarps);
  - colour contrast (cyan-white and violet against indigo and basalt);
  - real light levels.

  Bloom is not needed for any of them.

## 3. The design

**Concept.**
- **The torn edge:** the Rift is the tear itself. Its edge is where the ground broke: a sheer lip, undercut, with the
  plateau cracking behind it, and the wall shattered into steps and tilted plates.
- **The bleed:** the other world seeps up from below. The rock turns from our world's tuff and stone at the lip, to
  Distortion World stone lower down, to indigo Distortion deepslate at the floor.
- **The veins:** a branching crack of cyan-white light runs along the floor and splits up the walls, as in the sky
  reference.
- **Open windows:** where the tear is still open, the portal's own swirl shows through, in a torn window in a face, a
  pool in the deepest crack, or a curtain in a fissure.
- **The crossing:** stepping over the lip changes the sky, the fog, the grass colour, the sound and the air
  (portal particles).
- **Destinations:** the Elite Four tower and any mini towns stand in the gentler places the scarps leave, and the
  veins run towards them.

**Palette** (every block spawn-clean; light measured in game on staging):

| Role | Block | Light | Colour at range | Fallback |
| --- | --- | --- | --- | --- |
| upper lip face | the world's own strata, banded with `tuff` | 0 | grey | vanilla |
| lower faces | `legendarymonuments:distortion_stone` | 0 | (82, 56, 87) dusk violet | `purple_terracotta` |
| treads, floor near the veins | `legendarymonuments:distortion_deepslate` | 0 | (28, 36, 88) indigo | `deepslate` |
| vein core | `sea_lantern` | 15 | cyan-white | vanilla |
| vein halo | `legendarymonuments:galar_particle_block` | 15 | (212, 117, 199) violet-pink | `pearlescent_froglight` (15) |
| where veins thin | `crying_obsidian` | 10 | violet, dripping | vanilla |
| the wound's crust | `purple_stained_glass` over light | | violet depth | vanilla |
| crystals at branch points | `legendarymonuments:distortion_crystal` | 0 | (36, 28, 134) | `amethyst_cluster` (5) |
| close-range accents (not yet used) | `mega_showdown:dormant_crystal` (mint-white), `mega_stone_crystal` | 15 | not full cubes: close only | `end_rod` |

- **Why these mods:** LegendaryMonuments and Mega Showdown are Cobbleverse's own world-critical dependencies. The
  Distortion blocks are Giratina's world: things dragged through.
- **Fallbacks:** the builder checks each modded id against the installed jars and uses the fallback if it is gone.

**The character changes along the length** (each is one zone of the gating, so the look says where you are):

| Stretch | Depth, width | Character | Glow |
| --- | --- | --- | --- |
| South-west tip, Victory Road's gate | 30, 320-347 | **the fresh tear**: shallow scarps, raw rock, the descent cut through the lip as a stair where the guard stands | the brightest and bluest: a young wound |
| The shared stem | 30-40, 336-400 | **the shattered floor**: the floor itself broken into plates, internal cliffs; the south-east branch's mouth a natural up-step scarp | veins run the floor's length |
| The trunk, fork to spur (the prototype) | 45-63, 369-425 | **the chasm**: the deepest, sheerest, darkest floor; undercut lips, fissures, torn windows in the faces | the sky crack is widest above it |
| The spur's mouth | shallow on the spur side, 525-648 wide | **the wide pan**: the widest floor, a field of tilted plates, pools of energy in the cracks; the most room for a mini town | pools, not veins |
| The west spur, the dig camp | 16-22 | **the old scar**: healed, dim, crying obsidian seeping; outcrops of Distortion rock and meteorite fragments, which is why the diggers are here; the spur's floor a shelf that breaks off into the trunk, so the throat divides by elevation | dim |
| The League head | 29-33 | **the eye**: two scarps close in on the tower; every vein converges on the forecourt | brightest at the tower's foot |
| Behind the League, the apex | 7-23 | **the origin**: where the tear began. The one built division: the League's containment wall, in Distortion brick, across the trunk (gating Z4) | the sky crack's root comes down to the ground here |
| The south-east branch | 27-32 | **the crystal garden**: Distortion trees (`distortion_log` and `distortion_leaves`) and crystal outcrops, the collectors' reward pocket | violet |

**Divisions, made legible:**
- The throat and the south-east branch's mouth are natural: a shelf whose floor breaks off in a scarp. You see why
  you can't climb it.
- The apex is the one human-built wall, because the story walls off the origin.
- The gates are the cut descents: a stair in the scarp, the only walkable way, with the guard at the top.

**The edge in cross-section.** Here is the prototype's middle (s=120), measured from the plan:

```
  plateau y146 ───────┐                                          ┌── plateau y144
   (cracks behind the  │▓ lip riser 27 (undercut 4 under a 5-block overhang on the east side)
   lip, fissures back) │▓                                         ▓│
                y119 ──┴──────┐ tread (tilted plates, cracks)     ▓│
                              │ riser 12-16                        │
                         y101 └─────┐ tread                        │  (steps jitter
                                    │ riser                        │   ±4 along the
                               y89  └──┐                           │   length)
   floor y86 ──────────────────────────┴── veins, the wound ───────┴──
            |<-- about 180 blocks from the rim to the floor's middle -->|
```

**What is seen, and from where:**

| From | With shaders | Without shaders | Made of |
| --- | --- | --- | --- |
| 3,000+ blocks (DH; entities gone) | a line of violet and cyan light in the sky over the head of the Rift (the crack, 8+ thick); a dark indigo band where the lip faces catch the light; the wound's glow at night | the same forms: the crack as a pale line by day and a bright one by night; the faces as colour | blocks only: the sky crack, the scarp faces (DH draws vertical faces as coloured columns), the 9-wide wound |
| The rim | the drop; veins branching below; torn windows and pools swirling; the sky still ours | the same, without bloom: veins are bright lines that light the rock; the swirl still animates | blocks, plus the entities within about 128 blocks |
| The floor | inside the biome: violet sky and fog, portal particles, violet-grey grass, the basalt-deltas air; the veins lit and the plates between them dark | the same, minus bloom | the biome, blocks and entities |

**What stays at DH range once the entities are gone:** the sky crack, the colour of the scarp faces, and the
wound's glow. The portal sheets are close-range only, by design.

**Light and the feel of the floor** (flagged, not decided):
- **What lights up:** the veins give light 15. The floor within about 7 blocks of a vein reads 8 or more; the plates
  between the veins stay dark (0-7).
- **Why it matters:** fightorflight makes Dark and Ghost types aggressive in the dark. The Rift's rosters carry
  Scraggy and Scrafty, Pawniard and Bisharp, Golett and Golurk, and Runerigus. So the veins become the safer paths
  and the dark plates the dangerous ones.

**The biome begins at the lip.**
- **How it's painted:** only on 4 x 4 cells whose 16 columns all lie inside the lip, from y48 to y575. The first pass
  painted whole chunks and leaked up to 15 blocks, plus blending.
- **Pushback on "normal sky behind you and the otherworld ahead":** a game draws sky and fog colour from where the
  camera stands, not from where it looks. No biome can make the sky differ by direction.
- **So the crossing is the moment:** step over the lip and the sky and fog turn, blended over about 8-16 blocks.
  Standing on the rim, the otherworld ahead is carried by blocks and entities: the veins, the windows, the crack
  overhead.

**The spawn change the biome must ship with.**
- **The data edit:** in `data/spawns.json`, the 40 entries scoped to `rift_trunk`, `rift_west_spur`,
  `rift_south_west_arm` and `rift_south_east_arm` go from `"biomes": ["minecraft:windswept_gravelly_hills"]` to
  `["minecraft:windswept_gravelly_hills", "cobblers:the_rift"]`.
- **The recompile:** `tools/compile_spawns.py` then changes all 2,120 compiled Rift spawns, Victory Road's route
  pool included, because it takes those entries.
- **Tags:** no overlay is needed. Cobbleverse's own pools key on biome tags this biome is not in, and the curated
  suppression already covers the Rift.
- **What happens without it:** the Rift spawns nothing authored. Staging has no pools installed, so the prototype
  loses nothing there.

**Portal sheets.**
- **What they are:** `block_display` entities of `minecraft:nether_portal`, brightness 15/15, each paired with
  `minecraft:light` blocks.
- **Lifecycle:** the function force-loads a box round each sheet and waits 60 ticks for the chunks' entities to load
  (an entity arrives about 20 ticks after its chunk: the lesson of the 26 traders on 6 stalls). It then kills its own
  area tag, summons, and counts. Re-running never duplicates.
- **Culling:** each sheet is centred on its origin, with a culling box (`width`, `height`) as large as the sheet, so
  a large sheet does not vanish when its origin leaves the screen. The flight is the test.
- **Range:** `view_range` 2. In practice they are seen within the viewer's entity render distance, 128 blocks at
  the pack's default.

## 4. The owner's map and the Deep (2026-09-22)

The owner drew the Rift's regions on the heightmap (`land_8k_16_annotated_rift.png`, traced and measured into
`data/rift_regions.json`). From the apex south:

| Region | Where | Ground | What it is |
| --- | --- | --- | --- |
| e4 tower | x3527-3792 z2335-2653 | 84-103 | the League, moved here |
| gate | x3511-3635 z2612-2686 | 83-90 | between the entrance shelf and the tower |
| entrance to e4 | x3462-3613 z2661-3025 | 83-85 | a shelf reached only by the tunnel |
| **the Deep** (town) | x3421-3786 z3015-3429 | 82-83 | the widest floor; a sunken city fuelled by the Rift; the evil group's HQ |
| relic area / shrine | x3285-3429 z3229-3384 | 86-100 | between the Deep and the dig |
| rift excavation site | x2950-3308 z3213-3327 | 87-98 | the dig camp; a physical edge on its east side stops new players |
| the sink | x3509-4132 z3351-3755 | 82-120 | the veins drain down it into the Deep |
| upper rift | x3971-4368 z3672-4155 | 85-121 | |
| rift wilds | x4064-4360 z4140-4547 | 83-112 | |
| mega stone mine / the gulch | x4039-4454 z4513-4958 | 83-110 | the south-east branch; Mega Showdown's meteorite blocks belong here |
| hidden rift cavern | x3658-4125 z4574-5079 | 83-114 | the south-west arm, where players come in |

**Decided by the owner (2026-09-22):**
- **The League moves into the tower oval.** It fits facing south at lot x3675-3794 z2335-2445 on the apex, levelled
  to y88 (cut 16,364, fill 2,345, 88% inside the oval). Its forecourt runs 170 blocks south to the gate.
- **The Deep is sunk in terraces to a core at y40.**
  - **Terraces:** five rings about 18 wide, each stepping about 9 blocks, reach a core roughly 40-60 blocks across
    at the pan's middle (inradius 109).
  - **Volume:** about 1.7M blocks removed.
  - **Access:** 9-block risers cannot be walked, so the city moves between rings by stairs, ramps or lifts. LumyMon
    has an `elevator` block.
  - **The seal:** sunk, the Deep leaves the entrance shelf 44 blocks above it with a sheer edge. The shelf is sealed
    by terrain, so going through the town first is the only way up.
- **Victory Road is the tunnel alone.** It runs from the Deep up to the entrance shelf: a climb of 44, which is
  440-530 blocks at 1 in 10 to 1 in 12, or longer with switchbacks. The nine trainers stand in it, about one per 50-60
  blocks. The walk from the hidden rift cavern through the wilds, the upper rift and the sink to the Deep becomes the
  approach, with wild encounters and no trainers.
- **The Deep is late-game.** The 8-badge gate stands where players come into the Rift, not at the tunnel.

**Open:**
- **The city's buildings.** Nothing in the pack is futuristic as a building. The terraces, retaining walls, lifts,
  light bridges, and pylons drawing on the veins can be generated. The buildings themselves, the evil group's HQ
  first, need a source: prefabs the owner builds (Axiom kits), or donors. The materials that suit are Mega
  Showdown's meteorite blocks, Moar Concrete, Rechiseled, glass, and the veins' own crystals.
- **Spawns.** The eleven regions do not match the four spawn sub-regions (`rift_trunk`, `rift_west_spur`,
  `rift_south_west_arm`, `rift_south_east_arm`). The owner assigns spawns; flagged, not changed.
- **Water.** The Deep's core is below sea level (y62). A WorldPainter export has no aquifers, but caves can hold
  water. The Displaced City cavern's `02_shell` (every void within 24 blocks made rock) is the precedent for sealing
  it.

## 5. The prototype

- **What:** one stretch, "the chasm": the trunk from (4171, 3875) to (3911, 3583), 391 blocks, both walls, on a
  fresh staging export.
- **Why here:** it is the deepest (53-63), clear of every settlement, with an outside vantage on the east rim and a
  3,000-block sightline from the hometown.
- **What it demonstrates:** the edge, the glow, the three portal sheets (a vertical window, a horizontal pool, a
  curtain), the biome transition at the lip, and the sky crack sample.
- **Coordinates and counts:** see `derived/rift_fracture/plan.json` and the report.

**Full scale, not before the owner has flown this:**
- the heightmap operation;
- the volume pass for every stretch with its own character;
- the gate descents;
- the League exclusion;
- the spawn change;
- a reapply step and its audit.

## 5a. Found by the prototype's audit

- **Water runs into the cuts.** 4 of the 2,389 sampled cut cells held water on `cobblers-dryrun5`: cutting the walls
  opened the sides of water bodies above and beside them, and it flowed down the scarps. That is about 0.2% of the
  cut columns, which is small, but the forms do not control it. At full scale the volume pass must take the water
  bodies from the data (`data/rivers.json`, `data/waterways.json`, the landmarks' water). It then either seals them
  behind a rock rim, or turns them into deliberate falls down the scarps: a waterfall into the Rift is good scenery if
  it is placed.

## 6. Not verified

- **Complementary's emission:** whether it lights up the galar particle block, and whether it blooms a display
  entity. The flight will show.
- **Culling:** whether the culling box stops the sheets popping out. The flight will show.
- **DH at range:** how the sky crack and the scarp faces read in Distant Horizons from 3,000 blocks. It needs the DH
  LODs regenerated for `cobblers-dryrun5`, and the client's cached LODs of the old staging world moved aside.
- **Fog and grass colours:** the exact values in the biome are first guesses to be tuned in game.
