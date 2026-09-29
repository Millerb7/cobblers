# The authored gym buildings

The owner's redesign of 2026-09-29. `GYM_BUILDINGS_BRIEF.md` is the decision and the measured envelope; this
document is the **contract**: what a gym record may contain, what the generator does with each field, and what
the other four buildings must follow. Gym 1 (Brock) is written; gyms 3, 4, 5 and 7 are not.

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
