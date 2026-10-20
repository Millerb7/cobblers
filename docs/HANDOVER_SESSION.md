# Handover: sessions 2312d085 / 7698338d, ended 2026-10-20

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-20-integration` (worktree `.claude/worktrees/mods-182`, which holds `derived/`, `build/` and kits), draft
PR #150, which carries #149. Open PRs also: #148 (client bundle tool). Re-read with `git fetch --prune` and `gh pr list`.

## 2. Where it stopped
- LIVE is UP at 12G, started with `server/scripts/start-live.ps1` (hidden, console to logs/console-*.log; stop by RCON
  `stop`). Last install 2026-10-20 17:19: prepare 242/242 at 31357284, R9DR applied (Newmoon at y518; the old box read
  back empty by hand), stripped, install_check 0. Whitelist OFF, max-players 20. No lock held.
- Friends' files: `C:/Users/wnd/Documents/cobblers-client/` (the bundle .mrpack, sha1 d289833c, and the subset zip,
  sha1 b93e7563). The server address lives only in `C:/Users/wnd/Documents/cobblers-local/server-address.txt`.

## 3. Waiting on the owner
- Leaf decay (accept, mark leaves persistent, or a mod). Lance's single leader. Elder-tree refill speed.
- In game, not yet seen: overworld fishing per area; dungeon item catches and the "Caught: +N points" line; the 98 NPC
  looks (chosen from names, not by eye); Distant Horizons LODs arriving while a player moves.

## 4. Do not rediscover
- This world's build limit is y575 (cobblers_height: min -64, height 640), not y319.
- `/dh pregen` ends at radius 2 with 0 cps even with PRE_EXISTING_ONLY, generation 4096 and a held RCON connection;
  PregenManager reads the level's GeneratedFullDataSourceProvider. Not solved.
- R9DR's read-back says "old seat probes 0 of 0": its own check cannot see the old seat.
- `reapply.py run` needs max-tick-time=-1 while it runs; strip refuses while ANY java runs (the owner's client too).
- Shell heredocs collapse `\` escapes into raw bytes and Windows paths break Python strings: use the Edit tool.
- The dialogue compiler closes only a terminal line (next is itself).
- Steve NPCs left: dungeon bosses, stand trainers and egg vendors (tools/dungeon*.py), arena classes.

## 5. Cost
`python tools/session_cost.py`. Both sessions ran long; start fresh.
