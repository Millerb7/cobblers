#!/usr/bin/env python
"""The audit side of the three southern wayside places of 2026-10-03: what tools/challengers_cairn_audit.py,
tools/dry_cistern_audit.py and tools/survey_benchmark_audit.py share.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). Nothing here imports a builder: not
tools/challengers_cairn.py, tools/dry_cistern.py, tools/survey_benchmark.py, nor their shared tools/wayside_kit.py. It
REPLAYS an emitted build function into a block model laid over the natural ground (tools/ground.py, the canonical
heightmap, rounded: an unwritten cell at or under a column's ground is ground, over it air) and checks properties of the
result against the place's record and other data files. The only thing taken from a builder is its output.

What lives here, each written from the doc's rule and from Minecraft's block shapes, never from the builder's code:

  Replay / World     the function, run: final states, the line each cell was last written by, clears, forceloads
  flight             a stair cut from a chamber up to the ground, found where the RECORD says it starts (the cell next to
                     the chamber's edge on its centre line, at the chamber floor) and checked step by step: one block a
                     step, each a stair facing the way up, three non-colliding blocks over every step, roofed only with
                     two or more blocks of ground over it, the last step level with the ground of every lane
  shell              every non-void cell within `margin` (Chebyshev) of a void and under the column's kept top is
                     WRITTEN solid (an unwritten cell is whatever the export left: gravel, a cave, water)
  blocks / attached / boxes / find / site / seen / steps   as in tools/drovers_hollow_audit.py

The three-blocks-over-a-step rule is not a margin, it is the player: 1.8 blocks tall, climbing a bottom-half stair
half a block at a time. Stepping from step j's back half onto step j+1's front half puts the head at
floor(j) + 3.3 while the body still overlaps step j's column by 0.6, so the third cell over step j must have no
collision box. A wall sign has none; a lantern does (its hanging shape is y 1/16 to 10/16, x and z 5/16 to 11/16).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*?)(?: replace)?$")
FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$")
NATURAL = "natural:ground"
FACING = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
NAME = {v: k for k, v in FACING.items()}
SIX = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
SIGHT_RANGE = 250   # the docs' measure: Victory Road's / Route 8's walked points, every 4th, within 250 blocks
SIGHT_EVERY = 4
# a chest is a Gimmighoul spawn condition (tools/portals_audit.py); a bed sets a respawn point, which the blackout owns
NEVER = ("minecraft:chest", "minecraft:trapped_chest")


def base(state):
    return state.split("[")[0].split("{")[0]


def prop(state, key):
    m = re.search(r"[\[,]%s=([a-z_0-9]+)" % key, state.split("{")[0])
    return m.group(1) if m else None


def load_json(name, root=DATA):
    return json.loads((Path(root) / name).read_text(encoding="utf-8"))


def noncolliding(b):
    """Blocks with no collision box: a body passes through them."""
    return b in ("minecraft:air", "minecraft:cave_air") or b.endswith("_wall_sign")


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, check, msg):
        self.errors.append("%s: %s" % (check, msg))

    def note(self, msg):
        self.notes.append(msg)

    def checks(self):
        return sorted({e.split(":", 1)[0] for e in self.errors})


class Replay:
    """The build function, run: final states, the line each cell was last written by, clears and forceloads."""

    def __init__(self, lines):
        self.state, self.when, self.clears, self.loads, self.bad = {}, {}, [], [], []
        for i, raw in enumerate(lines):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = FORCELOAD.match(line)
            if m:
                if m.group(1) == "add":
                    self.loads.append(tuple(int(v) for v in m.groups()[1:]))
                continue
            m = FILL.match(line)
            if m and m.group(8):
                self.clears.append((m.group(8), [int(v) for v in m.groups()[:6]], base(m.group(7))))
                continue
            if m:
                x0, y0, z0, x1, y1, z1 = (int(v) for v in m.groups()[:6])
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    for y in range(min(y0, y1), max(y0, y1) + 1):
                        for z in range(min(z0, z1), max(z0, z1) + 1):
                            self.state[(x, y, z)] = m.group(7)
                            self.when[(x, y, z)] = i
                continue
            m = SETBLOCK.match(line)
            if m:
                k = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                self.state[k] = m.group(4)
                self.when[k] = i
                continue
            self.bad.append(line)


class World:
    """The replay over the natural ground."""

    def __init__(self, rep, g):
        self.rep, self.g, self._gc = rep, g, {}

    def ground(self, x, z):
        if (x, z) not in self._gc:
            self._gc[(x, z)] = int(self.g(x, z))
        return self._gc[(x, z)]

    def at(self, k):
        s = self.rep.state.get(k)
        if s is not None:
            return s
        return NATURAL if k[1] <= self.ground(k[0], k[2]) else "minecraft:air"

    def b(self, k):
        return base(self.at(k))

    def free(self, k):
        return noncolliding(self.b(k))

    def written_solid(self, k):
        return k in self.rep.state and not noncolliding(base(self.rep.state[k]))


def load_pack(pack, function):
    fn = Path(pack) / function
    if not fn.exists():
        return None, None
    lines = fn.read_text(encoding="utf-8").splitlines()
    return lines, Replay(lines)


# ------------------------------------------------------------------------------------------------- the flight of steps
class Flight:
    """A stair from a chamber's floor `F` up to the ground, laid along `d` from the landing column `first`, `hw` lanes
    either side of the centre line, `height` blocks of passage over each step. Found in the replay at the positions the
    record implies; nothing is taken from the builder."""

    def __init__(self, W, first, d, F, hw, height, stair_id):
        self.W, self.first, self.d, self.F, self.hw, self.h, self.stair = W, first, d, F, hw, height, stair_id
        self.facing = NAME[d]
        self.n = 0
        while True:
            j = self.n + 1
            if not any(self._is_step(c, F + j) for c in self.lanes(j)) or j > 128:
                break
            self.n = j

    def lanes(self, j):
        (fx, fz), (dx, dz) = self.first, self.d
        px, pz = -dz, dx
        return [(fx + dx * j + px * k, fz + dz * j + pz * k) for k in range(-self.hw, self.hw + 1)]

    def _is_step(self, c, y):
        st = self.W.at((c[0], y, c[1]))
        return base(st) == self.stair and prop(st, "facing") == self.facing and prop(st, "half") == "bottom"

    def roofed(self, c, j):
        """A lane column is roofed when the cell over its passage is solid and under the ground."""
        y = self.F + j + self.h + 1
        return y <= self.W.ground(*c) and not self.W.free((c[0], y, c[1]))

    def voids(self):
        """The cells the flight cuts out of the ground: a roofed column's passage, an open column's cut up to the
        ground (the air over the ground is the sky's, not a void a shell must close)."""
        out = set()
        for j in range(0, self.n + 1):
            for c in self.lanes(j):
                top = self.F + j + self.h if self.roofed(c, j) else self.W.ground(*c)
                for y in range(self.F + j + 1, top + 1):
                    out.add((c[0], y, c[1]))
        return out

    def check(self, R, name="stair"):
        Wd = self.W
        if self.n == 0:
            R.err(name, "no step: no %s facing %s at %s y%d (the landing's next column, one block up)"
                  % (self.stair, self.facing, self.lanes(1), self.F + 1))
            return
        for c in self.lanes(0):
            if Wd.free((c[0], self.F, c[1])) or (c[0], self.F, c[1]) not in Wd.rep.state:
                R.err(name, "the landing's floor (%d, %d, %d) is not written solid" % (c[0], self.F, c[1]))
        for j in range(1, self.n + 1):
            for c in self.lanes(j):
                if not self._is_step(c, self.F + j):
                    R.err(name, "step %d is not a bottom %s facing %s at (%d, %d, %d) (one block a step from the "
                          "floor y%d): %s" % (j, self.stair, self.facing, c[0], self.F + j, c[1], self.F,
                                              Wd.at((c[0], self.F + j, c[1]))))
        # the place's stair blocks are the flight's and nothing else's: a step moved up or down shows here
        flight = {(c[0], self.F + j, c[1]) for j in range(1, self.n + 1) for c in self.lanes(j)}
        stray = sorted(k for k, s in Wd.rep.state.items() if base(s) == self.stair and k not in flight)
        if stray:
            R.err(name, "%d %s block(s) are off the one-block-a-step flight from the floor y%d, e.g. %s"
                  % (len(stray), self.stair, self.F, stray[:3]))
        last = self.F + self.n
        for c in self.lanes(self.n):
            g = Wd.ground(*c)
            if last != g:
                R.err(name, "the top step y%d at (%d, %d) is not level with the ground y%d: a %s at the head"
                      % (last, c[0], c[1], g, "one-block jump" if g > last else "step standing above the ground"))
        for c in self.lanes(self.n + 1):
            g = Wd.ground(*c)
            if g > last:
                R.err(name, "past the top step the ground at (%d, %d) is y%d, over the top step y%d: a jump out"
                      % (c[0], c[1], g, last))

    def check_headroom(self, R, name="headroom"):
        Wd = self.W
        for j in range(0, self.n + 1):
            for c in self.lanes(j):
                for y in range(self.F + j + 1, self.F + j + self.h + 1):
                    if not Wd.free((c[0], y, c[1])):
                        R.err(name, "over step %d at (%d, %d) the cell y%d is %s, not free of collision: a player "
                              "climbing needs %d free cells over every step" % (j, c[0], c[1], y,
                                                                                Wd.at((c[0], y, c[1])), self.h))

    def check_roof(self, R, least, name="cover"):
        Wd = self.W
        worst = None
        for j in range(0, self.n + 1):
            for c in self.lanes(j):
                if self.roofed(c, j):
                    cv = Wd.ground(*c) - (self.F + j + self.h)
                    worst = cv if worst is None else min(worst, cv)
                    if cv < least:
                        R.err(name, "step %d at (%d, %d) is roofed with %d block(s) of ground over its passage; the "
                              "record roofs a step only with %d or more" % (j, c[0], c[1], cv, least))
                else:
                    for y in range(self.F + j + 1, max(Wd.ground(*c), self.F + j + self.h) + 1):
                        if not Wd.free((c[0], y, c[1])):
                            R.err(name, "step %d at (%d, %d) is neither roofed nor open: %s at y%d"
                                  % (j, c[0], c[1], Wd.at((c[0], y, c[1])), y))
                            break
        return worst


# ---------------------------------------------------------------------------------------------------- shared checks
def check_room(R, W, room, F, least_cover, allow, name="room"):
    """A chamber the record declares open: its floor layer F written solid; every cell of it free of collision unless
    `allow(k, state)` names it (what the record declares stands there) or it is a lantern hanging in the third cell or
    higher over the floor, over a standing player's head (feet F + 1, head F + 2.8; the lantern's shape starts 1/16 up
    its cell); every cell with `least_cover` or more blocks of ground over it."""
    for (x, _y, z) in {(k[0], 0, k[2]) for k in room}:
        if not W.written_solid((x, F, z)):
            R.err(name, "the floor (%d, %d, %d) is %s, not written solid" % (x, F, z, W.at((x, F, z))))
            break
    shut = []
    for k in sorted(room):
        st = W.at(k)
        if noncolliding(base(st)) or allow(k, st):
            continue
        if base(st) == "minecraft:lantern" and prop(st, "hanging") == "true" and k[1] >= F + 3:
            continue
        shut.append((k, base(st)))
    if shut:
        R.err(name, "%d cell(s) the record declares open hold a block it does not declare: %s"
              % (len(shut), ", ".join("%s %s" % s for s in shut[:6])))
    worst = min(W.ground(x, z) - y for (x, y, z) in room)
    if worst < least_cover:
        low = [k for k in room if W.ground(k[0], k[2]) - k[1] == worst]
        R.err(name, "a void %s has %d block(s) of ground over it; the record's depth leaves %d" % (low[0], worst,
                                                                                                   least_cover))
    return worst


def check_shell(R, W, voids, margin, keep, name="shell"):
    """Every non-void cell within `margin` (Chebyshev) of a void, at or under its column's ground less `keep`, was
    WRITTEN solid."""
    n = 0
    seen = set()
    for (x, y, z) in voids:
        for dx in range(-margin, margin + 1):
            for dz in range(-margin, margin + 1):
                cx, cz = x + dx, z + dz
                top = W.ground(cx, cz) - keep
                for dy in range(-margin, margin + 1):
                    k = (cx, y + dy, cz)
                    if k in voids or k in seen or k[1] > top:
                        continue
                    seen.add(k)
                    if not W.written_solid(k):
                        R.err(name, "%s is within %d of the void %s and is %s, not written solid"
                              % (k, margin, (x, y, z), W.at(k)))
                        return n
                    n += 1
    return n


def check_blocks(R, rep, rec, place, extra_never=(), data=DATA):
    ids = set(rec["blocks"]["ids"])
    placed = {base(s) for s in rep.state.values()} | {c[2] for c in rep.clears}
    bad = sorted(placed - ids)
    if bad:
        R.err("blocks", "written but not in blocks.ids: %s" % bad)
    sb = set(load_json("spawn_blocks.json", data)["blocks"])
    pol = load_json("spawn_block_policy.json", data)
    allowed = {b for w in pol.get("whitelist") or [] if place in (w.get("scope") or "") for b in w["blocks"]}
    cond = sorted((placed & sb) - allowed)
    if cond:
        R.err("blocks", "spawn conditions written (data/spawn_blocks.json), no policy entry scoped to %s: %s"
              % (place, cond))
    never = sorted(b for b in placed if b in NEVER or b.endswith("_bed") or b in extra_never)
    if never:
        R.err("blocks", "written and never allowed here: %s" % never)


def support_of(k, st):
    """The cell a hung block hangs on, by Minecraft's rules for the block's own state."""
    b = base(st)
    x, y, z = k
    if b == "minecraft:ladder" or b.endswith("_wall_sign"):
        dx, dz = FACING[prop(st, "facing")]
        return (x - dx, y, z - dz)
    if b == "minecraft:lantern":
        return (x, y + 1, z) if prop(st, "hanging") == "true" else (x, y - 1, z)
    if b == "minecraft:chain":
        return (x, y + 1, z)
    return None


def check_attached(R, W):
    for k, st in W.rep.state.items():
        s = support_of(k, st)
        if s is None:
            continue
        b = base(st)
        sb = W.b(s)
        on_chain = b in ("minecraft:chain", "minecraft:lantern") and s[1] == k[1] + 1 and sb == "minecraft:chain"
        if not on_chain and noncolliding(sb):
            R.err("attached", "%s at %s hangs on %s at %s" % (b, k, W.at(s), s))
            continue
        if s in W.rep.when and W.rep.when[s] > W.rep.when[k]:
            R.err("attached", "%s at %s is written (line %d) before what holds it, %s (line %d)"
                  % (b, k, W.rep.when[k] + 1, s, W.rep.when[s] + 1))


def _inside(box, x, z):
    return min(box[0], box[2]) <= x <= max(box[0], box[2]) and min(box[1], box[3]) <= z <= max(box[1], box[3])


def check_boxes(R, rep, rec):
    """Every write inside the function's own forceload, the record's bbox.forceload and bbox.writes; every clear inside
    bbox.clear and the forceload."""
    bb = rec["bbox"]
    wr, cl, fl = bb["writes"], bb["clear"], bb["forceload"]
    if not rep.loads:
        R.err("boxes", "the function force-loads nothing")
    out_fn = out_fl = out_wr = None
    for (x, y, z) in rep.state:
        if out_fn is None and not any(_inside(b, x, z) for b in rep.loads):
            out_fn = (x, y, z)
        if out_fl is None and not _inside(fl, x, z):
            out_fl = (x, y, z)
        if out_wr is None and not (wr["x"][0] <= x <= wr["x"][1] and wr["z"][0] <= z <= wr["z"][1]
                                   and wr["y"][0] <= y <= wr["y"][1]):
            out_wr = (x, y, z)
    for what, k in (("the function's own forceload", out_fn), ("bbox.forceload %s" % (fl,), out_fl),
                    ("bbox.writes", out_wr)):
        if k is not None:
            R.err("boxes", "%s is written outside %s" % (k, what))
    for tag, (x0, y0, z0, x1, y1, z1), _b in rep.clears:
        if not (cl["x"][0] <= min(x0, x1) and max(x0, x1) <= cl["x"][1] and cl["z"][0] <= min(z0, z1)
                and max(z0, z1) <= cl["z"][1] and cl["y"][0] <= min(y0, y1) and max(y0, y1) <= cl["y"][1]):
            R.err("boxes", "the clear of %s %s reaches outside bbox.clear" % (tag, (x0, y0, z0, x1, y1, z1)))
        for cx, cz in ((x0, z0), (x1, z1)):
            if not _inside(fl, cx, cz) or not any(_inside(b, cx, cz) for b in rep.loads):
                R.err("boxes", "the clear of %s reaches (%d, %d), outside the forceload" % (tag, cx, cz))


def check_steps(R, rep, lines, steps, fn):
    import function_limits
    bad = function_limits.check_lines(lines, "build")
    if bad:
        R.err("steps", "%d command(s) the server would refuse: %s" % (len(bad), bad[:2]))
    if rep.bad:
        R.err("steps", "%d line(s) this audit cannot read: %s" % (len(rep.bad), rep.bad[:2]))
    if steps is None:
        return
    steps = [tuple(s) for s in steps]
    if ("fn", "cobblers:%s/build" % fn) not in steps:
        R.err("steps", "the re-application does not run cobblers:%s/build" % fn)
    holds = [tuple(int(v) for v in s[1].split()[2:]) for s in steps if s[0] == "cmd" and s[1].startswith("forceload add")]
    if not holds or steps[-1][0] != "cmd" or not steps[-1][1].startswith("forceload remove"):
        R.err("steps", "the re-application does not hold the chunks round the build and release them after")
        return
    for (x, y, z) in rep.state:
        if not any(_inside(h, x, z) for h in holds):
            R.err("steps", "(%d, %d, %d) is written outside the re-application's forceload %s" % (x, y, z, holds))
            return


def standable(W, k):
    """A player's feet fit at k: k and the cell over it are free, the cell under it is solid."""
    x, y, z = k
    return W.free(k) and W.free((x, y + 1, z)) and not W.free((x, y - 1, z))


def check_find(R, W, reward_id, inside, data=DATA):
    """data/rewards.json's cache: its barrel is written where the record says, its trigger box is free cells, holds a
    place a player can stand, touches the barrel, and lies inside `inside` (a predicate on cells)."""
    rw = [r for r in load_json("rewards.json", data)["rewards"] if r["id"] == reward_id]
    if not rw:
        R.err("find", "no reward %s in data/rewards.json" % reward_id)
        return None
    r = rw[0]
    if r.get("kind") != "cache":
        R.err("find", "%s is not a cache" % reward_id)
    at = tuple(r["container"]["at"])
    if W.b(at) != "minecraft:barrel" or at not in W.rep.state:
        R.err("find", "data/rewards.json puts the barrel at %s; the pack writes %s there" % (at, W.at(at)))
    t = r["trigger"]
    box = [(x, y, z) for x in range(t["min"][0], t["max"][0] + 1) for y in range(t["min"][1], t["max"][1] + 1)
           for z in range(t["min"][2], t["max"][2] + 1)]
    shut = [k for k in box if not W.free(k)]
    if shut:
        R.err("find", "the trigger box holds %d cell(s) a body cannot enter, e.g. %s %s" % (len(shut), shut[0],
                                                                                             W.at(shut[0])))
    if not any(standable(W, k) for k in box):
        R.err("find", "no cell of the trigger box %s-%s is a place a player can stand" % (t["min"], t["max"]))
    if not any(math.dist(k, at) == 1 for k in box):
        R.err("find", "the trigger box %s-%s does not touch the barrel %s" % (t["min"], t["max"], at))
    out = [k for k in box if not inside(k)]
    if out:
        R.err("find", "the trigger box reaches %s, outside the place it should be in" % (out[0],))
    return at


# ------------------------------------------------------------------------------------------------- site and sight
def _poly_inside(poly, x, z):
    c = False
    for (ax, az), (bx, bz) in zip(poly, poly[1:] + poly[:1]):
        if (az > z) != (bz > z) and x < (bx - ax) * (z - az) / float(bz - az) + ax:
            c = not c
    return c


def _poly_dist(poly, x, z):
    best = 1e18
    for (ax, az), (bx, bz) in zip(poly, poly[1:] + poly[:1]):
        dx, dz = bx - ax, bz - az
        L = dx * dx + dz * dz
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L))
        best = min(best, math.hypot(x - ax - t * dx, z - az - t * dz))
    return best


def box_dist(box, x, z):
    return math.hypot(max(box[0] - x, 0, x - box[2]), max(box[1] - z, 0, z - box[3]))


def _overlap(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def write_box(rep):
    xs = [k[0] for k in rep.state]
    zs = [k[2] for k in rep.state]
    return (min(xs), min(zs), max(xs), max(zs))


def check_site(R, rep, rec, place, centre, data=DATA):
    """The write box is clear of the Rift (by the rim sculpt's reach), every traced Rift region, every town, every other
    place's bbox.writes, every placement and every Habitat Block's reach; the centre is in the sub-region the record
    names."""
    if not rep.state:
        R.err("site", "the pack writes nothing")
        return
    box = write_box(rep)
    regions = load_json("regions.json", data)
    rift = [r for r in regions["regions"] if r["id"] == "the_rift"][0]["polygons"][0]
    reach = load_json("rift_sculpt.json", data)["rim"]["reach"]
    corners = [(box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])]
    d_rift = min(min(_poly_dist(rift, x, z) for x, z in corners), min(box_dist(box, x, z) for x, z in rift))
    if any(_poly_inside(rift, x, z) for x, z in corners) or d_rift < reach:
        R.err("site", "the write box %s is inside the Rift or within the rim sculpt's reach (%d) of it" % (box, reach))
    for rid, r in load_json("rift_regions.json", data)["regions"].items():
        b = r["bbox"]
        if _overlap(box, (b[0], b[1], b[2], b[3])):
            R.err("site", "the write box overlaps the traced Rift region %s" % rid)
    for t in load_json("towns.json", data)["towns"]:
        fp = t.get("footprint") or {}
        if all(k in fp for k in ("min_x", "min_z", "max_x", "max_z")):
            if _overlap(box, (fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"])):
                R.err("site", "the write box overlaps the town %s" % t.get("id"))
    for f in sorted(Path(data).glob("*.json")):
        if f.stem == place:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        w = (d.get("bbox") or {}).get("writes") if isinstance(d, dict) and isinstance(d.get("bbox"), dict) else None
        if isinstance(w, dict) and "x" in w and "z" in w:
            if _overlap(box, (w["x"][0], w["z"][0], w["x"][1], w["z"][1])):
                R.err("site", "the write box overlaps %s's bbox.writes" % f.name)
    near_p = 1e18
    for p in load_json("placements.json", data)["placements"]:
        pos = p.get("position") or {}
        if isinstance(pos, dict) and "x" in pos and "z" in pos:
            d = box_dist(box, pos["x"], pos["z"])
            near_p = min(near_p, d)
            if d == 0:
                R.err("site", "the placement %s stands inside the write box" % p.get("id"))
    near_h = 1e18
    for hb in load_json("habitat_blocks.json", data)["blocks"]:
        pos = hb.get("position") or {}
        if "x" not in pos:
            continue
        r = max(int(hb.get("range_of_influence") or 0), int((hb.get("activated") or {}).get("spawn_range") or 0))
        d = box_dist(box, pos["x"], pos["z"])
        near_h = min(near_h, d)
        if _overlap(box, (pos["x"] - r, pos["z"] - r, pos["x"] + r, pos["z"] + r)):
            R.err("site", "the Habitat Block %s reaches the write box (range %d)" % (hb["id"], r))
    sub = [s for s in regions["subregions"] if s["id"] == rec["site"]["subregion"]]
    if not sub or not any(_poly_inside(pg, centre[0], centre[1]) for pg in sub[0]["polygons"]):
        R.err("site", "the centre %s is not in the sub-region %s" % (centre, rec["site"]["subregion"]))
    R.note("site: write box x%d..%d z%d..%d; %.0f from the Rift polygon; nearest placement %.0f, nearest Habitat Block "
           "%.0f" % (box[0], box[2], box[1], box[3], d_rift, near_p, near_h))


def sightline(g, frm, to, eye=1.62):
    """The least clearance over the heightmap of the line from a standing eye at `frm` to the middle of the block `to`."""
    fx, fz = frm
    ey = g(fx, fz) + 1 + eye
    tx, ty, tz = to
    n = max(2, int(math.hypot(tx - fx, tz - fz) * 2))
    worst = 1e9
    for i in range(1, n):
        t = i / float(n)
        x, z = fx + (tx - fx) * t, fz + (tz - fz) * t
        worst = min(worst, ey + (ty + 0.5 - ey) * t - (g(int(math.floor(x)), int(math.floor(z))) + 1))
    return worst


def check_seen(R, W, target, path_id, what, data=DATA):
    path = load_json("route_paths.json", data)["paths"][path_id]
    n = sum(1 for x, z in path[::SIGHT_EVERY]
            if math.hypot(x - target[0], z - target[2]) <= SIGHT_RANGE and sightline(W.ground, (x, z), target) > 0)
    near = min(box_dist(write_box(W.rep), x, z) for x, z in path)
    if not n:
        R.err("seen", "%s %s is in sight from no point of %s within %d blocks" % (what, target, path_id, SIGHT_RANGE))
    R.note("seen: %s %s in clear sight from %d of %s's points (every %dth within %d); the write box is %.0f blocks "
           "from its nearest walked point" % (what, target, n, path_id, SIGHT_EVERY, SIGHT_RANGE, near))
    return n


def column_on_ground(W, x, z, y_top):
    """True when (x, z) is solid from its own ground + 1 up to y_top: no gap, nothing floating."""
    return all(W.written_solid((x, y, z)) for y in range(W.ground(x, z) + 1, y_top + 1))


def main_report(R, name):
    for n in R.notes:
        print("  " + n)
    for e in R.errors:
        print("PROBLEM " + e)
    print("%s: %d problem(s)" % (name, len(R.errors)))
    return 1 if R.errors else 0
