# Early-Game Encounters — Pallet through Gym 3

**Status:** Narrative and gameplay design complete. Exact placement, item IDs, NPC
IDs, and event-state implementation remain unverified.

This package fills the required path from Pallet through Surge with optional,
small encounters. These are not gym gates or story requirements. The player
should understand each problem by looking at the scene before reading dialogue.

## Encounter map

| Chapter | Event | Intended duration | Main value |
| --- | --- | ---: | --- |
| Pallet | `EVT-PALLET-CRUSHED-HOUSE` | 8–15 min | Character comedy; Miracle Seed charm |
| Pallet | `EVT-PALLET-SALVAGE-LINE` | 3–5 min | Town life; basic supplies |
| Pallet | `EVT-PALLET-CORNER-MON` | 2–4 min | Gentle rescue; berries |
| Route 1 | `EVT-ROUTE1-GASTLY-FAMILY` | 15–25 min | Ghost side dungeon; Gastly lead |
| Route 1 | `EVT-ROUTE1-THIRSTY-STRANGER` | 3–6 min | Character joke; held-item candidate |
| Brock | `EVT-G1-MACHOP-SHIFT` | 5–8 min | Worksite scene; Machop encounter |
| Brock | `EVT-G1-PEBBLE-LEAGUE` | 3–5 min | Town minigame; local ribbon |
| Brock to Misty | `EVT-ROUTE2-ROLLAWAY-GEODUDE` | 5–8 min | Route chase; mining supplies |
| Misty | `EVT-G2-PSYDUCK-LAUNCH` | 4–6 min | Environmental solution; water supplies |
| Misty | `EVT-G2-POLIWAG-COUNT` | 3–5 min | Search scene; Poliwag encounter |
| Misty to Surge | `EVT-ROUTE3-CREEK-WOOPER` | 6–10 min | Creek puzzle; Ground-type answer |
| Misty to Surge | `EVT-ROUTE3-NOSEPASS-SIGNS` | 5–8 min | Mountain navigation; signal foreshadowing |
| Surge | `EVT-G3-MAGNEMITE-BOLTS` | 5–8 min | Town puzzle; electrical supplies |
| Surge | `EVT-G3-KITE-LINE` | 3–6 min | Wind puzzle; cosmetic reward |

The crushed house, Gastly mansion, and thirsty stranger have their own detailed
documents. The remaining encounters are specified below.

## Shared behavior

- Every encounter is optional and must leave the critical road readable.
- Completion and rewards are per player. Shared props may show the completed
  state, but another player must still be able to run the scene.
- A player may leave and resume without losing submitted items or repeating
  completed stages.
- Event Pokémon do not join ambient spawn pressure. A capture reward uses a
  controlled, per-player encounter once that mechanism is proven.
- Failure never consumes the encounter. Minigames reset after a short local
  reset action rather than a timer.
- Dialogue should be brief unless the player deliberately continues Hank's
  hundred-line conversation.

# Pallet Town

## `EVT-PALLET-SALVAGE-LINE` — Not Everything Is Lore

**Visible hook:** Three residents form a line outside a house whose front room
has collapsed. They are passing ordinary belongings into labeled piles while
arguing about who owns a dented kettle.

**Flow**

1. Speak to Mina at the safe end of the line. She asks the player to return four
   recognizable objects, all visible within the damaged yard and front room.
2. Recover the kettle, fishing rod, child's drawing, and Poké Ball case. No
   object is hidden in rubble that looks unsafe to enter.
3. Hand each item to the resident reacting to it rather than placing everything
   in one quest chest.
4. The final item, the drawing, belongs to a child who has been silently
   watching the line. Returning it ends the scene.

**Character beats**

- Mina treats every recovered object as important until the kettle appears.
- The fisherman claims the bent rod can be fixed and refuses a replacement.
- The Poké Ball case is empty; its owner is relieved because every partner
  Pokémon was already outside.
- The child's drawing shows Pallet with the old Kanto coastline, quietly
  reinforcing what the town remembers without turning the scene into exposition.

**Reward:** An early supply bundle of ordinary healing and capture items. The
child later displays the recovered drawing in an intact Pallet building.

**State and reset:** Objects are interaction markers, not loose collectible
items. Each player can return all four. The shared scene normally remains an
active salvage line while players are still progressing. If the campaign later
advances it to sorted piles, the four piles retain inspection markers and Mina
runs a short catch-up version in which a late joiner matches each recovered
object to its owner. The reward and callback unlock remain per player.

**Build needs:** Damaged House B, four readable object props, five resident
positions, sorted and unsorted pile states.

## `EVT-PALLET-CORNER-MON` — Familiar Smell

**Visible hook:** A Lillipup is wedged in a sheltered corner of damaged House C.
It growls at rescuers but stares at an empty food bowl near the doorway.

**Flow**

1. The owner explains that Lillipup will bite anyone forcing the gap wider.
2. Inspect the bowl to learn the food came from Pallet's kitchen, not from a
   special Pokémon item.
3. Bring the owner one ordinary cooked food approved for the opening inventory.
4. The owner places it in the bowl and calls from several blocks away.
5. Lillipup crosses the room on its own. The player does not drag, battle, or
   capture it.

**Dialogue beats**

- Owner: “He is not trapped. He is scared. Those are different problems.”
- Owner: “Give him something that smells like breakfast.”
- After rescue: “There you are. You stubborn little hero.”

**Reward:** A berry bundle and a small friendship item candidate. Lillipup and
its owner remain together in Pallet afterward.

**State and reset:** Food submission is per player. The shared rescue animation
may replay locally or use dialogue to credit late players; no player loses food
without receiving completion.

**Build needs:** Damaged House C, safe sightline into the corner, bowl marker,
owner position, and a proven static partner-Pokémon actor.

# Brock's town

## `EVT-G1-MACHOP-SHIFT` — One More Beam

**Visible hook:** The work bell rings and every builder stops except one Machop,
which keeps lifting the same support beam while the foreman tries to wave it
down.

**Flow**

1. Speak to Foreman Della. Machop believes stopping means the structure is still
   unsafe.
2. Inspect three support points around the worksite. Two are braced; one brace
   has fallen beside the marked footing.
3. Replace or activate the missing brace.
4. Ring the work bell again. Machop checks all three supports, puts down the
   beam, and finally sits with the crew.
5. Della marks a nearby training yard where a wild Machop has been watching the
   work and wants to test the player.

**Dialogue beats**

- Della: “Nobody taught it what the bell means. We only taught it that the wall
  cannot fall.”
- Builder: “It has moved that beam six times. The beam was correct the first
  time.”
- Della after completion: “There. Safe enough to rest is still safe.”

**Reward:** Building supplies and one controlled Machop encounter available to
that player. The capture is optional and cannot block event completion.

**State and reset:** Brace checks and reward are per player. The bell and Machop
rest pose are shared ambience. If the actor cannot be made replayable, late
players inspect the supports with Della while Machop remains seated.

**Build needs:** Worksite, three distinct braces, bell, beam prop, rest area,
and a nearby encounter yard.

## `EVT-G1-PEBBLE-LEAGUE` — Little League

**Visible hook:** Children cheer while a Roggenrola rolls down a shallow stone
lane and stops nowhere near the painted target.

**Flow**

1. Join for one round and choose left, center, or right release position.
2. Observe the lane: one side slopes, one has loose gravel, and the center is
   clear but longer.
3. Choose a release position and one of three strength cues.
4. Roggenrola rolls to the resulting scoring ring.
5. Any score completes the encounter; the center ring records a best result and
   changes the children's reaction.

**Dialogue beats**

- Child: “It is not bowling. Bowling has pins. This has geology.”
- Roggenrola's owner: “Do not ask how we measure a foul. We are still fighting
  about it.”
- Center hit: “That counts! Nobody change the rules until they leave.”

**Reward:** A local ribbon cosmetic. A center hit adds a small stone-item bonus,
but no important reward requires perfect input.

**State and reset:** Score is per player. The lane resets through a visible
return channel or attendant interaction, never by despawning Roggenrola.

**Build needs:** Short safe lane, three launch markers, three scoring rings,
return path, spectators, and a controlled Roggenrola actor.

# Brock-to-Misty road

## `EVT-ROUTE2-ROLLAWAY-GEODUDE` — Downhill From Here

**Visible hook:** A miner stands beside an empty handcart. Fresh scrape marks and
scattered ore samples continue downhill toward Lake Viltri.

**Flow**

1. The miner admits Geodude curled up in the cart during lunch and rolled away
   when the brake slipped.
2. Follow three obvious signs: a wheel rut, a split sample sack, and a newly
   chipped boulder.
3. At the bottom, find Geodude holding the cart against a tree so it cannot roll
   into the lake.
4. Secure the cart brake before asking Geodude to move.
5. Walk back with the miner and Geodude; no escort fails because the player
   moved too quickly.

**Dialogue beats**

- Miner: “Good news: Geodude is extremely durable.”
- Miner: “Bad news: so is the cart, and both of them were going downhill.”
- At the tree: “It did not run away. It caught the cart.”

**Reward:** Mining supplies, a town shop discount candidate, and a small stone
held-item candidate subject to early balance.

**State and reset:** Trail clues remain usable per player. The cart returns to
its starting place for unfinished players or is represented by a second local
state; implementation must not strand the event downhill after one completion.

**Build needs:** A believable downhill spur off the Brock-to-Misty road, cart,
three trail clues, safe stopping tree, and return dialogue point.

# Misty's town

## `EVT-G2-PSYDUCK-LAUNCH` — Docked by a Headache

**Visible hook:** A loaded rescue skiff is ready to launch, but Psyduck sits in
the middle of the ramp with both paws against its head. Workers have stopped
shouting because every loud sound makes it flinch.

**Flow**

1. Speak quietly to the dock worker and inspect three nearby places: the busy
   market awning, the open dock, and a shaded reed cove.
2. Notice that the cove blocks the bell and worksite noise.
3. Place a calming berry or the worker's approved snack at the cove marker.
4. Clear the direct walking line. Psyduck moves there on its own.
5. The skiff launches and returns as background activity.

**Wrong approaches:** Ringing the bell, striking blocks beside Psyduck, or
challenging it to battle makes it cover its head and resets the placement step.
Nothing attacks the player.

**Dialogue beats**

- Worker: “It is not blocking the ramp to be difficult. The whole dock is
  shouting inside its skull.”
- After completion: “See? Nobody had to win.”

**Reward:** Water-travel supplies and two useful drink items. Exact items await
inventory and ID verification.

**State and reset:** Food is consumed only when the correct cove is selected.
Psyduck's final position may be shared; late players solve the sound problem
through the worker's replay state.

**Build needs:** Boat ramp, skiff, audible or visual noise sources, three clear
candidate resting places, and reed cove.

## `EVT-G2-POLIWAG-COUNT` — One Ripple Short

**Visible hook:** A swimming teacher counts a looping line of Poliwag. The count
is always one short, while a tied boat near the class rocks at the wrong rhythm.

**Flow**

1. Watch one count. Do not make the player count a large moving crowd manually;
   the teacher states the expected and observed totals.
2. Check the shore, dock barrels, and tied boat.
3. Find the missing Poliwag asleep in the boat under a folded class towel.
4. Wake it gently with the teacher's whistle or a splash marker beside the
   boat.
5. Take the class photo after the Poliwag rejoins the line.

**Dialogue beats**

- Teacher: “Eight heads, seven ripples. Unless one learned to levitate.”
- At the boat: “Found our strongest swimmer. Excellent nap technique.”
- Student: “Can the boat be in the photo? It did most of the babysitting.”

**Reward:** A class-photo keepsake and one controlled Poliwag encounter at a
nearby practice pool. The photographed Poliwag is the teacher's partner and is
not catchable.

**State and reset:** Discovery is per player; the photo pose is replayable.
Each player's optional encounter is independent.

**Build needs:** Swim loop, tied boat with readable movement, towel prop, class
line, photo marker, and separate encounter pool.

# Misty-to-Surge climb

## `EVT-ROUTE3-CREEK-WOOPER` — The Dry Crossing

**Visible hook:** At the creek crossing near (1824, 1888), a supply crate is
stuck on a gravel bar. Several Wooper occupy the shallow channel between it and
the road.

**Flow**

1. A courier asks for the crate but warns that chasing the Wooper will scatter
   them into deeper water.
2. Inspect three stepping routes. One crosses their feeding patch, one is too
   deep, and one uses dry stones along the upstream edge.
3. Mark or traverse the dry route without entering the feeding patch.
4. Release the crate from the gravel bar and return it along the same path.
5. The Wooper remain calm. One follows the player to a nearby muddy pool and
   offers a controlled encounter.

**Readable solution:** Water bubbles and food particles mark the feeding patch;
darker water marks the deep route; dry lichen marks the safe stones. The player
should not solve this by invisible collision rules.

**Dialogue beats**

- Courier: “They were here first. The crate can wait five minutes.”
- After completion: “You brought the supplies back and left the creek where you
  found it. That is the whole job.”

**Reward:** One controlled Wooper encounter and a Soft Sand candidate. This is
an intentional optional Ground-type answer available before Surge, subject to
trainer-balance review.

**State and reset:** Route choice and reward are per player. Crossing the wrong
patch resets the crate interaction but does not remove the Wooper or permanently
fail the event.

**Build needs:** Authored creek crossing at the known anchor, three readable
routes, gravel-bar crate, feeding particles or props, and encounter pool.

## `EVT-ROUTE3-NOSEPASS-SIGNS` — North Keeps Moving

**Visible hook:** Three mountain trail signs point in different directions. A
Nosepass beside them repeatedly turns toward Surge's signal equipment instead
of geographic north.

**Flow**

1. Speak to the trail keeper, who knows the signs were correct that morning.
2. Inspect three sign bases. Metal fasteners vibrate when the signal pulses.
3. Use nonmetal wedges supplied by the keeper to lock the signs to their painted
   ground marks.
4. Wait through one visible pulse. Two signs hold; the third reveals a second
   loose bracket.
5. Fix the final bracket. Nosepass still turns toward the equipment, proving
   the compass problem is not ordinary magnetism.

**Dialogue beats**

- Keeper: “I trust Nosepass. I do not trust a mountain that can argue with one.”
- After the pulse: “The signs are fixed. The direction is not.”

**Reward:** Climbing supplies and a marked shelter location on the remaining
route to Surge. The scene foreshadows the directed signal without providing the
main-story proof early.

**State and reset:** Brackets are per-player interactions. Corrected signs are
shared scenery and may remain fixed after first world completion.

**Build needs:** Three signs with ground marks, pulse cue tied visually to the
mountain equipment, Nosepass actor, and trail-keeper shelter.

# Surge's town

## `EVT-G3-MAGNEMITE-BOLTS` — Magnetic Personality

**Visible hook:** Every loose bolt in the repair yard is stuck to Magnemite
hovering over the same roof. A technician removes one bolt; another immediately
flies up.

**Flow**

1. Speak to Technician Ivo and inspect the roof, scrap bin, and grounded work
   board.
2. Learn that the roof plate becomes magnetic during signal tests.
3. Move the scrap bin beneath the grounded board and place one supplied iron
   piece on it.
4. Trigger the safe test switch. Magnemite shift to the stronger, grounded
   target and release the bolts onto the board.
5. Sort the recovered fasteners into three visible sizes.

**Dialogue beats**

- Ivo: “They are helping. That is what makes this difficult.”
- Ivo: “Yesterday they organized every screw by emotional significance.”
- After completion: “Useful, grounded, and nowhere near the roof. Beautiful.”

**Reward:** Electrical crafting supplies and a held-item candidate useful to an
Electric-type team. Final items require balance and ID verification.

**State and reset:** The sort and reward are per player. The bin can reset to
its starting position through Ivo. The safe switch must not affect Surge's
story equipment or required evidence.

**Build needs:** Repair yard, roof plate, movable or stateful scrap bin,
grounded board, safe test switch, and several Magnemite actors.

## `EVT-G3-KITE-LINE` — Higher Than the Signal

**Visible hook:** A resident holds a bright kite beside three launch flags. The
kite is already tangled around their boots, and Surge's antenna array occupies
the obvious windy ledge.

**Flow**

1. Read the three flags: one points toward the antenna, one into a cliff rotor,
   and one along an open shoulder away from equipment.
2. Choose the open-shoulder launch marker.
3. Hold the line through three short wind cues by stepping between marked line
   lengths or selecting loosen/hold/reel.
4. The kite clears the ridge and remains visible over town for the completion
   scene.

**Wrong choices:** The antenna approach produces an immediate refusal from the
resident. The rotor tangles the kite in a low, reachable bush and resets the
launch. No choice damages equipment.

**Dialogue beats**

- Resident: “Surge said I could fly it anywhere that is not expensive.”
- Looking at the antenna: “That direction looks extremely expensive.”
- After completion: “There. Higher than the signal and cheaper than a repair.”

**Reward:** A kite-token cosmetic and mountain-weather notes that identify
visual wind cues elsewhere. No mechanical travel advantage is required.

**State and reset:** Launch result and reward are per player. The completed kite
may appear as shared town ambience after first completion.

**Build needs:** Three launch markers, readable flags, safe snag bush, kite prop
or particle effect, and a clear view back toward town.

# Implementation order

1. Place and prove the three Pallet damage scenes.
2. Place Route 1's mansion and hut without narrowing the critical path.
3. Block out the Brock worksite and pebble lane.
4. Author the downhill Geodude trail after the Brock-to-Misty road grade is
   final.
5. Build Misty's dock scenes around the final shoreline and boat placement.
6. Build the Wooper creek event at the measured crossing before dressing the
   rest of the mountain route.
7. Place the Nosepass signs where the player can see Mt Vessu equipment but not
   the required story evidence.
8. Fit Surge's two town events around the final gym and signal-array footprints.
9. Run a separate trainer-balance review on Machop, Poliwag, and Wooper access
   before assigning levels, moves, held items, or capture counts.

# Unverified technical needs

- Static Pokémon actors that can emote, move locally, and remain uncapturable.
- Per-player controlled encounters that cannot be duplicated through relogging.
- Per-player dialogue and submission state with shared scenery.
- Replayable prop state for multiplayer and late joiners.
- Exact item IDs and quantities for every reward.
- Exact placement coordinates outside established town centres and the creek
  anchor.