#!/usr/bin/env python
"""The Lopunny superfan's house, audited offline: the emitted pack replayed block by block against the plan, re-derived.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/lopunny_house.py. It
reads data/lopunny_house.json, the canonical heightmap (tools/ground.py), data/habitat_blocks.json, data/spawns.json,
data/regions.json, data/rewards.json, data/quests.json, data/dialogue.json, data/spawn_blocks.json and
data/spawn_block_policy.json, derives what it expects from them with its own arithmetic, then REPLAYS the generated
build function into a block model and compares. The only things taken from the generator are its outputs (the pack,
and the re-application steps it hands tools/reapply.py), which are what is being checked. Mutating the generator (a
cellar one block taller, a gap in its wall, a trapdoor left out, a sign placed before its wall, a callback that looks
for the wrong species) fails a named check here with data/lopunny_house.json untouched; tests/test_lopunny_house.py
does exactly that.

What is checked, each from the data and the heightmap, never from the pack:

  footprint  no write lands outside the site: the house's box (walls, overhang, roof, ears, step and door sign), the
             yard in front of it, and the statue's box; nothing below ground but the cellar's columns
  seat       the house floor is max(ground under the walls) + 1 and solid wall to wall; the statue's plinth is
             max(ground under it) + 1 with no air under it
  cellar     the room is the record's 9 by 9 by air_height under the floor, its floor the record's floor block, its
             ceiling at or under the ground; with the trapdoor CLOSED a flood fill from the room never leaves it
             (sealed), and with it open the room reaches the house and the open air (the way in)
  habitat    the Habitat Block the record names: activated, its pool the record's, its position the cellar floor's
             centre (as derived here), its mimic the floor block, which the build writes there. Its spawn box (a cube
             of spawn_range round the block, ActivatedHabitatSpawning) holds standing places for at least max_spawns
             Buneary and NONE outside the room; its cancel sphere takes in the whole room and no ground outside the
             walls. The pool is Buneary alone, within the band of the sub-region the house stands in
  blocks     every written block is in blocks.ids; none is a spawn condition (data/spawn_blocks.json) unless a policy
             entry scoped to lopunny_house allows it; no chest and no bed
  attached   every sign, banner, ladder, lantern, candle, carpet and door is written after what holds it up, and
             what holds it up is solid; the room and the cellar each have a light
  clear      the trees, leaves and replaceable plants are cleared over every column written above the ground
  npc        data/rewards.json's npc_grant for the quest stands on the house floor at the record's spot, two blocks of
             air, not on the trapdoor; its conversation exists and compiles
  check      the pack's player_tick_pre callback (Cobblemon's namespace: EXP-042 found ours never fires) reads the
             party, names the species the record names through a t. variable, adds AND removes the one tag, and that
             tag is the one the conversation's option and the quest's show transition read
  steps      the re-application holds every written chunk, runs the build, releases; the function passes
             tools/function_limits.py

NOT checked, and it needs a running server (experiments/EXP-052-lopunny-show): that the fills land, that Buneary
spawn in the room and stay in it, that the callback fires and tags, that the option appears, that the bell is given.

  python tools/lopunny_house_audit.py [--pack build/datapacks/cobblers_lopunny_house] [--source-root R]
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
PACK = ROOT / "build" / "datapacks" / "cobblers_lopunny_house"
FUNCTION = "data/cobblers/function/lopunny_house/build.mcfunction"
CALLBACK_DIR = "data/cobblemon/callbacks/player_tick_pre"
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*?)(?: replace)?$")
FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$")
# a block a body passes through (air, and what hangs in it); a closed trapdoor and a door are their own cases
PASSABLE = {"minecraft:air", "minecraft:ladder", "minecraft:lantern", "minecraft:chain", "minecraft:spruce_wall_sign",
            "minecraft:brown_wall_banner", "minecraft:white_wall_banner", "minecraft:red_carpet",
            "minecraft:brown_carpet", "minecraft:brown_candle"}
TRAPDOOR = "minecraft:spruce_trapdoor"
DOOR = "minecraft:spruce_door"
OPPOSITE = {"north": (0, 0, 1), "south": (0, 0, -1), "east": (-1, 0, 0), "west": (1, 0, 0)}


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
        return not (b in PASSABLE or b == DOOR)


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
    """What the record and the heightmap say, computed here."""

    def __init__(self, rec, g):
        self.rec = rec
        self.cx, self.cz = rec["site"]["centre"]
        h = self.h = rec["house"]["half"]
        self.n = rec["cellar"]["interior_half"]
        self.air = rec["cellar"]["air_height"]
        self.under = rec["cellar"]["under_fill"]
        self.hf = max(g(self.cx + a, self.cz + b) for a in range(-h, h + 1) for b in range(-h, h + 1)) + 1
        self.floor_y = self.hf - 1 - self.air - 1          # ceiling at hf-1, air under it, the floor under the air
        self.ceiling_y = self.hf - 1
        self.room = {(self.cx + a, y, self.cz + b) for a in range(-self.n, self.n + 1) for b in range(-self.n, self.n + 1)
                     for y in range(self.floor_y + 1, self.ceiling_y)}
        over = rec["house"]["roof_overhang"]
        self.house_box = (self.cx - h - over, self.cz - h - over, self.cx + h + over, self.cz + h + over)
        self.roof_top = self.hf + rec["house"]["wall_height"] + 1 + (h + over) + 5    # ridge + the ears
        sx, sz = rec["obsession"]["statue"]["at_local"]
        self.statue_cols = [(self.cx + sx + a, self.cz + sz + b) for a in range(-2, 3) for b in range(-1, 2)]
        self.plinth_cols = [(self.cx + sx + a, self.cz + sz + b) for a in (-1, 0, 1) for b in (-1, 0, 1)]
        self.statue_floor = max(g(x, z) for x, z in self.statue_cols) + 1
        self.statue_box = (self.cx + sx - 2, self.cz + sz - 1, self.cx + sx + 2, self.cz + sz + 2)
        self.yard_box = (self.cx - h - over, self.cz + h + 1, self.cx + h + over, self.cz + sz + 2)
        nx, nz = rec["npc"]["at_local"]
        self.npc = (self.cx + nx, self.hf + 1, self.cz + nz)


def in_box(x, z, box):
    return box[0] <= x <= box[2] and box[1] <= z <= box[3]


# --------------------------------------------------------------------------------------------- the checks
def check_footprint(rep, E, W, R):
    out = 0
    for (x, y, z), s in rep.state.items():
        if in_box(x, z, E.house_box):
            low = E.floor_y - E.under
            if not (low <= y <= E.roof_top):
                R.err("footprint", "(%d, %d, %d) %s is outside the house's height range y%d..%d" % (x, y, z, s, low, E.roof_top))
                out += 1
            elif y < E.hf - 1 and not (abs(x - E.cx) <= E.n + 1 and abs(z - E.cz) <= E.n + 1):
                R.err("footprint", "(%d, %d, %d) %s is below ground outside the cellar's columns" % (x, y, z, s))
                out += 1
        elif in_box(x, z, E.statue_box):
            if not (W.ground(x, z) - 0 <= y <= E.statue_floor + 9):
                R.err("footprint", "(%d, %d, %d) %s is outside the statue's height range" % (x, y, z, s))
                out += 1
        elif in_box(x, z, E.yard_box):
            if y != W.ground(x, z) and y > E.hf:
                R.err("footprint", "(%d, %d, %d) %s stands in the yard above the step" % (x, y, z, s))
                out += 1
        else:
            R.err("footprint", "(%d, %d, %d) %s is outside the site" % (x, y, z, s))
            out += 1
        if out > 20:
            return


def check_seat(rep, E, W, R):
    h = E.h
    for a in range(-h, h + 1):
        for b in range(-h, h + 1):
            k = (E.cx + a, E.hf, E.cz + b)
            s = rep.state.get(k)
            if s is None or not (W.solid(k) or base(s) == TRAPDOOR):
                R.err("seat", "the house floor at %s is %s, not a solid floor at y%d (max ground under the walls + 1)"
                      % (k[::2], s, E.hf))
                return
    for x, z in E.plinth_cols:
        k = (x, E.statue_floor, z)
        if base(rep.state.get(k, "")) != "minecraft:polished_andesite":
            R.err("seat", "the statue's plinth at %s is %s, not at y%d (max ground under it + 1)"
                  % ((x, z), rep.state.get(k), E.statue_floor))
            return
        for y in range(W.ground(x, z) + 1, E.statue_floor):
            if not W.solid((x, y, z)):
                R.err("seat", "air under the statue's plinth at (%d, %d, %d)" % (x, y, z))
                return


def check_cellar(rep, E, W, R):
    floor_block = E.rec["blocks"]["cellar_floor"]
    for a in range(-E.n, E.n + 1):
        for b in range(-E.n, E.n + 1):
            x, z = E.cx + a, E.cz + b
            if base(rep.state.get((x, E.floor_y, z), "")) != floor_block:
                R.err("cellar", "the floor at (%d, %d, %d) is %s, not %s" % (x, E.floor_y, z, rep.state.get((x, E.floor_y, z)), floor_block))
                return
            if E.ceiling_y > W.ground(x, z):
                R.err("cellar", "the ceiling at (%d, %d) is y%d, over the ground y%d: the cellar stands out of the ground"
                      % (x, z, E.ceiling_y, W.ground(x, z)))
                return
    open_ = [k for k in E.room if W.passable(k)]
    if len(open_) < 0.6 * len(E.room):
        R.err("cellar", "only %d of the room's %d cells are open" % (len(open_), len(E.room)))
        return
    # the room's height: nothing open in the room's columns over the ceiling or under the floor but the ladder shaft
    for a in range(-E.n, E.n + 1):
        for b in range(-E.n, E.n + 1):
            for y in (E.floor_y, E.floor_y - 1, E.ceiling_y + 1):
                k = (E.cx + a, y, E.cz + b)
                if y != E.ceiling_y + 1 and W.passable(k):
                    R.err("cellar", "open cell %s outside the room's %d blocks of air" % (k, E.air))
                    return
            k = (E.cx + a, E.ceiling_y, E.cz + b)
            if W.passable(k) and base(W.at(k)) != "minecraft:ladder":
                R.err("cellar", "the ceiling at %s is open (%s): the room is taller than the record's %d"
                      % (k, W.at(k), E.air))
                return
    start = sorted(open_)[0]
    lo = (E.cx - E.h - 8, E.floor_y - E.under - 2, E.cz - E.h - 8)
    hi = (E.cx + E.h + 8, E.roof_top + 2, E.cz + E.h + 14)
    inside = lambda k: all(lo[i] <= k[i] <= hi[i] for i in range(3))  # noqa: E731
    sealed = flood(W, start, inside)
    shaft_top = E.ceiling_y
    leak = [k for k in sealed if k not in E.room and not (k[1] == shaft_top and base(W.at(k)) == "minecraft:ladder")]
    if leak:
        R.err("cellar", "with the trapdoor closed the room is open to %d cell(s) outside it, e.g. %s" % (len(leak), sorted(leak)[0]))
    reach = flood(W, start, inside, trapdoor_open=True, doors_open=True)
    room_floor = [k for k in reach if k[1] == E.hf + 1 and abs(k[0] - E.cx) < E.h and abs(k[2] - E.cz) < E.h]
    outdoors = [k for k in reach if not in_box(k[0], k[2], E.house_box) and k[1] > W.ground(k[0], k[2])]
    if not room_floor:
        R.err("cellar", "with the trapdoor open the cellar does not reach the house's room: no way in")
    elif not outdoors:
        R.err("cellar", "the house's door does not open to the outside")
    R.note("cellar: room %d cells (%d open), sealed fill %d cells, floor y%d, ceiling y%d"
           % (len(E.room), len(open_), len(sealed), E.floor_y, E.ceiling_y))


def standing(W, k):
    x, y, z = k
    below = W.at((x, y - 1, z))
    return (W.passable(k) and W.passable((x, y + 1, z))
            and (W.solid((x, y - 1, z)) or base(below) == TRAPDOOR))


def check_habitat(rep, E, W, R, data=DATA):
    rec = E.rec
    hb = {b["id"]: b for b in load_json("habitat_blocks.json", data)["blocks"]}
    b = hb.get(rec["buneary"]["block"])
    if b is None:
        R.err("habitat", "no Habitat Block %s in data/habitat_blocks.json" % rec["buneary"]["block"])
        return
    want = (E.cx, E.floor_y, E.cz)
    pos = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
    a = b.get("activated") or {}
    if b.get("style") != "activated" or b.get("replace_spawns") is not False:
        R.err("habitat", "%s is not an activated block without ReplaceSpawns" % b["id"])
    if b.get("pool") != "cobblers:%s" % rec["buneary"]["habitat"]:
        R.err("habitat", "%s's pool is %s, not cobblers:%s" % (b["id"], b.get("pool"), rec["buneary"]["habitat"]))
    if pos != want:
        R.err("habitat", "%s stands at %s, not the cellar floor's centre %s" % (b["id"], pos, want))
    if b.get("mimic") != rec["blocks"]["cellar_floor"]:
        R.err("habitat", "%s mimics %s, not the cellar floor %s" % (b["id"], b.get("mimic"), rec["blocks"]["cellar_floor"]))
    if base(rep.state.get(pos, "")) != rec["blocks"]["cellar_floor"]:
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
        R.err("habitat", "the spawn box (spawn_range %d) holds %d standing place(s) outside the cellar, e.g. %s"
              % (r, len(stray), sorted(stray)[0]))
    inroom = [k for k in places if k in E.room]
    if len(inroom) < a["max_spawns"]:
        R.err("habitat", "the spawn box holds %d standing places in the room, fewer than max_spawns %d"
              % (len(inroom), a["max_spawns"]))
    c = a.get("cancel_range")
    if isinstance(c, int) and c > 0:
        far = max(math.dist(pos, k) for k in E.room)
        if far > c:
            R.err("habitat", "cancel_range %d does not take in the room (its far cell is %.1f away)" % (c, far))
        for dx in range(-c - 1, c + 2):
            for dz in range(-c - 1, c + 2):
                x, z = pos[0] + dx, pos[2] + dz
                if abs(x - E.cx) <= E.h and abs(z - E.cz) <= E.h:
                    continue
                k = (x, W.ground(x, z) + 1, z)
                if math.dist(pos, k) <= c:
                    R.err("habitat", "cancel_range %d reaches the ground outside the walls at %s" % (c, k))
                    return
    R.note("habitat: %s at %s, box %d standing places, all in the room" % (b["id"], pos, len(inroom)))
    # the pool
    sp = load_json("spawns.json", data)
    hab = next((h for h in sp["habitats"] if h["id"] == rec["buneary"]["habitat"]), None)
    if hab is None:
        R.err("habitat", "no habitat %s in data/spawns.json" % rec["buneary"]["habitat"])
        return
    species = {e["pokemon"] for e in hab["entries"]}
    if species != {"buneary"}:
        R.err("habitat", "the pool holds %s, not Buneary alone" % sorted(species))
    entries = [e for e in sp["entries"] if e.get("scope") == hab["id"] and e.get("mechanism") == "habitat_block"]
    if [e["species"] for e in entries] != ["buneary"] or entries[0].get("spawnable_position") != "grounded":
        R.err("habitat", "the pool's spawn entries are %s, not one grounded Buneary" % [e.get("id") for e in entries])
    sub = subregion_at(E.cx, E.cz, data)
    band = next((s["level_band"] for s in sp["subregions"] if s["id"] == sub), None)
    if band is None:
        R.err("habitat", "the house stands in no sub-region with a level band (%s)" % sub)
        return
    for e in list(hab["entries"]) + entries:
        lo, hi = (int(v) for v in e["level"].split("-"))
        if lo < band["minimum"] or hi > band["maximum"]:
            R.err("habitat", "%s levels %s are outside %s's band %d-%d" % (e.get("id", e.get("species")), e["level"], sub,
                                                                          band["minimum"], band["maximum"]))


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


def check_blocks(rep, E, R, data=DATA):
    allowed = set(E.rec["blocks"]["ids"])
    spawn = set(load_json("spawn_blocks.json", data)["blocks"])
    policy = load_json("spawn_block_policy.json", data)
    white = {bk for w in policy.get("whitelist") or [] if "lopunny_house" in (w.get("scope") or "") for bk in w["blocks"]}
    seen = {base(s) for s in rep.state.values()}
    for bk in sorted(seen - allowed):
        R.err("blocks", "%s is written and is not in data/lopunny_house.json blocks.ids" % bk)
    for bk in sorted((seen & spawn) - white):
        R.err("blocks", "%s is a spawn condition (data/spawn_blocks.json) and no policy entry scoped to lopunny_house allows it" % bk)
    for bk in sorted(seen):
        if "chest" in bk or bk.endswith("_bed"):
            R.err("blocks", "%s: no chests and no beds (data/lopunny_house.json blocks.rule)" % bk)


def support_of(k, s):
    """The cell that holds an attached block up, or None if it needs none."""
    x, y, z = k
    b = base(s)
    if b in ("minecraft:spruce_wall_sign", "minecraft:brown_wall_banner", "minecraft:white_wall_banner", "minecraft:ladder"):
        dx, dy, dz = OPPOSITE[prop(s, "facing")]
        return (x + dx, y + dy, z + dz)
    if b == "minecraft:lantern":
        return (x, y + 1, z) if prop(s, "hanging") == "true" else (x, y - 1, z)
    if b in ("minecraft:red_carpet", "minecraft:brown_carpet", "minecraft:brown_candle"):
        return (x, y - 1, z)
    if b == DOOR:
        return (x, y - 1, z) if prop(s, "half") == "lower" else None
    return None


def check_attached(rep, E, W, R):
    lights = {"room": 0, "cellar": 0}
    for k, s in rep.state.items():
        b = base(s)
        if b == "minecraft:lantern":
            if k in E.room:
                lights["cellar"] += 1
            elif abs(k[0] - E.cx) < E.h and abs(k[2] - E.cz) < E.h and k[1] > E.hf:
                lights["room"] += 1
        sup = support_of(k, s)
        if b == DOOR and prop(s, "half") == "upper":
            low = (k[0], k[1] - 1, k[2])
            if base(rep.state.get(low, "")) != DOOR or rep.when.get(low, 10 ** 9) > rep.when[k]:
                R.err("attached", "the door's upper half at %s has no lower half written before it" % (k,))
            continue
        if sup is None:
            continue
        ok = W.solid(sup) or (b == "minecraft:lantern" and base(W.at(sup)) == "minecraft:chain")
        if not ok:
            R.err("attached", "%s at %s is held by %s, which is %s" % (b, k, sup, W.at(sup)))
        elif sup in rep.when and rep.when[sup] > rep.when[k]:
            R.err("attached", "%s at %s is written before what holds it up (%s): the server drops it" % (b, k, sup))
    for where, n in lights.items():
        if not n:
            R.err("attached", "the %s has no lantern" % where)


def check_clear(rep, E, W, R):
    tags = {"#minecraft:logs": [], "#minecraft:leaves": [], "#minecraft:replaceable": []}
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
            if not any(min(b[0], b[3]) <= x <= max(b[0], b[3]) and min(b[2], b[5]) <= z <= max(b[2], b[5])
                       and min(b[1], b[4]) <= W.ground(x, z) + 1 and max(b[1], b[4]) >= hi + 2 for b in boxes):
                R.err("clear", "column (%d, %d), written y%d..%d, is not cleared of %s up to y%d" % (x, z, lo, hi, tag, hi + 2))
                break


def check_npc(rep, E, W, R, data=DATA):
    q = E.rec["quest"]["id"]
    rw = [r for r in load_json("rewards.json", data)["rewards"] if r.get("kind") == "npc_grant" and r.get("quest") == q]
    if len(rw) != 1:
        R.err("npc", "%d npc_grant records in data/rewards.json for %s, not 1" % (len(rw), q))
        return
    at = tuple(rw[0]["npc_at"])
    if at != E.npc:
        R.err("npc", "data/rewards.json %s stands him at %s, not the record's spot %s" % (rw[0]["id"], at, E.npc))
    x, y, z = at
    if not (base(W.at(at)) == "minecraft:air" and base(W.at((x, y + 1, z))) == "minecraft:air" and W.solid((x, y - 1, z))
            and base(W.at((x, y - 1, z))) != TRAPDOOR):
        R.err("npc", "his spot %s is %s over %s, not two blocks of air on the floor" % (at, W.at(at), W.at((x, y - 1, z))))
    if not (abs(x - E.cx) < E.h and abs(z - E.cz) < E.h and y == E.hf + 1):
        R.err("npc", "his spot %s is not in the house's room" % (at,))
    dl = load_json("dialogue.json", data)
    conv = next((c for c in dl["conversations"] if c["id"] == E.rec["npc"]["conversation"]), None)
    if conv is None or conv.get("quest_id") != q or not conv.get("npc_id"):
        R.err("npc", "no conversation %s with an NPC running %s" % (E.rec["npc"]["conversation"], q))
        return
    import compile_dialogue as CD
    try:
        _d, quests, fields = CD.load(data)
        CD.compile_conversation(conv, quests, fields)
    except SystemExit as e:
        R.err("npc", "the conversation does not compile: %s" % e)
    rq = next((x for x in load_json("quests.json", data)["quests"] if x["id"] == q), None)
    if rq is None or [c["item"] for r in rq.get("rewards") or [] for c in r["contents"]] != [c["item"] for c in rw[0]["contents"]]:
        R.err("npc", "the quest's reward contents differ from data/rewards.json %s" % rw[0]["id"])


def _tags_in(obj):
    out = []
    if isinstance(obj, dict):
        if obj.get("kind") == "player_tag":
            out.append(obj.get("tag"))
        for v in obj.values():
            out += _tags_in(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _tags_in(v)
    return out


def check_callback(pack, E, R, data=DATA):
    c = E.rec["lopunny_check"]
    files = sorted((pack / CALLBACK_DIR).glob("*.molang")) if (pack / CALLBACK_DIR).is_dir() else []
    if len(files) != 1:
        R.err("check", "%d callbacks under %s (Cobblemon fires only its own namespace's, EXP-042), not 1" % (len(files), CALLBACK_DIR))
        return
    text = files[0].read_text(encoding="utf-8")
    tag, sp = c["tag"], c["species"]
    if "''" in text:
        R.err("check", "the callback escapes a quote with '' (Molang has no escape): the script does not parse")
    if "q.player.party.pokemon" not in text:
        R.err("check", "the callback does not read the party (q.player.party.pokemon)")
    m = re.search(r"(t\.\w+)\s*=\s*t\.\w+\.species\.identifier;", text)
    if not m or not re.search(r"%s\s*==\s*'%s'" % (re.escape(m.group(1)), re.escape(sp)), text):
        R.err("check", "the callback does not compare the species through a t. variable with '%s' (a chained call "
              "does not read, .claude/rules/datapacks.md)" % sp)
    if "add %s'" % tag not in text or "remove %s'" % tag not in text:
        R.err("check", "the callback does not both add and remove the tag %s" % tag)
    period = re.search(r"math\.mod\(q\.player\.world\.game_time, (\d+)\)", text)
    if not period or int(period.group(1)) != int(c["period_ticks"]):
        R.err("check", "the callback is not throttled to the record's %s ticks" % c["period_ticks"])
    q = E.rec["quest"]["id"]
    quest = next((x for x in load_json("quests.json", data)["quests"] if x["id"] == q), {})
    conv = next((x for x in load_json("dialogue.json", data)["conversations"] if x["id"] == E.rec["npc"]["conversation"]), {})
    qt, ct = _tags_in(quest.get("transitions")), _tags_in(conv.get("nodes"))
    if not qt or not ct or set(qt + ct) != {tag}:
        R.err("check", "the quest's transitions read %s and the conversation's options %s; both must read %s" % (qt, ct, tag))


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
    if ("fn", "cobblers:lopunny_house/build") not in [tuple(s) for s in steps]:
        R.err("steps", "the re-application does not run cobblers:lopunny_house/build")
    holds = [tuple(int(v) for v in s[1].split()[2:]) for s in steps if s[0] == "cmd" and s[1].startswith("forceload add")]
    if not holds or kinds[-1] != "cmd" or not steps[-1][1].startswith("forceload remove"):
        R.err("steps", "the re-application does not hold the chunks round the build and release them after")
        return
    for (x, _y, z) in rep.state:
        if not any(min(h[0], h[2]) <= x <= max(h[0], h[2]) and min(h[1], h[3]) <= z <= max(h[1], h[3]) for h in holds):
            R.err("steps", "(%d, %d) is written outside the re-application's forceload" % (x, z))
            return


def audit(rec, g, pack, steps=None, data=DATA):
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
    check_footprint(rep, E, W, R)
    check_seat(rep, E, W, R)
    check_cellar(rep, E, W, R)
    check_habitat(rep, E, W, R, data)
    check_blocks(rep, E, R, data)
    check_attached(rep, E, W, R)
    check_clear(rep, E, W, R)
    check_npc(rep, E, W, R, data)
    check_callback(pack, E, R, data)
    check_steps(rep, lines, steps, R)
    R.note("house floor y%d, cellar floor y%d, statue floor y%d, Hopgood at %s; %d cells written"
           % (E.hf, E.floor_y, E.statue_floor, E.npc, len(rep.state)))
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rec = load_json("lopunny_house.json")
    g = G.load(a.source_root)
    steps = None
    try:
        import lopunny_house  # the re-application steps are the generator's OUTPUT, checked here, never its geometry
        steps = lopunny_house.placement_steps(lopunny_house.load(), g)
    except ImportError:
        pass
    R = audit(rec, g, a.pack, steps)
    for n in R.notes:
        print("note: %s" % n)
    for e in R.errors:
        print("PROBLEM %s" % e)
    print("lopunny_house_audit: %s (%d problem(s))" % ("clean" if not R.errors else "FAILED", len(R.errors)))
    return 1 if R.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
