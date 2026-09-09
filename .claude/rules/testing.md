---
description: Validation versus runtime testing, and the separation between implementer and test author
paths:
  - "tools/**"
  - "tests/**"
  - "experiments/**"
---

# Testing

Owner of: what counts as verified, and who verifies. Status vocabulary for
research and experiments is in `research.md`.

## Two tiers

| Tier | What it proves | Where |
|---|---|---|
| **Validation** | Files parse, required fields exist, namespaces and overrides are intentional, manifests are complete | `tools/validate.py`, `tools/pack_manifest.py`, `tests/` via `python -m pytest` |
| **Runtime** | The server boots with this mod set; a mechanic behaves as designed in the game | `boot-test` skill, then a functional test recorded in `experiments/EXP-NNN-*/` |

Validation never stands in for runtime. A green pytest run means the data
is well-formed, not that Cobblemon reads it the way we think. Report the
tier you actually reached.

## Rules

- **Different agents.** Whoever implements content or a system does not
  write its validator, its tests, or the experiment verdict. `test-author`
  writes checks; `qa-reviewer` grades experiments; the implementer reports
  what it ran. If one session must do both, say so explicitly in the report.
- pytest suites are offline and fast: no Minecraft launch, no downloads, no
  reading of secrets, `eula.txt`, or `servers.dat`. Use the real repository
  files or small fixtures under `tests/`.
- A test is named for the property it protects and says in a comment what
  breaks without it. Assert behavior and data properties, not the internal
  call order of the tool.
- A case that cannot run is reported `NOT_EXECUTED` or `BLOCKED` with the
  reason. Never describe an unexecuted check as passing.
- Runtime results record the exact versions (Minecraft, loader, Cobblemon,
  the mod set) and the log or observation they rest on. "Should work" is not
  a result.
