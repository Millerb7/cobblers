# Session handover (2026-09-28 evening, session 8c1db5dc, ended at its threshold: 304k context per turn)

For a cold start: read CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before starting. STATE holds the
durable facts; this holds where work stopped.

## 1. Branches and PRs

- The owner's answer to finding 2 is on `design/stone-faces-in-town`, stacked on #89, with its own draft PR.

- #88 (flight finding 1) is **merged**, head `9571af1` verified on main.
- This session's work is on `design/stone-faces` (branched from main `d1366e4`), pushed with a draft PR against
  `main`; the head sha and PR number are in the PR list (`gh pr list --head design/stone-faces`). Treat that PR as
  frozen once reported: further work goes on a new branch stacked on it.
- `.codex/config.toml` is modified in the session worktree and **never committed** (Codex's): stage files by name.
- The test-author agent's worktree `.claude/worktrees/agent-a7d9453477adc2847` (branch
  `worktree-agent-a7d9453477adc2847`, nothing committed) is spent: its `tools/mines_audit.py` was copied into this
  branch. Removable.

## 2. Where the job stopped

- **Staging is up for the owner's flight, lock held on purpose.** `cobblers-dryrun11`, started detached
  (`Start-Process java -Xmx16G -jar fabric-server-launch.jar nogui --universe
  C:/Users/wnd/Documents/github/cobblers-runtime-proof/dryrun11 --world cobblers-dryrun11`, working directory the
  server's), pid 24408 at 21:28. Lock owner line: "Claude Code session cobblers-session-start-531d15 (2026-09-28
  stone-faces redesign; took over the flight lock, server found down)". Tools that read the runtime need
  `COBBLERS_SERVER_LOCK` and `COBBLERS_LOCK_OWNER` (that line) set. It went down twice this session: at 19:24 with no
  stop line (most likely its console window closed) and at 19:53 by a `stop` nobody in this session sent. When the
  owner is done: `python cobblers-server/rcon.py save-all`, then `stop`, then remove the lock.
- **Done and verified: the faces are formations** (flight finding 1; `docs/world-building/STONE_FACES_REDESIGN.md`).
  `tools/mines.py` builds each face from an anchor shaped to its ground; the old boxes were cleared on staging by a
  one-off pack (scratch, removed after) and the new ones built: 501 of 505 sampled cells match, 0 of 440 old ore cells
  left. `tools/mines_audit.py` (rewritten by a test-author agent, run here) is clean and catches a planted missing
  bottom, pit and restore gap.
- **Next job: flight finding 2, the faces into the towns** (STATE, "Flight finding 2"; the redesign doc section 5).
  The owner liked the formations but not the distance: "make them a piece in town square or in like a house slot".
  The owner answered (2026-09-28): a mix per place, square, house slot, or near town with a townsperson who tells
  players about it. Put the starting mix in the redesign doc section 5 to the owner, and which houses give way. Then: a smaller
  formation for a lot (width 7-9, knoll 1-2), or one merged outcrop per place on the square with its faces on
  different sides (the builder merges a site's faces: one cap per column, one restore footprint); Viltri Light needs a
  site by the lighthouse (6x13 square, no lots). Replace the `ring` siting with the chosen spot per site
  (`prefer_near` or fixed anchors), rebuild, clear the current formations on staging the same way (the clear script
  was `old_faces_clear.py` in this session's scratchpad: clone the adjacent natural column back over every written
  column, keyed to the old commit's model; rewrite it against commit `0f3227f`'s model).
- **Half-done:** `tests/test_mines_independent.py` still describes the box and fails. A test-author agent writes it
  (not the builder); its planned fixtures are in the agent's report as summarised in the redesign doc's status. The
  places' `reading` strings in `data/mines.json` describe the old sites; rewrite them after finding 2.

## 3. What waits on the owner

- Finding 2: confirm the per-place mix (redesign doc section 5) and which houses give way; the townspeople's words are Codex's.
- The rest of the flight list (the previous handover's items 1-7, unchanged: working Pokemon, the level cap in
  battle, the gulch and cove town, re-materialed houses, shrines, guardians). Faces to fly now:
  tea town (2701, 109, 3747), Mining Town (6698, 119, 5536), Northlight (7222, 111, 1436), gorge hamlet
  (6795, 113, 4317), the Scar (2064, 281, 806), Viltri Light (565, 73, 4379), Displaced City (3334, 28, 1848).
- Carried: the Mega farms' zone, the West Spur Dig reshape, the spur's daily crystal, workers for Pallet, ATM x MSD
  v4.0 (STATE, What is open).

## 4. Do not rediscover

- A 5-high box sits flush only on about a 50-degree slope; the tea town, Northlight and the gorge hamlet have no
  8-block rise over 6 within 250 blocks (survey in the redesign doc). Any fixed-depth cut on these towns is a pit.
- Bash heredocs turn `\\n` in Python source into a newline (hit again this session in `tools/mines.py`): write
  scripts with Write, not `python - <<EOF`.
- `rcon.py` with many commands: a reply can span lines (forceload's does), so match replies by content ("Test
  passed/failed"), never by position.
- An isolated agent was refused a Bash command that redirected to `$TMPDIR` outside its worktree ("too complex to
  verify that it stays inside the worktree"); it stopped, as the rule says. Tell builders to keep every path inside
  the worktree. An agent worktree also lacks `build/paint`, `derived/water_shape`, `derived/cavern`,
  `derived/routes`, so it cannot run `mines.py build` or the audit: run those in the main session.
- The audit's first clean run proved nothing until faults were planted; do the same for the next audit change.

## 5. What this session cost

`python tools/session_cost.py`: 3.0M weighted over 95 turns (average 213k context per turn); its one agent 0.5M.
