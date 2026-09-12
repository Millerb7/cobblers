# tools/

Standalone command-line tools. Python, mostly standard library; the terrain
tools additionally need `numpy` and `Pillow`. No framework, no plugin system,
no abstraction over engines or games we do not use.

## Terrain analysis

All four read the heightmap through `terrain.py`, which resolves the path and
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
| `route_path.py` | A* between two points, paying for climb | `derived/paths/` |
| `sightlines.py` | Raycasts from a viewpoint to named landmarks | `derived/sightlines/` |
| `slope_masks.py` | Exports slope, aspect and land masks as PNG | `derived/slope/` |

These produce **candidates**. A human picks. None of them decides where a town
goes, which way a road runs, or what a place looks like.

```bash
python tools/find_sites.py  --min-size 24 --max-slope 4 --top 20
python tools/route_path.py  --from 3400,3400 --to 4100,3900 --slope-weight 10
python tools/sightlines.py  --from 3400,3400 --eye 2 --target volcano:6654,6242
python tools/slope_masks.py --max-degrees 60
```

Useful flags: `--bbox X0,Z0,X1,Z1` restricts the site search; `--slope-weight 0`
gives a straight line and a high value hugs contours; `--max-slope` sets what
counts as impassable or unbuildable; `--world` points at a different config.

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
| `validate_data.py` | Schema, referential, integrity, progression and spatial checks on `data/` |
| `validate.py` | File-level structural checks: JSON parses, `pack.mcmeta` present, duplicate basenames |
| `pack_manifest.py` | Base manifest and overlay: `generate`, `resolve-overlay`, `plan`, `verify`, `download` |
| `assemble_client.py` | Builds the client instance from the manifest |
| `patch_cobbleverse_riding.py` | Patches upstream riding data for Cobblemon 1.8, out of place |
