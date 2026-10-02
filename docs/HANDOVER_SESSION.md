# Handover — encounters rebuilt, hearts laid out, starters in the wild; nothing installed or seen in game

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. The branches

- **`build/2026-10-02-encounter-rebuild`**, from PR #105's head `2de7170`, pushed. **No PR, by instruction**: the
  owner wants one integration PR per batch. Re-read its head with
  `git fetch --prune; git rev-parse origin/build/2026-10-02-encounter-rebuild`.
- **`research/2026-10-02-mythical-starters`** (`194330c`, from main `31deeba`), pushed: one research document, no
  changes.
- **Main has moved**: `31deeba` (PR #106, `build/2026-10-02-night`) merged during this session. Nothing here is
  merged with it yet.

## 2. Where it stopped

Everything is merged into the rebuild branch and verified offline:

- `build_encounters.py --check`: identical. `validate_data.py`: 0 errors, 0 warnings.
- The design and hearts tests plus the compiler, Victory Road, Habitat Block and contract suites: 245 passed,
  2 xfailed.
- Full suite: **16 failed, 5,310 passed, 144 skipped, 11 xfailed** (560 s; this worktree has a copied `derived/` and no prepared `build/`). Since then, one of the 16 is fixed: `test_no_swallowed_crashes` had flagged two broad handlers in this work (`tools/encounter_audit.py`, `tests/test_encounter_hearts.py`); both now catch only `terrain.TerrainUnavailable`, and both pass with and without the heightmap. The 15 left:
  - the known ten (4 blackout_recovery_pid, 3 sea_town, 2 rift_heightmap, 1 mines_independent);
  - three that need a prepared `build/` (ambient_sites, light_plan, reapply_lock);
  - `test_route_events`, one road-clearance problem in inputs this work never touched (cause not found);
  - **one caused by this work**: `test_battle_sim.py`'s assertion that both Nidoran are in Gym 8's pool (the base forms are now off the path at tier 1). It belongs to a test author to re-point.

**The next step is to install and look.** Nothing rebuilt is in any world: staging-2026-10-01's `cobblers_spawns`
is the rejected one (byte-identical to `2de7170`'s compile). Take the coordination lock, then:

```
python tools/reapply.py prepare --only compile_spawns
python tools/reapply.py install --server-dir C:/Users/wnd/Documents/github/cobblers-server --world-dir C:/Users/wnd/Documents/cobblers-staging/staging-2026-10-01
```

Install regenerates the suppression against that server and world (it reads the server, so take the lock). Then
restart.

**Not installed: staging was busy (2026-10-02, after the owner confirmed the balance).** At the install attempt
port 25565 was listening (java pid 40584) and the coordination lock was held by session
`cobblers-cobblemon-session-start-531d15` since 08:47 ("staging-2026-10-01 up for the owner to see tonight's
builds"). Per the hard gate nothing in the runtime was read. Install when that session releases the lock and the
server is stopped, then boot detached and check the process.

**Where to stand** (ground from the canonical heightmap, +1 to stand on it; not yet checked in the world):

| Place | Stand at | What should spawn |
|---|---|---|
| Frostpeak, well above the y180 line | (566, 227, 316) | Absol and Delibird, Piloswine common, the presences (Abomasnow, Mamoswine, Beartic, Avalugg, Glalie) |
| Frostpeak, just above the line | (794, 183, 250) | as above, thinner; no heart Pokemon should stand below y180 |
| Frostpeak, just below the line | (806, 177, 244), 13 blocks from the last | slope table only: Absol, Delibird, Snorunt, Eiscue |
| Marshy Marsh's middle | (5158, ~63, 2166), the landmark centre | Toxicroak and Seismitoad thick, Swampert and Sliggoo, a big Feraligatr in the water |
| Lake Tilpey's middle | (5870, 63, 3874), by boat | Gyarados and Veluza; Wailord at 48-55 |
| The Great Crater's bowl | (6080, 195, 5530) | Chandelure; Charizard and Magmortar at 53-60, Volcarona |
| The dark Wedge's deep wood | (4016, 144, 3120) | Haunter, Drifblim; Gengar, Mismagius, Dusknoir at 43-50 |
| Lake Viltri's far woods | (1200, 103, 2928) | Bayleef common; Ninjask and Beedrill |
| The south-west fields' middle | (1904, 119, 5840) | Cottonee, Pikachu, Growlithe; Nidorina and Nidorino at 16-25 |

Spawns land around a player, not on them: read each Pokemon's own y (F3 while looking at it) for the summit line.

**Half-done:** nothing. No server, no lock held. Five agent worktrees under `.claude/worktrees/agent-*` hold only
what is merged here or pushed.

## 3. What waits on the owner

- **The balance numbers**, proposed in `ENCOUNTER_DESIGN.md` section 10:
  - a heart covers at most 1/9 of its place;
  - at most 11.2% of a heart's spawns may be above the cap;
  - a presence may reach at most the next leg's cap;
  - no heart sits within 128 blocks of a path.
- **The mythical starters**: `docs/research/MYTHICAL_STARTERS.md`. Three decisions:
  - evolution at 31 for all five, plus 46 for Cosmoem only;
  - hybrid scaling (Cosmog and Cosmoem only) or accept the spread;
  - how Meltan evolves at all.
- **Small calls already made, for the owner to overturn if wanted:**
  - Victory Road is 54-60, with prizes at 57-60;
  - the islands' tiers (each table's `tier_why` gives the reason);
  - which places have no heart (section 10 lists them).
- **In-game checks**, five minutes standing still each:
  - Frostpeak above y180, near (679, 324): Abomasnow, Mamoswine, Beartic and Avalugg among Absol and Delibird.
  - The middle of Marshy Marsh: Swampert, Sliggoo and a big Feraligatr.
  - Lake Viltri: Magikarp, Lotad and Corphish, with no Goldeen.
  - Lake Tilpey's open water: Gyarados and Veluza; Wailord at the heart.
  - Victory Road's Drowned Gallery: no Quagsire or Excadrill.
  - A starter, e.g. Bulbasaur in Pallet's meadows.
  - `minY` behaviour itself: whether a summit band spawns only above its line.
- **Starters config**: the owner says the server uses mythical starters. `modpack/config/cobblemon/starters.json`
  still lists the 27 normal starters plus a Hisui set; read only, not verified on the server.

## 4. What a cold start must not rediscover

- **An agent's worktree starts at main, not at this session's HEAD.** All four agents launched after main moved
  found `--ff-only` failing. Brief agents with `git checkout -b <branch> <full sha>`.
- **The audit reads the compiled pack.** Inside every sub-region the suppression cancels every inherited pool, so
  our tables are all a player meets there.
- **Heart and base, told apart in the compiled pack**: a heart detail carries `minY`, or covers a smaller box set
  than the base (`tests/test_encounter_design.py` `split_heart`). Heart ids follow `<sub>_h<n>_`.
- **`minY` is a real key**: the string is in `SpawningCondition.class`, and 504 stock spawns use it. Its behaviour
  is not seen in game.
- **Section 5 (waters) governs Totodile and Piplup** as water families. They are the only starters in a water
  table.
- **Same-session test edits, declared**:
  - `tests/test_encounter_design.py`: the regional-form lookup, edited by this session. The heart/base split was
    the second test author's.
  - `tests/test_vr_caves.py`: the prize band, 57-60.
- **`test_battle_sim.py`'s Nidoran assertion was red after the first rebuild.** It asserts both Nidoran are in
  Gym 8's pool. Check it in this run's result (section 2); if still red, a test author re-points it.
- **`install_check.py` at session start** reported one real problem: `cobbledollars/common.json` differs from the
  overlay. Not investigated.
- **staging-2026-10-01 has `cobblers_rift_zones` installed**, though STATE says it is excluded. Not investigated.
- **The Meltan finding**: Cobblemon 1.8.0 gives Meltan no evolution at all. Its level-70 anvil evolution is
  COBBLEVERSE's (`species_additions/meltan.json`).

## 5. Cost

`python tools/session_cost.py` at hand-over:

```
session ff9026c0-b8c8-4044-a57e-cd42a5a8fccd: 146 turns, context now 482k (average 327k), weighted 6.8M
  agent Research mythical starters feasibility     turns   88  final context  242k (the harness's figure)  weighted  1.73M
  agent Write encounter design tests               turns   41  final context  115k (the harness's figure)  weighted  0.48M
  agent Test encounter hearts per section 10       turns   82  final context  164k (the harness's figure)  weighted  1.27M
  agent Build encounter generator                  turns   75  final context  192k (the harness's figure)  weighted  1.24M
  agent Build focal-point encounter hearts         turns  109  final context  327k (the harness's figure)  weighted  2.85M
  agents together: 7.6M weighted
```
