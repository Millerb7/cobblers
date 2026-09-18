# EXP-025: rosters that reach the world, and spawn where they should

**Status:** partly verified in a running server
**Date:** 2026-09-18
**Versions:** Minecraft 1.21.1, Fabric, Cobblemon 1.8.0+1.21.1, COBBLEVERSE mod set
**World:** the disposable `spawnproof` copy, seeded from the offline snapshot `2026-09-17-pre-grass`. Never the live world.

## Objective

An audit of every authored roster against Cobblemon's own spawn data
(`docs/world-building/ROSTER_AUDIT.md`) turned up two faults in the generator, not in the rosters:

1. **Reach.** `tools/compile_spawns.py` emitted entries only for boxes a route corridor passed
   through. 35 of 71 sub-regions had no corridor through them, so they compiled to nothing: 350
   authored entries no player could ever meet.
2. **Position.** Every compiled entry said `"spawnablePositionType": "grounded"`, including the 25
   species that never spawn on dry land in Cobblemon's own data. They were being asked to stand on
   the ground.

A third question followed from the first: once 43 million blocks carry our rosters, the inherited
spawns there are still untouched, so the regions would read as vanilla with our species sprinkled in.

## Implementation

- `tools/subregion_boxes.py` rasterises a sub-region polygon from `data/regions.json`, drops the
  cells a route corridor already covers, and merges the rest into axis-aligned boxes. Cell membership
  is by centre, so two neighbouring sub-regions cannot both claim a cell.
- `tools/position_types.py` derives a position type per species from the installed Cobblemon jar
  (fishing entries dropped, any dry-land entry keeps `grounded`, otherwise the most-used water
  position) and writes it into `data/spawns.json` as `spawnable_position`.
- `tools/suppress_inherited_spawns.py --subregions` adds every sub-region polygon to the
  anticondition box set.
- `tools/waterways.py` and `data/waterways.json` carry a river as a centreline instead of a polygon.

## Results

### Reach and position: verified in game

At Lake Tilpey (`5643 78 4093`), area cleared to zero first, one player standing still for five
minutes. `tilpey_waters` is one of the 35 sub-regions that had never reached the world, and all ten
of its entries were compiled as ground spawners before this change.

| t | what was within 64 blocks |
| --- | --- |
| 1 min | psyduck 9, basculin 4, goldeen 2, magikarp 1, barraskewda 1 |
| 5 min | psyduck 4, goldeen 3, basculin 3, barraskewda 1 |

Goldeen at y74, Basculin at y75-76, Magikarp at y75 — under a surface at y77, so the submerged
position is being honoured. Psyduck, the one `grounded` entry that appeared, was on the bank at y82.
Observed levels ran 39-48 against an authored band of exactly 39-48. Magikarp, Goldeen, Basculin and
Barraskewda appear in no other roster, so the spawns can only have come from `tilpey_waters`.

### A bug the first creek reading found: colliding spawn ids

The first five minutes on the creek bank produced no Wooper at all, with the site itself in order:
open sky, water two blocks away, inside creek box (1968-1983, 1760-1823).

The generator was emitting one id per species per sub-region or waterway *segment*, not per box. The
creek file held 320 entries under 132 distinct ids; the sub-region files held 14,366 entries under
about 620. Whether Cobblemon keys spawn details by id is not established, but duplicates are wrong
either way. With the box index in the id the pack has 21,752 entries and no duplicates, and the creek
started producing.

This puts an asterisk on the Tilpey reading above, which was taken before the fix: the fish and their
levels are real, but the roster may have been running on a fraction of its boxes.

### The creek: verified in game

At the creek bank (`1976 119 1784`), area cleared, five minutes.

| t | what was within 64 blocks |
| --- | --- |
| 1 min | bunnelby 9, heracross 9, scyther 5, teddiursa 1 |
| 5 min | hoothoot 12, heracross 8, bunnelby 4, scyther 2, **wooper 1, quagsire 1** |

Quagsire level 28 at (1997, 121, 1783), Wooper level 29 at (2008, 120, 1777), against a creek band of
24-30. Everything else in the reading is `foothill_woods` at levels 21-23, so the two are
unambiguously the creek's.

It reads thin: two of twenty-eight. The cause is not the weight split (the creek's 56 against
foothill_woods' 86 would give it 39 per cent of the spawns it contests) but how few of the sampled
positions are beside water at all. `neededNearbyBlocks` is doing exactly what it was chosen for, and
the same restriction that keeps Wooper out of the woods keeps it rare in a reading that counts the
woods too.

Geodude and Mankey, which belong to no roster of ours, appeared in the first creek reading inside a
suppression box and did not reappear in the second. Most likely they wandered in from outside the
cleared radius. Not a confirmed hole, but worth re-checking.

### Suppression cost: measured, three box sets, same spawn pack

| box set | boxes | ground covered | heap after GC | dead overshoot |
| --- | --- | --- | --- | --- |
| route corridors only | 637 | 3.0M blocks | 3,551 MB | 3,520 blocks |
| sub-region grid 64, merge 64 | 362 | 45.6M | 3,245 MB | 25,024 (0.1%) |
| sub-region grid 32, merge 32 | 926 | 45.7M | 3,841 MB | 10,432 (0.0%) |

Grid 32 costs 290 MB over the corridors-only pack for fourteen times the ground, and is the one
installed. Dead overshoot is ground where suppression reaches but no roster of ours fills it. The
merge grid matters far more than the sub-region grid: sub-grid 32 merged at 64 gives only 220 boxes,
fewer than the corridors-only pack, but its dead overshoot jumps to 1.79M blocks (3.8%).

Full pack: boot 40.5 s, no reload failure, heap 3,854 MB after GC against a 10 GB ceiling. Spawn pack
3.2 MB to 9.5 MB, 18 files to 82.

### Two schema facts, from Cobblemon's own data

- **A regional form is fine on a `spawn_pool_world` entry** (`"pokemon": "wooper paldean"`; Cobblemon
  ships twelve such entries) and fatal in a **habitat pool**, whose `species` field takes a bare id
  and throws `InvalidIdentifierException` on the space — which aborts the server boot (EXP-021).
- **Nothing spawns in mid-air.** There are five position types: `grounded`, `submerged`, `surface`,
  `seafloor`, `fishing`. Perching is not a position type but a base-block condition: 343 stock
  entries across 97 species spawn in treetops, all `grounded` with
  `neededBaseBlocks: ["#cobblemon:trees"]`. Whether a **habitat pool** spawn accepts that condition
  is unproven: no stock pool uses one, though `HabitatSpawn` carries a `condition` field.

## Limitations

- The sub-region rosters were verified at one site. 34 other newly-live sub-regions are not observed.
- The suppression measurement is a single boot per box set, and heap after GC varies between runs.
- The audit that found both faults has not been independently reviewed; it is item 9 in
  `docs/HANDOVER_CODEX.md`, with the two mistakes found while writing it.
- `tools/subregion_boxes.py`, `tools/waterways.py` and `tools/position_types.py` have no pytest
  suites, and their tests would have to be written by a different agent.
- Whether suppression at the sub-region scale actually removes the inherited spawns in play is not
  observed: the Tilpey reading shows our roster arriving, not vanilla leaving.
