# The water's shape: the heightmap revision for the water export (Phase B)

**Status: DESIGN, RUN 2026-09-27, for the owner's review. Nothing is applied and nothing is exported.** The canonical
heightmap (`0d9b5f1e…`) and everything under the source root are untouched. The design (`data/water_shape.json`) was
applied to a copy by `tools/water_shape.py` and checked by `tools/water_shape_audit.py`: **167 checks, CLEAN**. Every
"after" number below is **[run]**, measured on that copy (`derived/water_shape/report.json`, `audit.json`); **[plan]**
marks values from `docs/mechanics/WATER_BUILD_PLAN.md`. The first run found the tools' bugs and several targets real
terrain could not meet; section 12 lists every target changed and why. Nothing here has been seen in a world: the maps
are renders of heights, and the in-world water check (section 9) is not written.

The plan this carries out is `WATER_BUILD_PLAN.md` Phase B: items 1, 3 and 4's *shape* (rivers and lake terrain, the
shallows, the seabed) as **one** heightmap revision and **one** staging export (decision 5). Materials, plants, coral,
grottos, caves, wrecks and docks are blocks (Phase C) and are not here.

**The revision in one line [run]:** 15,709,036 columns changed (of 67.1 M), 286,990,256 blocks filled and 2,638,647
cut; 14,096,247 of those columns and 277 M of the fill are the seabed. The copy is
`derived/water_shape/land_8k_16_rescaled_b145_pads_rift_water.png`.

---

## 1. What changes where, in one table

| Family | Where | What the player gets | Serves | Layer |
|---|---|---|---|---|
| **Meanders** | the major river's lower trunk (806-2213 m), Viltri's Path over the coastal flats (655-1298), Arrow Lake's outflow (32-262), three low-grade stretches of the Watering Hole outflow | loops of varying length and size, pools on the outside of bends, point bars inside, cut banks where a loop swings into the valley side; the surface steps only at riffles | decision 9, the owner's item 1 | heightmap |
| **Cascades and falls** | the tarn outflow, Peak Pond outflow, the Watering Hole outflow's last 320 blocks, Viltri's Path's last 213 blocks | the one-block steps gathered into short cascades with plunge pools, one 2-3 block fall each | decision 9, item 1 | heightmap |
| **The Viltri Ravine stream** | from a spring pool below the pass down the sea half, 611 blocks to the sea | an underfit stream 3 wide in a bed far too wide for it, 70 steps and one 3-block fall; the lake half stays dry | decision 4 (option B) | heightmap |
| **Lake beds** | all nine lakes | a wadeable shelf whose width wanders and widens in bays, a drop-off, a silt floor with relief, humps, sunken islands (bars) as rest points, arms that stay shallower than the basin, keep zones exactly as they were | decision 8, item 1 | heightmap (bed zones handed to the paint and the skin) |
| **Tidal flats** | off Pallet, Route 1's west coast, the south strand | wandering shore-parallel bars and runnels with rip channels; a lagoon behind a dry barrier bar on the south strand | the owner's item 3 | heightmap |
| **The Fungal bar chain** | Pallet coast (985, 5233) to Fungal Isle | two lobed sand bars; the longest 3-deep run 26 blocks; an unaided swimmer is warned and never hit | decision 7 | heightmap |
| **The Relic reef platform** | Relic Island's south and west apron | a platform 3 deep grading to 12, six lobed patch-reef knolls, a reef wall to the old seabed | decision 7, item 3 | heightmap (coral is blocks) |
| **Skerries and sea stacks** | windward cliffs (10 skerries, 4 stacks), north-west coast (6, 2) | low rocks at y63-65 and stacks to y73-81 with a boulder skirt | item 3 | heightmap |
| **First Cast's scour hole** | off the jetty's west end | a hole 4 deep under the rod (48 columns) | item 3; a **proposed addition** | heightmap |
| **The seabed** | the four marine zones inside 0-8191 | OCEAN.md's shelf, break, slope and basin, filled up to the profile with the canyons carried through; two ridges | decision 6 | heightmap |
| **The margin's seamounts** | outside the heightmap | not shaped: **owner question 1** | decision 6 | needs a decision |

Unchanged on purpose: the Tilpey outflow gorge under the Route 7 bridge, the Sound and everything Pacifidlog stands on,
every ferry strait, the islet, the towns, the roads, the Rift and Victory Road.

---

## 2. The rules the revision keeps (the audit checks each)

1. **Shape only (P1).** Everything here is a height; nothing is a block.
2. **Bit-identical outside the declared footprints (P2)**, column by column: B1, 0 stray columns.
3. **Nothing already placed moves (P3).** Never written: every town footprint plus 8, every route line plus 6, the
   Rift's region grown 24 and every column the Rift sculpt changed, Victory Road's band plus 32, the bridges plus 16,
   **the islet's outline plus 2** (section 12), the sea town, the First Cast jetty and Viltri's two platforms; and, new
   from the run, **every cut river's painted channel** (a lake shelf sealed four outlets on the first run).
4. **Swim-rate invariance (P4).** No sea column 3+ deep became shallower than 3 outside the declared rest-ground coast
   features (D1: 0 columns); the seabed never rises above y59.
5. **Lakes keep their level and shoreline (P5):** E1 and E2 pass on all nine lakes.
6. **Every river still drains end to end (P6):** no surface rises downstream; steps over one block only at the
   declared falls; no station dried out that was wet; no new leak (F3-F7 on every revised course).

---

## 3. Rivers (item 1: "rivers that feel like they flow")

**Today [plan]:** straight canals, sinuosity 1.01-1.20; one-block drops every 20-120 blocks.

**The design.** Sine-generated meanders over the old centreline, inside the room the valley gives, tapered to nothing at
each end of a window and at every tributary's mouth (the run added the mouths: the first run swung Viltri's Path off
the Mt Clay pond outflow's junction and filled it). **The run added variation**: a fixed sine read on the map as drawn,
so the wavelength wanders ±30% and the amplitude breathes (it only ever shrinks from the room allowed). The abandoned
channel is filled to one block above the old water; the new channel is cut to the reach's cross-section with the
thalweg on the outside of each bend. Steps are gathered upstream into riffles (meanders) or cascades (steep creeks).

**Sinuosity per window, measured by the audit on the copy [run]** (channel length over the chord):

| Window | Course | Before | After | Target | Wavelength / amplitude median, max |
|---|---|---:|---:|---|---|
| `major_lower_trunk` | major_river_trunk | 1.02 | **1.29** | 1.2-1.5 | 216 / 29.5, 39.5 |
| `viltris_path_coastal_flats` | lake_viltri_outflow | 1.11 | **1.56** | 1.3-1.6 | 79 / 10.8, 32.6 |
| `arrow_outflow` | arrow_lake_outflow | 1.07 | **1.34** | 1.3-1.6 | 120 / 20.1, 27.1 |
| `watering_hole_outflow_upper` | watering_hole_outflow | 1.06 | **1.32** | 1.2-1.5 | 110 / 10.7, 20.0 |
| `watering_hole_outflow_middle` | watering_hole_outflow | 1.00 | **1.24** | 1.2-1.5 | 110 / 13.0, 24.6 |
| `watering_hole_outflow_lower` | watering_hole_outflow | 1.07 | **1.41** | 1.2-1.5 | 110 / 18.0, 21.0 |

The cascade windows keep their planform (sinuosity 1.00-1.03) and gather the steps: tarn outflow 64 steps and a 3-block
fall; Peak Pond outflow 42 and a 2-block fall; Watering Hole outflow's last reach 19 and a 2-block fall (1,697 columns
held off by Sunset West's protected footprint); Viltri's Path mouth 24 and a 3-block fall.

**Checks [run]:** every revised course: surface never rises, big steps only at declared falls, 0 new dry stations,
and fewer leaks than before (dry columns below the water beside it, before -> after: major 318 -> 56, Viltri's Path
298 -> 180, Arrow outflow 22 -> 20, Watering Hole outflow 178 -> 85, Peak Pond outflow 305 -> 262, tarn outflow
214 -> 20). The five unchanged cut courses (the Tilpey, Marshy Marsh, Shrew Lake and Mt Clay pond outflows and Tilpey's
south-west outlet) paint exactly as before (F2).

**Finding (the plan said "the Watering Hole outflow's lower reach").** Its last 340 blocks are graded 0.026-0.12, too
steep to meander; the meanders are on its three low-grade stretches and the last reach gets cascades.

**Chain order (a deliberate change from WATER_BUILD_PLAN 3.4).** The river change is a final stage on the canonical file,
like the lakes (below y145 the rescale is the identity and the sculpt kept river channels unchanged), so one pass is
bit-identical everywhere else. The cost: `tools/paint_maps.py`'s cut-hash guard must accept a water-shaped heightmap and
read `derived/water_shape/rivers_revised.json` (a named change for the apply step). The revised courses keep the
canonical stations exactly outside the windows (full precision), and their reach boundaries are in the chainage the
painter measures, so a width change lands on the same stations as before.

**Seen on the maps.** The major river, Viltri's Path and Arrow's outflow read as rivers. The Watering Hole outflow reads
as a canal that meanders three times: the stretches between its windows keep the graded course's straight segments and
sharp vertex kinks (owner question 5).

---

## 4. The Viltri Ravine stream (decision 4, option B)

**[run]:** the spring pool at (870, 3846), level y134; the stream runs 611 blocks to the sea at y62, 21 of them beyond
the axis's low end; 70 steps, one 3-block fall 512 blocks down; 3,517 columns cut (10,266 blocks), none filled. Every
station holds water; the lake half is untouched outside Lake Viltri's basin (G1-G7). When applied,
`data/landmarks.json` `viltri_ravine` `water: never` becomes `partial`, and **Codex checks `SQ-G1-01`'s wording**.

---

## 5. Lakes (item 1: "lakes that read as lakes, not step-down bowls")

**The profile [run].** Shelf width comes from how enclosed the **shore** is, carried out over the water beside it (the
first run measured each column's own surroundings, so every shelf came out at the narrow end), and wanders ±30% over
about 56 blocks. Inner 60% of the shelf 1 deep, outer 40% 2 deep; the drop-off; a basin floor mapped from the old ramp
(plunging near the drop-off, flattening toward the deepest point) with ±2 blocks of silt relief. **Added by the run:**
arms and bays that were shallow stay within 2 blocks of their own deepest old bed (Shrew's south-west arm was dug from
about 6 deep to the basin's 14), and the floor eases back to the old bed over 32 blocks beside a keep zone (the first
run left Azelf's pit a plateau inside a moat). Rest points are **sunken islands**: an elongated, irregular crest 1 deep,
a 3-block apron to 3 deep, then a 1-in-1 flank (the first run's round crests on 1-in-2 flanks rendered as a grid of
cones). On Shrew, Arrow and Tilpey they lie on the lake's own trend, so they read as the valley's grain.

**Measured [run]** (farthest water from anywhere to stand; before is the whole lake, after leaves out each lake's
declared dive zone):

| Lake | Rung, budget | Wadeable before -> after (target) | Farthest from rest before -> after | Shoals | 9+ deep columns before -> after | Fill / cut blocks |
|---|---|---|---:|---:|---|---|
| Viltri | trained, 60 | 6.9% -> **18.5%** (15-40) | 80 -> **58** | 1 | 18,913 -> 19,549 | 36,311 / 53,946 |
| Shrew | trained, 60 | 6.6% -> **11.1%** (10-35) | 162 -> **58** (pit excluded) | 10 | 112,881 -> 112,533 | 818,792 / 628,396 |
| Arrow | trained, 60 | 4.2% -> **13.6%** (12-35) | 147 -> **57** (grotto floor excluded) | 6 | 82,579 -> 73,786 | 1,019,029 / 320,679 |
| Marshy Marsh | trained, 60 | 15.7% -> **25.0%** (20-45) | 124 -> **60** (Azelf's pit excluded) | 5 + 8 root crowns | 54,344 -> 60,182 | 117,187 / 223,471 |
| Tilpey | trained, **75** | 3.6% -> **15.0%** (12-35) | 242 -> **72** | 46 bars | 869,076 -> 677,341 | 7,054,270 / 695,555 |
| Peak Pond | trained, 60 | 15.9% -> **19.2%** (15-40) | 97 -> **53** | 2 | 15,635 -> 27,680 | 34,545 / 157,802 |
| Watering Hole | trained, 60 | 14.2% -> **20.3%** (15-45) | 65 -> **38** | 1 | 5,250 -> 9,161 | 11,568 / 34,398 |
| Mt Clay pond | **unaided**, 30 | 8.8% -> **18.9%** (15-45) | 82 -> **29** | 7 | 15,644 -> 12,504 | 128,067 / 41,578 |
| Ravine Head Tarn | trained, 60 | 10.5% -> **13.3%** (10-40) | 79 -> **47** | 1 | 12,649 -> 17,813 | 32,204 / 96,407 |

Every lake keeps at least half its 9+ deep water (the rosters' deep entries), its level and its wet area; every keep
zone is untouched (E1-E7). Neighbouring bed columns: level 78-92% before, 63-84% after, with 1.5-7% now two or more
apart (drop-offs and flanks) where there were none.

**Tilpey (owner question 4).** At about 1,300 by 900 blocks, keeping every point within the trained rung's 60 of rest
needed **81** bars [run]; at the rung's no-margin figure of 75 (75 out and 75 back is the 150 deep blocks before a
trained swimmer's first hit) it needs **46**, laid as long bars on the north-west arm's line: a drowned drumlin field.
Its fill is 7.05 M blocks, almost three quarters of all fill outside the seabed (9.84 M).

**Bed zones for the paint and the skin.** Per lake, `derived/water_shape/zones/lake_<id>.png`: 1 shelf, 6 shelf in a bay
(weed beds), 2 drop-off, 3 basin floor (silt), 4 hump, 5 shoal crest and apron, 7 kept.

**Finding.** Viltri's sounding platform's staffs read 5, 6 and 7 deep (`EARLY_ROUTES.md:138`), so the platform's water
is protected; its z range is inferred from the keeper's position and **not verified** against `tools/route_events.py`.

---

## 6. The shallows (item 3: "give it real attention")

**Today [plan]:** off Pallet and the south coast the water is one block deep for 16 blocks, then a ramp; the north and
west drop to 4-7 deep at once.

**Finding (run).** The region polygons stop 25-40 blocks short of their own beach, and the design measured distance
from the region's land: the water beside Pallet's shore measured 200+ blocks from shore and the first run laid bars on
about a sixth of the coast. The shore is now the region grown 96, which takes in its beach.

| Feature | Measured [run] |
|---|---|
| **Pallet flats** | 17,514 columns; wadeable share in the 64-block band 27.8% -> 34.0% (29,777 wet columns); 261 new dry bar crests; fill 18,967 / cut 4,378 |
| **Route 1 west coast flats** | 10,225 columns; wadeable 29.5% -> 28.9% (the runnels deepen as much as the bars raise); 114 dry crests; fill 9,111 / cut 3,956 |
| **South strand flats and lagoon** | 31,278 columns (7,911 held off by protected ground); wadeable 32.4% -> 44.4%; 1,634 new dry columns; fill 47,247 / cut 6,853. The lagoon: shore centre (2504, 6496), a barrier of 3,037 columns, 19,662 columns of calm water behind it, the inlet at (2476, 6533) |
| **The Fungal bar chain** | 2 lobed bars, 2,616 columns, 5,334 blocks filled; the line (985, 5233) -> (812, 5347) (section 8) |
| **The Relic reef** | 6,930 platform columns, 7,102 written, 110,517 blocks filled, shallowest 3 deep; knolls at (1021, 5521), (1037, 5578), (1113, 5600), (1054, 5555), (1054, 5593), (1040, 5534) |
| **Windward skerries and stacks** | 4 stacks (tops y78-81) at (419, 5140), (463, 2700), (404, 3056), (504, 4358); 10 skerries (y63-65); 2,586 new land columns; 183,617 blocks filled |
| **North-west skerries** | 2 stacks (y73-77) at (653, 1635), (721, 1518); 6 skerries; 1,396 new land columns; 59,936 blocks |
| **First Cast's hole** | 48 columns, 98 blocks cut; one column held off by the jetty's box |

**Seen on the maps and changed by the run:** bars at fixed offsets drew contour lines round the coast, so they now
wander ±6 blocks and swell and thin; they ease into the old bed toward every exclusion and box edge instead of stopping
square; the Fungal bars were dominoes and are now lobed; the reef's knolls were discs and are now lobed; the islet was
protected as a 65-block square, which left a square pit in the reef, and is now protected by its own outline (section
12). Still visible: the rip channels are noise-shaped, and one near the reef reads as a wedge.

---

## 7. The seabed (decision 6, OCEAN.md section 4)

**The profile [design]:** a shelf from `shelf_start_y` to y46, the break to y28 over 80, the slope to y18 over 400, the
basin to y10 over 600. Shelf starts: Frostwater y58 (240 wide), Windward y56 (160), Eastern Reach y58 (320), Southern
Shallows y59 (400). Fill only, never above y59, never a column under 4 deep, canyons carried through the fill.

**Measured [run]:** 14,096,247 columns filled, 277,151,889 blocks. Seabed y (p10 / median / p90, excluded water left out):

| Zone | Before | After |
|---|---|---|
| Frostwater Shelf | 11 / 22 / 56 | 21 / 48 / 56 |
| Eastern Reach | 10 / 12 / 46 | 17 / 30 / 54 |
| Southern Shallows | 10 / 18 / 58 | 25 / 51 / 58 |

The windward deep band keeps its water at y36 or below wherever it was (H5). Ridges raised 1,644 coarse cells
(windward break) and 2,005 (Frostwater; the line is drawn, not measured).

**Fixed by the run.** The canyon blur read the copy while it was being filled, band by band, and drew a line across the
sea every 256 rows; it now reads the canonical bed. The fill also fades out over the last 64 blocks of the zones' outer
edge.

**Findings.**
- **OCEAN.md contradicts itself** on filling versus keeping the imported surface; its per-zone medians show filling was
  meant, and this design fills.
- **OCEAN.md's shelf starts at y60, 2 deep**, written before swim fatigue; this design starts at y59 or deeper.
- **The excluded boxes show.** The Southern home waters box (x0-1760, z5000-5900) keeps its old deep water, so on the
  overview it is a dark rectangle with a 96-block feathered edge; the ferry straits (owner question 2) are dark channels
  across the new shelf. Both are 20-40 deep, seen only from a boat or under water.
- **The margin join (new).** Where a shelf reaches the map's edge (the northern isles), the fill now fades over 64
  blocks, but the export fills the margin as a y10 plain, so a slope of up to about 40 blocks remains at the border
  (owner question 1's option A would answer both).
- **Every seamount is outside the heightmap** (owner question 1), and the trench is blocks, postgame.

---

## 8. The crossings (WATER_BUILD_PLAN 11.1), measured [run]

Walked on the copy with `data/blackout.json`'s constants at 5 blocks a second: plain, with Slowness counted, and resting
on every rest stretch of 6+ blocks. The audit first reproduces the plan on the canonical heightmap: the four contract C3
lines match (Relic beach 71, Sound ferry 179, Sunset strait 257 against the plan's 258, Northlight 418).

| Crossing | Swim before -> after | Longest 3-deep run after | Unaided before -> after | Trained before -> after | Resting after (unaided / trained) | Required |
|---|---|---:|---|---|---|---|
| Relic, from the beach (C3) | 71 -> 71 | 62 | no hit -> no hit (exhausted) | no hit -> no hit | no hit / no hit | no hit: **met** |
| Relic, from the jetty | 117 -> 117 | 75 | hit -> hit | no hit -> no hit | hit / no hit | still a row: **met** |
| Pallet coast to Fungal Isle | 159 -> **53** | **26** | knocked out -> **no hit (warned)** | no hit -> no hit | no hit / no hit | no hit, warnings, run <= 40: **met** |
| First Cast jetty to Fungal Isle | 142 -> 113 | 83 | knocked out -> knocked out | no hit -> no hit | knocked out / no hit | reported |
| Sound narrows z6100 / z6300 / z6500 | 65 / 137 / 96, unchanged | 38 / 123 / 90 | no hit / KO / KO, unchanged | no hit | as before | unchanged depth for depth: **met** |
| Dunes to the Long Isle | 84 -> 84 | 78 | hit -> hit | no hit | hit / no hit | unchanged: **met** |
| Pacifidlog jetty to the square (C3) | 179 -> 179 | 160 | KO -> KO | KO -> KO | KO / **hit** | gate, unchanged: **met** (see below) |
| Eastern dunes to the Jungle Isle | 307 -> 307 | 275 | KO -> KO | KO -> KO | KO / KO | gate: **met** |
| Sunset strait (C3) | 257 -> 257 | 223 | KO -> KO | KO -> KO | KO / KO | gate: **met** |
| Marsh country to Northgate | 280 -> 280 | 256 | KO -> KO | KO -> KO | KO / KO | gate: **met** |
| The Northlight packet (C3) | 418 -> 418 | 397 | KO -> KO | KO -> KO | KO / KO | gate: **met** |

With Slowness counted every gate still knocks both swimmers out, and the jetty-to-Relic row knocks the unaided out.

- **The Sound ferry's trained resting walk** takes one hit, not two, **on the canonical heightmap as well**: the line
  crosses a rest stretch. The Sound is excluded from every pass, so the design now requires this line unchanged depth
  for depth instead (it is), and STATE already records the Sound ferry as a declared leak.
- **First Cast jetty to Fungal Isle** walks 142 blocks of swimming today, not the plan's 184: the audit's endpoint is the
  nearest land of the isle's region grown 24. The Pallet flats' bars now give it rest (113); unaided is still knocked out.
- The ferry is still the gate for unaided **and** trained swimmers on every gate line, under all three walks except the
  one noted.

---

## 9. How to make the maps and numbers (one command each)

With the canonical heightmap at the source root (`C:/Users/wnd/Documents`), no server, nothing written outside
`derived/` (about 3 minutes, then 1 for the audit):

```
python tools/water_shape.py --source-root C:/Users/wnd/Documents
python tools/water_shape_audit.py --source-root C:/Users/wnd/Documents
```

Written under `derived/water_shape/` (gitignored, reproducible):

- the copy `land_8k_16_rescaled_b145_pads_rift_water.png`, `manifest.json`, `changed.npy`, `owner.npy`,
  `rivers_revised.json`, `zones/lake_<id>.png`;
- `REPORT.md`, `report.json` (every number here), `audit.json`;
- **maps** (before, after, and for lakes the bed zones): `maps/lake_lake_viltri.png`, `lake_shrew_lake.png`,
  `lake_arrow_lake.png`, `lake_marshy_marsh.png`, `lake_lake_tilpey.png`, `lake_peak_pond.png`,
  `lake_watering_hole.png`, `lake_pond_west_of_mt_clay.png`, `lake_ravine_head_tarn.png`;
  `maps/river_major_river_trunk.png`, `river_lake_viltri_outflow.png`, `river_arrow_lake_outflow.png`,
  `river_watering_hole_outflow.png`, `river_ravine_head_tarn_outflow.png`, `river_peak_pond_outflow.png`;
  `maps/viltri_ravine_stream.png`; `maps/coast_southern_coast.png`, `coast_pallet_and_relic.png`,
  `coast_pallet_flats.png`, `coast_south_strand.png`, `coast_fungal_chain.png`, `coast_windward_skerries.png`,
  `coast_north_west_skerries.png`; `maps/seabed_overview.png` (1 px = 8 blocks);
- **sections**: `sections/<id>.png` for the 18 cross-sections in `data/water_shape.json` `sections`,
  `sections/river_<course>_long_profile.png` (6), `sections/viltri_ravine_stream_long_profile.png`,
  `sections/crossing_<id>.png` (13 fatigue traces, before and after), and `sections/sections.csv`.

**Scripts still needed** (none is written): `tools/paint_maps.py` reading the lake zones and the revised river courses
and accepting a water-shaped heightmap in its guard; paint classes for the new land (skerries, stacks, barrier and bar
crests); a world verify for the water after a staging export; the independent tests of this audit (a test author's).

---

## 10. What the audit checks (`tools/water_shape_audit.py`)

It never reads the generator's plan or report; it derives every footprint and expectation from the design file and the
committed data, and compares the copy with the canonical file.

| Code | Check |
|---|---|
| A | the canonical file hashes to `data/world.json`; the copy to its manifest; the manifest is complete; the design file is the one used; no sample rewritten without changing its ground |
| B | every changed column is inside a declared footprint |
| C | nothing changed in a town footprint, on a road, on a bridge span, in the Rift (region and sculpted columns), over Victory Road, under the islet's outline, or under a built water event site |
| D | swim-rate invariance outside the rest-ground coast features; the reef never under 3 |
| E | per lake: wet area and level; wadeable share, farthest from rest (the lake's budget) and deep area; keep zones untouched |
| F | every course present; unchanged courses paint identically; revised courses never rise, step big only at falls, dry no new station, end where they ended, add no leak; each meander's sinuosity |
| G | the stream starts at the pass, ends at the sea, drains, steps big only at its fall, holds water, and the ravine's lake half is untouched outside Lake Viltri's basin |
| H | seabed fill only, never above y59, never on a column shallower than 4; the windward deep band keeps its deep water |
| I | the walk calibrated against the plan (hard on the C3 lines); every gate knocks out under the plain and resting walks (one declared exemption); Relic as decided; Fungal crossed with no hit and with warnings; the Sound unchanged |
| J | something changed; every family, flat, skerry field, the reef and the chain changed something |

Three checks were recalibrated against the canonical data after the first run, none relaxed for the copy: F5 (the
canonical courses have a few dry outlet lips, so a dry station counts unless the canonical course had one within a
block at the same level), F6 (the canonical major river ends at 76.98 into Tilpey at 77 and paints 76, so a course must
end where it ended), G7 (Lake Viltri's bed is the E checks'). This is the implementer's audit; its independent tests come
later from a different agent.

---

## 11. What needs the export: all of it

Every piece here is shape and reaches the world only through an export; nothing is worked around with blocks.

**The staging export, `cobblers-dryrun12`** (REEXPORT.md "Dry run"; the owner approves step 4; nothing touches the live
world):

1. The owner reviews the maps and `REPORT.md`, and answers section 13.
2. `python tools/water_shape.py --source-root C:/Users/wnd/Documents`, then `python tools/water_shape_audit.py
   --source-root C:/Users/wnd/Documents`: CLEAN.
3. `python -m pytest tests/test_system_contracts.py` (C3 before and after).
4. **On a branch, owner-approved:** `python tools/water_shape.py --source-root C:/Users/wnd/Documents --apply`. It refuses
   unless the audit passed this exact copy; it copies the file beside the canonical one and repins `data/world.json`
   with `heightmap.water_shaped_from`.
5. After the apply: `data/rivers.json` from `derived/water_shape/rivers_revised.json`; `data/landmarks.json`
   `viltri_ravine` `water: partial`; the paint change (section 9) and `python tools/paint_maps.py`; then, as
   WATER_BUILD_PLAN 3.4 lists, `cell_stats.py --write-cells`, `region_measure.py --write`, `measure_towns.py`,
   `build_routes.py`, `waterways.py`, `compile_spawns.py`, the visibility re-measure, and
   `python -m pytest tests/test_system_contracts.py` on the new heightmap.
6. `python tools/heightmap_check.py C:/Users/wnd/Documents/land_8k_16_rescaled_b145_pads_rift_water.png`: 0 tears.
7. `python tools/reapply.py prepare --source-root C:/Users/wnd/Documents --server-dir C:/Users/wnd/Documents/github/cobblers-server`: 0 problems.
8. Process and port check, then take the coordination lock, server stopped.
9. `python tools/reexport.py --source-root C:/Users/wnd/Documents --old-world <cobblers-dryrun11> --out-dir <staging dir>
   --name cobblers-dryrun12 --world-file <a staging .world path, never cobblers-10240.world> --paint
   build/paint/manifest.json`; check 484 region files and `seed_match: true`.
10. `python tools/reapply.py carry --rehearsal …`, `install`, boot at `-Xmx16G` with the watchdog off, `reapply.py run`,
    stop, copy, `reapply.py audit`, watchdog back on.
11. The water verify (to be written) on the stopped copy; then the owner's flight.

The live world gets it only at the live re-export, which stays blocked on STATE's three items.

---

## 12. What the run changed in the design (each with its why in `data/water_shape.json`)

| Target | Was | Now | Why (measured) |
|---|---|---|---|
| Arrow outflow, room | within 3 blocks of the water | within 8; amplitude jitter 0.2 | room 9 either side (p10 7): no loop at all, sinuosity 1.06. Within 8 the room is 41: entrenched loops with cut banks up to ~8 high |
| Watering Hole outflow upper, room | 3 | 8 | room 12 (p10 8), sinuosity 1.10 |
| Watering Hole outflow lower, room and amplitude | 3, 28 | 6, 22 | room 17 (p10 11), 1.17; at 28 with the new room it measured 1.55 |
| Lake floor relief | ±1 | ±2 | a 40-deep floor rendered as one flat colour |
| Shelf width | fixed by bayness | ±30% wander over 56 blocks | a ring of one width read as a pool's step |
| Shoals | round crest, 1-in-2 flank, 8 at most | elongated crest, 3-block apron, 1-in-1 flank, 16 at most | a grid of cones; 8 left Shrew, Marshy Marsh and Tilpey over budget |
| Arrow shelf | 8-20 | 10-24 | wadeable 10.7% against 12% |
| Marshy Marsh | pit counted in the budget | pit excluded, its own near shoal | the far point was inside the kept pit; six shoals stacked on its rim and it still measured 70 |
| Shrew, Arrow, Tilpey shoals | random angles | on each lake's trend | Tilpey read as scattered seeds |
| Tilpey budget | 60 | **75** | 81 bars for 60, 46 for 75 (owner question 4) |
| Sound ferry | gate under every walk | gate, and unchanged depth for depth; the trained resting walk exempt | it takes one hit on the canonical heightmap too; the Sound is never written |
| Islet protection | 65-block square | its outline plus 2 | `island_top` ignores the bed (it is passed and unused); the square's corners are plain seabed and left a square pit in the reef |

The tools' bugs the run fixed are in the commit messages; the ones that changed what the owner would see: four lake
outlets sealed by the shelf, rivers' old-channel fill running past their windows (656 dry stations on the Watering Hole
outflow) and over a tributary's mouth, river windows writing into lake basins, new leaks from resampled stations,
shelves at the narrow end everywhere, the flats on a sixth of Pallet's coast, and the seabed's 256-row stripes.

---

## 13. Risks

- **Nothing has been in a world.** The maps are renders of heights; water, paint, flowing water on riffles and the
  new land's materials are unseen.
- **Every placed thing that seats on water ground moves with it** at the re-apply: the First Cast jetty and Viltri's
  platforms are protected, but lake docks and any Phase C site must be sited on the revised ground.
- **Paint.** New land (skerries, stacks, the barrier bar, 1,634 dry columns on the south strand, 261 off Pallet) has no
  coast class and would paint as the preset's default until the paint change.
- **Tilpey's volume.** 7 M blocks of fill for 46 bars; the export handles it, but the lake's look is the owner's call.
- **The Frostwater ridge line and the Viltri sounding box are drawn, not measured.**
- **Distant Horizons and the client cache** must be cleared after the export.

---

## 14. Owner questions (only where it is genuinely close)

1. **The margin's seamounts.** All five sites are outside the 0-8191 heightmap; the export fills the margin from a
   blank image. (A) a margin relief image beside the heightmap, pinned in `data/world.json` and read by
   `tools/worldpainter/export_world.js` in place of the blank (recommended: still shape, same export, and it would also
   meet the new shelves at the border, section 7); (B) a block pass after the export; (C) leave the margin a plain until
   the postgame.
2. **The ferry straits: keep them deep, or fill them with the shelf?** Filling would take the Sunset strait and the
   Jungle Isle's water from 20-37 deep to about 5-8; the swim rates would not change (P4). The design keeps them deep;
   on the overview they are dark channels across the new shelf.
3. **First Cast's scour hole.** Not in the plan (48 columns, 4 deep); it gives the rod open water. Keep or drop.
4. **Tilpey: the whole lake within reach of rest, or only its dive sites?** (A) the whole lake within 75 of rest: 46
   long bars on one trend, a drowned drumlin field, 7 M blocks (what the copy has); (B) within 60 as the rung says: 81
   bars; (C) decision 8 read literally, "every dive site a rest point within its budget": a handful of bars near the
   Dive school, the practice floor and the Weeping Elder island, and open deep water elsewhere, which reads most like a
   big lake but leaves a trained surface swimmer 100+ blocks from rest in the middle (a Dive-trained player does not tire
   under water, decision 1). Recommended: (C) if the Dive school's lessons cover the open water, else (A).
5. **The Watering Hole outflow between its meanders.** Its three meander windows are separated by the graded course's
   straight segments with sharp vertex kinks, so it reads as a canal that meanders three times. (A) leave it (the
   stretches between are steeper and the plan named only the low-grade reaches); (B) smooth the whole course's planform
   (a gentle curve through the kinks, no loops) in this same revision, re-cutting the channel between the windows (not
   written or measured). Recommended: (B).
