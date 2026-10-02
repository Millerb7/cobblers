# Handover: 2026-10-02, five native-evolving starters and the League's level cap (research and costing only)

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

**The previous handover (the night of 2026-10-02's integration, PR #106) is still the owner's open list.** Its
in-game checks and decisions are unchanged by this session. Read it with
`git show 31deeba:docs/HANDOVER_SESSION.md`.

## 1. The branch

- **`research/2026-10-02-native-starters`**, branched from `origin/main` at `31deeba` and pushed.
- **No PR**: the owner did not ask for one.
- It touches docs only: the new `docs/research/NATIVE_STARTERS_1_8_0.md`, `docs/mechanics/NATIVE_STARTERS_COST.md` and
  `experiments/EXP-049-native-starter-evolution/README.md`; one row in `docs/research/EXPERIMENT_BACKLOG.md`; one line
  in `docs/STATE.md`; and this file.

## 2. Where it stopped

- **Done:** the owner's brief is answered (the starter questions, the learnset question, identical evolution points,
  strength scaling, the stress tests).
- **Next:** nothing runs until the owner decides (section 3). Then EXP-049, in a staging session holding the lock.
- **Nothing half-done:** no server, no lock and no worktree for another agent.

## 3. What waits on the owner

**Decided on 2026-10-02:** a-lite at 30/45, EXP-049 first, reconcile with `194330c` before building, and Meltan stays
(no anvil, authored movepool: `NATIVE_STARTERS_COST.md` §6a).

**Open:**
- **Kubfu's scrolls:** who hands them out, and when.
- **Forced or offered** evolutions (`optional: false`).
- **The cap after gym 8** (`docs/mechanics/LEAGUE_LEVEL_CAP.md`):
  - **L1:** 59 (recommended), 58 or 57.
  - **L2:** the Champion uncapped from Lance's defeat, or capped until Blue.
  - **L3:** may we commit an authored override of Cobbleverse's League mob files?
  - **Lugia's level**, now that its band is known to be uncapped.

## 4. What a cold start must not rediscover

- **A parallel note exists:** `origin/research/2026-10-02-mythical-starters` (`194330c`,
  `docs/research/MYTHICAL_STARTERS.md`), unmerged.
  - Every shared measurement agrees, and its option-(b) sim figures reproduce to the unit.
  - It differs on the recommendation: c, against a-lite here. Its option (a) uses each line's final-form shape, where
    this session used each stage's own; that is why the two "a" figures differ.
  - Integrate the two before building. Do not build from either alone.
- **The jar is readable without the lock:** a client copy of `Cobblemon-fabric-1.8.0+1.21.1.jar` (and MSD 1.0.2,
  TMCraft 1.4.19) sits at `C:/Users/wnd/AppData/Roaming/ModrinthApp/profiles/Fabric 1.21.10/mods/`. Cobbleverse's
  datapacks are at `C:/Users/wnd/Documents/github/cobblers/COBBLEVERSE/datapacks/`.
- **A refused command:** `python tools/compile_spawns.py && python tools/availability.py --write` was refused by the
  permission classifier ("Irreversible Local Destruction"). It was not retried. The starter duels need no availability:
  the gym caps and foes were built straight from `data/trainers.json` with `battle_sim`'s own functions.
- **The scratch scripts** (`spread.py`, `forms.py`, `evolv.py`) lived in the session scratchpad and are not in the
  repo. The method is in the research note, §8.
- **Learned in rctmod v0.19.0-beta source:**
  - the cap after the last series trainer is 100;
  - a series is never reset on completion;
  - per-trainer `relativeLevelCap` lives in the mob file;
  - the trainer-level cache survives `/reload`.
- **The brief's "E4 aces 57/58/59/60" is the spread inside each team.** All four aces are 60 (`data/trainers.json`).
- **Learned in 1.8.0 source:**
  - passive evolutions are tried every second (`PlayerPartyStore.kt:146`);
  - `evolution_tested` has `set_result`;
  - the `species` setter keeps `forcedAspects`;
  - `FormData.evolutions` never falls back to the species list.

## 5. Cost

`python tools/session_cost.py` at the end: see the final line of the session report.
