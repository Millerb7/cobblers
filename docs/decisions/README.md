# Architecture Decision Records

Important architectural choices for this project are recorded here as ADRs.

An ADR is written when a decision:

- constrains future work (which mod provides trainers, how progression is stored),
- is expensive to reverse (world-critical dependencies, world asset strategy),
- or resolves a question that an experiment in `docs/research/EXPERIMENT_BACKLOG.md`
  was created to answer.

**Do not invent decisions before an experiment justifies them.** An ADR that
records "we chose X" must point at the evidence (experiment result, boot log,
verified documentation). Until then the topic stays in the backlog as an open
question and the ADR does not exist.

## Format

Copy `TEMPLATE.md` to `ADR-NNN-short-title.md`, using the next free number.
Status values: `Proposed`, `Accepted`, `Superseded by ADR-NNN`, `Rejected`.

## Index

| ADR | Title | Status |
| --- | ----- | ------ |
| [ADR-001](ADR-001-modpack-base-strategy.md) | Modpack base strategy: Cobbleverse as upstream reference, overlay targeting Cobblemon 1.8.x | Proposed |

Expected future ADRs (not yet written, pending experiments):

- Campaign progression storage (after EXP-007)
- Trainer system (after EXP-002)
- World asset strategy (before serious map construction)
- Level cap mechanism (after EXP-003)
