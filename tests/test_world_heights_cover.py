"""tools/world_heights.py: tree trunks, canopy and plants are cover, not ground, when reading a saved world's surface.

Synthetic chunk dicts only (plain dict sections with a block_states palette and packed data, the shape
nbt.region_chunks yields); no region files, no real world, no heightmap.

Not covered: the block names a real WorldPainter 2.27.1 export or a server-generated chunk actually contains
(e.g. bee_nest, moss_carpet, hanging roots or modded foliage would still be read as ground), and whether
the drift report on a painted world is now within tolerance. That needs an extract/compare run on an exported world.
"""
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import paint_maps as PM  # noqa: E402
import world_heights as WH  # noqa: E402

AIR = "minecraft:air"


def _pack(indices, bits):
    """Anvil 1.16+ packing: `64 // bits` indices per long, low bits first, no spanning."""
    per = 64 // bits
    words = []
    for i in range(0, len(indices), per):
        word = 0
        for j, v in enumerate(indices[i:i + per]):
            word |= int(v) << (j * bits)
        words.append(word)
    return b"".join(struct.pack(">Q", w) for w in words)


def _section(y, palette, grid=None):
    """grid: (16,16,16) palette indices [y, z, x]; a single-entry palette carries no data array."""
    bs = {"palette": [{"Name": n} for n in palette]}
    if len(palette) > 1:
        bits = max(4, int(np.ceil(np.log2(len(palette)))))
        bs["data"] = _pack(np.asarray(grid).reshape(-1), bits)
    return {"Y": y, "block_states": bs}


# ------------------------------------------------------------------ is_cover


# Protects: tree parts and plants are cover; if any of these reads as ground, a painted forest reports its canopy
# (or a flower) as the terrain surface and the drift report shows trees as terrain errors.
@pytest.mark.parametrize("name", [
    "minecraft:spruce_leaves", "minecraft:oak_leaves", "minecraft:azalea_leaves", "minecraft:flowering_azalea_leaves",
    "minecraft:oak_log", "minecraft:spruce_log", "minecraft:jungle_log", "minecraft:mangrove_log",
    "minecraft:stripped_birch_wood", "minecraft:dark_oak_wood", "minecraft:stripped_spruce_log",
    "minecraft:short_grass", "minecraft:grass", "minecraft:snow", "minecraft:azalea", "minecraft:flowering_azalea",
    "minecraft:tall_grass", "minecraft:vine", "minecraft:mushroom_stem", "minecraft:red_mushroom_block",
])
def test_tree_parts_and_plants_are_cover(name):
    assert WH.is_cover(name) is True


# Protects: real ground blocks stay ground; an over-broad suffix or set entry would push the surface down to
# whatever lies beneath, or leave columns without ground.
@pytest.mark.parametrize("name", [
    "minecraft:stone", "minecraft:grass_block", "minecraft:podzol", "minecraft:cobblestone", "minecraft:mud",
    "minecraft:dirt", "minecraft:sand", "minecraft:snow_block", "minecraft:basalt", "minecraft:moss_block",
    "minecraft:mossy_cobblestone", "minecraft:oak_planks", "minecraft:packed_mud", "minecraft:gravel",
])
def test_ground_blocks_are_not_cover(name):
    assert WH.is_cover(name) is False


# Protects: every plant tools/paint_maps.py asks WorldPainter to place is cover. Assumption (not verified against
# WorldPainter): its plant names snake-case to the block id, except "Dead Shrub" -> minecraft:dead_bush.
def test_every_painted_plant_is_cover():
    rename = {"Dead Shrub": "dead_bush"}
    names = {n for plants in PM.PLANT_SETS.values() for n in plants}
    not_cover = []
    for n in sorted(names):
        block = "minecraft:" + rename.get(n, n.lower().replace(" ", "_"))
        if not WH.is_cover(block):
            not_cover.append((n, block))
    assert not not_cover


# ------------------------------------------------------------------ chunk_columns


def _tree_on_grass_chunk():
    """Section Y=4 (y 64..79): stone y64..69, grass_block y70, oak trunk y71..75 at (x8, z8), leaves y74..79 around it,
    short grass at y71 elsewhere. Section Y=5 (y 80..95): solid spruce_leaves, single-entry palette (no data)."""
    palette = [AIR, "minecraft:stone", "minecraft:grass_block", "minecraft:oak_log", "minecraft:oak_leaves",
               "minecraft:short_grass"]
    g = np.zeros((16, 16, 16), np.int64)
    g[0:6] = 1
    g[6] = 2
    g[7] = 5
    g[10:16, 5:12, 5:12] = 4
    g[7:12, 8, 8] = 3
    return {"Status": "minecraft:full", "sections": [
        _section(4, palette, g),
        _section(5, ["minecraft:spruce_leaves"]),
    ]}


# Protects: ground under a tree is the grass_block, not the leaves or trunk above it, across a canopy that fills
# the whole section above (single-entry palette) and a trunk/crown inside the ground section (multi-entry palette).
def test_ground_under_tree_is_the_grass_block_not_the_canopy():
    ground, water, status = WH.chunk_columns(_tree_on_grass_chunk())
    assert ground.shape == (16, 16)
    assert (ground == 70).all(), np.unique(ground)
    assert (water == WH.NONE).all()
    assert status == "full"


# Protects: a column with only tree parts and air (a trunk over void, e.g. an unfinished chunk) has no ground,
# rather than reporting the log as terrain.
def test_column_of_only_logs_and_leaves_has_no_ground():
    palette = [AIR, "minecraft:birch_log", "minecraft:birch_leaves"]
    g = np.zeros((16, 16, 16), np.int64)
    g[0:8, 3, 3] = 1
    g[8:12, 2:5, 2:5] = 2
    chunk = {"Status": "full", "sections": [_section(2, palette, g)]}
    ground, _water, _status = WH.chunk_columns(chunk)
    assert (ground == WH.NONE).all()


# Protects: the canopy-over-water case keeps water above the real seabed: a mangrove crown over a flooded mud floor
# reports ground at the mud and water at the surface, not ground at the leaves (which would hide the water).
def test_leaves_over_water_keep_seabed_ground_and_water_surface():
    palette = [AIR, "minecraft:mud", "minecraft:water", "minecraft:mangrove_leaves", "minecraft:mangrove_log"]
    g = np.zeros((16, 16, 16), np.int64)
    g[0:3] = 1                        # mud y32..34 (section Y=2)
    g[3:6] = 2                        # water y35..37
    g[6:10, 0, 0] = 4                 # trunk out of the water
    g[10:13] = 3                      # canopy y42..44 over the whole chunk
    chunk = {"Status": "full", "sections": [_section(2, palette, g)]}
    ground, water, _ = WH.chunk_columns(chunk)
    assert (ground == 34).all(), np.unique(ground)
    assert (water == 37).all(), np.unique(water)
