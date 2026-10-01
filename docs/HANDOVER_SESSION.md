# Handover — the phase-2 PR, four red tests, and the settlement NPCs counted

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

Two units in one session: the overdue phase-2 PR, then the settlement-NPC count. 80 turns, context 241k,
**2.1M weighted** — against 42.9M for the run before it. `session_cost.py` says hand over, and the unit is
done, so this stops here.

## 1. The PR stack — three drafts, in order

Nothing is merged. **Merge bottom-up, each pinned to its reported head.**

| PR | Branch | Base | Head | What |
|---|---|---|---|---|
| [#95](https://github.com/Millerb7/cobblers/pull/95) | `night/2026-09-29-water-export` | `main` | `5230051ed2d2` | the water export (pre-existing, **frozen**) |
| [#97](https://github.com/Millerb7/cobblers/pull/97) | `build/2026-09-29-phase2` | `main` | `27710fdb82085d06d5cb01229b4651d2ba75b70a` | the phase-2 build, 140 commits |
| [#98](https://github.com/Millerb7/cobblers/pull/98) | `docs/2026-09-30-phase2-handover` | #97's branch | `3bf300b056c2b7037f261bb3fc9ebbd4a7e11ee2` | the suite-baseline correction |
| [#99](https://github.com/Millerb7/cobblers/pull/99) | `docs/2026-09-30-settlement-npcs` | #98's branch | see below | the settlement-NPC count |

- **#97 inherits 38 commits from #95 and must not merge before it.**
- Merge commands: `gh pr merge 97 --match-head-commit 27710fdb82085d06d5cb01229b4651d2ba75b70a`, then
  `gh pr merge 98 --match-head-commit 3bf300b056c2b7037f261bb3fc9ebbd4a7e11ee2`, then #99 at its head.
- All four are **drafts**; marking any ready is a human act and nobody has reviewed them.
- Current branch is `docs/2026-09-30-settlement-npcs`. Tree clean apart from `.codex/config.toml`,
  **deliberately uncommitted** — it is Codex's (`docs/HANDOVER_CODEX.md` item 29).
- **A memory note disagrees with this shape:** "one big PR per batch, not a stack". The stack happened
  because each PR was opened before the next unit started and a reported branch is frozen. If the owner
  prefers one PR, the three doc branches should be squashed onto #97 before it is reported anywhere else.

## 2. The next unit: four red tests that are phase-2's own

Unchanged from the last handover and **still the next job** — a chip was spawned for it (`task_2a850b3d`),
so it may already be running in another session; check before starting.

The suite at 27710fd is **5,138 passed, 12 failed, 9 xfailed** in 1,054 s. Eight are the real pre-existing
baseline and must not be chased. **Four are phase-2's own**, in two test files that are new on that branch
along with the data they check (`data/gym_buildings/` and `data/legendaries.json` exist on no other branch):

| Test | Why it fails |
|---|---|
| `test_gym_buildings_independent.py::test_the_five_buildings_are_exactly_the_five_interiors_that_were_superseded` | written at **five** buildings; there are now **seven** (gyms 6 and 8 landed after) |
| `…::test_the_audit_says_something_about_every_building_that_exists` | same cause |
| `test_legendaries.py::test_an_unadmitted_unsatisfiable_gate_is_rejected` | Registeel was unsited when it was written |
| `…::test_a_new_unsatisfiable_dependency_must_be_admitted` | *"registeel is sited now: this test no longer tests it"* |

**Use a `test-author` agent.** Decide what each should now assert; do not widen a threshold until it passes
(CLAUDE.md, "Reject your own slack"). Reproduce with:

```
python -m pytest -q --tb=line tests/test_gym_buildings_independent.py tests/test_legendaries.py tests/test_no_swallowed_crashes.py
```

While there: `no_swallowed_crashes` names those same two files for catching `BaseException` with the comment
*"no heightmap here"*. **The heightmap is present** — `tools/ground.py` read it fine this session — so that
excuse should be re-examined, not inherited.

## 3. The settlement NPCs: 15, not 32 (`docs/world-building/SETTLEMENT_NPCS.md`)

**The owner's figure of 32 has no file behind it** — `32` appears nowhere in the repository in connection
with NPCs. Closest real number is **34**, the gate-guard positions.

- **15 unplaced settlement NPCs**: the 13 `npc_main_*` actors of `main_worldshift_reveal`, plus Pallet's
  Hank (105 nodes) and Lena (16, `scope: mixed` — she is the one `compile_dialogue.py` refuses, on
  world-scoped fields). Nothing places any of them.
- `data/dialogue.json`'s 74 conversations hold 24 `npc_id`s; **50 carry none** and are Routes 1–3 props and
  Pokémon, already built. `data/scenes.json`'s 10 actors are all route Pokémon.
- **The blocker is standing blocks, not coordinates.** 10 of 13 have a `recorded_position_xz`; **0 have a
  `stand_marker`**. Nine of the ten check out — inside their own settlement's footprint and on heightmap
  ground within ~2 blocks of its `ground_y` range. Missing a position entirely: `pallet_maren`,
  `brock_witness`, `rift_surveyor`, all blocked upstream (Pallet relocation is open; `brock_witness`'s
  anchor now means the authored Stoneworks Hall).
- **The bulk of the work is the 12 physical-evidence objects, 10 unbuilt** — Misty's relief ledger, Surge's
  signal array and comparison record, Erika's survey ledger, Koga's control plate, Sabrina's convergence
  table, Blaine's destination model, Giovanni's dissenter carrier.
- **34 gate guards: positions exist, characters do not.** "THE GATES ARE GUARDS." Counted from
  `TOWN_CHARACTER.md` — 33 rows, 34 positions, Sunset West carrying two. Codex's.

### Defect for Codex, deliberately not fixed here

**`npc_main_league_steward` is recorded at (3297, 2603): 433 blocks from the League, inside no settlement,
at heightmap y118 against the League footprint's 86.3–98.9.** Three checks on independent data. It is **the
retired `FACTION.md` cradle coordinate**, the one the Rift-zones unit rejected for (3357, 3306) because it
falls outside the Rift — so one stale coordinate has propagated into a second file. `data/quests.json` is
story data: **Codex corrects it upstream.** Moving it to the League lot from this side would hide the
propagation.

## 4. Blocked: the server lock, so no install check has run

Server **down** — no listener on 25565, no Java process. The lock at
`C:\Users\wnd\Documents\github\.cobblers-server-agent.lock` still carries the 2026-09-29 owner line.

**The write to take it over was refused** by the auto-mode permission classifier (`Modify Shared
Resources`). Per CLAUDE.md a refusal ends the attempt, so it was not routed around — and that also rules out
`python tools/install_check.py`, which reads the server's `config/` and `datapacks/`. **The session-start
install check has not run for two sessions now.** A cold session either gets that write permitted or stays
repo-only. Both units this session were repo-only and unaffected.

## 5. Worktrees: cleaned once, no rule added

`.claude/worktrees/` was **44 directories, 7.9 GB**; 37 were `agent-*` isolation worktrees the harness never
reclaimed (it auto-cleans only unchanged ones, and every one had been written to). The app's own
`clean_up_worktrees` cannot see them — it reports 4 worktrees across 3 repos, session worktrees only.

Removed 36 and 59 stale `worktree-agent-*` branch refs → **8 directories, 4.77 GB**; registered worktrees
61 → 25. Checked safe first: every agent HEAD was reachable elsewhere, and all six dirty worktrees held only
redundant untracked copies.

Left alone deliberately: the locked `agent-a935361eae89fb3d0`; `canonical-data` (empty, unregistered); and
`winui3-widget-board-60b59c`, which is a worktree of the **`Job-Bored`** repo parked in cobblers' folder and
which `git worktree prune` here will never touch.

**No teardown rule was added** (the owner chose removal only). So this will rebuild; if it should not, the
rule belongs in CLAUDE.md's Delegation section.

## 6. Still open, untouched by this session

- **F12** — `route_07_trainer_01` and `route_07_trainer_04` authored inside town boxes. Seats moved to legal
  shoulders, authored points left alone. **Codex's `TRAINER_RULES.json`; do not correct from this side.**
- **Four zone walls withheld by data:** z4 needs Codex dialogue reading `q.player.pokedex.caught_count`; z5
  needs `rift_crisis_resolved`, which still has **no setter** on `origin/codex/trainer-modes`.
  `rift_zones.py report` exiting 1 on 3 OWED is correct. Do not invent the setter.
- **Giovanni's roster held and empty**, blocked on the singles-vs-doubles call in
  `docs/story/GIOVANNI_FORMAT.md`. His building exists; the eighth badge is winnable against upstream's
  roster. The decision goes in `data/gym_trainers.json` as his `battle_format`.
- **Unproven, owner only: whether Brock now refuses a rematch with the badge in hand.** The guard is
  installed; installed is not working.

## 7. What a cold start must not rediscover

- **A nested isolation worktree is based on the MAIN checkout's HEAD**, far behind, and `git merge --ff-only`
  fails. Authorise `git reset --hard <sha>` explicitly in the brief.
- **Verify against the world, not the plan.** Make the agent nominate, in advance and in coordinates, the
  seats most likely to embarrass it, then probe those over RCON.
- **"Our list is not the world"** and **"How to prove an audit is independent"** are both in CLAUDE.md. Read
  them before writing an audit or anything that enumerates our own data.
- `COBBLERS_SOURCE_ROOT` must be `C:\Users\wnd\Documents` in every shell. Both validators are clean at
  4514dad: `validate_data.py` 0 errors 0 warnings; `validate.py` 1,237 files, 0 errors, 0 warnings.
- The full suite takes **1,054 s** — over the 600 s tool timeout. Run it backgrounded.
- `tools/ground.py`'s API is `ground.load()` returning a callable, plus `.box()`; there is no `ground.at()`.
