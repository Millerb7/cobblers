# The Brass Petrel: the wreck on the southern desert beach

Built 2026-10-05 by `tools/desert_wreck.py` from `data/desert_wreck.json`. **Not applied to any world, not audited.**
Everything below is what the generator writes, as its `report` prints it against the canonical heightmap
(`tools/ground.py`, rounded). The independent audit is another agent's: its checklist is the last section.

The owner's brief: *"The southern desert beach is the last empty stretch I can name. Build a wreck half-buried in the
dunes -- something the water left behind, with an interior worth entering. Check it against Dustback in the south-east
dunes first; if they are the same stretch, site them so they do not compete. Propose and build whatever else that ground
supports. A desert meeting a sea should feel like neither."*

## Siting

- **Dustback is not the same stretch.** It is anchored at (6244, 142, 6112) on the dunes' plateau
  (`data/resident_encounters.json`), about 700 blocks north-west and 75 blocks higher; its scar ends at z6146. Nothing
  here moves it.
- **The beach**, measured 2026-10-05 at x4600-7300: water line z6576-6891 (it bows south between x5700 and x7000), flats
  rising y62 to about y68 over 60 blocks, then a dune wall to y105-125. At the site (x6460-6544) the water line is
  z6832-6840, the flats run y62 (z6824) to y69 (z6772), and the wall climbs y70 to y95 from z6764 to z6720.
- **The wreck** stands on x6483-6493, z6752-6791 (centre (6488, 6772), cell G7). Nearest route path about 1770 blocks;
  nearest authored place (not a polygon vertex) 440 blocks, the Pacifidlog bay blackout box. The Copperway Khan is 600
  blocks north-north-east, inland: the Petrel was the company's ore barque, so the two places tell one story from both
  ends. The beached wreck at (4070, 6584) (`data/sea_life.json`) lies in the shallows on its side; this one is high, dry
  and swallowed.

## What the pack writes (`cobblers_desert_wreck`, function `cobblers:desert_wreck/build`)

Every Y is derived: **deck D = max(ground under the transom row) + 4 = 66 + 4 = y70; keel K = D - 7 = y63; hold floor
y64.** Ground under the hull: y75 over the bow (z6752), y72-73 at z6757, y70-71 at z6762, y68-69 amidships, y67 at
z6782-6787, y66 under the transom (z6791). So the dune lies 1-5 blocks over the bow's deck (buried to the rail at the
first three rows), the sand is 1-2 under the deck amidships, and the stern stands 4 blocks of hull plus the cabin over
the flats.

4,299 blocks in all (1,261 air, 159 sand, 1,122 reef). Bounds: wreck and reef `(6466, 62, 6752)-(6510, 82, 6838)`;
the flag `(6450, 63-64, 6826)`.

| Piece | Where | Blocks |
|---|---|---|
| Clearing | box (6447, 62, 6749)-(6513, 86, 6841) | `fill ... air replace` for dead bush, short/tall grass, fern, large fern, cactus, sugar cane, `#logs`, `#leaves` only. **Never `#minecraft:replaceable`** (it holds water). Split under the fill limit by `function_limits.ensure_loaded`, which also force-loads every written chunk for the function |
| Hull | x6483-6493, z6752-6791, y63-70 | half-beam 5, bow taper 1,1,2,2,3,3,4,4,4 (z6752-6760), stern taper 5,5,4,4 (z6788-6791); narrowing downward 0,0,0,0,1,1,2,3 rows under the deck. Shell: dark oak planks to y67, spruce planks y68-70, a stripped dark oak wale (axis z) at y69 on the straight sides. Deck birch planks y70. Hold floor spruce planks y64. **Every hull cell is written**, solid or air, including those under the dune |
| Hold | inside the hull, y65-69 | air; beams (stripped spruce, axis x) at y69 on z6764, 6768 ... 6788 (every 4th row aft of the spill), not where the mast stands |
| Sand spill | z6753-6762 | written sand: full to y69 for z6753-6758, top y68/67/66/65 at z6759/60/61/62 |
| Bulkhead | z6781 | spruce planks y65-69, doorway (6488, 65-66, 6781) |
| The breach (way in) | transom z6791, x6487-6489 | sand sill y65, air y66-68 |
| Foremast | (6488, 64-79, 6759) | stripped spruce, axis y; it comes out of the dune |
| Mainmast | (6488, 64-82, 6772) | stripped spruce; yard at y79, x6485-6491 (axis x) |
| Hatch | (6488, 70, 6773) | spruce trapdoor (top, closed); ladder (facing south) y65-69 on the mast's south face |
| Deck holes | 10 cells at y70: (6488,6767) (6491,6770) (6489,6773) (6486,6775) (6488,6777) (6490,6777) (6492,6778) (6484,6779) (6491,6779) (6486,6780) | air; only where the ground is under the deck and aft of the spill, so no dune sand stands over a hole |
| Rail | y71, the deck's edge forward of the cabin, only where the ground is at or under the deck | 40 spruce fences, connected to each other |
| Cabin | z6782-6791, walls y71-73, roof (poop deck, birch) y74, roof rail y75 | doorway (6488, 71-72, 6782); stern windows (6486/6490, 72, 6791) open |
| Cargo | hold floor | raw copper blocks along x6485 and x6491, z6765-6779 (not z6772-6774), two high on every third row; barrels (6486/6490, 65, 6766/6770/6778); pots (6486/6490, 65, 6779); the company's plate (wall sign, facing north) at (6490, 67, 6780) |
| Berth | z6782-6790 under the cabin | light grey carpets (x6485,6486,6490,6491; z6783-6785); barrels (6485/6491, 65, 6788); pot (6485, 65, 6789) |
| Master's cabin | y71 | the log: four wall signs (facing east) at (6484, 72, z6783/6785/6787/6789); lectern (6488, 71, 6789, no book); cartography table (6485, 71, 6789); **the sea chest: barrel (6491, 71, 6789)**; blue carpet x6487-6489, z6784-6787 |
| Lanterns (the only light) | hold (6488,69,6766) (6486,69,6771) (6488,69,6778); berth (6488,69,6786); cabin (6488,73,6786) hanging; stern (6488,76,6791) on the rail post | 6 |
| Fallen topmast | x6495-6505, z6780, each on its own ground + 1 (y69) | stripped spruce, axis x |
| Kedge chain | x6494, z6793-6826, own ground + 1 | chain (axis z); its anchor a chipped anvil at (6494, 63, 6827) |
| Dead reef | x6466-6510, z6794-6838 | dead brain/tube/horn/fire/bubble coral blocks, bone blocks, calcite where value noise (5-block lattice) is over 0.55, 2 high over 0.72, 3 over 0.85, thinning over 6 blocks at the land edges; one block awash at y62 where the ground is y61, none deeper; a dead fan or sprig on one dry head in three. Lane x6486-6490 and chain columns x6493-6495 left bare |
| Castellan's flag | fence (6450, 63, 6826), white banner (6450, 64, 6826) | |

Spawn conditions written, all declared in `blocks.spawn_conditions` and whitelisted by the
`data/spawn_block_policy.json` entry whose scope names `desert_wreck`: sand (spill, sill), the five dead coral blocks,
dead horn coral and dead bubble coral. No water, no light source but lanterns, no soul sand or magma (no bubble
column), no chest, no bed.

## What is not in the pack

- **Castellan** (`cobblemon:palossand`, L52): `tools/resident_encounters.py`'s keeper, called through
  `southern_residents.shim()` as `tools/far_south.py` does; functions `cobblers:desert_wreck/castellan/{keep,hold,wake,
  settle,spawn,bind}`, `load`, `keeper`, `spawn_at`; objective `cobblers.dwres`. Anchor (feet) **(6448, 63, 6826)** on
  ground y62, two blocks from the sea. Yaw 180, **trigger 3, leash 14**, presence gate `gym7_cleared`, catch rule
  catchable after the gate. No `bind_new` and no entity step: the keeper brings it in for the first gated player within
  96 and nobody within 48.
- **Two natural ReplaceSpawns Habitat Blocks** (`data/habitat_blocks.json`, placed by R9E): `desert_wreck_strand_ward`
  at **(6488, 62, 6818)** (one under the sand, in the reef's lane) and `desert_wreck_hold_ward` at **(6488, 62, 6762)**
  (one under the keel), range 28 each, 56.0 apart (touching, not overlapping). Neither is in a written block. Between
  them a seam: berth cells more than 28 from both fall back to whatever the strip runs.
- **The pool** `desert_wreck_strand` (`data/spawns.json` habitats and entries), tier 7, band 38-48: Sandygast (anchor),
  Galarian Corsola, Binacle (common); Cursola, Silicobra, Sandaconda (uncommon); Shuckle (rare); Galarian Yamask (ultra);
  Palossand and Barbaracle authored-only. Compiled by `tools/compile_spawns.py` to `habitat_pools/desert_wreck_strand.json`
  with **regional forms as `"modifiers": "galarian"`** (fixed in compile_spawns this session: `HabitatSpawn.species` is a
  Species, and "corsola galarian" there would be an invalid species).
- **The cache** `desert_wreck_sea_chest` (`data/rewards.json`, `tools/rewards_pack.py`): Shell Bell, Spell Tag, 3 Dive
  Balls; trigger box (6490, 71, 6788)-(6492, 72, 6790), container the barrel at (6491, 71, 6789).

## The walk in

1. From the flats south of the stern, stand on the sand at (6488, 67, 6792) (ground y66).
2. Step down onto the breach's sand sill (feet y66), then onto the berth floor (feet y65). The berth is under the cabin.
3. North through the bulkhead doorway (6488, 65-66, 6781) into the cargo hold: the ore, the barrels, the sand slope
   choking its bow end from z6762 forward.
4. Up the ladder on the mainmast's south face (z6773) and through the trapdoor to the deck (y70).
5. Aft along the deck to the cabin doorway (6488, 71-72, 6782): the log on the port wall, the sea chest on the
   starboard side.

The other way: down the dune wall onto the bow, where the sand is level with or over the deck (z6758-6765), and aft
along the deck.

## Re-application (for the integrator: `tools/reapply.py` is not edited here)

- install the pack `cobblers_desert_wreck` with the others (reapply's pack list);
- prepare job: `python tools/desert_wreck.py build`;
- **R9DW** = `desert_wreck.placement_steps()`: `forceload add 6447 6749 6513 6841`, wait 3, `function
  cobblers:desert_wreck/build`, `forceload remove ...`. Put with the other block passes before R9E (the wards are not in
  written blocks, so order with R9E does not matter for them);
- R9E places the two new natural blocks; **restart after it** (a natural block is inert until its chunk reloads);
- recompile the spawn pack (`tools/compile_spawns.py`) and the rewards pack (`tools/rewards_pack.py`): both data files
  changed;
- no R18 step: Castellan is gated (`desert_wreck.entity_steps()` returns `[]`).

## Defects recorded (not fixed here)

1. **The beach strip has no campaign pool outside this site.** The `south_east_dunes` polygon stops 15-70 blocks short
   of today's water line from x4864 to x7296 (e.g. x6400: polygon to z6804, water z6825; x7040: z6703 against z6772).
   The water export moved the coast; the polygon was not redrawn. Only the two wards' spheres here are curated. Fix
   belongs to whoever owns `data/regions.json`: redraw the coast edge or add a beach sub-region and a design table.
2. `tests/test_system_contracts.py::test_contract_c4_every_tool_that_reads_the_spawn_conditions_is_accounted_for` fails
   at this branch's base: `tools/bank.py` and `tools/spawn_blocks_list.py` read `data/spawn_blocks.json` and are not
   listed in `data/system_contracts.json` C4 tools. Not this build's.
3. `data/towns.json` sea_town still gives Pacifidlog's centre as (7210, 6960) with "access by water from the mainland
   jetty (7092, 6711)", while `data/ferries.json` says the town moved to (5160, 7380) with the water export.
4. For the test author: `desert_wreck` is not yet in `_source_blocks()`'s place tuple (`tests/test_system_contracts.py`
   C4) and `data/desert_wreck.json` is not read by `tests/test_resident_siting.py`; this build's own tests hold the same
   rules for Castellan.

## Not verified (needs a running server)

The fills landing; the dune's sand lying on the bow's deck as planned (the export's material under the surface is not
known); the natural wards redirecting spawns (EXP-021) and their vertical reach (EXP-033, unrun); Galarian Corsola
spawning from a habitat pool's `modifiers`; the cache granting; Castellan appearing for a `gym7_cleared` player and
waking within 3; what the beach's surface block is (Sandygast's pool spawns need standable ground, not sand, in a pool).

## What an audit must check

Derive every expectation from the heightmap, `data/desert_wreck.json`'s declared numbers and the shared data files,
never from `desert_wreck.plan()` or its helpers. Mutate the GENERATOR (its code), not the record, to prove each check
bites.

1. **Seating.** D = max(round ground) over x6484-6492 at z6791, + `stern_show`; K = D - `depth`. Every hull column
   (from `bow_taper`, `half_beam`, `stern_taper`) has ground > K and >= 62. The first three bow rows have ground >= D+1.
2. **Shape.** The hull cell set matches the declared tapers and the narrowing 0,0,0,0,1,1,2,3; every cell of it is
   written (no natural block left inside the hull); shell vs interior as described; hold air y(D-5)..(D-1).
3. **The sea.** No air or sand written in a column whose ground is under 62; nothing written where the ground is under
   61; the clearing names no water and not `#minecraft:replaceable`.
4. **Palette and light.** Every written block is in `blocks.ids`; the only light-emitting block is the lantern; no
   water, bubble column, soul sand, magma, chest or bed. An independent block-light flood from the lanterns leaves no
   written air cell inside the wreck at 0 (deck holes excepted: they are open sky).
5. **Spawn conditions.** The written spawn-condition set equals `blocks.spawn_conditions` and is covered by the policy
   entry scoped to `desert_wreck`.
6. **Gravity.** No written sand over written air; no deck hole where the ground is at or over D.
7. **The walk in.** A two-high walk with steps of at most one block (ladders climbable) reaches, from the sand at
   (6488, 67, 6792): the berth, the cargo hold, the deck through the hatch, and the cache trigger box in the cabin.
8. **The wards.** Natural, ReplaceSpawns, range 28, not in a written block, not overlapping each other or any other
   natural block (3D, EXP-021), pool `cobblers:desert_wreck_strand` present in `data/spawns.json`.
9. **The pool.** Every species in the Cobblemon 1.8.0 jar; evolution levels read from the jar; authored-only exactly
   where the evolution level is over 38; positions from `position_types.choose()`; the compiled file writes
   `species` without a space and the form in `modifiers`.
10. **The cache.** Item ids in the jar; the trigger box round the barrel and holding standable air inside the cabin.
11. **Castellan.** Anchor dry, sea within 3, ground + 1, not built on; at least 128 from every route path; leash clear of
    every activated Habitat Block's spawn range; level <= `next_cap['7']` (55); `gym7_cleared` is an advancement the
    progression pack grants; keeper functions shaped as `tools/resident_encounters.py`'s and gated in `keep`.
12. **The pack.** `function_limits.check_lines` clean; every written chunk force-loaded; bounds equal
    `data/desert_wreck.json` bounds; no collision with another builder's bounds.
