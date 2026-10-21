# Handover: session 7698338d, ended 2026-10-21 ~01:50

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-20-fossick` (worktree `.claude/worktrees/mods-182`, holds `derived/`, `build/`, kits). Contains main and
PR #151's head; adds Fossick (R9OCF), the client pack fixes, the Kyogre lantern, Groudon's quake cavern and its review
fixes, STATE. Pushed as ONE draft PR that replaces #151 (the owner: "combine all of them"); #151 is left open for the
owner to close. Head and PR number: see the PR; re-read with `git fetch --prune` and `gh pr list`.

## 2. Where it stopped
- **LIVE is UP at 12G since 01:41** (pid 49280), launched as a Bash background task OF THIS SESSION: it dies when the
  session ends. The next session must check the PROCESS first and, if it is down, start it durably (section 3).
- Install done and verified (STATE "Live install 2026-10-21 01:41"). The coordination lock is RELEASED.
- Friends' bundle: `C:/Users/wnd/Documents/cobblers-client/cobblers-client-0.1.0-bundle.mrpack` sha1 fa8febab (client
  zip c7a58c9f inside; AllTheMons v4.0 required). Private.

## 3. Waiting on the owner
- **A durable launch:** a one-shot Task Scheduler start (asked; needs a yes), or the owner runs
  `server/scripts/start-live.ps1` from their own PowerShell window. The WMI launch died after 44 min.
- Raise the owner's level cap (RCT records through Giovanni) to catch Kyogre/Groudon? Unanswered.
- Groudon's blackout exemption (no item loss if it wins a full-party battle), as Kyogre has? Unanswered; not applied.
- Mod updates: 17 on Modrinth (STATE Runtime line). Batch later with a bundle rebuild.
- In game: the Groudon quake (log in with gym8_cleared, go to the eastern Craters bowl ~(6706, 5510)); Fossick's hill
  adit at (6764, 5804); the Kyogre shrine lantern; enable the client zip at the TOP of packs and name any Steve NPCs.

## 4. Do not rediscover
- The owner's account holds GRANTED flags (dive/surf, gym8_cleared, champion_cleared, kyogre attuned, groudon met); RCT's
  defeat records were not changed, so they disagree for that account.
- install and strip refuse a world inside the runtime: stop, `mv cobblers-server/cobblers-10240 cobblers-server-next/`,
  run, move back. `strip` needs `--world-dir`.
- `presence_audit.py` with no `--only` ran past 15 min; its `--only` names (arena,gulch,dens,relic,extra) do not include
  world_probes places by name: probe a place's blocks directly (data/world_probes.json places.<id>).
- A prepare refuses itself if data/ or tools/ change while it runs (happened once tonight); it also needs the lock env.
- `tests/test_training_grounds.py::test_shared_records_are_in_step_with_the_generator` fails on main too.
- Steve NPCs left: dungeon bosses/probes/fights (`tools/dungeon*.py` NPC_RESOURCE) and arenas.
- Groudon review's open item: a blackout-rebuilt legendary loses our tag, so a later R14L could summon a second one
  (all legendaries, not fixed).

## 5. Cost
~960 turns, context over 300k at the end, weighted ~50M (`tools/session_cost.py`). Agents: Groudon builder (Sonnet),
Opus review, Opus fixer.
