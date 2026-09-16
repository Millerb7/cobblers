# Built in the world: cavern, grove, town prep (2026-09-16)

Everything here was run on the exported creek world (heightmap `fd0db59b…`) with commands, and checked over RCON.
Nothing above ground level was built in either gym town, and no town was composed: the Displaced City and the tree
town are left for Axiom.

## Order

| Step | Result |
| --- | --- |
| Creek export | 2,255 s, `seed_match: true`, 484 region files |
| WorldEdit 7.3.8 | downloaded (6,222,854 bytes, sha512 `e039492d…`), loads: "WorldEdit for Fabric (version 7.3.8+6939-7d32b45) is loaded", commands registered, Lithium enables its own WorldEdit compatibility mixin |
| Hometown | re-placed from the fixed templates: 0 gaps in 36 corners and 1,670 columns; the placed waystone is there and the donor's mossy one is not |
| Cavern | seal, excavate, surfaces, light, trees, tunnel, biome |
| Grove | 7 giants at Foothill Woods |
| Town prep | Brock's and Misty's streets, plazas and the gym lot |

## The cavern

**What it is now:** a 200 × 200 chamber under the Glacial Tear at x3250–3449, z1650–1849, floor y33–53, ceiling
y72, headroom 17 to 45 blocks.

| Check | Measured |
| --- | --- |
| Shell | 46 of 48 sampled points: floor grass, air above it, air under the ceiling, glass, lantern. The other 2 are natural dirt and gravel above the ceiling instead of stone, still solid |
| Rock over the ceiling | at least 24 blocks everywhere, from the world's own ground |
| Water | 0 of 256 sampled cells in the band; the seal pass replaced the pockets with stone |
| Light for growth | **every one of 4,474 open floor cells** reads 9 or more one block above a sapling |
| Light against spawning | **every one of those cells** has block light 1 or more at spawn height |
| Trees | 40 of 40 placed |
| Biome | cherry grove at 70 of 70 sampled points |
| Tunnel | 68 of 68 stations: solid floor, 5 blocks of clear height, no water. Lit: 0 of 57 sampled stations at block light 0, measured at the floor |

**The light lattice needed repair.** The planned diamond lattice (800 blocks, 10 apart at floor+3) left 218 of
4,489 sampled cells under light 9, because the floor is graded and crowns absorb light. Two repair passes added
lights over the dark cells; the 15 cells that still read dark are inside tree trunks, where nothing grows or spawns.
**The generator still writes the plain lattice**, so a rebuild needs the same repair: measure, then fill in.

**A bug found and fixed in the tunnel.** Each station laid its floor and the next station's air carved it away, so
the floor had holes at every step and one station had water seeping in. The function now seals the corridor, carves
every station, then lays floors and stairs.

## The grove

Seven oak giants at Foothill Woods, 29–48 blocks apart, on ground within 0.4 blocks of level.
- **Each has:** 40–53 trunk and root blocks at ground level, a limb storey 18 blocks up, and a crown.
- **Nothing floats:** 0 of 344 trunk and root columns have air beneath them.
- **Trees only:** no platforms, bridges or buildings.

**A bug found and fixed:** the placement function force-loaded a single chunk per tree, but a giant is 30 × 29
blocks, so `place template` refused with "That position is not loaded". It now force-loads the whole footprint.

## Town prep

Ground level and below only, and measured: **0 solid blocks 2 above any street surface** in either town.

| | Brock | Misty |
| --- | --- | --- |
| Streets and plaza paved | 56 of 59 sampled points | 44 of 45 |
| The exceptions | 2 are where streets meet the plaza, which is paved in stone bricks; 1 lane point is paved a block lower than its sampled profile | 1 point paved a block lower, same reason |
| Gym lot | flattened to y141: grass at 56 of 56 sampled points, clear above all of them | not levelled: the waterfront lot is left as it lies |

**A trap worth remembering:** `forceload add` refuses a box over 256 chunks, and the failure is only in its reply.
Brock's 250 × 250 box is 272 chunks, so every fill in the first two runs silently did nothing. The box has to be
split, and the chunks need time to load before the commands run.

## The growth test, in the cavern itself

**The earlier test chamber is gone.** It was built in the world the creek export replaced, so the export wiped it.
The test now lives in the cavern, under the real lattice and the real cherry-grove biome.

| Sapling | At | Light above it |
| --- | --- | ---: |
| dim (light 9) | (3255, 34, 1690) | 9 |
| dim (light 9) | (3255, 34, 1830) | 9 |
| dim (light 9) | (3262, 36, 1753) | 9 |
| dim (light 9) | (3290, 35, 1655) | 9 |
| dim (light 9) | (3297, 41, 1711) | 9 |
| dim (light 9) | (3297, 40, 1802) | 9 |
| dim (light 9) | (3318, 51, 1753) | 9 |
| dim (light 9) | (3339, 41, 1676) | 9 |
| bright | (3255, 35, 1655) | 14 |
| bright | (3255, 35, 1704) | 13 |
| bright | (3255, 36, 1753) | 12 |
| bright | (3255, 35, 1802) | 11 |
| control, sealed dark niche | (3244, 41, 1840) | 0 |

- **The eight at light 9** sit exactly on the growth threshold: those are the test.
- **The four brighter ones** show the normal case.
- **The control** is a sealed niche cut into the rock west of the cavern wall, at light 0. It should never grow.
- **What finishes it:** a player within range for about 20 minutes, since random ticks need one.

## What is not done
- **Axiom in game** has not been used yet.
- **The towns themselves** are unbuilt, by design.
