# Build prep: creek, tooling, cavern, tree town, gym towns 1 and 2, kits (2026-09-16)

**Status: built.** This was the plan; the creek world is exported and everything in it has been built and checked.
What was run and what each check measured is in [`BUILT.md`](BUILT.md).

## Glacial Tear creek

Restored with the valley-wall head rule; details in [`RIVERS.md`](RIVERS.md#the-major-river). No other course is
affected.

## Tooling

| Piece | State |
| --- | --- |
| Axiom 6.0.5 on the server | **Installed and loading.** It is the same jar for server and client (`environment: *`); sha256 `fd443dd7…`. The boot shows "Initializing Axiom/6.0.5", with no new errors against the previous boot (43 error lines, 44 before) and no mixin failures |
| Axiom on your client | **Already installed** in the Modrinth profile "Fabric 1.21.10": `Axiom-6.0.5-for-MC1.21.1.jar` with Fabric API 0.116.14 and Sodium 0.8.12. Axiom's metadata marks Sodium 0.5.0 and older as incompatible |
| Axiom permissions | **The server has no permissions mod**, so Axiom falls back to operator status. Its server class checks for the Fabric Permissions API and otherwise uses `isOp`. You (`ExpiredWhippets`) are an operator at level 4 in `ops.json`. Join, press the Axiom editor key, and the server should grant everything. **Not tested yet:** that needs you in game |
| WorldEdit | **Not installed.** It needs a download; the build for Fabric 1.21.1 on Modrinth is `worldedit-mod-7.3.8.jar` (6,222,854 bytes, sha512 `e039492d…`). **Waiting on your yes.** No client mod is needed: WorldEdit's commands run server-side. WorldEdit CUI is an optional client visualiser |

## Displaced City cavern

**Depth check (a).** Done on the exported world's region files, over the full 200 × 200 footprint (x3250–3449,
z1650–1849).
- **Rock depth:** stone is continuous to bedrock at y-64 in every column, so the spec stands.
- **Solid share:** the y32–72 band is 99.93% solid, and 99.81% below y32. The gaps are underground water pockets
  (1,226 cells in the band). They are sealed before digging.
- **Rock over a y72 ceiling:** at least 29 blocks, median 32, with the surface at y101–135.
- **The restored creek changes this:** its bed crosses the footprint, and in 8 columns only 23 blocks would remain.
  The plan lowers the ceiling there, to y71 over 6 columns.

**Plan (b–f): `tools/cavern_plan.py`, functions not run.**

| Part | Plan |
| --- | --- |
| Excavation | 1,225,002 blocks, between the graded floor and the ceiling |
| Floor | y33–53, median 38: a rounded summit, benches at y46 and y40 where a town's streets could run, an old road ridge from the tunnel's arrival up to the summit, low relief throughout |
| Ceiling | y72 (y71 over 6 columns under the creek). At least 24 blocks of rock everywhere. Sea lanterns behind light blue stained glass |
| Headroom | minimum 17, median 32 |
| Light | 800 light blocks in a diamond lattice 10 apart, at floor+3 |
| Trees | 40 from the foliage library's cherry_vale classes (35 cherry, 2 birch, 3 azalea), thinned on the benches and summit and cleared along the arrival ridge |
| Tunnel | 339 blocks at a grade of 0.236 (limit 0.25). 5 wide and 5 tall, stone brick with a stair at each step, a light every 20 blocks. From a mouth at (3035, 119, 1700) to (3262, 39, 1660). The first 45 blocks are an open cut into the flank; after that there are at least 3 blocks of cover, median 20 |
| Approach | 188 blocks from the gym 3 to gym 4 leg at (3220, 1524) to the mouth |
| Biome | `60_biome` fills `minecraft:cherry_grove`, **not run: see the question below** |

**Light, tested (c).** In the sealed chamber:
- **Growth threshold:** every one of 441 positions one block above a sapling cell reads 9 or more. The predicted
  worst points read exactly 9.
- **Spawn threshold:** every spawn cell reads block light 8 or more.
- **Measured with:** the location predicate's light check, `execute if predicate {condition:"minecraft:location_check", predicate:{light:{light:{min:N}}}}`.
- **Why that rules out hostiles:** the chamber is sealed, so it has no sky light, and overworld monsters need block
  light 0.

**Growth: not yet shown.**
- **What happened:** 12 cherry saplings, 8 at the worst-lit points and 4 near a light, did not advance a single
  stage in 60 minutes of force-loaded ticking (checked every 5 minutes).
- **Why:** random ticks don't run in chunks with no player nearby. Under normal ticking each sapling gets a random
  tick about every 68 seconds and advances on 1 in 7, so all 12 staying at stage 0 for an hour is not chance.
- **To finish the test:** it needs a player within range. Stand or fly in spectator near (-800, -35, -800) for about
  20 minutes and the saplings should grow. The saplings and chamber are still there.

**Sequencing.** The restored creek changes the ground above the cavern. So excavate **after** the creek export, in
the new world, and generate the functions again with `--surface-world` on that world so the ceiling follows the real
creek bed. Excavating before the export would be lost, or copying its chunks across would undo the creek.

## Tree town

**Survey (a).** `tools/tree_town_sites.py` tests a 128-block grid for:
- 250–900 blocks off a routed leg;
- 600 blocks from towns and rest stops, 300 from outposts;
- 500 blocks outside Peak Pond Hollow;
- a forest type of at least 30 stems per hectare;
- a 192-block grove with mean slope under 12° and no open water within 24 blocks of its centre;
- scored by how many leg points within 900 blocks can see a point 40 blocks above the grove.

18 cells passed, one per sub-region below.

| Sub-region | Centre | Forest | Off path | From Peak Pond Hollow | Grove slope | Seen | Grove |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| tilpey_north_shore | (5600, 3296) y102 | birch_shore 65/ha | 294 | 1264 | 8.1° | 99% | 8 birch giants, 29–64 apart |
| **foothill_woods** | (2016, 2272) y115 | foothill_mixed 80/ha | 388 | 1624 | 9.5° | 89% | 7 oak giants, 34–48 apart |
| viltris_path_valley | (992, 3936) y137 | riparian_woods 55/ha | 596 | 3535 | 11.2° | 100% | 9 oak giants, 31–48 apart |
| lake_viltri_hollow | (2272, 2784) y114 | riparian_woods 55/ha | 531 | 1819 | 9.5° | 91% | 8 oak giants, 34–56 apart |
| viltri_plateau | (2400, 3040) y107 | birch_plateau 70/ha | 636 | 1884 | 11.0° | 63% | 8 birch giants, 30–41 apart |
| marshy_marsh | (5088, 1760) y111 | drowned_swamp 45/ha | 716 | 604 | 10.4° | 71% | 9 mangrove giants, 29–45 apart |
| wedge_south | (4704, 4448) y112 | broken_oakwood 60/ha | 458 | 1859 | 11.3° | 14% | 7 dark oak giants, 33–53 apart |

**Recommended: Foothill Woods.**
- **The densest wood on the list** (80 stems per hectare), so the giants read as the forest's elders.
- **Discoverable:** 388 blocks off the leg from Misty to Surge, and seen from 89% of that leg's points within
  900 blocks.
- **Clear of Peak Pond Hollow** by 1,624 blocks.

**Marshy Marsh is the only swamp.** It is barely 600 blocks from Peak Pond Hollow, and its grove ground measured dry:
5% within 5 blocks of water.

**What the town is (c):** a warden village that keeps the forest floor for the forest's Pokémon.
- **Why it is in the trees:** wild Pokémon spawn on the ground. A town on the floor would pave and fence the wood's
  spawning ground. A town in the limbs leaves it wild underneath, so a player walks through a living encounter area
  to reach stairs up the trunks.

**Grove (b).** `tools/tree_grove.py` generates habitat giants as kit prefabs, in oak, birch, mangrove and dark oak,
three variants each.
- **The shape:** a 5×5 trunk with buttress roots, and near-level limbs at 16–20 blocks reaching 12. The trunk is
  clear up to 30 blocks, with a crown of radius 14 above that.
- **Spacing:** trunks sit about 36 apart on flattened 5×5 ground (at most 0.7 blocks of relief), so crowns just touch
  and limb tips leave about 7 blocks to bridge.
- **Checked on the server:** one giant was placed and its trunk, limb storey and crown checked, then removed.
- **Not placed:** a grove goes in only after you pick the site.

## Gym towns 1 and 2

Plan data is in `data/placements.json` (`settlements.gym1_town.plan`, `gym2_town.plan`). `tools/town_plan.py`
grades the streets, proposes house lots, spaces lamps and writes prep fills to `build/town_prep/`, which are not run.

| | Brock (Viltri Plateau) | Misty (Lake Viltri Hollow) |
| --- | --- | --- |
| Route | In from the south-west, straight up the approach street into the plaza; out due north | In along the shore from the south-east into the plaza; out due north |
| Center, Mart | Center on the plaza's west side facing it: the first building ahead. Mart across the square | Center at the plaza's north-west corner; Mart across the avenue on the way out |
| Gym | Alone on the south-east knoll (y141–142), the highest ground, up its own lane; lot flattened to y141 | On the waterfront between two piers, facing the promenade, backing onto the lake |
| Streets | Approach and avenue 5 wide (polished andesite); lanes 3–4 wide (cobblestone); plaza of stone bricks at y138 | Shore street, avenue and west street in mud brick; promenade, link and plaza in prismarine bricks, plaza at y107 |
| House lots | 18 candidates, 12×14 | 8 candidates, 10×12 |
| Lamps | 23 | 19 |
| Earthwork | 1,439 blocks cut, 268 filled; streets no steeper than 1 block per 8 | 40 cut, 4 filled |

**Paving and spawns,** read from the loaded spawn data:
- **Base-block conditions are rare:** only 17 of Cobblemon's 4,892 spawn entries need a particular block underneath.
  - Quartz only counts in Nether quartz biomes.
  - Sand only counts in beach biomes.
  - Concrete brings Varoom and Revavroom in every overworld biome.
- **The Cobbleverse datapack widens concrete** to all 16 colours, and adds Terapagos on amethyst in caves.
- **So no street is concrete.** Stone, andesite, cobble, mud brick and prismarine carry no base-block condition.
- **Existing concrete:** the donor Pokémon Center and Mart already have white and blue concrete in their walls and
  roofs, so Varoom can spawn there in any town. Worth remembering when you compose.
- **Hostile mobs** need block light 0, so every street block is kept within 14 blocks of a lamp.

## Kits

`kits/structures/prefabs/<kind>/<set>/<name>.nbt` plus a sidecar, placed as `cobblers:kits/...`. The procedure for
saving from Axiom is in [`kits/structures/prefabs/README.md`](../../kits/structures/prefabs/README.md).
- **Tested:** importing a synthetic Sponge v2 and v3 file, then placing it on the server (door state and chest name
  checked).
- **Not tested:** a real Axiom export.
