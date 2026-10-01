#!/usr/bin/env python3
"""Lay the lake bed back on the columns the Rift skin painted over, in a world that already has them wrong.

WHY A SECOND TOOL. F5 (docs/FLIGHT_FINDINGS_2026-09-29.md) was that lake beds inside the Rift read as
mottled dark purple instead of sand or gravel. The cause, proved 2026-09-30: `tools/rift_skin.py` filled
every column it touched right up to its own top, including the 113,841 under a lake, overwriting the
GRAVEL/CLAY bed `tools/paint_maps.py` paints. The skin was fixed the same day - it now stops one course
short on a wet column - and that is enough for the NEXT world export, because the paint is baked into a
world at export time and the skin no longer overwrites it.

It is NOT enough for a world that already exists. Re-running R1 against `cobblers-dryrun12` on 2026-09-30
left (3009, 104, 4008) reading `legendarymonuments:distortion_stone`, because the skin no longer writes
that cell and nothing puts the gravel back: the correct block for it lives only in a fresh export. Probed
after the run, not assumed. So the beds in every world built before the fix stay wrong until something
lays them again. This is that something.

WHAT IT LAYS, and why it matches. The same rule `tools/paint_maps.py` uses, computed from the same value
noise with the same seed and salt, so a repaired column gets the block a fresh export would have given it:

    bed = GRAVEL where value_noise(40, seed + 17) > 0.5, else CLAY

A column is repaired only when ALL of these hold, so the pass can never touch dry ground or a cell the
skin still owns:

  - it is inside a landmark's `water_body` basin and its ground is below that basin's `level_y`;
  - the Rift skin's own emitted output writes that column (the pass exists to undo the skin, so a column
    the skin never touched is none of its business);
  - the cell it writes is exactly the ground cell, round(heightmap), and nothing above or below it.

GROUND COMES FROM THE HEIGHTMAP, NEVER FROM A WORLD (CLAUDE.md). `WORLD_READS` is empty and stays empty;
`tests/test_ground_rule.py` enforces that for placement tools and this keeps to it. It reads the SKIN'S
EMITTED TEXT to know which columns the skin claims - text this repository generated, not a world save.

    python tools/lakebed_repair.py report    # how many columns, and the blocks they hold now
    python tools/lakebed_repair.py build     # build/datapacks/cobblers_lakebed_repair
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits as FL  # noqa: E402

WORLD_READS: set = set()

NS = "cobblers"
FOLDER = "lakebed_repair"
OUT = ROOT / "build" / "datapacks" / "cobblers_lakebed_repair"
SKIN = ROOT / "build" / "datapacks" / "cobblers_rift" / "data" / "cobblers" / "function" / "rift"
PART = 3500

# a single-column fill the skin writes: "fill X y1 Z X y2 Z <block>"
COLUMN = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)\s*$")


class RepairError(SystemExit):
    pass


def skin_columns():
    """{(x, z): the highest y the skin writes there} from the skin's own emitted functions.

    The skin is the reason these cells are wrong, so its output is what says which columns are in scope.
    If it has not been built, say so rather than guessing: an empty scope would silently repair nothing.
    """
    if not SKIN.is_dir():
        raise RepairError("no %s: run `python tools/rift_skin.py build` first" % SKIN)
    top = {}
    for f in sorted(SKIN.glob("blocks_*.mcfunction")):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = COLUMN.match(line)
            if not m:
                continue
            x1, y1, z1, x2, y2, z2, _b = m.groups()
            if x1 != x2 or z1 != z2:
                continue
            k = (int(x1), int(z1))
            hi = max(int(y1), int(y2))
            if top.get(k, -1 << 30) < hi:
                top[k] = hi
    if not top:
        raise RepairError("%s holds no single-column fills: the skin's shape has changed and this tool's "
                          "scope with it" % SKIN)
    return top


def wet_mask(g):
    """Columns under a lake: inside a landmark water_body basin and below its level_y. Heightmap only."""
    from PIL import Image, ImageDraw
    lm = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
    H = g.heights
    wet = np.zeros(H.shape, bool)
    for l in lm["landmarks"]:
        wb = l.get("water_body")
        if not wb:
            continue
        img = Image.new("L", (H.shape[1], H.shape[0]), 0)
        d = ImageDraw.Draw(img)
        for ring in wb["basin_polygons"]:
            d.polygon([(q[0] - g.ox, q[1] - g.oz) for q in ring], fill=1)
        wet |= np.asarray(img).astype(bool) & (H < wb["level_y"])
    return wet


def bed_noise():
    """paint_maps' own bed rule: GRAVEL where value_noise(40, seed + 17) > 0.5, else CLAY."""
    import paint_maps as PM
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    seed = int(world["seed"]) if str(world.get("seed", "")).lstrip("-").isdigit() else 0
    return PM.value_noise(40, seed + 17)


def plan(source_root=None):
    """[(x, y, z, block)] for every column to repair, plus the counts behind it."""
    import ground as G
    g = G.load(source_root)
    wet = wet_mask(g)
    nz = bed_noise()
    if nz.shape != g.heights.shape:
        raise RepairError("the bed noise is %s and the heightmap is %s: they must be the same grid"
                          % (nz.shape, g.heights.shape))
    cols = skin_columns()
    out, seen = [], Counter()
    for (x, z), _hi in sorted(cols.items()):
        zz, xx = z - g.oz, x - g.ox
        if not (0 <= zz < wet.shape[0] and 0 <= xx < wet.shape[1]) or not wet[zz, xx]:
            continue
        y = int(round(float(g.heights[zz, xx])))
        block = "minecraft:gravel" if nz[zz, xx] > 0.5 else "minecraft:clay"
        out.append((x, y, z, block))
        seen[block] += 1
    return out, {"skin columns": len(cols), "under a lake": len(out), **seen}


def cmd_report(a):
    rows, counts = plan(a.source_root)
    for k, v in counts.items():
        print("  %-22s %d" % (k, v))
    if not rows:
        print("lakebed repair: nothing to repair")
        return 0
    print("lakebed repair: %d column(s) to lay back" % len(rows))
    return 0


def cmd_build(a):
    rows, counts = plan(a.source_root)
    if not rows:
        raise RepairError("nothing to repair: refusing to write an empty pack")
    # one setblock a column, split into functions small enough for one tick, each holding its own chunks
    body = ["setblock %d %d %d %s" % r for r in rows]
    if OUT.is_dir():
        import shutil
        shutil.rmtree(OUT)
    d = OUT / "data" / NS / "function" / FOLDER
    d.mkdir(parents=True, exist_ok=True)
    (OUT / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "cobblers: the lake beds the Rift skin painted over"}},
        indent=2) + "\n", encoding="utf-8")
    index = []
    for i in range(0, len(body), PART):
        name = "part_%03d" % (i // PART)
        lines = ["# Generated by tools/lakebed_repair.py: the bed tools/paint_maps.py paints, laid back on",
                 "# columns tools/rift_skin.py overwrote before 2026-09-30. Ground from the heightmap."] + body[i:i + PART]
        (d / (name + ".mcfunction")).write_text("\n".join(FL.ensure_loaded(lines)) + "\n", encoding="utf-8")
        index.append(name)
    (d / "index.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    print("wrote %s: %d column(s) in %d function(s) (%s)"
          % (OUT, len(rows), len(index), ", ".join("%s %d" % (k, v) for k, v in counts.items() if ":" in k)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("report", cmd_report), ("build", cmd_build)):
        q = sub.add_parser(name)
        q.add_argument("--source-root", default=None)
        q.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
