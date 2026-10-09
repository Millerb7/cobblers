# The gyms as one walk-through building

The owner, 2026-10-09, after playing the arenas on staging: "With the gyms the fight areas are way better but
getting to them sucks. It should be a single building that a player walks through to the boss, a mini puzzle in
between of course with engaged fights, but not this climb up and around then go down 5 flights of stairs to get to a
room I can't leave from. I think the vibes of the rooms were good, use that to expand and then mash the puzzle from
the old building into it."

So each gym becomes one building on its lot: **entrance, a short puzzle (the old building's beats, condensed), the
juniors fought at its chokepoints, the arena as the last room**, the leader raised at the far end and the floor
between. The arena rooms' look, palette, dressing and civic role are kept and expanded; their size rules are kept
(each leader's clear radius measured from the jars, `docs/world-building/GYM_ARENAS.md`). Tool and record format:
`tools/gym_arenas.py`, schema `gym_hall/1` in `data/gym_arenas/SCHEMA.md`. Gym 1 is built on it as the pilot.

## 1. The room you could not leave (the defect, found 2026-10-09)

Play and the walk model disagreed: `tools/gym_arenas_audit.py` walked every arena down and back up. The audit replayed
ONE order -- building, arena, seat -- which is the order a full apply makes. The apply allows others:

- **R16G** (`tools/gym_buildings.py`) clears each building's bounds and rebuilds its masonry, every run. Seven arenas'
  descents pass through that masonry (gym 1's newel stair under the gallery's west end, `through_building`
  [1810, 139, 3694, 1815, 158, 3699]; gym 3's under the gallery's north end; gym 4's in the court floor; and so on).
  Run after R16GA with no R16GA after it -- `--only R16G`, which `tools/reapply.py`'s own R16G comment names as a
  supported run ("so `--only R16G` never leaves a leader two spawners") -- it **refilled the top of every descent**,
  with anyone below inside. Measured in the audit's own model: the challenger's stand reached the route's end in all
  seven building-hosted arenas after R16GA, and in **none of the seven** after R16G again.
- **R16F** (`tools/gym_demolish.py`) refills the old works under gyms 1, 3, 4, 5 and 7 with stone and clears the
  donor-shell boxes, every run, before R16GA. Its `dig` boxes overlap the arenas carved since (gym 1's
  [1812, 114, 3667, 1838, 139, 3703] against the arena [1808, 120, 3658, 1844, 138, 3705]). Run alone, it **filled
  the arena with stone**; it also aired out the standing buildings inside the shell boxes (all six of 3..8 failed the
  order replay).

Which arena the owner was in is not known (he did not say, and nothing here reads the world). The night's apply was
`run --only R16GA,R16DG,R16DR`, which leaves every arena open, so this is not proven to be what he met; it is the one
fault the model can produce, and it traps a player in every arena. No physical cause was found in the generated
functions: stair facings, half-block treads, newel landings, headroom over every tread, door states and the
spawners all walk both ways in the audit's body model (0.6 x 1.8, step 0.6), and no stair is re-shaped by a
perpendicular neighbour.

**The fix, in the generators, kept by the rebuild:**

- `tools/reapply.py gym_step_functions()`: R16G runs every arena (and every hall's takedown and hall) **after** the
  buildings and before the seat moves, so any run of R16G leaves the descents carved.
- `tools/gym_demolish.py`: never writes inside an arena's bounds and through boxes, a hall's bounds and takedown
  (`gym_arenas.reserved_boxes`), or the box a building clears and rebuilds (`gym_buildings.clear_box`).
- A walk-through hall has no building under it and no descent: its building record is `superseded_by` and R16G does
  not build it.

**Why the audit missed it, and what it does now:** it never re-ran a step. `tools/gym_arenas_audit.py` now reads the
apply's order from `reapply.gym_step_functions()` (R16E, R16F, R16G, R16GA), replays it, then re-runs each step alone
on the finished world and walks again (`ORDER`), and fails a step that changes any cell the arena writes (the
Challenge spawner the trainers cycle sets in a dais excepted: an arena run takes it out and the cycle puts it back).
Mutations of the generator, data untouched: dropping R16G's re-carve fails gyms 3-8 with `ORDER --only R16G ... not
reached`; dropping the demolition's reservation fails gyms 3-8 (not reached) and gym 1 (`changes 1670 of the arena's
own cells`). Both restored, all eight pass.

## 2. What every gym is held to

- **One building, on its own lot** (data/placements.json, fixed). Bounds inside the lot; the superseded building's
  bounds wholly overwritten; the old arena under the lot filled with stone by the takedown (`replaces.arena`, the
  record as built).
- **Entrance -> puzzle -> juniors -> arena, in that order, the arena last.** The puzzle is the old building's beats
  condensed onto one floor or a gentle grade: a total rise of four or five courses, stairs (half steps) rather than
  ladders, nothing one-way on the way in. A wrong choice costs a walk, never a softlock (a stair out of every pit).
- **The juniors where the walk must pass them**, proved by `python tools/gym_trainers.py check --gym <gym>`, whose
  leader goal for a hall is rctmod's battle on sight (forceBattleMaxDistance 16, in sight) since no player stands on
  a dais.
- **The arena keeps its rules**: clear disc at the measured radius round both Pokemon blocks, the dais 2 to 5 over
  the floor and not climbable, the first floor cell farther than 17 from the leader, Battle Positions found from every
  cell a battle can start, no standable cell at block light 0.
- **The way out is walked**: from the challenger's stand to the street, no fall over 3. Back the way you came, or a
  door past the leader: an iron door opened by a stone button inside the arena room, which nobody outside can press,
  so it is never a way in past the juniors (`check` and the audit both prove it).
- **Each leader's civic role stays** (the arena records' `reading`; `docs/world-building/TOWN_CHARACTER.md`).

## 3. The eight

Measured from the data (lots and levels from data/placements.json; the carved arenas' boxes and floors from
data/gym_arenas as built 2026-10-09; clear radius from tools/gym_arenas.py leader_size). "Below" is how far under the
lot the carved arena's floor lies today: that is the descent each one replaces. Layouts for gyms 2-8 are designs to
be measured by their authors with `check`; only gym 1 is built.

| Gym | Lot (x, z), level, facing | Carved arena today: floor, below the lot | Largest Pokemon (clear radius) | Juniors |
|---|---|---|---|---|
| 1 Brock | 1806..1845 x 3656..3703 (40 x 48), y141, north | y122, 19 below | Onix 10.56 | 3 |
| 2 Misty | 1592..1631 x 2858..2891 (40 x 34), template, north | y92, under the template | Pelipper 1.85 | 2 |
| 3 Surge | 1722..1752 x 1388..1432 (31 x 45), y174, west | y158, 16 below | Raichu 2.93 | 3 |
| 4 Erika | 4288..4332 x 1470..1512 (45 x 43), y110, south | y94, 16 below | Victreebel 5.28 | 3 |
| 5 Koga | 4574..4606 x 2463..2495 (33 x 33), y116, north | y100, 16 below | Drapion 3.13 | 3 |
| 6 Sabrina | 6180..6212 x 3302..3334 (33 x 33), y97, south | y66, 31 below | Slowbro 2.09 (Hatterene 6.13 tall) | 4 |
| 7 Blaine | 6154..6186 x 4980..5010 (33 x 31), y106, west | y84, 22 below | Charizard 4.09 | 4 |
| 8 Giovanni | 3556..3588 x 6400..6432 (33 x 33), y112, east | y90, 22 below | Rhyperior 3.45 | 4 |

### Gym 1, Brock: the Setting-Out Floor (BUILT, data/gym_arenas/gym1.json)

The masons' works, walked through. In at the north door (x1812..1814) from the forecourt, where the witness Brock
still stands (data/npc_seats.json, unchanged). **The yard strip** (x1809..1818, floor y141, stand y142) carries the
Stoneworks Hall's puzzle laid flat: the cutting floor; **the wall being raised**, three courses across the strip,
climbed only at its stepped east end (three stone-brick stairs, the Hall Mason at its foot); **the void**, six of
straw (a three-block fall, harmless) crossed by three beams at the wall's height, with a stair back out of the straw;
**the cross wall** and its three slots, two blind, the middle one through and lit from the landing behind it (the
Loft Foreman on the parapeted landing); three stairs down into the yard. Then **the cross passage** (z3699..3702, the
Coal Hauler before the door) and in at the far end of **the setting-out floor** (x1820..1842 by z3665..3697, 23 by
33, floor y141): polished andesite drawn on in calcite, cobble at the wall foot and dressed stone above, pilasters
and spruce tie beams hung with lanterns, the stage wall to wall across the north end, the trilithon behind Brock
(seat (1831, 144, 3667), three over the floor). Total grade: up three and down three, all half steps. Out by the
**iron door past Brock** in the east wall (1843, 142..143, 3675), its button inside (1842, 143, 3674), onto the
lot's east side and round to the forecourt; or back the way you came. Takes down: the Stoneworks Hall (its bounds
cleared and overwritten) and the undercroft with its newel stair (stone, y120..140). Numbers: builder check clean
(approach 30.1, dais 3, 219 battle-start cells, all find the markers; light min 1); audit clean (street to stand and
back, every order, takedown 0 cells left); juniors proved (3 of 3).

### Gym 2, Misty: the Lifeboat House (the template stays)

Misty's hall is the one COBBLEVERSE template and is kept exactly as built (the owner, 2026-09-29); her climb is the
well, which the owner endorsed ("on misty, thats the way to go up"). Her route already ends where the walk-through
wants it: the ledger gallery's south door opens on a six-tread slipway (a gentle grade) into the boat house. **What
changes:** nothing above the cistern; a **way out past Misty** -- the launch channel is the natural one, through an
iron door with its button inside onto the quay -- is to be MEASURED first (where the channel meets the lake, and
whether its mouth is above water; nothing here has measured it). Until then, back the way you came, up the well's
scaffolding. No takedown. Juniors unchanged (2).

### Gym 3, Surge: the Relay Works and the Grounding Hall

Lot 31 by 45, facing west: the long axis runs east-west. In at the west end; **the bus floor** with the transformer
tower climbed by its seven tuff steps (now stairs) onto the catwalk; **the three downleads**, one whole (the choice);
**the live bus** with its two-block isolator over a bale floor three below, a stair back up; the duct; then **the
Grounding Hall** as the last room, the switch hall with its transformer banks in their oxidation order, sunk three
courses under the bus floor by one broad stair ("where the line is earthed"), Surge on the cab at the east end.
Raichu's radius (2.93) lets the hall be 15 wide beside a 10-wide puzzle strip. Out by an iron door past the cab, or
back. Takes down the Relay Works and the switch hall carved at y158 (its bounds run beyond the lot to x1759,
z1439: the takedown fills them, measured from the record).

### Gym 4, Erika: the Great Glasshouse and the Root Court

Lot 45 by 43, facing south, the largest after Brock's. In from the green; **the beds** and the bench runs (four
half steps up); **the low canopy** and **the three boughs**, only the living one walkable (the choice), down its
stair -- not the nine-block drop of today -- into **the Root Court** as the last room: the round mediation court at
the cherry's roots, sunk four under the glasshouse floor, Erika on the dais across it. Victreebel (5.28) needs a
court about 13 across clear of roots. Out by the court's garden gate past Erika (iron door, button inside), or back.
Takes down the glasshouse and the ring court at y94 (43 by 43 under the lot and beyond it).

### Gym 5, Koga: the Reed House and the Tracking Floor

Lot 33 by 33, facing north. In by the jetty; **the reed stair** onto the drying loft (three half steps); **the plank
walks** over the flood, a wrong plank a splash into two-deep water with a ladder out; one **breathing tank** swum
under its screen; then **the Tracking Floor** as the last room at the lot's level: the lanes divided by screens that
hide Koga until the last turn (kept), Koga at the far end. Drapion (3.13). Out by the jetty door past Koga, or back.
Takes down the Reed House (its flue and watch floor) and the range at y100.

### Gym 6, Sabrina: the Hall of Lenses and the Observation Well

Lot 33 by 33, facing south. In to **the reading stacks** (find the one true eye-arch: the choice), **the gallery**,
the turret climbed by a stair of four instead of its ladder, **the lens chamber**; then **the Observation Well** as
the last room, kept the tallest of the eight but turned upward: at the lot's level, open twenty or more courses to a
tinted lens hung over the floor (the clear height must take Hatterene, 6.13 in the table; the audit measures
Exeggutor 3.53: whichever is larger rules), Sabrina on the dais. Out past her, or back. Takes down the Hall of
Lenses and the well at y66 -- the deepest descent of the eight, 31 below the lot.

### Gym 7, Blaine: the Assay House and the Core Gallery (BUILT, data/gym_arenas/gym7.json)

Lot 33 by 31, facing west. In over **the spoil steps**; **the broken flight** (one gap over a bale floor, a stair
back); **the gantry stair** and **the gauge gallery**; **the four hoods**, one true; then **the Core Gallery** as the
last room, sunk three under the house floor by a broad stair ("into the core"), the banded strata in the walls and
the lava behind glass kept, Blaine on the dais. Charizard (4.09). No one-way geyser on the way out: an iron door past
Blaine, or back. Takes down the Assay House and the gallery at y84 (the adit's lanterns and walls go with it).

**As built (2026-10-09, offline only).** One gabled house on the whole lot, x6155..6186 by z4980..5010, house floor y106,
the Core Gallery north of the house and three under it. In at the west door (z5002..5004) from the causeway's end
(apron x6154 with lamp posts). **The drill floor**, then **the spoil steps**: three tuff-brick treads up to the deck's
level (y109) through the only opening in the wall at x6164. **The deck** (x6165..6168), then **the broken flight**: a
three-wide acacia catwalk (z5002..5004) over straw, the planking either side gone; a step off it is a drop of three onto
straw and a four-wide stair back up to the deck. **The second deck** (x6175..6177), then **the four hoods** in a wall
five thick (x6178..6182): each a stair of three treads down to the flue floor (y106); three end at a wall on straw, the
third (z5004..5005, hooded in chiselled blackstone with a lantern either side) goes on into **the flue's foot**, a
passage two wide along the east wall, north through the dividing wall onto the gallery's upper floor (y106), and down
**the broad stair** (fifteen wide, three treads) into **the Core Gallery** (x6157..6184 by z4982..4996, floor y103, 28 by
15): the strata in the walls and in six glass core tubes, four ember bays of magma behind glass in the north wall, ribs
with hung lanterns above y111, and at the west end the stage (top y106, three over the floor) with the bore-hole behind
it: a seven-by-seven window of lava one deep, sealed in the wall behind glass, a magma sill under it, copper pylons
either side. Blaine's seat (6159, 106, 4987); his Challenge cell (6159, 106, 4982) at the stage's north end. Out by the
iron door in the east wall at the stair's head (button inside), or back the way you came. Total grade: up three, down
three (the hoods), down three (the broad stair), all half steps. Takes down the Assay House (the lot cleared from y106,
the footing y103..105 rewritten) and the carved gallery (bounds as built, clipped to y102; see the record's
`replaces.arena.clipped_why`). Juniors: Assay Hand on the deck behind the wall's opening, Rim Researcher at the
catwalk's end, Flue Keeper and Stair Stoker in the flue's foot passage.

### Gym 8, Giovanni: the Gate and the Muster Hall

Lot 33 by 33, facing east. The gate mass stays the face of the building. In through **the yard**; **the sap** (a short
trench, down two and up two); **the shored heading**, dark; **the undercroft**; then the sally, its four ranked
bulkheads as the approach corridor, and **the Muster Hall** through the blast door as the last room at the lot's
level, Giovanni on the dais; the gate walk above stays as the town's face, no longer the way. Rhyperior (3.45). Out
by the postern past Giovanni (iron door, button inside), or back. Takes down the Gate of the South's interior and the
bunker at y90.

## 4. For the seven authors

Write `data/gym_arenas/<gym>.json` as a `gym_hall/1` record (SCHEMA.md), gym 1 as the example; keep the old record
under `replaces.arena`; mark the building `superseded_by`; re-seat the juniors; run, until each prints no problem:

    python tools/gym_arenas.py check --gym <gym>
    python tools/gym_trainers.py check --gym <gym>
    python tools/gym_arenas.py build && python tools/gym_demolish.py build && python tools/gym_buildings.py build
    python tools/gym_arenas_audit.py --gym <gym>          # another agent's audit: read its verdict, do not tune it
    python tools/gym_arenas.py probes --write

What a hall must not do: write outside its lot; leave a cell of the old building or an open cell of the old arena;
put a button that opens a door within reach of anyone who has not reached the arena; make the way back need a jump
over a gap or a fall over three.
