# The authored gym buildings — independent review

Written 2026-09-29 by an agent that built none of them. Five agents wrote
`data/gym_buildings/gym{1,3,4,5,7}.json`, one each, and none of them was
allowed to write a test (CLAUDE.md principle 16). The audit is
`tools/gym_buildings_independent.py`; its tests are
`tests/test_gym_buildings_independent.py`.

```
python tools/gym_buildings.py build
python tools/gym_buildings_independent.py            # 12 problems over 5 buildings
python -m pytest tests/test_gym_buildings_independent.py -q   # 80 passed, 12 xfailed
```

**Everything below is geometry read out of generated `.mcfunction` text and a
model of vanilla movement. Nothing has been seen in a running game.**

---

## Verdict per gym

| gym | leader | verdict | why |
|---|---|---|---|
| gym1 | Brock | **cannot be finished** | D2 the hoist ladder is broken at y155. Also D1 (spawn box), D3 (a jump the route does not declare) |
| gym3 | Lt. Surge | **completable**, one site defect | D4 the roof's north overhang lies one block outside the spawn-free box. Route, falls, water, support all clean |
| gym4 | Erika | **completable**, notation defect | D5 three route waypoints name a block cell instead of a standing cell. Route, falls, water, support all clean |
| gym5 | Koga | **cannot be finished** | D6 the reed stair's first course is a two-block rise out of the flood |
| gym7 | Blaine | **cannot be finished, and is a trap if it were** | D7 the assay deck's own rail closes the head of the spoil steps; D8 the vault and basin have no exit at all |

Three of five cannot be completed. Two of the three fail at **stage 1**, and
in both cases the block that blocks the climb is written by a later part of
the same record than the climb it blocks.

---

## Defects

### D2 — Brock's hoist ladder is broken at y155 (gym cannot be finished)

`build/.../gym1.mcfunction`, three parts in order:

```
fill 1829 153 3697 1829 156 3697 minecraft:ladder[facing=west]   # the hoist ladder
fill 1811 155 3695 1841 155 3698 minecraft:polished_andesite     # the gallery floor
fill 1829 155 3697 1829 155 3697 minecraft:air                   # "the ladder's hole through it"
```

The gallery-floor fill overwrites the ladder at `(1829,155,3697)` and the next
part re-cuts that cell to **air**, not to ladder. The final state is ladder at
y153, y154, air at y155, ladder at y156. A player climbing stops with their
feet at y154: `blockPosition` at y155 is air, so they are no longer on a
climbable and they drop. Route step 6 says the ladder "climbs four to the
gallery floor"; it climbs two.

Consequence: the gallery, `kanto_brock` at `(1832,156,3696)` and his chest are
unreachable. `data/gym_buildings/gym1.json` parts, the "the ladder's hole
through it" part.

*Fix (not applied — this agent reports, it does not repair): re-cut the hole to
`minecraft:ladder[facing=west]`, or write the ladder after the floor.*

### D7 — Blaine's spoil steps arrive at the deck's own rail (gym cannot be finished)

`gym7.mcfunction`:

```
fill 6160 112 4985 6180 112 4990 minecraft:acacia_planks   # the assay deck, top y113
fill 6160 113 4990 6165 113 4990 minecraft:tuff_wall       # the deck's rail
fill 6175 113 4990 6178 113 4990 minecraft:tuff_wall
fill 6160 107 4991 6160 111 4991 minecraft:tuff            # the top spoil step, top y112
fill 6161 107 4991 6161 111 4991 minecraft:tuff
```

The spoil steps are at x6160–6161 and end at z4991 with the player's feet at
y112. The deck's walking level is y113 at z4990. The rail occupies
`(6160..6165, 113, 4990)` — exactly the two columns the steps arrive at. A
wall block is 1.5 tall and cannot be stepped onto or through, so stage 1 is
impossible and stages 3–9 (the deck, the gantry stair, the gallery, the crown,
the hoods, the leap, the vault) are all cut off with it. The rail's own comment
says "the flue closes the middle and the gantry stair leaves through the east
gap"; there is no gap at the west end, where the climb is.

### D8 — Blaine's vault and basin are a sealed dead end

```
fill 6178 107 4996 6180 119 4998 minecraft:polished_blackstone_bricks   # the geyser casing
fill 6179 107 4997 6179 119 4997 minecraft:water                        # the column inside it
setblock 6179 106 4997 minecraft:soul_sand
```

The casing boxes the column on all four sides **for every course, y107 to
y119** — the comment in the record says so in as many words. The column's foot
`(6179,107,4997)` therefore has no opening into the vault, and the bubble
column is the vault's only declared exit (route step 9). The audit finds **192
reachable positions in the basin and vault from which the lot cannot be
regained**, even with D7 fixed. A player who beat Blaine would be sealed in
with him.

Note for whoever fixes it: cutting a hole in the casing at y107–108 is not
enough on its own. The audit's mutation test does exactly that and a `leak`
appears — the column is watertight only because it is sealed, and an opening at
the water line lets it spread into the vault. The exit needs either a door of
blocks the water cannot pass or an entry above the column's surface.

### D6 — Koga's reed stair cannot be mounted (gym cannot be finished)

The flood is water one deep in cell y116 over `muddy_mangrove_roots` at y115,
so a player wading in it stands with their feet at y116. The reed stair's first
course at z2477 (x4584–4586) occupies cell y117, so its top is y118: mounting
it is a **two-block rise**, and it is approached from the flood on every side
(at x4585 the hall floor is solid under the stack itself; z2478 is water). The
record reads "z2477 tops at y117", counting the block's index rather than its
top face, and the deck two steps later is counted the other way ("blocks at
y121, walked at y122"). Route steps 1–6 are cut off; `kanto_koga` at
`(4594,132,2487)` is unreachable.

### D1 / D4 — two buildings reach outside their spawn-free box

| gym | box (`data/spawn_suppression.json`) | outside it |
|---|---|---|
| gym1 `gym_brock` | `[1808, 3664, 1847, 3711]` | **4,530 cells** at z3659..3663 — the forecourt paving and the north eaves |
| gym3 `gym_surge` | `[1720, 1392, 1751, 1431]` | **840 cells** at z1391 — the roof's north overhang course and the rock mass's north edge |

Both records say so in their own `spawn_suppression.note`, which is honest, but
neither is harmless: wild Pokémon can spawn on those cells. gym4, gym5 and gym7
lie wholly inside their boxes.

### D5 — three of Erika's route waypoints are not standing cells

`[4310,111,1506]` (step 1 `to`, the door) is `packed_mud` with packed mud above
it for three more courses; `[4318,115,1500]` (step 2 `to`, step 3 `from`) is
`azalea_leaves`. The route itself is walkable and Erika is reachable — these
are coordinates in the record that name the block rather than the cell a player
occupies. Worth correcting because the next audit, and the next author, will
read them as positions.

### D3 — a jump off Brock's decoy gantry the route does not declare

`(1817,147,3673)` → `(1817,146,3676)`, a two-block leap over open air from the
north (dead-end) gantry onto the finished stone stack. It is a way *down*, not
a way past a gate, and the leader is not made reachable by it. It is recorded
because the route claims the north gantry "stops in mid air" and it does not
quite: a player who takes the wrong gantry has a shortcut back.

---

## The four things the builders flagged

**1. Blaine's soul-sand bubble column.** Under the model it is a correct
one-way lift: no cell of the shaft has a move to the cell below it (proved
twice — once on the emitted blocks, once by a mutation that swaps the soul sand
for `polished_blackstone` and makes the descent appear), and the up-chain is
unbroken with four ways to step off the head at y119 onto the gallery at y120.
So it is **not** a way in, and the vault is not reachable without the leap.
**But it is not a way out either**, because nothing can reach its foot (D8).
The record names "a ladder in the casing" as the fix for the lift failing; the
lift is not what fails. *Whether a bubble column really carries a player
thirteen blocks is a runtime fact and is still unproven; see "Not covered".*

**2. Koga's escape chute against `rules.max_fall`.** Measured from the cell the
record names: a **15-block fall from `(4585,132,2484)` landing on
`minecraft:hay_block` at `(4585,117,2484)` for 2.4 damage** (about one and a
quarter hearts). `data/gym_interiors.json` `rules.max_fall` is 12 and its own
`max_fall_why` says "a fall longer than this **must land on hay_block**". It
does. **The rule is satisfied, not broken.** It was unenforced — `tools/
gym_buildings.py` checks no falls at all and says so — and it is enforced now
by the `declared_fall` check, which measures every route step whose `how` is a
fall or a drop and fails a long one that does not land on hay or water. The
other declared falls: Brock's chute 14 blocks onto hay (2.2), Erika's court
9 blocks onto hay (1.2), Koga's tank 6 into four of water (0), Blaine's leap 14
into three of water (0).

**3. Every gym's extent against its suppression box**, not just Surge's. Two
fail: gym1 by five rows of z (4,530 cells), gym3 by one (840 cells). See D1/D4.
The check is now per-cell against `data/spawn_suppression.json`, not per-bounds.

**4. Can a drop-jump off Blaine's stair tower reach the crown parapet?**
**No** — the audit reports no sprint-jump over a real void between any two rooms
of gym7 that the route does not already join. The reach table used is
deliberately generous (4 blocks level, 5 dropping one, 3 rising one, and a
run-off into open air resolved by the fall model), and the stair tower's head at
y119/120 is separated from the crown floor by the flue's parapet, whose coping
stands at y122. The one route into the crown is the parapet opening at x6174,
z4994–4996, which is the route's own step 4.

---

## What the old independent suite became

`tools/gym_interiors_independent.py` and
`tests/test_gym_interiors_independent.py` were **narrowed, not retired**.
`data/gym_interiors.json` now marks gyms 1, 3, 4, 5 and 7 `built: false`, so
`tools/gym_interiors.py` emits only Misty's gym 2 and the healer sweep. The
audit now takes its gym list from those `built` flags (`built_gyms()`), and the
suite parametrises on it, with a new test that fails if the built set and the
parametrised set ever disagree. Misty's gym 2 keeps every check it had: 28
passed, 1 xfailed (F6, her four unsupported lanterns, still open).

The mutations that could only be made against a demolished interior were
carried across to the new suite rather than deleted, one for one:

| retired from the interiors suite | carried to the buildings suite |
|---|---|
| deleting the water at Blaine's landing | `test_deleting_the_water_under_blaines_leap_is_caught` |
| Blaine's pool one block deep | `test_making_blaines_basin_one_block_deep_is_caught` |
| opening a wall between two rooms (gyms 1, 7) | `test_opening_a_wall_into_erikas_court_lets_the_canopy_be_skipped_and_is_caught` |
| the geyser as an ordinary water column | `test_the_geyser_is_a_one_way_lift_and_an_ordinary_water_column_would_not_be` |
| removing the masons' ladder (a trap) | `test_removing_the_ladder_out_of_erikas_court_makes_it_a_trap_and_is_caught` |
| a ladder turned to face the open air | `test_a_ladder_turned_to_face_the_open_air_is_caught` |
| Erika's one-high flooded drain | `test_a_one_high_flooded_hole_is_entered_only_from_water_deep_enough_to_swim_in` (synthetic) |
| two interiors writing the same cells | `test_two_buildings_writing_the_same_cells_is_caught` |

Two more mutations were retargeted inside the interiors suite rather than
dropped: the shaft that stops a block short of the hall floor, and a data file
naming a gym's columns, both now parametrised and computed from the audit's own
`Site` instead of Brock's hard-coded coordinates.

---

## What is different about this audit

- **Ground from the town plan and the heightmap, never a world.** The pad is
  the gym anchor's `level` in `data/placements.json` inside the lot and
  `tools/ground.py` (rounded) outside it. `WORLD_READS = set()`; a test asserts
  the file names no world artefact.
- **The player starts on the lot's perimeter at pad level, not at the door the
  record declares.** A building whose door is walled up cannot pass by naming a
  door. That is how D7 surfaced.
- **Jumps are modelled, not just standable cells.** A sprint jump clears four
  blocks level, five dropping one, three rising one; a gap needs a run-up
  behind the take-off; a run-off into open air lands where the fall model says
  and never past water on the way (that last rule is what stopped a sealed
  water column being read as an entrance).
- **"Not skippable" is tested by removing the room.** Every room the route
  names between the way in and the leader is closed off in turn; if the spawner
  is still reachable, the stage is optional.
- **The later stages are tested even when an earlier one is broken.** A second
  graph is seeded at the design's own waypoints, so Blaine's vault, his bubble
  column and Koga's chute could be measured although nothing can reach them.
  Findings from that pass carry their own codes (`trap_later`,
  `declared_fall`, `bubble`, `gap`) and say so.

---

## Not covered

- **Nothing here was run in Minecraft.** Validity is not behaviour. Needed as
  experiments, not pytest: that a soul-sand bubble column lifts a player
  thirteen blocks and sets them on the casing head; that
  `rctmod:trainer_spawner` on a redstone block spawns each leader and that the
  badge follows; that the jump reach table matches the game; that unsupported
  lanterns pop; that `/fill`-placed water behaves as the leak model says.
- **The demolition is not audited.** `tools/gym_demolish.py` is what clears the
  ground these buildings stand on; this audit assumes the pad, not the world
  the carve left behind.
- **No trainer seats exist yet.** All five `trainers` arrays are empty, so
  nothing here says a guard cannot be walked round.
- **The `no_build` boxes are authored and not wired.** Until a scene record
  exists in `data/scenes.json`, a player with blocks can build past every gate
  in all five buildings, and no test can say otherwise.
- **The palette is checked by namespace only.** The audit does not ask whether
  a block the buildings place is a spawn condition
  (`data/spawn_blocks.json`); adding that would need a C4 entry in
  `data/system_contracts.json`, which this agent may not edit.

## Two pre-existing test failures, unrelated to this work

Found while running the suite; neither is caused by anything here and neither
is in a file this agent may edit.

- `tests/test_system_contracts.py::test_contract_c4_every_tool_that_reads_the_spawn_conditions_is_accounted_for`
  — `tools/gym_interiors_independent.py` reads `data/spawn_blocks.json` and has
  no entry in `data/system_contracts.json` C4 `tools`.
- `tests/test_heightmap_provenance.py::test_every_provenance_key_in_world_json_is_documented`
  — `water_shaped_from` in `data/world.json` is not explained in
  `docs/.../HEIGHTMAP_PROVENANCE.md`.
