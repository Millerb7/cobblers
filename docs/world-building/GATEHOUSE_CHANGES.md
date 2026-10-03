# Rift gatehouses: what changed shape (2026-10-03)

The owner's call, 2026-10-03: *"Fix the gatehouses ... A player who teleports in and cannot walk out is the
worse failure ... Pick whichever route is cheapest and record which gatehouses change shape, so I can look at
them when I fly."*

Source of every row: `data/rift_zones.json` (zones.*.guard / zones.z2.posts, re-traced by
`python tools/rift_zones.py trace`), measured against the canonical heightmap (`tools/ground.py`). Nothing
here ran in Minecraft. **Held** gatehouses are not in any world: R9Z does not build them until their zone's
`needs_*` field goes, so at a held row's coordinates you will see bare terrain (or whatever an earlier apply
left there; not checked, no world was read).

Centre = the guard's block; y = the walkway's floor feet level (guard ground + 1). Approach columns are
`[x, z, feet y]`; "bridged from yN" means the floor is filled up from yN.

| Gatehouse | Guard | Centre (x, y, z) | Faces out | Built by R9Z today? | Changed shape on 2026-10-03 | Approach (cut/bridged columns) |
|---|---|---|---|---|---|---|
| `z1` | G1, Dig company foreman | (3100, 88, 3270) | WSW | **Built** | No | out: (3097, 3271) y88 / in: (3106, 3267) y88 |
| `z2` | G2, Victory Road trailhead | (3548, 112, 5322) | S | **Built** | No | out: (3547, 5325) y112 / in: (3551, 5316) y112 |
| `z2_victory_road_descent` | Victory Road descent post | (3738, 87, 5082) | W | **Built** | No | out: (3735, 5081) y87 / in: (3745, 5084) y87 |
| `z2_rim_post_descent` | Rim post guard | (3877, 146, 3824) | S | **Built** | No | out: (3876, 3827) y146 / in: (3881, 3819) y145 |
| `z2_wilds_slip` | Wilds ranger | (4200, 95, 4300) | W | **Built** | No (broken ground, but it walks; see below) | out: (4197, 4300) y95, (4196, 4300) y96, (4195, 4300) y97 / in: (4207, 4301) y95, (4208, 4301) y94 bridged from y91, (4209, 4301) y95, (4210, 4301) y96 |
| `z4` | G4 | **(3600, 87, 2557)**, was (3600, 87, 2554) | S | Held (G4's caught-count dialogue) | **Yes: guard moved 3 blocks south.** The walkway now runs through behind_league's two rows (z2558-2559); outer mouth z2560 opens on the League's side. No wall column moves. Knock box z2557-2559, exit z2555, arrival z2554 (all x3600, y87). | out: (3600, 2560) y87 / in: (3600, 2550) y87 (were z2557 and z2547) |
| `z5` | G5 | (3573, 85, 2680) | W | Held (`rift_crisis_resolved` has no invoker) | **Yes: wall re-cut, 1 column.** league_gate's column (3581, 2680) left open; the inner approach runs one column further, onto it. The guard does not move. | out: (3570, 2680) y85 / in: (3580, 2680) y85, **(3581, 2680) y86 (new)** |

## Why these routes, and what each cost

Counts are block positions whose final block differs, from simulating every emitted wall and gatehouse
function's own `fill`/`setblock` lines in R9Z's order, before and after.

- **G4: moved, 87 block positions** (56 no longer written, 10 newly written, 21 with a different block).
  behind_league runs z2558-2559 at x3600; the old gatehouse (walkway z2547-2556) stood entirely north of it,
  so nobody on the League's side could reach the knock box. The cheaper-looking route, re-cutting the wall
  (open (3600, 2558..2559), add wall at (3599, 2557) and (3601, 2557)), is 68 positions: four wall columns of
  17 blocks, y86 to the crest at y102. **Rejected:** it leaves the mouth and the gap (z2557-2559) inside Z4's
  boxes and outside the knock box, so once z4's zone check is installed a player walking up without the pass is
  turned back before the guard can answer. Moved, the mouth is in Z5's boxes and every column from it to the
  guard is the knock box.
- **G5: wall re-cut, 16 block positions** (13 no longer written, 3 different). The record said G5 could not be
  walked; measured again before fixing, **it could**: the inner approach cut on 2026-10-02 let a player sidestep
  north onto the ground beside the wall. What was left was the column straight on from the inner mouth being
  league_gate obsidian, so a passed player walking straight out of the walkway walked into a wall. `trace` now
  carries an approach through its own zone's wall (`tools/rift_zones.py` `mouth_cut`), and `build` leaves
  every approach column out of the wall. Moving G5 instead would have moved the whole gatehouse.
- **The five built gatehouses: no change.** All five walked before and after. The wilds slip's broken ground
  is its 3-column cut outside and 4-column cut/bridge inside, listed above; it is walkable both ways and was
  left alone (re-siting it would cost a whole gatehouse).

## What was checked (`tests/test_rift_zones_apply.py`, over the heightmap, from the emitted functions)

- All seven gatehouses, built and held, with every wall up: outside to the knock box and back; arrival into
  the zone; zone to the exit box; and, new, a player walking **straight on** off each end of each approach steps
  onto ground. The strict xfail on `held_walls_do_not_meet_their_gatehouses` is gone; the record says `fixed`.
- The barrier is the only way past both gatehouses that sit in a wall (G4, G5), with a generator mutation
  (no side walls) that opens a way round both.
- `rift_zones.py walkable` 7/7, `tools/b12_independent_check.py` 7/7, `report` no problem (2 owed).

## Not fixed, and not a shape: four guards nobody without the pass can reach

`measured_defects[gates_stand_deep_inside_their_own_zone]`, a strict xfail. G1 and the three z2 posts stand
141, 144, 62 and 153 blocks inside their own zone's boxes. A player without the pass is turned back by the zone
check long before reaching the knock box, so **no survival player can earn z1's pass by walking up to G1**
(z1 opens only if something else calls `z1/grant`), and the posts serve only players who already hold z2's
pass. G2 moved to the trailhead on 2026-10-01 for exactly this reason. Which way to fix it (move the guards to
where their zones begin, or carve the zones' boxes back to the guards) is a siting decision for the owner.

## Flying checklist

1. Built today, look and walk: G1 (3100, 88, 3270), G2 (3548, 112, 5322), the descent post (3738, 87, 5082),
   the rim post (3877, 146, 3824), the wilds slip (4200, 95, 4300).
2. Held, nothing built: G4's new site (3600, 87, 2557), on behind_league's line at z2558-2559; G5 (3573, 85,
   2680) with league_gate's opened column at (3581, 2680).
3. Not verified anywhere: that the advancements fire, that `tp` lands where the data says, that the barrier
   cannot be jumped or pearled.
