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

## 3. Next: the overnight brief of 2026-10-10 (the owner, verbatim decisions; run in session bacb34ed because no tool here can start a fresh session)
1. **Nether override, FIRST (live defect):** stop Blaine-gym copies and Moltres altars generating in the Nether (and the
   End copies, STATE "Generated gym copies"); re-measure the copy count; prove on a throwaway world; nobody may reach a
   second Blaine or an unearned Moltres.
2. **Entei boss (option B, `docs/mechanics/NETHER_DUNGEON_SCOPE.md`):** each player fights their own copy; losing blacks
   you out; entry costs MATERIALS (Challenge players pay the same); first clear catchable, later clears give items; no
   Arceus plates; Mewtwo stays on the fossil route; Entei first, Heatran after. Experiments first; check every species
   against the 1.8.0 jar; the two-player case waits for a second account (never faked).
3. **Arena payout hole:** settle whether CobbleDollars pays on the arena's NPC wins; if it pays, cap it.
4. **Economy overhaul:** design then build: trainer income covers the fights; TMs, Mega stones, held items and training
   from materials; farm products pay early on a declining price, AFK food capped or excluded; a REFILLABLE MINING CAVE
   (stone-face reset mechanism: where, shared or per-player, yield, netherite too?); the Challenge voucher's real number
   from the ladder; the paid services ($500 to raise one Pokemon to the cap; EV/IV the same) after researching the
   level-setting command.
5. **Queue:** the eight units the brief lists LANDED on 2026-10-09 (`docs/REPORT_2026-10-09.md`); left: the P1s
   (Victory Road skippable on the surface and z4 over the League are owner decisions, N132; the Champion's floor trigger is
   in-game only) and the four blocked trainer seats (explain them).
Blocked on the owner: Brock (holds the 12), Lootr's two-player cases, the in-game checks.

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
