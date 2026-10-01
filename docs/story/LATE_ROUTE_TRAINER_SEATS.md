# Routes 4-8: where the twenty-eight late route trainers stand

Seated 2026-09-30 by `tools/late_route_trainers.py` into `data/late_route_trainers.json`. Nothing here
has been placed in a world: these are planned positions from the heightmap and the walked lines, and the
probe list at the bottom is how someone with a world checks them.

Routes 1-3's thirteen were seated by `tools/route_events.py`; their seats are untouched by this pass
(`data/route_trainers.json` is byte-identical). Victory Road's ten (`data/vr_trainers.json`) and the
mansion's five (`data/mansion_guardians.json`) are untouched too. With these 28, every route trainer
`data/trainers.json` holds now has a seat: 51 records, 51 seats.

## The rule, and whose it is

The seating rule is Routes 1-3's, and the tool reuses `route_events`' own `Road`, `frame` and `yaw_to`
rather than reimplementing them, so the geometry cannot drift between the two sets:

> the authored point when it is already off the walked line, else `offset` blocks onto the flatter
> shoulder, facing the road.

**All 28 authored points lie exactly ON the walked line** (measured distance 0.0 for every one; their
`sampled_y` also matches `tools/ground.py` to within half a block, so they were sampled from this same
heightmap). So all 28 are shouldered, the same way routes 1-3's were.

What this pass adds is the check routes 1-3 did not need, because their thirteen listed points happened
to land on flat shelves. A candidate becomes a seat only if:

| test | threshold | where the number comes from |
|---|---|---|
| relief over the 3x3 it stands in | <= 1 | routes 1-3's thirteen seats measure 0 or 1 |
| relief over the 5x5 around it | <= 2 | the same thirteen measure 0, 1 or 2 |
| height difference from the road's own ground | <= 2 | so the fight is at eye level with the walked line, not on a ledge |
| distance from every walked line (any route) | >= 2.2 | routes 1-3's seats measure 2.2 to 4.0 |
| distance from its own walked line | <= 7.0 | inside rctmod's 8-block sight reach: off the road, still in sight |
| inside a town, a placement footprint + 4, a spawn-free zone, a Routes 1-3 scene area, 16 blocks of a ferry dock, 8 blocks of another trainer's seat | refused | the brief; every candidate is checked and `--refusals` prints why each was rejected |

The search tries the shoulder at the authored cell first, both sides, flatter side first, at offset 3,
then 4, 5, 6; only then does it step along the route (±2, ±4 … ±120 path cells, nearest first). **26 of
the 28 are seated at offset 3 at the authored cell** — the plain precedent, with nothing added. The
other two are below.

**Spacing is not ours.** The distance along each route is `data/trainers.json`
`placement.at_distance_blocks`, authored from `docs/story/TRAINER_RULES.json`. The shoulder moves a
trainer sideways, and along the route only where the authored cell has no standable shoulder. Route 4
spaces six over 3,453 blocks (one about every 500); route 5 four over 1,051 (one every 112 to 289).
Re-spacing them would be re-authoring `TRAINER_RULES.json`, which is another unit's file.

**Ground** is `tools/ground.py`, the canonical heightmap rounded. No world save was read to decide any
position (`tests/test_ground_rule.py` passes, 10 tests).

**Eye contact.** None of the 28 forces a battle on sight. Routes 1-3 force exactly one (the first, as
the eye-contact lesson); Victory Road's ten all do. Whether each route's `gym_prep` trainer should be
unavoidable is a design call for the owner, not this tool's.

## The twenty-eight

`seat` is where the trainer stands (feet); its ground block is one below. `moved` is from the authored
point. `off` is the shoulder offset, `along` the step along the route in path cells.

| id | name | seat (x y z) | yaw | faces | moved | off/along | relief 3/5 | gap |
|---|---|---|---|---|---|---|---|---|
| route_04_trainer_01 | Snowfield Novice | 1899 142 1568 | -18 | south | 3.2 | 3/0 | 1/1 | 350 |
| route_04_trainer_02 | Alpine Ranger | 2371 158 1304 | 162 | north | 3.2 | 3/0 | 0/2 | 591 |
| route_04_trainer_03 | Campfire Keeper | 3070 108 1370 | -135 | north-east | 2.8 | 3/0 | 0/0 | 832 |
| route_04_trainer_04 | Ridge Scout | 3224 105 1563 | -135 | north-east | 2.8 | 3/0 | 0/0 | 257 |
| route_04_trainer_05 | Bird Watcher | 3569 104 1889 | -162 | north | 3.2 | 3/0 | 1/1 | 522 |
| route_04_trainer_06 | Naturalist | 3992 112 1841 | -18 | south | 3.2 | 3/0 | 0/0 | 466 |
| route_05_trainer_01 | Field Hand | 4380 115 1811 | -72 | east | 3.2 | 3/0 | 1/1 | 289 |
| route_05_trainer_02 | Field Medic | 4355 116 1962 | -90 | east | 3.0 | 3/0 | 0/0 | 159 |
| route_05_trainer_03 | Mind Reader | 4363 115 2134 | -108 | east | 3.2 | 3/0 | 0/0 | 174 |
| route_05_trainer_04 | Trail Warden | 4431 114 2218 | -108 | east | 3.2 | 3/0 | 0/0 | 112 |
| route_06_trainer_01 | Marsh Novice | 4921 136 2691 | -135 | north-east | 2.8 | 3/0 | 0/0 | 377 |
| route_06_trainer_02 | Marsh Ranger | 5146 132 2857 | 0 | south | 3.0 | 3/0 | 0/1 | 292 |
| route_06_trainer_03 | Night Courier | 5454 125 2939 | 18 | south | 3.2 | 3/0 | 0/0 | 344 |
| route_06_trainer_04 | Lake Pathfinder | 5756 106 3078 | 45 | south-east | 2.8 | 3/0 | 0/0 | 359 |
| route_06_trainer_05 | Displaced Archivist | 5964 96 3217 | 45 | south-east | 2.8 | 3/0 | 0/1 | 265 |
| route_07_trainer_01 | Expedition Novice | 6293 95 3597 | -135 | north-east | 68.0 | 4/+48 | 0/0 | 237 |
| route_07_trainer_02 | Bridge Hand | 6422 93 3714 | -162 | north | 3.2 | 3/0 | 0/0 | 176 |
| route_07_trainer_03 | Shore Battler | 6582 92 4055 | -72 | east | 3.2 | 3/0 | 0/1 | 496 |
| route_07_trainer_04 | Crater Geologist | 6522 108 4360 | -72 | east | 9.2 | 6/+4 | 0/0 | 327 |
| route_07_trainer_05 | Ash-Path Ranger | 6430 106 4605 | -72 | east | 3.2 | 3/0 | 0/0 | 286 |
| route_07_trainer_06 | Prospector | 6212 104 4832 | -72 | east | 3.2 | 3/0 | 0/0 | 320 |
| route_08_trainer_01 | Crater Novice | 5854 116 5090 | 162 | north | 3.2 | 3/0 | 0/0 | 261 |
| route_08_trainer_02 | Crater Scout | 5661 122 5183 | 0 | south | 3.0 | 3/0 | 0/0 | 232 |
| route_08_trainer_03 | Grassland Keeper | 5294 136 5282 | -18 | south | 3.2 | 3/0 | 0/0 | 407 |
| route_08_trainer_04 | Sand Runner | 5017 147 5384 | -18 | south | 3.2 | 3/0 | 0/0 | 319 |
| route_08_trainer_05 | Plateau Ranger | 4614 157 5604 | -18 | south | 3.2 | 3/0 | 0/0 | 494 |
| route_08_trainer_06 | Rift Surveyor | 4160 126 6047 | 135 | north-west | 2.8 | 3/0 | 0/0 | 639 |
| route_08_trainer_07 | Final Warden | 3893 102 6247 | -18 | south | 3.2 | 3/0 | 0/1 | 349 |

### The two that are not at their authored cell

Both because **the authored point is inside a town's recorded ground**, which is a finding for whoever
authors `docs/story/TRAINER_RULES.json`, not something this pass can fix at the source:

- **route_07_trainer_01** (Expedition Novice). Authored 170 blocks along route 7, at (6248, 3546), which
  is inside `gym6_town`'s bounds (6092, 3292)-(6314, 3596) — Saffron. Route 7 does not leave that box
  until 253 blocks along. Seated at the first standable shoulder past it, 48 path cells on, at (6293, 95,
  3597): 68 blocks from the authored point, still 176 blocks before trainer 02, and still the first
  fight on route 7. Note that `town_bounds` is a bounding box with an 8-block margin, so the seat is 9
  blocks outside the outermost thing Saffron records and may be considerably further from any building.
- **route_07_trainer_04** (Crater Geologist). Authored at (6531, 4358), inside `gorge_hamlet`'s box.
  Seated 6 blocks out and 4 cells on, at (6522, 108, 4360), 9.2 blocks from the authored point.

### What is NOT excluded (our list is not the world)

The exclusions are our own data: `data/placements.json`, `data/scenes.json`, `data/ferry_docks.json`,
`data/spawn_suppression.json` and the four seat files. Anything in the world that no generated list
knows about is not covered — a donor template's outbuildings beyond its recorded `size`, a mod-placed
structure, Repurposed Structures' villages, and the gym and League trainer spawners that live inside
somebody else's template. A seat 3 blocks off a walked line is unlikely to land in one, and nothing
here proves it did not.

**Painted water is not checked at all.** The heightmap gives land height; whether a column holds lake
or river water lives in the water-shape pass's own data, not here. Every seat sits level with the dry
walked line, which is the best an offline pass can do. The probe list is what settles it.

## The quest fields the owner must declare

Each of the 28 sets `quest.<id>.defeated`, and `tools/route_trainers.py` refuses to emit a trainer whose
fields are not declared in `data/progression.json` `quest_fields`. None of the 28 are declared
(2026-09-30); the generator names all 28 in one run. `data/progression.json` is read-only to this pass.

```
quest.route_04_trainer_01.defeated   quest.route_06_trainer_01.defeated   quest.route_08_trainer_01.defeated
quest.route_04_trainer_02.defeated   quest.route_06_trainer_02.defeated   quest.route_08_trainer_02.defeated
quest.route_04_trainer_03.defeated   quest.route_06_trainer_03.defeated   quest.route_08_trainer_03.defeated
quest.route_04_trainer_04.defeated   quest.route_06_trainer_04.defeated   quest.route_08_trainer_04.defeated
quest.route_04_trainer_05.defeated   quest.route_06_trainer_05.defeated   quest.route_08_trainer_05.defeated
quest.route_04_trainer_06.defeated   quest.route_07_trainer_01.defeated   quest.route_08_trainer_06.defeated
quest.route_05_trainer_01.defeated   quest.route_07_trainer_02.defeated   quest.route_08_trainer_07.defeated
quest.route_05_trainer_02.defeated   quest.route_07_trainer_03.defeated
quest.route_05_trainer_03.defeated   quest.route_07_trainer_04.defeated
quest.route_05_trainer_04.defeated   quest.route_07_trainer_05.defeated
                                     quest.route_07_trainer_06.defeated
```

Until they are declared, `tools/route_trainers.py` fails closed and with it
`tests/test_route_trainers.py` and `tests/test_mansion_guardians.py` (their module fixture calls
`files()`). That is the fail-closed design working, not a regression.

## PROBE LIST: what to check in the world

Ten of the 28, worst first: the two nearest a town edge, the four on the lowest ground (where painted
water is most likely to disagree with the heightmap), the three with any relief at all, and the one on
the Rift's lip. Each probe is two reads at one column:

| x | y | z | expected |
|---|---|---|---|
| 6293 | 94 | 3597 | solid, non-water ground (route_07_trainer_01's feet block; 1 block outside Saffron's box) |
| 6293 | 95 | 3597 | air before the apply; after R17 an `rctmod:trainer` with `TrainerId:"route_07_trainer_01"` |
| 6522 | 107 | 4360 | solid, non-water ground (route_07_trainer_04; 1 block outside gorge_hamlet's box) |
| 6522 | 108 | 4360 | air before; after, `rctmod:trainer` `TrainerId:"route_07_trainer_04"` |
| 6582 | 91 | 4055 | solid, non-water ground — the lowest seat of the 28 (route_07_trainer_03; ground drops to 89 within 8 blocks) |
| 6582 | 92 | 4055 | air before; after, `rctmod:trainer` `TrainerId:"route_07_trainer_03"` |
| 6422 | 92 | 3714 | solid, non-water ground (route_07_trainer_02; ground drops to 90 within 8 blocks) |
| 6422 | 93 | 3714 | air before; after, `rctmod:trainer` `TrainerId:"route_07_trainer_02"` |
| 5964 | 95 | 3217 | solid, non-water ground (route_06_trainer_05; its ground is exactly `watering_hole`'s level, y95) |
| 5964 | 96 | 3217 | air before; after, `rctmod:trainer` `TrainerId:"route_06_trainer_05"` |
| 3893 | 101 | 6247 | solid, non-water ground (route_08_trainer_07; ground drops to 100 within 8 blocks, `arrow_lake`/`marshy_marsh` level) |
| 3893 | 102 | 6247 | air before; after, `rctmod:trainer` `TrainerId:"route_08_trainer_07"` |
| 2371 | 157 | 1304 | solid ground — the roughest seat (route_04_trainer_02, relief 2 over its 5x5) |
| 2371 | 158 | 1304 | air before; after, `rctmod:trainer` `TrainerId:"route_04_trainer_02"` |
| 1899 | 141 | 1568 | solid ground — the steepest surroundings (route_04_trainer_01; ground drops to 138 within 8 blocks) |
| 1899 | 142 | 1568 | air before; after, `rctmod:trainer` `TrainerId:"route_04_trainer_01"` |
| 3569 | 103 | 1889 | solid, non-water ground (route_04_trainer_05, relief 1; ground drops to 101 within 8) |
| 3569 | 104 | 1889 | air before; after, `rctmod:trainer` `TrainerId:"route_04_trainer_05"` |
| 4160 | 125 | 6047 | solid ground, nothing hollow below (route_08_trainer_06, the Rift Surveyor, on the Rift's lip) |
| 4160 | 126 | 6047 | air before; after, `rctmod:trainer` `TrainerId:"route_08_trainer_06"` |

The y+1 column (head height) should be air at all ten. A seat whose feet block is `water`, whose feet
block is missing, or whose ground is not the y listed is a seat this pass got wrong, and the cause will
be either painted water or something in the world that no list of ours knows about.

The whole set can be swept at once with
`execute as @e[type=rctmod:trainer] run data get entity @s Pos` after the apply and compared against
`data/late_route_trainers.json`, but a sweep that agrees proves the apply ran, not that the ground is
right. The ten columns above are the ones that prove the ground.

## How it reaches the game

1. `tools/late_route_trainers.py` writes `data/late_route_trainers.json` (committed). Run without
   `--write` it re-seats and fails on drift, the way `tools/route_events.py` checks routes 1-3.
2. `tools/route_trainers.py` reads it as a fourth seat source and emits each one's team, mob, dialogue,
   empty loot table, defeat advancement, won-function and cycle lines. Verified: 359 files for 56 seated
   trainers once the quest fields are declared.
3. `tools/reapply.py` R17 summons each seat over RCON (`rctmod trainer summon_persistent`), pins it at
   movement speed 0 and makes it invulnerable. It needs one new `prepare` job, named in the handback.
