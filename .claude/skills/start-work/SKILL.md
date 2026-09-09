---
name: start-work
description: Begin a piece of feature or fix work from a GitHub Issue — find an existing issue or create one, then start a linked branch. Use before implementing a ticket, when asked to start work on something, or when a task arrives without an issue number.
---

# Start work

JobBored treats a GitHub Issue as the canonical work item. The Issue is the
durable record; the PR is the implementation record. Branch first, issue later
leaves work with no trace once the PR is merged.

**Inputs:** a short title, and optionally a type (`feature`, `bug`, `qa`, `build`)
or an existing issue number.

## Run it

```powershell
.\scripts\start-work.ps1 -Title "Settings tile uses the Apps icon" -Type bug
.\scripts\start-work.ps1 -Issue 42          # known issue
.\scripts\start-work.ps1 -Title "..." -DryRun
```

The script checks the working tree, `gh` auth, and the repository before it
creates anything, then resolves the work item:

| Situation | What happens |
|---|---|
| One strong title match | that Issue is reused |
| Several plausible matches | it stops and lists them; re-run with `-Issue N` |
| Nothing close | a new Issue is created from the matching template |

Ambiguity is never resolved by guessing — a wrongly reused issue is harder to
notice than a duplicate.

An Issue labelled `owner:<person>` — `owner:miller` today — is **manual
developer work and is refused**, before a branch or a card move happens. Those
Issues are decisions rather than tasks, and an agent choosing work off a backlog
cannot tell the difference by reading them. `-IncludeManualOwner` overrides it,
and belongs to the person named by the label: pass it only when the user has
authorized that specific Issue in this conversation. "Work through the backlog"
is not an authorization.

It then ensures the Issue is on the `JobBored Work Items` board **exactly
once** and sets its status to `In Progress`. That is the same transition
whether the Issue is new, sitting in `Todo`, or being picked up again after a
failed QA run — resuming is safe to repeat, and a developer explicitly
resuming is the one thing allowed to pull an item back out of `In QA`.

## After it runs

You are on a branch named `<issue>-<slug>` cut from current `main`, and the
work item is `In Progress`. Implement, then verify, then hand over:

```
In Progress → implement → developer verify → open-pr → PR Made → stop
```

Use the `open-pr` skill for the handover — it pushes the branch, opens the
**draft** PR with `Closes #N`, and moves the card. Do not open the PR by hand
and do not move the card by hand.

## When a work item is not worth it

Trivial repository housekeeping — a typo, a comment, a formatting pass — does
not need an Issue. Anything with observable behavior, a QA implication, or a
reason someone might ask "why did this change?" does.

## If it stops

- **`gh` missing or unauthenticated** — it prints the exact commands. Issue and
  branch creation need `repo`; adding to the Project also needs `project`.
- **Dirty working tree** — commit or stash first; a new branch would otherwise
  carry unrelated edits into this work item.
- **Project not found, or `Status` has no matching option** — the Issue and
  branch are still created and the script says what it skipped. The board is a
  view over Issues, so a missing board never blocks work; see
  `docs/WORKFLOW.md` for the one-time setup.
