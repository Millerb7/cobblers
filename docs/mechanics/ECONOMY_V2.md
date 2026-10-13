# Economy v2: one value spine, two ways to sell, a top tier that money cannot reach

**Status: DESIGN for the owner's approval, 2026-10-13, `content-architect`. Nothing here is built, run or priced in
data.** It extends `ECONOMY_OVERHAUL.md` (2026-10-10, largely built as data) rather than replacing it; where the two
differ, this document says so line by line (section 4).

**The owner's words (2026-10-13, brainstorming, not a spec):** "economy redesign ... where a master ball and the best
items are grindable but not easy to obtain and we can sell most minecraft and cobblemon items for money, i think like
64 cobble could be $100. maybe we need a system of power per dollar? so a stack of cobble is 1 power = $100 ... idk im
brainstorming." Standing: the game must be completable, and every Cobblemon item reachable, without crafting
(`docs/STATE.md:191`).

**Labels on every number.** MEASURED: read in a cited file. COMPUTED: my arithmetic on cited inputs (I have no
shell; a builder's tool must reproduce each before anything is priced on it). ESTIMATE: mine, with the reason.
RELAYED: from a named document, not re-measured.

---

## 0. Question, and the premises checked first

**Question.** Can the economy be put on one unit of value ("power", 1 P = $100), so that what a player can sell, and
for how much, follows from how hard the thing was to get; so that most Minecraft and Cobblemon items sell; and so
that the Master Ball and the best items stay grindable but slow, with no shortcut through the sell list?

**P1. "64 cobble = 1 P = $100" fails the owner's own test by about 8x, and the bank cannot express it at all.**

- Mining cobblestone at a face with a stone pickaxe is about 1 block a second: 15 ticks to break plus vanilla's
  5-tick swing delay. So it runs about 3,300 an hour, and about 10,000 an hour with an Efficiency V diamond pickaxe.
  ESTIMATE: vanilla break-time arithmetic, not timed in this world.
- At $100 a stack, that is about $5,200 an hour with a stone pick and $15,600 an hour with Efficiency V (COMPUTED).
  Leg 1's whole fight hour is $1,008: `data/markets.json:27` leg 1 is $4,033 / `max_leg_hours` 4,
  `data/bank.json:244`.
- The CobbleDollars bank prices **one unit** at a positive whole number of dollars (`data/bank.json:122`; the jar's
  `Offer.price`, `:12`). Its cheapest possible cobblestone is $1 a block, which is $64 a stack. At that floor a stone
  pick makes $3,300 an hour (COMPUTED), still 3.3x leg 1's fight hour, with no cap: the bank has no per-player or
  per-time key (`data/bank.json:12, :16`).
- **So every bulk block (cobble, dirt, sand, logs, netherrack) is out of the bank by construction.** It can sell only
  as a crate with its own price (section 2.2). The spine itself prices a stack of 64 cobble at about **$12 (0.12 P)**,
  not 1 P (section 1.2).

**P2. "Sell most Minecraft and Cobblemon items" runs against three of the owner's own decisions, and it can be done
anyway.**

- The three decisions:
  - 2026-10-07: "money systems will be abused somehow" (`docs/STATE.md:149` item 5);
  - 2026-10-08: "the bank is the lever, not the content" (`data/bank.json:79`);
  - 2026-10-10: "AFK-farmable food must not pay for everything — cap it or exclude it" (`data/bank.json:25`).
- Those decisions took the bank from 122 entries down to **29** by my count of the file: 16 base entries plus 13 of
  ours (`data/bank.json:26-91`, `:171-185`). The file's own status line still says 41.
- The way through is that "most items sell" works only if the selling is capped per player. The bank cannot cap
  (verified from the jar, `data/bank.json:12`). The Produce Buyer can (`data/produce_buyer.json:7-8`), but it has
  **never run in game**: EXP-061 is NOT_EXECUTED (`experiments/EXP-061-produce-buyer/README.md:3`). The whole of
  section 2.2 rests on that experiment.

**P3. The Master Ball is not "hard" today: money buys it.**

- Northlight sells it for $27,000 (`data/markets.json:395`). That is 1.6 fight hours of leg 8 ($68,505 / 4 =
  $17,126, COMPUTED from `:27`) and 15% of the League's payout ($175,051, `:33`).
- A steady player has $299,465 saved after the League (RELAYED, `ECONOMY_SIM_2026-10-09.md` T5), which is 11 Master
  Balls.
- The netherite barter beside it (`data/direct_trades.json:105-115`) is the slow route. Today it is optional, because
  the money line is faster.

**P4. "Power per dollar" has a second reading.** It could also mean how much team strength a dollar buys. That
question is already answered by the income gate (`data/markets.json:72-85`), and this design keeps it. Here
"power" is the unit of value. Section 6, E11 suggests a field name that does not collide with the shelves'
`strand: "power"`.

---

## 1. The value spine

### 1.1 The rule

> **1 P = $100.** An item's worth is the share of an hour of play it costs, at the wage of the tier where it is first
> obtainable:
>
> **worth($) = count × W(tier) / rate(item)**, rounded to a whole dollar per sale unit, and **P = worth / 100**.
>
> - **rate** is the item's typical gathering rate per hour by hand. It is declared and ASSUMED until timed, exactly
>   as `data/bank.json` `rate_per_hour` already is.
> - **W(tier)** is the tier's typical hour, which the parity rule already bounds: a tier's hour is at most the fight
>   hour of the leg it opens in (`data/bank.json:249`).

This is not new arithmetic. It is the bank's existing derivation, "a unit price is the tier's target hour shared
over what one hour of that tool in that place yields" (`data/bank.json:243`), given a name and extended to every
item. **The minerals are already on the spine**, in P:

| Item | $ (MEASURED, `data/bank.json:172-184`) | P |
|---|---:|---:|
| coal | 4 | 0.04 |
| raw iron | 8 | 0.08 |
| raw gold | 20 | 0.20 |
| diamond | 120 | 1.2 |
| ancient debris | 200 | 2.0 |
| netherite ingot | 900 | 9.0 |

On that scale the Master Ball is 30 ingots, **270 P**.

Danger and progression gates are carried by the tier wage, not by per-item multipliers:

| Tier | Opens | W (the typical hour) |
|---|---|---:|
| early | leg 1, stone pickaxe | $620 |
| deep | leg 3, iron pickaxe, diamond depth | $1,350 |
| nether | badge 8, lava and a diamond pickaxe | $2,120 |

The wages are MEASURED (`data/bank.json:290-291`, and `ECONOMY_SIM` T11 for the nether hour). The nether gate is
MEASURED at `data/nether_gate.json:7`, but `data/bank.json:262` still says leg 7 (section 7). One rule and no
per-item tuning is what "consistent by construction" means here.

### 1.2 Where the spine breaks, and the guard for each

Each guard below is a mechanism that already exists, cited, or it is marked as an experiment.

| Break | Why it breaks a flat price | Guard | Evidence |
|---|---|---|---|
| **Renewable bulk** (cobble generator, tree, sand, dirt) | The rate is unbounded with tools (P1), and the bank's $1 unit floor is already above the spine | **Excluded from the bank.** Sold only as crates (64 cobble about $12) inside a per-player allowance | `data/bank.json:122` (whole-dollar unit); allowance `data/produce_buyer.json:37-48` (unrun, EXP-061) |
| **AFK farms** (crops, kelp, melon, fishing, berry and apricorn regrowth) | Cost to the player after building is zero | Excluded from the bank by the afk rule; crate-sold under the allowance | `data/bank.json:93-115`; independent check `tools/economy_audit.py:43-54` |
| **Mob grinders** | Vanilla grinders need vanilla mobs | Nearly closed: zombies, zombie villagers, piglins and iron golems are blacklisted. Only Cobblemon wild knockouts remain, and they are effort | `server/config/mods/mobsbegone-blacklist.json:35, 45, 79, 81`; `data/bank.json:97` |
| **Cobblemon drops** (Pasture Loot ranch at 15% a minute; wild-KO drops uncapped; relic coins at about $16,000 an hour, ASSUMED) | A pastured Pokemon is a free printer; a knockout drop is effort with no ceiling | Ore ids are blacklisted from Pasture Loot (ranch_ore); every other drop is crate-sold under the allowance; **no `cobblemon:` item in the bank** (new rule, R-V2-3) | `data/bank.json:49, :102, :298`; drop rates are EXP-061 step 9 |
| **Craft chains from free inputs** (apricorn into balls, crops into medicines and vitamins) | The output's price pays for free inputs | Same as above: crafted Cobblemon goods are crate-priced by the crafts rule (inputs + max(2, 1%)) and capped | `data/bank.json:105-107, :221` |
| **Villager trading** | Villagers are not blacklisted. Wandering traders sell sand, kelp and saplings for emeralds; emeralds drop from Thievul | Emerald is never bought (`data/bank.json:79`), so emerald-priced goods reach dollars only through a crate, inside the cap. **Unknown:** whether a player can obtain a breedable villager (zombie villagers are blacklisted, so not by curing). `economy_audit` does not model villager trades (`tools/economy_audit.py:100`) | EXPERIMENT (U5) |
| **Storage blocks, nuggets, authored dressing** | 9-for-1 conversions; selling dressing pays for tearing the world down | `never_buy` | `data/bank.json:140-170` |
| **A sale race or duplication** | Two clicks or a disconnect mid-sale might pay twice | None proven | EXPERIMENT (U6; `data/bank.json:313`) |

The **diminishing return** the owner asked about already exists in one shape: an allowance per badge leg that falls
as badges rise (`data/produce_buyer.json:37-48`). A within-leg taper (full price for the first N P, half after) is
expressible with the same scores, but nothing builds it, and section 2.2 does not need it.

**Sell only at certain markets** is possible for the capped buyer only: it stands where its `sites` put it. The bank
opens at every merchant in every town and cannot be restricted (`data/bank.json:7, :16`, verified from the jar).

### 1.3 Mechanism rung (principle 6)

| Rung | What it can do here | Why it is or is not enough |
|---|---|---|
| Cobblemon native | Nothing: there is no sell-back | `data/bank.json:8` |
| Addon (CobbleDollars bank, a config file) | Uncapped global sales at whole-dollar unit prices | **Used for the minerals.** It cannot cap, price by player or price below $1 a unit (`data/bank.json:12, :122`) |
| Datapack | Nothing sells for money | n/a |
| Functions/commands (dialogue NPC, `clear`, `cobbledollars give`) | Per-player caps, crate prices, any site | **Used for everything else.** The same mechanism as the Produce Buyer, generalised. Unproven: EXP-061 |
| Vanilla villager barter | Item-for-item at fixed counts | **Used for the top tier** (Northlight's Station Exchange, `data/direct_trades.json:45-53`). Rejected for caps: `maxUses` is per villager, not per player (`data/produce_buyer.json:8`) |
| Scripting, a companion, a mod | | Not proposed. Only if EXP-061 fails, and only after the failure is written down |

**No ADR yet.** The two-channel split constrains every future price and would deserve one, but its capped half rests
on an unrun experiment. Following this role's rule, the experiment comes first (Plan step 0), and an ADR follows
EXP-061's PASS.

---

## 2. The sell list

There are three channels. Every item lands in exactly one, by this test, applied in order:

1. **Never sold** if it is a prize, key, progression item, spawn-condition block, storage block, authored dressing,
   unreachable, or a top-tier output (2.3).
2. **Bank** (uncapped) only if it is dug by a player, its upper hour at its price is at most 1.5x the opening leg's
   fight hour (`data/bank.json:250`), it is not in the AFK set, it is not `cobblemon:`-namespaced, and no seller sells
   it at or below the price.
3. **Trading Post** (capped) for everything else that a player can make or find.

### 2.1 Bank: unchanged prices, a shorter list

**Keep** the 13 entries of ours at their prices (`data/bank.json:172-184`): coal, raw copper, copper ingot, raw iron,
iron ingot, lapis, raw gold, redstone, diamond, ancient debris, netherite scrap, netherite ingot and quartz. Each is
on the spine (1.1).

**Remove**, through `base_removed` or `never_buy` with this document as the named decision:

| Base entry (MEASURED, `base-pack/cobbleverse/config/cobbledollars/bank.json`) | Today | To | Why |
|---|---:|---|---|
| `lumymon:glacier_feather`, `thunder_feather`, `ember_feather` | $5,000 each | never | Quest keys. Shrew Station is their one source (`docs/STATE.md:146`); a sale turns a legendary's key into $15,000. ECONOMY_OVERHAUL's question 6, still open |
| `lumymon:soul_feather` | $30,000 | never | A key item, as above |
| `cobblemon:pp_max` | $3,500 | Trading Post | R-V2-3: no `cobblemon:` item in the bank. Its source and recipe are unread (U3) |
| `cobblemon:poke_cake`, `smoked_tail_curry`, `rage_candy_bar`, `lumiose_galette`, `casteliacone`, `vivichoke_dip`, `big_malasada`, `open_faced_sandwich`, `tasty_tail` | $30-120 | Trading Post, crafts rule | R-V2-3; dishes from farmed inputs |
| `minecraft:elytra`, `chorus_fruit` | $25,000 / $5 | dormant, unchanged | The End is shut; still the owner's `end_goods_dormant` |

The result is a bank of **13 entries plus 2 dormant ones**: the miner's endless outlet, which falls in real terms as
legs grow 17x. That is the intent stated in `ECONOMY_OVERHAUL.md` 2.1.

### 2.2 Trading Post: the Produce Buyer, generalised

The mechanism is unchanged from `data/produce_buyer.json:7`: count the item, take it, pay with
`$cobbledollars give @s $(amount)`, and re-read the balance.

**Three changes:**

1. **Crates at a fixed spine price.** Today's buyer pays a crate price that falls with badges ($40 to $10,
   `:40-45`). In v2 a crate always pays its worth, and **only the allowance falls**. "A crate of 64 cobble is always
   $12" is easier to learn than a sliding price.
2. **The allowance is counted in P per badge leg, per player.** Recommended: the same dollars as today, so the price
   curve does not move (E3):

   | Badges held | Allowance |
   |---|---:|
   | 0 | 16 P |
   | 1 | 9 P |
   | 2 | 5 P |
   | 3 | 2 P |
   | 4-7 | 1 P each |
   | 8 and later | 0 |

   That is 36 P, the $3,600 campaign cap (`data/produce_buyer.json:47`).
3. **A "sell everything I can" option.** It walks the categories, dearest crate first, until the allowance is spent.
   It needs a bounded take, `clear @s <item> <max>`, which reports how many it removed. That is vanilla behaviour,
   ASSUMED and untested here (U2). Today's crate-exact path stays as the fallback.

**The categories.** Crate worth uses W(early) = $620, except the nether row, which uses W(nether) = $2,120 and the
nether rate. **Every rate is an ESTIMATE until timed (U3).** The dollar figures are COMPUTED from the rates.

| Category | Crate | Items (examples; the generator lists them) | Rate/h (ESTIMATE) | Crate worth | P |
|---|---:|---|---:|---:|---:|
| Bulk stone and earth | 64 | cobblestone, cobbled deepslate, stone, andesite, diorite, granite, tuff, dirt, sand, red sand, gravel | 3,300 | $12 | 0.12 |
| Bulk nether | 64 | netherrack, blackstone, basalt, soul sand | 15,000 | $9 | 0.09 |
| Logs | 32 | every `#minecraft:logs` | 400 | $50 | 0.50 |
| Crops (as today) | 32 | wheat, carrot, potato, beetroot | 1,000 | $20 | 0.20 |
| Melon, kelp, cane, bamboo, cactus | 64 | melon slice, dried kelp, sugar cane, bamboo, cactus | 1,500-2,000 | $20-26 | 0.2-0.26 |
| Apricorns (as today) | 32 | `#cobblemon:apricorns` | 1,250 (`data/bank.json:292`, RELAYED) | $16 | 0.16 |
| Berries (as today) | 16 | `#cobblemon:berries` | 300 | $33 | 0.33 |
| Fish (as today) | 16 | cod, salmon, tropical, puffer, cooked | 60 | $165 | 1.65 |
| Meat (as today) | 16 | the eleven meats and rabbit stew (`data/produce_buyer.json:58`) | 60 KOs (`DROPS_AUDIT` 8.1, RELAYED) | $165 | 1.65 |
| Ranch goods (as today) | 16 | string, bone, feather, hide, leather, spider eye, gunpowder, slime ball, ender pearl | 60 | $165 | 1.65 |
| Nether wart (as today) | 32 | nether wart | 1,000 | $20 | 0.20 |
| Relic coins | 64 | `cobblemon:relic_coin` (pouches and sacks are never sold: 9-for-1) | about 2,000 (36 coins a Gimmighoul drop, `data/bank.json:49`) | $20 | 0.20 |
| Kitchen and pharmacy | 16 | Cobblemon dishes, potions, ethers, revives, vitamins, PP Up and Max, golden carrot, bread, cake and pie | crafts rule: inputs' crate value + max($2, 1%) a unit | generated | about 0.05-0.5 |
| Specimens (found Cobblemon items) | 1 | held and evolution items that wild Pokemon drop, not on any list in 2.3 | W(early) / (60 KO/h × the best drop chance in the species tables), capped at 2 P | generated | at most 2 |

Rules that keep the Trading Post honest:

- **No round trip.** A crate's unit worth is below every seller's unit price for that item. This is today's buyer
  arbitrage check (`tools/economy_audit.py:55-59`). Example: a potion sells for about $4 here against $200 at a Mart.
- **A single allowance across all categories,** as today (`data/produce_buyer.json:62`), so an AFK farm only fills
  the allowance faster. It never exceeds it.
- **The site is the owner's** (E8). Today the one site is Hollin's farm (`data/produce_buyer.json:15-23`).

### 2.3 Never sold, and why

| Class | Examples (from the files) | Why |
|---|---|---|
| Evolution stones | the ten stones | The faces restore every 600 s; the Exchange sells and never buys (`data/bank.json:141-150`) |
| Spawn-condition blocks | `data/spawn_blocks.json` | Paying strips encounters out of the world (`data/bank.json:124`) |
| Storage blocks, nuggets, charcoal, obsidian, dressing | iron/gold/diamond blocks, raw ore blocks, glowstone dust, crying obsidian | 9-for-1 conversions, endless obsidian, and the world's own dressing (`:151-169`) |
| Unreachable | elytra, dragon egg, shulker shell, nether star, heavy core, mace, trial key | `:231-238` |
| Prizes and keys | arena trophies (Choice Band, Leftovers, Choice Scarf, Life Orb, Ability Patch, Gold Bottle Cap), first-win TMs, badges, the Beast Ball, feathers, Kubfu's scrolls, memories, Tower Ash, sigils, Mega stones | "A prize you can buy is not a prize" (`docs/STATE.md:151`); keys gate content |
| Progression items | Exp. Candies, Rare Candy, IV candies, Lucky Egg | Dungeon-exclusive (`docs/STATE.md:160`); a sale price would put a dollar value on the dungeons, and `ECONOMY_SIM` T9 rests on there being none |
| The top tier's outputs | Master Ball, Ancient Origin Ball, the barter outputs (2.4) | Sold back, they would become money; the bank already never buys a reward (`data/bank.json:132`) |
| TMs | all | Permanent unlocks, gated by badge (`docs/STATE.md:151, :160`) |

### 2.4 The top tier

The **"best items"**, named from the files:

- **The Master Ball** (`data/markets.json:395`; `data/direct_trades.json:105`).
- **The Ability Capsule** (`data/markets.json:394`).
- **Northlight's held items:** Focus Sash, Expert Belt, Eviolite and Assault Vest (`:402-405`).
- **Choice Specs and the Destiny Knot**, barter-only today (`data/direct_trades.json:116-137`).
- **Dungeon-only:** Rare Candy and IV candies.
- **Prizes the owner keeps as prizes:** the Ability Patch and the arena trophies (E6).

**The rule v2 proposes: a top-tier item has no dollar line.** It is bought with materials that dollars cannot buy.

The barterer holds at most 8 lines (`data/direct_trades.json:74`). The set below is exactly 8: the 3 approved
lines, the 4 held items, and the Capsule.

| Item | Barter (cost A + cost B) | Bank value (COMPUTED) | Status |
|---|---|---:|---|
| Master Ball | 1 netherite block + 21 netherite ingots (30 ingots) | $27,000 | approved today; the **money line goes** |
| Choice Specs | 1 diamond block + 4 ingots | $4,680 | today, unchanged |
| Destiny Knot | 1 diamond block + 3 ingots | $3,780 | today, unchanged |
| Assault Vest | 1 diamond block + 4 ingots, **or** 5 ingots (E5) | $4,680 / $4,500 | today a $4,500 money line |
| Focus Sash, Expert Belt, Eviolite | 1 diamond block + 3 ingots, or 4 ingots | $3,780 / $3,600 | today $3,600 money lines |
| Ability Capsule | 1 diamond block + 10 ingots | $10,080 (1.008 of today's $10,000) | today a $10,000 money line |

Rows 4 and 5 assume the diamond-block form. The vanilla barter needs cost A at count 1 and two different inputs
(`data/direct_trades.json:71-72`), so a block plus ingots is the form that fits. Every row lies inside the existing
1.00-1.10 band (`:77-78`), so the pricing rule does not change.

**The evolution items stay money lines** ($2,700 each, `data/markets.json:396-401`). They are reachability items
("every Cobblemon item reachable", `docs/STATE.md:191`), not power, and a money route keeps them reachable without
the Nether.

---

## 3. The Master Ball and the best items: route, hours, and why there is no shortcut

### 3.1 The route (bands 5-6: badge 8 and after the Champion)

1. **Gate.** The Nether opens at `gym8_cleared` (`data/nether_gate.json:7`), so no player has debris before band 5.
2. **Dig.** Ancient debris, at 10 an hour with a pickaxe and 30 an hour by bed or TNT mining (`data/bank.json:181`,
   ASSUMED). Smelt it into scrap.
3. **Gold.** Four gold ingots per netherite ingot. Gold is AFK-farmable through a Meowth ranch
   (`data/bank.json:217`), or mined at 10 raw gold an hour (`:178`, ASSUMED).
4. **Craft and trade.** Craft the ingots, and a block from 9 of them. Trade them at Northlight's Station Exchange,
   inside the Mart (`data/direct_trades.json:33-44`).
5. **One free Master Ball per player:** Giovanni's first win (`data/progression.json:5143`).

### 3.2 Hours per item

COMPUTED from the ASSUMED rates. Diamonds are at the deep tier's 4 an hour (`data/bank.json:180`). Gold counts zero
hours with a ranch, and the gold row shows the extra hours without one.

| Item | Debris | Diamonds | Hours, pickaxe (10 debris/h) | Hours, bed or TNT (30/h) | Extra hours if gold is mined |
|---|---:|---:|---:|---:|---:|
| **Master Ball** | 120 | 0 | **12.0** | **4.0** | +12.0 |
| Ability Capsule | 40 | 9 | 6.3 | 3.6 | +4.0 |
| Choice Specs, Assault Vest (block form) | 16 | 9 | 3.9 | 2.8 | +1.6 |
| Destiny Knot, Focus Sash, Expert Belt, Eviolite (block form) | 12 | 9 | 3.5 | 2.7 | +1.2 |

For contrast, by money today:

- The $27,000 Master Ball is **1.6 fight hours** at leg 8 and 0.15 of the League (COMPUTED, P3).
- The $3,600 held items are **0.2 fight hours** each.

The pickaxe route is 7.5x slower than the money line it replaces. That is the owner's "grindable but not easy". The
count itself (30 ingots) is E4.

The supply is finite. About 11,000 debris server-wide (RELAYED, `ECONOMY_OVERHAUL.md` 3.4, ASSUMED there) is about
90 Master Balls for the server's whole life (COMPUTED). The border and the density are unmeasured (U9).

### 3.3 Why the sell list cannot shortcut it

- **Dollars buy no top-tier input.** No seller sells debris, scrap, ingots, diamonds or raw ore (rule B1,
  `ECONOMY_OVERHAUL.md` 1.4). Today the audit only REPORTS B1 (`tools/economy_audit.py:74`); v2 makes it a FAILURE
  for any input of a top-tier barter (5.2, A3).
- **The top-tier outputs have no dollar line** (2.4), and the bank buys none back (`data/bank.json:132`).
- **The Trading Post pays dollars only, and is capped.** Even uncapped, dollars lead nowhere upstream.
- **The bank does buy ingots ($900), so Nether hours can become money.** It cannot go the other way. At the upper
  rate this is $6,120 an hour against leg 8's $17,126 fight hour (`ECONOMY_SIM` T11, RELAYED), under parity.
- **Three remaining leaks, all small or deliberate:**
  - Co-op pooling: friends hand each other debris (E10).
  - The Challenge voucher's kits grant 18 netherite scrap across legs 7-9, about 4.5 ingots
    (`data/challenge_mode.json:158-160`, COMPUTED).
  - Bastion and chest netherite: finite, shared, and found rather than farmed.

---

## 4. Reconciliation: every price and income source

Income sources:

| Source | Today (cited) | v2 |
|---|---|---|
| Trainer battles (NPC) | Expected $0.28125·S² a win, `cobbleDollarsIncomeMultiplier` 1.25 (`data/markets.json:20`; `modpack/config/cobbledollars/common.json:4`) | unchanged |
| Wild battles | $0 (`common.json:3`) | unchanged |
| Rematches of placed trainers | Blocked for a badge holder by the hold-off (`tools/route_trainers.py:508-532`) | unchanged |
| **Ambient RCT trainers** (need the trainer card) | **Uncapped and unmodelled.** A spawn try every 600-2,400 ticks at chance 0.55, up to 6 per player (`modpack/config/rctmod-server.toml:6, 21, 31, 60`); excluded from the income model (`data/markets.json:24`) | unchanged; **measure** (U4, E12) |
| Arena | First clears pay once; repeats $200 × 3 a day (`data/arena_fights.json:256`) | unchanged |
| Dungeon bosses | $0 net by the clawback, built but not run (`ECONOMY_SIM` design) | unchanged |
| Bank | 29 entries | 13 + 2 dormant (2.1) |
| Produce Buyer, becoming the Trading Post | 8 crate kinds; $40/30/25/20/10/0 a crate; campaign $3,600 (`data/produce_buyer.json:37-61`) | about 14 categories at fixed spine prices; allowance 16/9/5/2/1×4/0 P = 36 P = $3,600 (E3) |
| Research station feathers | The three bird feathers sell for $15,000 a player through the base bank (the soul feather's $30,000 line has no established source here) | not sellable |
| Challenge voucher | $23,748 total, $4,000 at Oak (`data/challenge_mode.json:168-173`) | unchanged (its bar is the cheapest income-gate line, $4,100, unchanged) |

Prices:

| Line | Today | v2 |
|---|---:|---|
| Master Ball, Northlight money line (`data/markets.json:395`) | $27,000 | **removed** to `superseded_stock`; the barter stays at 30 ingots (E4) |
| Focus Sash, Expert Belt, Eviolite (`:402-404`) | $3,600 each | barter lines (2.4) |
| Assault Vest (`:405`) | $4,500 | barter line |
| Ability Capsule (`:394`) | $10,000 | barter, 1 diamond block + 10 ingots |
| Choice Specs, Destiny Knot | barter | unchanged |
| Evolution items at Northlight and Fossick | $2,160-3,000 | unchanged |
| The 33-41 held income-gate TM and memory lines (`:409-419`; `docs/STATE.md:25, :151`) | held by the ball floor (`tools/bank.py:489-511`) | **The ball floor loses its anchor** when the Master Ball has no money line. Release at the income-gate price, the owner's own 2026-10-09 rule, or keep holding (E7) |
| Critical-path convenience lines (`curve_scale`) | priced to the 0.65-0.70 band | unchanged if E3 keeps $3,600; re-priced by `markets.py prices --write` if not |
| Trainer card at Pallet (`data/traders.json:659`) | $500 | price unchanged; **Oak hands one over** (E9) |
| Mart basics, Beast Ball ($5,000), training services ($500 / $17,200 / $17,200 a stat), blackout ($600) | as cited | unchanged |

**Early prices against early income.** This is the brief's check, and the one an earlier wave missed.

- **Income before the first Route 1 win is $0.**
  - Wild pay is off (`common.json:3`).
  - No starting balance is configured; whether CobbleDollars gives one is U-8, unverified
    (`PROGRESSION_LADDER.md:628`).
  - The Produce Buyer is neither installed nor run (`data/markets.json:66`; EXP-061).
- **Pallet's own shelf is affordable once anything pays:** backpack $100, sleeping bag $50 (`data/markets.json:137-138`).
- **The trainer card is not.** At $500 it is the dearest thing in Pallet, and its stated reason assumes wild pay at
  0.5 (`data/traders.json:665`); both premises are now false.
  - Route 1's four trainers pay an expected $14, $101, $205 and $648 (COMPUTED from S = 7, 19, 27, 48,
    `data/markets.json:42`), so the card needs about all four and a walk back.
  - Hence E9: Oak hands the card over at the lab.
- **The Trading Post's 16 P at 0 badges is the only non-fight money in leg 1,** and it is 670 blocks from Pallet
  (`data/produce_buyer.json:19`).

---

## 5. What a build would touch

### 5.1 Files

| Unit | Files | Owner (agent) | Rough size |
|---|---|---|---|
| B1 Bank | `data/bank.json`: `base_removed` for the 4 feathers, 9 dishes and `pp_max`; `never_buy` for the feathers; fix the stale `effort_model.label` (`:241`) and `tiers.nether.opens_leg` 7 → 8 (`:262`). `tools/bank.py`: rule R-V2-3 (no `cobblemon:` id), rule R-V2-1 (the unit floor: upper rate × $1 ≤ 1.5 × the fight hour, else not bankable), ball floor retired (`:489-511`). Then `modpack/config/cobbledollars/bank.json` by `bank.py write` | `datapack-content-dev` | small, about 2M |
| B2 Trading Post | `data/produce_buyer.json`: categories, `rate_per_hour` and tier per category, the allowance in P, the crafts rule for kitchen and pharmacy, specimens read from the species tables, sites. `tools/produce_buyer.py`: per-item sell functions with a bounded take, sell-all, the P allowance. A reapply step (R18PB exists) | `minecraft-systems-dev` | medium, about 4M |
| B3 Shelves and barter | `data/markets.json`: the Master Ball, Capsule and four held lines to `superseded_stock`, the held TM lines per E7, `curve_rule.produce_allowance` per E3. `data/direct_trades.json`: 5 new barter lines (8 in all) | `datapack-content-dev` | small, about 2M |
| B4 Audit | `tools/economy_audit.py` (5.2), `tools/economy_sim.py` (Trading Post allowance, Master Ball hours), tests, a `data/system_contracts.json` entry for "no dollar path to a top-tier input" | `test-author` (never the builders above) | medium, about 4M |
| B5 Trainer card | Oak's dialogue gives `rctmod:trainer_card` once (`data/dialogue.json`, the existing grant shape) | `datapack-content-dev` | small |

**Total: about 12-16M across four or five units** (ESTIMATE, from CLAUDE.md's 4M per builder; the small units
cost less). Plus the main session's integration, prepare, install and staging read-back.

### 5.2 How the arbitrage audit must change

`tools/economy_audit.py` already hunts loops across the bank, every seller, the recipes and the barter edges
(`:20-24`, `:60-83`). It needs six changes. Each is derived from data, not the builder's helpers.

- **A1 SPINE.** Recompute every bank and crate price from the declared rate and the tier wage. The wage comes from
  `income_basis.leg_by_badge` ÷ `max_leg_hours`, read independently, not through `bank.py`. FAILURE beyond
  whole-dollar rounding. **Mutate the generator** (a crate's count or a tier's wage inside `produce_buyer.py`), not
  the record: CLAUDE.md "How to prove an audit is independent".
- **A2 UNIT FLOOR.** FAILURE for a bank entry whose `rate_per_hour_upper` (or `rate_per_hour`) × $1 exceeds
  1.5 × the opening fight hour. This catches any bulk block that drifts into the bank.
- **A3 TOP TIER.** A reachability search from dollars, across every seller, every recipe and every barter edge, to
  each top-tier output and each of its inputs (debris, scrap, ingot, diamond and their blocks). FAILURE if any path
  exists. This promotes B1 from REPORT to FAILURE for these lines.
- **A4 TRADING POST.** The existing buyer check, extended to every category: no seller below the crate's unit worth;
  one allowance; the reset only on a badge change; and the sell-all order (take before pay, pay once, re-read).
- **A5 NAMESPACE.** FAILURE for any `cobblemon:` id in the installed bank.
- **A6 VILLAGERS.** A stated table of the vanilla wandering trader's offers. In 1.21.1 these live in code, not JSON:
  ASSUMED, to be confirmed by reading the jar. Emerald-priced edges are REPORTED as "outside money" while emerald is
  never bought, and FAILURE if one reaches a bank item.

The "0 arbitrage" result today is RELAYED (`docs/STATE.md:139`; `ECONOMY_SIM` "No loop prints money"). I could not
run it. A2, A3 and A5 are new properties, so a clean run of the old audit says nothing about them.

---

## 6. Questions for the owner

- **E1. The unit.** Keep 1 P = $100, but price 64 cobble at its spine worth, about $12 (0.12 P), rather than 1 P?
  At 1 P a stack, cobble fills any allowance in minutes and every other category becomes pointless. **Recommend:
  spine worth.**
- **E2. Two ways to sell.** "Most items" sell only through the capped Trading Post, and the uncapped bank keeps only
  dug minerals and Nether materials? **Recommend: yes.** It is the only form the bank's verified mechanics allow
  (P1, P2).
- **E3. The allowance.** Keep today's dollars (16 / 9 / 5 / 2 / 1×4 / 0 P, $3,600 a campaign) with fixed crate
  prices, or enlarge it? A larger allowance re-prices the critical-path shelf up through `curve_scale`.
  **Recommend: keep $3,600 now, and revisit after timed rates (U3).**
- **E4. The Master Ball.** Remove the $27,000 money line and make it barter-only at 30 ingots (12 h by pickaxe, 4 h by
  bed or TNT, plus gold), with Giovanni's free one? Or use 20 or 45 ingots? **Recommend: remove the money line and
  keep 30.**
- **E5. The other best items.** Move Focus Sash, Expert Belt, Eviolite, Assault Vest and the Ability Capsule from money
  to barter (2.4), and leave the evolution items as money lines? **Recommend: yes.**
- **E6. The arena trophies** (Ability Patch, Gold Bottle Cap, Life Orb, Choice Band, Choice Scarf, Leftovers). Your
  new words say "the best items are grindable"; 2026-10-09 said "a prize you can buy is not a prize". **Recommend:
  they stay prizes.** The grindable top tier is the barter set above.
- **E7. The held TM lines.** With no Master Ball money line, the ball floor that holds 33-41 TM and memory lines has
  nothing to compare against. Release them at their income-gate prices ($35,000-$134,400), your 2026-10-09 rule, or
  keep them held? **Recommend: release.** Their price is already the gate.
- **E8. Where the Trading Post stands.** Hollin's farm only (today), or also Fossick, Northlight and each gym town?
  More sites cost plaza cells and a reapply step. **Recommend: Hollin's farm plus one in Misty's town** (2,770 blocks
  north, `data/produce_buyer.json:23`). The allowance is per player, so extra sites add reach, never money.
- **E9. The first hour.** A new player has $0 and the trainer card costs $500. Should Oak hand the card over at the
  lab? **Recommend: yes.** The card is a licence, not a purchase, and its own price note rests on wild pay that you
  turned off.
- **E10. Co-op pooling.** Two friends pooling debris halve the hours for one Master Ball. Fine? **Recommend: yes.** It
  is a co-op game, and the server-wide debris supply is the real limit.
- **E11. Naming.** In data, call the unit field `worth_p` rather than `power`, so it cannot be confused with the
  shelves' `strand: "power"`? **Recommend: yes.** Call it "power" in player-facing text if you like the word.
- **E12. Ambient RCT trainers** pay without a cap once a player holds the card. Measure their dollars an hour by band
  before deciding? **Recommend: measure first (U4).** If they beat the fight hour, cap them the way the arena's
  repeats are capped.

---

## 7. Inconsistencies found in the current economy

1. **Staging runs the old bank.** The server's old `cobbledollars/bank.json` was restored by hand, and `install_check`
   reports 1 problem "by design" (`docs/STATE.md:21, :24`). So the AFK foods, relic coins and medicine buy-backs that
   data removed are live there.
2. **The price curve counts money nobody pays.** The curve's leg-1 denominator includes $1,600 of produce allowance,
   but the Produce Buyer is not installed or run (`data/markets.json:66`). That is 40% of leg 1's trainer income
   (COMPUTED).
3. **`data/bank.json` is stale in two places.**
   - `effort_model.label` still says the leg incomes are model B, relayed (`:241`).
   - `tiers.nether.opens_leg` is 7 against the badge-8 gate (`:262`; `data/nether_gate.json:7`).

   `ECONOMY_SIM` reported both on 2026-10-09, and both are still there.
4. **Two status lines disagree with their own data.** `data/bank.json`'s status says 41 entries, and the file computes
   to 29. `docs/STATE.md:154` still says EV and IV training cost about $50,000 in all, against $17,200 an EV spread and
   $17,200 an IV stat (`data/training_services.json:54`).
5. **The trainer card's price reasoning is stale** (`data/traders.json:665`). It assumes wild pay at multiplier 0.5,
   but wild pay is off and the multiplier is 1.25 (`common.json:3-4`). Pallet has no income before Route 1.
6. **The base bank still buys the four LumyMon feathers** ($5,000-30,000), which the station hands out as quest keys.
7. **The $27,000 Master Ball is cheap, not hard.** It costs 1.6 fight hours at leg 8, and a steady player can afford
   11 of them after the League (P3).
8. **`MATERIAL_EXCHANGE.md` section 5 is stale.** Its hours table still uses model B leg incomes.

---

## Plan

Each step is one experiment or one content task.

0. **[main session, staging, under the lock]** Run EXP-061 and the bank's own experiment (`data/bank.json:305`,
   steps 1-10), and add U2 (the bounded `clear`) and U7 (the bank refusing a stack with changed components).
   `qa-reviewer` grades the result. **Everything in 2.2 waits on this.**
1. **[main session]** U3: time an hour each of cobble, logs, crops, fish, debris (pickaxe, and bed or TNT) and raw
   gold. U4: an hour of ambient RCT fights at two bands with the card. U8: the starting balance. Record them in
   `experiments/`.
2. **`content-architect`:** an ADR proposal for the two-channel economy, citing the step 0 PASS.
3. **`datapack-content-dev`:** B1 (bank), then B3 (shelves and barter), on the owner's E2, E4, E5 and E7.
4. **`minecraft-systems-dev`:** B2 (Trading Post), using step 1's rates.
5. **`test-author`:** B4 (A1-A6, the sim, the contract).
6. **`datapack-content-dev`:** B5 (Oak's card), on E9.
7. **[main session]** Integration: `validate_data`, `economy_audit`, `markets_audit`, `town_squares_audit`, the
   contracts suite, then prepare, install, the R17M, R18DT and R18PB re-runs, and a read-back (the merchants' offers,
   the barterer's 8 lines, the Trading Post seat).

## Unknowns (experiment candidates)

- **U1** (EXP-061): count-and-clear, the give, the allowance reset.
- **U2:** `clear @s <item> <max>` returns the number removed.
- **U3:** every gathering rate above.
- **U4:** ambient RCT trainer income per hour.
- **U5:** can a player obtain a breedable villager; how often do wandering traders spawn here?
- **U6:** a bank sale race or duplication.
- **U7:** the bank refuses a stack with changed components (bank experiment step 7).
- **U8:** the starting balance (EXP-F).
- **U9:** the Nether border and debris density.
- **U10:** Pasture Loot's real drop rates (EXP-061 step 9).

None of section 2.2 or 3.2's hours is a fact until U1 and U3 have run.
