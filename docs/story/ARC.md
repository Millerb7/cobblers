# Narrative Arc

**Status:** Approved arc, revised 2026-09-16 against the regenerated data. Main-story dialogue and quest
schemas remain on hold. Side-content proposals are in `SIDEQUESTS.md` and
`SIDE_EVENTS.md`.

## Authority and current data limits

This arc treats geography as ground truth. Every required location below comes
from `data/towns.json`; every named physical feature comes from
`data/landmarks.json`, `data/regions.json`, or `data/rivers.json`.

The ten critical settlements are the complete required path:

`hometown` -> `gym1_town` -> `gym2_town` -> `gym3_town` ->
`gym4_town` -> `gym5_town` -> `gym6_town` -> `gym7_town` ->
`gym8_town` -> `league`.

All ten have coordinates, but nine are marked `proposed` in
`data/towns.json`; only `league` is marked `accepted`. Their display names
are null. This document therefore uses their stable IDs and working names.
Pallet Town is established by the premise; other town names remain open.

`data/trainers.json`, named route trainers, and faction progression flags do
not exist on this branch. Trainer prerequisites below are narrative
requirements with IDs still to be authored. Two approved additions should use
the existing flag ledger: `crater_operation_stopped` after the Craters climax
and `rift_crisis_resolved` after Hoopa is released at the Rift. This document
defines their meaning; a later schema pass must add their concrete setters and
chapter dependencies to `data/progression.json`.

Route lengths in this document are approximate and named by route ID.
`data/routes.json` holds the measured figure for every leg; when prose and data
disagree, the data wins. Victory Road (`victory_road`) runs roughly 5,200
blocks along the terrain-derived path through the Rift.

## Fixed path

| Order | Stable ID | Working place | Centre | Required progression |
| ---: | --- | --- | --- | --- |
| 0 | `hometown` | Pallet Town | (1462, 117, 5293) | Start |
| 1 | `gym1_town` | Brock's town, Viltri Plateau | (1743, 138, 3628) | Sets `gym1_cleared` |
| 2 | `gym2_town` | Misty's town, Lake Viltri Hollow | (1605, 108, 2801) | Sets `gym2_cleared` |
| 3 | `gym3_town` | Surge's town, Tri Peaks shelf below Mt Vessu | (1688, 174, 1410) | Sets `gym3_cleared` |
| 4 | `gym4_town` | Erika's town, Peak Pond Hollow | (4309, 111, 1555) | Sets `gym4_cleared` |
| 5 | `gym5_town` | Koga's town, Glacier Foot Fields | (4646, 117, 2446) | Sets `gym5_cleared` |
| 6 | `gym6_town` | Sabrina's town, Tilpey North Shore | (6196, 94, 3398) | Sets `gym6_cleared` |
| 7 | `gym7_town` | Blaine's town, Crater north-west rim | (6074, 107, 4995) | Sets `crater_operation_stopped`, then `gym7_cleared` |
| 8 | `gym8_town` | Giovanni's town, South Strand | (3647, 113, 6497) | Sets `gym8_cleared` |
| 9 | `league` | Pokemon League, Rift head | (3297, 118, 2603) | Requires `rift_crisis_resolved`; sets `champion_cleared` |

Coordinates are rounded from the measured town centres for readability. They
are identifiers and staging anchors, not permission to move terrain or town
footprints.

## Narrative rules

1. Pallet contains no reliable exposition. The opening question is created by
   the mismatch between memory and visible geography.
2. Each required settlement adds one useful fact and one new uncertainty.
3. The player understands the faction's rescue purpose before being asked to
   oppose it.
4. Ordinary displaced families remain visible after the faction becomes an
   antagonist.
5. The faction crosses the moral line when it knowingly chooses an occupied
   destination, not when the player first sees its technology.
6. Hoopa is destabilised by repeated forced use. Hoopa is neither a mastermind
   nor a simple final monster.
7. Optional places deepen or challenge the required account but never supply a
   fact needed to reach the next gym.
8. The ending stops the forced exchanges. It does not conveniently return every
   displaced person or erase the cost already paid.

## The Haven Compact

The faction's public name is **the Haven Compact**. It began as an agreement
between communities in collapsing worlds to share shelter, transport, food,
and technical knowledge. Its relocation crews learned to trigger and steer
Hoopa's exchanges. The name remains sincere even after its leadership chooses
an occupied destination: most members still understand themselves as rescue
workers. The Compact's leader, named members, history, and internal positions
are defined in `FACTION.md`.

## Rival — Maren of Pallet

Maren grew up in Pallet and remembers Kanto. A close family member was outside
town when Pallet moved, so Maren's loss points in the opposite direction from
the native settlement that vanished: they want to know whether a controlled
exchange could reconnect Pallet with the people left behind. They are neither
the player's spokesperson nor a recurring obstacle. They investigate by a
different route and sometimes reach a useful conclusion first.

Maren's position diverges from the player's required course in one central
way. The player must stop forced exchanges because the destination cannot
consent and Hoopa is breaking. Maren spends much of the story believing one
carefully measured exchange may still be justified if it can restore contact
with Kanto. Sabrina's evidence makes them doubt the method; the occupied target
at the Craters ends their support for it. At the Rift, Maren argues that release
must be followed by a rescue effort for people stranded on every side. Their
ending is a commitment to contact and repair, not a sudden agreement that every
hope of reversal was foolish.

| Settlement | Maren's appearance and changing position |
| --- | --- |
| `hometown` | Leaves Pallet with the same wrong map and a separate lead. Wants to find the family member who remained in Kanto. |
| `gym1_town` | Hears the native account of the settlement Pallet displaced. Accepts that Pallet's survival caused another loss. |
| `gym2_town` | Helps Haven Compact families unload supplies and listens when they describe successful rescues. Begins to think the Compact could reconnect Pallet with Kanto. |
| `gym3_town` | Recovers a second signal trace while the player protects Surge's records. Concludes that steering is real and potentially reversible. |
| `gym4_town` | Studies the dry channel and the evidence of an earlier city-scale exchange. Argues that better measurement, rather than a complete stop, may still prevent harm. |
| `gym5_town` | Follows abandoned anchor marks through the wet ground. Accepts that each forced use makes the next exchange less controllable. |
| `gym6_town` | Experiences part of Hoopa's distress through Sabrina. Stops defending the current method but still wants a future voluntary use. |
| `gym7_town` | Helps a Compact dissenter verify that the selected destination is occupied. Rejects the crater operation and assists in stopping it. |
| `gym8_town` | Works with displaced families while loyalists retreat. Insists that ending the mechanism does not end the duty to those whose homes are collapsing. |
| `league` | Helps free Hoopa before the League opens. Watches the League recognition, then begins a postgame record of missing and displaced communities. |

## Hoopa's physical location

Hoopa is physically held in the Haven Compact's containment cradle beneath the
League plateau at the head of the Rift, anchored to the `league` site at
(3297, 2603). The Compact routes each remote operation through that cradle;
Hoopa does not travel with its field crews. Before the finale the player can
encounter ring effects, distress, and projected glimpses, but cannot reach
Hoopa. Victory Road reaches the containment level after `gym8_cleared`, and the
Rift confrontation releases Hoopa before the League challenge begins.

The terrain data supplies the League footprint and nearby Rift, but no chamber
or exact underground Y coordinate. That required build is recorded as a
geography gap. Its entrance must lie on Victory Road (`victory_road`) and cannot
require an optional settlement.

## Gym-leader reconciliation

Brock, Misty, Surge, Erika, Koga, Sabrina, Blaine, and Giovanni are natives of
this world. Their order and battle identities follow the fixed Kanto sequence,
but the story does not treat them as Kanto arrivals, copies, or people Oak
already knows. Pallet's residents remember Kanto; the eight leaders do not.

**Antagonist identity:** The faction's leader is a new original character. They
are not Giovanni, another Gym Leader, or a concealed version of an existing
Kanto villain. Their name, history, internal allies, and exact position within
the faction are deliberately deferred to `docs/story/FACTION.md`. Giovanni has
no secret command relationship with them.

Their proposed civic roles support the geography and arc:

- Brock is a plateau builder and practical emergency coordinator.
- Misty manages a lake town accustomed to rescues and water travel.
- Surge maintains power, signals, and storm-facing equipment. His town sits
  on a shelf at the foot of Mt Vessu; his signal array stands on a Vessu
  shoulder above it.
- Erika protects Peak Pond Hollow and mediates between residents and arrivals.
- Koga tracks covert movement through the marsh and glacier-foot country.
- Sabrina studies the Rift's effects on memory, perception, and Pokémon.
- Blaine is a crater researcher who understands the energy used by the faction.
- Giovanni is the southern region's hard-edged civil defender. He is neither
  the antagonist nor a member or leader of the faction.

These roles are story proposals. They do not change trainer teams or structures.

# Act I — The place that should not be here

## Settlement 1: `hometown` — Pallet Town

**Ground truth**

- Centre: (1462, 117, 5293), in `pallet_meadows` / `pallet_fields`.
- The first route runs north through the plains toward `gym1_town`.
- The coast lies nearby. `river_of_shrews` is 605 blocks away.
- Optional `relic_island` is the nearest settlement, 440 blocks away, but it
  is not part of the required path.

**Required sequence**

The opening stays familiar. Oak offers the starter, gives the ordinary send-off,
and speaks as if the known route and neighboring landmarks are still outside.
No one explains the premise.

The break happens only when the player leaves the settled part of Pallet. The
route remembered by Pallet's residents is absent. A native trail runs north
through unfamiliar plains, the skyline is wrong, and expected Kanto landmarks
cannot be found. Most of the town survived intact, but a small cluster of homes at the exchanged
edge was crushed by falling and compressed material. Beyond that localized
damage, Pallet's edge does not join the land its residents remember.

Residents offer incompatible interpretations in short, uncertain fragments:
storm, attack, earthquake, dream, mass displacement. Oak admits that his maps
and field knowledge no longer fit. He does not give a formal investigation
quest. The player's clue is the mismatch itself: Pallet has not been rebuilt
into an imitation. Its surviving streets and buildings are the real town,
joined to the wrong ground, with localized damage where the exchange boundary
closed badly.

The only useful action is to take the starter and follow the real northbound
trail toward the nearest critical settlement.

**Knowledge state on departure**

- **Knows:** Pallet survived largely intact; its exchanged edge suffered
  localized damage; the surrounding terrain is not Kanto; local memories
  conflict with physical evidence.
- **Believes:** a single event moved or transformed the town.
- **Suspects:** someone outside Pallet may have seen what happened.
- **Does not know:** that this was an exchange, that a native settlement was
  displaced, that Hoopa was involved, or that the event was steered.

**Optional echo**

`relic_island` may show that part of Pallet was torn away from the main
arrival. It can make the event feel less clean, but no clue found there may be
required at Brock's town.

## Settlement 2: `gym1_town` — Brock on Viltri Plateau

**Ground truth**

- Centre: (1743, 138, 3628), in `viltri_plateau` / `viltri_woods`.
- Route from Pallet: `route_01_pallet_to_brock`, roughly 2,000 blocks, pinned
  through the Route 1 maze forest; no water crossing.
- Nearby: `viltri_ravine` 455 blocks, `lake_viltri` 573 blocks, and
  `viltris_path` 664 blocks.
- Defeating Brock sets `gym1_cleared`.

**Required sequence**

The player arrives as an unknown carrying a story that sounds impossible.
Brock and the town do not immediately grant access to the leader. The player
must defeat a short set of local trainers in public, ordinary battles. This is
a competence test, not a faction encounter. Exact trainer IDs are a data gap.

Brock then gives the first native account. From the plateau during the event,
he saw the western horizon distort. When people reached Pallet Meadows, Pallet
Town stood on ground where a native settlement had been. That settlement and
its people were gone. Pallet did not merely arrive; something else left.

Brock refuses to blame Pallet's residents. They look as stranded as everyone
else. He also refuses to call the event random: smaller discontinuities have
left straight seams, displaced material, and impossible alignments elsewhere.
He knows effects, not a cause.

The gym battle follows. After `gym1_cleared`, Brock directs the player toward
the lake town because Misty's people keep records of unusual arrivals and move
aid through Lake Viltri. This is a practical lead, not a lore assignment.

**Knowledge state after the gym**

- **Knows:** Pallet replaced an occupied native settlement; the event had
  witnesses outside Pallet; other discontinuities exist.
- **Believes:** the event is part of a regional pattern.
- **Suspects:** the missing native settlement may have gone wherever Pallet
  came from.
- **Does not know:** who causes exchanges or whether they are deliberate.

# Act II — Rescue and exchange

## Settlement 3: `gym2_town` — Misty at Lake Viltri

**Ground truth**

- Centre: (1605, 108, 2801), in `lake_viltri_hollow` / `viltri_woods`.
- Route from Brock: `route_02_brock_to_misty`, roughly 950 blocks, with no
  water crossing.
- `lake_viltri` is 86 blocks away; `viltri_ravine` is 195 blocks away;
  `viltris_path` is 242 blocks away.
- Defeating Misty sets `gym2_cleared`.

**Required sequence**

This is the first contact with the faction. They appear first as rescue workers,
surveyors, and displaced civilians near a town already organised around water
and recovery. Their ordinary families carry household belongings, medicines,
and Pokémon from a world that is failing. They do not threaten the player.

A faction field representative explains only the immediate truth: their home is
collapsing, and moving people is the only method that has saved anyone. The
player sees the human result before learning the cost. The faction recognises
Pallet as an unusually large and successful transfer, but does not admit to
causing it.

Misty treats the arrivals as people in danger while keeping control of her
shore. She does not ask the player to choose a side. Her gym tests whether the
player can act under pressure without turning frightened people into enemies.

After `gym2_cleared`, evidence from the lake records points north: Surge's
signal array on Mt Vessu has logged the same distinct pulse seen when Pallet
arrived, and his relayed readings sit in Misty's files. The route to Surge
(`route_03_misty_to_surge`, roughly 2,100 blocks) climbs through Foothill Woods,
Mt Clay, Mt Vessu, and the Tri Peaks without a water crossing.

**Knowledge state after the gym**

- **Knows:** at least some faction members and families come from a collapsing
  world; transfers can save real people.
- **Believes:** the faction may understand the phenomenon better than it admits.
- **Suspects:** Pallet's arrival resembles their rescue method.
- **Does not know:** whether they triggered Pallet, how transfers choose a
  destination, or what happens to those displaced from it.

This is the sympathy beat. Opposition comes later.

## Settlement 4: `gym3_town` — Surge below Mt Vessu

**Ground truth**

- Centre: (1688, 174, 1410), in `the_tri_peaks` / `tri_peaks`: a shelf on the
  south flank where the Tri Peaks meet Mt Vessu. The town is at the mountain's
  foot, not on it.
- Route from Misty: `route_03_misty_to_surge`, roughly 2,100 blocks through
  Foothill Woods, Mt Clay, Mt Vessu, and the Tri Peaks; no water crossing. It
  is a sustained ascent of roughly 80 blocks with no step steeper than 35
  degrees.
- Surge's signal array (`surge_signal_array`, planned) stands at
  (1928, 284, 1248) on a Mt Vessu shoulder, roughly 290 blocks from town and
  about 110 blocks above it. Its maintenance climb is not on the critical path
  and needs authored stairs or terracing.
- Arrival: over the last stretch of the route, the shelf lip opens onto the
  summits. This is a scenery moment with no beat attached.
- Optional `the_scar` is roughly 620 blocks from town and cannot be seen from
  it.
- Defeating Surge sets `gym3_cleared`.

**Required sequence**

Surge's instruments establish the next fact without explaining the whole
system. The array on the shoulder above town feeds its readings down to his
records: the transfer pulse is not natural noise. It contains repeated timing
and direction changes. Someone is triggering and steering it.

A faction team in town attempts to recover or disable records before Surge can
compare them with the Pallet event. This is the first direct obstruction. The
team avoids harming civilians and withdraws when exposed, preserving the
difference between secrecy and open violence.

Surge's battle comes after the player secures the critical evidence in town.
After `gym3_cleared`, he identifies the next signal source east of the massif,
toward Peak Pond Hollow. He cannot determine whether the signal is a weapon, a
rescue beacon, or both.

**Knowledge state after the gym**

- **Knows:** exchanges can be deliberately triggered and steered; the faction
  conceals technical evidence.
- **Believes:** the faction caused or directed Pallet's arrival.
- **Suspects:** the clean arrival required a destination to be exchanged.
- **Does not know:** who ordered Pallet's transfer or how much control the
  faction truly has.

**Optional echo**

`the_scar` at (2110, 280, 950) is not required. Players who climb there see
the empty summit footprint and a road ending at nothing. That discovery lets
them infer a second town-scale exchange before the critical path confirms it.
Players who skip it learn the same required fact later.

## Settlement 5: `gym4_town` — Erika at Peak Pond Hollow

**Ground truth**

- Centre: (4309, 111, 1555), in `peak_pond_hollow` /
  `northern_downs`.
- Route from Surge: `route_04_surge_to_erika`, roughly 3,500 blocks back
  across Mt Vessu and Mt Clay, then through Merian Cirque, the Crags, Upper
  Trough, and Peak Pond Hollow; no water crossing.
- `peak_pond` is 129 blocks away; `peak_pond_creek` is 297 blocks away.
- The major river is still only a headwater in this northern leg; the measured
  route records no water crossing.
- Defeating Erika sets `gym4_cleared`.

**Required sequence**

Peak Pond Hollow shows the faction's internal divide. Refugee families are
being housed in and around the town. Some faction members want to stop forced
transfers until they can guarantee an empty destination. Others argue that
waiting for certainty means abandoning living communities.

Erika makes the player deal with both groups as residents rather than symbols.
Then she takes the player to the dry channel above Peak Pond. The channel is
physically present at `peak_pond_creek` (3786, 1182), while its former head is
the tarn at (3376, 921). The measured channel rises 22–29 blocks between its
ends, so water cannot follow the carved course. The impossible grade is
evidence the player can inspect, not a hypothetical harmless destination.

Erika pairs the channel with pre-event survey records kept in town. Those
records show that the same exchange signature affected a settled summit west
of the hollow: a complete city-scale exchange happened before Pallet. The
required path therefore establishes the existence of the second exchange.
Climbing to `the_scar` or finding `displaced_city` remains optional and reveals
where the city went and how its people live now.

The evidence establishes that a transfer exchanges occupied volume rather than
adding new land. A rescue cannot be separated from whatever leaves the
destination. The Haven Compact still claims that careful targeting can reduce
the harm, and Maren still believes a sufficiently measured exchange might
restore contact without repeating the loss.

After `gym4_cleared`, Erika sends the player south because unusual equipment
and concealed movement have been reported around the Glacier Foot Fields and
Marsh Country.

**Knowledge state after the gym**

- **Knows:** every transfer is an exchange; a previous city-scale exchange
  moved a settled summit; faction members disagree about continuing.
- **Believes:** Pallet was moved as part of the same programme.
- **Suspects:** the faction cannot measure every life at a destination.
- **Does not know:** why exchanges are becoming less stable or what powers them.

# Act III — The cost of repetition

## Settlement 6: `gym5_town` — Koga at Glacier Foot Fields

**Ground truth**

- Centre: (4646, 117, 2446), in `glacier_foot_fields` /
  `marsh_country`.
- Route from Erika: `route_05_erika_to_koga`, roughly 1,050 blocks south
  through the North-East Downs to Glacier Foot Fields.
- `glacial_tear` and `marshy_marsh` are each 311 blocks away;
  `major_river` is 507 blocks away.
- Defeating Koga sets `gym5_cleared`.

**Required sequence**

Koga has tracked repeated faction movements through the wet ground and fields.
The evidence is cumulative rather than spectacular: abandoned anchors,
increasingly inaccurate destination marks, frightened Pokémon, and exchange
effects that persist after the equipment is gone.

The critical discovery is that each forced use makes the next transfer less
stable. The faction's early operations could exchange bounded places. Current
operations distort larger areas and leave effects far from the target.

The player also finds the first reliable indication that the power is mediated
through a living Pokémon. The name Hoopa need not be delivered as a speech; it
can emerge from a recovered symbol, device label, or brief faction reaction.
The essential fact is that the phenomenon is being forced through an unwilling,
destabilised being.

Koga's gym battle follows the investigation. After `gym5_cleared`, he sends
the player east to Sabrina's central town, where observations from the glacier,
river, and lake can be compared.

**Knowledge state after the gym**

- **Knows:** repeated forced exchanges are destabilising; a living Pokémon,
  Hoopa, is being used.
- **Believes:** even a technically successful rescue now makes later disasters
  more likely.
- **Suspects:** the Rift is accumulated damage rather than a natural landmark.
- **Does not know:** the faction's next target or whether Hoopa can survive
  another large exchange.

## Settlement 7: `gym6_town` — Sabrina at Tilpey North Shore

**Ground truth**

- Centre: (6196, 94, 3398), in `tilpey_north_shore` /
  `tilpey_lakeland`.
- Route from Koga: `route_06_koga_to_sabrina`, roughly 1,950 blocks through
  Glacier Foot Fields and Marsh Creek to Tilpey's north shore.
- `marsh_to_tilpey` is 252 blocks away; `lake_tilpey` 256 blocks away;
  `glacial_tear` 609 blocks away.
- Defeating Sabrina sets `gym6_cleared`.

**Required sequence**

Sabrina's town is where separate observations become one pattern. Water levels,
glacier disturbances, memory gaps, Pokémon behaviour, and faction signal
records all peak around the same forced exchanges. Sabrina can perceive Hoopa's
distress, but she does not translate its experience into a lore lecture. The
player receives fragments: fear before activation, pain during steering, and
confusion afterward.

A faction representative makes the strongest moral case here. One of their
largest remaining communities will not survive without relocation. They accept
that the method harms this world, but argue that refusing to act is also a
choice that kills people.

The player is not asked to declare the faction evil. The immediate conflict is
whether another forced use is acceptable when neither side has a harmless
answer.

Sabrina's battle tests resolve before the first real geographic barrier. After
`gym6_cleared`, the player can proceed south toward the Craters, crossing the
major river and Lake Tilpey's outflow gorge at about (6632, 3904).

**Knowledge state after the gym**

- **Knows:** Hoopa is being compelled; the Rift and other instability track
  repeated use; a large refugee community is in immediate danger.
- **Believes:** another mass transfer may permanently break Hoopa or widen the
  Rift.
- **Suspects:** the faction is preparing that transfer at a major energy source.
- **Does not know:** which destination they have selected or whether they will
  accept a refusal.

# Act IV — The line that cannot be defended

## Settlement 8: `gym7_town` — Blaine at the Craters

**Ground truth**

- Centre: (6074, 107, 4995), in `crater_rim_north_west` /
  `the_craters`.
- Route from Sabrina: `route_07_sabrina_to_blaine`, roughly 2,050 blocks
  through Tilpey's east and south shores.
- It crosses Lake Tilpey and its outflow at the required (6632, 3904) bridge.
- `craters` begins 27 blocks from town; `lake_tilpey` is 423 blocks away.
- Defeating Blaine sets `gym7_cleared`.

**Required sequence**

The faction is using the Craters as the energy source for its next mass
exchange. This is not itself the moral break; using available power to save
people remains understandable.

The line is crossed when the player and Blaine establish that the chosen
destination is occupied and the faction leadership proceeds anyway. Their
measurements predict displacement. They no longer claim the harm is accidental
or avoidable. They choose their own community over the people already there.

A faction member who has opposed that decision helps expose the destination
data. Refugee families remain nearby, making the cost of stopping the operation
visible. The player prevents the crater activation, setting
`crater_operation_stopped`, but that victory does not solve the refugees'
emergency. `gym7_cleared` remains the badge and route flag; the two flags record
different events.

Blaine does not turn the gym into a reward ceremony. The battle confirms that
the player can survive the southern route and act under catastrophic pressure.
After `gym7_cleared`, evidence points west along the southern coast: the
faction is withdrawing toward the Rift's southern approach.

**Knowledge state after the gym**

- **Knows:** faction leadership knowingly selected an occupied destination;
  another forced use would endanger Hoopa and this world.
- **Believes:** the crater operation was preparation, not the faction's last
  option.
- **Suspects:** the Rift can be used directly for a final attempt.
- **Does not know:** whether the faction's dissenters can prevent it or what
  stopping all transfers means for the refugees.

This is the moment the faction's chosen method stops being defensible. Their
people do not stop being worth saving.

## Settlement 9: `gym8_town` — Giovanni on South Strand

**Ground truth**

- Centre: (3647, 113, 6497), in `south_strand` /
  `southern_coast`.
- Route from Blaine: `route_08_blaine_to_giovanni`, roughly 3,050 blocks
  west, with no water crossing.
- `arrow_lake_south_east_branch` is 358 blocks away;
  `arrow_lake_south` 680 blocks away; `rift` 1,122 blocks away.
- Defeating Giovanni sets `gym8_cleared`.

**Required sequence**

Giovanni has kept the final gym closed while defending the southern settlements
and tracking movement toward the Rift. He is a native leader whose severity
comes from watching communities disappear, not a secret version of the
faction's commander.

The faction's internal break becomes public here. One group remains committed
to a final mass transfer through the Rift. Another refuses to trade one
population for another and offers the player the information needed to reach
the operation. Neither group has a way to save everyone.

Giovanni's challenge is the final regional test. It asks whether the player can
take responsibility for a decision whose cost cannot be hidden behind good
intentions. Defeating him sets `gym8_cleared` and opens the League route along
the Rift.

The critical path does not require `tableland_stop`, `rift_rim_stop`, or
`rift_dig_camp`. Those places may support travel or deepen the history, but
the route from Giovanni to the League must remain traversable without them.

**Knowledge state after the gym**

- **Knows:** the final forced exchange will be attempted through the Rift;
  faction dissenters will help stop it; the refugees still face collapse.
- **Believes:** ending forced use is the only way to prevent a larger chain of
  exchanges.
- **Suspects:** Hoopa may be able to stabilise if released rather than
  controlled.
- **Does not know:** whether existing exchanges can ever be reversed safely.

# Act V — The Rift and the League

## Settlement 10: `league` — the Rift head

**Ground truth**

- Centre: (3297, 118, 2603), in `foothill_woods` / `viltri_woods`.
- The League plateau is 178 blocks from `rift`, 447 blocks from
  `glacial_tear`, and 571 blocks from `major_river`.
- Victory Road follows the Rift's south-west arm, fork, trunk, and apex.
- Victory Road (`victory_road`) is roughly 5,200 blocks along the
  terrain-derived Rift path.
- The League is in the Overworld. End access is post-game.
- Defeating the champion sets `champion_cleared`.

**Required sequence**

Victory Road is the Rift itself. The terrain supplies the final exposition:
straight scars, displaced material, portal-like effects, and a path that grows
less stable toward the head. Required information is conveyed by what the
player crosses and by brief encounters with both faction loyalists and
dissenters. No optional settlement is needed.

Near the Rift head, before the League challenge, the Haven Compact begins its
final attempt above the containment cradle. Its leader's position remains
coherent: stopping means condemning their remaining community. The player's
position is equally clear: proceeding means knowingly displacing another
population, further breaking Hoopa, and risking uncontrolled exchanges across
multiple worlds.

The final story confrontation ends the forced activation and releases Hoopa
from the steering mechanism. It sets `rift_crisis_resolved`. Exact battle,
puzzle, and multiplayer-safe setter mechanics remain for the progression schema
pass, but the story state is distinct from both `gym8_cleared` and
`champion_cleared`.

The world does not snap back. Pallet remains here. The missing native
settlement remains missing. Refugees already transferred remain people who need
homes. Faction members who defected must live with both the rescues and the
displacements they enabled. Hoopa's condition improves enough to stop the
immediate collapse, but safe reversal is not promised.

Only after `rift_crisis_resolved` does the League open. It is recognition: the
region publicly acknowledges what the player has already done, and its
established trainers test the team that crossed the continent. The crisis does
not escalate again. The champion battle sets `champion_cleared`.

**Knowledge state after the champion**

- **Knows:** repeated forced use destabilised Hoopa and caused escalating
  exchanges; the faction knowingly accepted displacement to save its own;
  stopping forced use prevented a wider collapse.
- **Believes:** repair must begin with consent, evidence, and care for people
  stranded on every side.
- **Suspects:** some exchanges may eventually be reversible, but a blind
  reversal would repeat the same crime.
- **Open question:** where Pallet's displaced native settlement went and
  whether contact can be made without another forced swap.

## Ending image

Pallet is still geographically wrong, but no longer alone. News, travellers,
and Pokémon now move between it and the native settlements. Oak's original map
remains incorrect. A new map begins beside it.

The emotional resolution is belonging without pretending the loss was harmless.

# Optional discovery relationship

Optional content can move a player from uncertainty to deeper understanding
earlier, but the required settlement immediately afterward must still provide
the minimum fact needed by players who skipped it.

| Optional place | Real centre | Contribution | Must never gate |
| --- | --- | --- | --- |
| `relic_island` | (1092, 68, 5532) | Shows a Pallet fragment separated from the main exchange | Leaving Pallet or reaching Brock |
| `viltri_light` | (550, 68, 4518) | Shows an old estuary whose river no longer arrives | Brock or Misty |
| `the_scar` | (2110, 280, 950) | Shows the summit footprint of the displaced city | Surge or Erika |
| `displaced_city` | (2969, 123, 1710) | Gives the deepest human account of a complete town exchange | Any gym or the League |
| `tea_town` | (2654, 112, 3605) | Shows how ordinary culture continues beside impossible geography | Victory Road |
| `rift_dig_camp` | (3106, 91, 3314) | Documents older anomalous material in the Rift's west spur | The League |
| `mining_town` | (6633, 138, 5716) | Connects crater geology, fossil layers, and deep-world history | Blaine or Giovanni |
| `sunset_west` | (1716, 114, 7298) | Post-game port and stories from the outer sea | Main story |
| `northlight` | (7265, 116, 1556) | Post-game research on weather and distant instability | Main story |
| `jungle_ruins` | (5160, 128, 7463) | Evidence that world anomalies predate the current faction | Main story |

`merian_hut`, `gorge_hamlet`, `tableland_stop`, and
`rift_rim_stop` are optional rest stops. Their services may make long routes
safer, but refusing or missing them cannot block progression.

# Reveal ladder

| Stage | New required fact |
| --- | --- |
| Pallet | The town is largely intact, with localized edge damage, in the wrong geography |
| Brock | Pallet replaced a native settlement |
| Misty | The faction rescues people from collapsing worlds |
| Surge | Exchanges can be triggered and steered |
| Erika | Every rescue exchange displaces something at the destination; an earlier settled city was exchanged too |
| Koga | Repeated use is destabilising Hoopa and the world |
| Sabrina | Hoopa is being compelled; a mass rescue is imminent |
| Blaine | Leadership knowingly chooses an occupied destination; `crater_operation_stopped` records that operation's defeat |
| Giovanni | The final attempt will use the Rift |
| Rift | Forced use ends; `rift_crisis_resolved` records Hoopa's release |
| League | The region recognizes the player; repair becomes postgame work |

# Implementation and geography gaps

1. Add `crater_operation_stopped` and `rift_crisis_resolved` to the existing
   progression flag ledger during the approved schema pass. Do not create a
   parallel quest-state system.
2. Author a Haven Compact containment chamber beneath the League plateau at
   (3297, 2603), with an entrance on Victory Road. Its exact Y, footprint, and
   structure ID do not exist in current geography data.
3. Maren and the named Haven Compact members need trainer or NPC IDs before
   dialogue and implementation.
