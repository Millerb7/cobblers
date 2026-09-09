# modpack/

**modpack = base-pack manifest + our overrides.** Players install the result.

The base is the COBBLEVERSE modpack (Modrinth `cobbleverse`, release 1.7.42,
snapshot under `base-pack/`). We do not copy it here. Instead:

| Path | What it holds |
|------|---------------|
| `manifest/` | The machine-readable description of the pack: `base-cobbleverse-1.7.42.json` (every jar/zip of the base with hashes and Modrinth ids) and `overlay.json` (what we replace, remove, add, and exclude from the server). See `manifest/README.md`. |
| `mods/` | Empty in git. Jars are gitignored and populated by `tools/pack_manifest.py download` / `server/scripts/assemble-server.ps1`. |
| `config/` | Our config overrides. Files here shadow the base-pack config of the same relative path. |
| `resourcepacks/` | Our resource-pack additions (zips are gitignored; describe them in the manifest). |
| `datapacks/` | Our campaign datapacks (tracked, authored content). |
| `overrides/` | Anything else that must land in the instance root (e.g. `options.txt` defaults, `servers.dat`). |

Effective content = base files, minus `overlay.remove`, with `overlay.replace`
applied, plus `overlay.add`, plus everything under `config/`, `resourcepacks/`,
`datapacks/`, `overrides/`.

```
python tools/pack_manifest.py plan                 # what the pack contains after the overlay
python tools/pack_manifest.py plan --side server   # what a dedicated server needs
python tools/validate.py                           # structural checks on tracked content
```

Nothing under `modpack/` is a finished product yet; it is the foundation the
campaign content builds on.
