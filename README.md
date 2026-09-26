# cobblers

A private multiplayer **Cobblemon** campaign: a handcrafted, difficult Pokémon-style
region inside Minecraft for a small group of friends, inspired by ROM hacks such as
Run & Bun and Pokémon Imperium.

Read [docs/vision/GAME_VISION.md](docs/vision/GAME_VISION.md) for what we are making
and [CLAUDE.md](CLAUDE.md) for the working rules every contributor (human or agent)
follows.

## Where to find things

**What is built, decided and open right now:** [docs/STATE.md](docs/STATE.md). It is the one current record; every
other document is background.

| You want | Read |
| --- | --- |
| The game we are making | [docs/vision/GAME_VISION.md](docs/vision/GAME_VISION.md) |
| The story: acts, towns, leaders, side quests | [docs/story/ARC.md](docs/story/ARC.md), [docs/story/SIDEQUESTS.md](docs/story/SIDEQUESTS.md) |
| How a mechanic works: death and wipe, water, level caps, rewards | [docs/mechanics/](docs/mechanics/), in particular [DEATH_AND_WIPE.md](docs/mechanics/DEATH_AND_WIPE.md) and [WATER_MAP.md](docs/mechanics/WATER_MAP.md) |
| Why something was chosen | [docs/decisions/](docs/decisions/README.md) (the ADRs) |
| Whether a feature was proven in game | [experiments/](experiments/): one folder per proof, with its results |
| The world: towns, routes, the ocean, structures | [docs/world-building/](docs/world-building/) |
| What Cobblemon and the addons really support | [docs/research/](docs/research/) |
| The data the game is generated from | [data/](data/) (authored); `tools/` turns it into `build/` (disposable) |
| The server and how staging is rebuilt | [server/README.md](server/README.md), [docs/world-building/REEXPORT.md](docs/world-building/REEXPORT.md) |

Work in progress lives on branches with draft pull requests until the owner merges it; a document linked from a PR
is readable on GitHub even before it reaches `main`.

## Relationship to Cobbleverse

The [COBBLEVERSE](https://modrinth.com/modpack/cobbleverse) modpack is our
**reference and base experience**. A local snapshot consistent with Cobbleverse
1.7.42 (Minecraft 1.21.1, Fabric, Cobblemon 1.7.3) lives under `base-pack/`.

We do not fork it. We layer on top of it:

```text
Cobbleverse 1.7.42 (upstream, unmodified reference)
        +
Cobblemon 1.8.x compatibility overlay   (modpack/manifest/overlay.json)
        +
our pack configuration                  (modpack/config, modpack/overrides)
        +
our campaign design                     (data/, generated into build/datapack)
        +
our authored world                      (source/ + data/ + kits/ -> build/world)
```

When Cobbleverse ships its own Cobblemon 1.8 release, the compatibility overlay
shrinks or disappears and the campaign overlay moves across unchanged.

## Target versions

| Component | Base (Cobbleverse 1.7.42) | Target |
| --- | --- | --- |
| Minecraft | 1.21.1 | 1.21.1 |
| Loader | Fabric (>= 0.18.4 required by the pack) | Fabric 0.19.5 |
| Cobblemon | 1.7.3 | **1.8.x** (1.8.0 released 2026-09-06) |
| Java | 21 | 21 |

The Minecraft version does not change. The migration risk is Cobblemon addon
compatibility, not Minecraft compatibility. The current overlay applies 13
versioned replacements, removes Better Pokédex Scanner and Raid Dens, and keeps
PlayerXP out of the dedicated server; details in
[docs/research/COBBLEVERSE_COMPATIBILITY.md](docs/research/COBBLEVERSE_COMPATIBILITY.md).

## Repository layout

| Path | What belongs here |
| --- | --- |
| `CLAUDE.md` | Rules for every working session; principles; agent delegation |
| `.claude/` | Claude Code agents, rules, skills, settings |
| `docs/vision/` | Gameplay philosophy |
| `docs/research/` | Compatibility matrix, capability matrix, experiment backlog, research notes |
| `docs/architecture/` | Layer model, what runs where, what is committed |
| `docs/mechanics/` | Mechanic designs once experiments prove them |
| `docs/decisions/` | Architecture Decision Records |
| `docs/world-building/` | Verified reusable-structure catalog, placement workflow, palette, and town kit |
| `base-pack/` | Upstream Cobbleverse snapshot (config, licenses) plus inventory/hashes. **Never edited in place.** |
| `modpack/` | The client pack players install: manifests, overlay, our config, resource packs |
| `server/` | Dedicated server reproduction: config templates, launch docs, assembly and boot-test scripts |
| `source/` | Heightmap, masks, Gaea project. Irreplaceable, **outside this repo**, pinned by sha256. See `data/notes/source_tree.md` |
| `data/` | The design: cells, events, placements, spawns, trainers, gyms, progression, routes. Hand-edited, the real product |
| `kits/` | Reusable build assets: structure library, palettes, biome kits, schematics, templates |
| `derived/` | Generated analysis: slope masks, site index, path networks, sightlines. Disposable |
| `build/` | Generated output: datapack, world export, server bundle. Disposable |
| `experiments/` | One folder per experiment (EXP-NNN) with README, results, and run logs |
| `tools/` | Analysis, generators, manifest and validation tooling (Python, stdlib only) |
| `tests/` | pytest checks that the repository is internally consistent |

## How compatibility testing works

1. `tools/pack_manifest.py plan --side server` prints the target mod set: base pack
   minus removals plus replacements from `modpack/manifest/overlay.json`.
2. `server/scripts/assemble-server.ps1` copies the server-side jars into a server
   directory from a local source of jars (jars are never committed).
   `tools/assemble_client.py` creates the corresponding disposable client instance.
3. A human accepts the Minecraft EULA in that directory. Scripts never do this.
4. `server/scripts/boot-test.ps1` boots the server, captures logs and crash reports
   into `experiments/EXP-000-cobblemon-1.8-compat/runs/`, and prints a verdict.
5. Failures become rows in the compatibility matrix with a documented action
   (update, remove, replace, isolate). Then boot again. Then functional smoke tests
   with a connected client.

See [experiments/EXP-000-cobblemon-1.8-compat/README.md](experiments/EXP-000-cobblemon-1.8-compat/README.md).

## What is not committed

Mod jars, resource-pack zips, shader packs, the Cobbleverse datapack zips (their
license prohibits redistribution), server list files, world saves, logs, crash
reports, `eula.txt`, and any secrets. Binaries are represented by manifests with
hashes and source URLs under `base-pack/inventory/` and `modpack/manifest/`, and a
download tool under `tools/`. Rationale in
[docs/architecture/TECHNICAL_ARCHITECTURE.md](docs/architecture/TECHNICAL_ARCHITECTURE.md).

## Where things go

- A new encounter table, trainer team, gym, or dungeon design: `data/`.
- The generator that turns it into a datapack: `tools/`. The datapack itself is
  output in `build/` and is never hand-edited.
- A structure, schematic or palette it needs: `kits/`.
- Where that structure stands: `data/placements.json`.
- A server-only setting or script: `server/`.
- A question about whether the game can do something: `docs/research/` and an
  experiment under `experiments/`.
- A decision that constrains future work: `docs/decisions/`.
