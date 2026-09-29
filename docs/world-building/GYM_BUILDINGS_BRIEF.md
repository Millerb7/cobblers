# The gym buildings — the owner's redesign, 2026-09-29

## What was rejected, and why

Five gym interiors were built on 2026-09-29 as a shaft down from the
COBBLEVERSE donor shell into works carved in the rock beneath. The owner
rejected the pattern on sight:

> "these gyms arent it, a scaffold to a cave feels dumb every time, i get
> it on misty, thats the way to go up, but id rather have a large gym
> building with a puzzle inside than whatever that was."

The reason it went underground is recorded and is not a mystery: the
donor shells are placed whole and `data/gym_interiors.json` declared
`not_touched: everything in the shell except the healer's cell`, and the
donor interior is *one oval room, 160-248 floor cells, no second storey*.
With the inside off-limits there was nowhere for a puzzle but below.

## The decisions

1. **The donor shells are replaced by authored gym buildings** at gyms
   1, 3, 4, 5 and 7. The puzzle lives inside the building.
2. **Gym 2, Misty's, is kept exactly as built** and is not to be
   touched. Her shell is 36x40x32 and going down the 42-cell well *is*
   the building; the owner said so explicitly.
3. **The five sets of underground works are filled in.** The carve is
   reversible from the heightmap, so nothing is lost that cannot be
   rebuilt.
4. Gyms 6 and 8 are not in scope. Sabrina's (8) is out by earlier
   instruction.

## The envelope — CORRECTED 2026-09-29

**The first version of this table was wrong and is replaced.** It gave
the largest flat square the raw heightmap allows around each donor, and
called Surge's site "23x23, hillside, cannot grow". That is not the
envelope. Every gym has an **authored, levelled lot** in
`data/placements.json` under its settlement's `plan.anchors.<gym>_gym`,
with a `rect` and a `level`. The town build levels that pad, so the
building sits on flat ground at `level` whatever the raw terrain does.

| gym | leader | donor | **lot (the envelope)** | **pad y** | raw ground under it |
|---|---|---|---|---|---|
| gym1 | Brock | 27x24 | **40 x 48** | y141 | y140..142 |
| gym3 | Surge | 23x27 | **31 x 45** | y174 | y174..212 |
| gym4 | Erika | 27x23 | **45 x 43** | y110 | y109..110 |
| gym5 | Koga | 27x24 | **33 x 33** | y116 | y114..116 |
| gym7 | Blaine | 23x27 | **33 x 31** | y106 | y106 |

Build inside the lot rect, on the levelled pad, and leave a margin so
the building does not sit hard against the lot edge (Brock's hall is
33x36 in a 40x48 lot, margins 4/3/8/4).

**Surge's site does not step down a slope.** Its raw ground rises 38
blocks across the lot, but the pad is levelled to y174, so what the hill
gives him is a cut rock face on the uphill side, not a staircase
building. `data/placements.json` says of his lot: *"an electric gym
should read as workings in the rock, not a hall on a lawn"* — that is
the character to build into, on flat ground.

## What every gym building must still carry

- one `rctmod:trainer_spawner` for the leader, reachable only by
  finishing the puzzle;
- the leader's chest;
- **no healing machine.** Healers were deliberately removed from all
  eight gyms and the re-apply step asserts it.

## Rules that bind this work

- Ground comes from the heightmap, never from a world save.
  `tests/test_ground_rule.py` enforces it.
- **Whoever builds does not write the audit or the tests.** CLAUDE.md
  principle 16. It was broken on the interiors: the builder wrote
  `tools/gym_interiors_audit.py` and `tests/test_gym_interiors.py`, that
  audit reported CLEAN, and an independent one then found 13 problems
  including a gym that could not be completed.
- A refusal ends the attempt.

## What the independent audit already knows to look for

From `docs/world-building/GYM_INTERIORS_REVIEW.md`, on the rejected
interiors. Every one of these is a defect class the new buildings can
repeat:

- a route step that no player can physically make (Erika's one-high
  flooded drain entered from a dry cell);
- a puzzle skipped by a sprint jump (Brock's pit) or a hop between
  decoys one block apart (Koga's fen);
- leaves without `persistent=true`, which decay;
- open-topped water sources that flow out of their box;
- **blocks placed with no support** — 31 lanterns across five gyms stand
  or hang in mid-air and pop on the first block update. `setblock` does
  not check support, so nothing reports a problem. Four of them were
  confirmed missing by reading dryrun12 back (F10).
