# Gym 4: Erika, The Root Court

Record: `data/gym_arenas/gym4.json` (schema `gym_arena/1`, read by `tools/gym_arenas.py`). Status: authored
2026-10-08, offline checks only. Nothing here has been built in a world or seen in a running game.

## The reading

Peak Pond Hollow is the garden town where Erika keeps the peace between the residents and the arrivals
(`TOWN_CHARACTER.md` gym4_town). The Great Glasshouse is the gardeners' house and her walled court is its north end.
Under that court is where she hears them: a **mediation court dug into the roots of the great cherry**. It is a ring,
not a hall (Brock's is a colonnaded rectangle; this has no straight wall in the part a player sees):

- a round floor of mud brick, radius 10 about (4311, 1504), with a ring of cherry plank inlaid at radius 8..9 (the line
  the parties stand behind) and a round of moss at its middle, between the two Pokemon marks (the common ground);
- round it a low **bar** (two courses high, so nobody steps up from the floor) and four tiers of cherry benches
  rising to 6 over the floor, one side for each party; roots stand in the second tier and run up into the vault,
  dividing the bowl into bays; the outer tier is a bed of moss and azalea;
- the vault above is stepped (y104 over the middle, 103, 102 at the rim), patched with rooted dirt, hung with hanging
  roots, ten glow-berry vines and shroomlights set in the ceiling;
- one **aisle** cut through the benches on the north side: both parties come in by it;
- Erika is not in the ring. She sits at the far (south) side on a **raised bench of cherry**, four courses over the
  floor, with a front panel, a high back and two cherry posts at its corners, under a great root of the tree that has
  come down through the vault behind her: the place of the one who hears both.

Palette (all from the town's own): packed mud, mud brick, moss, cherry plank, stairs and stripped log, mangrove
roots, rooted dirt, hanging roots, cave vines, azalea, shroomlight, lantern, oak fence, hay. None is named by a spawn
condition (checked against `data/spawn_blocks.json`: flowering azalea, spore blossom, pink petals and leaves are, so
they are not used).

## The walk in

1. The player has passed the juniors and the puzzle route and drops into Erika's walled court (building step 6):
   the mulch bed at z1481..1484, the old spawner at (4308, 110, 1480).
2. At the court's south end a kerb of mud brick and a fence mark a square well, x4309..4314, z1479..1484, round a
   post of stripped cherry log that comes up flush with the court floor. The kerb has **one gap**, at
   (4311, 110, 1484), where the hay of the bed comes up to the first tread.
3. The stair winds down round the post: 25 cherry stair treads, 16 levels, from y110 to a landing at y94, with
   shroomlights set into the post. (Walled in mud brick; nothing between treads is rock.)
4. At the bottom a door in a cherry-log frame, one wide and three high, at (4311, 95..97, 1484) opens south on the
   **aisle**: 7 wide (x4308..4314), 11 long (z1485..1495), bench tiers rising on both sides, roots in the vault.
   The vault opens to 8 courses over the aisle.
5. The aisle opens into the ring at z1496. The floor is 21 across at its widest (x4301..4321 at z1504). The bench
   tiers curve away on either hand. Ahead, 16 to 27 blocks away, the raised bench.
6. The first floor cell the player reaches is (4311, 95, 1483), 31.3 from Erika's stand; the walk from the door
   to the foot of the bench is 28 blocks, down the moss strip along the axis. A battle can start only from the floor
   (the rctmod trigger is 16 and needs sight of her): the measured cells a battle can start from run z1499..1508,
   so the aisle is quiet.

## Where they stand

| | |
|---|---|
| Erika's seat | (4311, 98, 1514), spawner flush in the bench top, redstone at (4311, 97, 1514); she stands at y99. The Challenge copy's spawner moves to (4309, 98, 1514), two west |
| Erika's trainer stand | (4311, 97, 1513): when the battle starts she steps to the bench's front edge |
| Erika's Pokemon | (4311, 93, 1505), 6.5 from the bench face (z1512) |
| The challenger's Pokemon | (4311, 93, 1500), 5 from Erika's |
| The challenger | stands on the axis at (4311, 95, 1497), over the stand mark (4311, 93, 1497), 3 behind their Pokemon and 7 from the ring's centre (inside the plank ring) |

## Dimensions (measured from the model, `python tools/gym_arenas.py check --gym gym4`)

| | |
|---|---|
| Shell box | x4290..4332, y92..106, z1477..1519 (43 x 15 x 43), packed mud, solid; the hall is carved out of it. Inside the gym_erika spawn-free zone (no change) |
| Floor | y94 (stand y95), circle radius 10 about (4311, 1504); 21 across |
| Bowl | bar to radius 11.2 (top y96), tiers to 13.2 / 15.2 / 17.2 / 19.2 (tops y97 / y98 / y99 / y100); 19.2 outer |
| Ceiling | air to y104 within radius 11.2, y103 within 15.2, y102 beyond; ceiling course y105..106 |
| Bench | x4305..4317, z1512..1516, top y98 (4 over the floor; the check wants 2..5), 13 wide, 5 deep |
| Descent | newel stair ring x4310..4313, z1480..1483, first tread (4311, 110, 1483), landing (4311, 94, 1483) |
| Written | 42,642 cells in 858 commands in `cobblers:gym_arenas/gym4` (the seat move and the old-leader sweep apart) |
| Cover | slack 0 (top course y106 under a natural top at 108 beneath the building and 109 on the lot) |

**Size against the leader's team.** Her widest sweep is Victreebel's, clear radius 5.28 (`data/gym_arena_sizes.json`;
Tangrowth is the tallest, clear height 2.72, so the check wants air to y98 over the floor). Measured by an
independent scan of the model (every non-open cell at y95..98 within 14 of each mark; the check's own rule): the
nearest solid to Erika's mark is the bench face at **6.50**, **1.22** outside the sweep; to the challenger's mark it
is the bar at the aisle's mouth, **6.36**, **1.08** outside. Straight up the first solid over either mark is the
ceiling at y105: **6** courses of air above the y98 the sweep needs. The floor is 21 across against the 10.56 the
sweep needs (about double).

**Search and light.** All four Battle Positions blocks are found from all 162 cells a battle can start from (cells
within 16 of her with a line of sight, z1499..1508; nearer the bench her own bench blocks the line). 533 cells are
walkable in all (court, stair, aisle, floor); no walkable cell reaches y96 inside the arena, so the bar, tiers and
bench cannot be climbed from the floor. Block light over the 380 walkable cells inside the shell: minimum 4, median 8,
140 under 8 (lanterns on the bar every fifteen degrees, four lanterns hung on chains over the floor, shroomlights in
the vault and the post; the aisle's axis reads 5..9).

## What is not verified, and what I worked round

- Not built in a world and not seen. A fence, a cave vine, a hanging root or a stair block is placed by command with
  default states; their neighbour-shape updates (fence arms, stair corners, vines reaching down) and whether vine
  tips stay with their support are untested.
- The check models cave vines, hanging roots, azalea and mangrove roots as solid blocks (they are neither in the
  tool's open nor partial lists), and gives vines no light. They are all at y101 or higher and the lamps are lanterns
  and shroomlights, so the verdict does not lean on them either way.
- The check's walk is generous (fall any distance, jump one). The kerb and fence make the well hard to fall into;
  nobody can step up from the floor onto the bar (two courses). Neither is proved in a game.
- The ceiling and walls are exposed packed mud and mud brick. Whether that reads as roots-and-earth or as plain brown
  needs a look in game.
- Two things the record cannot say, worked round: (1) the tool has no circle op, so the bowl is `fill` rectangles
  merged from a circle by a one-off scratch script (a pure-data record, 526 parts); regenerating it means editing
  the record or rerunning that script, not the tool. (2) A stair needs a kerb and fence that the `newel_stair` op does
  not build; they are plain `fill` ops after it.
- The chest at (4312, 111, 1479) stands on the new kerb and was not moved; the court's lantern at (4313, 111, 1482)
  stands on the hay of a ring cell the stair does not carve to the top, and is untouched.
