# Income measurement: what a player actually earns, and whether the ladder's prices survive it

**Status: RESEARCH, 2026-10-01. Written at HEAD `be856747605a655a78d247e9fe01249d41612012`.**
This document answers `docs/mechanics/PROGRESSION_LADDER.md` **U-1** ("income has never
been measured — every price is evidence-free") as far as it can be answered **offline**.
It changes no `data/` file, no config and no pack, and it does not edit the ladder.

**The headline, before the detail.** The payout formula is **NOT discoverable on this
machine** — CobbleDollars' logic is in a jar that is not here. But the *authored battle
set* is fully known, and under every plausible shape of the formula the answer comes out
the same way: **the ladder costs between about 2.2x and 5.8x all the money a first-pass
player can earn.** That conclusion does not depend on which model is right, which is why
it is worth stating despite the missing formula.

---

## 0. Method, and what each claim rests on

Every claim below is marked **VERIFIED** (with `path:line`) or **ASSUMED** (with the
assumption stated in terms). Nothing here was run in a game by this agent.

**The limit, stated plainly.** `base-pack/cobbleverse/mods/` **does not exist** (VERIFIED:
`ls base-pack/cobbleverse/` returns `COBBLEVERSE - Third-Party Licenses.pdf`, `config`,
`licenses`, `resourcepacks`, `shaderpacks` and nothing else). So
`CobbleDollars-fabric-2.0.0+Beta-5.1+1.21.1.jar`
(VERIFIED: `base-pack/inventory/mod_inventory.json`, mod_id `cobbledollars`, author
Harmex, licence "All rights reserved") **cannot be read**. Earlier sessions did read it —
`experiments/EXP-040-cobbledollars-transaction/README.md:11-12` records the command tree
as "VERIFIED from the jar, `CobbleDollarsCommand`" — but no session recorded the payout
logic, and it is not in the repository anywhere. I did not invent one.

---

## 1. What a battle pays

### 1.1 The configuration, completely

Four keys, read end to end. **VERIFIED**, `base-pack/cobbleverse/config/cobbledollars/common.json:1-6`:

```json
{
  "earnCobbleDollarsFromNPC": true,
  "earnCobbleDollarsFromWildPokemon": true,
  "cobbleDollarsIncomeMultiplier": 0.5,
  "playerDataSaveFrequency": 15
}
```

`client.json` is one key (`overlayPosition`). `bank.json` and `default_shop.json` are
price lists, not income rules. **`modpack/config/cobbledollars/` does not exist and
`server/config/mods/` contains no cobbledollars file** (VERIFIED: `find modpack server
-ipath '*cobbledollar*'` returns nothing), so the base pack's four keys are the live
settings and nothing of ours overrides them.

**That is the entire discoverable surface of the income rule.** There is no per-class
rate, no level coefficient, no base-payout table, no per-species value anywhere in
`config/`. Those live in the jar.

### 1.2 The one measurement in the repository

**VERIFIED**, `docs/STATE.md:370` (and restated at
`docs/research/notes/rct-arena-capabilities.md:189`), measured on staging by the owner
2026-09-24 against a persistent upstream `kanto_brock` placed at Pallet, the owner's
party at level 25, the RCT cap at 20:

| Event | Balance before | Balance after | Paid |
| --- | ---: | ---: | ---: |
| First win over `kanto_brock` | 178 | 910 | **$732** |
| Immediate second win, same trainer | 910 | 1,510 | **$600** |

### 1.3 The formula: NOT DISCOVERABLE, and what the two numbers still prove

**I cannot state the formula.** What the data point does settle:

1. **`earnCobbleDollarsFromNPC` covers rctmod trainers.** VERIFIED by the payout itself.
2. **The payout is not a flat per-battle constant.** Two wins over the *same* trainer,
   minutes apart, paid different amounts (732, then 600). So it is a function of
   *something that varied* — or it has a random component. Both readings are open.
3. **It is not a function of the first-win reward path.** The badge and TM came from the
   loot table, separately; the money arrived both times
   (`docs/STATE.md:370`, and `data/progression.json` `upstream_neutralised.first_win_rewards.why`:
   "CobbleDollars still pays per win (`earnCobbleDollarsFromNPC`); not changed here").
4. **The order of magnitude for a gym-leader-sized battle at the level-20 cap is
   $600-$750, after the 0.5 multiplier.** That is the only hard number in this document.

**What cannot be inferred, and why.** The trainer fought was Cobbleverse's upstream
`kanto_brock`, not our `gym_01_brock`, and **no file in this repository records that
trainer's team or levels** (checked: `docs/research/notes/`, `data/`, the inventory).
Without the defeated team there is nothing to divide $732 by, so no coefficient can be
recovered from one observation. A second observation against a trainer whose team we
authored would settle it in one battle (§5, EXP-A).

### 1.4 Three candidate shapes, used as a bracket rather than an answer

Because the shape is unknown, the income table below is computed **three times**. Each is
labelled, each is **ASSUMED**, and the verdict in §4 is only quoted where all three agree.

| Model | Rule | Calibration | Why it is a plausible bracket |
| --- | --- | --- | --- |
| **A** (low) | every non-boss battle pays a flat **$150**; bosses pay $13.07 x (sum of team levels) | the flat rate is the smallest ferry fare (`data/ferries.json:672`), i.e. a deliberate "a fight is worth about one short crossing" | the floor: it assumes route trainers are near-worthless and only bosses pay |
| **B** (middle) | every battle pays **$13.07 x (sum of the defeated team's levels)** | $732 / 56, where 56 is our `gym_01_brock`'s level sum (18+18+20) used as a proxy for the Brock actually fought — **explicitly a proxy, see below** | mainline Pokemon prize money is linear in level; a per-Pokemon payout summed over the team is the most common mod shape |
| **C** (high) | every battle pays **$36.60 x (the highest level on the defeated team)** | $732 / 20, Brock's ace level | if the mod pays on the last/strongest Pokemon only, small teams are worth as much as large ones |

**The proxy is the weak link and is named as such.** Model B's and C's coefficients assume
the upstream Brock's team summed to 56 levels with a level-20 ace, because ours does
(VERIFIED: `data/trainers.json`, `gym_01_brock`, 3 members at 18/18/20). If the upstream
Brock fielded a bigger team, both coefficients are too high and every figure below is
proportionally too generous — which makes the verdict *stronger*, not weaker, since the
verdict is that income is too small.

---

## 2. Total authored income to each badge

### 2.1 The battle set, counted

**VERIFIED** from `data/trainers.json` (64 records) and `data/mansion_guardians.json`
(5 records), teams and per-member `level` read directly:

| Class | Count | Source |
| --- | ---: | --- |
| `gym_leader` | 8 | `data/trainers.json` |
| `elite_four` | 4 | `data/trainers.json` |
| `champion` | 1 | `data/trainers.json` |
| `route` | 50 | `data/trainers.json` |
| `optional_route` | 1 | `data/trainers.json` (`route_02_shore_trainer_01`) |
| mansion guardian | 5 | `data/mansion_guardians.json` |
| **total** | **69** | |

All 51 route records are **seated** (VERIFIED: `data/route_trainers.json` 13 ids for
routes 1-3, `data/late_route_trainers.json` 28 ids for routes 4-8,
`data/vr_trainers.json` 10 stands for Victory Road = 51, matching
`data/trainers.json` `generation_contract.route_trainers: 51`). The brief's "28 seated
route trainers" is `late_route_trainers.json` alone; the full seated count is 41 before
the League plus Victory Road's 10.

### 2.2 Which leg belongs to which badge

**VERIFIED**, `data/routes.json` `routes[]`: `route_01_pallet_to_brock` (order 1,
`hometown` -> `gym1_town`) through `route_08_blaine_to_giovanni` (order 8,
`gym7_town` -> `gym8_town`), then `victory_road` (order 9, `gym8_town` -> `league`). So
`route_0N` precedes gym N exactly, with no ambiguity. The mansion is on Route 1
(`data/mansion_guardians.json` note: "The five possessed Channelers of the Route 1
mansion"), so it falls before badge 1.

### 2.3 Assumptions behind the table

1. **The player fights everything once**, in order, and wins. ASSUMED (it is the brief's
   premise).
2. **Nobody is re-fought.** ASSUMED, and *supported*: the rematch hold-off now covers all
   28 seated trainers plus the eight leaders plus the League
   (`tools/route_trainers.py:338-361` `leader_cycle_lines`, keyed on `gymN_cleared`), so a
   badge-holder is refused. **NOT VERIFIED in game**, and the docstring's own interim
   caveat stands: "Cooldown is entity NBT on a shared trainer, so it cannot be held per
   player."
3. **No wild-Pokemon income**, although `earnCobbleDollarsFromWildPokemon: true`. This is
   the single biggest hole in the table and is §5's first experiment.
4. **Levels are the authored ones**, not rctmod-scaled. `relative_level_cap: 0`
   (VERIFIED: `data/trainers.json` `generation_contract`) and
   `modpack/config/rctmod-server.toml`'s `initialLevelCap 20`, so authored levels sit at
   the cap by construction.
5. **No quest, reward cache or first-win reward pays money** — see §3. VERIFIED.

### 2.4 The cumulative income table

Row N = "a player who has just earned badge N and fought every authored battle on the way".
Rows 9 and 10 are Victory Road and the League, shown for completeness.

| After | Battles in this leg | Sum of defeated levels | Leg income A | Leg income B | Leg income C | **Cumulative A** | **Cumulative B** | **Cumulative C** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| badge 1 | 10 (1 leader, 4 route, 5 mansion) | 290 | 2,082 | 3,790 | 4,685 | **2,082** | **3,790** | **4,685** |
| badge 2 | 5 (1 leader, 4 route) | 231 | 1,515 | 3,019 | 3,880 | **3,597** | **6,809** | **8,564** |
| badge 3 | 6 (1 leader, 5 route) | 356 | 2,240 | 4,653 | 5,527 | **5,837** | **11,462** | **14,091** |
| badge 4 | 7 (1 leader, 6 route) | 519 | 2,664 | 6,783 | 7,796 | **8,501** | **18,246** | **21,887** |
| badge 5 | 5 (1 leader, 4 route) | 468 | 3,149 | 6,117 | 6,478 | **11,650** | **24,362** | **28,365** |
| badge 6 | 6 (1 leader, 5 route) | 654 | 3,586 | 8,548 | 8,930 | **15,236** | **32,910** | **37,295** |
| badge 7 | 7 (1 leader, 6 route) | 819 | 4,063 | 10,704 | 11,602 | **19,299** | **43,615** | **48,898** |
| badge 8 | 8 (1 leader, 7 route) | 1,103 | 5,219 | 14,416 | 14,603 | **24,518** | **58,031** | **63,501** |
| Victory Road | 10 route | 1,274 | 1,500 | 16,651 | 21,338 | 26,018 | 74,682 | 84,839 |
| the League | 5 (E4 + Champion) | 1,764 | 23,055 | 23,055 | 11,053 | 49,074 | 97,737 | 95,892 |

**Read this as a band, not a number.** The defensible statement is: **a first-pass player
arrives at badge 8 with somewhere between about $25,000 and $64,000 gross, having earned
between about $2,000 and $4,700 by badge 1.** The three models disagree by 2.6x at badge 1
and by only 1.3x from badge 4 on, because by then team sizes have converged.

### 2.5 What has to come out of that gross

Two mandatory sinks, both VERIFIED, neither modelled in §2.4:

- **Mart basics.** Every Mart sells exactly three items — `poke_ball` 200, `potion` 200,
  `antidote` 100 (VERIFIED: `data/traders.json:561-569` `stock_policy.mart`, and confirmed
  against a *running* game at `docs/STATE.md:327-329`: "our clerk's live shop is exactly
  three categories -- Pokeballs (`poke_ball`, 200), Treatments (`potion`, 200), Remedies
  (`antidote`, 100)"). A frugal **5 balls + 3 potions per leg** is $1,600 a leg
  (ASSUMED allowance), which is **42% of model-B income by badge 1** and 22% by badge 8.
  Catching at all is expensive early: one Poke Ball is 5% of everything earned in the
  mansion-and-Route-1 leg.
- **Blackout.** SUPERSEDED 2026-10-01 by decision B10: now a flat $600 per blackout (20% of a $3,000 cap, never more than the balance; data/blackout.json, the owner's decision B10, 2026-10-01). It was 20% of the whole balance per incident, rounded up
  (VERIFIED: `data/blackout.json:6-10`, `percent: 20`, "rounding: up; a balance above zero
  always loses at least 1 (`ceil(balance * percent / 100)`)"; raised from 10 by the owner
  2026-09-27). This is a *proportional* sink, so it does not scale with the ladder: three
  blackouts in a leg cost roughly half of everything saved, whatever the ladder costs. **A
  20% balance tax is incompatible with saving up for a 20,000 purchase**, and that
  interaction is the most under-appreciated finding in this document (§4.3).
- **Ferries**, where one is the only way in: $150 the Sound crossing and the Pacifidlog
  line, $100, $400 "the one really long crossing", $600 x4 for postgame charters, two
  lines free (VERIFIED: `data/ferries.json:560,577,631,672,724,749,818,871,904,937`). A
  round trip at a gated town is $200-$1,200. `data/ferries.json:578` already calibrates
  against the same single data point: "For scale, Brock's first win paid $732 and a
  blackout takes 20%".

---

## 3. The other taps, each checked

| Tap | Pays money? | Evidence |
| --- | --- | --- |
| **`data/rewards.json`** — 11 finds (5 in Victory Road's caverns, 6 off Routes 1 and 3) | **No. Items only, no currency in any record.** | VERIFIED: all 11 `contents[]` arrays read; they hold stones, balls, potions, berries, a TM, `mega_showdown:dragonium_z`, `obc:bottle_cap_gold`, `cobblemon:old_amber_fossil`, `big_root`, `hard_stone`, `everstone` |
| **`data/progression.json` `first_win_rewards`** — the 8 leaders + Champion | **No. Items only.** Each is a badge (plus Brock's badge box, Giovanni's `lumymon:ancient_dna` and `cobblemon:master_ball`, Blue's trophy and `ancient_origin_ball`) and one TM from a weighted `one_of` | VERIFIED: `data/progression.json` `upstream_neutralised.first_win_rewards.trainers`, nine entries read in full |
| **`data/quests.json`** | **No quest pays CobbleDollars.** | VERIFIED: `grep -n "cobbledollar\|CobbleDollar\|currency\|dollars" data/quests.json` returns **no match** |
| **Gold bottle caps** | **The campaign owns the entire supply, and the supply is ONE.** Exactly one `obc:bottle_cap_gold` exists in all authored data: `vr_abandoned_cut`'s npc_grant | VERIFIED: `grep -rn "bottle_cap" data/*.json` returns exactly two hits, `data/rewards.json:191` and `data/quests.json:2002`, and they are the **same grant** (the reward record and the quest that delivers it) |
| **Selling to the bank** | Yes, and this is the uncapped tap nobody has priced. 82 sell entries: emerald 400, emerald_block 3,750, elytra 25,000, relic_coin 50 / pouch 475 / sack 4,500, four lumymon feathers at 5,000 and one at 30,000, vitamins 2,500 each | VERIFIED: `base-pack/cobbleverse/config/cobbledollars/bank.json:1-323` |
| **Wild Pokemon** | `earnCobbleDollarsFromWildPokemon: true`, **rate unknown** | VERIFIED (the key), UNMEASURED (the rate) |
| **The Assayer / stone Exchange** | A pure sink: sells all ten stones at 2,100, never buys | VERIFIED: `data/traders.json:584-589`; "No stone is in CobbleDollars' `bank.json`, so nothing else buys one back" |
| **The casino** | Nothing. Proposal only, no building, no template | VERIFIED: `docs/research/CASINO.md:297` "No Game Corner template exists" |

**The finding here is a negative, and it matters: the campaign has exactly one money tap —
winning battles.** Not one authored reward, quest or first-win grant pays a single dollar.
Every price in the ladder is therefore paid out of §2.4's table and nothing else, except
whatever a player scavenges into `bank.json`.

**And the one uncapped leak: `minecraft:emerald_block` sells for 3,750.** Nine emeralds is
a model-B gym leader's purse. `minecraft:elytra` sells for 25,000 — more than a first-pass
player earns in eight badges under model A. These are upstream defaults nobody has
reviewed against a campaign, and they are world-reachable (vanilla trading, End cities
through whatever portals exist). ASSUMED unreachable in our bordered world; **not checked**.

---

## 4. The verdict the ladder needs

### 4.1 Cumulative spend against cumulative income

Ladder prices transcribed from `docs/mechanics/PROGRESSION_LADDER.md` §1.1 (critical path)
and §1.2 (off-path). `cum spend` is the critical path only, assuming the player buys every
rung offered at the badge that unlocks it.

| After | This town's rungs | cum spend | cum income A | cum income B | cum income C | spend/A | spend/B | spend/C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| badge 0 (Pallet) | 550 | 550 | 0 | 0 | 0 | inf | inf | inf |
| **badge 1 (Brock)** | **13,000** | 13,550 | 2,082 | 3,790 | 4,685 | **6.5x** | **3.6x** | **2.9x** |
| badge 2 (Misty) | 5,700 | 19,250 | 3,597 | 6,809 | 8,564 | 5.4x | 2.8x | 2.2x |
| badge 3 (Surge) | 12,500 | 31,750 | 5,837 | 11,462 | 14,091 | 5.4x | 2.8x | 2.3x |
| badge 4 (Erika) | 7,900 | 39,650 | 8,501 | 18,246 | 21,887 | 4.7x | 2.2x | 1.8x |
| badge 5 (Koga) | 16,700 | 56,350 | 11,650 | 24,362 | 28,365 | 4.8x | 2.3x | 2.0x |
| badge 6 (Sabrina) | 17,500 | 73,850 | 15,236 | 32,910 | 37,295 | 4.8x | 2.2x | 2.0x |
| badge 7 (Blaine) | 24,000 | 97,850 | 19,299 | 43,615 | 48,898 | 5.1x | 2.2x | 2.0x |
| **badge 8 (Giovanni)** | **45,000** | **142,850** | 24,518 | 58,031 | 63,501 | **5.8x** | **2.5x** | **2.2x** |

Off-path gated shelves add 15,800 (mining town, at `gym3_cleared`), 5,100 (sunset_west
gated scrolls, `gym5_cleared`) and 3,800 (northlight, `gym6_cleared`), plus 5,100 of
ungated sunset_west scrolls: **the full ladder as proposed is $172,650.** Against model B's
$58,031 at badge 8 that is **3.0x**; against model A, **7.0x**.

**Pallet's row is the only "impossible" in the strict sense.** $550 is asked at badge 0,
when authored income is exactly **zero** — there is no battle before Pallet. The player
either has starting money (not configured anywhere I can find; `common.json` has no
starting-balance key) or cannot buy either item. **This is a hard blocker, not a
calibration question.**

### 4.2 Every rung mispriced by more than about 2x

Judged as **"can a player who bought the previous rungs afford this one"**, under model B
(the middle bracket). Direction is always *too expensive* — not one rung in the ladder is
too cheap.

| Rung | Price | Verdict | By how much | Why |
| --- | ---: | --- | --- | --- |
| **Pallet `backpack` + `sleeping_bag`** | 300 + 250 | **IMPOSSIBLE** | infinite | income at badge 0 is $0 and no starting balance is configured |
| **Brock `crafting_upgrade`** | **7,500** | **IMPOSSIBLE** | **2.0x all income ever earned**, and 7.7x under model A | the single worst-priced item in the document. It alone costs double everything a player has earned by badge 1 |
| **Brock's shelf as a whole** | 13,000 | **IMPOSSIBLE** | 3.4x income at badge 1 | even without the crafting upgrade the remaining 5,500 is 1.45x |
| **Giovanni `diamond_backpack`** | **20,000** | **IMPOSSIBLE after the earlier rungs** | 0.34x of badge-8 gross, but cum spend is already 97,850 against 43,615 earned | affordable only to a player who bought nothing for eight badges — which defeats the ladder's own premise |
| **Giovanni `obc` gold cap** | 15,000 | **IMPOSSIBLE in the same sense** | as above | and it is the *only* repeatable gold-cap source if sold, which makes its price the whole hyper-training economy |
| **Giovanni `inception_upgrade`** | 10,000 | **IMPOSSIBLE in the same sense** | as above | Giovanni's shelf is 45,000 at a badge where 14,416 was earned in the leg: **3.1x one leg's income** |
| **Blaine's shelf** | 24,000 | over-priced ~2.2x | 2.2x one leg's 10,704 | `gold_backpack` at 12,000 is 1.1x the whole leg |
| **Sabrina's shelf** | 17,500 | over-priced ~2.0x | 2.0x the leg's 8,548 | the three stack tiers (2,000/4,000/8,000) are 1.6x the leg on their own |
| **Koga's shelf** | 16,700 | over-priced ~2.7x | 2.7x the leg's 6,117 | `mega_bracelet` at 9,000 is 1.5x the leg by itself |
| **mining town (off-path, `gym3_cleared`)** | 15,800 | **IMPOSSIBLE** | 1.4x *total* income to badge 3 (11,462), on top of 31,750 already asked | the largest single off-path shelf, offered at the poorest point on the curve |
| **Surge `iron_backpack`** | 6,000 | borderline (0.52x of total income to date) | ~1.5x if Brock's and Misty's shelves were bought | the ladder's own declared pivot; a player who followed the ladder cannot reach it |

**Rungs that are correctly priced or near enough** (within about 2x, taking a leg's income
as the budget): Misty's whole shelf (5,700 against 3,019 earned in the leg — 1.9x, the
closest call in the ladder), Erika's `malasada`/`pokepuff` at 900/500 (genuinely trivial,
3-5% of income to date — correct for a restock), Erika's `feeding_upgrade` at 2,000,
northlight's 800 hammocks, and sunset_west's 400 blank scroll.

**Nothing in the ladder is priced too low.** The one rung I would call *trivial* for its
position is Erika's CobbleCuisine consumables, and §1.2 already calls that "a restock, not
a rung", so it is right.

### 4.3 The structural findings, which matter more than any single price

1. **The ladder is uniformly about 2.2x-5.8x too expensive, and the error is remarkably
   flat from badge 2 onwards (2.2x-2.8x under model B).** That is the signature of a
   *scale* error, not a shape error: the price column was written in units about 2.5x too
   large, and the relative ordering of rungs is fine. **The cheapest correct fix is to
   divide every price by about 2.5 and leave the ladder's shape alone.** The alternative —
   raising income 2.5x — means lifting `cobbleDollarsIncomeMultiplier` from 0.5 to about
   1.25, which is one key in one file (and would also multiply every bank-sale leak).
2. **Badge 1 is the worst rung and badge 0 is impossible.** The curve's error is not flat
   at the start: 6.5x/3.6x/2.9x at badge 1 against ~2.2x later. Early income is small
   because early teams are small (290 levels across 10 battles), and the mansion's five
   guardians at levels 8-16 are nearly worthless under every model. Any repricing must
   treat badge 0 and badge 1 separately.
3. **A 20% balance tax and a 20,000 purchase cannot coexist.** `data/blackout.json`'s
   20%-of-balance charge means the *expected* cost of saving is proportional to how long
   you save, so the ladder's expensive late rungs are not just unaffordable, they are
   *un-saveable-for* in a campaign designed to be difficult. Either the big-ticket rungs
   come down, or the blackout charge needs a cap, or the two systems need to be reconciled
   deliberately. **This is a cross-system contract, not a price.**
4. **Mart basics are a bigger share of early income than any ladder rung.** $1,600 a leg
   of balls and potions is 42% of model-B income by badge 1. The ladder competes with
   catching Pokemon for the same dollars, and catching wins.
5. **Income scales with authored level sum, so it is already paced correctly** — leg income
   rises from 3,790 to 14,416 under model B, a 3.8x rise across eight badges, while the
   ladder's per-badge ask rises from 13,000 to 45,000, a 3.5x rise. **The slopes match
   almost exactly.** The ladder's problem is its intercept, not its gradient. That is a
   genuinely encouraging result for the design.

---

## 5. What cannot be known offline

Each of these is an experiment candidate with the exact command. None was run by this agent.
The command tree is VERIFIED from the jar at
`experiments/EXP-040-cobbledollars-transaction/README.md:11-12`: `/cobbledollars` (alias
`/cd`) with `query`, `give`/`add`, `remove`/`subtract`, `set`, `pay`, `leaderboard`, and
`cobbledollars query <player>` returns the balance as a command result
(`:14`: `execute store result storage cobblers:exp cd_balance int 1 run cobbledollars query <player>` stored **712**).

### EXP-A — the formula, settled in three battles (highest value)

Fight **our own** trainers, whose teams are authored, and divide.

```
# before each battle
cobbledollars query @s
# then fight, then
cobbledollars query @s
```

Fight, in this order: `route_01_trainer_01` (1 Pokemon, level 7), `route_01_trainer_04`
(3 Pokemon, sum 48) and `gym_01_brock` (3 Pokemon, sum 56, ace 20). Three payouts against
three known (count, sum, max) triples distinguish models A, B and C outright, and the
first two have no reward noise. **This is the whole of U-1 for trainers and costs about
ten minutes.**

### EXP-B — the random component

Refight one trainer five times with the hold-off suppressed, and record five payouts. If
they differ with the team fixed, the payout has a roll and every figure above is a mean,
not a value. Use a throwaway seated trainer, not a leader (the leader hold-off is keyed on
`gymN_cleared` and suppressing it would mean editing a pack).

### EXP-C — wild-battle income, the biggest hole

```
cobbledollars query @s
# defeat (do not catch) 10 wild Pokemon of recorded levels, in one spawn band
cobbledollars query @s
```

Run it twice, once in a level-10 band and once in a level-45 band, and record the levels
defeated. This is the only tap that could invalidate §4: if wild battles pay anything
like per-level parity with trainers, a player who grinds has unbounded income and the
ladder's prices only gate the *first pass*. **Until this is measured, every verdict in §4
is conditional on a player who does not grind.**

### EXP-D — selling drops, and whether the bank is a leak

Sell one emerald block (3,750) and one relic coin sack (4,500) and confirm the prices in
`bank.json` are live, then check whether either is reachable in our world at all (villager
trading, loot). If an emerald block is farmable, income is effectively unbounded and §4's
verdict is about the *intended* economy only.

### EXP-E — rematch economics, in game

Beat a leader, then approach again as the badge-holder and confirm the hold-off refuses
(`tools/route_trainers.py:338-361`). Then do the same with a **second player who has no
badge standing beside the holder** — the docstring's own open caveat: "Cooldown is entity
NBT on a shared trainer, so it cannot be held per player." If a partner can start the
fight, the holder is dragged into a paying rematch and leader farming is open again.

### EXP-F — the starting balance

`cobbledollars query @s` on a brand-new player, before any battle. §4.1's only hard
blocker (Pallet asks $550 against $0 authored income) dissolves if CobbleDollars starts a
player with money, and no config key in the pack sets one. **One command, and it decides
whether row 0 of the ladder is impossible or fine.**

---

## 6. Summary of what this document settles and what it does not

| U-1's question | Answer |
| --- | --- |
| The formula | **NOT discoverable offline.** The jar is absent; no config key encodes it; one observation cannot be decomposed because the team fought is unrecorded. EXP-A settles it in three battles. |
| Income per battle, order of magnitude | **$600-$750 for a gym-leader-sized battle at the level-20 cap**, VERIFIED once. |
| Total income to badge 8 | **$25,000-$64,000** gross, first pass, everything fought once, under three stated models. |
| Are the ladder's prices right? | **No — uniformly about 2.2x to 5.8x too high**, flat from badge 2 on, worst at badge 1, and **impossible at badge 0**. |
| The cheapest fix | Divide the price column by ~2.5 (data-side), or raise `cobbleDollarsIncomeMultiplier` from 0.5 to ~1.25 (one config key, but it multiplies the bank-sale leak too). **The owner's call; this document does not make it.** |
| The thing nobody has priced | **Wild-Pokemon income** (`earnCobbleDollarsFromWildPokemon: true`, rate unknown) and `bank.json`'s 82 sell prices. Either could make income unbounded. |
