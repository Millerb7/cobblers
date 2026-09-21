# experiments/

Each design question that could sink the campaign gets an experiment before we
build on it. An experiment is a folder `EXP-NNN-short-name/` with a `README.md`
following the template below, optional `runs/` captures, and a `results.md`.

Experiments are cheap and disposable. They prove or disprove one thing; they
are not features. Decisions they produce are recorded in `docs/decisions/`.

| Id | Question | Status |
|----|----------|--------|
| EXP-000 | Does the Cobbleverse base boot on Cobblemon 1.8 with our overlay? | procedure written, not yet run |
| EXP-001 | Can F4 Route 1 feel authored through curated encounters and Relic Island? | separate 1,000-block F4 world ready for client playtest; spawn proof pending |
| EXP-002 | Can we build a genuinely difficult trainer battle? | stub |
| EXP-003 | Can we enforce a level cap? | stub |
| EXP-004 | Can we build a trainer gauntlet with restrictions? | stub |
| EXP-005 | Can we build a puzzle dungeon with persistent state? | stub |
| EXP-006 | Can we place a static, authored encounter? | stub |
| EXP-007 | Can we track story progression? | stub |
| EXP-012 | Can default spawns be suppressed inside route corridors only? | run: `anticonditions` (plural) on every inherited file, generated for 1,408 boxes; corridor 54% → 97.6% curated; +8 s boot, +1.5 GB heap, no tick cost; global off not needed |
| EXP-013 | Does any in-game placement method give hand-placed builds structure data, and what reads it? | run: no method writes structure data; D (player) confirms a pasted village is not a village to Cobblemon; E (player) trainer spawners work in pasted and command-set builds |
| EXP-014 | Can WorldPainter place Cobblemon ores, apricorn trees and berries? | run headless: ores via Underground Pockets (not Resources), objects via Sponge v2/.nbt; in-game load check done in EXP-017 |
| EXP-017 | What Pockets settings match modded ore density, and do exported Cobblemon block entities survive loading? | run: pockets need frequency 1 + NOISE host dilution (measured within ~±25 %); berry/habitat data survive load and save; leaf decay, growth, spawns need a player |
| EXP-019 | What shape do Cobblemon's apricorn trees generate, and do villagers work in a built plot? | run headless: one frame for all colours (trunk 5, 5×5 corner-cut canopy, 5-8 fruit facing their leaf); villagers took jobs, rolled trades and bred without structure data |
| EXP-020 | Can a datapack flag drive waystone unlocks, and can Xaero's show them? | run headless: `waystones activate/forget` compile in level-2 functions; `rctmod:defeat_count` and `any_block_use` advancements load; activation stat unusable; no Xaero waypoint packet, but built-in Waystones markers and chat shares exist. Player part F not run |
| EXP-024 | Can everything authored be re-applied after a re-export? | run: staging export (484 regions, seed carried) then R0-R10 re-applied and checked; Brock's gym re-placed from the installed pack; 0 gaps in the hometown; the live export still to do |
| EXP-023 | What mechanism can hold a sleeping Celebi in the sapling? | run: Pokemon entity gives uncatchable, unbattleable, immobile, persistent and a sleep pose, but a player can still kill it and data-driven interactions do not fire for a wild Pokemon; parked |
| EXP-022 | Can campaign dialogue run on Cobblemon's native dialogue with persistent per-player state? | run single-player: compiled thirsty stranger; disconnect restores the cursor; bucket and bottle consumed and returned; reward once; two-player not run |
| EXP-021 | Do Habitat Blocks replace or add, how far, do they persist and stack? | run: replace; edge at the configured range; survive restart, lost on re-export unless transplanted or re-placed; overlapping ranges spawn nothing; command-placed blocks need a chunk reload |

## Template

```markdown
# EXP-NNN: <title>

## Objective
One paragraph. What question does this answer? What would "yes" unlock?

## Success criteria
Bullet list. Observable, testable in-game or in logs.

## Dependencies
Mods / datapacks / tools / other experiments this needs. Versions.

## Implementation
What was built, where it lives (paths), how it is configured.

## Test instructions
Step by step, so someone else can reproduce: server setup, commands, what to look at.

## Results
What actually happened. Link `runs/<timestamp>/` captures. Screenshots if useful.

## Limitations
What this does NOT show. Edge cases not covered (multiplayer, restarts, ...).

## Decision
Adopt / adapt / reject, and why. Link the `docs/decisions/` record if one was written.

## Follow-up
Next experiments or tasks this unlocks or requires.
```
