# Water life: the block pass over the water export

**Status:** build spec, 2026-10-02. It is `WATER_BUILD_PLAN.md` Phase C items 1 (the skin), 2, 3, the surfacing
cave from item 4, and item 5, made concrete. It redesigns nothing: every role, stage and site is `WATER_MAP.md`'s
allocation and `WATER_BUILD_PLAN.md`'s tables. Where this spec departs from them it says so under "Departures".

**Why now.** Phase B is done. The canonical heightmap is the applied water export (`d1bc68d3…`, `docs/STATE.md`
"World facts"), so every shelf, drop-off, shoal, hump, bar, skerry, the Relic reef platform and the seabed are already
ground that `tools/ground.py` returns. `staging-2026-10-01` was exported from that heightmap. Everything below is
**blocks** seated on it, so **none of it needs an export** (see "Export flags").

## What is built, in two packs

| Pack | Tool and data | Content | `reapply.py` step |
|---|---|---|---|
| `cobblers_lake_life` | `tools/lake_life.py`, `data/lake_life.json` | the lake skin and the lake hooks | after the islet and the legendaries' chambers, before the towns |
| `cobblers_sea_life` | `tools/sea_life.py`, `data/sea_life.json` | the shore, the wrecks and Rift debris, the waterline sea cave, the surfacing cave | after the sea drift (R9SD), before the towns |

Each has an **independent** offline audit by another hand (`tools/lake_life_audit.py`, `tools/sea_life_audit.py`,
plus pytest suites), in the `sea_drift_audit.py` pattern: the audit reads the generated functions and the heightmap
and the data, never the builder's model.

### 1. Lake floors with structure (`cobblers_lake_life`, the skin)

On every painted lake (`tools/water_mask.bodies()`), by depth = level - `round(ground)`, so the zones are read off the
applied bed, never restated:

| Zone (from depth) | What is written |
|---|---|
| shelf, 1-2 deep | seagrass (2 deep: some tall), lily pads over still shelf water, reeds (sugar cane) at the bank where the bed is sand, dirt or grass |
| drop-off band, 3 to the lake's `drop_depth` (`data/water_shape.json` `lakes.bodies`) | kelp in patches, never within 2 of the surface; gravel and cobble scree |
| floor, deeper | silt: mud and clay patches replacing the top bed block only (no column changes height); sunken logs and stumps |
| humps and shoals (local maxima of the bed) | boulder piles (stone, mossy cobble, andesite), a sunken log |
| Marshy Marsh's shelf humps | drowned trees: dead trunks (stripped dark oak) rising out of the water, roots in the bed |

Density is a seeded hash per column; nothing is placed inside a town, route, bridge, dock, portal arch's clearance, a
legendary's `spawn_free_zone` or sleeve, or the sea town.

### 2. Lake hooks: sunken things, each pointing at something that exists

Every hook is seen from the surface and leads to a mechanism already in the world. **No new mechanism.**

| Lake | Hook (seen from the surface) | Leads to (exists) |
|---|---|---|
| Viltri | a line of survey buoys from the sounding platform over the drop-off, chains running down; a lantern on the lowest marker | the survey floor (`SQ-G2-01`) and the dive portal `dive_viltri_floor` |
| Shrew | a torn surveyor's float on the nearest shoal, its line running down into the pit; the surveyor's field case on the floor (a cache) | `SQ-DIG-02`; the dive portal `dive_shrew_pit` |
| Arrow | a ring of standing stones on the floor round Mesprit's grotto mouth, lit from inside | `legendaries.json` `mesprit` (its chamber exists; the ring was always "the lake-sites pack's dressing") |
| Marshy Marsh | drowned trees in a ring round the pit, one with a soul-lantern glow in its roots; a sunken boardwalk down the pit wall | `legendaries.json` `azelf` |
| Tilpey | a pale gold light deep off the Weeping Elder island's apron | `legendaries.json` `uxie`; the dive portal `dive_tilpey_gate` |
| Peak Pond, Watering Hole, the tarn | a sunken skiff or a lantern on a chain over the floor | the dive portals on their floors |

Lights are waterlogged lanterns and soul lanterns, sea pickles and glow lichen. **Never `minecraft:light` and never a
bubble column** (Departures).

### 3. The shallows and shore water (`cobblers_sea_life`), the only sea before Dive

On the coasts the water export shaped (`data/water_shape.json` `coasts`):
- **kelp beds** just past the wade line (3+ deep), seen swaying from the beach, never within 2 of the surface;
  **seagrass** on the sandy flats and runnels;
- **the Relic reef**: coral blocks, coral and fans and sea pickles on the reef platform (`coasts.relic_reef`), the
  sunlit edge at 3 deep seen from the islet, the drop-off below it;
- **rock pools** on the windward and north-west rocky points: a rim of boulders built on the ground at the tide line,
  water held inside it, never a cut into the ground (Departures);
- **a beached wreck** on the south strand (a procedural hull lying on its side on the sand), a cache in it;
- **the waterline sea cave** on the windward cliffs: a mouth at the tide line, walked into on foot at S0, a short
  carved cave (Victory Road's shell and walk-out checks), a cache at its end.

### 4. Shipwrecks and Rift debris (`cobblers_sea_life`), a recurring find

40-60 objects on the seabed, a quarter within Surf reach (at most 35 deep) and the rest Dive only, spaced by a density
rule per band and marine region. **All procedural block kits written by the tool** (Departures):
- **vessels**: a rowboat, a fishing boat, a two-master broken in half, a Pacifidlog log raft;
- **Rift debris, things that do not belong**: a house lying broken (walls, a roof, a door, a bed), a length of rail
  with a cart, a lamppost, a Centre sign, a garden gate with a mailbox, a bench, a bus-stop shelter; seeded in lines
  that point back toward the Rift;
- **hooks**: on the shallower finds, a lantern still burning, or a mast or chimney rising toward the surface (never
  within 2 of it inside a gate line's clearance, so no wreck becomes a rest point on a crossing that is a gate);
- **caches**: a barrel in about one find in four, a `data/rewards.json` record with a trigger box (the sea drift's
  pattern), contents from items another record already verifies.

### 5. The surfacing cave (`cobblers_sea_life`)

One cave under the windward headland south of Viltri Light, or in the Frostwater Shelf's cold ruins, **sited by
measurement and reported** before it is built: a mouth 20-40 deep in a cliff or on the seabed, a flooded passage that
rises into an air chamber whose pool is the only way in, dry galleries on foot from the pool to a cache and a sealed
view out through a crack in the cliff. The **Dive gate is the air ladder itself**: the passage's underwater length from
the open surface is longer than a Surf player's air (`data/blackout.json` `water`, read at run time, never restated),
so it is Dive content without any new gate. A lantern at the mouth is its hook.

## Excluded everywhere

Towns and their margins, route corridors, bridges, docks, the ferry lanes and every crossing declared a gate
(`data/water_shape.json` `coasts.gate_line_clearance_blocks`: no new rest point within it), the dive portals' arches,
the legendaries' sleeves and spawn-free zones, Relic Island's islet, Driftmouth Isle and the Seaward Drift's cover,
Pacifidlog, the First Cast hole, the Windward Deep and Victory Road. The tools find these through the existing
helpers (`tools/water_shape.py`'s protect masks, `tools/water_mask.py`, `data/placements.json`), never a new list.

## Departures from the plan, and why

- **No bubble columns.** In vanilla a player inside any bubble column does not lose air (`LivingEntity.baseTick`
  skips the decrement when the eye block is a bubble column) [A: read from vanilla behaviour, not run here]. A hook
  that is also a free air source bypasses the ladder the way Water Breathing did. `WATER_BUILD_PLAN.md` used a bubble
  column for Arrow Lake's hook and flagged the bypass; light replaces it.
- **Rock pools are rims, not cuts.** A cut lowers the ground, which is a height (plan section 2), and would need an
  export. A rim of boulders on the existing rock holds the water above ground and changes no column's ground.
- **Wrecks and debris are procedural kits, not templates.** Vanilla shipwreck and ruin templates cannot be committed
  (Mojang's), `/place template` cannot be audited offline, and whether a placed template floods correctly is
  unproven. A kit the tool writes block by block is committable, deterministic and checked block by block.

## Export flags

**Nothing in this spec needs an export.** It lands on `staging-2026-10-01` with an install and its `reapply.py` steps,
and in the live world at the live re-export like every other block pass. Flagged and **not built** here, because each
needs an export or an owner decision:
- the river skin (riffles, drift at bends): blocks, but proof P3 (do flowing riffles hold) is unrun;
- the Viltri Ravine stream: held by the owner;
- the Lugia trench: blocks below y10, blocked on an owner decision (`legendaries.json` `lugia`);
- the three wreck coves (Lugia's keys) and the forge ruin: Cobblemon jigsaw templates, which need EXP-014's capture;
- true rock-pool depressions or a reshaped cliff for the sea cave's mouth: these would be heights, so the water
  export's next revision.

## Not verified

None of this has run in a game. Specifically unproven [A]: that kelp and seagrass hold in a lake (proof P6); that
a lantern 25-50 deep is seen from the surface (P4); that an air chamber at depth stays dry across a restart (P1).
