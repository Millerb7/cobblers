# modpack/mods/

Jars are **not tracked** (`.gitignore`: `modpack/mods/*.jar`). This folder is
populated by tooling from the manifest:

```
python tools/pack_manifest.py download --target modpack/mods          # dry run: prints what it would fetch
python tools/pack_manifest.py download --target modpack/mods --yes    # actually downloads + verifies hashes
python tools/pack_manifest.py verify modpack/mods                     # missing / extra / hash mismatch
```

The list of jars comes from `modpack/manifest/base-cobbleverse-1.7.42.json`
with `modpack/manifest/overlay.json` applied. Jars with no recorded Modrinth
URL (see `resolution.unresolved` in the base manifest) must be copied from a
local Cobbleverse install.
