# Worldgen features: what the map lost, and how to put it back

**Status: inventory and method, for review.** In scope and ahead of scatter structures, per
the 2026-09-13 decision. Nothing is placed.

A WorldPainter export writes every chunk as already generated, so no feature runs inside
it: no ores, apricorn trees, berries, mints, fossils or wild waystones. The Nether and End
generate normally and keep their features, such as Nether fire-stone ore. Everything below
is about the overworld.

**Sources for this document:**
- `tools/worldgen_features.py`, which reads the server's jars and datapacks: output in
  `derived/features/features.json`, table in
  [`WORLDGEN_FEATURES_TABLE.md`](WORLDGEN_FEATURES_TABLE.md);
- the Mega Showdown 1.0.2 jar, read directly for its item chain;
- EXP-014 (WorldPainter placement, run headless) and EXP-013 (hand-placed structures).

## 1. Inventory

**278 non-vanilla placed features:**

| Source | Placed features | What they are |
| --- | ---: | --- |
| Repurposed Structures | 157 | Decoration inside its own structures (mineshaft supports and minecarts, NBT dungeons, vines, 7 plant patches). They come with RS structures and are not an economy |
| Cobblemon 1.8.0 | 103 | evolution-stone ores 42, fossil sites 23, habitats 15, plants and ingredients 10, apricorn trees 8, type gems and other 5 |
| Legendary Monuments | 6 | Galar particle ore (2) and 4 Distortion World decorations |
| Waystones | 6 | wild waystones (6 stone variants) |
| LumyMon | 5 | type ores: dragon, electron, ice, rock, steel |
| Mega Showdown | 1 | max mushroom |

**87 items are placed by those features.** For each one, the tool looked for any other
source in data: crafting recipes, non-block loot tables, datapack trades. Mob drops and
code-driven rewards are invisible to it.

| Other source in data | Items |
| --- | ---: |
| Loot tables only | 59 |
| Loot and crafting | 11 |
| Crafting only | 1 |
| **None: worldgen is the only source in data** | **16** |

**The 16 worldgen-only items:**
- Cobblemon mint plants in 6 colours. The mint *leaves* and seeds are also loot.
- Galarica nut bush. The nuts themselves are loot.
- Deepslate crystal core (type gems).
- Legendary Monuments Galar particle ore, stone and deepslate. The particle item is crafted.
- LumyMon's five relics: cryo, draco, metal, pebble, spark.
- Mega Showdown's max mushroom.

**Loot-only is not the same as available.** The loot tables that carry apricorns, stones and
mint leaves are mostly structure chests, trainer rewards (`rctmod:generic/*/nature`) and
raid dens (`cobblemonraiddens:raid/tier/*`). Those items exist only as long as the chests
are placed and the trainers and raids run.

### Mega Evolution, Dynamax, Z-Moves and Tera (read from the Mega Showdown jar)

| Item | Only source | So the map needs |
| --- | --- | --- |
| 83 mega stones (Abomasite, Absolite…) | crafted from `mega_showdown:mega_stone` plus a type item, iron and a diamond | raw mega stones |
| Raw `mega_stone` | the `mega_stone_crystal` block, found only in the **`mega_site`** template | mega sites, placed as structures. **Each site is mega stones in the economy** |
| Key Stone (Mega Bracelet) | `keystone_ore`, found only in the **`megaroid`** template | at least one megaroid |
| Mega Bracelet | crafted: Key Stone, white apricorns, diamond, iron | **apricorn trees** |
| Wishing star (Dynamax Band) | `wishing_star_crystal`, found only in the **`wishing_weald`** template | one wishing weald |
| Dynamax Band | crafted: wishing star, blue and pink apricorns, iron | apricorn trees |
| Max mushroom | worldgen feature only (y −63 to 60) | the scatter pass |
| Sparkling stone (Z-Ring) | archaeology loot, `archaeological_site_rare`, at the **`archaeological_site`** | one archaeological site with its suspicious blocks |
| Z-Ring | crafted: sparkling stone, white apricorns, iron | apricorn trees |
| Tera Orb | crafted from vanilla items | nothing |

**What follows from this:**
- **These four mechanics are structure-and-apricorn systems, not ore systems.** The
  templates keep their blocks when pasted (EXP-013), so the crystals and ores still drop.
- **Mega Showdown's "find" advancements will not fire at pasted sites.** They are
  `location_check` on structure data. Whether any recipe or unlock depends on them is not
  verified.
- **Apricorns sit underneath Poké Balls and three of the four mechanics.** Apricorn trees
  are the highest-priority feature.

## 2. Can WorldPainter place them? (EXP-014)

| Question | Result | Method to use |
| --- | --- | --- |
| Resources layer with a modded ore | **Fail.** The layer knows 14 vanilla resources; a modded ore throws a NullPointerException and exports nothing | not this |
| Underground Pockets layer with a modded ore | **Pass.** 202,287 fire-stone ore blocks at y0–70 and 173,365 deepslate ore blocks below y0 | ores, one layer per ore with stone and deepslate split by height. Pockets are noise blobs, not vein-shaped, and far denser than Cobblemon's feature until tuned |
| Custom Objects with apricorn trees and berry bushes | **Pass** with Sponge **v2** `.schem` or structure `.nbt`. Sponge v3 loses block-entity data | trees and bushes. Cobblemon ships **no apricorn tree schematic**: trees and berry groves are generated in code, so we author 7 tree objects |
| Per-biome density from a script | **Pass.** A biome filter limits the anchor column (a footprint can cross a biome edge), and density follows the source formula | set at paint time. Repainting biomes later does not move objects |
| Block entities (berries, habitat blocks) | **Pass.** Every `cobblemon:berry` and `cobblemon:habitat_block` entity kept its data | objects carrying block entities |
| Cobblemon's own templates as objects | **Partial.** A berry patch pasted its 765 jigsaw blocks as-is | flatten jigsaws first (script) |

**Not verified in game:**
- Whether exported chunks, stamped DataVersion 2860, load in 1.21.1 with Cobblemon's block
  entities intact.
- Berry growth, apricorn leaf decay, and habitat spawning.

**EXP-014's follow-up in-game load check comes before any painting at scale.**

## 3. Placement plan per feature family

| Family | Economy role | Method | Where (region plan) | Density target |
| --- | --- | --- | --- | --- |
| **Apricorn trees, 7 colours** | Poké Balls, Mega Bracelet, Z-Ring, Dynamax Band | WorldPainter Custom Objects (authored v2 trees), biome-filtered | forests and edges; one colour leaning per region so trade between regions matters | vanilla is 1 attempt per 8 chunks in eligible biomes. Start at roughly a quarter of that and raise it after playtest |
| **Evolution-stone ores**, 10 stones, stone and deepslate | evolutions; the stones also come from loot and 6 recipes each | Underground Pockets, one layer per stone, split at y0 | regional leaning: fire under the Ember Highlands, ice under the Glacier Valley, water under the coasts, moon in dripstone | tune pockets against Cobblemon's `count 8 / 8 / 4` placement per chunk |
| **LumyMon type ores** (relics, worldgen-only) | LumyMon items | Underground Pockets | dragon ore replaces sculk (y −60 to 0): the Giovanni and deep-dark regions; ice ore y65–125 in cold regions; the others by type | low, since relics are rewards |
| **Galar particle ore** (worldgen-only) | Legendary Monuments Galarian items | Underground Pockets | y −48 to 24 | low |
| **Type gems** (deepslate crystal core, worldgen-only) | Cobblemon gems | Underground Pockets below y0 | deep caves | low |
| **Berry groves and bushes** | berries (battle items, cooking, mulch) | Custom Objects built from `habitats/berry_patch*.nbt` with the jigsaws flattened, or authored v2 bushes | meadows, clearings, towns' edges | per region, set by the spawn and economy plan |
| **Mints**, 6 colours (worldgen-only) | nature mints | **scatter script**: a surface plant with `is_wild` state, y70+ with per-band rarity | highland meadows | vanilla rarity by altitude band |
| **Revival herb, medicinal leek, big root, galarica nuts, grains** | healing and cooking ingredients | scatter script: surface or under-surface predicates WorldPainter cannot express | by biome, per Cobblemon's placed features | vanilla |
| **Max mushroom** (worldgen-only) | Dynamax | scatter script: cave floors y −63 to 60 | underground biomes of the region plan | low |
| **Fossil sites**, 23 (sandy den, frozen spike, submerged impact…) | fossils for resurrection | Custom Objects from Cobblemon's `fossils/*.nbt`; suspicious blocks keep their loot tables | land and sea (`OCEAN.md`); the Mining Town underground | a curated count, not a density |
| **Habitats**, 15 underground and surface | spawn points (Habitat Blocks) | objects, counted as scatter placements (`STRUCTURE_DECISIONS.md`) | per region | in the 150 |
| **Wild waystones** | fast travel | **hand-placed**, not scattered: they shape travel | authored per route | authored |
| **Kelp, seagrass, coral, sea pickles** | Corsola and Cursola spawn blocks; the ocean's look | WorldPainter plants layer if it carries them (**not verified**), otherwise the scatter script | `OCEAN.md` section 4 | by zone |

## 4. The post-export scatter script (specification)

**Needed regardless of WorldPainter's success,** for four jobs:
- anything with a placement predicate WorldPainter cannot express (mints by altitude band,
  herbs under a heightmap, cave-floor mushrooms);
- flattening jigsaw blocks in Cobblemon templates;
- unwrapping Sponge v3 block entities;
- biome changes made after objects were painted.

It is also the full fallback if the in-game load check fails for WorldPainter objects. It
is specified here, not written: it needs an NBT **writer**, and `tools/nbt.py` is
read-only.

### `tools/scatter.py` (planned)

- **Input.**
  - `data/scatter_rules.json`, a new schema, `cobblers.scatter_rules/1`: one rule per
    placement kind.
  - A world copy. It never runs on the live world.
  - `data/regions.json`, including its `marine_regions`, for region filters.
  - The exported biomes, which are read back from the chunks, not from the plan.
- **Rule fields:**

| Field | Meaning |
| --- | --- |
| `id`, `kind` | `block` (single state), `object` (`.nbt` template with a palette, block entities, optional entities), `ore` (blob replace by host-rock tag) |
| `block` / `template` | block state with properties, or template path. Templates are flattened: jigsaw → `final_state`, structure voids skipped |
| `biomes`, `regions`, `exclude_regions` | where it may go. Biome is checked at the anchor, and also under the footprint when `footprint_biome: true` |
| `y`, `surface` | absolute Y range and a surface predicate: `top_solid`, `ocean_floor`, `cave_floor`, `beneath_surface` with a reach, or `replace` for ores |
| `on`, `above`, `light` | required block below (tag or list), required air or water above, and optional light bounds |
| `density` | placements per km² of eligible area, or `per_chunk` with a rarity like Minecraft's `rarity_filter` |
| `min_spacing`, `max_count` | spacing between placements of this rule and a hard cap |
| `block_entity` | NBT to write, for example a berry's `Berry` and `GrowthPoints`, or a suspicious block's `LootTable` |
| `seed` | per-rule seed, so the same rules on the same world give the same placements |

- **What it does:**
  1. Walk region files. Decode section palettes and packed states. Compute heightmaps from
     blocks, because EXP-013 found the exported chunks have empty `Heightmaps`.
  2. Collect eligible columns per rule. Sample them to density, with spacing and caps.
  3. Write blocks and block entities. Keep the chunk's DataVersion (the game upgrades it).
     Clear nothing else.
  4. Write a manifest, `derived/scatter/<run>.json`: every placement with rule, position,
     biome and region.
- **Safety:**
  - dry run by default;
  - `--apply` requires `--backup-dir` outside the world, like `region_trim.py`;
  - refuses a world with a running server (`session.lock` held).
- **Tests:** synthetic regions with the writer round-tripping through `tools/nbt.py`;
  density and spacing on a known surface; jigsaw flattening; biome filtering on a mixed
  chunk.
- **Audit:** `tools/dimension_audit.py`-style counts per rule and region, compared with
  targets in the rules file.

**It scatters features, never authored places.** Structures, towns, waystones and gyms
stay human-placed from candidates (the standing rule). Flora, ores and fossils are
distributions and can be generated.

## 5. Next checks

1. **EXP-014 follow-up:** load `exp014-obj-schem-v2` and the berry-patch export on a
   disposable copy. Harvest a berry, watch a habitat block spawn, check apricorn leaves do
   not decay.
2. Whether WorldPainter's plants layer can place kelp, seagrass, coral and sea pickles.
3. Tune Underground Pockets to one stone's vanilla yield per km² on a test tile.
4. Mega Showdown advancements: whether any recipe unlock needs a "find" advancement that a
   pasted site cannot grant.
