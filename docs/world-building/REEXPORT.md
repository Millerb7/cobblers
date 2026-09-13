# Re-export: cobblers-10240

**Status: done 2026-09-13, verified, stopped before painting.**

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
