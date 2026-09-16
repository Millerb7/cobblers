# Early-Game Event Bank — Pallet through Gym 3

**Status:** Proposed event bank. These twenty-eight scenes supplement the
fourteen encounters in `EARLY_GAME_ENCOUNTERS.md`. Exact placement, runtime
mechanisms, item IDs, and Pokémon levels remain unverified.

These are deliberately smaller than full sidequests. Most should take one to
five minutes, and several exist mainly to make a road or town feel occupied.
They never gate the route, gym, story, healing, or PC access.

## Density target

| Area | Existing detailed events | Added here | Total |
| --- | ---: | ---: | ---: |
| Pallet | 3 | 4 | 7 |
| Route 1 | 2 | 4 | 6 |
| Brock's town | 2 | 4 | 6 |
| Brock-to-Misty road | 1 | 4 | 5 |
| Misty's town | 2 | 4 | 6 |
| Misty-to-Surge climb | 2 | 4 | 6 |
| Surge's town | 2 | 4 | 6 |
| **Total through Gym 3** | **14** | **28** | **42** |

Not all forty-two events need equal visual weight. Large silhouettes belong to
the crushed house and ghost mansion. Most additions below need one small prop
cluster, one or two actors, and a clear interaction.

# Pallet Town

## `EVT-PALLET-FENCE-LINE` — Property Damage

**Visible hook:** A length of fence from one yard landed across the neighboring
garden. Both owners agree whose fence it is and disagree whose problem it is.

**Interaction:** Carry three loose posts to the painted line while the owners
give contradictory instructions. Any straight placement completes the job;
their argument continues over whether it is two inches wrong.

**Character beat:** “We survived the sky folding. We are not surviving this
setback.”

**Reward and aftermath:** Basic building blocks and a small food bundle. The
repaired fence remains slightly crooked, and both owners blame the other.

## `EVT-PALLET-LOST-LAUNDRY` — Not Ours

**Visible hook:** Clothing hangs from a tree at the exchanged edge, including a
bright shirt nobody in Pallet recognizes.

**Interaction:** Return three familiar pieces to residents. The unknown shirt
stays unclaimed and gets pinned to Oak's evidence line as an ordinary unresolved
object, not a major clue.

**Character beat:** One resident insists the shirt is Gary's. Gary denies ever
owning anything that ugly.

**Reward and aftermath:** Food and a cosmetic cloth item candidate. The unknown
shirt becomes a recurring background prop.

## `EVT-PALLET-PIDGEY-POST` — Same Roof, Wrong Sky

**Visible hook:** A courier Pidgey circles Pallet repeatedly and lands on the
wrong roofs because the surrounding skyline no longer matches its route.

**Interaction:** Place three colored route markers on the post office, Oak's
lab, and the town exit. Pidgey flies the short circuit successfully after the
markers are visible.

**Character beat:** The postmaster never blames Pidgey: “The bird remembers the
route. The horizon is the part that moved.”

**Reward and aftermath:** Courier supplies and access to short flavor notes from
residents. Pidgey repeats the local circuit as town ambience.

## `EVT-PALLET-BULBASAUR-BOX` — Wrong Side of the Sun

**Visible hook:** A Bulbasaur keeps dragging the same heavy window box across a
porch. The house's new shadow falls where morning sun used to reach.

**Interaction:** Test three marked spots and choose the one receiving open sky
without blocking the path. Bulbasaur settles beside it and stops scraping the
porch.

**Character beat:** The owner says the plant has occupied that window longer
than anyone remembers and refuses to call the move “repotting.”

**Reward and aftermath:** Seeds, common berries, and a small gardening callback
later. Bulbasaur is an owned actor, not a capture reward.

# Route 1 — Pallet to Brock

## `EVT-ROUTE1-CATERPIE-CROSSING` — Green Traffic

**Visible hook:** A slow line of Caterpie crosses the road toward a patch of
fresh leaves while two travelers wait on opposite sides.

**Interaction:** Move two fallen branches into a short leaf-covered crossing
beside the road. The Caterpie turn onto it, clearing the main path without being
attacked or collected.

**Character beat:** One traveler is impatient until a Caterpie climbs onto their
boot and falls asleep.

**Reward and aftermath:** Common berries and a Bug-type encounter marker deeper
in the grove, subject to route balance.

## `EVT-ROUTE1-RATTATA-PICNIC` — Lunch Tax

**Visible hook:** An open picnic basket is surrounded by tiny pawprints leading
to three nearby hiding places.

**Interaction:** Recover the wrapped lunch from the correct hiding place by
following crumbs. Leave a spare berry at the empty stump so the Rattata stop
returning to the basket.

**Character beat:** The owner is more offended by the neat unwrapping than the
theft.

**Reward and aftermath:** A food bundle and low-value capture supplies. Rattata
occasionally inspect the stump afterward.

## `EVT-ROUTE1-BUG-NET` — Catch and Release the Net

**Visible hook:** A bug catcher's net moves through tall grass with nobody
holding it.

**Interaction:** Follow the moving handle and find a Metapod caught in the hoop
while trying to climb through it. Brace the net and rotate it free; pulling
straight makes no progress but causes no harm.

**Character beat:** The embarrassed catcher has spent ten minutes tracking the
net and never considered that the net had caught itself.

**Reward and aftermath:** Repellent or field supplies and a route-tip dialogue
about the nearby Bug habitat. Metapod remains wild and leaves.

## `EVT-ROUTE1-SENTRET-WATCH` — The Second Lookout

**Visible hook:** A Sentret stands on a stump mirroring a nervous traveler's
every movement. A second Sentret watches from the opposite side of the path.

**Interaction:** Turn toward each Sentret in sequence until both point toward a
dropped satchel hidden in grass. Return it to the traveler.

**Character beat:** The traveler thought the first Sentret was mocking them. It
was trying to make them look the other way.

**Reward and aftermath:** The recovered travel supplies are split with the
player. Both Sentret return to their lookout stumps.

# Brock's town

## `EVT-G1-SANDSHREW-BATH` — Reserved Pile

**Visible hook:** A Sandshrew rolls happily in the exact sand pile the masons
need for mortar.

**Interaction:** Build a second dust bath from loose dry material and place one
sun-warmed stone in it. Sandshrew moves voluntarily; shoveling the occupied pile
is refused.

**Character beat:** The mason marked the original pile “urgent” after Sandshrew
had already marked it by sleeping there.

**Reward and aftermath:** Mason supplies and a controlled Sandshrew encounter
lead nearby, pending pre-Brock balance review.

## `EVT-G1-ONIX-SHADE` — Twenty Feet of Break Time

**Visible hook:** An Onix lies across an unused quarry spur, trying to fit its
head under a shade tarp designed for one person.

**Interaction:** Extend the tarp between three existing posts. No heavy lifting
or battle is required; the puzzle is choosing the posts that cover Onix without
blocking the work road.

**Character beat:** The foreman points out that everyone else received a lunch
break and Onix apparently read the schedule.

**Reward and aftermath:** Quarry access supplies and a shaded rest spot used by
workers and Pokémon. Onix is a crew partner, not catchable.

## `EVT-G1-FOSSIL-CASTS` — Extremely Ancient Plaster

**Visible hook:** A museum volunteer has mixed three plaster fossil casts with
ordinary quarry rocks and is treating all six as priceless.

**Interaction:** Match each cast to its labeled display using shape, tool marks,
and the plaster dust beneath it. The real rocks return to the builder's cart.

**Character beat:** One “prehistoric tooth” is clearly the broken handle from a
mug. The volunteer remains unconvinced.

**Reward and aftermath:** A replica fossil cosmetic and a museum note. No real
fossil or fossil Pokémon is awarded this early.

## `EVT-G1-SHUCKLE-PRESS` — Do Not Rush It

**Visible hook:** A berry seller pumps a small press while Shuckle watches from
beside three sealed jars. Nothing comes out.

**Interaction:** Read the dated jar labels and choose the batch that has rested
long enough. The newest jars remain sealed; using them is rejected without
consuming anything.

**Character beat:** The seller built a machine to speed up the one partner whose
entire method is waiting.

**Reward and aftermath:** Berry drinks and a small discount at the stall. Shuckle
keeps ownership of every jar.

# Brock-to-Misty road

## `EVT-ROUTE2-BONSLY-MILESTONE` — Very Convincing Tree

**Visible hook:** A newly painted route marker has apparently grown feet and is
quietly moving away from the road.

**Interaction:** Follow the “marker” to discover Bonsly imitating it. Place the
real marker from the grass back into its stone socket and leave Bonsly beside a
smaller decoy post.

**Character beat:** The road worker refuses to discuss how long they spent
painting Bonsly before noticing.

**Reward and aftermath:** Route supplies and a harmless fake milestone cosmetic.
Bonsly continues copying the decoy.

## `EVT-ROUTE2-BELLSPROUT-GAUGE` — Chance of Plants

**Visible hook:** A rain gauge reads full on a clear day because a Bellsprout has
rooted inside it.

**Interaction:** Prepare an adjacent damp soil patch and redirect a small drip
line to it. Bellsprout moves when the new patch is wetter than the gauge.

**Character beat:** The weather keeper has published “one hundred percent rain”
for three days and blames the instrument professionally.

**Reward and aftermath:** Weather supplies and a controlled Bellsprout encounter
lead, pending pre-Misty balance review.

## `EVT-ROUTE2-NINCADA-ROAD` — Quiet Underfoot

**Visible hook:** A maintenance worker hears scratching beneath a cracked side
path and has roped it off before the surface collapses.

**Interaction:** Tap three marked stones to locate the hollow section, then move
the rope around it. A Nincada emerges from the safe shoulder after traffic stops
crossing its tunnel.

**Character beat:** The worker values the road and the burrow equally: “Both
were here before my shift started.”

**Reward and aftermath:** Repair materials and a marked safe shortcut. Nincada
is not automatically offered as a capture.

## `EVT-ROUTE2-MUDBRAY-BOOT` — Keep the Other One

**Visible hook:** A hiker wears one boot and carries the matching sock. Mudbray
stands nearby with the missing boot stuck loosely over one hoof.

**Interaction:** Lead Mudbray across a shallow mud patch so the suction holds
the boot while it steps free. Pulling directly is refused because it scares the
Pokémon.

**Character beat:** The hiker admits the boot was stolen only after they tried
to ride Mudbray without asking.

**Reward and aftermath:** Climbing food and spare leather. Mudbray follows the
hiker at a deliberately judgmental distance.

# Misty's town

## `EVT-G2-AZURILL-ECHO` — One Echo Too Many

**Visible hook:** In the town square, an Azurill bounces beside an old stone
cistern. Each bounce produces a normal echo and a second hollow knock from
beneath one paving stone.

**Interaction:** Listen from three painted maintenance marks, then identify the
stone producing the delayed echo. A mason lifts it and finds a small washed-out
void before it can undermine the square.

**Character beat:** Children have been using the double echo as part of a
clapping game and are disappointed that the repair will make it sound normal.

**Reward and aftermath:** Town-square food and a small music-token cosmetic.
Azurill remains for the children's new, less structurally concerning game.

## `EVT-G2-CORPHISH-TOOLS` — Borrowed Forever

**Visible hook:** A mechanic reaches into an empty toolbox while Corphish stacks
wrenches by size beneath the dock.

**Interaction:** Trade three shiny washers from the mechanic for the three tools
Corphish collected. Choosing a tool before placing its washer makes Corphish
cover it but does not start a fight.

**Character beat:** The mechanic is annoyed that Corphish's sorting system is
better than theirs.

**Reward and aftermath:** Repair supplies and access to a small dock cache. The
washers remain as Corphish's new collection.

## `EVT-G2-FINNEON-LAMPS` — Lights Below

**Visible hook:** A row of unlit dock lamps flickers whenever Finneon swim under
the boards.

**Interaction:** Rotate three reflective plates so the Finneon's natural light
reaches the dock markers. The shaded boathouse makes the effect readable at any
time of day.

**Character beat:** A child insists the fish repaired the lamps. The electrician
allows this version of events.

**Reward and aftermath:** A luminous dock keepsake and a Finneon habitat marker
for later fishing or encounters, subject to route balance.

## `EVT-G2-SHELLOS-PAINT` — Fresh Coat

**Visible hook:** At a pottery yard away from the docks, wet glaze samples are
covered in small Shellos tracks. The Shellos now match several test tiles.

**Interaction:** Follow the color sequence to identify the glaze chosen for a
public fountain sign. Wash the chosen tile before handing it to the potter.

**Character beat:** The potter calls the tracks contamination until a child
calls them signatures.

**Reward and aftermath:** A signed decorative tile and colored building
materials. The Shellos remain harmless workshop visitors.

# Misty-to-Surge climb

## `EVT-ROUTE3-MAREEP-SHELTER` — Static in the Rain

**Visible hook:** A shepherd has moved the flock under rock cover, but one Mareep
stands beneath a metal trail frame with its wool sparking.

**Interaction:** Lower a nearby rope gate to create a path toward the stone
shelter, then remove the loose metal bell from the destination fence. Mareep
walks across once the route is clear.

**Character beat:** The shepherd is calm about the sparks and furious about who
put a metal bell on a mountain storm route.

**Reward and aftermath:** Wool, weather supplies, and a Mareep encounter lead
away from the owned flock, pending balance review.

## `EVT-ROUTE3-SPOINK-PEARL` — Do Not Stop Bouncing

**Visible hook:** A Spoink bounces in one tiny circle beside a pearl wedged under
a flat rock.

**Interaction:** Place a soft bedroll beside Spoink, lift the rock with the
visible lever branch, and roll the pearl back without forcing Spoink to stop.

**Character beat:** The nearby camper gives increasingly useless advice while
refusing to touch the bouncing Pokémon.

**Reward and aftermath:** A small Psychic-type utility item candidate and the
camper's spare supplies. Spoink leaves with its pearl.

## `EVT-ROUTE3-SWABLU-NEST` — Blue Thread

**Visible hook:** Blue fibers trail from a torn route flag into a low cliff nest.
Swablu have used the cloth to reinforce it before a storm.

**Interaction:** Gather three pieces of soft fallen plant fiber and place them
near the nest. The Swablu exchange the route cloth for the safer material.

**Character beat:** The guide wants the flag back but admits the birds improved
its stitching.

**Reward and aftermath:** The repaired route flag makes an optional sheltered
viewpoint easier to see; the player receives feathers and climbing supplies.
The viewpoint has a bench but no healing, PC, progression flag, or route unlock.
Equivalent route access remains unchanged on the main path.

## `EVT-ROUTE3-SABLEYE-REFLECTORS` — Shiny Way Down

**Visible hook:** Every reflective trail marker has vanished from a dim rock
cut. Glints appear from a shallow side cavity.

**Interaction:** Offer three ordinary polished stones from a maintenance box in
exchange for the reflectors. Place the recovered markers along the correct side
of the descent.

**Character beat:** Sableye examines each replacement like a jeweler and rejects
one chipped stone until the player turns its polished face outward.

**Reward and aftermath:** A marked safe descent and a small mineral cache.
Sableye remains a rare noncapture actor; this event does not grant early access
to it.

# Surge's town

## `EVT-G3-PLUSLE-MINUN-GRID` — Same Time, Please

**Visible hook:** Plusle celebrates every powered lamp while Minun switches the
previous lamp off. A technician is trapped in an endless demonstration.

**Interaction:** Activate three paired switches in matching order so both
Pokémon receive a cue at the same time. A mismatched pair resets only that pair.

**Character beat:** The technician has stopped saying “positive” and “negative”
because both Pokémon assumed positive meant praise.

**Reward and aftermath:** Electrical supplies and a synchronized lamp display
that repeats as town ambience.

## `EVT-G3-SKIDDO-ROOF` — Rooftop Grazing

**Visible hook:** A Skiddo has climbed onto a low terrace garden and is eating
only the herbs planted closest to the dangerous outer edge.

**Interaction:** Build a lower feeding rack from supplied fence pieces, then
move matching herb cuttings onto it. Skiddo follows the food down without being
pushed, leashed, or battled.

**Character beat:** The gardener is less surprised that Skiddo reached the roof
than that it ignored every expensive flower on the way.

**Reward and aftermath:** Cooking herbs and a small seed bundle. Skiddo remains
an owned town actor and naps beside the lower rack.

## `EVT-G3-ELECTRIKE-CABLE` — Inspection Run

**Visible hook:** Electrike races beside a cable trench and barks at the same
covered section every lap.

**Interaction:** Follow one complete lap, mark the barked section, and use the
technician's tester there. The cable is intact; a metal tag beneath the cover is
vibrating during signal pulses.

**Character beat:** The technician apologizes for assuming Electrike only wanted
to race. Electrike immediately starts another lap.

**Reward and aftermath:** A technical supply bundle and an Electrike habitat
lead for later encounter balancing. The event hints at the signal problem
without replacing Surge's required evidence.

## `EVT-G3-EMOLGA-WINDSOCK` — Unauthorized Upgrade

**Visible hook:** The town windsock now hangs between two trees because Emolga
have carried away its bright fabric strips for gliding markers.

**Interaction:** Place dull spare streamers on three safe branches. The Emolga
move their bright strips to the higher marked glide line, allowing the resident
to recover the windsock tail.

**Character beat:** The weather observer admits the Emolga selected a better
wind corridor than the official survey.

**Reward and aftermath:** A repaired windsock cosmetic and an accurate mountain
wind note. Emolga continue using the safe glide line.

# Multiplayer and reward contract

These rules apply to every event in this bank and are behavior requirements,
not claims about an implemented system.

1. Completion and reward claims are persistent per-player flags. The flag is
   recorded before the reward is granted so reconnecting cannot duplicate it.
2. Shared props may animate or remain in their completed pose, but they never
   carry the only interaction needed by an unfinished player. Each event keeps
   an NPC replay prompt, inspection marker, or reset lever that exposes the same
   decisions without reversing another player's completion.
3. Two players may investigate together. Interactions are credited separately;
   submitting an item or choosing the answer for one player does not consume or
   complete the other player's copy.
4. A late joiner receives the full interaction in a short reenactment state if
   the shared scene has advanced. Completed players receive ambient dialogue
   only and cannot claim the reward again.
5. Event Pokémon used as shared actors are never the capture reward. Any
   controlled capture is a separate per-player encounter and does not alter the
   shared actor.
6. These behaviors require a two-player, reconnect, and late-join experiment
   before implementation is considered verified.

**Reward budget:** Every reward is one-time per player. Until the early economy
is reviewed, “supplies” means a placeholder bundle worth no more than a small
route pickup, and held-item candidates are not approved items. Sandshrew,
Bellsprout, Mareep, and all other encounter leads are proposals only; they do
not add a species, level, moveset, or repeatable capture to the route until the
Gym 1–3 trainer and encounter review approves them.

# Distribution rules

1. Do not place every event directly on the road. Each route should have two
   obvious scenes and the rest on short, readable spurs.
2. Town events should be visible from ordinary services or the gym approach,
   while leaving those services uncluttered.
3. No area should play several rescue emergencies in a row. Alternate comedy,
   observation, helping work, Pokémon behavior, and exploration.
4. Only Sandshrew, Bellsprout, Mareep, and selected existing core events are
   candidate controlled encounters. The rest provide supplies, ambience,
   callbacks, or habitat knowledge.
5. Repeat actors remain useful after completion through short ambient dialogue,
   movement, or a changed prop state.
6. Late joiners receive the same completion and reward path even if shared
   scenery shows the event's completed form.
7. Exact coordinates are assigned only after road, town, gym, and service
   footprints are final.

# Implementation grouping

Build and test these as reusable families rather than twenty-eight unrelated
systems:

- **Return or trade a prop:** laundry, picnic, Corphish tools, Spoink pearl,
  Sableye reflectors.
- **Choose a safe destination:** Bulbasaur box, Caterpie crossing, Sandshrew
  bath, Onix shade, Bellsprout gauge, Psyduck cove, Mareep shelter, Skiddo rack.
- **Inspect and match:** fossil casts, salvage objects, Azurill echoes, Shellos
  glaze, trail signs, cable inspection.
- **Short ordered input:** Pidgey markers, pebble lane, Finneon mirrors,
  Plusle/Minun switches, kite line.
- **Follow a visible trail:** Rattata picnic, Sentret lookout, runaway Geodude,
  Mudbray boot, Swablu nest.

This grouping is a content-design recommendation, not a claim that a compatible
runtime system already exists.