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
| `z1` | G1, Dig company foreman | (3100, 88, 3270) | WSW | **Built**, but z1 ships no zone check (fails open, see the open item below) | No | out: (3097, 3271) y88 / in: (3106, 3267) y88 |
| `z2` | G2, Victory Road trailhead | (3548, 112, 5322) | S | **Built** | No | out: (3547, 5325) y112 / in: (3551, 5316) y112 |
| `z2_victory_road_descent` | Victory Road descent post | (3738, 87, 5082) | W | **Built** | No | out: (3735, 5081) y87 / in: (3745, 5084) y87 |
| `z2_rim_post_descent` | Rim post guard | (3877, 146, 3824) | S | **Built** | No | out: (3876, 3827) y146 / in: (3881, 3819) y145 |
| `z2_wilds_slip` | Wilds ranger | (4200, 95, 4300) | W | **Built** | No (broken ground, but it walks; see below) | out: (4197, 4300) y95, (4196, 4300) y96, (4195, 4300) y97 / in: (4207, 4301) y95, (4208, 4301) y94 bridged from y91, (4209, 4301) y95, (4210, 4301) y96 |
| `z4` | G4 | **(3700, 89, 2357)** since 2026-10-08; was (3600, 87, 2557), and (3600, 87, 2554) before 2026-10-03 | S | Held (G4's caught-count dialogue) | **Re-sited 2026-10-08 with behind_league**, which moved from z2560 to z2360 because the League stood in Z4 (`data/rift_zones.json` `measured_defects[the_league_stood_in_the_apex_zone]`). Same shape: the walkway runs through the wall's two rows (z2358-2359) and its outer mouth (z2360) opens on Z5's side, north of the League's building. Knock box z2357-2359, exit z2355, arrival z2354 (lanes x3698-3703, y90). The 2026-10-03 move to z2557 is kept in the guard's `superseded` record. | out: (3698-3703, 2360) y90 / in: (3698-3703, 2350) y90 |
| `z5` | G5 | (3573, 85, 2680) | W | **Built** from the next apply (released 2026-10-03: `rift_crisis_resolved` is set by the relic hall's binder, and this re-cut fixed its wall; `zones.z5.superseded_needs_walls`) | **Yes: wall re-cut, 1 column.** league_gate's column (3581, 2680) left open; the inner approach runs one column further, onto it. The guard does not move. | out: (3570, 2680) y85 / in: (3580, 2680) y85, **(3581, 2680) y86 (new)** |

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

## OPEN, the owner's decision: re-site the guards nobody without the pass can reach

`measured_defects[gates_stand_deep_inside_their_own_zone]`, a strict xfail. These guards stand inside their own
zone's boxes by the distance below (the record's `edge_distance`, measured from the traced mask), and every
column of their knock box and its edge is inside the zone, so a player without the pass is turned back by the
zone check long before reaching the guard:

| Gate | Guard at (x, z) | Inside its zone by | Zone has another reachable guard? |
|---|---|---|---|
| `z1` | G1 (3100, 3270) | **141 blocks** | **No** |
| `z2_victory_road_descent` | (3738, 5082) | 144 blocks | Yes, G2 at the trailhead |
| `z2_rim_post_descent` | (3877, 3824) | 62 blocks | Yes, G2 |
| `z2_wilds_slip` | (4200, 4300) | 153 blocks | Yes, G2 |

**Until it is decided, a zone with no reachable guard fails OPEN** (the owner, 2026-10-03: a player turned back
with no way through is the worse failure). `tools/rift_zones.py unreachable_zones()` finds such zones from the
geometry alone (no knock box of the zone lies outside its boxes or on their edge) and `build` ships them no zone
check, knock or exit advancement; their walls, gatehouses and placeholders are still built. **Today that is z1
only: z1 is open to everyone.** z2 keeps its checks, because G2's knock box at the trailhead is outside z2 and a
passless player can earn the pass there; the three posts let through only players who already hold it. The z1
check installed on staging on 2026-10-02 goes when the next `install` replaces `cobblers_rift_zones`.

Re-siting is the fix: move a guard to where its zone begins (G2's move on 2026-10-01 is the precedent), or carve
the zone's boxes back to the guard. The moment G1's knock box touches z1's edge, z1 ships its checks again with
nothing to flip, and the xfail XPASSes once all four are re-sited.

## Flying checklist

1. Built today, look and walk: G1 (3100, 88, 3270), G2 (3548, 112, 5322), the descent post (3738, 87, 5082),
   the rim post (3877, 146, 3824), the wilds slip (4200, 95, 4300).
2. Built from the next apply (R9Z): G5 (3573, 85, 2680) with league_gate's opened column at (3581, 2680).
   Held, nothing built: G4's new site (3600, 87, 2557), on behind_league's line at z2558-2559.
3. Not verified anywhere: that the advancements fire, that `tp` lands where the data says, that the barrier
   cannot be jumped or pearled.
