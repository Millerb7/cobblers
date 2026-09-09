# Codex agent system

This repository keeps its Claude Code setup intact and adds a Codex-native
translation. `AGENTS.md` is the small, always-loaded orchestration policy;
this document records the migration and model choices.

## Imported Claude inventory

The current `.claude/` system contains 11 agents, six path-scoped rules, four
skills, and one shared settings file. It has no hooks or command directory.

- Agents: `repo-scout`, `dependency-auditor`, `cobblemon-researcher`,
  `content-architect`, `datapack-content-dev`, `minecraft-systems-dev`,
  `world-content-dev`, `trainer-balance-designer`, `test-author`,
  `qa-reviewer`, and `build-doctor`.
- Rules: datapacks, research evidence, secrets, dedicated-server state,
  testing, and world-critical dependency safety.
- Skills: parallel worktrees, pull-request handoff, boot testing, and the
  experiment-record workflow.
- Settings: safe read-only Git commands, project validators, pytest, and the
  two server scripts are allowed; secret files are denied.
- Conventions: upstream is read-only, campaign and world layers stay separate,
  unknown behavior becomes an experiment, and implementation is separated
  from independent testing/review.

## Agent migration

| Claude agent | Decision | Codex result |
| --- | --- | --- |
| `repo-scout` | ADAPT | Luna read-only locator with targeted searches |
| `dependency-auditor` | ADAPT | Terra read-only dependency and metadata audit |
| `cobblemon-researcher` | ADAPT | Terra read-only, evidence-backed research |
| `content-architect` | ADAPT | Sol architecture and multiplayer state design |
| `datapack-content-dev` | ADAPT | Terra data-driven implementation |
| `minecraft-systems-dev` | ADAPT | Sol cross-system server implementation |
| `world-content-dev` | ADAPT | Terra world asset/spec implementation |
| `trainer-balance-designer` | ADAPT | Sol read-only balance design |
| `test-author` | ADAPT | Terra validation implementation, separate from feature author |
| `qa-reviewer` | ADAPT | Terra independent read-only review |
| `build-doctor` | ADAPT | Sol read-only diagnosis after cheaper log extraction |

Three older roles visible in repository history were intentionally not restored:

- `architect` was MERGED into `content-architect` and made campaign-specific.
- `feature-dev` was MERGED into `datapack-content-dev` for bounded data work
  and `minecraft-systems-dev` for cross-system runtime work.
- `security-reviewer` was DROPPED as a permanent specialist because this
  private Minecraft content repository has no application-auth surface;
  secret/EULA/player-data rules remain persistent in `.claude/rules/security.md`
  and `AGENTS.md`.

`architecture-reviewer` is NEW. It reserves Astra for a rare second opinion on
major irreversible decisions, unresolved cross-system failures, or explicit
maximum-quality review.

## Effective defaults

`.codex/config.toml` sets:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 6
default_subagent_model = "gpt-5.6-terra"
default_subagent_reasoning_effort = "medium"
interrupt_message = true
```

An unnamed worker therefore uses Terra medium rather than inheriting an
expensive root model. Explicit settings in each custom-agent file override the
defaults.

## Custom agents

| Agent | Model | Effort | Sandbox | Purpose |
| --- | --- | --- | --- | --- |
| `repo-scout` | `gpt-5.6-luna` | medium | read-only | Search and mechanical discovery |
| `dependency-auditor` | `gpt-5.6-terra` | high | read-only | Dependency and compatibility evidence |
| `cobblemon-researcher` | `gpt-5.6-terra` | high | read-only | Sourced behavior/data-format research |
| `content-architect` | `gpt-5.6-sol` | high | workspace-write | Architecture and ADR proposals |
| `minecraft-systems-dev` | `gpt-5.6-sol` | high | workspace-write | Cross-system server mechanics |
| `datapack-content-dev` | `gpt-5.6-terra` | high | workspace-write | Datapacks and structured campaign data |
| `world-content-dev` | `gpt-5.6-terra` | high | workspace-write | World specs and reproducible assets |
| `trainer-balance-designer` | `gpt-5.6-sol` | high | read-only | Difficult but fair balance proposals |
| `test-author` | `gpt-5.6-terra` | high | workspace-write | Validators and regression tests |
| `qa-reviewer` | `gpt-5.6-terra` | high | read-only | Independent correctness and multiplayer review |
| `build-doctor` | `gpt-5.6-sol` | high | read-only | Difficult boot/integration diagnosis |
| `architecture-reviewer` | `gpt-6-astra` | high | read-only | Exceptional high-impact second opinion |

## Routing and context policy

Luna handles clear, repetitive discovery. Terra is the default for serious
bounded work. Sol handles ambiguity that spans systems, hard debugging, and
game balance. Astra is never routine: use it only after Sol-level work leaves
a consequential question unresolved or when the user explicitly requests it.

For normal complex work, use two to four independent workers. Avoid agents
editing the same file. Worktrees are for substantial concurrent writers with
clean ownership boundaries; read-only work shares the current checkout.
Subagents return concise findings rather than raw inventories or logs.

## Root model guidance

- Ordinary project work: `gpt-5.6-terra`, medium.
- Large multi-agent implementation: `gpt-5.6-sol`, high, with Luna/Terra
  specialists delegated by role.
- Architecture/design: `gpt-5.6-sol`, high; escalate a major disputed or
  irreversible decision to `architecture-reviewer`.
- Difficult troubleshooting: `gpt-5.6-sol`, high, after a cheaper worker
  extracts relevant logs and versions; Astra only if still unresolved.

## Compatibility note

Codex CLI 0.153.4 accepts the current fields used here:
`agents.max_concurrent_threads_per_session`, default subagent model/effort,
and custom-agent `model`, `model_reasoning_effort`, and `sandbox_mode`.
Subagents inherit the parent session's live permission overrides, so a parent
started read-only cannot be made writable by an agent file alone.
