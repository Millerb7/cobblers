# EXP-019: What Cobblemon's apricorn trees look like, and whether villagers work in a built town

## Objective
Two small questions that block the worldgen and town specs.
**A.** Cobblemon ships no apricorn tree template; the tree is built in code. What shape does it
actually generate, so authored tree objects can be based on it rather than guessed?
**B.** Do villagers take jobs, roll trades and breed around beds, a bell and job-site blocks placed
by command, with no village structure data?

## Success criteria
- A: at least two generated trees per colour captured from a saved region; trunk, canopy layers,
  apricorn count, apricorn attachment rule and leaf properties described from the blocks.
- B: within about 5 minutes of summoning unemployed villagers next to job sites, beds and a bell:
  each villager holds a profession, a rolled `Offers` list, `home` / `job_site` / `meeting_point`
  memories, and at least one baby is born.

## Dependencies
Server `cobblers-server` (Fabric 1.21.1, Cobblemon 1.8.0, full mod set). A disposable world
`exp019-trees-villagers`: `level.dat` plus region, entities and poi `r.6.6.mca` copied from
`cobblers-10240` (flat plains near spawn). `tools/nbt.py`, `tools/world_heights.py`.

## Implementation
- `scripts/exp019_place.py`: over RCON, force-loads two areas, runs
  `place feature cobblemon:<colour>_apricorn_tree` on a 4×4 grid (x 3548..3581, z 3178..3211,
  y 130, spacing 11, colours cycling through all seven), paves a 23×21 stone-brick plot at
  3330..3352, 118, 3325..3345, and places 4 beds, a bell, a lectern, a composter and a smithing table,
  then summons 3 villagers with `profession:minecraft:none` and 6 bread each (tag `exp019`).
- `scripts/exp019_trees_scan.py`: reads the saved region and describes each tree.
- Game rules during the run: daylight and mob and Pokémon spawning off, time 1000.

## Test instructions
```
copy level.dat and region/entities/poi r.6.6.mca from cobblers-10240 into <server>/exp019-trees-villagers
java -Xms4G -Xmx10G -jar fabric-server-launch.jar nogui --world exp019-trees-villagers
python scripts/exp019_place.py
# after 2-5 minutes, over RCON:
execute if entity @e[type=villager,tag=exp019,nbt={VillagerData:{profession:"minecraft:librarian"}}]
data get entity @e[type=villager,tag=exp019,limit=1,nbt={VillagerData:{profession:"minecraft:librarian"}}] Offers.Recipes
data get entity @e[type=villager,tag=!exp019,limit=1] Age
save-all flush ; stop
python scripts/exp019_trees_scan.py
```

## Results

### A: generated apricorn trees (RUN, 16 trees, all seven colours)
All 16 trees have the same frame; only the colour and the fruit positions differ (`trees_report.json`).

| Part | Observed |
| --- | --- |
| Trunk | 5 `apricorn_log[axis=y]` in one column (y+0..y+4) |
| Canopy | 64-68 `apricorn_leaves` in a 5×5 footprint, y+1..y+5: y+1 about 10 (a 3×3 ring with a few extras), y+2 and y+3 20 each (5×5 minus the trunk and the four corners), y+4 10-13 (3×3 ring with extras), y+5 a plus-shaped cap of 5 |
| Fruit | 5-8 `<colour>_apricorn` per tree, all at y+2 or y+3, hanging on the outside of the two widest layers, `age=0` |
| Attachment | 118 of 118 apricorns have a leaf in their `facing` direction and air behind: the fruit faces the leaf it hangs from |
| Leaves | `persistent=false`, `distance` 1-3, `waterlogged=false` |

Slices of the first tree (rows are z −3..3, columns x −3..3; L log, # leaves, A apricorn):
```
 y+1 ....... ....... .####.. .##L#.. ..###.. ....... .......
 y+2 ....... ..###A. .#####. A##L##. .#####A ..###.. ...A...
 y+3 ....... .A###A. .#####. .##L##A .#####. ..###.. .......
 y+4 ....... ....... ..###.. ..#L#.. ..###.. ..##... .......
 y+5 ....... ....... ...#... ..###.. ...#... ....... .......
```

### B: villagers in a built plot (RUN, headless, force-loaded chunks)
Checked about 2-3 minutes after summoning:
- All three villagers had professions: librarian, farmer, toolsmith, one per job-site block.
- Rolled trades existed. Librarian: 9 emeralds → bookshelf, and 21 emeralds + book →
  Depth Strider II. Farmer: 20 wheat → 1 emerald.
- The toolsmith's brain held `home` (a bed at 3338, 119, 3327), `job_site` (the smithing table)
  and `meeting_point` (the bell).
- A baby villager (`Age -23299`) had been born next to the beds.
- No iron golem spawned.

## Limitations
- Headless: no player, so raids (Bad Omen/Raid Omen), iron golem panic spawning, trading itself, and
  the RCT trainer-association NPC near beds and a bell were not tested.
- One short run with three villagers and one plot.
- The trees are `/place feature` output, not natural generation; natural generation adds the biome
  and sapling-survival checks and, for dense/normal/sparse biomes, a count set in code that was not read.
- Leaf decay and apricorn growth need random ticks, which force-loaded chunks without a player did not
  get in EXP-017.

## Decision
- A: authored tree objects start from this frame (trunk 5, 5×5 corner-cut canopy over 5 layers, 5-8
  apricorns on the widest layers facing their leaf) and vary from it. Spec in
  `docs/world-building/WORLDGEN_RECOVERY.md`.
- B: villager life in built towns needs only blocks: beds, a bell, job sites and placed villagers.
  Professions, rolled trades and breeding work without any village structure. Used in
  `docs/world-building/STRUCTURE_DATA_FALLOUT.md` section 4.

## Follow-up
- With a player: a raid in a built town, iron golem spawning, and the RCT association NPC.
- Sample `cobblemon:type_gems` and `cobblemon:berry_groves` with `/place feature` the same way, so the
  scatter script copies their real shapes.
