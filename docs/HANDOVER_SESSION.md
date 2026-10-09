# Handover: session e7e951c6, 2026-10-08 (evening)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts. Review list:
`docs/OVERNIGHT_REVIEW_2026-10-06.md` (N155 is the chunk race).

## 1. The branches
- **[#129](https://github.com/Millerb7/cobblers/pull/129)** `build/2026-10-06-next` -> main, draft, **FROZEN** at
  `24ac441d3884d0b282401b0a01967104b22ab163` (the whole 10-06..10-08 batch, Glare included, main merged in).
  `gh pr merge 129 --match-head-commit 24ac441d3884d0b282401b0a01967104b22ab163`
- **[#128](https://github.com/Millerb7/cobblers/pull/128)** site: the starter page (Smeargle 476, Sketch uncapped), head
  `c5ff1f2bbfb3fa4c4d0d6202dae66a90e50123d5`. Same page as #129's, so either order merges clean.
- **`build/2026-10-08-chunk-race`**, stacked on #129: the N155 fix, the review, the Cutters fix, the sigil calls, this
  STATE and handover. Its PR is against `build/2026-10-06-next`; re-read the head before quoting
  (`git fetch --prune; gh pr view <N> --json headRefOid`). Built in a scratchpad worktree
  (`.../scratchpad/integ`); the session worktree `session-handover-decisions-de63f6` holds `derived/` and the
  `build/` of this install.
- Delete when convenient: `worktree-agent-a51bcd8...`, `-a3523e3...`, `-aa6cbb0...`, `-a5ab351...`, `-a4e0aba...` (all
  merged into the chunk-race branch).

## 2. Where it stopped
- **Installed to staging** (prepare 201/201 at 24ac441, install clean, server's OLD `bank.json` restored by hand:
  install_check 1 problem by design). Applied `run --only R17M --no-reload`: 39 stalls, 0 problems. Snapshot before:
  `cobblers-staging/snapshot-2026-10-08-before-install`. Probes: STATE "Latest install".
- **Staging RUNNING for the owner** in the Terminal panel tab "staging server", 12G, max-tick-time 60000. Lock released.
- **Stale steps NOT applied** (`reapply.py stale`): CHANGED R9SX, R9SF, R9MD, R9MB, R16C, R17A, R17L; never run clean
  R1S, R9JT. The owner's install list named only R17M; the rest wait on the owner's call.
- **The chunk-race fix is NOT installed.** Next install: prepare, install (hold the bank), then each changed step
  twice to prove a re-run reads its count and does not double: R18F, R18CW, R9Z, R9M, R1, R1S, R9S, R18AF, R14, R18DT.

## 3. Waiting on the owner
- EXP-059 steps 7-17 on staging (grant `cobblers:flag/champion_cleared` first); now on the new build.
- Sigils: Q20 (Night Shift's free first run) and Q23 (ungated recipes) were NOT accepted as recommended: what instead?
- The ten stale steps above: apply or not.
- Carried: EXP-061/062/064-068 in game; Brock; Lootr's two-player cases; the live Nether override; the 19 dungeon OPENs.

## 4. Do not rediscover
- A new worktree has no `derived/` or `build/`: prepare needs `derived/` (the Rift sculpt cannot be rebuilt). This
  session copied it from `wave-a-builds-integration-98eb36` with robocopy (~200 MB, seconds).
- `install` needs `--cobbleverse-dp`; the upstream zip is
  `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/datapacks/COBBLEVERSE-DP-v31.zip`.
- The lock file's owner line must read `owner: <id>` (tools/runtime_guard.py), matching `COBBLERS_LOCK_OWNER`.
- `presence_audit` needs a running server and takes over ten minutes: run it in the background, never under a timeout.
- `open(p, "w").write(f(p))` truncates p before f reads it: this session emptied `chunk_look_audit.py` that way during
  a merge (caught by the tests, restored c73b41e).
- Three builders each extended `chunk_look.py`; `need_all` and `all_shown` were the same option (kept `all_shown`).
- `data/gulch_mine.json` offers 61 Cutter stones against tests expecting 60 (since 41461a7): pre-existing.

## 5. Cost
`python tools/session_cost.py`: this session 3.9M weighted at the measure (context 279k: start fresh); agents 8.4M.
