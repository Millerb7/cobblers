# Cobbleverse's merchants: what the "Apricorn Salesman" is, and how to give each stall its own shop

Research, 2026-10-04. Question (the owner, looking at the new town stalls): "the steve villagers aren't it, it
should be the cobbleverse ones that have nice ui". The screenshot: a villager-model merchant, red cap, named
"Apricorn Salesman"; right-click opens a shop with an item preview, quantity, Buy, "Categories..." (Seeds),
"Offers..." priced 2.5K, and a Bank balance.

Versions: Minecraft 1.21.1, Cobblemon 1.8.0, **CobbleDollars 2.0.0+Beta-5.1** (the Cobbleverse 1.7.42 jar,
`modpack/manifest/base-cobbleverse-1.7.42.json:230-249`; our overlay does not replace it,
`modpack/manifest/overlay.json:662-665`), Cobbleverse datapack `COBBLEVERSE-DP-v31.zip` (namespace `bca`).
Labels per `.claude/rules/research.md`.

## 1. What the entity is

**VERIFIED.** It is a CobbleDollars merchant, `cobbledollars:cobble_merchant`, placed by a Cobbleverse (BCA)
shopkeeper structure template, and **we already summon it**. `tools/traders.py` reads the entity out of the
template (`entity_of`, `tools/traders.py:130-141`), drops only engine-owned fields (`:124-127`), and writes it into
a `summon`. The generated line for Stoneford's `gym1_vendor_01`
(`bca:stores/farmers_market/shopkeeper_apricorn_seeds`, `data/traders.json:20-37`), from a build of the current
generator (`.claude/worktrees/agent-a12d72c5164718e01/build/datapacks/cobblers_vendors/data/cobblers/function/towns/vendors_gym1_town_place.mcfunction:10`),
abridged to the load-bearing fields:

```
summon cobbledollars:cobble_merchant 1741.5 139 3603.5 {Invulnerable:1, PersistenceRequired:1b, Silent:1,
  CustomName:"\"Apricorn Salesman\"",
  CobbleMerchantShop:[{Category:"Seeds",Offers:[{Item:{count:1,id:"cobblemon:black_apricorn_seed"},Price:"2500"}, ... 7 seeds, all "2500"]}],
  VillagerData:{profession:"cobbledollars:cobble_merchant",level:99,type:"minecraft:plains"},
  Tags:[...], NoAI:1b}
```

- Entity id, name, category, price: all from the template's own NBT, not from config. "Seeds" and 2.5K in the
  owner's screenshot are this NBT (2500), and are **not** `defaultShop`, whose categories are Cobble Ball, Potions,
  Mob Drops, Cards (`docs/research/PROGRESSION_UNLOCKABLES.md:220-227`). **VERIFIED** for the NBT; that the
  screenshot shows this entity is an inference from the matching name, category and price.
- Where Cobbleverse defines them: structure templates `data/bca/structure/stores/**` in `COBBLEVERSE-DP-v31.zip`
  (`data/traders.json:24-28`); known ones are `farmers_market/{apricorn_seeds, herbalist, small_game, common_fish,
  exotic_fish, chef}` and `store_workers/{ds_general, ds_mulch, ds_special_balls, ds_battle_items}`
  (`docs/world-building/TOWN_SQUARES_SURVEY.md:424-429`). The full list is not in the repo. Other names read the
  same way: "Herb Salesman", "Gardening Specialist", "Small Game Salesman" (same file, lines 14, 18, 22).
- CobbleMerchants also spawn naturally in overworld villages (~8%), and a vanilla villager takes the profession from
  a Display Case (https://modrinth.com/mod/cobbledollars, VERIFIED as the mod's description, unversioned; the
  profession in 1.5.0's changelog, and Beta-5.1 "the shop of Vanilla Villagers with the CobbleMerchant profession
  now works correctly", https://api.modrinth.com/v2/project/cobbledollars/version).
- **ASSUMED:** the red-capped villager look is the mod's own merchant texture. The template carries no texture or
  skin field (above), only `VillagerData.type: plains`. Not read in the jar's assets.

**So the stall keepers look like Steve because they are a different system.** `data/markets.json` stalls are
Cobblemon 1.8 dialogue NPCs (`data/markets.json:6-15`, `tools/markets.py:26-42`), chosen because they can gate
stock per player (`docs/mechanics/MARKET_GATING.md:15-45`). Stoneford's square ALSO has five BCA merchants from
`data/traders.json` standing in a row at z=3603 (`gym1_vendor_01/03/04/05` plus the Mart clerk at 1793,139,3611),
not at the stalls: the stall plan names `gym1_vendor_01` as the intended seed seller
(`data/plaza_centres.json:627-641`, "why": "apricorn seeds (gym1_vendor_01)") but `data/traders.json:29-33` still
places it at (1741,139,3603), while the stall's `keeper_at` is (1737,139,3616, yaw -90).

## 2. How offers are defined, and per-merchant shops

**VERIFIED:**

- **Per entity**: the shop is the NBT list `CobbleMerchantShop: [{Category:"<name>", Offers:[{Item:{count, id},
  Price:"<n>"}]}]`, price as a string (the line above). Each merchant carries its own list. Changelog Beta-5:
  "an option to set a limited stock on **custom merchant offers** (currently only in the `/cm edit [merchant uuid]`
  UI)"; Beta-3: "a GUI accessed via `/cobblemerchant edit [cobble merchant UUID]` to edit the shop of a Cobble
  Merchant" (https://api.modrinth.com/v2/project/cobbledollars/version).
- **Global**: `config/cobbledollars/default_shop.json` (`defaultShop`: categories of `{item, price}`) and
  `bank.json` (sell-back prices), flat and server-wide, no merchant key
  (`base-pack/cobbleverse/config/cobbledollars/`; `docs/mechanics/MARKET_GATING.md:251-255`).
- A filtered and an authored shop already ship: Mart clerks get a filtered list, the Exchange a from-scratch one
  (`tools/traders.py:176-233`), and in a running game on 2026-10-01 a clerk's `CobbleMerchantShop` read back as
  exactly three categories (`docs/STATE.md:87, 210`; read with `data get`, not through the GUI).
- A plain `cobble_merchant` summoned with no shop has `CobbleMerchantShop: []` (`docs/STATE.md:210`).
- **No per-player stock**: one list per entity, the same for every player (`docs/mechanics/MARKET_GATING.md:19-23`).
  Payment is per player (each pays from their own balance).

**So yes: each stall can have its own list (fish at one, seeds at another) by `summon` NBT, from a datapack
function, with no config and no client change.** The fields are the template's own shape (§1). That an
**authored** list, items no template carries, appears in the GUI and sells is **P-7, not run**
(`docs/mechanics/STONE_ECONOMY.md:458-460, 659`). ASSUMED to work, because the shape is the template's.

**CobbleDollars 2.0.0+Beta-6 (not installed)** adds datapack-defined shops and banks, assigned per merchant with
`/cm edit <merchant_uuid> set shop <shop_id>`, `/cm open shop <shop_id>`, an Omnitool, and a **new serialization
format for "merchant shops stored on entities"**, migrated automatically
(https://api.modrinth.com/v2/project/cobbledollars/version, version `yWsg35wD`). VERIFIED as changelog text. On
upgrade our `CobbleMerchantShop` NBT shape would have to be re-read. Not needed for per-stall shops.

## 3. Placing one

`summon cobbledollars:cobble_merchant x y z {CustomName:"\"<Name>\"", NoAI:1b, PersistenceRequired:1b,
Invulnerable:1, Silent:1, Rotation:[<yaw>f,0f], Tags:[...], VillagerData:{profession:"cobbledollars:cobble_merchant",
level:99,type:"minecraft:plains"}, CobbleMerchantShop:[...]}`. This is the generator's shape, VERIFIED as what
we emit (§1). `traders.py` already handles the placement:

- staying put: `NoAI`, because with AI they walked 2-40 blocks off their stalls (`tools/traders.py:290-292`);
- facing: `Rotation` (`:298-300`);
- re-runs: force-load, wait, de-duplicate (`:18-28`);
- re-export: the R14 re-apply (`data/traders.json:4`).

- **Vanilla trade UI:** right-click opens the CobbleDollars shop, **shift + right-click opens the Bank**
  (https://modrinth.com/mod/cobbledollars). VERIFIED as the mod's description, and the owner's screenshot shows the
  shop. Consequence: **every stall merchant is also a sell-back point** for the whole global `bank.json`. The 14 Mart
  clerks already expose that bank, so this adds places, not a capability. ASSUMED: blocking it needs the permission
  `cobbledollars.cobblemerchant.open.bank` and a permissions mod; we have not checked for one.
- **Restocking:** a merchant has no vanilla `Offers`, so no vanilla restock. Limited stock is opt-in and set in the
  edit UI (Beta-5 changelog), and the templates carry no stock field. ASSUMED: offers are unlimited.
- **Does a NoAI merchant trade at all?** Not tested (`docs/STATE.md:87`). If the owner's screenshot came from
  staging's Stoneford square, it answers yes. **Ask the owner where it was taken.**

## 4. Cost

- No restart, no config file and no client change: CobbleDollars is already on server and clients.
- A summon line in a datapack function, then `/reload`.
- Generator work (an architecture call, not made here):
  - an authored shop per trader in `data/traders.json`: `traders.py` already authors one, for `stock: "stones"`;
  - `position` moved onto each stall's `keeper_at`;
  - one keeper per stall, chosen between the two systems.
- **The trade-off is the design's, not the mod's:** a CobbleMerchant cannot hide a badge-gated item from one player.
  The pretty UI is for ungated stalls only, unless a Beta-6 `/cm open shop <id>`, run from a dialogue option, can
  open a per-badge shop for one player. Unknown; see the backlog.

## 5. The smallest proof (staging, under the coordination lock, the owner at Stoneford's seed stall)

1. `summon cobbledollars:cobble_merchant 1737.5 139 3616.5 {CustomName:"\"Fishmonger Probe\"",NoAI:1b,PersistenceRequired:1b,Invulnerable:1,Silent:1,Rotation:[-90f,0f],Tags:["cobblers_p7"],VillagerData:{profession:"cobbledollars:cobble_merchant",level:99,type:"minecraft:plains"},CobbleMerchantShop:[{Category:"Fish",Offers:[{Item:{count:1,id:"minecraft:cod"},Price:"150"},{Item:{count:1,id:"minecraft:salmon"},Price:"200"}]}]}`.
   This is `keeper_at` of `gym1_town_stall_2`. The dialogue keeper may stand on the same block: click the one
   named "Fishmonger Probe".
2. `data get entity @e[tag=cobblers_p7,limit=1] CobbleMerchantShop`: the two offers echo back.
3. `cobbledollars query <player>`: record B0.
4. Owner: right-click. The screen must show category "Fish" with Cod 150 and Salmon 200, and nothing from
   `defaultShop`. Buy one Cod. Shift-right-click to note whether the Bank opens.
5. `cobbledollars query <player>` must read B0-150, and `clear <player> minecraft:cod 0` must count 1.
6. `data get entity @e[tag=cobblers_p7,limit=1] Pos` still reads (1737.5, 139, 3616.5). Then
   `kill @e[tag=cobblers_p7]`.

**Pass** closes P-7 (an authored per-merchant shop sells) and STATE's "a NoAI trader trades". Optional 7th step, a
second probe with `CobbleMerchantShop:[]`, answers C2/U-7 (does an empty shop fall back to `defaultShop`).

## Unknown

- The full BCA shopkeeper list.
- The merchant texture.
- Whether `Price` takes counts above one, or `Item.count > 1`, as a bundle.
- Whether Beta-6 `/cm open shop` can be run for one player from a function.
- Whether a permissions mod exists to deny the bank.

All are in `docs/research/EXPERIMENT_BACKLOG.md`.
