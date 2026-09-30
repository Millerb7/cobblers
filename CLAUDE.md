# Cobblers — a Cobblemon campaign

A handcrafted, difficult Pokémon-style region inside Minecraft, played
cooperatively by a small group of friends on a private Cobblemon (Fabric)
server. `docs/vision/GAME_VISION.md` is the design source of truth and
`docs/architecture/TECHNICAL_ARCHITECTURE.md` the technical one. Where a
document and the repository disagree, say so — the disagreement is a finding,
never something to paper over silently.

## Session state (required)

Read `docs/STATE.md` before doing any work. It is the operational record of
what is built, decided, open and blocked; when another document disagrees,
verify reality and correct the state rather than rediscovering the question.
Before ending every session, reconcile every affected line in `docs/STATE.md`
without adding history; if no state category changed, report that it was
reviewed and remains current. Follow its file-ownership table when making the
update. Then write the handover ("Session length").

At session start, after the live-server safety checks below, run
`python tools/install_check.py --server-dir <server>`, adding
`--world-dir <staging world>` for staging (never the live world). It checks
packs and configs. It reads the server's `config/` and `datapacks/` folders,
and a world's folder only when passed a staging one. Report every problem it
lists before doing other work. Work done in the repo that never reached the
running game has happened four times: the spawn tables; five config overlays,
starters among them; the re-apply steps; and the structures pack, present only
because it had been copied by hand.

## Live server safety (hard gate)

Before any command that could access the local `cobblers-server` runtime, make
a process/port check the first server-related action and acquire the shared
external lock at `C:\Users\wnd\Documents\github\.cobblers-server-agent.lock`.
Create the lock atomically outside the server tree and record the owning
agent/task and timestamp. If port 25565, a Minecraft Java process, or the
coordination lock is active, stop without enumerating the runtime. Do not
assume an existing coordination lock is stale merely because the server is
down; resolve ownership with the user or other agent first.

**A server started with PowerShell `Start-Process` does not outlive the tool
call.** On 2026-09-30 the staging server was booted that way, answered RCON,
was reported up, and then died silently: its console log ends mid-startup with
no shutdown line and no crash, and it had been down for three and a half hours
before the owner asked. Nothing was lost only because that boot ran no steps.
Start it detached (the Bash tool's `run_in_background`), and before reporting a
server up, check the PROCESS, not just that RCON answered once.

Claude Code and Codex must never enumerate, read, copy, hash, inspect, or back
up the live world directory at
`C:\Users\wnd\Documents\github\cobblers-server\cobblers-10240`. This includes
`session.lock`, region, entity, POI, player, data, and dimension files. Seed a
disposable test world only from a designated offline snapshot made while the
server was stopped. If no suitable snapshot exists, stop and ask for one.
Never delete `session.lock`; a persistent lock error requires identifying the
owning process or handle before recovery.

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
- **Target, reached:** Cobblemon 1.8.x on Minecraft 1.21.1 Fabric. The
  server runs Cobblemon 1.8.0+1.21.1 on Fabric Loader 0.19.5 (`docs/STATE.md`
  "Runtime"); the baseline above is the reference pack's, not the server's.
  Same Minecraft version, so the compatibility question is addon API/data
  compatibility, not MC version.
- **Base-pack systems:** trainers = Radical Cobblemon Trainers (`rctmod` +
  `rctapi`, data-driven via datapack JSON); Mega Evolution = Mega Showdown;
  TMs = TMCraft (Cobblemon 1.8 also adds native TMs); badges =
  CobbleverseBadges; raids = Cobblemon Raid Dens; breeding = Cobbreeding;
  economy = CobbleDollars.
- **World-critical (blocks/worldgen):** Rechiseled, CobbleFurnies, Carved
  Wood, Pokeblocks, Cozy Home, Handcrafted, Moar Concrete, VanillaBackport,
  LumyMon, Beautify, LegendaryMonuments, Waystones, Comforts,
  cobblemon-additions, Repurposed Structures, Biome Replacer. **Not**
  world-critical here: the Terralith datapack and the Hoenn, Johto and Sinnoh
  region datapacks (`datapacks/extra`). Cobbleverse ships them optional
  (`global_packs.toml`), our world has had them disabled since its first
  export, and they are almost all world generation for new chunks, which a
  pre-exported WorldPainter world inside its border never makes. No authored
  data references a Terralith biome (checked 2026-09-26).
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
| `CLAUDE.md`, `README.md`, `.gitignore`, `.gitattributes` | Root identity and repository policy |
| `.claude/` | Assistant configuration (agents, rules, skills); see `.claude/README.md` |
| `docs/vision/GAME_VISION.md` | The game we are making; design source of truth |
| `docs/research/` | `COBBLEVERSE_COMPATIBILITY.md`, `EXPERIMENT_BACKLOG.md`, `notes/` — verified vs assumed facts, with sources |
| `docs/architecture/TECHNICAL_ARCHITECTURE.md` | Technical source of truth for layers and boundaries |
| `docs/mechanics/` | Mechanic designs (level caps, encounters, rewards) before they become content |
| `docs/decisions/` | ADRs: `README.md`, `TEMPLATE.md`, `ADR-001-modpack-base-strategy.md`, … |
| `base-pack/` | Cobbleverse reference snapshot (`cobbleverse/`) and its inventory (`inventory/`); never edited |
| `modpack/manifest/`, `mods/`, `config/`, `resourcepacks/`, `overrides/` | Our overlay = the players' client pack |
| `server/config/`, `scripts/`, `launch/`, `README.md` | Dedicated server; `server/scripts/boot-test.ps1` and `assemble-server.ps1` are the entry points |
| `source/` | Heightmap, masks, Gaea project. Irreplaceable, **outside this repo**, gitignored, pinned by sha256 in `data/world.json`. See `data/notes/source_tree.md` |
| `data/` | `world.json` (the single config); places: `cells.json`, `regions.json`, `landmarks.json`, `towns.json`, `placements.json`, `structures.json`, `routes.json`, `rivers.json`; encounters: `spawns.json`, `habitat_blocks.json`, `trainers.json`, `route_trainers.json`; progression and story: `progression.json`, `quests.json`, `dialogue.json`, `scenes.json`, `rewards.json`; the Rift: `rift_*.json`, `vr_caves.json`; systems: `blackout.json`, `water_mounts.json`; `notes/`. Gyms are placements plus trainer records; there is no `gyms.json` or `events.json` |
| `kits/structures`, `biome-kits`, `schematics`, `templates` | Reusable build assets; a template has no position. Palettes are documented in `docs/world-building/BUILD_PALETTE.md` |
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

Do the work directly when it is a few tool calls. Delegate only when the task
is large, independently scoped, and the result compresses into a summary.
One subagent, not several, when one can finish the job. Never spawn an agent
to check, confirm or rephrase another agent's output — verify with files, logs
and running Minecraft instead. Agents do not spawn their own agent teams.

| Need | Agent | Writes |
|---|---|---|
| Find where something lives (cheap) | `repo-scout` | nothing (read-only) |
| Mod/jar metadata, 1.8 compatibility status, EXP-000 | `dependency-auditor` | `docs/research/COBBLEVERSE_COMPATIBILITY.md`, `base-pack/inventory/`, `experiments/EXP-000-*` |
| What Cobblemon/addons actually support, with sources | `cobblemon-researcher` | `docs/research/` only |
| Campaign architecture, data models, datapack-vs-script-vs-mod boundaries, ADR proposals | `content-architect` | `docs/decisions/`, `docs/mechanics/` |
| Spawn/trainer/gym tables and the generators that emit a datapack | `datapack-content-dev` | `data/`, `tools/` |
| Server-side logic, progression/puzzle/gauntlet state | `minecraft-systems-dev` | `server/config/`, `modpack/config/`, `data/`, `tools/` |
| Place specs, placements, structures, schematics, templates | `world-content-dev` | `data/`, `kits/` |
| Encounter tables, level caps, boss/gym/gauntlet teams, rewards | `trainer-balance-designer` | `data/` |
| Validation tooling and tests | `test-author` | `tools/`, `tests/` |
| Review an experiment against its success criteria | `qa-reviewer` | nothing (read-only; reports) |
| Server/client boot failure triage | `build-doctor` | nothing (proposes fixes; reads logs) |

Read-only agents (`repo-scout`, `qa-reviewer`, `build-doctor`) do not need a
worktree; worktrees exist to keep concurrent writers apart.

**A refusal ends the attempt (the owner, 2026-09-28).** A subagent whose action
is refused (a permission prompt denied, a hook or safety check blocking a write,
a guard in a tool) stops that line of work and hands back: what it tried, the
refusal's text, and what it has so far. It never reaches the same outcome
another way (a different tool, the shell instead of Edit, a script, another
path). Every brief says so. On 2026-09-28 four builders hit the same worktree
guard: three stopped and reported; one wrote its files through Bash and Python
instead. The output was good; the workaround was still the failure.

**Launching a writing agent (verified 2026-09-28 with three throwaway agents).**
Two gates stand between an agent and a file, and both are the harness's: the
worktree isolation checks (no write, working directory or git redirect into the
main checkout, and every other worktree lies inside the main checkout's folder)
and the permission classifier (a judgment on each command; it refused a copy
from another checkout, and `rift_heightmap.py --plan` twice, although
`Bash(python tools/:*)` is allowed). So:

1. Commit what the agent needs; its worktree starts from this session's
   committed HEAD (`worktree.baseRef: "head"` in `.claude/settings.json`).
   Never prepare a worktree for an agent: it cannot write there.
2. Launch with `isolation: "worktree"`. First command, alone:
   `git rev-parse HEAD`; if it is not the commit you named, `git merge --ff-only
   <sha>`.
3. Kits: `python tools/local_inputs.py hydrate --store
   C:/Users/wnd/Documents/cobblers-local` (allowed: all 338 files, verified).
   Derived inputs (the Rift plan, the paint, the water shape) are refused to an
   agent, and `.worktreeinclude` copied none of them: give the agent work that
   does not need them, or run it in the main session.
4. The agent edits, runs its unit's own generator and its unit's tests. It never
   runs prepare, the full suite or staging.
5. Every brief carries the refusal rule above and the cost rules below.

**Measuring cost.** The harness's per-agent `totalTokens` and
`subagent_tokens` are the agent's FINAL CONTEXT, not its spend; reports built on
them were off by roughly 20x (2026-09-28: "3.0M" was 26.5M). Spend is every
turn's context added up: context x turns, cache reads at a tenth.
`python tools/session_cost.py` reports the real figure for a session and each
of its agents; quote that, never the harness's.

**Cost rules (the owner, 2026-09-28, from the measured night), each with its
reason:**

- **Never wait inside an agent**: no `sleep`, no polling, no command expected to
  run past about four minutes. *Past the prompt cache's lifetime the whole
  context is re-written; one builder's four ten-minute sleeps cost 1.6M.*
- **Never resume a finished agent for a small follow-up**; do it in the main
  session. *A resume re-sends the agent's whole context: about 0.4M to restart a
  300k agent before it does anything.*
- **Prefer more, smaller agents to fewer, larger ones.** *Cost is context x
  turns: carrying 350k through 157 more turns costs about 5M more than starting
  fresh at 15k. A split costs little; a long agent costs a lot.*
- **Integration is never delegated**: prepare, the full suite, staging, the
  merges. *They need inputs an agent cannot fetch and waits an agent must not
  make, and they run once for every agent's work.*
- **Research is worth delegating.** *The level-cap and model-route research
  agents cost 0.57M and 0.66M and each settled a question.*
- **Build work goes only to an agent with a shell.** An agent that cannot run
  what it writes (no Bash/PowerShell: `world-content-dev`, `content-architect`,
  `trainer-balance-designer`) may write data and docs, never a generator, an
  audit or anything that has to run. *The water-shape design wrote 2,300 lines it
  could not run, and a second agent re-read everything to debug them.*
- **Batch fixes before sending tests back**, in one message. *Each round is a
  full re-read.*
- **Do small items yourself.** A fix of a few files, a data edit, an install or
  a staging check is done in the main session, not delegated.
- **Say the expected cost first**, measured as above: before spawning more than
  one subagent, tell the owner which agents, what each does and the rough cost,
  and wait for approval.
- **Say up front when a task will iterate on something expensive** (the whole
  heightmap, a full re-apply, the full suite), with how many passes, so the
  owner can choose fewer. *One water-shape agent spent 812,000 tokens over three
  hours re-running the full pipeline.*

**Content implementation and its test/review use different agents:** whoever wrote a
datapack does not write its validator or grade its experiment. Implementation
does not grade its own work.

## Context cost (the owner, 2026-09-29, after the overnight run)

Context is the bill. A session pays for its whole context on every turn, so anything that enters it is paid for
again by every turn that follows. The 2026-09-29 night averaged 431k a turn over 464 turns and cost 23.2M; most of
that was not thinking, it was tool output that arrived once and was then re-sent hundreds of times.

- **Run the cheap gates first.** `validate_data`, then the per-tool audits, then the expensive 80-job `prepare`
  once the data is known good. On 2026-09-29 `prepare` was run **four times** because it fail-closed at a different
  step each time -- the Rift sculpt plan, `route_events`, `shrines`, then the orphaned ferry function. Each run cost
  its whole output and most of its time before failing on something a cheaper check would have named in seconds.
  This is worth more than piping the output of the runs you then have to repeat.
- **Tool output: pipe it.** `tail`, `grep`, `head`, or a one-line summary. A `prepare` that touched 4,468 files
  needs its **verdict** in context, not its listing. A test run needs its failures, not its passes: `-q --tb=line`
  and `| tail`. Never let a tool print a path list, a JSON dump or a full audit body into the transcript.
- **Audits: write the result to a file, read back only the failures.** A 35-step audit that passed is one line. If
  it failed, read the failing entries, not the document. `> <file> 2>&1` then `grep -E "PROBLEM|FAIL|mismatch"`.
- **Subagents: brief them to report in under 500 words**, with the detail written to a file the main session reads
  only if it needs it. Their full findings belong in the repo, not in the orchestrator's context.
- **Do not re-read what you just wrote.** The Edit or Write result already says what changed. Re-reading a file to
  "check" an edit that did not error buys nothing and is paid for on every later turn.
- **Compact between phases, not at the end.** This is the big one. Tonight carried phase 1's tool output all the way
  into phase 4. Compact at each phase boundary with the handover already written, so the next phase starts near the
  cold-start floor instead of on top of everything before it.

  **Only at a phase boundary, never mid-phase** (the owner, 2026-09-29). Each compaction is a summarisation pass and
  each pass loses detail. At a boundary that is safe, because the next phase does not need the last one's tool
  output: the export does not need the experiment's `/tick query` readings, and the report does not need the
  export's region listings. **In the middle of a debugging run it is not safe** -- the thread of what was tried, what
  it printed and what that ruled out is exactly the detail a summary drops, and losing it means re-running the
  expensive thing that produced it. If a phase is long and expensive, end it properly and start the next one; do not
  compact inside it.

The ranking matters, because the discipline is not free: **compacting between phases is worth more than the other
four together.** Trimming output slows the growth within a phase; compaction resets it.

## Session length (the owner, 2026-09-28)

A long session is the single most expensive thing we do. The 2026-09-28 main
session cost 32.9M on its own, more than its thirteen agents together, at an
average 517k of context per turn: every turn re-sends everything before it.

- **One session per job.** The water export is a session; the Rift build is a
  session. When the job ends, hand over and stop, even if the session still
  feels useful: it carries the cost of everything before it.
- **The signal is context per turn, not elapsed time.** Check with
  `python tools/session_cost.py` ("context now") at every unit boundary.
  Under 200k: carry on. 200k to 300k: compact if the job goes on, hand over if
  it is done. Over 300k: hand over. A cold session restarts at about 70k
  (docs/STATE.md alone is 29k of it: keep it to current state, never history).
- **Compact early, not at the end.** Compacting costs one pass; carrying 500k
  for fifty more turns costs 2.5M. Compact at a unit boundary with the
  handover already written, so nothing lives only in the conversation.
- **The handover is part of ending a session, not something the owner asks
  for.** Before a session stops (job done, or over the threshold), it rewrites
  `docs/HANDOVER_SESSION.md` so a cold session starts for almost nothing:
  1. the branch, its head sha, its PR and whether that PR is frozen;
  2. where the job stopped: the last thing done and verified, the next step as a
     command, and anything half-done (a branch, a worktree, a running server,
     a held lock);
  3. what waits on the owner: decisions, and in-game checks with coordinates;
  4. what a cold start must not rediscover: findings, refusals and dead ends
     from this session, one line each with the file or commit;
  5. what the session cost (`tools/session_cost.py`).
  Durable facts go to `docs/STATE.md`, not the handover. The cold session
  reads CLAUDE.md, STATE and the handover, and nothing else, before it starts.

## Git and commit hygiene

- **Only MIT-style sources may be committed.** Anything else (All Rights Reserved, no-redistribution,
  unknown) is used locally and gitignored. Provenance is mandatory for every structure template: a
  `kits/PROVENANCE.json` record with source and licence, plus a committed notice file for third-party
  permissive donors. `python tools/validate.py --only template_provenance` enforces it (pre-commit hook in
  `.githooks/`, enable with `git config core.hooksPath .githooks`; CI workflow `provenance`).
- `one issue = one branch = one worktree = one implementation session`.
  Verify `git branch --show-current` before the first edit; never edit another
  session's worktree. Mechanics: `parallel-work` skill.
- Never commit secrets, `eula.txt`, `servers.dat`, `ops.json`/`whitelist.json`,
  world saves, logs, or mod/resource-pack jars and zips. `.gitignore` already
  excludes them; do not work around it.
- Never push or merge to `main`, never force-push, never amend a pushed
  commit. Hand over with a draft PR (`open-pr` skill); marking it ready is a
  human act.
- **A reported PR's branch is frozen.** Once a PR is reported to the user or is
  open for merging, push nothing more to its branch: further work goes on a new
  branch (stacked on it if it depends on it) with its own PR. Before any push,
  check the branch's PR state (`gh pr view --json state`); if it is open or
  merged, branch off instead. (2026-09-16: PR #17 merged while six more commits
  were still being pushed to its branch, and main silently lacked them.)
- **Pin every merge to the reported head.** Report each PR with its full head
  SHA and the command `gh pr merge <N> --match-head-commit <sha>`, so a merge
  cannot pick up commits the report did not cover.
- **Verify main before dependent work.** Before starting work that depends on a
  merged PR, confirm the expected commit is on main
  (`git fetch` then `git merge-base --is-ancestor <sha> origin/main`); a PR
  marked merged is not proof that main has its final commits.

## Ground comes from the heightmap, never from a world

Every tool that decides where something goes takes its ground from `tools/ground.py` (the canonical
heightmap, rounded) or from measured plan data. It never reads the surface of a world save to decide a
position. A world holds whatever was built into it last, and a tool that reads its own output as ground
builds on top of itself. This has happened twice:

- the Displaced City cavern plan was regenerated from a world the previous carve had damaged, and
  followed the damage instead of the terrain;
- `tools/place_town.py` seated Brock's houses on ground read from a world that already held the town,
  and on a rebuild they climbed six to ten blocks above their own street.

Rounded, not floored: against a fresh export `round(h)` matches the exported ground at 99.85% of
columns and `floor(h)` at 52%. Reading a world to *check* a result (the verify passes,
`tools/town_audit.py`) is different and still required. `tests/test_ground_rule.py` fails if a
placement tool reads a world to decide.

## Verify before claiming

A generated config, datapack or manifest is not proof that a feature works. A
clean `python tools/validate.py` run proves validity, not behavior. **Any
expectation derived from the artifact being checked is not an expectation:**
audits compare generated output and world results with independent source or
plan data, and permanent fixtures must include nonempty partial output.
Important features are tested in a running Minecraft (the `boot-test` skill,
then a functional test recorded in `experiments/`). Report exactly what you ran
and observed; mark everything else "not verified". Never accept the Minecraft
EULA on the user's behalf.

## Context boundaries

- `base-pack/cobbleverse/` holds hundreds of config files and datapack zips.
  Grep there deliberately with a narrow path, never by default; prefer
  `repo-scout` or `base-pack/inventory/` when locating a mod or config.
- Path-scoped rules in `.claude/rules/` load automatically; long procedures
  live in `.claude/skills/`. Do not restate either here.
