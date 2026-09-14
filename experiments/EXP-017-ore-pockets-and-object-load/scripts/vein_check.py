#!/usr/bin/env python
"""EXP-017 Task A: measure blocks placed per feature attempt IN GAME, to check ore_model.py.

  python vein_check.py place <rcon log.jsonl> <out.json>      (server running on the stone-block world)
  python vein_check.py count <world dir> <tools dir> <out.json> (server stopped)

`place` force-loads 0..255, then runs `/place feature <id> x y z` on a 31x31 grid (x, z = 8..248 step 8,
veins cannot touch) on one y plane per feature, records how many commands reported success, and saves.
`count` reads the saved region and counts every block in each plane's band (y-4..y+4) inside 0..255.
"""
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

PLANES = [  # (feature id, y)
    ("cobblemon:ore/thunder_stone", 60),
    ("cobblemon:ore/thunder_stone", 40),
    ("legendarymonuments:galar_particle_ore", 20),
    ("cobblemon:ore/thunder_stone", -10),
    ("lumymon:steel_ore", -30),
    ("legendarymonuments:deepslate_galar_particle_ore", -50),
]
GRID = [(x, z) for x in range(8, 249, 8) for z in range(8, 249, 8)]

if sys.argv[1] == "place":
    sys.path.insert(0, str(Path(__file__).parent))
    import srv  # noqa: E402
    log, out = sys.argv[2], Path(sys.argv[3])
    res = {"forceload": srv.run(["forceload add 0 0 255 255"], log)[0]}
    t0 = time.time()
    while not all("passed" in r for r in srv.run(["execute if loaded %d 0 %d" % (x, z) for x in (0, 255) for z in (0, 255)])):
        if time.time() - t0 > 600:
            break
        time.sleep(3)
    planes = []
    for fid, y in PLANES:
        cmds = ["place feature %s %d %d %d" % (fid, x, y, z) for x, z in GRID]
        replies = []
        for i in range(0, len(cmds), 300):
            replies += srv.run(cmds[i:i + 300])
        ok = sum(r.startswith("Placed") for r in replies)
        planes.append({"feature": fid, "y": y, "attempts": len(cmds), "reported_placed": ok,
                       "reply_examples": sorted(set(r[:120] for r in replies))[:4]})
        print(planes[-1])
    res["planes"] = planes
    res["save"] = srv.run(["save-all flush"], log)[0]
    out.write_text(json.dumps(res, indent=1), encoding="utf8")
elif sys.argv[1] == "count":
    world, tools, out = Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
    sys.path.insert(0, tools)
    import nbt  # noqa: E402
    from world_heights import unpack_states  # noqa: E402
    import numpy as np  # noqa: E402
    bands = {y: Counter() for _, y in PLANES}
    modded = []  # (x, y, z, name) of every non-minecraft block in any band
    for mca in sorted((world / "region").glob("*.mca")):
        for _, _, ch in nbt.region_chunks(mca):
            if not (0 <= ch["xPos"] < 16 and 0 <= ch["zPos"] < 16):
                continue
            for sec in ch.get("sections", []):
                bs = sec.get("block_states")
                if not bs:
                    continue
                pal = [p["Name"] for p in bs["palette"]]
                idx = unpack_states(bs.get("data"), len(pal)).reshape(16, 16, 16)  # [y, z, x]
                for yl in range(16):
                    y = sec["Y"] * 16 + yl
                    for py in bands:
                        if py - 4 <= y <= py + 4:
                            vals, cnt = np.unique(idx[yl], return_counts=True)
                            for v, c in zip(vals, cnt):
                                bands[py][pal[v]] += int(c)
                                if not pal[v].startswith("minecraft:"):
                                    for zz, xx in zip(*np.nonzero(idx[yl] == v)):
                                        modded.append((ch["xPos"] * 16 + int(xx), y, ch["zPos"] * 16 + int(zz), pal[v]))
    res = {"bands": {str(y): dict(c.most_common()) for y, c in bands.items()}, "planes": []}
    for fid, py in PLANES:
        per_attempt = Counter()
        for gx, gz in GRID:
            per_attempt[sum(1 for x, y, z, _ in modded
                            if abs(x - gx) <= 3 and abs(z - gz) <= 3 and py - 4 <= y <= py + 4)] += 1
        mod = {k: v for k, v in bands[py].items() if not k.startswith("minecraft:")}
        total = sum(mod.values())
        row = {"feature": fid, "y": py, "attempts": len(GRID), "modded_blocks": mod,
               "blocks_per_attempt": round(total / len(GRID), 4),
               "attempts_with_at_least_one_block": len(GRID) - per_attempt[0],
               "blocks_per_attempt_hist": {str(k): v for k, v in sorted(per_attempt.items())}}
        res["planes"].append(row)
        print(json.dumps(row))
    out.write_text(json.dumps(res, indent=1), encoding="utf8")
