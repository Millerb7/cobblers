# modpack/datapacks/

**Pack-level datapack overlays only.** These are compatibility fixes applied to
upstream datapacks so the base pack runs on our target Cobblemon version. They
are part of what players install, not part of the campaign.

Campaign content does **not** live here. It is authored as tables in `data/` and
generated into `build/datapack/` by a tool in `tools/`. See `data/README.md`.

The base pack force-loads `datapacks/` and `datapacks/extra/` through the
Global Packs mod (`base-pack/cobbleverse/config/global_packs.toml`). Overlays
here and the generated campaign pack must both be shipped the same way on
client and server, so an assembled instance gets
`base datapacks + overlays + generated`.

`tools/validate.py` checks that every datapack has a `pack.mcmeta`, that all
JSON parses, and warns on duplicate file names inside a namespace. Campaign
data checks live in `tools/validate_data.py`.

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
