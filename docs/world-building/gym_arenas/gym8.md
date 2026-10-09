# Gym 8: Giovanni, The Sally and the Muster Hall

`data/gym_arenas/gym8.json`, authored 2026-10-08. Offline checks only (`python tools/gym_arenas.py check --gym gym8`);
nothing here has been built in a world or seen in a running game.

## The reading

Giovanni's civic role is civil defence. His building is The Gate of the South (`data/gym_buildings/gym8.json`): a
gatehouse, a gate mass seven wide with the walk on top of it where he stands, a muster yard below. A garrison keeps
its bunker under its gate, so the arena is that bunker: the command post that holds when the gate does not. Heavy
and plain, polished deepslate and deepslate brick, with the town's orange (`TOWN_CHARACTER.md` gym8_town: terracotta,
polished granite, spruce, coarse dirt, mud brick) as the garrison's marks. He is a ground type, so the far end is not
more masonry: the shell gives out to the earth it was dug into.

It shares nothing with Brock's hall (a long colonnaded undercroft, a wall-to-wall stage). Here there are no columns;
the approach is a separate low corridor under bulkheads, the hall is a wide room with ribs on wall piers, and the
leader stands in a rock-walled dug-out behind a timber doorway.

## The walk in

1. **The gate walk (y121).** The player ends the puzzle route on the walk beside Giovanni's old cell (3565, 120, 6416).
   At the walk's north end (x3564..3566, z6405..6407) the gate mass is opened: a 3 x 3 newel stair in granite, the
   gate's own stone, round a polished granite post. The first tread is level with the walk; 61 treads, 30 levels, down
   through the gate mass, the building's rock and the two natural courses, lamps (glowstone) set into the post every
   six courses.
2. **The sally (y91).** A door one wide and three high at the foot (3567, 91..93, 6405) opens east into the approach:
   21 long, 5 wide, 5 high, deepslate tiles with a polished granite centre line, a glowstone flush in the ceiling in
   every bay. Four bulkheads cross it, every four blocks from x3572: chiselled jambs, a brick lintel, an opening three
   wide and three high. The nth bulkhead carries n orange rank marks on its west face (1, 2, 3, then 3 and one below).
3. **The blast door.** At the corridor's east end (x3586..3588) the player turns south through a passage three wide,
   four high and two thick (z6408..6409): chiselled jambs, a chiselled lintel with two glowstones, an orange sill
   and an orange course over it.
4. **The muster hall.** First floor cell (3587, 91, 6410). A hall 31 long (x3559..3589) and 19 wide (z6410..6428), nine
   high (y91..99), deepslate tiles with a polished granite axis down it from the dais to the door. Three ribs
   (x3566, 3574, 3582) at y98..99 each on a pair of wall piers, glowstone flush in each rib's underside at three
   places. On the east half orange 2 x 2 muster squares in ranks, sandbag stacks (mud brick) by the walls. The south
   wall's foot is bare rock: granite with coarse dirt, tuff and dripstone block, shored by three pit-props and a
   head-tree. At each Pokemon's mark a 3 x 3 orange square on the floor.
5. **The dug-out.** At the west end two raw granite wings (x3554..3562, with coarse dirt, tuff, dripstone block in their
   faces) close the hall in to a mouth nine wide, framed by two stripped spruce posts and a head-tree at y97. Beyond
   it the apse: rock walls and roof, the command dais (x3555..3558, z6414..6424), and on the back wall a situation
   map of terracotta contour bands (brown, orange, plain) with three glowstone signal lamps.

## Where they stand

| | |
|---|---|
| Giovanni | seat (3556, 94, 6419), spawner flush in the dais top (polished granite), redstone at y93; the trainer stand block (3557, 93, 6419), one in front |
| Challenger | walks the hall; the challenger's Pokemon mark (3573, 89, 6419) stands at (3573, 91, 6419) on the floor, the player stand block (3576, 89, 6419) |
| Giovanni's Pokemon | mark (3568, 89, 6419) |

## Dimensions (measured by the tool and my scripts on 2026-10-08)

| | |
|---|---|
| Shell | x3552..3591, y88..101, z6400..6431 (40 x 14 x 32), two courses all round; exactly the spawn-free zone `gym_giovanni` (no change to `spawn_suppression.json`) |
| Floor | y90 (a player stands at y91); hall air y91..99, vault y100..101; top course y101 with y102..103 natural over it and the building's rock from y104 (cover slack 0) |
| Dais | 4 high (top y94), face at x3559.0 |
| Hall | 31 x 19 plus the 9-wide mouth and the apse |
| Approach | entry.floor (3587, 91, 6410) is 32.5 from the leader's stand; the walk from route end to entry floor is 90 cells (no jump; falls of at most 3), back up 96; the dais foot is 125 cells from the route end |
| Written | 25,632 cells, 421 commands in `cobblers:gym_arenas/gym8` |
| Checks | 116 cells a battle can start from, all four Battle Positions blocks found from all 116; block light min 2, median 6 |

## Size against the largest member (Rhyperior: clear radius 3.45, clear height 3.78)

- Radius: the nearest block to Giovanni's Pokemon mark within y91..95 is 7.11 away (the proscenium post), so 3.66 spare;
  to the challenger's mark 7.52, so 4.07 spare. The mark is 9.5 from the dais face (3.45 needed).
- Height: air is y91..99, nine courses, over both marks; the tool requires five (`ceil(3.78) + 1`), so four spare.
  Under a rib (y98..99 filled) it is seven, two spare. Nothing solid stands over either mark.
- The two marks are 5 apart (the widest hitbox is Hippowdon's 2.2).

## The seat move

Giovanni is not in `single_leader.rollout`, so: `challenge_spawner` is set in the arena (`old_at` (3565, 120, 6418), the
Challenge spawner the trainers cycle set two south of his old cell, restored to granite over granite, the gate mass's
own blocks), and `data/challenge_mode.json bosses.kanto_giovanni.spawner.at` moves from (3565, 120, 6418) to
(3556, 94, 6421), two south of the new seat, flush in the same dais top. Only that value was edited. The `why` and
`measured_by` text beside it still describe the old position (the brief limited the edit to the one value).

## Not verified

- Nothing is built in a world. The stair's treads, the door cells, the bulkhead openings, the hall's look and the
  light by eye are model results only.
- That Battle Positions sends Rhyperior to the mark here; that a battle on sight starts at 16 from a leader four
  courses up; the bind-pose model sweep as real clearance.
- The through-building cut (the stair through the gate mass, x3563..3567, z6404..6408, y102..123) was not run
  against the real building as R16G leaves it in a world; the tool's model of the building was used. It replaces
  gate-mass granite and rock with granite and polished granite, and carves air over the treads; it touches nothing
  of the sap, the drift, the undercroft or the gate's inner stair (checked by their boxes in `gym_buildings/gym8.json`).
