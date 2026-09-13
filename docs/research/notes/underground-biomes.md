# Underground (3D) biomes for a WorldPainter-built Cobblemon 1.8.0 map

Question: how do we get cave biomes (`minecraft:dripstone_caves`, `lush_caves`, `deep_dark`, used by
`#cobblemon:is_cave` / `is_dripstone` / `is_deep_dark` spawns) underground, beneath painted surface
biomes? Answered for WorldPainter 2.27.1, Java 1.21.1, Cobblemon 1.8.0. Researched 2026-09-13.
WorldPainter source was read at git tag `v2.27.1`. Cobblemon source was read at gitlab tag `1.8.0`.
The local install is 2.27.1 (`C:\Users\wnd\AppData\Roaming\WorldPainter\logfile0.txt:7-10`), and
its export platform list includes "Minecraft 1.20.5 - 1.21.10" (same log, line 21).

## Verdicts

| # | Question | Answer | Source | Status |
|---|---|---|---|---|
| 1a | Can WP 2.27.1 write a different biome below the surface? | Yes, in two ways: a dimension-wide **Underground biome**, and a per-layer **Biome** on Custom Cave/Tunnel layers | [CHANGELOG][wpcl] 2.10.0, 2.23.0, 2.25.0; source below | VERIFIED |
| 1b | Dimension-wide option | Dimension Properties > General tab > "Underground biome:". Added in 2.23.0, but only actually used from 2.25.0 on. Applies to every 4x4 column below (lowest surface height minus top-layer depth), rounded down to a multiple of 4 | [CHANGELOG][wpcl]; [DimensionPropertiesEditor][dpe]; [WorldPainterChunkFactory][wcf] | VERIFIED |
| 1c | Per-area option | Custom Cave/Tunnel layer > "Biome:" (since 2.10.0). Written to every 4x4x4 cell that touches the carved interior (floor to roof) | [TunnelLayerDialog][tld]; [TunnelLayerExporter][tle] | VERIFIED |
| 1d | Do the built-in Caves / Caverns / Chasms layers set biomes? | No. Their exporters contain no biome code | [CavesExporter][ce], [CavernsExporter][cve], [ChasmsExporter][che] | VERIFIED |
| 1e | Is the painted Biomes layer 3D? | No. One biome per 4x4 column (the most common one in that column) | [WorldPainterChunkFactory][wcf] | VERIFIED |
| 2a | Export over an existing map | Export builds a new map. An existing folder with the same name is first moved to a backup folder, so biome edits made in-game are not carried into the new map | [JavaWorldExporter][jwe] | VERIFIED |
| 2b | Merge path that keeps in-game biomes | Yes. Merge has separate above-ground and underground biome-replace switches. Any switch left off keeps the existing map's biomes | [CHANGELOG][wpcl] 2.10.14; [JavaWorldMerger][jwm] | VERIFIED |
| 3a | `/fillbiome` in 1.21.1 | `/fillbiome <from> <to> <biome> [replace <filter>]`. Works on 4x4x4 cells. Fails on unloaded regions. Size capped by gamerule `commandModificationBlockLimit` (default 32768) | [wiki fillbiome][fb]; [23w03a][23w03a]; [Game rule][gr] | VERIFIED |
| 3a' | Does the cap count blocks or cells? Do clients update without relogging? | Unknown | none found | NOT VERIFIED |
| 3b | Amulet for 1.21.1 3D biomes | Amulet 0.10.33 notes say "Add 1.21 support". Latest release is 0.10.63 (2024-09-04). No source found for 1.21.1 3D biome editing | [0.10.33][am33]; [releases][amrel] | PARTLY VERIFIED |
| 3c | Underground spawns without a biome tag | Possible. 1.8.0 conditions include `canSeeSky`, `minY`/`maxY`, `minLight`/`maxLight`, `minSkyLight`/`maxSkyLight`, `structures`, `neededNearbyBlocks`, `neededBaseBlocks`, and more. Stock 1.8.0 underground spawns already use `maxSkyLight: 7` with `#cobblemon:is_overworld` | [SpawningCondition.kt][sc]; [geodude][geo]; [zubat][zub] | VERIFIED |
| 3c' | Habitat Block (1.8) | A spawner block for adventure maps. Placeable by cheats; its GUI edits a custom pool, range and trigger. It does not need a biome | [1.8.0 CHANGELOG][cc]; [Habitat Block wiki][hb] | VERIFIED (behaviour not tested) |
| 4 | Can WP 2.27.1 paint a datapack biome such as `cobblers:rift` into a 1.21.1 export? | Yes, as a Custom Biome. On named-biome platforms the dialog's text field is labelled "ID:". Its trimmed text is written unchanged as the chunk's biome palette string, with no namespace added | [CustomBiomeDialog][cbd]; [BiomeUtils][bu]; [MC118AnvilChunk][mc118] | VERIFIED in source; not tested in-game |
| 4a | What does the server do with a biome ID that no loaded datapack defines? | Logs "Recoverable errors when loading section [...]: (Unknown registry key in ... worldgen/biome]: <id> -> using default)". Seen on modded 1.20.x servers. The default biome and 1.21.1 behaviour are not sourced | [ATM-9 #2148][atm]; [MultiPaper #137][mp] | PARTLY VERIFIED |

## 1. WorldPainter 3D biomes, detail

- VERIFIED: the 2.10.0 changelog says "The Custom Cave/Tunnel layer now supports setting the biome
  inside the cave/tunnel to a different one than the surface. This works for Minecraft 1.17 and
  Minecraft 1.18+" ([CHANGELOG][wpcl]).
- VERIFIED: in `TunnelLayerExporter` (v2.27.1), `set3DBiomes` is true when the platform has
  `BIOMES_3D` or `NAMED_BIOMES` and a tunnel biome is set (or the layer has a floor dimension). The
  biome is written inside the carve loop, one call per carved block:
  `biomeUtils.set3DBiome(chunk, (x & 0xf) >> 2, z >> 2, (y & 0xf) >> 2, myBiome)`. The code comment
  says every 4x4x4 cell "touched" is changed ([source][tle]). In WorldPainter, `z` is height here.
  - Limit: the biome only reaches cells that contain carved blocks. Cells can stick out of the
    cave by up to 3 blocks, and solid rock around the cave keeps the underground or surface biome.
- VERIFIED: the 1.20.5-1.21.10 platform has `NAMED_BIOMES` but not `BIOMES_3D` ([DefaultPlugin][dp]).
  Both the tunnel "Biome:" box and the "Underground biome:" box are enabled for either capability
  ([tld], [dpe]).
- VERIFIED: 2.23.0 added "a separate underground biome for map formats that support 3D biomes". 2.25.0
  says the "'Underground biome' setting on the General tab of the Dimension Properties is now
  actually honoured" ([CHANGELOG][wpcl]). In `WorldPainterChunkFactory`, when the underground biome is
  set, cells from `minHeight` up to `lowestHeight` get it, and cells above get the painted biome.
  `lowestHeight = (getLowest2D(4, height - topLayerDepth) / 4) * 4`. When it is not set,
  `set2DBiome` writes the painted biome ([source][wcf]).
  - Limit: there is one underground biome per dimension, not per region.
- VERIFIED: the underground-biome list is built by `getAllBiomes(platform, customBiomeManager)`
  ([dpe]).
- ASSUMED: that list includes custom biome IDs. This is inferred from the parameter name only.
- NOT VERIFIED: that dripstone_caves, lush_caves and deep_dark all appear in the 1.21 platform's
  biome list.
- ASSUMED: the tunnel biome overwrites the underground biome where both apply. This depends on
  export order, which was not traced.
- Suggested pattern (ASSUMED, test first): set Underground biome = `minecraft:dripstone_caves`
  (or leave it unset). Then use Custom Cave/Tunnel layers with Biome = `lush_caves` or `deep_dark`
  for specific cave systems.

## 2. Export vs Merge, detail

- VERIFIED: `JavaWorldExporter` checks whether the target world folder exists. If it does, it
  logs "Directory already exists; backing up to ..." and runs `worldDir.renameTo(backupDir)`
  ([source][jwe]). A fresh Export therefore writes WorldPainter's biomes everywhere.
- VERIFIED: `JavaWorldMerger` has `mergeBiomesAboveGround` and `mergeBiomesUnderground`. For each
  biome cell, `(y >= biomesNewHeight) ? mergeBiomesAboveGround : mergeBiomesUnderground` decides
  whether the new biome is copied, where `biomesNewHeight = (newHeight - surfaceMergeDepth) >> 2`.
  Cells whose switch is off are left untouched ([source][jwm]). The changelog says the same (2.10.14).
- VERIFIED: the FAQ says use Merge (Ctrl+R), not Export, to write changes into an existing map
  ([FAQ][faq]).
- Implication (ASSUMED): Merge with "underground" biome replacement off keeps `/fillbiome` cave
  work done in-game.

## 3a. `/fillbiome` (Java 1.21.1)

- VERIFIED ([wiki][fb]):
  - Syntax is `/fillbiome <from> <to> <biome>` or `... <biome> replace <filter>`.
  - Without a filter, all biomes in the box are replaced.
  - It works on 4x4x4 cells, not blocks, and changes biomes only, not blocks.
  - It fails if "the specified region is unloaded or out of the world", or if the size is over
    `commandModificationBlockLimit`.
  - It needs permission level 2 and returns the number of cells changed.
- VERIFIED: 23w03a (1.19.4) added `commandModificationBlockLimit`, "defaults to 32768. Controls the
  maximum number of blocks changed in one execution of /clone, /fill, and /fillbiome"
  ([23w03a][23w03a]). Before that the cap was a hardcoded 32768 ([wiki][fb] history). The rule was
  renamed to `max_block_modifications` in 1.21.11 ([Game rule][gr]), so 1.21.1 uses the camelCase name.
- NOT VERIFIED: whether fillbiome measures the box in blocks (32768 = 32x32x32) or in cells.
- NOT VERIFIED: whether clients see the change without relogging. A clientbound "Chunk Biomes"
  packet exists in the current protocol ([packets][pk]), but no 1.21.1 source ties it to fillbiome.
- ASSUMED: unloaded regions need a player nearby or `/forceload` first.

## 3b. Amulet

- VERIFIED: Amulet 0.10.33's release notes read "Add 1.21 support" ([release][am33]). The latest
  release is 0.10.63, 2024-09-04 ([releases][amrel]).
- NOT VERIFIED: that Amulet handles 1.21.1 3D biome painting, or modded biome IDs (Terralith etc.)
  from our pack.

## 3c. Cobblemon 1.8.0 spawn conditions without a cave biome

- VERIFIED: base `SpawningCondition` (tag 1.8.0) fields ([source][sc]):
  - `dimensions`, `biomes`, `moonPhase`, `canSeeSky`
  - `minX`, `minY`, `minZ`, `maxX`, `maxY`, `maxZ`
  - `minLight`, `maxLight`, `minSkyLight`, `maxSkyLight`
  - `isRaining`, `isThundering`, `timeRange`, `structures` (IDs or tags), `isSlimeChunk`
  - `markers`, `isPokeSnack`, `appendages`
- VERIFIED: the checks compare against the spawn position, e.g.
  `canSeeSky != spawnablePosition.canSeeSky` and `position.y < minY || > maxY` ([sc]).
- VERIFIED: area conditions add `minHeight`, `maxHeight` and `neededNearbyBlocks`
  ([AreaSpawningCondition][asc]). `grounded` adds `neededBaseBlocks` ([Grounded][gsc]). `submerged`
  adds `minDepth`, `maxDepth`, `fluidIsSource` and `fluid` ([Submerged][ssc]).
- VERIFIED: there is no `isSubmerged` field. "submerged" is a position type, set per spawn with
  `"spawnablePositionType"` ([geodude][geo]).
- NOT VERIFIED: `labels`/`labelMode` are listed on the wiki ([Spawn Condition][wsc], edited
  2025-09-25, i.e. pre-1.8) but were not found in `SpawningCondition.kt` 1.8.0.
- VERIFIED: stock 1.8.0 already spawns many "cave" Pokémon without cave biomes.
  - `geodude-2` uses `maxSkyLight: 7` + `#cobblemon:is_overworld` ([geo]).
  - `zubat-3` uses the same and excludes `#cobblemon:is_deep_dark`.
  - `zubat-4` uses `canSeeSky: false` ([zub]).
- VERIFIED: `#cobblemon:is_cave` = dripstone_caves, lush_caves, plus optional `#c:is_cave` and
  mod caves (Terralith, Wythers...). It does not include deep_dark ([is_cave.json][tag]).
- VERIFIED: 1.8.0 added the Habitat Block, "a spawner block for servers and adventure maps that
  controls spawning in an area" ([CHANGELOG][cc]). According to the wiki, a player-placed block has
  a GUI covering: custom pool, species, bucket, weight, levels, moon phase, time, light, spawn range,
  and a Redstone/Tick/Random Tick trigger ([wiki][hb]).
- ASSUMED: an overlay datapack could spawn cave Pokémon by y-range or sky light in our own
  spawn files, instead of creating cave biomes.
- ASSUMED: `neededNearbyBlocks` (e.g. dripstone) can stand in for "is dripstone cave". The
  radius behind `nearbyBlockHolders` was not traced.

## 4. Custom datapack biomes (`cobblers:rift`) in WorldPainter

- VERIFIED: `CustomBiome` stores `String name` and `int id` ([source][cb]).
- VERIFIED: in `CustomBiomeDialog`, if the platform has `NAMED_BIOMES`, the numeric ID spinner is
  removed and the name label is relabelled `"ID:"`. `ok()` then saves
  `customBiome.setName(fieldName.getText().trim())`. The dialog has no format or namespace check
  ([source][cbd]).
- VERIFIED: `BiomeUtils.findBiomeName` looks up `MODERN_IDS[biome]` first, then falls back to
  `customBiomeNames[biome]` (the custom biome's name). `set3DBiome` and `set2DBiome` pass that
  string to `chunk.setNamedBiome` ([source][bu]).
- VERIFIED: the custom-name table is `new String[256]`, so custom numeric IDs must be below 256
  ([bu]).
- VERIFIED: `MC118AnvilChunk.setNamedBiome` stores the string, and `toNBT` writes it unchanged into
  `biomes.palette` ([source][mc118]).
- ASSUMED: the 1.20.5-1.21.10 platform uses `MC118AnvilChunk`. This was not traced.
- The ID must be typed in full, e.g. `cobblers:rift`. ASSUMED: without a namespace, the game
  would read it as `minecraft:rift`, which is standard resource-location parsing but not checked
  against 1.21.1 source.
- VERIFIED: 2.15.17 lets you list data packs on the Export screen, and WorldPainter copies them
  into the map's `datapacks` directory ([CHANGELOG][wpcl]). That is how `cobblers` would travel
  with the exported map.
- VERIFIED: custom biomes work in the tunnel and underground paths (2.15.15 "Use correct Custom
  Biome names when exporting Custom Cave/Tunnel Layers"; both biome combo boxes are built from
  `getAllBiomes(platform, customBiomeManager)`) ([CHANGELOG][wpcl]; [dpe]).
- VERIFIED: a missing biome ID produces "Unknown registry key in
  ResourceKey[minecraft:root / minecraft:worldgen/biome]: biomesoplenty:clover_patch -> using
  default" as a "Recoverable errors when loading section" log line ([ATM-9 #2148][atm], a 1.20.1
  pack). The same message with `terralith:yosemite_lowlands` appears in [MultiPaper #137][mp].
- NOT VERIFIED:
  - Which biome "default" means (plains is suspected).
  - Whether the substitution is saved back to disk, making the loss permanent.
  - 1.21.1-specific behaviour. No minecraft.wiki or Mojira source was found.
- Practical rule (ASSUMED): the `cobblers` datapack must be in `world/datapacks` before the
  server first loads any exported chunk. It also has to add `cobblers:rift` to any
  `#cobblemon:is_*` tags we want it to count for.

## Unknown / experiment candidates

1. Export a small 1.21 test map with Underground biome = dripstone_caves, plus one Tunnel layer
   with Biome = lush_caves. Check with F3 at several y-levels that the surface, rock and tunnel
   cells have the expected biomes. Also check whether the tunnel biome overrides the underground one.
2. Run `/fillbiome` on a 32x32x33 box with the default gamerule. Fails = the cap counts blocks.
   Watch whether a connected second client sees grass/fog change without relogging.
3. Merge a WP edit into a map after an in-game `/fillbiome`, with underground biome replacement off.
   The fillbiome cells should survive.
4. Cobblemon 1.8.0: does a `#cobblemon:is_cave` spawn fire inside a WP tunnel cell but not in
   rock-adjacent cells? Does `canSeeSky` read false under WP terrain?
5. Habitat Block: data format for pre-placing it in a WorldPainter/structure export
   (no NBT documentation found).
6. Export a tunnel with Custom Biome `cobblers:rift` and a minimal datapack biome JSON. Check
   that F3 shows `cobblers:rift`.
7. Start once without the datapack on a copy of that map. Record the log line and which biome
   F3 shows. Then restore the datapack and check whether the ID survived after the chunk was saved.

[wpcl]: https://www.pepsoft.org/worldpainter/CHANGELOG
[wcf]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/exporting/WorldPainterChunkFactory.java
[tle]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/layers/tunnel/TunnelLayerExporter.java
[tld]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPGUI/src/main/java/org/pepsoft/worldpainter/layers/tunnel/TunnelLayerDialog.java
[dpe]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPGUI/src/main/java/org/pepsoft/worldpainter/DimensionPropertiesEditor.java
[dp]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/DefaultPlugin.java
[ce]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/layers/exporters/CavesExporter.java
[cve]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/layers/exporters/CavernsExporter.java
[che]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/layers/exporters/ChasmsExporter.java
[jwe]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/exporting/JavaWorldExporter.java
[jwm]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/merging/JavaWorldMerger.java
[faq]: https://www.worldpainter.net/trac/wiki/FAQ
[fb]: https://minecraft.wiki/w/Commands/fillbiome
[23w03a]: https://minecraft.wiki/w/Java_Edition_23w03a
[gr]: https://minecraft.wiki/w/Game_rule
[pk]: https://minecraft.wiki/w/Java_Edition_protocol/Packets
[am33]: https://github.com/Amulet-Team/Amulet-Map-Editor/releases/tag/0.10.33
[amrel]: https://github.com/Amulet-Team/Amulet-Map-Editor/releases
[sc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/condition/SpawningCondition.kt
[asc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/condition/AreaSpawningCondition.kt
[gsc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/condition/GroundedSpawningCondition.kt
[ssc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/api/spawning/condition/SubmergedSpawningCondition.kt
[geo]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/spawn_pool_world/0074_geodude.json
[zub]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/spawn_pool_world/0041_zubat.json
[tag]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/common/src/main/resources/data/cobblemon/tags/worldgen/biome/is_cave.json
[cc]: https://gitlab.com/cable-mc/cobblemon/-/blob/1.8.0/CHANGELOG.md
[hb]: https://wiki.cobblemon.com/index.php/Habitat_Block
[cb]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/biomeschemes/CustomBiome.java
[cbd]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPGUI/src/main/java/org/pepsoft/worldpainter/biomeschemes/CustomBiomeDialog.java
[bu]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/util/BiomeUtils.java
[mc118]: https://github.com/Captain-Chaos/WorldPainter/blob/v2.27.1/WorldPainter/WPCore/src/main/java/org/pepsoft/minecraft/MC118AnvilChunk.java
[atm]: https://github.com/AllTheMods/ATM-9/issues/2148
[mp]: https://github.com/MultiPaper/MultiPaper/issues/137
[wsc]: https://wiki.cobblemon.com/index.php/Spawn_Condition
