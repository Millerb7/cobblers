---
description: Secrets and player privacy — nothing sensitive in git, no automatic EULA acceptance, no credentials in scripts
paths:
  - "server/**"
  - "modpack/**"
  - "tools/**"
  - "**/*.ps1"
  - "**/*.sh"
  - "**/*.properties"
---

# Secrets and privacy

Owner of: what must never be committed, written by an agent, or logged.
Server layout is in `server.md`.

## Never commit or write

- Credentials of any kind: RCON passwords, hosting/API tokens, SSH keys,
  Modrinth/CurseForge tokens, `.env` files. Launch scripts read them from
  the environment or a gitignored file; they never contain them.
- `eula.txt`. Accepting the Minecraft EULA is a human act; no tool, script,
  or agent sets the `eula` key to true in `eula.txt` or passes a flag that does. If a boot stops at
  the EULA, report it and stop.
- Player identity files: `servers.dat`, `ops.json`, `whitelist.json`,
  `banned-*.json`, `usercache.json`. They hold usernames, UUIDs and server
  addresses. Track `*.example.json` with placeholder entries only.
- The real server's hostname/IP, or players' names and UUIDs, in docs,
  configs, or commit messages. Use placeholders.

## Handling

- If a tracked file is found to contain a secret, report it immediately and
  do not copy it anywhere else (no "sanitised" pastes into chat or docs).
- Do not add `.gitignore` exceptions for the files above. The exception
  already present for `base-pack/cobbleverse/config/defaultoptions/servers.dat`
  is an upstream default-options file from the pack, not a live one.
- Third-party mod licenses (`base-pack/cobbleverse/licenses/`, inventory
  notes) constrain redistribution; note license sensitivity when carrying a
  pack-specific mod forward, and do not commit jars.
