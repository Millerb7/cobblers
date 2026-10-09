# Gym 5: Koga, The Tracking Floor

Record: `data/gym_arenas/gym5.json` (schema `gym_arena/1`, tool `tools/gym_arenas.py`). Authored 2026-10-08. Offline checks
only: nothing here has been built in a world or seen in a running game.

## The reading

Koga's town (`gym5_town`) is a fen-edge watch town whose trackers read the marsh for anyone passing unseen; its
signature dressing is a board of cast prints and its palette is mangrove, mud brick, packed mud, bamboo
(`docs/world-building/TOWN_CHARACTER.md`). The Reed House above is their watch house. The arena is the trackers' range
under it: a low mud-brick floor in half-light, mangrove roots grown down through the roof, prints of people and of an
animal set into the floor, and woven reed screens, floor to ceiling, that hide the far end. Koga is not on a stage: he
is in a blind, a raised hide with a plank roof, a lattice back and sides, and soul lanterns for his only light.

## The walk in (what a player sees)

1. The watch floor of the Reed House, where Koga's spawner used to be. At its east end the deck opens over a spiral
   stair of mud-brick treads wound round a stripped mangrove post. The deck opens only over the first treads, so the
   deepest step-off from the watch floor is three.
2. The stair turns down 31 levels (y131 to y100) inside a mud-brick tower standing in the flooded hall's south-east
   corner, lantern-lit from its post, and lets out through a one-wide door onto the floor.
3. Lane 1: the south lane, 6 wide, behind a woven screen. Human prints in the floor lead west. Nothing ahead but the
   lane's end. 24 blocks.
4. A gap at the west end (x4570..4573) turns north into lane 2: 5 wide, a second screen on its north side, prints
   leading back east. 27 blocks.
5. The gap at lane 2's east end (x4597..4603) opens into the range itself, but a third screen (x4591..4603, z2476)
   still stands across it. The player walks west under it, along a three-wide corridor.
6. At the screen's west end (x4591) the range opens: 34 wide, the blind at the far end, hung reed valances overhead at z2468 and z2474, prints leading to it,
   claw marks on the west flank. Koga is first in line of sight here, 18.9 from him; the walk to this cell is 63 steps
   from the door. A battle can start (within 16, in sight) from 71 steps.

## Where everyone stands

| | |
|---|---|
| Koga's seat | (4586, 103, 2461), in the blind's deck; redstone (4586, 102, 2461); the range's axis, x4586 |
| Koga's second (Challenge) spawner | (4584, 103, 2461), two west, in the same deck |
| Koga's Pokemon | (4586, 100, 2468) on the floor, marker at y99 |
| The challenger's Pokemon | (4586, 100, 2473), 5 from Koga's; marker at y99 |
| The challenger | stand marker (4586, 99, 2476) |
| Trainer stand | (4586, 102, 2462), behind the packed-mud face, so Koga steps to the front of the hide |

## Dimensions (measured from the record by `tools/gym_arenas.py check` and a scratch walk, not relayed)

| | |
|---|---|
| Shell | x4568..4605, y98..109, z2456..2494 (38 x 12 x 39), two courses of mud brick all round |
| Interior | x4570..4603, z2458..2492 (34 x 35), floor course y100, air y101..107 |
| Cover | slack 0: the top course y109 leaves y110 and y111 natural under the Reed House's lowest course (the flue sump, y112) |
| Blind | deck x4580..4592, z2458..2463, top y103 (3 over the floor), face z2463; hide posts and roof (y106) x4581..4591 |
| Screens | z2486 (x4574..4603), z2480 (x4570..4596), z2476 (x4591..4603): packed-mud foot, bamboo mosaic y103..105, plank beam y106..107 |
| Descent | newel stair, ring x4599..4602 z2488..2491, tower walls x4598..4603 z2487..2492, y99..130; door (4598, 101..102, 2488) |
| Written | 22,028 cells, 311 commands in `cobblers:gym_arenas/gym5` (the move and sweep apart) |

Team sizing (`data/gym_arena_sizes.json`, `tools/pokemon_sizes.py`): clear radius 3.13 (Drapion's model sweep), clear
height 2.72 (Toxtricity), so the disc around each Pokemon block is open to y104 (floor 100 + ceil(2.72) + 1).

| Measured spare | Koga's Pokemon (4586, 2468) | Challenger's (4586, 2473) |
|---|---|---|
| Nearest solid block in y101..104, horizontal | 4.5 (the blind's face, z2463) | 5.15 (screen 3's end, x4591) |
| Over the clear radius 3.13 | 1.37 | 2.02 |
| Solid overhead | y106 (a valance), 2 over the cleared top at y104 | y108 |

The two Pokemon are 5 apart; Drapion's hitbox is 2.02 wide. The approach (first floor cell to Koga's stand) is 29.3,
against forceBattleMaxDistance + 1 = 17.

## Checks (`python tools/gym_arenas.py check --gym gym5`)

No PROBLEM. 227 cells a battle can start from, every one finding all four Battle Positions blocks; block light min 1,
median 6, 742 of 1014 walkable cells under 8 (a dim hall, as intended: the gate is "no cell at 0"). Dais 3.

## Findings and what is not verified

- **A tool gap (blocks the pack, not the arena):** `gym_arenas.old_seat_restore` derives the cell the old Normal
  spawner is restored to from the commonest solid neighbour at each height. Koga's old spawner (4594, 131, 2487) sits in
  a deck with its redstone block hanging in the air at y130 and nothing solid round it, so it raises
  "gym5: nothing solid beside the old seat at y130 to restore it from". That fails `build` and every audit that calls
  `seat_lines` (11 tests failed, 22 errors at the time of writing; the list is in the hand-back). The right restore is
  `floor` = mangrove planks, `under` = air. The one-line fix is in the tool: when the record gives `old_seat_restore`
  and the derivation finds nothing solid, use the record's. This record already carries the Challenge spawner's
  `old_restore` (planks over air, read from the building model).
- **A test the move makes stale:** `tests/test_challenge_mode.py::test_a_gym_buildings_challenge_spawner_is_set_into_its_floor[kanto_koga]`
  asserts the Challenge spawner is inside the gym building; the required move puts it in the arena.
- Not verified in a world: the build, the stair walked both ways, that Battle Positions sends Koga's Drapion to its
  block, that a battle on sight starts at 16 from a leader three courses up in a hide, that the lattice blocks sight in
  game as it does in the check, how any of it looks, and the tower's look inside the flooded hall (it replaces the water
  and the muddy-root bed at x4598..4603, z2487..2492).
- The Reed House's cauldron at (4600, 132, 2490) now stands on the top of the stair's newel post (checked in the
  model); nothing of the building's route is written on.
- The old donor shell's dig `[4572, 94, 2466, 4605, 111, 2494]` is "filled back in by R16F"; the arena does not rely on it
  (the shell is built, never the rock) but it sits in the same volume.
