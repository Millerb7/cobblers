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

## Current status: verified

The canonical heightmap is `land_8k_16_eroded.png`, pinned in `data/world.json`.
Verified on 2026-09-13: 8192 by 8192, 16-bit single channel, every value from 0 to
65535 used, no neighbouring blocks more than 1.3 blocks apart, 0.34% of the surface
clipped at the ceiling.

On the authoring machine it sits loose in the Documents folder alongside its
provenance files (`landmass.terrain`, `land_8k_16.png`, `land_8k_16.TSmap`), so
`source_root` is that folder rather than the tidy layout above. Point
`COBBLERS_SOURCE_ROOT` there.

The two earlier exports remain rejected and are recorded in `data/world.json`.

## Pipeline

```
Gaea (landmass.terrain, 1024² build)
      ↓  export
GIMP (pre_erosion_land_8k.xcf, upscaled to 8192², masks applied)
      ↓  flatten to genuine 16-bit single channel
TerreSculptor (erosion pass)
      ↓
land_8k_16_eroded.png                  ← canonical
      ↓  import with data/world.json parameters
WorldPainter → Minecraft save
```
