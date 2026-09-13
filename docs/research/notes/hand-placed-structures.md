# Hand-placed structures: what "structure" data they create, and what reads it

Question: all structures on our WorldPainter map will be hand-placed. Which placement methods create
structure data (a StructureStart and chunk References)? Which systems need that data: `/locate`,
`location_check`, explorer maps, Cobblemon `structures` spawns, RCT spawners, LumyMon maps?
Answered for Java 1.21.1 Fabric, Cobblemon 1.8.0 (gitlab tag `1.8.0`) and rctmod 0.19.0-beta (gitlab
tag `v0.19.0-beta`, the overlay target in `modpack/manifest/overlay.json:138-149`). Researched 2026-09-13.
Already measured, not re-checked here: exported chunks are Status `full` with no structure starts, and
the overworld generator is `minecraft:noise`.

**Vanilla 1.21.1 source was not read.** No public decompiled `PlaceCommand` body was found. So every
answer about what `/place` writes to chunk data is NOT VERIFIED until EXP-A below is run.

## Verdicts

| # | Question | Answer | Source | Status |
|---|---|---|---|---|
| 1 | Does `/place structure` save a StructureStart and References? | Probably not. We believe it builds the start and places its pieces chunk by chunk, but never registers it | none found | NOT VERIFIED |
| 1a | Would `/locate structure` find it? | Very unlikely, even if a start were saved. `/locate` searches in units of the structure set's spacing, so it only tests the grid of candidate chunks | [locate][loc]; [structure set][ss] | Search method VERIFIED; outcome NOT VERIFIED |
| 1b | Would `location_check` `structures` or mod `StructureManager` lookups see it? | Only if References exist. Structure lookups are built from the chunk's References | [location template][lt]; [Yarn StructureAccessor][sa] | Mechanism VERIFIED; outcome NOT VERIFIED |
| 1c | Would explorer or cartographer maps point to it? | Very unlikely. Maps use the same search as `/locate`, and loot maps skip already-generated chunks by default | [explorer map][em]; [item modifier][im] | Mechanism VERIFIED; outcome NOT VERIFIED |
| 1d | Does it work in fully generated chunks? | Yes, it places blocks there. Local test on 1.8.0 passed, but only after 15x15 chunks were loaded | `experiments/EXP-008-structure-placement/results.json:20-22`; `docs/world-building/STRUCTURE_CATALOG.md:41-42` | VERIFIED (blocks only) |
| 1e | Limits | Fails if any chunk is unloaded or out of the world. Biome and height checks use the seed-based generator, not the terrain actually in the world (closed Works As Intended). Terrain adaptation is not run. Jigsaw `size` is 0-20; `max_distance_from_center` is 1-128 (116 with adaptation) | [place][pl]; [MC-263279][263279] → [MC-251339][251339], [MC-251309][251309]; [JSON format][sj] | VERIFIED |
| 2 | Do `/place template`, structure blocks, WorldEdit or Axiom create structure data? | No. Templates and schematics store only blocks, block entities, entities (and, for schematics, biomes). There is nothing to register | [structure file][sf]; [Sponge schematic v3][sp]; [place][pl] ("like the load button") | File formats VERIFIED; runtime side effects NOT VERIFIED |
| 2' | So 1a-1c for these methods? | All fail: no start, no References | follows from 2 and 1b | ASSUMED (strong) |
| 3 | `/place jigsaw` | Same as 1: we believe pieces are placed without a start. Fails if the start position is unloaded. Max depth has been 20 since 24w07a | [place][pl] | Placement rules VERIFIED; data NOT VERIFIED |
| 4 | Do command blocks inside a template run by themselves? | Unknown for 1.21.1. Placement in 1.21.1 does trigger block updates (the `strict` opt-out only arrived in 25w02a), so a template's redstone block *may* power them | [25w02a][25w02a]; [place history][pl] | NOT VERIFIED |
| 4' | Does `enable-command-block` matter? | Yes. On 1.21.1 it is a server.properties key, default false, and command blocks run only when it is true. It became a game rule in 25w35a | [command block][cb]; [server.properties][sprop] | VERIFIED |
| 5 | How does Cobblemon 1.8.0 check `structures`? | It looks up structure starts for the spawn position's **chunk** through `StructureManager.startsForStructure(ChunkPos(pos))` and caches them per position. It then matches IDs or tags. No bounding-box or piece test | [SpawningCondition.kt][cc]; [SpawnablePosition.kt][csp] | VERIFIED |
| 5' | Effect in our export area | With no starts and no References, `structures`-gated spawns never pass there | 5 + measured chunk data | ASSUMED (strong) |
| 6a | RCT `trainer_spawner` | Needs only the block entity (`TrainerIds` tag), a nearby player and RCT's spawn checks. No structure lookup in the spawner block, its block entity, or `TrainerSpawner.java` | [TrainerSpawnerBlockEntity][rbe]; [TrainerSpawnerBlock][rb]; [TrainerSpawner][rts]; [RCT blocks docs][rdoc] | VERIFIED (those 3 files) |
| 6b | LumyMon cartography-table maps, legendary radars, Cobbleverse `gym_map` | Docs say they "generate maps leading" to gyms and legendary structures. The mechanism is not public: LumyMon is closed source, and the Cobbleverse datapack zips are unread | [LumyMon page][lumy]; [legendary locator guide][lleg] | NOT VERIFIED |
| 6b' | Likely behaviour | They look like vanilla explorer-style searches ("Battle Seeker" gives a "never mapped" structure, which resembles skipping known structures). If so, they will not find hand-placed builds | [lleg] wording only | ASSUMED (weak) |

## Details

**1. `/place structure`.** The wiki lists syntax and failure cases only: unloaded or out-of-world chunks,
or "no valid position in this chunk". It says nothing about saving data [pl].
Mojang, on MC-251339: "/place only creates the structure, not additional generation around it" [251339].
MC-263279 found that `/place` uses seed calculations instead of the world's real biomes and height. It was
closed as a duplicate of Works As Intended tickets [263279]. **This matters for a WorldPainter world**,
where painted terrain does not match what `minecraft:noise` would generate. Jigsaw starts projected to a
heightmap, and biome-gated structures, may land at the wrong height or fail to place. Local runs agree:
the Legendary Monuments shrine failed its mod terrain check on a flat site, and a BCA village placed with
pool warnings (EXP-008 `results.json:20-22`).
Chunk data format: `structures.References` holds "coordinates of chunks that contain starts";
`structures.starts` holds structures "yet to be generated" [cf].

**1a/1c. Search, not scan.** `/locate` range is "201x201 units of the structure's spacing" [loc].
`random_spread` placement builds "a grid of initial positions" [ss]. Explorer maps work "similar to
`/locate structure`" (101x101 from loot, 201x201 from trades) and skip structures already found by earlier
maps [em]. `exploration_map.skip_existing_chunks` "Don't search in chunks that have already been generated.
Defaults to true" [im]. So even a saved start in an off-grid chunk would probably not be found (ASSUMED).
In our export area every chunk is already generated.

**1b. Containment.** The location predicate `structures` field means "the structure the location is
currently in" [lt]. Yarn 1.21.1 `StructureAccessor.getStructureStarts(ChunkSectionPos, Structure)`:
"structure starts are computed from the structure references of the given section's chunk". Also
`getStructureContaining` excludes positions that are in the expanded box but not in a child piece [sa].
A chunk without References therefore matches nothing, whatever blocks it holds.

**2. Templates and schematics.** Structure files "store small structures of blocks and entities" [sf].
Sponge schematic v3 has `Blocks`, `Biomes` and `Entities`, with no structure field [sp]. Local 1.8.0 runs of
`/place template` (with rotation and mirror) printed "Loaded template at ..." (EXP-008 `results.json:14-19`).
The `strict` argument does **not** exist on 1.21.1; it was added in 25w02a (1.21.5) [25w02a].

**4. Command blocks.** The `auto` tag "allows to activate the command without the requirement of a redstone
signal" [cb]. The wiki does not say whether a command block loaded from a template runs on load. Before
25w02a, template placement had no way to skip block updates, so a redstone block next to a command block
in the same template is a plausible trigger. Treat this as untested. It also needs
`enable-command-block=true` [sprop] [cb].

**5. Cobblemon.** In `SpawningCondition.fits`, when `structures` is non-empty, the spawn fails if none of
the entries passes `cache.check(structureAccess, position, id|tag)`. The cache's `loadStructures` calls
`structureAccess.startsForStructure(ChunkPos(pos)) { ... false }`, which records every structure the chunk
refers to. `check(id)` is `id in foundIdentifiers`; `check(tag)` is `holder.is(tag)` [cc] [csp].
This test is chunk-level, so it is coarse even for natural structures.
Alternative without structure data: 1.8 has a Habitat Block and position/biome/light conditions
(`docs/research/notes/underground-biomes.md:24-25`).

**6. RCT.** In `serverTick`, a spawner with non-empty `TrainerIds` and no current owner calls
`attemptSpawn`. That finds the nearest player and calls `TrainerSpawner.attemptSpawnFor(player, id,
pos.above(), true, true, boosted, 1.0, 1.0)`. The checks are: valid ID, `canSpawnAt`, global and
per-player caps, player level > 0, optional trainer card, uniqueness and chance [rbe] [rts]. The docs add
that the 2 blocks above must be air and the range is 2/3 of `maxHorizontalDistanceToPlayers` [rdoc].
So hand-placed spawners are plausible, but their behaviour has not been tested (`STRUCTURE_CATALOG.md:73`).

## Experiments that would settle the unverified rows

- **EXP-A (1, 1a-c, 3):** Use a disposable copy of the export on the 1.8.0 server.
  - In an exported chunk, run `/place structure minecraft:igloo` and `/place jigsaw` with a vanilla pool.
    Save and stop the server, then open the region file in an NBT editor. Record whether
    `structures.starts` or `References` gained entries.
  - Run `/locate structure` from next to it.
  - Test a datapack predicate `location_check {structures:"minecraft:igloo"}` with `/execute if predicate`
    while standing inside.
  - Buy a cartographer map, or run `/loot` with an `exploration_map` table whose destination tag includes it.
  - Repeat all of the above for `/place template` as a control.
- **EXP-B (1e):** Place a jigsaw that projects to a heightmap (a village) and a biome-gated structure
  (desert pyramid) on painted terrain that differs from the noise terrain. Record the Y it lands at and
  whether it fails.
- **EXP-C (4):** Build a template containing a command block (`auto:0`, running `say hi`) next to a redstone
  block, and a second one with `auto:1`. Place each with `/place template` and a structure block, first with
  `enable-command-block=false`, then `true`. Record which ones execute.
- **EXP-D (5'):** Write a test spawn entry with `structures: ["minecraft:igloo"]`.
  - Check it with Cobblemon's spawn debugging (command or tool not yet identified; find it first) in an
    exported chunk.
  - Then check next to a `/place structure` igloo, and next to a naturally generated igloo outside the export.
- **EXP-E (6a):** Place `cobbleverse:brock` with `/place template` in an exported chunk. Stand inside the range
  with a level > 0 player and record spawns. Also try a bare `rctmod:trainer_spawner` set with
  `/data modify block ... TrainerIds set value [...]`.
- **EXP-F (6b):** Craft a LumyMon Brock map and a legendary radar map next to hand-placed gyms and shrines.
  Record the target and any "not found" result. Read `gym_map` in `COBBLEVERSE-Loot-DP-v11.zip` and
  `COBBLEVERSE-DP-v31.zip` for `exploration_map` functions.

[pl]: https://minecraft.wiki/w/Commands/place
[loc]: https://minecraft.wiki/w/Commands/locate
[ss]: https://minecraft.wiki/w/Structure_set
[lt]: https://minecraft.wiki/w/Template:Nbt_inherit/conditions/location/template
[sa]: https://maven.fabricmc.net/docs/yarn-1.21.1+build.3/net/minecraft/world/gen/StructureAccessor.html
[em]: https://minecraft.wiki/w/Explorer_Map
[im]: https://minecraft.wiki/w/Item_modifier
[cf]: https://minecraft.wiki/w/Chunk_format
[263279]: https://mojira.dev/MC-263279
[251339]: https://mojira.dev/MC-251339
[251309]: https://mojira.dev/MC-251309
[sj]: https://minecraft.wiki/w/Structure/JSON_format
[sf]: https://minecraft.wiki/w/Structure_file
[sp]: https://github.com/SpongePowered/Schematic-Specification/blob/master/versions/schematic-3.md
[25w02a]: https://minecraft.wiki/w/Java_Edition_25w02a
[cb]: https://minecraft.wiki/w/Command_Block
[sprop]: https://minecraft.wiki/w/Server.properties
[cc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/condition/SpawningCondition.kt
[csp]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/position/SpawnablePosition.kt
[rbe]: https://gitlab.com/srcmc/rct/mod/-/blob/v0.19.0-beta/common/src/main/java/com/gitlab/srcmc/rctmod/world/blocks/entities/TrainerSpawnerBlockEntity.java
[rb]: https://gitlab.com/srcmc/rct/mod/-/blob/v0.19.0-beta/common/src/main/java/com/gitlab/srcmc/rctmod/world/blocks/TrainerSpawnerBlock.java
[rts]: https://gitlab.com/srcmc/rct/mod/-/blob/v0.19.0-beta/common/src/main/java/com/gitlab/srcmc/rctmod/api/service/TrainerSpawner.java
[rdoc]: https://srcmc.gitlab.io/rct/docs/0.15/gameplay/blocks/
[lumy]: https://www.lumyverse.com/en/cobbleverse/lumymon/
[lleg]: https://www.lumyverse.com/en/cobbleverse/how-to-find-legendary-pokemon-structures/
