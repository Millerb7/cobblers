# Session handover (2026-09-28 night, session 88461346, ended at its threshold: 273k context per turn)

For a cold start: read CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before starting. STATE holds the
durable facts; this holds where work stopped.

## 1. Branches and PRs

- **#89 and #90 are merged and verified on main**, pinned to their reported heads (`c61487e`, `7b5496f`). #90 had been
  opened against `design/stone-faces`, so it was retargeted to main first.
- **PR #91**, `tooling/prepare-loop-sweep`, draft, **head `2f987ab`**, base main. Two commits: the prepare sweep, then
  the determinism fix, the hash-seed pin, the mines-test hold and the STATE marine correction. **Frozen now it is
  reported**: further work goes on a new branch stacked on it.

  ```
  gh pr merge 91 --match-head-commit 2f987ab
  ```
  (re-read the PR's head before merging; the second commit landed after the PR was opened.)
- `.codex/config.toml` is modified in the worktree and **never committed** (Codex's): stage files by name.
- **The gym-interiors design landed and is committed**: `docs/mechanics/GYM_INTERIORS.md` (391 lines), by a
  `content-architect` agent off `2f987ab`, copied out of its worktree into this branch. **It is a proposal, not
  accepted**: its own step 4 is "ADR proposed, owner accepts", and it says no gym content should be authored before
  that. Its agent worktree (`worktree-agent-a5c7b45c78e489c10`) is spent and removable. Read the doc itself; it is self-contained and ends with nine open questions and a ten-step plan. **Q1 blocks everything**: no interior floor plan of any gym template exists in the repo, so the NBTs must be extracted locally (gitignored, never committed) and a y-slice dumped before any room is designed against real geometry.

## 1b. FIRST, AND IT IS NOT ABOUT GYMS: the mixed-progress rematch fault

The owner, 2026-09-28: the most important thing to come out of the gym design, and it is a trainer-system fault.

`tools/route_trainers.py:151-152` writes a trainer's hold-off `Cooldown` **only when every player near it has beaten
it**. Two players at different progress never satisfy that, so no cooldown is written and **the player who already
won is pulled into a rematch while their partner is still fighting**. It affects **every placed trainer in the game
the moment two people play** -- the 13 Route 1-3 trainers, the 5 mansion Channelers, and every gym trainer that gets
built later. Read from the generated line; **never observed in game**.

The fix is a per-player hold-off rather than a shared `Cooldown`, following the mansion's shape (gate on the
trainer's per-player win field, `STATE.md` "Gastly mansion details"). Confirm it in game with two players first --
EXP-034 has never run, and it is also what gates Sabrina's gym below. Recorded in `docs/STATE.md`, World facts.

## 2. THE NEXT JOB: dive and sky portals. Run it in this order

The owner's instruction, explicit: **the experiment first, then the researcher only if the experiment leaves gaps,
then the design. Not the other way round.** Do not write the design first.

### 2.1 What ADR-004 already settles (do not re-derive)

`docs/decisions/ADR-004-pocket-spaces.md`, Accepted 2026-09-26, with an in-game Xaero cache test on staging. Dive
caves and sky islands are both "elsewhere", so they are the **first real use of the pocket dimension, which has never
been built**. On paper it answers:

- **What it takes:** a **vanilla** datapack `dimension` + `dimension_type`, added with one server restart. It needs
  its own spawn rules, a re-application step (does not exist), and sky, light, time and weather chosen to match.
- **What a player notices:** a short loading screen; the dimension name in F3 and a jump in coordinates; a separate
  entry in the map's dimension list; no overworld horizon; **sent-out Pokemon recalled**; players outside no longer
  visible.
- **Re-export:** it survives, because WorldPainter never touches it — but its contents must still be reproducible
  from data, and per-player instancing needs per-player coordinates inside it.
- Also settled there: the western-ocean chamber grid is **dropped**; the Xaero status effects hide the map but do not
  stop the cache; Distant Horizons is a second, independent leak that rules out far-overworld pockets.

### 2.2 The four unknowns ADR-004 does NOT cover

1. Do **our compiled spawn pools** work in a custom dimension? (`compile_spawns.py` emits `spawn_pool_world/...`;
   whether a dimension condition is needed, and whether the suppression follows, is unknown.)
2. Do **Habitat Blocks** work there?
3. Do **our systems' callbacks** fire there (blackout, the level-cap catch block, scenes)?
4. Can a dive portal **put a player in water in another dimension without drowning them on arrival**?

### 2.3 The collision found here, VERIFIED — it shapes the dive design

- `build/datapacks/cobblers_blackout/.../surface/tick.mcfunction` and the ladder functions have **no dimension
  filter**: grepped for `dimension`, `overworld`, `minecraft:the_` — nothing. The swim-fatigue clock therefore runs in
  a pocket dimension exactly as in the overworld.
- ADR-004 says **sent-out Pokemon are recalled on crossing**. The tick's first branch is
  `execute if score #ride bo.tmp matches 1 run return run function cobblers:surface/recover`, so a recalled mount
  means `#ride` is 0.
- **Therefore: a player who rides a Dive mount through a portal arrives no longer riding, underwater, with the
  fatigue clock already running.**
- **Mitigating, also verified:** qualification is *party*-based (the `cobblers.dive` tag plus a party read, not the
  sent-out entity), so the recall does **not** strip their training. They arrive as a trained swimmer with the air
  ladder: half fatigue rate, not an instant drowning. But it is still an unmounted arrival under water.
- **Design consequence:** a dive portal must arrive in air, arrive in wading-shallow water, or re-seat the rider.
  Decide this before siting any portal.

### 2.4 The contract entry to add (specified, not added — and why)

Not added here on purpose. `.claude/rules/testing.md` requires a new contract to arrive **with its test in the same
change**, and `data/system_contracts.json` entries name a consumer system. The portal system does not exist yet, so an
entry now would have no consumer and no test and would break `tests/test_system_contracts.py`. Add it **with the
design**, as C15, shaped like C1:

- `id` C15, `title` "A portal arrival never drowns the arriving player"
- `owner` `portals` (new system; add it to the `systems` list too)
- `consumers` `["water_ladder"]`, `constrained_by` `["swim_fatigue"]`
- `statement`: "A player crossing a dive portal arrives either in air, in wading-depth water, or re-seated on their
  mount; in no case does the arrival leave them submerged and unmounted with the swim-fatigue clock running."
- `stated_in`: cite the design doc's arrival rule once written, plus `ADR-004` on recall.
- Its test belongs to a **test-author agent**, not the designer.

### 2.5 The experiment that settles all four unknowns — run this first

One throwaway pocket dimension on staging: a portal in, a Habitat Block, a compiled spawn pool, and an arrival in
water. Record it as `experiments/EXP-NNN-pocket-dimension/` (the `experiment` skill). Take the coordination lock and
follow the live-server gate. It should answer, in one sitting: 1-4 above, plus the arrival case in 2.3.

**Prove this in the same experiment (the owner, explicitly):** Habitat Blocks currently "survive restarts but not a
re-export" (STATE). In a dimension WorldPainter never touches, they may survive a re-export. **If they do, the pocket
dimension is the _better_ home for legendary encounters rather than merely the necessary one** — which changes what
belongs in it, not just where it can go. Worth proving deliberately, not incidentally.

### 2.6 The design, only after the experiment

Then: how many of each and where the portals are; what gates them (Dive for the underwater ones; **Soar was cut, so
the sky gate is an open question**); the aura and how a player learns portals exist; the return; which legendaries and
content belong in which.

**The ratio — this session's recommendation: about 1 in 6 meaningful.** The owner's instinct is the load-bearing part
of the design: if every portal holds a legendary, players check them all methodically and nothing feels found. Most
should hold a chest or nothing. Design the useless ones deliberately, not as filler.

## 3. What else waits on the owner

- **Staging is up with the lock held, for the owner's flight.** `cobblers-dryrun11`, pid 24408 on port 25565, lock
  owner line: "Claude Code session cobblers-session-start-531d15 (2026-09-28 stone-faces redesign; took over the
  flight lock, server found down)". Used here only for read-only jar reads and RCON. When the flight is done:
  `python cobblers-server/rcon.py save-all`, then `stop`, then remove the lock.
- **The dive test is set up and waiting** (see 5, "Do not rediscover"): the owner was sent to (96, 64, 4721) to dive
  to y35. Not yet reported back.
- **Flight finding 2, the stone faces into the towns, is still the queued build job** (STATE, "Flight finding 2";
  `STONE_FACES_REDESIGN.md` section 5). **The owner also asked for a survey of the other six places for the same
  three problems, reported before building.** Not started: this session was at its threshold.
- Carried: the Mega farms' zone, the West Spur Dig reshape, the spur's daily crystal, workers for Pallet,
  ATM x MSD v4.0 (STATE, What is open).

## 4. Where this session's own work stands

- **The prepare sweep: done.** 497 s to 351 s over all 80 jobs (29%), every pack byte-identical. Causes and what was
  deliberately not changed are in STATE ("A fresh checkout prepares", second bullet).
- **The determinism sweep: done and clean.** `derived/deep_city/plan.json` varied run to run because
  `deep_city.py:1404` iterated a **set of strings** into the counts. Fixed at source with `sorted()`; PYTHONHASHSEED
  is also pinned in `reapply.py`'s `py()` funnel. Then every job was rebuilt under seeds 1 and 12345:
  **7,556 files, 0 differ.** Nothing else in the build depends on the hash seed.
- **The mines tests: held, not fixed.** `tests/test_mines_independent.py` is skipped at module level with the reason
  in the file. It alone accounted for all 30 failures and 43 errors; the rest of the suite is green (4,583 passed,
  420 s). 43 of its red results are raised in **fixtures**, which xfail cannot express, hence a skip. The 9 tests that
  still pass go dark with it, and the file says so. **A test-author agent rewrites it with the redesign** and deletes
  the marker.
- **STATE corrected: the marine pools ARE installed.** The line said "not installed"; the three windward files stand
  in staging's `cobblers_spawns`. Corrected with what the deep band holds.

## 5. Do not rediscover

- **`derived/deep_city/plan.json` used to vary between runs and no longer does.** If it ever varies again, look for a
  set of strings being iterated into output, not for a regression in an unrelated tool. It cost this session a false
  alarm.
- **The dive test, already set up** (2026-09-28): the marine rosters are live on staging. Deep band = 23 boxes, 207
  entries at 25-30. `chinchou`, `relicanth`, `dhelmise` carry `maxY 40` and exist **only below y40**; `wailmer`,
  `carvanha`, `alomomola` are submerged at any depth; `wingull`, `pelipper`, `lapras` are surface. Magikarp's
  inherited pool is suppressed there (all 46 entries). Stand at **(96, 64, 4721)**, seabed y10, every column of that
  box below y40; dive to **y35** and **hold position 2-3 minutes** — moving shifts the spawn zone and reloads chunks.
- **Why lakes looked empty:** `pokemonPerChunk` is 0.25 and the budget is shared across every loaded chunk, so a
  lake's surrounding **land** chunks eat it. 256+ blocks out to sea every loaded chunk is sea, so the budget belongs
  to sea species. Config: pass every 10 ticks, `maximumSpawnsPerPass` 1, zone 16-64 blocks from the player, 8 wide by
  16 high, `minimumDistanceBetweenEntities` 8.
- **The owner had the Dive mount but not the training.** Wailmer and Lapras were in the party; the `cobblers.dive` and
  `cobblers.surf` tags were absent, so the ladder never qualified them. Granted here with
  `execute as <player> run function cobblers:water/grant_dive` (it grants both). Undo: `tag <player> remove
  cobblers.dive`. **This changed the owner's staging progression state** — it is not how Dive is meant to be earned.
- **The owner's level cap is 25 and the deep roster is 25-30**, so a catch there is over cap and
  `cobblers_levelcap` should block it outright — never yet run in game. The owner's party carries a Master Ball,
  which is exactly what that proof needs. A failed Master Ball there is the block working, not a bug.
- **There is no flying encounter.** Nothing designed: no sky spawns, no aerial encounter, no flying-mount content.
  What exists is bird nests in trees (Habitat Blocks) and `wingull`/`pelipper` as surface sea spawns.
- **Perching does not exist in Cobblemon 1.8.0** and was never claimed. The sapling nests **were** seen in game
  (2026-09-26, the Fletchling tree "its good", the Ducklett/Swanna tree "way better", 42-65 birds measured round each
  of four elders); the birds walk and fly off the limbs, and the `+58`/`+74` crown blocks put none up top.
- **Measured to be real work, not repetition** (do not re-profile hoping): shrines (28 s) and its audit (16 s);
  `ferries.nearest_other` — windowing its dilation was tried, gave identical answers, saved nothing, and was
  reverted, because the cost is the O(hits x shore) nearest-pair loop; `vr_caves.walkout` and `smooth`; the paint and
  heightmap decoding.
- **scipy is not installed and was not added.** The flood fill is numpy alone; a fresh checkout is unaffected.
- **Bash: `cat > "$TMP/x.py"` with no input hangs the tool call**, and `python - <<'EOF'` heredocs remain a trap.
  Write scripts with Write and run them by path. `/usr/bin/time` does not exist in this Git Bash.
- The harness's per-agent token figures are final context, not spend: `python tools/session_cost.py`.

## 6. What this session cost

`python tools/session_cost.py`: about 4M weighted over ~140 turns (average ~190k context per turn). One subagent, the
gym-interiors `content-architect`, still running when the session stopped.
