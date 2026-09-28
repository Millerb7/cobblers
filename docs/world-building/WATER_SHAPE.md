# The water's shape: the heightmap revision for the water export (Phase B)

**Status: DESIGN, RUN AND POLISHED 2026-09-27, for the owner's review. Nothing is applied and nothing is exported.**
The canonical heightmap (`0d9b5f1e…`) and everything under the source root are untouched. The design
(`data/water_shape.json`) was applied to a copy by `tools/water_shape.py` and checked by `tools/water_shape_audit.py`:
**181 checks, CLEAN**. Every "after" number below is **[run]**, measured on that copy (`derived/water_shape/report.json`,
`audit.json`); **[plan]** marks values from `docs/mechanics/WATER_BUILD_PLAN.md`. Nothing here has been seen in a world:
the maps are renders of heights, and the in-world water check (section 11) is not written.

This revision carries three things since the first run:

- **the polish** the owner asked for after reviewing the first maps ("nothing may look machine-made": sections 3, 5, 6,
  7 and 14);
- **the Viltri Ravine on hold** (the owner, 2026-09-27, after asking for the gravel path as a river: *"hold ... until I
  decide"*): no stream in either half, the ravine exactly as on the canonical heightmap (section 4);
- **Part B** (the owner, 2026-09-27: *"pacifidlog should be on an island, it should be on the sea, jungle isle should
  be removed and pacifidlog should be around there."*, section 15): the Jungle Isle removed down to a bank, Pacifidlog
  re-sited onto it, the margin's seamounts and the Long Isle's new desert/jungle split.

The plan this carries out is `WATER_BUILD_PLAN.md` Phase B: items 1, 3 and 4's *shape* (rivers and lake terrain, the
shallows, the seabed) as **one** heightmap revision and **one** staging export (decision 5). Materials, plants, coral,
grottos, caves, wrecks and docks are blocks (Phase C) and are not here.

**The revision in one line [run]:** 19,027,615 columns changed (of 67.1 M), 364.6 M blocks moved. The seabed fill is
15,994,530 columns and 295.2 M blocks; the Jungle Isle's removal is 1,611,482 columns and 63.4 M blocks cut. The copy is
`derived/water_shape/land_8k_16_rescaled_b145_pads_rift_water.png`; the margin relief beside it is
`derived/water_shape/margin_relief.png`.

---

## 1. What changes where, in one table

| Family | Where | What the player gets | Serves | Layer |
|---|---|---|---|---|
| **Meanders** | the major river's lower trunk, Viltri's Path over the coastal flats, Arrow Lake's outflow, three low-grade stretches of the Watering Hole outflow | loops of varying length and size, pools on the outside of bends, point bars inside, cut banks | decision 9, owner item 1 | heightmap |
| **Planform smoothing** | the Watering Hole outflow above its steep last reach | a gentle curve through the graded course's kinks, the meanders swinging about it | question 5 (B) | heightmap |
| **Cascades and falls** | the tarn and Peak Pond outflows, the Watering Hole outflow's last 320 blocks, Viltri's Path's last 213 | steps gathered into short cascades with plunge pools, one 2-3 block fall each | decision 9 | heightmap |
| **The Viltri Ravine** | the whole ravine | **ON HOLD**: nothing; the ravine stays dry and exactly as it is | decision 4, held by the owner 2026-09-27 | none |
| **Lake beds** | all nine lakes | a wandering wadeable shelf, a drop-off, a silt floor, irregular sunken islands, kept pits sitting at the bottom of their own slopes | decision 8 | heightmap (zones for paint and skin) |
| **Tidal flats** | off Pallet, Route 1's west coast, the south strand | crescent bar segments and runnels, rips in the gaps, a lagoon on the south strand | owner item 3 | heightmap |
| **The Fungal bar chain** | Pallet coast to Fungal Isle | two lobed sand bars; the longest 3-deep run 26 | decision 7 | heightmap |
| **The Relic reef** | Relic Island's south and west apron | a platform from the islet's own edge, 3 to 12 deep, patch reefs, a reef wall | decision 7 | heightmap (coral is blocks) |
| **Skerries and stacks** | windward cliffs, the north-west coast | low rocks and stacks with a boulder skirt | owner item 3 | heightmap |
| **First Cast's scour hole** | off the jetty's west end | a hole 4 deep under the rod | item 3 (question 3) | heightmap |
| **The seabed** | the four marine zones | OCEAN.md's shelf, break, slope and basin, filled to the profile with the canyons carried through, soft troughs under the ferry straits, two ridges; no exclusion boxes | decision 6 | heightmap |
| **The Jungle Isle's bank** | x4382-5951, z6860-7996 | the island gone: a drowned bank 4-9 deep, Pacifidlog's shallows and its blue hole | Part B | heightmap |
| **The margin relief** | the 1,280-block margin round the heightmap | the five seamounts; the map's edge carried outward (no cliff where land meets the edge) | question 1 (A) | a second export image |

Unchanged on purpose: the Viltri Ravine (on hold), the Tilpey outflow gorge under the Route 7 bridge, the islet, the towns (but Pacifidlog's Sound
footprint and the jungle ruins, section 15), the roads, the Rift and Victory Road.

---

## 2. The rules the revision keeps (the audit checks each)

1. **Shape only (P1).** Everything here is a height; nothing is a block.
2. **Bit-identical outside the declared footprints (P2)**, column by column: B1, 0 stray columns.
3. **Nothing already placed moves (P3).** Never written: every town footprint plus 8 (Relic Island's plus 0, because
   its islet's outline is protected on its own), every route line plus 6, the Rift and every column its sculpt changed,
   Victory Road's band plus 32, the bridges plus 16, **the islet's outline**, the built water event sites, and every cut
   river's painted water. Released by the design (section 15): Pacifidlog's Sound footprint and the jungle ruins'.
4. **Swim-rate invariance (P4).** No sea column 3+ deep became shallower than 3 outside the declared rest-ground coast
   features (D1: 0 columns); the seabed never rises above y59.
5. **Lakes keep their level and shoreline (P5):** E1 and E2 pass on all nine lakes.
6. **Every river drains end to end (P6):** no surface rises downstream; steps over one block only at declared falls; no
   station dried that was wet; no new leak.

---

## 3. Rivers (item 1: "rivers that feel like they flow")

**Sinuosity per meander window [run]** (channel length over the chord; targets unchanged):

| Window | Before | After | Target |
|---|---:|---:|---|
| `major_lower_trunk` | 1.02 | **1.29** | 1.2-1.5 |
| `viltris_path_coastal_flats` | 1.11 | **1.56** | 1.3-1.6 |
| `arrow_outflow` | 1.06 | **1.37** | 1.3-1.6 |
| `watering_hole_outflow_upper` | 1.06 | **1.28** | 1.2-1.5 |
| `watering_hole_outflow_middle` | 1.00 | **1.26** | 1.2-1.5 |
| `watering_hole_outflow_lower` | 1.07 | **1.37** | 1.2-1.5 |

**The Watering Hole outflow between its meanders (question 5, answered (B)).** The graded course above the steep last
reach (0-968) now follows its centreline smoothed with a 36-block Gaussian, the shift held inside the valley's room
(at most 24, measured at most 7.4 [run]) and tapered to nothing at each end and at every tributary mouth; the graded
course's sharpest kink there was 45°. The meander windows swing about the smoothed line; the course's own one-block
steps are kept where they fall. The last 340 blocks (graded 0.026-0.12) stay a straight cascading creek.

The cascade windows are unchanged in design; all six revised courses pass F3-F7 (never rising, big steps only at
falls, no new dry station, ending where they ended, no new leak), and the five unchanged cut courses paint as before.

---

## 4. The Viltri Ravine: ON HOLD (the owner, 2026-09-27)

**Nothing is shaped in the ravine.** The owner first asked for the gravel path (the ravine's dry bed on the lake side of
the pass, seen near (1008, 3789)) as a river (*"water export looks good, make sure to add that gravel path as a
river"*), then held the whole ravine: *"THE VILTRI RAVINE — hold ... stop the subagent working on the two streams until
I decide."* The run's sea-half stream is withdrawn too. The copy leaves every column inside the ravine's landmark polygon
(outside Lake Viltri's basin, which the lake pass owns) exactly as on the canonical heightmap, and the audit checks it
(G1, G2). The owner leans towards keeping it dry and dressing it so it reads as a deliberate, old, stopped watercourse:
block dressing, Phase C, not shape. `data/landmarks.json` `viltri_ravine` stays `water: never`.

**What was designed, for the owner's decision (measured on the copy before the hold; not in the copy now):**

- **The sea half** (the run's decision 4, option B): a spring pool at (870, 3846), y134, and a stream 611 blocks to the
  sea, 70 steps and one 3-block fall, widened from 3 to 4-6.
- **The lake half** (the gravel path): a spring at y133 on the lake side of the pass and a stream 1,084 blocks long, 5-9
  wide, 31 steps and one 2-block fall, with a pond at y133 below the spring (161 blocks, 3 deep) and a lakeside pond at
  y103 where the ravine floor dips to y95, below Lake Viltri's own level (189 blocks, 7 deep); the counter-rises (about
  26 blocks in all) were filled to their lips, the rest of a rise cut (at most 3).
- **Finding:** the lake half cannot reach the lake. The ravine's last 176 blocks toward Lake Viltri are Viltri's Path's
  own channel (`lake_viltri_outflow` leaves the lake at (1490, 3014) and runs west down the ravine to a fork at about
  (1314, 3022)), and Viltri's Path flows out of the lake there; a lake-side stream would join Viltri's Path 90 blocks
  below the outlet, at its level (y102), and reach the sea by it.
- **If water is chosen**, `SQ-G1-01` "Where Viltri Used to Run" and Brock's town's name Stoneford ("a river that no
  longer runs", `SETTLEMENT_NAMES.md`) would need Codex's rewrite; neither is touched here.

`tools/water_shape.py` keeps its stream pass (both halves, the join, the pools and the banks it raises), which runs
nothing while `data/water_shape.json` holds no `viltri_ravine_stream` block.

---

## 5. Lakes (item 1: "lakes that read as lakes, not step-down bowls")

**The polish.** The owner's review: shoals everywhere read as streaks, Tilpey's 46 bars as a drowned drumlin field,
and the kept pits as hard-edged blobs. Now:

- **A shoal is a sunken island**: a warped, lobed outline (two octaves of noise on its radius, a mild elongation at any
  angle), a size drawn from the lake's range with small ones commoner, a crest 1 deep with 2-deep saddles, a sand apron
  to 3 deep and a flank at 0.35-0.8 blocks of depth a block, different for each.
- **Fewer.** Budget shoals are placed where each brings the most over-budget water within reach, none within 40 blocks
  of a kept pit.
- **Decision 8 read literally on the big lakes**: every lake keeps its wadeable shelf, and each **dive site** (Shrew's
  pit, Mesprit's grotto floor, Azelf's pit, Tilpey's practice floor) gets a rest point within the trained budget. The
  open water keeps one to three **natural islands** where the old floor stood broadly highest.
- **Kept pits blend**: round every keep zone the floor eases back to the old bed over 80 blocks, both ways, so a pit
  sits at the bottom of its own slope (Viltri's small lake over 24).
- Protected event-site boxes (Viltri's platforms) and river channels are faded into over 12 blocks, not cut square;
  the floor's noise is broad swells at 64 and a half-block ripple at 20 (one octave at 24 read as speckle).

**Measured [run]:**

| Lake | Rest rule | Wadeable before -> after (target) | Farthest from rest before -> after | Dive site to rest | Shoals (natural) | 9+ deep before -> after | Fill / cut blocks |
|---|---|---|---|---|---|---|---|
| Viltri | whole lake, 60 | 6.9% -> **19.1%** (15-40) | 80 -> **57** | | 3 | 18,913 -> 16,531 | 57,756 / 25,566 |
| Shrew | dive site, 60 | 6.6% -> **10.8%** (10-35) | 162 -> 95 (open water) | pit **20** | 3 (2) | 112,881 -> 119,917 | 286,097 / 669,435 |
| Arrow | dive site, 60 | 4.2% -> **13.4%** (12-35) | 147 -> 95 | grotto **18** | 3 (2) | 82,579 -> 79,070 | 455,405 / 378,252 |
| Marshy Marsh | dive site, 60 | 15.7% -> **24.9%** (20-45) | 124 -> 105 | pit **12** | 2 (1) + 8 root crowns | 54,344 -> 63,860 | 70,137 / 181,164 |
| Tilpey | dive site + north shore band, 60 | 3.6% -> **12.9%** (12-35) | 242 -> 229 (open water); **60** in the north shore band | practice floor **0** | 5 (3) | 869,076 -> 825,590 | 1,633,159 / 1,066,883 |
| Peak Pond | whole lake, 60 | 15.9% -> **20.4%** | 97 -> **56** | | 3 | 15,635 -> 23,747 | 72,204 / 135,814 |
| Watering Hole | whole lake, 60 | 14.2% -> **20.7%** | 65 -> **53** | | 1 | 5,250 -> 8,511 | 8,849 / 25,730 |
| Mt Clay pond | whole lake, unaided **34** | 8.8% -> **20.5%** | 82 -> **34** | | 4 | 15,644 -> 15,490 | 89,497 / 73,256 |
| Ravine Head Tarn | whole lake, 60 | 10.5% -> **14.3%** | 79 -> **59** | | 2 | 12,649 -> 15,815 | 26,683 / 76,475 |

Shoal counts were 1 / 10 / 6 / 5 / 46 / 2 / 1 / 7 / 1 on the first run; now 3 / 3 / 3 / 2 / 5 / 3 / 1 / 4 / 2.

**Tilpey (question 4, answered (C), the main session's recommendation; the owner has seen the maps).** The rest
budget applies to the dive sites and the Dive school's north shore only: the practice floor (now a floor 36 blocks
round, at 25 deep, where the old bed first reaches 25 on the line from Sabrina's town toward the lake's anchor, below
the north shore; the run had flattened 591,398 columns, half the lake) with a rest point beside it, and the north
sector's water within 80 blocks of the shore. The open lake gets three natural islands (sizes 41-56) and is otherwise
open deep water: a trained surface swimmer can be about 230 blocks from rest in the middle; a Dive-trained player does
not tire under water (decision 1), and the Weeping Elder island is Uxie's rest point. Tilpey's fill fell from 7.05 M
blocks to 1.63 M. Its shelf widened from 10-40 to 14-44 (28-52 on the north shore) to keep the wadeable share.

**Mt Clay pond (the unaided Wooper stop).** At 30 blocks from rest it needed 12 shoals; its budget is now 34, the
unaided rung with Slowness counted and no other margin (out and back 68 deep blocks against the first hit at about 70).

**Close for the owner:** Shrew, Arrow and Marshy Marsh now hold only their dive sites to the budget, as Tilpey does.
A trained surface swimmer can be 95-105 blocks from rest in their open water; the first run held the whole lake to 60
with a necklace of 10-13 shoals round each pit.

---

## 6. The shallows (item 3)

| Feature | Measured [run] |
|---|---|
| **Pallet flats** | 14,007 columns; wadeable in the 64-block band 27.8% -> 20.5% (the gaps between bar segments are rips); 57 new dry crests; fill 11,568 / cut 5,136 |
| **Route 1 west coast flats** | 8,434 columns; wadeable 29.5% -> 23.4%; 6 dry crests |
| **South strand flats and lagoon** | 27,334 columns (7,169 held off by protected ground); wadeable 32.4% -> 35.7%; 1,599 new dry columns; the lagoon as before: shore centre (2504, 6496), barrier 3,037 columns, 19,662 of calm water, inlet (2476, 6533) |
| **The Fungal bar chain** | 2 lobed bars; longest 3-deep run 26; the line (985, 5233) -> (812, 5347) |
| **The Relic reef** | 12,258 platform columns, 10,261 written, 116,873 blocks filled, shallowest 3; 385 columns of patch reef |
| **Skerries, stacks, First Cast's hole** | as the run |

**The polish.** Unbroken bars read as contour streaks: a bar is now a string of crescent segments (a second, shorter
wander bends each seaward and back) and the gaps are the rips, a block deeper than the runnel, soft-edged on every side.
Bars ease into the old bed over about 48 blocks (wandering) toward a box edge, an exclusion or protected ground (12 read
as the box's straight edge). **The Pallet sickle is gone:** the reef platform started at a fixed radius 34 from Relic's
centre and read as a sickle cut against the deep basin, its knolls (three- and five-lobed discs) as crosses. The platform
now runs from the islet's own outline (its apron stands at sea - 4, so they meet with no moat; the islet's protection is
its outline, margin 0), shoals from 3 to 12 deep over 30-62 blocks, falls to the floor down a wall 5-13 wide, and fades
out over 40° past each end of its sector; patch reefs stand where two octaves of noise are highest. The coast maps now
draw the islet over its seabed.

---

## 7. The seabed (decision 6) and the margin (question 1)

**Measured [run]:** 15,994,530 columns filled, 295,181,699 blocks. Seabed y (p10 / median / p90):

| Zone | Before | After |
|---|---|---|
| Frostwater Shelf | 11 / 22 / 56 | 22 / 48 / 56 |
| Windward Deep | 12 / 17 / 52 | 17 / 36 / 52 |
| Eastern Reach | 10 / 12 / 46 | 17 / 32 / 54 |
| Southern Shallows | 10 / 26 / 71 | 23 / 53 / 71 |

**The polish (the owner's review: "remove the rectangular deep-water artefact").** No box is excluded any more: the
Southern home waters (x0-1760 z5000-5900), the coast features' boxes and the Sound (x6700-7700 z4400-7400) all read as
dark rectangles. The coast features now run **after** the sea floor and build on the fill (they may reshape the fill's
columns; nothing else may), the bank runs after it too, and only lake basins, river mouths and protected ground are kept
out, with the 96-block feather. The Sound's crossings keep every column's swim rate (I3b).

**The ferry straits (question 2)** are no longer kept at their old depth as cut channels: each gate line has a soft
trough, up to 12 blocks under the profile along a centreline that wanders 40 blocks, fading out over about 110 either
side and over 160 toward each shore (four straits: the Sound ferry, Sunset, Northgate, Northlight). The swim rates are
the fill's (P4), so every gate stays a gate (section 8); a strait still reads deeper than the shelf. The Pacifidlog lines
take no trough (section 15).

**The margin relief (question 1, option A, designed).** `tools/worldpainter/export_world.js` fills the margin by
importing a blank canvas-sized image through a `TransformingHeightMap` offset by the margin, with onlyRaise, creating
only the tiles the landmass lacks. It now takes `--margin-image=<png>` and imports that image there instead (same
offset, same importer and image-to-world line); `tools/reexport.py` passes it when `data/world.json`
`export.margin_relief` pins it (path beside the heightmap, sha256, checked like the heightmap); `water_shape.py --apply`
copies it there and writes the pin. **Not run: the export script change is untested.** The image [run]:
10,752 × 10,752, 16-bit, zero over the heightmap's square (so the landmass tiles stay untouched), and outside it:

- the copy's edge carried outward, the sea floor fading to the y10 floor over 320 blocks (it meets the edge within a
  block, M4), and the edge's land carried off as headlands (section 14, reworked 2026-09-28);
- **finding:** land touches the heightmap's edge (north 1,527 columns up to y96, west 444, east 452), and today's
  blank margin drops it to a y10 plain in one column, a cliff of up to 86 blocks inside the border; the image carries it
  off as headlands that fall to the sea (highest margin y95.6 at the edge; nothing above y59 beyond 200 blocks, M6);
- the five seamounts of `the_outer_deep`, radius 161-214, summits exactly at their region's y46-54 (M5).

The floor cannot go below y10.09 (image value 0 on the import line), so the_outer_deep's planned y8 plain is y10.

---

## 8. The crossings, measured [run]

Walked on the copy with `data/blackout.json`'s constants at 5 blocks a second: plain, with Slowness counted, and
resting on every rest stretch of 6+ blocks. The four contract C3 lines reproduce the plan on the canonical heightmap.

| Crossing | Swim before -> after | Longest 3-deep run after | Unaided before -> after | Trained before -> after | Resting after (unaided / trained) | Required |
|---|---|---:|---|---|---|---|
| Relic, from the beach (C3) | 71 -> 71 | 62 | no hit -> no hit | no hit -> no hit | no hit / no hit | no hit: **met** |
| Relic, from the jetty | 117 -> 117 | 75 | hit -> hit | no hit -> no hit | hit / no hit | still a row: **met** |
| Pallet coast to Fungal Isle | 159 -> **53** | **26** | KO -> **no hit (warned)** | no hit | no hit / no hit | **met** |
| First Cast jetty to Fungal Isle | 142 -> 142 | 83 | KO -> KO | no hit | KO / no hit | reported |
| Sound narrows z6100 / z6300 / z6500 | 65 / 137 / 96, unchanged | 38 / 123 / 90 | no hit / KO / KO | no hit | as before | rates unchanged: **met** |
| Dunes to the Long Isle | 84 -> 84 | 78 | hit -> hit | no hit | hit / no hit | rates unchanged: **met** |
| Pacifidlog's Sound jetty to the square (C3) | 179 -> 179 | 160 | KO -> KO | KO -> KO | KO / hit | gate, rates unchanged: **met** (retires, section 15) |
| **Pacifidlog ferry: new jetty to the re-sited square** | (over land) -> **659** | 659 | -> **KO** | -> **KO** | KO / KO | gate: **met** |
| **Pacifidlog: nearest land to the town** | (over land) -> **686** | 655 | -> **KO** | -> **KO** | KO / KO | gate: **met** |
| Sunset strait (C3) | 257 -> 257 | 223 | KO -> KO | KO -> KO | KO / KO | gate: **met** |
| Marsh country to Northgate | 280 -> 280 | 256 | KO -> KO | KO -> KO | KO / KO | gate: **met** |
| The Northlight packet (C3) | 418 -> 418 | 397 | KO -> KO | KO -> KO | KO / KO | gate: **met** |

The Jungle Isle's own crossing (eastern dunes to the isle, 307 swim, a gate) is gone with the island. The nearest land to
the re-sited town is the plateau's south beach at (5202, 6580), 686 blocks of swimming to the town's first deck at
(5217, 7282). Every ferry gate stays a gate under the plain, Slowness and resting walks, including the new Pacifidlog line.

---

## 9. How to make the maps and numbers (one command each)

With the canonical heightmap at the source root, no server, nothing written outside `derived/` (about 6 minutes, then 5
for the audit):

```
python tools/water_shape.py --source-root C:/Users/wnd/Documents
python tools/water_shape_audit.py --source-root C:/Users/wnd/Documents
python tools/sea_town.py plan --resite --heightmap derived/water_shape/land_8k_16_rescaled_b145_pads_rift_water.png
```

Written under `derived/water_shape/` (gitignored, reproducible): the copy, `margin_relief.png`, `manifest.json`,
`changed.npy`, `owner.npy`, `rivers_revised.json`, `zones/lake_<id>.png`, `REPORT.md`, `report.json`, `audit.json`;
**maps**: `lake_<lake>.png` (9), `river_<course>.png` (6),
`coast_*.png` (7), `seabed_overview.png`, `margin_relief.png`, `jungle_isle_bank.png` (the Jungle Isle before and the bank
after, with Pacifidlog's decks, the new jetty and the ferry line), `pacifidlog_bank_town.png` (the town's close-up), and
`long_isle_split.png` (the Long Isle's desert and jungle, the old line and the new); **sections**: the lake and shelf
sections, `jungle_bank_ns.png`, `jungle_bank_ew.png`, the six river long profiles, `crossing_<id>.png` (15 fatigue
traces) and
`sections.csv`. `derived/sea_town/plan_resite.json` is the town's plan on the copy.

**Scripts still needed** (none is written): `tools/paint_maps.py` reading the lake zones and the revised courses and
accepting a water-shaped heightmap in its guard; paint classes for the new land and for the bank; a world verify for the water after a staging export; the independent tests of this audit (a test author's).

---

## 10. What the audit checks (`tools/water_shape_audit.py`)

It never reads the generator's plan or report; it derives every footprint and expectation from the design file and the
committed data (and, for the re-sited town, from `data/sea_town.json` through `tools/sea_town.py`'s own translation),
and compares the copy with the canonical file.

| Code | Check |
|---|---|
| A | the canonical file hashes to `data/world.json`; the copy to its manifest; the manifest is complete; the design file is the one used |
| B | every changed column is inside a declared footprint (the bank's is the island grown by its apron) |
| C | nothing changed in a town footprint (but the released ones), on a road, a bridge, in the Rift, over Victory Road, under the islet or a built water event site |
| D | swim-rate invariance outside the rest-ground coast features; the reef never under 3 |
| E | per lake: wet area and level; wadeable share; the rest budget (whole lake, or the scoped shore band, and each dive site's rest point, E6b); deep area; keep zones untouched |
| F | every course present; unchanged courses paint identically; revised courses never rise, step big only at falls, dry no new station, end where they ended, add no leak; each meander's sinuosity |
| G | the Viltri Ravine on hold: no column changed inside its polygon outside Lake Viltri's basin, and no ravine stream among the revised courses |
| H | seabed fill only, never above y59, never on a column shallower than 4; the windward deep band keeps its deep water |
| I | the walk calibrated on the canonical heightmap (hard on the C3 lines); every gate knocks out under the plain and resting walks (one declared exemption); rates unchanged on the Sound lines (I3b); the new Pacifidlog lines walked on the copy only |
| J | something changed; every family (the bank's too), flat, skerry field, the reef and the chain changed something |
| K | the Jungle Isle: nothing of its land left at or above the sea; the bank 4-11 deep away from the town; rest ground only at the town; every re-sited deck over its kind's least depth; the new jetty ashore on the beach, its landing over 3; the blue hole 33+ deep |
| M | the margin relief: present and hashed, the canvas's size, zero over the heightmap, meeting the copy's edge, the seamounts' summits, nothing above y59 beyond 200 blocks of the edge |

The ravine's stream checks of the first run are replaced by "the ravine untouched" while it is on hold. This is the implementer's audit;
its independent tests come later from a different agent.

---

## 11. What needs the export: all of it

Every piece here is shape and reaches the world only through an export. **The staging export, `cobblers-dryrun12`**
(REEXPORT.md "Dry run"; the owner approves step 4; nothing touches the live world):

1. The owner reviews the maps and `REPORT.md`, and answers section 14.
2. The three commands of section 9: CLEAN, and the town's plan passing on the copy.
3. `python -m pytest tests/test_system_contracts.py` (C3 before and after).
4. **On a branch, owner-approved:** `python tools/water_shape.py --source-root C:/Users/wnd/Documents --apply`. It refuses
   unless the audit passed this exact copy; it copies the heightmap and the margin relief beside the canonical file and
   repins `data/world.json` (`heightmap.water_shaped_from`, `export.margin_relief`).
5. After the apply: `data/rivers.json` from `derived/water_shape/rivers_revised.json`; **Part B's records (section 15.4)**, starting with
   `python tools/sea_town.py fold-resite` then `write`; the paint change and `python tools/paint_maps.py`; then, as
   WATER_BUILD_PLAN 3.4 lists, `cell_stats.py --write-cells`, `region_measure.py --write`, `measure_towns.py`,
   `build_routes.py`, `waterways.py`, `compile_spawns.py`, the visibility re-measure, and
   `python -m pytest tests/test_system_contracts.py` on the new heightmap.
6. `python tools/heightmap_check.py C:/Users/wnd/Documents/land_8k_16_rescaled_b145_pads_rift_water.png`: 0 tears.
7. `python tools/reapply.py prepare …`: 0 problems.
8. Process and port check, then the coordination lock, server stopped.
9. `python tools/reexport.py … --name cobblers-dryrun12 …`; check 484 region files, `seed_match: true`, **and the margin
   (the seamounts and the edge) in the new world**: the first run of the margin image.
10. `reapply.py carry --rehearsal …`, `install`, boot at `-Xmx16G`, `reapply.py run`, stop, copy, `reapply.py audit`.
11. The water verify (to be written) on the stopped copy; then the owner's flight.

---

## 12. What changed in the design since the first run (each with its why in `data/water_shape.json`)

| Target | Was | Now | Why |
|---|---|---|---|
| Shoal shape and placement | elongated crests on a trend, farthest-point placement, up to 16 | irregular sunken islands, most-reach placement, up to 12, none within 40 of a kept pit | the owner: streaks; fewer |
| Big lakes' rest budget | whole lake | the dive sites (and Tilpey's north shore band); natural islands in the open water | question 4 answered (C), and the necklaces round the pits |
| Tilpey | 46 bars, budget 75, practice floor = half the lake | 5 shoals (3 natural), budget 60 in scope, practice floor a 36-block floor below the north shore | question 4 |
| Mt Clay pond | budget 30 | 34 | 12 shoals at 30 |
| Keep zones | eased only where the design was deeper, over 32 | both ways, over 80 (Viltri 24) | pits read as hard-edged blobs |
| Floor noise | one octave at 24 | 64 and a ripple at 20 | speckle |
| Flats | unbroken bars, noise rips, 12-block ease | crescent segments, gap rips, 48-block wandering ease | streaks and wedges |
| Relic reef | from radius 34, lobed knolls; islet margin 2, Relic town margin 8 | from the islet's outline, patch reefs, 40° fades; margins 0 | the sickle and the crosses; the moat |
| Seabed exclusions | Southern home waters, the Sound, coast-feature boxes, gate straits | none but lakes, river mouths and protected ground; troughs under the gate straits | the rectangles; cut channels |
| Order | coasts, then seabed | seabed, bank, then coasts | features build on the fill |
| Watering Hole outflow | kinks between meanders | smoothed planform | question 5 answered (B) |
| Viltri Ravine | a stream down the sea half | nothing: on hold | the owner, 2026-09-27 |
| Margin | not in the heightmap | a margin relief image | question 1 (A) |
| Jungle Isle, Pacifidlog, Long Isle | as they were | section 15 | the owner's Part B decision |

---

## 13. Risks

- **Nothing has been in a world.** The maps are renders of heights; water, paint and the new land's materials are
  unseen. The margin image path through WorldPainter is written, not run.
- **Every placed thing that seats on water ground moves with it** at the re-apply: the First Cast jetty and Viltri's
  platforms are protected; lake docks and any Phase C site must be sited on the revised ground.
- **Part B moves many records at the apply** (section 15.4); until then every record keeps the Sound town and the
  island, so staging and the contracts stay consistent.
- **Paint.** The bank and the new land (skerries, stacks, the barrier bar) have no paint classes yet.
- **The margin's edge continuation is crude**: land at the map's edge is carried straight outward, so the margin's
  first 80 blocks off each headland read as a ramp perpendicular to the edge.
- **The Frostwater ridge line and the Viltri sounding box are drawn, not measured.**

---

## 14. Owner questions

Answered on 2026-09-27 (the main session's recommendations; the owner reviewed the maps): **1** (A, the margin relief),
**4** (C, dive sites only), **5** (B, smooth the whole course). **2** (straits) is resolved by the troughs, which keep
a strait reading deeper without cutting a channel. Still open, and close:

**Decided by the owner, 2026-09-27** ("All of them choose 'reads real' over 'convenient', which is right"):
1. **First Cast's scour hole:** kept.
2. **Shrew, Arrow and Marshy Marsh by the dive-site rule:** kept (open water 95-105 blocks from rest).
3. **The Viltri Ravine: dry, both halves, and dressed** so it reads as a deliberate, old watercourse that stopped:
   braided channels, bleached bars, the dry falls lip at the pass, the ford at Stoneford, the silted dead arm at the
   lake end. "Your finding that a lake-side stream could never have reached Lake Viltri settles it — it is honest as
   well as the better story." The bed pattern goes into the export (paint); the boulders, driftwood, falls lip, ford and
   dead arm are blocks after it. SQ-G1-01 and Stoneford stand as written.
4. **Part B's reading** (section 15.1): not corrected by the owner.
5. **The Pacifidlog ferry's length:** 686 blocks, kept.
6. **The Pallet flats at 20% wadeable** (the gaps between bars are rips): kept.
Still open: **the margin's continuation** of land off the map edge (section 7). The main session's close-ups
(2026-09-27): the design removes today's single-column cliffs (north 86 blocks, west 67, east 58; steepest step now
0.6-2 blocks) but copies each edge column straight outward, so the ramp reads combed (parallel streaks), not as a
headland. To be reworked before the export.

**Reworked 2026-09-28, waiting on the owner's look** (`data/water_shape.json` `seabed.margin.relief.headlands`,
`water_shape.py` `_headland_field`). Farther from the edge the edge row is read more blurred along itself (a narrow
ridge tapers, a broad shoulder holds) at a position that wanders, and each stretch of coast reaches out its own
50-185 blocks, holding its height and rounding over to a tip two blocks under the sea, then falling at 0.6 a block under
water. The sea floor is read blurred faster than the land, so a step in the heightmap's own edge (shelf to deep) no
longer runs out as a hard line. [run] Margin land (y62 and over) 191,406 columns; the first margin column within a
block of the edge (M4); highest ground beyond 200 blocks y54 (M6); the audit clean at 181 checks. Close-ups of the three
edges with land (north x446-1270, west z5430-5874, east z6010-6462), before and after, were shown to the owner. Left for the owner's
look: the east headland is the weakest of the three, and a small round hollow sits in the north headland's east end.

---

## 15. Part B: the Jungle Isle removed, Pacifidlog on the sea, the Long Isle split

### 15.1 The decision and its reading

The owner, 2026-09-27, verbatim: *"pacifidlog should be on an island, it should be on the sea, jungle isle should be
removed and pacifidlog should be around there."* and of the Long Isle's south: *"it should be half jungle half desert"*.

**The main session's reading, stated so the owner can correct it:** the Jungle Isle's land (`data/regions.json`
`jungle_isle`, x4384-5928 z6880-7976) is removed down to a shallow sea bank where the island stood; Pacifidlog, the raft
town, is re-sited onto that bank on the open sea (rafts on posts to the seabed, as built in the Sound); the Long Isle
becomes half desert, half jungle; the jungle ruins and the quests and charter that visit them move to the Long Isle's
jungle half (recommended; the owner may drop them). "On an island" is read as "a place of its own out on the sea": no
land is kept (a small sand cay under the Stilt Quarter would be the alternative, and would add rest ground only at the
town).

### 15.2 The bank (`data/water_shape.json` `jungle_isle_bank`) [run]

- **Removed:** the island's 1,321,739 land columns (its polygons grown 64, at or above the sea), and the old beach ramp
  where it stood shallower than the bank's edge (289,818 columns): 63.4 M blocks cut, nothing filled. **Nothing is left
  at or above the sea** (K1).
- **A drowned island:** the bank's depth follows the old island's own relief (its high ground, ranked, the crown at 5
  deep; its coast the edge at 9), with two octaves of low relief. Away from the town it is **4-9 deep** (p10 5, median 7,
  p90 9): swimming, diving and fishing water with no rest ground. It rises from the filled shelf on the north (8-12) and
  from the deep basin on the south.
- **The town's bed:** rafts over 3-5, sand shallows 1-2 deep of their own wandering shape under the Stilt Quarter and the
  boatwright's yard (the only rest ground on the bank: 3,073 columns, all at the town, K3), a dredged slip under the
  yard's slipway, all fading into the bank over 40 blocks.
- **The blue hole** off Fishers' Row's head, centre (4939, 7378), 34 deep: a sand lip, a wall with a ledge, a bowl floor.

### 15.3 Pacifidlog's new site (`data/sea_town.json` `resite`), measured on the copy

`python tools/sea_town.py plan --resite --heightmap derived/water_shape/…_water.png` (new: `--resite` translates the
layout by the resite; `--heightmap` measures on the copy, checked against its manifest; `write` and `check` never use
it, and a new `fold-resite` makes the resite the layout, refusing until `data/world.json` carries
`heightmap.water_shaped_from`). **Passes every rule of the plan on the copy [run]:**

- The whole town but its mainland jetty moves by (-2050, +420): the square from (7210, 6960) to **(5160, 7380)**, over the
  old island's high middle (the ruins' flat square was at (5160, 7463)); 55 elements, 8,149 deck cells, 451 posts, 246
  outdoor lanterns, every open deck cell lit to at least 5.
- Depths under the decks: rafts 3-5, the square 3-4, Fishers' Row and its head 3-11 (the head at the blue hole's lip),
  bridges 2-5, the breakwater 3-5 (it now floats: its landfall is off), the wharf, boardwalk and landings 1-2, the
  moored rafts 2.
- The Centre's door at (5160, 7360), the Mart's clerk at (5189, 63, 7378), the waystone at (5160, 7384).
- **The new mainland jetty** on the plateau's south beach: a bamboo jetty x5159-5161 z6582-6653 (ashore on y62 sand) to a
  landing x5153-5167 z6654-6662 over 6-7 blocks of water, its boat rack, a sign to Redbrow (the Tableland stop, 850 north)
  and one to Pacifidlog, "south by boat, about 700 blocks".
- **The ferry is the gate** (section 8): the ferry line swims 659, the nearest land 686; both knock out unaided and
  trained swimmers under every walk. **Boats:** at `rough_blocks` 48 the bank, with no land, is rough water everywhere, so
  the only sheltered box is the town's own, x4946-5254 z7256-7682 (the town grown 24): boats work round the town and
  tip their riders on the crossing. The Sound's bay and apron boxes retire.
- **The Sound's old town:** the re-apply builds the town from data, so at the next export it is built only at the new
  site and **the Sound gets nothing** (no rafts, no jetty, no ferryman). The staging world's Sound town stays in that
  world until an export rebuilds the region from the heightmap.

### 15.4 Every record that names the Jungle Isle or Pacifidlog's Sound site

**Changed in this design (committed):**

| Record | Change |
|---|---|
| `data/water_shape.json` | `jungle_isle_bank`; `release_towns` (sea_town, jungle_ruins); the Pacifidlog crossings; the Jungle Isle crossing removed; the Sound lines to rates-unchanged |
| `data/sea_town.json` | `resite` (shift, the new jetty, rack and signs, the floating breakwater, site, reading, sheltered box) |
| `data/ferries.json` | dock `pacifidlog_south_jetty` (planned); line `pacifidlog_ferry` ($150, swim `unsited` until the apply, with its designed barriers); `sound_ferry` marked to retire; `jungle_ruins_landing` to be sited on the Long Isle or dropped |
| `data/regions.json` | the Long Isle's desert/jungle line (15.5) |
| `tools/sea_town.py`, `tools/water_shape.py`, `tools/water_shape_audit.py`, `tools/reexport.py`, `tools/worldpainter/export_world.js` | as above |

**At the apply (not changed now: the canonical heightmap still has the island, and staging and contract C3 stand on the
Sound town):**

| Record | Change | Owner |
|---|---|---|
| `data/sea_town.json`, `data/placements.json` (settlement and six earthworks), `data/traders.json` (`sea_town_mart`), `data/towns.json` `sea_town` | `sea_town.py fold-resite`, `write`, then `measure_towns.py`; the town's `for`/`why_here` text | world-content-dev |
| `data/blackout.json` `boats.sheltered` | `pacifidlog_bay` and `pacifidlog_apron` replaced by `pacifidlog_bank` | minecraft-systems-dev |
| `data/ferries.json` | `pacifidlog_ferry` declared a gate (island seed (5160, 7380), barriers from section 8); the new dock built; `sound_ferry` and `pacifidlog_jetty` retired; `pacifidlog_square` moves with the square | minecraft-systems-dev |
| `data/system_contracts.json` C3 and C11, `tests/test_sea_town.py`, `tests/test_system_contracts.py`, `tests/test_boats.py` | the Sound ferry line replaced by the new one; the breakwater no longer comes ashore | test-author |
| `data/regions.json` `jungle_isle`, `jungle_west`, `jungle_east` | retired (or a marine sub-area for the bank) | world-content-dev |
| `data/spawns.json` `jungle_west`, `jungle_east` rosters | retired; the bank needs a marine and fishing roster round the town (LONG_ISLE.md section 6's Sound and Current Gate candidates) | datapack-content-dev, trainer-balance-designer |
| `data/foliage.json` jungle overlays (`jungle_west`, `jungle_east`), `tests/test_foliage_overlays.py` (its jungle window) | retired; the overlays' intent moves to `long_isle_south` | world-content-dev, test-author |
| `data/elder_trees.json` `elder_jungle_east_1`, `_2`, `elder_jungle_west_1`, `_2` and their 16 nests in `data/habitat_blocks.json` | retired or moved to the Long Isle's jungle half (they would seat on the seabed) | world-content-dev |
| `data/towns.json` `jungle_ruins`, `data/placements.json` (its settlement and six ruin pieces), `data/signposts.json` ("Jungle Isle ruins") | moved to the Long Isle's jungle half (recommended) or dropped | world-content-dev |
| `data/structures.json` (8 records naming `jungle_isle`), `data/sculpt.json` (`jungle_isle` in the coast's soft regions) | drop `jungle_isle` | world-content-dev |
| `docs/mechanics/WATER_BUILD_PLAN.md` 11.1-11.3, `WATER_PROPOSAL.md` (the Sound ferry, the jungle ruins charter), `WATER_MAP.md`, `docs/world-building/OCEAN.md`, `REGIONS.md`, `SETTLEMENTS.md`, `SETTLEMENT_NAMES.md`, `FOLIAGE*.md`, `BIOME_COVERAGE*.md`, `SAPLING_BIRDS.md`, `STRUCTURE_*.md` | the island's removal and the town's move | content-architect, world-content-dev |
| **Codex (story text, not edited here):** `SQ-SUNSET-02` (sails to the ruins at (5160, 7463)), `SQ-JUNGLE-01`, `SQ-JUNGLE-02` (the ruins, "the harbour and jungle island"), `docs/story/ENCOUNTERS.md` (the Jungle Isle's section), `docs/HANDOVER_CODEX.md` items 17-18 (the ruins' cache), the Pacifidlog display text ("in the Sound"); and, from section 4, `SQ-G1-01` and Stoneford | new coordinates or a rewrite | Codex |

### 15.5 The Long Isle, half desert and half jungle (paint, `data/regions.json`)

The desert/jungle line (the cover change between `long_isle_middle`, sandstone uplands, and `long_isle_south`, jungle)
moves about 220 blocks north, from about z6880 to a wandering line at z6632-6672 from (7345, 6650) to (8161, 6640),
824 blocks long. Re-measured by `tools/region_measure.py --write` (only these two records changed): **desert (north and
middle) 1.284 km², jungle (south) 1.285 km²** (they were 1.48 and 1.08). The map is
`derived/water_shape/maps/long_isle_split.png`. It is paint and lands at the next WorldPainter export; the rosters and
foliage follow the polygons. See `docs/world-building/LONG_ISLE.md` section 11.
