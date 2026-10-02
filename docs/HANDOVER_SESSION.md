# Handover — the gates are fixed, the legendaries are measured, and three of the owner's builds were never started

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. The branch

- **Work branch `build/2026-10-01-rift-builds`** is FROZEN: its PR, [#104](https://github.com/Millerb7/cobblers/pull/104),
  is open and reported with head `201edbf`. Nothing more goes to it.
- **The handover PR**: SUITE_AND_PR_PENDING. Re-read the head with `git rev-parse HEAD`
  before quoting it; the owner merges while sessions work.
- `origin/main` is `a271532`; **nothing from 2026-10-01 is merged**. #102 and #103 are the older drafts.

## 2. Where it stopped

Everything delegated has been integrated, re-run in a full checkout and committed. Last verified state:
**10 failed, 5,411 passed, 11 xfailed, 0 errors** (771 s, full checkout) - the known ten, by name, in
`docs/STATE.md`. `validate.py` clean at 1,242 files.

**Half-done and still running:**

- **The staging server is UP** (`staging-2026-10-01`, started from this session as a background shell) and
  **this session holds the coordination lock** (`python tools/server_lock.py status`). The owner left the
  server at 23:23 on 2026-10-01. Stop it gracefully and release the lock when the owner is done flying.
- **Six agent worktrees** under `.claude/worktrees/agent-*` hold copies of work that is now committed here;
  none holds anything that is not. Safe to clean up.

## 3. What waits on the owner

**Their requests that were NEVER STARTED.** All three were asked for on 2026-10-01 and the session was
pulled onto other work. It told the owner it was starting the first two; it did not.

| Request | Measured | Next |
|---|---|---|
| **Ursaluna cave** at (1504, 164, 1414): a solid cave for a large Ursaluna, Teddiursa on the outskirts, an NPC players can talk to | ground y162; 157-244 blocks west of Highwire (gym 3's town); nothing else in the way | build it |
| **Mine tunnel + strip mine** from near (1455, 113, 1795), surfacing near the beach at (330, 70, 1584), with **a small island** and water spawns round it | mouth ground y112, empty for ~400 blocks; the exit is ground **y26 in 36 blocks of sea**, so the island is required, not optional | build it |
| **Research site** at the south foot of Frostpeak, studying the legendary above | **(688, 688), ground y110.6**, relief 4.9 over 40x40, on the summit's own N-S axis (summit (679, 324) y310), 385 blocks off and 27 degrees up. Articuno's shrine is now at (904, 320). | author it. NB the session's last message to the owner wrongly called this "a different place" from the south foot. It IS the south foot. |

**Decisions** (`docs/DECISION_QUEUE.md`):

- **B15, the Jungle Isle.** Four pinned elders hang 17-68 blocks over the sea; four ruin templates sit
  inside Pacifidlog's rafts (496 columns); "Jungle Isle" and "Sunken Court" title open water. The owner's
  2026-09-27 "jungle isle should be removed" governs - so this is most likely finishing a removal (re-site or
  drop the four elders and their 16 bird blocks; move or drop the ruin set; retire the region's name)
  rather than a fresh design question. Confirm, then do it.
- **Tri Peaks foliage**: the region has no foliage model at all. Proposed: a `foliage.json` entry for its three
  alpine subregions plus scatter.
- **More of the Cobbleverse catalogue** waits on EXP-048: if an altar is silent, the four adopted sites are
  scenery and `stark_mountain`, `crown_spire` and the lake trio should be judged as scenery too.
- **Placing the four adopted sites**: they need `placements.json` records and an apply step; nothing emits them.

**In-game checks only the owner can make:**

- **EXP-048** (`experiments/EXP-048-legendary-altar/README.md`): place `crown_cemetery` at (4118, 109, 1982)
  and right-click its altar with an empty hand. The commands are in the file, in order.
- **The railing** at (3565, 114, 5294) and the gatehouse at the trailhead (3548, 114, 5322) - `docs/FLIGHT_LIST.md` 4b.
  The gatehouse can now be **walked out of**; that is worth trying.
- C1 (Hoopa renders), C2b (sell one emerald block: 3,750 or 1,875), C3 (Brock refuses a rematch), C4 (two players).

## 4. What a cold start must not rediscover

- **RCON writes to the running server are refused** by the permission classifier as *Remote Shell Writes*
  (2026-10-01, EXP-048). A refusal of the outcome: do not retry it another way. It needs a permission rule or the owner.
- **A test that reads the real heightmap is not therefore independent.** `rift_zones`' places test checked each
  place against the ground at its own column - the generator's rule - and was green through the whole defect.
  Re-scoped to the floor the player stands on; proved by running it on the pre-fix data from git (`db406fb`).
- **A strict xfail keyed in a test file, not on the record, does not drop when the record gains `fixed`.**
  The implementer correctly reported those rather than editing a test it was not entitled to grade.
- **Integration needs `derived/`**: the test-debt agent's 18 failures and 66 errors were all missing plans.
  In a full checkout they were zero.
- **The four blackout recovery failures are not a fault**: `docs/mechanics/BLACKOUT_RECOVERY_COUPLING.md`.
  Re-point as relations and add one contract; test-author work.
- **`brink_columns` (the railing) still has no test.**
- **R14C's Celebi guard is not idempotent against wild spawns** - a wild Pokemon at the sapling satisfies
  `distance=..3` and suppresses the spawn. It wants a tag or species selector.
- **The heatmap counts point records, not built volume**: the Displaced City reads 3% of peak.
- The session relayed an unmeasured count again ("six gatehouses"; there are seven) and wrote two
  off-by-one figures into its own Articuno record. Agents caught all three.

## 5. Cost

`python tools/session_cost.py`: **767 turns, 44.3M weighted, context 411k at hand-over** (the threshold is
300k); **agents together 26.4M**. About 70.7M in all.
