# modpack/datapacks/

**Our campaign datapacks live here** (tracked, authored content): encounter
tables, trainers, loot, structures, progression data, Cobblemon spawn/species
overrides. One folder per datapack, each with a `pack.mcmeta`.

The base pack force-loads `datapacks/` and `datapacks/extra/` through the
Global Packs mod (`base-pack/cobbleverse/config/global_packs.toml`). Our packs
must be shipped the same way on both client and server, so the assembled
instance gets `base datapacks + these`.

`tools/validate.py` checks that every datapack has a `pack.mcmeta`, that all
JSON parses, and warns on duplicate file names inside a namespace. Campaign
specific checks (duplicate ids, unknown Pokemon, broken references) are
extension points in that script and are not implemented yet.
