# The water's shape: the heightmap revision for the water export (Phase B)

**Status: DESIGN for the owner's review, 2026-09-27. Nothing is applied, nothing is exported, and nothing has been
run.** The canonical heightmap (`0d9b5f1e…`) and everything under the source root are untouched. This revision was
written without a shell, so **no number in the "after" columns below is measured yet**: the design is complete as data
(`data/water_shape.json`), the generator that applies it to a copy (`tools/water_shape.py`) and its audit
(`tools/water_shape_audit.py`) are written, and one command produces every map, section and measurement this report
promises (section 9). Numbers marked **[plan]** are measured values already committed in
`docs/mechanics/WATER_BUILD_PLAN.md`; numbers marked **[design]** are targets; **[run]** means the tool measures it.

The plan this carries out is `WATER_BUILD_PLAN.md` Phase B: items 1, 3 and 4's *shape* (rivers and lake terrain, the
shallows, the seabed) as **one** heightmap revision and **one** staging export (decision 5). Materials, plants, coral,
grottos, caves, wrecks and docks are blocks (Phase C) and are not here.

---

## 1. What changes where, in one table

| Family | Where | What the player gets | Serves | Layer |
|---|---|---|---|---|
| **Meanders** | the major river's lower trunk (805-2240 m), Viltri's Path over the coastal flats (654-1298), Arrow Lake's outflow (12-262), three low-grade stretches of the Watering Hole outflow | loops on a sine-generated planform, pools on the outside of bends, point bars on the inside, cut banks where a bend swings into a terrace; the surface steps only at riffles (2-4 single steps close together), still pools between | decision 9, the owner's item 1 | heightmap |
| **Cascades and falls** | the tarn outflow, Peak Pond outflow, the steep last 340 blocks of the Watering Hole outflow, Viltri's Path's last 220 blocks to the sea | today's one-block step every 6-20 blocks gathered into short cascades with still plunge pools, and one 2-3 block fall on each at its steepest | decision 9, item 1 | heightmap |
| **The Viltri Ravine stream** | from a spring pool just below the pass at (878, 3842) down the sea half, about 570 blocks and on to the sea | an underfit stream 3 wide and at most 1.5 deep, cascading all the way, in a bed far too wide for it; the lake half stays dry | decision 4 (option B) | heightmap |
| **Lake beds** | all nine lakes | a wadeable littoral shelf (1 deep on its inner part, 2 on its outer) widest in the bays, a drop-off, a basin floor that plunges then flattens, humps (fishing marks), shoals to 1 deep as rest points, and keep zones left exactly as they are (Viltri's survey floor, Shrew's pit, Mesprit's grotto floor, Azelf's pit) | decision 8, item 1 | heightmap (the bed zones are handed to the paint and the skin) |
| **Tidal flats** | off Pallet, Route 1's west coast, the south strand to Sunset West | the one-block sheet broken into shore-parallel sand bars and runnels with rip channels; one lagoon behind a dry barrier bar with an inlet on the south strand | the owner's item 3 | heightmap |
| **The Fungal bar chain** | Pallet coast (985, 5233) to Fungal Isle | a staggered chain of sand bars; no run of 3-deep water over 30 blocks (the decision allows about 40) | decision 7 | heightmap |
| **The Relic reef platform** | Relic Island's south and west apron, 34-96 blocks out | a platform 3 deep at the islet grading to 12, six patch-reef knolls, a reef wall down to the old seabed (y35) | decision 7, WATER_PROPOSAL 3.2, item 3 | heightmap (coral is blocks) |
| **Skerries and sea stacks** | off the windward cliffs (10 skerries, 4 stacks) and the north-west coast (6, 2) | low rocks at y63-65 and stacks to y70-86 with a boulder skirt, 20-100 blocks out, for Wingull colonies | item 3 | heightmap |
| **First Cast's scour hole** | 4 blocks deep off the jetty's west end | open water under the rod (vanilla's treasure check likely fails on the one-deep flats) | item 3; a **proposed addition** | heightmap |
| **The seabed** | the four marine zones inside 0-8191 | OCEAN.md section 4's shelf, break, slope and basin, filled up to the profile with every erosion canyon carried through as a canyon; a ridge along the windward shelf break and one across the Frostwater Shelf | decision 6 | heightmap |
| **The margin's seamounts** | the five sites, all outside the heightmap | not shaped here: **owner question 1** | decision 6 | needs a decision |

Unchanged on purpose: the Tilpey outflow gorge under the Route 7 bridge (decision 9), the Sound and everything Pacifidlog
stands on, every crossing the ferry is the gate for, the islet, the towns, the roads, the Rift and Victory Road.

---

## 2. The rules the revision keeps (the audit checks each)

1. **Shape only.** Everything here is a height; nothing is a block. (`data/water_shape.json` principle P1.)
2. **Bit-identical outside the declared footprints**, column by column, the Rift's rule (P2).
3. **Nothing already placed moves (P3).** Never written: every town footprint plus 8, every route line plus 6, the
   Rift's region grown 24 **and every column the Rift sculpt changed** (read from the pinned pre-Rift file), Victory
   Road's band plus 32, the Route 7 bridge plus 16, the islet, the sea town, and three built water event sites (the
   First Cast jetty and Viltri's two platforms).
4. **Swim-rate invariance (P4).** The swim rule charges 4 a tick in water 3 or more deep and 1 in shallower
   (`data/blackout.json` `surface`). No sea column that is 3 or more deep today becomes shallower than 3, except inside
   a coast feature that declares new rest ground (the flats, the Fungal chain, the skerries). The seabed pass never
   raises anything above y59. So **every ferry line keeps exactly its swim rates by construction**, and the audit
   still walks each one.
5. **Lakes keep their level and shoreline (P5):** nothing at or above level - 1 changes, and nothing is raised to the
   level, so the wet area, the basin polygons, towns, routes and foliage all stay valid.
6. **Every river still drains end to end (P6):** no surface ever rises downstream; steps over one block only at the
   declared falls.

---

## 3. Rivers (item 1: "rivers that feel like they flow")

**Today [plan]:** every course is a straight canal, sinuosity 1.01-1.20 (a natural lowland river is 1.5 or more); the
surface drops one block every 20-120 blocks, evenly, so every reach is a still canal with a lip.

**The design.** Meanders follow a sine-generated curve (the shape real meanders take), laid over the old centreline and
kept inside the room the valley gives: the graded floodplain on the major river, the measured low ground (within 3
blocks of the water) elsewhere, never nearer than 4 blocks to anything protected, and tapered to nothing at each end of
a window so the joins are untouched. The abandoned channel is filled to one block above the old water (it reads as an
old channel scar, above the water, so it cannot leak). The new channel is cut to the reach's own cross-section, with
the thalweg shifted to the outside of each bend by 35% of the half-width.

Pools and riffles: every one-block step of the old surface is moved **upstream** to the nearest gather point, never
downstream (the water may be let down, never held above its old surface), so the surface is flat through each pool and
steps two to four times close together at each riffle. Pools are 1.4 times the reach depth (at most 3 more), riffles 0.6.

| Window | Course | Length | Grade [plan] | Width [plan] | Room | Sinuosity target [design] | After [run] |
|---|---|---:|---|---|---|---|---|
| `major_lower_trunk` | major_river_trunk | 1,435 | 0.0074-0.018 | 18-26 | floodplain 19-28 a side **plus the first terrace** | 1.2-1.5 | not measured |
| `viltris_path_coastal_flats` | lake_viltri_outflow | 644 | 0.0006-0.0092 | 7-10 | measured | 1.3-1.6 | not measured |
| `arrow_outflow` | arrow_lake_outflow | 250 | 0.0047-0.008 | 10-11 | measured | 1.3-1.6 | not measured |
| `watering_hole_outflow_upper` / `_middle` / `_lower` | watering_hole_outflow | 126 / 128 / 195 | 0.0076-0.0116 | 11 | measured | 1.2-1.5 | not measured |

| Cascades | Course | Stretch | Grade [plan] | Gathered every | Fall |
|---|---|---|---|---|---|
| `tarn_outflow_cascades` | ravine_head_tarn_outflow | 8-399 | 0.035-0.29 | 14 | 3 blocks at the steepest 40 |
| `peak_pond_outflow_cascades` | peak_pond_outflow | 198-543 | 0.04-0.2 | 16 | 2 blocks |
| `watering_hole_outflow_falls` | watering_hole_outflow | 968-1290 | 0.026-0.12 | 18 | 2 blocks (stops short of Sunset West's protected footprint) |
| `viltris_path_mouth_cascades` | lake_viltri_outflow | 1492-1706 | 0.047-0.19 | 16 | 3 blocks, at the coast |

**Why the major river cuts into its first terrace.** Its floodplain is 19-28 blocks a side [plan: `data/rivers.json`];
a sine-generated loop keeps amplitude to about a fifth of its wavelength, so the floodplain alone allows a sinuosity
of only about 1.15 on a 25-wide river [design estimate]. Letting the loops use the first tread (5-block riser) gives
the room for about 1.3 and leaves a cut bank wherever a bend swings into the terrace, which is what the plan asked for.

**What cannot be promised.** Minecraft water that is all source blocks does not move; a still pool looks still. The
flow is carried by the planform, the riffles and cascades where water really steps, and (Phase C) flowing water on the
riffles if proof P3 shows it holds.

**Finding (the plan said "the Watering Hole outflow's lower reach").** Its last 340 blocks are graded 0.026-0.12
[plan: `data/rivers.json`], too steep to meander; the meanders go on its three low-grade stretches upstream and the
lower reach gets cascades.

**Chain order (a deliberate change from WATER_BUILD_PLAN 3.4).** The plan put the river change at the start of the
heightmap chain (re-run `tools/grade_rivers.py`, then the sculpt, rescale, pads and Rift). This design applies it as a
final stage instead, like the lakes: below y145 the rescale is the identity and the sculpt kept river channels unchanged,
so a river column in the canonical file *is* the river cut, and one final pass is provably bit-identical everywhere else,
which re-running four stages is not. The cost: `tools/paint_maps.py`'s guard (the rivers' cut hash must equal
`heightmap.sculpted_from`) has to accept a water-shaped heightmap and read `derived/water_shape/rivers_revised.json`
(or its copy into `data/rivers.json`), a named change for the apply step.

---

## 4. The Viltri Ravine stream (decision 4, option B)

**Today [plan]:** the pass at (879, 3841), floor y135; the sea half falls to y68 over 570 blocks with no counter-rise
(grade 0.12); the lake half has a 9-block counter-rise, which is `SQ-G1-01`'s reveal.

**The design.** The thalweg is found as the lowest ground within 6 blocks of the axis every 2 blocks, smoothed; the
surface is one block under the lowest ground met so far (so it always has banks); a spring pool of radius 5, 2 deep, sits
8 blocks down the sea side of the pass; the stream is 3 wide and 1.5 deep, its steps gathered into cascades every
about 18 blocks with plunge pools, and one 3-block fall where it is steepest. From the axis's low end (554, 4270) it
follows the steepest non-rising ground to the sea (at most 320 blocks, and the tool stops if the sea is not reached).
The lake half is untouched (the audit's G7). When applied, `data/landmarks.json` `viltri_ravine` `water: never` becomes
`partial`, and **Codex checks `SQ-G1-01`'s wording** ("a river that no longer reaches the sea").

---

## 5. Lakes (item 1: "lakes that read as lakes, not step-down bowls")

**Today [plan, F2]:** every bed is a ramp of one-block terraces (78-92% of neighbouring bed columns level, the rest one
step, none two or more); no shelf, no drop-off, no structure; 4-16% wadeable; the deepest point 47-179 blocks from
anywhere to stand.

**The profile.** Shelf width comes from how enclosed the shore is (a bay gets the wide end of the range, a point the
narrow end). Inner 60% of the shelf 1 deep (wading, rest ground, weed beds), outer 40% 2 deep; then the drop-off to
`drop_depth` over `drop_width` blocks; then the basin floor, which maps the old ramp so it plunges near the drop-off and
flattens toward the deepest point (the deepest point keeps its depth), with ±1 block of low rolling noise. Humps rise to
3-6 deep; shoals rise to 1 deep with a crest of radius 5. Shoals are placed first where a dive needs one (Shrew,
Arrow), then greedily at the farthest water from anywhere to stand until every point is within the rung's budget.

**The budgets.** Unaided: a swimmer's first hit comes at 75 blocks of deep water, so every point within 30 of rest
(a 60-block round trip). Trained (Surf or Dive): 150, so within 60. Decision 1 keeps a trained diver from tiring
underwater; these are surface budgets.

| Lake | Level | Rung, stage | Shelf | Drop to | Keep | Structure | Wadeable before [plan] -> target | Farthest from rest before [plan] -> target |
|---|---:|---|---|---|---|---|---|---|
| Viltri | 103 | trained, S1-S2 | 8-24 | 10 over 5 | the survey floor core (28 deep, y75) | 1 hump; shoals as needed | 6.9% -> 15-40% | 72 -> 60 |
| Shrew | 106 | trained, S2 | 6-14 | 14 over 4 (walled) | the pit (40+ deep core, 51 at the bottom) | a shoal 26-34 from the pit's lip (the dive point); 1 hump | 6.6% -> 10-35% | 147 -> 60 (the pit itself excluded: it is the dive) |
| Arrow | 100 | trained, S3 | 8-20 | 12 over 5 | Mesprit's grotto floor (radius 12 round the deepest point) | a shoal 30-40 from the grotto; 2 humps | 4.2% -> 12-35% | 118 -> 60 |
| Marshy Marsh | 100 | trained, S5 | 12-40 | 8 over 6 | Azelf's pit (20+ deep core) | 8 drowned-forest humps on the shelf to 1 deep (root crowns) | 15.7% -> 20-45% | 108 -> 60 |
| Tilpey | 77 | trained, S6-S7 | 10-40; **24-48 on the north shore** (the Dive school) | 10 over 6 | — | the practice floor flattened to 25; 3 humps; sunken islands as needed | 3.6% -> 12-35% | 179 -> 60 |
| Peak Pond | 105 | trained, S4 | 8-20 | 8 over 5 | — | 1 hump (a fishing mark) | 15.9% -> 15-40% | 90 -> 60 |
| Watering Hole | 95 | trained, S7 | 6-16 | 6 over 4 | — | 1 hump | 14.2% -> 15-45% | 47 -> 60 |
| Mt Clay pond | 119 | **unaided**, S2 (the Wooper stop) | 6-18 | 8 over 4 | — | 1 hump | 8.8% -> 15-45% | 68 -> 30 |
| Ravine Head Tarn | 127 | trained, S4 | 4-12 | 8 over 3 | — | 1 hump | 10.5% -> 10-40% | 71 -> 60 |

Every lake also keeps at least half its water 9 or more deep, because the rosters' deep entries are cut at
`maxY = level - 8`. **All "after" values: not measured [run].**

**Bed zones for the paint and the skin.** Per lake, `derived/water_shape/zones/lake_<id>.png`: 1 shelf (sand), 6 shelf
in a bay (the densest weed beds), 2 drop-off (gravel and stone; the kelp band), 3 basin floor (clay: silt), 4 hump
(gravel, stone, boulders), 5 shoal crest (sand), 7 kept. `tools/paint_maps.py` would read these instead of its noise
(a named change for the apply); the skin (`cobblers_water_skin`, Phase C) reads them for seagrass, kelp and mud.

**Finding.** Viltri's sounding platform's staffs read **5, 6 and 7 deep** (`EARLY_ROUTES.md:138`). A shelf there would
make them false, so the platform's water is protected. Its z range is inferred from the keeper's position (1773, 3010)
and is **not verified** against `tools/route_events.py`; check it before the run.

---

## 6. The shallows (item 3: "give it real attention")

**Today [plan]:** off Pallet and the south coast the water is one block deep for 16 blocks, then a ramp (80-98%
wadeable within 16); the north and west drop to 4-7 deep at once. Nothing lives in any of it.

| Feature | Design | Numbers [design] | After [run] |
|---|---|---|---|
| **Pallet flats** (box x880-1720, z5240-5760) | three shore-parallel bars at 14, 32 and 50 blocks out, crests 1 deep (a few dry at "low tide"), runnels 2 deep between, rip channels 3 deep every 70-130 blocks; never within 16 of either Relic line | changes at most 2 down, 3 up | wadeable share in the band, columns, fill/cut: not measured |
| **Route 1 west coast flats** (x440-1060, z4380-5250) | two bars at 12 and 30 | as above | not measured |
| **South strand flats and lagoon** (x2256-4271, z5856-6760) | three bars; one lagoon 360 blocks long where the flats are widest: a dry sand barrier (crest y63) 44-56 blocks out, 8 wide, one inlet 8 wide and 3 deep, calm water 1-2 deep behind it; nothing within 48 blocks of the Sunset strait | | lagoon site and inlet: chosen by the tool, not measured |
| **The Fungal bar chain** | bars 24-36 long and 10-16 wide, crests 1 deep, flanks 1 in 3, alternately 3 blocks either side of the line; as many as it takes for no 3-deep run over 30 blocks and an unaided walk with warnings and no hit | today [plan]: 198 blocks, 160 of swimming, 122 deep, unaided knocked out after 124 | bars, runs, the walk: not measured |
| **The Relic reef** | a platform on bearings 150-330 (south and west), 34 to 64-96 blocks from the islet's centre, 3 deep at its inner edge to 12 at its outer, six knolls to 3 deep, a 5-block reef wall to the seabed; never shallower than 3, never under the islet | fill only | not measured |
| **Windward skerries and stacks** (x0-760, z2600-5200) | 10 skerries (radius 4-9, top y63-65), 4 stacks (y72-86, near-vertical sides, a boulder skirt at y60-62), in water 3-12 deep, 20-100 from land, 60 apart, none within 48 of a gate line | | placed sites: not measured |
| **North-west skerries** (x300-1000, z1400-2600) | 6 skerries, 2 stacks | | not measured |
| **First Cast's hole** | radius 4, 4 deep at the centre, off the jetty's west end; deepens only | **proposed addition** | not measured |

The seabed pass stays out of the Pallet-Relic-Fungal water entirely (box x0-1760, z5000-5900) so these features are
the only hand on it.

---

## 7. The seabed (decision 6, OCEAN.md section 4)

**The profile per zone [design]:** a shelf from `shelf_start_y` to y46 over the zone's width, the break to y28 over 80,
the slope to y18 over 400, the basin to y10 over 600, then y10. Zones blend over 128 blocks.

| Zone | Shelf starts | Width | Why |
|---|---:|---:|---|
| Frostwater Shelf | y58 | 240 | broad cold shelf, kelp forest |
| Windward Sea | **y56** | 160 | narrow: the windward coast keeps its 4-7-deep drop at the shore |
| Eastern Reach | y58 | 320 | the sea lane |
| Southern Shallows | y59 | 400 | the warm coral shelf |

**Fill to the profile, canyons kept.** Where the profile is higher than today's seabed the pass fills up to it; every
erosion channel (at least 3 blocks under its 32-block surroundings) is carried through the fill as an incision of the
same depth, so the canyons survive as canyons. Never above y59; never a column already under 4 deep; nothing within
16 blocks of shore; a 96-block feather at every exclusion.

**Excluded:** the Sound (x6700-7700, z4400-7400: Pacifidlog's shelf and the Sound wreck's 32-39-deep hole), the
southern home waters, every coast feature plus 32, every lake basin, every river course plus 24, and **the ferry
straits plus 64 (owner question 2)**. The windward deep band (256+ from land) keeps its water under y36 wherever it
was, so the Windward Sea's deep entries (`maxY 40`) still have water to spawn in.

**Ridges:** along the windward shelf break (40 blocks past the shelf, 60 wide, 10-20 above the slope, crest capped at
y50, gaps where noise is low); across the Frostwater Shelf on a line drawn from OCEAN.md's description (review it on
the overview map: it is **not** measured).

**Findings.**
- **OCEAN.md contradicts itself.** It says both "where the planned shelf is shallower than the imported surface, the
  pass fills up to it" and "where the imported surface is deeper than the profile, the pass keeps the imported
  surface"; read literally these cover the same columns. Its per-zone medians (Southern Shallows y24 to y51) show
  filling was meant, and this design fills, carrying the canyons through.
- **OCEAN.md's shelf starts at y60, 2 deep.** Written before swim fatigue, it would lay a strip of shallow-rate water
  along every coast and move every crossing. This design starts at y59 or deeper.
- **Every seamount is outside the heightmap** (owner question 1), and the trench is blocks, postgame.

---

## 8. The crossings (WATER_BUILD_PLAN 11.1), before and required after

Walked by the audit on the copy with `data/blackout.json`'s constants at 5 blocks per second: a plain walk, a walk
with Slowness counted, and a walk that rests on every stretch of rest ground 6 blocks or longer. A gate must knock out
both an unaided and a trained swimmer under the plain and the resting walks.

| Crossing | Before [plan] | Required after | How it is held |
|---|---|---|---|
| Pallet beach to Relic (C3) | 71 swim; unaided arrives exhausted, no hit | no hit, unaided and trained | outside every feature; P4 |
| First Cast jetty to Relic | 113 swim; first hit 8 short | still a row: a hit or worse unaided | the Relic corridors are excluded; the hole only deepens |
| Pallet coast to Fungal Isle | 160 swim; unaided knocked out after 124 | **no hit unaided, with warnings; no 3-deep run over 40** | the bar chain |
| First Cast jetty to Fungal Isle | 184 swim; knocked out after 130 | reported | — |
| The Sound narrows z6100 / z6300 / z6500, dunes to the Long Isle | 65 / 137 / 96 / 84 swim | unchanged, depth for depth | the Sound is excluded from every pass |
| Pacifidlog's jetty to the square (C3) | knocked out after 134 / 228 | gate | the Sound is excluded |
| Eastern dunes to the Jungle Isle | knocked out after 116 / 191 | gate | P4; strait excluded from the fill |
| Sunset West's south pier to the Sunset isle (C3) | knocked out after 117 / 192 | gate | P4; flats keep 48 off; strait excluded |
| Marsh country to Northgate | knocked out after 110 / 185 | gate | P4 |
| The Northlight packet (C3) | knocked out after 108 / 183 | gate | P4; the Frostwater ridge crest is capped at y50 |

**After: not measured [run].** The audit first checks that its walk reproduces the plan's numbers on today's heightmap
(hard for the four contract C3 lines, reported for the rest), so the walk is calibrated against measurements it did not
make.

---

## 9. How to make the maps and numbers (one command each)

With the canonical heightmap at the source root (`C:/Users/wnd/Documents`), no server needed, nothing written outside
`derived/`:

```
python tools/water_shape.py --source-root C:/Users/wnd/Documents
python tools/water_shape_audit.py --source-root C:/Users/wnd/Documents
python -m pytest tests/test_system_contracts.py
```

`tools/water_shape.py` writes, under `derived/water_shape/` (gitignored, reproducible):

- `land_8k_16_rescaled_b145_pads_rift_water.png`, the copy, and `manifest.json` (its sha256, the features);
- `REPORT.md` and `report.json`: every measurement in this document's "after" columns, the design's own verdicts, cut
  and fill per feature, columns held off by protection;
- `maps/lake_<id>.png` (before, after, bed zones), `maps/river_<course>.png`, `maps/viltri_ravine_stream.png`,
  `maps/coast_southern_coast.png`, `maps/coast_pallet_and_relic.png` (the flats and the reef),
  `maps/coast_fungal_chain.png`, `maps/coast_windward_skerries.png`, `maps/coast_north_west_skerries.png`,
  `maps/seabed_overview.png` (1 px = 8 blocks, exclusions outlined, the Frostwater ridge line drawn);
- `sections/<id>.png` and `sections/sections.csv`: the 18 cross-sections in `data/water_shape.json` `sections`
  (through every lake's deepest point, the flats, the Fungal line, the reef, three shelf profiles), river long profiles,
  the stream's long profile, and a fatigue trace for every crossing, before and after;
- `rivers_revised.json` (the courses as paint would read them), `zones/` (the bed zones), `changed.npy`, `owner.npy`.

`tools/water_shape_audit.py` writes `derived/water_shape/audit.json` and exits non-zero on any failure.

**Scripts still needed** (none is written): `tools/paint_maps.py` reading the lake zones and the revised river courses,
and accepting a water-shaped heightmap in its guard; a world verify for the water after a staging export (every lake
and river wet where painted, no water outside it: WATER_BUILD_PLAN 3.5's "in the world" step); the independent tests
of this audit (a test author's).

---

## 10. What the audit checks (`tools/water_shape_audit.py`)

It never reads the generator's plan or report; it derives every footprint and expectation from the design file and the
committed data, and compares the copy with the canonical file.

| Code | Check |
|---|---|
| A | the canonical file hashes to `data/world.json`; the copy to its manifest; the manifest is complete; the design file is the one used; no sample rewritten without changing its ground |
| B | every changed column is inside a declared footprint: river corridors (64 from the **original** centreline over each window), the stream's corridor, lake basins, coast boxes, the seabed's zones minus its excluded boxes |
| C | no changed column in a town footprint, on a road (4 either side), on a bridge span, in the Rift (region grown 24, and every column the Rift sculpt changed, read from the pinned pre-Rift file), over Victory Road's band, under the islet, or under a built water event site |
| D | swim-rate invariance: no sea column 3+ deep became shallower than 3 outside the rest-ground coast features; the reef never under 3 |
| E | per lake: wet area unchanged; nothing at or above level - 1 changed; wadeable share, farthest-from-rest and deep area against the targets; keep zones untouched; the lake changed |
| F | every course present; painted as `tools/paint_maps.py` paints: surfaces never rise, big steps only at declared falls, every station wet, each course ends where it should, no new leak; each meander's sinuosity measured on the result against its target; unchanged courses paint identically |
| G | the stream starts at the pass, ends at the sea, drains, steps big only at its fall; the ravine's lake half untouched |
| H | seabed fill only, never above y59, never on a column shallower than 4; the windward deep band keeps its deep water |
| I | the walk calibrated against the plan on today's heightmap; every gate knocks out under the plain and resting walks; Relic as decided; Fungal crossed with no hit and with warnings; the Sound unchanged |
| J | something changed at all; every family, flat, skerry field, the reef and the chain changed something |

**Fail closed:** a missing file, a hash mismatch, a partial copy, a crossing with no water on it or a check with
nothing to check is a failure. This is the implementer's audit; its independent tests come later from a different agent.

---

## 11. What needs the export: all of it

Every piece here is shape, and reaches the world only through an export. **Nothing is worked around with blocks.**

**The staging export, `cobblers-dryrun12`** (REEXPORT.md "Dry run", with this revision; the owner approves step 4 and
nothing touches the live world):

1. The owner reviews the maps and `REPORT.md`, and answers section 13.
2. `python tools/water_shape.py --source-root C:/Users/wnd/Documents`, then `python tools/water_shape_audit.py
   --source-root C:/Users/wnd/Documents`: CLEAN.
3. `python -m pytest tests/test_system_contracts.py` (on today's heightmap: C3 must pass before and after).
4. **On a branch, owner-approved:** `python tools/water_shape.py --source-root C:/Users/wnd/Documents --apply`. It
   refuses unless the audit passed this exact copy; it copies the file beside the canonical one (never over it) and
   repins `data/world.json` with `heightmap.water_shaped_from`.
5. After the apply: `data/rivers.json` from `derived/water_shape/rivers_revised.json` (the courses and the stream);
   `data/landmarks.json` `viltri_ravine` `water: partial`; the paint change (section 9) and `python tools/paint_maps.py`;
   then, as WATER_BUILD_PLAN 3.4 lists, `cell_stats.py --write-cells`, `region_measure.py --write`,
   `measure_towns.py` (0 drift expected: no footprint moves), `build_routes.py` (no new water crossing), `waterways.py`,
   `compile_spawns.py`, the visibility re-measure (already stale), and `python -m pytest tests/test_system_contracts.py`
   again on the new heightmap (C3 walks the real ground now).
6. `python tools/heightmap_check.py C:/Users/wnd/Documents/land_8k_16_rescaled_b145_pads_rift_water.png`: 0 tears.
7. `python tools/reapply.py prepare --source-root C:/Users/wnd/Documents --server-dir C:/Users/wnd/Documents/github/cobblers-server`: 0 problems.
8. Process and port check, then take the coordination lock (`C:\Users\wnd\Documents\github\.cobblers-server-agent.lock`),
   server stopped.
9. `python tools/reexport.py --source-root C:/Users/wnd/Documents --old-world <the staging world cobblers-dryrun11, for
   its seed and settings; never the live world> --out-dir <staging dir, created first> --name cobblers-dryrun12
   --world-file <a staging .world path, never cobblers-10240.world> --paint build/paint/manifest.json`; check 484
   region files and `seed_match: true`. Whether `--world-file` may be omitted for staging is not verified.
10. `python tools/reapply.py carry --rehearsal --old-world <cobblers-dryrun11> --world-dir <dryrun12>`, then
    `install --world-dir <dryrun12>`; watchdog off (`max-tick-time=-1`); boot at `-Xmx16G`;
    `python tools/reapply.py run --server-dir <server>`; stop; copy the world; `python tools/reapply.py audit`; watchdog
    back on.
11. The water verify (to be written, section 9) on the stopped copy; then the owner's flight.

The live world gets it only at the live re-export, which stays blocked on STATE's three items; this adds no blocker
but adds content that exists only on staging until then.

---

## 12. Risks

- **Nothing has run.** The generator and audit are written but not executed; the first run will find bugs, and some
  targets (sinuosity where the valley is tight, the Mt Clay pond's 30-block budget, Tilpey's 60) may not be met with
  the room there is. The audit fails honestly in that case; the fix is in the data, not the audit.
- **Every placed thing that seats on water ground moves with it** at the re-apply: the First Cast jetty and Viltri's
  platforms are protected, but lake docks, the Viltri piers and any Phase C site must be sited on the revised ground.
- **Paint.** New land (skerries, stacks, the barrier bar, dry bar crests) has no coast class and would paint as the
  preset's default; the paint change must give it stone, gravel and sand.
- **Leaks.** The river pass holds a lip at the water's level beside every new channel column and the audit counts dry
  columns below adjacent water before and after, but no in-game water check exists yet (section 9).
- **Distant Horizons and the client cache** must be cleared after the export, as for every export.
- **The Frostwater ridge line and the Viltri sounding box are drawn, not measured**; both are for review on the maps.
- **Run time and memory.** The full map is held as int16 and uint8 arrays (about 0.6 GB) and the distance fields are
  iterated in numpy; expect minutes, not seconds.

---

## 13. Owner questions (only where it is genuinely close)

1. **The margin's seamounts.** All five sites are outside the 0-8191 heightmap; the export fills the margin from a
   blank image. (A) a margin relief image beside the heightmap, pinned in `data/world.json` and read by
   `tools/worldpainter/export_world.js` in place of the blank (recommended: it is still shape, and it rides the same
   export); (B) a block pass after the export, about 3 million blocks each; (C) leave the margin a plain until the
   postgame. Decision 6 asked for the full scope, so (C) would be a change to it.
2. **The ferry straits: keep them deep, or fill them with the shelf?** Filling the Southern Shallows to OCEAN.md's
   profile would take the Sunset strait and the Jungle Isle's water from 20-37 deep to about 5-8. The swim rates would
   not change (P4), so the gates hold either way; the difference is how the strait looks from the shore. The design
   keeps them deep (dark water reads as a gate).
3. **First Cast's scour hole.** Not in the plan; it gives the rod open water. Keep or drop.
