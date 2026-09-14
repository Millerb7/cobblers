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
| `regions.json` | Terrain-bounded regions: class, tier, status, character, biomes by band, underground biomes, tags, overlays, coverage, polygons. `marine_regions` holds the five planned sea regions (seabed profile, biome bands, flora, content) | **draft**, schema `cobblers.regions/2` proposed and awaiting approval. Rationale in `docs/world-building/REGIONS.md` and `OCEAN.md`. `marine_regions` is not yet checked by the validator |
| `cells.json` | The 8×8 planning grid and measured terrain per cell | **draft**: terrain blocks written by `tools/cell_stats.py --write-cells`, tied to the heightmap sha256 and import digest, recomputed by the validator; authored fields (role, landmarks) not yet written |
| `landmarks.json` | Named features from the annotated heightmap: outlines, axes, anchors, `status` (built / partial / planned), water policy, carve and anomaly specs | **draft**: rift, glacier corridor, meltwater lake, moraine, meltwater river, range, cones. Validated for required fields and enums |
| `checks/sightlines.json` | Sightline sets run against landmarks by `tools/sightlines.py --plan` | present; results in `docs/world-building/SIGHTLINES.md` |
| `events.json` | Authored event definitions with anchors and terrain requirements | not written yet |
| `structures.json` | Every structure the loaded pack generates, with an authored class (PROGRESSION, LEGENDARY, NAMED, SCATTER) and disposition | **draft**, schema `cobblers.structures/1` proposed. Report in `docs/world-building/STRUCTURE_INVENTORY.md` |
| `placements.json` | Every structure instance and its position | not written yet |
| `trainers.json` | Trainer teams, AI, gating, rewards | not written yet |
| `spawns.json` | Curated encounter tables | not written yet |
| `gyms.json` | The eight gyms and the Elite Four | not written yet |
| `progression.json` | Chapters, flags (one per gym: badge ledger and waystone unlock), trainer ids per RCT series, waystone towns | **draft**: 8 gym flags and the champion flag with kanto/johto/hoenn/sinnoh ids; waystone positions null until towns are placed. `tools/progression_pack.py` builds the datapack. Design in `docs/world-building/NAVIGATION.md` |
| `routes.json` | Authored route polylines | not written yet |
| `notes/` | Plain markdown. Not validated, not read by tooling |

The absent files are absent on purpose. Regions come first; towns, routes, events and
trainers are authored against them once the region layout is approved.

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
