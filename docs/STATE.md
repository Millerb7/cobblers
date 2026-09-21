# Project state

## World facts

- **Authoring landmass:** 8,192 × 8,192 blocks at `x/z 0..8191`; the WorldPainter canvas is `x/z -1280..9471`.
- **World border:** 10,240 blocks square, centred at `(4096, 4096)`, with playable limits `x/z -1024..9215`.
- **Planning grid:** 8 × 8 square cells (`A1`–`H8`) at 1,024 blocks per cell; hexes are retired.
- **Vertical bands:** authored terrain is `y10..310`, sea level is `y62`, and the runtime overworld build range is `y-64..575`.
- **Current peaks:** terrain reaches `y310` (`data/world.json` `measured_ceiling_y`); the built world tree reaches `y535`, recorded separately as `built_ceiling`.
- **Canonical heightmap:** `land_8k_16_rescaled_b145_pads.png`, 8,192 × 8,192 16-bit grayscale, SHA-256 `5b9635676bb0d9bf3d5189d647e6dc154b974fb73ffe354c2070d6d24140d6fb`: the rescaled `3eb0edee…` with three `data/sculpt.json` pads pressed by `tools/press_pads.py` (the Scar y280, the Frostpeak shrine y310, Surge's shelf y174.4); every other column is bit-identical.
- **WorldPainter source:** `cobblers-10240.world`, SHA-256 `3906dc77352eadc385293ce43d307b963853ac9ef2ebfe753dd4e219c6b72490` (saved after the thinned-grass paint); it and the live world predate all three pads.
- **Live world:** `cobblers-10240` under the local `cobblers-server` runtime; `level.dat` reports spawn `(1461, 118, 5306)`, 484 overworld region files, and a matching 10,240-block border.
- **Runtime:** Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, and Java 21; the latest live log reached `Done (2.659s)`.
- **Seed:** retained in the live `level.dat`, deliberately uncommitted, and identified only by SHA-256 `48202407c92bc5d07cd215b93f631b384a5f7dde58e993e7bc9f7365e03563f3`.

## What is built

- **World export:** 1 disposable/authoring overworld exists and is pregenerated as 484 region files; the live save is runtime state, not repository source.
- **Towns:** 24 of 29 planned places are laid out. On the disposable world: Hometown/Pallet (9 donor structures, all `verified`), Brock's and Misty's towns; batch 1, approved 2026-09-21 (Koga, Sabrina, Blaine, Giovanni, the League); Erika's town and batch 2, approved as drawn (the Merian hut, the gorge hamlet, the Tableland stop, the Rift rim post, the Rift dig camp); and, drafted without the owner's review, Northlight, the Mining Town surface, the tea town, the Displaced City (redrawn on the cavern's benches: 42 houses, no Centre or Mart), Relic Island, Viltri Light, the jungle ruins and Sunset West (re-sited from the Sunset isle, which has no bay, to a river mouth on the strait's mainland shore). Surge's town and the Scar are authored and built only on the staging export `cobblers-dryrun3`, since the disposable world predates their pads. Every place with services has a Centre and a Mart except the Displaced City. On `cobblers-dryrun3` all 23 planned places audit plan-clean by result and all 24 verify at 0 floor gaps (EXP-026). The 7 regional-stock traders stand in Brock's and Misty's towns only (4 more are withdrawn); none anywhere else until the badge-gated stock lands; that a `NoAI` trader still trades is not tested in game. Nothing here is in the live world. Parked: the Frostpeak shrine (no plan). The 5 landmark trees need no plan.
- **Gyms:** 7 of 8 gym buildings stand on the disposable world and all 8 on the staging export `cobblers-dryrun3` (Surge's `cobbleverse:ltsurge` too), Cobbleverse templates placed by resource id, plus the Kanto League. Giovanni's redstone torch, which drew Rotom into a Ground gym, is a plain torch; its fossil machine still draws Rotom (an owner decision).
- **Routes:** 0 of 9 critical routes is built as a finished road or event chain; all 9 exist as candidate polylines and 1,408 spawn boxes in `data/routes.json`, routed by `tools/build_routes.py` on the canonical heightmap with 0 sub-region holes and no step over 35 degrees on any leg.
- **Regions:** 21 regions and 62 sub-regions exist as authored data and WorldPainter paint inputs; they are not gameplay boundaries at runtime.
- **Terrain landmarks:** 27 are tracked in data with 22 marked built, 4 partial, and 1 planned; summits are re-measured on the canonical heightmap and water bodies are checked unchanged by the rescale, but the status labels themselves have not been re-judged.
- **Displaced City cavern:** 1 of 1 planned test caverns is excavated at `x3250..3449, z1650..1849`; its seal now turns gravel and sand in the shell to stone, and its trees and light strings (17 and 6) keep clear of the town's plan. The city stands on the cavern's two benches and summit: the old road, two ring streets, 42 houses on levelled terraces (worst cut 5, worst fill 4), a summit square with a cairn and an eight-step stair, a gate at the surface mouth.
- **Large trees:** 1 world tree, 7 giants, 52 elders, and 5 painted giants exist (4 landmark trees and the demoted Weeping Elder); the Foothill grove contains 12 of those trees and 48 elders are distributed across 20 sub-regions.
- **Foliage:** the current WorldPainter project records 77,750 custom foliage objects generated from `data/foliage.json`.
- **Campaign content:** 0 trainers, 0 production side events, and 0 boss encounters are placed in the world.
- **Encounter data:** 62 of 62 sub-regions have weighted/leveled source rosters in `data/spawns.json`. `tools/compile_spawns.py` generates 9 route pool files (1,408 boxes, 7,066 entries), 62 sub-region files (2,033 boxes, 14,488 entries over 43.0 million blocks), 1 waterway file and 9 Habitat pool files. Until 2026-09-17 only the route corridors compiled, so 35 sub-regions reached nothing; and every entry said `grounded`, so 25 water species never appeared. Both are fixed and the sub-region rosters are observed in game at Lake Tilpey (EXP-025). Suppression now covers the sub-region polygons too, at 926 boxes and 3,841 MB of heap. 0 pools, blocks or suppression are installed in the live world.
- **Size variance:** two layers, no mod. Cobblemon's own intrinsic roll is widened to 0.8-1.2 in `modpack/config/cobblemon/main.json`, and `data/sizes.json` with `tools/size_outliers.py` makes roughly 1 wild Pokemon in 200 a notable individual, gated on headroom because collision boxes scale with `ScaleModifier` (EXP-025). Proven on the disposable world; whether a captured outlier keeps its size is not tested.
- **Quest data:** 3 dialogue conversations and 2 quests exist as source data; 1 (the Route 1 thirsty stranger, 44 nodes) compiles through `tools/compile_dialogue.py` and ran on the disposable world (EXP-022); 0 are placed in the live world.
- **Structure catalog:** 254 structure records exist in `data/structures.json`; catalog presence does not mean a structure is placed.
- **Tooling:** 80 Python tools, 2 PowerShell server scripts, 50 pytest modules, and 22 experiment directories exist; each experiment's own result file defines what has actually run. Every generated function holds the chunks it writes for its whole run (a function that releases chunks and then writes again is held whole) and splits fills over the block limit (`tools/function_limits.py`); all 216 the re-application installs pass. `tools/reapply.py` drives the whole re-application.
- **Stale inventory:** landmark-tree sightlines in `docs/world-building/FOLIAGE.md` and `LANDMARK_SIGHTLINES_POST_RESCALE.md` are a reproducible survey on `data/routes.json` legs and the canopy `tools/paint_maps.py` writes (sha256 `ce7da822…`); a different canopy hash means they are stale. Dated records (`TERRAIN_2026-09-14.md`, `SCULPT.md`, `VERTICAL_RESCALE.md`, `REEXPORT.md`, `TOWN_CANDIDATES.md`) keep pre-rescale levels and are labelled as such.
- **Re-export readiness:** ready to run, not run. `tools/reapply.py` re-applied everything on a fresh staging export (`cobblers-dryrun3`, EXP-026) with no stop in 4.5 minutes, and the result audit was clean: cavern roof 40,000 of 40,000, forest 46,051 of 46,052 trunks, world tree 1,380 of 1,380, islet 2,139 of 2,139, 23 of 23 places plan-clean, 24 of 24 at 0 floor gaps. The first staging run found trees on streets and gravel falling from the cavern roof, both fixed at the source. The live re-export has not been run; `docs/world-building/REEXPORT.md` is the runbook (about 35 minutes to an audited world).
- **Retired snapshots:** the retained recovery anchors `2026-09-16-pre-rescale` and `2026-09-17-pre-grass` both boot from copies (Done, clean save; all 43 error lines per anchor classified and also present in a live-world boot); retention, per-line classification and the user's delete commands are in `docs/world-building/SNAPSHOTS.md`.

## What is decided

- **Base and target:** preserve the Cobbleverse experience through an overlay while targeting Cobblemon 1.8.x on Minecraft 1.21.1 Fabric.
- **Live-world isolation:** agents check process/port and acquire `C:\Users\wnd\Documents\github\.cobblers-server-agent.lock` before any server-runtime access; agents never read `cobblers-server/cobblers-10240/`, and disposable worlds are seeded only from designated offline snapshots.
- **Spawn philosophy:** use curated exclusive pools on critical-path route corridors and keep the default Cobbleverse pool open in wilderness and postgame areas.
- **Map geometry:** use 1,024-block square planning cells, terrain-following region polygons, and no hex grid.
- **Vertical scale:** use the Option B rescale above `y145`, with authored terrain capped at `y310` and the runtime ceiling raised to `y575`.
- **World source:** commit reproducible heightmaps, WorldPainter sources, templates, data, and tools; do not treat the live save as source code.
- **Licensing:** only MIT-style (permissive) sources may be committed; anything else is used locally and gitignored, and every structure template needs a `kits/PROVENANCE.json` record, enforced by `python tools/validate.py --only template_provenance`.
- **Structure placement:** place campaign structures deliberately and do not enable donor packs as uncontrolled natural world generation.
- **Recognizable towns:** use CobblemonCityTowns first, then compatible licensed donor libraries, with minimal custom connectors and a donor manifest.
- **Navigation:** use waystones only for fast travel, with gym-clear progression flags controlling gym-town activation.
- **Dialogue:** native Cobblemon dialogue rather than KantoNPCs, compiled from campaign data by `tools/compile_dialogue.py`; quest fields and the cursor live in Cobblemon player data (`q.player.data()`, persisted per player); item checks use the vanilla item predicate run as the server; every give reports success and a reward claim depends on it (EXP-022: disconnect restore, bucket and bottle hand-over, reward once all pass single-player).
- **Dialogue cursors:** store long-sequence position as first-class per-player state and persist it after each line or short segment.
- **Quest namespaces:** reserve progression gates as `flags.<id>` and side-quest fields as `quest.<quest_id>.<field>`.
- **Gastly escort:** each player owns and advances an independent Gastly escort; there is no shared-party quest state.
- **Crushed house:** house completion is shared world state, dialogue cursors and rewards are per-player, and Lena relocates after rescue.
- **Villain:** Giovanni remains gym 8 and a civil defender; the campaign villain is original rather than Giovanni or another existing Kanto villain.
- **Blaine:** place Blaine's gym in the overworld at the Craters, not in the Nether.
- **League:** place the League in the overworld at the Rift head, disable generated End copies, and reserve End access for postgame.
- **Surge's town:** on a shelf pressed into the Tri Peaks - Mt Vessu south flank at `(1688, 1410)`, y174.4, sub-region `the_tri_peaks`; leg 3 climbs 81 blocks with no step over 35 degrees; Mt Vessu's summit is visible from town; site D `(2347, 1956)` is superseded.
- **Route 1:** pinned through the built maze forest's main path (17 waypoints in `routes.json` `routing.mandatory_waypoints`), so it passes River of Shrews vale.
- **Leg 4 waypoint:** passes west of the Merian cirque at `(2640, 1180)` so the Displaced City stays at least 250 and the Merian hut 100-450 blocks off the critical path.
- **Flat pads:** the Scar and the Frostpeak shrine are re-pressed at their authored levels carried through the rescale curve (y280, y310), and Surge's shelf is authored directly on the rescaled terrain (`pressed_y` 174.4), all by `tools/press_pads.py`.
- **Surge's signal array:** landmark `surge_signal_array` on a Mt Vessu shoulder at `(1928, 1248)`, y284; the Route 3 Nosepass signs aim at it from `(2186, 1606)`, inside the only stretch of leg 3 that sees its mast over the canopy (moved 18 blocks west of `(2203, 1609)` so the built elder at `(2236, 1622)` stands outside the 40-block clearing; mast margin 1.5 blocks, about 638 blocks of route remaining). The summit reveal at the shelf lip carries no quest beat.
- **Route 3 pond stop:** place `EVT-ROUTE3-CREEK-WOOPER` on the pond shore at `(2204, 1580)`, about 32 blocks from the relocated Nosepass signs; `SQ-G3-02` is cut and players are not sent back to this pond.
- **Measured town records:** off-path distance and `nearest_leg` (on `data/routes.json`) and every town's centre and footprint heights and slope (on the canonical heightmap, plus `built_ground` such as Relic Island's islet) are checked by `tools/validate_data.py` and rewritten only by `tools/measure_towns.py`, never trusted from records; landmark trees (sited to be seen from a leg) may stand 200 or more off the path, other outposts 250.
- **Route 3 and the Foothill grove:** leg 3 deliberately brushes the built grove and world tree (nearest trunk edge 29.5 blocks, no trunk or crown over the centreline), recorded on `route_03_misty_to_surge`'s `foothill_woods_grove` landmark; it is not a clearance fault.
- **Relic Island footprint:** the record is the islet's dry 20-block core `(1082-1101, 5522-5541)`, y63-70, all 400 columns above sea; the islet is not re-run or levelled.
- **Nosepass sightline:** the mast stays 12 blocks; a clearing extends 60 blocks along the line toward the array, 16 blocks wide, giving a 4.3-block canopy margin (hard build constraint on the sign site and in `EVT-ROUTE3-NOSEPASS-SIGNS`).
- **Weeping Elder:** demoted from landmark to an ordinary feature; it stays painted on its Lake Tilpey island with its glade, and is not an outpost or a viewpoint claim.
- **Visibility claims:** every claim that something can or cannot be seen is a measured record in `data/visibility.json`, re-measured by `tools/validate_data.py` and cited in its stating record as `visibility:<id>`; claims on 10 or fewer points or under 5% are marked fragile in the record.
- **Compiled spawn pools:** generated build output from `tools/compile_spawns.py` into `build/datapacks/cobblers_spawns/`; no compiled pool is committed; each route's species list is authored in `data/spawns.json` `route_species_selection`.
- **Route corridor exclusivity:** bounded exclusion, not global off: every inherited spawn file (1,729 paths, 5,195 entries) is re-emitted at its path with the route boxes snapped to a 16-block grid (637 boxes) as `anticonditions` by `tools/suppress_inherited_spawns.py` into `build/` (168 MB, never committed); Cobbleverse defaults stay live outside the corridors. EXP-012 (settled): corridor sample 54% → 97.6% curated with weights as authored, no measurable tick cost; at grid 16 about +3 s boot, +690 MB heap, +5 s `/reload`.
- **Habitat Blocks:** carry place identity: natural `ReplaceSpawns` replaces the ambient pool within `RangeOfInfluence` (edge measured at the configured 24); ranges must not overlap (overlap spawns nothing); blocks are placed from data by `setblock` + `data merge` and become active after one chunk reload; they survive restarts but not a re-export, so every campaign block is recorded in `data/habitat_blocks.json` (0 recorded), re-applied by `tools/habitat_blocks.py function` plus a restart in the post-export table in `docs/world-building/REEXPORT.md`, and checked by the validator's `habitat-blocks` check (overlap, pool, and presence in a stopped world copy via `--world-save`) (EXP-021).

## What is open

- **Spawn installation:** installing the route pools, the suppression pack and recorded Habitat Blocks in the live world waits on a server build step that regenerates the pack on mod, Cobbleverse or route changes, sited Habitat Blocks in `data/habitat_blocks.json`, and an independent review of `tools/suppress_inherited_spawns.py` and `tools/habitat_blocks.py`; this blocks live encounter content.
- **Pallet relocation:** decide whether the already composed Hometown/Pallet moves farther north; this blocks final town coordinates, Route 1's origin, and nearby event sites.
- **Route 1 middle feature:** choose and site the unnamed middle feature; this blocks the final Route 1 composition and side-event spacing.
- **Snapshot cleanup:** the user runs the delete commands for the non-retained snapshots and boot-check copies (about 42.5 GiB); this blocks nothing technical.
- **Hometown waystone:** decide whether it starts unlocked or is earned; this blocks its final progression trigger.
- **Midpoint waystones:** decide whether routes receive none, post-gym unlocks, or discovery unlocks; this blocks final navigation data and retreat rules.
- **Route 8 landmark:** whether Blaine to Giovanni gets a landmark tree; the candidate on file is (5216, 5024), seen from 38.5% of legs 5-8 (`data/foliage.json` `landmark_candidates`), a new decision, not a Weeping Elder rescue; this blocks nothing.
- **Gastly mansion details:** choose the donor/site, actors, rewards, levels, and final roster; this blocks implementation of that optional quest.
- **Live re-export:** ready to run from `docs/world-building/REEXPORT.md`; the owner starts and supervises it. It blocks Surge's town, the Scar and the Frostpeak shrine in the live world, and every town being real.
- **Giovanni's fossil machine:** its tank, analyser, monitor and a redstone block draw Rotom into the Ground gym; keep them and accept Rotom, or make the gym interior spawn-free. Blocks nothing.
- **Displaced City services:** drawn without a Centre or Mart (a summit town displaced underground, not a waystation); the owner confirms or asks for them. Blocks nothing.
- **Jungle ruins cache and Sunset West story coordinates:** the ruins' cache needs a reward chosen; `docs/story/` still places Sunset West at its first site (1716, 7298) and needs its owner to move it to (2660, 6490). Blocks nothing in the world.
- **Gym matchup sufficiency:** the coordinated audit is complete in `docs/story/GYM_SUFFICIENCY_AUDIT.md`; decide the proposed `20/25/30/35/40/45/50/55` leader curve, cap offset zero, and minimal placement/roster package before changing encounters or trainers.

## What is blocked

- **Pads in the world:** the Scar, Frostpeak shrine and Surge shelf pads exist in the canonical heightmap and on the staging exports; the live world and the disposable world predate them, so Surge's town, the Scar and the Frostpeak shrine wait for the live re-export, which is ready to run.
- **Dialogue delivery:** per-player dialogue is proven single-player (EXP-022); the two-player run is blocked on a second account, and the crushed-house conversations are blocked on a design for world-scoped quest fields, which the compiler refuses.
- **Navigation runtime:** flag-driven waystones are blocked on an in-game proof of activation, locked-touch rollback, reconnect reconciliation, and Xaero behavior.
- **Generated gym copies:** the overworld Blaine/League decision is blocked from enforcement until the exact datapack overrides that suppress Nether/End copies are proven.
- **Pack foundation:** EXP-000 has server boot and one-client connection evidence but is blocked from completion on multiplayer and remaining world-critical/gameplay-critical functional tests.
- **Every spawn test needs a player.** Cobblemon spawns around players only: with nobody connected, no Pokemon spawn anywhere, however long a world runs. An agent can place, resize, read and verify entities over RCON, but it cannot make the world produce a natural spawn. Plan a spawn observation as an appointment with somebody in game, five minutes standing still per site, rather than discovering the dependency mid-test. `/tp` the player, clear the area first, and census over RCON.

## File ownership

| Path | Owning agent | Protocol |
| --- | --- | --- |
| `data/world.json` | `world-content-dev` | World constants change only with matching source/runtime evidence. |
| `data/cells.json` | `world-content-dev` | Regenerate from the canonical world/grid inputs. |
| `data/regions.json` | `world-content-dev` | Other agents submit coordinates and failing intervals; only the owner edits polygons and regenerates dependents. |
| `data/towns.json` | `world-content-dev` | Other agents submit placement or story constraints; only the owner changes coordinates, status, footprints, or route distances. |
| `data/landmarks.json` | `world-content-dev` | Keep geometry and build status tied to world evidence. |
| `data/rivers.json` | `world-content-dev` | Regenerate with the terrain pipeline after canonical height changes. |
| `data/routes.json` | `world-content-dev` | Regenerate from canonical terrain and owner-controlled regions/towns; do not hand-edit derived geometry. |
| `data/sculpt.json` | `world-content-dev` | Terrain brushes require source hash and affected-site checks. |
| `data/placements.json` | `world-content-dev` | Record planned placements separately from verified in-world placement. |
| `data/foliage.json` | `world-content-dev` | Regenerate placement output from canonical terrain. |
| `data/structures.json` | `world-content-dev` | Catalog and donor-placement ownership; dependency audit is read-only review. |
| `data/dialogue.json` | `datapack-content-dev` | Content edits must reference fields declared in progression and quests. |
| `data/quests.json` | `datapack-content-dev` | Quest definitions never create a parallel mutable state store. |
| `data/spawn_block_policy.json` | `datapack-content-dev` | Policy changes require Cobblemon-format evidence and runtime proof. |
| `data/spawn_blocks.json` | `datapack-content-dev` | Generated/placement records must remain traceable to policy and world coordinates. |
| `data/progression.json` | `minecraft-systems-dev` | This is the sole registry for progression and quest state fields. |
| `data/checks/` | `test-author` | Store machine-checkable data validation outputs only. |
| `data/notes/` | `content-architect` | Store bounded source notes; promote settled state into this file. |
| `data/README.md` | `content-architect` | Keep the data index aligned with files that actually exist. |
| `data/habitat_blocks.json` | `world-content-dev` | Every placed Habitat Block has a record; placements are re-applied after every export and checked by `habitat-blocks`. |
| `data/spawns.json`, `data/spawn_suppression.json` | `datapack-content-dev` | Keep source rosters, per-route species selection and suppression proof status synchronized; native pools are generated by `tools/compile_spawns.py` into `build/`, never committed; installation requires the named runtime proofs. |
| Future `data/events.json`, `data/trainers.json`, `data/gyms.json` | `datapack-content-dev` | Create only after the corresponding schema/mechanism is accepted. |
| `kits/` | `world-content-dev` | Source-controlled templates, schematics, and structure assets only; the live save never enters this path. |
| `derived/`, `build/` | `world-content-dev` | Regenerated outputs and their indexes only; do not hand-edit generated artifacts. |
| `modpack/datapacks/` | `datapack-content-dev` | Implement only accepted data formats and mechanisms. |
| `modpack/resourcepacks/`, `modpack/overrides/` | `datapack-content-dev` | Keep authored client assets separate from upstream donor files. |
| `server/`, `modpack/config/` | `minecraft-systems-dev` | Runtime and server configuration changes require a boot or functional test. |
| `modpack/manifest/`, `modpack/mods/`, `base-pack/inventory/` | `dependency-auditor` | Owner is read-only: it proposes exact manifest/inventory updates and the orchestrator applies them after review. |
| `base-pack/cobbleverse/` | `dependency-auditor` | Read-only upstream reference; no agent edits it in place. |
| `tools/`, `tests/` | `test-author` | Feature implementers provide contracts; a separate test-author owns validators and tests. |
| `experiments/` | `content-architect` | The implementing role supplies evidence; the owner keeps status/result records consistent and QA remains read-only. |
| `docs/vision/`, `docs/architecture/`, `docs/mechanics/`, `docs/decisions/`, `docs/story/`, `docs/agent-system/` | `content-architect` | Specialists propose changes; the owner integrates cross-system decisions. |
| `docs/research/` | `cobblemon-researcher` | Research remains read-only evidence; the orchestrator applies accepted documentation changes. |
| `docs/world-building/` | `world-content-dev` | Keep world claims synchronized with canonical data and measured saves. |
| `.agents/`, `.codex/`, `.claude/`, `AGENTS.md`, `CLAUDE.md` | `content-architect` | Agent-system edits must preserve both Codex and Claude workflows. |
| Root `README.md`, `.gitignore`, `.gitattributes` | `content-architect` | Keep repository identity and tracking policy aligned with the actual layout. |
| `docs/STATE.md` | `content-architect` | Every session reads it first and reconciles affected lines before ending; other owners submit verified one-line changes and never add history. |
| Any cross-owner change | Owning agent named above | One agent edits each file; dependent owners consume the committed result or coordinate a sequential handoff. |
