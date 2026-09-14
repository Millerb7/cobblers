"""Describe the apricorn trees Cobblemon generated in exp019 from the saved region file."""
import json, sys, collections
from pathlib import Path
import numpy as np
sys.path.insert(0, r"C:\Users\wnd\Documents\github\cobblers-worktrees\restructure\tools")
import nbt, world_heights as WH

REGION = Path(r"C:\Users\wnd\Documents\github\cobblers-server\exp019-trees-villagers\region\r.6.6.mca")
trees = json.load(open(Path(__file__).with_name("exp019_trees.json")))
x0, x1, z0, z1 = 3540, 3595, 3170, 3225
blocks = {}
for lx, lz, ch in nbt.region_chunks(REGION):
    cx, cz = 6 * 32 + lx, 6 * 32 + lz
    if cx * 16 + 15 < x0 or cx * 16 > x1 or cz * 16 + 15 < z0 or cz * 16 > z1:
        continue
    for sec in ch.get("sections") or []:
        bs = sec.get("block_states") or {}
        pal = bs.get("palette") or []
        names = [p.get("Name", "") for p in pal]
        hits = [i for i, n in enumerate(names) if "apricorn" in n]
        if not hits:
            continue
        idx = WH.unpack_states(bs.get("data"), len(pal)).reshape(16, 16, 16)
        for i in hits:
            ys, zs, xs = np.nonzero(idx == i)
            for y, z, x in zip(ys, zs, xs):
                blocks[(cx * 16 + int(x), int(sec["Y"]) * 16 + int(y), cz * 16 + int(z))] = (names[i], pal[i].get("Properties") or {})

report = []
for t in trees:
    own = {p: v for p, v in blocks.items() if abs(p[0] - t["x"]) <= 5 and abs(p[2] - t["z"]) <= 5 and 125 <= p[1] <= 150}
    logs = sorted(p for p, v in own.items() if v[0].endswith("apricorn_log"))
    leaves = [p for p, v in own.items() if v[0].endswith("apricorn_leaves")]
    fruit = [(p, v) for p, v in own.items() if not v[0].endswith(("_log", "_leaves"))]
    if not logs:
        report.append({"tree": t, "logs": 0})
        continue
    base_y = min(p[1] for p in logs)
    rel = lambda p: (p[0] - t["x"], p[1] - base_y, p[2] - t["z"])
    lv = np.array([rel(p) for p in leaves]) if leaves else np.zeros((0, 3))
    fr = [rel(p) for p, _ in fruit]
    report.append({
        "tree": t, "logs": len(logs), "trunk_height": max(p[1] for p in logs) - base_y + 1,
        "log_columns": len({(p[0], p[2]) for p in logs}),
        "log_axes": dict(collections.Counter(own[p][1].get("axis") for p in logs)),
        "leaves": len(leaves),
        "leaf_bbox": None if not len(lv) else [int(lv[:, 0].min()), int(lv[:, 0].max()), int(lv[:, 1].min()), int(lv[:, 1].max()), int(lv[:, 2].min()), int(lv[:, 2].max())],
        "leaf_layers": dict(sorted(collections.Counter(int(p[1]) for p in lv).items())),
        "leaf_props": dict(collections.Counter(json.dumps(own[p][1], sort_keys=True) for p in leaves).most_common(3)),
        "fruit": len(fruit), "fruit_block": sorted({v[0] for _, v in fruit}),
        "fruit_y_rel": dict(sorted(collections.Counter(p[1] for p in fr).items())),
        "fruit_props": dict(collections.Counter(json.dumps(v[1], sort_keys=True) for _, v in fruit).most_common(6)),
    })
json.dump(report, open(Path(__file__).with_name("exp019_trees_report.json"), "w"), indent=1)
for r in report:
    if r["logs"] == 0:
        print(r["tree"]["colour"], "no tree found"); continue
    print("%-6s logs %2d trunk %d cols %d leaves %3d bbox %s layers %s fruit %2d at y %s props %s" % (
        r["tree"]["colour"], r["logs"], r["trunk_height"], r["log_columns"], r["leaves"], r["leaf_bbox"], r["leaf_layers"],
        r["fruit"], r["fruit_y_rel"], list(r["fruit_props"].items())[:2]))
