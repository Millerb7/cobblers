# Handover: the 2026-10-02 integration (encounter rebuild + both starter branches)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 0. The integration

- **Branch:** `build/2026-10-02-integration`, from `origin/main` at `31deeba` (#104, #105 and #106 are all merged
  there; nothing is left to close).
- **It merges three branches:**
  - `build/2026-10-02-encounter-rebuild` at `e332cd3`. Its head moved past the relayed `717923d`, which it contains.
  - `research/2026-10-02-mythical-starters` at `194330c`.
  - `research/2026-10-02-native-starters` at `3751cd4`.
- **Its PR, head and merge command** are in the final report of the session that built it. Re-read the head with
  `gh pr view <N> --json headRefOid` before quoting it.
- **Not in this pass:**
  - `codex/resident-encounters`: open draft #107, another agent's, not reviewed here.
  - `codex/exp-009-hex-prototype`: one documentation commit from 2026-09-10.
  - `world/town-character`, `world/rift-mines`, `towns/batch1-placement`: stale tips whose only extra commit is a
    merge already on main (`git cherry` is empty).
- **The two starter notes are reconciled.** The owner's 2026-10-02 decisions supersede both recommendations:
  - a-lite at 30/45;
  - offered evolutions;
  - scrolls from the research station;
  - Meltan as drafted;
  - the cap kept at 60 after gym 8.

  Both notes stay as evidence. Section A has the detail.

## A. Starters, the League cap and the legendaries audit (native-starters session)

**The previous handover (the night of 2026-10-02's integration, PR #106) is still the owner's open list.** Its
in-game checks and decisions are unchanged by this session. Read it with
`git show 31deeba:docs/HANDOVER_SESSION.md`.

### 1. The branch

- **`research/2026-10-02-native-starters`**, branched from `origin/main` at `31deeba` and pushed.
- **No PR**: the owner did not ask for one.
- It touches docs only: the new `docs/research/NATIVE_STARTERS_1_8_0.md`, `docs/mechanics/NATIVE_STARTERS_COST.md` and
  `experiments/EXP-049-native-starter-evolution/README.md`; one row in `docs/research/EXPERIMENT_BACKLOG.md`; one line
  in `docs/STATE.md`; and this file.

### 2. Where it stopped

- **Done:** the owner's brief is answered (the starter questions, the learnset question, identical evolution points,
  strength scaling, the stress tests).
- **Next:** nothing runs until the owner decides (section 3). Then EXP-049, in a staging session holding the lock.
- **Nothing half-done:** no server, no lock and no worktree for another agent.

### 3. What waits on the owner

**Everything asked is decided** (2026-10-02):
- a-lite at 30/45; EXP-049 first; reconcile with `194330c` before building;
- evolutions offered, not forced;
- the research station hands out Kubfu's scrolls;
- Meltan approved as drafted;
- the cap stays at 60 after gym 8 and is capped until Blue;
- Lugia at 75.

**Next work:** EXP-049, in a staging session holding the lock. Then the a-lite build, which must start by integrating
`194330c`.

**Changed in code this session:** `tools/legendaries_audit.py` (`rct_caps`, the real-cap check), four tests in
`tests/test_legendaries.py`, and `data/legendaries.json` (`cap_at_gate` corrected, Lugia 75, champion band 100).
- Lugia is `blocked`, so no emitted pack changes.
- The other records' levels are unchanged, so no re-apply is needed.

### 4. What a cold start must not rediscover

- **A parallel note exists:** `origin/research/2026-10-02-mythical-starters` (`194330c`,
  `docs/research/MYTHICAL_STARTERS.md`), unmerged.
  - Every shared measurement agrees, and its option-(b) sim figures reproduce to the unit.
  - It differs on the recommendation: c, against a-lite here. Its option (a) uses each line's final-form shape, where
    this session used each stage's own; that is why the two "a" figures differ.
  - Integrate the two before building. Do not build from either alone.
- **The jar is readable without the lock:** a client copy of `Cobblemon-fabric-1.8.0+1.21.1.jar` (and MSD 1.0.2,
  TMCraft 1.4.19) sits at `C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10/mods/`. Cobbleverse's
  datapacks are at `C:/Users/wnd/Documents/github/cobblers/COBBLEVERSE/datapacks/`.
- **A refused command:** `python tools/compile_spawns.py && python tools/availability.py --write` was refused by the
  permission classifier ("Irreversible Local Destruction"). It was not retried. The starter duels need no availability:
  the gym caps and foes were built straight from `data/trainers.json` with `battle_sim`'s own functions.
- **Run heightmap tests with `COBBLERS_SOURCE_ROOT='C:\Users\wnd\Documents'`.** This session's shell did not inherit it from `.claude/settings.json`, and without it 47 tests skip silently.
- **`tools/validate_data.py` reports 263 errors, all `[spawn-blocks]` in `data/placements.json`.** None were introduced here.
- **The scratch scripts** (`spread.py`, `forms.py`, `evolv.py`) lived in the session scratchpad and are not in the
  repo. The method is in the research note, §8.
- **Learned in rctmod v0.19.0-beta source:**
  - the cap after the last series trainer is 100;
  - a series is never reset on completion;
  - per-trainer `relativeLevelCap` lives in the mob file;
  - the trainer-level cache survives `/reload`.
- **The brief's "E4 aces 57/58/59/60" is the spread inside each team.** All four aces are 60 (`data/trainers.json`).
- **Learned in 1.8.0 source:**
  - passive evolutions are tried every second (`PlayerPartyStore.kt:146`);
  - `evolution_tested` has `set_result`;
  - the `species` setter keeps `forcedAspects`;
  - `FormData.evolutions` never falls back to the species list.

### 5. Cost

`python tools/session_cost.py` at the end: see the final line of the session report.

## B. The encounter rebuild (carried unchanged from `e332cd3`)

### 1. The branches

- **`build/2026-10-02-encounter-rebuild`**, from PR #105's head `2de7170`, pushed. **No PR, by instruction**: the
  owner wants one integration PR per batch. Re-read its head with
  `git fetch --prune; git rev-parse origin/build/2026-10-02-encounter-rebuild`.
- **`research/2026-10-02-mythical-starters`** (`194330c`, from main `31deeba`), pushed: one research document, no
  changes.
- **Main has moved**: `31deeba` (PR #106, `build/2026-10-02-night`) merged during this session. Nothing here is
  merged with it yet.

### 2. Where it stopped

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

### 3. What waits on the owner

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

### 4. What a cold start must not rediscover

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

### 5. Cost

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
