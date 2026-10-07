# EV and IV training, and whether the Marts become training hubs

**Status: design only, answering the owner's 2026-10-07 item 11.** Nothing here is built, generated or run in game. Written by `content-architect`
(Wave A, unit A7). It writes no data and no tool; the plan in section 5 hands the work to the dev agents.

**The ask** (the owner, 2026-10-07, `docs/STATE.md:137` item 11): *"EV training implemented"*, possibly *"pokemarts
become ev / iv hubs and all items are delegated to traders"*. Design first; it reshapes the 2026-10-06 Mart tiers.

**Restated:** what can a player use, in this pack, to shape a Pokemon's EVs and IVs; where should they get it; should
the Marts stop selling the ordinary goods and sell training instead; and what does that do to the Mart tiers (R14),
the counters, the economy, the level caps, and Challenge and Nuzlocke play.

**How numbers are marked.** *measured* = read or counted from a file in this checkout this session, with the path.
*relayed* = taken from another document without re-measuring, with its source. *arithmetic* = computed here from the
figures named. *ASSUMED* = not verified anywhere.

---

## 1. What EV and IV training is in this pack (native and installed mechanisms only)

### 1.1 Verified

Every row is from `docs/research/ITEMS_ABILITY_EV_HELD_MEGA.md` (Cobblemon GitLab tag `1.8.0`, read through a fetch
tool that summarises; the code quoted there was returned verbatim, the item lists are the tool's extraction and may be
incomplete, `:13-16`). **Nothing in that note was run in Minecraft** (`:16`). So "VERIFIED" below means *verified in
source for 1.8.0*, the server's version (`docs/STATE.md` "Runtime", relayed).

| Mechanism | Effect | Source (note line) |
|---|---|---|
| EV caps | 252 per stat, 510 total; every add clamps to both | `:80-82`, `EVs.kt` |
| Battle EVs | each defeated opponent awards its form's `evYield` (`Generation8EvCalculator`) | `:94-98` |
| Power items (`power_weight`, `_bracer`, `_belt`, `_lens`, `_band`, `_anklet`) | held: +8 in its stat on each EV award, flat, matched by item tag | `:90`, `:96-97` |
| Vitamins (`hp_up`, `protein`, `iron`, `calcium`, `zinc`, `carbos`) | +10 per use; no 100-EV vitamin cap, so 26 uses reach 252 | `:86` |
| Mochi (`health_mochi` ... `swift_mochi`) | +4 per use | `:88` |
| EV feathers (`health_feather` ... `swift_feather`) | +1 per use | `:87` |
| `fresh_start_mochi` | resets all EVs to 0 | `:89` |
| EV-lowering berries (pomeg, kelpsy, qualot, hondew, grepa, tamato) | -10 in one stat (`evLowerAmount "10"` in `data/cobblemon/mechanics/berries.json`, a Molang value a datapack can override) | `:91` |
| Macho Brace | **not in Cobblemon 1.8.0** | `:92` |
| Hyper-training candies (`health_candy`, `mighty_candy`, `tough_candy`, `smart_candy`, `courage_candy`, `quick_candy`; and six -1 twins) | +1 (or -1) *effective* IV in one stat per use, via `hyperTrainIV` | `:102-107` |
| Ability Capsule / Ability Patch | swap within the species' own abilities; no randomiser item exists | `:22-54` |

Installed, verified locally:

| Mechanism | Effect | Source |
|---|---|---|
| Only Bottle Caps (`obc`, `Only Bottle Caps-1.5.0-fabric.jar`) | silver cap maxes one IV, gold maxes all, withered zeroes; per-stat caps crafted from a silver cap and mint leaves | `docs/research/notes/reward-item-inventory.md:314-324` (Modrinth page, VERIFIED there); jar in `modpack/manifest/overlay.json:316-344` (measured) |
| Silver caps from fishing: 3% vanilla treasure, 5% Poke Rod treasure; gold caps 0.0 from both | config | `base-pack/cobbleverse/config/obc-common.toml:5,9,15,19` (measured); `modpack/config/` carries no obc override (measured, directory listing) |
| cobblecuisine shakes grant EVs (`lowShakeEv 2`, `mediumShakeEv 4`, `highShakeEv 8`), and a food boost keeps wild IVs in 20-31 (`ivMinValue`, `ivMaxValue`) | config keys exist | `base-pack/cobbleverse/config/cobblecuisine.json:12-13, 20-22` (measured). **What the keys do is ASSUMED from their names.** Shakes are withheld from every stall for exactly this (`data/markets.json:422`, measured) |

Both `obc` and `cobblecuisine` are listed as *"loads under 1.8 but behaviour is unverified"*
(`modpack/manifest/overlay.json:675-677, 703-705`, measured).

### 1.2 How a player can get each one today (measured in `data/`, relayed where noted)

| Item | Where in our data | Other route |
|---|---|---|
| Vitamins | Northlight's counter `northlight_station`, **3,500 each**, ungated since `counters_are_merchants` (`data/markets.json:298-303`, measured) | brewing only, and brewing is unreachable (no blaze rod; `docs/research/OBTAINABILITY_VANILLA_COBBLEMON.md:93-95`, `OBTAINABILITY_SWEEP_2026-10-05.md:95-99`, relayed) |
| Gold Bottle Cap | Holdfast's counter, 6,000 (`data/markets.json:248`, measured) | none (gold 0.0 above) |
| Silver Bottle Cap | not sold | fishing, 3% / 5% (above) |
| Ability Capsule | Northlight's counter, 10,000 (`data/markets.json:304`, measured) | brewing from dragon's breath once a brewing stand exists (relayed, sweep `:95-98`) |
| Power items | **nowhere** | recipe needs a white mint leaf, which has no source (`OBTAINABILITY_VANILLA_COBBLEMON.md:91-92`, relayed) |
| Mochi, EV feathers, reset mochi, hyper-training candies | **nowhere in `data/`** (grep for their ids over `data/`: 0 matches, measured) | **UNKNOWN**: no research note records a source. A6 is routing every item and owns this question |
| EV-lowering berries | not sold; **not bought by either bank** (grep of `data/bank.json` and the base `bank.json` for the six ids: 0 matches, measured) | berry trees, if they exist in the world (not checked here) |
| Battle EVs | free, from every wild or trainer fight | the training grounds (section 2.2) |

**So the region already has an EV shop: Northlight's counter, vitamins only, at a price that makes one maxed stat cost
91,000** (26 x 3,500, arithmetic on `data/markets.json:298`). No item that *steers* battle EVs (power items) or *undoes*
them (reset mochi, berries) is obtainable.

### 1.3 Assumed (each is an experiment in section 6)

- **A-1** Cobblemon uses the mainline stat formula, so 252 EVs add about `63 x L / 100` to a stat at level L and an IV
  of 31 against 15 adds `16 x L / 100`. Not checked in the note. Every magnitude in section 4.1 rests on it.
- **A-2** `evYield` holds all six stats (some 0), so a power item adds +8 even against a species that yields nothing in
  its stat (the note's own ASSUMED, `:98-100`).
- **A-3** Audino, Chansey and Blissey yield HP EVs only (2, 2, 3 in the mainline series). **Not read from the 1.8.0
  jar**; no tool in the repo reads `evYield` (grep, measured).
- **A-4** A Pokemon held at rctmod's level cap still gains EVs when its EXP is clamped. rctmod clamps in
  `EXPERIENCE_GAINED_EVENT_PRE` (`docs/mechanics/LEVEL_CATCHUP.md:39`, relayed); the EV award is a different code path
  (`EvCalculator`), but whether rctmod's handler cancels anything the EV path depends on is unread.
- **A-5** The summary screen shows a player their EVs and IVs. If it does not, training is invisible and needs a
  reader (section 3, option E).
- **A-6** Hyper-training candies have no level requirement, and their *effective* IV behaves in battle like a real
  one. The note shows `hyperTrainIV(stat, effectiveIV + n)` and no level check in the quoted line; the class was not
  read whole.
- **A-7** EV items can be used on another player's Pokemon or only the owner's. The Ability items are owner-only
  (`:44`); the EV items' `accepted` set is not quoted.

---

## 2. Where this touches what exists

### 2.1 The Marts and counters (measured unless marked)

- `data/traders.json` has 26 trader records: **14 Mart clerks** (`"stock": "mart"`), 1 Assayer (`stones`), 7
  `regional`, 4 `withdrawn` (count of `stock` values, measured).
- A Mart clerk sells its BCA shopkeeper template's own list, filtered: basics (Poke Ball 200, Potion 200, Antidote 100)
  plus every tier line with `badges <= tier` (`data/traders.json:561-579`). **Nothing is authored**; the prices are the
  template's (`:581`). The tier is the badges a critical-path player holds arriving (`:582`). R14 writes the clerks
  (`tools/reapply.py:2067`, step `R14` "town traders", `cobblers:towns/vendors_<town>`, measured).
- Two authored categories already ride on clerks: the trainer card on Pallet's (`stock_policy.trainer_card`,
  `:585-596`, "one authored category appended to one Mart clerk's filtered shop", `tools/traders.py card_shop`) and the
  Assayer's stones (`:597-616`, `stone_shop`). **Neither has been seen to sell in game: proof P-7** (`:591`, `:615`).
- **15 counters** in `data/markets.json`, **14 of them beside a Mart** (`near_trader` = each of the 14 Mart ids; the
  15th, `tableland_stop`, has none, `:406`), measured. Since `counters_are_merchants` every counter and stall is a
  CobbleDollars merchant, one list for every player; 53 counter lines lost a per-player badge gate (`:460-468`).
- A Mart never sells what its own town's counter sells (`tests/test_mart_tiers.py`, relayed from
  `data/traders.json:581`).
- I counted **41** stall records in `data/markets.json` (records whose first line is `"id": ..., "town"`, measured by
  regex; a record shaped differently would be missed). The brief's **43 contract stalls** is relayed and may be the
  plaza contract's count (`data/plaza_centres.json`); not reconciled here, and nothing below depends on it.

**Consequence for "delegate all items to traders": no seller in the region can gate per player.** A Mart clerk, a
counter and a stall are the same kind of merchant with the same one-list screen. Moving the basics from the clerk to
the counter beside it moves them about three blocks (counters stand 3+ blocks to the side of the Mart door,
`data/markets.json:238` and its siblings, measured) and changes no gate.

### 2.2 The training grounds

`data/training_grounds.json` plans one activated Habitat Block per gym town (8, `:99-260`), up to 6 alive, 2 per
activation (`:42-43`), levels cap-3 to cap-1 (`:47-52`), rosters **Audino at tiers 1-5; Audino, Chansey, Blissey at
6-8** (`:55-82`), all measured. Planned, not placed (`:4`).

**Finding.** If A-3 holds, every team a player fills up at a ground comes out with **HP EVs and nothing else**, up to
252 HP. The catch-up system therefore decides the player's EV spread, silently. That is harmless (HP is never wasted)
but it means any EV design must either accept "HP first" or give the player a way to steer (power items) and undo
(reset mochi). It also makes the grounds the natural EV site: with a power item held, every Audino becomes +8 in the
chosen stat (A-2), so **one HP-yield ground trains any stat** and no per-stat grounds are needed.

### 2.3 The level cap

The cap is enforced on EXP (rctmod `allowOverLeveling = false`, `data/training_grounds.json:7`, relayed). EVs are not
EXP. If A-4 holds, a player at the cap can keep training EVs at the ground, which is the right shape: the cap stays the
ceiling on level, and EV training becomes the thing a player does *at* the cap instead of grinding past it. If A-4
fails (no EVs at the cap), the grounds stop being an EV site exactly when a player most wants one, and the bought
items carry the whole feature.

### 2.4 Parallel units

| Unit | Touch point | What must not happen |
|---|---|---|
| **A4** (vanilla villager item-for-item `Offers`, EXP-055, UNPROVEN; no `experiments/EXP-055*` exists in this checkout, measured) | the only real "trader" that is not a CobbleDollars merchant. If proven, the late kit (vitamins, gold caps) could be barter-only, which is the owner's item 5 ("no money where possible", `docs/STATE.md:137`) | a barter villager selling a vitamin for an item the bank buys for less than 2,500 (section 4.2) |
| **A6** (every item to a source) | power items, mochi, feathers, reset mochi and candies have no recorded source (1.2). This design proposes the Mart as their route | two units giving one item two routes, one of them renewable and cheaper; A6 and this design must agree one owner per item (`data/id_authorship.json` discipline applies if both write records) |
| **A8** (Minecraft-play grind loops) | EV feathers (+1) and mochi (+4) are a natural grind reward | a loop that outputs a **vitamin**: the base bank buys every vitamin at 2,500, so a renewable vitamin is a money printer (4.2) |

---

## 3. Options for "Marts as EV/IV hubs"

All options use the same native EV mechanics (rung 1) and the same CobbleDollars merchants (rung 2, configuration);
the clerk is written by a function (rungs 5 + 7). **None adds a dependency, a scripting layer, a companion or a mod,
and none is world-critical** (no blocks or worldgen; a merchant is an entity). Multiplayer: every option sells to
everyone who reaches the counter; none gates per player (2.1).

| | Option | What the Mart does | Where the ordinary items go | Mart tiers and R14 | Build cost | Blast radius |
|---|---|---|---|---|---|---|
| **A** | **Leave the Marts; make the grounds the EV site** | unchanged | unchanged | unchanged | none in the Marts; the power items still have no source, so EV training stays HP-only plus Northlight's vitamins | smallest; does not deliver "implemented" |
| **B** | **The Mart adds a training shelf** (recommended) | keeps basics and its medicine/ball tiers, and gains one authored category, "Training", released by the same tier rule | stay in the Mart | the tier rule is unchanged; a second tier list (`training_tiers`) rides on it. R14 unchanged as a step; its output grows by one category per clerk | **data + a small generator change**: a `training_shop` in `tools/traders.py` beside `card_shop`, and a block in `data/traders.json` `stock_policy.mart` | one generator, 14 clerks, one test file; no other system |
| **C** | **Training shelf on the counter instead** | unchanged | unchanged | unchanged; the training lines go into each town's counter stock in `data/markets.json` (`tools/markets.py`, R17M) | data only (markets.py already emits authored lines) | 14 counters; the counters' curve and `target_ratio` (`data/markets.json:16-24`) must absorb the lines |
| **D** | **The literal ask: the Mart becomes the hub; the ordinary items go to the counter** | sells only the training kit (and Pallet's trainer card) | basics and the tier ladder move to the counter beside each Mart (14 of 14 have one) | **the tier ladder moves from `traders.json` to `markets.json`**: R14 then writes a training-only clerk; R17M writes the medicine and balls. Prices must be authored (copied from the template: great 600, ultra 800, super 700, hyper 1,500, revive 2,000, max potion 2,500, full heal 400, relayed from `data/traders.json:581`) | **generator change in two tools** (`traders.py` stops filtering the template and emits an authored shop; `markets.py` gains a tier list); `tests/test_mart_tiers.py` rewritten; the independent `economy_audit.py` tiers section re-aimed by `test-author` | widest: both seller systems, both reapply steps, the curve, the audit; and **zero gating gained** (2.1). The owner's 2026-09-25 rule "A town with no balls is not a town" (`data/traders.json:569`) still holds, since the counter is in the same town, but the Mart stops being where balls are |
| **E** | **A training service, not a shop** | an NPC that reads and sets EVs/IVs for a fee (`pokemoneditother <player> <slot> ...`, `ITEMS_ABILITY_EV_HELD_MEGA.md:66-67`, VERIFIED source), charged by `cobbledollars remove` | unchanged | unchanged | **new mechanism**: a dialogue NPC (the superseded dialogue purchase, `data/markets.json:425-442`, kept for this), slot choice, a double-submit guard | new per-player state; the owner chose "villagers with ui only" for shops (`:465`), so a dialogue NPC needs his say. Worth keeping only as an **EV/IV reader** if A-5 fails |

What D's "delegation" would actually buy: nothing a player can feel except that balls move three blocks. If the
owner's "traders" means **A4's barter villagers**, that is a different and compatible idea: the *late* kit could be
traded for Minecraft materials, which B leaves room for (section 4.2 rule E3).

---

## 4. Recommendation: B, the Mart's training shelf, with the grounds as the free route

**The design.** EV training is native battle training, steered by a held power item, at the training ground of each
gym town, at the cap. The Mart sells the kit that makes that possible, released by the Mart's own tier. The expensive
shortcuts (vitamins, the gold cap, the capsule) stay where they are, on the counters. Nothing moves out of the Marts.

### 4.1 The shelf (PROPOSED: items, tiers and prices are the owner's)

| Mart tier (badges arriving) | Training lines | Price, PROPOSED | Why |
|---|---|---|---|
| 0 (Pallet, Stoneford, Steepside) | none | | the first hour teaches catching and the card (`stock_policy.trainer_card`); a level ~15 team gains about 9 points from a full stat (A-1, arithmetic `63 x 15 / 100`) |
| 1 (gym 2's town) | the six power items | 1,500 each | the selector. Durable (a held item, not consumed), one per stat, so a player buys one or two, not six. Against the badge-1 leg of 9,475 (relayed, `data/markets.json:20`, model B, itself unmeasured) one is 16% of the leg |
| 2 | `fresh_start_mochi`; the six EV-lowering berries | 1,000; 300 | the undo, needed the moment the grounds' HP EVs (2.2) are in the way |
| 3 | the six mochi | 800 | top-up of 4 EVs to finish a spread exactly (510 is not divisible into two 252s plus a clean third) |
| 6 | hyper-training candies, the six +1 kinds | 1,500 each | IVs matter least (an IV of 31 against 15 is about 9 points at level 55, A-1, arithmetic `16 x 55 / 100`); late and a little dear. **Only if EV-6 passes** |
| (counters, unchanged) | vitamins 3,500 at Northlight; gold cap 6,000 at Holdfast; capsule 10,000 at Northlight | unchanged | the shortcuts stay off the Marts, so `test_mart_tiers`' "a Mart never sells its counter's line" holds without an exception |

Silver bottle caps stay a fishing find (3% / 5%), not sold: one maxed IV for luck is the right reward for fishing, and
it keeps an A8 loop (fishing) worth doing.

Every price above is a placeholder for `trainer-balance-designer`, to be set against `data/markets.json`
`income_basis` and the 30-35% slack the curve leaves for "the Mart, the ferry, the stones and the blackout"
(`:22`, relayed). The Mart lines are inside that slack, not the curve.

### 4.2 Economy: the arbitrage reasoning (no audit edited)

The economy is safe against a money printer if no item can be bought for less than any buyer pays for it
(`tools/economy_audit.py:20-24`, the audit's own definition, measured). The only buyer is the one global CobbleDollars
bank (`data/bank.json:7, 12`, measured).

1. **What the bank buys of the kit:** the six vitamins at **2,500** (`base-pack/cobbleverse/config/cobbledollars/bank.json:71-93`,
   measured), carried into ours unchanged by rule (`data/bank.json:25-26`). **Nothing else**: power items, mochi,
   feathers, reset mochi, EV berries, candies and bottle caps appear in neither bank file (grep, measured). So every
   line of the proposed shelf is round-trip safe at any positive price. **Zero new arbitrage edges.**
2. **The one constraint is the vitamin.** Any seller, barter villager or grind loop that yields a vitamin for less than
   2,501 is a tap. Northlight's 3,500 is safe. Vitamins are not on the proposed shelf, so the shelf adds no vitamin
   seller. Making vitamins cheaper would need the base entry overridden, which `data/bank.json:26` calls "a separate,
   named decision" (owner question 4).
3. **Recipes.** The audit lowers an item's cost by every recipe whose inputs are buyable (`economy_audit.py:20-23`).
   A power item's recipe needs a white mint leaf, which nothing sells (1.2, relayed). If a seller ever sells mint
   leaves, a power item may become cheaper by recipe than at the Mart, which is a dead shelf line, not a tap, because
   the bank does not buy power items.
4. **Proposed guard rules** (for `minecraft-systems-dev` to author, `test-author` to enforce; not done here):
   - **E1** every kit item goes into `data/bank.json` `never_buy`, so a future `buys` entry cannot turn a renewable
     kit item into income;
   - **E2** no seller, barter villager or loop yields a vitamin at or under the bank's vitamin price;
   - **E3** a barter line (A4) for a kit item never takes a material the bank buys for more than the line's dollar
     price would be, so barter is never the cheaper way to dollars.
5. **What it costs a player** (arithmetic, prices from `data/markets.json:298`, income relayed `:19`): vitamins alone,
   one stat to 252, are 26 x 3,500 = **91,000**; two stats, 52 vitamins = **182,000**, more than model B's entire
   income to badge 8, **145,078**. The vitamin is a top-up, never the route. The proposed route costs one power item
   (1,500) and about 32 fights per stat at the ground (252 / 8, rounded up, arithmetic; A-2), or 26 against Audino
   with the Power Weight (8 + 2 per fight, A-3).

### 4.3 Progression bypass

- **Against the cap: none by construction.** No EV or IV item touches level or EXP. The cobblecuisine defects that do
  (D1 EXP boost after the clamp, D2 Fancy Shake sets the level; `LEVEL_CATCHUP.md:33-34, 219-221`, relayed) are
  separate and stay open. The shakes are already withheld (`data/markets.json:422`).
- **Against the gyms: real, and unmodelled.** No authored trainer carries EVs or IVs: `"evs"` and `"ivs"` occur 0
  times in `data/` (measured). `tools/battle_stress.py:467` assumes IV 15 and EV 0 on both sides (measured). So a
  player with 252 in their attacking stat at level 55 has about +34 (A-1, arithmetic `63 x 55 / 100`) that no stress
  verdict counted. Normal gyms get easier than measured; Normal Brock is already "trivial" (`docs/STATE.md:239`,
  relayed). The same lever could make **Challenge gyms 2-8**, flagged "unwinnable risks" there, fair, if Challenge
  teams are tuned against a trained player. This is owner question 3 and a `trainer-balance-designer` task, not a
  reason to withhold the kit.
- **Early reach.** Mart tiers are by town, and some towns are reachable early: Sunset West sells tier 7 to a player
  who walks there with no badges (`data/traders.json:583`, relayed). The training shelf inherits that. The impact is
  bounded by the player's level (A-1): power items at level 15 are worth about 9 points a stat.
- **Co-op.** Gating controls purchase, never possession (`PROGRESSION_LADDER.md:365`, relayed): one player buys,
  another uses. A-7 (owner-only use) does not change that, because the item is handed over before use.

### 4.4 Nuzlocke and Challenge

- **Nuzlocke (self-imposed, `GAME_VISION.md:168-174`).** EV training adds fights, and every fight at a ground is at
  cap-1 to cap-3 (`data/training_grounds.json:47-52`), so a Nuzlocke player risks a death for EVs; that is the
  player's choice and the ground is optional. **Open:** whether a ground is part of its sub-region's catch zone or a
  zone of its own. `NUZLOCKE_ZONES.md:36` counts one `site` zone today (the Route 1 mansion); the grounds are planned
  Habitat Blocks and are not listed (owner question 8). A blackout at a ground charges the flat blackout fee
  (`data/markets.json:22`, relayed).
- **Challenge.** Challenge swaps each boss to a harder team per player (`OAK_AND_CHALLENGE.md`; the swap is unproven,
  E7 in `docs/STATE.md:137` item 6, relayed). If Challenge teams are later given EVs, EV training stops being optional
  for Challenge players, and the kit must then be reachable **before** the gym that needs it. By the tier rule a
  tier-N line is first sold in gym N+1's town, before that gym, so gym N's Challenge team may assume a trained player
  only for lines of tier N-1 or lower. `trainer-balance-designer` checks this per gym.

### 4.5 What it costs to build

| Piece | Kind | Agent |
|---|---|---|
| `stock_policy.mart.training_tiers` in `data/traders.json`, the items and prices of 4.1 once the owner sets them | data | `datapack-content-dev` |
| `training_shop` in `tools/traders.py`, appended to each clerk's filtered shop by tier, in the offer shape `card_shop` already emits | small generator change | `datapack-content-dev` |
| E1 `never_buy` additions in `data/bank.json` | data | `minecraft-systems-dev` |
| tests: training lines by tier, no Mart/counter duplicate, E1-E2 | tests | `test-author` |
| prices against income; Challenge teams against a trained player; `battle_stress` with a trained-player profile | balance | `trainer-balance-designer` |
| no change to R14 as a step; R14 must be re-run after install to rewrite the 14 clerks, then verified from the world (presence probes, `install_check`) | integration | main session |

No new reapply step, no new mechanism, no new dependency.

---

## 5. Plan (ordered; each step one experiment or one task)

1. **Static jar read, no game:** Audino, Chansey, Blissey `evYield` in the 1.8.0 species data (A-3); the
   `EvCalculator` loop over `evYield` against a zero entry (A-2); the EV items' `accepted` ownership (A-7); the whole
   `HyperTrainingItem` class for a level check (A-6). `cobblemon-researcher`, into `docs/research/`.
2. **P-7 on staging:** buy one authored line from a clerk (the trainer card is already the candidate). Everything in
   B depends on it. Main session (server lock).
3. **EV-1 to EV-5 on staging** (section 6). `minecraft-systems-dev` sets up; `qa-reviewer` grades.
4. Owner answers section 7. Then prices: `trainer-balance-designer`.
5. Data and generator: `datapack-content-dev`. Tests: `test-author`. Different agents (CLAUDE.md principle 16).
6. Integration: install, R14, `install_check`, probes. Main session.
7. Challenge teams against a trained player, per gym: `trainer-balance-designer`, after 6.

---

## 6. Unknowns, as experiment candidates (not added to `EXPERIMENT_BACKLOG.md`: this unit writes one file)

| Id | Question | Blocks |
|---|---|---|
| **EV-0** | Does the 1.8.0 summary screen show EVs and IVs to the player (A-5)? If not, how can a player or an NPC read them (a Molang query, a command)? | whether training is visible at all; option E |
| **EV-1** | A Pokemon at the rctmod cap defeats an Audino: EXP is clamped; do its EVs rise (A-4)? With and without a power item | the grounds as the EV site |
| **EV-2** | A power item's +8 against a species with 0 yield in that stat (A-2); and a participant versus an Exp Share holder (does a non-participant gain EVs?) | the fight counts in 4.2 |
| **EV-3** | A vitamin: +10 per use, 26 reach 252, 510 total clamp; usable on another player's Pokemon? | the shortcut's arithmetic |
| **EV-4** | `fresh_start_mochi` resets all six; a pomeg berry lowers HP by 10 | the undo |
| **EV-5** | The stat formula: one Pokemon's stat at a known level before and after 252 EVs (A-1) | every magnitude here |
| **EV-6** | A hyper-training candy below level 100: does it apply, does the stat change, does it survive a relog, a PC store and breeding? A silver and a gold bottle cap under Cobblemon 1.8.0 (`obc` behaviour is unverified, overlay `:703-705`) | the IV half of the shelf |
| **EV-7** | A cobblecuisine shake: do `lowShakeEv` etc. grant EVs, and can a player make one (recipe, ingredients)? | whether a third, unpriced EV route exists |
| **P-7** | (existing) an authored offer sells from a clerk's or merchant's screen | option B and C |

---

## 7. Owner questions

1. **What does "all items are delegated to traders" mean?** (a) the Mart sells only training and the balls and
   medicine move to the counter beside it (option D: no gate gained, both seller systems rewritten); (b) the Mart
   keeps them and adds a training shelf (option B, recommended); or (c) the late items go to barter villagers (A4),
   which B allows. Default if unanswered: B.
2. **Is "EV training implemented" satisfied by battle training with power items at the grounds, plus a shelf?** Or do
   you want EVs bought outright (vitamins cheap and everywhere)?
3. **Should boss teams carry EVs, in Normal, Challenge, or neither?** Today no authored trainer has EVs or IVs and the
   stress test assumes none.
4. **Vitamins:** keep them as the 3,500 shortcut on Northlight's counter, or make a named decision to override the base
   bank's 2,500 buy-back so they can be sold cheaper (and in more places)?
5. **From which badge should EV training open?** Proposed: power items at tier 1 (gym 2's town).
6. **The grounds give HP EVs to every catch-up team.** Accept "HP first, steer with a power item", or ask for stat
   pens (a second Habitat Block per ground with other yields, a generator change and new siting)?
7. **The prices in 4.1** are placeholders. Yours to set, or `trainer-balance-designer`'s against the income model?
8. **Nuzlocke:** is a training ground part of its sub-region's catch zone, or a zone of its own?
9. **IVs:** sell hyper-training candies late (tier 6), or keep IVs to finds (silver caps by fishing) and the Holdfast
   gold cap?

---

## 8. Premises in the brief, checked

- *Ability Capsule/Patch native, no randomiser; vitamins, feathers, mochi and the reset mochi native*: **confirmed** in
  the research note (`:22-54`, `:78-92`), as source reads, none run in game.
- *About 90 held items native*: **not checked**; the note gives no count and says its list may be incomplete
  (`:145-148`). Nothing here depends on it.
- *The training grounds are a natural EV-training site*: **yes, with a correction**: as rostered they train HP only
  (A-3), and only power items make them general (2.2).
- *The Marts are where EV items would go*: the region's existing EV shop is **Northlight's counter**, not a Mart
  (1.2).
- *43 contract stalls*: I measured 41 stall records in `data/markets.json`; see 2.1.
- The three figures the brief excluded ("THE NURSE: 30 minutes", "237 ambient across 26 settlements", "the four P2s")
  are not used here.

---

## Decisions taken 2026-10-08 (overnight)

Unit MART built option B as data (`data/traders.json` `stock_policy.mart.training`) and generator
(`tools/traders.py` `training_offers` / `training_shop`, appended in `apply_stock_policy` beside the trainer card).
**Nothing was run in game; P-7 (an authored offer sells) is still unproven, and the whole shelf rests on it.** A
question was answered here only where this design recommends one answer and the answer moves no progression gate,
level cap or story beat. Everything else stays the owner's.

**Taken:**

| Q | Call | Why it was mine to take |
|---|---|---|
| 1 | **B**: the Marts keep their basics and tiers and gain a Training category | the design's recommendation and its own stated default if unanswered; no gate moves (2.1: no seller gates per player) |
| 5 | **Power items at tier 1** (gym 2's town), reset mochi and the six EV-lowering berries at tier 2, mochi at tier 3 | the design's proposed table (4.1); EVs touch no level or EXP (4.3), so no cap moves |
| 6 | **"HP first, steer with a power item"** | sections 2.2 and 4 design for exactly this; the alternative (stat pens) is a different system's generator change and new siting, not taken |
| 9 (part) | **Hyper-training candies NOT on the shelf** | the design's own condition, "only if EV-6 passes" (4.1); EV-6 is not run. Whether to sell them once it passes stays the owner's |
| 4 (part) | **Vitamins stay where they are** (3,500 at Northlight's counter, not on any Mart) | the design keeps the shortcuts on the counters (4.1, 4.2); keeping the status quo changes nothing. Overriding the base bank's 2,500 buy-back is still the owner's named decision |

What was built, by tier (the clerk's tier rule is unchanged):

| Tier | Lines (all 19 ids verified in `Cobblemon-fabric-1.8.0+1.21.1.jar`: lang key `item.cobblemon.<id>` and item model) | Price (PLACEHOLDER, 4.1) |
|---|---|---|
| 1 | `power_weight`, `power_bracer`, `power_belt`, `power_lens`, `power_band`, `power_anklet` | 1,500 |
| 2 | `fresh_start_mochi`; `pomeg_berry`, `kelpsy_berry`, `qualot_berry`, `hondew_berry`, `grepa_berry`, `tamato_berry` | 1,000; 300 |
| 3 | `health_mochi`, `muscle_mochi`, `resist_mochi`, `genius_mochi`, `clever_mochi`, `swift_mochi` | 800 |

The early-reach clerks price the shelf by `early_reach_pricing` like any tier line: at Sunset West (reachable at 0)
tiers 1-2 are in the convenience band (x2: power items 3,000, reset mochi 2,000, berries 600) and the mochi (tier 3)
behind the income gate (28,700, from `income_basis`, RELAYED); at Pacifidlog (priced for 6 badges, the owner
2026-10-08) every training line is at its normal price.

Economy (4.2): none of the 19 ids is bought by `data/bank.json`, the generated `modpack/config/cobbledollars/bank.json`
or the base bank (grep; the one `_mochi` hit is `potato_mochi`), and no vitamin is on the shelf, so the vitamin rule
holds. `tools/economy_audit.py` found **0 arbitrage failures** with the shelf emitted (669 sale offers, from 479); its
190 FAILURE lines are all one rule, "neither a Mart basic nor a tier line": the independent audit predates the
Training category and must be taught it (test-author). E1 (`never_buy`) is not done: `data/bank.json` is not this
unit's.

**Left to the owner:**

- **Q2** whether battle training plus a shelf satisfies "EV training implemented".
- **Q3** whether boss teams carry EVs (Normal, Challenge, neither): it changes every gym's difficulty.
- **Q4** overriding the base bank's 2,500 vitamin buy-back.
- **Q7** the shelf's prices: shipped as the 4.1 placeholders, not derived.
- **Q8** whether a training ground is its own Nuzlocke zone.
- **Q9** whether to sell the hyper-training candies at all once EV-6 passes.
