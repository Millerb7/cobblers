---
description: Campaign data and generated datapack conventions — JSON validity, namespaces, overlay instead of editing upstream
paths:
  - "data/**"
  - "build/datapack/**"
  - "base-pack/cobbleverse/datapacks/**"
---

# Campaign data and the generated datapack

Owner of: file validity, namespaces, and the upstream/overlay boundary for
data. Runtime proof is in `testing.md`; formats are documented in
`docs/research/`, not here.

## The datapack is generated

`data/` is authored and version controlled. `build/datapack/` is generated from
it by a tool in `tools/` and is disposable.

- Never hand-edit anything under `build/`. It is regenerated and the edit is
  lost. If something cannot be generated, that is a missing field in `data/`;
  raise it rather than writing the file by hand.
- Everything in `build/` must be reproducible from `source/`, `data/` and
  `tools/` alone. If reproducing it needs a remembered parameter or a file that
  exists nowhere else, it is in the wrong place.
- Generators translate, they do not decide. A generator that invents balance,
  placement or naming has taken an authoring decision that belongs in `data/`.

## Upstream is read-only

- `base-pack/cobbleverse/datapacks/**` is a reference snapshot. Never edit,
  unzip-and-edit, or delete anything there. To change upstream behavior,
  generate a file at the same namespaced path into our pack — later packs
  override earlier ones — and record the override in `data/` so the collision
  is deliberate.
- Do not copy whole upstream datapacks into our pack; override the specific
  files, so an upstream update stays diffable.

## Validity

- Every `.json`, `.mcmeta` and `.json5`-style config must parse. Run
  `python tools/validate_data.py` for authored data and `python tools/validate.py`
  for file-level validity before claiming a change is done. Trailing commas and
  comments are not valid JSON.
- `pack.mcmeta` `pack_format` must match Minecraft 1.21.1 (data packs use
  format 48). Do not guess other version numbers; check the Minecraft wiki.
- Filenames and namespaces: lowercase, `a-z0-9_-./` only. Authored content
  uses our own namespace; never write into `minecraft:` or `cobblemon:`
  namespaces except to deliberately override an upstream file.
- Cobblemon and addon JSON fields are only as documented in `docs/research/`
  or shown by a working example in the base pack. An undocumented field is a
  research question, not a guess.

## Coordinates

No record in `data/` may carry a coordinate that has not been validated.
While `data/world.json` has a null `grid.origin_x`, a null `grid.origin_z` or a
null `heightmap.sha256`, positions cannot be checked against terrain and the
validator fails closed on all three. Author the non-spatial fields and leave
the anchors for when both land.

## Separation

- `data/` holds the authored design with its rationale; `build/datapack/` holds
  what the game loads. The data file is always the source and the pack file is
  always derived — name the tool that derives it.
- Datapacks are loaded by the server for gameplay data; anything client-side
  (models, textures, lang) is a resource pack under `modpack/resourcepacks/`.
- Reusable assets that content is assembled from — structure NBT, palettes,
  biome kits — live in `kits/`, not in `data/`. A template is a kit; the
  decision to put one at a coordinate is a placement and is data.

## Runtime facts learned the hard way (verified on staging)

- Cobblemon fires MoLang callbacks only from `data/cobblemon/callbacks/<event>/`.
  A file under our own namespace registers (the load count rises) but never runs.
  Add ours there with a `cobblers_` filename; never override Cobblemon's own files
  (EXP-042).
- `/reload` does not reload registry data: enchantments, damage types, worldgen.
  A change there needs a server restart (EXP-042 session 3).
- `spawnpokemonat` written in a function spawns nothing when the function was
  parsed at server start, and works after a `/reload` re-parses it; a **macro**
  line (`$spawnpokemonat $(x) ...`) works either way, so a keeper that must run
  after a plain restart spawns through a macro (EXP-046; EXP-042's "works" ran
  after the driver's `/reload`). Claim the spawn in the same function: an
  unclaimed Pokemon is despawned within a minute with no player near.
  `summon cobblemon:pokemon` is refused even with a full `Pokemon` compound. To
  recreate a Pokemon, spawn a placeholder and write the saved compound over its
  `Pokemon` data (EXP-042).
- An NBT filter cannot follow a list index (`list[0]{k:v}` does not parse). Copy
  the element to a named compound first, then filter that.
- A MoLang value read off a function call does not chain
  (`q.player.party.get_pokemon(0).species` returns the Pokemon). Assign the call
  to a `t.` variable first.
