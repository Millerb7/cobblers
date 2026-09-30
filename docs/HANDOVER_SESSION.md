# Handover — the 2026-09-30 overnight run

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch and PR

- Branch `build/2026-09-29-phase2`, head **1692865** (plus whatever the two in-flight agents add, §2).
- Stacked on `night/2026-09-29-water-export`, whose **PR #95 is OPEN and therefore FROZEN**. Nothing may
  be pushed to that branch. No PR is open for this branch yet; opening one is the next session's job
  (`open-pr` skill, draft only).
- `.codex/config.toml` is modified and is **deliberately uncommitted** — it is Codex's, see
  `docs/HANDOVER_CODEX.md` item 29. Leave it.

## 2. In flight when this was written

Two background agents were still running. Neither has been merged or reviewed; **check them first.**

| agent | unit | what to do |
|---|---|---|
| `a70a7cdda2e690938` | the Rift Z1–Z4 zone system | It was launched on a worktree based on MAIN (see §4, the launch fault) and was sent a correction authorising `git reset --hard c056a21`. Confirm it took the reset before trusting a line of its output. |
| `a321228e6c761dfd3` | F11: emit the eight gym leaders' teams | Its first unit (Victory Road + League) is merged as a422cf5 and verified. This second unit was sent after 6570a92. |

Re-run every audit an agent reports, in the full checkout, before believing it (F8).

## 3. Where the work stopped

**Done and verified in the world** (`cobblers-dryrun12`, probed by block, not by exit code):

- Five authored gym buildings (R16F demolition, then R16G), all five leaders' spawners present.
- The twelve portals re-skinned (R16P).
- Routes 1–3 event sites re-applied (R12) after the re-route.

**Done in the repo, NOT in any world:**

- The lake-bed fix (F5) — lands at the next **R1**, a full re-skin, not a step to run casually.
- Victory Road's ten fights and the League's five overrides — R17 places them; R17 was not run.
- The dig camp's 2026-09-29 reshape — R9M still holds the previous shape.

**The next command**, if picking up the applied work:

```bash
python tools/gym_buildings_independent.py   # must stay clean over 5 buildings
```

The server is **running** on `cobblers-dryrun12` with `max-tick-time=60000` restored. **Start it with a
detached launch, never PowerShell `Start-Process` from a tool call** - one started that way died silently
at 00:57 on 2026-09-30, its console log ending mid-startup with no shutdown line and no crash. The coordination
lock at `C:\Users\wnd\Documents\github\.cobblers-server-agent.lock` is **still held** by this session's
owner line — take it over or release it.

## 4. What a cold start must not rediscover

- **A nested isolation worktree is based on the MAIN checkout's HEAD, not this session's**, even with
  `worktree.baseRef: "head"`. Both agents launched with `isolation: "worktree"` came up on main, 87
  commits behind. `git merge --ff-only` then fails outright. One agent stopped and reported (correct);
  the fix is to authorise `git reset --hard <sha>` explicitly. **Verify an agent's base before trusting
  its output.**
- **`reapply.py run --only` was fail-open** and ran zero steps at exit 0 for a comma-separated list.
  Fixed in c056a21; it now fails closed twice over. It was caught by the run log being six lines long,
  never by the exit code.
- **The eight gym leaders fight with COBBLEVERSE's teams** (F11, commit 6570a92). Not a guess:
  `grep -rl "gym_01_brock" build/ modpack/ server/` returns nothing.
- **F5's recorded hypothesis was wrong about the cause.** It blamed the water-shape pass; the culprit is
  `tools/rift_skin.py`, and the skin reaches outside the Rift's own polygons in `data/regions.json`.
- **The re-route was safe**: Routes 1–8 moved zero columns. Do not re-litigate it.
- **C3 and C14 fail today and are recorded** in `data/system_contracts.json` `fails_today` as strict
  xfail. A green contracts run is 80 passed, 2 xfailed. Do not "fix" them by deleting the entries.
- `COBBLERS_SOURCE_ROOT` must be `C:\Users\wnd\Documents` in every shell that runs a heightmap tool;
  `prepare` does not pass it down to `legendaries.py`.
- `COBBLERS_LOCK_OWNER` must match the lock file's owner line **exactly**, and `COBBLERS_SERVER_LOCK`
  must point at the lock path, or `runtime_guard` refuses.

## 5. What waits on the owner

1. **F11 — the leaders' teams.** Confirm the eight authored rosters should replace COBBLEVERSE's before
   the fix is applied: it changes the difficulty of all eight gym fights at once.
2. **Fly the five new gyms** and say whether the buildings are right. Coordinates in the morning report.
3. **`patriarch_from_victory_road` is fragile** (10 observer points of 137): taller wedge, or downgrade
   the claim?
4. **The ferry migration** (C3/C14): which line replaces the Sound ferry, and where is Pacifidlog's
   square now? Both stops of the old line are retired and so is `pacifidlog_ferry`'s second stop.
5. **Lugia's level** — its gate is `champion_cleared` and that cap is `null`. Still unanswered.
6. **Registeel's location** — `upper_rift` (4195, 3896) recommended; it also fixes Regigigas, which is
   otherwise permanently unreachable.
7. **The carry** — needs the owner in dryrun11 to revoke `gym5_cleared`/`gym6_cleared`, then
   `reapply.py carry --rehearsal`.

## 6. Cost

`python tools/session_cost.py` at the time of writing: **573 turns, context 446k, 16.7M weighted for
the main session; 25.5M across 19 agents; 42.2M together.** The verdict line said HAND OVER — 446k of
context means every turn costs 44k to send. This session ran long because the owner asked for an
overnight run and could not compact.

---

## 7. Added at the end of the run

- **The zone system is merged but HELD**: `cobblers_rift_zones` is in `reapply.py`'s `EXCLUDED` and
  R9Z is withdrawn, because its walls would seal the Rift — nothing calls `z*/qualify`. The note
  beside the exclusion says what must hold before both come back. Do not "restore" the step without
  reading it.
- **F11 is fixed and unproven**: seven leaders' teams emit as overrides; whether a datapack override
  at `data/rctmod/trainer/kanto_*.json` actually replaces rctmod's own roster has never been tested.
  One staging fight with Brock settles it.
- **The suite's honest baseline is 4,937 passed / 8 failed / 8 xfailed.** All 8 fail at 36eb267 too.
  They are: heightmap provenance (`water_shaped_from` undocumented), mines_independent surface faces,
  no_swallowed_crashes, two rift_heightmap sculpt tests, and three sea_town tests — the last three
  being the same ferry/sea-town migration that C3 and C14 record.
