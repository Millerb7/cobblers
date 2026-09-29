# Morning report, 2026-09-29

Written through the night as things landed. `docs/NIGHT_REVIEW.md` holds every decision taken without you and why.

## What landed

### Phase 1 — experiments and measurements

- **EXP-047, the pocket dimension: it works.** A custom dimension registers, loads with no new error, is writable
  and holds entities. Three results that shape the portal design:
  - **Our per-tick systems reach it for free.** A selector with no positional constraint is not dimension-scoped
    here — a kill run `in minecraft:overworld` destroyed an entity in the pocket dimension. So the blackout tick,
    the water ladder, the trainer cycle and the progression checks all apply to a player there with no change. And
    anything positional (a habitat block's range, a trainer seat) is confined for free. The flip side: a global
    selector also reaches *into* it, so anything meant to be overworld-only needs an explicit dimension predicate.
  - **Its contents do not survive a re-export.** The blocks live at `<world>/dimensions/`, inside the world folder,
    and a re-export makes a new one while only players are carried. **Your hypothesis is disproved as things stand
    — but the refinement is better than the negative:** a pocket dimension is the *only* part of the world that
    could be carried verbatim by a folder copy, because nothing regenerates it. Extending `reapply.py carry` to copy
    `dimensions/` would make it true, and it is a small change.
  - Spawning, habitat-pool resolution and the callbacks **need a player** and are recorded untested, not assumed.
- **The villager is measured: ~20 us a tick** (swept 0-64 in the empty pocket dimension, nobody online). So ~220
  villagers reach 10% of a tick and a 40-50 villager town costs ~2%. Villagers are not the constraint. **`T`, the
  rctmod trainer, is still unmeasured** — it cannot be plain-`summon`ed, and the sweep stopped rather than report a
  number from an empty pen.
- **`/tick query` prints to 0.1 ms**, confirmed, so every single-entity figure is multiply-and-divide.
- **The water ladder: 35 command lines a tick down to 7** on the dry path, with the two `effect clear` commands off
  it entirely. Contracts C1 and C2 green, 337 tests green. Vanilla air on land now runs from a
  `minecraft:effects_changed` advancement, and the wet path still clears unconditionally so the rule cannot break in
  water. **The land clear is unverified in game** — that is the one behaviour this could regress.

### Phase 2 — content

- **The trainer rematch fault is fixed (interim)** and the strict xfail that pinned it is gone, removed because the
  fix made it pass and `XPASS(strict)` forced the cleanup. `test_trainer_cycle.py:175`, which asserted the buggy
  clause as correct, is rewritten with a guard against its return.
- **Legendaries: six chambers built, four blocked by name.** Audit 376 checks, 0 failures, proved fail-closed on six
  tampered inputs. See the review list — five gates are a proposal, not your decision, and there are two new Celebi
  faults.
- **Stone faces re-sited into their towns**, rebuilt, audit CLEAN (22 faces, 13,953 cells). One face had to be
  re-anchored after the repaint put trees over it.

### Phase 3 — the export

- **`cobblers-dryrun12` is built**, `seed_match: true`, and the **margin relief ran for the first time** (7,056
  tiles) — the seamounts and the carried-off map edge have never existed in a world before tonight.
- **The water shape is applied**: 19,027,615 columns changed, the new heightmap is canonical, and the old sha is
  kept in `previous_sha256`, so it is reversible.
- Its dependents were re-measured until `validate_data` read **0 errors**: Pacifidlog folded onto its new site,
  regions, cells and town grounds re-measured, the paint regenerated, the visibility claims re-measured.
- **Prepare's whole-build gate passed**: 4,468 function files, 0 problems, 26 places, 32 pack donors, 35 steps,
  every function pack covered.
- **Install is clean**: every pack and config the repo builds is installed and current.
- The re-application over RCON, the audit and the Distant Horizons pregen follow.

**Region count, explained rather than waved through.** 454 files where the old world has 491 and the runbook names
484. Inside the border 390 of 400 are present; the 10 absent are the far-north sea strip beyond the authored
landmass, empty ocean WorldPainter had nothing to write for, and the pregen is the step that fills them. The 37 the
old world has extra are spill from having been played.

**Three things the export broke, all caught by fail-closed audits and fixed rather than bypassed:** the drowned
Pacifidlog docks and the Sound ferry (retired per the plan STATE already recorded), a stone face under the new
canopy (re-anchored), and the Route 2 shrine (moved clear of both the new shore and the new trees). A fourth, the
now-orphaned ferry charge macro, was caught by prepare's own orphan gate.

## What was cut, and why

See `docs/NIGHT_REVIEW.md`. In short: the Viltri Ravine (held by you, never in the audited design), `build_routes`
(audit C2 proves no road changed), the employed-villager sweep, `T`, both two-player measurements (second account),
and everything player-gated in EXP-047.

## Cost per agent (context x turns, `tools/session_cost.py`)

| agent | turns | weighted |
|---|---|---|
| Legendary placements and gates | 114 | 3.21M |
| Stone faces survey and redesign | 116 | 2.60M |
| Gym interiors data and gym 1 | 89 | 2.07M |
| Design eight gym interiors | 39 | 1.11M |
| Town tick-cost inventory and plan | 69 | 0.90M |
| Water ladder early exit | 49 | 0.64M |
| Failing test for the rematch fault | 21 | 0.23M |

The main session is the expensive one, as always.
