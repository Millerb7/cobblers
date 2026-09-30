# The authored gym buildings

The owner's redesign of 2026-09-29. `GYM_BUILDINGS_BRIEF.md` is the decision and the measured envelope; this
document is the **contract**: what a gym record may contain, what the generator does with each field, and what
the other buildings must follow. **All seven are now written** — gyms 1, 3, 4, 5 and 7 on 2026-09-29/30, and
gyms 6 (Sabrina) and 8 (Giovanni) on 2026-09-30, §6 below. Gym 2 is Misty's and is not touched.

| | |
|---|---|
| the tables | `data/gym_buildings/<gym>.json`, **one file per gym** |
| the generator | `tools/gym_buildings.py` (`report`, `build`) → `build/datapacks/cobblers_gym_buildings` |
| the demolition | `tools/gym_demolish.py` (`report`, `build`) → `build/datapacks/cobblers_gym_demolish` |
| the re-apply | `R16F` demolition, then `R16G` the buildings, both after `R16E` |
| the report | `derived/gym_buildings/report.json`, `trainer_seats.json`, `no_build.json`, `demolish.json` |

---

## 1. The contract for the four remaining buildings

**Write one file, `data/gym_buildings/<gym>.json`, and nothing else.** The generator is not per-gym: it reads
every record in the directory and emits `cobblers:gym_buildings/<id>` for each, and `R16G` lists the functions
from the directory, so a new file needs no change to `tools/gym_buildings.py` and no change to
`tools/reapply.py`. A building must stand inside its own gym lot from the town plan in `data/placements.json`
(the generator refuses `bounds` that leave it), take its ground from the lot's `level` or from
`tools/ground.py` and never from a world, carry exactly one `rctmod:trainer_spawner` powered by a redstone
block under it with two air cells over it, carry the leader's chest, carry **no healing machine**, reach the
spawner only by finishing the puzzle, and keep every route step inside vanilla movement (a one-block rise to
mount, no gap of four blocks or less where a sprint jump would skip a stage, and any fall over twelve blocks
landing on `minecraft:hay_block`). Do not touch gym 2, `data/gym_interiors.json`'s gym2 record, or anything in
Misty's town. Do not write the audit or the tests for your own building (CLAUDE.md principle 16).

---

## 2. The record

`schema` must be `"gym_building/1"` and `id` must equal the file name.

| field | required | what the generator does with it |
|---|---|---|
| `id` | yes | the function name: `cobblers:gym_buildings/<id>` |
| `settlement` | yes | looks the gym lot up in `data/placements.json` `settlements.<settlement>.plan.anchors` (the anchor with `role: "gym"`) and **fails** if `site.lot_rect`/`site.lot_level` disagree with it |
| `supersedes_donor` | no | carried into the report; the donor removed by `tools/gym_demolish.py` |
| `site.lot_rect`, `site.lot_level` | yes | checked against the town plan (above) |
| `site.ground.kind` | no | `lot_level` (default) uses `site.lot_level` for every column; `heightmap` uses `tools/ground.py`, rounded, per column. **The only two ways to get ground.** A building that steps down a slope uses `heightmap` |
| `site.footprint` `[x0,z0,x1,z1]`, `floor_y`, `stand_y` | yes | reported; `floor_y` is what the height in the report is measured from |
| `bounds` `[x0,y0,z0,x1,y1,z1]` | yes | **every** write must land inside it, and it must lie inside the lot rect. This is the whole spill guard |
| `leader.id`, `leader.name`, `leader.spawner`, `leader.chest` | yes | `leader.spawner` must be where the one `rctmod:trainer_spawner` is written, and `leader.id` must appear in its `TrainerIds` |
| `blocks` | yes | the allow-list. Any block a part writes that is not in it fails the build; `cobblemon:healing_machine` fails regardless |
| `rooms`, `route` | no | documentation and the report; **not checked**. `route` is where a building states each step and why it cannot be skipped, for the independent audit to disprove |
| `trainers` | no | copied to `derived/gym_buildings/trainer_seats.json` as a handoff for `trainer-balance-designer`. Nothing is placed from it |
| `no_build` | no | copied to `derived/gym_buildings/no_build.json`; the adventure-mode boxes are not wired here |
| `parts` | yes | the build, in order |

### The ops

Five, and no more. Each may carry `why`, which becomes a comment in the function.

| op | fields | what it emits |
|---|---|---|
| `fill` | `box` (6), `block`, optional `mode` (`replace`/`outline`/`hollow`/`keep`/`destroy`), optional `filter` | one `/fill`; oversized fills are split by `tools/function_limits.py` |
| `setblock` | `pos` (3), `block` | one `/setblock` |
| `scatter` | `positions` (list of 3), `block` | one `/setblock` each — for lanterns, barrels, fittings |
| `columns` | `cells` (list of `[x, z, top_y]`), `from_y`, `block` | one `/fill` per cell, `from_y` up to that cell's `top_y`. **This is how a stepped thing is authored**: a stair of courses, a row of piers, a wall whose top follows a slope, a run of window slits |
| `gable_roof` | `box` (`[x0,z0,x1,z1]`), `eaves_y`, `run` (`x` or `z`), `material`, optional `edge`, `overhang`, `gable`, `gable_from_y` | a roof of full blocks one course higher every two columns, ridge down the middle of `run`, the two gable triangles filled with `gable`, and an `overhang` course at `eaves_y` outside the box. It invents no stair facings: pass the block state you want as `material` and own it |

Order matters: parts are applied in sequence, and a later part overwrites an earlier one. That is how a plinth
band, a doorway or a hole in a floor is authored — fill the mass, then cut it.

### What the generator refuses to write

Fail-closed checks, not an audit. They are here because nothing else reports them.

1. a block outside the record's `blocks` list, and a healing machine anywhere;
2. a write outside `bounds`, or `bounds` outside the gym lot;
3. **a block vanilla would not keep standing.** The tool builds a voxel model of its own output over the pad and
   checks the final state: a ladder with nothing behind it (`facing=east` hangs on the block to its **west**), a
   hanging lantern with nothing above, a standing lantern with nothing below, a chain with neither, a falling
   block or a carpet/plate/torch over air. 31 lanterns stood in mid air across the five interiors this work
   replaces, because `setblock` does not check support and nothing reported it;
4. not exactly one trainer spawner; a spawner that is not where `leader.spawner` says, does not name `leader.id`,
   has no `minecraft:redstone_block` under it (EXP-013 E2: an unpowered spawner spawns nobody) or has anything
   but air in the two cells over it; no chest;
5. a command the server would refuse (`tools/function_limits.py`): an oversized fill, or a write into a chunk the
   function has not force-loaded.

**It does not check the route.** Whether a stage can be skipped, whether a trainer can be walked round and
whether a fall hurts are the independent audit's, and the audit is written by somebody who did not build.

---

## 3. Gym 1 — the Stoneworks Hall (Brock)

`data/gym_buildings/gym1.json`. **33 x 36, floor y141, 25 above the floor** (eaves y157, ridge y166), on the
levelled gym lot 1806,3656..1845,3703 with a 4/3/8/4 margin. The brief's envelope for the site is 89x89; that is
what the terrain allows, not a target, and the town plan's own lot is 40x48. The donor shell it replaces was
27x24 with one undivided oval room.

Brock's town is the plateau's builders, so the gym is their works hall: stone, polished andesite, cobblestone
and andesite with spruce timber, a timber roof, buttress posts outside the walls and a wall being raised inside.

**The puzzle is the building's own construction, climbed.** From the door the whole hall is legible: the masons'
loft five blocks up along the west wall, four stacks of stone under it of which only one is finished into a
stair, two plank gantries leaving the loft eastward, the half-built wall beyond them, and high on the cross wall
at the far end three slots, one of which is lit from inside. Stage 1 is the stair to the loft — the three decoy
stacks top two blocks under the deck, which no player can mount. Stage 2 is the choice of gantry: the north one
stops in mid air over the cutting floor, the south one runs eighteen blocks to the scaffold deck at the wall.
Stage 3 is the wall's unfinished east end, stepped course by course from y147 to y152, the only one-block rise on
a mass that is sheer everywhere else. Stage 4 is three one-wide jib beams over six blocks of open air — a sprint
jump clears four, so the beams are the only crossing, and missing one is an eleven-block fall onto the straw the
masons pack under the works, which costs nothing but the climb again. Stage 5 is the lit slot: the two dark ones
are one course deep and blind, the third goes through into the hoist shaft.

**The spawner is reached only by finishing.** Through the slot is a loading ledge, and a ladder on the shaft's
east wall climbs four to the gallery. The gallery is a floor at y155 across the whole width of the hall on solid
masonry, sealed by the cross wall to the north (which stands three courses higher than the beams), the hall's
own walls elsewhere and the roof above; its floor has exactly two holes, the ladder's and a chute back down.
Brock's `rctmod:trainer_spawner{TrainerIds:["kanto_brock"]}` stands on a redstone block set into that floor with
two air cells over it, his chest four blocks east. The ladder's foot is eleven blocks over the straw at the
bottom of the shaft, so nobody who takes the chute climbs back up it — they walk out of the archway at the
shaft's foot and start the climb again. There is no healing machine.

**The gate is real, and it is new.** The rejected interior could not gate Brock, because the donor template's
own spawner stood in the shell and nothing stopped a player walking to it. Taking the shell down removes that
spawner, and this one is the only `kanto_brock` in the town (a persistent `kanto_brock` anywhere awards the
badge: verified on staging 2026-09-24, `docs/STATE.md`).

**Not verified.** Everything above is geometry in a generated function. Nothing has been seen in a running game:
not the climb, not the beams, not the spawn, not the light through the slot.

---

## 4. The demolition

`tools/gym_demolish.py` acts on every gym `data/gym_interiors.json` marks `superseded_by` — gyms 1, 3, 4, 5 and
7 — and **refuses gym 2 by name**. For each it writes one function that sets the whole of that gym's `dig` box
and the whole of its donor shell's box back to `minecraft:stone` where the column is under the ground and to air
where it is over it. The ground is the gym lot's `level` from the town plan on the levelled pad and the
heightmap (`tools/ground.py`, rounded) outside it — never the world, which matters more here than anywhere
else, because the world under these five gyms currently holds the carve the tool is undoing.

The shell removal takes the template's walls, floor, nine command blocks, pressure plate and its own trainer
spawner with it. It does not take entities: if somebody has stood on Brock's plate before the shell came down,
the "Kanto Map Guide" villager it summoned survives and has to be removed by hand.

`data/gym_interiors.json` keeps those five records — the demolition is driven by their `dig` and
`shell.expect_box` — with `built: false`, so `tools/gym_interiors.py` no longer emits them and `R16E` no longer
runs them. `R16E` still runs the healer sweep over all eight shells and still builds and runs gym 2.

---

## 5. Two things the next author must settle first

1. **Surge's site.** The brief measures gym 3 as "23x23 only, y174..197, 23 blocks of fall" from the heightmap.
   The town plan in `data/placements.json` says his gym lot is `[1722, 1388, 1752, 1432]` — 31 x 45 — **levelled
   to y174**, which if the prep really cut it is a flat pad and not a hillside at all. The two disagree and the
   disagreement decides whether his building steps down a slope or stands on a pad. Settle it before authoring
   (the town's own `status` line records which prep steps were built), and if the pad is real use
   `"ground": {"kind": "lot_level"}`; if the fall is real use `"heightmap"` and author the levels with `columns`.
2. **Gym trainers.** No seats are authored for Brock, deliberately: unavoidability is a claim about where a
   player can physically stand, and the model that settles it (`tools/gym_interiors_independent.py`) belongs to
   whoever audits, not to whoever builds. The `trainers` array is supported and lands in
   `derived/gym_buildings/trainer_seats.json` for `trainer-balance-designer`.

---

## 6. Gyms 6 and 8 — the last two (2026-09-30)

The owner: *"GYMS 6 AND 8. Sabrina's and Giovanni's have no interior. **Sabrina's was blocked on a per-player
design — redesign it shared like the other six.** Independent audit before either applies."*

Both are one new record each, in the same `gym_building/1` schema, and **nothing in `tools/gym_buildings.py`
was extended**: the tool reads every record in the directory and `R16G` lists the functions from it, so two new
files needed no code change. The op vocabulary in §2 was enough for both.

### The one thing both records do that the first five do not

`tools/gym_demolish.py` acts only on gyms that `data/gym_interiors.json` marks `superseded_by`, and **gyms 6
and 8 have no such record** — their entries are `built: false` with no `dig` and no `shell` box, because
nothing was ever carved under them. So no demolition step runs on these two lots, and each record **takes its
own donor shell down**: an air fill over the pad and a stone fill under it, both sized to cover the donor's
whole box (`gym6_gym_building` at 6183,96,3306..6209,112,3329; `gym8_gym_building` at
3560,111,6403..3583,127,6429, computed from `data/placements.json` through `tools/place_donor.py`). The shell's
own `rctmod:trainer_spawner` goes with it, which is what makes each record's spawner the only one of its
leader in its town.

### The envelope, from the lot and not from the terrain

| gym | leader | lot (the envelope) | pad y | raw ground under it | **binding constraint** |
|---|---|---|---|---|---|
| gym6 | Sabrina | **33 x 33** `[6180,3302,6212,3334]` | y97 | y95..97 | the spawn-free box, z3304 |
| gym8 | Giovanni | **33 x 33** `[3556,6400,3588,6432]` | y112 | y110..112 | the spawn-free box, z6431 |

Both pads are levelled to the **top** of their raw range, so the prep is a small cut and a two-course fill —
which is what each town's own `prep_note` says. `"ground": {"kind": "lot_level"}` for both.

**Neither record changes `data/spawn_suppression.json`, and that was a design constraint, not an afterthought.**
`gym_sabrina` is `[6176,3304,6215,3335]` and `gym_giovanni` is `[3552,6400,3591,6431]`; both are already whole
8-blocks, and in both cases the box does **not** cover the whole lot (Sabrina's misses the lot's two
northernmost rows, Giovanni's its southernmost). So the buildings were fitted inside the boxes rather than the
boxes grown to the buildings. Growing one has to be an outward snap to the 8-block grid or
`tools/suppress_inherited_spawns.py` fails closed at install, which cost a cycle on 2026-09-30 at four other
gyms. Building inside costs nothing.

### Gym 6 — the Hall of Lenses (Sabrina)

`data/gym_buildings/gym6.json`. **27 x 25, floor y97, ridge y124**, on the levelled lot with margins 3/3/5/3 and
a one-course eaves overhang. One tall calcite hall; a reading gallery **four wide as a closed ring** at floor
course y104; a ladder turret standing on the gallery's north strip; a sealed lens chamber at floor course y111
with Sabrina at the centre of a quartz lens let into its floor.

**The per-player design is retired and what replaces it is THE EYE.** Nothing in the record is instanced, lit
for one player, or held in one player's state. The eye is one purpur panel with a pearlescent-froglight pupil,
set in the fabric of the building three times — over the stack that reaches, over the arch that goes through,
and over Sabrina's seat. It is a thing in the world that says which way, the same for everyone, in the family
of Brock's lit slot and Misty's three mouths.

Three gates, each a different mechanism:

1. **The reading stacks.** Four stacks of record shelving rise out of the hall floor. One runs east along the
   well's south edge with tops y98..y103 and reaches the gallery. The other three top at y102 — feet y103
   against a gallery whose walking level is y105, a **two-block rise**, which vanilla does not allow and no
   sprint jump covers (three blocks up one, nothing up two). The quartz posts under the gallery stop at y102
   and are capped by its own soffit at y103, so none of them can be stood on.
2. **The eye arch.** A calcite screen two courses thick closes the gallery's north strip over its full height.
   Three recesses; two are one course deep with the screen's second course solid behind them; the third goes
   through.
3. **The turret ladder.** y105 to y111 on solid quartz, through a floor that is unbroken everywhere else.

The way back is a **drop shaft**, one cell cut in the chamber floor over the gallery's east arm: a seven-block
fall for four damage.

### Gym 8 — the Gate of the South (Giovanni)

`data/gym_buildings/gym8.json`. **25 x 25, floor y112, walls to y122**, no roof: a walled muster yard open to
the sky. The gate mass is seven wide and the full depth of the yard, solid granite from the paving to y120,
**sheer on the yard side with no opening at any height**, and its top is the gate walk at y121 where Giovanni
stands. Eight courses over the yard, and nothing in the yard rises past y114.

Giovanni's gym is the gate (`data/placements.json`: *"for the eighth it is the one you have to go through to
leave"*), and he is a ground type, so the way past a shut gate is the way a garrison actually takes it: **you
go under the gate to get on top of it.** Three gates:

1. **The sap head.** The yard has one door and no stair. Three well heads are cut in its paving; two are
   cisterns one course deep, and the sap goes six down to a counter-mine. *The tell:* the sap alone carries a
   spruce headframe and a lamp.
2. **The shored heading.** Three headings are driven south off the drift, all one wide and two high and alike
   at the mouth. Two run two cells to a face. *The tell:* the west one alone is shored — a stripped-spruce
   crown down its whole ceiling course with three glowstones in it.
3. **The tower stair.** Fourteen courses cut up through the gate mass from the undercroft, each step closed
   above by the rock of the step in front, so no drop inside the slot is longer than one block.

The way back is the walk's open east edge: an **eight-block drop into the yard for five damage**, which is not
a way up.

### The twelve defects of `GYM_BUILDINGS_REVIEW.md`, answered rather than repeated

| the review's lesson | what these two records do |
|---|---|
| D2 a ladder's course through a floor must be re-cut as LADDER | **both ladders are the last block part in their record**, written after every floor that crosses them |
| D5 a waypoint must name the cell a player STANDS in | all twenty waypoints are standing cells; the audit reports every one "reached" |
| D6 a rise out of water must be one block | there is **no water and no lava** in either gym |
| D7 a rail must not stand where a stair arrives | gym 6 has **no rail anywhere**; gym 8's parapet starts at z6409 and the stair arrives at z6408 |
| the sprint-jump rule | no gate in either building is made of a gap — every gate is a two-block rise, a blind recess, or solid rock |
| every fall over 12 blocks lands on hay or water | **no fall in either gym is over 8**, so no hay is used and none is needed |
| D8 a room must have a way OUT | both leaders' rooms have two: the climb back, and a one-way drop |
| F6 31 lanterns stood in mid air | **no lanterns and no chains**; every light is a froglight or a glowstone let flush into a floor, a ceiling or a beam |
| leaves without `persistent=true` decay | no leaves |
| open-topped water flows out of its box | no water sources at all |

Neither record uses a rail, fence, wall or slab, because the audit's movement model reads every one of them as
solid and a passage furnished with them stops being a passage.

### Verdicts

```
python tools/gym_buildings.py build
  gym6 (Sabrina): 27x25, floor y97, 233 commands, 35,125 cells, 4 rooms, 5 route steps
  gym8 (Giovanni): 25x25, floor y112,  87 commands, 22,089 cells, 5 rooms, 5 route steps
python tools/gym_buildings_independent.py     # clean over 7 building(s)
```

**Not verified.** Everything above is geometry in a generated function and a model of vanilla movement.
Nothing has been seen in a running game: not the climbs, not the drops, not the spawns, not the badges, not
whether either building reads from the town as it is meant to.

### What these two still need

1. **The independent audit the owner asked for**, by an agent that built neither. `tools/gym_buildings_independent.py`
   reports clean, but the builder ran it; a reviewer should also ask the questions the tool does not — whether
   the eye and the headframe are legible in play, and whether either building's `rooms` boxes flatter its own
   `skip` check.
2. **The `no_build` boxes are authored and not wired.** Until a scene record exists in `data/scenes.json`, a
   player with blocks can pillar eight courses out of Giovanni's yard straight onto the gate walk, and out of
   Sabrina's well onto her gallery, and no test can say otherwise.
3. **No trainer seats.** Both `trainers` arrays are empty, so nothing here says a guard cannot be walked round.
4. **`data/gym_interiors.json` gyms 6 and 8 are untouched** and still carry no `superseded_by`. That is
   deliberate — the demolition is done in-function — but if `tools/gym_demolish.py` is ever made to cover all
   seven, those two records are where it would be said, and the in-function clearing fills would then be
   redundant rather than wrong.
