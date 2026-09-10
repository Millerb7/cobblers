# EXP-000: Cobbleverse → Cobblemon 1.8 compatibility

## Objective

Determine whether the Cobbleverse 1.7.42 experience can be preserved on Cobblemon 1.8.0, Minecraft 1.21.1 Fabric, without editing the reference pack in place. Establish the mod, config, datapack, and world-critical baseline that later campaign experiments can trust.

## Success criteria

- The dedicated server reaches `Done (` with the complete overlay and no mod-resolution errors.
- A client made from the same manifest connects without registry or mod mismatch errors.
- The two-player smoke checklist below passes.
- World-critical dependencies are frozen from fresh-world evidence.
- Every removal or replacement has a recorded reason and source.

## Dependencies

- Java 21; this machine has Temurin 21.0.9.
- Minecraft 1.21.1, Fabric installer 1.1.2, Fabric Loader 0.19.5.
- `modpack/manifest/base-cobbleverse-1.7.42.json` and `modpack/manifest/overlay.json`.
- The local immutable reference files under `base-pack/cobbleverse/`.
- `tools/pack_manifest.py`, `server/scripts/assemble-server.ps1`, and `server/scripts/boot-test.ps1`.

## Implementation

`test-pack.json` records the exact target and controlled stages. The disposable runtime is `runtime/server/` and is gitignored. It currently contains:

- the Fabric 1.21.1 server launcher with loader 0.19.5;
- 100 hash-verified server jars: 88 unchanged base jars and 12 Modrinth-pinned replacements;
- the reference config plus the repository overlay config;
- all 10 reference datapack zips;
- `server.properties` copied from the repository example.

The effective client plan contains 135 jars, 47 resource packs, 10 datapacks, and one shader pack. PlayerXP and Krypton remain client-optional; both are excluded from the server, while Raid Dens is removed from both sides. The assembled client launches and connects.

The reference pack was read and hashed only. No jar, config, datapack, save, or launcher file under `base-pack/cobbleverse/` was modified.

## Controlled test sequence

| Stage | Mod set | Purpose | Current result |
| --- | --- | --- | --- |
| 0 | unmodified 1.7.42 server set | prove the local baseline | not run; EULA gate |
| 1 | replace Cobblemon only | capture exact hard-pin errors | not run; EULA gate |
| 2 | add TMCraft, Capture XP, Tim Core updates; remove Better Pokédex Scanner | clear declared 1.7.3 blockers | not run; EULA gate |
| 3 | update RCT/API, Mega Showdown, ZAMegas | isolate trainer and battle core | not run; EULA gate |
| 4 | update Cobbreeding, Only Bottle Caps, PlayerXP, CobbleNav, Fight or Flight | use identified 1.8-era gameplay releases | not run; EULA gate |
| 5 | complete overlay with preserved unknown addons | determine actual stable server set | PlayerXP fatal during entrypoint initialization |
| 6 | exclude PlayerXP from server only | preserve its possible client tooltip while fixing dedicated-server startup | Raid Dens fatal during datapack reload |
| 7 | remove Raid Dens from both sides | omit a world-critical addon whose released/current code calls a removed API | **BOOTED**; reached `Done (6.377s)` |
| 8 | exclude Krypton from the server only | resolve the runtime-proven Cobblemon passenger attachment conflict while retaining client network optimization | **BOOTED**; riding attachment restored and reached `Done (1.314s)` |

After each failed boot, change only the implicated overlay entry, reassemble, and record the exact error. Do not edit the runtime mod folder as the source of truth.

## Commands used

```powershell
python tools/pack_manifest.py verify base-pack/cobbleverse/mods --side server --no-overlay
python tools/pack_manifest.py download --side server --replacements-only --target experiments/EXP-000-cobblemon-1.8-compat/runtime/replacements --yes
pwsh server/scripts/assemble-server.ps1 -ExtraDir experiments/EXP-000-cobblemon-1.8-compat/runtime/replacements -TargetDir experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods -Apply -Clean
python tools/assemble_client.py --replacements-dir experiments/EXP-000-cobblemon-1.8-compat/runtime/replacements --target experiments/EXP-000-cobblemon-1.8-compat/runtime/client --apply --clean
pwsh server/scripts/boot-test.ps1 -ServerDir experiments/EXP-000-cobblemon-1.8-compat/runtime/server -WhatIf
```

The Fabric installer command was:

```powershell
java -jar fabric-installer-1.1.2.jar server -mcversion 1.21.1 -loader 0.19.5 -downloadMinecraft -dir runtime/server
```

## Functional smoke tests

Run on a fresh disposable world after the server boots. Use two clients for rows marked `2`.

| Check | Players | What constitutes a pass |
| --- | ---: | --- |
| server startup | 0 | reaches `Done (` without loader, registry, datapack, or mixin failure |
| client connection | 1 | joins without missing registry or mismatched-mod kick |
| Cobblemon basics | 1 | starter flow or party works, `/pokespawn` works, natural spawns appear |
| wild battle and capture | 1 | battle completes, capture succeeds, Capture XP grants XP |
| RCT trainer | 2 | trainer spawns; either player can start and finish the intended battle flow |
| Mega Showdown + ZAMegas | 1 | Mega Evolution works in a trainer battle and resources/forms load |
| TMCraft | 1 | table/machine exists and teaches a move |
| PC and PokéCenter | 1 | PC deposit/withdraw works and PokéCenter structure assets load |
| CobbleNav | 1 | UI opens and expected data populates |
| Raid Dens | 2 | deferred: addon is removed until a Cobblemon 1.8-compatible build exists |
| Cobbreeding | 2 | pasture breeding starts, persists, and produces an egg without duplication |
| visibility/synchronization | 2 | each client sees the other player's Pokémon and battle state correctly |
| reconnect/restart | 2 | party, trainer, den, breeding, and world block state remain consistent |

Record observations in `results.md`; do not infer a pass from an absent error.

## Results

- Baseline inventory: 138 jar records, 137 enabled and one disabled.
- Immutable baseline server verification: 104 matching jars, zero missing, zero hash mismatches; 34 expected non-server extras.
- Target overlay: 13 replacements, two enabled removals, one disabled-file removal, 33 metadata client-only mod IDs, and two runtime-proven server-only exclusions.
- Final server verification: 100 matching jars, zero missing, zero hash mismatches, zero extras, zero unverified.
- Effective client plan: 135 jars. The full post-removal client assembly is pending because the immutable base jars are outside this worktree's local client source path.
- Runtime iteration: PlayerXP 1.1.1 crashed the dedicated server by loading `ItemTooltipCallback` from its common entrypoint. No newer release or upstream source fix exists, so it is excluded from the server only.
- Runtime iteration: Raid Dens failed datapack reload with `NoSuchMethodError: GraalShowdownService.getContext()`. Published 0.11.7 and current source retain that call, so the addon is removed from both plans.
- Runtime iteration: Krypton 0.2.8's server entity-tracker mixin prevented Cobblemon 1.8 from attaching the player as a passenger. Vanilla boat attachment passed; Better Third Person and Not Enough Animations were ruled out; server-only Krypton removal synchronized player and mount positions while the client copy remained enabled.
- Final boot: the 100-jar server reached `Done (1.314s)` and stopped cleanly. Capture `20260910-110333`, mod-set hash `62BEABD9398A`.
- Client connection and riding passed with one player; the remaining gameplay matrix is not tested.

See `docs/research/COBBLEVERSE_COMPATIBILITY.md` and `docs/research/WORLD_CRITICAL_DEPENDENCIES.md` for the full audit.

## Limitations

- The Minecraft EULA was accepted in the disposable runtime by a human; repository tooling did not create or change that acceptance.
- Loader metadata and hashes do not prove mixin, API, data, or gameplay compatibility.
- Server boot cannot validate client-only mods, resource packs, rendering, UI, or client/server registry agreement.
- Functional testing requires a client, and several checks require two players.
- World-critical compatibility requires fresh-world generation and save/restart checks.

## Decision

**INCOMPLETE — NOT READY FOR EXP-001.** The target server now boots reproducibly, but no client connection or functional smoke test has run and the world-critical set is not frozen. Do not begin Route 1 or serious map construction.

The next action is to assemble and launch the 135-jar client, connect it to the server, and run the smoke checklist. ADR-001 remains Proposed until client connection passes.

## Follow-up

1. Complete the post-removal client assembly and connect.
2. Decide whether PlayerXP provides enough client value and connects without a registry mismatch.
3. Complete the two-player functional checklist.
4. Remove or override the now-orphaned Raid Dens loot-table data if its nonfatal load errors remain in the client/server pack.
5. Freeze or replace world-critical dependencies from fresh-world evidence.
