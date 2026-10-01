# Handover — the baseline is 7, and a build step nobody tests

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

Three units: the overdue phase-2 PR, the settlement-NPC count, and the four red tests. ~150 turns, context
over 300k, **~4M weighted** — against 42.9M for the 2026-09-30 run. Handing over on the cost rule.

## 1. The PR stack — four drafts, merge bottom-up, each pinned

Nothing is merged. **#97 inherits 38 commits from #95 and must not merge before it.**

| PR | Branch | Base | Head |
|---|---|---|---|
| [#95](https://github.com/Millerb7/cobblers/pull/95) | `night/2026-09-29-water-export` | `main` | `5230051ed2d24d1c3b7c13b0a171159b44653b5c` |
| [#97](https://github.com/Millerb7/cobblers/pull/97) | `build/2026-09-29-phase2` | `main` | `27710fdb82085d06d5cb01229b4651d2ba75b70a` |
| [#98](https://github.com/Millerb7/cobblers/pull/98) | `docs/2026-09-30-phase2-handover` | #97 | `3bf300b056c2b7037f261bb3fc9ebbd4a7e11ee2` |
| [#99](https://github.com/Millerb7/cobblers/pull/99) | `docs/2026-09-30-settlement-npcs` | #98 | `3a1aff32f818a076adffc33dcba77caf8a194594` |
| #100 | `fix/2026-09-30-phase2-red-tests` | #99 | see §5 |

**The stack contradicts the owner's own rule** ("one big PR per batch, not a stack"). It grew because each
PR opened before the next unit began, and a reported branch is frozen. **If one PR is wanted, the three doc
and fix branches squash onto #97** — worth settling before any of it merges.

## 2. The suite baseline is 7, not 8 or 12

**Measured 2026-10-01 at the fix branch: `7 failed, 5169 passed, 9 xfailed in 641 s`.** All four failures
that were phase-2's own are fixed, and `no_swallowed_crashes` with them. The remaining seven are
pre-existing and still not to be chased: heightmap provenance (`water_shaped_from` undocumented),
`mines_independent` surface faces, two `rift_heightmap` sculpt tests, three `sea_town` tests (the
sea-town/ferry migration that contracts C3 and C14 record).

How each was fixed, none by moving a number until it passed — the detail is in `docs/STATE.md`:

- **The gym pair** was one hardcoded `GYMS = (gym1, gym3, gym4, gym5, gym7)` in the test while
  `tools/gym_buildings_independent.py` has always globbed the folder. The tool audited gyms 6 and 8; the
  tests never looked. `GYMS` now reads the folder, and **gyms 6 and 8 pass all 117 content properties**.
- **The legendaries pair** shared one cause: `registeel` was their "unsited" exemplar and #97 sited it. The
  exemplar now comes from the data. The one whose live fault that siting **closed** was replaced by the
  direction nothing covered — that a correct `gate.unsatisfiable_until` is honoured — proved by mutating
  the generator (`admitted = []`), then reverted.
- **`no_swallowed_crashes`** was right about two `except BaseException` fixtures; both now catch
  `terrain.TerrainUnavailable`, and the skip path is verified with `COBBLERS_SOURCE_ROOT` unset.

## 3. THE NEXT UNIT: `tools/gym_demolish.py` has no test at all

**A full suite run with the demolish step fail-closed on gym6 still reported `7 failed, 5169 passed` — the
identical numbers to a healthy run.** Nothing exercises `superseded()` or the demolition's selection, so
step R16F could refuse to build and the suite would stay green. It was found by reading the consumers of a
changed field and running the tool by hand, not by any check.

A chip is spawned (`task_29e9ef92`) with the full brief and the seven properties worth protecting. **It must
be a `test-author` agent**: this session changed that tool, so it must not write its first test. Check the
chip before starting in case it is already running.

## 4. Gyms 6 and 8: confirmed, with the gate answered by design not by experiment

The owner confirmed both on 2026-10-01, so `data/gym_interiors.json` records them `superseded_by` and the
strict xfail is gone. Two things a cold start should not have to re-derive:

- **gym6's `why_not` was an owner gate** — Sabrina's gym not built until EXP-034 has run, being the only
  per-player puzzle. **EXP-034 is still unrun.** The gate is answered because the Hall of Lenses carries no
  per-player state, so the machinery it protected against is not in the building. If anyone later wants the
  gate honoured literally, this is the decision to revisit.
- **gym8's `why_not` was `"as gym2"`, and that was stale.** Giovanni's was a COBBLEVERSE donor shell, not
  Misty's carved interior. Corrected.
- Marking them superseded **fail-closed `gym_demolish.py`**, which demanded both `dig` and
  `shell.expect_box`. Each now declares `works_existed: false` (absence declared, never inferred from a
  missing key) and carries a `shell.expect_box` derived from `data/placements.json` — the source gym1 uses,
  never the building's own record. The tool re-derives it and agrees.

## 5. Also done this session

- **The settlement NPCs are 15, not 32** (`docs/world-building/SETTLEMENT_NPCS.md`, PR #99). The figure 32
  appears nowhere in the repository. The blocker is **standing blocks, not coordinates**: 10 of 13 actors
  have a position, **0 have a `stand_marker`**. The bulk of the work is 12 physical-evidence objects, 10
  unbuilt. Separately, **34 gate-guard positions have no characters at all** (Codex's).
- **Defect for Codex, deliberately not fixed:** `npc_main_league_steward` is recorded at (3297, 2603) —
  433 blocks from the League, inside no settlement, heightmap y118 against the League's 86.3–98.9. It is the
  retired `FACTION.md` cradle coordinate the Rift-zones unit already rejected for (3357, 3306). **Codex
  corrects it upstream**; moving it from this side would hide the propagation.
- **Worktrees cleaned once:** `.claude/worktrees/` 44 directories / 7.9 GB → 8 / 4.77 GB; registered
  worktrees 61 → 25. Nothing lost (every agent HEAD was reachable; all dirty files redundant). Left alone:
  the locked `agent-a935361eae89fb3d0`, the empty `canonical-data`, and `winui3-widget-board-60b59c`, which
  belongs to the **`Job-Bored`** repo. **No teardown rule was added**, so it will rebuild.

## 6. Blocked: the server lock, three sessions running

Server **down** — no listener on 25565, no Java process. The lock at
`C:\Users\wnd\Documents\github\.cobblers-server-agent.lock` still carries the 2026-09-29 owner line.
**The write to take it over is refused** by the auto-mode classifier (`Modify Shared Resources`), and per
CLAUDE.md a refusal ends the attempt, so it has not been routed around. That also rules out
`tools/install_check.py`. **The session-start install check has not run for three sessions.** Either get
that write permitted or stay repo-only.

## 7. Still open, untouched

- **F12** — two authored trainer points inside town boxes. Seats moved to legal shoulders, authored points
  left alone. **Codex's `TRAINER_RULES.json`.**
- **Four zone walls withheld by data:** z4 needs Codex dialogue reading `q.player.pokedex.caught_count`;
  z5 needs `rift_crisis_resolved`, which has **no setter** on `origin/codex/trainer-modes`. Do not invent it.
- **Giovanni's roster held and empty**, blocked on `docs/story/GIOVANNI_FORMAT.md`. The decision goes in
  `data/gym_trainers.json` as his `battle_format`.
- **Unproven, owner only: whether Brock refuses a rematch with the badge in hand.** Installed is not working.

## 8. What a cold start must not rediscover

- **A nested isolation worktree is based on the MAIN checkout's HEAD**; `git merge --ff-only` fails.
  Authorise `git reset --hard <sha>` in the brief.
- **Mutate the generator, not the record**, and reject your own slack. Both proved their worth this session:
  the legendaries admission path was only provable by mutating `legendaries_audit.py`.
- **Read the consumers of any field you change.** One `superseded_by` edit fail-closed a build step and no
  test noticed.
- The full suite is **~640–1,050 s** — over the 600 s tool timeout. Run it backgrounded.
- `tools/ground.py` is `ground.load()` returning a callable, plus `.box()`; there is no `ground.at()`.
  It raises `terrain.TerrainUnavailable` when the heightmap is missing.
- `COBBLERS_SOURCE_ROOT` must be `C:\Users\wnd\Documents` in every shell. Both validators clean at the tip.
