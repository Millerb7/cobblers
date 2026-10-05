# Handover: Wave 1 and the 2026-10-05/06 overnight build (session 595493c5)

A cold session reads CLAUDE.md, `docs/STATE.md`, this file, `docs/MORNING_REPORT_2026-10-06.md` and
`docs/OVERNIGHT_REVIEW_2026-10-06.md`, and nothing else, before it starts.

## 1. The branch
- **`build/2026-10-06-next`** on origin (no PR yet), stacked on `build/2026-10-05-p0` (draft PR
  [Millerb7/cobblers#119](https://github.com/Millerb7/cobblers/pull/119), frozen). Worked from worktree
  `wave-1-launch-prep-3d2fa0`, local branch `wave1-2026-10-06`, pushed with `git push origin HEAD:build/2026-10-06-next`
  (the branch itself is checked out in the old `consolidate-parallel-sessions-b6b9d7` worktree, untouched).
  Re-read the head before quoting: `git fetch --prune; git rev-parse origin/build/2026-10-06-next`.
- Next: open ONE draft PR for it against main (memory: one big PR per batch) after #119 merges, or stacked on #119.

## 2. Where it stopped
- **Staging is DOWN: the detached boot (java pid 50764, 05:55) was killed when the tool's background task hit its 2-hour limit; its log ends at 06:21 with no shutdown line (review N53). The apply's own save-all and the world's autosaves precede it; whatever changed after the last autosave is lost. The coordination lock is released.** max-tick-time is 60000.
- Everything built tonight is applied to staging and read back (the morning report's table). Nothing is half-done.
- `derived/` and `build/` in this worktree are current for head 541a7d8 + the docs commits (prepare stamp
  58322c025cddfef1); any data/ or tools/ commit needs a full prepare (~27 min) before install. Run prepare with
  `COBBLERS_SERVER_ROOT=C:/Users/wnd/Documents/github/cobblers-server` set (sea_drift_audit needs it, N40).
- `reapply.py run` refuses unless max-tick-time is -1: stop, set -1, boot, run, stop, restore 60000, boot.

## 3. Waits on the owner
The morning report's "Waiting on you" list (10 items: N8 badgeless walk to the finale; N39 stone gate; the Displaced
City market held; obtainability proposals; route species growth; Challenge mode's two leaders; summit loot;
waystone locations; Kyogre 1 and 8; in-game checks).

## 4. Do not rediscover
- The ten beats and the Rift finale were ALREADY wired (N12, finale builder): the work was evidence displays and
  wayfinding lines, not wiring.
- No "stone shard" exists in any jar (N21); TMs are uncraftable from renewables (N22).
- `ambient_idle.py compose` (the authors' check) does not replay the built packs: 10 of 13 towns passed it and failed
  the build (N43). Re-site against `build` (55 s, names every refused town since tonight).
- `ambient.Site` marks plaza pieces taken; `markets.py` opts out (`avoid_plaza_pieces`) because keepers stand on their
  stall pieces (N38).
- The independent idle audit was taught the composition by the orchestrator (N48): a second reader must check it.
- The squares audit and the markets design disagree on gating evolution stones (N39): stones are KNOWN-ungated.
- Mega-field dens hold 2-3 Megas each in staging (N50, P1): not caused tonight, cause not found.
- `git reset --hard` on a worktree branch is refused by the auto-mode classifier; use `git switch -c ... --track`.

## 5. Cost
`python tools/session_cost.py`: 424 turns, 20.6M weighted for the main session (context 682k at hand-over, far past
the line), agents 37.2M weighted (20 agents: 3 research, 8 builders, 2 town authors, 1 re-siter, 5 auditors/reviewers,
1 generator).
