# The spawn condition that restricts a dimension, Cobblemon 1.8.0

Read 2026-10-08 for review N153/N154, from the server's jar
`C:/Users/wnd/Documents/github/cobblers-server/mods/Cobblemon-fabric-1.8.0+1.21.1.jar` (read only: Python `zipfile`
for strings and JSON, `javap -c -p -cp <jar>` for bytecode). Nothing was run in game.

## VERIFIED in the jar

- **Field.** `com/cobblemon/mod/common/api/spawning/condition/SpawningCondition.class` declares
  `private java.util.List<net.minecraft.class_2960> dimensions` (`class_2960` is the intermediary name of
  `ResourceLocation`), with `getDimensions` / `setDimensions`. No `SerializedName` string is in the class, so the JSON
  key is the field name: **`"dimensions"`**, a list of dimension ids.
- **Check.** `SpawningCondition.fits(T)`, bytecode offsets 365-426: if `dimensions != null` and
  `!dimensions.isEmpty()` and `!dimensions.contains(position.getWorld().method_27983().method_29177())` (that is,
  `world.dimension().location()`), return false. So an absent or **empty** list restricts nothing, and a listed id must
  equal the world's dimension location exactly.
- **Anticonditions.** `com/cobblemon/mod/common/api/spawning/detail/SpawnDetail.class` `isSatisfiedBy`, offsets
  129-240: if `anticonditions` is non-empty and **any** of them `isSatisfiedBy` the position, return false. An
  anticondition is a full `SpawningCondition`, so its fields AND together: a box with
  `"dimensions": ["minecraft:overworld"]` is satisfied only inside the box *and* on the overworld, and in the Nether or
  the End it never removes the detail.
- **Value format, in use.** The jar's own 1,544 `spawn_pool_world` files never use `dimensions`. A working example on
  the same server: `cobblemon-additions-4.1.6.jar`
  `data/cobblemon/spawn_pool_world/swamp_hut_pokemon.json`, five details with `"dimensions": ["minecraft:overworld"]`
  (the only mod jar of the server's `mods/` that uses the field). Namespaced ids, as written.
- **`canSeeSky`** is used by 1,209 stock details' conditions; it is a `Boolean` field compared with the position's
  sky flag (`docs/research/notes/underground-biomes.md` 3c).

## Applied

- `tools/suppress_inherited_spawns.py`: first, every suppression box carried `"dimensions": ["minecraft:overworld"]`
  (N153). **Reverted 2026-10-08**: the pack grew from 240.8 MB to 418.8 MB (that unit's measurement). Instead every
  inherited detail gets ONE anticondition `{"dimensions": ["minecraft:the_nether"]}` (`NETHER_ANTICONDITION`),
  which removes it everywhere in the Nether and nowhere else, as the owner's "replace" for the Nether asked
  (`docs/mechanics/NETHER_ENCOUNTERS.md` Q3). Measured on the 2026-10-05 offline snapshot's mods and global datapacks
  with an empty scratch world, `--subregions --boxes merged --grid 16`: 1,729 files, 5,195 details, **240,777,251
  bytes without the Nether rule and 240,985,051 with it** (+207,800). With the Nether anticondition removed from every
  detail the two packs are identical, file for file.
- `tools/compile_spawns.py` `open_sky_forced`: `canSeeSky: true` is forced only on a land or surface entry whose
  `conditions.dimensions` is absent or exactly `["minecraft:overworld"]` (N154).

## NOT verified

- That the bound anticonditions load and an inherited Nether spawn appears at an overworld box's x/z
  (`docs/mechanics/NETHER_ENCOUNTERS.md` experiment N3), or that a grounded Nether entry without `canSeeSky` spawns
  (experiment N1).
- That the Nether anticondition loads and `/checkspawn` in the Nether lists none of the inherited species (N3).

## Also read 2026-10-08, for the Nether tables (same jar, sha256 a6228f32...dc9ec31)

- **`neededNearbyBlocks`** is a field of `AreaTypeSpawningCondition` (the superclass of the grounded condition):
  `List<RegistryLikeCondition<Block>>`. `fits`, offsets 74-261: when the list is non-empty, the position fails unless
  **at least one** listed block (id or tag) matches one of `AreaSpawnablePosition.getNearbyBlockHolders()`. Those come
  from `AreaSpawnablePositionCalculator.getNearbyBlocks`, whose defaults read
  `CobblemonConfig.getMaxNearbyBlocksHorizontalRange()` and `getMaxNearbyBlocksVerticalRange()`; our
  `modpack/config/cobblemon/main.json` and the snapshot's `config/cobblemon/main.json` set them to **4 and 2**. The
  exact box shape the calculator draws with them is not read. The jar's own pools use it on 448 details
  (`minecraft:water` 87, `#minecraft:iron_ores` 18, `minecraft:lily_pad` 17, ...).
- **`structures`** is `List<Either<ResourceLocation, TagKey<Structure>>>` on `SpawningCondition`, checked through the
  position's structure cache. The jar's own pools use it on 852 details, e.g. `["minecraft:monument"]`,
  `["minecraft:swamp_hut"]`, `["#minecraft:village"]`. `minecraft:fortress` and `minecraft:bastion_remnant` are the
  vanilla structure ids recorded from `server-1.21.1.jar` in `data/structures.json`.
