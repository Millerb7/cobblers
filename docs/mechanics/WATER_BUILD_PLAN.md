# The water build plan: rivers, lakes, shallows, the Dive sea, wrecks, docks, the ferry and fishing

**Status:** plan, 2026-09-27, for the owner. **Nothing is built by this document, and no server or world was read to
write it.** Every measurement is on the canonical heightmap (`0d9b5f1e…`, `tools/ground.py`, rounded; the islet and
the sea town's decks through `ground.for_settlement`) and committed data. It turns `WATER_PROPOSAL.md` and `WATER_MAP.md`
into a build order, says for each piece whether it is **heightmap and an export** or **blocks**, names the audit that
fails closed for it, and answers the two open questions (the ferry, fishing for prizes).

The owner's order is kept: 1 rivers and lake terrain, 2 lake content, 3 shallows and shore water, 4 the Dive sea,
5 shipwrecks and Rift debris, 6 docks and fishing. **Each part is reported to the owner before it is built**
(section 10).

**Tags.** [V: source] verified, with where. [M] measured for this plan on the heightmap, read-only (method in the
appendix). [A] assumed: not run, not read from a jar.

Stages: **S0** before Brock, **SN** after gym N, **L** the League, **P** postgame. Caps 20/25/30/35/40/45/50/55.

---

## The answer in one table

| # | Item | Layer | Needs an export? | Buildable on staging now? |
|---|---|---|---|---|
| 1 | Rivers and lake terrain | **Shape in the heightmap** (river planform, pools and riffles, cascades, lake shelves, drop-offs, humps, the Viltri Ravine stream). **Skin as blocks** (weed beds, silt, structure, flowing riffles) | **Yes: flagged.** The shape lands on staging only through a fresh staging export, and in the live world only at the live re-export, which is blocked (`docs/STATE.md` "What is blocked") | The design, its offline audits and a proof rig for flowing riffles. Not the shape |
| 2 | Lake content | Blocks (grottos, air chambers, hooks, finds), NPCs and functions | No, but it sits on item 1's lake beds, so it is built after the water export | Mechanism proofs only (a grotto air chamber, a visible-light hook, remounting in deep water) |
| 3 | Shallows and shore water | **Shape in the heightmap** (bars, flats, skerries, the Relic reef platform); **blocks** for everything that lives on it (kelp, seagrass, coral, rock pools, beached wrecks, a sea cave) | **Yes for the shape: flagged** | Rosters (data), the swim-budget audit, a sea-cave proof |
| 4 | The Dive sea | **Seabed shape in the heightmap** (OCEAN.md section 4's pass); **blocks** for the trench (below the heightmap's y10 floor), every cave, the sunken Pallet fragment, the forge ruin, the coves | **Yes for the seabed: flagged** | Template work (flooding, capture) and a surfacing-cave proof |
| 5 | Shipwrecks and Rift debris | Blocks: a seeded scatter seated on the seabed | No, but it seats on item 4's seabed | The kit and its transforms, offline |
| 6 | Docks and fishing | Blocks (docks, as `tools/bridges.py` builds a bridge); data (fishing spawns); functions (the exchange) | No | Docks on shores the water export does not reshape; the fishing and exchange proofs |

**The ferry:** the new fatigue rule has already made it a real gate for every swimmer, trained or not, on five of its
six lines. Exhaustion does not need to get harsher. What decides whether the ferry gates anything is **boats**: a
boat is ridden, so it is exempt, and a boat crosses every strait from S0 unless boats are shallows craft. With boats
as shallows craft (WATER_PROPOSAL option C), the ferry is the only way across the far straits until a player rides a
water Pokemon, about S1. With boats unrestricted it is decoration (section 11).

**Fishing for prizes:** yes. The exchange side is the casino's mechanism exactly: a per-player score, a dialogue
counter whose options are gated per player, and a function that gives the prize. The new part is the earning side,
and the recommended form is a hand-in at the counter (section 12).

---

## 1. Read first: what the 2026-09-27 fatigue rule changes

The owner changed surface exhaustion on 2026-09-27 (commit `2262aa3`, `data/blackout.json` `surface`): every swim in
any water builds fatigue, four times as fast where the feet's block and the two under it are water. The constants,
read from `data/blackout.json` and the generator (`tools/blackout_pack.py` `surface/tick`) [V]:

| Swimmer | Deep water (3+ blocks) | Shallow water (2 deep) | Recovers |
|---|---|---|---|
| **Unaided** | warned at 5 s (25 blocks at 5 blocks per second), Slowness at 7.5 s, exhausted at 11 s, **first hit at 15 s (75 blocks)**, knocked out at 18 s (90 blocks) | four times as long: first hit at 60 s (300 blocks) | 2 a tick on land, wading (on the bottom with the eyes out, water 1 deep) or riding: 30 s from collapse to rested |
| **Trained, with a partner** (Surf or Dive, the ladder's qualification) | half the rate: warned at 10 s, **first hit at 30 s (150 blocks)**, knocked out at 33 s (165 blocks) | first hit at 120 s | the same |
| **Riding anything** (a Pokemon or a boat) | none: riding recovers | none | — |

A "hit" is the water ladder's half-health hit; the second from full health knocks the player out [V: EXP-042 run 1].
Slowness probably does not slow an unaided swimmer: in vanilla water movement, the movement-speed attribute only
counts in proportion to `water_movement_efficiency`, which is 0 without Depth Strider [A: reasoned from vanilla, not
run]. `data/blackout.json`'s "about 70 blocks" assumes it does. The tables below give both where it matters. For a
Dive-trained player (efficiency 0.5, `dive_swim_efficiency`) it does count.

### Finding F1: fatigue now caps Surf and Dive underwater, at 30 seconds

The rule counts a swimmer whose eyes are at the ladder's depth as deep water, in any water, and only halves it for a
trained player [V: `tools/blackout_pack.py` `surface/tick`, the `bo.deep` line; `tests/test_surface_exhaustion.py`
`test_eyes_at_the_ladders_depth_count_as_deep_water` and `test_deep_water_uses_the_deep_rate_and_a_qualified_player_halves_it`].
So:

- a **Surf** player has 61 s of air (EXP-042) but collapses from fatigue after **30 s** of continuous swimming,
  surface and dive together;
- a **Dive** player has unlimited air (EXP-042 session 3 held it flat at a floor for over two minutes) but under the
  new rule is **knocked out at 33 s** of continuous swimming. At Dive's 10 blocks per second that is about 300 blocks.

This contradicts `DEATH_AND_WIPE.md` ("Dive provides unlimited air"), `WATER_MAP.md` section 0 and every lake-floor
and Dive design built on them. It was not in the owner's stated intent ("a new player should struggle with water").
It decides the size of every site in items 2 and 4, so it is **decision 1**, and nothing underwater is sized until it
is answered. Sections 4 and 6 give each site's budget under both readings.

### Finding F2: the lakes are step-down bowls, measured

Every lake bed is a ramp of one-block contour terraces [M]: depth rises about half a block for every block from
shore, 78-92% of neighbouring bed columns are level and the rest are one-block steps, and not one pair differs by two
or more. There is no shelf, no drop-off and no structure. The wadeable margin (water 1 deep) is 4-16% of each lake.

| Lake | Level | Deepest | Median depth at 1-4 / 5-8 / 9-16 / 17-32 / 33-64 / 65+ blocks from shore | Wadeable | Level neighbours / 1-step | Deepest point to nearest rest |
|---|---:|---:|---|---:|---|---:|
| Lake Viltri | 103 | 28 | 1 / 2 / 4 / 8 / 17 / 25 | 6.9% | 78.5 / 21.5% | 72 |
| Shrew Lake | 106 | 51 | 1 / 2 / 3 / 6 / 17 / 39 | 6.6% | 80.9 / 19.1% | 147 |
| Arrow Lake | 100 | 45 | 1 / 2 / 4 / 8 / 17 / 36 | 4.2% | 79.1 / 20.9% | 118 |
| Marshy Marsh | 100 | 37 | 1 / 1 / 2 / 4 / 8 / 13 | 15.7% | 88.1 / 11.9% | 108 |
| Lake Tilpey | 77 | 26 | 1 / 2 / 4 / 7 / 13 / 25 | 3.6% | 92.3 / 7.7% | 179 |
| Peak Pond | 105 | 19 | 1 / 1 / 2 / 4 / 8 / 15 | 15.9% | 90.0 / 10.0% | 90 |
| Watering Hole | 95 | 13 | 1 / 2 / 3 / 5 / 9 / 13 | 14.2% | 87.7 / 12.3% | 47 |
| Mt Clay pond | 119 | 25 | 1 / 2 / 3 / 7 / 14 / 23 | 8.8% | 82.2 / 17.8% | 68 |
| Ravine Head Tarn | 127 | 22 | 1 / 2 / 3 / 6 / 13 / 19 | 10.5% | 83.3 / 16.7% | 71 |

"Rest" is land or wadeable water. The last column is why F1 matters: a trained swimmer's whole budget is 150 blocks
of deep water, and the deepest point of four lakes is 108-179 blocks from anywhere to stand.

### Finding F3: the Viltri Ravine is dry on purpose

`SQ-G1-01` "Where Viltri Used to Run" sends the player down the dry ravine to the Mouth of Viltri; its reveal is
that the ravine "is an old watercourse whose elevation no longer permits Lake Viltri to drain through it"
[V: `docs/story/SIDEQUESTS.md:54-65`]. The gravel the owner saw is `tools/paint_maps.py` painting every dry ravine's
axis as a 10-wide gravel floor [V: `paint_maps.py`, "dry ravines ... gravel floors"], which reads as a river bed with
the river missing. That is what the story wants, and it is also why it looks wrong. Section 3.2 measures it and gives
the option that serves both.

### Other findings

- **`docs/STATE.md` "Surface exhaustion (EXP-044)" describes the superseded rule** (distance bands from
  `tools/open_water.py`, warning at 20 s). The pack no longer reads that map. Corrected in this commit.
- **The experiment number is wrong in two places.** `WATER_PROPOSAL.md` (sections 4.1 and 9) and
  `docs/mechanics/README.md` call surface exhaustion EXP-043; it is `experiments/EXP-044-surface-exhaustion`. EXP-043
  is the casino's proposed prototype (`docs/research/CASINO.md`). The README row is corrected in this commit.
- **The Long Isle is swimmable unaided at one place.** `LONG_ISLE.md` D4 (2026-09-27) says the island "is no longer
  swimmable unaided". The narrows at z6100 are not: 65 blocks of swimming, only 38 of them 3 deep, fatigue peaks at
  716 of 1,200 (warned and slowed, no hit) [M]. Every other line to the island is lethal unaided.
- **Relic Island is swimmable from the beach, not from the jetty.** From the nearest Pallet beach (1101, 5410) it is
  71 blocks of swimming and the swimmer arrives exhausted but unhurt; from the First Cast jetty it is 113 blocks and
  the first hit lands about 8 blocks short of the islet [M]. `WATER_PROPOSAL.md` 4.1 called both "all shallows".
- **Bubble columns may be a player-built air source.** In vanilla an upward bubble column refills a player's air
  [A: vanilla behaviour, not run here]. Soul sand and water would then bypass the ladder the way Water Breathing did.
  Added to the proofs (section 10). The same column is a good visible hook if the ladder accounts for it.
- **Lakes meet dry channels below their level.** Below-level ground runs past every lake's painted basin (the
  outflow notches account for much of it) and 5-183 edge columns per lake have painted water beside a dry column
  below the level [M, section 3.5]. Whether any of them is anything but an outflow step is not checked; the item-1
  audit makes that check permanent.

---

## 2. Heightmap or blocks: the rule

The repository has already answered this twice, and the answer is the same for water:

- **Shape is a height.** Anything that moves the ground surface over an area goes into the canonical heightmap and
  reaches the world by an export. Precedents: the river cut (`tools/grade_rivers.py`), the sculpt, the pads
  (`tools/press_pads.py`), and the Rift, whose tool says why: *"The prototype built one stretch as a block pass. That
  cannot reach the live world without being re-applied after every export, and it cannot be what `tools/ground.py`
  calls ground"* [V: `tools/rift_heightmap.py`].
- **Everything that is not a height is blocks**: materials on top of the ground (the Rift skin), voids and overhangs
  (caves, the cavern, Victory Road), anything below the heightmap's y10 floor (the Windward Deep pit at y0,
  `tools/rift_deep.py`), objects (bridges, towns, wrecks), and one small bounded object whose ground the placement
  data carries (Relic Island's islet, a `ground` kind in `data/placements.json`).

For water there are three more reasons the shape cannot be blocks:

1. **WorldPainter fills the water from the heightmap.** Lakes are basin polygons filled to a level, rivers per-column
   level crops, the sea everything below y62 [V: `tools/paint_maps.py`]. A block pass that raises a lake bed must also
   delete water; one that lowers it must add water. The block pass would be fighting the export on every column.
2. **Every seated tool reads `tools/ground.py`.** A grotto mouth, a dive raft's anchor, a wreck, a dock pile all seat
   themselves on the heightmap. A bed changed by blocks would put every one of them in the wrong place.
3. **Spawn depths are computed from the heightmap.** The lake rosters' deep entries are cut at `maxY` = level - 8
   [V: STATE, "Every painted lake has a water roster"]. A bed that moved by blocks would move the spawns off the
   design.

**What an export costs.** A heightmap change reaches staging through a fresh staging export (`tools/reexport.py`,
REEXPORT.md "Dry run"; an agent can run it) followed by the whole re-application and audit, about 14 minutes of
export and one rehearsal (EXP-026 runs 3-5). It reaches the live world only at the live re-export, which is blocked
on the three items in STATE "What is blocked". **So every heightmap piece in this plan is flagged, and none of them is
worked around with blocks.** To pay that cost once, all of them go into one revision of the heightmap and one
staging export, "the water export" (decision 5).

**What a block pass costs.** A generated pack, a `tools/reapply.py` step (`prepare` fails closed on a pack no step
runs [V: `reapply.py` EXCLUDED]), an offline audit run by `prepare`, and a verify against a stopped world copy. It is
re-applied after every export, so a block feature built on staging now is not wasted, provided its tool seats itself
on the heightmap and its site is not reshaped by the water export.

---

## 3. Item 1: rivers and lake terrain

### 3.1 What exists

**Rivers** are graded and cut into the heightmap [V: `docs/world-building/RIVERS.md`, `data/rivers.json`]. They
descend correctly (no rise anywhere, 581 stations checked) and carry the right water, but they are drawn as straight
4-block routes: *"Composition: meanders, gravel bars, pools, bank detail. That is Axiom work"* is RIVERS.md's own
"Still not done". Measured from `data/rivers.json` [M]:

| Course | Length | Sinuosity | Drop | Width | Depth | What it looks like |
|---|---:|---:|---:|---|---|---|
| Major river trunk | 2,268 | **1.01** | 27 | 5-26 | to 7-9 | 19 vertices, 126 blocks apart: a straight canal down the Glacial Tear |
| Viltri's Path | 1,710 | 1.20 | 41 | 4-10 | 1.4-2.9 | the most varied; still straight segments |
| Watering Hole outflow | 1,308 | 1.12 | 33 | 10-16 | 3.1-3.2 | straight, steep |
| Mt Clay creek | 1,261 | 1.07 | 31 | 5-10 | 1.8-2.8 | straight |
| Peak Pond outflow | 545 | 1.04 | 43 | 5-9 | 1.8-1.9 | straight, steep |
| Tarn outflow | 401 | 1.04 | 65 | 4-6 | 1.5 | one step every 6 blocks |
| Tilpey outflow gorge | 352 | 1.05 | 15 | 22-32 | 9 | a straight gorge; the Route 7 bridge crosses it |
| Arrow, Shrew, Marsh, Tilpey inflow | 231-483 | 1.07-1.11 | 6-38 | 3-14 | 1.3-2.9 | short links |

A natural lowland river is 1.5 or more. The water surface drops in single one-block steps spread evenly along each
course, and each reach has one width and one parabolic bed. Minecraft water that is all source blocks does not move,
so every reach is a still canal with a one-block lip every 20-120 blocks.

**Lakes:** finding F2 above. Bed material is gravel and clay by noise, sand on a two-block bank [V: `paint_maps.py`].

### 3.2 The Viltri Ravine, measured

On the channel axis in `data/landmarks.json` `viltri_ravine`, with the floor taken as the lowest ground within 4 blocks
of each station every 4 blocks [M]:

- **The pass** is at (879, 3841), floor y135, 1,333 blocks from the lake end and 570 from the sea end.
- **Pass to the sea:** y135 to y68 over 570 blocks, **no counter-rise at all**. A grade of 0.12: a one-block drop every
  8-9 blocks, steep enough that water on it really flows.
- **Pass to Lake Viltri:** y135 to y76 over 1,333 blocks, with a worst counter-rise of **9 blocks** and 21 blocks of
  rises in all. Water from the pass cannot reach the lake without cutting through them, which is `SQ-G1-01`'s reveal
  and `RIVERS.md`'s 31.5-block cut on the original line.
- Near the lake the floor sits at y98-102 for about 150 blocks, just under the lake's level (y103); only the basin
  polygon keeps the lake's water off it. The item-1 leak audit checks this column by column.

Three options (decision 4):

| Option | What | Story | Recommendation |
|---|---|---|---|
| A. Dry, as written | Keep it dry. Replace the 10-wide gravel stripe with a bed that reads as abandoned: bleached gravel bars, rounded boulders, stranded driftwood and snags, a dry falls lip, the builder's worn stonework | `SQ-G1-01` unchanged | acceptable |
| **B. An underfit stream** | A spring pool at the pass and a narrow stream (2-4 wide, at most 1.5 deep) down the sea half only, 570 blocks of real cascades in a bed far too wide for it; the lake half stays dry and dressed as in A | Stronger evidence: a trickle in a valley cut by a river, cut off from the lake by the rise. `SQ-G1-01`'s wording ("a river that no longer reaches the sea") needs Codex's eye | **recommended** |
| C. A river from the lake | Re-route Lake Viltri's drainage through the ravine | Deletes `SQ-G1-01` and Viltri's Path, needs about 9 blocks of cut and a new outflow | rejected |

Option B is heightmap (a new course in `data/rivers.json`: source at the pass, graded to the sea, cut and painted) plus
the dry half's dressing as blocks. The landmark's `water: never` becomes `partial`.

### 3.3 What will be built

**Rivers: shape (heightmap).**
- **Planform.** Meanders where the valley floor has room and the grade is low: the major river's lower trunk inside
  its floodplain, Viltri's Path over the coastal flats, the Arrow Lake outflow, the Watering Hole outflow's lower
  reach. Target sinuosity 1.3-1.6, amplitude from the reach's width, never leaving the graded valley. Steep creeks and
  the Tilpey outflow gorge stay straight (the gorge carries the Route 7 bridge; `data/bridges.json` is not re-sited).
- **Pools and riffles.** The bed deepens on the outside of bends and at pools (up to 1.5 times the reach depth) and
  shallows over riffles. The water surface drops **only at riffles and cascades**, two to four single steps close
  together, with still pools between. That is where water moves, makes its sound and pushes a boat.
- **Cascades and falls.** On steep reaches (the tarn outflow, Peak Pond outflow, the Viltri Ravine stream) the drop is
  gathered into short cascades and one or two small falls over plunge pools.
- **Banks.** Cut banks on the outside of bends, point bars of sand or gravel on the inside, painted from the result.

**Lakes: shape (heightmap).** Every lake keeps its level and its shoreline (no column at or above level - 1 changes,
so towns, routes, foliage and the basin polygons stay valid). Under the water, each lake is rebuilt to a profile
instead of a ramp:

| Zone | Depth | Width | Purpose |
|---|---|---|---|
| **Littoral shelf** | 1 (wadeable) to 2 | 8-40 blocks, widest in bays, narrow at points and cliffs | the first thing a player sees; wading rest ground under the fatigue rule; weed beds |
| **Drop-off** | from 2-3 to 8-15 over 3-8 blocks | a band | the edge that makes a lake read as a lake; gravel and stone |
| **Basin floor** | 8 to the lake's deepest | the rest | silt (clay and mud), flat or gently rolling |
| **Structure** | — | a few per lake | humps rising to 3-6 deep, one **shoal or sunken island to 1 deep** where a dive site needs a rest point, a point running out as a ridge, a channel between two basins |

Per lake, what the structure is for:
- **Viltri:** a shelf all round (the Surf school's first lesson is the drop-off), the survey floor kept at y75.
- **Shrew:** the pit kept at its full 51, walled; a narrow shelf; a shoal about 30 blocks from the pit's lip as the
  dive point for the surveyor's case.
- **Arrow:** a shoal within 30-40 blocks of Mesprit's grotto mouth, so the grotto is within a trained budget without a
  raft (section 4).
- **Marshy Marsh:** already the shallowest-sided (15.7% wadeable); drowned-forest humps on the shelf, the pit kept.
- **Tilpey:** a wide north-shore shelf for the Dive school's lessons, the practice floor at 25, a shoal near Uxie's
  grotto, the Weeping Elder island's apron.
- **Peak Pond, Watering Hole, Mt Clay pond, the tarn:** shelf, drop-off and one hump each; fishing marks.

**Bed materials (paint, in the export):** sand on the shelf, gravel and stone on the drop-off, clay on the floor
(`paint_maps.py` terrain zones, replacing the noise). Mud has no WorldPainter terrain in use here, so mud is a block.

**Skin (blocks),** one generated pack, `cobblers_water_skin`:
- **weed beds**: seagrass and tall seagrass on shelves, kelp in the drop-off band (never breaching the surface),
  lily pads over still pools and shelves, reeds (sugar cane) on slow banks;
- **silt**: mud and clay patches on basin floors and in slow river pools, replacing the top bed block only;
- **structure**: sunken logs and stumps, drowned trees on Marshy Marsh's shelf, boulder piles on humps and in riffles,
  drift logs at river bends, river stones (cobble, mossy cobble) in riffles;
- **flowing riffles**: where a riffle's single steps sit close enough, its source blocks are replaced by flowing water
  so the surface shows the current and a boat drifts. Whether this holds after the game updates the water is not
  known [A]; proof P3 in section 10 decides it before any riffle is built.
- the Viltri Ravine's dry half: the dressing of option A.

Minecraft cannot make a gentle river's surface move: a still pool looks still whatever is built. The feeling of flow
comes from the planform, the riffles and cascades where water really moves and sounds, and the bars and drift that
say which way it goes. That is what is promised here, and no more.

### 3.4 How

| Piece | Tool and data | Where it sits in the heightmap chain | Owner |
|---|---|---|---|
| River planform, pools, riffles, cascades, the Viltri Ravine stream | `tools/grade_rivers.py` gains a meander and pool-riffle step after `descend_route`, and a spring source kind; `data/rivers.json` regenerated | The start of the chain: the river cut is made into the eroded file, then the sculpt, rescale, pads and Rift are re-run. Each stage starts from its recorded input and is deterministic [V: `data/world.json` notes; RIVERS.md "deterministic"]. The rescale is the identity below y145 and no river is above y127, so rivers pass through it unchanged | `world-content-dev` |
| Lake bathymetry | A new final-stage pass, `tools/lake_beds.py` with `data/lake_beds.json`, in the Rift pass's pattern: it starts from the recorded un-bedded heightmap, changes only columns inside a basin polygon below level - 1, and records `lake_beds_from` in `data/world.json` | The end of the chain | `world-content-dev` |
| Bed zones | `tools/paint_maps.py` reads `data/lake_beds.json` zones and the new river reaches | Paint | `world-content-dev` |
| The skin | `tools/water_skin.py`, pack `cobblers_water_skin`, a new `reapply.py` step after the islet (R10) and before the towns (R8); it writes only in water columns and never inside a town, route, bridge or dock box | Blocks | `world-content-dev`; audit by `test-author` |

After the heightmap changes: `cell_stats.py --write-cells`, `region_measure.py --write`, `measure_towns.py`,
`build_routes.py` (checking no new route crossing), `waterways.py` and `compile_spawns.py` for the new river lines,
the visibility re-measure (already stale, STATE), and `paint_maps.py`.

### 3.5 Audits (fail closed)

Heightmap, offline, comparing the new heightmap with the old and with the data, never with the generator's plan:
1. **Outside the declared boxes, bit-identical.** Any other changed column fails (the Rift's rule).
2. **Shorelines fixed:** no lake column at or above level - 1 changes; every lake's wet area at its level is unchanged.
3. **No new leak:** every dry column below a lake's level that touches its painted water is a declared outflow step.
   Today's count per lake is the baseline: Tilpey 183, Shrew 91, Marshy Marsh 51, Arrow 46, Watering Hole 23,
   Viltri 17, Peak Pond 11, Mt Clay 6, the tarn 5 [M]. An undeclared column fails.
4. **Descent:** no river bed or water surface rises downstream, at full resolution, on every course (RIVERS.md's check,
   kept); each surface step is at a declared riffle, cascade or fall, and no single step is over one block except a
   declared fall.
5. **Shape delivered, measured from the result:** each meandered reach's sinuosity within its target; each lake's
   wadeable shelf share, drop-off gradient and every declared shoal's depth (1) and hump top within tolerance. A lake
   or reach declared and found unchanged fails, and so does an audit that found nothing to check.
6. **Nothing else moved:** 0 settlement drift (`measure_towns.py`), no new water crossing on any route leg except
   `data/bridges.json`'s, no route step over 35 degrees, the Route 7 bridge's audit still clean, no landmark tree or
   elder within its water clearance.

Blocks, offline at `prepare`, from the function's own writes held against the heightmap and the water model
(`tools/bridges.py`'s `water()`, which already computes lakes, rivers and sea from committed data):
7. every write is in a water column or on its bank, never inside a town, route, bridge or dock box;
8. seagrass and kelp only on a valid support block in water, kelp tops at least one block under the surface;
9. silt replaces the top bed block only (no column's top changes height);
10. no structure blocks a declared grotto mouth, dive line or boat channel;
11. nonempty per lake and per river; a lake or river with no writes fails.

In the world, after the step: `verify --world <stopped copy>` reads back a sample of every lake's and river's writes
and fails below 100% of the sample.

### 3.6 Export flag

**Item 1's shape needs an export.** It will not be done as blocks. What can be done before it: the heightmap design,
its measured maps and cross-sections for the owner to look at, the audits above running offline, and proof P3
(flowing riffles) on staging.

---

## 4. Item 2: lake content

### 4.1 What exists

- **Viltri:** the sounding platform, the north-bank platform with its beached skiff, the Lake Surveyor, on staging
  [V: `EARLY_ROUTES.md:138-139`]; `SQ-G2-01` surveys the floor at y75.1. Misty's two piers are planned anchors only.
- **Shrew:** `SQ-DIG-02`, a surveyor lost there; rare deep Dratini in the roster (compiled, not seen in game).
- **Tilpey:** the Weeping Elder on its island; the Route 7 bridge over the outflow (staging). No Dive school, no
  survey diver, no dock.
- **Arrow, Marshy Marsh:** rosters only. The trio's grottos are decided in the lakes and exist nowhere.
- **The ladder's grants** `cobblers:water/grant_surf` and `grant_dive` exist; no event calls them [V: `blackout_pack.py`].
- Nothing under any lake's water is built.

### 4.2 What will be built: a visible hook for every lake

The owner's test for each: something **visible from the surface** that makes a player want to go under. Light and
movement carry through clear water from above [A: a lit block seen from the surface through 25-50 blocks of water is
not measured; proof P4]. So every hook is a light, a column of bubbles or a shape on the shelf, and every one is seen
by a player long before they can reach it.

| Lake | Role | Stage | Hook seen from the surface | What is under it | Rest point for the dive |
|---|---|---|---|---|---|
| **Viltri** | The Surf school | S1-S2 | A line of survey buoys from the sounding platform out over the drop-off, each on a chain that runs down out of sight; at night the lowest marker glows on the floor | The survey grid's weighted markers down the drop-off to the y75 floor; Misty's training course (rings of stone and copper on chains); the floor survey's finds (`SQ-G2-01`); a practice cache | the platforms; a buoy raft at the drop-off |
| **Shrew** | The dragon's pit | S2 | A torn surveyor's float snagged on the shoal, its line running down into the dark; now and then a slow ripple of bubbles over the pit | The line leads to the surveyor's field case on the pit floor at 50 deep (`SQ-DIG-02`), with shed scales; Dratini's deep water | the new shoal |
| **Tilpey** | The Dive school, and Uxie | S6, S7 | A diving bell hanging from a gantry at the school's dock, and the practice floor's lit markers under it; away across the lake, a pale gold light deep off the Weeping Elder island | The practice floor (25 deep) and its lesson cache; Uxie's grotto mouth under the island's apron, a flooded passage and an air chamber | the dock, the bell (an air pocket), the island |
| **Arrow** | Mesprit's grotto | S3 | A ring of standing stones on a hump, lit from inside, and a thin column of bubbles rising from the middle of the ring | The grotto mouth in the ring's centre, a passage of no more than 20 blocks, an air chamber for the battle | the new shoal |
| **Marshy Marsh** | Azelf's grotto | S5 | Drowned trees standing out of the water in a ring round the pit, one with a blue soul-lantern glow in its roots | A sunken boardwalk down the pit's wall to the roots; the grotto mouth under the root tangle; an air chamber | the drowned trees' root crowns (standing ground) |
| Peak Pond, Watering Hole | Fishing water | S4, S7 | a fishing jetty and marks (item 6) | fish; a rod find (WATER_PROPOSAL 5.1) | the jetty |

The trio are shown to every player whatever their badges; the legendary answers only for a player whose badge flag
allows it (`cobblers:flag/gym3_cleared`, `gym5`, `gym7`). A player who finds Arrow's ring at S2 learns there is a
reason to come back, which is the point of a hook.

### 4.3 How

All blocks, built after the water export because every piece sits on a lake bed item 1 reshapes:
- **Grottos and air chambers** are carved like Victory Road's caves: a model, a sealed shell, a flat water surface in
  the chamber at one Y, dry floor above it. An air pocket at depth is stable in Minecraft (water does not rise into
  air) [A: proof P1].
- **Hooks** (buoys, chains, stones, the bell, drowned trees, lights) are block writes in the same pack,
  `cobblers_lake_sites`, with its own `reapply.py` step.
- **Finds** (the case, practice caches, survey finds) are ADR-002 finds in `data/rewards.json`, per player
  [V: `tools/rewards_pack.py`; per-player delivery not yet proven, STATE "Rewards"].
- **The legendaries** are authored encounters, EXP-006 (unrun), spawned by a function when a qualified player enters
  the air chamber [V: `spawnpokemonat` works from a function, EXP-042]. Shared or per player is still open
  (WATER_MAP decision 1).
- **The schools**: Misty's Surf grant and the survey diver are dialogue NPCs whose conversations call `grant_surf`
  and `grant_dive` (`tools/compile_dialogue.py`, scene NPCs placed by R9F or R17). The story lines are Codex's
  (`ARC.md` has neither).

### 4.4 The dive budgets, under both readings of finding F1

Round trip from the rest point, at 5 blocks per second (Surf) [M, planned sites]:

| Site | From the rest point | Surf player now (fatigue 30 s) | If trained players do not tire at depth (decision 1) |
|---|---|---|---|
| Viltri survey floor, 28 deep | from a drop-off raft: about 6 s down, 6 s up | 18 s on the floor before the first hit | 49 s on the floor (air) |
| Shrew's case, 50 deep | from a shoal 30 blocks off the pit: about 16 s each way | **no time on the floor**: the case must lie on a ledge or the player must ride out and dive from a mount | 29 s on the floor (air) |
| Arrow grotto, 41 deep + 20 of passage | from a shoal 30-40 blocks off: about 15-20 s to the chamber | reaches the chamber inside the budget, recovers there | as now |
| Marshy Marsh grotto, about 37 deep | from the root crowns: about 10 s | fine | fine |
| Uxie, Tilpey, about 25 deep + passage | from the island apron: about 10 s | fine | fine |

Riding a water Pokemon out and diving from it works under either reading, because riding recovers fatigue
[V: `surface/tick`]. Whether a player can send out and remount a Pokemon while swimming in deep water is not tested
[A: proof P5].

### 4.5 Audits (fail closed)

1. **Every grotto:** its shell sealed (at least 4 blocks of rock round every void, no void connecting to the lake but
   the passage), the chamber's water surface flat at one Y, the passage no longer than declared, a walkable chamber
   floor at least the declared battle area; checked on the model and, after the step, cell by cell on a stopped world
   copy (the Victory Road pattern [V: `tools/vr_caves.py verify`]).
2. **Every hook is visible:** a light source or bubble column within 8 blocks of the site and within the declared
   depth of the surface; a site with no hook fails.
3. **Every dive fits its stage:** the path from the declared rest point (a shoal, raft, dock or root crown in the
   data, checked against the heightmap for depth 1 or land) to the site, at the stage's rung, stays inside the
   fatigue and air budgets computed from `data/blackout.json`'s constants, never restated in the audit. A site out of
   budget, or with no rest point, fails.
4. **Gates:** each legendary's function checks its badge flag (parsed from the generated function); a spawn line
   without a flag check fails.
5. Nonempty; every find has a `data/rewards.json` record.

---

## 5. Item 3: shallows and shore water

### 5.1 What exists

Measured near-shore profiles [M]:

| Coast | Median depth at 1-4 / 5-8 / 9-16 / 17-32 / 33-64 / 65-128 blocks out | Wadeable within 16 |
|---|---|---|
| Pallet and the Route 1 west coast | 1 / 1 / 1 / 2 / 3 / 8 | 80-93% |
| The south coast to Sunset West | 1 / 1 / 1 / 2 / 3 / 15 | 88-98% |
| The north-west coast, Viltri's Path mouth | 1 / 4 / 6 / 8 / 9 / 18 | 12-58% |
| The windward coast | 1 / 4 / 7 / 9 / 11 / 24 | 24-55% |

The south coasts, where a new player starts, are a flat sheet of water one block deep for 16 blocks, then a ramp; the
north and west coasts drop to 4-7 deep at once. Nothing grows in any of it: a WorldPainter export places no kelp,
seagrass or coral [V: `OCEAN.md` section 4]. The only marine roster is the Windward Sea's, compiled and not installed
[V: STATE]. Built on staging: the First Cast jetty and Relic Island's islet. The sea was a third of the design and is
empty water.

### 5.2 What will be built: the sea before Dive, by stage

| Stage | What the player meets | Layer |
|---|---|---|
| **S0** (no mount, untrained) | **Tidal flats and bars** off the south coasts: the one-block sheet broken into sand bars, runnels and a lagoon behind a barrier bar, so wading the coast is a road and every bar is a rest point. **A bar chain to Fungal Isle** (decision 7) with no run of 3-deep water over about 40 blocks between bars. **Rock pools** on the rocky points of the windward and north-west coasts (Krabby, Corphish, Shellder, a find in one). **Kelp beds** just past the wade line, seen swaying from the beach, with Krabby and Tentacool. **Sea stacks and skerries** off the rocky coasts with Wingull colonies. **A beached shipwreck** on the south strand. **A sea cave at the waterline** on the windward cliffs, walked into on foot at the tide line: a cave explored on foot at S0, with a find. First Cast's fishing. The Relic reef's sunlit edge seen from the islet | bars, flats, skerries: **heightmap**; everything on them: blocks |
| **S1** (first ride, Gyarados at 20) | The lane to Viltri Light over the open water; the sunlit fishing-boat wreck 5-10 deep; Wailmer seen spouting | blocks; rosters |
| **S2** (Surf) | The slope wreck at 20-35 deep; the Relic reef's drop-off (Galarian Corsola); Viltri's Path estuary (fishing, Wooper and Poliwag); caches on the kelp floor | blocks; the reef platform is heightmap |
| **S3-S5** | The Sunset strait and the Sunset isle's coast (ferry); the north-east coast and the marsh outflow's estuary; the Northlight packet at S5; the Eastern Reach shelf (Mantine needs `minY 48`) | blocks; rosters |

**Rosters** (data, `datapack-content-dev` with `trainer-balance-designer`): a Southern Shallows marine zone round
Pallet, Relic Island and Sunset West (WATER_MAP decision 9), rock-pool and coral entries (Corsola needs coral nearby
[V: OCEAN.md section 4]), and the other coasts' shallows, each at its nearest leg's band so fishing and swimming
cannot reach over the cap.

### 5.3 How

- **Heightmap** (in the water export): the bars, runnels, lagoon, skerries and stacks, the Fungal bar chain and the
  Relic reef platform, as a coast pass in the final-stage pattern, local boxes only, with `tools/ground.py` then
  knowing them as ground. The islet stays blocks (decided, STATE).
- **Blocks:** pack `cobblers_shore` (kelp, seagrass, coral and fans on the warm south shelf, sea pickles, rock-pool
  dressing, tide-line debris, the beached wreck from a vanilla or Cobblemon template [V: OCEAN.md table: templates,
  hand-placeable], the waterline sea cave carved in the cliff).
- **Coral in a lake or cold water:** coral dies out of water; whether it lives in any water whatever the biome is
  assumed [A: proof P6]. The reef box can be given `warm_ocean` by `fillbiome` as the Rift skin does [V:
  `tools/rift_skin.py`].

### 5.4 Audits (fail closed)

1. **The swim-budget audit** (new, `tools/swim_budget.py`, `test-author`): every crossing in the data is declared with
   the stage and rung that should manage it, or declared a gate. The audit walks each line on the heightmap with the
   pack's constants read from `data/blackout.json` and fails if a "swimmable at S0" line reaches collapse, or a "gate"
   line is swimmable. This is the ferry's audit too (section 11), and it is re-run whenever `data/blackout.json`
   changes.
2. The coast pass: bit-identical outside its boxes; every bar's crest at depth 1 and every declared skerry above y62,
   measured from the result.
3. Blocks: kelp and seagrass on valid supports under the surface; coral only inside the reef boxes and touching water;
   nothing written inside a town, route, dock or ferry-lane box; nonempty per coast.
4. The sea cave: the Victory Road cave checks (shell, walk-out, reachable floor) and its mouth at the waterline.

**Export flag:** the bars, skerries and reef platform need the water export.

---

## 6. Item 4: the Dive sea

### 6.1 What exists

The sea floor is the extended import line: the median sea column went from y40 to y21.5 in 2026-09-13's re-import,
and beyond about 400 blocks from land it is a flat plain at y10 [V: `OCEAN.md` sections 1-2]. The seabed pass that
would give it a shelf, a break, a slope, a basin, seamounts and ridges is specified and not built. No Dive site exists.

### 6.2 What will be built

| Site | Stage | What | Layer |
|---|---|---|---|
| **The seabed** | — | OCEAN.md section 4: shelf to y46, break to y28, slope to y18, basin to y10, five seamounts to y46-54, two ridges with passages, submarine canyons kept (decision 6) | **heightmap** |
| **The Relic reef and the sunken Pallet fragment** | S0 edge, S2 drop-off, S6 fragment | WATER_PROPOSAL 3.2's three layers: coral on the reef platform (item 3), the drop-off, and on the seabed the torn-off rest of Pallet: a house and its cellar lying broken, rooms joined by a collapsed stair, flooded; the reef cache and a second letter | platform heightmap; the rest blocks |
| **The forge ruin** | S6 | Cobblemon's submerged forge ruins template, flooded, in the Windward Sea's deep band | blocks |
| **The three wreck coves** (Lugia's keys) | S6+ | Cobblemon's lush, submerged and magma shipwreck coves, assembled once in a disposable world, captured and flattened (jigsaw blocks removed), placed in the Frostwater Shelf, the Eastern Reach and the Outer Deep [V: OCEAN.md: coves are jigsaw, depth 20; EXP-014 on jigsaw blocks] | blocks |
| **The trench** | P | 60-120 wide, floor y-20 to y-40, deepslate, three air-pocket chambers on the descent, the flooded shrine | **blocks**: below the heightmap's y10 floor, as the Windward Deep pit is [V: `tools/rift_deep.py`] |
| **Underwater caves at real depth** | S6 | At least three cave systems entered 20-40 deep, with passages longer than a Surf breath. **One surfaces into a dry cave:** its flooded passage rises into an air chamber whose pool is the only way in, and from the pool dry galleries run on foot to a cache, a Habitat Block tile and a sealed view out through a crack in the cliff. Candidate settings: under the windward headland south of Viltri Light, or in the Frostwater Shelf's cold ruins; the site is chosen by measurement against the criteria in the audit and reported before building | blocks |

**Dive, not Surf:** a Dive site is one whose path from the nearest air or rest point is longer than the Surf budget.
Under today's rule both rungs tire at the same 30 s (F1), so "Dive only" rests on air alone; decision 1 matters here
too.

### 6.3 How

- The seabed: a final-stage `tools/seabed.py` from `OCEAN.md` section 4's profile, keeping the imported surface
  wherever it is deeper than the profile (so erosion canyons survive), in the water export.
- Blocks: `tools/dive_sites.py` with `data/dive_sites.json`, pack `cobblers_dive_sites`, one `reapply.py` step for
  caves and sites, seating everything on `tools/ground.py`'s new seabed.
- **Two template transforms that do not exist yet:** *flood* (a template's air becomes water and every waterloggable
  block is waterlogged, or a house placed underwater carries its own air pockets [A]) and *lay on its side* (rotate
  about a horizontal axis with block states remapped). `tools/rematerial.py` does neither [V: WATER_PROPOSAL 3.2].
  Both are offline tools on the template, testable without a world.

### 6.4 Audits (fail closed)

1. Seabed: bit-identical above y62 and on land; the profile's shelf, break, slope and basin depths met by band,
   measured from the result; every seamount summit within its range; no new land.
2. Caves (the Victory Road pattern): shell at least 4, every open face sealed but the declared mouths, fluids bounded,
   every air chamber's water surface flat, every dry floor cell reachable on foot from the surfacing pool (0 traps), no
   void in any town, route or lake basin.
3. **The surfacing cave exists:** at least one cave whose mouth is at least 20 blocks under the surface and whose
   model has an air chamber with dry galleries reachable only through the pool; fewer fails.
4. **Rung check:** each site declared Dive has an underwater path from air longer than the Surf budget, and each site
   declared Surf a path inside it, computed from `data/blackout.json`.
5. The trench: carved only inside its polygon, a deepslate shell, chambers sealed.
6. After the step: every cave verified cell by cell on a stopped world copy (`vr_caves.py`'s precedent: 1,936,430
   model cells matched).

**Export flag:** the seabed needs the water export. Nothing in the Dive sea is placed before it, because every site
seats on it.

---

## 7. Item 5: shipwrecks and Rift debris

### 7.1 What exists

No wreck or debris anywhere. Available: vanilla shipwreck and ocean-ruin templates and Cobblemon's fishing boats,
hand-placeable [V: OCEAN.md table]; the Displaced City's 18 house designs, re-materialed; `tools/ruins.py`'s method for
ruined copies of them [V: STATE, the Scar]. Dhelmise's shipwreck spawns read structure data, which no placement writes
[V: EXP-013].

### 7.2 What will be built

A **recurring find**: about 40-60 objects on the sea floor, a quarter in Surf reach (at most 35 deep, S2+) and the rest
Dive only, spaced by a density rule per band and marine region:
- **vessels:** vanilla shipwrecks, Cobblemon fishing boats, a Pacifidlog raft, lying flooded, some broken in two;
- **Rift debris, things that do not belong:** Displaced City houses (ruined copies, flooded), a length of rail with a
  cart, a lamppost, a Centre sign, a garden gate with a mailbox, a bench, a bus-stop shelter: the exchange's leftovers,
  seeded in lines that point back toward the Rift;
- each find has a per-player first-find cache (ADR-002), and a few carry a line of the story (Codex).

Dhelmise and any shipwreck-bound species come from position boxes or Habitat Blocks at the wrecks, not structure
entries.

### 7.3 How

`data/sea_finds.json` (kit, count per band and region, seed) and `tools/sea_finds.py`: a seeded scatter seated on the
seabed from `tools/ground.py`, with the flood and side-lying transforms of 6.3; pack `cobblers_sea_finds`, one step.

### 7.4 Audits (fail closed)

1. Every find seated: its footprint's lowest heightmap ground within 2 blocks of its base; wholly under the surface
   (or declared breaching); flooded (no air block in its writes unless declared an air pocket).
2. No two finds overlap; none inside a ferry lane, dock, cove, cave, the trench or a town; spacing and counts per band
   within the rule; counts measured from the function, not read from the plan.
3. Every find's cache has a rewards record; every species entry for a wreck names a box or block that exists.
4. Nonempty; a band with a declared count and no finds fails.

---

## 8. Item 6: docks and fishing

### 8.1 What exists

Built on staging: the First Cast jetty, the two Viltri platforms, Pacifidlog's jetty, Fishers' Row (17 stations) and
waterfront [V: STATE; `EARLY_ROUTES.md`]. Planned: Misty's two piers, Sunset West's quay, west pier, south pier and
slipway [V: `data/placements.json`]. Proposed: 11 new small docks (WATER_PROPOSAL section 6). **No fishing spawn
exists in the data** [V: WATER_PROPOSAL 5]; what a rod's ball does is unresearched; whether a coordinate box holds on
a fishing spawn is unknown [A]. At First Cast, vanilla's open-water treasure check probably fails on the one-deep flats
[V: `EARLY_ROUTES.md:136`].

### 8.2 What will be built

- **Docks:** `data/docks.json` and `tools/docks.py` in `tools/bridges.py`'s pattern (a deck continuous from ground to
  water, piles to the bed, lanterns on posts, a boat rack where a water road starts), pack `cobblers_docks`, one step.
  Order: the Relic landing, the Sunset isle landing and the Tilpey three first; then the lakes' fishing jetties after
  the water export (their beds change); the Northlight pair with Northlight.
- **Fishing:** `fishing` entries per spot in `data/spawns.json`, each at its own stage's band (WATER_PROPOSAL 5.2),
  after proof P7 shows a box holds on a fishing spawn; the rod ladder after the rod research (`cobblemon-researcher`).
- **The prize exchange:** section 12.

### 8.3 Audits (fail closed)

1. Docks (the bridges audit, adapted): continuous deck from heightmap ground to water, the deck's end over water at
   least the declared depth (a fishing dock over at least 3, so treasure and fish can bite), piles only below the
   deck, lanterns on posts, no light block, nothing in a town's lot or building unless the town plan names it.
2. Fishing: every fishing entry's box inside a water body from the water model, its levels inside its stage's band
   (`compile_spawns.py`), and no fishing box without a dock, bank or boat access within 16 blocks.

---

## 9. Which items need an export

**Flagged, not worked around:**

| Needs the water export | Why |
|---|---|
| River planform, pools, riffles, cascades; the Viltri Ravine stream | shape; WorldPainter fills rivers from level crops |
| Lake shelves, drop-offs, floors, humps, shoals; bed zones | shape; lake water and bed paint come from the heightmap |
| Coast bars, flats, lagoons, skerries, the Fungal bar chain, the Relic reef platform | shape; ground for everything seated on them |
| The seabed pass | shape; ground for every Dive site and every wreck |

The export is a **staging** export first (`cobblers-dryrun12`), with every existing re-apply step re-run and audited
on it. The live world receives all of it only at the live re-export, blocked today on the three items in STATE
"What is blocked". Nothing here adds a blocker to that list, but it adds content that exists only on staging until
then.

**Blocks, re-applied after every export:** the water skin, the lake sites, the shore dressing, the Dive sites, the
trench, the caves, the sea finds, the docks.

---

## 10. Phase order

**Phase A: decisions and proofs.** No content. The owner answers section 13. Proofs on staging
(`cobblers-dryrun11`), each a rig cleared afterwards, recorded in one new experiment:

| # | Proof | Why |
|---|---|---|
| P1 | An air chamber at depth stays dry and flat across a restart | every grotto and the surfacing cave |
| P2 | Fatigue underwater under the chosen rule (decision 1); whether Slowness slows an unaided swim | every dive budget; every crossing's margin |
| P3 | Flowing riffles: close single steps with flowing water, left for the game to update; do they stay flowing, sound and push a boat? | the river skin |
| P4 | A light 25 and 50 blocks down seen from the surface by day and night; a bubble column's surface; whether a bubble column refills air | every hook; the air bypass |
| P5 | Sending out and mounting a water Pokemon while swimming in deep water | riding out to a dive |
| P6 | Coral, kelp and seagrass alive in a lake and in cold water | weed beds; the reef |
| P7 | A fishing spawn inside a coordinate box; whether a Poke Rod fires `minecraft:fishing_rod_hooked` and what else it reels in | fishing spots; the exchange's earning side |

What can be **built on staging now**, in parallel: the ferry's mechanism at the two docks that exist (section 11),
the exchange prototype with the casino's EXP-043, the swim-budget audit, the template transforms (flood, lay on its
side), and docks on shores the water export does not reshape (the Relic landing, the Sunset isle landing).

**Phase B: the water export.** Items 1, 3 and 4's shape designed, measured and shown to the owner as maps and
sections (report). Then applied to the canonical heightmap as one revision, audited offline (sections 3.5, 5.4,
6.4), exported to `cobblers-dryrun12`, every existing step re-applied and the full audit run.

**Phase C: blocks, in the owner's order**, each reported before it is built and audited after:
1. the water skin (item 1);
2. the lake sites (item 2);
3. the shore (item 3);
4. the Dive sites, caves and trench (item 4);
5. the sea finds (item 5);
6. the lake docks and fishing (item 6).

**Phase D: live**, at the live re-export.

Who builds what: `world-content-dev` the heightmap passes and the block packs; `minecraft-systems-dev` the fatigue
change, boat rule and ferry functions; `datapack-content-dev` the rosters and fishing entries with
`trainer-balance-designer` for levels; `cobblemon-researcher` the rods and fishing events; `test-author` every audit
named here, never the builder of what it audits.

---

## 11. The ferry: gate or decoration

### 11.1 The crossings under the 2026-09-27 rule

Each line walked block by block on the heightmap from shore to shore [M]. "Swim" is the longest run without a place
to stand or wade; "3+ deep" is how much of all the swimming is deep-rate water. Knocked out is the second hit.

| Crossing | Length | Swim | 3+ deep | Deepest | Unaided | Trained (Surf or Dive partner) |
|---|---:|---:|---:|---:|---|---|
| Pallet beach (1101, 5410) to Relic Island | 93 | 71 | 64 | 23 | arrives exhausted (1,052 of 1,200), no hit | warned only |
| First Cast jetty to Relic Island | 154 | 113 | 74 | 24 | first hit 8 blocks short; knocked out 6 short if Slowness counts | warned only |
| Pallet coast (985, 5233) to Fungal Isle | 198 | 160 | 122 | 7 | knocked out after 124 | exhausted, no hit |
| First Cast jetty to Fungal Isle | 234 | 184 | 133 | 5 | knocked out after 130 | exhausted, no hit (a hit at 174 if Slowness counts) |
| The Sound narrows at z6100 | 103 | 65 | 38 | 4 | **slowed, no hit** | fine |
| The Sound narrows at z6300 | 148 | 137 | 123 | 8 | knocked out after 107 | exhausted, no hit |
| The Sound narrows at z6500 | 103 | 96 | 90 | 6 | knocked out after 97 | fine |
| Dunes to the Long Isle, shortest ((7319, 6462) to (7397, 6503)) | 88 | 84 | 79 | 6 | first hit 7 short of land | fine |
| Pacifidlog's jetty to the town square | 276 | 179 | 184 | 27 | knocked out after 134 | **knocked out after 228** |
| Eastern dunes to the Jungle Isle, shortest | 322 | 290 | 261 | 37 | knocked out after 116 | **knocked out after 191** |
| Sunset West's south pier to the Sunset isle | 284 | 258 | 223 | 26 | knocked out after 117 | **knocked out after 192** |
| Marsh country to Northgate Isle, shortest | 304 | 282 | 257 | 31 | knocked out after 110 | **knocked out after 185** |
| Marsh country to the Pine Isles, shortest | 437 | 418 | 397 | 41 | knocked out after 108 | **knocked out after 183** |

Before 2026-09-27, `WATER_PROPOSAL.md` 4.1 found every island but the Pine Isles swimmable in 12-18 s of open water.
Under the new rule:

### 11.2 The answer

1. **Is the ferry now a gate for untrained players? Yes.** Every ferry line but the Relic row now crosses water an
   unaided swimmer cannot: the Sunset strait (258 blocks of swimming against a 90-block limit), the Sound ferry from
   the jetty (179), the Northlight packet (418), the charters. Only the Relic row stays kindness (the beach swim
   arrives exhausted) and the Long Isle stays reachable at its z6100 narrows.
2. **At which stage does it stop being one? Not at Surf.** Surf training (S2, Misty) halves fatigue, so a trained
   swimmer is knocked out after about 165 blocks of deep water. That opens Fungal Isle and the Sound narrows and
   nothing else: the Sunset strait, the Jungle Isle, Northgate, the Pine Isles and Pacifidlog's crossing are all longer
   than 165 blocks of continuous swimming. Dive (S6) halves the same way. **By swimming, the far islands are never
   reachable at any stage.**
3. **What does end it is riding.** Riding anything recovers fatigue [V: `surface/tick`]. Nothing in the repository
   gates riding (STATE, "The western sea has its own rosters"). The first surface mount in the rosters is Gyarados,
   from the Magikarp in the Viltri, Shrew, Peak Pond and Tilpey rosters at level 20 [A: evolution level from the
   species data, not re-read], which the S0 cap of 20 allows; a rare Relicanth at Arrow Lake before Brock rides as a
   Dive mount. So for a player who raises one, the ferry stops being a gate at about S1.
4. **Boats decide whether it gates anything.** A boat is ridden, so it is exempt and crosses every strait above from
   S0 (five planks). With boats unrestricted (WATER_PROPOSAL options A or B) **the ferry is decoration**. With boats
   as shallows craft (option C, swamped past 96 blocks from land), a boat still reaches Relic, Fungal and the Long Isle,
   whose lines never pass 80 blocks from land (WATER_PROPOSAL 4.1's "farthest from land" column [M there]), and cannot
   cross the Sunset strait, the Jungle Isle, Northgate, the Pine Isles or Pacifidlog's crossing unless the Sound is
   authored sheltered water. Option C needs a distance field again for boats only: `tools/open_water.py` still builds
   it; the pack no longer reads it [V: `data/blackout.json` `superseded`].

**So, which: exhaustion is already harsh enough, and the ferry is a gate, not decoration, if boats are shallows
craft.** It is the only way across the far straits for a player without a ridden water Pokemon, which in practice
means S0-S1 and any player who never raises one. The one early-arrival leak the ferry cannot close is the Long Isle's
z6100 narrows and, soon, its bridge (LONG_ISLE D4); that belongs to the level-cap trap's fix (D5), not the ferry.

### 11.3 The build, once decided

WATER_PROPOSAL 4.2's option A stands: a ferryman, a compiled dialogue, a fare checked and charged in CobbleDollars
[V: EXP-040, EXP-042], a fade and a teleport, per player. It can be proven now at the two built docks, First Cast
(the Relic row) and Pacifidlog's jetty (the Sound ferry). **Audit:** the swim-budget audit (5.4) carries every line as
a declared gate or not, so a change to the fatigue constants that makes a gated strait swimmable fails the prepare;
plus each ferry function's fare check before its charge, and its teleport target on heightmap ground or a deck.

---

## 12. Fishing for prizes: can it use the casino's score currency?

**Yes.** The casino research settles the exchange side, and nothing in it is specific to coins [V:
`docs/research/CASINO.md` section 1]:

- **The stall is per-player stock, not per-player payment.** A villager or CobbleMerchant shows every player the same
  offers, which is where the trader work stopped. A dialogue counter shows each player options gated by that player's
  badge flags, quest fields or score, and each option runs a function as that player: check the score, deduct it,
  `give` or `pokegive`, confirm.
- **The currency is a per-player scoreboard score**, persistent, not an item, so it cannot be duped, dropped or traded;
  no cash-out, a cap, and `scoreboard.dat` made a required carry at the re-export (the casino's own finding).

**The mechanism for fishing** (per player throughout):

| Part | How | Status |
|---|---|---|
| The points | A score of its own, `fish.pts`, separate from the casino's coins so neither converts into the other (decision 11) | the scoreboard pattern is proven in the blackout pack [V] |
| **Earning (recommended): hand-in** | The Guild's fishing master (Pacifidlog) and each fishing spot's keeper take catches at the counter: the dialogue checks the held items with the vanilla item predicate and clears them, storing the count into points; a rare catch counts more | item checks and hand-over proven single-player [V: EXP-022, bucket and bottle]; the scene function a dialogue runs is built, never clicked [V: STATE, EXP-034] |
| Earning (alternative): on the catch | A `minecraft:fishing_rod_hooked` advancement whose reward function adds points and revokes itself, scoped to a spot by the function's position check | whether a Poke Rod fires the vanilla trigger is unknown [A: P7] |
| Earning (alternative): a Pokemon caught by rod | the `pokemon_captured` callback the blackout pack already uses | whether the event knows the Pokemon was fished is unknown [A]; research |
| Farming guards | a daily cap per player keyed on `time query day`, a per-spot cooldown, points only for catches the spot's water can give | design |
| The prize counter | the casino's counter: badge-gated options, each a checked deduction and a give | the combination is EXP-043's prototype (casino), unrun; one proof serves both |

What the hand-in needs to know first is what a Poke Rod actually reels in besides Pokemon (fish and treasure items, or
none) [A: P7]; if it reels in no items, the counter takes the vanilla rod's catch, and the fishing master gives a
vanilla rod.

---

## 13. Owner decisions

1. **Does fatigue build underwater for a trained player?** Today a Surf or Dive player is knocked out after 33 s of
   continuous swimming, dives included (F1). *Recommend:* fatigue is a surface rule for trained players. While the
   eyes are at the ladder's depth and the player qualifies, fatigue neither builds nor recovers, and the air ladder
   governs; a Dive-qualified player does not tire underwater at all. Unaided swimmers keep the rule as it is. Needed
   before any lake-floor or Dive site is sized.
2. **Boats beyond the shallows** (WATER_PROPOSAL decision 1). *Recommend C:* boats are shallows craft, swamped past 96
   blocks from land, with the Sound and harbour basins authored as sheltered water, using `tools/open_water.py`'s
   field for boats only. This is what makes the ferry a gate.
3. **The ferry.** *Recommend:* build it as the gate for players without a ridden water Pokemon, with WATER_PROPOSAL
   4.3's lines and fares; do not make exhaustion harsher. Prove the mechanism first at First Cast and Pacifidlog.
4. **The Viltri Ravine.** *Recommend B:* an underfit stream from a spring at the pass down the sea half (570 blocks of
   real cascades), the lake half kept dry and dressed as an abandoned bed; Codex checks `SQ-G1-01`'s wording.
5. **One water export.** *Recommend:* every heightmap piece (rivers, lakes, coasts, the reef platform, the seabed) in
   one revision and one staging export, so the full rehearsal is paid once.
6. **The seabed pass's scope.** *Recommend:* the whole of OCEAN.md section 4 in that export, not only the south coasts,
   because every Dive site and wreck seats on it and a second export would repeat the rehearsal.
7. **Fungal Isle at S0.** *Recommend:* a bar chain, so an unaided player crosses with warnings and never more than
   about 40 blocks of 3-deep water at a time. Relic stays as it is (swimmable from the beach; the row from the jetty).
8. **Lake shelves and shoals as rest points.** *Recommend yes:* every lake gets a wadeable shelf, and every dive site a
   shoal, root crown, dock or raft within its rung's budget.
9. **River meanders.** *Recommend:* meander the low-grade reaches (the major river's lower trunk, Viltri's Path's
   coastal flats, the Arrow and Watering Hole outflows), cascades on the steep creeks, the Tilpey gorge unchanged
   under its bridge. It re-runs the whole heightmap chain.
10. **The trio's hooks for everyone.** *Recommend yes:* the grottos and their hooks are visible from any stage; only
    the encounter waits for the badge.
11. **Fishing points.** *Recommend:* a score of their own (not casino coins), earned by hand-in at the counter with a
    daily cap, spent at badge-gated counters.
12. **The Long Isle's early arrival.** The z6100 narrows are swimmable unaided and the bridge (D4) will be walkable.
    *Recommend:* answer it with the level-cap trap's fix (D5), not the ferry.
13. **The surfacing cave.** *Recommend:* S6, Dive only, sited under a coastal headland by measurement (windward
    headland near Viltri Light or the Frostwater ruins), reported with its site before it is carved.
14. **Wreck and debris finds.** *Recommend:* 40-60 in all, a quarter within Surf reach, each with a per-player
    first-find cache (ADR-002).

---

## Appendix: how the numbers were measured

Read-only scripts, not committed, on `tools/ground.py`'s heightmap (rounded), with Relic Island's islet and the sea
town's decks laid over as ground (`ground.for_settlement`). No world was read.

- **Crossings:** land is ground at y62 or above; water depth is 62 minus the ground. Region polygons stop short of the
  waterline, so each was grown by 24 blocks before its shore was taken. Each line is sampled every block. A block is
  rest (land, or water 1 deep: wading), shallow (2 deep) or deep (3 or more). Fatigue is stepped with
  `data/blackout.json`'s constants at 5 blocks per second; with Slowness, 15% slower from 600 and 30% from 900. The
  Pine Isles and Northgate were checked for a walkable link to the mainland (land or 1-deep water): none.
- **Lakes:** each `water_body` basin polygon, wet where ground is below the level; depth is level minus ground; shore
  distance by 4-neighbour erosion; "level neighbours" compares each bed column with its four neighbours.
- **The Viltri Ravine:** stations every 4 blocks along the `channel` axis, floor the lowest ground within 4 blocks.
- **Leaks:** below-level ground connected to each lake's water, and dry below-level columns touching it outside the
  basin polygon. Outflow notches are included, so these are a baseline, not a fault count.
- **Coasts:** distance from land by 4-neighbour dilation in each box, depth percentiles by band.
