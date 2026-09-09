---
description: Datapack and campaign data conventions — JSON validity, namespaces, overlay instead of editing upstream
paths:
  - "modpack/datapacks/**"
  - "campaign/**"
  - "base-pack/cobbleverse/datapacks/**"
---

# Datapacks and campaign data

Owner of: file validity, namespaces, and the upstream/overlay boundary for
data. Runtime proof is in `testing.md`; formats are documented in
`docs/research/`, not here.

## Upstream is read-only

- `base-pack/cobbleverse/datapacks/**` is a reference snapshot. Never edit,
  unzip-and-edit, or delete anything there. To change upstream behavior,
  place a file at the same namespaced path in a datapack under
  `modpack/datapacks/` — later packs override earlier ones — and record the
  override in the datapack's README so the collision is deliberate.
- Do not copy whole upstream datapacks into `modpack/datapacks/`; override
  the specific files, so an upstream update stays diffable.

## Validity

- Every `.json`, `.mcmeta` and `.json5`-style config must parse. Run
  `python tools/validate.py` (when present) before claiming a change is done;
  otherwise parse each written file. Trailing commas and comments are not
  valid JSON.
- `pack.mcmeta` `pack_format` must match Minecraft 1.21.1 (data packs use
  format 48). Do not guess other version numbers; check the Minecraft wiki.
- Filenames and namespaces: lowercase, `a-z0-9_-./` only. Authored content
  uses our own namespace; never write into `minecraft:` or `cobblemon:`
  namespaces except to deliberately override an upstream file.
- Cobblemon and addon JSON fields are only as documented in
  `docs/research/` or shown by a working example in the base pack. An
  undocumented field is a research question, not a guess.

## Separation

- `campaign/` holds authored design data with rationale; `modpack/datapacks/`
  holds what the game loads. When both exist for one thing, the campaign file
  is the source and the datapack file is derived from it — say which tool or
  step derives it.
- Datapacks are loaded by the server for gameplay data; anything client-side
  (models, textures, lang) is a resource pack under `modpack/resourcepacks/`.
