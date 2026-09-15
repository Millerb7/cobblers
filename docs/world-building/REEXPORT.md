# Re-export: cobblers-10240

## 2026-09-14 (third): Crater-only volcanic biomes; pre-build checks

**Status: exported, pregenerated, and checked.** The heightmap and river cuts are unchanged from
the export below.

**Why it was re-exported.**
- **The tags:** the Mining Town's identity needs `#cobblemon:is_volcanic` and
  `#cobblemon:is_thermal`. Cobblemon 1.8.0 fills them only with Terralith, Biomes O' Plenty,
  Wythers and Darker Depths biomes, none of which is loaded.
- **The overlay:** `cobblers_spawn_tags`, built from `regions.json` `spawn_tag_overlays` by
  `tools/spawn_tag_pack.py`, adds `stony_peaks` and `savanna_plateau`, the Craters' two
  biomes.
- **The leak it had to fix:** 14% of `stony_peaks` was painted on the Crags summits. That
  band now paints `jagged_peaks`, so both tag biomes are 98–99% inside the Craters (the rest
  is region-edge rasterisation).

| Step | Result |
| --- | --- |
| Paint maps | regenerated with the Crags change; `spawn_tag_pack.py --check-paint`: `stony_peaks` 98.85% and `savanna_plateau` 98.17% inside the Craters |
| Export | the same `reexport.py` command, with the old world from `cobblers-server-retired/2026-09-14-biome-tags/`; export 835 s; 484 region files, 2.33 GB; `seed_match: true`; `.world` sha256 `dae3d5c5…` |
| Datapack | `spawn_tag_pack.py --install <server>/datapacks`. Global Packs force-loads `datapacks/`; the log shows "Found new data pack cobblers_spawn_tags, loading it automatically", and `datapack list enabled` includes it |
| Border | 10240 |
| Distant Horizons | `dh pregen start minecraft:overworld 4096 4096 320`, complete in 12.5 minutes; `data/DistantHorizons*` 659 MB; region files still 484 |

**Tags checked in game** with `execute if biome` on force-loaded painted chunks. `locate biome`
is no use here: it consults the world generator's noise biomes, not the painted chunks.

| Position | Result |
| --- | --- |
| Mining Town (6633, 139, 5716) | `stony_peaks`; volcanic yes, thermal yes; volcanic at y60 underground too |
| Crater rim (5913, 111, 5071) | volcanic yes, thermal no (as designed) |
| Crags summit (3541, 164, 1323) | `jagged_peaks`; volcanic no |
| Crags grove (3295, 128, 1402) | volcanic no |

**Not checked:** that Cobblemon actually spawns volcanic or thermal species there. That is an
encounter-table matter, still deferred.

### Pre-build checks on the exported world

**1. Displaced City depth.** Full columns under the 200 × 200 cavern footprint were read from
the region files.
- **Bedrock** is at y−64 under all 40,000 columns.
- **The y32–72 band** is 98.3% solid: stone, granite, andesite, diorite, dirt and gravel
  pockets, coal and iron ore, with 884 air cells.
- **Rock over a y72 ceiling:** 24 blocks at its thinnest, 31 at the median.
- **The spec stands.**

**2. Surface against the heightmap.** A full-map `world_heights extract` and `compare` on the
previous export; the terrain is unchanged in this one.
- **Chunks:** all 262,144 present.
- **Land:** 99.10% exact and 99.94% within 1 block. The rest is WorldPainter's rounding and
  small plants.
- **Seabed:** 99.9999% exact.
- **First pass misreported this:** it showed about 10 million land columns 5 blocks high. That
  was tree canopy counted as ground; `world_heights.py` now treats logs and leaves as cover.
- **Below sea level without water:** 160,609 columns, almost all shoreline, where heightmap
  y61.6–62 rounds to a y62 ground block.

**3. Rivers and lakes.** Every cut course compared with its paint level map.
- **Planned water columns:** 95,798.
- **At the planned level:** 98.1%.
- **Raised:** 1.9%, where a course meets a lake or another course; water is only ever raised.
- **Dry or lower:** 0.
- **Lakes:** at their levels (Tilpey 77, Shrew 106, Arrow 100 and so on).

**4. Earlier paint issues.** A scan of all 451,584 saved chunks, including the margin.
- **Coastal overhang:** fixed. There are 0 log or leaf blocks in sea water, and 0 ice or snow at
  sea level over water.
- **The old grass name:** WorldPainter writes `minecraft:grass` (1,250,087 blocks), the
  pre-1.20.3 name.
  - The chunks carry DataVersion 2860, so the server upgrades them to `short_grass` on load.
    In game, `execute if block … minecraft:short_grass` passes on the scanned positions.
  - Only Distant Horizons, which reads raw region files, logs "Unknown registry key …
    minecraft:grass". The LODs miss those tufts, which is invisible at LOD distance.
  - **No repaint is needed for it.**

**Retired, not deleted,** to `cobblers-server-retired/2026-09-14-biome-tags/`: the previous
`cobblers-10240` world and `cobblers-10240.world`.
- **The client LOD cache was left in place,** because the game was running. Only the Crags'
  summit colour differs from what it holds. Clear it in Distant Horizons if that band looks
  stale.

## 2026-09-14 (second): river-cut terrain, rivers filled

> Superseded by the export above (same terrain, the Crags repainted). That world is in
> `cobblers-server-retired/2026-09-14-biome-tags/`.

**Status: exported and pregenerated for Distant Horizons.** No player has been in it yet.

| Step | Result |
| --- | --- |
| Heightmap | `land_8k_16_eroded_rivers.png`, sha256 `861d10ac…`: the carved revision with graded rivers, catchment-sized channels and the major river's valley cut in by `tools/grade_rivers.py` ([`RIVERS.md`](RIVERS.md)). Same import line |
| Re-measured | `data/cells.json` (no drift), `data/regions.json` measured blocks (`tools/region_measure.py`); validator clean |
| Paint maps | `python tools/paint_maps.py --source-root <source> --out build/paint`. Adds per-column water for all 10 cut courses, bed and bank material, river biome; ravines keep gravel floors |
| Export | the same `reexport.py` command, with the old world from `cobblers-server-retired/2026-09-14-rivers/` |
| WorldPainter | paint applied; save 23 s; export 764 s; 484 region files, 2.33 GB; `.world` sha256 `c0c716bf…` |
| Water | lakes as before. Rivers, raised per column: major river trunk 41,804 columns, Viltri's Path 12,747, Watering Hole outflow 13,820, Tilpey outflow 7,246, and six smaller courses |
| Seed | carried; `seed_match: true` |
| Border | `worldborder get`: 10240 |
| Distant Horizons | `dh pregen start minecraft:overworld 4096 4096 320`, complete in 7.5 minutes; `data/DistantHorizons*` 667 MB; region files still 484 |

**Checked in the region files** (`world_heights.extract` on four stretches, 37,601 planned water
columns):
- **Dry columns:** 0.
- **At the planned level:** 96–100%.
- **The rest** are 1 block higher, inside Lake Tilpey's basin outline, where the lake's level
  raises them.

**Retired, not deleted,** to `cobblers-server-retired/2026-09-14-rivers/`:
- the previous `cobblers-10240` world, with its DH stores;
- `cobblers-10240.world`;
- the client LOD cache `local+ho`, because the seed is unchanged and it would otherwise show the
  old terrain.

**Not checked in game:**
- how river water behaves at its 1-block steps and where it meets a lake;
- how the river biome spawns;
- whether the known `minecraft:grass` issue below still applies.

## 2026-09-14: carved terrain, painted

> Superseded by the export above. The world it describes is in
> `cobblers-server-retired/2026-09-14-rivers/`.

**Status: exported and pregenerated for Distant Horizons.** No player has been in it yet.

| Step | Result |
| --- | --- |
| Heightmap | the carved revision, sha256 `acdc3d1d…`, same import line as below |
| Paint maps | `python tools/paint_maps.py --source-root <source> --out build/paint` from `data/regions.json` presets and `data/landmarks.json` water bodies ([`REGIONS.md`](REGIONS.md) §6) |
| Export | `python tools/reexport.py --old-world <retired cobblers-10240> --out-dir ../cobblers-server --name cobblers-10240 --world-file <source>/cobblers-10240.world --paint build/paint/manifest.json` |
| WorldPainter | 2.27.1. 7,056 tiles with the margin. Paint applied in 11 s; save 21 s; export 672 s; 484 region files, 2.3 GB |
| Lakes raised | Tilpey y77 (1.19 M columns), Shrew y106, Arrow y100, Marshy Marsh y100, Peak Pond y105, Lake Viltri y103, Mt Clay pond y119, Watering Hole y95 |
| Seed | carried; `level.dat` seed sha256 matches `48202407…`; `WorldGenSettings`, datapacks and game rules carried as before |
| Border | `worldborder get`: 10240 in the overworld and the Nether |
| Spawn | (3400, 3400) unchanged. It now lands on the floor of the Rift's west spur, about y96 |
| Distant Horizons | server generation stays off. LODs built from the exported chunks with `dh pregen start minecraft:overworld 4096 4096 320`: complete in 6 minutes, 673 MB, and region files still 484 (nothing generated). The client LOD cache for this server was moved out, because DH keys it by seed |

**Spot check** of 8 region files (craters, dunes, glacier, Shrew Lake, marsh, Viltri Woods,
Pine Isles, the Tri Peaks):
- basalt, blackstone and magma, sand and cactus;
- snow layers and snow blocks;
- mud;
- oak, birch and spruce logs;
- sweet berry bushes, azalea, tall grass;
- raised water.

**Known issues in this export:**
- **`minecraft:grass` blocks.** 25,754 of them in the sample. They do not come from the plant
  sets, which avoid "Short Grass"; WorldPainter itself writes the old block name.
  - *Corrected 2026-09-14:* the earlier note here said those columns load without it. That was
    wrong. The chunks carry DataVersion 2860, so the server upgrades the name to `short_grass`
    on load, which was checked in game.
  - Only Distant Horizons, which reads raw region files, warns.
- **Coastal paint overhang.** The maps were generated before a fix: sub-region polygons
  overhanging the coast could put tree density, plants and frost on sea columns. The fixed tool
  clears all three on sea and on flooded lake columns. It applies from the next repaint.
- **Not yet checked in game:** how painted trees look, whether any grow in water, and how
  lakes behave when their water updates.

**Retired, not deleted,** to `cobblers-server-retired/2026-09-14/`:
- the unpainted `cobblers-10240` world, with its DH stores;
- `cobblers-10240.world`;
- the client LOD cache `local+ho`;
- an aborted partial export.

The earlier 2026-09-13 export is described below.

---

**Status (2026-09-13): done, verified, stopped before painting.**

The server world is now `cobblers-10240`, exported from the canonical heightmap. Nothing is
painted or carved: the terrain is the heightmap and nothing else.

## 1. What was done

| Step | Result |
| --- | --- |
| a. Ocean depth mapping | **Applied.** WorldPainter's script API and GUI only take whole-number world levels, so 10.093 cannot be entered. The same straight line was written as image level −32.125 → y10 and 65278 → y200, using WorldPainter's own `HeightMapImporter`. At image level 0 it gives y10.0935. No derived heightmap was needed, and the 4.3% shift from `low_out 10` was not accepted |
| b. Seed | **Carried over.** The runner passes it to WorldPainter through the environment only. After export the new `level.dat` seed matches the old one by sha256 (`48202407…`). WorldPainter had written its own overworld preset (`large_biomes`) and per-dimension generator seeds, so the old `WorldGenSettings` was copied in whole. Overworld, Nether, End and the mod dimensions now carry the old generators exactly |
| c. Heightmap import | WorldPainter reported **bit depth 16**, 8192×8192, unsigned, no alpha, value range 0..65535 (`land_8k_16_eroded.png`, sha256 `526fe220…`) |
| d. Border | **10240 × 10240, centre 4096,4096.** Written into `level.dat` by WorldPainter. The server reports "10240 block(s) wide" in the overworld, Nether and End. The export is a full overwrite: a new world, not a trim. None of the old world's chunks or its 62 structure starts exist in it |
| e. `world.json` | `heightmap.status` "ok", sha256 recorded, import block updated. The validator's `cell-terrain` and `spatial` checks now **execute**: 0 errors, 0 skipped |

**Export geometry:**

| | Blocks |
| --- | --- |
| Landmass (heightmap) | 0..8191 |
| World border | −1024..9215 |
| Exported canvas | −1280..9471 (484 region files, 451,584 chunks, 2.2 GB) |

- **The 256-block ring outside the border is unreachable ocean.** It exists so chunks loaded
  within view distance of the border already exist, and nothing ever generates beyond the
  wall.
- **Carried from the old world's `level.dat`:** `WorldGenSettings`, `DataPacks` (Terralith,
  Sinnoh, Johto and Hoenn stay disabled), `GameRules`, difficulty (hard), game type,
  commands flag.
- **Spawn:** (3400, y122, 3400), as before. The old world's spawn was at the same x,z.

**WorldPainter defaults** that apply because nothing was painted:
- the default theme (grass, beaches near water, stone mix below);
- the **Resources layer applied everywhere**, which places vanilla ores;
- no caves or chasms;
- Minecraft population off: chunks are written `full`, with no features or structures.

**Reproduce:**
```
python tools/reexport.py --old-world <old world> --out-dir ../cobblers-server --name cobblers-10240 --world-file <source>/cobblers-10240.world
```
The WorldPainter project is saved as `cobblers-10240.world` next to the heightmap (111 MB).
It is the file future painting starts from.

## 2. Verification against the exported world

Measured from the region files, not the heightmap: `tools/world_heights.py extract`, then
`compare` against the heightmap at the new mapping.

### Chunks

| | Count |
| --- | --- |
| Chunks expected in the canvas | 451,584 |
| Present, all status `full` | 451,584 |
| Saved outside the canvas | 0 |
| Columns without ground | 0 |

### Land elevation: did it shift?

- **No.** Across all 44.5 million land columns, WorldPainter's height matches the
  heightmap's float height rounded to the nearest block in 99.09% of cases, and every
  column is within one block.
- **Against the previous mapping (40/200):** of 51.3 million columns above the old y40
  floor, 99.21% are identical, 404,292 are one block higher, 204 one lower, and 1 column is
  two higher.

| Where the +1 blocks are | Columns | Why |
| --- | ---: | --- |
| Clipped summits at **y201** | 393,236 | WorldPainter does not clamp at the top of the line. Source values above 65,406 continue past y200 to y200.75 and round to y201. The design clamp was y200 |
| Elsewhere | about 10,000 | rounding at exactly half a block |

### Seabed: does it match the proposal?

**Yes, block for block.** Every one of the 22.6 million columns below sea level matches the
heightmap prediction exactly.

| Open sea (region plan sea mask) | Before (y40 floor) | Proposal | **Export** |
| --- | ---: | ---: | ---: |
| Median seabed | y40 | y21.5 | **y21** (whole blocks) |
| At or below y20 | 0% | 46.9% | **48.0%** |
| At or below y30 | 0% | 63.6% | **64.3%** |
| Sitting on exactly y40 | 75.9% | — | **1.2%** |
| 10th / 90th percentile | 40 / 57 | 10 / 53 | 10 / 53 |

- **The margin inside the border** is a flat seabed at y10 with water to y62, on all 48.5
  million columns.
- **Below sea level, 98.95% of columns hold water up to y62.** The rest are columns whose
  float height rounds up to y62 itself.
- **No water sits above sea level.**

### Clipped summits

| | Share of land |
| --- | ---: |
| Heightmap at or above the y200 ceiling (source ≥ 65,278) | 0.93% |
| Export at y200 or y201 | 0.96% |
| Export at y201 | 0.88% |
| Source pixels at full scale 65,535 (all columns) | 0.34% |

**The summits are still flat, now one block higher.** The top of the line maps full scale to
y200.75, so the summits sit at y201. `world.json` keeps the y200 clamp as the design value.
Measuring the summit plateaus from the world, not the heightmap, reads y201.

### The border holds, and nothing generates outside it

**On a headless boot with `--world cobblers-10240`:**
- `worldborder get` gave 10240 in the overworld, `the_nether` and `the_end`, before and after
  a full save.
- Datapacks came up exactly as carried: 57 enabled; Terralith, Sinnoh, Johto and Hoenn listed
  as available but not enabled.

**Scanned after the server was stopped:**
- **Canvas:** all 451,584 chunks inside, **0 outside**.
- **Border:** 409,600 chunks inside. The 41,984 outside are exactly the pre-written buffer
  ring, with 0 structure starts.
- **No Nether or End chunks were created.** `DIM-1` and `DIM1` hold only DH data folders.
- **The server's chunk upgrade changed nothing.** A second extraction after the boot, DH
  pregen and save matches the pre-boot extraction: 0 ground columns and 0 water columns
  differ. All 451,584 chunks are still `full`.

**Distant Horizons:**
- Server-side distant generation is now **off**: `enableServerGeneration = false` in
  `config/DistantHorizons.toml`, with a backup beside it. DH ignores the world border, and with
  generation on it would generate real chunks up to 4,096 chunks around a player.
- LODs were built from the exported chunks with `dh pregen start minecraft:overworld 4096 4096
  320`: 7 minutes, 561 MB. It generated nothing outside the canvas, as the scan above shows.
- Clients sync those LODs when they join.
- **Not verified:** a player walking or flying into the wall. The boot was headless.

## 3. Changes outside the repository

| Path | Change |
| --- | --- |
| `cobblers-server/cobblers-10240/` | new world |
| `cobblers-server/server.properties` | `level-name=erosion-land-8k` → `cobblers-10240` (one line; backup `server.properties.pre-cobblers-10240`) |
| `cobblers-server/config/DistantHorizons.toml` | `enableServerGeneration = false` (backup `.pre-reexport-20260913`) |
| `Documents/cobblers-10240.world` | new WorldPainter project |
| `cobblers-server-retired/2026-09-13/erosion-land-8k/` | **the old world, moved here** with its Distant Horizons stores (1.7 GB) |
| `cobblers-server-retired/2026-09-13/client-distant-horizons-cache/` | the client LOD cache from the Modrinth profile "Fabric 1.21.10" (116 MB) |

**Why the client cache was moved:** DH names a server's LOD folder from the seed, which is
unchanged. Left in place, the client would have drawn the old terrain in the distance.

**Retired, not deleted.** Permanent deletion is left to you:
```
Remove-Item -Recurse -Force "C:\Users\wnd\Documents\github\cobblers-server-retired\2026-09-13"
```
Player data in the old world (inventories, Pokédex, Cobblemon party data) went with it. The
new world has none.

## 4. What the flight will show that is not a decision yet

- **The rift floods where its floor is below y62.** That is 917 columns, 783 with water.
  WorldPainter floods everything below sea level. The landmark's policy is `water: never`,
  with the treatment still undecided.
- **The rest of the unpainted defaults:**
  - summits at y201;
  - vanilla ores everywhere (the Resources layer);
  - grass on all land and beaches at the waterline;
  - no biomes painted: WorldPainter's default applies;
  - no trees or features.
- **The margin** is a flat y10 plain to the wall. The seabed pass is not built.
- **`exp013-structures`** is still in the server folder. It was built from the old world and
  is not the world the EXP-013 D/E session will use.
