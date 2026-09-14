# Town placements: eight gyms, the hometown, the League

**Status: proposed, 2026-09-14.**
- **Data:** `data/towns.json` (schema `cobblers.towns/1`, validated).
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

## The placements

| # | Town | Leader | Centre | Site | Ground y | Sub-region | Came from |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 0 | Hometown | | (1462, 5293) | 132², ≤8° | 109–118 | Pallet Meadows | box A |
| 1 | Gym 1 | Brock (Rock) | (1743, 3628) | 217², ≤8° | 131–142 | Viltri Plateau | box D |
| 2 | Gym 2 | Misty (Water) | (1605, 2801) | 119², ≤5° | 105–109 | Lake Viltri Hollow | **box E moved to Lake Viltri** |
| 3 | Gym 3 | Lt. Surge (Electric) | (1847, 1262) | 83², ≤8° | 186–194 | Mt Vessu | **box F, off the clipped summit** |
| 4 | Gym 4 | Erika (Grass) | (4309, 1555) | 179², ≤5° | 107–112 | Peak Pond Hollow | **box G moved inland** |
| 5 | Gym 5 | Koga (Poison) | (4646, 2446) | 230², ≤8° | 114–123 | Glacier Foot Fields | box I |
| 6 | Gym 6 | Sabrina (Psychic) | (6196, 3398) | 198², ≤5° | 93–98 | Tilpey North Shore | box J |
| 7 | Gym 7 | Blaine (Fire) | (6074, 4995) | 152², ≤5° | 105–111 | North-West Rim | box K |
| 8 | Gym 8 | Giovanni (Ground) | (3647, 6497) | 124², ≤5° | 109–115 | South Strand | box C |
| 9 | League | Elite Four, Blue | (3297, 2603) | 196², ≤8° | 114–121 | Foothill Woods | new: the head of the Rift |

**Footprint classes** (`TOWN_KIT.md`):
- **Small** for the hometown and Surge's shoulder, which are the tightest sites.
- **Major city** for the League. Cobbleverse's own League structure is 111 × 120 blocks, which
  fits the 196-block square.
- **Medium** for the other gym towns.

`data/towns.json` records each footprint's square, ground range, mean and maximum slope, and
nearest landmarks.

## Approach and what each site does for the route

**0 → 1, Hometown to Brock** (1,780 blocks, no crossings).
- **Hometown:** Pallet Meadows' upper bench. The loop starts in the south-west corner and runs
  north first.
- **Brock:** a birch upland, the first town north, as Pewter is north of Pallet.
- **Counters to Brock are close:** Water is one leg ahead at Lake Viltri, and Grass is on the
  plateau.

**1 → 2, Brock to Misty** (908 blocks, no crossings).
- **Misty sits on the lake's north shore,** 86 blocks from the water. It is the flattest site of
  the ten.
- **Nearby:** Viltri's Path, now on the lake's real outflow, leaves 240 blocks west. The dry
  Viltri Ravine lies 195 blocks south-west.
- **The short leg** makes the first two gyms a pair, as Pewter and Cerulean are.

**2 → 3, Misty to Surge** (1,643 blocks).
- **The first crossing of the game:** the creek from the pond west of Mt Clay, at (1824, 1888),
  5–10 blocks wide.
- **Surge sits on Mt Vessu's south shoulder,** the highest town (y186–194): an exposed peak for
  the electric gym.
- **Why not box F's own plateau:** it is flat only because the terrain is clipped at y200.

**3 → 4, Surge to Erika** (2,640 blocks, no crossings).
- **The route runs east along the north of the massif.** It passes the major river's head while
  the river is still a creek.
- **Erika is 129 blocks from Peak Pond,** in place of the box that was in the sea.
- **Paint:** the sub-region is dense taiga. Erika's structure generates in flower forest, so a
  flower preset around the town is worth considering when building starts.

**4 → 5, Erika to Koga** (1,027 blocks, no crossings).
- **Koga is at the foot of the Glacial Tear,** 311 blocks from Marshy Marsh: poison beside the
  marsh.
- **The major river's valley** is 311–507 blocks south-west, in view but not yet in the way.

**5 → 6, Koga to Sabrina** (1,946 blocks, no crossings).
- **Sabrina is on the terrace over Lake Tilpey,** where the glacier and the major river end.
- **It is the central hub,** as Saffron is, and the last town before the barrier.

**6 → 7, Sabrina to Blaine: the barrier.**
- **With a bridge:** 2,021 blocks, crossing the Tilpey outflow gorge (22–32 blocks of water,
  9 deep) at about (6632, 3904).
- **Without crossing** the river or the lake: 9,496 blocks, back past the river's head.
- **This puts the game's first real obstacle between badges 6 and 7.**
- **Blaine's town is on the Craters' north-west rim.** For the gym itself, a 156-block flat in
  the East Cones by the eastern bowl (6607, 5622) is recorded as an alternative, if the gym
  should stand in the caldera.

**7 → 8, Blaine to Giovanni** (3,055 blocks, no crossings).
- **The route runs west** along the south of the Craters and the Rift's southern arms.
- **Giovanni is back near the hometown for the finale,** as Viridian's gym opens last beside
  Pallet.

**8 → 9, Giovanni to the League** (4,038 blocks, no crossings).
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

## Not decided here

- **Town names.** `display_name` is null; the working names are placeholders.
- **Layout, streets and buildings.** Those are authored in Axiom; the footprint is only the
  flat square that fits.
- **Waystone positions** in `data/progression.json` stay null until the towns are built. Each
  `gymN_town` id here is the town those flags name, and the validator checks that they
  exist.
- **Not checked in game:** any site or route.
