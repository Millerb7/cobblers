# Gym 6: Sabrina, The Observation Well

`data/gym_arenas/gym6.json` (schema `gym_arena/1`, read by `tools/gym_arenas.py`). Authored 2026-10-08. Offline
checks only: nothing here has been built in a world or seen in a running game.

## The reading

Sabrina is the Rift researcher. Her town is the region's place of study (`TOWN_CHARACTER.md` gym6_town: calcite,
smooth quartz, polished diorite, purpur and end rods as accents) and the Hall of Lenses above is where the work is
read. The arena is where it is **observed**: a deep, tall well with a great lens hung over the floor. It is the
tallest room of the eight (21 courses clear over the floor; Brock's is 14) and a vertical room, not a long one: the
long approach is a descent, a terrace to see the room from, and a glass-screened flight down its wall.

The lens is a biconvex disc of tinted glass in an amethyst rim, radius 6, centre (6192, 3320), hung from the ceiling
on four chains with end rods under its rim. Its image is let into the floor as an amethyst ring (radius 6) and a
purpur ring round a froglight focus, with the two Pokemon marks inside it, as the building's own lens floor is the
shape the observatory's lens makes at noon. Sabrina stands on a purpur dais in a stepped apse at the west end, under
THE EYE (the town's sign, three times in the building: purpur, amethyst iris, pearlescent-froglight pupil), lit from
behind her. Nothing here is per player.

## The walk in

1. In the lens chamber (the end of the building's route), a stair mouth is cut in the chamber floor at
   (6200, 111, 3314), east of the lens, a few cells from where Sabrina stood. Its first tread is level with the
   floor; the floor cells over the next treads open as the headroom is cut (the stair is the only way into them).
2. The stair winds down a quartz newel inside a solid quartz tube: 47 treads, 31 levels (y111 to y80), four turns.
   The tube passes through the chamber floor, hangs through the open well of the hall (x6199..6204, z3312..3317, y98
   to y110, between the decoy stacks and the gallery), the hall floor, the rock under the pad, and the arena's
   ceiling, and hangs 9 courses below it into the room like the barrel of the instrument. Froglights are set into
   the newel every two courses.
3. A landing at (6201, 80, 3313), a door (6201, 81..83, 3312) and the **terrace**: a landing of polished diorite hung
   fourteen courses over the floor, x6196..6213 by z3306..3311, tinted-glass screens two high round its open edges.
   The player looks west down the whole room: the lens just below eye level, the floor far below, the eye on the far wall
   and Sabrina small on her dais, 20.1 away at the nearest terrace cell (outside rctmod's reach of 16).
4. The **east flight**: fourteen smooth-quartz stairs down the east wall (z3312..3325, y80 to y67) over a solid
   wedge, a glass screen along its open side with froglights set in it. It lets out at (6211, 67, 3326), the first
   floor cell, 30.9 from Sabrina.
5. The floor, west toward the dais, between the lens's image and the pilasters, to the apse. By cardinal steps the
   whole walk from the building's route end to the dais foot is 113 steps (BFS over the model, steps down of at most
   one), 52 of them to the landing and 81 to the floor.

## Where they stand

| | |
|---|---|
| Sabrina's seat | (6181, 70, 3320), flush in the dais top, redstone block at y69 (the seat function writes both) |
| Dais | x6178..6184 by z3314..3325, y67..70: purpur body, smooth quartz top, amethyst lip at x6184, chiseled quartz face; 4 courses over the floor (rule: 2 to 5) |
| Apse | the room narrows round the dais in steps (z3306..3309 to x6189, z3310..3311 to x6187, z3312..3313 to x6185, mirrored on the south), solid floor to ceiling, so no aisle runs up beside the dais |
| Trainer stand | (6182, 69, 3320), under the dais top one in front of the seat |
| Sabrina's Pokemon | (6190, 65, 3320), 5.50 from the dais face |
| Challenger's Pokemon | (6194, 65, 3320), 4 from Sabrina's |
| Challenger stands | (6197, 65, 3320), 3 behind their Pokemon |

## Dimensions

- Shell: x6176..6215, y64..89, z3304..3335, 40 x 26 x 32, two courses of calcite on all six faces. It is the whole
  spawn-free zone `gym_sabrina` (6176, 3304, 6215, 3335, measured from `data/spawn_suppression.json`), so the zone
  needed no change.
- Interior: x6178..6213 (36), z3306..3333 (28), y67..87 (21 over the floor course y66; stand y67).
- Top course y89 under the building's lowest course y92 (natural y90, y91): COVER 2, slack 0.
- Cells written: 41,659 (34,052 distinct cells; 374 commands in `cobblers:gym_arenas/gym6`).
- Light: 855 standable cells, minimum 5, median 10, 121 under 8.

## What was measured against the leader's size

- Sabrina's team (`data/gym_arena_sizes.json`): widest hitbox exeggutor 1.53, tallest hatterene 2.80 hitbox, model
  top 6.13, clear radius 2.09 (slowbro's model sweep), clear height 6.13. The check wants no block within 2.09 of
  either marker up to floor + ceil(6.13) + 1 = y74.
- Nearest solid to Sabrina's Pokemon marker within y67..74 is 5.50 (the dais face): 3.41 over the clear radius. To
  the challenger's marker it is 8.86 (a terrace post). The lens's lowest course is y77, ten courses over the floor
  (3.87 over hatterene's 6.13; three courses over the check's own ceiling). Both from the built model.
- The Pokemon markers are 4.00 apart against the widest hitbox 1.53.
- 122 cells can start a battle (within 16 with a line of sight); both Pokemon blocks and both stands are found from
  all 122. The terrace and the east flight are beyond reach, so no high cell starts a battle that Battle Positions
  could not place.

## The seat move

Sabrina is not in `single_leader.rollout`, so she keeps a second, Challenge spawner. `challenge_spawner.old_at` is
(6194, 111, 3312), restored to smooth quartz over air (read from the building's model, not typed).
`data/challenge_mode.json` `bosses.kanto_sabrina.spawner.at` moves from (6194, 111, 3312) to (6181, 70, 3318): two
north of the seat on the dais top (z3318, the same row of dais, a full purpur-and-quartz block with air above). No
zone change.

## Not verified

- Nothing has been built in a world. The block placement, light, the chains and end rods, the stair states
  (`smooth_quartz_stairs[facing=...]`) and the glass screens are model results only.
- Whether the tube's walls and the 6 x 6 quartz column standing in the Hall of Lenses' well read well from the
  hall and gallery (it is the one place the arena shows in the building), and that no later building step puts
  anything in it. The building's own audits were not rerun.
- That the Battle Positions blocks send Sabrina's Pokemon to their marks, that a battle on sight starts at 16 from a
  leader four courses up, and that a flying Pokemon stays under the lens.
- The decoy stacks D2 and D3 and the gallery are untouched, but the tube is a new solid in the well: whether any
  Pokemon spawn, or a player in the well, behaves differently there was not tested.
