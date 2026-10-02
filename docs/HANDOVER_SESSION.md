# Handover: the starters design (2026-10-02). Design only, nothing built

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

**This session was a side job.** The build stack's handover is the previous version of this file, on PR #105's branch
(`git show origin/build/2026-10-02-gates-and-legendaries:docs/HANDOVER_SESSION.md`). Its §3 (the owner's three
unstarted builds: Ursaluna cave, mine tunnel and island, Frostpeak research site; B15; EXP-048) and its §4 are
**unchanged by this session** and still stand.

## 1. The branch

- **`design/2026-10-02-starters`**, branched from `origin/build/2026-10-02-gates-and-legendaries` at `2de7170`
  (PR #105's head when read). It is pushed, and **no PR was opened**, by the owner's instruction (one integration PR per batch). To fold
  it into the batch, merge it into the next integration branch. It touches only docs.
- `origin/main` was `a271532`. PR #105 is a draft, OPEN, FROZEN.

## 2. Where it stopped

Done and committed:

- `docs/research/STARTER_OPTIONS.md`: the report, verified vs assumed, with a recommendation.
- `docs/research/notes/starter-stat-mechanics.md`: the 1.8.0 source reading, by the research agent.
- `docs/mechanics/STARTER_DESIGN_COMPARISON.md`: the costed comparison and the decisions for the owner.
- Two proposed rows in `docs/research/EXPERIMENT_BACKLOG.md`.
- `docs/STATE.md`: the starter spread lines are corrected to today's measurement, plus one open item.

Next step if the owner says go: run E1, E3 and E4 on staging (one session, needs the server lock). Steps are in the
notes file, §"Experiments needed".

**Not touched:** the server runtime. The coordination lock was held by the encounter-rebuild session (acquired
2026-10-02 01:29), so `install_check.py` was **not run**. There was no Java process and no listener on 25565. The
previous handover's "staging server is UP" is therefore no longer true.

## 3. What waits on the owner

The five decisions at the end of `docs/mechanics/STARTER_DESIGN_COMPARISON.md`. The first is whether to adopt idea 2
at all; the recommendation is to run E1, E3 and E4 before deciding anything else.

## 4. What a cold start must not rediscover

- **"25 leader Pokemon beaten down to 1" is the retired 36-species list.** Measured today it is 27 (Mudkip) to 9
  (Tepig) of 35 across eight gyms. Grass is no longer the hole (type means: Fire 16.2, Grass 17.2, Water 18.2).
- **`battle_sim.config_starters()` keeps only the first word** of each entry, so the Hisuian starters are
  simulated as their ordinary forms (`tools/battle_sim.py:991`). Neither simulator reads our `species_additions`.
- **`battle_stress.py:330` and `tests/test_battle_stress.py:82` hard-require 27 starters.** Either starter idea
  breaks them.
- **The simulator's Mew is a floor.** It scores 10 because it uses level-up moves only (Pound and so on). Real Mew
  learns every TM.
- **Gym flags are advancements** (`cobblers:flag/gymN_cleared`, `tools/legendaries.py:255`), so an `advancement`
  evolution requirement can key on a badge.
- **A fresh worktree's `availability.py --write` rewrites `docs/story/AVAILABILITY.md` by 7 lines**: a 1585 → 1465
  count and six sapling rows dropped. Reverted here, not investigated. Probably a missing derived input in the
  worktree.
- **`derived/` and `build/`** were generated in this worktree (`compile_spawns.py`, `availability.py`). They are
  gitignored and disposable.

## 5. Cost

`python tools/session_cost.py`: main session 48 turns, about 1.0M weighted at 168k context; the research agent 1.31M.
**About 2.3M in all** at the time of writing (the final figure is in the session's closing message).
