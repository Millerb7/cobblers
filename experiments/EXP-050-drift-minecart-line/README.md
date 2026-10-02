# EXP-050: Does the Seaward Drift's straight rail line carry a ridden minecart from Foothill Gate to Driftmouth Light and back?

**Status:** rebuilt 2026-10-02 as a straight road and audited offline (tools/sea_drift.py, tools/sea_drift_audit.py,
tests/test_sea_drift.py); not run in game. The first line (an L-shaped tunnel with a scissor-stair well, 1,420 rails)
was ridden by the owner in staging-2026-10-01: it worked and was "too slow".

## Question

The owner, 2026-10-02: "make the mine crat rails activated so a player could use them if they build a minecart"; then,
after riding it: "make it a straight shot to the island for sure ... if we could make it feel like a bike tunnel from the
games that would be sick", and "make the house you come out a light house as well". Does a player who places a
minecart at either stop ride it to the other stop, without stopping on the way, derailing, or being thrown out, and stop
safely there? Does the ride read as the Cycling Road?

## What is built

`data/sea_drift.json` (`rebuild`, `route`, `gatehouse`, `road`, `island.lighthouse`, `rail_line`) and
`tools/sea_drift.py`. One straight line of 1,137 rails along z1795, from a stop in **Foothill Gate** (1450-1462,
1790-1800, over the owner's point 1455 113 1795) to a stop in the keeper's hall of **Driftmouth Light** on
Driftmouth Isle (centre 336, 1798; the isle moved 212 north onto the mouth's line). Flat through the gatehouse, an
open cut falling 1 in 2 to the portal at (1432, 104), then a steady coast of 1 in 16 to y38 under the shelf, a flat
bottom at x360-363, and a straight climb of 1 in 1 (32 rails) up into the hall at y70. 167 powered rails, each with a
lever switched on and sealed in rock two blocks below it; 966 detector rails; 2 activator rails (one between each stop
and the line); 2 stops. No `minecraft:rail`: the line never turns, and the first line's spawn-policy exception for its
12 curves is gone. On the flat never more than 11 unpowered rails between powered ones.

The road: paved either side of the rail (polished andesite, polished deepslate below y48), the lane edges dashed in
calcite 3 on, 3 off; a pair of lanterns over the footpaths and a timber set every 6 cells; a distance board on each
wall every 128 cells ("Driftmouth Light / N blocks", "Foothill Gate / N blocks").

Trip: 1,137 blocks at the cited cap of 8 blocks a second is **142 seconds** at best, against about 177 for the first
line's 1,420 rails.

## Cited physics (Java 1.21.1, Minecraft Wiki; 1.21.2+ experimental minecarts do not apply)

- A ridden cart keeps full speed for 38 and then 26 rails between single powered rails (Rail, "Minecart speeds"). The
  audit's limit is 26 / 2 = 13; the line's worst run is 11.
- Climbing: at least "3 every 6 blocks" powered; here every climbing rail is powered (6 in 6).
- An unpowered powered rail brakes a cart, "usually stopping it within one block's distance". A powered rail pushes a
  stationary cart "away from a solid opaque block".
- Powered rails pass power along up to 8 joined powered rails. Activator rails do the same along activator rails, and
  a powered activator rail throws the rider out. That is why no power source and no detector rail sits beside one.
- "A predefined speed limit of exactly 8 blocks per second per axis of travel" (Minecart).

## ASSUMED, to be checked here

1. An occupied cart arriving at full speed stops on the single stop rail and does not leave the line.
2. A ridden cart holds the climb of 1 in 1 for all 32 rails on powered rails without stalling (every rail of it is
   powered; the wiki's "a minecart can climb at most 24 blocks before stopping" is for unpowered track).
3. Rails placed by `setblock` end with the shapes written. The fittings and surface passes place the levers first, then
   the rails in line order, as a player lays track.

## Probes (after the cleanup, R9SD and R9E, on staging)

Each should succeed (`execute if block ...` returns 1). The full list is `derived/sea_drift/plan.json` `probes`.

| x y z | block | what |
|---|---|---|
| 1461 113 1795 | `minecraft:powered_rail[shape=east_west,powered=false]` | the stop in Foothill Gate |
| 1462 113 1795 | a stone-brick block (the gate's east wall) | its buffer |
| 1461 113 1796 | `minecraft:stone_button[face=floor]` | its launch button |
| 1460 113 1795 | `minecraft:activator_rail[powered=false]` | the gate's station rail |
| 1459 113 1795 | `minecraft:powered_rail[shape=east_west,powered=true]` | a flat booster (lever at 1459 111 1795) |
| 1448 112 1795 | `minecraft:powered_rail[shape=ascending_east,powered=true]` | the first step down the cut (lever at 1448 110 1795) |
| 1458 113 1795 | `minecraft:detector_rail[shape=east_west]` | a detector rail |
| 1455 116 1789 | `minecraft:spruce_wall_sign` | Foothill Gate's sign over its north door |
| 1431 103 1794 | `minecraft:calcite` | a lane dash beside the rail |
| 1368 103 1793 | `minecraft:spruce_wall_sign` | a distance board: Driftmouth Light, 1,043 blocks |
| 661 51 1795 | `minecraft:air` (52: rock) | the roof under the sea's least cover (sea floor y55) |
| 338 60 1795 | `minecraft:powered_rail[shape=ascending_west,powered=true]` | the climb into the isle (lever at 338 58 1795) |
| 326 70 1795 | `minecraft:activator_rail[powered=false]` | the hall's station rail |
| 325 70 1795 | `minecraft:powered_rail[shape=east_west,powered=false]` | the stop in the keeper's hall |
| 325 70 1796 | `minecraft:stone_button[face=floor]` | its launch button (the wall at 324 70 1795 is the buffer) |
| 328 73 1800 | `minecraft:spruce_wall_sign` | Driftmouth Light's sign over the hall's south door |
| 327 94 1788 | `minecraft:glowstone` | **the lighthouse's lamp** (and 327 95 1788) |
| 327 95 1785 | `minecraft:glass` | the lantern room's glazing, north face |

The cleanup of the first drift (staging only, before R9SD):

| x y z | block | what |
|---|---|---|
| 900 69 1795 | a rock block (stone, andesite or tuff) | the first drift's north-west corner, filled |
| 900 55 1584 | a rock block | its south-west corner, filled |
| 336 60 1586 | `minecraft:water` | where the first isle stood |
| 364 58 1558 | `minecraft:water` | where the first isle's NE stack and its upper Habitat Block stood |

Run the probes after a second R9SD as well: the shapes and states must be the same.

## Ride test (needs a player)

1. In Foothill Gate, place a minecart on 1461 113 1795, get in, press the button on 1461 113 1796.
2. Expected: the cart runs west through the gate's west wall, down the cut, under the portal at x1432 and down the long
   coast under the plateau, the coast and the shelf, along the bottom at x360-363 and up the climb into the keeper's
   hall, and stops on 325 70 1795. About 142 seconds at full speed.
3. Press the button on 325 70 1796. Expected: the cart runs back the whole way and stops on 1461 113 1795.
4. Record any place the cart slows to a stop (its coordinates and the rail under it), leaves the rail, throws the rider
   out, or fails to stop at a stop. Note how long each way took. Also walk it: the footpaths beside the rail, the stairs
   at every step and up the climb, the hall's south door and the path to the shingle, the tower's stair to the lantern
   room.
5. From the sea at night, and from the nearest shore (497, 1870), 189 blocks east-south-east of the lamp (render
   distance 12 chunks or more): is the lamp seen? Does the tower read as a lighthouse?

## Results

Not run.
