#!/usr/bin/env python
"""Independent offline audit of the written Wardenhold pack (build/datapacks/cobblers_frostpeak_keep).

It reads the pack's function text back into blocks and checks them against sources the generator does not use to decide
them. NOTHING is imported from tools/frostpeak_keep.py (asserted by tests/test_frostpeak_keep.py).

  the ground        tools/ground.py, per column (rounded: the canonical heightmap)
  the site          data/frostpeak_keep.json site.centre and dims.base_hu/base_hv (the record), data/regions.json
                    frostpeak_strand's polygon (own point-in-polygon), data/spawn_blocks.json
  Highwire          data/towns.json gym3_town footprint (the streets) and data/placements.json gym3_gym_building
                    (the roofline) -- the observers; Highwire's ground from tools/ground.py
  the players       a small walking model of its own (standable cells, jumps of one, drops of three, ladders)

Checks (each must hold):

  K0  pack           the pack has one function and it parses
  K1  courtyard      the courtyard floor (the pad) is the highest ground under the base rectangle, and the cleared box
                     starts one above it and spans exactly the rectangle
  K2  strand         the base rectangle lies wholly inside frostpeak_strand's polygon
  K3  bounds         every write within the rectangle's reach; nothing digs into the ground except one 3-wide lane
                     south of the keep
  K4  spawn/light    no written block is a spawn condition, emits light, or is a chest, bed or bell; the only block
                     entities are wall signs (and an empty lectern, barrels and a campfire that is not lit); no sign
                     line is over 15 characters
  K5  support        every written solid block is joined to the ground (no floating piece)
  K6  snow           the roofs are white (the column tops over ry 27 are snow, blue ice, packed ice or a finial) and the
                     masonry carries snow layers
  K7  sightline      from Highwire's streets and the gym roofline, with the terrain only (the heightmap raised by the
                     pack's plinth): the spire's finial is seen from every street point and most of the roofline, the
                     beacon arcade from 9 of 10 street points, and the spire shows at least 30 blocks from the belvedere
  K8  reciprocal     from the beacon arcade the town is seen: the belvedere and 8 of 10 street points
  K9  walking        from the north approach a player walks to the courtyard, the hall, the archive, the loft, the keep
                     roof and the beacon floor; from the hill south of the postern a player walks to the courtyard;
                     every sign is within reach of a standable cell
  K10 limits         tools/function_limits.py finds nothing the server would refuse
  K11 non-empty      enough written to be a castle

  python tools/frostpeak_keep_audit.py [--pack DIR] [--source-root R]   exit 1 on any problem
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_frostpeak_keep"
OUT = ROOT / "derived" / "frostpeak_keep" / "audit.json"
SETBLOCK = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (.+)$")
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)$")
EMITS = re.compile(r"(lantern|torch|glowstone|shroomlight|froglight|candle|beacon|magma|end_rod|redstone_lamp|"
                   r"glow_lichen|jack_o_lantern|lava)$|^minecraft:(soul_)?fire$|^minecraft:light$")
FORBIDDEN = re.compile(r"(chest|_bed$|^minecraft:bell$|shulker|spawner|hopper|furnace|smoker)")
FREE = ("air", "snow", "ladder", "spruce_wall_sign")
CLIMB = "ladder"
EYE = 1.62
BIG_AIR = 5000
SNOWY_TOPS = ("snow_block", "blue_ice", "packed_ice", "stone_brick_wall")
WORLD_READS: set = set()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def name_of(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def short(state):
    return name_of(state).replace("minecraft:", "")


def replay(lines):
    """({(x, y, z): state} of non-air writes, [air boxes], [every air write box]) after every setblock and fill."""
    blocks, airs, other = {}, [], []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("forceload "):
            continue
        m = SETBLOCK.match(line)
        if m:
            x, y, z, s = m.groups()
            k = (int(x), int(y), int(z))
            if name_of(s) == "minecraft:air":
                blocks.pop(k, None)
                airs.append(k + k)
            else:
                blocks[k] = s
            continue
        m = FILL.match(line)
        if m:
            x0, y0, z0, x1, y1, z1, s = m.groups()
            x0, x1 = sorted((int(x0), int(x1)))
            y0, y1 = sorted((int(y0), int(y1)))
            z0, z1 = sorted((int(z0), int(z1)))
            if name_of(s) == "minecraft:air":
                airs.append((x0, y0, z0, x1, y1, z1))
                if (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1) <= BIG_AIR:
                    for x in range(x0, x1 + 1):
                        for y in range(y0, y1 + 1):
                            for z in range(z0, z1 + 1):
                                blocks.pop((x, y, z), None)
                continue
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    for z in range(z0, z1 + 1):
                        blocks[(x, y, z)] = s
            continue
        other.append(line)
    return blocks, airs, other


def pack_lines(pack):
    out = {}
    for f in sorted(Path(pack).glob("data/*/function/**/*.mcfunction")):
        out[str(f.relative_to(pack))] = f.read_text(encoding="utf-8").splitlines()
    return out


def in_polygon(x, z, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % n]
        if (z0 > z) != (z1 > z) and x < x0 + (z - z0) * (x1 - x0) / (z1 - z0):
            inside = not inside
    return inside


class Report:
    def __init__(self):
        self.rows = []

    def check(self, ok, name, detail=""):
        self.rows.append({"check": name, "ok": bool(ok), "detail": "" if ok else detail})

    @property
    def problems(self):
        return [r for r in self.rows if not r["ok"]]


# ------------------------------------------------------------------------------------------------ sight lines
class Terrain:
    """The ground's top surface (round(h) + 1) with the pack's blocks at or below the courtyard floor laid over it."""

    def __init__(self, g, blocks, pad):
        self.g = g
        self.over = {}
        for (x, y, z) in blocks:
            if y <= pad and y + 1 > self.over.get((x, z), -1):
                self.over[(x, z)] = y + 1

    def top(self, x, z):
        return max(self.g(x, z) + 1, self.over.get((x, z), -1))

    def clear(self, eye, tgt):
        """True when the straight segment eye -> tgt clears every ground column in between (flat world)."""
        (x0, y0, z0), (x1, y1, z1) = eye, tgt
        d = math.hypot(x1 - x0, z1 - z0)
        n = int(d)
        for i in range(1, n):
            t = i / d
            if self.top(round(x0 + (x1 - x0) * t), round(z0 + (z1 - z0) * t)) > y0 + (y1 - y0) * t:
                return False
        return True


def find(o, pred):
    """The first dict anywhere in o for which pred is true."""
    if isinstance(o, dict):
        if pred(o):
            return o
        for v in o.values():
            r = find(v, pred)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = find(v, pred)
            if r is not None:
                return r
    return None


def observers(g):
    towns = load_json(ROOT / "data" / "towns.json")
    t = find(towns, lambda d: d.get("id") == "gym3_town" and "footprint" in d)
    fp = t["footprint"]
    xs = (fp["min_x"] + 4, (fp["min_x"] + fp["max_x"]) // 2, fp["max_x"] - 3)
    zs = (fp["min_z"] + 4, (fp["min_z"] + fp["max_z"]) // 2, fp["max_z"] - 3)
    streets = {"belvedere": (xs[2] - 12, g(xs[2] - 12, fp["min_z"]) + 1 + EYE, fp["min_z"])}
    for x in xs:
        for z in zs:
            streets["street(%d,%d)" % (x, z)] = (x, g(x, z) + 1 + EYE, z)
    pl = load_json(ROOT / "data" / "placements.json")
    gym = next(s for s in pl["placements"] if s.get("id") == "gym3_gym_building")
    roof = gym["position"]["y"] + gym["size"][1]
    plan_rect = next(b for b in pl["settlements"]["gym3_town"]["plan"]["anchors"] if b["id"] == "gym3_gym")["rect"]
    gx = (plan_rect[0] + plan_rect[2]) // 2
    gz = (plan_rect[1] + plan_rect[3]) // 2
    roofline = {"gym roof(%d,%d)" % (gx, z): (gx, roof + EYE, z) for z in (gz - 14, gz, gz + 14)}
    return streets, roofline


# ------------------------------------------------------------------------------------------------ the walking model
class World:
    """The written blocks over the natural ground inside `box` (x0, z0, x1, z1); a walker never leaves the box."""

    def __init__(self, blocks, airs, g, box):
        self.b = {k: short(v) for k, v in blocks.items()}
        self.box = box
        self.ground = g.box(*box)

    def inside(self, x, z):
        return self.box[0] <= x <= self.box[2] and self.box[1] <= z <= self.box[3]

    def state(self, x, y, z):
        s = self.b.get((x, y, z))
        if s is not None:
            return s
        return "air" if y > self.ground[z - self.box[1], x - self.box[0]] else "natural"

    def free(self, x, y, z):
        return self.state(x, y, z) in FREE

    def solid(self, x, y, z):
        return not self.free(x, y, z)

    def standable(self, x, y, z):
        if not (self.free(x, y, z) and self.free(x, y + 1, z)):
            return False
        return self.state(x, y, z) == CLIMB or self.solid(x, y - 1, z)

    def neighbours(self, c):
        x, y, z = c
        here = self.state(x, y, z)
        if here == CLIMB:                                   # climb: up while the head is clear, down while free
            if self.free(x, y + 2, z) and self.free(x, y + 1, z):
                yield (x, y + 1, z)
            if self.free(x, y - 1, z):
                yield (x, y - 1, z)
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not self.inside(nx, nz):
                continue
            if self.standable(nx, y, nz):
                yield (nx, y, nz)
            # up one: a jump needs the cell above the head free; a stair is walked up (half a block, then half again)
            if (self.free(x, y + 2, z) or self.state(nx, y, nz).endswith("_stairs")) and self.standable(nx, y + 1, nz):
                yield (nx, y + 1, nz)
            if self.free(nx, y, nz) and self.free(nx, y + 1, nz):                  # walk off an edge, fall up to 3
                for drop in range(1, 4):
                    if self.standable(nx, y - drop, nz):
                        if all(self.free(nx, y - k, nz) for k in range(1, drop + 1)):
                            yield (nx, y - drop, nz)
                        break

    def reach(self, start, limit=2_000_000):
        seen = {start}
        q = deque([start])
        while q and len(seen) < limit:
            c = q.popleft()
            for n in self.neighbours(c):
                if n not in seen:
                    seen.add(n)
                    q.append(n)
        return seen


def audit(pack, g):
    doc = load_json(ROOT / "data" / "frostpeak_keep.json")
    rep = Report()
    files = pack_lines(pack)
    rep.check(len(files) == 1, "K0 pack", "expected one function in %s, found %d" % (pack, len(files)))
    if not files:
        return rep
    lines = [l for ls in files.values() for l in ls]
    blocks, airs, other = replay(lines)
    rep.check(not other, "K0 pack", "%d line(s) the audit does not parse, first: %s" % (len(other), other[:1]))

    # ---- K1 the courtyard floor and the cleared box, from the heightmap and the record
    cx, cz = doc["site"]["centre"]
    hu, hv = doc["dims"]["base_hu"], doc["dims"]["base_hv"]
    x0, z0, x1, z1 = cx - hu, cz - hv, cx + hu, cz + hv
    pad = max(g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
    big = [a for a in airs if (a[3] - a[0] + 1) * (a[4] - a[1] + 1) * (a[5] - a[2] + 1) > BIG_AIR]
    # function_limits splits a fill over 32768 blocks, so the one cleared box may arrive as stacked slabs: their union
    union = (min(a[0] for a in big), min(a[1] for a in big), min(a[2] for a in big),
             max(a[3] for a in big), max(a[4] for a in big), max(a[5] for a in big)) if big else None
    vol = sum((a[3] - a[0] + 1) * (a[4] - a[1] + 1) * (a[5] - a[2] + 1) for a in big)
    ok = bool(big) and union[:3:2] == (x0, z0) and union[3:6:2] == (x1, z1) and union[1] == pad + 1         and vol == (x1 - x0 + 1) * (z1 - z0 + 1) * (union[4] - union[1] + 1)
    rep.check(ok, "K1 courtyard", "the cleared box %s should be one box spanning x%d..%d z%d..%d from y%d (the highest ground "
              "under the base rectangle, y%d, plus one)" % (union, x0, x1, z0, z1, pad + 1, pad))
    top_y = max(y for (_x, y, _z) in blocks)
    rep.check(bool(big) and union[4] >= top_y, "K1 courtyard", "the cleared box stops at y%d under a block at y%d" % (union[4] if big else -1, top_y))
    courtyard = sum(1 for (x, y, z) in blocks if y == pad and x0 + 4 <= x <= x1 - 4 and z0 + 4 <= z <= z1 - 4)
    rep.check(courtyard > 1500, "K1 courtyard", "only %d floor blocks at y%d inside the base rectangle" % (courtyard, pad))

    # ---- K2 inside the Strand
    regs = load_json(ROOT / "data" / "regions.json")
    poly = next(r for r in regs["subregions"] if r["id"] == "frostpeak_strand")["polygons"][0]
    outside = [(x, z) for x in range(x0, x1 + 1) for z in (z0, z1) if not in_polygon(x, z, poly)] + \
              [(x, z) for z in range(z0, z1 + 1) for x in (x0, x1) if not in_polygon(x, z, poly)]
    rep.check(not outside, "K2 strand", "%d base-rectangle edge columns outside frostpeak_strand, first %s" % (len(outside), outside[:1]))

    # ---- K3 bounds and digging
    reach = doc["dims"]["batter_reach"] + 6
    hx0, hz0, hx1, hz1 = x0 - reach, z0 - reach, x1 + reach, z1 + reach
    stray = [k for k in blocks if not (hx0 <= k[0] <= hx1 and hz0 <= k[2] <= hz1)]
    rep.check(not stray, "K3 bounds", "%d writes outside the hold box, first %s" % (len(stray), stray[:1]))
    digs = set()
    for (ax0, ay0, az0, ax1, ay1, az1) in airs:
        if (ax1 - ax0 + 1) * (ay1 - ay0 + 1) * (az1 - az0 + 1) > BIG_AIR:
            continue
        for x in range(ax0, ax1 + 1):
            for z in range(az0, az1 + 1):
                if ay0 <= g(x, z):
                    digs.add((x, z))
    dx = [c[0] for c in digs]
    dz = [c[1] for c in digs]
    lane_ok = (not digs) or (max(dx) - min(dx) <= 2 and min(dz) > z1 and max(dz) - min(dz) <= 24)
    rep.check(lane_ok, "K3 bounds", "air is written into the ground over %d columns spanning x%s z%s: only one 3-wide lane south "
              "of the keep may be cut" % (len(digs), (min(dx), max(dx)) if digs else None, (min(dz), max(dz)) if digs else None))

    # ---- K4 spawn conditions, light, containers, signs
    spawn = set(load_json(ROOT / "data" / "spawn_blocks.json")["blocks"])
    names = {}
    for k, s in blocks.items():
        names[name_of(s)] = names.get(name_of(s), 0) + 1
    bad_spawn = sorted(n for n in names if n in spawn)
    rep.check(not bad_spawn, "K4 spawn/light", "spawn-condition blocks written: %s" % bad_spawn)
    bad_light = sorted(n for n in names if EMITS.search(n) or FORBIDDEN.search(n))
    rep.check(not bad_light, "K4 spawn/light", "light emitters or forbidden containers written: %s" % bad_light)
    lit = [s for s in blocks.values() if short(s) == "campfire" and "lit=true" in s]
    rep.check(not lit, "K4 spawn/light", "a lit campfire is written")
    nbt = [(k, s) for k, s in blocks.items() if "{" in s]
    non_sign = [(k, s[:60]) for k, s in nbt if short(s) != "spruce_wall_sign"]
    rep.check(not non_sign, "K4 spawn/light", "block entities other than signs carry data: %s" % non_sign[:2])
    longest = 0
    for k, s in nbt:
        for msg in re.findall(r"'\"((?:[^\"\\]|\\.)*)\"'", s):
            longest = max(longest, len(msg))
    rep.check(longest <= 15, "K4 spawn/light", "a sign line is %d characters (the most a sign shows is about 15)" % longest)
    rep.check(len(nbt) >= 6, "K4 spawn/light", "only %d signs: the Wardens' log is missing" % len(nbt))

    # ---- K5 support: every written solid block is joined to the ground
    solid = {k for k, s in blocks.items() if short(s) not in ("snow",)}
    seen, q = set(), deque()
    for (x, y, z) in solid:
        if y <= g(x, z) + 1:
            seen.add((x, y, z))
            q.append((x, y, z))
    while q:
        x, y, z = q.popleft()
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (x + d[0], y + d[1], z + d[2])
            if n in solid and n not in seen:
                seen.add(n)
                q.append(n)
    floating = solid - seen
    rep.check(not floating, "K5 support", "%d written blocks are not joined to the ground, first %s" % (len(floating), sorted(floating)[:1]))

    # ---- K6 snow
    colt = {}
    for (x, y, z), s in blocks.items():
        if short(s) != "snow" and y > colt.get((x, z), (-9999, ""))[0]:
            colt[(x, z)] = (y, short(s))
    high = {c: v for c, v in colt.items() if v[0] >= pad + 33}
    white = sum(1 for v in high.values() if v[1] in SNOWY_TOPS)
    rep.check(bool(high) and white >= 0.95 * len(high), "K6 snow", "%d of %d column tops over ry 32 (above the keep's battlements) are white" % (white, len(high)))
    layers = sum(1 for s in blocks.values() if short(s) == "snow")
    rep.check(layers >= 500, "K6 snow", "only %d snow layers on the masonry" % layers)

    # ---- K7 / K8 sightlines
    streets, roofline = observers(g)
    terrain = Terrain(g, blocks, pad)
    spire_cols = [(c, v[0]) for c, v in colt.items() if v[0] == top_y]
    finial = (spire_cols[0][0][0], top_y, spire_cols[0][0][1]) if spire_cols else None
    if finial:
        tgt = (finial[0] + 0.5, finial[1] + 0.5, finial[2] + 0.5)
        seen_by = [n for n, e in streets.items() if terrain.clear(e, tgt)]
        seen_gym = [n for n, e in roofline.items() if terrain.clear(e, tgt)]
        rep.check(len(seen_by) == len(streets), "K7 sightline",
                  "the finial (%s) is seen from %d of %d street points, not %s" % (finial, len(seen_by), len(streets), sorted(set(streets) - set(seen_by))))
        rep.check(len(seen_gym) >= 2, "K7 sightline", "the finial is seen from %d of 3 roofline points" % len(seen_gym))
        # the spire's shaft: how many of its blocks (the finial's column and the chamber's) the belvedere sees
        sx, sz = finial[0], finial[2]
        eye = streets["belvedere"]
        y = top_y
        while y > pad and terrain.clear(eye, (sx + .5, y - .5, sz + .5)):
            y -= 1
        shown = top_y - y
        rep.check(shown >= 30, "K7 sightline", "the belvedere sees the spire's axis from y%d up: %d blocks below the finial (needs 30)" % (y + 1, shown))
        arc_y = pad + doc["dims"]["spire_floor"] + 3
        arcade = (sx, arc_y, sz)
        arc_by = [n for n, e in streets.items() if terrain.clear(e, (arcade[0] + .5, arcade[1] + .5, arcade[2] + .5))]
        rep.check(len(arc_by) >= 9, "K7 sightline", "the beacon arcade (y%d) is seen from %d of 10 street points" % (arc_y, len(arc_by)))
        # K8: from the arcade, Highwire
        ceye = (sx + .5, arc_y + .5 + EYE - 0.5, sz + .5)
        back = [n for n, e in streets.items() if terrain.clear(ceye, e)]
        rep.check("belvedere" in back and len(back) >= 8, "K8 reciprocal",
                  "from the beacon arcade the town is seen from %d of 10 street points (belvedere %s)" % (len(back), "belvedere" in back))
    else:
        rep.check(False, "K7 sightline", "no spire column found")

    # ---- K9 walking
    W = World(blocks, airs, g, (hx0, hz0, hx1, hz1))
    kc = doc["dims"]["keep_cv"]
    sf = doc["dims"]["spire_floor"]
    kr = doc["dims"]["keep_roof"]
    north = (cx, g(cx, z0 - 30) + 1, z0 - 30)
    r1 = W.reach(north)
    goals = {"courtyard": (cx, pad + 1, cz - 10), "the hall": (cx + 3, pad + 1, cz + kc - 1), "the archive": (cx + 2, pad + 11, cz + kc + 2),
             "the loft": (cx - 2, pad + 21, cz + kc + 2), "the keep roof": (cx + 7, pad + kr + 1, cz + kc), "the beacon floor": (cx + 1, pad + sf + 1, cz + kc)}
    missing = [k for k, c in goals.items() if c not in r1]
    rep.check(not missing, "K9 walking", "from the north approach (%s) a player cannot walk to: %s (%d cells reached)" % (north, missing, len(r1)))
    south = (cx - 14, g(cx - 14, z1 + 22) + 1, z1 + 22)
    r2 = W.reach(south)
    rep.check(goals["courtyard"] in r2, "K9 walking", "from the hill south of the postern %s a player cannot walk to the courtyard (%d cells)" % (south, len(r2)))
    unread = []
    for (x, y, z), s in blocks.items():
        if short(s) == "spruce_wall_sign":
            if not any((x + i, y - j, z + k) in r1 for i in range(-3, 4) for j in range(0, 5) for k in range(-3, 4)):
                unread.append((x, y, z))
    rep.check(not unread, "K9 walking", "%d signs have no standable cell within 3 blocks: %s" % (len(unread), unread[:2]))

    # ---- K10 limits, K11 non-empty
    bad = function_limits.check_lines(lines, "frostpeak_keep/build")
    rep.check(not bad, "K10 limits", "tools/function_limits.py: %s" % (bad[:2],))
    count = {"blocks": len(blocks), "snow_block": sum(1 for s in blocks.values() if short(s) == "snow_block"),
             "packed_ice": sum(1 for s in blocks.values() if short(s) == "packed_ice"),
             "blue_ice": sum(1 for s in blocks.values() if short(s) == "blue_ice"), "ladders": sum(1 for s in blocks.values() if short(s) == "ladder"),
             "stairs": sum(1 for s in blocks.values() if short(s).endswith("_stairs")), "signs": len(nbt)}
    need = {"blocks": 20000, "snow_block": 600, "packed_ice": 300, "blue_ice": 30, "ladders": 60, "stairs": 60, "signs": 6}
    low = {k: (count[k], v) for k, v in need.items() if count[k] < v}
    rep.check(not low, "K11 non-empty", "too little written (have, need): %s" % low)
    rep.counts = dict(count, pad=pad, top_y=top_y, reached_from_north=len(r1), reached_from_south=len(r2))
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    g = G.Ground(a.source_root)
    rep = audit(a.pack, g)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": rep.rows, "counts": getattr(rep, "counts", {})}, indent=1) + "\n", encoding="utf-8")
    if rep.problems:
        for p in rep.problems:
            print("PROBLEM %s: %s" % (p["check"], p["detail"]))
        return 1
    print("CLEAN: %d checks over %s; counts %s" % (len(rep.rows), a.pack, getattr(rep, "counts", {})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
