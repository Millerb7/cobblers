# data/

The design itself. Hand-edited, version controlled, and the real product of this
repository. Everything else either feeds this or is generated from it.

`derived/` and `build/` can be deleted and rebuilt. `source/` can be re-exported.
This directory cannot be regenerated from anything, so it is the part that
matters.

## Files

| File | Holds | State |
| --- | --- | --- |
| `world.json` | The single config: heightmap path and hash, import mapping, vertical band, grid, and `export` (WorldPainter levels, canvas, border, spawn, seed digest) | present and verified: origin 0,0, heightmap pinned by sha256; exported as `cobblers-10240` (`docs/world-building/REEXPORT.md`) |
| `regions.json` | Regions by terrain character and their sub-regions (the spawn unit): polygons, measured terrain, boundary legibility, an empty `encounters` slot, and `paint_presets` read by `tools/paint_maps.py`. `marine_regions` and `underground_biomes` carried from revision 2; `spawn_tag_overlays` (region identities as Cobblemon biome tags, built by `tools/spawn_tag_pack.py`) | **draft**, schema `cobblers.regions/3` proposed: 21 regions, 62 sub-regions on the 2026-09-14 terrain. Rationale in `docs/world-building/REGIONS.md` |
| `cells.json` | The 8×8 planning grid and measured terrain per cell | **draft**: terrain blocks written by `tools/cell_stats.py --write-cells`, tied to the heightmap sha256 and import digest, recomputed by the validator; authored fields (role, landmarks) not yet written |
| `rivers.json` | Lake outflows and river courses graded so the bed never rises: least worst cut, verdict (river / canal / no river), graded polylines `[x, z, surface_y, floor_y]`, reaches (catchment, grade, width, depth, bank slope, bed, incision, valley), the major river's selection, checks along each carved axis, and the `cut` record of the imported heightmap (path, sha256, cost per course, checks) | **derived** by `tools/grade_rivers.py`, schema `cobblers.rivers/1`. Validated: planned on `world.json` `heightmap.derived_from`, its cut is the imported heightmap, no graded course rises. `docs/world-building/RIVERS.md` |
| `towns.json` | Every settlement and outpost, by tier: the ten on the critical path (hometown, eight gym towns, the League) with route order and approach legs; major non-gym towns, rest stops and outposts off it, each with what it is for, why it sits there, distance from the routed path, nearest settlement, buildability and waystone policy; volume-build notes for the Mining Town and the Displaced City; recorded decisions | **proposed** 2026-09-14 (the League accepted), schema `cobblers.towns/1`; built: the hometown, street prep in Brock's and Misty's towns and Brock's gym (see `not_placed`); Surge's town re-sited 2026-09-16. Validated: exactly ten critical, nothing off the path ordered, gated or named by a progression flag, off-path distance ranges, spacing, footprints within the border. `docs/world-building/TOWNS.md`, `SETTLEMENTS.md` |
| `sculpt.json` | Local terrain brushes: prevailing wind, protection (sites, rivers, lakes, the built hometown area), coast classes and their profiles, massif asymmetry, summits and strata, the volcano's cones, and deliberate flat pads | **draft**, schema `cobblers.sculpt/1`. Applied by `tools/sculpt.py`; its output is the imported heightmap (`world.json` `heightmap.sculpted_from`). `docs/world-building/SCULPT.md` |
| `placements.json` | Structure instances placed by command, and each settlement's composition (roads, waystone, spawn) | **draft**, schema `cobblers.placements/1`: the hometown's nine buildings, placed by `tools/place_town.py` and verified in the rescaled world 2026-09-16 |
| `foliage.json` | Forest identity and tree placement: forest types (what each is and what it is like inside, stems per hectare, edge, glades, clumping, species classes by zone, lone trees, debris, floor, understory, biome), preset defaults, sub-region assignments (old growth at Peak Pond Hollow), and the five landmark trees with the observers each must be seen from | **draft**, schema `cobblers.foliage/1`. Read by `tools/paint_maps.py` through `tools/foliage.py`; objects in `kits/structures/foliage/`. `docs/world-building/FOLIAGE.md` |
| `landmarks.json` | Named features from the annotated heightmap: outlines, axes, anchors, `status` (built / partial / planned), water policy, carve and anomaly specs | **draft**: the 18 annotated features of the 2026-09-14 terrain, the carved channels (now rivers on their graded courses or dry ravines) and the major river, with measured basins, water levels, outflows and drainage tests (`docs/world-building/TERRAIN_2026-09-14.md`, `RIVERS.md`). Validated for required fields and enums |
| `checks/sightlines.json` | Sightline sets run against landmarks by `tools/sightlines.py --plan` | **stale**: references landmark ids from the 2026-09-13 terrain |
| `events.json` | Authored event definitions with anchors and terrain requirements | not written yet |
| `structures.json` | Every structure the loaded pack generates, with an authored class (PROGRESSION, LEGENDARY, NAMED, SCATTER) and disposition | **draft**, schema `cobblers.structures/1` proposed. Report in `docs/world-building/STRUCTURE_INVENTORY.md` |
| `trainers.json` | Trainer teams, AI, gating, rewards | not written yet |
| `spawns.json` | Weighted and leveled source rosters for 62 sub-regions and 9 Habitat places, plus compilation provenance | **source**, schema `cobblers.spawns/1`, including each route's authored species selection. `tools/compile_spawns.py` generates the native Cobblemon pools into `build/datapacks/cobblers_spawns/` (not committed, not installed, not runtime-proven) |
| `habitat_blocks.json` | Every Habitat Block the campaign places: pool, natural style, ReplaceSpawns, range, position, status | **source**, schema `cobblers.habitat-blocks/1`, 0 blocks; re-applied after every export (`docs/world-building/REEXPORT.md`), checked by `habitat-blocks` |
| `spawn_suppression.json` | Hybrid default-pool policy and the boundary between generated data and runtime proofs | **policy compiled**; route suppression proven by EXP-012 and Habitat replacement by EXP-021 on a disposable world; not installed live |
| `gyms.json` | The eight gyms and the Elite Four | not written yet |
| `progression.json` | Chapters, flags (one per gym: badge ledger and waystone unlock), trainer ids per RCT series, waystone towns | **draft**: 8 gym flags and the champion flag with kanto/johto/hoenn/sinnoh ids; waystone positions null until towns are placed. `tools/progression_pack.py` builds the datapack. Design in `docs/world-building/NAVIGATION.md` |
| `routes.json` | Terrain-derived critical-route polylines, elevation/crossing evidence, geography intervals, mandatory waypoints and 1,408 spawn boxes | **derived candidate**, schema `cobblers.routes/1`; generated by `tools/build_routes.py` on the canonical heightmap, 0 sub-region holes |
| `visibility.json` | Every claim that something can or cannot be seen from somewhere (landmark trees from their legs, rest stops from their leg, summits and valleys from towns, the Nosepass mast margin), with where it is stated, what observes what over terrain or the planned canopy, the measured count and whether it is fragile | **measured** 2026-09-16, schema `cobblers.visibility/1`; re-measured by `tools/validate_data.py` (check `visibility`), refreshed by `tools/visibility_claims.py --write`; every stating record cites `visibility:<id>` and says "fragile" when it is |
| `notes/` | Plain markdown. Not validated, not read by tooling |

Missing files remain intentional. Candidate routes and encounter data now exist; events, trainers and gyms still wait on accepted mechanisms and upstream geometry.

## Rules

**One config.** Anything that reads import parameters or the heightmap path
reads `world.json`. No tool carries its own copy of 40, 200, 62 or 8192.

**Fractions in, blocks out.** `import.low_in` and `high_in` are fractions of
full scale, so they survive a change of heightmap bit depth. `low_out`,
`high_out` and `water_level` are absolute Minecraft Y values and never scale.

**Cells index location only.** A cell is a square 1024-block planning label:
rows A to H run north to south, columns 1 to 8 run west to east. Region
boundaries are a separate concept that follows terrain and does not align to
cell edges. Do not conflate the two.

**Terrain statistics are measured, never typed.** The `terrain` block on a cell
is computed from the heightmap and carries the `sha256` it was computed from.
The validator recomputes and fails on drift.

**Fail closed.** A null hash, a missing origin or an unpopulated terrain block
is an error, not a warning. Checks that cannot run report `SKIPPED` with a
reason and never pass silently.

## Validation

```bash
python tools/validate_data.py
python tools/validate_data.py --json    # for CI
python tools/validate_data.py --list    # registered checks
```

Non-zero exit on any error.
