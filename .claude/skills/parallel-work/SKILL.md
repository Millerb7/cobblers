---
name: parallel-work
description: Run several implementation sessions at once using Git worktrees — one Issue per worktree. Use when asked to work on multiple Issues in parallel, to set up a second Claude session, or when you need to check which worktree and Issue the current session owns before editing.
---

# Parallel work

```
one Issue = one branch = one worktree = one implementation session
```

Every worktree shares this repository and its history. There are **no extra
clones**, and no dependency is copied.

## When you need a worktree

| Situation | Worktree? |
|---|---|
| Two agents making **concurrent code changes** | **Yes** — required |
| Long-running implementation you want to leave in place | Yes |
| `repo-scout`, `security-reviewer`, `architect`, research | **No** — read-only, stays in this session |
| Running a build or tests for the current Issue | No |

Read-only subagents share the session's worktree safely. Worktrees exist to
stop two *writers* colliding, not to isolate readers.

## Verify before you edit

At the start of every session, and before your first edit:

```powershell
git rev-parse --show-toplevel   # which worktree am I in
git branch --show-current       # which Issue does it own
git status --short              # is someone else mid-edit here
```

The branch's `NNN-` prefix is the Issue this worktree owns. **If it does not
match the Issue you were asked to work on, STOP and say so.** Do not edit, do
not switch branches, do not create a branch here — another session may be
mid-change, and switching a branch out from under it corrupts its work.

## Create one

```powershell
.\scripts\new-worktree.ps1 -Issue 15
```

Run it from the **control workspace** (`Job-Bored/`), not from inside another
worktree. It fetches, branches from current `origin/main`, creates
`..\Job-Bored-wt-15`, and moves the Issue to `In Progress` — only after the
worktree exists. Re-running is safe: an existing worktree for that Issue is
reused, never duplicated.

Then open a Claude Code session pointed at that directory.

```powershell
.\scripts\list-worktrees.ps1    # what is in flight
.\scripts\remove-worktree.ps1 -Issue 15
```

## Rules

0. Never fill a round with an Issue labelled `owner:<person>` (`owner:miller`
   today). Those are manual developer work; `new-worktree.ps1` refuses them.
   See `docs/WORKFLOW.md`, "Ownership labels".
1. Never edit another Issue's worktree. Inspecting it is fine.
2. Never check the same branch out twice — git refuses, and the refusal is correct.
3. New work branches from `origin/main`, never from another feature branch.
4. `Job-Bored/` is the control workspace, not an implementation workspace.
5. Removal refuses dirty worktrees. Do not reach for `--force` to make an error go away.

## Lifecycle is unchanged

Each session still ends the same way and stops there:

```
implement → verify → commit → push own branch → DRAFT PR → PR Made → STOP
```

Use `.\scripts\open-pr.ps1`. Never push another worktree's branch, never push
`main`, never mark your own PR ready for review, never start QA, never merge.

## Conflicts

Worktrees prevent **filesystem** collisions, not **merge** conflicts. Two
Issues touching `RootWindow.cpp` or `theme.py` will still conflict at merge
time — prefer independent Issues, and resolve conflicts normally when they
happen. Nothing here predicts them.

## Builds

Each worktree builds into its own `build/` (derived from the script's own
location). CEF and vcpkg are **shared, read-only**, resolved from the control
workspace — never copy them per worktree. See `docs/WORKFLOW.md`.
