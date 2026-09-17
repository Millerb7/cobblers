# Settlements off the critical path

**Status: proposed, 2026-09-14; distances re-measured on the regenerated routes 2026-09-16.**
- **Data:** `data/towns.json`, alongside the ten critical towns ([`TOWNS.md`](TOWNS.md)).
- **Nothing is built.**
- **Validated by `tools/validate_data.py`:**
  - the critical path is exactly ten;
  - nothing else is on it, gates it, or is named by a progression flag;
  - off-path distances are within their range;
  - spacing holds;
  - footprints fit the border.

## The count

| Tier | Count | What it is |
| --- | ---: | --- |
| Critical path | 10 | hometown, eight gym towns, the League. **Unchanged** |
| Major non-gym towns | 5 | full towns with an identity and services; destinations |
| Rest stops | 4 | a Center, a waystone, a couple of buildings, one NPC; slightly off a long leg |
| **Settlements** | **19** | 9 of them discoverable |
| Outposts | 6 | one building or a small cluster; discovery without services |

- **Settlements (towns and rest stops):** 19, of which 9 are discoverable, within your
  18–22 and 8–12.
- **Counting outposts too:** 25 places.

## Decided, recorded

In `data/towns.json` `decisions` and
[`DIMENSIONS_AND_BORDERS.md`](DIMENSIONS_AND_BORDERS.md) §4.2:
- **The League** stays at the head of the Rift, in the overworld.
- **The End's League copies** (`cobbleverse:kanto_league`) are to be disabled, like the
  Nether's Blaine copies. The override form is still an experiment.
- **End access is post-game.**
- **The critical path stays at ten.**

## Method

- **Sites:** `tools/find_sites.py`'s largest-square search on the imported river-cut
  heightmap, at least 24 blocks from lake and river water. The slope limit is 5° where a big
  enough square exists, otherwise 8°, and 10° for outposts.
- **Distance from the critical path:** measured to the routed legs in `data/routes.json`, the
  full-resolution terrain-weighted paths between consecutive critical towns, not to straight
  lines. `tools/validate_data.py` re-measures every recorded off-path distance against those
  polylines and fails when a record is more than 2 blocks stale. Giovanni → League is measured
  along Victory Road as authored (`victory_road`, roughly 5,200 blocks up the Rift's south-west
  arm and trunk). The shortest route crosses the plains beside the Rift instead; it was 4,038
  blocks in the 2026-09-14 routing. Measuring against it would have put the Rift rim post on top
  of Victory Road.
- **Figures below** are rounded from `data/towns.json` at the 2026-09-16 regeneration. Leg
  lengths are approximate and name their route ID.
- **Spacing rules** (enforced by the validator):
  - towns and rest stops at least 600 blocks apart;
  - an outpost at least 300 from anything.
  - **Closest pairs:** the Displaced City to Merian hut at 628; the hometown to Relic Island at
    440, on purpose, as a sightline. Surge's town to the Scar was 408 and a sightline; since
    Surge moved to the shelf it is 624, and the Scar cannot be seen from the town.

## Major non-gym towns

| Town | Centre | Site | Off path | Nearest | Waystone |
| --- | --- | --- | ---: | --- | --- |
| **Sunset West** (harbour) | (1716, 7298) | 408², y104–123, ≤8° | 2,021 | Relic Island 1,873 | discovery |
| **Northlight** (South Pine Isle) | (7265, 1556) | 231², y111–124, ≤8° | 2,106 | Sabrina's town 2,130 | discovery |
| **Mining Town** (East Cones) | (6633, 5716) | 227², y132–144, ≤8° | 905 | Blaine's town 912 | none |
| **The Displaced City** (entrance) | (2969, 1710) | 132², y117–127, ≤8° | 287 | Merian hut 628 | discovery, inside the city |
| **Tea town** (Shrew Lake shores) | (2654, 3605) | 248², y107–116, ≤8° | 891 | Rift dig camp 538 | none |

**Sunset West: the region's harbour.**
- **What it is for:** a fishing and boat-building port where players charter boats to the outer
  islands and the deep sea.
- **Why there:** the best site on the map, on the largest island, 2,000 blocks from any gym. The
  sea crossing makes it a destination. It is post-game in content, not locked.

**Northlight: the cold-water research town.**
- **What it is for:** the region's weather and aurora observatory, and an ice-type field
  station.
- **Why there:** the only snowy islands, in the opposite corner from Sunset West, so the two
  post-game islands pull players to both ends of the map.

**Mining Town.** Your spec, folded in as a major town.
- **What it is for:** ore and minerals on the eastern cone: mine head, ore rail, smelter and a
  fossil lab.
- **Why there:** the spec puts it in the volcanic region, and the eastern cone is the only one
  with a bowl (210 blocks north of the site). It is 912 blocks from Blaine's rim town, close
  enough to be heard of there and far enough to be its own trip.
- **The mine is the set piece** (volume build, Axiom/WorldEdit):
  - an adit into the cone toward the bowl;
  - a main shaft from about y135 to the fossil levels (y40–70);
  - deep workings below for Groudon.
  - **Scope estimate:** about 2 km of 3 × 4 galleries (25,000 blocks) and four 30 × 30 × 15
    chambers (54,000). The Groudon chamber is authored separately.
- **Carries:**
  - `sulfur_caves` in the workings, already planned for the Craters and optional, because it
    binds the save to VanillaBackport;
  - the underground fossil-site placements;
  - Groudon.
- **Spawn tags, written 2026-09-14:** the overlay pack `cobblers_spawn_tags`, generated from
  `regions.json` `spawn_tag_overlays` by `tools/spawn_tag_pack.py`, gives the Craters their
  identity.
  - `#cobblemon:is_volcanic` covers the cones and rim (`stony_peaks`, `savanna_plateau`).
  - `#cobblemon:is_thermal` covers the cones, where the town and mine are.
  - Both biomes are now painted only in the Craters (99% inside), so the tags do not leak.
  - See `REEXPORT.md` for what was checked in game.
- **Not done:** the list of fossil species it makes reachable comes with the encounter tables.

**The Displaced City.** Your spec, placed and tiered.
- **What it is for:** a summit town moved by the Worldshift into a cherry-grove cavern, streets
  still laid out for a mountaintop and trees living on light that is not the sun. The
  region's great mystery, with Regigigas sealed beside it.
- **Tier: major, discoverable.** A full town with services, but nothing on the route leads into
  it.
- **Placement: beneath the glacier, not off a Rift side-chamber.**
  - **The Rift has a purpose now:** it is Victory Road to the League. When the spec was written
    it had nowhere to go.
  - **Regigigas** was already planned beneath the glacier.
  - **The absurdity:** ice above, a blossoming city below.
  - **The Scar** (below) is about 1,150 blocks away in a straight line, across the Merian
    cirque, so the two connect by sight and story.
- **Entrance:** a meltwater cave on the trough's south-west flank, at the site above.
- **Cavern:** centred on (3350, 1750), 200 × 200 blocks, y32–72.
  - The ground above is y96 or higher, and the major river's bed nearby is about y98, so at
    least 24 blocks of rock over the ceiling.
  - Excavation: about 1.0–1.6 million blocks plus a 400-block tunnel.
  - **Depth, verified in the exported region files (2026-09-14):** under all 40,000 columns of
    the cavern footprint the world is solid to bedrock at y−64. The y32–72 band is 98.3%
    solid (stone, granite, andesite, diorite, dirt and gravel pockets, coal and iron ore),
    with 884 air cells.
    - The rock over a y72 ceiling is 24 blocks at its thinnest and 31 at the median.
    - The spec stands. There is room to lower the cavern if a thicker roof is wanted.
- **Ceiling, recommended: a glowing false sky.** Light blocks set in the roof let the cherry
  trees and grass live on block light, the "not sunlight" of the spec. Daylight shafts would
  contradict the spec, and full dark would hide the city.

**Tea town: a town built on one industry.**
- **What it is for:** tea terraces and a tea house in the cherry-blossom country above Shrew
  Lake, and the set piece for Poltchageist and Sinistcha.
- **Why there:**
  - it is the only cherry-grove country on the map;
  - the tea house was already the recommended home for Poltchageist
    (`STRUCTURE_DATA_FALLOUT.md`);
  - it is about 890 blocks off the Brock-to-Misty road (`route_02_brock_to_misty`) and 911 from
    Brock, so found by wandering.

## Rest stops

**All four are optional.** Each is roughly 120–390 blocks off its leg (the validator's range is
100–450): visible from the route, but not on it. Measured claims (`data/visibility.json`, an 8-block roofline from
leg points every 16 blocks; re-measured by `tools/validate_data.py`):

| Rest stop | Over bare terrain | Over the planned canopy |
| --- | --- | --- |
| Merian hut | 86 of 216 points (visibility:merian_hut_from_its_leg_terrain) | 35 of 216 points (visibility:merian_hut_from_its_leg_canopy) |
| Gorge hamlet | 55 of 129 points (visibility:gorge_hamlet_from_its_leg_terrain) | **fragile:** 1 of 129 points (visibility:gorge_hamlet_from_its_leg_canopy) |
| Tableland stop | 88 of 191 points (visibility:tableland_stop_from_its_leg_terrain) | **fragile:** 5 of 191 points (visibility:tableland_stop_from_its_leg_canopy) |
| Rift rim post | 60 of 328 points (visibility:rift_rim_stop_from_its_leg_terrain) | **fragile:** 2 of 328 points (visibility:rift_rim_stop_from_its_leg_canopy) |

The fragile three hold over the canopy on a handful of points, so a foliage pass can break them silently; each
needs a tall marker or a kept sightline to read from the road, and the validator fails if the count moves. A player who walks past loses only the convenience.

| Rest stop | Centre | Site | Leg (how far along) | Off path | Nearest | Waystone |
| --- | --- | --- | --- | ---: | --- | --- |
| **Merian hut** | (2813, 1102) | 237², y107–109, ≤5° | Surge → Erika, `route_04_surge_to_erika` (42%) | 120 | Displaced City 628 | discovery |
| **Gorge hamlet** | (6814, 4367) | 181², y109–115, ≤5° | Sabrina → Blaine, `route_07_sabrina_to_blaine` (60%) | 283 | Blaine's town 971 | discovery |
| **Tableland stop** | (4876, 5729) | 198², y158–164, ≤5° | Blaine → Giovanni, `route_08_blaine_to_giovanni` (53%) | 238 | Blaine's town 1,405 | discovery |
| **Rift rim post** | (3734, 3951) | 123², y138–143, ≤5° | Giovanni → League, `victory_road` (63%) | 386 | Rift dig camp 895 | discovery |

- **Merian hut:** an alpine hut in the cirque at the major river's source.
- **Gorge hamlet:** bridge-keepers above the Tilpey outflow gorge, on the far bank, about 500
  blocks in a straight line from the bridge waypoint at (6632, 3904). Its NPC knows the river.
- **Tableland stop:** a waystation, prospector's house and lookout on the badlands plateau top,
  high enough to be seen from below.
- **Rift rim post:** a rangers' post on the rim above the fork. It is the traditional Center
  before Victory Road, but placed off the road, so players climb out to rest and Victory Road
  stays unbroken.

**Is any leg too long to play without a stop? No.** The longest is Giovanni → League: Victory
Road (`victory_road`), roughly 5,200 blocks up the Rift. That length is Victory Road itself.
At a sprint (about 5.6 blocks per second) it is about 16 minutes, less on a ridden Pokémon. The
longest gym leg, `route_04_surge_to_erika`, is roughly 3,500 blocks, about 10 minutes, with the
Merian hut on it. If it plays too long, the fix is the route:
start Victory Road at the Rift's south-west tip, 1,122 blocks from Giovanni. Not a town.

## Outposts

| Outpost | Centre | Site | Off path | Nearest | What it is for |
| --- | --- | --- | ---: | --- | --- |
| **Relic Island** (Ash House) | (1092, 5532) | built islet, ground y63–70 over seabed y35 | 440 | hometown 440 | The F4 worldshift fragment: a Pallet starter home on a torn-off islet, visible from the hometown's coast |
| **The Scar** | (2110, 950) | 301², pressed pad y280 (ground y264–280) | 437 | Surge's town 624 | Where the Displaced City stood: foundations and a road that ends at nothing, high on Mt Vessu. It cannot be seen from Surge's town; his road survey points to it |
| **Viltri Light** | (550, 4518) | 12², y66–70 | 840 | Relic Island 1,150 | A lighthouse over the Mouth of Viltri, an estuary no river uses any more |
| **Rift dig camp** | (3106, 3314) | 121², y87–102, ≤9° | 495 | tea town 538 | Archaeologists excavating the steel chamber (Registeel) in the Rift's dead-end west spur |
| **Frostpeak shrine** | (682, 380) | 111², pressed pad y310 (ground y306–310) | 1,440 | Surge's town 1,440 | A shrine on the lone summit of the most remote corner of the mainland |
| **Jungle Isle ruins** | (5160, 7463) | 301², y120–134, ≤8° | 1,715 | Tableland stop 1,757 | Overgrown ruins and a cache that reward the boat trip without adding a town |

### Landmark trees (outposts added by the foliage pass)

Four giant trees are outposts too (`kind: landmark_tree`). They are discovery sites with nothing built, no waystone
and no gate. The foliage paint places them; each keeps a glade clear. Sites, what each does and sightlines:
[`FOLIAGE.md`](FOLIAGE.md) §4.

| Landmark tree | Centre | Kind | Off path | Nearest |
| --- | --- | --- | ---: | --- |
| The Great Oak | (1800, 5184) | visible from a route | 339 | hometown 355 |
| The Sentinel | (3264, 1008) | a clearing worth finding | 390 | Merian hut 461 |
| The Patriarch | (4272, 3600) | ridge | 247 | Rift rim stop 642 |
| The Cherry Elder | (3408, 3840) | vale | 531 | Rift rim stop 344 |

With them the outposts number 10, and the map has 29 places. A fifth giant, the Weeping Elder on its Lake Tilpey
island, still stands but was demoted to an ordinary feature on 2026-09-16: it is not a place.

**Buildability, honestly:**

| Site | Condition | What it means |
| --- | --- | --- |
| Relic Island | built in the sea | `tools/islet.py` builds the islet: 2,628 columns, 1,413 above water, crown y70, about 72,900 blocks (`data/towns.json` ground note) |
| The Scar, Frostpeak shrine | the rescale removed the clipped y200 flats; both are now pads pressed by `tools/press_pads.py` (Scar y280, shrine y310), feathered at the edges | right for a scar that should look scraped flat; fine for a shrine. The pads are on the canonical heightmap, not yet in the live world |
| Viltri Light | the coast here is low and falls to the sea (to 19° across its pad) | a small raised platform for the tower |
| Rift dig camp | 15 blocks of relief where the spur floor meets its wall | a camp that terraces |
| Mining Town, Northlight | 12–13 blocks of relief | terracing, which suits both |
| Every other site | flat enough | no heavy flattening |

## Waystones

**Rule:** a waystone only where getting back is the hard part, or where convenience is the
whole point.

| Where | Waystone | Why |
| --- | --- | --- |
| The ten critical towns | **flag-driven** | as designed: a gym defeat opens the town's waystone. The hometown's is still the open question in `progression.json`; the League's is proposed to open with it |
| Sunset West, Northlight | **discovery** | islands: the waystone is what a sea crossing earns |
| The Displaced City | **discovery, inside the city** | hard to find twice; the waystone is the reward for finding it |
| The four rest stops | **discovery** | convenience is all they are for; walking past loses nothing |
| Mining Town, tea town | **none** | each is about 900 blocks from a gym waystone; walking in is part of arriving |
| All outposts | **none** | discovery without services |

**Totals:**
- **17 fast-travel nodes:** 10 flag-driven and 7 discovery.
- **8 places without one:** 2 towns and 6 outposts.

**Discovery** means the Waystones mod's own first-visit activation, with no progression flag.
That is the "midpoints by discovery" option in `NAVIGATION.md` §3.2, now applied to these
places.

## Not decided here

- **Names:** `display_name` is null throughout; the working names are placeholders.
- **The spawn tables and fossil list** for the Mining Town and the Displaced City; the
  encounter lists are still deferred.
- **Layouts, interiors and the two volume builds.** These are Axiom work; the data gives only
  the site, the volume and the footprint.
- **Not checked in game:** any of these sites.
