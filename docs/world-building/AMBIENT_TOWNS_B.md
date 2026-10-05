# Ambient towns, author B

Ten towns composed to `data/ambient.json` `composition` (the owner's 2026-10-05 brief, with the
coordinator's same-day rule change: each share within 0.08 or one Pokemon; mining towns at least half
working, the rest split 15:20:35). One file per town in `data/ambient_towns/`. Positions are measured
from the town plans and `tools/ground.py` (rounded), never a world. No two of these ten towns share a
species (297 species in all); against author A's seven files present on 2026-10-05 no species is in more
than three towns, the largest roster overlap is 0.17 (Fossick and Brock's town), and no situation title
repeats.

Nine of the ten pass `tools/ambient_idle.py compose` (orchestrator branch). Pacifidlog does not: see
below.

| Town | Character | Situations (unique first) |
|---|---|---|
| Greenhollow (gym4) | A gardeners' town: water, weed, trim, pollinate, haul silt and hay | **The marrow show** (four Pumpkaboo and one real pumpkin); The Lotad crossing; The bench nobody sits next to; Bounsweet in the jam pans; The nest on the pergola |
| Fenhide (gym5) | Trappers and poisoners in the reeds: reeds, eels, snares, smoke, balls | **The Stunfisk on the square's step**; The frog chorus on the fen walk; The moths at the junction lamp; More Pokemon than mushrooms; The game on the eel barrel |
| Tilpey Cross (gym6) | A city of readers and shops: the hour, doors, books, food, a street mime | **The staring contest in the square**; Asleep on the observatory steps; The tea service in the masons' garden; The Spoink that will not stop; The chess game by the library; The dance in Observatory Street |
| Cinderlee (gym7) | A field station on a live crater: vents, cores, labels, instruments | **The cold visitors in the Centiskorch's coil**; The bath nobody else can use; The Durant column to the core shed; The bird on the instrument mast; Asleep in the old kiln; After the causeway race |
| Holdfast (gym8) | A garrison on the strand: drill, stakes, ditch, sentry, armoury | **The recruits on parade**; The trough the horses cannot use; The dogs off watch; The wagon that has not moved since Tuesday; The Marowak at the cairn |
| Fossick (mining_town) | A working mine, 22 of 44 breaking, drilling, hauling, sorting | **The canary at the adit**; The Golem asleep on the rails; Fossils in the wash trough; The salt lick behind the ore road |
| West Spur Dig (rift_dig_camp) | An archaeologists' camp: dig, haul, record | **The Unown at the cut face** |
| Redbrow (tableland_stop) | A stop on the scorched plateau | **The Spinda on the brow** |
| Rimwatch (rift_rim_stop) | The rangers' post on the Rift's lip | **The three on the overlook rail** |
| Pacifidlog (sea_town) | A town on log rafts: fish, smoke, bail, caulk, keep the lights | **The Lapras tied up at the guild raft**; The bait tanks on the Row; The one that got away; The flock on the breakwater; Why nobody swims at the gate; The sushi on the inn's tray |

## What could not be sited, and why

- **Pacifidlog, all 44.** Every deck cell of the town is within 8 of a column the water export changes
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
