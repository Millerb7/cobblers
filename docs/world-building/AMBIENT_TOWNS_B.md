# Ambient towns, author B

Ten towns composed to `data/ambient.json` `composition` (the owner's 2026-10-05 brief, with the
coordinator's same-day rule change: each share within 0.08 or one Pokemon; mining towns at least half
working, the rest split 15:20:35). One file per town in `data/ambient_towns/`. Positions are measured
from the town plans and `tools/ground.py` (rounded), never a world. No two of these ten towns share a
species (297 species in all); against author A's seven files present on 2026-10-05 no species is in more
than three towns, the largest roster overlap is 0.17 (Fossick and Brock's town), and no situation title
repeats.

All ten pass `tools/ambient_idle.py build` against the built packs (2026-10-06, after the additions below), and
`tools/ambient_composition_audit.py` over the build's plans passes. Pacifidlog now builds: the generator exempts its
decks (`Site.deck`), so the note on it below is history.

| Town | Character | Situations (unique first) |
|---|---|---|
| Greenhollow (gym4) | A gardeners' town: water, weed, trim, pollinate, haul silt and hay | **The marrow show** (four Pumpkaboo and one real pumpkin); The Lotad crossing; The bench nobody sits next to; Bounsweet in the jam pans; The nest on the pergola; *Two Psyduck and a water butt*; *Asleep in the top crate* |
| Fenhide (gym5) | Trappers and poisoners in the reeds: reeds, eels, snares, smoke, balls | **The Stunfisk on the square's step**; The frog chorus on the fen walk; The moths at the junction lamp; More Pokemon than mushrooms; The game on the eel barrel; *The queue for the antidote*; *The fifth target* |
| Tilpey Cross (gym6) | A city of readers and shops: the hour, doors, books, food, a street mime | **The staring contest in the square**; Asleep on the observatory steps; The tea service in the masons' garden; The Spoink that will not stop; The chess game by the library; The dance in Observatory Street; *The memory stone with a face*; *A page behind* (and, placed rather than a situation, a Misdreavus in the armourer's chimney pot) |
| Cinderlee (gym7) | A field station on a live crater: vents, cores, labels, instruments | **The cold visitors in the Centiskorch's coil**; The bath nobody else can use; The Durant column to the core shed; The bird on the instrument mast; Asleep in the old kiln; After the causeway race; *The queue to be weighed*; *The geological feature* |
| Holdfast (gym8) | A garrison on the strand: drill, stakes, ditch, sentry, armoury | **The recruits on parade**; The trough the horses cannot use; The dogs off watch; The wagon that has not moved since Tuesday; The Marowak at the cairn; *The queue at the butcher's door*; *The sentry nobody posted* |
| Fossick (mining_town) | A working mine, 22 of 44 breaking, drilling, hauling, sorting | **The canary at the adit**; The Golem asleep on the rails; Fossils in the wash trough; The salt lick behind the ore road; *The lump of ore with a face*; *Whoever the Klefki likes*; *The snap tins on the shelf* |
| West Spur Dig (rift_dig_camp) | An archaeologists' camp: dig, haul, record | **The Unown at the cut face** |
| Redbrow (tableland_stop) | A stop on the scorched plateau | **The Spinda on the brow**; *Two cactuses by the counter* |
| Rimwatch (rift_rim_stop) | The rangers' post on the Rift's lip | **The three on the overlook rail** |
| Pacifidlog (sea_town) | A town on log rafts: fish, smoke, bail, caulk, keep the lights | **The Lapras tied up at the guild raft**; The bait tanks on the Row; The one that got away; The flock on the breakwater; Why nobody swims at the gate; The sushi on the inn's tray; *The angler who uses its tail*; *One sheet too many*; *The lamp that came back on* |

*Italic*: added 2026-10-06 (the owner: "push the unique situations higher"). Every one is hand-written, sited from
the town plan and the template as placed (FEET y, Pacifidlog's deck walk y 63), and checked by
`tools/ambient_idle.py build` against the built packs' replay. The ceiling binds them: a town's situations may be at
most 0.35 + 0.08 = 0.43 of its total and the total at most 48, so a gym town tops out at 20 situation members; each
gym town went 46 -> 48 (Tilpey 47 -> 48) and gave up one placed Pokemon, and Fenhide, Cinderlee and Holdfast each
took one member out of an existing group (a Tympole from the chorus, the fifth Durant, a Herdier) to fit a queue of
three. Fossick stays at 44 (working 22 = 0.50; two placed and one pet converted, situations 14 = 0.32 of the 0.33
mining ceiling). Redbrow's Cacnea pet became its situation. **Rimwatch and the West Spur Dig have no room**: an
outpost totals at most 6, Rimwatch's situations are already 3 of 6 (the ceiling 0.35 + 1/6), the dig's 2 of 6 (the
mining ceiling 0.25 + 1/6), and neither can lose its one placed Pokemon (placed floor 0.20 - 1/6 > 0).

**A situation cannot stand on a building.** `tools/ambient_idle.py` accepts a situation anchored on a building's top
(`anchor_ground_ok`), but `tools/ambient_idle_audit.py` refuses any situation member inside a building's footprint at
any height (placed Pokemon are exempt). The two disagree; until they agree, "something in a chimney" is a placed
Pokemon at an explicit `at` (Tilpey's Misdreavus), and a prop over a member reads as a roof (indoors) to the audit.

## What could not be sited, and why

- **Pacifidlog, all 44 (2026-10-05; since resolved in the generator, which exempts the decks).** Every deck cell of the town is within 8 of a column the water export changes
  (measured: 0 clear of about 8,000 raft, pier, wharf and boardwalk cells; the town was re-sited onto the
  export's own reshaped bank), and every deck is an earthwork in `data/placements.json`, which
  `tools/ambient.py` refuses for a worker. The file is written to the schema with the deck's y (walk y63)
  on every record and `"y": 63` on every worker, but the generator refuses it until it exempts the sea
  decks from the water margin and accepts deck earthworks as ground. That is a generator decision, not
  an authoring one.
- **No pets at Rimwatch or the West Spur Dig.** Neither places an NPC or a stall keeper
  (`data/markets.json` lists both as having no market; `data/npc_seats.json` seats nobody there). The
  dig is written as an outpost (its own plan: "An outpost, so no Center"; the scale's "a camp"): at
  hamlet size, the mining split cannot be met with no pets.
- **Sleep pose.** Only the eight day sleepers in `idle.rules.sleeps_by_day` may sleep in a lit town, and
  none of them is used here (Snorlax, Slowpoke, Purrloin and Murkrow are the pasted rosters this
  replaces). Members the stories call asleep are `still`.
- **Not verified in game.** The mast-top birds at Cinderlee stand 20 and 22 above the mast's foot (its
  dressing height is 22); the generator does not model the mast's blocks, so whether they sit on its head
  is for the build or a look. Nothing here has been seen in a running game.
