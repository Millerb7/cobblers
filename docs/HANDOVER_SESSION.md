# Handover: session bacb34ed, 2026-10-08 (end of day)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts. The review list is
`docs/OVERNIGHT_REVIEW_2026-10-06.md` (N140-N165 are the last days').

## 1. The branches
- **`build/2026-10-06-next`** at `c9688fe` on origin, no PR yet (memory: one big PR per batch, against main). Worked
  from worktree `wave-a-builds-integration-98eb36` (local `claude/wave-a-builds-integration-98eb36`), pushed with
  `git push origin HEAD:build/2026-10-06-next`. Re-read first: `git fetch --prune; git rev-parse origin/build/2026-10-06-next`.
- **Player site PRs** #120-#126 MERGED; [Millerb7/cobblers#127](https://github.com/Millerb7/cobblers/pull/127) (Flutter
  Mane line) open draft. The site's source of truth is `tools/player_site.py` on the batch branch; each site PR copies
  `docs/player/` onto a fresh branch off main from `../site-pr-2026-10-08`. Since #127 the batch also changed the
  starter page (Smeargle old-shape stages), so a new site PR is owed after #127 merges.

## 2. Where it stopped
- **Staging is RUNNING for the owner (process 32372), no lock held.** It carries the build of prepare 381c568b
  (installed and applied 2026-10-08 afternoon: `run --only R9O,R9Z,R16Q,R14,R17M,R17TS,R17`, R17M re-run twice for the
  merchant race). The server's `cobbledollars/bank.json` is deliberately the OLD one (install_check: 1 problem by design;
  the new bank waits for the Produce Buyer to be seen working).
- **EXP-059 (Entei room):** RCON steps 1-6 PASSED (results in its README). Steps 7-17 wait for the owner in game
  (grant `cobblers:flag/champion_cleared` first). The exit arch's interaction box is doubled (race).
- **Merged AFTER that install, NOT in staging:** Smeargle old-shape stages (330/430 in 74/79/60/79/60/98, final 476 in
  92/68/78/68/78/92, 20/35) with the `tm:uturn` addition; the TM gate's four calls (Inferno/Zap Cannon 5, Meteor
  Assault/Prismatic Laser/Roar of Time 7, Return/Frustration 7, chain raises) and Spore at 5 (group 18); the simulator
  move-source check (`tools/sim_move_sources.py`); the R17M race fix (a35a7b6); the independent review of the TM and
  Smeargle tests. Next install: prepare (~45-50 min; `--server-dir`, `COBBLERS_SERVER_ROOT`, lock env), install (hold
  the bank: back up the server's bank.json first and restore it after), boot 16G tick -1, apply R17M (and R14/R17 if
  their inputs changed), restore tick 60000, read back.

## 3. Waiting on the owner
- EXP-059 steps 7-17 on staging; EXP-061/062/064/065/066/067/068 in game; Brock; Lootr's two-player cases.
- Calls: Glare to 5 (Spore at 5 now opens a sure sleep before a sure paralysis); Frustration at 7 (recommended);
  fix the other forceload-then-act steps (Coldwater, Frostpeak first; list in N155); the dungeon sigil questions
  Q20-Q23 (`docs/mechanics/DUNGEONS.md` 7.4); the 19 dungeon questions marked OPEN there.
- The live Nether override (copy `build/datapacks/cobblers_dimension_overrides` into the live world's datapacks, server
  stopped, before anyone enters the Nether or runs /locate). The AllTheMons subset zip goes to players directly
  (`modpack/config/README.md`).

## 4. Do not rediscover
- Any `data/` or `tools/` change after a prepare makes the whole prepare stale; merge agents only AFTER install+apply.
- Prepare needs `COBBLERS_SERVER_ROOT` as well as the lock env.
- Agents often misreport their branch as `claude/wave-a-builds-integration-98eb36`: verify by sha (`git branch --contains`).
- Two units can each add a contract with the same number (C19, C22 today): resolve by renumbering, never deleting.
- A six-number list in any data file reads as an overworld box to the audits' generic box finders (the Nether gate's
  sweep volume broke desert_wreck_audit; now corner+size).
- `/locate` saves a structure start; the dimension override cannot remove one.
- Timed dungeons are DESIGNED (`docs/mechanics/DUNGEONS.md`, ADR-008 Proposed; ~35M to the Night Shift); the den
  cannot be built until the dungeon run tag exists (STATE).
- Sketch is UNLIMITED for now (`superseded_sketch_cap`); its tests and C22 skip until the cap returns.

## 5. Cost
`python tools/session_cost.py`: this session 66.6M weighted over 1,118 turns (context 921k at hand-over: start fresh).
