# EXP-013: Hand-placed structures: structure data, height, command blocks, gym maps

## Objective

Every structure on the WorldPainter map will be hand-placed. This experiment checks which placement
methods create structure data (a StructureStart and chunk References), and whether systems that
read that data see the builds. The systems are `/locate`, the `location_check` predicate, and the
Cobbleverse `gym_map` explorer map. Cobblemon structure spawns and RCT spawners were also in scope.
It also covers placement height on painted terrain and whether command blocks in a pasted
template run.
It runs EXP-A to EXP-F from `docs/research/notes/hand-placed-structures.md`.

## Success criteria

- EXP-A: after `save-all flush` and stop, the chunk NBT for each placement shows whether
  `structures.starts` / `structures.References` gained entries. `/locate` and
  `execute if predicate` are recorded at each site, next to natural positive controls.
- EXP-B: the landed Y of `/place structure` and `/place jigsaw` is measured against the painted top
  block, and failures are recorded.
- EXP-C: `cobbleverse:brock` command blocks are observed with `enable-command-block` false and then
  true: whether placement alone runs them, and whether the gym's own trigger runs them.
- EXP-D/E: run if a player-free method exists; otherwise NOT RUN, with what a client test needs.
- EXP-F: record the `gym_map` target next to the hand-placed gyms and outside the export.

## Dependencies

- Local server `cobblers-server`: Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0, the
  current mod set, and the Global Packs datapacks (COBBLEVERSE-DP-v31, -RCT-DP-v20, -Loot-DP-v11, …).
- `tools/nbt.py` (read-only NBT/region reader).
- Disposable predicate datapack: `datapack/exp013/` (a copy of what was installed in the test
  world). Predicates: `exp:inigloo`, `invillage`, `invillageplains`, `inbrock`, `inbrocktag`,
  `inmegasite`, `inmineshaft`, `inpyramid`. Each is `location_check` with `structures` set to the
  ID or tag.

## Implementation

**Disposable world.** The world was `cobblers-server/exp013-structures/`. It is left in place for
inspection and is not committed. It contains `level.dat` and the region files `r.3.3`, `r.3.4`,
`r.4.3`, `r.4.4` and `r.6.6` from `erosion-land-8k`. These are inside the export: Status full, no
structure data. The spawn is at 3400,3400 in r.6.6, copied so the spawn area was not regenerated.
It also has `r.-1.-1` from outside the export, which contains natural starts. Before boot 2, six
more exported regions (`r.0.7`, `r.1.1`, `r.6.3`, `r.5.7`, `r.7.5`, `r.3.9`) were copied over files
the server had written. That is the skip control in EXP-A/F. The live world `erosion-land-8k` was
never booted or edited.

**Launch.** `java -Xms4G -Xmx10G -jar fabric-server-launch.jar nogui --world exp013-structures`,
run from the server dir. The launcher accepted `--world`: the log shows
`Preparing level "exp013-structures"`, and `level-name` was not touched. The server was driven
over RCON with `runs/…/scripts/drive.py`, which uses the server's `rcon.py`. Both boots were
stopped with the RCON `stop` command, and java exited about 4 s later each time. No java process
or listener on 25565/25575 remained.

**server.properties.** A backup was taken first. For boot 2 only `enable-command-block=false→true`
changed. The server also rewrites the date comment on line 2 at every boot. The backup was then
copied back, and `cmp` plus sha256 `35fcf09d…ea10fd` show the result is byte-identical. A
before/after snapshot of the server dir, excluding `exp013-structures`, shows:
- no change under `erosion-land-8k`;
- runtime churn only: `logs/`, `.mixin.out/`, and 3 mod `.properties` files whose Java date
  comment was regenerated at the same byte size;
- mtime-only rewrites of about 40 configs, `ops.json`, `usercache.json` and the ban lists.

The backup file and a `__pycache__` created by importing `rcon.py` were deleted afterwards.

**Sites.** Blocks below are `x y z`; painted top block Y in brackets; each site force-loaded as
15×15 chunks.

| Site | Command | Painted top |
|---|---|---|
| A1 | `place structure minecraft:igloo 1672 107 1672` | 107 |
| A2 | `place structure minecraft:village_plains 1912 113 1672` | 112–115 |
| A3 | `place jigsaw minecraft:village/plains/town_centers minecraft:street 7 1672 97 1912` | 96–97 |
| A4 (control) | `place template minecraft:igloo/top 1912 99 1912` | 98 |
| B1 | `place structure minecraft:desert_pyramid 2184 106 2184` | 105 |
| C1 (boot 1, cmd off) | `place template cobbleverse:brock 2184 117 1672` | 116 |
| C2 (boot 2, cmd on) | `place template cobbleverse:brock 2424 114 1912` | 113 |
| C3 | `place structure cobbleverse:brock 1672 83 2184` | 82 |
| C4 | `place jigsaw cobbleverse:brock minecraft:bottom 1 1912 89 2424` (and `minecraft:empty`) | 88 |
| N1 natural | `mega_showdown:mega_site` start chunk (-13,-23), piece BB -208,-9,-368 → -196,4,-356 | — |
| N2 natural | `minecraft:mineshaft` start chunk (-27,-20) | — |

The painted tops were read from the source export with a section decoder. The exported chunks have
empty `Heightmaps`. At boot, `execute if block … minecraft:grass_block` confirmed them in-game.

## Test instructions

1. Stop the live server. Copy `level.dat` and the region files listed above into a new world
   folder. Put `datapack/exp013` in `<world>/datapacks/`.
2. Boot with `--world <folder>`. Run `gamerule doDaylightCycle false`,
   `gamerule doMobSpawning false`, `gamerule randomTickSpeed 0` and `difficulty peaceful` (the
   difficulty change is stored in the disposable world's level.dat only).
3. `forceload add` 15×15 chunks around each site. Check with `execute if loaded`.
4. Run the command files in `runs/20260913-122700/commands/` in this order: `cmdsA.txt` (after the
   four A placements), `cmdsC1.txt`, `cmdsC3.txt`, `cmdsBiome.txt`, `cmdsF1.txt`. Then
   `save-all flush` and `stop`.
5. Inspect with `scripts/inspect_sites.py` (block diff against the original export, starts,
   References) and `scripts/heights.py` (placed Y minus painted top per block type).
6. Set `enable-command-block=true`. Copy the regions that held the boot-1 locate and map answers
   from the export. Boot, then run `cmdsL2.txt` and `cmdsC2.txt`. Stop. Restore server.properties.

`say` output does not come back over RCON. Use a bare `execute … if predicate …`, which replies
"Test passed/failed".

## Results

Full command/response log: `runs/20260913-122700/rcon_log.jsonl` (198 records). Also in that folder:
console logs, inspection JSON, scripts and the server-dir diff. `runs/*/` is gitignored, so the
key raw observations are quoted here and in `results.json`.

| Exp | Run | Outcome | What it showed |
|---|---|---|---|
| EXP-A | RUN | PASS (answered) | None of `/place structure`, `/place jigsaw` or `/place template` wrote structure data. Every placement chunk saved as `structures: {References: {}, starts: {}}`, and all 225×7 site chunks had no starts and no References. `location_check` failed at all 11 in-structure points (igloo ×3, village ×5, brock ×3). `/locate` never returned a placed build. Natural controls passed: predicate `Test passed`, locate 8 and 10 blocks away, starts plus 16 and 9 References chunks. |
| EXP-B | RUN | FAIL for projected jigsaws | `village_plains`: bell at y64 and houses buried 31–54 blocks under the painted surface; streets followed the surface (1617/1808 path blocks at dy 0). `/place structure cobbleverse:brock`: snapped to the chunk origin (1664, 62, 2176), 20 blocks under the surface at 82. Igloo: floor at the painted top (y107). `/place jigsaw` at an explicit y97: center at y97, streets on the surface, **no houses**. `desert_pyramid`: `Failed to place structure` (cause not verified). |
| EXP-C | RUN | PASS (answered) | Placement never ran the Brock command blocks, with `enable-command-block` false or true (checked at 0 s and 5 s). The chain starts from a **light weighted pressure plate**; an item entity pressed it. With false: the command block got `powered:1b` and a new `LastExecution` but did nothing. With true: plate removed, command blocks turned to dirt, villager "Kanto Map Guide" summoned. C1 (placed while off) and the structure-placed C3 also ran once triggered in boot 2. |
| EXP-D | NOT RUN | — | `/checkspawn` exists but rejects RCON use (`Incorrect argument for command`). A player is needed. |
| EXP-E | NOT RUN (spawn) | block data PASS | All three pasted gyms kept `rctmod:trainer_spawner {TrainerIds: ["kanto_brock"]}`. The template's `OwnerUUID` is absent after placement. Spawning needs a player (`/rctmod trainer spawn_for [<target>]`). |
| EXP-F | RUN (loot) | FAIL for hand-placed | 6 `gym_map` rolls (3 per boot, 2 next to hand-placed gyms and 1 outside) all returned `filled_map` with `target_point` at unrelated places, never at a hand-placed gym. LumyMon trades and radars: NOT RUN. |

### EXP-A raw excerpts

```
> place structure minecraft:igloo 1672 107 1672
  Generated structure "minecraft:igloo" at 1672, 107, 1672
> execute positioned 1667 108 1670 if predicate exp:inigloo          (inside the igloo's blocks)
  Test failed
> execute positioned 1667 108 1670 run locate structure minecraft:igloo
  The nearest minecraft:igloo is at [288, ~, 3648] (2411 blocks away)
> execute positioned 1911 64 1661 if predicate exp:invillage         (on the placed bell)
  Test failed
> execute positioned 1670 64 2188 if predicate exp:inbrock           (structure-placed gym)
  Test failed
> execute positioned -202 0 -362 if predicate exp:inmegasite         (natural)
  Test passed
> execute positioned -202 0 -362 run locate structure mega_showdown:mega_site
  The nearest mega_showdown:mega_site is at [-208, ~, -368] (8 blocks away)
> execute positioned -426 -6 -312 if predicate exp:inmineshaft       (natural)
  Test passed
```

NBT after stop (`inspect_final.json`). Placement chunks (104,104), (119,104), (104,119), (119,119),
(136,104), (104,136) and (105,137) are all `Status minecraft:full` with
`structures={'References': {}, 'starts': {}}`. Whole-region scans of exp013 r.3.3, r.3.4, r.4.3 and
r.4.4 found 0 chunks with starts and 0 with References. Natural control: mega_site chunk (-13,-23)
went from Status `structure_starts` to full, and 16 neighbouring chunks hold References to it.

**Locate skip control.** Boot-1 answers all pointed into regions missing from the disposable world.
In boot 2, with exported copies (full, no starts) in those regions, the same queries moved:

| Query | Boot 1 | Boot 2 |
|---|---|---|
| igloo, from A1 | [288, ~, 3648] | [640, ~, 3616] |
| `#village`, from A2 | [848, ~, 816] | [1136, ~, 1936] |
| brock, from C1 | [3472, ~, 1936] | [144, ~, 1536] |
| mega_site, from N1 | [-208, ~, -368] | unchanged |

### EXP-B raw excerpts

Placed Y minus painted top per block type (`heightsA.json`):

- A2 village_plains
  - cobblestone: y59–81, dy −31…−54
  - oak_planks: y63–77
  - bell: y64 (dy −49)
  - dirt_path: 1617 blocks at dy 0, 94 at +1, 57 at −51/−52
- A3 jigsaw
  - dirt_path: 1684 at dy 0
  - cobblestone: dy −4…+4
  - houses: no house blocks anywhere nearby
- A1 igloo structure: snow_block dy 0…+4
- A4 igloo template: dy +1…+5 (placed one block above the top block, as commanded)
- C3 brock structure: block changes y62–78 at x1664–1690 z2176–2199; 8304 terrain blocks replaced by the template's air

`/place structure` ignored the seed biome for igloo and village. The seed biome comes from
`locate biome`; the placed chunk's biome comes from `execute if biome`:
`#has_structure/igloo` nearest 439 blocks away, but the igloo was placed; the painted biome at all
sites is `minecraft:plains`. The pyramid failure therefore needs another explanation, not
investigated.

### EXP-C raw excerpts

```
[boot 1, enable-command-block=false]
> place template cobbleverse:brock 2184 117 1672
  Loaded template "cobbleverse:brock" at 2184, 117, 1672
> execute if entity @e[type=minecraft:villager,name="Kanto Map Guide"]
  Test failed
> summon minecraft:item 2197.5 119.1 1690.5 {Item:{id:"minecraft:cobblestone",count:1},PickupDelay:32767}
> data get block 2197 117 1690
  {... powered: 1b, auto: 0b, Command: <template text omitted>, SuccessCount: 0, LastExecution: 1948336L ...}
> execute if block 2197 119 1690 minecraft:air
  Test failed                                   (plate still there, nothing ran)
[boot 2, enable-command-block=true]
> place template cobbleverse:brock 2424 114 1912
> execute if entity @e[type=minecraft:villager,name="Kanto Map Guide"]     (0 s and 5 s later)
  Test failed
> summon minecraft:item 2437.5 116.1 1930.5 {...}
> execute if block 2437 116 1930 minecraft:air
  Test passed
> execute if block 2446 114 1927 minecraft:dirt
  Test passed
> execute if entity @e[type=minecraft:villager,name="Kanto Map Guide"]
  Test passed, count: 1          Pos [2447.5d, 116.5625d, 1928.5d]
```

How the template works, read from `brock.nbt`:
1. The plate at [13,2,18] powers the command block at [13,0,18], which removes the plate.
2. The chain block at [13,0,17] fills `bamboo_mosaic` with `redstone_block`.
3. That powers the impulse block at [17,0,15], and chain blocks [18–23,0,15] summon the villager
   and replace the command blocks with dirt.

The template's own `redstone_block` at [6,0,12] only powers the trainer spawner above it.

### EXP-F raw excerpts

`gym_map.json` uses vanilla `minecraft:exploration_map` with `destination`
`cobbleverse:kanto_brock_gym` (tag = `[cobbleverse:brock]`), `search_radius` 30 and the default
`skip_existing_chunks`. LumyMon's `kanto_cartographer.json` trade, in the same zip, uses the same
function with radius 50.

| Boot | Where | Map target (x, z) |
|---|---|---|
| 1 | C1 template gym | 2816, 3840 |
| 1 | C3 structure gym | 3888, 2624 |
| 1 | outside, -202,-362 | 1952, 4656 |
| 2 | C1 | 2768, 4624 |
| 2 | C3 | 2032, 5408 |
| 2 | outside | 2672, 5168 |

Before boot 2, the boot-1 target regions held small 12 KB files the server had written during the
search, and they were overwritten with exported copies. The copied outside region r.-1.-1 contains
no natural `cobbleverse:brock` start, so no map could point at a natural gym there.

## Limitations

- **Headless.** No player joined, so Cobblemon spawns (EXP-D), RCT spawns (EXP-E), LumyMon trades
  and radars were not tested, and nothing was checked visually.
- **Partial world.** Only 12 region files existed, so most of the 8k export was ungenerated in the
  disposable world. Locate and map answers landed in those gaps. In the full live world, every
  chunk inside the export exists; answers there are NOT VERIFIED. The skip control only shows that
  the answers moved once exported regions were present.
- **Map move is confounded.** Explorer maps skip structures an earlier map already found. The EXP-F
  target move is consistent with skipping generated no-start chunks but does not prove it on its
  own. `/locate` does not use that rule, and its answers moved too.
- **Not tested:**
  - the structure block Load button, WorldEdit, Axiom;
  - an `auto:1` impulse or repeating command block in a template;
  - rotation or mirroring;
  - multiplayer.
- **No source read.** The vanilla `PlaceCommand` source was not read. The "no structure data"
  result is observed on disk, not explained from code.
- **Unexplained:** why the desert pyramid failed.

## Decision

**Hand-placement cannot rely on structure data.** On this server, every in-game placement method
we tested left the chunks with no start and no References. Anything keyed to structure IDs will
therefore not see our builds. That covers `/locate`, `location_check` / advancements, the
Cobbleverse `gym_map`, LumyMon's exploration-map trades (same function, not run), and very likely
Cobblemon `structures` spawn conditions (not run).

Implications:
- Gym maps, cartographer trades and legendary radars that target structure tags need a
  replacement. The dataset already uses a plain `exploration_map`, so a fixed-position alternative
  (a hand-made map item, or waypoints) must be designed; this is not a config switch.
- Structure-gated spawns and predicates must be replaced with non-structure conditions: position,
  biome, Habitat Block, or a function/scoreboard region check.
- Use `/place template` (or a paste tool) at an explicit Y. Do not use `/place structure` or
  `/place jigsaw` on painted terrain: heightmap-projected jigsaws put rigid pieces at seed-terrain
  height, 20–54 blocks under our surface, and `/place jigsaw` dropped the village houses.
- Pasted Cobbleverse gyms keep their RCT spawner IDs. Their command blocks stay dormant until the
  light weighted pressure plate is pressed, and only run with `enable-command-block=true`. Any
  entity can press that plate, including dropped items and mobs.

No ADR written; this feeds the structure-placement ADR when one is drafted.

## Follow-up

- Client test (one player): EXP-D `/checkspawn` with a `structures: ["minecraft:igloo"]` test
  spawn at A1/A4 and at a natural igloo; EXP-E Brock spawner spawns; LumyMon Brock-map trade and
  legendary radar next to a pasted gym.
- Decide the replacement for structure-tag maps and spawns (content-architect ADR).
- Optional: check `/locate` and `gym_map` against a complete copy of the export (all regions) to
  confirm where answers go when every export chunk exists.
