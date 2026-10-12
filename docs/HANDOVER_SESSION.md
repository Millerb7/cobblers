# Handover: session 74260a (2026-10-11 evening), IN PROGRESS

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-09-dungeon-playtest` in worktree `.claude/worktrees/night-shift-engine-gym-9b76f2`, LOCAL ONLY (no PR;
one big draft PR for the batch is owed). Re-read the head with `git rev-parse HEAD` (e18ec16 when this was written).
The integrator branch `worktree-agent-a957ab31010595219` is fully merged (final head 72a920a; it stopped at 15:27).

## 2. Where it stopped
- Done: the integrator merged; Zero Dig cut (fda6fa6); the Compact's "evil" framing removed (fda6fa6); the draw
  design written, `docs/mechanics/DUNGEON_DRAW.md` (f2bcd5d, design only, waiting on the owner); two Compact seat
  collisions fixed that prepare caught (4ff9b35 Nia at Viltri, e18ec16 the CP-12 east guard at Cinderlee).
- Running when written: the full `reapply.py prepare` at e18ec16. Then: RCON stop staging (the owner approved,
  2026-10-11), hold `config/cobbledollars/bank.json`, install, restore the bank, `max-tick-time=-1`, boot at 12G in
  the terminal panel, `run --only R16DG,R16DR,R9ST,R18CP,R17N,R17 --no-reload`, watchdog 60000, restart, check the
  process twice, release the lock.
- **The server lock is HELD** by "Claude Code session 74260a" at `C:\Users\wnd\Documents\github\.cobblers-server-agent.lock`.
- Env a prepare needs in this shell: `COBBLERS_SERVER_LOCK` (lock path), `COBBLERS_LOCK_OWNER` (its owner line), and
  `COBBLERS_SERVER_ROOT=C:/Users/wnd/Documents/github/cobblers-server` (sea_drift_audit reads Cobblemon's jar
  through it; unset, the audit fails on Clauncher).

## 3. Waiting on the owner
- The draw design: D1-D5 in `docs/mechanics/DUNGEON_DRAW.md` section 4.
- Play the Street, the Patriarch, Ash Bell first (`scoreboard players set <player> dg.ptband <n>`, tag
  `cobblers.dg_playtest`).

## 4. Do not rediscover
- The independent audit takes about 33 min on 13 dungeons (2014 s measured), not 2.
- `tests/test_dungeon_probes.py::test_staging_only_never_installed` fails in an agent worktree only because
  `R.steps()` needs a prepared build/; not a defect.
- New Compact NPCs were authored without the markets and ambient clearance checks; prepare's `markets:audit` and
  `ambient_idle:build` are where such collisions surface.

## 5. Cost
`python tools/session_cost.py`: 247k context, 2.9M weighted at 115 turns when written.
