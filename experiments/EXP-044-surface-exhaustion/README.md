# EXP-043: Surface exhaustion in the open sea

**Objective:** a player cannot cross the sea by swimming. They can swim the shallows and a little way into open water,
tire, and have to turn back. Riding a water Pokemon removes the limit.

**Why:** the owner, 2026-09-26: the Route 1 ocean is reachable, but "a player on route one for the first time cant swim
without a surf mon". With vanilla air items removed (EXP-042), swimming out across the surface was the last way round
the water progression.

**Source of the brief:** the owner asked for "surface exhaustion as briefed". No written brief for it was found in the
repository or the session transcript, so this is the builder's reading of it. Every number below is a judgement call
in the review list.

Versions: Minecraft 1.21.1 Fabric, Cobblemon 1.8.0, staging `cobblers-dryrun11`, in pack `cobblers_blackout`
(world-local).

## Rule

| Where (distance from land) | Swimming, unaided | With a trained water partner in the party | Riding anything |
|---|---|---|---|
| Land, lakes, the shallows (under 96) | recovers 2 per tick | recovers | recovers |
| Open water (96-256) | +1 per tick | +0.5 per tick | recovers |
| The deep (256+) | +2 per tick | +1 per tick | recovers |

| Fatigue (ticks) | Effect |
|---|---|
| 400 (20 s of open water) | yellow warning: "Your arms are growing heavy. The open sea is no place to swim." |
| 600 (30 s) | Slowness I |
| 900 (45 s) | Slowness II, Hunger, red warning: "You are exhausted. Turn back to shore, or ride a water Pokemon." |
| 1200 (60 s) | "The sea is pulling you under.", then the water ladder's hit (half health, lethal from half health) every 3 s in open water, faster in the deep. A death is environmental: money and the checkpoint, no items |

At the measured sprint-swim of 5 blocks per second (EXP-042 session 3), an unaided swimmer reaches:
- the warning about 100 blocks past the shallows' edge;
- collapse about 300 blocks from land, or sooner in the deep band.

A swimmer who turns at the warning gets home.

## Mechanism

- **The zones:** `tools/open_water.py` builds them from the canonical heightmap, never a world.
  - Grid: 16-block cells over the playable world.
  - Land is a cell with any column at or above sea level (y62).
  - The sea is the below-sea-level cells connected to the border, so inland lakes are excluded even where their
    floors dip below y62.
  - Bands are by Chebyshev distance from land.
- **The result on the current heightmap:** open water 9.9 km², the deep 39.8 km².
  - Spot checks: Route 1's shallows, Lake Tilpey, Shrew Lake, Relic Island and spawn are all free; the far west
    margin is deep.
- **In the pack:** one function per cell row, `surface/r/<z>` (640 files), lists that row's open and deep runs.
  - A swimmer costs one macro call and a few range checks, every 10 ticks.
  - The zone is tested only while the player's feet or eyes are in water and they ride nothing (`execute on vehicle`).
- **Note:** these bands measure distance from land on 16-block cells, while the spawn rosters' marine bands measure it
  from sub-region cells, so the two lines differ by some tens of blocks. The spawn bands decide what spawns; these
  decide fatigue.

## Results so far (no player)

- The pack loads with no function errors on staging (2026-09-27); the constants are in `bo.cfg`.

## Test (the owner)

1. From the Route 1 beach, sprint-swim straight west. Expect:
   - the yellow warning after about 20 s of open water;
   - Slowness at about 30 s;
   - the red warning at about 45 s;
   - the hits from about 60 s.

   Turn back at the red warning and check you recover on the shallows.
2. With Surf training and a Lapras in the party, repeat: every threshold should come at twice the distance.
3. Ride the Lapras out past where you collapsed: no fatigue.
4. Swim Lake Tilpey end to end: no fatigue (a lake is not the sea).

## Open

- **Vanilla boats** are vehicles, so a boat crosses anything. Whether boats beyond the shallows break is the owner's
  decision (docs/mechanics/WATER_PROPOSAL.md).
- The numbers are first guesses from the measured swim speed.
