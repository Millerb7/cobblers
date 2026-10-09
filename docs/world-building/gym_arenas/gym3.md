# Gym 3: Lt. Surge, The Grounding Hall

Record: `data/gym_arenas/gym3.json` (schema `gym_arena/1`, tool `tools/gym_arenas.py`). Offline checks only: nothing
here has been built in a world or seen in a running game. Numbers below are the tool's own output
(`python tools/gym_arenas.py check --gym gym3`) or measured from the model it builds; the survey figures are from
`data/gym_arenas/survey.json`.

## The reading

Surge's town keeps the power, the relays and the storm gear running (`TOWN_CHARACTER.md` gym3_town: deepslate and
tuff, weathered and waxed copper). The Relay Works above is the substation where the feeder from his array lands.
Under it is where the line is earthed: a deep switch hall. Transformer banks stand along both walls, each bank one
stage further up copper's oxidation ladder (oxidised, weathered, exposed, bright), with lightning rods on every
bank; three bus runs hang from the ceiling on chains, two weathered and one bright, as the building above carries
them; and down the floor runs one course of waxed copper, oxidised at the door and bright at the dais, with a pair
of ochre froglights set in the floor every third course. That is the signal line the player walks: the current
rising as it comes in. At the far end Surge stands in a control cab four courses up, between two generator
housings, in front of a board of redstone lamps whose lit columns rise to a peak over his head.

It is not Brock's hall: no colonnade, no nave, no stage wall to wall. Machinery on both walls, a line in the floor,
a board behind the leader. Every copper block is waxed, so the gradient stays where it is put (unwaxed copper
oxidises over time).

## The walk in

1. The puzzle route ends in the cable-head gallery (4 wide, 13 long, cut in the rock), at (1747, 191, 1414), one over
   Surge's old spawner. At the gallery's north end the floor opens on the head of a stair: the feeder's own, wound
   round a weathered-copper conduit (ring x1746..1749, z1404..1407). The gallery's chest (1747, 191, 1406), barrels
   and lanterns are not touched; the conduit stands under the chest.
2. The stair winds down four turns, 49 treads, 32 levels, from the gallery floor (y190) to the hall floor (y158),
   lit by lanterns set into the conduit. The deepest step off the gallery into the opening is three (no damage).
3. A landing at (1748, 158, 1407), then the cable door: one wide, three high, two long, through the hall's north wall.
   Its jambs and lintel on the hall side are oxidised copper.
4. The hall: 19 wide, 28 long, 11 of air over the floor. The signal line starts at the player's feet, dull green,
   and runs 23 blocks to the cab's face at z1433, brightening as it goes. The banks stand either side; the
   ceiling busses run overhead. Nothing blocks the line: the bays are flush against the walls.
5. Surge stands on the cab, four courses over the floor, in front of the lamp board. 25.3 from the door: farther than
   rctmod's forceBattleMaxDistance + 1 (17), so the player is in the hall before he can call the fight. The
   housings close the cab on both sides, so there is no aisle beside it and no way up.

## Where they stand

| | |
|---|---|
| Surge's seat | (1748, 162, 1435), the spawner flush in the cab top, redstone block at y161; trainer stand block (1748, 161, 1434) |
| His Pokemon | (1748, 157, 1427): 5.5 from the cab's face (cell edge z1433.0 against z1427.5) and 6.5 from the nearest bank |
| The challenger's Pokemon | (1748, 157, 1420), 7.0 behind his; challenger stands (1748, 157, 1417) |
| Challenge spawner | (1746, 162, 1435), two west of the seat, moved there from the gallery (1747, 190, 1412) |

## Dimensions

| | |
|---|---|
| Shell | x1737..1759, y156..171, z1408..1439 (23 x 16 x 32), two courses all round; the stair's ring and walls add x1745..1750, z1403..1408 |
| Floor | y158 (stand at y159), interior x1739..1757 (19) by z1410..1437 (28), air y159..169 (11) |
| Cab | x1743..1753, z1433..1437, top y162 (4 over the floor), face at z1433 |
| Housings | x1739..1742 and x1754..1757, z1430..1437, top y166 |
| Banks | x1739..1741 and x1755..1757, four bays each at z1411, 1416, 1421, 1426 (4 long), seams between |
| Approach | 23 blocks from the door (z1410) to the cab's face (z1433); 25.3 from the entry cell to Surge |
| Written | 15,948 cell writes (8,824 solid, the rest air) in 309 commands in `cobblers:gym_arenas/gym3`, before the move |
| Cover | slack 0: the top course y171 under natural top y173 (the lot's pad at 174 less one) |

## What I measured

- Surge's measured team (the survey): clear radius 2.93 (Raichu's model sweep), clear height 1.96 (Electabuzz).
  Against it, measured on the model: the nearest solid to his Pokemon's block in y159..161 is 5.5 away (spare 2.57),
  to the challenger's 6.5 (spare 3.57); the ceiling is 11 over the floor against the 3 the rule asks (clear height
  rounded up, plus the send-out's one); the clear floor across is 13 (x1742..1754) against 2 x 2.93 = 5.9.
- The check: no PROBLEM. 116 cells a battle can start from, all four Battle Positions blocks found from all 116;
  block light min 6, median 12, 6 cells under 8; dais 4; Pokemon 7.0 apart (widest hitbox 1.5).
- The shell top is the survey's maximum for this lot (171); the floor is 8 under the survey's maximum (166), the
  descent is 32 levels where the survey's was 24, because a taller hall was worth a longer stair.
- Zone: `gym_surge` (1720..1759 x 1384..1439) already holds the arena (x1737..1759, z1403..1439); no change.

## Notes and what is not verified

- The old Challenge spawner at (1747, 190, 1412) is taken out by `gym3_seat` under its guard; the data value
  `bosses.kanto_ltsurge.spawner.at` is the one edit to `data/challenge_mode.json`. Its `why` there still describes the old
  position and was left alone on purpose.
- Redstone lamps are lit only where a redstone block touches them (behind the board, in the shell). A lit lamp with
  no power would switch itself off. Lightning rods are underground and below the surface height, so they cannot be struck.
- Not verified: anything in a running game. That the lamps stay lit after a chunk reload; that Battle Positions sends
  Surge's Pokemon to its block here; that a battle on sight starts at 16 from a leader four courses up; the bind-pose
  model sweep as the real clearance; that no vanilla update turns a lit lamp off; that the block ids with a state
  (`ochre_froglight[axis=y]`, `lightning_rod[facing=up]`, `redstone_lamp[lit=...]`) are accepted by the server as
  written (they are vanilla 1.21.1 ids).
