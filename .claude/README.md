# Claude configuration

How the assistant configuration in this repository is organised. Kept short on
purpose: this file is documentation, not context — `CLAUDE.md` is the only
thing loaded into every session.

## Layout

| Path | Loaded | Purpose |
|---|---|---|
| `../CLAUDE.md` | always | Project identity, layers, layout, principles, delegation |
| `rules/` | when a matching file is touched | Path-scoped conventions |
| `skills/` | on description match | Multi-step procedures |
| `agents/` | descriptions always; body on use | Delegation targets |
| `settings.json` | always | Permission allowlist (read-only git, `python tools/*`, pytest, server scripts) |

Context cost is the reason for the split. Only `CLAUDE.md` plus the
one-line descriptions of each agent and skill are paid for every session;
everything else loads when it is relevant.

`settings.local.json` is gitignored and personal; do not commit it.

## Rules

Each topic has exactly one owner file, and files state their owner explicitly
where topics touch:

- `datapacks.md` — JSON validity, namespaces, overlay-not-edit for `modpack/datapacks/`, `campaign/`, and the base-pack datapacks
- `world-critical.md` — extra scrutiny for block/worldgen dependencies under `world/` and `modpack/manifest/`
- `server.md` — dedicated server: no secrets, no EULA, client-only mods excluded
- `testing.md` — validation vs runtime testing; test author separate from implementer
- `security.md` — secrets and player privacy
- `research.md` — verified vs assumed, the status vocabulary for `docs/research/` and `experiments/`

Do not restate a rule in a second file. Link the concept and keep the rule in
one place.

## Agents

Roles, not tasks. A one-off job is a skill or a script, not a new agent.

- `repo-scout` — cheap read-only locator
- `dependency-auditor` — jar metadata and Cobblemon 1.8 compatibility status; owns the compatibility doc, the inventory, and EXP-000
- `cobblemon-researcher` — verified-vs-assumed research into Cobblemon and addon capabilities, written to `docs/research/`
- `content-architect` — read-mostly campaign architecture, data models, datapack-vs-script-vs-mod boundaries; ADR proposals
- `datapack-content-dev` — datapacks, functions, advancements, loot, spawn configs
- `minecraft-systems-dev` — server-side logic and progression/puzzle/gauntlet state; must prove need before proposing a mod
- `world-content-dev` — dungeon specs, structures, schematics, templates under `world/`
- `trainer-balance-designer` — encounter availability, level caps, boss/gym/gauntlet teams, reward placement
- `test-author` — validation tooling and pytest suites; never the implementer of what it tests
- `qa-reviewer` — read-only review of experiments against success criteria
- `build-doctor` — read-only boot failure triage from server/client logs

Keep them short: one responsibility, tools, where it writes, what it must not
do, how it reports. Global rules ("verify before claiming", "never edit
`base-pack/`") live in `CLAUDE.md` once, not repeated in each agent.

## Skills

- `parallel-work` — worktree procedure with plain git
- `open-pr` — push the branch and open a draft PR with plain `gh`
- `boot-test` — assemble a server from the manifest, boot it, collect logs, record the result
- `experiment` — create and fill an `experiments/EXP-NNN-<slug>/` folder

## Model selection

Most agents declare no model and inherit the session's. Only one pins one,
and only to stay cheap:

- `repo-scout` → `haiku`. It is mechanical: locate a file or a string. Deeper
  reasoning does not change the answer.

Everything else follows the session model, so upgrading a model does not mean
editing a dozen Markdown files. This is the only place the decision is
recorded; do not scatter model names into rules or skills.
