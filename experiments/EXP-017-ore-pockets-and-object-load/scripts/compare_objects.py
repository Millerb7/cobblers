#!/usr/bin/env python
"""EXP-017 Task B: diff two probe_objects.py snapshots (export before load vs. world saved by the server).

  python compare_objects.py <pre.json> <post.json> [out.json]

Per cobblemon:* block name: positions in pre, how many hold the same block name in post, how many
also have identical properties. Per block entity id: count in pre, how many exist in post at the
same position with the same id, and how many have data identical to the export (deep equality of
every exported key; keys added by the game are listed separately).
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

pre = json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
post = json.loads(Path(sys.argv[2]).read_text(encoding="utf8"))

post_blocks = {}
for name, info in post["blocks"].items():
    for x, y, z, props in info["positions"]:
        post_blocks[(x, y, z)] = (name, props)
blocks = {}
for name, info in pre["blocks"].items():
    same_name = same_props = 0
    prop_changes = Counter()
    for x, y, z, props in info["positions"]:
        got = post_blocks.get((x, y, z))
        if got and got[0] == name:
            same_name += 1
            if got[1] == props:
                same_props += 1
            else:
                for k in set(props) | set(got[1]):
                    if props.get(k) != got[1].get(k):
                        prop_changes["%s: %s -> %s" % (k, props.get(k), got[1].get(k))] += 1
    blocks[name] = {"pre": info["count"], "post_same_block": same_name, "post_same_properties": same_props,
                    "property_changes_top": dict(prop_changes.most_common(8))}

post_be = {(tuple(b["pos"]), b["id"]): b for b in post["block_entities"]}
bes = defaultdict(lambda: {"pre": 0, "post_present": 0, "post_data_identical": 0, "added_keys": Counter(),
                           "changed_keys": Counter()})
for b in pre["block_entities"]:
    s = bes[b["id"]]
    s["pre"] += 1
    got = post_be.get((tuple(b["pos"]), b["id"]))
    if not got:
        continue
    s["post_present"] += 1
    changed = [k for k in b["data"] if got["data"].get(k) != b["data"][k]]
    for k in changed:
        s["changed_keys"][k] += 1
    for k in set(got["data"]) - set(b["data"]):
        s["added_keys"][k] += 1
    if not changed:
        s["post_data_identical"] += 1

res = {
    "pre_world": pre["world"], "post_world": post["world"],
    "pre_data_version": pre["data_version"], "post_data_version": post["data_version"],
    "pre_status": pre["status"], "post_status": post["status"],
    "blocks": blocks,
    "block_entities": {k: {**v, "added_keys": dict(v["added_keys"]), "changed_keys": dict(v["changed_keys"])}
                       for k, v in bes.items()},
    "post_block_entity_counts": post["block_entity_counts"],
}
text = json.dumps(res, indent=1)
if len(sys.argv) > 3:
    Path(sys.argv[3]).write_text(text, encoding="utf8")
print(text)
