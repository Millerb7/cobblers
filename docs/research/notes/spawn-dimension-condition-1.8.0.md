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

- `tools/suppress_inherited_spawns.py` `box_anticondition`: every suppression box carries
  `"dimensions": ["minecraft:overworld"]` (N153).
- `tools/compile_spawns.py` `open_sky_forced`: `canSeeSky: true` is forced only on a land or surface entry whose
  `conditions.dimensions` is absent or exactly `["minecraft:overworld"]` (N154).

## NOT verified

- That the bound anticonditions load and an inherited Nether spawn appears at an overworld box's x/z
  (`docs/mechanics/NETHER_ENCOUNTERS.md` experiment N3), or that a grounded Nether entry without `canSeeSky` spawns
  (experiment N1).
- The server's heap and load time with the larger suppression pack (see the measurement in the commit that applied
  this: 240.8 MB to 418.8 MB against the 2026-10-05 offline snapshot's mods and global datapacks).
