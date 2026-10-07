# EXP-055: a summoned villager keeps fixed item-for-item trades

## Objective

The owner, 2026-10-07 (docs/STATE.md "What is decided", the owner's answers item 5): late-game items by **direct
trade**, no money where possible -- "4 netherite ingots for a master ball or something difficult, money systems will
be abused somehow". CobbleDollars cannot barter: an Offer holds item, price and stock only
(docs/OVERNIGHT_REVIEW_2026-10-06.md N63). So the barter is a vanilla villager whose offers are written into its
summon command. Prove that such a villager, with a **modded** item for sale, trades exactly as written: no restock
effect, no price drift, no per-player discount, and that it survives a restart and a chunk unload.

Mechanism rung (CLAUDE.md principle 6): Cobblemon has no barter NPC; CobbleDollars (a Cobbleverse dependency) prices
in money only (N63); the cheapest rung that trades item for item is vanilla entity data in a summon command
(functions/commands). No addon, script or mod.

## Success criteria

(a) Readable over RCON with NO player (`tools/direct_trades.py rcon_checks()`):

1. `scoreboard players get #breach cob_dt` is 0 (the booth was carved; 1 means the shell met air, water or lava and
   nothing was placed).
2. `execute if entity @e[type=minecraft:villager,tag=cob_dt_barterer]` finds exactly one.
3. `data get entity @e[type=minecraft:villager,tag=cob_dt_barterer,limit=1] Offers.Recipes` returns the two
   experiment recipes exactly as in the summon (`build/datapacks/cobblers_direct_trades/.../place.mcfunction`):
   every `uses` 0, `maxUses` 9999, `priceMultiplier` 0.0f (0.2f on the control), `demand` 0, `specialPrice` 0,
   `xp` 0, `rewardExp` 0b. **Not** two random armorer trades: that would mean the Offers failed to parse (see
   "Profession").
4. `data get entity ... VillagerData` is `{level:5, profession:"minecraft:armorer", type:"minecraft:plains"}`.
5. Items 2-4 hold again after a server restart, and after the chunk unloads and reloads (`forceload remove`, no
   player within view distance, wait past the unload, then `forceload add` and read again).

(b) The owner, in game (two players for item 4):

1. Both offers show in the trade screen, with the Poke Ball and Great Ball icons and counts as written.
2. `exp_two_inputs` trades: 4 Poke Balls + 1 Great Ball out, 1 Great Ball back. Shift-click trades in bulk.
3. After 20 or more trades, closing and reopening the screen, a full day/night cycle (`time add 24000`) and a
   restart, `exp_two_inputs` still asks 4 Poke Balls + 1 Great Ball. `exp_control_multiplier` is the control: write
   down whether its cost fell below 4 (see "Price").
4. A second player opening the screen sees the same costs, both before and after the first player's trades.
5. Over RCON after the trades: `Offers.Recipes[0].uses` counts the trades made; `demand` and `specialPrice` are
   still 0 (or say what they are).

## Dependencies

Minecraft 1.21.1 vanilla villager; Cobblemon 1.8.0 items (`cobblemon:poke_ball`, `cobblemon:great_ball`); MobsBeGone
(blacklists `minecraft:witch`, `minecraft:zombie_villager`, `minecraft:pillager`, `minecraft:ravager`,
`minecraft:vindicator`, `minecraft:evoker`, `minecraft:iron_golem`; not `minecraft:villager`: grep of
`base-pack/cobbleverse/config/mobsbegone-blacklist.json`, 2026-10-07).

## Implementation

- `data/direct_trades.json`: the site, the barterer, the fixed-trade fields, the two experiment offers and the
  eight **held** barter lines (`status: proposal`, `approved: false`).
- `tools/direct_trades.py build` writes the world-local pack `cobblers_direct_trades`: `place` (a breach check of all
  98 shell cells, a 5x5x5 hollow `minecraft:stone_bricks` booth with a glowstone in the ceiling, the summon, a
  100-tick schedule) and `place_done` (one barterer kept by tag, older copies killed). Only experiment offers and
  `approved: true` lines are in the summon.
- `tools/reapply.py` step **R18DT** (after R18AF): `forceload add 3634 6462`, wait 3 s, `function
  cobblers:direct_trades/place`, wait 7 s, `forceload remove 3634 6462`. Prepare job `direct_trades:build`. The pack
  is in SERVER_PACKS and WORLD_LOCAL.
- `tests/test_direct_trades.py`: the summon carries the fixed fields exactly, held lines are not placed, the guards
  refuse each bad mutation, the coverage gate fails without R18DT.

**The test spot.** Villager feet at **(3634, 102, 6462)**, standing on the booth floor at y101; interior x3633-3635,
y102-104, z6461-6463; shell x3632-3636, y101-105, z6460-6464. Measured by `python tools/direct_trades.py build`
from the canonical heightmap (`tools/ground.py`): ground y112 at the site, y111-112 across the 5x5 footprint, y111
the lowest within 4 blocks, so six layers of rock (y106-111) over the ceiling. It is 9 blocks under the Holdfast
counter (data/markets.json `holdfast`, badge 8, at (3634, 113, 6462)). Reach it with
`/tp @s 3633.5 102 6462.5`.

### Why the summon holds (cited, with what is verified and what is not)

Sources: the vanilla 1.21.1 client jar (`ModrinthApp/meta/versions/1.21.1-0.19.5/1.21.1-0.19.5.jar`, obfuscated),
read with `javap -c -p` and a string-constant scan on 2026-10-07. The obfuscated class names are matched to their
roles by their own strings (e.g. `cmk` logs "Villager {} was struck by lightning {}."); the Mojang names below are
that inference.

**Fields** (VERIFIED: string constants). `dbu` (MerchantOffer) codec keys, in order: `buy`, `buyB`, `sell`, `uses`,
`maxUses`, `rewardExp`, `specialPrice`, `demand`, `priceMultiplier`, `xp`. `dbv` (MerchantOffers) wraps them as
`fieldOf("Recipes")` of a list. `dbs` (ItemCost, the `buy`/`buyB` form): `id`, `count`, `components`. `cml`
(VillagerData): `type`, `profession`, `level`. `cmf` (AbstractVillager) saves `Offers`; `cmk` (Villager) saves
`VillagerData`, `Xp`, `Gossips`, `RestocksToday`. `NoAI`, `Invulnerable`, `PersistenceRequired`, `Silent`,
`CustomName`, `Rotation`, `Tags` are the standard entity/mob keys the repo already summons with
(`tools/apricorn_farm.py merchant_data`). Every fixed field is written explicitly; no codec default is relied on.

**Price** (VERIFIED: bytecode of `dbu` and `cmk`).
- Cost A = clamp(count + max(0, floor(count * demand * priceMultiplier)) + specialPrice, 1, max stack). With
  `priceMultiplier` 0 the demand term is 0 whatever `demand` becomes.
- Cost B is returned as written: no demand, no special price, no discount of any kind.
- `updateDemand`: demand = demand + uses - (maxUses - uses); it only matters through priceMultiplier.
- Per-player special price, applied when a player opens the screen: specialPrice -= floor(reputation *
  priceMultiplier) for each offer -- **zeroed by priceMultiplier 0** -- and, if the player has Hero of the Village,
  specialPrice -= max(1, floor((0.3 + 0.0625 * amplifier) * costA count)) -- **NOT** multiplied by priceMultiplier.
  Hence the rule every barter line obeys: cost A has count 1 (the clamp holds it at 1) and the bulk cost is cost B.
  Whether Hero of the Village is even obtainable here is unknown (pillagers are blacklisted; a raid's outcome with
  no raiders is not checked): the rule makes it not matter.
- Not verified: that the special price is reset when the screen closes (from memory of the source; the two-player
  check (b)4 observes it).

**Restock** (partly verified). Restock resets `uses` (and calls updateDemand); with maxUses 9999 and priceMultiplier
0 it changes neither stock nor price, so whether a NoAI villager restocks (it has no job site and, as recalled, its
brain does not tick with NoAI) does not matter. NOT verified: that NoAI stops the brain.

**Profession** (partly verified). Level 5 is the last level, and `xp` 0 on every offer means trading never adds
villager experience, so no level-up can append vanilla trades. A villager only generates trades when its Offers are
null: if the summon's `Offers` failed to parse, it would generate level-5 armorer trades on first open -- check (a)3
catches that. NOT verified in bytecode: the brain's profession reset applies only at level 1 with 0 experience
(recalled from the source); NoAI and level 5 each stop it, and check (a)4 after a restart observes it. The brief's
"an unemployed or nitwit villager does not trade" is relayed: those professions have no trades table, which is why
`check()` refuses them; whether an unemployed villager with written Offers would trade was not tested.

**Lightning** (VERIFIED: bytecode of `cmk`'s thunder handler). Unless the difficulty is peaceful, the villager logs
the strike, creates a witch, copies its position, NoAI and name, makes it persistent, calls `addFreshEntityWithPassengers`
on it, releases its POIs and **discards itself**. The discard does not depend on the witch being added, and there is
no invulnerability check. MobsBeGone cancels blacklisted entities in `ServerLevel.addEntity` (relayed: docs/STATE.md
"No vanilla hostiles", a summon test of a witch that answered "Summoned" and did not exist), so **a struck barterer
simply vanishes and no witch appears**. Hence the booth: NOT verified in bytecode, recalled from the source -- a bolt
hits entities within 3 blocks of its strike point (on top of the highest block), and only targets entities that can
see the sky. The booth's villager is 9 under the ground, under 6 layers of rock, with no sky; `booth()` refuses a
site where the feet are not 4 below the lowest ground within 4 blocks.

**Multiplayer.** Stock and price live on the one villager, not per player: maxUses 9999 so nobody empties it for the
others; priceMultiplier 0 so nobody's reputation changes anyone's price; cost A count 1 so nobody's Hero of the
Village does either. NOT verified: a villager trades with one player at a time (recalled), so a second player waits
for the first to close the screen; check (b)4 observes it. Late join, death and disconnect touch no state: the trade
is atomic in the screen, and no score or flag is kept per player.

### The item-for-item edges (for the economy audit)

`python tools/direct_trades.py edges` prints these from the data. Bank figures are `data/bank.json` `buys` (what the
bank PAYS per unit), counter figures `data/markets.json` prices, both read 2026-10-07; "-" is not listed there.

| Line | Placed | Inputs | Output | Bank pays for inputs | Output elsewhere |
|---|---|---|---|---|---|
| exp_two_inputs | yes (experiment) | 4 cobblemon:poke_ball + 1 cobblemon:great_ball | 1 cobblemon:great_ball | - | output is an input: never a gain |
| exp_control_multiplier | yes (experiment) | 4 cobblemon:poke_ball (1 at worst) | 1 cobblemon:poke_ball | - | output is an input: never a gain |
| master_ball | held | 1 minecraft:diamond_block + 4 minecraft:netherite_ingot | 1 cobblemon:master_ball | diamond 120 (x9 if a block is crafted from diamonds), ingot 900 x4 | counter 27000 CobbleDollars |
| ability_patch | held | 1 cobblemon:ability_capsule + 2 minecraft:netherite_ingot | 1 cobblemon:ability_patch | ingot 900 x2 | capsule on a counter at 10000; patch an arena prize |
| life_orb | held | 1 minecraft:diamond_block + 4 minecraft:netherite_scrap | 1 cobblemon:life_orb | scrap 202 x4 | - |
| choice_band | held | 1 minecraft:diamond_block + 3 minecraft:netherite_scrap | 1 cobblemon:choice_band | scrap 202 x3 | - |
| choice_specs | held | 1 minecraft:diamond_block + 3 minecraft:netherite_scrap | 1 cobblemon:choice_specs | scrap 202 x3 | - |
| choice_scarf | held | 1 minecraft:diamond_block + 3 minecraft:netherite_scrap | 1 cobblemon:choice_scarf | scrap 202 x3 | - |
| leftovers | held | 1 minecraft:diamond_block + 2 minecraft:netherite_scrap | 1 cobblemon:leftovers | scrap 202 x2 | - |
| destiny_knot | held | 1 minecraft:diamond_block + 2 minecraft:netherite_scrap | 1 cobblemon:destiny_knot | scrap 202 x2 | - |

None of the eight outputs is in the bank's buy list (grep of `data/bank.json` 2026-10-07), so no line's output sells
back for money; whether the bank's `crafts`/`exchanges` reach them is the auditor's to check. Every output id has a
`item.cobblemon.<id>` key in the Cobblemon 1.8.0 jar's `en_us.json` (read 2026-10-07; a lang key is a proxy for the
registry, not the registry).

## Test instructions

Staging only, never the live world; the server checks and the shared lock first (CLAUDE.md "Live server safety").

1. `python tools/reapply.py prepare` (builds the pack), `install` onto staging, restart (world-local packs load at
   boot), then `python tools/reapply.py run --only R18DT`.
2. Run the five RCON reads of (a); record the full `Offers.Recipes` output.
3. Restart; read (a)2-4 again. Then `forceload remove 3634 6462`, keep every player out of view distance, wait
   past the unload, `forceload add 3634 6462`, read again, `forceload remove`.
4. The owner: `/tp @s 3633.5 102 6462.5`, `/give @s cobblemon:poke_ball 128` and `cobblemon:great_ball 32`, then
   (b)1-5 with a second player for (b)4.

## Results

NOT_EXECUTED. Nothing here has run in a server. What ran (2026-10-07, worktree): `python tools/direct_trades.py
build` (4 files, 107 commands, barterer at (3634, 102, 6462)); `python tools/function_limits.py` on the pack (2
files, 0 problems); `tests/test_direct_trades.py` (17 passed); `reapply.uncovered`/`unreferenced` against the built
pack with only R18DT as the step list (both empty; without the step, the pack is named as uncovered).

## Limitations

- The booth is reached by `/tp`: it is an experiment spot, not a player-facing site (decision `barterer_site`).
- The breach check reads only the 98 shell cells; a cellar or cave 1-6 blocks above the ceiling is not checked
  (the ceiling itself is).
- The town plan (`derived/towns`) was not available in the building worktree; the site is under the counter's own
  record, not checked against basements of nearby templates beyond the breach check.
- The barter lines' balance (inputs, which items, whether held items belong in this campaign at all) is a proposal
  for the owner and the trainer-balance designer; their economy is the independent auditor's (`tools/economy_audit.py`).

## Decision

Pending: EXP-055 runs first. Then the owner approves lines (`approved: true`, `status: "approved"` per line in
`data/direct_trades.json`), picks the player-facing site, and decides whether the counter's 27000-CobbleDollar Master
Ball stays beside the barter (`decisions_pending`).

## Follow-up

- If (a)3 shows random armorer trades, the Offers did not parse: compare the summon against the field list above.
- If the control's cost falls and the fixed line's does not, priceMultiplier 0 is confirmed as the holding field.
- If the barterer is missing after a storm, the booth failed the lightning reasoning: read the server log for
  "was struck by lightning".
