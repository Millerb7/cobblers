# Technical Architecture

## Layer model

Two axes. The **delivery** stack decides which mods run:

```text
upstream Cobbleverse modpack and its mods         base-pack/        (reference, read-only)
          ↓
our modpack compatibility layer                   modpack/manifest/ (overlay: replace / remove / add)
          ↓
server                                            server/           (dedicated server reproduction)
```

The **world** is organised as data, not as blocks:

```text
source/     heightmap, masks, Gaea project        irreplaceable, OUTSIDE the repo
data/       cells, events, placements, spawns,    authored, version controlled
            trainers, gyms, progression, routes   THE PRODUCT
kits/       structure library, palettes, biome kits
tools/      analysis, generators, placement, validation
          ↓
derived/    slope and aspect masks, site index,   disposable
            path networks, sightlines
build/      datapack, world export, server bundle disposable
```

**The reproducibility rule.** Anything in `derived/` or `build/` must be
reproducible from `source/`, `data/` and `tools/` alone. If regenerating it
needs a manual step, a remembered parameter, or a file that exists nowhere
else, it is in the wrong place and belongs in `source/` or `data/`.

Each layer only depends on the layers above it. Nothing below edits anything above
it in place; changes are expressed as overlays, so an upstream update is a re-base
of the overlay, not a merge into a fork.

### Upstream (base-pack/)

The Cobbleverse 1.7.42 snapshot. Tracked: `config/`, `licenses/`, shader settings,
inventory and hashes. Not tracked: jars, resource-pack zips, shader folders,
Cobbleverse datapack zips (no-redistribution license), `servers.dat`. The snapshot
is evidence and a source for the manifest. **It is never edited.**

### Compatibility layer (modpack/manifest/)

- `base-cobbleverse-1.7.42.json`: every upstream component with hash, side, and
  (where resolved) Modrinth source.
- `overlay.json`: target versions plus `replace`, `remove`, `add`,
  `server_exclude`, and `needs_functional_test` lists, each entry with a reason.

`tools/pack_manifest.py plan` computes the effective mod set. This is the only
place where "which mods, which versions" is decided.

### Server (server/)

Configuration templates, launch documentation, assembly and boot-test scripts.
Client-only mods (34 in the base pack) are excluded by the manifest's side field.
The live server directory itself is not in the repository.

### Source (source/)

The Gaea project, the GIMP working files, the masks and the canonical heightmap.
Large, irreplaceable, and **outside this repository**: gitignored, located per
machine via `COBBLERS_SOURCE_ROOT`, and pinned by `sha256` in `data/world.json`.
The validator recomputes that hash and fails closed when it is null, the file is
missing, or the hashes disagree. Layout and current status are in
`data/notes/source_tree.md`.

### Campaign data (data/)

The design itself and the real product of this repository: `world.json` as the
single config, plus cells, landmarks, events, placements, spawns, trainers, gyms,
progression and routes. Hand-edited and version controlled.

Everything the game loads is **generated** from these tables by a tool in
`tools/` into `build/datapack/`. Nothing under `build/` is hand-edited; if
something cannot be generated, that is a missing field in `data/`. Keeping the
authored table and the emitted format apart lets the mod-specific format change
without rewriting the design.

`data/world.json` is the only place import parameters and the heightmap path
live. No tool carries its own copy of 40, 200, 62 or 8192. The input mapping is
expressed as fractions of full scale so it survives a change of heightmap bit
depth; the outputs are absolute Minecraft Y and never scale.

### Kits (kits/)

Reusable assets that content is assembled from: the structure library with its
provenance manifests and licences, block palettes, and biome kits. A template in
`kits/` has no position. The decision to put one at a coordinate is a placement
and lives in `data/placements.json`.

### Derived and build (derived/, build/)

Both disposable, both gitignored apart from their READMEs. `derived/` holds
analysis output; `build/` holds the datapack, the world export and the server
bundle. A world save that has been played is no longer reproducible from source,
so it is a save to be backed up, not a build artifact, and never belongs in
`build/`. If a save is ever committed, an ADR says why.

## What runs where

| Concern | Client | Server | Datapack | Script layer | World | Custom mod |
| --- | --- | --- | --- | --- | --- | --- |
| Pokémon models, animations, UI, minimap, shaders, performance | yes | no | no | no | no | no |
| Cobblemon core, addons with server logic (trainers, megas, raids, breeding) | yes | yes | data | no | no | no |
| Wild encounter tables | no | via data | **yes** (Cobblemon spawn pools) | no | placement | no |
| Trainer teams, AI, dialogue, gating | no | via data | **yes** (RCT JSON, verified format) | no | spawner blocks in structures | no |
| Level caps | no | config | series data | no | no | only if RCT's cap proves insufficient |
| Progression flags, badges, unlocks | no | state | advancements / functions | **candidate** | doors, gates | only if experiments show need |
| Puzzle and dungeon state | no | state | functions, scoreboards | **candidate** | redstone, structures | only if experiments show need |
| Gauntlet rules (healing, PC, reset) | no | state | functions | **candidate** | area design | possible, after EXP-004 |
| Structures, terrain, decoration | render | generate | worldgen JSON, NBT | no | **yes** | no |

"Script layer" today means Minecraft functions/commands and Cobblemon's own
Molang/NPC scripting. **No KubeJS or equivalent exists in the base pack.** Adding one
is a dependency decision that needs an ADR; it is not assumed.

Order of preference for any capability: Cobblemon native → existing compatible
addon → existing Cobbleverse dependency → configuration → datapack → functions and
commands → scripting layer → server-side companion → custom Fabric mod. A custom
mod is created only after an experiment shows simpler mechanisms fail.

## Client versus server

- The client pack is `modpack/` applied over the base: all mods, resource packs,
  and our config. Players install it with a launcher from a manifest.
- The server gets the same set minus client-only mods, plus `server/config/`.
- Datapacks must be identical on both, and Cobbleverse loads them through the
  Global Packs mod from the game directory's `datapacks/` folder, so the server
  needs the same folder layout.

## What is committed

| Committed | Not committed |
| --- | --- |
| Manifests with hashes and source URLs | Mod jars, `.mrpack`, resource-pack zips, shader folders |
| Our config overrides, our datapacks, campaign JSON | Cobbleverse datapack zips (license), Lumyverse menu art |
| Structure NBT, schematics, WorldPainter sources (LFS if large) | Live world saves, backups |
| Server config templates, scripts, docs | `eula.txt`, `ops.json`, `whitelist.json`, `servers.dat`, logs, crash reports |
| Experiment READMEs, results, selected run logs | Routine runtime logs, caches |
| Tools and tests | Secrets, credentials, `.env` |

Rationale for excluding binaries: GitHub blocks files over 100 MB (the Cobblemon
jar alone is 130 MB, three music packs are 89 to 171 MB), Git LFS on the free tier
would be exhausted by one clone, and per-mod licenses vary (several are
all-rights-reserved with curator-obtained permissions, the Lumyverse content forbids
redistribution). A manifest plus a download tool reproduces the pack without
redistributing anything.

## Multiplayer stance

Progression state is per player unless a design says otherwise. Any system that
holds state (dungeons, gauntlets, one-time rewards) must specify per-player versus
shared behavior and what happens on late join, mid-dungeon disconnect, and two
players triggering the same thing at once. This is a success criterion of every
experiment, not an afterthought.

## World-critical dependencies

Blocks, furniture, worldgen, biomes, structures, and world-affecting performance
mods (noise, chunk generation, lighting) must be frozen before serious map work.
Removing one later corrupts or alters the handcrafted map. The list is maintained in
`docs/research/COBBLEVERSE_COMPATIBILITY.md` under the WORLD-CRITICAL type and any
change to it requires an ADR once map construction has begun.
