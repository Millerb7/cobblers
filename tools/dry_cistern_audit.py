#!/usr/bin/env python
"""The Dry Cistern, audited offline: the emitted pack replayed block by block over the natural ground.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). Written by an agent that built none of the place.
This file never imports tools/dry_cistern.py's or tools/wayside_kit.py's geometry: it reads data/dry_cistern.json, the
canonical heightmap (tools/ground.py) and the other data files named below, derives what it expects with its own
arithmetic (tools/wayside_audit.py, which imports no builder), REPLAYS the build function and compares. The only thing
taken from the generator is its output: the pack, and (in main) the re-application steps it hands tools/reapply.py.
tests/test_dry_cistern_audit.py mutates the GENERATOR (the roof rule cut to 1, a ladder missing, the trapdoor open, the
house a block low, the water line on the wrong course) with the record untouched, and each is caught.

The checks, docs/world-building/DRY_CISTERN.md 'What an audit must check', numbered as there:

  blocks    (1) every written block in blocks.ids; no spawn condition (data/spawn_blocks.json) unscoped by
            data/spawn_block_policy.json for dry_cistern; no sand, no red sand, no chest, no bed
  cistern   (2) floor = min ground over the 9 by 7 footprint - floor_below_ground, written solid; every room cell free
            of collision unless the record declares what stands there (its four pillars, the shaft's ladder, the
            cache's barrel) or it is a lantern hung over a standing head; floor_below_ground - height (6) blocks of
            ground over every room cell
  cover     (2) every roofed stair column 2 or more blocks under the ground; every open one open to the sky
  stair     (3) one block a step from the landing next to the room's west edge, each a red sandstone stair facing west,
            the top step level with the ground in every lane, no rise past it
  headroom  (3) passage.height (3) cells free of collision over every step
  shaft     (4) a ladder in every cell from the floor to the one under the trapdoor, each hanging on a solid block east
            of it; a closed trapdoor in the ground's top block; nothing solid in the shaft
  house     (5) floor = max ground under its footprint + 1, written solid, a foundation down to the ground under every
            column; a doorway two cells high in its south wall at door_x
  well      (5) every column of the well-head round the shaft stands on its own ground, solid to its top
  pillars   (6) each pillar solid from the floor to the roof; white terracotta only on the water line, in a wall facing
            the room, and on every such wall cell
  shell     every non-void cell within chamber.margin of a void, under the column's kept top, written solid
  find      (7) the barrel at dry_cistern_store container.at, not at the shaft's foot; the trigger box free cells a
            player can stand in, touching it, inside the room
  attached  (8) every hung block on a solid block written before it
  boxes     (8) every write inside the function's forceload, bbox.forceload and bbox.writes; clears inside bbox.clear
  steps     (8) R9CI holds every written column, runs the build and releases; the function passes function_limits
  site, seen (9) clear of the Rift, Rift regions, towns, other places' boxes, placements and Habitat Blocks; the
            well-head lantern in sight of a standing eye from Route 8

NOT checked, and it needs a running server: that the fills land, that the cache is granted, that a player can climb
out of the shaft past the slab ring and the lantern over its mouth (the shaft is not the way in: the stair is).

  python tools/dry_cistern_audit.py [--pack DIR] [--data FILE] [--source-root R]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wayside_audit as A  # noqa: E402

PLACE = "dry_cistern"
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / ("cobblers_%s" % PLACE)
FUNCTION = "data/cobblers/function/%s/build.mcfunction" % PLACE
ROOF_LEAST = 2   # data/dry_cistern.json passage.why: "roofed while it has two blocks of ground over it"
NEVER_HERE = ("minecraft:sand", "minecraft:red_sand")   # both spawn conditions; the doc names them


class Expect:
    def __init__(self, rec, g):
        self.rec = rec
        c = rec["chamber"]
        self.cx, self.cz = c["centre"]
        self.hx, self.hz, self.ch, self.depth = c["half_x"], c["half_z"], c["height"], c["floor_below_ground"]
        self.margin, self.keep = c["margin"], c["keep_natural_top"]
        self.foot = [(x, z) for x in range(self.cx - self.hx, self.cx + self.hx + 1)
                     for z in range(self.cz - self.hz, self.cz + self.hz + 1)]
        self.F = min(g(x, z) for x, z in self.foot) - self.depth
        self.room = {(x, y, z) for x, z in self.foot for y in range(self.F + 1, self.F + self.ch + 1)}
        self.pillars = {(self.cx + ox, self.cz + oz) for ox, oz in c["pillars"]}
        self.wl = self.F + c["water_line_above_floor"]
        ps = rec["passage"]
        self.d = tuple(ps["direction"])
        half = self.hx if self.d[0] else self.hz
        self.first = (self.cx + self.d[0] * (half + 1), self.cz + self.d[1] * (half + 1))
        self.hw, self.ph = ps["half_width"], ps["height"]
        self.stair = [b for b in rec["blocks"]["ids"] if b.endswith("_stairs")]
        self.sx, self.sz = rec["shaft"]["at"]
        self.gs = g(self.sx, self.sz)
        self.shaft = {(self.sx, y, self.sz) for y in range(self.F + self.ch + 1, self.gs)}
        hs = rec["house"]
        self.hx0, self.hx1 = hs["x"]
        self.hz0, self.hz1 = hs["z"]
        self.door_x = hs["door_x"]
        self.hf = max(g(x, z) for x in range(self.hx0, self.hx1 + 1) for z in range(self.hz0, self.hz1 + 1)) + 1


def check_shaft(R, E, W):
    for y in range(E.F + 1, E.gs):
        k = (E.sx, y, E.sz)
        st = W.at(k)
        if A.base(st) != "minecraft:ladder" or A.prop(st, "facing") != "west":
            R.err("shaft", "%s is %s, not a ladder hung on the block east of it (facing west)" % (k, st))
            return
        if W.free((E.sx + 1, y, E.sz)):
            R.err("shaft", "the ladder at %s has nothing solid east of it" % (k,))
            return
    top = (E.sx, E.gs, E.sz)
    st = W.at(top)
    if not A.base(st).endswith("_trapdoor") or top not in W.rep.state:
        R.err("shaft", "the ground's top block over the shaft %s is %s, not a trapdoor" % (top, st))
    elif A.prop(st, "open") != "false":
        R.err("shaft", "the trapdoor %s is open" % (top,))
    R.note("shaft: ladder y%d..%d at (%d, %d), trapdoor y%d" % (E.F + 1, E.gs - 1, E.sx, E.sz, E.gs))


def check_house(R, E, W):
    for x in range(E.hx0, E.hx1 + 1):
        for z in range(E.hz0, E.hz1 + 1):
            if not A.column_on_ground(W, x, z, E.hf):
                R.err("house", "the house column (%d, %d) is not solid from its ground y%d to the floor y%d (= max "
                      "ground under the house + 1)" % (x, z, W.ground(x, z), E.hf))
                return
    # inside the walls a player stands on the floor: two free cells over it, but for the cauldron the record puts there
    inner = [(x, z) for x in range(E.hx0 + 1, E.hx1) for z in range(E.hz0 + 1, E.hz1)]
    shut = [(x, y, z) for x, z in inner for y in (E.hf + 1, E.hf + 2) if not W.free((x, y, z))
            and not (y == E.hf + 1 and W.b((x, y, z)) == "minecraft:cauldron")]
    if shut:
        R.err("house", "%d cell(s) over the floor y%d inside the walls are not free, e.g. %s %s (a floor seated high?)"
              % (len(shut), E.hf, shut[0], W.at(shut[0])))
    for y in (E.hf + 1, E.hf + 2):
        if not W.free((E.door_x, y, E.hz1)):
            R.err("house", "the south doorway (%d, %d, %d) is %s" % (E.door_x, y, E.hz1, W.at((E.door_x, y, E.hz1))))
    R.note("house: floor y%d (max ground under it + 1)" % E.hf)


def check_well(R, E, W):
    n = 0
    for x in (E.sx - 1, E.sx, E.sx + 1):
        for z in (E.sz - 1, E.sz, E.sz + 1):
            if (x, z) == (E.sx, E.sz):
                continue
            ys = [y for (a, y, b) in W.rep.state if (a, b) == (x, z) and y > W.ground(x, z)]
            if not ys:
                continue
            n += 1
            if not A.column_on_ground(W, x, z, max(ys)):
                R.err("well", "the well-head column (%d, %d) does not stand on its ground y%d, solid to its top y%d"
                      % (x, z, W.ground(x, z), max(ys)))
    if not n:
        R.err("well", "nothing stands round the shaft's mouth")


def check_pillars(R, E, W):
    for x, z in sorted(E.pillars):
        for y in range(E.F, E.F + E.ch + 2):
            if not W.written_solid((x, y, z)):
                R.err("pillars", "the pillar (%d, %d) is %s at y%d: not solid from the floor y%d to the roof y%d"
                      % (x, z, W.at((x, y, z)), y, E.F, E.F + E.ch + 1))
                break
    for k, st in W.rep.state.items():
        if A.base(st) != "minecraft:white_terracotta":
            continue
        faces = any((k[0] + a, k[1] + b, k[2] + c) in E.room for a, b, c in A.SIX)
        if k[1] != E.wl or not faces or k in E.room:
            R.err("pillars", "white terracotta at %s is not in a wall facing the room on the water line y%d" % (k, E.wl))
            return
    missing = []
    for (x, y, z) in E.room:
        if y != E.wl:
            continue
        for a, _b, c in A.SIX:
            k = (x + a, y, z + c)
            if k in E.room or (a, c) == (0, 0):
                continue
            if W.written_solid(k) and W.b(k) != "minecraft:white_terracotta":
                missing.append(k)
    if missing:
        R.err("pillars", "%d wall cell(s) facing the room on the water line y%d are not white terracotta, e.g. %s"
              % (len(missing), E.wl, sorted(missing)[:3]))


def audit(rec, g, pack, steps=None, data=DATA):
    R = A.Report()
    lines, rep = A.load_pack(pack, FUNCTION)
    if rep is None:
        R.err("steps", "no %s in %s: build the pack first" % (FUNCTION, pack))
        return R
    W = A.World(rep, g)
    E = Expect(rec, g)
    A.check_blocks(R, rep, rec, PLACE, extra_never=NEVER_HERE, data=data)
    if len(E.stair) != 1:
        R.err("stair", "blocks.ids names %d stair blocks; the flight is one" % len(E.stair))
        return R
    barrel = tuple(next(r for r in A.load_json("rewards.json", data)["rewards"]
                        if r["id"] == rec["find"]["reward"])["container"]["at"])

    def declared(k, st):
        b = A.base(st)
        return ((k[0], k[2]) in E.pillars and not A.noncolliding(b)) or (k == barrel and b == "minecraft:barrel") \
            or ((k[0], k[2]) == (E.sx, E.sz) and b == "minecraft:ladder")
    worst_room = A.check_room(R, W, E.room, E.F, E.depth - E.ch, declared, name="cistern")
    flight = A.Flight(W, E.first, E.d, E.F, E.hw, E.ph, E.stair[0])
    flight.check(R)
    flight.check_headroom(R)
    worst_roof = flight.check_roof(R, ROOF_LEAST)
    check_shaft(R, E, W)
    check_house(R, E, W)
    check_well(R, E, W)
    check_pillars(R, E, W)
    voids = (E.room - {(x, y, z) for (x, y, z) in E.room if (x, z) in E.pillars}) | flight.voids() | E.shaft
    n_shell = A.check_shell(R, W, voids, E.margin, E.keep)
    if (barrel[0], barrel[2]) == (E.sx, E.sz):
        R.err("find", "the barrel %s stands at the shaft's foot" % (barrel,))
    A.check_find(R, W, rec["find"]["reward"], lambda k: k in E.room, data)
    A.check_attached(R, W)
    A.check_boxes(R, rep, rec)
    A.check_site(R, rep, rec, PLACE, (E.cx, E.cz), data)
    lantern = sorted(k for k, s in rep.state.items() if (k[0], k[2]) == (E.sx, E.sz) and k[1] > E.gs
                     and A.base(s) == "minecraft:lantern")
    if not lantern:
        R.err("seen", "no lantern over the shaft's mouth")
    else:
        A.check_seen(R, W, lantern[-1], "route_08_blaine_to_giovanni", "the well-head lantern", data)
    A.check_steps(R, rep, lines, steps, PLACE)
    roofed = sum(1 for j in range(flight.n + 1) if all(flight.roofed(c, j) for c in flight.lanes(j)))
    R.note("cistern: floor y%d (min ground %d - %d), %d cells, least ground over it %d, water line y%d; stair: a landing "
           "and %d steps, %d of the %d roofed (least cover %s), top step y%d; shell %d cells checked"
           % (E.F, E.F + E.depth, E.depth, len(E.room), worst_room, E.wl, flight.n, roofed, flight.n + 1, worst_roof,
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
    import dry_cistern  # the re-application steps are the generator's OUTPUT, checked here, never its geometry
    steps = dry_cistern.placement_steps(None, g)
    return A.main_report(audit(rec, g, a.pack, steps), "dry_cistern_audit")


if __name__ == "__main__":
    raise SystemExit(main())
