#!/usr/bin/env python
"""The Old Orchard, audited offline: the emitted pack replayed block by block against the plan, re-derived.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/old_orchard.py. It
reads data/old_orchard.json, the canonical heightmap (tools/ground.py), data/resident_encounters.json (the resident's
anchor, trigger and leash, read there and not from the orchard's copy), data/habitat_blocks.json, data/spawns.json,
data/regions.json, data/rewards.json, data/dialogue.json, data/quests.json, data/spawn_blocks.json,
data/spawn_block_policy.json, data/placements.json, data/towns.json, data/route_paths.json and, when it can find it,
the Cobblemon jar (the evolution levels). It derives what it expects from them with its own arithmetic, then REPLAYS
the generated build function into a block model and compares. The only things taken from the generator are its
outputs (the pack, and the re-application steps it hands tools/reapply.py), which are what is being checked. Mutating
the generator (a row moved towards the sleeper, a cellar one block taller, a trapdoor left out, the find's barrel
moved, leaves that decay, a lantern hung before its post) fails a named check here with data/old_orchard.json
untouched; tests/test_old_orchard.py does exactly that.

What is checked, each from the data and the heightmap, never from the pack:

  resident   no write, and no clear, within max(4, resident.no_write_within) blocks of the resident's anchor column
             (data/resident_encounters.json); the keeper, the press-house door, the cellar room and the Habitat
             Block's spawn box all lie outside its leash (the resident's own build_brief)
  footprint  every write and every clear lies in the record's old_orchard_all box and outside every keep_out box
             (+ margin: the palm sapling, its companions, its dressing); the box is clear of every route leg
             (data/route_paths.json), every placement and town coordinate, by 16 blocks
  seat       the press-house floor is max(ground under the walls) + 1, solid wall to wall; every tree's first log is
             its own ground + 1, and a living tree's trunk is trunk logs high; hives, posts on their ground + 1
  cellar     the room is the record's (2 * interior_half + 1) square by air_height under the floor, its ceiling at or
             under the ground; with the trapdoor CLOSED a flood fill from the room never leaves it (sealed), and
             with it open the room reaches the press-house (the way in)
  find       data/rewards.json's cache for the record's reward: its barrel is written where the container says, in
             the room; its trigger box is inside the room and holds a place a player can stand; Leftovers in it
  habitat    the Habitat Block the record names: activated, its pool the record's, its position the second log of
             the record's (living) tree as derived here, written as an oak log; its pool is within the band of the
             sub-region it stands in, carries no species of the resident, and (with the jar) keeps the evolution
             policy: no stage above four past its own next level evolution, none below the level it evolves at,
             non-level evolutions only in the upper half of the band
  blocks     every written block is in blocks.ids; leaves are persistent; no chest and no bed; a spawn condition
             (data/spawn_blocks.json) only if the record allows it AND data/spawn_block_policy.json lists it
  attached   every sign, ladder, lantern, chain, plant, carpet and door is written after what holds it up, and what
             holds it up is solid; lanterns at every post, in the press-house and in the cellar
  clear      every written cell above ground + 1 lies in a clear of logs and leaves
  npc        the keeper's spot is two blocks of air on natural ground, outside every write; her conversation exists,
             compiles, and its quest lists it; the generator's npc step stands her there
  steps      the re-application holds every written chunk and runs the build; the function passes
             tools/function_limits.py

NOT checked, and it needs a running server: that the fills land, that Applin spawn round the tree, that the cache
grants, that the keeper renders and talks, and anything about the Slaking (another builder's).

  python tools/old_orchard_audit.py [--pack build/datapacks/cobblers_old_orchard] [--source-root R]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_old_orchard"
FUNCTION = "data/cobblers/function/old_orchard/build.mcfunction"
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*?)$")
FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$")
MIN_CLEARANCE = 4          # the common brief of 2026-10-02: no block within 4 of a resident's anchor
PASSABLE = {"minecraft:air", "minecraft:ladder", "minecraft:lantern", "minecraft:chain", "minecraft:oak_wall_sign",
            "minecraft:short_grass", "minecraft:fern", "minecraft:moss_carpet"}
TRAPDOOR = "minecraft:oak_trapdoor"
DOOR = "minecraft:oak_door"
PLANTS = {"minecraft:short_grass", "minecraft:fern", "minecraft:sweet_berry_bush", "minecraft:moss_carpet"}
BEHIND = {"north": (0, 0, 1), "south": (0, 0, -1), "east": (-1, 0, 0), "west": (1, 0, 0)}


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
                a = [int(v) for v in m.groups()[:6]]
                self.clears.append((m.group(8), a, base(m.group(7))))
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

    def passable(self, k, trapdoor_open=False, doors_open=False):
        b = base(self.at(k))
        if b in PASSABLE:
            return True
        if b == TRAPDOOR:
            return trapdoor_open
        if b == DOOR:
            return doors_open
        return False

    def solid(self, k):
        b = base(self.at(k))
        return not (b in PASSABLE or b in PLANTS or b == DOOR)


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


# --------------------------------------------------------------------------------------------- the expectations
class Expect:
    """What the records and the heightmap say, computed here."""

    def __init__(self, rec, g, data=DATA):
        self.rec = rec
        res = next(r for r in load_json("resident_encounters.json", data)["encounters"] if r["id"] == rec["resident"]["id"])
        self.anchor = (res["location"]["x"], res["location"]["z"])
        m = re.search(r"trigger (\d+), leash (\d+)", res.get("build_brief", ""))
        self.trigger, self.leash = (int(m.group(1)), int(m.group(2))) if m else (None, None)
        self.resident_species = res["species"].split(":")[-1]
        self.clearance = max(MIN_CLEARANCE, int(rec["resident"]["no_write_within"]))
        boxes = {b["id"]: b for b in rec["site"]["bounding_boxes"]}
        self.all = boxes["old_orchard_all"]
        km = rec["keep_out"]["margin"]
        self.keep_out = [(b["id"], b["min"][0] - km, b["min"][1] - km, b["max"][0] + km, b["max"][1] + km)
                         for b in rec["keep_out"]["boxes"]]
        ph = rec["press_house"]
        self.cx, self.cz = ph["centre"]
        self.h = ph["half"]
        self.hf = max(g(self.cx + a, self.cz + b) for a in range(-self.h, self.h + 1) for b in range(-self.h, self.h + 1)) + 1
        c = rec["cellar"]
        self.n, self.air = c["interior_half"], c["air_height"]
        self.ceiling_y = self.hf - 1
        self.floor_y = self.ceiling_y - self.air - 1
        self.room = {(self.cx + a, y, self.cz + b) for a in range(-self.n, self.n + 1) for b in range(-self.n, self.n + 1)
                     for y in range(self.floor_y + 1, self.ceiling_y)}
        o = rec["orchard"]
        self.trees = [(x, z) for z in o["rows_z"] for x in o["cols_x"]]
        self.kind = {}
        for k, lst in o["variants"].items():
            if k == "why":
                continue
            for z, x in lst:
                self.kind[(x, z)] = k
        hz, hx = rec["applin"]["tree"]
        self.habitat = (hx, g(hx, hz) + 2, hz)
        nx, nz = rec["npc"]["at"]
        self.npc = (nx, g(nx, nz) + 1, nz)
        self.door = (self.cx, self.hf + 1, self.cz + self.h)


def in_box(x, z, box):
    return box["min"][0] <= x <= box["max"][0] and box["min"][1] <= z <= box["max"][1]


def hdist(x, z, p):
    return math.hypot(x - p[0], z - p[1])


# --------------------------------------------------------------------------------------------- the checks
def check_resident(rep, E, R):
    bad = [k for k in rep.state if hdist(k[0], k[2], E.anchor) <= E.clearance]
    for tag, a, _st in rep.clears:
        x0, x1, z0, z1 = min(a[0], a[3]), max(a[0], a[3]), min(a[2], a[5]), max(a[2], a[5])
        nx, nz = min(max(E.anchor[0], x0), x1), min(max(E.anchor[1], z0), z1)
        if hdist(nx, nz, E.anchor) <= E.clearance:
            bad.append(("clear", tag, tuple(a)))
    if bad:
        R.err("resident", "%d write(s) within %d of the resident's anchor %s, e.g. %s"
              % (len(bad), E.clearance, E.anchor, bad[0]))
    if E.leash is None:
        R.err("resident", "the resident's build_brief names no 'trigger N, leash N'")
        return
    for what, (x, _y, z) in (("the keeper", E.npc), ("the press-house door", E.door)):
        if hdist(x, z, E.anchor) <= E.leash:
            R.err("resident", "%s at (%d, %d) is inside the resident's leash (%d)" % (what, x, z, E.leash))
    near = min(hdist(x, z, E.anchor) for x, _y, z in E.room)
    if near <= E.leash:
        R.err("resident", "the cellar room comes within %.1f of the resident, inside its leash (%d)" % (near, E.leash))


def check_footprint(rep, E, R, data=DATA):
    out = 0
    parts = [b for b in E.rec["site"]["bounding_boxes"] if b["id"] != "old_orchard_all"]
    for (x, y, z), s in rep.state.items():
        if not in_box(x, z, E.all):
            R.err("footprint", "(%d, %d, %d) %s is outside old_orchard_all" % (x, y, z, s))
            out += 1
        elif not any(in_box(x, z, b) for b in parts):
            R.err("footprint", "(%d, %d, %d) %s is in none of the record's feature boxes" % (x, y, z, s))
            out += 1
        for kid, x0, z0, x1, z1 in E.keep_out:
            if x0 <= x <= x1 and z0 <= z <= z1:
                R.err("footprint", "(%d, %d, %d) %s is in keep_out %s" % (x, y, z, s, kid))
                out += 1
        if out > 20:
            return
    for tag, a, _st in rep.clears:
        for x, z in ((a[0], a[2]), (a[3], a[5])):
            if not in_box(x, z, E.all):
                R.err("footprint", "a clear of %s reaches (%d, %d), outside old_orchard_all" % (tag, x, z))
    lo, hi = E.all["min"], E.all["max"]

    def box_dist(x, z):
        dx = max(lo[0] - x, 0, x - hi[0])
        dz = max(lo[1] - z, 0, z - hi[1])
        return math.hypot(dx, dz)
    paths = load_json("route_paths.json", data)["paths"]
    worst = min((box_dist(p[0], p[1]), name) for name, pts in paths.items() for p in pts)
    if worst[0] < 16:
        R.err("footprint", "route leg %s passes %.1f from the orchard's box" % (worst[1], worst[0]))
    R.note("nearest route leg: %s, %.0f blocks" % (worst[1], worst[0]))

    def pairs(o):
        if isinstance(o, dict):
            if isinstance(o.get("x"), (int, float)) and isinstance(o.get("z"), (int, float)):
                yield o["x"], o["z"]
            for v in o.values():
                yield from pairs(v)
        elif isinstance(o, list):
            if len(o) in (2, 3) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in o):
                yield (o[0], o[1]) if len(o) == 2 else (o[0], o[2])
            else:
                for v in o:
                    yield from pairs(v)
    for f in ("placements.json", "towns.json"):
        d = min(box_dist(x, z) for x, z in pairs(load_json(f, data)))
        if d < 16:
            R.err("footprint", "data/%s has a coordinate %.1f from the orchard's box" % (f, d))


def check_seat(rep, E, W, R):
    for a in range(-E.h, E.h + 1):
        for b in range(-E.h, E.h + 1):
            k = (E.cx + a, E.hf, E.cz + b)
            if not W.solid(k) and base(W.at(k)) != TRAPDOOR:
                R.err("seat", "the press-house floor at %s is %s" % (k, W.at(k)))
                return
    for a in range(-E.h, E.h + 1):
        for b in range(-E.h, E.h + 1):
            x, z = E.cx + a, E.cz + b
            if any(W.at((x, y, z)) == "minecraft:air" for y in range(W.ground(x, z) + 1, E.hf)):
                R.err("seat", "the press-house floor floats over (%d, %d)" % (x, z))
                return
    if (E.cx, E.hf + 1, E.cz + E.h + 1) not in rep.state and W.ground(E.cx, E.cz + E.h + 1) < E.hf - 1:
        R.err("seat", "nothing to step up to the door from")
    o = E.rec["orchard"]["tree"]
    for x, z in E.trees:
        y0 = W.ground(x, z) + 1
        if base(W.at((x, y0, z))) != "minecraft:oak_log":
            R.err("seat", "the tree at (%d, %d) has no log on its ground + 1 (y%d): %s" % (x, z, y0, W.at((x, y0, z))))
            continue
        kind = E.kind.get((x, z), "alive")
        if kind == "alive":
            for dy in range(o["trunk"]):
                if base(W.at((x, y0 + dy, z))) != "minecraft:oak_log" and (x, y0 + dy, z) != E.habitat:
                    R.err("seat", "the living tree at (%d, %d) has no log at y%d" % (x, z, y0 + dy))
            if base(W.at((x, y0 + o["trunk"], z))) != "minecraft:oak_leaves":
                R.err("seat", "the living tree at (%d, %d) has no crown over its trunk" % (x, z))
        if kind == "fallen" and not any(base(W.at((x + a, W.ground(x + a, z) + 1, z))) == "minecraft:oak_log"
                                        for a in range(2, 6)):
            R.err("seat", "the fallen tree at (%d, %d) has no trunk lying east of it" % (x, z))
    for x, z in E.rec["beehives"]["at"]:
        y = W.ground(x, z) + 1
        if base(W.at((x, y, z))) != "minecraft:oak_log" or base(W.at((x, y + 1, z))) != "minecraft:beehive":
            R.err("seat", "the hive at (%d, %d) is not a beehive on a log stand on its ground" % (x, z))


def check_cellar(rep, E, W, R):
    for k in E.room:
        if base(W.at(k)) not in PASSABLE | {"minecraft:barrel", "minecraft:cauldron"}:
            R.err("cellar", "the room's cell %s is %s" % (k, W.at(k)))
            return
    # nothing open in the room's columns under its floor or between its ceiling and the floor but the ladder shaft
    ladder = (E.cx - E.n, E.cz - E.n)
    for a in range(-E.n, E.n + 1):
        for b in range(-E.n, E.n + 1):
            x, z = E.cx + a, E.cz + b
            if not W.solid((x, E.floor_y, z)):
                R.err("cellar", "the floor at (%d, %d) is %s" % (x, z, W.at((x, E.floor_y, z))))
                return
            if (x, z) != ladder and not W.solid((x, E.ceiling_y, z)):
                R.err("cellar", "the room is taller than the record: (%d, %d, %d) is %s"
                      % (x, E.ceiling_y, z, W.at((x, E.ceiling_y, z))))
                return
    if E.ceiling_y > min(W.ground(x, z) for x, _y, z in E.room):
        R.err("cellar", "the ceiling y%d stands above the ground: not a cellar" % E.ceiling_y)
    start = (E.cx, E.floor_y + 1, E.cz)
    box = (E.cx - E.h - 3, E.cz - E.h - 3, E.cx + E.h + 3, E.cz + E.h + 3, E.floor_y - 3, E.hf + 4)

    def inside(k):
        return box[0] <= k[0] <= box[2] and box[1] <= k[2] <= box[3] and box[4] <= k[1] <= box[5]
    sealed = flood(W, start, inside)
    leak = [k for k in sealed if k not in E.room and not (k[0], k[2]) == ladder]
    if leak:
        R.err("cellar", "with the trapdoor shut the room is open to %s" % (sorted(leak)[0],))
    opened = flood(W, start, inside, trapdoor_open=True)
    if not any(k[1] == E.hf + 1 for k in opened):
        R.err("cellar", "with the trapdoor open the room does not reach the press-house floor")


def standing(W, k):
    x, y, z = k
    return W.passable(k) and W.passable((x, y + 1, z)) and W.solid((x, y - 1, z))


def check_find(rep, E, W, R, data=DATA):
    rid = E.rec["find"]["reward"]
    r = next((x for x in load_json("rewards.json", data)["rewards"] if x["id"] == rid), None)
    if r is None or r.get("kind") != "cache":
        R.err("find", "no cache %s in data/rewards.json" % rid)
        return
    at = tuple(r["container"]["at"])
    if base(W.at(at)) != base(r["container"]["block"]):
        R.err("find", "the container %s is %s, not %s" % (at, W.at(at), r["container"]["block"]))
    if at not in E.room:
        R.err("find", "the container %s is not in the cellar room" % (at,))
    lo, hi = r["trigger"]["min"], r["trigger"]["max"]
    cells = [(x, y, z) for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1) for z in range(lo[2], hi[2] + 1)]
    if any(k not in E.room for k in cells):
        R.err("find", "the trigger box reaches outside the cellar room")
    if not any(standing(W, k) for k in cells):
        R.err("find", "nowhere in the trigger box can a player stand")
    if "cobblemon:leftovers" not in [c["item"] for c in r["contents"]]:
        R.err("find", "the cache holds no Leftovers")


def _sub_band(x, z, data=DATA):
    reg = load_json("regions.json", data)

    def inp(poly):
        c, j = False, len(poly) - 1
        for i in range(len(poly)):
            xi, zi = poly[i]
            xj, zj = poly[j]
            if ((zi > z) != (zj > z)) and x < (xj - xi) * (z - zi) / float(zj - zi) + xi:
                c = not c
            j = i
        return c
    sub = next((s["id"] for s in reg["subregions"] if any(inp(p) for p in s.get("polygons") or [])), None)
    sp = load_json("spawns.json", data)
    band = next((s["level_band"] for s in sp["subregions"] if s["id"] == sub), None)
    return sub, band


def _jar_evolutions():
    """{species: (pre-evolution or None, the level it evolves FROM its pre at or None, next level evolution or None,
    has a non-level evolution into it)} from the Cobblemon jar, or None if no jar is found."""
    try:
        import battle_sim
        jar = battle_sim.find_jar()
    except battle_sim.SimError:                   # no jar on this machine: the caller reports the check as not run
        return None
    z = zipfile.ZipFile(jar)
    nxt, pre = {}, {}
    for n in z.namelist():
        if not (n.startswith("data/cobblemon/species/") and n.endswith(".json")):
            continue
        sp = n.rsplit("/", 1)[1][:-5]
        d = json.loads(z.read(n))
        for e in d.get("evolutions") or []:
            res = (e.get("result") or "").split(" ")[0]
            lv = next((q.get("minLevel") for q in e.get("requirements") or [] if q.get("variant") == "level"), None)
            if lv is not None:
                nxt[sp] = min(nxt.get(sp, 999), lv)
            pre[res] = (sp, lv)
    return nxt, pre


def check_habitat(rep, E, W, R, data=DATA):
    rec = E.rec
    hb = {b["id"]: b for b in load_json("habitat_blocks.json", data)["blocks"]}
    b = hb.get(rec["applin"]["block"])
    if b is None:
        R.err("habitat", "no Habitat Block %s in data/habitat_blocks.json" % rec["applin"]["block"])
        return
    pos = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
    if b.get("style") != "activated" or b.get("replace_spawns") is not False:
        R.err("habitat", "%s is not an activated block without ReplaceSpawns" % b["id"])
    if b.get("pool") != "cobblers:%s" % rec["applin"]["habitat"]:
        R.err("habitat", "%s's pool is %s, not cobblers:%s" % (b["id"], b.get("pool"), rec["applin"]["habitat"]))
    if pos != E.habitat:
        R.err("habitat", "%s stands at %s, not the tree's second log %s" % (b["id"], pos, E.habitat))
    if E.kind.get((E.habitat[0], E.habitat[2]), "alive") != "alive":
        R.err("habitat", "the Habitat Block's tree is not a living one")
    if base(W.at(E.habitat)) != "minecraft:oak_log" or b.get("mimic") != "minecraft:oak_log":
        R.err("habitat", "the build writes %s at the block and its mimic is %s: not one log in the trunk"
              % (W.at(E.habitat), b.get("mimic")))
    r = int((b.get("activated") or {}).get("spawn_range", 0))
    nx = min(max(E.anchor[0], pos[0] - r), pos[0] + r)
    nz = min(max(E.anchor[1], pos[2] - r), pos[2] + r)
    if E.leash is not None and hdist(nx, nz, E.anchor) <= E.leash:
        R.err("habitat", "the spawn box reaches within %.1f of the resident, inside its leash" % hdist(nx, nz, E.anchor))
    sub, band = _sub_band(pos[0], pos[2], data)
    hab = next((h for h in load_json("spawns.json", data)["habitats"] if h["id"] == rec["applin"]["habitat"]), None)
    if hab is None or band is None:
        R.err("habitat", "no habitat pool %s, or no band for its sub-region %s" % (rec["applin"]["habitat"], sub))
        return
    lo, hi = band["minimum"], band["maximum"]
    if not (lo <= hab["level_band"]["minimum"] and hab["level_band"]["maximum"] <= hi):
        R.err("habitat", "the pool's band %s is not inside %s's %d-%d" % (hab["level_band"], sub, lo, hi))
    ev = _jar_evolutions()
    if ev is None:
        R.note("habitat: no Cobblemon jar found; the evolution policy was not checked")
    for e in hab["entries"]:
        a, z2 = (int(v) for v in e["level"].split("-"))
        if not (lo <= a <= z2 <= hi):
            R.err("habitat", "%s %s is outside %s's band %d-%d" % (e["pokemon"], e["level"], sub, lo, hi))
        if e["pokemon"] == E.resident_species:
            R.err("habitat", "the pool carries %s, the resident's own species" % e["pokemon"])
        if ev is None:
            continue
        nxt, pre = ev
        if e["pokemon"] in nxt and z2 > nxt[e["pokemon"]] + 4:
            R.err("habitat", "%s spawns to %d, past four over its evolution at %d" % (e["pokemon"], z2, nxt[e["pokemon"]]))
        if e["pokemon"] in pre:
            _p, lv = pre[e["pokemon"]]
            if lv is not None and a < lv:
                R.err("habitat", "%s spawns from %d, under the level %d it evolves at" % (e["pokemon"], a, lv))
            if lv is None and a < (lo + hi + 1) // 2:
                R.err("habitat", "%s is a non-level evolution spawning from %d, under the band's upper half"
                      % (e["pokemon"], a))


def check_blocks(rep, E, R, data=DATA):
    allowed = set(E.rec["blocks"]["ids"])
    cond = load_json("spawn_blocks.json", data)["blocks"]
    ok = set(E.rec["blocks"].get("spawn_conditions_allowed") or {})
    listed = set()

    def walk(o):                                   # every block any policy entry names
        if isinstance(o, dict):
            for b in o.get("blocks") or []:
                if isinstance(b, str):
                    listed.add(b)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(load_json("spawn_block_policy.json", data))
    seen = set()
    decays = None
    for k, s in rep.state.items():
        b = base(s)
        if b == "minecraft:oak_leaves" and prop(s, "persistent") != "true" and decays is None:
            decays = k
        if b in seen:
            continue
        seen.add(b)
        if b not in allowed:
            R.err("blocks", "%s at %s is not in blocks.ids" % (b, k))
        if b.endswith("_bed") or b in ("minecraft:chest", "minecraft:trapped_chest"):
            R.err("blocks", "%s at %s: no chests and no beds" % (b, k))
        if b in cond and not (b in ok and b in listed):
            R.err("blocks", "%s at %s is a spawn condition (%s) the record or the policy does not allow"
                  % (b, k, cond[b][0]))
    if decays is not None:
        R.err("blocks", "the leaves at %s are not persistent: they decay" % (decays,))


def support_of(k, s):
    x, y, z = k
    b = base(s)
    if b == "minecraft:lantern":
        return (x, y + 1, z) if prop(s, "hanging") == "true" else (x, y - 1, z)
    if b == "minecraft:chain":
        return (x, y + 1, z)
    if b in ("minecraft:oak_wall_sign", "minecraft:ladder"):
        d = BEHIND[prop(s, "facing")]
        return (x + d[0], y, z + d[2])
    if b in PLANTS or (b == DOOR and prop(s, "half") == "lower"):
        return (x, y - 1, z)
    if b == DOOR:
        return (x, y - 1, z)
    return None


def check_attached(rep, E, W, R):
    lanterns = [k for k, s in rep.state.items() if base(s) == "minecraft:lantern"]
    for k, s in rep.state.items():
        sup = support_of(k, s)
        if sup is None:
            continue
        sb = W.at(sup)
        if base(sb) == "minecraft:air" or (base(sb) in PLANTS):
            R.err("attached", "%s at %s hangs on %s at %s" % (base(s), k, sb, sup))
            continue
        if sup in rep.when and rep.when[sup] > rep.when[k]:
            R.err("attached", "%s at %s is written before what holds it (%s at %s)" % (base(s), k, base(sb), sup))
    for x, z in E.rec["lantern_posts"]["at"]:
        y = W.ground(x, z) + 3
        if base(W.at((x, y, z))) != "minecraft:lantern":
            R.err("attached", "no lantern on the post at (%d, %d)" % (x, z))
    if not any(k in E.room for k in lanterns):
        R.err("attached", "the cellar has no lantern")
    if not any(abs(k[0] - E.cx) < E.h and abs(k[2] - E.cz) < E.h and k[1] > E.hf for k in lanterns):
        R.err("attached", "the press-house has no lantern")


def check_clear(rep, E, W, R):
    boxes = {}
    for tag, a, _st in rep.clears:
        boxes.setdefault(tag, []).append(a)
    for k, s in rep.state.items():
        x, y, z = k
        if base(s) == "minecraft:air" or y <= W.ground(x, z) + 1:
            continue
        for tag in ("#minecraft:logs", "#minecraft:leaves"):
            if not any(min(b[0], b[3]) <= x <= max(b[0], b[3]) and min(b[1], b[4]) <= y <= max(b[1], b[4])
                       and min(b[2], b[5]) <= z <= max(b[2], b[5]) for b in boxes.get(tag, [])):
                R.err("clear", "%s at %s is written into a cell never cleared of %s" % (base(s), k, tag))
                return


def check_npc(rep, E, W, R, npcs=None, data=DATA):
    x, y, z = E.npc
    if not (W.at(E.npc) == "minecraft:air" and W.at((x, y + 1, z)) == "minecraft:air"
            and W.at((x, y - 1, z)) == "natural:ground"):
        R.err("npc", "the keeper's spot %s is %s over %s, not two blocks of air on the ground"
              % (E.npc, W.at(E.npc), W.at((x, y - 1, z))))
    dl = load_json("dialogue.json", data)
    conv = next((c for c in dl["conversations"] if c["id"] == E.rec["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        R.err("npc", "no conversation %s with an NPC" % E.rec["npc"]["conversation"])
        return
    quest = next((q for q in load_json("quests.json", data)["quests"] if q["id"] == conv.get("quest_id")), None)
    if quest is None or conv["id"] not in (quest.get("dialogue_ids") or [quest.get("dialogue_id")]):
        R.err("npc", "the conversation's quest %s does not list it" % conv.get("quest_id"))
    import compile_dialogue as CD
    try:
        _d, quests, fields = CD.load(data)
        CD.compile_conversation(conv, quests, fields)
    except SystemExit as e:
        R.err("npc", "the conversation does not compile: %s" % e)
    if not any("cellar" in (n.get("text") or "").lower() for n in conv["nodes"]):
        R.err("npc", "the keeper's talk never points at the cellar")
    if npcs is not None:
        want = (conv["id"], E.npc, "%s:%s" % (E.rec["namespace"], conv["npc_id"]))
        if [(n[0], tuple(n[1]), n[2]) for n in npcs] != [want]:
            R.err("npc", "the npc step %s does not stand %s at %s" % (npcs, conv["npc_id"], E.npc))


def check_steps(rep, lines, steps, R):
    import function_limits
    bad = function_limits.check_lines(lines, "build")
    if bad:
        R.err("steps", "%d command(s) the server would refuse: %s" % (len(bad), bad[:2]))
    if steps is None:
        return
    fns = [s[1] for s in steps if s[0] == "fn"]
    if fns != ["cobblers:old_orchard/build"]:
        R.err("steps", "the steps run %s, not cobblers:old_orchard/build" % fns)
    held = []
    for s in steps:
        if s[0] == "cmd" and s[1].startswith("forceload add "):
            held.append(tuple(int(v) for v in s[1].split()[2:]))
    held += rep.loads
    for (x, _y, z) in rep.state:
        if not any(min(b[0], b[2]) // 16 <= x // 16 <= max(b[0], b[2]) // 16
                   and min(b[1], b[3]) // 16 <= z // 16 <= max(b[1], b[3]) // 16 for b in held):
            R.err("steps", "the write at (%d, %d) is in a chunk nothing holds" % (x, z))
            return


def audit(rec, g, pack, steps=None, npcs=None, data=DATA):
    R = Report()
    f = Path(pack) / FUNCTION
    if not f.is_file():
        R.err("pack", "no %s" % f)
        return R
    lines = f.read_text(encoding="utf-8").splitlines()
    rep = Replay(lines)
    for b in rep.bad[:3]:
        R.err("pack", "a command the replay does not know: %s" % b)
    E = Expect(rec, g, data)
    W = World(rep, g)
    check_resident(rep, E, R)
    check_footprint(rep, E, R, data)
    check_seat(rep, E, W, R)
    check_cellar(rep, E, W, R)
    check_find(rep, E, W, R, data)
    check_habitat(rep, E, W, R, data)
    check_blocks(rep, E, R, data)
    check_attached(rep, E, W, R)
    check_clear(rep, E, W, R)
    check_npc(rep, E, W, R, npcs, data)
    check_steps(rep, lines, steps, R)
    R.note("%d cells written, %d clears; press-house floor y%d, cellar floor y%d; nearest write to the resident %.1f"
           % (len(rep.state), len(rep.clears), E.hf, E.floor_y,
              min(hdist(k[0], k[2], E.anchor) for k in rep.state) if rep.state else -1))
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--data", default=str(DATA / "old_orchard.json"))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rec = json.loads(Path(a.data).read_text(encoding="utf-8"))
    g = G.load(a.source_root)
    import old_orchard  # the re-application steps are the generator's OUTPUT, checked here, never its geometry
    rep = audit(rec, g, a.pack, old_orchard.placement_steps(), old_orchard.npc_placements(None, g))
    for n in rep.notes:
        print("note: " + n)
    for e in rep.errors:
        print("PROBLEM " + e)
    print("old_orchard_audit: %s (%d problems)" % ("clean" if not rep.errors else "FAILED", len(rep.errors)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
