# server/

Everything needed to **assemble and boot the private dedicated server**, minus
the things that must never be committed.

| Path | Tracked? | Purpose |
|------|----------|---------|
| `config/server.properties.example` | yes | Sane private-server defaults. Copy to the live server dir as `server.properties` and edit. |
| `launch/README.md` | yes | How the server is put together: Fabric installer, loader version, Java 21, memory. |
| `scripts/assemble-server.ps1` | yes | Builds `server/mods/` from the manifest plan (`--side server`) out of a local jar folder. Dry-run by default. |
| `scripts/boot-test.ps1` | yes | Pre-flight checks, boots the server once, captures logs into `experiments/EXP-000-cobblemon-1.8-compat/runs/`. |
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
