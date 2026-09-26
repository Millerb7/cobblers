# Foliage: mangrove marsh and jungle thickets

**Status: spec and generator code, not generated, not painted, not exported (2026-09-25).** The owner's playtest
notes 25 and 29 (`experiments/EXP-035-first-playtest/README.md`): "the swamp marshes need a way more distinct feel,
tall trees, vines everywhere, i want like mangroves" and "jungle isle should be thicker in some places". This extends
`FOLIAGE.md`; the forest types there are unchanged.

## 1. How foliage reaches the world, and which path this takes

Foliage is not command-placed and not re-applied. `tools/paint_maps.py` reads `data/foliage.json` and
`data/regions.json`, calls `tools/foliage.py place` for exact positions, and writes one `objects_<group>.png` per
object group plus `build/paint/manifest.json`. `tools/reexport.py --paint build/paint/manifest.json` builds a fresh
WorldPainter world from the canonical heightmap, `tools/worldpainter/paint.js` turns each group into a Custom Objects
layer of the `.nbt` files in `kits/structures/foliage/`, and the export writes them into the region files
(`REEXPORT.md` C4). **So this change reaches a world only at the next WorldPainter export**: a staging export first,
then the live re-export. Nothing in `tools/reapply.py` touches foliage.

## 2. What changes

Nothing about the existing forest types. Three **overlays** (new `data/foliage.json` `overlays`) are laid over named
sub-regions after every type and its debris are placed:

| Overlay | Sub-regions (density scale) | What it adds | Rule |
| --- | --- | --- | --- |
| `marsh_giants` | Marshy Marsh 1.0, Marsh Creek 0.45 | Tall trees: swamp giants (2x2 oak, about 17-23 tall, vine curtains 3-12 long) and tall mangroves (about 21-28 tall), in groves over half the marsh | 10 stems/ha nominal, patch noise at 160 blocks (top 50%), spacing 12 and 10 |
| `marsh_mangroves` | Marshy Marsh 1.0, Marsh Creek 0.35 | Mangroves on prop roots with hanging propagules and vines, root knots, mangrove scrub, vine-wrapped snags; mud and moss floor near the water | 60 stems/ha nominal, times 0.25 far from water rising to 1.0 at it (reach 50 blocks); spacing 6 |
| `jungle_thickets` | Jungle West 1.0, Jungle East 0.85 | Thickets: jungle trees 3.5 apart and mega jungle 8 apart, jungle bushes, fallen logs, a darker podzol and moss floor, denser jungle understory | 150 stems/ha nominal in patches (noise at 120 blocks, top 35%); nothing added between patches |

Why overlays and not edited types: `foliage.py` draws every type from one shared random stream in sorted order, and
tags noise by the type's index. Editing the drowned swamp or the jungle types, or adding a type, would re-roll every
forest that sorts after it, across the whole map. An overlay runs after everything and draws from its own stream
(the paint seed and the overlay id), so every other forest paints exactly as it did, and the diff stays in these four
sub-regions. The swamp oaks and snag fen stay; the mangroves and giants fill the gaps between them.

Rules the overlays keep (`tools/foliage.py`): the same pairwise spacing from every stem already standing, clear of
debris, landmark glades, settlement footprints plus 16, the 3-block block-scale water clearance, slope, and **5 blocks
either side of every route centreline** in `data/routes.json` (`overlays.path_clearance_blocks`). Route 6 (Koga to
Sabrina) crosses the marsh; prop roots and knees are solid, so without the lane a dense mangrove wood could wall the
critical path. They never paint a biome: every Marshy Marsh pool entry in `data/spawns.json` is conditioned on
`minecraft:swamp` and every jungle entry on `minecraft:jungle` or `sparse_jungle`, so a `mangrove_swamp` biome would
silently empty the marsh's encounters. `foliage.py` refuses an overlay with a `biome`.

## 3. The new objects (generated, `tools/foliage_objects.py`)

24 objects in 6 groups, seeded code like the rest of the generated library, vanilla 1.21.1 blocks only:

| Group | Objects | Height | Build |
| --- | --- | --- | --- |
| `mangrove` | 6 | about 11-17 | 1x1 mangrove trunk raised 3-5 blocks on a root column and 5-8 arching prop roots (feet 3-5 out, muddy roots at the foot), a slight lean, 2-3 branches to leaf clouds, hanging propagules under 5% of the leaves, vine chains on 12% of open leaf sides, moss on the roots |
| `tall_mangrove` | 4 | about 21-28 | the same, trunk 13-18, 7-9 roots reaching 5-6, 3-4 branches, longer vines |
| `mangrove_scrub` | 3 | about 6-7 | a knee-high mangrove on 4 roots |
| `swamp_giant` | 4 | about 17-23 | 2x2 oak on log knees, 4-5 limbs to a flat crown 13-16 across, a drooping leaf rim, vine curtains on 30% of open leaf sides (3-12 long), vines climbing the trunk, moss on the knees |
| `vine_snag` | 3 | 6-10 | a dead oak or mangrove trunk wrapped in vines |
| `root_tangle` | 4 | 2-3 | a knot of 3-5 low root arches with moss |

Vines and propagules never reach the two lowest layers, so they are not ground contact and not in the eye-level
measure. Every root foot is on the object's lowest layer, which WorldPainter's extend foundation carries down to
uneven ground. `ground_radius` for a tall mangrove comes out around 6-7, so its whole 13-15 block square must be
allowed ground: they stand on dry land at least 3 blocks from water and overhang it, never in it.

**Not used, on purpose.** Mod blocks: nothing in `base-pack/inventory/` lists block ids for VanillaBackport, and
nothing else in the manifest was checked for a hanging-moss block, so none is used. `minecraft:firefly_bush`
(VanillaBackport, checked with `setblock` per `FOLIAGE.md`) was left out of the root knots: whether WorldPainter 2.27.1
treats that unknown block as solid and extends it down as a foundation is not known. In-water mangroves:
`paint.js` can set `ATTRIBUTE_SPAWN_IN_WATER`, but what WorldPainter then does with a flooded column is unverified
(`FOLIAGE.md` records objects landing on the water surface), so it is an experiment, not this spec.

## 4. Blocks that decide spawns (`data/spawn_blocks.json`, `data/spawn_block_policy.json`)

| Block the change writes | In `spawn_blocks.json`? | Note |
| --- | --- | --- |
| `minecraft:mangrove_propagule` | **yes**, via `#cobblemon:flowers` (combee, comfey, cutiefly, ribombee, vespiquen, vivillon, herds; nearby blocks) | New. The policy's foliage entry allows the `flowers` tag for foliage objects but does not name the propagule in its block list: worth adding by whoever owns the policy. The marsh already carries flowers (blue orchids in `swamp_floor`), so it adds no new kind of condition there |
| `minecraft:oak_leaves` (swamp giants) | yes (applin line, herds) | Already throughout the marsh in the vanilla swamp oaks |
| mangrove log, leaves, roots, muddy roots, vine, moss carpet, stripped logs, jungle wood and leaves, mud, moss, podzol | no | none |
| water | yes | none added: no terrain or water change |

Our compiled pools carry no block conditions; the blocks matter only to upstream spawns, which the sub-region
suppression covers.

## 5. Multiplayer

No triggers, chests or state. Dense mangroves are slow going: the route lane keeps Route 6 open, but a party leaving
the lane climbs over roots. The jungle ruins' footprint plus 16 stays tree-free, as before.

## 6. Measure, generate and export

Not run in this session (no shell was available to the session that wrote it). In order:

1. `python tools/foliage_objects.py generate` writes the 24 new `.nbt`/`.json` files and rewrites `library.json`;
   the existing generated objects must come out byte-identical (`git status` shows only additions and
   `library.json`). Until this runs, `tests/test_foliage_objects.py::test_committed_generated_objects_match_the_generator`
   fails and `paint_maps.py` stops on the missing groups.
2. `python -m pytest -q tests/test_foliage_objects.py tests/test_foliage_place.py tests/test_paint_maps.py tests/test_foliage_validator.py`
   and `python tools/validate_data.py`.
3. `python tools/paint_maps.py --source-root C:/Users/wnd/Documents --out build/paint`. `build/paint/stats.json`
   now carries `foliage.overlays` (per overlay: stems added, trees per hectare before and after over its area and its
   dense part, eye-level sightline before and after) and `foliage.by_subregion` (trees and other objects per
   sub-region before and after the overlays, on dry ground). One run measures both sides, because the overlays do not
   change what the types place.
4. `canopy.npz` changes, so `data/visibility.json`'s canopy sha goes stale again. By geometry none of its 11 canopy
   claims has observers or a target near these four sub-regions; the one to look at is `gorge_hamlet_from_its_leg_canopy`
   (Route 7 leaves Sabrina's town beside Marsh Creek). `data/foliage.json` `landmark_candidates` (the Route 8 candidate)
   records 16 of 41 points on the Koga-to-Sabrina leg, which crosses the marsh: that figure may drop. Check with the
   check mode of `tools/visibility_claims.py` and `tools/landmark_trees.py check`, then refresh deliberately.
5. A scratch export of the new objects, as `FOLIAGE.md` §1 did for the first library: prop-root feet extended to the
   ground on a slope, vine curtains and propagules present, and whether WorldPainter's rotation turns vine faces.
6. Staging export and dry run (`REEXPORT.md`), then the live re-export.

## 7. Not verified

- Nothing is generated, painted, measured or exported; every count and density above is a parameter, not a result.
- How the marsh reads in game, and whether 60 mangroves per hectare near water is too thick to walk.
- Whether WorldPainter rotates vine faces. If it does not, a rotated curtain hangs on the wrong side of its leaf: it
  still renders, but a block update beside it can break it.
- Whether WorldPainter's plant layers place on `MUD`.
- `tools/validate_data.py` does not check overlays; `foliage.py` refuses a malformed one at paint time instead.
  Validator coverage belongs to `test-author`.
- `tools/world_heights.py` `COVER` has `mangrove_roots` but not `muddy_mangrove_roots` or `mangrove_propagule`, so
  a drift report on an exported marsh would read root feet as ground.
