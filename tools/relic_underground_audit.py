#!/usr/bin/env python
"""Audit the relic site underground as BUILT, offline, against data it did not come from.

tools/relic_underground.py writes build/datapacks/cobblers_relic_underground. This reads what it actually wrote -- the
block functions in their index order, the zone advancements and functions -- and checks them against sources it did
not decide:

  the carve      data/relic_underground.json's declared numbers (hall centre, radius, floor, the dome's rim and
                 apex, the gallery's and the passage's boxes, DEEP_CITY.md's passage ramp), re-implemented HERE.
                 This file does not import the generator or its geometry.
  the ground     tools/ground.py (the canonical heightmap) and tools/rift_deep.py's pit treads
  what else is   every OTHER built pack in build/datapacks, swept: the undo and the shell may not touch a cell any of
  there          them writes (CLAUDE.md, "our list is not the world"), and the Deep's city pack is read as TEXT,
                 not rebuilt, so "what R9DC writes" comes from a different derivation than the generator's
  the old build  tools/relic_surface_superseded.py, the superseded generator kept verbatim: the only record of which
                 cells the old surface build wrote, since no world may be read. The generator uses it too; that
                 expectation is SHARED, and is the one thing here that is (see the cordon check, which is not)

What must hold:

  carve      every cell the data says is the hall's, the gallery's or the passage's air is air when the functions have
             run, except what the composition stands on the floor; no air is written anywhere else; the floor under
             every carved column is written solid; the choked shaft holds no air
  hq         the HQ's way down (data geometry.hq), re-derived HERE from the data's runs, records room, dressing and
             lights: every air cell air, every tread a stair facing uphill, every landing, wall, floor, ceiling and
             fixture solid, a pressure plate either side of the front door, the old hatch laid back to rock, and every
             face of its air sealed (written, shell or hull, under a pit tread where tools/rift_deep.py refills every
             void, or the HQ room's open air over the stair's head)
  route      a player can walk from OUTSIDE THE HQ'S FRONT DOOR to the hall's centre through the blocks actually there
             (two passable, a floor under, steps of one): the relic pack's writes, else the city pack's (read as text),
             else the pit's tread and the heightmap. An iron door passes only with a pressure plate on both sides. The
             walk must pass the stair's head and the knock box. Found the gallery sealed off from the passage on
             2026-10-02; extended the same day from the passage's end to the front door
  shell      no shell cell is in the carve's or the HQ's air (25_reshell would fill it back), none is above its column's
             ground minus one, none is in the Deep's air, and none touches a cell another pack writes -- except the
             `replace` fills of a pack applied BEFORE R9RU (EARLIER: tools/rift_deep.py's pit, R9B), which ran first;
             before 2026-10-02 this check failed 46,909 cells against cobblers_deep in any checkout that built it
  zone       the advancement's boxes and y bounds are the data's; every carved column west of the threshold is in a
             box; the knock box and the turn-back are outside them; the knock box is carved air over a floor; the turn-back stands on the city's floor or the
             pit's tread with two clear blocks over it; the pass is tested fail-closed (`unless score ... matches 1..`)
  undo       writes exactly the old build's cells minus the city's: air over the ground where the old block was
             solid, never a cell the old build cut to air over the ground, a non-air natural block at and under the
             ground, and none of the old build's materials; touches no cell another pack writes
  cordon     independently of the superseded generator: every edge column of the traced relic region (the old
             audit's own definition of the fence: the three blocks over the ground) is air after the undo, unless
             the city writes it
  nonempty   every block function has commands

  python tools/relic_underground_audit.py [--source-root <root>] [--pack <dir>]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)
DATA = ROOT / "data" / "relic_underground.json"
PACKS = ROOT / "build" / "datapacks"
PACK = PACKS / "cobblers_relic_underground"
SELF = "cobblers_relic_underground"
FOLDER = "relic_underground"

NUM = r"(-?\d+)"
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)(?: replace (\S+))?\s*$" % ((NUM,) * 6))
SETB = re.compile(r"^setblock %s %s %s (\S+)\s*$" % ((NUM,) * 3))
AIR = "minecraft:air"
# the old surface build's materials: none of them is natural ground, so the undo may lay none of them
OLD_MATERIALS = ("tuff_bricks", "polished_tuff", "chiseled_tuff", "crying_obsidian", "raw_gold_block", "distortion_stone",
                 "purple_stained_glass", "tinted_glass", "iron_bars", "end_rod", "sea_lantern", "waxed_oxidized_copper")


def base(b):
    return b.split("[")[0].split("{")[0]


def parse(lines):
    """[(x0, y0, z0, x1, y1, z1, block, replace_tag or None)] for every fill and setblock."""
    out = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        m = FILL.match(s)
        if m:
            v = list(map(int, m.groups()[:6]))
            out.append((min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]),
                        max(v[2], v[5]), m.group(7), m.group(8)))
            continue
        m = SETB.match(s)
        if m:
            x, y, z = map(int, m.groups()[:3])
            out.append((x, y, z, x, y, z, m.group(4), None))
    return out


def cells(w):
    x0, y0, z0, x1, y1, z1 = w[:6]
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                yield (x, y, z)


def read_pack(pack):
    """({function name: [writes]}, index order, {relative path: text} of the zone's files)."""
    fdir = pack / "data" / "cobblers" / "function" / FOLDER
    idx = fdir / "index.txt"
    if not idx.is_file():
        raise SystemExit("no %s: run `python tools/relic_underground.py build` first" % idx)
    order = [n for n in idx.read_text(encoding="utf-8").split("\n") if n.strip()]
    fns = {n: parse((fdir / (n + ".mcfunction")).read_text(encoding="utf-8").splitlines()) for n in order}
    zone = {}
    for f in list(fdir.glob("*.mcfunction")) + list((pack / "data" / "cobblers" / "advancement" / FOLDER).glob("*.json")):
        zone[f.name] = f.read_text(encoding="utf-8")
    return fns, order, zone


# ---------------------------------------------------------------- the expectation, from the data's numbers alone

def expected_air(spec):
    """{(x, y, z)} the data says is air: the hall under its dome, the gallery, the passage on DEEP_CITY.md's ramp.
    Re-implemented from data/relic_underground.json's declared numbers; nothing imported from the generator."""
    g = spec["geometry"]
    h, ga, p = g["hall"], g["gallery"], g["passage"]
    cx, cz = h["centre"]
    R, F = h["radius"], h["floor_y"]
    rim, apex = h["ceiling_rim_y"], h["ceiling_apex_y"]
    air, floor = set(), {}
    for x in range(cx - R, cx + R + 1):
        for z in range(cz - R, cz + R + 1):
            r = math.hypot(x - cx, z - cz)
            if r > R:
                continue
            top = rim + int(round((apex - rim) * (1.0 - (r / R) ** 2)))      # "26 + round(8 * (1 - (r / 21)^2))"
            air.update((x, y, z) for y in range(F + 1, top + 1))
            floor[(x, z)] = F
    for x in range(ga["x"][0], ga["x"][1] + 1):
        for z in range(ga["z"][0], ga["z"][1] + 1):
            air.update((x, y, z) for y in range(ga["floor_y"] + 1, ga["floor_y"] + ga["height"] + 1))
            floor[(x, z)] = ga["floor_y"]
    for x in range(p["stops_at_x"], p["from"][0] + 1):
        f = int(round(12.0 * (3427 - x) / 70.0))                                # data: passage.floor_y
        for z in range(p["interior"]["z"][0], p["interior"]["z"][1] + 1):
            air.update((x, y, z) for y in range(f + 1, f + p["interior"]["height"] + 1))
            floor[(x, z)] = f
    return air, floor


# the stair's facing for a run descending along its step: uphill. Written here again, not imported
_UP = {(0, 1): "north", (0, -1): "south", (1, 0): "west", (-1, 0): "east"}
_DIR = {"east": (1, 0), "west": (-1, 0), "south": (0, 1), "north": (0, -1)}


def expected_hq(spec, passage_air):
    """The HQ's way down from data/relic_underground.json geometry.hq's declared numbers, re-implemented: (air, floors
    {cell: facing or None}, solid {cell}, plates {cell}, hatch {cell}). Nothing imported from the generator.
    passage_air: expected_air()'s air, whose cells the records room's walls leave to the passage."""
    h = spec["geometry"]["hq"]
    room_y, hr = h["room"]["floor_y"], h["head_room"]
    ix0, iy0, iz0, ix1, iy1, iz1 = h["basement"]["interior"]
    ox0, oy0, oz0, ox1, oy1, oz1 = h["basement"]["outer"]
    air = {(x, y, z) for x in range(ix0, ix1 + 1) for y in range(iy0, iy1 + 1) for z in range(iz0, iz1 + 1)}
    p = spec["geometry"]["passage"]
    pfloor = {(x, int(round(12.0 * (3427 - x) / 70.0)), z) for x in range(p["stops_at_x"], p["from"][0] + 1)
              for z in range(p["interior"]["z"][0], p["interior"]["z"][1] + 1)}
    solid = {(x, y, z) for x in range(ox0, ox1 + 1) for y in range(oy0, oy1 + 1) for z in range(oz0, oz1 + 1)
             if (x, y, z) not in air and (x, y, z) not in passage_air and (x, y, z) not in pfloor}
    floors = {}
    for run in h["runs"]:
        if "landing" in run:
            a, b, c, d = run["landing"]
            st = [(x, z, run["floor_y"], None) for x in range(a, c + 1) for z in range(b, d + 1)]
        else:
            (fx, fz), (sx, sz) = run["from"], run["step"]
            st = [(fx + k * sx, fz + k * sz, run["floor_y"] - k, _UP[(sx, sz)]) for k in range(run["n"])]
        for x, z, f, face in st:
            floors[(x, f, z)] = face
            air.update((x, y, z) for y in range(f + 1, f + hr + 1) if y <= room_y)
    air -= set(floors)
    solid -= air
    solid -= set(floors)
    fixtures = set()
    for d in h["dressing"]:
        a, b, c, d2, e, f = d["fill"]
        fixtures.update((x, y, z) for x in range(a, d2 + 1) for y in range(b, e + 1) for z in range(c, f + 1))
    fixtures.update(tuple(c) for c in h["lights"]["standing"] + h["lights"]["hanging"])
    air -= fixtures
    plates = {tuple(c) for c in h["front_door"]["plates"]}
    hatch = {tuple(c) for c in h["hatch_undo"]["cells"]}
    return air, floors, solid | fixtures, plates, hatch


PASS = ("minecraft:air", "minecraft:cave_air", "minecraft:void_air")


def walkable_world(final, city_blocks, pit, ground):
    """(block_at, passable): the world after R9RU as this audit models it, from sources the generator does not decide
    for the HQ: what the relic pack wrote, else what the city pack writes, else the Deep's pit (air over its tread,
    rock at and under it) or the heightmap's ground. An iron door is passable only with a pressure plate on BOTH sides
    of its lower half along its facing: the plate you stand on opens it, the one past it lets you back out."""
    def block_at(c):
        if c in final:
            return final[c]
        if c in city_blocks:
            return city_blocks[c]
        t = pit(c[0], c[2])
        if t is not None:
            return AIR if c[1] > t else "rock"
        return AIR if c[1] > ground(c[0], c[2]) else "rock"

    def plate(c):
        return base(block_at(c)).endswith("_pressure_plate")

    def passable(c):
        b = block_at(c)
        bb = base(b)
        if bb in PASS or bb.endswith("_pressure_plate"):
            return True
        if bb == "minecraft:iron_door":
            lower = c if "half=lower" in b else (c[0], c[1] - 1, c[2])
            m = re.search(r"facing=(\w+)", block_at(lower))
            if not m or base(block_at(lower)) != "minecraft:iron_door":
                return False
            dx, dz = _DIR[m.group(1)]
            return plate((lower[0] + dx, lower[1], lower[2] + dz)) and plate((lower[0] - dx, lower[1], lower[2] - dz))
        return False
    return block_at, passable


# ---------------------------------------------------------------- the checks

# Packs applied BEFORE R9RU whose writes the HQ's way down is cut into on purpose (tools/reapply.py order, checked by
# tests/test_relic_underground.py). Overlap with their `replace` fills is not a conflict: they ran first, and two
# void-to-rock fills never fight. Overlap with their DEFINITE writes still is, but for the door's plates, which stand
# in the pit's open air (R9B cuts it to air and R9RU puts a plate in it afterwards).
EARLIER = {"cobblers_deep": "R9B, tools/rift_deep.py: the pit, whose refill under every tread is replace #rift_void"}


def audit(fns, order, zone, spec, ground, pit, others, old, city, city_blocks=None, others_definite=None):
    """fns/order/zone: read_pack(). ground(x, z) -> y; pit(x, z) -> tread y or None. others: {pack: set of cells}
    (every other built pack's writes in the bounds, the city's included). old: {(x, y, z): block} the superseded
    surface build wrote. city: set of cells the Deep's city pack writes. city_blocks: {cell: block} the city pack
    writes (for the walk from the HQ's front door; without it the walk starts at the passage's HQ end and says so).
    others_definite: {pack: cells written WITHOUT `replace`}; a pack missing from it counts as all definite.
    -> (problems [(kind, msg)], stats)."""
    problems, st = [], {}

    def bad(kind, msg):
        problems.append((kind, msg))

    for n in order:
        if not fns[n]:
            bad("nonempty", "%s writes nothing" % n)
    carve = [n for n in order if n.startswith("carve/")]
    if not any(n == "undo" for n in order):
        bad("nonempty", "no undo function in the index")
    # replay the carve in order: void and surfaces and composition are definite; the shell is `replace` (conditional)
    final, shell, full = {}, set(), {}
    for n in carve:
        for w in fns[n]:
            if w[7]:
                shell.update(cells(w))
                continue
            for c in cells(w):
                final[c] = base(w[6])
                full[c] = w[6]
    air_exp, floor_exp = expected_air(spec)
    hq_air, hq_floors, hq_solid, hq_plates, hq_hatch = expected_hq(spec, air_exp)
    hq_cells = hq_air | set(hq_floors) | hq_solid | hq_plates | hq_hatch
    comp = {c for n in carve if "composition" in n for w in fns[n] for c in cells(w)}
    ch = spec["geometry"]["choked_shaft"]
    half = ch["ring"] // 2
    choke = {(ch["at"][0] + dx, y, ch["at"][1] + dz) for dx in range(-half, half + 1) for dz in range(-half, half + 1)
             for y in range(ch["from_y"], ch["to_y"] + 1)}
    miss = [c for c in air_exp if final.get(c) != AIR and c not in comp]
    if miss:
        bad("carve", "%d cells the data says are air are not, e.g. %s" % (len(miss), sorted(miss)[:3]))
    stray = [c for c, b in final.items() if b == AIR and c not in air_exp and c not in hq_air]
    if stray:
        bad("carve", "%d air cells outside the hall, gallery, passage and the HQ's way down, e.g. %s"
            % (len(stray), sorted(stray)[:3]))
    # the HQ's way down, against its own re-derived expectation: every air cell air, every tread a stair facing uphill,
    # every landing and wall solid, the plates plates, the old hatch rock
    miss = [c for c in hq_air if final.get(c) != AIR]
    if miss:
        bad("hq", "%d cells of the HQ's way down that the data says are air are not, e.g. %s"
            % (len(miss), sorted(miss)[:3]))
    wrongf = [(c, full.get(c)) for c, face in hq_floors.items() if final.get(c) in (None, AIR) or
              (face is not None and ("_stairs" not in full.get(c, "") or "facing=%s" % face not in full.get(c, "")))]
    if wrongf:
        bad("hq", "%d treads or landings are missing or face the wrong way, e.g. %s" % (len(wrongf), sorted(wrongf)[:3]))
    unsolid = [c for c in hq_solid if final.get(c) in (None, AIR)]
    if unsolid:
        bad("hq", "%d wall, floor, ceiling or fixture cells of the records room are not written solid, e.g. %s"
            % (len(unsolid), sorted(unsolid)[:3]))
    noplate = [c for c in hq_plates if not base(final.get(c, "")).endswith("_pressure_plate")]
    if noplate:
        bad("hq", "no pressure plate at %s" % (sorted(noplate),))
    openhatch = [c for c in hq_hatch if final.get(c) in (None, AIR)]
    if openhatch:
        bad("hq", "the old hatch's cells %s are not laid back to rock" % (sorted(openhatch),))
    st["hq_air"] = len(hq_air)
    nofloor = [(x, z) for (x, z), f in floor_exp.items() if final.get((x, f, z)) in (None, AIR)]
    if nofloor:
        bad("carve", "%d carved columns have no floor written, e.g. %s" % (len(nofloor), nofloor[:3]))
    open_choke = [c for c in choke if final.get(c) in (None, AIR)]
    if open_choke:
        bad("carve", "the choked shaft is open at %s" % (sorted(open_choke)[:3],))
    # the composition stands in the hall's air or is laid IN its floor (the platform's lowest step is the floor
    # course, data composition.platform.y [5, 7] on a floor at y5)
    floor_cells = {(x, f, z) for (x, z), f in floor_exp.items()}
    loose = [c for c in comp if c not in air_exp and c not in choke and c not in floor_cells]
    if loose:
        bad("carve", "%d composition blocks outside the hall's air, e.g. %s" % (len(loose), sorted(loose)[:3]))
    st["air"] = sum(1 for b in final.values() if b == AIR)

    # the route: a player can WALK from outside the HQ's front door to the hall's centre through what was actually
    # written. A standing place is two passable cells over a solid one; a step goes to a 4-neighbour at most one up or
    # down, with head room. The world is walkable_world(): the relic pack's writes, else the city pack's, else the pit
    # and the heightmap. Independent of the data's own boxes: a gallery that stops one block short of the passage passes
    # every box check and fails here, and so does a stair whose head is sealed or an iron door nothing opens
    block_at, passable = walkable_world(final, city_blocks or {}, pit, ground)

    def stand(c):
        return passable(c) and passable((c[0], c[1] + 1, c[2])) and not passable((c[0], c[1] - 1, c[2]))
    fd = spec["geometry"]["hq"]["front_door"]
    dx_, dy_, dz_ = fd["at"]
    door = block_at((dx_, dy_, dz_)) if city_blocks else ""
    if city_blocks is None:
        # no city to walk through (a caller that has none): start at the passage's HQ end, and say so
        p = spec["geometry"]["passage"]
        hx, hz = p["from"]
        starts = [(hx, y, hz) for y in range(-5, 30) if stand((hx, y, hz))]
        st["route_from"] = "the passage's HQ end (no city blocks given)"
    elif base(door) != "minecraft:iron_door" or "half=lower" not in door:
        starts = []
        bad("route", "the HQ's front door %s is %s in the city, not an iron door's lower half" % (fd["at"], door))
    else:
        ox, oz = _DIR[re.search(r"facing=(\w+)", door).group(1)]
        starts = [(dx_ + ox, dy_, dz_ + oz)] if stand((dx_ + ox, dy_, dz_ + oz)) else []
        st["route_from"] = "outside the HQ's front door %s" % ((dx_ + ox, dy_, dz_ + oz),)
    cx, cz = spec["geometry"]["hall"]["centre"]
    # the plinth (radius 4, data composition.ring) fills the centre, so "the centre" is standing at the plinth's foot:
    # anywhere within 6 of the hall's centre, which is on the platform's top disc
    goal = {(x, z) for x in range(cx - 6, cx + 7) for z in range(cz - 6, cz + 7) if math.hypot(x - cx, z - cz) <= 6}
    lim = (3340, -5, 3230, 3450, 80, 3330)
    seen, todo, reached = set(starts), list(starts), False
    via = {"stair": False, "records room": False}
    head = tuple(spec["zone"]["hq_access"]["shaft_head"])
    while todo and not reached:
        x, y, z = todo.pop()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                n = (x + dx, y + dy, z + dz)
                if n in seen or not (lim[0] <= n[0] <= lim[3] and lim[1] <= n[1] <= lim[4] and lim[2] <= n[2] <= lim[5]):
                    continue
                if not stand(n):
                    continue
                if dy == 1 and not passable((x, y + 2, z)):
                    continue                                     # no head room to step up
                if dy == -1 and not passable((n[0], n[1] + 2, n[2])):
                    continue                                     # no head room stepping down into it
                seen.add(n)
                todo.append(n)
                if (n[0], n[2]) in goal:
                    reached = True
    st["route_cells"] = len(seen)
    via["stair"] = head in seen
    kb = spec["zone"]["knock"]["box"]
    via["records room"] = any((x, kb[1], z) in seen for x in range(kb[0], kb[3] + 1) for z in range(kb[2], kb[5] + 1))
    st["route_via"] = via
    if not starts:
        bad("route", "nowhere to stand outside the HQ's front door %s" % (fd["at"],))
    elif not reached:
        far = min(seen, key=lambda c: abs(c[0] - cx) + abs(c[2] - cz))
        bad("route", "the hall's centre cannot be walked to from %s (%d places reached, nearest %s; stair head reached: "
                     "%s, knock box reached: %s)" % (st.get("route_from"), len(seen), far, via["stair"],
                                                     via["records room"]))
    elif city_blocks is not None and not (via["stair"] and via["records room"]):
        bad("route", "the hall was reached from the HQ's door but not by the stair's head and the knock box: %s" % via)

    # the knock box is the records room's air at the doorway, over its floor
    kair = [(x, y, z) for x in range(kb[0], kb[3] + 1) for y in range(kb[1], kb[4] + 1) for z in range(kb[2], kb[5] + 1)
            if final.get((x, y, z)) != AIR]
    kfloor = [(x, z) for x in range(kb[0], kb[3] + 1) for z in range(kb[2], kb[5] + 1)
              if final.get((x, kb[1] - 1, z)) in (None, AIR)]
    if kair or kfloor:
        bad("zone", "the knock box %s is not carved air over a floor: %d cells not air, %d columns with no floor, e.g. %s"
            % (kb, len(kair), len(kfloor), (kair or kfloor)[:2]))

    # every face of the HQ's air is sealed: written by this pack (air or block), a shell or hull cell, under a pit
    # column's tread from y-4 (tools/rift_deep.py refills every void there: data/rift_deep.json floor_y - shell.depth),
    # or the HQ room's open air over the stair's head
    dj = json.loads((ROOT / "data" / "rift_deep.json").read_text(encoding="utf-8"))
    pit_lo = dj["floor_y"] - dj["shell"]["depth"]
    room_y = spec["geometry"]["hq"]["room"]["floor_y"]
    unsealed = []
    for (x, y, z) in hq_air:
        for n in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)):
            if n in final or n in shell:
                continue
            t = pit(n[0], n[2])
            if t is not None and (pit_lo <= n[1] < t or (n[1] > room_y and y == room_y)):
                continue
            unsealed.append(((x, y, z), n))
    if unsealed:
        bad("hq", "%d faces of the HQ's air are not sealed, e.g. %s" % (len(unsealed), sorted(unsealed)[:2]))

    # the shell
    st["shell"] = len(shell)
    inair = shell & (air_exp | hq_air)
    if inair:
        bad("shell", "%d shell cells in the carve's air (25_reshell would fill it back), e.g. %s"
            % (len(inair), sorted(inair)[:3]))
    high = [c for c in shell if c[1] > ground(c[0], c[2]) - 1]
    if high:
        bad("shell", "%d shell cells at or above their column's ground, e.g. %s" % (len(high), sorted(high)[:3]))
    deep = [c for c in shell if pit(c[0], c[2]) is not None and c[1] > pit(c[0], c[2])]
    if deep:
        bad("shell", "%d shell cells in the Deep's air, e.g. %s" % (len(deep), sorted(deep)[:3]))
    carved = set(final) | shell
    for name, cs in others.items():
        if name in EARLIER:
            hit = (carved & (others_definite or {}).get(name, cs)) - hq_plates
        else:
            hit = carved & cs
        if hit:
            bad("shell", "%d cells of the carve or its shell are written by %s too, e.g. %s"
                % (len(hit), name, sorted(hit)[:3]))

    # the zone
    z = spec["zone"]
    adv = json.loads(zone.get("relic_zone.json", "{}") or "{}")
    try:
        terms = adv["criteria"]["here"]["conditions"]["player"][0]["terms"]
        got = sorted((int(t["predicate"]["location"]["position"]["x"]["min"]),
                      int(t["predicate"]["location"]["position"]["z"]["min"]),
                      int(t["predicate"]["location"]["position"]["x"]["max"]) - 1,
                      int(t["predicate"]["location"]["position"]["z"]["max"]) - 1,
                      int(t["predicate"]["location"]["position"]["y"]["min"]),
                      int(t["predicate"]["location"]["position"]["y"]["max"]) - 1) for t in terms)
        want = sorted((b[0], b[1], b[2], b[3], z["y"][0], z["y"][1]) for b in z["boxes"])
        if got != want:
            bad("zone", "the advancement's boxes %s are not the data's %s" % (got, want))
    except (KeyError, IndexError, TypeError, ValueError) as e:
        bad("zone", "relic_zone.json is not a location advancement over boxes: %s" % e)

    def inbox(x, zz):
        return any(b[0] <= x <= b[2] and b[1] <= zz <= b[3] for b in z["boxes"])
    out_ = sorted({(x, zz) for (x, y, zz) in air_exp if x < z["threshold_x"] and not inbox(x, zz)})
    if out_:
        bad("zone", "%d carved columns west of the threshold are outside the zone, e.g. %s" % (len(out_), out_[:3]))
    if any(y > z["y"][1] for (_x, y, _z) in air_exp):
        bad("zone", "the carve reaches over the zone's ceiling y%d" % z["y"][1])
    kb = z["knock"]["box"]
    if any(inbox(x, zz) for x in range(kb[0], kb[3] + 1) for zz in range(kb[2], kb[5] + 1)):
        bad("zone", "the knock box is inside the zone")
    tx, ty, tz = z["turn_back"]["at"]
    ix, iz = int(math.floor(tx)), int(math.floor(tz))
    if inbox(ix, iz) and ty <= z["y"][1]:
        bad("zone", "the turn-back point is inside the zone")
    stand = (ix, int(ty) - 1, iz) in city or pit(ix, iz) == int(ty) - 1
    if not stand:
        bad("zone", "the turn-back (%s) stands on neither the city's floor nor the pit's tread" % (z["turn_back"]["at"],))
    if (ix, int(ty), iz) in city.get("solid", set()) or (ix, int(ty) + 1, iz) in city.get("solid", set()):
        bad("zone", "the turn-back is inside a block the city writes")
    tb = zone.get("turn_back.mcfunction", "")
    if "tp @s %s %d %s" % (tx, ty, tz) not in tb:
        bad("zone", "turn_back.mcfunction does not teleport to the data's point %s" % (z["turn_back"]["at"],))
    if "unless score @s %s matches 1.." % z["objective"] not in zone.get("zone.mcfunction", ""):
        bad("zone", "the zone function does not test the pass fail-closed")

    # the undo
    undo = {}
    for n in order:
        if n == "undo" or n.startswith("undo_"):
            for w in fns[n]:
                for c in cells(w):
                    undo[c] = base(w[6])
    st["undo"] = len(undo)
    city_cells = city["all"]
    expect = {c: b for c, b in old.items() if c not in city_cells}
    extra = [c for c in undo if c not in expect]
    if extra:
        bad("undo", "%d undo cells the old build never wrote, e.g. %s" % (len(extra), sorted(extra)[:3]))
    in_city = [c for c in undo if c in city_cells]
    if in_city:
        bad("undo", "%d undo cells R9DC writes, e.g. %s" % (len(in_city), sorted(in_city)[:3]))
    wrong, skipped_ok, missing = [], 0, []
    for c, ob in expect.items():
        gy = ground(c[0], c[2])
        got = undo.get(c)
        if c[1] > gy:
            if base(ob) == AIR:
                if got is not None:
                    wrong.append((c, "the old build cut this to air over the ground; the undo must leave it", got))
                else:
                    skipped_ok += 1
            elif got != AIR:
                missing.append((c, ob, got))
        else:
            if got is None or got == AIR or any(got.endswith(m) for m in OLD_MATERIALS):
                missing.append((c, ob, got))
    if wrong:
        bad("undo", "%d cells written that must be left, e.g. %s" % (len(wrong), wrong[:2]))
    if missing:
        bad("undo", "%d old cells not put back (air over the ground, natural ground under it), e.g. %s"
            % (len(missing), missing[:3]))
    for name, cs in others.items():
        if name == "cobblers_deep_city":
            continue
        hit = set(undo) & cs
        if hit:
            bad("undo", "%d undo cells are written by %s too, e.g. %s" % (len(hit), name, sorted(hit)[:3]))
    st["undo_air"] = sum(1 for b in undo.values() if b == AIR)
    st["undo_ground"] = len(undo) - st["undo_air"]
    return problems, st


def cordon_check(undo, edge, ground, city_cells):
    """The old fence, by the OLD AUDIT's own definition and not by the superseded generator: on every edge column of
    the traced relic region the three blocks over the ground. Each must be laid to air by the undo, unless the city
    still writes it. -> [(x, y, z)] not cleared."""
    out = []
    for (x, z) in edge:
        g = ground(x, z)
        for dy in (1, 2, 3):
            c = (x, g + dy, z)
            if c in city_cells:
                continue
            if undo.get(c) != AIR:
                out.append(c)
    return out


# ---------------------------------------------------------------- inputs

def other_packs(bounds):
    """({pack: set of cells}, {pack: set of cells written WITHOUT `replace`}) for every OTHER built pack's fill and
    setblock writes inside the bounds box."""
    x0, z0, x1, z1 = bounds
    out, definite = {}, {}
    for p in sorted(PACKS.iterdir()) if PACKS.is_dir() else []:
        if not p.is_dir() or p.name == SELF:
            continue
        cs, ds = set(), set()
        for f in (p / "data").rglob("*.mcfunction") if (p / "data").is_dir() else []:
            for w in parse(f.read_text(encoding="utf-8", errors="replace").splitlines()):
                if w[3] < x0 or w[0] > x1 or w[5] < z0 or w[2] > z1:
                    continue
                for c in cells((max(w[0], x0), w[1], max(w[2], z0), min(w[3], x1), w[4], min(w[5], z1))):
                    cs.add(c)
                    if not w[7]:
                        ds.add(c)
        if cs:
            out[p.name] = cs
            definite[p.name] = ds
    return out, definite


def city_blocks_of(bounds):
    """{cell: block} the Deep's city pack writes inside the bounds box, read as TEXT in its index order (a later write
    wins, as R9DC runs them), then any function the index does not name."""
    x0, z0, x1, z1 = bounds
    fdir = PACKS / "cobblers_deep_city" / "data" / "cobblers" / "function" / "deep_city"
    idx = fdir / "index.txt"
    names = [n for n in idx.read_text(encoding="utf-8").split("\n") if n.strip()] if idx.is_file() else []
    files = [fdir / (n + ".mcfunction") for n in names]
    files += sorted(f for f in (PACKS / "cobblers_deep_city" / "data").rglob("*.mcfunction") if f not in files)
    out = {}
    for f in files:
        if not f.is_file():
            continue
        for w in parse(f.read_text(encoding="utf-8", errors="replace").splitlines()):
            if w[3] < x0 or w[0] > x1 or w[5] < z0 or w[2] > z1:
                continue
            for c in cells((max(w[0], x0), w[1], max(w[2], z0), min(w[3], x1), w[4], min(w[5], z1))):
                out[c] = w[6]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root", default=env_source_root())
    ap.add_argument("--pack", default=str(PACK))
    a = ap.parse_args(argv)
    if not a.source_root:
        ap.error("needs --source-root or COBBLERS_SOURCE_ROOT: the ground comes from the heightmap")
    import ground as G
    import rift_deep as RD
    import relic_surface_superseded as S
    spec = json.loads(DATA.read_text(encoding="utf-8"))
    g = G.load(a.source_root)
    m = RD.model(a.source_root)
    X0, Z0, _X1, _Z1 = m["box"]

    def pit(x, z):
        i, j = z - Z0, x - X0
        if 0 <= i < m["mask"].shape[0] and 0 <= j < m["mask"].shape[1] and m["mask"][i, j]:
            return int(m["tread_y"][i, j])
        return None
    b = spec["bounds"]
    box = (min(b["undo"][0], b["carve_with_shell"][0]), min(b["undo"][1], b["carve_with_shell"][1]),
           max(b["undo"][2], b["carve_with_shell"][2]), max(b["undo"][3], b["carve_with_shell"][3]))
    others, others_definite = other_packs(box)
    if "cobblers_deep_city" not in others:
        raise SystemExit("no build/datapacks/cobblers_deep_city: run `python tools/deep_city.py build` first; the undo "
                         "cannot be checked against what R9DC writes without it")
    dc = others["cobblers_deep_city"]
    city = {"all": dc, "solid": set()}
    for f in (PACKS / "cobblers_deep_city" / "data").rglob("*.mcfunction"):
        for w in parse(f.read_text(encoding="utf-8").splitlines()):
            if base(w[6]) != AIR and not (w[3] < box[0] or w[0] > box[2] or w[5] < box[1] or w[2] > box[3]):
                city["solid"].update(cells(w))
    fns, order, zone = read_pack(Path(a.pack))
    old = S.old_write_set(a.source_root)
    problems, st = audit(fns, order, zone, spec, g, pit, others, old, _CityView(dc, city["solid"]),
                         city_blocks=city_blocks_of(box), others_definite=others_definite)
    # the cordon, independently of the superseded generator
    rm, (RX0, RZ0, _RX1, _RZ1), _n = RD.region_mask(spec["measured"]["region_containment"]["region"], a.source_root)
    edge = []
    H, W = rm.shape
    for i in range(H):
        for j in range(W):
            if rm[i, j] and any(not (0 <= i + di < H and 0 <= j + dj < W) or not rm[i + di, j + dj]
                                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                edge.append((j + RX0, i + RZ0))
    undo = {}
    for n in order:
        if n == "undo" or n.startswith("undo_"):
            for w in fns[n]:
                for c in cells(w):
                    undo[c] = base(w[6])
    left = cordon_check(undo, edge, g, dc)
    if left:
        problems.append(("cordon", "%d cells of the old fence's band on the region's %d edge columns are not cleared, "
                                   "e.g. %s" % (len(left), len(edge), left[:3])))
    print("swept packs: %s" % ", ".join("%s (%d cells in the box)" % (k, len(v)) for k, v in sorted(others.items())))
    print("carve air %d (HQ's way down %d); shell cells %d; undo %d (%d to air, %d to ground); relic edge columns %d"
          % (st.get("air", 0), st.get("hq_air", 0), st.get("shell", 0), st.get("undo", 0), st.get("undo_air", 0),
             st.get("undo_ground", 0), len(edge)))
    print("route from %s: %d places, via %s" % (st.get("route_from"), st.get("route_cells", 0), st.get("route_via")))
    kinds = {}
    for k, msg in problems:
        kinds.setdefault(k, []).append(msg)
    for k in ("carve", "hq", "route", "shell", "zone", "undo", "cordon", "nonempty"):
        got = kinds.get(k, [])
        print("%-9s %s" % (k, "clean" if not got else "%d PROBLEM(S): %s" % (len(got), "; ".join(got[:3]))))
    print("relic_underground audit: %s" % ("CLEAN" if not problems else "%d PROBLEMS" % len(problems)))
    return 0 if not problems else 1


class _CityView:
    """`c in view` -> does the Deep's city pack write c; view.get("solid") -> the cells it writes a block into;
    view["all"] -> every cell it writes."""

    def __init__(self, all_, solid):
        self._all, self._solid = all_, solid

    def __contains__(self, c):
        return c in self._all

    def get(self, k, d=None):
        return {"solid": self._solid, "all": self._all}.get(k, d)

    def __getitem__(self, k):
        return {"solid": self._solid, "all": self._all}[k]


if __name__ == "__main__":
    sys.exit(main())
