# Town placements: eight gyms, the hometown, the League

> **The critical path.** These ten are the whole route. Everything off it (major towns, rest
> stops, outposts) is in [`SETTLEMENTS.md`](SETTLEMENTS.md); both tiers live in
> `data/towns.json`.

**Status: proposed, 2026-09-14; route figures and Surge's site revised 2026-09-16.**
- **Data:** `data/towns.json` (schema `cobblers.towns/1`, validated). Leg figures come from
  `data/routes.json`; the lengths quoted below are approximate and name their route ID.
- **Nothing is built.** These are placements for you to accept before Axiom work starts.
- **Supersedes** the assessment in [`TOWN_CANDIDATES.md`](TOWN_CANDIDATES.md).

## Decisions this rests on (yours, 2026-09-14)

1. **Blaine is at the Craters, not the Nether.** The dimensions plan is updated, and the
   Nether now needs its generated Blaine copies disabled
   ([`DIMENSIONS_AND_BORDERS.md`](DIMENSIONS_AND_BORDERS.md) §4.1).
2. **The Kanto chain stays; two boxes move.**
   - The north-coast box (G, in the sea) moves inland to Peak Pond.
   - Misty's box (E, no water) moves to Lake Viltri.

## Method

All sites are measured on the river-cut terrain that is now imported.

**Sites** use `tools/find_sites.py`'s largest-square search in a window around each box or
feature, with these limits:
- slope under 5° where a large enough square exists, otherwise under 8°;
- ground between y64 and y196, so the clipped y200 summits are excluded;
- at least 24 blocks from any lake or river water.

**Legs** are routed on 8-block cells:
- **Cost:** length × (1 + climb), with a penalty on slopes over 35°.
- **Two variants per leg:** one where water can be crossed, at 25× cost, which reports each
  crossing; and one where the sea, lakes and the major river are impassable.
- **Superseded for the leg figures, 2026-09-16.** Legs are now routed at full resolution on the
  canonical heightmap by `tools/build_routes.py`, with mandatory waypoints, and stored in
  `data/routes.json`. The site searches above are unchanged except Surge's.

## The placements

| # | Town | Leader | Centre | Site | Ground y | Sub-region | Came from |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 0 | Hometown | | (1462, 5293) | 132², ≤8° | 109–118 | Pallet Meadows | box A |
| 1 | Gym 1 | Brock (Rock) | (1743, 3628) | 217², ≤8° | 131–142 | Viltri Plateau | box D |
| 2 | Gym 2 | Misty (Water) | (1605, 2801) | 119², ≤5° | 105–109 | Lake Viltri Hollow | **box E moved to Lake Viltri** |
| 3 | Gym 3 | Lt. Surge (Electric) | (1688, 1410) | 56², flat (pressed shelf) | 174 | The Tri Peaks | **box F, moved to a shelf below Mt Vessu (2026-09-16)** |
| 4 | Gym 4 | Erika (Grass) | (4309, 1555) | 179², ≤5° | 107–112 | Peak Pond Hollow | **box G moved inland** |
| 5 | Gym 5 | Koga (Poison) | (4646, 2446) | 230², ≤8° | 114–123 | Glacier Foot Fields | box I |
| 6 | Gym 6 | Sabrina (Psychic) | (6196, 3398) | 198², ≤5° | 93–98 | Tilpey North Shore | box J |
| 7 | Gym 7 | Blaine (Fire) | (6074, 4995) | 152², ≤5° | 105–111 | North-West Rim | box K |
| 8 | Gym 8 | Giovanni (Ground) | (3647, 6497) | 124², ≤5° | 109–115 | South Strand | box C |
| 9 | League | Elite Four, Blue | (3297, 2603) | 196², ≤8° | 114–121 | Foothill Woods | new: the head of the Rift |

**Footprint classes** (`TOWN_KIT.md`):
- **Small** for the hometown and Surge's shelf, which are the tightest sites.
- **Major city** for the League. Cobbleverse's own League structure is 111 × 120 blocks, which
  fits the 196-block square.
- **Medium** for the other gym towns.

`data/towns.json` records each footprint's square, ground range, mean and maximum slope, and
nearest landmarks.

## Approach and what each site does for the route

**0 → 1, Hometown to Brock** (`route_01_pallet_to_brock`, roughly 2,000 blocks, no crossings;
pinned through the Route 1 maze forest).
- **Hometown:** Pallet Meadows' upper bench. The loop starts in the south-west corner and runs
  north first.
- **Brock:** a birch upland, the first town north, as Pewter is north of Pallet.
- **Counters to Brock are close:** Water is one leg ahead at Lake Viltri, and Grass is on the
  plateau.

**1 → 2, Brock to Misty** (`route_02_brock_to_misty`, roughly 950 blocks, no crossings).
- **Misty sits on the lake's north shore,** 86 blocks from the water. It is the flattest site of
  the ten.
- **Nearby:** Viltri's Path, now on the lake's real outflow, leaves 240 blocks west. The dry
  Viltri Ravine lies 195 blocks south-west.
- **The short leg** makes the first two gyms a pair, as Pewter and Cerulean are.

**2 → 3, Misty to Surge** (`route_03_misty_to_surge`, roughly 2,100 blocks, no crossings).
- **No creek crossing any more.** The road passes east of the pond west of Mt Clay. The pond's
  outflow, once crossed at (1824, 1888), now runs about 150 blocks off the road at its closest.
- **A real ascent:** roughly 80 blocks of climb, most of the steep part on the final Tri Peaks
  grade, with no step over 35°.
- **Surge sits on a shelf pressed into the Tri Peaks–Mt Vessu south flank at y174,** the
  highest town. It is above the treeline and open to the prevailing wind, with the summits in
  view: an exposed site for the electric gym. The town is at Mt Vessu's foot, not on it.
- **His signal array** (`surge_signal_array` in `data/landmarks.json`, planned) stands on a
  Vessu shoulder about 290 blocks from town. It is sited so the Route 3 Nosepass signs can see
  its mast. That sightline is a hard build constraint (`EVT-ROUTE3-NOSEPASS-SIGNS`).
- **Why not the old shoulder at (1847, 1262):** after the vertical rescale it measured y234–275
  with slopes to 33.5°, and legs 3 and 4 climbed 181 blocks with 19 steps over 35°. The
  candidates and the superseded site D are in `site_history` in `data/towns.json`.

**3 → 4, Surge to Erika** (`route_04_surge_to_erika`, roughly 3,500 blocks, no crossings).
- **The route crosses back over Mt Vessu and Mt Clay, then runs east along the north of the
  massif** through a waypoint west of the Merian cirque at (2640, 1180). It passes the major
  river's head while the river is still a creek.
- **Erika is 129 blocks from Peak Pond,** in place of the box that was in the sea.
- **Paint:** the sub-region is dense taiga. Erika's structure generates in flower forest, so a
  flower preset around the town is worth considering when building starts.

**4 → 5, Erika to Koga** (`route_05_erika_to_koga`, roughly 1,050 blocks, no crossings).
- **Koga is at the foot of the Glacial Tear,** 311 blocks from Marshy Marsh: poison beside the
  marsh.
- **The major river's valley** is 311–507 blocks south-west, not yet in the way. Part of the Glacial Tear is visible
  from town; the river itself is not (`LANDMARK_SIGHTLINES_POST_RESCALE.md`).

**5 → 6, Koga to Sabrina** (`route_06_koga_to_sabrina`, roughly 1,950 blocks, no crossings).
- **Sabrina is on the terrace over Lake Tilpey,** where the glacier and the major river end.
- **It is the central hub,** as Saffron is, and the last town before the barrier.

**6 → 7, Sabrina to Blaine: the barrier.**
- **With a bridge:** `route_07_sabrina_to_blaine`, roughly 2,050 blocks. It crosses Lake
  Tilpey's edge and its outflow at the mandatory bridge waypoint (6632, 3904); `data/routes.json`
  records both crossings, each a few tens of blocks. The 2026-09-14 survey measured the gorge
  at 22–32 blocks of water, 9 deep.
- **Without crossing** the river or the lake: 9,496 blocks, back past the river's head. That
  figure is from the 2026-09-14 8-block routing and has not been re-measured.
- **This puts the game's first real obstacle between badges 6 and 7.**
- **Blaine's town is on the Craters' north-west rim.** The East Cones flat by the eastern bowl,
  once recorded as a caldera site for the gym, now holds the Mining Town
  ([`SETTLEMENTS.md`](SETTLEMENTS.md)).

**7 → 8, Blaine to Giovanni** (`route_08_blaine_to_giovanni`, roughly 3,050 blocks, no crossings).
- **The route runs west** along the south of the Craters and the Rift's southern arms.
- **Giovanni is back near the hometown for the finale,** as Viridian's gym opens last beside
  Pallet.

**8 → 9, Giovanni to the League** (Victory Road, `victory_road`, roughly 5,200 blocks up the
Rift, no crossings).
- **Victory Road is the Rift:** the route runs north from its south-west tip, 1,122 blocks from
  Giovanni.
- **The League is on the plateau at the Rift's head:** 178 blocks from its west rim, 447 from the
  Glacial Tear, looking over the major river.

## The League: decided

**Decided 2026-09-14 (yours): the League is in the overworld, at the head of the Rift.** Its
entry in `data/towns.json` is `accepted`; the other towns are still `proposed`.

**Why it moved.** The reasoning that moved Blaine applies:
Cobbleverse's League (`cobbleverse:kanto_league`) would otherwise generate on the End's outer
islands.

**If you accept it:**
- the End's League copies need the same override as the Nether's Blaine copies;
- the End portal room moves from after Giovanni to post-game.

**If you keep the League in the End,** this site becomes the end of Victory Road and the portal
room. See [`DIMENSIONS_AND_BORDERS.md`](DIMENSIONS_AND_BORDERS.md) §4.2.

## Hometown: placed (2026-09-15, a proposal to keep or rework)

The composition, roads, waystone and spawn are recorded in `data/placements.json`. `tools/place_town.py` builds
them into a datapack function (`cobblers:towns/hometown`, 3,919 commands) that was run in the live world.

- **Layout.** North to south:
  - a main street runs 126 blocks from the route north at (1461, 5226);
  - the Pokémon Center and Mart face each other at its head;
  - a cross street at z5292 carries the town sign and five houses to the west;
  - Oak's lab sits at the end of a lane to the east at z5318;
  - spawn is on the main street at (1461, 118, 5306), south of the crossroads, facing the route.
- **The buildings.** All nine are donor templates from the loaded pack. Each rotation comes from the template's
  entrance jigsaw so the door faces its street. Jigsaws are resolved to their final state and loot tables are
  stripped.
- **Checked in the world (first placement):** 0 jigsaw blocks remain, both waystone halves are present, 913 path
  blocks, blocks in all nine footprints, and `level.dat` spawn 1461 118 5306.
- **Re-seated 2026-09-15.**
  - **Why the buildings floated:** the first placement set each template on a levelled pad, one block above
    grade, so every building floated by its ground layer's height. That was +1 for the houses, lab and Mart
    (ground layer 0) and +4 for the Pokémon Center (ground layer 3, above a 3-layer basement).
  - **How the placer seats them now:**
    - it reads the ground from the stopped world's region files;
    - it puts the entrance jigsaw's layer at the ground in front of the door;
    - it runs a foundation course down to the ground under every column the building stands on;
    - it fills air the template stores under a column's lowest block;
    - it never lays a pad.
  - **Verified over RCON:** 0 gaps across the 36 footprint corners and all 1,670 columns the buildings stand on.
  - **Floor against outside ground at the corners:** 25 at grade, 7 one block below, 4 one block above.
  - **The site:** ground under the hometown is 115–118, so no foundation course was needed here. The foundation
    logic was checked on a synthetic 1-in-4 slope: foundations up to 4 blocks, cuts up to 6, 0 gaps.
- **One waystone.** The Pokémon Center donor carried a `waystones:mossy_waystone`.
  - **Why it had to come out of the template:** Waystones registers a waystone the moment a template places one,
    and keeps it registered after the block is replaced.
  - **What the placer does now:** it places a copy of the template with the waystone removed. Block entities and
    entities are kept; only the waystone's 2 blocks and 2 block entities go.
  - **Result:** `waystones.dat` holds exactly one entry, the placed waystone at (1467, 119, 5286).
  - **Still not wired:** its unlock is the open question in `progression.json`.
- **Across re-exports:** the built area (x1376-1567, z4976-5391) is protected from sculpting, and
  `tools/transplant_chunks.py` copies its chunks into a new export.

## Not decided here

- **Town names.** `display_name` is null; the working names are placeholders.
- **Layout, streets and buildings.** Those are authored in Axiom; the footprint is only the
  flat square that fits. The hometown's placement above is a first composition for you to accept or
  rework.
- **Waystone positions** in `data/progression.json` stay null until the towns are built. Each
  `gymN_town` id here is the town those flags name, and the validator checks that they
  exist.
- **Not checked in game:** any site or route.
