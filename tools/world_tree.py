#!/usr/bin/env python
"""The world tree at Foothill Woods: a datapack of fill functions, plus its foundation course.

At 1.26 million blocks the tree is far too large for one `place template` -- a structure loads its whole block list
into memory and places it in a single tick, and the NBT alone runs to megabytes. So it ships the way the cavern
did, as run-length fills split across functions (`maxCommandChainLength` is 65536, which is why it is split).

It needs the raised build limit: at Foothill Woods, ground y116, the crown reaches y535 against a vanilla ceiling
of y319. See `modpack/datapacks/cobblers_height`.

  python tools/world_tree.py
  then: /reload, /function cobblers:worldtree/00_tree .. 03_tree, then 90_foundation

This lives in the repo rather than only in a scratch directory because the datapack it writes sits INSIDE the world
folder, and a terrain re-export would carry it off with the world. The tree is sha256-seeded, so regenerating it
reproduces the same blocks exactly.
"""
import sys, json, shutil
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
SERVER_DP = Path(r"C:\Users\wnd\Documents\github\cobblers-server\cobblers-10240\datapacks\cobblers_worldtree")

CENTRE = (2016, 2280)          # trunk centre, as recorded in the grove report
GROUND = 116


def main():
    import tree_grove as TG
    import world_heights as WH
    b, dims = TG.big_tree("oak", "a", "world")
    c = dims["trunk"][0] // 2                       # builder trunk centre is at (c, ., c)
    ox = CENTRE[0] - c
    oz = CENTRE[1] - c
    oy = GROUND + 1                                 # builder y0 sits one above ground, as `place template` did
    print("tree: height %d, trunk %s, crown radius %d, %d blocks"
          % (dims["height"], dims["trunk"], dims["crown_radius"], len(b.blocks)))
    print("origin (%d, %d, %d) -> trunk centre (%d, %d)  top y%d"
          % (ox, oy, oz, CENTRE[0], CENTRE[1], oy + max(y for _, y, _ in b.blocks)))

    parts = TG.fill_runs(b.blocks, (ox, oy, oz), "world tree at Foothill Woods, oak, 418 blocks")
    print("fill functions: %d, commands %d" % (len(parts), sum(len(p) - 1 for p in parts)))

    # foundation: the ground under the trunk runs y114-117, so a flat-bottomed 35-wide trunk leaves gaps on the
    # low side. For every column the tree occupies, pack dirt from 5 below its lowest block up to it.
    low = {}
    for (x, y, z) in b.blocks:
        k = (ox + x, oz + z)
        low[k] = min(low.get(k, 10 ** 6), oy + y)
    g, _, _ = WH.extract(r"C:\Users\wnd\Documents\github\cobblers-server\cobblers-10240",
                         (min(k[0] for k in low), min(k[1] for k in low),
                          max(k[0] for k in low), max(k[1] for k in low)))
    gx0, gz0 = min(k[0] for k in low), min(k[1] for k in low)
    found, gaps = [], 0
    for (x, z), y in sorted(low.items()):
        gy = int(g[z - gz0, x - gx0])
        # ONLY at the base. Every column the canopy covers also has a "lowest block", 400 blocks up, and packing
        # dirt from the ground to those would have been 8.2 million blocks of column. A real gap under a trunk or
        # a root is a block or three; anything taller than 6 is sky under a branch and must be left alone.
        if gy < y - 1 <= gy + 6:
            found.append("fill %d %d %d %d %d %d minecraft:dirt replace #minecraft:air" % (x, gy + 1, z, x, y - 1, z))
            gaps += y - 1 - gy
    print("foundation: %d columns need packing, %d blocks" % (len(found), gaps))

    if SERVER_DP.exists():
        shutil.rmtree(SERVER_DP)
    fdir = SERVER_DP / "data" / "cobblers" / "function" / "worldtree"
    fdir.mkdir(parents=True, exist_ok=True)
    (SERVER_DP / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "Cobblers: the world tree at Foothill Woods, as fill commands."}},
        indent=2) + "\n", encoding="utf-8")
    names = []
    for i, p in enumerate(parts):
        n = "%02d_tree" % i
        (fdir / (n + ".mcfunction")).write_text("\n".join(p) + "\n", encoding="utf-8")
        names.append(n)
    (fdir / "90_foundation.mcfunction").write_text(
        "# pack the ground up to the tree where the pad falls away\n" + "\n".join(found) + "\n", encoding="utf-8")
    names.append("90_foundation")
    print("installed %s" % SERVER_DP)
    print("functions: %s" % ", ".join("cobblers:worldtree/%s" % n for n in names))
    json.dump({"centre": CENTRE, "ground_y": GROUND, "origin": [ox, oy, oz], "height": dims["height"],
               "trunk": dims["trunk"], "crown_radius": dims["crown_radius"], "blocks": len(b.blocks),
               "top_y": oy + max(y for _, y, _ in b.blocks), "functions": names,
               "storeys_world_y": [[oy + a, oy + c2] for a, c2 in dims["floor_tier_y"]],
               "crown_world_y": [oy + dims["crown_y"][0], oy + dims["crown_y"][1]]},
              open(REPO / "derived" / "sites" / "world_tree_foothill_woods.json", "w"), indent=1)


if __name__ == "__main__":
    main()
