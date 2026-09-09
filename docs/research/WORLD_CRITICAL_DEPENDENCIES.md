# World-critical dependency freeze list

## Gate

**Status: PROVISIONAL — serious world construction must not begin.** These components are the current freeze candidates for EXP-000. Their blocks, structures, or terrain can become permanent map state. They are not accepted as stable until the full Cobblemon 1.8 server boots, a client connects, and fresh-world checks pass.

Removing a block provider after it has been used can replace map content with air or missing-state fallbacks. Changing biome, structure, or noise providers can create seams and inconsistent new chunks. A successful loader boot alone is insufficient evidence.

## Block and decoration providers

| Component | Why it is world-critical | Cobblemon 1.8 position | Required check before freeze |
| --- | --- | --- | --- |
| Rechiseled | 3,628 blockstates; likely palette dependency across builds | preserve provisionally | place representative blocks, restart, reload chunks |
| CobbleFurnies | 372 Pokémon-themed furniture blockstates; required by Legendary Monuments | preserve; UNKNOWN behavior | place/use blocks and generate dependent structures |
| Carved Wood | 325 decorative wood blockstates | preserve provisionally | representative placement/restart test |
| Pokeblocks | 314 Pokémon-themed blockstates | preserve provisionally | representative placement/restart test |
| Cozy Home | 278 furniture blockstates | preserve provisionally | representative placement/restart test |
| Handcrafted | 268 furniture/decor blockstates | preserve provisionally | representative placement/restart test |
| Moar Concrete | 178 construction blockstates | preserve provisionally | representative placement/restart test |
| Vanilla Backport | 72 blockstates plus biome/structure content | preserve provisionally | blocks plus fresh-chunk generation |
| LumyMon | 64 blockstates, custom mechanics, structures, and worldgen | preserve; UNKNOWN and pack-specific | fresh-world generation, structure, restart, and interaction tests |
| Beautify | 57 decorative blockstates | preserve provisionally | representative placement/restart test |
| Legendary Monuments | 48 blockstates and legendary structures; pack-specific | preserve; UNKNOWN | locate/generate structures and verify blocks after restart |
| Waystones | 45 blockstates and generated structures; stores destinations | preserve provisionally | generate, activate, teleport, restart |
| Comforts | 34 persistent bed/hammock states | preserve provisionally | place, sleep, restart |

## Terrain and structure providers

| Component | Persistent effect | Cobblemon 1.8 position | Required check before freeze |
| --- | --- | --- | --- |
| Terralith datapack | overworld terrain and biomes | preserve provisionally | generate a fixed-seed fresh world and compare representative chunks |
| Regional datapacks (Hoenn, Johto, Sinnoh) | spawn/region data loaded through Global Packs | preserve for functional test | confirm pack load order, tags, and spawn behavior |
| Cobblemon Additions | Pokémon villages and spawn pools | preserve; UNKNOWN | locate villages and verify spawn-pool loading |
| Repurposed Structures | broad structure generation | preserve provisionally | locate representative structures in fresh chunks |
| Biome Replacer | maps Terralith biomes to biome categories used by the pack | freeze with its config | verify mappings and biome-dependent spawns |
| Cobblemon Raid Dens | generated structures and persistent den blocks | preserve; UNKNOWN/high API coupling | locate den, start/finish raid, restart |
| Mega Showdown | keystone ore, meteorite/worldgen, and persistent blocks | update to 1.0.2; functional test | generate resources and complete Mega flow |
| PokeCenter PCs datapack | village PokéCenter structure NBT | preserve provisionally | locate structure and operate the PC |
| Main Cobbleverse datapack | includes structure NBT and Mega/form data | preserve for fresh-world test | datapack load, structure placement, form assets |

## Other persistent block providers

TMCraft, Cobblemon Battle Positions, Radical Cobblemon Trainers, Sophisticated Backpacks/Storage, Tom's Storage, and Iron Chests can leave blocks or block entities in the map. They are gameplay systems as well as world-state dependencies. TMCraft, RCT/RCT API, Mega Showdown, ZAMegas, Cobbreeding, CobbleNav, PlayerXP, Only Bottle Caps, Capture XP, and Tim Core use their Cobblemon 1.8-compatible overlay releases where available.

## Generation implementation dependencies

`zfastnoise`, C2ME, ScalableLux, and Biome Replacer can affect generation behavior even when they add no authored blocks. Pin their exact versions before selecting the campaign seed or generating source terrain. Any later change requires a fixed-seed comparison and a decision about whether only new chunks or the whole world will be regenerated.

## Freeze decision procedure

1. Boot the complete overlay on a fresh disposable world.
2. Confirm all required datapacks load without registry or tag errors.
3. Generate fixed-seed chunks that exercise Terralith, biome replacement, villages, monuments, raid dens, and PokéCenters.
4. Place representative blocks from every provider, use block entities, save, restart, and inspect the same chunks.
5. Run the relevant multiplayer interactions.
6. Record exact jar and datapack hashes, then accept the freeze in an ADR.

No listed component is approved for removal solely because it lacks a release labeled for Cobblemon 1.8. Unknown world-critical components remain isolated in the test pack until runtime evidence supports keeping or replacing them.
