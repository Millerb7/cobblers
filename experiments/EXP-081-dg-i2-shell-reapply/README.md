# EXP-081: I2, the time and block count of one slot's shell re-apply

**Status: designed 2026-10-08, NOT_EXECUTED.** Probe I2 (new) of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only. Entirely over RCON.

## Objective
Each slot is a persistent shell placed by a re-apply step (DUNGEONS.md 1 and 11.3): fills of at most 32,768 blocks,
forceloads of at most 256 chunks per add, "a 2,048 x 64 strip is about 512 chunks, so two batches". The shell's
block count is the builder's to report; the step's run time is I2. I2 times a stand-in shell on one slot-sized strip:
a bedrock hull with its interior cleared, on fresh ground, on an intact shell, and after a dressed interior.

## Success criteria
Three timed runs of `i2/shell`, each one RCON call, with the block counts the server reports:
- fresh ground: **456,264** (the hull: 2,048 x 64 x 48 = 6,291,456 less the interior 2,046 x 62 x 46 = 5,835,192;
  the interior is already air);
- intact: **0**;
- after `i2/dirty` (730,112 stone: the first 256 blocks of the interior): **730,112**.
And the server stays up (no watchdog stop) and catches up after each.

## Dependencies
Vanilla `fill`, `forceload`, `execute store`; `cobblers:pocket`.

## Implementation
`cobblers_dg_probes:i2/*`; objective `dpi2.r`. The strip x 1024..3071, z -960..-897, y 72..119 (its own row, inside the
border margin, disjoint from every other probe, the rescue box, Entei's band and the dungeon rows).
- `shell`: `forceload add` twice (256 chunks each: x 1024..3071 by z -960..-929 and -928..-897), the hull (floor,
  ceiling, two long walls, two ends) and the interior cleared, each fill under 32,768 and its count added into `#n`;
  then the forceloads released (a re-apply step holds nothing after). 200 fills. Returns `#n`.
- `dirty`: stone over x 1025..1280 of the interior, the dressing stand-in. Returns its count.
- `clear` (and `cleanup`): the whole strip back to air.

## Test instructions
### (a) RCON, no player (all of it)
Time each call from send to reply (the function runs inside the command, so the reply comes when it is done). Run
`tick query` before and after each to see the tick-time spike.

| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:i2/shell` (fresh: the 512 chunks are generated on this call) | `returned 456264`; record the seconds | another count: the ground was not empty, or a fill was refused (check `logs/latest.log`) |
| 2 | `function cobblers_dg_probes:i2/shell` again (chunks load from disk) | `returned 0`; record the seconds | |
| 3 | `function cobblers_dg_probes:i2/dirty` | `returned 730112`; record the seconds | |
| 4 | `function cobblers_dg_probes:i2/shell` | `returned 730112`; record the seconds (the clear of a dressed interior) | |
| 5 | `function cobblers_dg_probes:i2/cleanup` | `returned 1`; record the seconds | |
| 6 | `forceload query` in the pocket: `execute in cobblers:pocket run forceload query` | none of x 1024..3071, z -960..-897 listed | some held: a release failed |

No owner step.

## Results
NOT_EXECUTED.

## Limitations
- The real shell's dressing (walls, stands, lake, parkour, displays) is not built; the dirty pass is a stand-in for
  "a dressed interior", and its 730,112 is one point, not a curve.
- Staging hardware and load, one run each. A run long enough to approach `max-tick-time` (60 s by default) would stop
  the server: if run 1 takes more than 20 s, stop and split the step before going on.

## Decision
Feeds the re-apply budget (11.3): if one slot's shell is under a few seconds, the four slots run as one step each; if
it is longer, the step is split per batch (two forceload adds, each its own function call) so no single call holds the
tick past a few seconds.

## Follow-up
The real shell's block count, once `tools/dungeon.py` generates one.
