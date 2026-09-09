---
name: open-pr
description: Hand finished work over for review — push this worktree's branch and open a DRAFT pull request against main with plain git and gh. Use after implementation and validation pass, when asked to open a PR, submit work, or hand a change over. Not for merging or for marking a PR ready.
---

# Open the PR

The end of what an implementation session may do:

```
implement → validate → commit → push own branch → DRAFT PR → STOP
```

**Inputs:** a one-line summary, and what you actually ran to verify.

## Before running it

- Validation must genuinely pass (`python tools/validate.py`,
  `python -m pytest` where they exist). If the change is runtime-relevant
  and a boot or functional test was possible, it has been run and recorded
  in `experiments/`. If it was not possible, the PR body says so.
- Commit first; uncommitted changes do not appear in the PR.
- Confirm the branch: `git branch --show-current` is not `main` and matches
  the work you were asked to do.

## Run it

```powershell
git push -u origin (git branch --show-current)
gh pr create --draft --base main --title "<summary>" --body @"
## What
<one paragraph>

## Verification (developer only)
- <command> — <result>
- Boot/functional test: <EXP-NNN link, or "not run: <reason>">

## Not verified
- <what still needs a running Minecraft or a human>
"@
```

No force-push, no `--no-draft`, no merge.

## Then stop

Say the PR is open and hand it back. Do not:

- mark the PR ready for review — that is the human handover
- merge, or push anything to `main`
- push another worktree's branch
- describe validation as if it were runtime proof

## If it stops

- **`gh` missing or unauthenticated** — report the exact command that failed;
  do not work around it with tokens.
- **Refused on `main`** — the work is on the wrong branch; see `parallel-work`.
