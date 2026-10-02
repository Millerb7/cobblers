# Handover: blockers on the south map (2026-10-02, session e183ad9d)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file. `docs/HANDOVER_SOUTH.md` is the south session's own
handover and is still current for its batched apply (section 2 below folds it in).

## 1. The branch

- **`claude/blockers-on-south-map`**, pushed, **no PR** (the owner wants one PR per batch; open it when the apply
  is done). Re-read the head: `git fetch --prune; git rev-parse origin/claude/blockers-on-south-map`.
- It merges three inputs: `origin/claude/south-map-world-audit-2219f3` (the base: theirs wins on the relic hall,
  `deep_city` and the residents), `origin/main` at `1a4b85f` (#108, the hearts, which the south branch lacked), and
  the server session's local `build/2026-10-02-followups` at `a2fb389` (Shrew Station etc., 21 commits the south
  branch lacked). If followups has moved since, merge it again.
- **Not merged:** `claude/legendary-followups-2026-10-02` (worktree `legendary-shrines-placement-fa3eea`), which
  had UNCOMMITTED edits to `data/adopted_legendary_sites.json`, `server.properties.example` and
  `tools/install_check.py`. The owner routed the EXP-048 fixes there (clone dropping shrine blocks, the missing ritual
  block, the 71-block placement error, Mew's fossil from the research station, unblocking Spectrier, Calyrex, the
  feathers, Zacian and Zamazenta). Do not do that work from here.
- Superseded and never pushed: `claude/integration-blockers-outstanding-4ac1df` at `d198fcd` (its relic and resident
  changes lost to the south branch's; its guard, validator fix and siting test were carried over).

## 2. Where it stopped: the apply, waiting on the lock all session

The server (java pid 26736, since 12:15) and the lock (`cobblers-cobblemon-session-start-531d15`, since 08:47) were
held the whole session; per the hard gate the runtime was never read. When they free, in this order:

1. Take the lock. `python tools/install_check.py --server-dir C:/Users/wnd/Documents/github/cobblers-server --world-dir C:/Users/wnd/Documents/cobblers-staging/staging-2026-10-01`.
2. **World probe BEFORE any apply** (the owner asked whether the Mega mine, Hoopa underground, the arena and the
   Deep's changes are in the world): `python tools/presence_audit.py --only arena,gulch,dens,relic --out <scratch>/before.tsv`
   (`dens` drives the keepers: staging only). Repo-side verdicts are in `docs/HANDOVER_SOUTH.md` section 2.
3. **The hearts may already be installed**: followups' STATE says the server session installed them at 12:16
   (world-local `cobblers_spawns` byte-identical to its compile, 989 heart ids). Check that, do not repeat it blind.
4. `docs/HANDOVER_SOUTH.md` section 3's batched apply (`max-tick-time=-1`, full `prepare`, `install`, boot detached and
   check the PROCESS, `run --only R9Z,R9RU,R9DU,R9HF,R9SO,R9E,R18DU,R18HF,R18SO,R18R`), plus Shrew Station's R9RS from
   followups. Then the owner's own asks: `run --only R17N` and `python tools/npc_seats.py verify`.
5. Restart, `presence_audit.py --out <scratch>/after.tsv`, `deep_city.py verify --world <staging>`.
6. The full suite after prepare. Before prepare it was 27 failed, 5,279 passed, 66 errors (nearly all need
   `build/` or `derived/`; the four battle_sim tests that needed `derived/availability.json` passed).

Then tell the owner where to stand on Frostpeak (re-measured): above the y180 line (566, 227, 316); just above
(794, 183, 250); just below (806, 177, 244), 13 blocks from the last.

## 3. What waits on the owner

- **Split-Bark L62** is over its tier-8 place's ceiling of 60 (`tests/test_resident_siting.py`, strict xfail); the
  south session proposed 63 to close its catch leak instead. One call.
- **Wiremother L30** (lowered to its ceiling) is a declared catch-gate leak: a partner between gyms 2 and 3 can catch
  it once it appears. Keep, or move to a tier-3 place and restore 33.
- **The relic hall's spawn decision** (spawn-free zones are x/z only, so one would also blank the dig above).
- The moved ROSTER + GATE ONLY residents (Ridgejaw, Hornwall, Split-Bark) no longer stand in a clearing: look in game.

## 4. Do not rediscover

- **The primary checkout is fixed**: `C:/Users/wnd/Documents/github/cobblers` is on `main` at `1a4b85f` with the `env`
  block. Its old history (no common ancestor with origin/main) is `backup/main-pre-cleanup-2026-10-02`.
  `COBBLEVERSE/` there now shows untracked (its datapacks intact). This session still lacked the variable.
- **The suite refuses green without the heightmap** (`tests/conftest.py`); `--allow-no-heightmap` for a partial run.
  A skip naming `rift_heightmap.py` is a missing derived plan and is not counted.
- **The 263 spawn-block errors** were unhydrated local kits; `python tools/local_inputs.py hydrate --store C:/Users/wnd/Documents/cobblers-local`.
- **Merging data files by text loses records.** Both sides appending to one list makes git interleave half-records;
  joined, they become one object with duplicate keys and JSON keeps the last. Merge by id from `:1:`/`:2:`/`:3:` and
  check the result is additive against both sides (`validate_data` caught a lost cursor field here).
- `#107` was merged at 16:57 before review; its premise of overlapping the encounter rebuild was wrong (no shared file
  or id).

## 5. Cost

`python tools/session_cost.py`: 227 turns, context now 402k (average 259k), weighted 7.4M. No agents.
