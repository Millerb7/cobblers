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

## 2. Where it stopped
- Wave A is built, audited, installed and applied to staging, and read back from the world before and after a
  restart (the morning report's table). Prepare is complete at head 9827099 (187 jobs; later commits are docs only).
- **Staging**: stopped with RCON `stop` at the end of the session, lock released (see section 5 of the morning report
  for the boot history). Boot: terminal panel, `-Xmx16G` for unattended runs (12G cannot `/reload`, N111), universe
  flags; `max-tick-time` is back at 60000.
- The worktree `wave-a-builds-integration-98eb36` has a full `derived/` (copied from `wave-1-launch-prep-3d2fa0`) and a
  complete `build/`: use it for the next install.
- Agent worktrees of the night (`agent-a1bee230…`, `agent-a7097f3a…`, `agent-a33db429…`, `agent-ad8e5716…` and the
  four auditors') are all merged; they can be cleaned up.

## 3. The owner's answers (2026-10-08) and the next job
Recorded in STATE "What is decided" ("The owner's answers to the Wave A morning report"). The next session's work, in
order, each with an independent audit before any apply:
1. **A fresh independent audit of A1** (another agent, opus, escalation rule 1): the integrator fixed the retire and
   edited `tests/test_challenge_mode_audit.py` to match (N95). Then measure Misty's and the League's
   `single_leader.restore` from their templates and the League's `normal_at` (N97). Roll out the 12 only after the
   owner's Brock check passes.
2. **Pricing (A3 follow-up):** Pacifidlog reachable at 6 badges, not 0; early-town status heals re-priced as a
   convenience (not 9,500). Re-run `economy_audit`; R14 at apply.
3. **Barter lines (A4 follow-up):** re-price so the exchange is an alternative path, not a ~5.8x bypass of
   Northlight's $27,000 Master Ball; place the approved lines at **Northlight's counter** (the one trading centre);
   fix `rcon_checks()`'s selectors (N113). The economy audit with barter edges is in place.
4. **Lootr:** the owner gave permission to download it (2026-10-08). Install on staging only, run EXP-056 (mind the
   shared `mods/` hazard in ADR-007: the jar out of `mods/` before any live boot); ADR-007 stays Proposed until seen
   working.
5. Gym 2 keeps two juniors (accepted). The finale gate stays on all eight badges (as built).
6. The owner does the five in-game checks, Brock first; Wave B waits on the owner's read of A6-A10.
Still unsourced: "THE NURSE: 30 minutes", "237 ambient across 26 settlements", "the four P2s".

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
