# Town character: purpose, landmark, dressing, palette, and how much is pasted

**Status: proposed, 2026-09-27, written while the owner was asleep ("make the call, record it, move on").** Every
purpose below is a call an agent made from the arc and the settlement briefs; **each is on the review list at the
end, for the owner to correct.** The measurement is reproducible (`python tools/town_character.py measure`).

**The owner's brief, verbatim (given weeks ago):** "Several towns read as pasted." Every town gets:
- a one-line purpose. For gym towns, use the civic roles already in the arc. For minor settlements, use their
  briefs; where there is none, draft one and mark it for Codex;
- a signature landmark that says the purpose from a distance;
- set dressing that expresses it: workshops, stalls, props, work in progress. A mason town has stone being cut. A
  fishing town has nets drying;
- its own material palette;
- a measurement of how much of each town is bespoke versus straight donor, as a check on whether it has character.

The brief also asked for the purposes to be reported before anything was built, so the owner could correct them.
The owner is asleep, so they were committed first, on their own, and building followed on top of them.

## Sources

- **Gym towns:** the civic roles in `docs/story/ARC.md` ("Their proposed civic roles support the geography and
  arc").
- **Other places:** the briefs in `docs/world-building/SETTLEMENTS.md`, the optional-discovery table in `ARC.md`,
  `docs/world-building/LONG_ISLE.md` (the sea town) and `docs/world-building/FOLIAGE.md` §4 (the landmark trees).
- **What stands there now:** each plan's `reading` in `data/placements.json`.
- **Palettes:** partly from `docs/world-building/TOWN_CENTERS.md` (a proposal of 2026-09-25 that nobody has
  decided), partly from what each town's houses are built of.

Every palette here keeps to the spawn-neutral rule of `TOWN_CENTERS.md` rule 7: no block that
`data/spawn_blocks.json` lists as a spawn condition, unless `data/spawn_block_policy.json` already whitelists it for
that place. So there is no wool, no vanilla concrete, no water, no rails, no pumpkins, no bells and no lightning
rods.

## Purposes

Marked **(draft, for Codex)** where no brief says it, and the purpose had to be written here.

| Place | Purpose (one line) | Signature landmark | Set dressing | Palette |
| --- | --- | --- | --- | --- |
| `hometown` (Pallet) | Pallet Town as it was in Kanto, whole, set down on ground that is not Kanto. | Oak's Lab (standing). | The crushed houses at the exchanged edge (`ARC.md`; not built), and nothing else: an intact Pallet is the clue. | CobbleTowns Pallet as it came: oak, white fence, red roofs. |
| `gym1_town` (Brock) | The plateau's builders' town: masons who build in the plateau's stone, and the coordinator who runs the rescue when the ground moves. | A timber derrick crane over the mason's yard, a cut block hanging from its jib. | A mason's yard with stone being cut: stonecutters, a grindstone, cut-stone piles, a wall half built under scaffolding. A rescue depot: barrels, crates, rope coils and a handcart. | Stone, polished andesite, cobblestone, tuff, calcite; stripped birch and spruce timber. |
| `gym2_town` (Misty) | The lake town that takes in whoever the water brings: rescue boats, and a record of every arrival. | A rescue lookout on the promenade with a lantern at its head. | Boats hauled out on the shore, oar racks, net racks, a ledger board of arrivals. | Prismarine and mud brick (the streets), dark oak, spruce. |
| `gym3_town` (Surge) | The signal town under Mt Vessu: its people keep the power, the relays and the storm gear running. | Surge's signal array on the Vessu shoulder (`surge_signal_array`, planned), and a copper relay mast in town. | Cable drums, copper spools, relay cabinets, insulator racks, a storm shutter being hung. | Deepslate and tuff (the houses, in the flank's stone), weathered and waxed copper. |
| `gym4_town` (Erika) | Peak Pond Hollow's garden town, where Erika keeps the peace between the residents and the arrivals. | The green itself, with a glasshouse or pergola at its heart. | Potting benches, compost bins, seed racks, flower carts, trellises, a hedge being planted. | Moss, packed mud, cherry and oak, the garden's flowers (whitelisted for gardens). |
| `gym5_town` (Koga) | A fen-edge watch town where trackers read the marsh and the glacier foot for anyone passing unseen. | A watchtower on mangrove stilts at the fen's edge, seen over the reeds. | Reed-drying racks, eel traps, a tracker's board of cast prints, training targets, smoke racks. | Mangrove, mud brick, packed mud, bamboo, dark oak. |
| `gym6_town` (Sabrina) | The region's place of study: Sabrina's people record what the Rift does to memory, perception and Pokemon. | The observatory (standing, Mega Showdown's), and a white listening spire with a lens at its head. | Reading stalls and record carts, instrument stands, lecterns, "memory stones" on plinths along the rows. | Calcite, smooth quartz, polished diorite, birch; purpur and end rods as accents. |
| `gym7_town` (Blaine) | A research town on the crater rim: it studies the cone's energy, and keeps the mound between itself and the fire. | An instrument tower on the rim, facing the cone, with signal smoke rising from its top. | Core-sample racks, crates of rock samples, a field laboratory (brewing stands, cauldrons, a lectern), survey tables, a fumarole vent. | Blackstone, basalt, tuff, terracotta; acacia (the houses) and copper instruments. |
| `gym8_town` (Giovanni) | The southern garrison: Giovanni defends the settlements behind him and holds the last gate before Victory Road. | A signal beacon on the dome's crown. | A supply depot, palisade stakes, armour and weapon racks, a training yard, sandbag walls. | Terracotta, polished granite, spruce, coarse dirt; mud brick for the sandbags. |
| `league` | The League: the region's last hall, on the Rift's apex, reached only by Victory Road. | The League building (Cobbleverse's). | The torch walk of `TOWN_CENTERS.md` (braziers either side of the ramp); not built. | Polished tuff, tuff bricks, gold trim. |
| `sunset_west` | The region's harbour: fishers and boatwrights, and the charter boats to the outer sea. | The slipway with a hull on it (standing). | Nets drying, boats on trestles, fish racks, crates on the quay. | Brick (the streets), polished granite, spruce, oak. |
| `northlight` | The cold-water research town: the region's weather and aurora observatory, and an ice-type field station. | The observatory on the isle's high point (standing). | Weather instruments, sled racks, ice blocks being cut, a field station's crates. | Deepslate, spruce, packed ice, light-blue glass. |
| `mining_town` | Ore and minerals on the eastern cone: the mine head, the ore rail, a smelter and a fossil lab. | The headframe over the capped shaft (standing). | The working mine (standing: `tools/mining_works.py`). | Deepslate and tuff (the houses, re-materialed). |
| `displaced_city` | A summit town exchanged into a cavern, its streets still laid for a mountaintop: the deepest human account of an exchange. | The summit cairn (standing). | Its fields (standing); an altitude plaque that is wrong by a mountain (`TOWN_CENTERS.md`, not built). | Cherry and dark oak (the houses, re-materialed), stone brick. |
| `tea_town` | A town built on one industry: tea terraces over Shrew Lake, a tea house, and Poltchageist. | The tea house on the terrace's edge (standing, BCA's), over the terraces (standing). | Leaf-drying racks, tea chests, kettles, pickers' baskets on the terrace ends. | Mossy stone brick, bamboo, cherry. |
| `sea_town` (Pacifidlog, working name) | A fishing town floating in the Sound: rafts, a fishers' row, a boatwright, and the stilt quarter. | The Current Gate lookout (standing). | Standing (`tools/sea_town.py`): the fishing stations, the yard's hull in frame. | Bamboo, jungle wood, spruce, mangrove. |
| `merian_hut` | The keeper's hut at the river's source: a bed kept ready at the end of a long walk. | The hut against the cliff, with smoke from its chimney. | A woodshed and log piles, the stable's hay, the keeper's water barrels. | Spruce, cobblestone. |
| `gorge_hamlet` | The bridge-keepers' walled yard above the Tilpey gorge, whose keeper knows the river. | The well its plan promises (not built; no placement exists), and a rope-winch at the gap onto the drop. | Rope coils, a winch, water jars. | Sandstone, cut sandstone. |
| `tableland_stop` | A waystation and a prospector's house on the badlands rim, whose lookout is seen from the road below. | The watchtower (standing, vanilla). | The prospector's sample piles, a sieve, crates of ore samples. | Red sandstone, terracotta. |
| `rift_rim_stop` | The rangers' post on the Rift's rim: the last Center before the League, off the road so Victory Road stays whole. | The railed overlook over the rim (standing). | The rangers' gear racks and firewood. | Spruce, coarse dirt. |
| `relic_island` | A Pallet home on a torn-off islet: evidence that the exchange was not clean. | The house and the broken seam behind it (standing). | Nothing added: the islet is the evidence. | Pallet's own; calcite and amethyst at the seam. |
| `the_scar` | Where the Displaced City stood: its own houses in ruin on a pressed disc high on Mt Vessu. | The two standing towers (standing). | The ruins (standing). The story is with Codex (`HANDOVER_CODEX.md` item 27). | Cracked and mossy stone brick. |
| `viltri_light` | A lighthouse keeping a light over an estuary no river uses any more. | The lighthouse (standing). | The keeper's track (standing). | Stone brick. |
| `rift_dig_camp` | Archaeologists excavating towards the steel chamber (Registeel) in the Rift's west spur. | The excavation and its scaffold (standing, Mega Showdown's). | Sieves, finds trays, tool racks and spoil heaps along the track. | Coarse dirt, gravel, spruce, canvas-coloured terracotta. |
| `frostpeak_shrine` | **(draft, for Codex)** A shrine on the mainland's loneliest summit, kept for whoever climbed it first. Whose shrine it is, and what it keeps, is not written anywhere. | The shrine itself (no plan; parked). | None until it has a story. | Snow, packed ice, spruce, stone. |
| `great_oak_pallet` | The first giant a new trainer sees, in the meadow east of the first road. | The tree. | None: a landmark tree, not a settlement. | The tree's own. |
| `sentinel_spruce_tarn` | A clearing worth finding: a 75-block spruce over old growth, with a hidden tarn nearby. | The tree. | None. | The tree's own. |
| `patriarch_wedge` | A dark oak that breaks the skyline over the Rift; climbing out of Victory Road to reach it is the discovery. | The tree. | None. | The tree's own. |
| `cherry_elder_shrew` | A colour landmark: a leaning cherry, pink against the plateau from two legs. | The tree. | None. | The tree's own. |

The Route 1 mansion and the Route 1 old mine have plans in `data/placements.json` but no `data/towns.json` record,
so they are outside the owner's "every town". Both are bespoke builds already (`route1_mansion_house`,
`route1_old_mine_hill`).

## How much of each town is pasted

**Method** (`tools/town_character.py measure`):
- **Source:** the placements in `data/placements.json`. Nothing is read from a world.
- **Classes.** Each placement is one of:
  - **straight donor:** a pack's structure placed by resource id, or a kit copy placed as it came (CobbleTowns,
    Repurposed Structures, vanilla and Cobblemon village houses);
  - **re-materialed:** donor geometry in the town's own materials;
  - **ruined:** donor geometry broken by `tools/ruins.py`;
  - **bespoke:** an earthwork's generated geometry, and the dressing.
- **Infrastructure:** street and plaza paving and the lanterns (`<place>_lights`) are counted but kept out of the
  ratio. Every place has them, and none is known by them.
- **Block volume:**
  - a template counts the non-air blocks it stores;
  - an earthwork counts the non-air blocks its commands write.

  A replace-filtered fill counts at full volume, so a bespoke build can only be over-counted.
- **Share:** straight-donor share = straight donor ÷ (straight donor + re-materialed + ruined + bespoke).
- **Ranking:** most pasted first, by share. Ties go to the town with fewer bespoke blocks, then to the one with more
  straight-donor placements.

**Where the templates were read:**
- a kit file where the checkout has one;
- otherwise the local Cobbleverse instance's own copy, the datapacks before the mods before the vanilla 1.21.1
  jar.

Every template placement of every place (329) was read; none is unmeasured. Measured 2026-09-28, with the dressing (`cobblers_town_dressing`, built) and with the houses of ten towns in their own palettes (`data/rematerial.json` `house_sets`, below); `measure --no-dressing` leaves the dressing out. The first measurement (2026-09-27, `1b9bbc1`, before either) had every gym town but Surge's at 100%. The
paving cells come from `tools/town_plan.py` and are shown as "-" where the place has no town plan.

| Rank | Place | Straight donor | Re-materialed | Ruined | Bespoke | Share straight donor | Placements (donor / rem. / ruin / bespoke) | Most repeated template | Paving cells | Unmeasured |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 1 | `rift_dig_camp` | 2,680 | 0 | 0 | 0 | 100% | 11 / 0 / 0 / 0 | 4 | 699 | 0 |
| 2 | `hometown` | 6,719 | 0 | 0 | 0 | 100% | 9 / 0 / 0 / 0 | 1 | - | 0 |
| 3 | `jungle_ruins` | 1,968 | 0 | 0 | 0 | 100% | 6 / 0 / 0 / 0 | 1 | 1,746 | 0 |
| 4 | `merian_hut` | 1,211 | 0 | 0 | 0 | 100% | 3 / 0 / 0 / 0 | 1 | 1,038 | 0 |
| 5 | `tableland_stop` | 1,966 | 0 | 0 | 0 | 100% | 3 / 0 / 0 / 0 | 1 | 1,200 | 0 |
| 6 | `league` | 159,487 | 0 | 0 | 0 | 100% | 1 / 0 / 0 / 0 | 1 | 0 | 0 |
| 7 | `rift_rim_stop` | 1,314 | 0 | 0 | 53 | 96% | 3 / 0 / 0 / 1 | 1 | 1,597 | 0 |
| 8 | `gorge_hamlet` | 1,014 | 0 | 0 | 120 | 89% | 3 / 0 / 0 / 1 | 1 | 1,722 | 0 |
| 9 | `gym2_town` | 18,562 | 2,566 | 0 | 0 | 88% | 3 / 8 / 0 / 0 | 1 | 2,417 | 0 |
| 10 | `gym3_town` | 4,942 | 845 | 0 | 0 | 85% | 3 / 4 / 0 / 0 | 1 | 973 | 0 |
| 11 | `gym6_town` | 20,329 | 5,952 | 0 | 409 | 76% | 6 / 32 / 0 / 0 | 1 | 4,962 | 0 |
| 12 | `gym4_town` | 5,007 | 2,338 | 0 | 0 | 68% | 3 / 10 / 0 / 0 | 1 | 5,133 | 0 |
| 13 | `gym8_town` | 4,811 | 2,415 | 0 | 258 | 64% | 3 / 14 / 0 / 0 | 1 | 3,266 | 0 |
| 14 | `gym7_town` | 4,799 | 2,372 | 0 | 463 | 63% | 3 / 12 / 0 / 0 | 1 | 2,882 | 0 |
| 15 | `relic_island` | 448 | 0 | 0 | 280 | 62% | 1 / 0 / 0 / 1 | 1 | 19 | 0 |
| 16 | `gym5_town` | 4,856 | 3,084 | 0 | 311 | 59% | 3 / 16 / 0 / 0 | 1 | 2,689 | 0 |
| 17 | `gym1_town` | 4,819 | 4,127 | 0 | 284 | 52% | 3 / 18 / 0 / 0 | 1 | 3,485 | 0 |
| 18 | `northlight` | 5,175 | 2,779 | 0 | 2,137 | 51% | 3 / 14 / 0 / 1 | 1 | 2,780 | 0 |
| 19 | `mining_town` | 5,377 | 3,624 | 0 | 1,630 | 51% | 3 / 14 / 0 / 2 | 1 | 2,696 | 0 |
| 20 | `displaced_city` | 4,373 | 3,193 | 0 | 1,682 | 47% | 24 / 18 / 0 / 5 | 2 | 5,760 | 0 |
| 21 | `sunset_west` | 3,008 | 4,165 | 0 | 695 | 38% | 2 / 17 / 0 / 4 | 1 | 3,585 | 0 |
| 22 | `tea_town` | 4,206 | 3,148 | 0 | 26,600 | 12% | 3 / 15 / 0 / 1 | 1 | 2,133 | 0 |
| 23 | `viltri_light` | 0 | 0 | 0 | 1,259 | 0% | 0 / 0 / 0 / 1 | 0 | 141 | 0 |
| 24 | `the_scar` | 0 | 0 | 6,301 | 6,571 | 0% | 0 / 0 / 33 / 4 | 2 | 5,231 | 0 |
| 25 | `sea_town` | 0 | 3,008 | 0 | 27,197 | 0% | 0 / 2 / 0 / 6 | 1 | 289 | 0 |
| 26 | `frostpeak_shrine` | 0 | 0 | 0 | 0 | n/a | 0 / 0 / 0 / 0 | 0 | - | 0 |
| 27 | `great_oak_pallet` | 0 | 0 | 0 | 0 | n/a | 0 / 0 / 0 / 0 | 0 | - | 0 |
| 28 | `sentinel_spruce_tarn` | 0 | 0 | 0 | 0 | n/a | 0 / 0 / 0 / 0 | 0 | - | 0 |
| 29 | `patriarch_wedge` | 0 | 0 | 0 | 0 | n/a | 0 / 0 / 0 / 0 | 0 | - | 0 |
| 30 | `cherry_elder_shrew` | 0 | 0 | 0 | 0 | n/a | 0 / 0 / 0 / 0 | 0 | - | 0 |

**What it says:**
- **Six places are 100% straight donor, and no gym town is among them any more.** On 2026-09-27 thirteen were, with
  every gym town but Surge's; the dressing and the re-materialed houses moved all seven. Of the six, the hometown and
  the League are pasted by design (below); the dig camp, the jungle ruins, Merian's hut and the tableland stop are not
  dressed or re-materialed yet.
- **"Re-materialed" counts a whole house, however much of it the set changed.** The sets change 3% (Northlight,
  whose spruce and ice houses were already in its palette) to 57% (Misty's) of a house's blocks: see the table under
  "The houses in their town's palette".
- **No design repeats within a town,** except the dig camp's tents, the Scar's ruins and the Displaced City's
  pairs. So
  "pasted" here means unaltered, not repeated. Brock's 18 houses are 18 different birch-village pieces; nothing in
  the town is his.
- **The towns that read as places have bespoke work in them:** the tea town's terraces, the sea town, the mining
  town's works, the Scar's ruins, Viltri Light. That is the brief's check doing its job.
- **Two 100% places are pasted by design and are not candidates for dressing.** The hometown is the real Pallet;
  its being unaltered is the clue (`ARC.md`, Pallet). The League is Cobbleverse's own building by the owner's
  choice.

## Which towns get dressed first

The five most pasted places that are not pasted by design are, by the ranking above, **Sabrina's, Brock's, Koga's,
Giovanni's and Blaine's towns**. They are dressed first. Erika's and Misty's (ranks 6 and 7) come next.

## The dressing (built as data and functions; not yet in any world)

**What it is made of:**
- **Data:** `data/town_dressing.json` (`cobblers.town_dressing/1`). Each town has a landmark and its pieces. A
  piece is a kind from the library in `tools/town_dressing.py`, a position, a facing and a palette.
- **Generator:** `tools/town_dressing.py build` writes the pack `cobblers_town_dressing`, one function per town,
  `cobblers:town_dressing/<town>`. It is re-applied by `tools/reapply.py` step **R16B**, after the donors (R9) and
  the lights (R16), so nothing placed later erases a piece.
- **Plan audit:** `tools/town_dressing_audit.py` reads the written functions and checks them against plan data it
  computes itself:
  - the plan's lots and anchor lots;
  - the paved streets and plaza, and each street's drawn polyline at its width;
  - every building's footprint from its template and rotation;
  - the route event sites' recorded areas (`data/scenes.json`): Route 2's Geodude cart stands just north of
    Brock's town, and the audit caught a rope pile on it before this was committed;
  - the heightmap's ground.

  It never uses the generator's mask. `prepare` runs it and stops on any problem. On 2026-09-27: **CLEAN, 11,669
  writes checked, 0 problems** across the five towns.

**How a piece is placed:**
- **Ground:** the heightmap, rounded (`tools/ground.py`). A piece stands on the highest ground under it, and a
  column on falling ground gets a foundation course in the town's own stone.
- **Keeps off:**
  - streets, the plaza and the one-block verge beside them;
  - every house lot and anchor lot, with a block of margin;
  - three blocks round every building (a town rebuild clears two);
  - other earthworks and the lamps;
  - the waystone, traders, signposts, scene props and route event sites (two blocks);
  - routed legs (three blocks);
  - painted water;
  - four blocks round a painted tree, so no crown is left hanging over a cut trunk.
- **Blocks:** only the 87 vanilla 1.21.1 ids in the data's allowlist, each checked against the 1.21.1 client jar's
  block states. None is a spawn condition (`data/spawn_blocks.json`, re-checked by `tests/test_town_dressing.py`),
  so the dressing decides no encounters.

| Town | Landmark (top) | Pieces | Blocks | What the dressing says |
| --- | --- | ---: | ---: | --- |
| Brock (`gym1_town`) | **A timber derrick crane** at (1768, 3672), between the plaza and the gym knoll. Its jib reaches over the mason's yard, with a cut block hanging from a chain. Top y159, 20 blocks over the ground. | 18 | 285 | **The mason's yard:** a wall half built under scaffolding, cut-stone piles, a stonecutter, grindstone and anvil bench, a lime kiln smoking. More cut stone waits on the approach from Pallet and at the west lane. **The rescue depot** by the road north: the red flag, crates, rope, water barrels and shoring timber, and the coordinator's red-awninged stall by the Mart. |
| Koga (`gym5_town`) | **A watchtower on mangrove stilts** at (4568, 2420), at the fen's edge west of the high street. It has a railed platform, a roof and a lantern, and a ladder up one leg. Top y130. | 18 | 311 | **Along the fen edge:** four reed-drying racks, bundles of reed, eel traps. **Two smoke racks.** **At the market yard:** a stall. **The trackers:** two boards of mud casts and a practice yard of four targets. |
| Sabrina (`gym6_town`) | **A listening spire** at (6140, 3300), on the high ground by the observatory: a quartz shaft on a diorite plinth, amethyst at its foot, a tinted-glass lens and end rods at its head. Top y120, 22 blocks over the ground. | 18 | 174 | **Along the east and west rows:** seven memory stones (a diorite plinth, a quartz stone, an amethyst cluster). **Two reading stalls and two record stalls** with lecterns and shelves. **Four copper instrument stands,** on the high ground and aimed across the lake. |
| Blaine (`gym7_town`) | **An instrument mast** on the mound's top at (6015, 4935): a blackstone shaft, a copper instrument deck, and rods pointed east at the cone. Top y128. | 14 | 331 | **On the open rim east of the square:** four fumaroles smoking in basalt rings, and two copper instruments aimed at the cone. The rim stays unbuilt, as its plan says. **By the square:** a field laboratory, core-sample racks, sample crates, obsidian and cooling rock. |
| Giovanni (`gym8_town`) | **A signal beacon** on the dome's crown at (3625, 6555): a granite tower with terracotta bands and a signal fire, whose smoke column stands far above it. Top y128. | 17 | 258 | **At the gate square:** a palisade, sandbag walls, the supply depot and the garrison's orange colours, where the road leaves for Victory Road. **South of the square:** a quartermaster's stall. **On the dome's flank:** a training yard with targets, cover and an armoury bench. |

**The dressing alone moved the measurement only a little** (Sabrina's town to 99% straight donor, Brock's and
Giovanni's 97%, Koga's and Blaine's 96%). Props are small beside eighteen houses: 174 to 331 blocks against 7,000 to
26,000. A town's volume is its houses.

### The houses in their town's palette (2026-09-28; built, not yet in any world)

The owner approved the palette lever. Every house of ten towns (156) now names a material set in `data/rematerial.json`
`house_sets`, alternating the town's two sets where it has two, so a street is not one colour.
`tools/place_town.py` places a copy of the house with its palette renamed like for like (stairs stay stairs, walls
walls, logs pillars; a map entry whose block the house lacks is skipped), jigsaw final states included. The gym, the
Centre and the Mart keep their own looks. Every target block was checked against `data/spawn_blocks.json`: none is a
spawn condition (quartz, which Sabrina's palette names, is, and is left out).

| Town | Sets | What changes | Blocks swapped | Straight donor (was) |
| --- | --- | --- | ---: | ---: |
| Brock (`gym1_town`) | `brock_mason_a`, `_b` | cobble to stone brick or polished andesite; white terracotta to calcite or tuff brick; birch roofs to spruce (a) | 44% | 52% (97%) |
| Misty (`gym2_town`) | `misty_rescue_a`, `_b` | oak to dark oak (a) or spruce (b); cobble to mud brick; cyan terracotta to prismarine brick | 57% | 88% (100%) |
| Erika (`gym4_town`) | `erika_garden` | the cherry houses keep their cherry; oak wood to stripped cherry, brick to packed mud and mud brick | 14% | 68% (100%) |
| Koga (`gym5_town`) | `koga_fen_a`, `_b` | oak to dark oak (a) or mangrove (b), stripped logs to mangrove or bamboo, terracotta to packed mud or mud brick | 25% | 59% (96%) |
| Sabrina (`gym6_town`) | `sabrina_study_a`, `_b` | stone brick and cobble to polished diorite, calcite or smooth stone; spruce frames to birch | 42% | 76% (99%) |
| Blaine (`gym7_town`) | `blaine_rim` | dark oak frames to basalt and blackstone; red sandstone trim to tuff | 22% | 63% (96%) |
| Giovanni (`gym8_town`) | `giovanni_garrison_a`, `_b` | sandstone to polished granite and terracotta, sand to coarse dirt; cobble to mud brick (b) | 42% | 64% (97%) |
| `northlight` | `northlight_cold` | light-blue glass; cobble, diorite and smooth-stone trim to deepslate | 3% | 51% (79%) |
| `sunset_west` | `sunset_harbour_a`, `_b` | cobble to brick (a) or polished granite (b); oak roofs to spruce (a) | 34% | 38% (91%) |
| `tea_town` | `tea_terrace` | mud brick to mossy stone brick, packed mud to mossy cobble, yellow trim to stripped cherry | 15% | 12% (22%) |

"Blocks swapped" is the share of the houses' own non-air blocks the sets rename, read from the donor templates. The
share column counts a re-materialed house whole, so Northlight's 3% moves it as far as Brock's 44%: its spruce and
ice houses were already in its palette, and the measure says little there. **Not verified:** how any of it looks,
and that the houses stand in the world (the main session's `tools/town_audit.py` run after R8, which reads the
rewritten copies).

## Install and run (for the orchestrator, on staging)

**Build** (no server needed):
```
python tools/reapply.py prepare --source-root <root> --server-dir <server>
```
It runs `town_dressing.py build` and `town_dressing_audit.py` after the town plans and signposts, and stops if the
audit finds anything.

To build it alone, it needs:
- `tools/town_plan.py <town>` for the five towns;
- `tools/critical_legs.py`;
- `tools/signposts.py function`;
- a `build/paint` from `tools/paint_maps.py`.

Then:
```
python tools/town_dressing.py build
python tools/town_dressing_audit.py
```

**Install:** with the server stopped, `python tools/reapply.py install ...` installs `cobblers_town_dressing` into
`<server>/datapacks` (a global pack, like `cobblers_towns`: it has no load or tick tag, so it does nothing until a
function is run).

**Run**, with the server up after the towns, the donors and the lights (R8, R9, R16):
```
python tools/reapply.py run --server-dir <server> --only R16B
```

Or by hand over RCON, in this order, with drops off (`gamerule doTileDrops false`, restored afterwards, because the
clearing fills pop grass and flowers):

1. `function cobblers:town_dressing/gym1_town`
2. `function cobblers:town_dressing/gym5_town`
3. `function cobblers:town_dressing/gym6_town`
4. `function cobblers:town_dressing/gym7_town`
5. `function cobblers:town_dressing/gym8_town`

Then `save-all`.

**Chunks:** no manual force-loading is needed. Each function force-loads every chunk it writes before its first
command and releases them after its last (`tools/function_limits.py` `ensure_loaded`). The boxes are 6 to 15
per town, all inside x1664-1807 z3536-3727 (Brock), x4544-4719 z2336-2463 (Koga), x6096-6303 z3280-3519
(Sabrina), x6000-6143 z4928-5039 (Blaine) and x3568-3663 z6400-6559 (Giovanni).

**Check in the world:** `derived/town_dressing/checks.txt` (written by the build) has one
`execute if block x y z <block>` per piece, each answered "Test passed" when the piece stands. For the five
landmarks:
```
execute if block 1768 159 3672 minecraft:lantern
execute if block 4570 130 2422 minecraft:mangrove_slab
execute if block 6140 120 3300 minecraft:end_rod
execute if block 6015 128 4935 minecraft:end_rod
execute if block 3625 128 6555 minecraft:campfire
```

**Not verified:**
- none of this has been run in any world;
- nobody has seen a piece in game;
- whether the smoke columns read from the roads, and whether a stall's front posts sit well on its counter;
- whether a ladder or a lantern survives its neighbours' updates (each is placed after the block it hangs on).

## Gates: where the guards would stand (not built)

The original brief also said **"THE GATES ARE GUARDS"**: a town's way in is marked by the people who keep it, not
by a structure. **No guard is built here, and none is authored.**

**Where each gate would go:**
- Every gate is a plan's own entry or exit point in `data/placements.json` (`plan.entries[].at`,
  `plan.exits[].at`), where the street meets the town's edge.
- Ground heights are the heightmap's, rounded. The Displaced City, Relic Island and the sea town stand on their own
  ground, so no height is given for them.
- **A guard stands beside the road, never on it.** The walked line and the street must stay open.

**Critical path** (a gate at each end of every town on it):

| Town | Gate | Faces | Position | Street |
| --- | --- | --- | --- | --- |
| Pallet (`hometown`) | out | Route 1 to Brock | (1461, 5226) y118 | `route_north` |
| Brock (`gym1_town`) | in | from Pallet | (1654, 3736) y133 | `approach_sw` |
| Brock | out | to Misty | (1756, 3520) y137 | `north_avenue` |
| Misty (`gym2_town`) | in | from Brock | (1664, 2846) y107 | `shore_approach` |
| Misty | out | to Surge | (1620, 2742) y105 | `north_avenue` |
| Surge (`gym3_town`) | in | from Misty | (1674, 1437) y174 | `lip_walk` |
| Surge | out | to Erika | (1700, 1378) y174 | `array_path` |
| Erika (`gym4_town`) | in | from Surge | (4232, 1554) y109 | `pond_road` |
| Erika | out | to Koga | (4392, 1554) y111 | `east_lane` |
| Koga (`gym5_town`) | in | from Erika | (4572, 2355) y116 | `post_road` |
| Koga | out | to Sabrina | (4751, 2524) y121 | `post_road` |
| Sabrina (`gym6_town`) | in | from Koga | (6104, 3398) y94 | `cross_street` |
| Sabrina | out | to Blaine | (6196, 3496) y94 | `grand_axis` |
| Blaine (`gym7_town`) | in | from Sabrina | (6150, 4919) y105 | `rim_road` |
| Blaine | out | to Giovanni | (6002, 5067) y109 | `rim_road` |
| Giovanni (`gym8_town`) | in | from Blaine | (3709, 6436) y109 | `foot_street` |
| Giovanni | out | to Victory Road and the League | (3593, 6426) y111 | `foot_street` |
| League | in | from Victory Road (the stair's mouth on the apron) | (3656, 2486) y86 | none |

**Other places** (one way in each):

| Place | Faces | Position | Street |
| --- | --- | --- | --- |
| Merian hut | Route 4 | (2813, 1222) y107 | `cirque_path` |
| Gorge hamlet | Route 7 | (6531, 4358) y107 | `dune_trail` |
| Tableland stop | Route 8 | (4708, 5561) y156 | `brow_trail` |
| Rift rim post | Victory Road | (4007, 3678) y85 | `rim_trail` |
| Rift dig camp | the spur's mouth | (3166, 3300) y88 | `camp_track` |
| The Scar | the south slope | (2110, 1098) y280 | `old_avenue` |
| Northlight | the landing | (7265, 1444) y111 | `harbour_road` |
| Mining town | the west | (6522, 5716) y137 | `ore_road` |
| Tea town | the north | (2600, 3486) y112 | `terrace_road` |
| Displaced City | the tunnel (cavern floor) | (3264, 1662) | `old_road` |
| Relic Island | the sea (islet) | (1110, 5531) | `front_walk` |
| Viltri Light | inland | (574, 4519) y75 | `keeper_track` |
| Jungle ruins | the north shore | (5160, 7318) y122 | `causeway` |
| Sunset West | the southern coast on foot, and the sea | (2790, 6625) y63; (2616, 6482) y66 | `strand`; `quay` |
| Sea town | the jetty's boats (decks) | (7172, 6711) | none |

**For Codex (the guards' characters), with the constraints any answer must keep:**
- **Who each guard is.** The natural reading is that each town's guards come from its trade, as its dressing
  does: a mason on watch at Brock's, rescue-boat crew at Misty's, a lineman at Surge's, a gardener at Erika's, a
  tracker at Koga's, a record-keeper at Sabrina's, a researcher at Blaine's, a garrison soldier at Giovanni's.
  Names, voices and what each says are unwritten.
- **Guards gate nothing.** The critical path stays at ten, and nothing else gates it (`SETTLEMENTS.md`,
  validated). A guard can greet, warn or point the way. It cannot stop a player, except where a flag already
  gates the way:
  - Giovanni's gym is already Victory Road's gate, on `gym8_cleared`;
  - the League opens on `gym8_cleared` today, and the Rift-to-League handoff has no setter (`STATE.md`, mainline
    reveal runtime).
- **The ruins and outposts may have no guard at all.** The Scar and the jungle ruins are dark and unkept by design.
  A guard there would contradict them.
- **When built, guards are NPCs.** Cobblemon's NPCs are placed over RCON after a restart
  (`reapply.py` R9F and R17), never by a function. They stand pinned beside the road, like the route trainers.
- **The Rift already has five "guard trailhead" placeholders** (`tools/rift_skin.py`). Whether they are the same
  kind of guard is for Codex too.

## For the owner to correct

Every line of the purposes table is an agent's call. These are the ones most worth a look:

1. **Every gym-town purpose.** Each turns an `ARC.md` civic role ("proposed", "they do not change trainer teams or
   structures") into a trade the town can show. The trades are: Brock's masons, Misty's rescue boats, Surge's
   relays, Erika's gardeners, Koga's trackers, Sabrina's record-keepers, Blaine's crater researchers and
   Giovanni's garrison.
2. **Brock's landmark is a crane, not a tower:** a builders' town says so with the tool it builds with.
3. **Giovanni's town as a garrison.** "Civil defender" read as soldiers, supplies and a beacon. It is not read as a
   fortress: the gym is already the gate.
4. **Frostpeak shrine's purpose is drafted, for Codex** (`HANDOVER_CODEX.md` item 28). No brief says whose shrine it is.
5. **Hometown and the League are left undressed on purpose** (pasted by design, above).
6. **The ranking's tie-break.** Six places tie at 100% (thirteen did before the dressing and the house palettes).
   Placement count decides among them, so bigger all-donor towns rank as more pasted.
7. **The dressing keeps off every anchor lot, open squares included.** Sabrina's market square and commons are
   anchor lots, so they got no stalls. A square is where a town's market belongs; that waits on the town-centre
   decisions in `TOWN_CENTERS.md`.
8. **No wool, cobweb or water anywhere in the dressing.** All three are spawn conditions. So a fishing town's
   drying nets, when one is dressed, will have to be iron bars or chains in a timber frame. No fishing town is in
   the five.
9. **Houses keep their village materials** (the palette lever above).
