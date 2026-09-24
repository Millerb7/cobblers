# Early-Game Event Bank — Pallet through Gym 3

**Status:** Reconciled event bank. These twenty-one scenes supplement the
fourteen encounters in `EARLY_GAME_ENCOUNTERS.md`. Route 1–3 membership and
positions are settled in `EARLY_ROUTE_RECONCILIATION.md`; runtime mechanisms,
item IDs, and Pokémon levels remain unverified.

These are deliberately smaller than full sidequests. Most should take one to
five minutes, and several exist mainly to make a road or town feel occupied.
They never gate the route, gym, story, healing, or PC access.

## Density target

| Area | Existing detailed events | Added here | Total |
| --- | ---: | ---: | ---: |
| Pallet | 3 | 4 | 7 |
| Route 1 | 2 | 2 | 4 |
| Brock's town | 2 | 4 | 6 |
| Brock-to-Misty road | 1 | 2 | 3 |
| Misty's town | 2 | 4 | 6 |
| Misty-to-Surge climb | 2 | 1 | 3 |
| Surge's town | 2 | 4 | 6 |
| **Total through Gym 3** | **14** | **21** | **35** |

Not all thirty-five events need equal visual weight. Large silhouettes belong to
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

## `EVT-ROUTE1-FIRST-CAST` — First Cast

**Placement:** a signed coastal spur to the jetty at `(1066, 5349)`, about 400
blocks from Route 1's origin. This uses real ocean water; the River of Shrews
vale is dry in the current terrain.

**Visible hook:** A fisher works from a small timber jetty while an unused rod
rests in the tackle rack. The coast and nearby islets make the detour legible
from the approach without putting it on the critical road.

**Interaction:** Speak to the fisher, inspect the water and tackle rack, then
receive one basic rod. The event ends after the first cast or after the player
confirms they want to leave fishing for later.

**Character beat:** The fisher treats patience as a route skill: “Roads show
you where to walk. Water makes you decide where to wait.”

**Reward and aftermath:** One `minecraft:fishing_rod` per player, once. The
jetty remains a reusable fishing site. Actual catches, Habitat Block fishing
replacement, and Only Bottle Caps' 3% silver Bottle Cap treasure chance still
need a production balance proof.



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





## `EVT-ROUTE2-VILTRI-SOUNDING` — Viltri Sounding

**Placement:** shore station at (1779, 3011), route distance 636.1, after the
road enters Lake Viltri Hollow.

**Visible hook:** Three depth staffs disagree, and a floating gauge drifts at
the end of a loose tether while Lotad use the one safe shelf between them.

**Interaction:** Read the three water lines, follow the Lotad shelf, and reset
the gauge after finding Corphish claw marks on the loosened knot.

**Character beat:** The shore keeper treats the first lake view as something
worth learning rather than scenery to sprint through: “Look at the banks before
the map.”

**Reward and aftermath:** Regional food and ordinary shore supplies. The gauge
remains aligned and the platform becomes a readable Lake Viltri stop; no
special species is granted.

## `EVT-VILTRI-NORTH-BANK` — The Other Shore

**Placement:** Lake Viltri north bank at `(1604, 3068)`, 184.1 blocks from the
Route 2 anchor `(1779, 3011)` and 267 blocks from Route 3's origin. It is a
shared optional destination for the end of Route 2 and beginning of Route 3.

**Visible hook:** A small platform, beached skiff and net rack sit across the
water from the sounding station. An angler waits where the bank narrows.

**Interaction:** Follow the short ring trail around the lake, challenge the
North Bank Angler's Krabby and Shellder, then speak again after a player win.

**Character beat:** “Most people see Viltri from the south road and think they
have seen the lake. The north bank disagrees.”

**Reward and aftermath:** One `cobblemon:lure_ball` per player after their first
verified win. The reward is issued by the quest dialogue, never a shared
trainer bag, and the platform remains an optional fishing and rest landmark.

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

`route_03_misty_to_surge` is a long approach followed by a real ascent. Read
the current figures from `data/routes.json`; at the 2026-09-16 regeneration the
leg ran roughly 2,100 blocks and climbed roughly 80, with no step steeper than
35 degrees. The shape matters more than the numbers. Parts below come from the
simplified route polyline and are approximate:

- **Lake Viltri Hollow and Foothill Woods, about the first 70%.** Near-level
  lakeside road, then a long forest rise of roughly 20 blocks spread over more
  than a kilometre. The Nosepass signs sit at the end of this stretch.
- **The pond, Mt Clay's western foot, and the edge of Mt Vessu, about the next
  20%.** The trees thin and the road gains roughly another 20 blocks.
- **The Tri Peaks grade, under 10% of the length.** Roughly 30 blocks of ascent
  in under 200 blocks of road: the steepest and most exposed part of the leg,
  a graded switchback line up the south flank to Surge's shelf. It is a
  sustained climb on a built trail, not a scramble. Players should feel the
  height without needing ladders, jumps, or hands.
- **The shelf lip, roughly the final 70 blocks.** Level ground; the summits come
  into view on arrival. This is a scenery moment and deliberately carries no
  event, NPC, prompt, or reward. Nothing in this bank may be placed on it.

The two detailed encounters share one stop at the pond shore: the Wooper
scene at (2204, 1580) sits about 32 blocks from the Nosepass signs at
(2186, 1606), route distance 1469. Swablu marks the later forest-to-mountain
transition. The final shelf lip remains empty.


## `EVT-ROUTE3-SWABLU-NEST` — Blue Thread

**Placement:** a low cut bank where the road leaves the woods at Mt Clay's
western foot, the first place the climb becomes visible ahead.

**Visible hook:** Blue fibers trail from a torn route flag into a nest in the cut
bank. Swablu have used the cloth to reinforce it before a storm.

**Interaction:** Gather three pieces of soft fallen plant fiber and place them
near the nest. The Swablu exchange the route cloth for the safer material.

**Character beat:** The guide wants the flag back but admits the birds improved
its stitching.

**Reward and aftermath:** The repaired flag marks an optional sheltered rest
bench a short way up the grade; the player receives feathers and climbing
supplies. The bench has no healing, PC, progression flag, or route unlock, and
it must not be the shelf lip. Route access is unchanged.



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

Build and test these as reusable families rather than twenty-one unrelated
systems:

- **Return or trade a prop:** laundry, picnic, Corphish tools, Spoink pearl,
  Sableye reflectors.
- **One-time personal unlock:** First Cast rod and North Bank Lure Ball.
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
