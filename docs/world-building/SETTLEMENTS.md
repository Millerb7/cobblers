# Settlements off the critical path

**Status: proposed, 2026-09-14.**
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
- **Distance from the critical path:** measured to the routed legs, the terrain-weighted
  paths between consecutive critical towns (the same routing as `TOWNS.md`), not to straight
  lines. Giovanni → League is measured along Victory Road as authored: up the Rift's
  south-west arm and trunk, 4,953 blocks. The shortest route (4,038) crosses the plains
  beside the Rift instead, and measuring against it would have put the Rift rim post on top of
  Victory Road.
- **Spacing rules** (enforced by the validator):
  - towns and rest stops at least 600 blocks apart;
  - an outpost at least 300 from anything.
  - **Closest pairs:** the Displaced City to Merian hut at 628; Surge's town to the Scar at 408
    and the hometown to Relic Island at 440, both on purpose, as sightlines.

## Major non-gym towns

| Town | Centre | Site | Off path | Nearest | Waystone |
| --- | --- | --- | ---: | --- | --- |
| **Sunset West** (harbour) | (1716, 7298) | 408², y104–123, ≤8° | 2,022 | Relic Island 1,873 | discovery |
| **Northlight** (South Pine Isle) | (7265, 1556) | 231², y111–124, ≤8° | 2,108 | Sabrina's town 2,130 | discovery |
| **Mining Town** (East Cones) | (6633, 5716) | 227², y132–144, ≤8° | 903 | Blaine's town 912 | none |
| **The Displaced City** (entrance) | (2969, 1710) | 132², y117–127, ≤8° | 426 | Merian hut 628 | discovery, inside the city |
| **Tea town** (Shrew Lake shores) | (2654, 3605) | 248², y107–116, ≤8° | 898 | Rift dig camp 538 | none |

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
- **Not done:**
  - `#cobblemon:is_volcanic` and `#cobblemon:is_thermal` have no loaded biome, so the overlay
    that puts the Craters' biomes into them is still to be written and verified;
  - the list of fossil species it makes reachable comes with the encounter tables.

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
  - **The Scar** (below) is 900 blocks away across the Merian cirque, so the two connect by
    sight and story.
- **Entrance:** a meltwater cave on the trough's south-west flank, at the site above.
- **Cavern:** centred on (3350, 1750), 200 × 200 blocks, y32–72.
  - The ground above is y96 or higher, and the major river's bed nearby is about y98, so at
    least 24 blocks of rock over the ceiling.
  - Excavation: about 1.0–1.6 million blocks plus a 400-block tunnel.
  - **Check first:** the export's lowest block layer before digging below y40 (not verified).
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
  - it is 898 blocks off Victory Road and 911 from Brock, so found by wandering.

## Rest stops

**All four are optional.** Each is 180–365 blocks off its leg: visible from the route, but
not on it. A player who walks past loses only the convenience.

| Rest stop | Centre | Site | Leg (how far along) | Off path | Nearest | Waystone |
| --- | --- | --- | --- | ---: | --- | --- |
| **Merian hut** | (2813, 1102) | 237², y107–109, ≤5° | Surge → Erika, 2,640 (39%) | 182 | Displaced City 628 | discovery |
| **Gorge hamlet** | (6814, 4367) | 181², y109–115, ≤5° | Sabrina → Blaine, 2,021 (60%) | 330 | Blaine's town 971 | discovery |
| **Tableland stop** | (4876, 5729) | 198², y158–162, ≤5° | Blaine → Giovanni, 3,055 (56%) | 235 | Blaine's town 1,405 | discovery |
| **Rift rim post** | (3734, 3951) | 123², y138–143, ≤5° | Giovanni → League, Victory Road 4,953 | 365 | Rift dig camp 895 | discovery |

- **Merian hut:** an alpine hut in the cirque at the major river's source.
- **Gorge hamlet:** bridge-keepers above the Tilpey outflow gorge, on the far bank, 330 blocks
  from the crossing. Its NPC knows the river.
- **Tableland stop:** a waystation, prospector's house and lookout on the badlands plateau top,
  high enough to be seen from below.
- **Rift rim post:** a rangers' post on the rim above the fork. It is the traditional Center
  before Victory Road, but placed off the road, so players climb out to rest and Victory Road
  stays unbroken.

**Is any leg too long to play without a stop? No.** The longest is Giovanni → League: 4,038
blocks by the shortest route, or 4,953 up the Rift as Victory Road. That length is Victory
Road itself. At a sprint (about 5.6 blocks per second) it is about 15 minutes, less on a
ridden Pokémon. If it plays too long, the fix is the route:
start Victory Road at the Rift's south-west tip, 1,122 blocks from Giovanni. Not a town.

## Outposts

| Outpost | Centre | Site | Off path | Nearest | What it is for |
| --- | --- | --- | ---: | --- | --- |
| **Relic Island** (Ash House) | (1092, 5532) | sea, seabed y35 | 439 | hometown 440 | The F4 worldshift fragment: a Pallet starter home on a torn-off islet, visible from the hometown's coast |
| **The Scar** | (2110, 950) | 301², y200, flat | 310 | Surge's town 408 | Where the Displaced City stood: foundations and a road that ends at nothing, on Mt Vessu's summit above Surge's town |
| **Viltri Light** | (550, 4518) | 12², y66–70 | 928 | Relic Island 1,150 | A lighthouse over the Mouth of Viltri, an estuary no river uses any more |
| **Rift dig camp** | (3106, 3314) | 121², y87–102, ≤9° | 491 | tea town 538 | Archaeologists excavating the steel chamber (Registeel) in the Rift's dead-end west spur |
| **Frostpeak shrine** | (682, 380) | 111², y200, flat | 1,458 | Surge's town 1,461 | A shrine on the lone summit of the most remote corner of the mainland |
| **Jungle Isle ruins** | (5160, 7463) | 301², y120–134, ≤8° | 1,736 | Tableland stop 1,757 | Overgrown ruins and a cache that reward the boat trip without adding a town |

**Buildability, honestly:**

| Site | Condition | What it means |
| --- | --- | --- |
| Relic Island | built in the sea | about 35 blocks of fill from the seabed for a 40-block islet, roughly 50,000 blocks; the F4 spec's own function builds it |
| The Scar, Frostpeak shrine | summits flat because the terrain is clipped at y200 | right for a scar that should look scraped flat; fine for a shrine |
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
