#!/usr/bin/env python
"""The Surveyors' Benchmark, audited offline: the emitted pack replayed block by block over the natural ground.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). Written by an agent that built none of the place.
This file never imports tools/survey_benchmark.py's or tools/wayside_kit.py's geometry: it reads
data/survey_benchmark.json, the canonical heightmap (tools/ground.py) and the other data files named below, derives what
it expects with its own arithmetic (tools/wayside_audit.py, which imports no builder), REPLAYS the build function and
compares. The only thing taken from the generator is its output: the pack, and (in main) the re-application steps it
hands tools/reapply.py. tests/test_survey_benchmark_audit.py mutates the GENERATOR (the hut a block high, the door
walled, a stake off its line, the plinth a block low, the ramp a step short) with the record untouched, and each is
caught.

The checks, docs/world-building/SURVEY_BENCHMARK.md 'What an audit must check', numbered as there:

  blocks    (1) every written block in blocks.ids; no spawn condition (data/spawn_blocks.json) unscoped by
            data/spawn_block_policy.json for survey_benchmark; no chest, no bed, no lightning rod
  pillar    (2) the 3 by 3 plinth's top on max(ground under it) + 1, every column solid down to its own ground, nothing
            on its outer ring; the pillar pillar.height over it, a chiselled cap, a standing lantern on the cap
  hut       (2, 3) the floor on max(ground under the hut) + 1, every column solid down to its own ground; the walls
            solid to wall_height but for a doorway two cells high in the west wall at door_z; wall_height cells over the
            floor inside free, but for the barrel, cartography table and lectern the record puts there (in the first
            cell, free over them); a solid roof over every column at floor + wall_height + 1
  ramp      (3) from the doorway west, one block down a step, each an acacia stair facing east (the way up) on its own
            foundation, every step above its ground, while the next would still be above it; nothing to climb past it
  stakes    (2, 4) stakes.count stakes, the k-th the nearest column to the point k * stakes.every along the line from
            the pillar to stakes.toward: two fence posts on the column's own ground and a standing lantern
  find      (5) the barrel at survey_benchmark_store container.at; the trigger box free cells a player can stand in,
            touching it, inside the hut
  attached  (6) every lantern and sign on a solid block written before it
  boxes     (6) every write inside the function's forceload, bbox.forceload and bbox.writes; clears inside bbox.clear
  steps     (6) R9BM holds every written column, runs the build and releases; the function passes function_limits
  site, seen (7) clear of the Rift polygon by the rim sculpt's reach, Rift regions, towns, other places' boxes,
            placements and Habitat Blocks; the pillar's lantern in sight of a standing eye from Victory Road

NOT checked, and it needs a running server: that the fills land, that the cache is granted, how the place looks.

  python tools/survey_benchmark_audit.py [--pack DIR] [--data FILE] [--source-root R]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wayside_audit as A  # noqa: E402

PLACE = "survey_benchmark"
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / ("cobblers_%s" % PLACE)
FUNCTION = "data/cobblers/function/%s/build.mcfunction" % PLACE
NEVER_HERE = ("minecraft:lightning_rod",)
# data/survey_benchmark.json hut.why: "Inside, the party's barrel (the find), a cartography table and an empty lectern."
FURNISHINGS = ("minecraft:barrel", "minecraft:cartography_table", "minecraft:lectern")
RAMP = "minecraft:acacia_stairs"
FENCE = "minecraft:acacia_fence"


class Expect:
    def __init__(self, rec, g):
        self.rec = rec
        self.px, self.pz = rec["pillar"]["at"]
        self.ph = rec["pillar"]["height"]
        self.plinth = [(x, z) for x in range(self.px - 1, self.px + 2) for z in range(self.pz - 1, self.pz + 2)]
        self.pb = max(g(x, z) for x, z in self.plinth) + 1
        self.cap = self.pb + self.ph + 1
        h = rec["hut"]
        self.x0, self.x1 = h["x"]
        self.z0, self.z1 = h["z"]
        self.wh, self.door_z = h["wall_height"], h["door_z"]
        self.bf = max(g(x, z) for x in range(self.x0, self.x1 + 1) for z in range(self.z0, self.z1 + 1)) + 1
        s = rec["stakes"]
        tx, tz = s["toward"]
        L = math.hypot(tx - self.px, tz - self.pz)
        self.stake_points = [(self.px + (tx - self.px) * k * s["every"] / L, self.pz + (tz - self.pz) * k * s["every"] / L)
                             for k in range(1, s["count"] + 1)]

    def in_hut(self, k):
        return self.x0 < k[0] < self.x1 and self.z0 < k[2] < self.z1 and self.bf < k[1] <= self.bf + self.wh


def check_pillar(R, E, W):
    for x, z in E.plinth:
        if not A.column_on_ground(W, x, z, E.pb):
            R.err("pillar", "the plinth column (%d, %d) is not solid from its ground y%d to the plinth top y%d (= max "
                  "ground under it + 1)" % (x, z, W.ground(x, z), E.pb))
            return
        if (x, z) != (E.px, E.pz) and not W.free((x, E.pb + 1, z)):
            R.err("pillar", "the plinth's ring holds %s at y%d: its top is not y%d" % (W.at((x, E.pb + 1, z)), E.pb + 1,
                                                                                       E.pb))
            return
    for y in range(E.pb + 1, E.cap):
        if not W.written_solid((E.px, y, E.pz)):
            R.err("pillar", "the pillar is %s at y%d" % (W.at((E.px, y, E.pz)), y))
            return
    if W.b((E.px, E.cap, E.pz)) != "minecraft:chiseled_stone_bricks":
        R.err("pillar", "the cap (%d, %d, %d) is %s" % (E.px, E.cap, E.pz, W.at((E.px, E.cap, E.pz))))
    lan = W.at((E.px, E.cap + 1, E.pz))
    if A.base(lan) != "minecraft:lantern" or A.prop(lan, "hanging") != "false":
        R.err("pillar", "no standing lantern on the cap at y%d: %s" % (E.cap + 1, lan))
    R.note("pillar: plinth y%d, cap y%d, lantern y%d" % (E.pb, E.cap, E.cap + 1))


def check_hut(R, E, W):
    for x in range(E.x0, E.x1 + 1):
        for z in range(E.z0, E.z1 + 1):
            if not A.column_on_ground(W, x, z, E.bf):
                R.err("hut", "the hut column (%d, %d) is not solid from its ground y%d to the floor y%d (= max ground "
                      "under the hut + 1)" % (x, z, W.ground(x, z), E.bf))
                return
            ring = x in (E.x0, E.x1) or z in (E.z0, E.z1)
            for y in range(E.bf + 1, E.bf + E.wh + 1):
                k = (x, y, z)
                door = (x, z) == (E.x0, E.door_z) and y in (E.bf + 1, E.bf + 2)
                if ring and not door and not W.written_solid(k):
                    R.err("hut", "the wall is open at %s (%s)" % (k, W.at(k)))
                    return
                if door and not W.free(k):
                    R.err("hut", "the west doorway %s is %s" % (k, W.at(k)))
                    return
                if not ring:
                    st = W.at(k)
                    if W.free(k) or (y == E.bf + 1 and A.base(st) in FURNISHINGS):
                        continue
                    if A.base(st) == "minecraft:lantern" and A.prop(st, "hanging") == "true" and y >= E.bf + 3:
                        continue
                    R.err("hut", "inside the hut %s is %s: not %d free cells over the floor y%d"
                          % (k, st, E.wh, E.bf))
                    return
            for y in (E.bf + 2, E.bf + 3):
                if not ring and A.base(W.at((x, E.bf + 1, z))) in FURNISHINGS and not W.free((x, y, z)):
                    R.err("hut", "over the furnishing at (%d, %d) the cell y%d is %s" % (x, z, y, W.at((x, y, z))))
                    return
    roof = E.bf + E.wh + 1
    for x in range(E.x0, E.x1 + 1):
        for z in range(E.z0, E.z1 + 1):
            if not W.written_solid((x, roof, z)):
                R.err("hut", "the roof is open at (%d, %d, %d)" % (x, roof, z))
                return
    R.note("hut: floor y%d, walls to y%d, roof y%d" % (E.bf, E.bf + E.wh, roof))


def check_ramp(R, E, W):
    """Acacia stairs facing east down from the doorway sill: the j-th at x0 - 1 - j, y bf - j, while that is above the
    ground of its column."""
    z = E.door_z
    j, n = 0, 0
    while True:
        x, y = E.x0 - 1 - j, E.bf - j
        if y <= W.ground(x, z):
            break
        st = W.at((x, y, z))
        if A.base(st) != RAMP or A.prop(st, "facing") != "east":
            R.err("ramp", "step %d of the ramp (%d, %d, %d) is %s, not an acacia stair facing east (one block down a "
                  "step from the sill y%d, while above the ground y%d)" % (j, x, y, z, st, E.bf, W.ground(x, z)))
            return
        if not A.column_on_ground(W, x, z, y):
            R.err("ramp", "step %d (%d, %d, %d) does not stand on a foundation down to its ground" % (j, x, y, z))
            return
        for h in (1, 2):
            if not W.free((x, y + h, z)):
                R.err("ramp", "over step %d the cell y%d is %s" % (j, y + h, W.at((x, y + h, z))))
                return
        n, j = n + 1, j + 1
    stray = sorted(k for k, s in W.rep.state.items() if A.base(s) == RAMP and not (k[2] == z and E.x0 - n <= k[0] < E.x0
                                                                                   and k[1] == E.bf - (E.x0 - 1 - k[0])))
    if stray:
        R.err("ramp", "%d acacia stair(s) off the one-block-a-step ramp, e.g. %s" % (len(stray), stray[:3]))
    if n == 0 and W.ground(E.x0 - 1, z) < E.bf - 1:
        R.err("ramp", "the doorway's sill y%d stands over ground y%d with no ramp" % (E.bf, W.ground(E.x0 - 1, z)))
    last_y = E.bf - (n - 1) if n else E.bf
    after = (E.x0 - 1 - n, z)
    if W.ground(*after) > last_y:
        R.err("ramp", "past the ramp the ground at %s is y%d, over its last step y%d" % (after, W.ground(*after), last_y))
    R.note("ramp: %d step(s) from the sill y%d" % (n, E.bf))


def check_stakes(R, E, W):
    cols = sorted({(k[0], k[2]) for k, s in W.rep.state.items() if A.base(s) == FENCE})
    if len(cols) != len(E.stake_points):
        R.err("stakes", "%d stake column(s) written, the record names %d" % (len(cols), len(E.stake_points)))
    for i, (ex, ez) in enumerate(E.stake_points):
        near = [c for c in cols if abs(c[0] - ex) <= 0.5 and abs(c[1] - ez) <= 0.5]
        if not near:
            R.err("stakes", "no stake at the nearest column to (%.2f, %.2f), %d blocks along the line to %s"
                  % (ex, ez, (i + 1) * E.rec["stakes"]["every"], E.rec["stakes"]["toward"]))
            continue
        x, z = near[0]
        gy = W.ground(x, z)
        posts = [W.b((x, y, z)) for y in (gy + 1, gy + 2)]
        lan = W.at((x, gy + 3, z))
        if posts != [FENCE, FENCE] or A.base(lan) != "minecraft:lantern" or A.prop(lan, "hanging") != "false":
            R.err("stakes", "the stake at (%d, %d) is not two posts on its ground y%d and a lantern: %s, %s"
                  % (x, z, gy, posts, lan))
    R.note("stakes: %s" % cols)


def audit(rec, g, pack, steps=None, data=DATA):
    R = A.Report()
    lines, rep = A.load_pack(pack, FUNCTION)
    if rep is None:
        R.err("steps", "no %s in %s: build the pack first" % (FUNCTION, pack))
        return R
    W = A.World(rep, g)
    E = Expect(rec, g)
    A.check_blocks(R, rep, rec, PLACE, extra_never=NEVER_HERE, data=data)
    check_pillar(R, E, W)
    check_hut(R, E, W)
    check_ramp(R, E, W)
    check_stakes(R, E, W)
    A.check_find(R, W, rec["find"]["reward"], E.in_hut, data)
    A.check_attached(R, W)
    A.check_boxes(R, rep, rec)
    A.check_site(R, rep, rec, PLACE, (E.px, E.pz), data)
    A.check_seen(R, W, (E.px, E.cap + 1, E.pz), "victory_road", "the pillar's lantern", data)
    A.check_steps(R, rep, lines, steps, PLACE)
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--data", default=str(DATA / ("%s.json" % PLACE)))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rec = json.loads(Path(a.data).read_text(encoding="utf-8"))
    g = G.load(a.source_root)
    import survey_benchmark  # the re-application steps are the generator's OUTPUT, checked here, never its geometry
    steps = survey_benchmark.placement_steps(None, g)
    return A.main_report(audit(rec, g, a.pack, steps), "survey_benchmark_audit")


if __name__ == "__main__":
    raise SystemExit(main())
