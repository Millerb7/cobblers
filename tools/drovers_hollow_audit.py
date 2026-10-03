#!/usr/bin/env python
"""The Drovers' Hollow, audited offline: the emitted pack replayed block by block against the plan, re-derived.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/drovers_hollow.py's
geometry. It reads data/drovers_hollow.json, the canonical heightmap (tools/ground.py) and the other data files named
below, derives what it expects from them with its own arithmetic, then REPLAYS the generated build function into a block
model and compares. The only things taken from the generator are its outputs: the pack, and the re-application steps it
hands tools/reapply.py. Mutating the generator (a thinner shell, a taller drift, a missing trapdoor, a barn seated a
block high, signs written before their walls, a fold with a gap) fails a named check here with data/drovers_hollow.json
untouched; tests/test_drovers_hollow.py does exactly that.

What is checked, each from the data and the heightmap, never from the pack:

  site       the place's whole write box lies outside the Rift's polygon (and 45 blocks clear of it, the rim sculpt's
             reach), the gulch's zone, the Mega dens' approach boxes, every traced Rift region, every town box, and
             more than 60 blocks from Route 8's and Victory Road's walked paths, and nothing is written within 100
             blocks of a resident's anchor (data/resident_encounters.json); the fold's Habitat Block is in the
             sub-region the record names (data/regions.json)
  footprint  above the ground nothing is written outside the barn, its roof, its ramps and posts, the fold and the lane;
             under it nothing outside the working's shell, the fold's top layer and the paths
  seat       the barn floor is max(ground under the walls) + 1 and solid wall to wall; nothing but the well is open
             between the ground and the floor
  working    every void block the record describes (drift, store, well) is open; every block within `margin` of one, at
             or under its column's ground less keep_natural_top, was WRITTEN solid (the shell, filled first); every void
             block outside the barn's footprint has margin + 1 blocks of ground over it; with the trapdoor CLOSED a
             flood from the store never reaches open air or the barn (sealed)
  walk       a player on the ground outside reaches the barn floor, the loft, and with the trapdoor OPEN the store's
             trigger box; with it closed, not the store
  fold       the fold's floor is closed by its fence and gate: a walk on the floor from its middle never leaves the pen
  habitat    the record's Habitat Block: activated, the pool the record names, at the fold floor's centre in the ground's
             top block, its mimic the block the pack writes there; its spawn box holds standing places for max_spawns and
             none outside the pen; its cancel sphere reaches no standing place on the barn floor. The pool is the
             record's species, in the band of the sub-region, under its tier's cap
  blocks     every written block is in blocks.ids; none is a spawn condition (data/spawn_blocks.json) unless a policy
             entry scoped to drovers_hollow allows it; no chest and no bed
  attached   every sign, ladder, lantern and chain is written after what holds it up, and what holds it up is solid
  light      every place a player stands in the barn and the working is within 12 blocks (Manhattan) of a lantern
  find       data/rewards.json's cache: its barrel is where the store's east end is, written by this pack; its trigger
             box is inside the store
  drover     his conversation, quest and cursor field agree; he stands on a written path, two blocks of air
  seen       the barn's ridge, derived here, is in clear sight of a standing eye from Route 8's walked path
  steps      the re-application holds every written chunk, runs the build, releases; the function passes
             tools/function_limits.py

NOT checked, and it needs a running server: that the fills land, that the herd spawns and stays penned, that the
reward is granted, that the drover talks. Light is counted by distance, not by Minecraft's light engine.

  python tools/drovers_hollow_audit.py [--pack build/datapacks/cobblers_drovers_hollow] [--source-root R]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_drovers_hollow"
FUNCTION = "data/cobblers/function/drovers_hollow/build.mcfunction"
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*?)(?: replace)?$")
FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$")
# what a body passes through; a closed trapdoor is its own case
PASSABLE = {"minecraft:air", "minecraft:ladder", "minecraft:lantern", "minecraft:chain", "minecraft:spruce_wall_sign"}
NOT_A_FLOOR = {"minecraft:spruce_fence", "minecraft:spruce_fence_gate", "minecraft:ladder"}
TRAPDOOR = "minecraft:spruce_trapdoor"
HUNG = {"minecraft:ladder", "minecraft:lantern", "minecraft:chain", "minecraft:spruce_wall_sign"}
FACING = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0)}
H4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
ROUTE_CLEAR = 60          # the place is off the path: no write within this many blocks of a walked route point
RESIDENT_CLEAR = 100      # the brief's rule is 4; the place keeps far clearer of every resident than that
RIFT_CLEAR = 45           # the rim sculpt's reach (data/rift_sculpt.json rim.reach 30) and a margin past it
LIGHT_REACH = 12
SIGHT_RANGE = 250


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, check, msg):
        self.errors.append("%s: %s" % (check, msg))

    def note(self, msg):
        self.notes.append(msg)


def base(state):
    return state.split("[")[0].split("{")[0]


def prop(state, key):
    m = re.search(r"[\[,]%s=([a-z_0-9]+)" % key, state.split("{")[0])
    return m.group(1) if m else None


def load_json(name, root=DATA):
    return json.loads((root / name).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------------- the replay
class Replay:
    """The build function, run: final states, the order each cell was last written in, clears and forceloads."""

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
    """The replay over the natural ground: an unwritten cell is ground at or under the heightmap, air over it."""

    def __init__(self, rep, g):
        self.rep, self.g = rep, g
        self._gc = {}

    def ground(self, x, z):
        if (x, z) not in self._gc:
            self._gc[(x, z)] = self.g(x, z)
        return self._gc[(x, z)]

    def at(self, k):
        s = self.rep.state.get(k)
        if s is not None:
            return s
        return "natural:ground" if k[1] <= self.ground(k[0], k[2]) else "minecraft:air"

    def passable(self, k, trapdoor_open=False):
        b = base(self.at(k))
        if b in PASSABLE:
            return True
        return trapdoor_open and b == TRAPDOOR

    def floor(self, k, trapdoor_open=False):
        """Can a body stand on the cell k (it is solid and a full enough top)?"""
        b = base(self.at(k))
        return not self.passable(k, trapdoor_open) and b not in NOT_A_FLOOR

    def supported(self, f, trapdoor_open=False):
        return (base(self.at(f)) == "minecraft:ladder" or self.floor((f[0], f[1] - 1, f[2]), trapdoor_open))


def walk(world, start, inside, trapdoor_open=False):
    """Every feet cell a player can reach from `start`: walking, a one-block step or jump with headroom, falling, and
    climbing ladders."""
    W = world
    op = {"trapdoor_open": trapdoor_open}

    def clear(f):
        return W.passable(f, **op) and W.passable((f[0], f[1] + 1, f[2]), **op)

    seen, todo = {start}, deque([start])
    while todo:
        x, y, z = todo.popleft()
        cands = []
        for dx, dz in H4:
            n = (x + dx, y, z + dz)
            if inside(n) and clear(n):
                k = n
                for _ in range(40):
                    if W.supported(k, **op):
                        break
                    down = (k[0], k[1] - 1, k[2])
                    if not W.passable(down, **op):
                        break
                    k = down
                if W.supported(k, **op):
                    cands.append(k)
            up = (x + dx, y + 1, z + dz)
            if inside(up) and clear(up) and W.passable((x, y + 2, z), **op) and W.supported(up, **op):
                cands.append(up)
        on_ladder = base(W.at((x, y, z))) == "minecraft:ladder"
        if on_ladder or base(W.at((x, y - 1, z))) == "minecraft:ladder":
            # a body climbing still holds the rung under its feet for one block over the ladder's top
            for dy in (1, -1):
                n = (x, y + dy, z)
                if inside(n) and clear(n):
                    cands.append(n)
        if not on_ladder:
            down = (x, y - 1, z)
            if inside(down) and base(W.at(down)) == "minecraft:ladder":
                cands.append(down)
            if inside(down) and W.passable(down, **op) and not W.supported((x, y, z), **op):
                cands.append(down)
        for k in cands:
            if k not in seen:
                seen.add(k)
                todo.append(k)
    return seen


def flood(world, start, inside, trapdoor_open=False):
    seen, todo = {start}, deque([start])
    while todo:
        x, y, z = todo.popleft()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            k = (x + dx, y + dy, z + dz)
            if k in seen or not inside(k) or not world.passable(k, trapdoor_open):
                continue
            seen.add(k)
            todo.append(k)
    return seen


# --------------------------------------------------------------------------------------------- the expectations
class Expect:
    """What the record and the heightmap say, computed here."""

    def __init__(self, rec, g):
        self.rec, self.g = rec, g
        b = rec["barn"]
        self.x0, self.x1 = b["x"]
        self.z0, self.z1 = b["z"]
        self.zc = (self.z0 + self.z1) // 2
        self.bf = max(g(x, z) for x in range(self.x0, self.x1 + 1) for z in range(self.z0, self.z1 + 1)) + 1
        self.loft_y = self.bf + b["loft"]["above_floor"]
        self.over = b["roof_overhang"]
        self.ridge = self.bf + b["wall_height"] + 1 + (self.zc - self.z0) + self.over
        w = rec["working"]
        self.m, self.keep = int(w["margin"]), int(w["keep_natural_top"])
        self.wf = self.bf - w["floor_below_barn_floor"]
        self.voids = set()
        for part in (w["tunnel"], w["chamber"]):
            for x in range(part["x"][0], part["x"][1] + 1):
                for z in range(part["z"][0], part["z"][1] + 1):
                    for y in range(self.wf + 1, self.wf + 1 + part["height"]):
                        self.voids.add((x, y, z))
        self.wx, self.wz = rec["well"]["at"]
        self.well = [(self.wx, y, self.wz) for y in range(self.wf + 1, self.bf)]
        self.voids |= set(self.well)
        c = w["chamber"]
        self.store = c
        self.barrel = (c["x"][1], self.wf + 1, (c["z"][0] + c["z"][1]) // 2)
        f = rec["fold"]
        self.fx0, self.fx1 = f["x"]
        self.fz0, self.fz1 = f["z"]
        self.fold_centre = ((self.fx0 + self.fx1) // 2, (self.fz0 + self.fz1) // 2)
        self.npc = tuple(rec["npc"]["at_xz"])
        xs = [v[0] for v in self.voids]
        zs = [v[2] for v in self.voids]
        self.work_box = (min(xs) - self.m, min(zs) - self.m, max(xs) + self.m, max(zs) + self.m)
        # above the ground: the barn and its roof's overhang, the ramps and posts west of the cattle doorway (as far
        # out as the floor stands over the ground, plus the posts), the lane, the fold
        drop = self.bf - min(g(x, z) for x in range(self.x0 - 12, self.x0) for z in range(self.z0, self.z1 + 1))
        self.above_box = (self.x0 - max(drop + 1, 3), self.z0 - self.over, self.x1 + self.over, self.fz1)

    def in_barn(self, x, z):
        return self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1

    def in_box(self, box, x, z):
        return box[0] <= x <= box[2] and box[1] <= z <= box[3]


# --------------------------------------------------------------------------------------------- the checks
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


def _box_dist(box, x, z):
    return math.hypot(max(box[0] - x, 0, x - box[2]), max(box[1] - z, 0, z - box[3]))


def check_site(R, E, rep, data):
    cols = {(x, z) for (x, _y, z) in rep.state}
    if not cols:
        R.err("site", "the pack writes nothing")
        return
    box = (min(c[0] for c in cols), min(c[1] for c in cols), max(c[0] for c in cols), max(c[1] for c in cols))
    corners = [(box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])]
    regions = load_json("regions.json", data)
    rift = [r for r in regions["regions"] if r["id"] == "the_rift"][0]["polygons"][0]
    for x, z in corners:
        if _poly_inside(rift, x, z) or _poly_dist(rift, x, z) < RIFT_CLEAR:
            R.err("site", "(%d, %d) is inside the Rift or within %d of its polygon" % (x, z, RIFT_CLEAR))
    gulch = load_json("gulch_mine.json", data)
    gp = [tuple(p) for p in gulch["zone"]["polygon"]]
    gb = (min(p[0] for p in gp), min(p[1] for p in gp), max(p[0] for p in gp), max(p[1] for p in gp))
    if not (box[2] < gb[0] or box[0] > gb[2] or box[3] < gb[1] or box[1] > gb[3]):
        R.err("site", "the write box %s overlaps the gulch zone's box %s" % (box, gb))
    for f in gulch.get("farms") or []:
        a = f.get("approach")
        if a and not (box[2] < a[0] or box[0] > a[3] or box[3] < a[2] or box[1] > a[5]):
            R.err("site", "the write box overlaps the Mega den %s's approach box" % f.get("id"))
    for rid, r in load_json("rift_regions.json", data)["regions"].items():
        b = r["bbox"]
        if not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]):
            R.err("site", "the write box overlaps the traced Rift region %s" % rid)
    towns = load_json("towns.json", data)["towns"]
    for t in (towns.values() if isinstance(towns, dict) else towns):
        fp = t.get("footprint") or {}
        if all(k in fp for k in ("min_x", "min_z", "max_x", "max_z")):
            if not (box[2] < fp["min_x"] or box[0] > fp["max_x"] or box[3] < fp["min_z"] or box[1] > fp["max_z"]):
                R.err("site", "the write box overlaps the town %s" % t.get("id"))
    paths = load_json("route_paths.json", data)["paths"]
    d = min(_box_dist(box, x, z) for k in ("route_08_blaine_to_giovanni", "victory_road") for x, z in paths[k])
    if d < ROUTE_CLEAR:
        R.err("site", "a write is %.0f blocks from a walked route point (the place is off the path: %d)" % (d, ROUTE_CLEAR))
    R.note("site: write box x%d..%d z%d..%d; nearest walked route point %.0f blocks away" % (box[0], box[2], box[1],
                                                                                             box[3], d))
    for e in load_json("resident_encounters.json", data)["encounters"]:
        loc = e.get("location") or {}
        if "x" in loc and _box_dist(box, loc["x"], loc["z"]) < RESIDENT_CLEAR:
            R.err("site", "a write is within %d blocks of the resident %s" % (RESIDENT_CLEAR, e["id"]))
    for p in load_json("placements.json", data)["placements"]:
        pos = p.get("position") or {}
        if isinstance(pos, dict) and "x" in pos and _box_dist(box, pos["x"], pos["z"]) < 60:
            R.err("site", "the placement %s is within 60 blocks" % p.get("id"))
    sub = [s for s in regions["subregions"] if s["id"] == E.rec["site"]["subregion"]]
    hx, hz = E.fold_centre
    if not sub or not any(_poly_inside(pg, hx, hz) for pg in sub[0]["polygons"]):
        R.err("site", "the fold's centre (%d, %d) is not in the sub-region %s" % (hx, hz, E.rec["site"]["subregion"]))


def check_footprint(R, E, W):
    shell_cols = E.work_box
    for (x, y, z), st in W.rep.state.items():
        gy = W.ground(x, z)
        if y > gy:
            if not E.in_box(E.above_box, x, z):
                R.err("footprint", "(%d, %d, %d) %s is written above the ground outside the site %s"
                      % (x, y, z, base(st), E.above_box))
                return
        elif not (E.in_box(shell_cols, x, z) or (y == gy and E.in_box(E.above_box, x, z))):
            R.err("footprint", "(%d, %d, %d) %s is written under the ground outside the working and the site's top layer"
                  % (x, y, z, base(st)))
            return


def check_seat(R, E, W):
    for x in range(E.x0, E.x1 + 1):
        for z in range(E.z0, E.z1 + 1):
            k = (x, E.bf, z)
            if (x, z) == (E.wx, E.wz):
                if base(W.at(k)) != TRAPDOOR:
                    R.err("seat", "the well's mouth %s is %s, not the trapdoor" % (k, W.at(k)))
                continue
            if W.passable(k) or k not in W.rep.state:
                R.err("seat", "the barn floor is open or unwritten at %s (floor y%d = max ground + 1)" % (k, E.bf))
                return
            for y in range(W.ground(x, z) + 1, E.bf):
                if W.passable((x, y, z)):
                    R.err("seat", "the barn stands on air at (%d, %d, %d)" % (x, y, z))
                    return
    # a floor seated high leaves floor blocks where a player's feet should be: nothing inside the walls one over the
    # derived floor may be a floor block
    over = [(x, z) for x in range(E.x0 + 1, E.x1) for z in range(E.z0 + 1, E.z1)
            if base(W.at((x, E.bf + 1, z))) in ("minecraft:cobblestone", "minecraft:coarse_dirt")]
    if over:
        R.err("seat", "the floor is a block high: floor blocks at y%d inside the walls, e.g. %s" % (E.bf + 1, over[:2]))


def check_working(R, E, W):
    allowed_in_void = {"minecraft:barrel", "minecraft:hay_block"}
    for v in sorted(E.voids):
        b = base(W.at(v))
        if not (W.passable(v) or b in allowed_in_void):
            R.err("working", "the void block %s is %s" % (v, W.at(v)))
            return
    n_shell = 0
    for (x, y, z) in E.voids:
        for dx in range(-E.m, E.m + 1):
            for dz in range(-E.m, E.m + 1):
                cx, cz = x + dx, z + dz
                top = W.ground(cx, cz) - E.keep
                for dy in range(-E.m, E.m + 1):
                    k = (cx, y + dy, cz)
                    if k in E.voids or k[1] > top:
                        continue
                    if k not in W.rep.state or W.passable(k):
                        R.err("working", "%s is within %d of the void %s and was not written solid (the shell)"
                              % (k, E.m, (x, y, z)))
                        return
                    n_shell += 1
    worst = None
    for (x, y, z) in E.voids:
        if E.in_barn(x, z):
            continue
        c = W.ground(x, z) - y
        if worst is None or c < worst[0]:
            worst = (c, (x, y, z))
        if c < E.m + 1:
            R.err("working", "the void block %s has %d blocks of ground over it; margin %d needs %d"
                  % ((x, y, z), c, E.m, E.m + 1))
            return
    R.note("working: %d void blocks, least cover outside the barn %s at %s" % (len(E.voids), worst[0], worst[1]))
    bx0, bz0, bx1, bz1 = E.work_box

    def inside(k):
        return bx0 - 2 <= k[0] <= bx1 + 2 and bz0 - 2 <= k[2] <= bz1 + 2 and E.wf - E.m - 2 <= k[1] <= E.bf + 3

    start = (E.store["x"][0] + 1, E.wf + 2, (E.store["z"][0] + E.store["z"][1]) // 2)
    sealed = flood(W, start, inside, trapdoor_open=False)
    leak = [k for k in sealed if k not in E.voids]
    if leak:
        R.err("working", "with the trapdoor closed the working is open to %s (sealed fails)" % (sorted(leak)[:3],))


def check_walk(R, E, W, data=DATA):
    rec = E.rec
    pad = 8
    xa, za, xb, zb = E.above_box
    xa, za, xb, zb = min(xa, E.work_box[0]) - pad, min(za, E.work_box[1]) - pad, max(xb, E.work_box[2]) + pad, zb + pad

    def inside(k):
        return xa <= k[0] <= xb and za <= k[2] <= zb and E.wf - 1 <= k[1] <= E.ridge + 2

    sx, sz = rec["barn"]["south_doorway_x"], E.fz1 + 4
    start = (sx, W.ground(sx, sz) + 1, sz)
    closed = walk(W, start, inside, trapdoor_open=False)
    opened = walk(W, start, inside, trapdoor_open=True)
    aisle = (E.x0 + 3, E.bf + 1, E.zc)
    loft = (rec["barn"]["loft"]["x"][0] + 3, E.loft_y + 1, E.zc)
    rw = [r for r in load_json("rewards.json", data)["rewards"] if r["id"] == rec["find"]["reward"]]
    if aisle not in closed:
        R.err("walk", "a player outside cannot reach the barn floor at %s" % (aisle,))
    if loft not in closed:
        R.err("walk", "a player cannot climb to the loft at %s" % (loft,))
    if rw:
        t = rw[0]["trigger"]
        box = [(x, y, z) for x in range(t["min"][0], t["max"][0] + 1) for y in range(t["min"][1], t["max"][1] + 1)
               for z in range(t["min"][2], t["max"][2] + 1)]
        if not any(k in opened for k in box):
            R.err("walk", "with the trapdoor open a player cannot reach the store's trigger box")
        if any(k in closed for k in box):
            R.err("walk", "with the trapdoor closed a player still reaches the store: the working is not sealed")
    R.note("walk: %d feet cells reachable with the trapdoor closed, %d open" % (len(closed), len(opened)))
    return opened


def check_fold(R, E, W, rec_hb):
    cx, cz = E.fold_centre
    seen, todo = {(cx, cz)}, deque([(cx, cz)])
    inner = (E.fx0 + 1, E.fz0 + 1, E.fx1 - 1, E.fz1 - 1)
    while todo:
        x, z = todo.popleft()
        if not E.in_box(inner, x, z):
            R.err("fold", "a Pokemon on the fold's floor walks out at (%d, %d)" % (x, z))
            return
        fy = W.ground(x, z) + 1
        for dx, dz in H4:
            nx, nz = x + dx, z + dz
            if (nx, nz) in seen:
                continue
            ny = W.ground(nx, nz) + 1
            if abs(ny - fy) > 1 or not W.passable((nx, ny, nz)) or not W.passable((nx, ny + 1, nz)):
                continue
            seen.add((nx, nz))
            todo.append((nx, nz))
    if len(seen) < 10:
        R.err("fold", "the fold's floor is %d columns: it is not a pen" % len(seen))


def check_habitat(R, E, W, data):
    rec = E.rec
    hbs = [b for b in load_json("habitat_blocks.json", data)["blocks"] if b["id"] == rec["herd"]["block"]]
    if not hbs:
        R.err("habitat", "no Habitat Block %s in data/habitat_blocks.json" % rec["herd"]["block"])
        return
    hb = hbs[0]
    cx, cz = E.fold_centre
    want = (cx, W.ground(cx, cz), cz)
    pos = (hb["position"]["x"], hb["position"]["y"], hb["position"]["z"])
    if pos != want:
        R.err("habitat", "the block stands at %s, not the fold floor's centre %s" % (pos, want))
    if hb.get("style") != "activated" or hb.get("pool") != "cobblers:%s" % rec["herd"]["habitat"]:
        R.err("habitat", "the block is not activated on cobblers:%s" % rec["herd"]["habitat"])
    if base(W.at(pos)) != hb.get("mimic") or pos not in W.rep.state:
        R.err("habitat", "the pack writes %s where the block sits, not its mimic %s" % (W.at(pos), hb.get("mimic")))
    a = hb.get("activated") or {}
    r = int(a.get("spawn_range", 0))
    places = []
    for x in range(pos[0] - r, pos[0] + r + 1):
        for z in range(pos[2] - r, pos[2] + r + 1):
            for y in range(pos[1] - r, pos[1] + r + 1):
                f = (x, y, z)
                if W.passable(f) and W.passable((x, y + 1, z)) and W.floor((x, y - 1, z)):
                    places.append(f)
    out = [f for f in places if not (E.fx0 < f[0] < E.fx1 and E.fz0 < f[2] < E.fz1)]
    if out:
        R.err("habitat", "the spawn box holds standing places outside the pen, e.g. %s" % (out[:3],))
    if len(places) < int(a.get("max_spawns", 0)):
        R.err("habitat", "the spawn box holds %d standing places for max_spawns %s" % (len(places), a.get("max_spawns")))
    cr = float(a.get("cancel_range", 0))
    for x in range(E.x0 + 1, E.x1):
        for z in range(E.z0 + 1, E.z1):
            d = math.dist((x + 0.5, E.bf + 1, z + 0.5), (pos[0] + 0.5, pos[1] + 0.5, pos[2] + 0.5))
            if d < cr:
                R.err("habitat", "the cancel sphere (%.0f) reaches the barn floor at (%d, %d)" % (cr, x, z))
                return
    sp = load_json("spawns.json", data)
    hab = [h for h in sp["habitats"] if h["id"] == rec["herd"]["habitat"]]
    if not hab:
        R.err("habitat", "no habitat pool %s in data/spawns.json" % rec["herd"]["habitat"])
        return
    species = sorted(e["pokemon"] for e in hab[0]["entries"])
    if species != sorted(rec["herd"]["species"]):
        R.err("habitat", "the pool is %s, the record names %s" % (species, sorted(rec["herd"]["species"])))
    sub = [s for s in sp["subregions"] if s["id"] == rec["site"]["subregion"]][0]
    lo, hi = sub["level_band"]["minimum"], sub["level_band"]["maximum"]
    cap = load_json("encounter_design.json", data)["rules"]["tiers"][str(sub["level_band"]["tier"])]["cap"]
    for e in hab[0]["entries"] + [x for x in sp["entries"] if x.get("scope") == rec["herd"]["habitat"]]:
        a_, b_ = (int(v) for v in e["level"].split("-"))
        if a_ < lo or b_ > hi or b_ > cap:
            R.err("habitat", "%s spawns at %s, outside the %s band %d-%d (cap %d)" % (e.get("species"), e["level"],
                                                                                     sub["id"], lo, hi, cap))
    R.note("habitat: %s at %s, %d standing places in its spawn box, all in the pen" % (hb["id"], pos, len(places)))


def check_blocks(R, E, W, data):
    ids = set(E.rec["blocks"]["ids"])
    placed = {base(s) for s in W.rep.state.values()}
    bad = sorted(placed - ids)
    if bad:
        R.err("blocks", "written but not in blocks.ids: %s" % bad)
    sb = set(load_json("spawn_blocks.json", data)["blocks"])
    pol = load_json("spawn_block_policy.json", data)
    allowed = {b for w in pol.get("whitelist") or [] if "drovers_hollow" in (w.get("scope") or "") for b in w["blocks"]}
    cond = sorted((placed & sb) - allowed)
    if cond:
        R.err("blocks", "spawn conditions written (data/spawn_blocks.json): %s" % cond)
    if any(b.endswith("_bed") or b == "minecraft:chest" for b in placed):
        R.err("blocks", "a chest or a bed is written")


def check_attached(R, E, W):
    for k, st in W.rep.state.items():
        b = base(st)
        if b not in HUNG:
            continue
        x, y, z = k
        if b in ("minecraft:ladder", "minecraft:spruce_wall_sign"):
            dx, _dy, dz = FACING[prop(st, "facing")]
            s = (x - dx, y, z - dz)
        elif b == "minecraft:lantern":
            s = (x, y + 1, z) if prop(st, "hanging") == "true" else (x, y - 1, z)
        else:
            s = (x, y + 1, z)
        sb = base(W.at(s))
        on_chain = b in ("minecraft:chain", "minecraft:lantern") and s[1] == y + 1 and sb == "minecraft:chain"
        if not (on_chain or not W.passable(s)):
            R.err("attached", "%s at %s hangs on %s at %s" % (b, k, W.at(s), s))
            return
        if s in W.rep.when and W.rep.when[s] > W.rep.when[k]:
            R.err("attached", "%s at %s is written before what holds it (%s)" % (b, k, s))
            return


def check_light(R, E, W, reached):
    lanterns = [k for k, s in W.rep.state.items() if base(s) == "minecraft:lantern"]
    inside = [f for f in reached if (E.in_barn(f[0], f[2]) and f[1] > E.bf) or f in E.voids]
    worst = 0
    for f in inside:
        d = min(abs(f[0] - l[0]) + abs(f[1] - l[1]) + abs(f[2] - l[2]) for l in lanterns) if lanterns else 99
        if d > worst:
            worst = d
        if d > LIGHT_REACH:
            R.err("light", "%s is %d blocks from the nearest lantern (reach %d)" % (f, d, LIGHT_REACH))
            return
    R.note("light: %d lanterns; the darkest place a player stands inside is %d from one" % (len(lanterns), worst))


def check_find(R, E, W, data):
    rec = E.rec
    rw = [r for r in load_json("rewards.json", data)["rewards"] if r["id"] == rec["find"]["reward"]]
    if not rw:
        R.err("find", "no reward %s in data/rewards.json" % rec["find"]["reward"])
        return
    r = rw[0]
    if r.get("kind") != "cache":
        R.err("find", "%s is not a cache" % r["id"])
    if tuple(r["container"]["at"]) != E.barrel:
        R.err("find", "the container is at %s; the store's east end is %s" % (r["container"]["at"], E.barrel))
    if base(W.at(E.barrel)) != "minecraft:barrel" or E.barrel not in W.rep.state:
        R.err("find", "the pack writes %s at the barrel's place %s" % (W.at(E.barrel), E.barrel))
    t = r["trigger"]
    for x in range(t["min"][0], t["max"][0] + 1):
        for y in range(t["min"][1], t["max"][1] + 1):
            for z in range(t["min"][2], t["max"][2] + 1):
                if (x, y, z) not in E.voids:
                    R.err("find", "the trigger box reaches %s, outside the store" % ((x, y, z),))
                    return


def check_drover(R, E, W, data):
    rec = E.rec
    x, z = E.npc
    feet = (x, W.ground(x, z) + 1, z)
    if not (W.passable(feet) and W.passable((x, feet[1] + 1, z))):
        R.err("drover", "his spot %s is not two blocks of air" % (feet,))
    if base(W.at((x, feet[1] - 1, z))) != "minecraft:dirt_path" or (x, feet[1] - 1, z) not in W.rep.state:
        R.err("drover", "he does not stand on the path the pack writes at %s" % ((x, feet[1] - 1, z),))
    conv = [c for c in load_json("dialogue.json", data)["conversations"] if c["id"] == rec["npc"]["conversation"]]
    if not conv or not conv[0].get("npc_id"):
        R.err("drover", "no conversation %s with an npc_id" % rec["npc"]["conversation"])
        return
    c = conv[0]
    q = [x for x in load_json("quests.json", data)["quests"] if x["id"] == c.get("quest_id")]
    fld = [f for f in load_json("progression.json", data)["quest_fields"]
           if f["id"] == (c.get("cursor") or {}).get("progression_field")]
    if not q or c["id"] not in q[0].get("dialogue_ids", []):
        R.err("drover", "the quest %s does not list the conversation" % c.get("quest_id"))
    if not fld or sorted(fld[0]["allowed_values"]) != sorted(n["id"] for n in c["nodes"]):
        R.err("drover", "the cursor field's values are not the conversation's nodes")
    text = " ".join(n.get("text", "") for n in c["nodes"]).lower()
    for word in ("trough", "trapdoor", "working"):
        if word not in text:
            R.err("drover", "his talk never names the %s: it must point at the find" % word)


def sightline(g, frm, to, eye=1.62):
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


def check_seen(R, E, W, data):
    target = (E.x0 + 4, E.ridge, E.zc)
    if base(W.at(target)) != "minecraft:spruce_planks":
        R.err("seen", "the ridge derived here, %s, is %s in the pack" % (target, W.at(target)))
    path = load_json("route_paths.json", data)["paths"]["route_08_blaine_to_giovanni"]
    n = 0
    for x, z in path[::4]:
        if math.hypot(x - target[0], z - target[2]) <= SIGHT_RANGE and sightline(W.ground, (x, z), target) > 0:
            n += 1
    if not n:
        R.err("seen", "the ridge %s is in sight from no point of Route 8 within %d blocks" % (target, SIGHT_RANGE))
    R.note("seen: the ridge %s is in clear sight from %d sampled points of Route 8" % (target, n))


def check_steps(R, rep, lines, steps):
    import function_limits
    bad = function_limits.check_lines(lines, "build")
    if bad:
        R.err("steps", "%d command(s) the server would refuse: %s" % (len(bad), bad[:2]))
    if rep.bad:
        R.err("steps", "%d line(s) this audit cannot read: %s" % (len(rep.bad), rep.bad[:2]))
    if steps is None:
        return
    if ("fn", "cobblers:drovers_hollow/build") not in [tuple(s) for s in steps]:
        R.err("steps", "the re-application does not run cobblers:drovers_hollow/build")
    holds = [tuple(int(v) for v in s[1].split()[2:]) for s in steps if s[0] == "cmd" and s[1].startswith("forceload add")]
    if not holds or steps[-1][0] != "cmd" or not steps[-1][1].startswith("forceload remove"):
        R.err("steps", "the re-application does not hold the chunks round the build and release them after")
        return
    for (x, _y, z) in rep.state:
        if not any(min(h[0], h[2]) <= x <= max(h[0], h[2]) and min(h[1], h[3]) <= z <= max(h[1], h[3]) for h in holds):
            R.err("steps", "(%d, %d) is written outside the re-application's forceload" % (x, z))
            return


def audit(rec, g, pack, steps=None, data=DATA):
    R = Report()
    fn = Path(pack) / FUNCTION
    if not fn.exists():
        R.err("steps", "no %s in %s: build the pack first" % (FUNCTION, pack))
        return R
    lines = fn.read_text(encoding="utf-8").splitlines()
    rep = Replay(lines)
    W = World(rep, g)
    E = Expect(rec, g)
    check_site(R, E, rep, data)
    check_footprint(R, E, W)
    check_seat(R, E, W)
    check_working(R, E, W)
    reached = check_walk(R, E, W, data)
    check_fold(R, E, W, None)
    check_habitat(R, E, W, data)
    check_blocks(R, E, W, data)
    check_attached(R, E, W)
    check_light(R, E, W, reached)
    check_find(R, E, W, data)
    check_drover(R, E, W, data)
    check_seen(R, E, W, data)
    check_steps(R, rep, lines, steps)
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--data", default=str(DATA / "drovers_hollow.json"))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rec = json.loads(Path(a.data).read_text(encoding="utf-8"))
    g = G.load(a.source_root)
    import drovers_hollow  # the re-application steps are the generator's OUTPUT, checked here, never its geometry
    steps = drovers_hollow.placement_steps(None, g)
    R = audit(rec, g, a.pack, steps)
    for n in R.notes:
        print("  " + n)
    for e in R.errors:
        print("PROBLEM " + e)
    print("drovers_hollow_audit: %d problem(s)" % len(R.errors))
    return 1 if R.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
