#!/usr/bin/env python
"""Victory Road: the gauntlet out of the wound, from the Deep's floor to the League's apron.

One road, not a maze. A spine of long straight runs with slow bends, authored in data/victory_road.json and
threaded through five caverns, inside the corridor the owner traced as entrance_to_e4 and then into e4_tower. It
ticks uphill, dips twice, climbs the last 36 in a switchback stair, and opens on the League's own apron seven
blocks from the door. Ten trainer stands and one rest station, both marked and unstaffed.

Schema 1 built a labyrinth here -- four stacked galleries on a 16-block lattice, each a pruned spanning tree,
ending on a shelf 400 blocks short of the tower. The owner replaced it on 2026-09-24: large corridors and gaping
caves, relatively straight, all the way to the tower, about ten fights and a rest station inside.

Light is a difficulty setting. fightorflight makes Dark and Ghost types more aggressive at or below block light 7
and calmer at or above 12, the light block emits 15, and block light falls one per block of travel; so the road is
lit from the floor where a fight starts and dark between. `light` reports the distribution the build produces
without needing a server.

Ground comes from the canonical heightmap, never from a world; `verify` reads a world only to check.

    python tools/victory_road.py build  --source-root <root> [--server-dir <server>]
    python tools/victory_road.py light  --source-root <root>
    python tools/victory_road.py verify --world <stopped world copy>
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

import function_limits as FL

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "victory_road.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_victory_road"
BACKFILL_OUT = ROOT / "build" / "datapacks" / "cobblers_vr_backfill"
PLAN = ROOT / "derived" / "victory_road" / "plan.json"
TILE = 64
PART = 3500

WORLD_READS = {"verify", "main"}


class RoadError(Exception):
    pass


def h3(x, y, z, salt):
    a = (np.asarray(x, np.int64) * 73856093) ^ (np.asarray(y, np.int64) * 19349663) \
        ^ (np.asarray(z, np.int64) * 83492791) ^ np.int64(salt * 2654435761)
    a &= np.int64(0x7FFFFFFF)
    a = (a ^ (a >> 15)) * np.int64(2246822519)
    a &= np.int64(0x7FFFFFFF)
    a = (a ^ (a >> 13)) * np.int64(3266489917)
    return a & np.int64(0x7FFFFFFF)


def unit(x, y, z, salt):
    return h3(x, y, z, salt) / float(0x7FFFFFFF)


def installed_blocks(server_dir):
    import glob
    import re
    import zipfile
    if not server_dir:
        return None
    import runtime_guard
    runtime_guard.require_lock("read the server's mod jars")
    mods = runtime_guard.check(Path(server_dir) / "mods", "read the mod jars in")
    ids = set()
    for jar in glob.glob(str(mods / "*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except (zipfile.BadZipFile, OSError):  # not a readable jar
            continue
        for n in z.namelist():
            m = re.match(r"assets/([^/]+)/blockstates/([^/]+)\.json$", n)
            if m:
                ids.add("%s:%s" % m.groups())
    return ids


def pick(block, fallback, have):
    return block if block.startswith("minecraft:") or have is None or block in have else fallback


def densify(points):
    """The spine at one-block spacing: [(x, y, z)] a player could walk along."""
    out = []
    for (ax, ay, az), (bx, by, bz) in zip(points, points[1:]):
        n = max(abs(bx - ax), abs(bz - az), abs(by - ay))
        for k in range(n):
            f = k / float(n)
            out.append((int(round(ax + (bx - ax) * f)), int(round(ay + (by - ay) * f)),
                        int(round(az + (bz - az) * f))))
    out.append(tuple(points[-1]))
    return out


def grades(points):
    """[(leg index, rise over run)] for every leg of the spine."""
    out = []
    for i, ((ax, ay, az), (bx, by, bz)) in enumerate(zip(points, points[1:])):
        run = math.hypot(bx - ax, bz - az)
        out.append((i, abs(by - ay) / run if run else float("inf")))
    return out


class Site:
    """The lines the build emits, in the four passes the order depends on.

    walls  every wall and ceiling, before any air is cut. A chamber that wrote its own shell as it went would seal
           the corridor that runs into it.
    air    everything hollowed out, in one pass, so no carve can undo another's.
    floor  the floor AFTER the air, not with the walls. On a climbing leg the air box of one step reaches down over
           the floor the next step lays, so a floor written in the first pass is eaten away wherever the road
           rises: the exit ramp came out as a four-deep trench and every graded leg had its floor dropped behind
           the grade (found in the world on 2026-09-24, six audit mismatches).
    after  everything that stands in the finished space: the rest station, the landmark, the stands and the light.
    """

    def __init__(self):
        self.solid, self.air, self.after = [], [], []
        self.floor_at = {}
        self.checks, self.counts = [], {}

    def count(self, k, v=1):
        self.counts[k] = self.counts.get(k, 0) + v

    def fill(self, pas, x0, y0, z0, x1, y1, z1, block):
        pas.append("fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, block))

    def set(self, pas, x, y, z, block):
        pas.append("setblock %d %d %d %s" % (x, y, z, block))

    def put_floor(self, x, z, y, block, dist):
        """One floor block per column, at the height of whichever feature's middle is nearest it.

        Written once, not once per covering step: a graded leg covers a column from up to nine steps at nine
        different heights, and writing them all packs the corridor solid up to the highest of them.
        """
        old = self.floor_at.get((x, z))
        if old is None or dist < old[0]:
            self.floor_at[(x, z)] = (dist, y, block)

    def floor_lines(self):
        return ["setblock %d %d %d %s" % (x, y, z, b)
                for (x, z), (_d, y, b) in sorted(self.floor_at.items())]


def carve_run(site, a, b, w, h, wall, floor):
    """A length of corridor: rock around it and under it in the first pass, air through the middle in the second."""
    (ax, ay, az), (bx, by, bz) = a, b
    n = max(abs(bx - ax), abs(bz - az), abs(by - ay))
    half = w // 2
    for k in range(n + 1):
        f = k / float(max(1, n))
        cx = int(round(ax + (bx - ax) * f))
        cz = int(round(az + (bz - az) * f))
        cy = int(round(ay + (by - ay) * f))
        for dx in range(-half - 1, half + 2):
            for dz in range(-half - 1, half + 2):
                X, Z = cx + dx, cz + dz
                if abs(dx) > half or abs(dz) > half:
                    site.fill(site.solid, X, cy - 1, Z, X, cy + h, Z, wall)
                else:
                    site.put_floor(X, Z, cy - 1, floor, abs(dx) + abs(dz))
                    site.set(site.solid, X, cy + h, Z, wall)
                    site.fill(site.air, X, cy, Z, X, cy + h - 1, Z, "minecraft:air")
        site.count("corridor blocks", (w + 2) * (w + 2) * (h + 2))


def dome(cy, height, rr):
    """The cavern's ceiling at a fraction rr of its radius: flattened over the middle so it reads as a cave."""
    return cy + max(4, int(round(height * math.sqrt(max(0.0, 1.0 - rr ** 3)))))


def chamber_cover(g, cx, cy, cz, radius, height):
    """The least rock left between a cavern's dome and the canonical ground."""
    # g.box, not g(...): see the note in build
    gb = g.box(cx - radius, cz - radius, cx + radius, cz + radius)
    zz, xx = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    rr = np.hypot(xx, zz) / float(radius)
    top = cy + np.maximum(4, np.round(height * np.sqrt(np.maximum(0.0, 1.0 - rr ** 3))))
    return int((gb - (top + 2))[rr <= 1.0].min())


def carve_chamber(site, cx, cy, cz, radius, height, wall, floor):
    """A gaping cave: a domed room with a flat floor, carved on the spine so the road runs straight through it."""
    cols = 0
    for dx in range(-radius, radius + 1):
        for dz in range(-radius, radius + 1):
            rr = math.hypot(dx, dz) / float(radius)
            if rr > 1.0:
                continue
            X, Z = cx + dx, cz + dz
            top = dome(cy, height, rr)
            site.put_floor(X, Z, cy - 1, floor, abs(dx) + abs(dz))
            site.fill(site.solid, X, top + 1, Z, X, top + 2, Z, wall)
            site.fill(site.air, X, cy, Z, X, top, Z, "minecraft:air")
            cols += 1
    site.count("cavern columns", cols)
    return cols


def disc_grid(cx, cz, radius, spacing):
    """Grid points inside a disc, on a world-aligned lattice so a rebuild puts them in the same places."""
    out = []
    for X in range(cx - radius, cx + radius + 1):
        if X % spacing:
            continue
        for Z in range(cz - radius, cz + radius + 1):
            if Z % spacing:
                continue
            if math.hypot(X - cx, Z - cz) <= radius:
                out.append((X, Z))
    return out


def region_test(spec, source_root, RD):
    """A (x, z) -> bool over the union of the owner's traced regions the road is allowed inside."""
    masks = []
    for rid in spec["regions"]["inside"]:
        m, (X0, Z0, _X1, _Z1), _n = RD.region_mask(rid, source_root)
        masks.append((m, X0, Z0))

    def inside(x, z):
        for m, X0, Z0 in masks:
            iz, ix = z - Z0, x - X0
            if 0 <= iz < m.shape[0] and 0 <= ix < m.shape[1] and m[iz, ix]:
                return True
        return False
    return inside


def carve_stair(site, sx, sy, sz, hw, hl, top_y, legs, wall, floor):
    """A switchback stair in a hall: the climb a player feels, and the route up it."""
    x0, x1 = sx - hw // 2, sx + hw // 2
    z0, z1 = sz - hl // 2, sz + hl // 2
    for X in range(x0 - 1, x1 + 2):
        for Z in range(z0 - 1, z1 + 2):
            if X < x0 or X > x1 or Z < z0 or Z > z1:
                site.fill(site.solid, X, sy - 1, Z, X, top_y + 3, Z, wall)
            else:
                site.put_floor(X, Z, sy - 1, floor, abs(X - sx) + abs(Z - sz))
                site.fill(site.solid, X, top_y + 3, Z, X, top_y + 4, Z, wall)
                site.fill(site.air, X, sy, Z, X, top_y + 2, Z, "minecraft:air")
    site.count("stair hall blocks", (hw + 2) * (hl + 2) * (top_y + 5 - sy))
    # Consecutive legs run in SEPARATE LANES, west then east, joined by a landing across the whole hall. A stair
    # whose legs both used the full width put each leg's treads at the head height of the one below it near the
    # turn, where the two converge: air at the feet and rock at the head, and a player stopped dead (found by the
    # test author on 2026-09-24, four positions at two turns).
    lanes = (range(x0 + 1, sx), range(sx + 1, x1))
    rise = top_y - sy
    per = rise / float(legs)
    route = []

    def tread(xs, Z, y):
        for X in xs:
            site.set(site.after, X, y - 1, Z, floor)
            site.fill(site.after, X, y, Z, X, y + 3, Z, "minecraft:air")

    for L in range(legs):
        za, zb = (z1 - 3, z0 + 3) if L % 2 == 0 else (z0 + 3, z1 - 3)
        ya, yb = int(round(sy + per * L)), int(round(sy + per * (L + 1)))
        xs = lanes[L % 2]
        mx = (min(xs) + max(xs)) // 2
        n = abs(zb - za)
        for k in range(n + 1):
            f = k / float(n)
            Z = int(round(za + (zb - za) * f))
            y = int(round(ya + (yb - ya) * f))
            tread(xs, Z, y)
            route.append((mx, y, Z))
        # The landing: flat, the full width of the hall, so the next leg can start in the other lane. It runs
        # PAST the end of the leg, never back over it: a landing centred on the turn put its own floor at the head
        # height of the last three treads below it, and the route was solid rock there.
        step = 1 if zb > za else -1
        for Z in range(min(zb, zb + 3 * step), max(zb, zb + 3 * step) + 1):
            tread(range(x0 + 1, x1), Z, yb)
        route.append((sx, yb, zb))
        if L == legs - 1:
            # the top landing is also the way out, and the exit ramp starts where it ends: begun at the turn
            # instead, the ramp's first floor blocks were inside this landing's air and a player stepped into a
            # three-block hole at the head of the stair
            route.append((sx, yb, zb + 3 * step))
        site.count("stair legs")
    return route


def carve_exit(site, top, target, ramp_from_z, w, h, wall, floor):
    """From the stair's top out onto the League's apron: a covered ramp, then an open cut in the apron itself."""
    tx, ty, tz = top
    ex, ey, ez = target
    route = []
    n = max(abs(ex - tx), abs(ez - tz), abs(ey - ty))
    half = w // 2
    for k in range(n + 1):
        f = k / float(max(1, n))
        cx = int(round(tx + (ex - tx) * f))
        cz = int(round(tz + (ez - tz) * f))
        cy = int(round(ty + (ey - ty) * f))
        roofed = cz > ramp_from_z
        for dx in range(-half - 1, half + 2):
            for dz in range(-half - 1, half + 2):
                X, Z = cx + dx, cz + dz
                if abs(dx) > half or abs(dz) > half:
                    site.fill(site.solid, X, cy - 1, Z, X, cy + h, Z, wall)
                else:
                    site.put_floor(X, Z, cy - 1, floor, abs(dx) + abs(dz))
                    if roofed:
                        site.set(site.solid, X, cy + h, Z, wall)
                    site.fill(site.air, X, cy, Z, X, cy + h - 1 + (0 if roofed else 6), Z, "minecraft:air")
        route.append((cx, cy, cz))
        site.count("exit ramp blocks", (w + 2) * (w + 2) * (h + 2))
    return route


def build_rest(site, spec, cx, cy, cz, have, light_b):
    """The rest station: a walled room in the middle cavern, lit to calm over its whole floor."""
    r = spec["rest"]
    wx, wz = r["size"]
    wall_b = pick(r["wall"], r["wall_fallback"], have)
    floor_b = pick(r["floor"], r["floor_fallback"], have)
    x0, x1 = cx - wx // 2, cx + wx // 2
    z0, z1 = cz - wz // 2, cz + wz // 2
    top = cy + 5
    # built after the cavern is hollow, so the walls stand rather than being carved back out
    site.fill(site.after, x0, cy - 1, z0, x1, top, z1, wall_b)
    site.fill(site.after, x0 + 1, cy, z0 + 1, x1 - 1, top - 1, z1 - 1, "minecraft:air")
    site.fill(site.after, x0 + 1, cy - 1, z0 + 1, x1 - 1, cy - 1, z1 - 1, floor_b)
    # A door on each of the two faces the road runs through, four high and five wide. The room's floor is flat and
    # the road through this cavern is on a grade, so a player meets the doorway a block or two above the room's
    # own floor; a three-high opening left them crouching through it.
    for dz in (-1, 1):
        gz = cz + dz * (wz // 2)
        site.fill(site.after, cx - 2, cy, gz, cx + 2, cy + 3, gz, "minecraft:air")
    # the lattice is anchored to the ROOM, not to the world grid: world-aligned it left the two low edges two
    # blocks from the nearest source, and 13 of 169 floor cells read 10 or 11 where the spec promises calm
    sp = spec["light"]["tiers"]["rest"]["spacing"]
    for i, X in enumerate(range(x0 + 1, x1)):
        for j, Z in enumerate(range(z0 + 1, z1)):
            if i % sp == 0 and j % sp == 0:
                site.set(site.after, X, cy - 1, Z, light_b)
    site.set(site.after, cx, cy - 1, cz, r["marker"])
    # the marker stands on a lattice point, so it takes a light out of the middle of the room and left five floor
    # cells at 10 or 11 where the spec promises calm: put that light back around it
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        site.set(site.after, cx + dx, cy - 1, cz + dz, light_b)
    site.checks.append((cx, cy - 1, cz, [r["marker"]], "rest marker"))
    site.checks.append((x0, cy + 2, z0, [wall_b], "rest wall"))
    site.checks.append((cx, cy + 1, cz, ["minecraft:air"], "rest open"))
    site.count("rest station", 1)
    return [x0, cy, z0, x1, top, z1]


def place_stands(spec, walk, spine, named, chambers, rest_box, last):
    """Ten fights: one in the corridor approaching each cavern, one in each cavern that is not the rest, one at
    the head of the stair."""
    idx = {}
    for k, (X, _Y, Z) in enumerate(walk):
        idx.setdefault((X, Z), k)

    def at(name):
        x, _y, z = spine[named[name]]
        return idx.get((x, z), min(range(len(walk)), key=lambda k: abs(walk[k][0] - x) + abs(walk[k][2] - z)))

    marks, prev = [], 0
    for ch in spec["chambers"]:
        name = ch["at"]
        k = at(name)
        marks.append(("corridor before %s" % name, (prev + k) // 2))
        if not chambers[name][5].get("rest"):
            marks.append((name, k))
        prev = k
    marks.append(("the head of the stair", last))
    want = spec["trainers"]["count"]
    if len(marks) != want:
        raise RoadError("laid out %d fights, not %d: %s" % (len(marks), want, [m[0] for m in marks]))
    out = []
    for _why, k in marks:
        X, Y, Z = walk[k]
        if rest_box and rest_box[0] <= X <= rest_box[3] and rest_box[2] <= Z <= rest_box[5]:
            raise RoadError("a trainer stand at %s is inside the rest station" % ((X, Y, Z),))
        out.append((X, Y, Z))
    apart = spec["trainers"]["min_apart"]
    for a, b in zip(out, out[1:]):
        d = math.dist((a[0], a[2]), (b[0], b[2]))
        if d < apart:
            raise RoadError("two stands are %d apart, under the %d minimum: %s %s" % (d, apart, a, b))
    return out


def build(source_root, server_dir=None):
    import os
    import ground as G
    import rift_deep as RD
    # the same fallback tools/ground.py makes: without it a missing --source-root died inside region_mask with a
    # TypeError about NoneType instead of saying what was missing
    source_root = source_root or os.environ.get("COBBLERS_SOURCE_ROOT")
    if not source_root:
        raise RoadError("no --source-root and no COBBLERS_SOURCE_ROOT: the heightmap and the owner's tracings "
                        "both live under it")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    have = installed_blocks(server_dir)
    g = G.load(source_root)

    cor = spec["corridor"]
    w, h = cor["width"], cor["height"]
    wall_b = pick(cor["wall"], cor["wall_fallback"], have)
    floor_b = pick(cor["floor"], cor["floor_fallback"], have)
    light_b = pick(spec["light"]["block"], spec["light"]["fallback"], have)
    stand_b = pick(spec["trainers"]["stand"], spec["trainers"]["stand_fallback"], have)

    spine = [(p["x"], p["y"], p["z"]) for p in spec["spine"]]
    named = {p["name"]: i for i, p in enumerate(spec["spine"]) if p.get("name")}

    # ---- the road must stay in the corridor the owner traced, and under rock
    inside = region_test(spec, source_root, RD)
    walk = densify(spine)
    for end in (walk[0], walk[-1]):
        if not inside(end[0], end[2]):
            raise RoadError("the road starts or ends outside %s" % (spec["regions"]["inside"],))
    runs, cur = [], 0
    for (x, _y, z) in walk:
        if inside(x, z):
            if cur:
                runs.append(cur)
            cur = 0
        else:
            cur += 1
    if cur:
        runs.append(cur)
    tol = spec["regions"]["gap_tolerance"]
    if runs and max(runs) > tol:
        raise RoadError("the road runs %d blocks outside %s, over the %d tolerance"
                        % (max(runs), spec["regions"]["inside"], tol))
    # g.box, not g(...): calling the Ground instance resolves to the whole class in tools/ground_rule.py, and one
    # of its methods names a region file, so build would be reported as reading a world. It reads the heightmap.
    cover = [int(g.box(x, z, x, z)[0, 0]) - (y + h) for x, y, z in spine]
    thin = [(i, c) for i, c in enumerate(cover) if c < spec["cover"]["min"]]
    if thin:
        raise RoadError("waypoints with less than %d of rock over the ceiling: %s" % (spec["cover"]["min"], thin))
    steep = [(i, round(gr, 2)) for i, gr in grades(spine) if gr > cor["max_grade"]]
    if steep:
        raise RoadError("legs steeper than %s: %s" % (cor["max_grade"], steep))

    # the mouth has to open on the Deep's floor, which this tool does not build: check the pit's own ground a few
    # blocks beyond it. A mouth short of the pit is a road that starts in solid rock.
    mx, my, mz = spine[0]
    site_mouth = (mx, my, mz + 8)

    site = Site()
    site.checks.append((site_mouth[0], site_mouth[1], site_mouth[2], ["minecraft:air"], "mouth on the pit floor"))
    site.count("waypoints", len(spine))
    site.count("min rock cover over the ceiling", min(cover))
    site.count("blocks of route outside the traced regions", sum(runs))

    # ---- the spine
    for a, b in zip(spine, spine[1:]):
        carve_run(site, a, b, w, h, wall_b, floor_b)

    # ---- the caverns
    chambers, cham_cover = {}, []
    for ch in spec["chambers"]:
        cx, cy, cz = spine[named[ch["at"]]]
        cov = chamber_cover(g, cx, cy, cz, ch["radius"], ch["height"])
        if cov < spec["cover"]["min"]:
            raise RoadError("cavern %s has %d of rock over its dome, under the %d minimum"
                            % (ch["at"], cov, spec["cover"]["min"]))
        cham_cover.append(cov)
        carve_chamber(site, cx, cy, cz, ch["radius"], ch["height"], wall_b, floor_b)
        chambers[ch["at"]] = (cx, cy, cz, ch["radius"], ch["height"], ch)
        site.checks.append((cx, cy + 2, cz, ["minecraft:air"], "cavern open"))
        site.checks.append((cx + ch["radius"] - 3, cy + 2, cz, ["minecraft:air"], "cavern open"))
    site.count("min rock cover over a cavern", min(cham_cover))

    # ---- the landmark: the Rift's own material, in the cavern that exposes it
    lm = spec["landmark"]
    road_cols = {(x, z) for (x, _y, z) in walk}

    def near_route(x, z, d):
        return any((x + dx, z + dz) in road_cols for dx in range(-d, d + 1) for dz in range(-d, d + 1))

    face_b = pick(lm["face"], lm["face_fallback"], have)
    vein_b = pick(lm["vein"], lm["vein_fallback"], have)
    lmk = None
    for _name, (cx, cy, cz, R, _HH, ch) in chambers.items():
        if ch["kind"] != "landmark":
            continue
        lmk = [cx, cy, cz]
        for dx in range(-R, R + 1):
            for dz in range(-R, R + 1):
                rr = math.hypot(dx, dz) / float(R)
                if rr > 1.0 or rr < 0.55:
                    continue                      # the middle of the room stays open floor
                X, Z = cx + dx, cz + dz
                if (X, Z) not in site.floor_at:
                    continue
                # on the column's own floor, not on the cavern's: the road ramps through this cavern, so a face
                # laid at the cavern's floor level stands a block up in the road (found in the world 2026-09-24)
                fy = site.floor_at[(X, Z)][1]
                u = unit(X, cy, Z, 231)
                if u < 0.34:
                    site.set(site.after, X, fy, Z, face_b)
                elif u < 0.40:
                    site.set(site.after, X, fy, Z, lm["seep"])
                if unit(X, cy, Z, 232) < 0.04 and not near_route(X, Z, 3):
                    top = fy + 1 + int(3 + 6 * unit(X, cy, Z, 233))
                    site.fill(site.after, X, fy + 1, Z, X, top, Z, vein_b)
        for ang in (0, 72, 144, 216, 288):
            rx = cx + int(round(math.cos(math.radians(ang)) * R * 0.8))
            rz = cz + int(round(math.sin(math.radians(ang)) * R * 0.8))
            ry = site.floor_at.get((rx, rz), (0, cy - 1, None))[1]
            site.checks.append((rx, ry, rz, [face_b, lm["seep"], vein_b, floor_b, light_b], "landmark"))
        site.count("landmark cavern radius", R)
    if lmk is None:
        raise RoadError("no cavern is the landmark")

    # ---- the stair: the last climb, in one switchback inside a narrow hall
    st = spec["stair"]
    sx, sy, sz = spine[named[st["at"]]]
    hw, hl = st["hall"]
    top_y = st["top_y"]
    stair_route = carve_stair(site, sx, sy, sz, hw, hl, top_y, st["legs"], wall_b, floor_b)
    site.checks.append((sx, top_y + 1, sz - hl // 2 + 2, ["minecraft:air"], "stair top open"))

    # ---- the exit: up inside the League's apron and open on it
    ex, ez = spec["exit"]["at"]
    ey = spec["exit"]["y"]
    exit_route = carve_exit(site, stair_route[-1], (ex, ey, ez), spec["exit"]["ramp_from_z"], w, h,
                            wall_b, floor_b)
    site.checks.append((ex, ey + 1, ez, ["minecraft:air"], "exit open"))
    site.checks.append((ex, ey - 1, ez, [floor_b], "exit floor"))
    stair_top_index = len(walk) + len(stair_route) - 1
    climb_from = len(walk)
    walk = walk + stair_route + exit_route

    # ---- the rest station, built in the finished cavern
    rest_box = None
    for _name, (cx, cy, cz, _R, _HH, ch) in chambers.items():
        if ch.get("rest"):
            rest_box = build_rest(site, spec, cx, cy, cz, have, light_b)
    if rest_box is None:
        raise RoadError("no cavern carries the rest station")

    # ---- the ten fights
    stands = place_stands(spec, walk, spine, named, chambers, rest_box, stair_top_index)
    for (X, Y, Z) in stands:
        site.set(site.after, X, Y - 1, Z, stand_b)
        site.checks.append((X, Y - 1, Z, [stand_b], "trainer stand"))
    site.count("trainer stands", len(stands))

    # ---- light, by tier: calm where a fight starts, dark between
    tiers = spec["light"]["tiers"]
    # Floor light is placed by COLUMN and then dropped onto that column's own floor, never at a height taken from
    # a route point: on a grade the route a few blocks away is a block or two higher, and a light at its level
    # lands at standing height in the middle of the road (found in the world on 2026-09-24).
    # a stand sits on the same lattice its own pool is lit from, and the light is written later, so without this
    # five of the ten stands were buried under a light block (found in the world on 2026-09-24)
    on_a_stand = {(X, Z) for (X, _Y, Z) in stands}
    lit = []
    for _name, (cx, cy, cz, R, _HH, _ch) in chambers.items():
        for (X, Z) in disc_grid(cx, cz, R - 1, tiers["chamber"]["spacing"]):
            if (X, Z) in site.floor_at and (X, Z) not in on_a_stand:
                lit.append((X, site.floor_at[(X, Z)][1], Z))
    rad, sp = tiers["stand"]["radius"], tiers["stand"]["spacing"]
    for (X, Y, Z) in stands:
        for (px, pz) in disc_grid(X, Z, rad, sp):
            if (px, pz) in on_a_stand:
                continue
            fy = site.floor_at.get((px, pz), (0, Y - 1, None))[1]
            # the stair's treads are not in floor_at (a column there has a floor at four different heights), so a
            # stand at the head of the stair would light the hall's own floor 35 blocks under it
            lit.append((px, fy if abs(fy - (Y - 1)) <= 2 else Y - 1, pz))
    # the stair gets its own light, in the treads: it is the last climb and the last fight, and a flat disc of
    # light over a staircase lands half in rock and half in the air over the step below
    for k, (X, Y, Z) in enumerate(stair_route + exit_route):
        if k % tiers["stair"]["every"] == 0:
            lit.append((X, Y - 1, Z))
    for k, (X, Y, Z) in enumerate(walk):
        if k % tiers["corridor"]["every"] == 0:
            lit.append((X, Y + h - 1, Z))
    lit = sorted(set(lit))
    for (X, Y, Z) in lit:
        site.set(site.after, X, Y, Z, light_b)
    for k in range(0, len(lit), max(1, len(lit) // 40)):
        site.checks.append((lit[k][0], lit[k][1], lit[k][2], [light_b], "light"))
    site.count("light blocks", len(lit))

    plan = {"lines": site.solid + site.air + site.floor_lines() + site.after, "checks": site.checks, "counts": site.counts,
            "stands": [list(p) for p in stands], "landmark": lmk,
            "chambers": {k: [v[0], v[1], v[2], v[3]] for k, v in chambers.items()},
            "rest": rest_box, "exit": [ex, ey, ez], "stair_top": [sx, top_y, sz], "climb_from": climb_from,
            "route": [list(p) for p in walk], "light": [list(p) for p in lit]}
    return plan, spec


# ------------------------------------------------------------------ the light the build produces

def light_field(plan):
    """Block light over the road, from the plan's own commands. No server: this is what the build leaves.

    Every block is whatever the plan's last write to it made it, in the order the functions run, so the field is
    the finished space and not an intermediate pass. Light spreads six ways losing one per block, which is how
    Minecraft propagates it, so the number here is the number fightorflight reads. Sky light is not modelled:
    the road is underground, where there is none.
    """
    lines = plan["lines"]
    xs, ys, zs = [], [], []
    for ln in lines:
        t = ln.split()
        if t[0] == "fill":
            xs += [int(t[1]), int(t[4])]
            ys += [int(t[2]), int(t[5])]
            zs += [int(t[3]), int(t[6])]
        else:
            xs.append(int(t[1]))
            ys.append(int(t[2]))
            zs.append(int(t[3]))
    X0, X1, Y0, Y1, Z0, Z1 = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    shape = (Y1 - Y0 + 1, Z1 - Z0 + 1, X1 - X0 + 1)
    air = np.zeros(shape, bool)
    src = np.zeros(shape, np.uint8)
    light_b = None
    for ln in lines:
        t = ln.split()
        if t[0] == "fill":
            a = (slice(int(t[2]) - Y0, int(t[5]) - Y0 + 1), slice(int(t[3]) - Z0, int(t[6]) - Z0 + 1),
                 slice(int(t[1]) - X0, int(t[4]) - X0 + 1))
            block = t[7]
        else:
            a = (int(t[2]) - Y0, int(t[3]) - Z0, int(t[1]) - X0)
            block = t[4]
        glows = "galar_particle" in block or "froglight" in block
        air[a] = block == "minecraft:air"
        src[a] = 15 if glows else 0
        if glows:
            light_b = block
    lit = src.astype(np.int16)
    for _ in range(15):
        nxt = lit.copy()
        # sliced, not np.roll: a roll wraps, and light would leak out of one face of the box and in at the other
        for ax in (0, 1, 2):
            lo = [slice(None)] * 3
            hi = [slice(None)] * 3
            lo[ax], hi[ax] = slice(0, -1), slice(1, None)
            nxt[tuple(lo)] = np.maximum(nxt[tuple(lo)], lit[tuple(hi)] - 1)
            nxt[tuple(hi)] = np.maximum(nxt[tuple(hi)], lit[tuple(lo)] - 1)
        nxt[~air] = 0
        nxt = np.maximum(nxt, src.astype(np.int16))
        if np.array_equal(nxt, lit):
            break
        lit = nxt
    return np.clip(lit, 0, 15), air, (X0, Y0, Z0), light_b


def light_report(plan):
    lit, _air, (X0, Y0, Z0), light_b = light_field(plan)

    def sample(points, dy=0):
        out = []
        for (x, y, z) in points:
            iy, iz, ix = y + dy - Y0, z - Z0, x - X0
            if 0 <= iy < lit.shape[0] and 0 <= iz < lit.shape[1] and 0 <= ix < lit.shape[2]:
                out.append(int(lit[iy, iz, ix]))
        return np.array(out)

    def band(v):
        return {"hostile": int((v <= 7).sum()), "neutral": int(((v >= 8) & (v <= 11)).sum()),
                "calm": int((v >= 12).sum()), "n": int(v.size),
                "median": int(np.median(v)) if v.size else 0}

    route = [tuple(p) for p in plan["route"]]
    climb = route[plan["climb_from"]:]
    level = route[:plan["climb_from"]]
    ch = plan["chambers"]
    inch, incs = [], set()
    for _name, (cx, _cy, cz, R) in ch.items():
        for (x, y, z) in level:
            if math.hypot(x - cx, z - cz) <= R:
                inch.append((x, y, z))
                incs.add((x, z))
    # in three dimensions, not two: the stair's lower legs pass within six blocks of the stand at its head and
    # are ten below it, and they are corridor, which is meant to be dark
    near = []
    for (sx, sy, sz) in [tuple(p) for p in plan["stands"]]:
        near += [(x, y, z) for (x, y, z) in route if math.dist((x, y, z), (sx, sy, sz)) <= 6]
    rb = plan["rest"]
    rest = [(x, rb[1], z) for x in range(rb[0] + 1, rb[3]) for z in range(rb[2] + 1, rb[5])]
    return {"the whole road": band(sample(route, dy=0)),
            "inside the caverns": band(sample(inch, dy=0)),
            "the corridors between": band(sample([p for p in level if (p[0], p[2]) not in incs], dy=0)),
            "the stair and the ramp": band(sample(climb, dy=0)),
            "within 6 of a trainer": band(sample(near, dy=0)),
            "inside the rest station": band(sample(rest, dy=0))}, light_b


# ------------------------------------------------------------------ putting schema 1 back

def backfill(source_root, server_dir=None):
    """Fill the rock schema 1's labyrinth was carved out of, so the old road does not open off the new one.

    For a disposable world. It writes rock from y0 to one under the canonical ground over the old build's box,
    which also buries the Deep's northern rim; the Deep's own functions put that back afterwards, and the spec
    names which ones.
    """
    import ground as G
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    bf = spec["backfill"]
    have = installed_blocks(server_dir)
    wall_b = pick(spec["corridor"]["wall"], spec["corridor"]["wall_fallback"], have)
    g = G.load(source_root)
    x0, z0, x1, z1 = bf["box"]
    y0, y1 = bf["y"]
    ox, oz = bf["old_exit"]
    orad = bf["old_exit_radius"]
    # g.box, not g(...): see the note in build
    grid = g.box(x0, z0, x1, z1)
    lines, cols = [], 0
    for iz, Z in enumerate(range(z0, z1 + 1)):
        for ix, X in enumerate(range(x0, x1 + 1)):
            surf = int(grid[iz, ix])
            top = min(y1, surf if math.hypot(X - ox, Z - oz) <= orad else surf - 1)
            if top < y0:
                continue
            lines.append("fill %d %d %d %d %d %d %s" % (X, y0, Z, X, top, Z, wall_b))
            cols += 1
    return {"lines": lines, "checks": [], "counts": {"columns refilled": cols},
            "box": bf["box"]}, spec


# ------------------------------------------------------------------ output

def write(plan, out=None, folder="victory_road", label="Victory Road"):
    import shutil
    out = out or OUT
    if out.exists():
        shutil.rmtree(out)
    fn = out / "data" / "cobblers" / "function" / folder
    fn.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "Cobblers: %s" % label}}, indent=2) + "\n", encoding="utf-8")
    tiles = {}
    for n, ln in enumerate(plan["lines"]):
        t = ln.split()
        tiles.setdefault((int(t[1]) // TILE, int(t[3]) // TILE), []).append((n, ln))
    prefix = "vr" if folder == "victory_road" else "bf"
    order = []
    for t in sorted(tiles):
        body = [ln for _n, ln in sorted(tiles[t])]
        for k in range(0, len(body), PART):
            name = "%s_%d_%d%s" % (prefix, t[0], t[1], "" if k == 0 else "_%d" % (k // PART + 1))
            part = FL.ensure_loaded(["# Generated by tools/victory_road.py: tile %d %d" % t] + body[k:k + PART])
            probs = FL.check_lines(part, name)
            if probs:
                raise RoadError("function %s would be refused: %s" % (name, probs[:3]))
            (fn / (name + ".mcfunction")).write_text("\n".join(part) + "\n", encoding="utf-8")
            order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    if folder == "victory_road":
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps({k: v for k, v in plan.items() if k != "lines"}), encoding="utf-8")
    return order


def verify(world):
    import build_audit
    import runtime_guard
    runtime_guard.check(world, "read")
    if not PLAN.is_file():
        print("FAIL: no derived/victory_road/plan.json: run the build first")
        return 1
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    kinds = {c[4] for c in p["checks"]}
    need = {"light", "trainer stand", "landmark", "exit open", "cavern open", "rest marker", "stair top open"}
    if not need <= kinds:
        print("FAIL: the plan checks %s, missing %s" % (sorted(kinds), sorted(need - kinds)))
        return 1
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    if len(p["stands"]) != spec["trainers"]["count"]:
        print("FAIL: %d trainer stands, not %d" % (len(p["stands"]), spec["trainers"]["count"]))
        return 1
    W = build_audit.World(world)
    by, bad = {}, {}
    for x, y, z, allowed, what in p["checks"]:
        got = W.block(x, y, z)
        ok = got in allowed
        by.setdefault(what, [0, 0])[0 if ok else 1] += 1
        if not ok:
            bad.setdefault(what, []).append((x, y, z, got))
    for k in sorted(by):
        good, wrong = by[k]
        print("%-16s %7d of %7d as planned%s" % (k, good, good + wrong, ("   e.g. %s" % bad[k][:2]) if wrong else ""))
    total = sum(b for _, b in by.values())
    print("Victory Road: %s" % ("clean" if total == 0 else "%d MISMATCHES" % total))
    return 0 if total == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "backfill", "light", "verify"))
    ap.add_argument("--source-root")
    ap.add_argument("--server-dir")
    ap.add_argument("--world")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        if not a.world:
            ap.error("verify needs --world")
        return verify(a.world)
    if a.cmd == "backfill":
        plan, spec = backfill(a.source_root, a.server_dir)
        order = write(plan, BACKFILL_OUT, "vr_backfill", "Victory Road backfill (schema 1)")
        print("  %-40s %9d" % ("columns refilled", plan["counts"]["columns refilled"]))
        print("backfill: %d functions, %d commands over %s"
              % (len(order), len(plan["lines"]), plan["box"]))
        print("  then re-apply: %s" % spec["backfill"]["re_apply_after"])
        return 0
    plan, spec = build(a.source_root, a.server_dir)
    if a.cmd == "light":
        rows, light_b = light_report(plan)
        print("block light at a Pokemon's feet, from %s emitting %s" % (light_b, spec["light"]["emits"]))
        print("%-26s %8s %9s %9s %9s %8s" % ("", "blocks", "0-7", "8-11", "12-15", "median"))
        for k, v in rows.items():
            n = max(1, v["n"])
            print("%-26s %8d %8.0f%% %8.0f%% %8.0f%% %8d"
                  % (k, v["n"], 100.0 * v["hostile"] / n, 100.0 * v["neutral"] / n, 100.0 * v["calm"] / n,
                     v["median"]))
        return 0
    order = write(plan)
    for k, v in sorted(plan["counts"].items()):
        print("  %-40s %9d" % (k, v))
    print("Victory Road: %d functions, %d commands" % (len(order), len(plan["lines"])))
    print("  landmark %s, rest %s, stair top %s, exit %s"
          % (plan["landmark"], plan["rest"][:3], plan["stair_top"], plan["exit"]))
    print("  %d blocks of walked route, %d stands" % (len(plan["route"]), len(plan["stands"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
