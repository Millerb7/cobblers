# EXP-017: Underground Pockets calibration for modded ores, and in-game load of exported Cobblemon block entities

## Objective
Two questions left open by EXP-014.
**A.** What WorldPainter Underground Pockets settings reproduce the density and vein size of each
modded ore the server generates (Cobblemon, LumyMon, Legendary Monuments)? "Yes" means the
handcrafted region gets the same ore economy as the Cobbleverse base without a post-export ore pass.
**B.** Do Cobblemon blocks and block entities written by WorldPainter (chunk DataVersion 2860) survive
loading and saving in the Minecraft 1.21.1 + Cobblemon 1.8.0 server? "Yes" means berries, habitat
blocks and apricorn trees can be placed as Custom Objects.

## Success criteria
- A1: every modded ore feature's config is read from the loaded jars (target, replace rule, size,
  discard, count/rarity, height, biome) and turned into a density per 1,000 host blocks with a stated formula.
- A2: a frequency x scale sweep of exported worlds gives a measured relation to density and blob size.
- A3: 2-3 recommended settings, exported and measured, land within about ±30% of the target density
  with a comparable vein size.
- B1: after booting a copy of an EXP-014 export, `data get block` returns the exported berry/habitat
  data and `execute if block` finds the apricorn blocks.
- B2: after `stop`, the saved region still holds those block entities with the same data.

## Dependencies
- WorldPainter 2.27.1 `wpscript.exe`; source at tag v2.27.1 (paths below relative to `WorldPainter/WPCore/src/main/java/org/pepsoft/worldpainter/`).
  `org.pepsoft.util.PerlinNoise` is not in that repo: read with `javap` from `C:\Program Files\WorldPainter\lib\Utils.jar`.
- Server `cobblers-server`: Fabric 1.21.1, `Cobblemon-fabric-1.8.0+1.21.1.jar`, `LumyMon-0.6.6.jar`,
  `LegendaryMonuments-Cobbleverse.jar`, `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar`.
  Vanilla classes read with `javap` from `.fabric/remappedJars/minecraft-1.21.1-0.19.5/server-intermediary.jar`,
  names resolved with `stackdeobf_mappings/yarn_1.21.1+build.3.gz`.
- EXP-014 exports `exp014-obj-cobblemon-template` and `exp014-obj-schem-v2` (still in the scratch directory).
- `tools/nbt.py`, `tools/world_heights.py` (`unpack_states`). Python 3.10 + numpy (no scipy).

## Implementation
`scripts/` (nothing here is part of the pack; exports and worlds stayed in the scratch directory):

| File | Role |
|---|---|
| `ore_model.py <mods dir> <out.json>` | reads every ore placed/configured feature from the jars, height pdfs, Monte-Carlo of `OreFeature`, density per y and per band |
| `make_heightmap.py <dir>` | `heightmap100.png` (flat y=100) |
| `pockets_sweep.js <spec...>` | one Underground Pockets layer per world, `name:block:freq:scale:min:max[:value]` |
| `pockets_verify.js <plan.json>` + `verify_plan.json` | multi-layer verification worlds, optional NOISE `MixedMaterial` dilution (ore row + host row) |
| `measure_pockets.py <tools> <out> [--rows LO HI] <worlds>` | per-world ore permille in the rows, per-row permille, 6-connected blob sizes |
| `calibrate.py <sweep json> <out>` | k = measured / nominal, blob size by scale and frequency |
| `stone_block.js <name>` | flat world with all Resources chances 0 (clean host for the in-game vein check) |
| `vein_check.py place|count` | `/place feature` on a 31x31 grid per y plane over RCON; count the blocks placed per attempt from the saved region |
| `probe_objects.py`, `check_objects.py`, `compare_objects.py` | Task B: snapshot Cobblemon blocks + block entities of a world; RCON `data get block` / `execute if block` checks; diff export vs saved world |
| `srv.py` | RCON helper (password read from the server's `.rcon-password`, never printed or logged) |

Captures: `runs/20260913-exp017/taskA/` and `taskB/` (JSON outputs, wpscript logs, RCON logs, boot-log excerpts).

## Test instructions
```
# A1 model
python scripts/ore_model.py <server>/mods <scratch>/ore_model.json --sim 100000
# A2 sweep (wpscript host, in a scratch dir holding the .js and heightmap100.png)
python scripts/make_heightmap.py <scratch>
wpscript pockets_sweep.js sw-f1-s20:cobblemon:fire_stone_ore:1:20:-64:319 ...   # f {1,2,5,10,20,50} x s {5,10,20,35,50,100,200}
wpscript pockets_sweep.js val-f1-s20-v1:cobblemon:fire_stone_ore:1:20:-64:319:1 ...
python scripts/measure_pockets.py tools <scratch>/sweep_measure.json <scratch>/exports/sw-* <scratch>/exports/val-*
python scripts/calibrate.py <scratch>/sweep_measure.json <scratch>/calibration.json
# A3 verification
wpscript pockets_verify.js verify_plan.json
python scripts/measure_pockets.py tools out.json --rows 0 94 exports/ver-cobblemon-normal-a ...   # rows per layer, see Results
# A (vein size in game)
wpscript stone_block.js exp017-stone-block ; copy to <server>/exp017-veins
java -Xms4G -Xmx10G -jar fabric-server-launch.jar nogui --world exp017-veins
python scripts/vein_check.py place rcon.jsonl place.json ; RCON stop
python scripts/vein_check.py count <server>/exp017-veins tools post-count.json
# B (per world: exp014-obj-cobblemon-template -> exp017-objects-template, exp014-obj-schem-v2 -> exp017-objects-schemv2)
python scripts/probe_objects.py <export> tools pre.json
copy export to <server>/<folder>; java ... nogui --world <folder>; python scripts/srv.py wait-ready <console log>
python scripts/check_objects.py pre.json check.json rcon.jsonl
python scripts/srv.py cmd rcon.jsonl "forceload remove all" "save-all flush" ; ... stop ; srv.py wait-exit
python scripts/probe_objects.py <server>/<folder> tools post.json ; python scripts/compare_objects.py pre.json post.json
move <server>/<folder> back to the scratch directory
```
Every boot started with no java process running and ended with none. `cobblers-10240` was not
booted or read; `server.properties` was not edited (the server rewrote it on start as it always does;
`level-name` is still `cobblers-10240`).

## Results

### A1 - ore configs (RUN, read from jars and bytecode)
| Ore feature | Type, size, target | Placement | Biomes |
|---|---|---|---|
| Cobblemon `<x>_stone_lower` / `_upper` (x = dawn, dusk, fire, ice, leaf, moon, shiny, sun, thunder, water) | `minecraft:ore` 3, discard 0; `tag stone_ore_replaceables` -> `<x>_stone_ore`, `tag deepslate_ore_replaceables` -> `deepslate_<x>_stone_ore`; sun stone also `tag minecraft:terracotta` -> `terracotta_sun_stone_ore` | count 8, trapezoid -64..192 / 64..320 | `#cobblemon:has_ore/ore_<x>_stone_normal` |
| Cobblemon `<x>_stone_lower_rare` / `_upper_rare` | same feature | count 4, same ranges | `..._rare` tag |
| Cobblemon `moon_stone_dripstone` | ore 3, `tag cobblemon:dripstone_replaceables` (= `dripstone_block`) | count 256, trapezoid -64..256 | `ore_moon_stone_dripstone` |
| Cobblemon `fire_stone_nether` | ore 5, `block_match netherrack` | count 1, uniform 10..245 (nether) | `ore_fire_stone_nether` |
| Cobblemon `type_gems` | `cobblemon:type_gem` (core `deepslate_crystal_core`; code requires origin in `deepslate_ore_replaceables` with an air neighbour) | count 2, rarity 1/3, trapezoid -64..0 | `#minecraft:is_overworld` |
| LumyMon `dragon/electron/ice/rock/steel_ore_placed` | `scattered_ore` 1; sculk / sandstone / packed_ice / terracotta (block_match), steel `tag deepslate_ore_replaceables` | count 30 u(-60..0) / 1 u(30..90) / 3 u(65..125) / 2 u(75..135) / 1 u(-50..10) | deep_dark / desert / ice_spikes+frozen_ocean+frozen_peaks / badlands+eroded+wooded / dripstone_caves |
| Legendary Monuments `galar_particle_ore_placed` | ore 5, `stone_ore_replaceables` | rarity 1/4, count 5, trapezoid -48..24 | `foundInOverworld()` |
| Legendary Monuments `deepslate_galar_particle_ore_placed` | ore 5, `deepslate_ore_replaceables` | count 10, trapezoid -24..56 | `foundInOverworld()` |
| Mega Showdown `keystone_ore` | no feature; one block in `structure/megaroid.nbt` | - | - |

Biome attachment is code, not data: `CobblemonOrePlacedFeatures` pairs `upper`+`lower` with the
`_normal` tag and the `_rare` pair with `_rare` (UNDERGROUND_ORES); LumyMon/Legendary Monuments use
Fabric `BiomeSelectors` (intermediary biome fields resolved with yarn). No datapack on the server
overrides these features (searched `datapacks/*.zip`, `datapacks/extra/*.zip`, `cobblers_campaign`).

### A1 - expected density (RUN; model + in-game check)
`D(y) per 1,000 host blocks = 1000 * count / rarity * B * p(y) / 256`, with p(y) the uniform or
trapezoid pdf (trapezoid = min + U[0,m] + U[0,l], checked in `TrapezoidHeightProvider` bytecode) and
B the blocks one attempt places when every cell is host.
- The assumption "size N places about N blocks" is wrong for small veins. Simulated `OreFeature`
  (bytecode-faithful): size 3 **B = 0.46** (65 % of attempts place nothing, blobs 1.10 blocks),
  size 5 B = 3.15 (blobs 2.27). `scattered_ore` size 1: B = 0.5 (`nextInt(size+1)` attempts).
- In game (`/place feature`, 961 attempts per plane, clean stone/deepslate host): thunder stone
  0.413 / 0.395 (stone) and 0.453 (deepslate), 67-69 % empty; galar stone 2.95; deepslate galar 2.44
  (21 % empty); steel 0.512. The game is within 10 % of the model for size 3 and size 1, and 6-23 %
  below it for size 5.

Targets (model): Cobblemon stone normal tier 0.029 (deepslate -63..-1), 0.084 (0..63), 0.112 (64..191),
0.098 (0..255); rare tier half of that. The lower+upper pair makes a near-flat profile from 64 to 192.
Others: dripstone moon stone 2.0 per 1,000 dripstone blocks (0..191); nether fire stone 0.052 per 1,000
netherrack; galar stone 0.146 (0..24); galar deepslate 0.92 (-24..-1); dragon 0.96 per 1,000 sculk;
electron 0.032 per 1,000 sandstone; ice 0.096 per 1,000 packed ice; rock 0.064 per 1,000 terracotta;
steel 0.032 per 1,000 deepslate (-50..-1).

### A2 - calibration (RUN, 46 exports)
Source: threshold = the noise level exceeded by `frequency x 0.9^(8 - value)` per mille of samples
(`layers/pockets/UndergroundPocketsLayerExporter.java:29`, `PerlinNoise.getLevelForPromillage` is a
lookup table), noise cell `4.099 x scale / 100` blocks (`:31`), pockets stop `topLayerDepth` below the
surface (`:73`) and overwrite any block. `applyLayer` without `toLevel` writes value 8
(`tools/scripts/MappingOp.java:74`); the GUI calls frequency "Occurrence" (1..1000, default 10) and
scale defaults to 100.

Measured (256x256x158 rows, stone mix + default Resources):

| | f=1 | f=2 | f=5 | f=10 | f=20 | f=50 |
|---|---|---|---|---|---|---|
| permille, mean over scales | 0.62 | 1.49 | 3.74 | 7.54 | 16.2 | 42.6 |
| k = measured/nominal (min-max) | 0.62 (0.47-0.75) | 0.74 (0.60-0.86) | 0.75 (0.64-0.84) | 0.75 (0.67-0.87) | 0.81 (0.74-0.88) | 0.85 (0.84-0.87) |
| blob mean, scale 5-35 | 1.00-1.02 | 1.00-1.03 | 1.01-1.05 | 1.02-1.08 | 1.04-1.12 | 1.14-1.27 |
| blob mean, scale 50 | 1.09 | 1.14 | 1.22 | 1.27 | 1.39 | 1.93 |
| blob mean, scale 100 | 2.47 | 3.23 | 3.29 | 4.09 | 6.08 | 11.6 |
| blob mean, scale 200 | 16.3 | 19.9 | 20.6 | 27.5 | 47.2 | 129 |

Value tests (f=1, s=20): value 1 -> 0.263, value 4 -> 0.327, value 12 -> 0.994; f=10 value 4 -> 4.93.

**Relation:** `permille ~= k x frequency x 0.9^(8 - value) x q`, k ~= 0.75 (0.62 at frequency 1,
±25 % between seeds), q = ore/(ore + host) when the pocket material is a NOISE MixedMaterial.
Density does not depend on scale; blob size does: scale <= 35 gives single blocks, 50 about 1.1-1.4,
100 about 2.5-6, 200 tens of blocks. Per-row density varies strongly at low frequency (f=1 rows 0.02-1.3).
The floor without dilution is about 0.26 permille (frequency 1, value 1): 2.7x the Cobblemon normal
stone target, 9x its deepslate target. Hence the recommendations dilute with a host row.

### A3 - recommendations and verification exports (RUN for the rows marked measured)
All layers: Underground Pockets, applied (or painted) at value 8, split at y=0 into a stone and a
deepslate layer, painted only where the source biome applies (biome filter as in EXP-014).
"NOISE a:b host" = custom material in NOISE mode with rows (ore x a) and (host x b).

| Ore | Layer(s) | Target permille | Measured | Vein |
|---|---|---|---|---|
| Cobblemon evolution stones, normal tier | stone: `<x>_stone_ore` NOISE 1:5 `stone`, f 1, s 20, y 0..max; deepslate: `deepslate_<x>_stone_ore` NOISE 1:20 `deepslate`, f 1, s 20, y -64..-1 | 0.093 (rows 0..94) / 0.029 | 0.094, 0.103 / 0.021, 0.036 (2 seeds) | singles (vanilla 1-2 blocks, blob 1.10) |
| same, rare tier | stone 1:11, deepslate 1:41, same f/s | 0.047 / 0.014 | 0.057 / 0.0165 | singles |
| both tiers in one biome | add them: stone 1:3, deepslate 1:13 (computed, not exported) | 0.14 / 0.043 | not verified | |
| Galar particle, deepslate | `deepslate_galar_particle_ore` plain, f 1, s 100, value 10 (value 8 gives ~0.7), y -24..-1 | 0.92 | 0.84 | blob 2.45 (vanilla 2.27; in game 2.44 blocks/attempt) |
| Galar particle, stone | `galar_particle_ore` NOISE 1:4 `stone`, f 1, s 100, y 0..24 | 0.146 | 0.174 | blob 1.2 (clusters broken up by dilution) |
| LumyMon steel (dripstone caves) | `lumymon:steel_ore` NOISE 1:18 `deepslate`, f 1, s 10, y -50..-1 | 0.032 | 0.033 | singles (vanilla singles) |
| Cobblemon fire stone, nether | Nether dimension: `nether_fire_stone_ore` NOISE 1:13 `netherrack`, f 1, s 100, y 10..245 | 0.052 (in-game B suggests 0.040-0.049) | not verified | diluted clusters |
| Cobblemon moon stone, dripstone | not a pocket: put the ore into the dripstone material, NOISE `dripstone_block` 499 : `dripstone_moon_stone_ore` 1 | 2.0 per 1,000 dripstone | not verified | |
| LumyMon dragon / ice | same idea in the painted sculk / packed-ice material: ~1:1040 / ~1:10400 | 0.96 / 0.096 per host | not verified | |
| LumyMon electron / rock, Cobblemon terracotta sun stone | host is sandstone / terracotta, which WorldPainter usually paints as the top layer that pockets never reach (`:73`); built-in Mesa terrain has no material mix | 0.032 / 0.064 / 0.098 per host | not verified | post-export pass or accept none |
| Cobblemon type gems | not reproducible with pockets (needs cave air next to deepslate, grows gem blocks in code) | - | - | post-export or hand placement |
| Mega Showdown keystone | place `megaroid.nbt` as a Custom Object (EXP-014 path) | - | - | - |

Dilution side effect: the host row writes plain `stone`/`deepslate` into pocket cells, which shows only
where the pocket lands in granite/diorite/andesite/tuff (estimated under 0.1 per 1,000 cells at f 1; not measured).

### B - exported Cobblemon block entities after load (RUN, PASS)
`exp017-objects-template` (copy of `exp014-obj-cobblemon-template`), booted with `--world`, `forceload add 0 0 255 255`
(area loaded after 11 s):
- `data get block` on every exported block entity: `cobblemon:berry` 766/766 and `cobblemon:habitat_block`
  969/969 returned block data with every exported key and string value, e.g.
  `{Berry: "cobblemon:payapa_berry", ..., GrowthPoints: [...], GrowthPointsSequence: "ED8A0135CFB46279", ...}` and
  `{SpawningStyle: "cobblemon:natural", PoolId: "cobblemon:berry_patch", DisplaySpecies: [...], RangeOfInfluence: 16, ...}`.
- `execute if block`: coba_berry 386/386, payapa_berry 380/380, habitat_block 969/969; exported properties matched 20/20 per name.
- After `save-all flush` + `stop`, re-read region: 256 chunks now DataVersion 3955, `minecraft:full`; berry 766
  and habitat 969 block entities at the same positions with data identical to the export (only `keepPacked`
  added); 765 jigsaw block entities identical; all 1,735 blocks keep their state.

`exp017-objects-schemv2` (copy of `exp014-obj-schem-v2`, Sponge v2):
- `data get block`: berry 103/103 with all keys. `execute if block`: apricorn_leaves 5,219/5,219,
  apricorn_log 416/416, red_apricorn 106/106, oran_berry 103/103.
- Saved region: 103/103 berry block entities identical; logs, red apricorns, berries identical state;
  every apricorn_leaves block gained `persistent=false` (the export had no `persistent` property; the
  block has one: `[persistent=false]` test passed, `[persistent=true]` failed); `distance` changed on 19
  leaves; 19 leaves are at `distance=7` after save.
- Random ticks: with `randomTickSpeed 1000` for about 1,000 game ticks, a control
  `oak_leaves[distance=7,persistent=false]` did not decay and wheat stayed at age 0, so force-loaded chunks
  without a player got no random ticks here. Leaf decay and berry growth: NOT VERIFIED.
- Side observations: after load, 2 modded ore blocks (`sun_stone_ore` at 252,43,255,
  `deepslate_leaf_stone_ore` at 71,-3,255) appeared inside the exported area, written by generation of the
  new neighbouring chunks into the border chunks, and the exported chunks gained `blending_data`. The server
  logged `key missing: DragonFight` for the WorldPainter level.dat and continued.

## Limitations
- Densities are for flat 256x256 test worlds with WorldPainter's default stone mix; real terrain with caves,
  aquifers and a varying surface changes the host volume. Pockets overwrite whatever is there (ores, water, lava).
- Target densities are a model plus a `/place feature` check; natural generation in real Cobbleverse terrain
  (biome checks at the attempt position, 3D cave biomes, air exposure) was not counted.
- Only two seeds for the normal-tier recommendation; seed-to-seed spread at frequency 1 is about ±25 %,
  and NOISE-mode exports are not reproducible (`MixedMaterial.java:468` uses `new Random()`).
- Pockets give a flat profile inside [min, max]; vanilla profiles are triangular (±15 % over 0..255 for
  Cobblemon stones, much steeper for galar).
- Nether, dripstone, sculk, packed ice, sandstone, terracotta recommendations were not exported.
- GUI not operated: brush intensity -> layer value and NOISE custom materials in the GUI are NOT VERIFIED.
- Task B used force-loaded chunks with no player: no random ticks, no entity/player interaction. Habitat
  spawning, berry harvest/growth and leaf decay are NOT VERIFIED. Only the two EXP-014 exports were loaded.

## Decision
Adapt.
1. Modded ores in WorldPainter: use Underground Pockets at frequency 1 with a NOISE custom material that
   dilutes the ore with its host (table above), two layers split at y=0, painted per biome. Undiluted
   pockets cannot get down to Cobblemon's rates. Scale 10-20 for size-1/size-3 ores, 100 for size-5 veins.
2. Ores whose host is not stone/deepslate go into the painted host material (dripstone, sculk, packed ice)
   or a post-export pass (sandstone, terracotta, type gems). Keystone ore comes with the megaroid object.
3. Custom Objects with Cobblemon block entities are safe to use: berry and habitat data survive the
   DataVersion 2860 -> 3955 upgrade unchanged. Apricorn leaves load as `persistent=false`; author tree
   objects so leaves are within distance 6 of a log (or test whether `persistent=true` survives export)
   before relying on them.

## Follow-up
- Player-present test in a disposable world: leaf decay of exported apricorn trees, berry growth/harvest,
  habitat-block spawns (needs a client).
- Check whether a Sponge v2 object with `apricorn_leaves[persistent=true]` keeps the property through export.
- Count natural Cobblemon ore generation in a pregenerated disposable Cobbleverse area to confirm the model per biome.
- Export the nether and host-material recommendations (dripstone, sculk, packed ice) and measure them.
- Terrain edges: plan a border of pre-generated or WorldPainter chunks so neighbouring worldgen does not
  write into the handcrafted region's edge chunks.
