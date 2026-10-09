# The economy with the dungeons in it: a simulation (2026-10-09)

The owner's question (2026-10-09): *"Dungeons change the economy: entry costs, held rewards, drops, the greed ladder.
Re-run the economy model with them in and tell me whether it is still where it needs to be: the income by badge, the cost
of the late game, what a player can afford, and whether any route now prints money or starves a player. Simulate it, do
not reason about it."*

Everything numeric below is the output of `python tools/economy_sim.py` (default seed 1, 300 players a cell; the tables
are written into this file by `--write-doc`). Nothing in it was seen in a running game: the dungeon engine has not run on
a server (`data/dungeons.json` status), and the payout formula's inclusive draw is ASSUMED
(`docs/research/notes/paid-services-and-npc-payouts.md` B2). Tests: `tests/test_economy_sim.py`.

## Verdict

**Where it needs to be: yes, with one defect to fix before the stands are built.**

1. **The design (the clawback works) leaves the economy where it was.** A steady player who runs the Night Shift once a
   leg ends the campaign with $328,345 against $333,511 for the same player with no dungeons (-1.5%); the dungeon is a
   small sink (T10: -0.7% to -4.4% of a leg's curve income). Spend over income stays at 0.67-0.68 at every badge with no
   dungeons, reproducing `tools/markets.py report` (0.672-0.676), which the sim does not call.
2. **No loop prints money.** The best as-built dungeon hour is 0.05, 0.10, 0.10, 0.21, 0.23 and 0.53 of the band's fight
   hour (T2), under the design's parity line (1.0) and R5's ceiling (1.5) in every band, at every win rate swept
   including a perfect player (T8: at most 0.75). Gathering, produce and the AFK farm are unchanged and under parity (T11).
3. **No route starves a player.** A steady, greedy, AFK or Challenge player never falls short of the Mart and ferries in
   any leg and leaves a leg's curve shelf unbought in at most 1% of runs (T5). The only starving type
   is the pure fighter in legs 1 and 2 (backlog in 55% and 36% of runs): the design already says legs 1-3 are
   "covered by produce and about two hours of mining" (`ECONOMY_OVERHAUL.md` 1.3), and dungeons do not change it.
4. **Defect 1 (the boss stage pays the NPC payout, no clawback) is the one that matters.** It turns the dungeon from a
   sink into the best non-fighting hour from band 4 up: 1.72x, 1.35x and 4.32x the gathering hour at that badge (T2), and
   it is the best post-Champion income there is ($9,965 net an hour for a player who runs band 6 every hour, against
   -$1,459 in the design and $2,120 for typical Nether mining). Over a campaign it adds $11,820 to a steady player
   (+3.6%), $42,020 to a greedy runner (+12.8%) and about $100,000 per ten post-Champion hours (T6). It is not a print by
   the stated threshold, but it reorders the late game: a completionist's EV and IV bill for one team ($722,400, T7)
   becomes about 72 hours of band-6 runs instead of 118-341 hours of Nether mining.
5. **Building the stands before the clawback WOULD print money.** The same payout on the three stands is 1.03x parity at
   band 1, 2.0-2.9x at bands 2-4, 5.6x at band 5 and 16.5x at band 6 ($283,074 an hour, T2): a campaign ending with
   $1.0M for the greedy runner and $3.8M after ten band-6 hours (T6). The clawback is not optional for step 6.
6. **Defect 2 (the TM gate's `recipe give @s *` opens every sigil recipe) is nothing in money.** Worst case, every player
   crafts the next band's sigil once, in the window: -$102 a player over a campaign (T6). The window only exists when the
   gate re-syncs a player (first join, the starter pick, a plan-key change; `tools/tm_gate.py` sync and `regivers`), and the
   rip only overcharges a higher sigil, never refunds one.

## Premises checked first (the brief and the repository disagree in places)

| Premise | Found |
|---|---|
| "`data/markets.json` `income_basis` (model B)" | **Stale.** `income_basis` now holds the measured quadratic model (`tools/income_model.py`: cumulative $4,033 at badge 1 to $202,835 at badge 8, Challenge $338,847). Model B ($9,475 to $145,078) is kept under `superseded_model_b`. `tools/bank.py:450` still says "relayed model B" and `data/bank.json` `effort_model.label` still says the leg incomes are RELAYED from it, but the code at `bank.py:456` reads the live `leg_by_badge`. The sim uses the live model, and its drawn fights reproduce `exact_expectation` to 2% (tested). |
| Boss payouts per run $202-405 / $855-1,710 / $11,062-22,125 | **Re-derived, correct.** Stage teams from `data/dungeons.json` (offsets -2/-1/0 on the band's lower cap, the escort on the last stage from band 4), the formula B = int(5 S sum(L/50)), credit = floor(1.25 (B + U[B/2, 2B])). Band 6's $11,062 needs the escort: stages 98, 99 and 100+99 give S = 98, 99, 199. All six bands equal `tools/dungeon_audit.py --payout` and the generated NPC classes (tested). |
| "The Nether tier opens at leg 7" (`data/bank.json` `effort_model.tiers.nether.opens_leg`) | **Disagrees with `data/nether_gate.json`** (`gym8_cleared`, badge 8). `tools/markets.py` `r2_earned` therefore counts a $2,120 Nether hour in legs 7 and 8 that no player can have. The curve ratio at badges 7 and 8 reads 0.685 and 0.688 instead of 0.675, still inside 0.65-0.70. The sim uses the gate. |
| STATE: EV and IV training "~$50,000 in all if fully used" | **Disagrees with `data/training_services.json`**: EV $17,200 a Pokemon, IV $17,200 a stat, repeat purchases at full price. One Pokemon perfected is $120,400, a team of six $722,400 (T7). The price rule (hours saved x leg 8's fight hour) superseded the owner's $50,000 figure. |
| A dungeon win "pays $0 net" (contract) | **Not met today**: the boss stage pays (defect 1). The stands are not built, so they pay nothing today. |
| The 1-hour lockout limits a dungeon to one run an hour | Holds for the Night Shift, the only dungeon (D19). Entei's lockout is 24,000 ticks (20 minutes of uptime) and is a pure money sink: two netherite ingots ($1,800) a Tower Ash, up to $5,400 an hour, its drops (Life Orb, Smoke Ball...) sold by no counter and bought by no bank line. |

## Method, and what is assumed

Read from data (a test mutates each and checks the result moves): `data/markets.json` (every battle's level sum,
Normal and Challenge; the fight allowance; every counter line), `data/bank.json` (prices, rates), `data/dungeons.json`
(bands, clocks, sigil recipes, the greed ladder, the boss), `data/blackout.json` ($600 flat), `data/produce_buyer.json`,
`data/training_services.json`, `data/mining_caves.json`, `modpack/config/cobbledollars/common.json` (the sim refuses a
world where wild battles pay or NPC battles do not).

Every battle is drawn from the real formula; no battle is priced at its mean. Paired scenarios consume the same draws,
so a difference between two scenarios is the difference and not noise. Scenarios: `design` (clawback works),
`defect1` (boss pays), `defect2` (recipe window), `as_built` (both), `stands_unclawed` (counterfactual).

Player types: **fighter** (fights only; no gathering, no produce), **baseline** (the model before dungeons: one
gathering hour and the produce allowance a leg), **steady** (baseline plus one Night Shift run a leg, safe), **greedy**
(four runs a leg at the seam take that earns most, and ten hours of band-6 runs after the Champion), **afk** (baseline
plus six idle farming hours a leg), **challenge** (Challenge rosters, two deaths a leg).

ASSUMED, swept where it matters (T8): 4 hours of fights a leg (`effort_model.max_leg_hours`, assumed there), Victory
Road 4, the League 2, the HQ tower 2; the bank's declared gathering rates x U(0.7, 1.3); one death a leg outside
dungeons (the curve's own blackout allowance); in a dungeon P(win a stand) 0.97, P(win a boss stage) 0.88-0.92,
P(fall or other death) 0.04; a run's time is DUNGEONS.md 4.2's planning table (relayed) times lognormal(0, 0.12) split
around the seam as 4.3 worked it for band 1; the seam's ore mix is the cave yields scaled to 24 blocks (the seam is not
authored: step 6; bands 3-4 without diamond, 5-6 with one); vanilla ore drops without Fortune. **A seam is worth $144 to
$318 a face and cannot carry a dungeon's economy whatever its mix** (T8: 12 diamonds still lose money at band 6 in the
design).

Not modelled: the items a run holds (gems, candies, battle items, the first-clear prizes) have no dollar value (no counter
sells and no bank line buys one; T9), co-op, the stands' fights beyond time and deaths, Heaven's Arena, rematches.

<!-- economy_sim:tables:begin -->
_Generated by `python tools/economy_sim.py --runs 300 --seed 1 --write-doc ...`; do not edit between the markers._

### T1. The boss payout per run, re-derived from the formula and data/dungeons.json

| Band | Stage teams (levels; a + is the escort) | Stage S | Per run, min-max | Per run, mean of 4,000 draws |
|---|---|---|---:|---:|
| 1 | 18; 19; 20 | 18, 19, 20 | $202-405 | $303 |
| 2 | 28; 29; 30 | 28, 29, 30 | $471-944 | $708 |
| 3 | 38; 39; 40 | 38, 39, 40 | $855-1,710 | $1,279 |
| 4 | 48; 49; 50+49 | 48, 49, 99 | $2,718-5,437 | $4,081 |
| 5 | 58; 59; 60+59 | 58, 59, 119 | $3,937-7,875 | $5,917 |
| 6 | 98; 99; 100+99 | 98, 99, 199 | $11,062-22,125 | $16,635 |

### T2. One dungeon run, by band (p(win a boss stage) 0.9; 3000 runs a cell; best seam take per scenario)

| Band | Badges held | Sigil bank value | Gather min | Seam face value | Fight hour (parity) | Design: take, net/run | Design net/h | Design / parity | As built: take, finish, die | As built net/h | As built / parity | Verdict (as built) | Gathering hour at that badge | As built / gathering | Stands unclawed net/h (x parity) |
|---|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|---|---:|---:|---|
| 1 | 0-1 | $39 | 9 | $144 | $1,008 | 24, $48 | $48 | 0.05 | 24, 0%, 8% | $48 | 0.05 | ok | $620 | 0.08x | $1,036 (1.03x) |
| 2 | 2-3 | $62 | 19 | $144 | $2,492 | 24, $25 | $25 | 0.01 | 4, 63%, 37% | $243 | 0.10 | ok | $1,350 | 0.18x | $5,924 (2.38x) |
| 3 | 4-5 | $160 | 25 | $224 | $5,358 | 24, $6 | $6 | 0.00 | 4, 63%, 37% | $558 | 0.10 | ok | $1,350 | 0.41x | $10,885 (2.03x) |
| 4 | 6-7 | $262 | 36 | $224 | $11,050 | 24, $-100 | $-100 | -0.01 | 4, 62%, 38% | $2,322 | 0.21 | ok | $1,350 | 1.72x | $32,006 (2.90x) |
| 5 | 8 | $900 | 48 | $318 | $12,335 | 24, $-644 | $-644 | -0.05 | 4, 62%, 38% | $2,860 | 0.23 | ok | $2,120 | 1.35x | $69,552 (5.64x) |
| 6 | Champion | $1,708 | 72 | $318 | $17,126 | 24, $-1,458 | $-1,458 | -0.09 | 4, 62%, 38% | $9,150 | 0.53 | ok | $2,120 | 4.32x | $283,074 (16.53x) |

### T3. The greed ladder: net money per run by seam take (blocks), design vs as built

| Band | Scenario | take 4 (x1) | take 9 (x1.2) | take 14 (x1.5) | take 19 (x2) | take 24 (x3) |
|---|---|---:|---:|---:|---:|---:|
| 1 | design | $-241 | $-300 | $-8 | $25 | $48 |
| 1 | as_built | $-29 | $-90 | $-8 | $25 | $48 |
| 3 | design | $-350 | $-390 | $-85 | $-35 | $6 |
| 3 | as_built | $558 | $497 | $-85 | $-35 | $6 |
| 4 | design | $-453 | $-494 | $-183 | $-136 | $-100 |
| 4 | as_built | $2,322 | $2,056 | $-183 | $-136 | $-100 |
| 6 | design | $-1,890 | $-1,910 | $-1,577 | $-1,511 | $-1,458 |
| 6 | as_built | $9,150 | $8,463 | $-1,577 | $-1,511 | $-1,458 |

### T4. Income per active hour by stage (as built; mean of 300 players per type)

| Stage | Badges | Fight hour | fighter | steady | afk | challenge | greedy |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 1,008 | 996 | 1,076 | 1,247 | 1,851 | 749 |
| 2 | 1 | 1,144 | 1,154 | 1,047 | 1,205 | 2,182 | 732 |
| 3 | 2 | 2,492 | 2,473 | 2,044 | 2,365 | 3,735 | 1,553 |
| 4 | 3 | 4,104 | 4,080 | 3,068 | 3,590 | 5,510 | 2,226 |
| 5 | 4 | 5,358 | 5,382 | 3,999 | 4,631 | 6,242 | 3,002 |
| 6 | 5 | 8,427 | 8,389 | 6,019 | 6,964 | 10,010 | 4,344 |
| 7 | 6 | 11,050 | 11,048 | 8,031 | 9,139 | 13,082 | 6,357 |
| 8 | 7 | 17,126 | 17,132 | 12,015 | 13,986 | 17,461 | 9,011 |
| vr | 8 | - | 12,231 | 9,237 | 10,264 | 10,662 | 7,538 |
| league | 8 | - | 88,000 | 87,157 | 87,473 | 87,654 | 87,174 |
| hq_tower | 8 | - | 20,275 | 20,661 | 20,527 | 20,548 | 20,536 |
| champion, 10 h of runs | 8+ | (leg 8: 17,126) | - | - | - | - | 11,877 gross, **9,965 net** (design: 294 gross, -1,459 net) |

Active hours: fights (4 a leg, VR 4, League 2, HQ 2) + the gathering hour + dungeon hours (1 per run, the lockout). The AFK farmer's 6 idle hours a leg are not counted. 'Income' is every dollar in (fights, gathering, produce, ore, boss payout), before costs.

### T5. Savings and what the late shelf lets them buy (as built; savings = cash after the Mart, ferries, deaths, sigils and the curve's own shelf)

| After | Fighter savings | Steady savings | Steady buys of late shelf | Greedy savings (as built) | Greedy (design) | Challenge savings | Steady cum. income | Starves? (steady / fighter) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | $366 | $2,045 | 4% of $44,500 | $2,200 | $2,200 | $6,002 | $6,455 | no / BACKLOG 55% |
| 2 | $689 | $3,836 | 7% of $46,700 | $4,382 | $4,382 | $14,080 | $12,740 | no / BACKLOG 36% |
| 3 | $2,474 | $7,852 | 4% of $186,040 | $9,393 | $8,393 | $27,682 | $25,002 | no / no |
| 4 | $6,429 | $13,844 | 7% of $189,340 | $16,275 | $14,333 | $47,686 | $43,408 | no / no |
| 5 | $12,459 | $21,823 | 10% of $197,840 | $26,250 | $22,009 | $68,405 | $67,403 | no / no |
| 6 | $22,255 | $33,798 | 11% of $293,140 | $40,175 | $33,408 | $103,717 | $103,518 | no / no |
| 7 | $35,149 | $50,210 | 17% of $301,840 | $64,214 | $47,253 | $149,800 | $151,704 | no / no |
| 8 | $55,955 | $74,017 | 24% of $308,240 | $95,715 | $68,410 | $205,703 | $223,795 | no / no |
| vr | $102,398 | $125,757 | 41% of $308,240 | $156,545 | $114,525 | $265,454 | $279,217 | no / no |
| league | $277,778 | $299,465 | 91% of $308,240 | $330,267 | $288,247 | $439,537 | $453,531 | no / no |
| hq_tower | $317,680 | $340,165 | 100% of $308,240 | $370,806 | $328,786 | $479,387 | $494,853 | no / no |
| champion +10 h of runs | - | - | - | $470,461 | $314,193 | - | - | - |

The whole late shelf is $308,240 (one of each line). 'Buys of late shelf' takes the lines available at that badge, cheapest first.

### T6. The two defects, separated (campaign end = after the HQ tower; post = after 10 more hours of band-6 runs)

| Scenario | Steady: savings at end | Steady vs design | Greedy: savings at end | Greedy vs design | Greedy: post-Champion 10 h | vs design |
|---|---:|---:|---:|---:|---:|---:|
| design | $328,345 | +0 | $328,786 | +0 | $314,193 | +0 |
| defect1 | $340,267 | +11922 | $370,908 | +42122 | $470,563 | +156369 |
| defect2 | $328,243 | -102 | $328,684 | -102 | $314,091 | -102 |
| as_built | $340,165 | +11820 | $370,806 | +42020 | $470,461 | +156267 |
| stands_unclawed | $500,747 | +172402 | $1,009,228 | +680442 | $3,839,934 | +3525741 |

### T7. The late game's bill (priced from the data)

| Item | Low | High | Note |
|---|---:|---:|---|
| The late shelf: every counter line not on the curve (off-path counters, critical power, stretch), one of each | $308,240 | $308,240 | data/markets.json counters; includes the Master Ball and one Beast Ball |
| Level-raise service for a team of six at every cap step (10 steps x 6 x $500) | $30,000 | $30,000 | optional; STATE says ~$30,000 |
| Effort training, one Pokemon (EV spread) | $17,200 | $17,200 | per Pokemon |
| Perfect IVs, all six stats of one Pokemon | $103,200 | $103,200 | per stat, bought again at full price even at 31 (services.iv.repeat_rule) |
| EV + IV for a team of six | $722,400 | $722,400 | STATE's '~$50,000 if fully used' predates the per-hour pricing rule |
| Beast Balls for ONE boss catch (Entei, built) | $20,000 | $95,000 | 4 throws asleep at 1 HP .. 19 at full HP; a failed throw spends the ball (key_ball.json) |
| Tower Ash for an Entei attempt (2 netherite ingots at the bank) | $1,800 | $1,800 | per attempt; lockout 24,000 ticks (20 min of uptime): a farm-mode hour can cost 3 ashes |

Steady player, cumulative income through the League and HQ tower: $494,853; savings then: $340,165 (as built).

### T8. Sensitivity: how the as-built dungeon hour moves with the assumptions I could not measure

| Band | p(win a stage) | Finish | Net/h as built (best take) | Parity ratio |
|---|---:|---:|---:|---:|
| 1 | 0.75 | 0% | $49 | 0.05 |
| 1 | 0.90 | 0% | $49 | 0.05 |
| 1 | 0.97 | 79% | $108 | 0.11 |
| 1 | 1.00 | 86% | $166 | 0.16 |
| 4 | 0.75 | 35% | $1,144 | 0.10 |
| 4 | 0.90 | 62% | $2,283 | 0.21 |
| 4 | 0.97 | 77% | $2,913 | 0.26 |
| 4 | 1.00 | 84% | $3,230 | 0.29 |
| 6 | 0.75 | 36% | $5,234 | 0.31 |
| 6 | 0.90 | 62% | $9,269 | 0.54 |
| 6 | 0.97 | 79% | $11,720 | 0.68 |
| 6 | 1.00 | 86% | $12,837 | 0.75 |

Seam diamonds on the band-6 face (design, greed take 24, turn back):

| Diamonds on the face | Face value | Net/run (take 24) | Net/h |
|---:|---:|---:|---:|
| 0 | $224 | $-1,547 | $-1,547 |
| 1 | $318 | $-1,462 | $-1,462 |
| 3 | $546 | $-1,238 | $-1,238 |
| 6 | $885 | $-935 | $-935 |
| 12 | $1,547 | $-305 | $-305 |

### T9. The held rewards are items, not dollars (design, seam take 4 = the free tier and finish the run; p(win a stage) 0.9)

| Band | Finish rate | Area gems a run | Boss bundle (relayed, DUNGEONS.md 9.2) | Bundles an hour |
|---|---:|---:|---|---:|
| 1 | 63% | 1.9 | 1 M + 2 S candies | 0.63 |
| 2 | 63% | 1.9 | 3 M candies | 0.63 |
| 3 | 63% | 3.8 | 1 L + 2 M candies | 0.63 |
| 4 | 62% | 3.7 | 2 L + 1 M, 1-2 IV candies | 0.62 |
| 5 | 62% | 5.6 | 1 XL, 2-3 IV candies, 1 Rare Candy | 0.62 |
| 6 | 62% | 5.5 | 2 XL, 3-4 IV candies, 1-2 Rare Candy | 0.62 |

Counter lines selling a candy or a type gem: 0 (none). Bank lines buying one: 0. So a reward has no dollar price anywhere in the economy and a held reward cannot be sold: its worth is the levels and TM crafts it saves.

### T10. What the dungeons do to the money the curve was built on (steady player, per leg)

| Stage | Curve income (fights+gather+produce) | Spend on the curve (Mart, ferries, deaths, shelf) | Spend / income, no dungeons | Dungeon net, design | Dungeon net, as built | Dungeon net / curve income, design | as built |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | $6,214 | $4,185 | 0.67 | $-274 | $-71 | -4.4% | -1.1% |
| 2 | $6,062 | $4,149 | 0.68 | $-264 | $-56 | -4.4% | -0.9% |
| 3 | $11,912 | $7,964 | 0.67 | $-304 | $164 | -2.6% | +1.4% |
| 4 | $17,834 | $12,048 | 0.68 | $-298 | $170 | -1.7% | +1.0% |
| 5 | $23,297 | $15,498 | 0.67 | $-366 | $399 | -1.6% | +1.7% |
| 6 | $35,315 | $23,694 | 0.67 | $-364 | $515 | -1.0% | +1.5% |
| 7 | $45,693 | $31,266 | 0.68 | $-518 | $1,838 | -1.1% | +4.0% |
| 8 | $70,435 | $47,754 | 0.68 | $-484 | $2,076 | -0.7% | +2.9% |

The curve's own target is spend/income 0.65-0.70 (markets.json income_basis.target_ratio). Early legs read above it (the pure curve ask is not met by trainer money alone there: the design covers it with produce and mining, which the baseline player does).

### T11. Every loop against the yardstick (a non-fighting hour may pay at most the band's fight hour; R5's upper hour is 1.5x)

| Loop | $/h | Yardstick | Ratio | Verdict |
|---|---:|---:|---:|---|
| Gathering, early tier typical hour (opens leg 1) | $620 | $1,008 | 0.61 | ok |
| Gathering, deep tier typical hour (opens leg 3) | $1,350 | $2,492 | 0.54 | ok |
| Gathering, nether tier typical hour (opens leg 7) | $2,120 | $11,050 | 0.19 | ok |
| Gathering, Nether upper hour (bed or TNT; 30 debris), vs leg 8 | $6,120 | $17,126 | 0.36 | ok |
| AFK produce farm, the whole campaign's cap spread over its first 10 hours | $330 | $1,008 | 0.33 | ok |
| Night Shift band 1, as built, best take 24 | $48 | $1,008 | 0.05 | ok |
| Night Shift band 2, as built, best take 4 | $243 | $2,492 | 0.10 | ok |
| Night Shift band 3, as built, best take 4 | $558 | $5,358 | 0.10 | ok |
| Night Shift band 4, as built, best take 4 | $2,322 | $11,050 | 0.21 | ok |
| Night Shift band 5, as built, best take 4 | $2,860 | $12,335 | 0.23 | ok |
| Night Shift band 6, as built, best take 4 | $9,150 | $17,126 | 0.53 | ok |
| Night Shift band 4, design (clawback works) | $-100 | $11,050 | -0.01 | pays nothing / a sink |
| Night Shift band 6, design (clawback works) | $-1,458 | $17,126 | -0.09 | pays nothing / a sink |

Sinks that run on a clock: Entei with a Tower Ash every 20 minutes of uptime is -$5,400 an hour in ash alone (+ drops that no counter or bank buys).
<!-- economy_sim:tables:end -->

## Reading the tables

**Income by badge (T4).** A fighter earns the fight hour the model already prices: $996 an hour in leg 1 rising to
$17,132 in leg 8. A steady player's income per active hour is lower ($1,076 in leg 1, $12,015 in leg 8) because the
dungeon run and the gathering hour are extra hours that pay less than a fight hour; a Challenge player earns 1.45x to
2.1x a steady one per hour (the Challenge rosters, not the dungeons). The greedy runner works 9 hours a leg for $749
an hour in leg 1 and $9,011 in leg 8: dungeons are not how anyone gets rich in the campaign.

**The cost of the late game (T7).** One of every counter line off the curve is $308,240. Adding the optional services,
the late bill for a completionist is the shelf + level raises ($30,000) + EV and IV for one team ($722,400) + one boss
catch's Beast Balls ($20,000-$95,000) = **$1.08M-$1.16M**, against cumulative income of $494,853 and savings of $340,165
at the end of the HQ tower. The shelf alone is fully affordable by the end of the League (steady 91% after the League,
100% after the HQ tower, T5); the services are not, by a factor of three. That is the existing design (services are
optional and priced above the play they save); the dungeons neither close nor widen the gap except through defect 1.

**What a player can afford (T5).** Steady savings after badge 4 are $13,844, after badge 8 $74,017 (24% of the late
shelf available then, cheapest first). A Challenge player has $205,703 after badge 8 against the same shelf and the same
ask, so a Challenge player can afford 64% of it there: that is the Challenge rosters' income, unrelated to dungeons, and
worth the owner knowing.

**The greed ladder (T3, T2).** In the design a seam take is worth at most the face ($144-$318) and finishing the run
pays no money at all, so the ladder's trade is ore against items and the money-seeking choice is take 24 and turn back:
+$48, +$25, +$6 a run at bands 1-3 and a loss at bands 4-6 (the sigil costs more than the face). As built the choice
inverts at bands 2+: finishing nets $243 to $9,150 an hour, and any take past 9 blocks puts the clock past the boss, so
greed forfeits the payout ($504 a run at band 2 to $11,155 at band 6, T3 and the boss rows of T1). Defect 1 therefore
also flattens the greed trade the owner designed: from band 2 nobody takes 15 blocks when the boss is worth more than the
whole face.

**Entry costs (T2).** The sigil is $39, $62, $160, $262, $900 and $1,708 in forgone sales (9 to 72 minutes of gathering
at the bank's declared rates), 2.4% to 10% of the band's fight hour; the fee is time, as DUNGEONS.md 7.4 says.
A death costs the flat $600, and it dominates the early cost: $258 of the steady player's leg-1 dungeon spending is
deaths (at P(win a stage) 0.88), against $39 for the sigil.

## Loops

| Loop | Prints money? | Starves a player? |
|---|---|---|
| Night Shift, design | No: it is a sink from band 4 (-$100, -$644, -$1,458 an hour) | A run costs $39-$1,708 plus $600 per death; never more than 4.4% of a leg's curve income (leg 2) |
| Night Shift, as built (defect 1) | Not by threshold: 0.05-0.53 of parity. But best non-fighting hour from band 4 and the best post-Champion income | No |
| Stands built before the clawback | **Yes**: 1.03x to 16.5x parity | No |
| Gathering, all three tiers | No: 0.19-0.61 of parity, unchanged | No |
| Produce buyer and the AFK farm | No: the campaign cap is $3,600 a player, tested; the apricorn farm (550 fruit per ~17 minutes, bank.json, relayed) fills the first leg's 40 crates in about 40 minutes | No |
| Pure fighter, legs 1-2 | No | Yes, backlog in 55% and 36% of runs: the known design gap, covered by produce and mining |
| Entei (Tower Ash) | No: -$1,800 an attempt, drops unsellable | No |
| Beast Ball catches | No: a sink of $20,000-$95,000 a legendary | Not a gate: optional |

## What to do (decisions, not changes I made)

1. Keep `engine.clawback` ahead of the stands in the build order. Until it exists, the boss payout is bounded
   ($11,062-$22,125 a run at band 6, once an hour) and the stands must not be built.
2. If the clawback slips, the damage is concentrated in bands 4-6; bands 1-3 pay $212, $504 and $898 a run more than the
   design, under the cost of a death.
3. Fix the stale text: `tools/bank.py:450` and `data/bank.json` `effort_model.label` (model B), the Nether tier's
   `opens_leg` (7 against the gate's badge 8), STATE's EV/IV figure. These are the owner-file-ownership of other agents; none
   was edited here.
4. The seam cannot be the dungeon's money: do not tune the face to make runs profitable; the design wants items.

## Not verified

No payout, run, death, lockout, sigil craft or seam was observed in a game. The success rates, the time split around the
seam and the ore mix are assumed (T8 sweeps the first). The 4-19 Beast Ball throws are a relayed research figure. The
hours per leg are the model's own assumption (`effort_model.max_leg_hours`); a real leg that takes longer lowers every
hourly figure here and leaves the totals alone. The one-hour lockout is counted in uptime, and a run's wall hour is
taken as the lockout (60 minutes) whenever the run itself is shorter.
