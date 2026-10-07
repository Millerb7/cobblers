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

## 2. Where it stopped (overnight 2026-10-08/09)
- The overnight brief is built, audited, applied to staging and read back after a restart: `docs/MORNING_REPORT_2026-10-09.md`.
  Prepare complete at the head before the docs commits (187 jobs). Staging stopped with RCON `stop`, saved, lock
  released, `max-tick-time` 60000, no Lootr in `mods/` (jar and generated config kept in
  `C:/Users/wnd/Documents/cobblers-local/mods-pending/`).
- Snapshots: `cobblers-staging/snapshot-2026-10-08-before-overnight` (before tonight), `snapshot-2026-10-07-before-wave-a`.
  Disposable: `cobblers-staging/lootr-exp-2026-10-08` (Lootr converted containers in it; do not boot it without Lootr
  expecting them), `staging-2026-10-01.oom-2026-10-07` (the OOM-damaged copy).
- This worktree has a full `derived/` and a complete `build/`.

## 3. Next
1. **Owner: Brock in game**, then the 12 bosses, after fixing the two traps (N115) and deciding Agatha/Lance (N116).
2. **Owner: TMs at counters** (N126/N127): commit 2833317's `data/markets.json` part holds the 41 lines; re-apply it
   once the gate is chosen, then prepare + R17M. Arena trophies by barter (N125).
3. Griseous Core needs a sweep site to declare extra caches (N118); the Pallet waypoint needs its marker record (N120);
   the gulch cove town and the Deep's city have no ambient (N119); walk 2 items 7-8 (N121).
4. Lootr: the two-player cases with the owner, on a disposable copy; ADR-007 stays Proposed.
5. Owner questions left in each design file's "Decisions taken 2026-10-08 (overnight)" section.

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
