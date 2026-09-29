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

## The measured envelope

Ground from `tools/ground.py` (the canonical heightmap, rounded), never
from a world. The envelope is the largest square centred on the donor
that holds ground spread <= 5 and stays >= 6 blocks clear of the nearest
neighbouring placement anchor in `data/placements.json`.

| gym | leader | donor footprint | buildable | ground | note |
|---|---|---|---|---|---|
| gym1 | Brock | 27x24 | **89x89** | y139, spread 3 | open, flat |
| gym3 | Surge | 23x27 | **23x23 only** | y174..197 | **hillside, 23 blocks of fall** |
| gym4 | Erika | 27x23 | **47x47** | y109, spread 2 | flat |
| gym5 | Koga | 27x24 | **61x61** | y114, spread 3 | flat |
| gym7 | Blaine | 23x27 | **89x89** | y106, spread 4 | open, flat |

89x89 is what the terrain and the neighbours allow, not a target. A gym
that size would dwarf its town; the number is there so a designer knows
what the limit is not.

**Surge's site cannot grow.** His building has to step down the slope.
That is a different building, not a smaller one.

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
