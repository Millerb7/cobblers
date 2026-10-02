# Handover — the night of 2026-10-02: four sessions integrated, everything applied and probed in staging

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. The branch and the PR

- **`build/2026-10-02-night`** — ONE integration branch for the whole batch, as the owner prefers
  (memory: one-big-pr-per-batch). It carries PR #105's work (and so #104's), this session's night, and the three
  parallel sessions' branches, merged here and re-verified in a full checkout:
  `build/2026-10-02-place-all-trainers` (1c57d67), `build/2026-10-02-encounter-rebuild` (acd9a6a),
  `design/2026-10-02-starters` (f1b333c).
- **The PR is [#106](https://github.com/Millerb7/cobblers/pull/106)**, draft. It supersedes #105 and #104; if it merges,
  close both unmerged. FROZEN from the moment it was reported. Re-read its head
  with `gh pr view <N> --json headRefOid` before quoting it.
- `origin/main` is still `a271532`; nothing from 2026-10-01 or 2026-10-02 is merged.

## 2. Where it stopped — everything is applied and the server is down

Final suite on the integration head: **11 failed, 5,534 passed, 11 xfailed, 0 errors** (614 s, full checkout) - the
known ten, named in `docs/STATE.md`, plus Brock's witness on gym 1's apron (a decision, section 3).

**In staging-2026-10-01, applied and probed against the world tonight** (`reapply.py run --only
R9SD,R9E,R17N,R18U,R18F`, then `--only R17`, then a second prepare + install for the encounter tables):

| What | Verified in the world |
|---|---|
| Ursaluna's den, Frostpeak camp, Seaward Drift + Driftmouth Isle | 31 of 31 probes, each named by its builder before the apply |
| The Ursaluna | species, level 35, `ScaleModifier` 2.0, `NoAI` - read off the entity |
| 20 settlement NPCs (R17N) | 20 of 20 (`npc_seats.py verify`) |
| Every seated trainer + gym spawners | 63 of 63 at their seats, none doubled; 8 of 8 spawners (`trainer_world_audit.py`) |
| The rebuilt encounter tables | 166 pool files installed; boot shows 0 spawn warnings and the same 43 third-party errors as before |
| EXP-048 | both adopted templates placed; all 8 LumyMon blocks real; a console-dropped carrot does nothing |

**Nothing is running.** Server stopped cleanly, `max-tick-time` restored to 60000, `level-name` still
`cobblers-10240` (never touched), coordination lock released and free.

## 3. What waits on the owner

**In-game checks, with coordinates:**

- **EXP-048, the right-click half** (`experiments/EXP-048-legendary-altar/README.md`): Articuno altar at
  (914, 153, 331) with `/give @s lumymon:glacier_feather`; Calyrex statue (4140, 112, 2005) with a crown; THROW a
  carrot from the crop (4156, 111, 2009) onto the Spectrier ring round (4153, 112, 1999). Record any chat line.
- **The encounter tables** (the encounter session's list): Lake Viltri (Magikarp, Lotad, Corphish, deep Chinchou;
  no Goldeen); Lake Tilpey's open water (Gyarados, Veluza, Golduck); Marshy Marsh; Victory Road's Drowned Gallery
  (no Quagsire, Whiscash or Excadrill); an off-path find such as Riolu in the Viltri path valley.
- **The den** at (1504, 162, 1414): does the Ursaluna look twice its size? The mouth faces south-east, 45 degrees
  off the line to Highwire, because that is where the ground is thick enough to roof a cave.
- **The camp** at (688-723, 688-725) and **Driftmouth Isle** at (336, 1586): do they read right from a distance?

**Decisions:**

- **The altars are scenery for three of four sites** unless the campaign supplies the item: no recipe or loot table
  anywhere makes a glacier_feather, thunder_feather or calyrex_crown. Supply them (a reward, the research camp?)
  or accept the sites as places. This decides the "import more of the catalogue" question.
- **route_03_trainer_05 stands inside a signpost** at (1980, 134, 1602). Move the trainer or the signpost.
- **Brock's witness stands on gym 1's forecourt apron** at (1832, 142, 3661), which the gym's own check counts as inside
  the building. Both records are deliberate. Does an NPC that writes no blocks "claim" a building's columns? Until
  decided, `test_gym_buildings_independent::test_nothing_else_claims_the_columns_a_building_occupies` stays red.
- **The sleeping Ursaluna** is unbattleable at level 35; the rebuilt band there is 20-28. Should it wake and fight?
- **"Frostpeak shrine"**: the summit outpost in `towns.json` or the Articuno tower on the east shoulder?
- **The starters design** (`docs/mechanics/STARTER_DESIGN_COMPARISON.md`, `docs/research/STARTER_OPTIONS.md`):
  costed, not built. Note that the encounter rebuild already put starters and pseudo-legendary bases off the path.
- **B15 (the Jungle Isle)** and **Tri Peaks foliage** are unchanged from the previous handover.

## 4. What a cold start must not rediscover

- **Take the lock only through `tools/server_lock.py take`**: an agent wrote it by hand as `owner=...`, which the tool
  cannot parse, so it could not be released; it was removed by its owning session after verifying the agent had
  finished. `runtime_guard` needs `COBBLERS_SERVER_LOCK` and `COBBLERS_LOCK_OWNER` (exactly the `owner:` line).
- **`reapply.py run` needs `max-tick-time=-1`**, set with the server stopped and put back after. `--only` runs in
  PLAN order, not the order given.
- **R17 and the "npc" action are idempotent** (a trainer or NPC already standing is left), so re-running R17 seats
  only what is missing.
- **A function that force-loads and writes in the next command works on this runtime** - R1's Rift pass does it
  and has landed on every verified apply - so no waits were added to the drift's 90 functions.
- **`trainer_world_audit.py`'s first run in a world** misread `attribute ... get` (fixed), measures transient AI
  rotation as "facing" (reported), and counts flowers and carpets as solid (reported).
- **`data/spawns.json` is generated** by `tools/build_encounters.py`, which owns the sub-region rosters, Victory
  Road's pools and route selection and copies everything else through. `"authored-only"` is the bucket INSIDE a
  pool (247 nested entries), never on a top-level entry (weight-0 top-level records use `"ultra-rare"`).
- **The drift's generator read its own output**: species positions now skip its own pool and fall back to
  Cobblemon's own spawn files (`tools/position_types.py`).
- **Relayed and wrong tonight, caught by measuring:** that the altar feathers are in the templates' barrels (false;
  it went into a data record unmeasured and was corrected); the isle's "1,228" dry columns (1,289 by its audit);
  Frostpeak's "summit" (679, 324), which is the pad's north rim, and its "27 degrees", a point not visible from the
  camp.
- **A green suite is not proof of a right change**: one fix rewrote 268 records, 264 of them other systems', and
  every test passed. The count caught it; it was reverted.
- **NPC coverage** (`tests/test_npc_seats.py`) is now a sweep over the step list, but covers only NPC classes
  compiled from `data/dialogue.json`; the camp ships its own classes and is invisible to it.
- **For a test author:** `test_habitat_blocks_activated.py` now copies `tools/habitat_blocks.py`'s cancel rule
  (changed by the drift's builder); `test_adopted_legendary_sites.py` can tighten `top_y` to one convention.

## 5. Cost

`python tools/session_cost.py`: this session **991 turns, 58.8M weighted**, context 726k at the end (the
owner lifted the hand-over threshold for tonight); agents together **36.3M**. About 95M across the session's life,
not counting the three parallel sessions, which report their own.
