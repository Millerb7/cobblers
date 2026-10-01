# Handover — the phase-2 PR, and four red tests it exposed

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

This session did one unit and stopped, as the previous handover asked. 46 turns, context 191k, **1.1M
weighted** — against the 42.9M of the run before it. The split works; keep doing it.

## 1. Branch and PR

- Branch `build/2026-09-29-phase2`, head **27710fdb82085d06d5cb01229b4651d2ba75b70a**.
- **PR #97 is OPEN as a draft** and is this branch's PR — the overdue one is now open.
  <https://github.com/Millerb7/cobblers/pull/97>. CI 1 passing, 0 failing. Bound to the app's PR bar.
  Marking it ready is a human act; nobody has reviewed it.
- **Its branch is now frozen.** Push nothing more to `build/2026-09-29-phase2`; further work goes on a new
  branch stacked on it with its own PR.
- **It is stacked on `night/2026-09-29-water-export`, PR #95, still OPEN and FROZEN.** #97 inherits 38 of
  its commits and must not merge before #95.
- Merge #97 only as:
  `gh pr merge 97 --match-head-commit 27710fdb82085d06d5cb01229b4651d2ba75b70a`
- Tree clean apart from `.codex/config.toml`, **deliberately uncommitted** — it is Codex's
  (`docs/HANDOVER_CODEX.md` item 29). The STATE edit below is committed on the next branch, not this one.

## 2. The next unit: four red tests that are this branch's own

**The headline finding of this session.** The suite measured at 27710fd is **5,138 passed, 12 failed,
9 xfailed** in 1,054 s. The long-standing "8 failed, and none of them is from the 2026-09-30 work" is
superseded and its second half was wrong. `docs/STATE.md` is corrected.

Eight are the real pre-existing baseline and should still not be chased: heightmap provenance,
`mines_independent`, `no_swallowed_crashes`, two `rift_heightmap`, three `sea_town`.

**Four are not baseline.** `tests/test_gym_buildings_independent.py` and `tests/test_legendaries.py` are
both new on this branch, as are the data files they check — `data/gym_buildings/` and
`data/legendaries.json` exist on no other branch. Each pins a state a later commit on the *same branch*
moved past:

| Test | Why it fails |
|---|---|
| `test_the_five_buildings_are_exactly_the_five_interiors_that_were_superseded` | written at **five** buildings; `data/gym_buildings/` now holds **seven** (`gym1,3,4,5,6,7,8`) since Sabrina's gym 6 and Giovanni's gym 8 landed |
| `test_the_audit_says_something_about_every_building_that_exists` | same cause, membership assertion |
| `test_an_unadmitted_unsatisfiable_gate_is_rejected` | Registeel was an unsited blocked chamber when it was written |
| `test_a_new_unsatisfiable_dependency_must_be_admitted` | fails with its own message: *"registeel is sited now: this test no longer tests it"* |

This is exactly the staleness the different-agents rule exists to catch: content moved, its tests did not
follow. **Fix them with a `test-author` agent, not with whoever ships the content** — a test rewritten by
the author of the thing it guards is worth less than a red one. The judgement needed is what each should
now assert, not a number bump; do not widen a threshold until the data passes (CLAUDE.md, "Reject your own
slack").

While there: `no_swallowed_crashes` now names those same two new files for catching `BaseException` and
disposing of it with the comment *"no heightmap here: the site checks cannot run"*. **The heightmap is
present on this machine** — `data/world.json` resolves, and both validators run clean against it — so that
excuse should be re-examined rather than inherited.

Next step, as a command:

```
python -m pytest -q --tb=line tests/test_gym_buildings_independent.py tests/test_legendaries.py tests/test_no_swallowed_crashes.py
```

## 3. Worktrees: cleaned, and there is still no rule

`.claude/worktrees/` held **44 directories, 7.9 GB**, 37 of them `agent-*` isolation worktrees that the
harness never reclaimed — it auto-cleans one only if unchanged, and every one of these was written to. The
app's own `clean_up_worktrees` cannot see them: `get_storage_usage` reports 4 worktrees across 3 repos,
session worktrees only.

Removed 36 (the locked `agent-a935361eae89fb3d0` left alone) and 59 stale `worktree-agent-*` branch refs.
**Now 8 directories, 4.77 GB; registered worktrees 61 → 25.** Verified safe before deleting: every agent
HEAD was reachable from `main`, this branch or the water-export branch, and all six dirty worktrees held
only redundant untracked copies — four already on `main`, and two where the committed version was strictly
newer (the holdoff test by 4 comment lines, `TOWN_TICK_BUDGET.md` by 105 lines).

Left for the owner, deliberately:

- `.claude/worktrees/canonical-data` — an empty directory, not a registered worktree.
- `.claude/worktrees/winui3-widget-board-60b59c` — a worktree of a **different repository**
  (`github/Job-Bored`) parked inside cobblers' worktree folder. `git worktree prune` here will not touch it.

**No teardown rule was added** (the owner chose removal only, 2026-09-30). So this will rebuild. If it
should not, the rule belongs in CLAUDE.md's Delegation section.

## 4. Blocked: the server lock, so no install check ran

The server is **down** — no listener on 25565, no Java process. The lock at
`C:\Users\wnd\Documents\github\.cobblers-server-agent.lock` still carries the previous run's owner line.

**The write to take it over was refused** by the auto-mode permission classifier (`Modify Shared
Resources`). Per CLAUDE.md a refusal ends the attempt, so it was not routed around by another tool — and
that also ruled out `python tools/install_check.py`, which reads the server's `config/` and `datapacks/`.
**The session-start install check has therefore not run this session.** A cold session either gets that
write permitted or does repo-only work.

## 5. Still open, unchanged by this session

All five of the previous handover's visible items stand, and the detail is in `docs/STATE.md` rather than
repeated here:

- **F12** — `route_07_trainer_01` and `route_07_trainer_04` are authored inside town boxes. The seats moved
  to legal shoulders; the authored points were deliberately left alone. **The fix is Codex's
  `TRAINER_RULES.json`; do not "correct" them from this side.**
- **The 32 settlement NPCs are unplaced**, and the number itself is unverified — it came from the owner,
  not from a file anyone has checked. **Establishing what the 32 actually are is the first job there.** The
  four Rift guards and two posts already have seats with armour-stand placeholders.
- **Four zone walls withheld by data**, not by a list: z4 needs Codex dialogue reading
  `q.player.pokedex.caught_count`; z5 needs `rift_crisis_resolved`, which still has **no setter** on
  `origin/codex/trainer-modes`. `rift_zones.py report` exiting 1 on 3 OWED is correct. Do not invent the
  setter — it is the finale's quest stage.
- **Giovanni's roster is held and empty**, blocked on the singles-versus-doubles call in
  `docs/story/GIOVANNI_FORMAT.md`. His building exists and the eighth badge is winnable against upstream's
  roster. Whatever the decision, it goes in `data/gym_trainers.json` as his `battle_format`.
- **Unproven, and only the owner can settle it: whether Brock now refuses a rematch with the badge in
  hand.** The guard is installed; installed is not working.

## 6. What a cold start must not rediscover

- **A nested isolation worktree is based on the MAIN checkout's HEAD**, far behind, and
  `git merge --ff-only` fails outright. Authorise `git reset --hard <sha>` explicitly in the brief.
- **Verify against the world, not the plan.** The pattern that worked: make the agent nominate, in advance
  and in coordinates, the seats most likely to embarrass it, then probe those over RCON.
- **"Our list is not the world"** and **"How to prove an audit is independent"** are both in CLAUDE.md.
  Read them before writing an audit or anything that enumerates our own data.
- `COBBLERS_SOURCE_ROOT` must be `C:\Users\wnd\Documents` in every shell. Both validators are clean at
  27710fd: `validate_data.py` 0 errors 0 warnings, `validate.py` 1,237 files 0 errors 0 warnings.
- The full suite takes **1,054 s** — over the 600 s tool timeout. Run it backgrounded.
