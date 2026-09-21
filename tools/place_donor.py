#!/usr/bin/env python
"""Re-place donor structures that live only in an installed pack, from data/placements.json.

Brock's gym is Cobbleverse's own `cobbleverse:brock` template. Its licence forbids redistribution, so the .nbt is
never committed; but the pack that carries it is installed on the server, so the structure can be placed by resource
id and then have the campaign's block substitutions applied. That makes the placement reproducible from committed
data alone: the record here, plus data/spawn_block_policy.json.

A record is handled by this tool when it has `pack_template` (a resource id the server can already place):

  {"id": ..., "pack_template": "cobbleverse:brock", "position": {"x":…, "y":…, "z":…},
   "rotation": "180", "mirror": "none", "size": [27,17,24], "substitutions": "data/spawn_block_policy.json"}

  python tools/place_donor.py function [--out build/datapacks/cobblers_donor]
  python tools/place_donor.py verify --world <stopped world copy>

`function` writes one mcfunction per record: forceload, `place template`, then a `fill … replace` per substitution
(EXP-024 measured these counts as identical to the ones data/spawn_block_policy.json recorded for the hand-placed
gym). `verify` reads the saved chunks and reports the substituted block counts and the block entities in the box,
so a re-application can be checked without a player.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import function_limits

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_donor"
NS = "cobblers"


def records(placements_doc):
    return [p for p in placements_doc.get("placements") or [] if isinstance(p, dict) and p.get("pack_template")]


def box(rec):
    """Inclusive world box the template occupies, for the given rotation about its placement corner."""
    x, y, z = (rec["position"][k] for k in "xyz")
    sx, sy, sz = rec["size"]
    rot = rec.get("rotation", "none")
    if rot == "none":
        return (x, y, z), (x + sx - 1, y + sy - 1, z + sz - 1)
    if rot == "180":
        return (x - sx + 1, y, z - sz + 1), (x, y + sy - 1, z)
    if rot == "clockwise_90":
        return (x - sz + 1, y, z), (x, y + sy - 1, z + sx - 1)
    if rot == "counterclockwise_90":
        return (x, y, z - sx + 1), (x + sz - 1, y + sy - 1, z)
    raise SystemExit("unknown rotation %r" % rot)


def commands(rec, subs):
    x, y, z = (rec["position"][k] for k in "xyz")
    lo, hi = box(rec)
    out = ["# %s: %s at (%d, %d, %d) rotation %s" % (rec["id"], rec["pack_template"], x, y, z, rec.get("rotation", "none")),
           "forceload add %d %d %d %d" % (lo[0] - 16, lo[2] - 16, hi[0] + 16, hi[2] + 16),
           "place template %s %d %d %d %s %s 1.0 0" % (rec["pack_template"], x, y, z, rec.get("rotation", "none"), rec.get("mirror", "none"))]
    # /fill refuses more than 32,768 blocks, and it refuses the whole command rather than part of it.
    # Brock's gym is 11,016 and fitted; Misty's is 46,080 and every substitution silently did nothing
    # until this was split (found 2026-09-20 by place_donor.py verify, 958 blocks left unsubstituted).
    area = (hi[0] - lo[0] + 1) * (hi[2] - lo[2] + 1)
    layers = max(1, min(hi[1] - lo[1] + 1, 32768 // max(area, 1)))
    for s in subs:
        for y0 in range(lo[1], hi[1] + 1, layers):
            y1 = min(y0 + layers - 1, hi[1])
            out.append("fill %d %d %d %d %d %d %s replace %s"
                       % (lo[0], y0, lo[2], hi[0], y1, hi[2], s["to"], s["from"]))
    # A building that straddles a bank needs something under it, or the template's own ground shows as
    # a mound: Misty's gym stands with its back to the water and its floor at the promenade, so the
    # lake side is carried on a quay rather than on dirt.
    plinth = rec.get("plinth")
    if plinth:
        top = y - 1
        base = int(plinth.get("from_y", top - 8))
        material = plinth.get("material", "minecraft:stone_bricks")
        area = (hi[0] - lo[0] + 1) * (hi[2] - lo[2] + 1)
        layers = max(1, min(top - base + 1, 32768 // max(area, 1)))
        for y0 in range(base, top + 1, layers):
            y1 = min(y0 + layers - 1, top)
            for gone in ("minecraft:water", "minecraft:air"):
                out.append("fill %d %d %d %d %d %d %s replace %s"
                           % (lo[0], y0, lo[2], hi[0], y1, hi[2], material, gone))
    out.append("forceload remove %d %d %d %d" % (lo[0] - 16, lo[2] - 16, hi[0] + 16, hi[2] + 16))
    return out


def read_world(world, lo, hi):
    """(block name counts, block entity id counts) inside the inclusive box of a stopped world."""
    import structure_nbt as SN
    import nbt
    b = SN.capture(world, lo, hi)
    names = Counter(v[0] for v in b.blocks.values())
    bes = Counter()
    for rx in range(lo[0] >> 9, (hi[0] >> 9) + 1):
        for rz in range(lo[2] >> 9, (hi[2] >> 9) + 1):
            p = Path(world) / "region" / ("r.%d.%d.mca" % (rx, rz))
            if not p.is_file():
                continue
            for _, _, ch in nbt.region_chunks(p):
                for be in ch.get("block_entities") or []:
                    if lo[0] <= be.get("x", -1) <= hi[0] and lo[1] <= be.get("y", -1) <= hi[1] and lo[2] <= be.get("z", -1) <= hi[2]:
                        bes[be.get("id")] += 1
    return names, bes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--placements", default=str(ROOT / "data" / "placements.json"))
    p.add_argument("--policy", default=str(ROOT / "data" / "spawn_block_policy.json"))
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("function")
    f.add_argument("--out", default=str(DEFAULT_OUT))
    v = sub.add_parser("verify")
    v.add_argument("--world", required=True, help="a stopped world copy; the live world is refused")
    a = p.parse_args(argv)
    placements = json.loads(Path(a.placements).read_text(encoding="utf-8"))
    subs = json.loads(Path(a.policy).read_text(encoding="utf-8"))["substitutions"]
    recs = records(placements)
    if not recs:
        print("no pack_template placements")
        return 0
    if a.cmd == "function":
        out = Path(a.out)
        for rec in recs:
            fn = out / "data" / NS / "function" / "structures" / ("place_%s.mcfunction" % rec["id"])
            fn.parent.mkdir(parents=True, exist_ok=True)
            lines_out = commands(rec, subs)
            refused = function_limits.check_lines(lines_out, str(fn))
            if refused:
                for _n, _cmd, _why in refused:
                    print("REFUSED line %d: %s" % (_n, _why))
                    print("   %s" % _cmd)
                raise SystemExit("%s: %d command(s) the server would refuse; not written" % (fn, len(refused)))
            fn.write_text("\n".join(commands(rec, subs)) + "\n", encoding="utf-8", newline="\n")
            print("wrote", fn)
        (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers donor structure placements (generated)"}}) + "\n", encoding="utf-8")
        return 0
    import runtime_guard
    runtime_guard.check(a.world, "read")
    bad = 0
    for rec in recs:
        lo, hi = box(rec)
        names, bes = read_world(a.world, lo, hi)
        print("== %s %s..%s" % (rec["id"], lo, hi))
        print("   non-air blocks", sum(names.values()), "block entities", sum(bes.values()), dict(bes))
        for s in subs:
            got, left = names.get(s["to"], 0), names.get(s["from"], 0)
            expected = (rec.get("expect_substituted") or {}).get(s["to"])
            state = "ok" if (expected is None or got == expected) and left == 0 else "MISMATCH"
            if state != "ok":
                bad += 1
            if got or left or expected:
                print("   %-46s %5d (expected %s), unsubstituted left %d  %s" % (s["to"], got, expected, left, state))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
