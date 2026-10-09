# Gym 2: Misty, The Lifeboat House (a walk-through hall)

Record: `data/gym_arenas/gym2.json` (schema `gym_hall/1`). Tool: `tools/gym_arenas.py` (R16G, R16GA). Below and
beside it: `tools/gym_demolish.py` (R16F). Authored 2026-10-09; offline checks only.

The owner, 2026-10-09: "Misty needs to have the template building removed, make it match the rest of the world."
That reverses the 2026-09-29 keep. The COBBLEVERSE template `cobbleverse:misty`, its rock plinth and quay, the works
carved under it (the well, cistern, race and ledger gallery) and the 2026-10-08 boat house carved under the lot all
come down, and Misty's gym becomes one building on her lot like the other seven.

## The reading

Misty's town is the lake's rescue service, the town that takes in whoever the water brings
(`docs/world-building/TOWN_CHARACTER.md` gym2_town: rescue boats, a record of every arrival; prismarine and mud brick,
dark oak, spruce). The gym is now the rescue station itself: a mud-brick building with its back to the lake, a spruce
roof deck railed in dark oak with a lantern at each corner. The boat house the owner liked is its last room, kept as it
was (prismarine quay, launch channel with the boat lying in it, buoys, lifeline, lifebuoy on the end wall, the lookout
deck), moved up onto the lot by (dx 0, dy +13, dz -4).

## The site, measured (tools/ground.py rounded; tools/bridges.py water())

- Lot: `data/placements.json` gym2_town anchor `gym2_gym`, x1592..1631 by z2858..2891. It has no `level`: it
  straddles the bank, ground y108 along the promenade (y107 east of x1626) falling to y104 at the south-east corner.
- Water: the mask marks NO column of the lot wet. The lake (lake_viltri, level y103) begins at z2896 on the lot's
  east edge (x1628..1631) and further south to the west. Nothing in the hall is at or below the lake's level next to
  it: the boat house's south wall is on the lot's edge (z2891) over ground y104..106.
- The only other data on the lot (scanned every `data/*.json`): the template's own placement and seven of the 17
  lanterns of `gym2_town_lights` (tools/light_plan.py, planned from a model that held the template). The hall clears
  them every apply and carries its own light; the light plan wants re-running.

## What comes down, and by what

| What | Box | By |
|---|---|---|
| The template `cobbleverse:misty` and its spawner (1605, 132, 2874) | [1594, 107, 2859, 1629, 146, 2890] | the hall's first parts: the lot cleared y105..147 (the hall's bounds reach one over the template's top) |
| The quay plinth (prismarine from y100, `placements.json` gym2_misty_gym `plinth`) | [1594, 100, 2859, 1629, 106, 2890] | y101..106 the hall (rock y101..104, then its own floors); y100 R16F, rock |
| The works (`gym_interiors.json` gym2 `dig`) | [1598, 84, 2861, 1626, 106, 2881] | R16F, rock (ground y106..108 over all of it), less what the hall and its takedown write |
| The 2026-10-08 boat house (`replaces.arena.bounds`) | [1592, 88, 2877, 1631, 102, 2895] | the hall's takedown (`gym2_takedown`), stone: the box is under the ground at every column (lowest ground y103) |
| The shore stair added 2026-10-09 (ca4c84b), never applied (`replaces.arena.exit_passages`) | [1594, 92, 2896, 1596, 108, 2907] | R16F, back to the ground: rock under it, air over it. Five of its columns are wet-but-not-definite (ground rounds to the lake level y103): their y103 course is left to the world |

R16F for gym 2 (measured from `python tools/gym_demolish.py build`): 107 commands, 9,579 cells to rock, 144 to air,
0 to water. The donor step (R9) still stamps the template every apply, as it does the other seven donors; R16F and the
hall take it down again in the same apply. The old Challenge cell (1627, 95, 2885) is inside the takedown;
`data/challenge_mode.json` keeps it as `superseded_at`.

## The walk (entrance to arena, one building, a total fall of three courses)

1. **The door** from the promenade, two wide, x1611..1612 in the north wall; the forecourt row (z2858) paved in the
   promenade's prismarine at its own level. Sea lanterns set in the facade light it.
2. **The arrivals hall** (z2861..2864, floor y108, level with the promenade): lockers, the arrivals board.
3. **The step down**, the one way on: a two-wide stair (x1626..1627) in the cistern wall at z2865, one course down.
   **The Quay Swimmer** (gym2_junior_01) stands at its head, (1625, 109, 2864), facing back down the hall.
4. **The race** (z2866..2871, quays at y107): a still canal wall to wall, three wide, a shelf a course deep along each
   bank and two deep down the middle, lit from its bed. Wade, swim, climb out. Nobody walks round it.
5. **The three mouths** (x1606, 1614, 1622) in the wall under the far bank, alike. The east and middle ones are blind,
   five deep, ending at the boat house wall; the west one has light in it (a sea lantern in the far wall, on its line).
   The old cistern's puzzle condensed: no switch, only which mouth has light. A wrong choice costs a walk.
6. **The ledger gallery** (x1594..1609, z2874..2876, dark oak floor y107), the ledger shelved along it. **The
   Lifeguard** (gym2_junior_02) stands in its middle, (1600, 108, 2875), facing the true mouth.
7. **The slipway**: two treads (x1594..1596) down through the boat house's north wall to its floor, y105.
8. **The Lifeboat House** (x1594..1629 by z2879..2889, floor y105, 36 by 11): Misty on the lookout deck at the east
   end, seat (1627, 108, 2883), three over the quay; first floor cell (1595, 106, 2879) 32.4 from her.

## The way out (exit kept as a door past the leader; the shore stair dropped)

Over the gangway across the launch channel at x1622, an iron door in the south wall (1622, 106..107, 2890) opened by
the stone button inside (1623, 107, 2889), and out through the outer course onto the shore at z2892, ground y104
(dry), one step down. Nothing outside opens it. Or back the way you came. The 2026-10-09 shore stair (an eleven-tread
passage up from a deep arena) is dropped: on the lot the boat house's floor is a course over the shore, so a door is
enough.

## Juniors

Two seats proved (`python tools/gym_trainers.py check --gym gym2`: proved, arrival "sky", nothing assumed closed). A
third chokepoint exists (the slipway, more than 16 from Misty) and waits on a roster:
`data/gym_junior_trainers.json` gyms.gym2 below_minimum says so.

## Verdicts (2026-10-09, offline)

- `python tools/gym_arenas.py check --gym gym2`: clean. 88,413 cells, 275 commands, dais 3, approach 32.4, gap 8.0,
  battle start cells 78 (all find the four Battle Positions blocks), light min 4.
- `python tools/gym_arenas_audit.py --gym gym2`: clean (street to stand and back, every step order, the template box
  and the plinth wholly written, the old arena left solid, the shore stair box back to the ground). It notes the size
  table's floatzel height (1.53) against the model's 1.72, as before.
- Mutation (generator, data untouched): R16F without its plinth and passage boxes fails the audit's TAKEDOWN (184 plinth
  cells at y100 never written).

## Not verified

Nothing here has been built in a world or seen in a running game. The water's stillness in the race and the launch
channel, the iron door and button, the battle on sight at 16 through the deck rails, and whether a rider lands on the
roof deck are runtime questions for staging.
