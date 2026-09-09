---
name: boot-test
description: Assemble a dedicated server from the modpack manifest, boot it, collect the logs, and record the result in experiments/. Use when asked to boot-test, check whether the mod set loads, verify a compatibility change, or before claiming any runtime-relevant change works. Never accepts the EULA.
---

# Boot test

**Inputs:** the experiment this run belongs to (`experiments/EXP-NNN-*`), and
optionally a manifest variant to test. Boot testing proves the server starts
with this mod set; it does not prove any gameplay feature works.

## Entry point

`server/scripts/boot-test.ps1` is the planned entry point (with
`server/scripts/assemble-server.ps1` doing the assembly step). **If they do
not exist yet, say so and stop** — do not improvise a launcher, download
jars, or hand-copy mods. Report that the script is missing as the blocker.

## Steps

1. **Assemble** — `.\server\scripts\assemble-server.ps1` builds a server
   directory from `modpack/manifest/`, excluding mods whose environment is
   `client` (see `.Codex/rules/server.md`). Record the manifest revision
   (`git rev-parse HEAD`) and the resulting mod list.
2. **EULA gate** — if `eula.txt` is absent or `eula=false`, the server will
   stop and say so. **Do not set the `eula` key to true yourself.** Report it and ask the user
   to accept it themselves; then continue.
3. **Boot** — `.\server\scripts\boot-test.ps1` starts the server with a
   timeout, waits for the ready line (`Done (` in `logs/latest.log`) or a
   failure, then stops it. Never leave a server running.
4. **Collect** — copy `logs/latest.log` and any `crash-reports/*` into the
   experiment folder as `boot-<yyyymmdd-hhmm>.log`. Filter for the report:
   first `ERROR`/`FATAL`, loader "Incompatible mods" block, mixin failures,
   JSON parse errors. Never paste a full log into the conversation.
5. **Diagnose** — if it did not reach ready, hand the filtered log to
   `build-doctor` for a verdict. Apply at most one minimal fix per
   iteration, through the owning agent, and re-run.
6. **Record** — update the experiment README (results, versions, mod set,
   decision) per the `experiment` skill and `.Codex/rules/research.md`, and
   move affected statuses in `docs/research/COBBLEVERSE_COMPATIBILITY.md`
   no higher than `NEEDS FUNCTIONAL TEST`.

## Boundaries

- Never accept the EULA, edit `server.properties` to disable `online-mode`,
  or commit anything from the assembled server directory.
- Do not remove several mods at once to force a boot.
- A boot with datapack load errors is `BOOTED WITH ERRORS`, not a pass.

## Output

- **Verdict** — `BOOTED`, `BOOTED WITH ERRORS`, `FAILED`, or `BLOCKED`
  (missing script, EULA, missing jars).
- **Versions** — Minecraft, loader, Fabric API, Cobblemon, manifest revision.
- **Findings** — filtered log lines with the mod/file responsible.
- **Recorded in** — the experiment path updated.
- **Not verified** — everything beyond "the server started".
