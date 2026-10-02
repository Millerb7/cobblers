# The Slip: measured against the terrain, and what it changes

**Status: a measurement and a design correction, 2026-10-01. Nothing built.** The barrier the owner asked
for cannot be built the way `DEEP_CITY.md` section 6 describes, because the terrain it describes is not
there. The measurements are below; the recommendation is that **unit 2 removes most of the need for
unit 3**.

## 1. What was asked

The owner, 2026-10-01: *"A PHYSICAL BARRIER BETWEEN THE MINING TOWN AND THE DEEP. They should not run
into each other. Terrain, not a wall if you can help it."*

`DEEP_CITY.md` section 6 already recommends one: **the Slip**, *"a landslide ridge across the spur floor
on the excavation/relic boundary (about x3290-3310; trace it from the two region masks, which overlap
there), 24-30 above the floor, sheer on the camp side"*, with a one-way down-lift on the relic side and
an up-lift gated on a flag. `data/rift_mines.json`'s `keep_clear` box `relic_area_and_the_slip`
(`rect [3280, 3150, 3440, 3440]`) already reserves the ground for it.

## 2. The premise that holds

The two region masks do overlap where the design says. Measured from `data/rift_regions.json`:

| Region | bbox | columns | ground min/median/max |
|---|---|---:|---|
| `rift_excavation_site` | x2950–3308, z3213–3327 | 30,839 | 87 / 88 / 98 |
| `relic_area_shrine` | x3285–3429, z3229–3384 | 13,875 | 86 / 90 / 100 |

They overlap in **x3285–3308**, which is the design's "about x3290–3310". That part of the design is
right.

## 3. The premise that does not: there is no spur, and there are no walls

Read off the canonical heightmap through `tools/ground.py` (rounded), never from a world.

**Along x3296, the line the design names**, ground runs y103 at z3190 down to y87 across z3280–3310 and
back to y97 by z3370. **Nothing anywhere in z3180–3400 rises above y110.** The columns at or under y95 —
the floor — run **z3219 to z3366, 148 of 220 sampled**.

**Across the whole area there is no neck to tie a ridge into.** Width of passable floor (ground ≤ y100)
in z, for each x from 3240 to 3380:

| x | floor z-range | width | ground |
|---:|---|---:|---|
| 3240 | z3179–z3379 | 201 | 87–100 |
| 3280 | z3188–z3387 | 200 | 87–100 |
| 3296 | z3198–z3387 | **190** | 87–100 |
| 3332 | z3201–z3411 | 211 | 87–100 |
| 3364 | z3223–z3404 | **182** | 87–100 |

The narrowest section in the entire span is **182 columns**, and the widest 211. The floor is one
continuous flat plain at y86–100 from the camp to the relic area and on to the Deep's west lip.

**So a ridge at floor+26 (crest ≈ y113) would have to run about 190 blocks and would still die in the
open at both ends**, on ground that only reaches y100. A player walks round it. It cannot seal, and no
amount of length fixes that, because there is nothing for it to meet.

## 4. And the haul road is not the corridor either

`data/rift_sculpt.json`'s `excavation_haul_road` entrance is at **(3100, 3270)**, gap 40, width 6, and
its own `why` says *"The excavation site's own way in and out, on the western arm."* It is the camp's
connection **west, to the rim** — not the way between the camp and the relic area, which is simply open
floor to the east. There is no corridor to bar.

## 5. What this leaves, and the recommendation

Three honest options. The first two are the owner's to choose between; the third is already on tonight's
list and makes the choice mostly moot.

1. **A ~190-block rubble ridge as scenery, with the zone check as the real enforcement.** This is what
   `DEEP_CITY.md` section 6 actually intends — it says so: *"Enforcement is still RIFT_ZONES section 4's
   zone check: move the Z1/Z2 line to the ridge."* The ridge reads as terrain and stops the two places
   running into each other visually, which is what the owner asked for; it does not seal, and a
   determined player walks round the end. **Note what that costs today: the Z1–Z5 zone system is built
   and deliberately not installed**, because `rift_crisis_resolved` has no setter anywhere (re-checked
   2026-10-01 across every remote branch). So this option ships scenery with **nothing enforcing it**
   until the finale's quest stage exists.
2. **Sculpt a neck into the heightmap.** `tools/rift_heightmap.py --apply` rewrites the canonical
   heightmap and `data/world.json`, re-pinning the sha256 every measured artifact in the repository is
   keyed to, and needs a full world re-export. It is the only option that produces a barrier that
   genuinely seals. It is also the one irreversible act available here and was deliberately not taken
   unsupervised.
3. **Put the relic site underground — which is unit 2, and it dissolves most of unit 3.** The owner's own
   next ask is *"THE RELIC SITE UNDERGROUND, reachable only through the Compact HQ, turned back by the
   zone check rather than barriers."* If the relic area stops being a surface neighbour of the dig camp,
   the thing the barrier was separating is no longer there: what remains on that floor is the camp and
   the Deep's west lip, and the Deep is a pit whose rim is its own edge. **Recommendation: do unit 2
   first and then re-ask whether unit 3 is needed at all.** On this terrain a barrier between two places
   on one flat plain is a 190-block wall across open ground; moving one of the places underground is both
   cheaper and the thing the owner already wanted.

## 6. Status of every claim here

| Claim | Status |
|---|---|
| The two masks overlap at x3285–3308 | **VERIFIED** from `data/rift_regions.json` bboxes |
| Ground along x3296 and the floor's extent | **VERIFIED**, `tools/ground.py` on the canonical heightmap, rounded |
| Floor width 182–211 columns across x3240–3380 | **VERIFIED**, same source, sampled every 4 blocks in x |
| Nothing above y110 in z3180–3400 at x3296 | **VERIFIED**, same source |
| The haul road is the western way in and out | **VERIFIED**, `data/rift_sculpt.json` `excavation_haul_road` |
| A crest at floor+26 ends in the open | **DERIVED** from the two measurements above |
| The zone system cannot enforce anything today | **VERIFIED**: `rift_crisis_resolved` has no setter on any remote branch, and `data/quests.json` says so itself |
| That unit 2 removes the need for unit 3 | **ARGUED, not verified.** It depends on where the relic site's new underground entrance comes out, which unit 2 decides |
