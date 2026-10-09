# Gym 8: Giovanni, The Gate of the South and the Muster Hall

`data/gym_arenas/gym8.json`, schema `gym_hall/1`, authored 2026-10-09 as one of the eight walk-through halls
(`docs/world-building/GYM_WALKTHROUGH.md`). Offline checks only (`python tools/gym_arenas.py check --gym gym8`,
`tools/gym_arenas_audit.py`, `tools/gym_trainers.py check`); nothing here has been built in a world or seen in a
running game. It replaces the carved arena of 2026-10-08 (22 courses under the lot, a 61-tread newel stair from the gate
walk), which is kept in the record under `replaces.arena` and taken down by `gym8_takedown`.

## The reading

Giovanni's civic role is civil defence: his town is the southern garrison and its gym is the gate. The gate is shut (a
sheer granite face on the yard, the blind arch of the gate that does not open let into it in terracotta), so the way past
is the way a garrison takes a shut gate. The hall behind it is the post that holds when the gate does not. A ground type,
in his own ground: the earth the bunker was dug into shows at the wall foot and in the dais's flanks.

## The walk (lot 3556..3588 x 6400..6431, pad y112, facing east)

Measured in the model: 48 steps from the street cell (3589, 111, 6404) to the challenger's stand (3565, 113, 6422); the
lowest the walk goes is y111 (down 2 from the yard), the hall is at the pad.

1. **The yard** (x3575..3587, z6401..6409), open to the sky, entered by the gate in the east curtain over a two-step
   sill (the street's heightmap is y110 along the lot's east edge). Three wells in the paving: two cisterns one course
   deep with nothing in them, and **the sap**, the only one with a headframe over it and a lamp: the same tell for every
   player. The shut gate fills the yard's west side; the postern, an iron door, is in a recess beside the blind arch.
2. **The sap**: three wide, two stairs down to the drift's floor (y110). The Sapper stands on the trench floor.
3. **The drift and the headings** under the keep: three headings off it, two of them two cells and a face, the east one
   three wide, shored with a stripped-spruce crown and lit. The Heading Guard stands where the drift turns, the
   Undercroft Sentry in the shored heading.
4. **The way up**: two stairs, three wide, to the sally's floor (y112).
5. **The sally** (x3575..3587, z6422..6426): five wide, five high, under four ranked bulkheads (the nth carries n orange
   rank marks; the blast door's lintel the fourth). The Wall Captain stands in its first bay.
6. **The blast door** (x3573..3574, z6423..6425) into **the muster hall** (x3558..3572, z6402..6429, floor y112, 15 by 28,
   seven high): deepslate tile and polished granite, orange marks where the garrison falls in, ribs on wall piers,
   pit-props, sandbags, the command dais at the far end (x3560..3570, z6402..6406, top y116) with Giovanni on it
   (seat (3565, 116, 6404)) under the situation map on the back wall. First floor cell 21.6 from the leader.

Out: back the way you came (every stair is walked both ways), or the postern past Giovanni: an iron door in the hall's
east wall at the dais's flank (3573, 113..114, 6408), opened by the stone button inside it (3572, 114, 6407), out
through a recess in the gate's face onto the yard and east to the gate. Nothing in the yard can press the button.

## What it takes down

The old Gate of the South (`data/gym_buildings/gym8.json`, now `superseded_by`): the hall's first parts clear the lot
above the pad (the donor shell, the gate mass, curtain, walk and stair) and overwrite the building's nine courses under
it (y104..111) with stone; the old arena (bounds x3552..3591, y88..103) is filled by `gym8_takedown`. The gate walk
remains as a deck at y121 on the gatehouse, unreachable: the town's face, no longer the way.

## Not verified

Everything in a running game. Ground at the east edge is the heightmap's y110; if the town's prep leaves the street
higher the sill is a step down, which the gate still walks. The Challenge spawner cell (3565, 116, 6402) is two behind
the seat on the dais's back row (outside the old building's bounds on purpose: `tools/gym_arenas.py replaced_seats` counts a Challenge cell inside them
as a replaced seat, and the audit then fails it as a spawner left standing).
