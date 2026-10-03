# The water-life audits: what they check, what they found, how we know they bite

2026-10-02, offline, test-author. The two independent audits of the water-life packs
(`docs/mechanics/WATER_LIFE.md`): `tools/lake_life_audit.py` (pack `cobblers_lake_life`) and
`tools/sea_life_audit.py` (pack `cobblers_sea_life`), with their shared replay in `tools/water_life_replay.py` and the
suites `tests/test_lake_life_audit.py` and `tests/test_sea_life_audit.py`. Nothing here ran in a game.

## Independence

Neither audit imports `tools/lake_life.py` or `tools/sea_life.py` or reads `derived/*/plan.json`. Each parses the
pack's `.mcfunction` files (`fill`, `setblock`, `fill ... replace <filter>`, `execute if block ... run fill`; any other
command fails the parse) and replays them in index order over a world built only from `tools/ground.py` (rounded) and
`tools/water_mask.py`'s painting rule. Basins are rasterised by scanline with `in_polygons`'s even-odd rule (a test
checks the two agree on a concave ring). Expectations come from `data/` and from the other packs' own functions
(`cobblers_portals`, `cobblers_legendaries`, `cobblers_sea_drift`, the other water-life pack).

Thresholds, and where each comes from:

| Threshold | Source |
|---|---|
| lake kelp top <= level - 3 | WATER_LIFE 1 "never within 2 of the surface"; the audit also refuses `top_below_surface` < 3 in the data |
| sea kelp top <= sea - 3 | the same sentence in WATER_LIFE 3 |
| Surf air distance 305 blocks | `data/blackout.json` water `surf_bonus_ticks` 900 + vanilla's 300 air ticks + one `pulse_ticks` 20 (the second, knockout hit) = 1220 ticks, at `data/ferries.json` `swim_model.speed_blocks_per_second` 5 (EXP-042's measured sprint-swim, relayed) |
| swim length | a guaranteed LOWER bound: the shallowest mouth cell's depth plus the 26-connected Dijkstra length through the cave's water divided by the worst-case octile ratio 1.1281 (computed, not tuned) |
| shell 4, cover 6 | WATER_BUILD_PLAN 6.4 "shell at least 4"; the data's own claimed cover (shell + export_tolerance + natural_seabed) is checked too |
| find seated within 2 | WATER_BUILD_PLAN 7.4 item 1 |
| find cluster link 16 | half of the closest two finds the data allows: (debris_line_spacing 40 - 2 x jitter 4) / 2 |
| reef radius 101 | `coasts.relic_reef` outer_radius max 96 + drop_width_blocks 5 |
| margins (docks 40, portals 16, ...) | the packs' own `exclusions` records, read as authored data |

## Results on the packs as built from `4e5d114`

- **Lake: 0 problems** over 337,275 commands. All nine painted lakes skinned; kelp tops at most level - 3, all age 25;
  every bed write at its column's ground; no light block, bubble column, soul sand or magma; every hook site lit
  within 8. The pack shares 175 columns with `cobblers_legendaries` (Mesprit's and Azelf's chambers and sleeves) and
  no cell: every lake write there stands at least 2 above a stone roof that pack wrote. Reported, not failed.
- **Sea: 9 problems in 4 checks**, all real (below). Everything else passes: 48 finds (12 Surf, 36 Dive: share 0.25),
  12 with a cache (0.25), all seated, none breaking the surface or near it inside a gate's clearance; the surfacing
  cave's mouth 29-30 deep, one flat pool at y62, 325 of 325 dry floor cells walkable from it, the swim's lower bound
  319.6 against 305; the waterline cave walkable from the beach (114 of 114 floor cells); no write in a town, Pacifidlog,
  the drift, a dock, a portal or a legendary zone; no column shared with any of the four other packs.

## Faults found in `tools/sea_life.py` (xfail(strict) in `tests/test_sea_life_audit.py`)

1. **Dry cells under the sea: places to breathe.** 4 oak doors, 4 red beds and 2 dark-oak fence gates, 33-41 deep, at
   (176-181, 28-29, 4119-4120), (4387-4388, 21-22, 7781-7786), (4300, 27, 7126), (7853, 25, 3638). None of the three is
   waterloggable, so its cell holds no water [A: vanilla, not run]: the bypass WATER_LIFE's Departures forbid for bubble
   columns. Written by the kits at `tools/sea_life.py:279-282` and `:314`; the builder's own flooded check exempts them
   on purpose (`:81` `DRY_IN_WATER`, `:1707`).
2. **Sea kelp within 2 of the surface.** 13,585 kelp tops at y60 (sea - 2). `data/sea_life.json`
   `shore.kelp.max_top_below_surface` 2, applied at `tools/sea_life.py:1487`, against WATER_LIFE 3 "never within 2 of
   the surface", which the lake pack reads as level - 3. The data says kelp cannot be stood on; the spec does not make
   that exception. An owner reading, or a one-number fix.
3. **Coral past the reef.** 1,294 coral writes 101-107 blocks from the reef's centre, on ground 3-14 deep, beyond
   outer_radius max + drop_width_blocks. `tools/sea_life.py:1522` takes `water_shape.reef_footprint`, which is the flats
   pass's keep-out mask (`tools/water_shape.py:2234`) with a -2/+6 margin (`:2180-2181`), as the reef's extent.
4. **A dark sea cave at S0.** 23 roofed floor cells of the waterline sea cave at block light 0 (e.g. (391, 59, 3502));
   the surfacing cave has none. Not a spec rule; `tools/sea_drift_audit.py`'s precedent. Hostiles can spawn in a cave by the first beach.

Not a fault, but worth knowing: the builder's own air rule measures the passage's centre line plus the full descent and
riser (`tools/sea_life.py:857-863`), which is not a lower bound on a swim. Mutation M3 below built a cave the builder
called 326.7 blocks long whose provable lower bound is 283.1.

## Mutation tests (the generator mutated, the data untouched, each reverted and the packs rebuilt byte-identical)

| | Mutation in the generator | Builder | Audit |
|---|---|---|---|
| M1 | `tools/lake_life.py` `lines()`: every kelp head emitted 2 blocks higher | built, 0 problems | `kelp` and `plants` fail: tops 2 under the surface, 53,120 heads on water, stems with no head |
| M2 | `tools/sea_life.py` `commit_find()`: every find block written 3 higher than its recorded base | built, 0 problems | `finds` fails: every find "not seated" (base 4 over its lowest ground), one breaks the surface |
| M3 | `tools/sea_life.py` `surfacing_cave()`: the route's first vertex 30 blocks east (a shorter passage); its mouth-depth and air checks were disabled too, and proved unnecessary (it measured a 23-deep mouth and 326.7 blocks) | built, 0 problems | `surfacing` fails: lower bound 283.1 against 305, and 7 mouth cells away from the data's mouth |

Synthetic mutations in the suites prove the rest bite: a thin roof (land 66 instead of 70) fails the shell; water
beside air fails the pool; an out-of-reach gallery is a trap; an open hole to the sky fails the seal; a passage swum
at 2 blocks a second fails the air rule; a find 4 over its ground is unseated.

## Not covered

Runtime, all of it: kelp, seagrass and coral holding in these biomes (P6), a lantern seen from the surface (P4), an
air chamber staying dry across a restart (P1), whether a door cell really gives breath (vanilla behaviour, read, not
run), and the swim speed itself (relayed from EXP-042). Offline gaps: the soil under a lake cane (paint decides it), the
`northgate_shortest` and `pacifidlog_nearest_land` gate lines (endpoints computed here by this audit's own rule, not the
water export's), spacing between finds (no label tells a vessel from debris in the functions), and anything a world
holds that the heightmap does not.
