# Session handover (2026-09-28, session 419ff6d9, ended at 360k context per turn)

For a cold start: read CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before starting. STATE holds the
durable facts; this holds where work stopped. Rewrite it at the end of every session (CLAUDE.md "Session length").

## 1. Branches and PRs

- #84 (the overnight batch) and #85 (a fresh checkout prepares) are **merged**; both heads verified on main (2026-09-28).
- `tooling/cost-rules-and-prepare-speed` (head: the commit adding this file), draft PR against `main`, frozen once reported: the local store and `worktree.baseRef`; `prepare --only/--from`; the gulch build 30x faster; the shared reach walk; quote-matched citations; `tools/session_cost.py`; the CLAUDE.md cost and session-length rules.
- `.codex/config.toml` is modified in this worktree and **never committed** (Codex's; HANDOVER_CODEX item 29).
  `git commit -a` sweeps it in: stage files by name.
- #84 has merged, so the `worktree-agent-*` branches and `.claude/worktrees/agent-*` can go, and
  `.claude/worktrees/night-towns-shrines` (builder A's re-material, already applied) can be removed.

## 2. Where the job stopped

- Done and verified: every item of the owner's 2026-09-28 cost request (the PR bodies list what was run).
- **Staging is running** for the owner's flight: world `cobblers-dryrun11`, `--universe
  C:/Users/wnd/Documents/github/cobblers-runtime-proof/dryrun11`, `-Xmx16G`. The coordination lock is **held by this
  session** (owner string "Claude Code session cobblers-session-start-531d15 (overnight: ambient workers proof and
  builds on staging dryrun11)"). When the flight is over: `python cobblers-server/rcon.py save-all`, then `stop`,
  then remove `C:\Users\wnd\Documents\github\.cobblers-server-agent.lock`.
- Next job, in a NEW session: the water export (approved, 0.75-1.25M), `docs/world-building/WATER_SHAPE.md` section
  11 steps 3-11; then re-measure `data/visibility.json` with `--write`.

## 3. Waiting on the owner

### In game (most important first)
1. Brock's mason yard (1781, 141, 3669): the Graveler carrying, the Machop at the bench; click one; hit one with a
   sword (the box should take it); hear them.
2. Northlight's square (7272, 117, 1602 to the fire at 7280, 1577): the Timburr's 25-block walk.
3. The level cap's new line ("It broke free! Your team isn't strong enough yet."), in a battle too.
4. A re-materialed town (Sabrina's, Blaine's, Giovanni's).
5. A shrine (Brock's cairn at 1609, 3767; the Tableland altar at 4765, 5622).
6. A stone face and its restore (Mining Town, tea town, Northlight); a chest left in a face; the Assayer sells.
7. The gulch: the wall from outside, the grille, the cove town, the Cutters' price, the crystal faces not mineable.
8. Carried over: a sword kill of a guardian, a kill by a Pokemon outside battle, a real loss, the Mining Fatigue at
   the mine door, whether Megas attack in daylight.

### Decisions
- The Mega farms' zone: both sites are inside Victory Road's Z2 (8 badges); the design says after gym 6.
- The West Spur Dig reshape: not started, about 300k.
- The spur's daily crystal after gym 6 may give a free raw stone (against "not free").
- Workers for Pallet, and after the export for Misty's town, Sunset West and Viltri Light.
- ATM x MSD v4.0 adoption (`docs/research/CLIENT_MODEL_FIXES.md`): needs an in-game look.

## 4. Do not rediscover

- An isolated agent's worktree starts at the session's committed HEAD (`worktree.baseRef: "head"`, verified); it may
  hydrate kits from `C:/Users/wnd/Documents/cobblers-local`; the classifier refuses it `rift_heightmap.py --plan`
  ("Irreversible Local Destruction", then "Production Reads"); `.worktreeinclude` copied nothing (removed).
- The Rift sculpt protects town footprints: `--plan` sculpts with those `--apply` recorded (`data/world.json`
  `heightmap.rift_sculpted_from.footprints`), because the League and the rim post moved after the sculpt.
- `data/routes.json` was adjusted after routing; `data/route_paths.json` is committed, never regenerated.
- The per-agent token figure from the harness is final context, not spend: `tools/session_cost.py`.
- Bash heredocs in this environment turn `\\n` into a newline inside Python source: write scripts with Write/Edit.
- Prepare leaves stale files in `build/` (14 stripped templates found); harmless, not yet cleaned.

## 5. What this session cost

`python tools/session_cost.py`: this session 37.6M weighted over 674 turns (average 463k context per turn); its 16
agents 26.8M, of which the three throwaway launch tests 0.3M.
