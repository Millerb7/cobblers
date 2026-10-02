# Handover: the consolidation of 2026-10-02 (session a292b1c5, worktree consolidate-parallel-sessions-b6b9d7)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file. The job: main holds everything the five parallel
sessions of 2026-10-02 built, as ONE PR, applied to staging and verified against the world.

## 1. The branch

- **`build/2026-10-02-consolidation`**, off main `1a4b85f`, pushed, **no PR yet** (open it only when the apply is
  verified; the owner wants one big correct PR). Re-read the head: `git fetch --prune; git rev-parse
  origin/build/2026-10-02-consolidation`.
- Merged, in order: `claude/blockers-on-south-map` `cee7430` (which already held the south branch to `b9e8963`, main
  and the server session's followups to `a2fb389`); `build/2026-10-02-followups` `aa5b5b9` (EXP-048 PASS, local
  only); `claude/south-map-world-audit-2219f3` `b6b1f0b` (Mega dens R9MD, Hoopa's HQ guard, Split-Bark 63); the
  legendary stack `0bebc5a` (#109-#112); water `b4cef78` (#113); cherry-pick of `edc81c4` (the water_shape fix that
  was only on local `claude/affectionate-chaplygin-fa86cd`).
- **Close without merging once the consolidation PR merges:** #109, #110, #111, #112, #113 (all inside it).
- **Delete after merge:** `build/2026-10-02-station-coast`, `claude/integration-blockers-outstanding-4ac1df`
  (`d198fcd`, superseded; its guard, validator fix and siting test were carried into blockers), the 38
  `worktree-agent-*` branches (every one is tip-contained or its work re-committed under the orchestrator's title).
- **Not part of this job, for the owner:** old Codex branches whose files never reached main:
  `codex/trainer-modes` (validate_trainers.py; an EXP-047 that collides with main's EXP-047-pocket-dimension),
  `codex/handover-content`, `codex/celebi-sapling-narrative`, `codex/legendary-system-audit`,
  `codex/trader-stock-planning`.

## 2. Where it stopped

Done and verified:
- All merges committed; data files merged by id and field from the index stages (refusing any field both sides
  changed). The touched suites: 209 passed; 2 resident tests wait on `build/` (prepare).
- **The owner's player progress on staging was reset, everything** (owner's choice): 32 scoreboard scores reset over
  RCON; after a clean `stop`, 20 per-player files (vanilla, advancements, stats, Cobblemon party/PC/pokedex/molang/
  player data, CobbleDollars, Cobblenav, TM moves, the RCT player record and the one-trainer RCT memory of the Brock
  defeat) MOVED to `C:/Users/wnd/Documents/cobblers-staging/player-reset-backup-2026-10-02/<uuid>/`. Left by
  decision: the recovery ledger's name registry, waystone ownership, a backpack's storage.
- `enable-command-block=true` set in the server's `server.properties` (was false; the Necrozma towers and Mew's door
  need it).
- **Server UP on staging** since 16:25:54, pid 54688, launched `nohup ... & disown` from a background task and
  checked alive after that task exited (it is not tied to a tool timeout). Command line:
  `java -Xmx16G -jar fabric-server-launch.jar nogui --universe C:/Users/wnd/Documents/cobblers-staging --world
  staging-2026-10-01` from `C:/Users/wnd/Documents/github/cobblers-server`. **`server.properties` level-name is
  `cobblers-10240`, the LIVE world: never boot without `--universe/--world`.**
- **The lock is HELD by this session** (taken over from `cobblers-cobblemon-session-start-531d15` with the owner's
  approval). RCON needs `COBBLERS_SERVER_LOCK=<lock path>` and `COBBLERS_LOCK_OWNER=<its owner line>` (runtime_guard).

Next, in order:
1. **The Jungle Isle residue (the owner's in-game notes 3 and 4), decision B15 "jungle isle should be removed":**
   - A dirt prism y56-128 capped by an underwater-ruin template stands at x5140-5180, z7470-7500, read from the
     staging world 2026-10-02: `ruin_great_hall` from its old y126 seat. `data/placements.json` re-seated the six
     `jungle_ruins` ruins to y59-62 on 2026-09-30, but nothing removed the old builds. And at the NEW seats four of
     the six overlap Pacifidlog by 496 columns (STATE). Proposed: retire the `jungle_ruins` placements, and a
     one-off clear of the old seats' volumes in staging (old positions from git before the 2026-09-30 re-seat).
   - The four drowned jungle elders (`elder_jungle_east_1/2`, `elder_jungle_west_1/2` in `data/elder_trees.json`,
     pinned to pre-water ground) hang 17-68 blocks in the air with their nests. The owner: "need to be moved". New
     sites are a design call; the old trees need clearing.
2. `python tools/local_inputs.py hydrate --store C:/Users/wnd/Documents/cobblers-local`; copy `derived/` from the
   primary checkout (`C:/Users/wnd/Documents/github/cobblers/derived`, gitignored, ~198 MB; rift_sculpt cannot be
   rebuilt anywhere). `validate_data`, then `reapply.py prepare` once, then the full suite.
3. After prepare, check the water packs (R9LL, R9SL) against the new builds: neither generator reads Shrew Station,
   the Old Orchard, the Mega dens, the Hollow or the Khan. The apply order already puts water first so a build wins.
4. Warn the owner, then stop, install (with `max-tick-time=-1`), boot detached, check the PROCESS, run the batched
   steps (`docs/HANDOVER_SOUTH.md` section 3: R9Z, R9RU, R9DU, R9HF, R9SO, R9E, R18DU, R18HF, R18SO, R18R; plus R9RS,
   R9MD, R9LL, R9SL, R18A, R18S, R9LH and the Spectrier cap), then `run --only R17N` and `python tools/npc_seats.py
   verify`, then `presence_audit.py`. The owner's notes 1-2 (no Mega mine or south-Rift changes; the shrine still on
   Shrew Lake) are this apply, never run because the lock was held all day.
5. Rewrite STATE in one pass from the world, open the draft PR with its head pinned.

## 3. What waits on the owner

- **Feathers and Kubfu's scrolls have two authors**, both inert: Shrew Station's Director (`data/research_station.json`
  economy, issuing false) and the Frostpeak camp's dialogue (`data/frostpeak_camp.json` item_economy, not built).
  Recommended: scrolls, crown and dews at the station; feathers via the camp, per the owner's later quoted words.
  The station's ember survey still targets the Nether structure; Moltres is now in the Craters.
- **EXP-048's species**: the two sessions relayed Calyrex and Spectrier for the same click.
- **Wiremother L30** is a declared catch-gate leak (pinned in `tests/test_resident_encounters.py` as the only one).
- New sites for the four jungle elders.

## 4. Do not rediscover

- Text-merging data JSON loses records; merge by id from `:1:/:2:/:3:` (the scratch tool was a 90-line three-way
  merge refusing any field both sides changed). Formats: most data files are `json.dumps(indent=2)`;
  `adopted_legendary_sites.json` is indent=1; `research_station.json` and `frostpeak_camp.json` are hand-formatted.
- `cobblers_ursaluna_cave` had been listed twice in reapply's generated-pack list since blockers (an earlier text
  merge); it broke 29 install_check tests. Fixed in `e301dcf`.
- #107 and the encounter rebuild share no file, id or co-located species; their overlap was resident levels against
  tier ceilings.
- The Pacifidlog pillar is dirt, not an elder trunk (nearest elder 240 blocks away).

## 5. Cost

`python tools/session_cost.py`: 139 turns at the handover, context 316k (average 216k), weighted 3.9M. No agents.
