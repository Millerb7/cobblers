#!/usr/bin/env python
"""The Displaced City's fields: small lantern-lit plots on the bare slopes between the benches.

A summit town put under the ice still has to eat. The fields are small, 5 x 5, on the slopes the town's lots do not
use (design radius 62 to 70 between the benches, 30 to 44 between the summit and the upper bench), each levelled by at most two blocks, and each lit by two lantern
posts at opposite corners: every crop is 7 blocks or less from a lantern, so it stands at block light 8, enough to
live and barely enough to grow. Carrots, potatoes and beetroots at young, uneven ages, a few failed cells left as bare
coarse dirt, a composter and a hay bale at the corner: struggling, and clearly tended. None is a spawn condition
(wheat would be).

Sites come from data only: the cavern floor and design fields (tools/cavern_plan.summit_floor), the town's derived
plan (streets, lots, anchors, the square) and the cavern's own trees and light strings, all kept clear.

  python tools/cavern_farms.py --source-root <root>      # writes the earthwork displaced_farms
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SID = "displaced_city"
N = 5                 # a plot is N x N farmland
WANT = 6              # fields
CROPS = ("carrots", "potatoes", "beetroots")


def fields():
    import cavern_plan as CP
    plan = json.loads((ROOT / "derived" / "cavern" / "plan.json").read_text(encoding="utf-8"))
    x0, z0 = plan["cavern"][0], plan["cavern"][1]
    n = plan["cavern"][2] - x0 + 1
    floor, r, d = CP.summit_floor(n, 20260916, (plan["tunnel"]["arrival"][0] - (x0 + n // 2), plan["tunnel"]["arrival"][2] - (z0 + n // 2)))
    saved = np.load(ROOT / "derived" / "cavern" / "plan.npz")["floor"]
    if not (floor == saved).all():
        raise SystemExit("the recomputed cavern floor does not match derived/cavern/plan.npz: re-run tools/cavern_plan.py")
    return x0, z0, floor, r


def taken_cells(x0, z0, n):
    """Columns the town or the cavern already uses, with a margin."""
    busy = np.zeros((n, n), bool)
    tp = json.loads((ROOT / "derived" / "towns" / ("%s_plan.json" % SID)).read_text(encoding="utf-8"))

    def mark(a, b, c, d_, pad):
        busy[max(0, b - z0 - pad):max(0, d_ - z0 + pad + 1), max(0, a - x0 - pad):max(0, c - x0 + pad + 1)] = True
    for st in tp["streets"].values():
        for z, _, xa, xb in st["cells"]:
            mark(xa, z, xb, z, 1)
    for rect in [l["rect"] for l in tp["lots"]] + [a["rect"] for a in tp["anchors"]] + ([tp["plaza"]["rect"]] if tp.get("plaza") else []):
        mark(*rect, 1)
    cp = json.loads((ROOT / "derived" / "cavern" / "plan.json").read_text(encoding="utf-8"))
    for t in cp.get("tree_positions") or []:
        mark(t["at"][0], t["at"][2], t["at"][0], t["at"][2], 5)
    light = ROOT / "build" / "datapacks" / "cobblers_cavern" / "data" / "cobblers" / "function" / "cavern" / "40_light.mcfunction"
    for line in light.read_text(encoding="utf-8").splitlines():
        m = re.match(r"(?:setblock|fill) (-?\d+) -?\d+ (-?\d+)", line)
        if m:
            mark(int(m.group(1)), int(m.group(2)), int(m.group(1)), int(m.group(2)), 3)
    return busy


def pick(x0, z0, floor, r):
    n = floor.shape[0]
    busy = taken_cells(x0, z0, n)
    cands = []
    for j in range(2, n - N - 2, 2):
        for i in range(2, n - N - 2, 2):
            rr = r[j + N // 2, i + N // 2]
            if not (62 <= rr <= 70 or 30 <= rr <= 44):
                continue
            if busy[j - 1:j + N + 1, i - 1:i + N + 1].any():
                continue
            blk = floor[j - 1:j + N + 1, i - 1:i + N + 1]
            lvl = int(np.median(blk))
            if blk.max() - lvl > 2 or lvl - blk.min() > 2:
                continue
            cands.append((int(blk.max() - blk.min()), i, j, lvl))
    cands.sort()
    chosen = []
    for rel, i, j, lvl in cands:
        cx, cz = x0 + i, z0 + j
        if all(abs(cx - a) > 24 or abs(cz - b) > 24 for a, b, _ in chosen):
            chosen.append((cx, cz, lvl))
        if len(chosen) >= WANT:
            break
    return chosen


def commands(chosen):
    """-> (ground, crops). The ground, the edge, the lantern posts, the composter and the hay go in with the town. The
    farmland and the crops go in its after-donor function (tools/place_town.py), minutes later: a crop checks its
    light when it or a neighbour is set, and a lantern set in the same function has not lit anything yet, so on
    2026-09-21 131 of 136 crops set beside their lanterns broke at once. Farmland goes with them because farmland with
    nothing on it dries back to dirt at its first random tick."""
    c = ["# the Displaced City's fields: small lantern-lit plots on the slopes (tools/cavern_farms.py)"]
    crops = ["# the fields' farmland and crops, set once the lanterns have lit (tools/cavern_farms.py)"]
    for f, (x, z, L) in enumerate(chosen):
        x1, z1 = x + N - 1, z + N - 1
        c.append("fill %d %d %d %d %d %d minecraft:air" % (x - 1, L + 1, z - 1, x1 + 1, L + 5, z1 + 1))
        c.append("fill %d %d %d %d %d %d minecraft:dirt" % (x - 1, L - 3, z - 1, x1 + 1, L - 1, z1 + 1))
        c.append("fill %d %d %d %d %d %d minecraft:coarse_dirt" % (x - 1, L, z - 1, x1 + 1, L, z1 + 1))     # the worn edge
        for px, pz in ((x - 1, z - 1), (x1 + 1, z1 + 1)):
            c.append("setblock %d %d %d minecraft:spruce_fence" % (px, L + 1, pz))
            c.append("setblock %d %d %d minecraft:lantern[hanging=false]" % (px, L + 2, pz))
        c.append("setblock %d %d %d minecraft:composter[level=3]" % (x1 + 1, L + 1, z - 1))
        c.append("setblock %d %d %d minecraft:hay_block" % (x - 1, L + 1, z1 + 1))
        crops.append("fill %d %d %d %d %d %d minecraft:farmland[moisture=7]" % (x, L, z, x1, L, z1))
        for k in range(N):                                    # rows of one crop each, young and uneven
            crop = CROPS[(f + k) % 3]
            top = 3 if crop == "beetroots" else 7
            for i in range(N):
                h = (x * 31 + z * 17 + i * 7 + k * 13) % 11
                if h == 0:
                    crops.append("setblock %d %d %d minecraft:coarse_dirt" % (x + i, L, z + k))   # a cell that failed
                    continue
                age = min(top, h % (top // 2 + 2))
                crops.append("setblock %d %d %d minecraft:%s[age=%d]" % (x + i, L + 1, z + k, crop, age))
    return c, crops


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    p.parse_args(argv)
    x0, z0, floor, r = fields()
    chosen = pick(x0, z0, floor, r)
    path = ROOT / "data" / "placements.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    ground, crops = commands(chosen)
    doc["placements"] = [q for q in doc["placements"] if q["id"] not in ("displaced_farms", "displaced_farm_crops")]
    doc["placements"].append({"id": "displaced_farms", "settlement": SID, "kind": "earthwork", "cell": "B4", "status": "planned",
                              "chosen_because": "the owner, 2026-09-21: small, struggling, clearly tended fields on the bare slopes "
                                                "between the benches, lit by their own lanterns because the cavern has no sun",
                              "commands": ground})
    doc["placements"].append({"id": "displaced_farm_crops", "settlement": SID, "kind": "earthwork", "cell": "B4", "status": "planned",
                              "after": "donors",
                              "chosen_because": "the fields' farmland and crops, set after the lanterns have lit them: a crop set "
                                                "in the dark breaks (tools/cavern_farms.py commands)",
                              "commands": crops})
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("%d fields: %s" % (len(chosen), chosen))


if __name__ == "__main__":
    main()
