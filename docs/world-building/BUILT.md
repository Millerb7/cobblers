# Built in the world: cavern, groves, big trees, town prep (2026-09-16)

Everything here was run on the exported creek world (heightmap `fd0db59b…`) with commands, and checked over RCON or
by reading the region files. Nothing above ground level was built in either gym town, and no town was composed: the
Displaced City and the tree town are left for Axiom.

## Order

| Step | Result |
| --- | --- |
| Creek export | 2,255 s, `seed_match: true`, 484 region files |
| WorldEdit 7.3.8 | loads: "WorldEdit for Fabric (version 7.3.8+6939-7d32b45) is loaded"; Lithium enables its own WorldEdit compatibility mixin |
| Hometown | re-placed from the fixed templates: 0 gaps in 36 corners and 1,670 columns; one waystone, the donor's mossy one gone |
| Cavern | rebuilt: deeper floor, a roof that follows the rock, no false sky, light from the ground |
| Groves | 12 trees at Foothill Woods in three sizes, and 48 elders across 20 forested sub-regions |
| Town prep | Brock's and Misty's streets, plazas and the gym lot |

## The cavern, as rebuilt

The first cut read as a lit lid over a rice-paddy floor. What changed and why is in `tools/cavern_plan.py`; the
numbers are below. **200 × 200 at x3250–3449, z1650–1849.**

| | First cut | Now |
| --- | --- | --- |
| Floor | y33–53, median 38 | **y22–52, median 27** |
| Ceiling | flat y72 everywhere | **y72–110, median 79** — the rock itself, `surface − 24`, smoothed |
| Headroom | min 17, median 32 | **min 25, median 49, max 85** (north-east quadrant: median 65) |
| Excavated | 1,225,002 | **1,940,550** |
| Light | 800 invisible light blocks in the ceiling lattice, sea lanterns behind glass | **437 chain links, 87 lanterns, no roof light at all** |
| Tunnel | 339 blocks at grade 0.292 — over its own 0.25 limit | **404 blocks at 0.245**, and the generator now refuses to emit an illegal grade |

**Why the floor can go to y21 and no deeper.** Lava, not bedrock: 4,203 lava cells in 2,923 of the 40,000 columns,
from y15 down. A floor bottoming at y21 leaves 6 blocks of rock over the highest of them, so no lava seal pass is
needed. Below y16 one would be.

**Why the ceiling is not flat.** The legal cap is the ground minus 24 blocks of rock. That is y72 only under the
creek in the south-west; the median is y79 and it reaches y107 in the north-east. The first cut took the single
lowest legal value and applied it to all 40,000 columns, which is why it read as a lid.

**Why there is no light in the roof.** A lantern is light 15 falling 1 a block, so it dies 16 blocks up. With
minimum headroom 25 there is nothing up there to see unless something up there is lit. Nothing is.

**The wild floor is dark on purpose.** Measured: **79% of sampled floor cells are at block light 0.** Hostiles
spawn at exactly 0, so the dark margins are an encounter area and the lit ground is the safe ground. The city's own
lanterns come with the city.

### Verified, every column, from the region files

| Check | Measured |
| --- | --- |
| Floor block solid | **40,000 / 40,000** |
| Air above the floor | 39,922 / 40,000 — the other 78 are tree trunks, chains and lanterns |
| Air under the roof | **40,000 / 40,000** |
| Roof 4 blocks solid | **40,000 / 40,000** |
| Fluid inside the chamber | **0** |
| Lava remaining | 184 cells, all at y14–15, under the floor where it belongs |
| Sea lanterns, glass, light blocks left from the first cut | **0** |
| Tunnel clear height | min 4, median 5; **0 of 68 stations under 3** |
| Tunnel light | **0 of 146 air cells at block light 0** |

### Four defects found during the rebuild

- **The roof had 511 holes.** Natural rock has voids in it, and 511 of 40,000 columns had a non-solid block exactly
  at the ceiling line, between y76 and y110 — skylights and mob routes, and a leak under the north-east aquifer.
  `15_cap` now lays 4 blocks of stone over every column whatever is there.
- **The seal filled the creek.** Widening the seal to cover the taller chamber took it to y120, above the ground
  (the surface here runs y96–135), and `fill stone replace water` does not know a buried pocket from a river: it
  turned **900 columns of the Glacial Tear into stone at y98–100**. The seal top is now per column,
  `min(ceiling + 10, ground − 4)`, which under the creek is y82. Repaired: 1,997 blocks back to water, 0 spill.
  752 of the 900 columns hold water and the other 148 are **ice** over gravel — frozen creek, never water, never
  damaged.
- **Regenerating the plan from a world you have already built in drifts.** The ceiling is read from the live
  ground, so while the creek was filled the ceiling sat up to 3 blocks high. Regenerate only after repairs.
- **The tunnel lanterns failed twice.** On the floor at y+1 they landed where the rubble step goes (35 of 51
  stations dark); hung from the roof they had no roof along the 76-block open cut (23 of 102 dark, all in the cut).
  They are now posts — a wall at y+1 and a lantern at y+2, placed unconditionally, because stations are 1 block
  apart and a neighbour's step occupies the cell about 2 times in 10.

**A measurement trap worth remembering.** Three separate "failures" were the check, not the build: `execute … run
say` returns nothing over RCON (use the bare predicate, which answers "Test passed"), counting palette entries per
chunk section counts blocks outside your box, and sampling a tunnel at its station centres puts a fifth of the
samples inside rock, where light 0 is correct.

## The trees

### Foothill Woods: three sizes, and the world tree

| Tier | Count | Height | Crown radius | Trunk | Limb storeys |
| --- | ---: | ---: | ---: | --- | --- |
| giant (already standing) | 7 | 45 | 14 | 5x5 | 1, at +16 |
| elder | 4 | 81 | 19 | 7x7 | 2, at +20 and +38 |
| **world tree** | 1 | **418** | **78** | **35x35** | **8, at +56 to +322** |

An elder is a world tree's sapling and takes the species of the wood it lands in, which is why there are seven
species of them. There is one grown world tree and nothing else on the map is its scale.

**The world tree stands at (2016, 2280)**, ground y116, trunk to y457 and crown **y457-535**. The giants' crowns
top out at y162, so its canopy is a second sky over them rather than anything they touch. Two numbers are not free
choices: the first limb storey is at +56 to clear every giant crown below it, and the roots reach 26 rather than
the 60 the tree could carry, because the nearest giant trunk is 34.7 blocks away.

**It needs the raised build limit.** `modpack/datapacks/cobblers_height` takes the overworld to **y-64..y575**
(`height: 640`, `min_y` unchanged). Values came from the server jar's own datagen, not from memory. Verified live
after the restart: y575 accepts a block, y576 is "out of this world", y-65 still is.

**It is built from fill commands, not a template.** At 1,264,724 blocks it is far too large for one
`place template`, so `fill_runs` emits it as run-length fills split across 4 functions (118,234 commands), the same
mechanism that moved 1.94M blocks into the cavern. The split is needed because `maxCommandChainLength` is 65536.

**The old 119-block tree was removed exactly, not box-filled.** A bounding-box clear would have taken the crowns
of the giants 35 blocks away. The tree is seeded from sha256 of its name, so rebuilding it with the geometry it was
generated from reproduces its block set exactly; those 55,860 positions and only those were cleared, in 11,792
commands, 0 failures.

**Verified after the build:** trunk continuous from y116 to y455, canopy present to y534, air above, trunk 35 wide
at the base and no trunk at 19 out, canopy reaching 70 blocks from the centre, and every one of the 7 giants and
4 elders still standing at its true trunk centre.

### 48 elders over 20 forested sub-regions

2–4 a region, scaled by area, on flat dry ground at least 220 blocks apart, off the routed legs but within sight of
them. Species follow what each foliage type actually plants: spruce, birch, oak, dark oak, mangrove, cherry, jungle.
Minimum spacing achieved **348 blocks**, maximum pad relief 2.0. The `near-leg` rule was dropped for 9 regions —
the offshore islands and the jungle, where no critical leg comes within 1,100 blocks.

**Verified in world:** 48 of 48 placed, **384 checks, 0 failures** (trunk base, trunk at +40, crown at +72, ground
solid, nothing floating).

Sites and reasons: `derived/sites/elder_trees.json`. Closest elder to the Foothill Woods grove is 309 blocks.

### Two bugs fixed in `tools/tree_grove.py`

- **The forceload box was wrong for three of the four rotations.** `min(px, px + sx)` assumes a template never
  extends in the negative direction, but `place template` rotates about the placement position, so for 180 and the
  two 90s it does. The box covered a corner of the tree instead of the tree — the exact "That position is not
  loaded" failure forceloading exists to prevent. `footprint()` now takes all four rotated corners.
- **Rotations were seeded with `abs(hash(id))`.** Python randomises string hashing per process, so a re-run emitted
  different rotations from the ones recorded. Seeded from sha256 now; two runs are byte-identical.
- **`(x, z)` means the trunk's min corner in a giant's record**, and the augment pass measured pad relief and
  seating height there rather than at the centre — 6 blocks off for a 13-wide trunk. In world this cost 5 air cells
  in the skirt of one elder at (2073, 2265), repaired to grass. The tool now sites and seats on trunk centres and
  lays its own skirt.

## Town prep

Ground level and below only, and measured: **0 solid blocks 2 above any street surface** in either town.

| | Brock | Misty |
| --- | --- | --- |
| Streets and plaza paved | 56 of 59 sampled points | 44 of 45 |
| The exceptions | 2 where streets meet the stone-brick plaza; 1 lane point paved a block lower than its profile | 1 point paved a block lower, same reason |
| Gym lot | flattened to y141: grass at 56 of 56 points, clear above all | not levelled: the waterfront lot is left as it lies |

**A trap worth remembering:** `forceload add` refuses a box over 256 chunks and the failure is only in its reply.
Brock's 250 × 250 box is 272 chunks, so every fill in the first two runs silently did nothing.

## What is not done

- **Axiom in game** has not been used yet.
- **The towns themselves** are unbuilt, by design — including the Displaced City in the cavern.
- **The cherry growth test is gone.** Re-excavating removed the 13 saplings. It no longer gates anything: the
  cavern's trees are placed as templates, not grown, and their leaves are `persistent`. Cherry saplings need light
  9 to grow, so any sapling planted on the dark floor will not — by design.
