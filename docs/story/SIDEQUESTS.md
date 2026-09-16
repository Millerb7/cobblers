# Settlement Sidequests

**Status:** Proposed for review. These are narrative quest briefs, not
implemented quest data. They add no required progression and set no gym,
chapter, crater, Rift, or champion flag.

Small ambient scenes and character encounters are cataloged separately in
[`SIDE_EVENTS.md`](SIDE_EVENTS.md), with detailed prototypes under `events/`.

## Coordinate rule

Coordinates below are block **(x, z)** anchors from `data/towns.json` and
`data/landmarks.json`. A Y value is included only where the data records one.
When a quest stays inside a settlement whose individual buildings have not
been placed, every step remains anchored to the measured town centre rather
than inventing street coordinates. Exact NPC IDs, item tables, encounters, and
structure IDs remain for later implementation.

Kinds are **LOCAL PROBLEM**, **WORLD PUZZLE**, **PLACE DISCOVERY**, and
**CHARACTER**. Every reward is optional.

# Critical settlements

## `hometown` — Pallet Town

### `SQ-HOME-01` — The Wrong Field Guide

- **Kind:** CHARACTER
- **Hook:** At Pallet centre (1462, 5293), Oak asks residents to mark what they
  remember without trying to force their stories into one answer.
- **Steps:** At (1462, 5293), collect three conflicting recollections; compare
  them with Oak's old map at the same anchor; choose which uncertainty to write
  first in the new field guide.
- **Reward:** An explorer's supply bundle and a cosmetic copy of the unfinished
  regional map.
- **Reveal:** Pallet's people share a home but do not share one explanation for
  what happened.

### `SQ-HOME-02` — A Roof Across the Water

- **Kind:** PLACE DISCOVERY
- **Hook:** A resident at (1462, 5293) spots a familiar roof offshore that does
  not appear on the old Pallet map.
- **Steps:** Leave Pallet at (1462, 5293); reach `relic_island` at
  (1092, 5532; ground 35.3); inspect the separated Pallet house; return to
  (1462, 5293) with any account of what remains.
- **Reward:** A one-time useful encounter on the island and a small keepsake
  from Pallet; exact species and item await encounter design.
- **Reveal:** Pallet's exchange sheared off fragments rather than moving one
  perfect rectangle.

## `gym1_town` — Brock's town

### `SQ-G1-01` — Where Viltri Used to Run

- **Kind:** WORLD PUZZLE
- **Hook:** A plateau builder at (1743, 3628) has stonework worn by a river that
  no longer reaches the sea.
- **Steps:** Enter `viltri_ravine` at its anchor (1100, 3600); follow the dry
  landform to `mouth_of_viltri` (613, 4306); report to `viltri_light`
  (550, 4518; ground 67.7).
- **Reward:** A lighthouse map marker, fishing supplies, and a decorative
  river-stone token.
- **Reveal:** Viltri Ravine is an old watercourse whose elevation no longer
  permits Lake Viltri to drain through it.

### `SQ-G1-02` — Load-Bearing

- **Kind:** LOCAL PROBLEM
- **Hook:** Brock's emergency crew at (1743, 3628) needs help deciding which
  damaged homes can safely shelter new arrivals.
- **Steps:** Inspect the crew's marked materials and battle three volunteer
  builders at the town centre (1743, 3628); return the test results at the same
  anchor.
- **Reward:** Building materials and access to the crew's optional training
  battles.
- **Reveal:** Brock's authority comes from practical work and public trust, not
  only his gym title.

## `gym2_town` — Misty's town

### `SQ-G2-01` — The Lake Keeps Receipts

- **Kind:** WORLD PUZZLE
- **Hook:** Misty's rescue crew at (1605, 2801) has objects recovered after
  identical pulses but from shores that should not connect.
- **Steps:** Survey `lake_viltri` at (1638, 2998; floor 75.1); compare the finds
  with records at (1605, 2801); sort local debris from exchanged material.
- **Reward:** Water-travel supplies and a choice of common held items useful in
  early battles.
- **Reveal:** Exchange effects leave material evidence even when the main
  boundary looks clean.

### `SQ-G2-02` — Viltri's Path

- **Kind:** PLACE DISCOVERY
- **Hook:** A boat worker at (1605, 2801) points out a route name that survived
  after its river did not.
- **Steps:** Travel from town (1605, 2801) to `viltris_path` (1086, 2514); find
  the place where the living watercourse and old name disagree; return to town.
- **Reward:** A regional path marker and a curated early Water- or Grass-type
  encounter, species deferred to encounter balance.
- **Reveal:** Names preserve older geography after the land itself changes.

## `gym3_town` — Surge's town

### `SQ-G3-01` — Road to Nothing

- **Kind:** PLACE DISCOVERY
- **Hook:** Surge's crew at (1847, 1262) has a road survey whose final segment
  ends in open air.
- **Steps:** Climb from (1847, 1262) to `the_scar`
  (2110, 950; ground 200); inspect the bare footprint and ended road; copy the
  orientation of the remaining foundations.
- **Reward:** A Scar map marker and a technical accessory from Surge's stores.
- **Reveal:** A settlement once stood on Mt Vessu and vanished as a whole.

### `SQ-G3-02` — The Pond Behind Clay

- **Kind:** LOCAL PROBLEM
- **Hook:** A mountain guide at (1847, 1262) has not heard from a regular field
  researcher working behind Mt Clay.
- **Steps:** Reach `pond_west_of_mt_clay` (2110, 1706; floor 93.9); find the
  research cache; return to (1847, 1262).
- **Reward:** Climbing supplies and an optional mountain encounter.
- **Reveal:** The high massif contains sheltered living pockets, not only bare
  peaks and story ruins.

## `gym4_town` — Erika's town

### `SQ-G4-01` — A Channel That Climbs

- **Kind:** WORLD PUZZLE
- **Hook:** Erika's survey records at (4309, 1555) describe water once running
  where water can no longer descend.
- **Steps:** Inspect `peak_pond_creek` at (3786, 1182); continue to
  `ravine_head_tarn` (3376, 921; floor 105); compare both ends with
  `peak_pond` (4042, 1470; floor 86.1).
- **Reward:** A set of botanical ingredients and a cosmetic field-surveyor
  badge.
- **Reveal:** The channel was moved into an impossible profile; the tarn now
  drains north instead of toward Peak Pond.

### `SQ-G4-02` — The Hollow's Guests

- **Kind:** CHARACTER
- **Hook:** At (4309, 1555), a native household and a Haven Compact family keep
  returning the same borrowed cooking pot to each other.
- **Steps:** Hear both families at (4309, 1555); choose a shared meal ingredient
  from the player's ordinary supplies; attend the meal at the same anchor.
- **Reward:** A reusable local recipe and improved optional shop stock.
- **Reveal:** Coexistence is built through mundane obligations while the larger
  political dispute remains unresolved.

### `SQ-G4-03` — The Sentinel

- **Kind:** PLACE DISCOVERY
- **Hook:** A forester at (4309, 1555) describes an old tree called the Sentinel
  beside a hidden tarn.
- **Steps:** Reach the real `ravine_head_tarn` anchor
  (3376, 921; floor 105); record the tree and water together; return to
  (4309, 1555).
- **Reward:** A rare berry or seedling and a tarn map marker.
- **Reveal:** Old-growth landmarks can preserve local memory independently of
  roads and town records.
- **Implementation limit:** The tarn is in data, but the Sentinel itself has no
  landmark ID or exact tree coordinate. This quest cannot be implemented until
  that record is added; see the gap list.

## `gym5_town` — Koga's town

### `SQ-G5-01` — Tracks That Stop

- **Kind:** WORLD PUZZLE
- **Hook:** Koga's trackers at (4646, 2446) find repeated equipment marks that
  end at bare wet ground.
- **Steps:** Compare the field edge at (4646, 2446) with `marshy_marsh`
  (5158, 2166; floor 62.9); identify which tracks belong to wildlife and which
  match abandoned Compact anchors.
- **Reward:** Marsh travel supplies and a tracker-themed cosmetic.
- **Reveal:** The Compact has tested more sites than its public teams admit.

### `SQ-G5-02` — Ice Above, Blossoms Below

- **Kind:** PLACE DISCOVERY
- **Hook:** A glacial worker at (4646, 2446) reports warm air emerging from the
  direction of the Glacial Tear.
- **Steps:** Reach `glacial_tear` at (4380, 2640); follow the safe approach to
  the `displaced_city` surface entrance (2969, 1710; ground 122); return or
  continue into the optional city once its entrance is built.
- **Reward:** The Displaced City map marker and cold-weather supplies.
- **Reveal:** The vanished summit city did not cease to exist; it survives
  beneath the glacier.

## `gym6_town` — Sabrina's town

### `SQ-G6-01` — The Marsh's Abandoned Course

- **Kind:** WORLD PUZZLE
- **Hook:** Shore keepers at (6196, 3398) disagree over whether the long dry cut
  was ever part of Lake Tilpey.
- **Steps:** Inspect `marsh_to_tilpey` (5822, 2726); compare its ends with
  `marshy_marsh` (5158, 2166; floor 62.9) and `lake_tilpey`
  (5870, 3874; floor 51.3); report at (6196, 3398).
- **Reward:** A weatherproof pack upgrade or equivalent travel utility.
- **Reveal:** The old channel cannot descend without a 31.7-block cut; the
  marsh now drains northeast.

### `SQ-G6-02` — Bridge Keepers

- **Kind:** PLACE DISCOVERY
- **Hook:** A ferrier at (6196, 3398) asks the player to carry a roster to the
  people who maintain the southern gorge crossing.
- **Steps:** Travel from (6196, 3398) to `gorge_hamlet`
  (6814, 4367; ground 112.7); deliver the roster; help the keepers update the
  crossing schedule at the same anchor.
- **Reward:** The hamlet's rest services and a bridge-keeper map marker.
- **Reveal:** Long routes remain usable because small communities maintain
  them between gym towns.

## `gym7_town` — Blaine's town

### `SQ-G7-01` — The Other Crater Workers

- **Kind:** PLACE DISCOVERY
- **Hook:** A crater researcher at (6074, 4995) asks who keeps extracting ore
  from the eastern cone during the evacuation crisis.
- **Steps:** Inspect `craters` at (6454, 5078; summit 200); continue to
  `mining_town` (6633, 5716; ground 137.3); deliver Blaine's safety notice.
- **Reward:** The Mining Town marker, ore-processing access, and a fossil lead.
- **Reveal:** The Craters support ordinary industry as well as catastrophic
  story machinery.

### `SQ-G7-02` — Cooling Line

- **Kind:** LOCAL PROBLEM
- **Hook:** Blaine's field crew at (6074, 4995) needs Pokémon capable of moving
  water, stone, or heat-safe equipment during a vent flare.
- **Steps:** Assemble a suitable party and complete a short environmental test
  at the town anchor (6074, 4995); verify the nearby crater reading at
  (6454, 5078).
- **Reward:** A Fire-resistant supply bundle and a curated utility Pokémon
  encounter, species deferred.
- **Reveal:** Team building solves civic problems outside formal battles.

## `gym8_town` — Giovanni's town

### `SQ-G8-01` — The Fourth Dry River

- **Kind:** WORLD PUZZLE
- **Hook:** A South Strand surveyor at (3647, 6497) finds a channel that leaves
  the real Arrow Lake creek and then climbs toward the coast.
- **Steps:** Inspect `arrow_lake_south` at (3202, 5622); follow the split to
  `arrow_lake_south_east_branch` (3870, 5978); return to (3647, 6497).
- **Reward:** A southern-coast map annotation and a rare held item suited to
  ground travel.
- **Reveal:** This is the fourth abandoned watercourse; land movement, rather
  than drought, made it impossible.

### `SQ-G8-02` — Names on the Boats

- **Kind:** CHARACTER
- **Hook:** At (3647, 6497), local defenders are recording boats and families
  displaced along the southern coast.
- **Steps:** Help a native resident, a Pallet arrival, and a Compact family add
  one missing name each to the record at (3647, 6497).
- **Reward:** A memorial ribbon cosmetic and improved local supply access.
- **Reveal:** The region counts losses from every side without treating one
  group's grief as proof against another's.

## `league` — Rift head

### `SQ-LEAGUE-01` — The West Spur Record

- **Kind:** PLACE DISCOVERY
- **Hook:** After the crisis, a League archivist at (3297, 2603) finds notes
  from archaeologists who were studying the Rift before the final operation.
- **Steps:** Travel to `rift_dig_camp` (3106, 3314; ground 91.7); inspect the
  nearby `rift` anchor (4160, 3920) through the camp's recorded measurements;
  return to (3297, 2603).
- **Reward:** Dig-camp access, an archaeology supply bundle, and a Registeel
  chamber lead that does not guarantee the encounter.
- **Reveal:** The Rift contains older anomalies that predate the Haven Compact.

### `SQ-LEAGUE-02` — A New Atlas

- **Kind:** CHARACTER
- **Hook:** Maren begins a registry at (3297, 2603) after the League recognizes
  the player.
- **Steps:** Add accounts from any three already discovered settlements; bring
  them to (3297, 2603); choose whether the first volume organizes entries by
  origin, present home, or missing place.
- **Reward:** A cosmetic atlas and optional map markers for settlements already
  visited.
- **Reveal:** Repair begins by recording people without reducing them to a
  single world of origin.

# Optional major towns

## `sunset_west` — harbour town

### `SQ-SUNSET-01` — A Boat for the Outer Sea

- **Kind:** LOCAL PROBLEM
- **Hook:** Boat builders at (1716, 7298) have a seaworthy hull but no crew
  willing to make the first post-Worldshift charting run.
- **Steps:** Complete a navigation and battle-readiness check at
  (1716, 7298); make an optional survey leg to `relic_island`
  (1092, 5532; ground 35.3); return to harbour.
- **Reward:** Chartered travel from the harbour and a nautical cosmetic.
- **Reveal:** Sunset West reconnects isolated places through skill and trade,
  without world-changing machinery.

### `SQ-SUNSET-02` — Southern Green

- **Kind:** PLACE DISCOVERY
- **Hook:** A fisher at (1716, 7298) brings back a leaf that does not grow on
  the harbour island.
- **Steps:** Sail from (1716, 7298) to `jungle_ruins`
  (5160, 7463; ground 127.4); identify the overgrown site; return with a rubbing
  rather than removing a ruin block.
- **Reward:** Jungle Ruins marker and a tropical encounter lead.
- **Reveal:** The southern islands hold cultures and anomalies older than the
  present crisis.

## `northlight` — research town

### `SQ-NORTH-01` — Weather That Arrives Early

- **Kind:** WORLD PUZZLE
- **Hook:** The observatory at (7265, 1556) records aurora and storms several
  minutes before the same pattern appears over the mainland.
- **Steps:** Take a synchronized reading at (7265, 1556); compare it with the
  `marsh_outflow` anchor (5565, 1703); bring the observations back to
  Northlight.
- **Reward:** A weather instrument cosmetic and cold-region supplies.
- **Reveal:** Some instability travels through the sky and water before it is
  visible as a ring.

### `SQ-NORTH-02` — Field Station Supper

- **Kind:** CHARACTER
- **Hook:** Two researchers at (7265, 1556) have kept separate food stores for
  so long that neither realizes both are running out of the same staple.
- **Steps:** Compare their inventories and organize one shared supper at
  (7265, 1556).
- **Reward:** A warm meal recipe and an ice-field encounter tip.
- **Reveal:** Northlight's isolation shapes ordinary habits as much as its
  research.

## `mining_town`

### `SQ-MINE-01` — Layers Out of Order

- **Kind:** WORLD PUZZLE
- **Hook:** The fossil lab at (6633, 5716) has two samples that cannot belong to
  adjacent layers.
- **Steps:** Compare the mine record at (6633, 5716) with the Craters anchor
  (6454, 5078; summit 200); identify the sample carrying the exchange signature.
- **Reward:** One fossil restoration service or equivalent fossil reward,
  exact fossil deferred to encounter balance.
- **Reveal:** World exchanges can splice geological history as well as towns.

### `SQ-MINE-02` — The Prospector's Line

- **Kind:** PLACE DISCOVERY
- **Hook:** A mine cart ledger at (6633, 5716) includes deliveries to a
  waystation that no current worker recognizes.
- **Steps:** Follow the overland line to `tableland_stop`
  (4876, 5729; ground 160.7); return the surviving ledger page to
  (6633, 5716).
- **Reward:** Tableland marker and access to optional ore trades.
- **Reveal:** Small rest stops bind the region's industries together.

## `displaced_city`

### `SQ-CITY-01` — Streets Built for a Summit

- **Kind:** WORLD PUZZLE
- **Hook:** At the surface entrance (2969, 1710), a city surveyor asks why the
  underground streets all drain toward a sky that is no longer above them.
- **Steps:** Enter through (2969, 1710) once the city is built; compare the
  street orientation with `the_scar` (2110, 950; ground 200); return to the
  entrance record at (2969, 1710).
- **Reward:** A city history volume and an optional cherry-grove encounter.
- **Reveal:** The cavern did not grow around the city; the complete summit plan
  was exchanged into it.

### `SQ-CITY-02` — Light That Is Not the Sun

- **Kind:** CHARACTER
- **Hook:** Gardeners at (2969, 1710) disagree over whether the false sky should
  imitate the seasons they lost or the cavern they now inhabit.
- **Steps:** Record plant responses within the city anchored at (2969, 1710);
  choose one non-permanent lighting trial; report to the gardeners there.
- **Reward:** A cherry-themed cosmetic and rare cultivation ingredients.
- **Reveal:** The city's survival is active work, and preserving memory can
  conflict with adapting to a new home.

## `tea_town`

### `SQ-TEA-01` — The Cup That Walked Away

- **Kind:** CHARACTER
- **Hook:** A tea maker at (2654, 3605) insists a prized cup leaves its shelf
  whenever nobody watches it.
- **Steps:** Observe the tea house at (2654, 3605); distinguish a playful
  Poltchageist from ordinary misplacement; settle the matter without forcing a
  capture.
- **Reward:** A tea recipe and an intentionally repeatable Poltchageist
  encounter opportunity.
- **Reveal:** Pokémon shape local traditions in ways unrelated to the crisis.

### `SQ-TEA-02` — The Dead-End Camp

- **Kind:** PLACE DISCOVERY
- **Hook:** A tea courier at (2654, 3605) has an undelivered parcel for the dig
  crew in the Rift's west spur.
- **Steps:** Carry it to `rift_dig_camp`
  (3106, 3314; ground 91.7); return the crew's stamped field note to
  (2654, 3605).
- **Reward:** Rift Dig Camp marker and a mineral-infused tea recipe.
- **Reveal:** Scholarship and ordinary trade continue around the Rift.

# Rest stops

## `merian_hut`

### `SQ-MERIAN-01` — First Water

- **Kind:** WORLD PUZZLE
- **Hook:** The hut keeper at (2813, 1102) asks the player to verify which
  trickle truly becomes the major river.
- **Steps:** Compare `merian` (2754, 1055) and the `major_river` anchor
  (3214, 1714); return to the hut at (2813, 1102).
- **Reward:** Alpine travel supplies and a source-water keepsake.
- **Reveal:** The region's largest river begins in an ordinary cirque rather
  than a supernatural source.

### `SQ-MERIAN-02` — A Bed Kept Ready

- **Kind:** CHARACTER
- **Hook:** The keeper at (2813, 1102) always leaves one bunk unused for a
  traveler who stopped arriving after the city exchange.
- **Steps:** Hear the keeper's account at (2813, 1102); optionally carry the
  name to the Displaced City entrance (2969, 1710); return with news or admit
  none was found.
- **Reward:** Free rest at the hut and a personal letter kept as a cosmetic
  record.
- **Reveal:** Missing-place stories persist through small private rituals.

## `gorge_hamlet`

### `SQ-GORGE-01` — High Water Marks

- **Kind:** LOCAL PROBLEM
- **Hook:** Bridge keepers at (6814, 4367) need new safety marks before the next
  Lake Tilpey release.
- **Steps:** Compare the hamlet anchor (6814, 4367) with `lake_tilpey`
  (5870, 3874; floor 51.3); return and help choose the warning level.
- **Reward:** Gorge crossing supplies and free rest.
- **Reveal:** The dramatic crossing is maintained infrastructure, not a
  one-time hero obstacle.

### `SQ-GORGE-02` — The Keeper Who Hates Bridges

- **Kind:** CHARACTER
- **Hook:** A young keeper at (6814, 4367) is excellent at repairs and terrified
  of crossing their own bridge.
- **Steps:** Complete a low-stakes partner-Pokémon exercise with them at
  (6814, 4367); let them choose whether to cross.
- **Reward:** A bridge-crew cosmetic and a rematch invitation.
- **Reveal:** Local competence and personal fear can coexist.

## `tableland_stop`

### `SQ-TABLE-01` — Two Horizons

- **Kind:** WORLD PUZZLE
- **Hook:** The lookout at (4876, 5729) claims the Craters and Rift brighten in
  alternating pulses.
- **Steps:** Take readings at (4876, 5729); compare bearings toward `craters`
  (6454, 5078) and `rift` (4160, 3920); record whether the pulse alternates.
- **Reward:** A lookout lens cosmetic and a regional panorama map.
- **Reveal:** Crater energy and Rift instability are connected without being
  the same phenomenon.

### `SQ-TABLE-02` — The Prospector's Last Bet

- **Kind:** CHARACTER
- **Hook:** The prospector at (4876, 5729) has one final claim and asks the
  player to choose between digging it or preserving the view.
- **Steps:** Review the claim at (4876, 5729); choose a non-binding recommendation;
  witness the prospector's decision there.
- **Reward:** A mineral sample or a landscape sketch, matching the choice.
- **Reveal:** Not every regional conflict needs a universal correct answer.

## `rift_rim_stop`

### `SQ-RIM-01` — Ranger Stones

- **Kind:** LOCAL PROBLEM
- **Hook:** Rangers at (3734, 3951) need missing path markers replaced after a
  small Rift pulse.
- **Steps:** Inspect the post at (3734, 3951) and the nearby `rift` anchor
  (4160, 3920); complete the marker check without entering Victory Road.
- **Reward:** Rift travel supplies and the rest-stop marker.
- **Reveal:** The Rift was a dangerous landscape before it became the final
  route.

### `SQ-RIM-02` — Tea at the Edge

- **Kind:** PLACE DISCOVERY
- **Hook:** A ranger at (3734, 3951) keeps a sealed tea tin addressed to a maker
  they have never visited.
- **Steps:** Carry it to `tea_town` (2654, 3605; ground 112.1); return a fresh
  blend to (3734, 3951).
- **Reward:** A shared rest recipe and both settlements' optional map notes.
- **Reveal:** Small personal routes cross boundaries the main campaign treats
  as dangerous.

# Outposts

## `relic_island`

### `SQ-RELIC-01` — Roots in the Wrong Stone

- **Kind:** WORLD PUZZLE
- **Hook:** The lone surviving tree beside the Pallet house at the island anchor
  (1092, 5532) has roots meeting stone unlike the Pallet mainland.
- **Steps:** Inspect the house and tree area at (1092, 5532); compare a harmless
  sample with Pallet at (1462, 5293).
- **Reward:** A Pallet keepsake and a rare cultivation ingredient.
- **Reveal:** The island includes both exchanged material and native substrate;
  the boundary cut through living ground.

### `SQ-RELIC-02` — Message in an Empty House

- **Kind:** CHARACTER
- **Hook:** A note in the house at (1092, 5532) was written for someone still in
  Pallet.
- **Steps:** Read it at (1092, 5532); decide whether to deliver it, preserve it,
  or return it unopened to Pallet centre (1462, 5293).
- **Reward:** A house-themed cosmetic and a small relationship scene in Pallet.
- **Reveal:** Familiar architecture carries private lives that the exchange did
  not neatly preserve.

## `the_scar`

### `SQ-SCAR-01` — Follow the Foundations

- **Kind:** WORLD PUZZLE
- **Hook:** At the Scar (2110, 950), surviving foundations line up with streets
  described by rumors from beneath the Glacial Tear.
- **Steps:** Record the foundation orientation at (2110, 950); travel to the
  `displaced_city` entrance (2969, 1710); compare the underground street plan
  once available.
- **Reward:** A paired before-and-after map and a city encounter lead.
- **Reveal:** The Scar and Displaced City are the two sides of one exchange.

### `SQ-SCAR-02` — Summit Memorial

- **Kind:** CHARACTER
- **Hook:** A former city resident returns to (2110, 950) but cannot decide
  whether leaving a memorial claims the summit or says goodbye to it.
- **Steps:** Hear their account at (2110, 950); help choose a temporary marker
  that does not alter terrain permanently.
- **Reward:** A city-made cosmetic and an optional rematch.
- **Reveal:** Surviving displacement does not settle whether an old home should
  be reclaimed, remembered, or released.

## `viltri_light`

### `SQ-LIGHT-01` — A Lighthouse for No River

- **Kind:** WORLD PUZZLE
- **Hook:** The keeper at (550, 4518) maintains a light above
  `mouth_of_viltri` (613, 4306), though Viltri Ravine no longer carries water.
- **Steps:** Inspect the mouth at (613, 4306); trace the dry route to
  `viltri_ravine` (1100, 3600); relight the keeper's historical chart at
  (550, 4518).
- **Reward:** Permanent lighthouse map marker and a navigation cosmetic.
- **Reveal:** The lighthouse is civic memory for a river mouth the moved land
  made obsolete.

### `SQ-LIGHT-02` — Night Watch

- **Kind:** CHARACTER
- **Hook:** The keeper at (550, 4518) asks for company during a storm watch.
- **Steps:** Remain at the lighthouse anchor (550, 4518); record ships, Pokémon,
  and false ring lights without chasing them.
- **Reward:** A lantern-themed cosmetic and a coastal encounter tip.
- **Reveal:** Some people preserve a place simply by continuing its routine.

## `rift_dig_camp`

### `SQ-DIG-01` — Steel Before the Compact

- **Kind:** WORLD PUZZLE
- **Hook:** Archaeologists at (3106, 3314) expose material that predates the
  Compact's field anchors.
- **Steps:** Inspect the camp record at (3106, 3314); compare it with the `rift`
  anchor (4160, 3920); complete a non-destructive pattern puzzle at camp.
- **Reward:** An archaeology cosmetic and access to the optional Registeel
  chamber sequence once that structure exists.
- **Reveal:** The Rift has a deeper history than the present forced exchanges.

### `SQ-DIG-02` — The Missing Surveyor

- **Kind:** PLACE DISCOVERY
- **Hook:** A camp roster at (3106, 3314) lists a surveyor last seen heading for
  Shrew Lake.
- **Steps:** Search `shrew_lake` (2822, 3954; floor 55.2); return the surveyor or
  their field case to (3106, 3314).
- **Reward:** A Shrew Lake marker and field supplies.
- **Reveal:** Optional research has ordinary risks unrelated to villains.

## `frostpeak_shrine`

### `SQ-FROST-01` — One Summit, Three Shadows

- **Kind:** WORLD PUZZLE
- **Hook:** The shrine at (682, 380; ground 200) casts a morning shadow that
  seems to point toward all three northern peaks in turn.
- **Steps:** Observe from (682, 380); compare the bearing with `tri_peaks`
  (1310, 882; summit 200); record the result without moving shrine blocks.
- **Reward:** A summit charm cosmetic and an alpine encounter lead.
- **Reveal:** The shrine's builders understood the massif as one connected
  landscape.

### `SQ-FROST-02` — The Offering Nobody Owns

- **Kind:** CHARACTER
- **Hook:** Two pilgrims at (682, 380) each insist an old offering belongs to
  the other community.
- **Steps:** Hear both accounts at (682, 380); leave the object in shared care
  or document it without assigning ownership.
- **Reward:** A noncombat shrine blessing represented by a cosmetic or camp
  supply bundle.
- **Reveal:** Shared traditions can outlast certainty about who began them.

## `jungle_ruins`

### `SQ-JUNGLE-01` — Older Than the Rift

- **Kind:** WORLD PUZZLE
- **Hook:** Symbols at (5160, 7463) resemble rings but lie under growth older
  than the Haven Compact.
- **Steps:** Survey the ruins at (5160, 7463); make rubbings without removing
  blocks; compare them with a post-crisis archive at the League
  (3297, 2603).
- **Reward:** A ruin cosmetic and one hidden cache.
- **Reveal:** Ring-like phenomena or their interpretation existed before the
  current faction.

### `SQ-JUNGLE-02` — The Harbour's Lost Marker

- **Kind:** PLACE DISCOVERY
- **Hook:** A weathered navigation marker in the ruins at (5160, 7463) bears
  Sunset West's old harbor sign.
- **Steps:** Carry a rubbing to `sunset_west` (1716, 7298); let the boat builders
  decide whether to restore the route.
- **Reward:** Optional travel between the harbour and jungle island, subject to
  later travel-system implementation.
- **Reveal:** The outer islands exchanged goods before the present routes were
  lost.

# Coverage gaps that must remain visible

## Landmark trees

The current `data/landmarks.json`, `data/regions.json`, and `data/towns.json` do
not define five landmark-tree IDs or coordinates. The only matching authored
facts are:

- the user's direction that **the Sentinel** stands by a hidden tarn;
- the real `ravine_head_tarn` anchor at (3376, 921; floor 105), used by
  `SQ-G4-03`;
- the lone tree on `relic_island` described in the F4 event document, anchored
  only to the island centre (1092, 5532), used by `SQ-RELIC-01`.

The other four requested landmark-tree visits cannot receive valid quest steps
without invented geography. Add stable tree IDs and block coordinates, then
assign each a PLACE DISCOVERY, WORLD PUZZLE, CHARACTER, or encounter purpose.
If the Relic Island tree is one of the intended five, only three remain missing.

## Nether side content

The Nether is real and optional. Existing design supports a midgame expedition
for blaze rods, Moltres, four Ruin shrines, fortresses, and Nether materials.
It does **not** yet supply real generated structure coordinates: the dimension
has never been pregenerated or audited, and candidate starts are explicitly
only attempts. A coordinate-complete quest would therefore be fabricated.

Recommended story use after the dimension audit: a Mining Town commission to
compare crater material at (6633, 5716) with one audited Nether ruin or fortress,
followed by a Lake Tilpey or Blaine research reward. This remains optional and
must not restore Nether copies of Blaine's gym.

## End side content

End access is postgame, and generated League copies are disabled. The intended
optional content is a consent-based survey of Necrozma's Dawn and Dusk towers,
Eternatus, and other ring anomalies after `champion_cleared`. The End has not
been generated or audited, so those structures have no verified coordinates.
The loaded pack also schedules a shiny level-100 Rayquaza at End (0, 70, 0),
but whether to keep, gate, or remove that behavior is unresolved; it is not used
as a quest reward here.

Recommended story use after audit: Maren's New Atlas expedition starts at the
League (3297, 2603), enters through the future postgame portal room, and records
audited tower locations without moving or claiming them. It cannot become a
coordinate-complete quest until the portal room and destination structures
exist.

## Other build dependencies

1. The Displaced City quests require the city cavern, safe entrance, and street
   plan at the accepted surface anchor (2969, 1710).
2. Registeel and Regigigas quest rewards require their planned chambers and
   verified encounter behavior; neither is promised by these briefs.
3. Settlement-local steps need building and NPC coordinates after town layouts
   are placed. Until then, the measured centre is the only valid anchor.
4. Travel unlocks, shop changes, one-time encounters, recipes, and cosmetics
   are reward intentions. Their exact IDs and multiplayer behavior wait for the
   quest schema and mechanic experiments.
