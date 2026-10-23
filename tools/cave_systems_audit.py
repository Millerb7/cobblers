#!/usr/bin/env python
"""The audit of the cave systems (data/cave_systems.json, pack cobblers_cave_systems), by REPLAYING the written pack.

Written in the same session as tools/cave_systems.py because the brief asked for both (CLAUDE.md principle 16 would have a
second agent do it: say so when reporting). To keep it from agreeing with the generator by construction it takes nothing from
the generator's geometry. What it shares, and what it does not:

  reads    data/cave_systems.json (the record: rules, mouths), the pack's .mcfunction text and its index.txt, the canonical
           heightmap (tools/ground.py, round(h)), data/world.json (sea level), data/landmarks.json and tools/water_mask.py
           (the repo's definition of painted lake water), data/rivers.json, data/towns.json, data/route_paths.json,
           data/placements.json, data/regions.json (the Rift), tools/southern_residents.py authored_points (the repo's own
           reading of every x/z another data file authors) and data/spawn_blocks.json / spawn_block_policy.json
  does not import tools/cave_systems.py, ever (tests/test_cave_systems.py checks the import list)
  derives   the carved volume from the pack's `fill ... minecraft:air` lines, replayed in order with last-write times per
           cell; everything below is then recomputed from that volume and the heightmap, not from the generator's net

What it checks, per system (a PROBLEM line for each failure; exit 1):
  commands   only comments, `function`, `fill` and `setblock`; every write inside its own 192-block tile, y -64..320, x <= 4032
             (64 west of the eastern half); fill volumes and chain length (tools/function_limits.py check_lines)
  order      all the shells run before any carve; in every carve chain every carved cell is written to air, then the
             shell (water AND lava replace) covers it, then it is written to air again; the last write to a carved cell is air
  shell      every cell within two (Chebyshev) of a carved cell is covered by BOTH a water and a lava replace; no shell cell is
             more than six from a carved cell (the pack only meshes the ring in 4-blocks)
  cover      every carved cell has ground - y >= 8 and y <= ground, except within `mouth_zone` of a declared mouth where only
             y <= ground holds; the exception radius is capped here at 60 whatever the record says
  water      no carved column within 12 (Euclid) of water: the sea (heightmap at or below sea level), a landmark water_body
             basin below its level (tools/water_mask.py), a river course (distance to its graded polyline against its widest
             reach / 2)
  authored   no carved column within 32 of an authored point, a densified polyline, a footprint rectangle, the Rift region or
             an exclusion disc
  mouths     3 to 6; each a carved cell at the surface, 40 to 200 blocks from a town edge, a settlement or a route path
  walk       from the mouths, by one-block steps (up one with headroom, down three), every mouth reaches every other, at least
             95% of the standing cells are reached, and the longest shortest walk from a mouth is reported (>= 1000 required)
  caverns    at least three open volumes 30 across and 15 tall are present in the replayed volume (a flood-based measure)
  ore        every ore cell is outside the carved volume, touches it, is deepslate under y0 and stone over it, lies in its
             type's y range, has >= 4 cover; a diamond/redstone/gold/lapis ore is deepest; richer deeper and farther from a town
  light      no light source but a lantern, none farther than 60 from a mouth
  palette    nothing but air, stone, deepslate, the spec's ores and the lantern is placed; every ore that is a spawn condition has
             a data/spawn_block_policy.json whitelist entry scoped `cave_systems`
  size       six players: standing columns and ore blocks per player are reported and must exceed a floor
  traps      (2026-10-23) every standing cell the first mouth's walk reaches can walk back out of SOME mouth (the walk's step
             rules read backwards): no one-way drop into a dead end
  live       (2026-10-23) the cells of the `_air` functions are data's live_carve (count and sha256 of the sorted int32 triples):
             what is in the live world is still carved, in its own functions; every live cell is in the replayed volume; no cell
             is ADDED within the mouth zone of a mouth (the mouths stay as carved)
  nests      (2026-10-23) 2 or 3 rooms a system, each with one activated Habitat Block record (data/habitat_blocks.json, ids
             `cave_nest_`) in the floor cell under the record's centre, mimicking the floor's rock, not an ore; the record's radii
             and wall noise give 12 to 20 across; every column inside the inner bound open three high; no carved cell within 3
             of the room but the room and its spur (a dead end); nothing but the room in the spawner's box; the middle walked to
             from the first mouth; the pool in data/spawns.json with every level inside the band of the sub-region the block
             stands in (read here from data/regions.json and data/spawns.json). These blocks' own (x, z) are the only points
             excused from the authored check

What it does NOT check (CLAUDE.md "Our list is not the world"): anything outside data/ (donor templates, other built packs,
build/paint's trees and water raster, derived/routes' legs, the pending water export): none of them exists in a fresh
checkout. Not a word about behaviour in game: whether the server accepts the commands, water or lava beyond the shell,
sand and gravel falling, mobs and Pokemon spawning in the dark.

  python tools/cave_systems_audit.py [--pack DIR] [--system ID] [--json FILE]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402
import southern_residents as SR  # noqa: E402
import water_mask as WM        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "cave_systems.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_cave_systems"
FOLDER = "cave_systems"
WRITE_X = 4032                 # the brief: at least 64 west of x 4096
COVER = 8
WATER = 12
AUTHORED = 32
SHELL = 2
SHELL_MAX = 6
ZONE_CAP = 60
TILE = 192
LANTERN_REACH = 60
NEST_PREFIX = "cave_nest_"
NESTS = (2, 3)                 # the brief: 2 to 3 nest rooms a system
ROOM_ACROSS = (12, 20)         # the brief: a room 12 to 20 across, at the narrowest and widest its noisy wall can be
FILL_RE = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: replace (\S+))?$")
SET_RE = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$")
FN_RE = re.compile(r"^function cobblers:%s/(\S+)$" % FOLDER)
# entrance_trails.json, fishing_fill.json and underground_spawns.json (2026-10-22) are not places to keep clear:
# the trails END at the mouths by design, the fill is water cells, the pools are the caves' own boxes
SKIP_FILES = {"cave_systems.json", "cells.json", "regions.json", "marine_seas.json", "sculpt.json", "world.json", "spawns.json", "fishing_fill.json", "underground_spawns.json",
              "spawn_suppression.json", "entrance_trails.json", "fishing_fill.json", "underground_spawns.json"}


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ reading the pack

def read_pack(pack):
    """({function name: [lines]}, index) from a pack directory."""
    base = Path(pack) / "data" / "cobblers" / "function" / FOLDER
    fns = {}
    for f in sorted(base.glob("*.mcfunction")):
        fns[f.stem] = f.read_text(encoding="utf-8").split("\n")
    idx = [x for x in (base / "index.txt").read_text(encoding="utf-8").split("\n") if x.strip()]
    return fns, idx


def run_function(fns, name, problems, depth=0, chain=None):
    """The commands one function run executes, in order, calls expanded: [("fill", box, block, filter) | ("set", pos, block)]."""
    chain = chain if chain is not None else [0]
    out = []
    if depth > 6 or name not in fns:
        problems.append("function %s: missing or too deep" % name)
        return out
    for raw in fns[name]:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        chain[0] += 1
        m = FILL_RE.match(line)
        if m:
            v = [int(q) for q in m.groups()[:6]]
            box = (min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]), max(v[2], v[5]))
            out.append(("fill", box, m.group(7), m.group(8)))
            continue
        m = SET_RE.match(line)
        if m:
            out.append(("set", (int(m.group(1)), int(m.group(2)), int(m.group(3))), m.group(4)))
            continue
        m = FN_RE.match(line)
        if m:
            out += run_function(fns, m.group(1), problems, depth + 1, chain)
            continue
        problems.append("function %s: a command that is not a comment, function, fill or setblock: %s" % (name, line[:80]))
    return out


def split_name(name):
    sysid, tx, tz, kind = name.rsplit("_", 3)
    return sysid, int(tx), int(tz), kind


# ------------------------------------------------------------------ the data the audit reads for itself

def authored_inputs():
    """(points (N,2), rects [(x0,z0,x1,z1)], rift rings) read for the audit, apart from the generator's walker."""
    skip = {n: "audit skip" for n in SKIP_FILES}
    pts = [(p[0], p[1]) for p in SR.authored_points({"residents": [], "rules": {"authored_clearance_exempt_files": skip}}, own_file=SPEC)]
    rects = []
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)   # noqa: E731

    cmd_fill = re.compile(r"\b(?:fill|clone)\s+(-?\d+)\s+-?\d+\s+(-?\d+)\s+(-?\d+)\s+-?\d+\s+(-?\d+)")
    cmd_set = re.compile(r"\bsetblock\s+(-?\d+)\s+-?\d+\s+(-?\d+)")

    def walk(o, key=None):
        if isinstance(o, str):
            # a command written into a record (an earthwork's fill, a setblock): its box or point is authored ground too
            for m in cmd_fill.finditer(o):
                x0, z0, x1, z1 = (int(q) for q in m.groups())
                rects.append((min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)))
            for m in cmd_set.finditer(o):
                pts.append((int(m.group(1)), int(m.group(2))))
            return
        if isinstance(o, dict):
            if {"min_x", "max_x", "min_z", "max_z"} <= set(o) and all(num(o[k]) for k in ("min_x", "max_x", "min_z", "max_z")):
                rects.append((o["min_x"], o["min_z"], o["max_x"], o["max_z"]))
            for k, v in o.items():
                if isinstance(k, str) and (k.startswith("nearest_") or k in ("extent", "polygons", "basin_polygons", "outline", "vertices", "ring")):
                    continue
                walk(v, k)
        elif isinstance(o, list):
            if len(o) == 4 and all(num(v) for v in o) and key in ("box", "bbox", "footprint", "rect", "bounds", "footprint_bbox", "hold", "keep_clear",
                                                                  "boxes", "apron_rect", "cell_box", "interior", "forceload"):
                if o[2] >= o[0] and o[3] >= o[1] and o[2] - o[0] < 2000 and o[3] - o[1] < 2000:
                    rects.append(tuple(o))
            else:
                for v in o:
                    walk(v, key)
    for p in sorted((ROOT / "data").rglob("*.json")):
        rel = p.relative_to(ROOT / "data")
        if p.name in SKIP_FILES or (set(rel.parts[:-1]) & {"notes", "held", "checks"}):
            continue
        d = jload(p)
        walk(d)
        if len(rel.parts) > 1:                    # SR.authored_points reads only data/*.json: the sub-folders' points here
            pts += _points_of(d)
    # a route path is a line: add the points between its vertices (the vertices are already one block apart; a guard for the rest)
    for name, line in jload(ROOT / "data" / "route_paths.json")["paths"].items():
        for a, b in zip(line, line[1:]):
            n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])))
            for i in range(0, n + 1, 4):
                t = i / max(n, 1)
                pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    rift = [r for r in jload(ROOT / "data" / "regions.json")["regions"] if r["id"] == "the_rift"][0]["polygons"]
    # the nest rooms' own Habitat Blocks sit in the floor of rooms this pack carves: their exact (x, z) are not an authored place
    # for this check (the nest check below proves each is where a room is); nothing else is excused
    own = {(b["position"]["x"], b["position"]["z"]) for b in nest_blocks()}
    pts = [p for p in pts if (p[0], p[1]) not in own]
    return np.array(pts, float).reshape(-1, 2), rects, rift


def nest_blocks():
    """The Habitat Block records of this pack's nest rooms: ids starting `cave_nest_` in data/habitat_blocks.json."""
    return [b for b in jload(ROOT / "data" / "habitat_blocks.json")["blocks"] if str(b.get("id", "")).startswith(NEST_PREFIX)]


def cells_digest(X, Y, Z):
    """The data's live_carve definition: sha256 of int32 little-endian (x, y, z) triples sorted by x, then y, then z."""
    a = np.unique(np.stack([np.asarray(X, np.int64), np.asarray(Y, np.int64), np.asarray(Z, np.int64)], axis=1), axis=0)
    return len(a), hashlib.sha256(np.ascontiguousarray(a).astype("<i4").tobytes()).hexdigest()


def band_at(x, z):
    """(sub-region, min, max) of a point from data/regions.json polygons and data/spawns.json bands, read here for itself."""
    sp = {s["id"]: s for s in jload(ROOT / "data" / "spawns.json")["subregions"]}
    for r in jload(ROOT / "data" / "regions.json")["subregions"]:
        if r["id"] not in sp:
            continue
        for poly in r["polygons"]:
            inside, n = False, len(poly)
            for i in range(n):
                (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
                if (z0 > z) != (z1 > z) and x < x0 + (z - z0) * (x1 - x0) / (z1 - z0):
                    inside = not inside
            if inside:
                b = sp[r["id"]]["level_band"]
                return r["id"], int(b["minimum"]), int(b["maximum"])
    return None, None, None


def _points_of(d):
    out = []
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)   # noqa: E731

    def walk(o):
        if isinstance(o, dict):
            if num(o.get("x")) and num(o.get("z")):
                out.append((o["x"], o["z"]))
            for k, v in o.items():
                if not (isinstance(k, str) and k.startswith("nearest_")):
                    walk(v)
        elif isinstance(o, list):
            if len(o) == 2 and all(num(v) for v in o):
                out.append((o[0], o[1]))
            else:
                for v in o:
                    walk(v)
    walk(d)
    return out


def attractors_for_audit():
    """Where a mouth may reasonably be said to be 'near': (x, z) points of route paths, town footprint edges, settlements."""
    pts = []
    for name, line in jload(ROOT / "data" / "route_paths.json")["paths"].items():
        pts += [(p[0], p[1]) for p in line]
    for t in jload(ROOT / "data" / "towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        for x in range(f["min_x"], f["max_x"] + 1, 6):
            pts += [(x, f["min_z"]), (x, f["max_z"])]
        for z in range(f["min_z"], f["max_z"] + 1, 6):
            pts += [(f["min_x"], z), (f["max_x"], z)]
    for k, v in jload(ROOT / "data" / "placements.json")["settlements"].items():
        if "centre" in v:
            pts.append(tuple(v["centre"]))
    return np.array(pts, float)


# ------------------------------------------------------------------ geometry helpers

def box_cells(box):
    x0, y0, z0, x1, y1, z1 = box
    X, Y, Z = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1), np.arange(z0, z1 + 1), indexing="ij")
    return X.ravel(), Y.ravel(), Z.ravel()


def dilate_cube(m, r):
    out = m
    for ax in (0, 1, 2):
        acc = out.copy()
        for s in range(1, r + 1):
            a = [slice(None)] * 3
            b = [slice(None)] * 3
            a[ax] = slice(s, None)
            b[ax] = slice(None, -s)
            acc[tuple(a)] |= out[tuple(b)]
            acc[tuple(b)] |= out[tuple(a)]
        out = acc
    return out


def disc_offsets(r):
    return [(dx, dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1) if dx * dx + dz * dz <= r * r]


def near_mask(grid, ox, oz, cols_x, cols_z, r):
    """For each (cols_x, cols_z): is any True cell of `grid` (whose [0,0] is block (ox, oz)) within Euclid r. Cells outside the grid are False."""
    out = np.zeros(len(cols_x), bool)
    H, W = grid.shape
    for dx, dz in disc_offsets(r):
        ix, iz = cols_x + dx - ox, cols_z + dz - oz
        ok = (ix >= 0) & (ix < W) & (iz >= 0) & (iz < H)
        out[ok] |= grid[iz[ok], ix[ok]]
    return out


# ------------------------------------------------------------------ the audit

class Audit:
    def __init__(self, spec, pack, only=None, g=None):
        self.spec = spec
        self.rules = spec["rules"]
        self.pack = Path(pack)
        self.only = only
        self.g = g or G.Ground()
        self.problems = []
        self.report = {}
        self.H = np.asarray(self.g.heights)
        self.sea = int(jload(ROOT / "data" / "world.json")["vertical"]["sea_level"])

    def bad(self, sysid, msg):
        self.problems.append("%s: %s" % (sysid, msg))

    def ground(self, x, z):
        return np.round(self.H[z, x]).astype(np.int64)

    # -- 1. read and replay the commands
    def replay(self):
        fns, idx = read_pack(self.pack)
        self.fns, self.index = fns, idx
        pr = []
        shells = [n for n in idx if n.endswith("_shell")]
        carves = [n for n in idx if n.endswith("_carve")]
        if idx != shells + carves:
            self.problems.append("index: every shell must come before every carve (the run step reads it in order)")
        used = set()
        for name in idx:
            used.add(name)
        self.events = {}            # tile name -> events of the shell run, then the carve run
        self.tiles = {}
        clock = 0
        for name in shells + carves:
            sysid, tx, tz, kind = split_name(name)
            ev = run_function(fns, name, pr)
            for e in ev:
                clock += 1
            self.tiles.setdefault((sysid, tx, tz), {})[kind] = ev
        self.problems += pr
        for n, lines in fns.items():
            for bad in FL.check_lines(lines, n):
                self.problems.append("function_limits %s: %s" % (n, bad))
        return self

    def check_commands(self):
        T = self.rules["tile"]
        if T != TILE:
            self.problems.append("record tile %s != the audit's 192" % T)
        chain_max = 0
        for (sysid, tx, tz), kinds in self.tiles.items():
            x0, z0 = tx * TILE, tz * TILE
            for kind, ev in kinds.items():
                chain_max = max(chain_max, len(ev))
                for e in ev:
                    boxes = [e[1]] if e[0] == "fill" else [(e[1][0], e[1][1], e[1][2], e[1][0], e[1][1], e[1][2])]
                    for b in boxes:
                        if b[0] < x0 or b[3] > x0 + TILE - 1 or b[2] < z0 or b[5] > z0 + TILE - 1:
                            self.bad(sysid, "tile %d,%d %s writes %s outside its tile" % (tx, tz, kind, b))
                        if b[3] > WRITE_X:
                            self.bad(sysid, "tile %d,%d %s writes x %d, past the eastern limit %d" % (tx, tz, kind, b[3], WRITE_X))
                        if b[1] < -64 or b[4] > 320:
                            self.bad(sysid, "tile %d,%d %s writes y %d..%d outside -64..320" % (tx, tz, kind, b[1], b[4]))
        self.report["_run"] = {"longest_command_run": chain_max, "functions": len(self.fns)}
        if chain_max > FL.CHAIN_LIMIT:
            self.problems.append("a function run executes %d commands, over %d" % (chain_max, FL.CHAIN_LIMIT))

    # -- 2. the carved volume and the shell, per system
    def volume(self, sysid):
        """The cells the pack writes to air, as arrays, from the carve runs only."""
        xs, ys, zs = [], [], []
        for (s, tx, tz), kinds in self.tiles.items():
            if s != sysid:
                continue
            for e in kinds.get("carve", []):
                if e[0] == "fill" and e[2] == "minecraft:air" and e[3] is None:
                    X, Y, Z = box_cells(e[1])
                    xs.append(X)
                    ys.append(Y)
                    zs.append(Z)
        if not xs:
            return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0, np.int64)
        X, Y, Z = np.concatenate(xs), np.concatenate(ys), np.concatenate(zs)
        k = np.unique((X.astype(np.int64) * 8192 + Z) * 512 + (Y + 64))
        return (k // 512) // 8192, k % 512 - 64, (k // 512) % 8192

    def check_order_and_shell(self, sysid, X, Y, Z):
        """Replay each tile's writes in time order, with last-write times per cell."""
        n_cells = 0
        for (s, tx, tz), kinds in sorted(self.tiles.items()):
            if s != sysid:
                continue
            x0, z0 = tx * TILE, tz * TILE
            sel = (X >= x0 - SHELL_MAX) & (X < x0 + TILE + SHELL_MAX) & (Z >= z0 - SHELL_MAX) & (Z < z0 + TILE + SHELL_MAX)
            ys_all = [e[1][1] for k in kinds.values() for e in k if e[0] == "fill"] + [e[1][4] for k in kinds.values() for e in k if e[0] == "fill"]
            if sel.any():
                ys_all += [int(Y[sel].min()) - SHELL_MAX, int(Y[sel].max()) + SHELL_MAX]
            if not ys_all:
                continue
            oy = min(ys_all) - 1
            ny = max(ys_all) - oy + 2
            first_air = np.full((ny, TILE, TILE), 1 << 30, np.int32)
            last_air = np.zeros((ny, TILE, TILE), np.int32)
            last_w = np.zeros((ny, TILE, TILE), np.int32)
            last_l = np.zeros((ny, TILE, TILE), np.int32)
            t = 0
            for kind in ("shell", "carve"):
                for e in kinds.get(kind, []):
                    t += 1
                    if e[0] != "fill":
                        continue
                    b = e[1]
                    sl = (slice(b[1] - oy, b[4] - oy + 1), slice(b[2] - z0, b[5] - z0 + 1), slice(b[0] - x0, b[3] - x0 + 1))
                    if e[2] == "minecraft:air" and e[3] is None:
                        last_air[sl] = t
                        first_air[sl] = np.minimum(first_air[sl], t)
                    elif e[3] == "minecraft:water" and e[2] in ("minecraft:stone", "minecraft:deepslate"):
                        last_w[sl] = t
                    elif e[3] == "minecraft:lava" and e[2] in ("minecraft:stone", "minecraft:deepslate"):
                        last_l[sl] = t
            carved = last_air > 0
            n_cells += int(carved.sum())
            # the replay's own carved set must be the volume this audit built (a function could write air then be overwritten)
            if carved.any():
                if (last_w[carved] == 0).any() or (last_l[carved] == 0).any():
                    self.bad(sysid, "tile %d,%d: %d carved cells with no water or lava replace over them" % (tx, tz, int(((last_w == 0) | (last_l == 0))[carved].sum())))
                if (last_air[carved] <= np.maximum(last_w[carved], last_l[carved])).any():
                    self.bad(sysid, "tile %d,%d: carved cells whose last write is the shell, not air (the passage could refill)" % (tx, tz))
                if (first_air[carved] >= np.maximum(last_w[carved], last_l[carved])).any():
                    self.bad(sysid, "tile %d,%d: carved cells never written to air before the shell ran (not carve, shell, carve)" % (tx, tz))
            # coverage of the ring, with the neighbours' cells
            if sel.any():
                halo = SHELL_MAX
                arr = np.zeros((ny, TILE + 2 * halo, TILE + 2 * halo), bool)
                arr[Y[sel] - oy, Z[sel] - (z0 - halo), X[sel] - (x0 - halo)] = True
                ring = dilate_cube(arr, SHELL)[:, halo:halo + TILE, halo:halo + TILE]
                reach = dilate_cube(arr, SHELL_MAX)[:, halo:halo + TILE, halo:halo + TILE]
                both = (last_w > 0) & (last_l > 0)
                miss = ring & ~both
                if miss.any():
                    iy, iz, ix = np.nonzero(miss)
                    self.bad(sysid, "tile %d,%d: %d ring cells within %d of a carved cell are not covered by both a water and a lava replace (first %d %d %d)"
                             % (tx, tz, int(miss.sum()), SHELL, ix[0] + x0, iy[0] + oy, iz[0] + z0))
                over = ((last_w > 0) | (last_l > 0)) & ~reach
                if over.any():
                    self.bad(sysid, "tile %d,%d: %d shell cells are more than %d from any carved cell" % (tx, tz, int(over.sum()), SHELL_MAX))
            elif any(((last_w > 0) | (last_l > 0)).ravel()):
                self.bad(sysid, "tile %d,%d: a shell with no carved cell within reach" % (tx, tz))
        if n_cells != len(X):
            self.bad(sysid, "replayed carved cells %d != the carve runs' union %d (a carve is overwritten)" % (n_cells, len(X)))

    # -- 3. cover, water, authored
    def check_cover(self, sysid, X, Y, Z, mouths):
        g = self.ground(X, Z)
        cover = g - Y
        zone_r = min(self.rules["mouth_zone"], ZONE_CAP)
        inzone = np.zeros(len(X), bool)
        for m in mouths:
            inzone |= (X - m["x"]) ** 2 + (Z - m["z"]) ** 2 <= zone_r ** 2
        above = cover < 0
        if above.any():
            self.bad(sysid, "%d carved cells are above the ground (first %s)" % (int(above.sum()), (int(X[above][0]), int(Y[above][0]), int(Z[above][0]))))
        thin = (cover < COVER) & ~inzone
        if thin.any():
            i = int(np.nonzero(thin)[0][0])
            self.bad(sysid, "%d carved cells have under %d blocks of rock over them outside a mouth zone (first %d %d %d: ground y%d)"
                     % (int(thin.sum()), COVER, X[i], Y[i], Z[i], g[i]))
        self.report[sysid]["min_cover_outside_mouths"] = int(cover[~inzone].min()) if (~inzone).any() else None
        self.report[sysid]["cells_in_mouth_zones"] = int(inzone.sum())
        return cover

    def water_inputs(self, bx0, bz0, bx1, bz1):
        pad = WATER + 4
        x0, z0, x1, z1 = max(0, bx0 - pad), max(0, bz0 - pad), min(8191, bx1 + pad), min(8191, bz1 + pad)
        Hs = self.H[z0:z1 + 1, x0:x1 + 1]
        wet = Hs <= self.sea
        from PIL import Image, ImageDraw
        for bid, b in WM.bodies().items():
            if not b["basin"]:
                continue
            img = Image.new("L", (x1 - x0 + 1, z1 - z0 + 1), 0)
            d = ImageDraw.Draw(img)
            for ring in b["basin"]:
                d.polygon([(q[0] - x0, q[1] - z0) for q in ring], fill=1)
            wet |= (np.asarray(img).astype(bool)) & (np.round(Hs) < b["level_y"])
        return wet, x0, z0

    def check_water(self, sysid, X, Z):
        cols = np.unique(X.astype(np.int64) * 8192 + Z)
        cx, cz = cols // 8192, cols % 8192
        wet, ox, oz = self.water_inputs(int(cx.min()), int(cz.min()), int(cx.max()), int(cz.max()))
        hit = near_mask(wet, ox, oz, cx, cz, WATER)
        if hit.any():
            i = int(np.nonzero(hit)[0][0])
            self.bad(sysid, "%d carved columns lie within %d of sea or lake water (first %d, %d)" % (int(hit.sum()), WATER, cx[i], cz[i]))
        # rivers: the distance to each graded course's polyline against its widest reach
        worst = 1e9
        for c in jload(ROOT / "data" / "rivers.json")["courses"]:
            line = [(p[0], p[1]) for p in (c.get("graded_polyline") or [])]
            if len(line) < 2:
                continue
            half = max([r.get("width", 0) for r in (c.get("reaches") or [])] or [24]) / 2.0
            for (ax, az), (bx, bz) in zip(line, line[1:]):
                if max(ax, bx) + 60 < cx.min() or min(ax, bx) - 60 > cx.max() or max(az, bz) + 60 < cz.min() or min(az, bz) - 60 > cz.max():
                    continue
                dx, dz = bx - ax, bz - az
                L2 = dx * dx + dz * dz or 1.0
                t = np.clip(((cx - ax) * dx + (cz - az) * dz) / L2, 0, 1)
                d = np.hypot(cx - (ax + t * dx), cz - (az + t * dz))
                worst = min(worst, float((d - half).min()))
        self.report[sysid]["nearest_river_edge_blocks"] = None if worst > 1e8 else round(worst, 1)
        if worst < WATER:
            self.bad(sysid, "a carved column is %.1f from a river course's edge (needs %d)" % (worst, WATER))
        sea_d = None
        self.report[sysid]["columns_checked_for_water"] = int(len(cols))

    def check_authored(self, sysid, X, Z):
        pts, rects, rift = self._auth
        cols = np.unique(X.astype(np.int64) * 8192 + Z)
        cx, cz = cols // 8192, cols % 8192
        x0, z0, x1, z1 = int(cx.min()) - 40, int(cz.min()) - 40, int(cx.max()) + 40, int(cz.max()) + 40
        occ = np.zeros((z1 - z0 + 1, x1 - x0 + 1), bool)
        occ[cz - z0, cx - x0] = True
        sel = pts[(pts[:, 0] >= x0 - AUTHORED) & (pts[:, 0] <= x1 + AUTHORED) & (pts[:, 1] >= z0 - AUTHORED) & (pts[:, 1] <= z1 + AUTHORED)]
        closest = 1e9
        first = None
        offs = [(dx, dz) for dx in range(-AUTHORED, AUTHORED + 1) for dz in range(-AUTHORED, AUTHORED + 1) if dx * dx + dz * dz < AUTHORED * AUTHORED]
        offs_a = np.array(offs)
        for (px, pz) in sel:
            ix, iz = int(round(px)) - x0, int(round(pz)) - z0
            zz = iz + offs_a[:, 1]
            xx = ix + offs_a[:, 0]
            ok = (zz >= 0) & (zz < occ.shape[0]) & (xx >= 0) & (xx < occ.shape[1])
            if occ[zz[ok], xx[ok]].any():
                first = first or (float(px), float(pz))
                closest = 0
                break
        if first:
            self.bad(sysid, "a carved column is within %d of the authored point %s" % (AUTHORED, first))
        bad_rects = 0
        for (rx0, rz0, rx1, rz1) in rects:
            if rx1 + AUTHORED < x0 or rx0 - AUTHORED > x1 or rz1 + AUTHORED < z0 or rz0 - AUTHORED > z1:
                continue
            dx = np.maximum(np.maximum(rx0 - cx, cx - rx1), 0)
            dz = np.maximum(np.maximum(rz0 - cz, cz - rz1), 0)
            if (np.hypot(dx, dz) < AUTHORED).any():
                bad_rects += 1
                if bad_rects == 1:
                    self.bad(sysid, "a carved column is within %d of the footprint rectangle %s" % (AUTHORED, (rx0, rz0, rx1, rz1)))
        from PIL import Image, ImageDraw
        img = Image.new("L", (x1 - x0 + 1, z1 - z0 + 1), 0)
        d = ImageDraw.Draw(img)
        for ring in rift:
            d.polygon([(q[0] - x0, q[1] - z0) for q in ring], fill=1)
        if near_mask(np.asarray(img).astype(bool), x0, z0, cx, cz, AUTHORED).any():
            self.bad(sysid, "a carved column is within %d of the Rift region" % AUTHORED)
        for ex in self.rules.get("exclusion_discs", []):
            if (np.hypot(cx - ex["x"], cz - ex["z"]) < ex["r"]).any():
                self.bad(sysid, "a carved column is inside the exclusion disc %s" % ex)
        self.report[sysid]["authored_points_in_range"] = int(len(sel))

    # -- 4. mouths, walk, caverns
    def check_mouths(self, sysid, X, Y, Z, mouths):
        if not 3 <= len(mouths) <= 6:
            self.bad(sysid, "%d mouths (3 to 6 wanted)" % len(mouths))
        A = self._attr
        cellset = set(zip(X.tolist(), Y.tolist(), Z.tolist()))
        out = []
        for m in mouths:
            gy = int(self.ground(np.array([m["x"]]), np.array([m["z"]]))[0])
            cols = [(x, z) for x in range(m["x"] - 2, m["x"] + 3) for z in range(m["z"] - 2, m["z"] + 3)]
            surf = [(x, z) for (x, z) in cols if (x, int(self.ground(np.array([x]), np.array([z]))[0]), z) in cellset]
            if not surf:
                self.bad(sysid, "mouth %s (%d, %d) has no carved cell at the surface (ground y%d)" % (m["id"], m["x"], m["z"], gy))
            d = float(np.hypot(A[:, 0] - m["x"], A[:, 1] - m["z"]).min())
            out.append({"id": m["id"], "x": m["x"], "z": m["z"], "ground_y": gy, "nearest_town_route_or_settlement": round(d)})
            if not 40 <= d <= 200:
                self.bad(sysid, "mouth %s is %.0f blocks from the nearest town edge, settlement or route path (40 to 200 wanted)" % (m["id"], d))
        self.report[sysid]["mouths"] = out

    def check_walk(self, sysid, X, Y, Z, mouths):
        cells = set(zip(X.tolist(), Y.tolist(), Z.tolist()))
        stand = set()
        for (x, y, z) in cells:
            if (x, y + 1, z) in cells and (x, y - 1, z) not in cells:
                stand.add((x, y, z))
        starts = []
        for m in mouths:
            c = [p for p in stand if abs(p[0] - m["x"]) <= 3 and abs(p[2] - m["z"]) <= 3]
            if not c:
                self.bad(sysid, "mouth %s: nowhere to stand within 3 of it" % m["id"])
                starts.append(None)
            else:
                starts.append(max(c, key=lambda p: p[1]))
        def bfs(src):
            dist = {src: 0}
            q = deque([src])
            while q:
                x, y, z = q.popleft()
                d = dist[(x, y, z)]
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    for dy in (0, 1, -1, -2, -3):
                        p = (x + dx, y + dy, z + dz)
                        if p in dist or p not in stand:
                            continue
                        if dy == 1 and (x, y + 2, z) not in cells:
                            continue
                        if dy < 0 and not ((x + dx, y + 1, z + dz) in cells):
                            continue
                        dist[p] = d + 1
                        q.append(p)
                        break
            return dist
        live = [s for s in starts if s]
        if not live:
            return
        dist = bfs(live[0])
        for m, s in zip(mouths, starts):
            if s and s not in dist:
                self.bad(sysid, "mouth %s cannot be walked to from mouth %s" % (m["id"], mouths[starts.index(live[0])]["id"]))
        frac = len(dist) / max(1, len(stand))
        far = max(dist.values()) if dist else 0
        cols = {(p[0], p[2]) for p in dist}
        self.report[sysid].update({"standing_cells": len(stand), "reachable_standing_fraction": round(frac, 4), "longest_walk_from_mouth_0": far,
                                   "reachable_floor_columns": len(cols)})
        if frac < 0.95:
            self.bad(sysid, "only %.1f%% of the standing cells can be walked to from the first mouth" % (100 * frac))
        if far < 1000:
            self.bad(sysid, "the longest walk from a mouth is %d steps (1000 wanted)" % far)
        self._standing = {(p[0], p[1], p[2]) for p in dist}
        return dist

    def check_caverns(self, sysid, X, Y, Z):
        """Cavern volumes from the replayed cells alone: connected columns carved 8 or more high (a passage is at most 7 high), whose
        footprint is at least 24 across both ways, with a column at least 15 high and 300 columns or more."""
        H = {}
        for x, y, z in zip(X.tolist(), Y.tolist(), Z.tolist()):
            H[(x, z)] = H.get((x, z), 0) + 1
        tall = {k for k, v in H.items() if v >= 8}
        big = 0
        seen = set()
        for k0 in sorted(tall):
            if k0 in seen:
                continue
            comp = [k0]
            seen.add(k0)
            q = deque([k0])
            while q:
                a_, b_ = q.popleft()
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    p = (a_ + dx, b_ + dz)
                    if p in tall and p not in seen:
                        seen.add(p)
                        comp.append(p)
                        q.append(p)
            xs = [c[0] for c in comp]
            zs = [c[1] for c in comp]
            if len(comp) >= 300 and max(xs) - min(xs) >= 24 and max(zs) - min(zs) >= 24 and max(H[c] for c in comp) >= 15:
                big += 1
        self.report[sysid]["cavern_like_volumes"] = big
        if big < 3:
            self.bad(sysid, "only %d cavern-like volumes (8+ high columns, 24+ across, one 15+ high); 3 wanted" % big)

    # -- 5. ore, light, palette
    def check_dress(self, sysid, X, Y, Z, mouths):
        cells = set(zip(X.tolist(), Y.tolist(), Z.tolist()))
        types = {}
        for t in self.rules["ore"]["types"]:
            types[t["stone"]] = t
            types[t["deepslate"]] = t
        ore, lanterns, odd = [], [], set()
        for (s, tx, tz), kinds in self.tiles.items():
            if s != sysid:
                continue
            for e in kinds.get("carve", []):
                if e[0] == "set":
                    if e[2].startswith("minecraft:lantern"):
                        lanterns.append(e[1])
                    else:
                        odd.add(e[2])
                elif e[0] == "fill" and e[2] in types and e[3] == "#minecraft:base_stone_overworld":
                    b = e[1]
                    if b[0:3] != b[3:6]:
                        self.bad(sysid, "an ore fill that is not one cell: %s" % (b,))
                    ore.append((b[0], b[1], b[2], e[2]))
                elif e[0] == "fill" and e[2] in ("minecraft:air", "minecraft:stone", "minecraft:deepslate"):
                    pass
                else:
                    odd.add(e[2])
        if odd:
            self.bad(sysid, "blocks placed that are not air, stone, deepslate, a spec ore or a lantern: %s" % sorted(odd)[:6])
        # light: lanterns only, near mouths, on the floor
        for (x, y, z) in lanterns:
            if min(math.hypot(x - m["x"], z - m["z"]) for m in mouths) > LANTERN_REACH:
                self.bad(sysid, "a lantern at %s is more than %d from every mouth" % ((x, y, z), LANTERN_REACH))
            if (x, y, z) not in cells or (x, y - 1, z) in cells:
                self.bad(sysid, "a lantern at %s is not on a floor cell of the carved volume" % ((x, y, z),))
        self.report[sysid]["lanterns"] = len(lanterns)
        # ore
        per = {}
        bad_n = 0
        for (x, y, z, b) in ore:
            t = types[b]
            want = t["deepslate"] if y < 0 else t["stone"]
            msgs = []
            if b != want:
                msgs.append("wrong variant for y%d" % y)
            if not t["y_min"] <= y <= t["y_max"]:
                msgs.append("outside its y range")
            if (x, y, z) in cells:
                msgs.append("inside the carved volume")
            if not any((x + dx, y + dy, z + dz) in cells for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))):
                msgs.append("not exposed")
            if int(self.ground(np.array([x]), np.array([z]))[0]) - y < 4:
                msgs.append("under 4 of cover")
            if msgs:
                bad_n += 1
                if bad_n <= 3:
                    self.bad(sysid, "ore %s at %s: %s" % (b, (x, y, z), ", ".join(msgs)))
            per[b] = per.get(b, 0) + 1
        if bad_n > 3:
            self.bad(sysid, "%d ore cells in all break a rule" % bad_n)
        self.report[sysid]["ore_blocks"] = len(ore)
        self.report[sysid]["ore_by_block"] = per
        # richer deeper and farther: ore blocks per 1000 EXPOSED WALL cells (a rock cell touching the carved volume, 4 or more under the
        # surface), by depth below the surface and by distance from the nearest town
        key = (X.astype(np.int64) * 8192 + Z) * 512 + (Y + 64)
        key.sort()
        nb = np.unique(np.concatenate([key + d for d in (1, -1, 512, -512, 512 * 8192, -512 * 8192)]))
        pos = np.searchsorted(key, nb)
        pos[pos >= len(key)] = len(key) - 1
        wall = nb[key[pos] != nb]
        wy = wall % 512 - 64
        wz = (wall // 512) % 8192
        wx = (wall // 512) // 8192
        wc = self.ground(wx, wz) - wy
        keep = wc >= 4
        wx, wy, wz, wc = wx[keep], wy[keep], wz[keep], wc[keep]
        oc = (self.ground(np.array([o[0] for o in ore]), np.array([o[2] for o in ore])) - np.array([o[1] for o in ore])) if ore else np.zeros(0)
        bands = ((0, 45), (45, 90), (90, 1000))
        dens = {}
        for lo, hi in bands:
            n_o = int(((oc >= lo) & (oc < hi)).sum())
            n_w = int(((wc >= lo) & (wc < hi)).sum())
            dens["%d..%d under the surface" % (lo, hi)] = [n_o, n_w, round(1000.0 * n_o / max(1, n_w), 2)]
        self.report[sysid]["ore_per_1000_wall_cells_by_depth"] = dens
        d = [v[2] for v in dens.values()]
        if dens[list(dens)[0]][1] > 2000 and dens[list(dens)[-1]][1] > 2000 and not (d[-1] >= 1.2 * d[0]):
            self.bad(sysid, "ore is not clearly richer deep under the surface than shallow (the deepest band should hold 1.2 times the shallowest's density): %s" % dens)
        tw = [(t["centre"]["x"], t["centre"]["z"]) for t in jload(ROOT / "data" / "towns.json")["towns"] if (t.get("centre") or {}).get("x") is not None]
        if ore and tw:
            ox = np.array([o[0] for o in ore])
            oz = np.array([o[2] for o in ore])
            dt = np.min([np.hypot(ox - a, oz - b) for a, b in tw], axis=0)
            dw = np.min([np.hypot(wx - a, wz - b) for a, b in tw], axis=0)
            med = float(np.median(dw))
            near = [int((dt < med).sum()), int((dw < med).sum())]
            far = [int((dt >= med).sum()), int((dw >= med).sum())]
            self.report[sysid]["ore_per_1000_wall_cells_nearer_then_farther_than_median_town_distance"] = [
                round(med), round(1000.0 * near[0] / max(1, near[1]), 2), round(1000.0 * far[0] / max(1, far[1]), 2)]
        # palette: spawn-condition ores need the policy entry
        sb = set(jload(ROOT / "data" / "spawn_blocks.json")["blocks"])
        policy = jload(ROOT / "data" / "spawn_block_policy.json")
        allowed = {b for w in policy["whitelist"] if "cave_systems" in (w.get("scope") or "") for b in w["blocks"]}
        for b in sorted({o[3] for o in ore} & sb - allowed):
            self.bad(sysid, "places %s, a spawn condition (data/spawn_blocks.json), with no data/spawn_block_policy.json entry scoped cave_systems" % b)
        self.report[sysid]["ore_spawn_blocks_policy_covered"] = sorted({o[3] for o in ore} & sb)
        return ore

    # -- 6. the live carve: the 2026-10-22 cells are still carved, in their own functions, and nothing was added at a mouth
    def check_live(self, sysid, X, Y, Z, mouths):
        rec = ((self.spec.get("live_carve") or {}).get("systems") or {}).get(sysid)
        if not rec:
            self.bad(sysid, "data/cave_systems.json live_carve has no record: what is in the world cannot be checked")
            return None
        xs, ys, zs = [], [], []
        for name, lines in self.fns.items():
            if not (name.startswith(sysid + "_") and name.endswith("_air")):
                continue
            for raw in lines:
                m = FILL_RE.match(raw.strip())
                if m and m.group(7) == "minecraft:air" and m.group(8) is None:
                    v = [int(q) for q in m.groups()[:6]]
                    a, b_, c = box_cells((min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]), max(v[2], v[5])))
                    xs.append(a)
                    ys.append(b_)
                    zs.append(c)
        if not xs:
            self.bad(sysid, "no `_air` function carves anything: the live carve is not in the pack")
            return None
        LX, LY, LZ = np.concatenate(xs), np.concatenate(ys), np.concatenate(zs)
        n, dg = cells_digest(LX, LY, LZ)
        self.report[sysid]["live_cells"] = n
        if n != rec["cells"] or dg != rec["sha256"]:
            self.bad(sysid, "the `_air` functions carve %d cells (sha256 %s...), not the live carve's %d (%s...): the pack no longer carves "
                            "what is in the world" % (n, dg[:12], rec["cells"], rec["sha256"][:12]))
        key = (X.astype(np.int64) * 8192 + Z) * 512 + (Y + 64)
        lk = np.unique((LX.astype(np.int64) * 8192 + LZ) * 512 + (LY + 64))
        isin = np.isin(lk, key)
        if not isin.all():
            self.bad(sysid, "%d live cells are not carved by the replayed pack (a re-run would leave them as they are, but the pack "
                            "no longer describes the world)" % int((~isin).sum()))
        added = ~np.isin(key, lk)
        self.report[sysid]["added_cells"] = int(added.sum())
        zone_r = min(self.rules["mouth_zone"], ZONE_CAP)
        for m in mouths:
            hit = added & ((X - m["x"]) ** 2 + (Z - m["z"]) ** 2 <= zone_r ** 2)
            if hit.any():
                self.bad(sysid, "%d cells added inside mouth %s's zone (the mouths stay as carved)" % (int(hit.sum()), m["id"]))
        return added

    # -- 7. the nest rooms: one activated Habitat Block in each room's floor, the room whole and a dead end off its spur
    def check_nests(self, sysid, sysspec, X, Y, Z, ore):
        rooms = sysspec.get("nest_rooms") or []
        self.report[sysid]["nest_rooms"] = []
        if not NESTS[0] <= len(rooms) <= NESTS[1]:
            self.bad(sysid, "%d nest rooms (%d to %d wanted)" % (len(rooms), NESTS[0], NESTS[1]))
        blocks = {b["id"]: b for b in jload(ROOT / "data" / "habitat_blocks.json")["blocks"]}
        habs = {h["id"]: h for h in jload(ROOT / "data" / "spawns.json")["habitats"]}
        cells = set(zip(X.tolist(), Y.tolist(), Z.tolist()))
        ores = {(o[0], o[1], o[2]) for o in ore}
        mine = [b for b in blocks.values() if str(b["id"]).startswith(NEST_PREFIX + sysid + "_")]
        if len(mine) != len(rooms):
            self.bad(sysid, "%d nest Habitat Blocks for %d rooms" % (len(mine), len(rooms)))
        dist = getattr(self, "_dist", {}) or {}
        for r in rooms:
            rid = r["id"]
            b = blocks.get(rid + "_block")
            if b is None:
                self.bad(sysid, "%s: no Habitat Block record %s_block" % (rid, rid))
                continue
            bx, by, bz = (b["position"][k] for k in "xyz")
            cx, yf, cz = r["centre"]
            a, bb = r["radius"]
            ang, tall, wn = r["angle"], int(r["tall"]), float(r["wall_noise"])
            (sx, _sy, sz), (ex, _ey, ez) = r["spur"]
            hw = r["spur_width"] / 2.0
            row = {"id": rid, "block": [bx, by, bz], "pool": b["pool"]}
            msgs = []
            if (bx, bz) != (cx, cz) or by != yf - 1:
                msgs.append("the block %s is not the floor cell under the room's middle %s" % ((bx, by, bz), (cx, yf - 1, cz)))
            if b.get("style") != "activated" or b.get("replace_spawns") is not False:
                msgs.append("not an activated, non-replacing block")
            if b.get("mimic") != ("minecraft:deepslate" if by < 0 else "minecraft:stone"):
                msgs.append("mimic %s is not the floor's rock" % b.get("mimic"))
            if (bx, by, bz) in cells or (bx, by + 1, bz) not in cells or (bx, by + 2, bz) not in cells:
                msgs.append("the block is not a rock cell under two open cells")
            if (bx, by, bz) in ores:
                msgs.append("an ore is written at the block")
            # across, from the record's own radii and wall noise: the narrowest and widest the noisy wall can make it
            lo_, hi_ = 2 * min(a, bb) * (1 - wn), 2 * max(a, bb) * (1 + wn)
            row["across_bounds"] = [round(lo_, 1), round(hi_, 1)]
            if lo_ < ROOM_ACROSS[0] - 1e-6 or hi_ > ROOM_ACROSS[1] + 1e-6:
                msgs.append("its radii and wall noise allow %.1f to %.1f across, not %d to %d" % (lo_, hi_, ROOM_ACROSS[0], ROOM_ACROSS[1]))
            # classify every carved cell near the room: inside the room's outer bound, or in the spur's corridor, or foreign
            ca, sa = math.cos(ang), math.sin(ang)
            reach = int(math.ceil(max(a, bb) * (1 + wn))) + 4
            near = [(x, y, z) for x in range(cx - reach, cx + reach + 1) for z in range(cz - reach, cz + reach + 1)
                    for y in range(yf - 4, yf + tall + 4) if (x, y, z) in cells]

            def rho(x, z):
                u = ((x - cx) * ca + (z - cz) * sa) / a
                v = (-(x - cx) * sa + (z - cz) * ca) / bb
                return math.sqrt(u * u + v * v)

            def in_spur(x, z):
                dx, dz = ex - sx, ez - sz
                L2 = dx * dx + dz * dz or 1.0
                t = max(0.0, min(1.0, ((x - sx) * dx + (z - sz) * dz) / L2))
                return math.hypot(x - (sx + t * dx), z - (sz + t * dz)) <= hw + 1e-9

            def own(x, y, z):
                return ((yf <= y < yf + tall and rho(x, z) <= 1 / (1 - wn))
                        or (yf <= y < yf + int(r["spur_height"]) and in_spur(x, z)))
            # "within 3 of the room", taken from below so a room that keeps 3 clear always passes: the room certainly holds its
            # inner bound (rho < 1 / (1 + wn)) at least three high (yf..yf+2); the inner ellipse scaled by 1 + 3 / its larger radius
            # is within 3 of it, and so are the cells from three under its floor to three over its third cell
            lim = 1 / (1 + wn) + 3.0 / max(a, bb)
            foreign = [c for c in near if not own(*c) and yf - 3 <= c[1] <= yf + 5 and rho(c[0], c[2]) <= lim]
            if foreign:
                msgs.append("%d carved cells within 3 of the room are neither room nor spur (first %s): the room is not a dead end"
                            % (len(foreign), foreign[0]))
            inner_miss = [(x, z) for x in range(cx - reach, cx + reach + 1) for z in range(cz - reach, cz + reach + 1)
                          if rho(x, z) < 1 / (1 + wn) and not ((x, yf, z) in cells and (x, yf + 1, z) in cells and (x, yf + 2, z) in cells)]
            if inner_miss:
                msgs.append("%d columns inside the room's inner bound are not open three high (first %s)" % (len(inner_miss), inner_miss[0]))
            sr = int(b["activated"]["spawn_range"])
            box_foreign = [c for c in near if abs(c[0] - bx) <= sr and abs(c[1] - by) <= sr and abs(c[2] - bz) <= sr
                           and not own(*c)]
            if box_foreign:
                msgs.append("the spawn box (spawn_range %d) holds %d carved cells outside the room" % (sr, len(box_foreign)))
            if dist and (bx, by + 1, bz) not in dist:
                msgs.append("the room's middle cannot be walked to from the first mouth")
            pid = str(b["pool"]).split(":", 1)[-1]
            h = habs.get(pid)
            sub, lo, hi = band_at(bx, bz)
            row.update({"subregion": sub, "band": [lo, hi]})
            if h is None or not h.get("entries"):
                msgs.append("pool %s is not in data/spawns.json habitats, or is empty" % pid)
            else:
                row["species"] = ["%s %s" % (e["pokemon"], e["level"]) for e in h["entries"]]
                for e in h["entries"]:
                    lv = [int(q) for q in str(e["level"]).split("-")]
                    if lo is None or min(lv) < lo or max(lv) > hi:
                        msgs.append("%s at %s is outside the band of %s (%s-%s)" % (e["pokemon"], e["level"], sub, lo, hi))
            others = [o for o in blocks.values() if o is not b and abs(o["position"]["x"] - bx) <= reach and abs(o["position"]["z"] - bz) <= reach
                      and abs(o["position"]["y"] - by) <= reach]
            if others:
                msgs.append("another Habitat Block is in the room: %s" % others[0]["id"])
            for q in msgs:
                self.bad(sysid, "nest %s: %s" % (rid, q))
            self.report[sysid]["nest_rooms"].append(row)
        for i, r in enumerate(rooms):
            for s in rooms[i + 1:]:
                d = math.hypot(r["centre"][0] - s["centre"][0], r["centre"][2] - s["centre"][2])
                if d < self.rules["nests"]["spacing"]:
                    self.bad(sysid, "nests %s and %s are %.0f apart (%d wanted)" % (r["id"], s["id"], d, self.rules["nests"]["spacing"]))

    def check_traps(self, sysid, X, Y, Z, mouths):
        """Every standing cell the first mouth's walk reaches can walk back out of SOME mouth (a one-way drop into a dead end is a
        softlock). The step rules are check_walk's, read backwards."""
        cells = set(zip(X.tolist(), Y.tolist(), Z.tolist()))
        stand = {(x, y, z) for (x, y, z) in cells if (x, y + 1, z) in cells and (x, y - 1, z) not in cells}
        rev = {}
        for (x, y, z) in stand:
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for dy in (0, 1, -1, -2, -3):
                    p = (x + dx, y + dy, z + dz)
                    if p not in stand:
                        continue
                    if dy == 1 and (x, y + 2, z) not in cells:
                        continue
                    if dy < 0 and (x + dx, y + 1, z + dz) not in cells:
                        continue
                    rev.setdefault(p, []).append((x, y, z))
                    break
        out = set()
        for m in mouths:
            c = [p for p in stand if abs(p[0] - m["x"]) <= 3 and abs(p[2] - m["z"]) <= 3]
            if c:
                out.add(max(c, key=lambda p: p[1]))
        q = deque(out)
        while q:
            c = q.popleft()
            for a in rev.get(c, ()):
                if a not in out:
                    out.add(a)
                    q.append(a)
        reached = getattr(self, "_standing", set())
        trapped = [p for p in reached if p not in out]
        self.report[sysid]["trapped_standing_cells"] = len(trapped)
        if trapped:
            self.bad(sysid, "%d standing cells can be walked to but no mouth can be walked back to from them (first %s)" % (len(trapped), min(trapped)))

    # -- the whole run
    def run(self):
        self.replay()
        self.check_commands()
        self._auth = authored_inputs()
        self._attr = attractors_for_audit()
        for s in self.spec["systems"]:
            sysid = s["id"]
            if self.only and sysid != self.only:
                continue
            self.report[sysid] = {}
            X, Y, Z = self.volume(sysid)
            if not len(X):
                self.bad(sysid, "the pack carves nothing")
                continue
            self.report[sysid]["carved_cells"] = int(len(X))
            self.report[sysid]["bounds"] = [int(X.min()), int(Y.min()), int(Z.min()), int(X.max()), int(Y.max()), int(Z.max())]
            if int(X.max()) > self.rules["east_limit_x"] + 1:
                self.bad(sysid, "carves x %d, past the record's own east limit %d" % (int(X.max()), self.rules["east_limit_x"]))
            if int(X.max()) > WRITE_X:
                self.bad(sysid, "carves x %d, within 64 of x 4096" % int(X.max()))
            self.check_order_and_shell(sysid, X, Y, Z)
            self.check_cover(sysid, X, Y, Z, s["mouths"])
            self.check_water(sysid, X, Z)
            self.check_authored(sysid, X, Z)
            self.check_mouths(sysid, X, Y, Z, s["mouths"])
            self._standing = set()
            self._dist = self.check_walk(sysid, X, Y, Z, s["mouths"])
            self.check_traps(sysid, X, Y, Z, s["mouths"])
            self.check_caverns(sysid, X, Y, Z)
            ore = self.check_dress(sysid, X, Y, Z, s["mouths"])
            self.check_live(sysid, X, Y, Z, s["mouths"])
            self.check_nests(sysid, s, X, Y, Z, ore or [])
            rp = self.report[sysid]
            if rp.get("reachable_floor_columns", 0) < 6 * 1500:
                self.bad(sysid, "only %s reachable floor columns: under 1500 per player for six players" % rp.get("reachable_floor_columns"))
            if rp.get("ore_blocks", 0) < 6 * 150:
                self.bad(sysid, "only %s ore blocks: under 150 per player for six players" % rp.get("ore_blocks"))
        return self.problems, self.report


def audit(spec=None, pack=PACK, only=None, g=None):
    return Audit(spec or jload(SPEC), pack, only, g).run()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default=str(PACK))
    p.add_argument("--system")
    p.add_argument("--json")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    p.add_argument("--source-root")
    a = p.parse_args(argv)
    if not (Path(a.pack) / "data").is_dir():
        raise SystemExit("no pack at %s: run python tools/cave_systems.py build first" % a.pack)
    problems, report = audit(jload(SPEC), a.pack, a.system)
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for sid, r in [(k, v) for k, v in report.items() if not k.startswith("_")]:
        print("%-13s %s cells, walk %s, standing %s (%s reached), floor columns %s, ore %s, mouths %d, cover min %s"
              % (sid, r.get("carved_cells"), r.get("longest_walk_from_mouth_0"), r.get("standing_cells"), r.get("reachable_standing_fraction"),
                 r.get("reachable_floor_columns"), r.get("ore_blocks"), len(r.get("mouths", [])), r.get("min_cover_outside_mouths")))
    for pr in problems[:60]:
        print("PROBLEM:", pr)
    print("cave_systems_audit: %d system(s), %d problem(s)" % (len([k for k in report if not k.startswith("_")]), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
