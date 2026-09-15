# tools/

Standalone command-line tools. Python, mostly standard library; the terrain
tools additionally need `numpy` and `Pillow`. No framework, no plugin system,
no abstraction over engines or games we do not use.

## Terrain analysis

All of these read the heightmap through `terrain.py`, which resolves the path and
the import mapping from `data/world.json` and **refuses to run** while
`heightmap.status` is anything other than `"ok"`, while the recorded `sha256`
is null, or while the file on disk does not match that hash. There is no flag
to bypass that; fix the config or re-export the heightmap.

Output goes to `derived/`, which is disposable and gitignored. Every artifact
records the heightmap hash it was computed from, so a stale derivative can be
detected rather than trusted.

| Tool | Does | Writes |
| --- | --- | --- |
| `find_sites.py` | Ranks flat buildable squares above sea level | `derived/sites/` |
| `route_path.py` | A* between two points, paying for climb; also the descent searches (`descend_min_cut`, `descend_route`) for beds that never rise | `derived/paths/` |
| `grade_rivers.py` | `plan`: least-cut descending course from every lake and river source to the sea, catchment-sized reaches (width, depth, banks, bed, incision), the major river chosen by catchment with its valley, checks along each carve. `cut`: carve those sections into the heightmap `heightmap.derived_from` names, write the imported file and re-check it (`docs/world-building/RIVERS.md`) | `data/rivers.json`, `<source root>/land_8k_16_eroded_rivers.png` |
| `drainage.py` | Priority flood, D8 flow directions and accumulation on a coarse height grid | (library) |
| `region_measure.py` | Re-measure `regions.json` measured blocks from the committed polygons on the current heightmap | `data/regions.json` with `--write` |
| `spawn_tag_pack.py` | Build the `cobblers_spawn_tags` overlay from `regions.json` `spawn_tag_overlays` (biome tags Cobblemon spawns on that no loaded biome carries); `--check-paint` fails if an overlay biome is painted outside its regions; `--install` copies it into a datapacks folder | `build/datapacks/cobblers_spawn_tags/` |
| `sightlines.py` | Raycasts from a viewpoint to named landmarks; `cast(surface=)` occludes with terrain plus canopy | `derived/sightlines/` |
| `foliage.py` | Forest placement for `paint_maps.py`: density fields (edge, ragged boundary, glades, clumping, slope, treeline, water) and exact object positions with class spacing, lone trees, debris, canopy and per-type stats (`docs/world-building/FOLIAGE.md`) | (library) |
| `foliage_objects.py` | The foliage object library: `harvest` vanilla trees over RCON into `.nbt`, `generate` seeded objects and landmark giants, `index` sizes, crowns, eye-level widths and hashes | `kits/structures/foliage/` |
| `structure_nbt.py` | Write and read structure templates (`.nbt`); capture a box of blocks from a world's region files | (library) |
| `landmark_trees.py` | Landmark giant designs; `check` sightlines from each tree's intended observers over terrain plus canopy | `derived/foliage/landmark_sightlines.json` |
| `sculpt.py` | Local terrain brushes from `data/sculpt.json`: coasts by class, massif asymmetry, summits and strata, volcano cones, flat pads; writes the sculpted heightmap, the coast class map and before/after previews | `<source root>/land_8k_16_sculpted.png`, `build/sculpt/`, `derived/sculpt/` |
| `coast_measure.py` | Profiles normal to the shoreline: grade over the first rise, shelf depth, terraces | `derived/coast/` |
| `massif_measure.py` | Summits, radial flank grades, clipped tops and cone bowls | `derived/terrain/massifs.json` |
| `place_town.py` | A settlement's placements as a datapack function: pads, rotated templates, jigsaws resolved, loot stripped, paths, waystone, spawn | `build/datapacks/cobblers_towns/`, `derived/towns/` |
| `transplant_chunks.py` | Copy whole chunks (region, entities, poi) from one closed world into another, to carry a build across a re-export | (in place) |
| `critical_legs.py` | Route the critical path legs (Victory Road along the Rift axes) and tally blocks per sub-region | `derived/routes/critical_legs.json` |
| `slope_masks.py` | Exports slope, aspect and land masks as PNG | `derived/slope/` |
| `cell_stats.py` | Per-cell elevation, land fraction, slope and distance to sea | `derived/cells/` |
| `landforms.py` | Land and water bodies, peaks, candidate landform classes | `derived/landforms/` |
| `cross_section.py` | Profiles perpendicular to a polyline or landmark axis: floor, rims, depth, floor and rim-to-rim width, wall angle, U / V / flat-floored / asymmetric | `derived/sections/` |

### Landmarks

`landmarks.py` reads `data/landmarks.json`: named features with outlines, axes, anchors, a
`status` (`built`, `partial`, `planned`) and a water policy. Tools look features up there
instead of inferring them from the heightmap.

- `cross_section.py --landmark rift --axis trunk` reads the axis and transect width.
- `sightlines.py` accepts `@landmark` or `@landmark.anchor` wherever it takes a point, and
  `@landmark*` as a target meaning any part of the feature: its outline and highest points.
  `--plan FILE` runs many sets on one terrain load.
- `landforms.py` and `cell_stats.py` honour `water: never`. Ground below sea level inside
  such a landmark is `void_floor` / `void_fraction`, never inland water. Pass
  `--no-landmarks` to measure without them.

A malformed landmarks file stops these tools; it is never silently ignored.

These produce **candidates**. A human picks. None of them decides where a town
goes, which way a road runs, or what a place looks like.

```bash
python tools/find_sites.py  --min-size 24 --max-slope 4 --top 20
python tools/route_path.py  --from 3400,3400 --to 4100,3900 --slope-weight 10
python tools/sightlines.py  --from 3400,3400 --eye 2 --target volcano:6654,6242
python tools/slope_masks.py --max-degrees 60
python tools/cross_section.py --landmark glacier_corridor --axis trough --sample-step 4 --level 62
python tools/sightlines.py  --plan data/checks/sightlines.json
```

Useful flags: `--bbox X0,Z0,X1,Z1` restricts the site search; `--max-y` excludes ground
clipped flat at the height ceiling, which otherwise ranks first; `--slope-weight 0`
gives a straight line and a high value hugs contours; `--max-slope` sets what
counts as impassable or unbuildable; `--world` points at a different config.

## Pack analysis

| Tool | Does | Writes |
| --- | --- | --- |
| `spawn_biomes.py` | Reads the server's vanilla jar, mod jars (with nested jars) and datapacks. Enumerates every biome and biome tag Cobblemon spawn conditions reference, resolves tags to loaded biomes, and checks coverage and species reachability against `data/regions.json` | `derived/spawns/`, optional markdown table |
| `structure_inventory.py` | Every structure the loaded pack generates: biomes, structure set, footprint from template NBT, template contents (loot, trainer spawners, altars, command blocks), spawn entries and data files that depend on it, plus mod worldgen features. With `--world`, scans a save's region files for structure starts inside and outside the map bounds | `derived/structures/`, optional markdown tables |
| `worldgen_features.py` | Every non-vanilla placed feature, the modded blocks it places, the items those drop, and whether each item has another source in data (recipes, non-block loot, datapack trades) | `derived/features/`, optional markdown table |
| `structure_candidates.py` | Candidate start chunks of random-spread structure sets inside a rectangle, from the world seed in `level.dat` (never written out). Upper bound: biome checks are not modelled. Verified against 49 real starts | optional JSON |
| `nbt.py` | Read-only NBT and Anvil region reader used by the above | nothing |

These need a server directory (`--server-dir` or `COBBLERS_SERVER_DIR`), not the heightmap.

## World saves

Run against a stopped server's world folder, or a copy. Procedures are in
`docs/world-building/DIMENSIONS_AND_BORDERS.md`.

| Tool | Does | Writes |
| --- | --- | --- |
| `region_trim.py` | Classifies saved chunks (region, entities, poi) inside or outside a block rectangle in one dimension, and lists structure starts outside. Dry run by default; `--apply` needs `--backup-dir` outside the dimension, backs files up, deletes wholly-outside files and clears outside chunks from straddling ones. Does not touch Distant Horizons data | JSON report; the world only with `--apply` |
| `dimension_audit.py` | After pregen: generation status coverage inside the rectangle, chunks saved outside, every structure start inside, and which catalog structures of the required classes are missing. `--fail-on-missing` and `--fail-on-incomplete` gate a procedure | JSON report |
| `world_heights.py` | `extract`: decodes every chunk in a rectangle into per-column ground and water-top heights, with chunk presence, status and chunks saved outside. `compare`: drift of that surface against the heightmap at the `world.json` mapping (land, seabed, clipped summits, margin, water) | `derived/world/` |
| `level_dat.py` | Type-preserving level.dat reader/writer. `summary` (seed shown only as sha256), `seed-match`, `carry` (copy top-level keys from one level.dat to another, with a backup) | the target level.dat with `carry` |
| `reexport.py` | Re-exports the heightmap with WorldPainter: reads the mapping, margin, border and spawn from `world.json` and the seed from the old world (passed to WorldPainter only through the environment). Runs `worldpainter/export_world.js` through `wpscript`, then carries `WorldGenSettings`, datapack selection and game settings from the old `level.dat`. Refuses to overwrite a world | a new world folder and `.world` project |

Record of the 2026-09-13 run: `docs/world-building/REEXPORT.md`.

Pack-analysis tools take `--scope default` (the Cobblemon jar alone) or `--scope pack`
(mod and datapack overrides by path). `datapacks/extra/` is read only with
`--include-extra`, because the server does not load it.

```bash
python tools/spawn_biomes.py --server-dir ../cobblers-server --regions data/regions.json     --markdown docs/world-building/BIOME_COVERAGE_MATRIX.md
```

## Fixture and tests

`make_fixture.py` generates the synthetic surface the tools are tested against:
a flat base, a stepped plateau, a cone, a ridge, a trench and a sea band, all
with hand-computable slopes and heights. The import mapping is chosen so that
samples are exactly invertible, since 65535 is 255 times 257.

```bash
python tools/make_fixture.py              # regenerate tests/fixtures/terrain/
python -m pytest tests -q
```

Tests assert against values derived from the feature geometry, not against a
previous run. A 45 degree flank must measure 45 degrees; the plateau must come
back as a 32 by 32 square at y=120; a high slope weight must route around the
ridge with zero climb rather than over it.

## Validation and packaging

| Tool | Does |
| --- | --- |
| `validate_data.py` | Schema, referential, integrity and progression checks on `data/`. With a verified heightmap it also recomputes every `cells.json` terrain block (`cell-terrain`, fails on drift) and checks landmark anchors, region and marine polygons and the export border geometry (`spatial`) |
| `validate.py` | File-level structural checks: JSON parses, `pack.mcmeta` present, duplicate basenames |
| `pack_manifest.py` | Base manifest and overlay: `generate`, `resolve-overlay`, `plan`, `verify`, `download` |
| `assemble_client.py` | Builds the client instance from the manifest |
| `patch_cobbleverse_riding.py` | Patches upstream riding data for Cobblemon 1.8, out of place |
