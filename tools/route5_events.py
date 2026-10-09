#!/usr/bin/env python
"""Route 5 (Erika to Koga): the Bellwether, four event sites and one find, built from the heightmap and the walked
route, never from a world (docs/world-building/ROUTE5_EVENTS.md).

Routes 1-3 got their event sites from tools/route_events.py (R12). Route 5 had none. This is that tool's mechanism for
the fifth leg, in its own file and its own pack so that nothing Routes 1-3 build can move: it imports route_events'
Site (the block-command recorder), sign(), wall_sign(), yaw_to() and scene_patch()/apply_scene_patch() and changes none
of them. Its walked line is route_05_erika_to_koga in data/route_paths.json.

  the chain   one quest, evt_route5_bellwether (data/quests.json), four scenes (data/scenes.json), eleven conversations
              (data/dialogue.json), thirteen fields (data/progression.json). A shepherd's bellwether, a Flaaffy
              called Tolly, has gone south alone; the walker meets the empty fold (walked ~145), the three bell
              cairns off the road (~375), the weather keeper's hut (~560) and the winter fold at the glacier's foot
              (~900, the payoff). Each event stands alone and any order works; what a player did earlier only changes
              what a later person says and one reward.
  the find    a tin in the lee of the cairns (data/rewards.json r5_shepherds_tin), an ADR-002 cache like Route 1's.
  ground      tools/ground.py, rounded. A column's wall or floor stands on the rounded ground; feet are one above.
  the road    nothing built within ROAD_CLEAR of a walked cell except surface work (a trail's own blocks).
  clearing    vegetation only, by block tag, with the same protection route_events applies (towns, the elders in
              data/elder_trees.json).

  python tools/route5_events.py [--source-root R]            write the pack; fail on drift against data/
  python tools/route5_events.py --write-scenes               also write the positions into the four scene records and
                                                             the cache's record (those records only, as text)
  python tools/route5_events.py probes [--write]             presence probes (data/world_probes.json route5_events)
  python tools/route5_events.py --verify-world <stopped world>   read a staging world and check every block stands

WHAT THIS DOES NOT COVER (CLAUDE.md, "our list is not the world"): the wild Pokemon that spawn here are Route 5's own
table; a donor template's or a mod's structure near the line is not in data/placements.json and is not checked.
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
import route_events as RE  # noqa: E402

ROUTE = "route_05_erika_to_koga"
PACK = ROOT / "build" / "datapacks" / "cobblers_route5_events"
FOLDER = "route5_events"
SCENES, REWARDS, WORLD_PROBES = RE.SCENES, ROOT / "data" / "rewards.json", ROOT / "data" / "world_probes.json"
ROAD_CLEAR = RE.ROAD_CLEAR
REGION5 = (4250, 1480, 4700, 2480)          # x0, z0, x1, z1: every Route 5 path cell and every site, with margin
SCENE_IDS = ["route5_empty_fold", "route5_cairn_bells", "route5_lee_hut", "route5_winter_fold"]
CACHE_ID = "r5_shepherds_tin"
PROBE_KEY = "route5_events"
# the ground rule: the verify reads a world only to check (tests/test_ground_rule.py)
WORLD_READS = {"main"}


def check_paths_heightmap(source_root=None):
    """route_events.check_paths_heightmap, over Route 5's region instead of Routes 1-3's (it reads a module global, so
    the region is swapped for the call and put back)."""
    old = RE.REGION
    RE.REGION = REGION5
    try:
        return RE.check_paths_heightmap(source_root)
    finally:
        RE.REGION = old


class Road5:
    """Route 5's walked line: the dense A* path (data/route_paths.json), with the walked distance at each cell."""

    def __init__(self):
        doc = json.loads(RE.PATHS.read_text(encoding="utf-8"))
        self.path = [tuple(p) for p in doc["paths"][ROUTE]]
        xs, zs = [p[0] for p in self.path], [p[1] for p in self.path]
        x0, z0, x1, z1 = REGION5
        if min(xs) < x0 or max(xs) > x1 or min(zs) < z0 or max(zs) > z1:
            raise SystemExit("%s leaves REGION5 %s: widen it" % (ROUTE, REGION5))
        self.cells = set(self.path)
        d, acc = [0.0], 0.0
        for a, b in zip(self.path, self.path[1:]):
            acc += math.hypot(b[0] - a[0], b[1] - a[1])
            d.append(acc)
        self.walked = d

    def nearest(self, x, z):
        best = min(range(len(self.path)), key=lambda i: (self.path[i][0] - x) ** 2 + (self.path[i][1] - z) ** 2)
        px, pz = self.path[best]
        return best, math.hypot(px - x, pz - z), self.walked[best]

    def near_any(self, x, z, r):
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if (x + dx, z + dz) in self.cells:
                    return True
        return False


_PROTECTED = None


def protected(ax, az, bx, bz):
    """Why a clearing tile must not be cut, or None: a town's ground (route_events' rule) and a built elder
    (data/elder_trees.json, the 26-block circle route_events uses). Route 1's maze forest and the grove giants are
    nowhere near Route 5."""
    global _PROTECTED
    if _PROTECTED is None:
        import reapply
        import town_audit
        pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
        rects = [("town %s" % sid, town_audit.town_bounds(sid, pl)) for sid in ["hometown"] + reapply.places(pl)]
        elders = json.loads((ROOT / "data" / "elder_trees.json").read_text(encoding="utf-8"))["elders"]
        circles = [("a built tree at (%d, %d)" % (e["x"], e["z"]), e["x"], e["z"], 26) for e in elders]
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


class Site5(RE.Site):
    """route_events.Site with Route 5's own clearing protection (RE.Site.clear reads route_events' module-level
    protected(), which needs derived/sites; this reads data/ only)."""

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


# ====================================================================== helpers
def drystone(x, z):
    """A dry wall's course: mostly cobblestone, some moss and some grey, by column so a rebuild is identical."""
    k = (x * 7 + z * 13) % 6
    return "minecraft:mossy_cobblestone" if k == 0 else "minecraft:andesite" if k == 1 else "minecraft:cobblestone"


def ring(x0, z0, x1, z1):
    out = []
    for x in range(x0, x1 + 1):
        out += [(x, z0), (x, z1)]
    for z in range(z0 + 1, z1):
        out += [(x0, z), (x1, z)]
    return out


def wall(s, cells, h=2):
    """A dry wall h high over each column's own ground (every course starts on the rounded ground)."""
    for x, z in cells:
        b = s.gy(x, z)
        for dy in range(1, h + 1):
            s.set(x, b + dy, z, drystone(x, z + dy))


def fence_post(s, x, z, h, block="minecraft:spruce_fence"):
    b = s.gy(x, z)
    s.fill((x, b + 1, z), (x, b + h, z), block)
    return b + h


# ====================================================================== the sites
def empty_fold(g, road):
    """E1, walked ~145: a drystone fold east of the road, its gate open, the flock standing at the gap, the bellwether's
    hook on the gate post, empty. Nan Tarrow keeps the gap."""
    s = Site5("route5_empty_fold", g, road, "route5_empty_fold",
              "EVT-ROUTE5-EMPTY-FOLD: the drystone fold, the open gate, the empty hook, the shepherd at the gap")
    X0, Z0, X1, Z1 = 4402, 1656, 4416, 1667
    s.clear(4394, 1648, 4424, 1676, up=14)
    gap = {(X0, 1661), (X0, 1662)}
    wall(s, [c for c in ring(X0, Z0, X1, Z1) if c not in gap], 2)
    for z in (1661, 1662):                                                            # the gate, swung open
        s.on_ground(X0, z, "minecraft:spruce_fence_gate[facing=east,in_wall=false,open=true,powered=false]")
    px, pz = X0 - 2, 1659                                                            # the hook post, outside the gate
    pb = s.gy(px, pz)
    s.fill((px, pb + 1, pz), (px, pb + 3, pz), "minecraft:stripped_spruce_log[axis=y]")
    s.set(px - 1, pb + 2, pz, "minecraft:tripwire_hook[attached=false,facing=west,powered=false]")   # the empty hook
    s.prop("empty_hook", (px - 1, pb + 2, pz), (0.8, 1.0))
    for x in (4413, 4414):                                                             # hay racked in the corner
        s.on_ground(x, 1658, "minecraft:hay_block[axis=x]")
    s.on_ground(4413, 1658, "minecraft:hay_block[axis=x]", dy=2)
    s.on_ground(4410, 1665, "minecraft:cauldron")
    s.on_ground(4412, 1665, "minecraft:barrel[facing=up,open=false]")
    roof = max(s.gy(x, z) for x in (4414, 4415) for z in (1660, 1664)) + 4            # the lean-to along the east wall
    for z in (1660, 1664):
        s.fill((4414, s.gy(4414, z) + 1, z), (4414, roof - 1, z), "minecraft:spruce_fence")
    s.fill((4413, roof, 1659), (4415, roof, 1665), "minecraft:spruce_slab[type=bottom,waterlogged=false]")
    s.set(4414, roof - 1, 1662, "minecraft:lantern[hanging=true,waterlogged=false]")
    s.on_ground(4415, 1662, "minecraft:spruce_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]")
    s.trail([(4386, 1661), (4392, 1661), (4400, 1661)], "minecraft:dirt_path", width=1)
    s.npc("dlg_r5_nan", 4399, 1664, yaw=90)
    s.marker("ewe_gate", 4406, 1662, yaw=90, slots=[[0, 0], [0.9, 0], [0, 0.9], [0.9, 0.9]])
    s.set_area(4392, 1650, 4420, 1672)
    return s


# the three bells: (id, cairn x, z, which note); the flat one is the north cairn
BELLS = [("bell_west", 4424, 1884), ("bell_north", 4432, 1876), ("bell_south", 4434, 1889)]


def cairn_bells(g, road):
    """E2, walked ~375: three herders' cairns on the rise east of the road, each with a bell hung from an arm; one
    note is flat. The tin sits in the lee between them."""
    s = Site5("route5_cairn_bells", g, road, "route5_cairn_bells",
              "EVT-ROUTE5-CAIRN-BELLS: three bell cairns, one flat note, the strap on the north arm")
    s.clear(4408, 1864, 4448, 1898, up=14)
    s.trail([(4386, 1884), (4400, 1884), (4414, 1884), (4420, 1884)], "minecraft:dirt_path", width=1)
    s.on_ground(4387, 1880, "minecraft:spruce_fence")                                    # the signpost on the shoulder
    s.on_ground(4387, 1880, RE.sign("spruce", 4, ["Drovers' cairns", "east, forty paces", "", "ring them softly"]), dy=2)
    for pid, cx, cz in BELLS:
        for x in (cx - 1, cx):
            for z in (cz, cz + 1):
                s.on_ground(x, z, "minecraft:cobblestone")
        b = s.gy(cx, cz)
        s.set(cx, b + 2, cz, "minecraft:mossy_cobblestone")
        s.set(cx, b + 3, cz, "minecraft:andesite")
        s.set(cx, b + 4, cz, "minecraft:cobblestone_slab[type=bottom,waterlogged=false]")
        s.set(cx + 1, b + 3, cz, "minecraft:spruce_fence[east=false,north=false,south=false,waterlogged=false,west=true]")  # the arm
        s.set(cx + 1, b + 2, cz, "minecraft:chain[axis=y,waterlogged=false]")
        s.set(cx + 1, b + 1, cz, "minecraft:lantern[hanging=true,waterlogged=false]")                    # the bell
        s.prop(pid, (cx + 1, b + 1, cz), (0.8, 1.7))
    # the strap: a blue banner hung on the north cairn's andesite head (wool is a spawn condition; a banner is not)
    nx, nz = BELLS[1][1], BELLS[1][2]
    s.set(nx, s.gy(nx, nz) + 3, nz - 1, "minecraft:blue_wall_banner[facing=north]")
    s.on_ground(4430, 1883, "minecraft:barrel[facing=up,open=false]")                    # the shepherds' tin
    s.on_ground(4431, 1883, "minecraft:moss_carpet")
    s.caches = {CACHE_ID: {"trigger": {"min": [4428, s.gy(4430, 1883) - 1, 1881], "max": [4432, s.gy(4430, 1883) + 2, 1885]},
                           "container": {"block": "minecraft:barrel", "at": [4430, s.gy(4430, 1883) + 1, 1883]}}}
    s.set_area(4412, 1866, 4446, 1896)
    return s


def lee_hut(g, road):
    """E3, walked ~560: a stone hut with a slab roof in the lee of the rise, a weather board on its west wall, a
    commons box under the bench. Old Gorse watches the Tear from it."""
    s = Site5("route5_lee_hut", g, road, "route5_lee_hut", "EVT-ROUTE5-LEE-HUT: the weather keeper's hut, the board, the commons box")
    x0, z0, x1, z1 = 4397, 2071, 4405, 2077
    f = g(x0 - 1, 2074)                                                                   # the sill is level with the ground outside the door; the slope behind is dug out
    s.clear(4390, 2064, 4412, 2084, up=14)
    s.fill((x0, f - 3, z0), (x1, f, z1), "minecraft:cobblestone")                       # the plinth the floor stands on
    s.fill((x0, f + 1, z0), (x1, f + 5, z1), "minecraft:air")
    s.fill((x0, f, z0), (x1, f, z1), "minecraft:spruce_planks")
    for y in range(f + 1, f + 4):
        for a, b in (((x0, y, z0), (x1, y, z0)), ((x0, y, z1), (x1, y, z1)), ((x0, y, z0), (x0, y, z1)), ((x1, y, z0), (x1, y, z1))):
            s.fill(a, b, "minecraft:stone_bricks" if y == f + 1 else "minecraft:cobblestone")
    s.fill((x0 - 1, f + 4, z0 - 1), (x1 + 1, f + 4, z1 + 1), "minecraft:spruce_slab[type=bottom,waterlogged=false]")
    s.fill((x0, f + 1, 2074), (x0, f + 2, 2074), "minecraft:air")                       # the doorway, west wall
    s.set(x1, f + 2, 2074, "minecraft:glass_pane")
    s.set(x0 + 4, f + 2, z0, "minecraft:glass_pane")
    s.set(x0 + 4, f + 2, z1, "minecraft:glass_pane")
    s.set(4403, f + 1, 2076, "handcrafted:spruce_table[color=none,shape=single,waterlogged=false]")
    s.set(4403, f + 2, 2076, "handcrafted:wood_cup[facing=west,pieces=1,waterlogged=false]")
    s.set(4402, f + 1, 2076, "handcrafted:spruce_chair[color=none,facing=east,waterlogged=false]")
    s.set(4404, f + 1, 2072, "minecraft:cauldron")
    s.set(4404, f + 1, 2073, "minecraft:barrel[facing=up,open=false]")                  # the commons box (the dialogue's)
    s.set(4401, f + 3, 2074, "minecraft:lantern[hanging=true,waterlogged=false]")
    s.set(x0 + 1, f + 1, 2072, "minecraft:spruce_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]")
    s.set(x0 + 1, f + 1, 2076, "minecraft:spruce_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]")
    s.set(x0 - 1, f + 2, 2072, RE.wall_sign("spruce", "west", ["WIND  SSW, rising", "Pond: skinning", "Ewes: gone quiet", "Tonight."]))
    s.prop("weather_board", (x0 - 1, f + 2, 2072), (0.9, 0.9))
    s.trail([(4370, 2074), (4382, 2074), (4392, 2074), (x0 - 1, 2074)], "minecraft:dirt_path", width=1)
    s.npc("dlg_r5_gorse", 4401, 2074, yaw=90, y=f + 1)
    s.set_area(4390, 2064, 4412, 2084)
    s.floor = f
    return s


def winter_fold(g, road):
    """E4, walked ~900: the winter fold in the fields at the glacier's foot. A windbreak wall to the south-west, a turf-
    roofed byre, a pen with a flat stone, and Jory Tarrow at the door. Tolly stands on the stone."""
    s = Site5("route5_winter_fold", g, road, "route5_winter_fold",
              "EVT-ROUTE5-WINTER-FOLD: the windbreak, the turf-roofed byre, the pen and the stone, the tally post")
    s.clear(4553, 2278, 4593, 2304, up=14)
    # the windbreak: west side x4560 z2284-2298, south side z2298 x4560-4590 with a 3-wide gap at x4570-4572
    cells = [(4560, z) for z in range(2284, 2299)] + [(x, 2298) for x in range(4561, 4591) if not 4570 <= x <= 4572]
    wall(s, cells, 2)
    x0, z0, x1, z1 = 4566, 2288, 4576, 2292
    f = g(4571, z1 + 1)                                                                   # level with the ground at the door
    s.fill((x0, f - 3, z0), (x1, f, z1), "minecraft:cobblestone")
    s.fill((x0, f + 1, z0), (x1, f + 6, z1), "minecraft:air")
    s.fill((x0, f, z0), (x1, f, z1), "minecraft:spruce_planks")
    for y in range(f + 1, f + 4):
        for a, b in (((x0, y, z0), (x1, y, z0)), ((x0, y, z1), (x1, y, z1)), ((x0, y, z0), (x0, y, z1)), ((x1, y, z0), (x1, y, z1))):
            s.fill(a, b, "minecraft:cobblestone")
    s.fill((x0 - 1, f + 4, z0 - 1), (x1 + 1, f + 4, z1 + 1), "minecraft:mossy_cobblestone_slab[type=bottom,waterlogged=false]")
    s.fill((x0 - 1, f + 5, z0 - 1), (x1 + 1, f + 5, z1 + 1), "minecraft:moss_block")             # the turf
    s.fill((4571, f + 1, z1), (4571, f + 2, z1), "minecraft:air")                                 # the byre door, south wall
    for x in (4568, 4574):
        s.set(x, f + 1, z0 + 1, "minecraft:hay_block[axis=x]")
    s.set(4572, f + 1, z0 + 1, "minecraft:barrel[facing=up,open=false]")
    s.set(4571, f + 3, 2290, "minecraft:lantern[hanging=true,waterlogged=false]")
    # the pen: a fence ring east of the byre with a gate in its south side, the flat stone along its middle
    px0, pz0, px1, pz1 = 4579, 2287, 4585, 2293
    for x, z in ring(px0, pz0, px1, pz1):
        if (x, z) != (4582, pz1):
            s.on_ground(x, z, "minecraft:spruce_fence")
    s.on_ground(4582, pz1, "minecraft:spruce_fence_gate[facing=south,in_wall=false,open=false,powered=false]")
    for x in range(4580, 4585):
        s.on_ground(x, 2290, "minecraft:smooth_stone")
    s.marker("tolly_stone", 4582, 2290, yaw=90, dy=2, slots=[[0, 0], [0.9, 0], [-0.9, 0]])
    # the tally post by the gap
    tb = fence_post(s, 4574, 2296, 2)
    s.set(4574, tb + 1, 2296, RE.sign("spruce", 8, ["WINTER FOLD", "J. Tarrow", "19 ewes in", "1 bell out"]))
    s.prop("tally_post", (4574, tb + 1, 2296), (0.9, 1.4))
    s.trail([(4538, 2313), (4550, 2308), (4560, 2304), (4571, 2301), (4571, 2297)], "minecraft:dirt_path", width=1)
    s.npc("dlg_r5_jory", 4571, 2295, yaw=0, y=s.gy(4571, 2295) + 1)
    s.set_area(4554, 2280, 4592, 2302)
    s.floor = f
    return s


def caches(g, road, cairn_site):
    s = Site5("route5_caches", g, road, None, "the find off the path: the shepherds' tin in the lee of the cairns")
    s.caches = cairn_site.caches
    return s


SITES = [empty_fold, cairn_bells, lee_hut, winter_fold]


def build(g, road):
    sites = [f(g, road) for f in SITES]
    return sites


def all_cache_records(sites):
    return {cid: pos for s in sites for cid, pos in getattr(s, "caches", {}).items()}


# ====================================================================== the pack
def write_pack(sites, out=PACK):
    if out.exists():
        shutil.rmtree(out)
    fn = out / "data" / "cobblers" / "function" / FOLDER
    fn.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers Route 5 event sites (tools/route5_events.py)"}}) + "\n", encoding="utf-8")
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

    # every site's clearing runs before any site builds, for the reason route_events gives: a clear is `replace
    # #minecraft:logs`, so one run after another site's build would take that build's posts
    clear = [c for s in sites for c in (["# %s" % s.id] + s.clear_cmds if s.clear_cmds else [])]
    clear = ["# every site's vegetation, cleared before any site builds (tools/route5_events.py)"] + function_limits.ensure_loaded(clear)
    (fn / "00_clear.mcfunction").write_text("\n".join(clear) + "\n", encoding="utf-8", newline="\n")
    for s in sites:
        box = bbox(s.cmds)
        body = [s.cmds[0]] + forceload_commands(box, "add") + s.cmds[1:] + forceload_commands(box, "remove")
        (fn / ("%s.mcfunction" % s.id)).write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    (fn / "index.txt").write_text("\n".join(["00_clear"] + [s.id for s in sites]) + "\n", encoding="utf-8", newline="\n")


# ====================================================================== the records (as text, so a diff is only ours)
def record_span(lines, rid, indent):
    """(first line, last line) of the record at `indent` spaces that carries `"id": "<rid>"`, or None."""
    pad = " " * indent
    for i, l in enumerate(lines):
        if l.strip() == '"id": "%s",' % rid and lines[i - 1] == pad + "{" and l.startswith(pad + "  "):
            j = i
            while lines[j] not in (pad + "}", pad + "},"):
                j += 1
            return i - 1, j
    return None


def replace_record(text, rid, rec, indent):
    lines = text.split("\n")
    span = record_span(lines, rid, indent)
    if span is None:
        raise SystemExit("no record %s at indent %d to rewrite" % (rid, indent))
    a, b = span
    comma = "," if lines[b].endswith(",") else ""
    body = json.dumps(rec, indent=2, ensure_ascii=False).split("\n")
    body = [" " * indent + l for l in body]
    body[-1] += comma
    return "\n".join(lines[:a] + body + lines[b + 1:])


def drift(sites, scenes_doc, rewards_doc, write):
    """Differences between the build and data/ (scene positions, the cache's trigger and container). With `write`, the
    documents are updated in place and returned."""
    patch = RE.scene_patch(sites)
    diffs = RE.apply_scene_patch(scenes_doc, patch, write=write)
    missing = [sid for sid in SCENE_IDS if sid not in patch]
    for sid in missing:
        diffs.append("scene %s is not built by any site" % sid)
    recs = {r["id"]: r for r in rewards_doc["rewards"]}
    for cid, pos in all_cache_records(sites).items():
        r = recs.get(cid)
        if r is None:
            diffs.append("data/rewards.json has no record %s for its cache" % cid)
        elif {k: r.get(k) for k in pos} != pos:
            diffs.append("data/rewards.json %s position" % cid)
            if write:
                r.update(pos)
    return diffs


def write_data(sites, scenes_doc, rewards_doc):
    st = SCENES.read_text(encoding="utf-8")
    byid = {s["id"]: s for s in scenes_doc["scenes"]}
    for sid in SCENE_IDS:
        st = replace_record(st, sid, byid[sid], 4)
    SCENES.write_text(st, encoding="utf-8", newline="\n")
    rt = REWARDS.read_text(encoding="utf-8")
    recs = {r["id"]: r for r in rewards_doc["rewards"]}
    for cid in all_cache_records(sites):
        rt = replace_record(rt, cid, recs[cid], 4)
    REWARDS.write_text(rt, encoding="utf-8", newline="\n")


# ====================================================================== probes
def probes(sites):
    """Presence probes in data/world_probes.json's shape: the block under each prop (the thing the dialogue talks about),
    one structural block per site, and each NPC standing where its scene puts it. (The actors and the props are entities
    R17 places; the scenes' own verify covers them.) Block states are not compared, only the block."""
    structural = {"route5_empty_fold": ["minecraft:spruce_fence_gate"], "route5_cairn_bells": ["minecraft:barrel"],
                  "route5_lee_hut": ["minecraft:spruce_planks"], "route5_winter_fold": ["minecraft:moss_block", "minecraft:smooth_stone"]}
    out = []
    for s in sites:
        if s.scene is None:
            continue
        for pid, p in sorted(s.props.items()):
            pos = tuple(p["on"])
            out.append({"what": "%s: the block under prop %s" % (s.id, pid), "block": list(pos) + [s.blocks[pos].split("[")[0]], "expect": True})
        for want in structural[s.id]:
            pos = min(q for q, b in s.blocks.items() if b.split("[")[0] == want)
            out.append({"what": "%s: %s" % (s.id, want.split(":")[1]), "block": list(pos) + [want], "expect": True})
        for n in s.npcs:
            x, y, z = n["at"]
            out.append({"what": "%s: %s" % (s.id, n["conversation"]), "entity": "@e[type=cobblemon:npc,x=%d,y=%d,z=%d,distance=..2]" % (x, y, z),
                        "count": 1, "hold": [x, y, z]})
    return out


def write_probes(sites):
    doc = json.loads(WORLD_PROBES.read_text(encoding="utf-8"))
    new = {}
    for k, v in doc["places"].items():
        new[k] = v
        if k == "zapdos_tower":                                  # a middle anchor: an append at the end is where every unit's edit lands
            new[PROBE_KEY] = probes(sites)
    if PROBE_KEY not in new:
        new[PROBE_KEY] = probes(sites)
    doc["places"] = new
    WORLD_PROBES.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


# ====================================================================== checks and main
def problems(g, road, sites):
    probs = [x for s in sites for x in s.road_problems()]
    built = {}
    for s in sites:
        for p, b in s.blocks.items():
            if b != "minecraft:air":
                built[p] = (s.id, b)
    for s in sites:
        for n in s.npcs:
            x, y, z = n["at"]
            for yy in (y, y + 1):
                if (x, yy, z) in built:
                    probs.append("%s stands at %s inside %s's %s" % (n["conversation"], (x, y, z), *built[(x, yy, z)]))
    return probs


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", nargs="?", choices=["build", "probes"], default="build")
    p.add_argument("--source-root", default=None)
    p.add_argument("--write-scenes", action="store_true")
    p.add_argument("--write", action="store_true", help="probes: write data/world_probes.json")
    p.add_argument("--verify-world", default=None)
    a = p.parse_args(argv)
    print("walked line:", check_paths_heightmap(a.source_root))
    g = G.Ground(a.source_root)
    road = Road5()
    sites = build(g, road)
    if a.command == "probes":
        pr = probes(sites)
        if a.write:
            write_probes(sites)
            print("wrote %d probes into data/world_probes.json (%s)" % (len(pr), PROBE_KEY))
        else:
            print("%d probes (add --write to put them in data/world_probes.json)" % len(pr))
        return 0
    probs = problems(g, road, sites)
    scenes_doc = json.loads(SCENES.read_text(encoding="utf-8"))
    rewards_doc = json.loads(REWARDS.read_text(encoding="utf-8"))
    diffs = drift(sites, scenes_doc, rewards_doc, write=a.write_scenes)
    if a.write_scenes:
        write_data(sites, scenes_doc, rewards_doc)
        print("wrote positions into %d scene records and %d cache records (%d differences)" % (len(SCENE_IDS), len(all_cache_records(sites)), len(diffs)))
    elif diffs:
        print("DRIFT: data/scenes.json or data/rewards.json disagree with the build (run --write-scenes):")
        for d in diffs:
            print("   ", d)
    for s in sites:
        d = road.nearest(*(s.npcs[0]["at"][0::2]))[2] if s.npcs else 0
        print("  %-22s walked ~%4d  %5d commands  %d cleared tiles%s" % (s.id, round(d), len(s.cmds), len(s.cleared),
                                                                       ("  (kept: %s)" % ", ".join(sorted(s.kept))) if s.kept else ""))
    write_pack(sites)
    print("wrote %d site functions (%d commands) to %s" % (len(sites), sum(len(s.cmds) for s in sites), PACK))
    if probs:
        print("ROAD CLEARANCE: %d problems" % len(probs))
        for x in probs[:40]:
            print("   ", x)
    if a.verify_world:
        n, bad = RE.verify_world(a.verify_world, sites)
        print("verify: %d planned blocks, %d problems" % (n, len(bad)))
        for b in bad[:60]:
            print("   ", b)
        return 1 if bad else 0
    return 1 if (probs or (diffs and not a.write_scenes)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
