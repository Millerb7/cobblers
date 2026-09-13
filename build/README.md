# build/

**Disposable output.** Nothing here is authored and nothing here is edited by
hand. Delete the whole directory at any time and rebuild it.

The contract is the same as `derived/`: everything must be reproducible from
`source/`, `data/` and `tools/` alone.

Expected contents:

| Path | Produced by | Holds |
| --- | --- | --- |
| `build/datapack/` | step 5 generators | the campaign datapack: spawn files, trainer JSON, functions, loot |
| `build/world/` | WorldPainter export automation | the exported Minecraft save |
| `build/server/` | server assembly scripts | the runnable server bundle, mods plus config plus world |

Two things that are emphatically not build output and must never be written
here: the live server's world save once players have touched it, and anything
authored by a human. A world that has been played is no longer reproducible from
source, so it is a save to be backed up, not a build artifact.

The contents are gitignored. This README is not.
