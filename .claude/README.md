# Claude configuration

How the assistant configuration in this repository is organised. Kept short on
purpose: this file is documentation, not context — `CLAUDE.md` is the only
thing loaded into every session.

## Layout

| Path | Loaded | Purpose |
|---|---|---|
| `../CLAUDE.md` | always | Project identity, architecture, build, principles |
| `rules/` | when a matching file is touched | Path-scoped conventions |
| `skills/` | on description match | Multi-step procedures |
| `agents/` | descriptions always; body on use | Delegation targets |

Context cost is the reason for the split. Only `CLAUDE.md` plus the
one-line descriptions of each agent and skill are paid for every session;
everything else loads when it is relevant.

## Rules

Each topic has exactly one owner file, and files state their owner explicitly
where topics touch:

- `cpp-qt.md` — object lifetime, signals, headers
- `ui-architecture.md` — atomic layering, signal direction, styling
- `cef.md` — CEF correctness: threading, lifecycle, embedding
- `security.md` — security and privacy decisions
- `build.md` — CMake targets, dependencies, deployment
- `testing.md` — test structure and QA policy bindings

Do not restate a rule in a second file. Link the concept and keep the rule in
one place.

## Agents

Roles, not tasks. A one-off job is a skill or a script, not a new agent.

- `architect` — read-only structural analysis and planning
- `feature-dev` — scoped implementation inside the existing design
- `security-reviewer` — read-only security and privacy review
- `qa-reviewer` — reviews a completed deterministic QA run
- `build-doctor` — builds and classifies failures
- `repo-scout` — cheap read-only locator

Keep them short: one responsibility, tools, when to use, what they return,
prohibitions. Global rules ("do not commit", "never read `external/`") live in
`CLAUDE.md` once, not repeated in each agent.

## Model selection

Most agents declare no model and inherit the session's. Only two pin one, and
only to stay cheap:

- `repo-scout` and `build-doctor` → `haiku`. Both are mechanical: locate a
  symbol, or classify a compiler error. Deeper reasoning does not change the
  answer.

Everything else follows the session model, so upgrading a model does not mean
editing a dozen Markdown files. This is the only place the decision is
recorded; do not scatter model names into rules or skills.

## QA

The QA system is documented in `qa/README.md`. The only part that lives here
is `agents/qa-reviewer.md`, which reasons over the artifacts the QA scripts
produce and never reads the repository broadly.
