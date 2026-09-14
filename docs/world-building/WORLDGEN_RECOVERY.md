# Worldgen recovery: ores, objects, apricorn trees, scatter script, and what is lost

**Status: Part 3 of the blocker work, for review.** Nothing is painted, placed or scripted yet.

**Evidence:**
- EXP-014: WorldPainter placement, headless.
- EXP-017: Underground Pockets calibration and in-game load of exported objects.
- EXP-019: generated apricorn trees sampled from a saved region, and villagers.
- The generation data read from the server's jars.

Earlier inventory: `WORLDGEN_FEATURES.md`.

## a. Modded ores with Underground Pockets

**Confirmed with test exports in WorldPainter 2.27.1 (EXP-017), not docs.** 46 calibration
exports and 4 verification exports were measured block by block.

**What vanilla actually places**, read from the jars and checked in game with `/place feature`:
- A size-3 `minecraft:ore` attempt places 0.46 blocks on average: 65% of attempts place
  nothing.
- Size 5 places about 3.
- `scattered_ore` size 1 places 0.5.

**Expected density per 1,000 host blocks** = 1000 × count ÷ rarity × blocks per attempt ×
p(y) ÷ 256.

**Pockets:** density ≈ 0.75 × frequency × 0.9^(8 − layer value) × ore share of the material.
Scale sets blob size, not density. Even at frequency 1, undiluted pockets are 3–9× too dense
for Cobblemon's rates. So every recommendation uses a **NOISE custom material that mixes the ore
with its host rock.**

| Ore (source) | Vanilla config | Target per 1,000 host | WorldPainter layer(s) | Measured |
| --- | --- | ---: | --- | --- |
| Evolution stones, normal tier (Cobblemon; 10 stones) | `ore` size 3, count 8 lower (trapezoid −64..192) + 8 upper (64..320); biome tag `has_ore/ore_<x>_stone_normal` (attached in code) | stone 0.093, deepslate 0.029 | stone layer: ore 1 : stone 5, f 1, scale 20, value 8, y 0..max; deepslate layer: ore 1 : deepslate 20, f 1, scale 20, y −64..−1 | 0.094 / 0.103 and 0.021 / 0.036 (2 seeds) |
| Evolution stones, rare tier | same, count 4 | 0.047 / 0.014 | ore 1 : stone 11, ore 1 : deepslate 41 | 0.057 / 0.0165 |
| Both tiers in one biome | | 0.14 / 0.043 | ore 1 : stone 3, ore 1 : deepslate 13 | computed, not exported |
| Galar particle, deepslate (Legendary Monuments) | `ore` size 5, count 10, trapezoid −24..56 | 0.92 | plain ore, f 1, scale 100, value 10, y −24..−1 | 0.84, blob 2.45 (vanilla 2.27) |
| Galar particle, stone | `ore` size 5, rarity 1/4, count 5, trapezoid −48..24 | 0.146 | ore 1 : stone 4, f 1, scale 100, y 0..24 | 0.174 |
| LumyMon steel (dripstone caves) | `scattered_ore` 1, count 1, −50..10, deepslate | 0.032 | ore 1 : deepslate 18, f 1, scale 10, y −50..−1 | 0.033 |
| Nether fire stone | `ore` 5, count 1, 10..245, netherrack | 0.052 | Nether is vanilla-generated, so no layer is needed; listed for completeness | not exported |
| Moon stone in dripstone (Cobblemon) | `ore` 3, count 256 in dripstone blocks | 2.0 per 1,000 dripstone | no pocket: paint the dripstone as a mixed material with 1 ore per 499 dripstone | not exported |
| LumyMon dragon (sculk, deep dark) / ice (packed ice) | `scattered_ore` 1, count 30 / 3 | 0.96 / 0.096 per host | mixed into the painted sculk (about 1:1040) / packed ice (about 1:10400) material | not exported |
| LumyMon electron (sandstone, desert) / rock (terracotta, badlands); terracotta sun stone | `scattered_ore` 1 / `ore` 3 into terracotta | 0.032 / 0.064 / 0.098 | **not reachable by pockets**: WorldPainter paints these hosts as the surface layer, which pockets never reach | scatter script (d) |
| Type gems (`deepslate_crystal_core`) | code feature, count 2, rarity 1/3, −64..0, needs cave air beside deepslate | — | not a pocket | scatter script (d) |
| Key Stone (Mega Showdown) | only inside the `megaroid` template | — | place the template as an object | — |

**Painting and caveats:**
- **Paint per biome.** Cobblemon pairs each stone with `has_ore` biome tags in code (read from
  bytecode in EXP-017). Use the biome filter from EXP-014.
- **Reproducibility.** A NOISE material uses an unseeded random, so two exports differ slightly.
  The world file is the record, not the export.
- **Dilution side effect.** Pocket cells that land in granite, diorite or andesite become plain
  stone. The estimate is under 0.1 per 1,000 cells.

## b. Custom Objects: .nbt, Sponge v2, or both?

**Both, in WorldPainter 2.27.1. Not Sponge v3.**

| Format | Blocks | Block entities (berries, habitat blocks) | After Minecraft loads it | Source |
| --- | --- | --- | --- | --- |
| Structure `.nbt` (what a structure block saves) | yes | kept: 126/126, 412/412, 41/41; Cobblemon template 766/766 berries, 969/969 habitat blocks | **identical after load and save** (EXP-017 B: chunk upgraded 2860 → 3955) | EXP-014, EXP-017 |
| Sponge v2 `.schem` | yes | kept, 103/103 | identical after load and save | EXP-014, EXP-017 |
| Sponge v3 `.schem` | yes | **data nested under `Data`**, which the game does not read | not tested | EXP-014 |
| MCEdit `.schematic` | numeric ids only, so modded blocks are impossible | — | — | WorldPainter source |

**Use structure `.nbt`.** It is what a structure block writes, so it needs no conversion tool.

**Four rules for objects:**
1. **Leaves.** Exported leaves load as `persistent=false`, and 19 of 5,219 test leaves ended at
   `distance=7` (decay range). Keep every leaf within 4 blocks of a log. Whether player-placed
   `persistent=true` survives the export is not verified: check it once with the first tree
   (EXP-017 follow-up).
2. **Jigsaw blocks** in Cobblemon's own templates are pasted as they are (765 in one berry
   patch). Replace them with their `final_state` before use; the scatter script's
   `flatten_jigsaws` job does it.
3. **Biome filter** limits where an object starts, not its footprint. Objects near a biome edge
   can spill a few blocks over.
4. **Growth and decay** need random ticks, which never ran without a player. Berry growth,
   apricorn ripening and leaf decay are not verified.

## c. The seven apricorn trees

### What Cobblemon generates (EXP-019, 16 trees, all colours)

**Every colour uses the same frame; only the fruit block and the fruit positions change:**

| Part | Generated |
| --- | --- |
| Trunk | 5 `apricorn_log[axis=y]`, one column |
| Canopy | 64–68 `apricorn_leaves` in a 5×5 footprint over 5 layers: a 3×3 ring (y+1), 5×5 with corners cut (y+2 and y+3), a 3×3 ring (y+4), a plus-shaped cap (y+5) |
| Fruit | 5–8 `cobblemon:<colour>_apricorn` on the outside of the y+2 and y+3 layers, `age=0` |
| Fruit rule | `facing` points at the leaf the fruit hangs from, with air behind it (118 of 118) |

```
 y+1 ....... ....... .####.. .##L#.. ..###.. ....... .......   rows z −3..3, columns x −3..3
 y+2 ....... ..###A. .#####. A##L##. .#####A ..###.. ...A...   L log, # leaves, A apricorn
 y+3 ....... .A###A. .#####. .##L##A .#####. ..###.. .......
 y+4 ....... ....... ..###.. ..#L#.. ..###.. ..##... .......
 y+5 ....... ....... ...#... ..###.. ...#... ....... .......
```

**The problem:** the same 5×5 lollipop repeated thousands of times is what reads as "one model
repeated". The seven designs below keep the frame's scale and fruit rule, so they still read
as apricorn trees and stay easy to harvest. Each colour gets its own silhouette and a place
that suits it.

### Rules for every design

1. **Blocks:** only `cobblemon:apricorn_log`, `cobblemon:apricorn_leaves` and that colour's
   `cobblemon:<colour>_apricorn`.
2. **Fruit:** hangs on the side of a leaf block, facing it, with air on the far side. At chest
   to head height where possible (y+2..y+4 above the ground the player stands on). 5–8 per tree.
   Build with mixed `age` 0–3 so some fruit already looks ripe; `age=3` is harvestable.
3. **Leaves:** every leaf within 4 steps of a log through leaves or logs. Place them by hand, so
   they are `persistent=true`.
4. **Footprint:** at most 7×7, height at most 9, so trees never block paths or sightlines.
5. **Base:** the lowest log sits in the bottom layer of the saved box; WorldPainter sets that
   layer on the surface. No dirt or grass in the object.
6. **Empty cells:** fill every empty cell in the saved box with `minecraft:structure_void`
   before saving, so the object never writes air into terrain or neighbouring trees.
7. **Rotation:** WorldPainter's random rotation rotates `facing` correctly (EXP-014 saw fruit
   facings rotated), so designs need not be symmetric.

### The designs

| # | Colour (what it crafts) | Silhouette | Trunk | Canopy | Fruit | Size (x·y·z) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Red** (Poké Ball, Great Ball) | **Orchard round**: the reference tree, closest to Cobblemon's own, so players learn "this is an apricorn tree" | 5 straight | the generated frame, with one or two extra leaves on a random side at y+1 and y+4 | 7, on the two wide layers, spread round the tree | 5·6·5 |
| 2 | **Blue** (Great, Dive, Heavy) | **Coastal lean**: shaped by wind | 5, stepping one block sideways at y+3 (logs stay `axis=y`) | 5×5 wide layers pushed one block toward the lean; the upwind side is two blocks thin | 6, under the long downwind side | 6·6·5 |
| 3 | **Yellow** (Ultra, Quick, Repeat) | **Tall upland**: narrow and high | 6 straight | a 3×3 ring at y+2 and y+3, one 5×5 corner-cut band at y+4, 3×3 at y+5, plus cap at y+6 | 5, all on the single wide band at y+4, the highest harvest | 5·7·5 |
| 4 | **Green** (Nest, Lure, Friend, Safari) | **Broad forest**: low and wide | 4 straight | 5×5 corner-cut at y+1..y+3 with ragged edges (3–5 leaves sticking out to a 6th column), 3×3 top at y+4 | 8, low at y+1 and y+2, easy picking | 6·5·6 |
| 5 | **Pink** (Love, Heal, Dream, Level) | **Blossom dome**: a rounded crown on branches | 4, with two one-block side branches at y+3 (`axis=x` and `axis=z` logs, opposite sides) | a dome over the branches: 5×5 corner-cut at y+3 and y+4, 3×3 at y+5, a single leaf at y+6 | 6, under the branch ends | 5·7·5 |
| 6 | **White** (Premier, Net, Fast, Dive) | **Snow cone**: a spruce-like cone | 6 straight | 5×5 corner-cut at y+2, 3×3 rings at y+3 and y+4, plus shapes at y+5 and y+6, top leaf at y+7 | 5, around the wide skirt at y+2 | 5·8·5 |
| 7 | **Black** (Heavy, Level, Moon, Dusk, Luxury) | **Gnarled fork**: split and flat-topped | 3 straight, then a fork: two diagonal log columns 2 high (y+3, y+4) | a flat 5×5 corner-cut plate at y+4 with gaps, 3×3 patches over each fork arm at y+5 | 6, under the plate's edge | 5·6·5 |

**Variation inside a colour, optional and cheap:** save a mirrored copy of any design with the
leaf edges changed (`<colour>_b`). Two objects per colour at equal weight, plus random rotation,
gives 8 visible arrangements per colour.

### Build, save and load

1. **Build world.** Use a disposable creative world. A copy of `cobblers-10240`'s spawn region
   works; the flat plot at 3548..3581, 3178..3211 has room. Build each tree on its own
   9×9 stone pad with 3 blocks of air between trees.
2. **Build the tree** by the rules above, in survival-style order: logs, then leaves, then fruit
   (fruit needs its leaf in place).
3. **Fill empty cells.** Structure void in every empty cell of the tree's box, e.g.
   `/fill x1 y1 z1 x2 y2 z2 minecraft:structure_void replace minecraft:air`, with the box from
   the pad's top surface up.
4. **Structure block:** `/give @s minecraft:structure_block`, then place it just outside the
   box's minimum corner.
   - Mode: **Save**.
   - Name: `cobblers:apricorn_red_a`, and so on.
   - Relative position and size: the tree's box, starting at the lowest log layer.
   - Include entities: off.
   - Press **Save**.
   - The file appears at `<world>/generated/cobblers/structures/apricorn_red_a.nbt`.
5. **Remove the voids** from the world if you keep building there:
   `/fill … minecraft:air replace minecraft:structure_void`.
6. **Keep the files** in the repo at `world/objects/apricorn/`. They are authored assets, a few
   KB each.
7. **WorldPainter:**
   - Add a *Custom Objects* layer named "Apricorn trees" and add the 7 (or 14) `.nbt` files.
   - Per object: random rotation on, mirroring on, offset 0.
   - One layer per region group (below), each painted with its biome filter.
8. **Check in game** on a disposable export before painting at scale:
   - leaves still `persistent=true` after load;
   - fruit harvestable at `age=3`;
   - no floating fruit after rotation.

GUI dialog details are not verified; EXP-014 drove WorldPainter by script.

### Density and biome per colour

**Vanilla** (read from the jars):
- One tree attempt per 8 chunks in eligible biomes, about 490 attempts per km².
- The colour is picked uniformly at random.
- Eligible biome sets:
  - dense: badlands, desert, forest, jungle, snowy forest, snowy taiga, taiga;
  - normal: hills, grassland, shrubland, sparse jungle;
  - sparse: tundra.
- The count multiplier for dense, normal and sparse is set in code and was not read.

**Proposal:**
- **Keep the eligible biomes.** Replace the uniform colour with a leaning per region, so the
  ball economy follows progression and regions trade.
- **Start at a quarter of vanilla attempts:** about 120 trees per km² of dense biome, 60 normal,
  15 sparse. Raise after playtesting; thinning a painted layer is easy.

| Colour | Leaning region(s) (share of that colour's trees) | Elsewhere | Why |
| --- | --- | --- | --- |
| Red | Eastern Downs, Lakeshore Vale, Windward Coast (70%) | everywhere eligible (30%) | Poké Balls from the first hour |
| Blue | Windward Coast, Southern Isles, Strand Flats (60%) | Lakeshore Vale | Great and Dive Balls near water; available before gym 2 (Misty) |
| Green | Lakeshore Vale, Stillwater Basin, Jungle Isle (60%) | forests | Nest, Lure, Friend, Safari: the catching specialists of the lowland routes |
| Pink | Stillwater Basin (cherry grove) (70%) | Lakeshore Vale | Love, Heal, Dream; fits the tea-house basin |
| Yellow | Rim Uplands, Leeward Plateau (70%) | Northern Range foothills | Ultra Balls higher and later, a reason to climb |
| White | Glacier Valley, Northern Isles (70%) | Northern Range | Premier, Net, Fast in the cold north |
| Black | Ember Highlands, Northern Range (70%) | the Rift edges | Heavy, Level, Moon, Dusk, Luxury in the harsh ground |

Exact weights are tuned when the encounter and progression plans exist. This table is only
the starting paint.

## d. The post-export scatter script (specification, not written)

**Scope:** everything WorldPainter cannot place with pockets or objects. It supersedes the
outline in `WORLDGEN_FEATURES.md` §4 where they differ.

### Rules, from the generation data

Rates are per chunk of eligible area. "Start" is the proposed first pass.

| Rule id | Block state written | Where | Surface predicate (from the placed feature) | Vanilla rate | Start |
| --- | --- | --- | --- | --- | --- |
| `mints` | `cobblemon:<red\|blue\|cyan\|pink\|green\|white>_mint[is_wild=true]`, colour uniform | planned highland regions (vanilla biome attachment is in code, not read) | on `#minecraft:dirt`, top of `MOTION_BLOCKING_NO_LEAVES`, y ≥ 70, air above; retry up to 64 times within ±8 x/z, ±1 y | chance per chunk by altitude: 70–79 1/88, 80–89 1/77, 90–99 1/55, 100–109 1/33, 110–119 1/22, ≥120 1/12 | 50% |
| `revival_herb` | `cobblemon:revival_herb[age=8,is_wild=true]` (drops the White, Mental, Mirror, Power herbs and Pep-Up Flower) | lush caves (`#cobblemon:is_lush`) in the underground biome plan | below the ocean-floor heightmap: a cave floor with air above, where the herb survives, or on moss carpet; patch of 5 tries, spread 4/1 | 2 patches per chunk | 25% |
| `medicinal_leek` | `cobblemon:medicinal_leek[age=2]` | rivers and lakes, not freezing, coast or ocean biomes | water surface: water below, air at the spot; patch of 20 tries, spread 4 | rarity 1/4, 2 patches | 50% |
| `big_root` | `cobblemon:big_root` | cave ceilings within 32 blocks of the surface | hangs under `#cobblemon:roots_spreadable` (dirt, stone), 2 air below; patch of 3 | rarity 1/2, 2 patches | 50% |
| `galarica_nuts` | `cobblemon:galarica_nut_bush`, age 3 (8 in 11), age 2 (3 in 11) | biome attachment in code, not read; propose the Leeward Plateau and Ember Highlands edges | world surface where the bush survives; patch of 20 tries, spread 5 | rarity 1/6 | 50% |
| `hearty_grains` | `cobblemon:hearty_grains[waterlogged=true,age=6,half=lower]` plus the upper half | plains and swamp shallows | at y 62, waterlogged, where it survives; patch of 20 tries, spread 3 | plains 1/7, swamp 1/8 | 50% |
| `max_mushroom` | `mega_showdown:max_mushroom[age=3]` | lush caves only (Mega Showdown's biome modifier) | cave air on a solid floor, y −63..60; patch of 6 tries, spread 3/2 | 10 patches per chunk | 10% |
| `host_ores` | `lumymon:electron_ore` in sandstone (desert, y 30–90), `lumymon:rock_ore` in terracotta (badlands, y 75–135), `cobblemon:terracotta_sun_stone_ore` in terracotta | the host blocks WorldPainter paints on the surface | replace host blocks at the EXP-017 densities | 0.032 / 0.064 / 0.098 per 1,000 host | 100% |
| `type_gems` | `cobblemon:deepslate_crystal_core` and its code-grown gem blocks | underground, y −64..0 | a deepslate block next to cave air; shape sampled first with `/place feature cobblemon:type_gems` | count 2, rarity 1/3 | 50% |
| `berry_groves` | berry bushes with `cobblemon:berry` block entities (`Berry`, `GrowthPoints`…, as in EXP-014) | sparse / normal / dense biomes | on `#cobblemon:berry_wild_soil` (dirt, sand, terracotta, snow) with replaceable above; retry within ±8/±1 | 1/70 sparse, 1/25 normal, 1/10 dense | 25% |
| `underwater_flora` | kelp, seagrass, coral, coral fans, sea pickles | the marine regions (`OCEAN.md` §4) | by zone and depth band | per zone table | per zone |
| `flatten_jigsaws` | each `minecraft:jigsaw` → its `final_state` | every placed Cobblemon template object | block entity field `final_state` | — | all |
| `leaf_persistence` | `apricorn_leaves[persistent=true]` | inside apricorn tree objects, if export drops the property | — | — | all |

**Before the script copies two code-built shapes,** sample them in a disposable world the way
EXP-019 sampled trees: type gems, and berry groves (which berries grow in which biome).
`underwater_flora` becomes a WorldPainter plants layer instead if that layer can place kelp,
seagrass and coral (not verified).

### Script behaviour

The contract from `WORLDGEN_FEATURES.md` §4 still stands:
- dry run by default;
- `--apply` needs a backup directory outside the world;
- refuses a running server;
- per-rule seeds, so runs are reproducible;
- a manifest of every placement;
- a final audit of counts per rule and region against the rules file.

**Additions:**
1. **Heightmaps are rebuilt from blocks** (`tools/world_heights.py` already does it): exported
   chunks carry empty heightmaps. Cave floors and ceilings come from a column scan for
   air-over-solid and solid-over-air.
2. **Biome comes from the chunk's stored biomes**, not from the plan, so later biome painting
   is respected.
3. **Region filters** come from `data/regions.json` and the marine regions. The underground
   biome plan decides which caves are lush.
4. **It writes blocks and block entities only.** It keeps each chunk's DataVersion; the game
   upgrades chunks on load, which EXP-017 verified keeps block entities.
5. **It needs an NBT writer.** `tools/level_dat.py` already writes typed NBT; region chunk
   writing would extend it.
6. **Run order:** after the final WorldPainter export, before the world is opened with a player.

## e. What is still unrecoverable after all of the above

**The crafting and evolution economy is fully recoverable:**
- evolution stones, relics and particles: pockets, host materials and the script;
- apricorns: objects;
- berries, mints, herbs, grains, nuts and max mushrooms: objects and the script;
- fossils, habitats and ruins: templates as objects, with block entities that survive;
- mega stones, the Key Stone, wishing stars and sparkling stones: the Mega Showdown templates,
  pasted with their crystal blocks and loot tables.

What is actually lost, or needs a replacement that changes how it works:

| Lost | Why | Consequence | Replacement |
| --- | --- | --- | --- |
| Explorer, treasure and cartographer maps pointing at overworld structures (vanilla chest maps, cartographer trades, LumyMon's Kanto cartographer, Cobbleverse `gym_map`) | `exploration_map` finds only structures with structure data (EXP-013 F) | the maps point nowhere, or the offer is dropped | no replacement item. Gym towns are found through flag-driven waystones and Xaero map markers (`NAVIGATION.md`); the broken map sources are removed (`STRUCTURE_DATA_FALLOUT.md` §3). Treasure maps have no replacement proposed |
| **LumyMon locator items and legendary radars** in the overworld | closed source; assumed to search structure data (not tested) | the items become useless for overworld targets | none. Their sources are removed so they do not act as false cues (`NAVIGATION.md`) |
| Eyes of ender finding a stronghold | no stronghold can exist in the exported world | End access has to be authored | the portal room after Giovanni (`DIMENSIONS_AND_BORDERS.md` §4) |
| "Find this structure" advancements (Mega Showdown, Repurposed Structures) | `location_check` on structure data | they cannot be earned at pasted sites | overriding them with position-based triggers is possible, not proposed. Whether any recipe depends on them is not checked |
| Mobs that spawn because a structure is there: guardians and elder guardians at monuments, pillagers at outposts, witches and their cats at swamp huts | vanilla structure spawn overrides read structure data | pasted monuments are empty: **no sponges** from elder guardians; no outpost pillagers (patrols still spawn); no hut witches | none proposed. Blazes, wither skeletons and piglins are unaffected (the Nether is vanilla) |
| Overworld structure-gated Pokémon spawns | EXP-013 D | none for availability: every species has or gets a home (`STRUCTURE_DATA_FALLOUT.md` §1) | re-homing and the town-ground gate |
| Cobbleverse's exact natural distribution: which biomes get mints, galarica, leeks and berry types, and the dense/normal/sparse apricorn counts | attached in code, not read (ore attachment was read from bytecode in EXP-017, so the rest is readable the same way) | only the Cobbleverse "feel" of where things grow | the region plan decides where things grow instead |
| Exactly reproducible ore exports | the NOISE material's unseeded random | two exports of the same world differ in ore positions | keep the exported world, or the script's seeded `host_ores` job, as the record |

Nothing in this table stops a species, an evolution item, a ball type, Mega Evolution,
Dynamax or Z-Moves from existing in the campaign.
