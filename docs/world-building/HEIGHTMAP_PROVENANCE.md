# The heightmap's provenance keys in `data/world.json`

The canonical heightmap is not authored in one step. It is the end of a chain of passes, and each pass records
the file it consumed under its own key in `world.json`'s `heightmap` object, with that file's sha256. A pass
always re-derives from *its own* recorded input, so running it twice never applies it twice.

**Every key names the pass's INPUT, not its output.** `heightmap.path` is the only key naming the current file.

That distinction is what went wrong on 2026-09-22: `tools/rift_heightmap.py` was written to read `sculpted_from`,
assuming it meant "the map before my sculpt". It means "the river cut that `tools/sculpt.py` consumed" — a
pre-rescale file three passes older. The tool silently worked against terrain from an earlier era; the basin came
back empty, which is the only reason it was caught. `tools/paint_maps.py` and `tools/validate_data.py` both read
that key with its real meaning, so redefining it would have broken them too.

**Before adding a pass, add a row here.** If a key you want already exists, it is taken.

## The chain

```
authored relief
   ↓  tools/grade_rivers.py cut          (input recorded as: derived_from)
land_8k_16_eroded_rivers.png
   ↓  tools/sculpt.py apply              (input recorded as: sculpted_from)
land_8k_16_sculpted_relief.png
   ↓  tools/rescale.py                   (input recorded as: rescaled_from)
land_8k_16_rescaled_b145.png
   ↓  tools/press_pads.py --apply        (input recorded as: pressed_from)
land_8k_16_rescaled_b145_pads.png
   ↓  tools/rift_heightmap.py --apply    (input recorded as: rift_sculpted_from)
land_8k_16_rescaled_b145_pads_rift.png   ← heightmap.path today
```

## The keys

| Key | Names | Written by | Also read by |
| --- | --- | --- | --- |
| `path` | **the current canonical heightmap** | whichever pass ran last | `tools/terrain.py` `resolve_heightmap`, and so every tool that asks for ground |
| `sha256` | its hash; `resolve_heightmap` refuses a file that does not match | the last pass | `tools/terrain.py` |
| `status` | must be `"ok"`; anything else makes terrain tools refuse | by hand | `tools/terrain.py` |
| `derived_from` | the authored relief the river cut consumed | `tools/grade_rivers.py` | `tools/grade_rivers.py`, `tools/validate_data.py` |
| `sculpted_from` | **the river cut that `sculpt.py` consumed** — not "before the Rift sculpt" | `tools/sculpt.py` | `tools/paint_maps.py` (the cut of the import), `tools/validate_data.py` (the import chain), `tests/test_sculpt.py` |
| `rescaled_from` | the sculpted relief the b145 rescale consumed | `tools/rescale.py` | `tools/paint_maps.py` |
| `pressed_from` | the rescaled map the pads were pressed on | `tools/press_pads.py` | `tools/press_pads.py` |
| `rift_sculpted_from` | the pressed map the Rift sculpt consumed | `tools/rift_heightmap.py` | `tools/rift_heightmap.py`, `tests/test_rift_heightmap.py` |
| `previous_sha256` | every hash the canonical file has had, newest first | every pass | — |
| `revision_note` | prose about the current revision | by hand | — |
| `width` | the image's width in pixels, one per block | by hand | `tools/terrain.py` |
| `height` | the image's height in pixels, one per block | by hand | `tools/terrain.py` |
| `channel` | which channel carries the height (`gray`) | by hand | `tools/terrain.py` |
| `bit_depth` | 16: the samples a pass reads and writes | by hand | `tools/terrain.py`, every pass |

## Rules for a new pass

1. **Pick a key nothing else uses**, named for your pass, not for its position in the chain. `sculpted_from`
   sounded generic and was not.
2. **Record the input's path and sha256**, and verify that hash before reading it. If it does not match, stop —
   do not fall back to the canonical file.
3. **Always start from your own recorded input**, so a second run re-derives rather than compounding.
4. **Append the old hash to `previous_sha256`** and leave every other key alone.
5. `resolve_heightmap` already returns the right file and verifies it. Do not second-guess it: read a different
   file only through your own key, and only for the purpose that key names.

## What the ceiling means

`vertical.max_y` is 310 and the export is invoked with `--world-high=310`: the 16-bit samples map onto y10..y310
for the **whole world**. Nothing sculpted can pass y310 without rescaling every existing landform, so a pass that
wants more height must put the excess in blocks and accept that it is re-applied after each export.
