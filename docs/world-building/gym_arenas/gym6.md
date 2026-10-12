# Gym 6: Sabrina, the Hall of Lenses and the Observation Well

`data/gym_arenas/gym6.json` (schema `gym_hall/1`, read by `tools/gym_arenas.py`; `SCHEMA.md` has the format and
`docs/world-building/GYM_WALKTHROUGH.md` the design for all eight). Authored 2026-10-09 as the walk-through
replacement for the carved Observation Well (schema `gym_arena/1`, applied to staging 2026-10-09, kept in the record
under `replaces.arena`) and for the Hall of Lenses building (`data/gym_buildings/gym6.json`, now `superseded_by`).
Offline checks only: nothing here has been built in a world or seen in a running game.

## The reading

Sabrina is the Rift researcher; her town is the region's place of study (`TOWN_CHARACTER.md` gym6_town: calcite,
smooth quartz, polished diorite, purpur as the accent). The carved Well's vibe was kept and expanded: the tallest room
of the eight, a vertical room with a great biconvex tinted lens hung over the floor and its image let into the floor
as a purpur ring round the two Pokemon marks, Sabrina on a purpur dais under THE EYE (purpur lid, quartz white,
froglight pupil). What changed is the way there: no descent of 31 courses and no tube, one building on the lot.

## The walk (all measured from the generated model, `tools/gym_arenas.py check`)

Lot 6180..6212 x 3302..3334, pad y97, facing south; the hall stands on x6180..6211, z3305..3331. 44 moves from the
street cell (6196, 97, 3335) to the challenger's stand (6197, 98, 3312); up four, down four, all half steps.

1. **The door**, on the town's axis (x6196), into **the reading stacks**: a foyer 30 by 7, seven courses clear,
   shelving along the divider wall. The Archive Reader stands in the middle of it.
2. **Three eye-arches** in the divider wall (z3323). Two are blind reading cells (the west one is where the iron door
   out of the Well lets out); the east one, under THE EYE, goes through. The Gallery Medium stands just inside it.
3. **The turret stair**: four half steps up, five wide (the old ladder is gone), into **the lens chamber** (floor y101,
   five by twelve). The Stack Warden stands at the stair's head.
4. **Three apertures** in the chamber's west wall (two courses thick): only the middle one goes through; the other two
   are one course deep. The Lens Keeper stands in front of the true one.
5. **The Observation Well**, the last room, 23 by 13 and 22 courses clear (y98..119): the aperture opens onto a terrace
   at the east end (19.0 from Sabrina, past forceBattleMaxDistance + 1 = 17) and a broad stair of four takes the
   player to the floor. The lens' lowest course is y113, sixteen over the floor (Hatterene, the tallest, is 6.13).
   Sabrina's seat is (6183, 101, 3312) in the dais top; the dais is four courses and runs wall to wall.

Out past her by the **iron door** in the Well's south wall (6190, 98..99, 3319), opened by the stone button inside the
Well at (6191, 99, 3318) and by nothing outside, into the west reading cell and back through its arch; or back the way
you came (the stair is walked both ways).

## Why two cells differ from the other halls

- The west wall stands on the lot's edge (x6180) so the dais reaches x6181. Sabrina is outside
  `single_leader.rollout`, so a Challenge spawner stands beside her seat, and a Challenge cell inside the old
  building's bounds (which begin at x6182) is a replaced seat to both the builder and the independent audit: it would
  be called dead the moment the cycle set it. It is at (6181, 101, 3312).
- No amethyst and no end rod: `tools/gym_trainers.py`'s movement model has no row for either (it fails closed), so the
  rim and the bands are purpur and the lamps are the town's pearlescent froglight.

## Takedown

`gym6_takedown` fills the carved Well's bounds (6176..6215 x 64..89 x 3304..3335) and the last two courses of its
descent tube (y90..91) with stone; the hall's first part clears the lot above the pad (y97..128), stones y92..96 under
the old building, and writes every cell of the old building's bounds.

## Juniors (`python tools/gym_trainers.py check --gym gym6`: proved)

Archive Reader (6203, 98, 3327) d4.0; Gallery Medium (6208, 98, 3322) d3.0; Stack Warden (6207, 102, 3316) d2.5;
Lens Keeper (6206, 102, 3312) d2.5. Pass order 01, 02, 04, 03, tops 42, 43, 44, 44, all under Sabrina's 45.

## Not verified

Everything in a running game: the iron door's redstone, the stair feel, the sightlines through the aperture, the
exterior mass from the axis. The audit's body model and the movement model are models.
