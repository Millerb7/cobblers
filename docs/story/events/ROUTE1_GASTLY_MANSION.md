# Route 1 Ghost Mansion — Lost in the House

- **Event ID:** `EVT-ROUTE1-GASTLY-FAMILY`
- **Kind:** Optional exploration dungeon and Pokémon escort
- **Route anchor:** Pallet (1462, 5293) to Brock’s town (1743, 3628)
- **Progression:** Optional; never blocks the main path

## Premise

A large abandoned mansion stands off the forested part of the first route. The
house is active with Ghost-type Pokémon. Near the entrance, a young Gastly is
hiding from them. It became separated from its two parents after the house's
old protective ward collapsed and is too frightened to cross the occupied
rooms alone.

The player leads Gastly through the mansion to a Haunter and Gengar trapped in
the far wing. The other Ghost Pokémon are not an evil army. Some defend nests,
some play tricks, and some have claimed rooms the family once crossed safely.
The mansion is a local ghost story, not evidence about who steered the
Worldshift.

## Location and donor strategy

The authored manor is centred at `(1630, 5034)`, with footprint
`x1614..1645, z5022..5045` and its main floor at `y114`. Its side trail leaves
Route 1 at `(1468, 5018)`, route distance 284.9. The house is visible north of
Pallet, lost behind the forest from the route mouth, and recovered by the
junction signpost. Keep that sightline behavior; do not replace it with a
woodland-mansion donor.

## Cast

- **Pip:** working name for the young Gastly. Speaks in short frightened
  fragments or communicates through emotes if voiced Pokémon are undesirable.
- **Haunter parent:** cautious and quick to investigate sounds.
- **Gengar parent:** held behind the final room’s unstable barrier and keeping
  the surrounding ghosts away from the trapped wing.

The family relationship is story canon for these authored Pokémon; it does not
claim that every evolution family works this way.

## Player-facing opening

At the foyer, Gastly repeatedly peeks from behind broken furniture and retreats
when another ghost crosses the room.

- **Gastly:** Gaaas…?
- **Observation:** It keeps looking toward the upper hall.
- **Choice:** `Come with me.` / `I’ll come back.`

Accepting starts the escort. Declining leaves Gastly safely at the foyer.

## Mansion route

### Checkpoint 1 — Foyer: watching eyes

- Shuppet move between portraits and furniture.
- The player identifies the one clear path instead of battling every Pokémon.
- Gastly moves from its hiding place to the staircase checkpoint.
- **Purpose:** Teach that escort progress happens room by room.

### Checkpoint 2 — Dining room: occupied place settings

- Sinistea or Polteageist occupy cups across the long table.
- The player moves through without taking the marked cup, or returns it after a
  trick interaction.
- One optional battle yields a small tea-related reward.
- Gastly moves to the service corridor.

### Checkpoint 3 — Library: the wrong whisper

- Duskull and Misdreavus mimic the parents’ calls from different shelves.
- The real clue is Gastly’s reaction to a familiar sound or object.
- Choosing the right aisle opens the next checkpoint; wrong aisles produce
  harmless scares or optional battles.

### Checkpoint 4 — Bedroom hall: lights out

- Litwick illuminate doors in a repeating order.
- Following the order reveals the safe room; rushing causes the sequence to
  reset, not player damage.
- Gastly moves to the far-wing landing.

### Checkpoint 5 — Sealed ballroom: the family

- Haunter is outside the unstable barrier, trying to reach Gengar.
- The player restores three broken ward marks in the order indicated by the
  ballroom floor, or defeats the event's strongest wild Ghost Pokémon.
- The barrier drops, Gengar emerges, and Gastly crosses the room on its own.
- The three reunite. None becomes a forced capture reward.

## Escort behavior

The preferred implementation is **checkpoint movement**, not free-form entity
pathfinding:

1. Gastly waits at a safe marker.
2. The player completes the current room condition.
3. Gastly plays a short move animation or teleports along a concealed safe path
   to the next marker.
4. If players leave or the server restarts, Gastly returns to the last completed
   checkpoint.

This reads as being led through the house while avoiding long-distance follow
AI, chunk unloading, door navigation, and multiplayer desync.

## Ending

- **Haunter:** Hau! Haunter!
- **Gastly:** Gastly!
- **Gengar:** Gengaaaaar.
- **Observation:** The three shadows overlap for a moment, then separate.
- **Observation:** Gengar leaves something where Gastly had been hiding.

After completion, the family may appear together in one safe mansion room.
Ambient Ghost Pokémon remain; the mansion does not become empty.

## Reward

- **Primary:** Spell Tag, subject to item-ID verification.
- **Secondary:** one-time mansion cache with Dusk Balls or similarly early
  capture supplies, exact quantity deferred to balance.
- **Encounter:** unlock a separate, clearly non-family Gastly encounter outside
  the mansion if early Gastly availability fits Route 1 balance.

The player does not receive Pip or either parent as an automatic capture.

## Multiplayer behavior

- Each player owns an independent Gastly escort, checkpoint, dialogue cursor,
  and reward claim.
- Shared rooms and props remain in place, but one player's progress never
  advances, resets, or hides another player's actor.
- A reconnect restores that player's Gastly to their last saved checkpoint.
- Required battles are player-local and must not target another player's
  escort actor.

## Implementation gaps

1. Explicit mansion spawn control that does not flood Route 1.
2. Player-local Gastly, Haunter, and Gengar actor method.
3. Checkpoint restore and two-player isolation proof.
4. Verified Spell Tag and cache item IDs.
5. Final encounter levels and species list after Route 1 balance is approved.
