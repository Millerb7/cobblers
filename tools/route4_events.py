#!/usr/bin/env python
"""Route 4's middle: the event chain of the cirque headwall, the trough floor and the Displaced City's gate.

Routes 1-3 have ten event sites (tools/route_events.py, step R12). Route 4 is 3,453 walked blocks with six trainers and
nothing else; this is its middle (walked 1085-2263, cells B3-B4, band 3). It COPIES the mechanism and CHANGES NOTHING
of Routes 1-3: the Site class, the sign helpers and the pack writer's shape are imported from route_events and the
rest is this file's own.

  rung 5 (datapack) for the blocks: build/datapacks/cobblers_route4_events, one function per site, re-applied by R12R4.
  rung 5 for the people: a scene (props, a per-player actor, zones, effects, an NPC) per event in data/scenes.json,
  a quest, its conversations and its fields, all written into their shared files by this tool from
  data/route4_events.json (the hand-authored design: sites, texts, transitions, rewards).
  rung 5 for the find: data/rewards.json kind cache, the advancement mechanism of ADR-002.
  Nothing here is rung 6 or above: no script, no companion, no mod.

Ground: tools/ground.py (the canonical heightmap, rounded), never a world. The walked line is data/route_paths.json.

  python tools/route4_events.py                     build the pack, check every written record against the design
  python tools/route4_events.py --write             also write the records into data/ (scenes, quests, dialogue,
                                                    progression, rewards, world_probes), spliced after the Route 3
                                                    swablu records so no existing line is reformatted
  python tools/route4_events.py --verify-world W    read a STOPPED staging world and check every planned block stands

What this does NOT cover (our list is not the world): the Merian ice fishing lodge, the Tri Peaks and the other
places other builders put in B3/B4 tonight; the cavern pack's real tunnel mouth (derived/cavern/plan.json is not in
a worktree: the mouth is recomputed here from the same formula tools/cavern_plan.py uses); the six Route 4 trainers'
sight lines beyond a distance check.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ground as G  # noqa: E402
import route_events as RE  # noqa: E402  (imported for Site, sign helpers and yaw_to; nothing in it is changed)

SPEC = ROOT / "data" / "route4_events.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_route4_events"
PACK = "route4_events"
ROUTE = "route_04_surge_to_erika"
ROUTE5 = "route_05_erika_to_koga"
ROAD_CLEAR = RE.ROAD_CLEAR
REGION = (1600, 900, 4500, 2100)       # x0, z0, x1, z1: every Route 4 middle site and the Route 4 path cells it is checked against
ANCHOR = "route3_swablu_nest"          # the records are spliced in right after Route 3's last event's
SOURCE = "data/route4_events.json"
CACHE_ID = "r4_strayed_load"
JAR = "Cobblemon-fabric-1.8.0+1.21.1.jar"
WORLD_READS = {"verify_world", "main"}  # the ground rule: a world is read only to check (tests/test_ground_rule.py)

WOOD = "spruce"
STONE_BRICK_SIGN = "spruce"


# ====================================================================== the design
def load_spec():
    return json.loads(SPEC.read_text(encoding="utf-8"))


# ====================================================================== the road
class Road4(RE.Road):
    """Route 4's walked line (and Route 5's, which starts where it ends) with Route 1-3's frame/nearest/near_any."""

    def __init__(self):
        doc = json.loads(RE.PATHS.read_text(encoding="utf-8"))
        self.heightmap_sha256 = doc["heightmap_sha256"]
        self.paths = {k: [tuple(p) for p in doc["paths"][k]] for k in (ROUTE, ROUTE5)}
        x0, z0, x1, z1 = REGION
        xs, zs = [p[0] for p in self.paths[ROUTE]], [p[1] for p in self.paths[ROUTE]]
        if min(xs) < x0 or max(xs) > x1 or min(zs) < z0 or max(zs) > z1:
            raise SystemExit("%s leaves REGION %s: widen it" % (ROUTE, REGION))
        self.cells = {k: set(v) for k, v in self.paths.items()}
        self.walked = {}
        for k, v in self.paths.items():
            d, acc = [0.0], 0.0
            for a, b in zip(v, v[1:]):
                acc += math.hypot(b[0] - a[0], b[1] - a[1])
                d.append(acc)
            self.walked[k] = d

    def at_walked(self, w):
        """The path cell index nearest to walked distance w."""
        d = self.walked[ROUTE]
        return min(range(len(d)), key=lambda i: abs(d[i] - w))


def check_paths_heightmap(road, source_root=None):
    """The walked line must have been routed on the ground these sites stand on (route_events.check_paths_heightmap,
    for this tool's region): the current heightmap, or the one the Rift sculpt was pressed into when the two agree bit
    for bit over the region."""
    import hashlib
    import numpy as np
    from PIL import Image
    import terrain as T
    world_path = ROOT / "data" / "world.json"
    world = T.load_world(world_path)
    have = road.heightmap_sha256
    if have == world["heightmap"]["sha256"]:
        return "routed on the current heightmap"
    base = world["heightmap"].get("rift_sculpted_from") or {}
    if have != base.get("sha256"):
        raise SystemExit("data/route_paths.json was routed on heightmap %s, neither the current one nor the one the Rift "
                         "sculpt was pressed into: route again (tools/build_routes.py)" % have[:8])
    cur = T.resolve_heightmap(world, world_path, source_root)
    old = cur.parent / base["path"]
    if hashlib.sha256(old.read_bytes()).hexdigest() != base["sha256"]:
        raise SystemExit("%s does not hash to %s" % (old, base["sha256"][:8]))
    ox, oz = world["grid"]["origin_x"], world["grid"]["origin_z"]
    x0, z0, x1, z1 = REGION
    a = np.array(Image.open(cur))[z0 - oz:z1 - oz + 1, x0 - ox:x1 - ox + 1]
    b = np.array(Image.open(old))[z0 - oz:z1 - oz + 1, x0 - ox:x1 - ox + 1]
    diff = int((a != b).sum())
    if diff:
        raise SystemExit("the Rift sculpt changed %d columns inside this tool's region: route again" % diff)
    return "routed on %s, the heightmap before the Rift sculpt; identical to the current one over x%d-%d z%d-%d" % (
        have[:8], x0, x1, z0, z1)


_PROTECT = None


def protected(ax, az, bx, bz):
    """Why a clearing tile must not be cut, or None: every surface town's own ground and the pinned elder trees (data/
    elder_trees.json, radius 26: the crown). The Displaced City is NOT protected: its recorded bounds are its cavern
    and its tunnel, underground, and this tool clears vegetation only (never terrain), so its surface gate is cleared
    like any other ground. route_events.protected reads derived/, which a worktree has not got; this reads data/."""
    global _PROTECT
    if _PROTECT is None:
        import town_audit
        pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
        rects = []
        for sid, s in pl["settlements"].items():
            if sid in ("displaced_city", "relic_island") or s.get("retired"):
                continue
            try:
                rects.append(("town %s" % sid, town_audit.town_bounds(sid, pl)))
            except Exception:                        # a settlement with no plan has no bounds
                continue
        elders = json.loads((ROOT / "data" / "elder_trees.json").read_text(encoding="utf-8"))["elders"]
        circles = [("an elder tree at (%d, %d)" % (e["x"], e["z"]), e["x"], e["z"], 26) for e in elders]
        _PROTECT = (rects, circles)
    rects, circles = _PROTECT
    for why, (x0, z0, x1, z1) in rects:
        if ax <= x1 and bx >= x0 and az <= z1 and bz >= z0:
            return why
    for why, cx, cz, r in circles:
        nx, nz = min(max(cx, ax), bx), min(max(cz, az), bz)
        if math.hypot(nx - cx, nz - cz) <= r:
            return why
    return None


class Site(RE.Site):
    """route_events.Site with this tool's vegetation protection."""

    def __init__(self, sid, g, road, scene=None, title=""):
        super().__init__(sid, g, road, scene, title)
        self.points = {}            # named particle positions (x, y, z): not scene markers, nobody stands there
        self.zones = []             # {"id", "from", "to"} boxes
        self.checks = []            # (what, x, y, z, block): the presence probes
        self.cmds[0] = "# %s: %s (tools/route4_events.py)" % (sid, title)

    def clear(self, x0, z0, x1, z1, up=18, down=1, cells=None):
        step = 12
        for tx in range(min(x0, x1), max(x0, x1) + 1, step):
            for tz in range(min(z0, z1), max(z0, z1) + 1, step):
                ax, az = tx, tz
                bx, bz = min(tx + step - 1, max(x0, x1)), min(tz + step - 1, max(z0, z1))
                if cells is not None and not cells((ax + bx) / 2.0, (az + bz) / 2.0):
                    continue
                why = protected(ax, az, bx, bz)
                if why:
                    self.kept.add(why)
                    continue
                hs = [self.g(x, z) for x in range(ax, bx + 1, 3) for z in range(az, bz + 1, 3)] + [self.g(bx, bz)]
                y0, y1 = min(hs) - down, max(hs) + up
                for pred in RE.VEG:
                    self.clear_cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (ax, y0, az, bx, y1, bz, pred))
                self.cleared.append((ax, y0, az, bx, y1, bz))

    def raw(self, cmd):
        """A command that is not tracked as a planned block (a conditional clear of snow)."""
        self.cmds.append(cmd)

    def thaw(self, cells, y_of):
        """Snow out of a set of cells (only snow: `replace minecraft:snow`, one block above each cell's ground), one fill
        per run of cells along z at the same ground height."""
        by_x = {}
        for x, z in cells:
            by_x.setdefault(x, []).append(z)
        for x, zs in sorted(by_x.items()):
            zs.sort()
            run = [zs[0]]
            for z in zs[1:] + [None]:
                if z is not None and z == run[-1] + 1 and y_of(x, z) == y_of(x, run[0]):
                    run.append(z)
                    continue
                y = y_of(x, run[0]) + 1
                self.raw("fill %d %d %d %d %d %d minecraft:air replace minecraft:snow" % (x, y, run[0], x, y, run[-1]))
                run = [z] if z is not None else []

    def probe(self, what, x, y, z, block):
        self.checks.append((what, int(x), int(y), int(z), block))


def wsign(wood, rotation, front):
    """route_events.sign() with the text waxed (`is_waxed`), so nobody edits a milestone's inscription."""
    s = RE.sign(wood, rotation, front)
    return s[:-1] + ",is_waxed:1b}"


def rotation_to(fx, fz):
    """The standing-sign rotation whose front faces the vector (fx, fz)."""
    return int(round(RE.yaw_to(fx, fz) / 22.5)) % 16


def perimeter_hash(x, z, salt=0):
    """A deterministic 0..99 per cell, for dither and scatter that a rebuild reproduces exactly."""
    return ((x * 73856093) ^ (z * 19349663) ^ (salt * 83492791)) % 100


# ====================================================================== the sites
def headwall_camp(g, road, spec):
    c = spec["sites"]["headwall_camp"]
    cx, cz = c["x"], c["z"]
    s = Site("headwall_camp", g, road, spec["events"]["headwall_camp"]["scene"], "Hallam's camp on the shelf above the cirque headwall: lean-to, fire, spilled loads, hitching post, the rockfall's scar")
    s.clear(cx - 28, cz - 14, cx + 38, cz + 22, up=16)
    roof = "minecraft:%s_slab[type=bottom,waterlogged=false]" % WOOD
    fence = "minecraft:%s_fence" % WOOD
    # the lean-to: four posts, a slab roof, a back wall, a bench, a barrel
    lx0, lx1, lz0, lz1 = cx - 6, cx - 2, cz + 3, cz + 5
    for x in (lx0, lx1):
        for z in (lz0, lz1):
            s.fill((x, g(x, z) + 1, z), (x, g(x, z) + 3, z), fence)
    top = max(g(x, z) for x in (lx0, lx1) for z in (lz0, lz1)) + 4
    s.fill((lx0 - 1, top, lz0 - 1), (lx1 + 1, top, lz1 + 1), roof)
    for x in range(lx0, lx1 + 1):
        s.fill((x, g(x, lz1) + 1, lz1), (x, g(x, lz1) + 2, lz1), "minecraft:%s_planks" % WOOD)
    for x in (lx0 + 1, lx0 + 2):
        s.on_ground(x, lz0 + 1, "minecraft:%s_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]" % WOOD)
    s.on_ground(lx1 - 1, lz0 + 1, "minecraft:barrel[facing=up,open=false]")
    s.set(lx0 + 2, top - 1, lz0 + 1, "minecraft:lantern[hanging=true]")
    s.probe("the lean-to's barrel", lx1 - 1, g(lx1 - 1, lz0 + 1) + 1, lz0 + 1, "minecraft:barrel")
    # the fire, ringed, with two log seats; Hallam stands north of it, facing the road
    fx, fz = cx + 4, cz
    s.on_ground(fx, fz, "minecraft:campfire[facing=north,lit=true,signal_fire=false,waterlogged=false]")
    for dx, dz in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        s.on_ground(fx + dx, fz + dz, "minecraft:cobblestone")
    s.on_ground(fx - 3, fz + 2, "minecraft:%s_log[axis=x]" % WOOD)
    s.on_ground(fx + 3, fz + 3, "minecraft:%s_log[axis=z]" % WOOD)
    s.probe("the camp fire", fx, g(fx, fz) + 1, fz, "minecraft:campfire")
    s.npc("dlg_route4_headwall_camp", cx + 3, cz - 3, yaw=180)
    # the loads: barrels stacked and one thrown on its side, a spilled sack of grain (hay is whitelisted, wool is not)
    for dy in (1, 2):
        s.on_ground(cx - 14, cz - 2, "minecraft:barrel[facing=up,open=false]", dy=dy)
    s.on_ground(cx - 13, cz - 2, "minecraft:barrel[facing=up,open=false]")
    s.on_ground(cx - 12, cz + 1, "minecraft:barrel[facing=east,open=false]")
    s.on_ground(cx - 11, cz - 1, "minecraft:hay_block[axis=x]")
    # the hitching post, with the rope stub that parted: strands pointing east
    hx, hz = cx + 6, cz + 6
    for x in range(hx - 4, hx + 1):
        s.fill((x, g(x, hz) + 1, hz), (x, g(x, hz) + 2, hz), fence)
    s.set(hx + 1, g(hx, hz) + 2, hz, "minecraft:chain[axis=x,waterlogged=false]")
    s.set(hx - 4, g(hx - 4, hz) + 3, hz, "minecraft:lantern[hanging=false]")
    s.prop("lead", (hx, g(hx, hz) + 1, hz), (1.0, 1.6), dy=0.0)
    s.probe("the hitching post", hx, g(hx, hz) + 1, hz, fence)
    # the rockfall's scar at the east lip: gravel swath, andesite and tuff, one boulder
    sx, sz = cx + 25, cz - 4
    swath = [(sx + a, sz + b) for a in range(-3, 4) for b in range(-3, 4) if (a * a + b * b) <= 11]
    for x, z in swath:
        s.ground_block(x, z, "minecraft:gravel")
    for k, (x, z) in enumerate(swath):
        if perimeter_hash(x, z, 1) < 30:
            s.on_ground(x, z, ("minecraft:cobblestone", "minecraft:andesite", "minecraft:tuff")[k % 3])
    bx, bz = sx, sz
    for a, b, h in ((0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1), (0, 0, 2), (1, 1, 2)):
        s.on_ground(bx + a, bz + b, "minecraft:andesite" if h == 1 else "minecraft:cobblestone", dy=h)
    s.prop("scar", (bx, g(bx, bz) + 2, bz), (2.0, 1.4), dy=0.0)
    s.probe("the boulder", bx, g(bx, bz) + 1, bz, "minecraft:andesite")
    s.set_area(cx - 30, cz - 16, cx + 40, cz + 24)
    return s


def steam_hollow(g, road, spec):
    c = spec["sites"]["steam_hollow"]
    cx, cz = c["x"], c["z"]
    s = Site("steam_hollow", g, road, spec["events"]["steam_hollow"]["scene"], "the hollow on the trough floor: a warm pool in a ring of green moss, pink petals, hoofprints in and out")
    gy = g(cx, cz)
    s.clear(cx - 20, cz - 20, cx + 20, cz + 20, up=12)
    pool = [(x, z) for x in range(cx - 3, cx + 4) for z in range(cz - 3, cz + 4) if (x - cx) ** 2 + (z - cz) ** 2 <= 10]
    ring, outer = [], []
    for x in range(cx - 9, cx + 10):
        for z in range(cz - 9, cz + 10):
            r2 = (x - cx) ** 2 + (z - cz) ** 2
            if 10 < r2 <= 40:
                ring.append((x, z))
            elif 40 < r2 <= 64 and perimeter_hash(x, z, 2) < 45:
                outer.append((x, z))
    s.thaw([(x, z) for x, z in pool + ring + outer], lambda x, z: g(x, z))
    for x, z in ring + outer:
        s.ground_block(x, z, "minecraft:moss_block")
    for x, z in pool:
        yy = g(x, z)
        s.set(x, yy, z, "minecraft:air")
        s.set(x, yy - 1, z, "minecraft:water[level=0]")
        s.set(x, yy - 2, z, "minecraft:water[level=0]")
        s.set(x, yy - 3, z, "minecraft:gravel")
    s.set(cx, gy - 2, cz, "minecraft:light[level=15,waterlogged=true]")        # keeps the pool from freezing (ASSUMED: not read in game)
    # snow forms only where block light is under 10 (vanilla Biome.shouldSnow): four invisible light blocks on the ring keep
    # the moss clear in a snowfall (ASSUMED from the vanilla rule, not seen in game)
    for dx, dz in ((5, 0), (-5, 0), (0, 5), (0, -5)):
        s.set(cx + dx, g(cx + dx, cz + dz) + 1, cz + dz, "minecraft:light[level=15,waterlogged=false]")
    s.probe("the pool's water", cx + 1, gy - 1, cz, "minecraft:water")
    s.probe("the pool's moss", cx + 5, gy, cz, "minecraft:moss_block")
    # petals on the moss, a handful, each on its own block
    petals = [(x, z) for x, z in ring if 13 <= (x - cx) ** 2 + (z - cz) ** 2 <= 30 and perimeter_hash(x, z, 3) < 14]
    facings = ("north", "east", "south", "west")
    for k, (x, z) in enumerate(petals):
        s.on_ground(x, z, "minecraft:pink_petals[facing=%s,flower_amount=%d]" % (facings[k % 4], 1 + (k * 7) % 4))
    # boulders round the hollow, so it reads as a hollow and not a puddle
    for k in range(6):
        a = math.radians(30 + 60 * k)
        bx, bz = int(round(cx + 8.5 * math.cos(a))), int(round(cz + 8.5 * math.sin(a)))
        blk = ("minecraft:tuff", "minecraft:mossy_cobblestone")[k % 2]
        s.on_ground(bx, bz, blk)
        if k % 2 == 0:
            s.on_ground(bx, bz, blk, dy=2)
    # hoofprints: in from the walked line (north-east), out east toward the foot of the wall; a cell of coarse dirt with
    # the snow taken off, a pair per stride, alternate sides
    i = road.at_walked(1900)
    px, pz = road.paths[ROUTE][i]
    ins = _prints(g, s, [(px - 6, pz + 8), (cx + 6, cz - 5)], 4.5)
    foot = spec["sites"]["strayed_load"]
    out_ = _prints(g, s, [(cx + 8, cz - 1), (foot["x"] - 6, foot["z"] + 2)], 7.0)
    s.notes.append("%d prints in from the walked line, %d out toward the find" % (ins, out_))
    # the three props
    tx, tz = cx + 8, cz - 1
    s.prop("tracks", (tx, g(tx, tz), tz), (1.4, 0.8), dy=1.0)
    s.prop("pool", (cx + 4, g(cx + 4, cz), cz), (1.6, 1.0), dy=1.0)
    px_, pz_ = petals[len(petals) // 2]
    s.prop("petal", (px_, g(px_, pz_), pz_), (0.9, 0.7), dy=1.0)
    s.points["steam_a"] = (cx + 0.5, gy + 1.0, cz + 0.5)
    s.points["steam_b"] = (cx - 1.0, gy + 1.0, cz + 1.5)
    s.set_area(cx - 22, cz - 22, cx + 22, cz + 22)
    return s


def _prints(g, s, pts, stride):
    """Hoofprints along the polyline: returns how many cells were written."""
    n = 0
    k = 0
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        L = math.hypot(bx - ax, bz - az)
        ux, uz = (bx - ax) / L, (bz - az) / L
        d = 0.0
        while d <= L:
            x0, z0 = ax + ux * d, az + uz * d
            side = 1 if k % 2 == 0 else -1
            x, z = int(round(x0 - uz * 0.9 * side)), int(round(z0 + ux * 0.9 * side))
            s.ground_block(x, z, "minecraft:coarse_dirt")
            s.raw("fill %d %d %d %d %d %d minecraft:air replace minecraft:snow" % (x, g(x, z) + 1, z, x, g(x, z) + 1, z))
            n += 1
            k += 1
            d += stride
    return n


def strayed_load(g, road, spec):
    c = spec["sites"]["strayed_load"]
    cx, cz = c["x"], c["z"]
    s = Site("strayed_load", g, road, None, "the strayed load at the east wall's foot: a barrel, torn oilcloth boards, a red pennant")
    s.clear(cx - 14, cz - 12, cx + 14, cz + 12, up=14)
    gy = g(cx, cz)
    s.on_ground(cx, cz, "minecraft:barrel[facing=up,open=false]")
    s.probe("the strayed barrel", cx, gy + 1, cz, "minecraft:barrel")
    for k, (dx, dz) in enumerate(((-2, 0), (2, 1), (1, -2), (-1, 2))):
        s.on_ground(cx + dx, cz + dz, "minecraft:%s_planks" % WOOD)
    s.on_ground(cx - 1, cz - 1, "minecraft:%s_trapdoor[facing=north,half=bottom,open=true,powered=false,waterlogged=false]" % WOOD)
    s.on_ground(cx + 2, cz - 1, "minecraft:chain[axis=x,waterlogged=false]")
    px, pz = cx - 3, cz - 3
    s.fill((px, g(px, pz) + 1, pz), (px, g(px, pz) + 7, pz), "minecraft:%s_fence" % WOOD)
    s.set(px, g(px, pz) + 8, pz, "minecraft:red_banner[rotation=4]")
    s.probe("the red pennant", px, g(px, pz) + 8, pz, "minecraft:red_banner")
    s.checks_cache = {"container": [cx, gy + 1, cz], "trigger": {"min": [cx - 2, gy, cz - 2], "max": [cx + 2, gy + 3, cz + 2]}}
    return s


def dp_simplify(pts, tol):
    """Douglas-Peucker."""
    if len(pts) < 3:
        return list(pts)
    (ax, az), (bx, bz) = pts[0], pts[-1]
    L = math.hypot(bx - ax, bz - az) or 1.0
    best, bi = -1.0, 0
    for i in range(1, len(pts) - 1):
        d = abs((bx - ax) * (az - pts[i][1]) - (ax - pts[i][0]) * (bz - az)) / L
        if d > best:
            best, bi = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return dp_simplify(pts[:bi + 1], tol)[:-1] + dp_simplify(pts[bi:], tol)


def trail_route(g, road, spec):
    """The dense trail from the walked-2100 cell to the gate's approach, routed on the heightmap (contour-following A*,
    slope no steeper than 25 degrees, which takes it round the river's head rather than through it)."""
    import numpy as np
    import route_path as RP
    import terrain as T
    c = spec["sites"]["summit_road"]
    i = road.at_walked(c["from_walked"])
    start = road.paths[ROUTE][i]
    goal = tuple(c["to"])
    ax0, az0, ax1, az1 = 2960, 1540, 3300, 1780
    hh = g.heights[az0 - g.oz:az1 - g.oz, ax0 - g.ox:ax1 - g.ox]
    passable = T.slope_degrees(hh) <= 25
    r, _ = RP.route(hh, passable, (start[0] - ax0, start[1] - az0), (goal[0] - ax0, goal[1] - az0), 8.0)
    dense = [(x + ax0, z + az0) for x, z in r]
    return start, dense


def summit_road(g, road, spec):
    s = Site("summit_road", g, road, spec["events"]["summit_road"]["scene"], "the old summit road: a trail from the walked line to the Displaced City's gate, six numbered milestones counting down")
    start, dense = trail_route(g, road, spec)
    pts = dp_simplify(dense, 2.0)
    gate_x, gate_z = spec["sites"]["thaw_gate"]["gate"]
    pts = pts + [(gate_x, gate_z + 3)]              # the last stretch, straight north to the gate
    cells = s.trail(pts, "minecraft:dirt_path", width=2)
    s.thaw(cells, lambda x, z: g(x, z))
    # the dense trail's distance along itself, for the stones
    dist = [0.0]
    for a, b in zip(pts, pts[1:]):
        dist.append(dist[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = dist[-1]

    def along(d):
        d = max(0.0, min(total, d))
        for k in range(len(pts) - 1):
            if dist[k + 1] >= d:
                t = (d - dist[k]) / max(dist[k + 1] - dist[k], 1e-9)
                return (pts[k][0] + (pts[k + 1][0] - pts[k][0]) * t, pts[k][1] + (pts[k + 1][1] - pts[k][1]) * t,
                        (pts[k + 1][0] - pts[k][0]), (pts[k + 1][1] - pts[k][1]))
        return pts[-1][0], pts[-1][1], 0.0, 1.0

    texts = {5: ["OLD SUMMIT", "ROAD", "5", "stones to climb"],
             4: ["SUMMIT", "4", "the cistern", "is dry"],
             3: ["SUMMIT", "3", "meltwater", "rises near"],
             2: ["SUMMIT", "2", "warm wind", "from the hill"],
             1: ["SUMMIT", "1", "rest here", "you are close"],
             0: ["SUMMIT", "0", "you are", "here"]}
    stones = {}
    for n in (5, 4, 3, 2, 1, 0):
        d = {5: 5.0, 0: total - 3.0}.get(n, (5 - n) * total / 5.0)
        tx, tz, dx, dz = along(d)
        L = math.hypot(dx, dz) or 1.0
        nx, nz = -dz / L, dx / L
        best = None
        for sgn in (1, -1):
            sx, sz = int(round(tx + sgn * nx * 4)), int(round(tz + sgn * nz * 4))
            score = abs(g(sx, sz) - g(int(round(tx)), int(round(tz))))
            if best is None or score < best[0]:
                best = (score, sx, sz)
        _, sx, sz = best
        stones[n] = (sx, sz, int(round(tx)), int(round(tz)))
        gy = g(sx, sz)
        s.on_ground(sx, sz, "minecraft:mossy_stone_bricks")
        s.on_ground(sx, sz, "minecraft:stone_bricks", dy=2)
        # the front faces back along the trail toward whoever is coming, tilted to the trail itself
        bx, bz, _, _ = along(d - 7.0)
        s.set(sx, gy + 3, sz, wsign(STONE_BRICK_SIGN, rotation_to(bx - sx, bz - sz), texts[n]))
        s.probe("milestone %d" % n, sx, gy + 1, sz, "minecraft:mossy_stone_bricks")
        s.zones.append({"id": "z%d" % n, "from": [int(tx) - 4, gy - 3, int(tz) - 4], "to": [int(tx) + 4, gy + 8, int(tz) + 4]})
    s.stones = stones
    sx, sz, _, _ = stones[0]
    s.prop("stone_0", (sx, g(sx, sz) + 1, sz), (0.9, 3.2), dy=0.0)
    xs = [x for x, _ in cells]
    zs = [z for _, z in cells]
    s.set_area(min(xs) - 14, min(zs) - 14, max(xs) + 14, max(zs) + 10)
    s.notes.append("trail %d cells, %.0f blocks; stones at %s" % (len(cells), total, {n: (v[0], v[1]) for n, v in stones.items()}))
    return s


def thaw_gate(g, road, spec):
    c = spec["sites"]["thaw_gate"]
    gx, gz = c["gate"]
    mx, mz = c["mouth"]
    s = Site("thaw_gate", g, road, spec["events"]["thaw_gate"]["scene"], "the gate on the hill: green moss and cherry petals running from the tunnel mouth into the snow")
    s.clear(gx - 24, gz - 24, gx + 24, gz + 18, up=16)
    top = g(gx, gz - 5)
    # the moss belt between the mouth and the gate: nothing within 3 of the mouth itself (the cavern pack cuts it)
    z0, z1 = mz + 4, gz - 3
    belt = []
    for x in range(gx - 9, gx + 10):
        for z in range(z0, z1 + 1):
            ex = (x - (gx + 1)) / 8.0
            ez = (z - (z0 + z1) / 2.0) / ((z1 - z0) / 2.0 + 0.5)
            r = ex * ex + ez * ez
            if r <= 0.8 or (r <= 1.2 and perimeter_hash(x, z, 4) < 55):
                belt.append((x, z))
    s.thaw(belt, lambda x, z: g(x, z))
    for x, z in belt:
        s.ground_block(x, z, "minecraft:moss_block")
    leaves, petals = [], []
    # nobody stands or lies in a petal: the keeper's cell, the Gogoat's two markers and the drift prop, with a ring of one
    keep = [(gx, gz - 5), (gx + 6, gz - 8), (gx + 5, gz + 4), (gx + 4, gz - 6)]
    for x, z in belt:
        if any(abs(x - kx) <= 1 and abs(z - kz) <= 1 for kx, kz in keep):
            continue
        h = perimeter_hash(x, z, 5)
        if h < 6:
            leaves.append((x, z))
        elif h < 26:
            petals.append((x, z))
    for x, z in leaves:
        s.on_ground(x, z, "minecraft:cherry_leaves[distance=1,persistent=true,waterlogged=false]")
    for k, (x, z) in enumerate(petals):
        s.on_ground(x, z, "minecraft:pink_petals[facing=%s,flower_amount=%d]" % (("north", "east", "south", "west")[k % 4], 1 + (k * 5) % 4))
    for dx in (-6, -2, 2, 6):
        lx, lz = gx + dx, (z0 + z1) // 2
        if (lx, lz) in belt and not any(abs(lx - kx) <= 1 and abs(lz - kz) <= 1 for kx, kz in keep):
            s.set(lx, g(lx, lz) + 1, lz, "minecraft:light[level=15,waterlogged=false]")
    s.probe("the moss belt", gx + 1, g(gx + 1, (z0 + z1) // 2), (z0 + z1) // 2, "minecraft:moss_block")
    # two lantern posts and a stone bench by the gate's inside
    for x, z in ((gx - 6, gz - 5), (gx + 6, gz - 5)):
        s.fill((x, g(x, z) + 1, z), (x, g(x, z) + 2, z), "minecraft:stone_brick_wall")
        s.set(x, g(x, z) + 3, z, "minecraft:lantern[hanging=false]")
    s.probe("the gate's lantern post", gx - 6, g(gx - 6, gz - 5) + 3, gz - 5, "minecraft:lantern")
    s.on_ground(gx - 4, gz - 3, "minecraft:stone_brick_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]")
    # the keeper stands on the belt facing the gate; the Gogoat lies in the drift
    s.npc("dlg_route4_thaw_gate", gx, gz - 5, yaw=0)
    s.marker("biscuit_drift", gx + 6, gz - 8, yaw=90, slots=[[0, 0]])
    s.marker("biscuit_gate", gx + 5, gz + 4, yaw=0, slots=[[0, 0]])
    dx_, dz_ = gx + 4, gz - 6
    s.prop("drift", (dx_, g(dx_, dz_) + 1, dz_), (1.2, 1.2), dy=0.0)
    s.on_ground(dx_, dz_, "minecraft:cherry_leaves[distance=1,persistent=true,waterlogged=false]")
    s.points["petals_a"] = (mx + 0.5, g(mx, z0) + 1.5, z0 + 0.5)
    s.points["petals_b"] = (gx + 0.5, g(gx, gz - 7) + 1.5, gz - 7 + 0.5)
    s.set_area(gx - 26, mz - 6, gx + 26, gz + 26)
    return s


SITES = [headwall_camp, steam_hollow, strayed_load, summit_road, thaw_gate]


def build(g, road, spec):
    return [f(g, road, spec) for f in SITES]


# ====================================================================== records from the design
COND = re.compile(r"^(!)?([a-z_0-9]+)$")


class Builder:
    """The design (data/route4_events.json) as the records the shared files hold. One quest carries the whole chain: the
    validator lets a quest read only its own fields, and the finale reads the earlier events' flags."""

    def __init__(self, spec, sites):
        self.spec = spec
        self.q = spec["quest"]["id"]
        self.sites = {s.id: s for s in sites}

    # ---- conditions and effects
    def field(self, name):
        return "quest.%s.%s" % (self.q, name)

    def cond(self, tok):
        if " in " in tok:
            f, vals = tok.split(" in ")
            return {"kind": "progression_in", "field": self.field(f.strip()), "values": vals.split(",")}
        if "!=" in tok:
            f, v = tok.split("!=")
            return {"kind": "not", "condition": {"kind": "progression_equals", "field": self.field(f), "value": v}}
        if "=" in tok:
            f, v = tok.split("=")
            return {"kind": "progression_equals", "field": self.field(f), "value": v}
        m = COND.match(tok)
        if not m:
            raise SystemExit("condition %r" % tok)
        neg, f = m.groups()
        return {"kind": "progression_equals", "field": self.field(f), "value": not neg}

    def conds(self, toks):
        cs = [self.cond(t) for t in toks]
        if not cs:
            return {"kind": "always"}
        return cs[0] if len(cs) == 1 else {"kind": "all", "conditions": cs}

    @staticmethod
    def value(v):
        return {"true": True, "false": False}.get(v, v)

    def effect(self, tok):
        if tok.startswith("set:"):
            f, v = tok[4:].split("=")
            return {"kind": "set_progression", "field": self.field(f), "value": self.value(v)}
        if tok.startswith("sync_scene:"):
            return {"kind": "sync_scene", "scene": tok[len("sync_scene:"):]}
        if tok.startswith("grant:"):
            rid = tok[6:]
            return {"kind": "grant_reward_once", "reward": rid, "target": "triggering_player",
                    "claim_field": self.field(self.spec["quest"]["rewards"][rid]["claim"]),
                    "idempotency_key": "%s:%s:{player_uuid}" % (self.q, rid), "receipt_commit": "atomic_with_item_delivery"}
        raise SystemExit("effect %r" % tok)

    def action(self, tok):
        if tok.startswith("T:"):
            return {"kind": "quest_transition", "transition": tok[2:]}
        if tok == "close":
            return {"kind": "close_dialogue"}
        raise SystemExit("action %r" % tok)

    # ---- progression fields
    def fields(self):
        quest = self.spec["quest"]
        out = []
        for name, t in quest["fields"].items():
            rec = {"id": self.field(name), "quest_id": self.q, "field": name, "scope": "player"}
            if t == "bool":
                rec.update({"type": "boolean", "initial": False})
            else:
                rec.update({"type": "enum", "initial": t[1]})
                if name in ("hallam_cursor", "oriel_cursor"):
                    conv = next(c for ev in self.spec["events"].values() for c in ev["conversations"] if c["cursor"] == name)
                    rec["allowed_values"] = "node ids from %s" % conv["id"]
                elif name == "prop_cursor":
                    rec["allowed_values"] = "node ids from this quest's prop conversations; each enters on an explicit node and never restores"
                elif name == "last_stone":
                    rec["allowed_values"] = "none|s5|s4|s3|s2|s1|s0"
                else:
                    raise SystemExit("enum field %s has no allowed_values" % name)
            out.append(rec)
        return out

    # ---- quest
    def quest(self):
        quest = self.spec["quest"]
        objectives = []
        for o in quest["objectives"]:
            act = self.cond(o["active"])
            objectives.append({"id": o["id"], "active_when": {"field": act["field"], "equals": act["value"]},
                               "complete_when": {"field": self.field(o["complete"]), "equals": True}, "text": o["text"]})
        trans = [{"id": t["id"], "conditions": [self.cond(w) for w in t["when"]], "effects": [self.effect(d) for d in t["do"]]}
                 for t in quest["transitions"]]
        rewards = [{"id": rid, "status": "item_ids_verified; quantities provisional",
                    "contents": [self.item(i, n) for i, n in r["contents"]], "why": r["why"]} for rid, r in quest["rewards"].items()]
        return {"id": self.q, "source": SOURCE, "scope": "player", "optional": True, "progression_gate": [],
                "availability": {"conditions": [], "repeatable": False, "npc_remains_after_completion": True},
                "dialogue_ids": [c["id"] for ev in self.spec["events"].values() for c in ev["conversations"]],
                "objectives": objectives, "transitions": trans, "rewards": rewards,
                "multiplayer": {"state": "per_player", "props": "shared props open each clicker's own conversation",
                                "actors": "posed Pokemon are per-player actors (data/scenes.json), never capture rewards",
                                "concurrent_players": "independent transitions; no player may read or write another player's fields"},
                "progression_field_refs": [self.field(f) for f in quest["fields"]],
                "scene": "data/scenes.json " + ", ".join(ev["scene"] for ev in self.spec["events"].values()),
                "lore_rule": quest["lore_rule"]}

    @staticmethod
    def item(item, n):
        ns, name = item.split(":")
        ver = ("assets/cobblemon/models/item/%s.json in %s" % (name, JAR)) if ns == "cobblemon" else "vanilla item"
        return {"item": item, "count": n, "verification": ver}

    # ---- conversations
    def conversation(self, c):
        rules = []
        for r in c["rules"]:
            rule = {"priority": r["p"], "when": self.conds(r["when"]), "node": r["node"]}
            if r.get("do"):
                rule["actions"] = [self.action(d) for d in r["do"]]
            rules.append(rule)
        nodes = []
        for n in c["nodes"]:
            node = {"id": n["id"], "kind": n.get("kind", "line"), "speaker": n["speaker"], "text": n["text"]}
            if node["kind"] == "choice":
                node["responses"] = []
                for r in n["responses"]:
                    resp = {"id": r["id"], "text": r["text"]}
                    if r.get("do"):
                        resp["actions"] = [self.action(d) for d in r["do"]]
                    if r.get("next"):
                        resp["next"] = r["next"]
                    node["responses"].append(resp)
            else:
                node["next"] = n["next"]
                if n.get("after"):
                    node["actions_after_acknowledge"] = [self.action(d) for d in n["after"]]
            nodes.append(node)
        rec = {"id": c["id"], "quest_id": self.q, "npc_id": (c["npc"] or {}).get("id"), "source": SOURCE, "scope": "player",
               "cursor": {"progression_field": self.field(c["cursor"]), "initial_node": c["initial"],
                          "persist": "after_each_node", "restore": "on_every_interaction", "cursor_is": "next_unread_node"},
               "entry_rules": rules, "nodes": nodes, "speakers": c["speakers"]}
        if c["npc"]:
            rec["npc_name"] = c["npc"]["name"]
        return rec

    # ---- scene
    def scene(self, event):
        ev = self.spec["events"][event]
        site = self.sites[ev["site"]]
        sd = ev["scene_def"]
        rec = {"id": ev["scene"], "quest_id": self.q, "source": SOURCE, "built_by": "tools/route4_events.py %s" % ev["site"]}
        rec["area"] = site.area
        rec["markers"] = site.markers
        props = []
        for p in sd["props"]:
            q = site.props[p["id"]]
            props.append({"id": p["id"], "conversation": p["conversation"], "at": q["at"], "size": q["size"], "on": q["on"]})
        rec["props"] = props
        actors = []
        for a in sd["actors"]:
            place = []
            for pl in a["place"]:
                r = {}
                if pl.get("when"):
                    r["when"] = self.conds(pl["when"])
                r["marker"] = pl["marker"]
                place.append(r)
            act = {"id": a["id"], "species": a["species"], "level": a["level"]}
            if a.get("name"):
                act["name"] = a["name"]
            act.update({"conversation": a["conversation"], "not_yours": a["not_yours"], "place": place})
            actors.append(act)
        rec["actors"] = actors
        zones = []
        for z in sd["zones"]:
            box = next(b for b in site.zones if b["id"] == z["id"])
            zones.append({"id": z["id"], "from": box["from"], "to": box["to"], "transitions": z["transitions"]})
        rec["zones"] = zones
        effects = []
        for e in sd["effects"]:
            if e["kind"] == "particles":
                x, y, z = site.points[e["at_point"]]
                effects.append({"id": e["id"], "kind": "particles",
                                "particles": [{"particle": e["particle"], "at": [round(x, 1), round(y, 1), round(z, 1)],
                                               "delta": e["delta"], "count": e["count"]}]})
            elif e["kind"] == "actionbar":
                effects.append({"id": e["id"], "kind": "actionbar", "when": self.conds(e["when"]),
                                "text": e["text"], "color": e.get("color", "gold")})
            else:
                raise SystemExit("effect kind %r" % e["kind"])
        rec["effects"] = effects
        rec["npcs"] = site.npcs
        return rec


def npc_grant_record(b, rid, r, site, title):
    npc = site.npcs[0]
    return {"id": "r4_" + rid.replace("reward_", ""), "kind": "npc_grant", "place": title,
            "npc_at": npc["at"], "quest": b.q, "contents": [b.item(i, n) for i, n in r["contents"]], "why": r["why"],
            "built_by": "the NPC by spawnnpcat after a restart (reapply step R17); its position written by `route4_events.py --write`"}


def cache_record(spec, site):
    f = spec["find"]
    box = site.checks_cache
    return {"id": f["id"], "kind": "cache", "place": f["place"], "contents": [Builder.item(i, n) for i, n in f["contents"]],
            "message": f["message"], "why": f["why"],
            "built_by": "tools/route4_events.py strayed_load (the container, reapply step R12R4); positions written by `route4_events.py --write`",
            "trigger": box["trigger"], "container": {"block": "minecraft:barrel", "at": box["container"]}}


def build_records(spec, sites):
    """Every record this tool owns: {file key: [records]}, normalised through JSON so a comparison is exact."""
    b = Builder(spec, sites)
    byid = {s.id: s for s in sites}
    out = {"scenes": [], "quests": [b.quest()], "dialogue": [], "progression": b.fields(), "rewards": []}
    for event, ev in spec["events"].items():
        for c in ev["conversations"]:
            out["dialogue"].append(b.conversation(c))
        out["scenes"].append(b.scene(event))
    for rid, r in spec["quest"]["rewards"].items():
        ev = spec["events"][r["event"]]
        out["rewards"].append(npc_grant_record(b, rid, r, byid[ev["site"]], ev["title"]))
    out["rewards"].append(cache_record(spec, byid["strayed_load"]))
    return {k: json.loads(json.dumps(v)) for k, v in out.items()}


# ====================================================================== writing into the shared files
# file, array key, the record after which ours go, whose records are ours
TARGETS = {
    "scenes": ("scenes.json", "scenes", lambda o: o.get("id") == ANCHOR, lambda o: str(o.get("id", "")).startswith("route4_")),
    "quests": ("quests.json", "quests", lambda o: o.get("id") == "evt_" + ANCHOR, lambda o: str(o.get("id", "")).startswith("evt_route4_")),
    "dialogue": ("dialogue.json", "conversations", lambda o: o.get("quest_id") == "evt_" + ANCHOR, lambda o: str(o.get("id", "")).startswith("dlg_route4_")),
    "progression": ("progression.json", "quest_fields", lambda o: o.get("quest_id") == "evt_" + ANCHOR, lambda o: str(o.get("quest_id", "")).startswith("evt_route4_")),
    "rewards": ("rewards.json", "rewards", lambda o: o.get("id") == "r3_world_tree_roots", lambda o: str(o.get("id", "")).startswith("r4_")),
}


def splice(path, key, anchor_pred, owned_pred, records, write):
    """Put `records` right after the anchor record's LAST occurrence in the top-level array `key`, replacing whatever of
    ours stood there, without re-serialising anything else (these files are hand-formatted: a round trip reformats
    hundreds of lines). Returns True when the file already holds exactly `records`."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r'^  "%s": \[' % re.escape(key), text, re.M)
    if not m:
        raise SystemExit("%s has no top-level array %r" % (path.name, key))
    dec = json.JSONDecoder()
    spans, i = [], m.end()
    while True:
        while text[i] in " \t\r\n,":
            i += 1
        if text[i] == "]":
            break
        obj, j = dec.raw_decode(text, i)
        spans.append((i, j, obj))
        i = j
    anchors = [k for k, (_, _, o) in enumerate(spans) if anchor_pred(o)]
    if not anchors:
        raise SystemExit("%s: the anchor record is gone" % path.name)
    a = anchors[-1]
    owned = [k for k, (_, _, o) in enumerate(spans) if owned_pred(o)]
    if owned != list(range(a + 1, a + 1 + len(owned))):
        raise SystemExit("%s: this tool's records are not the run right after the anchor (positions %s, anchor %d): put them back or remove them by hand" % (path.name, owned, a))
    old_end = spans[a + len(owned)][1]
    current = [spans[k][2] for k in owned]
    same = json.loads(json.dumps(current)) == records
    ins = "".join(",\n" + "\n".join("    " + ln for ln in json.dumps(r, indent=2, ensure_ascii=False).split("\n")) for r in records)
    new = text[:spans[a][1]] + ins + text[old_end:]
    if write and new != text:
        path.write_text(new, encoding="utf-8", newline="\n")
    return same


def probes_doc(sites):
    out = []
    for s in sites:
        for what, x, y, z, blk in s.checks:
            out.append({"what": "%s: %s" % (s.id, what), "block": [x, y, z, blk], "expect": True})
        if s.scene:
            for pid, p in s.props.items():
                x, y, z = p["on"]
                out.append({"what": "%s: the %s prop (an interaction box)" % (s.id, pid), "hold": [int(x), int(y), int(z)],
                            "entity": "@e[type=minecraft:interaction,tag=cobblers_prop_%s_%s]" % (s.scene, pid), "count": 1})
    return out


def write_probes(sites, write):
    path = ROOT / "data" / "world_probes.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    want = probes_doc(sites)
    same = doc["places"].get("route4_events") == want
    if write and not same:
        doc["places"]["route4_events"] = want
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return same


# ====================================================================== the pack
def write_pack(sites, out=OUT):
    if out.exists():
        shutil.rmtree(out)
    fn = out / "data" / "cobblers" / "function" / PACK
    fn.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers Route 4's middle event sites (tools/route4_events.py)"}}) + "\n", encoding="utf-8")
    from place_town import forceload_commands
    import function_limits

    def bbox(cmds):
        xs, zs = [], []
        for c in cmds:
            q = c.split()
            if q[0] in ("setblock", "fill"):
                xs += [int(q[1])] + ([int(q[4])] if q[0] == "fill" else [])
                zs += [int(q[3])] + ([int(q[6])] if q[0] == "fill" else [])
        return (min(xs), min(zs), max(xs), max(zs))

    # every site's vegetation is cleared before any site builds (a clear is `replace #minecraft:logs`; one run after a
    # build takes that build's own posts): route_events' rule, kept
    clear = [c for s in sites for c in (["# %s" % s.id] + s.clear_cmds if s.clear_cmds else [])]
    clear = ["# every site's vegetation, cleared before any site builds (tools/route4_events.py)"] + function_limits.ensure_loaded(clear)
    (fn / "00_clear.mcfunction").write_text("\n".join(clear) + "\n", encoding="utf-8", newline="\n")
    for s in sites:
        box = bbox(s.cmds)
        body = [s.cmds[0]] + forceload_commands(box, "add") + s.cmds[1:] + forceload_commands(box, "remove")
        (fn / ("%s.mcfunction" % s.id)).write_text("\n".join(function_limits.split_fills(body)) + "\n", encoding="utf-8", newline="\n")
    (fn / "index.txt").write_text("\n".join(["00_clear"] + [s.id for s in sites]) + "\n", encoding="utf-8", newline="\n")


# ====================================================================== checks
# The spawn-condition blocks (data/spawn_blocks.json) this tool writes ON PURPOSE, and what each can draw. Anything else in
# that file is refused. data/spawn_block_policy.json governs placed TEMPLATES; these are authored builds, so each use is
# argued here instead. Which species actually spawn is decided by the pools (data/spawns.json), not by the block.
SPAWN_OK = {
    "minecraft:pink_petals": "the hollow's and the gate's petals are the point; at most the flower species (combee, cutiefly, comfey, ribombee) where a pool carries them",
    "minecraft:cherry_leaves": "the gate's drifted leaves: the same flower species",
    "minecraft:water": "the hollow's pool, seven cells and two deep: ordinary freshwater",
}


def spawn_condition_blocks():
    return set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])


def base(b):
    return b.split("[")[0].split("{")[0]


def problems(sites, g, road, spec):
    out = []
    for s in sites:
        out += s.road_problems()
    # a block that is a spawn condition must be one this tool declares on purpose (SPAWN_OK)
    cond = spawn_condition_blocks()
    for s in sites:
        for b in sorted({base(v) for v in s.blocks.values()} | {base(v) for (_, _, _, _, v) in s.checks}):
            if b in cond and b not in SPAWN_OK:
                out.append("%s writes %s, a spawn-condition block (data/spawn_blocks.json) this tool does not declare" % (s.id, b))
    # nothing built where a person or an actor stands (feet and head), and every marker has air to stand in
    built = {p: (s.id, v) for s in sites for p, v in s.blocks.items() if v != "minecraft:air"}
    stands = [(n["conversation"], tuple(n["at"])) for s in sites for n in s.npcs] + \
             [("marker %s" % k, tuple(m["at"])) for s in sites for k, m in s.markers.items()]
    for who, (x, y, z) in stands:
        for yy in (y, y + 1):
            if (x, yy, z) in built:
                out.append("%s stands at %s inside %s's %s" % (who, (x, y, z), *built[(x, yy, z)]))
        if g(x, z) + 1 != y:
            out.append("%s at %s is not on the ground (ground y%d)" % (who, (x, y, z), g(x, z)))
    # every prop sits on a block that exists: the ground or one of ours
    for s in sites:
        for pid, p in s.props.items():
            x, y, z = p["on"]
            if (x, y, z) not in s.blocks and g(x, z) < y - 0.5 and g(x, z) != y:
                out.append("%s prop %s sits on %s, which is neither ground nor built" % (s.id, pid, (x, y, z)))
    # the sites' distances from what they were sited against
    trainers = json.loads((ROOT / "data" / "late_route_trainers.json").read_text(encoding="utf-8"))["trainers"]
    seats = [(t["id"], t["seat"][0], t["seat"][2]) for t in trainers if t["id"].startswith("route_04")]
    rng = {"headwall_camp": (10, 40), "steam_hollow": (25, 60), "strayed_load": (70, 150)}
    for sid, (lo, hi) in rng.items():
        c = spec["sites"][sid]
        i, d, w = road.nearest(ROUTE, c["x"], c["z"])
        if not lo <= d <= hi:
            out.append("%s: %.0f blocks from the walked line, outside %s (the route moved?)" % (sid, d, (lo, hi)))
        for tid, tx, tz in seats:
            if math.hypot(tx - c["x"], tz - c["z"]) < 60:
                out.append("%s is %.0f blocks from %s" % (sid, math.hypot(tx - c["x"], tz - c["z"]), tid))
        b = g.box(c["x"] - 8, c["z"] - 8, c["x"] + 8, c["z"] + 8)
        if int(b.max() - b.min()) > 4:
            out.append("%s: ground varies by %d over 17 x 17" % (sid, int(b.max() - b.min())))
    # keep clear of the Merian hut and its neighbours (the ice fishing lodge is being built there tonight: not read here)
    hut = (2813, 1102)
    for s in sites:
        for (x, y, z) in list(s.blocks)[:: max(1, len(s.blocks) // 400)]:
            if math.hypot(x - hut[0], z - hut[1]) < 150:
                out.append("%s writes at %s, within 150 of the Merian hut" % (s.id, (x, y, z)))
                break
    # the gate's earthwork and the cavern pack's mouth are not ours to write over
    mx, mz = spec["sites"]["thaw_gate"]["mouth"]
    for s in sites:
        for (x, y, z), v in s.blocks.items():
            if v != "minecraft:air" and math.hypot(x - mx, z - mz) < 3.5:
                out.append("%s writes %s at %s, within 3.5 of the tunnel mouth" % (s.id, v, (x, y, z)))
    gate = (3029, 3037, 1713, 1715)
    for s in sites:
        for (x, y, z), v in s.blocks.items():
            if gate[0] <= x <= gate[1] and gate[2] <= z <= gate[3] and y >= g(3033, 1714) - 2 and v != "minecraft:air" and s.id != "summit_road":
                out.append("%s writes %s at %s, inside the gate earthwork's box" % (s.id, v, (x, y, z)))
    return out


def verify_world(world, sites):
    """Every planned block stands in a STOPPED staging world; no log or leaves in a cleared volume that we did not build."""
    import build_audit
    w = build_audit.World(Path(world))
    bad, n = [], 0
    planned = {p for s in sites for p in s.blocks}
    for s in sites:
        for (x, y, z), b in s.blocks.items():
            if b == "minecraft:air" and (x, y, z) not in planned:
                continue
            got = w.block(x, y, z)
            n += 1
            if got is None:
                bad.append("%s: %s not loaded" % (s.id, (x, y, z)))
            elif build_audit.base(got) != build_audit.base(b):
                bad.append("%s: %s is %s, planned %s" % (s.id, (x, y, z), got, b))
        for (x0, y0, z0, x1, y1, z1) in s.cleared:
            for x in range(x0, x1 + 1, 3):
                for z in range(z0, z1 + 1, 3):
                    for y in range(y0, y1 + 1):
                        got = w.block(x, y, z) or ""
                        if got.endswith(("_log", "_leaves")) and (x, y, z) not in planned:
                            bad.append("%s: %s at %s left in a clearing" % (s.id, got, (x, y, z)))
                            break
    return n, bad


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=None)
    p.add_argument("--write", action="store_true", help="write the records into data/ (spliced after the Route 3 swablu records)")
    p.add_argument("--verify-world", default=None)
    a = p.parse_args(argv)
    spec = load_spec()
    road = Road4()
    print("walked line:", check_paths_heightmap(road, a.source_root))
    g = G.Ground(a.source_root)
    sites = build(g, road, spec)
    probs = problems(sites, g, road, spec)
    for s in sites:
        for n in s.notes:
            print("  %s: %s" % (s.id, n))
    recs = build_records(spec, sites)
    drift = []
    for key, (fname, arr, anchor, owned) in TARGETS.items():
        if not splice(ROOT / "data" / fname, arr, anchor, owned, recs[key], a.write):
            drift.append("data/%s: this tool's %d records differ from the design" % (fname, len(recs[key])))
    if not write_probes(sites, a.write):
        drift.append("data/world_probes.json places.route4_events differs from the design")
    if a.write:
        print("wrote %s" % ", ".join("%s (%d)" % (k, len(v)) for k, v in recs.items()))
    elif drift:
        print("DRIFT (run --write):")
        for d in drift:
            print("   ", d)
    write_pack(sites)
    print("wrote %d site functions (%d commands) to %s" % (len(sites), sum(len(s.cmds) for s in sites), OUT))
    if probs:
        print("PROBLEMS: %d" % len(probs))
        for x in probs[:40]:
            print("   ", x)
    if a.verify_world:
        n, bad = verify_world(a.verify_world, sites)
        print("verify: %d planned blocks, %d problems" % (n, len(bad)))
        for b in bad[:60]:
            print("   ", b)
        return 1 if bad else 0
    return 1 if (probs or (drift and not a.write)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
