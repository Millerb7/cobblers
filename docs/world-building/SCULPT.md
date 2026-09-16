# Terrain refinement: coasts, massifs, volcano

**Status: sculpted and repainted 2026-09-15; not exported.** The design is `data/sculpt.json` and the tool
`tools/sculpt.py`.

## How it was done

These are local brushes on the current terrain, not a regenerated heightmap.

`tools/sculpt.py` reads the river-cut heightmap and applies feathered, masked brushes. It writes the result as
`land_8k_16_sculpted.png`, which `world.json` now imports (`heightmap.sculpted_from`). The chain is:

> authored heightmap → river cut → sculpt → WorldPainter

**Why not the WorldPainter GUI.** The export pipeline rebuilds the WorldPainter project from the heightmap on
every export. A hand sculpt inside the `.world` would be lost at the next export, and the river grading, paint,
foliage and sightline tools would never see it. The brushes are data instead, and every tool reads the same
terrain.

**What stays untouched:**
- **Unbrushed columns:** written back bit-identical.
- **Lake basins:** 0 columns changed.
- **River water:** 10 raw changes, all under 0.003 blocks.
- **Settlements:** inscribed circles 0 changed.
- **The built hometown area:** 0 changed.

Overall: 19.4 million columns touched; 13.7 million changed by half a block or more.

## 1. Coasts

### Measured before (`tools/coast_measure.py`, 2,301 profiles normal to the shoreline)

**Every coast had the same profile:** a straight ramp at about 1 block of rise per 3.5 horizontal, running
from about y51 on the seabed to y95-100 some 150 blocks inland.

| Measure | Value |
| --- | --- |
| Run per block of rise over the first 4 blocks | p10 / median / p90: 2.7 / 3.5 / 4.5, with every region's median between 3.0 and 3.5 |
| Beach-width grade (1:8 or flatter) | 1% of the coast |
| Steeper than 1:2 | 0.5% |
| Distance to 3 blocks deep | median 11 blocks |
| Distance to 8 blocks deep | median 29 blocks |

**The terracing.** It is not in the 16-bit heightmap.
- The stepping index (1-block against 9-block slope) is under 0.07 in 99% of coastal windows. Values on 8-bit
  levels are 0.4%, the same as inland.
- It is the uniform ramp turned into blocks: in the exported world every sampled coast rose one block every 2-4
  blocks (median 3), over and over, for 30-50 blocks of rise.
- So the cure was grade variation plus a zero-mean micro-relief (under a block on beaches, 0.9 elsewhere) that
  breaks the metronome. It was not smoothing, which would have flattened the coast.

### Classes

Classes are driven by the terrain, not assigned by hand. Each shoreline sample carries four features:
- **Exposure:** the prevailing wind from 250° (west-south-west, off the open ocean) against the seaward normal,
  times open-water fetch.
- **Shape:** land share within 256 blocks.
- **Hardness:** region class, plus hinterland relief (the height 200-500 blocks inland, above the ramp's y100 top).
- **River mouths:** distance to the nearest mouth.

Classes are smoothed along the coast, and profiles blend between them.

| Class | Rule (`data/sculpt.json` coast.rules) | Coast | Profile |
| --- | --- | ---: | --- |
| Estuary | within 200 blocks of a river reaching the sea | 3.6 km | Mud and clay flats: a 16-32 block berm, 1:20-1:28 up to 2-3 blocks, a shelf out to 2-3 deep |
| Cliff | exposed headland, or hard ground with high relief behind | 4.9 km | A 10-26 block face that comes and goes along the coast, talus at its foot, deep water |
| Rocky shore | hard ground, or exposed and not a bay, or high relief on medium ground | 12.9 km | A 1:1.8 stone and gravel bank, roughened, dropping fast to 9 deep |
| Beach | a bay, or soft ground that is bay-like or sheltered | 30.4 km | A 6-18 block berm, a 1:8-1:15 strand to 3-5.5 blocks, a sand shelf 1:12-1:20 to 3.5-6 deep |
| Grassy shore | everything else | 21.8 km | The first rise cut back to 1:5-1:7, a thin gravel strand, a 1:8-1:11 shelf |

Where they fall:
- **Beaches:** the eastern dunes, Sunset Isle, the south coast, the Jungle Isle and part of Pallet.
- **Cliffs and rocky shore:** Frostpeak Point and the exposed north-west and west coasts (Viltri, part of Pallet,
  Long Isle's rocky middle).
- **Estuaries:** the Tilpey outflow (the major river's water), the Watering Hole, Marshy Marsh, Viltri, Peak Pond
  and the tarn.
- **Grassy shore:** the Pine Isles and Northgate.

Sand now follows the grade:
- `tools/paint_maps.py` paints shore materials by class (`build/sculpt/coast_class.png`): beach sand only on the
  graded strand and in shallows to 7 deep, mud and clay on estuaries, gravel and stone on rocky shores, talus
  under cliffs.
- Cold coasts take gravel.
- Without the class map the old uniform rule applies.

### Measured after

| Class | Run per rise over the first 4 blocks (p10 / median / p90) | To 3 deep | To 8 deep |
| --- | --- | ---: | ---: |
| Beach | 8.3 / 11.5 / 14.5 | 49 | 83 |
| Estuary | 2.3 / 20.4 / 27 (the low end is river banks, which are protected) | 49 | 89 |
| Grassy shore | 4.0 / 5.3 / 7.0 | 31 | 57 |
| Rocky | 1.5 / 1.8 / 2.3 | 5 | 13 |
| Cliff | 0.2 / 0.5 / 2.7 | 8 | 14 |

Overall:
- **Beach-width grade:** 43% of the coast (was 1%).
- **Steeper than 1:1.5:** 12% (was 0%).
- **To 3 deep:** median 33 blocks (was 11).
- **To 8 deep:** 61 (was 29).

## 2. Massifs and volcano

**Measured before (`tools/massif_measure.py`):**
- **Clipped summits:** 409,494 columns flat at y200.
- **Mt Vessu:** a plateau about 480 by 500 blocks.
- **Tri Peaks range asymmetry:** the wrong way for the landscape. Crest-to-y130 sections had the west-south-west
  flank at grade 0.149 against 0.080 east-north-east.
- **Cones:** three clipped discs (240, 180 and 100 blocks across) and a 7-block bowl, which is really a 260-block
  hollow rimmed 8-10 blocks high.

### Which way each massif faces, and why

| Massif | Steep face | Why |
| --- | --- | --- |
| Tri Peaks, Mt Vessu, Mt Clay | east-north-east | The lee of the prevailing wind, where the Merian cirque and the Glacial Tear already cut in (glaciers form on the lee, shaded side), and toward the Rift. The west-south-west flank runs long to the Viltri uplands |
| Frostpeak | north-west | It faces the storms off the open sea above the northern strand, and slopes gently south-east to the mainland |
| The cones | west-south-west | That side takes the wind; ash falls downwind, so the eastern flanks are long and gentle |

### What changed

- **Asymmetry.** The upper massif shifts toward its steep face along a tapered weight: up to 140 blocks for the
  Tri Peaks range, 55 for Frostpeak and 25 for the cones. The steep flank compresses and the other stretches.
  - Tri Peaks sections now run east-north-east 0.110 against west-south-west 0.092 (was 0.080 against 0.149).
  - Frostpeak, median slope by facing: north-west 0.36 → 0.39, south-east 0.32 → 0.26.
  - The great cone, by facing: west-south-west 0.39 → 0.34, east-north-east 0.48 → 0.25.
- **Height along the range.**
  - Clipped plateaus are broken by a ridged lowering of up to 24 blocks, deepest in the saddles.
  - A designated summit, Mt Vessu at (1860, 770), stands at y200.
  - Everything above y180 more than 150-300 blocks from it is compressed toward y180.
  - The other summits now top out at y191-196. The next-highest ground, y197, is the protected shoulder of Surge's
    town and the Scar.
  - Clipped columns fell from 409,494 to 24,687. Most of those are the two deliberate flats below.
- **Deliberate flats.**
  - **The Scar:** pressed to a scraped table at y194 (73,133 flat columns), just below the true summit.
  - **The Frostpeak shrine:** keeps a levelled platform at y200 (9,941 columns).
- **Cliffs, scree and benches.**
  - Strata on smoothed height: cliff bands of 12-19 blocks where the slope is over 32°, benches of 20-32 blocks on
    12-26° ground. Both come in patches, never full rings, and stop below the summits.
  - Scree: presets paint gravel on the band just below where ground turns to bare rock, blackstone on the cones.
- **Volcano.** The cones' largest raise is 23 blocks and their largest cut is 73 (the caldera).

| Cone | Before | After |
| --- | --- | --- |
| Great cone (6100, 5520) | clipped disc at y200, 240 across | Stratovolcano: a crater 96 across with its floor at y174, rim at y200, flank to about y162 by 200 blocks out, breached to the east (downwind) with a lava channel |
| North-east cone (6560, 5170) | clipped disc at y200, 180 across | Lava dome: convex, y199 at the top, 190 at 60 blocks, steep-sided, five spines |
| West cone (5620, 5620) | peak y167-187 with a clipped spur to y200 | Cinder cone: a regular 32° cone from y189 with a 28-block summit crater (floor y180); the spur is cut to the plain at y145 |
| Eastern bowl (6672, 5508) | floor y127, rim 8-10 blocks higher | Caldera centred 38 blocks north at (6672, 5470): a flat floor 140 across at y104, steep walls, rim y148-154, about 46 blocks of wall. The rim sinks to the south, where the Mining Town keeps its ground |

## 2b. Hillside relief: contour rings (added 2026-09-15, second pass)

**The problem, measured.** From the air the whole landmass read as concentric contour rings. The source is not
stepped: the old terrace index stays at or below 0.07 in the 16-bit data. The cause is quantisation of a grade
that is too regular.

**The arithmetic.** A slope of grade `g` becomes a 1-block step every `1/g` blocks. Those steps run as rings wherever
the grade stays constant across a wide area.

`tools/terrace_measure.py` measures it three ways, over the whole map:

- **Regime:** 53% of land lies between 1:12 and 1:1.5, the grades that make visible rings, and it is in every region.
- **Rho:** `rho = |grad(fine) - grad(regional)| / |grad(regional)|` on that ground. Contours run as parallel rings
  near 0, wander above about 0.3, and break into spurs and gullies near 1.
- **Tread CV:** the variation of consecutive treads on the block surface, in 64-block windows. A regular ring field
  sits near 0.15.

**Options, evaluated before implementing.**

| Option | Arithmetic | Verdict |
| --- | --- | --- |
| Per-region grade multiplier (1:2 to 1:8) | Scales the fine and regional gradients alike, so rho and tread CV don't change: rings stay, only their spacing changes per region. It also moves ground by (m-1)·g·d: halving a 1:4 coast lowers ground 19 blocks, 150 blocks inland | Rejected: not local, and doesn't break rings |
| Low-frequency noise on the falloff | 2πA/L changes the grade. On a 2048-block crop, 3 blocks at 160-block spacing added up to 5 blocks of change and broke fewer rings than 2 more points of the chosen k | Rejected on measurement |
| Beach flats 10–20%, cliffs 5–10% | The brief's 1% and 0.5% were the pre-sculpt figures. Live, cliffs are already 6.8% at 1:1 or steeper, and flats under 1:20 are 2.4%. Flats on 10–20% of 74 km of shoreline convert 0.6–1.2 million columns, 2.4–4.8% of ring ground | Not done: doesn't reach the inland rings |
| **Relief proportional to grade, stretched down the fall line** | `A = k·g` gives `rho = 2πk/L` at every grade, so flats stay flat. Averaging along the fall line makes spurs and gullies, not knobs. Wavelengths are about 24–144 blocks (grid spacings 12, 24, 48), so the relief survives Distant Horizons' coarse LODs | **Chosen**, k = 10, capped at 2.5 blocks, soft-clipped at 2σ |

**Where it applies.** It fades out below sea+4..12, so the graded beaches stay as they were. It fades out on
grades over 0.7..1.0, so the cliffs keep their faces. It is exactly zero inside protected sites: footprints,
channels, lake basins and the hometown rectangle, with a 24-block feather.

**Noise normalisation.** The noise is normalised by a statistic of the noise alone, not of the whole map. So an edit
in one place changes the relief only near that edit.

**Results.**

| Whole map | Before sculpt | Sculpted | + relief |
| --- | ---: | ---: | ---: |
| rho median on ring ground | 0.093 | 0.146 | 0.401 |
| ring ground with rho over 0.3 | 10% | 18% | 65% |
| tread CV median (64-block windows) | 0.18 | 0.25 | 0.49 |
| windows with tread CV under 0.2 | 58% | 32% | 7% |
| terrace index p50 / p90 | 0.021 / 0.054 | 0.030 / 0.075 | 0.057 / 0.104 |
| terrace index share under 0.05 | 88% | 77% | 38% |

**Checked in the exported world** (ground read back from the region files):

| Crop | Tread CV median | Windows under 0.2 |
| --- | --- | --- |
| North mountains | 0.31 → 0.56 | 16% → 1.6% |
| Pallet lowland | 0.23 → 0.43 | 38% → 6.8% |

The terrace index means nothing on whole blocks; it reads 1.2–1.6 in both worlds.

**What the relief moves.**

- **Terrain:** the largest change is 4.9 blocks, and 99% of changes are under 3.4.
- **Lake basins and the hometown rectangle:** unchanged. River water: 10 raw columns under 0.003 blocks.
- **Paint:** bare ROCK went from 210,627 to 367,045 columns, as steep spur faces tip over the rock slope. That is
  0.35% of land.
- **Foliage:** 77,750 objects became 76,636.
- **Landmark sightlines:** Great Oak 20/37, Sentinel 26/81, Patriarch 68/155, Cherry Elder 61/160, Weeping Elder
  36/144.

**Not verified:** whether the rings stop dominating the view from y200. That needs a flight screenshot.

## 3. What the sculpt protects

- Every settlement: the inscribed circle of its footprint plus 32 blocks, feathered over 24 blocks on coasts and
  60 in the mountains.
- Landmark-tree glades (plus 8 blocks) and river channels (plus 12).
- Lake basins get only the 16-block `lake_margin_blocks`. That margin is also added to every protected feature
  above, so a settlement circle's effective margin is 48.
  - The added margin covers the corners of the square footprints. Across all 23 footprint rectangles, the largest
    change is 0.22 blocks (Mining Town), and no column changed by half a block.
  - Rectangles were tried and dropped: a feathered rectangle leaves a square mesa on a sloping coast.
- The built hometown area (x1376-1567, z4976-5391), chunk-aligned, so its chunks can be carried from the live world
  into an export unchanged (`tools/transplant_chunks.py`).

## 4. Not verified

- Everything was measured in the heightmap. Nothing sculpted has been exported or seen in game yet.
- The hillshade previews (`build/sculpt/preview_*.png`) show faint hatching where the massif shift resamples. It
  measured at 0.07 → 0.074 blocks of high-frequency relief, with 1% more columns rounding differently.
- Whether the cliffs, cones and beaches read well from the ground is the flight's question.
