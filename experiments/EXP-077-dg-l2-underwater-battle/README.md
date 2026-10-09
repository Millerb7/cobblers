# EXP-077: L2, does a wild battle start and finish underwater, with and without Dive?

**Status: designed 2026-10-08, NOT_EXECUTED.** Probe L2 of `docs/mechanics/DUNGEONS.md` section 14, pack
`cobblers_dg_probes`, staging only.

## Objective
The band-6 lake legendary is battled on the bed of a flooded shaft (3.7). That a Cobblemon battle starts and runs with
the wild Pokemon and the player under water is ASSUMED (L2). The fallback is a dry chamber. L2 settles three cases:
the player's head above water with the wild submerged; the player submerged in shallow water (vanilla air only); and
the player deep (the water ladder's deep rule) with Dive.

## Success criteria
For each case: the battle opens, both sides' Pokemon appear, it runs to a KO, the wild one is gone after
(`execute ... if entity` fails), and `q.player.in_battle` read 1 during it. Anything odd (camera, send-out failing,
drowning during the battle, the battle ending early) is recorded.

## Dependencies
Cobblemon 1.8.0 battles and `spawnpokemonat`; the blackout's water ladder (`data/blackout.json` `water.deep_blocks` 5:
eyes 5 or more under is "deep"; the ladder strips water breathing from anyone unqualified).

## Implementation
`cobblers_dg_probes:l2/*`; objectives `dpl2.st`, `dpl2.r`. Area x 3072..3327; a pen at (3104, 96, -640).
- Shallow basin: water x 3092..3101, z -643..-637, surface y 99. A 1-deep shelf at x 3092..3094 (head above water);
  the rest 4 deep (eyes about 2.4 under: vanilla air, under the ladder's 5).
- Deep basin: water x 3107..3113, z -643..-637, y 90..99, 10 deep (eyes about 8.4 under: the ladder's deep rule).
- `wild_shallow`, `wild_deep`: `tentacool level=5` by macro at (3098.5, 96, -639.5) and (3110.5, 90, -639.5), tagged,
  persistent, and carrying the blackout's `claims.exempt_tag` (`data/blackout.json`), so a loss takes no items.
- `to_shallow`, `to_deep` (as the owner): onto the shelf, or onto the deep basin's west rim at y 100, facing east.

## Test instructions
### (a) RCON, no player
| # | Command | PASS | FAIL |
|---|---|---|---|
| 1 | `function cobblers_dg_probes:l2/setup`; wait 15 s; `function cobblers_dg_probes:l2/wild_shallow`; `function cobblers_dg_probes:l2/wild_deep` | `returned 1` each | 0: the spawn did not land under water |
| 2 | after 60 s: `execute in cobblers:pocket if entity @e[tag=dpl2.ws]`, `... @e[tag=dpl2.wd]` | both `Test passed` (kept: not despawned) | |

### (b) The owner in game (a party of level 5 or more; for case 3 his Dive training and a Dive-capable member)
| # | The owner does | The session runs | PASS |
|---|---|---|---|
| 1 | stands in the overworld | `execute as <owner> at @s run function cobblers_dg_probes:l2/enter`, `execute as <owner> run function cobblers_dg_probes:l2/to_shallow` | on the shelf, head above water |
| 2 | Case 1: starts a battle with the submerged Tentacool from the shelf (sends out at it) | during the battle: `runmolang "return q.player.in_battle;" <owner>` | output 1; battle UI opens; both Pokemon visible |
| 3 | KOs it | `execute in cobblers:pocket if entity @e[tag=dpl2.ws]` | `Test failed` (gone) |
| 4 | | `function cobblers_dg_probes:l2/wild_shallow` | `returned 1` |
| 5 | Case 2: swims down into the 4-deep part (head under), starts the battle there, watches his air bar | the step 2 read | 1; note whether air drains and drowning hurts during the battle |
| 6 | KOs it, surfaces | step 3's test | `Test failed` |
| 7 | Case 3, ONLY if Dive-qualified: `to_deep` | `execute as <owner> run function cobblers_dg_probes:l2/to_deep` | on the rim |
| 8 | dives to the bed with his Dive partner, starts the battle on the bed | `runmolang "return q.player.in_battle;" <owner>` | 1 |
| 9 | KOs it | `execute in cobblers:pocket if entity @e[tag=dpl2.wd]` | `Test failed`; he took no ladder damage |
| 10 | | `execute as <owner> run function cobblers_dg_probes:l2/leave`, `function cobblers_dg_probes:l2/cleanup` | |

If he is not Dive-qualified, case 3 is skipped and recorded as not run: without Dive the deep rule's hits land every
second (`pulse_ticks` 20, half maximum health).

## Results
NOT_EXECUTED.

## Limitations
Case 3 needs the owner's Dive state; a real legendary at level 100 (the 3.7 encounter) is not spawned. A wild loss
here makes no claim (the exempt tag), but still runs the blackout's charge and return.

## Decision
Gates the lake encounter's place (3.7). Case 3 PASS: the battle stays on the bed. Case 1 PASS only: the legendary is
battled from a ledge above the water, not on the bed. No case passes: the fallback, a dry chamber behind the membrane
(the built `lake_grotto` archetype), with the Dive gate kept on the membrane.

## Follow-up
EXP-064 (the Beast Ball key on a tagged boss) for the band-6 catch.
