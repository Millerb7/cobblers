# EXP-049: Does the Seaward Drift's rail line carry a ridden minecart from the mine mouth to Driftmouth Isle and back?

**Status:** built and audited offline (tools/sea_drift.py, tools/sea_drift_audit.py); not run in game.

## Question

The owner, 2026-10-02: "for the long mine tunnel tothe island, make the mine crat rails activated so a player could use
them if they build a minecart". Does a player who places a minecart at either stop ride it to the other stop, without
stopping on the way, derailing, or being thrown out, and stop safely there?

## What is built

`data/sea_drift.json` `rail_line` and `tools/sea_drift.py` `rail_line()`. One line of 1,420 rails from a stop at the
cut's head to a stop in the headhouse, down the drift's centre (1,325 cells), on along the well's first row, up the
middle row of each of the six flights and round each landing. Under each of the 237 powered rails there is a lever,
switched on and sealed in rock, two blocks below the rail. The rest of the line is 1,167 detector rails, 12 curves
(`minecraft:rail`), 2 activator rails (one between each stop and the line) and 2 stops. Every ascending rail is
powered. On the flat there are never more than 11 unpowered rails between powered ones.

## Cited physics (Java 1.21.1, Minecraft Wiki; 1.21.2+ experimental minecarts do not apply)

- A ridden cart keeps full speed for 38 and then 26 rails between single powered rails (Rail, "Minecart speeds"). The
  audit's limit is 26 / 2 = 13; the line's worst run is 11.
- Climbing: at least "3 every 6 blocks" powered; here every climbing rail is powered (6 in 6).
- An unpowered powered rail brakes a cart, "usually stopping it within one block's distance". A powered rail pushes a
  stationary cart "away from a solid opaque block".
- Powered rails pass power along up to 8 joined powered rails. Activator rails do the same along activator rails, and
  a powered activator rail throws the rider out. That is why no power source and no detector rail sits beside one.

## ASSUMED, to be checked here

1. An occupied cart arriving at full speed stops on the single stop rail and does not leave the line. The wiki says a
   cart can bounce off an opaque buffer; a bounce lands it back on the same braking rail.
2. Rails placed by `setblock` end with the shapes written. Vanilla re-shapes a newly placed rail from its neighbours
   (`AbstractRailBlock.onBlockAdded`). The fittings and surface passes place the levers first, then the rails in line
   order, as a player lays track, so the shapes it settles to should be the ones written. Re-running R9SD: the shell
   pass re-writes each lever's cell as rock, the air pass clears every rail under the ground, and the fittings pass
   places them fresh. The rails above the ground (the cut's head, the headhouse) are rewritten in the same state, so
   setblock does nothing to them.

## Probes (after R9SD, on staging)

Each one should succeed (`execute if block ...` returns 1):

| x y z | block | what |
|---|---|---|
| 1458 113 1795 | `minecraft:powered_rail[shape=east_west,powered=false]` | the mouth's stop |
| 1459 113 1795 | `minecraft:stone_bricks` | its buffer |
| 1459 114 1795 | `minecraft:stone_button[face=floor]` | its launch button |
| 1457 113 1795 | `minecraft:activator_rail[powered=false]` | the mouth's station rail |
| 1456 112 1795 | `minecraft:powered_rail[shape=ascending_east,powered=true]` | the first climb |
| 1456 110 1795 | `minecraft:lever[face=ceiling,powered=true]` | its sealed lever |
| 1428 104 1795 | `minecraft:powered_rail[shape=east_west,powered=true]` | a flat booster (lever at 1428 102 1795) |
| 1455 112 1795 | `minecraft:detector_rail[shape=east_west]` | a detector rail |
| 900 68 1795 | `minecraft:rail[shape=north_east]` | the first corner |
| 900 54 1584 | `minecraft:rail[shape=south_west]` | the second corner |
| 341 16 1584 | `minecraft:powered_rail[shape=ascending_west,powered=true]` | the foot of the first flight |
| 331 25 1584 | `minecraft:rail[shape=south_east]` | the first turn, in |
| 331 25 1588 | `minecraft:rail[shape=north_east]` | the first turn, out |
| 342 70 1588 | `minecraft:powered_rail[shape=east_west,powered=true]` | the top landing's booster (lever at 342 68 1588) |
| 343 70 1588 | `minecraft:activator_rail[powered=false]` | the isle's station rail |
| 344 70 1588 | `minecraft:powered_rail[shape=east_west,powered=false]` | the isle's stop |
| 344 70 1587 | `minecraft:stone_button[face=floor]` | its launch button (the wall at 345 70 1588 is the buffer) |

Run the probes after a second R9SD as well: the shapes and states must be the same.

## Ride test (needs a player)

1. At the mouth, place a minecart on 1458 113 1795, get in, press the button on 1459 114 1795.
2. Expected: the cart runs west and down the cut and drift, turns at (900, 1795) and (900, 1584), reaches the well's foot
   at (342-344, 16, 1584), climbs six flights with a turn at each landing, and stops on 344 70 1588 in the headhouse.
   About 1,420 rails at up to 8 blocks a second: three minutes or a little more.
3. Press the button on 344 70 1587. Expected: the cart runs back the whole way and stops on 1458 113 1795.
4. Record any place the cart slows to a stop (its coordinates and the rail under it), leaves the rail, throws the rider
   out, or fails to stop at a stop. Also check that a player can still walk the drift and the flights on the stairs
   beside the rail.

## Results

Not run.
