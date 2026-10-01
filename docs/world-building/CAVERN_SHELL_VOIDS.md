# The twelve voids in the Displaced City's cavern shell

Measured 2026-09-30. The data is `data/cavern_shell_voids.json`; the checker is
`tools/build_audit.py` (`void_reach`); the builder is `tools/cavern_plan.py`.

## The question, and why counting could not answer it

The Displaced City sits in a chamber at `x3250..3449, z1650..1849`, 60 to 100 blocks under the
trough flank. It is a *sealed* city: the only way in is the tunnel. `02_shell` exists to keep it
that way — it turns every void within 24 blocks of the chamber into rock, over the roof and in a
24-block ring round the walls, because the first cut of this cavern had two real back doors: a
surface-open cave four blocks over the west rim at `x3252-3261, z1745`, and water pockets running
down the west wall at `x3249`.

`tools/build_audit.py --only cavern` measured 0 shell voids on the staging export
`cobblers-dryrun4`. On `cobblers-dryrun12` it measured 12, reported as
`shell_voids: {"in the walls, air": 12}` and nothing more. That number was noticed only because
someone compared two reports by eye, and even once noticed it could not be acted on: a void
"in the walls" might be a sealed pocket of air in the rock or a chain of open cells reaching
daylight, and the audit said the same thing about both.

## What the twelve are

Seven pockets, 96 open cells, **all twelve void columns in the single row `z=1850`** — one block
south of the chamber's south wall — each running eight blocks up from the cavern floor:

| seed | columns | cells | bounding box | touches |
|---|---|---|---|---|
| 3266 28 1850 | 3266, 3267 | 16 | 3266 28 1850 → 3267 35 1850 | the chamber at 3266 28 1849 |
| 3269 28 1850 | 3269 | 8 | 3269 28 1850 → 3269 35 1850 | the chamber at 3269 28 1849 |
| 3286 23 1850 | 3286 | 8 | 3286 23 1850 → 3286 30 1850 | the chamber at 3286 23 1849 |
| 3289 23 1850 | 3289, 3290 | 16 | 3289 23 1850 → 3290 30 1850 | the chamber at 3289 23 1849 |
| 3331 28 1850 | 3331 | 8 | 3331 28 1850 → 3331 35 1850 | the chamber at 3331 28 1849 |
| 3390 24 1850 | 3390, 3391, 3392 | 24 | 3390 24 1850 → 3392 31 1850 | the chamber at 3390 24 1849 |
| 3394 24 1850 | 3394, 3395 | 16 | 3394 24 1850 → 3395 31 1850 | the chamber at 3394 24 1849 |

**Every one is an alcove in the chamber's own wall.** None reaches the surface, none holds or
touches water or lava, none joins another pocket, none leaves the search box (the shell's ring plus
24 blocks). A player standing in the city can step one block into the wall at seven places;
nobody outside the city can reach them. **There is no back door, and the city is still sealed.**

The one thing to keep in mind about that result: it is measured on `cobblers-dryrun12` only, and the
floods are bounded. "No back door" means "no chain of open cells out of these seven pockets inside
the searched volume", not "the cavern is sealed everywhere" — the roof cap, the seal and the floor
checks are what cover the rest, and they are clean on the same world.

## Why they are there

Not a later build re-opening them. Every `fill` and `setblock` in the cavern pack, the town's prep
function and the town's placement commands was tested against `(3266, 30, 1850)`, and the only one
that covers it is `02_shell`'s own
`fill 3266 18 1850 3340 100 1850 minecraft:stone replace #cobblers:cavern_void`. No generated
cavern command names `z=1850` at all except the shell's. The columns are not ones the town rebuilds
(the audit already skips those). The tag loaded (a tag that had not would have left voids in all
60,992 shell columns). The widest fill in that row is 6,225 blocks, well under the limit, and
`tools/function_limits.py` reports 0 problems over the pack.

What is left is the shell's blind spot: **it runs once, before the excavation, and a
`replace #<tag>` fill skips any block the tag does not name.** The best account of seven thin,
eight-block-tall pockets hanging in the rock, every one of them against the carve, is that they held
natural cave decoration — a dripstone spike, hanging roots, a glow lichen, a cave vine — which the
tag did not name, which the shell therefore left alone, and which broke to air when the excavation
took away the wall it was hanging on, after the only pass that would have filled it. `dryrun4`
measured 0 because it was a different export with cave decoration in different places.

**That is a hypothesis, not a measurement.** The pre-carve world is gone and the blocks are air now,
so it cannot be confirmed without a fresh export. The fix does not depend on it being right.

## What changed

- `tools/build_audit.py` — `void_reach`. Each shell void is flooded, 6-connected, through air and
  fluid. The chamber's interior is a *terminal*, not something to expand through: the city is
  200 × 200 × 50 of deliberate open space, and expanding into it would flood the whole cavern and
  say nothing. Each pocket is then classified, and the audit **exits non-zero** on:
  - a pocket that reaches the surface (a clear column of non-solid blocks to y319);
  - a pocket holding or touching water or lava (the west wall's old pockets were a back door and a
    flood path both);
  - a pocket the flood cannot bound — it left the search box, or passed `VOID_CAP` = 20,000 cells;
  - more than `VOID_MAX_POCKETS` = 64 separate pockets;
  - more than 0.5% of shell columns holding a void (`SHELL_VOID_OK`), however harmless each is —
    a shell pass that never ran would otherwise leave thousands of innocent-looking alcoves.

  An alcove open only into the chamber, and a pocket shut in the rock, are **notes** carrying their
  coordinates, their cell count and their bounding box. The old unconditional "N columns with a
  void" problem is now one of those notes.
- `tools/cavern_plan.py` — `#cobblers:cavern_void` widened from 8 blocks to 27, adding the
  support-dependent cave decoration; and a second pass, **`25_reshell`**, the same 5,367 fills run
  again *after* the carve. Safe by construction: inside the box the shell starts at the ceiling and
  the excavation stops at `ceiling-2`, so a reshell can never eat the chamber; outside the box it is
  all sealed rock.

## What this does not do

Nothing here has touched a world. The twelve are still in `cobblers-dryrun12`, and `25_reshell` has
never been run anywhere. To close them:

1. **`tools/reapply.py` needs `"25_reshell"` added to `CAVERN`, immediately after `"20_surfaces"`.**
   It must come after the carve and **before `"50_tunnel"`**, which is dug through the shell. That
   edit was out of scope for the session that found this and has not been made.
2. Re-run the cavern steps (R2) and re-audit with `tools/build_audit.py --only cavern`, which should
   then report 0 void columns and no notes.

## What a test should assert

`void_reach` is a checker, not a test, and it has no test of its own. A test author should build
small synthetic worlds (a `block(x, y, z)` stub is enough — the function takes a world object, a
void list, a search box, a cavern box and the floor/ceiling grids) and assert:

- an isolated pocket in solid rock → 0 problems, verdict "isolated";
- a pocket whose only open neighbour is a chamber cell → 0 problems, verdict "alcove", and the
  chamber contact's coordinates in the record;
- a pocket with a clear column of air above it to y319 → exactly 1 problem naming "the surface";
- a water-filled pocket, otherwise sealed → 1 problem naming the fluid;
- a pocket whose open cells run off the search box → 1 problem naming it unbounded;
- a pocket of more than `VOID_CAP` cells → 1 problem, and the flood terminating rather than hanging;
- a pocket touching both the chamber and the surface → 1 problem naming both (the real back door);
- two voids in the same pocket → one record, not two (the pass must not re-flood a visited pocket);
- `shell_voids` over `SHELL_VOID_OK` of `shell_columns`, all of them harmless alcoves → still a
  problem, so a shell pass that never ran cannot pass;
- a world with no voids at all → no notes, no problems, and `shell_pockets` empty.

These were checked by hand against synthetic worlds while the function was written (isolated,
alcove, surface shaft, fluid, unbounded, and a chamber-plus-surface back door all behaved as above);
none of it is a committed test.
