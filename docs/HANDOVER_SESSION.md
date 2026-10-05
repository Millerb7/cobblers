# Handover: Wave 1 fixes and research (session 595493c5, 2026-10-06)

A cold session reads CLAUDE.md, `docs/STATE.md`, this file and `docs/PLAYTEST_2026-10-05.md`, and nothing else.

## 1. The branch
- **`build/2026-10-06-next`** on origin, stacked on `build/2026-10-05-p0` (draft PR
  [Millerb7/cobblers#119](https://github.com/Millerb7/cobblers/pull/119), frozen). No PR of its own yet. This session
  worked in worktree `wave-1-launch-prep-3d2fa0` on local branch `wave1-2026-10-06` (the branch itself was checked
  out in the old `consolidate-parallel-sessions-b6b9d7` worktree, left untouched) and pushed with
  `git push origin HEAD:build/2026-10-06-next`. Re-read the head before quoting it: `git fetch --prune; git rev-parse
  origin/build/2026-10-06-next`.

## 2. Where it stopped
- **Staging is DOWN**, stopped cleanly by RCON; `max-tick-time=60000` restored. **The lock is released.**
- **Built and committed, NOT prepared, installed or applied:** route variety / Pallet's Caterpie (85), Old Knot still
  (84), the lake grotto partitions never shut a player in (87), the bird towers' feathers removed after the paste
  (note 14), Dr. Vale's locked scroll line and hub re-entry (88), the waystone gate off (89). Commits 188edd8,
  37fd3d6, 926e6fd, 8338100.
- **Next, as commands** (main session, holding the lock): `python tools/validate_data.py` after
  `python tools/local_inputs.py hydrate --store C:/Users/wnd/Documents/cobblers-local`; then `python tools/reapply.py
  prepare` (~25 min, once); `install`; then the affected steps on staging (the spawns are installed by install; the
  residents R18R-family step for Old Knot; R14L is NOT re-runnable (duplicates summons): apply Azelf's new `near`
  by install + /reload rather than re-running R14L; R9E/R18A-family re-pastes are not needed for the feathers: run
  `data remove block 895 68 5582 storageWrapper.contents.inventory.Items[{id:"lumymon:thunder_feather"}]`,
  `... 6266 168 5361 ...ember_feather`, `... 682 311 379 ...glacier_feather` over RCON and read the barrels back).
  Also still deferred from the play test: farms, the bank buy list (install_check's one problem), Coldwater, the arena
  spawn-free zone.
- **Not done in Wave 1:** the spawn-block **allow** is recorded and the owner's list is generated
  (`docs/world-building/SPAWN_BLOCKS_LIST.md`), but ~60 generators/audits and 29 tests still refuse a spawn block in
  our builds, each reading `data/spawn_blocks.json` itself: a builder task (~4M). The second waystone near Viltri Quay
  and research-station waystones wait on locations.

## 3. Waits on the owner
- **Route rosters grew:** routes now carry 20/20/28/35/20/23/24/28/28 species (was 20 each) so every crossed table keeps
  three of its own; veto or accept.
- Challenge mode design (`docs/research/RCT_PER_PLAYER_MODE.md`): both leaders standing in every gym, each refusing
  the other mode's players -- acceptable?
- Summit barrels in the bird towers keep their loot (gems, diamond boots, trident, netherite template): keep?
- Kyogre questions 1 (per player) and 8 (chests) were not answered; defaults recorded.
- Locations: the second Viltri Quay waystone, research-station waystones.
- Per-player chests: Lootr (MIT, client+server, world-critical once used) vs SlashLoot (server-only, young); ADR next.

## 4. Do not rediscover
- Caterpie's cause was not its weight: a corridor box compiles only its table's species on the ROUTE's 20-species list,
  and Pallet lost every slot but Caterpie (also on the Viltri plateau). 113 route boxes had 1-2 species.
- The feathers ARE in the templates (Sophisticated barrel at template (10,1,10)/(14,1,13)/(14,0,17), path
  `storageWrapper.contents.inventory.Items`); STATE's older line saying otherwise was wrong.
- `test_system_contracts.py::test_contract_c4...` fails on `tools/bank.py` at 1c24f76 already.
- Two tests were edited by the implementer for intended behaviour changes (`test_articuno_tower.py`,
  `test_gym_waystones.py`): a second reader should look.
- `git reset --hard` on a worktree branch is refused by the auto-mode classifier; branch with `git switch -c ... --track`.
- Writing files with Python `Path.write_text` on Windows needs `newline="\n"` or git warns CRLF.

## 5. Cost
`python tools/session_cost.py`: 152 turns, 4.2M weighted for the main session (context 326k at hand-over), agents 2.4M
(three research agents).
