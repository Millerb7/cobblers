# Handover: session 7698338d, 2026-10-20 night (context over 300k; the install continues from here)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-20-fossick` in worktree `.claude/worktrees/mods-182` (holds `derived/`, `build/`, kits). Head is the
merge `83b5463e` (Groudon's cavern 9d764bcc into Fossick) plus `6afe867a` (client pack) and `a88e4fb5` (Kyogre
lantern) below it. Not pushed, no PR. Open PR: #151 (`build/2026-10-20-next`), which this branch stacks on; the owner
said "combine all of them": hand over as ONE integration PR replacing #151. `git fetch --prune` and `gh pr list` first.

## 2. Where it stopped
- **LIVE is UP at 12G** (pid at start 24540, launched by the new `server/scripts/start-live.ps1`: Win32_Process.Create,
  survives tab/app resets, verified). **The lock IS HELD**: `C:/Users/wnd/Documents/github/.cobblers-server-agent.lock`,
  owner `claude-launch-2026-10-20c`. Every reapply/RCON call needs COBBLERS_SERVER_LOCK + COBBLERS_LOCK_OWNER set.
- **Running:** an Opus fix agent on the Groudon review's findings, branch `build/2026-10-21-groudon-fixes` from
  83b5463e: (1) HIGH the ravine rims become unguarded ~40-block cliffs: guard wall + audit must fail cut-made drops;
  (2) all stages fire in one tick; (3) the cut's slow falling is unaudited; (4) R14L can skip the carve silently and
  summon Groudon into rock if the old pedestal is gone: read `#built cobblers.gq` back; (5) late slow falling on rejoin;
  (6) blackout exempt tag. Review text: the Opus qa-reviewer's report in this session.
- **Next, as commands, once the fix agent returns:** review its report; `git merge` its branch into
  build/2026-10-20-fossick; gates (`validate_data`, `id_authorship`, `pytest tests/test_groudon_cavern.py
  tests/test_legendaries_rerun.py tests/test_system_contracts.py`); then ONE prepare:
  `COBBLERS_SERVER_LOCK=... COBBLERS_LOCK_OWNER=claude-launch-2026-10-20c python tools/reapply.py prepare --source-root
  C:/Users/wnd/Documents --server-dir C:/Users/wnd/Documents/github/cobblers-server` (~60 min; never edit data/ or tools/
  in this worktree while it runs: it refuses itself, and did once tonight). Then warn players, RCON stop, install, boot
  24G with max-tick-time=-1, `run --only` the Fossick step (R9OCF, check its plan for a town/signpost step) and R14L
  (Groudon's cleanup + carve) and R18KC (the Kyogre lantern) `--no-reload`; verify (presence_audit, groudon_cavern
  probes 10); restore max-tick-time 60000; strip; restart 12G with start-live.ps1; release the lock.
- **Before R14L on live:** confirm in game the old pedestal at (6672, 68, 5542) is still smooth_basalt (finding 4).
- Friends' bundle: `C:/Users/wnd/Documents/cobblers-client/cobblers-client-0.1.0-bundle.mrpack` sha1 fa8febab (also in
  build/client). Carries our client zip c7a58c9f (model fixes for the bundle stack, 98 NPC looks, rip) and AllTheMons
  v4.0 now REQUIRED and enabled. Private: COBBLEVERSE no-redistribution files inside.

## 3. Waiting on the owner
- Raise the owner's level cap (RCT records beaten through Giovanni) so Kyogre/Groudon can be caught? Asked, unanswered.
- In game: enable `cobblers-client-AllTheMons-subset.zip` at the TOP of the owner's packs (copied into the profile
  "cobblers-client-0.1.0-bundle"; that profile was then re-imported as "(1)", so it may need the new bundle instead);
  then report remaining Steve NPCs by name.
- Mod updates (Modrinth, 2026-10-20): 17 newer; recommended batch later, not tonight (list in this session's reply).

## 4. Do not rediscover
- The owner's account was GRANTED: dive/surf tags, `cobblers:flag/gym8_cleared` (ran Giovanni's first-win loot),
  `champion_cleared`, kyogre_cave sounded/attuned, groudon met. RCT's own defeat records were NOT changed, so the flags
  and rctmod disagree for that account (fine for a test account; `tools/carry_players.py badge_agreement` will say so).
- Kyogre's wake click works; it had no marker. A sea lantern was set live at (8226, 29, 2240) in cobblers:pocket and is
  now in `tools/kyogre_cave.py` (a88e4fb5). The catcher's pedestal (8228, 30, 2250) looks like the shrine.
- Rayquaza appears only when nobody is within 8 blocks of its crown spot (`spawn_clear`); it did appear.
- "Dolls" were mostly NPCs: the looks ship only in our client zip, which was not enabled. Steve NPCs left: dungeon
  bosses/probes/fights (`tools/dungeon*.py` NPC_RESOURCE) and arenas.
- `client_model_fix.py build` now restores pack-textured forms (Mega Showdown Megas etc.); scan on the bundle stack:
  uv 89 -> 2 (male Beautifly, Dustox), crash 6 -> 0. `--server-pack --no-donor` for a stack with AllTheMons v4.0.
- `tests/test_training_grounds.py::test_shared_records_are_in_step_with_the_generator` fails on main too.
- STATE's Runtime line still says Cobblemon 1.8.0; the server runs 1.8.2 since 2026-10-15 (mods/ checked). Fix it.
- Distant Horizons `/dh pregen` still fails immediately (unsolved).

## 5. Cost
893 turns, context 309k at handover, weighted 48.7M (`tools/session_cost.py`). Agents tonight: Groudon builder
(Sonnet, ~0.54M final context), Opus review (0.16M), Opus fixer (running).
