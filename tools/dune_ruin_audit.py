#!/usr/bin/env python
"""The Copperway Khan, audited offline: the emitted pack replayed block by block against the place, re-derived.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/dune_ruin.py's
geometry. It reads data/dune_ruin.json, the canonical heightmap (tools/ground.py), data/habitat_blocks.json,
data/spawns.json, data/regions.json, data/rewards.json, data/dialogue.json, data/quests.json, data/towns.json,
data/placements.json, data/route_paths.json, data/resident_encounters.json, data/spawn_blocks.json and
data/spawn_block_policy.json, derives what it expects with its own arithmetic, then REPLAYS the generated build function
into a block model over the natural ground and checks it. The only things taken from the generator are its outputs (the
pack, and the re-application steps and NPC placement it hands tools/reapply.py), which are what is being checked.
tests/test_dune_ruin.py mutates the GENERATOR (a vault one block taller, a trapdoor left out, a lintel raised off the
sand line, the trench's steps gone, a lantern taken from the vault, sand written, a post seated high) and leaves the
records alone; each must fail a named check here.

What is checked, each from the data and the heightmap, never from the pack:

  footprint  no write outside the Khan's box or a milestone's column; nothing under the Khan's footing but the vault's
             columns; every written column dry (tools/water_mask.py); nothing within 4 blocks of a resident anchor, in a
             town's footprint, within 32 of a placement or within 128 of the critical path (data/route_paths.json)
  drowned    the sand line S is max(ground under the outer walls) and the floor F = S - bury: the outer wall is solid
             from F-1 to S+2, every arcade lintel lies on the sand line, every arch but the trench's is NOT open
             (sand or drift fills it), and no buried room holds an air cell under its roof (no dark gap)
  way in     walking (feet and head clear, ground under the feet, a step up of one, a drop of three) from the sand in
             front of the gate reaches the courtyard's sand, the hall's floor and the salvager's spot, and NOT the vault
  vault      the room is the record's 9 by 9 by air_height with its ceiling at F, its floor the record's floor block;
             with the trapdoor closed and the bricked door standing a flood fill never leaves it (sealed); with the
             door broken and the trapdoor open it reaches the hall (the way in exists)
  habitat    the record's Habitat Block: activated, its pool the record's, its position the vault floor's centre (as
             derived here), its mimic the floor block, which the build writes there; its spawn box holds standing
             places for max_spawns and NONE outside the vault; its cancel sphere takes in the vault and no ground outside
             the Khan's walls; the pool is the record's species alone, within the sub-region's band
  blocks     every written block is in blocks.ids; none is a spawn condition (data/spawn_blocks.json) unless a policy
             entry scoped to dune_ruin allows it; no chest and no bed; NO sand at all
  attached   every sign, ladder, lantern, trapdoor and carpet is written after what holds it up, which is solid
  light      every standing place in the hall, the stair-head room and the vault has block light >= 1 from the lanterns
             written there (15 a lantern, 10 a soul lantern, one less a block): no hostile mob spawns in them
  clear      logs, leaves, replaceable plants and cacti are cleared over every column written above the ground
  find       data/rewards.json's cache for the record: a barrel where the record puts it, its trigger box inside the
             vault and holding a standing place, the container beside the box
  road       milestones from outside Fossick's footprint (the first within 32 of its edge) to the gate: posts no more
             than spacing + 2 apart, each solid at its own ground + 1 and + 2, every lantern_every-th lit, the first
             signed, the last within spacing of the gatehouse
  npc        the R18DU placement stands on the hall floor at the record's spot, two blocks of air; its conversation
             exists, has an NPC, and compiles
  steps      the re-application holds every written chunk, runs the build, releases; the function passes
             tools/function_limits.py

NOT checked, and it needs a running server: that the fills land, that the world's ground under the Khan is sand (the
heightmap says where the ground is, not what it is), that Cofagrigus spawn in the vault and stay in it, that the cache
grants, that the salvager appears.

  python tools/dune_ruin_audit.py [--pack build/datapacks/cobblers_dune_ruin] [--source-root R]
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
PACK = ROOT / "build" / "datapacks" / "cobblers_dune_ruin"
FUNCTION = "data/cobblers/function/dune_ruin/build.mcfunction"
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*?)$")
FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$")
# what a body passes through; a closed trapdoor is its own case
PASSABLE = {"minecraft:air", "minecraft:ladder", "minecraft:lantern", "minecraft:soul_lantern", "minecraft:chain",
            "minecraft:acacia_wall_sign", "minecraft:acacia_sign", "minecraft:red_carpet", "minecraft:brown_carpet"}
TRAPDOOR = "minecraft:acacia_trapdoor"
LIGHT = {"minecraft:lantern": 15, "minecraft:soul_lantern": 10}
OPPOSITE = {"north": (0, 0, 1), "south": (0, 0, -1), "east": (-1, 0, 0), "west": (1, 0, 0)}
CLEAR_TAGS = ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable", "minecraft:cactus")


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

    def __init__(self, rep, g, opened=()):
        self.rep, self.g, self.opened = rep, g, set(opened)
        self._gc = {}

    def ground(self, x, z):
        if (x, z) not in self._gc:
            self._gc[(x, z)] = self.g(x, z)
        return self._gc[(x, z)]

    def at(self, k):
        if k in self.opened:
            return "minecraft:air"
        s = self.rep.state.get(k)
        if s is not None:
            return s
        return "natural:ground" if k[1] <= self.ground(k[0], k[2]) else "minecraft:air"

    def passable(self, k, trapdoor_open=False):
        b = base(self.at(k))
        if b in PASSABLE:
            return True
        return b == TRAPDOOR and trapdoor_open

    def solid(self, k):
        return not self.passable(k, trapdoor_open=True)


def flood(world, start, inside, **open_):
    seen, todo = {start}, deque([start])
    while todo:
        x, y, z = todo.popleft()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            k = (x + dx, y + dy, z + dz)
            if k in seen or not inside(k) or not world.passable(k, **open_):
                continue
            seen.add(k)
            todo.append(k)
    return seen


def standing(W, k):
    x, y, z = k
    return W.passable(k) and W.passable((x, y + 1, z)) and W.solid((x, y - 1, z))


def walk(W, start, inside):
    """Every standing place reachable on foot: a step up of one, a drop of up to three."""
    seen, todo = {start}, deque([start])
    while todo:
        x, y, z = todo.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if not W.passable((x + dx, y + 1, z + dz)) and not W.passable((x, y + 2, z)):
                continue                              # no head room either way: a wall
            for dy in (1, 0, -1, -2, -3):
                k = (x + dx, y + dy, z + dz)
                if not inside(k) or k in seen:
                    continue
                if dy == 1 and not W.passable((x, y + 2, z)):
                    continue
                if standing(W, k):
                    seen.add(k)
                    todo.append(k)
                    break
                if dy <= 0 and not W.passable((x + dx, y + dy, z + dz)):
                    break
    return seen


# --------------------------------------------------------------------------------------------- the expectations
class Expect:
    """What the record and the heightmap say, computed here."""

    def __init__(self, rec, g):
        self.rec = rec
        self.cx, self.cz = rec["site"]["centre"]
        H = self.H = rec["khan"]["half"]
        self.A = rec["khan"]["arcade"]
        self.S = max(g(self.cx + a, self.cz + b) for a in range(-H, H + 1) for b in range(-H, H + 1)
                     if max(abs(a), abs(b)) == H)
        self.F = self.S - rec["khan"]["bury"]
        u = rec["undercroft"]
        self.ux, self.uz = self.cx + u["centre_local"][0], self.cz + u["centre_local"][1]
        self.n, self.air, self.under = u["interior_half"], u["air_height"], u["under_fill"]
        self.vault_floor = self.F - self.air - 1
        self.room = {(self.ux + a, y, self.uz + b) for a in range(-self.n, self.n + 1) for b in range(-self.n, self.n + 1)
                     for y in range(self.vault_floor + 1, self.F)}
        (ax0, ax1), (az0, az1) = u["antechamber"]["x"], u["antechamber"]["z"]
        self.ante = {(self.cx + a, y, self.cz + b) for a in range(ax0, ax1 + 1) for b in range(az0, az1 + 1)
                     for y in range(self.F + 1, self.F + 5)}
        (hx0, hx1), (hz0, hz1) = rec["hall"]["x"], rec["hall"]["z"]
        self.hall = {(self.cx + a, y, self.cz + b) for a in range(hx0, hx1 + 1) for b in range(hz0, hz1 + 1)
                     for y in range(self.F + 1, self.F + 5)}
        self.hall_cols = {(x, z) for x, _y, z in self.hall}
        self.ante_cols = {(x, z) for x, _y, z in self.ante}
        (tx0, tx1), (tz0, tz1) = rec["trench"]["x"], rec["trench"]["z"]
        self.trench_cols = {(self.cx + a, self.cz + b) for a in range(tx0, tx1 + 1) for b in range(tz0, tz1 + 1)}
        self.trench_arch = {(self.cx + a, self.cz + self.A) for a in range(tx0, tx1 + 1)}
        dx, dz = u["bricked_door_local"]
        self.door = [(self.cx + dx, self.F + 1, self.cz + dz), (self.cx + dx, self.F + 2, self.cz + dz)]
        t = rec["khan"]["tower"]
        self.tower = (self.cx + t["corner"][0], self.cz + t["corner"][1], t["half"], self.F + t["top"])
        # the Khan's box: the walls, the gatehouse one block proud, the lantern posts three out
        self.box = (self.cx - H - 3, self.cz - H - 3, self.cx + H + 3, self.cz + H + 3)
        self.low_y = self.vault_floor - self.under
        self.top_y = self.F + t["top"] + 4
        nx, nz = rec["npc"]["at_local"]
        self.npc = (self.cx + nx, self.F + 1, self.cz + nz)
        bx, bz = rec["find"]["barrel_local"]
        self.barrel = (self.cx + bx, self.vault_floor + 1, self.cz + bz)
        self.gate_front = (self.cx, self.S + 1, self.cz - H - 5)


def in_box(x, z, box):
    return box[0] <= x <= box[2] and box[1] <= z <= box[3]


# --------------------------------------------------------------------------------------------- the checks
def check_footprint(rep, E, W, R, data=DATA):
    out = 0
    vault_cols = (E.ux - E.n - 1, E.uz - E.n - 1, E.ux + E.n + 1, E.uz + E.n + 1)
    for (x, y, z), s in sorted(rep.state.items()):
        if in_box(x, z, E.box):
            if not (E.low_y <= y <= E.top_y):
                R.err("footprint", "(%d, %d, %d) %s is outside the Khan's height range y%d..%d" % (x, y, z, s, E.low_y, E.top_y))
                out += 1
            elif y < E.F - 1 and not in_box(x, z, vault_cols):
                R.err("footprint", "(%d, %d, %d) %s is under the Khan's footing outside the vault's columns" % (x, y, z, s))
                out += 1
        elif not (W.ground(x, z) < y <= W.ground(x, z) + 3):
            R.err("footprint", "(%d, %d, %d) %s is outside the Khan and not on a milestone's own ground (y%d)"
                  % (x, y, z, s, W.ground(x, z)))
            out += 1
        if out > 20:
            return
    cols = {(x, z) for x, _y, z in rep.state}
    import water_mask
    bodies, sea = water_mask.bodies(), water_mask.sea_level()
    wet = [c for c in sorted(cols) if water_mask.level_at(c[0], c[1], W.ground, bodies, sea)[0] is not None]
    if wet:
        R.err("footprint", "%d written column(s) under painted water, e.g. %s" % (len(wet), wet[0]))
    for r in load_json("resident_encounters.json", data).get("encounters") or []:
        loc = r.get("location") or {}
        if "x" in loc and "z" in loc:
            near = [c for c in cols if math.hypot(c[0] - loc["x"], c[1] - loc["z"]) <= 4]
            if near:
                R.err("footprint", "writes within 4 blocks of resident %s's anchor (%s, %s), e.g. %s"
                      % (r["id"], loc["x"], loc["z"], near[0]))
    for t in load_json("towns.json", data)["towns"]:
        fp = t.get("footprint") or {}
        if all(k in fp for k in ("min_x", "min_z", "max_x", "max_z")):
            inside = [c for c in cols if fp["min_x"] <= c[0] <= fp["max_x"] and fp["min_z"] <= c[1] <= fp["max_z"]]
            if inside:
                R.err("footprint", "writes inside %s's footprint, e.g. %s" % (t["id"], inside[0]))
    pts = [(p["position"]["x"], p["position"]["z"], p["id"]) for p in load_json("placements.json", data)["placements"]
           if isinstance(p.get("position"), dict)]
    xs = [c[0] for c in cols]
    zs = [c[1] for c in cols]
    for px, pz, pid in pts:
        if min(xs) - 32 <= px <= max(xs) + 32 and min(zs) - 32 <= pz <= max(zs) + 32:
            d = min(math.hypot(px - c[0], pz - c[1]) for c in cols)
            if d < 32:
                R.err("footprint", "writes within %.0f blocks of placement %s" % (d, pid))
    route = [c for path in load_json("route_paths.json", data)["paths"].values() for c in path]
    near = min(math.hypot(rx - c[0], rz - c[1]) for c in sorted(cols)[::7] + [(E.cx, E.cz)] for rx, rz in route[::4])
    if near < 128:
        R.err("footprint", "writes %.0f blocks from the critical path (data/route_paths.json): under 128" % near)
    R.note("footprint: %d columns written, all dry; nearest critical path ~%.0f blocks" % (len(cols), near))


def check_drowned(rep, E, W, R):
    H, A, F, S = E.H, E.A, E.F, E.S
    gate = {(E.cx + a, E.cz - H) for a in (-1, 0, 1)}
    for a in range(-H, H + 1):
        for b in range(-H, H + 1):
            m = max(abs(a), abs(b))
            x, z = E.cx + a, E.cz + b
            if m == H and (x, z) not in gate:
                for y in range(F - 1, S + 3):
                    if not W.solid((x, y, z)):
                        R.err("drowned", "the outer wall at (%d, %d, %d) is %s: not solid from F-1 y%d to S+2 y%d"
                              % (x, y, z, W.at((x, y, z)), F - 1, S + 2))
                        return
            elif m == A:
                t = b if abs(a) == A else a
                pier = (abs(a) == A and abs(b) == A) or t % 4 == 2
                if (x, z) in E.trench_arch or (abs(a) <= 1 and b == -A):
                    continue
                if not W.solid((x, S, z)) or base(W.at((x, S, z))) == "natural:ground":
                    R.err("drowned", "no lintel on the sand line at (%d, %d, %d): %s" % (x, S, z, W.at((x, S, z))))
                    return
                if not pier:
                    for y in range(F + 1, S):
                        if W.passable((x, y, z)):
                            R.err("drowned", "the arch at (%d, %d) is open at y%d: only the trench's arch is dug out" % (x, z, y))
                            return
            elif m > A and (x, z) not in E.hall_cols and (x, z) not in E.ante_cols and not (abs(a) <= 1 and b < 0):
                for y in range(F + 1, S + 1):
                    if W.passable((x, y, z)):
                        R.err("drowned", "a dark gap at (%d, %d, %d) in a buried room" % (x, y, z))
                        return
    R.note("drowned: sand line S y%d, floor F y%d, outer wall to y%d" % (S, F, S + 2))


def check_way_in(rep, E, W, R):
    lo = (E.cx - E.H - 8, E.vault_floor - 1, E.cz - E.H - 8)
    hi = (E.cx + E.H + 8, E.S + 4, E.cz + E.H + 8)
    inside = lambda k: all(lo[i] <= k[i] <= hi[i] for i in range(3))  # noqa: E731
    start = (E.gate_front[0], W.ground(E.gate_front[0], E.gate_front[2]) + 1, E.gate_front[2])
    if not standing(W, start):
        R.err("way in", "the sand in front of the gate %s is not a standing place" % (start,))
        return
    reach = walk(W, start, inside)
    court = [k for k in reach if abs(k[0] - E.cx) < E.A and abs(k[2] - E.cz) < E.A]
    hall = [k for k in reach if k in E.hall]
    if not court:
        R.err("way in", "walking from the gate does not reach the courtyard")
    if not hall:
        R.err("way in", "walking from the gate does not reach the hall's floor")
    if E.npc not in reach:
        R.err("way in", "walking from the gate does not reach the salvager's spot %s" % (E.npc,))
    if any(k in E.room or k in E.ante for k in reach):
        R.err("way in", "the store is reachable on foot without breaking in")
    R.note("way in: %d standing places reachable from the gate (%d in the courtyard, %d in the hall)"
           % (len(reach), len(court), len(hall)))


def check_vault(rep, E, W, R):
    floor_block = E.rec["blocks"]["vault_floor"]
    c = (E.ux, E.vault_floor, E.uz)
    if base(rep.state.get(c, "")) != floor_block:
        R.err("vault", "the floor's centre %s is %s, not %s" % (c, rep.state.get(c), floor_block))
        return
    tx, tz = E.rec["undercroft"]["trapdoor_local"]
    trap = (E.cx + tx, E.F, E.cz + tz)
    if base(W.at(trap)) != TRAPDOOR:
        R.err("vault", "the trapdoor at %s is %s, not %s" % (trap, W.at(trap), TRAPDOOR))
    for a in range(-E.n, E.n + 1):
        for b in range(-E.n, E.n + 1):
            x, z = E.ux + a, E.uz + b
            if not W.solid((x, E.vault_floor, z)):
                R.err("vault", "the floor at (%d, %d, %d) is open" % (x, E.vault_floor, z))
                return
            k = (x, E.F, z)
            if W.passable(k) and k != trap:
                R.err("vault", "the ceiling at %s is open (%s): the vault is taller than the record's %d" % (k, W.at(k), E.air))
                return
            if E.F > W.ground(x, z):
                R.err("vault", "the ceiling at (%d, %d) is y%d, over the ground y%d" % (x, z, E.F, W.ground(x, z)))
                return
    open_ = [k for k in E.room if W.passable(k)]
    if len(open_) < 0.6 * len(E.room):
        R.err("vault", "only %d of the room's %d cells are open" % (len(open_), len(E.room)))
        return
    start = sorted(open_)[0]
    lo = (E.cx - E.H - 4, E.low_y - 2, E.cz - E.H - 4)
    hi = (E.cx + E.H + 4, E.S + 4, E.cz + E.H + 4)
    inside = lambda k: all(lo[i] <= k[i] <= hi[i] for i in range(3))  # noqa: E731
    sealed = flood(W, start, inside)
    leak = [k for k in sealed if k not in E.room]
    if leak:
        R.err("vault", "with the trapdoor closed and the door bricked the vault is open to %d cell(s) outside it, e.g. %s"
              % (len(leak), sorted(leak)[0]))
    Wo = World(rep, W.g, opened=E.door)
    reach = flood(Wo, start, inside, trapdoor_open=True)
    if not any(k in E.hall for k in reach):
        R.err("vault", "with the door broken and the trapdoor open the vault does not reach the hall: no way in")
    R.note("vault: %d cells (%d open), floor y%d, ceiling y%d" % (len(E.room), len(open_), E.vault_floor, E.F))


def _in_poly(x, z, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi:
            inside = not inside
        j = i
    return inside


def subregion_at(x, z, data=DATA):
    for s in load_json("regions.json", data)["subregions"]:
        if any(_in_poly(x + 0.5, z + 0.5, p) for p in s.get("polygons") or []):
            return s["id"]
    return None


def check_habitat(rep, E, W, R, data=DATA):
    rec = E.rec
    hb = {b["id"]: b for b in load_json("habitat_blocks.json", data)["blocks"]}
    b = hb.get(rec["habitat"]["block"])
    if b is None:
        R.err("habitat", "no Habitat Block %s in data/habitat_blocks.json" % rec["habitat"]["block"])
        return
    want = (E.ux, E.vault_floor, E.uz)
    pos = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
    a = b.get("activated") or {}
    if b.get("style") != "activated" or b.get("replace_spawns") is not False:
        R.err("habitat", "%s is not an activated block without ReplaceSpawns" % b["id"])
    if b.get("pool") != "cobblers:%s" % rec["habitat"]["pool"]:
        R.err("habitat", "%s's pool is %s, not cobblers:%s" % (b["id"], b.get("pool"), rec["habitat"]["pool"]))
    if pos != want:
        R.err("habitat", "%s stands at %s, not the vault floor's centre %s" % (b["id"], pos, want))
    if b.get("mimic") != rec["blocks"]["vault_floor"]:
        R.err("habitat", "%s mimics %s, not the vault floor %s" % (b["id"], b.get("mimic"), rec["blocks"]["vault_floor"]))
    if base(rep.state.get(pos, "")) != rec["blocks"]["vault_floor"]:
        R.err("habitat", "the build writes %s at the block's position %s, not the floor it is disguised as"
              % (rep.state.get(pos), pos))
    if a.get("trigger") != "TICK" or a.get("chance") != 1.0 or not isinstance(a.get("max_spawns"), int) or a["max_spawns"] < 2:
        R.err("habitat", "%s must refill on TICK at chance 1 and keep at least 2 alive" % b["id"])
        return
    r = a["spawn_range"]
    box = [(pos[0] + dx, pos[1] + dy, pos[2] + dz) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
           for dz in range(-r, r + 1)]
    places = [k for k in box if standing(W, k)]
    stray = [k for k in places if k not in E.room]
    if stray:
        R.err("habitat", "the spawn box (spawn_range %d) holds %d standing place(s) outside the vault, e.g. %s"
              % (r, len(stray), sorted(stray)[0]))
    inroom = [k for k in places if k in E.room]
    if len(inroom) < a["max_spawns"]:
        R.err("habitat", "the spawn box holds %d standing places in the vault, fewer than max_spawns %d"
              % (len(inroom), a["max_spawns"]))
    c = a.get("cancel_range")
    if isinstance(c, int) and c > 0:
        far = max(math.dist(pos, k) for k in E.room)
        if far > c:
            R.err("habitat", "cancel_range %d does not take in the vault (its far cell is %.1f away)" % (c, far))
        for dx in range(-c - 1, c + 2):
            for dz in range(-c - 1, c + 2):
                x, z = pos[0] + dx, pos[2] + dz
                if abs(x - E.cx) <= E.H and abs(z - E.cz) <= E.H:
                    continue
                k = (x, W.ground(x, z) + 1, z)
                if math.dist(pos, k) <= c:
                    R.err("habitat", "cancel_range %d reaches the ground outside the walls at %s" % (c, k))
                    return
    R.note("habitat: %s at %s, box %d standing places, all in the vault" % (b["id"], pos, len(inroom)))
    sp = load_json("spawns.json", data)
    hab = next((h for h in sp["habitats"] if h["id"] == rec["habitat"]["pool"]), None)
    if hab is None:
        R.err("habitat", "no habitat %s in data/spawns.json" % rec["habitat"]["pool"])
        return
    species = {e["pokemon"] for e in hab["entries"]}
    if species != {rec["habitat"]["species"]}:
        R.err("habitat", "the pool holds %s, not %s alone" % (sorted(species), rec["habitat"]["species"]))
    entries = [e for e in sp["entries"] if e.get("scope") == hab["id"] and e.get("mechanism") == "habitat_block"]
    if [e["species"] for e in entries] != [rec["habitat"]["species"]] or entries[0].get("spawnable_position") != "grounded":
        R.err("habitat", "the pool's spawn entries are %s, not one grounded %s" % ([e.get("id") for e in entries],
                                                                                  rec["habitat"]["species"]))
    sub = subregion_at(E.cx, E.cz, data)
    if sub != rec["site"]["subregion"]:
        R.err("habitat", "the Khan stands in %s, not the record's %s" % (sub, rec["site"]["subregion"]))
    band = next((s["level_band"] for s in sp["subregions"] if s["id"] == sub), None)
    if band is None:
        R.err("habitat", "the Khan stands in no sub-region with a level band (%s)" % sub)
        return
    for e in list(hab["entries"]) + entries:
        lo, hi = (int(v) for v in e["level"].split("-"))
        if lo < band["minimum"] or hi > band["maximum"]:
            R.err("habitat", "%s levels %s are outside %s's band %d-%d" % (e.get("id", e.get("species")), e["level"], sub,
                                                                          band["minimum"], band["maximum"]))


def check_blocks(rep, E, R, data=DATA):
    allowed = set(E.rec["blocks"]["ids"])
    spawn = set(load_json("spawn_blocks.json", data)["blocks"])
    policy = load_json("spawn_block_policy.json", data)
    white = {bk for w in policy.get("whitelist") or [] if "dune_ruin" in (w.get("scope") or "") for bk in w["blocks"]}
    seen = {base(s) for s in rep.state.values()}
    for bk in sorted(seen - allowed):
        R.err("blocks", "%s is written and is not in data/dune_ruin.json blocks.ids" % bk)
    for bk in sorted((seen & spawn) - white):
        R.err("blocks", "%s is a spawn condition (data/spawn_blocks.json) and no policy entry scoped to dune_ruin allows it" % bk)
    for bk in sorted(seen):
        if "chest" in bk or bk.endswith("_bed") or bk in ("minecraft:sand", "minecraft:red_sand", "minecraft:suspicious_sand"):
            R.err("blocks", "%s: no chests, no beds and no sand (data/dune_ruin.json blocks.rule)" % bk)


def support_of(k, s):
    """The cell that holds an attached block up, or None if it needs none."""
    x, y, z = k
    b = base(s)
    if b in ("minecraft:acacia_wall_sign", "minecraft:ladder"):
        dx, dy, dz = OPPOSITE[prop(s, "facing")]
        return (x + dx, y + dy, z + dz)
    if b in LIGHT:
        return (x, y + 1, z) if prop(s, "hanging") == "true" else (x, y - 1, z)
    if b in ("minecraft:red_carpet", "minecraft:brown_carpet", "minecraft:acacia_sign", "minecraft:acacia_fence"):
        return (x, y - 1, z)
    if b == TRAPDOOR:
        dx, dy, dz = OPPOSITE[prop(s, "facing")]
        return (x + dx, y + dy, z + dz)
    return None


def check_attached(rep, E, W, R):
    for k, s in sorted(rep.state.items()):
        b = base(s)
        sup = support_of(k, s)
        if sup is None:
            continue
        if b == TRAPDOOR:
            # a trapdoor needs nothing in 1.21, but it must sit in the floor it closes
            if not (W.solid((k[0] - 1, k[1], k[2])) or W.solid((k[0] + 1, k[1], k[2]))):
                R.err("attached", "the trapdoor at %s is not set in a floor" % (k,))
            continue
        ok = W.solid(sup) or (b in LIGHT and base(W.at(sup)) == "minecraft:chain")
        if not ok:
            R.err("attached", "%s at %s is held by %s, which is %s" % (b, k, sup, W.at(sup)))
        elif sup in rep.when and rep.when[sup] > rep.when[k]:
            R.err("attached", "%s at %s is written before what holds it up (%s): the server drops it" % (b, k, sup))
        if b == "minecraft:acacia_wall_sign":
            fx, fy, fz = OPPOSITE[prop(s, "facing")]
            front = (k[0] - fx, k[1] - fy, k[2] - fz)
            if not W.passable(front):
                R.err("attached", "the sign at %s faces %s, which is %s: nobody can read it" % (k, front, W.at(front)))


def light_map(W, sources, inside):
    """Block light: each source's level, one less per passable block, the brightest wins."""
    level = {}
    todo = deque()
    for k, v in sources:
        if level.get(k, 0) < v:
            level[k] = v
            todo.append(k)
    while todo:
        x, y, z = todo.popleft()
        v = level[(x, y, z)] - 1
        if v <= 0:
            continue
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            k = (x + dx, y + dy, z + dz)
            if inside(k) and W.passable(k) and level.get(k, 0) < v:
                level[k] = v
                todo.append(k)
    return level


def check_light(rep, E, W, R):
    srcs = [(k, LIGHT[base(s)]) for k, s in rep.state.items() if base(s) in LIGHT]
    for name, cells in (("hall", E.hall), ("stair-head room", E.ante), ("vault", E.room)):
        mine = [(k, v) for k, v in srcs if k in cells]
        if not mine:
            R.err("light", "the %s has no lantern" % name)
            continue
        lm = light_map(W, mine, lambda k: k in cells)  # noqa: B023
        dark = [k for k in cells if standing(W, k) and lm.get(k, 0) < 1]
        if dark:
            R.err("light", "%d standing place(s) in the %s at block light 0 (a hostile mob spawns), e.g. %s"
                  % (len(dark), name, sorted(dark)[0]))
    tx, tz, h, top = E.tower
    if not any(base(s) == "minecraft:lantern" and k[0] == tx and k[2] == tz and k[1] > top for k, s in rep.state.items()):
        R.err("light", "no lantern on the tower's top over y%d" % top)


def check_clear(rep, E, W, R):
    tags = {t: [] for t in CLEAR_TAGS}
    for tag, a, blk in rep.clears:
        if tag in tags and blk == "minecraft:air":
            tags[tag].append(a)
    cols = {}
    for (x, y, z) in rep.state:
        if y > W.ground(x, z):
            lo, hi = cols.get((x, z), (y, y))
            cols[(x, z)] = (min(lo, y), max(hi, y))
    for tag, boxes in tags.items():
        for (x, z), (lo, hi) in sorted(cols.items()):
            # the union of the boxes over this column (tools/function_limits.py splits a big fill into y slices)
            spans = sorted((min(b[1], b[4]), max(b[1], b[4])) for b in boxes
                           if min(b[0], b[3]) <= x <= max(b[0], b[3]) and min(b[2], b[5]) <= z <= max(b[2], b[5]))
            reach = W.ground(x, z)
            for a, b in spans:
                if a <= reach + 1:
                    reach = max(reach, b)
            if reach < hi + 2:
                R.err("clear", "column (%d, %d), written y%d..%d, is cleared of %s only to y%d, not y%d"
                      % (x, z, lo, hi, tag, reach, hi + 2))
                break


def check_find(rep, E, W, R, data=DATA):
    rid = E.rec["find"]["reward"]
    rw = [r for r in load_json("rewards.json", data)["rewards"] if r.get("id") == rid]
    if len(rw) != 1 or rw[0].get("kind") != "cache":
        R.err("find", "data/rewards.json has %d cache record(s) %s, not 1" % (len(rw), rid))
        return
    r = rw[0]
    at = tuple(r["container"]["at"])
    if at != E.barrel or r["container"]["block"] != "minecraft:barrel":
        R.err("find", "the cache's container is %s at %s, not a barrel at the record's %s" % (r["container"]["block"], at, E.barrel))
    if base(rep.state.get(E.barrel, "")) != "minecraft:barrel":
        R.err("find", "the build writes %s at the strongbox %s, not a barrel" % (rep.state.get(E.barrel), E.barrel))
    (x0, y0, z0), (x1, y1, z1) = r["trigger"]["min"], r["trigger"]["max"]
    box = [(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)]
    if any(k not in E.room for k in box):
        R.err("find", "the trigger box %s..%s reaches outside the vault" % (r["trigger"]["min"], r["trigger"]["max"]))
    if not any(standing(W, k) for k in box):
        R.err("find", "no standing place in the trigger box: nobody can earn the find")
    if not all(a - 1 <= v <= b + 1 for a, v, b in zip(r["trigger"]["min"], at, r["trigger"]["max"])):
        R.err("find", "the barrel %s is not beside the trigger box" % (at,))


def check_road(rep, E, W, R, data=DATA):
    rd = E.rec["road"]
    posts = sorted({(x, z) for (x, y, z), s in rep.state.items()
                    if not in_box(x, z, E.box) and base(s) == E.rec["blocks"]["ornament"]})
    if not posts:
        R.err("road", "no milestones outside the Khan")
        return
    fx, fz = rd["from"]
    gx, gz = E.cx, E.cz - E.H - 1
    posts.sort(key=lambda c: math.hypot(c[0] - fx, c[1] - fz))
    for x, z in posts:
        y = W.ground(x, z)
        for dy in (1, 2):
            if not W.solid((x, y + dy, z)) or (x, y + dy, z) not in rep.state:
                R.err("road", "the milestone at (%d, %d) is not solid at its own ground + %d (y%d)" % (x, z, dy, y + dy))
                return
        if (x, y + 3, z) in rep.state and base(rep.state[(x, y + 3, z)]) != "minecraft:lantern":
            R.err("road", "the milestone at (%d, %d) carries %s over its post" % (x, z, rep.state[(x, y + 3, z)]))
    lit = [c for c in posts if base(rep.state.get((c[0], W.ground(*c) + 3, c[1]), "")) == "minecraft:lantern"]
    if len(lit) < len(posts) // rd["lantern_every"]:
        R.err("road", "%d of %d milestones lit, fewer than one in %d" % (len(lit), len(posts), rd["lantern_every"]))
    gaps = [math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(posts, posts[1:])]
    if gaps and max(gaps) > rd["spacing"] + 2:
        R.err("road", "milestones %.0f blocks apart, over spacing %d + 2" % (max(gaps), rd["spacing"]))
    last = math.hypot(posts[-1][0] - gx, posts[-1][1] - gz)
    if last > rd["spacing"] + 2:
        R.err("road", "the last milestone is %.0f blocks from the gatehouse, over spacing %d" % (last, rd["spacing"]))
    first = posts[0]
    fp = next(t for t in load_json("towns.json", data)["towns"] if t["id"] == "mining_town")["footprint"]
    dx = max(fp["min_x"] - first[0], 0, first[0] - fp["max_x"])
    dz = max(fp["min_z"] - first[1], 0, first[1] - fp["max_z"])
    edge = math.hypot(dx, dz)
    if edge == 0 or edge > 32:
        R.err("road", "the first milestone %s is %.0f blocks from Fossick's footprint: it must stand outside it, within 32"
              % (first, edge))
    signed = [s for (x, y, z), s in rep.state.items() if base(s) == "minecraft:acacia_wall_sign"
              and math.hypot(x - first[0], z - first[1]) <= 1.5]
    if not signed:
        R.err("road", "the first milestone %s carries no sign" % (first,))
    R.note("road: %d milestones, %d lit, first %s (%.0f from Fossick's edge), last %.0f from the gatehouse"
           % (len(posts), len(lit), first, edge, last))


def check_npc(rep, E, W, R, placements=None, data=DATA):
    conv_id = E.rec["npc"]["conversation"]
    if placements is not None:
        if [tuple(p[1]) for p in placements] != [E.npc] or [p[0] for p in placements] != [conv_id]:
            R.err("npc", "the R18DU placement is %s, not %s at the record's spot %s" % (placements, conv_id, E.npc))
    x, y, z = E.npc
    if not (W.passable(E.npc) and W.passable((x, y + 1, z)) and W.solid((x, y - 1, z))):
        R.err("npc", "the salvager's spot %s is %s over %s, not two blocks of air on the floor"
              % (E.npc, W.at(E.npc), W.at((x, y - 1, z))))
    if E.npc not in E.hall:
        R.err("npc", "the salvager's spot %s is not in the hall" % (E.npc,))
    dl = load_json("dialogue.json", data)
    conv = next((c for c in dl["conversations"] if c["id"] == conv_id), None)
    if conv is None or not conv.get("npc_id"):
        R.err("npc", "no conversation %s with an NPC" % conv_id)
        return
    import compile_dialogue as CD
    try:
        _d, quests, fields = CD.load(data)
        CD.compile_conversation(conv, quests, fields)
    except SystemExit as e:
        R.err("npc", "the conversation does not compile: %s" % e)


def check_steps(rep, lines, steps, R):
    import function_limits
    bad = function_limits.check_lines(lines, "build")
    if bad:
        R.err("steps", "%d command(s) the server would refuse: %s" % (len(bad), bad[:2]))
    if rep.bad:
        R.err("steps", "%d line(s) this audit cannot read: %s" % (len(rep.bad), rep.bad[:2]))
    if steps is None:
        return
    kinds = [s[0] for s in steps]
    if ("fn", "cobblers:dune_ruin/build") not in [tuple(s) for s in steps]:
        R.err("steps", "the re-application does not run cobblers:dune_ruin/build")
    holds = [tuple(int(v) for v in s[1].split()[2:]) for s in steps if s[0] == "cmd" and s[1].startswith("forceload add")]
    if not holds or kinds[-1] != "cmd" or not steps[-1][1].startswith("forceload remove"):
        R.err("steps", "the re-application does not hold the chunks round the build and release them after")
        return
    for (x, _y, z) in rep.state:
        if not any(min(h[0], h[2]) <= x <= max(h[0], h[2]) and min(h[1], h[3]) <= z <= max(h[1], h[3]) for h in holds):
            R.err("steps", "(%d, %d) is written outside the re-application's forceload" % (x, z))
            return


def audit(rec, g, pack, steps=None, placements=None, data=DATA):
    R = Report()
    pack = Path(pack)
    fn = pack / FUNCTION
    if not fn.exists():
        R.err("steps", "no %s in %s: build the pack first" % (FUNCTION, pack))
        return R
    lines = fn.read_text(encoding="utf-8").splitlines()
    rep = Replay(lines)
    E = Expect(rec, g)
    W = World(rep, g)
    check_footprint(rep, E, W, R, data)
    check_drowned(rep, E, W, R)
    check_way_in(rep, E, W, R)
    check_vault(rep, E, W, R)
    check_habitat(rep, E, W, R, data)
    check_blocks(rep, E, R, data)
    check_attached(rep, E, W, R)
    check_light(rep, E, W, R)
    check_clear(rep, E, W, R)
    check_find(rep, E, W, R, data)
    check_road(rep, E, W, R, data)
    check_npc(rep, E, W, R, placements, data)
    check_steps(rep, lines, steps, R)
    R.note("sand line y%d, floor y%d, vault floor y%d, salvager at %s; %d cells written"
           % (E.S, E.F, E.vault_floor, E.npc, len(rep.state)))
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rec = load_json("dune_ruin.json")
    g = G.load(a.source_root)
    steps = placements = None
    try:
        import dune_ruin  # the re-application steps and the NPC placement are the generator's OUTPUT, checked here
        doc = dune_ruin.load()
        steps = dune_ruin.placement_steps(doc, g)
        placements = dune_ruin.npc_placements(doc, g)
    except ImportError:
        pass
    R = audit(rec, g, a.pack, steps, placements)
    for n in R.notes:
        print("note: %s" % n)
    for e in R.errors:
        print("PROBLEM %s" % e)
    print("dune_ruin_audit: %s (%d problem(s))" % ("clean" if not R.errors else "FAILED", len(R.errors)))
    return 1 if R.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
