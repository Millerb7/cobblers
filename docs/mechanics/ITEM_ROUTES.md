# Item routes: every item attainable, gated where its power says so

**Status (2026-10-07):** design only, unit A6 of Wave A. Nothing here is built, priced by the owner, or run in game.
No data file was edited. Each route names the system that would carry it and whether it needs new data, a new
record, a generator change or a decision.

**The ask.** The owner, 2026-10-07 (`docs/STATE.md` "What is decided", the morning-report answers, item 9): "every
item attainable" -- "for sure, but not for speedruns necessarily, they can be gated". The standing rule beside it
(the owner, 2026-09-24, same section): every Cobblemon item reachable **through natural sources alone** (world
finds, rewards, trainers, shops, fishing, events), so a no-crafting run works.

**Evidence read for this file** (not summaries of it): `docs/UNFINISHED_SWEEP_2026-10-06.md` section 4;
`docs/research/OBTAINABILITY_SWEEP_2026-10-05.md`; `docs/research/OBTAINABILITY_MODS.md` section 1;
`docs/research/OBTAINABILITY_VANILLA_COBBLEMON.md` sections 1 and 3; `docs/research/notes/lumymon-altars.md`
section 2; `docs/mechanics/MATERIAL_EXCHANGE.md` sections 1-4; `docs/mechanics/LEVEL_CATCHUP.md` section 2; and the
data files cited by line below.

**Number labels.** *measured* = counted or read in the named file and line by this unit; *relayed* = taken from the
named document without re-measuring. Nothing here uses the three unsourced figures the brief names.

---

## 0. Premises checked first (five are wrong or incomplete)

| # | Premise (as relayed) | What the files say | Effect on this design |
|---|---|---|---|
| P1 | "The 11 items" | No document says 11 (the sweep says so itself, `UNFINISHED_SWEEP_2026-10-06.md:84`). It reproduces as the **11 rows** of that section's table, lines 92-102 (*measured*). A row holds up to 18 items, so "11 items" is 11 rows of about 80 ids | Routes below are per row and per item inside a row |
| P2 | "The Dubious Disc ... blocks Porygon-Z" | **The Disc already has a route**: `data/markets.json:306`, Northlight's Station Supply, `exchange_for` 3 netherite ingots = $2,700 (*measured*), authored on 2026-10-06 by the material exchange (`MATERIAL_EXCHANGE.md` section 4 table). STATE line 127 says the exchange was applied to staging that night (*relayed*). The sweep's row 10 missed it. A purchase from any merchant is still proof P-7, never run | Row 10 shrinks to the Sachet and the two cosmetic items -- **but** under the no-crafting rule Porygon-Z is still blocked one step earlier, by the Upgrade and the Link Cable (section 4) |
| P3 | "Mewtwo's DNA grant is dead without `cloning_catalyst`" | Half true. `lumymon:ancient_dna` has **two** uses: Mewtwo's Cobbleverse fossil (DNA + catalyst; `OBTAINABILITY_MODS.md:62`, *relayed*) and **Mew's Origin Fossil** (`lumymon:ancient_dna` + 5 x `#cobblemon:fossils` + `cobblemon:ancient_origin_ball`, jar `recipe/origin_fossil.json`; `lumymon-altars.md:141`, *relayed* as VERIFIED). Mew is sited and Blue's first win gives the Ancient Origin Ball (`data/progression.json:3614`, *measured*). So the DNA is live for Mew | **"Drop the DNA", the sweep's second option, would remove a live Mew input.** Keep it (section 2.2) |
| P4 | Row 9: "Griseous: nothing (... Giratina not adopted)" | **Giratina is adopted**: the Distortion shrine at (4374, 66, 2862), applied to staging (STATE line 127, *relayed*); `data/adopted_legendary_sites.json:936` gates it on `champion_cleared` and says some of its spawn strings hold `mega_showdown:griseous_core` (*measured*). Also **Darkrai is adopted** (Newmoon Island, same STATE line), while `data/gulch_mine.json:2873` still lists `zamega:darkranite` as "left out ... for Pokemon nobody can catch here" (*measured*): stale | The Griseous Core joins blocker 3. The Darkranite is a follow-on for whoever owns the Cutters |
| P5 | Shrew Station's issuing is OFF | `data/research_station.json:159` says `"issuing": true` (*measured*); STATE line 134 still says "issuing is still OFF". The data and STATE disagree | No route here depends on the station; recorded as a disagreement for the orchestrator |
| P6 | The four blockers are what blocks something | They are what blocks something **when crafting is allowed**: the 2026-10-05 sweep's tier A includes crafting and every station (`OBTAINABILITY_SWEEP_2026-10-05.md` section 0), and its own section 8 says "A no-crafting audit is still owed". Under the 2026-09-24 rule more things block: the Link Cable, the Upgrade, the fossil machine, the Origin Fossil, the pots and teacups | Section 4 lists what reading this unit's evidence surfaced; section 6 is the audit that finds the rest |

Also: "Gyms and the League hand out 23 TMs" (sweep row 1) is the **pool**, not the hand-out. The nine
`first_win_rewards` entries carry 25 TM entries, 23 distinct, but each leader gives **one** of its `one_of` list
(`data/progression.json:3586-3687`, *measured*: Fire Blast appears three times, at Blaine and twice at Giovanni;
Blue's list is empty). **A player is sure of eight TMs from the gyms**, plus the Overheat TM in the Victory Road
Slagworks cache (`data/rewards.json:90-93`, *measured*).

---

## 1. The gating principle

One rule, three tests, applied to every route below.

**An item is gated at the first point where the thing it unlocks can be used, unless having it there would replace
the intended answer to the next boss; then it moves to after that boss.**

1. **Usable-at.** Gate no earlier than the item can do anything: an evolution item at the band where its species and
   evolution level are reachable (`data/spawns.json` tier and level), a legendary's item with the legendary's own
   gate. Earlier is harmless but noise; later is the "arbitrary hard-counter" the balance philosophy forbids.
2. **Answer check.** If the item would make one Pokemon the only sensible answer to a fight it precedes (Primal
   Groudon before the League is the case in point), move it past that fight. The level caps already bound raw
   levelling (`LEVEL_CATCHUP.md` section 2: candies are clamped, *relayed* as VERIFIED from source, not run); items
   that add base stats or erase a type matchup are what the caps do not bound.
3. **Renewable unlocks are priced as permanent.** A mint seed, a brewing stand or a Link Cable is bought once and
   works forever, so it is priced and placed as the last rung of what it unlocks, not the first.

**Which gate a system can express** (this decides where an item goes):

| System | Gate it can express | Per player? | Status |
|---|---|---|---|
| `data/progression.json` `first_win_rewards` (`loot give @s` on the leader's flag) | the leader's flag | yes, once, to the winner | data only; whether it gives in game NOT VERIFIED by this unit |
| `data/rewards.json` caches (ADR-002) | a place, plus `requires_flags` (field documented at `rewards.json:16`, *measured*) | yes, once | "The two-player grant is unproven (ADR-002)" (`rewards.json:3`, *measured*) |
| `data/quests.json` `grant_reward_once` via dialogue | any flag the dialogue checks | yes, once | used by the Abandoned Cut's npc_grant (*relayed*, `rewards.json:4`) |
| `data/markets.json` counters (CobbleDollars merchants) | **only the town's position on the road**: the merchant screen shows one list to everyone (`counters_are_merchants`, *relayed* from the `gate_dropped` notes, e.g. `markets.json:273`) | unlimited stock, so effectively yes | purchase NOT RUN (proof P-7) |
| `data/markets.json` `exchange_for` lines | as counters; the price must equal count x the bank's price (`MATERIAL_EXCHANGE.md` section 1) | as counters | as counters |
| `data/traders.json` Mart tiers | the town's tier (`traders.json:570-583`, *measured*) | as counters | NOT run in game (`traders.json:580`) |
| A vanilla villager with fixed `Offers` (unit A4, **EXP-055**) | the villager's position; the cost item itself (netherite needs the Nether) | **ASSUMED shared**: vanilla offers count `uses` per villager, for everyone | **UNPROVEN**; no `experiments/EXP-055-*` exists in this checkout (*measured*, glob) |

The owner's answer (4) of 2026-10-07 lets an early-reachable town sell late stock if its **price** is out of reach
early. Since merchants cannot gate per player, the price is the gate wherever a merchant carries a power item.

---

## 2. The four blockers, with a recommendation each

### 2.1 Type gems and crafted TMs (row 1)

**What is blocked.** Every crafted TM: none of 3,596 TM recipes is craftable from renewable inputs, and 805 name a
type gem outright (`OBTAINABILITY_SWEEP_2026-10-05.md` section 4 row P0, *relayed*). Under the no-crafting rule the
gems are beside the point: a no-crafting run needs **finished TMs**, so the gem question answers itself.

**Recommendation: sell finished TMs; do not sell gems.**

- **Item ids:** TMCraft's plain `tmcraft:tm_<move>` items, the ones the first wins already give
  (`progression.json:3593` ff., *measured*). They fit a merchant offer as a bare id. `cobblemon:technical_machine`
  needs its `cobblemon:tm_move` component (`rewards.json:92`, *measured*); whether a CobbleDollars offer's ItemStack
  keeps a component is NOT VERIFIED (`MATERIAL_EXCHANGE.md` section 1 reads the Offer as an ItemStack, *relayed*), so
  do not route through it until that is checked.
- **Route A (per player, data only, recommended first):** the TMs a player did **not** roll from a leader. After
  gym N, that leader's whole `one_of` list becomes buyable at a counter in gym N's town or later. This makes all 23
  pool TMs attainable for every player without changing the first-win drop. *Build:* new lines in
  `data/markets.json` on existing counters (datapack-content-dev); the town is the gate.
- **Route B (team building, needs a decision):** at each town, the TMs that answer the **next** gym's type, priced
  out of reach before that gym's band (owner answer 4). This is the balance philosophy's "plausible answers in the
  accessible region" made concrete. Which moves per town is a per-gym answer check, done when the owner's team
  rewrite lands (STATE item 13, parked); not authored here.
- **Route C (EXP-055):** the strongest coverage TMs (Earthquake, Ice Beam class) as item-for-item trades for
  netherite or diamonds. Rests on EXP-055.
- **Gate fit.** A TM is the cheapest team-building lever and the one the level cap does not bound; selling a gym's
  own TMs only after that gym, and counter-TMs priced to land in the band before the next one, keeps every TM an
  answer rather than a skip.

**Decision needed:** whether "every item" means every one of TMCraft's ~930 TMs (`OBTAINABILITY_MODS.md:56`,
*relayed*) or a curated set (Q1); and whether TMs stay single-use (`consumeMoveItemOnUse`, a game rule named in
`OBTAINABILITY_MODS.md:57`, *relayed* as VERIFIED in the jar's lang; Q2). A permanent TM changes how many lines are
needed by an order of magnitude.

### 2.2 `lumymon:ancient_dna` and Mewtwo (row 7)

**What is blocked.** Mewtwo only. The DNA itself feeds Mew (premise P3). Mewtwo's fossil needs the DNA and
`cloning_catalyst`, whose only source is `team_rocket_admin_atena`, which never spawns (`OBTAINABILITY_MODS.md:62`,
*relayed*).

**Recommendation: keep Giovanni's DNA; decide Mewtwo; if Mewtwo is in, give the catalyst and a second DNA at the
Champion, not at Giovanni.**

- **Route:** `data/progression.json` `first_win_rewards.trainers.kanto_champion_blue.items` (today the trophy and the
  Ancient Origin Ball, `progression.json:3612-3615`, *measured*) gains the catalyst and one more `lumymon:ancient_dna`.
  *Build:* one data edit; the generator already emits the list.
- **Why a second DNA:** both fossils consume a DNA, so one DNA forces a player to choose Mew or Mewtwo. The Mew
  temple's own container also holds one (`lumymon-altars.md:139`, *relayed*), but a container is first-come and
  server-wide until Lootr lands (STATE item 8); a first win is per player.
- **Gate fit:** Mewtwo at the League would be the only sensible answer to it; after the Champion it is a postgame
  prize, where Mew already sits (Mew's wall opens for `defeat_champion_blue`, `adopted_legendary_sites.json:139`,
  *measured*).
- **Not verified, must be read before the edit:** the catalyst's namespaced id (no file read by this unit names it);
  the revived Mewtwo's level (DP-v31 `data/cobblemon/fossils/mewtwo.json`); that a fossil revive needs the
  Resurrection Machine, which is itself crafting-only (section 4).
- **Follow-on:** Mewtwonite X and Y are in the Cutters' `left_out` (`gulch_mine.json:2863-2864`, *measured*); if
  Mewtwo is in, they move to the Cutters' owner.

### 2.3 Legendary and form items: memories, Red Orb, Prison Bottle, Griseous Core (row 9)

| Item | Unlocks | Route | Gate | Build |
|---|---|---|---|---|
| **17 Silvally memories** | Silvally's types. Type: Null is a mythical starter; it becomes Silvally at **L45** and learns Multi-Attack then (`data/mythical_starters.json:404-414`, *measured*); its peak is gym 8 (`:327-331`) | **Recommended:** 17 cheap lines on Northlight's Station Supply (a research station studying an artificial Pokemon; the town is at the gym-6 rung, `markets.json:285`, *measured*). **Alternative, per player:** the gym-type memory in each Kanto leader's first win (8 of 17) plus the rest at the Champion | town position (Northlight). Memories are inert before L45, so earlier costs nothing | new lines in `markets.json`; the bank must not buy them back (economy audit) |
| **Red Orb** | Primal Groudon (held item; ASSUMED from Mega Showdown 1.0.2's item list, form trigger not read) | a `requires_flags` cache in Groudon's chamber (`data/legendaries.json:489-516`, sealed chamber under the Craters) | **`champion_cleared`, not Groudon's own `gym8_cleared`** (Groudon's gate is itself "PROPOSED, NOT DECIDED", `legendaries.json:503`, *measured*). Primal Groudon adds base stats and an ability that erases Water moves: in the League it would be the answer, not an answer (test 2) | new record in `rewards.json` with coordinates from the chamber build (world-content-dev places, datapack-content-dev emits); a decision (Q5) |
| **Blue Orb** | Primal Kyogre | the same, in the Kyogre cave when it is built (`docs/world-building/KYOGRE_CAVE.md`, designed, not built) | as the Red Orb | add to that design's build |
| **Prison Bottle** | Hoopa Unbound | a `requires_flags` cache inside the cradle (`data/hoopa_cradle.json:14`, spot (3357, 13, 3306), *measured*) | `rift_crisis_resolved`, Hoopa's own gate (`hoopa_cradle.json:19`, *measured*). Hoopa is level 60, after gym 8 (`:17-18`); the Unbound form changes Hoopa only | new reward record; ASSUMED that Mega Showdown 1.0.2's bottle changes the form (the cradle's own runtime checks leave the model question open, `hoopa_cradle.json:59`) |
| **Griseous Core** | Giratina Origin | add to the Giratina altar's cache (`sweep_red_chain`, named in `adopted_legendary_sites.json:936`, *measured*) | `champion_cleared`, Giratina's gate | one edit to an existing reward record; the id is relayed from Giratina's spawn strings, so verify it in the jar |
| Plates (17) | Arceus forms; possibly type-boosting held items for any Pokemon (ASSUMED, Showdown behaviour, not read for Mega Showdown 1.0.2) | none recommended: no Arceus, and the type boosters Cobblemon already ships do the same job | n/a | a decision (Q4) |
| Griseous Orb | as the Core, if Mega Showdown 1.0.2 keeps both ids (not read) | with the Core | as the Core | verify |

**Recommendation in one line:** each item with its species, at its species' gate, except the two Primal orbs, which
wait for the Champion.

### 2.4 Dubious Disc and Sachet (row 10), and the cosmetic pot and teacup

- **Dubious Disc:** routed already (premise P2): Northlight exchange, 3 ingots. Nothing to build; proof P-7 to run.
- **Sachet** (Spritzee to Aromatisse; Spritzee is tier 3, L18-28, weight 6 in `fungal_north`,
  `data/spawns.json:1495-1504`, *measured*): **one `exchange_for` line at Fossick's Mine Stores and Exchange**, 18
  diamonds = $2,160, the same rung and rule as the Metal Coat beside it (`markets.json:273`, *measured*). Gate fit:
  Aromatisse is a modest final stage whose base is mid-game; Fossick is the gym-3 rung (`markets.json:257`). The
  fiction is weak (a mine selling perfume); the alternative is Northlight beside the Disc at 3 ingots, a later rung
  for a weaker item. *Build:* one line.
- **Whipped Dream:** no route needed; Swirlix is not in `data/spawns.json` (*measured*, no match).
- **Chipped Pot, Masterpiece Teacup** (Antique Polteageist, Artisan Sinistcha; cosmetic): two lines at Steepside, the
  tea town (`steepside_tea_front`, `markets.json:643`). Early-reachable and ungated, so priced high (owner answer 4).
  *Build:* two lines. With them, the **Cracked Pot** and **Unremarkable Teacup** the base evolutions need, if the
  audit confirms they have no natural source (no seller names them, *measured*: `cobblemon:cracked_pot` and
  `cobblemon:unremarkable_teacup` appear only in `data/blackout.json`). Polteageist itself is catchable wild from tier
  6 (`spawns.json:12062`, *measured*), which softens the pot.

**But the chains are longer than these items** (section 4): Porygon-Z needs the Upgrade first and, solo, two Link
Cable uses; Aromatisse needs a Link Cable solo. Routing the Disc and the Sachet alone does not open either in a
no-crafting solo run.

---

## 3. The rest of the eleven rows

| Row | Item(s) | Route | Gate and why | Build or decision |
|---|---|---|---|---|
| 2 | **Mint seeds** (6) | six lines at Northlight's Station Supply, beside the vitamins (`markets.json:298-303`, *measured*) | gym-6 rung: a nature is a permanent stat change with no cap bound (test 2 is mild), and one seed is renewable forever (test 3) | six lines; price the owner's |
| 3 | **Dynamax** (band, wishing star, max mushroom, power spot) | none until decided. If kept: band and a Power Spot as one post-Champion reward | Dynamax needs a Power Spot within 32 (`powerSpotRange`, *relayed* `OBTAINABILITY_MODS.md:59`) | **decision first** (Q6): `dynamax: false` is a config change, not this unit's |
| 4 | **Brewing stand** (or a blaze rod) | one line at Northlight | not before the Ability Capsule's own seller (Northlight, 10,000, `markets.json:304`): a stand makes capsules renewable from dragon's breath (four rostered droppers, *relayed*) | one line; price at or above the capsule's |
| 5 | **Exp. Candies, Rare Candy** | lines at the gym-town counters from gym 4 on, or as training-ground prizes | the cap clamps them and a candy is not used up at the cap (`LEVEL_CATCHUP.md:31`, *relayed* VERIFIED from source, not run), so the gate is economic, not power: the curve has no room at badges 1-3 (`LEVEL_CATCHUP.md:22-23`, *relayed*) | lines; the owner's (candies are "cut by design" today) |
| 5 | **PP Up, PP Max** | one line each at Holdfast (gym-8 rung) | convenience; late | two lines |
| 5 | **Ability Patch** | already routed: arena prize at rank 7 and streak 50 (`OBTAINABILITY_SWEEP_2026-10-05.md:155`, *relayed*) | hidden abilities are late power | none |
| 6 | **Ancient balls** (15) | the Ancient Origin Ball: Blue's first win (`progression.json:3614`, *measured*). The other 14: a late off-path counter | the Origin Ball is a Master Ball (post-Champion is right); the rest are throw-arc variants, convenience | lines; the owner may cut them (Q7) |
| 6 | **Beast Ball** | none unless an Ultra Beast is offered | nothing uses it | declare out (Q7) |
| 8 | **Plain bottle cap** | one line beside the gold cap at Holdfast (*relayed* sweep row 8) | one-stat hyper-training at the gym-8 rung, under the gold cap | one line |
| 11 | **LumyMon's nine Kanto locators** | none: they are already craftable and are misleading, not missing | n/a | a generator change (`progression_pack.py upstream_neutralised` recipe kind) or leave them; Q8 asks whether a deliberately disabled item counts against "every item" |

Rows the sweep had already closed: fossils (the Scorchbone Dig), the Z-Ring (the Raw Tear cache), the Ability
Capsule (Northlight) and the decorative Legendary Monuments blocks (*relayed*, `UNFINISHED_SWEEP_2026-10-06.md:86`).
The fossils are closed only with crafting (section 4).

---

## 4. No-crafting gaps found while reading (outside the eleven rows)

Not an audit: these are what this unit's evidence surfaced. Each fails the 2026-09-24 rule because its only route
is a recipe.

| Item | What it blocks | Evidence | Proposed route | Gate |
|---|---|---|---|---|
| **Link Cable** | solo trade evolutions: 18 rostered families (Onix, Scyther, Porygon, Seadra, Feebas, Machoke, Graveler and others) | recipe needs quartz and an ender pearl (`OBTAINABILITY_VANILLA_COBBLEMON.md:118`, *relayed*); no seller in `data/` (*measured*: only `blackout.json:111`) | one line at Fossick (gym-3 rung), diamond-priced | co-op trades between friends already do this (ASSUMED in that doc); a cable gives a solo player what a party has. Q9 |
| **Upgrade** | Porygon to Porygon2, hence Porygon-Z | recipe: a redstone lamp and a blank TM (`OBTAINABILITY_VANILLA_COBBLEMON.md:122`, *relayed*); no seller (*measured*: only `blackout.json:118`). Porygon is common in the Displaced City cavern, L32-45, weight 12 (`spawns.json:21842-21847`, *measured*) | one line at Northlight beside the Dubious Disc, 3 ingots | the Disc's rung, so the two halves arrive together |
| **Fossil machine** (analyzer, restoration tank, monitor) | every fossil revive, Mewtwo's included | `data/fossil_dig.json:157-158` lists only recipes for the three parts (*measured*) | the three parts as a reward from the dig's foreman (an npc_grant, per player) | the dig's own reach |
| **Origin Fossil** | Mew | crafted from the DNA, 5 fossils and the Origin Ball (`lumymon-altars.md:141`, *relayed*) | give `lumymon:origin_fossil` itself at the Champion, or keep the craft and accept Mew as the one crafted legendary | `champion_cleared` (Mew's own). Q3 |
| **Cracked Pot, Unremarkable Teacup** | Sinistea and Poltchageist's base evolutions | no seller (*measured*); routes otherwise unread | with the cosmetic pair at Steepside (2.4) | price |
| **Evolution stones** | ten species families | the faces in `data/mines.json` yield ore that is smelted (*relayed*, `OBTAINABILITY_SWEEP_2026-10-05.md:60-63`); the sellers (Steepside, the Assayer) sell finished stones | already routed by the sellers, **if** smelting counts as crafting | Q10 asks whether smelting, brewing and the campfire pot count |

---

## 5. If unit A7's "Marts as EV/IV hubs, items delegated to traders" is adopted

This file does not decide A7's question. If it is adopted:

- **Would move into the Mart hub:** the mint seeds (row 2), the plain bottle cap (row 8), the PP Up/Max (row 5), and
  the vitamins they sit beside at Northlight today. They are EV/IV/nature items.
- **Would move if "traders" means a different seller from today's counters:** every route above that names a
  `markets.json` counter (TMs, memories, Sachet, pot and teacup, brewing stand, Link Cable, Upgrade, candies, ancient
  balls). They are written against the counter mechanism, which is the same CobbleDollars merchant a trader is, so
  the move is a change of seller, not of design.
- **Would not move:** first-win items, caches, dialogue grants (the DNA, catalyst, Origin Fossil, Red and Blue Orbs,
  Prison Bottle, Griseous Core, the fossil machine) and EXP-055 trades.
- **No route here is placed on a Mart clerk's tier list** (`traders.json:570-579`), deliberately, so A7 reshaping the
  tiers breaks nothing in this file.

---

## 6. Routes resting on unproven mechanisms

- **Every merchant line** (counters and exchange lines): a CobbleDollars purchase has never been run in game (proof
  P-7; `markets.json` status, *relayed*). This includes the Dubious Disc that already exists.
- **Every cache** (Red Orb, Blue Orb, Prison Bottle, Griseous Core): ADR-002's two-player grant is unproven
  (`rewards.json:3`, *measured*).
- **Every first-win addition** (catalyst, second DNA, Origin Fossil, memories alternative): the `loot give` path was
  not checked in game by this unit.
- **EXP-055 (unit A4, unproven):** only Route C for TMs (2.1) rests on it, and the owner's netherite-for-Master-Ball
  shape, which already has a dollar route (`markets.json:305`). No blocker's recommended route depends on it.
- **Form changes** (Primal orbs, Prison Bottle, Griseous Core, memories): that holding or using the item changes the
  form under Mega Showdown 1.0.2 is ASSUMED, not read.

---

## 7. Brief for the full audit (for a later test-author; not built here)

**Question:** for every item id the server can register, is there at least one **natural** route (no recipe), and
at which gate?

**Enumerate the items from the jars, not from our data** ("our list is not the world"):

1. The server's mod jars and global datapacks: the 2026-10-05 snapshot at
   `C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/` (101 of 102 jars identical to the profile
   the sweeps used, *relayed* `OBTAINABILITY_SWEEP_2026-10-05.md:24`), opened offline with `zipfile`. Never the live
   server folder, and note that `rewards_pack.py` refuses a server-shaped directory without the lock (same
   document, section 6).
2. Ids from `assets/<ns>/lang/en_us.json` `item.*` and `block.*` keys, cross-checked against
   `assets/<ns>/models/item/*.json`, as the 2026-10-05 sweep did. Known blind spots of that method: colour-variant
   items without a base lang key, and anything registered in code only.
3. As an independent check, a registry dump from a staging boot (a command listing `minecraft:item` registry
   entries). Whether such a dump is available on 1.21.1 Fabric without a mod is NOT VERIFIED: an experiment
   candidate, not an assumption.

**Count only these sources** (each with its gate and whether it is per player, server-shared, finite or renewable):
terrain and block drops; fishing loot tables; drops of species with weight above zero in `data/spawns.json` (and
Pasture Loot's farming of them, ASSUMED to work as configured); `data/markets.json` lines; `data/traders.json`
Marts with their tiers and the BCA templates' filtered shops; `data/bank.json` exchanges; `data/rewards.json`;
`data/quests.json` grants; `data/progression.json` first wins; `data/research_station.json` items **with the issuing
state**; `data/arena_fights.json` prizes; `data/mines.json` faces; `data/gulch_mine.json` Cutters; the fossil dig;
EXP-055 villager offers once proven; Lootr loot tables once decision 8 lands. **Exclude** crafting, and whatever
the owner rules on smelting, brewing and the campfire pot (Q10).

**Declarations, not silence.** An item with no route must be either routed or **declared out** in a data file
(proposed: `data/item_routes.json`, one entry per id or id pattern, with the reason and the owner's decision), the
way `data/id_authorship.json` declares shared ids. The audit fails on an undeclared gap and on a declaration whose
id set no longer matches.

**Independence.** The audit's item list comes from the jars and its route list from the seller files; it must not
import the generators' own item lists. Its mutation test removes a line in a **generator's** output path (for
example, drop one stock line inside `tools/markets.py`'s emission, data untouched) and must then report that item
as a gap.

**Report:** counts per mod (routed / declared out / gap), and the gaps by what they block, in the
`OBTAINABILITY_SWEEP_2026-10-05.md` section 4 shape. Written to a file; only failures read back.

---

## 8. Multiplayer

- First wins, caches and dialogue grants are **per player, once**: right for every legendary-form item and for the
  catalyst and DNA, since each player raises their own team.
- Merchant lines have unlimited stock (a missing `Stock` is -1, `MATERIAL_EXCHANGE.md` section 1, *relayed*), so
  they are per player in effect, and **one price for everyone** (no per-player gate).
- EXP-055 villager trades are ASSUMED to share `uses` server-wide; a trade meant for every player needs a high
  `maxUses` or a restock, which A4's experiment should measure.
- Containers placed in the world (the Mew temple's DNA) are first-come and server-wide until Lootr (decision 8):
  never the only route to a per-player item.

---

## 9. Owner questions

1. **"Every item" and TMs:** every one of TMCraft's ~930 TMs (*relayed*), or a curated set per town plus the first-win
   pools?
2. **TMs single-use or permanent** (`consumeMoveItemOnUse`)? Permanent TMs cut the lines needed by an order of
   magnitude and make a first-win TM a lasting unlock.
3. **Mew and Mewtwo:** is Mewtwo in the game (post-Champion, catalyst and a second DNA at Blue)? And under the
   no-crafting rule, should Blue give the Origin Fossil itself rather than its ingredients?
4. **Items for species not in the game** (the 32 Mega Stones in the Cutters' `left_out`, *measured*
   `gulch_mine.json:2847-2881`; plates, drives, masks, LumyMon relics and radars): are they part of "every item", or
   declared out? (Darkranite should leave that list either way: Darkrai is adopted.)
5. **The Primal orbs at `champion_cleared` rather than at Groudon's and Kyogre's own gate?** The recommendation is
   yes, because Primal Groudon before the League is a single answer, not a plausible one.
6. **Dynamax:** off (`dynamax: false`), or kept with a post-Champion band and Power Spot?
7. **Ancient balls and the Beast Ball:** routed at a late counter, or declared out?
8. **A deliberately disabled item** (the Kanto locators, if their recipes are emptied): does it count against
   "every item"?
9. **The Link Cable for solo players:** at the gym-3 rung, or later? Without it, solo players lose 18 rostered
   evolutions (*relayed*); co-op players have each other.
10. **What counts as crafting** for the no-crafting rule: smelting (every stone face yields ore), brewing (the
    Ability Capsule), the campfire pot (the Revive the fossil machine needs)?
11. **Memories:** one cheap seller at Northlight (recommended), or per-player at each gym's first win?
12. **Prices:** every line here needs one; the exchange rule (count x the bank's price) fixes the exchange lines, the
    rest are the owner's, and early-town lines must be out of reach early (answer 4).

---

## Decisions taken 2026-10-08 (overnight)

### Cache routes

Unit REWARD built the section 2.3 caches whose answer the design already gives. All are ADR-002 caches in
`data/rewards.json`, generated by `tools/rewards_pack.py` into `cobblers_rewards`. Every item id was read at its
model path in `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar`, in the **offline server snapshot**
`C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods`. The live server's mods folder was not read,
because that needs the coordination lock. No block is added to any world. Each container is a block that its place's
own builder already writes, so no carve and no audit derivation changes.

| Item | Record | Place and container | Trigger box | Gate | Placed by |
|---|---|---|---|---|---|
| Red Orb (`mega_showdown:red_orb`) | `groudon_red_orb` | Groudon's chamber; the smooth-basalt pedestal under Groudon, (6672, 68, 5542) | (6668, 68, 5538)-(6676, 71, 5544) | `champion_cleared` | the pedestal is `tools/legendaries.py`'s carve, R14L |
| Prison Bottle (`mega_showdown:prison_bottle`) | `hoopa_prison_bottle` | Hoopa's cradle; the dais centre's crying obsidian (`rift_seep`), (3357, 12, 3306) | (3355, 12, 3304)-(3359, 15, 3308) | `rift_crisis_resolved` | `tools/relic_underground.py`'s dais, R9RU |

- **Coordinates come from plan data, never a world.** The Red Orb's come from `legendaries.geometry()` on the
  canonical heightmap: chamber x6662-6682, y69-79, z5524-5544. The Prison Bottle's come from `data/hoopa_cradle.json`
  `spot` and `data/relic_underground.json` `geometry.cradle`. Each place's record now carries `cache`
  (`data/legendaries.json` groudon, `data/hoopa_cradle.json`). Its generator fails closed if the reward's container
  or trigger leaves the block it names (`legendaries.cache_problems`, `hoopa_cradle.cache_problems`). Moving
  Groudon's `drop` by one block was checked and caught.
- **Red Orb at `champion_cleared` and not at `gym8_cleared`.** This is the design's recommendation, but Q5 is still the
  owner's. To change it, edit the one `requires_flags` entry. A player who opens the chamber with eight badges earns
  nothing there and can come back after the Champion.
- **Griseous Core: NOT built, blocked by the audit.** Two shapes were tried and both fail an audit this unit may not
  extend:
  - Adding the item to `sweep_red_chain` breaks `tools/legendary_sweep.py` and `tools/legendary_sweep_audit.py`, which
    both hold that record to exactly one item, the altar's activation item.
  - A second record (`giratina_griseous`) with the same trigger and container fails the hidden-site clearance rule
    (`authored point (4393, 2878) in data/rewards.json is 0 from the footprint edge`). That rule's skip set excludes
    only the cache that holds the activation item.

  **Needs a test-author:** let a sweep site declare extra caches of its own, skipped by both clearance checks and
  exempt from the one-item contract. The record was drafted and then removed. Its shape: `sweep_red_chain`'s trigger
  and container, `requires_flags` `champion_cleared`, and contents `mega_showdown:griseous_core` and
  `mega_showdown:griseous_orb`, one of each. Both ids were verified in the jar.
- **Griseous Orb goes with the Core when the Core is built.** The jar keeps both ids. The Orb's only route is the
  jar's `recipe/griseous_orb.json`, which needs `cobblemon:ghost_gem` and `cobblemon:dragon_gem`, and section 2.1
  says nothing in our world drops those gems.
- **Not built, by the brief:** the Blue Orb (the Kyogre cave is not built), and the catalyst and second DNA (Q3, "if
  Mewtwo is in"). Nothing else in this file is both a cache or first-win route and free of an owner question. The
  memories alternative is Q11 and the Origin Fossil is Q3. The fossil machine is an npc_grant that needs a quest and
  dialogue, so it is not a cache.
- **Unproven:** the ADR-002 two-player grant (section 6). Also unproven is that either item changes the form under
  Mega Showdown 1.0.2. The jar ships `effect/red_orb.json` and `effect/prison_bottle.json`, but the trigger was not
  read. Neither cache has been run in a world.

### Exchange and counter lines (unit EXCH)

Unit EXCH, on the owner's 2026-10-08 answers (`docs/STATE.md`: "Players trade at Northlight's counter. One place, so
the economy has a centre"; "the exchange should be an alternative path, not a bypass"). Built in `data/markets.json`
(generator `tools/markets.py`, placed by R17M); nothing here has been bought in game (proof P-7). Every item id was read
in the jars of the 2026-10-05 server snapshot (`C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods`),
not the live server folder, which this unit did not open; `python tools/markets.py ids` found all 219 sold ids.

| # | Decision | Why |
|---|---|---|
| D1 | **Route A for TMs, the leaders' pools only (Q1 answered for stage 1 as "curated": 23 TMs, not ~930).** Every distinct TM in the nine `first_win_rewards` `one_of` lists is a counter line: Brock's, Misty's and Surge's ten at **Fossick**, Erika's, Koga's, Sabrina's, Blaine's and Giovanni's thirteen at **Northlight** (Fire Blast once, under Blaine) | A counter cannot gate per player (`counters_are_merchants`), so the town is the gate. The critical-path counters cannot carry them: the price curve (`tools/markets.py curve`) already asks 0.65-0.70 of income against a 0.70 target, and one TM per counter breaks it. The two off-path exchange counters are not on the curve; Fossick is the gym-3 rung, Northlight the gym-6 rung, so the first three leaders' TMs land after their gyms and the last five at the one centre |
| D2 | TM ids are TMCraft's finished `tmcraft:tm_<move>` items, each read as `assets/tmcraft/models/item/tm_<move>.json` in `tmcraft-1.4.19+1.8.0.jar` | They have no lang key, so `tools/markets.py ids` now also accepts an item model (as `tools/economy_audit.py` already did). `cobblemon:technical_machine` stays out (its move component in a merchant offer is unverified, 2.1) |
| D3 | TM price: **5% of the road's cumulative income at the leader's badge** (`income_basis`), rounded to $100: $500, $900, $1,400, $2,300, $3,000, $4,100, $5,500, $7,300. PROPOSED, the owner's (Q12) | One rule, rising with the road. Blaine's and Giovanni's TMs sit at Northlight's gym-6 rung ahead of their leaders, so their price is their gate (answer 4) |
| D4 | **The 17 memories at Northlight** (`mega_showdown:<type>_memory`, lang keys in `mega_showdown-fabric-1.0.2`), $1,000 each, PROPOSED (Q11 answered with the recommendation) | The design's recommended seller; inert before Silvally at L45, and the bank buys none back |
| D5 | **The Sachet at Fossick**, an exchange line, 18 diamonds = $2,160 (`cobblemon:sachet`) | The design's recommendation. The one-centre rule is about where players trade item for item (the barter now stands at Northlight); the money counters elsewhere stay, and Northlight is a later rung for a weaker item |
| D6 | **The barter is at Northlight**: the eight `data/direct_trades.json` lines, re-priced to 1.00-1.05 of the counter's price and approved, on a villager inside the Northlight Mart (`counter_site`, step R18DT). EXP-055's villager stays under Holdfast | The owner's two answers above. The rule and each line's price are in `data/direct_trades.json` `pricing` |

**Still the owner's** (unchanged by the above): Q2 TMs single-use or permanent (`consumeMoveItemOnUse`); Q3 Mewtwo in
or out, and the Origin Fossil; Q6 Dynamax; Q12 every PROPOSED price above; and Q1 beyond stage 1 (whether "every item"
means all ~930 TMs). Not built tonight, though the design names them: the mint seeds, the brewing stand, PP Up/Max,
the bottle cap, the ancient balls, the Link Cable, the Upgrade, the pot and teacup lines (each waits on a price or a
question above).

**Known gaps this leaves for other owners:** `tools/markets_audit.py` and `tools/town_squares_audit.py` read item ids
from lang keys only, so the 23 TM lines read as unknown ids there (`tests/test_markets_audit.py::test_ids_and_recipe_
conditions_in_the_server_jars`); `data/bank.json` `not_built` still says "TMs are not built".
