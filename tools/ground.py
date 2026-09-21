#!/usr/bin/env python
"""The ground a placement stands on, from the heightmap. Never from a world.

THE RULE. Every tool that decides where something goes takes its ground from here: the canonical
heightmap in data/world.json, rounded. It never reads the surface of a world save to decide a
position, because a world save holds whatever was built into it last, and a tool that reads its own
output as ground builds on top of itself.

That has happened twice:

  - the Displaced City cavern plan was regenerated from a world that the previous cavern carve had
    already damaged, so the plan followed the damage rather than the terrain
  - on 2026-09-20 tools/place_town.py seated Brock's houses on the highest ground under each
    footprint, read from the world, which on a rebuild was the last build's roofs: the houses
    climbed six to ten blocks above their own street

Reading a world to CHECK a result is different and still right: tools/town_audit.py and the verify
passes read the world because the world is what the player sees. Reading it to DECIDE is what this
module replaces. tests/test_ground_rule.py fails if a placement tool starts doing it again.

WHY ROUNDED. Measured on 2026-09-20 against the staging export cobblers-dryrun, over 40 random 64 by
64 windows of dry land away from anything built (163,840 columns):

  round(h)   matches the exported ground at 99.85% of columns (the rest one block low, at water edges)
  floor(h)   matches at 52.18%, one block low at the other 47.7%
  ceil(h)    matches at 47.74%

So round(h) is the ground WorldPainter writes, and floor(h), which tools/town_plan.py and
tools/cavern_plan.py used as their heightmap fallback, was a block low across half the map.

  python tools/ground.py <x> <z>          # the ground at one column
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

import terrain as T

ROOT = Path(__file__).resolve().parent.parent


class Ground:
    """(x, z) -> the integer Y of the ground block a fresh export has at that column."""

    def __init__(self, source_root=None, world_path=None):
        world_path = world_path or str(ROOT / "data" / "world.json")
        source_root = source_root or os.environ.get("COBBLERS_SOURCE_ROOT")
        self.heights, self.world = T.load(world_path, source_root)
        self.ox = self.world["grid"]["origin_x"]
        self.oz = self.world["grid"]["origin_z"]

    def __call__(self, x, z):
        return int(np.round(self.heights[int(z) - self.oz, int(x) - self.ox]))

    def box(self, x0, z0, x1, z1):
        """A (z, x) array of ground Y for the inclusive box."""
        h = self.heights[int(z0) - self.oz:int(z1) - self.oz + 1, int(x0) - self.ox:int(x1) - self.ox + 1]
        return np.round(h).astype(int)


def load(source_root=None, world_path=None):
    return Ground(source_root, world_path)


if __name__ == "__main__":
    g = load()
    x, z = int(sys.argv[1]), int(sys.argv[2])
    print("ground at %d, %d is y%d (heightmap %.2f)" % (x, z, g(x, z), g.heights[z - g.oz, x - g.ox]))
