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

| What | Why | State |
|---|---|---|
| **The Viltri Ravine** | Held by the owner on 2026-09-27 and never in the audited water design (audit check G1 proves it untouched). Tonight's list called for "the ravine bed paint"; there is no shape to paint | Unchanged, still held. Addable later without a re-export |
| **`build_routes` not re-run** | Audit C2 proves no road corridor changed (0 columns, 4 blocks either side of every route line), and STATE records that `routes.json` was hand-adjusted after routing so a re-route does not reproduce it | Routes untouched, deliberately |
| **The employed-villager sweep** | The floor (unemployed, no POI) was measured at ~20 us; the with-beds-and-job-sites sweep was not run | `V` known for the floor only |
| **`T`, the rctmod trainer cost** | `rctmod:trainer` cannot be plain-`summon`ed; the sweep counted 0 present and stopped rather than report a number from an empty pen | Still the one unmeasured number in the budget |
| **Both two-player measurements** | Blocked on the second account, as recorded before the night began. Not faked | Waiting on the owner |
| **Everything player-gated in EXP-047** | Spawning, habitat-pool resolution and the Cobblemon callbacks are player-driven; with nobody online they are structurally unobservable | Recorded as untested, not assumed |

## A near-miss worth recording

The export writes no log until it finishes, and `tasklist | grep java` found nothing, so I read an
in-progress export as a dead one and ran `rm -rf` on its output directory. **The operating system refused
it** -- "Device or resource busy" on the files WorldPainter still held open -- and a region count taken 45
seconds apart then showed it advancing 12 -> 39. Nothing was lost.

Two lessons, both cheap: **absence of a log is not evidence of death** for a tool that buffers, and a
progress check (does the output grow?) costs 45 seconds and would have prevented the attempt entirely. I
should have measured before deleting rather than after being refused.

## Review list for the owner

1. **`jungle_ruins` is now at or below sea level.** It measured y119-134 and now measures **y55-61**: it stood on the
   Jungle Isle, which the water shape removes by design. This is `WATER_SHAPE.md` 15.4's known consequence, but it is
   not fixed — the ruins need re-siting or removing, and until then they are drowned.
2. **The gorge hamlet's canopy claim flipped back to visible** at 1 of 129 points (0.8%, fragile). Its own record
   predicted this would happen when the export repainted the canopy. You may prefer to clear or plant the single line
   rather than keep a claim that flips with the paint.
3. **`derived/rift_sculpt/plan.json` was repinned** to the new heightmap sha rather than regenerated, because
   `rift_heightmap.py --plan` only describes an applied sculpt and refuses the water heightmap. Sound because audit C5
   measured 0 Rift columns changed, but it is a pin I moved by hand and you should know it moved.
4. **The water ladder's early exit changed behaviour on land.** Vanilla air removal on dry land now runs from a new
   `minecraft:effects_changed` advancement instead of two `effect clear` commands every tick. The wet path still
   clears unconditionally, so the rule cannot break in water, but the **land** clear is unverified in game.
5. **The trainer hold-off interim is live.** A player who has beaten a trainer is protected from a forced rematch; the
   partner who has not may have to start the fight by interacting. Reversible, and the proper per-player fix is still
   gated on EXP-034.

(Filled in as they happen.)

## The legendaries: six built, four blocked, and six things that need you

`data/legendaries.json`, `tools/legendaries.py`, `tools/legendaries_audit.py`, `docs/mechanics/LEGENDARIES.md`.
Audit **376 checks, 0 failures**, and proved fail-closed against six tampered inputs (gate stripped from a line, a
write moved outside the shell, an empty pack, no pack, every record blocked, a level above the catch cap). I re-ran
it here myself rather than take the agent's word: same result.

**Emitted:** Mesprit (Arrow, 3 badges), Azelf (Marshy Marsh, 5), Regirock, Regice, Regigigas, Groudon.
**Blocked, each with a named reason rather than a guess:** Uxie, Registeel, Lugia, Celebi's wake.

1. **Five gates are the agent's proposal, not your decision.** Only the lake trio's badges and Lugia's Dive +
   `champion_cleared` are yours on record. Regirock gym 4, Regice gym 6, Registeel gym 7, Regigigas gym 8 (plus all
   three golems met), Groudon gym 8 and Celebi gym 8 are **guesses** and marked as such. They want your call.
2. **Uxie needs one line from you.** Lake Tilpey is the only trio lake with no keep zone in `data/water_shape.json`;
   Arrow and Marshy Marsh both have one protecting exactly these mouths. Adding
   `{"id": "uxie_grotto_floor", "radius": 12, "around": <mouth>}` to Tilpey's `keep` unblocks it with nothing else
   changed. I did not edit that file: the water shape was mid-apply.
3. **A new Celebi fault, found while building.** `cobblers_celebi`'s keeper re-merges the dormant NBT **every 40
   ticks** while a player is within 48 blocks, so any wake that only flips flags is undone within two seconds. The
   keeper has to learn the woken state before a wake can work at all. That is independent of which trigger you pick.
4. **The advancement trigger for the wake burns.** An advancement fires once per player for ever and its criteria
   cannot test another advancement, so a player who tries the right item *before* the gate opens can never wake it.
   EXP-023's candidate mechanism is therefore unsound as stated. The gate is built and correct; nothing calls it.
5. **Celebi is level 70 and above every provisional cap**, and `cobblers_levelcap` blocks an over-cap catch outright,
   Master Ball included. As it stands Celebi cannot be caught. The per-badge caps have not been read out of the
   Cobbleverse RCT data; the numbers in the file are a placeholder for a balance pass.
6. **The chambers are shared, not per player.** Entity NBT is world state: one qualified player opens a grotto for
   everyone in it, and the first catch takes the legendary for the server. Per player would need the scene runtime
   and EXP-034. Also, once open, a woken legendary can be killed with a sword (EXP-023) and the keeper cannot
   re-summon it.

## Routes 1-3's water events are stale, and I did not force them through

`route_events.py` refused to build: its guard compares the current heightmap against the one the routes were routed
on, over the whole Routes 1-3 region, and the water shape changed **68,761 columns** there.

I first suspected the guard was over-broad, because the water audit's check C2 proves **no road corridor changed**
(0 columns within 4 blocks of every route line). So I measured what actually matters instead of arguing: **6 of the
40 scene props now stand on ground the export moved** — `route1_first_cast`, both `route2_viltri_sounding` props and
all three `route3_creek_wooper` props. Every one of them is a **water** event, sitting on exactly the features the
water shape re-cut. *(My parallel check of the route path points themselves found 0 points to check — my reader did
not match `route_paths.json`'s shape — so that half is inconclusive, not clean. C2 is the evidence that the roads
are fine, not my script.)*

**So the guard is right and I left it alone.** `route_events.py --write-scenes` would re-site the props, but it runs
*after* the guard, and defeating a fail-closed guard to reach the fixer is the exact move the standing constraints
forbid. Rewriting `scenes.json` wholesale also risks overwriting hand-authored anchors and dialogue positions, which
is not a call to make while you are asleep.

**Consequence, stated plainly:** the rest of the build carried on from the next job, so the new world gets everything
else, and **Routes 1-3 keep their previous event positions**. Six water props will sit on ground that has moved —
First Cast on the old coastline, the Viltri sounding and the creek Wooper on the old water. They will look wrong
until re-sited.

**The fix, for a session with you awake:** run `python tools/route_events.py --source-root <root> --write-scenes`
once the guard is satisfied, then diff `data/scenes.json` and check the change is confined to those six positions.
It is a morning's work, not a night's.

## THE ONE THING TO READ FIRST: the new world has no players carried

`reapply.py carry` **refused**, correctly, and then my attempt to clear the blocker was **refused by the
permission system**. Both refusals stand; I did not route around either.

**What the carry found.** Your player in `cobblers-dryrun11` holds `cobblers:flag/gym5_cleared` (granted
2026-09-27 11:36) and `cobblers:flag/gym6_cleared` (2026-09-27 21:51), but **rctmod has no win for either**
— neither its series progress nor its trainer memory. The carry cross-checks badges against rctmod and
fails closed when they disagree, which is exactly the guard working: it will not copy a progression state
it cannot vouch for. Koga and Sabrina were almost certainly flag-granted during testing rather than beaten.

**What I tried, and what stopped me.** The honest resolution is to revoke the two flags, because nothing
backs them — granting rctmod wins instead would fabricate victories. I backed up your advancements file
and went to remove those two entries. **The permission classifier refused it as irreversible local
destruction.** A refusal ends the attempt, so that line of work stopped there and I did not attempt it by
any other route.

**Consequence:** `cobblers-dryrun12` is built and everything else is applied to it, but **no player data was
carried**. Your party, items, position and badges are still in `cobblers-dryrun11` and untouched.

**To fix it, in about a minute, with you awake.** Either:
- boot `cobblers-dryrun11`, run `advancement revoke <you> only cobblers:flag/gym5_cleared` and the same for
  `gym6_cleared`, stop, then run the carry; or
- if you *did* mean to have those badges, grant the matching rctmod progress instead and carry.

Then: `python tools/reapply.py carry --rehearsal --old-world <dryrun11> --world-dir <dryrun12>`.

**Housekeeping:** I left `advancements/<your-uuid>.json.pre-revoke-backup` in `cobblers-dryrun11`. It is an
untouched copy made before the refused edit; delete it whenever.
