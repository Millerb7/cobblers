# kits/

Reusable building blocks that content is assembled *from*, as opposed to the
design itself, which lives in `data/`.

| Path | Holds |
| --- | --- |
| `kits/structures/` | The structure library: donor NBT, provenance manifests, licences |
| `kits/palettes/` | Block palettes: which blocks make up a road, a roof, a cliff face |
| `kits/biome-kits/` | Biome kits: the vegetation, surface and decoration rules for a landscape identity |

## structures/

Preserved intact through the restructure. All 72 structure ids in
`manifests/structure-dependencies.json` resolve, and this is the infrastructure
worth keeping from the retired prototype work.

- `campaign/` donor NBT organised by role
- `manifests/structure-dependencies.json` component and world-critical map
- `manifests/pokemon-town-donors.json` donor provenance, licences, hashes
- `manifests/structure-source-evidence.json` archive hash evidence
- `licenses/` licence notices that must travel with the NBT

The MIT notice in `licenses/` is a condition of use. It moves with the files.

## palettes/ and biome-kits/

Empty. These are authored when the first region is built for real, not before.
A palette invented without a place to use it is a guess.

## What does not belong here

Anything with a position. A structure in `kits/` is a template; the decision to
put one at a coordinate is a placement and lives in `data/placements.json`.
