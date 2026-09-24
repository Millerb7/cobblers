#!/usr/bin/env python
"""EXP-033's rig: a sealed chamber at depth under the Rift with one Habitat Block on a Victory Road-band pool, and
three sealed pockets above it for vertical reach. Prints the commands, one per line; nothing here touches a world.

The rig is an experiment, not campaign content: it is not in data/habitat_blocks.json (EXP-021's proof blocks were
not either), it has no reapply step, and a re-export erases it, which is what should happen to it.

  python experiments/EXP-033-habitat-sealed-chamber/rig.py            the carve and the block
  python experiments/EXP-033-habitat-sealed-chamber/rig.py --stands   the stands, as /tp lines for the owner

The site (3470, 20, 2880) was chosen from the heightmap (tools/ground.py) and the Deep's traced outline: 52 blocks
of rock over the shell, and at least 33 blocks of rock between the shell and Victory Road's corridor, its rooms,
all five planned region sites and the Deep's pit.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import habitat_blocks  # noqa: E402

CX, CY, CZ = 3470, 20, 2880           # the block sits on the floor at the room's centre
HALF, HEIGHT = 20, 10                 # room air x/z +-20, y20-30
SHELL = "legendarymonuments:distortion_deepslate"
FLOOR = "rechiseled:basalt_bordered_polished"
MARK = "minecraft:crying_obsidian"    # under every stand
LIGHT = "minecraft:shroomlight"
POOL, RANGE = "cobblers:rift_depths", 16
BLOCK = {"id": "exp033", "pool": POOL, "style": "natural", "replace_spawns": True,
         "range_of_influence": RANGE, "position": {"x": CX, "y": CY, "z": CZ}}

# Pockets for vertical reach, 5 blocks south of the block: feet height above the block, and what a sphere and a
# cylinder of radius 16 each predict there. Source says a sphere; nothing has measured it.
PX, PZ = CX, CZ + 5
POCKETS = [(13, "inside a sphere (13.9) and a cylinder"),
           (17, "OUTSIDE a sphere (17.7), inside a cylinder"),
           (23, "outside both")]

STANDS = [
    ("S1", (CX, CY, CZ + 3), "3 blocks from the block, room floor", "the pool, alone"),
    ("S2", (CX, CY, CZ + 13), "13 blocks out, room floor", "the pool, alone"),
    ("S3", (CX, CY, CZ + 19), "19 blocks out, room floor, past the range", "the ambient cave pool, no rift_depths species"),
] + [("V%d" % (i + 1), (PX, CY + dy, PZ), "%d above the block, 5 south, sealed pocket" % dy, verdict)
     for i, (dy, verdict) in enumerate(POCKETS)]


def commands():
    x0, x1, z0, z1 = CX - HALF - 2, CX + HALF + 2, CZ - HALF - 2, CZ + HALF + 2
    top = CY + HEIGHT + 3
    out = ["forceload add %d %d %d %d" % (x0, z0, x1, z1)]
    # shell first, so no face is left open; two fills because one is over the 32,768-block limit
    mid = (CY - 3 + top) // 2
    out += ["fill %d %d %d %d %d %d %s" % (x0, lo, z0, x1, hi, z1, SHELL) for lo, hi in ((CY - 3, mid), (mid + 1, top))]
    # the pockets' own shell column, from the room's roof to above the highest pocket
    ptop = CY + POCKETS[-1][0] + 4
    out.append("fill %d %d %d %d %d %d %s" % (PX - 3, CY + HEIGHT + 1, PZ - 3, PX + 3, ptop, PZ + 3, SHELL))
    out.append("fill %d %d %d %d %d %d minecraft:air" % (CX - HALF, CY, CZ - HALF, CX + HALF, CY + HEIGHT, CZ + HALF))
    out.append("fill %d %d %d %d %d %d %s" % (CX - HALF, CY - 1, CZ - HALF, CX + HALF, CY - 1, CZ + HALF, FLOOR))
    for dy, _ in POCKETS:
        fy = CY + dy - 1
        out.append("fill %d %d %d %d %d %d minecraft:air" % (PX - 1, fy + 1, PZ - 1, PX + 1, fy + 3, PZ + 1))
        out.append("fill %d %d %d %d %d %d %s" % (PX - 1, fy, PZ - 1, PX + 1, fy, PZ + 1, FLOOR))
        out.append("setblock %d %d %d %s" % (PX + 1, fy + 3, PZ + 1, LIGHT))
    for _sid, (x, y, z), _where, _v in STANDS:
        out.append("setblock %d %d %d %s" % (x, y - 1, z, MARK))
    for dx, dz in ((-10, -10), (10, -10), (-10, 10), (10, 10)):
        out.append("setblock %d %d %d %s" % (CX + dx, CY + HEIGHT, CZ + dz, LIGHT))
    out += habitat_blocks.commands(BLOCK)
    out.append("forceload remove %d %d %d %d" % (x0, z0, x1, z1))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--stands", action="store_true")
    a = p.parse_args(argv)
    if a.stands:
        for sid, (x, y, z), where, verdict in STANDS:
            print("%s  /tp @s %d %d %d   %s -> expect %s" % (sid, x, y, z, where, verdict))
    else:
        print("\n".join(commands()))


if __name__ == "__main__":
    main()
