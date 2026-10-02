# Five native-evolving starters: identical evolution points and similar strength, costed

**Status:** PROPOSAL, research and costing only (2026-10-02). Nothing is built. The owner decides.
**Evidence:** `docs/research/NATIVE_STARTERS_1_8_0.md` (VERIFIED / ASSUMED, with sources). Figures marked MEASURED come
from `tools/battle_sim.py`'s own functions, run from a scratch script that changed nothing in the repo.
**Supersedes for this question:** the one-mythical costing in `STARTER_DESIGN_COMPARISON.md` (its idea 2). Its idea 1,
traditional starters in the world, is being handled in another worktree.

## 1. The facts that drive the cost

1. **Only Cosmog evolves twice.** Kubfu, Type: Null, Poipole and Meltan each evolve once. Two identical evolution
   points for all five therefore needs a **same-species stage** on four lines. Only aspect-selected forms provide one.
2. **Natively, three of the five lines cannot follow a schedule:**
   - **Meltan never evolves** in our campaign. The jar has no Meltan evolution at all. Cobbleverse adds anvil + level 70,
     and the caps end at 62.
   - **Cosmog cannot deal damage** until level 53: its learnset is Splash and Teleport, and Cosmoem adds only Cosmic
     Power.
   - **Poipole can evolve at level 5**: Dragon Pulse is a level-1 move, and passive evolutions are checked every second.
   - Type: Null's friendship 160 lands wherever play style puts it. Kubfu needs scrolls our world does not supply.
3. **A level requirement is already a badge gate.** The cap is the next gym's ace (20/25/30/35/40/45/50/55, then the
   Elite Four at 60 and the Champion at 62). So level **31 can only be reached after gym 3, and 46 only after gym 6**;
   **30 and 45** are the arrival caps for gyms 3 and 6. No flag, learnset edit or move gate is needed, provided Rare
   Candy respects the cap (ASSUMED; EXP-049 step 4).
4. **Gym 3 and gym 6 are each about one stage behind a normal starter.** MEASURED from the jar, the 27 configured
   starters reach their middle stage at 16 (median; before gym 1) and their final stage at 36 (median; after gym 4).
   The points are deliberately late, which suits "the final form does not carry the midgame".
5. **Normalising base stats does not close the spread; typing and movepool do.** MEASURED in every variant below, and
   independently by `origin/research/2026-10-02-mythical-starters` (`194330c`). **Meltan is last in every scenario.**

## 2. Replacing the native method: what it actually takes

| Route | Two points on two-stage lines | Wild, raid and trainer copies | Files | Main risk |
|---|---|---|---|---|
| **Forms**: per-instance `species_additions` forms with their own `evolutions`, `baseStats` and `moves`, keyed by a starter aspect | **yes** (same-species stage) | untouched | our own JSON, committed | the same-species stage has never been run (EXP-049 step 3) |
| **Veto**: append our evolution with an aspect requirement, and refuse the native one in an `evolution_tested` callback (`q.set_result`) | no: one evolution | untouched | one `.molang` and five small additions | field names on `q.evolution` (ASSUMED; EXP-049 step 5) |
| **Full species files** at the jar paths, emitted to `build/` from a patch spec (the parallel note's choice) | no | **changed** (wild Kubfu, Meltan and Cosmog get our levels) | five species files and a shadowed CV-DP Meltan addition; MSD also ships `kubfu.json` | pack order against MSD and CV-DP (ASSUMED) |

Two things apply to every route:
- **The evolution is offered, not forced** (`optional` defaults to true). "Identical" means the same *earliest* point.
- **Kubfu keeps its choice** under any route if the replacement stays `item_interact` on the scrolls with a `level`
  requirement added. The campaign then hands both scrolls out.

## 3. Strength (MEASURED; wins of 35 leader Pokémon)

Settings: IVs 15, level-up moves only, no TMs, items, abilities or switching. These are lower bounds on spread, not
predictions. **Today's 27 configured starters: 9 to 27, median 17.**

"Shape" means the stat distribution a normalised stage is scaled into. It is each stage's own, except the Cosmog line,
which uses Solgaleo's shape and learnset because Cosmoem's 131/131 defences make a wall with 30 Attack.

| Variant | Points | Stage BSTs | Cosmog | Kubfu | Type: Null | Poipole | Meltan | Spread |
|---|---|---|---|---|---|---|---|---|
| Native, as the sim sees it | native | native | 0 | 9 | 16 | 9 | 2 | 0–16 |
| **b**: native stats, two-stage lines evolve at the first point | 31 / 46 | native | 3 | 22 | 26 | 20 | 12 | 3–26 |
| **b** | 30 / 45 | native | 8 | 24 | 29 | 23 | 14 | 8–29 |
| b, two-stage lines evolve at the second point | 31 / 46 | native | 3 | 14 | 21 | 14 | 2 | 2–21 |
| **a**: forms on every stage | 16 / 36 (the starter curve) | 310 / 405 / 530 | 16 | 20 | 21 | 16 | 8 | 8–21 |
| a | 30 / 45 | 310 / 405 / 530 | 12 | 18 | 16 | 10 | 6 | 6–18 |
| a | 30 / 45 | 360 / 450 / 530 | 17 | 20 | 18 | 14 | 7 | 7–20 |
| **a-lite**: forms on the first two stages, native final | 31 / 46 | 330 / 430 / native | 14 | 14 | 13 | 12 | 3 | 3–14 |
| **a-lite** | 30 / 45 | 330 / 430 / native | 19 | 18 | 17 | 12 | 7 | 7–19 |
| a-lite | 31 / 46 | 380 / 450 / native | 14 | 16 | 14 | 14 | 5 | 5–16 |
| **c**: b plus species-level stats and moves for Cosmog and Cosmoem (RELAYED from `194330c` §6c) | 31 / 46 | native, Cosmog rebased | ~16–18 | 22 | 26 | 20 | 12 | ~12–26 |

What the table says:
- **Without Meltan, a-lite at 30/45 is the tightest band measured: 12 to 19, around today's median.** Option b at
  30/45 spans 8 to 29, wider than today's 27 starters.
- **The form route's real lever is the movepool, which this table does not exercise.** Every "a" row reuses native
  level-up lists. Authored movepools are what would move Meltan and Poipole up and Type: Null down. That is a balance
  pass, not more machinery.
- **Meltan is the floor whatever is done to its stats.** Keep it and author a movepool (form or species level), or
  replace it as a candidate. This is a decision, not a fix.

## 4. Cost, side by side

| | **a: forms on every stage** | **a-lite: forms on stages 1–2, native final** | **b: veto route, native stats** | **c: b + Cosmog rebased** |
|---|---|---|---|---|
| Delivers two identical points for all five | yes | yes | no: one point on four lines | no: one point on four lines |
| Delivers similar strength | only with authored movepools | only with authored movepools; final stage native (540–680 from gym 6) | no (8–29) | partly (~12–26, relayed) |
| Affects wild, raid or trainer copies | no | no | no | Cosmog and Cosmoem species-wide |
| Forms to author | about 12 species. **Silvally needs a form per memory (17) and Urshifu one per style (2)**, because `getForm` takes the last matching form, so an appended form hides theirs | **10 forms on 6 species** (Cosmog, Cosmoem, and two each on Kubfu, Type: Null, Poipole, Meltan). Finals untouched: memories and styles keep working | 0 | 0 (two species-level additions) |
| Other data | `starters.json` category of five (`... level=5 aspect=cobblers_starter`); scrolls as rewards | the same | one callback, five appended evolutions, `starters.json`, scrolls | b plus two additions |
| Unproven links (EXP-049) | forms load and fight at form stats (steps 1–2); aspect carried across a species change (2) | steps 1–3: **the same-species stage is the riskiest single link** | steps 4–5 | steps 4–5 plus a `baseStats` addition loading |
| Tools | `battle_sim.py`: forms, aspects, our additions; `evolve()` beyond single-requirement levels; `config_starters()` keeps only the first word (`tools/battle_sim.py:991`) | the same | `battle_sim.py`: the replaced points and `item_interact` + level | as b, plus two additions |
| Tests | stress rewrite (§5); an independent audit of each stage's BST against the jar-derived starter curve (the expectation from the jar's starter lines, never from our additions) | the same, for two stages | stress rewrite; an audit that each replaced evolution is reachable under the caps (expectation from `data/trainers.json` aces) | as b, plus the Cosmog BST audit |
| Effort (ASSUMED, scaled from the one-mythical estimate of about 3 sessions) | **5–7 sessions** (the parallel note's figure; the Silvally fan-out dominates) | **about 4**: experiment 1, build and generator 1, tools and tests 1, movepool balance pass 1 | **about 2**: experiment (shared) 1, build, tools and tests 1 | **about 2–2.5** (relayed) |

The "about 3 sessions" for **one** mythical (`STARTER_DESIGN_COMPARISON.md:93`) does not multiply by five.
- **The machinery is shared:** one aspect, one emitter, one experiment, one tooling change.
- **Two things scale with the species:** the forms, and the movepool balance pass.
- a-lite holds the form count at 10 by leaving the finals native. It also keeps two native choices, Cosmoem's
  Solgaleo/Lunala and Kubfu's scrolls, at no cost.

## 5. The stress tests (VERIFIED by reading; the same under every option)

**What breaks:**

| Where | What | Breaks because |
|---|---|---|
| `tools/battle_stress.py:329-331` | raises unless `len(config_starters()) == 27` | 5 ≠ 27 |
| `tools/battle_stress.py:92-93` | raises unless `SAMPLE_SIZE % len(starters) == 0` | 108 % 5 = 3 |
| `tools/battle_stress.py:29-38` | `SAMPLE_SIZE = 108`, archetypes 24/18/18/18/15/15 | must re-total |
| `tools/battle_stress.py:2-7` and the report text | "all 27 configured starter species appear four times" | stale prose |
| `tests/test_battle_stress.py:69, 82-83` | `== 108`, `== 27`, four profiles each | count |
| `tests/test_battle_stress.py:148` | monkeypatches 27 synthetic starters | count |

`tests/test_server_config_record.py` uses its own fixture lists and is unaffected. Nothing else reads
`config_starters()` (grep this session).

**The arithmetic:**
- 105 (21 each), 110 (22) and 120 (24) all divide by 5.
- **115 = 25/20/20/20/15/15** (the parallel note's proposal) also keeps every archetype a multiple of 5. That is about
  6% more simulation than 108.
- If the 27 ever stay on the screen beside the five, it is 32 starters, and 96 or 128.

**The real cost is the starter model, not the count.**
- The stress test seats the starter as `{"species": <first word>, "lo": 5, "hi": 5}`. It is evolved only by
  `battle_sim.evolve()`, which follows a `level_up` with **exactly one** `level` requirement
  (`tools/battle_sim.py:277-300`). `load_pack` reads only the jar's species, never our additions or forms.
- Left as it is, it would seat:
  - a Splash-only Cosmog that becomes a Cosmoem and never a Solgaleo (two requirements);
  - a Kubfu, a Type: Null and a Poipole that never evolve;
  - a Meltan with no evolution at all.
- That is a confident measurement of the wrong Pokémon, which is worse than a red test.
- **The fix, under any option:** one authored starter record, which `battle_sim` reads, giving per line the stage
  species, its base stats and its level-up list for each level band.
  - Under a or a-lite, the generator emits our additions from that same record.
  - The audit's expectation must still come from the jar's starter lines (CLAUDE.md, "How to prove an audit is
    independent").
- **Once the 27 are wild catches** (the other worktree), "27 × 4" is a stale model, not only a broken assertion.

**Cost:** about one session, in every option, and the same work whichever is chosen. Then one full stress run in the
integration session.

## 6. Recommendation

1. **Run EXP-049 first.** One staging session settles every unproven link:
   - forms load and fight at form stats;
   - the aspect survives a species change;
   - the same-species stage works;
   - the cap holds against Rare Candy;
   - the `evolution_tested` veto works.
2. **If steps 1–3 pass: a-lite at 30 / 45.** It is the only option that gives all five two identical points. It leaves
   wild copies alone and has no Silvally or Urshifu fan-out. It measured the tightest band (12–19 without Meltan).
   - 30/45 makes the partner evolve *for* gyms 3 and 6. 31/46 makes it a reward and measures weaker (3–14).
   - Budget the fourth session for authored movepools.
3. **If step 3 fails** (no same-species stage), **take c with the veto route**: one point at 30 for the two-stage lines
   and 30/45 for Cosmog. That is about 2 sessions. Accept the spread and present the differences as the choice.
4. **Decide Meltan separately.** It is last in every scenario. Keep it with an authored movepool, or swap it for
   another line.
5. **Budget about one session for the stress-test starter model whichever option is chosen.** Do not trust a stress
   figure for the five until it lands.

## 7. Decisions for the owner

1. **Points:** 30/45 (evolves *for* gyms 3 and 6) or 31/46 (a reward *for* beating them)? Or the starter curve, 16/36?
2. **Two points on every line** (a-lite) **or one** on the two-stage lines (b or c)?
3. **Forced or offered:** `optional: false`, or let a player keep the base form?
4. **Meltan:** keep it with an authored movepool, or replace it?
5. **Kubfu's scrolls:** handed out by whom, and at which point?
