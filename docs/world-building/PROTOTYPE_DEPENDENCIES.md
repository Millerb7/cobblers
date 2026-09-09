# EXP-009 production candidates

This focused classification applies to the disposable prototype. It does not
freeze the permanent world-critical dependency set.

| Component | Classification | Reason |
| --- | --- | --- |
| Cobblemon 1.8.0 | KEEP FOR PROTOTYPE | Required runtime and Center source; the target server already boots. |
| Terralith | KEEP BUT MANUAL TEST REQUIRED | Compare a fixed seed and exported-world boundaries before allowing it to decorate new chunks around authored terrain. |
| Biome Replacer | KEEP BUT MANUAL TEST REQUIRED | Its Terralith-to-vanilla mappings affect Cobblemon spawning and need a client/runtime biome check. |
| Cobblemon Additions | KEEP BUT MANUAL TEST REQUIRED | Individual templates are useful; full village generation remains excluded because of missing-pool warnings. |
| Rechiseled | KEEP BUT MANUAL TEST REQUIRED | Strong architectural palette; representative placement/restart test remains outstanding. |
| Carved Wood | KEEP BUT MANUAL TEST REQUIRED | Regional timber palette; representative placement/restart test remains outstanding. |
| CobbleFurnies | KEEP BUT MANUAL TEST REQUIRED | Service interiors and a Legendary Monuments dependency; Cobblemon-facing behaviour needs inspection. |
| Handcrafted | KEEP BUT MANUAL TEST REQUIRED | Interior palette; representative placement/restart test remains outstanding. |
| Cozy Home | KEEP BUT MANUAL TEST REQUIRED | Domestic palette; representative placement/restart test remains outstanding. |
| Moar Concrete | KEEP BUT MANUAL TEST REQUIRED | Construction palette; representative placement/restart test remains outstanding. |
| Pokeblocks | KEEP BUT MANUAL TEST REQUIRED | Themed props; representative placement/restart test remains outstanding. |
| Beautify | KEEP BUT MANUAL TEST REQUIRED | Street/garden palette; representative placement/restart test remains outstanding. |
| Repurposed Structures | OPTIONAL | No prototype placement requires it; test only if a specific piece is selected. |
| Legendary Monuments | DO NOT DEPEND ON YET | Pack-specific worldgen and licensing/functional questions remain open. |

The source terrain deliberately uses vanilla terrain/biome categories. Decorative
mods become dependencies only when their blocks are intentionally placed in the
exported world and recorded in a structure manifest.
