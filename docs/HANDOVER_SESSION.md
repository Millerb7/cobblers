# Handover: Wave A (session bacb34ed, 2026-10-08)

A cold session reads CLAUDE.md, `docs/STATE.md`, this file and `docs/MORNING_REPORT_2026-10-08.md`, and nothing else,
before it starts. The review list is `docs/OVERNIGHT_REVIEW_2026-10-06.md` (N95-N113 are Wave A's).

## 1. The branch
- **`build/2026-10-06-next`** on origin, no PR yet, stacked on `build/2026-10-05-p0` (draft PR
  [Millerb7/cobblers#119](https://github.com/Millerb7/cobblers/pull/119), frozen). Wave A worked from worktree
  `wave-a-builds-integration-98eb36` (local branch `claude/wave-a-builds-integration-98eb36`) and pushed with
  `git push origin HEAD:build/2026-10-06-next`; the branch is also checked out (behind) in worktree
  `consolidate-parallel-sessions-b6b9d7`, so `git switch` to it refuses there. Re-read the head before quoting:
  `git fetch --prune; git rev-parse origin/build/2026-10-06-next`.
- Next: ONE draft PR for it against main (memory: one big PR per batch) after #119 merges, or stacked on #119.

## 2. Where it stopped (2026-10-09, day)
- Today's build is applied and read back: `docs/REPORT_2026-10-09.md`. Staging stopped with RCON `stop`, saved, lock
  released, `max-tick-time` 60000. Snapshot before today: `cobblers-staging/snapshot-2026-10-09-before-day`.
- This worktree has a full `derived/` and a complete `build/` (prepare at the head before the docs commits).

## 3. Next
1. **Owner: Brock in game** -> then fix `P1:move_orphan` (N130) and decide Agatha/Bruno and Bruno/Lorelei (N131)
   before the League rolls out; the other 7 gyms' templates need nothing more than Misty's/the League's measured data.
2. **Owner decisions** listed in the report (N128 the Master Ball floor, N138 Link Cable/Upgrade, N132 z4, N129 prices,
   the 12 design choices, U7).
3. **Land the coast fringe (N139)**: store its cells in a form no siting scanner reads as a point, then re-audit.
4. The level-cap check's gauntlet gap (N133); U6 mint-seed barter (research done: `docs/research/notes/mint-seeds.md`).
5. The guides: regenerate with `python tools/player_guide_battles.py` and `python tools/player_guide_map.py`
   after data changes; tests for both are a test-author's job (none yet).

## 4. Do not rediscover
- `reapply.py prepare` needs `--server-dir` and the lock env (`COBBLERS_SERVER_LOCK`, `COBBLERS_LOCK_OWNER` equal to
  the lock file's `owner:` line, `COBBLERS_SERVER_ROOT`). The lock file must carry an `owner: <id>` line or
  `runtime_guard` refuses.
- Copying `derived/` into a worktree: the folder already exists (tracked README), so `cp -r src ./derived` nests it;
  copy the contents.
- A 12G staging server ran out of memory in reapply's `/reload` (N111); `--no-reload` straight after a boot works.
- Ctrl-C does not reliably save this server (N112): stop with RCON `stop`.
- rctmod saves `InBattle` as `0b` on a standing trainer (measured on `gym1_junior_01`).
- `direct_trades.rcon_checks()`'s `data get` selectors are malformed (N113); read with `@e[...,limit=1]`, after
  waiting ~5 s for a forceloaded chunk's entities.
- A1's retire was fixed by the integrator and the auditor's test edited to match (N95): a re-audit by another agent is
  owed before the 12-boss rollout.

## 5. Cost
`python tools/session_cost.py`: this session ~7.5M weighted (context ~400k at hand-over, average ~290k); agents 15.8M
across 14 (5 design, 4 builders, 1 ADR, 4 audits/checks); about 23-24M of the ~30M approved.
