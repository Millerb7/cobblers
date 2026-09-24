#!/usr/bin/env python
"""Generate the rewards datapack from data/rewards.json (ADR-002: per-player grants keyed to an advancement).

For every record of kind "cache":
  advancement/reward/<id>.json   criterion minecraft:location: the player stands in the record's trigger box in the
                                 overworld. Per player and once only, by construction: an advancement is granted once
                                 per player and recorded in advancements/<uuid>.json, which a re-export carries.
  function/reward/<id>           run as the earning player by the advancement's reward: gives the contents and says so
                                 to that player only.

Records of kind "npc_grant" are given by a quest's grant_reward_once (tools/compile_dialogue.py) and are only checked
here. The containers are scenery placed by the build named in each record, never by this pack.

  python tools/rewards_pack.py [--out DIR] [--server-dir DIR]

With --server-dir, every item's verification path is looked up in the named jar under <server>/mods, under the
coordination lock, and a missing one stops the build.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data" / "rewards.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_rewards"
NS = "cobblers"
ID = re.compile(r"^[a-z0-9_]+$")


class RewardError(Exception):
    pass


def problems(doc):
    out = []
    seen = set()
    for r in doc.get("rewards") or []:
        rid = r.get("id")
        if not (isinstance(rid, str) and ID.match(rid)):
            out.append("bad id %r" % (rid,))
            continue
        if rid in seen:
            out.append("%s: duplicate id" % rid)
        seen.add(rid)
        kind = r.get("kind")
        if kind not in ("cache", "npc_grant"):
            out.append("%s: kind must be cache or npc_grant" % rid)
        for c in r.get("contents") or []:
            if not (isinstance(c.get("item"), str) and ":" in c["item"]):
                out.append("%s: an item needs a namespaced id" % rid)
            if not (isinstance(c.get("count"), int) and c["count"] > 0):
                out.append("%s: %s needs a positive count" % (rid, c.get("item")))
            if not str(c.get("verification", "")).strip():
                out.append("%s: %s has no verification" % (rid, c.get("item")))
        if not r.get("contents"):
            out.append("%s: no contents" % rid)
        if kind == "cache":
            t = r.get("trigger") or {}
            lo, hi = t.get("min"), t.get("max")
            if not (isinstance(lo, list) and isinstance(hi, list) and len(lo) == 3 and len(hi) == 3
                    and all(a <= b for a, b in zip(lo, hi))):
                out.append("%s: trigger needs min and max [x, y, z] with min <= max" % rid)
            at = (r.get("container") or {}).get("at")
            if isinstance(at, list) and isinstance(lo, list) and isinstance(hi, list) and not all(
                    a - 1 <= v <= b + 1 for a, v, b in zip(lo, at, hi)):
                out.append("%s: the container at %s is not beside its trigger box" % (rid, at))
            if not str(r.get("message", "")).strip():
                out.append("%s: no message" % rid)
        if kind == "npc_grant" and not r.get("quest"):
            out.append("%s: an npc_grant names its quest" % rid)
    return out


def jar_problems(doc, server_dir):
    import glob
    import zipfile
    import runtime_guard
    runtime_guard.require_lock("read the server's mod jars")
    mods = runtime_guard.check(Path(server_dir) / "mods", "read the mod jars in")
    jars = {Path(j).name: j for j in glob.glob(str(mods / "*.jar"))}
    out = []
    for r in doc.get("rewards") or []:
        for c in r.get("contents") or []:
            # "<path> in <jar>" or "<path> and <path> in <jar>"; a jar name may hold spaces
            m = re.match(r"(.+?) in (.+?\.jar)", c["verification"])
            if not m:
                out.append("%s: %s verification names no jar path" % (r["id"], c["item"]))
                continue
            paths, jar = m.group(1).split(" and "), m.group(2)
            if jar not in jars:
                out.append("%s: %s: %s is not installed" % (r["id"], c["item"], jar))
                continue
            names = set(zipfile.ZipFile(jars[jar]).namelist())
            for path in paths:
                if path not in names:
                    out.append("%s: %s: %s is not in %s" % (r["id"], c["item"], path, jar))
    return out


def advancement(r):
    (x0, y0, z0), (x1, y1, z1) = r["trigger"]["min"], r["trigger"]["max"]
    # a position predicate reads the player's feet as a double: max + 1 takes in the whole of the last block
    pos = {"x": {"min": x0, "max": x1 + 1}, "y": {"min": y0, "max": y1 + 1}, "z": {"min": z0, "max": z1 + 1}}
    return {"criteria": {"found": {"trigger": "minecraft:location", "conditions": {"player": [
        {"condition": "minecraft:entity_properties", "entity": "this",
         "predicate": {"location": {"position": pos, "dimension": "minecraft:overworld"}}}]}}},
            "rewards": {"function": "%s:reward/%s" % (NS, r["id"])}}


def function(r):
    lines = ["# Generated by tools/rewards_pack.py from data/rewards.json: %s. Runs as the earning player, once." % r["id"]]
    for c in r["contents"]:
        lines.append("give @s %s%s %d" % (c["item"], c.get("components", ""), c["count"]))
    lines.append("tellraw @s %s" % json.dumps({"text": r["message"], "color": "gray", "italic": True}, ensure_ascii=False))
    return lines


def write(doc, out):
    if out.exists():
        shutil.rmtree(out)
    (out / "data" / NS / "advancement" / "reward").mkdir(parents=True)
    (out / "data" / NS / "function" / "reward").mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: rewards (generated)"}},
                                                indent=2) + "\n", encoding="utf-8")
    n = 0
    for r in doc["rewards"]:
        if r["kind"] != "cache":
            continue
        (out / "data" / NS / "advancement" / "reward" / ("%s.json" % r["id"])).write_text(
            json.dumps(advancement(r), indent=2) + "\n", encoding="utf-8")
        (out / "data" / NS / "function" / "reward" / ("%s.mcfunction" % r["id"])).write_text(
            "\n".join(function(r)) + "\n", encoding="utf-8")
        n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--server-dir")
    a = ap.parse_args(argv)
    doc = json.loads(Path(a.data).read_text(encoding="utf-8"))
    bad = problems(doc) + (jar_problems(doc, a.server_dir) if a.server_dir else [])
    for m in bad:
        print("ERROR %s" % m)
    if bad:
        return 1
    n = write(doc, Path(a.out))
    grants = sum(1 for r in doc["rewards"] if r["kind"] == "npc_grant")
    print("rewards: %d caches as advancements, %d npc grants left to their quests -> %s" % (n, grants, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
