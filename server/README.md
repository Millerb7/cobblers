# server/

Everything needed to **assemble and boot the private dedicated server**, minus
the things that must never be committed.

| Path | Tracked? | Purpose |
|------|----------|---------|
| `config/server.properties.example` | yes | Sane private-server defaults. Copy to the live server dir as `server.properties` and edit. |
| `launch/README.md` | yes | How the server is put together: Fabric installer, loader version, Java 21, memory. |
| `scripts/assemble-server.ps1` | yes | Builds `server/mods/` from the manifest plan (`--side server`) out of a local jar folder. Dry-run by default. |
| `scripts/boot-test.ps1` | yes | Pre-flight checks, boots the server once, captures logs into `experiments/EXP-000-cobblemon-1.8-compat/runs/`. |
| `scripts/install-exp001-world.ps1` | yes | Installs/selects the separate F4 WorldPainter export in the proven local runtime; leaves EULA and EXP-009 untouched. |
| `scripts/run-exp001-server.ps1` | yes | Guarded interactive launcher for the selected EXP-001 F4 world. |
| `mods/` | **no** (`*.jar` gitignored) | Output of `assemble-server.ps1`. |
| `libraries/`, `versions/`, `*.jar` | **no** | Fabric server launcher output. |

## Never committed (see `.gitignore`)

- `eula.txt` - accepting the Minecraft EULA is a human decision. No script here writes it.
- `world/`, `world_*/`, `logs/`, `crash-reports/`, `backups/`
- `ops.json`, `whitelist.json`, `banned-*.json`, `usercache.json` (player UUIDs). Commit `*.example.json` variants only.
- secrets: `.env`, `*.pem`, `*.key`, `secrets/`; anything with RCON passwords or tokens. `server.properties` itself is not tracked because it can carry `rcon.password`.

## Assembly (see `launch/README.md` for detail)

1. Install the Fabric server launcher for Minecraft 1.21.1 into a server dir (outside git, or `server/` itself since the launcher output is ignored).
2. `pwsh server/scripts/assemble-server.ps1 -TargetDir <serverdir>/mods -Apply` (after a dry run).
3. Copy `config/server.properties.example` to `<serverdir>/server.properties` and edit.
4. Put the base datapacks (+ ours from `modpack/datapacks/`) where `global_packs.toml` expects them and copy the config overlay.
5. Generate the Cobbleverse riding-compatible runtime datapack using the command in `launch/README.md`.
6. Read and, if you agree, accept the EULA in `<serverdir>/eula.txt` yourself.
7. `pwsh server/scripts/boot-test.ps1 -ServerDir <serverdir>`.

## Client pack (ADR-006, Proposed)

The server can push one resource pack to every client, so players install nothing by hand:
`cobblers-client-AllTheMons-subset.zip` (AllTheMons models for the 43 doll species, Flutter Mane and Iron Valiant
among them, plus Cobblemon 1.8's own files for the mis-assembled and crash forms). It is built locally and never
committed.

**Licence gate first.** The AllTheMons files are under ALLTHEMONS LICENSE v3.2, whose §1.3 allows uploading copies
"only with explicit written permission". Hosting the zip at a URL is an upload. Do not do steps 2-4 until Lvnatic's
written permission is on record in ADR-006. Without it, the route that uploads nothing is ATM x MSD v4.0 referenced
from Modrinth by hash (`docs/research/CLIENT_MODEL_FIXES.md`).

1. Build it, with the game closed, from a client instance (read only):
   `python tools/client_model_fix.py build --server-pack --instance "<client instance>"`.
   It prints the size and the sha1 and writes `build/client/cobblers-client-AllTheMons-subset.zip.sha1`.
   If the sha1 differs from `resource-pack-sha1` in `config/server.properties.example`, update the example, ADR-006
   and `docs/research/CLIENT_MODEL_FIXES.md` (`tests/test_server_client_pack.py` fails until they agree).
2. Host the zip at an HTTPS direct-download URL reachable without login (ADR-006, "Hosting"). Upload the exact built
   file: a re-zipped copy has a different sha1, and clients reject it.
3. With the server stopped, copy the five `resource-pack*` / `require-resource-pack` lines from the example into the
   live `server.properties`, and set `resource-pack=<the URL>`.
4. Start the server, join, accept the prompt, and check the client log for the pack and a Flutter Mane or Vullaby on
   screen (`/pokespawn fluttermane`). A player who declines is disconnected (`require-resource-pack=true`).

A rebuild that changes the zip changes the sha1: re-upload, then update `resource-pack-sha1` in the live file.

## EXP-001 F4 playtest

The local F4 profile reuses the verified 100-jar runtime but has its own world,
`exp001-f4-pallet-prototype`. After export, install it with
`server/scripts/install-exp001-world.ps1`; start it with
`server/scripts/run-exp001-server.ps1`. Exact rebuild, placement and teleport
commands are in `experiments/EXP-001-curated-route/README.md`.
