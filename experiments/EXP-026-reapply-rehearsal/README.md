# EXP-026: The whole re-application, rehearsed on a fresh export with result checks

## Objective
EXP-024 showed the re-application commands run on a staging export, but most of its checks were command checks
(see its correction). Before the live re-export, run the entire sequence the way the live run will be run, by one
driver (`tools/reapply.py`), on a fresh export, and judge it only by result checks.

## Success criteria
- A fresh staging export from the canonical heightmap, seed carried, 484 regions.
- Every step R2-R14 runs from `tools/reapply.py run` without a stop, on that export.
- Every place's floor verify reports 0 gaps and the trader verify passes, with the server running.
- `tools/reapply.py audit` on the stopped world reports clean: `build_audit` (cavern, forest, world tree, islet) and
  `town_audit` for every planned place.

## Dependencies
WorldPainter 2.27.1 headless, the canonical heightmap (`5b963567…`, the three pads pressed), `cobblers-10240.world`,
the paint manifest, the offline snapshot `2026-09-17-pre-grass` for the seed (never the live world), the installed
packs for donor templates. Cobblemon 1.8.0 on MC 1.21.1, `-Xms4G -Xmx10G`, under the coordination lock.

## Runs

### Run 1: `cobblers-dryrun2` (2026-09-21)
Export 14 minutes, 484 regions, `seed_match: true`. `prepare` 260 s, 216 functions, 0 refused.

| Step | Result |
| --- | --- |
| R2 | 8 s |
| R3 | **stopped by its checkpoint**: the crown test ran in a chunk the tree's functions had released. The crown was there. The check now holds the chunk and waits for it |
| R4-R14 | ran; 23 places, 32 donors |
| V | 3 verifies failed with `WinError 10048` (one RCON connection per block test ran Windows out of client ports); one earlier stale verify file was read as 9 gaps. The verify now batches its tests and the driver never reads an old file |
| audit | **not clean**, see below |

What the audit found, all of it invisible on the disposable world, where the ground restore had cleared everything:
- **Trees and flowers on streets** (Giovanni's, the gorge hamlet, the Rift rim, Sunset West): the prep never cleared
  above a street. Every street and square now gets 3 blocks of headroom and its trees cleared (`tools/town_plan.py`).
- **Gravel falling from the cavern roof**: 347 roof-cap columns open and 75 lumps on the Displaced City's streets.
  The seal now turns gravel and sand in the cavern's shell to stone (`tools/cavern_plan.py` `00_seal`).
- **The audit's own blind spots**: the cavern floor and the islet core are built on later (81% and 97%), and four
  plazas stand in a landscape painted in their own stone. `build_audit` now leaves out the columns a later town
  rebuilds and says how many; the stray-paving check compares with a control ring and says "not checkable" where the
  landscape is mostly the plaza's material.

### Run 2: `cobblers-dryrun3` (2026-09-21), after the fixes
Export 14 minutes, 484 regions, `seed_match: true`. `prepare` 244 s, 216 functions, 0 refused; boot 28 s.

| Step | Time | Result |
| --- | --- | --- |
| R2 cavern | 7 s | ran |
| R3 world tree | 4 s | crown present |
| R4 grove, R5 elders, R6 forest | 20 s | ran |
| R10 islet | 0 s | ran (before the towns) |
| R7 hometown | 1 s | ran |
| R8 23 places | 14 s | ran, including Surge's town and the Scar on their pads |
| R9 32 donors | 98 s | ran |
| R14 traders | 16 s | ran |
| V verify | 116 s | **24 of 24 places 0 gaps**; trader verify passed |
| audit | 128 s | **clean** |

The audit, in full: cavern roof cap 40,000 of 40,000, floor 26,647 of the 26,650 columns the town does not rebuild
(13,350 rebuilt), open interior 26,650; forest 46,051 of 46,052 trunks (the one under a lantern post's fence);
world tree 1,380 of 1,380 and the crown at (2044, 535, 2282); islet 2,139 of 2,139; all 23 places plan-clean with no
unpolicied spawn block. Stray paving was not checkable at Erika's town (moss 40% of the landscape), the Merian hut
(cobblestone 78%), the Tableland stop (red terracotta 48%) and the dig camp (gravel 87%). Run and audit records:
`derived/reapply/run_20260921_130109.json`, `derived/reapply/audit_20260921_130836.json` (gitignored).

### Run 3: `cobblers-dryrun4` (2026-09-21), after the lights, fields, titles, the cavern shell and the Codex review
Export 14 minutes, 484 regions, `seed_match: true`, seed from the offline snapshot `2026-09-17-pre-grass`.
`prepare` 180 s, 332 functions, 0 refused; boot 30 s, 43 error lines, none from our packs (all Cobbleverse's own:
raid-den loot tables, two Cobblemon advancements).

Codex's review found four fail-open defects in the re-export path (the lock; audits passing on empty output; "not
checkable" counted clean; the ground-rule detector). The owner stopped the run on this export until they were fixed.
They were, with a sweep of every other verify (`tests/test_reapply_lock.py`, `test_audits_fail_closed.py`,
`test_town_audit_fail_closed.py`, `test_verifies_fail_closed.py`, `test_ground_rule.py`); then the run went ahead
on the same export, under the lock with its owner declared (`COBBLERS_LOCK_OWNER`).

| Step | Time | Result |
| --- | --- | --- |
| R2 cavern (now with `02_shell`) | 6 s | ran |
| R3-R6, R10, R7 | 19 s | ran |
| R8 24 places | 11 s | ran |
| R9 32 donors | 98 s | ran |
| R16 lights and the fields' crops, after the donors | 1 s | ran |
| R15 signposts, now after the donors | 1 s | ran |
| R14 traders | 16 s | ran |
| V verify | 116 s | **25 of 25 places 0 gaps, 0 unverified**; trader verify passed |

The first audit, failing closed, was not clean, and each finding was real: the department store (a donor placed
whole) had erased the Route 7 post at Sabrina's town, since the signs went in first (R15 now follows R9); the fields
were compared earthwork by earthwork instead of by final state (88.8%); the light model counted positions under house
floors that carry foundations, and the light check skipped snow-covered positions. Fixed, and the whole driver run
again on the same export (272 s, no stop, every verify clean).

The second audit (`derived/reapply/audit_20260921_182200.json`):

| Check | Result |
| --- | --- |
| cavern | roof cap 40,000 of 40,000; floor 26,175 of 26,178; **shell 60,992 columns, 0 voids** within 24 blocks of the chamber |
| forest | 46,043 of 46,052 planned trunks (99.98%); the plan's count, plus the sapling |
| world tree | 1,380 of 1,380, crown at (2044, 535, 2282), the plan's y535 |
| islet | 2,139 of 2,139 |
| towns | 24 of 24 plan-clean: paving checked cell by cell against the plan (no heuristic, nothing "not checkable"), every building the data records checked |
| signposts | 51 of 51 |
| light check | **fails**: 67 positions at Surge's town and 14 at Northlight, all in snow-layer cells, store block light 0 while the air directly above reads 10-11 and the lanterns stand lit. The model has no snow. Every other place 0 |
| MobsBeGone | `/summon` of zombie, skeleton, creeper, spider, enderman and witch each answer "Summoned" and none exists; the control armor stand does |

**Result: not clean, on the light check alone.** Everything else passes.

### Run 4: `cobblers-dryrun10` (2026-09-24), a fresh export from main `55e7505`, then the playtest

The full driver ran on a fresh staging export (`--no-reload`, one boot), then `audit` on a stopped copy. Two
operational stops on the way:

- The server's 60 s watchdog killed it at R5, on forceloads waiting behind the Rift's lighting backlog. The run
  completed with `max-tick-time=-1`, restored afterwards.
- V failed with WinError 10048: R17's hundreds of one-connection RCON calls exhausted the ephemeral ports. V ran clean
  after the ports drained: 26 of 26 places, 0 gaps.

| Check | Result |
| --- | --- |
| Victory Road caves | 1,936,430 of 1,936,430 |
| the Deep | clean |
| route events | 2,237 blocks, 0 problems |
| signposts | 50 of 50 |
| habitat blocks | 81 of 81 after a restart |
| forest | 46,006 of 46,015 |
| world tree, cavern, mansion, old mine | clean |
| towns | clean except `league` and `rift_rim_stop` |
| rift skin | entities **0 of 14**; 13 cell mismatches |
| League lot | "lot clear" 28 of 48 |
| islet | 2,404 of 2,628 columns |

**Defects found, all fixed on 2026-09-25 and checked offline against a copy of the audited world. None has been
re-run on a rebuilt world.**

- **Rift entities 0 of 14:** `rift/fx` was never run by any step. R1 now runs it and waits for all 14 to register.
- **League forecourt:** R8B's lot skirt repaved 211 forecourt cells in blackstone, and erased the forecourt waystone's
  upper half. The lot now leaves the town's forecourt rects alone (`data/rift_league_tunnel.json`
  `lot.leave_to_the_town`), and the waystone is seated on the anchor level.
- **Rim overlook:** paved anchors were never cleared above, unlike streets. `tools/town_plan.py` now clears over them.
- **Watchdog:** `reapply.py run` refuses unless `max-tick-time=-1`, and REEXPORT.md has the set and restore steps
  (5b, 8a).
- **RCON:** the driver keeps one connection and reconnects when the server drops it (302 commands, 1 connection,
  against a fake server).
- **False alarms:**
  - The rift skin verify excludes the 13 cells later steps own.
  - "Lot clear" excludes the League building's volume.
  - The islet replay honours `replace` filters: 2,628 of 2,628.
- **Runbook:** it named the old heightmap.

The owner then played it: EXP-035.

### Run 5: `cobblers-dryrun11` (2026-09-25), a fresh export with the marsh and jungle foliage

A fresh WorldPainter export from `world/playtest-3`:
- **Export:** 836 s, 484 regions, `seed_match: true`, with the new foliage overlays painted.
- **Prepare:** 560 s, 25 places, 23 steps, 2,759 functions with 0 problems.
- **Carry and install:** the owner's player carried with `--rehearsal`; install put the spawns and suppression world-local.
- **Driver:** run with the watchdog off (the new preflight).

**Stopped at R17: the 10 GB heap ran out of memory** and the server hung. It was the first full run with the spawn
suppression installed (about 3.8 GB of heap on its own). Restarted at 16 GB and resumed `--from R17`: R17 in 262 s on
one RCON connection (no port exhaustion), R14, R14C (one Celebi), V 26 of 26 places at 0 gaps, traders clean.

The audit of a stopped copy then found the steps done between the last autosave and the crash missing from the world:
- 2 of 50 signposts;
- the thirsty stranger's hut (R12);
- lamps in three towns (R16).

The run had reported each of those steps done. Re-running R9F, R16, R15 and R12 restored them: 50 of 50 signposts,
2,237 of 2,237 route-event blocks, and gym2, gym3 and the mining town plan-clean.

| Check | Result |
| --- | --- |
| rift skin | clean: 1,966 of 1,966, entities 14 of 14, 13 samples left to the later steps that own them |
| the Deep | clean |
| League lot and tunnel | clean: lot clear 63 of 63, surface 44 of 44 |
| Victory Road caves | 1,936,430 of 1,936,430 |
| islet | 2,628 of 2,628 columns, 10,785 of 10,785 blocks |
| world tree | 1,380 of 1,380 |
| forest | 46,006 of 46,015 |
| towns | 25 of 25 plan-clean and spawn-clean (after the re-run) |
| Habitat Blocks | 81 of 81 |
| lights (report only) | snow and a few cells in 8 places, as before; the Displaced City 295 |

**Fixes from run 5:**
- `reapply.py run` saves after every step, so a crash loses at most one step.
- The drop rules always come back on, never "as found".
- REEXPORT step 6 boots at 16 GB.

Run 4's fixes all held on a rebuilt world: the Rift fx step, the forecourt, the rim overlook, the verify exclusions,
the islet replay and the single RCON connection.

## Limitations
- A staging export, not the live world. The live run adds retiring the world and its datapack list.
- Not in the driver and not run: Habitat Blocks (0 recorded), `waystones.dat` (a fresh export has none), spawn pools
  and suppression (none are in the live world; installing them is a separate decision), Distant Horizons pregen.
- Everything here is a command or a chunk read. No player walked it.
- The accidental boots: two boots of a mistyped universe generated two vanilla worlds, moved aside unread to
  `cobblers-runtime-proof/_accidental-generated-world-2026-09-21{,-b}`. They can be deleted.
- Implementation, tests and this verdict are the same session's.

## Decision
Run 2's decision ("ready") is withdrawn: its clean audit rested on checks that passed when they had nothing to check.
After run 4 (2026-09-25): not ready until a fifth fresh rehearsal runs the fixed driver clean end to end, with the
watchdog off and the spawn packs installed by `install`; the owner-supervised live run follows that.
After run 3 the re-application was not yet ready for the live world. It waits on (1) Codex's re-review of the fixes,
and (2) the owner's call on the light check's 81 snow-layer positions, which have no gameplay effect since vanilla
hostiles cannot spawn in this pack. The live run is the owner's to start once both are done.
