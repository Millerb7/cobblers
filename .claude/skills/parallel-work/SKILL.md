---
name: parallel-work
description: Run several implementation sessions at once using Git worktrees — one issue per branch per worktree, with plain git commands. Use when asked to work on multiple things in parallel, to set up a second Claude session, or to check which worktree and branch the current session owns before editing.
---

# Parallel work

```
one issue = one branch = one worktree = one implementation session
```

Every worktree shares this repository and its history. There are no extra
clones.

## When you need a worktree

| Situation | Worktree? |
|---|---|
| Two agents making **concurrent file changes** | **Yes** — required |
| Long-running implementation you want to leave in place | Yes |
| `repo-scout`, `qa-reviewer`, `build-doctor`, research | **No** — read-only, stays in this session |
| Running validation or a boot test for the current branch | No |

Read-only subagents share the session's worktree safely. Worktrees exist to
stop two *writers* colliding, not to isolate readers.

## Verify before you edit

At the start of every session, and before your first edit:

```powershell
git rev-parse --show-toplevel   # which worktree am I in
git branch --show-current       # which branch does it own
git status --short              # is someone else mid-edit here
```

If the branch is not the one you were asked to work on, **stop and say so**.
Do not edit, switch, or create a branch here — another session may be
mid-change.

## Create one

Worktrees live under `.claude/worktrees/` (gitignored). Branch names are
`<type>/<slug>` — `feature/`, `fix/`, `experiment/`, `research/`, `docs/`,
`bootstrap/`. Run from the main checkout, not from inside another worktree:

```powershell
git fetch origin
git worktree add .claude/worktrees/<slug> -b <type>/<slug> origin/main
```

Then open a Claude Code session pointed at that directory.

```powershell
git worktree list                                   # what is in flight
git worktree remove .claude/worktrees/<slug>        # refuses if dirty
git branch -d <type>/<slug>                         # after merge
```

## Rules

1. Never edit another session's worktree. Inspecting it is fine.
2. Never check the same branch out twice — git refuses, and the refusal is correct.
3. New work branches from `origin/main`, never from another feature branch.
4. Removal refuses dirty worktrees. Do not reach for `--force` to make an error go away.
5. Worktrees prevent filesystem collisions, not merge conflicts. Two branches
   touching `modpack/manifest/` or the same campaign file still conflict at
   merge time — prefer independent scopes.

## Lifecycle

```
implement → validate → (boot/functional test if runtime) → commit → push own branch → DRAFT PR → stop
```

Use the `open-pr` skill. Never push another worktree's branch, never push
`main`, never mark your own PR ready for review, never merge.
