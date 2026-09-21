"""The floor verify chooses a building's corner columns from floor blocks only. A snow layer or a fern at a template's
ground layer is not floor (vanilla's #minecraft:replaceable), and choosing it as a corner reported a gap that was not
there: 80 false gaps at Northlight and the tea town on 2026-09-21. False gaps train a reader to ignore the verify."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import place_town as PT  # noqa: E402


def test_snow_layers_plants_and_carpets_are_not_floor():
    for name in ("minecraft:snow", "minecraft:fern", "minecraft:short_grass", "minecraft:tall_grass",
                 "minecraft:large_fern", "minecraft:white_carpet", "minecraft:air", "minecraft:jigsaw",
                 "minecraft:wheat", "minecraft:poppy", "minecraft:oak_sapling", "minecraft:torch"):
        assert not PT.is_floor(name), name


def test_real_floor_blocks_are_floor():
    for name in ("minecraft:stone", "minecraft:spruce_planks", "minecraft:snow_block", "minecraft:dirt_path",
                 "minecraft:cobblestone", "minecraft:bamboo_mosaic", "minecraft:oak_slab"):
        assert PT.is_floor(name), name
