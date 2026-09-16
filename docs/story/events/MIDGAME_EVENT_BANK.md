# Midgame Event Bank — Gyms 4 through 6

**Status:** Proposed event bank. Exact placement, runtime mechanisms, item IDs,
Pokémon levels, and rewards remain unverified.

This package continues the populated-world approach from Surge to Sabrina. It
contains thirty-six optional events across three routes and three gym towns.
None gates a route, gym, story fact, healing service, PC, or waystone.

## Density map

| Area | Event count | Regional character |
| --- | ---: | --- |
| Surge-to-Erika route | 6 | Northern downs, long travel, refugee traffic, map disagreement |
| Erika's town | 6 | Gardens, shared housing, native and Compact coexistence |
| Erika-to-Koga route | 6 | Dense forest changing into wet ground |
| Koga's town | 6 | Marsh work, tracking, medicine, concealed movement |
| Koga-to-Sabrina route | 6 | Glacial Tear, marsh-to-lake transition, long shoreline travel |
| Sabrina's town | 6 | Lake terrace, ferries, memory effects, refugee decision point |
| **Total** | **36** | |

## Shared contract

- Completion and rewards are persistent per-player and one-time.
- Shared props retain a replay prompt, inspection marker, or NPC reenactment for
  simultaneous players and late joiners.
- A shared Pokémon actor is never also the capture reward. Controlled captures
  are separate per-player encounters and require balance approval.
- “Supplies,” held items, species access, levels, and quantities are placeholders
  until the Gym 4–6 economy and trainer-counter review.
- A completed event may change ambience but cannot remove an unfinished player's
  interaction path.
- These requirements need a two-player, reconnect, and late-join runtime proof.


### Replay surfaces by interaction family

| Family | Simultaneous and late-join surface |
| --- | --- |
| Choose a destination | The event NPC can issue personal placement markers while the shared completed prop remains visible. |
| Return or trade a prop | The NPC supplies a non-droppable proxy interaction for each unfinished player; world decoration is never the reward authority. |
| Inspect or classify | Inspection points remain usable after scenery changes and record answers per player. |
| Reroute a path or actor | A nearby practice marker replays the choices without moving the shared actor back. |
| Ordered input | A personal control board or dialogue sequence mirrors the shared device after first completion. |
| Short environmental sequence | Personal step markers and NPC prompts replay the sequence while shared plants, filters, lamps, or rest props stay in their completed pose. |

A persistent completion flag, not prop position, decides reward eligibility.

# Route 4 — Surge to Erika

**Route context:** Approximately 2,907 blocks through Mt Clay, Merian
Cirque, the Crags, Upper Trough, and Peak Pond Hollow. The path passes near Merian's hut
and has no water crossing.

## `EVT-R4-MERIAN-DELIBIRD` — Wrong Hut Again

**Visible hook:** Delibird drops the same parcel at Merian's hut every time
Merian places it back on the route marker. The label uses an unfamiliar
three-arch symbol instead of a town name.

**Interaction:** Compare the parcel symbol with three visible trail symbols and
turn the marker toward the matching ridge path without learning what lies at
its destination.

**Character beat:** Merian has added “not me” to the parcel in four languages.

**Reward and aftermath:** Alpine supplies. After Erika's required city-scale
exchange reveal, a later callback may identify the symbol and confirm that the
parcel reached its intended owner. Delibird resumes the corrected route.

## `EVT-R4-ABSOL-WARNING` — Before the Wind

**Visible hook:** An Absol watches a travel camp from the ridge while residents
quietly blame it for every sudden gust across the downs.

**Interaction:** Read the bent grass and loose canopy ropes, then secure three
windward ties before the visible gust arrives. Absol leaves once the camp is
safe.

**Character beat:** The oldest traveler says, “It came before the wind. That is
not the same as bringing it.”

**Reward and aftermath:** Weather supplies and an Absol field-note cosmetic.
Absol is a rare noncapture actor in this scene.

## `EVT-R4-DEERLING-CROSSING` — Six Seasons at Once

**Visible hook:** A mixed group of Deerling with different seasonal coats waits
beside a narrow stock gate while two surveyors argue over which habitat label
belongs on the sign.

**Interaction:** Open the wider meadow gate and select a neutral “Deerling
crossing” marker instead of assigning the group to one season.

**Character beat:** One surveyor wants a precise answer. The other points at the
four different answers currently eating the signpost.

**Reward and aftermath:** A field-guide cosmetic and common berries. The herd
uses the safer crossing as route ambience.

## `EVT-R4-APPLIN-CART` — One Apple Too Heavy

**Visible hook:** A produce cart rolls unevenly despite having four matched
wheels. One apple in the top crate keeps changing position.

**Interaction:** Watch the cart tilt, identify the moving crate, and offer an
empty basket beside it. Applin transfers into the basket instead of being
handled directly.

**Character beat:** The merchant is relieved the axle is fine and offended that
Applin sampled only the expensive fruit.

**Reward and aftermath:** Food and a berry-growing supply. Applin rides beside
the merchant and is not catchable.

## `EVT-R4-GREEDENT-CACHE` — Emergency Means Later

**Visible hook:** A marked roadside ration cache is empty, while Greedent keeps
packing berries into the hollow post beneath it.

**Interaction:** Place a squirrel-safe storage box next to the post, move one
visible berry bundle into it, and wait for Greedent to copy the new location.
The sealed emergency shelf is then restocked.

**Character beat:** The ranger admits Greedent understands “save this for later”
better than most travelers.

**Reward and aftermath:** One route ration and a restocked public cache that is
scenery, not a repeatable item source.

## `EVT-R4-MAP-SEAM` — Both Maps Are Right

**Visible hook:** A native ranger and a Compact surveyor have laid incompatible
maps on the same boulder. Both routes reach the visible ridge, but their named
landmarks do not match.

**Interaction:** Sight three shared physical features—a split pine, pale rock
face, and headwater crossing—and mark them on both maps without choosing one as
false.

**Character beat:** The surveyor keeps asking which map is current. The ranger
answers, “The ground is current.”

**Reward and aftermath:** A route sketch showing shared landmarks and a small
travel bundle. The event adds no required navigation marker.

# Erika's town — Peak Pond Hollow

**Town context:** Centre (4309, 1555), near Peak Pond and the impossible dry
channel. Native households, Compact families, surveyors, and gardeners share a
small hollow under active political tension.

## `EVT-G4-ODDISH-BEDS` — The Garden Changed Rows

**Visible hook:** Oddish wake in a different household's garden every morning,
and both families quietly return them before breakfast.

**Interaction:** Compare the food placed in both gardens and discover that each
family is feeding the same group. Create one shared bed between the plots.

**Character beat:** Both households claim they were only feeding “their half” of
the Oddish.

**Reward and aftermath:** Herbs and a peaceful Oddish encounter lead, pending
balance review. The shared bed remains between the homes.

## `EVT-G4-COMBEE-HOME` — Three Votes, One Hive

**Visible hook:** Combee inspect three proposed hive frames and reject all of
them by returning to the gardener's hat.

**Interaction:** Test shade, flower distance, and foot traffic. Combine the
shaded frame with the quiet flower-side location.

**Character beat:** The gardener insists each face voted differently. Nobody can
prove otherwise.

**Reward and aftermath:** Honey and a Combee habitat lead. The swarm remains a
shared actor rather than a capture reward.

## `EVT-G4-SEED-LIBRARY` — Same Name, Different Plant

**Visible hook:** Native and Compact seed packets share several common names but
show different plants. Volunteers have stopped sorting before they ruin the
sample beds.

**Interaction:** Match four packets by seed shape and the growers' sketches,
then label each with both its origin and plant rather than choosing one name as
correct.

**Character beat:** Two packets labeled “sunheart” produce completely different
flowers. Both growers insist the other one still looks like a sunheart.

**Reward and aftermath:** A small seed bundle and access to the shared seed
library's flavor notes. Two sample rows grow side by side.

## `EVT-G4-ROSERIA-RIBBONS` — Pollinator's Route

**Visible hook:** Roselia repeatedly remove colored survey ribbons from stakes
and carry them between flower beds.

**Interaction:** Follow the ribbon order to identify the pollination route, then
move the stakes outside the beds rather than taking the ribbons back.

**Character beat:** A surveyor realizes the “random interference” is a better
map of the garden than their grid.

**Reward and aftermath:** Botanical ingredients and a decorative ribbon. The
route remains visible without blocking Roselia.

## `EVT-G4-SEWADDLE-CANOPY` — Hemmed In

**Visible hook:** Sewaddle have stitched the loose edge of a refugee canopy to a
hedge, making the shelter sturdy and the doorway impossible to open.

**Interaction:** Add a second cloth strip at the proper anchor points. The
Sewaddle move their stitches to it, freeing the entrance without cutting their
work.

**Character beat:** The shelter owner calls it excellent construction in the
least useful location.

**Reward and aftermath:** Cloth, thread, and a repaired shared shelter used by
families after completion.

## `EVT-G4-TANGELA-FOOTPATH` — Preferred Shortcut

**Visible hook:** Tangela vines cover a small service path every afternoon even
after gardeners clear it.

**Interaction:** Notice the path crosses a cool damp patch used by Tangela.
Move the stepping stones around the patch and plant two supplied guide shrubs.

**Character beat:** The gardener has been clearing the shortcut for people who
were not actually using it.

**Reward and aftermath:** Herbs and a short optional garden loop. Main services
remain available regardless of completion.

# Route 5 — Erika to Koga

**Route context:** Approximately 1,038 blocks south through forest. The ground
becomes wetter toward Glacier Foot Fields and Marsh Country. There is no
required water crossing.

## `EVT-R5-SHROOMISH-RING` — Back Where You Started

**Visible hook:** Three hikers insist the trail loops. A ring of Shroomish has
moved the small arrow markers to face inward.

**Interaction:** Read moss growth and the visible slope rather than the arrows,
then restore the markers outside the Shroomish ring.

**Character beat:** The hikers walked the circle twice because every lap made
the signs feel more authoritative.

**Reward and aftermath:** Forest supplies and a corrected optional spur marker.
The main road was never blocked.

## `EVT-R5-ARIADOS-WEB` — High Bridge

**Visible hook:** On an optional forest spur, Ariados webs span above a shallow
path cut, catching fallen branches. A low loose strand blocks the spur while the
main road remains open and visible.

**Interaction:** Raise the loose strand onto two existing high hooks without
breaking the load-bearing web.

**Character beat:** The ranger arrived expecting to remove a hazard and found a
better bridge inspection system.

**Reward and aftermath:** String, antidote supplies, and a visible protected
crossing. Ariados remain overhead.

## `EVT-R5-PARAS-BARK` — The Correct Dead Tree

**Visible hook:** An herbalist needs medicinal fungus from fallen wood, but Paras
occupy several logs and one living tree shows similar growth.

**Interaction:** Identify the naturally fallen, unoccupied log using leaf loss,
soft bark, and no Paras tracks. Harvest only the marked sample.

**Character beat:** The herbalist refuses the largest sample because “useful”
does not mean “ours.”

**Reward and aftermath:** A small medicine bundle and a field note about forest
fungi.

## `EVT-R5-VENIPEDE-LOG` — Queue Underneath

**Visible hook:** A line of Venipede passes through a hollow log positioned
across the side trail. Travelers keep stepping over it and interrupting them.

**Interaction:** Roll two short dead branches beside the log to make a separate
human crossing. The Venipede retain the hollow route.

**Character beat:** A courier complains until they realize the Venipede queue is
better organized than the town ferry.

**Reward and aftermath:** Forest travel supplies. Both crossings remain as
ambient movement.

## `EVT-R5-HERB-MARKERS` — Wrong Red Ribbon

**Visible hook:** An apprentice has marked six plants with identical red ribbons
and forgotten which two are medicinal.

**Interaction:** Use the mentor's field card—leaf edge, stem color, and smell—to
move the ribbons to the correct plants. Incorrect choices are corrected without
harvesting them.

**Character beat:** The mentor considers “all red means important” a teachable
mistake and “pick all six” an unforgivable one.

**Reward and aftermath:** Antidotes and an herb-book cosmetic. The plants remain
in place.

## `EVT-R5-ZORUA-TRACKS` — Too Many Walkers

**Visible hook:** One set of bootprints becomes two, then four, then tiny paw
prints beside an abandoned Compact survey marker.

**Interaction:** Follow the trail only until it reaches a safe clearing. Place a
spare cloth marker there and step back; Zorua reveals itself long enough to take
the cloth and leave.

**Character beat:** Koga's scout recognizes the trick and is impressed the
player stopped before chasing it into the marsh.

**Reward and aftermath:** Tracker supplies and a nonessential note that local
Pokémon investigate abandoned equipment. Zorua is not a capture reward.

# Koga's town — Glacier Foot Fields

**Town context:** Centre (4646, 2446), near Marshy Marsh and the Glacial Tear.
The town tracks concealed Compact movement while maintaining medicine, wetland
paths, and field shelters.

## `EVT-G5-CROAGUNK-CURE` — Bad Medicine Face

**Visible hook:** Croagunk repeatedly steals capped antidote bottles and stacks
them beside a sunny wall.

**Interaction:** Offer empty colored bottles from the healer's discard crate.
Croagunk trades the sealed medicine for the brighter collection.

**Character beat:** The healer spent an hour diagnosing a healthy Croagunk that
simply liked blue glass.

**Reward and aftermath:** Antidotes and a Croagunk habitat lead. The shared
Croagunk is not catchable.

## `EVT-G5-NINCADA-TRAIL` — Holes in a Straight Line

**Visible hook:** Fresh Nincada burrows form an unnaturally straight boundary
through wet ground.

**Interaction:** Place three harmless marker reeds along the line and compare it
with an abandoned Compact anchor footprint. Leave the burrows untouched.

**Character beat:** Koga's tracker trusts Nincada because they followed the soil
change, not anyone's orders.

**Reward and aftermath:** Tracker supplies and optional nonessential lore about
an earlier test boundary.

## `EVT-G5-GRIMER-FILTER` — The Clean Side

**Visible hook:** A Grimer sits beside a clogged reed filter while clear water
flows around it. Workers assume it caused the blockage.

**Interaction:** Inspect the upstream grate and find cloth debris there. Clear
the grate, then add a low sunning stone beside the filter for Grimer.

**Character beat:** The filter worker apologizes to Grimer before apologizing to
the coworker who blamed it.

**Reward and aftermath:** Marsh utility supplies. The filter runs and Grimer
returns to the warm stone.

## `EVT-G5-VENONAT-LANTERNS` — Purple Glass

**Visible hook:** Venonat cluster around one purple field lantern and ignore
five white ones, leaving a medicine path unevenly lit.

**Interaction:** Fit supplied purple covers onto two lamps away from the walking
line. The Venonat spread out and clear the central route.

**Character beat:** The lamp keeper calls this “advanced color theory” to avoid
admitting the solution was more purple lamps.

**Reward and aftermath:** A lantern cosmetic and night-travel supplies. No event
requires waiting for night; the covers are readable in shade.

## `EVT-G5-WOOPER-SLUICE` — Mud Where It Belongs

**Visible hook:** Wooper have packed mud against a small drainage gate, flooding
a herb-drying yard while improving their own pool.

**Interaction:** Open a parallel shallow channel into an unused basin and move
one mud marker there. The Wooper follow the new wet edge; workers clear the gate.

**Character beat:** The herbalist accepts that the Wooper made an excellent pond
in a terrible workplace.

**Reward and aftermath:** Herbs and a permanent side pool. The main yard drains.

## `EVT-G5-SKORUPI-BASKET` — Handle With Gloves

**Visible hook:** A gathering basket moves by itself through tall grass because
a Skorupi is carrying it from underneath.

**Interaction:** Place the worker's padded tray beside the basket and transfer
three fragrant herb bundles onto it. Skorupi follows the scent out and releases
the basket.

**Character beat:** The gatherer is less worried about the stinger than about
Skorupi's strong opinions on herb quality.

**Reward and aftermath:** A medicine ingredient and protective gloves cosmetic.
Skorupi remains a wild ambient actor.

# Route 6 — Koga to Sabrina

**Route context:** Approximately 1,944 blocks through Glacier Foot Fields and
Marsh Creek. The route passes the marsh-to-lake transition and reaches Lake Tilpey's north
terrace without a required water crossing.

## `EVT-R6-BERGMITE-REFLECTION` — False Trail Light

**Visible hook:** Blue route reflectors appear to continue onto the ice because
Bergmite faces are mirroring them from below the slope.

**Interaction:** Add a second reflector color to the true landward edge and turn
one marker away from the ice.

**Character beat:** The guide insists the Bergmite are not misleading anyone;
they are standing still extremely convincingly.

**Reward and aftermath:** Cold-route supplies and a safer visible trail edge.

## `EVT-R6-SNORUNT-CAIRN` — Snowball Offering

**Visible hook:** A small travel cairn contains snowballs where every loose stone
should be. Snorunt wait nearby with another replacement ready.

**Interaction:** Build a second low snow cairn beside the route and mark the
stone cairn with a warm-colored cloth that Snorunt avoid.

**Character beat:** The route keeper has rebuilt the cairn three times and only
just realized the snowballs were arranged by size.

**Reward and aftermath:** A shrine-style cosmetic and cold-weather food. Snorunt
maintain their own cairn.

## `EVT-R6-QUAGSIRE-BOARDWALK` — Missing Board, Present Quagsire

**Visible hook:** Quagsire sits comfortably in a gap where one plank washed out
from an optional marsh-lookout boardwalk. The dry shoreline route remains open
beside it.

**Interaction:** Build the replacement section beside Quagsire first, then place
a berry on the adjacent mud shelf. Quagsire moves without being shoved.

**Character beat:** The maintenance worker nearly thanked Quagsire for filling
the gap before remembering people cannot walk on it.

**Reward and aftermath:** Marsh travel supplies. Quagsire keeps the new mud
shelf and the boardwalk becomes safe.

## `EVT-R6-GLACIER-BELL` — Ice in the Mouth

**Visible hook:** A weather bell swings in strong wind without making sound. Its
clapper is frozen inside a clear sleeve of ice.

**Interaction:** Redirect a small dark heat panel toward the sleeve, then stop
heating when the marked drip tray fills. Breaking the bell is never offered.

**Character beat:** The weather keeper says a silent warning bell is “more of a
sculpture than a system.”

**Reward and aftermath:** Weather notes and a bell-token cosmetic. The restored
bell becomes route ambience.

## `EVT-R6-DRIFBLIM-BALLOON` — Tether Dispute

**Visible hook:** A weather balloon and a Drifblim pull opposite ends of the same
ribbon above a survey camp.

**Interaction:** Release the balloon's spare lower tether and attach it to a
visible ground ring. Drifblim keeps the bright ribbon while the instrument stays
secured.

**Character beat:** The surveyor objects to calling it theft because Drifblim
has been holding half the equipment in the air all morning.

**Reward and aftermath:** Survey supplies and a weather-balloon map note.
Drifblim leaves with the ribbon and is not catchable.

## `EVT-R6-MUNNA-REST` — Somebody Else's Nap

**Visible hook:** Three travelers wake from the same short rest describing the
same unfamiliar kitchen. Munna sleeps beneath the bench.

**Interaction:** Move the travelers to three separate marked bedrolls and place
a calming incense candidate at Munna's sheltered spot. Each reports their own
ordinary dream afterward.

**Character beat:** Nobody treats the shared dream as prophecy. One traveler is
mostly concerned that the kitchen had no doors.

**Reward and aftermath:** Rest supplies and a dream-journal cosmetic. This is an
optional echo of regional memory disturbance, not required Hoopa evidence.

# Sabrina's town — Tilpey North Shore

**Town context:** Centre (6196, 3398), on the terrace above Lake Tilpey where the
Glacial Tear and major river meet. Ferries, refugees, observers, and long-route
travelers converge here.

## `EVT-G6-SLOWPOKE-FERRY` — The Ferry Is Thinking

**Visible hook:** A ceremonial ferry launch waits for Slowpoke to step aboard.
Slowpoke sits at the end of the dock facing away from the boat.

**Interaction:** The player may wait through a short dialogue cycle, offer the
approved snack, or move the ribbon ceremony around Slowpoke. Every patient
choice succeeds without pushing it.

**Character beat:** The ferrier eventually admits the boat does not need
Slowpoke; the town invited it and then invented a schedule.

**Reward and aftermath:** A patience-themed charm candidate. The ferry launches
and Slowpoke remains on the dock by choice.

## `EVT-G6-DREAM-SKETCH` — Someone Else's Party

**Visible hook:** A child sketches one of the player's current party Pokémon
before being shown it.

**Interaction:** Compare the sketch with the party, then let the player choose
whether to show the Pokémon, describe it, or keep the resemblance private.

**Character beat:** Sabrina treats the event as ordinary local sensitivity, not
a prophecy or command.

**Reward and aftermath:** A personalized sketch cosmetic. No party species or
player response changes progression.

## `EVT-G6-ABRA-QUEUE` — Back of the Line

**Visible hook:** Abra repeatedly teleports from the front of a service queue to
the back whenever a clerk calls its number.

**Interaction:** Place the numbered floor mat at the back position Abra already
prefers and have the clerk serve the queue in reverse for one turn.

**Character beat:** The clerk refuses to call this priority service because Abra
has technically waited in every position.

**Reward and aftermath:** A service voucher and town supplies. Abra finishes its
errand and naps beside the office.

## `EVT-G6-MIME-JR-CROSSING` — The Wall Is Real Enough

**Visible hook:** Travelers stop at an empty crosswalk because Mime Jr. performs
an invisible wall across it whenever carts approach.

**Interaction:** Observe that the performance starts only for unsafe crossings.
Place two visible stop markers where Mime Jr. stands and teach the cart driver
the new pause signal.

**Character beat:** The driver dislikes taking traffic instruction from a mime
until shown the accident log.

**Reward and aftermath:** A crossing-sign cosmetic and a safer town street. Mime
Jr. continues performing beside the real markers.

## `EVT-G6-CHIMECHO-BELL` — One Note Underwater

**Visible hook:** Chimecho hum around a lakeside bell frame, but one note answers
from beneath the dock.

**Interaction:** Follow the harmonics to a fallen hand bell in shallow water and
raise it with the dock's basket line rather than swimming after it.

**Character beat:** The bell keeper thought the low note was an omen and is
relieved it was poor inventory control.

**Reward and aftermath:** A sound-themed cosmetic and lake supplies. The restored
bell joins the Chimecho ambience.

## `EVT-G6-ASTER-LANTERN` — A Window for Home

**Visible hook:** Jo Aster tries several places for a small lantern made from
material carried out of the family's collapsing world. None can be seen from
the refugee lodging.

**Interaction:** Test the market rail, ferry post, and lakeside terrace. Choose
the terrace where the lantern is visible from both the lodging and shore
without interfering with navigation.

**Character beat:** Jo does not claim the light can reach the old world. He only
wants the family to know which direction to look together.

**Reward and aftermath:** A small lantern keepsake and new optional dialogue from
Mila and Dev Aster. The scene strengthens the Compact's human cost without
asking the player to approve another forced exchange.

# Distribution rules

1. Place two obvious events on each route and four on short, readable spurs or
   rest areas. Long Route 4 needs visible intervals more than clustered density.
2. Erika's events alternate gardens, households, shelter work, and observation.
   Koga's alternate medicine, marsh infrastructure, tracking, and Pokémon
   behavior. Sabrina's alternate civic life, ferries, perception, and refugees.
3. Worldshift and Compact details remain optional echoes. Required facts still
   come from each town's main sequence.
4. The same Pokémon should not appear as a curated capture reward in multiple
   midgame events without an encounter-table reason.
5. No optional event changes the state of the impossible channel, Glacial Tear,
   major river, Lake Tilpey, or gorge.
6. Exact placement follows final roads, town services, gym footprints, and
   faction staging areas.

# Reusable implementation families

- **Choose or prepare a destination:** Deerling gate, Oddish bed, Combee hive,
  Tangela path, Wooper basin, Quagsire shelf, Aster lantern.
- **Return, trade, or recover a prop:** Delibird parcel, Applin basket, Croagunk
  bottles, Skorupi basket, glacier bell, Drifblim ribbon, Chimecho bell.
- **Inspect and classify:** shared maps, fossil-like trail evidence, herb
  markers, Nincada boundary, Bergmite reflectors, dream sketch.
- **Reroute without harming Pokémon:** Caterpillar-style crossings, Ariados web,
  Venipede log, Sewaddle canopy, Mime Jr. crosswalk.
- **Short environmental sequence:** Roselia ribbons, Shroomish markers, Grimer
  filter, Venonat lanterns, Munna rest positions.

These families are design groupings. No compatible runtime implementation is
claimed until an experiment proves it.