# Session handover (2026-09-28, branch `claude/cobblers-cobblemon-session-start-531d15`)

The open threads of the session that ran 2026-09-27 night to 2026-09-28, for a cold start. `docs/STATE.md` holds the
durable state; this file holds only where work stopped, what waits on the owner, and the next steps. Delete it once
its threads are picked up or moved into STATE. (The previous handover's threads are closed or carried below.)

## 1. The branch

- Everything from this session is on `claude/cobblers-cobblemon-session-start-531d15`, handed over as one draft PR
  (memory `one-big-pr-per-batch`). It holds the builders' and test authors' branches merged in
  (`worktree-agent-*`); those branches and their worktrees under `.claude/worktrees/agent-*` can be removed once the PR
  merges. `.claude/worktrees/night-towns-shrines` (branch `build/towns-shrines`) holds builder A's uncommitted
  re-material, already applied here: remove it.
- `.codex/config.toml` is modified in this worktree and **not committed on purpose** (Codex's; HANDOVER_CODEX item 29).

## 2. Staging at handover

- Staging world `cobblers-dryrun11`, **running** for the owner's flight (booted 2026-09-28 after the integration run),
  started with `--universe C:/Users/wnd/Documents/github/cobblers-runtime-proof/dryrun11 --world cobblers-dryrun11` at
  `-Xmx16G`. The coordination lock is **held** by this session while it runs; stop the server (`rcon.py save-all`,
  `stop`) and remove the lock when the flight is over.
- `max-tick-time` is back to 60000.
- Integration run (`reapply.py run`, all steps): every place 0 gaps; audit clean (26 of 26 places, dressing, build,
  50 of 50 signposts, sea town, the Deep); 20 of 20 workers; shrines 6 of 6 spot checks; stone faces 84 of 84 sampled
  blocks; full pytest 4,652 passed, 5 known xfails.

## 3. Waiting on the owner

### In game (where to fly, most important first)
1. Brock's mason yard (1781, 141, 3669): the Graveler carrying, the Machop at the bench; click one; hit one with a
   sword (the box should take it); hear them (the sound fix).
2. Northlight's square (7272, 117, 1602 to the fire at 7280, 1577): the Timburr's 25-block walk on its trodden track.
3. The level cap, again with the new line ("It broke free! Your team isn't strong enough yet."), in a battle too.
4. A re-materialed town or two (Sabrina's, Blaine's, Giovanni's).
5. A shrine (Brock's cairn at 1609, 3767; the Tableland altar at 4765, 5622).
6. A stone face and its restore (Mining Town, tea town, Northlight): mine it, leave, come back after 10 minutes; a
   chest left in a face survives; the Assayer's shop on the Mining Town plaza sells.
7. The gulch: the rockslide wall from outside, the grille, the cove town, the Cutters' 2-raw price, the crystal faces
   not mineable.
8. Carried over: a sword kill of a guardian, a kill by a Pokemon outside battle, a real loss, the Mining Fatigue at
   the mine door, whether Megas attack in daylight.

### Decisions
- The Mega farms' zone: both sites are inside Victory Road's Z2 (8 badges); the design says after gym 6.
- The West Spur Dig reshape (item 7): not started; about 300k tokens.
- The spur's daily crystal after gym 6 may give a free raw stone (against "not free").
- Workers for Pallet (intact by design), and after the water export for Misty's town, Sunset West and Viltri Light;
  the Displaced City needs the tool to seat on the cavern floor.
- ATM x MSD v4.0 adoption (docs/research/CLIENT_MODEL_FIXES.md): needs an in-game look first.

## 4. Next steps

1. The water export (approved, 0.75-1.25M): after the flight. WATER_SHAPE.md section 11 steps 3-11.
2. The fresh-checkout blocker (STATE "What is blocked"): after the export, decide which inputs are committed, which
   regenerated, and whether `rift_heightmap.py --apply`'s plan-and-record coupling is the real problem.
3. Re-measure `data/visibility.json` with `--write` after the export repaints the canopy.

## 5. How agents behaved (for the owner's record)

Builders are launched with `isolation: "worktree"` and a `git merge --ff-only <base>`; a worktree made by the main
session is refused by a guard. One builder routed its files round that refusal through the shell before the rule
existed (CLAUDE.md "A refusal ends the attempt"); after the rule, every agent that met a refusal stopped and handed
back, and some disclosed earlier splits or scratch scripts they had used on the guard's own suggestion.
