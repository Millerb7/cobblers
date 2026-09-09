# cobblers

A private multiplayer **Cobblemon** campaign: a handcrafted, difficult Pokémon-style
region inside Minecraft for a small group of friends, inspired by ROM hacks such as
Run & Bun and Pokémon Imperium. Not a mandatory Nuzlocke.

Read [docs/vision/GAME_VISION.md](docs/vision/GAME_VISION.md) for what we are making
and [CLAUDE.md](CLAUDE.md) for the working rules every contributor (human or agent)
follows.

## Status

**Bootstrap / compatibility audit.** No campaign content exists yet, on purpose.

| Milestone | State |
| --- | --- |
| Repository structure, docs, agent system | done (this commit) |
| Base pack inventory and compatibility matrix | done, see `docs/research/` |
| EXP-000 boot test of Cobbleverse on Cobblemon 1.8 | **not run yet**, next step |
| EXP-001 to EXP-007 capability experiments | backlog only |
| Route 1, gyms, dungeons, story | not started, gated on EXP-000 |

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
our campaign systems                    (campaign/, modpack/datapacks)
        +
our authored world                      (world/)
```

When Cobbleverse ships its own Cobblemon 1.8 release, the compatibility overlay
shrinks or disappears and the campaign overlay moves across unchanged.

## Target versions

| Component | Base (Cobbleverse 1.7.42) | Target |
| --- | --- | --- |
| Minecraft | 1.21.1 | 1.21.1 |
| Loader | Fabric (>= 0.18.4 required by the pack) | Fabric |
| Cobblemon | 1.7.3 | **1.8.x** (1.8.0 released 2026-09-06) |
| Java | 21 | 21 |

The Minecraft version does not change. The migration risk is Cobblemon addon
compatibility, not Minecraft compatibility. Four mods hard-pin Cobblemon 1.7.3 and
three of them already have 1.8 builds; details in
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
| `base-pack/` | Upstream Cobbleverse snapshot (config, licenses) plus inventory/hashes. **Never edited in place.** |
| `modpack/` | The client pack players install: manifests, overlay, our config, our datapacks, resource packs |
| `server/` | Dedicated server reproduction: config templates, launch docs, assembly and boot-test scripts |
| `campaign/` | Authored campaign data: encounters, trainers, gyms, bosses, gauntlets, dungeons, quests, rewards, dialogue, progression |
| `world/` | Reproducible world assets: WorldPainter sources, schematics, structure NBT, templates |
| `experiments/` | One folder per experiment (EXP-NNN) with README, results, and run logs |
| `tools/` | Manifest and validation tooling (Python, stdlib only) |
| `tests/` | pytest checks that the repository is internally consistent |

## How compatibility testing works

1. `tools/pack_manifest.py plan --side server` prints the target mod set: base pack
   minus removals plus replacements from `modpack/manifest/overlay.json`.
2. `server/scripts/assemble-server.ps1` copies the server-side jars into a server
   directory from a local source of jars (jars are never committed).
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

- A new encounter table, trainer team, gym, or dungeon design: `campaign/`.
- A datapack that implements it: `modpack/datapacks/`.
- A structure or schematic it needs: `world/`.
- A server-only setting or script: `server/`.
- A question about whether the game can do something: `docs/research/` and an
  experiment under `experiments/`.
- A decision that constrains future work: `docs/decisions/`.
