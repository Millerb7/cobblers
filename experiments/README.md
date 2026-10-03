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
| EXP-026 | Does the whole re-application, driven by `tools/reapply.py`, build everything on a fresh export, judged by result? | run twice: the first found trees on streets and gravel falling from the cavern roof (fixed); the second ran every step without a stop, 24 of 24 places 0 gaps, audit clean |
| EXP-021 | Do Habitat Blocks replace or add, how far, do they persist and stack? | run: replace; edge at the configured range; survive restart, lost on re-export unless transplanted or re-placed; overlapping ranges spawn nothing; command-placed blocks need a chunk reload |
| EXP-033 | Does a Habitat Block replace in sealed rock at depth, give its pool's level band, and reach as a sphere or a column? | rig built on staging (3470, 20, 2880); block placed and resolved its pool (`DisplaySpecies` filled); the three questions need the owner at the stands |
| EXP-035 | What does the first playtest (Pallet to the third gym town, staging) find? | run by the owner: 17 notes. Built or fixed on staging: Mart clerks in 13 towns, flag-driven gym waystones, our spawns and suppression, the sapling Celebi and birds, the mine's workings, rctapi 0.16.1. Open: the level-cap catch trap, blackout-to-Center, custom leaders, pacing (three gym towns inside an hour) |
| EXP-034 | Does the scene runtime (per-player actors, props, zones, effects) carry the Gastly escort and the Route 1-3 events, and do the route trainers battle and record per player? | built and audited on staging (dryrun9): mansion, 10 events, 13 trainers, 41 props, 8 NPCs; every click, actor and battle needs the owner in game |
| EXP-038 | Which Pokemon can carry a rider on or under water, and can a datapack read the party for it? | static: 45 Surf (boat, dolphin) and 10 Dive (submarine) species from the merged riding data; MoLang reads each party member's species (confirmed in game, EXP-042). Correction: callbacks run only under data/cobblemon/callbacks/ |
| EXP-039 | Which events identify a full-party loss, a wild knockout and a trainer loss, with a stable victor? | static: battle_victory exposes losers, winners and their kinds and UUIDs; a direct wild knockout names no killer (the environmental default). Not run in game |
| EXP-040 | Can the 10% blackout charge be read and taken in one transaction? | balance read verified; the macro charge verified in game by the blackout (EXP-042) |
| EXP-041 | Can a wild guardian be kept from despawning and rebuilt? | run on staging: vanilla PersistenceRequired keeps it through unload and restart; /kill destroys it; rebuilt from the ledger in EXP-042 |
| EXP-042 | Do the blackout, the recovery claims and the water ladder work in game? | run with the owner, three sessions: the charge, return, Center checkpoint, air, Surf, Dive, the lethal second hit, the removal of vanilla air and the Dive swim boost pass; the waystone checkpoint, a mid-dive swap, a battle loss, recovery and delivery are not run |
| EXP-043 | Can a datapack run a Game Corner (coins, a slot machine, a prize counter) per player? | proposed in docs/research/CASINO.md (branch research/casino); not run |
| EXP-044 | Does surface exhaustion stop a player swimming across the sea? | built, loads clean on staging; not run in game |
| EXP-048 | Does a pasted LumyMon altar respond? | console half run 2026-10-02: both adopted templates place and all eight LumyMon blocks are real; a console-dropped carrot does nothing; three of four activation items exist nowhere in the pack. The right-click half waits on the owner |
| EXP-049 | Native-evolving starters: forms, a same-species stage, the cap gate and the evolution veto | designed 2026-10-02, not run ([README](EXP-049-native-starter-evolution/README.md)) |
| EXP-050 | Does the Seaward Drift's straight rail line carry a ridden minecart from Foothill Gate to Driftmouth Light and back? | rebuilt 2026-10-02 straight and audited offline (1,137 rails on z1795, 167 powered by sealed levers, no curve; 142 s at the cap); probes and the ride test not run |
| EXP-051 | Do our NPCs render as people once their classes name a model? | fixed and audited offline 2026-10-02: all 40 classes name `cobblemon:standard` (Cobblemon's trainer); pre-fix build audited 40 of 40 dolls; in-game look not run |
| EXP-052 | Can Ellis Hopgood see the player's Lopunny (a party callback's tag read by his dialogue), and do his Buneary stay in the cellar? | built and audited offline 2026-10-02 (`tools/lopunny_house.py`, `tools/lopunny_house_audit.py`); not run in game |
| EXP-053 | Does the Ursaluna's wake turn the sleeping bear into a boss fight? | built and audited offline 2026-10-02 (copies the Celebi's wake); not run in game |
| EXP-046 | Can a town hold a working Pokemon through restarts, unloads and players, doing visible work? | run headless on staging: held, protected against every `/damage` type, survives unload and restart, moves by `tp`; `spawnpokemonat` in a function works only after a `/reload` unless it is a macro; 13 workers placed and verified. Walk animation, clicks and a sword need the owner |
| EXP-045 | Can a player Mega Evolve with a Mega Bracelet? | PASS in game 2026-09-27: worn in the Accessories slot before the battle; reverts after; not held, not equipped mid-battle |

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
