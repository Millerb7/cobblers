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

## Limitations
- A staging export, not the live world. The live run adds retiring the world and its datapack list.
- Not in the driver and not run: Habitat Blocks (0 recorded), `waystones.dat` (a fresh export has none), spawn pools
  and suppression (none are in the live world; installing them is a separate decision), Distant Horizons pregen.
- Everything here is a command or a chunk read. No player walked it.
- The accidental boots: two boots of a mistyped universe generated two vanilla worlds, moved aside unread to
  `cobblers-runtime-proof/_accidental-generated-world-2026-09-21{,-b}`. They can be deleted.
- Implementation, tests and this verdict are the same session's.

## Decision
The re-application is ready to run on the live world with `tools/reapply.py`, as written in
`docs/world-building/REEXPORT.md`. The live run is the owner's to start.
