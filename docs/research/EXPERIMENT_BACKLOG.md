# Experiment backlog

The detailed bootstrap backlog lives in the existing `experiments/EXP-000-*`
through `EXP-007-*` folders. This index records active and added proofs.

| Experiment | Status | Objective | Minimum proof | Decision / follow-up |
| --- | --- | --- | --- | --- |
| EXP-000 Cobblemon 1.8 compatibility | running | stable Cobbleverse-derived 1.8 foundation | server boot, client connect, critical smoke tests | server boot passed; client/function/world freeze remain |
| EXP-001 F4 curated route | active; F4 world ready for playtest | authored encounter table plus a memorable optional place | controlled 10–20-species Pallet coast and runtime-placed Relic Island | separate 1,000-block coast exported and booted; 13 donor/event checks and restart passed; client art/sightline and spawn proof remain |
| EXP-002 Difficult trainer | planned | ROM-hack-style boss control | one fully specified trainer battle | gated by EXP-000 |
| EXP-003 Level cap | planned | prevent grinding past progression | one enforceable cap | gated by EXP-000 |
| EXP-004 Trainer gauntlet | planned | multiplayer-safe chained battles | A→B→C→Admin flow | gated by EXP-000 |
| EXP-005 Puzzle dungeon | planned | persistent puzzle + encounter | three states and sealed reward | gated by EXP-000 |
| EXP-006 Static encounter | planned | controlled one-time Pokémon | multiplayer-safe authored encounter | gated by EXP-000 |
| EXP-007 Story progression | planned | player/shared campaign flags | persistent unlock and reward | gated by EXP-000 |
| EXP-008 Structure placement | partial | reuse existing NBT/jigsaw assets | five representative placements plus save/restart | use vanilla templates for prototypes; client visual QA next |
| EXP-009 Automated hex world | partial result | deterministic 2×2 terrain and scale proof | source masks → exported/booted world → client mount test | pipeline passed; river worked; 1,250-block prototype felt too empty; use 1,000-block working scale |
| EXP-010 Underground biomes (proposed) | proposed | cave biomes beneath painted surface biomes | small WorldPainter 2.27.1 export: Underground biome = dripstone_caves plus one Custom Cave/Tunnel layer with Biome = lush_caves; F3 at several heights; does the tunnel biome win where both apply? | 29 species depend on underground biomes in the region plan; see `docs/research/notes/underground-biomes.md` |
| EXP-011 Rift custom biome (proposed) | proposed | a datapack biome with fog, sky/fog colour, particles, sound and a hidden floor | export a tunnel or area with Custom Biome `cobblers:rift` and a minimal biome JSON; F3 shows the ID; restart once without the datapack and record what happens | the rift's biome is deferred until this passes |
| EXP-012 Partial spawn suppression | run | default spawns off in route corridors, on elsewhere | `anticonditions` coordinate boxes on every inherited file, sampled inside and outside | hybrid is buildable; see `experiments/EXP-012-bounded-default-suppression/` |
| EXP-021 Habitat Block influence | run | can a Habitat Block carry a place's encounter identity | replace vs add, measured radius, persistence, stacking | adopted with rules; see `experiments/EXP-021-habitat-block-influence/` |
| EXP-028 Underground habitat spawning (proposed) | proposed | wild encounters on the enclosed Victory Road | one natural `ReplaceSpawns` block in sealed rock with no sky access: `/checkspawn` shows the pool **and** an 8-minute sample records a real spawn; then vertical reach (two blocks 30 apart in a shaft, range 24 each), a `"maxLight": 7` entry, and `RangeOfInfluence: 64` | source says the mechanism ignores sky entirely and the influence is a 3D sphere; see `docs/research/notes/habitat-blocks-underground.md` |
