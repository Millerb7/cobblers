# Claude Build Handoff — Routes 1–3

This is the physical and runtime build list for the accepted early-route
events and trainers. Coordinates are `(x, z)` unless Y is shown. Route distance
is walked distance from that route's origin in `data/routes.json`.

Do not move route polylines to fit these scenes. If a footprint cannot use the
listed site, report the collision and move the scene only after re-measuring
its route distance. Do not place anything on Route 3's final shelf lip.

## Shared runtime contract

- Every side event is optional and per player.
- Every mutable field is under `quest.<quest_id>.*`; no event writes a
  `flags.*` mainline field.
- Persist `dialogue_cursor` after every node or short response segment.
- Shared blocks and static actors may show one world state, but completion and
  rewards remain independently replayable and claimable.
- Route trainer battles are singles and give no item reward in this pass.
- A trainer's `win` dialogue ID means **the player won**; `loss` means **the
  player lost**.
- Exact trainer teams, levels, moves, dialogue text, RCT payloads, and proposed
  coordinates are generated into `data/trainers.json` from
  `docs/story/TRAINER_RULES.json`.

## Route 1 events

### `EVT-ROUTE1-GASTLY-FAMILY`

- **Route position:** spur entrance `(1468, 5018)`, route distance `284.9`,
  route ground `y118.6`; mansion footprint `x1614..1645, z5022..5045`, floor
  `y114`, centre `(1630, 5034)`, 162.8 blocks from the route.
- **Physical build:** keep the authored manor from `tools/route1_mansion.py`;
  add a signed side trail, foyer hiding marker, five player-local checkpoint
  markers, Haunter and Gengar final-room actor markers, and one non-loot cache
  prop. Do not add a Rift ring, pulse machine, or explanatory anomaly.
- **Dialogue:** add `dlg_route1_gastly_family` from
  `events/ROUTE1_GASTLY_MANSION.md`; Pip asks for help, each checkpoint has one
  short observation, and the final room has the family reunion.
- **Quest:** add `evt_route1_gastly_family`.
- **Fields written:** `quest.evt_route1_gastly_family.started`,
  `.checkpoint` (`foyer|stairs|service|library|landing|family`),
  `.reward_claimed`, `.completed`, `.dialogue_cursor`.
- **Fields read:** only the five fields above.
- **Failure rule:** leaving or disconnecting restores that player's Gastly to
  their saved checkpoint. One player never advances another player's actor.

### `EVT-ROUTE1-RATTATA-PICNIC`

- **Route position:** basket `(1454, 4828)`, route distance `556.6`, three
  blocks from route point `(1454, 4831)`, route ground `y121.6`.
- **Physical build:** one blanket, open basket, three hiding props within 12
  blocks, crumb trail to one prop, and a berry stump off the walking line.
- **Dialogue:** `dlg_route1_rattata_picnic`: owner opening, one line at each
  false hiding place, crumb discovery, lunch return, repeat line.
- **Quest:** `evt_route1_rattata_picnic`.
- **Fields written:** `quest.evt_route1_rattata_picnic.started`, `.lunch_found`,
  `.reward_claimed`, `.completed`, `.dialogue_cursor`.
- **Fields read:** only the five fields above.
- **Actors:** use ordinary Route 1 Rattata; any posed Rattata is noncapture and
  does not alter ambient spawn weight.

### `EVT-ROUTE1-THIRSTY-STRANGER`

- **Route position:** hut entrance `(1509, 4469)`, route distance `1039.4`,
  route ground `y122.6`; put the small footprint east of the road with centre
  `(1521, 4461)` so it does not overlap the corridor.
- **Physical build:** 9×7 hut maximum, table, empty cup, bedroll, decorative
  chest, and no water source. Face the entrance toward `(1509, 4469)`.
- **Dialogue and quest:** existing `dlg_route1_thirsty_stranger` and
  `evt_route1_thirsty_stranger`; do not rewrite the proven flow.
- **Fields written/read:** the existing `.started`, `.water_delivered`,
  `.reward_claimed`, `.completed`, `.dialogue_cursor` fields.
- **Reason for move:** the earlier `(1410, 4600)` suggestion sits beside the
  Celebi sapling. This site is about 210 walked blocks later.

### Protected Route 1 discovery — Celebi

- **Position:** `(1380, 4628)`, nearest route distance `828.8`, 9.8 blocks from
  route point `(1389, 4624)`.
- **Build rule:** preserve the sleeping Celebi and sapling exactly. No Route 1
  NPC names the wake item, no side event writes Celebi state, and the nearby
  road remains quiet enough that the player notices it.

### `EVT-ROUTE1-FIRST-CAST`

- **Shore position:** jetty anchor `(1066, 5349)`, terrain about `y62`, with
  the deck at `y64`; 399.9 blocks from Route 1's origin at `(1462, 5293)`.
  This is an intentional optional coast spur, not a replacement for the
  critical path.
- **Physical build:** a 5×9 timber jetty on piles, compact tackle rack or
  open shelter, one stool, and a signed footpath from Pallet's west side. Keep
  the silhouette small and do not add Relic Island, Rift, or Hoopa exposition.
- **Dialogue:** add `dlg_route1_first_cast`; a local fisher shows the player
  that this is usable water, hands over one basic rod, and points out that a
  patient cast can be worthwhile without naming a rare catch.
- **Quest:** add `evt_route1_first_cast`.
- **Fields written:** `quest.evt_route1_first_cast.started`, `.rod_claimed`,
  `.completed`, `.dialogue_cursor`.
- **Reward:** one `minecraft:fishing_rod` per player, once. Do not substitute
  Cobblemon's Poké Rod.
- **Proof still required:** observe the actual early fishing pool and measure
  the effect of Only Bottle Caps adding a 3% silver Bottle Cap chance to
  vanilla treasure. Habitat Block fishing replacement is not yet runtime
  proven.

## Route 2 events

### `EVT-ROUTE2-ROLLAWAY-GEODUDE`

- **Route position:** miner/cart at `(1756, 3528)`, route distance `105.4`,
  route ground `y137.7`; stopped cart and Geodude around `(1767, 3517)`, route
  distance `120.9`, ground `y137.2`.
- **Physical build:** empty brake position, 15-block wheel rut, split sample
  sack, chipped boulder, one stopping tree, resettable brake interaction, and
  safe two-block walking clearance around the route.
- **Dialogue:** `dlg_route2_rollaway_geodude`: miner's two-line opening,
  inspection lines for three clues, “It did not run away. It caught the cart,”
  return and repeat lines.
- **Quest:** `evt_route2_rollaway_geodude`.
- **Fields written:** `quest.evt_route2_rollaway_geodude.started`,
  `.clue_rut`, `.clue_sack`, `.clue_boulder`, `.brake_secured`,
  `.reward_claimed`, `.completed`, `.dialogue_cursor`.
- **Fields read:** only those fields; each clue is a boolean so the proven
  schema needs no counter operation.
- **Lore rule:** this is a work accident from Brock's stone country. It is not
  caused by the Worldshift or the Haven Compact.

### `EVT-ROUTE2-VILTRI-SOUNDING`

- **Route position:** shore station `(1779, 3011)`, route distance `636.1`,
  route ground `y113.7`, after the route enters Lake Viltri Hollow.
- **Physical build:** 7×9 shore platform, three depth staffs at clearly
  different water shelves, one floating gauge on a short tether, a Corphish
  claw-mark prop, and an uninterrupted lake view. Keep the critical road open.
- **Dialogue:** add `dlg_route2_viltri_sounding`.
  - Opening: “First time at Viltri? Then look at the banks before the map.”
  - After wrong staff: “Deep water leaves a different line. Try the shelf the
    Lotad are using.”
  - After all staffs: “Same lake, three depths. That is why one path never
    tells you the whole shore.”
  - At the gauge: “Corphish did not steal it. It improved the tether until it
    came loose.”
  - Completion: “Now the marker agrees with the water. Welcome to Viltri.”
- **Quest:** add `evt_route2_viltri_sounding`.
- **Fields written:** `quest.evt_route2_viltri_sounding.started`,
  `.staff_shallow`, `.staff_middle`, `.staff_deep`, `.gauge_reset`,
  `.reward_claimed`, `.completed`, `.dialogue_cursor`.
- **Fields read:** only those fields; each staff is a boolean so the proven
  schema needs no counter operation.
- **Actors:** ambient Lotad/Lombre on the shelf and one posed noncapture
  Corphish; no special species reward.

### `EVT-VILTRI-NORTH-BANK` — shared Route 2/3 shore stop

- **Shore position:** `(1604, 3068)`, terrain `y104.4`, beside Lake Viltri's
  `y103` water. Its Route 2 anchor is `(1779, 3011)` at distance `636.1`; the
  measured shore spur is 184.1 blocks. It is also 267 blocks from Route 3's
  origin at `(1605, 2801)`, so players may find it before Misty or revisit it
  while starting the mountain leg.
- **Physical build:** a 7×9 timber-and-stone bank platform, short ring trail
  from the settled road, net rack, and either a beached skiff or tackle box.
  Keep it visually and physically separate from the existing sounding station.
- **Trainer:** place `route_02_shore_trainer_01`, the North Bank Angler, on the
  platform with enough clear bank for a battle interaction.
- **Dialogue:** add `dlg_viltri_north_bank`; the angler explains that seeing
  Viltri from the south road is not the same as knowing its north bank, then
  offers a battle.
- **Quest:** add `evt_viltri_north_bank`.
- **Fields written:** `quest.evt_viltri_north_bank.started`,
  `.trainer_defeated`, `.reward_claimed`, `.completed`, `.dialogue_cursor`.
- **Reward:** after a verified player win, grant one `cobblemon:lure_ball` per
  player through the quest reward path, not the shared RCT bag.

## Route 3 events

### `EVT-ROUTE3-CREEK-WOOPER`

- **Route position:** shore site `(2204, 1580)`, nearest route point
  `(2199, 1606)`, route distance `1469.0`, route ground `y123.9`, offset 26.5.
- **Physical build:** three visually distinct shore approaches, shallow crate,
  feeding-patch particles or props, dry lichen stones, and a small controlled
  encounter pool. Share path and clearing work with the Nosepass site.
- **Dialogue:** `dlg_route3_creek_wooper`: courier opening, one observation per
  approach, safe-route confirmation, crate return, repeat line.
- **Quest:** `evt_route3_creek_wooper`.
- **Fields written:** `quest.evt_route3_creek_wooper.started`,
  `.safe_path_found`, `.crate_recovered`, `.encounter_claimed`, `.completed`,
  `.dialogue_cursor`.
- **Fields read:** only those fields. Do not create `SQ-G3-02` or any return
  objective from Surge.

### `EVT-ROUTE3-NOSEPASS-SIGNS`

- **Route position:** signs `(2186, 1606)`, nearest route point `(2199, 1606)`,
  route distance `1469.0`, route ground `y123.9`, offset 13; array mast
  `(1928, 284, 1248)`.
- **Physical build:** the measured 60×16 directional sightline, three signs
  with painted ground marks, two loose-fastener states, nonmetal wedges,
  Nosepass actor, and a visible receive-pulse cue on the existing mast. Keep
  the elder at `(2236, 1622)` outside the 40-block clearing.
- **Dialogue:** `dlg_route3_nosepass_signs`.
  - Opening: “The marks are right. The signs moved after the mast flashed.”
  - Inspection: “The metal is humming. Use the wood wedges.”
  - Pulse: “There. The mast caught something, and Nosepass caught it too.”
  - Completion: “The signs are fixed. Whatever they heard is still north-west.”
- **Quest:** `evt_route3_nosepass_signs`.
- **Fields written:** `quest.evt_route3_nosepass_signs.started`,
  `.brackets_fixed`, `.pulse_observed`, `.reward_claimed`, `.completed`,
  `.dialogue_cursor`.
- **Fields read:** only those fields. Never read or write
  `flags.surge_reveal_complete`; the event cannot identify deliberate steering.

### `EVT-ROUTE3-SWABLU-NEST`

- **Route position:** nest `(2014, 1606)`, nearest route point `(1978, 1606)`,
  route distance `1690.0`, route ground `y132.9`, offset 36 at the forest-to-
  mountain cut bank.
- **Physical build:** low cut-bank nest, torn route flag, three fallen-fiber
  props, replacement flagpole, and a sheltered bench farther uphill. The bench
  has no healing, PC, waystone, or progression function.
- **Dialogue:** `dlg_route3_swablu_nest`: guide opening, fiber observations,
  exchange, repaired-flag line, repeat line.
- **Quest:** `evt_route3_swablu_nest`.
- **Fields written:** `quest.evt_route3_swablu_nest.started`, `.fiber_placed`,
  `.flag_recovered`, `.reward_claimed`, `.completed`, `.dialogue_cursor`.
- **Fields read:** only those fields.

## Route trainers

Register one per-player boolean for each trainer:
`quest.<trainer_id>.defeated`. Pre-battle dialogue reads `false`; player-win
dialogue writes `true`; repeat interaction reads `true` and uses the win line.
Loss dialogue writes nothing. No trainer writes a mainline flag.

| ID | Name | Route distance | Exact position | Team | Levels | Physical placement |
| --- | --- | ---: | --- | --- | --- | --- |
| `route_01_trainer_01` | Trail Novice | 285 | `(1468, 119, 5018)` | Pidgey | 7 | Road shoulder at the mansion junction; preserve the spur entrance. |
| `route_01_trainer_02` | Meadow Apiarist | 733 | `(1385, 124, 4714)` | Combee, Surskit | 9, 10 | Flower boxes and two hives outside the road corridor. |
| `route_01_trainer_03` | Vale Naturalist | 1247 | `(1581, 122, 4291)` | Buizel, Surskit | 13, 14 | Dry-vale observation post; the planned River of Shrews does not exist as fishable water. |
| `route_01_trainer_04` | Plateau Guide | 1677 | `(1594, 123, 3867)` | Wooloo, Fomantis, Wingull | 15, 16, 17 | Guide post and Brock warning board. |
| `route_02_trainer_01` | Ravine Scrapper | 268 | `(1762, 133, 3372)` | Corphish | 18 | Small gravel turnout after the Geodude scene. |
| `route_02_trainer_02` | Glowbug Keeper | 486 | `(1773, 131, 3159)` | Volbeat, Illumise | 19, 20 | Two hooded lantern posts at the lake-hollow boundary. |
| `route_02_trainer_03` | Lake Surveyor | 723 | `(1774, 111, 2926)` | Lombre, Mareep, Lotad | 20, 21, 22 | Survey tripod and rain gauge after the sounding event. |
| `route_02_shore_trainer_01` | North Bank Angler | 636 anchor | `(1604, 104, 3068)` | Krabby, Shellder | 20, 21 | Optional Lake Viltri platform, 184.1 blocks from its Route 2 anchor and shared with the Route 3 start. |
| `route_03_trainer_01` | Climbing Novice | 247 | `(1747, 104, 2613)` | Rockruff | 21 | First ascent marker; clear sight line along the road. |
| `route_03_trainer_02` | Grove Ranger | 607 | `(1876, 113, 2306)` | Heracross, Noctowl | 22, 23 | Ranger lean-to outside the world-tree protection area. |
| `route_03_trainer_03` | Groundkeeper | 1029 | `(2034, 124, 1950)` | Bunnelby, Skiddo | 23, 24 | Burrow and root-cut display beside the road. |
| `route_03_trainer_04` | Signal Watcher | 1469 | `(2199, 124, 1606)` | Pachirisu, Volbeat | 25, 26 | Use the Nosepass keeper shelter; NPC stands on-route, 13 blocks from signs. |
| `route_03_trainer_05` | Vessu Ranger | 1690 | `(1978, 133, 1606)` | Wooper, Makuhita, Skiddo | 25, 26, 27 | Use the Swablu guide bench; preserve the nest 36 blocks east. |

The exact pre-, player-win-, and player-loss lines are in each generated
record's `dialogue_text`. The dialogue compiler still needs a trainer adapter
that maps the three stable IDs in `dialogue` to those lines and sets the
per-player defeat field only from a verified RCT player-win callback.

## Build order

1. Re-export and reapply the existing Route 1 mansion and route infrastructure.
2. Protect the Celebi sapling and Route 3 shelf-lip exclusion zones.
3. Build the ten event prop clusters and trainer shoulders without actors.
4. Audit walking clearance, event spacing, mansion spur access, array
   sightline, and Swablu/Nosepass tree clearances.
5. Register quest fields and compile dialogue.
6. Place static actors and RCT trainers.
7. Test each scene independently with two player records before adding rewards.

## Required proof

- Every trainer starts only its own battle and writes defeat for the initiating
  player only.
- Two players can hold different Gastly checkpoints and reconnect to them.
- The Nosepass scene never sets or bypasses Surge's mainline reveal.
- Wooper can be claimed once per player and remains optional.
- Event props remain usable after one player completes the scene.
- The First Cast rod grants once per player; the North Bank Lure Ball grants
  only after that player wins and never twice.
- Actual fishing catches and Bottle Cap treasure exposure are recorded before
  the rod event is accepted for production balance.
- All thirteen trainer movesets resolve in Cobblemon 1.8/RCT; this document does not
  claim learnset validation.
