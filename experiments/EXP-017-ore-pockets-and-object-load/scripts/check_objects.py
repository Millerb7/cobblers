#!/usr/bin/env python
"""EXP-017 Task B: check, on the RUNNING server, that exported Cobblemon blocks and block entities
are present after Minecraft loaded (and data-fixed) the chunks.

  python check_objects.py <pre.json from probe_objects.py> <out.json> <rcon log.jsonl> [--label L] [--skip-forceload]

1. forceload add 0 0 255 255 and poll `execute if loaded` until the area is loaded
2. `data get block` on every cobblemon:berry and cobblemon:habitat_block block entity from the export;
   a block entity passes when the reply is block data (not "not a block entity") and every top-level
   key of the exported data appears in it, and every exported string value appears in it
3. `execute if block x y z <name>` on every cobblemon:* block position from the export
4. `execute if block x y z <name>[<exported properties>]` on the first 20 positions per block name
"""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import srv  # noqa: E402

pre = json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
out, log = Path(sys.argv[2]), sys.argv[3]
label = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else "check"
res = {"label": label, "world": pre["world"]}


def batched(cmds, n=400):
    replies = []
    for i in range(0, len(cmds), n):
        replies += srv.run(cmds[i:i + n])
    return replies


t0 = time.time()
if "--skip-forceload" not in sys.argv:
    res["forceload"] = srv.run(["forceload add 0 0 255 255"], log)[0]
probe = ["execute if loaded %d 0 %d" % (x, z) for x in (0, 128, 255) for z in (0, 128, 255)]
while True:
    r = srv.run(probe)
    if all("passed" in x for x in r):
        res["loaded_after_s"] = round(time.time() - t0, 1)
        break
    if time.time() - t0 > 600:
        res["loaded_after_s"] = None
        res["loaded_probe"] = r
        break
    time.sleep(3)
srv.run(probe, log)

# block entities
be_stats = defaultdict(lambda: {"checked": 0, "is_block_entity": 0, "all_keys_present": 0,
                                "all_string_values_present": 0, "failures": [], "sample_reply": None})
targets = [b for b in pre["block_entities"] if b["id"] in ("cobblemon:berry", "cobblemon:habitat_block")]
replies = batched(["data get block %d %d %d" % tuple(b["pos"]) for b in targets])
for b, r in zip(targets, replies):
    s = be_stats[b["id"]]
    s["checked"] += 1
    ok_be = "has the following block data" in r
    keys_ok = ok_be and all(("%s:" % k) in r for k in b["data"])
    strs = [v for v in b["data"].values() if isinstance(v, str)]
    vals_ok = ok_be and all(v in r for v in strs)
    s["is_block_entity"] += ok_be
    s["all_keys_present"] += keys_ok
    s["all_string_values_present"] += vals_ok
    if s["sample_reply"] is None and ok_be:
        s["sample_reply"] = r[:1500]
    if not (ok_be and keys_ok and vals_ok) and len(s["failures"]) < 10:
        s["failures"].append({"pos": b["pos"], "reply": r[:400]})
res["block_entities"] = dict(be_stats)

# blocks by name
blk = {}
for name, info in pre["blocks"].items():
    cmds = ["execute if block %d %d %d %s" % (x, y, z, name) for x, y, z, _ in info["positions"]]
    r = batched(cmds)
    passed = sum("passed" in x for x in r)
    fails = [info["positions"][i][:3] for i, x in enumerate(r) if "passed" not in x][:10]
    prop_cmds, prop_desc = [], []
    for x, y, z, props in info["positions"][:20]:
        if props:
            ps = ",".join("%s=%s" % kv for kv in sorted(props.items()))
            prop_cmds.append("execute if block %d %d %d %s[%s]" % (x, y, z, name, ps))
            prop_desc.append(ps)
    pr = batched(prop_cmds) if prop_cmds else []
    blk[name] = {"positions": info["count"], "block_present": passed, "missing_examples": fails,
                 "props_checked": len(pr), "props_match": sum("passed" in x for x in pr),
                 "props_mismatch_examples": [d for d, x in zip(prop_desc, pr) if "passed" not in x][:5]}
res["blocks"] = blk
res["elapsed_s"] = round(time.time() - t0, 1)
out.write_text(json.dumps(res, indent=1), encoding="utf8")
print(json.dumps({k: {n: {kk: vv for kk, vv in v.items() if kk not in ("sample_reply", "failures")}
                      for n, v in res[k].items()} for k in ("block_entities", "blocks")}, indent=1))
print("loaded_after_s", res.get("loaded_after_s"), "elapsed", res["elapsed_s"])
