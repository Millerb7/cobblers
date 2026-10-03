# Tiered goods: what in the pack has tiers, which ids are real, and which can be gated

**Status: audit, 2026-10-03.** Every id below was read out of the jar the server runs
(`C:/Users/wnd/Documents/github/cobblers-server/mods/`, read only: `assets/<ns>/lang/en_us.json` item keys and
`data/<ns>/recipe/*.json`), not out of the 1.7.42 REI index `docs/research/PROGRESSION_UNLOCKABLES.md` had to use
(its §0: "The mod jars are not on this machine ... Nothing in this document is a recipe read out of a jar"). The
scan script is not committed; its method is one `zipfile` pass per jar, and the market tool re-checks every id it
sells against the same jars (`python tools/markets.py ids --jar-dir <server>/mods`).

Labels: **VERIFIED** = read in the jar or a config at the path given. **ASSUMED** = inferred, not run.
Nothing here was run in a game.

This document feeds `data/markets.json` (the per-town shelves) and the recipe overlay
`modpack/config/sophisticatedcore-common.toml`. The mechanism is `docs/mechanics/MARKET_GATING.md`'s; the prices
are `docs/mechanics/PROGRESSION_LADDER.md` revision 2's, corrected where an id was wrong (§3).

## 1. The answer in one table

| Mod (jar) | Tiers | Gate the SUPPLY by | Rung | In the markets? |
| --- | --- | --- | --- | --- |
| **Sophisticated Backpacks** `sophisticatedbackpacks-1.21.1-3.23.4.3.106.jar` | 6 backpack tiers; 56 upgrades incl. basic/advanced pairs, a 6-step stack ladder | **`sophisticatedcore-common.toml` `enabledItems`**, documented in the file: "Disable / enable any items here (disables their recipes)" | 4 (configuration) | **yes: the spine** |
| TMCraft `tmcraft-1.4.19+1.8.0.jar` | 6 blank grades x 4 forms; **each TM recipe names one grade** | no config; only a datapack recipe override | 5, **unproven** (U-5) | **no** (§2.2) |
| Only Bottle Caps `Only Bottle Caps-1.5.0-fabric.jar` | stat caps, gold cap | gold is already off treasure (`obc-common.toml` `goldBottleCap = 0.0`) | 4, already set | yes: gold cap at Holdfast |
| Mega Showdown `mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar` | key item per mechanic | none needed: the bracelet's recipe needs a `keystone` | — | yes: the bracelet at Fenhide |
| Sophisticated Storage `sophisticatedstorage-1.21.1-1.3.7.9.139.jar` | 6-tier chests, barrels, shulker boxes | the same `enabledItems` list | 4 | no: furniture, and its in-place tier upgrades make a sold box leak (§2.5) |
| Waystones `waystones-fabric-1.21.1-21.1.37.jar` | scrolls, warp stone | no per-item key; recipes are cheap | — | yes, as convenience only (Sunset West) |
| Comforts `comforts-fabric-9.0.5+1.21.1.jar` | none (colours only) | — | — | yes, as convenience (Pallet, Northlight) |
| CobbleCuisine `cobblecuisine-2.0.1-1.7.rc1.jar` | friendship 1 / 6 / 12 (`cobblecuisine.json` `beanFriendship`, `pokepuffFriendship`, `malasadaFriendship`) | — | — | yes (Greenhollow, Steepside) |
| Cobblemon `Cobblemon-fabric-1.8.0+1.21.1.jar` | ball, medicine and vitamin ladders; type-boost held items | the Mart's `stock_policy` withholds them; a gated counter releases them | 5+7 | yes: the power strand |
| Iron Chests `IronChests-2.0.4.jar` | 8 chest tiers + upgrade kits | recipe only | — | no: a house, which the brief removes |
| Tom's Storage `toms_storage_fabric-1.21-2.3.0.jar` | wireless terminal, advanced wireless terminal (range by beacon level) | recipe + config | — | no: late logistics, owner's call |
| Cobblenav `cobblenav-fabric-2.4.1.jar` | `pokenav_item`, `pokefinder_item`, `fishingnav_item` (no tiers) | — | — | no |
| RCT `rctmod-fabric-1.21.1-0.19.0-beta.jar` | `trainer_card` (licence, not a tier) | — | — | already on Pallet's Mart clerk (`data/traders.json` `stock_policy.trainer_card`) |

## 2. Each mod, with the evidence

### 2.1 Sophisticated Backpacks: the spine, and gateable by configuration

**Tier ids, VERIFIED in the jar's lang:** `sophisticatedbackpacks:backpack`, `copper_backpack`, `iron_backpack`,
`gold_backpack`, `diamond_backpack`, `netherite_backpack`. Slot counts are Cobbleverse's
(`base-pack/cobbleverse/config/sophisticatedbackpacks-server.toml`, PROGRESSION_UNLOCKABLES §1.2): 27/1, 45/1,
81/7, 96/8, 108/9, 120/10 (inventory/upgrade slots).

**Upgrade ids, VERIFIED (57 items in the lang):** `upgrade_base`; `pickup`, `magnet`, `filter`, `deposit`,
`restock`, `refill`, `feeding`, `compacting`, `void`, `tool_swapper`, `pump`, `jukebox` each with an `advanced_`
form; `crafting`, `anvil`, `smithing`, `stonecutter`; `smelting`, `smoking`, `blasting` and `auto_` forms;
`inception`, `tank`, `battery`, `xp_pump`, `everlasting`, `infinity`, `survival_infinity`;
`stack_upgrade_starter_tier`, `stack_upgrade_tier_1`..`tier_4`, `stack_upgrade_omega_tier`,
`stack_downgrade_tier_1`..`3` (each id carries the `_upgrade` suffix where the jar does).

**How a tier is obtained, VERIFIED from the recipes:** crafting only (PROGRESSION_UNLOCKABLES §1.3 for loot and
drops). `copper_backpack` = 8 copper ingots round a `backpack`; `iron_backpack` = 8 iron round a `backpack`, and
`iron_backpack_from_copper` = 4 iron round a `copper_backpack`; `gold_backpack` = 8 gold round an `iron_backpack`;
recipe type `sophisticatedbackpacks:backpack_upgrade`, which carries the contents into the new tier (ASSUMED from
the type name; not read in the class).

**The gate, VERIFIED, and it is configuration (rung 4), not a datapack.** Every recipe in the jar carries
`"fabric:load_conditions": [{"condition": "sophisticatedcore:item_enabled", "itemRegistryName": "<id>"}]`
(`data/sophisticatedbackpacks/recipe/copper_backpack.json` and the rest). The condition reads
`sophisticatedcore-common.toml`'s `enabledItems`, whose shipped comment is
**"Disable / enable any items here (disables their recipes)"**, entries in the form `"<id>|true"`
(`base-pack/cobbleverse/config/sophisticatedcore-common.toml:3-4`). In the jar, `isItemEnabled` is read by
`ItemEnabledCondition` (recipes), `ItemBase` and `BlockItemBase` (`addCreativeTabItems`) and `BackpackItem` (its
creative-tab colours). **Nothing else reads it**, so a disabled item stays registered, can be `give`n and works;
only its recipe and its creative-tab entry go. That is exactly "sold, not crafted". (Class-reference reading of
`sophisticatedcore-1.21.1-1.2.9.21.168.jar`; **not run in game**: audit item A-6.)

Note the condition is keyed on the RESULT, so disabling `iron_backpack` removes both `iron_backpack` and
`iron_backpack_from_copper`, and disabling `advanced_magnet_upgrade` removes
`advanced_magnet_upgrade_from_basic` too.

**Residual bypasses, recorded rather than closed** (each is a higher item still craftable when a lower one is sold):

| Sold (recipe off) | Still craftable | Why left |
| --- | --- | --- |
| `diamond_backpack` | `netherite_backpack` (smithing from a diamond backpack) | needs the bought diamond pack, so it is gated by the purchase; PROGRESSION_LADDER §1.1 row 9 makes netherite a champion reward, owner Q-5 |
| `stack_upgrade_tier_1` | `stack_upgrade_tier_2`, `_3`, `_4`, `omega` (each from the tier below) | gated by the bought tier 1; `maxUpgradesPerStorage` caps stack upgrades at 3 per pack |
| `magnet_upgrade` | `advanced_magnet_upgrade` from `upgrade_base` | the advanced recipe needs more; selling only the basic one keeps Fenhide's shelf in budget. Owner call |
| `filter_upgrade` | `advanced_filter_upgrade` | as above |
| all sold upgrades | everything not sold (`deposit`, `restock`, `refill`, `pump`, `tool_swapper`, `jukebox`, the `chipped/*` tables) | not on any shelf, so withholding them buys nothing |

### 2.2 TMCraft: real tiers, and NOT built here

**VERIFIED in `tmcraft-1.4.19+1.8.0.jar`:** six grades x four forms, `tmcraft:{copper,iron,gold,emerald,diamond,
netherite}_blank_{disc,book,egg,star}`. **U-4 is answered:** the grade gates the move, because each
`data/tmcraft/recipe/tm_<move>.json` is a shapeless recipe naming exactly one blank grade, e.g. `tm_thunderbolt`
= `diamond_blank_disc` + `electric_gem` + `electirizer`, `tm_hyperbeam` = `netherite_blank_disc` + `normal_gem` +
`sculk_shrieker`. Of 334 TM recipes: copper 12, iron 42, gold 120, emerald 91, diamond 38, netherite 31.
**Emerald is not a step on the power line:** it holds status moves (`agility`, `calmmind`, `bulkup`, ...), and its
blank is smithed from **gold**, like diamond's (`emerald_blank_disc` and `diamond_blank_disc` both take
`gold_blank_disc` as the base). The chain is copper (1 copper ingot, shapeless) -> iron -> gold -> {emerald,
diamond} -> netherite, each by `smithing_transform` with `tmcraft:move_upgrade_smithing_template`.

**Why no shelf sells blanks:** a copper blank is one copper ingot and each grade is one ingot more, and TMCraft
ships no config. Selling a blank the player crafts for an ingot gates nothing. Gating it needs the blank recipes
replaced by a datapack (rung 5), and "can a datapack stop a mod's recipe loading" is exactly U-5, untested in this
pack. PROGRESSION_LADDER §2.5 hung five power rungs on these; **they are replaced** in `data/markets.json` by the
town's type-boost held item and released Mart lines, and the blanks wait on U-5.

### 2.3 Only Bottle Caps

VERIFIED ids: `obc:bottle_cap`, `bottle_cap_{hp,attack,defence,special_attack,special_defence,speed}` and
`_withered` forms, `bottle_cap_gold`. `bottle_cap_gold` is craftable from the six stat caps
(`data/obc/recipe/bottle_cap_normal/bottle_cap_gold.json`); each stat cap is a `bottle_cap` ringed by eight mint
leaves. Treasure: `goldBottleCap = 0.0` in both tables (PROGRESSION_UNLOCKABLES §2.6). So a gold cap is either six
silver-cap finds or a purchase, and the purchase is the reliable tap.

### 2.4 Mega Showdown

VERIFIED: `mega_showdown:mega_bracelet` (+ six colours) and `mega_ring`, each crafted around a
`mega_showdown:keystone` with a diamond and iron. The keystone's own source is not traced here (ASSUMED: world
generation or loot). The bracelet on a shelf is a guaranteed source, not an exclusive one.

### 2.5 Sophisticated Storage

VERIFIED: 109 items, including `shulker_box`, `copper_`/`iron_`/`gold_`/`diamond_`/`netherite_shulker_box`, the
same for barrels and chests, and in-place tier kits `basic_to_iron_tier_upgrade` etc. Gateable by the same
`enabledItems`. **Not sold:** a bought iron shulker box is upgraded in place by a craftable tier kit, so a
shelf would have to withhold a dozen kits too, and the boxes are storage the backpack already supplies.

### 2.6 The rest, checked and left off the shelves

- **Waystones** (VERIFIED): `blank_scroll`, `bound_scroll`, `return_scroll`, `warp_scroll`, `warp_scroll_bound`,
  `portal_scroll`, `warp_stone`, `warp_plate`, `attuned_shard`. `return_scroll` crafts 3 from gold nuggets, ink
  and paper; `warp_scroll` adds an ender pearl. Sold at Sunset West as a convenience, priced as one.
- **Comforts** (VERIFIED): **there is no `comforts:sleeping_bag`.** The items are `comforts:sleeping_bag_<colour>`
  and `comforts:hammock_<colour>` (16 colours each). PROGRESSION_LADDER §1.1 names the colourless id; the shelf
  uses `sleeping_bag_brown` and `hammock_white`.
- **CobbleCuisine** (VERIFIED): **there is no `cobblecuisine:malasada` or `cobblecuisine:pokepuff`.** Malasadas
  are `sweet_`/`sour_`/`dry_`/`bitter_`/`spicy_malasada`, pokepuffs `sweet_`/`mint_`/`citrus_`/`mocha_`/
  `spice_pokepuff`. The shelf uses the sweet ones. Whether flavour changes the friendship gain is NOT VERIFIED.
- **Cobblemon** (VERIFIED): `x_defence`, `x_special_attack`, `x_special_defence` (British spelling; `x_defense`
  does not exist); `charcoal_stick`, not `charcoal`; no `repel`, no `old_rod`/`great_rod`/`ultra_rod`
  (only `poke_rod`). Exp candies and `rare_candy` exist and are **deliberately never sold**: the level cap is the
  campaign's pacing (`data/level_cap.json`).
- **Iron Chests, Tom's Storage, Cobblenav**: ids above; no shelf (a house, late logistics, no tiers).

## 3. What changed against PROGRESSION_LADDER revision 2, and why

| Ladder said | Built | Reason |
| --- | --- | --- |
| `comforts:sleeping_bag` | `comforts:sleeping_bag_brown` | the colourless id does not exist (§2.6) |
| `cobblecuisine:malasada` / `pokepuff` | `sweet_malasada` / `sweet_pokepuff` | the plain ids do not exist (§2.6) |
| TMCraft blank grades 1-5 at Brock, Surge, Sabrina, Blaine, Giovanni | the town's type-boost held item, plus released Mart lines | a blank is an ingot; without U-5 it gates nothing (§2.2) |
| Misty `advanced_filter_upgrade` 2,500 | not sold | Viltri Quay's leg is the smallest (7,548) and the shelf ran to 102% of it |
| Koga `advanced_magnet` 3,000, `smoking` 2,000 | Fenhide sells `magnet` 1,500; `smoking` moves to Cinderlee's furnace group | Fenhide with the bracelet ran to 98% of its leg |
| Sabrina stack tier 2 at 6,000 | not sold: crafted from the bought tier 1 | Tilpey Cross ran to 91% of its leg |
| Sunset West great/ultra balls | great balls at Highwire (badge 3), ultra at Tilpey Cross (badge 6); Sunset West keeps the scrolls and Pacifidlog sells the sea's balls | a port is not where a campaign's standard ball should first appear; the leader's town is |
| iron/gold/silver shulker boxes at Sunset West | not sold | §2.5 |

## 4. Independent audit checklist (for an agent that did not build it)

The builder's own audit (`python tools/markets.py audit`) shares the builder's data; these are the checks it cannot
make about itself. Offline items first, then the in-game ones, which are `MARKET_GATING.md` section 5's experiment.

Offline:

- **A-1 Ids.** Re-read every sold id from the jars yourself (not through `markets.py ids`): open each jar's
  `assets/<ns>/lang/en_us.json` and confirm the 62 ids in `data/markets.json`. Spot-check §2.6's three "does not
  exist" claims (`comforts:sleeping_bag`, `cobblecuisine:malasada`, `cobblemon:x_defense`).
- **A-2 The overlay.** Diff `modpack/config/sophisticatedcore-common.toml` against the base: exactly the 26
  `sophisticatedbackpacks:*` entries flipped to `|false`, nothing else. Confirm each flipped item is sold by a
  `sited` counter, and that no sited counter sells a Sophisticated Backpacks item that is still `|true` except
  `backpack` (declared in `left_craftable`).
- **A-3 The gate in the jar.** Confirm from the recipe JSON that every recipe producing a flipped item carries the
  `sophisticatedcore:item_enabled` condition on that item (including `iron_backpack_from_copper`,
  `advanced_magnet_upgrade_from_basic`, `smoking_upgrade_from_smelting_upgrade`,
  `stack_upgrade_tier_1_from_starter`), and that no OTHER recipe in any jar produces one of them.
- **A-4 The curve, independently.** Recompute badge by badge from `PROGRESSION_LADDER.md` §0.2's model-B table and
  the shelf prices, by hand or a fresh script, with the furnace group at its dearest and the crafting upgrade aside.
  Expected 0.69 / 0.67 / 0.70 / 0.65 / 0.68 / 0.67 / 0.65 / 0.69. Then the question the tool cannot ask: is the 0.70
  target still right now that the blackout is a flat $600 rather than the ~$1,500 the ladder budgeted (§0.4)?
- **A-5 Bank floors.** For every sold item in `bank.json`, unit price above the sell-back (super potion 400 > 175,
  max potion 900 > 625, full restore 1,500 > 750, max revive 2,500 > 1,000, vitamins 3,500 > 2,500).
- **A-6 Mutation.** Mutate `tools/markets.py` `buy_lines` (give before the charge, the price +1, the gate dropped,
  the verify dropped, the refund dropped, the cooldown last) and confirm `output_problems` names each; the builder
  ran these once in a scratch script and saw 50-53 problems for each, 0 unchanged. Make it a test.
- **A-7 Keepers' ground in a full checkout.** Run `python tools/markets.py audit --source-root <root>` WITHOUT
  `--skip-dressing` after `reapply.py prepare`; the builder's worktree lacked `derived/signposts.json`, so the
  town-dressing pieces were never checked against the eleven keeper cells.
- **A-8 The tests that the builder could not run.** `tests/test_npc_seats.py` needs prepare's output; add the
  keepers (`markets.npc_placements`) to its spacing sweep's source list beside the ferrymen.

In game (staging, under the lock; never the live world):

- **G-1** A keeper's menu shows the gated options only with the badge (`advancement grant/revoke ... only
  cobblers:flag/gym3_cleared`).
- **G-2** A purchase takes exactly the price; too little money takes nothing and says so.
- **G-3** The item arrives once; a full inventory drops it at the player's feet rather than refunding (vanilla
  `give`), which is acceptable but should be seen.
- **G-4** After the overlay is installed and the server restarted, the crafting table and REI show no recipe for
  `copper_backpack` or `crafting_upgrade`, and a bought one still works (opens, accepts upgrades).
- **G-5** Two players at one keeper at once (blocked on a second account, `docs/STATE.md`).
- **G-6** The refund branch: force a failing give (an invalid id in a throwaway build) and confirm the money returns.

## 5. The diamond backpack's price

Diamond backpack stays at **10,000** (revision 2), not revision 1's 20,000. The owner's brief of 2026-10-03 says
"the ladder reaches 20,000"; that figure is revision 1's, quoted in `data/blackout.json` `charge_rule_why`.
Revision 2 cut it after the 1.25 multiplier, as 0.55x of the badge-8 leg for +12 slots. It is one field in
`data/markets.json` if the owner wants 20,000 back.
