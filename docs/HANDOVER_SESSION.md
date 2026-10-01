# Handover — #97's suite is DEAD, and one deletion must not be made

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 0. STOP: the whole pytest suite collects ZERO tests on `build/2026-09-29-phase2`

`origin/main` was merged into #97's branch on 2026-10-01 (merge commit **`2e0487f`**). The one textual
conflict (`data/progression.json`) was resolved correctly as a union -- 131 shared entries identical, 39 ours,
7 theirs (`ambient_stone_tips` cursors), zero content clashes, purely additive, validators clean.

**But git auto-merged a SEMANTIC collision it could not see.** Victory Road's ten fights,
`route_09_trainer_01..10`, are now authored twice:

- **ours**, `data/vr_trainers.json` -- the STAND: `seat`, `yaw`, `faces`, `eye_contact`, `sight_distance`,
  `skin`, `stand_index`, and a written `unavoidable` rationale per stand. Only 1 of 10 carries a team.
- **main's** (#96), `data/trainers.json` -- the ROSTER: `team`, `format`, `archetype`, `lesson`, `modes`, and
  a `placement` block carrying `x`/`z`/`sampled_y` whose `placement_authority` is
  *"data/vr_caves.json trainer stand"* -- the same stands, same coordinates.

`tools/route_trainers.py:125` raises `SystemExit("data/vr_trainers.json re-authors %s, which
data/trainers.json already has")`. That escapes during pytest COLLECTION, so the suite reports
**`no tests ran`** and an `INTERNALERROR`, not a failure count. **Nothing is being tested on this branch.**
Fix this before trusting any other result here.

### Do NOT resolve it by deleting either file's ten

The owner chose "keep main's, drop ours" on 2026-10-01 **while both sides were believed to be duplicates.**
They are not, and the session checked twice before acting:

1. First worry -- that dropping ours loses the coordinates -- was **wrong**: main carries `x`/`z`/`sampled_y`
   with the same values. (An earlier check missed them only because main stores x/z as separate keys, not an
   array.)
2. Second check was the decisive one: `data/vr_trainers.json` declares
   `generated_by: "hand, from derived/vr_caves/plan.json 'stands' (tools/vr_caves.py place_fights)"`.
   **Hand-authored, not generated.** Deleting it destroys `yaw`, `faces`, `eye_contact`, `sight_distance`,
   `skin` and the per-stand `unavoidable` rationale -- which way each trainer faces, whether it initiates on
   sight, how far it sees, its texture, and why each stand is unavoidable. `seat` and `stand_index` are
   re-derivable from `derived/vr_caves/plan.json`; **the judgement is not.** Seated without it, the ten face
   arbitrary directions with no eye-contact behaviour.

So **no deletion was made.** The real fix is the guard's assumption, which #96 invalidated: the two files are
no longer rival authors but two halves -- main owns the roster, ours owns the stand behaviour. Options, the
owner's to pick:

- **(recommended) Teach the guard the split.** `tools/route_trainers.py` reads the roster from
  `data/trainers.json` and the stand fields from `data/vr_trainers.json`, and the guard fires only on a field
  authored in both. Keeps every field, needs a small change to the tool and one line in `vr_trainers.json`
  saying it no longer authors trainers, only stands.
- **Port then delete.** Move the six behavioural fields into main's `placement` block for each of the ten,
  then drop `data/vr_trainers.json`. Loses nothing, but edits `data/trainers.json`, which is Codex's.
- **Delete ours anyway**, accepting the loss, and re-derive facing and sight by hand later. Cheapest now,
  most expensive later, and the rationale text is simply gone.

Already cleared by the merge: `vr_trainers.json`'s own note said the ten `quest.<id>.defeated` fields were
undeclared in `data/progression.json` as of 2026-09-30, which would have made `route_trainers.py` refuse to
emit them. **This branch declares all ten.**

## 0b. Also arrived with main: Giovanni is unblocked

`docs/story/GIOVANNI_FORMAT.md` records the decision -- **singles** -- and `data/trainers.json`'s
`gym_08_giovanni` is now `status: authored`, a team of 6, `blocked_by: None`. The long-standing "Giovanni's
roster is held and empty" item is **closed by main**. Two loose ends: `tools/route_trainers.py`'s own comments
(lines 19 and 140) still describe him as held with an empty team, and **whether his override actually emits is
unverified** -- it needs a `prepare` run, which has not happened since the merge. If it does emit, all eight
leaders carry our teams rather than seven.

## 0c. The NPC placement: the count is wrong and the method needs a world

The owner asked for "the 32 settlement NPCs and four Rift guards" placed, predict-then-probe as the 56
trainers were. **There are not 32** (`docs/world-building/SETTLEMENT_NPCS.md`, merged as #99): `32` appears
nowhere in the repository. The real figures are **15** conversation-bearing settlement NPCs (13 `npc_main_*`
plus Pallet's Hank and Lena), **34** gate-guard positions with no characters authored at all, and the **four
Rift guards, which already have seats with armour-stand placeholders**.

**The blocker is standing blocks, not coordinates:** 10 of 13 carry a `recorded_position_xz` and **0 carry a
`stand_marker`**. Nine of those ten check out against their settlement footprint and heightmap ground.

The owner's decision (2026-10-01): **fix the lock permission first, then place in a fresh session.** The
probe half of the method needs a running world, and there is none -- which is section 1.

## 1. FIRST: `install_check.py` has not run for three sessions. Fix the permission, do not skip it again

**This is the check that catches built-but-never-installed, and it has been blind since Monday.**

The cause is the same every time: the session-start gate needs the shared lock at
`C:\Users\wnd\Documents\github\.cobblers-server-agent.lock`, and **the write to take it over is refused by the
auto-mode permission classifier** (`Modify Shared Resources`). Per CLAUDE.md a refusal ends the attempt, so it
is correctly not routed around — and `tools/install_check.py` reads the server's `config/` and `datapacks/`,
so it dies with the gate. Three sessions have now started repo-only and skipped it.

**Do not skip it a fourth time.** Get the lock write permitted properly — a Bash permission rule for that one
path, or the owner taking the lock over by hand before the session starts — then run, as CLAUDE.md requires:

```
python tools/install_check.py --server-dir C:/Users/wnd/Documents/github/cobblers-server
```

Why it matters, in the repository's own words: work done in the repo that never reached the running game has
happened **four times** — the spawn tables; five config overlays, starters among them; the re-apply steps; and
the structures pack, present only because it had been copied by hand. The leaders' teams (F11) were the fifth.
This check is what stands between that and a sixth. A session that cannot run it should say so loudly rather
than quietly doing repo work, which is what the last three did.

Current server state: **down** — no listener on 25565, no Java process. The lock still carries the
2026-09-29 owner line.

## 2. SECOND: the demolish coverage gap, and the general question behind it

The chip is queued (`task_29e9ef92`) with the full brief and seven properties worth protecting. **It must go
to a `test-author` agent**: the session that found the gap also changed `tools/gym_demolish.py`, so it must
not write its first test.

**The general finding, which is worth more than the one tool.** On 2026-10-01 marking gyms 6 and 8
`superseded_by` made `gym_demolish.py` fail-closed with `SystemExit` — step R16F would refuse to build
anything. A full suite run in that state reported `7 failed, 5169 passed, 9 xfailed`: **identical, test for
test, to a healthy run.**

> A suite that reports identically whether a step works or fail-closes is not covering that step.

It was found by reading the consumers of a field that had changed and running the tool by hand. No check
noticed.

**So the unit is not just one test file. Ask which other `reapply.py` steps have the same hole.** `prepare`
fail-closes on several conditions and every block pass is a generated-mcfunction step; the question for each
is whether anything in `tests/` would go red if that step refused to emit. The cheap probe is the one that
worked here: break the step deliberately, run the suite, and see whether the numbers move. Where they do not,
that step is uncovered. Candidates to start from are the steps with their own audits run by `prepare`, since
an audit that is never asserted on is the same shape of gap.

## 3. The PRs: everything collapsed into #97, which is the only one open

Verified against GitHub after a `--prune` fetch, not assumed:

| PR | Branch | State |
|---|---|---|
| #95 | `night/2026-09-29-water-export` | MERGED to main, 2026-10-01 04:22 |
| #96 | `codex/trainer-modes` | MERGED to main, 04:23 |
| #98 | `docs/2026-09-30-phase2-handover` | MERGED into `build/2026-09-29-phase2`, 04:25 |
| #99 | `docs/2026-09-30-settlement-npcs` | MERGED into `build/2026-09-29-phase2`, 04:26 |
| #100 | `fix/2026-09-30-phase2-red-tests` | MERGED into `build/2026-09-29-phase2`, 06:05 (merge commit `cc9a8339`) |
| [#97](https://github.com/Millerb7/cobblers/pull/97) | `build/2026-09-29-phase2` -> `main` | **OPEN**, head **`cc9a833`** |

- **The stack is gone: #97 is now one PR carrying the whole batch**, which is what the one-big-PR rule wanted.
- **Every earlier merge command for #97 is stale** — it was reported at `27710fd`, then `7b008b6b`, now
  `cc9a833`. Re-read the head before quoting it (CLAUDE.md now says why).
- `origin/main` was `ac6487e` at the time of writing; #97 is not merged.
- This branch, `docs/2026-10-01-handover`, carries only this file and the CLAUDE.md line, and targets
  `build/2026-09-29-phase2`.

## 4. The suite baseline is 7

**Measured 2026-10-01: `7 failed, 5169 passed, 9 xfailed in 641 s`.** The four failures that were phase-2's
own are fixed, and `no_swallowed_crashes` with them, so the baseline dropped from 8. The seven remaining are
pre-existing and still not to be chased: heightmap provenance, `mines_independent` surface faces, two
`rift_heightmap` sculpt tests, three `sea_town` tests (contracts C3 and C14).

How they were fixed is in `docs/STATE.md`; the short version is that none was fixed by moving a number. The
gym pair was a hardcoded five in the test while the tool globbed the folder, so gyms 6 and 8 were unexamined
for a day — they then passed all 117 content properties. The legendaries pair lost their "unsited" exemplar
when `registeel` was sited; the exemplar now comes from the data, and the one whose fault had been closed was
replaced by the direction nothing covered, that `gate.unsatisfiable_until` is honoured — proved by mutating
the generator.

## 5. Decisions taken this session that a cold start should not reopen

- **Gyms 6 and 8 are confirmed** (the owner, 2026-10-01) and `data/gym_interiors.json` records both
  superseded. **gym6's `why_not` had been an owner gate** — Sabrina's gym not built until EXP-034 has run —
  and **EXP-034 is still unrun**; the gate is answered because the Hall of Lenses carries no per-player state,
  not by the experiment. If anyone wants it honoured literally, that is the decision to revisit. gym8's
  `"as gym2"` was stale: Giovanni's was a donor shell.
- **The worktree cleanup was removal only, with no teardown rule** (the owner's choice). `.claude/worktrees/`
  went 44 directories / 7.9 GB -> 8 / 4.77 GB. It will rebuild; if it should not, the rule belongs in
  CLAUDE.md's Delegation section. Left alone: the locked `agent-a935361eae89fb3d0`, the empty
  `canonical-data`, and `winui3-widget-board-60b59c`, which belongs to the **`Job-Bored`** repo.

## 6. Open, and not this session's to fix

- **The settlement NPCs are 15, not 32** (`docs/world-building/SETTLEMENT_NPCS.md`). The blocker is
  **standing blocks, not coordinates**: 10 of 13 actors have a position, **0 have a `stand_marker`**. The bulk
  is 12 physical-evidence objects, 10 unbuilt. Separately **34 gate-guard positions have no characters**.
- **For Codex, deliberately not fixed:** `npc_main_league_steward` is recorded at (3297, 2603) — 433 blocks
  from the League, inside no settlement, heightmap y118 against the League's 86.3-98.9. It is the retired
  `FACTION.md` cradle coordinate the Rift-zones unit already rejected for (3357, 3306). Correcting it here
  would hide the propagation.
- **F12** — two authored trainer points inside town boxes; seats moved, authored points left alone. Codex's
  `TRAINER_RULES.json`.
- **Four zone walls withheld by data:** z4 needs Codex dialogue reading `q.player.pokedex.caught_count`; z5
  needs `rift_crisis_resolved`, which has **no setter** on `origin/codex/trainer-modes`. Do not invent it.
- **Giovanni's roster held and empty**, blocked on `docs/story/GIOVANNI_FORMAT.md`; the decision goes in
  `data/gym_trainers.json` as his `battle_format`.
- **Unproven, owner only: whether Brock refuses a rematch with the badge in hand.** Installed is not working.

## 7. What a cold start must not rediscover

- **Prune before trusting a remote ref, and re-read every head you quote** — now a CLAUDE.md rule, with the
  2026-10-01 case that produced it.
- **Read the consumers of any field you change.** One `superseded_by` edit fail-closed a build step.
- **Mutate the generator, not the record**, and reject your own slack.
- **A nested isolation worktree is based on the MAIN checkout's HEAD**; `git merge --ff-only` fails.
  Authorise `git reset --hard <sha>` in the brief.
- The full suite is **~640-1,050 s** — over the 600 s tool timeout. Run it backgrounded.
- `tools/ground.py` is `ground.load()` returning a callable, plus `.box()`; there is no `ground.at()`. It
  raises `terrain.TerrainUnavailable` when the heightmap is missing.
- `COBBLERS_SOURCE_ROOT` must be `C:\Users\wnd\Documents` in every shell. Both validators are clean at the
  tip: `validate_data.py` 0/0, `validate.py` 1,237 files 0/0.
