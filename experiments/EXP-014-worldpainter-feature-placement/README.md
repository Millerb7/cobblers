# EXP-014: WorldPainter placement of Cobblemon worldgen content

## Objective
Can WorldPainter 2.27.1, driven headless by `wpscript`, put Cobblemon worldgen
content (modded ore blocks, apricorn trees, berry bushes with their block
entities) into a Minecraft 1.20.5-1.21.x Java export, including biome-restricted
scatter? "Yes" means the handcrafted region can be painted in WorldPainter
without a post-export pass for these features; every "no" names exactly what a
post-export script has to do instead.

## Success criteria
- Q1: a modded ore ID (`cobblemon:*_stone_ore`, `cobblemon:deepslate_*_stone_ore`)
  appears in exported section palettes at the requested y-range, placed through
  the Resources layer or, failing that, another WorldPainter layer.
- Q2: a Custom Objects layer loads `.schem` / `.nbt` objects holding Cobblemon
  blocks and scatters them at a controllable density, only inside one biome, set
  from a script.
- Q2b: `cobblemon:berry` block entities survive export with their data, on the
  matching berry block.

## Dependencies
- WorldPainter 2.27.1 (build 20260830164405), `C:\Program Files\WorldPainter\wpscript.exe`
  (Nashorn JavaScript host; bindings `wp`, `arguments`, `params`, `scriptDir`,
  see `WPGUI/.../tools/ScriptingTool.java`). Java: Temurin 21.0.9.
- Source read at tag `v2.27.1` of github.com/Captain-Chaos/WorldPainter (commit
  d0891cf "Release 2.27.1"). Paths below are relative to `WorldPainter/`.
- `Cobblemon-fabric-1.8.0+1.21.1.jar` (from the server mods folder) for block
  names, block-entity NBT and the `habitats/berry_patch10.nbt` template.
- `tools/nbt.py` (read-only NBT/Anvil reader) for inspection.
- Not used: Minecraft client or server. Nothing here was loaded in a game.

## Implementation
`scripts/` (all small, stdlib Python + wpscript JavaScript):

| File | Role |
|---|---|
| `make_inputs.py <dir> [cobblemon jar]` | 256x256 flat height map (y=80), biome mask (x<128 forest, else plains), hand-made `apricorn_v2.schem` (Sponge v2), `apricorn_v3.schem` (Sponge v3), `oran_bush.nbt` (structure template), and optionally copies `berry_patch10.nbt` from the jar |
| `common.js` | create world (map format `org.pepsoft.anvil.1.20.5` = "Minecraft 1.20.5 - 1.21.10"), export helper, `Material.get` overload helper |
| `t1_resources.js api\|reflect` | Resources layer: public `setChance` on a modded material; `reflect` injects entries into the private settings map (unsupported hack, diagnostic only) |
| `t2_pockets.js` | two Underground Pockets custom layers with `MixedMaterial` of `cobblemon:fire_stone_ore` (y 0..70) and `cobblemon:deepslate_fire_stone_ore` (y -64..-1) |
| `t3_objects.js <objects...> --world= --level= --density=` | paint Biomes layer from the mask, load objects into a `Bo2ObjectTube`, `Bo2Layer` with density, `applyLayer(...).withFilter(createFilter().onlyOnBiome(forest))` |
| `inspect_export.py <world> <tools dir>` | decodes every section palette + packed block-state and biome data; per `cobblemon:*` block: count, y-range, west/east split, biome; every block entity with the block at its position |

The hand-made objects copy the `cobblemon:berry` block-entity fields
(`Berry`, `GrowthPoints`, `GrowthPointsSequence`, `GrowthTimer`, `LastTickTime`
(long), `MulchDuration`, `MulchVariant`, `StageTimer`) and the berry block state
(`age=5,generated=true,mulch=none,rooted=false`) from Cobblemon's own
`habitats/berry_patch10.nbt`.

## Test instructions
```
python scripts/make_inputs.py <scratch> <path>/Cobblemon-fabric-1.8.0+1.21.1.jar
copy scripts/*.js <scratch>
wpscript <scratch>/t1_resources.js api
wpscript <scratch>/t1_resources.js reflect
wpscript <scratch>/t2_pockets.js
wpscript <scratch>/t3_objects.js apricorn_v2.schem   --world=exp014-obj-schem-v2 --level=2 --density=20
wpscript <scratch>/t3_objects.js apricorn_v3.schem   --world=exp014-obj-schem-v3 --level=2 --density=20
wpscript <scratch>/t3_objects.js oran_bush.nbt       --world=exp014-obj-structure-nbt --level=2 --density=20
wpscript <scratch>/t3_objects.js oran_bush.nbt       --world=exp014-obj-structure-nbt-level4 --level=4 --density=20
wpscript <scratch>/t3_objects.js oran_bush.nbt       --world=exp014-obj-structure-nbt-density80 --level=2 --density=80
wpscript <scratch>/t3_objects.js berry_patch10.nbt   --world=exp014-obj-cobblemon-template --level=2 --density=20
python scripts/inspect_export.py <scratch>/exports/<world> tools > <world>.json
```
Exports went to the scratch directory only. Captures: `runs/20260913-wpscript/`
(`*.json` inspector output; `*.log` wpscript output with the repetitive
"Unknown tile entity ID" warnings counted, not listed). All wpscript runs exited 0.

## Results

### Q1 - Resources layer with a modded ore: RUN, FAIL (as a supported feature)
- Source: `ResourcesExporterSettings` holds a fixed `Map<Material, ResourceSettings>`
  filled only by `defaultSettings()` with 14 vanilla entries
  (`WPCore/.../layers/exporters/ResourcesExporter.java:269-291`); its constructor is
  private (`:179`), `ResourceSettings` is package-private (`:430`), and there is no
  add method - `setChance` does `settings.get(material).chance = chance` (`:220-221`).
  The GUI editor is one hard-coded spinner row per vanilla resource
  (`WPGUI/.../DimensionPropertiesEditor.java:529-570`). Deepslate swapping is a
  vanilla-only map (`ResourcesExporter.java:151`).
- Observed (`t1_api.log`): the dimension's settings list exactly `gold_ore, dirt,
  coal_ore, lava, copper_ore, diamond_ore, redstone_ore, emerald_ore,
  nether_quartz_ore, lapis_ore, iron_ore, gravel, ancient_debris, water`;
  `setChance(cobblemon:thunder_stone_ore, 20)` threw
  `NullPointerException: Cannot assign field "chance" because the return value of "java.util.Map.get(Object)" is null`.
  Export `exp014-resources-api`: 0 `cobblemon:*` blocks; control coal_ore 33,841,
  iron_ore 18,135, deepslate_iron_ore 14,644.
- Diagnostic only (`t1_resources.js reflect`, private-field injection, not a
  supported API): export `exp014-resources-reflect` contained
  `cobblemon:thunder_stone_ore` 75,483 blocks y 0..76 and
  `cobblemon:deepslate_thunder_stone_ore` 62,464 blocks y -63..-1. So the exporter
  writes whatever `Material` it is given (`ResourcesExporter.java:126`); the
  limitation is the settings model/GUI, not the chunk writer. Do not build on this.

### Q1 alternative - Underground Pockets layer with a modded block ID: RUN, PASS
- `UndergroundPocketsLayer` takes a `MixedMaterial`, and
  `MixedMaterial.create(name, Material.get("cobblemon:fire_stone_ore"))` is accepted.
- Export `exp014-pockets`: `cobblemon:fire_stone_ore` 202,287 blocks y 0..70 and
  `cobblemon:deepslate_fire_stone_ore` 173,365 blocks y -63..-1, both halves of the
  map (palette entries carry no properties: `{"Name": "cobblemon:fire_stone_ore"}`).
- Caveats (source + observation): pockets are Perlin blobs, not vanilla-style
  veins; at frequency 50 / scale 50 they are far denser than Cobblemon's
  `ore/fire_stone.json` (`minecraft:ore`, size 3) - tuning needed. The exporter
  overwrites whatever is below the top layer (`UndergroundPocketsLayerExporter.java:85,95`,
  no host-rock test), so stone vs deepslate variants must be separated by y-range
  (two layers), not by replace-target tags as in the Cobblemon feature JSON.
  The same layer in the GUI takes a custom material (not operated here: NOT VERIFIED
  in the GUI).

### Q2 - Custom Objects layer with .schem / .nbt holding Cobblemon blocks: RUN, PASS
- Supported object formats: `bo2, bo3, schematic, nbt, schem`
  (`WPCore/.../DefaultCustomObjectProvider.java:49`). Legacy MCEdit `.schematic`
  only accepts `Materials=Alpha` numeric IDs (`layers/bo2/Schematic.java:37,117`),
  so it cannot carry `cobblemon:` names (source only, not run). `.nbt` must be
  gzip with a single `palette` (`layers/bo2/Structure.java:146,151`).
- Cobblemon 1.8.0 jar: 1,235 `.nbt` files, **none with "apricorn" in the path** and no
  `.schem`/`.schematic`; apricorn trees are `cobblemon:apricorn_tree` configured
  features (`configured_feature/red_apricorn_tree.json`) and berry groves are
  `cobblemon:berry_grove` with empty config - code, no schematic. 48 `.nbt` paths
  contain "berry"; the 16 `habitats/berry_patch*.nbt` templates hold
  `cobblemon:*_berry` blocks with `cobblemon:berry` block entities plus
  `cobblemon:habitat_block` and `minecraft:jigsaw` blocks.
- Hand-made apricorn tree, Sponge v2 (`exp014-obj-schem-v2`): `apricorn_log` 416
  (y 81..84), `apricorn_leaves` 5,219 (y 84..86), `red_apricorn` 106 (y 83),
  `oran_berry` 103 (y 81) - every one in `minecraft:forest`, 0 in plains.
- Structure `.nbt` (`exp014-obj-structure-nbt`): `oran_berry` 126, all forest.
- Cobblemon template `berry_patch10.nbt` (`exp014-obj-cobblemon-template`):
  `coba_berry` 386, `payapa_berry` 380, `habitat_block` 969 (4 of 969 and 8 of 380
  payapa blocks fall in plains), and **765 literal `minecraft:jigsaw` blocks** -
  WorldPainter pastes templates verbatim; it does not resolve jigsaws or apply
  `final_state`.
- Density: chance per column = `nextInt(density*64) <= level^2`
  (`layers/bo2/Bo2LayerExporter.java:60,77`). Observed oran_bush placements:
  level 2 / density 20 = 126; level 4 / density 20 = 412; level 2 / density 80 = 41
  (predicted ~128 / ~435 / ~32).
- Block properties: random rotation rewrote `red_apricorn` `facing` (north 27,
  west 25, east 24, south 23 section-palette occurrences); `apricorn_log`
  kept `axis=y`; `apricorn_leaves` gained `distance` 1..7 and `waterlogged=false`
  and no `persistent` property. Whether Cobblemon's leaves have those properties
  and whether they decay: NOT VERIFIED.

### Q2 - Biome restriction from a script: RUN, PASS (paint-time only)
- `wp.createFilter().onlyOnBiome(id)` builds the same `DefaultFilter` class the GUI
  paint tools use (`tools/scripts/CreateFilterOp.java:141,292`); `MappingOp` skips
  columns where the filter strength is 0 (`tools/scripts/MappingOp.java:396`).
- Observed: Biomes layer painted from the mask (forest=4, plains=1); layer value at
  (10,10) forest = 2, at (200,10) plains = 0. Placements were forest-only as listed
  above. The filter restricts the object's anchor column, not its footprint:
  `exp014-obj-schem-v3` put 8 of 492 logs, 100 of 6,125 leaves and 4 of 120 berries
  across the x=128 border into plains; the template had the same spill.
- The filter is evaluated when the layer is painted; repainting biomes later does
  not move the layer (source reading of `MappingOp.go()`; not separately run).

### Q2b - Block entities survive export: RUN, PASS for Sponge v2 and .nbt; FAIL for Sponge v3
- Exporter copies object tile entities verbatim (`layers/exporters/WPObjectExporter.java:197`)
  and, for an unknown ID, only logs "Unknown tile entity ID ... can't check whether
  the corresponding block is there!" and keeps it (`minecraft/MCNamedBlocksChunk.java:28-31`).
  0 "Removing tile entity" lines in any run.
- `exp014-obj-schem-v2`: 103 `cobblemon:berry` block entities, 103 on an
  `oran_berry` block, top-level keys `Berry, GrowthPoints, GrowthPointsSequence,
  GrowthTimer, LastTickTime, MulchDuration, MulchVariant, StageTimer` - identical to
  the Cobblemon template's.
- `exp014-obj-structure-nbt`: 126/126 on `oran_berry`, same keys.
  Level-4 run 412/412; density-80 run 41/41.
- `exp014-obj-cobblemon-template`: `cobblemon:berry` 766/766 on `coba_berry` or
  `payapa_berry`; `cobblemon:habitat_block` 969/969 with `DisplaySpecies, MimicId,
  Modifiers, PhaseOrder, PoolId, RangeOfInfluence, ReplaceSpawns, SpawningStyle`;
  765 `minecraft:jigsaw` block entities.
- `exp014-obj-schem-v3`: 120/120 `cobblemon:berry` on `oran_berry`, but the only
  data key is `Data` - the fields stay nested. `Schem.getTileEntity` strips `Id`/`Pos`
  but never unwraps the v3 `Data` compound (`layers/bo2/Schem.java:287-306`).
  Export Sponge v2 (or `.nbt`), not v3.
- Chunk format: exported chunks carry `DataVersion` 2860 (1.18.0) and
  `Status: full` (`minecraft/MC118AnvilChunk.java:249`); `level.dat` DataVersion 3837.
  Minecraft 1.21.1 will run its data fixers on these chunks; whether the
  Cobblemon block entities come through that upgrade and load in game: NOT VERIFIED.

## Limitations
- Nothing was loaded in Minecraft. Block states, block-entity data, leaf behaviour,
  berry growth, habitat-block spawning and chunk upgrade from DataVersion 2860 are
  NOT VERIFIED in game.
- The GUI was not operated. Everything was driven by wpscript; the GUI Resources
  editor and Custom Objects/Pockets dialogs are cited from source only.
- Apricorn trees: no Cobblemon schematic exists; the tested tree is a hand-made
  stand-in, not Cobblemon's `apricorn_tree` feature shape.
- Only vanilla biome IDs (forest, plains) were used for filtering; custom/Terralith
  biome filtering NOT VERIFIED.
- Only flat 256x256 terrain at y=80, one region file, no caves or water.
- Pocket frequency/scale and object density were not tuned to match Cobblemon's
  generation rates.

## Decision
Adapt. WorldPainter can do the placement, with these rules:
1. Modded ores: do **not** use the Resources layer (vanilla-only by design). Use
   Underground Pockets layers with a custom material per ore, split stone/deepslate
   variants by y-range, and tune frequency/scale; or place ores in a post-export
   script that replaces stone/deepslate by tag like Cobblemon's `minecraft:ore` feature.
2. Apricorn trees and berry bushes: Custom Objects layers with Sponge **v2** `.schem`
   or structure `.nbt` objects, biome-filtered at paint time. Author the apricorn
   tree objects ourselves (none ship with Cobblemon).
3. Post-export script needed for: jigsaw blocks in Cobblemon templates (replace with
   `final_state` or strip them before import), any Sponge v3 object (unwrap `Data`),
   and anything that must follow biomes painted after the object layer.
4. Before relying on it, load one exported world in the 1.21.1 + Cobblemon 1.8.0
   server and check berries, habitat blocks and apricorn leaves (follow-up below).

## Follow-up
- In-game check (boot-test skill, disposable world copy): load
  `exp014-obj-cobblemon-template` / `exp014-obj-schem-v2`, confirm berries are
  harvestable and keep their `Berry` data after the DataVersion 2860 upgrade,
  habitat blocks spawn, apricorn leaves do not decay.
- Tune pockets frequency/scale against Cobblemon's ore placed features.
- Object library: author apricorn tree variants (7 colours) as Sponge v2 files.
