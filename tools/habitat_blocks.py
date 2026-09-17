#!/usr/bin/env python
"""Habitat Blocks as data: the placement manifest (data/habitat_blocks.json), its placement function, and presence checks.

A re-export regenerates every region file from the WorldPainter project, which never contains a block placed in game,
so a Habitat Block is erased by every export (EXP-021). This tool makes each block reproducible from data, like
the cavern, the world tree and the islet:

  function   write a datapack function that places every manifest block with the two commands EXP-021 proved:
               setblock <pos> cobblemon:habitat_block[cancels_regular_spawns=<replace>,activated_style=false] replace
               data merge block <pos> {SpawningStyle:"cobblemon:natural",ReplaceSpawns:..,RangeOfInfluence:..,PoolId:..}
             A block placed by command stays inert until its chunk reloads, so the post-export procedure runs the
             function and then restarts the server (docs/world-building/REEXPORT.md).
  verify     check that every placed or verified manifest block is present, with its style, pool, range, ReplaceSpawns
             and blockstate:
               --world <stopped world>   read from region files (an offline snapshot or disposable copy; the live world
                                         is refused by runtime_guard)
               --rcon <server dir>       ask a running server (under the coordination lock)

  python tools/habitat_blocks.py function [--out build/datapacks/cobblers_habitats]
  python tools/habitat_blocks.py verify --world <world dir> | --rcon <server dir>

Static rules (also enforced by the habitat-blocks check in tools/validate_data.py): the pool is a Habitat pool that
data/spawns.json defines; only the natural style is recorded; ranges of ReplaceSpawns blocks must not overlap
(EXP-021: an overlap spawns nothing), measured horizontally because vertical reach is untested.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

MANIFEST = ROOT / "data" / "habitat_blocks.json"
SPAWNS = ROOT / "data" / "spawns.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_habitats"
BLOCK = "cobblemon:habitat_block"
PLACED = ("placed", "verified")
STATUSES = ("planned",) + PLACED


def habitat_pool_ids(spawns_doc):
    return {"cobblers:%s" % h["id"] for h in (spawns_doc or {}).get("habitats") or [] if isinstance(h, dict) and "id" in h}


def static_problems(manifest_doc, spawns_doc):
    """[(record id or None, message)] for rules that need no world."""
    out = []
    blocks = manifest_doc.get("blocks") if isinstance(manifest_doc, dict) else None
    if not isinstance(blocks, list):
        return [(None, '"blocks" must be a list')]
    pools = habitat_pool_ids(spawns_doc)
    seen = set()
    good = []
    for b in blocks:
        bid = b.get("id") if isinstance(b, dict) else None
        if not isinstance(b, dict) or not bid:
            out.append((None, "every block needs an id"))
            continue
        if bid in seen:
            out.append((bid, "duplicate id"))
        seen.add(bid)
        pos = b.get("position")
        if not (isinstance(pos, dict) and all(isinstance(pos.get(k), int) for k in "xyz")):
            out.append((bid, "position must be {x, y, z} integers"))
            continue
        if b.get("style") != "natural":
            out.append((bid, 'style must be "natural" (the activated style is untested)'))
        if not isinstance(b.get("replace_spawns"), bool):
            out.append((bid, "replace_spawns must be true or false"))
        r = b.get("range_of_influence")
        if not isinstance(r, int) or isinstance(r, bool) or r <= 0:
            out.append((bid, "range_of_influence must be a positive integer"))
            continue
        if b.get("pool") not in pools:
            out.append((bid, "pool %r is not a Habitat pool in data/spawns.json (%s)" % (b.get("pool"), ", ".join(sorted(pools)) or "none")))
        if b.get("status") not in STATUSES:
            out.append((bid, "status must be one of %s" % ", ".join(STATUSES)))
        good.append(b)
    for i, a in enumerate(good):
        for c in good[i + 1:]:
            if not (a.get("replace_spawns") and c.get("replace_spawns")):
                continue
            d = math.hypot(a["position"]["x"] - c["position"]["x"], a["position"]["z"] - c["position"]["z"])
            if d < a["range_of_influence"] + c["range_of_influence"]:
                out.append((a["id"], "range overlaps %s: %.1f blocks apart, ranges %d + %d (EXP-021: an overlap spawns nothing)"
                            % (c["id"], d, a["range_of_influence"], c["range_of_influence"])))
    return out


def commands(b):
    x, y, z = (b["position"][k] for k in "xyz")
    replace = "true" if b["replace_spawns"] else "false"
    return [
        "setblock %d %d %d %s[cancels_regular_spawns=%s,activated_style=false] replace" % (x, y, z, BLOCK, replace),
        'data merge block %d %d %d {SpawningStyle:"cobblemon:natural",ReplaceSpawns:%s,RangeOfInfluence:%d,PoolId:"%s"}'
        % (x, y, z, "1b" if b["replace_spawns"] else "0b", b["range_of_influence"], b["pool"]),
    ]


def expected(b):
    return {"id": BLOCK, "SpawningStyle": "cobblemon:natural", "PoolId": b["pool"],
            "RangeOfInfluence": b["range_of_influence"], "ReplaceSpawns": 1 if b["replace_spawns"] else 0,
            "cancels_regular_spawns": "true" if b["replace_spawns"] else "false"}


def compare(b, found):
    """Mismatch messages between a manifest block and what the world holds (found: dict or None)."""
    if not found:
        return ["absent: no %s block entity at %s" % (BLOCK, tuple(b["position"][k] for k in "xyz"))]
    msgs = []
    for k, v in expected(b).items():
        got = found.get(k)
        if k in ("RangeOfInfluence", "ReplaceSpawns") and got is not None:
            got = int(got)
        if got != v:
            msgs.append("%s is %r, manifest says %r" % (k, got, v))
    return msgs


def read_world(world_dir, blocks):
    """{block id: dict of block-entity fields plus cancels_regular_spawns from the blockstate, or None}."""
    import nbt
    from world_heights import unpack_states
    world = Path(world_dir)
    want = {}
    for b in blocks:
        x, y, z = (b["position"][k] for k in "xyz")
        cx, cz = x >> 4, z >> 4
        want.setdefault((cx >> 5, cz >> 5), {}).setdefault((cx & 31, cz & 31), []).append(b)
    out = {b["id"]: None for b in blocks}
    for (rx, rz), chunks in want.items():
        path = world / "region" / ("r.%d.%d.mca" % (rx, rz))
        if not path.is_file():
            continue
        for lx, lz, ch in nbt.region_chunks(path, wanted=set(chunks)):
            bes = {(be.get("x"), be.get("y"), be.get("z")): be for be in ch.get("block_entities") or []}
            for b in chunks[(lx, lz)]:
                x, y, z = (b["position"][k] for k in "xyz")
                be = bes.get((x, y, z))
                if not be or be.get("id") != BLOCK:
                    continue
                rec = dict(be)
                for sec in ch.get("sections") or []:
                    if int(sec.get("Y", -99)) != y >> 4:
                        continue
                    pal = (sec.get("block_states") or {}).get("palette") or []
                    if not pal:
                        break
                    idx = unpack_states((sec.get("block_states") or {}).get("data"), len(pal)).reshape(16, 16, 16)
                    state = pal[int(idx[y & 15, z & 15, x & 15])]
                    if state.get("Name") == BLOCK:
                        rec["cancels_regular_spawns"] = (state.get("Properties") or {}).get("cancels_regular_spawns")
                out[b["id"]] = rec
    return out


def world_problems(manifest_doc, world_dir):
    """[(record id, message)] for placed/verified blocks missing or different in a stopped world."""
    import runtime_guard
    runtime_guard.check(world_dir, "read")
    blocks = [b for b in manifest_doc.get("blocks") or [] if isinstance(b, dict) and b.get("status") in PLACED]
    found = read_world(world_dir, blocks)
    return [(b["id"], m) for b in blocks for m in compare(b, found[b["id"]])]


def rcon_problems(manifest_doc, server_dir):
    import re
    import runtime_guard
    module, pw = runtime_guard.rcon(server_dir)
    run = lambda c: module.run([c], pw, timeout=120)[0]
    out = []
    for b in [b for b in manifest_doc.get("blocks") or [] if b.get("status") in PLACED]:
        x, y, z = (b["position"][k] for k in "xyz")
        run("forceload add %d %d" % (x, z))
        try:
            got = run("data get block %d %d %d" % (x, y, z))
            if "block data" not in got:
                out.append((b["id"], "absent: %s" % got.strip()))
                continue
            found = {"id": BLOCK if '"%s"' % BLOCK in got else None}
            for k in ("SpawningStyle", "PoolId"):
                m = re.search(r'%s: "([^"]*)"' % k, got)
                found[k] = m.group(1) if m else None
            for k in ("RangeOfInfluence", "ReplaceSpawns"):
                m = re.search(r"%s: (\d+)b?" % k, got)
                found[k] = int(m.group(1)) if m else None
            state = "true" if "passed" in run("execute if block %d %d %d %s[cancels_regular_spawns=true]" % (x, y, z, BLOCK)) else "false"
            found["cancels_regular_spawns"] = state
            out.extend((b["id"], m) for m in compare(b, found))
        finally:
            run("forceload remove %d %d" % (x, z))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest", default=str(MANIFEST))
    p.add_argument("--spawns", default=str(SPAWNS))
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("function")
    f.add_argument("--out", default=str(DEFAULT_OUT))
    v = sub.add_parser("verify")
    g = v.add_mutually_exclusive_group(required=True)
    g.add_argument("--world")
    g.add_argument("--rcon", metavar="SERVER_DIR")
    a = p.parse_args(argv)
    manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    spawns = json.loads(Path(a.spawns).read_text(encoding="utf-8"))
    problems = static_problems(manifest, spawns)
    if problems:
        for bid, m in problems:
            print("ERROR %s: %s" % (bid, m))
        return 1
    blocks = manifest["blocks"]
    if a.cmd == "function":
        out = Path(a.out)
        fn = out / "data" / "cobblers" / "function" / "habitats" / "place.mcfunction"
        fn.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# generated by tools/habitat_blocks.py from data/habitat_blocks.json; restart the server afterwards so each block's chunk reloads (EXP-021)"]
        for b in blocks:
            x, z = b["position"]["x"], b["position"]["z"]
            lines += ["# %s (%s)" % (b["id"], b["pool"]), "forceload add %d %d" % (x, z)] + commands(b) + ["forceload remove %d %d" % (x, z)]
        fn.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers Habitat Blocks (generated)"}}) + "\n", encoding="utf-8")
        print("wrote %s: %d blocks" % (fn, len(blocks)))
        return 0
    problems = world_problems(manifest, a.world) if a.world else rcon_problems(manifest, a.rcon)
    n = sum(1 for b in blocks if b.get("status") in PLACED)
    for bid, m in problems:
        print("MISMATCH %s: %s" % (bid, m))
    print("%d placed or verified blocks checked, %d problems" % (n, len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
