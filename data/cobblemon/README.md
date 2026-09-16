# Cobblemon encounter compilation

Generated data files for review. They have **not** been installed into a server or live datapack.

- `data/cobblers/spawn_pool_world/routes/`: 9 Cobblemon 1.8 world-spawn files covering all 1,269 route boxes.
- `data/cobblers/habitat_pools/`: 9 Cobblemon 1.8 Habitat Block pool files.
- Source and eligibility decisions: `data/spawns.json`.
- Suppression policy and unproven runtime boundary: `data/spawn_suppression.json`.

This directory is a structurally loadable datapack candidate. It has not been installed. It deliberately omits inherited-pool suppression because that requires transforming the complete installed spawn set and still needs EXP-012. Habitat pool files define rosters; world placement and `ReplaceSpawns` NBT remain separate authored-world work.

## Schema evidence

The route key set was checked against Cobblemon 1.8 `SpawningCondition.class` and stock `data/cobblemon/spawn_pool_world/*.json`. The Habitat key set was checked against stock `data/cobblemon/habitat_pools/abandoned_fortress.json`, `abandoned_village_house.json`, `HabitatPool.class` and `HabitatSpawn.class` in `Cobblemon-fabric-1.8.0+1.21.1.jar` (SHA-256 `a6228f3291c70ed6348b9a47beadabc79cb241b6522312e7e2b56d428dc9ec31`).

This verifies the serialized field names, not runtime loading or block placement. `HabitatBlockEntity.class` verifies that `ReplaceSpawns` filters to the block roster inside `RangeOfInfluence`; its influence geometry, persistence and interaction with fishing remain unproven here.