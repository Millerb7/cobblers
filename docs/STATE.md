# Project state

## World facts

- **Authoring landmass:** 8,192 × 8,192 blocks at `x/z 0..8191`; the WorldPainter canvas is `x/z -1280..9471`.
- **World border:** 10,240 blocks square, centred at `(4096, 4096)`, with playable limits `x/z -1024..9215`.
- **Planning grid:** 8 × 8 square cells (`A1`–`H8`) at 1,024 blocks per cell; hexes are retired.
- **Vertical bands:** authored terrain is `y10..310`, sea level is `y62`, and the runtime overworld build range is `y-64..575`.
- **Current peaks:** terrain reaches `y310` (`data/world.json` `measured_ceiling_y`); the built world tree reaches `y535`, recorded separately as `built_ceiling`.
- **Canonical heightmap:** `land_8k_16_rescaled_b145_pads.png`, 8,192 × 8,192 16-bit grayscale, SHA-256 `a69df9e32b8ce4a4959f9ec1462618738367c36e90a38936ddb0271ba37a8313`: the rescaled `3eb0edee…` with the Scar and Frostpeak shrine pads re-pressed; every other column is bit-identical.
- **WorldPainter source:** `cobblers-10240.world`, SHA-256 `3906dc77352eadc385293ce43d307b963853ac9ef2ebfe753dd4e219c6b72490` (saved after the thinned-grass paint); it and the live world predate the pad re-press.
- **Live world:** `cobblers-10240` under the local `cobblers-server` runtime; `level.dat` reports spawn `(1461, 118, 5306)`, 484 overworld region files, and a matching 10,240-block border.
- **Runtime:** Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0+1.21.1, and Java 21; the latest live log reached `Done (2.659s)`.
- **Seed:** retained in the live `level.dat`, deliberately uncommitted, and identified only by SHA-256 `48202407c92bc5d07cd215b93f631b384a5f7dde58e993e7bc9f7365e03563f3`.

## What is built

- **World export:** 1 disposable/authoring overworld exists and is pregenerated as 484 region files; the live save is runtime state, not repository source.
- **Towns:** 1 of 30 planned towns is composed in blocks: Hometown/Pallet has 9 donor structures, roads, spawn, and 1 waystone, all 9 placements `verified` in `placements.json`.
- **Gyms:** 1 of 8 gym buildings exists: Brock's (a local-only Cobbleverse template) on gym1_town's prepared lot; Brock and Misty have ground-level street/plaza preparation.
- **Routes:** 0 of 9 critical routes is built as a finished road or event chain; all 9 exist as candidate polylines and 1,349 spawn boxes in `data/routes.json`, routed by `tools/build_routes.py` on the canonical heightmap with 0 sub-region holes.
- **Regions:** 21 regions and 62 sub-regions exist as authored data and WorldPainter paint inputs; they are not gameplay boundaries at runtime.
- **Terrain landmarks:** 27 are tracked in data with 22 marked built, 4 partial, and 1 planned; summits are re-measured on the canonical heightmap and water bodies are checked unchanged by the rescale, but the status labels themselves have not been re-judged.
- **Displaced City cavern:** 1 of 1 planned test caverns is excavated at `x3250..3449, z1650..1849`, with 1,940,550 blocks removed; the city inside it is 0 built.
- **Large trees:** 1 world tree, 7 giants, 52 elders, and 5 painted landmark trees exist; the Foothill grove contains 12 of those trees and 48 elders are distributed across 20 sub-regions.
- **Foliage:** the current WorldPainter project records 77,750 custom foliage objects generated from `data/foliage.json`.
- **Campaign content:** 0 trainers, 0 production side events, and 0 boss encounters are placed in the world.
- **Encounter data:** 62 of 62 sub-regions have weighted/leveled source rosters in `data/spawns.json`; `tools/compile_spawns.py` generates 9 route pool files over 1,349 boxes (6,866 entries) and 9 Habitat pool files into `build/datapacks/cobblers_spawns/`; 0 pools are installed and 0 placed Habitat Blocks are verified in-world. Of the authored per-route species lists, 8 species on Route 3 and 1 on Route 4 now have no sub-region on their route, because Route 3 no longer crosses Mt Clay or Mt Vessu.
- **Quest data:** 3 dialogue conversations and 2 quests exist as proposed source data; 0 have been compiled into or proven through a runtime dialogue system.
- **Structure catalog:** 254 structure records exist in `data/structures.json`; catalog presence does not mean a structure is placed.
- **Tooling:** 61 Python tools, 2 PowerShell server scripts, 37 pytest modules, and 15 experiment directories exist; each experiment's own result file defines what has actually run.
- **Stale inventory:** `docs/world-building/BUILT.md`, `NAVIGATION.md`, `TOWNS.md` and `SETTLEMENTS.md`, and the `docs/story/` documents listed in `docs/HANDOVER_CODEX.md`, still quote pre-rescale or pre-sculpt geometry.
- **Retired snapshots:** the retained recovery anchors `2026-09-16-pre-rescale` and `2026-09-17-pre-grass` both boot (copies booted 2026-09-16: Done, clean save, no errors beyond a live boot's); unique provenance heightmaps are kept in `cobblers-server-retired/2026-09-17-provenance-heightmaps/`.

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
- **Dialogue:** target native Cobblemon dialogue rather than KantoNPCs, with quest state stored in the progression registry.
- **Dialogue cursors:** store long-sequence position as first-class per-player state and persist it after each line or short segment.
- **Quest namespaces:** reserve progression gates as `flags.<id>` and side-quest fields as `quest.<quest_id>.<field>`.
- **Gastly escort:** each player owns and advances an independent Gastly escort; there is no shared-party quest state.
- **Crushed house:** house completion is shared world state, dialogue cursors and rewards are per-player, and Lena relocates after rescue.
- **Villain:** Giovanni remains gym 8 and a civil defender; the campaign villain is original rather than Giovanni or another existing Kanto villain.
- **Blaine:** place Blaine's gym in the overworld at the Craters, not in the Nether.
- **League:** place the League in the overworld at the Rift head, disable generated End copies, and reserve End access for postgame.
- **Surge's town:** re-sited off Mt Vessu to the foot of the Vessu-Clay saddle at `(2347, 1956)`, y124-133; Mt Vessu stays the landmark.
- **Route 1:** pinned through the built maze forest's main path (17 waypoints in `routes.json` `routing.mandatory_waypoints`), so it passes River of Shrews vale.
- **Leg 4 waypoint:** passes west of the Merian cirque at `(2640, 1180)` so the Displaced City stays at least 250 and the Merian hut 100-450 blocks off the critical path.
- **Flat pads:** the Scar and the Frostpeak shrine are re-pressed at their authored levels carried through the rescale curve (y280, y310) by `tools/press_pads.py`, not re-sited.
- **Compiled spawn pools:** generated build output from `tools/compile_spawns.py` into `build/datapacks/cobblers_spawns/`; no compiled pool is committed; each route's species list is authored in `data/spawns.json` `route_species_selection`.

## What is open

- **Pallet relocation:** decide whether the already composed Hometown/Pallet moves farther north; this blocks final town coordinates, Route 1's origin, and nearby event sites.
- **Route 1 middle feature:** choose and site the unnamed middle feature; this blocks the final Route 1 composition and side-event spacing.
- **Route 3 species:** re-author `route_species_selection` for Route 3, which now reaches only Lake Viltri Hollow and Foothill Woods; this blocks the chapter-3 availability curve.
- **Surge's view of the Scar:** decide whether the re-sited town must see the Scar (1,034 blocks away, unchecked); this blocks the Scar's narrative framing from Surge's town.
- **Snapshot cleanup:** the user runs the delete commands for the non-retained snapshots and boot-check copies (about 42.5 GiB); this blocks nothing technical.
- **Hometown waystone:** decide whether it starts unlocked or is earned; this blocks its final progression trigger.
- **Midpoint waystones:** decide whether routes receive none, post-gym unlocks, or discovery unlocks; this blocks final navigation data and retreat rules.
- **Gastly mansion details:** choose the donor/site, actors, rewards, levels, and final roster; this blocks implementation of that optional quest.

## What is blocked

- **Pads in the world:** the Scar and Frostpeak shrine re-press exists in the canonical heightmap only; the live world and the WorldPainter project predate it, so in-world flats are blocked on the next re-export.
- **Codex's documents:** `docs/story/` and `docs/world-building/TOWNS.md`/`SETTLEMENTS.md` quote pre-sculpt distances and the old Surge site; narrative acceptance of the new geometry is blocked on the revisions listed in `docs/HANDOVER_CODEX.md`.
- **Habitat replacement:** 9 native roster files are compiled, but runtime enforcement is blocked until Habitat Block placement, influence and persistence are proven in game.
- **Bounded suppression:** runtime exclusivity for curated route pools is blocked until EXP-012 proves default Cobblemon spawns can be suppressed inside a coordinate-bounded area without suppressing the outside world.
- **Dialogue delivery:** the 3 authored conversations and 2 quests are blocked on a compiler/runtime adapter from campaign JSON to native Cobblemon dialogue, commands, and persistent cursors.
- **Navigation runtime:** flag-driven waystones are blocked on an in-game proof of activation, locked-touch rollback, reconnect reconciliation, and Xaero behavior.
- **Generated gym copies:** the overworld Blaine/League decision is blocked from enforcement until the exact datapack overrides that suppress Nether/End copies are proven.
- **Pack foundation:** EXP-000 has server boot and one-client connection evidence but is blocked from completion on multiplayer and remaining world-critical/gameplay-critical functional tests.

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
| `data/spawns.json`, `data/spawn_suppression.json` | `datapack-content-dev` | Keep source rosters, per-route species selection and suppression proof status synchronized; native pools are generated by `tools/compile_spawns.py` into `build/`, never committed; installation requires the named runtime proofs. |
| Codex, 2026-09-16 | — | Codex paused all `data/` work while the canonical data was regenerated (branch `data/post-rescale-regeneration`). It can resume `docs/story/`, the world-building documents and `data/spawns.json` rosters now, and the rest of `data/` once that branch merges; the revision list is `docs/HANDOVER_CODEX.md`. |
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
