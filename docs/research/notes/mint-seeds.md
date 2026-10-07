# Mint seeds: growth, yield, ids, sources (U6 SEEDS, 2026-10-07)

**Question** (`docs/mechanics/MINECRAFT_PLAY_LOOPS.md:282`, `docs/mechanics/DESIGN_QUESTIONS_2026-10-09.md:261-265`):
do Cobblemon's mint seeds grow and yield mint leaves in survival, what are the ids, how are they planted, and
does any natural source of the seeds exist? Answered for **Cobblemon 1.8.0** (the server's version).

**How it was read.** This research agent had no shell, so the local jar
(`C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar`, present,
found by glob) was **not opened**. Source was read instead from the Cobblemon GitLab repository **at the `1.8.0` ref**
(`https://gitlab.com/cable-mc/cobblemon/-/raw/1.8.0/...`), through a fetch tool that passes pages through a summariser.
The JSON and Kotlin below are what that tool returned as verbatim; a jar read should re-confirm the loot table before
prices are set on it (experiment E1). The `main` branch was also fetched and has diverged (it registers mint leaves
as `*_MINT_LEAF_LITTER` block items); `main` is **not** evidence for 1.8.0 and is not cited for any fact here.

## Answer

**Yes, they grow and yield.** A planted seed is an ordinary Cobblemon crop with 8 ages (0-7). At age 7, breaking it
drops 1-3 leaves and 1 seed or more, so a patch keeps itself going and grows. VERIFIED from the 1.8.0 source below;
**not run in game** (E2).

## Verified

### Ids (Cobblemon 1.8.0)

| Colour | Seed item (plants the crop) | Crop block | Leaf item |
|---|---|---|---|
| red | `cobblemon:red_mint_seeds` | `cobblemon:red_mint` | `cobblemon:red_mint_leaf` |
| blue | `cobblemon:blue_mint_seeds` | `cobblemon:blue_mint` | `cobblemon:blue_mint_leaf` |
| cyan | `cobblemon:cyan_mint_seeds` | `cobblemon:cyan_mint` | `cobblemon:cyan_mint_leaf` |
| pink | `cobblemon:pink_mint_seeds` | `cobblemon:pink_mint` | `cobblemon:pink_mint_leaf` |
| green | `cobblemon:green_mint_seeds` | `cobblemon:green_mint` | `cobblemon:green_mint_leaf` |
| white | `cobblemon:white_mint_seeds` | `cobblemon:white_mint` | `cobblemon:white_mint_leaf` |

- Seeds: `mintSeed(name, block)` builds `"${name}_mint_seeds"` with `this.blockItem(finalName, mintBlock)`, so the seed
  item **places the crop block** (compost chance 0.30). Leaves: `mintLeaf` builds `"${name}_mint_leaf"` as a
  `MintLeafItem` (compost 0.50). Source: `.../1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/CobblemonItems.kt`.
  VERIFIED (1.8.0 ref).
- The same twelve item ids are in the base pack's REI config (`base-pack/cobbleverse/config/roughlyenoughitems/collapsible.json5:840-852`)
  and in the jar-derived table `docs/world-building/WORLDGEN_FEATURES_TABLE.md:10-15,38-40,55-57,61-63,78-80`. VERIFIED (local).
- Block tag `cobblemon:mints` = the six crop blocks above (`.../1.8.0/.../data/cobblemon/tags/block/mints.json`). VERIFIED.

### Planting and growth (`.../1.8.0/common/src/main/kotlin/com/cobblemon/mod/common/block/MintBlock.kt`)

- `class MintBlock(...) : CropBlock(settings), BonemealableBlock`; `AGE = CropBlock.AGE`, `MATURE_AGE = MAX_AGE`; the
  shape table has entries for ages 0-7. VERIFIED.
- **Soil.** `canSurvive`: `(world.getRawBrightness(pos, 0) >= 8 || world.canSeeSky(pos)) && ((this.isWild(state) &&
  floor.is(BlockTags.DIRT)) || this.mayPlaceOn(floor, world, pos))`. The file has **no `mayPlaceOn` override**, so a
  player-planted (non-wild) mint uses `CropBlock`'s, which is farmland. VERIFIED for the code; that the vanilla
  `CropBlock` soil is farmland is VERIFIED from the Minecraft wiki ("Wheat seeds can be placed on farmland",
  https://minecraft.wiki/w/Wheat_Seeds, current Java). Only **wild** mints (`is_wild=true`, worldgen) sit on any
  `#minecraft:dirt`.
- **Light.** To place/survive: raw brightness >= 8 **or** sky view. To grow: `randomTick` returns early if
  `getRawBrightness(pos, 0) < 9`, so it needs 9+. VERIFIED.
- **Growth rate.** `randomTick` grows one age only when `random.nextInt(8) == 0`, a flat 1 in 8 per random tick. It
  replaces vanilla's moisture-based chance, so hydrated farmland does **not** speed it up. VERIFIED.
- **Bone meal.** `getBonemealAgeIncrease(world) = 1`: one age per bone meal (vanilla crops get 2-5), so **7 bone meal
  take a seed to maturity**. VERIFIED.
- **No biome requirement.** Nothing in `MintBlock` reads the biome. Altitude and dirt matter only to worldgen (below).
  VERIFIED (absence in the file).
- **Farmland is kept.** `data/minecraft/tags/block/maintains_farmland.json` (1.8.0) = `#cobblemon:berries`,
  `#cobblemon:crops`. `cobblemon:crops` includes `#cobblemon:mints`. So mints keep their farmland from drying back to
  dirt; trampling can still break it. VERIFIED.

### Yield (`.../1.8.0/common/src/main/resources/data/cobblemon/loot_table/blocks/red_mint.json`)

The loot table has an `explosion_decay` function and these pools:
1. 1 seed, **always**, at any age. Breaking an unripe crop returns its seed.
2. A 12.5% chance (`random_chance` 0.125) of +1 seed, age 7 only.
3. With Fortune (any level), a 25% chance of +1 seed, age 7 only.
4. With Fortune II or higher, a 50% chance of +1 seed, age 7 only.
5. 1 leaf at age 7.
6. A 50% chance of 2 more leaf rolls at age 7.

So a mature mint with no Fortune gives **1-3 leaves** and **1.125 seeds** on average. VERIFIED (1.8.0 ref; red
fetched, white fetched from `main` only).

- **White mint is the colour source.** On `main`, `white_mint.json` pool 2 is a weighted group: white 2 and each
  other colour 1, out of 7. So a mature white mint has a 12.5% x 5/7 = about 8.9% chance to drop a seed of another
  colour, about 1.8% for any one colour. The wiki says the same: "White Mint crops have an additional chance to drop 1
  other mint seed color" (https://wiki.cobblemon.com/index.php/Mint_Seed, edited 2026-01-12). ASSUMED for 1.8.0, since
  the 1.8.0 copy of the white table was not fetched (E1).
- **The wiki contradicts itself.** The same page says harvesting gives "1-2 of the respective mint seed" and also "1
  ... with a 1 in 8 chance that it will drop 2". The loot table agrees with the second. The wiki page has no version
  label and is not used for any fact here except the white-mint line.

### Natural sources

- **Worldgen.** `worldgen/placed_feature/mints.json` (1.8.0) places a wild mint (`is_wild: true`, picked at random
  from the six colours by `configured_feature/mints.json`) only at altitude >= 70 and only on `#minecraft:dirt`. Its
  rarity filters get rarer with height: 88 at y70-79, 77, 55, 33, 22, and 12 at y120+. VERIFIED. Harvesting a wild
  mint gives seeds through the loot table above.
  - **Our world has none.** The WorldPainter map makes no new chunks inside the border, and we place no mints
    (`docs/mechanics/SPAWN_PHILOSOPHY.md:274`, `docs/world-building/WORLDGEN_FEATURES.md:7,43`). VERIFIED (local).
- **Loot tables.** Every seed id appears in **exactly 2 loot tables** across the snapshot's jars
  (`docs/world-building/WORLDGEN_FEATURES_TABLE.md:12,15,40,57,63,80`, generated by `tools/worldgen_features.py`). For
  the five non-white colours, those two are the colour's own block table and the white-mint block table, so they have
  **no chest, fishing or trainer route**. That is ASSUMED, because it rests on the white table read from `main`. Which
  second table holds `white_mint_seeds` is UNKNOWN (E1).
- **Earlier sweeps agree there is no route** (relayed, not re-measured here). `docs/research/OBTAINABILITY_VANILLA_COBBLEMON.md:91-92`
  says all 33 mint items reach players only through tier-F (unverified trainer) loot, and the six Power items need a
  white mint leaf. Its sweep included the species drop tables, vanilla and Cobblemon fishing, and Pasture Loot (tier
  B, `:61,67-70`). So no Pokemon drop and no fishing loot is known to carry a mint seed. `base-pack/cobbleverse/config/PastureLoot.json`
  does not mention mints at all (grep, 0 matches). VERIFIED.
- **Nothing of ours overrides it.** A grep of the repo for `mint_seed` finds only docs and the base-pack REI config:
  nothing in `data/` or `modpack/`. VERIFIED (local, 2026-10-07).

### Berries, for the rare-berry seeds the loop wants

- There is **no separate berry seed item**. `open class BerryItem(private val berryBlock: BerryBlock) :
  ItemNameBlockItem(berryBlock, Properties())`, so **the berry itself is what you plant**
  (`.../1.8.0/.../item/berry/BerryItem.kt`). A barter for a rare berry "seed" therefore sells the berry item, e.g.
  `cobblemon:<name>_berry`. VERIFIED for the class. That the id follows this pattern for every berry is ASSUMED.
- `BerryBlock` (1.8.0) is reported as `BonemealableBlock, Mulchable`, with `MATURE_AGE = 3` and `FRUIT_AGE = 5`, a
  survival check against a berry-soil tag (wild ones also accept a wild-soil tag), bone meal that succeeds at the
  berry's own `boneMealChance`, and a 125/1000 base mutation chance (x4 with Surprise Mulch). The fetch tool
  **summarised** this rather than quoting it, so it is ASSUMED until quoted. The exact soil tag ids are UNKNOWN.

## Assumed

- **Time to mature.** At the default `randomTickSpeed` 3, a given block gets a random tick about every 68 s, so one
  age takes about 9 min and age 0 to 7 about 64 min. This is my own arithmetic; the server's gamerule was not read.
- **Night growth.** Outdoors, `getRawBrightness(pos, 0)` passes 0 for sky darkening, so a mint with sky access should
  grow at night. This is inferred from how vanilla defines the method, not tested.
- **Sell white seeds only?** Because white rarely drops other colours, one white-seed line could in principle supply
  all six. At about 1.8% per colour per harvest that is slow, so six lines remain the practical design. This is a
  design inference.

## Unknown / experiment candidates

These belong in `EXPERIMENT_BACKLOG.md`, but the brief limited this unit to writing this file.

- **E1 (jar read, no server).** Open the 1.8.0 jar with Python zipfile and record three things:
  - whether `data/cobblemon/loot_table/blocks/{red,white}_mint.json` match the tables above;
  - which second loot table carries `white_mint_seeds`;
  - whether any other jar in the snapshot overrides `cobblemon:blocks/*_mint`.
  Pass: the tables match, and the second table is named.
- **E2 (staging, in game).** `/give` one seed of each colour, then:
  - plant on hydrated farmland under the sky. Expect it to place, and to refuse dirt and grass;
  - apply bone meal. Expect exactly 7 uses to reach age 7 (`/data` or F3 shows `age=7`);
  - break a mature plant, 20 times per colour. Expect 1-3 leaves and at least 1 seed every time;
  - craft one mint from the leaves.
  Pass: every one of these holds. Then repeat one plant unattended for 90 min to confirm unaided growth.

## Sources

- Cobblemon 1.8.0 source, GitLab `cable-mc/cobblemon` at ref `1.8.0`, the paths cited inline, fetched 2026-10-07.
- https://wiki.cobblemon.com/index.php/Mint_Seed (unversioned, edited 2026-01-12).
- https://minecraft.wiki/w/Wheat_Seeds, https://minecraft.wiki/w/Farmland (Java, current).
- Local: the paths cited inline.
