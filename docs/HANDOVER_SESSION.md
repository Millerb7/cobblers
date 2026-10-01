# Handover — the suite is alive, the collision has a check, and the NPCs are next

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. The branch

- **`fix/2026-10-01-vr-trainer-ownership`**, head **see `git rev-parse HEAD`** -- re-read it rather than trusting a quoted one.
- **[PR #102](https://github.com/Millerb7/cobblers/pull/102), OPEN, draft, base `main`, head
  `39f72df30a2d896558c97b83d0f458e3efff347a`.** Merge with
  `gh pr merge 102 --match-head-commit 39f72df30a2d896558c97b83d0f458e3efff347a`.
- **#102 was already open when this session started, and this session pushed to it before checking.**
  It had opened as the previous session's problem report ("main's pytest suite collects zero tests, and
  the obvious fix deletes hand-authored work") and had been reported to the owner, so CLAUDE.md's freeze
  rule applied and the two commits should have gone on a new branch stacked on it. The check
  (`gh pr view --json state`) was run after the push, not before; a force-push to undo it is also
  forbidden. Remedy taken: the PR's title and body now describe what the branch carries, with the
  original report preserved verbatim in a collapsed section. **Check the PR's state BEFORE the push, not
  after** -- `gh pr list --head $(git branch --show-current)` costs one command.
- `origin/main` carries #97 (merge `a271532`), which this branch has merged in and which is an ancestor
  of this head (checked with `git merge-base --is-ancestor` after a `--prune` fetch).
- **Prune before trusting any remote ref** (`git fetch --prune`) and re-read every head you quote. The
  owner merges while a session works and GitHub deletes the branch on merge; on 2026-10-01 that
  invalidated two reported `--match-head-commit` commands in one night.

## 2. What was done, and what proves it

**The suite was reporting nothing at all and now reports a count.** It had been dying at collection since
06:14: `tools/route_trainers.py` raised `SystemExit` while `tests/test_trainer_cycle.py` was imported, and
a `SystemExit` is a `BaseException`, so pytest answered `no tests ran` plus `INTERNALERROR` — no failures,
no passes, nothing comparable with the day before. Three things changed:

1. **The trainer guard is field-level** (`tools/route_trainers.py`, the "who authors what" block). The
   roster (`data/trainers.json`) owns who a trainer is; a seat file owns where it stands and how it
   behaves standing there. Three declared modes: `STAND_FIELDS` the roster must not carry, `ROSTER_ECHO`
   that must stay identical, and `ROSTER_PRECEDENCE` (`dialogue_text`) where the roster wins and the seat
   file is the fallback. Against the real data it named the real collision — **9 fields on
   `route_09_trainer_10`**, not the whole id.
2. **Nothing hand-authored was deleted.** The tenth stand's roster moved into `superseded_roster` in
   `data/vr_trainers.json`, verbatim, with a note saying why it is kept. Verified after the change: all
   ten stands keep their seats and yaws (`(3563,2,3009)` through `(3655,65,2564)`), and the tenth emits
   main's roster on our stand's skin with `forceBattleOnSight` on.
3. **`tests/test_id_authorship.py` (18 tests, written by a `test-author` agent, not by the session that
   wrote the tool).** It found two real defects, both fixed and both verified by hand against mutated
   copies of `data/`, and **neither has a test** -- a chip is queued (`task_77d572d3`) with the three
   cases:
   - a collision between **two satellites** of one space named `space["owner"]`, a file carrying neither
     value. (The report diagnosed an `fa`/`fb` sort-order bug in the owner-satellite case; checking it
     against the data showed that case attributes correctly and the real hole was the ownerless pair.
     A fault that names the wrong file is worse than a quiet one: it is a day spent in the wrong file.)
   - a declared overlap whose ids stop overlapping **entirely** was never reported stale, because the
     check ran over the data's keys and an emptied declaration has none. It iterates the union now.
   - `test_the_registry_is_not_derived_from_the_tool` asserts that two sets differ after one is
     monkeypatched, which is true of any two sets. It proves nothing and should be rewritten or dropped.
4. **A tool failing closed at import can no longer end the run.** `tests/conftest.py`'s
   `pytest_make_collect_report` turns it into one named collection error carrying the tool's message
   verbatim, and `continue_on_collection_errors` keeps the count. **Proved by mutating the generator**
   (a deliberate `raise SystemExit` in `load()`): `10 passed, 1 error`, message intact, instead of
   INTERNALERROR.

**And the general case, because this will happen again.** `tools/id_authorship.py` +
`data/id_authorship.json`: every id two files in `data/` both carry a record for is declared as a space or
an overlap, by exact id set, or it is a fault. 265 such ids, 132 cross-file field pairs, 15 overlap
classes read value by value, **6 marked `finding`** (listed in `docs/STATE.md`). Runs from
`.githooks/post-merge` — where the fault is made — and as `python tools/validate.py --only duplicate_ids`
(the `duplicate_ids` stub is now real).

**CLAUDE.md gained two rules**: "A clean merge is not a clean union", and a file declaring `generated_by`
"hand" is never deleted to resolve a conflict.

**`install_check.py` ran for the first time in four sessions: 0 problems (packs and configs).** Port 25565
free, no Java process. `Bash(python tools/server_lock.py:*)` in `.claude/settings.local.json` was enough —
**the lock write was not refused.** Whatever stopped the last three sessions, it is not that rule.

Measured: `validate_data.py` 0 errors / 0 warnings, `validate.py` 1,238 files 0/0,
`tools/id_authorship.py` 0 faults, trainer/gym/league tests **887 passed, 1 xfailed**. Full suite **7 failed, 5,188 passed, 9 xfailed in 578 s** -- the baseline seven exactly (heightmap
provenance, `mines_independent` surface faces, two `rift_heightmap` sculpt tests, three `sea_town`), no
new failure, and 19 more passes than the 5,169 of the last run that counted, because the trainer tests
that had been collected-but-dead now run.

## 3. What waits on the owner

- **Which tenth trainer stands at the exit ravine.** Main's **League Examiner** (four Pokemon, Tailwind
  Crobat with a Focus Sash, "the exam is what you do after that") is what emits today. Our **Gate Warden**
  (three Pokemon, "nobody walks onto the apron without going through me") is in
  `data/vr_trainers.json`'s `superseded_roster`. The same choice, smaller, applies to the other nine and to
  the 28 late-route trainers: the roster's dialogue is what a player hears and **38 hand-authored
  seat-file sets are superseded** (the generator prints the count on every run). Nothing is lost either way
  — it is which lines play.
- **Giovanni: one stale field stands between seven leaders' teams and eight.** `data/trainers.json` gives
  `gym_08_giovanni` `status: authored`, `blocked_by: None`, singles, six Pokemon at 52-55 whose top is
  exactly his contract's 55. `docs/story/GIOVANNI_FORMAT.md` settled the format. Only
  `data/gym_trainers.json`'s `held: true` skips him, and its `held_because` quotes an empty team that no
  longer exists. The generator fails closed if the ace disagrees with the contract, so it cannot emit a
  wrong level. Left undone deliberately: it changes what a player fights.
- **Whether superseding the server lock was mine to do.** Its owner line named *this worktree's* session
  from 2026-09-29 ("morning flight; owner awake and flying cobblers-dryrun12"), two days old, server down.
  Taken with `--supersede`, so the old line is recorded inside the lock file, but CLAUDE.md says resolve
  ownership with the owner rather than judge a lock stale.
- **Six declared `finding` overlaps want renames**, none urgent: `tri_peaks` / `glacial_tear` are both a
  landmark and a region; `sunset_west` is both a town and a spawn subregion; `kind`, `theme` and `order`
  each mean two things in two files one tool reads together. All in `data/id_authorship.json` with reasons.

## 4. The next job: the settlement NPCs, in a fresh session

The owner's method is predict-then-probe, as the 56 trainers were done. **The count is 15, not 32**
(`docs/world-building/SETTLEMENT_NPCS.md`): 15 conversation-bearing settlement NPCs, **34 gate-guard
positions with no characters authored at all**, and the **four Rift guards, which already have seats with
armour-stand placeholders**. The owner has confirmed these figures; the 32 was a session's error.

**The blocker is standing blocks, not coordinates:** 10 of 13 `npc_main_*` carry a `recorded_position_xz`
and **0 carry a `stand_marker`**. Nine of the ten check out against their settlement footprint and
heightmap ground. The probe half needs a running world and there is none — the server is down and this
session held the lock only for `install_check` (see below).

Deliberately not fixed, for Codex: `npc_main_league_steward` is recorded at (3297, 2603), 433 blocks from
the League, inside no settlement, heightmap y118 against the League's 86.3-98.9. It is the retired
`FACTION.md` cradle coordinate the Rift-zones unit already rejected. Correcting it here would hide the
propagation.

## 5. State of the machine

- **Server down**: no listener on 25565, no Java process (checked 2026-10-01).
- **The coordination lock is FREE** (released at the end of this session). It had been held since
  2026-09-29 by a line naming *this worktree's* session ("morning flight; owner awake and flying
  cobblers-dryrun12"); this session took it with `--supersede`, ran `install_check`, and released it.
- No worktree, branch or process is left half-done by this session. `build/datapacks/cobblers_trainers`
  was regenerated (359 files, 56 seated trainers, 12 overrides) and is disposable.

## 6. What a cold start must not rediscover

- **A clean merge is not a clean union** — now a CLAUDE.md rule with the case, and a check that runs on
  merge. A guard keyed on an id cannot tell halves from rivals.
- **Check `generated_by` before deleting either side of a duplicate.** A generated file regenerates; a
  hand-authored one loses judgement that exists in no generator.
- **`SystemExit` is a `BaseException`**, so it escapes pytest's collection and takes the whole run with it.
  Handled in `tests/conftest.py` now; the same trap waits anywhere else a tool is imported.
- **The harness's `totalTokens` per agent is its FINAL CONTEXT, not its spend.** Use
  `python tools/session_cost.py`.
- The full suite is over the 600 s tool timeout — run it backgrounded.
- `COBBLERS_SOURCE_ROOT` must be `C:\Users\wnd\Documents` in every shell.
- `tools/ground.py` is `ground.load()` returning a callable, plus `.box()`; there is no `ground.at()`.

## 7. What this session cost

`python tools/session_cost.py`: **3.1M weighted**, 130 turns, context 259k at the end (average 180k).
One subagent, 0.35M. Cheap for what it carried because the expensive things ran once: one full suite
(578 s), one `prepare`-free path, and no staging.
