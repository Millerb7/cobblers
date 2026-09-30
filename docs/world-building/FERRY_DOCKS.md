# The ferry docks

The owner, 2026-09-30: *"FERRY DOCKS: build the twelve. The charters exist on
paper and docks are what make them real."*

`data/ferries.json` carried sixteen docks and ten lines, and only `relic_row`
could run, because only its two docks were built. Nine of the twelve `planned`
docks are now sited and built by `tools/ferry_docks.py` from
`data/ferry_docks.json`. Three cannot be sited from anything in the repository
and are listed below with the decision each waits on.

**Nothing here has run in a game.** The functions are valid text that no server
has executed; `python tools/ferry_docks.py report` proves the data and the
geometry against the heightmap, not the result.

## The nine

| dock | position (ferryman) | deck y | landward | line |
| --- | --- | ---: | --- | --- |
| `pacifidlog_south_jetty` | 5163, 63, 6658 | 62 (built by `tools/sea_town.py`) | the bamboo jetty north to the plateau's south beach | `pacifidlog_ferry` |
| `sunset_south_pier` | 2697, 64, 6590 | 64 (`sunset_pier_south`) | Sunset West's shore, level to the town square | `sunset_strait` |
| `sunset_isle_landing` | 2572, 63, 6899 | 64 | the Sunset isle's north shore | `sunset_strait` |
| `sunset_quay` | 2634, 64, 6521 | 64 (`sunset_pier_west`) | Sunset West, level ground east into the town | the four charters |
| `northeast_landing` | 6605, 63, 2306 | 64 | marsh country's shore, rising south | `northlight_packet` |
| `northlight_landing` | 6878, 63, 1955 | 64 | South Pine Isle, rising north to the town plan | `northlight_packet` |
| `tilpey_sabrina_dock` | 6050, 79, 3609 | 79 | Lake Tilpey's north shore, 250 blocks up to Sabrina's town | `tilpey_launch` |
| `weeping_elder_landing` | 5690, 80, 4114 | 79 | the island's shore, 65 blocks to the elder tree | `tilpey_launch` |
| `tilpey_south_landing` | 5879, 78, 4519 | 79 | the lake's south shore, toward the outflow gorge | `tilpey_launch` |

## How a dock is sited

Ground comes from `tools/ground.py` (the canonical heightmap, rounded), or from
a settlement's own measured plan ground where the settlement does not stand on
the heightmap (`ground.for_settlement`; the sea town's decks are the case here).
Never from a world save — CLAUDE.md's ground rule, `tests/test_ground_rule.py`.

Each record names the dock's `near` (which `data/ferries.json` already carried,
with its `near_basis`) and the cardinal direction `out` it faces. From those two
numbers the tool derives the **shore column** by one rule, the same for every
dock:

> the column nearest `near` that is dry (ground >= the water level), whose whole
> `width`-wide strip has at least `min_reach` water columns straight outward
> along `out`, and which has at least `min_dry` dry columns straight back
> landward; ties broken by distance, then z, then x.

The record also writes down the column it was authored against, and `report`
derives it again and refuses if the two disagree. That is the point of writing
the derivation down twice: if the heightmap moves under a dock, the dock fails
instead of hanging in the air.

**Water levels.** The sea is `data/world.json` `vertical.sea_level` (62). Lake
Tilpey is **y77**, measured plan data from `data/legendaries.json` (Uxie's
grotto mouth: *"18 below the water level y77"*). A lake record must name its
source; a level with no source is refused.

**Deck height = water level + 2.** That is what every dock and pier already
built here stands at: `first_cast`'s jetty (`tools/route_events.py`, deck 64),
`sunset_pier_south` and `sunset_pier_west` (`data/placements.json`, planks at
y64) — sea level 62 plus 2 in all three. The sea town's rafts are a different
thing, a floating deck replacing the top water layer at y62
(`tools/sea_town.py`); a jetty is not a raft, so this follows the jetties.

**Style**, likewise from the built docks: spruce planks with a stripped spruce
wood grain, spruce log piles to the seabed every four columns, a spruce fence
rail, mooring posts with lanterns at the head, a stair and two solid courses up
from the shore, and a forecourt of boards laid *at* the ground (not above it) so
the heightmap ground under the ferryman is the ground the re-apply's audit
reads.

**Where the ferryman stands.** On heightmap ground at the dock's root, never on
the deck: `tools/ferries.py` places and audits every ferryman at `ground + 1`
with the ground from the heightmap, so an NPC over water fails. `first_cast`'s
boatman stands on his beach for the same reason. Each dock's `keep_clear` box is
its deck, step and stair; the ferryman and the landing sit outside it, on the
forecourt.

## What `report` refuses

It is fail-closed (exit non-zero on any problem) and every check compares
against the data and the heightmap, never against the tool's own output:

- the derived shore column must equal the declared one;
- `deck_y` must be the water level + 2, the level read from data;
- every deck cell past the root must stand over water on the heightmap, and the
  head must have at least the record's `min_head_depth` blocks of it — a deck
  that does not meet the water is not a dock;
- the root must stand on dry ground and the walk inland must stay dry for
  `min_dry` columns with no step over one block — a dock nobody can reach from
  land is not a dock;
- no cell may land on a column `data/placements.json` already writes (real
  columns, not bounding rects: `sunset_west_lights` is lanterns scattered over a
  whole town and its rect swallows every street between them), nor inside a
  spawn-free zone in `data/spawn_suppression.json`;
- **no block written may be a spawn condition.** The tool reads
  `data/spawn_blocks.json` and refuses any block it lists, as
  `data/system_contracts.json` contract C4 requires of every tool that writes
  world blocks. The palette here — spruce planks, stripped spruce wood, spruce
  log, spruce fence, spruce stairs, lantern — is clear of all 259 entries;
- the ferryman and landing in `data/ferries.json` must stand at ground + 1 on
  dry ground, outside the dock's own blocks and its keep-clear box, and at least
  two blocks apart (the rule `tools/ferries.py` applies at R17F, checked here so
  a bad edit fails at the cheap gate);
- `tools/function_limits.py`: fills under the `/fill` limit, every write inside
  a chunk the function force-loads for its whole run.

## The re-apply step this needs

`tools/reapply.py` is **not** touched by this work. The step it needs:

```
R16H   the ferry docks (data/ferry_docks.json)
       [("fn", "cobblers:ferry_docks/%s" % d) for d in <ids from data/ferry_docks.json>]
```

listed from the committed data, not the built pack, exactly as `R16G` and `R16P`
already do, so the step exists whether or not the pack was built in that run.
Two records emit no function and must be skipped: `pacifidlog_south_jetty`
(structure `host`) writes no block, and any future `host` record likewise.

**Where in the order.** After **R9** (the pack donors, which stamp structures
whole and would erase anything written first) and after **R16** (the towns'
lights), because `sunset_quay` and `sunset_south_pier` lay boards beside piers
the town earthworks build at R8. Before **R17F**, which places the ferrymen over
RCON at the built docks — the docks have to exist before the boatmen stand on
them. `R16H`, between `R16G` (the gym buildings) and `R16P` (the portals), is
the natural slot.

`build/datapacks/cobblers_ferry_docks` also needs adding to the pack list in
`tools/reapply.py` (world-local is not required: these are overworld blocks that
a re-export replaces, so they are rebuilt every run like the gym buildings).

## The three that are not sited

| dock | why not |
| --- | --- |
| `jungle_ruins_landing` | the water export removed the Jungle Isle (`data/water_shape.json` `jungle_isle_bank`) and the jungle ruins now measure y55-61 against a sea level of y62. Its line `charter_jungle_ruins` is already `retired`, and `docs/NIGHT_REVIEW.md` review item 1 leaves the ruins' own home to the owner. A landing sited now would stand on drowned ground. |
| `appearing_island_landing` | its `near` (1600, 8400) is outside the heightmap (z past 8191), so `tools/ground.py` has no ground for it at all, and WATER_PROPOSAL decision 8 builds nothing there until the client models and EXP-006 land. |
| `trench_marker` | not sited in any data: Lugia's trench is Dive content and what a player stands on out there is undesigned. A dock needs somewhere to put its feet. |

## What building the docks exposed

Two line-level gaps that were invisible while the docks were planned, because
`tools/ferries.py` only checks a line once **every** one of its docks is built.
`python tools/ferries.py audit` now reports both, and until they are answered it
refuses the whole ferry pack:

1. **`tilpey_launch`: a lake line cannot be declared.** `tools/ferries.py` walks
   every crossing at one water level, `data/world.json`'s sea level y62, and
   Lake Tilpey stands at y77. Walked at y62 the whole lake reads as dry land, so
   declaring a barrier here would put a false number in the audit. The line
   stays `unsited` — and unemitted — until `tools/ferries.py` can take a
   crossing's own water level. Its three docks are built and waiting.

2. **`charter_relic`: SQ-SUNSET-01 has no completion field.** The gate's own
   `field` is `null` and `data/progression.json` declares no player boolean for
   the quest. While `sunset_quay` was planned this cost nothing, because the
   line was never emitted; now both its docks are built and the audit refuses
   it. The fix is one player boolean quest field for SQ-SUNSET-01 in
   `data/progression.json` and this gate's `field` naming it. (Not made here:
   `data/progression.json` was read-only for this work.)

3. **`pacifidlog_ferry` still has no town-end dock.** Its second stop is
   `pacifidlog_square`, which is `retired` at the old site (7206, 6955). The
   town moved by (-2050, +420) and its square is now at (5160, 7380); no dock
   record exists there. The mainland end is built; the line needs a new dock at
   the re-sited square before it can run. This also blocks the C3 repair below.

## The two recorded contract failures

Both were read before this work (`data/system_contracts.json` `fails_today`).

- **C3 `sound_ferry_from_the_jetty`** — still fails, and this work does not fix
  it. It measures a crossing of the retired Sound ferry between two ends, one of
  which is open water. Its recorded fix is "re-measure both ends against the
  current sea town and the live line, or retire the crossing with the line". The
  live line is `pacifidlog_ferry`, whose mainland end is now built — but whose
  town end does not exist yet (item 3 above), so the migration is still
  incomplete and the re-measure still has nowhere to point. One dock at the
  re-sited square is the remaining blocker. The registry entry is left alone.
- **C14 `ferry_cooldown-relog_restart`** — a fixture finding no live crossing to
  walk. Two more lines (`sunset_strait`, `northlight_packet`) have both docks
  built now, so the fixture may find a crossing once the two blockers above let
  `tools/ferries.py` emit again. **Not verified:** the tests are the test
  author's and were not run here. The registry entry is left alone.
