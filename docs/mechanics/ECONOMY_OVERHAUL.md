# Economy overhaul: trainer money pays for the fights, materials pay for power

**Status: DESIGN, unit ECON-DESIGN (overnight 2026-10-10), `trainer-balance-designer`. Nothing here is built or run
in game.** Builders work from the BUILD LIST (section 9). The owner's direction is in `docs/STATE.md` "What is decided":
"The economy drives Minecraft play", "Challenge mode is not concerned with Minecraft" and "Paid training services,
OPTIONAL". The overnight brief is `docs/HANDOVER_SESSION.md` section 3, item 4.

**Labels used on every number.**

- **MEASURED:** read from a file in this checkout, with the file cited.
- **COMPUTED:** my own arithmetic on cited inputs. Nothing was run, because this agent has no shell. Unit U0 must
  reproduce every COMPUTED figure with a tool before anything is priced on it.
- **RELAYED:** taken from a named document and not re-measured.
- **ASSUMED:** inferred, with the reason given.

---

## 0. Premises checked first (seven are wrong or narrower than they look)

**P1. Income model B is contradicted by the jar.** Research unit LEVELSET read CobbleDollars' `battleVictory` in the
jar (`docs/research/notes/paid-services-and-npc-payouts.md` B2; VERIFIED there from bytecode, RELAYED here). It pays:

```
B = 5·S·S/50 = S²/10, where S is the losing team's level sum
credit = 1.25 × (B + random(B/2 .. 2B))
```

So the expected credit is 1.25 × 2.25 × S²/10 = **0.28125·S²** (COMPUTED; the uniform draw is ASSUMED by the note).
Payment is quadratic in team size, not linear. Section 1 recomputes income from the real rosters.

One caveat about the note's corroboration. The two measured payouts, $732 and $600, were taken on 2026-09-24 against
the UPSTREAM `kanto_brock`, at the base multiplier of 0.5 (`docs/research/INCOME_MEASUREMENT.md:44, 61-69`, MEASURED).
The note compares them against OUR Brock (level sum 56) at 1.25. The formula is consistent with the measurements if
upstream Brock's level sum is 70-99 (COMPUTED), which nobody has checked. So the formula is VERIFIED from bytecode,
but its corroboration is weaker than the note states.

**P2. CobbleDollars also pays for WILD battles under the same formula.** `earnCobbleDollarsFromWildPokemon: true`
(the note's B2 config bullet), and `battleVictory` applies the same arithmetic to a WILD loser.

- A single level-L wild Pokemon pays about 0.28·L² (COMPUTED): $112 at level 20 and $703 at level 50.
- At an ASSUMED one wild battle a minute, that is about $6,700 an hour in leg 1 and $42,000 an hour at cap 50.
  Leg 1's entire trainer income is $4,033 (section 1).
- **This is the largest money tap in the game, and the level cap does not touch it**, because rctmod clamps EXP, not
  money.

Wild battles are ordinary Pokemon play, not AFK, but they make every price an hour of grinding. Every number below
assumes the wild payout is **OFF**. That is owner question 1, and it costs one key in a `modpack/config/` overlay.

**P3. "A declining price" cannot be expressed in the CobbleDollars bank.** The bank is one server-wide list with no
player, time or progress key (`data/bank.json` `mechanism.verified`, read from the jar, MEASURED). A function also
cannot rewrite a config file. So the decline moves to a functions-rung buyer that reads per-player flags (section 2.2).

**P4. "A refillable cave instead of finite worldgen ore" should read "as well as".** Removing the pre-exported world's
ore would be a world-wide write over every chunk. The worldgen ore stays where it is, and the cave becomes the
renewable source (section 3).

**P5. The $100k voucher was sized on model B and on the full service budget.** Under the jar's formula, a Challenge
player out-earns a Normal player by about **$145,000** by Victory Road, because Challenge teams are larger and pay
quadratically (section 4). The money gap that remains is small. What the voucher really has to cover is the
Minecraft-only inputs.

**P6. Two owner decisions now pull against the new direction.**

- **(a)** Barter is "an alternative path, not a bypass", priced at 1.00-1.05 of the counter
  (`data/direct_trades.json` `pricing.rule`, 2026-10-08).
- **(b)** "Players trade at Northlight's counter. One place."

Power from materials makes the barter the intended route, and the answers for gyms 2-6 are needed long before
Northlight. This design proposes the inversion and the extra sites. The owner decides (questions 2 and 3).

**P7. The arena pays twice.** Our purse comes from `tools/arena_runtime.py:720-754` (MEASURED), and CobbleDollars
pays automatically as well: about $5,300-10,600 for a rank-1 win, up to about $128,000 on the streak (RELAYED, note
B2). Turning off `earnCobbleDollarsFromNPC` would also end all trainer income, so the arena needs its own
neutralisation (section 6).

---

## 1. The money model by badge

### 1.1 Trainer income from the jar's formula and the real rosters

The level sums S were read by grep from `data/trainers.json` (the first team copy of each record; the junior records
are the 26 that follow `route_09_trainer_10`) and from `data/mansion_guardians.json`. Income = Σ 0.28125·S² (COMPUTED,
expected value, multiplier 1.25). Model B is RELAYED from `data/markets.json` `income_basis`.

| Leg (to badge) | Battles: S values (Normal) | Leg income | Cumulative | Model B cumulative | Ratio |
|---|---|---:|---:|---:|---:|
| 1 | route 1: 7, 19, 27, 48; mansion: 16, 20, 24, 27, 46; juniors: 33, 35, 37; Brock 56 | 4,033 | **4,033** | 9,475 | 0.43 |
| 2 | 18, 39, 41 (shore), 63; juniors 43, 45; Misty 70 | 4,576 | **8,609** | 17,023 | 0.51 |
| 3 | 21, 45, 47, 51, 78; juniors 53, 55, 57; Surge 114 | 9,967 | **18,576** | 28,655 | 0.65 |
| 4 | 26, 53, 59, 87, 63, 96; juniors 63, 65, 65; Erika 135 | 16,415 | **34,991** | 45,615 | 0.77 |
| 5 | 32, 67, 69, 105; juniors 73, 75, 77; Koga 195 | 21,433 | **56,424** | 60,905 | 0.93 |
| 6 | 37, 75, 79, 120, 126; juniors 83, 85, 87, 87; Sabrina 217 | 33,708 | **90,132** | 82,275 | 1.10 |
| 7 | 41, 83, 87, 132, 93, 141; juniors 93, 95, 97, 97; Blaine 242 | 44,198 | **134,330** | 109,038 | 1.23 |
| 8 | 46, 91, 95, 144, 99, 153, 156; juniors 103, 105, 105, 107*; Giovanni 319 | 68,505 | **202,835** | 145,078 | 1.40 |
| Victory Road | 113, 113, 115 ×4, 117, 117, 118, 236 | 49,341 | 252,176 | 186,705 | 1.35 |
| League | 351 ×4, Blue 360 | 175,051 | 427,227 | 244,343 | 1.75 |

\* The last gym-8 junior was cut off in the grep output. It is ASSUMED to be (53, 54), from the pattern of the other
three.

**Result: early income is half of model B, and late income is 1.4x model B.**

### 1.2 How far the 0.65-0.70 curve moves

Take PROGRESSION_LADDER rev 2's cumulative shelf (section 1.3: 6,050 / 11,250 / 19,750 / 27,650 / 41,650 / 56,150 /
73,950 / 99,750, RELAYED) and divide by the new income. The ratio becomes **1.50 at badge 1, then 1.31, 1.06, 0.79,
0.74, 0.62, 0.55, and 0.49 at badge 8** (COMPUTED).

So the flat 0.61-0.69 line turns into a slope: the early shelf cannot be afforded from fights, and late money piles up.

The built counters differ from rev 2 (TIERED_GOODS moved lines), so U0 recomputes this against `data/markets.json`
with `tools/markets.py curve`. The slope will hold, because it comes from S², not from any one price.

That slope is the owner's direction already shaped by the jar:

- **Early:** fights pay for fights, and farming and mining pay for the backpack ("farm products pay the early game").
- **Late:** fights produce surplus money, so power cannot be priced in money at all. It has to be materials (section
  1.4).

### 1.3 What trainer income covers, leg by leg (Normal mode)

These assumptions are carried from `data/markets.json` and `PROGRESSION_LADDER.md`:

- **Fight costs: $2,500 a leg** (ASSUMED). That is the Mart allowance of $1,600 (ladder A-5, ASSUMED), one blackout
  at $600 (`data/blackout.json` `charge_rule`, MEASURED) and ferries at about $300.
- **Convenience strand:** ladder rev 2's per-town figures (RELAYED), with the crafting upgrade left as a stretch.

| Leg | Income | Fights | Convenience | Leg balance | Cumulative | Covered by |
|---|---:|---:|---:|---:|---:|---|
| 1 | 4,033 | 2,500 | 6,050 | −4,517 | −4,517 | produce allowance $1,600 + about 2 h of early mining |
| 2 | 4,576 | 2,500 | 2,700 | −624 | −5,141 | produce $900 + about 1 h of mining |
| 3 | 9,967 | 2,500 | 8,500 | −1,033 | −6,174 | produce $500 + about 1 h of deep mining or cave |
| 4 | 16,415 | 2,500 | 6,500 | +7,415 | +1,241 | fights |
| 5 | 21,433 | 2,500 | 6,500 + bracelet 7,500 | +4,933 | +6,174 | fights |
| 6 | 33,708 | 2,500 | 14,500 | +16,708 | +22,882 | fights |
| 7 | 44,198 | 2,500 | 12,500 | +29,198 | +52,080 | fights (surplus) |
| 8 | 68,505 | 2,500 | 17,000 | +49,005 | +101,085 | fights (surplus) |

**The rule this design adopts:**

> **Trainer income covers the fights at every badge.** Fights are the Mart, healing, ferries and the blackout.
>
> **The convenience strand is paid by trainer income plus the farm and mine.** Early on it is mostly farm and mine;
> late it is all fights.
>
> **Power is never priced in money a fighter can reach.** Power means TMs, held items, Mega stones and the Mega
> answers. It comes from materials (barter), and its dollar line is income-gated.

The late surplus (about $100k at badge 8) is soaked by these sinks:

- re-pricing the late convenience strand up to the curve (U5);
- the optional services (section 5);
- the Master Ball ($27,000, `data/markets.json` northlight, MEASURED);
- income-gated dollar lines for anyone who prefers paying to digging.

### 1.4 Each gym's answer kit, priced in materials

A kit is **one counter-type TM** plus **one type-boosting held item** for the next gym. The specific moves wait on the
per-gym answer check owed when the owner's team rewrite lands (STATE item 13). Ids already seen in `data/markets.json`
lines 297-363 (MEASURED) are named as examples. Any other TMCraft id must be verified in `tmcraft-1.4.19+1.8.0.jar`.

**Material prices** come from `data/bank.json` `buys` (MEASURED): raw iron $8, coal $4, lapis $4, raw gold $20,
redstone $2, diamond $120, netherite scrap $202, quartz $2. The gathering hours are RELAYED from `data/bank.json`
`income_estimate`: early $620/h, deep $1,350/h, and late about $2,000/h (10 debris an hour, ASSUMED).

| Leg (gym) | Answer types | TM recipe (bank value) | Held-item recipe (bank value) | Kit value | Minecraft hours (ASSUMED) |
|---|---|---|---|---:|---:|
| 2 (Misty, water) | Grass / Electric (e.g. `tm_megadrain`) | 48 raw iron + 32 coal + 16 lapis ($576) | 24 raw iron + 24 coal ($288) | 864 | 1.4 |
| 3 (Surge, electric) | Ground (id to verify) | as leg 2 ($576) | 1 diamond + 24 raw iron + 16 redstone ($344) | 920 | 0.7 |
| 4 (Erika, grass) | Fire / Flying | 2 diamonds + 32 raw iron + 4 raw gold + 32 lapis ($704) | as leg 3 ($344) | 1,048 | 0.8 |
| 5 (Koga, poison) | Ground / Psychic | as leg 4 | as leg 3 | 1,048 | 0.8 |
| 6 (Sabrina, psychic) | Dark / Bug / Ghost | as leg 4 | as leg 3, plus 2 Mega stones (2 raw stones + 1 diamond each at the Cutters, built: `SOUTHERN_RIFT_MEGA.md` 13.1) | 1,288 | 1.0 |
| 7 (Blaine, fire) | Water / Rock (e.g. `tm_scald`, `tm_rockslide`) | 2 diamonds + 4 netherite scrap + 32 raw iron ($1,304) | 1 diamond + 2 netherite scrap + 16 quartz ($556) | 1,860 | 0.9 |
| 8 (Giovanni, ground) | Water / Grass / Ice (e.g. `tm_gigadrain`) | as leg 7 | as leg 7 | 1,860 | 0.9 |
| League | mixed | as leg 7 | as leg 7 | 1,860 | 0.9 |
| **Total** | | | | **10,748** | **about 7.4 h** |

Notes on the kits:

- **The raw Mega stones are fought for** (farm Megas, 15% a drop, `SOUTHERN_RIFT_MEGA.md:701`, RELAYED). That is
  Pokemon play, not Minecraft.
- **The Mega farms are HELD** pending the owner's Z2 / gym-6 decision (same document, line 706).
- **The Mega Bracelet stays a dollar line at $7,500.** It is a key item, on Koga's counter (`data/markets.json:193`,
  MEASURED).
- **Every recipe must carry at least one non-purchasable input (rule B1).** Coal is sold at Cinderlee, so raw iron,
  raw gold, diamond or scrap is the binding input in each recipe. `tools/economy_audit.py` decides.
- **The hours scale linearly with the recipes.** About one hour of Minecraft a leg is the baseline; the owner sets
  the dial (question 8).

---

## 2. The bank's new schedule

### 2.1 What the bank keeps buying (flat prices)

Ore, gems and the Nether tier keep their prices. Each of them needs a player at the pick, so none can be AFK-farmed:

- the minerals: coal, copper, iron, lapis, gold, redstone, diamond and amethyst *(but see below)*;
- `ancient_debris` $200, `netherite_scrap` $202, `netherite_ingot` $900 and `quartz` $2.

All of these are MEASURED from `data/bank.json` `buys`. A flat price falls in real terms as the legs grow 17x
(4,033 to 68,505, COMPUTED), so late-game mining for money becomes pointless, as intended. Late mining is for
materials.

`minecraft:amethyst_shard` leaves the bank, because geode harvesters are AFK (`tools/economy_audit.py:173`, MEASURED).

### 2.2 The AFK rule and the declining farm price

**Rule (fails closed):** the bank buys nothing that an unattended farm makes. That covers:

- every item in `tools/economy_audit.py` `AFK_FARMABLE` whose farm the mobsbegone blacklist does not block;
- every drop a Pasture Loot ranch makes;
- apricorns, berries and fish.

Those items are sold **only** to the **Produce Buyer**, under a per-player allowance.

**Entries leaving the bank.** All of these were MEASURED in the two files:

- **From the base list:** apple, mushroom_stew, bread, cod, salmon, tropical_fish, pufferfish, cooked_cod,
  cooked_salmon, cookie, melon_slice, dried_kelp, carrot, potato, baked_potato, golden_carrot, beetroot,
  beetroot_soup, sweet_berries and glow_berries.
  - The base also buys pork, beef, chicken, mutton, rabbit, cake and pumpkin pie. Their sources are animals that
    mobsbegone removes, so these entries are dormant and stay unless the audit finds a route.
  - Cobblemon's cooked foods (poke_cake $120, old_gateau, curry, candied_apple) stay only if the audit's
    recipe-reduction pass shows no all-AFK recipe for them.
- **From ours:** the seven apricorns, the ten berries, string, bone, feather, spider_eye, rabbit_hide, gunpowder,
  slime_ball, leather, ender_pearl, nether_wart and amethyst_shard.

**The Produce Buyer** (functions rung; mechanisms already in use):

- **The NPC:** a dialogue NPC stands at each gym town's market and at Hollin's farm. Its options read "Sell a crate
  of <kind>".
- **Taking the crate:**
  - Count first with `execute store result score @s pb.n run clear @s <item> 0`. That a 0-count `clear` reports
    without removing anything is ASSUMED vanilla behaviour and needs a test.
  - If the player has enough, `clear @s <item> <crate>`.
- **Paying:** the macro line `$cobbledollars give @s $(amount)`. This exact form is used by
  `tools/arena_runtime.py:753` and `tools/blackout_pack.py:632`; the blackout's money return worked in game (EXP-042,
  RELAYED, STATE line 114).
- **Reading progress:** the badge count comes from the per-player `cobblers:flag/gymN_cleared` advancements.
- **The allowance:** a per-player score `pb.sold` resets whenever the badge count changes. So the allowance is **per
  leg**, not per hour, and an AFK farm can fill it but never exceed it.

**Crates:** wheat, carrot, potato or beetroot ×32; melon slice ×64; any apricorn ×32; berries ×16; fish ×16; ranch
goods ×16; dried kelp ×64; nether wart ×32. All kinds count against one allowance, so the player chooses what to farm.

| Badges held | $ per crate | Crates per leg | Most a player can earn in the leg | Share of the leg's trainer income (COMPUTED) |
|---:|---:|---:|---:|---:|
| 0 | 40 | 40 | 1,600 | 40% |
| 1 | 30 | 30 | 900 | 20% |
| 2 | 25 | 20 | 500 | 5% |
| 3 | 20 | 10 | 200 | 1.2% |
| 4-7 | 10 | 10 | 100 | under 0.5% |
| 8 and later | 0 | 0 | 0 | 0 |

The whole campaign's farm income is capped at **$3,600 per player** (COMPUTED). Money from the farm is early income
only. Late farming is for berries, mints and Pokemon food, not dollars.

**The rule that keeps a stall from undercutting the buyer:** no seller in the world may sell a produce item at or
under $1.25 a unit (the badge-0 crate price ÷ 32). Stoneford's bakehouse and the farm stalls must be checked.

**Considered and rejected:** a barter villager paying relic coins (bank $50, base). Its `maxUses` is per villager, so
the cap would be shared rather than per player, and the price could not decline by badge.

### 2.3 What data/bank.json must be able to carry

`tools/bank.py` cannot express any of section 2.2 today. It refuses any base change (`problems`, line 172-173:
"changing a base price is a separate decision", MEASURED). It needs:

- **`base_removed`:** `[{item, why, decision}]`. `entries()` filters these out of the base list. The decision is the
  owner's direction of 2026-10-10, cited.
- **`afk_rule`:** a declared list that `problems()` checks against the bank. `economy_audit.py` independently
  cross-checks the bank against its own `AFK_FARMABLE` table, so the builder's list and the auditor's list stay
  separate derivations.
- **`effort_model` rule change:** see section 7, R5.
- **New tier `cave`:** its rate derives from the cave's reset clock (section 3.3).

---

## 3. The refillable mining cave

### 3.1 The mechanism: reused, not invented

The cave reuses `tools/mines.py` exactly (MEASURED, lines 690-760):

- the restore runs only while a player is inside the approach box, checked every 100 ticks;
- the fill is filtered over `#cobblers:face_resettable`, so a player's chest survives;
- there is an occupancy guard: no player and no `cobblemon:pokemon` inside the formation or within 1 block of it;
- the formation's four corners must be loaded;
- a per-face period runs on the saved game time, so a restart neither repeats nor loses a restore;
- 8 ore variants, never the same one twice running.

A cave **gallery** is a face formation with vanilla ore in place of stone ore. `data/mines.json` `resettable` must
gain the vanilla ore blocks (coal, iron, copper, lapis, gold, redstone and diamond, with their deepslate forms).

Iron ore is a spawn-condition block. The world packs' contract C4 and `data/spawn_block_policy.json` therefore need
a whitelist entry; the owner allowed such blocks on 2026-10-05, and that is a builder flip. The gallery restore's
clock must join contract C14's sweep.

### 3.2 Where, shared or per-player

The cave is **shared**, because blocks are world state. A per-player copy would need a per-player pocket dimension,
the same unproven X-experiments as `NETHER_DUNGEON_SCOPE.md` section 12. Fairness comes from size instead: **at least
two galleries per expected concurrent player**, so 8 galleries for four friends.

The sites come from data. No coordinates are invented here; each is marked **to site**, and the builder sites it
under the ground rule.

| Candidate | Record | Why | Use |
|---|---|---|---|
| **The Route 1 old mine**, west of Route 1 | `tools/route1_old_mine.py`, finds `r1_old_mine` / `r1_old_mine_stope`; built in staging (STATE line 103) | already an adit, cave and stope on the first leg | **Early chamber**, 3 galleries: legs 1-3, where money is short (section 1.3) |
| **Fossick** (`mining_town`) | `data/towns.json:1352` | the mining town; its bank already opens there (`data/bank.json` `buyer_towns`) | **Main deep cave**, 8 galleries: from leg 3 |
| West Spur Dig | `data/rift_mines.json` (applied in staging) | quarry dressing; reached late | alternative to Fossick |
| Victory Road's Abandoned Cut | `data/dialogue.json:3762` (the Digger) | tier 9 | not recommended: too late for the kits |

**Recommendation: the Route 1 old mine (early) plus Fossick (deep).** Fossick's reachability by badge is still
PROGRESSION_LADDER's U-5. If Fossick is not reachable by leg 3, the deep cave moves to the West Spur Dig.

### 3.3 Yield and reset

The reset period is **20 minutes per gallery** (24,000 ticks; the stones use 600 s). The two-face stagger rule is
reused. A gallery is ASSUMED to take a player about 10 minutes to clear.

| Gallery | Ore blocks per reset (mean over the 8 variants) | Bank value per reset | One player's hour | Fight hour of the leg it opens |
|---|---|---:|---:|---:|
| Early (Route 1) | 10 coal, 8 iron, 4 copper, 1 lapis | 158 | 948 | leg 1: 1,008 |
| Deep (Fossick) | 8 coal, 8 iron, 2 lapis, 1 gold, 2 redstone; 1 diamond in 3 of 8 variants | 231 | 1,386 (upper, Fortune III: 2,322) | leg 3: 2,492 |

Basis for these figures:

- The ore drop counts are vanilla averages without Fortune (ASSUMED).
- Prices are MEASURED from `data/bank.json`. Values and hours are COMPUTED; the fight hour is the leg's income ÷ 4,
  the ASSUMED `max_leg_hours`.
- **Server-wide ceiling:** 8 galleries × 3 resets an hour × 0.375 = **9 diamonds an hour** from Fossick, plus the
  finite worldgen.
- A player clearing galleries alone gets about **2.25 diamonds an hour**. That makes a leg-4 TM (2 diamonds) about
  an hour of work, which matches section 1.4.

### 3.4 Netherite: no refill

The Nether generates new chunks normally (RELAYED, `MINECRAFT_PLAY_LOOPS.md` P4/P5).

- If its border is the overworld's scaled by 1/8 (ASSUMED vanilla), it is about 1,280 blocks square. At about 1.7
  debris a chunk (ASSUMED), that is about 11,000 debris (COMPUTED).
- A Master Ball by barter costs 1 netherite block + 21 ingots (`data/direct_trades.json:109-110`, MEASURED). That is
  30 ingots, or 120 debris.
- So the debris supply is not scarce for four players, and debris stays the effort gate and the sink.

The Nether border and the debris density must be measured first (`MINECRAFT_PLAY_LOOPS.md` section 7, unknown 3)
before netherite is declared safe.

---

## 4. The Challenge voucher: the actual number

### 4.1 Challenge income

Challenge rosters were read the same way (MEASURED). Every leader brings six:

- Challenge leader level sums: 116, 145, 174, 205, 240, 270, 300, 330;
- Normal leader level sums: 56, 70, 114, 135, 195, 217, 242, 319.

Each junior and each 3-member route trainer gains a member: for example `route_01_trainer_04` goes from 15/16/17 to
15/16/16/17, and `route_09_trainer_10` gains a fifth. Because payment is quadratic, the extra income is **+$42,605
from the leaders, +$53,963 from the juniors and +$48,254 from the route trainers: +$144,822 by Victory Road**
(COMPUTED). The mansion guardians and the League are treated as identical in both modes.

| Leg | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | VR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Challenge leg income | 8,691 | 11,304 | 20,175 | 31,066 | 35,191 | 57,730 | 73,867 | 100,823 | 58,152 |

### 4.2 The ask a Challenge player must cover without Minecraft

Each item below is assumed bought **in full**.

- **Fight costs: $3,700 a leg** (ASSUMED). That is Normal's $2,500 plus two extra blackouts at $600 for Full-Team
  fights.
- **Convenience:** as section 1.3 (RELAYED).
- **The raise service:** 6 Pokemon × $500 at every cap step, so $3,000 a leg. This is the owner's full-use figure:
  10 steps × 6 × $500 = $30,000.
- **EV service:** 6 × $2,000 at badge 5.
- **IV service:** 6 × $6,000 at badge 8.
- **The Mega Bracelet:** $7,500 at badge 5.
- **The answer kits: in kind** (4.3).

Cash flow, COMPUTED:

| Leg | Income − fights − convenience − services | Cumulative |
|---|---:|---:|
| 1 | 8,691 − 3,700 − 6,050 − 3,000 = **−4,059** | **−4,059** |
| 2 | 11,304 − 3,700 − 2,700 − 3,000 = +1,904 | −2,155 |
| 3 | 20,175 − 3,700 − 8,500 − 3,000 = +4,975 | +2,820 |
| 4 | 31,066 − 3,700 − 6,500 − 3,000 = +17,866 | +20,686 |
| 5 | 35,191 − 3,700 − 6,500 − 3,000 − 7,500 − 12,000 = +2,491 | +23,177 |
| 6 | 57,730 − 3,700 − 14,500 − 3,000 = +36,530 | +59,707 |
| 7 | 73,867 − 3,700 − 12,500 − 3,000 = +54,667 | +114,374 |
| 8 | 100,823 − 3,700 − 17,000 − 3,000 − 36,000 = +41,123 | +155,497 |

**The only cash shortfall is leg 1: $4,059.** It drops to $1,059 if the player does not buy raises in leg 1.

**For comparison, under the relayed model B** (linear, with Challenge's extra members at $13.07 a level) the same
schedule bottoms out at −$32,627 at badge 8 (COMPUTED). The jar's quadratic payout removes that gap.

### 4.3 What no amount of trainer money buys

**The answer kits' materials, $10,748 at bank value** (section 1.4). Rule B1 means no seller sells diamonds, raw ore
or scrap, and the kits' dollar lines are income-gated (section 7, R3). They are gated on Normal income, and a
Challenge player can afford a few of them, but not eight kits.

### 4.4 The number, and how it is delivered

> **The voucher is $4,000 in cash at Oak's mode choice, plus that leg's answer-kit materials granted at each gym's
> first clear (the gym N flag) to a player tagged `cobblers_mode_challenge`. The kits total $10,748 at bank value
> across eight grants.**
>
> **Total ≈ $14,750 of value, not $100,000.**

- **Cash at $4,000, not $4,059:** the cash stays just under the badge-1 income gate under the new income
  ($4,100, section 7, R3). A voucher above that gate buys a gated TM before badge 1.
- **Why not $100k at Oak:** it would open every income gate up to $100k at once (the gated TMs of badges 1-5 under
  the new income).
- **Delivery uses existing mechanisms:**
  - the grant is a `give` in the per-leader reward function that `tools/progression_pack.py` already runs once per
    player on the flag;
  - the cash is the Oak dialogue's existing action;
  - `quest.main_worldshift_reveal.trainer_mode` is the lock field, so the grant happens once.
- **Multiplayer:** the grant is per player. A Challenge player can hand materials to a Normal friend; whether that is
  pooling or co-op is owner question 4.
- **Sensitivity:** if the owner's team rewrite shrinks the Challenge rosters, the $144,822 falls with S², and the cash
  gap reopens. U6 makes the voucher a generated number, recomputed from the rosters, so it cannot go stale.

---

## 5. Paid services (the command is now known)

The commands are VERIFIED from the jars by LEVELSET (RELAYED from the note's A1-A3):

- `pokemoneditother <player> <slot 1-6> level=N | <stat>_ev=N | <stat>_iv=N`, op level 2;
- `testpartyslot <player> <slot> <props>`, which matches values exactly;
- the cap read: `$execute store result score @s svc.cap run rctmod player get level_cap @s$(x)`
  (`tools/levelcap_pack.py:93`).

**`level=` bypasses rctmod's cap**, because no EXP event fires. The service must therefore set exactly the cap it read.

| Service | Price | Effect | From | Where |
|---|---:|---|---|---|
| **Raise to cap** | **$500 per Pokemon** (the owner's figure) | `level=<cap>`. Refused, with no charge, if the cap fails to read, the slot is empty, the slot is already at the cap, or the party is over the cap | cap 20 onward | each gym town's training ground keeper (`data/training_grounds.json`, 8 grounds, applied in staging) |
| **EV spread** | **$2,000 per Pokemon** | zero all six EVs in one command, then set two stats to 252 and HP to 4 (the 510 total rule, note A1) | badge 2 (the power items' Mart tier) | as above |
| **IV training** | **$1,000 per stat**, so $6,000 for all six | `<stat>_iv=31` for the stats bought | badge 8 (the retired gold cap's gate) | as above |

Rules for the services:

- **Payment** uses the ferry's checked sequence: read the balance, `cobbledollars remove`, re-read
  (`tools/ferries.py:228-236`, MEASURED).
- **Limits:**
  - each service is per player and acts on the player's own party only (`@s`);
  - raising a Pokemon is refused at or above the cap, so it is bought once per Pokemon per cap step;
  - EV and IV services can be bought again at full price.
- **Full use** for a team of six is $30,000 + $12,000 + $36,000 = $78,000 (COMPUTED). Against the jar's income that
  is optional spending, not a wall. By leg 8 a $500 raise is 0.7% of a leg (COMPUTED); owner question 7.
- **After the Champion (cap 100):** a flat $500 raise would skip the arena's whole climb. **Recommendation:** the
  service stops at cap 62; after that it charges **$200 per level** above 62 ($7,600 to raise one Pokemon to 100).
  Owner question 7.
- **Untested, and blocking the build:**
  - whether moves are learned and evolutions offered after a level set (note A2: no event fires);
  - an empty slot;
  - an EV set that would pass 510;
  - choosing a slot through MoLang.

  These are experiment S1-S5 (BUILD LIST U7), run before anything is placed.

---

## 6. The arena cap rule

**Step 1: CobbleDollars' automatic pay keeps nothing on an arena win.**

- The runtime reads the balance at the bout's start (the ferry's read) and again in `fn["won"]`.
- It then `cobbledollars remove @s <delta>`, removing all of the automatic credit before paying our purse. The
  configurable cap the other unit is building is set to **0**.
- This is a claw-back, so the random credit does not need predicting. The other unit owns the mechanism; this design
  sets the cap at 0.

**Step 2: our purse, under a per-player rule.** Purses are as in `tools/arena_runtime.py` (MEASURED).

| Win | Pays |
|---|---|
| Every win that counts toward clearing a rank the player has **not yet cleared** (its `advance` wins, its legs, its clear bonus, its rank-up exam) | the full purse, once per player |
| A win at a rank the player **has** cleared | a flat **$200**, at most **3 paid wins per player per Minecraft day** (24,000 ticks), then $0 that day |
| Exhibition (two or more ranks below) | retired: covered by the row above |
| Streak (rank 9) | the purse only on wins that extend the player's best streak; the every-5th-win bonus only when that multiple is a new best; milestone prizes (10/25/50) once |

Numbers (COMPUTED from the note's B1 table and `data/arena_fights.json`):

- **The first clears of ranks 1-4 pay about $47,050 once per player:**
  - rank 1: 3 × 2,200 + 2,150;
  - rank 2: 3 × 3,000 + 2,250;
  - rank 3: 2 clears × (2 × 2,300 + 2,000) + 4,400;
  - rank 4: 2 × 3,150 + 3,150.
- **Repeats pay at most $600 a Minecraft day,** which is at most $1,800 an hour of continuous play (3 days an hour).
  That is under the deep mining hour, so the arena is "always a fight" but never a money farm.
- Arena trophies stay once-per-player prizes, never sold (owner, 2026-10-09).

---

## 7. Rules and audits that change

| # | Rule today (where) | Change | Why |
|---|---|---|---|
| R1 | Income is model B, linear ($13.07/level), RELAYED (`data/markets.json` `income_basis`) | Generated by `tools/income_model.py` from the jar's formula (expected 0.28125·S²) over `data/trainers.json` and `data/mansion_guardians.json`, with Normal and Challenge columns and `relayed: false` | P1: model B is contradicted by the jar |
| R2 | `CURVE_BAND = (0.65, 0.70)` over every critical-path shelf line (`tools/markets_audit.py:92`) | **The band stays. Its numerator becomes the convenience lines plus a declared fight allowance; power lines leave it. Its denominator becomes trainer income (R1) + the produce allowance + one declared gathering hour a leg at the tier's rate.** The hard check stays: fights ≤ trainer income at every badge | The old band was tuned with power lines inside and on model B; at the new income it reads 1.50 to 0.49 (1.2). Every input of the new form comes from data, with no tuned constant |
| R3 | `price_policies.income_gate` applies to TMs, memories and the Sachet | Applied to **every power line with a material route**: held items, keyed Mega stones and answer TMs. Prices move with R1: badge 1 goes from $9,500 to $4,100 and badge 8 from $145,100 to $202,900 (COMPUTED) | "Power is never priced in money a fighter can reach" (1.3); the owner's own TM rule, generalised |
| R4 | Ball floor: the Master Ball must cost more than the dearest non-exchange line (`tools/bank.py:312`) | Lines whose `price_rule` is `income_gate` are excluded from the floor | An income-gate price is a gate, not a value. Under R1, badges 1-3 TMs ($4,100-18,600) already clear $27,000. The other held lines release only with this change (owner question 5) |
| R5 | `effort_model` `half_wage` (a gathering hour × 4 ≤ half the leg) and `upper_wage` (`tools/bank.py:141-142`) | `half_wage` becomes **parity**: the typical hour ≤ the leg's fight hour (income ÷ 4). `upper_wage` becomes the upper hour ≤ 1.5 × the fight hour | Under R1 the early tier's $620 × 4 = 2,480 is over half of leg 1 (2,016), and the deep tier's $1,350 fails as well (COMPUTED). The owner now wants Minecraft to pay early, so parity, not half, is the intent |
| R6 | Base bank entries are never changed (`tools/bank.py:172`) | `base_removed`, plus the AFK rule (2.2) | The owner's direction of 2026-10-10 is the "separate, named decision" the rule asks for |
| R7 | Barter band 1.00-1.05 of the counter (`data/direct_trades.json` `pricing.rule`) | Kept for the Northlight late shelf (the Master Ball and the held items there). Answer-kit barters are priced by section 1.4's recipes and **may be far cheaper than their income-gated dollar line** | P6(a); owner question 2 |
| R8 | `held_item` exchange floor = the dearest held item on a shelf (`tools/bank.py:310`) | Read from lines that are not income-gated only, or the floor jumps to $35,000+. The Fossick and Northlight held-item exchange lines re-check against it | R3's side effect |
| R9 | The arena exhibition quarter (`tools/arena_runtime.py:587`) | Replaced by section 6 | P7 |
| R10 | `economy_audit.py` | Gains sell points for the Produce Buyer (a buyer), barter edges for the kit lines, the cave as a renewable supply (its restore clock), and a check that 0 unblocked AFK items are bought | The new buyers and supplies must be inside the arbitrage hunt |

---

## 8. Entei: the material sink (prices only; the Nether unit builds it)

Each entry consumes a key made from **2 netherite ingots**: 8 debris + 8 gold, $1,800 at bank value, about an hour at
the ASSUMED 10 debris an hour.

- The key costs the same on every clear and in both modes (the owner).
- Later clears pay items from the collection table, never dollars, and none of those items is bought by the bank
  (`NETHER_DUNGEON_SCOPE.md` section 3).
- **Entei is a wild battler.** If the wild payout stays on (P2), a level-70 clear also pays about $1,378 (COMPUTED,
  0.28125 × 70²).

---

## 9. BUILD LIST (ordered)

Marks: **[S]** needs the staging server (the main session, never an agent). **[O]** waits on an owner decision.

Every unit's done criterion includes `python tools/validate_data.py` and `python -m pytest
tests/test_system_contracts.py`. Audits are written by `test-author`, never by the builder.

1. **U0 Income model.**
   - **Files:** `tools/income_model.py` (new); `data/markets.json` `income_basis` (generated block); `tests/`.
   - **Done when:** it reproduces section 1.1's cumulative column within 1% and section 4.1's Challenge column; and
     `markets.py prices --write` re-prices the income-gate lines.
   - **Must pass:** an independent test that recomputes Σ0.28125·S² from the rosters by its own reader, plus
     `tools/markets_audit.py`.
2. **U1 Bank AFK exclusion.**
   - **Files:** `data/bank.json` (`base_removed`, `afk_rule`, the removals in 2.2, R5's parity rule); `tools/bank.py`
     (`entries()` filter, the new problems); `modpack/config/cobbledollars/bank.json` (`bank.py write`).
   - **Done when:** `bank.py check` is clean and `economy_audit.py` reports 0 unblocked AFK items bought and 0
     arbitrage.
   - **Install:** the next install [S].
3. **U2 Produce Buyer.**
   - **Files:** `data/produce_buyer.json` (crates, the 2.2 schedule, sites); `tools/produce_buyer.py` (the pack); an
     independent `tools/produce_buyer_audit.py`; a reapply step.
   - **Done when:** the audit checks the allowance resets per badge, that the price is never above the schedule, and
     that no seller sells a produce item at ≤ $1.25.
   - **Experiment:** count-and-clear, give, and the allowance reset, in staging [S].
   - **Owner:** is a dialogue button UI acceptable for selling? [O]
4. **U3 Mining caves.**
   - **Files:** `data/mining_caves.json` (sites to be sited, galleries, the 3.3 yields); a generator reusing
     `tools/mines.py` (formation, `column_runs`, check and restore); `data/mines.json` `resettable` plus the vanilla
     ores; a C4 whitelist entry; the C14 sweep; an independent audit; a reapply step.
   - **Done when:** the audit passes, which means the occupancy guard is present, the period ≥ 24,000, the yields
     equal the data, and the `cave` tier passes R5.
   - **Apply [S].** Sites are confirmed by the owner [O].
5. **U4 Answer kits.**
   - **Files:** `data/direct_trades.json` (kit lines per town); `data/markets.json` (the power lines carry
     `price_rule: income_gate` and name their barter route).
   - **Done when:** `economy_audit.py` passes B1-B4; the TMCraft ids are verified (models in the jar; the lang-key
     audits must accept a model where no lang key exists, `data/bank.json` `exchanges.not_built`).
   - **Owner:** a barter villager in each gym town, or Northlight only? [O] Do it after U0.
6. **U5 Curve and floor rules.**
   - **Files:** `tools/markets_audit.py` (R2); `tools/bank.py` (R4, R8); `data/markets.json` (convenience lines
     re-priced to the new curve with `markets.py prices --write`; `fight_allowance` declared).
   - **Done when:** `markets_audit.py` and `town_squares_audit.py` are clean.
   - **R4 is [O].**
7. **U6 Challenge voucher.**
   - **Files:** `data/challenge_voucher.json` (cash and per-gym kits, generated); `tools/challenge_voucher.py`
     (computes section 4 from U0's columns, the shelf and the services); grant lines in `tools/progression_pack.py`
     and Oak's action; an independent test.
   - **Done when:** the generated number equals section 4 within 1% at the current data, and the grant is gated on
     the tag and runs once per player.
   - **Experiment [S]; form [O].**
8. **U7 Paid services.**
   - **First:** experiment S1-S5 (5) [S].
   - **Then files:** `data/training_services.json`; `tools/training_services.py` (dialogue at the training grounds,
     checked payment, `pokemoneditother` macro lines, the cap read and refusals); an independent audit.
   - **Done when:** the audit shows no path writes `level=` other than the read cap, and every refusal path charges
     nothing.
   - **Postgame price [O].**
9. **U8 Arena cap.**
   - **Files:** `data/arena_fights.json` `prizes.repeat_rule` (section 6); `tools/arena_runtime.py` (purse, claw-back
     cap 0).
   - **Done when:** the arena audit and tests show the full purse only before a rank's first clear, $200 × 3 per day
     after that, and the claw-back on every win.
   - **Coordinate** with tonight's arena unit. In-game proof: one rank-1 win, the balance before and after [S].
10. **U9 Entei key price.** `data/` for the Nether unit: the key is 2 netherite ingots per entry, and the drop table
    is excluded from the bank (section 8).

**Before any of it [O]:** the wild payout (P2). If it stays on, every number above is a floor and the produce
allowance is irrelevant.

---

## 10. Owner questions

1. **Turn off CobbleDollars' wild-battle pay** (`earnCobbleDollarsFromWildPokemon: false`, a `modpack/config` overlay)?
   Under the jar's formula, a level-50 wild battle pays about $700, uncapped.
2. **Make barter the intended route for the gym answer kits**, cheaper than their income-gated dollar line, inverting
   2026-10-08's "alternative, not a bypass" for kits only?
3. **Put a barter villager in each gym town** for its leg's kit, keeping Northlight as the centre and the late shelf?
4. **The Challenge voucher:** $4,000 cash at Oak plus kit materials per badge (about $14,750 of value), instead of
   $100,000 at Oak? And is a Challenge player handing materials to friends co-op, or a leak?
5. **Exclude income-gate lines from the Master Ball floor**, releasing the held TM lines as gated dollar lines?
6. **The base bank's emerald ($400) and the lumymon feathers ($5,000-30,000):** keep them or remove them? The
   research station issues the feathers.
7. **Services:** is the flat $500 raise still right when a late leg pays $68,000? And after the Champion, $200 a
   level?
8. **Minecraft per leg:** about one hour (these recipes), or more?
9. **Caves:** the Route 1 old mine plus Fossick, 8 galleries, 20-minute reset?
