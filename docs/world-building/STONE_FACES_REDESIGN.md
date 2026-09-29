# Stone faces: the survey and the redesign (proposal, 2026-09-28)

Flight finding 1 (the owner, 2026-09-28, at the tea town): the faces read as square pits beside the Centre and Mart,
and nothing shows where the ore ends. The owner's brief: check the other six places first; move faces away from
plazas and main streets ("found, not walked past"); shape them to their ground (into real slopes where there are
slopes, irregular and natural where there are not), dropping the fixed box; give each a distinct bottom.

**Built on staging 2026-09-28** (the owner: "do it"; `tools/mines.py`, `data/mines.json`): the old boxes cleared and all 22 formations built on `cobblers-dryrun11`, 501 of 505 sampled cells matching the model over RCON (the 4 others are the Displaced City's lanterns, which the build places in cells the check sampled as air), every face's variant-0 ore in place, 0 of 440 old ore cells left. The audit `tools/mines_audit.py` is rewritten for formations and clean; it catches a planted missing bottom, a planted pit and a missing restore line. `tests/test_mines_independent.py` still describes the box and fails until it is rewritten. Not yet seen in game.

## 1. The survey (all 22 faces, all seven places)

Measured on the canonical heightmap and the town plans by `tools/mines.py`'s own model (0 model problems), never a
world. Distances are from the face's written columns; "climb" is how far the cut's floor rises to meet the ground
around it (0 means the face is entered at ground level; 4 or more is a pit); "rise" is the natural ground's rise
from where the player stands to the back of the box.

| Place | Faces | From plaza | From street | Nearest building | Climb (pit depth) | Natural rise | Slope |
|---|---|---|---|---|---|---|---|
| Viltri Light (water) | 2 | 4-7 | 8-11 | - | 4 | 4 | 16-18 deg |
| Tea town (leaf, shiny) | 4 | 14-37 | 25-62 | 8-18 | 5-6 | 0-1 | 1-5 deg |
| The Scar (sun) | 2 | 4-12 | **2**-13 | 13-16 | 6 | 0 | 0 deg (the pad) |
| Northlight (ice) | 2 | 19-34 | 21-22 | 7-11 | 5 | 1 | 2 deg |
| Gorge hamlet (dusk, dawn) | 4 | 27-51 | 42-66 | 12-36 | 5 | 1 | 2 deg |
| Mining Town (fire, thunder) | 4 | 103-145 | **3**-22 | 18-38 | 5 | 1-2 | 4-7 deg |
| Displaced City (moon, thunder) | 4 | 82-98 | 28-49 | 17-35 | **0** | 74-79 (the cavern wall) | - |

**Problem 1, too easy to find: six of seven places.** Viltri Light and the Scar are worst (4 blocks from the plaza,
2 from a street at the Scar). The tea town, Northlight and the gorge hamlet sit 7-18 blocks from a building. The
Mining Town's faces are far from its plaza but 3-22 blocks from its streets. Only the Displaced City's are set back.

**Problem 2, square pits: all six surface places (18 faces).** Every surface face is sunk 4-6 blocks below the
ground round it, with 5-7-block vertical walls on both sides of its apron. The cause is the geometry, not the
search: the box needs every box column's ground at least 2 over its top, so a 5-high face only sits flush where the
ground rises about 7 blocks across the box's 6-block depth (a 50-degree slope). Nothing near these towns is that
steep. The four Displaced City faces are the exception: they cut into the cavern wall at floor level.

**The ground there is.** Rise over 8 blocks, off the town plan, the routed legs (grown by 3), painted water and the
water export's changed columns (grown by 8), in a ring 25-200 blocks from the centre:

| Place | Rise 6+ (a flush face) | Rise 3-5 (a bank) | Steepest 8-block step within 250 |
|---|---|---|---|
| Tea town | none | none | 5 |
| Northlight | none | none | 4 |
| Gorge hamlet | none | 1,734 columns, all 150-200 out | 6 |
| The Scar | none | 2,451 columns, all 150-200 out (the pad's rim) | 18 (off the pad) |
| Viltri Light | 9 columns, 150-200 out | 17,770 columns, from 25 out | 7 |
| Mining Town | 956 columns, 150-200 out (the cone's flank) | 4,363 | 24 |

So the tea town, Northlight and the gorge hamlet have no slope to cut into, the Scar and Viltri Light have banks,
and only the Mining Town has a real hillside, 150-200 blocks from its centre.

**Problem 3, no bottom: all seven places.** Under and behind every box is two blocks of the same host rock
(the "backing"), and the cut's floor is the host's cobbled form (cobblestone on stone, cobbled deepslate on
deepslate; the Scar's floor is terracotta on terracotta). Nothing marks where the ore-bearing volume ends.

## 2. The proposed shape: a formation, not a box

One rule for every face, which becomes a cut where the ground rises and an outcrop where it does not:

1. **The floor is the natural ground in front of the face, never lowered.** A three-row working apron may be levelled
   by one block at most. No face is entered by climbing down.
2. **The face is a working wall about 5 high**, its line irregular (each column set back 0-1 by seeded noise), its
   width 7-11 by noise, its top edge following the ground.
3. **Where the natural ground behind the face rises less than the wall, rock is built up** into a rounded knoll:
   top at the wall height plus noise, falling away from the face with a stepped, broken edge (1 down per 1-2 blocks),
   a few loose boulders at its foot, capped as the place's ground is (grass, moss, snow on Northlight, bare on the
   Scar). On flat ground the whole formation is an outcrop, a tor standing in the meadow with one worked side. On a
   bank it is a cut topped by a knoll. On a real slope it is a plain cut and nothing is built.
4. **The ore body** is the rock 1-4 blocks behind the face line, from the bottom course up to a block under the
   formation's surface: its outline follows the formation, not a box. At least one ore shows on the face at eye
   height (the visible tell); the rest lie hidden 1-3 deep. Yields unchanged.
5. **The distinct bottom.** One course of a contrasting rock under the whole ore body, showing as a band along the
   foot of the face (the ore starts one above it). Dig down to the band and you are done:

   | Host | Bottom course | Places |
   |---|---|---|
   | stone | deepslate (dark under pale, the vanilla transition) | Viltri Light, tea town, Northlight, gorge dawn |
   | deepslate | tuff (pale under dark) | gorge dusk, Mining Town, Displaced City thunder |
   | terracotta | smooth basalt | the Scar |
   | dripstone block | calcite | Displaced City moon |

   None of the four is a spawn condition (`data/spawn_blocks.json`, `data/spawn_block_policy.json`). The back and
   sides could take the same course so the whole seam is bounded; the owner asked only for the bottom.
6. **The restore** refills the whole formation, not a box: every rock cell of the knoll, the body and the bottom
   course, through the same `#cobblers:face_resettable` filter (a chest still survives), with the occupancy guard over
   the formation's bounding box. A player who quarries the knoll away finds it back. More commands per restore than
   one box fill (column runs, roughly 100-200 per face); counted when built.

Every formation is different (seeded per face), and the Displaced City's four become the same rule's "real slope" case
in the cavern wall.

## 3. The proposed siting: found, not walked past

- **A ring 50-150 blocks from the town centre**, outside the town's footprint, instead of inside its reach.
- **At least 25 blocks from any street, the plaza and every routed leg**; the existing keep-clear rules stay (water,
  the water export's reach, trees, dressing, working Pokemon).
- **Preferring rise:** the search scores the built-up volume (less is better), so where a bank or a slope exists
  within the ring the face goes into it.
- Where the fiction points somewhere, the place's `prefer_near` says so, as the Mining Town's does now.

| Place | Proposal |
|---|---|
| Tea town | Two mossy stone outcrops among the tea rows, 50-150 out. No slope exists. |
| Northlight | Two snow-capped outcrops inland on the islet, clear of the water export's reach. No slope exists. |
| Gorge hamlet | Two dark outcrops (dusk) and two pale ones (dawn), 50-150 out; the 3-4 banks at 150-200 are an alternative. The reading says the outflow cut the seam open, but the outflow's banks are water-export ground, so they wait for the export. |
| The Scar | Two terracotta humps left by the scraping, out among the ruins but off its streets, or the pad's rim (banks, 150-200 out). |
| Viltri Light | Two bank faces topped by knolls, 60-150 out, on the 3-5 rises. Within 150 blocks no rise of 6 or more is free of the plan, the legs and the water export's reach (which of them excludes the lighthouse's cliff is not checked). |
| Mining Town | Four plain cuts into the cone's flank, 150-200 out, where the rise is 6 or more: the "thermal working on the cone's flank" the design meant. Outside the 50-150 ring, deliberately. |
| Displaced City | Keep the four sites (already in the cavern wall and set back); reshape to the formation rule and add the bottom course. |

## 4. What building it takes

`tools/mines.py` (the geometry, the search, the restore's fills), `data/mines.json` (the geometry block, the rings,
the bottom blocks, new boxes), and `tools/mines_audit.py` plus `tests/test_mines_independent.py`, which recompute the
box geometry independently and must be rewritten for the formation by someone other than the builder (CLAUDE.md,
content and its review by different agents). Then `reapply.py prepare --only mines:build`, the old faces cleared on
staging, R9O re-run, and a spot check over RCON. The old faces' pits are refilled from the heightmap on staging before
the new ones go in.

## 5. Flight finding 2 (the owner, 2026-09-28): in the town, not out past it

Seen on the rebuilt tea town faces: "i like these better, but some of them arent near towns enough, like mining town someone wouldnt know its connected. make them a piece in town square or in like a house slot." The shape stays; the siting ring of section 3 is replaced. What the plans hold (measured, `tools/town_dressing.py` town_plan):

| Place | Square | Lots (all taken) |
|---|---|---|
| Tea town | 29 x 27 | 15, 13 x 12-13 |
| The Scar | 33 x 33 | 32, 12 x 11 |
| Northlight | 41 x 31 | 14, 13 x 13 |
| Gorge hamlet | 31 x 29 | none |
| Mining Town | 41 x 24 | 14, 13 x 13 |
| Viltri Light | 6 x 13 | none |

A formation is 13-19 by 9-19 today, so a lot takes a smaller one (width 7-9, knoll 1-2 round it) and a square takes one outcrop per place with its faces on different sides (the tea town's leaf north, shiny south), which needs the builder to merge a site's faces into one formation (one cap per column, one restore footprint). Viltri Light fits neither and needs a site by the lighthouse. Decisions for the owner before building: square or lot per place, and which house gives way where it is a lot.
