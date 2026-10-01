# The progression ladder: what each town sells, and what each badge buys

**Status: PROPOSED, 2026-10-01. Nothing here is decided and nothing is built.** Every
row is a `content-architect` proposal; the owner's open questions are numbered at the
end and can be answered one at a time. No `data/` file, config or pack is touched by
this document.

**The owner's goal, verbatim:** *"I want a player to advance materially as they travel,
so they never need to build a house — they live out of a backpack that gets better.
Town markets are where that happens."* And: *"It should feel like the region, not a shop
list — a mining town sells what a mining town would."*

## What this rests on

| Source | What it settles |
| --- | --- |
| `docs/research/PROGRESSION_UNLOCKABLES.md` | the mod audit: six backpack tiers, 56 upgrades, crafting-only supply, the flattened curve, what is and is not gateable |
| `docs/mechanics/MARKET_GATING.md` | the mechanism: per-player **dialogue option visibility** on a `cobblers:flag/<id>` probe, paid with the ferry's checked CobbleDollars sequence |
| `data/towns.json`, `docs/world-building/TOWN_CHARACTER.md` | each place's purpose, landmark, dressing and palette — the ladder follows these, it does not invent |
| `data/progression.json` | the flags that exist: `gym1_cleared`…`gym8_cleared`, `champion_cleared`, `chapter_1`…`chapter_8`, `league`, `postgame` |
| `data/traders.json` | the 26 trader records, the 14 Mart clerks, the Assayer, and `stock_policy` (interim, waiting for exactly this document) |
| `data/trainers.json` `generation_contract` | `gym_ace_levels` 20/25/30/35/40/45/50/55, `relative_level_cap: 0` |
| `modpack/config/rctmod-server.toml` | the parallel progression already running |

**Procedural note, recorded because it is a finding.** This agent has no shell, so the
briefed `git rev-parse HEAD` could not be run. The worktree's HEAD, read from
`.git/worktrees/<name>/HEAD` → `refs/heads/worktree-agent-a2c947026c27f2ea8`, is
**`a2715326385f624b58fe03fdcbff4cdb406d86d7`**, not the briefed
`b16c060e27c4e12e6c6c8f8a2e7fd17e72f08679`, and `git reset --hard` could not be run
either. `docs/research/PROGRESSION_UNLOCKABLES.md` and `docs/mechanics/MARKET_GATING.md`
do not exist at this HEAD; both were read from the session worktree at
`C:\Users\wnd\Documents\github\cobblers\.claude\worktrees\cobblers-cobblemon-session-start-531d15`.
Everything else was read in this worktree. If `data/` moved between the two commits,
this document's trader and flag citations are one commit stale.

---

## 0. The question the shape depends on: is `defaultShop` global?

**Answer: `defaultShop` is GLOBAL — one flat, server-wide list, with no merchant key and
no per-player field. VERIFIED.** And it **does not decide the ladder**, because per-town
stock does not come from it.

`base-pack/cobbleverse/config/cobbledollars/default_shop.json` is a single
`"defaultShop": [...]` array of four named categories (`Cobble Ball`, `Potions`,
`Mob Drops`, `Cards`), each a flat list of `{item, price}`. Read end to end, 120 lines:
there is no merchant id, no town, no selector, no condition, no player field anywhere in
it. `common.json` is four keys (`earnCobbleDollarsFromNPC`,
`earnCobbleDollarsFromWildPokemon`, `cobbleDollarsIncomeMultiplier: 0.5`,
`playerDataSaveFrequency`). `client.json` is one key. `modpack/config/cobbledollars/`
**does not exist**, so nothing of ours overrides any of it. This confirms
`MARKET_GATING.md` open question 4 independently.

**But per-merchant stock is already ours, and already built.** Each merchant entity
carries its own `CobbleMerchantShop` NBT compound, and `tools/traders.py` authors it per
trader — `stone_shop()` at `tools/traders.py:156-160` replaces the Assayer's entire shop
with ten stones at one price, and `apply_stock_policy()` at `:171-203` rewrites
`out["CobbleMerchantShop"]` per record. So:

| Layer | Per town? | Per player? | Rung (principle 6) |
| --- | --- | --- | --- |
| `defaultShop` config | **no** — one global list | no | 4 (configuration) |
| `CobbleMerchantShop` entity NBT, authored by `tools/traders.py` | **yes** | no — build-time, identical for everyone | 2 (Cobbleverse dependency) + 5 |
| Dialogue counter, options gated on `cobblers:flag/<id>` | yes | **yes** | 5 (datapack) + 7 (functions), money at rung 2 |

**So the ladder has two shapes and uses both, which is what the towns want anyway:**
the per-town *feel* comes from the authored NBT shop (every town's ungated shelf differs,
no flags involved, and the 14 clerks already work), and the per-badge *gate* comes from
a second counter per town — a dialogue quartermaster beside the clerk, exactly as
`MARKET_GATING.md` §4 recommends. **No rung below moves on account of `defaultShop`.**

**What is still NOT VERIFIED, and it is urgent:** whether `defaultShop` is the *fallback*
for a merchant carrying no `CobbleMerchantShop` compound, or a separate always-global
shop reachable some other way. It matters because of §5 collision 1: the
`rctmod:trainer_card` lives **only** in `defaultShop`, and no clerk of ours stocks it.

---

## 1. The ladder, town by town

**How to read it.** `Flag` is a flag that exists in `data/progression.json` today unless
marked **(request)**. `Rung` is the mechanism rung from principle 6. Prices are
**proposals with no measurement under them** — calibrated against the only prices in the
repository (Mart basics 200/200/100, the Mart revive 2,000, the Assayer's stones 2,100,
`defaultShop`'s great ball 750 / ultra 1,000 / revive 3,000 / trainer card 500, `bank.json`'s
elytra 25,000) and against `cobbleDollarsIncomeMultiplier: 0.5`. See U-1.

### 1.1 The critical path

| # | Town | Purpose it already has | What becomes buyable | Flag | ~Price | Why **this** town |
| ---: | --- | --- | --- | --- | ---: | --- |
| 0 | **Pallet** (`hometown`) | Pallet Town as it was, whole, set down on ground that is not Kanto | `sophisticatedbackpacks:backpack` (27/1); `comforts:sleeping_bag` | none (start) | 300; 250 | Pallet is the one town that **is** a house. The last thing home gives you is the means never to come back. The brief's whole premise is sold here or nowhere. |
| 1 | **Brock** (`gym1_town`) | the plateau's builders' town: masons, and the coordinator who runs the rescue | `stonecutter_upgrade`; `anvil_upgrade`; `crafting_upgrade` (see Q-2); `copper_backpack` (45/1) | `gym1_cleared` | 1,800; 2,500; 7,500; 1,200 | **The strongest identity match in the region, and it needs no invention:** the dressing already contains a stonecutter, a grindstone and an anvil bench (`TOWN_CHARACTER.md`, Brock's row). The town's product is the workstation. |
| 2 | **Misty** (`gym2_town`) | the lake town that takes in whoever the water brings, and keeps a record of every arrival | `tank_upgrade`; `filter_upgrade`; `advanced_filter_upgrade` | `gym2_cleared` | 1,500; 1,200; 3,000 | A rescue crew sells water carried. A town whose landmark is a **ledger board of arrivals** sells the thing that decides what you keep. |
| 3 | **Surge** (`gym3_town`) | the signal town under Mt Vessu: its people keep the power and the relays running | **`iron_backpack` (81/7)**; `battery_upgrade`; `xp_pump_upgrade` | `gym3_cleared` | 6,000; 2,500; 4,000 | **The pivot of the whole spine, and it is a config fact rather than a choice.** Cobbleverse's iron tier jumps 1 → **7** upgrade slots (`sophisticatedbackpacks-server.toml`). Everything bought at Brock's and Misty's is unusable until this rung, and simultaneously usable after it. Power and relays are also the only trade in the region that would plausibly sell a battery. |
| 4 | **Erika** (`gym4_town`) | Peak Pond Hollow's garden town | `feeding_upgrade`; `advanced_feeding_upgrade`; CobbleCuisine's `malasada`/`pokepuff` | `gym4_cleared` | 2,000; 4,500; 900/500 | A garden town sells food, and the feeding upgrade **is** food that follows you. CobbleCuisine already ships the three-rung friendship ladder as plain numbers (`beanFriendship: 1`, `pokepuffFriendship: 6`, `malasadaFriendship: 12`). |
| 5 | **Koga** (`gym5_town`) | a fen-edge watch town where trackers read the marsh | `pickup_upgrade`; `advanced_magnet_upgrade`; `smoking_upgrade`; **`mega_showdown:mega_bracelet`** | `gym5_cleared` | 1,500; 4,000; 2,200; 9,000 | Trackers and traps. Pickup and magnet **are** trapping, mechanically, and the dressing has eel traps and smoke racks. The bracelet is here because badge 5 of 8 leaves three gyms to use Mega Evolution on (§4). |
| 6 | **Sabrina** (`gym6_town`) | the region's place of study: her people record what the Rift does to memory and perception | `smithing_upgrade`; `stack_upgrade_starter_tier` → `tier_2` | `gym6_cleared` | 3,500; 2,000 / 4,000 / 8,000 | A town of record-keepers and memory stones sells **compression**: a stack of 64 reading as 1,024 is the on-theme joke that is also the strongest storage rung left after iron. Capped at 3 per backpack by `maxUpgradesPerStorage`, so the shelf has a natural end. |
| 7 | **Blaine** (`gym7_town`) | a research town on the crater rim, studying the cone's energy | `smelting_upgrade`; `auto_smelting_upgrade`; `blasting_upgrade`; `gold_backpack` (96/8) | `gym7_cleared` | 2,800; 6,000; 3,200; 12,000 | A town on a volcano sells **heat**, and nowhere else should. The dressing already has a field laboratory, cauldrons and fumaroles. `furnace_upgrades|1` means the player picks one, which is a real choice rather than a shelf. |
| 8 | **Giovanni** (`gym8_town`) | the southern garrison: the last gate before Victory Road | `inception_upgrade`; `diamond_backpack` (108/9); **`obc` gold bottle cap** | `gym8_cleared` | 10,000; 20,000; 15,000 | **The quartermaster's stall is already built and already faces the road to Victory Road.** A quartermaster's answer to "I have too much" is packs inside packs. The gold cap belongs here because `goldBottleCap = 0.0` from treasure (`obc-common.toml`) means the campaign owns its **entire** supply, and hyper-training a level-55 team at the last gate is the correct moment for it. |
| 9 | **League** | the region's last hall, on the Rift's apex | **nothing. The League sells nothing.** | — | — | **Said rather than padded.** The League is not a shop, it has no `data/traders.json` record, and `TOWN_CHARACTER.md` keeps it undressed by design. `netherite_backpack` is +12 slots and +1 upgrade slot over diamond: it is not worth a rung. Propose it as `champion_cleared`'s **reward item** in ADR-002's shape, not a sale. |

### 1.2 Off the path — where identity earns its keep

| Town | Purpose it already has | What becomes buyable | Flag | ~Price | Why **this** town |
| --- | --- | --- | --- | ---: | --- |
| **`mining_town`** | ore and minerals on the eastern cone: the mine head, the ore rail, a smelter, a fossil lab | `compacting_upgrade`; `advanced_compacting_upgrade`; `void_upgrade`; `advanced_void_upgrade` — the Assayer keeps the ten stones at 2,100, untouched | `gym3_cleared` (reachability: U-4) | 3,000; 7,000; 1,800; 4,000 | **A mining town sells mining answers.** Compacting is nine ingots into a block: a smelter town's one trick. Void is what a miner throws away. Neither belongs anywhere else in the region. |
| **`sunset_west`** | the region's harbour: fishers and boatwrights, and the charter boats to the outer sea | `waystones:blank_scroll`, `return_scroll` (ungated); `warp_scroll`, `bound_scroll` (gated); `sophisticatedstorage` iron/gold shulker boxes | none; then `gym5_cleared` | 400; 1,200 \| 3,500; 2,600; 2,500 | **The cleanest identity match after Brock's: a port's product is going somewhere.** It is the only place in the region that should sell passage. Crates on a quay sell portable crates — shulkers, which are the one `sophisticatedstorage` line that is luggage rather than furniture. |
| **`northlight`** | the cold-water research town: weather and aurora observatory, ice-type field station | `comforts` hammocks (16 colours); a "field bedroll" — **but see U-5** | `gym6_cleared` | 800; 3,000 | A weather station sells **shelter**, which is the owner's goal in one word. `sleepingBagEffects = []` is config, so a bedroll that grants a waking buff needs no code — **except that the key is server-wide, so it cannot distinguish a field bedroll from Pallet's. This rung probably does not work as a tier.** U-5. |
| **`tea_town`** | a town built on one industry: tea terraces over Shrew Lake, a tea house, Poltchageist | CobbleCuisine consumables, at a discount | none | 500/900 less a margin | **A one-industry town sells its one industry, and that industry is a consumable.** This is a restock, not a rung. Said plainly rather than padded: tea town gives the ladder **nothing durable**. |
| **`sea_town`** | a fishing town floating in the Sound: rafts, a fishers' row, a boatwright | fishing gear, and the ferry fares **already built** | existing ferry flags | existing | **Already a working gated counter.** `tools/ferries.py:220-239` is the precedent every rung above copies. It is the proof, not a rung. |
| **`hometown`** | see 1.1 row 0 | | | | |
| `displaced_city`, `merian_hut`, `gorge_hamlet`, `tableland_stop`, `rift_rim_stop`, `relic_island`, `the_scar`, `viltri_light`, `rift_dig_camp`, `jungle_ruins`, `frostpeak_shrine` | eleven places | **nothing, and most should never have a market.** | — | — | None has a `data/traders.json` record. The Scar and the jungle ruins are "dark and unkept by design" (`TOWN_CHARACTER.md`, gates section). The rim post is a ranger station — a Centre, not a shop. Merian's hut is a bed at the end of a walk. **The one I would reconsider:** `tableland_stop`'s prospector already has sample piles, a sieve and ore crates, so it is the only off-path stop with the identity for a second mining counter. It has no trader record, so that is a **request**, not a rung (Q-6). |

### 1.3 What the ladder deliberately does not do

- **It does not sell a badge or any badge-shaped token.** RCT already gives badges from
  each leader's loot table on first defeat (`data/progression.json` note 6). Two ledgers
  is a bug, not a feature.
- **It does not sell `rctmod:trainer_card`.** That is a tax, not a rung (§5.1).
- **It does not include `everlasting_upgrade`, `infinity_upgrade` or
  `survival_infinity_upgrade`.** They end the economy the markets exist for.
  Recommend they are not in the campaign at all.
- **It does not touch `stock_policy`'s interim blanket withholding yet.** Once a gated
  counter exists, `Pokéballs`, `Combat`, `Treatments`, `Remedies` and `Boosts` can be
  revisited **item by item** — which is the thing `data/traders.json`
  `stock_policy.status` has been waiting for since 2026-09-21. That is a separate,
  larger piece of work and belongs to `trainer-balance-designer`, not here.

---

## 2. The backpack as the spine: the verdict

### 2.1 The real numbers

| Tier | Item | Slots | Upgrade slots | Over the tier below |
| --- | --- | ---: | ---: | --- |
| 1 | `backpack` | 27 | 1 | — |
| 2 | `copper_backpack` | 45 | 1 | +18, +0 |
| 3 | `iron_backpack` | **81** | **7** | **+36, +6** |
| 4 | `gold_backpack` | 96 | 8 | +15, +1 |
| 5 | `diamond_backpack` | 108 | 9 | +12, +1 |
| 6 | `netherite_backpack` | 120 | 10 | +12, +1 |

A vanilla player inventory is 36 slots. **81 is 2.25 inventories in one item, reached at
badge 3 of 8.** And the number that matters is not 81, it is **7**: four portable
workstations (`crafting`, `anvil`, `smithing`, `stonecutter`) + `feeding` + one of
`pickup`/`magnet` + one furnace = exactly seven. **The pack's own config hands the player
a complete "no house" loadout at iron**, and the four tiers above it add 39 slots and 3
upgrade slots between them.

### 2.2 Can a player live out of one? Yes.

A crafting table, an anvil, a smithing table and a stonecutter **in the pack**, plus a
Comforts sleeping bag that passes the night and sets no spawn point
(`sleepingBagUse = "DAY_OR_NIGHT"`, `sleepingBagBreakChance = 0`), is every reason a
Minecraft player builds a house, removed. Lumymon's `remotePcEnabled = true` already
removes the Pokémon half from day one. The answer is yes, and it is yes **with
configuration that already ships**, not with anything we build.

### 2.3 What it needs

1. **The tiers above leather must not be craftable.** Supply is crafting-only
   (`chestLootEnabled = false`, `backpackDropChance = 0.0`, `entityLootTableList = []`),
   so if the recipes stay, the shop is a convenience and the spine is decorative. This is
   the **one blocking dependency** and it is untested in this pack (U-2).
2. **The shelf must be visible before it is affordable.** An absent recipe reads as a
   mystery, not a goal (`PROGRESSION_UNLOCKABLES.md` §1.4: the item stays in REI with no
   recipe and no explanatory text). A priced shelf the player can see and not yet afford
   says "later"; a missing recipe says nothing.
3. **A second counter per town.** The clerk keeps the trade GUI for ungated basics; the
   quartermaster is a dialogue NPC for gated goods (`MARKET_GATING.md` §4). NPC classes
   load only at server start, so each new counter is a **restart**, and its placement is
   an RCON `spawnnpcat` step in `tools/reapply.py` (R17F), never a function.

### 2.4 What it breaks

1. **Storage is not a reward in this pack, and pretending it is will fall flat.** Lumymon
   gives remote PC storage at minute one; shulkers, barrels, chests, Iron Chests and Tom's
   Storage all exist. By badge 3 the player has 81 slots and will never fill them.
   **Rungs 4, 5 and 6 are not rewards, they are receipts.** If the owner wants six tier
   rungs, `sophisticatedbackpacks-server.toml` has to be re-tuned in `modpack/config/` —
   a configuration decision, cheap, and one the owner should make knowingly.
2. **Portable crafting removes the reason to return to town, and the markets depend on
   that reason.** This is the real tension in the brief and the owner should see it named.
   A player with crafting, feeding and a sleeping bag does not come back. The ladder's
   answer is that the markets sell what the pack **cannot make**: stones (2,100, no
   buy-back, ever), Poké Balls, potions, revives, waystone scrolls, TMCraft blanks. The
   counter stays the destination even when the house is not.
3. **Gating controls purchase, never possession.** No mod in the pack exposes a per-player
   gate (`PROGRESSION_UNLOCKABLES.md` §4); the only per-player mechanism is holding an
   item, and a held item can be dropped, traded or chested. In a four-friend co-op one
   player buys the crafting upgrade at badge 6 and hands it to three friends at badge 2.
   **The ladder is a pacing tool, not an enforcement — so it should be generous, because
   it cannot be strict.**
4. **No trade GUI at a gated counter.** Fixed quantities in a dialogue menu, no
   drag-and-drop, no stack arithmetic. A real downgrade in feel, and the owner should see
   one before it spreads to sixteen counters.
5. **Two players at one counter is unproven.** Whether two players can hold an open
   dialogue with one Cobblemon NPC simultaneously is UNKNOWN (`MARKET_GATING.md` open
   question 1), and the two-player test is blocked on a second account.

### 2.5 The other side, argued because the owner invited it

**The strongest case against the backpack as the spine is that it is not a Pokémon
ladder.** Every rung in §2.1 is Minecraft convenience: slots, a workbench, a furnace.
None of it changes a battle, a catch, or which Pokémon the player can reach. Meanwhile
the campaign's actual power ladder already exists and is sharper in every respect:

- **TMCraft:** six material grades of blank × four forms, 24 ids verified — a ready-made
  six-town ladder for **move access**, which is campaign power rather than convenience.
- **Mega Showdown's key items:** one `mega_bracelet` = Mega Evolution, exactly as the
  games do it. One item, one mechanic, instantly legible.
- **The evolution stones** at 2,100 with no buy-back, already authored and already in a
  town that earns them.
- **Gold bottle caps**, whose entire supply the campaign owns because treasure gives none.

A player handed a stonecutter upgrade at badge 1 and a Mega bracelet at badge 5 will
remember the bracelet. The honest recommendation is therefore:

> **The backpack is the spine of the "no house" promise. It is not the spine of
> progression.** Run two strands at every counter — one convenience rung (the backpack)
> and one power rung (a TM blank grade, a key item, a stone, a cap). The convenience
> strand makes the travelling liveable; the power strand makes the badge matter. **If only
> one strand can be built, build the power strand**, because 81 slots and a sleeping bag
> already solve "no house" by badge 3 with almost no help from us.

That is a disagreement with the brief's framing, offered as a finding. The ladder in §1
is built so that either strand can be dropped without the other collapsing: §1's
convenience rungs stand alone, and the three power rungs in it (the bracelet at Koga's,
the caps at Giovanni's, the stones at the Assayer's) are each one row.

---

## 3. The spine against the brief, in one paragraph

Badges 0–3 are the "you can leave home" arc: a pack, a bedroll, two workstations and then
the iron tier that makes them all usable at once. Badges 4–6 are the "you can stay out"
arc: feeding, pickup, compression. Badges 7–8 are the "you are equipped for the League"
arc, where the convenience strand has nothing left to give and the power strand (furnace,
caps, inception) carries it. **The arc is finished at badge 3, four rungs before the game
is**, and that is the structural problem with making storage the spine — see §2.5 and Q-1.

---

## 4. The order against the level caps

Caps: `gym_ace_levels` 20/25/30/35/40/45/50/55 with `relative_level_cap: 0` and
`allowOverLeveling = false`, so a player's cap is the next required leader's ace
**exactly**.

**The test a rung must pass: it must arrive while the thing it affects is still binding.**

| Cap | Badge | Rung that must land here or earlier | Why it stops mattering later |
| ---: | ---: | --- | --- |
| 20 | 0 | leather backpack, sleeping bag, **trainer card** | the card is a *prerequisite* for trainers spawning at all. It cannot be a reward; it is a tax (§5.1) |
| 25 | 1 | copper backpack, stonecutter, anvil | an anvil matters while gear is still being repaired rather than replaced, i.e. early |
| 30 | 2 | filter, tank | sorting matters while the pack is small. After iron's 81 slots nobody filters anything |
| 35 | 3 | **iron backpack (81/7)** | **the hinge.** Later than badge 3 and six badges of upgrades sit unusable in a one-slot pack |
| 40 | 4 | feeding; CobbleCuisine camp boosts | `expBoostMultiplier: 2.0` and `catchRateMultiplier: 2.0` are worth most while the dex is incomplete |
| 45 | 5 | pickup, magnet; **Mega bracelet** | Mega Evolution at cap 45 of 55 leaves three gyms to use it on. At badge 7 it is a trophy |
| 50 | 6 | smithing; stack upgrades | **`crafting_upgrade` would be too late here. See Q-2** |
| 55 | 7 | furnace group; gold backpack | heat is pure convenience; late is fine |
| (E4) | 8 | diamond backpack, inception, **gold caps** | the only rung that is *better* late: hyper-training a level-55 team at the last gate is the correct moment |
| — | champion | netherite as a reward, not a sale | nothing left to pace |

**The one rung my own test says is in the wrong place: `crafting_upgrade`.** The owner's
goal is "never need to build a house", and a player cannot credibly stop building until
they can craft on the road. Badge 6 is three-quarters through the campaign. Two fixes,
both proposals:

1. Move it to Brock's — the masons' town has the better identity claim anyway, and its
   dressing already holds a stonecutter *and* an anvil bench.
2. Sell it at Brock's at a price the player cannot meet until about badge 3: **price as
   the gate**, which is the one gate CobbleDollars gives for free.

**I recommend 2.** It is the only mechanism in the whole document that needs no flag, no
dialogue visibility, no datapack and no restart, and it gives exactly the legibility that
`PROGRESSION_UNLOCKABLES.md` §1.4 says a suppressed recipe destroys: the rung is visible
from badge 1 and affordable at badge 3. §1.1 lists it at Brock's on that basis.

---

## 5. What this collides with

### 5.1 The trainer card is a tax, not a rung — and nothing in this region sells it

**The most urgent collision in the list, and the cheapest to check.**
`spawningRequiresTrainerCard = true` (`modpack/config/rctmod-server.toml:87`): without a
card in inventory, trainers do not spawn naturally at all. The card costs 500 and appears
**only** in `defaultShop`. Every one of our 14 Mart clerks carries authored
`CobbleMerchantShop` NBT whose contents are `stock_policy.mart.items` =
`poke_ball`, `potion`, `antidote` — no card. Unless `defaultShop` is the fallback for a
merchant with no shop compound (§0, NOT VERIFIED), **a new player in this region cannot
buy a trainer card and therefore never meets a wild trainer.**

Three consequences, all of which need the owner:

- It is a **tax on the first hour**, paid out of wild-Pokémon income alone
  (`earnCobbleDollarsFromWildPokemon: true` at `cobbleDollarsIncomeMultiplier: 0.5`),
  because trainer income is what it unlocks. 500 CD against a Mart Poké Ball at 200.
- It must be stocked somewhere, or given. **Recommend: Pallet's clerk stocks it at
  rung 0**, beside the backpack and the bedroll — a hometown handing over the licence is
  the right scene — or it is the starter kit's item and costs nothing.
- `spawnTrainerAssociation = true` means RCT's own association NPC already spawns near any
  village with three occupied beds. Our towns have beds. **So RCT's progression counter and
  its trade are already standing in our markets, authored by nobody, and it is not in
  `data/placements.json`** — the "our list is not the world" case, third instance.

### 5.2 Two level ladders keyed on different defeats

Our `gymN_cleared` flags are set by `trainer_defeat` on named ids (`kanto_brock`,
`kanto_misty`, …). RCT's cap comes from "the strongest Pokémon from the party of their
**next required trainer** in a series", whose chain is Cobbleverse's `requiredDefeats`
read from COBBLEVERSE-RCT-DP-v20 — and `data/progression.json` note 7 records that
**which leader sits in which town is still an open trainer-design decision.**

If town order and RCT's required order differ, a player clears town 3's gym, receives our
rung, and **RCT's cap does not move.** The two cannot both be authoritative. Reconcile one
way or the other: either re-author the RCT series chain to our town order, or make our
flags follow RCT's chain. This belongs to `trainer-balance-designer` and is not something
the ladder can decide for itself.

### 5.3 `freeroamRequiresCompletedSeries = true` means income, not level, paces the ladder

The cap is always the next leader's ace exactly, and there is no freeroam escape until the
series is done. So a money-priced rung is paced entirely by **income**, and income is
`cobbleDollarsIncomeMultiplier: 0.5` against a level-capped team. **Nobody has measured
CobbleDollars per hour at cap 20.** Every price in §1 is therefore a proposal with no
evidence under it. See U-1: this is the one measurement that would turn the price column
from guess into design.

### 5.4 `maxLevelDiff = 10` and `forceBattleMaxLevelDiff = 12` gate the off-path towns already

A player who detours to the mining town or the port before the badges that make the road
survivable meets trainers up to twelve levels above them, forced into battle on sight at
16 blocks (`forceBattleOnSight = true`, `forceBattleMaxDistance = 16.0`,
`forceBattleLookTicks = 30`). **So the off-path rungs in §1.2 are already gated by
survivable travel, independently of any flag.** The flags I chose there (`gym3_cleared`,
`gym5_cleared`, `gym6_cleared`) are a guess at reachability and need checking against
`data/towns.json`'s graph (U-4). Where travel already gates a shelf, **leave it ungated**:
a flag that duplicates a difficulty gate is a flag that adds nothing and costs a restart.

### 5.5 RCT owns the badge reward

Badges come from each leader's RCT loot table on first defeat. The market must not hand
out a badge-shaped token as well.

---

## 6. Unknowns — experiment candidates, in the order they should be settled

| # | Unknown | Blocks | Smallest proof |
| --- | --- | --- | --- |
| **U-1** | **CobbleDollars income per hour at level cap 20, and at 40.** | every price in §1 | an hour of play on staging with `cobbledollars query` read at the start and end. Not a datapack, not a mod: one measurement. **Highest value in this table.** |
| **U-2** | **Can a datapack suppress a mod's recipe?** | the entire ladder: without it, every tier stays craftable and the shop is a convenience | `PROGRESSION_UNLOCKABLES.md` §6.1 — suppress one backpack tier recipe, boot, open REI |
| **U-3** | **Is `defaultShop` a fallback for a merchant with no `CobbleMerchantShop`?** | §5.1 — whether a trainer card can be bought anywhere in this region | summon a bare CobbleMerchant with no shop NBT on staging and right-click it |
| **U-4** | **Which off-path towns are reachable at which badge**, by the `data/towns.json` graph and §5.4's level diff | the three off-path flags in §1.2 | a tool read of `data/towns.json` plus `data/route_trainers.json` levels. No server needed |
| **U-5** | **Can a "field bedroll" differ from a sleeping bag?** `sleepingBagEffects` is server-wide. | Northlight's only rung | read the `comforts` jar for a per-item effect key. If there is none, Northlight sells hammocks and colour, and that is all — **say so rather than inventing a tier** |
| **U-6** | **Two players, one dialogue counter, at once.** | whether every gated counter is one NPC or one button per shelf | `MARKET_GATING.md` §5 criterion 5; blocked on a second account |
| **U-7** | **Does the blank's material grade decide which moves a TM reaches?** The 24 ids are verified; the semantics are ASSUMED. | the power strand's six rungs (§2.5) | a TMCraft jar read, for `cobblemon-researcher` |
| **U-8** | **Does `lumymon:store_card` gate the remote PC?** | whether remote Pokémon storage can be a rung at all, or is day-one for everyone | `PROGRESSION_UNLOCKABLES.md` §6.4 |

**U-1 and U-2 should be settled before any of §1 is built.** U-1 because the price column
is the whole gate for the rung I recommend in §4, and U-2 because it decides whether the
ladder is a ladder.

---

## 7. New flags: requests, not assumptions

**The eight badge rungs need no new flag.** `gym1_cleared`…`gym8_cleared` and
`champion_cleared` already exist and already carry what the ladder needs.

Requested only if the owner prefers **arrival** to **badge count** for the off-path
counters (§1.2, U-4):

| Requested flag | What would set it | Why it does not exist yet |
| --- | --- | --- |
| `reached_mining_town` | arrival in the town | `data/progression.json` has **no arrival `set_by` kind** today; its kinds are `trainer_defeat` and quest fields. Adding one is a schema change for `minecraft-systems-dev`, not something this document assumes |
| `reached_sunset_west` | as above | as above |
| `reached_northlight` | as above | as above |

**Recommendation: do not add them.** §5.4 shows travel already gates these towns through
the level diff, and a flag that duplicates a difficulty gate costs a schema change and a
server restart and buys nothing.

---

## 8. Open questions for the owner, one at a time

1. **Is the backpack the spine, or is the power strand?** §2.5 argues the convenience arc
   finishes at badge 3 of 8 and that TM grades, key items, stones and caps are the sharper
   ladder. Two strands at every counter is the proposal; one strand is cheaper.
2. **`crafting_upgrade` at Brock's, priced out of reach until badge 3 — or at Sabrina's on
   `gym6_cleared`?** §4 recommends Brock's with price as the only gate: no flag, no
   datapack, no restart, and the rung is visible for five badges before it is affordable.
3. **Should `sophisticatedbackpacks-server.toml` be re-tuned in `modpack/config/`?** As
   Cobbleverse ships it, gold, diamond and netherite add 15, 12 and 12 slots. Four of six
   tiers have almost nothing left to give (§2.4.1).
4. **Where is `rctmod:trainer_card` bought — Pallet's clerk at 500, or is it free in the
   starter kit?** §5.1. Until this is answered a new player may meet no trainers at all.
5. **`stack_upgrade_*` at Sabrina's or the mining town?** A study town sells compression;
   a smelter town has an equal claim. One or the other, not both.
6. **Does `tableland_stop` get a trader record?** It is the only off-path stop whose
   dressing (sample piles, a sieve, ore crates) already argues for a counter, and it has
   no record today.
7. **Is `netherite_backpack` `champion_cleared`'s reward, or is it not in the campaign?**
   §1.1 row 9 recommends the reward. It is +12 slots.
8. **Do `everlasting_upgrade` / `infinity_upgrade` / `survival_infinity_upgrade` exist in
   this campaign at all?** §1.3 recommends no: they end the economy the markets exist for.
9. **Which is authoritative, our town order or RCT's `requiredDefeats` chain?** §5.2. They
   must be reconciled, not layered, and the answer constrains `data/trainers.json`.

---

## 9. If this is accepted: the ordered plan, and who does each step

Each step is small enough to be one experiment or one content task.

| # | Step | Agent |
| ---: | --- | --- |
| 1 | Measure CobbleDollars income at cap 20 and cap 40 on staging (U-1) | main session (a staging run is not delegated) |
| 2 | Recipe-suppression proof: one backpack tier, boot, REI (U-2) | `qa-reviewer` grades it; the pack is `datapack-content-dev`'s |
| 3 | Bare-merchant `defaultShop` fallback check (U-3), and settle where the trainer card is bought | main session, one RCON summon |
| 4 | Reachability-by-badge read over `data/towns.json` and route trainer levels (U-4) | `repo-scout` to locate, `test-author` for the check |
| 5 | Jar reads: `comforts` per-item effects (U-5), TMCraft blank semantics (U-7), `lumymon:store_card` (U-8) | `cobblemon-researcher` |
| 6 | A `data/` schema for a gated shelf (`data/market.json`, or a `shelves` block in `data/traders.json`) and its validation | `minecraft-systems-dev` with `test-author` |
| 7 | **EXP: one badge-gated counter in one town** — `MARKET_GATING.md` §5's six criteria, on the disposable world | `datapack-content-dev` builds; `qa-reviewer` grades |
| 8 | Re-price the whole of §1 against step 1's measurement | `trainer-balance-designer` |
| 9 | Reconcile the RCT chain with town order (§5.2) | `trainer-balance-designer`; may need an ADR |
| 10 | Only then: the remaining fifteen counters | `datapack-content-dev` |

**Nothing past step 7 should be built before step 7 passes** (principle 20): sixteen
counters authored against an unproven gate is sixteen counters to redo.

---

## 10. Where an ADR is owed

Not written here, because each needs an answer from §8 first:

- **The gated-counter mechanism** (dialogue NPC + flag visibility + checked CobbleDollars
  charge, with the trade GUI given up at gated counters). It constrains every market in
  the region, it is expensive to reverse once sixteen counters exist, and its evidence is
  `MARKET_GATING.md` plus EXP-022, EXP-040, EXP-042 — real evidence, but the counter
  itself is unrun. **Propose the experiment (step 7) before the ADR.**
- **Whether the RCT series chain or our town order is authoritative** (§5.2). This one is
  expensive to reverse in both directions and should have an ADR as soon as Q-9 is
  answered.
