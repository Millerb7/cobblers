# Handover: session 2312d085, 2026-10-16 (launch and first live fixes; far past the context line)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-16-gyms` in worktree `.claude/worktrees/mods-182` (holds `derived/`, `build/`, hydrated kits). Pushed with
a draft PR (re-read with `gh pr list --head build/2026-10-16-gyms`). It stacks on `build/2026-10-15-launch-fixes`
(PR #141, draft, head d1badbcb, FROZEN: do not push to it). PR #139 and #140 are merged. Re-read heads after
`git fetch --prune` before quoting them: the owner merges while sessions work.

## 2. Where it stopped
- **LIVE is UP** at 12G, started with `server/scripts/start-live.ps1` (hidden window, console to
  `logs/console-*.log`; stop with RCON `stop`). Last install 2026-10-16 10:56: prepare 242/242, install_check 0,
  R17L 12 bosses 0 problems, watchdog back at max-tick-time=60000 (a `reapply.py run` needs -1 while it runs).
- The coordination lock is held by `claude-launch-2026-10-15d`
  (`C:\Users\wnd\Documents\github\.cobblers-server-agent.lock`). Release it when no session is working the server.
- Whitelist: the owner's two names (in the server's whitelist only, never in the repo).
- The client files for friends: `C:\Users\wnd\Documents\cobblers-client\` (the .mrpack, sha1 adb0bce6, and the
  subset zip, sha1 b43635df, which now carries the NPC looks and the rip oval). Steps: `docs/launch/CLIENT_PACK.md`.

## 3. Waiting on the owner
- A cast test: fishing in a few areas (Lake Viltri, West Shore, the Windward shallows); before 2026-10-16 no area
  hooked a Pokemon.
- Dungeon fishing: deepen one canal slot's pool by RCON with the owner present and cast (STATE has the coordinates).
- Lance's single leader (needs the challenge audit's R:summon rule widened: reviewer's call); the Agatha/Bruno/Lorelei
  floor overlaps (open decision).
- More NPC looks (only Brock's witness has one), the Trading Post as a CobbleDollars bank screen (integer per-item
  prices block cheap bulk goods), near-player rip weighting (not built), faster elder-tree refill (offered, not done).

## 4. Do not rediscover
- rctapi 0.16.2 Text reads only `literal`/`translatable`; a `text` key is blank, and under speech bubbles a crash
  (`route_trainers.rct_line`). rctmod speech bubbles stay off.
- A Cobblemon NPC look = a client variation (`assets/<ns>/bedrock/npcs/variations/`) + the class
  `resourceIdentifier`; `ForcedResourceIdentifier` on the entity overrides it live. No look in the client = the
  substitute doll.
- Lootr chests naming a missing loot table: Pallet's eight were set to `minecraft:empty` on live only; the
  `place_town.py` source fix is open.
- The 2026-10-15 watchdog stop was a blocked console write, not a datapack (no tick function is slow).
- RCON `execute if block` in an unloaded chunk fails: forceload around probes, then remove.
- Shell heredocs turn `\\x..` escapes into raw bytes; write binary literals without escapes (bytes([...])).
- Strip refuses while ANY java runs, the owner's client included.

## 5. Cost
`python tools/session_cost.py`. This session ran far past the hand-over line at the owner's request; start fresh.
