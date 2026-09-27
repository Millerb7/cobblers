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

## Cross-system contracts

A contract is one system's guarantee that another relies on: Dive's unlimited
air, which swim fatigue must not cut short; the ferry's gates, which the
fatigue constants and the heightmap decide together. The registry is
`data/system_contracts.json` (owner, consumers, the lines that state it, the
tests that enforce it); `tests/test_system_contracts.py` runs the systems
together, as generated.

- A change to any system's rule (its data, its generator, the heightmap) runs
  `python -m pytest tests/test_system_contracts.py` before it is reported,
  and the report names every contract it touches. A green run of the changed
  system's own suite is not enough: on 2026-09-27 the swim-fatigue change
  passed its own tests and knocked out Dive players after 33 s.
- A new assumption one system makes about another gets a contract and a test
  in the same change: an entry in the registry, a `test_contract_*` test, and
  a citation of the line that states it.
- A contract that fails today is recorded in the registry (`fails_today`) and
  marked strict xfail through it, never deleted or loosened; the fix removes
  the entry.
