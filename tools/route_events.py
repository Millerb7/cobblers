#!/usr/bin/env python
"""Routes 1-3: the event sites and the trainers' shoulders (docs/story/EARLY_ROUTE_BUILD_HANDOFF.md), built from the
heightmap and the walked route, never from a world.

Each site is a function of block commands (build/datapacks/cobblers_route_events, cobblers:route_events/<site>) and
the positions its scene needs: markers, props, NPCs and the area (written into data/scenes.json with --write-scenes,
and checked against it otherwise, so the scene and the build cannot drift apart). The trainers' seats go to
data/route_trainers.json the same way, for tools/route_trainers.py.

  ground     tools/ground.py, rounded: the top solid block of each column. Feet stand one above.
  the road   the walked line is build/routes/paths.json (the dense A* path of each leg; data/routes.json holds its
             simplified polyline). Where Codex's listed point is ON the walked line (most of them: the handoff
             measured distance to the simplified polyline's vertices, and the dense path runs through the point),
             the scene stands on the shoulder instead, and the record says by how much. Nothing built stands within
             ROAD_CLEAR blocks of the walked line except surface work (a trail's own blocks).
  clearing   vegetation only, by block tag (`fill ... replace #minecraft:logs` and the rest), so terrain is never cut;
             the Nosepass clearing is the measured 40-block circle and the 60 x 16 strip toward the mast
             (data/landmarks.json surge_signal_array), kept below the built elder's crown.
  water      Lake Viltri stands at y103 and the pond west of Mt Clay at y119 (data/rivers.json lakes); water is where
             the rounded ground is below the level, as WorldPainter paints it (checked on staging 2026-09-24).

  python tools/route_events.py [--source-root R]                 write the pack; check scenes and seats agree
  python tools/route_events.py --write-scenes [--source-root R]  also write the positions into data/scenes.json and
                                                                 data/route_trainers.json
  python tools/route_events.py --verify-world <stopped world>    read a staging world and check every block written
                                                                 stands, and no tree is left in a clearing
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ground as G  # noqa: E402

OUT = ROOT / "build" / "datapacks" / "cobblers_route_events"
PATHS = ROOT / "build" / "routes" / "paths.json"
SCENES = ROOT / "data" / "scenes.json"
SEATS = ROOT / "data" / "route_trainers.json"
ROAD_CLEAR = 2                      # no built block within this many blocks of a walked-line cell (surface work aside)
VIltri_Y, POND_Y, SEA_Y = 103, 119, 62
# the ground rule: the verify reads a world only to check (tests/test_ground_rule.py)
WORLD_READS = {"verify_world", "main"}
VEG = ["#minecraft:logs", "#minecraft:leaves", "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern",
       "minecraft:large_fern", "#minecraft:flowers", "minecraft:vine", "minecraft:sweet_berry_bush",
       "#minecraft:saplings", "minecraft:dead_bush", "minecraft:bamboo", "minecraft:moss_carpet"]
SURFACE = {"minecraft:dirt_path", "minecraft:coarse_dirt", "minecraft:rooted_dirt", "minecraft:gravel",
           "minecraft:mud", "minecraft:packed_mud", "minecraft:calcite", "minecraft:mossy_cobblestone",
           "minecraft:podzol", "minecraft:grass_block", "minecraft:sand", "minecraft:suspicious_gravel"}
ROUTES = {1: "route_01_pallet_to_brock", 2: "route_02_brock_to_misty", 3: "route_03_misty_to_surge"}


def sign(wood, rotation, front, back=("", "", "", "")):
    q = lambda ls: ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(ls) + ["", "", "", ""])[:4])
    return "minecraft:%s_sign[rotation=%d]{front_text:{messages:[%s]},back_text:{messages:[%s]}}" % (wood, rotation, q(front), q(back))


def wall_sign(wood, facing, front):
    q = lambda ls: ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(ls) + ["", "", "", ""])[:4])
    return "minecraft:%s_wall_sign[facing=%s]{front_text:{messages:[%s]}}" % (wood, facing, q(front))


def yaw_to(dx, dz):
    """Minecraft yaw facing along (dx, dz): 0 south, 90 west, 180 north, -90 east."""
    return round(math.degrees(math.atan2(-dx, dz)))


REGION = (1000, 1200, 2400, 5450)          # x0, z0, x1, z1: every Route 1-3 path cell and every site, with margin


def check_paths_heightmap(source_root=None):
    """The walked lines must have been routed on the ground these sites stand on.

    build/routes/paths.json records the heightmap it was routed on. When that is the current one, fine. When it is the
    one the Rift sculpt was pressed into (data/world.json heightmap.rift_sculpted_from), the two files are compared bit
    for bit over this whole region: the sculpt only changes columns inside the Rift's box, and if that ever stops being
    true here the routes must be routed again (tools/build_routes.py) before these sites can trust them."""
    import hashlib
    import numpy as np
    from PIL import Image
    import terrain as T
    world_path = ROOT / "data" / "world.json"
    world = T.load_world(world_path)
    have = json.loads(PATHS.read_text(encoding="utf-8"))["heightmap_sha256"]
    if have == world["heightmap"]["sha256"]:
        return "routed on the current heightmap"
    base = world["heightmap"].get("rift_sculpted_from") or {}
    if have != base.get("sha256"):
        raise SystemExit("build/routes/paths.json was routed on heightmap %s, neither the current one nor the one the Rift "
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
        raise SystemExit("the Rift sculpt changed %d columns inside Routes 1-3's region: route again before building here" % diff)
    return "routed on %s, the heightmap before the Rift sculpt; identical to the current one over x%d-%d z%d-%d" % (
        have[:8], x0, x1, z0, z1)


def maze_trunks():
    """{(x, z)} of every planned trunk in the Route 1 maze forest, read from its generated pack the way
    tools/build_audit.py forest() reads it (the object's placement and its template's trunk offset); None when the
    pack is not built."""
    import build_audit
    import place_town
    fdir = ROOT / "build" / "datapacks" / "cobblers_route1" / "data" / "cobblers" / "function" / "route1"
    tiles = sorted(fdir.glob("tile_*.mcfunction"))
    if not tiles:
        return None
    offs = build_audit._trunk_offsets()
    out = set()
    for f in tiles:
        for l in f.read_text(encoding="utf-8").splitlines():
            m = build_audit.PLACE.match(l.strip())
            if not m or m.group(1) not in offs:
                continue
            off = offs[m.group(1)]
            rx, rz = place_town.rotate(off[0], off[2], m.group(5))
            out.add((int(m.group(2)) + rx, int(m.group(4)) + rz))
    return out


_PROTECTED = None


def protected(ax, az, bx, bz):
    """Why a clearing tile must not be cut, or None. Trees that another tool plants are that tool's data: the Route 1
    maze forest (tools/maze_forest.py), the built elders and grove giants (derived/sites/elder_trees.json,
    tree_grove_*.json) and every town's own ground (tools/town_audit.py town_bounds). A clear is `replace
    #minecraft:logs`, so one over a town takes its log walls (Brock's library, on staging 2026-09-24) and one in the
    maze takes planned trunks."""
    global _PROTECTED
    if _PROTECTED is None:
        import maze_forest
        import town_audit
        import reapply
        rects = [("the Route 1 maze forest", maze_forest.BOX)]
        pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
        for sid in ["hometown"] + reapply.places(pl):
            rects.append(("town %s" % sid, town_audit.town_bounds(sid, pl)))
        circles = []
        for f, r in (("elder_trees.json", 26), ("tree_grove_foothill_woods.json", 22)):
            path = ROOT / "derived" / "sites" / f
            if not path.is_file():
                raise SystemExit("%s is missing: run tools/reapply.py prepare (it writes it) before building sites" % path)
            doc = json.loads(path.read_text(encoding="utf-8"))
            sites = [x for rg in doc.get("regions") or [] for x in rg.get("sites") or []] + list(doc.get("sites") or doc.get("trees") or [])
            circles += [("a built tree at (%d, %d)" % (x["x"], x["z"]), x["x"], x["z"], r) for x in sites if "x" in x and "z" in x]
        _PROTECTED = (rects, circles)
    rects, circles = _PROTECTED
    for why, (x0, z0, x1, z1) in rects:
        if ax <= x1 and bx >= x0 and az <= z1 and bz >= z0:
            return why
    for why, cx, cz, r in circles:
        nx, nz = min(max(cx, ax), bx), min(max(cz, az), bz)
        if math.hypot(nx - cx, nz - cz) <= r:
            return why
    return None


class Road:
    def __init__(self):
        self.paths = {k: [tuple(p) for p in v] for k, v in json.loads(PATHS.read_text(encoding="utf-8"))["paths"].items()}
        for k in ("route_01_pallet_to_brock", "route_02_brock_to_misty", "route_03_misty_to_surge"):
            xs, zs = [p[0] for p in self.paths[k]], [p[1] for p in self.paths[k]]
            if min(xs) < REGION[0] or max(xs) > REGION[2] or min(zs) < REGION[1] or max(zs) > REGION[3]:
                raise SystemExit("%s leaves REGION %s: widen it" % (k, REGION))
        self.cells = {k: set(v) for k, v in self.paths.items()}
        self.walked = {}
        for k, v in self.paths.items():
            d, acc = [0.0], 0.0
            for a, b in zip(v, v[1:]):
                acc += math.hypot(b[0] - a[0], b[1] - a[1])
                d.append(acc)
            self.walked[k] = d

    def nearest(self, route, x, z):
        best = min(range(len(self.paths[route])), key=lambda i: (self.paths[route][i][0] - x) ** 2 + (self.paths[route][i][1] - z) ** 2)
        px, pz = self.paths[route][best]
        return best, math.hypot(px - x, pz - z), self.walked[route][best]

    def frame(self, route, i, span=6):
        """(tangent, normal) unit vectors at path index i; normal is the tangent turned right (x, z) -> (-z, x)."""
        p = self.paths[route]
        a, b = p[max(0, i - span)], p[min(len(p) - 1, i + span)]
        tx, tz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tx, tz) or 1.0
        tx, tz = tx / L, tz / L
        return (tx, tz), (-tz, tx)

    def near_any(self, x, z, r):
        for cells in self.cells.values():
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if (x + dx, z + dz) in cells:
                        return True
        return False


class Site:
    """One site's commands and scene positions, in world coordinates, ground from the heightmap."""

    def __init__(self, sid, g, road, scene=None, title=""):
        self.id, self.g, self.road, self.scene, self.title = sid, g, road, scene, title
        self.cmds = ["# %s: %s (tools/route_events.py)" % (sid, title)]
        self.blocks = {}            # (x, y, z) -> block, last write wins
        self.surface = set()        # cells written as ground surface (a trail), allowed on the road
        self.cleared = []           # (x0, y0, z0, x1, y1, z1) vegetation-cleared volumes
        self.kept = set()           # protected areas a clear left alone (their trees are other tools' data)
        self.clear_cmds = []        # emitted before anything is built: a later clear would take the build's own logs
        self.markers, self.props, self.npcs, self.area = {}, {}, [], None
        self.notes = []

    def gy(self, x, z):
        return self.g(int(round(x)), int(round(z)))

    def set(self, x, y, z, b, surface=False):
        x, y, z = int(x), int(y), int(z)
        self.cmds.append("setblock %d %d %d %s" % (x, y, z, b))
        self.blocks[(x, y, z)] = b.split("{")[0]
        if surface:
            self.surface.add((x, z))

    def fill(self, a, c, b, surface=False):
        (x0, y0, z0), (x1, y1, z1) = a, c
        self.cmds.append("fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, b))
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    self.blocks[(x, y, z)] = b
                    if surface:
                        self.surface.add((x, z))

    def on_ground(self, x, z, b, dy=1):
        """A block standing on the ground at (x, z): dy 1 is the first block above the ground."""
        y = self.gy(x, z) + dy
        self.set(x, y, z, b)
        return y

    def ground_block(self, x, z, b):
        """Replace the ground's top block (a trail, a painted mark): surface work, allowed near the road."""
        self.set(x, self.gy(x, z), z, b, surface=True)

    def clear(self, x0, z0, x1, z1, up=18, down=1, cells=None):
        """Vegetation out of a box (or only the tiles of it whose centre is in `cells`): terrain is never touched."""
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
                for pred in VEG:
                    self.clear_cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (ax, y0, az, bx, y1, bz, pred))
                self.cleared.append((ax, y0, az, bx, y1, bz))

    def trail(self, pts, block="minecraft:dirt_path", width=1, clear=True):
        """A walked trail over the ground between the points (straight segments), surface work only."""
        cells = []
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            n = max(abs(bx - ax), abs(bz - az), 1)
            for k in range(n + 1):
                x, z = round(ax + (bx - ax) * k / n), round(az + (bz - az) * k / n)
                for w in range(-(width // 2), width - width // 2):
                    c = (x + w, z) if abs(bz - az) >= abs(bx - ax) else (x, z + w)
                    if c not in cells:
                        cells.append(c)
        for x, z in cells:
            self.ground_block(x, z, block)
        if clear:
            xs, zs = [c[0] for c in cells], [c[1] for c in cells]
            self.clear(min(xs) - 1, min(zs) - 1, max(xs) + 1, max(zs) + 1, up=6, cells=lambda cx, cz: any(abs(cx - x) <= 7 and abs(cz - z) <= 7 for x, z in cells))
        return cells

    def marker(self, name, x, z, yaw=0, dy=1, slots=None, y=None):
        y = self.gy(x, z) + dy if y is None else y
        m = {"at": [int(x), int(y), int(z)], "yaw": int(yaw)}
        if slots:
            m["slots"] = slots
        self.markers[name] = m
        return m

    def prop(self, pid, on, size=(0.9, 1.2), dy=0.0):
        """A clickable prop on the block `on` (x, y, z): the box starts on that block's top half."""
        x, y, z = on
        self.props[pid] = {"at": [x + 0.5, round(y + dy, 2), z + 0.5], "size": list(size), "on": [x, y, z]}

    def npc(self, conversation, x, z, yaw=0, y=None):
        y = self.gy(x, z) + 1 if y is None else y
        self.npcs.append({"conversation": conversation, "at": [int(x), int(y), int(z)], "yaw": int(yaw)})

    def set_area(self, x0, z0, x1, z1, below=6, above=14):
        hs = [self.g(x, z) for x in range(x0, x1 + 1, 4) for z in range(z0, z1 + 1, 4)]
        self.area = {"from": [x0, min(hs) - below, z0], "to": [x1, max(hs) + above, z1]}

    # ------------------------------------------------------------------ checks
    def road_problems(self):
        """Built blocks too close to a walked line (surface work aside)."""
        out = []
        seen = set()
        for (x, y, z), b in self.blocks.items():
            if b == "minecraft:air" or (x, z) in self.surface or (x, z) in seen:
                continue
            seen.add((x, z))
            if self.road.near_any(x, z, ROAD_CLEAR - 1):
                out.append("%s: %s at %s is within %d of the walked line" % (self.id, b, (x, y, z), ROAD_CLEAR - 1))
        return out


# ====================================================================== the sites
def seat(road, g, rid, tid, x, z, offset=3):
    """A trainer's seat: the listed point if it is off the walked line, else `offset` blocks onto the flatter shoulder,
    facing the road. (seat x, z, yaw, walked distance, listed point's distance from the line)."""
    route = ROUTES[rid]
    i, d, walked = road.nearest(route, x, z)
    px, pz = road.paths[route][i]
    (tx, tz), (nx, nz) = road.frame(route, i)
    if d >= ROAD_CLEAR + 0.5:
        sx, sz = x, z
    else:
        best = None
        for s in (1, -1):
            cx, cz = round(px + s * nx * offset), round(pz + s * nz * offset)
            score = abs(g(cx, cz) - g(px, pz))
            if best is None or score < best[0]:
                best = (score, cx, cz)
        _, sx, sz = best
    return sx, sz, yaw_to(px - sx, pz - sz), walked, d


def mansion_junction(g, road):
    s = Site("mansion_junction", g, road, None, "the signed side trail to the mansion, where the spur leaves Route 1")
    # the spur (tools/maze_forest.py spur_mansion) leaves the entrance stretch at (1466, 5036) eastward
    x, z = 1471, 5039
    s.on_ground(x, z, "minecraft:dark_oak_fence")
    s.on_ground(x, z, sign("dark_oak", 12, ["The old manor", "east, past the trees", "", "keep to the path"]), dy=2)
    return s


def picnic(g, road):
    s = Site("route1_picnic", g, road, "route1_rattata_picnic", "EVT-ROUTE1-RATTATA-PICNIC: blanket, open basket, three hiding places, the berry stump")
    # in the picnic glade west of the walked line (tools/maze_forest.py CLEARINGS "picnic")
    for x in range(1446, 1450):
        for z in range(4826, 4830):
            s.on_ground(x, z, "minecraft:%s_carpet" % ("red" if (x + z) % 2 else "pink"))
    s.on_ground(1450, 4828, "minecraft:barrel[facing=up,open=true]")                 # the open basket
    s.on_ground(1449, 4830, "handcrafted:wood_plate[facing=north,pieces=1,waterlogged=false]")
    # hiding place 1 (the right one): a hollow log, the crumbs lead to it
    for x in range(1442, 1445):
        s.on_ground(x, 4822, "minecraft:oak_log[axis=x]")
    s.on_ground(1441, 4822, "minecraft:oak_trapdoor[facing=east,half=bottom,open=true,powered=false,waterlogged=false]")
    s.prop("hollow_log", (1443, s.gy(1443, 4822) + 1, 4822), (2.8, 1.2))
    # hiding place 2: a dense bush
    for dx, dz, dy in ((0, 0, 1), (1, 0, 1), (0, 1, 1), (0, 0, 2)):
        s.on_ground(1444 + dx, 4833 + dz, "minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]", dy=dy)
    s.prop("bush", (1444, s.gy(1444, 4833) + 1, 4833), (2.0, 2.0))
    # hiding place 3: an overturned crate
    s.on_ground(1455 - 8, 4817, "minecraft:barrel[facing=north,open=false]")
    s.prop("crate", (1447, s.gy(1447, 4817) + 1, 4817), (1.0, 1.1))
    # the berry stump, off the walking line
    s.on_ground(1440, 4828, "minecraft:stripped_oak_log[axis=y]")
    s.prop("stump", (1440, s.gy(1440, 4828) + 1, 4828), (1.0, 1.2))
    s.npc("dlg_route1_rattata_picnic", 1448, 4831, yaw=180)
    s.marker("rattata_stump", 1441, 4829, yaw=90, slots=[[0, 0], [0, 0.9]])
    s.marker("rattata_basket", 1451, 4827, yaw=90, slots=[[0, 0], [0.9, 0]])
    s.set_area(1434, 4812, 1460, 4840)
    return s


def stranger_hut(g, road):
    s = Site("route1_stranger_hut", g, road, "route1_thirsty_stranger", "EVT-ROUTE1-THIRSTY-STRANGER: the hut, entrance toward (1509, 4469)")
    x0, z0, x1, z1 = 1517, 4458, 1525, 4464                                         # 9 x 7, east of the road
    f = max(g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))         # floor on the highest ground
    s.fill((x0, f - 3, z0), (x1, f, z1), "minecraft:packed_mud")                      # a mud-brick plinth
    s.fill((x0, f + 1, z0), (x1, f + 5, z1), "minecraft:air")
    s.fill((x0, f, z0), (x1, f, z1), "minecraft:spruce_planks")
    for y in range(f + 1, f + 4):
        s.fill((x0, y, z0), (x1, y, z0), "minecraft:mud_bricks")
        s.fill((x0, y, z1), (x1, y, z1), "minecraft:mud_bricks")
        s.fill((x0, y, z0), (x0, y, z1), "minecraft:mud_bricks")
        s.fill((x1, y, z0), (x1, y, z1), "minecraft:mud_bricks")
    s.fill((x0 - 1, f + 4, z0 - 1), (x1 + 1, f + 4, z1 + 1), "minecraft:spruce_slab[type=bottom]")
    s.fill((x0, f + 1, 4462), (x0, f + 2, 4462), "minecraft:air")                    # the doorway, west wall
    s.set(x0, f + 2, 4460, "minecraft:glass_pane")
    s.set(x1, f + 2, 4461, "minecraft:glass_pane")
    s.set(1519, f + 1, 4459, "handcrafted:spruce_table[color=none,shape=single,waterlogged=false]")
    s.set(1519, f + 2, 4459, "handcrafted:wood_cup[facing=west,pieces=1,waterlogged=false]")   # the empty cup
    s.set(1520, f + 1, 4460, "handcrafted:spruce_chair[color=none,facing=north,waterlogged=false]")
    s.set(1524, f + 1, 4459, "minecraft:chest[facing=west,type=single,waterlogged=false]")      # decorative
    s.set(1523, f + 1, 4463, "minecraft:brown_carpet")                                          # the bedroll
    s.set(1524, f + 1, 4463, "minecraft:brown_carpet")
    s.set(1522, f + 3, 4461, "minecraft:lantern[hanging=true,waterlogged=false]")
    # no trail: the glade opens off the corridor, and a trail to the door would cross the maze's planned trunks
    s.npc("dlg_route1_thirsty_stranger", 1521, 4461, yaw=90, y=f + 1)
    s.set_area(1508, 4452, 1530, 4470)
    return s


def first_cast(g, road):
    s = Site("route1_first_cast", g, road, "route1_first_cast", "EVT-ROUTE1-FIRST-CAST: the jetty and the signed footpath from Pallet")
    deck = 64
    x_shore, zc = 1058, 5349
    for x in range(x_shore - 9, x_shore):                                             # 5 x 9 jetty, west over the flats
        for z in range(zc - 2, zc + 3):
            s.set(x, deck, z, "minecraft:spruce_planks" if (x + z) % 4 else "minecraft:stripped_spruce_wood[axis=x]")
        if (x - x_shore) % 3 == 0:
            for z in (zc - 2, zc + 2):                                                 # piles
                s.fill((x, g(x, z) + 1, z), (x, deck - 1, z), "minecraft:spruce_log[axis=y]")
    for x in range(x_shore - 9, x_shore, 2):
        s.set(x, deck + 1, zc - 2, "minecraft:spruce_fence")
    s.fill((x_shore, g(x_shore, zc) + 1, zc - 1), (x_shore + 1, deck, zc + 1), "minecraft:spruce_planks")   # the step up
    s.set(x_shore - 8, deck + 1, zc + 1, "handcrafted:spruce_chair[color=none,facing=west,waterlogged=false]")   # the stool
    s.set(x_shore - 3, deck + 1, zc + 2, "minecraft:barrel[facing=up,open=false]")                               # tackle
    s.fill((x_shore - 5, deck + 1, zc + 2), (x_shore - 5, deck + 2, zc + 2), "minecraft:spruce_fence")          # the rack
    s.set(x_shore - 5, deck + 3, zc + 2, "minecraft:spruce_slab[type=bottom]")
    s.prop("rack", (x_shore - 5, deck + 1, zc + 2), (0.9, 2.2))
    s.npc("dlg_route1_first_cast", x_shore - 6, zc, yaw=90, y=deck + 1)
    # the footpath from Pallet's west side to the jetty: the gentlest line over open meadow
    pts = [(1392, 5292), (1330, 5300), (1260, 5316), (1190, 5330), (1120, 5342), (x_shore + 2, zc)]
    s.trail(pts, "minecraft:dirt_path", width=2)
    s.on_ground(1392, 5294, "minecraft:spruce_fence")
    s.on_ground(1392, 5294, sign("spruce", 4, ["West to the water", "fishing jetty", "", ""]), dy=2)
    s.on_ground(x_shore + 3, zc - 3, "minecraft:spruce_fence")
    s.on_ground(x_shore + 3, zc - 3, sign("spruce", 12, ["Pallet", "east along the path", "", ""]), dy=2)
    s.set_area(x_shore - 12, zc - 8, x_shore + 6, zc + 8)
    return s


def geodude(g, road):
    s = Site("route2_geodude", g, road, "route2_rollaway_geodude", "EVT-ROUTE2-ROLLAWAY-GEODUDE: brake, rut, sack, boulder, the tree that stopped it")
    s.clear(1748, 3510, 1776, 3534, up=16)
    # the miner and the empty brake position, west of the walked line at (1756, 3528)
    s.npc("dlg_route2_rollaway_geodude", 1752, 3528, yaw=-90)
    s.on_ground(1753, 3526, "minecraft:spruce_trapdoor[facing=east,half=bottom,open=false,powered=false,waterlogged=false]")  # the chock
    # the rut: fifteen blocks east of the line, from the brake position down to the cart
    rut = [(1759 + k * 9 // 14, 3527 - k * 8 // 14) for k in range(15)]
    for x, z in rut:
        s.ground_block(x, z, "minecraft:rooted_dirt")
    s.prop("rut", (rut[7][0], s.gy(*rut[7]), rut[7][1]), (1.0, 1.0), dy=1)
    # the split sample sack beside the rut
    s.on_ground(1764, 3524, "minecraft:brown_wool")
    for x, z in ((1765, 3524), (1764, 3525)):
        s.on_ground(x, z, "minecraft:gravel")
    s.prop("sack", (1764, s.gy(1764, 3524) + 1, 3524), (1.0, 1.1))
    # the chipped boulder
    for dx, dz, dy in ((0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1), (0, 0, 2), (1, 1, 2)):
        s.on_ground(1771 + dx, 3524 + dz, "minecraft:andesite" if dy == 1 else "minecraft:cobblestone", dy=dy)
    s.on_ground(1771, 3526, "minecraft:andesite_slab[type=bottom,waterlogged=false]")
    s.prop("boulder", (1771, s.gy(1771, 3524) + 2, 3524), (2.0, 1.2))
    # the tree that caught the cart, and the cart against it
    tx, tz = 1773, 3515
    base = g(tx, tz)
    s.fill((tx, base + 1, tz), (tx, base + 6, tz), "minecraft:birch_log[axis=y]")
    for dy in (5, 6, 7):
        r = 2 if dy < 7 else 1
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if (dx, dz) != (0, 0) and abs(dx) + abs(dz) <= r + 1:
                    s.set(tx + dx, base + dy, tz + dz, "minecraft:birch_leaves[distance=1,persistent=true,waterlogged=false]")
    s.set(tx, base + 7, tz, "minecraft:birch_leaves[distance=1,persistent=true,waterlogged=false]")
    cx, cz = 1770, 3517
    cy = s.on_ground(cx, cz, "minecraft:barrel[facing=east,open=false]")
    s.set(cx + 1, cy, cz, "minecraft:barrel[facing=east,open=false]")
    for x in (cx, cx + 1):
        s.set(x, cy, cz - 1, "minecraft:spruce_trapdoor[facing=north,half=bottom,open=true,powered=false,waterlogged=false]")
        s.set(x, cy, cz + 1, "minecraft:spruce_trapdoor[facing=south,half=bottom,open=true,powered=false,waterlogged=false]")
    s.set(cx - 1, cy, cz, "minecraft:lever[face=floor,facing=west,powered=false]")                         # its brake
    s.prop("brake", (cx - 1, cy, cz), (0.8, 0.9))
    s.marker("geodude_cart", cx + 1, cz - 2, yaw=0, slots=[[0, 0], [0.9, 0], [-0.9, 0]])
    s.marker("geodude_home", 1753, 3530, yaw=-90, slots=[[0, 0], [0, 0.9], [-0.9, 0]])
    s.set_area(1744, 3506, 1780, 3540)
    return s


def sounding(g, road):
    s = Site("route2_sounding", g, road, "route2_viltri_sounding", "EVT-ROUTE2-VILTRI-SOUNDING: the keeper at the listed station, the platform at the waterline below it")
    # the listed station (1779, 3011) is 11 above the lake and 48 from its water: the keeper keeps the view there,
    # and a stepped path goes down the bank to a platform at the waterline (the staffs must stand in water)
    # the walked line runs through the listed station itself, so the keeper stands just west of it, on the lake side
    s.npc("dlg_route2_viltri_sounding", 1773, 3010, yaw=90)
    s.on_ground(1771, 3007, "minecraft:spruce_fence")
    s.on_ground(1771, 3007, sign("spruce", 4, ["Viltri sounding", "down to the water", "", ""]), dy=2)
    s.trail([(1772, 3012), (1760, 3012), (1745, 3012), (1735, 3011)], "minecraft:coarse_dirt", width=2)
    # the platform: 7 x 9, deck one above the water, from the bank out over the shallows
    deck = VIltri_Y + 1
    for x in range(1725, 1734):
        for z in range(3008, 3015):
            s.set(x, deck, z, "minecraft:spruce_planks")
        if x % 4 == 1:
            for z in (3008, 3014):
                s.fill((x, g(x, z) + 1, z), (x, deck - 1, z), "minecraft:spruce_log[axis=y]")
    for z in range(3008, 3015, 2):
        s.set(1725, deck + 1, z, "minecraft:spruce_fence")
    # three depth staffs at three shelves: posts from the bed to above the water, a band at the water line
    staffs = [("shallow", 1722, 3006), ("middle", 1716, 3012), ("deep", 1708, 3018)]
    for name, x, z in staffs:
        bed = g(x, z)
        s.fill((x, bed + 1, z), (x, VIltri_Y + 3, z), "minecraft:stripped_spruce_log[axis=y]")
        s.set(x, VIltri_Y + 1, z, "minecraft:blue_wool")
        s.set(x, VIltri_Y + 3, z, "minecraft:spruce_trapdoor[facing=east,half=top,open=false,powered=false,waterlogged=false]")
        s.prop("staff_%s" % name, (x, VIltri_Y + 1, z), (0.8, 3.0))
        s.notes.append("staff %s at (%d, %d): bed y%d, water %d deep" % (name, x, z, bed, VIltri_Y - bed))
    # the floating gauge on its short tether, and the post the tether was clawed off
    gx, gz = 1721, 3016
    s.set(gx, VIltri_Y, gz, "minecraft:spruce_slab[type=top,waterlogged=true]")
    s.set(gx, VIltri_Y + 1, gz, "minecraft:lightning_rod[facing=up,powered=false,waterlogged=false]")
    s.fill((gx + 1, VIltri_Y + 1, gz), (1724, VIltri_Y + 1, gz), "minecraft:chain[axis=x,waterlogged=true]")
    s.prop("gauge", (gx, VIltri_Y + 1, gz), (1.0, 1.0))
    s.set(1725, deck + 1, 3015, "minecraft:stripped_spruce_log[axis=y]")                                 # the clawed post
    s.prop("claw_post", (1725, deck + 1, 3015), (0.8, 1.1))
    s.clear(1704, 3002, 1736, 3024, up=14)
    s.marker("corphish", 1727, 3014, yaw=-90, y=deck + 1, slots=[[0, 0], [0.9, 0], [0, -0.9]])
    s.marker("lotad_shelf", 1716, 3011, yaw=90, y=VIltri_Y, slots=[[0, 0], [0.9, 0.9], [-0.9, 0.9]])
    s.set_area(1700, 2998, 1784, 3028)
    return s


def north_bank(g, road):
    s = Site("route2_north_bank", g, road, "viltri_north_bank", "EVT-VILTRI-NORTH-BANK: the platform, net rack, beached skiff and the shore ring trail")
    deck = VIltri_Y + 2
    for x in range(1601, 1608):
        for z in range(3060, 3069):
            s.set(x, deck, z, "minecraft:spruce_planks" if (x + z) % 5 else "minecraft:stripped_spruce_wood[axis=z]")
        if x in (1601, 1604, 1607):
            for z in (3060, 3064):
                s.fill((x, g(x, z) + 1, z), (x, deck - 1, z), "minecraft:spruce_log[axis=y]")
    for x in (1601, 1607):
        s.set(x, deck + 1, 3060, "minecraft:spruce_fence")
    # the net rack: posts and a chain line on the bank
    for z in (3071, 3075):
        s.fill((1610, g(1610, z) + 1, z), (1610, g(1610, z) + 3, z), "minecraft:spruce_fence")
    s.fill((1610, g(1610, 3073) + 3, 3072), (1610, g(1610, 3073) + 3, 3074), "minecraft:chain[axis=z,waterlogged=false]")
    # the beached skiff, keel up on the bank
    for x in range(1595, 1599):
        s.on_ground(x, 3069, "minecraft:spruce_stairs[facing=north,half=top,shape=straight,waterlogged=false]")
        s.on_ground(x, 3070, "minecraft:spruce_stairs[facing=south,half=top,shape=straight,waterlogged=false]")
    s.on_ground(1597, 3068, "minecraft:barrel[facing=up,open=true]")                                  # the tackle box
    s.prop("tackle", (1597, s.gy(1597, 3068) + 1, 3068), (1.0, 1.1))
    s.clear(1590, 3056, 1616, 3080, up=14)
    # the ring trail from the sounding station along the bank (tools/route_events.py measures it below)
    ring = [(1735, 3016), (1722, 3032), (1700, 3046), (1676, 3058), (1650, 3066), (1628, 3070), (1608, 3071)]
    cells = s.trail(ring, "minecraft:coarse_dirt", width=2)
    s.notes.append("ring trail %d cells from the sounding platform to the north bank" % len(cells))
    s.set_area(1586, 3052, 1620, 3084)
    return s


def nosepass(g, road):
    s = Site("route3_nosepass", g, road, "route3_nosepass_signs", "EVT-ROUTE3-NOSEPASS-SIGNS and EVT-ROUTE3-CREEK-WOOPER: one stop, the clearing, the signs, the shelter, the pond shore")
    SX, SZ = 2186, 1606
    MX, MZ = 1928, 1248
    ux, uz = (MX - SX) / math.hypot(MX - SX, MZ - SZ), (MZ - SZ) / math.hypot(MX - SX, MZ - SZ)
    EX, EZ = 2236, 1622                                                                   # the built elder

    def in_clearing(cx, cz):
        if math.hypot(cx - SX, cz - SZ) <= 40:
            return True
        t = (cx - SX) * ux + (cz - SZ) * uz
        lat = abs((cx - SX) * uz - (cz - SZ) * ux)
        return 0 <= t <= 60 and lat <= 8

    # up to 30 above the ground: the elder's crown is y180-205, far above (data/landmarks.json elder_clearance)
    s.clear(SX - 46, SZ - 64, SX + 46, SZ + 46, up=30, down=2, cells=lambda cx, cz: in_clearing(cx, cz) and math.hypot(cx - EX, cz - EZ) > 24)
    s.notes.append("clearing: 40-block circle round the signs and 60 x 16 strip toward the mast, vegetation only, "
                   "tiles within 24 of the elder's trunk left alone")
    # a few stumps: the clearing was cut for the view, and reads that way
    for x, z in ((2170, 1590), (2200, 1586), (2166, 1618), (2158, 1570)):
        s.on_ground(x, z, "minecraft:spruce_log[axis=y]")
    # three signs on the north shoulder, each with a painted ground mark in front
    signs = [("a", 2182, 1602, 6, ["Surge's shelf", "west, then up", "", ""]),
             ("b", 2186, 1601, 8, ["Viltri", "back the way", "you came", ""]),
             ("c", 2190, 1602, 10, ["Mt Clay pond", "south, off the path", "", ""])]
    for k, x, z, rot, text in signs:
        s.on_ground(x, z, "minecraft:spruce_fence")
        s.on_ground(x, z, sign("spruce", rot, text), dy=2)
        s.ground_block(x, z + 1, "minecraft:calcite")                                     # the painted mark
        s.prop("sign_%s" % k, (x, s.gy(x, z) + 1, z), (0.9, 2.0))
    # the trail keeper's shelter, north of the signs: a lean-to of spruce with a bench
    hx, hz = 2194, 1596
    f = g(hx, hz)
    for dx in (0, 3):
        for dz in (0, 3):
            s.fill((hx + dx, g(hx + dx, hz + dz) + 1, hz + dz), (hx + dx, f + 3, hz + dz), "minecraft:spruce_fence")
    s.fill((hx - 1, f + 4, hz - 1), (hx + 4, f + 4, hz + 4), "minecraft:spruce_slab[type=bottom,waterlogged=false]")
    s.set(hx + 1, f + 1, hz + 1, "minecraft:spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]")
    s.set(hx + 2, f + 1, hz + 1, "minecraft:spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]")
    s.set(hx + 3, f + 1, hz, "minecraft:barrel[facing=up,open=false]")
    s.npc("dlg_route3_nosepass_signs", hx + 1, hz + 3, yaw=0)
    s.marker("nosepass_north", 2186, 1597, yaw=180, slots=[[0, 0], [1.2, 0], [-1.2, 0], [0, -1.2]])
    s.marker("nosepass_mast", 2186, 1597, yaw=yaw_to(ux, uz), slots=[[0, 0], [1.2, 0], [-1.2, 0], [0, -1.2]])
    s.set_area(SX - 22, SZ - 18, SX + 22, SZ + 8)
    return s


def creek_wooper(g, road):
    """The pond shore 24 blocks south of the Nosepass signs. The listed (2204, 1580) is a vertex of the pond's
    annotation outline, 8 above the water and 54 from it; the water's nearest shore to the signs is here, inside the
    same clearing, so the two scenes are the one stop the design wants."""
    s = Site("route3_creek_wooper", g, road, "route3_creek_wooper", "EVT-ROUTE3-CREEK-WOOPER: the shore pocket, three approaches, the crate, the pool")
    s.trail([(2186, 1609), (2186, 1618), (2188, 1626)], "minecraft:coarse_dirt")
    s.npc("dlg_route3_creek_wooper", 2190, 1624, yaw=180)
    s.on_ground(2192, 1623, "minecraft:barrel[facing=up,open=true]")                      # the courier's cart load
    # three approaches from the courier to the shallows: the feeding patch (west), deep mud (south), dry stones (east)
    for x, z in ((2184, 1626), (2183, 1627), (2182, 1628)):
        s.ground_block(x, z, "minecraft:mud")                                             # the feeding patch's soft edge
    s.prop("approach_feeding", (2184, s.gy(2184, 1626), 1626), (1.2, 1.0), dy=1)
    for x, z in ((2188, 1628), (2188, 1629), (2187, 1630)):
        s.ground_block(x, z, "minecraft:mud")
    s.prop("approach_mud", (2188, s.gy(2188, 1628), 1628), (1.2, 1.0), dy=1)
    for x, z in ((2191, 1627), (2191, 1629), (2190, 1631), (2188, 1632)):
        s.ground_block(x, z, "minecraft:mossy_cobblestone")                               # dry lichen stones
    s.prop("approach_stones", (2191, s.gy(2191, 1627), 1627), (1.2, 1.0), dy=1)
    # the crate in the shallows
    cx, cz = 2182, 1632
    s.set(cx, POND_Y - 1, cz, "minecraft:barrel[facing=up,open=false]")
    s.prop("crate", (cx, POND_Y - 1, cz), (1.0, 1.4))
    s.marker("wooper_feeding", 2178, 1630, yaw=90, slots=[[0, 0], [0.9, 0.5], [-0.9, 0.5], [0, -0.9]])
    s.marker("wooper_pool", 2192, 1631, yaw=180)
    s.set_area(2168, 1612, 2204, 1642)
    return s


def mast(g, road):
    s = Site("surge_mast", g, road, None, "the signal array's mast on its Mt Vessu shoulder: 12 blocks, as measured")
    x, z = 1928, 1248
    base = g(x, z)
    s.fill((x - 1, base, z - 1), (x + 1, base, z + 1), "minecraft:polished_andesite")
    s.fill((x, base + 1, z), (x, base + 11, z), "minecraft:iron_bars")
    for y in range(base + 1, base + 12, 3):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            s.set(x + dx, y, z + dz, "minecraft:iron_bars")
    s.set(x, base + 12, z, "minecraft:lightning_rod[facing=up,powered=false,waterlogged=false]")
    s.set(x, base + 11, z, "minecraft:redstone_lamp[lit=false]")
    s.notes.append("the rest of the array (Surge's equipment) is not built; only the mast the Nosepass signs look at")
    return s


def swablu(g, road):
    s = Site("route3_swablu", g, road, "route3_swablu_nest", "EVT-ROUTE3-SWABLU-NEST: the cut-bank nest, the torn flag, fibers, the bench uphill")
    # the nest in the cut bank on the north shoulder of the walked line, 36 blocks east of the ranger's bench
    for x in range(2010, 2019):
        s.ground_block(x, 1602, "minecraft:coarse_dirt")
        s.on_ground(x, 1601, "minecraft:rooted_dirt")
    nx, nz = 2014, 1601
    ny = s.gy(nx, nz) + 2
    s.set(nx, ny, nz, "minecraft:hay_block[axis=y]")
    s.set(nx - 1, ny, nz, "minecraft:moss_block")
    s.set(nx + 1, ny, nz, "minecraft:blue_wool")                                        # the flag's fibers woven in
    s.prop("nest", (nx, ny, nz), (2.8, 1.2))
    # the torn route flag on its pole by the nest
    s.fill((2019, s.gy(2019, 1602) + 1, 1602), (2019, s.gy(2019, 1602) + 4, 1602), "minecraft:spruce_fence")
    s.set(2019, s.gy(2019, 1602) + 4, 1603, "minecraft:blue_wall_banner[facing=south]")
    # three piles of soft fallen fiber along the bank
    for k, (x, z) in enumerate(((2004, 1600), (2023, 1599), (2009, 1597))):
        s.on_ground(x, z, "minecraft:moss_carpet")
        s.prop("fiber_%d" % (k + 1), (x, s.gy(x, z) + 1, z), (1.0, 0.6))
    s.clear(2000, 1592, 2026, 1604, up=14)
    # the sheltered bench farther up, where the Vessu Ranger keeps watch: no healing, no PC, no flag
    bx, bz = 1980, 1600
    for x in (bx, bx + 1):
        s.on_ground(x, bz, "minecraft:spruce_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]")
    s.on_ground(bx - 1, bz - 1, "minecraft:spruce_fence")
    s.on_ground(bx + 2, bz - 1, "minecraft:spruce_fence")
    top = max(s.gy(bx - 1, bz - 1), s.gy(bx + 2, bz - 1)) + 3
    s.fill((bx - 1, top, bz - 1), (bx + 2, top, bz), "minecraft:spruce_slab[type=bottom,waterlogged=false]")
    for x in (bx - 1, bx + 2):
        s.fill((x, s.gy(x, bz - 1) + 2, bz - 1), (x, top - 1, bz - 1), "minecraft:spruce_fence")
    s.npc("dlg_route3_swablu_nest", 2016, 1598, yaw=0)
    s.marker("swablu_nest", 2014, 1601, yaw=0, y=ny + 1, slots=[[0, 0], [1.0, 0], [-1.0, 0]])
    s.set_area(1996, 1588, 2030, 1612)
    return s


def trainer_props(g, road, seats):
    """The trainers' shoulders: the small thing each stands by (the handoff's physical placement column)."""
    s = Site("route_trainer_shoulders", g, road, None, "what each Route 1-3 trainer stands by")
    for t in seats:
        x, z, tid = t["seat"][0], t["seat"][2], t["id"]
        yaw = t["yaw"]
        # the thing each stands by goes one block behind them, away from the road they face
        back_x, back_z = x - round(-math.sin(math.radians(yaw)) * 1.0), z - round(math.cos(math.radians(yaw)) * 1.0)
        if tid == "route_01_trainer_02":                                             # hives and flower boxes
            for dx, dz in ((-2, 2), (-2, -1)):
                s.on_ground(x + dx, z + dz, "minecraft:beehive[facing=east,honey_level=3]")
            for dz in range(-1, 3):
                s.on_ground(x - 4, z + dz, "minecraft:oak_trapdoor[facing=west,half=bottom,open=true,powered=false,waterlogged=false]")
                s.on_ground(x - 3, z + dz, "minecraft:%s" % ("poppy" if dz % 2 else "cornflower"))
        elif tid == "route_01_trainer_03":                                           # a dry-vale observation post
            s.on_ground(back_x, back_z, "minecraft:spruce_fence")
            s.on_ground(back_x, back_z, "minecraft:lectern[facing=north,has_book=false,powered=false]", dy=2)
        elif tid == "route_01_trainer_04":                                           # guide post and Brock warning
            s.on_ground(back_x, back_z, "minecraft:spruce_fence")
            s.on_ground(back_x, back_z, sign("spruce", ((yaw % 360) * 16 // 360 + 8) % 16,
                                             ["Brock's gym ahead", "Rock survives", "the first hit.", "Bring two answers."]), dy=2)
        elif tid == "route_02_trainer_01":                                           # a small gravel turnout
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    s.ground_block(back_x + dx, back_z + dz, "minecraft:gravel")
        elif tid == "route_02_trainer_02":                                           # two hooded lantern posts
            for side in (-2, 2):
                px, pz = back_x + (side if abs(math.cos(math.radians(yaw))) > 0.7 else 0), back_z + (side if abs(math.cos(math.radians(yaw))) <= 0.7 else 0)
                y0 = s.gy(px, pz)
                s.fill((px, y0 + 1, pz), (px, y0 + 2, pz), "minecraft:spruce_fence")
                s.set(px, y0 + 3, pz, "minecraft:lantern[hanging=false,waterlogged=false]")
                s.set(px, y0 + 4, pz, "minecraft:spruce_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]")
        elif tid == "route_02_trainer_03":                                           # survey tripod and rain gauge
            s.on_ground(back_x, back_z, "minecraft:spruce_fence")
            s.on_ground(back_x, back_z, "minecraft:lightning_rod[facing=up,powered=false,waterlogged=false]", dy=2)
            s.on_ground(back_x + 1, back_z + 1, "minecraft:cauldron")
        elif tid == "route_03_trainer_01":                                           # the first-ascent cairn
            s.on_ground(back_x, back_z, "minecraft:cobblestone_wall[east=none,north=none,south=none,up=true,waterlogged=false,west=none]")
            s.on_ground(back_x, back_z, "minecraft:stone_button[face=floor,facing=north,powered=false]", dy=2)
        elif tid == "route_03_trainer_02":                                           # the ranger's lean-to
            # two posts either side of the point behind the ranger, across the way the ranger faces
            px, pz = round(math.cos(math.radians(yaw))), round(math.sin(math.radians(yaw)))
            y0 = s.gy(back_x, back_z)
            for k in (-1, 1):
                qx, qz = back_x + k * px, back_z + k * pz
                s.fill((qx, s.gy(qx, qz) + 1, qz), (qx, y0 + 2, qz), "minecraft:spruce_fence")
                s.set(qx, y0 + 3, qz, "minecraft:spruce_slab[type=bottom,waterlogged=false]")
            s.set(back_x, y0 + 3, back_z, "minecraft:spruce_slab[type=bottom,waterlogged=false]")
        elif tid == "route_03_trainer_03":                                           # burrow and root-cut display
            s.ground_block(back_x, back_z, "minecraft:coarse_dirt")
            s.on_ground(back_x + 1, back_z, "minecraft:rooted_dirt")
        # route_01_trainer_01 stands by the junction's sign; 03_04 and 03_05 use the Nosepass shelter and the
        # Swablu bench; the shore angler stands on the north bank platform
    return s


# ====================================================================== trainers
TRAINERS = {
    # id: (skin, eye contact, seat override (x, z) or None, why)
    "route_01_trainer_01": ("camper_liam_008e", True, None, "the eye-contact lesson"),
    "route_01_trainer_02": ("bug_catcher_brandon_02ee", False, (1382, 4714), "in the apiary glade west of the walked line, by the hives"),
    "route_01_trainer_03": ("aroma_lady_violet_022e", False, None, ""),
    "route_01_trainer_04": ("hiker_brice_00ba", False, None, ""),
    "route_02_trainer_01": ("camper_jeff_0092", False, None, ""),
    "route_02_trainer_02": ("bug_catcher_sammy_0068", False, None, ""),
    "route_02_shore_trainer_01": ("fisherman_andrew_00e9", False, (1604, 3063), "on the north bank platform"),
    "route_02_trainer_03": ("scientist_ted_014f", False, None, ""),
    "route_03_trainer_01": ("hiker_nob_00b7", False, None, ""),
    "route_03_trainer_02": ("pokemon_ranger_jeffrey_0336", False, None, ""),
    "route_03_trainer_03": ("worker_braden_0460", False, None, ""),
    "route_03_trainer_04": ("engineer_bernie_00de", False, None, "on the route by the Nosepass shelter, as the handoff says"),
    "route_03_trainer_05": ("pokemon_ranger_taylor_0335", False, (1980, 1602), "at the Swablu guide bench"),
}


def trainer_seats(g, road):
    t = json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))
    out = []
    for r in t["trainers"]:
        if r["id"] not in TRAINERS:
            continue
        skin, eye, over, why = TRAINERS[r["id"]]
        p = r["placement"]
        rid = int(r["id"][6:8])
        sx, sz, yaw, walked, d = seat(road, g, rid, r["id"], p["x"], p["z"])
        if over:
            sx, sz = over
            i, _, walked = road.nearest(ROUTES[rid], sx, sz)
            px, pz = road.paths[ROUTES[rid]][i]
            yaw = yaw_to(px - sx, pz - sz) if (px, pz) != (sx, sz) else 0
        y = g(sx, sz) + 1
        if r["id"] == "route_02_shore_trainer_01":
            y = VIltri_Y + 3
        out.append({"id": r["id"], "name": r["display_name"], "listed": [p["x"], p["z"]], "seat": [sx, y, sz], "yaw": yaw,
                    "listed_off_walked_line": round(d, 1), "walked_distance": round(walked, 1),
                    "moved_blocks": round(math.hypot(sx - p["x"], sz - p["z"]), 1),
                    "skin": "rctmod:textures/trainers/single/%s.png" % skin, "eye_contact": eye,
                    "why": why or ("on the flatter shoulder, off the walked line" if (sx, sz) != (p["x"], p["z"]) else "the listed point, already off the walked line")})
    return out


# the finds that reward leaving the path (data/rewards.json, ADR-002 caches): the three secret glades Route 1's hidden
# squeeze paths end in (tools/maze_forest.py CLEARINGS), and the world tree's west foot, 95 blocks off Route 3 under its
# crown. Each is an empty barrel (scenery) and a trigger box round it; the reward is the advancement's
CACHE_SITES = {"r1_fern_glade": (1602, 4941), "r1_west_hollow": (1258, 4801), "r1_north_ring": (1662, 4381),
               "r3_world_tree_roots": (1991, 2279)}


def caches(g, road):
    s = Site("route_caches", g, road, None, "finds off the path: Route 1's three secret glades, the world tree's roots")
    s.caches = {}
    for cid, (x, z) in CACHE_SITES.items():
        y = s.on_ground(x, z, "minecraft:barrel[facing=up,open=false]")
        s.on_ground(x + 1, z, "minecraft:moss_carpet")
        s.caches[cid] = {"trigger": {"min": [x - 2, y - 1, z - 2], "max": [x + 2, y + 2, z + 2]},
                         "container": {"block": "minecraft:barrel", "at": [x, y, z]}}
    return s


SITES = [mansion_junction, picnic, stranger_hut, first_cast, geodude, sounding, north_bank, nosepass, creek_wooper, mast, swablu]


def build(g, road):
    seats = trainer_seats(g, road)
    sites = [f(g, road) for f in SITES] + [trainer_props(g, road, seats), caches(g, road)]
    return sites, seats


def scene_patch(sites):
    """{scene id: {area, markers, props, npcs}} from the builds."""
    out = {}
    for s in sites:
        if not s.scene:
            continue
        e = out.setdefault(s.scene, {"markers": {}, "props": {}, "npcs": []})
        e["markers"].update(s.markers)
        e["props"].update(s.props)
        e["npcs"] += s.npcs
        if s.area:
            e["area"] = s.area
    return out


def apply_scene_patch(doc, patch, write=True):
    """Put the built positions into the scene records; returns the differences (empty = agree)."""
    diffs = []
    byid = {s["id"]: s for s in doc["scenes"]}
    for sid, p in patch.items():
        s = byid.get(sid)
        if s is None:
            diffs.append("scene %s is built but has no record in data/scenes.json" % sid)
            continue
        if s.get("area") != p.get("area"):
            diffs.append("%s area" % sid)
            if write:
                s["area"] = p["area"]
        for name, m in p["markers"].items():
            if (s.get("markers") or {}).get(name) != m:
                diffs.append("%s marker %s" % (sid, name))
                if write:
                    s.setdefault("markers", {})[name] = m
        props = {q["id"]: q for q in s.get("props") or []}
        for pid, q in p["props"].items():
            have = props.get(pid)
            want = {k: q[k] for k in ("at", "size", "on")}
            if have is None:
                diffs.append("%s prop %s has no record" % (sid, pid))
                continue
            if {k: have.get(k) for k in want} != want:
                diffs.append("%s prop %s" % (sid, pid))
                if write:
                    have.update(want)
        npcs = {n["conversation"]: n for n in s.get("npcs") or []}
        for n in p["npcs"]:
            have = npcs.get(n["conversation"])
            if have is None or have.get("at") != n["at"] or have.get("yaw") != n["yaw"]:
                diffs.append("%s npc %s" % (sid, n["conversation"]))
                if write:
                    if have is None:
                        s.setdefault("npcs", []).append(n)
                    else:
                        have.update(n)
    return diffs


def write_pack(sites, out=OUT):
    if out.exists():
        shutil.rmtree(out)
    fn = out / "data" / "cobblers" / "function" / "route_events"
    fn.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers Routes 1-3 event sites (tools/route_events.py)"}}) + "\n", encoding="utf-8")
    from place_town import forceload_commands
    def bbox(cmds):
        xs, zs = [], []
        for c in cmds:
            q = c.split()
            if q[0] in ("setblock", "fill"):
                xs += [int(q[1])] + ([int(q[4])] if q[0] == "fill" else [])
                zs += [int(q[3])] + ([int(q[6])] if q[0] == "fill" else [])
        return (min(xs), min(zs), max(xs), max(zs))

    # every site's vegetation clearing runs before ANY site builds: a clear is `replace #minecraft:logs`, so one run
    # after another site's build takes that build's posts and piles (the north bank's trail took the sounding
    # platform's clawed post on staging, 2026-09-24)
    # Every chunk is held for the whole run (function_limits.ensure_loaded): two sites' clears overlap, and a segment
    # releasing its chunks before the next re-added them would write into chunks on their way out
    import function_limits
    clear = [c for s in sites for c in (["# %s" % s.id] + s.clear_cmds if s.clear_cmds else [])]
    clear = (["# every site's vegetation, cleared before any site builds (tools/route_events.py)"]
             + function_limits.ensure_loaded(clear))
    (fn / "00_clear.mcfunction").write_text("\n".join(clear) + "\n", encoding="utf-8", newline="\n")
    for s in sites:
        box = bbox(s.cmds)
        body = [s.cmds[0]] + forceload_commands(box, "add") + s.cmds[1:] + forceload_commands(box, "remove")
        (fn / ("%s.mcfunction" % s.id)).write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    (fn / "index.txt").write_text("\n".join(["00_clear"] + [s.id for s in sites]) + "\n", encoding="utf-8", newline="\n")


def verify_world(world, sites):
    """Every block the sites write stands in a stopped staging world; no log or leaves in a cleared volume."""
    import build_audit
    w = build_audit.World(Path(world))
    bad, n = [], 0
    planned = {p for s in sites for p in s.blocks}          # a log another site builds on purpose is not a tree left
    for s in sites:
        for (x, y, z), b in s.blocks.items():
            got = w.block(x, y, z)
            n += 1
            if got is None:
                bad.append("%s: %s not loaded" % (s.id, (x, y, z)))
            elif build_audit.base(got) != build_audit.base(b):
                bad.append("%s: %s is %s, planned %s" % (s.id, (x, y, z), got, b))
        for (x0, y0, z0, x1, y1, z1) in s.cleared:
            for x in range(x0, x1 + 1, 2):
                for z in range(z0, z1 + 1, 2):
                    for y in range(y0, y1 + 1):
                        got = w.block(x, y, z) or ""
                        if got.endswith(("_log", "_leaves")) and (x, y, z) not in planned:
                            bad.append("%s: %s at %s left in a clearing" % (s.id, got, (x, y, z)))
                            break
    return n, bad


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=None)
    p.add_argument("--write-scenes", action="store_true")
    p.add_argument("--verify-world", default=None)
    a = p.parse_args(argv)
    print("walked lines:", check_paths_heightmap(a.source_root))
    g = G.Ground(a.source_root)
    road = Road()
    sites, seats = build(g, road)
    probs = [x for s in sites for x in s.road_problems()]
    # nothing built on a planned trunk of the Route 1 maze forest (its trees are its data: the forest audit counts them)
    trunks = maze_trunks()
    if trunks is None:
        probs.append("the Route 1 forest pack is not built (tools/maze_forest.py): trunks cannot be checked")
    else:
        for s in sites:
            for (x, y, z), b in s.blocks.items():
                if b != "minecraft:air" and (x, z) not in s.surface and (x, z) in trunks:
                    probs.append("%s: %s at %s stands on a planned maze-forest trunk" % (s.id, b, (x, y, z)))
    # nothing built where a trainer or an NPC stands (feet and head)
    built = {}
    for s in sites:
        for p, b in s.blocks.items():
            if b != "minecraft:air":
                built[p] = (s.id, b)
    stands = [(t["id"], tuple(t["seat"])) for t in seats] + [(n["conversation"], tuple(n["at"])) for s in sites for n in s.npcs]
    for who, (x, y, z) in stands:
        for yy in (y, y + 1):
            if (x, yy, z) in built:
                probs.append("%s stands at %s inside %s's %s" % (who, (x, y, z), *built[(x, yy, z)]))
    for s in sites:
        for n in s.notes:
            print("  %s: %s" % (s.id, n))
    doc = json.loads(SCENES.read_text(encoding="utf-8"))
    diffs = apply_scene_patch(doc, scene_patch(sites), write=a.write_scenes)
    rw_path = ROOT / "data" / "rewards.json"
    rw = json.loads(rw_path.read_text(encoding="utf-8"))
    recs = {r["id"]: r for r in rw["rewards"]}
    for cid, pos in next(x for x in sites if x.id == "route_caches").caches.items():
        r = recs.get(cid)
        if r is None:
            diffs.append("data/rewards.json has no record %s for its cache" % cid)
        elif {k: r.get(k) for k in pos} != pos:
            diffs.append("data/rewards.json %s position" % cid)
            r.update(pos)
    seat_doc ={"schema": "cobblers.route-trainers/1", "generated_by": "tools/route_events.py --write-scenes",
                "note": "Where each Route 1-3 trainer stands (docs/story/EARLY_ROUTE_BUILD_HANDOFF.md): the listed point, or "
                        "the nearest shoulder off the walked line (build/routes/paths.json) when the point is on it. "
                        "tools/route_trainers.py generates the RCT data and reapply places each with summon_persistent.",
                "trainers": seats}
    if a.write_scenes:
        SCENES.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        SEATS.write_text(json.dumps(seat_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        rw_path.write_text(json.dumps(rw, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
        print("wrote scene positions (%d changes) and %d trainer seats" % (len(diffs), len(seats)))
    else:
        old = json.loads(SEATS.read_text(encoding="utf-8")) if SEATS.exists() else {}
        if old.get("trainers") != seats:
            diffs.append("data/route_trainers.json differs from the seats computed now")
        if diffs:
            print("DRIFT: data/scenes.json or data/route_trainers.json disagree with the build (run --write-scenes):")
            for d in diffs:
                print("   ", d)
    for t in seats:
        print("  %-26s seat %-18s moved %4.1f  walked %6.1f  %s" % (t["id"], t["seat"], t["moved_blocks"], t["walked_distance"], t["why"]))
    write_pack(sites)
    print("wrote %d site functions (%d commands) to %s" % (len(sites), sum(len(s.cmds) for s in sites), OUT))
    if probs:
        print("ROAD CLEARANCE: %d problems" % len(probs))
        for x in probs[:40]:
            print("   ", x)
    if a.verify_world:
        n, bad = verify_world(a.verify_world, sites)
        print("verify: %d planned blocks, %d problems" % (n, len(bad)))
        for b in bad[:60]:
            print("   ", b)
        return 1 if bad else 0
    return 1 if (probs or (diffs and not a.write_scenes)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
