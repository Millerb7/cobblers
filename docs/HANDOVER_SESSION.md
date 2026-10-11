# Handover: session ce7100f5, ending 2026-10-11 (the owner: "hand over now")

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts. The owner's report:
`docs/MORNING_REPORT_2026-10-11.md`; the owner's decisions on it are in STATE ("Dungeons, the owner 2026-10-11").

## 1. Branch
`build/2026-10-09-dungeon-playtest` in worktree `.claude/worktrees/night-shift-engine-gym-9b76f2`, LOCAL ONLY (never
pushed since d77fd0d; no PR covers it). Re-read the head (`git rev-parse HEAD`); at hand-over it is the commit after
a44f8d9 that adds this file and STATE. One big draft PR for the batch is owed (memory: one big PR per batch).

## 2. Where it stopped, as commands
- **Still running when this session ended:** the integrator MEGA-INTEGRATE, branch `worktree-agent-a957ab31010595219`
  (last commit cc37ff3 at hand-over; 10 dungeon branches merged there, per-dungeon vault budgets, padded clocks back to
  derived, shared tests fixed; it was in its final test chunks). Its report goes to the dead session: read its branch
  instead. When it has stopped (`git log` shows no new commits for a while, or its worktree has no running pytest):
  `git merge --no-edit worktree-agent-a957ab31010595219` here, then `python tools/validate_data.py`, `python tools/id_authorship.py`,
  `python tools/dungeon_audit.py`, `python tools/dungeon_independent_audit.py` (full, ~2+ min with 14 dungeons).
- **Zero Dig:** the owner: "re-author it as its own dungeon or cut it" and "NOTHING ELSE GETS AUTHORED until I have
  played at least three". So CUT it from this install: remove the `zero_dig` record (and its rip, its roster status, its
  test file and §7 row), keep the history in git; re-authoring waits for the owner's play.
- **Compact framing:** the owner: NOT evil, heroes to themselves, throughout. Grep the new docs and data for "evil"
  (DUNGEON_PASS2.md's overnight section quotes "evil faction"; HAVEN_COMPACT_PASS.md O1) and reframe; the built points
  already follow ARC rules 3-5.
- **Then build and install** (staging; the owner may be on it: ask before stopping): lock, `reapply.py prepare`
  (~50 min), stop, hold `config/cobbledollars/bank.json`, `install --cobbleverse-dp C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/datapacks/COBBLEVERSE-DP-v31.zip`,
  restore the bank, `max-tick-time=-1`, boot at 12G in the terminal panel, `run --only R16DG,R16DR,R9ST,R18CP,R17N,R17 --no-reload`
  (dungeon shells and rips; the Scar Tarn; the Compact core points; the Compact route NPCs and seated trainers: confirm
  the step ids with `python tools/reapply.py prepare --list` and `steps()`), watchdog 60000, restart, check the process
  twice, release the lock.
- **Tell the owner which three to play first** (recommendation): **the Street** (city; its bands 1-3 rare pool means the
  prize shows at the owner's playtest band; rooftops over the street it walked), **the Patriarch** (great tree; rare pool
  1-3 and legendaries from 4; a 40-block descent back under the first fork), **Ash Bell** (nether wastes; the first new
  dungeon through the engine-scale fix). Set the playtest band with `scoreboard players set <player> dg.ptband <n>`
  (tag `cobblers.dg_playtest`). Rips for the new dungeons are on the test trail by the old mine, x1420-1680 z~4118.

## 3. Waiting on the owner
- **The draw design (report before any rework):** dungeons are not tied to biomes; progression gates the draw. Propose:
  what decides the band (progression vs sigil; the owner leans progression), which dungeons can be drawn per band,
  rotation per band, two players at one rip (own instance, own band: confirm in tools/dungeon.py slot assignment), where
  rips go. Design only, one agent at most, on the owner's go.
- Open from the report: Eternatus, Koraidon/Miraidon, Lugia/Registeel, Cistern/Temple Calendar, switching off old wild
  spawns, the Scar Tarn's respawning over-cap alphas, Giratina, bands 5-6 tuning, Compact O2-O10.

## 4. Do not rediscover
- The keeper's chain: one scheduled pass per live slot (tools/dungeon.py DISPATCH); a re-joined chain makes the audit's
  LIMIT fire (tested). Never `datapack enable` on staging (OOM). A pack must be in SERVER_PACKS to install.
- The vault budget: per dungeon from its own clock (MEGA-INTEGRATE); before that, authors padded clocks.
- 29 prize species need the AllTheMons subset (`model_gate`); no required prize may depend on it.
- Cost rules (memory: fanout-model-and-width-limits): authors on Sonnet, Opus for audits/design, max three
  unattended agents, play before building.

## 5. Cost
`python tools/session_cost.py`: this session 82.6M+ weighted over 1,320+ turns, context 925k at the end (far past the
line); agents 422.4M in all, about 223M of it on the night of 2026-10-11 against an estimate of 40-60M.
