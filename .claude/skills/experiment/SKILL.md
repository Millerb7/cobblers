---
name: experiment
description: Create or update an experiments/EXP-NNN-<slug>/ folder — a small proof with objective, implementation, test instructions, results, limitations and decision. Use when a question about Cobblemon, an addon, a mechanic or the mod set cannot be answered from sources, before building on an assumption, or when asked to record a proof.
---

# Experiment

Unknown behavior becomes an experiment (`CLAUDE.md` principle 8); small proofs
come before large implementations (principle 15). An experiment answers one
question with evidence from a running game or from data, and ends in a
decision or a follow-up experiment.

**Inputs:** the question, and where it came from (an entry in
`docs/research/EXPERIMENT_BACKLOG.md`, a design, or a failure).

## Create

1. Pick the next free number: `ls experiments/` — `EXP-000` is the
   Cobblemon 1.8 compatibility boot test. Slug is lowercase-hyphenated.
2. Copy the template from `experiments/README.md` to
   `experiments/EXP-NNN-<slug>/README.md`. If the template does not exist
   yet, use the sections below verbatim.
3. Link it from `docs/research/EXPERIMENT_BACKLOG.md` (status `planned`).

## README sections

```markdown
# EXP-NNN: <question as a title>

## Objective
One question, and the success criteria that would answer it yes or no.

## Implementation
What was built or configured, with paths. Mechanism rung used (principle 6).

## Test instructions
Exact steps to reproduce: versions, mod set / manifest revision, commands,
what to observe in-game or in the log.

## Results
What happened, with log excerpts or observations, dated, with versions.
Each result labeled by tier: validation / boot / functional.

## Limitations
What this does not show (single player vs multiplayer, one Pokémon, one
biome, not tested after restart, ...).

## Decision
Adopt / reject / needs EXP-NNN. Status changes made in docs/research/.
Link the ADR if one follows.
```

## Rules

- One question per experiment. A second question is a second folder.
- Keep artifacts small: filtered logs, a datapack of a few files, a config
  diff. No jars, world saves, or full logs in git.
- The implementer writes Objective through Test instructions and records
  raw Results. `qa-reviewer` judges whether Results support the Decision;
  the implementer does not grade its own work.
- A result without versions and the mod set it ran on is incomplete.
- Never accept the EULA or edit the live world to run an experiment; use a
  throwaway world in the assembled test server (`boot-test` skill).

## Output

- **Experiment** — path and status (planned / running / done).
- **Answer** — yes / no / partial, in one sentence, with the evidence tier.
- **Follow-ups** — statuses updated, ADR or next experiment proposed.
