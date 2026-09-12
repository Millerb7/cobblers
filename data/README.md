# data/

The design itself. Hand-edited, version controlled, and the real product of this
repository. Everything else either feeds this or is generated from it.

`derived/` and `build/` can be deleted and rebuilt. `source/` can be re-exported.
This directory cannot be regenerated from anything, so it is the part that
matters.

## Files

| File | Holds | State |
| --- | --- | --- |
| `world.json` | The single config: heightmap path and hash, import mapping, vertical band, grid | present, origin and hash deliberately unset |
| `cells.json` | The 8×8 planning grid and measured terrain per cell | not written yet |
| `landmarks.json` | Named features: rift, peaks, volcano, island chains | not written yet |
| `events.json` | Authored event definitions with anchors and terrain requirements | not written yet |
| `placements.json` | Every structure instance and its position | not written yet |
| `trainers.json` | Trainer teams, AI, gating, rewards | not written yet |
| `spawns.json` | Curated encounter tables | not written yet |
| `gyms.json` | The eight gyms and the Elite Four | not written yet |
| `progression.json` | Chapters, badges, level caps, flags | not written yet |
| `routes.json` | Authored route polylines | not written yet |
| `notes/` | Plain markdown. Not validated, not read by tooling |

The absent files are absent on purpose. An empty validated skeleton is the
correct state until the heightmap is re-exported and the grid origin is known;
a populated one would be authored against terrain that does not exist yet.

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
