# Handover: session 74260a, ending 2026-10-12 morning (far past the context line)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts. The owner's
summary: `docs/MORNING_REPORT_2026-10-12.md`.

## 1. Branch
`build/2026-10-12-overnight` in worktree `.claude/worktrees/night-shift-engine-gym-9b76f2`, LOCAL ONLY, no PR (re-read
the head). It sits on PR #134 (`build/2026-10-12-rift-guide`, draft, head 88bdde1, the guide book and themed rip
ground). #133 (the dungeon batch) is MERGED to main at 3dc7c00. Owed: one draft PR for the overnight branch
(after or with #134).

## 2. Where it stopped
- **Staging is UP at 20G** (terminal tab "staging server 20G"), installed from prepare 236/236 at 09ff917 and
  applied (STATE "Latest install (2026-10-12 overnight)"). The lock is released.
- **Merged AFTER that install (not in the world):** the paradox pools (worktree-agent-af27ca7b40c6cb147). Next
  install: prepare, then `run --only R16DG` at **24G** (and the shells' entity chain at 24G), restart at 20G.
- **Owed checks:** `python tools/npc_seats.py verify` (the 12G server died under it; never ran at 20G);
  `presence_audit` for caves, maze_shrines, gatehouse.

## 3. Waiting on the owner
The morning report's "Decisions waiting on you" (Heatran/Yveltal, the defaults taken, Tapu Bulu's site, the world
tree, C4, the gulch gate), plus DUNGEON_DRAW.md D1-D5.

## 4. Do not rediscover
- The play heap is 20G: the idle live set is 12.4 GB (jcmd GC.run, GC.heap_info). A server that stops answering RCON
  with CPU pinned and a silent latest.log is out of memory; the OOM lines are only in the console tab.
- R16DG's entity read-back can under-count on a loaded server (154, 151) and over-count after blind acts (158); a
  re-run at 24G settles it at 156.
- Prepare's late failures tonight: stale nuzlocke_zones after new encounter tables; the caves' own Habitat Blocks
  counted as another pack's writes (fixed in caves.py and, independently, caves_audit.py).
- Merges between agent branches conflict on data/dungeon_prize_roster.json and data/world_probes.json; resolve the
  probes structurally (load both, add the new place group), never by hand.

## 5. Cost
`python tools/session_cost.py`: this session ran far past the hand-over line at the owner's request; its agents
tonight were ten builders and two designers.
