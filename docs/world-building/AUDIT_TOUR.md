# Audit tour

A walk of every place built on the disposable world, most important first. Stop when you run out of time: the
first block is the twenty minutes that matter. Each stop is a `/tp` and what to look at, and every item on the
review list of 2026-09-21 is at one of these stops (marked **R**).

**Before you start.** Boot the disposable world (`--universe cobblers-runtime-proof --world spawnproof`) under the
coordination lock. `/gamemode spectator` so a `/tp` into a wall or a tree is harmless, and `/time set noon` for the
towns. **A location title should appear** as you arrive at each town and region (they are advancements that fire
about once a second; `/tp` counts as arriving; if none shows in spectator, try one stop in survival). Say if one
does not, or shows the wrong name. Every coordinate is where you stand, a block or two above the ground.

The Scar is **not** on the disposable world, which predates its pad; Surge's town now is, on ground restored from
the heightmap for the light check (the feathered flank round it is still the old terrain). Both are built, and
audited clean, on the staging export `cobblers-dryrun3` (`--universe cobblers-runtime-proof/dryrun3 --world
cobblers-dryrun3`), which also holds every other place as the live re-export will build it: a fresh export with its
natural foliage, not the restored ground of the disposable world. Their stops are at the end.

## The twenty minutes

### 1. The Displaced City, redone (5 min)
The most loaded place in the world, drawn again on the floor the cavern was graded for.

| Stop | `/tp` | Look at |
| --- | --- | --- |
| Tunnel arrival | `/tp @s 3262 30 1660` | The old road leaving the arrival up the ridge's groove. Lanterns ring the arrival. |
| Stair foot | `/tp @s 3346 44 1756` | **R** The road ends at the foot of the crown and an eight-step stair climbs to the square. The alternative was a 9-block cut. |
| Summit square | `/tp @s 3328 48 1757` | **R** The cairn on the true top (y46, flat within one block), the waystone. **No Centre, no Mart**: a decision made without you. Say if the city should have them. |
| Upper street | `/tp @s 3366 40 1800` | The upper bench ring: houses on terraces cut level at their own median, facing out over the dark. Worst cut 5, worst fill 4 anywhere in the town. |
| Lower street | `/tp @s 3373 30 1821` | The lower ring, where most of the 42 houses are. **R** 18 houses repeat a design, and each second copy is re-materialed in cherry or dark oak: is repetition still what you notice? |
| Lit as a town | `/tp @s 3300 40 1740` | **R** 254 lantern posts: along the old road every 10 blocks, the ring streets every 16, the square's corners, and the rest filling the dark slopes. Nothing in the cavern is at block light 0. Does it read as a town that lights itself, or as a lantern field? |
| A field | `/tp @s 3324 48 1766` | **R** One of six 5 x 5 plots on the slopes: carrots, potatoes, beetroots, young and uneven, a few failed cells, two lantern posts, a composter and hay. Small, struggling, tended? |
| From above | `/tp @s 3350 70 1750` | **R** The cavern keeps 17 cherry trees (it had 41) in its margins and the north-west, and 6 light strings. The slopes between the benches are bare, because the town's keep-clear buffer covers them. Too bare? |

### 2. Sunset West, re-sited (4 min)
**R** No bay or inlet exists anywhere on the Sunset isle; its painted shore is smooth all round. The town moved to
the mainland: a river mouth on the strait, across from the isle.

| Stop | `/tp` | Look at |
| --- | --- | --- |
| The square | `/tp @s 2654 67 6494` | Centre and Mart in brick, red and yellow terracotta. |
| South pier head | `/tp @s 2701 67 6639` | Look south across the strait: the isle is where the boats go. Is this a harbour? |
| Footbridge | `/tp @s 2629 72 6448` | The river left as it runs; the bridge, quay and slipway. |

### 3. The League in the Rift (3 min)
| Stop | `/tp` | Look at |
| --- | --- | --- |
| The forecourt | `/tp @s 3576 88 2724` | **R** The League on the Rift's floor at the trunk head, Victory Road's end at the plaza's south edge; its Centre and Mart are the template's own, inside. Red sand is red concrete powder, wool is terracotta. The precinct is spawn-free: stand two minutes and nothing wild should appear. This has never been watched with a player. On `cobblers-dryrun4` the old plateau League, Centre and Mart still stand at (3346, 2603); a fresh export has none. |

### 3a. The Rift overhaul, staging only (10 min)
Built on `cobblers-dryrun4` by `tools/rift_build.py` from `data/rift.json` (2026-09-22); not in the live world. Fly it: `/gamemode spectator`.
| Stop | `/tp` | Look at |
| --- | --- | --- |
| Overview | `/tp @s 3900 300 3300 150 40` | **R** The wall on the rim, 211 spires to y320 (top third purple glass), the floor's crying-obsidian light, the biome's fog and portal particles |
| G2, Victory Road's gate | `/tp @s 3560 113 5291 -90 10` | **R** The rubble either side, the gatehouse, the one-wide roofed walkway, the barrier behind the (placeholder) guard |
| G4, behind the League | `/tp @s 3611 87 2574 180 10` | **R** The cross-wall to the apex and its gatehouse |
| G1, the dig camp | `/tp @s 2946 104 3316 -90 10` | **R** The dig camp's gate at the spur's end |
| G3, the south-east branch | `/tp @s 4609 131 4836 90 10` | **R** The collectors' pocket gate |
| The rim post | `/tp @s 3734 142 3951` | **R** The wall stops either side of the post's town: an unguarded way in (open decision) |

### 4. Giovanni's gym (2 min)
| Stop | `/tp` | Look at |
| --- | --- | --- |
| The square, then the gym on its west | `/tp @s 3605 115 6451` | The torch on the desk is a plain torch, and every gym interior is now spawn-free, so the fossil machine draws nothing. Nothing to decide. |

### 4a. The Route 1 mansion (3 min)
| Stop | `/tp` | Look at |
| --- | --- | --- |
| North of Pallet | `/tp @s 1466 121 5211` | **R** Measured: the chimneys and ridge are on the skyline to the north-east at about 230 blocks (Distant Horizons range). From Route 1's mouth (`/tp @s 1466 122 5100`) the forest hides it at any height: measured, so not a question, unless you want a sightline cut. The junction post (`the old manor / this way`) is at the spur. |
| The front | `/tp @s 1629 117 5050` | The drive round to the south front, the double door. |
| Inside | `/tp @s 1629 116 5041` | Foyer and stair; dining room west (long table, cups), library east (three aisles); the service corridor behind. Upstairs, the hall's five doors and the barred ballroom doors off the landing. |

### 4b. A signpost (1 min)
| Stop | `/tp` | Look at |
| --- | --- | --- |
| Route 1 leaving Pallet | `/tp @s 1466 121 5211` | **R** The first post: `Route 1 / to / Brock's town` on the front, `Pallet` on the back. The towns' names are working names from `data/signposts.json`. |

### 5. The two towers (3 min)
| Stop | `/tp` | Look at |
| --- | --- | --- |
| Northlight observatory | `/tp @s 7183 124 1638` | **R** Now a square station house carrying a copper dome with a glass slit. |
| Viltri Light | `/tp @s 560 74 4518` | **R** Now a round tower tapering in three stages, with a gallery and a lantern room. Do the two read as different buildings? |

### 6. Relic Island (2 min)
| Stop | `/tp` | Look at |
| --- | --- | --- |
| The torn edge | `/tp @s 1114 66 5531` | **R** The house is the same design as Pallet's large house, on purpose. The fence runs towards Pallet and stops at the torn edge; the calcite seam is behind the house. |

## The next half hour: batch 3 and the rest of the review list

| Place | `/tp` | Look at |
| --- | --- | --- |
| Northlight | `/tp @s 7265 118 1555` | **R** The road up the isle's one hollow, snowy houses, the field station (a bca lodge with its pep-up flowers removed, loot cleared). |
| Mining Town | `/tp @s 6620 140 5699` | **R** The shelf town; the portal (`/tp @s 6735 146 5810`) faces into the rising south-east flank, barred. The mine itself is not built. |
| Tea town | `/tp @s 2618 117 3583` | **R** The tea house on the terrace edge; the tea rows (`/tp @s 2690 113 3550`) step down the east slope. Bamboo houses. |
| Jungle ruins | `/tp @s 5160 132 7485` | **R** Six underwater-ruin models set on land and half sunk. The cache its brief names is **not built**: it needs a reward chosen. |
| Sabrina | `/tp @s 6196 97 3398` | **R** Spawn exceptions as approved; the market square, the observatory, the dojo, the department store. |
| Tableland stop | `/tp @s 4843 164 5690` | **R** The watchtower (`/tp @s 4800 175 5672`) without its ominous banners or loot. Does anything still read as hostile? |
| Rift dig camp | `/tp @s 3108 92 3303` | The excavation keeps its suspicious sand; the tents alternate badlands and desert. |
| Erika | `/tp @s 4310 113 1556` | The green. |
| Koga, Blaine | `/tp @s 4668 120 2432`, `/tp @s 6074 110 4995` | **R** The gym exceptions: Koga's pond planting, Blaine's magma floor. |
| Gorge hamlet, Rift rim, Merian hut | `/tp @s 6813 116 4367`, `/tp @s 3759 142 3952`, `/tp @s 2813 110 1035` | Batch 2 as approved. |

## Queued checks that need you in game

- **Right-click a trader** in Brock's town (`/tp @s 1756 141 3620`): a `NoAI` merchant should still open its trades.
- **The ball throw** and **the creek census**, as queued before.

## After the re-export, or on the staging export `cobblers-dryrun3`

| Place | `/tp` | Look at |
| --- | --- | --- |
| Surge's town | `/tp @s 1676 177 1393` | **R** Drawn to the approved plan and never seen: the lip walk, the copper belvedere, the gym cut into the wall (the plan's one deep excavation, up to 38 blocks). Its houses are now the flank's deepslate brick and tuff, not Sabrina's stone. |
| The Scar | `/tp @s 2110 283 950` | Foundations only, one course, on the 32 lots; no lamps. |
