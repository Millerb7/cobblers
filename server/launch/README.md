# server/launch/ - how the dedicated server is assembled

Nothing in this folder runs anything. It records the recipe so a human (or a
later script) can reproduce the server exactly.

## Components

| Component | Version | Source | Status |
|-----------|---------|--------|--------|
| Minecraft (server) | 1.21.1 | fetched by the Fabric installer | fixed by the pack |
| Fabric Loader | **0.19.5** (base requires >= 0.18.4) | Fabric installer, `-loader 0.19.5` | pinned for EXP-000 from Fabric Meta on 2026-09-08; 101-jar server boot passed on 2026-09-09 |
| Fabric API | 0.116.14+1.21.1 (base pack) | part of the mods set (manifest) | Cobblemon 1.8.0 requires Fabric API (Modrinth `P7dR8mSH`); the base version is assumed sufficient until boot test says otherwise |
| Fabric Language Kotlin | 1.13.13+kotlin.2.4.10 | mods set | as base |
| Architectury | 13.0.8 | mods set | as base |
| Cobblemon | 1.8.0 (Fabric) | overlay replace | target |
| Java | **21** (Temurin 21.0.9 found on the dev machine) | system | required by Cobblemon / MC 1.21.1 |

## Steps

1. **Install the launcher** (human action; downloads a jar):
   get the Fabric installer from fabricmc.net and run
   `java -jar fabric-installer-1.1.2.jar server -mcversion 1.21.1 -loader 0.19.5 -downloadMinecraft -dir <serverdir>`.
   It writes `fabric-server-launch.jar` (or `fabric-server-mc.1.21.1-loader.<v>-launcher.<i>.jar`),
   `server.jar`, and `libraries/`. All are gitignored.
2. **Mods**: `pwsh server/scripts/assemble-server.ps1 -TargetDir <serverdir>/mods -Apply`.
   Only `side: both|server` jars are copied. The server plan excludes 33 jars whose
   metadata marks them client-only and PlayerXP, whose common entrypoint was proven
   to load a client API on a dedicated server. The disabled legacy `particular` jar
   and incompatible Raid Dens jar are removed outright. Replacement jars for
   Cobblemon 1.8 must exist in `-SourceDir` or `-ExtraDir` (fetch them with
   `python tools/pack_manifest.py download --target <dir> --yes`).
3. **Config**: copy `base-pack/cobbleverse/config/` then `modpack/config/` (ours wins) into `<serverdir>/config/`.
   The server needs at least `global_packs.toml` so datapacks load.
4. **Datapacks**: copy `base-pack/cobbleverse/datapacks/` (including `extra/`) and `modpack/datapacks/` to `<serverdir>/datapacks/`
   (that is the path `global_packs.toml` force-loads; world-level `world/datapacks/` is not used).
5. **server.properties**: from `server/config/server.properties.example`.
6. **EULA**: open `<serverdir>/eula.txt`, read the linked EULA, and change the value yourself if you agree. No script does this.
7. **Boot**: `pwsh server/scripts/boot-test.ps1 -ServerDir <serverdir>` (see the script header for parameters).

## JVM

- Java 21. Check with `java -version`; `boot-test.ps1` refuses anything older.
- Memory: start with `-Xms4G -Xmx6G` for 4-8 players (Cobblemon + Terralith + ~100 server-side mods).
  Raise to 8G if the log shows long GC pauses. Do not exceed roughly half the host RAM.
- Flags: the plain `-Xms/-Xmx -jar fabric-server-launch.jar -nogui` is enough for a first boot.
  Aikar-style G1 flags are an optimisation for later, not a requirement.

## Open items

- Re-evaluate loader 0.19.5 only when a boot failure identifies the loader itself or a future pack rebase requires it.
- Decide the host (this dev machine vs. a VPS) and whether `playit.gg` / port forwarding is used.
- Backup routine for `world/` (outside git).
