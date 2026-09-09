---
name: open-pr
description: Hand a finished ticket over for review — push this worktree's branch and open a linked DRAFT pull request, then move the Issue to PR Made. Use after implementation and developer verification pass, when asked to open a PR, submit work, or hand a change over. Not for merging or for starting QA.
---

# Open the PR

The end of what an implementation session may do:

```
implement → developer verify → commit → push own branch
  → DRAFT PR → Issue: PR Made → STOP
```

**Inputs:** a one-line summary, and what you actually ran to verify.

## Before running it

Developer verification must genuinely pass — build, tests, and an observed run
if the change is user-visible. Use `build-and-verify`. If it does not pass, do
not open the PR; report what failed.

Commit first. The script refuses a dirty tree, because uncommitted changes
would not appear in the PR.

## Run it

```powershell
.\scripts\open-pr.ps1 -Summary "Wire back and forward" `
                      -Verified "Release build clean","ctest 9/9","observed run"
.\scripts\open-pr.ps1 -DryRun
```

It refuses to run on `main`, checks that the branch matches the Issue it
claims, pushes **this worktree's** branch, opens a **draft** PR carrying
`Closes #N`, and only then moves the card to `PR Made`. If PR creation fails
the card is deliberately left alone rather than claiming a PR that does not
exist.

There is no force-push option and no `-Ready` switch, by design.

## Then stop

Say the PR is open and hand it back. Do not:

- mark the PR ready for review — that is the human handover, and it is what
  starts independent QA
- start, rerun or interpret a QA run
- merge, or push anything to `main`
- push another worktree's branch
- move the Issue to `In QA`, `Release` or `Done`

The PR body records **developer verification only** and says so. Never write
anything implying independent QA has run or passed.

## If it stops

- **"Refusing to open a PR from main"** — the work is on the wrong branch. See
  the `start-work` or `parallel-work` skill.
- **"This branch does not match issue #N's expected branch"** — you may be in
  another Issue's worktree. Check `git rev-parse --show-toplevel` before doing
  anything else.
- **Project not updated** — the PR exists and is what matters; the board is a
  view. See `docs/WORKFLOW.md`.
