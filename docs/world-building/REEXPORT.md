# Re-export: cobblers-10240

## The export procedure

An export regenerates every region file from the WorldPainter project and the canonical heightmap. **Nothing built in
game survives it**, and neither do the datapacks that live inside the world folder. Everything below is either carried
by the export or has to be re-applied, in this order, with the check beside it. Anything not in this list is content
the next export erases silently: add it here the day it is first built.

Run the whole sequence against a staging export first (see "Dry run" below). Never re-apply straight into the live
world before the dry run passes.

### Carried by the export

| # | Content | Carried because |
| --- | --- | --- |
| C1 | Terrain, coasts, massifs, river cuts, the vertical rescale | the canonical heightmap is the export input (`data/world.json` sha256) |
| C2 | Pads: the Scar y280, Frostpeak shrine y310, Surge's shelf y174.4 | pressed into the canonical heightmap by `tools/press_pads.py` |
| C3 | Biomes, surface materials, snow and scree, the thinned grass | the paint manifest passed with `--paint` |
| C4 | 77,750 foliage objects, including the painted landmark trees | WorldPainter custom-object layers from the same manifest |
| C5 | Lakes, rivers and water levels | paint |
| C6 | Seed, world settings, border, spawn, the enabled-datapack **list** | `tools/reexport.py` copies them from the old level.dat |

Ores and underground water pockets are re-rolled by WorldPainter on every export; they are not authored.

### Status, 2026-09-21

**Rehearsed end to end on a fresh staging export, and clean by result** (EXP-026). EXP-024 (2026-09-17) was reported
as a proof and was a proof that the commands run: most of its checks were command checks, and the builds they passed
were missing 13,586 of Route 1's 46,052 trees and 165 cavern roof columns. Since then every function holds its own
chunks, every step has a result check, and the whole sequence is driven by one tool, `tools/reapply.py`.

Its first staging run (`cobblers-dryrun2`) stopped and failed audit on real defects the disposable world had hidden:
trees and flowers standing on streets, and gravel falling from the cavern roof. Both are fixed at the source. The
second, on a fresh export (`cobblers-dryrun3`), ran every step without a stop, verified 24 of 24 places at 0 floor
gaps, and audited clean: cavern roof 40,000 of 40,000, forest 46,051 of 46,052, world tree 1,380 of 1,380, islet
2,139 of 2,139, all 23 planned places plan-clean. **The live re-export has not been run.**

### Which earlier "verified" results were command-checked

A **result check** compares the world with what the step should have built, everywhere the step builds. A
**command check** confirms the command ran, or samples a point, or reads a count with no expected number.

| Step | EXP-024 said | What it actually checked | Kind | What it missed |
| --- | --- | --- | --- | --- |
| R1 | both packs enabled | `/datapack list enabled` | config, adequate | nothing |
| R2 cavern | ok | air, floor and biome at sampled points | command (sample) | 165 roof-cap columns open; the roof was never read |
| R3 world tree | 394 blocks, top y512 | one column, (2016, 2280) | command (sample) | anything off that column; its "crown top" check named a block the tree never reaches |
| R4 grove | 33,545 oak logs | a count in the grove box | command (no expectation) | any shortfall: there was no number to compare with |
| R5 elders | ok | 3 of 48 sites sampled | command (sample) | the other 45 |
| R6 maze forest | 157 of 158 corridor points clear | eye-height clearance, the sapling | result, of the wrong property | 13,586 missing trees: a missing tree makes a corridor clearer, so the check passed more easily |
| R7 hometown | 0 gaps in 1,670 columns | floor support at each building's corners | result, seating only | roads, paving, whether each building stands |
| R8 gym-town prep | ok | one plaza block | command (sample) | Brock's streets laid a block off their plan (found 2026-09-21) |
| R9 Brock's gym | 2,712 blocks, substitutions exact | block and block-entity counts in its box | result | nothing found since |
| R10 islet | 400 columns, y63-70 | column tops against `data/towns.json` | result | nothing found since |
| (BUILT.md) cavern | "1,940,550 blocks removed" | the excavation function's own count | command | whether they were removed |

The town and trader checks added since (`town_audit.py`, `traders.py verify`) are result checks from the start.

### Re-applied, in order

Every step takes its ground from the source root (the out-of-repo heightmap), never from the world being rebuilt:
`--surface-world` is refused by every placement tool (CLAUDE.md, `tests/test_ground_rule.py`). Regenerate the
gitignored derived inputs first: they are not in the repository. Every generated function holds the chunks it writes
and splits fills over the block limit; `python tools/function_limits.py build` must report 0 problems before
anything is installed.

| # | Step | Command | Result check |
| --- | --- | --- | --- |
| R0 | Derived inputs | `python tools/critical_legs.py --source-root <root>`; `python tools/paint_maps.py` if the paint changed | the files exist (inputs, not results) |
| R1 | World datapacks back into the world folder | copy `modpack/datapacks/cobblers_height` and the generated `build/datapacks/cobblers_worldtree` into `<world>/datapacks/` | `/datapack list enabled` names both. **cobblers_height raises the build limit to y575; without it the world tree's crown (y457-535) will not build** |
| R2 | Displaced City cavern | `python tools/cavern_plan.py --source-root <root> --install <server>/datapacks`, then `/function cobblers:cavern/00_seal`, `05_reset`, `10_excavate`, `20_surfaces`, `30_trees`, `40_light`, `50_tunnel`, `70_drain`, then `15_cap` last (water seeps until the drain runs), then `60_biome` | `python tools/build_audit.py --world <stopped copy> --only cavern`: every one of 40,000 columns read; grass at the planned floor in 98%, the 4-block roof cap solid in 100%, the interior open in 99%. Passed 2026-09-21: 39,996 / 40,000 / 40,000. Biome: `execute if biome <inside> minecraft:cherry_grove` |
| R3 | World tree | `python tools/world_tree.py --source-root <root>`, install, `/function cobblers:worldtree/00_tree` … `03_tree`, then `90_foundation` | `python tools/build_audit.py --world <stopped copy> --only world_tree`: 13 trunk and crown columns replayed from the tree's own functions and compared block by block (99%), and the crown's highest block, (2044, 535, 2282), present. Passed 2026-09-21: 1,380 of 1,380 |
| R4 | Foothill grove: giants and elders | `python tools/tree_grove.py --source-root <root> --site 2016,2272 --id foothill_woods`, then its placement function; `--augment foothill_woods` for the elders | **no result check yet**: a count of logs in the grove box, with no expected number. Add a replay check before relying on it |
| R5 | The 48 elders | `python tools/elder_trees.py --source-root <root>`, then `build/elders/elders.mcfunction` | **no result check yet**: the run report lists 48 placed, which is the command's count. The tool re-picks sites, so compare with `derived/sites/elder_trees.json` from the previous run |
| R6 | Route 1 maze forest and the world-tree sapling | `python tools/maze_forest.py --source-root <root> --install <server>/datapacks`, then `/function cobblers:route1/tile_*` (16 tiles) | `python tools/build_audit.py --world <stopped copy> --only forest`: a log where each of the 46,052 placed trees puts its trunk, 98% or better. Passed 2026-09-21: 46,051 (the one is under a lantern post's fence). Corridor clearance at eye height is a separate check of the maze, not of the build |
| R7 | Hometown | `python tools/place_town.py hometown --source-root <root> --install <server>/datapacks`, `/reload`, `/function cobblers:towns/hometown` | `python tools/place_town.py hometown --verify --server-dir <server>`: 0 gaps. Seating only: the hometown has roads, not a town plan, so `town_audit.py`'s plan check does not cover it yet |
| R8 | Planned towns and places, 23: gym1-gym8 (Surge's included: the export carries its pad), the League, the Merian hut, the gorge hamlet, the Tableland stop, the Rift rim post, the Rift dig camp, the Scar, Northlight, the Mining Town, the tea town, Viltri Light, the jungle ruins, Sunset West, Relic Island, the Displaced City. The Displaced City after the cavern step and Relic Island after the islet step: their ground is the cavern floor and the islet (`tools/ground.py` `for_settlement`), not the heightmap | `python tools/rematerial.py`, then per place `python tools/town_plan.py <id> --source-root <root>` and its prep function (force-loads its own ground, levels donor lots, paves open squares, lights the lamps); then `python tools/place_town.py <id> --source-root <root> --install <server>/datapacks`, `/reload`, `/function cobblers:towns/<id>` | `python tools/town_audit.py <id> --world <stopped copy> --server-dir <server>`: every road cell paved as planned, no plaza paving outside the plan, every lamp lit, every building (houses, services, earthworks) at 95% of what it should be, no ground in its rooms, and no spawn-deciding block a template writes that the policy does not allow. Passed 2026-09-21 for all 23 on the staging export `cobblers-dryrun3` |
| R9 | Pack donors, 32: every gym, the League, Sabrina's observatory, dojo and department store, the Tableland lookout, the dig camp's excavation and tents, Northlight's field station, the Mining Town's assay office, the tea house and the six jungle ruins | `python tools/place_donor.py function --server-dir <server>`, install, `/function cobblers:structures/place_<id>` for each, then wait 3 seconds before saving (see "Pack placements that fail" below) | the same `town_audit.py` run: every donor at 95% of its template or better, with its own substitutions and removals applied (the League 159,470 of 159,471 on 2026-09-21) |
| R10 | Relic Island islet | `python tools/islet.py --source-root <root> --apply --server <server>` under the coordination lock | `python tools/build_audit.py --world <stopped copy> --only islet`: the 700-column dry core replayed from the islet function block for block, with no water standing on it. Passed 2026-09-21: 4,450 of 4,450 |
| R11 | Habitat Blocks | `python tools/habitat_blocks.py function`, install, `/function cobblers:habitats/place` with no player near them, then **restart the server**, and only then verify. See the three rules below | `python tools/habitat_blocks.py verify --rcon <server>` **after the restart** |
| R12 | Waystones | re-registered by R7 and R8; clear stale entries from `waystones.dat` before the first boot | the hometown waystone is claimable and no duplicate appears (an in-game check; not automated) |
| R13 | Spawn pools, suppression, spawn-free zones (datapacks, not blocks) | regenerate if routes or the mod set changed: `python tools/compile_spawns.py`; `python tools/suppress_inherited_spawns.py --server <server> --world <world> --subregions` (grid 16) | no compiled pool detail reaches a spawn-free zone, and every column of each zone is under the suppression boxes (`tests/test_spawn_free_zones.py` on the compiled pack). In game: EXP-012's `/checkspawn` on a corridor shows the authored roster only; nothing spawns on the League plateau (not yet tested with a player) |
| R14 | Town traders | `python tools/traders.py function --server-dir <server>`, install `build/datapacks/cobblers_vendors`, `/reload`, then `/function cobblers:towns/vendors_<settlement>` per town and wait 8 seconds. Safe to re-run. Never summon a trader by hand. Regional stock only, and none in gym4-gym8, the League or the batch 2 places, until the badge-gated stock lands | `python tools/traders.py verify --rcon <server>`: every trader `1 tagged, 1 on its spot, 0 untagged copies`, withdrawn ones absent, and no withheld item for sale |

**The order the driver runs:** R2, R3, R4, R5, R6, then **R10 before R7 and R8** (Relic Island's house stands on the
islet), then R7, R8 (the Displaced City and Relic Island last among the places), R9, R14, and a verify pass.
`tools/reapply.py plan` prints it. After the run, `tools/reapply.py audit` runs `build_audit.py` and `town_audit.py`
for every place on the stopped world; any mismatch is a failed step.

### Pack placements that fail

**What was seen.** In two full rebuilds of every town on the disposable world, 2 of 20 pack-donor placements did not
land: Koga's gym in one run, Blaine's in the next, each with nothing placed at all. Run on their own, 0 of 10
failed, and 8 back-to-back runs of the exact town-then-gym sequence all placed. The cause was not found.

**What the function does now.** Each donor's function force-loads its box, waits 20 ticks, places the template and
its substitutions, waits 20 ticks, and then checks one block of the template chosen so the ground cannot already hold
it (a battle-position marker, a sea lantern, stone bricks, never dirt or stone). If that block is missing it places
the template once more, then releases the box. In the rebuild after this change, every donor landed.

**If a placement still fails in the live run.** The retry happens once, in the same run. Nothing in game reports a
second failure, so the audit is what finds it: `town_audit.py` on the stopped world shows that donor far under 95%,
or with ground in its rooms.
1. Run that one donor's function again on its own (`/function cobblers:structures/place_<id>`): it is idempotent,
   placing the template over whatever is there and substituting again.
2. Save, stop, and audit again.
3. If it fails a second time on its own, that is not the failure seen so far (which never repeated in isolation).
   Stop the run, leave the retired world untouched, and treat it as a new problem to diagnose before continuing.
   The retired world folder is a complete, bootable copy, so rolling back loses nothing.

#### Habitat Blocks: three rules R11 depends on

Measured on the disposable world on 2026-09-17, with the crater pool in a block inside route
suppression box `r01_b0080` and a control block in open forest outside every box.

1. **Re-application is `setblock`, `data merge`, restart — and the validator runs after the restart.**
   A block placed by command carries its NBT but stays inert until its chunk loads *from disk*. An
   unload/reload cycle with `forceload remove` was not enough; the server restart was.
2. **`data merge` on a live habitat block silently deactivates it.** Editing `RangeOfInfluence` on a
   block that was already working left it cancelling nothing and spawning nothing — route Pokémon
   spawned 9 blocks from it — with no error anywhere. A restart brought it back with no other change.
   So a placement is never verified in the same session it was edited in.
3. **A habitat block beats the suppression pack, and `RangeOfInfluence` is honoured well past 24.**
   Inside `r01_b0080`, five minutes with the area cleared first gave 8 Pokémon in range, every one
   from the block's pool at its pool levels (44-49), out to 58 blocks, and not one corridor spawn
   survived inside the radius. A control block at range 64 spawned its pool at 63 blocks. Habitat
   blocks and corridors compose: the corridor table runs everywhere except inside a block's range.

### Known dependencies that are not in the repository

- **The canonical heightmap and the WorldPainter project** live outside git (`data/world.json` pins the heightmap by sha256).
- **`derived/` and `build/` are gitignored**: R0 regenerates what later steps read.
- **Donor templates under licence.** The Pokémon Center and Mart (`kits/structures/campaign/f4/services/*.nbt`) are
  local-only processed copies of `bca:default/one_off/pokecenter` and `…/structure_pokemart` from the installed
  COBBLEVERSE datapack; the other seven hometown templates are committed MIT donors. Brock's gym needs no local file at
  all: `data/placements.json` records it as `pack_template: cobbleverse:brock` and `tools/place_donor.py` places it from
  the installed pack and applies the recorded substitutions.
- **The staging directory must already exist** before `tools/reexport.py` runs; WorldPainter refuses to create it.

### Dry run

Before touching the live world:
1. Export to a staging directory outside the server (`tools/reexport.py --out-dir <staging> --name <name>`).
2. Boot it as a disposable universe (`--universe <staging> --world <name>`), under the coordination lock.
3. Run R0-R14 against it and record every result check, not just that the commands ran.
4. Only then retire the live world and repeat on the real export.

## The next live re-export: runbook (ready; the owner starts it)

Rehearsed twice on fresh staging exports on 2026-09-21 (EXP-026); the second run is the timing below. Every command
is one line to type; the driver stops itself at a checkpoint and says what to re-run.

**What it delivers.** The three pads land in the world, so Surge's town and the Scar are built with everything else;
all 23 planned places, 32 pack donors, the cavern, the world tree, the grove, the elders, Route 1's forest and the
islet are rebuilt from committed data; and every one of them is audited by result before anyone logs in.

**Before the day** (none of this touches the server)
1. Free about 3 GiB for the retired world.
2. `python tools/heightmap_check.py C:/Users/wnd/Documents/land_8k_16_rescaled_b145_pads.png`: 0 tears. Regenerate the paint if it changed (`tools/paint_maps.py`).
3. `python tools/reapply.py prepare --source-root C:/Users/wnd/Documents --server-dir C:/Users/wnd/Documents/github/cobblers-server`
   — 4 minutes; it must end `216 function file(s) checked, 0 with problems`.
4. `python tools/reapply.py plan` to see the steps and the 23 places.

**The run** (about 35 minutes to an audited world, then Distant Horizons)

| # | Step | Measured |
| --- | --- | --- |
| 1 | Confirm nobody is playing; take the coordination lock; stop the server | 2 min |
| 2 | Retire the world and the `.world` file to `cobblers-server-retired/<date>-pre-reexport/` | 3 min |
| 3 | `python tools/reexport.py --source-root C:/Users/wnd/Documents --old-world <retired world> --out-dir C:/Users/wnd/Documents/github/cobblers-server --name cobblers-10240 --world-file C:/Users/wnd/Documents/cobblers-10240.world --paint build/paint/manifest.json` | 14 min |
| 4 | Check: 484 region files, `seed_match: true` in its report | 1 min |
| 5 | `python tools/reapply.py install --server-dir <server> --world-dir <server>/cobblers-10240` (server stopped): the packs, `cobblers_height` and `cobblers_worldtree` into the world folder, and the disposable-only restore pack removed | 1 min |
| 6 | Boot the server | 30 s |
| 7 | `python tools/reapply.py run --server-dir <server>` | 4.5 min |
| 8 | Stop the server; copy the world folder (the audit tools refuse to read the live save) | 3 min |
| 9 | `python tools/reapply.py audit --server-dir <server> --world <the copy>` | 2 min |
| 10 | Boot; Distant Horizons pregen over the border; retire the client LOD cache | 10-60 min |
| 11 | The audit tour (`docs/world-building/AUDIT_TOUR.md`) | you |

**If the run stops.** It names the step and why. Re-run that step alone once (`--only R8`), then continue
(`--from R9`). Every step is idempotent. A pack donor that fails twice alone is a new problem: stop and diagnose (see
"Pack placements that fail").

**If the audit is not clean.** Re-run the named place's step on its own (`--only R8` rebuilds all places;
`/function cobblers:towns/<id>` and `cobblers:reapply/prep_<id>` rebuild one), stop, copy, and audit again. If it
does not clear, roll back.

**Rollback.** Nothing is deleted: the retired folder is a complete, bootable world. Stop, move the new world aside, put
the retired one back.

**Not in the run, on purpose**
- Spawn pools and suppression (R13): none are installed in the live world today; installing them is its own decision.
- Habitat Blocks (R11): 0 recorded. Waystones (R12): a fresh export has no stale `waystones.dat`.
- No traders beyond Brock's and Misty's regional stock (R14) until the badge-gated stock lands.

**Known costs of doing it**
- Ore and underground-water placement is re-rolled, so any ore survey is stale afterwards.
- Elder and grove sites are re-picked deterministically; individual trees may move.
- Player inventories and Pokédex data carry in `playerdata/`; anything built by hand is lost (nothing has been).
- The Distant Horizons client cache has to be cleared, or players see the old terrain at distance.

## 2026-09-17: dry run of the whole procedure on a staging export

**Status: the commands ran on staging; the live world is untouched.** Full record: `experiments/EXP-024-reexport-dry-run/`. **Corrected 2026-09-21:** most of the checks below were command checks, and the builds they passed were missing 13,586 trees and 165 roof columns; see "Which earlier 'verified' results were command-checked" at the top.

| Step | Result |
| --- | --- |
| Export | to `cobblers-runtime-proof/dryrun/cobblers-dryrun`, 484 region files, `seed_match: true`, spawn (1461, 5306). The staging directory must exist first |
| R1 | `cobblers_height` and `cobblers_worldtree` re-installed into the world folder and enabled |
| R2 | cavern rebuilt; the cherry-grove biome applied on a fresh export for the first time |
| R3 | world tree: column top y512, above the vanilla 319, so the height pack is loading |
| R4-R5 | grove (33,545 oak logs) and the 48 elders |
| R6 | 16 maze tiles; 157 of 158 corridor points clear at eye height; sapling seated at ground y124 as recorded |
| R7 | hometown re-placed: 0 gaps in 1,670 columns, one waystone |
| R8-R9 | gym1 and gym2 prep; **Brock's gym re-placed from the installed pack** (2,712 blocks, 20 block entities, substitutions exact) |
| R10 | islet: 400 columns, y63-70, all above sea |
| Not covered | Distant Horizons pregen, a client flight, spawn-pool installation, and any Habitat Block (none recorded) |

**Two blockers are gone:** Brock's gym now has a rebuild path that needs no local template, and the braided maze
forest has been re-applied after an export and checked.

## 2026-09-16: the Glacial Tear creek, and the first built interiors

**Status: exported, built in, checked, pregenerated.**

| Step | Result |
| --- | --- |
| Heightmap | `fd0db59b…` on river cut `f5ff054e…`: the major river starts on the trough floor, so the creek is back (see [`RIVERS.md`](RIVERS.md#the-major-river)) |
| Retired | `cobblers-server-retired/2026-09-16-pre-creek/` |
| Export | 2,255 s (tests were running beside it), `seed_match: true`, 484 region files |
| Hometown | **re-placed, not copied across.** The templates changed (concrete substituted), so placing again applies the fix and seats the buildings on the new ground: 0 gaps in 36 corners and 1,670 columns |
| Mods | WorldEdit 7.3.8 added and loading beside Axiom 6.0.5 |
| Built | the Displaced City cavern, the Foothill Woods grove, and terrain prep for gym towns 1 and 2: [`BUILT.md`](BUILT.md) |
| Distant Horizons | pregen over the whole border |

**The town's buildings are no longer donor-concrete.** `data/spawn_block_policy.json` records the substitution;
the placed Pokémon Center and Mart now carry `moarconcrete:*_concrete_texture`, so Varoom and Revavroom no longer
have a base block in any town.

## 2026-09-15 (second and third): hillside relief, seated hometown, major river head

**Status: exported twice, both checked in the region files and over RCON.** Each export was followed by a
Distant Horizons pregen.

| Step | Relief export | River-head export |
| --- | --- | --- |
| Heightmap | `217d411c…` (relief) | `924253ad…` on river cut `6b6352bc…` |
| Corruption check (`heightmap_check.py`) | ok: 0 tears, 0.39% multiples of 257, 0 duplicate rows | ok, same |
| Retired | `cobblers-server-retired/2026-09-15-pre-relief/` | `cobblers-server-retired/2026-09-15-river-head/`, with the previous cut and relief files and `rivers.json.before` |
| Export | 865 s, `seed_match: true`, `.world` `f825eded…` | 878 s, `seed_match: true`, `.world` `25b74090…` |
| Hometown | copied in (312 chunks) | copied in from the re-seated town (312 chunks) |
| World checks | tread CV in 2048-block crops: 0.31 → 0.56 (north mountains), 0.23 → 0.43 (Pallet) | no water above y100 within 500 blocks of (2583, 1546) except the lake at y119; 508 river stations at 16-block spacing, 0 bed or water rises |
| Distant Horizons | pregen complete in 7 minutes | pregen started |

**The hometown between the two exports.**
- **Restoring the ground:** the placed town was wiped back to pristine terrain by copying chunks from the sculpted
  export kept before its first copy (`2026-09-15-pre-sculpt/sculpted-export-before-transplant`). Terrain in the
  hometown rectangle is identical in every export since the sculpt.
- **The seam:** outside the rectangle, the two exports differ by 457 blocks in the 8-block strips around it. About
  170 are leaves or logs of a few trees; the rest is underground water pockets.
- **Re-placing:** the town was placed again with the seating placer. `waystones.dat` was cleared of hometown
  entries before boot. The original files are `2026-09-15-pre-relief/waystones.dat.before-*`.

**Distant Horizons.**
- **After the cache move:** the white terrain and hard-edged coloured wedge seen on the flight were Distant
  Horizons rebuilding. The client cache had been moved away at 08:03. A new one was created at 08:12 and was
  343.5 MB at its last write (08:28), against the server's 626 MB of LOD data, so the client had received about
  half of it.
- **This time:** the client cache was moved again after the relief export. None existed at the river-head export,
  so the next join rebuilds from scratch again.

## 2026-09-15: sculpted coasts and massifs, the hometown placed

**Status: exported, hometown carried across, checked over RCON, pregenerated.** Nobody had built in the
hometown, so the copied chunks are the placement as the script left it.

| Step | Result |
| --- | --- |
| Retire | Server stopped (0 players). World and `.world` moved to `cobblers-server-retired/2026-09-15-pre-sculpt/` |
| Export | `reexport.py` with an absolute `--out-dir`; 887 s; 484 region files; `seed_match: true`; spawn (1461, 5306); `.world` sha256 `cd6439ea…` |
| Hometown | `transplant_chunks.py` over x1376-1567, z4976-5391: 312 region chunks, 37 entity chunks, 12 poi chunks. The untransplanted export is kept beside the retired world (`sculpted-export-before-transplant/`) |
| Server | Boots, no chunk load errors. `level.dat` spawn is 1461 118 5306 |
| Checked over RCON | Waystone halves at (1467, 118/119, 5286); main-street path at spawn; donor roof slab at (1482, 129, 5244) |
| Surface against the heightmap | Caldera floor y104 against 104.0; great-cone crater 178 against 177.7; Mt Vessu 201 against 200.0; NE dome 197 against 197.5; Scar pad 195 against 194.0; spawn 117 against 116.6. The top block sits on the heightmap value, rounded up |
| Distant Horizons | `dh pregen start minecraft:overworld 4096 4096 320`, complete in 7.5 minutes |
| Client LOD cache | `local+ho` moved to `…/2026-09-15-pre-sculpt/client-distant-horizons-cache/` (the client was closed) |

**Found:** the donor Pokémon Center carries its own `waystones:mossy_waystone` at (1449, 122-123, 5256). It is a
second, unlocked waystone in the hometown.

**Not checked:** how the coasts, cliffs, cones and town read in game. That is the flight.

The preparation notes follow.

**What is ready:**
- **Heightmap:** `land_8k_16_sculpted.png` (`19abdd39…`), a sculpt of the river cut (`60b241d1…`). Design and
  numbers: [`SCULPT.md`](SCULPT.md).
- **Measurements:** cells and regions re-measured.
- **Paint:** repainted on the sculpted terrain. Shore materials follow the coast class, cold shallows take
  gravel, and scree bands are painted. 77,750 objects.
- **Checks on the repaint:** spawn tags 98.85% and 98.17%. Landmark sightlines: Great Oak 21/37, Sentinel 33/81,
  Patriarch 66/155, Cherry Elder 61/160, Weeping Elder 29/144.
- **Spawn:** `world.json` `export.spawn` is (1461, 5306), the hometown's main street.

**The live world already has the hometown and its spawn** (`place_town.py`, run on the `6ca95bdc` export).

**Plan when approved:**
1. Stop the server. Retire the world to `cobblers-server-retired/2026-09-15-pre-sculpt/`.
2. Run `python tools/reexport.py … --out-dir <absolute server dir>` (a relative path resolves against
   WorldPainter's folder).
3. Carry the hometown across. The sculpt left the built area untouched, so its chunks fit the new terrain:
   ```
   python tools/transplant_chunks.py --from <retired world> --to <new world> --blocks 1376 4976 1567 5391
   ```
   The box is 1376-1567 by 4976-5391, which is 12 by 26 chunks. The tool copies region, entities and poi byte for
   byte. It was byte-verified on retired worlds, but it has not been boot-tested.
4. Boot, check the town blocks and spawn in game, run the Distant Horizons pregen, and retire the client LOD cache
   if the client is closed.

## 2026-09-14 (fifth): foliage pass

**Status: exported, checked in the region files and in game, and pregenerated.** Same heightmap
(`60b241d1…`), rivers and lakes as the export below; the paint changed.

**Exported twice.** A separate test author found five placement faults in the first export. It was retired
unplayed to `cobblers-server-retired/2026-09-14-foliage-first-pass/`:
1. understory was mapped over water (the export itself had none there, because plant layers skip flooded
   columns);
2. the 3-block water clearance was only enforced on the 4-block grid;
3. long objects (fallen logs, boulders) had only four columns checked;
4. random rotation was not covered: 2x2 trunks turn about the painted column, so three quarters could stand
   on unchecked columns;
5. landmark-tree outposts added a 16-block settlement margin on top of their glades.

All five are fixed. The table and checks below are the second export: 78,887 objects, 102 fewer. The sample
windows and landmark sightlines came out the same.

**Why.** The paint's forests were too packed and too uniform: WorldPainter tree layers at one density per
preset. They are now placed per forest type as custom objects at computed positions, with five landmark
trees. Design, method and numbers: [`FOLIAGE.md`](FOLIAGE.md).

| Step | Result |
| --- | --- |
| Objects | `tools/foliage_objects.py`: 148 vanilla captures (19 groups) and 53 generated objects (17 groups) in `kits/structures/foliage/` |
| Paint | 35 object layers, 78,887 objects; understory, floor and `old_growth_pine_taiga` by forest type; spawn tags still 98.85% and 98.17% inside the Craters |
| Landmark sightlines | `tools/landmark_trees.py check` over terrain and the planned canopy: Great Oak seen from 21 of 37 first-leg points, Sentinel 27 of 81, Patriarch 66 of 155 on Victory Road, Cherry Elder 58 of 160, Weeping Elder 31 of 144 |
| Export | `reexport.py`. The pre-foliage world is in `cobblers-server-retired/2026-09-14-foliage/`, and the first foliage export (seed carried from it) in `…-foliage-first-pass/`. Second export 1,690 s; 484 region files, 2.28 GB; `seed_match: true`; `.world` sha256 `6ca95bdc…` |
| Rotation | 120 sampled 2x2 trunks (mega spruce, mega pine, ancient spruce) landed in all four quadrants around their painted column, every one inside the checked 3x3 |
| Server | boots; border 10240; `cobblers_spawn_tags` enabled |
| Distant Horizons | `dh pregen start minecraft:overworld 4096 4096 320`, complete; `data/DistantHorizons*` 602 MB |
| Client LOD cache | `local+ho` moved to the retirement folder again (the client had rejoined since the last export and was closed) |

**Checked in the region files: before and after, in 256 x 256 windows.** "Trunks/ha" counts connected log
columns two blocks above the ground. "Eye blocked" is the share of columns with a log or leaves at that
height.

| Window | Trunks/ha before | after | Eye blocked before | after |
| --- | ---: | ---: | ---: | ---: |
| Old growth (Peak Pond Hollow, densest giants) | 510 | 24 | 5.1% | 2.2% |
| Thicket (Northgate Isle) | 534 | 137 | 5.3% | 12.7% |
| Dark wood (the Wedge) | 960 | 66 | 9.9% | 3.0% |
| Birch plateau | 518 | 60 | 6.6% | 0.8% |
| Mossy broadleaf (Long Isle) | 397 | 51 | 5.7% | 3.1% |
| Foothill mixed | 294 | 61 | 5.1% | 3.7% |

- **Landmark trees:** all five are in place with every log and leaf block of their templates. Crown tops are
  at y143, 205, 177, 170 and 116.
- **Old-growth floor sample:** podzol, coarse dirt and moss, no grass block.

**Checked in game:**
- `minecraft:leaf_litter` survives chunk load (VanillaBackport);
- the Sentinel's trunk is at (3264, 130, 1008);
- `execute if biome … minecraft:old_growth_pine_taiga` passes at two old-growth positions.

**Not checked:** how the forests read from inside and at distance. That is the flight.

## 2026-09-14 (fourth): the missing tarn

> Superseded by the export above (same terrain, repainted forests). That world is in
> `cobblers-server-retired/2026-09-14-foliage/`.

**Status: exported, checked in the region files and in game, and pregenerated.**

**Why.** On the flight, the small lake at the top of the map had no water. It was not one of the
eight painted lakes, which all held water at their levels. It was a closed hollow the annotation
missed, so it never got a `water_body`.
- **What it is:** a hollow 23 blocks deep at the head of the dry ravine above Peak Pond.
  - Floor y105 at (3376, 921); spill y128.3 at (3289, 848); 0.042 km² at the spill.
- **What the old world held there:** 0 water columns of 41,819.
- **Now:** `ravine_head_tarn` in `landmarks.json`. It is a lake at y127, one block below its
  spill, the same rule as every other lake.
  - The polygon wets exactly the hollow below y127, 29,872 columns on the heightmap, and nothing
    outside it.

| Step | Result |
| --- | --- |
| Rivers | `grade_rivers.py plan`: one course added, `ravine_head_tarn_outflow`, 401 blocks north to the coast, cut up to 2.0, 4 wide, gravel. No existing course or the major river changed. `peak_pond_creek_from_high_end`, never cut (it needed 22.5), is gone: the tarn now drains that end |
| Cut | `cut --replace`: sha256 `60b241d1…`. Against the previous cut, 2,786 columns changed, all in x3295–3337, z432–815; none raised. The previous file is in `cobblers-server-retired/2026-09-14-tarn/` |
| Re-measured | `cells.json` (sha only, no drift), `regions.json` measured blocks (Peak Pond hollow slope 61.6 → 61.4% flat); validator clean; 609 tests pass |
| Paint | tarn mask at y127; stream levels y126 → y62; `spawn_tag_pack.py --check-paint` unchanged (98.85%, 98.17%) |
| Export | `reexport.py`, old world from `cobblers-server-retired/2026-09-14-tarn/`; 1,818 s; 484 region files, 2.33 GB; `seed_match: true`; `.world` sha256 `a2d8e09e…`. The first attempt failed at once: `--out-dir ../cobblers-server` is resolved from WorldPainter's folder, so pass it absolute |
| Server | boots; `worldborder get` 10240; `cobblers_spawn_tags` enabled. In game at (3376, 921): y127 water, y128 air |
| Distant Horizons | `dh pregen start minecraft:overworld 4096 4096 320`, complete in 14 minutes; `data/DistantHorizons*` 654 MB; region files still 484 |
| Client LOD cache | `local+ho` moved to `cobblers-server-retired/2026-09-14-tarn/client-distant-horizons-cache/` (the client was closed), so the tarn and the Crags summits are drawn fresh |

**Checked in the region files:**
- **Tarn:** every column below y127, 27,810 of them, holds water at y127.
- **Stream:** 1,539 columns with ground below their planned level. 1,497 are at that level, 42
  are raised where the stream leaves the tarn, and 0 are dry.
  - Another 369 painted columns have ground exactly at the level, so they have no room for water.
    They are bank pixels.

**Other unpainted closed hollows**, from the same basin search on 8-block cells, deeper than 7
blocks. These are listed, not changed:

| Near | Depth | Spill | Area km² | Inside |
| --- | --- | --- | --- | --- |
| (2550, 2785) | 13.7 | y108 | 0.03 | no landmark |
| (1830, 4969) | 11.3 | y109 | 0.24 | no landmark |
| (4715, 3899) | 9.4 | y100 | 0.02 | no landmark, above Tilpey's west arm |
| (2819, 2365) | 8.6 | y109 | 0.22 | no landmark |
| (4369, 2860) | 8.4 | y77 | 0.02 | the Glacial Tear |
| (3779, 3707) | 8.3 | y90 | 0.49 | the Rift |
| (6682, 5487) | 7.4 | y134 | 0.05 | the Craters |

## 2026-09-14 (third): Crater-only volcanic biomes; pre-build checks

> Superseded by the export above (same paint, plus the tarn). That world is in
> `cobblers-server-retired/2026-09-14-tarn/`.

**Status: exported, pregenerated, and checked.** The heightmap and river cuts are unchanged from
the export below.

**Why it was re-exported.**
- **The tags:** the Mining Town's identity needs `#cobblemon:is_volcanic` and
  `#cobblemon:is_thermal`. Cobblemon 1.8.0 fills them only with Terralith, Biomes O' Plenty,
  Wythers and Darker Depths biomes, none of which is loaded.
- **The overlay:** `cobblers_spawn_tags`, built from `regions.json` `spawn_tag_overlays` by
  `tools/spawn_tag_pack.py`, adds `stony_peaks` and `savanna_plateau`, the Craters' two
  biomes.
- **The leak it had to fix:** 14% of `stony_peaks` was painted on the Crags summits. That
  band now paints `jagged_peaks`, so both tag biomes are 98–99% inside the Craters (the rest
  is region-edge rasterisation).

| Step | Result |
| --- | --- |
| Paint maps | regenerated with the Crags change; `spawn_tag_pack.py --check-paint`: `stony_peaks` 98.85% and `savanna_plateau` 98.17% inside the Craters |
| Export | the same `reexport.py` command, with the old world from `cobblers-server-retired/2026-09-14-biome-tags/`; export 835 s; 484 region files, 2.33 GB; `seed_match: true`; `.world` sha256 `dae3d5c5…` |
| Datapack | `spawn_tag_pack.py --install <server>/datapacks`. Global Packs force-loads `datapacks/`; the log shows "Found new data pack cobblers_spawn_tags, loading it automatically", and `datapack list enabled` includes it |
| Border | 10240 |
| Distant Horizons | `dh pregen start minecraft:overworld 4096 4096 320`, complete in 12.5 minutes; `data/DistantHorizons*` 659 MB; region files still 484 |

**Tags checked in game** with `execute if biome` on force-loaded painted chunks. `locate biome`
is no use here: it consults the world generator's noise biomes, not the painted chunks.

| Position | Result |
| --- | --- |
| Mining Town (6633, 139, 5716) | `stony_peaks`; volcanic yes, thermal yes; volcanic at y60 underground too |
| Crater rim (5913, 111, 5071) | volcanic yes, thermal no (as designed) |
| Crags summit (3541, 164, 1323) | `jagged_peaks`; volcanic no |
| Crags grove (3295, 128, 1402) | volcanic no |

**Not checked:** that Cobblemon actually spawns volcanic or thermal species there. That is an
encounter-table matter, still deferred.

### Pre-build checks on the exported world

**1. Displaced City depth.** Full columns under the 200 × 200 cavern footprint were read from
the region files.
- **Bedrock** is at y−64 under all 40,000 columns.
- **The y32–72 band** is 98.3% solid: stone, granite, andesite, diorite, dirt and gravel
  pockets, coal and iron ore, with 884 air cells.
- **Rock over a y72 ceiling:** 24 blocks at its thinnest, 31 at the median.
- **The spec stands.**

**2. Surface against the heightmap.** A full-map `world_heights extract` and `compare` on the
previous export; the terrain is unchanged in this one.
- **Chunks:** all 262,144 present.
- **Land:** 99.10% exact and 99.94% within 1 block. The rest is WorldPainter's rounding and
  small plants.
- **Seabed:** 99.9999% exact.
- **First pass misreported this:** it showed about 10 million land columns 5 blocks high. That
  was tree canopy counted as ground; `world_heights.py` now treats logs and leaves as cover.
- **Below sea level without water:** 160,609 columns, almost all shoreline, where heightmap
  y61.6–62 rounds to a y62 ground block.

**3. Rivers and lakes.** Every cut course compared with its paint level map.
- **Planned water columns:** 95,798.
- **At the planned level:** 98.1%.
- **Raised:** 1.9%, where a course meets a lake or another course; water is only ever raised.
- **Dry or lower:** 0.
- **Lakes:** at their levels (Tilpey 77, Shrew 106, Arrow 100 and so on).

**4. Earlier paint issues.** A scan of all 451,584 saved chunks, including the margin.
- **Coastal overhang:** fixed. There are 0 log or leaf blocks in sea water, and 0 ice or snow at
  sea level over water.
- **The old grass name:** WorldPainter writes `minecraft:grass` (1,250,087 blocks), the
  pre-1.20.3 name.
  - The chunks carry DataVersion 2860, so the server upgrades them to `short_grass` on load.
    In game, `execute if block … minecraft:short_grass` passes on the scanned positions.
  - Only Distant Horizons, which reads raw region files, logs "Unknown registry key …
    minecraft:grass". The LODs miss those tufts, which is invisible at LOD distance.
  - **No repaint is needed for it.**

**Retired, not deleted,** to `cobblers-server-retired/2026-09-14-biome-tags/`: the previous
`cobblers-10240` world and `cobblers-10240.world`.
- **The client LOD cache was left in place,** because the game was running. Only the Crags'
  summit colour differs from what it holds. Clear it in Distant Horizons if that band looks
  stale.

## 2026-09-14 (second): river-cut terrain, rivers filled

> Superseded by the export above (same terrain, the Crags repainted). That world is in
> `cobblers-server-retired/2026-09-14-biome-tags/`.

**Status: exported and pregenerated for Distant Horizons.** No player has been in it yet.

| Step | Result |
| --- | --- |
| Heightmap | `land_8k_16_eroded_rivers.png`, sha256 `861d10ac…`: the carved revision with graded rivers, catchment-sized channels and the major river's valley cut in by `tools/grade_rivers.py` ([`RIVERS.md`](RIVERS.md)). Same import line |
| Re-measured | `data/cells.json` (no drift), `data/regions.json` measured blocks (`tools/region_measure.py`); validator clean |
| Paint maps | `python tools/paint_maps.py --source-root <source> --out build/paint`. Adds per-column water for all 10 cut courses, bed and bank material, river biome; ravines keep gravel floors |
| Export | the same `reexport.py` command, with the old world from `cobblers-server-retired/2026-09-14-rivers/` |
| WorldPainter | paint applied; save 23 s; export 764 s; 484 region files, 2.33 GB; `.world` sha256 `c0c716bf…` |
| Water | lakes as before. Rivers, raised per column: major river trunk 41,804 columns, Viltri's Path 12,747, Watering Hole outflow 13,820, Tilpey outflow 7,246, and six smaller courses |
| Seed | carried; `seed_match: true` |
| Border | `worldborder get`: 10240 |
| Distant Horizons | `dh pregen start minecraft:overworld 4096 4096 320`, complete in 7.5 minutes; `data/DistantHorizons*` 667 MB; region files still 484 |

**Checked in the region files** (`world_heights.extract` on four stretches, 37,601 planned water
columns):
- **Dry columns:** 0.
- **At the planned level:** 96–100%.
- **The rest** are 1 block higher, inside Lake Tilpey's basin outline, where the lake's level
  raises them.

**Retired, not deleted,** to `cobblers-server-retired/2026-09-14-rivers/`:
- the previous `cobblers-10240` world, with its DH stores;
- `cobblers-10240.world`;
- the client LOD cache `local+ho`, because the seed is unchanged and it would otherwise show the
  old terrain.

**Not checked in game:**
- how river water behaves at its 1-block steps and where it meets a lake;
- how the river biome spawns;
- whether the known `minecraft:grass` issue below still applies.

## 2026-09-14: carved terrain, painted

> Superseded by the export above. The world it describes is in
> `cobblers-server-retired/2026-09-14-rivers/`.

**Status: exported and pregenerated for Distant Horizons.** No player has been in it yet.

| Step | Result |
| --- | --- |
| Heightmap | the carved revision, sha256 `acdc3d1d…`, same import line as below |
| Paint maps | `python tools/paint_maps.py --source-root <source> --out build/paint` from `data/regions.json` presets and `data/landmarks.json` water bodies ([`REGIONS.md`](REGIONS.md) §6) |
| Export | `python tools/reexport.py --old-world <retired cobblers-10240> --out-dir ../cobblers-server --name cobblers-10240 --world-file <source>/cobblers-10240.world --paint build/paint/manifest.json` |
| WorldPainter | 2.27.1. 7,056 tiles with the margin. Paint applied in 11 s; save 21 s; export 672 s; 484 region files, 2.3 GB |
| Lakes raised | Tilpey y77 (1.19 M columns), Shrew y106, Arrow y100, Marshy Marsh y100, Peak Pond y105, Lake Viltri y103, Mt Clay pond y119, Watering Hole y95 |
| Seed | carried; `level.dat` seed sha256 matches `48202407…`; `WorldGenSettings`, datapacks and game rules carried as before |
| Border | `worldborder get`: 10240 in the overworld and the Nether |
| Spawn | (3400, 3400) unchanged. It now lands on the floor of the Rift's west spur, about y96 |
| Distant Horizons | server generation stays off. LODs built from the exported chunks with `dh pregen start minecraft:overworld 4096 4096 320`: complete in 6 minutes, 673 MB, and region files still 484 (nothing generated). The client LOD cache for this server was moved out, because DH keys it by seed |

**Spot check** of 8 region files (craters, dunes, glacier, Shrew Lake, marsh, Viltri Woods,
Pine Isles, the Tri Peaks):
- basalt, blackstone and magma, sand and cactus;
- snow layers and snow blocks;
- mud;
- oak, birch and spruce logs;
- sweet berry bushes, azalea, tall grass;
- raised water.

**Known issues in this export:**
- **`minecraft:grass` blocks.** 25,754 of them in the sample. They do not come from the plant
  sets, which avoid "Short Grass"; WorldPainter itself writes the old block name.
  - *Corrected 2026-09-14:* the earlier note here said those columns load without it. That was
    wrong. The chunks carry DataVersion 2860, so the server upgrades the name to `short_grass`
    on load, which was checked in game.
  - Only Distant Horizons, which reads raw region files, warns.
- **Coastal paint overhang.** The maps were generated before a fix: sub-region polygons
  overhanging the coast could put tree density, plants and frost on sea columns. The fixed tool
  clears all three on sea and on flooded lake columns. It applies from the next repaint.
- **Not yet checked in game:** how painted trees look, whether any grow in water, and how
  lakes behave when their water updates.

**Retired, not deleted,** to `cobblers-server-retired/2026-09-14/`:
- the unpainted `cobblers-10240` world, with its DH stores;
- `cobblers-10240.world`;
- the client LOD cache `local+ho`;
- an aborted partial export.

The earlier 2026-09-13 export is described below.

---

**Status (2026-09-13): done, verified, stopped before painting.**

The server world is now `cobblers-10240`, exported from the canonical heightmap. Nothing is
painted or carved: the terrain is the heightmap and nothing else.

## 1. What was done

| Step | Result |
| --- | --- |
| a. Ocean depth mapping | **Applied.** WorldPainter's script API and GUI only take whole-number world levels, so 10.093 cannot be entered. The same straight line was written as image level −32.125 → y10 and 65278 → y200, using WorldPainter's own `HeightMapImporter`. At image level 0 it gives y10.0935. No derived heightmap was needed, and the 4.3% shift from `low_out 10` was not accepted |
| b. Seed | **Carried over.** The runner passes it to WorldPainter through the environment only. After export the new `level.dat` seed matches the old one by sha256 (`48202407…`). WorldPainter had written its own overworld preset (`large_biomes`) and per-dimension generator seeds, so the old `WorldGenSettings` was copied in whole. Overworld, Nether, End and the mod dimensions now carry the old generators exactly |
| c. Heightmap import | WorldPainter reported **bit depth 16**, 8192×8192, unsigned, no alpha, value range 0..65535 (`land_8k_16_eroded.png`, sha256 `526fe220…`) |
| d. Border | **10240 × 10240, centre 4096,4096.** Written into `level.dat` by WorldPainter. The server reports "10240 block(s) wide" in the overworld, Nether and End. The export is a full overwrite: a new world, not a trim. None of the old world's chunks or its 62 structure starts exist in it |
| e. `world.json` | `heightmap.status` "ok", sha256 recorded, import block updated. The validator's `cell-terrain` and `spatial` checks now **execute**: 0 errors, 0 skipped |

**Export geometry:**

| | Blocks |
| --- | --- |
| Landmass (heightmap) | 0..8191 |
| World border | −1024..9215 |
| Exported canvas | −1280..9471 (484 region files, 451,584 chunks, 2.2 GB) |

- **The 256-block ring outside the border is unreachable ocean.** It exists so chunks loaded
  within view distance of the border already exist, and nothing ever generates beyond the
  wall.
- **Carried from the old world's `level.dat`:** `WorldGenSettings`, `DataPacks` (Terralith,
  Sinnoh, Johto and Hoenn stay disabled), `GameRules`, difficulty (hard), game type,
  commands flag.
- **Spawn:** (3400, y122, 3400), as before. The old world's spawn was at the same x,z.

**WorldPainter defaults** that apply because nothing was painted:
- the default theme (grass, beaches near water, stone mix below);
- the **Resources layer applied everywhere**, which places vanilla ores;
- no caves or chasms;
- Minecraft population off: chunks are written `full`, with no features or structures.

**Reproduce:**
```
python tools/reexport.py --old-world <old world> --out-dir ../cobblers-server --name cobblers-10240 --world-file <source>/cobblers-10240.world
```
The WorldPainter project is saved as `cobblers-10240.world` next to the heightmap (111 MB).
It is the file future painting starts from.

## 2. Verification against the exported world

Measured from the region files, not the heightmap: `tools/world_heights.py extract`, then
`compare` against the heightmap at the new mapping.

### Chunks

| | Count |
| --- | --- |
| Chunks expected in the canvas | 451,584 |
| Present, all status `full` | 451,584 |
| Saved outside the canvas | 0 |
| Columns without ground | 0 |

### Land elevation: did it shift?

- **No.** Across all 44.5 million land columns, WorldPainter's height matches the
  heightmap's float height rounded to the nearest block in 99.09% of cases, and every
  column is within one block.
- **Against the previous mapping (40/200):** of 51.3 million columns above the old y40
  floor, 99.21% are identical, 404,292 are one block higher, 204 one lower, and 1 column is
  two higher.

| Where the +1 blocks are | Columns | Why |
| --- | ---: | --- |
| Clipped summits at **y201** | 393,236 | WorldPainter does not clamp at the top of the line. Source values above 65,406 continue past y200 to y200.75 and round to y201. The design clamp was y200 |
| Elsewhere | about 10,000 | rounding at exactly half a block |

### Seabed: does it match the proposal?

**Yes, block for block.** Every one of the 22.6 million columns below sea level matches the
heightmap prediction exactly.

| Open sea (region plan sea mask) | Before (y40 floor) | Proposal | **Export** |
| --- | ---: | ---: | ---: |
| Median seabed | y40 | y21.5 | **y21** (whole blocks) |
| At or below y20 | 0% | 46.9% | **48.0%** |
| At or below y30 | 0% | 63.6% | **64.3%** |
| Sitting on exactly y40 | 75.9% | — | **1.2%** |
| 10th / 90th percentile | 40 / 57 | 10 / 53 | 10 / 53 |

- **The margin inside the border** is a flat seabed at y10 with water to y62, on all 48.5
  million columns.
- **Below sea level, 98.95% of columns hold water up to y62.** The rest are columns whose
  float height rounds up to y62 itself.
- **No water sits above sea level.**

### Clipped summits

| | Share of land |
| --- | ---: |
| Heightmap at or above the y200 ceiling (source ≥ 65,278) | 0.93% |
| Export at y200 or y201 | 0.96% |
| Export at y201 | 0.88% |
| Source pixels at full scale 65,535 (all columns) | 0.34% |

**The summits are still flat, now one block higher.** The top of the line maps full scale to
y200.75, so the summits sit at y201. `world.json` keeps the y200 clamp as the design value.
Measuring the summit plateaus from the world, not the heightmap, reads y201.

### The border holds, and nothing generates outside it

**On a headless boot with `--world cobblers-10240`:**
- `worldborder get` gave 10240 in the overworld, `the_nether` and `the_end`, before and after
  a full save.
- Datapacks came up exactly as carried: 57 enabled; Terralith, Sinnoh, Johto and Hoenn listed
  as available but not enabled.

**Scanned after the server was stopped:**
- **Canvas:** all 451,584 chunks inside, **0 outside**.
- **Border:** 409,600 chunks inside. The 41,984 outside are exactly the pre-written buffer
  ring, with 0 structure starts.
- **No Nether or End chunks were created.** `DIM-1` and `DIM1` hold only DH data folders.
- **The server's chunk upgrade changed nothing.** A second extraction after the boot, DH
  pregen and save matches the pre-boot extraction: 0 ground columns and 0 water columns
  differ. All 451,584 chunks are still `full`.

**Distant Horizons:**
- Server-side distant generation is now **off**: `enableServerGeneration = false` in
  `config/DistantHorizons.toml`, with a backup beside it. DH ignores the world border, and with
  generation on it would generate real chunks up to 4,096 chunks around a player.
- LODs were built from the exported chunks with `dh pregen start minecraft:overworld 4096 4096
  320`: 7 minutes, 561 MB. It generated nothing outside the canvas, as the scan above shows.
- Clients sync those LODs when they join.
- **Not verified:** a player walking or flying into the wall. The boot was headless.

## 3. Changes outside the repository

| Path | Change |
| --- | --- |
| `cobblers-server/cobblers-10240/` | new world |
| `cobblers-server/server.properties` | `level-name=erosion-land-8k` → `cobblers-10240` (one line; backup `server.properties.pre-cobblers-10240`) |
| `cobblers-server/config/DistantHorizons.toml` | `enableServerGeneration = false` (backup `.pre-reexport-20260913`) |
| `Documents/cobblers-10240.world` | new WorldPainter project |
| `cobblers-server-retired/2026-09-13/erosion-land-8k/` | **the old world, moved here** with its Distant Horizons stores (1.7 GB) |
| `cobblers-server-retired/2026-09-13/client-distant-horizons-cache/` | the client LOD cache from the Modrinth profile "Fabric 1.21.10" (116 MB) |

**Why the client cache was moved:** DH names a server's LOD folder from the seed, which is
unchanged. Left in place, the client would have drawn the old terrain in the distance.

**Retired, not deleted.** Permanent deletion is left to you:
```
Remove-Item -Recurse -Force "C:\Users\wnd\Documents\github\cobblers-server-retired\2026-09-13"
```
Player data in the old world (inventories, Pokédex, Cobblemon party data) went with it. The
new world has none.

## 4. What the flight will show that is not a decision yet

- **The rift floods where its floor is below y62.** That is 917 columns, 783 with water.
  WorldPainter floods everything below sea level. The landmark's policy is `water: never`,
  with the treatment still undecided.
- **The rest of the unpainted defaults:**
  - summits at y201;
  - vanilla ores everywhere (the Resources layer);
  - grass on all land and beaches at the waterline;
  - no biomes painted: WorldPainter's default applies;
  - no trees or features.
- **The margin** is a flat y10 plain to the wall. The seabed pass is not built.
- **`exp013-structures`** is still in the server folder. It was built from the old world and
  is not the world the EXP-013 D/E session will use.
