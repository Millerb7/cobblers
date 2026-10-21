#!/usr/bin/env python
"""Where an ACTIVATED Habitat Block's birds can stand: the Cobblemon 1.8.2 rule as a pure function of a block set.

Everything below was read from the bytecode of Cobblemon-fabric-1.8.2+1.21.1.jar (javap -c on the classes named in
each paragraph, 2026-10-21). Nothing here is a measurement of a running server; `docs/world-building/SAPLING_BIRDS.md`
"Where the birds stand" says which live observations the rule reproduces and which parts are still ASSUMED.

THE RULE (one activation of one block)
  1. ActivatedHabitatSpawning.activate: runs only while fewer than MaxSpawns of the block's own spawned entities are
     alive (spawnedEntityIDs), then asks its FixedAreaSpawner for min(MaxSpawns - alive, MaxSpawnsPerActivation).
  2. ActivatedHabitatSpawning.generateSpawnDetails builds that spawner with horizontalRadius = verticalRadius =
     SpawnRange. FixedAreaSpawner.getZoneInput: a box whose base is the block minus (r, r, r) and whose size is
     (2r+1)^3, so its centre (SpawningZoneInput.getCenter, base + size/2, floored) is the block itself.
  3. Spawner.constrainArea (default method, the one FixedAreaSpawner inherits) then moves that box vertically:
       - the centre column's block must be a VALID START: `isValidStartPoint`: the block AT the start is air and the
         block above it is passable (state.isPathfindable(a pathing type), which is true of air, false of a full block);
       - if it is not, the spawner tries start + 1, start - 1, start + 2, start - 2 ... up to the config's
         maxVerticalCorrectionBlocks (64 in modpack/config/cobblemon/main.json), UP FIRST at each distance, in the
         same x/z column only, and takes the first valid one;
       - if none is valid the area is dropped (constrainArea returns null): NO SPAWN;
       - the box is re-based to that valid y: baseY = y - height/2, i.e. it is centred on the valid start, not on the
         block.
     The block is a solid block itself, so a Habitat Block buried in a trunk is never its own start.
  4. CobblemonSpawningZoneGenerator.generate stores EVERY block of the box (no column-top-only scan); it only records
     per column whether the sky is seen.
  5. AreaSpawnablePositionResolver.resolve walks every cell of the box. A cell is skipped when it is within
     minimumDistanceBetweenEntities (8 in main.json) of any living entity in the zone other than the spawn's cause
     (the nearest player within 64 of the block). Otherwise the first calculator in the priority list that `fits`
     makes it a spawnable position. GroundedSpawnablePositionCalculator is FlooredSpawnablePositionCalculator with
     baseCondition = isSolidCondition (BlockState.isSolid) and surroundingCondition = isAirCondition (air, or not
     solid and not water and not in one block tag): `fits` is "the cell is solid and the cell above is air". So the
     candidates of `grounded` are EVERY standable top surface in the box (limb tops, ledges, leaf tops, the ground),
     not only column tops.
  6. FlatSpawnablePositionWeightedSelector picks a spawn detail by weight and then ONE of the positions that detail
     fits, by weight: SpawnDetail.weight is the same for every position (the habitat's own influence overrides no
     affectWeight), so the choice is UNIFORM over the grounded cells. The bird stands on the cell above the chosen one.

WHAT THAT MEANS FOR A TREE
  A nest buried in solid wood does not spawn at its own height. Its zone is centred on the nearest air in its column
  (up first). A trunk nest under a crown therefore spawns birds in the crown's box, and the density by height follows
  the number of standable cells at each height: wide leaf tops dominate over limbs.

NOT MODELLED (the model over-estimates cells in each case)
  - the 8-block spacing (it thins cells near already-spawned birds; applied only as a count, not placement),
  - terrain and neighbouring trees outside the tree's own block set (a flat floor at ground_y is the only terrain),
  - chunk loading, the cap of 9 x spawner.maxPokemonPerChunk Pokemon near the zone centre (16 * 9 here), light, time.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_JSON = ROOT / "modpack" / "config" / "cobblemon" / "main.json"

# blocks that are not `isSolid` (collision shape smaller than 0.73 on average and shorter than 1): the only ones the
# tree prefabs hold besides full blocks (counted over kits/structures/prefabs/trees: snow layers, dead bush, cocoa)
NOT_SOLID = ("minecraft:snow", "minecraft:dead_bush", "minecraft:cocoa", "minecraft:lightning_rod",
             "minecraft:vine", "minecraft:glow_lichen")


def config():
    """(maxVerticalCorrectionBlocks, minimumDistanceBetweenEntities) from the modpack's main.json."""
    c = json.loads(MAIN_JSON.read_text(encoding="utf-8"))
    return int(c["maxVerticalCorrectionBlocks"]), float(c["minimumDistanceBetweenEntities"])


def solid_name(name, props=None):
    """True for a block `BlockState.isSolid` accepts. Snow counts as solid only as a full 8-layer block."""
    if name in ("minecraft:air", "minecraft:cave_air", "minecraft:void_air"):
        return False
    if name == "minecraft:snow":
        return int((props or {}).get("layers", "1")) >= 8
    return name not in NOT_SOLID


class World:
    """A block set plus a flat floor. `solid` is a set of (x, y, z); everything else at or above floor_y + 1 is air."""

    def __init__(self, solid, floor_y):
        self.solid = solid
        self.floor_y = floor_y

    def is_solid(self, x, y, z):
        return y <= self.floor_y or (x, y, z) in self.solid


def valid_start(w, x, y, z):
    """Spawner.isValidStartPoint: air at the start, a passable block above it."""
    return not w.is_solid(x, y, z) and not w.is_solid(x, y + 1, z)


def centre_y(w, x, y, z, max_correction=None):
    """The y Spawner.constrainArea re-centres the zone on, or None when the area is dropped (no spawn)."""
    mc = max_correction if max_correction is not None else config()[0]
    if valid_start(w, x, y, z):
        return y
    for k in range(1, mc + 1):
        if valid_start(w, x, y + k, z):
            return y + k
        if valid_start(w, x, y - k, z):
            return y - k
    return None


def zone_cells(w, x, y, z, r=16, max_correction=None):
    """(centre y, [grounded cells (x, y, z) of the box]) for a block at (x, y, z), or (None, []) when it spawns nothing.

    A cell is a standing surface: solid, with air above. A bird stands at (x, y + 1, z)."""
    cy = centre_y(w, x, y, z, max_correction)
    if cy is None:
        return None, []
    base_y = cy - (2 * r + 1) // 2
    cells = []
    for cx in range(x - r, x + r + 1):
        for cz in range(z - r, z + r + 1):
            for yy in range(base_y, base_y + 2 * r + 1):
                if w.is_solid(cx, yy, cz) and not w.is_solid(cx, yy + 1, cz):
                    cells.append((cx, yy, cz))
    return cy, cells


def profile(cells, ground_y, bin_size=8):
    """{height band start above ground: share of cells} for a list of cells, bands of `bin_size` blocks."""
    c = Counter(((y + 1 - ground_y) // bin_size) * bin_size for _, y, _ in cells)
    n = sum(c.values()) or 1
    return {k: v / n for k, v in sorted(c.items())}


def off_ground(cells, ground_y):
    """Cells that are the floor itself (a bird there is on the forest floor, not in the tree)."""
    return sum(1 for _, y, _ in cells if y <= ground_y)
