# Repository audit

**Audit date:** 2026-09-16
**Audit baseline:** `origin/main` at `da50e0b`, plus every registered worktree and the local `cobblers-server-retired/` store.
**Method:** static reachability/import searches, tests and documentation references, Git tracking/ignore checks, worktree ancestry/status checks, and filesystem size/date inventory. No files or worlds were deleted, moved, opened by Minecraft, or modified during the audit.

The tracked repository is **1,202 files / 16.33 MiB**. The storage problem is outside Git: retired world snapshots occupy **40.71 GiB**, and ignored runtimes in the stale Claude worktree occupy another **about 2.37 GiB**. The repo contains stale statements and several non-replayable experiments, but it is not dominated by dead source code.

## DELETE

These items have no current load-bearing role. Deletion is still a user decision; this audit changed nothing.

| Path | Size | Why it is safe to delete | What breaks if it goes |
| --- | ---: | --- | --- |
| `.claude/worktrees/cobblemon-campaign-setup-64929d/experiments/EXP-000-cobblemon-1.8-compat/runtime/` | 2,190.36 MiB | Ignored assembled client/server copies and downloaded replacements; the manifest and assembly tooling are the source. | Local launches from this exact assembled runtime stop working until it is rebuilt. No tracked source is lost. |
| `.claude/worktrees/cobblemon-campaign-setup-64929d/experiments/EXP-000-cobblemon-1.8-compat/runs/20260909-*`, `20260910-*` | 0.55 MiB | Untracked old boot captures already superseded by committed EXP-000 conclusions. | Raw console evidence for those four runs is lost. Keep only if it is needed for provenance. |
| `.claude/worktrees/cobblemon-campaign-setup-64929d/tests/test_progression_pack.py` | 0 B | Empty untracked file; the current tracked test has content elsewhere. | Nothing. |
| `tests/fixtures/kit/hut_v2.*`, `tests/fixtures/kit/hut_v3.*`, `tests/fixtures/kit/kit_test_v2.schem`, `tests/fixtures/kit/kit_test_v3.schem` | 3.2 KiB total | No test or tool references these sample fixtures; only the fixture README names them. | Those four manual format examples disappear; the tested fixtures remain. |
| `experiments/EXP-002-difficult-trainer-battle/` through `EXP-007-story-progression/` | 5.9 KiB total | Six one-page backlog placeholders, not experiments or runnable proofs. Their objectives belong in `docs/research/EXPERIMENT_BACKLOG.md`. | Directory-per-future-ID placeholders disappear; no evidence or implementation is lost. Consolidate the objectives first if the backlog does not already contain them. |
| `cobblers-server-retired/2026-09-14/aborted-partial-export/` | 982.21 MiB | Explicitly aborted partial world export. | Nothing reproducible or playable; only forensic evidence from the aborted export. |
| `.claude/worktrees/cobblemon-campaign-setup-64929d/experiments/EXP-001-curated-route/runtime/` and `runs/` | 22.55 MiB | Ignored runtime for a retired prototype whose tracked instructions are already non-replayable. | The old prototype cannot be reopened locally; its written record remains. |
| `.claude/worktrees/cobblemon-campaign-setup-64929d/experiments/EXP-009-automated-hex-world/` ignored export/runtime material | 154.91 MiB | Retired 1,250-block hex prototype; square 1,024-block cells replaced it. | The discarded prototype cannot be reopened. Preserve one small record or screenshots first if wanted. |

The names `tools/verify_water.py` and `tools/dp_hash.py` do not exist in any registered worktree or reachable Git history. They are already absent or were external scratch scripts; there is nothing in the repository to delete.

## ARCHIVE

These are useful records, but they should stop presenting themselves as current runnable systems. “Archive” means retain the concise result/provenance and remove or relocate obsolete runtime instructions and fixtures after review.

| Path | Size | Why archive it | What breaks if it goes entirely |
| --- | ---: | --- | --- |
| `tools/rescale.py` | 8.0 KiB | One-off transform that produced the accepted vertical rescale. The canonical result is already applied; no current workflow calls or imports it. | Exact reproduction of the original rescale operation becomes harder. Preserve its formula and input/output hashes in `VERTICAL_RESCALE.md`. |
| `tools/islet.py` | 5.9 KiB | Historical Relic Island builder, with no test/static caller and hard-coded server/RCON assumptions. | Rebuilding that retired island exactly. If retained, first parameterize it to use an offline snapshot and explicit target. |
| `tools/world_tree.py` | 4.9 KiB | One-off world-tree datapack builder with hard-coded live-world paths; `tree_grove.py` now owns reusable tree geometry. | The current hard-coded world-tree datapack rebuild path. Preserve the tree parameters before archiving. |
| `experiments/EXP-001-curated-route/` | 7.3 KiB tracked | Explicitly superseded; five named source/world inputs are gone, yet its result still reads as runnable/ready. | Historical explanation of the first route prototype; its useful intent is already summarized in `data/notes/legacy_events.md`. |
| `experiments/EXP-009-automated-hex-world/` | 7.9 KiB tracked | Records the retired 1,250-block hex prototype. The project now uses 1,024-block square cells. | Evidence explaining why the hex approach was abandoned. |
| `experiments/EXP-013-hand-placed-structures/` | 53.2 KiB | Concluded and valuable evidence, but its raw world/run capture is external and ignored. Keep the results as an evidence record, not as a reproducible runner. | Verified facts about template placement, structure-gated spawns, RCT spawners, and gym-map limits. |
| `experiments/EXP-014-worldpainter-feature-placement/` | 40.4 KiB | Concluded WorldPainter behavior evidence; scratch exports and runs are absent and Minecraft loading was not fully verified. | WorldPainter placement-format findings and calibration evidence. |
| `experiments/EXP-019-apricorn-shape-and-villagers/` | 27.6 KiB | Concluded evidence based on an external disposable copy of live-world region data, so it cannot be replayed from the repository. | Observed apricorn shape and villager behavior. |
| `experiments/EXP-020-flag-driven-waystones/` | 11.6 KiB | Tests A–D are concluded and committed; test F never ran. Archive the proven portion or keep active only if F remains scheduled. | Existing evidence for flag-driven waystones; the unrun F test is not evidence. |
| `docs/world-building/SCALE_TEST.md` and `PROTOTYPE_DEPENDENCIES.md` | 7.2 KiB total | Describe the retired 1,250-block hex prototype. | Historical scale-test rationale. |
| `docs/world-building/events/F4_RELIC_ISLAND_ASH_HOUSE.md` | 8.5 KiB | Describes a deleted 1,000×1,000 hex-world event at noncanonical coordinates. | Detailed retired event implementation; intent remains in `data/notes/legacy_events.md`. |
| `docs/world-building/BIOME_COVERAGE.md`, `BIOME_COVERAGE_MATRIX.md`, `CROSS_SECTIONS.md`, `GLACIER_CARVE.md`, `SIGHTLINES.md`, `TOWN_CANDIDATES.md` | 71.5 KiB total | Superseded reports generated against pre-rescale terrain or replaced planning. Each already has a newer source or report. | Historical comparisons and old measurements; current build logic should not depend on them. |
| `docs/world-building/REEXPORT.md` historical sections | 32.8 KiB file | A long chronological export diary mixes pre-rescale and current instructions. Retain the diary as dated history and extract one short current export procedure. | Detailed sequence of earlier exports and recovery actions. |

### Retired world store

These directories are outside Git. Most are full-world copies of roughly the same 2.9–3.1 GiB save. Keep a small number of named recovery anchors and delete the rest only after the user chooses those anchors.

| Snapshot | Size | Last modified | Recommendation | What breaks if removed |
| --- | ---: | --- | --- | --- |
| `cobblers-server-retired/2026-09-13/` | 1.68 GiB | 2026-09-13 14:49 | Delete after confirming later anchors boot. | Earliest retained campaign-world rollback. |
| `cobblers-server-retired/2026-09-14/` | 3.93 GiB | 2026-09-14 02:37 | Delete the 982.21 MiB aborted export immediately after approval; assess the remaining world separately. | A pre-biome/foliage rollback. |
| `2026-09-14-biome-tags/` | 3.09 GiB | 2026-09-14 19:29 | Delete if the later foliage/rivers snapshots supersede it. | Exact rollback before later paint passes. |
| `2026-09-14-foliage/` | 3.08 GiB | 2026-09-14 22:52 | Delete or retain one of this and `foliage-first-pass`, not both. | One foliage-state rollback. |
| `2026-09-14-foliage-first-pass/` | 2.88 GiB | 2026-09-14 23:34 | Archive only if the first-pass comparison still matters. | Before/after evidence for foliage iteration. |
| `2026-09-14-rivers/` | 3.11 GiB | 2026-09-14 18:00 | Delete if a later pre-rescale anchor is retained. | Exact pre/post-river rollback. |
| `2026-09-14-tarn/` | 3.14 GiB | 2026-09-14 21:01 | Delete if a later pre-rescale anchor is retained. | Exact tarn-stage rollback. |
| `2026-09-15-pre-relief/` | 2.98 GiB | 2026-09-15 09:30 | Delete if `pre-sculpt` or `pre-rescale` is the chosen terrain anchor. | Pre-relief rollback. |
| `2026-09-15-pre-sculpt/` | 5.26 GiB | 2026-09-15 07:57 | Inspect: its parent is much larger than its nested world and may contain duplicate extras. Keep only unique evidence. | Pre-sculpt rollback and any unique side files. |
| `2026-09-15-river-head/` | 3.08 GiB | 2026-09-15 10:12 | Delete if no direct river-head comparison remains. | River-head rollback. |
| `2026-09-15-valley-head-files/` | 97.46 MiB | 2026-09-15 16:19 | Good archive candidate because it is small and targeted. | Local valley-head evidence. |
| `2026-09-16-pre-creek/` | 2.99 GiB | 2026-09-15 20:21 | Keep only if creek rollback is still operationally useful. | Pre-creek rollback. |
| `2026-09-16-pre-rescale/` | 2.90 GiB | 2026-09-15 23:27 | Keep as the strongest pre-rescale anchor until the new world is stable. | Direct recovery/comparison point for the vertical rescale. |
| `2026-09-17-pre-grass/` | 2.47 GiB | 2026-09-16 08:03 | Keep as the latest compact full-world anchor. | Most recent pre-grass recovery point. |
| `exp013de-nether-outside-border/` | 16 KiB | 2026-09-13 | Archive with EXP-013 evidence or delete after extracting the result. | Tiny experiment fixture only. |
| `exp013de-site-backup/` | 7.91 MiB | 2026-09-13 | Archive with EXP-013 if its exact blocks matter. | Small site rollback. |
| `town-iteration-test/` | 14.19 MiB | 2026-09-15 | Archive until town composition is accepted, then delete. | Small town-iteration rollback. |

A reasonable retention set is `2026-09-16-pre-rescale`, `2026-09-17-pre-grass`, `2026-09-15-valley-head-files`, and the two small EXP-013/town fixtures. That would preserve meaningful recovery points while allowing roughly **35 GiB** of duplicate snapshots to be removed after verification.

## CONSOLIDATE

| Paths | Size | Surviving source | Why consolidate | What breaks if the others go before migration |
| --- | ---: | --- | --- | --- |
| Bilinear height sampling in `tools/terrain.py`, `tools/cross_section.py`, `tools/coast_measure.py`, and `tools/sculpt.py` | 78.7 KiB across files | `tools/terrain.py` | The interpolation logic is independently implemented three extra times and can drift at edges/rounding. | Cross-section, coast, and sculpt measurements break until they import the shared implementation. |
| Region-file test writers in `tests/test_region_trim.py` and `tests/test_reexport_tools.py` | Small helper functions | New `tests/helpers/anvil.py` | Both tests build typed Anvil region records independently. | Those tests fail until imports are changed. Production readers/writers are unaffected. |
| World constants repeated through `docs/world-building/`, `data/*.json`, tools, and tests | 83 textual `10240` references in 27 non-base files; 50 `8192` references in 27 | `data/world.json` for machine values; `docs/STATE.md` for the human summary | Sea level, world bounds, grid size, vertical band, source hashes, and import mapping are copied into prose and have already diverged. | Standalone documents lose context unless they link to the canonical fields. Tests should keep intentional fixture-local constants. |
| Import mapping in `data/world.json`, `OCEAN.md`, `REEXPORT.md`, and tests | Distributed | `data/world.json` | The same coordinate transform is explained and sometimes implemented more than once. | Historical explanations become less self-contained; no runtime behavior breaks if references are replaced with links. |
| Route distances in `data/routes.json`, `data/towns.json`, `TOWNS.md`, `ARC.md`, `SIDEQUESTS.md`, and event docs | Distributed | `data/routes.json`; validator-enforced copies in `towns.json` only where operationally required | Current route distances are `1792, 946, 1989, 2907, 1038, 1944, 2053, 3049, 5157`; prose copies have already drifted (`TOWNS.md` still says 908 and 1946 for legs 2 and 6). | Narrative wording that promises an exact distance must be rewritten to reference a leg or explicitly marked approximate. |
| `data/spawns.json`, `data/routes/*.json`, and `data/cobblemon/` | 4.03 MiB combined; `data/cobblemon/` alone is 2.93 MiB | Authored source plus a committed generator and manifest | Native spawn JSON duplicates source rosters and 1,269 route boxes, but no complete committed generator was identified. Decide whether native files are authored deliverables or generated build output. | Deleting `data/cobblemon/` now loses the only compiled native pools; moving it before a generator exists makes the spawn work unreproducible. |
| `docs/world-building/REEXPORT.md`, `BUILT.md`, `VERTICAL_RESCALE.md`, and `docs/STATE.md` | About 60 KiB | `STATE.md` for facts, `VERTICAL_RESCALE.md` for the accepted transform, a short current export runbook | Current state, process, and history are interleaved. | Removing history without extracting the current runbook loses recovery knowledge. |
| Future experiment placeholders and `docs/research/EXPERIMENT_BACKLOG.md` | 5.9 KiB placeholders | `EXPERIMENT_BACKLOG.md` | A planned experiment should have one backlog record; create a directory only when implementation/evidence starts. | Only empty directory scaffolding is lost. |

The heightmap/region/sightline sweep did **not** find wholesale duplicate implementations:

- `tools/terrain.py` is the canonical heightmap coordinate/height layer; `height_to_sample_floor` in river grading is an intentional inverse, not a duplicate.
- `tools/nbt.py` is the canonical read-only Anvil/NBT decoder. `region_trim.py` and `transplant_chunks.py` perform distinct mutations and must not be merged blindly.
- `tools/sightlines.py` is the canonical ray/visibility implementation. `landmark_trees.py` and `tree_town_sites.py` consume it rather than reimplementing it.

## FIX

These items are active or informative, but currently stale, unsafe, or misleading.

| Path | Size | Required fix | What breaks if left as-is |
| --- | ---: | --- | --- |
| `data/world.json` | 6.1 KiB | Replace obsolete `measured_ceiling_y: 201` and WorldPainter hash `cd6439…` with verified post-rescale values (`y310` terrain; project hash `47e01a…`) and state how the `y535` tree is measured separately. | Tools and agents can select the wrong vertical limits or wrong source project. |
| `data/cells.json` | 260.6 KiB | Regenerate all 64 records from canonical hash `3eb0ed…`; current records use the pre-rescale `fd0…` heightmap. | Terrain metrics, site selection, and validation remain wrong. |
| `data/regions.json` | 56.7 KiB | Regenerate vertical/terrain-dependent data and close the 29 polygon holes. | Exact spawn compilation remains blocked and route intervals use fallbacks. |
| `data/routes.json` and `data/routes/*.json` | 3.15 MiB total | Reroute/recompute against the canonical rescaled heightmap, then update dependent town/rest-stop/narrative distances. | Distances, grades, crossings, boxes, and availability assumptions remain pre-rescale. |
| `data/towns.json`, `landmarks.json`, `rivers.json`, `placements.json` | About 133 KiB combined | Recompute stale terrain hashes/heights/status. `towns.json` still contains `y200` clipping rationale; placements still call the built nine-piece Hometown “planned.” | Agents treat old candidate geometry and build status as current. |
| `data/README.md` | 5.8 KiB | Update “nothing built” statements and point to `STATE.md` for counts. | Every data-focused session begins from false world state. |
| `docs/world-building/BUILT.md` | 13.1 KiB | Stop presenting the pre-rescale creek export/hash as the audited current world. | Agents can rebuild or validate against the wrong world generation. |
| `docs/world-building/NAVIGATION.md:220` | 8.5 KiB file | Replace the instruction to locate Blaine in the Nether with the decided overworld Craters plan. | Navigation work may deliberately wire the wrong gym location. |
| `docs/world-building/STRUCTURE_DATA_FALLOUT.md:120` and `STRUCTURE_INVENTORY.md:305` | 19.6 KiB combined | Mark Nether Blaine statements as historical/generated-copy risks; do not list Nether Blaine as campaign placement. | Structure planning contradicts the settled gym plan. |
| `docs/world-building/TOWNS.md` | 7.7 KiB | Replace stale leg 2/6 distances (908/1946) with references to route IDs; do not copy mutable distances into prose. | Rest-stop and event spacing decisions use wrong leg lengths. |
| `docs/world-building/TOWN_ITERATION.md` | 13.5 KiB | Replace the 384-block world-height assumption with runtime `y-64..575` and rewrite commands that target the live world to use named offline snapshots. | Chunk-copy bounds can be wrong and the instructions violate live-world isolation. |
| `docs/world-building/OCEAN.md`, `RIVERS.md`, `SCULPT.md`, `REEXPORT.md` | 66.0 KiB combined | Add clear post-rescale status at the top; move older hash/y201 instructions into dated history. | Agents can treat pre-rescale measurements as current procedure. |
| `tools/elder_trees.py` | 17.8 KiB | Remove the default path to `cobblers-server/cobblers-10240`; require an explicit offline snapshot/output. | An agent can read or mutate the live save despite the lock rule. |
| `tools/world_heights.py` | 20.4 KiB | Replace its live-world example with an offline snapshot example. | Documentation invites prohibited live-world reads. |
| `tools/world_tree.py` and `tools/islet.py` | 10.8 KiB combined | If retained, remove hard-coded live paths/RCON defaults and require explicit disposable targets. | Running either can touch runtime state before the caller notices. |
| `tools/validate.py` | 12.8 KiB | Four registered checks are reachable stubs that report “skipped/info.” Label them as planned capabilities rather than allowing the validator surface to imply they validate content. | A green validation run can be overread as proof of missing-reference checks. |
| `experiments/EXP-013`, `EXP-014`, `EXP-019` | 121.2 KiB total | Add a concise fixture/runtime manifest and mark replayability honestly: evidence-only, environment-dependent, or external-runtime. | Future agents waste time searching for absent scratch worlds and may claim replayability that does not exist. |
| `experiments/EXP-020-flag-driven-waystones/README.md` | Part of 11.6 KiB experiment | Separate proven A–D conclusions from unrun test F. | “Experiment complete” can be mistaken for proof of every listed case. |
| `data/cobblemon/` ownership/build policy | 2.93 MiB | Resolve the contradiction between `STATE.md` assigning it as committed data and architecture saying generated output belongs under `build/`. Add the missing generator or declare it authored native output. | Future cleanup may delete the only compiled pools, or future agents may hand-edit generated files. |
| Canonical source location | External heightmap and `.world` files; hashes only in Git | Either commit permitted reproducible sources, provide a durable artifact manifest/location, or revise the policy that says they are committed. | The world cannot be rebuilt from a fresh clone despite the stated architecture. |
| `design/structures` worktree: `tools/maze_forest.py` | 24.2 KiB | Keep the unmerged Route 1 work, but remove the hard-coded live-world path before integration and require an offline snapshot. | Merging as-is reintroduces the exact live-world collision class the project rules now prohibit. |
| `.claude/worktrees/bootstrap-compatibility-audit/` | 0.18 MiB untracked research plus old branch | Reconcile unique `base-pack/README.md`, capability/compatibility notes, and pack-content audit into current docs before removing the worktree. | Unique compatibility research may be silently lost. |
| Root `main` checkout | Clean but 105 commits behind `origin/main` at audit time | Fast-forward when no local user work is present. | Users and agents opening the root checkout see a very old project. |

### Worktree status

Git reports no prunable registrations, so these are not broken administrative entries. The problem is mixed conventions and old worktrees that retain large ignored artifacts.

| Worktree / branch | Status | Action |
| --- | --- | --- |
| root checkout / `main` | Clean; 105 commits behind `origin/main` | FIX by fast-forwarding after review. |
| `cobblers-worktrees/restructure` / `design/structures` | Clean; 8 ahead and 8 behind | KEEP: active unmerged structure/forest work; rebase/merge deliberately and fix live path first. |
| `.codex/worktrees/encounter-spawn-data` | Clean; merged | Remove registration/directory after this audit is safely retained elsewhere. |
| `.codex/worktrees/narrative` | Clean; merged | Safe to remove as a worktree. |
| `.codex/worktrees/state-doc` | Clean; merged | Safe to remove as a worktree. |
| `.claude/worktrees/cobblemon-campaign-setup-64929d` | Old branch with about 2.37 GiB ignored runtimes | Preserve any unique run evidence, delete reproducible runtimes, then remove the worktree. |
| `.claude/worktrees/bootstrap-compatibility-audit` | Old unmerged branch; unique untracked research | Reconcile first; not safe to delete yet. |
| old branches without registered worktrees: `bootstrap/claude-infrastructure`, `bootstrap/runtime-foundation`, `codex/exp009-*` | Unmerged ancestry but apparently superseded/squash-integrated | Compare patches once, then delete branches if no unique commit remains. |

Use one convention going forward: `.codex/worktrees/<task>` for Codex work. Keep `.claude/worktrees/` only for currently active Claude tasks, and remove merged worktrees promptly. The sibling `cobblers-worktrees/` location should be retired after `design/structures` lands.

## KEEP

These are the load-bearing surfaces. Their lack of imports is expected where they are standalone command-line tools.

| Path | Size | Why keep it | What breaks if it goes |
| --- | ---: | --- | --- |
| `tools/terrain.py`, `heightmap_check.py`, `make_fixture.py` | Core terrain helpers | Canonical coordinate/height conversion and deterministic test fixtures; directly covered by tests. | Terrain measurements and many validators. |
| `tools/route_path.py`, `drainage.py`, `grade_rivers.py`, `region_measure.py`, `cell_stats.py`, `slope_masks.py`, `landforms.py`, `coast_measure.py`, `massif_measure.py`, `terrace_measure.py`, `cross_section.py` | Route/terrain analysis suite | Rebuilds and measures route, river, cell, landform, coast, massif, terrace, and cross-section data. | Canonical terrain-derived data cannot be regenerated or checked. |
| `tools/sightlines.py`, `landmark_trees.py`, `tree_town_sites.py` | Sightline/site suite | One shared sightline implementation plus consumers. | Landmark visibility and site-selection evidence. |
| `tools/foliage.py`, `foliage_objects.py`, `paint_maps.py`, `elder_trees.py`, `tree_grove.py` | Foliage pipeline | Generates the 77,750-object foliage layer and authored tree groups. | WorldPainter foliage/tree inputs cannot be reproduced; `elder_trees.py` still needs the safety fix above. |
| `tools/nbt.py`, `structure_nbt.py`, `world_heights.py`, `dimension_audit.py`, `region_trim.py`, `level_dat.py`, `reexport.py`, `transplant_chunks.py` | Anvil/world toolkit | Distinct read, audit, export, trim, and transplant responsibilities. | Controlled export/recovery and world inspection. Do not collapse these into one mutator. |
| `tools/pack_manifest.py`, `assemble_client.py`, `patch_cobbleverse_riding.py`, `client_model_fix.py` | Pack/client tools | Reproducible pack assembly and verified compatibility patches. | Client/server pack reproduction and known 1.8 fixes. |
| `tools/validate.py`, `validate_data.py`, `progression_pack.py`, `spawn_tag_pack.py`, `spawn_biomes.py`, `spawn_blocks.py` | Content/pack validation and compilation | Current validation and generated datapack paths. | Data checks and pack generation; improve stubs rather than deleting the tool. |
| `tools/kit.py`, `place_town.py`, `town_plan.py`, `cavern_plan.py`, `critical_legs.py`, `worldgen_features.py`, `structure_inventory.py`, `structure_candidates.py` | Structure/town planning | Current donor inventory, town kit, placement, cavern, and route planning workflows. | Reusable structure composition and site planning. |
| `experiments/EXP-000-cobblemon-1.8-compat/` | 19.7 KiB tracked | Active compatibility baseline and boot evidence. | The pack loses its primary compatibility record. |
| `experiments/EXP-008-structure-placement/` | 6.4 KiB | Compact runtime proof that raw templates/transforms work and BCA jigsaw placement is partial. | Structure-placement evidence. |
| `experiments/EXP-017-ore-pockets-and-object-load/` | 82.0 KiB | Detailed, still-relevant ore calibration and proof that exported Cobblemon block entities survive load/save. | WorldPainter ore/object decisions lose their evidence. |
| `docs/STATE.md` | 13.3 KiB | Required current project index and ownership map. | Every session returns to rediscovery. It must be corrected when canonical data changes. |
| `data/world.json`, canonical heightmap/project hashes, and `docs/world-building/VERTICAL_RESCALE.md` | Distributed | World identity and accepted vertical transform. | Rebuilds lose their coordinate and elevation contract. Fix stale fields first. |
| `data/structures.json`, `kits/`, structure inventory/workflow docs | 2.3 MiB plus docs | Reusable donor/structure surface and authored templates. | Towns and landmarks revert to manual rediscovery. |
| `base-pack/inventory/` and tracked `base-pack/cobbleverse/config/`/licenses | 5.24 MiB top-level total | Provenance and compatibility reference without committing redistributable jars. | Cobbleverse compatibility and license decisions become unverifiable. |
| `.gitignore` and `.gitattributes` | 5.7 KiB | Current ignore policy is working: no tracked file was found that matches ignore rules. | Runtimes, worlds, jars, secrets, and transient files are more likely to enter Git. |

No convincing unreachable production function or dead internal branch was found. Static reachability is limited for command-line entry points, but every surviving tool above is either tested, documented as a current workflow, imported by another tool, or produces a current data asset. The four `validate.py` stubs are reachable placeholders, not unreachable branches.

## Size assessment

### Tracked repository by top-level path

| Path | Tracked size |
| --- | ---: |
| `data/` | 6.18 MiB |
| `base-pack/` | 5.00 MiB |
| `kits/` | 1.76 MiB |
| `docs/` | 0.96 MiB |
| `tools/` | 0.82 MiB |
| `modpack/` | 0.76 MiB |
| `tests/` | 0.44 MiB |
| `experiments/` | 0.25 MiB |
| agent/config/root files | 0.16 MiB |

Largest tracked files are `base-pack/.../roughlyenoughitems/collapsible.json5` (1.26 MiB), `data/notes/reference/f4-pallet-coast-concept.jpg` (0.82 MiB), `data/spawns.json` (0.64 MiB), the base-pack license PDF (0.56 MiB), and the per-route/structure JSON files (about 0.28–0.44 MiB each). None is an accidental committed runtime. The image and PDF are intentional reference/provenance assets; the spawn output is the main unresolved source-versus-generated duplication.

### Blunt conclusion

By tracked bytes, roughly **75% is currently load-bearing reference, source, tests, or current evidence**. About **20% is generated spawn material whose reproducibility/ownership is unresolved**, and about **5% is clearly historical, superseded, or placeholder material**. By file count and attention cost, the accumulated share is worse: around **one quarter to one third of the visible surface** is old reports, concluded experiments, repeated constants, or worktree residue that an agent must filter before finding current truth.

Disk use tells the harsher story. The tracked repo is only **16.33 MiB**, while identified retired snapshots and ignored runtimes total about **43.08 GiB**. More than **99.9% of the measured local project footprint is accumulated world/runtime state outside Git**. Most of that can eventually go; the safe process is to retain two full recovery anchors, keep the small targeted fixtures, reconcile the one worktree with unique research, and delete the remaining duplicate snapshots and assembled runtimes after explicit approval.
