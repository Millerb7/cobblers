# Overnight run, 2026-09-29 — decisions, cuts and the review list

The owner is asleep and asked for every call to be made and recorded rather than queued. This is that record.
Durable facts move to `docs/STATE.md`; this is the night's log.

## Standing constraints honoured

Staging only, the live world untouched. No destructive step without a verified snapshot. Fail-closed audits. A
refusal ends the attempt. Ground never read from a built world. Commit per unit.

## Decisions taken without the owner

| # | Decision | Why | The alternative, for review |
|---|---|---|---|
| D1 | The pocket-dimension experiment runs **before** the tick measurements | It unblocks the portals, which are a Phase 2 build item and therefore go in the export. The measurements are valuable but not on the export's critical path, and the budget doc already carries predictions | Measurements first; they would have been more complete with the server quiet, but a cut there costs nothing that ships |
| D2 | **The arrival-in-water question is closed, not tested** | The owner's reasoning, recorded so nobody reopens it: portals are right-click interactions, so the player is already dismounted when they cross. The recall-on-crossing collision cannot arise, because there is nothing mounted to recall | If a portal is ever made to trigger by walking into it, this reopens immediately and the collision is live again |
| D4 | **The Viltri Ravine is cut from the export**, and this is a conflict the owner should see | Tonight's instruction lists "the ravine bed paint" as part of the approved export. But `data/water_shape.json` records the ravine as **ON HOLD** -- "the owner, 2026-09-27: 'hold ... until I decide'" -- and "Nothing is shaped in the ravine". The shaping does not exist, so this is not a paint job; shaping a ravine unsupervised would be inventing terrain the owner held back deliberately | Shape it to the held option B (an underfit stream down the sea half) and paint that. Everything else in the export is unaffected, so this can be added later without a re-export |
| D5 | **The export is GO** | Its real cost is ~35 min of steps plus 10-60 min of Distant Horizons pregen, from `REEXPORT.md`'s own measured column -- not the multi-hour operation I had assumed from EXP-026 run 5, which was long because it debugged an out-of-memory. That fits tonight with room, so the protected item is safe | Skipping the export and re-applying new content onto the existing `cobblers-dryrun11`. Safer still, but it would leave the water shape unapplied, which is the thing the owner approved |
| D3 | The Phase 1b measurements are **limited by having no player** | Cobblemon spawning, the ambient workers and the water ladder are all player-gated; with nobody online their cost is structurally zero. Entity costs (`T`, `V`) can still be swept under forceload, and those are the two numbers that decide the ceiling | Everything player-gated waits for the owner or a second account |

## Cuts

(Filled in as they happen.)

## Review list for the owner

(Filled in as they happen.)
