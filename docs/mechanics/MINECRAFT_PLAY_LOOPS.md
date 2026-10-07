# Minecraft play loops: why a player stops battling and plays Minecraft

**Status (2026-10-07):** design proposal by `content-architect` (Wave A, unit A8). Nothing here is built, nothing
here is verified in a game. Every number says where it came from: **measured** (read from a file in this checkout,
cited), **computed** (arithmetic on cited values), **relayed** (from a document, cited, not re-measured) or
**ASSUMED** (vanilla or Cobblemon behaviour from memory, owed to `cobblemon-researcher` or an experiment).

**The ask** (the owner, `docs/STATE.md:137`, answer 12): no quest reason to build a house, but *"a player should
hopefully feel like they can stop pokemon'ng and play minecraft"*, made worth it by an item or Pokemon grind. It
ties to the material exchange (`docs/mechanics/MATERIAL_EXCHANGE.md`; bare `MATERIAL_EXCHANGE.md:N` below means
this file) and to answer 5, late-game items by direct trade with no
money (*"4 netherite ingots for a master ball or something difficult, money systems will be abused somehow"*).

## 1. Premises checked first

Five things the brief or the obvious design takes for granted are wrong or narrower than they look in this pack.

**P1. Building with spawn-condition blocks draws nothing where players will live.** The brief's premise is that
building with the blocks in `docs/world-building/SPAWN_BLOCKS_LIST.md` brings Pokemon. That list is generated from
the *inherited* spawn data in the server's jars and datapacks (`SPAWN_BLOCKS_LIST.md:3`). But:

- the inherited spawn files are re-emitted with coordinate anticonditions over every route corridor and every
  sub-region polygon (`tools/suppress_inherited_spawns.py:2-19`; installed in staging at 926 boxes, relayed from
  `docs/STATE.md:114`), so inside a sub-region no inherited spawn, block-keyed or not, runs;
- our own generated rosters use no block condition except `neededNearbyBlocks` water and `neededBaseBlocks` sand
  (`docs/mechanics/ENCOUNTER_DESIGN.md:214-215`, relayed);
- a Habitat Block replaces the pool round it (`SPAWN_BLOCKS_LIST.md:5`), so the training grounds and dens are
  closed to it too.

So a magma-block garden in a town or on a route draws no Gible: the species is either in our roster (and spawns
whether the block is there or not) or suppressed. The blocks act only on land outside every sub-region polygon and
corridor. **How much land that is was not measured** (the sub-region rosters cover "43 million blocks", relayed
from `tools/suppress_inherited_spawns.py:18`, of a 10,240-block-square border, measured at `data/world.json:221`,
much of it sea). This also puts two lines of STATE in tension: the spawn philosophy keeps "the default Cobbleverse
pool open in wilderness" (`docs/STATE.md:139`) while the suppression covers the sub-region polygons too
(`docs/STATE.md:114`). If the polygons tile the land, there is no wilderness in that sense. Section 3.4 proposes
how to make the premise true.

**P2. There are no animals, so "farming" means plants and Pokemon.** MobsBeGone removes 81 entities, every passive
animal among them (cow, sheep, chicken, pig, bee, ...); only the villager, the wandering trader and the ender dragon
are left (relayed from `docs/research/OBTAINABILITY_VANILLA_COBBLEMON.md:23-29`, VERIFIED there from the pack's
blacklist). STATE says "every vanilla hostile" (`docs/STATE.md:184`); that is true and incomplete. No animal pen, no
leather, wool, egg or honey farm exists. Pokemon replace them through drops and Pasture Loot (section 3.3).

**P3. Food has no survival value.** The pack ships the `No Hunger` datapack (relayed from
`OBTAINABILITY_VANILLA_COBBLEMON.md:53`). A crop farm's only outlets are the Bank (which may pay for it: N64 closed,
`docs/STATE.md:137` answer 2), Cobblemon cooking and Pokemon that eat. "Grow food to survive" is not a loop here.

**P4. Overworld ore is finite and shared.** The world is pre-exported inside its border (`data/world.json:221-222`)
and generates no new chunks, so every ore, gem cluster and debris-equivalent in the overworld exists once, for the
whole server. The Nether generates normally (relayed, `OBTAINABILITY_VANILLA_COBBLEMON.md:34`), but if its border is
the overworld's scaled by 1/8 (ASSUMED vanilla behaviour) it is about 1,280 blocks square (computed: 10,240 / 8),
so **ancient debris is finite and contested too.** This matters for direct trade: an item-priced reward is rationed
by the world itself.

**P5. The Nether is reachable at any time, not "from leg 7".** `data/bank.json` labels the Nether tier as opening
at leg 7 (`MATERIAL_EXCHANGE.md:84`), but that is a pricing label. A portal needs obsidian, which a water-and-lava
cast makes (ASSUMED reachable, `OBTAINABILITY_VANILLA_COBBLEMON.md:36-37`). Nothing gates it on a badge. A Nether
reward is gated by effort and gear (a diamond pickaxe for debris), not by progress. The End is unreachable (no
stronghold, `MATERIAL_EXCHANGE.md:145-149`): no elytra, beacon or dragon-egg loop exists.

**Not used:** the figures "THE NURSE: 30 minutes", "237 ambient across 26 settlements" and "the four P2s" are
unsourced (the brief) and nothing here rests on them.

## 2. What makes a Minecraft loop worth doing

A loop is worth leaving battle for when it pays in **something the battle route does not pay cheaper**. Three shapes
qualify, and each has a mechanism that exists or is being proven:

| Shape | Pays | Mechanism (CLAUDE.md principle 6 rung) | Status |
|---|---|---|---|
| **Effort for an item, by barter** | A late item for a non-renewable material | A vanilla villager with fixed `Offers` (vanilla native, placed by our generated functions) | UNPROVEN, unit A4 / EXP-055 |
| **Effort for money** | Dollars at the Bank, then anything on a shelf | CobbleDollars Bank (`data/bank.json`) | Built, applied to staging, not run in game (`docs/STATE.md:127`) |
| **A built place for Pokemon** | More of a species, or a species, near what you built | Spawn conditions in our generated pools (datapack) | Does not work today where players live (P1) |

The second shape is the one the owner distrusts, for a structural reason (section 4): money is fungible, so every
hole anywhere in the economy flows into every price. The material exchange's wage rules keep gathering below
fighting (`MATERIAL_EXCHANGE.md:68-88`), which makes money a fallback, never a reason to stop battling. **So the
loops below lean on the first and third shapes, and use money only where the reward is cheap.**

## 3. The loops

Stage names follow the gym legs (leg N is the walk to gym N). "Feeds" names the parallel unit that consumes it:
**A4** (barter villager, EXP-055), **A6** (every item routed to a source), **A7** (EV/IV training and the Marts).

### 3.1 Mining

| What the player does | Pays | Mechanism | Stage |
|---|---|---|---|
| Works the evolution-stone faces by the towns | The ten stones, one restore per face per 600 s while someone is near (measured, `data/mines.json:40-47`) | World blocks (built, `tools/mines.py`, R9O); the Bank never buys a stone (measured, `data/bank.json:45-54`) | Legs 1-8 |
| Strip-mines iron, gold, redstone, diamond | Dollars ($8 raw iron, $120 a diamond: measured, `data/bank.json:78,84`); the Fossick lines (18 diamonds per evolution item, relayed `MATERIAL_EXCHANGE.md:97`) | Bank, exchange lines | Legs 1-6 |
| Mines gem clusters (if any are authored, 3.7) | Type gems: 294 of 335 native TM recipes need one (relayed, `OBTAINABILITY_VANILLA_COBBLEMON.md:81-85`) | World blocks + crafting | Mid to late |

**Proposal:** the Fossick diamond lines become **barters** (18 diamonds for a Metal Coat, item for item) rather than
"sell 18, then buy at $2,160". Diamonds are finite (P4), so the barter is rationed by the world; the money version is
rationed only by the wage rules, which rest on ASSUMED rates (`MATERIAL_EXCHANGE.md:70-72`). Feeds A6 (a source row
for each held and evolution item), A4 (the second counter after the Nether one).

### 3.2 Farming: berries, mints, apricorns

| What the player does | Pays | Mechanism | Stage |
|---|---|---|---|
| Grows apricorns | Ball crafting; $1 a fruit (a token, measured `data/bank.json:86-90`); about 17 minutes picked to ripe, only while a player keeps the chunk simulated (relayed, `data/apricorn_farm.json:50`) | Hollin's farm (built, not audited) and player trees | Leg 1 on |
| Grows and cross-breeds berries | Held berries; EV-lowering berries (ASSUMED present in Cobblemon 1.8); $ for ten berries (relayed, `MATERIAL_EXCHANGE.md:44`) | Berry trees and mutations (154 mutations read from the jars, relayed `OBTAINABILITY_VANILLA_COBBLEMON.md:55`) | Leg 2 on |
| Grows mints from seed | Nature change; the white mint leaf the six Power items need (relayed, `OBTAINABILITY_VANILLA_COBBLEMON.md:91-92`) | **Today none:** all 33 mint items have no source but unverified trainer loot; mint plants are worldgen-only (same, `:91`) | Mid game |

**Proposal: the seed barter.** A barter that pays **seeds, not product** turns a one-off trade into a farm the
player owns: one trade for each mint seed kind (and for the rarer berry parents), priced in a mid-game material
(diamonds, gold, amethyst). After that the grind is the farm, which is exactly "playing Minecraft". This is the
cheapest loop with a real Pokemon payoff, and the only route mints and Power items would have. **Feeds A7 directly**
(natures, Power items and EV berries are the inputs of an EV/IV hub) and A6 (33 mint items routed). Unknown first:
that a mint seed planted in survival grows and yields (ASSUMED, section 7).

### 3.3 Ranching (the Pasture)

| What the player does | Pays | Mechanism | Stage |
|---|---|---|---|
| Builds a pasture yard and keeps Pokemon in it | Each pastured Pokemon has a 15% chance a minute to drop from its own drop table, 34 items blacklisted (relayed, `OBTAINABILITY_VANILLA_COBBLEMON.md:67-70`, ASSUMED to work as configured) | Pasture Loot (base pack, installed) | Leg 1 on |

This is the pack's real replacement for animal farms (P2) and already exists: string, bone, feathers, scutes and
the like come from a ranch of the right species. It is the strongest "build a place and tend it" loop the pack has,
and it needs nothing built. It is also the largest AFK source (section 4.3). **Feeds A6** (most drop items get a
renewable route here once a player owns one of the species).

### 3.4 Building: attractor gardens (the Pokemon reason to build)

| What the player does | Pays | Mechanism | Stage |
|---|---|---|---|
| Builds with a block from the spawn-blocks list (a magma terrace, a quartz floor, an amethyst grotto, a flower meadow) | More of a species near the build | **Not working today** (P1). Proposed: **attractor entries** in our generated pools | Leg 2 on |

To make building draw Pokemon inside the sub-regions, `tools/build_encounters.py` (rung: datapack) would add, per
sub-region, a few **attractor entries**: a species already legal at that sub-region's tier, with a
`neededNearbyBlocks` (or `neededBaseBlocks`) condition taken from `data/spawn_blocks.json`, weighted so a garden
makes that species noticeably commoner nearby. The two choices that matter:

- **Which species.** (a) Bias only: species already on the sub-region's roster become commoner near their block.
  Safe for balance, weak as a reason to build. (b) New species: a species not on the roster appears only near its
  block, within the tier's level band and the hearts' ceiling (`ENCOUNTER_DESIGN.md` section 10). A real reason to
  build, and a balance decision. Owner question 3.
- **Which blocks.** Only blocks our own world packs do not place, or contract **C4** ("no world pack places a spawn
  condition its place is not whitelisted for", `data/system_contracts.json:403-409`) faults every authored lake,
  tree and stone face at once. Water, oak leaves and iron ore are out; magma, quartz block, amethyst block, lightning
  rod, cake and the gem blocks are candidates. The audit derives the allowed set from the world packs' placed
  blocks, never from a hand list.

Blast radius: every sub-region pool changes, so a full prepare and install (`docs/STATE.md:120`). Multiplayer: a
garden is world state, so it draws for whoever stands there. World-critical: none (no new mod).

### 3.5 The Nether

| What the player does | Pays | Mechanism | Stage |
|---|---|---|---|
| Mines ancient debris, smelts scrap, crafts ingots | **The Master Ball and the late held items by barter** | A4's villager (EXP-055) | Reachable any time (P5); priced for late game |
| Mines quartz, farms nether wart | Building blocks for 3.4 (quartz block is an `on` block for Duraludon and Carbink, magma block a `near` block for Gible and Magby: measured, `SPAWN_BLOCKS_LIST.md:47,56`); $2 a quartz (relayed, `MATERIAL_EXCHANGE.md:55`) | Bank, attractors | Mid to late |
| Explores fortresses and bastions | Finite chest loot, type gems among it (relayed, `OBTAINABILITY_VANILLA_COBBLEMON.md:62,84`) | Vanilla loot (Lootr, if it covers Nether chests, makes them per player: `docs/STATE.md:137` answer 8) | Late |

The ingot arithmetic, for the barter price: an ingot is 4 scrap + 4 gold, a scrap is one smelted debris (relayed,
`MATERIAL_EXCHANGE.md:53-54`). So the owner's example, **4 ingots, is 16 debris and 16 gold**, about 1.6 hours at
the ASSUMED 10 debris an hour, or about 0.5 hours bed- or TNT-mining at the ASSUMED 30 (computed from rates relayed
from `MATERIAL_EXCHANGE.md:52`). The money exchange asks **30 ingots** for the same ball (measured,
`MATERIAL_EXCHANGE.md:98`): 12.7 hours typical (relayed, `:131`). The two figures differ by 7.5 times; which one
the owner meant is owner question 1. Whatever the count, the ball still breaks free against an over-cap Pokemon
(`MATERIAL_EXCHANGE.md:210-211`, relayed). The Ruinous four stay Nether-generated (relayed from the brief), which
makes the Nether a Pokemon loop too. **Feeds A4** (the first counter's offers) and A6 (the Master Ball's one
repeatable route, `MATERIAL_EXCHANGE.md:156`).

### 3.6 Fishing

| What the player does | Pays | Mechanism | Stage |
|---|---|---|---|
| Fishes with a rod | Fish ($10-20 at the base Bank, relayed `MATERIAL_EXCHANGE.md:164-166`; N64 accepts it); vanilla and Cobblemon fishing loot (relayed, `OBTAINABILITY_VANILLA_COBBLEMON.md:60`) | Bank | Leg 1 on |
| Fishes for Pokemon with a Poke Rod and bait | Water species, perhaps ones on no land roster | Cobblemon fishing (ASSUMED: what it hooks, whether our water pools feed it, and bait effects are not recorded in `docs/research/`) | Unknown |

Fishing is a loop the pack already has, but **nothing about Pokemon fishing in this world is verified**. It is the
first research question, not a design (section 7).

### 3.7 Exploration

| What the player does | Pays | Mechanism | Stage |
|---|---|---|---|
| Finds caches, wrecks, finds off the path | One-off items (`data/rewards.json`, 12 wrecks with caches relayed `docs/STATE.md:126`) | Rewards, Lootr once built | All |
| Digs the fossil site | Fossils, shared: one per suspicious block for whoever brushes it first (relayed, `data/fossil_dig.json:98`) | Fossil dig (authored, not built) | Mid |
| Finds gem-cluster seams (proposed) | Type gems, then TMs | World blocks (not authored) | Mid to late |

Exploration pays well already and is bounded by being one-off. The gap is **renewable** exploration income, and
the stone-face pattern (a restore on approach, `data/mines.json:40-47`) is the template: a gem seam in a cave that
restores like a face would make TMs craftable without a shop. That depends on the TM decision
(`MATERIAL_EXCHANGE.md:150-152`) and is the most expensive loop here.

## 4. Abuse analysis

### 4.1 Why direct trade resists better than money

Money is **fungible**: any dollar from any hole buys any shelf item. The holes that exist or are accepted today:
AFK food at the base Bank (accepted, N64), Pasture Loot drops the Bank buys (9 drop rows, relayed
`MATERIAL_EXCHANGE.md:44`), the base's $400 emerald at an unmeasured ore density (`MATERIAL_EXCHANGE.md:87-88`),
and every rate in the wage rules is ASSUMED. Under money pricing each of these converts, eventually, into a Master
Ball. The wage rules prevent that only while the ASSUMED rates hold; the deep tier passes by $416 (relayed,
`MATERIAL_EXCHANGE.md:86`).

A barter's price is a **specific item**. A hole elsewhere in the economy does not reach it. What remains is the
input's own supply, and the inputs proposed here (debris, diamonds, gems) are non-renewable in this world (P4).
**That is the whole argument, and it holds only under four rules**, which the barter's independent audit must check:

- **B1. At least one input is not purchasable.** If every input can be bought, money re-enters through the input.
  (Gold is in every ingot; debris is the binding input. No seller may sell debris, scrap or ingots, which
  `economy_audit.py` already checks for bank-bought materials.)
- **B2. No input an unattended farm makes.** `economy_audit.py`'s `AFK_FARMABLE` table (`tools/economy_audit.py:43-45`)
  is the list to check against.
- **B3. No output the Bank buys, and no barter cycle.** Otherwise the barter becomes a money machine (trade in,
  sell out). The economy audit today models shops, the bank and recipes (`tools/economy_audit.py:19-24`), not barter
  edges; it must gain them.
- **B4. No price drift.** A vanilla villager's offers move with demand, level-ups add random trades, and restocking
  depends on a workstation (all ASSUMED vanilla behaviour). EXP-055 should show each held fixed, or the counter is
  not a fixed price.

### 4.2 Where direct trade does not help

- **Pooling.** Items move between players as freely as any money transfer could. Four friends pooling debris buy a
  Master Ball four times faster. In a small cooperative group this may be the intended game (owner question 4).
- **Shared stock.** A vanilla offer's `maxUses` belongs to the villager, not to a player (ASSUMED; the same shape
  as a CobbleDollars `Stock`, `MATERIAL_EXCHANGE.md:19-20`). A per-player cap needs per-player state, which neither
  provides natively.
- **Contention.** Finite debris (P4) means the first player to strip a Nether region takes it from the others. A
  barter priced at 30 ingots may be unreachable for the third player to arrive. Measure the debris supply before
  pricing (section 7).
- **Early reach.** P5: a determined player can open the Nether before gym 1. A barter counter in an early town
  sells to that player (owner answer 4 allows early sale at out-of-reach prices, `docs/STATE.md:137`). The effort
  is the gate. Owner question 2.

### 4.3 Per loop

| Loop | AFK farm | Pooling | Arbitrage against bank and counters |
|---|---|---|---|
| Stone faces | None: restore only while a player is near, 600 s per face (`data/mines.json:47`) | Shared world blocks; the group splits a face | None: the Bank never buys a stone (`data/bank.json:45-54`) |
| Strip mining | None (needs a player) | Finite ore is contested | Covered by the wage rules (ASSUMED rates); a diamond barter removes the dollar leg |
| Apricorns | Partial: ripening needs a simulated chunk, so a player AFK in range farms them (`data/apricorn_farm.json:50`) | Free | $1 a fruit, a token |
| Berries, mints | As apricorns (ASSUMED growth mechanics); a seed barter must not take a farmed crop as its input (B2) | Seeds are copyable once anyone holds one | Mints and Power items must never be Bank-bought (B3) |
| Ranch (Pasture Loot) | **Yes, the largest**: 15% a minute per Pokemon, unattended if the chunk is loaded (relayed, ASSUMED) | Free | Any drop the Bank buys is AFK money; the 9 drop rows should be re-read with this in mind (owner question 5) |
| Attractor gardens | A player AFK beside a garden next to a bed sees more of a species; bounded by the level cap and catching being active play | World state, shared | None directly; drops via Pasture once caught |
| Nether barter | None: debris is mined, not grown | Pooling and contention (4.2) | Rules B1-B4 |
| Fishing | **Yes**: AFK fishing is vanilla (ASSUMED); fish are Bank-bought (accepted, N64) | Free | Money only; no barter should take fish |
| Exploration | None (one-off) | Shared unless Lootr | None |

One edge case for A4's experiment, ASSUMED vanilla behaviour: lightning turns a villager into a witch, the witch is
on MobsBeGone's list (relayed, `OBTAINABILITY_VANILLA_COBBLEMON.md:24`), and a lightning rod is a spawn block players
may build (`SPAWN_BLOCKS_LIST.md:46`). Whether an `Invulnerable` barter villager survives a strike is worth one test.

## 5. Where this feeds the parallel units

- **A4 (barter villager, EXP-055):** the offers in 3.5 and 3.1; rules B1-B4 as success criteria; the lightning case.
- **A6 (item routes):** source rows for the Master Ball (Nether barter), the held and evolution items (diamond
  barter), the 33 mint items and Power items (seed barter, then farm), the drop items (ranch), the type gems
  (seams, if built), fishing loot.
- **A7 (EV/IV and the Marts):** mints, EV berries and Power items are farm products, not shelf stock, if the seed
  barter is built; an EV/IV hub that *buys* farm products by barter (berries in, vitamins out) is a loop worth
  considering, under B2 and B3.

## 6. What exists and what needs building, by value for cost

| # | Item | Exists | Needs | Agent |
|---|---|---|---|---|
| 1 | **Nether barter counter** (Master Ball, late held items) | Bank prices, the Northlight counter site, A4's experiment in flight | EXP-055 passing; `data/` barter records; a generator (extend `tools/markets.py` or a new one); barter edges in `tools/economy_audit.py` (B1-B4); a decision on the Northlight money lines | A4 result, then `datapack-content-dev`; audit `test-author` |
| 2 | **Seed barter + farming** (mints, rare berries) | Berry mutations in the jars; the barter mechanism from 1 | Research: mint seed growth in survival, berry trees; barter records; A7's consumption | `cobblemon-researcher`, then `datapack-content-dev` |
| 3 | **Diamond barter at Fossick** | The money lines (`MATERIAL_EXCHANGE.md:97`) | Records only, once 1 exists | `datapack-content-dev` |
| 4 | **Ranch rules** | Pasture Loot installed | A decision on which drops the Bank buys (data only); a runtime check that Pasture Loot drops as configured | owner, then `datapack-content-dev`; experiment |
| 5 | **Attractor gardens** | `data/spawn_blocks.json`, the encounter generator | Measurement of P1; a rule in `docs/mechanics/ENCOUNTER_DESIGN.md`; a generator change; a C4-aware block set; an experiment | `datapack-content-dev` (generator), `test-author` (audit), staging test |
| 6 | **Fishing** | The pack's fishing | Research before any design | `cobblemon-researcher` |
| 7 | **Restoring gem seams** | The stone-face restore pattern | The TM decision; world authoring; an audit | `world-content-dev`, `test-author` |

Items 1, 3 and 4 are mostly data once EXP-055 passes. Item 5 has the highest Pokemon value and the widest blast
radius (every sub-region pool). Item 7 is world work and waits on the TM decision.

## 7. Unknowns, as experiment candidates

1. **Land outside the suppression** (P1): count land columns outside every sub-region polygon and route corridor,
   on the canonical heightmap. A tool run in a full checkout; seconds.
2. **A block draws a spawn** inside a sub-region once an attractor entry exists: a magma patch, a timed watch, with
   and without the block. Staging.
3. **The Nether's border and debris supply:** `/worldborder get` in the Nether on staging, and a debris count over a
   sample of Nether chunks, to price the barter against a finite supply.
4. **Mint seeds grow in survival** and yield leaves; berry trees and mutations as in the jars. Research, then a
   disposable-world test.
5. **Pasture Loot drops as configured** with no player near (chunk loaded vs unloaded).
6. **Pokemon fishing:** what a Poke Rod hooks over our water pools, and what bait does. Research.
7. **Villager offer stability** (B4) and the lightning case: part of EXP-055.
8. **Rates:** an hour of strip mining, bed mining and Nether debris mining, timed (already owed,
   `MATERIAL_EXCHANGE.md:203-205`).

## 8. Owner questions

1. **The Master Ball's barter price.** Your example was 4 netherite ingots (16 debris, about 0.5-1.6 h at ASSUMED
   rates); the built exchange asks 30 (12.7 h). Which is closer to "something difficult"?
2. **Does a barter counter care about badges?** The Nether is open from the start (P5). Gate the counter on a badge,
   or let effort alone gate it?
3. **Attractor gardens: bias or new species?** Should building with a block only make a place's own Pokemon
   commoner, or bring species the place does not otherwise have (inside its level band)?
4. **Is pooling abuse or co-op?** If four friends pooling debris for one player's Master Ball is fine, barters need
   no per-player limit. If not, per-player limits need a mechanism neither shop type has.
5. **Ranch drops at the Bank.** Pasture Loot makes drops unattended. Keep buying the 9 drop rows (N64 suggests yes),
   or stop buying the ones a ranch makes?
6. **Retire the money exchange lines?** Once barters exist, should the Northlight and Fossick "sell then buy" lines
   go, so late items have one route and it is not money?
7. **Seeds rather than product.** Should the barter sell mint and rare-berry seeds once, so players farm natures
   and Power items themselves, rather than the Marts or A7's hubs selling mints?
8. **Wilderness spawns.** STATE says the default pool stays open in wilderness, and the suppression covers every
   sub-region. Which is intended? It decides whether inherited spawn blocks act anywhere players go.
