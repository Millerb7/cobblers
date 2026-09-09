# experiments/

Each design question that could sink the campaign gets an experiment before we
build on it. An experiment is a folder `EXP-NNN-short-name/` with a `README.md`
following the template below, optional `runs/` captures, and a `results.md`.

Experiments are cheap and disposable. They prove or disprove one thing; they
are not features. Decisions they produce are recorded in `docs/decisions/`.

| Id | Question | Status |
|----|----------|--------|
| EXP-000 | Does the Cobbleverse base boot on Cobblemon 1.8 with our overlay? | procedure written, not yet run |
| EXP-001 | Can we author a curated route (controlled encounters)? | stub |
| EXP-002 | Can we build a genuinely difficult trainer battle? | stub |
| EXP-003 | Can we enforce a level cap? | stub |
| EXP-004 | Can we build a trainer gauntlet with restrictions? | stub |
| EXP-005 | Can we build a puzzle dungeon with persistent state? | stub |
| EXP-006 | Can we place a static, authored encounter? | stub |
| EXP-007 | Can we track story progression? | stub |

## Template

```markdown
# EXP-NNN: <title>

## Objective
One paragraph. What question does this answer? What would "yes" unlock?

## Success criteria
Bullet list. Observable, testable in-game or in logs.

## Dependencies
Mods / datapacks / tools / other experiments this needs. Versions.

## Implementation
What was built, where it lives (paths), how it is configured.

## Test instructions
Step by step, so someone else can reproduce: server setup, commands, what to look at.

## Results
What actually happened. Link `runs/<timestamp>/` captures. Screenshots if useful.

## Limitations
What this does NOT show. Edge cases not covered (multiplayer, restarts, ...).

## Decision
Adopt / adapt / reject, and why. Link the `docs/decisions/` record if one was written.

## Follow-up
Next experiments or tasks this unlocks or requires.
```
