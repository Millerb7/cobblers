# Handover — the encounter tables are rebuilt; nothing is installed or seen in game

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. The branch

- **`build/2026-10-02-encounter-rebuild`**, from PR #105's head `2de7170`, pushed. **No PR, by instruction**: the
  owner wants one integration PR per batch, and this batch had three parallel sessions. Re-read its head with
  `git fetch --prune; git rev-parse origin/build/2026-10-02-encounter-rebuild`.
- It carries the audit (`ca3358c`), the design (`ccc6b23`), the independent tests (`9cb0613`), the generator
  (`ba50470`), the fixes (`d92abad`, `38bd8db`) and this handover.

## 2. Where it stopped

Done and verified offline:

- `tools/build_encounters.py --check`: identical. `validate_data.py`: 0 errors, 0 warnings.
- `tests/test_encounter_design.py`: 25 of 25 (20 of them fail on the rejected data).
- Spawn, Habitat Block, Victory Road, bird and design suites: 579 passed.
- `tests/test_system_contracts.py`: 83 passed, 1 skipped, 2 xfailed (C4 untouched: only existing condition keys).
- Full suite: **15 failed, 5,289 passed, 146 skipped, 11 xfailed** (625 s; this worktree with `derived/` copied, no prepared `build/`). The known ten (4 blackout_recovery_pid, 3 sea_town, 2 rift_heightmap, 1 mines_independent). Three need a prepared `build/` (`test_ambient_sites`, `test_light_plan`, `test_reapply_lock`: 'run `reapply.py prepare` first'). `test_route_events` reports 1 ROAD CLEARANCE problem; it reads nothing this rebuild changed and its inputs are unchanged since `2de7170`, cause not identified. **One is this rebuild's:** `test_battle_sim.py::test_every_gym_pool_is_exactly_what_the_sidecar_records` asserts both gendered Nidoran are in Gym 8's pool; at tier 8 the Nidoran families show only Nidoqueen and Nidoking (the base forms are off the path at tier 1). The assertion is about the gender-sign key and needs re-pointing at a pool that holds Nidoran: test-author work, left red.

**Next step: install and look.** Nothing rebuilt is in any world. staging-2026-10-01's `cobblers_spawns` is the
rejected one, byte-identical to `2de7170`'s compile. With the coordination lock (the trainer-placement session
owned staging tonight; it was free at 01:30 and 01:45 when this session read the staging spawn packs read-only):

```
python tools/reapply.py prepare --only compile_spawns
python tools/reapply.py install --server-dir C:/Users/wnd/Documents/github/cobblers-server --world-dir C:/Users/wnd/Documents/cobblers-staging/staging-2026-10-01
```

Install regenerates the suppression against that server and world (it reads the server, so take the lock). Then restart: Habitat pools resolve after a chunk reload.

**The next job (the owner, 2026-10-02, after reading this):** small at the edges, big at the focal points, and Pokemon
above the cap allowed at a place's heart. Frostpeak first ("big snowy creatures"). `ENCOUNTER_DESIGN.md` section 10;
a fresh session, one builder plus one test author.

**Half-done:** nothing. No server started, no lock held (released twice, verified free), and the two agent worktrees
(`agent-a34fe9f3a8cb8935a`, `agent-a74e5041a4bd3d3c6`) hold only what is merged here.

## 3. What waits on the owner

**In-game checks**, each about five minutes standing still (spawns need a player):

- Lake Viltri (leg 2): Magikarp, Lotad, Corphish, rare deep Chinchou. No Goldeen.
- Lake Tilpey's open water (tier 7): Gyarados, Veluza, Golduck. No Magikarp.
- Marshy Marsh (tier 5): Croconaw/Feraligatr, Palpitoad, Toxicroak, Stunfisk; Goomy in rain.
- Victory Road's Drowned Gallery: Lanturn, Kingdra, Gyarados, Toxapex, Golisopod, Barbaracle, Crawdaunt. No Quagsire,
  Whiscash or Excadrill anywhere in the cave. Prizes at 57-60.
- An off-path find, e.g. Riolu in the Viltri path valley (tier 2, ~1 land spawn in 80).

**Decisions, small:**

- Victory Road's levels moved from 58-64 to 54-60 and the prizes to 57-60, because the catch block (2026-09-28)
  made everything over 60 uncatchable. `data/vr_caves.json` `spawns.band` changed with it.
- Fifteen off-path places lost their 25-45 placeholder band. The islands' tiers are judgments, each with its
  `tier_why` in `data/encounter_design.json`. The Long Isle is tier 7 in the north and middle and 8 in the south,
  near the owner's 44-50.
- Starters and pseudo-legendary bases now appear as off-path finds: Rowlet, Dratini, Larvitar, Deino, Bagon,
  Jang-mo-o, Axew, Riolu, Eevee, Lapras, Snorlax and others.

## 4. What a cold start must not rediscover

- **The audit reads the compiled pack, never `data/spawns.json`'s intent.** Inside every sub-region the
  suppression pack cancels every inherited pool, so the tables are all a player meets there.
- **The rebuild's cause list:**
  - The band-minimum evolution rule (154 rows zeroed).
  - Sixteen 25-45 placeholder bands.
  - One water template pasted into eleven lakes.
  - Empty off-path rare slots.
  - Victory Road's shared filler (Golbat, Excadrill, Boldore, Graveler).
- **`availability.py` does not walk Victory Road**, so all four Rift tables are off the path by the design's rule.
  They carry finds, and the Victory Road corridor does not carry them.
- **Regional forms**: `"sandshrew alolan"` was read as plain Sandshrew by both the test and the audit. Fixed in both.
- **Same-session test edits, declared**: `tests/test_encounter_design.py` (the form lookup) and
  `tests/test_vr_caves.py` (the prize band, 57-60). Neither moves a threshold set before the build.
- **Mutation proofs, generator-side:**
  - Maturity forced to 0: three escalation tests fail.
  - The corridor admitting finds with no species cap: the corridor test names all five Rift finds.
  - The corridor admitting finds with the cap kept: no test fails, because no find reaches a capped corridor.
  - Stone and trade evolutions at every tier: caught only indirectly, by a water test. Section 8 sets no target
    for that rule.
- **The audit's leg grouping shows leg 2 1.8 below leg 1** (it counts the corridors); the design test groups by
  table tier and finds no fall. Victory Road's novel-family share is 0.12: its new things are final forms of
  families met earlier.
- **`install_check.py` at session start**: 48 of its 49 problems were only "not built in this worktree". The one
  real finding is that the server's `cobbledollars/common.json` differs from `modpack/config/`. Not investigated.
- **staging-2026-10-01's world datapacks include `cobblers_rift_zones`**, which STATE says is deliberately NOT
  installed (`reapply.py` EXCLUDED). Seen in a folder listing only; not investigated.
- **The worktree complexity guard** refused a few compound `python -c` commands, both agents' and one of mine;
  re-run as plain commands, as its message asks.

## 5. Cost

`python tools/session_cost.py` at hand-over:

```
session ff9026c0-b8c8-4044-a57e-cd42a5a8fccd: 104 turns, context now 398k (average 277k), weighted 4.2M
  agent Write encounter design tests               turns   41  final context  115k (the harness's figure)  weighted  0.48M
  agent Build encounter generator                  turns   75  final context  192k (the harness's figure)  weighted  1.24M
  agents together: 1.7M weighted
```
