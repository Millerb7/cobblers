# The source tree

`source/` is **not in this repository**. It holds large, irreplaceable authoring
files that git should not carry: the Gaea project, the GIMP working files, and
the 8K heightmaps. It is referenced by hash, not by content.

Point tooling at it with the `COBBLERS_SOURCE_ROOT` environment variable, or
pass `--source-root` to any tool that reads terrain. `data/world.json` records
`source_root: null` deliberately, because the path is machine-specific.

## Expected layout

```
<source root>/
├── gaea/
│   └── landmass.terrain          Gaea node graph. Builds at 1024².
├── gimp/
│   └── pre_erosion_land_8k.xcf   GIMP working file, 8192², layered
├── masks/
│   ├── land_plan.png             hand-authored landmass plan
│   ├── landmask.png
│   ├── landmask_invert.png
│   ├── landmask_blure.png
│   └── landmask_invert_blur.png
└── heightmap/
    └── land_8k_16.png            THE canonical heightmap: 8192², 16-bit, single channel
```

Only `heightmap/land_8k_16.png` is referenced by `data/world.json`. Everything
else is provenance, kept so the canonical file can be rebuilt.

## Integrity

`data/world.json` records the canonical heightmap's `sha256`. The validator
recomputes it and **fails closed** when the recorded hash is null, the file is
missing, or the hashes disagree. There is no mode in which an unverified
heightmap is silently accepted.

## Current status: blocked

Neither existing export is usable and `land_8k_16.png` does not exist yet.

- `erosion_land_8k.png` has sawtooth wraparound across the whole surface. About
  7.3% of horizontally adjacent pixels differ by more than 100, which would be a
  100-plus block cliff every few blocks in game. It is also stored as 8-bit RGB
  with the height only in the red channel. Macro structure, meaning the rift,
  both peaks and the coastline, is intact; mid-frequency detail is mangled and
  does not unwrap cleanly.
- `pre_erosion_land_8k.png` has the landmass clipped to 255, mean 244 and median
  255. It contains no land elevation data at all.

Both need re-export from a verified GIMP flatten at genuine 16-bit. Until that
file exists:

- `heightmap.sha256` stays null
- cell `terrain` blocks stay unpopulated
- `computed_from_sha256` stays null
- the validator fails on all three, and reports the spatial checks as SKIPPED

## Pipeline

```
Gaea (landmass.terrain, 1024² build)
      ↓  export
GIMP (pre_erosion_land_8k.xcf, upscaled to 8192², masks applied)
      ↓  flatten to genuine 16-bit single channel
TerreSculptor (erosion pass)
      ↓
source/heightmap/land_8k_16.png        ← canonical
      ↓  import with data/world.json parameters
WorldPainter → Minecraft save
```
