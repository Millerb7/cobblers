#!/usr/bin/env python
"""The relic site underground: the hall off the Compact HQ's cradle passage, and its zone check.

The owner, 2026-10-01: "THE RELIC SITE UNDERGROUND, reachable only through the Compact HQ, turned back
by the zone check rather than barriers."

docs/world-building/DEEP_CITY.md section 5 had the opposite: the shrine on the Deep's west lip inside a
Compact cordon of tinted glass and iron bars. The shaft-from-the-HQ half of that section is right and is
kept. This tool moves the SHRINE off the surface into a hall on the underground route, and replaces the
cordon with a zone check.

  python tools/relic_underground.py report               # the checks, the measured cover, the owed deps
  python tools/relic_underground.py build [--out DIR]    # the datapack, the undo and the carve, into build/datapacks
  python tools/relic_underground.py verify --world DIR   # read a world to CHECK the result (never to decide)

Re-applied by tools/reapply.py step R9RU, after R9DC and before R9E: hold the chunks, take the old surface build off
(`undo_*`), then the CAVERN pattern (02_shell, 10_void, 20_surfaces, 25_reshell, 30_composition), then the HQ's way
down (40_hq), then release. The pack is world-local: its zone advancement acts on its own and needs no step.

THE HQ'S WAY DOWN (geometry.hq, 2026-10-02). The owner's "reachable only through the Compact HQ" needs a way in that no
other tool builds: a switchback stair from that room's south-west corner down the reserved secure shaft, and a records room
at y0 whose open west doorway is the passage's east end and holds the zone's knock box. It is carved AFTER the reshell
so no shell pass seals it, and the shell never lays a cell of it. tools/deep_city.py owns the HQ above ground and no
longer lays the old hatch; everything under the room's floor is this file's, inside data/deep_city.json's reservations.

THE DOOR (the owner, 2026-10-02: "the HQ door should need the finale's quest stage, not a plate anyone can stand on").
The ring-0 section's iron door stays SHUT: nothing beside it opens it (the first build's two pressure plates are gone,
geometry.hq.front_door.superseded_plates). The gate is a Compact guard (geometry.hq.guard) whose compiled dialogue
(data/dialogue.json dlg_main_relic_hq_guard) offers "Go through." only to a player whose quest.main_worldshift_reveal.stage
is rift_crisis_pending or later, and whose action runs hq_admit as THAT player: a teleport to the inside landing. The
door never opens, so nobody follows. The way out is the inside guard (hq_release, ungated). Both NPCs are placed by
tools/reapply.py step R18RU after R17N (npc_placements()).

THE UNDO. A world applied before 2026-10-02 (staging, R9DC on 2026-10-01 17:10) holds the relic area's old surface
build: the platform, the six arches, the plinth and gold ring, the standing stones, the processional way and the
cordon. tools/deep_city.py no longer writes them, and a data edit changes nothing in a world, so this pack takes them
off. WHICH cells: tools/relic_surface_superseded.py, the old generator kept verbatim, minus every cell the CURRENT
tools/deep_city.py build writes (R9DC rewrites those itself; the sealed entrance, the lookout and the dig stay), and minus every cell the Rift skin
lays definitely (R1 rewrites those itself, earlier in the same run; skin_cells() reads its emitted functions). WHAT
goes back: air over the ground, and under it the ground tools/paint_maps.py painted there for the export (the
preset's terrain code, from the same value noise and seed; GRAVEL as gravel, ROCK and STONE_MIX as stone). A cell
the old build wrote as AIR over the ground is left alone: that world already has air there, and a fresh world may
hold an earlier pack's block in it. Never derived from a world.

GROUND COMES FROM THE HEIGHTMAP. Every y this tool decides comes from tools/ground.py or from arithmetic
on data/relic_underground.json. It never reads a world to decide a position (CLAUDE.md, tests/test_ground_rule.py).

THE RUNG. Datapack plus functions and commands, CLAUDE.md principle 6 rungs 5 and 6. The rungs below do
not reach an area a player may not stand in: Cobblemon native has no player-zone concept, no installed
addon gates an area, Cobbleverse ships none, and no config key expresses a box. A minecraft:location
advancement does, and its reward function acts. tools/gulch_mine.py and tools/rift_zones.py already run
exactly this shape, so the rung is proven here rather than assumed.

WHAT THIS TOOL DOES NOT COVER (CLAUDE.md, "our list is not the world"). It enumerates its own three
rectangles. It knows nothing about what else stands in them: the Deep's pit (tools/rift_deep.py), the HQ
and the surface relic area (tools/deep_city.py), the cradle (Codex's, unbuilt), Habitat Blocks, donor
templates, or anything an earlier pass left. The zone's boxes are a world-shaped predicate -- any player
inside them, however they arrived -- and that is deliberate; the CARVE is a list and is not.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT =Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)
DATA = ROOT / "data" / "relic_underground.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_relic_underground"
NS = "cobblers"
FOLDER = "relic_underground"
SHELL = 24
VOID_TAG = "relic_void"
PART = 3000           # commands per function: one function is one tick (tools/deep_city.py PART)
LOADED_BY = "# chunks-loaded-by: tools/reapply.py R9RU (relic_underground.placement_steps holds the box)"
PAINT_SEED = 20260914  # tools/paint_maps.py --seed default: every documented export ran with it (tests check it)
# the WorldPainter terrain codes the relic area is painted with, as the block at the ground and the two below it.
# GRAVEL is gravel; ROCK is stone; STONE_MIX's andesite/diorite/granite fraction is NOT modelled and is laid as stone.
# A code not named here fails the build closed rather than guessing
PAINT_BLOCK = {"GRAVEL": "minecraft:gravel", "ROCK": "minecraft:stone", "STONE_MIX": "minecraft:stone"}
AIR = "minecraft:air"

VOID = ["minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:water", "minecraft:lava",
        "minecraft:gravel", "minecraft:sand", "minecraft:red_sand", "minecraft:powder_snow",
        "minecraft:pointed_dripstone", "minecraft:glow_lichen", "minecraft:hanging_roots", "minecraft:vine",
        "minecraft:cave_vines", "minecraft:cave_vines_plant", "minecraft:small_dripleaf",
        "minecraft:big_dripleaf", "minecraft:big_dripleaf_stem", "minecraft:moss_carpet",
        "minecraft:sculk_vein", "minecraft:spore_blossom", "minecraft:brown_mushroom",
        "minecraft:red_mushroom", "minecraft:amethyst_cluster", "minecraft:large_amethyst_bud",
        "minecraft:medium_amethyst_bud", "minecraft:small_amethyst_bud"]


class RelicError(Exception):
    pass


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


# --------------------------------------------------------------- geometry, from the data alone

class Geo:
    """Every y and every column, from data/relic_underground.json. Nothing here reads a world."""

    def __init__(self, spec):
        g = spec["geometry"]
        self.spec = spec
        self.z = g["axis_z"]
        p = g["passage"]
        self.px0, self.px1 = p["stops_at_x"], p["from"][0]          # 3358 .. 3421
        self.pz0, self.pz1 = p["interior"]["z"]
        self.ph = p["interior"]["height"]
        h = g["hall"]
        self.hc = tuple(h["centre"])
        self.hr = h["radius"]
        self.hfloor = h["floor_y"]
        self.crim, self.capex = h["ceiling_rim_y"], h["ceiling_apex_y"]
        ga = g["gallery"]
        self.gx0, self.gx1 = ga["x"]
        self.gz0, self.gz1 = ga["z"]
        self.gfloor, self.gh = ga["floor_y"], ga["height"]
        self.junction = tuple(g["junction"]["at"])
        self.choke = g["choked_shaft"]

    # the passage floor is DEEP_CITY.md section 5's own arithmetic, evaluated per column
    def pfloor(self, x):
        return int(round(12.0 * (3427 - x) / 70.0))

    def hall_ceiling(self, x, z):
        r = math.hypot(x - self.hc[0], z - self.hc[1])
        return self.crim + int(round((self.capex - self.crim) * (1.0 - (r / self.hr) ** 2)))

    def in_hall(self, x, z):
        return math.hypot(x - self.hc[0], z - self.hc[1]) <= self.hr + 1e-9

    def in_gallery(self, x, z):
        return self.gx0 <= x <= self.gx1 and self.gz0 <= z <= self.gz1

    def in_passage(self, x, z):
        return self.px0 <= x <= self.px1 and self.pz0 <= z <= self.pz1

    def carved_range(self, x, z):
        """(lo, hi) of everything this build writes at a column, floor block to ceiling block, or None."""
        rs = []
        if self.in_hall(x, z):
            hi = self.hall_ceiling(x, z) + 1
            if abs(x - self.choke["at"][0]) <= self.choke["ring"] // 2 and \
               abs(z - self.choke["at"][1]) <= self.choke["ring"] // 2:
                hi = max(hi, self.choke["to_y"])
            rs.append((self.hfloor, hi))
        if self.in_gallery(x, z):
            rs.append((self.gfloor, self.gfloor + self.gh + 1))
        if self.in_passage(x, z):
            f = self.pfloor(x)
            rs.append((f, f + self.ph + 1))
        if not rs:
            return None
        return min(r[0] for r in rs), max(r[1] for r in rs)

    def footprint(self):
        """Every column the carve touches, with its (lo, hi)."""
        out = {}
        for x in range(self.hc[0] - self.hr, self.hc[0] + self.hr + 1):
            for z in range(self.hc[1] - self.hr, self.hc[1] + self.hr + 1):
                r = self.carved_range(x, z)
                if r:
                    out[(x, z)] = r
        for x in range(self.gx0, self.gx1 + 1):
            for z in range(self.gz0, self.gz1 + 1):
                out[(x, z)] = self.carved_range(x, z)
        for x in range(self.px0, self.px1 + 1):
            for z in range(self.pz0, self.pz1 + 1):
                out[(x, z)] = self.carved_range(x, z)
        return out

    def shell_distance(self, x, z):
        """Chebyshev-free distance from a column to the nearest carved volume, 0 inside."""
        d = math.hypot(x - self.hc[0], z - self.hc[1]) - self.hr
        for (x0, x1, z0, z1) in ((self.gx0, self.gx1, self.gz0, self.gz1),
                                 (self.px0, self.px1, self.pz0, self.pz1)):
            dx = max(x0 - x, 0, x - x1)
            dz = max(z0 - z, 0, z - z1)
            d = min(d, math.hypot(dx, dz))
        return max(0.0, d)

    def nearest_range(self, x, z):
        """The (lo, hi) to shell around a column outside the carve: the nearest volume's own range."""
        best, bd = None, 1e9
        cands = [(self.hc[0], self.hc[1]), (min(max(x, self.gx0), self.gx1), min(max(z, self.gz0), self.gz1)),
                 (min(max(x, self.px0), self.px1), min(max(z, self.pz0), self.pz1))]
        for cx, cz in cands:
            r = self.carved_range(cx, cz)
            if r is None:
                continue
            d = math.hypot(cx - x, cz - z)
            if d < bd:
                best, bd = r, d
        if best is None:
            raise RelicError("no carved volume near %s" % ((x, z),))
        return best


def source_root_of(given):
    import os
    sr = given or env_source_root()
    if not sr:
        raise RelicError("no source root: pass --source-root or set COBBLERS_SOURCE_ROOT")
    return sr


_MEMO = {}


def ground_of(source_root):
    if ("g", source_root) not in _MEMO:
        import ground as G
        _MEMO[("g", source_root)] = G.Ground(source_root)
    return _MEMO[("g", source_root)]


# --------------------------------------------------------------- what else stands here (other tools' output)

def city_cells(source_root):
    """{(x, y, z): block} for everything the CURRENT tools/deep_city.py build writes (R9DC), computed, not read."""
    if ("city", source_root) not in _MEMO:
        import deep_city as DC
        cv, _p, _s, _spec = DC.build(source_root, None)
        _MEMO[("city", source_root)] = {k: v[0] for k, v in cv.v.items()}
    return _MEMO[("city", source_root)]


# the Rift skin's emitted block functions (R1, tools/rift_skin.py). R1 runs before R9RU in every tools/reapply.py run
SKIN = ROOT / "build" / "datapacks" / "cobblers_rift" / "data" / "cobblers" / "function" / "rift"


def skin_cells(box):
    """{(x, y, z)} every cell R1 (tools/rift_skin.py) writes DEFINITELY (a plain fill or setblock, not `replace
    <filter>` or `keep`) inside box (x0, z0, x1, z1), read from the skin's own emitted functions, as
    tools/lakebed_repair.py reads them. The skin cannot be rebuilt here (it needs derived/rift_sculpt), so its output is
    the record of what R1 lays. Not built: fail closed, since an empty set would silently let the undo pave the skin."""
    key = ("skin", tuple(box))
    if key in _MEMO:
        return _MEMO[key]
    if not SKIN.is_dir():
        raise RelicError("no %s: run `python tools/rift_skin.py build` first; the undo must leave the cells R1 lays"
                         % SKIN)
    x0, z0, x1, z1 = box
    out = set()
    for f in sorted(SKIN.glob("blocks_*.mcfunction")):
        for line in f.read_text(encoding="utf-8").splitlines():
            t = line.split()
            if not t or t[0] not in ("fill", "setblock"):
                continue
            n = 6 if t[0] == "fill" else 3
            mode = t[n + 2:]
            if mode and mode not in (["replace"], ["destroy"]):
                if mode[0] in ("keep",) or (mode[0] == "replace" and len(mode) == 2):
                    continue
                raise RelicError("%s: a skin write this undo does not model: %s" % (f.name, line))
            v = [int(s) for s in t[1:n + 1]]
            if t[0] == "setblock":
                v = v + v
            ax, bx = min(v[0], v[3]), max(v[0], v[3])
            az, bz = min(v[2], v[5]), max(v[2], v[5])
            if bx < x0 or ax > x1 or bz < z0 or az > z1:
                continue
            out.update((x, y, z) for x in range(max(ax, x0), min(bx, x1) + 1)
                       for y in range(min(v[1], v[4]), max(v[1], v[4]) + 1)
                       for z in range(max(az, z0), min(bz, z1) + 1))
    _MEMO[key] = out
    return out


def pit_of(source_root):
    """(x, z) -> the Deep's tread y at a pit column, or None outside the pit (tools/rift_deep.py model())."""
    if ("pit", source_root) not in _MEMO:
        import rift_deep as RD
        m = RD.model(source_root)
        X0, Z0, _X1, _Z1 = m["box"]
        mask, tread = m["mask"], m["tread_y"]

        def at(x, z):
            a, b = z - Z0, x - X0
            if 0 <= a < mask.shape[0] and 0 <= b < mask.shape[1] and mask[a, b]:
                return int(tread[a, b])
            return None
        _MEMO[("pit", source_root)] = at
    return _MEMO[("pit", source_root)]


# --------------------------------------------------------------- the natural ground, as the export painted it

def painted_terrain(cols, source_root):
    """{(x, z): WorldPainter terrain code name} for the given columns, by tools/paint_maps.py's own rule: the
    sub-region's preset, its patches, terrain_above/below on height plus jitter, scree and the rock slope, from the
    same value noise and seed. The coast, lake, river and ravine overrides paint_maps applies afterwards are NOT
    modelled; instead this fails closed if any of them can reach these columns."""
    import paint_maps as PM
    from PIL import Image, ImageDraw
    import terrain as T
    g = ground_of(source_root)
    H = g.heights
    world = g.world
    sea = T.sea_level(world)
    xs = [c[0] for c in cols]
    zs = [c[1] for c in cols]
    X0, Z0, X1, Z1 = min(xs) - 2, min(zs) - 2, max(xs) + 2, max(zs) + 2
    regions = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    subs, presets = regions["subregions"], regions["paint_presets"]
    img = Image.new("L", (X1 - X0 + 1, Z1 - Z0 + 1), 0)
    d = ImageDraw.Draw(img)
    for i in sorted(range(len(subs)), key=lambda i: -subs[i]["measured"]["area_km2"]):
        for ring in subs[i]["polygons"]:
            if len(ring) >= 3:
                d.polygon([(p[0] - X0, p[1] - Z0) for p in ring], fill=i + 1)
    idx = np.asarray(img)
    lo_ground = min(g(x, z) for x, z in cols)
    if lo_ground < sea + 8:
        raise RelicError("ground y%d is within reach of paint_maps' coast bands (sea y%d): not modelled" % (lo_ground, sea))
    lm = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
    for l_ in lm["landmarks"]:
        wb = l_.get("water_body")
        rings = (wb or {}).get("basin_polygons") or []
        pts = [p for r in rings for p in r] + [p for ax in (l_.get("axes") or []) if l_.get("kind") == "ravine"
                                               for p in ax["polyline"]]
        if pts and not (max(p[0] for p in pts) < X0 - 16 or min(p[0] for p in pts) > X1 + 16 or
                        max(p[1] for p in pts) < Z0 - 16 or min(p[1] for p in pts) > Z1 + 16):
            raise RelicError("landmark %s (a lake basin or ravine) reaches the relic area: its paint is not modelled"
                             % l_.get("id"))
    rv = json.loads((ROOT / "data" / "rivers.json").read_text(encoding="utf-8"))
    for p in _numbers2(rv):
        if X0 - 32 <= p[0] <= X1 + 32 and Z0 - 32 <= p[1] <= Z1 + 32:
            raise RelicError("a river point %s reaches the relic area: its paint is not modelled" % (p,))
    noise = {}

    def nz(scale, salt):
        if (scale, salt) not in noise:
            noise[(scale, salt)] = PM.value_noise(scale, PAINT_SEED + salt)
        return noise[(scale, salt)]
    jitter = (nz(48, 7) - 0.5) * 16.0
    win = H[Z0 - 2:Z1 + 3, X0 - 2:X1 + 3]
    slope = T.slope_degrees(win)[2:-2, 2:-2]
    codes = {v: k for k, v in PM.TERRAIN_CODES.items()}
    out = {}
    for (x, z) in cols:
        i = int(idx[z - Z0, x - X0])
        if i == 0:
            raise RelicError("column %s is in no sub-region (paint_maps fills it from a neighbour): not modelled" % ((x, z),))
        s = subs[i - 1]
        pr = dict(presets[s["paint"]["preset"]], **(s["paint"].get("override") or {}))
        h = float(H[z, x]) + float(jitter[z, x])
        t = pr.get("terrain", "GRAVEL")
        for patch in pr.get("patches") or []:
            if nz(patch.get("scale", 64), 11 + PM.TERRAIN_CODES[patch["terrain"]])[z, x] < patch["coverage"]:
                t = patch["terrain"]
        for lo, name in pr.get("terrain_above") or []:
            if h >= lo:
                t = name
        for hi_, name in pr.get("terrain_below") or []:
            if h < hi_:
                t = name
        sc = pr.get("scree")
        sl = float(slope[z - Z0, x - X0])
        if sc and sc["slope_deg"][0] <= sl < sc["slope_deg"][1] and nz(24, 29)[z, x] < sc.get("coverage", 0.7):
            t = sc["terrain"]
        steep = pr.get("rock_slope_deg", 38)
        if steep and sl >= steep:
            t = pr.get("rock", "STONE_MIX")
        assert t in PM.TERRAIN_CODES, t
        out[(x, z)] = codes[PM.TERRAIN_CODES[t]]
    return out


def _numbers2(o):
    """Every [x, z] or [x, y, z] number list in a JSON document, as (x, z)."""
    if isinstance(o, dict):
        for v in o.values():
            yield from _numbers2(v)
    elif isinstance(o, list):
        if len(o) in (2, 3) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in o):
            yield (o[0], o[-1])
        else:
            for v in o:
                yield from _numbers2(v)


# --------------------------------------------------------------- the undo: the old surface build, taken off

def undo_plan(source_root):
    """-> (cells {(x, y, z): block to write}, stats). The cells the superseded surface build wrote that the current
    tools/deep_city.py does not, each put back to the ground the export had: air over the ground, the painted
    terrain at and under it. Cells the old build wrote as air over the ground are skipped (see the module doc).

    Cells the Rift skin lays (R1, tools/rift_skin.py) are left too, like the city's: R1 runs before R9RU in every
    tools/reapply.py run, so by the time the undo runs it has already laid its block over the old build's, and the
    painted ground would pave the skin over (2026-10-02: 62 cells of distortion stone and crying obsidian at the
    region's south-west, turned to gravel)."""
    import relic_surface_superseded as S
    g = ground_of(source_root)
    old = S.old_write_set(source_root)
    city = city_cells(source_root)
    skin = skin_cells(json.loads(DATA.read_text(encoding="utf-8"))["bounds"]["undo"])
    keep = {k: b for k, b in old.items() if k not in city}
    by_city = len(old) - len(keep)
    keep = {k: b for k, b in keep.items() if k not in skin}
    ground_cols = sorted({(x, z) for (x, y, z) in keep if y <= g(x, z)})
    paint = painted_terrain(ground_cols, source_root) if ground_cols else {}
    cells, st = {}, {"old_cells": len(old), "rewritten_by_city": by_city,
                     "rewritten_by_rift_skin": len(old) - by_city - len(keep), "air_over_ground_skipped": 0,
                     "to_air": 0, "to_ground": 0, "paint": {}}
    for (x, y, z), b in keep.items():
        gy = g(x, z)
        if y > gy:
            if b.split("[")[0] == AIR:
                st["air_over_ground_skipped"] += 1
                continue
            cells[(x, y, z)] = AIR
            st["to_air"] += 1
        else:
            code = paint[(x, z)]
            if code not in PAINT_BLOCK:
                raise RelicError("the export painted %s at %s, which this undo does not lay: not modelled" % (code, (x, z)))
            cells[(x, y, z)] = PAINT_BLOCK[code]
            st["to_ground"] += 1
            st["paint"][code] = st["paint"].get(code, 0) + 1
    if cells:
        st["bbox"] = [min(c[0] for c in cells), min(c[2] for c in cells), max(c[0] for c in cells),
                      max(c[2] for c in cells)]
    return cells, st


# --------------------------------------------------------------- the composition, in the hall

def composition(geo, spec):
    """cells[(x, y, z)] = block, for everything DEEP_CITY.md section 5 put on the surface, in the hall."""
    P = spec["palette"]
    c = spec["composition"]
    cx, cz = geo.hc
    base = geo.hfloor
    cells = {}

    def put(x, y, z, b):
        cells[(int(x), int(y), int(z))] = b

    # the stepped platform: three steps from radius 16 down to the top disc
    pl = c["platform"]
    r0, rtop, steps = pl["radius"], pl["top_radius"], pl["steps"]
    for i in range(steps):
        r = r0 - (r0 - rtop) * i / float(steps)
        y = base + i
        for x in range(int(cx - r), int(cx + r) + 1):
            for z in range(int(cz - r), int(cz + r) + 1):
                if math.hypot(x - cx, z - cz) <= r:
                    put(x, y, z, P["tuff_stone"] if i == steps - 1 else P["ancient_stone"])
        # a lit riser course at the step's edge
        for a in range(0, 360, 12):
            rx = cx + (r - 0.5) * math.cos(math.radians(a))
            rz = cz + (r - 0.5) * math.sin(math.radians(a))
            put(round(rx), y, round(rz), P["sea_lantern"])
    top = base + steps - 1

    # the plinth and the broken relic ring, unchanged numbers from data/deep_city.json relic_area.ring
    rg = c["ring"]
    for y in range(top + 1, top + rg["plinth"] + 1):
        for x in range(cx - 4, cx + 5):
            for z in range(cz - 4, cz + 5):
                if math.hypot(x - cx, z - cz) <= 4:
                    put(x, y, z, P["chiseled"] if (x - cx) % 2 == 0 else P["ancient_stone"])
    ring_cy = top + rg["plinth"] + rg["radius"] + 1
    gap = rg["gap_degrees"]
    for a in range(0, 360):
        if 90 - gap / 2.0 <= a <= 90 + gap / 2.0:         # the missing fragment's gap, at the ring's crown
            continue
        for rr in (rg["radius"] - 0.5, rg["radius"] + 0.0):
            y = ring_cy + rr * math.sin(math.radians(a))
            z = cz + rr * math.cos(math.radians(a))
            put(cx, round(y), round(z), P["hoopa_gold"] if rr > rg["radius"] - 0.4 else P["rift_seep"])

    # six standing ring arches, orbit and radius unchanged; orbit is inside the hall's wall
    ar = c["arches"]
    for k in range(ar["count"]):
        a = 2 * math.pi * k / ar["count"]
        ax, az = cx + ar["orbit"] * math.cos(a), cz + ar["orbit"] * math.sin(a)
        nx, nz = -math.sin(a), math.cos(a)                 # the arch's plane is tangent, so you look through it
        rad = ar["radius"]
        for t in range(0, 360, 6):
            dy = rad * math.sin(math.radians(t))
            du = rad * math.cos(math.radians(t))
            y = base + 1 + rad + dy
            if y < base + 1:
                continue
            x = ax + du * nx
            z = az + du * nz
            b = P["rift_seep"] if t in (84, 90, 96) else P["distortion"]
            put(round(x), round(y), round(z), b)
        for y in range(base + 1, base + 1 + rad):          # the two legs
            for s in (-1, 1):
                put(round(ax + s * rad * nx), y, round(az + s * rad * nz), P["distortion"])
        put(round(ax), base + 1 + 2 * rad + 1, round(az), P["end_rod"] + "[facing=up]")
        put(round(ax + 1.5 * nx), base + 1 + rad, round(az + 1.5 * nz), P["glass_band"])

    # eight standing stones, two fallen, at the orbit this file moved inward (composition.stones.changed_why)
    st = c["stones"]
    for k in range(st["count"]):
        a = 2 * math.pi * k / st["count"] + math.pi / st["count"]
        sx, sz = cx + st["orbit"] * math.cos(a), cz + st["orbit"] * math.sin(a)
        h = st["height"][0] + (k * 3) % (st["height"][1] - st["height"][0] + 1)
        fallen = k < st["fallen"]
        if fallen:
            # INWARD, toward the ring. Outward would lay a stone of height h at orbit + h, which for the
            # tallest stone is 26 and the hall's radius is 21: the report caught exactly that.
            for j in range(h):
                put(round(sx - j * math.cos(a)), base + 1, round(sz - j * math.sin(a)),
                    P["ancient_stone"] if j % 3 else P["chiseled"])
        else:
            for y in range(base + 1, base + 1 + h):
                put(round(sx), y, round(sz), P["ancient_stone"] if (y - base) % 3 else P["chiseled"])

    # the choked shaft in the dome's apex: masonry ring, rubble above it, no air anywhere in it
    ch = geo.choke
    half = ch["ring"] // 2
    rock = ch["fill_used"]
    for y in range(ch["from_y"], ch["to_y"] + 1):
        for dx in range(-half, half + 1):
            for dz in range(-half, half + 1):
                edge = abs(dx) == half or abs(dz) == half
                put(cx + dx, y, cz + dz,
                    P["ancient_stone"] if (edge and y <= ch["from_y"] + 1) else rock[(y + dx + dz) % len(rock)])
    return cells


# --------------------------------------------------------------- the HQ's way down (geometry.hq)

# a run descending along `step` faces back up it: the stair's tall side is uphill
UPHILL = {(0, 1): "north", (0, -1): "south", (1, 0): "west", (-1, 0): "east"}


def hq_plan(spec):
    """-> {"cells": {(x, y, z): block}, "air": set, "floors": set, "undo": set}: everything carve/40_hq writes (the
    hull aside), from data/relic_underground.json geometry.hq alone. Layered: the records room's shell and air, then the
    runs (their floors, then their head room), the dressing, the lights and the hatch's two cells. Nothing is written at
    or over the HQ room's floor (the door's plates came off 2026-10-02: the guard is the way in), and no cell the passage
    writes is touched."""
    h = spec["geometry"]["hq"]
    geo = Geo(spec)
    room_y, hr = h["room"]["floor_y"], h["head_room"]
    cells = {}

    def passage_owns(x, y, z):
        r = geo.carved_range(x, z)
        return r is not None and r[0] <= y <= r[1]

    b = h["basement"]
    ox0, oy0, oz0, ox1, oy1, oz1 = b["outer"]
    ix0, iy0, iz0, ix1, iy1, iz1 = b["interior"]
    for x in range(ox0, ox1 + 1):
        for y in range(oy0, oy1 + 1):
            for z in range(oz0, oz1 + 1):
                if passage_owns(x, y, z):
                    continue
                if ix0 <= x <= ix1 and iy0 <= y <= iy1 and iz0 <= z <= iz1:
                    cells[(x, y, z)] = AIR
                elif y == oy0:
                    cells[(x, y, z)] = b["floor_block"]
                elif y == oy1:
                    cells[(x, y, z)] = b["ceiling_block"]
                else:
                    cells[(x, y, z)] = b["wall_block"]
    floors, airs = {}, set()
    for run in h["runs"]:
        if "landing" in run:
            x0, z0, x1, z1 = run["landing"]
            steps = [(x, z, run["floor_y"], h["landing_block"]) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
        else:
            (fx, fz), (sx, sz) = run["from"], run["step"]
            blk = "%s[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (h["stair_block"], UPHILL[(sx, sz)])
            steps = [(fx + k * sx, fz + k * sz, run["floor_y"] - k, blk) for k in range(run["n"])]
        for x, z, f, blk in steps:
            if (x, f, z) in floors:
                raise RelicError("run %s lays a second floor at %s" % (run["id"], (x, f, z)))
            floors[(x, f, z)] = blk
            airs.update((x, y, z) for y in range(f + 1, min(f + hr, room_y) + 1))
    clash = sorted(set(floors) & airs)
    if clash:
        raise RelicError("a tread or landing is in another flight's head room at %s" % (clash[:3],))
    for c in airs:
        cells[c] = AIR
    cells.update(floors)
    for d in h["dressing"]:
        x0, y0, z0, x1, y1, z1 = d["fill"]
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    cells[(x, y, z)] = d["block"]
    L = h["lights"]
    for c in L["standing"]:
        cells[tuple(c)] = L["block"]
    for c in L["hanging"]:
        cells[tuple(c)] = L["hanging_block"]
    undo = {tuple(c) for c in h["hatch_undo"]["cells"]}
    for c in undo:
        cells[c] = h["hatch_undo"]["block"]
    bad = [c for c in cells if passage_owns(*c)]
    if bad:
        raise RelicError("the HQ's way down writes %d cells the passage writes, first %s" % (len(bad), bad[0]))
    return {"cells": cells, "air": {c for c, v in cells.items() if v == AIR}, "floors": set(floors), "undo": undo}


def reserved_boxes(spec):
    """{id: (x0, y0, z0, x1, y1, z1)} of the data/deep_city.json reservations geometry.hq names."""
    dc = json.loads((ROOT / "data" / "deep_city.json").read_text(encoding="utf-8"))
    have = {r["id"]: tuple(r["box"]) for r in dc["reserved"]}
    want = spec["geometry"]["hq"]["reserved_boxes"]
    miss = [w for w in want if w not in have]
    if miss:
        raise RelicError("data/deep_city.json reserves no %s" % miss)
    return {w: have[w] for w in want}


def in_boxes(c, boxes):
    return any(b[0] <= c[0] <= b[3] and b[1] <= c[1] <= b[4] and b[2] <= c[2] <= b[5] for b in boxes)


N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def hq_hull(spec, hp, source_root):
    """The cells carve/40_hq makes rock if they are void: every face-neighbour of the way down's air that it does not
    write, inside the reserved boxes, never above a pit column's tread (so never into the HQ room or the Deep), never a
    cell the passage or the city writes."""
    geo = Geo(spec)
    boxes = list(reserved_boxes(spec).values())
    pit = pit_of(source_root)
    city = city_cells(source_root)
    out = set()
    for (x, y, z) in hp["air"]:
        for dx, dy, dz in N6:
            n = (x + dx, y + dy, z + dz)
            if n in hp["cells"] or n in city or not in_boxes(n, boxes):
                continue
            r = geo.carved_range(n[0], n[2])
            if r is not None and r[0] <= n[1] <= r[1]:
                continue
            t = pit(n[0], n[2])
            if t is not None and n[1] > t:
                continue
            out.add(n)
    return out


def hq_unsealed(spec, hp, hull, source_root):
    """[(air cell, neighbour)] for every face of the way down's air that nothing guarantees is rock or meant to be
    open. A face is sealed when the neighbour is written by the way down, is the passage's (carved_range), is in the
    hull, is under a pit column's tread at y-4 or above (tools/rift_deep.py refills every void there, R9B), or is
    the HQ room's air over the stair's head (the one opening, y over the room's floor)."""
    geo = Geo(spec)
    pit = pit_of(source_root)
    room_y = spec["geometry"]["hq"]["room"]["floor_y"]
    floor_y = json.loads((ROOT / "data" / "rift_deep.json").read_text(encoding="utf-8"))["floor_y"]
    depth = json.loads((ROOT / "data" / "rift_deep.json").read_text(encoding="utf-8"))["shell"]["depth"]
    out = []
    for (x, y, z) in sorted(hp["air"]):
        for dx, dy, dz in N6:
            n = (x + dx, y + dy, z + dz)
            if n in hp["cells"] or n in hull:
                continue
            r = geo.carved_range(n[0], n[2])
            if r is not None and r[0] <= n[1] <= r[1]:
                continue
            t = pit(n[0], n[2])
            if t is not None and floor_y - depth <= n[1] < t:
                continue
            if t is not None and n[1] > room_y and y <= room_y:
                continue
            out.append(((x, y, z), n))
    return out


# --------------------------------------------------------------- fills

def rows(cells):
    """[(x0, y, z, x1, block)] -- the cells merged into runs along x, so a disc is rows and not setblocks."""
    out = []
    by = {}
    for (x, y, z), b in cells.items():
        by.setdefault((y, z), []).append((x, b))
    for (y, z), lst in sorted(by.items()):
        lst.sort()
        i = 0
        while i < len(lst):
            k = i
            while k + 1 < len(lst) and lst[k + 1][0] == lst[k][0] + 1 and lst[k + 1][1] == lst[i][1]:
                k += 1
            out.append((lst[i][0], y, z, lst[k][0], lst[i][1]))
            i = k + 1
    return out


def fill(x0, y, z, x1, b, mode=""):
    return "fill %d %d %d %d %d %d %s%s" % (x0, y, z, x1, y, z, b, (" " + mode) if mode else "")


def rock_for(y, spec):
    p = spec["palette"]
    tab = p["rock_lower"] if y < p["rock_split_y"] else p["rock_upper"]
    return tab[0]


# --------------------------------------------------------------- report

def cmd_report(a):
    spec = load()
    geo = Geo(spec)
    sr = source_root_of(getattr(a, "source_root", None))
    g = ground_of(sr)
    bad, note = [], []
    fp = geo.footprint()

    # 1 cover. TWO numbers, and conflating them was this check's first fault: the choked shaft's top is
    # higher than any ceiling and is SOLID, so the rock over the void and the rock over the choke are
    # different measurements and only the first one is a cavern's cover.
    ch = geo.choke
    half = ch["ring"] // 2

    def is_choke(x, z):
        return abs(x - ch["at"][0]) <= half and abs(z - ch["at"][1]) <= half
    void_cover = min(g(x, z) - hi for (x, z), (_lo, hi) in fp.items() if not is_choke(x, z))
    choke_cover = min(g(x, z) - ch["to_y"] for (x, z) in fp if is_choke(x, z))
    note.append("carved columns %d; rock over the void at its thinnest %d blocks; rock over the choked "
                "shaft's top (solid, not void) %d blocks" % (len(fp), void_cover, choke_cover))
    if void_cover < 9:
        bad.append("only %d blocks of rock over the void; SOUTHERN_RIFT_MEGA wants 9 under a floor"
                   % void_cover)
    if choke_cover < spec["geometry"]["shell"]["blocks"]:
        bad.append("only %d blocks over the choked shaft, less than the %d-block shell: the shell would be "
                   "clipped by the ground" % (choke_cover, spec["geometry"]["shell"]["blocks"]))

    # 2 the zone's boxes contain every carved column, and the knock box and turn-back point do not
    boxes = spec["zone"]["boxes"]

    def inbox(x, z):
        return any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for b in boxes)
    # The two threshold columns at the open doorway are carved and deliberately NOT in the zone: a passless
    # player stands IN the doorway, sees the passage and is turned back the moment they step past it. Any
    # other carved column outside the boxes is a hole in the zone.
    thr = spec["zone"]["threshold_x"]
    out = [c for c in fp if not inbox(*c) and c[0] < thr]
    if out:
        bad.append("%d carved columns west of the threshold x%d are outside the zone's boxes, first %s"
                   % (len(out), thr, out[0]))
    stray = sorted(c for c in fp if not inbox(*c) and c[0] >= thr)
    note.append("carved columns outside the zone, at the doorway: %d%s"
                % (len(stray), (" " + str(stray)) if stray else ""))
    kb = spec["zone"]["knock"]["box"]
    for x in range(kb[0], kb[3] + 1):
        for z in range(kb[2], kb[5] + 1):
            if inbox(x, z):
                bad.append("the knock box column %s is INSIDE the zone: a passless player would be turned "
                           "back while asking to be let through" % ((x, z),))
    tb = spec["zone"]["turn_back"]["at"]
    if inbox(int(tb[0]), int(tb[2])):
        bad.append("the turn-back point %s is inside the zone: the check would loop" % (tb,))

    # 3 the zone's ceiling is clear of every surface over it
    ytop = spec["zone"]["y"][1]
    lowest = min(g(x, z) for b in boxes for x in range(b[0], b[2] + 1, 2) for z in range(b[1], b[3] + 1, 2))
    note.append("zone ceiling y%d, lowest ground over the zone y%d, margin %d blocks"
                % (ytop, lowest, lowest - ytop))
    if lowest - ytop < 8:
        bad.append("the zone's ceiling y%d is within %d of the ground at its lowest (y%d): a player walking "
                   "on the surface would be turned back" % (ytop, lowest - ytop, lowest))
    if ytop < max(hi for _k, (_lo, hi) in fp.items()):
        bad.append("the zone's ceiling y%d is below the highest thing carved" % ytop)

    # 4 the composition fits the hall it is in
    cells = composition(geo, spec)
    for (x, y, z) in cells:
        r = geo.carved_range(x, z)
        if r is None or not geo.in_hall(x, z):
            bad.append("a composition block at %s is outside the hall" % ((x, y, z),))
            break
        if y < geo.hfloor or y > r[1]:
            bad.append("a composition block at %s is outside the hall's air (floor %d, ceiling %d)"
                       % ((x, y, z), geo.hfloor, r[1]))
            break
    apex = max(y for (_x, y, _z) in cells if y < geo.choke["from_y"]) if cells else 0
    note.append("composition blocks %d, highest non-choke block y%d, dome apex y%d"
                % (len(cells), apex, geo.capex))

    # 5 containment in the traced region the owner drew for the relic area
    try:
        import rift_deep as RD
        m, (X0, Z0, _X1, _Z1), _n = RD.region_mask(spec["measured"]["region_containment"]["region"], sr)
        miss = 0
        for (x, z) in fp:
            if geo.in_hall(x, z):
                i, j = z - Z0, x - X0
                if not (0 <= i < m.shape[0] and 0 <= j < m.shape[1] and m[i, j]):
                    miss += 1
        note.append("hall columns outside the traced relic region: %d" % miss)
        if miss:
            bad.append("%d hall columns are outside the traced relic_area_shrine region" % miss)
    except Exception as e:                                   # pragma: no cover - mask is a local input
        note.append("region containment NOT CHECKED (%s: %s)" % (type(e).__name__, e))

    # 6 the owed dependencies, named and not quietly forgotten
    owed = []
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    have = set()
    for f in prog.get("flags", []) if isinstance(prog.get("flags"), list) else []:
        have.add("%s:flag/%s" % (NS, f.get("id")))
    for adv in spec["zone"]["pass"]["threshold_advancements"]:
        if have and adv not in have:
            owed.append("the pass names %s and data/progression.json has no such flag" % adv)
    if "cobblers:flag/rift_crisis_resolved" in spec["zone"]["pass"]["threshold_advancements"]:
        bad.append("the pass names cobblers:flag/rift_crisis_resolved, whose setter NOTHING INVOKES (data/progression.json "
                   "set_by.invoked_by is null): "
                   "the zone would be shut forever (data/relic_underground.json needs.upgrade_path)")
    # 7 the Deep and the city: nothing carved into the pit's air or into a cell the city writes, and the turn-back
    # lands on the Compact's front step in the open (measured: tools/rift_deep.py's treads, tools/deep_city.py's build)
    pit = pit_of(sr)
    city = city_cells(sr)
    clash = []
    for (x, zz), (lo, hi) in fp.items():
        t = pit(x, zz)
        for y in range(lo, hi + 1):
            if (t is not None and y > t) or (x, y, zz) in city:
                clash.append((x, y, zz))
    if clash:
        bad.append("%d carved cells are in the Deep's air or in a cell the city writes, first %s" % (len(clash), clash[0]))
    tx, ty, tz = (int(math.floor(v)) for v in spec["zone"]["turn_back"]["at"])
    t = pit(tx, tz)
    floor = city.get((tx, ty - 1, tz))
    if t != ty - 1:
        bad.append("the turn-back (%d, %d, %d) does not stand on the Deep's tread (tread there: %s)" % (tx, ty, tz, t))
    if floor is not None and floor.split("[")[0] == AIR:
        bad.append("the turn-back's floor (%d, %d, %d) is air in the city's build" % (tx, ty - 1, tz))
    for dy in (0, 1):
        b = city.get((tx, ty + dy, tz))
        if b is not None and b.split("[")[0] != AIR:
            bad.append("the turn-back (%d, %d, %d) is inside the city's %s" % (tx, ty + dy, tz, b))
    note.append("turn-back (%d, %d, %d): tread y%s, floor %s, two clear blocks over it"
                % (tx, ty, tz, t, (floor or "the tread itself").split("[")[0]))
    # 7a the HQ's way down (geometry.hq): its own cells, the city's door it opens, the reserved boxes it stays in, the
    # knock box it carves, and every face of its air sealed
    h = spec["geometry"]["hq"]
    try:
        hp = hq_plan(spec)
    except RelicError as e:
        bad.append("the HQ's way down cannot be planned: %s" % e)
        hp = None
    if hp is not None:
        boxes = reserved_boxes(spec)
        outside = [c for c in hp["cells"] if c not in hp["undo"] and not in_boxes(c, boxes.values())]
        if outside:
            bad.append("%d cells of the HQ's way down are outside the reserved boxes %s, first %s"
                       % (len(outside), sorted(boxes), sorted(outside)[0]))
        in_city = sorted(c for c in hp["cells"] if c in city)
        if in_city:
            bad.append("%d cells of the HQ's way down are cells the city writes, first %s (%s)"
                       % (len(in_city), in_city[0], city[in_city[0]]))
        # a dressing fill declared seals_room is the one thing allowed over the tread: the wall that closes the
        # storey-0 room off from the next HQ section (2026-10-02), inside its own reservation (checked above)
        sealing = {(x, y, z) for d in h["dressing"] if d.get("seals_room")
                   for x in range(d["fill"][0], d["fill"][3] + 1) for y in range(d["fill"][1], d["fill"][4] + 1)
                   for z in range(d["fill"][2], d["fill"][5] + 1)}
        in_pit_air = sorted(c for c in hp["cells"] if c not in sealing
                            and pit(c[0], c[2]) is not None and c[1] > pit(c[0], c[2]))
        if in_pit_air:
            bad.append("%d cells of the HQ's way down are in the Deep's air or the HQ room, first %s"
                       % (len(in_pit_air), in_pit_air[0]))
        fd = h["front_door"]
        dx_, dy_, dz_ = fd["at"]
        door = city.get((dx_, dy_, dz_), "")
        if door.split("[")[0] != "minecraft:iron_door" or "half=lower" not in door:
            bad.append("the HQ's front door %s is %s in the city's build, not an iron door's lower half"
                       % (fd["at"], door or "nothing"))
        # the door stays shut: nothing this pack writes stands beside it
        near_door = [c for c in hp["cells"] if abs(c[0] - dx_) <= 1 and abs(c[2] - dz_) <= 1 and dy_ - 1 <= c[1] <= dy_ + 2]
        if near_door:
            bad.append("the HQ's way down writes %s beside the door %s: the door is the guard's" % (near_door[:2], fd["at"]))
        # the guards: each seat, the doorstep and both landings stand on the city's floor or the pit's tread with two
        # clear blocks over them; each guard is in talking reach of where its player stands
        def stands(c):
            under = city.get((c[0], c[1] - 1, c[2]))
            t = pit(c[0], c[2])
            on = (under is not None and under.split("[")[0] != AIR) or (under is None and t == c[1] - 1)
            clear = all((city.get((c[0], c[1] + dy, c[2])) or AIR).split("[")[0] == AIR and
                        (t is None or c[1] + dy > t) for dy in (0, 1))
            return on and clear
        gd, ig = h["guard"], h["inside_guard"]
        spots = {"the guard": gd["at"], "the doorstep": gd["front_step"], "the inside landing": gd["inside_landing"],
                 "the inside guard": ig["at"],
                 "the way out's landing": [int(math.floor(v)) for v in ig["release"]["to"]]}
        for what, c in spots.items():
            if not stands(tuple(c)):
                bad.append("%s %s does not stand on a floor with two clear blocks over it" % (what, c))
        if [int(math.floor(v)) for v in gd["admit"]["to"]] != list(gd["inside_landing"]):
            bad.append("the guard's admit target %s is not the inside landing %s" % (gd["admit"]["to"], gd["inside_landing"]))
        rx0, rz0, rx1, rz1 = h["room"]["interior"]
        for what, c in (("the inside landing", gd["inside_landing"]), ("the inside guard", ig["at"])):
            if not (rx0 <= c[0] <= rx1 and rz0 <= c[2] <= rz1 and c[1] == h["room"]["floor_y"] + 1):
                bad.append("%s %s is not on the storey-0 room's floor %s" % (what, c, h["room"]["interior"]))
        for what, a_, b_ in (("the guard", gd["at"], gd["front_step"]), ("the inside guard", ig["at"], gd["inside_landing"])):
            if math.dist(a_, b_) > 3:
                bad.append("%s %s is out of talking reach of %s" % (what, a_, b_))
        if math.dist(gd["at"], ig["at"]) <= 3:
            bad.append("the two guards stand within 3 blocks: R18RU's 'already there' probe (distance ..2) could mistake one")
        try:
            npc_placements(spec)
        except RelicError as e:
            bad.append(str(e))
        for c in hp["undo"]:
            if c in city:
                bad.append("the city still writes %s at the old hatch %s: the undo would fight R9DC" % (city[c], c))
        kb = spec["zone"]["knock"]["box"]
        hole = [(x, y, zz) for x in range(kb[0], kb[3] + 1) for y in range(kb[1], kb[4] + 1)
                for zz in range(kb[2], kb[5] + 1) if hp["cells"].get((x, y, zz)) != AIR]
        nofl = [(x, zz) for x in range(kb[0], kb[3] + 1) for zz in range(kb[2], kb[5] + 1)
                if hp["cells"].get((x, kb[1] - 1, zz), AIR) == AIR]
        if hole or nofl:
            bad.append("the knock box %s is not the records room's air over its floor: %d solid cells, %d columns with "
                       "no floor, first %s" % (kb, len(hole), len(nofl), (hole or nofl)[0]))
        hull = hq_hull(spec, hp, sr)
        open_ = hq_unsealed(spec, hp, hull, sr)
        if open_:
            bad.append("%d faces of the HQ's way down are not sealed, first %s" % (len(open_), open_[0]))
        note.append("the HQ's way down: %d cells (%d air, %d treads and landings), hull %d, hatch cells %s; the door "
                    "shut, the guard at %s, the inside landing %s, the inside guard at %s"
                    % (len(hp["cells"]), len(hp["air"]), len(hp["floors"]), len(hull), sorted(hp["undo"]),
                       h["guard"]["at"], h["guard"]["inside_landing"], h["inside_guard"]["at"]))

    # 8 the undo: what it takes off and what it lays back
    try:
        ucells, ust = undo_plan(sr)
        note.append("undo: %d cells of the old surface build; %d rewritten by the current city; %d left to the Rift skin "
                    "(R1); %d cut-air cells over the ground skipped; %d to air, %d to painted ground %s; bbox %s"
                    % (ust["old_cells"], ust["rewritten_by_city"], ust["rewritten_by_rift_skin"],
                       ust["air_over_ground_skipped"], ust["to_air"],
                       ust["to_ground"], ust["paint"], ust.get("bbox")))
        hit = [c for c in ucells if geo.carved_range(c[0], c[2]) and c[1] <= geo.carved_range(c[0], c[2])[1] + SHELL]
        if hit:
            bad.append("the undo writes %d cells within the carve's shell, first %s" % (len(hit), hit[0]))
    except RelicError as e:
        bad.append("the undo cannot be planned: %s" % e)

    # 9 the spawn decision (the owner, 2026-10-02: nothing spawns in the hall): its zones are in the spawn suppression
    sd = spec["composition"]["spawn_decision"]
    ss = json.loads((ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))
    have = {z_["id"]: z_["box"] for z_ in ss.get("spawn_free_zones") or []}
    for zid, box in (sd.get("zones") or {}).items():
        if have.get(zid) != box:
            bad.append("spawn-free zone %s %s is not in data/spawn_suppression.json as decided (there: %s)"
                       % (zid, box, have.get(zid)))
    if not sd.get("zones"):
        owed.append("a spawn decision for the hall (composition.spawn_decision has no zones)")

    for n in note:
        print("  " + n)
    for o in owed:
        print("  owed: " + o)
    for b in bad:
        print("PROBLEM: " + b)
    print("relic_underground report: %d problems, %d owed" % (len(bad), len(owed)))
    return 2 if bad else (1 if owed else 0)


# --------------------------------------------------------------- build

def text(s, **st):
    return json.dumps(dict({"text": s}, **st), ensure_ascii=False)


def box_cond(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    return {"condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"location": {"dimension": "minecraft:overworld", "position": {
                "x": {"min": x0, "max": x1 + 1}, "y": {"min": y0, "max": y1 + 1},
                "z": {"min": z0, "max": z1 + 1}}}}}


def adv(conds, reward):
    return {"criteria": {"here": {"trigger": "minecraft:location", "conditions": {"player": conds}}},
            "rewards": {"function": reward}}


def guard_functions(spec):
    """{function name: lines} for the HQ door's guards (geometry.hq.guard, inside_guard; the owner, 2026-10-02). The
    iron door never opens: each guard's compiled dialogue runs one of these as and at THE ONE PLAYER who chose it
    (tools/compile_dialogue.py `function` effect), and that player is moved past the door. The stage test is the
    dialogue's (a per-player enum in Cobblemon player data, which no command can read); these test only that the player
    is at the guard."""
    fn = {}
    for key, side, act, what in (("guard", "admit", "hq_admit", "in to the storey-0 room"),
                                 ("inside_guard", "release", "hq_release", "back out to ring 0's doorstep")):
        gd = spec["geometry"]["hq"][key]
        mv = gd[side]
        ax, ay, az = gd["at"]
        x, y, z = mv["to"]
        fn[act] = [
            "# the HQ guard's %s (data/dialogue.json %s): %s. Run as and at the player who chose it, never" % (
                act, gd["conversation"], what),
            "# @a: the door stays shut and nobody else moves. Nothing for a player not at the guard.",
            "execute unless entity @s[x=%d,y=%d,z=%d,distance=..%d] run return fail" % (ax, ay, az, mv["reach"]),
            "ride @s dismount",
            "tp @s %s %d %s %s %s" % (x, y, z, mv["yaw"], mv["pitch"])]
    return fn


def cmd_build(a):
    spec = load()
    geo = Geo(spec)
    sr = source_root_of(getattr(a, "source_root", None))
    rc = cmd_report(argparse.Namespace(source_root=sr))
    if rc == 2:
        raise RelicError("report found problems; nothing built")
    g = ground_of(sr)
    z = spec["zone"]
    obj = z["objective"]
    F = "%s:%s" % (NS, FOLDER)
    files, fn = {}, {}

    # ---- the zone check. The advancement tests LOCATION ONLY; the pass is tested in the function, because
    # minecraft:entity_scores does not match an unset score and would fail OPEN for every new player.
    ymin, ymax = z["y"]
    files["data/%s/advancement/%s/relic_zone.json" % (NS, FOLDER)] = adv(
        [{"condition": "minecraft:any_of",
          "terms": [box_cond((b[0], ymin, b[1]), (b[2], ymax, b[3])) for b in z["boxes"]]}],
        "%s/zone" % F)
    kb = z["knock"]["box"]
    files["data/%s/advancement/%s/relic_knock.json" % (NS, FOLDER)] = adv(
        [box_cond(kb[:3], kb[3:])], "%s/knock" % F)

    fn["load"] = ["# one dummy objective, one value per player, never reset and never unset by this pack",
                  "scoreboard objectives add %s %s" % (obj, z["objective_criterion"])]
    tb = z["turn_back"]
    tx, ty, tz = tb["at"]
    fn["zone"] = [
        "# the relic hall's zone check (docs/mechanics/RIFT_ZONES.md section 4, data/relic_underground.json).",
        "# The advancement tests LOCATION ONLY. The pass is tested HERE: minecraft:entity_scores does not",
        "# match an unset score, so a score condition in the advancement fails OPEN for every player who has",
        "# never stood at the HQ's door. `unless score ... matches 1..` is true for an unset score.",
        "# The knock box is OUTSIDE the zone's boxes, so nothing has to be excluded and nothing can race.",
        "advancement revoke @s only %s:%s/relic_zone" % (NS, FOLDER),
        "execute if entity %s unless score @s %s matches 1.. run function %s/turn_back" % (z["exempt"], obj, F)]
    fn["turn_back"] = [
        "# a bed or respawn anchor set inside the hall goes first, so a respawn cannot loop (RIFT_ZONES.md 4)",
        "execute if entity @s[gamemode=!creative] run spawnpoint @s %d %d %d" % (int(tx), int(ty), int(tz)),
        "# the mount first, then the player. UNPROVEN that Cobblemon riding survives this (RIFT_ZONES.md 4)",
        "execute on vehicle run tp @s %s %d %s" % (tx, ty, tz),
        "tp @s %s %d %s %s %s" % (tx, ty, tz, tb["yaw"], tb["pitch"]),
        "title @s actionbar %s" % text(tb["message"], color="gold")]
    inner = ",".join("%s=true" % s for s in z["pass"]["threshold_advancements"])
    fn["knock"] = [
        "# THE THING THAT CALLS QUALIFY. A player standing in the HQ basement's alcove at the open west",
        "# doorway is asking to be let through, so the server answers. data/gulch_mine.json gate.knock is",
        "# the same shape at the gulch's grille; there is no guard and no grille here, so the alcove asks.",
        "advancement revoke @s only %s:%s/relic_knock" % (NS, FOLDER),
        "function %s/qualify" % F]
    fn["qualify"] = [
        "# the pass is 'you came through the Compact HQ', plus the eight badge flags so that reaching the",
        "# basement early is still refused. ONE advancements={...} argument: a selector may not carry the key",
        "# twice. The flags are tools/progression_pack.py's per-player advancements (EXP-027).",
        "execute if entity @s[gamemode=!spectator,advancements={%s}] run function %s/grant" % (inner, F),
        "execute unless entity @s[advancements={%s}] run title @s actionbar %s"
        % (inner, text("The Compact's passage is closed to you.", color="gray"))]
    fn["grant"] = [
        "# the pass. Nothing is teleported: the doorway is OPEN and the player walks (the owner, 2026-10-01:",
        "# 'turned back by the zone check rather than barriers'). Dialogue may call this function instead of",
        "# composing a scoreboard command, so the objective's name lives in one place.",
        "execute unless score @s %s matches 1.. run title @s actionbar %s"
        % (obj, text("The Compact's passage is open to you.", color="aqua")),
        "scoreboard players set @s %s 1" % obj]

    fn.update(guard_functions(spec))

    # ---- the carve: shell, void, surfaces, re-shell, composition. The CAVERN pattern (tools/cavern_plan.py).
    fp = geo.footprint()
    cells_void, cells_rock, shell = {}, {}, {}
    for (x, zz), (lo, hi) in fp.items():
        cells_rock[(x, lo, zz)] = rock_for(lo, spec)                       # the floor
        cells_rock[(x, hi, zz)] = rock_for(hi, spec)                       # the ceiling
        for y in range(lo + 1, hi):
            cells_void[(x, y, zz)] = "minecraft:air"
        shell[(x, zz)] = (hi + 1, min(hi + SHELL, g(x, zz) - 1))
    x0 = min(c[0] for c in fp) - SHELL
    x1 = max(c[0] for c in fp) + SHELL
    z0 = min(c[1] for c in fp) - SHELL
    z1 = max(c[1] for c in fp) + SHELL
    for x in range(x0, x1 + 1):
        for zz in range(z0, z1 + 1):
            if (x, zz) in fp or geo.shell_distance(x, zz) > SHELL:
                continue
            lo, hi = geo.nearest_range(x, zz)
            shell[(x, zz)] = (max(ymin, lo - SHELL), min(hi + SHELL, g(x, zz) - 1))

    # the shell never reaches into the Deep's air (a pit column is capped at its tread, which is rock) and never
    # converts a cell the city writes: its rooms cut into the risers are air the shell's `replace` would fill
    pit = pit_of(sr)
    city = city_cells(sr)
    # the HQ's way down is carved AFTER the reshell (carve/40_hq), so the shell must never be laid in its cells: a
    # `replace` over its air would only be undone by 40_hq, but a shell cell in its walls is a second owner
    hp = hq_plan(spec)
    shell_cmds, shell_n, clipped, hq_skipped = [], 0, 0, 0
    for (x, zz), (lo, hi) in sorted(shell.items()):
        t = pit(x, zz)
        if t is not None and hi >= t:
            clipped += hi - t + 1
            hi = t - 1
        for y in range(lo, hi + 1):
            if (x, y, zz) in city:
                clipped += 1
                continue
            if (x, y, zz) in hp["cells"]:
                hq_skipped += 1
                continue
            shell_cmds.append((x, y, zz, rock_for(y, spec)))
            shell_n += 1
    shell_rows = rows({(x, y, zz): b for x, y, zz, b in shell_cmds})
    head = ["# the shell: every void within %d blocks of the carve made rock, over the roof and round the"
            % SHELL,
            "# walls, never above the ground (tools/cavern_plan.py 02_shell / 25_reshell, the Displaced City",
            "# precedent DEEP_CITY.md section 5 names). %d cells tested." % shell_n]
    body = [fill(r[0], r[1], r[2], r[3], r[4], "replace #%s:%s" % (NS, VOID_TAG)) for r in shell_rows]
    fn["carve/02_shell"] = head + body
    fn["carve/10_void"] = ["# the void: the hall, the gallery and the passage, dug through the shell"] + \
        [fill(r[0], r[1], r[2], r[3], r[4]) for r in rows(cells_void)]
    fn["carve/20_surfaces"] = ["# the floors and the ceilings"] + \
        [fill(r[0], r[1], r[2], r[3], r[4]) for r in rows(cells_rock)]
    fn["carve/25_reshell"] = ["# the shell again, after the carve: one pass cannot see what the excavation",
                              "# opens (tools/cavern_plan.py). Must run BEFORE anything is dug through it."] + body
    comp = composition(geo, spec)
    fn["carve/30_composition"] = ["# the relic site itself: DEEP_CITY.md section 5's platform, six arches,",
                                  "# plinth, broken ring and standing stones, at their own numbers, in the hall"] + \
        [fill(r[0], r[1], r[2], r[3], r[4]) for r in rows(comp)]
    # the HQ's way down (geometry.hq): after the reshell, so nothing seals it again. Its hull first (a void beside it
    # made rock, inside the reserved boxes only), then its cells: the records room, the stair, the dressing, the
    # lanterns, and the old hatch's two cells laid back to rock. Nothing at the city's iron door: the guard is the way in
    hull = hq_hull(spec, hp, sr)
    fn["carve/40_hq"] = ["# the HQ's way down: the guard (hq_admit) -> storey-0 room -> the stair in the reserved shaft ->",
                         "# the records room at y0 -> its open west doorway into the passage (data/relic_underground.json",
                         "# geometry.hq). Hull first, `replace` only: it turns a void beside the air into rock."] + \
        [fill(r[0], r[1], r[2], r[3], r[4], "replace #%s:%s" % (NS, VOID_TAG))
         for r in rows({c: rock_for(c[1], spec) for c in hull})] + \
        [fill(r[0], r[1], r[2], r[3], r[4]) for r in rows(hp["cells"])]

    # ---- the undo: the old surface build taken off, BEFORE the carve (it is on the surface, the carve 50 down).
    # rows() sorts by y, so in every column the ground goes back from the bottom up and no gravel is laid over air
    ucells, ust = undo_plan(sr)
    fn["undo"] = ["# the relic area's OLD surface build taken off a world that has it (tools/relic_surface_superseded.py",
                  "# minus what tools/deep_city.py still writes): air over the ground, the painted ground under it.",
                  "# On a world that never had it this lays air where there was air and the painted ground where",
                  "# the export painted it."] + [fill(r[0], r[1], r[2], r[3], r[4]) for r in rows(ucells)]

    # every block function split into parts of PART commands, in order; each says its chunks are held by the step
    order, written = [], {}
    for name in ("undo", "carve/02_shell", "carve/10_void", "carve/20_surfaces", "carve/25_reshell",
                 "carve/30_composition", "carve/40_hq"):
        lines = fn.pop(name)
        head = [l for l in lines if l.startswith("#")]
        cmds = [l for l in lines if not l.startswith("#")]
        for k in range(0, max(1, len(cmds)), PART):
            part = name if k == 0 else "%s_%d" % (name, k // PART + 1)
            body_lines = [LOADED_BY] + head + cmds[k:k + PART]
            probs = function_limits().check_lines(body_lines, part)
            if probs:
                raise RelicError("function %s would be refused: %s" % (part, probs[:3]))
            written[part] = body_lines
            order.append(part)
    fn.update(written)

    out = Path(a.out or OUT)
    if out.exists():
        shutil.rmtree(out)
    (out / "data" / NS / "function" / FOLDER / "carve").mkdir(parents=True, exist_ok=True)
    (out / "data" / NS / "advancement" / FOLDER).mkdir(parents=True, exist_ok=True)
    (out / "data" / NS / "tags" / "block").mkdir(parents=True, exist_ok=True)
    (out / "data" / "minecraft" / "tags" / "function").mkdir(parents=True, exist_ok=True)
    for p, body_ in files.items():
        (out / p).write_text(json.dumps(body_, indent=1) + "\n", encoding="utf-8")
    for name, lines in fn.items():
        (out / "data" / NS / "function" / FOLDER / (name + ".mcfunction")).write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
    (out / "data" / NS / "tags" / "block" / (VOID_TAG + ".json")).write_text(
        json.dumps({"values": VOID}, indent=1) + "\n", encoding="utf-8")
    (out / "data" / "minecraft" / "tags" / "function" / "load.json").write_text(
        json.dumps({"values": ["%s/load" % F]}, indent=1) + "\n", encoding="utf-8")
    (out / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48,
                  "description": "Cobblers: the relic site underground (tools/relic_underground.py)"}},
        indent=2) + "\n", encoding="utf-8")
    # the block functions R9RU runs, in order (tools/reapply.py indexed() reads this file)
    (out / "data" / NS / "function" / FOLDER / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")

    print(json.dumps({"out": str(out), "carved_columns": len(fp), "air_blocks": len(cells_void),
                      "surface_blocks": len(cells_rock), "shell_cells": shell_n, "shell_cells_clipped": clipped,
                      "shell_commands": len(body), "composition_blocks": len(comp),
                      "hq_cells": len(hp["cells"]), "hq_air": len(hp["air"]), "hq_hull": len(hull),
                      "shell_cells_left_to_the_hq": hq_skipped,
                      "undo_cells": len(ucells), "undo": {k: v for k, v in ust.items()},
                      "functions": {k: len(v) for k, v in fn.items()},
                      "advancements": len(files)}, indent=1))
    return 0


def function_limits():
    import function_limits as FL
    return FL


def hold_box(spec=None):
    """(x0, z0, x1, z1): every column R9RU writes -- the undo's columns (the relic area's traced region, from
    data/relic_underground.json bounds.undo) and the carve's with its shell -- in one forceload."""
    spec = spec or load()
    b = spec["bounds"]
    boxes = [b["undo"], b["carve_with_shell"]]
    return (min(x[0] for x in boxes), min(x[1] for x in boxes), max(x[2] for x in boxes), max(x[3] for x in boxes))


def npc_placements(spec=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for tools/reapply.py step R18RU's "npc" actions: the Compact guard
    at the HQ's ring-0 door and the one inside it, from the committed data alone. Fails closed when a conversation is
    not in data/dialogue.json with that NPC."""
    spec = spec or load()
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    convs = {c["id"]: c for c in dl["conversations"]}
    out = []
    for key in ("guard", "inside_guard"):
        g = spec["geometry"]["hq"][key]
        conv = convs.get(g["conversation"])
        if conv is None or conv.get("npc_id") != g["npc"]:
            raise RelicError("%s is not a conversation with NPC %s in data/dialogue.json" % (g["conversation"], g["npc"]))
        out.append((conv["id"], tuple(g["at"]), "%s:%s" % (NS, g["npc"]), g["yaw"]))
    return out


def placement_steps(pack_dir=None):
    """For tools/reapply.py, as step R9RU after R9DC and before R9E: hold the chunks, run the indexed block
    functions (undo, then the CAVERN pattern), release. Named from the built pack's own index, like R9DC."""
    pack_dir = Path(pack_dir or OUT)
    idx = pack_dir / "data" / NS / "function" / FOLDER / "index.txt"
    if not idx.is_file():
        raise SystemExit("no %s: run `reapply.py prepare` first" % idx)
    names = [n for n in idx.read_text(encoding="utf-8").split("\n") if n.strip()]
    hold = "%d %d %d %d" % hold_box()
    return ([("cmd", "forceload add " + hold), ("wait", 3)] +
            [("fn", "%s:%s/%s" % (NS, FOLDER, n)) for n in names] +
            [("cmd", "forceload remove " + hold)])


# --------------------------------------------------------------- verify (reads a world to CHECK)

def cmd_verify(a):
    """Read a world to CHECK the carve. Reading a world to DECIDE is what tools/ground.py replaces; reading
    it to check is still required (CLAUDE.md). This is a stub until a staging world exists: docs/STATE.md
    records that the staging worlds are gone, so there is nothing to read."""
    print("relic_underground verify: NOT IMPLEMENTED. The RCON probes in docs/world-building/RELIC_UNDERGROUND.md "
          "section 9 are the check for a live staging server. The checks a world read must make: every column of the zone's boxes at "
          "y41..y85 is solid; the hall's air matches 10_void exactly; the choked shaft holds no air; the "
          "relic ring's apex stands clear of the dome; the HQ doorway at (3421, 2..5, 3305..3307) is open; and the "
          "HQ's way down (40_hq) matches its cells: nothing beside the shut door (3443, 67, 3282), the stair from "
          "(3429, 66, 3299), the records room x3422-3428 y1-4 z3301-3310.")
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root", default=None, help="COBBLERS_SOURCE_ROOT if not in the environment")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("report").set_defaults(f=cmd_report)
    b = sub.add_parser("build")
    b.add_argument("--out", default=None)
    b.set_defaults(f=cmd_build)
    v = sub.add_parser("verify")
    v.add_argument("--world", default=None)
    v.set_defaults(f=cmd_verify)
    a = ap.parse_args(argv)
    try:
        return a.f(a)
    except RelicError as e:
        print("relic_underground: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
