# Flight findings, 2026-09-29 (morning, `cobblers-dryrun12`)

Recorded as they come in. **Nothing here is built on until the flight is finished** (the owner, 2026-09-29).
Each entry: what was seen, where, and whether it is confirmed from outside the game.

## From the session-start checks (before the flight)

### F0 — `DistantHorizons.toml` drift: the pregen radius is not in the repo

`install_check` reports the server's copy differs from `modpack/config/DistantHorizons.toml` in two places:

| key | repo | server |
|---|---|---|
| `generationMaxChunkRadius` | 256 | **320** |
| `serverId` | 0 | -932479244 |

`serverId` is runtime-generated and not ours to track. **`generationMaxChunkRadius` is a real, deliberate
change** — the overnight run raised it so the Distant Horizons pregen would cover the whole 400-region border,
which it did (`docs/MORNING_REPORT.md`: 477 files, 0 border regions missing). The repo never recorded it, so a
fresh install would put 256 back and the next pregen would fall short.

**Open:** does 320 become the repo value, or was it a one-off for the pregen? Not decided, not changed.

## From the flight



### F1 — Pacifidlog still reads "Jungle Isle" on the map

Owner, in game at `(5229, 128, 7389)`, looking at the new Pacifidlog site `(5160, 7380)`: the minimap
label for the place is **Jungle Isle**, the name of the landmark that the export removed. The town moved;
the map name did not follow it. Not investigated.

### F2 — a large dirt block mass beside the town

A tall solid dark column stands immediately west of Pacifidlog, roughly `(5150-5190, ?, 7400-7440)` by eye
from the screenshot, reading as a plain dirt/earth mass with a small structure on its top. It is not part of
the town's palette and looks like fill rather than a build. Not investigated.

### F3 — a sapling/tree floating in the air

A tree is suspended in the sky north-east of the town, well above sea level and unsupported, at roughly
`(5210, ~170, 7300)` by eye. The owner calls it "the sapling". Not investigated.

**Also in frame, already known and not a new finding:** the drowned ruins at sea level east of the town
(morning report stop 3, jungle ruins at y55-61, awaiting re-siting).

### F4 — saplings out of place on Long Isle too

Owner, same flight: saplings on **Long Isle** are also misplaced, so F3 is not a one-off at Pacifidlog.
Two sightings in two places suggests the sapling placement did not follow the water shape rather than a
single bad entry. Not investigated. (`docs/world-building/LONG_ISLE.md`; the sapling steps are `R5B`
themed saplings and `R3` world tree in the re-application.)

### F5 — lake beds are Rift-looking blocks, not sand

Owner, in game at `(3009, 173, 4008)`, over a lake on the east side: the bed reads as mottled dark
purple/violet blocks rather than sand or gravel, and he asks whether there is a reason the lakes do not
have sand floors. The shore above the waterline looks correct; it is the submerged floor that is wrong.
Whether this is every lake or this one is not established. Not investigated.

**Unverified hypothesis, recorded so it is not re-derived, NOT acted on:** the water shape pass changed
ground heights (19,027,615 columns) but a height change does not re-materialise the surface. Ground that
the new shape put under water would keep whatever block the earlier paint left there — which for anything
inside or near the Rift skin/biome paint (`R1`/`R1B`) would be exactly these blocks. If that is right, the
fix is a bed-material pass over newly submerged columns, not a re-shape. `data/world.json` has no
lakebed/substrate key, so the material decision lives in the water-shape tool, unread.

### F6 — Shrew Lake is half and half, split by a straight north-south seam

Owner, full-map view at `(2753, 56, 4623)`. **Shrew Lake is divided down the middle by a dead-straight
N-S line running through roughly x2760.**

- **West of the seam:** bathymetry is visible — depth contours, a graded shallow margin inside the beach,
  varied floor. This is what the water shape was supposed to produce.
- **East of the seam:** uniform flat dark blue to the shoreline, no contours, no visible margin.

A perfectly straight boundary is a processing boundary, not terrain. Two candidates, **neither checked**:
1. **Real** — the water shape / margin relief covered the west of this lake and not the east, i.e. a tile
   or job boundary in the shape pass. Would also explain F5, since unshaped floor keeps its old material.
2. **A map artifact** — the minimap rendering cached tiles on one side and Distant Horizons LOD on the
   other. The land either side of the seam is also rendered differently, which keeps this live.

**The cheap in-game test, for the flight rather than for me:** drop to the east half and look at the floor
and the shore. Graded margin and correct bed east of the seam = map artifact. Flat floor running to a wall
at the beach = real, and the water shape did not cover everything.

Minor, same frame: the biome at this point over the lake reads **Ocean**. Not established whether that is
intended for the lakes.

**F6 RESOLVED — not a coverage gap. The shape covered the whole lake.**

Checked against the water shape's own change mask, `derived/water_shape/changed.npy` (8192x8192 bool,
28.35% of the map changed), which is independent of the world and of the run's "0 problems":

| z | changed % per 50 blocks, x2400 -> x3100 |
|---|---|
| 4500 | 0 0 0 0 18 98 100 100 94 78 0 0 0 0 0 |
| 4560 | 0 0 0 34 100 100 98 100 100 96 100 96 6 0 0 |
| 4623 | 0 0 0 62 100 98 80 82 100 100 96 100 84 0 0 |
| 4700 | 0 0 0 0 40 98 100 100 98 100 98 72 0 0 0 |

Coverage is contiguous from about x2550 to x3050 at every z sampled. **There is no gap and no boundary at
x2760.** The canonical heightmap agrees: a transect at z4623 grades 76-66-59-57 into the basin on the west
and 63-67-72-80-99 out of it on the east — both margins shaped, no wall either side. x2760 is also not a
region-file edge (those fall at 2560 and 3072), so it is not an export tile boundary.

**Verdict: a client render artifact** — almost certainly Distant Horizons LOD against loaded chunks, which
also explains the land rendering differently across the same line. **Reading 2 of the two candidates.**

The one thing this does NOT prove is that the world received the shape everywhere; `changed.npy` is what
the shape computed, before the export. The owner's eyes on the east floor remain the cheap confirmation.
**F5 is unaffected** — the bed was re-shaped, so wrong bed material is a material question, not a coverage
one, and the hypothesis above stands.

## From the build (2026-09-29 morning), not from the flight

### F7 — `water_check` can pass a dive portal standing in a dry column

Found while re-siting `dive_watering_hole_floor`, not looked for. **`water_check` tests a landmark's
`extent.polygons`, but water is only painted inside its `basin_polygons`** (`tools/paint_maps.py` ~line 536
rasterises the basin polygons, marks every column where the canonical heightmap is below `level_y`, and
`tools/worldpainter/paint.js` raises water to that level on export). The two polygon sets are not the same.

So a dive portal sited in the gap — inside `extent` but outside `basin` — passes the audit and is dry in
the world. Nothing is wrong today: the re-sited portal at (2958, 5235) is inside both, checked. **Not
fixed, not investigated further.** It is a fail-open gap in a check, which is the kind that stays quiet
until it does not.

### F8 — agent worktree isolation made two audits lie, in opposite directions

Recorded because it will recur, not because it broke anything permanently.

- **Falsely CLEAN:** the portals agent reported its audit clean. Its worktree had no Rift skin pack, so it
  could not see that `dive_watering_hole_floor` sat inside the Rift's distortion tile. In the full checkout
  the same audit reported **85 problems**.
- **Falsely BROKEN:** the dig camp agent reported two `test_reapply_*` failures on a missing
  `derived/ambient/plan.json`. They pass in the full checkout; its worktree simply lacked `derived/`.

**The rule this establishes: an agent's audit result is provisional until integration re-runs it against a
full checkout.** Both directions cost real work today. `.worktreeinclude` carries no derived inputs and
`local_inputs.py hydrate` brings kits only (338 files).

## F9 — a guarded summon never re-levels an entity that is already there

Found applying the re-level to dryrun12, 2026-09-29.

`tools/legendaries.py` `placement_steps` emits the summon as

```
execute unless entity @e[tag=cobblers_leg_<id>] positioned <at>
  unless entity @e[type=cobblemon:pokemon,distance=..3]
  run spawnpokemonat <at> <species> level=<N> no_ai
```

The level is **not in the datapack**. It is baked into this one RCON
command at re-apply time, read from `data/legendaries.json`. The
`unless entity` guard exists so a re-apply does not stack duplicates,
and it does its job — which means re-running R14L after changing a
level is a no-op for every chamber whose legendary is still standing.

Five were: azelf, regirock, regice, regigigas, groudon. Each was
killed inside a forceload of its own chamber bbox before R14L re-ran,
and each then re-summoned at its new level. Uxie was absent, because
it was only sited today. `data/sapling_celebi.json` and R14C have the
same shape and the same trap: the Celebi read level 70 in the world
after R14C reported success, and needed the same kill.

**The rule this gives us:** changing a level, a species or any other
argument of a guarded summon is not applied by re-running its step.
The entity has to be removed first. A step that reports 0 problems has
only told you the guard held.

## F10 — four of Erika's lanterns stand on water and pop

`cobblers_gym_interiors/.../gym_interiors/gym4.mcfunction:84` sets
`minecraft:lantern[hanging=false]` at (4314, 97, 1498). The cell
directly below, (4314, 96, 1498), is water — it is over the cistern.

`setblock` does not check support, so the command succeeds and the
step reports no problem; the block then pops on the next update. The
cell reads air in dryrun12 now. Four lanterns in gym 4 are placed
`hanging=false`, and the class of defect is "a block that needs
support, placed over water or air".

This is the only miss in an 18-block sample taken from the portals,
gym interiors and rift mines packs and read back out of the world
(17/18 matched). It was found by probing the world, not by any audit:
the gym interiors audit compares the emitted functions with
`data/gym_interiors.json`, and by that comparison the lantern is
correct.

## F11 — the eight gym leaders fight with COBBLEVERSE's teams, not ours

Found 2026-09-30 by the agent that seated Victory Road's fights, while looking for how the League's
five reach the game. Independently re-checked in the full checkout before being believed.

`data/trainers.json` holds 63 authored trainers, among them `gym_01_brock` through
`gym_08_giovanni`, with the whole designed curve behind them: `generation_contract.gym_ace_levels`
is `[20, 25, 30, 35, 40, 45, 50, 55]`, and 12 authored boss rosters.

**None of it is emitted.** `grep -rl "gym_01_brock" build/ modpack/ server/` returns nothing. The only
files we write under an upstream leader's name are loot tables -
`cobblers_progression/data/rctmod/loot_table/trainers/single/kanto_brock.json` and the `first_win`
tables beside them. The trainer definitions themselves, `data/rctmod/trainers/kanto_*.json`, we never
write. `cobblers_trainers` emits rctmod trainers for the League five, the five mansion guardians, the
thirteen Routes 1-3 seats and Victory Road's ten - and not one gym leader.

So every gym battle in the game today uses the COBBLEVERSE roster. The reward for winning is ours;
the fight is not. The level caps, the ace levels, the type coverage and every balance decision
recorded for the eight leaders are sitting in a file nothing reads.

This is the fifth time (CLAUDE.md, "Work done in the repo that never reached the running game has
happened four times"): the spawn tables, five config overlays, the re-apply steps, the structures
pack - and now the leaders' teams.

**The mechanism to fix it already exists and is proven for the League.** On 2026-09-30
`tools/route_trainers.py` learned to write an override at the UPSTREAM path - our team and dialogue
on top of `kanto_league_lorelei` and the rest - precisely because the `kanto_league` template's
spawners are locked to the upstream ids and cannot be re-pointed. A gym leader is the same shape:
`gym1_cleared` binds to `kanto_brock`, the gym's `rctmod:trainer_spawner` names the upstream id, and
the override goes at `data/rctmod/trainers/kanto_brock.json`.

Not fixed in the commit that records this. It changes the difficulty of all eight gym fights at once,
which deserves to be a unit of its own with its own audit.

## F11 PROVEN IN GAME, 2026-09-30 — and the leaders had no rematch guard

**The owner fought Brock on `cobblers-dryrun12` and his Geodude came out at level 18.**
Cobbleverse's Geodude is level 16; ours is 18. So a datapack file at `data/rctmod/trainers/<id>.json`
DOES replace the roster rctmod loads, the override mechanism works, and all eight gym leaders' authored
teams are live. The assumption the whole fix rested on is now a measurement.

What that settles beyond the leaders: the same mechanism carries the Elite Four and the Champion
(`data/league_trainers.json`), and every balance number recorded for the gym ladder now describes the
game being played rather than a game nobody was in.

Before (upstream, read from `COBBLEVERSE-RCT-DP-v20.zip`): geodude 16, bonsly 16, onix 20, cranidos 18,
two Full Restores, `maxItemUses: 2`. After (ours): geodude 18, bonsly 18, cranidos 19, onix 20, every
one holding an item, no bag, `maxItemUses: 0`, `healPlayers: false`.

### The second finding, from the same session

The owner, immediately after: *"i can fight brock again if i send out my mon at him."*

CLAUDE.md records the standing limitation - "rctmod never refuses a rematch with a placed trainer" -
and our own cooldown in `tools/route_trainers.py` is the mitigation. **It covered the 28 trainers we
seat and none of the eight leaders.** The cycle is built from `placements()`, and a leader is not
placed by us: its gym's own `rctmod:trainer_spawner` spawns it, so it was never in the list the
cooldown is generated from.

What a rematch costs, measured rather than feared:

- **Items: nothing.** The per-win rctmod loot table we write for each leader is `{"pools": []}`,
  deliberately emptied (`data/progression.json` `upstream_neutralised`), and the badge and the TMs come
  from a `cobblers:first_win` table that fires once.
- **Battle XP: everything.** `data/level_cap.json` caps CATCHING, not battling. A leader who can be
  refought at will is a level-cap bypass, and stops being a gate.

Fixed the same day: `leader_cycle_lines()` adds a hold-off for all eight, keyed on the `gymN_cleared`
ADVANCEMENT instead of a quest field - the flag already exists and is already bound to the leader's
upstream id, so neither a molang callback nor a tag is needed. Misty's gym 2 is the one surviving
carved interior and has no `data/gym_buildings` record, so her seat comes from `data/gym_interiors.json`
`leader.expect_spawner_at`; she was the eighth and would otherwise have been missed.

It carries the same interim caveat as the seated trainers: `Cooldown` is entity NBT on a shared
trainer, so it cannot be held per player. A player holding the badge is protected; an unbeaten partner
beside them may have to start the fight by interacting. **Not yet seen in game** - the owner's rematch
is the evidence the guard was absent, not that the guard works.
