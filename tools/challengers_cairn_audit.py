#!/usr/bin/env python
"""The Challengers' Cairn, audited offline: the emitted pack replayed block by block over the natural ground.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). Written by an agent that built none of the place.
This file never imports tools/challengers_cairn.py's or tools/wayside_kit.py's geometry: it reads
data/challengers_cairn.json, the canonical heightmap (tools/ground.py) and the other data files named below, derives
what it expects with its own arithmetic (tools/wayside_audit.py, which imports no builder), REPLAYS the build function
and compares. The only thing taken from the generator is its output: the pack, and (in main) the re-application steps
it hands tools/reapply.py. tests/test_challengers_cairn_audit.py mutates the GENERATOR (a thinner shell, a step two
high, a missing barrel, a capstone a block high, hung blocks first) with the record untouched, and each is caught.

The checks, docs/world-building/CHALLENGERS_CAIRN.md 'What an audit must check', numbered as there:

  blocks    (1) every written block in blocks.ids; no spawn condition (data/spawn_blocks.json) that no
            data/spawn_block_policy.json entry scoped to challengers_cairn allows; no chest, no bed
  cist      (2) floor = min ground over the 5 by 5 footprint - floor_below_ground; the floor written solid; every cist
            cell free of collision unless the record declares what stands there (the cache's barrel) or it is a
            lantern hung over a standing head; every cist cell floor_below_ground - height blocks under the ground
  cover     (2) every roofed stair column has 2 or more blocks of ground over its passage (the record's rule); every
            open one is open to the sky
  stair     (3) one block a step from the landing next to the cist's south edge, each a stone brick stair facing
            south, no stair block off the flight, the top step level with the ground in every lane, no rise past it
  headroom  (3) height (3) cells free of collision over every step (tools/wayside_audit.py says why three)
  shell     (4) every non-void cell within cist.margin of a void, under the column's kept top, written solid
  cairn     (5) the crown on the centre column's ground + cairn.height, a chiselled capstone over it, a standing
            lantern on that; every column within cairn.radius stands on its own ground, solid to its top, no gap;
            the ring: a stone on its own ground at each of ring.stones positions at ring.radius except where the
            stair's corridor runs, and nowhere else
  find      (6) the barrel at data/rewards.json challengers_cairn_cist container.at; the trigger box free cells a
            player can stand in, touching the barrel, inside the cist
  attached  (7) every lantern and sign hangs on a solid block written before it
  boxes     (8) every write inside the function's forceload, bbox.forceload and bbox.writes; clears inside bbox.clear
  steps     (8) R9CN holds every written column, runs the build and releases; the function passes function_limits
  site, seen (9) clear of the Rift, Rift regions, towns, other places' boxes, placements and Habitat Blocks; the
            capstone lantern in sight of a standing eye from Victory Road

NOT checked, and it needs a running server: that the fills land, that the cache is granted, how the place looks.
Collision is judged from Minecraft's block shapes as documented, not simulated.

  python tools/challengers_cairn_audit.py [--pack DIR] [--data FILE] [--source-root R]
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

PLACE = "challengers_cairn"
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / ("cobblers_%s" % PLACE)
FUNCTION = "data/cobblers/function/%s/build.mcfunction" % PLACE
ROOF_LEAST = 2   # data/challengers_cairn.json passage.why: "roofed while it has two blocks of ground over it"


class Expect:
    """What the record and the heightmap say, computed here."""

    def __init__(self, rec, g):
        self.rec = rec
        self.cx, self.cz = rec["cairn"]["centre"]
        self.R, self.H = rec["cairn"]["radius"], rec["cairn"]["height"]
        c = rec["cist"]
        self.h, self.ch, self.depth = c["half"], c["height"], c["floor_below_ground"]
        self.margin, self.keep = c["margin"], c["keep_natural_top"]
        self.foot = [(x, z) for x in range(self.cx - self.h, self.cx + self.h + 1)
                     for z in range(self.cz - self.h, self.cz + self.h + 1)]
        self.F = min(g(x, z) for x, z in self.foot) - self.depth
        self.room = {(x, y, z) for x, z in self.foot for y in range(self.F + 1, self.F + self.ch + 1)}
        ps = rec["passage"]
        self.d = tuple(ps["direction"])
        # the stair leaves the cist from the cell next to its edge on the centre line, the way the record points it
        self.first = (self.cx + self.d[0] * (self.h + 1), self.cz + self.d[1] * (self.h + 1))
        self.hw, self.ph = ps["half_width"], ps["height"]
        self.stair = [b for b in rec["blocks"]["ids"] if b.endswith("_stairs")]
        self.crown = g(self.cx, self.cz) + self.H


def check_cairn(R, E, W, flight):
    cx, cz = E.cx, E.cz
    cap, lan = (cx, E.crown + 1, cz), (cx, E.crown + 2, cz)
    if not A.column_on_ground(W, cx, cz, E.crown):
        R.err("cairn", "the crown column (%d, %d) is not solid from its ground y%d to the crown y%d (= ground + "
              "cairn.height %d)" % (cx, cz, W.ground(cx, cz), E.crown, E.H))
    if W.b(cap) != "minecraft:chiseled_stone_bricks":
        R.err("cairn", "the capstone %s is %s" % (cap, W.at(cap)))
    if W.b(lan) != "minecraft:lantern" or A.prop(W.at(lan), "hanging") != "false":
        R.err("cairn", "no standing lantern on the capstone at %s: %s" % (lan, W.at(lan)))
    if not W.free((cx, E.crown + 3, cz)):
        R.err("cairn", "something stands over the capstone lantern at y%d" % (E.crown + 3))
    # every column of the mound stands on its own ground, solid to its top. The mound is round and "9 blocks across"
    # (cairn.why) with radius 4: 2R + 1 across, so a column is in it when its centre is within R + 0.5 of the cairn's
    for x in range(cx - E.R, cx + E.R + 1):
        for z in range(cz - E.R, cz + E.R + 1):
            if math.hypot(x - cx, z - cz) > E.R + 0.5:
                continue
            ys = [y for (a, y, b) in W.rep.state if (a, b) == (x, z) and y > W.ground(x, z)]
            if not ys:
                R.err("cairn", "the column (%d, %d), within the cairn's radius %d, holds no stone" % (x, z, E.R))
                return
            if not A.column_on_ground(W, x, z, max(ys)):
                R.err("cairn", "the column (%d, %d) is not solid from its ground y%d to its top y%d (a gap or a "
                      "floating stone)" % (x, z, W.ground(x, z), max(ys)))
                return
    # the ring: a marker at each position the record names, except where the stair's corridor runs
    rg = E.rec["ring"]
    corridor = {c for j in range(0, flight.n + 1) for c in flight.lanes(j)}
    corridor |= {(x + a, z + b) for (x, z) in corridor for a in (-1, 0, 1) for b in (-1, 0, 1)}
    want, left_out = [], []
    for i in range(rg["stones"]):
        a = 2 * math.pi * i / rg["stones"]
        ex, ez = cx + rg["radius"] * math.cos(a), cz + rg["radius"] * math.sin(a)
        # the nearest whole column(s) to the exact point: both, when it is a tie
        cols = {(x, z) for x in (math.floor(ex + 0.5), math.ceil(ex - 0.5)) for z in (math.floor(ez + 0.5),
                                                                                       math.ceil(ez - 0.5))}
        (want if not any(c in corridor for c in cols) else left_out).append(cols)
    stones = set()
    for (x, y, z) in W.rep.state:
        if y > W.ground(x, z) and math.hypot(x - cx, z - cz) > E.R + 0.5 and (x, z) not in corridor:
            stones.add((x, z))
    found = 0
    for cols in want:
        hit = [c for c in cols if c in stones]
        if not hit:
            R.err("cairn", "no ring stone at %s (ring.radius %d)" % (sorted(cols), rg["radius"]))
            continue
        found += 1
        x, z = hit[0]
        top = max(y for (a, y, b) in W.rep.state if (a, b) == (x, z))
        if not (A.column_on_ground(W, x, z, top) and 2 <= top - W.ground(x, z) <= 3):
            R.err("cairn", "the ring stone (%d, %d) is not 2 or 3 high on its own ground" % (x, z))
    extra = stones - {c for cols in want for c in cols}
    if extra:
        R.err("cairn", "blocks stand above the ground off the cairn, the ring and the stair at %s" % sorted(extra)[:4])
    for cols in left_out:
        if any(c in stones for c in cols):
            R.err("cairn", "a ring stone stands in the stair's corridor at %s" % sorted(cols))
    R.note("cairn: crown y%d, capstone y%d, lantern y%d; %d ring stones (%d left out for the stair)"
           % (E.crown, E.crown + 1, E.crown + 2, found, len(left_out)))


def audit(rec, g, pack, steps=None, data=DATA):
    R = A.Report()
    lines, rep = A.load_pack(pack, FUNCTION)
    if rep is None:
        R.err("steps", "no %s in %s: build the pack first" % (FUNCTION, pack))
        return R
    W = A.World(rep, g)
    E = Expect(rec, g)
    A.check_blocks(R, rep, rec, PLACE, data=data)
    if len(E.stair) != 1:
        R.err("stair", "blocks.ids names %d stair blocks; the flight is one" % len(E.stair))
        return R
    barrel = tuple(next(r for r in A.load_json("rewards.json", data)["rewards"]
                        if r["id"] == rec["find"]["reward"])["container"]["at"])

    def declared(k, st):
        return k == barrel and A.base(st) == "minecraft:barrel"
    worst_room = A.check_room(R, W, E.room, E.F, E.depth - E.ch, declared, name="cist")
    flight = A.Flight(W, E.first, E.d, E.F, E.hw, E.ph, E.stair[0])
    flight.check(R)
    flight.check_headroom(R)
    worst_roof = flight.check_roof(R, ROOF_LEAST)
    voids = E.room | flight.voids()
    n_shell = A.check_shell(R, W, voids, E.margin, E.keep)
    check_cairn(R, E, W, flight)
    A.check_find(R, W, rec["find"]["reward"], lambda k: k in E.room, data)
    A.check_attached(R, W)
    A.check_boxes(R, rep, rec)
    A.check_site(R, rep, rec, PLACE, (E.cx, E.cz), data)
    A.check_seen(R, W, (E.cx, E.crown + 2, E.cz), "victory_road", "the capstone lantern", data)
    A.check_steps(R, rep, lines, steps, PLACE)
    roofed = sum(1 for j in range(flight.n + 1) if all(flight.roofed(c, j) for c in flight.lanes(j)))
    R.note("cist: floor y%d (min ground %d - %d), %d cells, least ground over it %d; stair: a landing and %d steps, %d "
           "of the %d roofed (least cover %s), top step y%d; shell %d cells checked"
           % (E.F, E.F + E.depth, E.depth, len(E.room), worst_room, flight.n, roofed, flight.n + 1, worst_roof,
              E.F + flight.n, n_shell))
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
    import challengers_cairn  # the re-application steps are the generator's OUTPUT, checked here, never its geometry
    steps = challengers_cairn.placement_steps(None, g)
    return A.main_report(audit(rec, g, a.pack, steps), "challengers_cairn_audit")


if __name__ == "__main__":
    raise SystemExit(main())
