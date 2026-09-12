# derived/

**Disposable.** Everything here is generated and nothing here is authored.

The contract: anything in `derived/` must be reproducible from `source/`,
`data/` and `tools/` alone. If regenerating it needs a manual step, a
remembered parameter, or a file that exists nowhere else, it is in the wrong
place and belongs in `source/` or `data/`.

Expected contents once the step 4 analysis toolkit lands:

| Path | Produced by | Holds |
| --- | --- | --- |
| `derived/slope/` | slope and aspect exporter | slope and aspect masks as PNG for WorldPainter |
| `derived/sites/` | buildable-site finder | ranked flat-area candidates with size and slope |
| `derived/paths/` | path router | A* polylines between points, contour-following |
| `derived/sightlines/` | sightline checker | raycast results from a point to named landmarks |

Every artifact records the heightmap `sha256` it was computed from, so a stale
derivative can be detected rather than trusted.

The contents are gitignored. This README is not.
