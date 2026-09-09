# Region terrain sources

`region.json` is the source of truth for EXP-009. `hex_flat_to_flat`, row and
column counts, and `blocks_per_pixel` derive both block and raster dimensions;
the generator contains no second copy of the 1,250-block scale. The generation
summary hashes decoded pixels so different PNG encoder versions do not create a
false reproducibility failure.

Regenerate from the repository root:

```powershell
python tools/generate_region.py
python tools/validate.py --only region_source
```

The generator writes `exp-009/masks/`, a visual preview, a hash manifest, and
the post-export town placement function. Re-running with the same config and
seed must reproduce every mask hash. Generated Minecraft worlds and
WorldPainter `.world` files live in the experiment's ignored `runtime/` folder.

## Masks

All masks cover 2,500 × 2,500 blocks at one block per pixel. This avoids
interpolation of exact category values during WorldPainter import.

| File | Encoding |
| --- | --- |
| `heightmap.png` | 8-bit surface Y, 50–184 (river valley/bed included) |
| `land-water.png` | 255 land, 0 river water |
| `river.png` | 255 channel, 0 elsewhere |
| `forest.png` | 255 old-growth core, 0 elsewhere |
| `plains.png` | 255 traversable lowland/edge, 0 elsewhere |
| `mountain-rock.png` | 255 exposed foothill/ridge, 0 elsewhere |
| `beach-coast.png` | 255 river bank/shore transition, 0 elsewhere |
| `terrain-categories.png` | exact values 1 plains, 2 forest edge, 3 forest core, 4 rock, 5 bank, 6 river |
| `transition-bands.png` | exact values 0 none, 85 forest edge, 170 rocky foothill, 255 river bank |
| `roads-trails.png` | 255 reserved route corridor, 0 elsewhere |
| `event-reservations.png` | 255 medium event, 128 small event, 0 elsewhere |

Category masks use discrete values without antialiasing. Natural changes come
from the global elevation/river functions and explicit transition bands:

- plains → scattered meadow/forest edge → forest core;
- forest → forest edge → rocky foothill → exposed ridge;
- lowland → 42-block bank → river channel;
- the eastbound town route reserves an 11-block bridge crossing near (1245, 600);
- elevation and the river are calculated over the whole master raster, so no
  feature is generated independently on a D/E or 4/5 boundary.

The fantasy hex map and adventure-plan document are visual and scale references.
They are not machine inputs and their illustrated colours are never sampled as
biome data.

## WorldPainter adapter

WorldPainter is not installed in the inspected environment. Install or extract
the official 64-bit portable WorldPainter package, then run from the repository
root:

```powershell
$region = Get-Content world/source/region.json -Raw | ConvertFrom-Json
$scalePercent = $region.world.blocks_per_pixel * 100
wpscript world/source/worldpainter/build-exp-009.js $scalePercent
wpscript world/source/worldpainter/build-exp-009.js $scalePercent export
```

The first command creates an editable `.world`; the second also exports a
Minecraft save. The script uses the 1.20.5-or-later Anvil format selected by
WorldPainter for Minecraft 1.21.1. Before production use, open the `.world` and
verify the biome IDs, Deciduous layer, water fill, border/export settings, and
spawn point in the installed WorldPainter version. Road and event masks become
WorldPainter annotations; `place-town.mcfunction` then grades lots, clears
building envelopes, lays the main dirt path and plaza, and places templates.
The script is source-ready
but unexecuted until `wpscript` exists.
