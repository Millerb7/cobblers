# Handover: session 2312d085, 2026-10-15 (launch; far past the context line at the owner's request)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-14-launch` (worktree `.claude/worktrees/mods-182`, which holds `derived/`, `build/` and hydrated
kits), merged to main through its PR at the end of this session (re-read: `git fetch --prune`; `gh pr list --state all
--head build/2026-10-14-launch`). Everything from #137 and #138 is on main; job D (`build/2026-10-14-rips-spawn`) is
merged into the launch branch.

## 2. Where it stopped
- **The LIVE server is UP** in the Terminal panel tab "LIVE server 12G (voucher)" (12G, watchdog 60000, whitelist on with
  the old server's two names), restarted 2026-10-15 20:26 with the voucher build (draft PR #140, branch
  `build/2026-10-15-voucher`). The coordination lock is held by `claude-launch-2026-10-15d` for the owner's in-game
  smoke test: release it (`C:\Users\wnd\Documents\github\.cobblers-server-agent.lock`) once the owner
  has the server, or keep it while a session works on it.
- Rollback: `docs/launch/ROLLBACK.md` (the retired world, the D: snapshots).
- Launch docs: `docs/launch/` (HOSTING, CLIENT_PACK, KNOWN_ISSUES, ROLLBACK); the client pack
  `build/client/cobblers-client-0.1.0.mrpack` (sha1 72244e00) and the AllTheMons subset zip.
- **Not clean, the owner's call:** the offline audit (town audits predate the gym overhaul; light-0 cells; the Deep city
  2 blocks; two trails) and presence 973/1,062 (Mega dens 31 probes look inverted; dens 29 short; Night Shift slots 12).
  All in `docs/MORNING_REPORT_2026-10-14.md`.

## 3. Waiting on the owner
- Launch: the network route (HOSTING.md), `whitelist add` for each friend, the client pack to friends.
- The audit verdict above; Challenge's 77 route/junior fights (not redesigned); the voucher's eight gym-clear grants (Oak's $4,000 is built, not seen in game); Cobbreeding's new 5% alpha chance.
- Later: a VPS (24-32 GB RAM) and moving the tooling to Linux.

## 4. Do not rediscover
- CobbleDollars Beta-6.1: `default_bank.json` (bare list, string prices); a merchant's shop lives at
  `CobbleDollars.Shop`; a summon's old CobbleMerchantShop migrates but gets an EMPTY inline bank; a registry bank
  (`{type:"registry",bank:"cobbledollars:default"}`) sticks only when set AFTER the summon (`traders.bank_line`).
- Cobblemon 1.8.2 ships Showdown zipped (`battle_sim.showdown_read`); its type chart adds Stellar; only Venonat,
  Venomoth (tm:megadrain) and Spinda (tm:teeterdance) changed learnsets. `find_jar` prefers the 1.8.0 snapshot jar.
- Zamega 1.8.2 moved five stones into Mega Showdown; three Z-A stones have no recipe (the Cutters still trade them).
- Distant Horizons v5 dropped `enableServerGeneration`; `maxGenerationRequestDistance = 0` replaces it.
- Every tool change makes prepare stale, and install, run and strip all refuse until a full prepare (about 46 min).
  Strip insists on the world path the last install used.
- Lootr: loot-table containers convert on chunk load; `lootr custom-chest` from a function works (EXP-056 C2).

## 5. Cost
`python tools/session_cost.py`: this session ran far past the hand-over line at the owner's request.
