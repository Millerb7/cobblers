# Dungeon vaults: what a vault pays

Status: DESIGN, 2026-10-11 (trainer-balance-designer). Authored in `data/dungeons.json` (every `vault` and
`bank_vault` room's `params.loot_by_band`) and `data/dungeon_greed.json` (prices, `vault_budget.dollar_factor`).
Every expected value below was **computed by hand**, not by `tools/dungeon_greed.py`. It needs the `one_of`
pricing the generator builder is adding, and the orchestrator's run is the check. Nothing here has been run in game.

The owner (2026-10-11): *"I think the vault isn't rewarding enough. Need to make sure we give balls the player would
be hard to get access to, maybe a random held item at times, etc."*

## 1. Principles

- **A vault is where the unsold balls come from.** Each dungeon has two or three themed situational balls (the
  "U" pool) and two comfort or cosmetic balls (the "C" pool). Shop balls (Poke, Great, Ultra) are filler, and in the
  bank vaults they are also a jackpot roll paid in bulk.
- **A held roll in every chest.** At band 1 it gives only type-resist berries, which are cheap one-use held items
  that grow nowhere in this world. From band 2 an unsold type booster can come up, from band 3 a utility held item,
  and from band 5 a competitive one. The chance of something better than a berry rises with the band.
- **Candy in every chest** (dungeon-exclusive, docs/STATE.md). The Rare Candy appears as a 1-in-10 to 1-in-4 pick
  from band 3.
- **No Beast Ball and no Master Ball.** I also left out the six direct-trade held items (Choice Band, Choice Specs,
  Choice Scarf, Life Orb, Leftovers, Destiny Knot) and the items a counter sells (Focus Sash, Expert Belt, Eviolite,
  Assault Vest, Rocky Helmet).
- **Chests in one vault differ through rolls.** Every chest gets the same table, but each stack is a separate
  weighted `one_of` behind its own `chance`. Four chests can therefore give a Dusk Ball, nothing, a Premier Ball and
  a Weakness Policy.
- **Value scales by item quality, not by cp.** The budget follows the gathering tier, which is flat across bands 2-4
  (early $620/h, deep $1350/h, nether $2120/h, from data/bank.json buys and effort_model). Bands 3-4 therefore get
  better items at about the same cp as band 2: more U balls, fewer C balls, and more held items above berry grade.

## 2. The three tables

The rows are band → expected cp of one chest. "U" is the themed utility-ball pick and "held" is the chance of the
held roll.

| band | 4-chest vault (treasury, offering well, specimen locker, crows' hoard) | 3-chest vault (pay office, instrument store; three stacks, as tests/test_dungeon_night_shift.py asserts) | bank vault, 4 chests (+ a bulk shop-ball roll) |
|---|---|---|---|
| 1 | 141: ball 0.45 (1 U : 3 C), xs candy 2-4, berry 0.35 | 201: ball 0.65 | 143: ball 0.30, Poke x2-4 at 0.08 |
| 2 | 310: ball 0.60 (U, C, or 2-3 Poke), s candy, held 0.33 | 435: ball 0.85, held 0.45 | 325: ball 0.45, bulk 0.12 (3-5 Poke or 2-3 Great) |
| 3 | 322: ball 0.45 (3 U, 1 C, or 1-2 Great), m candy / rare, held 0.28 | 446: ball 0.65, held 0.35 | 332 (345 with Sport): ball 0.35, Great x2-4 at 0.10 |
| 4 | 323: ball 0.38 (3 U or Great), held 0.18 | 433: ball 0.55, held 0.20 | 325 (308 with Sport): ball 0.28, Great x2-4 at 0.10 |
| 5 | 599: ball 0.60 (U, or an Ultra), l candy / rare, held 0.16 | 811: ball 0.85, held 0.20 | 609 (601 with Cherish): ball 0.35, bulk 0.20 (3-5 Great or 1-2 Ultra) |
| 6 | 646: as band 5, xl candy / 1-2 rare | 870 | 633 (625): ball 0.35, Ultra x1-3 at 0.18 |

Held-roll weights (berries : boosters : utility : competitive) are 100:0:0:0 at band 1, 84:16:0:0 at band 2,
75:20:5:0 at band 3, 60:30:10:0 at band 4, 36:24:28:12 at band 5 and 30:20:30:20 at band 6.

**Per vault, the full 4-chest table.** Expected unsold balls: 1.8 at band 1 (0.45 of them U), 1.0 U + 1.0 C at
band 2, 1.2 U at band 3, 1.1 U at band 4, and 2.1 U at bands 5-6. Expected held items above berry grade: 0.21, 0.28,
0.29, 0.41 and 0.45 at bands 2-6. So a held item turns up "at times": about one vault in three to one in two.

**Budget.** Every chest sits at about 85-92% of its budget at dollar_factor 2.0 (`floor(2 x tier x clock / 4500) /
chests`, each dungeon on its own clock). The tightest cases are the offering well at band 1 (141 against its test's
0.9 bound of 144) and band 6 (646 against 661). The treasury and the crows' hoard are held to 0.95 of the budget at
band 3 (322 against 342).

**Clock** (rate = 10 + floor(carried cp / 200); an opened chest is charged its expected value, not what it rolled).
Emptying a whole 4-chest vault adds about +0.2x at band 1, +0.6x at bands 2-4 and +1.1 to +1.2x at bands 5-6. The
3-chest vault and the bank vault add the same to within 0.1x. Before this change it was about +0.1x at band 1 and
+0.6x at band 6. A full vault never reaches the x3 cap on its own.

## 3. Prices added to data/dungeon_greed.json

| item(s) | cp | source |
|---|---|---|
| Poke Ball | 200 | market: every Mart at $200 (data/traders.json `mart.why`) |
| Dive, Net (pacifidlog), Heavy (redbrow) | 600 | market: $3000 for 5 |
| group `utility_balls` (Quick, Timer, Dusk, Repeat, Nest, Level, Love, Moon, Fast, Dream) | 600 | derived from Dive/Net/Lure/Heavy, the same class |
| group `comfort_balls` (Premier, Heal, Luxury, Friend, Park, Safari) | 200 | derived from the Poke Ball |
| Sport Ball | 350 | derived from the Great Ball |
| Cherish Ball | 500 | design |
| group `resist_berries` (all 18) | 8 | derived from the Lum Berry's last bank price |
| group `type_boosters` (9 unsold) | 1000 | derived from the counters' boosters |
| group `held_utility` (25, Lucky Egg among them) | 2500 | between Metal Coat $2160 and Rocky Helmet $3000 |
| group `held_competitive` (11) | 3600 | derived from Focus Sash, Expert Belt and Eviolite |

`price_order` "derived" now also covers "priced as the sold item of its class". I used that because no recipe or
trade links these items to a priced one.

## 4. Unsold balls by dungeon

| dungeon | room(s) | U (U3 from band 3) | C (bands 1-3) | extra |
|---|---|---|---|---|
| Night Shift | pay office, colliery bank | Dusk, Timer, Quick | Heal, Premier | |
| Overgrown Temple | treasury | Nest, Fast, Quick | Friend, Safari | |
| Drowned Reliquary | offering well | Repeat, Dive*, Net* | Luxury, Premier | |
| Ash Bell | strongroom | Timer, Level, Quick | Heal, Premier | Cherish 5-6 |
| Soul Ossuary | reliquary vault | Dusk, Repeat, Dream | Heal, Luxury | Cherish 5-6 |
| Moth Cathedral | tithe vault | Moon, Love, Quick | Luxury, Friend | |
| Dragonspiral | keepers' store | Level, Timer, Nest | Premier, Park | |
| Field of Swords | strongroom | Quick, Fast, Level | Premier, Heal | Sport 3-4 |
| Warped Laboratory | specimen locker | Repeat, Timer, Nest | Park, Heal | |
| Crucible | strongroom | Level, Heavy*, Timer | Premier, Luxury | |
| Starfall Crater | instrument store, observatory safe | Moon, Dusk, Dream | Premier, Heal | Cherish 5-6 (safe) |
| The Street | savings bank | Quick, Repeat, Fast | Luxury, Friend | Sport 3-4 |
| Under the Patriarch | crows' hoard | Nest, Love, Dream | Friend, Safari | |

`*` marks a ball that is also sold at a counter. The C pool appears at bands 1-2 (both balls) and band 3 (the first
one); the strongrooms keep it at band 3 only where no Sport Ball replaces it.

## 5. The bank check

`data/bank.json buys` lists only minerals. Nothing a vault now gives sells to the bank, so there is no direct
arbitrage. I removed the minerals the old placeholders carried (iron, gold, lapis, diamond). The only cash route is
**the wishing well**: it pays out a share of an item's GREED cp in iron, diamonds or netherite, at an expected share
of 0.9 or under and 2 throws a run, and `priced_ids` takes every group id. A thrown competitive held item (3600 cp)
returns about 3240 cp on average, with a 2% chance of 5x. The well ladders cap a single payout at 64 of the currency
item. Bounded by the vault budget, a vault converted through the well pays at most about 1.8x the run's gathering
time. Resist berries (8 cp) are under min_cp, so the well refuses them.

## 6. "Obtainable without crafting" (docs/STATE.md, the owner, 2026-09-24)

This change gives a natural source to all 18 balls that are sold or traded nowhere. My search of markets.json,
traders.json and direct_trades.json for those ids found none; the Dusk Ball also comes from data/rewards.json and
quests.json. It also covers 9 type boosters, 24 utility held items, 11 competitive held items and 18 resist berries.
Weak spots:

- The Sport Ball drops only at bands 3-4 in two strongrooms, and the Cherish Ball only at bands 5-6 in three.
- The held items are chance drops. "Obtainable" here means reachable, not guaranteed.

## 7. Open questions for the owner

1. **The budget (the change this design rests on).** The enforced KIT3 budget allowed 80-370 cp a chest at
   dollar_factor 1.0. That is under one Great Ball at bands 1-4, so the ask did not fit. I set `dollar_factor` to
   2.0: a vault may pay twice the run's time spent gathering, and a full vault costs about +0.6x clock at bands 2-4
   instead of about +0.3x. The alternative is to keep 1.0 and halve every `chance` above, which gives about 1 unsold
   ball per vault and 1 better-than-berry held item in about 6 vaults. Which do you want?
2. Should the six direct-trade held items (Choice items, Life Orb, Leftovers, Destiny Knot) stay out of the vaults?
3. Should the Lucky Egg come from vaults? It is in the Dragonspiral from band 4 and the Patriarch from band 3.
4. The Sport Ball and the Cherish Ball are narrow. Should they be widened?

## 8. What this breaks until someone else updates it

- `tests/test_dungeon_kit3.py`: `_by_hand` and `test_a_shorter_dungeon...` assume factor 1.0. In
  `test_the_contract_is_published_in_dungeon_rooms_md`, the worked example in docs/mechanics/DUNGEON_ROOMS.md 1b
  ("band 1 82 cp, ...") needs the factor-2 figures (165, 378, 378, 396, 692, 734). That fix belongs to test-author
  and DUNGEON_ROOMS.md's owner.
- Every room's loot uses `one_of`, so it needs the generator builder's `chest_cp`, `check_loot` and `loot_table`
  extension.
