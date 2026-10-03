#!/usr/bin/env python
"""The Dry Cistern on the Scorched Plateau's west brow, from data/dry_cistern.json: a rock-cut cistern under the
tableland, the keepers' stair down into it, its draw-shaft and well-head, and the keeper's fallen house.

The owner, 2026-10-03 (relayed): "the southern map, still the thinnest part of the world." Measured that day, the brow
above Route 8 here is the second emptiest ground in the south a player walks past (docs/world-building/DRY_CISTERN.md).
Every part is a proven pattern (tools/wayside_kit.py):

  the cistern   carved the Ursaluna den's way: a stone shell filled SOLID `margin` blocks beyond every void, never in
                the top `keep_natural_top` block of a column, then the void cut out; lined in red sandstone and
                terracotta, a white terracotta band for the old water line, four pillars under the roof.
  the stair     roofed while two or more blocks of ground stand over it, then an open trench between dressed walls.
  the shaft     a one-block draw-shaft with a ladder, capped by a closed trapdoor in the ground's top block, under a
                well-head of acacia posts, a crossbar and a hanging lantern.
  the house     roofless, on max(ground under its walls) + 1 with a foundation down to the ground
                (tools/drovers_hollow.py's convention); walls 1 to 3 high by turns.
  the find      NOT in this pack: a cache in data/rewards.json (dry_cistern_store), granted once per player by
                tools/rewards_pack.py's advancement on reaching the cistern's east end (ADR-002). The barrel is scenery.

Ground is tools/ground.py's (the canonical heightmap, rounded); nothing reads a world. No Habitat Block and no NPC.
Its step, R9CI, runs before R9E with the other block passes of the south.

  python tools/dry_cistern.py [build] [--source-root R] [--out DIR]   write the pack
  python tools/dry_cistern.py --report [--source-root R]             the numbers and steps; writes nothing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wayside_kit as K  # noqa: E402

PLACE = "dry_cistern"
DATA = ROOT / "data" / ("%s.json" % PLACE)
DEFAULT_OUT = ROOT / "build" / "datapacks" / ("cobblers_%s" % PLACE)
SCHEMA = "cobblers.dry-cistern/1"
FN = PLACE
STEP = "R9CI"
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()

LINING = ["minecraft:red_sandstone", "minecraft:red_sandstone", "minecraft:cut_red_sandstone", "minecraft:terracotta",
          "minecraft:orange_terracotta"]
HOUSE = ["minecraft:terracotta", "minecraft:orange_terracotta", "minecraft:brown_terracotta", "minecraft:red_sandstone"]
SIX = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def load(path=DATA):
    doc = K.load_record(path, SCHEMA, PLACE)
    c = doc["chamber"]
    if c["height"] < 3 or doc["passage"]["height"] < 2:
        raise K.PlaceError("a player needs two blocks of air to walk the stair and three under the cistern's roof")
    if c["floor_below_ground"] < c["height"] + 3:
        raise K.PlaceError("the cistern must have three blocks of ground over its roof")
    sx, sz = doc["shaft"]["at"]
    cx, cz = c["centre"]
    if sx != cx + c["half_x"] or not (cz - c["half_z"] <= sz <= cz + c["half_z"]):
        raise K.PlaceError("the draw-shaft stands in the cistern's east row, against the east wall its ladder hangs on")
    return doc


def plan(doc, g):
    p = K.Plan(doc["blocks"]["ids"], PLACE)
    c = doc["chamber"]
    cx, cz = c["centre"]
    hx, hz, ch = c["half_x"], c["half_z"], c["height"]
    foot = [(x, z) for x in range(cx - hx, cx + hx + 1) for z in range(cz - hz, cz + hz + 1)]
    F = min(g(x, z) for x, z in foot) - c["floor_below_ground"]
    room = {(x, y, z) for x, z in foot for y in range(F + 1, F + ch + 1)}
    ps = doc["passage"]
    d = tuple(ps["direction"])
    first = (cx - hx - 1, cz) if d == (-1, 0) else None
    if first is None:
        raise K.PlaceError("the keepers' stair leaves the cistern's west end (direction [-1, 0])")
    steps = K.stair_passage(g, first, d, F, ps["half_width"], ps["height"])
    sx, sz = doc["shaft"]["at"]
    shaft = {(sx, y, sz) for y in range(F + ch + 1, g(sx, sz))}
    voids = room | K.passage_voids(g, steps, ps["height"]) | shaft
    # 1. the shell, the lining (with the water line), the floor
    sh = K.shell(g, voids, c["margin"], c["keep_natural_top"])
    for k in sorted(sh):
        p.put(*k, "minecraft:stone")
    wl = F + c["water_line_above_floor"]
    for (x, y, z) in sorted(sh):
        if any((x + a, y + b, z + e) in voids for a, b, e in SIX):
            near_room = any((x + a, y + b, z + e) in room for a, b, e in SIX)
            p.put(x, y, z, "minecraft:white_terracotta" if near_room and y == wl else K.pick(x, y, z, LINING))
    for x, z in foot:
        p.put(x, F, z, "minecraft:smooth_red_sandstone")
    # 2. the stair
    K.dress_passage(p, g, steps, ps["height"], d, "minecraft:smooth_red_sandstone", "red_sandstone", LINING,
                    "minecraft:cut_red_sandstone")
    # 3. the keeper's house: foundation, a terracotta floor, walls of broken height, a south doorway
    hs = doc["house"]
    x0, x1 = hs["x"]
    z0, z1 = hs["z"]
    hf = max(g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)) + 1
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            for y in range(g(x, z) + 1, hf):
                p.put(x, y, z, "minecraft:red_sandstone")
            p.put(x, hf, z, "minecraft:terracotta")
            if x in (x0, x1) or z in (z0, z1):
                if (x, z) == (hs["door_x"], z1):
                    continue
                corner = x in (x0, x1) and z in (z0, z1)
                tall = 3 if corner else 1 + (x * 7 + z * 13) % 3
                for y in range(hf + 1, hf + 1 + tall):
                    p.put(x, y, z, K.pick(x, y, z, HOUSE))
    # 4. the well-head over the shaft: a slab ring on each column's ground, two posts, a crossbar, the trapdoor
    gs = g(sx, sz)
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if (dx, dz) == (0, 0):
                continue
            x, z = sx + dx, sz + dz
            if dz == 0:
                for y in range(g(x, z) + 1, gs + 4):
                    p.put(x, y, z, "minecraft:stripped_acacia_log[axis=y]")
            else:
                p.put(x, g(x, z) + 1, z, "minecraft:red_sandstone_slab[type=bottom,waterlogged=false]")
    for x in (sx - 1, sx, sx + 1):
        p.put(x, gs + 4, sz, "minecraft:acacia_log[axis=x]")
    # 5. the void, cut last of the structure; then what stands in it
    for k in voids:
        p.put(*k, "minecraft:air")
    for ox, oz in c["pillars"]:
        for y in range(F + 1, F + ch + 1):
            p.put(cx + ox, y, cz + oz, "minecraft:chiseled_red_sandstone" if y in (F + 1, F + ch)
                  else "minecraft:cut_red_sandstone")
    barrel = (cx + hx, F + 1, cz)
    if barrel[2] == sz:
        raise K.PlaceError("the barrel would stand at the shaft's foot")
    p.put(*barrel, "minecraft:barrel[facing=west,open=false]")
    p.put(x0 + 1, hf + 1, z0 + 1, "minecraft:cauldron")
    # --- what hangs: the trapdoor, ladders, lanterns, chain, signs
    signs = doc["blocks"]["signs"]
    p.hang(sx, gs, sz, "minecraft:acacia_trapdoor[facing=west,half=top,open=false,powered=false,waterlogged=false]")
    for y in range(F + 1, gs):
        p.hang(sx, y, sz, "minecraft:ladder[facing=west,waterlogged=false]")
    p.hang(sx, gs + 3, sz, K.lantern(True))
    p.hang(cx - 3, F + ch, cz, K.lantern(True))
    p.hang(cx + 1, F + ch, cz - hz + 1, K.lantern(True))
    p.hang(barrel[0], F + 2, barrel[2], K.wall_sign("acacia", "west", signs["store"]))
    p.hang(cx, wl, cz - hz, K.wall_sign("acacia", "south", signs["line"]))
    p.hang(x1 - 1, hf + 1, z0 + 1, K.wall_sign("acacia", "south", signs["house"]))
    roofed = [s for s in steps if not s["open"]]
    opened = [s for s in steps if s["open"]]
    # no lantern under the stair roof: it hung in the third block over a step, where a player climbing onto the next
    # step strikes it (the independent audit's headroom check, 2026-10-03); the roof is only the passage height tall
    if opened:
        last = opened[-1]
        for x, z in last["sides"]:
            p.hang(x, max(g(x, z), last["floor"]) + 1, z, K.lantern(False))
        fo = opened[0]
        mx, mz = fo["cols"][len(fo["cols"]) // 2]
        p.hang(mx, fo["floor"] + ps["height"], mz, K.wall_sign("acacia", K.FACING[d], signs["head"]))
    blocks = p.blocks()
    clear = K.above_ground_box(blocks, g)
    low = min(g(x, z) for x in range(clear[0], clear[2] + 1) for z in range(clear[1], clear[3] + 1))
    ks = list(blocks)
    trig = ([barrel[0] - 1, F + 1, barrel[2] - 1], [barrel[0] - 1, F + 2, barrel[2] + 1])
    return {"plan": p, "floor": F, "room": room, "voids": voids, "shaft": shaft, "steps": steps, "barrel": barrel,
            "trigger": trig, "well_lantern": (sx, gs + 3, sz), "house_floor": hf, "blocks": blocks, "clear": clear,
            "clear_y": (low + 1, gs + 6),
            "bbox": (min(k[0] for k in ks), min(k[2] for k in ks), max(k[0] for k in ks), max(k[2] for k in ks)),
            "y_range": (min(k[1] for k in ks), max(k[1] for k in ks))}


def files(doc, g):
    pl = plan(doc, g)
    header = ["# Generated by tools/dry_cistern.py from data/dry_cistern.json. Re-run to rebuild; do not edit.",
              "# The Dry Cistern on the Scorched Plateau's west brow: cistern, stair, draw-shaft, well-head, house.",
              "# Run BEFORE R9E (step %s), with the other block passes of the south." % STEP]
    lines = K.build_lines(header, pl["plan"], pl["clear"], pl["clear_y"])
    return K.pack_files(FN, "Cobblers: the Dry Cistern (tools/dry_cistern.py)", lines), pl


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, step R9CI BEFORE R9E: hold the chunks, build, release."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    pl = plan(doc, g)
    return K.placement_steps(K.hold_box(pl["blocks"], pl["clear"]), FN)


def report(doc, pl, g):
    ps = doc["passage"]
    roofed = [s for s in pl["steps"] if not s["open"]]
    under = pl["room"] | K.passage_voids(g, roofed, ps["height"])
    cv = K.cover(g, under)
    worst = min(cv.items(), key=lambda kv: kv[1])
    paths = K.route_paths()
    n, best = K.visible_from_route(g, paths["route_08_blaine_to_giovanni"], pl["well_lantern"])
    return [
        "cistern floor y%d, %d room void blocks; stair %d steps (%d roofed); shaft %d blocks; least ground over a "
        "roofed void %d at %s" % (pl["floor"], len(pl["room"]), len(pl["steps"]), len(roofed), len(pl["shaft"]),
                                  worst[1], worst[0]),
        "house floor y%d; well-head lantern %s" % (pl["house_floor"], pl["well_lantern"]),
        "blocks written %d; bbox x%d..%d z%d..%d y%d..%d; above-ground clear box %s y%s; hold %s"
        % ((len(pl["blocks"]),) + (pl["bbox"][0], pl["bbox"][2], pl["bbox"][1], pl["bbox"][3]) + pl["y_range"]
           + (pl["clear"], pl["clear_y"], K.hold_box(pl["blocks"], pl["clear"]))),
        "nearest walked point of Route 8 %.0f blocks from the write box"
        % K.distance_to_paths(pl["bbox"], ["route_08_blaine_to_giovanni"]),
        "the well-head lantern is in sight of a standing eye from %d of Route 8's points (every 4th within %d); the "
        "clearest, %s, by %.1f blocks" % ((n, K.SIGHT_RANGE) + best),
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
