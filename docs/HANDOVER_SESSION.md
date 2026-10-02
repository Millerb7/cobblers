# Handover: the consolidation of 2026-10-02 (session a292b1c5)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file. `docs/REVIEW_2026-10-02.md` lists every call made
while the owner was out; read it before reversing anything.

## 1. The branch

- **`build/2026-10-02-consolidation`**, one draft PR against main (re-read its head: `git fetch --prune; gh pr view
  <N> --json headRefOid`). It holds the five parallel sessions of 2026-10-02 (blockers on the south map, the south
  map audit, the server session's followups, the legendary stack #109-#112, water #113 plus `edc81c4`) and this
  session's agent wave.
- **Close without merging once it merges:** #109, #110, #111, #112, #113. Delete after: `build/2026-10-02-station-coast`,
  `claude/integration-blockers-outstanding-4ac1df`, every `worktree-agent-*` branch.
- **Not part of this job:** `codex/trainer-modes` holds Codex's only written finale, `docs/story/NPCS_AND_RIFT_FINALE.md`
  (commit 9cbfd213), local and unpushed; also `codex/handover-content`, `codex/celebi-sapling-narrative`,
  `codex/legendary-system-audit`, `codex/trader-stock-planning` (files that never reached main).

## 2. Where it stopped

- **Applied and verified in staging-2026-10-01** (18:15 apply, 18:24 restart): see STATE. `presence_audit` 250 of 260
  (was 72 of 257); `npc_seats.py verify` 20 of 20; `install_check` 0 problems.
- **Server UP**, pid 48868, launched `nohup ... & disown` (outlives the tool). `level-name` in server.properties is the
  LIVE world: always pass `--universe C:/Users/wnd/Documents/cobblers-staging --world staging-2026-10-01`.
  `enable-command-block=true`, `max-tick-time=60000` (a `reapply.py run` refuses until it is -1: set it with the
  server stopped).
- **The lock is held by this session**; release it (delete the file) or hand it over explicitly.
- Next, in order:
  1. The four open probes: the arena crown ring point (one of four at y127 round (3609, 3249) is air); three gulch
     coves whose probe positions disagree with the built functions (e.g. heart_lapidary_1: probe z4854, build z4808-4816).
     The six stale probes (relic centre, relic platform gravel, two pre-move residents, two Orchard Sleeper) need
     `data/world_probes.json` / `tools/presence_audit.py` updated.
  2. Switch Shrew Station's feather issuing on now that Zapdos and Moltres stand: a test author retargets
     `test_every_item_is_held_today`, then rebuild, install, R9RS.
  3. Hoopa's release scene in the cradle (invokes `rift_crisis_resolved`'s setter; then z5 can open, after the
     behind_league / league_gate walls are re-cut round G4/G5, strict-xfailed).
  4. The full suite once on the final head (not re-run after the last merges; the touched suites pass).

## 3. What waits on the owner

- The review list, `docs/REVIEW_2026-10-02.md` (19+ calls).
- EXP-048: which Pokemon appeared at the Crown Cemetery click (Calyrex or Spectrier); whether the anchorless bird
  altars need a `summon_anchor` (one right-click at (682, 312, 380) with a glacier feather).
- The Crown Cemetery's shaderoot crop cannot multiply (one plant, its own seed): the crown's price of 16 is
  unreachable. Design call.
- Wiremother L30's declared catch-gate leak; the moved jungle elders' 25-30 birds against the isle's 44-50.
- The southern map's thinness and the a-lite starters (EXP-049 has never run): not started.

## 4. Do not rediscover

- `reapply.py run` accepts a function reply starting "Running function" as success; a step that does nothing still
  prints "done". Probe the world after every apply.
- A fresh `build/` exposed two prepare jobs nobody had (lakebed_repair, ferry_docks) and mines_audit placed too early.
- Agent tests that skip for want of a jar hide failures: copy the server's Cobblemon and LumyMon jars (and, for
  `test_themed_saplings`, Cobbleverse's datapack zip and the Mega Showdown jar) into the gitignored
  `experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods`.
- The three EXP-048 "tooling causes" (clone, ritual block, 71 blocks) exist nowhere in code or transcripts.
- Shrew Station's lake cleanup is a STAGING pack (`research_station.py cleanup`), never part of the apply.

## 5. Cost

`python tools/session_cost.py` at the handover: main session ~59k a turn, agents together 8.3M weighted (before the
STATE agent).
