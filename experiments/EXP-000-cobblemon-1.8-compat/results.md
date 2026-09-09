# EXP-000 results

## Environment

- Date: 2026-09-08 through 2026-09-09
- OS: Windows
- Java: Temurin OpenJDK 21.0.9 LTS
- Minecraft: 1.21.1
- Fabric installer: 1.1.2
- Fabric Loader: 0.19.5 stable
- Fabric API: 0.116.14+1.21.1
- Cobblemon target: 1.8.0
- Test runtime: `runtime/server/` (gitignored)

## Preparation results

| Check | Result | Evidence |
| --- | --- | --- |
| reference pack unchanged | PASS | 104 planned server jars match recorded hashes; zero mismatch/missing |
| replacement acquisition | PASS | 13 Modrinth files downloaded and SHA-512 verified by `pack_manifest.py` |
| target assembly | PASS | 101 planned jars; zero missing, mismatch, extra, or unverified |
| client plan | PASS | 135 planned jars plus 47 resource packs, 10 datapacks, and one shader pack; full post-removal assembly pending |
| config/datapack assembly | PASS | reference config present; 10 datapack zips present |
| Fabric launcher | PASS | installer 1.1.2 generated MC 1.21.1 / loader 0.19.5 launcher |
| complete-overlay boot | PASS | reached `Done (6.377s)` with 101 jars; stopped cleanly |

## Boot attempts

`mod set hash` is written by `boot-test.ps1` after an actual launch. The first PlayerXP failure was captured in the then-current runtime `logs/latest.log`; later attempts have immutable run captures.

| # | date | stage | run dir | mod set hash | Cobblemon | loader | outcome | errors / blocker | action taken |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2026-09-08 | baseline | — | — | 1.7.3 | 0.19.5 | NOT RUN | human EULA acceptance required | none |
| 1 | 2026-09-08 | Cobblemon-only | — | — | 1.8.0 | 0.19.5 | NOT RUN | human EULA acceptance required | none |
| 2 | 2026-09-08 | loader blockers | — | — | 1.8.0 | 0.19.5 | NOT RUN | human EULA acceptance required | overlay prepared |
| 3 | 2026-09-08 | trainer/battle core | — | — | 1.8.0 | 0.19.5 | NOT RUN | human EULA acceptance required | overlay prepared |
| 4 | 2026-09-08 | supported addons | — | — | 1.8.0 | 0.19.5 | NOT RUN | human EULA acceptance required | overlay prepared |
| 5 | 2026-09-08 | complete overlay | — | — | 1.8.0 | 0.19.5 | PREFLIGHT REFUSED | `eula.txt` missing; Minecraft not launched | awaiting human action |
| 6 | 2026-09-09 | complete overlay | runtime `logs/latest.log` | not captured | 1.8.0 | 0.19.5 | FAILED | PlayerXP 1.1.1 common entrypoint loaded client-only `ItemTooltipCallback` on SERVER | exclude PlayerXP from server only; retain client provisionally |
| 7 | 2026-09-09 | without PlayerXP | `20260909-000955` | `4439B7A088FB` | 1.8.0 | 0.19.5 | FAILED | Raid Dens datapack reload called removed `GraalShowdownService.getContext()` | remove Raid Dens from both plans before world construction |
| 8 | 2026-09-09 | without PlayerXP or Raid Dens | `20260909-001735` | `D1483348BC2D` | 1.8.0 | 0.19.5 | **BOOTED** | reached `Done (6.377s)` | server stopped cleanly |

## Functional smoke tests

| Test | Players | Result | Notes |
| --- | ---: | --- | --- |
| server boots | 0 | PASS | 101-jar complete overlay reached `Done (6.377s)` |
| client connects | 1 | NOT TESTED | assembled client exists at `runtime/client/`; requires GUI launch and booted server |
| `/pokespawn` and natural spawning | 1 | NOT TESTED | |
| wild battle, catch, Capture XP | 1 | NOT TESTED | |
| RCT trainer spawn and battle | 2 | NOT TESTED | |
| Mega Showdown and ZAMegas | 1 | NOT TESTED | |
| TMCraft teaches move | 1 | NOT TESTED | |
| PC and PokéCenter structure | 1 | NOT TESTED | |
| CobbleNav | 1 | NOT TESTED | |
| Raid Den multiplayer flow | 2 | REMOVED | runtime-incompatible; future release must be retested before use |
| Cobbreeding multiplayer flow | 2 | NOT TESTED | |
| second client sees Pokémon/battle | 2 | NOT TESTED | |
| reconnect and restart persistence | 2 | NOT TESTED | |

## Current conclusion

EXP-000 remains **INCOMPLETE**. The dedicated-server boot criterion now passes. The repository is **NOT READY FOR EXP-001** until a client connects, the critical functional checks pass, and the world-critical freeze has runtime evidence. The successful run still logs nonfatal errors from Raid Dens loot-table data retained inside an upstream datapack; per the boot-iteration rule this was recorded rather than repaired because it did not block startup.
