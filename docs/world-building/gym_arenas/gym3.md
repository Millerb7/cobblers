# Gym 3: Lt. Surge, the Relay Works and the Grounding Hall

Record: `data/gym_arenas/gym3.json` (schema `gym_hall/1`, tool `tools/gym_arenas.py`; design in
`docs/world-building/GYM_WALKTHROUGH.md`). One building on the lot (1722..1752 x 1388..1432, level y174, facing
west), walked through to the leader. Offline checks only: nothing here has been built in a world or seen in a running
game. The carved arena it replaced (schema `gym_arena/1`, a newel stair down from a gallery in the rock) is kept in
the record's `replaces.arena` and in git (`dfcd2fb`); its look is kept and expanded.

## The reading

Surge's town keeps the power, the relays and the storm gear running (`TOWN_CHARACTER.md` gym3_town: deepslate and tuff,
weathered and waxed copper). The building is the substation where the feeder from his array lands, and the hall at
its end is where the line is earthed. Machinery on both walls, a line in the floor, a board behind him; every copper
block waxed, so the gradient stays where it is put.

## The walk (85 moves from the lane to the challenger's stand; stand height up 4 then down 7)

1. **The lane door** (west wall x1723, z1391..1393) and **the bay**: cable drums and spools; the Line Engineer
   stands at the foot of the tower, clear ground in front of it.
2. **The tower** (z1396..1403, two courses, across the whole 10-wide strip x1724..1733): sheer, climbed only by its
   two half steps at the east end (x1732..1733) onto the **catwalk** (grate deck, stand y177).
3. **The leads**: three two-wide bus bars (x1725..1726, x1728..1729, x1731..1732) run south over a pit of packing
   straw at y178. Only the west bar has its lead (two stair steps, z1404..1405); the other two begin two courses over
   the deck with no step, and are weathered and oxidised, dark. The live bar is bright waxed copper with lanterns
   over it. The Relay Technician stands on the deck in front of the whole lead. The puzzle is reading which lead is
   whole; the other two cannot be stepped onto. A player who drops into the straw (four down, hay) climbs out by the
   stair at the pit's east edge (x1733).
4. **The isolator**: the live bar steps down onto a tuff insulator two long (z1410..1411) and up again, the open
   switch, all half steps; the bar goes through the isolator wall (z1415..1416) by the **duct** and down **four half
   steps** onto the ground.
5. **The junction** (z1423..1428): the Cable Rigger, then the cross passage east through the divider (x1734,
   z1426..1428) onto **the earthing gallery** (y174, z1425..1428, 15 wide).
6. **The Grounding Hall**: one broad stair of three half steps, 15 wide, down to the floor (y171, three under the
   works' floor). The hall is 15 wide (x1735..1749) by 35 long (the cab z1390..1394, the floor z1395..1421, the stair
   z1422..1424); the signal line is
   oxidised at the stair and bright at the cab; four banks each side, brightest at the cab; three bus runs on chains
   at y179; the cab four courses up at the north end with the lamp board in the wall behind it. 29 from the stair's
   foot to Surge, so the fight cannot start until the player stands on the floor.

**Out**: an iron door in the divider at (1734, 175, 1392), opened by a stone button at (1735, 176, 1393) on the hall
side, reached by a three-step stair west of the cab (x1735..1736) up to a platform: it lets out into the bay, 11 blocks
from the lane door, 40 moves from the challenger's stand. Or back the way you came (70 moves, nothing one-way, no fall
over three). The pilaster at x1737 stands between the platform and the cab, so the cab cannot be climbed from it.

## Where they stand

| | |
|---|---|
| Surge's seat | (1742, 175, 1392), the spawner flush in the cab top, redstone block at y174; trainer stand block (1742, 174, 1393) |
| Challenge spawner | (1742, 175, 1390), two north of the seat on the same line (the one row of the cab outside the old Relay Works' bounds, z1391..1430, so `replaced_seats` does not claim it) |
| His Pokemon | (1742, 170, 1400): 5.5 from the cab's face (cell edge z1395.0 against z1400.5), 4.5+ from the nearest bank |
| The challenger's Pokemon | (1742, 170, 1407), 7.0 behind his; challenger stands (1742, 170, 1410) |
| Juniors | Line Engineer (1730, 175, 1394); Relay Technician (1726, 177, 1403); Cable Rigger (1730, 175, 1425) |

## What it takes down

The old Grounding Hall (x1737..1759, y156..171, z1403..1439: filled with stone by `gym3_takedown`, measured from
`replaces.arena`), the part of its newel stair under the pad, and above the pad every cell of the Relay Works' bounds
(x1725..1750, y174..206, z1391..1430), cleared by the hall's own first part. `data/gym_buildings/gym3.json` is
`superseded_by` the hall (R16G no longer builds it).

## Not verified

Everything in a running game: stair shapes as placed, that the lit lamps stay lit across a chunk reload, that Battle
Positions sends Surge's Pokemon to its block here, that a battle on sight starts at 16 from a leader four courses up,
that the hall's lightning rods are inert (they stand under the roof; the roof carries copper finials, not rods), the
bind-pose model sweep as the real clearance. The walk is a model's walk: a real player's jumps over the one-wide
gaps between the bars are not modelled.
