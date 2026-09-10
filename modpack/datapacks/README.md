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

## Cobbleverse riding compatibility

Do not edit the licensed upstream `COBBLEVERSE-DP-v31.zip` in place. Its
Cobblemon 1.7 riding additions use offset-based seats that override Cobblemon
1.8's named model locators. Generate the runtime copy after the target
Cobblemon JAR and base datapacks have been assembled:

```powershell
python tools/patch_cobbleverse_riding.py base-pack/cobbleverse/datapacks/COBBLEVERSE-DP-v31.zip <runtime>/datapacks/COBBLEVERSE-DP-v31.zip --cobblemon-jar <runtime>/mods/Cobblemon-fabric-1.8.0+1.21.1.jar --expect-patched 51
```

The tool replaces seats only for species whose authoritative riding definition
exists in the target JAR. It preserves custom riding statistics and legacy
offsets for Cobbleverse-only mounts.
