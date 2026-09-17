# Regional Side Events

**Status:** Proposed narrative and encounter catalog. These are small optional
scenes that make settlements and routes feel inhabited. They do not gate gyms,
routes, the Rift, or the League. Detailed prototypes live in `events/`.

## Event principles

1. Most events should take 2–8 minutes. A few named set pieces, such as the
   ghost mansion, may take longer.
2. Each event begins with a person or Pokémon doing something visible. The
   player should not need a quest-board paragraph to understand the problem.
3. Rewards are useful, memorable, and optional. No side event gives a required
   progression flag.
4. Authored Pokémon should not join normal ambient spawn pressure. Use static
   encounters, NPC actors, or tightly bounded event spawns after the relevant
   mechanic is proven.
5. Shared-world scenery may change once, but dialogue and rewards should be
   tracked per player where practical. Multiplayer behavior must be decided
   before implementation.
6. A joke may be long because the player chooses to stay with it. Leaving and
   returning must preserve progress rather than restarting a long monologue.

## Detailed event packages

| Scope | Place | State | Detailed design |
| --- | --- | --- | --- |
| `EVT-PALLET-CRUSHED-HOUSE` | `hometown`, centre (1462, 5293) | Approved concept; exact house coordinate and ruin layout needed | [`events/PALLET_CRUSHED_HOUSE.md`](events/PALLET_CRUSHED_HOUSE.md) |
| `EVT-ROUTE1-GASTLY-FAMILY` | Pallet-to-Brock route, (1462, 5293) to (1743, 3628) | Mansion site needed; donor candidates identified | [`events/ROUTE1_GASTLY_MANSION.md`](events/ROUTE1_GASTLY_MANSION.md) |
| `EVT-ROUTE1-THIRSTY-STRANGER` | Pallet-to-Brock route, (1462, 5293) to (1743, 3628) | Hut site and accepted item IDs needed | [`events/ROUTE1_THIRSTY_STRANGER.md`](events/ROUTE1_THIRSTY_STRANGER.md) |
| Pallet through Gym 3 | Pallet, Routes 1–3, Brock, Misty, and Surge | Fourteen-event package designed; placement and technical proofs needed | [`events/EARLY_GAME_ENCOUNTERS.md`](events/EARLY_GAME_ENCOUNTERS.md) |
| Expanded early event bank | Same early-game path | Twenty-eight additional small scenes designed; total is 42 through Gym 3 | [`events/EARLY_GAME_EVENT_BANK.md`](events/EARLY_GAME_EVENT_BANK.md) |
| Gyms 4–6 event bank | Surge-to-Erika through Sabrina | Thirty-six route and town events designed; placement and technical proofs needed | [`events/MIDGAME_EVENT_BANK.md`](events/MIDGAME_EVENT_BANK.md) |

## Pallet damage cluster

Pallet should contain **three visibly damaged homes** at its exchanged edge.
They make the Worldshift personal before the player receives a technical
explanation.

- **House A — the couple:** crushed roof and blocked interior; the husband is
  outside and the wife is alive inside. This is the detailed dialogue event.
- **House B — the salvage line:** residents pass ordinary belongings from the
  damaged doorway. The player can return one family item for a small supply
  reward. No tragic reveal is required.
- **House C — the Pokémon nook:** a small Pokémon refuses to leave a sheltered
  corner until its owner brings familiar food. This is an ambient rescue scene,
  not another missing-person emergency.

All three must fit inside the measured Pallet footprint
(x 1397–1528, z 5228–5359). Their exact blocks depend on the final town layout;
none is assigned a fake coordinate here. The damage should look like debris
dropped and compressed during the exchange, with intact neighboring buildings,
so the town still reads as transported rather than generically ruined.

# Settlement event catalog

Each location below gets at least one event beyond the broader quests in
`SIDEQUESTS.md`. Coordinates are measured settlement centres and placement
anchors, not final NPC positions.

## Critical settlements

### `hometown` — Pallet Town (1462, 5293)

- **`EVT-PALLET-CRUSHED-HOUSE`: The Hundred Complaints.** A worried husband
  hides panic behind an absurd hundred-line rant about the “chud wife” who was
  “being a fungus” during their last argument. The player checks the house,
  finds her alive, and receives her Miracle Seed wedding charm.
- **`EVT-PALLET-SALVAGE-LINE`: Not Everything Is Lore.** Help residents sort a
  kettle, fishing rod, child’s drawing, and Poké Ball case recovered from House
  B. Reward: early supplies and one local character callback later.
- **`EVT-PALLET-CORNER-MON`: Familiar Smell.** Bring familiar food from
  Pallet to coax an owned Lillipup from House C. Reward: a berry bundle; the
  rescued Lillipup remains with its owner.

- **`EVT-PALLET-FENCE-LINE`: Property Damage.** Rebuild a displaced fence while
  two neighbors agree about everything except whose problem it is.
- **`EVT-PALLET-LOST-LAUNDRY`: Not Ours.** Return familiar laundry and preserve
  one unexplained shirt from outside Pallet.
- **`EVT-PALLET-PIDGEY-POST`: Same Roof, Wrong Sky.** Add colored roof markers
  so a courier Pidgey can relearn its route against the changed horizon.
- **`EVT-PALLET-BULBASAUR-BOX`: Wrong Side of the Sun.** Help an owned Bulbasaur
  move a familiar planter out of the town's new shadow.

### `gym1_town` — Brock’s town (1743, 3628)

- **`EVT-G1-MACHOP-SHIFT`: One More Beam.** A Machop helping Brock’s crews will
  not stop working after the humans take a break. Restore the missing support
  brace and ring the work bell again. Reward: building supplies and a separate
  Machop encounter lead.
- **`EVT-G1-PEBBLE-LEAGUE`: Little League.** Children use tame Roggenrola as a
  precision rolling game. The player joins a short target challenge. Reward: a
  local ribbon cosmetic and rematch score.

- **`EVT-G1-SANDSHREW-BATH`: Reserved Pile.** Build a second dust bath so
  Sandshrew voluntarily leaves the masons' mortar sand.
- **`EVT-G1-ONIX-SHADE`: Twenty Feet of Break Time.** Extend a work tarp over a
  crew Onix without blocking the quarry road.
- **`EVT-G1-FOSSIL-CASTS`: Extremely Ancient Plaster.** Separate museum casts
  from ordinary rocks and one very suspicious mug handle.
- **`EVT-G1-SHUCKLE-PRESS`: Do Not Rush It.** Select the berry batch that has
  actually rested long enough instead of forcing Shuckle's process.

### `gym2_town` — Misty’s town (1605, 2801)

- **`EVT-G2-PSYDUCK-LAUNCH`: Docked by a Headache.** A Psyduck sits on the only
  boat ramp and refuses to move. Find a quiet spot or a calming berry rather
  than battling it. Reward: water-travel supplies.
- **`EVT-G2-POLIWAG-COUNT`: One Ripple Short.** A swimming teacher keeps
  counting one fewer Poliwag after every circuit. The missing one is asleep in
  a boat. Reward: a curated Poliwag encounter and a funny class photo item.

- **`EVT-G2-AZURILL-ECHO`: One Echo Too Many.** Use Azurill's bounce echoes
  to locate a washed-out void beneath the town square.
- **`EVT-G2-CORPHISH-TOOLS`: Borrowed Forever.** Trade shiny washers for the
  mechanic's neatly sorted tools.
- **`EVT-G2-FINNEON-LAMPS`: Lights Below.** Aim reflectors so Finneon's glow
  reaches shaded dock markers.
- **`EVT-G2-SHELLOS-PAINT`: Fresh Coat.** Follow colored Shellos tracks
  through a pottery yard to identify glaze for a public fountain sign.

### `gym3_town` — Surge’s town (1688, 1410)

- **`EVT-G3-MAGNEMITE-BOLTS`: Magnetic Personality.** Magnemite keep carrying
  Surge’s loose fasteners to the same roof. Redirect them with scrap metal.
  Reward: electrical crafting supplies.
- **`EVT-G3-KITE-LINE`: Higher Than the Signal.** A resident wants to fly a kite
  from the exposed shelf without sending it toward Surge's signal array on the
  Vessu shoulder above town. Choose a safe launch wind.
  Reward: mountain-weather notes and a cosmetic kite token.

- **`EVT-G3-PLUSLE-MINUN-GRID`: Same Time, Please.** Synchronize paired switches
  so Plusle and Minun stop undoing each other's work.
- **`EVT-G3-SKIDDO-ROOF`: Rooftop Grazing.** Build a lower herb rack so an
  owned Skiddo leaves a terrace garden's dangerous edge.
- **`EVT-G3-ELECTRIKE-CABLE`: Inspection Run.** Follow Electrike's repeated lap
  to find a cable tag reacting to the signal pulses.
- **`EVT-G3-EMOLGA-WINDSOCK`: Unauthorized Upgrade.** Trade safe glide markers
  for the bright strips Emolga took from the town windsock.

## Route events through Gym 3

Detailed core flows are in
[`events/EARLY_GAME_ENCOUNTERS.md`](events/EARLY_GAME_ENCOUNTERS.md). The
expanded small-event specifications are in
[`events/EARLY_GAME_EVENT_BANK.md`](events/EARLY_GAME_EVENT_BANK.md).

### Route 1 — Pallet to Brock

- **`EVT-ROUTE1-GASTLY-FAMILY`: Lost in the House.** Lead a frightened Gastly
  through an abandoned mansion to find its parent.
- **`EVT-ROUTE1-THIRSTY-STRANGER`: The Thirsty Stranger.** Bring water to a
  familiar-looking man who is definitely not Tupac.
- **`EVT-ROUTE1-CATERPIE-CROSSING`: Green Traffic.** Create a leaf-covered
  crossing beside the road for a slow Caterpie line.
- **`EVT-ROUTE1-RATTATA-PICNIC`: Lunch Tax.** Follow crumbs to recover a neatly
  unwrapped picnic lunch.
- **`EVT-ROUTE1-BUG-NET`: Catch and Release the Net.** Free a Metapod from a net
  that appears to be moving by itself.
- **`EVT-ROUTE1-SENTRET-WATCH`: The Second Lookout.** Follow the mirrored signals from two Sentret to a dropped satchel.

### Route 2 — Brock to Misty

- **`EVT-ROUTE2-ROLLAWAY-GEODUDE`: Downhill From Here.** Follow an escaped
  handcart downhill and discover that the missing Geodude stopped it before it
  reached Lake Viltri.
- **`EVT-ROUTE2-BONSLY-MILESTONE`: Very Convincing Tree.** Recover the real
  route marker after a Bonsly imitates it and walks away.
- **`EVT-ROUTE2-BELLSPROUT-GAUGE`: Chance of Plants.** Move Bellsprout from a
  rain gauge into a better damp-soil patch.
- **`EVT-ROUTE2-NINCADA-ROAD`: Quiet Underfoot.** Mark a hollow side path so
  traffic stops crossing a Nincada burrow.
- **`EVT-ROUTE2-MUDBRAY-BOOT`: Keep the Other One.** Use a mud patch to remove a
  hiker's boot from Mudbray without frightening it.

### Route 3 — Misty to Surge

- **`EVT-ROUTE3-CREEK-WOOPER`: The Pond's Edge.** At the pond shore near
  the Nosepass signs, recover a supply crate without trampling a Wooper feeding
  patch. The controlled Wooper encounter is an optional team-building reward
  before Surge.
- **`EVT-ROUTE3-NOSEPASS-SIGNS`: North Keeps Moving.** At (2203, 1609), repair
  trail signs that rotate during signal pulses while a Nosepass turns toward
  the mast of Surge's signal array instead of north. The array must stay
  visible from the signs; the build constraint is in the detailed spec.
- **`EVT-ROUTE3-MAREEP-SHELTER`: Static in the Rain.** On an exposed switchback
  of the Tri Peaks grade, clear a safe route from a metal trail frame to stone
  cover.
- **`EVT-ROUTE3-SPOINK-PEARL`: Do Not Stop Bouncing.** Recover Spoink's pearl
  while giving it a safe place to keep moving.
- **`EVT-ROUTE3-SWABLU-NEST`: Blue Thread.** Exchange soft nesting fiber for a
  route flag the Swablu used to reinforce their nest.
- **`EVT-ROUTE3-SABLEYE-REFLECTORS`: Shiny Way Up.** Trade polished stones for
  stolen trail reflectors and re-mark the switchbacks through a rock cut on the
  climb.

The last stretch into Surge's town, where the shelf lip reveals the summits, is
kept free of events.

### `gym4_town` — Erika’s town (4309, 1555)

- **`EVT-G4-ODDISH-BEDS`: The Garden Changed Rows.** Oddish migrate between the
  native and Compact family gardens every night. Discover that both sides are
  feeding them. Reward: herbs and a peaceful Oddish encounter.
- **`EVT-G4-COMBEE-HOME`: Three Votes, One Hive.** A Combee swarm repeatedly
  rejects new hive sites. The player tests shade, flowers, and distance from
  foot traffic. Reward: honey and an encounter lead.

- **`EVT-G4-SEED-LIBRARY`: Same Name, Different Plant.** Sort native and
  Compact seed packets by plant and origin without declaring one shared name
  correct.
- **`EVT-G4-ROSERIA-RIBBONS`: Pollinator's Route.** Follow Roselia's moved
  survey ribbons to map the garden's real pollination path.
- **`EVT-G4-SEWADDLE-CANOPY`: Hemmed In.** Add a proper cloth anchor so Sewaddle
  stop stitching a refugee canopy shut.
- **`EVT-G4-TANGELA-FOOTPATH`: Preferred Shortcut.** Move a little-used service
  path around the damp patch Tangela keep reclaiming.

### `gym5_town` — Koga’s town (4646, 2446)

- **`EVT-G5-CROAGUNK-CURE`: Bad Medicine Face.** A Croagunk keeps stealing
  antidotes because it likes the bottles, not because it is poisoned. Recover
  the supplies without cornering it. Reward: antidotes and a Croagunk lead.
- **`EVT-G5-NINCADA-TRAIL`: Holes in a Straight Line.** Fresh Nincada burrows
  trace one abandoned Compact anchor boundary. Reward: tracker supplies and a
  small piece of nonessential lore.

- **`EVT-G5-GRIMER-FILTER`: The Clean Side.** Clear upstream cloth from a reed
  filter instead of blaming the Grimer sunning beside it.
- **`EVT-G5-VENONAT-LANTERNS`: Purple Glass.** Spread Venonat away from a
  medicine path by adding purple covers to safer lamps.
- **`EVT-G5-WOOPER-SLUICE`: Mud Where It Belongs.** Open a side basin so Wooper
  move their excellent pond away from an herb-drying yard.
- **`EVT-G5-SKORUPI-BASKET`: Handle With Gloves.** Use fragrant herbs to coax
  Skorupi out from beneath a moving gathering basket.

### `gym6_town` — Sabrina’s town (6196, 3398)

- **`EVT-G6-SLOWPOKE-FERRY`: The Ferry Is Thinking.** A Slowpoke chosen as a
  ceremonial launch guest will not step onto the boat. The player can wait,
  offer food, or move the ceremony around it. Reward: a patience-themed charm.
- **`EVT-G6-DREAM-SKETCH`: Someone Else’s Party.** A child sketches one of the
  player’s party Pokémon before seeing it. Sabrina treats it as ordinary local
  sensitivity rather than prophecy. Reward: a personalized sketch cosmetic.

- **`EVT-G6-ABRA-QUEUE`: Back of the Line.** Rearrange one service turn around
  an Abra that teleports backward whenever its number is called.
- **`EVT-G6-MIME-JR-CROSSING`: The Wall Is Real Enough.** Turn Mime Jr.'s
  invisible traffic warning into a real cart-stop signal.
- **`EVT-G6-CHIMECHO-BELL`: One Note Underwater.** Follow Chimecho harmonics to
  a hand bell beneath the dock.
- **`EVT-G6-ASTER-LANTERN`: A Window for Home.** Help Jo Aster place a family
  lantern where the refugee lodging and lakeshore can both see it.

## Route events for Gyms 4–6

Detailed specifications are in
[`events/MIDGAME_EVENT_BANK.md`](events/MIDGAME_EVENT_BANK.md).

### Route 4 — Surge to Erika

- **`EVT-R4-MERIAN-DELIBIRD`: Wrong Hut Again.** Correct the trail marker for
  a parcel labeled only with an unfamiliar three-arch symbol.
- **`EVT-R4-ABSOL-WARNING`: Before the Wind.** Read the bent grass and secure
  a travel camp before the gust that an Absol came to warn about.
- **`EVT-R4-DEERLING-CROSSING`: Six Seasons at Once.** Give a mixed Deerling
  herd a neutral crossing instead of forcing one habitat label onto it.
- **`EVT-R4-APPLIN-CART`: One Apple Too Heavy.** Find the Applin shifting among
  produce crates and offer it a safe basket.
- **`EVT-R4-GREEDENT-CACHE`: Emergency Means Later.** Redirect Greedent's cache
  away from the sealed public ration shelf.
- **`EVT-R4-MAP-SEAM`: Both Maps Are Right.** Mark shared physical landmarks on
  a native map and a Compact survey without declaring either false.

### Route 5 — Erika to Koga

- **`EVT-R5-SHROOMISH-RING`: Back Where You Started.** Use moss and slope to
  restore trail arrows moved inward around a Shroomish ring.
- **`EVT-R5-ARIADOS-WEB`: High Bridge.** Raise one loose Ariados strand while
  preserving the web catching branches above the path.
- **`EVT-R5-PARAS-BARK`: The Correct Dead Tree.** Harvest medicinal fungus from
  a fallen, unoccupied log rather than a Paras habitat.
- **`EVT-R5-VENIPEDE-LOG`: Queue Underneath.** Build a human crossing beside the
  hollow log used by a line of Venipede.
- **`EVT-R5-HERB-MARKERS`: Wrong Red Ribbon.** Reidentify medicinal plants after
  an apprentice marks every candidate as important.
- **`EVT-R5-ZORUA-TRACKS`: Too Many Walkers.** Follow multiplying footprints
  only far enough to offer a curious Zorua a harmless cloth marker.

### Route 6 — Koga to Sabrina

- **`EVT-R6-BERGMITE-REFLECTION`: False Trail Light.** Add a second reflector
  color so Bergmite reflections do not appear to continue onto the ice.
- **`EVT-R6-SNORUNT-CAIRN`: Snowball Offering.** Build Snorunt their own cairn
  beside the stone travel marker they keep rebuilding with snowballs.
- **`EVT-R6-QUAGSIRE-BOARDWALK`: Missing Board, Present Quagsire.** Repair a
  boardwalk gap beside the Quagsire currently filling it.
- **`EVT-R6-GLACIER-BELL`: Ice in the Mouth.** Thaw a weather bell's clapper
  with a controlled heat panel.
- **`EVT-R6-DRIFBLIM-BALLOON`: Tether Dispute.** Secure a weather balloon while
  letting Drifblim keep the bright spare ribbon.
- **`EVT-R6-MUNNA-REST`: Somebody Else's Nap.** Separate three resting travelers
  from Munna after they report the same unfamiliar dream.

### `gym7_town` — Blaine’s town (6074, 4995)

- **`EVT-G7-MAGBY-VALVE`: Too Helpful.** A Magby repeatedly reheats a safety
  valve after workers cool it. Teach it the difference between work lights.
  Reward: heat-resistant supplies and a Magby lead.
- **`EVT-G7-SLUGMA-GLASS`: Moving Furnace.** A glassworker’s Slugma wanders off
  midway through a batch. Guide it back along a safe route. Reward: decorative
  glass and a Fire-type held-item candidate.

### `gym8_town` — Giovanni’s town (3647, 6497)

- **`EVT-G8-MEOWTH-LEDGER`: Exact Change.** A Meowth steals only coins from one
  side of a relief ledger. Following it uncovers a bookkeeping mistake, not a
  criminal plot. Reward: corrected payment and an Amulet Coin candidate.
- **`EVT-G8-SANDYGAST-WALL`: The Fort That Stayed.** Children’s Sandygast wall
  has become part of a real storm barrier. Help reinforce it without capturing
  the Pokémon. Reward: coastal supplies and a photo keepsake.

### `league` — Rift head (3297, 2603)

- **`EVT-LEAGUE-RIBBON-WIND`: The First Ceremony.** A rookie attendant loses
  the recognition ribbons to the Rift wind. Recover them around the plateau.
  Reward: the player’s own ribbon cosmetic.
- **`EVT-LEAGUE-OLD-TEAM`: Still Nervous.** A veteran trainer admits they are
  more frightened of the repaired world than of a battle. An optional rematch
  helps them decide what to do next. Reward: League supplies.

## Optional major towns

### `sunset_west` — harbour town (1716, 7298)

- **`EVT-SUNSET-WINGULL`: Return Address.** A Wingull courier keeps bringing
  every parcel back to the harbour. Pair markings with the correct boats.
  Reward: sea-route notes and a Wingull lead.
- **`EVT-SUNSET-ANCHOR`: The Anchor That Walked.** A Crabrawler has adopted a
  small anchor as training equipment. Trade it a safer weight. Reward: harbor
  supplies.

### `northlight` — frozen research town (7265, 1556)

- **`EVT-NORTH-CONKELDURR`: Timber Shift.** A Conkeldurr repairing the field
  station needs suitable wood carried from town stores through deep snow. The
  player helps fetch, sort, and place beams. Reward: cold-weather supplies and
  a Conkeldurr rematch.
- **`EVT-NORTH-SNOM-WINDOW`: Warm Glass.** Snom gather on the observatory window
  and block the night reading. Create a nearby cold lamp that attracts them
  without harming them. Reward: an aurora cosmetic and Snom encounter lead.

### `mining_town` (6633, 5716)

- **`EVT-MINE-GEODUDE`: Downhill Since Breakfast.** A worker’s Geodude curled
  up to rest, began rolling, and never stopped. Follow impact marks and stop it
  with a safe barrier or a Pokémon move. Reward: ore, a Hard Stone candidate,
  and a Geodude encounter.
- **`EVT-MINE-DRILBUR`: Wrong Side of the Fall.** A miner and Drilbur are safe
  behind a small cave-in but cannot move their loaded cart. Open a second route
  or assemble a party that can shift debris. Reward: fossil-lab service and
  mining supplies.

### `displaced_city` (2969, 1710)

- **`EVT-CITY-CHERRIM`: Noon on a Timer.** Cherrim gather beneath one false-sky
  panel and react when its lighting schedule slips. Help gardeners recalibrate
  the day. Reward: cultivation supplies and a Cherrim lead.
- **`EVT-CITY-BANETTE`: Returned Property.** A Banette carries an object from a
  family that lived on the summit. Find the owner without treating the Pokémon
  as a thief. Reward: a city keepsake and Banette encounter lead.

### `tea_town` (2654, 3605)

- **`EVT-TEA-POLTCHAGEIST`: Cupboard Union.** Several Poltchageist refuse to
  leave the good cups until the owner stops serving from cracked ones. Reward:
  tea supplies and a Poltchageist encounter.
- **`EVT-TEA-TASTE`: Too Many Experts.** Three residents give contradictory
  instructions for brewing one pot. The player chooses a method and everyone
  claims that was theirs. Reward: a tea recipe.

## Rest stops and outposts

### `merian_hut` (2813, 1102)

Merian hut's Delibird parcel scene is cataloged under Route 4 and specified
in the Gym 4–6 event bank.

### `gorge_hamlet` (6814, 4367)

- **`EVT-GORGE-TIMBURR`: Bridge Rhythm.** A Timburr crew works faster when the
  player matches their carrying pattern. Reward: bridge materials and rest.

### `tableland_stop` (4876, 5729)

- **`EVT-TABLE-TRAPINCH`: One Boot Missing.** A Trapinch has swallowed a
  prospector’s boot into its pit. Lure it out with movement, not damage.
  Reward: a mineral sample and Trapinch lead.

### `rift_rim_stop` (3734, 3951)

- **`EVT-RIM-NOSEPASS`: North Is Having a Day.** A Nosepass points toward the
  Rift during small pulses. Record the changes for the rangers. Reward: a
  compass-themed cosmetic.

### `relic_island` (1092, 5532)

- **`EVT-RELIC-HOPPIP`: Same Wind, Wrong Shore.** Hoppip caught in the exchange
  circle the house whenever wind blows toward Pallet. Reward: a Pallet keepsake
  and Hoppip encounter.

### `the_scar` (2110, 950)

- **`EVT-SCAR-CARBINK`: Foundation Lights.** Carbink illuminate surviving
  foundations at dusk, revealing one missing street line. Reward: city map
  detail and a Carbink lead.

### `viltri_light` (550, 4518)

- **`EVT-LIGHT-LAMPENT`: Borrowed Flame.** A Lampent keeps replacing the
  lighthouse flame with its own. Decide whether the keeper should work with it.
  Reward: lighthouse cosmetic and Lampent lead.

### `rift_dig_camp` (3106, 3314)

- **`EVT-DIG-ARON`: Brush Collector.** Aron has carried every steel-handled
  brush into one neat pile. Trade wooden tools for them. Reward: archaeology
  supplies and an Aron lead.

### `frostpeak_shrine` (682, 380)

- **`EVT-FROST-SNORUNT`: Shared Offering.** Snorunt replace every shrine
  offering with snowballs. Discover which offering they leave untouched.
  Reward: a shrine cosmetic and Snorunt lead.

### `jungle_ruins` (5160, 7463)

- **`EVT-JUNGLE-AIPOM`: Better Rubbing.** An Aipom copies the archaeologist’s
  motions and produces a clearer wall rubbing by accident. Reward: the rubbing
  and an Aipom encounter lead.

# Placement and implementation queue

1. Place three damaged Pallet homes inside the accepted town layout and assign
   exact house, husband, wife, salvage, and Pokémon coordinates.
2. Choose a mansion site on the Pallet-to-Brock route. `minecraft:mansion` is
   an unverified functional donor candidate; whether the active Cobblemon 1.8
   pack associates it with usable mansion spawn presets must be tested.
   `repurposed_structures:mansion_birch` is a visual donor candidate for the
   birch plateau. Verify whichever placement method is chosen preserves or
   replaces the desired spawn behavior.
3. Choose a small hut site on the same route and a reusable donor structure.
4. Verify static Pokémon actors, follow behavior, per-player dialogue state,
   once-per-player rewards, and shared scenery before implementing event data.
5. Verify actual item IDs for Miracle Seed, Spell Tag, Black Glasses, Fresh
   Water or a Pokémon water bottle, and any custom-named rewards.
