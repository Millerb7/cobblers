# Cobblers — a Cobblemon campaign

A handcrafted, difficult Pokémon-style region inside Minecraft, played
cooperatively by a small group of friends on a private Cobblemon (Fabric)
server. `docs/vision/GAME_VISION.md` is the design source of truth and
`docs/architecture/TECHNICAL_ARCHITECTURE.md` the technical one. Where a
document and the repository disagree, say so — the disagreement is a finding,
never something to paper over silently.

## Baseline and target (verified)

- **Reference/base experience:** the COBBLEVERSE modpack (Modrinth slug
  `cobbleverse`), local snapshot consistent with release 1.7.42 (2026-07-21),
  stored at `base-pack/cobbleverse/` — `config/` and `licenses/` are tracked;
  mod jars, resource-pack zips, shaderpacks and the Lumyverse datapack zips
  (no-redistribution license) are gitignored and described by
  `base-pack/inventory/*.json|csv|md`. The full snapshot exists only in the
  local checkout; the datapack contents are documented in `docs/research/notes/`.
- **Baseline:** Minecraft 1.21.1, Fabric loader (pack requires >= 0.18.4),
  Fabric API 0.116.14+1.21.1, Fabric Language Kotlin 1.13.13+kotlin.2.4.10,
  Cobblemon 1.7.3, Architectury 13.0.8, Java 21.
- **Target:** Cobblemon 1.8.x on Minecraft 1.21.1 Fabric (Cobblemon 1.8.0
  released 2026-09-06 for MC 1.21.1). Same Minecraft version, so the
  compatibility question is addon API/data compatibility, not MC version.
- **Base-pack systems:** trainers = Radical Cobblemon Trainers (`rctmod` +
  `rctapi`, data-driven via datapack JSON); Mega Evolution = Mega Showdown;
  TMs = TMCraft (Cobblemon 1.8 also adds native TMs); badges =
  CobbleverseBadges; raids = Cobblemon Raid Dens; breeding = Cobbreeding;
  economy = CobbleDollars.
- **World-critical (blocks/worldgen):** Rechiseled, CobbleFurnies, Carved
  Wood, Pokeblocks, Cozy Home, Handcrafted, Moar Concrete, VanillaBackport,
  LumyMon, Beautify, LegendaryMonuments, Waystones, Comforts,
  cobblemon-additions, Repurposed Structures, Biome Replacer, the Terralith
  datapack, and the region datapacks in `base-pack/cobbleverse/datapacks/extra`.
- **No KubeJS or scripting layer exists in the base pack.** Cobblemon itself
  has Molang-scriptable NPCs and datapack folders (1.8 adds `party_pools`,
  `party_compositions`, `moveset_builders`, and a Habitat Block for spawn
  control on adventure maps). Do not assert more than this about APIs without
  a cited source.

## Layer model

```
upstream   Cobbleverse pack + third-party mods      base-pack/   (read-only reference)
   ↓
overlay    our modpack: compatibility fixes, mod     modpack/     (what players install)
           list, configs
   ↓
server     dedicated server config, launch, scripts  server/
```

The world itself separates **world-as-data** from **world-as-blocks**:

```
source/    heightmap, masks, Gaea project, notes      irreplaceable, OUTSIDE the repo
data/      the design: cells, events, placements,     authored, version controlled,
           spawns, trainers, gyms, progression        THE PRODUCT
kits/      structure library, palettes, biome kits    reusable assets
tools/     analysis, generators, placement, validation
   ↓
derived/   slope maps, path networks, site index      disposable
build/     datapack, world, server bundle             disposable
```

**The rule:** anything in `derived/` or `build/` must be reproducible from
`source/`, `data/` and `tools/` alone. If it is not, it is in the wrong place.

Upstream content is never edited in place. It is overridden from the overlay,
or from a file our generators emit at the same namespace path.

A cell indexes location only: a square 1024-block planning label, rows A–H
north to south, columns 1–8 west to east. Region boundaries are a separate
concept that follows terrain and does not align to cell edges.

## Repository layout

| Path | What belongs here |
|---|---|
| `AGENTS.md`, `README.md`, `.gitignore`, `.gitattributes` | Root identity and repository policy |
| `.codex/config.toml`, `.codex/agents/` | Codex multi-agent defaults and project custom agents |
| `.agents/skills/` | Codex project skills |
| `.claude/` | Coexisting Claude Code agents, rules, skills, and settings |
| `docs/agent-system/CODEX_AGENTS.md` | Agent inventory, migration map, and model routing |
| `docs/vision/GAME_VISION.md` | The game we are making; design source of truth |
| `docs/research/` | `COBBLEVERSE_COMPATIBILITY.md`, `CAPABILITY_MATRIX.md`, `EXPERIMENT_BACKLOG.md` — verified vs assumed facts, with sources |
| `docs/architecture/TECHNICAL_ARCHITECTURE.md` | Technical source of truth for layers and boundaries |
| `docs/mechanics/` | Mechanic designs (level caps, encounters, rewards) before they become content |
| `docs/decisions/` | ADRs: `README.md`, `TEMPLATE.md`, `ADR-001-modpack-base-strategy.md`, … |
| `base-pack/` | Cobbleverse reference snapshot (`cobbleverse/`) and its inventory (`inventory/`); never edited |
| `modpack/manifest/`, `mods/`, `config/`, `resourcepacks/`, `overrides/` | Our overlay = the players' client pack |
| `server/config/`, `scripts/`, `launch/`, `README.md` | Dedicated server; `server/scripts/boot-test.ps1` and `assemble-server.ps1` are the controlled entry points |
| `source/` | Heightmap, masks, Gaea project. Irreplaceable, **outside this repo**, gitignored, pinned by sha256 in `data/world.json`. See `data/notes/source_tree.md` |
| `data/` | `world.json` (the single config), `cells.json`, `landmarks.json`, `events.json`, `placements.json`, `spawns.json`, `trainers.json`, `gyms.json`, `progression.json`, `routes.json`, `notes/` |
| `kits/structures`, `palettes`, `biome-kits`, `schematics`, `templates` | Reusable build assets; a template has no position |
| `derived/` | Generated analysis: slope and aspect masks, site index, path networks, sightlines. Disposable |
| `build/` | Generated output: datapack, world export, server bundle. Disposable, never hand-edited |
| `experiments/` | `README.md` template plus `EXP-NNN-<slug>/README.md` per proof (`EXP-000-cobblemon-1.8-compat` first) |
| `tools/` | `validate_data.py`, `validate.py`, `pack_manifest.py`, analysis tools and generators (Python, standalone CLIs) |
| `tests/` | pytest suites for tooling and content validity |

## Principles

1. Cobbleverse is the reference/base experience.
2. Cobblemon 1.8.x is the target unless explicitly changed.
3. Preserve desirable Cobbleverse features when compatible.
4. Our campaign owns progression, encounter balance, bosses, world design and story.
5. Never assume a custom mod is required.
6. Prefer existing functionality, configuration and data before custom code, in
   this order: Cobblemon native → compatible addon → Cobbleverse dependency →
   configuration → datapack → functions/commands → scripting layer →
   server-side companion → custom Fabric mod last.
7. Never fabricate Cobblemon APIs or config formats.
8. Unknown behavior becomes an experiment.
9. Do not casually add dependencies.
10. World-critical dependencies require extra scrutiny.
11. Avoid removing world-critical dependencies after serious map development begins.
12. Preserve multiplayer compatibility.
13. Keep upstream content separate from authored campaign content.
14. Do not treat the live world save as ordinary source code.
15. Use small proofs before large implementations.
16. Content implementation and test/review should preferably use different agents.
17. Important architectural choices require ADRs.
18. A generated configuration is not proof that a feature works.
19. Important features should eventually be tested inside a running Minecraft environment.
20. Do not build large amounts of campaign content before foundational mechanics are proven.

## Delegation

Delegate when independent work materially improves speed, context isolation,
or quality. Use 2–4 concurrent workers for normal complex tasks; use more only
when ownership boundaries are obvious. Do work directly when it is a few tool
calls. Do not spawn agents merely to appear agentic, duplicate the same
research, or ask one agent to rephrase another.

Route by difficulty and cost:

- **Luna medium:** repository search, inventory, metadata extraction, obvious
  reference tracing, and repetitive classification.
- **Terra medium/high:** the default serious worker for audits, research,
  bounded implementation, datapacks, tests, QA, and configuration.
- **Sol high:** architecture, multiplayer state, cross-system implementation,
  game balance, difficult integration, and runtime debugging.
- **Astra high:** exceptional review after Sol remains unresolved, disagreement
  on a major irreversible choice, or an explicit maximum-quality request.

Sol and Astra agents consume concise discovery summaries rather than scanning
the entire repository or reading huge logs. Every subagent returns status,
failures, relevant excerpts, file references, and the next step.

| Need | Agent | Writes |
|---|---|---|
| Find where something lives (cheap) | `repo-scout` | nothing (read-only) |
| Mod/jar metadata and 1.8 compatibility evidence | `dependency-auditor` | nothing (read-only; proposes updates) |
| What Cobblemon/addons actually support, with sources | `cobblemon-researcher` | nothing (read-only; returns a research note) |
| Campaign architecture, data models, datapack-vs-script-vs-mod boundaries, ADR proposals | `content-architect` | `docs/decisions/`, `docs/mechanics/` |
| Spawn/trainer/gym tables and the generators that emit a datapack | `datapack-content-dev` | `data/`, `tools/` |
| Server-side logic, progression/puzzle/gauntlet state | `minecraft-systems-dev` | `server/config/`, `modpack/config/`, `data/`, `tools/` |
| Place specs, placements, structures, schematics, templates | `world-content-dev` | `data/`, `kits/` |
| Encounter tables, level caps, boss/gym/gauntlet teams, rewards | `trainer-balance-designer` | nothing (read-only; proposes designs) |
| Validation tooling and tests | `test-author` | `tools/`, `tests/` |
| Review an experiment against its success criteria | `qa-reviewer` | nothing (read-only; reports) |
| Server/client boot failure triage | `build-doctor` | nothing (proposes fixes; reads logs) |
| Rare high-impact second opinion after Sol-level work | `architecture-reviewer` | nothing (read-only; Astra escalation) |

Read-only agents do not need a worktree; worktrees exist to keep concurrent
writers apart. Use worktrees only for substantial parallel implementation with
clean file ownership, not for search, audits, documentation lookup, reviews,
tiny fixes, or one-file edits. **Content
implementation and its test/review use different agents:** whoever wrote a
datapack does not write its validator or grade its experiment. Implementation
does not grade its own work.

## Git and commit hygiene

- `one issue = one branch = one worktree = one implementation session`.
  Verify `git branch --show-current` before the first edit; never edit another
  session's worktree. Mechanics: `parallel-work` skill.
- Never commit secrets, `eula.txt`, `servers.dat`, `ops.json`/`whitelist.json`,
  world saves, logs, or mod/resource-pack jars and zips. `.gitignore` already
  excludes them; do not work around it.
- Never push or merge to `main`, never force-push, never amend a pushed
  commit. Hand over with a draft PR (`open-pr` skill); marking it ready is a
  human act.

## Verify before claiming

A generated config, datapack or manifest is not proof that a feature works. A
clean `python tools/validate.py` run proves validity, not behavior. Important
features are tested in a running Minecraft (the `boot-test` skill, then a
functional test recorded in `experiments/`). Report exactly what you ran and
observed; mark everything else "not verified". Never accept the Minecraft EULA
on the user's behalf.

## Context boundaries

- `base-pack/cobbleverse/` holds hundreds of config files and datapack zips.
  Grep there deliberately with a narrow path, never by default; prefer
  `repo-scout` or `base-pack/inventory/` when locating a mod or config.
- Claude Code's path-scoped rules remain in `.claude/rules/`. Codex workflows
  live in `.agents/skills/`; custom-agent configuration lives in
  `.codex/agents/`. Keep both systems working.
