---
description: Dedicated server conventions — no secrets, no EULA, client-only mods excluded, runtime state never committed
paths:
  - "server/**"
---

# Dedicated server

Owner of: what goes into `server/` and what must not. Secrets and privacy
detail is in `security.md`; boot procedure is the `boot-test` skill.

## Contents

- `server/config/` — server-side mod configs and `server.properties`
  templates. `server/launch/` — JVM/launch configuration. `server/scripts/`
  — `boot-test.ps1` and `assemble-server.ps1` (planned entry points; say so
  if they do not exist yet rather than inventing flags).
- The server mod set is derived from `modpack/manifest/`, never maintained
  as a second list by hand. Mods whose `fabric.mod.json` environment is
  `client` are excluded from the server; mods with `*` or `server` go in.
  The environment field is what decides, not the mod's name — check
  `base-pack/inventory/mod_inventory.md`.
- Java 21, Fabric loader >= 0.18.4, Minecraft 1.21.1 (see `CLAUDE.md`).

## Never in git

- `eula.txt` — accepting the Minecraft EULA is a human decision. No script
  or agent sets the `eula` key to true in `eula.txt`.
- `servers.dat`, `ops.json`, `whitelist.json`, `banned-*.json`,
  `usercache.json` — player identities. Track `*.example.json` only.
- `world/`, `logs/`, `crash-reports/`, `backups/`, jars. `.gitignore`
  already covers these; do not add exceptions.
- Credentials, RCON passwords, tokens, or hostnames of the real server in
  `server.properties`, launch scripts, or docs. Use placeholders and a
  gitignored `.env`.

## Behavior

- `online-mode` stays `true` unless the user decides otherwise in an ADR.
- Config changes are stated with the mod, key, old and new value, and the
  source documenting the key. A config file is not proof the feature works;
  the `boot-test` skill plus an experiment is.
