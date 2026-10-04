# Town squares and traders: a survey of every settlement's middle and where a player spends money

**Status: survey, 2026-10-03, read from the repository's data and generators at `daa6390`. Nothing here is
built, and no world was read.** It answers the owner's brief of the same day:

> "TOWN SQUARES AND TRADERS. Finish them properly. Market squares, stalls, the civic centre of each town.
> Several still read as streets with buildings rather than places with a middle. More traders, and new
> ones. The backpack ladder landed last night -- build out the rest of the stock the same way, per town,
> reading as the place. Every town should have somewhere a player goes to spend money."

The main question is whether each town has a middle: a place a player would recognise, not a paved
rectangle.

## 0. The answer

- **Two of the fourteen towns with a Mart have a real middle: Fossick (the Mining Town) and Northlight.**
  Fossick's pithead yard has a headframe in the middle, ore piles in its corners, two working Pokemon and
  the Assayer. Northlight's square has its bonfire and weather instruments on its edge, the keeper on the
  paving, and the Centre and Mart facing it from three blocks away. Steepside comes close: its tea house
  fronts the square, but the paving itself is empty.
- **Three gym towns have no middle at all: Fenhide, Cinderlee and Highwire.** Each has a plaza, but every
  service that matters stands 22 to 66 blocks away from it, and so does the market keeper. Pallet has no
  plaza either; its centre is the Pallet sign at the crossroads.
- **Seven towns have a bare middle**: services that face a paved rectangle with nothing built on it.
  These are Stoneford, Viltri Quay, Tilpey Cross, Greenhollow, Holdfast, Sunset West and Pacifidlog.
  Stoneford and Viltri Quay have traders on the paving, but they stand in a row with no stalls.
- **No tool can put anything on a plaza.**
  - `tools/place_town.py:479-490` paves the plaza as a single street segment.
  - `tools/town_plan.py:208-210` sets flush lamps on a 27-block grid.
  - `tools/town_dressing.py:195-197` marks the plaza and its verge as keep-clear, so no dressing piece can
    land on it.
  - The generator that would build squares, `tools/plaza_centre.py` with re-apply step R13, was proposed in
    `TOWN_CENTERS.md` on 2026-09-25 and never written. `docs/STATE.md:235` still reads "the plazas are bare
    paved rectangles ... nothing built".
- **Places where a player can spend nothing beyond the Mart clerk's three items** (Poke Ball, Potion,
  Antidote; `data/traders.json` `stock_policy.mart`):
  - Sunset West, Pacifidlog and Pallet. Their market counters are `unsited`, so `tools/markets.py:98-99`
    never emits them. Pallet's clerk also sells the trainer card.
  - Redbrow: it has a counter but no clerk to stand it beside, and `markets.py:306-308` refuses that.
  - The Deep's city: it has a Mart building and a built row of stalls, but no clerk and no trader record.
    Its counter row is absent from `data/towns.json`, so the markets audit never asks about it.

## 1. How this was measured

The measurements come from scratch scripts that read only `data/*.json`, plus `tools/ground.py` (the
heightmap, rounded). For every settlement they record:

- the plan's `plaza` rect, `y` and surface;
- every anchor's gap to the plaza (Chebyshev, block edge to block edge), and whether its `facing` points at
  the plaza centre (cosine above 0.5 counts as "toward");
- every `data/traders.json` trader, every `data/markets.json` keeper `at`, every `data/town_dressing.json`
  piece, every `data/ambient.json` worker and every `data/npc_seats.json` seat within 4 to 6 blocks of the
  rect;
- every earthwork `fill`/`setblock` in `data/placements.json` whose box touches the rect.

The price curve comes from `python tools/markets.py report`.

**Not measured:**
- `derived/` is absent from this worktree, so I could not read lamp cells, street cells or template
  footprints.
- I did not check the proposed sites outside an existing plaza (Pallet only) against building footprints.
  Run `tools/town_dressing.py show_map` in a full checkout first.
- I did not read any item id proposed in section 4 from a jar unless `docs/mechanics/TIERED_GOODS.md`
  already verifies it. Every other id is marked ASSUMED; `python tools/markets.py ids --jar-dir
  <server>/mods` checks them.

**On "25 places":** `data/placements.json` `settlements` holds 27 records. `jungle_ruins` is retired, and
`route1_mansion` and `route1_old_mine` are not towns (`no_services`). That leaves 24 towns. The brief also
names the Deep's city and the station towns, so `data/deep_city.json` (the Windward Deep's city) and
`data/research_station.json` are surveyed as well. Neither is in `settlements` or in `data/towns.json`.

## 2. Town by town

Terms used in the tables:

- **Gap**: the distance from an anchor's rect to the plaza rect. 0 means it touches.
- **Faces**: whether the anchor's `facing` points at the plaza.
- **Spend**: everything a player can buy in the town.
- **Clerk**: a Mart shopkeeper, `data/traders.json` stock `mart`. It sells only Poke Ball, Potion and
  Antidote.
- **Keeper**: a `data/markets.json` gated counter.

Every keeper's purchase is **not run in game** (`data/markets.json` `status`). R17M placed the sited keepers
in staging overnight on 2026-10-03 (`docs/STATE.md:22`).

### Pallet (hometown): no plaza; Mart and counter

| | |
|---|---|
| Character | Pallet as it was in Kanto, whole, set down on ground that is not Kanto. The owner wants it kept intact (no ambient Pokemon by the owner's call, `STATE.md:233`). |
| Middle | No plan and no plaza. The centre is the CobbleTowns Pallet sign (`hometown_sign`, kind `town_centre`, 13x13, `verified`) at the main and cross streets' crossroads (1461, 5292). The waystone stands at (1467, 5286), unactivated. |
| On it | The sign; Mina's seat (`npc_main_pallet_mina`). |
| Services | Centre (1432, 5238) and Mart (1467, 5239), both rotated 180, about 50 blocks north of the crossroads. Oak's Lab is on its own lane. |
| Spend | Mart clerk, plus the trainer card at $500 (`stock_policy.trainer_card`). The Packmaker counter (leather backpack $300, sleeping bag $250) is **unsited, so it is not sold**: "no plan anchors" (`markets.json:69`). The tier-1 backpack can still be crafted. The bedroll is sold nowhere until this counter is sited; Northlight sells the hammock. |
| Verdict | **No middle, by the owner's intact rule.** It needs only a seat for the Packmaker. |

### Stoneford (gym1_town): bare square, traders standing on it

| | |
|---|---|
| Character | The plateau's builders' town: masons who build in its stone, and the coordinator who runs the rescue when the ground moves. |
| Plaza | 41x41 at (1736, 3600)-(1776, 3640), y138, stone_bricks. The heightmap reads 138-139, with 30 of 1,681 cells one block off the plan. Large class. |
| On it | Paving, flush lamps and the waystone (1756, 3606). Six trader NPCs stand in a row at z3603, (1741-1766): four regional (apricorn seeds, herbalist, mulch, small game) and two withdrawn. There are **no stalls under them**: a trader is an entity summoned from a BCA template, `data/traders.json` `fields.template`. The Yard Steward keeper is at (1776, 139, 3608), on the east edge. |
| Off it | All of the dressing is 26-74 blocks away: the derrick crane 32, the coordinator's stall 30, the kiln 36. |
| Services | Centre gap 4, faces it. Mart gap 2, faces it. Gym gap 30, faces it. |
| Spend | Clerk, four regional vendors, and the keeper ($13,500 of stock, one of each line: copper backpack, stonecutter, anvil and crafting upgrades, Hard Stone). **More traders stand on this square than on any other.** |
| Verdict | **Bare.** It has the most trade and the least place. The trader row is still in the north avenue's mouth: vendor_04 at (1756, 3603) stands three blocks in front of the waystone. `TOWN_CENTERS.md` reported this finding on 2026-09-25, and it is unchanged. |

### Viltri Quay (gym2_town): bare square, traders standing on it

| | |
|---|---|
| Character | The lake town that takes in whoever the water brings: rescue boats, and a record of every arrival. |
| Plaza | 33x33 at (1604, 2796)-(1636, 2828), y107, prismarine_bricks. The heightmap reads 107-108, with 1,003 of 1,089 cells at 108 (fill). Medium class. |
| On it | Paving, lamps, the waystone, and five vendor NPCs standing at z2799: three regional (common fish, exotic fish, chef) and two withdrawn. The relief clerk's seat is 3 off the edge. No stalls and no centrepiece. |
| Services | Centre gap 4, faces it. Mart gap 7, side-on. Gym gap 30 on the waterfront, faces it. The keeper (Rescue Quartermaster) is at (1624, 108, 2772), **24 blocks off the square**. |
| Spend | Clerk, three regional vendors, and the keeper ($4,900: filter and tank upgrades, Super Potions, Mystic Water). |
| Verdict | **Bare.** No ambient Pokemon works here (`STATE.md:233`) and nothing is dressed. |

### Highwire (gym3_town): a viewpoint, no middle

| | |
|---|---|
| Character | The signal town under Mt Vessu, whose people keep the power, the relays and the storm gear running. |
| Plaza | The belvedere, 33x15 at (1660, 1386)-(1692, 1400), y174, exposed_copper. The heightmap is flat at 174 (0 cells off). Small class. |
| On it | Paving, the waystone, and Surge's Magnemite at the plaza lamp (`ambient` `surge_magnemite_lamp`). No dressing: Highwire is not one of the six dressed towns. |
| Services | Centre gap 2, faces it. **Mart gap 42.** Gym gap 30. The keeper (Relay Storekeeper) is at (1678, 175, 1437), 37 off. |
| Spend | Clerk and keeper ($8,550: iron backpack, battery upgrade, Magnet, Great Balls). The keeper stands by the Mart, not on the belvedere. |
| Verdict | **No middle.** The belvedere is a view. Trade happens 40 blocks down the walk, beside a Mart that faces the street. |

### Greenhollow (gym4_town): the green, bare

| | |
|---|---|
| Character | Peak Pond Hollow's garden town, where Erika keeps the peace between the residents and the arrivals. |
| Plaza | The green, 53x61 at (4284, 1526)-(4336, 1586), y110, moss_block. The heightmap reads 110-112. Large class. |
| On it | Moss. Erika's Bulbasaur waters and her Bellossom tends (`ambient`), and the survey archivist's seat is on it. The waystone is 8 off, at the west corner. The flowers the plan's `why` promises ("the flowers that will go in it") are **not placed**: no earthwork or dressing touches the rect. |
| Services | **Every one faces it**: Centre, Mart and gym, each at gap 14 across the ring street. The keeper (Green Grocer) is 12 off. |
| Spend | Clerk and keeper ($9,800: feeding upgrades, sweets, Miracle Seed, Full Heal). |
| Verdict | **Bare, but with the best bones in the region.** The whole town is already arranged round its middle. What it lacks is the garden itself. |

### Fenhide (gym5_town): a yard nobody faces

| | |
|---|---|
| Character | A fen-edge watch town where trackers read the marsh and the glacier foot for anyone passing unseen. |
| Plaza | The "market yard", 33x25 at (4652, 2420)-(4684, 2444), y117, mossy_cobblestone. The heightmap reads 117-118. Medium class. |
| On it | Paving, lamps and the waystone. At its edge stand the trackers' board (6 off), market crates (6 off) and a market stall (14 off), all `town_dressing` pieces. **The stall has no trader.** |
| Services | **Centre gap 36, facing away.** Mart gap 22. Gym gap 46 across the fen. The keeper (Tracker's Outfitter) is at (4697, 119, 2491), **47 off**. |
| Spend | Clerk and keeper ($11,500: pickup and magnet upgrades, the Mega Bracelet, Poison Barb), both well away from the yard. |
| Verdict | **No middle.** The plan names this yard "the market yard", yet no market and no service is on it or faces it. |

### Tilpey Cross (gym6_town): the region's square, its market never built

| | |
|---|---|
| Character | The region's place of study: Sabrina's people record what the Rift does to memory, perception and Pokemon. The plan calls this square "the only true square in the region". |
| Plaza | 33x33 at (6180, 3382)-(6212, 3414), y94, polished_diorite. The heightmap is flat at 94. Medium class. |
| On it | Paving, lamps, the waystone, and the pattern NPC's seat. Every dressing piece is 64-90 off: the listening spire 82, the stalls and reading stalls 78-90. |
| Next to it | `gym6_market` (37x47, levelled, smooth_stone, gap 4): "the region's market. Its stalls are the traders, placed once the badge-gated stock lands; until then it is a square." Also `gym6_commons` (37x47, gap 4): "lawn, trees and a fountain (Cozy Home fountain blocks)". **Neither has anything placed**; there is no placement or earthwork for the fountain. |
| Services | Centre and Mart gap 4, side-on along the cross street. Gym gap 48 at the head of the axis. The keeper (Archive Stores) is 12 off. |
| Spend | Clerk and keeper ($13,500: smithing and stack upgrades, Twisted Spoon, Ultra Balls). The badge-gated stock the market block was waiting for has now landed, as one keeper. |
| Verdict | **Bare.** The plan already reserves a market square and a park beside the square, and both are empty. |

### Cinderlee (gym7_town): an ash square with nothing at it

| | |
|---|---|
| Character | A research town on the crater rim that studies the cone's energy and keeps the mound between itself and the fire. |
| Plaza | The ash square, 29x29 at (6060, 4981)-(6088, 5009), y107, polished_basalt. The heightmap reads 107-108. Medium class. |
| On it | Paving, lamps, the waystone, and the crater analyst's seat. Dressing sits close to the edge: rim instruments 7 and 10 off, square crates 12 off, fumaroles 17-46, the core rack 18. |
| Services | **Centre gap 41, Mart gap 35, gym gap 66.** All face toward it, from far away. The keeper (Rim Ironmonger) is 27 off. |
| Spend | Clerk and keeper ($23,500: gold backpack, the furnace upgrades, Charcoal Stick, Max Potions). |
| Verdict | **No middle.** It is a crossing with props at its rim. |

### Holdfast (gym8_town): a gate square, dressed round its edge only

| | |
|---|---|
| Character | The southern garrison: Giovanni defends the settlements behind him and holds the last gate before Victory Road. |
| Plaza | The gate square, 31x23 at (3590, 6440)-(3620, 6462), y112, terracotta. The heightmap reads 111-113. Medium class. |
| On it | Paving, lamps and the waystone. Round it: sandbags 10 off, the quartermaster's stall 10 off **with no trader**, the south depot 11, gate colours 14, the palisade 20. |
| Services | Mart gap 6, faces it. Gym gap 8, faces it. **Centre gap 56.** The keeper (Garrison Quartermaster) is 14 off. |
| Spend | Clerk and keeper ($28,500: diamond backpack, inception upgrade, gold bottle cap, Max Revive, Full Restore). These are the last stores before Victory Road (`markets.json` `no_counter.rift_rim_stop`). |
| Verdict | **Bare.** It reads as a gate, but the quartermaster's stall stands empty ten blocks away while the quartermaster keeper stands fourteen blocks away. |

### Sunset West: chandlers' square, bare, nothing to buy

| | |
|---|---|
| Character | The region's harbour: fishers and boatwrights, and the charter boats to the outer sea. |
| Plaza | 25x29 at (2642, 6480)-(2666, 6508), y64, polished_granite. The heightmap reads 64-67, with 350 of 725 cells off. Medium class. |
| On it | Paving, lamps and the waystone. No dressing, no ambient Pokemon, no seat. |
| Services | Centre gap 2, faces it. Mart gap 3, faces it. Ferries leave from `sunset_quay` and `sunset_south_pier` (`data/ferries.json`; the strait costs $100). |
| Spend | Clerk and ferry fares. The Harbour Scrivener (blank, return, warp and bound scrolls, $7,700) is **unsited**: its plan needs `build/paint/manifest.json`, which the earlier agent did not have (`markets.json` `unsited_why`). |
| Verdict | **Bare**, and it is the region's port with nothing on its quay to buy. |

### Pacifidlog (sea_town): a raft square

| | |
|---|---|
| Character | A fishing town floating on the sea: rafts, a fishers' row, a boatwright and the stilt quarter. |
| Plaza | The square raft, 17x17 at (5152, 7372)-(5168, 7388), y62 sea deck, jungle_planks. Small class. |
| On it | The waystone, plus jungle fence and lanterns round the raft's edge (`sea_town_old_rafts`). Its bell was left out, because a bell decides spawns (Chimecho); that call is the owner's. |
| Services | Centre gap 12 and Mart gap 9, each across a bridge, each facing it. |
| Spend | Clerk and a ferry fare ($150). The Deck Chandler (Dive, Net and Lure Balls, $9,000) is **unsited**: it can be sited only on a deck cell from `tools/sea_town.py`'s plan. `STATE.md:286`: "Not built: its NPCs (rod master, fishing trader, boatwright)". |
| Verdict | **Bare, small.** The town square is the raft, and the raft holds nothing. |

### Steepside (tea_town): framed by the tea house, thin stock

| | |
|---|---|
| Character | A town built on one industry: tea terraces over Shrew Lake, a tea house, and Poltchageist. |
| Plaza | The tea square, 29x27 at (2604, 3570)-(2632, 3596), y114, mossy_stone_bricks. The heightmap reads 114-115. Medium class. |
| On it | Paving, the Tea House Kitchen keeper at (2604, 115, 3596), and the picker's seat. The tea house (BCA `blossom_balcony`) is gap 4 and faces it. |
| Services | Centre and Mart gap 8 across the road, facing it. |
| Spend | Clerk and keeper, **$1,100 in all**: a sweet malasada and a sweet pokepuff. This is the thinnest shelf in the region. |
| Verdict | **Partial.** The tea house gives the square a focus, but the paving between is empty and the shelf has two lines. |

### Fossick (mining_town): a real middle

| | |
|---|---|
| Character | Ore and minerals on the eastern cone: the mine head, the ore rail, a smelter and a fossil lab. |
| Plaza | The pithead yard, 41x24 at (6600, 5688)-(6640, 5711), y137, cobblestone. The heightmap reads 136-138. Medium class. |
| On it | The **headframe over a capped shaft in the middle** (`tools/mining_works.py:37`, `:145-167`), **ore piles in each corner** (coal, iron, copper, spoil; `:38-48`, `:169-`), the ore track, the Machop and Roggenrola at the piles (`ambient`), the foreman's seat, and **the Assayer on the yard** (all ten stones at $2,100, never buying). |
| Services | Centre and Mart gap 6, side-on along the ore road. The keeper (Mine Stores) is 13 off. |
| Spend | Clerk, the Exchange (Assayer), and the keeper ($9,200: compacting and void upgrades). |
| Verdict | **Yes.** This is the model the others should copy. One known complaint is open: its stone faces read as unconnected to the town (`STATE.md:328`). A sample plinth on this yard is one of the owner's stated answers. |

### Northlight: a real middle (its fire at the edge)

| | |
|---|---|
| Character | The cold-water research town: the region's weather and aurora observatory, and an ice-type field station. |
| Plaza | 41x31 at (7245, 1540)-(7285, 1570), y116, polished_deepslate. The heightmap reads 115-117. Medium class. |
| On it | The waystone, the Station Supply keeper at (7277, 117, 1540), the field hand's seat, and weather instruments 2-3 blocks off the edge. **The bonfire landmark is 7 off the south edge**, and the Timburr carries logs to it from the woodpile. |
| Services | Centre and Mart gap 3, both facing it. |
| Spend | Clerk and keeper ($21,800: hammock, six vitamins at $3,500 each). |
| Verdict | **Yes.** This is the only dressed town whose landmark was put at its square. |

### Redbrow (tableland_stop): a rest-stop yard with a counter and no clerk

| | |
|---|---|
| Character | A waystation and a prospector's house on the badlands rim, whose lookout is seen from the road below. |
| Plaza | The yard, 27x21 at (4830, 5680)-(4856, 5700), y161, red_terracotta. The heightmap is flat at 161. |
| Services | Centre (waystation) gap 2, faces it. The prospector's house is across the yard. No Mart. |
| Spend | **Nothing.** The Prospector counter (Soft Sand, Heavy Ball, $4,000) is unsited: it has no clerk to stand beside (`markets.py:306-308`), and open question Q-4 asks whether the stop gets a counter at all. |
| Verdict | **Bare**, and a small one is right for a rest stop. The prospector's house fronting the yard is the obvious seat. |

### Bridgekeep (gorge_hamlet): the promised well is still missing

| | |
|---|---|
| Character | The bridge-keepers' walled yard above the Tilpey gorge, whose keeper knows the river. |
| Plaza | The yard inside the wall ring, 31x29 at (6798, 4353)-(6828, 4381), y113, cut_sandstone. Flat. |
| On it | The elder's seat and the waystone. The plan says "a well at its centre", but **no placement builds one**. `gorge_courtyard_wall` writes only the ring wall. `TOWN_CENTERS.md` recorded this finding and it still stands. |
| Spend | None, by decision (`no_counter`: "rope, not stock" if the owner wants one). |
| Verdict | **Bare.** A well is all it needs. |

### Places with no middle and no shop by design

These need no square and no shop, and I propose none.

| Place | What its middle is | Spend |
|---|---|---|
| The League | No plaza. The arrival is two polished-tuff forecourts either side of the ramp (y88; the heightmap under the west forecourt reads 86-88). The torch walk `TOWN_CENTERS.md` proposed is not built. | "The League sells nothing" (`no_counter`). The Centre and Mart are inside the Cobbleverse template; whether that template carries a shopkeeper is **not verified**. |
| The Displaced City | **Yes**: a 16x16 summit square at y46 with the summit cairn (`displaced_cairn`) in its middle and lanterns on posts. The mason's seat is on it. | None, by decision ("a market would decide a story question"). |
| Merian Hut | A cobbled apron 69x7 along the hut row. | None (a bed at the end of a walk). |
| Rimwatch (rift_rim_stop) | A boardwalk 27x9 from the Centre to the overlook: "There is no square". The Growlithe watches. | None (the rangers' post). |
| West Spur Dig | A gravel middle (17x27) by the finds shed. | None. |
| The Scar | **Yes, as a ruin**: the old square 33x33 at y280 with an empty cairn plinth (`scar_cairn_plinth`) whose cairn now stands in the Displaced City. | None (dark and unkept). |
| Relic Island, Viltri Light | One house; a lighthouse apron. | None. |
| The Deep's city (`data/deep_city.json`) | **A middle exists**: the Core's paved floor (polished deepslate with a basalt grid) round Heaven's Arena drum. Rimside, the arrival ring, has a front row of **stalls** built as blocks (`tools/deep_city.py:1386`, `:2016`: copper posts, canopy, counter, lamp) and a Centre and Mart from the league templates. | **Nothing.** `not_built` lists "NPCs, the Mart clerk and the Compact's people". The city has no `data/towns.json` record, so `tools/markets.py:273-279` never asks it for a counter or a reason (CLAUDE.md "Our list is not the world"). |
| Research station (`data/research_station.json`) | A paved plaza 61x39 (524-584, 2792-2830) between the Institute, the Archive, the bunkhouse and the wet lab; the weather mast. | None, and none was asked for. |

## 3. Ranked by need

The rank weighs whether the town has a middle (the main question), then whether its trade is away from its
middle, then how many players pass through (critical path first).

| # | Town | Middle | Why it ranks here |
|---|---|---|---|
| 1 | Fenhide | none | The plan calls it the "market yard", yet the Centre faces away from it at 36 blocks, the keeper is 47 away and the dressing's market stall is empty. Critical path. |
| 2 | Cinderlee | none | The Centre is 41 away, the Mart 35 and the gym 66. Nothing ties the town to its square. |
| 3 | Highwire | none | A viewpoint. The Mart and keeper are 40 down the walk. It is small, so it needs a small square. |
| 4 | Stoneford | bare | The first gym square, the largest and the most visited. Six NPCs stand in a row on bare paving, in the avenue mouth. `TOWN_CENTERS.md`'s chosen prototype. |
| 5 | Holdfast | bare | An empty quartermaster's stall and a quartermaster keeper 14 apart. The last stores before Victory Road. |
| 6 | Viltri Quay | bare | Traders but no stalls. The keeper is 24 off. No life in the town (no ambient Pokemon). |
| 7 | Tilpey Cross | bare | The plan reserves a 37x47 market and a park beside the square; both are empty. |
| 8 | Sunset West | bare | The port square is empty and its counter is unsited, so the scrolls go unsold. |
| 9 | Pacifidlog | bare | A raft with a waystone. The counter is unsited; the town's own NPCs are not built (`STATE.md:286`). |
| 10 | Greenhollow | bare | Every service already faces the green, and the garden only has to be planted. |
| 11 | Steepside | partial | The square has a focus, but the shelf is thin ($1,100). |
| 12 | Redbrow | bare | A rest stop. It needs a clerk before its counter can stand (Q-4). |
| 13 | Pallet | sign | The owner wants it intact. It needs only the Packmaker's seat. |
| 14 | Bridgekeep | bare | The promised well. |
| 15 | The Deep's city | yes (no trade) | The stalls are built and empty, and the Mart has no clerk. This is story-gated (the Compact). |
| 16 | Northlight | yes | Benches would finish it. |
| 17 | Fossick | yes | Done; the model. |

## 4. The squares to build

Each proposal sites the square on the plan's own plaza rect, because the rect is already graded, paved,
lit, and faced by the town's doors. Only Pallet has no rect. Ground is the plan `y`, checked against the
heightmap in section 2.

The size class and the elements are `TOWN_CENTERS.md` sections 1-2: the waystone pad (W), notice board
(N), centrepiece (C), emblem plinth (E), stalls (t), benches (b), tree pits (Y), and the 15% coverage cap.
The stall piece already exists as generated blocks in `tools/town_dressing.py:315-336` (`piece_stall`:
counter, goods, four posts, awning); only the plaza mask (`:195-197`) keeps it off the square.

**Stall count rule.** A small square gets 2 stalls, a medium 4, a large 6. One stall always holds the
town's existing `markets.json` keeper, moved from beside the Mart onto the square.

### Stock: the shared rules

Section 5 explains why these rules apply.

- Any **new critical-path item** must be `"stretch": true` or move money elsewhere, because the critical
  path is already at the 0.65-0.70 target.
- New **produce** stalls use the `data/traders.json` regional pattern instead. Ungated produce is not on
  the curve.
- Ids marked (A) are ASSUMED and not read from a jar here. Every other id is verified in
  `TIERED_GOODS.md` section 2.

### The proposals, town by town

| Town | Site (rect, y) | Class | Centrepiece | Stalls | Stock to add |
|---|---|---|---|---|---|
| **Fenhide** | (4652, 2420)-(4684, 2444), y117 | medium | The **dry well**: a roofed mud-brick well with a mangrove roof. Three stone lanterns on the west edge line up on the boardwalk's start, as a hint toward the gym (`TOWN_CENTERS.md`). Move `koga_market_stall` and the market crates onto the yard's east band. | 4 | Move the Tracker's Outfitter keeper onto a stall. Add two regional vendors (`farmers_market/shopkeeper_small_game`, `shopkeeper_herbalist`: smoked game and reeds). Add counter lines: `advanced_pickup_upgrade` (stretch, $3,000: "trapping"), `cobblemon:nest_ball` (A) and `cobblemon:dusk_ball` (A) for watchers in the reeds. |
| **Cinderlee** | (6060, 4981)-(6088, 5009), y107 | medium | The **ember brazier**: a raised blackstone basin with campfires, south of the causeway line so the view east to the gym stays open. Blaine's quiz board as the notice (N). No magma or lava. | 4 | Move the Rim Ironmonger keeper onto a stall. Add a sample-trader stall that sells nothing spawn-relevant: Blaine's core samples as flavour, plus `xp_pump_upgrade` (stretch). Add a field-kitchen stall (regional `shopkeeper_chef`). Add `cobblemon:fire_stone` **only if** the owner moves it off the Exchange's monopoly (STONE_ECONOMY; otherwise no). |
| **Highwire** | (1660, 1386)-(1692, 1400), y174 | small (15 deep) | The **relay pylon**: a waxed copper lattice mast at the east end, crowned with end rods (never a lightning rod, which is a spawn condition). Add a brass sighting pointer aimed at the array, and benches on the west rail facing the drop. Re-pave the plaza in `waxed_exposed_copper`, or `town_audit` will keep expecting a surface that oxidises (`TOWN_CENTERS.md` finding). | 2 | Move the Relay Storekeeper keeper onto a stall on the belvedere, a Mart extension beside the view. Add `jukebox_upgrade` (stretch: "the relay's radio"). **Badge 3 has $1,155 of hard headroom with its stretch item included** (section 5), so anything else here has to wait for the income measurement. |
| **Stoneford** | (1736, 3600)-(1776, 3640), y138 | large | The **Onix run**: a low segmented stone serpent, no hump over 3 high, curling across the SE quarter with its head toward the gym lane. Birch tree pits. The boulder emblem at the gym lane's mouth. | 6 | Give the four regional vendors (apricorn seeds, herbalist, mulch, small game) **stalls**, and move the row one bay off the north avenue and the waystone. Move the Yard Steward keeper onto a stall. Add `tool_swapper_upgrade` (stretch, "a mason's tool belt"). |
| **Holdfast** | (3590, 6440)-(3620, 6462), y112 | medium | The **Gate of Eight**: eight standing stones in an arc off the foot street, each in its gym town's stone, the eighth beside the gym. Victory Road's badge check, as flavour. | 4 | Move the Garrison Quartermaster keeper **into `giovanni_quartermaster`'s stall**. A dressing piece and a keeper already share the name, so the fix is siting. Add a provisions stall (regional `shopkeeper_chef`: rations), plus `everlasting_upgrade` (A; stretch) and `advanced_magnet_upgrade` (stretch, released at last). |
| **Viltri Quay** | (1604, 2796)-(1636, 2828), y107 | medium | The **Starmie fountain**: a five-pointed basin. It needs the owner's water whitelist for this plaza (`TOWN_CENTERS.md` decision 2). Without water, a rescue-boat hull on trestles with the arrivals ledger (N) beside it. | 4 | Put the three regional vendors (two fishmongers and the chef) on stalls. Move the Rescue Quartermaster keeper from 24 off onto a stall. Add `cobblemon:poke_rod`, a lake town's rod, and `pump_upgrade` (stretch). |
| **Tilpey Cross** | The square (6180, 3382)-(6212, 3414), y94, **plus `gym6_market`** (6152, 3418)-(6188, 3464), y95 | medium plus market | On the square, the **flush "eye" mosaic**, so the crossing stays flat. Quartz plinths stand in the corner bays. In `gym6_commons`, the fountain it promises. | 8, in the market block | **The region's market.** Move the Archive Stores keeper here. Add regional vendors (the four farmers'-market templates already in use). Add X items `cobblemon:x_defence`, `x_special_attack`, `x_special_defence` (verified spellings; withheld today as `Combat`, so release them as gated lines). Add `advanced_filter_upgrade` (stretch: "sorting records"). |
| **Sunset West** | (2642, 6480)-(2666, 6508), y64 | medium | An **upturned hull on trestles** in oak, net racks, and a tide-and-charter board (N) naming the ferry lines. | 4 | **Site the Harbour Scrivener first** (scrolls; this is a full-checkout measurement). Add a fish market (`shopkeeper_common_fish`, `shopkeeper_exotic_fish`) and `cobblemon:poke_rod`. It is off path, so the curve does not bind. |
| **Pacifidlog** | (5152, 7372)-(5168, 7388), sea deck y62 | small | The bell raft as it should be. The bell is the owner's spawn call. Without it, a net-mending frame and a chandler's barrel stack. | 2 | **Site the Deck Chandler** on a deck cell. Add the planned fishing trader (`STATE.md:286`): regional fish. |
| **Greenhollow** | (4284, 1526)-(4336, 1586), y110 | large | The **formal garden**: four hedged parterres and a central pergola with seats and one cherry tree, on the garden spawn scope the policy already grants. | 6, on the ring's inner edge | Move the Green Grocer keeper onto a stall. Add flower and seed carts (regional `shopkeeper_apricorn_seeds`, `shopkeeper_herbalist`), plus `refill_upgrade` (stretch: "food that follows you", the town's theme). |
| **Steepside** | (2604, 3570)-(2632, 3596), y114 | medium | A **tea pavilion** with low tables, a cherry tree pit and stone lanterns. | 2 | Widen the shelf from 2 lines to the flavours: `cobblecuisine:mint_pokepuff`, `citrus_pokepuff`, `mocha_pokepuff` (verified ids; whether flavour matters is unverified). It is off path. |
| **Redbrow** | (4830, 5680)-(4856, 5700), y161 | medium (small use) | Sample piles and a sieve on the yard, by the prospector's door. | 1 | **First a clerk record** in `data/traders.json`, the prospector, so the counter can be sited (`markets.py:306-308`). Then the existing Soft Sand and Heavy Ball shelf. This waits on Q-4. |
| **Pallet** | No rect. Candidate east of the main street, north of the cross street: box (1466, 5262)-(1486, 5282), heightmap 117-118. **Not checked against the Mart template's footprint.** | small | None: the town is intact by rule. Add a bench pair and the "first step" stone at the Route 1 mouth. | 1 | Site the Packmaker (leather pack, bedroll) by measuring the free cells outside the Mart door in a full checkout. |
| **Bridgekeep** | (6798, 4353)-(6828, 4381), y113 | medium | **The well its plan promises**, plus a rope winch at the gap onto the drop. | 0 | None, unless the owner wants "rope, not stock" (`no_counter`). |
| **The Deep's city** | Rimside's existing stall row | - | Exists. | Exists | A `data/towns.json` record (or a declared exception) so the markets audit sees the city. A Mart clerk record. A Compact counter, which is story-gated, so its stock is Codex's and the owner's. |
| **Northlight** | as is | - | Exists: the bonfire. | - | Benches of packed ice facing the fire. Stock unchanged. |

## 5. The backpack-ladder pattern: copy it exactly

The owner's "build out the rest of the stock the same way" points at one data file and one generator.

**Data: `data/markets.json`.**

- `:62` `counters`: one record per town. Pallet's is `:63-77` and Stoneford's, the first sited one,
  `:78-100`. Each record has:
  - `id`, `town`, `path` (`critical` or `off_path`), `badge` and `status` (`sited` or `unsited`, with
    `unsited_why`);
  - `at` [x, y, z], `yaw`, `site_why` and `sited_by`;
  - `near_trader` (the Mart clerk's `data/traders.json` id);
  - `keeper` {`name`, `greeting`} and `theme` (the one line that makes the shelf "read as the place");
  - `stock`, a list of {`id`, `item`, `name`, `count`, `price`, `gate` (a badge flag or null),
    `strand` (`convenience` or `power`), `why`}, with an optional `stretch: true` and `affordable_by`.
- `:356` `no_counter`: every other `data/towns.json` town, each with its `why`.
- `:17-25` `income_basis`: the cumulative income by badge, relayed from `PROGRESSION_LADDER.md` 0.2, and
  `target_ratio` 0.7.
- `:26-35` `badges` and `:51-61` `recipe_overlay`: every Sophisticated Backpacks item sold has its recipe
  disabled in `modpack/config/sophisticatedcore-common.toml` `enabledItems`, unless it is in
  `left_craftable`.

**Generator: `tools/markets.py`.**

- `:98-99` emits `sited` counters only.
- `:130-154` builds one dialogue menu per keeper. Each gated option is `visible_when` its badge flag,
  compiled by `tools/compile_dialogue.py`.
- `:158-195` writes the purchase function: cooldown, gate re-check, `cobbledollars query`, refuse if short,
  charge by macro, verify the fall, give as the player, refund on a failed give.
- `:198-222` writes the pack `build/datapacks/cobblers_markets`.
- `:225-228` emits the keepers for `tools/reapply.py` R17M (`reapply.py:1710`, the `npc` action).
- `:372-` curve and `:398-` `curve_problems`; `:445-` `site_problems`.
- The CLI is `build`, `audit`, `overlay`, `report` and `ids`.

**The six things the pattern enforces that a square-and-stalls build has to change or respect.** All six
were measured from the code and from `markets.py report` today.

1. **One counter per town.** `markets.py:276-279` fails any town with more than one entry across
   `counters` and `no_counter`. "More traders" at a town under this pattern means either more lines on the
   one keeper, or a schema change (for example a `stall` key on several counters per town, with the check
   keyed on town plus stall). That is a test-author change.
2. **The critical path is at its budget.**

   | Badge | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
   |---|---|---|---|---|---|---|---|---|
   | Ratio of ask to income (stretch excluded) | 0.69 | 0.67 | 0.70 | 0.65 | 0.68 | 0.67 | 0.65 | 0.69 |

   The hard check includes stretch items and is cumulative. Stoneford's $7,500 crafting upgrade is the one
   stretch item, and it counts from badge 3 (`affordable_by`). The headroom it leaves:

   | Badge | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
   |---|---|---|---|---|---|---|---|---|
   | Headroom with stretch | $2,925 | $5,573 | **$1,155** | $8,315 | $12,105 | $19,975 | $30,538 | $38,078 |

   Every dollar added at an early badge also comes out of every later badge's headroom. New gated stock
   in gym towns therefore has three options: be stretch and small, wait for EXP-A's income measurement
   (`income_basis.relayed: true`), or go on the regional, ungated `data/traders.json` path, which the curve
   does not count.
3. **A critical-path counter gates only on its own badge** (`markets.py:326-328`). Stock released later in
   an earlier town is not expressible today.
4. **A sited counter needs a clerk to stand beside** (`markets.py:306-308`). Redbrow, the Deep's city and
   any stall-only square fail this check.
5. **The keeper's site rule says "beside its Mart, on its door side, facing the plaza"** (`markets.py:37-42`,
   `site_problems` `:445`). Moving a keeper onto a square stall changes that rule. The ground still comes
   from the plan (the plaza's `y`), so the ground rule is untouched.
6. **The plaza is masked from every dressing piece** (`town_dressing.py:195-197`). A centrepiece and its
   stalls need the generator `TOWN_CENTERS.md` section 3 specifies (`tools/plaza_centre.py`, step R13 after
   R9F and before R16) or a deliberate opening in that mask. The flush lamps (`town_plan.py:208-210`) and
   `tools/light_plan.py` must then see the new blocks.

**The second trader pattern** is the produce stalls: `data/traders.json` stock `regional`, generated by
`tools/traders.py` and applied at R14. A BCA shopkeeper template is summoned by resource id, its trade list
filtered by `stock_policy`. It sells ungated produce through the CobbleDollars trade GUI. The templates the
repository already uses and knows exist are:

- `farmers_market/`: `apricorn_seeds`, `herbalist`, `small_game`, `common_fish`, `exotic_fish`, `chef`;
- `store_workers/`: `ds_mulch`, plus `ds_general`, `ds_special_balls` and `ds_battle_items` (the last two
  withdrawn).

The full list of BCA shopkeepers is not in the repository. Read `data/bca/structure/stores/**` from
`COBBLEVERSE-DP-v31.zip` in a full checkout.

**Not used anywhere yet**, so free for new shelves (`TIERED_GOODS.md` section 2.1):

- the `deposit`, `restock`, `refill`, `tool_swapper`, `pump`, `jukebox` and `xp_pump` upgrades;
- the `advanced_` forms of `pickup`, `filter` and `magnet`, among others;
- the `everlasting` upgrade (id not confirmed in that section's list);
- stack tiers 2-4, which are crafted from the bought tier 1;
- every Comforts colour, and the cuisine flavours.

## 6. For the owner

1. **Direction**, unchanged from `TOWN_CENTERS.md` decision 1: a signature centrepiece per town, or calm
   civic squares?
2. **Keepers onto the squares?** This moves R17M's site rule from "beside the Mart" to "at a stall on the
   plaza".
3. **More than one keeper per town?** This is a schema change in `data/markets.json` and its audit.
4. **The budget**: should new gym-town stock be stretch only, or wait for the income measurement, or use
   the ungated regional stalls?
5. **Water and bells on squares** (Viltri Quay's fountain, Pacifidlog's bell, Tilpey's commons fountain):
   `TOWN_CENTERS.md` decision 2.
6. **The Deep's city**: does the Compact sell, and to whom?
