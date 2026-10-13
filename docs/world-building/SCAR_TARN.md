# The Scar Tarn

The owner, 2026-10-11: the Scar is good, but the mountain is empty. A recess on its north-west side could hold a pond,
with trees and alpha Pokemon "down to have taken over the afflicted area". Record `data/scar_tarn.json`, generator
`tools/scar_tarn.py`, pack `cobblers_scar_tarn`, step **R9ST** (before R9E), tests `tests/test_scar_tarn.py`.
Optional, off every route. Status: the tarn and its own wood were applied to staging 2026-10-11 (STATE "Latest install");
the arms below (2026-10-12) are in the repository only. The live world predates the Scar's pad and has neither.

## Where, measured (canonical heightmap, rounded; `python tools/scar_tarn.py report`)

- Mt Vessu's summit is (1864, 760) y300; the Scar pad is y280 at (2110, 950). A priority-flood fill over x1700..2500
  z550..1300 (window edge open) finds two closed hollows over 40 columns: this one and a larger one on the NE side
  (x2154..2354 z648..793, 14,903 columns, fill level y223, depth 30), which is not the north-west recess.
- The hollow: x1965..2071 z686..744, two dips (y228 at x1988 z727; y229 at x2017 z707), lowest rim y239. It lies 237
  blocks north of the Scar's centre, about 95 north of the old avenue's end (z806) and 43 below the pad.
- Water at y237: 1,887 columns, 6,710 water blocks, deepest 9, bbox x1966..2068 z688..743. Natural freeboard at the lowest
  rim is two blocks (y239 is exactly the hollow's own limit; y240 escapes); the pack lifts 267 of the 324 rim columns to y238
  so a world one block under the heightmap still holds the water.
- Route 3 is 769 blocks away, Route 4 688 (`data/route_paths.json`, nearest point to the seed).

## What is built

Vanilla blocks only, `blocks.ids` in the record (the generator refuses any other): the pond with a clay/mud lining, a
moss/mud/coarse-dirt/gravel bank; 190 trees round the water and, in the arms, 846 more (spruce, a few 18-24 block spruce
elders, birch near the water, dead snags),
9 fallen logs, 10 mossy boulders, five stubs of `mossy_stone_bricks`/`cracked_stone_bricks` (the Scar's own palette), moss,
podzol and coarse dirt thinning to 34 blocks out, ferns, grass, azalea and moss carpet on the dirt-tag ground. No lamps (the
Scar is dark by design). Water is the one spawn-condition block, whitelisted for `scar_tarn` in
`data/spawn_block_policy.json`. Nothing is written within 24 blocks of an x/z another data file authors.

## The wood's arms (2026-10-12)

The owner, looking at the tarn on the map: "The forest should expand toward the Scar, maybe envelop some of it, and then down
the back and side of the mountain." (`growth.arms` in the record; `build_arms` in the generator.) The tarn's own wood is
layer 1 and its function `build.mcfunction` is byte for byte what it was (`tests/test_scar_tarn.py` pins its sha256), so a
re-apply adds trees and moves none. The arms are layer 2: five lobes, each a spine of (x, z, radius) knots, each its own
function `arm_<lobe>.mcfunction`, the same kinds, heights, ground cover and plants, a tree probability that falls from the
spine to zero at the radius (a natural edge). Slopes decide where the wood can go: a trunk needs the 3x3 around it to vary by
two blocks or less (the tarn's own wood allows three), so the wood thins and stops at the cliffs.

- **To the Scar** (`to_the_scar_west`, `to_the_scar_east`): from the tarn's south shore over the ramp (y240 to 280) onto the
  pad's north apron, then round the pad's west rim to the cross road's latitude and round its north-east rim. The pad (y280,
  radius 150 round (2110, 950)) is the Scar's own ground; this is its outskirts, so the wood envelops the city's north,
  west and east edges and stops at the ruins. Three brick stubs in the Scar's palette per lobe.
- **Down the back** (`down_the_back`, `down_the_back_east`): the north face. The hollow's north wall (z636 to 700) is bare
  cliff; under it the face is a gentle 20 to 30 degree slope down to the Mt Vessu outline at z556 to 600, and the 24-block
  clearance from that outline leaves a band z584 to 634. The wood runs down into it.
- **Down the side** (`down_the_side`): the EAST flank, where the pad's feather falls away east of the Scar. West of the pad the
  mountain drops 100 blocks in 50 (x1830 to 1880) under Thundurus's shoulder and inside the outline's margin there is no
  gentle ground, so the heightmap leaves the east. (Chosen from the heightmap, not from the brief: the brief did not say which
  side.)

Kept clear (the keep-clear net the generator carves each lobe with, and the audit re-derives on its own): every x/z, line and
box any other record authors, 24 blocks (the tarn's own rule): the Scar's streets and the avenue's approach, Thundurus's
portal, chamber and spawn-free box (plus the avoid box `thundurus_plug_and_approach`), Wardenhold's burrow, the mines' faces,
every route path; the city's core (the hull of the three house-lot bands, so the houses and the plaza stay readable); and
everything outside the Mt Vessu outline. No light block, no spawn-condition block but water (still the tarn's only). The one
exemption: the Scar's town footprint box (a 300 x 300 planning square) is `rules.authored_box_exempt`, replaced by the
geometric rules above.

Step R9ST runs the tarn's function and then each arm (hold, wait, function, release); a re-run over the wood already in the
world adds the arms and rewrites the tarn identically, but R9ST writes the four ward mimic blocks back over the Habitat
Blocks, so run it as `run --only R9ST,R9E`. The alphas (wards, pools, band) are untouched.

## The alphas

Four ACTIVATED Habitat Blocks (`scar_tarn_grove_north_ward`, `_grove_south_ward` on the banks, `scar_tarn_waters_west_ward`,
`_east_ward` in the bed), at R9E, keeping up to 2 (land) or 1 (water) alive within 16 each: at most 6. Pools in
`data/spawns.json`: `scar_tarn_waters` (Quagsire, Lanturn, Gyarados, submerged) and `scar_tarn_grove` (Lycanroc, Gabite,
Haunter, grounded), levels 29-33, every entry carrying `"modifiers": "alpha=true"`. The compiler
(`tools/compile_spawns.py` `compile_habitat`) writes that as the habitat spawn's `modifiers`.

Why it should make an alpha: the Cobblemon 1.8.0 jar's `HabitatSpawn.createSpawnDetail` copies `modifiers` into the
spawn detail's PokemonProperties and `PokemonProperties.commonApply` calls `Pokemon.setAlpha(true)` when `isAlpha` is set
(javap of `Cobblemon-fabric-1.8.0+1.21.1.jar`, 2026-10-11). NOT seen in game.

The band 29-33 is one over Mt Vessu's table (22-28) and two under tier 3's next cap (35). In game the number a player
fights is not this one: the jar's alpha level-matching sensor re-levels a wild alpha within 32 blocks to the party's
highest level +8 (21-30) or +12 (31-45) (`data/encounter_design.json` rules.hearts.alpha_level_matching, relayed from that
file, from bytecode and not seen in game). Beaten alphas pay gems (`data/alpha_spoils.json`) and the blocks refill, so the
tarn is a repeatable gem source: the owner's call.

## Needs a running server before it is a fact

1. The pack lands: `presence_audit` on the `scar_tarn` probes (38).
2. The water holds in game, and whether the cold biome ices the surface (it probably does; it is scenery).
3. The activated blocks keep their pools alive, and what a spawned entity is: an alpha at all (`/data get entity` on one
   for the alpha flag, or its size).
4. The player's level against it (the sensor), and that it is optional in practice.

## The audit (tools/scar_tarn_audit.py)

Written for the tarn by an agent that built none of it. The forest rules (`check_forest`) were added 2026-10-12 by the session
that built the arms (the audit's rules are its own code, read from the emitted functions, the heightmap and the OTHER
records' geometry, and it is proven by mutating the GENERATOR in `tests/test_scar_tarn_audit.py`; it is not the owner's
independent reviewer). It checks each arm: trunks on ground within the record's relief, above the record's floor, standing at
the ground; every arm column inside the outline; the Scar's streets (half-width + 4), ruin footprints and plaza (8), the
city's core hull; Thundurus's spawn-free box (20) and portal (24); no light, no fire, no spawn-condition block but the
whitelisted water; each function inside the server's limits. Not covered: the world (the heightmap stands in for the
save), what a mod or a donor template put there.

## What an audit must check (independent, by an agent that built none of it)

- WATER CONTAINMENT, from the emitted `build.mcfunction` alone, replayed over a world made of the heightmap: every water
  block has water or a solid block on its four sides and below, with the unwritten ground at the heightmap and one block
  under it; also at 0 and 2 under at the lining. The builder's own test does 0 and 1 with its own replay; the audit should
  derive "solid" without `NOT_SOLID` and walk the water from the surface down, and flood the written world from the surface
  to prove nothing reaches a column outside the window.
- The pond's shape against the heightmap (a flood from the seed at y236 columns) and the two-block spill margin.
- The alphas against the cap: the pool band and the species' evolution levels from the jar, the band against
  `data/progression.json` for the area, and the claim about the sensor, which is bytecode-only.
- Our list is not the world: anything a mod, a donor template or an earlier pass put in x1923..2110 z655..794 (the
  Scar's old avenue ends at (2110, 806), 24+ blocks south of the nearest written column).
