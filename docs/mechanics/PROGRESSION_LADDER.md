# The progression ladder: what each town sells, and what each badge buys

**Status: PROPOSED, revision 2 (2026-10-01). Nothing here is built.** Revision 1 was
written before income was measured; this revision folds in four owner decisions and
re-derives every price against the income they produce. No `data/` file, config or pack is
touched by this document.

**The four decisions, verbatim (the owner, 2026-10-01):**

- **B8 + B9** — *"raise the income multiplier to 1.25, then re-price. That fixes the scale
  factor with one key, and the card's $500 stops being impossible."*
- **B7** — *"move crafting to Brock's, priced out of reach. Price as the gate is elegant."*
- **B6** — *"two strands per counter."*
- **B10** (settled elsewhere, assumed here) — the blackout charge becomes a flat percentage
  of a **cap**, not of balance, so saving is no longer punished.

**The owner's goal, verbatim:** *"I want a player to advance materially as they travel, so
they never need to build a house — they live out of a backpack that gets better. Town
markets are where that happens."* And: *"It should feel like the region, not a shop list —
a mining town sells what a mining town would."*

## What this rests on

| Source | What it settles |
| --- | --- |
| `docs/research/INCOME_MEASUREMENT.md` | the income band, three models, the one in-game data point ($732/$600 over `kanto_brock`), and the verdict revision 1 was 2.2x-5.8x too expensive |
| `docs/research/PROGRESSION_UNLOCKABLES.md` | the mod audit: six backpack tiers, 56 upgrades, crafting-only supply, what is and is not gateable |
| `docs/mechanics/MARKET_GATING.md` | the mechanism: per-player **dialogue option visibility** on a `cobblers:flag/<id>` probe, paid with the ferry's checked CobbleDollars sequence |
| `data/towns.json`, `docs/world-building/TOWN_CHARACTER.md` | each place's purpose and dressing — the ladder follows these, it does not invent |
| `data/progression.json` | the flags that exist: `gym1_cleared`…`gym8_cleared`, `champion_cleared`, `chapter_1`…`chapter_8`, `league`, `postgame` |
| `data/traders.json` | 26 trader records, 14 Mart clerks, the Assayer, and `stock_policy` (interim, waiting for exactly this document) |
| `base-pack/cobbleverse/config/cobbledollars/bank.json` | 82 sell-back prices — the floor under every shop price (§6.4) |

**Procedural notes, recorded because they are findings.**

1. This agent has no shell, so the briefed `git rev-parse HEAD` could not be run and
   neither could `git reset --hard c4c9b5b`. The agent worktree
   (`.claude/worktrees/agent-a4f9c9d6059e31df8`) **does not contain**
   `docs/mechanics/PROGRESSION_LADDER.md`, `docs/research/INCOME_MEASUREMENT.md`,
   `docs/research/PROGRESSION_UNLOCKABLES.md` or `docs/mechanics/MARKET_GATING.md`: none of
   them exists at the committed HEAD this worktree was cut from. All four were read from the
   session worktree at
   `C:\Users\wnd\Documents\github\cobblers\.claude\worktrees\cobblers-cobblemon-session-start-531d15`.
   This file is therefore written **fresh** in the agent worktree rather than edited in
   place; the main session must take it as a whole-file replacement.
2. **`data/traders.json` needs no change for B7.** `grep crafting_upgrade data/traders.json`
   returns **no match** in either worktree: the file carries trader records and
   `stock_policy` only, and no ladder price of any kind. There is nothing to re-price, so the
   data is left to an implementer and §4 states the figure instead.

---

## 0. The arithmetic the decisions produce

### 0.1 The one key

`base-pack/cobbleverse/config/cobbledollars/common.json:4` —
`"cobbleDollarsIncomeMultiplier": 0.5` — becomes **1.25**, in a new
`modpack/config/cobbledollars/common.json` overlay (the base pack is never edited; the
directory does not exist yet, VERIFIED `INCOME_MEASUREMENT.md` §1.1). **Rung 4
(configuration)**, one key, one file, no restart beyond the next boot.

**Every measured income figure multiplies by 2.5.** That is exactly the factor
`INCOME_MEASUREMENT.md` §4.3.5 identified as the error: *"leg income rises 3.8x across
eight badges and the ladder's per-badge ask rises 3.5x; the slopes match almost exactly.
The ladder's problem is its intercept, not its gradient."* Raising income fixes the
intercept and leaves the gradient alone.

**So the price column is now close to right as it stands, and must not be divided again.**
Dividing by 2.5 *and* raising the multiplier would correct the same error twice and leave
the ladder 2.5x too cheap.

### 0.2 Income after the change (model B, the middle bracket)

`INCOME_MEASUREMENT.md` §2.4 x 2.5. Model B = $13.07 per level of the defeated team,
calibrated on the one measured battle. A and C are carried as the band.

| After | Leg income B | **Cum. income A** | **Cum. income B** | **Cum. income C** |
| --- | ---: | ---: | ---: | ---: |
| badge 1 | 9,475 | 5,205 | **9,475** | 11,713 |
| badge 2 | 7,548 | 8,993 | **17,023** | 21,410 |
| badge 3 | 11,633 | 14,593 | **28,655** | 35,228 |
| badge 4 | 16,958 | 21,253 | **45,615** | 54,718 |
| badge 5 | 15,293 | 29,125 | **60,905** | 70,913 |
| badge 6 | 21,370 | 38,090 | **82,275** | 93,238 |
| badge 7 | 26,760 | 48,248 | **109,038** | 122,245 |
| badge 8 | 36,040 | 61,295 | **145,078** | 158,753 |
| Victory Road | 41,628 | 65,045 | 186,705 | 212,098 |
| the League | 57,638 | 122,685 | 244,343 | 239,730 |

Badge 0 income is still **exactly zero** under all three models (no authored battle precedes
Pallet), which is why the trainer card is §5.1's conditional and not a price.

### 0.3 Revision 1's ladder against the new income

Revision 1's cumulative critical-path ask was **$142,850**, and **$172,650** including the
off-path shelves (`INCOME_MEASUREMENT.md` §4.1). Against model B's new $145,078 at badge 8:

| After | Rev-1 cum. ask | Cum. income B (new) | ask / income |
| --- | ---: | ---: | ---: |
| badge 1 | 13,550 | 9,475 | **1.43x** |
| badge 2 | 19,250 | 17,023 | 1.13x |
| badge 3 | 31,750 | 28,655 | 1.11x |
| badge 4 | 39,650 | 45,615 | 0.87x |
| badge 5 | 56,350 | 60,905 | 0.93x |
| badge 6 | 73,850 | 82,275 | 0.90x |
| badge 7 | 97,850 | 109,038 | 0.90x |
| badge 8 | 142,850 | 145,078 | 0.98x |

**The multiplier did most of the job.** Ratios of 5.8x became 0.98x. But 0.98x means *the
ladder consumes every dollar a first-pass player ever earns*, leaving nothing for the two
sinks §2 of the measurement proved are mandatory — Mart basics ($1,600 a leg assumed, 17%
of leg 1 and 4% of leg 8) and ferries ($100-$600 a crossing) — nor for the Assayer's
$2,100 stones, nor for a blackout. **A ladder that is exactly affordable is unaffordable.**

So the calibration target for this revision is explicit:

> **A town's whole shelf costs at most about 70% of that leg's income, and cumulative
> spend stays near 0.65-0.70 of cumulative income at every badge.** The remaining
> 30-35% is the Mart, the ferry, the stones and the blackout.

That target, not a blanket divide, is what sets §1's prices.

### 0.4 What I assume about the blackout (B10)

**ASSUMED, pending the number B10 settles.** I assume the charge is a **flat percentage of
a cap**, therefore (a) **bounded**, (b) **independent of balance** and (c) **predictable**;
and for budgeting I assume the bound is no more than about one leg's Mart restock
(~$1,500-$2,000 at mid-game) and at most one incident a leg.

**This is what makes the back half of the ladder legal at all.** Under the old 20%-of-balance
rule (`data/blackout.json:6-10`, VERIFIED) the *expected* cost of saving rose with how long
you saved, so `INCOME_MEASUREMENT.md` §4.3.3 was right that *"a 20% balance tax and a
20,000 purchase cannot coexist"*. A bounded charge makes saving for the Mega bracelet or the
diamond backpack a plan rather than a leak. **If B10 lands on a cap high enough that a
mid-game loss still exceeds a leg's income, §1's three big-ticket rungs must come down
again** — that dependency is Q-2.

I do not touch `data/blackout.json`.

### 0.5 The side effect nobody has priced, and it is the new top unknown

`cobbleDollarsIncomeMultiplier` is named *income*. **Whether a sale to the bank counts as
income is UNKNOWN.** If it does, `bank.json`'s 82 sell prices all rise 2.5x with the key:
`minecraft:emerald_block` 3,750 → **9,375**, `minecraft:elytra` 25,000 → **62,500**,
`lumymon` feather 30,000 → **75,000**. That would turn a reviewed leak into an unbounded
one and would invalidate every price below.

If it does *not*, the opposite happens and is benign: every fixed price in the campaign
becomes 2.5x cheaper in real terms — the Mart restock falls from 42% of badge-1 income to
17%, a ferry from 8% to 3%, an Assayer stone from a fifth of a leg to a twelfth. §6.3
records the consequences for files this document does not own.

**One sale, before and after the key change, settles it (U-1).** It must be run before the
multiplier ships.

---

## 1. The ladder, town by town — two strands per counter

**B6: every counter offers a convenience strand and a power strand.** The reasoning
revision 1 argued and the measurement confirmed: the convenience arc *finishes at badge 3
of 8* (iron's 81 slots and 7 upgrade slots are a complete "no house" loadout, §2), so the
power strand is what carries badges 4-8, and a player who does not care about backpacks
still has something to buy at every stop.

**How to read it.** `Flag` exists in `data/progression.json` today unless marked
**(request)**. Prices are **proposals with reasoning**; each is marked **keep** (revision 1's
figure survives the new income) or **was N** (re-priced here). Power-strand items priced
per item, because nobody buys a shelf whole. ASSUMED labels are in §6.

### 1.1 The critical path

| # | Town | Convenience strand | Power strand | Flag | Shelf | % of leg |
| ---: | --- | --- | --- | --- | ---: | ---: |
| 0 | **Pallet** (`hometown`) | `sophisticatedbackpacks:backpack` **300 keep**; `comforts:sleeping_bag` **250 keep** | `rctmod:trainer_card` **500, conditional — see §5.1** | none | 550 | n/a |
| 1 | **Brock** (`gym1_town`) | `stonecutter_upgrade` **1,800 keep**; `anvil_upgrade` **2,500 keep**; `copper_backpack` **1,200 keep** | TMCraft blank, grade 1, **500 each** (4 forms); **`crafting_upgrade` 7,500 keep — the priced gate, §4** | `gym1_cleared` | 5,500 | **58%** |
| 2 | **Misty** (`gym2_town`) | `tank_upgrade` **1,500 keep**; `filter_upgrade` **1,200 keep**; `advanced_filter_upgrade` **2,500** (was 3,000) | released Treatments, item by item: a hyper-potion tier **~900**, full restore **~1,800** (§1.4) | `gym2_cleared` | 5,200 | **69%** |
| 3 | **Surge** (`gym3_town`) | **`iron_backpack` 4,500** (was 6,000); `battery_upgrade` **2,000** (was 2,500); `xp_pump_upgrade` **2,000** (was 4,000) | TMCraft blank, grade 2, **900 each** | `gym3_cleared` | 8,500 | **73%** |
| 4 | **Erika** (`gym4_town`) | `feeding_upgrade` **2,000 keep**; `advanced_feeding_upgrade` **4,500 keep** | CobbleCuisine `malasada` **900 keep** / `pokepuff` **500 keep** (the friendship ladder, `beanFriendship 1` / `pokepuffFriendship 6` / `malasadaFriendship 12`); released Remedies | `gym4_cleared` | 6,500 | **38%** |
| 5 | **Koga** (`gym5_town`) | `pickup_upgrade` **1,500 keep**; `advanced_magnet_upgrade` **3,000** (was 4,000); `smoking_upgrade` **2,000** (was 2,200) | **`mega_showdown:mega_bracelet` 7,500** (was 9,000); released Boosts (X items) | `gym5_cleared` | 14,000 | **92%** |
| 6 | **Sabrina** (`gym6_town`) | `smithing_upgrade` **3,000** (was 3,500); `stack_upgrade` starter / t1 / t2 **2,000 keep / 3,500** (was 4,000) **/ 6,000** (was 8,000) | TMCraft blank, grade 3, **1,400 each** | `gym6_cleared` | 14,500 | **68%** |
| 7 | **Blaine** (`gym7_town`) | furnace group, **pick one** (`furnace_upgrades|1`): `smelting` **2,800 keep** / `auto_smelting` **4,500** (was 6,000) / `blasting` **2,500** (was 3,200); `gold_backpack` **8,000** (was 12,000) | TMCraft blank, grade 4, **2,000 each** | `gym7_cleared` | 17,800 | **67%** (12,500 effective) |
| 8 | **Giovanni** (`gym8_town`) | `inception_upgrade` **7,000** (was 10,000); `diamond_backpack` **10,000** (was 20,000) | **`obc:bottle_cap_gold` 6,000** (was 15,000) — §1.4; TMCraft blank, grade 5, **2,800 each** | `gym8_cleared` | 25,800 | **72%** |
| 9 | **League** | **nothing. The League sells nothing.** | — | — | — | — |

Row 9 unchanged from revision 1 and said rather than padded: the League has no
`data/traders.json` record and `TOWN_CHARACTER.md` keeps it undressed by design.
`netherite_backpack` is +12 slots and +1 upgrade slot over diamond — propose it as
`champion_cleared`'s **reward item** in ADR-002's shape, not a sale (Q-5). TMCraft grade 6,
if the grades mean what U-4 assumes, is the same: a reward, not a shelf.

**Why each town sells what it sells (the identity claim, one line each).**

- **Pallet** is the one town that *is* a house. The last thing home gives you is the means
  never to come back. Its power strand is the licence itself.
- **Brock's** is the plateau's builders' town: its dressing already holds a stonecutter, a
  grindstone and an anvil bench (`TOWN_CHARACTER.md`). A masons' town sells workstations —
  and **cuts blanks**, which is why the TM arc starts here.
- **Misty's** lake town takes in whoever the water brings and keeps a ledger of every
  arrival: a rescue crew sells water carried (tanks, filters) and **medicine**.
- **Surge's** signal town keeps the power and the relays running. The only trade in the
  region that would plausibly sell a battery, and the only one that would sell the blank
  grade above Brock's.
- **Erika's** garden town sells food — and the feeding upgrade *is* food that follows you,
  while the friendship ladder is food that changes a Pokémon.
- **Koga's** fen-edge watch town traps and tracks. Pickup and magnet *are* trapping; the
  smoke racks are in the dressing; and the bracelet is here because badge 5 of 8 leaves
  three gyms to use Mega Evolution on.
- **Sabrina's** is the region's place of study, recording what the Rift does to memory:
  a town of record-keepers sells **compression**, and `maxUpgradesPerStorage` caps stack
  upgrades at 3 so the shelf has a natural end.
- **Blaine's** research town sits on the crater rim. A town on a volcano sells **heat**, and
  nowhere else should.
- **Giovanni's** southern garrison is the last gate before Victory Road, and **the
  quartermaster's stall is already built and already faces that road.** A quartermaster's
  answer to "I have too much" is packs inside packs; the caps are here because
  hyper-training a level-55 team at the last gate is the correct moment for them.

### 1.2 Off the path

| Town | Convenience strand | Power strand | Flag | Shelf |
| --- | --- | --- | --- | ---: |
| **`mining_town`** | `compacting` **2,000** (was 3,000); `advanced_compacting` **3,500** (was 7,000); `void` **1,200** (was 1,800); `advanced_void` **2,500** (was 4,000) | **the Assayer's ten stones at 2,100, untouched** — already authored, already the region's clearing house | `gym3_cleared` (reachability U-5) | **9,200** (was 15,800) |
| **`sunset_west`** | `waystones:blank_scroll` **400 keep**, `return_scroll` **1,200 keep** (ungated); `warp_scroll` **3,500 keep**, `bound_scroll` **2,600 keep**; iron/gold shulker boxes **2,500 keep** | released Pokéballs: great **750**, ultra **1,000** (`defaultShop`'s own prices) — a port sells the balls that work on water | none; then `gym5_cleared` | 1,600 + 8,600 |
| **`northlight`** | `comforts` hammocks **800 keep** (16 colours). **The "field bedroll" is dropped** — `sleepingBagEffects` is server-wide, so it cannot differ from Pallet's (U-6) | vitamins **3,500 each** — a research station sells supplements. **Priced above `bank.json`'s 2,500 sell-back on purpose, §6.4** | `gym6_cleared` | 800 + 3,500 |
| **`tea_town`** | CobbleCuisine consumables at a discount, **500/900 less a margin, keep** | the same discount *is* the power strand: the cheapest route in the region to a friendship evolution | none | restock |
| **`sea_town`** | ferry fares, **already built** (`tools/ferries.py:220-239`) | dive and special balls, fishing gear | existing ferry flags | existing |
| `displaced_city`, `merian_hut`, `gorge_hamlet`, `tableland_stop`, `rift_rim_stop`, `relic_island`, `the_scar`, `viltri_light`, `rift_dig_camp`, `jungle_ruins`, `frostpeak_shrine` | **nothing, and most should never have a market.** None has a `data/traders.json` record; the Scar and the jungle ruins are "dark and unkept by design"; the rim post is a ranger station, a Centre not a shop; Merian's hut is a bed at the end of a walk. **The one I would reconsider:** `tableland_stop`'s prospector has sample piles, a sieve and ore crates — the only off-path stop with the identity for a second mining counter (Q-4). | | — | — |

### 1.3 The re-derived cumulative check

Shelf totals from §1.1, cumulative, against §0.2's model B. `crafting_upgrade` (7,500) is
shown separately because B7 makes it a *stretch* purchase, not part of a badge's shelf.

| After | Cum. shelf ask | Cum. income B | ratio | with crafting bought | ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| badge 0 | 550 | 0 | — | — | — |
| badge 1 | 6,050 | 9,475 | **0.64x** | — | — |
| badge 2 | 11,250 | 17,023 | **0.66x** | — | — |
| badge 3 | 19,750 | 28,655 | **0.69x** | 27,250 | 0.95x |
| badge 4 | 27,650 | 45,615 | **0.61x** | 35,150 | 0.77x |
| badge 5 | 41,650 | 60,905 | **0.68x** | 49,150 | 0.81x |
| badge 6 | 56,150 | 82,275 | **0.68x** | 63,650 | 0.77x |
| badge 7 | 73,950 | 109,038 | **0.68x** | 81,450 | 0.75x |
| badge 8 | 99,750 | 145,078 | **0.69x** | 107,250 | 0.74x |

**Flat at 0.61-0.69 across the whole campaign**, which is the result the design wants: a
third of income is left over at every badge for the Mart, the ferries, the stones and a
bounded blackout, and the shape of revision 1 is untouched. Full ladder including the
off-path shelves and crafting: **about $129,350** (was $172,650), against model B's
$145,078 at badge 8 and $244,343 after the League.

Under **model A** (the floor — route trainers nearly worthless) the ladder is still 1.6x
income at badge 8 ($61,295), and under **model C** it is 0.63x. **The band is the honest
answer and EXP-A closes it in three battles** (U-2).

### 1.4 The rungs still mispriced after the multiplier, and by how much

This is the answer to the brief's question. Judged against §0.3's target, these are the
rungs revision 1 still had wrong *after* income rose 2.5x, with the cut taken:

| Rung | Rev-1 | Now | Over by | Why it was still wrong |
| --- | ---: | ---: | ---: | --- |
| **Giovanni `diamond_backpack`** | 20,000 | **10,000** | **−10,000** | 0.55x of leg 8's entire income for +12 slots over gold. The worst-priced item in revision 1 once the multiplier is applied |
| **Giovanni `obc` gold cap** | 15,000 | **6,000** | **−9,000** | 0.42x of the leg for one cap, and if it is repeatable its price *is* the hyper-training economy. At 6,000 a badge-8 player can buy two or three, which is what hyper-training needs |
| **mining town shelf** | 15,800 | **9,200** | **−6,600** | the largest off-path shelf, offered at `gym3_cleared` where cumulative headroom after the critical path is about 8,900. Optional content must be payable out of *slack*, not out of leg income |
| **Surge shelf** (`iron_backpack` 6,000 → 4,500 and the two upgrades) | 12,500 | **8,500** | **−4,000** | the ladder's own declared pivot: 6,000 alone was 52% of the leg, leaving nothing for the leg's other rungs. A pivot the ladder's own buyer cannot reach is not a pivot |
| **Blaine `gold_backpack`** | 12,000 | **8,000** | **−4,000** | +15 slots and +1 upgrade slot over iron. A receipt, not a reward (§2.4) |
| **Giovanni `inception_upgrade`** | 10,000 | **7,000** | **−3,000** | Giovanni's shelf was 45,000 against a leg of 36,040 |
| **Sabrina stack tiers** | 2,000/4,000/8,000 | **2,000/3,500/6,000** | **−2,500** | the three tiers alone were 1.6x the leg in revision 1; capped at 3 per pack, so this is the whole shelf |
| **Koga `mega_bracelet`** | 9,000 | **7,500** | **−1,500** | 0.59x of the leg. Koga's shelf is still the tightest on the ladder at **92% of its leg** — deliberately, because the bracelet is the one rung a player should *save* for, and §0.4's bounded blackout is what makes that safe. **If B10's cap is generous, this is the first rung to cut again** |
| **Blaine `auto_smelting`** | 6,000 | **4,500** | **−1,500** | `furnace_upgrades\|1` means the player picks one, so the group's prices must each stand alone |
| **Koga `advanced_magnet`** | 4,000 | **3,000** | **−1,000** | — |
| **Blaine `blasting`** | 3,200 | **2,500** | **−700** | — |
| **Misty `advanced_filter`** | 3,000 | **2,500** | **−500** | Misty's shelf was the closest call in revision 1 (1.9x) and needed the least |
| **Koga `smoking`** | 2,200 | **2,000** | **−200** | rounding, for the shelf to fit |
| **northlight "field bedroll"** | 3,000 | **dropped** | — | not a price error: `sleepingBagEffects` is server-wide, so the tier cannot exist (U-6). Said rather than invented |

**Unchanged, because the multiplier made them correct:** Pallet's 300/250; Brock's entire
shelf (1,800/2,500/1,200) and its 7,500 crafting upgrade; Erika's whole shelf
(2,000/4,500/900/500); northlight's 800 hammocks; every sunset_west scroll and shulker; the
Assayer's 2,100 stones; tea town's discount. That list is almost exactly the set
`INCOME_MEASUREMENT.md` §4.2 called *"correctly priced or near enough"*, **plus Brock's**,
which was "IMPOSSIBLE at 3.4x" and is now 0.58x of its leg. **That is the multiplier doing
its job, and it is why no blanket divide was applied.**

**Nothing in the ladder is priced too low**, with one deliberate exception: Erika's
CobbleCuisine consumables, which §1.2 calls a restock rather than a rung, and which the new
multiplier makes genuinely trivial (900 is 5% of leg 4). That is correct for a restock.

### 1.5 What the ladder deliberately does not do

Unchanged from revision 1:

- **It does not sell a badge or any badge-shaped token.** RCT already gives badges from each
  leader's loot table on first defeat (`data/progression.json` note 6). Two ledgers is a bug.
- **It does not include `everlasting_upgrade`, `infinity_upgrade` or
  `survival_infinity_upgrade`.** They end the economy the markets exist for (Q-6).
- **It does not rewrite `stock_policy` here.** Releasing `Pokéballs`, `Combat`,
  `Treatments`, `Remedies` and `Boosts` **item by item** is what the power strands in §1.1
  need, and it is `trainer-balance-designer`'s work, not this document's. What this document
  owes it is the shape: an item is released to a *gated counter* at the badge named above,
  not to the clerk's ungated shelf.

---

## 2. The backpack as the spine: unchanged, and now explicitly only half the ladder

### 2.1 The real numbers

| Tier | Item | Slots | Upgrade slots | Over the tier below | Price |
| --- | --- | ---: | ---: | --- | ---: |
| 1 | `backpack` | 27 | 1 | — | 300 |
| 2 | `copper_backpack` | 45 | 1 | +18, +0 | 1,200 |
| 3 | `iron_backpack` | **81** | **7** | **+36, +6** | **4,500** |
| 4 | `gold_backpack` | 96 | 8 | +15, +1 | 8,000 |
| 5 | `diamond_backpack` | 108 | 9 | +12, +1 | 10,000 |
| 6 | `netherite_backpack` | 120 | 10 | +12, +1 | reward, not sold |

A vanilla inventory is 36 slots. **81 is 2.25 inventories, reached at badge 3 of 8.** The
number that matters is not 81 but **7**: four portable workstations (`crafting`, `anvil`,
`smithing`, `stonecutter`) + `feeding` + one of `pickup`/`magnet` + one furnace = exactly
seven. **The pack's own config hands the player a complete "no house" loadout at iron.**

Note what the price column now says out loud: iron costs 4,500 and the three tiers above it
cost 8,000, 10,000 and nothing. **The curve is deliberately flat above iron**, because the
tiers above iron are receipts (§2.4.1).

### 2.2 Can a player live out of one? Yes

Crafting, anvil, smithing and stonecutter *in the pack*, plus a Comforts sleeping bag that
passes the night and sets no spawn point (`sleepingBagUse = "DAY_OR_NIGHT"`,
`sleepingBagBreakChance = 0`), is every reason a Minecraft player builds a house, removed.
Lumymon's `remotePcEnabled = true` removes the Pokémon half from day one. **Yes, and with
configuration that already ships.**

### 2.3 What it needs

1. **The tiers above leather must not be craftable.** Supply is crafting-only
   (`chestLootEnabled = false`, `backpackDropChance = 0.0`, `entityLootTableList = []`), so
   if the recipes stay, the shop is a convenience and the spine is decorative. **The one
   blocking dependency, and untested in this pack (U-3).**
2. **The shelf must be visible before it is affordable.** An absent recipe reads as a
   mystery; a priced shelf the player cannot yet afford says "later". This is also precisely
   what makes B7's price-as-gate work (§4).
3. **A second counter per town.** The clerk keeps the trade GUI for ungated basics; the
   quartermaster is a dialogue NPC for gated goods (`MARKET_GATING.md` §4). NPC classes load
   only at server start, so each new counter is a **restart**, and its placement is an RCON
   `spawnnpcat` step in `tools/reapply.py` (R17F), never a function.

### 2.4 What it breaks

1. **Storage is not a reward in this pack.** Lumymon gives remote PC storage at minute one;
   shulkers, barrels, chests, Iron Chests and Tom's Storage all exist. By badge 3 the player
   has 81 slots and will never fill them. **Rungs 4, 5 and 6 are receipts, not rewards** —
   which is why §1.4 cut gold and diamond hardest and why B6's power strand exists. If the
   owner wants six real tier rungs, `sophisticatedbackpacks-server.toml` has to be re-tuned
   in `modpack/config/` (Q-3).
2. **Portable crafting removes the reason to return to town.** Named because it is the real
   tension in the brief. The ladder's answer: markets sell what the pack **cannot make** —
   stones (2,100, no buy-back ever), balls, potions, revives, scrolls, TM blanks, caps. The
   counter stays the destination even when the house is not. **B6 strengthens this
   considerably:** a power strand is by construction unmakeable.
3. **Gating controls purchase, never possession.** No mod in the pack exposes a per-player
   gate on an item once bought; in a four-friend co-op one player buys the crafting upgrade
   and hands it to three friends. **The ladder is a pacing tool, not an enforcement — so it
   should be generous, because it cannot be strict.** This applies to B7's price gate too:
   one player saving 7,500 unlocks portable crafting for the party.
4. **No trade GUI at a gated counter.** Fixed quantities in a dialogue menu, no
   drag-and-drop, no stack arithmetic. A real downgrade in feel; the owner should see one
   before it spreads to sixteen counters.
5. **Two players at one counter is unproven** (`MARKET_GATING.md` open question 1; blocked on
   a second account).

### 2.5 The two strands, settled

Revision 1 argued that *"the backpack is the spine of the 'no house' promise. It is not the
spine of progression"*, and recommended two strands per counter. **B6 accepts that.** So the
ladder is no longer a single line with three power rungs bolted on; §1.1 has a power column
for every town, and the four power families are:

| Family | Source | What it is worth | Status |
| --- | --- | --- | --- |
| **TMCraft blanks, grades 1-5** | Brock, Surge, Sabrina, Blaine, Giovanni | **move access** — campaign power, not convenience. Six material grades x four forms, 24 ids VERIFIED | the grade→move-pool semantics are **ASSUMED** (U-4). If the grades do not mean what we assume, the five rungs collapse into one and the power strand needs a different spine |
| **Key items** | Koga (`mega_bracelet`) | one item, one mechanic, instantly legible | VERIFIED id |
| **Evolution stones** | the Assayer (mining town), 2,100, no buy-back | the catch-up for a skipped place | **already authored and built** |
| **Released Mart lines + caps + vitamins** | Misty, Erika, Koga, sunset_west, northlight, Giovanni | medicine, X items, better balls, hyper-training | needs `stock_policy` opened item by item (§1.5) |

**The TM grade arc is the load-bearing assumption in this revision.** It is the only power
family with five rungs, and U-4 is therefore promoted to the second-highest unknown, behind
only the multiplier's effect on the bank.

---

## 3. The spine against the brief, in one paragraph

Badges 0-3 are the "you can leave home" arc: a pack, a bedroll, two workstations, then the
iron tier that makes them usable at once — and the crafting upgrade visible from badge 1 as
the thing you are saving for. Badges 4-6 are "you can stay out": feeding, pickup,
compression, and on the power side the friendship foods, the Mega bracelet and the third TM
grade. Badges 7-8 are "equipped for the League", where the convenience strand has nothing
left to give and the power strand (furnace, caps, grades 4-5, inception) carries it.
**The convenience arc still finishes at badge 3, four rungs before the game does** — that is
exactly why B6's power strand exists, and it is no longer a structural problem but the
design.

---

## 4. `crafting_upgrade` at Brock's, priced as the gate (B7)

**The decision:** move `crafting_upgrade` from Sabrina's (`gym6_cleared`) to **Brock's**, and
gate it with **price alone**.

**The price: 7,500 — unchanged from revision 1.** The multiplier did the work; the number did
not need to move. This is the clearest case in the document for not double-correcting.

**Why price is the right gate.** It is the only mechanism in this whole document that needs
**no flag, no dialogue visibility, no datapack and no restart**: it is a line on a shelf.
And it buys exactly the legibility a suppressed recipe destroys — the rung is **visible from
badge 1** and affordable around badge 3, which is also what §2.3.2 asks for.

**Unaffordable at badge 1 — the arithmetic.** Model B gives a badge-1 player
**$9,475 gross** (§0.2). Mandatory first-leg spend: the trainer card **500** (§5.1) and a
frugal Mart restock of 5 balls + 3 potions, **1,600** (ASSUMED allowance,
`INCOME_MEASUREMENT.md` §2.5). Maximum possible balance at badge 1, for a player who buys
**nothing else at all** — no backpack, no bedroll, none of Brock's shelf:

> 9,475 − 500 − 1,600 = **7,375 < 7,500.** Unaffordable, by $125.

Under **model A** it is 5,205 − 2,100 = **3,105**, unaffordable by a wide margin. Under
**model C** it is 11,713 − 2,100 = **9,613**, so an ascetic model-C player *could* buy it at
badge 1. **The $125 margin under model B is too thin to be a gate**, and the model-C case
leaks outright, so:

> **Recommendation: hold 7,500, and re-check it the day EXP-A (U-2) returns.** If EXP-A lands
> at or above model B, raise it to **8,000** for a $625 margin. Do not raise it before the
> measurement: an 8,000 gate costs the badge-3 affordability shown next.

**Affordable by badge 3 — the arithmetic.** At badge 3 a player has earned **$28,655**
(model B). A player who bought Pallet's two items and Brock's and Misty's shelves
(550 + 5,500 + 5,200 = 11,250), paid the card (500) and restocked three legs
(3 x 1,600 = 4,800), and who **banks Surge's leg instead of buying its shelf**, holds:

> 28,655 − 11,250 − 500 − 4,800 = **12,105.**

That affords the crafting upgrade (7,500) **and** the iron backpack (4,500) with $105 to
spare: 12,000 of 12,105. **The gate opens at badge 3 to a player who saved for it, and
stays shut on a player who bought every convenience rung on the way** — which is what
"priced out of reach" is supposed to mean, and it is a choice rather than a wall. A
completionist buyer reaches it at badge 4 instead (45,615 − 27,650 − 500 − 6,400 = 11,065).

**Minus one bounded blackout** (§0.4, ASSUMED ~1,500) the badge-3 saver holds 10,605 and
must choose crafting *or* the iron pack that leg. That is a good decision to hand a player,
and it is only tolerable because B10 made the loss bounded.

**The data change: none is needed.** `data/traders.json` carries no `crafting_upgrade` record
(grep returns no match), and no ladder price of any kind — the file is trader records plus
`stock_policy`. **I have not touched it.** The implementer's figure is:
`crafting_upgrade`, **7,500**, at Brock's gated counter, visible from `gym1_cleared`, no flag
gate of its own, in whatever shelf schema step 6 of §9 defines. If it is ever written into
`data/traders.json` directly it must follow the file's conventions — the authored offer shape
the templates themselves carry, `{Item:{count,id},Price:"<n>"}`, as `stock_policy.stones`
does at `data/traders.json:584`, with a `status` field recording that it is a proposal and a
`why` recording the gate.

### 4.1 The order against the level caps

Caps: `gym_ace_levels` 20/25/30/35/40/45/50/55, `relative_level_cap: 0`,
`allowOverLeveling = false`, so a player's cap is the next required leader's ace exactly.
**The test a rung must pass: it must arrive while the thing it affects is still binding.**

| Cap | Badge | Rung that must land here or earlier | Why it stops mattering later |
| ---: | ---: | --- | --- |
| 20 | 0 | leather backpack, sleeping bag, **trainer card** | the card is a *prerequisite* for trainers spawning at all (§5.1) |
| 25 | 1 | copper backpack, stonecutter, anvil, TM grade 1; **crafting visible** | an anvil matters while gear is repaired rather than replaced |
| 30 | 2 | filter, tank, first released potions | sorting matters while the pack is small |
| 35 | 3 | **iron backpack (81/7)**, TM grade 2, **crafting affordable** | **the hinge**; later than badge 3 and six badges of upgrades sit unusable in a one-slot pack |
| 40 | 4 | feeding, friendship foods | `expBoostMultiplier 2.0` and `catchRateMultiplier 2.0` are worth most while the dex is incomplete |
| 45 | 5 | pickup, magnet, **Mega bracelet**, X items | Mega at cap 45 of 55 leaves three gyms to use it on; at badge 7 it is a trophy |
| 50 | 6 | smithing, stack upgrades, TM grade 3 | — |
| 55 | 7 | furnace group, gold backpack, TM grade 4 | heat is pure convenience; late is fine |
| (E4) | 8 | diamond, inception, **gold caps**, TM grade 5 | the only rungs *better* late: hyper-training a level-55 team at the last gate |
| — | champion | netherite and TM grade 6 as rewards, not sales | nothing left to pace |

**B7 removes the one contradiction revision 1 found in its own table.** `crafting_upgrade` at
cap 50 was three-quarters through a campaign whose premise is "never build a house"; at
Brock's, visible from cap 25 and affordable at cap 35, it lands where the promise is made.

---

## 5. What this collides with

### 5.1 The trainer card: 500 at Pallet, and conditional on a measurement being taken tonight

`spawningRequiresTrainerCard = true` (`modpack/config/rctmod-server.toml:87`): with no card
in inventory, trainers do not spawn naturally at all. The card costs 500 and appears **only**
in `defaultShop`, which is a flat server-wide list with no merchant key (VERIFIED); none of
our 14 clerks stocks it (`stock_policy.mart.items` = `poke_ball`, `potion`, `antidote`).

**The decision records it at 500 at Pallet. The multiplier makes 500 possible rather than
impossible — but only if income at badge 0 is nonzero, and badge-0 income is *entirely*
wild income.** Authored income before Pallet is exactly $0 under all three models
(`INCOME_MEASUREMENT.md` §4.1: *"a hard blocker, not a calibration question"*), and
`earnCobbleDollarsFromWildPokemon: true` with the **rate unknown** is the only tap that can
pay for it. That rate is being measured in game tonight (EXP-C), so:

**Conditional, stated as a rule rather than a guess:**

| If tonight's wild measurement shows… | then the card is… | reasoning |
| --- | --- | --- |
| **near zero** (under ~$300 for a realistic first session's wild battles, post-1.25) | **free: an item in the starter kit, price 0**, and Pallet's power strand becomes the first Poké Ball line instead | a 500 price against 0 income is not a gate, it is a stop. A licence the region requires and will not sell is a bug |
| **$300-$1,500** for a first session | **500, kept**, but Pallet's *convenience* strand must be buyable after it: 300 + 250 + 500 = 1,050 total at badge 0 | the card is then a real but payable first errand, and the backpack may trail it by a few catches |
| **above ~$1,500** | **500, kept, and the rest of the ladder is re-derived**, because wild income is then a tap on the same order as trainers and every figure in §0.2 is a floor | `INCOME_MEASUREMENT.md` §5 EXP-C: *"if wild battles pay anything like per-level parity with trainers, a player who grinds has unbounded income and the ladder's prices only gate the first pass"* |

**I am not guessing which.** Everything in §1.3 assumes **no wild income**, exactly as
`INCOME_MEASUREMENT.md` §2.3.3 does, so every ratio there is a **worst case** and wild income
can only make the ladder more affordable. The card is the one row where that conservatism
breaks, because its budget is wild income and nothing else.

**Also unresolved and cheap:** whether CobbleDollars starts a player with a balance. No
config key in the pack sets one; `cobbledollars query @s` on a brand-new player answers it in
one command (EXP-F). If there is a starting balance, the whole conditional dissolves.

**And the third instance of "our list is not the world":** `spawnTrainerAssociation = true`
means RCT's own association NPC already spawns near any village with three occupied beds. Our
towns have beds. **RCT's progression counter and its trade are already standing in our
markets, authored by nobody, and are not in `data/placements.json`.**

### 5.2 Two level ladders keyed on different defeats

Our `gymN_cleared` flags are set by `trainer_defeat` on named ids (`kanto_brock`, …). RCT's
cap comes from the next *required* trainer in its series, whose chain is Cobbleverse's
`requiredDefeats` from COBBLEVERSE-RCT-DP-v20 — and `data/progression.json` note 7 records
that **which leader sits in which town is still open.** If the orders differ, a player clears
town 3's gym, receives our rung, and **RCT's cap does not move.** Both cannot be
authoritative. `trainer-balance-designer`'s call; it needs an ADR (Q-7).

**Revision 2 raises the stakes on this**, because every price in §1.1 is calibrated against
the authored level sums of specific legs (§0.2). If the leader order changes, the leg income
column changes and the shelf percentages move with it.

### 5.3 Income, not level, paces the ladder — and now it is measured once

`freeroamRequiresCompletedSeries = true` and the cap is always the next leader's ace exactly,
so a money-priced rung is paced entirely by income. That is no longer unmeasured: one
in-game battle ($732, then $600 over `kanto_brock` at cap 20) anchors the band, and the
multiplier is set against it. **The remaining gaps are the formula's shape (U-2), wild income
(§5.1) and the bank (§0.5)** — not the order of magnitude.

### 5.4 `maxLevelDiff = 10` and `forceBattleMaxLevelDiff = 12` already gate the off-path towns

A player who detours to the mining town or the port early meets trainers up to twelve levels
above them, forced into battle on sight at 16 blocks. **The off-path shelves are already
gated by survivable travel, independently of any flag.** Where travel already gates a shelf,
**leave it ungated**: a flag that duplicates a difficulty gate costs a restart and buys
nothing. The flags in §1.2 are a guess at reachability and need U-5.

### 5.5 RCT owns the badge reward

Badges come from each leader's RCT loot table on first defeat. The market must not hand out a
badge-shaped token as well.

---

## 6. Assumptions, and the ones that would move prices

### 6.1 ASSUMED, load-bearing

| # | Assumption | What it holds up |
| --- | --- | --- |
| A-1 | **Model B is the right income shape** ($13.07 per defeated level), calibrated on one battle with the defeated team *proxied* by our own `gym_01_brock` (18/18/20) | every price in §1.1. The band A-to-C is 6.5x wide at badge 1 and 1.3x wide from badge 4 |
| A-2 | **`cobbleDollarsIncomeMultiplier` scales battle income linearly and multiplies nothing else** | §0.1's entire premise. If it also scales bank sales, §0.5 applies |
| A-3 | **TMCraft blank grades gate which moves a TM can reach** | five of the ten power rungs (§2.5) |
| A-4 | **The blackout charge becomes bounded and modest** (§0.4) | Koga's bracelet, Giovanni's shelf, and B7's price gate |
| A-5 | **A frugal player spends about $1,600 a leg on Mart basics** | the 30-35% slack in §1.3 |
| A-6 | **Nobody re-fights a trainer and nobody grinds wild Pokémon** | §0.2's whole table is a *first-pass* figure, so a floor |
| A-7 | **`stock_policy`'s withheld categories can be released item by item to a gated counter** | every released-Mart power rung |

### 6.2 What is VERIFIED

The config keys and their current values; the two measured payouts; the 24 TMCraft ids; the
backpack tier slot counts; `bank.json`'s 82 sell prices; the dialogue-visibility, flag-probe
and checked-charge mechanisms (EXP-022, EXP-040, EXP-042, `tools/ferries.py`); that
`defaultShop` is a flat global list; that the campaign has **exactly one money tap** —
winning battles — because no authored reward, quest or first-win grant pays a dollar.

### 6.3 Files this document does not own, whose numbers the multiplier moves

Flagged, not changed. **Every fixed price in the campaign becomes 2.5x cheaper in real terms
the moment the key changes:**

- `data/traders.json` `stock_policy.stones.price` **2,100** — was a fifth of a mid-game leg,
  becomes a twelfth. Open decision O-6 already exists on it.
- `data/ferries.json` fares **100-600** — a round trip falls from 8% of a leg to 3%.
- `base-pack/cobbleverse/config/cobbledollars/default_shop.json` — great ball 750, ultra
  1,000, revive 3,000, trainer card 500.
- `base-pack/.../bank.json` — the sell side (§0.5, §6.4).

None of these is wrong *because* of the multiplier; they are simply all now cheap, and
somebody should decide that deliberately rather than by omission.

### 6.4 A shop price must exceed `bank.json`'s sell price for the same item

**A structural rule this revision adds, because the power strand nearly broke it.** Vitamins
sell to the bank for **2,500** (`bank.json`). A shop selling a vitamin at 2,500 is a
zero-cost laundering loop, and one selling it below that is an **infinite money printer**. So
northlight's vitamins are priced at **3,500**, not 2,500.

**Every power-strand item must be checked against `bank.json`'s 82 entries before it is
priced.** This is the same reasoning that made the Assayer never buy a stone (*"a stone with
a sell price would make a face a money printer"*, `data/traders.json:589`) and it generalises:
it belongs in the shelf schema's validation (§9 step 6), as a check that fails closed.

---

## 7. Unknowns — experiment candidates, in the order they should be settled

| # | Unknown | Blocks | Smallest proof |
| --- | --- | --- | --- |
| **U-1** | **Does `cobbleDollarsIncomeMultiplier` scale bank sell-backs as well as battle income?** | **B8 itself.** If yes, raising it to 1.25 turns a reviewed leak into an unbounded one (emerald block 3,750 → 9,375, elytra 25,000 → 62,500) | sell one emerald block, read the balance, change the key, reboot, sell another. **Must run before the multiplier ships.** |
| **U-2** | **The income formula.** Fight `route_01_trainer_01` (1 Pokémon, L7), `route_01_trainer_04` (3, sum 48), `gym_01_brock` (3, sum 56, ace 20), reading `cobbledollars query @s` either side | collapses the A/B/C band to one column and confirms or moves every price in §1 | three battles, ten minutes (`INCOME_MEASUREMENT.md` EXP-A) |
| **U-3** | **Wild income per hour**, in a low band and a high band | §5.1's trainer-card conditional, and whether §0.2 is a floor or the answer | EXP-C: defeat 10 wild Pokémon of recorded levels, twice. **Being measured tonight** |
| **U-4** | **Do TMCraft blank grades gate the move pool?** 24 ids VERIFIED, semantics ASSUMED | five of the ten power rungs (§2.5) | a TMCraft jar read, for `cobblemon-researcher` |
| **U-5** | **Can a datapack suppress a mod's recipe?** | the whole convenience strand: without it every tier stays craftable | suppress one backpack tier recipe, boot, open REI |
| **U-6** | **Which off-path towns are reachable at which badge**, by `data/towns.json` and §5.4's level diff | the three off-path flags in §1.2 | a tool read of `data/towns.json` plus route trainer levels. No server |
| **U-7** | **Is `defaultShop` the fallback for a merchant carrying no `CobbleMerchantShop`?** | whether a trainer card is buyable anywhere in the region at all | summon a bare CobbleMerchant on staging and right-click it |
| **U-8** | **Does CobbleDollars give a new player a starting balance?** | §5.1 — one command decides whether row 0 is possible | `cobbledollars query @s` on a brand-new player (EXP-F) |
| **U-9** | **Can a "field bedroll" differ from a sleeping bag?** `sleepingBagEffects` is server-wide | northlight's dropped rung. If not, northlight sells hammocks and colour, and that is all | read the `comforts` jar for a per-item key |
| **U-10** | **Two players, one dialogue counter, at once** | whether every gated counter is one NPC or one button per shelf | `MARKET_GATING.md` §5 criterion 5; blocked on a second account |

**U-1, U-2 and U-3 before anything in §1 is built.** U-1 because it can invalidate the
decision that set these prices; U-2 because it closes the band; U-3 because it decides the
trainer card and whether the ladder gates a first pass or a campaign.

---

## 8. Open questions for the owner, renumbered

The four decisions retired revision 1's Q-1 (which strand is the spine — **both**), Q-2
(where crafting lives — **Brock's, price-gated at 7,500**), the repricing method (**the
multiplier, not a divide**) and most of Q-4 (**the card is 500 at Pallet**, conditional on
U-3). What remains:

1. **The multiplier ships only if U-1 says the bank is untouched.** If it scales sell-backs
   too, do we (a) ship 1.25 and re-price `bank.json` in a `modpack/config/` overlay, (b) ship
   a smaller multiplier, or (c) go back to dividing the ladder? §0.5.
2. **What cap does B10's blackout charge land on?** §0.4 budgets a bounded loss of about
   $1,500-$2,000 mid-game. If the cap is high enough that a loss still exceeds a leg's
   income, Koga's bracelet (7,500, 92% of its leg) is the first rung to cut again.
3. **Should `sophisticatedbackpacks-server.toml` be re-tuned in `modpack/config/`?** As
   Cobbleverse ships it, gold, diamond and netherite add 15, 12 and 12 slots — which is why
   §1.4 cut their prices by 4,000 and 10,000. Re-tuning would make them rungs instead of
   receipts. §2.4.1.
4. **Does `tableland_stop` get a trader record?** The only off-path stop whose dressing
   (sample piles, a sieve, ore crates) already argues for a counter; it has no record today.
5. **Is `netherite_backpack` `champion_cleared`'s reward, or not in the campaign?** §1.1 row
   9 recommends the reward. Same question for TMCraft grade 6.
6. **Do `everlasting_upgrade` / `infinity_upgrade` / `survival_infinity_upgrade` exist in this
   campaign at all?** §1.5 recommends no: they end the economy the markets exist for.
7. **Which is authoritative, our town order or RCT's `requiredDefeats` chain?** §5.2. They
   must be reconciled, not layered; the answer constrains `data/trainers.json` **and** every
   leg income figure in §0.2. Needs an ADR.
8. **`stack_upgrade_*` at Sabrina's or the mining town?** A study town sells compression; a
   smelter town has an equal claim. One or the other, not both.
9. **Is the TM grade arc acceptable as the power strand's spine before U-4 is answered?** Five
   of ten power rungs rest on an assumption. If the owner would rather not bet on it, the
   alternative spine is released Mart lines plus key items, which is three or four rungs, not
   ten.

---

## 9. If this is accepted: the ordered plan, and who does each step

| # | Step | Agent |
| ---: | --- | --- |
| 1 | **U-1: does the multiplier scale bank sales?** One sale, the key change, a reboot, one sale | main session (a staging run is not delegated) |
| 2 | Write `modpack/config/cobbledollars/common.json` with `cobbleDollarsIncomeMultiplier: 1.25` and nothing else, and record in `docs/STATE.md` that it overrides the base pack | `minecraft-systems-dev` |
| 3 | **U-2: the formula, in three battles**; **U-3: wild income, two bands**; **U-8: the starting balance** | main session, one staging session |
| 4 | Settle the trainer card against §5.1's table, and whether it is stocked or granted | the owner, then `datapack-content-dev` |
| 5 | Jar reads: TMCraft grade semantics (U-4), `comforts` per-item effects (U-9) | `cobblemon-researcher` |
| 6 | A `data/` schema for a gated shelf (`data/market.json`, or a `shelves` block in `data/traders.json`), its validation, **and §6.4's bank-floor check as a fail-closed rule** | `minecraft-systems-dev` with `test-author` |
| 7 | Recipe-suppression proof: one backpack tier, boot, REI (U-5) | `datapack-content-dev` builds; `qa-reviewer` grades |
| 8 | **EXP: one badge-gated counter in one town**, both strands — `MARKET_GATING.md` §5's six criteria, on the disposable world | `datapack-content-dev` builds; `qa-reviewer` grades |
| 9 | Re-derive §1 against step 3's measured formula; collapse the A/B/C band to one column | `trainer-balance-designer` |
| 10 | Reconcile the RCT chain with town order (§5.2) | `trainer-balance-designer`; needs an ADR |
| 11 | Only then: the remaining fifteen counters, and `stock_policy` opened item by item | `datapack-content-dev` |

**Nothing past step 8 is built before step 8 passes** (principle 20): sixteen counters
authored against an unproven gate is sixteen counters to redo.

---

## 10. Where an ADR is owed

- **The gated-counter mechanism** (dialogue NPC + flag visibility + checked CobbleDollars
  charge, trade GUI given up at gated counters). It constrains every market in the region and
  is expensive to reverse once sixteen counters exist. Evidence: `MARKET_GATING.md`,
  EXP-022, EXP-040, EXP-042 — real, but the counter itself is unrun. **Propose step 8 before
  the ADR.**
- **The income multiplier at 1.25.** One key, but it re-denominates every price in the
  campaign (§6.3) and is cheap to reverse only until content is priced against it. Its
  evidence is `INCOME_MEASUREMENT.md` plus U-1 and U-2. **An ADR as soon as U-1 and U-2
  return** — not before, because U-1 can reverse the decision.
- **Whether the RCT series chain or our town order is authoritative** (§5.2, Q-7). Expensive
  to reverse in both directions; an ADR as soon as Q-7 is answered.
