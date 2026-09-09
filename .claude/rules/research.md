---
description: Research and experiment records — verified versus assumed, sources, and the compatibility status vocabulary
paths:
  - "docs/research/**"
  - "experiments/**"
---

# Research and experiments

Owner of: how facts are recorded and graded. Testing tiers are in
`testing.md`; the experiment folder procedure is the `experiment` skill.

## Verified versus assumed

- Every claim about Cobblemon, an addon, Fabric, or Minecraft carries a
  label and a source: `VERIFIED` (seen in source, official docs, a changelog
  for the stated version, the local snapshot, or an experiment result) or
  `ASSUMED` (inferred, community post, unversioned page, memory).
- Sources are URLs or `path:line`, plus the version they apply to. A fact
  about 1.7.3 is not a fact about 1.8.x until re-checked.
- A working value in `base-pack/cobbleverse/config/` proves one instance,
  not a schema.
- Unknowns are written down as experiment candidates in
  `docs/research/EXPERIMENT_BACKLOG.md`, not resolved by guessing.

## Status vocabulary

Used in `docs/research/COBBLEVERSE_COMPATIBILITY.md`,
`docs/research/CAPABILITY_MATRIX.md`, and `base-pack/inventory/`:

| Status | Meaning |
|---|---|
| `VERIFIED WORKING` | Booted and functionally tested on the target versions; experiment linked |
| `LIKELY WORKING` | Metadata and API coupling give no reason to expect failure; not yet run |
| `NEEDS BOOT TEST` | Must be loaded on the target to know |
| `NEEDS FUNCTIONAL TEST` | Loads (or expected to), but the feature it provides must be exercised |
| `INCOMPATIBLE` | Declared dependency range or observed failure excludes the target |
| `UPDATE AVAILABLE` | A newer build targeting Cobblemon 1.8.x / MC 1.21.1 exists; cite it |
| `REPLACE` | Drop in favor of a named alternative (Cobblemon native or another mod) |
| `REMOVE` | Drop without replacement; state what is lost |
| `UNKNOWN` | No evidence either way |

`UNKNOWN` stays `UNKNOWN` until verified. A status only moves up with linked
evidence (log, experiment, source); it can move down on a single observed
failure. `LIKELY WORKING` is the ceiling without a run.

## Experiment records

Each `experiments/EXP-NNN-<slug>/README.md` has: objective, implementation,
test instructions, results (with versions and log excerpts), limitations,
decision. A result without the mod set and versions it ran on is incomplete.
