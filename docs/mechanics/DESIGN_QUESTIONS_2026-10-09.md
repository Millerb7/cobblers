# Design questions, 2026-10-09: what the designs settle, what is the owner's

**Status:** unit DESIGNQ, `content-architect`. Nothing here is built or run. It sorts every numbered question still
open at the end of the five Wave A designs. The owner's instruction (2026-10-09) was: "answer the ones the design
settles, record the call, build. Bring me only the ones that are genuinely mine."

**The five files:** `docs/mechanics/ITEM_ROUTES.md` (A6), `EV_IV_TRAINING.md` (A7), `MINECRAFT_PLAY_LOOPS.md` (A8),
`docs/story/CAMPAIGN_OUTLINE.md` (A9), `docs/world-building/SIDE_ISLANDS.md` (A10).

**The owner's decisions used here:** `docs/STATE.md` "What is decided":
- `:139`, the answers of 2026-10-07, cited as (10-07 n);
- `:140`, the Wave A answers of 2026-10-08, cited as (10-08 n);
- `:141`, the decisions of 2026-10-09, cited as (10-09 n).

**The test for "settled by the design":** the file recommends one answer, and that answer moves no progression gate,
level cap, owner-set price or story.

## 0. Premises found wrong while sorting

1. **A8 and A9 have no decisions section, but both were built from.** The morning report lists builds from them:
   the Northlight barter from A8, and from A9 the bird hint and the after-Koga Mega field line
   (`docs/MORNING_REPORT_2026-10-09.md:22,33`).
2. **The thunder feather does have a source.** `SIDE_ISLANDS.md:44,236-239` and
   `data/adopted_legendary_sites.json:336` say nothing hands it out, and the last says "issuing false". But
   `data/research_station.json:180` issues it at `gym8_cleared`, by the owner's decision of 2026-10-02 (`STATE.md:136`).
3. **U71 is real, and the zone reasoning cites the wrong lot.**
   - `data/rift_zones.json:522` says the League's lot is x3517-3636 z2591-2701.
   - The built lot is x3635-3754 z2375-2485 (`data/placements.json:1769-1777`, and `data/towns.json` agrees).
   - The built lot is north of the `behind_league` cut at z2560 (`rift_zones.json:1040`), so it lies inside z4.
   - z4 and z5 were cut for the old lot.
4. **The 10-09 ruling does not cover 18 of the 41 held lines.** It names TMs only. The held lines are 23 TMs,
   17 memories and the Sachet (N127, `docs/OVERNIGHT_REVIEW_2026-10-06.md:136`).
5. **EXCH's TM prices are superseded.** The $500-$7,300 prices (`ITEM_ROUTES.md:384`, D3) are replaced by (10-09 1).
6. **"A Link Cable works forever" is unverified** (`ITEM_ROUTES.md:56`). If the cable is consumed on use, it is
   priced per use, not as an unlock.
7. **The owner's hand-placed spawn blocks may draw nothing inside sub-regions.**
   - The owner places them (STATE `:142`).
   - The suppression strips every inherited spawn there, block-keyed ones included (`MINECRAFT_PLAY_LOOPS.md:18-37`,
     relayed; `tools/suppress_inherited_spawns.py:16-19`).
   - The amount of land outside every polygon has not been measured.

## 1. Taken overnight 2026-10-08, still standing (not re-asked)

| File | Q | Call | Where |
|---|---|---|---|
| ITEM | Q1 stage 1 | The 23 pool TMs, curated (Route A) | `ITEM_ROUTES.md:382` D1 (held, N127) |
| ITEM | Q11 | 17 memories at Northlight | `:385` D4 (held, N127) |
| EV | Q1 | Option B: the Training shelf | `EV_IV_TRAINING.md:351` (built, R14 applied) |
| EV | Q5 | Power items at tier 1 | `:352` (built) |
| EV | Q6 | HP first, steer with a power item | `:353` |
| EV | Q4 (part) | Vitamins stay at 3,500 on Northlight's counter | `:355` |
| EV | Q9 (part) | No hyper-training candies until EV-6 | `:354` |
| SIDE | Q6 (part) | The SQ-SUNSET-01 gate is off the charters | `SIDE_ISLANDS.md:294-301` (built) |

## 2. Settled by the design (8)

| File | Q | Call | Settling line | Build |
|---|---|---|---|---|
| ITEM | Q5 | Both Primal orbs at `champion_cleared` | `ITEM_ROUTES.md:139,146`. A new item gated per its gating rule, which (10-07 9) allows: "they can be gated" | Red Orb **built** (`:337`). The Blue Orb goes with the Kyogre cave |
| ITEM | Q9 | Link Cable at Fossick, the gym-3 rung, as an exchange line | `:200`. Price by the Fossick evolution-item rung, 18 diamonds (`MATERIAL_EXCHANGE.md:97`) | U5 |
| SIDE | Q2 | No gym moves. The leader's work is on the island | `SIDE_ISLANDS.md:96-99`. The owner's ask was "a story reason **or** move a gym" | none |
| SIDE | Q4 | The Long Isle is pointed at, not required for Blaine | `:70`. The gatehouse is deferred (section 5) | none until the bridge is designed |
| SIDE | Q8 | Retire the drowned Jungle Isle records | `:25` F6, `:262-266` | U7 |
| SIDE | Q9 | Northgate stays mount-only, with no dock | `:75` | none |
| OUTLINE | O2 | Keep the finale chain. Each required NPC gets a one-line path | `CAMPAIGN_OUTLINE.md:291-296`. Turning them into fights is not recommended | Codex C14 |
| OUTLINE | O7 | Retire the `jungle_ruins` record from `towns.json` | X10 `:248`. Same call as SIDE Q8 | U7 |

## 3. Settled by an owner decision already recorded (13)

| File | Q | Call | Decision |
|---|---|---|---|
| EV | Q3 | Boss EVs are parked with the team rewrite | (10-07 13): teams are parked |
| PLAY | Q1 | The Master Ball barter is at counter parity, a netherite block plus 21 ingots (30 ingots) | (10-08 5); `data/direct_trades.json:109-114` (built) |
| PLAY | Q2 | No badge gate. It is at Northlight, and its price is its gate | (10-08 6); `direct_trades.json:42` |
| PLAY | Q4 | Pooling is co-op. No per-player limit, which neither shop type can express | the approved lines share stock by design (`direct_trades.json:56,64,195`). Reopen if not meant |
| PLAY | Q5 | The bank keeps buying ranch drops | (10-07 2): "the bank may pay for anything" |
| PLAY | Q6 | Keep the money exchange lines. The barter is the alternative | (10-08 5); `direct_trades.json:197` |
| PLAY | Q7 | Sell seeds, not product. Mint seeds by barter at Northlight | (10-07 5) "no money where possible". Both designs route seeds (`ITEM_ROUTES.md:176`, `MINECRAFT_PLAY_LOOPS.md:107`) |
| SIDE | Q5 | The thunder feather comes from Shrew Station at `gym8_cleared` | STATE `:136` (2026-10-02); `research_station.json:180` (data, not run) |
| SIDE | Q7 | No ferry repair now. Pacifidlog's prices assume a 6-badge arrival, so a repaired line must not open it earlier without re-pricing | (10-08 2) |
| SIDE | Q10 | The Sunset strait ferry stays ungated | STATE `:144` (over-cap wild Pokemon welcome) and (10-07 4); priced reach 0 (`data/traders.json:597`) |
| SIDE | Q11 | Misty stays parked | (10-07 13); `docs/HANDOVER_SESSION.md` 2c |
| OUTLINE | O5 | Re-cut the zone; do not move the lot | STATE `:175` (the League at the Rift head, built there); z4 is postgame (`rift_zones.json:2815`). U8 |
| OUTLINE | O6 | Sunset West opens early and Northlight at `gym5_cleared`, as built. `ARC.md:671-672` is stale | (10-07 4), (10-08 2); `traders.json:597` |

## 4. Genuinely the owner's (20 questions, as 12 choices)

1. **TMs** (ITEM Q2, and the 10-09 bar):
   - **(a) The price bar.** Price each leader's TMs above the income to that leader's badge, or above the badge-1
     income for all TMs?
     - By leader's badge, the data's own income-gate rule (`traders.json:587`; income relayed from
       `markets.json:19`): $9,500, 17,100, 28,700, 45,700, 61,000, 82,300, 109,100 and 145,100 for gyms 1-8.
     - Flat: $9,500 for every TM.
     - *Recommended: by leader.* The flat reading lets a player with one badge buy Earthquake. But Giovanni's TMs then
       cost more than all the income modelled to badge 8.
   - **(b) Reuse.** Does "TMs are permanent unlocks" mean reusable TMs (`consumeMoveItemOnUse` false)?
2. **"Every item": its scope and what counts as crafting** (ITEM Q1 rest, Q4, Q7, Q8, Q10):
   - Declare out, with a reason, the items whose species or mechanic is absent: the 32 Mega Stones less the
     Darkranite, the plates, drives, masks, relics and radars, the Beast Ball, and the locators if disabled.
   - Route the 14 ancient balls at a late counter (the recommendation), or cut them?
   - Is "every TM" the 23-TM pool or all ~930 (relayed)?
   - Do smelting, brewing and the campfire pot count as crafting?
3. **Mewtwo** (ITEM Q3): is it in?
   - If yes, the catalyst and a second DNA at Blue (the recommendation).
   - Separately: does Blue give the Origin Fossil itself, or does Mew stay the one crafted legendary?
4. **Dynamax** (ITEM Q6): off, or kept with a post-Champion band and a Power Spot? There is no recommendation.
5. **Prices** (ITEM Q12, EV Q7): `trainer-balance-designer` sets every PROPOSED price against `income_basis` under
   your rules (the income gate, the exchange rule, the barter band), and you approve the table. Or do you set each
   one? *Recommended: the former.*
6. **EV training** (EV Q2, Q4 rest): is the built option B (battle training, a power item and the shelf) "EV training
   implemented"? Or do you want EVs bought outright, with cheap vitamins everywhere? That needs overriding the base
   bank's 2,500 buy-back.
7. **Nuzlocke** (EV Q8): is a training ground its own catch zone, or part of its sub-region's? The status quo is part
   of the sub-region's.
8. **Spawn blocks** (PLAY Q8, then Q3): should the default pool really be open in "wilderness" when the suppression
   covers every sub-region? Your hand-placed blocks act only where it is open (premise 7). Then attractor gardens: bias
   the place's own species, or bring new ones?
9. **Northlight before Sabrina** (SIDE Q1, Q3): rctmod `requiredDefeats` on the student, or only signposted? If
   required, two $400 crossings land on the critical path: keep that fare, make the first crossing free, or lower it?
   *The design recommends P1-alt; whether it is required is open.*
10. **Challenge and the story** (O1): may a Challenge player skip the story, which is already true in both modes? Or
    should Challenge show less? *Recommended: one story in both modes.*
11. **The release** (O3): does the first release change the shared world, or does each player release Hoopa alone,
    as built?
12. **Victory Road** (O4): is it the only way up, or may players bypass it on the surface?

**Deferred, not askable yet:** EV Q9 (sell hyper-training candies once EV-6 passes) and SIDE Q4's gatehouse
(asked with the bridge's design).

**In-game check, not a decision:** O8. Click the Brock at (1832, 142, 3661). If `dlg_main_brock_witness` opens, he
is the witness.

## 5. Codex's (story text, 15)

- **C1-C12** as listed at `CAMPAIGN_OUTLINE.md:304-329`:
  - C1: the Craters scene, which must set `crater_operation_stopped`;
  - C2: Hoopa caught or freed;
  - C3: the mid-game clerks;
  - C4: Maren;
  - C5: the `quests.json` corrections;
  - C6: the Scar and the Displaced City;
  - C7: the placeholder lines and X15;
  - C8: the two Directors;
  - C9: who Blue is;
  - C10: the legendary hooks and the starters;
  - C11: the postgame repair;
  - C12: the guards.
- **C13** (SIDE Q6, the remainder): write SQ-SUNSET-01 on the Sunset Isle, re-sited off the drowned coordinates
  (F7). Once it can be granted, the owner decides whether the charters re-gate, by moving `superseded_gates` back.
- **C14** (O2): a one-line path for each of the seven required finale interactions.
- **C15:** the stale facts in `ARC.md`:
  - X1, the League's position;
  - X9, Sunset West and Northlight as postgame;
  - X10, the jungle ruins;
  - X12, the Scar, which is built.
- **Conditional:** if choice 9 is "required", Codex also writes the student, the aide, the Fenhide pointer and the
  quest text (`SIDE_ISLANDS.md:153`).

## 6. Build list

Every unit uses plain single commands and runs its own generator and tests, never prepare. "Server" means the main
session: lock, install, apply and probes. Writer and auditor are different agents.

**Already built, none to redo:**
- the Red Orb and Prison Bottle caches;
- the Training shelf;
- the Northlight barter;
- the Relic charter ungated;
- the bird hint;
- the after-Koga line.

**Held:** the 41 counter lines (2833317).

### U1. TM-PRICE: restore the 23 TM lines at the income gate (10-09 1)

**Builder:** `datapack-content-dev`.

**Files:**
- `data/markets.json`: the lines from commit 2833317, at Fossick and Northlight.
- `tools/markets.py`: the price is generated from a `price_rule: income_gate` naming the leader's badge, not typed
  in, so it follows `income_basis`.
- The note in `data/bank.json` `not_built`.

**Done when:**
- Every TM costs the smallest $100 multiple strictly above `cumulative_by_badge[leader]`. Choice 1a may change one
  field.
- `markets.py ids` passes.
- `economy_audit` shows 0 arbitrage failures.

**Audit:** U1A. **Server:** R17M, then `install_check`.

### U1A. COUNTER-AUDIT: teach the counter audits (test-author)

**Files:** `tools/town_squares_audit.py`, `tools/markets_audit.py`, `tests/`.

**The checks:**
- Accept TMCraft ids by item model (the EXCH gap at `ITEM_ROUTES.md:395`).
- Accept an income-gate price as a gate. The audit computes it itself from `income_basis`, and the leader from
  `data/progression.json` `first_win_rewards`.
- Accept a declared use-gate (U2), verified against `data/mythical_starters.json` and `data/spawns.json`.

**Mutation:** change the rounding or the badge inside `markets.py` and leave the data untouched. The audit must fail.

### U2. USE-GATED: restore the 17 memories and the Sachet (D4, D5)

**Builder:** `datapack-content-dev`.

**The gate each line declares:**
- Memories: inert before Silvally at L45 (`mythical_starters.json:404-414`).
- Sachet: Spritzee is tier 3, and the 18-diamond exchange price is fixed by rule.

**Done when:** U1A passes. **Server:** R17M.

**Flag to the owner, not a question:** if (10-09 1) was meant for all 41 lines, these take the U1 rule instead.

### U3. TROPHIES-OUT: arena prizes leave the barter (10-09 3)

**Builder:** `datapack-content-dev`.

**Files:** `data/direct_trades.json`.
- **Supersede five lines:** `ability_patch`, `life_orb`, `choice_band`, `choice_scarf` and `leftovers`. Set each to
  `approved: false`, `status: superseded`, with the decision and the why. Keep them in place: the file is
  `generated_by: hand`.
- **Close `decisions_pending` `held_items_money_line`:** no money line for the five (10-09 3), and barter only for
  Specs and the Knot (10-07 5).

**Done when:** three lines remain.

**Audit (test-author):** sweep `data/arena_fights.json` prizes against every seller (`markets.json`, `traders.json`,
`direct_trades.json`). Do not use a list. Measure the five against `arena_fights.json`; they are relayed from N125.

**Server:** R18DT, then read the barterer's offers back.

### U4. GRISEOUS: the Core and Orb at Giratina's altar (ITEM 2.3, N118)

**Step 1, test-author:** let a sweep site declare extra caches, exempt from the one-item rule and from the clearance
skip set (`tools/legendary_sweep.py`, `tools/legendary_sweep_audit.py`, the clearance check).

**Step 2, `datapack-content-dev`:** re-add the drafted record (`ITEM_ROUTES.md:357-361`), gated on
`champion_cleared`.

**Server:** install.

### U5. CABLE-UPGRADE: the Link Cable at Fossick, the Upgrade at Northlight

**Builder:** `datapack-content-dev`.

**Files:**
- `data/markets.json`:
  - the Link Cable at 18 diamonds;
  - the Upgrade at 3 ingots, beside the Dubious Disc (`ITEM_ROUTES.md:201`).
- `data/gulch_mine.json`: move `zamega:darkranite` out of `left_out` (ITEM Q4 note; Darkrai is adopted).

**Before writing:** read in the snapshot jars:
- the ids;
- whether the Link Cable is consumed (premise 6);
- the Darkranite id.

**Done when:** `markets.py ids` and `economy_audit` pass. **Server:** R17M.

### U6. SEEDS: mint seeds by barter at Northlight (PLAY Q7)

**Step 1, `cobblemon-researcher`:**
- Do mint seeds grow and yield in survival (`MINECRAFT_PLAY_LOOPS.md:282`)?
- What are the seed ids?

**Step 2, `datapack-content-dev`:** six barter lines, priced by `pricing.band` against a reference named per line.
3 + 6 = 9 lines is over `rules.max_lines` 8, the "short list" cap (`tools/direct_trades.py:170`). Raising the cap is
a recorded edit with its reason.

**Server:** R18DT. **Waits on** step 1.

### U7. DROWNED: retire the stale records (SIDE Q8, O7, F6 and F7)

**Builder:** `datapack-content-dev`.

**Retire, with a reason; do not delete:**
- `data/regions.json` `jungle_isle`;
- `data/spawns.json` `jungle_west` and `jungle_east`;
- `data/towns.json` `jungle_ruins`.

**Correct:**
- the `long_isle` `character` line;
- the Sunset landing note;
- `adopted_legendary_sites.json:336` (premise 2).

**First:** list every consumer of these ids. Pacifidlog's 43-53 "jungle residue" band may draw on them. Retiring a
polygon must not silently drop it from the suppression boxes.

**Done when:** `validate_data`, `id_authorship` and `tests/test_system_contracts.py` pass.

**Server and prepare:** the spawn compile, suppression and install run in the main session.

### U8. Z4-LEAGUE: re-cut z4 and z5 off the built League lot (O5, U71)

**Builder:** `minecraft-systems-dev`.

**Files:** `data/rift_zones.json`:
- move `behind_league` north of z2375;
- check that `league_gate` still lies on the approach;
- correct the stale `:522` lot.

**Done when:** the walk check no longer warns N30 "P0 4", and the steward (3647, 89, 2490) and the forecourts are in
z5.

**Before starting:** check whether `tools/rift_zones.py` reads `derived/`. If it does, run that part in the main
session.

**Server:** the walls are re-applied, then the gatehouse is verified.

### U9. GYM1-WAYPOINT: land N120 (O1 "either way")

**Builder:** `datapack-content-dev`.

**Files:** the gym 1 marker record and the `gym_markers` note in `data/progression.json`, as in
`docs/world-building/WALK_P2.md` section 2.

**Done when:** the Oak test model and the dialogue checks pass. On a scratch copy the edits passed 628/0 (N120,
relayed).

**Server:** install. **In game:** EXP-020 part F.

**Waiting on choice 5, the prices, not units:** the brewing stand, PP Up and Max, the bottle cap, the pot and
teacup, candies and the ancient balls.
