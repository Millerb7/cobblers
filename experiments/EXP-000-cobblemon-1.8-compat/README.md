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
- 103 hash-verified server jars: 90 unchanged base jars and 13 Modrinth-pinned replacements;
- the reference config plus the repository overlay config;
- all 10 reference datapack zips;
- `server.properties` copied from the repository example.

The matching disposable client at `runtime/client/` contains 136 hash-verified jars, 47 resource packs, 10 datapacks, and one shader pack. It is ready to import into a Minecraft launcher, but no GUI launch has been performed.

The reference pack was read and hashed only. No jar, config, datapack, save, or launcher file under `base-pack/cobbleverse/` was modified.

## Controlled test sequence

| Stage | Mod set | Purpose | Current result |
| --- | --- | --- | --- |
| 0 | unmodified 1.7.42 server set | prove the local baseline | not run; EULA gate |
| 1 | replace Cobblemon only | capture exact hard-pin errors | not run; EULA gate |
| 2 | add TMCraft, Capture XP, Tim Core updates; remove Better Pokédex Scanner | clear declared 1.7.3 blockers | not run; EULA gate |
| 3 | update RCT/API, Mega Showdown, ZAMegas | isolate trainer and battle core | not run; EULA gate |
| 4 | update Cobbreeding, Only Bottle Caps, PlayerXP, CobbleNav, Fight or Flight | use identified 1.8-era gameplay releases | not run; EULA gate |
| 5 | complete overlay with preserved unknown addons | determine actual stable server set | assembled and hash-verified; launch blocked by EULA |

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
| Raid Dens | 2 | den generates and a multiplayer raid can start and finish |
| Cobbreeding | 2 | pasture breeding starts, persists, and produces an egg without duplication |
| visibility/synchronization | 2 | each client sees the other player's Pokémon and battle state correctly |
| reconnect/restart | 2 | party, trainer, den, breeding, and world block state remain consistent |

Record observations in `results.md`; do not infer a pass from an absent error.

## Results

- Baseline inventory: 138 jar records, 137 enabled and one disabled.
- Immutable baseline server verification: 104 matching jars, zero missing, zero hash mismatches; 34 expected non-server extras.
- Target overlay: 13 replacements, one enabled removal, one disabled-file removal, 33 client-only mod IDs excluded from the server.
- Target assembly verification: 103 matching jars, zero missing, zero hash mismatches, zero extras, zero unverified.
- Client assembly verification: 136 matching jars, zero missing, zero hash mismatches, zero extras, zero unverified.
- Preflight: Java 21.0.9, Fabric launcher present, and 103 jars present. It stopped at the missing `eula.txt` check. Minecraft was not launched.
- Client and gameplay results: not tested.

See `docs/research/COBBLEVERSE_COMPATIBILITY.md` and `docs/research/WORLD_CRITICAL_DEPENDENCIES.md` for the full audit.

## Limitations

- The Minecraft EULA requires a human decision; repository tooling does not create or accept `eula.txt`.
- Loader metadata and hashes do not prove mixin, API, data, or gameplay compatibility.
- Server boot cannot validate client-only mods, resource packs, rendering, UI, or client/server registry agreement.
- Functional testing requires a client, and several checks require two players.
- World-critical compatibility requires fresh-world generation and save/restart checks.

## Decision

**INCOMPLETE — NOT READY FOR EXP-001.** The target pack is assembled and reproducible, but the server has not booted and no client or functional smoke test has run. Do not begin Route 1 or serious map construction.

The next action is for a human to read the Minecraft EULA and, if they agree, accept it in `runtime/server/eula.txt`. Then execute stages 0–5, update `results.md`, and run the smoke checklist. ADR-001 remains Proposed until at least the complete-overlay server boot and client connection pass.

## Follow-up

1. Human EULA acceptance in the disposable runtime.
2. Run and capture the staged server boots.
3. Build the client target pack and connect.
4. Complete the two-player functional checklist.
5. Freeze or replace world-critical dependencies from fresh-world evidence.
