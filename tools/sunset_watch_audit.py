#!/usr/bin/env python
"""The Sundown Watch, audited offline: the emitted pack replayed block by block against the record, re-derived.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/sunset_watch.py. It
reads data/sunset_watch.json, the canonical heightmap (tools/ground.py), data/habitat_blocks.json, data/spawns.json,
data/regions.json, data/rewards.json, data/dialogue.json, data/progression.json, data/quests.json, data/ferries.json,
data/spawn_blocks.json, data/spawn_block_policy.json, tools/compile_spawns.py (to compile the pools the way the
campaign does) and, when it can find it, the Cobblemon jar (the evolution levels). It derives what it expects with its
own arithmetic, then REPLAYS the generated build function into a block model and compares. The only things taken from
the generator are its outputs (the pack, and the re-application steps it hands tools/reapply.py), which are what is
being checked. Mutating the generator (a pillar a block short, the terrace laid at the lowest ground, a bench turned
round, the find's barrel moved, leaves that decay) fails a named check here with data/sunset_watch.json untouched;
tests/test_sunset_watch.py does exactly that.

What is checked, each from the data and the heightmap, never from the pack:

  footprint  every write and every clear lies in the record's two boxes; no write within 16 blocks of the Dusk tower
             or any other authored coordinate (data/*.json) outside this place's own records
  terrace    paved level P = the highest ground under the footprint; every column paved at P, solid under it to its own
             ground, air over it (but for features); the highest-ground rule leaves no column above P
  dial       the plinth stands at the dial's centre one over the floor; the ring is smooth stone at the four axes; the
             twelve hour marks' axis cells are chiselled brick
  gate       four pillar columns, each `height` blocks, a lintel across them, an opening the record's width clear to the
             sky under the lintel; the sight line from the first bench to the gate at head height is clear (the point
             of the place); the gate stands on the dial's own east-west axis
  benches    every bench cell is a stone-brick stair facing east (back to the east, open to the gate), on the floor, the
             aisle between the groups is clear
  stairs     the way down from the lip is one lower each column, on solid foundation, and ends within a step of the
             natural ground; the parapet is open exactly where it is
  hut        floor = highest ground under the walls + 1 and flush with the terrace within one block; walls solid and
             four high but for the door and the window holes; a door in the south wall; a roof over every interior
             column; the interior is a place to stand; the barrel in the north-east corner
  find       data/rewards.json's cache for the record's reward: its barrel is written where the container says; its
             trigger box holds a place a player can stand; Dusk Balls and a Spell Tag in it
  mast       the pole is `height` logs; its second log is the day Habitat Block's cell, written as a spruce log
  habitat    each Habitat Block the record names: activated, its pool the record's, its position the plinth / the mast's
             second log, its mimic what the build writes there; its pool compiled through tools/compile_spawns.py
             carries `timeRange` on every entry; the dusk pool is dusk and the day pool is day; every level is inside
             the sub-region's band except the nest's; (with the jar) the evolution policy
  blocks     every written block is in blocks.ids; leaves are persistent; no chest and no bed; no spawn condition
             (data/spawn_blocks.json) and the record declares none
  attached   every sign, lantern, chain, plant and door is written after what holds it, which is solid; lanterns light
             at least `LIT_SHARE` of the terrace's columns to block light 8 (15 less the Manhattan distance)
  clear      every written cell above ground + 1 lies in a clear of logs and leaves
  npc        the keeper's spot is two blocks of air on a paved floor; her conversation exists, compiles, its quest and
             progression field list it; the npc step stands her there
  landing    the waymark is a sign facing north on dry beach, far from the ferryman and the jetty
  see        the mast's crown is visible from a boat at sea level 550 blocks west (no ground in the line)
  steps      the re-application holds every written chunk and runs the build; the function passes
             tools/function_limits.py

NOT checked, and it needs a running server: that the fills land, that the Habitat Blocks spawn the pools (and that the
`timeRange` gate holds in an ACTIVATED block), that the cache grants, that the keeper renders and talks, that the sun
sets through the gate, anything about how it looks.

  python tools/sunset_watch_audit.py [--pack build/datapacks/cobblers_sunset_watch] [--source-root R]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_sunset_watch"
FUNCTION = "data/cobblers/function/sunset_watch/build.mcfunction"
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S.*?)$")
FORCELOAD = re.compile(r"^forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$")
# Block light 15 less the Manhattan distance to a lantern (leaves and walls not counted). Hostile mobs spawn at block
# light 0 in 1.21 (ASSUMED from vanilla, not measured here), so a column is lit when it is within 14 of a lantern.
LIT_DIST = 14
LIT_SHARE = 1.0
BEHIND = {"north": (0, 1), "south": (0, -1), "east": (-1, 0), "west": (1, 0)}
PLANTS = {"minecraft:short_grass", "minecraft:fern"}
NOT_SOLID = {"minecraft:air", "minecraft:lantern", "minecraft:chain", "minecraft:spruce_wall_sign", "minecraft:spruce_sign",
             "minecraft:short_grass", "minecraft:fern", "minecraft:spruce_door"}


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

    def solid(self, k):
        return base(self.at(k)) not in NOT_SOLID


class Expect:
    """Everything the audit expects, derived here from the record and the heightmap."""

    def __init__(self, rec, g):
        self.rec, self.g = rec, g
        self.cx, self.cz = rec["site"]["centre"]
        t = rec["terrace"]
        self.t = t
        cols = [(self.cx + a, self.cz + b) for a in range(t["lx"][0], t["lx"][1] + 1) for b in range(t["lz"][0], t["lz"][1] + 1)]
        self.cols = cols
        self.P = max(g(x, z) for x, z in cols)
        h = rec["hut"]
        self.hx, self.hz = self.cx + h["centre"][0], self.cz + h["centre"][1]
        self.hh = h["half"]
        self.hf = max(g(self.hx + a, self.hz + b) for a in range(-self.hh, self.hh + 1) for b in range(-self.hh, self.hh + 1)) + 1
        self.plinth = (self.cx + rec["dial"]["centre"][0], self.P + 1, self.cz + rec["dial"]["centre"][1])
        m = rec["mast"]
        self.mast = (self.cx + m["at"][0], self.cz + m["at"][1])
        self.mast_log2 = (self.mast[0], self.P + 2, self.mast[1])
        self.barrel = (self.hx + self.hh - 1, self.hf + 1, self.hz - (self.hh - 1))
        self.npc = (self.cx + rec["npc"]["at"][0], self.P + 1, self.cz + rec["npc"]["at"][1])
        ap = rec["landing_post"]["at"]
        self.sign = (ap[0], g(ap[0], ap[1]) + 2, ap[1])


def in_box(x, z, b):
    return b["min"][0] <= x <= b["max"][0] and b["min"][1] <= z <= b["max"][1]


# --------------------------------------------------------------------------------------------------------- the checks
def check_footprint(rep, E, R, data=DATA):
    boxes = [b for b in E.rec["site"]["bounding_boxes"] if b["id"] in ("sunset_watch_all", "sunset_watch_landing_box")]
    for (x, y, z) in rep.state:
        if not any(in_box(x, z, b) for b in boxes):
            R.err("footprint", "a write at (%d, %d, %d) lies outside the record's boxes" % (x, y, z))
            break
    for tag, a, _st in rep.clears:
        for (x, z) in ((a[0], a[2]), (a[3], a[5])):
            if not any(in_box(x, z, b) for b in boxes):
                R.err("footprint", "a clear %s reaches (%d, %d) outside the record's boxes" % (a, x, z))
                return
    # nothing else authored lies within 16 blocks of the main box (our own records excluded)
    mine = {"sunset_watch.json", "habitat_blocks.json", "spawns.json", "rewards.json", "world_probes.json", "dialogue.json",
            "progression.json", "quests.json", "regions.json", "system_contracts.json", "id_authorship.json"}
    main_box = boxes[0] if boxes[0]["id"] == "sunset_watch_all" else boxes[1]
    x0, z0 = main_box["min"][0] - 16, main_box["min"][1] - 16
    x1, z1 = main_box["max"][0] + 16, main_box["max"][1] + 16
    hits = []

    def walk(o, f, p):
        if isinstance(o, dict):
            if isinstance(o.get("x"), (int, float)) and isinstance(o.get("z"), (int, float)) and x0 <= o["x"] <= x1 and z0 <= o["z"] <= z1:
                hits.append((f, p))
            for k, v in o.items():
                walk(v, f, p + "/" + k)
        elif isinstance(o, list):
            if len(o) in (2, 3) and all(isinstance(v, (int, float)) for v in o):
                px, pz = (o[0], o[1]) if len(o) == 2 else (o[0], o[2])
                if x0 <= px <= x1 and z0 <= pz <= z1:
                    hits.append((f, p))
            for i, v in enumerate(o):
                walk(v, f, p + "[%d]" % i)
    for f in sorted(list(data.glob("*.json")) + list(data.glob("*/*.json"))):
        if f.name in mine:
            continue
        try:
            walk(json.loads(f.read_text(encoding="utf-8")), f.name, "")
        except (ValueError, UnicodeDecodeError):
            continue
    if hits:
        R.err("footprint", "authored coordinates within 16 blocks of the Watch: %s" % hits[:3])


def check_terrace(rep, E, W, R):
    t = E.t
    bad_level = [c for c in E.cols if E.g(*c) > E.P]
    if bad_level:
        R.err("terrace", "ground above the paved level y%d at %s" % (E.P, bad_level[0]))
    paving = {"minecraft:stone_bricks", "minecraft:mossy_stone_bricks", "minecraft:cracked_stone_bricks",
              "minecraft:polished_andesite", "minecraft:smooth_stone", "minecraft:chiseled_stone_bricks"}
    for x, z in E.cols:
        if base(W.at((x, E.P, z))) not in paving:
            R.err("terrace", "column (%d, %d) is not paved at y%d: %s" % (x, z, E.P, W.at((x, E.P, z))))
            return
        for y in range(W.ground(x, z) + 1, E.P):
            if not W.solid((x, y, z)):
                R.err("terrace", "no foundation at (%d, %d, %d) under the paving" % (x, y, z))
                return
    # air over the floor, but for the features: the benches, the plinth, the gate, the posts, the mast, the keeper's room
    gate_x = {E.cx + v for v in E.rec["gate"]["lx"]}
    for x, z in E.cols:
        a, b = x - E.cx, z - E.cz
        if x in gate_x or (a == E.rec["parapet"]["lx"]):
            continue
        if base(W.at((x, E.P + 2, z))) not in ("minecraft:air", "minecraft:lantern") and (x, z) != E.mast:
            if base(W.at((x, E.P + 2, z))) in ("minecraft:spruce_fence", "minecraft:spruce_log"):
                continue
            R.err("terrace", "something stands at head height above the floor at (%d, %d): %s" % (x, z, W.at((x, E.P + 2, z))))
            return
    # the extra paving
    for lx0, lz0, lx1, lz1 in t.get("extra_paving", []):
        for a in range(lx0, lx1 + 1):
            for b in range(lz0, lz1 + 1):
                x, z = E.cx + a, E.cz + b
                if base(W.at((x, E.P, z))) not in paving:
                    R.err("terrace", "extra paving at (%d, %d) is %s" % (x, z, W.at((x, E.P, z))))
                    return


def check_dial(rep, E, W, R):
    d = E.rec["dial"]
    px, py, pz = E.plinth
    if base(W.at(E.plinth)) != "minecraft:chiseled_stone_bricks":
        R.err("dial", "the plinth at %s is %s" % (E.plinth, W.at(E.plinth)))
    if base(W.at((px, E.P, pz))) != "minecraft:chiseled_stone_bricks":
        R.err("dial", "the dial's centre floor is not chiselled")
    mid = (d["ring"][0] + d["ring"][1]) / 2.0
    r = int(round(mid))
    for dx, dz in ((r, 0), (-r, 0), (0, r), (0, -r)):
        s = base(W.at((px + dx, E.P, pz + dz)))
        if s != "minecraft:smooth_stone":
            R.err("dial", "the ring at (%d, %d) is %s, not smooth stone" % (px + dx, pz + dz, s))
    r = int(round(sum(d["mark_radii"]) / 2.0))
    for dx, dz in ((r, 0), (-r, 0), (0, r), (0, -r)):
        s = base(W.at((px + dx, E.P, pz + dz)))
        if s != "minecraft:chiseled_stone_bricks":
            R.err("dial", "the hour mark at (%d, %d) is %s, not chiselled brick" % (px + dx, pz + dz, s))
    # each of the twelve marks: some chiselled floor cell within one block of its ray, between the mark radii
    for k in range(d["marks"]):
        ang = math.radians(k * 360.0 / d["marks"])
        ux, uz = math.cos(ang), math.sin(ang)
        hit = False
        for (x, y, z), s in rep.state.items():
            if y != E.P or base(s) != "minecraft:chiseled_stone_bricks":
                continue
            dx, dz = x - px, z - pz
            along = dx * ux + dz * uz
            across = abs(-dx * uz + dz * ux)
            if d["mark_radii"][0] - 0.5 <= along <= d["mark_radii"][1] + 0.5 and across <= 1.0:
                hit = True
                break
        if not hit:
            R.err("dial", "hour mark %d (%d degrees) has no chiselled cell on its ray" % (k, k * 360 // d["marks"]))


def check_gate(rep, E, W, R):
    gt = E.rec["gate"]
    h = gt["height"]
    stone = ("minecraft:stone_bricks", "minecraft:mossy_stone_bricks", "minecraft:chiseled_stone_bricks")
    for lx in range(gt["lx"][0], gt["lx"][1] + 1):
        for lo, hi in gt["pillar_lz"]:
            for lz in range(lo, hi + 1):
                x, z = E.cx + lx, E.cz + lz
                for dy in range(1, h + 1):
                    if base(W.at((x, E.P + dy, z))) not in stone:
                        R.err("gate", "the pillar at (%d, %d) is %s at +%d" % (x, z, W.at((x, E.P + dy, z)), dy))
                        return
                if W.solid((x, E.P + h + 3, z)):
                    R.err("gate", "the pillar at (%d, %d) is taller than %d blocks plus its cap" % (x, z, h))
        lo_all = min(a for a, _b in gt["pillar_lz"])
        hi_all = max(b for _a, b in gt["pillar_lz"])
        for lz in range(lo_all, hi_all + 1):
            if base(W.at((E.cx + lx, E.P + h + 1, E.cz + lz))) != "minecraft:stone_bricks":
                R.err("gate", "no lintel at lx %d lz %d" % (lx, lz))
                return
    # the opening is clear from the floor to the lintel
    open_lo = max(b for _a, b in gt["pillar_lz"][:1]) + 1
    open_hi = min(a for a, _b in gt["pillar_lz"][1:]) - 1
    for lx in range(gt["lx"][0], gt["lx"][1] + 1):
        for lz in range(open_lo, open_hi + 1):
            for dy in range(1, h + 1):
                if W.solid((E.cx + lx, E.P + dy, E.cz + lz)):
                    R.err("gate", "the opening is blocked at (%d, %d, %d)" % (E.cx + lx, E.P + dy, E.cz + lz))
                    return
    if open_hi - open_lo + 1 < 7:
        R.err("gate", "the opening is %d wide, under 7" % (open_hi - open_lo + 1))
    # on the dial's own east-west axis: the opening is symmetric about the dial centre's lz
    if (open_lo + open_hi) / 2.0 != E.rec["dial"]["centre"][1]:
        R.err("gate", "the opening's middle %s is not on the dial's axis lz %s" % ((open_lo + open_hi) / 2.0, E.rec["dial"]["centre"][1]))
    # the sight line: head height (floor + 2 and + 3) from the first bench row to the gate along the axis is clear
    z = E.cz + E.rec["dial"]["centre"][1]
    first = E.cx + E.rec["benches"]["rows_lx"][0] - 1
    for x in range(E.cx + gt["lx"][1], first + 1):
        for dy in (2, 3):
            if W.solid((x, E.P + dy, z)):
                R.err("gate", "the sight line from the benches to the gate is blocked at (%d, %d, %d) by %s"
                      % (x, E.P + dy, z, W.at((x, E.P + dy, z))))
                return
    # beyond the gate, westwards, nothing the player could mistake for the horizon for 12 blocks at head height
    for x in range(E.cx + gt["lx"][0] - 12, E.cx + gt["lx"][0]):
        for dy in (3, 4):
            if base(W.at((x, E.P + dy, z))) not in ("minecraft:air", "minecraft:acacia_leaves") and x > E.cx - 60 and W.ground(x, z) < E.P + dy:
                R.err("gate", "something stands in the view west of the gate at (%d, %d, %d)" % (x, E.P + dy, z))
                return


def check_benches(rep, E, W, R):
    b = E.rec["benches"]
    cells = set()
    for lx in b["rows_lx"]:
        for lo, hi in b["groups_lz"]:
            for lz in range(lo, hi + 1):
                cells.add((E.cx + lx, E.cz + lz))
    for x, z in cells:
        s = W.at((x, E.P + 1, z))
        if base(s) != "minecraft:stone_brick_stairs" or prop(s, "facing") != "east" or prop(s, "half") != "bottom":
            R.err("benches", "(%d, %d) is %s, not a stone-brick stair facing east" % (x, z, s))
            return
    found = {(x, z) for (x, y, z), s in rep.state.items() if y == E.P + 1 and base(s) == "minecraft:stone_brick_stairs"
             and E.cx + E.t["lx"][0] <= x <= E.cx + E.t["lx"][1]}
    if found != cells:
        R.err("benches", "stairs on the terrace floor at %s are not exactly the record's benches" % sorted(found - cells)[:3])
    aisle = set(range(min(g[1] for g in b["groups_lz"]) and 0, 1))
    lo_aisle = max(h for _l, h in b["groups_lz"][:1]) + 1
    hi_aisle = min(l for l, _h in b["groups_lz"][1:]) - 1
    for lx in b["rows_lx"]:
        for lz in range(lo_aisle, hi_aisle + 1):
            if W.solid((E.cx + lx, E.P + 1, E.cz + lz)):
                R.err("benches", "the aisle is blocked at lx %d lz %d" % (lx, lz))
                return
    del aisle


def check_stairs(rep, E, W, R):
    sr = E.rec["stair_run"]
    pa = E.rec["parapet"]
    lzs = range(sr["lz"][0], sr["lz"][1] + 1)
    # the parapet is open exactly where the record says
    for lz in range(E.t["lz"][0], E.t["lz"][1] + 1):
        s = base(W.at((E.cx + pa["lx"], E.P + 1, E.cz + lz)))
        gap = pa["gap_lz"][0] <= lz <= pa["gap_lz"][1]
        if gap and s == "minecraft:stone_brick_wall":
            R.err("stairs", "the parapet is closed in the stair run's gap at lz %d" % lz)
            return
        if not gap and s not in ("minecraft:stone_brick_wall", "minecraft:spruce_fence"):
            R.err("stairs", "the parapet has a hole at lz %d: %s" % (lz, s))
            return
    last_y, last_col = E.P + 1, None
    for k in range(0, 80):
        lx = sr["from_lx"] - k
        ys = []
        for lz in lzs:
            x, z = E.cx + lx, E.cz + lz
            col = [y for y in range(W.ground(x, z) - 1, E.P + 3) if base(W.at((x, y, z))) == "minecraft:stone_brick_stairs"]
            ys.append(col)
        if not any(ys):
            break
        if any(len(c) != 1 for c in ys) or len({c[0] for c in ys}) != 1:
            R.err("stairs", "column lx %d is not one even stair row: %s" % (lx, ys))
            return
        y = ys[0][0]
        if y != E.P - k:
            R.err("stairs", "column lx %d stands at y%d, not one lower each time (y%d)" % (lx, y, E.P - k))
            return
        for lz in lzs:
            x, z = E.cx + lx, E.cz + lz
            s = W.at((x, y, z))
            if prop(s, "facing") != "east":
                R.err("stairs", "the stair at (%d, %d) does not rise towards the terrace" % (x, z))
                return
            for yy in range(W.ground(x, z) + 1, y):
                if not W.solid((x, yy, z)):
                    R.err("stairs", "no foundation under the stair at (%d, %d, %d)" % (x, yy, z))
                    return
        last_y, last_col = y, lx
    if last_col is None:
        R.err("stairs", "no way down from the lip")
        return
    nxt = sr["from_lx"] - (E.P - last_y + 1)
    for lz in lzs:
        gg = W.ground(E.cx + nxt, E.cz + lz)
        if gg - last_y > 1 or last_y - gg > 1:
            R.err("stairs", "the stairs end at y%d but the ground beyond is y%d: more than a step" % (last_y, gg))
            return


def check_hut(rep, E, W, R):
    h, hf = E.hh, E.hf
    top = E.rec["hut"]["wall_height"]
    if abs(hf - E.P) > 1:
        R.err("hut", "the hut floor y%d is %d from the terrace's y%d" % (hf, abs(hf - E.P), E.P))
    if base(W.at((E.hx, hf, E.hz))) != "minecraft:spruce_planks":
        R.err("hut", "the floor at the centre is %s" % W.at((E.hx, hf, E.hz)))
    holes = set()
    for a in (-2, 2):
        holes.update({(a, 2, h), (a, 3, h)})
    for a in (-1, 1):
        holes.update({(a, 2, -h), (a, 3, -h)})
    holes.update({(-h, 2, 0), (-h, 3, 0), (h, 2, 0), (h, 3, 0), (0, 1, h), (0, 2, h)})
    for a in range(-h, h + 1):
        for b in range(-h, h + 1):
            if max(abs(a), abs(b)) != h:
                continue
            for dy in range(1, top + 1):
                s = W.at((E.hx + a, hf + dy, E.hz + b))
                if (a, dy, b) in holes:
                    if (a, dy, b) in ((0, 1, h), (0, 2, h)):
                        if base(s) != "minecraft:spruce_door":
                            R.err("hut", "no door at the south wall's middle +%d" % dy)
                    elif W.solid((E.hx + a, hf + dy, E.hz + b)):
                        R.err("hut", "the window hole at %s is solid" % ((a, dy, b),))
                    continue
                if not W.solid((E.hx + a, hf + dy, E.hz + b)):
                    R.err("hut", "a hole in the wall at %s: %s" % ((E.hx + a, hf + dy, E.hz + b), s))
                    return
    ni = h - 1
    furniture = {(ni, 1, -ni), (-ni, 1, 0), (-ni, 1, ni), (ni, 1, ni)} | {(a, 1, -ni) for a in range(-ni, 1)} | {(a, 2, -ni) for a in (-ni, -ni + 1)}
    for a in range(-ni, ni + 1):
        for b in range(-ni, ni + 1):
            for dy in (1, 2):
                k = (E.hx + a, hf + dy, E.hz + b)
                if (a, dy, b) in furniture:
                    continue
                if W.solid(k):
                    R.err("hut", "the interior is blocked at %s by %s" % (k, W.at(k)))
                    return
            # a roof over every interior column
            if not any(W.solid((E.hx + a, hf + dy, E.hz + b)) for dy in range(top + 1, top + 8)):
                R.err("hut", "no roof over the interior column (%d, %d)" % (E.hx + a, E.hz + b))
                return
    # the way in: the cell outside the door is paved or ground and two air above it
    fx, fz = E.hx, E.hz + h + 1
    if not W.solid((fx, hf, fz)) or W.solid((fx, hf + 1, fz)) or W.solid((fx, hf + 2, fz)):
        R.err("hut", "the cell outside the door (%d, %d) is not a floor with two blocks of air over it" % (fx, fz))
    if base(W.at(E.barrel)) != "minecraft:barrel":
        R.err("hut", "the north-east corner at %s holds %s, not the barrel" % (E.barrel, W.at(E.barrel)))
    sgn = [k for k, s in rep.state.items() if base(s) == "minecraft:spruce_wall_sign" and abs(k[0] - E.hx) <= h + 1]
    if not sgn:
        R.err("hut", "no sign on the door's wall")


def check_find(rep, E, W, R, data=DATA):
    rw = {r["id"]: r for r in load_json("rewards.json", data)["rewards"]}
    r = rw.get(E.rec["find"]["reward"])
    if r is None or r.get("kind") != "cache":
        R.err("find", "no cache %s in data/rewards.json" % E.rec["find"]["reward"])
        return
    if tuple(r["container"]["at"]) != E.barrel:
        R.err("find", "the cache's container is at %s, the barrel is at %s" % (r["container"]["at"], E.barrel))
    if base(W.at(tuple(r["container"]["at"]))) != "minecraft:barrel":
        R.err("find", "the build writes %s where the cache's barrel is" % W.at(tuple(r["container"]["at"])))
    mn, mx = r["trigger"]["min"], r["trigger"]["max"]
    if not (mn[0] <= E.barrel[0] <= mx[0] and mn[1] <= E.barrel[1] <= mx[1] and mn[2] <= E.barrel[2] <= mx[2]):
        R.err("find", "the trigger box %s does not contain the barrel %s" % ((mn, mx), E.barrel))
    stand = False
    for x in range(mn[0], mx[0] + 1):
        for z in range(mn[2], mx[2] + 1):
            for y in range(mn[1], mx[1] + 1):
                if W.solid((x, y - 1, z)) and not W.solid((x, y, z)) and not W.solid((x, y + 1, z)):
                    stand = True
    if not stand:
        R.err("find", "no place a player can stand in the trigger box")
    items = {c["item"]: c["count"] for c in r["contents"]}
    if items.get("cobblemon:dusk_ball", 0) < 1 or items.get("cobblemon:spell_tag", 0) < 1:
        R.err("find", "the cache does not hold Dusk Balls and a Spell Tag: %s" % items)
    z = zipfile.ZipFile(_jar()) if _jar() else None
    for c in r["contents"]:
        if z is not None and "assets/cobblemon/models/item/%s.json" % c["item"].split(":")[1] not in z.namelist():
            R.err("find", "%s is not an item in the 1.8.0 jar" % c["item"])


def check_mast(rep, E, W, R):
    m = E.rec["mast"]
    for dy in range(1, m["height"] + 1):
        s = W.at((E.mast[0], E.P + dy, E.mast[1]))
        if base(s) != "minecraft:spruce_log":
            R.err("mast", "the pole is %s at +%d" % (s, dy))
            return
    if W.solid((E.mast[0], E.P + m["height"] + 2, E.mast[1])):
        R.err("mast", "the pole is taller than %d" % m["height"])
    if base(W.at((E.mast[0], E.P + m["height"] + 1, E.mast[1]))) != "minecraft:lantern":
        R.err("mast", "no lantern at the crown")
    for s in (-1, 1):
        ex = E.mast[0] + s * m["arm_reach"]
        if base(W.at((ex, E.P + m["arm_y"] - 2, E.mast[1]))) != "minecraft:lantern":
            R.err("mast", "no lantern at the arm's end %d" % ex)


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


_JAR = []


def _jar():
    if not _JAR:
        try:
            import battle_sim
            _JAR.append(battle_sim.find_jar())
        except BaseException:
            _JAR.append(None)
    return _JAR[0]


def _jar_evolutions():
    """{species: lowest level it evolves AT} and {species: (pre-evolution, level or None)} from the jar, or None."""
    jar = _jar()
    if jar is None:
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
    spawns = load_json("spawns.json", data)
    sub, band = _sub_band(E.cx, E.cz, data)
    if sub != rec["site"]["subregion"]:
        R.err("habitat", "the site is in %s, the record says %s" % (sub, rec["site"]["subregion"]))
    ev = _jar_evolutions()
    if ev is None:
        R.note("habitat: no Cobblemon jar found; the evolution policy was not checked")
    import compile_spawns as CS
    for key, want_pos, want_time in (("dusk", E.plinth, "dusk"), ("day", E.mast_log2, "day")):
        d = rec[key]
        b = hb.get(d["block"])
        if b is None:
            R.err("habitat", "no Habitat Block %s in data/habitat_blocks.json" % d["block"])
            continue
        pos = (b["position"]["x"], b["position"]["y"], b["position"]["z"])
        if b.get("style") != "activated" or b.get("replace_spawns") is not False:
            R.err("habitat", "%s is not an activated block without ReplaceSpawns" % b["id"])
        if b.get("pool") != "cobblers:%s" % d["habitat"]:
            R.err("habitat", "%s's pool is %s, not cobblers:%s" % (b["id"], b.get("pool"), d["habitat"]))
        if pos != want_pos:
            R.err("habitat", "%s stands at %s, not %s" % (b["id"], pos, want_pos))
        if base(W.at(want_pos)) != base(b.get("mimic", "")) or base(W.at(want_pos)) != base(d["mimic"]):
            R.err("habitat", "the build writes %s at %s and the block's mimic is %s: not one more of them"
                  % (W.at(want_pos), want_pos, b.get("mimic")))
        act = b.get("activated") or {}
        if act.get("trigger") != "TICK" or act.get("cancel_range") != -1:
            R.err("habitat", "%s is not a TICK block that leaves natural spawning alone" % b["id"])
        hab = next((h for h in spawns["habitats"] if h["id"] == d["habitat"]), None)
        if hab is None or band is None:
            R.err("habitat", "no habitat pool %s, or no band for %s" % (d["habitat"], sub))
            continue
        lo, hi = band["minimum"], band["maximum"]
        if not (lo <= hab["level_band"]["minimum"] and hab["level_band"]["maximum"] <= hi):
            R.err("habitat", "the pool's band %s is not inside %s's %d-%d" % (hab["level_band"], sub, lo, hi))
        flat = [e for e in spawns["entries"] if e.get("scope") == d["habitat"]]
        if {e["species"] for e in flat} != {e["pokemon"] for e in hab["entries"]}:
            R.err("habitat", "%s: the flat entries and the pool's entries name different species" % d["habitat"])
        for e in hab["entries"] + flat:
            if (e.get("conditions") or {}).get("timeRange") != want_time:
                R.err("habitat", "%s %s carries timeRange %s, not %s" % (d["habitat"], e.get("pokemon") or e.get("species"),
                                                                        (e.get("conditions") or {}).get("timeRange"), want_time))
        # compiled the way the campaign compiles it: the gate must reach the datapack
        comp, _s = CS.compile_habitat(hab, flat)
        for s in comp["spawns"]:
            if s.get("timeRange") != want_time:
                R.err("habitat", "compiled %s: %s has timeRange %s" % (d["habitat"], s.get("species"), s.get("timeRange")))
        nest = {"drakloak"} if key == "dusk" else set()
        for e in hab["entries"]:
            a, z2 = (int(v) for v in e["level"].split("-"))
            if e["pokemon"] in nest:
                if not (E.rec["dusk"]["above_band"][0] == a and E.rec["dusk"]["above_band"][1] == z2 and a > hi - 0 and a > lo):
                    R.err("habitat", "the nest's %s %s is not the record's above_band" % (e["pokemon"], e["level"]))
            elif not (lo <= a <= z2 <= hi):
                R.err("habitat", "%s %s is outside %s's band %d-%d" % (e["pokemon"], e["level"], sub, lo, hi))
            if ev is None:
                continue
            nxt, pre = ev
            sp = e["pokemon"].split()[0]
            if e["pokemon"] not in nest:
                if sp in nxt and z2 > nxt[sp] + 4:
                    R.err("habitat", "%s spawns to %d, past four over its evolution at %d" % (sp, z2, nxt[sp]))
                if sp in pre:
                    _p, lv = pre[sp]
                    if lv is not None and a < lv:
                        R.err("habitat", "%s spawns from %d, under the level %d it evolves at" % (sp, a, lv))
    if "dusk" in rec:
        n = [e for e in next(h for h in spawns["habitats"] if h["id"] == rec["dusk"]["habitat"])["entries"]
             if e["pokemon"] == "drakloak"]
        cap = 40
        tiers = load_json("encounter_design.json", data)["rules"]["tiers"]
        for tier in tiers.values():
            if tier["band"] == [band["minimum"], band["maximum"]]:
                cap = tier["cap"]
        if not n or int(n[0]["level"].split("-")[0]) <= cap:
            R.err("habitat", "the nest's Drakloak is not above the tier's cap %d" % cap)
        else:
            R.note("habitat: the nest is Drakloak %s, against the tier-5 cap %d" % (n[0]["level"], cap))


def check_blocks(rep, E, R, data=DATA):
    allowed = set(E.rec["blocks"]["ids"])
    cond = load_json("spawn_blocks.json", data)["blocks"]
    if E.rec["blocks"].get("spawn_conditions_allowed"):
        R.err("blocks", "the record declares spawn conditions; the Watch should place none")
    seen, decays = set(), None
    for k, s in rep.state.items():
        b = base(s)
        if b in ("minecraft:acacia_leaves",) and prop(s, "persistent") != "true" and decays is None:
            decays = k
        if b in seen:
            continue
        seen.add(b)
        if b not in allowed:
            R.err("blocks", "%s at %s is not in blocks.ids" % (b, k))
        if b.endswith("_bed") or b in ("minecraft:chest", "minecraft:trapped_chest"):
            R.err("blocks", "%s at %s: no chests and no beds" % (b, k))
        if b in cond:
            R.err("blocks", "%s at %s is a spawn condition (%s)" % (b, k, cond[b][0]))
    if decays is not None:
        R.err("blocks", "the leaves at %s are not persistent: they decay" % (decays,))


def support_of(k, s):
    x, y, z = k
    b = base(s)
    if b == "minecraft:lantern":
        return (x, y + 1, z) if prop(s, "hanging") == "true" else (x, y - 1, z)
    if b == "minecraft:chain":
        return (x, y + 1, z)
    if b == "minecraft:spruce_wall_sign":
        d = BEHIND[prop(s, "facing")]
        return (x + d[0], y, z + d[1])
    if b in PLANTS or b in ("minecraft:spruce_door", "minecraft:spruce_sign"):
        return (x, y - 1, z)
    return None


def check_attached(rep, E, W, R):
    lanterns = []
    for k, s in rep.state.items():
        if base(s) == "minecraft:lantern":
            lanterns.append(k)
        sup = support_of(k, s)
        if sup is None:
            continue
        sb = W.at(sup)
        if base(sb) in ("minecraft:air",) or base(sb) in PLANTS:
            R.err("attached", "%s at %s hangs on %s at %s" % (base(s), k, sb, sup))
            continue
        if sup in rep.when and rep.when[sup] > rep.when[k]:
            R.err("attached", "%s at %s is written before what holds it (%s at %s)" % (base(s), k, base(sb), sup))
    lit = 0
    for x, z in E.cols:
        if any(abs(x - lx) + abs(E.P + 1 - ly) + abs(z - lz) <= LIT_DIST for lx, ly, lz in lanterns):
            lit += 1
    share = lit / float(len(E.cols))
    if share < LIT_SHARE:
        R.err("attached", "lanterns light only %.1f%% of the terrace's columns above block light 0 (the bar is %.0f%%)"
              % (100 * share, 100 * LIT_SHARE))
    R.note("attached: %.1f%% of the terrace's %d columns are above block light 0; %d lanterns" % (100 * share, len(E.cols), len(lanterns)))
    if not any(abs(k[0] - E.hx) < E.hh and abs(k[2] - E.hz) < E.hh and k[1] > E.hf for k in lanterns):
        R.err("attached", "the lamp house has no lantern")


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
    if not (W.at(E.npc) == "minecraft:air" and W.at((x, y + 1, z)) == "minecraft:air" and W.solid((x, y - 1, z))
            and base(W.at((x, y - 1, z))) != "natural:ground"):
        R.err("npc", "the keeper's spot %s is %s over %s, not two blocks of air over paving" % (E.npc, W.at(E.npc), W.at((x, y - 1, z))))
    dl = load_json("dialogue.json", data)
    conv = next((c for c in dl["conversations"] if c["id"] == E.rec["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        R.err("npc", "no conversation %s with an NPC" % E.rec["npc"]["conversation"])
        return
    quest = next((q for q in load_json("quests.json", data)["quests"] if q["id"] == conv.get("quest_id")), None)
    if quest is None or conv["id"] not in (quest.get("dialogue_ids") or [quest.get("dialogue_id")]):
        R.err("npc", "the conversation's quest %s does not list it" % conv.get("quest_id"))
    prog = {f["id"]: f for f in load_json("progression.json", data)["quest_fields"]}
    fld = prog.get(conv["cursor"]["progression_field"])
    if fld is None or fld.get("allowed_values") != [n["id"] for n in conv["nodes"]]:
        R.err("npc", "the cursor field does not list the conversation's nodes in order")
    import compile_dialogue as CD
    try:
        _d, quests, fields = CD.load(data)
        CD.compile_conversation(conv, quests, fields)
    except SystemExit as e:
        R.err("npc", "the conversation does not compile: %s" % e)
    text = " ".join(n.get("text") or "" for n in conv["nodes"]).lower()
    for word in ("dusk", "gate", "bench", "hut"):
        if word not in text:
            R.err("npc", "the keeper's talk never mentions the %s" % word)
    if npcs is not None:
        want = (conv["id"], E.npc, "%s:%s" % (E.rec["namespace"], conv["npc_id"]))
        if [(n[0], tuple(n[1]), n[2]) for n in npcs] != [want]:
            R.err("npc", "the npc step %s does not stand %s at %s" % (npcs, conv["npc_id"], E.npc))


def check_landing(rep, E, W, R, data=DATA):
    lp = E.rec["landing_post"]
    x, z = lp["at"]
    gy = W.ground(x, z)
    if gy < 63:
        R.err("landing", "the waymark's ground y%d is not dry beach (sea level y62)" % gy)
    signs = [(k, s) for k, s in rep.state.items() if base(s) == "minecraft:spruce_sign"]
    if len(signs) != 1:
        R.err("landing", "expected one standing sign, found %d" % len(signs))
        return
    k, s = signs[0]
    if k != E.sign:
        R.err("landing", "the sign is at %s, expected %s" % (k, E.sign))
    if prop(s, "rotation") != "8":
        R.err("landing", "the sign's rotation %s is not 8 (facing north, towards a player arriving from the jetty)" % prop(s, "rotation"))
    for line in lp["sign"]:
        if line and json.dumps(line).replace("'", "\\'") not in s:
            R.err("landing", "the sign does not carry the line %r" % line)
    if base(W.at((k[0], k[1] - 1, k[2]))) != "minecraft:stripped_spruce_log":
        R.err("landing", "the sign is not on its post")
    fe = load_json("ferries.json", data)
    dock = next(d for d in fe["docks"] if d["id"] == "sunset_isle_landing")
    fx, _fy, fz = dock["ferryman"]["at"]
    if math.hypot(k[0] - fx, k[2] - fz) < 10:
        R.err("landing", "the sign is within 10 blocks of the ferryman")
    kc = dock["keep_clear"][0]
    if kc[0] - 3 <= k[0] <= kc[2] + 3 and kc[1] - 3 <= k[2] <= kc[3] + 3:
        R.err("landing", "the sign is inside the jetty's keep_clear")
    ax, _ay, az = dock["landing"]["at"]
    dist = math.hypot(k[0] - ax, k[2] - az)
    if not 8 <= dist <= 40:
        R.err("landing", "the sign is %.0f blocks from the arrival spot: not in sight and not out of the way (8-40)" % dist)
    if (k[2] - az) <= 0:
        R.err("landing", "the sign is not south of the arrival spot, so a sign facing north is not facing the player")


def check_see(rep, E, W, R):
    m = E.rec["mast"]
    top = (E.mast[0], E.P + m["height"] + 1, E.mast[1])
    eye = (E.cx - 550, 65.6, E.cz)
    n = 280
    worst = None
    for i in range(1, n):
        t = i / float(n)
        x = eye[0] + (top[0] - eye[0]) * t
        z = eye[2] + (top[2] - eye[2]) * t
        y = eye[1] + (top[1] - eye[1]) * t
        c = y - max(W.ground(int(round(x)), int(round(z))), 62)
        worst = c if worst is None else min(worst, c)
    if worst < 0:
        R.err("see", "the mast's crown is hidden from a boat 550 blocks west by ground (%.1f)" % worst)
    R.note("see: least clearance of the crown from a boat 550 blocks west is %.1f" % worst)


def check_steps(rep, lines, steps, R):
    import function_limits
    bad = function_limits.check_lines(lines, "build")
    if bad:
        R.err("steps", "%d command(s) the server would refuse: %s" % (len(bad), bad[:2]))
    if steps is None:
        return
    fns = [s[1] for s in steps if s[0] == "fn"]
    if fns != ["cobblers:sunset_watch/build"]:
        R.err("steps", "the steps run %s, not cobblers:sunset_watch/build" % fns)
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
    adds = sum(1 for s in steps if s[0] == "cmd" and s[1].startswith("forceload add "))
    rems = sum(1 for s in steps if s[0] == "cmd" and s[1].startswith("forceload remove "))
    if adds != rems:
        R.err("steps", "the steps add %d forceload boxes and remove %d" % (adds, rems))


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
    E = Expect(rec, g)
    W = World(rep, g)
    check_footprint(rep, E, R, data)
    check_terrace(rep, E, W, R)
    check_dial(rep, E, W, R)
    check_gate(rep, E, W, R)
    check_benches(rep, E, W, R)
    check_stairs(rep, E, W, R)
    check_hut(rep, E, W, R)
    check_find(rep, E, W, R, data)
    check_mast(rep, E, W, R)
    check_habitat(rep, E, W, R, data)
    check_blocks(rep, E, R, data)
    check_attached(rep, E, W, R)
    check_clear(rep, E, W, R)
    check_npc(rep, E, W, R, npcs, data)
    check_landing(rep, E, W, R, data)
    check_see(rep, E, W, R)
    check_steps(rep, lines, steps, R)
    R.note("%d cells written, %d clears; terrace y%d, hut floor y%d, barrel %s" % (len(rep.state), len(rep.clears), E.P, E.hf, E.barrel))
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--data", default=str(DATA / "sunset_watch.json"))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    rec = json.loads(Path(a.data).read_text(encoding="utf-8"))
    g = G.load(a.source_root)
    import sunset_watch  # the re-application steps are the generator's OUTPUT, checked here, never its geometry
    rep = audit(rec, g, a.pack, sunset_watch.placement_steps(), sunset_watch.npc_placements(None, g))
    for n in rep.notes:
        print("note: " + n)
    for e in rep.errors:
        print("PROBLEM " + e)
    print("sunset_watch_audit: %s (%d problems)" % ("clean" if not rep.errors else "FAILED", len(rep.errors)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
