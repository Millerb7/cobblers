# Stone faces: the survey and the redesign (proposal, 2026-09-28)

Flight finding 1 (the owner, 2026-09-28, at the tea town): the faces read as square pits beside the Centre and Mart,
and nothing shows where the ore ends. The owner's brief: check the other six places first; move faces away from
plazas and main streets ("found, not walked past"); shape them to their ground (into real slopes where there are
slopes, irregular and natural where there are not), dropping the fixed box; give each a distinct bottom.

**Built on staging 2026-09-28** (the owner: "do it"; `tools/mines.py`, `data/mines.json`): the old boxes cleared and all 22 formations built on `cobblers-dryrun11`, 501 of 505 sampled cells matching the model over RCON (the 4 others are the Displaced City's lanterns, which the build places in cells the check sampled as air), every face's variant-0 ore in place, 0 of 440 old ore cells left. The audit `tools/mines_audit.py` is rewritten for formations and clean; it catches a planted missing bottom, a planted pit and a missing restore line. `tests/test_mines_independent.py` still describes the box and fails until it is rewritten. Not yet seen in game.

**Re-sited 2026-09-29 (section 6 below).** The formations' shape and bottom course stand; the 18 surface faces moved from 121-205 blocks out to 30-64 (the Scar 110-119), still 26+ from every plaza and 28+ from every street. The audit is clean and `tests/test_mines_independent.py` is rewritten for the formation, its skip marker deleted (80 tests, 0 skipped). **Nothing has been rebuilt on staging since**, so the 2026-09-28 formations still stand there at the old coordinates.

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

**The owner's answer (2026-09-28):** "doesnt have to be same for all, should be a mix, maybe some can be just near town and a person talks to players about it." So each place gets one of three: on the square, in a house slot, or near town with a townsperson who tells players where it is. A starting mix for the next session to put to the owner (nothing decided): the Mining Town on its square beside the Assayer (the finding's own example: it must read as the town's); the gorge hamlet on its square (no lots); Northlight on its big square; the tea town in a house slot among the tea houses; the Scar in a ruined house's lot (32 ruins, one gives way); Viltri Light near town with the lighthouse keeper pointing to it; the Displaced City unchanged (its bays are already in the city). The townsperson's words are story, so Codex writes them (`docs/HANDOVER_CODEX.md`); the NPC is a dialogue in `data/dialogue.json` compiled by `tools/compile_dialogue.py`, placed like the Digger.

---

## 6. Built 2026-09-29: re-sited into the towns, off the plazas

The owner's order for this session: **away from plazas, shaped to their ground, distinct bottoms**; where the mix of
section 5 conflicts with "away from plazas", prefer away from the plaza and record the alternative.

### 6.1 The survey, re-measured on the formations as they stood

Measured on the canonical heightmap and the town plans (`tools/ground.py`, `derived/towns/*_plan.json`), never a world.
"Pit" is how far the natural ground round the working apron stands over the floor a player walks on; "plaza",
"street" and "building" are the least distance from any written column of the face.

| Place | Centre | Plaza | Street | Building | Pit | Verdict |
|---|---|---|---|---|---|---|
| Viltri Light | 130-140 | 118-124 | 123-129 | - | 1 | too far out |
| Tea town | 121-148 | 131-159 | 30-49 | 33-53 | 1 | too far out |
| The Scar | 149 | 120-121 | 35-55 | 33-44 | 0 | too far out |
| Displaced City | 328-446 (the surface centre) | 82-97 | 28-49 | 17-35 | 1 | **already in the city: keep** |
| Northlight | 126-137 | 97-105 | 34-54 | 26-45 | 1 | too far out |
| Gorge hamlet | 55-77 | 35-59 | 48-72 | 21-44 | 1 | the one that already read right |
| Mining Town | 176-205 | 140-170 | 69-100 | 77-108 | 2 | worst: the owner's own example |

So **problems 1 and 3 of flight finding 1 are gone at all seven places**: no face is a pit (0-2, was 4-6), and every
face has a distinct bottom course that is neither its host nor its floor nor its ore. **Problem 2 has inverted**: the
50-150 ring of section 3, plus a search that scored the rock it would have to build, put five of the six surface
places 121-205 blocks out, which is flight finding 2 exactly.

### 6.2 What was changed

- Each surface site's **`ring` is now the nearest band round its town's centre in which a whole formation still
  clears every street, the plaza and every routed leg by `keep_clear.road_clear` (25)**. The inner edge was measured
  per place by probing every anchor and front on a 2-block grid in order of distance from the centre:

  | Place | Nearest legal anchor | Ring set | Why |
  |---|---|---|---|
  | Viltri Light | 36 | 36-90 | the nearest the rule allows |
  | Tea town | 17 | **30**-85 | held back from 17 on purpose: at 17 a formation stands behind the Centre, which is what finding 1 complained of |
  | The Scar | 109 | 105-150 | its own 301-block ruin field, 32 lots and their streets allow no nearer |
  | Northlight | 50 | 50-95 | the nearest the rule allows |
  | Gorge hamlet | 44 | 44-100 | the nearest the rule allows |
  | Mining Town | 36 | 36-95 | the nearest the rule allows |

- **`siting.centre_pull` (6 per block)** is added to the search's score, so of two legal sites the nearer to the town
  wins even when it costs more rock to build. Without it the search takes the cheapest rock, which is always the
  outside of the ring.
- The **readings** were rewritten: they described the old far-out sites.
- The **shape and the bottom course are untouched** (section 2 stands), and the **Displaced City's four are
  untouched**: they are already bays in the cavern wall, 17-35 from the city's buildings.

### 6.3 Where they stand now

| Place | Centre | Plaza | Street | Building | Pit | The reading it now has |
|---|---|---|---|---|---|---|
| Viltri Light | 44-49 | 28-34 | 33-35 | - | 1 | near town, the keeper points the way |
| Tea town | 30-42 | 35-59 | 35-80 | 5-24 | 1 | tors among the tea rows at the town's edge |
| The Scar | 110-119 | 86-92 | 28 | 20-26 | 0 | humps among the ruins, off their streets |
| Displaced City | (unchanged) | 82-97 | 28-49 | 17-35 | 1 | bays in the cavern wall |
| Northlight | 51-64 | 28-35 | 39-40 | 23-26 | 0 | outcrops past the station's last hut |
| Gorge hamlet | 46-59 | 26-34 | 47-65 | 12-29 | 1 | tors over the hamlet's fields |
| Mining Town | 39-55 | 37-56 | 30-48 | 20-38 | 1 | the town's own working behind the pithead |

### 6.4 The deviation from section 5's mix, and the alternative

**The square and the house slot were not built, at any place.** A square *is* the plaza, and every lot touches a
street: either would put written columns inside the 25 blocks the owner set in finding 1. Tonight's order settles it
in favour of the clearance, and this is the record of what was given up.

The alternative, if the owner would rather have a piece on the square than the clearance: drop `road_clear` for
streets alone (keeping 25 for the plaza), which means splitting `keep_clear.road_clear` into a plaza clearance and a
street clearance, and lowering `ROAD_CLEAR_MIN` in `tools/mines_audit.py` — that floor is the audit's, and the audit
is not the builder's to loosen, so it is the owner's call and a separate change.

The mix that *does* survive the clearance, and is what stands:

| Place | Siting built | Section 5 wanted |
|---|---|---|
| Mining Town | its own ground behind the pithead, 39-55 out, in sight of the Assayer | the square |
| Gorge hamlet | over the hamlet's fields, 46-59 out | the square |
| Northlight | inland past the last hut, 51-64 out | the square |
| Tea town | among the tea rows at the town's edge, 30-42 out, 5 from the nearest tea house | a house slot |
| The Scar | among the ruins, off their streets, 110-119 out | a ruined lot |
| Viltri Light | 44-49 out, with a townsperson to point the way | near town, a townsperson |
| Displaced City | unchanged | unchanged |

**Still owed, and not written here:** the townsperson at Viltri Light. The words are story, so Codex writes them
(`docs/HANDOVER_CODEX.md`); the NPC is a dialogue in `data/dialogue.json` compiled by `tools/compile_dialogue.py`,
placed like the Digger.

### 6.5 What was verified, and what was not

- `python tools/mines.py build`: 0 model problems, 7 sites, 22 faces.
- `python tools/mines_audit.py`: **CLEAN**, 7 sites, 22 faces, 13,966 cells written by the build functions, 10 stones
  on sale. Proved to be checking rather than passing: with three faults planted in `data/mines.json` (a bottom course
  equal to its host, `road_clear` 10, a ring of 400-500) it reported 7 problems naming each; the data was restored and
  it went clean again.
- `python -m pytest tests/test_mines_independent.py`: **80 passed, 0 skipped**, module skip marker deleted.
- **Not verified:** anything in a running game. Nothing here has been seen in Minecraft. The formations have not been
  built on staging since the re-siting, so the old ones still stand there at the old coordinates and must be cleared
  from the heightmap before the new ones go in, as on 2026-09-28.
- **A disagreement to settle, not papered over:** `docs/mechanics/STONE_ECONOMY.md` section 14 ("What was built,
  2026-09-28") still describes the 9 x 5 x 6 box, the 3-row apron and ramp, and the pre-redesign coordinates. It was
  already stale after the formation rebuild and is staler now. It is not this session's file to rewrite.
