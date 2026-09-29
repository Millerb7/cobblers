# Session handover (2026-09-28 night, session 88461346, ended at its threshold: 259k context per turn)

For a cold start: read CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before starting. STATE holds the
durable facts; this holds where work stopped.

## 1. Branches and PRs

- **#89 and #90 are merged and verified on main**, pinned to their reported heads (`c61487e`, `7b5496f`); main is
  `f2a056b`. #90 had been opened against `design/stone-faces`, so it was retargeted to main before merging.
- This session's work is one commit, `137213d`, on `tooling/prepare-loop-sweep`, branched from main `f2a056b`, with a
  draft PR against main. **Treat that PR as frozen now it is reported**: further work goes on a new branch.
- `.codex/config.toml` is modified in the worktree and **never committed** (Codex's): stage files by name.

## 2. Where the job stopped

- **Done and verified: the prepare sweep for the gulch's loop shape.** 497 s to 351 s over all 80 jobs (29%), every
  generated pack byte-identical. The causes, the numbers and what was deliberately *not* changed are in STATE
  ("A fresh checkout prepares", second bullet). Method, if it is repeated: time each job
  (`reapply.prepare_jobs`, called directly so the lock is only needed for the four jar readers), profile the slowest
  with `python -m cProfile -o x.prof`, read pstats by cumulative *and* self time, then compare sha256 over every file
  in `build/` and `derived/` before and after.
- **Nothing is installed or re-applied.** This is tooling only: no pack was rebuilt into a server or world, and
  staging was not touched beyond reading the server's mod jars under the lock.
- **Next job: flight finding 2, the faces into the towns** (STATE, "Flight finding 2"; `STONE_FACES_REDESIGN.md`
  section 5), unchanged by this session. The owner's answer and the starting mix are already recorded there; it needs
  the per-place mix confirmed, then the `ring` siting replaced, a rebuild, and the current formations cleared on
  staging the way the previous handover describes.
- **Half-done, unchanged:** `tests/test_mines_independent.py` still describes the old box faces and fails. It alone
  accounts for **all** 30 failures and 43 errors in the full suite; everything else passes (4,583 passed, 420 s). A
  test-author agent writes it, not the builder. The places' `reading` strings in `data/mines.json` still describe the
  old sites.

## 3. What waits on the owner

- **Staging is still up with the lock held, on purpose, for the owner's flight.** `cobblers-dryrun11`, pid 24408 on
  port 25565. Lock owner line: "Claude Code session cobblers-session-start-531d15 (2026-09-28 stone-faces redesign;
  took over the flight lock, server found down)". This session used it only for read-only jar reads, with the owner's
  explicit go-ahead, and left it held. When the flight is done: `python cobblers-server/rcon.py save-all`, then
  `stop`, then remove the lock.
- Finding 2: confirm the per-place mix and which houses give way; the townspeople's words are Codex's.
- The rest of the flight list is unchanged (working Pokemon, the level cap in battle, the gulch and cove town,
  re-materialed houses, shrines, guardians). Faces to fly: tea town (2701, 109, 3747), Mining Town (6698, 119, 5536),
  Northlight (7222, 111, 1436), gorge hamlet (6795, 113, 4317), the Scar (2064, 281, 806), Viltri Light
  (565, 73, 4379), Displaced City (3334, 28, 1848).
- Carried: the Mega farms' zone, the West Spur Dig reshape, the spur's daily crystal, workers for Pallet,
  ATM x MSD v4.0 (STATE, What is open).

## 4. Do not rediscover

- **`derived/deep_city/plan.json` is not reproducible between runs, and never was.** Its counts-key order follows
  `PYTHONHASHSEED`: at a fixed seed the old and new tools write identical bytes, across seeds each varies on its own.
  It is a disposable `derived/` file. Do not treat a changed hash there as a regression; pin the seed to compare.
- **A clean run of a checker proves nothing until faults are planted.** The changed `function_limits` was checked
  against ten planted cases (unforced setblock, one-chunk fill, a released box, negative coordinates, the
  `chunks-loaded-by` marker), `covered_by` against 600 randomised cases, `ferries.component` against every real call
  plus 42 planted probes.
- **Tried and reverted: windowing `ferries.nearest_other`'s dilation.** Identical answers, no time saved; its cost is
  the O(hits x shore) nearest-pair loop, not the dilation. Do not retry that one.
- **Measured to be real work, not repetition** (do not re-profile hoping): shrines (28 s) and its audit (16 s) read
  every other pack's ~4M writes plus images and NBT, already cached once per process; `vr_caves.walkout` (8.3M `kind`
  calls) and `smooth`; the paint and heightmap decoding.
- **scipy is not installed.** The flood fill is numpy alone, and nothing new was added, so a fresh checkout is
  unaffected. If it were ever added, `ndimage.label` and `distance_transform_edt` are what would want it.
- **Bash: `cat > "$TMP/x.py"` with no input hangs the tool call**, and `python - <<'EOF'` heredocs are still a trap
  (the previous handover's `\n` warning stands). Write scripts with Write, run them by path.
- `/usr/bin/time` does not exist in this Git Bash; time with `$SECONDS` or `time.perf_counter`.
- The harness's own per-agent token figures are final context, not spend: `python tools/session_cost.py`.

## 5. What this session cost

`python tools/session_cost.py`: 3.3M weighted over 127 turns (average 189k context per turn). No subagents: the job
was measurement and small fixes, done in the main session as instructed.
