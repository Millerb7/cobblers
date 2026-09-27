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

Every template placement of every place (329) was read; none is unmeasured. Measured 2026-09-27 on `1b9bbc1`, before any dressing. The
paving cells come from `tools/town_plan.py` and are shown as "-" where the place has no town plan.

| Rank | Place | Straight donor | Re-materialed | Ruined | Bespoke | Share straight donor | Placements (donor / rem. / ruin / bespoke) | Most repeated template | Paving cells |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 1 | `gym6_town` (Sabrina) | 26,281 | 0 | 0 | 0 | 100% | 38 / 0 / 0 / 0 | 1 | 4,962 |
| 2 | `gym1_town` (Brock) | 8,946 | 0 | 0 | 0 | 100% | 21 / 0 / 0 / 0 | 1 | 3,485 |
| 3 | `gym5_town` (Koga) | 7,940 | 0 | 0 | 0 | 100% | 19 / 0 / 0 / 0 | 1 | 2,689 |
| 4 | `gym8_town` (Giovanni) | 7,226 | 0 | 0 | 0 | 100% | 17 / 0 / 0 / 0 | 1 | 3,266 |
| 5 | `gym7_town` (Blaine) | 7,171 | 0 | 0 | 0 | 100% | 15 / 0 / 0 / 0 | 1 | 2,882 |
| 6 | `gym4_town` (Erika) | 7,345 | 0 | 0 | 0 | 100% | 13 / 0 / 0 / 0 | 1 | 5,133 |
| 7 | `gym2_town` (Misty) | 21,128 | 0 | 0 | 0 | 100% | 11 / 0 / 0 / 0 | 1 | 2,417 |
| 8 | `rift_dig_camp` | 2,680 | 0 | 0 | 0 | 100% | 11 / 0 / 0 / 0 | 4 | 699 |
| 9 | `hometown` | 6,715 | 0 | 0 | 0 | 100% | 9 / 0 / 0 / 0 | 1 | - |
| 10 | `jungle_ruins` | 1,968 | 0 | 0 | 0 | 100% | 6 / 0 / 0 / 0 | 1 | 1,746 |
| 11 | `merian_hut` | 1,213 | 0 | 0 | 0 | 100% | 3 / 0 / 0 / 0 | 1 | 1,038 |
| 12 | `tableland_stop` | 1,968 | 0 | 0 | 0 | 100% | 3 / 0 / 0 / 0 | 1 | 1,200 |
| 13 | `league` | 159,487 | 0 | 0 | 0 | 100% | 1 / 0 / 0 / 0 | 1 | 0 |
| 14 | `rift_rim_stop` | 1,316 | 0 | 0 | 53 | 96% | 3 / 0 / 0 / 1 | 1 | 1,597 |
| 15 | `sunset_west` | 7,173 | 0 | 0 | 695 | 91% | 19 / 0 / 0 / 4 | 1 | 3,585 |
| 16 | `gorge_hamlet` | 1,016 | 0 | 0 | 120 | 89% | 3 / 0 / 0 / 1 | 1 | 1,722 |
| 17 | `gym3_town` (Surge) | 4,942 | 845 | 0 | 0 | 85% | 3 / 4 / 0 / 0 | 1 | 973 |
| 18 | `northlight` | 7,954 | 0 | 0 | 2,060 | 79% | 17 / 0 / 0 / 1 | 1 | 2,780 |
| 19 | `relic_island` | 448 | 0 | 0 | 280 | 62% | 1 / 0 / 0 / 1 | 1 | 19 |
| 20 | `mining_town` | 5,377 | 3,624 | 0 | 1,630 | 51% | 3 / 14 / 0 / 2 | 1 | 2,696 |
| 21 | `displaced_city` | 4,373 | 3,193 | 0 | 1,682 | 47% | 24 / 18 / 0 / 5 | 2 | - |
| 22 | `tea_town` | 7,354 | 0 | 0 | 26,600 | 22% | 18 / 0 / 0 / 1 | 1 | 2,133 |
| 23 | `viltri_light` | 0 | 0 | 0 | 1,259 | 0% | 0 / 0 / 0 / 1 | 0 | 141 |
| 24 | `the_scar` | 0 | 0 | 6,301 | 6,571 | 0% | 0 / 0 / 33 / 4 | 2 | 5,231 |
| 25 | `sea_town` | 0 | 3,008 | 0 | 27,197 | 0% | 0 / 2 / 0 / 6 | 1 | 289 |
| 26-30 | `frostpeak_shrine` and the four landmark trees | 0 | 0 | 0 | 0 | n/a | nothing placed | - | - |

**What it says:**
- **Thirteen places are 100% straight donor, and every one of the eight gym towns but Surge's is among them.** The
  gym towns are the places every player visits. They are also the ones built entirely from village and pack pieces
  placed as they came.
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

## For the owner to correct

Every line of the purposes table is an agent's call. These are the ones most worth a look:

1. **Every gym-town purpose.** Each turns an `ARC.md` civic role ("proposed", "they do not change trainer teams or
   structures") into a trade the town can show. The trades are: Brock's masons, Misty's rescue boats, Surge's
   relays, Erika's gardeners, Koga's trackers, Sabrina's record-keepers, Blaine's crater researchers and
   Giovanni's garrison.
2. **Brock's landmark is a crane, not a tower:** a builders' town says so with the tool it builds with.
3. **Giovanni's town as a garrison.** "Civil defender" read as soldiers, supplies and a beacon. It is not read as a
   fortress: the gym is already the gate.
4. **Frostpeak shrine's purpose is drafted, for Codex.** No brief says whose shrine it is.
5. **Hometown and the League are left undressed on purpose** (pasted by design, above).
6. **The ranking's tie-break.** Thirteen places tie at 100%. Placement count decides among them, so bigger
   all-donor towns rank as more pasted.
