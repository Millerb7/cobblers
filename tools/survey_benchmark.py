#!/usr/bin/env python
"""The Surveyors' Benchmark in the Rift Foot, from data/survey_benchmark.json: a trig pillar on a rise beside Victory
Road, the survey party's hut, and a line of lit sighting stakes toward the Rift entry.

The owner, 2026-10-03 (relayed): "the southern map, still the thinnest part of the world." Measured that day, Victory
Road's stretch here is the only run of a southern route with no authored thing within 300 blocks
(docs/world-building/SURVEY_BENCHMARK.md). Every part is a proven pattern (tools/wayside_kit.py):

  the pillar    a stone-brick trig pillar on a 3 by 3 plinth seated on max(ground under it) + 1 with a cobblestone
                foundation down to the ground (tools/drovers_hollow.py's convention), a chiselled cap and a lantern.
  the hut       the same seating; cobblestone base course, acacia frame and planks, a flat slab roof, glass in its long
                walls, a door in the west wall with a stair ramp down to the ground (tools/drovers_hollow.py ramp()).
  the stakes    acacia fence posts on their own column's ground, each with a lantern, toward the Rift entry.
  the find      NOT in this pack: a cache in data/rewards.json (survey_benchmark_store), granted once per player by
                tools/rewards_pack.py's advancement on reaching the barrel in the hut (ADR-002). The barrel is scenery.

Ground is tools/ground.py's (the canonical heightmap, rounded); nothing reads a world. No carving, no Habitat Block, no
NPC. Its step, R9BM, runs before R9E with the other block passes of the south.

  python tools/survey_benchmark.py [build] [--source-root R] [--out DIR]   write the pack
  python tools/survey_benchmark.py --report [--source-root R]             the numbers and steps; writes nothing
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

PLACE = "survey_benchmark"
DATA = ROOT / "data" / ("%s.json" % PLACE)
DEFAULT_OUT = ROOT / "build" / "datapacks" / ("cobblers_%s" % PLACE)
SCHEMA = "cobblers.survey-benchmark/1"
FN = PLACE
STEP = "R9BM"
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


def load(path=DATA):
    doc = K.load_record(path, SCHEMA, PLACE)
    h = doc["hut"]
    if h["wall_height"] < 3:
        raise K.PlaceError("the hut needs three blocks of headroom")
    if not (h["z"][0] < h["door_z"] < h["z"][1]):
        raise K.PlaceError("the hut's door is in its west wall, between the corners")
    px, pz = doc["pillar"]["at"]
    if not (px + 1 < h["x"][0] - 1):
        raise K.PlaceError("the hut stands east of the pillar's plinth, with a gap")
    return doc


def ramp(p, g, x, z, dx, top, facing):
    """Acacia stairs down from a doorway sill at `top` (the floor block's y), one block a step along dx, each on a
    cobblestone foot, until a step would be at or under the ground (tools/drovers_hollow.py ramp())."""
    for j in range(0, 16):
        y = top - j
        sx = x + dx * (j + 1)
        if y <= g(sx, z):
            return
        for fy in range(g(sx, z) + 1, y):
            p.put(sx, fy, z, "minecraft:cobblestone")
        p.put(sx, y, z, K.stair("acacia", facing))


def plan(doc, g):
    p = K.Plan(doc["blocks"]["ids"], PLACE)
    signs = doc["blocks"]["signs"]
    # 1. the pillar on its plinth
    px, pz = doc["pillar"]["at"]
    ph = doc["pillar"]["height"]
    plinth = [(x, z) for x in range(px - 1, px + 2) for z in range(pz - 1, pz + 2)]
    pb = max(g(x, z) for x, z in plinth) + 1
    for x, z in plinth:
        for y in range(g(x, z) + 1, pb):
            p.put(x, y, z, "minecraft:cobblestone")
        p.put(x, pb, z, "minecraft:stone_bricks")
    for y in range(pb + 1, pb + ph + 1):
        p.put(px, y, pz, "minecraft:stone_bricks")
    cap = pb + ph + 1
    p.put(px, cap, pz, "minecraft:chiseled_stone_bricks")
    # 2. the hut
    h = doc["hut"]
    x0, x1 = h["x"]
    z0, z1 = h["z"]
    wh = h["wall_height"]
    bf = max(g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)) + 1
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            for y in range(g(x, z) + 1, bf):
                p.put(x, y, z, "minecraft:cobblestone")
            ring = x in (x0, x1) or z in (z0, z1)
            p.put(x, bf, z, "minecraft:cobblestone" if ring else "minecraft:acacia_planks")
            for dy in range(1, wh + 1):
                y = bf + dy
                if not ring:
                    p.put(x, y, z, "minecraft:air")
                elif x in (x0, x1) and z in (z0, z1):
                    p.put(x, y, z, "minecraft:stripped_acacia_log[axis=y]")
                elif dy == 1:
                    p.put(x, y, z, "minecraft:cobblestone")
                elif z in (z0, z1) and dy in (2, 3) and (x - x0) % 2 == 0:
                    p.put(x, y, z, "minecraft:glass")
                else:
                    p.put(x, y, z, "minecraft:acacia_planks")
    for dy in (1, 2):
        p.put(x0, bf + dy, h["door_z"], "minecraft:air")
    for x in range(x0 - 1, x1 + 2):
        for z in range(z0 - 1, z1 + 2):
            p.put(x, bf + wh + 1, z, "minecraft:acacia_slab[type=bottom,waterlogged=false]")
    ramp(p, g, x0, h["door_z"], -1, bf, "east")
    zc = h["door_z"]
    barrel = (x1 - 1, bf + 1, zc)
    p.put(*barrel, "minecraft:barrel[facing=west,open=false]")
    p.put(x1 - 1, bf + 1, zc - 1, "minecraft:cartography_table")
    p.put(x1 - 1, bf + 1, zc + 1, "minecraft:lectern[facing=west,has_book=false,powered=false]")
    # 3. the sighting stakes toward the Rift entry
    tx, tz = doc["stakes"]["toward"]
    L = math.hypot(tx - px, tz - pz)
    ux, uz = (tx - px) / L, (tz - pz) / L
    stakes = []
    for k in range(1, doc["stakes"]["count"] + 1):
        d = k * doc["stakes"]["every"]
        x, z = px + int(round(ux * d)), pz + int(round(uz * d))
        gy = g(x, z)
        p.put(x, gy + 1, z, K.fence("acacia"))
        p.put(x, gy + 2, z, K.fence("acacia"))
        stakes.append((x, gy + 3, z))
    # --- what hangs
    p.hang(px, cap + 1, pz, K.lantern(False))
    for s in stakes:
        p.hang(*s, K.lantern(False))
    p.hang((x0 + x1) // 2, bf + wh, zc, K.lantern(True))
    p.hang(px - 1, pb + 2, pz, K.wall_sign("acacia", "west", signs["pillar"]))
    p.hang(x0 - 1, bf + 3, zc - 1, K.wall_sign("acacia", "west", signs["door"]))
    p.hang(barrel[0], bf + 2, zc, K.wall_sign("acacia", "west", signs["store"]))
    blocks = p.blocks()
    clear = K.above_ground_box(blocks, g)
    low = min(g(x, z) for x in range(clear[0], clear[2] + 1) for z in range(clear[1], clear[3] + 1))
    ks = list(blocks)
    trig = ([barrel[0] - 1, bf + 1, zc - 1], [barrel[0] - 1, bf + 2, zc + 1])
    top = max(cap + 1, bf + wh + 1)
    return {"plan": p, "plinth": pb, "cap": cap, "hut_floor": bf, "stakes": stakes, "barrel": barrel, "trigger": trig,
            "blocks": blocks, "clear": clear, "clear_y": (low + 1, top + 2),
            "bbox": (min(k[0] for k in ks), min(k[2] for k in ks), max(k[0] for k in ks), max(k[2] for k in ks)),
            "y_range": (min(k[1] for k in ks), max(k[1] for k in ks))}


def files(doc, g):
    pl = plan(doc, g)
    header = ["# Generated by tools/survey_benchmark.py from data/survey_benchmark.json. Re-run to rebuild; do not edit.",
              "# The Surveyors' Benchmark in the Rift Foot: the trig pillar, the party's hut and the sighting stakes.",
              "# Run BEFORE R9E (step %s), with the other block passes of the south." % STEP]
    lines = K.build_lines(header, pl["plan"], pl["clear"], pl["clear_y"])
    return K.pack_files(FN, "Cobblers: the Surveyors' Benchmark (tools/survey_benchmark.py)", lines), pl


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, step R9BM BEFORE R9E: hold the chunks, build, release."""
    import ground as G
    doc = doc or load()
    g = g or G.load()
    pl = plan(doc, g)
    return K.placement_steps(K.hold_box(pl["blocks"], pl["clear"]), FN)


def report(doc, pl, g):
    px, pz = doc["pillar"]["at"]
    target = (px, pl["cap"] + 1, pz)
    n, best = K.visible_from_route(g, K.route_paths()["victory_road"], target)
    return [
        "plinth y%d, cap y%d (lantern y%d); hut floor y%d; stakes (lantern blocks) %s"
        % (pl["plinth"], pl["cap"], pl["cap"] + 1, pl["hut_floor"], pl["stakes"]),
        "blocks written %d; bbox x%d..%d z%d..%d y%d..%d; above-ground clear box %s y%s; hold %s"
        % ((len(pl["blocks"]),) + (pl["bbox"][0], pl["bbox"][2], pl["bbox"][1], pl["bbox"][3]) + pl["y_range"]
           + (pl["clear"], pl["clear_y"], K.hold_box(pl["blocks"], pl["clear"]))),
        "nearest walked point of Victory Road %.0f blocks from the write box"
        % K.distance_to_paths(pl["bbox"], ["victory_road"]),
        "the pillar's lantern %s is in sight of a standing eye from %d of Victory Road's points (every 4th within %d); "
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
