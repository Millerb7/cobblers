# Legacy event intent

Design intent salvaged from the retired prototype worlds before their coordinate
data was deleted. **This file is an idea list, nothing more.** It is plain
markdown, it is not validated, and no tool reads it.

Two prototype worlds produced this material and neither landscape exists any
more. EXP-009 was a 2500×2500 generated world of four 1250-block cells. EXP-001
was a separate 1000×1000 world in its own `f4-local-1000` coordinate space. Every
position, footprint and cell assignment referred to terrain that was never part
of the `erosion_land_8k` heightmap, so all of it was discarded rather than
re-sited. Only the ideas survive.

Event ids below keep their original spelling. The `d4-` and `e5-` style prefixes
are historical labels from the retired grid and carry **no meaning** under the
current A–H by 1–8 scheme. Treat them as names, not locations.

## Events from EXP-009

| id | kind | scale | what it was for |
| --- | --- | --- | --- |
| `d4-meadow-trial` | trainer_clearing | medium | Open meadow fight, the first real trainer test near the starting town. Was built as a fenced, entity-free arena |
| `d4-berry-grove` | berry_grove | small | Early harvesting stop, low stakes, off the main road |
| `d4-fishing-bend` | fishing_spot | small | Water's-edge encounter variety near the town |
| `d4-old-mill` | landmark | small | Navigation landmark, purely visual anchor for wayfinding |
| `d5-cabin` | abandoned_cabin | medium | Explorable interior in deep forest, the "someone lived here" beat |
| `d5-nest` | pokemon_nest | small | Concentrated species pocket in old-growth woods |
| `d5-shrine` | shrine | small | Quiet forest discovery, candidate for a gated or puzzle reward |
| `d5-clearing` | trainer_clearing | small | Forest-trail ambush fight, tighter sightlines than the meadow |
| `e4-river-camp` | ranger_camp | medium | Friendly NPC waypoint on the riverbank, rest and information |
| `e4-ford` | fishing_spot | small | Shallow crossing doubling as a water encounter |
| `e4-grove` | berry_grove | small | Riverside harvesting counterpart to the lowland grove |
| `e4-cache` | rocket_cache | small | First villain-faction breadcrumb, a hidden stash rather than a fight |
| `e5-cavern` | cavern_entrance | medium | Entrance to an underground area in the rocky uplands |
| `e5-overlook` | ridge_overlook | small | High vantage point, intended to reveal the region below |
| `e5-shrine` | shrine | small | Mountain counterpart to the forest shrine |
| `e5-nest` | pokemon_nest | small | Rock-type species pocket at altitude |

## Events from EXP-001

| id | kind | what it was for |
| --- | --- | --- |
| `abandoned-fish-hut` | shore_hut | Derelict hut and dock on the western coast, early exploration reward |
| `abandoned-house` | abandoned_house | Northeastern ruin, small interior discovery |
| `broken-boat` | shore_wreck | Shoreline wreck acting as a visual clue pointing offshore |
| `relic-island` | worldshift_fragment | The offshore relic, detailed below |

## Relic island

Full name "Relic Island — The Stranded Home". Optional, never required, intended
as an early-but-memorable discovery rather than a gated reward.

- **Hook:** a broken dock and boat debris on the mainland shore line up with the
  island, so the player infers it before they can see anything on it.
- **Access:** an early optional swim or an ordinary boat. Later water mounts make
  the return trip quicker. Deliberately no hard gate.
- **Composition requirements:** open water around the entire footprint, an
  unobstructed sightline back toward the town, and no required route or gym
  progression routed through it.
- **Recommended reward:** one level 5 to 7 Pichu per player plus a lore
  collectible, claimed once per player and independent of shared world state.
  Explicitly *not* a low-weight ordinary spawn. If reliable per-player static
  encounters prove impossible, the fallback was a badge-delayed Light Ball.
- **Dependencies:** needs the EXP-006 static encounter proof and the EXP-007
  per-player progression proof before it can be built for real.

## Settlement composition

The prototype town, "brookstep_prototype" in EXP-009 and "Pallet Town" in
EXP-001, was assembled from these library pieces. The composition is worth
keeping even though the layout is not.

Pokémon Center, Poké Mart, two lodges, two willow houses, a battle pad, and a
well at a path crossroads. EXP-001 added Professor Oak's lab, a player house, a
neighbour house, and three smaller houses. A stone-and-oak wayfinder landmark
sat apart from the buildings as a navigation anchor.

Every one of those pieces resolves against the structure library, which is
preserved intact under `kits/structures/`.

## Landscape identities

Four macro identities were being trialled as adjacent regions. They are recorded
as intent only. Under the current model, region boundaries follow terrain and are
a separate concept from the planning grid, so these do not map onto cells.

- Rolling plains lowlands carrying the starting town, travelled by broad roads
  and open meadow.
- Old-growth forest edge on hills, travelled by concealed trails.
- A river valley of plains and water, travelled along the bank and across a
  bridge crossing.
- Rocky foothills rising to a ridge, travelled by switchback trail and a pass.

## Route and crossing intent

No route geometry survives, since every polyline was in a retired coordinate
space. The shapes that were being tested are worth restating:

- A town-to-neighbouring-region road as the main east–west spine.
- A short spur from the town to a nearby medium event, about two bends long.
- A full west-to-east traverse across the starting region.
- A long diagonal connecting the lowlands to the far uplands, used to test
  travel time across the whole prototype.
- A bridge crossing roughly eleven blocks wide where the spine met the river.

## Reward-design principle worth keeping

From the relic island notes, and applicable generally: a memorable optional
reward should be useful without invalidating early team building, and a
per-player claim model is preferred over shared world state for anything a
group might reach at different times.
