#!/usr/bin/env python
"""The Challengers' Cairn on the south strand, from data/challengers_cairn.json: a field-stone cairn beside the foot of
Victory Road, a ring of marker stones, and a stone-lined cist under it reached by a stair cut down from the south.

The owner, 2026-10-03 (relayed): "the southern map, still the thinnest part of the world." Measured that day, the
emptiest ground in the south that a player walks past is this stretch of the strand beside Victory Road
(docs/world-building/CHALLENGERS_CAIRN.md). Every part is a proven pattern (tools/wayside_kit.py):

  the cairn    a mound of field stone on each column's own ground (tools/ground.py, rounded; never a world), a
               chiselled capstone and a lantern on the crown. Trees and replaceable plants over it are cleared first.
  the cist     carved the Ursaluna den's way: a stone shell filled SOLID `margin` blocks beyond every void, never in the
               top `keep_natural_top` block of a column, then the void cut out; lined in stone bricks.
  the stair    roofed while two or more blocks of ground stand over it, then an open trench between dressed walls.
  the find     NOT in this pack: a cache in data/rewards.json (challengers_cairn_cist), granted once per player by
               tools/rewards_pack.py's advancement on reaching the cist's north end (ADR-002). The barrel is scenery.

No Habitat Block and no NPC. Its step, R9CN, runs before R9E with the other block passes of the south.

  python tools/challengers_cairn.py [build] [--source-root R] [--out DIR]   write the pack
  python tools/challengers_cairn.py --report [--source-root R]             the numbers and steps; writes nothing
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wayside_kit as K  # noqa: E402

PLACE = "challengers_cairn"
DATA = ROOT / "data" / ("%s.json" % PLACE)
DEFAULT_OUT = ROOT / "build" / "datapacks" / ("cobblers_%s" % PLACE)
SCHEMA = "cobblers.challengers-cairn/1"
FN = PLACE
STEP = "R9CN"
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()

FIELD_STONE = ["minecraft:cobblestone", "minecraft:mossy_cobblestone", "minecraft:stone", "minecraft:andesite",
               "minecraft:cobblestone", "minecraft:mossy_cobblestone"]
LINING = ["minecraft:stone_bricks", "minecraft:stone_bricks", "minecraft:mossy_stone_bricks",
          "minecraft:cracked_stone_bricks"]


def load(path=DATA):
    doc = K.load_record(path, SCHEMA, PLACE)
    if doc["cist"]["height"] < 2 or doc["passage"]["height"] < 2:
        raise K.PlaceError("a player needs two blocks of air to walk the cist and the stair")
    if doc["cist"]["floor_below_ground"] < doc["cist"]["height"] + 2:
        raise K.PlaceError("the cist must have two blocks of ground over its roof")
    if doc["ring"]["radius"] <= doc["cairn"]["radius"] + 2:
        raise K.PlaceError("the ring stands clear of the cairn")
    return doc


def plan(doc, g):
    p = K.Plan(doc["blocks"]["ids"], PLACE)
    cx, cz = doc["cairn"]["centre"]
    R, H = doc["cairn"]["radius"], doc["cairn"]["height"]
    c = doc["cist"]
    h, ch = c["half"], c["height"]
    foot = [(x, z) for x in range(cx - h, cx + h + 1) for z in range(cz - h, cz + h + 1)]
    F = min(g(x, z) for x, z in foot) - c["floor_below_ground"]
    cist = {(x, y, z) for x, z in foot for y in range(F + 1, F + ch + 1)}
    ps = doc["passage"]
    d = tuple(ps["direction"])
    first = (cx + d[0] * (h + 1), cz + d[1] * (h + 1))
    steps = K.stair_passage(g, first, d, F, ps["half_width"], ps["height"])
    voids = cist | K.passage_voids(g, steps, ps["height"])
    # 1. the shell, then the lining (every shell block that faces a void), then the cist floor
    sh = K.shell(g, voids, c["margin"], c["keep_natural_top"])
    for k in sorted(sh):
        p.put(*k, "minecraft:stone")
    for (x, y, z) in sorted(sh):
        if any((x + a, y + b, z + e) in voids for a, b, e in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
                                                              (0, 0, 1), (0, 0, -1))):
            p.put(x, y, z, K.pick(x, y, z, LINING))
    for x, z in foot:
        p.put(x, F, z, "minecraft:polished_andesite")
    # 2. the stair's floor, its trench walls and the face over its mouth
    K.dress_passage(p, g, steps, ps["height"], d, "minecraft:polished_andesite", "stone_brick", LINING,
                    "minecraft:stone_bricks")
    # 3. the cairn: each column from its own ground up to the mound's height there
    crown = None
    for x in range(cx - R, cx + R + 1):
        for z in range(cz - R, cz + R + 1):
            r = math.hypot(x - cx, z - cz)
            if r > R + 0.5:
                continue
            top = g(cx, cz) + max(1, int(round(H * (1 - r / (R + 0.5)))))
            for y in range(g(x, z) + 1, top + 1):
                p.put(x, y, z, K.pick(x, y, z, FIELD_STONE))
            if (x, z) == (cx, cz):
                crown = top
    p.put(cx, crown + 1, cz, "minecraft:chiseled_stone_bricks")
    # 4. the ring of marker stones, leaving out any that would stand in or against the stair's trench
    near_stair = {(x, z) for s in steps for (x, z) in s["cols"] + s["sides"]}
    rg = doc["ring"]
    ring = []
    for i in range(rg["stones"]):
        a = 2 * math.pi * i / rg["stones"]
        x, z = cx + int(round(rg["radius"] * math.cos(a))), cz + int(round(rg["radius"] * math.sin(a)))
        if any(abs(x - sx) <= 1 and abs(z - sz) <= 1 for sx, sz in near_stair):
            continue
        for y in range(g(x, z) + 1, g(x, z) + 1 + (2 if i % 2 else 3)):
            p.put(x, y, z, "minecraft:polished_andesite" if y == g(x, z) + 1 else "minecraft:andesite")
        ring.append((x, z))
    # 5. the void, cut last of the structure; then what stands in it
    for k in voids:
        p.put(*k, "minecraft:air")
    barrel = (cx, F + 1, cz - h)
    p.put(*barrel, "minecraft:barrel[facing=south,open=false]")
    for x, z in ((cx - h, cz - h), (cx + h, cz - h), (cx - h, cz + h), (cx + h, cz + h)):
        p.put(x, F + 1, z, K.pick(x, F + 1, z, ["minecraft:mossy_cobblestone", "minecraft:cobblestone"]))
    # --- what hangs: lanterns, signs
    signs = doc["blocks"]["signs"]
    p.hang(cx, crown + 2, cz, K.lantern(False))
    p.hang(cx, F + ch, cz, K.lantern(True))
    p.hang(cx, F + 2, cz - h, K.wall_sign("spruce", "south", signs["cist"]))
    roofed = [s for s in steps if not s["open"]]
    opened = [s for s in steps if s["open"]]
    if len(roofed) > 1:
        s = roofed[1]
        mx, mz = s["cols"][len(s["cols"]) // 2]
        p.hang(mx, s["floor"] + ps["height"], mz, K.lantern(True))
    if opened:
        last = opened[-1]
        for x, z in last["sides"]:
            p.hang(x, max(g(x, z), last["floor"]) + 1, z, K.lantern(False))
        fo = opened[0]
        mx, mz = fo["cols"][len(fo["cols"]) // 2]
        p.hang(mx, fo["floor"] + ps["height"], mz, K.wall_sign("spruce", K.FACING[d], signs["head"]))
    blocks = p.blocks()
    clear = K.above_ground_box(blocks, g)
    low = min(g(x, z) for x in range(clear[0], clear[2] + 1) for z in range(clear[1], clear[3] + 1))
    ks = list(blocks)
    trig = ([cx - h, F + 1, cz - h + 1], [cx + h, F + 2, cz - h + 2])
    return {"plan": p, "floor": F, "crown": crown, "voids": voids, "cist": cist, "steps": steps, "ring": ring,
            "barrel": barrel, "trigger": trig, "blocks": blocks, "clear": clear, "clear_y": (low + 1, crown + 3),
            "bbox": (min(k[0] for k in ks), min(k[2] for k in ks), max(k[0] for k in ks), max(k[2] for k in ks)),
            "y_range": (min(k[1] for k in ks), max(k[1] for k in ks))}


def files(doc, g):
    pl = plan(doc, g)
    header = ["# Generated by tools/challengers_cairn.py from data/challengers_cairn.json. Re-run to rebuild; do not edit.",
              "# The Challengers' Cairn on the south strand: the cairn, its ring of stones and the cist under it.",
              "# Run BEFORE R9E (step %s), with the other block passes of the south." % STEP]
    lines = K.build_lines(header, pl["plan"], pl["clear"], pl["clear_y"])
    return K.pack_files(FN, "Cobblers: the Challengers' Cairn (tools/challengers_cairn.py)", lines), pl


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, step R9CN BEFORE R9E: hold the chunks, build, release."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    pl = plan(doc, g)
    return K.placement_steps(K.hold_box(pl["blocks"], pl["clear"]), FN)


def report(doc, pl, g):
    cx, cz = doc["cairn"]["centre"]
    roofed = [s for s in pl["steps"] if not s["open"]]
    under = K.passage_voids(g, roofed, doc["passage"]["height"])
    cv = K.cover(g, under, skip=lambda x, z: math.hypot(x - cx, z - cz) <= doc["cairn"]["radius"] + 0.5)
    cv_cist = K.cover(g, pl["cist"])
    worst = min(cv.items(), key=lambda kv: kv[1]) if cv else (None, None)
    paths = K.route_paths()
    target = (cx, pl["crown"] + 2, cz)
    n, best = K.visible_from_route(g, paths["victory_road"], target)
    return [
        "cairn crown y%d (capstone y%d, lantern y%d); cist floor y%d, %d void blocks, least ground over the cist %d"
        % (pl["crown"], pl["crown"] + 1, pl["crown"] + 2, pl["floor"], len(pl["cist"]), min(cv_cist.values())),
        "stair: %d steps, %d roofed, %d open; least ground over a roofed stair void outside the cairn %s at %s"
        % (len(pl["steps"]), len(roofed), len(pl["steps"]) - len(roofed), worst[1], worst[0]),
        "ring stones at %s" % (pl["ring"],),
        "blocks written %d; bbox x%d..%d z%d..%d y%d..%d; above-ground clear box %s y%s; hold %s"
        % ((len(pl["blocks"]),) + (pl["bbox"][0], pl["bbox"][2], pl["bbox"][1], pl["bbox"][3]) + pl["y_range"]
           + (pl["clear"], pl["clear_y"], K.hold_box(pl["blocks"], pl["clear"]))),
        "nearest walked point of Victory Road %.0f blocks from the write box"
        % K.distance_to_paths(pl["bbox"], ["victory_road"]),
        "the capstone lantern %s is in sight of a standing eye from %d of Victory Road's points (every 4th within %d); "
        "the clearest, %s, by %.1f blocks" % ((target, n, K.SIGHT_RANGE) + best),
        "cache: barrel %s, trigger %s; data/rewards.json %s: %s"
        % (pl["barrel"], pl["trigger"], doc["find"]["reward"],
           K.reward_check(doc["find"]["reward"], pl["barrel"], pl["trigger"])),
        "steps %s: %s" % (STEP, json.dumps([list(s) for s in placement_steps(doc, g)])),
    ]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build",))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the numbers and the steps; write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, pl = files(doc, g)
    if a.report:
        print("\n".join(report(doc, pl, g)))
        return 0
    K.write(out_files, a.out)
    n = sum(1 for l in out_files["data/%s/function/%s/build.mcfunction" % (K.NS, FN)].splitlines()
            if l and not l.startswith("#"))
    print("%s: %d files -> %s (build: %d commands)" % (PLACE, len(out_files), a.out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
