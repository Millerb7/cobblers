# Handover: session 74260a, ending 2026-10-11 evening (over the context line)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-09-dungeon-playtest` in worktree `.claude/worktrees/night-shift-engine-gym-9b76f2`, LOCAL ONLY (no PR;
one big draft PR for the batch is owed). Re-read the head with `git rev-parse HEAD`. Installed build: prepare
229/229 at e18ec16. The integrator branch is fully merged (72a920a). Three agent branches wait to be merged (section 2).

## 2. Where it stopped
- **Staging is UP for the owner to play**: 12G, terminal panel tab "staging server", PID 20076 at hand-over, watchdog
  60000, the dungeons, Scar Tarn and Compact applied (STATE "Latest install (2026-10-11 evening)"). The server lock
  is released.
- **Next, in order (a new session; no server needed until the last step):**
  1. Merge `worktree-agent-ab58f8c4e3d5f1aab` (1e3a58c, the `one_of` loot generator), then
     `worktree-agent-aa63c56da70fb431e` (4d02fca, the vault tables; needs the first), then
     `worktree-agent-ab7b02f38664ec26c` (60c2305, the player dungeon guide).
  2. Cheap checks: `python tools/validate_data.py`, `python tools/id_authorship.py`, `python tools/dungeon_audit.py`,
     `python tools/dungeon_greed.py` (if it has a check), `python -m pytest tests/test_dungeon_vault_one_of.py
     tests/test_player_guide_dungeons.py -q --tb=line`, then the full `python tools/dungeon_independent_audit.py`
     (33 min). Fix `tests/test_dungeon_kit3.py` and DUNGEON_ROOMS.md 1b for `dollar_factor` 2.0 ONLY if the owner
     keeps 2.0 (DUNGEON_VAULTS.md Q1); confirm the new ball and held-item ids in the Cobblemon 1.8.0 jar.
  3. `python tools/player_guide_dungeons.py` then `python tools/player_site.py` (every page's nav gets the guide).
  4. Next install: env `COBBLERS_SERVER_LOCK`, `COBBLERS_LOCK_OWNER`, `COBBLERS_SERVER_ROOT=C:/Users/wnd/Documents/github/cobblers-server`
     (sea_drift_audit needs it), full prepare (~51 min), RCON stop, hold `config/cobbledollars/bank.json`, install
     with `--cobbleverse-dp C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/datapacks/COBBLEVERSE-DP-v31.zip`,
     restore the bank, `max-tick-time=-1`, **boot at 24G for R16DG** (12G runs out of memory at 13 dungeons),
     `run --only R16DG --no-reload` (the vaults are in the shells), watchdog 60000, restart at 12G, check twice.

## 3. Waiting on the owner
- **Vault budget (DUNGEON_VAULTS.md Q1):** `dollar_factor` 2.0 (richer vaults, the greed clock speeds up more) or 1.0
  (every chance halves).
- **The draw design:** D1-D5 in `docs/mechanics/DUNGEON_DRAW.md` (design only; no rework until approved).
- **Play first:** the Street, the Patriarch, Ash Bell. Tag `cobblers.dg_playtest`, then
  `scoreboard players set <player> dg.ptband <n>`; rips on the test trail by the old mine, x1350-1677 z~4118.
  Nothing new is authored until three are played.
- Whether the guide's level of detail is spoiler-light enough (nest and mini-boss species, fork looks, vault rooms).

## 4. Do not rediscover
- R16DG at 13 dungeons OOMs a 12G heap; the save survived (checked chunk by chunk). 24G ran it in 69 s.
- The independent audit takes ~33 min, not 2. `test_staging_only_never_installed` fails in an agent worktree only
  because `R.steps()` needs a prepared build/.
- New Compact NPCs collided twice with older placements (fixed 4ff9b35, e18ec16); prepare's `markets:audit` and
  `ambient_idle:build` catch these. Three more stand in a solid block (STATE, What is open).
- The vault budget per chest is KIT3's (bank tier rates x clocks), 80 to ~546 cp at factor 1.0: below one Great Ball
  at bands 1-4. A `one_of` is priced at its expected value.
- C: is 100% full (7 GB); the pagefile is on D: (47 GB commit free at 21:00).

## 5. Cost
`python tools/session_cost.py`: hand over verdict at ~300k context (more than 32k a turn); agents 4.4M weighted together (guide, vault
designer on Opus, generator builder).
