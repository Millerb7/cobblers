# Handover: session 74260a, ending 2026-10-11 late

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-09-dungeon-playtest` in worktree `.claude/worktrees/night-shift-engine-gym-9b76f2`, LOCAL ONLY (no PR;
one big draft PR for the batch is owed). Re-read the head (`git rev-parse HEAD`; c7243b4 plus this file). The three
agent branches (guide, vaults, one_of generator) are merged; 335 merged worktrees and 460 merged branches were removed
(135 worktrees and 146 branches remain: dirty, locked or unmerged ones kept on purpose).

## 2. Where it stopped
- **Staging is UP; the owner is playing the Street, the Patriarch and Ash Bell.** Installed: prepare 229/229 at
  e18ec16. NOT installed: the vaults, the guide, the NPC plant clearing (all merged after it). The lock is released.
- **Verified snapshot:** `D:\cobblers-snapshots\staging-2026-10-11-after-dungeons` (sha256-matched). Snapshots live on D:.
- **Next (after the owner reports back; nothing new is authored before that):**
  1. `python tools/dungeon_independent_audit.py` (33 min) on the merged vaults; `python tools/player_site.py` (every
     page's nav gets the guide); confirm the new ball and held-item ids in the Cobblemon 1.8.0 jar; declare or read
     `data/frostpeak_keep_quest.json` (the one failing site test, older than this work).
  2. Next install: snapshot to D: first; env `COBBLERS_SERVER_LOCK`, `COBBLERS_LOCK_OWNER`,
     `COBBLERS_SERVER_ROOT=C:/Users/wnd/Documents/github/cobblers-server`; full prepare (~51 min); RCON stop; hold
     `config/cobbledollars/bank.json`; install with `--cobbleverse-dp C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/datapacks/COBBLEVERSE-DP-v31.zip`
    ; restore the bank; `max-tick-time=-1`; **boot at 24G**;
     `run --only R16DG,R17N,R17,R18CP --no-reload` (the vaults are in the shells; the npc steps clear plants); watchdog
     60000; restart at 12G; check twice.

## 3. Waiting on the owner
- Their play report on the three dungeons (bands via `scoreboard players set <player> dg.ptband <n>`, tag
  `cobblers.dg_playtest`).
- The draw design, D1-D5 in `docs/mechanics/DUNGEON_DRAW.md`.
- Deleting the old worlds (they run the commands themselves; listed in STATE "Snapshots go to D:").

## 4. Do not rediscover
- R16DG at 13 dungeons OOMs 12G (memory: apply-heap-24g). The independent audit takes ~33 min.
- The "solid block at its feet" verify fails on plants; the npc action now clears them (`stand_clear_commands`).
- The guide reads vault stacks; any new stack form must be taught to `tools/player_guide_dungeons.py` `stack_text`.
- New Compact NPCs collided with older placements twice; prepare's `markets:audit` and `ambient_idle:build` catch it.

## 5. Cost
`python tools/session_cost.py`: far past the hand-over line at the end (the owner chose to continue here).
