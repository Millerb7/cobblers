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
        self.kind = "heightmap"
        self.ceiling = None

    def __call__(self, x, z):
        return int(np.round(self.heights[int(z) - self.oz, int(x) - self.ox]))

    def box(self, x0, z0, x1, z1):
        """A (z, x) array of ground Y for the inclusive box."""
        h = self.heights[int(z0) - self.oz:int(z1) - self.oz + 1, int(x0) - self.ox:int(x1) - self.ox + 1]
        return np.round(h).astype(int)


def load(source_root=None, world_path=None):
    return Ground(source_root, world_path)


# Three settlements do not stand on the heightmap. The Displaced City is on the cavern floor, 60 to 100 blocks under
# the surface, Relic Island is on an islet built over seabed, and the sea town floats on log decks at the sea level
# over the Sound. Their ground is still never read from a world: it is the measured plan data the tool that builds
# them computes from the heightmap (the sea town's decks are pure geometry from data/sea_town.json and the sea level
# in data/world.json). A settlement names it in data/placements.json as "ground": "cavern_floor", "islet" or
# "sea_deck", and gets that ground inside its box and the heightmap everywhere else.
GROUND_KINDS = ("cavern_floor", "islet", "sea_deck")


def cavern_floor():
    """(box, floor grid, ceiling grid) of the Displaced City cavern, from tools/cavern_plan.py's plan."""
    plan = ROOT / "derived" / "cavern" / "plan.json"
    grids = ROOT / "derived" / "cavern" / "plan.npz"
    if not plan.is_file() or not grids.is_file():
        raise SystemExit("no cavern plan: run python tools/cavern_plan.py --source-root <root> first")
    import json
    box = json.loads(plan.read_text(encoding="utf-8"))["cavern"]
    g = np.load(grids)
    return tuple(box), g["floor"].astype(int), g["ceiling"].astype(int)


def islet_top(g):
    """(box, top grid with NaN off the islet) of Relic Island's islet, as tools/islet.py builds it."""
    import islet as I
    import terrain as T_
    sea = int(T_.sea_level(g.world))
    cx, cz = I.CENTRE
    r = I.RADIUS
    bed = g.heights[cz - r - g.oz:cz + r + 1 - g.oz, cx - r - g.ox:cx + r + 1 - g.ox].astype(float)
    top, _ = I.island_top(bed, sea)
    return (cx - r, cz - r, cx + r, cz + r), top


def for_settlement(settlement, source_root=None, placements=None, base=None):
    """The ground for one settlement: the heightmap, with the settlement's own measured ground laid over its box."""
    import json
    g = base or Ground(source_root)
    doc = placements or json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    kind = (doc.get("settlements", {}).get(settlement) or {}).get("ground")
    if kind is None:
        return g
    if kind not in GROUND_KINDS:
        raise SystemExit("%s: unknown ground %r (known: %s)" % (settlement, kind, ", ".join(GROUND_KINDS)))
    h = g.heights.astype(np.float64, copy=True)
    if kind == "cavern_floor":
        (x0, z0, x1, z1), floor, ceiling = cavern_floor()
        h[z0 - g.oz:z1 - g.oz + 1, x0 - g.ox:x1 - g.ox + 1] = floor
        g.ceiling = {"box": (x0, z0, x1, z1), "grid": ceiling}
    elif kind == "islet":
        (x0, z0, x1, z1), top = islet_top(g)
        sub = h[z0 - g.oz:z1 - g.oz + 1, x0 - g.ox:x1 - g.ox + 1]
        sub[~np.isnan(top)] = top[~np.isnan(top)]
    else:
        # the sea town: every deck cell is ground at the sea level (tools/sea_town.py deck_ground)
        import sea_town
        level, deck = sea_town.deck_ground(g.world)
        for x, z in deck:
            h[z - g.oz, x - g.ox] = level
    g.heights = h
    g.kind = kind
    return g


if __name__ == "__main__":
    g = load()
    x, z = int(sys.argv[1]), int(sys.argv[2])
    print("ground at %d, %d is y%d (heightmap %.2f)" % (x, z, g(x, z), g.heights[z - g.oz, x - g.ox]))
