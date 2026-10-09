# Handover: session ce7100f5, the night of 2026-10-08/09

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts. The owner's report:
`docs/MORNING_REPORT_2026-10-09-NIGHT.md` (its section 5 is tonight's review list).

## 1. The branches
- **`claude/night-shift-engine-gym-9b76f2`** (this worktree), on main `43efdad` + #131 (`8df1ca3`, docs, still an open PR:
  merge #131 first or let this branch carry it). Holds: EXP-059 parked, E1, the probe pack and its results, the
  engine core, the eight gym arenas, the audits and their fixes, the designs, STATE and this handover. Re-read the head
  before quoting it (`git rev-parse HEAD`). **No PR opened yet**: one draft PR for the batch is the next step
  (memory: one big PR per batch).
- **The world brief, MERGED into this branch (the merges and fixes are its last commits); the agent branches it came from** (`worktree-agent-<id>`, each one commit or two on `0b3a8b2`/
  `1bcb087`): swamp nest a775e90e671b31012 `3af7466`; Drowned Quarry ac7dfdcff287b1624 `bd39246`; Tilpey spawns
  a033d07c5517417a9 `a9aa8f5`; Fungal Isle ac9d376819faa18f3 `f2f4ea4`; Sundown Watch ab7d2c93d44329266 `49a3580`;
  Wardenhold af825b9f9e7b000df `5a52d69`; ice lodge a54e72cf1167a8edc `7a669dc`; economy sim a8fe0288bd86a9c7f
  `36cb6bd`; Crownbreaker aac996cb89c97f615 `1e99d60`; Undertow a6f9e8dcc018e1c00 `aaa9a82`; Gull Rock
  a6574158502118a45 `01f9b13`; Route 5 a7b3215c5d44b18d7 `2c90346`; Route 4 aef58650877204df6 `2a48d77`; the C3 place
  a81e02708207b16e7 `7344e73`. Audits: water a11b8677bd0e5af4f `9052c96`, land afb9e845577a94967 `70c6cf5`, both merged.

## 2. Where it stopped
- **Staging RUNNING for the owner**, 12G, watchdog 60000, Terminal panel tab "staging server". Lock released.
  Installed from prepare 203/203 at `0b3a8b2`; R16GA, R16DG, R16DR applied (0 problems), restarted, read back (8 of 8
  arena spawners; presence extra 386/393). The world brief is NOT installed.
- **Next, as commands:** the world brief is merged, validated (0 errors, 0 faults) and audited (except the Long Count);
  decide Gull Rock's wake with the owner; then prepare, install (hold the bank: copy `config/cobbledollars/bank.json` before,
  restore after), boot with `max-tick-time=-1`, `run --only <the new steps> --no-reload`, restore 60000, restart, read back.
  New steps: R9HM R18HM (swamp), R18DQ (quarry), R9FI (fungal), R9SW R18SW (sunset), R9FK (keep), R18IL (lodge),
  R9TP (Crownbreaker), R9BD R18BD (Undertow), R9RK R18RK (Gull Rock), R9LC R18LC + R9F (the Long Count), R12R5 (Route 5),
  R12R4 (Route 4), then R17.

## 3. Waiting on the owner
- The probes' owner halves (report section 2) and EXP-084's 15 owner steps; XT1 decides the clocks.
- **Q20** (the Night Shift's free first run) and **Q23** (ungated sigil recipes): still no alternative given.
- The review list's owner choices (report section 5, items 6, 7 and 9); the catch design's Q-C1 and Q-C6; dungeons 2
  and 3's S-Q1..5 and P-Q1..5.
- Carried: the stale steps and the chunk-race steps from the previous handover; EXP-061/062/064-068 in game.

## 4. Do not rediscover
- **Never `datapack enable` on staging**: it is a full reload and OOMs this build at 16G (2026-10-09). Copy a pack in
  with the server stopped and boot.
- A pack must be in `SERVER_PACKS` (or the spawn packs) to be installed; `WORLD_LOCAL` alone is not enough (guard test
  `tests/test_install_check.py::test_every_world_local_pack_is_in_an_install_list`).
- Prepare refuses a build whose jobs predate the last change to `data/` or `tools/`: `--from` after an edit does not
  complete it; run it whole. `COBBLERS_SERVER_ROOT` must be set or `sea_drift_audit` fails.
- `reapply.py run` refuses while `max-tick-time` is not -1.
- RCON replies are cut at 4096 bytes; `datapack list` cannot be read whole. `datapack list available` lists ALL packs.
- MobsBeGone deletes every summoned vanilla mob except villagers and wandering traders.
- A predicate against a crafted sigil must use the byte form `{cobblers_dg_sigil:1b}`.
- Concrete (and possibly concrete powder: unresolved) is a spawn-condition block contract C4 refuses in built packs.
- Summoning in the same RCON burst as a `forceload add` finds nothing (N155): wait a moment.
- Agents briefed with a path in this session's scratchpad wrote their own scripts there once and were refused
  ("Modify Shared Resources"): brief them to keep scratch inside their worktree.
- `derived/` for a new worktree: robocopy from `session-handover-decisions-de63f6` (done here).

## 5. Cost
`python tools/session_cost.py` at the handover: this session ~14M weighted (context ~600k: over the line, start fresh);
agents 99.3M+ against about 100M estimated in all. Over estimate: the arena pilot (10.4M vs 5M), Fungal Isle (6.6 vs
4), the C7 rookery (5.3 vs 4), Route 5 (5.2 vs 4), Route 4 (7.2 vs 4), C3 (6.2+ vs 4). Under: the seven arena
authors (7.1M vs 18M), E1 (0.9 vs 2.6), the challenge tests (1.1 vs 2.6).
