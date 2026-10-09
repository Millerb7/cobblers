# Gym 2: Misty, The Lifeboat House

`data/gym_arenas/gym2.json` (schema `gym_arena/1`, tools/gym_arenas.py). Offline checks only; nothing here has been
built in a world or seen in a running game.

## The reading

Misty's town keeps the lake's rescue service (`TOWN_CHARACTER.md` gym2_town: rescue boats, a record of every arrival;
prismarine and mud brick, dark oak, spruce). The cistern the town draws from, the race that feeds it and the ledger
gallery above the race are already carved under the template hall (`data/gym_interiors.json` gym2). The arena is the
next room of the same works: the service's boat house, past the lifeguard. A long mud-brick hall framed in dark oak,
a prismarine quay, the launch channel along its whole south side with the rescue boat still lying in it, buoys on the
water, a lifeline strung on posts along the quay edge, a lifebuoy painted on the end wall. At the east end the
lookout deck, where the watch is kept: spruce planking on a dark prismarine plinth, three courses over the quay, and
Misty on it. Nothing in it is stone and colonnade: it is timber, water and lamps, which is not Brock's hall.

## Where it is, and the one thing that is not what the brief assumed

The brief assumed a descent "from the end of the puzzle route inside the building". Misty's building is the donor
template, and her route is not a stair: it is the well (hall, 38 down the scaffolding, cistern, race, mouths, ledger
gallery, sill, cistern, well back up). Her spawner stands in the hall only because the template put it there. So:

- The descent from the hall is the well that already stands (gallery floor y98 to hall floor y133, 35 courses; the
  survey's "36"). This arena builds no second shaft through the template's mound: replaying the template as placed,
  the hall holds 87 floor cells with three clear courses over them, none of them in a free 3 by 3 (19 free 2 by 2),
  and the shell rule below (every open arena cell must touch a written cell) cannot be satisfied at a hatch in an
  open hall the tool has no model of.
- The arena hangs off the route at its **last gated room**: a door in the ledger gallery's south wall at
  (1606, 99..100, 2877), east of the lifeguard (1604, 99, 2874) and the true mouth (1602..1603). The mouth's exit puts a
  player beside the lifeguard; the door is beyond him. So the puzzle and its two juniors do lead to it. (The hall was
  never gated either: `data/gym_interiors.json` gym2 `leader.gate` is null. Nothing is made easier.)
- The arena lies in the rock south of the carve, x1592..1631 by z2877..2895, y88..102, wholly inside the existing
  `gym_misty` spawn-free box (no zone change), wholly under the ground (the template's lowest course is y107).

## The walk in, step by step

1. Misty is no longer in the hall. A player who came for her goes down the well, as before.
2. In the ledger gallery, past the lifeguard, a dark oak door stands open in the south wall, east of him.
3. Through it: a landing, three wide, and a lantern. Six prismarine-brick stair treads, three wide, run west and
   down from y98 to y93 (flush with the landing at the top, one over the quay at the bottom). Rock and mud brick on
   every side and over head; lanterns hung from the roof.
4. The foot, two long, and an arch through the hall's north wall, two wide and three high, framed in dark oak.
5. The hall's north-west corner at (1598, 93, 2883): the whole hall is in view. 36 blocks long, 11 wide, air to y99,
   dark oak beams across the roof every six, a post up the wall to each, two lanterns hung on chains from each beam.
   Lockers (barrels) along the north wall. On the south side the channel, three wide: the rescue boat lies in its
   west end under a mast lantern; three buoys (red, white, lantern) float east of it; sea lanterns in the bed light
   the water from under; a fence post and lantern every five along the quay edge with a chain strung between.
6. East 29 blocks to the lookout: the deck's front edge is a stripped dark oak course, three over the quay. On it
   Misty, in front of a lifebuoy (red arcs top and bottom, white sides) painted on the end wall, a watch lamp in the
   roof over her.
7. The fight starts when the player is within 16 of her with a line of sight, which is at about x1611, at the hall's
   middle. Her Pokemon goes to (1620, 92, 2887), the challenger's to (1612, 92, 2887).

## Dimensions

| | |
|---|---|
| Bounds | x1592..1631, y88..102, z2877..2895 |
| Hall shell | x1592..1631, y88..101, z2881..2895, two courses; interior 36 x 11 x 10 (x1594..1629, z2883..2893, y90..99) |
| Floor | prismarine brick top course y92, stand y93; base y90..91 |
| Ceiling | air to y99 (7 over the stand), beams y99, vault y100..101 |
| Launch channel | x1594..1629, z2891..2893, water y91..92 (surface flush with the quay), bed y90, sea lanterns in the bed |
| Lookout deck | x1624..1629, z2883..2890; plinth y93..94, deck y95 (3 over the floor); trim course x1624 |
| Seat | (1627, 95, 2887); redstone under it at y94; trainer stand (1626, 94, 2887) |
| Challenger | Pokemon block (1612, 91, 2887); stand block (1609, 91, 2887) |
| Leader's Pokemon block | (1620, 91, 2887): 3.5 from the deck's front trim |
| Slipway | block x1597..1607, z2877..2881, y91..102; landing (1606, 98), 6 treads x1605..1600 (y98..93), foot x1598..1599 |
| Approach | 29.4 from the arch to Misty's stand (rule: over 17); 40 steps by the check's own walk from the landing to the deck's foot (13 of them to the arch exit) |
| Challenge spawner | moved to (1627, 95, 2885), two south of the seat on the same deck |
| Written | 11,105 cells, 195 commands in `cobblers:gym_arenas/gym2` (the move and sweep apart) |

## What was measured

- **Size.** Misty's team over every tier: widest hitbox pelipper 0.96, tallest floatzel 1.53, largest model sweep
  (clear radius) pelipper 1.85 (`data/gym_arena_sizes.json`, the check reads it). The floor across is 11 wide against
  3.7 needed; the disc round her Pokemon block is empty by 1.65 to the deck, and the two blocks are 8 apart against a
  hitbox of 0.96. The hall is therefore large for her team on purpose: it is a stage, not a fit.
- **The check** (`python tools/gym_arenas.py check`): no PROBLEM. 73 cells a battle can start from; both Pokemon
  blocks and both stands found from all 73; block light min 4, median 10 (29 cells under 8); cover slack 0.
- **Mutations that bite** (each tried against this record or the generator, not just the data): the door cells as air
  fails the shell rule at (1606, 99, 2877) beside the gallery's own air; `COVER + 1` fails 15 columns on the south
  wall; the trainer's Pokemon block moved to the deck face fails the clear disc; the challenger's block at x1600
  fails Battle Positions' search from 31 of 73 cells; the stair at headroom 1 cuts the descent; `floor_y` 94 fails the
  dais and the marker; an entry cell at 15.6 from the leader fails the approach.
- **Against the dig** (replayed `tools/gym_interiors.py gym2_commands`, not a world): 0 of the arena's writes land on a
  cell the dig wrote; the nearest open arena cell is 2 cells from the nearest open dig cell (one cell of the slipway
  block's north wall between it and the gallery).
- **Ground** (`tools/ground.py`): 103 at the lowest column of the bounds. The south wall's top (y101) is exactly two
  under it there: cover slack 0, the same standard as Brock's.
- **The lake**: level up to 103 in the survey window. The arena's top is y102 (the slipway block) and y101 (the hall).
  The nearest wet column (1632, 2895) is 1 horizontal block from the bounds, at ground 103 and level 103: two courses
  above the hall's top and outside a solid shell. Not a risk the design should hide, so it is stated: the hall's
  south-east corner is the closest thing to the lake, and what keeps the lake out is the two courses of mud brick and
  the rock above them, not distance.

## What the check cannot see, and what is not verified

- **The junction.** `tools/gym_arenas.py` builds no model of the template or the dig for gym 2, so it walks from the
  slipway's landing (`entry.route_end` (1606, 99, 2878)), not from the hall, and sees the door as a solid block. That
  a player in the gallery reaches the landing through an open door, and a Pokemon follows, is not proven. The door is
  `dark_oak_door[open=true]`, lower and upper half, placed by `setblock` in that order; a player can close it.
- Nothing was built in a world. That Battle Positions sends Misty's Pokemon to its block and the player's to theirs
  here; that a battle on sight starts at 16 on a deck three up; that a Pokemon that does not fly can leave the
  channel's water; the bind-pose model sweep as the real clearance.
- The seat move: `<gym>_seat` moves the spawner from the template's pool rim (1605, 132, 2874) to the deck and puts
  the rim stair back (`old_seat_restore`: a straight west smooth quartz stair over smooth stone, read from the
  template as placed), and takes the Challenge spawner out of (1605, 132, 2873). Read from data, not seen.
- The hall above is left with no leader. It is still the gym's front door and the well's head; whether a player who
  climbs back into it should be told where she went (a sign, a line of dialogue) is a design question, not made here.
- Arena order in R16GA after R16E (the dig): the dig is applied first, so the door is cut after it; a re-run of R16E
  alone does not touch the arena (the dig writes no cell the arena wrote).
