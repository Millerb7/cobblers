# Heaven's Arena: the north floor of the Windward Deep, measured

The owner, 2026-10-03, on the in-game map: Heaven's Arena "was meant to go in the slot next to it: the empty
space in the north of the Deep particularly". This note measures that space. It changes no data and builds
nothing; the move itself is a separate job.

**How it was measured.** On commit `b78b6f0`: `rift_deep.model()` (the ring model, recomputed from the canonical
heightmap) and `deep_city.build(env_source_root(), None)` run once (11 s, not minutes), its canvas reduced to
per-column owners and the blocks at y1-2; `deep_city.riser_field()` re-run to depth 400 for true riser distances.
Nothing was read from a world. "Free" below means a y0 floor column on which the city writes nothing but
paving (`plaza`, `sidewalk`, `fill_light` at y0). Distances are Euclidean in blocks between column centres,
walks are 4-connected over columns with nothing solid at y1-2. Figures marked RELAYED come from the owner's
screenshot and were not measured.

## 1. What the empty north area is

It is **the Deep's floor (y0) on the sheer side**: the 55-degree sector toward `entrance_to_e4` where the pit
keeps only ring 0 and then drops one 66-block face to the floor (`data/rift_deep.json:22-27`,
`tools/rift_deep.py:185-204`). In the model it is `ring 4, tread y0, sheer = True`: **25,518 columns**; the
non-sheer floor (the Core proper, where the arena drum now stands) is only 3,757.

The city leaves its middle empty on purpose, for three reasons, none of them steepness (it is dead flat, y0):

| Why | Source |
| --- | --- |
| **The lot rule.** Buildings are seeded only where a column is within 16 of a riser foot (`lot_zone = (dist < zone)`, `zone_depth` 16). On the sheer floor 7,379 columns are within 16 and **18,139 are not**; the furthest column, (3589, 3153), is 91 from any riser. The 27 Stacks buildings fill the rim band; the rule cannot put anything in the middle. | `tools/deep_city.py:1079`, `data/deep_city.json:99` |
| **It is the city's square by design.** The sheer floor is paved flush at y0 in polished deepslate on a 9-block basalt grid "so the floor reads as the city's lowest square, not the bottom of a hole": 18,581 columns of `plaza`. DEEP_CITY.md gives the Core "the plaza before Victory Road's mouth". | `data/deep_city.json:150-156`, `tools/deep_city.py:1374-1383`, `docs/world-building/DEEP_CITY.md:97` |
| **The mouth plaza keep-clear** covers its north-west quarter: x3528-3592, y1-40, z3064-3124 ("open floor, nothing standing on it"), 3,965 sheer-floor columns; the tunnel box x3555-3565, y0-9, z2974-3066 runs north from Victory Road's mouth at (3560, 1, 3064) under ring 0. | `data/deep_city.json:249-251`, `tools/deep_city.py:771-772`, `data/vr_caves.json:86-91` |

And the arena never considered it: the spire/arena site search takes **only non-sheer** floor columns
(`mask & (T == floor) & ~M["sheer"]`, `tools/deep_city.py:947`).

## 2. Its usable extent

**20,080 free columns at y0** (16,115 outside the mouth plaza keep-clear), centroid (3584, 3141). Their convex
hull is 21,381 columns, so the shape is very nearly convex: **a pentagon**, simplified (area 20,889):

| Vertex | (x, z) | What closes it |
| --- | --- | --- |
| NW | (3528, 3064) | the 66 face, beside Victory Road's mouth |
| NE | (3615-3628, 3065-3073) | the face, then Stacks lots `lot_3608_0_3062`, `lot_3624_0_3065` |
| E | (3681, 3142) | Stacks against ring 0's riser (roofs y66) |
| S (apex) | (3592, 3240) | narrows to 12 wide at z3230 and joins the Core floor beside the arena drum |
| W | (3496, 3175) | Stacks against ring 0/1's riser (roofs y66, y49) |

Width of the widest free run per row: z3080 106 (x3528-3633), z3100 131, z3120 153, **z3140 172 (x3508-3679)**,
z3160 163, z3180 138, z3200 82, z3210 54, z3220 38 (x3576-3613), z3230 12. All of it is one level, y0, open
to the sky; nothing of the city spans over it (no bridge or deck is built north of the drum).

Its edges are the 27 Stacks buildings (`district == "stacks"`, 5,438 columns), whose roofs are the streets above
them: y66 (the north promenade, ring 0) on the north, north-east and west edges; stepping y49, y32, y15 down the
south-east and south-west edges toward the apex.

## 3. What is in or touching it

| Thing | Where | Relation to the north floor |
| --- | --- | --- |
| Mouth plaza keep-clear | x3528-3592, y1-40, z3064-3124 | inside it: its NW quarter |
| Mouth tunnel keep-clear | x3555-3565, y0-9, z2974-3066 | touches its north edge at the mouth |
| Victory Road | mouth (3560, 1, 3064); guide runs north from there (`data/vr_caves.json` guide); first seat relayed at (3563, 2, 3009) | all of it is north of z3066, under ring 0 and beyond; nothing under the floor |
| Stacks, 27 homes | the rim band | doors open onto the floor; every one is reachable today |
| Lift-bank-3 stair towers (y0-y15) | west x3574-3580 z3238-3244, door (3580, 3241); east x3617-3623 z3279-3285, door (3620, 3279) | the west one stands at the apex, the nearest stair to the floor. No lift or stair is on the sheer side (`data/rift_deep.json:63`) |
| Heaven's Arena drum (site A) | centre (3609, 3249), r16, y0-y128 | at the apex. It **narrows the Core-to-floor link to under 5 wide** (a 3-wide walk passes, a 5-wide one does not) |
| Arena bridges y15 | east to (3643, 3249), west to (3575, 3249), south to (3609, 3284) | none north |
| Sink Gate | door (3694, 3387), lip to ring 0 | 242 and 258 from option A's and B's centres; ring-0 walk to the floor's NE edge about 435 (2D estimate) |
| HQ tower | x3428-3438, z3303-3313, top y132 | about 197 west-south-west |
| HQ basement, secure shaft, shaft head, room partition | all west of x3445 | 177-203 away |
| Relic hall (underground) | centre (3390, 3262), r21, y5-34 (`data/relic_underground.json` geometry.hall) | about 190 west, under other ground |
| Hoopa's cradle (reserved) | box x3317-3397, y-12..72, z3266-3346 | 210 away |
| Rift zone | the whole `the_deep` region is zone z2 (`data/rift_zones.json:1820`) | same zone as site A; no boundary crossed |

## 4. The largest dome footprint

Obstacles: anything not y0 floor, any column the city writes above y0 or with a non-paving owner, and both
keep-clear boxes. The existing drum and its bridges count as obstacles but never bind.

| Option | Centre | Radius | Street left round it | What it costs |
| --- | --- | --- | --- | --- |
| Touching nothing | (3584, 3171) | **45** (46.3 to the nearest obstacle) | 1.3 at the south | Stacks doors 1.9 and 2.5 from its wall (`lot_3555_0_3214`, `lot_3619_0_3208`): not usable |
| **A. Largest usable** | **(3584, 3171)** | **40** (81 across, 5,025 columns) | at least 6 (7 to the keep-clear at the north) | all 27 doors still reachable; covers only paving and floor lights; but it stands across the line from the Core to Victory Road's mouth: the walk from the west lift-bank-3 door to the mouth grows from 222 to 256 |
| **B. Boulevard kept** | **(3630, 3137)** | **34** (69 across, 3,625 columns) | at least 5.6 (to `lot_3656_0_3103`'s rail) | all doors reachable; a 16-wide straight way from the apex to the mouth stays open, so the walk to Victory Road is unchanged (222); r39 there would cut off four east Stacks doors |

**Height.** Nothing is overhead: the pit is open to the sky (`data/rift_deep.json` form). The owner's rule
keeps the Compact HQ tower (top y132, `data/deep_city.json:217`) the dominant building, so the crown stays at or
below **y131**; the current design's crown y128 (`data/deep_city.json:187`) fits as it is. The audit ceiling is
y150 (`tools/deep_city_audit.py:62`). The lip is y83, so anything meant to show from the Rift floor must clear
y83. A hemisphere of r40 or r34 only reaches y40 or y34, below ring 1: to read from the lip it needs a drum
under the dome.

## 5. An entrance a player already reaches

1. **On the floor (y0), from Relay Row.** Relay Row (ring 3, y15) to the west lift-bank-3 stair tower, down to
   its door at (3580, 3241), north through the apex: **104 blocks of walk to option B's wall at (3604, 3160)**
   (`g` on the plan); 43 to option A's. A small gatehouse on B's south-west face, facing the boulevard, sits on
   the route players already take to Victory Road (the mouth is a 94-block walk from B's nearest wall).
2. **At street height, from the east Stacks roofs (option B only).** B's east side lies 6-12 blocks from the
   Stacks whose roofs are the ring streets: y66 `lot_3656_0_3103` at 6.4, y32 `lot_3655_0_3174` at 7.0, y15
   `lot_3643_0_3185` at 11.2, y49 `lot_3667_0_3163` at 12.2; the bare ring-0 street (Rimside, y66) at
   (3664, 3103), `b` on the plan, 14.1. The arena's tiers already land on the ring levels (y15/32/49/66), so a
   short bridge from Rimside at y66 makes the arena reachable from the arrival ring without going down at all.
   For option A the same is true only on its south-west, at y15 (`lot_3555_0_3214`, 7.4) and y32 (11.9).

## 6. What contradicts the premise or the documents

- **The relayed extent is off by about 100 blocks.** The owner's screenshot read about z2950-3200. The floor is
  **z3064-3240** (x3496-3681). North of z3064 is the 66 face, ring 0 at y66 and Rimside; north of z3015 is
  outside the pit.
- **It is not empty of buildings.** Its middle is, but 27 Stacks homes ring it and their doors face onto it.
  A footprint inside the radii above displaces none of them.
- **It is not unused.** It is designed as the city's paved square and the way to Victory Road (`DEEP_CITY.md:97`,
  `data/deep_city.json:150-156`). HEAVENS_ARENA.md rejected site B partly because a fight tower would stand
  "on the plaza a player crosses to leave for the Elite Four". This is that plaza. Option B keeps the crossing
  straight; option A puts the arena in its way.
- **Site A's justification is false.** `data/deep_city.json:184` says site A is "the one large footprint the
  city's own lot rule leaves empty". The sheer floor has 18,139 columns outside the lot zone and holds a clear
  disc of r45 against site A's r16. The search excluded it in code (`tools/deep_city.py:947`), not by the lot
  rule. HEAVENS_ARENA.md's site C ("the north face, in the Stacks", lines 133-147) was costed as a tower
  against the face, displacing 4 to 27 Stacks homes. The owner's spot is the open middle, which displaces
  none, so that cost does not apply to it.
- **Not verified:** walkability is a 2D check (nothing solid at y1-2), not a game walk; the ring-0 walk of
  about 435 ignores the blocks above y66 along the route.

## Plan, 4 blocks to a character, north up

`O` option B (r34), `+` option A's wall (r40), `P` mouth plaza keep-clear, `M` Victory Road's mouth, `.` free
sheer floor (y0), `:` free Core floor (y0), `A` the current arena drum, `=` its y15 bridges, `L` lift-bank
stair towers, `#` built, `D` a building door, `0`-`3` ring treads (y66/49/32/15), `g` ground entrance,
`b` the ring-0 bridgehead. Column labels: x hundreds, then tens.

```
        4    5    5    5    5    5    6    6    6    6    6    7
        8    0    2    4    6    8    0    2    4    6    8    0
 3040       ####0000#D####D#00000##0000000000#D###
 3044      #####000000###00000000000#0000000#0#####
 3048      ###D0#0#0#0000000000#000000000#00#0######
 3052     #####00000000#00##00#00000000####00000#D##
 3056     #####000000#000000000000#000######00##0####
 3060     ###D00#0####0000000#00000##########00000####
 3064    #####0000##PPPPPPPMMPPPPPPP#####.####0000#D###
 3068    #####0000##PPPPPPPPPPPPPPPP###.D..D###0000#####
 3072    ####0#000##PPPPPPPPPPPPPPPP#D......####0000#####
 3076   ####D0#00###PPPPPPPPPPPPPPPP..........D##00#0#D###
 3080   #####0000###PPPPPPPPPPPPPPPP...........##00000####
 3084  ######000####PPPPPPPPPPPPPPPP............##0#000####
 3088  #####0000####PPPPPPPPPPPPPPPP............###00#00#D##
 3092 #####0000####DPPPPPPPPPPPPPPPP.............D##00000####
 3096 ####D0000###..PPPPPPPPPPPPPPPP..............###0000#####
 3100 #####000###D..PPPPPPPPPPPPPPPP...............###b#0#####
 3104 ###0000####...PPPPPPPPPPPPPPPP......OOOOOOO..D###0000D###
 3108 ##D00000##....PPPPPPPPPPPPPPPP....OOOOOOOOOOO..##000#0####
 3112 ##00000####...PPPPPPPPPPPPPPPP...OOOOOOOOOOOOO..##0000#####
 3116 ##00##0###D...PPPPPPPPPPPPPPPP..OOOOOOOOOOOOOOO.D##0000#D###
 3120 ##00000####...PPPPPPPPPPPPPPPP..OOOOOOOOOOOOOOO..####0#0####
 3124 #D0000####.....................OOOOOOOOOOOOOOOOO..###0000###
 3128 #0##00####................++++.OOOOOOOOOOOOOOOOO..D###0#000D
 3132 #0000####D.............+++....+OOOOOOOOOOOOOOOOO...####0#000
 3136 #0000####.............+........OOOOOOOOOOOOOOOOO....###000##
 3140 ##000###............++.........OOOOOOOOOOOOOOOOO....####0000
 3144 0#00####............+..........OOOOOOOOOOOOOOOOO...D####0000
 3148 0000####D..........+............OOOOOOOOOOOOOOO....######000
 3152 0000####..........++............OOOOOOOOOOOOOOO...####D###00
 3156 000#####..........+..............OOOOOOOOOOOOO..D###########
 3160 00#####...........+..............gOOOOOOOOOOO...###111#1####
 3164 000###D...........+................OOOOOOOOO..######11111D##
 3168 00####............+..................OOOOO...#######11111###
 3172 #0####............+..................+......#D###D###1111###
 3176 0#####D...........+..................+.....#####2####11111D#
 3180 00#######.........+..................+....D###222#D###1##1##
 3184 00#######D#.......+..................+...####22222####11111#
 3188 0####1######.......+................+...######2222#####111##
 3192 0####111#####D.....+................+..D######22222#####1111
 3196 0###D1111######.....+..............+..###3D####2222#D###1111
 3200 #####1111########D...++..........++..###33#####22222#####11#
 3204 #####1111###########..++........++.D###3333#D###222#####1111
 3208 ####111#1###222######D..++++++++...####33333####2222#####11#
 3212 ####11111##D222#2######.............###33#33####22#2#D###111
 3216 ###D1#111###222222#######...........###33333####2#222####111
 3220 ####1#111###22222########D.........:###33333D###22222#####11
 3224 ####11111###2#2222###33####.......::D###33333#33LL22#22###11
 3228 ###1#11####D22#22###D#333###.#...:::####333333###222222D##11
 3232 ##D##111####2222#####33333####D.:AAA:####3#333####22222####1
 3236 ###1#111#####222LL##D333#LL###.AAAAAA:###33333D####222#####1
 3240 ###1#1#1####D222LL####333LL::::AAAAAAA####333#3####2222#####
 3244 ##D11111####22#22####33333::::AAAAAAAAD##:33333####22#2#D###
 3248 ###11111####22222###D33333====AAAAAAAA==D==3333#####2222####
 3252 ###1#11#####2222#####3333###::AAAAAAAA:#####333#D###2222####
 3256 ###1111######222#####3333###D::AAAAAAA:####3333#####22222D##
```

Each character samples its cell's centre column, except doors and the marked points, which show if any column
of the cell has one. `b` sits on a ring-0 street column between Stacks roofs at the same height, y66.
