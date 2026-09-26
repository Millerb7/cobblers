#!/usr/bin/env python
"""Habitat Blocks as data: the placement manifest (data/habitat_blocks.json), its placement function, and presence checks.

A re-export regenerates every region file from the WorldPainter project, which never contains a block placed in game,
so a Habitat Block is erased by every export (EXP-021). This tool makes each block reproducible from data, like
the cavern, the world tree and the islet:

  function   write a datapack function that places every manifest block.
             natural, with the two commands EXP-021 proved:
               setblock <pos> cobblemon:habitat_block[cancels_regular_spawns=<replace>,activated_style=false] replace
               data merge block <pos> {SpawningStyle:"cobblemon:natural",ReplaceSpawns:..,RangeOfInfluence:..,PoolId:..}
             A natural block placed by command stays inert until its chunk reloads, so the post-export procedure runs
             the function and then restarts the server (docs/world-building/REEXPORT.md).
             activated, with its whole block entity in one setblock, after the position is set to its mimic block:
               setblock <pos> <mimic> replace
               setblock <pos> cobblemon:habitat_block[cancels_regular_spawns=false,activated_style=true]{..all..} replace
             Cobblemon 1.8.0's HabitatBlockEntity builds its spawner once, on its first tick (an `initialized` flag
             that is not saved). A `data merge` onto a block that has ticked hands it an activated style whose spawner
             was never built, and every tick then throws (staging, 2026-09-26: Neruina kicked the player). Setting
             the mimic first makes the second setblock a new block entity rather than the old one re-read, and the
             NBT must carry PhaseOrder, which the loader reads with valueOf and does not default.
  verify     check that every placed or verified manifest block is present, with its style, pool, range, ReplaceSpawns
             and blockstate:
               --world <stopped world>   read from region files (an offline snapshot or disposable copy; the live world
                                         is refused by runtime_guard)
               --rcon <server dir>       ask a running server (under the coordination lock)

  python tools/habitat_blocks.py function [--out build/datapacks/cobblers_habitats]
  python tools/habitat_blocks.py verify --world <world dir> | --rcon <server dir>

Static rules (also enforced by the habitat-blocks check in tools/validate_data.py): the pool is a Habitat pool that
data/spawns.json defines; only the natural style is recorded; ranges of ReplaceSpawns blocks must not overlap
(EXP-021: an overlap spawns nothing), measured in three dimensions: the reach is a sphere. Activated blocks keep up to
max_spawns of their pool alive within spawn_range of themselves, refill as those go, and do not cancel one another. Staging, 2026-09-26: three
blocks stacked on one trunk (ground + 12, + 35, + 58, range 11, 23 apart vertically, 0 apart horizontally) still spawned
their pool's Fletchling in the trunk's column; had the reach been a column, the three would overlap and spawn nothing.
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


# The ground rule (tools/ground_rule.py): the functions here that read a world, each only to check, never to
# decide a position: the verify reads a stopped world copy to check placed Habitat Blocks.
WORLD_READS = {'main', 'read_world', 'world_problems'}


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
        style = b.get("style")
        if style not in ("natural", "activated"):
            out.append((bid, 'style must be "natural" or "activated"'))
            continue
        if not isinstance(b.get("replace_spawns"), bool):
            out.append((bid, "replace_spawns must be true or false"))
        if style == "natural":
            r = b.get("range_of_influence")
            if not isinstance(r, int) or isinstance(r, bool) or r <= 0:
                out.append((bid, "range_of_influence must be a positive integer"))
                continue
        else:
            if b.get("replace_spawns") is not False:
                out.append((bid, "an activated block has replace_spawns false"))
            if not (isinstance(b.get("mimic"), str) and ":" in b["mimic"]):
                out.append((bid, "an activated block needs mimic, a namespaced block id"))
            act = b.get("activated")
            if not isinstance(act, dict):
                out.append((bid, "an activated block needs its activated settings"))
                continue
            for k in ("spawn_range", "max_spawns", "max_spawns_per_activation", "cancel_range"):
                v = act.get(k)
                if not isinstance(v, int) or isinstance(v, bool) or (v <= 0 and not (k == "cancel_range" and v == -1)):
                    out.append((bid, "activated.%s must be a positive integer%s"
                                % (k, " or -1" if k == "cancel_range" else "")))
            if act.get("trigger") not in ("TICK", "REDSTONE"):
                out.append((bid, "activated.trigger must be TICK or REDSTONE"))
            c = act.get("chance")
            if not isinstance(c, (int, float)) or isinstance(c, bool) or not 0 < c <= 1:
                out.append((bid, "activated.chance must be in (0, 1]"))
        if b.get("pool") not in pools:
            out.append((bid, "pool %r is not a Habitat pool in data/spawns.json (%s)" % (b.get("pool"), ", ".join(sorted(pools)) or "none")))
        if b.get("status") not in STATUSES:
            out.append((bid, "status must be one of %s" % ", ".join(STATUSES)))
        good.append(b)
    for i, a in enumerate(good):
        for c in good[i + 1:]:
            if not (a.get("replace_spawns") and c.get("replace_spawns")
                    and a.get("style") == c.get("style") == "natural"):
                continue
            d = math.dist([a["position"][k] for k in "xyz"], [c["position"][k] for k in "xyz"])
            if d < a["range_of_influence"] + c["range_of_influence"]:
                out.append((a["id"], "range overlaps %s: %.1f blocks apart, ranges %d + %d (EXP-021: an overlap spawns nothing)"
                            % (c["id"], d, a["range_of_influence"], c["range_of_influence"])))
    return out


def activated_nbt(b):
    a = b["activated"]
    return ('{MimicId:"%s",PhaseOrder:"SIMPLE",LevelRange:"",Modifiers:"",SpawningStyle:"cobblemon:activated",'
            'Chance:%sf,Trigger:"%s",CancelRange:%d,SpawnRange:%d,MaxSpawns:%d,MaxSpawnsPerActivation:%d,PoolId:"%s"}'
            % (b["mimic"], float(a["chance"]), a["trigger"], a["cancel_range"], a["spawn_range"], a["max_spawns"],
               a["max_spawns_per_activation"], b["pool"]))


def commands(b):
    x, y, z = (b["position"][k] for k in "xyz")
    if b["style"] == "activated":
        cancels = "true" if b["activated"]["cancel_range"] > 0 else "false"
        return ["setblock %d %d %d %s replace" % (x, y, z, b["mimic"]),
                "setblock %d %d %d %s[cancels_regular_spawns=%s,activated_style=true]%s replace"
                % (x, y, z, BLOCK, cancels, activated_nbt(b))]
    replace = "true" if b["replace_spawns"] else "false"
    return [
        "setblock %d %d %d %s[cancels_regular_spawns=%s,activated_style=false] replace" % (x, y, z, BLOCK, replace),
        'data merge block %d %d %d {SpawningStyle:"cobblemon:natural",ReplaceSpawns:%s,RangeOfInfluence:%d,PoolId:"%s"}'
        % (x, y, z, "1b" if b["replace_spawns"] else "0b", b["range_of_influence"], b["pool"]),
    ]


def expected(b):
    if b["style"] == "activated":
        a = b["activated"]
        return {"id": BLOCK, "SpawningStyle": "cobblemon:activated", "PoolId": b["pool"], "MimicId": b["mimic"],
                "SpawnRange": a["spawn_range"], "MaxSpawns": a["max_spawns"],
                "MaxSpawnsPerActivation": a["max_spawns_per_activation"], "CancelRange": a["cancel_range"],
                "Trigger": a["trigger"], "cancels_regular_spawns": "true" if a["cancel_range"] > 0 else "false"}
    return {"id": BLOCK, "SpawningStyle": "cobblemon:natural", "PoolId": b["pool"],
            "RangeOfInfluence": b["range_of_influence"], "ReplaceSpawns": 1 if b["replace_spawns"] else 0,
            "cancels_regular_spawns": "true" if b["replace_spawns"] else "false"}


INT_KEYS = ("RangeOfInfluence", "ReplaceSpawns", "SpawnRange", "MaxSpawns", "MaxSpawnsPerActivation", "CancelRange")


def compare(b, found):
    """Mismatch messages between a manifest block and what the world holds (found: dict or None)."""
    if not found:
        return ["absent: no %s block entity at %s" % (BLOCK, tuple(b["position"][k] for k in "xyz"))]
    msgs = []
    for k, v in expected(b).items():
        got = found.get(k)
        if k in INT_KEYS and got is not None:
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
            for k in ("SpawningStyle", "PoolId", "MimicId", "Trigger"):
                m = re.search(r'\b%s: "([^"]*)"' % k, got)
                found[k] = m.group(1) if m else None
            for k in INT_KEYS:
                m = re.search(r"\b%s: (-?\d+)b?" % k, got)
                found[k] = int(m.group(1)) if m else None
            want_true = expected(b)["cancels_regular_spawns"] == "true"
            # retried: straight after a forceload the state test read "false" for a block that read "true" a moment
            # later, and a different handful of blocks every run (staging, 2026-09-26: 9, then 21, then 8 of 237)
            state = "false"
            for _ in range(4 if want_true else 1):
                if "passed" in run("execute if block %d %d %d %s[cancels_regular_spawns=true]" % (x, y, z, BLOCK)):
                    state = "true"
                    break
                import time
                time.sleep(1)
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
        lines = ["# generated by tools/habitat_blocks.py from data/habitat_blocks.json; restart the server afterwards so each natural block's chunk reloads (EXP-021)"]
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
    if n == 0:
        # fail closed: with no block recorded as placed there is nothing to verify, and "0 checked" is not a pass
        print("MISMATCH: no Habitat Block is recorded as placed; nothing was verified")
        return 1
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
