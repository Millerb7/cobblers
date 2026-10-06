# The material exchange: what Minecraft effort is worth, and what it buys

**Status (2026-10-06):** authored and checked offline; **not run in game, not independently audited, not applied.**
Data: `data/bank.json` (the material table, `effort_model`, `exchanges`) and `data/markets.json` (the exchange
lines on two counters). Generators: `tools/bank.py` (the bank file) and `tools/markets.py` (the merchants). Tests:
`tests/test_material_exchange.py`.

**The owner, 2026-10-06:** "I want ordinary Minecraft play to be worth doing. Netherite traded for a Master Ball is
the shape -- real Minecraft effort converted into Pokemon progression ... high-value exchanges that take real effort:
netherite, elytra, beacons, dragon eggs; evolution items, held items, balls, TMs as the rewards; priced so it is an
alternative path, not a shortcut past the economy."

## 1. Can a merchant take items as payment? No.

Read in `CobbleDollars-fabric-2.0.0+Beta-5.1+1.21.1.jar` (the 2026-10-05 server snapshot), with `javap`:

- `fr.harmex.cobbledollars.common.world.item.trading.shop.Offer` has three fields: `item` (an ItemStack), `price`
  (a BigInteger) and `stock` (an int).
- `Shop$Companion` reads an offer's NBT keys `Item`, `Price` and `Stock`, and nothing else. A missing `Stock` means
  -1, unlimited. A `Stock` that is set belongs to the merchant and is shared by every player.
- `network.handlers.server.BuyHandler.buy` compares the player's CobbleDollars with the price, subtracts the price
  and gives the item stack. It reads no cost item anywhere.

`tests/test_material_exchange.py` checks the three fields against the jar.

**So the exchange is two halves of one merchant.** Shift + right-click opens the Bank, which buys the material at
`data/bank.json`'s price. The shop screen sells the reward at exactly **N x** that price. A line carries
`exchange_for {item, count}`, and the check refuses a price that is not exactly count x the bank's price. So "a
Master Ball for thirty netherite ingots" is literally true at the same counter: sell thirty ingots, then buy the
ball.

A real item-for-item barter does exist, and it has no dialogue: a vanilla villager's `Offers` (buy, buyB, sell). It
is not built, because none of the three market audits models it (`exchanges.not_built`; decision `barter_villager`).

## 2. The material table

The bank's list is one server-wide file. It holds **122 entries: the base's 80, kept unchanged, and 42 of ours.**
Five are new tonight, all in the Nether tier. The other 37 were added on 2026-10-05.

The table has three parts, and every row carries a reason:

| Part | Rows | What |
|---|---:|---|
| `buys` (ours) | 42 | minerals 11, apricorns 7, berries 10, drops 9, **nether 5** |
| `never_buy` | 28 | stones, storage blocks, authored dressing, nuggets, charcoal; tonight: netherite block, beacon, glowstone dust, crying obsidian, obsidian |
| `unreachable` | 7 | elytra, dragon egg, shulker shell, nether star, heavy core, mace, trial key |

The five new rows:

| Item | $ | Supply | Rate/h (ASSUMED) |
|---|---:|---|---:|
| `minecraft:ancient_debris` | 200 | the Nether's lower layers, diamond pickaxe; risk: lava, with no fire resistance | 10 (30 by bed or TNT) |
| `minecraft:netherite_scrap` | 202 | smelted debris (raw + 2) | 0 |
| `minecraft:netherite_ingot` | 900 | 4 scrap + 4 gold = $896 at the bank, so $900 (crafts rule) | 0 |
| `minecraft:quartz` | 2 | nether quartz ore | 60 |
| `minecraft:nether_wart` | 1 | fortress gardens, then a farmed crop (a token) | 0 |

The rules that set those prices, each enforced by `tools/bank.py check`:

- **Smelting pays raw to raw + 2.**
- **Crafting pays its inputs' total to that total + max(2, 1%).**
- **No unreachable item is bought.**
- **Every tier holds the two wage rules in section 3.**

**Crops are not extended.** The base already pays $5-$40 for food, and an unattended farm makes several of those
items with no player at all (section 7, `base_afk_prices`).

## 3. Effort to dollars: the wage rules

The **hour** of a tier is the sum of rate x price over that tier's items. Every rate is ASSUMED; nobody has timed
gathering in this world. The leg incomes are relayed from `data/markets.json income_basis.leg_by_badge` (model B).
`max_leg_hours` = 4 is also ASSUMED.

Two rules:

- **half_wage:** typical hour x 4 ≤ half the leg's income. Gathering is worth doing, but never the better plan.
- **upper_wage:** the efficient method's hour x 4 ≤ the whole leg's income. The best grinder earns at most what a
  fighter earns.

| Tier | Opens | Leg income | Typical hour | x4 vs half the leg | Upper hour | x4 vs the leg |
|---|---|---:|---:|---|---:|---|
| early | leg 1 | 9,475 | 620 | 2,480 ≤ 4,737 | 620 | 2,480 ≤ 9,475 |
| deep | leg 3 | 11,633 | 1,350 | 5,400 ≤ 5,816 (tight) | 1,350 | 5,400 ≤ 11,633 |
| nether | leg 7 | 26,760 | 2,120 | 8,480 ≤ 13,380 | 6,120 | 24,480 ≤ 26,760 |

The deep tier passes by only $416. Any measured rate above the assumed one breaks it, and that is the point: when a
rule fails, re-price. **Emerald (base, $400) is outside the tiers because its ore density in this world is
unknown** (`emerald_rate`).

## 4. The exchanges, and where

Exchange lines go only on **off-path counters whose shelf the ladder gates on a badge**. Those are the only places
an exchange avoids both failures below.

| Counter (town, flag) | Unit | Lines |
|---|---|---|
| Fossick, Mine Stores and Exchange (`mining_town`, gym3) | diamond, $120 | Metal Coat, Protector, Razor Claw, Razor Fang, Oval Stone: **18 diamonds, $2,160** each. Rocky Helmet: **25, $3,000** |
| Northlight, Station Supply and Exchange (`northlight`, gym6) | netherite ingot, $900 | **Master Ball: 30 ingots, $27,000.** Dubious Disc, Reaper Cloth, Dragon Scale, Prism Scale, Deep Sea Tooth, Deep Sea Scale: **3 ingots, $2,700** each. Focus Sash, Expert Belt, Eviolite: **4, $3,600** each. Assault Vest: **5, $4,500** |

The Bank, which buys every material, opens at every CobbleDollars merchant in every town. `buyer_towns` now also
lists Northlight.

**Where an exchange cannot go, and why:**

- **Holdfast and Cinderlee:** these are critical-path counters. Every line there is on the price curve, and a
  $27,000 line would push badge 8's cumulative ask out of the 0.65-0.70 band.
- **Redbrow, Steepside and Pacifidlog:** these have no flag. An ungated ball, held item or evolution item there is
  a known defect in `town_squares_audit.py`.

## 5. The pricing check

**1. Off the curve.** Both counters are `off_path`, and the curve counts critical towns only. Evidence:

- `tools/markets.py audit`: 0 problems.
- `tools/town_squares_audit.py`: 0 problems, 46 known, and its BASELINE_CURVE equality still holds.
- `tools/markets_audit.py`: 0 faults. The only change in its findings is the two counters' existing "window" lines
  (10 and 18 lines now on sale before the badge, from 4 and 7).

**2. Never cheaper power than the shelves already price.** Each kind has a floor, read from data and never set as
a constant:

- **evolution item:** at least the stone price, $2,100 (`traders.json stock_policy.stones.price`).
- **held item:** above the dearest type booster on a shelf, $1,000.
- **ball:** above every other line for sale, the Ability Capsule's $10,000.

**3. An alternative path, not a shortcut.** The Master Ball's $27,000 is 0.75 of leg 8's battle income. To earn it
by debris:

| Route | Hours |
|---|---:|
| Typical Nether hour ($2,120) | 12.7 |
| Bed or TNT mining ($6,120) | 4.4 |
| Fighting leg 7 at 4 h a leg ($6,690/h) | 4.0 |

A Fossick line ($2,160) takes 1.6 h of deep mining, against 0.7 h of leg-3 fighting.

**So grinding is never faster than fighting, and the best grinder is about as fast.** This holds only while legs
take at most 4 hours.

**4. Never a round trip.** The bank buys no reward back. No seller the tool can read sells a material at or under
the bank's price: 280 sell points were checked. The 26 BCA template shops are not read without `--server-dir`.

## 6. Premises that were wrong

- **Elytra, dragon eggs and beacons cannot be exchanges, because no player can get them.** The End has no portal:
  no stronghold can exist in a pre-exported world. A beacon needs a nether star, which needs the Wither, and the
  wither skeleton and the Wither are both blacklisted. The heavy core needs a trial chamber, and none generate. The
  base bank already buys elytra at $25,000; that price is dormant (`end_goods_dormant`). The Deep's city places a
  beacon, so the bank never buys one.
- **TMs are not built.** Both audits verify an id by its lang key. TMCraft's per-move TMs (`tmcraft:tm_earthquake`)
  have no lang key, so both audits would fault them. A native `cobblemon:technical_machine` needs a move component,
  which neither the offer (`Item {count, id}`) nor the audits' one-offer-per-id model can express.
- **"No route" was too strong for most evolution items.** Most are random Pokemon drops in the 1.8.0 jar's species
  data, or craftable from drops (blaze powder from the Charmander line, scutes from Sandshrew and Squirtle). The
  exchange is the **certain** route, not the only one. Exceptions:
  - The Master Ball has no other repeatable route. Its own recipe needs a nether star and a shulker shell.
  - The Dubious Disc drops only from Porygon-Z, and its recipe needs sculk, which this world lacks.
  - Focus Sash and Assault Vest drop from nothing (they are craftable).

## 7. Decisions for the owner

All five are in `data/bank.json decisions_pending`:

- **`base_afk_prices`, the largest hole.** The base pays for melon slices ($5), dried kelp ($10), fish ($10-20),
  mushroom stew ($25) and cookies ($5). Unattended farms make all of these. Changing a base price is a named
  exception to the bank's rules.
- **`end_goods_dormant`:** the base's elytra price is $25,000. Decide it before the End ever opens.
- **`emerald_rate`:** the base pays $400 an emerald, and the ore's density in this world is unmeasured.
- **`barter_villager`:** should netherite buy the ball directly, without passing through dollars?
- **The prices themselves are PROPOSED:** 30 ingots for a Master Ball, 18 diamonds for an evolution item.

## 8. Getting it into the game

1. `python tools/bank.py write`, already done; the file is committed. Then `tools/reapply.py install` copies
   `modpack/config/cobbledollars/bank.json` to the server, and `cobbledollars reload` or a boot makes it live.
2. `python tools/markets.py build`, a prepare job. Then install `cobblers_markets` (world-local) and run **R17M**,
   which re-summons the Fossick and Northlight merchants with their new shops. Its `_done` step kills the older
   copies.
3. Read back from the world: `data get entity` on the two merchants shows 10 and 19 offers.
4. Run the experiment in `data/bank.json experiment` steps 9-10: sell 30 ingots, gain $27,000, buy the ball. This
   is also the first observed purchase from an authored shop (P-7).

## 9. What an audit must check

An independent auditor, who is not this builder, should check the following. Wherever possible, read the INSTALLED
artifacts (`config/cobbledollars/bank.json`, the merchants' `CobbleMerchantShop`), not the two data files.

1. **Exact rate.** For each exchange line, the merchant's offered `Price` equals count x the installed bank price
   of `exchange_for.item`. The builder's test does this offline from the built pack, so in game is what is owed.
2. **Ids.** Every reward and every new material is an item in the server's jars (Cobblemon 1.8.0 and Minecraft
   1.21.1), read from the server, not the snapshot.
3. **No round trip, across the whole world:** no seller anywhere sells a material at or under the bank's price.
   That includes BCA template shopkeepers, donor-template merchants and `defaultShop`. No seller sells a reward
   below its exchange price, and the bank buys no reward.
4. **No craft or smelt loop:** nothing sold crafts or smelts into a bought material for less. Check netherite from
   bastion loot, gold from Nether gold ore, and Gimmighoul's netherite stash. Gimmighoul takes netherite as stash
   points; whether it ever gives netherite back is unread.
5. **No renewable source without work:** Pasture Loot (its jar names no new material: checked), Pickup, ambient
   workers, repeatable rewards, and any automatic farm. The base's AFK-farmable food prices are a known hole
   (`base_afk_prices`).
6. **No authored block that pays when torn down.** The world places glowstone, crying obsidian, amethyst and a
   beacon. The first three and the beacon are never bought; amethyst shards are (base list, 2026-10-05).
7. **The wage rules against measured rates.** Time an hour of strip mining, an hour of bed mining at y15, and an
   hour in a mountain biome for emerald. Time one leg of play to replace `max_leg_hours`. Re-run
   `tools/bank.py check`.
8. **The floors still hold after any shelf change:** each kind's floor is re-read from the shelves.
9. **Prizes are not stock.** No exchange reward is a once-per-player prize in `data/arena_fights.json`, nor a
   one-off grant in `data/rewards.json` or `data/progression.json` that the exchange cheapens. The Master Ball is
   Giovanni's grant and the exchange repeats it at $27,000: decide whether that is acceptable.
10. **The Master Ball against the level cap:** a Master Ball thrown at an over-cap Pokemon breaks free, as
    `data/level_cap.json` says.

## 10. Not verified

- Any purchase from an authored merchant shop in game (P-7).
- Any sale to the bank in game.
- Every rate.
- Leg length.
- Whether `Stock` restocks.
- What the shop screen does with 19 offers in one category.
