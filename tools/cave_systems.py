#!/usr/bin/env python
"""The cave systems (the owner, 2026-10-21): huge natural underground passages for the western half of the map, from
data/cave_systems.json. "With no caves people won't be incentivized to mine at all ... i need some to be thousands long".

The world is a pre-exported WorldPainter world with essentially no natural caves, and the cave kits are a hundred blocks each
(tools/caves.py mode `natural`, tools/mining_caves.py, tools/route1_old_mine.py). A SYSTEM here is a network of winding passages
three to seven wide, a few thousand blocks of centreline in all, with caverns thirty to eighty across and fifteen to forty tall,
several levels joined by slopes, dead-end side branches, loops where two branches meet, three to six surface mouths near towns
or routes, and vanilla ore (the ores the bank buys) in the exposed walls, richer deeper and farther from a town. Dark by design:
the only light is a few lanterns at the mouths.

THE PIPELINE (the house pattern: data -> generator -> function pack -> offline audit -> a tools/reapply.py step)

  data/cave_systems.json     rules, levels, ore table and each system's seed, centre, radius, mouths and cavern count
  tools/cave_systems.py      this file: plan, carve, dress, write build/datapacks/cobblers_cave_systems
  tools/cave_systems_audit.py  the independent replay of the written pack against the heightmap and the data
  tools/reapply.py           prepare job `cave_systems:build` + `cave_systems_audit`; run step R9CS (never run tonight)

  python tools/cave_systems.py site [<system id>]   free ground and candidate mouths near towns; nothing written
  python tools/cave_systems.py report [<id>]        plan every system, print its numbers; nothing written
  python tools/cave_systems.py build                -> build/datapacks/cobblers_cave_systems, derived/cave_systems/plan.json
  python tools/cave_systems.py map                  -> docs/world-building/cave_systems/*.png (one per system and the west map)

HOW A SYSTEM IS MADE (deterministic: every random choice is a seeded FNV hash, as tools/mines.py h32 does)

  1. region      the heightmap box round the centre (tools/ground.py, round(h), never a world) and the BLOCKED grid: every column
                 within 32 (+4 slack) of an authored point, footprint, route, command-written box or the Rift, within 12 (+4) of
                 water (the sea, a lake basin, a river course), inside an exclusion disc, or past the east limit (the eastern half
                 belongs to another builder: every write stays at x <= 4032, the carve at x <= 4000)
  2. network     from each mouth a passage enters the hill (the direction nearest the centre in which a 0.5 ramp stays under the
                 ground) and winds on (turning is an Ornstein-Uhlenbeck walk), forks into side branches that dead-end or loop back
                 where two meet, and slopes (<= 0.5) to the next level (levels are picked from how far each is short of its share).
                 A step is taken only if the next 22 blocks keep clear of blocked ground and keep 3 blocks more rock than the audit
                 asks for. Separate pieces (one per mouth, as a rule) are then joined by an A* route over free ground with a height
                 profile held under the cover cap and at most 0.45 steep, kept clear of passages it could cut a ledge in
  3. caverns     placed on nodes of the network with room for them; the nodes near one are blended to its floor so no passage
                 meets it at a drop; a cavern is refused if another level's passage would cross its volume
  4. voxels      every segment is swept as a flat-floored superellipse (width 3-7 by headroom 4-7, noisy walls); every cell is
                 clipped to: not blocked, >= 8 of rock above it except inside a mouth zone, above the floor limit; cells that
                 do not connect to a mouth are dropped; a floor that can only be reached by climbing two or more is lowered
  5. walk        the result is walked from every mouth (one-block steps: up one with headroom, down three). A seed that leaves a
                 mouth or 1% of the floor out of reach is rejected and the next seed tried, in a fixed order, up to 8; the system
                 fails closed if none walks (the audit then walks the written pack again, independently)
  6. dress       ore in exposed wall cells as small veins (richer deeper under the surface and farther from a town); lanterns at
                 the mouths
  7. pack        per 192-block tile (12x12 chunks): one function that is only the SHELL (every water and lava block within
                 two cells of any carved cell, and in it, becomes stone/deepslate), run for every tile first; and one that
                 CARVES (air), runs the shell function again, carves AGAIN so the shell cannot refill the passage, then
                 places the ore and lanterns. The shell goes first everywhere so no pocket beside a tile edge can flood a
                 passage that is already open (Groudon's cavern was flooded from pockets in the rock: docs/STATE.md)

  2026-10-23, ADDITIVE over the live carve (steps 1-7 are the "base", carved into the live world on 2026-10-22 by R9CS):
  8. live        the base must reproduce data/cave_systems.json live_carve cell for cell (count and sha256), or the build fails
                 closed: a re-plan would carve a second network over the one in the world. A data change within the plan's
                 reach (an authored point within 36 of a passage, water, the heightmap) is exactly such a re-plan
  9. widen       the owner: "make some of the caves tunnels wider span from 3-15 blocks wide". Every node gets a width from a
                 smooth seeded field ranked over the system (rules.widen): the narrowest share keep their width (the squeezes),
                 most go 5.5 to 9.5, the top quarter 9.5 to 15; capped so another passage keeps 3 of rock; headroom up to 12.
                 Added cells only, under the rules in the comment above cells_digest (cover 8 everywhere, nothing in a mouth zone,
                 decks never opened into each other, the walk and the TRAP check). The pack carves base cells in `_air` (the live
                 lines) and the added ones in `_wide`, both before and after the shell
  10. nests      2 or 3 nest rooms a system (rules.nests), sited once by `nests --site` into systems[].nest_rooms: a straight spur
                 off a branch into an elliptical room 12 to 20 across, a dead end; one activated Habitat Block in the floor under
                 the middle, its record and pool written by `nests --write` through tools/nest_rooms.py. The block is placed by
                 R9E after R9CS (tools/habitat_blocks.py: mimic first, then one setblock with the whole entity); nothing here
                 data-merges or force-loads one to read it back (docs/STATE.md, the 2026-10-20 crash)

  python tools/cave_systems.py nests --site [--write --jar <Cobblemon jar>]   site the rooms / write their records (data/ only)

WHAT THIS DOES NOT COVER (CLAUDE.md "Our list is not the world")
  - Only what is in data/ is kept clear of. The world also holds what donor templates, mods and earlier passes put there. Nothing
    reads build/datapacks (the other packs' writes), derived/routes (the routed legs), build/paint (painted trees and the painted
    water raster) or derived/water_shape/changed.npy: none of them exists in a fresh worktree. Water is the heightmap at or below
    sea level, every landmark water_body basin polygon, and every graded river course with its widest reach as half-width.
    A pond or tarn that is a built feature of another tool and is not in a landmark basin is covered only by that tool's own
    x/z points (32 round each).
  - Trees over a mouth are not cleared. Hidden water or lava OUTSIDE the shell ring is not touched; a pocket beyond two cells
    cannot flow through two cells of stone.
  - Sand and gravel in the rock above a passage can fall; nothing here replaces them.
  - It claims no behaviour in game. Hostile and Pokemon spawns in the dark are not designed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import shutil
import sys
import zlib
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "cave_systems.json"
PACK = "cobblers_cave_systems"
OUT = ROOT / "build" / "datapacks" / PACK
PLAN = ROOT / "derived" / "cave_systems" / "plan.json"
IMAGES = ROOT / "docs" / "world-building" / "cave_systems"
NS = "cobblers"
FOLDER = "cave_systems"
F = "%s:%s" % (NS, FOLDER)
GENERATED = "tools/cave_systems.py"
POLICY_SCOPE = "cave_systems"
CARVE_AGAIN = True                 # carve, shell, carve again. A hook: tests/test_cave_systems.py turns it off to prove the audit bites
WORLD_READS: set = set()           # tools/ground_rule.py: this tool reads no world; the heightmap and data only
WIDEN = True                       # the 2026-10-23 widening and the nest rooms; False gives the live 2026-10-22 carve alone
NEST_PREFIX = "cave_nest_"         # this tool's nest-room ids (tools/nest_rooms.py); its own blocks are not "authored places"
CHECK_LIVE = True                  # fail closed if the base no longer reproduces the live carve (data/cave_systems.json live_carve)

SEA_LEVEL = 62                     # data/world.json vertical.sea_level (the audit reads the file; a test pins the two together)
Y_MIN = -64                       # the world's floor; keys use Y - Y_MIN
NY = 420
STEP = 2.0                         # blocks between network nodes
HMAX = 7                           # the tallest passage headroom
AIR = "minecraft:air"
LANTERN = "minecraft:lantern[hanging=false,waterlogged=false]"
BASE_STONE = "#minecraft:base_stone_overworld"

# files that are not footprints (planning labels, region polygons, spawn rules) and the paths no tool should walk
# entrance_trails.json, fishing_fill.json and underground_spawns.json (2026-10-22) are not places to keep clear:
# the trails END at the mouths by design, the fill is water cells, the pools are the caves' own boxes
SKIP_FILES = {"cave_systems.json", "cells.json", "regions.json", "marine_seas.json", "sculpt.json", "world.json", "spawns.json",
              "spawn_suppression.json", "entrance_trails.json", "fishing_fill.json", "underground_spawns.json"}
SKIP_DIRS = {"notes", "held", "checks"}
SKIP_KEYS = set()          # tools/southern_residents.py authored_points skips only `nearest_*`; so does this (landmark extents count)
RECT_KEYS = {"box", "bbox", "footprint", "rect", "bounds", "footprint_bbox", "hold", "keep_clear", "boxes", "apron_rect", "cell_box",
             "interior", "forceload"}


FILL_CMD = re.compile(r"\b(?:fill|clone)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)")
SET_CMD = re.compile(r"\bsetblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)")
LOAD_CMD = re.compile(r"\bforceload\s+add\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+)\s+(-?\d+))?")


class CaveSystemError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ hashing and noise

def h32(*vals):
    """FNV-style 32-bit mix of integers (the same mix tools/mines.py and tools/rift_mines.py use)."""
    a = 0x811C9DC5
    for v in vals:
        a = ((a ^ (int(v) & 0xFFFFFFFF)) * 0x01000193) & 0xFFFFFFFF
        a ^= a >> 15
        a = (a * 0x2C1B3C6D) & 0xFFFFFFFF
        a ^= a >> 12
    return a


def sid(s):
    return zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF


def rnd(*key):
    return random.Random(h32(*[sid(k) if isinstance(k, str) else k for k in key]))


_M = np.uint64(0xFFFFFFFF)


def hash01(ix, iy, iz, seed):
    """The h32 mix over integer arrays: [0, 1) per lattice point."""
    shape = np.broadcast(np.asarray(ix), np.asarray(iy), np.asarray(iz)).shape
    a = np.full(shape, 0x811C9DC5, dtype=np.uint64)
    for v in (seed, ix, iy, iz):
        v = (np.asarray(v).astype(np.int64) & 0xFFFFFFFF).astype(np.uint64)
        a = ((a ^ v) * np.uint64(0x01000193)) & _M
        a ^= a >> np.uint64(15)
        a = (a * np.uint64(0x2C1B3C6D)) & _M
        a ^= a >> np.uint64(12)
    return a.astype(np.float64) / 4294967296.0


def vnoise(x, y, z, seed, scale):
    """Trilinear value noise in [0, 1), smooth over `scale` blocks."""
    x = np.asarray(x, np.float64) / scale
    y = np.asarray(y, np.float64) / scale
    z = np.asarray(z, np.float64) / scale
    x0, y0, z0 = np.floor(x), np.floor(y), np.floor(z)
    fx, fy, fz = x - x0, y - y0, z - z0
    fx, fy, fz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
    xi, yi, zi = x0.astype(np.int64), y0.astype(np.int64), z0.astype(np.int64)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (fx if dx else 1 - fx) * (fy if dy else 1 - fy) * (fz if dz else 1 - fz)
                out = out + w * hash01(xi + dx, yi + dy, zi + dz, seed)
    return out


def noise1(t, seed):
    """Value noise along a line, [0, 1)."""
    return float(vnoise(t, 0.5, 0.5, seed, 1.0))


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ what is authored, and where water is

_AUTH = {}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def collect_authored():
    """{points, rects, rift} from every data/**/*.json except the planning labels (SKIP_FILES, SKIP_DIRS).

    The rule is tools/southern_residents.py authored_points widened: dicts with numeric x and z; [x, z], [x, y, z] (read both
    ways) and [x0, z0, x1, z1] corner lists (corners and centre); consecutive [x, z] pairs densified to one point every 16
    blocks (a route path is a line, not its vertices); rect dicts (min_x..max_z) and the keyed rect lists (RECT_KEYS) as
    filled rectangles; the Rift region polygon. Records noting ANOTHER place (`nearest_*`) place nothing and are skipped."""
    if "v" in _AUTH:
        return _AUTH["v"]
    pts, rects = [], []

    def add_line(a, b):
        n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) // 16)
        for i in range(n + 1):
            t = i / max(n, 1)
            pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))

    def commands_in(text):
        # a command written into a record (an earthwork's fill, a forceload): its boxes and points count as authored too
        for m in FILL_CMD.finditer(text):
            v = [int(q) for q in m.groups()]
            rects.append((min(v[0], v[3]), min(v[2], v[5]), max(v[0], v[3]), max(v[2], v[5])))
        for m in SET_CMD.finditer(text):
            pts.append((int(m.group(1)), int(m.group(3))))
        for m in LOAD_CMD.finditer(text):
            v = [int(q) for q in m.groups() if q is not None]
            rects.append((min(v[0], v[2] if len(v) > 2 else v[0]), min(v[1], v[3] if len(v) > 2 else v[1]),
                          max(v[0], v[2] if len(v) > 2 else v[0]), max(v[1], v[3] if len(v) > 2 else v[1])))

    def walk(o, key=None):
        if isinstance(o, str):
            if "fill " in o or "setblock " in o or "forceload " in o or "clone " in o:
                commands_in(o)
            return
        if isinstance(o, dict):
            if str(o.get("id", "")).startswith(NEST_PREFIX):
                return          # this tool's own nest-room Habitat Blocks sit inside its passages (tools/nest_rooms.py)
            ks = set(o)
            if {"min_x", "max_x", "min_z", "max_z"} <= ks and all(_num(o[k]) for k in ("min_x", "max_x", "min_z", "max_z")):
                rects.append((o["min_x"], o["min_z"], o["max_x"], o["max_z"]))
            if _num(o.get("x")) and _num(o.get("z")):
                pts.append((o["x"], o["z"]))
            for k, v in o.items():
                if isinstance(k, str) and (k.startswith("nearest_") or k in SKIP_KEYS):
                    continue
                walk(v, k)
        elif isinstance(o, list):
            if len(o) == 2 and all(_num(v) for v in o):
                pts.append((o[0], o[1]))
            elif len(o) == 3 and all(_num(v) for v in o):
                pts.append((o[0], o[2]))
                pts.append((o[0], o[1]))
            elif len(o) == 4 and all(_num(v) for v in o):
                x0, z0, x1, z1 = o
                if x1 >= x0 and z1 >= z0 and x1 - x0 < 2000 and z1 - z0 < 2000:
                    for xx in (x0, (x0 + x1) / 2.0, x1):
                        for zz in (z0, (z0 + z1) / 2.0, z1):
                            pts.append((xx, zz))
                    if key in RECT_KEYS:
                        rects.append((x0, z0, x1, z1))
            else:
                pair = [v for v in o if isinstance(v, list) and len(v) == 2 and all(_num(q) for q in v)]
                if len(pair) == len(o) and len(o) >= 2:
                    for a, b in zip(o, o[1:]):
                        if abs(a[0] - b[0]) + abs(a[1] - b[1]) <= 400:
                            add_line(a, b)
                for v in o:
                    walk(v, key)

    for p in sorted((ROOT / "data").rglob("*.json")):
        rel = p.relative_to(ROOT / "data")
        if p.name in SKIP_FILES or (set(rel.parts[:-1]) & SKIP_DIRS):
            continue
        walk(json.loads(p.read_text(encoding="utf-8")))
    reg = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    rift = [r for r in reg["regions"] if r["id"] == "the_rift"][0]["polygons"]
    _AUTH["v"] = {"points": np.array(pts, np.float64).reshape(-1, 2), "rects": rects, "rift": rift}
    return _AUTH["v"]


_WATER = {}


def collect_water():
    """{lakes: [ring], rivers: [(polyline, half width)], sea}: the landmark basins, the graded river courses, the sea level."""
    if "v" in _WATER:
        return _WATER["v"]
    lakes = []
    for l in json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))["landmarks"]:
        wb = l.get("water_body") or {}
        if wb.get("level_y") is not None:
            lakes += [[tuple(q) for q in r] for r in (wb.get("basin_polygons") or [])]
    rivers = []
    for c in json.loads((ROOT / "data" / "rivers.json").read_text(encoding="utf-8"))["courses"]:
        line = [(p[0], p[1]) for p in (c.get("graded_polyline") or [])]
        wid = max([r.get("width", 0) for r in (c.get("reaches") or [])] or [24])
        if len(line) >= 2:
            rivers.append((line, wid / 2.0 + 2))
    _WATER["v"] = {"lakes": lakes, "rivers": rivers}
    return _WATER["v"]


def towns():
    """[(id, x, z, min_x, min_z, max_x, max_z)] for the towns with a footprint."""
    out = []
    for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]:
        f = t.get("footprint") or {}
        c = t.get("centre") or {}
        if f.get("min_x") is None or c.get("x") is None:
            continue
        out.append((t["id"], c["x"], c["z"], f["min_x"], f["min_z"], f["max_x"], f["max_z"]))
    return out


# ------------------------------------------------------------------ raster helpers

def dilate_disc(m, r):
    """m grown by a Euclidean disc of radius r (integer), same shape."""
    if r <= 0:
        return m.copy()
    xs = [m]
    for _ in range(r):
        p = xs[-1].copy()
        p[:, 1:] |= xs[-1][:, :-1]
        p[:, :-1] |= xs[-1][:, 1:]
        xs.append(p)
    out = np.zeros_like(m)
    h = m.shape[0]
    for dz in range(-r, r + 1):
        w = int(math.isqrt(r * r - dz * dz))
        src = xs[w]
        if dz >= 0:
            out[dz:] |= src[:h - dz]
        else:
            out[:h + dz] |= src[-dz:]
    return out


def draw_mask(shape, origin, rings=(), lines=(), width=1):
    """Polygons filled and polylines drawn (width blocks) into a bool grid whose [0, 0] is the block `origin` (x, z)."""
    from PIL import Image, ImageDraw
    img = Image.new("L", (shape[1], shape[0]), 0)
    d = ImageDraw.Draw(img)
    ox, oz = origin
    for ring in rings:
        d.polygon([(q[0] - ox, q[1] - oz) for q in ring], fill=1)
    for ln, w in lines:
        d.line([(q[0] - ox, q[1] - oz) for q in ln], fill=1, width=max(1, int(2 * w)))
    return np.asarray(img).astype(bool)


# ------------------------------------------------------------------ the region: ground and what is blocked

def ground_grid(g, box):
    """Rounded heightmap ground (z, x) for the inclusive box. A hook: tests mutate THIS to prove the audit bites."""
    return g.box(*box).astype(np.int32)


def blocked_grid(rules, box, H):
    """bool (z, x) over the box: columns a cave may not be under. A hook (tests mutate it). Returns (blocked, parts)."""
    x0, z0, x1, z1 = box
    pad = 40
    gx0, gz0, gx1, gz1 = x0 - pad, z0 - pad, x1 + pad, z1 + pad
    shape = (gz1 - gz0 + 1, gx1 - gx0 + 1)
    a = collect_authored()
    ac = rules["authored_clearance"] + rules["plan_slack"]["authored"]
    wc = rules["water_reach"] + rules["plan_slack"]["water"]
    P = a["points"]
    sel = P[(P[:, 0] >= gx0 - ac) & (P[:, 0] <= gx1 + ac) & (P[:, 1] >= gz0 - ac) & (P[:, 1] <= gz1 + ac)]
    pm = np.zeros(shape, bool)
    ix = np.clip(np.round(sel[:, 0]).astype(int) - gx0, 0, shape[1] - 1)
    iz = np.clip(np.round(sel[:, 1]).astype(int) - gz0, 0, shape[0] - 1)
    inside = (np.round(sel[:, 0]) >= gx0) & (np.round(sel[:, 0]) <= gx1) & (np.round(sel[:, 1]) >= gz0) & (np.round(sel[:, 1]) <= gz1)
    pm[iz[inside], ix[inside]] = True
    # points just outside the padded grid still reach in: stamp them on the nearest edge cell (conservative)
    pm[iz[~inside], ix[~inside]] = True
    authored = dilate_disc(pm, ac)
    for (rx0, rz0, rx1, rz1) in a["rects"]:
        xa, xb = max(int(rx0) - ac, gx0), min(int(rx1) + ac, gx1)
        za, zb = max(int(rz0) - ac, gz0), min(int(rz1) + ac, gz1)
        if xa <= xb and za <= zb:
            authored[za - gz0:zb - gz0 + 1, xa - gx0:xb - gx0 + 1] = True
    rift = draw_mask(shape, (gx0, gz0), rings=a["rift"])
    authored |= dilate_disc(rift, ac)
    for ex in rules.get("exclusion_discs", []):
        zz, xx = np.ogrid[gz0:gz1 + 1, gx0:gx1 + 1]
        authored |= (zz - ex["z"]) ** 2 + (xx - ex["x"]) ** 2 <= (ex["r"] + rules["plan_slack"]["authored"]) ** 2
    w = collect_water()
    wet = draw_mask(shape, (gx0, gz0), rings=w["lakes"], lines=w["rivers"])
    sea = SEA_LEVEL
    big = np.full(shape, 9999, np.int32)
    big[pad:pad + H.shape[0], pad:pad + H.shape[1]] = H
    wet |= big <= sea + 1
    wet = dilate_disc(wet, wc)
    oob = np.zeros(shape, bool)
    gxs = np.arange(gx0, gx1 + 1)
    oob[:, gxs > rules["east_limit_x"]] = True
    oob[:, gxs < rules["west_limit_x"]] = True
    gzs = np.arange(gz0, gz1 + 1)
    oob[(gzs < rules["north_limit_z"]) | (gzs > rules["south_limit_z"]), :] = True
    blocked = authored | wet | oob
    sl = (slice(pad, pad + H.shape[0]), slice(pad, pad + H.shape[1]))
    return blocked[sl], {"authored": authored[sl], "water": wet[sl], "limits": oob[sl]}


def min_filter(a, r):
    """The minimum of `a` over the (2r+1) square round each cell."""
    out = a.copy()
    for ax in (0, 1):
        acc = out.copy()
        for k in range(1, r + 1):
            sa = [slice(None)] * 2
            sb = [slice(None)] * 2
            sa[ax] = slice(k, None)
            sb[ax] = slice(None, -k)
            acc[tuple(sa)] = np.minimum(acc[tuple(sa)], out[tuple(sb)])
            acc[tuple(sb)] = np.minimum(acc[tuple(sb)], out[tuple(sa)])
        out = acc
    return out


class Region:
    """The heightmap and the blocked grid over one system's box, indexed [z - z0, x - x0]."""

    def __init__(self, rules, sysspec, g=None):
        g = g or G.Ground()
        cx, cz = sysspec["centre"]
        pad = sysspec["radius"] + 70
        self.x0 = max(rules["west_limit_x"] - 40, cx - pad)
        self.x1 = min(rules["east_limit_x"] + 40, cx + pad)
        self.z0 = max(rules["north_limit_z"] - 40, cz - pad)
        self.z1 = min(rules["south_limit_z"] + 40, cz + pad)
        self.box = (self.x0, self.z0, self.x1, self.z1)
        self.H = ground_grid(g, self.box)
        self.blocked, self.parts = blocked_grid(rules, self.box, self.H)
        self.free_c = ~dilate_disc(self.blocked, 7)         # a node centre keeps 7 off the blocked ground (tube radius <= 3.6)
        self.shape = self.H.shape
        self.nz = self.shape[0]
        self.Hmin = min_filter(self.H, 5)                    # the lowest ground within 5 blocks: a passage's cover is judged on it

    def inside(self, x, z):
        return self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1

    def gnd(self, x, z):
        return int(self.H[int(round(z)) - self.z0, int(round(x)) - self.x0])

    def gmin(self, x, z):
        return int(self.Hmin[int(round(z)) - self.z0, int(round(x)) - self.x0])

    def free(self, x, z):
        ix, iz = int(round(x)) - self.x0, int(round(z)) - self.z0
        return 0 <= ix < self.shape[1] and 0 <= iz < self.shape[0] and bool(self.free_c[iz, ix])

    def key(self, X, Y, Z):
        return ((X - self.x0).astype(np.int64) * self.nz + (Z - self.z0)) * NY + (Y - Y_MIN)

    def unkey(self, k):
        y = k % NY + Y_MIN
        r = k // NY
        return (r // self.nz + self.x0), y, (r % self.nz + self.z0)


# ------------------------------------------------------------------ the network

class Net:
    def __init__(self):
        self.n = []              # [x, y, z, w, h, branch]
        self.edges = []          # (i, j)
        self.branches = []
        self.bucket = {}
        self.length = 0.0

    def add(self, x, y, z, w, h, b):
        i = len(self.n)
        self.n.append([x, y, z, w, h, b])
        self.bucket.setdefault((int(x) // 8, int(z) // 8), []).append(i)
        return i

    def link(self, i, j):
        self.edges.append((i, j))
        a, b = self.n[i], self.n[j]
        self.length += math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)

    def near(self, x, y, z, rh, rv):
        bx, bz = int(x) // 8, int(z) // 8
        k = int(rh // 8) + 1
        out = []
        for ax in range(bx - k, bx + k + 1):
            for az in range(bz - k, bz + k + 1):
                for i in self.bucket.get((ax, az), ()):
                    n = self.n[i]
                    if abs(n[1] - y) < rv and (n[0] - x) ** 2 + (n[2] - z) ** 2 < rh * rh:
                        out.append(i)
        return out


def angdiff(a, b):
    d = (a - b + math.pi) % (2 * math.pi) - math.pi
    return d


class Builder:
    def __init__(self, spec, sysspec, region, attempt=0):
        self.spec, self.rules, self.s, self.R = spec, spec["rules"], sysspec, region
        self.attempt = attempt
        self.seed = (sid(sysspec["id"]) ^ (sysspec["seed"] & 0xFFFFFFFF) ^ (attempt * 0x9E3779B1)) & 0xFFFFFFFF
        self.net = Net()
        self.cx, self.cz = sysspec["centre"]
        self.rad = sysspec["radius"]
        self.levels = self.rules["levels"]
        self.mouths = []
        self.level_len = [0.0] * len(self.levels)

    # -- feasibility
    def cap(self, x, z):
        return self.R.gmin(x, z) - self.rules["plan_cover"] - HMAX

    def step_ok(self, x, y, z, hd, ny, ramp):
        R = self.R
        for t in (STEP, 6, 10, 14, 18, 22):
            px, pz = x + t * math.cos(hd), z + t * math.sin(hd)
            if not R.inside(px, pz) or not R.free(px, pz):
                return False
            if (px - self.cx) ** 2 + (pz - self.cz) ** 2 > self.rad ** 2:
                return False
            if not ramp and self.cap(px, pz) < ny - 0.5 * (t - STEP) - 0.5:
                return False
        return True

    def conflict(self, x, y, z, br, own, parent_chain):
        for j in self.net.near(x, y, z, self.rules["separation"], self.rules["separation_v"]):
            if j in parent_chain:
                continue
            if self.net.n[j][5] == br and j in own[-8:]:
                continue
            return j
        return None

    def level_y(self, rng, level):
        lv = self.levels[level]
        return lv["y"] + rng.uniform(-lv["spread"], lv["spread"])

    # -- one branch
    def grow(self, task):
        net, R, rules = self.net, self.R, self.rules
        rng = rnd(self.seed, "branch", task["id"])
        tid = sid(task["id"]) & 0xFFFF
        bid = len(net.branches)
        br = {"id": task["id"], "kind": task["kind"], "level": task["level"], "start": task["start"], "nodes": [], "length": 0.0,
              "joined": None, "parent": task.get("parent_branch")}
        net.branches.append(br)
        i0 = task["start"]
        x, y, z = net.n[i0][0], net.n[i0][1], net.n[i0][2]
        heading, turn = task["heading"], 0.0
        ly = task["level_y"]
        w0 = task["width"]
        pb = net.n[i0][5]
        parent_chain = {q for q in range(max(0, i0 - 5), min(len(net.n), i0 + 6)) if net.n[q][5] == pb}
        if task["kind"] == "mouth":
            parent_chain = {i0}
        own = [i0]
        prev = i0
        L = 0.0
        children = []
        last_child = 0.0
        ramp_len = rules["mouth_zone"] if task["kind"] == "mouth" else 0
        phase = rng.uniform(0, 6.28)
        sigma = rules["turn_sigma"]
        offs = (0, 0.3, -0.3, 0.65, -0.65, 1.0, -1.0, 1.6, -1.6, 2.4, -2.4)
        while L < task["max_len"]:
            turn = 0.82 * turn + rng.gauss(0, sigma)
            hd = heading + turn
            dc = math.hypot(self.cx - x, self.cz - z)
            if dc > 0.7 * self.rad:
                hd += 0.22 * angdiff(math.atan2(self.cz - z, self.cx - x), hd) * min(2.0, dc / self.rad + 0.3)
            ramping = L < ramp_len
            holding = task["kind"] != "mouth" and L < rules["fork_flat"]
            wob = 2.2 * math.sin(L / 41.0 + phase) + 1.2 * math.sin(L / 17.0 + 2 * phase)
            target = y if holding else ly + (0 if ramping else wob)
            diff = target - y
            slope = rules["slope_max"] if (abs(diff) > 3 or ramping) else 0.3
            ny = y + max(-STEP * slope, min(STEP * slope, diff))
            ny = max(ny, rules["min_floor_y"])
            placed = None
            joined = None
            for off in offs:
                h2 = hd + off
                nx, nz = x + STEP * math.cos(h2), z + STEP * math.sin(h2)
                if not R.inside(nx, nz):
                    continue
                nyc = ny if ramping else min(ny, self.cap(nx, nz))
                if not self.step_ok(x, nyc, z, h2, nyc, ramping):
                    continue
                c = self.conflict(nx, nyc, nz, bid, own, parent_chain)
                if c is not None:
                    n = net.n[c]
                    if L > rules["join_after"] and joined is None and rng.random() < rules["join_chance"] and abs(n[1] - y) <= 0.45 * math.hypot(n[0] - x, n[2] - z):
                        joined = c
                        break
                    continue
                placed = (nx, nyc, nz, h2)
                break
            if joined is not None:
                net.link(prev, joined)
                br["joined"] = joined
                br["length"] += STEP
                L += STEP
                break
            if placed is None:
                break
            nx, ny, nz, heading = placed
            width = max(rules["width"][0], min(rules["width"][1], w0 + 1.5 * (noise1(L / 45.0, self.seed + tid * 7) - 0.5) * 2))
            hgt = max(rules["height"][0], min(rules["height"][1], 3.2 + 0.55 * width + 1.6 * (noise1(L / 31.0, self.seed + 11 + tid) - 0.5)))
            j = net.add(nx, ny, nz, width, hgt, bid)
            net.link(prev, j)
            own.append(j)
            br["nodes"].append(j)
            prev = j
            x, y, z = nx, ny, nz
            L += STEP
            br["length"] += STEP
            if L > 40 and L - last_child > rules["child_spacing"] and rng.random() < rules["child_rate"] and task["kind"] != "stub":
                children.append((j, heading, L))
                last_child = L
        br["end"] = prev
        self.level_len[task["level"]] += br["length"]
        return br, children

    def mouth_heading(self, m, gy):
        """The way a mouth's passage enters the hill: the direction nearest the system's centre in which the ramp (0.5 down a block)
        stays under the ground by the rules' cover, over free ground, for 70 blocks."""
        R = self.R
        base = math.atan2(self.cz - m["z"], self.cx - m["x"])
        offs = [0.0]
        for k in range(1, 13):
            offs += [k * math.radians(15), -k * math.radians(15)]
        best, best_score = base, -1e9
        for off in offs:
            ang = base + off
            score = 1e9
            for t in range(4, 74, 3):
                px, pz = m["x"] + t * math.cos(ang), m["z"] + t * math.sin(ang)
                if not R.inside(px, pz) or not R.free(px, pz):
                    score = -1e9
                    break
                if t >= 6 and R.gnd(px, pz) - (gy - 0.5 * t) < 2:
                    score = -1e9                       # the ground falls away faster than the ramp: the floor would hang in the air
                    break
                if t >= 24:
                    score = min(score, R.gmin(px, pz) - (gy - 0.5 * t) - (HMAX - 1))
            if score >= self.rules["plan_cover"] - 1:
                return ang
            if score > best_score:
                best, best_score = ang, score
        return best

    def mouth_task(self, m, k):
        R = self.R
        if not R.inside(m["x"], m["z"]) or not R.free(m["x"], m["z"]):
            raise CaveSystemError("%s: mouth %s (%d, %d) is not on free ground: it lies within the kept-clear margin of something authored, "
                                  "water or the map's limits (python tools/cave_systems.py site %s)" % (self.s["id"], m["id"], m["x"], m["z"], self.s["id"]))
        gy = R.gnd(m["x"], m["z"])
        hd = math.radians(m["heading"]) if m.get("heading") is not None else self.mouth_heading(m, gy)
        rng = rnd(self.seed, "mouth", k)
        i = self.net.add(float(m["x"]), float(gy), float(m["z"]), 4.4, 5.0, -1)
        self.mouths.append({"id": m["id"], "node": i, "x": m["x"], "z": m["z"], "y": gy, "near": m.get("near")})
        return {"id": "m%d" % k, "start": i, "heading": hd, "level": 0, "level_y": self.level_y(rng, 0), "max_len": min(rng.uniform(*self.rules["trunk_len"]), 1.4 * self.s["target_length"] / len(self.s["mouths"]) + 80),
                "kind": "mouth", "width": rng.uniform(4.2, 6.0)}

    def child_task(self, parent_branch, node, heading, L, k, rng):
        rules = self.rules
        lvl = parent_branch["level"]
        nl = len(self.levels)
        tgt = float(self.s["target_length"])
        share = rules["level_share"]
        opts = [(lvl, "side")]
        if lvl + 1 < nl:
            opts.append((lvl + 1, "descent"))
        if lvl > 0:
            opts.append((lvl - 1, "ascent"))
        wts = []
        for (lv, kd) in opts:
            deficit = max(0.0, share[lv] * tgt - self.level_len[lv]) / tgt
            wts.append(rules["level_base"][kd] + rules["level_pull"] * deficit)
        pick = rng.random() * sum(wts)
        level, kind = opts[-1]
        for (lv, kd), w in zip(opts, wts):
            pick -= w
            if pick <= 0:
                level, kind = lv, kd
                break
        side = rng.choice((-1, 1))
        hd = heading + side * rng.uniform(0.9, 1.9)
        if kind == "descent":
            mx = rng.uniform(*rules["descent_len"])
        else:
            mx = min(rules["side_len"][1], rules["side_len"][0] + rng.expovariate(1.0 / rules["side_len_mean"]))
        return {"id": "b%d" % k, "start": node, "heading": hd, "level": level, "level_y": self.level_y(rng, level), "max_len": mx,
                "kind": kind, "width": rng.uniform(3.2, 5.8), "parent_branch": parent_branch["id"]}

    def pick_task(self, queue, rng):
        """The queued branch whose level is shortest of its share, with a little noise: deeper levels get their length."""
        for i, t in enumerate(queue):
            if t["kind"] == "mouth":
                del queue[i]
                return t
        tgt = float(self.s["target_length"])
        share = self.rules["level_share"]
        best, bi = -1e9, 0
        for i, t in enumerate(queue):
            sc = (share[t["level"]] * tgt - self.level_len[t["level"]]) / tgt + (0.35 if t["kind"] == "mouth" else 0.0) + 0.25 * rng.random()
            if sc > best:
                best, bi = sc, i
        t = queue[bi]
        del queue[bi]
        return t

    def run(self):
        rng = rnd(self.seed, "orchestra")
        queue = []
        for k, m in enumerate(self.s["mouths"]):
            queue.append(self.mouth_task(m, k))
        target = self.s["target_length"]
        k = 0
        guard = 0
        while (self.net.length < target or any(t["kind"] == "mouth" for t in queue)) and guard < 4000:
            guard += 1
            if not queue:
                # every branch ended: fork again from a random node of the network
                if not self.net.n or guard > 3000:
                    break
                j = rng.randrange(len(self.net.n))
                nb = self.net.n[j][5]
                if nb < 0:
                    continue
                queue.append(self.child_task(self.net.branches[nb], j, rng.uniform(0, 6.28), 0, 9000 + guard, rng))
            task = self.pick_task(queue, rng)
            br, kids = self.grow(task)
            rng.shuffle(kids)
            for (j, hd, L) in kids:
                k += 1
                queue.append(self.child_task(br, j, hd, L, k, rng))
        self.link_components(rng)
        return self.net

    # -- one system, one network: join every separate piece to the largest by a routed link passage
    def components(self):
        n = len(self.net.n)
        par = list(range(n))

        def find(a):
            while par[a] != a:
                par[a] = par[par[a]]
                a = par[a]
            return a
        for i, j in self.net.edges:
            par[find(i)] = find(j)
        comp = {}
        for i in range(n):
            comp.setdefault(find(i), []).append(i)
        return list(comp.values())

    def avoid_grid(self, a, b):
        """4-block cells a link from node a to node b must not cross: within 10 of a passage whose floor is within 12 of the floor the
        link will have there (a link crossing a passage at a near level would cut its floor away and leave a ledge). The ends keep
        16 blocks of freedom."""
        f4 = self.free4
        R = self.R
        av = np.zeros(f4.shape, bool)
        dx, dz = b[0] - a[0], b[2] - a[2]
        L2 = dx * dx + dz * dz or 1.0
        for n in self.net.n:
            if math.hypot(n[0] - a[0], n[2] - a[2]) < 16 or math.hypot(n[0] - b[0], n[2] - b[2]) < 16:
                continue
            t = min(1.0, max(0.0, ((n[0] - a[0]) * dx + (n[2] - a[2]) * dz) / L2))
            if n[1] < min(a[1], b[1]) - 14 or n[1] > max(a[1], b[1]) + 14:
                continue
            gx, gz = int(round((n[0] - R.x0) / 4.0)), int(round((n[2] - R.z0) / 4.0))
            av[max(0, gz - 3):gz + 4, max(0, gx - 3):gx + 4] = True
        return av

    def astar(self, ax, az, bx, bz, avoid=None):
        """A route over the free ground at 4-block cells, [(x, z)] from a to b, or None."""
        import heapq
        R = self.R
        if not hasattr(self, "free4"):
            f4 = R.free_c[::4, ::4].copy()
            zz, xx = np.ogrid[0:f4.shape[0], 0:f4.shape[1]]
            f4 &= ((xx * 4 + R.x0 - self.cx) ** 2 + (zz * 4 + R.z0 - self.cz) ** 2) <= self.rad ** 2
            self.free4 = f4
        f4 = self.free4 if avoid is None else (self.free4 & ~avoid)

        def cell(x, z):
            return (int(round((z - R.z0) / 4.0)), int(round((x - R.x0) / 4.0)))

        def nearest_free(c):
            if 0 <= c[0] < f4.shape[0] and 0 <= c[1] < f4.shape[1] and f4[c]:
                return c
            for r in range(1, 5):
                for dz in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        q = (c[0] + dz, c[1] + dx)
                        if 0 <= q[0] < f4.shape[0] and 0 <= q[1] < f4.shape[1] and f4[q]:
                            return q
            return None
        a, b = nearest_free(cell(ax, az)), nearest_free(cell(bx, bz))
        if a is None or b is None:
            return None
        openh = [(0.0, 0.0, a)]
        came = {a: None}
        best = {a: 0.0}
        nbrs = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        while openh:
            _f, g, c = heapq.heappop(openh)
            if c == b:
                break
            if g > best.get(c, 1e18):
                continue
            for dz, dx, w in nbrs:
                q = (c[0] + dz, c[1] + dx)
                if not (0 <= q[0] < f4.shape[0] and 0 <= q[1] < f4.shape[1]) or not f4[q]:
                    continue
                if dz and dx and not (f4[c[0] + dz, c[1]] and f4[c[0], c[1] + dx]):
                    continue
                ng = g + w
                if ng < best.get(q, 1e18):
                    best[q] = ng
                    came[q] = c
                    heapq.heappush(openh, (ng + math.hypot(q[0] - b[0], q[1] - b[1]), ng, q))
        if b not in came:
            return None
        path = []
        c = b
        while c is not None:
            path.append((c[1] * 4 + R.x0, c[0] * 4 + R.z0))
            c = came[c]
        path.reverse()
        return path

    def link_profile(self, pts, ya, yb, cover=None):
        """Floor heights along a resampled route: the straight run from ya to yb, held under the cap and the slope limit; None
        if the ends cannot be met."""
        cv = self.rules["plan_cover"] if cover is None else cover
        cap = np.array([self.R.gmin(x, z) - cv - HMAX for x, z in pts])
        d = np.array([0.0] + [math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) for i in range(1, len(pts))]).cumsum()
        D = d[-1]
        y = ya + (yb - ya) * d / max(D, 1e-9)
        y = np.minimum(y, cap)
        y = np.maximum(y, self.rules["min_floor_y"])
        y[0], y[-1] = ya, yb
        sl = 0.45
        for i in range(1, len(y)):
            y[i] = min(y[i], y[i - 1] + sl * (d[i] - d[i - 1]))
            y[i] = max(y[i], y[i - 1] - sl * (d[i] - d[i - 1]))
        for i in range(len(y) - 2, -1, -1):
            y[i] = min(y[i], y[i + 1] + sl * (d[i + 1] - d[i]))
            y[i] = max(y[i], y[i + 1] - sl * (d[i + 1] - d[i]))
        if abs(y[0] - ya) > 0.6 or abs(y[-1] - yb) > 0.6:
            return None
        inner = y[1:-1]
        if len(inner) and (inner > cap[1:-1] + 1.0).any():
            return None
        return y

    def resample(self, path, step=STEP):
        P = np.array(path, float)
        raw = P.copy()
        for _ in range(3):
            Q = P.copy()
            for i in range(1, len(P) - 1):
                Q[i] = (P[i - 1] + 2 * P[i] + P[i + 1]) / 4.0
            P = Q

        def along(A):
            seg = np.hypot(*np.diff(A, axis=0).T)
            c = np.concatenate(([0.0], seg.cumsum()))
            n = max(2, int(c[-1] // step) + 1)
            t = np.linspace(0, c[-1], n)
            return [(float(np.interp(v, c, A[:, 0])), float(np.interp(v, c, A[:, 1]))) for v in t]
        sm = along(P)
        if all(self.R.free(x, z) for x, z in sm):
            return sm
        return along(raw)

    def link_components(self, rng):
        net = self.net
        self.links = []
        self.unlinked = []
        self.link_log = []
        for _round in range(24):
            comps = self.components()
            if len(comps) <= 1:
                return
            comps.sort(key=len, reverse=True)
            main = comps[0]
            hard = self.rules["cover_min"] + 1 + HMAX
            main = [i for i in main if net.n[i][1] <= self.R.gmin(net.n[i][0], net.n[i][2]) - hard]       # not a surface-hugging mouth node
            if not main:
                return
            mainset = np.array([[net.n[i][0], net.n[i][1], net.n[i][2]] for i in main])
            done = False
            for comp in comps[1:]:
                best = []
                for i in comp:
                    nd = net.n[i]
                    if nd[1] > self.R.gmin(nd[0], nd[2]) - hard:
                        continue
                    hd_ = np.sqrt((mainset[:, 0] - nd[0]) ** 2 + (mainset[:, 2] - nd[2]) ** 2)
                    dy_ = np.abs(mainset[:, 1] - nd[1])
                    ok_ = dy_ <= 0.34 * hd_ + 1.0           # a link walks at 0.45 at most over a route that is longer than the straight line
                    if not ok_.any():
                        continue
                    dd = np.where(ok_, hd_, 1e9)
                    j = int(dd.argmin())
                    best.append((float(dd[j]), i, main[j]))
                best.sort()
                picked = []
                for (dist, i, j) in best:
                    if all(math.hypot(net.n[i][0] - net.n[p][0], net.n[i][2] - net.n[p][2]) > 60 for p, _q in picked):
                        picked.append((i, j))
                    if len(picked) >= 8:
                        break
                for (i, j) in picked:
                    a, b = net.n[i], net.n[j]
                    self.astar(a[0], a[2], a[0], a[2])          # builds free4
                    prof = pts = None
                    for avoid in (self.avoid_grid(a, b), None):
                        path = self.astar(a[0], a[2], b[0], b[2], avoid)
                        if not path or len(path) < 2:
                            self.link_log.append("no route %s -> %s" % ([round(v) for v in a[:3]], [round(v) for v in b[:3]]))
                            continue
                        pts = self.resample(path)
                        prof = self.link_profile(pts, a[1], b[1])
                        if prof is None:
                            prof = self.link_profile(pts, a[1], b[1], self.rules["cover_min"] + 1)
                        if prof is not None:
                            break
                        self.link_log.append("no profile %s -> %s over %d blocks (ends y%.0f and y%.0f)" % ([round(v) for v in a[:3]], [round(v) for v in b[:3]], len(pts) * 2, a[1], b[1]))
                    if prof is None:
                        continue
                    bid = len(net.branches)
                    lvl = min(range(len(self.levels)), key=lambda q: abs(self.levels[q]["y"] - float(prof.mean())))
                    br = {"id": "link%d" % len(self.links), "kind": "link", "level": lvl, "start": i, "nodes": [], "length": 0.0,
                          "joined": j, "parent": None, "end": i}
                    net.branches.append(br)
                    prev = i
                    for k in range(1, len(pts) - 1):
                        w = max(3.2, min(6.0, 4.4 + 1.2 * (noise1(k / 12.0, self.seed + 91 + len(self.links)) - 0.5) * 2))
                        hh = max(4.0, min(6.5, 3.2 + 0.55 * w))
                        q = net.add(pts[k][0], float(prof[k]), pts[k][1], w, hh, bid)
                        net.link(prev, q)
                        br["nodes"].append(q)
                        prev = q
                    net.link(prev, j)
                    br["end"] = prev
                    br["length"] = float(sum(math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]) for k in range(1, len(pts))))
                    self.level_len[lvl] += br["length"]
                    self.links.append({"from": i, "to": j, "length": round(br["length"])})
                    done = True
                    break
                if done:
                    break
            if not done:
                self.unlinked = [[net.n[c[0]][0], net.n[c[0]][2]] for c in self.components()[1:]]
                return

    # -- caverns
    def place_caverns(self):
        rules, R, net = self.rules, self.R, self.net
        cr = rules["cavern"]
        rng = rnd(self.seed, "caverns")
        want = self.s["caverns"]
        order = [i for i in range(len(net.n)) if net.n[i][5] >= 0]
        rng.shuffle(order)
        chosen = []
        # prefer different levels: bucket the candidate nodes by level and take them round robin
        by_level = {}
        for i in order:
            by_level.setdefault(min(range(len(self.levels)), key=lambda q: abs(self.levels[q]["y"] - net.n[i][1])), []).append(i)
        rr = [lv for lv in (1, 2, 0, 3) if lv in by_level] + [lv for lv in by_level if lv not in (0, 1, 2, 3)]
        tries = 0
        li = 0
        ptr = {lv: 0 for lv in by_level}
        while len(chosen) < want and tries < 4000 and rr:
            tries += 1
            lv = rr[li % len(rr)]
            li += 1
            if ptr[lv] >= len(by_level[lv]):
                if all(ptr[q] >= len(by_level[q]) for q in rr):
                    break
                continue
            i = by_level[lv][ptr[lv]]
            ptr[lv] += 1
            n = net.n[i]
            if any(math.hypot(n[0] - c["x"], n[2] - c["z"]) < cr["spacing"] for c in chosen):
                continue
            cav = self.try_cavern(i, rng, cr)
            if cav:
                cav["id"] = len(chosen)
                chosen.append(cav)
        self.caverns = chosen
        return chosen

    def try_cavern(self, i, rng, cr):
        net, R = self.net, self.R
        n = net.n[i]
        x, y, z = n[0], n[1], n[2]
        # not under the mouth zone, not too near the start of a mouth branch
        for m in self.mouths:
            if math.hypot(m["x"] - x, m["z"] - z) < self.rules["mouth_zone"] + 40:
                return None
        for attempt in range(3):
            across = rng.uniform(*cr["across"])
            a = across / 2.0
            b = a * rng.uniform(0.85, 1.0)
            ang = rng.uniform(0, math.pi)
            tall = rng.uniform(*cr["tall"]) * (0.9 ** attempt)
            yf = int(round(y))
            ca, sa = math.cos(ang), math.sin(ang)
            ext = int(a * 1.5) + 3
            xs = np.arange(int(x) - ext, int(x) + ext + 1)
            zs = np.arange(int(z) - ext, int(z) + ext + 1)
            if xs[0] < R.x0 or xs[-1] > R.x1 or zs[0] < R.z0 or zs[-1] > R.z1:
                continue
            X, Z = np.meshgrid(xs, zs)
            u = ((X - x) * ca + (Z - z) * sa) / a
            v = (-(X - x) * sa + (Z - z) * ca) / b
            rho = np.sqrt(u * u + v * v)
            foot = rho < 1.45
            iz, ix = Z - R.z0, X - R.x0
            if R.blocked[iz[rho < 1.05], ix[rho < 1.05]].mean() > 0.12 or R.blocked[iz[foot], ix[foot]].mean() > 0.2:
                continue
            gmin = int(R.Hmin[iz[rho < 1.4], ix[rho < 1.4]].min())
            hmax = gmin - self.rules["plan_cover"] - 2 - yf
            if hmax < cr["tall"][0] * 0.9:
                continue
            tall = min(tall, hmax)
            if tall < cr["tall"][0] * 0.9:
                continue
            # another level's passage may not cross the volume at a different height (it would open into a drop)
            bad = False
            for j in net.near(x, yf, z, a * 1.6, 400):
                m = net.n[j]
                uu = ((m[0] - x) * ca + (m[2] - z) * sa) / a
                vv = (-(m[0] - x) * sa + (m[2] - z) * ca) / b
                if uu * uu + vv * vv < 1.5 ** 2 and yf - 12 < m[1] < yf + tall + 4 and not (yf - 3 <= m[1] <= yf + 3):
                    bad = True
                    break
            if bad:
                continue
            return {"x": x, "z": z, "yf": yf, "a": a, "b": b, "angle": ang, "tall": tall, "node": i, "id": len(getattr(self, "caverns", []))}
        return None

    def blend_to_caverns(self):
        net = self.net
        for c in self.caverns:
            ca, sa = math.cos(c["angle"]), math.sin(c["angle"])
            for i, m in enumerate(net.n):
                if m[5] < 0:
                    continue
                uu = ((m[0] - c["x"]) * ca + (m[2] - c["z"]) * sa) / c["a"]
                vv = (-(m[0] - c["x"]) * sa + (m[2] - c["z"]) * ca) / c["b"]
                d = math.sqrt(uu * uu + vv * vv)
                if d < 1.3 and abs(m[1] - c["yf"]) <= 3.6:
                    t = smooth((d - 0.35) / 0.95)
                    m[1] = c["yf"] + (m[1] - c["yf"]) * t

    # -- halls at dead ends
    def halls(self):
        out = []
        rng = rnd(self.seed, "halls")
        for br in self.net.branches:
            if br["kind"] in ("mouth",) or br["joined"] is not None or len(br["nodes"]) < 12:
                continue
            i = br["end"]
            n = self.net.n[i]
            if rng.random() < self.rules["hall_chance"]:
                if any(math.hypot(n[0] - c["x"], n[2] - c["z"]) < c["a"] * 1.4 + 12 for c in self.caverns):
                    continue
                out.append({"node": i, "x": n[0], "y": n[1], "z": n[2], "a": rng.uniform(5.5, 9.0), "b": rng.uniform(4.5, 7.0),
                            "angle": rng.uniform(0, 3.14), "tall": rng.uniform(5, 9)})
        # a hall must fit the same rules as a passage: keep it only where the cover and the free ground allow
        keep = []
        for h in out:
            ext = int(h["a"]) + 2
            ok = all(self.R.inside(h["x"] + dx, h["z"] + dz) and self.R.free(h["x"] + dx, h["z"] + dz)
                     and self.cap(h["x"] + dx, h["z"] + dz) >= h["y"] + h["tall"] - HMAX + 1
                     for dx in (-ext, 0, ext) for dz in (-ext, 0, ext))
            if ok:
                keep.append(h)
        self.hall_list = keep
        return keep


# ------------------------------------------------------------------ voxels

def tube_cells(net, seed, rules):
    """int arrays X, Y, Z of every cell the passages sweep (flat floor, superellipse section, noisy walls)."""
    segs = []
    for (i, j) in net.edges:
        a, b = net.n[i], net.n[j]
        d = math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)
        n = max(2, int(math.ceil(d / 0.5)))
        t = np.linspace(0.0, 1.0, n + 1)
        segs.append(np.stack([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t,
                              a[3] + (b[3] - a[3]) * t, a[4] + (b[4] - a[4]) * t], axis=1))
    if not segs:
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0, int)
    S = np.concatenate(segs)
    px, py, pz, w, h = S[:, 0], S[:, 1], S[:, 2], S[:, 3], S[:, 4]
    cxs, czs, yf = np.round(px).astype(np.int64), np.round(pz).astype(np.int64), np.round(py).astype(np.int64)
    rr = w / 2.0 * 1.12
    R = int(math.ceil(rules["width"][1] / 2.0 * 1.12 * 1.3)) + 1
    outx, outy, outz = [], [], []
    for dx in range(-R, R + 1):
        for dz in range(-R, R + 1):
            x = cxs + dx
            z = czs + dz
            d = np.hypot(x - px, z - pz)
            nz_ = vnoise(x, yf, z, seed + 3, 5.0)
            reff = rr * (0.84 + 0.32 * nz_)
            ok = d < reff
            if not ok.any():
                continue
            frac = (d[ok] / reff[ok]) ** 2.4
            hc = np.floor(h[ok] * np.sqrt(np.maximum(0.0, 1 - frac)) + 0.35).astype(np.int64)
            xx, zz, yy = x[ok], z[ok], yf[ok]
            for k in range(HMAX + 1):
                m = hc > k
                if m.any():
                    outx.append(xx[m])
                    outy.append(yy[m] + k)
                    outz.append(zz[m])
    return np.concatenate(outx), np.concatenate(outy), np.concatenate(outz)


def cavern_cells(c, seed, region):
    """A cavern: a flat floor at yf, a dome ceiling to yf + tall, noisy walls, a few pillars and rubble mounds."""
    a, b, ang, yf, tall = c["a"], c["b"], c["angle"], c["yf"], c["tall"]
    ca, sa = math.cos(ang), math.sin(ang)
    ext = int(a * 1.5) + 3
    xs = np.arange(int(c["x"]) - ext, int(c["x"]) + ext + 1)
    zs = np.arange(int(c["z"]) - ext, int(c["z"]) + ext + 1)
    X, Z = np.meshgrid(xs, zs)
    u = ((X - c["x"]) * ca + (Z - c["z"]) * sa) / a
    v = (-(X - c["x"]) * sa + (Z - c["z"]) * ca) / b
    rho = np.sqrt(u * u + v * v)
    warp = 1 + 0.18 * (vnoise(X, 0, Z, seed + 5 + c["id"], 14.0) - 0.5) * 2 + 0.06 * (vnoise(X, 1, Z, seed + 6, 5.0) - 0.5) * 2
    rr = rho * warp
    inside = rr < 1.0
    ceil_noise = 2.2 * (vnoise(X, 2, Z, seed + 7, 9.0) - 0.5) * 2
    top = yf + np.floor(tall * np.power(np.maximum(0.0, 1 - rr * rr), 0.55) + ceil_noise * (rr < 0.9)).astype(np.int64)
    top = np.maximum(top, yf + 3)
    rng = rnd(seed, "cavern", c["id"])
    # pillars and rubble keep clear of the node's own passage (rho < 0.25 round the centre)
    keep = np.zeros(X.shape, bool)
    for _ in range(rng.randint(3, 7)):
        pr = rng.uniform(0.25, 0.8)
        pa = rng.uniform(0, 6.28)
        px = c["x"] + pr * a * math.cos(pa)
        pz = c["z"] + pr * b * math.sin(pa)
        rad = rng.uniform(1.4, 3.0)
        keep |= np.hypot(X - px, Z - pz) < rad
    keep &= rho > 0.3
    rubble = np.zeros(X.shape, bool)
    for _ in range(rng.randint(6, 16)):
        pr = rng.uniform(0.2, 0.9)
        pa = rng.uniform(0, 6.28)
        px = c["x"] + pr * a * math.cos(pa)
        pz = c["z"] + pr * b * math.sin(pa)
        rubble |= np.hypot(X - px, Z - pz) < rng.uniform(1.5, 3.2)
    rubble &= rho > 0.3
    ox, oy, oz = [], [], []
    cols = inside & ~keep
    ix, iz = np.nonzero(cols)
    topc = top[ix, iz]
    base = np.full(ix.shape, yf, np.int64) + rubble[ix, iz].astype(np.int64)
    for k in range(0, int(tall) + 6):
        y = yf + k
        m = (y >= base) & (y <= topc)
        if m.any():
            ox.append(X[ix[m], iz[m]])
            oz.append(Z[ix[m], iz[m]])
            oy.append(np.full(int(m.sum()), y))
    return np.concatenate(ox), np.concatenate(oy), np.concatenate(oz)


def hall_cells(h, seed):
    c = dict(h, yf=int(round(h["y"])), id=1000)
    return cavern_cells(c, seed, None)


def mouth_zone_mask(region, mouths, radius):
    m = np.zeros(region.shape, bool)
    for q in mouths:
        zz, xx = np.ogrid[region.z0:region.z1 + 1, region.x0:region.x1 + 1]
        m |= (zz - q["z"]) ** 2 + (xx - q["x"]) ** 2 <= radius ** 2
    return m


def clip_cells(region, rules, X, Y, Z, zone):
    """The cells allowed by the rules: unblocked columns, cover >= cover_min (a mouth zone only needs to stay under the surface),
    above the floor limit. Returns (keep mask, count of cells each rule removed)."""
    ix, iz = X - region.x0, Z - region.z0
    inb = (ix >= 0) & (ix < region.shape[1]) & (iz >= 0) & (iz < region.shape[0])
    ixc, izc = np.clip(ix, 0, region.shape[1] - 1), np.clip(iz, 0, region.shape[0] - 1)
    g = region.H[izc, ixc]
    cover = g - Y
    free = ~region.blocked[izc, ixc]
    zn = zone[izc, ixc]
    ok_cover = (cover >= rules["cover_min"]) | (zn & (cover >= 0))
    ok_y = Y >= rules["min_floor_y"] - 1
    keep = inb & free & ok_cover & ok_y
    return keep, {"outside": int((~inb).sum()), "blocked": int((inb & ~free).sum()), "cover": int((inb & free & ~ok_cover).sum()), "low": int((~ok_y).sum())}


# ------------------------------------------------------------------ ore and light

def town_dist(X, Z):
    best = np.full(X.shape, 1e9)
    for (_i, tx, tz, *_r) in towns():
        best = np.minimum(best, np.hypot(X - tx, Z - tz))
    return best


def ore_table(rules):
    return rules["ore"]["types"]


def dress_ore(region, rules, seed, carved_keys, zone):
    """[(x, y, z, block)] ore cells in exposed wall cells. Veins grow over wall cells; richer deeper and farther from a town."""
    od = rules["ore"]
    d6 = np.array([1, -1, NY, -NY, region.nz * NY, -region.nz * NY], np.int64)
    nb = (carved_keys[:, None] + d6[None, :]).ravel()
    nb = np.unique(nb)
    pos = np.searchsorted(carved_keys, nb)
    pos[pos >= len(carved_keys)] = len(carved_keys) - 1
    wall = nb[carved_keys[pos] != nb]
    wx, wy, wz = region.unkey(wall)
    ix, iz = wx - region.x0, wz - region.z0
    ok = (ix >= 0) & (ix < region.shape[1]) & (iz >= 0) & (iz < region.shape[0])
    wall, wx, wy, wz, ix, iz = wall[ok], wx[ok], wy[ok], wz[ok], ix[ok], iz[ok]
    g = region.H[iz, ix]
    cover = g - wy
    ok = cover >= od["min_cover"]
    wall, wx, wy, wz, cover = wall[ok], wx[ok], wy[ok], wz[ok], cover[ok]
    dt = town_dist(wx, wz)
    rich = od["rich_base"] + od["rich_depth"] * np.clip((cover - 20) / 140.0, 0, 1) + od["rich_far"] * np.clip(dt / 1000.0, 0, 1)
    u = hash01(wx, wy, wz, seed + 101)
    centre = u < od["centre_rate"] * rich
    cx, cy, cz, cr = wx[centre], wy[centre], wz[centre], rich[centre]
    types = ore_table(rules)
    wallset = {int(k): (int(x), int(y), int(z)) for k, x, y, z in zip(wall, wx, wy, wz)}
    taken = {}
    out = []
    order = np.argsort(hash01(cx, cy, cz, seed + 102))
    for q in order:
        x, y, z, r = int(cx[q]), int(cy[q]), int(cz[q]), float(cr[q])
        avail = [t for t in types if t["y_min"] <= y <= t["y_max"]]
        if not avail:
            continue
        wts = [t["weight"] * (1 + (t["depth_gain"] * (r - 1) if t.get("depth_gain") else 0)) for t in avail]
        pick = hash01(x, y, z, seed + 103) * sum(wts)
        acc = 0.0
        t = avail[-1]
        for tt, ww in zip(avail, wts):
            acc += ww
            if pick <= acc:
                t = tt
                break
        size = int(t["vein"] * (0.6 + 0.8 * hash01(x, y, z, seed + 104)))
        cells = [(x, y, z)]
        seenv = {(x, y, z)}
        k = 0
        while k < len(cells) and len(cells) < size:
            cx0, cy0, cz0 = cells[k]
            k += 1
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        p = (cx0 + dx, cy0 + dy, cz0 + dz)
                        if p in seenv or len(cells) >= size:
                            continue
                        seenv.add(p)
                        key = int(region.key(np.array([p[0]]), np.array([p[1]]), np.array([p[2]]))[0])
                        if key in wallset and key not in taken and t["y_min"] <= p[1] <= t["y_max"] and hash01(p[0], p[1], p[2], seed + 105) < 0.75:
                            cells.append(p)
        for p in cells:
            key = int(region.key(np.array([p[0]]), np.array([p[1]]), np.array([p[2]]))[0])
            if key in wallset and key not in taken and t["y_min"] <= p[1] <= t["y_max"]:
                block = t["deepslate"] if p[1] < 0 else t["stone"]
                taken[key] = block
                out.append((p[0], p[1], p[2], block))
    return out


def lantern_cells(net, region, mouths, carved_set, rules):
    """Lanterns on the floor of each mouth passage: a few, spaced along the first 28 blocks inside the surface."""
    out = []
    for m in mouths:
        br = [b for b in net.branches if b["start"] == m["node"] and b["kind"] == "mouth"]
        if not br:
            continue
        nodes = [m["node"]] + br[0]["nodes"]
        for want in rules["light"]["at_nodes"]:
            if want >= len(nodes):
                continue
            n = net.n[nodes[want]]
            nxt = net.n[nodes[min(want + 1, len(nodes) - 1)]]
            dx, dz = nxt[0] - n[0], nxt[2] - n[2]
            ln = math.hypot(dx, dz) or 1.0
            px, pz = -dz / ln, dx / ln
            yf = int(round(n[1]))
            found = None
            for side in (1, -1):
                for off in (n[3] / 2.0 - 1.2, n[3] / 2.0 - 2.0, 1.0):
                    x, z = int(round(n[0] + px * side * off)), int(round(n[2] + pz * side * off))
                    for y in (yf, yf + 1, yf - 1):
                        if (x, y, z) in carved_set and (x, y - 1, z) not in carved_set and (x, y + 1, z) in carved_set:
                            found = (x, y, z)
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                out.append(found)
    return out


# ------------------------------------------------------------------ meshing and the pack

def mesh_layer_boxes(mask):
    """Greedy boxes (x0, y0, z0, x1, y1, z1) in the array's own index space, mask indexed [y][z][x]."""
    boxes = []
    ny = mask.shape[0]
    prev = {}
    for y in range(ny + 1):
        cur = {}
        if y < ny:
            rects = _layer_rects(mask[y])
            for r in rects:
                cur[r] = prev.pop(r, y)
        for r, y0 in prev.items():
            boxes.append((r[0], y0, r[2], r[1], y - 1, r[3]))
        prev = cur
    return boxes


def _layer_rects(m2):
    """[(x0, x1, z0, z1)] covering a 2D bool [z][x]: row runs merged down while the run is identical."""
    nz, nx = m2.shape
    out = []
    openr = {}
    for z in range(nz + 1):
        runs = set()
        if z < nz:
            row = m2[z]
            if row.any():
                d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
                st, en = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1
                runs = set(zip(st.tolist(), en.tolist()))
        for r in list(openr):
            if r not in runs:
                out.append((r[0], r[1], openr.pop(r), z - 1))
        for r in runs:
            openr.setdefault(r, z)
    return out


def split_big(b, limit=32000):
    x0, y0, z0, x1, y1, z1 = b
    v = (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1)
    if v <= limit:
        return [b]
    dims = [(x1 - x0, 0), (y1 - y0, 1), (z1 - z0, 2)]
    _, ax = max(dims)
    lo = [x0, y0, z0]
    hi = [x1, y1, z1]
    mid = (lo[ax] + hi[ax]) // 2
    a = list(hi)
    a[ax] = mid
    c = list(lo)
    c[ax] = mid + 1
    return split_big((lo[0], lo[1], lo[2], a[0], a[1], a[2]), limit) + split_big((c[0], c[1], c[2], hi[0], hi[1], hi[2]), limit)


def tile_of(x, z, tile):
    return (x // tile, z // tile)


def dilate_cube(m, r):
    """3D boolean Chebyshev dilation by r over an array [y][z][x]."""
    out = m
    for ax in (0, 1, 2):
        acc = out.copy()
        for s in range(1, r + 1):
            sl_a = [slice(None)] * 3
            sl_b = [slice(None)] * 3
            sl_a[ax] = slice(s, None)
            sl_b[ax] = slice(None, -s)
            acc[tuple(sl_a)] |= out[tuple(sl_b)]
            acc[tuple(sl_b)] |= out[tuple(sl_a)]
        out = acc
    return out


def stone_for(y):
    return "minecraft:deepslate" if y < 0 else "minecraft:stone"


def fill_line(b, block, flt=None):
    s = "fill %d %d %d %d %d %d %s" % (b[0], b[1], b[2], b[3], b[4], b[5], block)
    return s + (" replace %s" % flt if flt else "")


def tile_functions(sysid, region, rules, cx, cy, cz, ores, lanterns, base=None):
    """{name: lines} for every tile with carve cells or shell cells. cx, cy, cz: int arrays of every carved cell. `base`: the
    (x, y, z) arrays of the live 2026-10-22 carve, a subset of the cells; given, a tile's `_air` carves exactly its base cells
    (the live lines) and `_wide` the rest, and the carve chain runs both before and after the shell."""
    T_ = rules["tile"]
    sh = rules["shell"]
    files = {}
    stats = {"air_lines": 0, "shell_lines": 0, "ore_lines": 0, "lantern_lines": 0, "wide_lines": 0}
    tx_all, tz_all = cx // T_, cz // T_
    tiles = set(zip(tx_all.tolist(), tz_all.tolist()))
    # the shell reaches `sh` into the neighbours
    shell_tiles = set()
    for (tx, tz) in tiles:
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                shell_tiles.add((tx + dx, tz + dz))
    ymin, ymax = int(cy.min()), int(cy.max())
    CB = rules["shell_block"]                      # the shell is meshed in CB-sized blocks (an over-approximation of the ring)
    oy = ((ymin - sh) // CB) * CB
    ny = ((ymax + sh - oy) // CB + 1) * CB
    ore_by = {}
    for (x, y, z, b) in ores:
        ore_by.setdefault((x // T_, z // T_), []).append((x, y, z, b))
    lan_by = {}
    for (x, y, z) in lanterns:
        lan_by.setdefault((x // T_, z // T_), []).append((x, y, z))
    order = sorted(shell_tiles)
    for (tx, tz) in order:
        x0, z0 = tx * T_, tz * T_
        # dense carve array with a halo of `sh`
        sel = (cx >= x0 - sh) & (cx < x0 + T_ + sh) & (cz >= z0 - sh) & (cz < z0 + T_ + sh)
        if not sel.any():
            continue
        arr = np.zeros((ny, T_ + 2 * sh, T_ + 2 * sh), bool)
        arr[cy[sel] - oy, cz[sel] - (z0 - sh), cx[sel] - (x0 - sh)] = True
        inner = arr[:, sh:sh + T_, sh:sh + T_]
        shell = dilate_cube(arr, sh)[:, sh:sh + T_, sh:sh + T_]
        own = inner
        name = "%s_%d_%d" % (sysid, tx, tz)
        head = ["# Generated by %s from data/cave_systems.json: system %s, tile %d,%d (x %d..%d, z %d..%d)" % (GENERATED, sysid, tx, tz, x0, x0 + T_ - 1, z0, z0 + T_ - 1),
                "# chunks-loaded-by: the re-application (forceload add over RCON before this runs)"]
        # shell: water and lava in the carved cells and the ring round them become stone (deepslate under y0)
        lines = list(head)
        if shell.any():
            coarse = shell.reshape(ny // CB, CB, T_ // CB, CB, T_ // CB, CB).any(axis=(1, 3, 5))
            yy = (np.arange(ny // CB) * CB + oy)
            for blk, sel_y in (("minecraft:deepslate", yy < 0), ("minecraft:stone", yy >= 0)):
                m = coarse.copy()
                m[~sel_y] = False
                if not m.any():
                    continue
                for b in mesh_layer_boxes(m):
                    for bb in split_big((b[0] * CB, b[1] * CB, b[2] * CB, b[3] * CB + CB - 1, b[4] * CB + CB - 1, b[5] * CB + CB - 1)):
                        box = (bb[0] + x0, bb[1] + oy, bb[2] + z0, bb[3] + x0, bb[4] + oy, bb[5] + z0)
                        lines.append(fill_line(box, blk, "minecraft:water"))
                        lines.append(fill_line(box, blk, "minecraft:lava"))
                        stats["shell_lines"] += 2
        files[name + "_shell"] = lines
        if own.any():
            if base is None:
                own_base, own_wide = own, None
            else:
                bsel = (base[0] >= x0) & (base[0] < x0 + T_) & (base[2] >= z0) & (base[2] < z0 + T_)
                own_base = np.zeros_like(own)
                own_base[base[1][bsel] - oy, base[2][bsel] - z0, base[0][bsel] - x0] = True
                own_wide = own & ~own_base
            calls = []
            if own_base.any():
                air = list(head)
                air[0] = air[0].replace("system", "carve air for system")
                for b in mesh_layer_boxes(own_base):
                    for bb in split_big(b):
                        box = (bb[0] + x0, bb[1] + oy, bb[2] + z0, bb[3] + x0, bb[4] + oy, bb[5] + z0)
                        air.append(fill_line(box, AIR))
                        stats["air_lines"] += 1
                files[name + "_air"] = air
                calls.append("function %s/%s_air" % (F, name))
            if own_wide is not None and own_wide.any():
                wide = list(head)
                wide[0] = wide[0].replace("system", "carve the 2026-10-23 widening and nest rooms for system")
                for b in mesh_layer_boxes(own_wide):
                    for bb in split_big(b):
                        box = (bb[0] + x0, bb[1] + oy, bb[2] + z0, bb[3] + x0, bb[4] + oy, bb[5] + z0)
                        wide.append(fill_line(box, AIR))
                        stats["wide_lines"] += 1
                files[name + "_wide"] = wide
                calls.append("function %s/%s_wide" % (F, name))
            dress = list(head)
            dress[0] = dress[0].replace("system", "ore and light for system")
            for (x, y, z, b) in sorted(ore_by.get((tx, tz), ())):
                dress.append("fill %d %d %d %d %d %d %s replace %s" % (x, y, z, x, y, z, b, BASE_STONE))
                stats["ore_lines"] += 1
            for (x, y, z) in sorted(lan_by.get((tx, tz), ())):
                dress.append("setblock %d %d %d %s" % (x, y, z, LANTERN))
                stats["lantern_lines"] += 1
            files[name + "_dress"] = dress
            files[name + "_carve"] = (list(head[:1]) + head[1:]
                                      + ["# carve, shell, carve again (the shell must not leave water or lava where the passage is), then dress"]
                                      + calls + ["function %s/%s_shell" % (F, name)]
                                      + (calls if CARVE_AGAIN else [])
                                      + ["function %s/%s_dress" % (F, name)])
    return files, stats


# ------------------------------------------------------------------ one system, end to end

MAX_ATTEMPTS = 8


def walk_problems(res):
    """[problem] if the generated volume cannot be walked: every mouth must reach every other and 99% of the standing cells. The
    same rule the audit applies, here so a seed that cuts a ledge is rejected and the next tried (deterministically) instead of written."""
    reg = res["region"]
    cells = set(zip(res["x"].tolist(), res["y"].tolist(), res["z"].tolist()))
    stand = standing_cells(cells, reg.gnd)
    probs = []
    first = None
    for m in res["mouths"]:
        near = [p for p in stand if abs(p[0] - m["x"]) <= 3 and abs(p[2] - m["z"]) <= 3]
        if not near:
            probs.append("mouth %s: nowhere to stand" % m["id"])
            continue
        d = walk_from(stand, cells, max(near, key=lambda p: p[1]), reg.gnd)
        if first is None:
            first = d
        elif max(near, key=lambda p: p[1]) not in first:
            probs.append("mouth %s cannot be walked to from the first" % m["id"])
    if first is not None and len(first) < 0.99 * len(stand):
        probs.append("only %d of %d standing cells can be walked to" % (len(first), len(stand)))
    res["walk_far"] = max(first.values()) if first else 0
    return probs


def generate(spec, sysspec, g=None, region=None, widen=None, rooms=None):
    """Plan and voxelise one system, trying seeds until one can be walked end to end (at most MAX_ATTEMPTS, a fixed order, so the
    result is reproducible). Fails closed with every attempt's reasons. That is the BASE, the live 2026-10-22 carve; it is
    checked against data/cave_systems.json live_carve and then (WIDEN) widened and given its nest rooms, additively."""
    g = g or G.Ground()
    region = region or Region(spec["rules"], sysspec, g)
    log = []
    for attempt in range(MAX_ATTEMPTS):
        res = generate_once(spec, sysspec, g, region, attempt)
        probs = walk_problems(res)
        if not probs:
            res["attempt"] = attempt
            res["rejected"] = log
            if CHECK_LIVE:
                check_live(spec, sysspec, res)
            if WIDEN if widen is None else widen:
                widen_system(spec, sysspec, res, rooms)
            return res
        log.append("attempt %d: %s" % (attempt, "; ".join(probs)))
    raise CaveSystemError("%s: no seed in %d attempts gave a walkable system: %s" % (sysspec["id"], MAX_ATTEMPTS, " | ".join(log)))


def generate_once(spec, sysspec, g, region, attempt=0):
    """One attempt at a system. Returns a dict: net, caverns, halls, carved (x, y, z arrays), ore, lanterns, stats, region."""
    rules = spec["rules"]
    b = Builder(spec, sysspec, region, attempt)
    net = b.run()
    caverns = b.place_caverns()
    b.blend_to_caverns()
    halls = b.halls()
    seed = b.seed
    tx_, ty_, tz_ = tube_cells(net, seed, rules)
    parts = [(tx_, ty_, tz_)]
    for c in caverns:
        parts.append(cavern_cells(c, seed, region))
    for h in halls:
        parts.append(hall_cells(h, seed))
    X = np.concatenate([p[0] for p in parts])
    Y = np.concatenate([p[1] for p in parts])
    Z = np.concatenate([p[2] for p in parts])
    zone = mouth_zone_mask(region, b.mouths, rules["mouth_zone"])
    keep, removed = clip_cells(region, rules, X, Y, Z, zone)
    X, Y, Z = X[keep], Y[keep], Z[keep]
    keys = np.unique(region.key(X, Y, Z))
    # drop what does not connect to a mouth
    starts = []
    for m in b.mouths:
        n = net.n[m["node"]]
        for dy in range(0, 4):
            starts.append(int(region.key(np.array([int(round(n[0]))]), np.array([int(round(n[1])) + dy]), np.array([int(round(n[2]))]))[0]))
    starts = np.unique(np.array(starts, np.int64))
    seen = flood_from(region, keys, starts)
    dropped = int((~seen).sum())
    keys = keys[seen]
    cx, cy, cz = region.unkey(keys)
    carved_set = set(zip(cx.tolist(), cy.tolist(), cz.tolist()))
    carved_set, repaired = repair_steps(carved_set, (b.mouths[0]["x"], b.mouths[0]["z"]), region.gnd)
    if repaired:
        arr = np.array(sorted(carved_set), np.int64)
        cx, cy, cz = arr[:, 0], arr[:, 1], arr[:, 2]
        keys = np.unique(region.key(cx, cy, cz))
        cx, cy, cz = region.unkey(keys)
    ores = dress_ore(region, rules, seed, keys, zone)
    lants = lantern_cells(net, region, b.mouths, carved_set, rules)
    return {"builder": b, "net": net, "caverns": caverns, "halls": halls, "keys": keys, "x": cx.astype(np.int64), "y": cy.astype(np.int64),
            "z": cz.astype(np.int64), "ores": ores, "lanterns": lants, "region": region, "removed": removed, "disconnected": dropped, "repaired": repaired,
            "mouths": b.mouths}


def flood_from(region, keys, starts):
    """Boolean over `keys` (sorted, unique): True for every cell 6-connected to a cell of `starts`."""
    n = len(keys)
    pos = np.array([p for p, s in zip(np.searchsorted(keys, starts), starts) if p < n and keys[p] == s], np.int64)
    seen = np.zeros(n, bool)
    frontier = np.unique(pos)
    seen[frontier] = True
    deltas = np.array([1, -1, NY, -NY, region.nz * NY, -region.nz * NY], np.int64)
    while len(frontier):
        nb = (keys[frontier][:, None] + deltas[None, :]).ravel()
        p = np.searchsorted(keys, nb)
        p[p >= n] = n - 1
        hit = keys[p] == nb
        p = np.unique(p[hit])
        p = p[~seen[p]]
        seen[p] = True
        frontier = p
    return seen


NB4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def standing_cells(cells, gnd):
    """Cells a player can stand in: this one is carved, the one above is open (carved, or above the ground), the one below is rock."""
    out = set()
    for c in cells:
        x, y, z = c
        g = gnd(x, z)
        if ((x, y + 1, z) in cells or y + 1 > g) and (x, y - 1, z) not in cells and y - 1 <= g:
            out.add(c)
    return out


def walk_from(stand, cells, src, gnd):
    """{standing cell: steps} from `src`, one block at a time: up one with headroom, level, down to three."""
    dist = {src: 0}
    q = deque([src])
    while q:
        x, y, z = q.popleft()
        d = dist[(x, y, z)]
        for dx, dz in NB4:
            for dy in (0, 1, -1, -2, -3):
                p = (x + dx, y + dy, z + dz)
                if p in dist or p not in stand:
                    continue
                if dy == 1 and not ((x, y + 2, z) in cells or y + 2 > gnd(x, z)):
                    continue
                if dy < 0 and not ((x + dx, y + 1, z + dz) in cells or y + 1 > gnd(x + dx, z + dz)):
                    continue
                dist[p] = d + 1
                q.append(p)
                break
    return dist


def repair_steps(cells, src_xz, gnd, max_iter=80):
    """Lower the floor of a standing cell that can only be reached by climbing two or more: carve the one cell under it (the cover
    only grows). Returns (cells, number of cells carved). `src_xz`: (x, z) of the mouth the walk starts from."""
    carved = 0
    for _ in range(max_iter):
        stand = standing_cells(cells, gnd)
        near = [p for p in stand if abs(p[0] - src_xz[0]) <= 3 and abs(p[2] - src_xz[1]) <= 3]
        if not near:
            return cells, carved
        reached = walk_from(stand, cells, max(near, key=lambda p: p[1]), gnd)
        add = set()
        for (x, y, z) in stand:
            if (x, y, z) in reached:
                continue
            for dx, dz in NB4:
                for dy in range(2, 9):
                    if (x + dx, y - dy, z + dz) in reached:
                        add.add((x, y - 1, z))
        if not add:
            return cells, carved
        cells = cells | add
        carved += len(add)
    return cells, carved


def centreline_length(net):
    """Blocks of centreline: the 3D length of every graph edge."""
    return net.length


# ------------------------------------------------------------------ 2026-10-23: wider passages and nest rooms, ADDITIVE ONLY
#
# The 2026-10-22 carve (the "base": everything above, unchanged) is in the live world. What follows only ever ADDS air to it:
# the base cells are kept whole and the pack still carves them in their own `_air` functions (whose cells the audit digests
# against data/cave_systems.json live_carve), and the new cells go in `_wide` functions. Rules for every added cell:
#   - cover >= cover_min EVERYWHERE (the mouth-zone relaxation is not extended) and no added cell within mouth_zone of a
#     mouth, so the mouths and the hillside outside them are exactly as carved (another builder works on the mouths' outside);
#   - unblocked (authored 32, water 12, the limits: the same blocked grid), above the floor limit;
#   - DECKS: every cell carries the floor of the vertical run it belongs to; an added cell within deck_gap (Chebyshev) of any
#     carved cell whose floor differs by more than deck_tolerance is dropped, so widening never opens one level into another
#     (no new hole, ledge or drop); a cell two separate widened runs both claim is dropped too;
#   - never at or under a base lantern; connected to a mouth; then the walk (every mouth, 99% of the standing cells) and the
#     TRAP check (every standing cell reached can walk back out of some mouth) must pass, or the build fails closed.

def cells_digest(x, y, z):
    """sha256 of the cell set: int32 little-endian (x, y, z) triples sorted by x, then y, then z (the definition
    data/cave_systems.json live_carve states; the audit computes it for itself from the replayed pack)."""
    a = np.stack([np.asarray(x, np.int64), np.asarray(y, np.int64), np.asarray(z, np.int64)], axis=1)
    o = np.lexsort((a[:, 2], a[:, 1], a[:, 0]))
    return hashlib.sha256(np.ascontiguousarray(a[o]).astype("<i4").tobytes()).hexdigest()


def check_live(spec, sysspec, res):
    """The base must be the live carve, cell for cell: a re-plan (a data change within the plan's reach, a code change) would
    carve a different network over the one that is in the world. Fails closed."""
    rec = ((spec.get("live_carve") or {}).get("systems") or {}).get(sysspec["id"])
    if not rec:
        return
    n = int(len(res["x"]))
    dg = cells_digest(res["x"], res["y"], res["z"])
    if n != rec["cells"] or dg != rec["sha256"]:
        raise CaveSystemError("%s: the base plan no longer reproduces the live carve (%d cells, sha256 %s..., live %d, %s...): something "
                              "within the plan's reach changed (an authored point or box, water, the heightmap, this tool). Re-running R9CS "
                              "would carve a different network over the one in the world; find the change before building"
                              % (sysspec["id"], n, dg[:12], rec["cells"], rec["sha256"][:12]))


def width_targets(net, seed, rules, mouths):
    """(W, Hh) per node: the widened width and headroom. A smooth seeded field (value noise over `noise_scale` blocks) ranked
    over the system's nodes, so the shares are exact: the lowest `share_squeeze` keep their own width (the squeezes), the
    next ones spread over `typical`, the top `share_wide` over typical's top to width's top. Never narrower than the base
    node; tapered back to the base width over `mouth_taper` blocks outside each mouth zone."""
    wr = rules["widen"]
    P = np.array([[q[0], q[1], q[2], q[3], q[4]] for q in net.n], np.float64)
    n = len(P)
    u = vnoise(P[:, 0], P[:, 1], P[:, 2], seed + 77, float(wr["noise_scale"]))
    rank = np.empty(n)
    rank[np.argsort(u, kind="stable")] = np.arange(n) / max(1.0, n - 1.0)
    sq, wide = wr["share_squeeze"], wr["share_wide"]
    t_lo, t_hi = wr["typical"]
    w_top = wr["width"][1]
    t = np.where(rank < sq, 0.0,
                 np.where(rank < 1 - wide, t_lo + (t_hi - t_lo) * (rank - sq) / max(1e-9, 1 - wide - sq),
                          t_hi + (w_top - t_hi) * (rank - (1 - wide)) / max(1e-9, wide)))
    dm = np.full(n, 1e9)
    for m in mouths:
        dm = np.minimum(dm, np.hypot(P[:, 0] - m["x"], P[:, 2] - m["z"]))
    f = np.clip((dm - rules["mouth_zone"]) / float(wr["mouth_taper"]), 0.0, 1.0)
    W = P[:, 3] + f * np.maximum(0.0, t - P[:, 3])
    W = np.minimum(W, foreign_caps(net, P, wr))
    hn = vnoise(P[:, 0], P[:, 1], P[:, 2], seed + 78, 31.0)
    Hh = np.clip(3.2 + 0.55 * W + 1.6 * (hn - 0.5) * 2, rules["height"][0], wr["height_max"])
    return W, np.maximum(Hh, P[:, 4])


def foreign_caps(net, P, wr):
    """The widest each node may become so that it keeps `rock_between` blocks of rock from every node of ANOTHER passage (one more
    than `own_reach` blocks away along the network) within 14 vertically: the gap beyond the two carved half-widths (x 1.3 for the
    wall noise) is shared half and half. Passages that already touch keep their own width."""
    n = len(P)
    adj = {}
    for i, j in net.edges:
        d = math.dist(P[i], P[j])
        adj.setdefault(i, []).append((j, d))
        adj.setdefault(j, []).append((i, d))
    reach = float(wr["own_reach"])
    rock = float(wr["rock_between"])
    cap = np.full(n, 1e9)
    bucket = {}
    for i in range(n):
        bucket.setdefault((int(P[i, 0]) // 16, int(P[i, 2]) // 16), []).append(i)
    import heapq
    for i in range(n):
        own = {i: 0.0}
        hq = [(0.0, i)]
        while hq:
            d, a = heapq.heappop(hq)
            if d > own.get(a, 1e9):
                continue
            for b, w in adj.get(a, ()):
                nd = d + w
                if nd <= reach and nd < own.get(b, 1e9):
                    own[b] = nd
                    heapq.heappush(hq, (nd, b))
        bx, bz = int(P[i, 0]) // 16, int(P[i, 2]) // 16
        rb_i = P[i, 3] / 2.0 * 1.3
        for ax in (bx - 2, bx - 1, bx, bx + 1, bx + 2):
            for az in (bz - 2, bz - 1, bz, bz + 1, bz + 2):
                for j in bucket.get((ax, az), ()):
                    if j in own or abs(P[j, 1] - P[i, 1]) >= 14:
                        continue
                    dh = math.hypot(P[j, 0] - P[i, 0], P[j, 2] - P[i, 2])
                    if dh > 30:
                        continue
                    slack = dh - rock - rb_i - P[j, 3] / 2.0 * 1.3
                    cap[i] = min(cap[i], max(P[i, 3], 2.0 * (rb_i + slack / 2.0) / 1.3))
    return cap


def wide_columns(net, seed, W, Hh, wmax, hmax, step=1.0):
    """Column runs (x, z, floor, top exclusive) of the passages swept at the widened sizes, with the base sweep's own wall noise."""
    segs = []
    for (i, j) in net.edges:
        a, b = net.n[i], net.n[j]
        d = math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)
        n = max(2, int(math.ceil(d / step)))
        t = np.linspace(0.0, 1.0, n + 1)
        segs.append(np.stack([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t,
                              W[i] + (W[j] - W[i]) * t, Hh[i] + (Hh[j] - Hh[i]) * t], axis=1))
    S = np.concatenate(segs)
    px, py, pz, w, h = S[:, 0], S[:, 1], S[:, 2], S[:, 3], S[:, 4]
    cxs, czs, yf = np.round(px).astype(np.int64), np.round(pz).astype(np.int64), np.round(py).astype(np.int64)
    rr = w / 2.0                 # the base sweep's 1.12 left out: a widened node measures about its nominal width, walls +-16%
    R = int(math.ceil(wmax / 2.0 * 1.2)) + 1
    ox, oz, of, ot = [], [], [], []
    for dx in range(-R, R + 1):
        for dz in range(-R, R + 1):
            x = cxs + dx
            z = czs + dz
            d = np.hypot(x - px, z - pz)
            reff = rr * (0.84 + 0.32 * vnoise(x, yf, z, seed + 3, 5.0))
            ok = d < reff
            if not ok.any():
                continue
            frac = (d[ok] / reff[ok]) ** 2.4
            hc = np.minimum(np.floor(h[ok] * np.sqrt(np.maximum(0.0, 1 - frac)) + 0.35).astype(np.int64), int(hmax) + 1)
            m = hc > 0
            ox.append(x[ok][m])
            oz.append(z[ok][m])
            of.append(yf[ok][m])
            ot.append(yf[ok][m] + hc[m])
    return np.concatenate(ox), np.concatenate(oz), np.concatenate(of), np.concatenate(ot)


def column_cells(region, X, Z, F, T):
    """Cells (x, y, z, deck) of column runs: runs in one column whose floors chain within 4 merge (one passage on a slope), the
    run's floor is the lowest of them, its top the highest; runs further apart stay separate (separate passages)."""
    col = (X - region.x0) * region.nz + (Z - region.z0)
    o = np.lexsort((F, col))
    col, F, T = col[o], F[o], T[o]
    new = np.r_[True, (col[1:] != col[:-1]) | (F[1:] - F[:-1] > 4)]
    st = np.nonzero(new)[0]
    floor = F[st]
    top = np.maximum.reduceat(T, st)
    gcol = col[st]
    hgt = np.maximum(0, top - floor)
    rep = np.repeat(np.arange(len(floor)), hgt)
    offs = np.arange(len(rep)) - np.repeat(np.cumsum(hgt) - hgt, hgt)
    colc = gcol[rep]
    return colc // region.nz + region.x0, floor[rep] + offs, colc % region.nz + region.z0, floor[rep]


def run_floors(keys):
    """The floor (lowest y) of the vertical run each of the sorted unique keys belongs to, as an offset in y - Y_MIN."""
    st = np.r_[True, np.diff(keys) != 1]
    rid = np.cumsum(st) - 1
    return (keys[st] % NY)[rid] + Y_MIN


def deck_mismatch(region, keys, deck, test, tol, gap, tile=128):
    """bool over `test` (indices into keys): True where a carved cell within `gap` (Chebyshev) has a deck more than `tol` away."""
    X, Y, Z = region.unkey(keys)
    out = np.zeros(len(test), bool)
    if not len(test):
        return out
    tx, tz = X[test] // tile, Z[test] // tile
    for (a, b) in sorted(set(zip(tx.tolist(), tz.tolist()))):
        x0, z0 = a * tile - gap, b * tile - gap
        n_ = tile + 2 * gap
        sel = (X >= x0) & (X < x0 + n_) & (Z >= z0) & (Z < z0 + n_)
        y0 = int(Y[sel].min()) - gap
        ny = int(Y[sel].max()) - y0 + gap + 1
        hi = np.full((ny, n_, n_), -30000, np.int32)
        lo = np.full((ny, n_, n_), 30000, np.int32)
        iy, iz, ix = Y[sel] - y0, Z[sel] - z0, X[sel] - x0
        np.maximum.at(hi, (iy, iz, ix), deck[sel])
        np.minimum.at(lo, (iy, iz, ix), deck[sel])
        for ax in range(3):
            ah, al = hi.copy(), lo.copy()
            for s in range(1, gap + 1):
                a_ = [slice(None)] * 3
                b_ = [slice(None)] * 3
                a_[ax] = slice(s, None)
                b_[ax] = slice(None, -s)
                ah[tuple(a_)] = np.maximum(ah[tuple(a_)], hi[tuple(b_)])
                ah[tuple(b_)] = np.maximum(ah[tuple(b_)], hi[tuple(a_)])
                al[tuple(a_)] = np.minimum(al[tuple(a_)], lo[tuple(b_)])
                al[tuple(b_)] = np.minimum(al[tuple(b_)], lo[tuple(a_)])
            hi, lo = ah, al
        mine = np.nonzero((tx == a) & (tz == b))[0]
        q = test[mine]
        d = deck[q]
        jy, jz, jx = Y[q] - y0, Z[q] - z0, X[q] - x0
        out[mine] = (hi[jy, jz, jx] - d > tol) | (d - lo[jy, jz, jx] > tol)
    return out


def nest_room_cells(room, seed):
    """(x, y, z) of a nest room and its spur: an elliptical room with a flat floor at `centre` y (the lowest air), a dome to
    `tall`, mildly noisy walls; the spur a straight flat passage from `spur[0]` (in the parent passage) into the room."""
    cx, yf, cz = room["centre"]
    a, b = room["radius"]
    ang, tall = room["angle"], room["tall"]
    ca, sa = math.cos(ang), math.sin(ang)
    ext = int(max(a, b) * 1.25) + 2
    xs = np.arange(cx - ext, cx + ext + 1)
    zs = np.arange(cz - ext, cz + ext + 1)
    X, Z = np.meshgrid(xs, zs)
    u = ((X - cx) * ca + (Z - cz) * sa) / a
    v = (-(X - cx) * sa + (Z - cz) * ca) / b
    rr = np.sqrt(u * u + v * v) * (1 + room["wall_noise"] * (vnoise(X, 0, Z, seed + 91, 6.0) - 0.5) * 2)
    inside = rr < 1.0
    hc = np.maximum(3, np.floor(tall * np.sqrt(np.maximum(0.0, 1 - rr * rr)) + 0.5)).astype(np.int64)
    ox, oy, oz = [], [], []
    for k in range(int(tall) + 1):
        m = inside & (hc > k)
        ox.append(X[m])
        oz.append(Z[m])
        oy.append(np.full(int(m.sum()), yf + k))
    (sx, sy, sz), (ex, _ey, ez) = room["spur"][0], room["spur"][1]
    L = math.hypot(ex - sx, ez - sz)
    hw = room["spur_width"] / 2.0
    pad = int(math.ceil(hw)) + 1
    gx = np.arange(int(min(sx, ex)) - pad, int(max(sx, ex)) + pad + 1)
    gz = np.arange(int(min(sz, ez)) - pad, int(max(sz, ez)) + pad + 1)
    GX, GZ = np.meshgrid(gx, gz)
    t = np.clip(((GX - sx) * (ex - sx) + (GZ - sz) * (ez - sz)) / max(1e-9, L * L), 0, 1)
    on = np.hypot(GX - (sx + t * (ex - sx)), GZ - (sz + t * (ez - sz))) <= hw
    for k in range(int(room["spur_height"])):
        ox.append(GX[on])
        oz.append(GZ[on])
        oy.append(np.full(int(on.sum()), yf + k))
    X_, Y_, Z_ = np.concatenate(ox), np.concatenate(oy), np.concatenate(oz)
    k_ = np.unique((X_.astype(np.int64) * 8192 + Z_) * 1024 + (Y_ + 512))
    return (k_ // 1024) // 8192, k_ % 1024 - 512, (k_ // 1024) % 8192


def room_only_cells(room, seed):
    """The room's own cells without the spur (for its clearance)."""
    r = dict(room, spur=[room["centre"], room["centre"]], spur_height=0)
    return nest_room_cells(r, seed)


def offsets_cube(r):
    return [(dx, dy, dz) for dx in range(-r, r + 1) for dy in range(-r, r + 1) for dz in range(-r, r + 1)]


def any_near(region, keys_sorted, X, Y, Z, r):
    """bool per cell: a key of keys_sorted lies within r (Chebyshev) of it."""
    out = np.zeros(len(X), bool)
    if not len(keys_sorted) or not len(X):
        return out
    for dx, dy, dz in offsets_cube(r):
        k = region.key(X + dx, Y + dy, Z + dz)
        p = np.searchsorted(keys_sorted, k)
        p[p >= len(keys_sorted)] = len(keys_sorted) - 1
        out |= keys_sorted[p] == k
    return out


def room_problems(region, rules, room, seed, others, mouths):
    """[problem] for one recorded room against the carved cells `others` (sorted keys, the room excluded): every cell kept by
    the rules, the room `room_clear` from everything, the spur `spur_clear` from everything past its first cells, the
    spawner's box free of every other carved cell, the block a rock cell under an open floor."""
    nr = rules["nests"]
    out = []
    X, Y, Z = nest_room_cells(room, seed)
    keep, _rm = clip_cells(region, rules, X, Y, Z, np.zeros(region.shape, bool))
    if not keep.all():
        out.append("%s: %d of its %d cells break the cover, blocked or floor rule" % (room["id"], int((~keep).sum()), len(X)))
    for m in mouths:
        if (np.hypot(X - m["x"], Z - m["z"]) <= rules["mouth_zone"] + rules["nests"]["mouth_clear"]).any():
            out.append("%s: inside a mouth zone" % room["id"])
            break
    RX, RY, RZ = room_only_cells(room, seed)
    if any_near(region, others, RX, RY, RZ, nr["room_clear"]).any():
        out.append("%s: the room comes within %d of another carved cell" % (room["id"], nr["room_clear"]))
    sx, sy, sz = room["spur"][0]
    far = np.hypot(X - sx, Z - sz) > room["attach_radius"]
    if any_near(region, others, X[far], Y[far], Z[far], nr["spur_clear"]).any():
        out.append("%s: the spur comes within %d of another carved cell past its attachment" % (room["id"], nr["spur_clear"]))
    bx, by, bz = room["block"]
    sr = room["spawn_range"]
    bxs, bys, bzs = np.meshgrid(np.arange(bx - sr, bx + sr + 1), np.arange(by - sr, by + sr + 1), np.arange(bz - sr, bz + sr + 1), indexing="ij")
    kb = region.key(bxs.ravel(), bys.ravel(), bzs.ravel())
    p = np.searchsorted(others, kb)
    p[p >= len(others)] = len(others) - 1
    if len(others) and (others[p] == kb).any():
        out.append("%s: another carved cell is inside the Habitat Block's spawn box (spawn_range %d)" % (room["id"], sr))
    cells = set(zip(X.tolist(), Y.tolist(), Z.tolist()))
    if (bx, by, bz) in cells or (bx, by + 1, bz) not in cells or (bx, by + 2, bz) not in cells:
        out.append("%s: the block %s is not a rock cell under an open floor" % (room["id"], (bx, by, bz)))
    return out


def added_allowed(region, rules, mouths, X, Y, Z):
    """bool per candidate added cell: unblocked, cover_min of rock EVERYWHERE, above the floor limit, outside every mouth zone.
    A hook: tests/test_cave_systems.py swaps it for the base's mouth-zone rule to prove the audit sees cells added at a mouth."""
    keep, _removed = clip_cells(region, rules, X, Y, Z, np.zeros(region.shape, bool))
    for m in mouths:
        keep &= np.hypot(X - m["x"], Z - m["z"]) > rules["mouth_zone"]
    return keep


def widen_system(spec, sysspec, res, rooms=None):
    """Add the widened passages and the nest rooms (the recorded ones, or `rooms`) to a generated base result, in place.
    Fails closed."""
    rules = spec["rules"]
    wr = rules["widen"]
    reg, net, b = res["region"], res["net"], res["builder"]
    seed = b.seed
    base_keys = np.asarray(res["keys"], np.int64)
    bx_, by_, bz_ = res["x"], res["y"], res["z"]
    W, Hh = width_targets(net, seed, rules, res["mouths"])
    X, Z, Fl, T = wide_columns(net, seed, W, Hh, wr["width"][1], wr["height_max"])
    cx, cy, cz, deck = column_cells(reg, X, Z, Fl, T)
    rooms = (sysspec.get("nest_rooms") or []) if rooms is None else rooms
    rsrc = [np.zeros(len(cx), np.int64)]
    parts = [(cx, cy, cz, deck)]
    for i, room in enumerate(rooms):
        rx, ry, rz = nest_room_cells(room, seed)
        parts.append((rx, ry, rz, np.full(len(rx), int(room["centre"][1]), np.int64)))
        rsrc.append(np.full(len(rx), i + 1, np.int64))
    cx = np.concatenate([p[0] for p in parts])
    cy = np.concatenate([p[1] for p in parts])
    cz = np.concatenate([p[2] for p in parts])
    deck = np.concatenate([p[3] for p in parts])
    src = np.concatenate(rsrc)
    stats = {"swept_cells": int((src == 0).sum())}
    # the rules: unblocked, cover everywhere, floor limit; outside every mouth zone; not at or under a base lantern
    keep = added_allowed(reg, rules, res["mouths"], cx, cy, cz)
    lan = set()
    for (x, y, z) in res["lanterns"]:
        lan |= {(x, y, z), (x, y - 1, z)}
    if lan:
        keep &= np.array([(int(a), int(b_), int(c)) not in lan for a, b_, c in zip(cx, cy, cz)], bool)
    k = reg.key(cx, cy, cz)
    pos = np.searchsorted(base_keys, k)
    pos[pos >= len(base_keys)] = len(base_keys) - 1
    new = base_keys[pos] != k
    room_lost = [i for i in range(len(rooms)) if not keep[src == i + 1].all()]
    if room_lost:
        raise CaveSystemError("%s: nest room(s) %s break the cover, blocked, floor or mouth-zone rule" % (sysspec["id"], [rooms[i]["id"] for i in room_lost]))
    sel = keep & new
    k, deck, src = k[sel], deck[sel], src[sel]
    # one cell claimed by two runs of different decks is a merge: drop every copy
    o = np.lexsort((deck, k))
    k, deck, src = k[o], deck[o], src[o]
    first = np.r_[True, k[1:] != k[:-1]]
    dk_lo = deck[first]
    dk_hi = np.maximum.reduceat(deck, np.nonzero(first)[0])
    uk = k[first]
    usrc = np.minimum.reduceat(np.where(src > 0, -src, 0), np.nonzero(first)[0])      # a room cell keeps its room
    usrc = -usrc
    split = (dk_hi - dk_lo) > wr["deck_tolerance"]
    stats["dropped_two_decks"] = int(split.sum())
    uk, udeck, usrc = uk[~split], dk_lo[~split], usrc[~split]
    # decks against the union
    allk = np.concatenate([base_keys, uk])
    alld = np.concatenate([run_floors(base_keys), udeck])
    o = np.argsort(allk, kind="stable")
    allk, alld = allk[o], alld[o]
    isnew = np.zeros(len(allk), bool)
    isnew[np.searchsorted(allk, uk)] = True
    test = np.nonzero(isnew)[0]
    bad = deck_mismatch(reg, allk, alld, test, wr["deck_tolerance"], wr["deck_gap"])
    badk = allk[test[bad]]
    pos = np.searchsorted(uk, badk)
    room_hit = sorted({int(usrc[p]) for p in pos if usrc[p] > 0})
    if room_hit:
        raise CaveSystemError("%s: nest room(s) %s come within %d of a carved cell on another deck" % (sysspec["id"], [rooms[i - 1]["id"] for i in room_hit], wr["deck_gap"]))
    stats["dropped_deck"] = int(bad.sum())
    okmask = np.ones(len(uk), bool)
    okmask[pos] = False
    uk, usrc = uk[okmask], usrc[okmask]
    # connected to a mouth; then the floors that need a climb of two are lowered, as for the base
    keys = np.unique(np.concatenate([base_keys, uk]))
    starts = []
    for m in res["mouths"]:
        n_ = net.n[m["node"]]
        for dy in range(0, 4):
            starts.append(int(reg.key(np.array([int(round(n_[0]))]), np.array([int(round(n_[1])) + dy]), np.array([int(round(n_[2]))]))[0]))
    seen = flood_from(reg, keys, np.unique(np.array(starts, np.int64)))
    stats["dropped_disconnected"] = int((~seen).sum())
    keys = keys[seen]
    ux, uy, uz = reg.unkey(keys)
    cells = set(zip(ux.tolist(), uy.tolist(), uz.tolist()))
    cells, repaired = repair_steps(cells, (res["mouths"][0]["x"], res["mouths"][0]["z"]), reg.gnd)
    stats["repaired"] = repaired
    base_set = set(zip(bx_.tolist(), by_.tolist(), bz_.tolist()))
    cells, pruned, left = prune_unwalkable(cells, base_set, res["mouths"], reg.gnd)
    stats["dropped_unwalkable"] = pruned
    if repaired or pruned:
        arr = np.array(sorted(cells), np.int64)
        keys = np.unique(reg.key(arr[:, 0], arr[:, 1], arr[:, 2]))
        ux, uy, uz = reg.unkey(keys)
    # the base must be whole inside the result
    p = np.searchsorted(keys, base_keys)
    p[p >= len(keys)] = len(keys) - 1
    if not (keys[p] == base_keys).all():
        raise CaveSystemError("%s: the widened volume lost %d live cells" % (sysspec["id"], int((keys[p] != base_keys).sum())))
    # every room whole, its block a rock cell under an open floor, its spawn box and its clearance kept
    for i, room in enumerate(rooms):
        rx, ry, rz = nest_room_cells(room, seed)
        rk = np.unique(reg.key(rx, ry, rz))
        others = np.setdiff1d(keys, rk, assume_unique=True)
        p = np.searchsorted(keys, rk)
        p[p >= len(keys)] = len(keys) - 1
        if not (keys[p] == rk).all():
            raise CaveSystemError("%s: nest room %s is not whole in the result" % (sysspec["id"], room["id"]))
        probs = room_problems(reg, rules, room, seed, others, res["mouths"])
        if probs:
            raise CaveSystemError("%s: %s" % (sysspec["id"], "; ".join(probs)))
    res.update({"base_keys": base_keys, "base_x": bx_, "base_y": by_, "base_z": bz_, "keys": keys,
                "x": ux.astype(np.int64), "y": uy.astype(np.int64), "z": uz.astype(np.int64)})
    probs = walk_problems(res)
    trapped = trap_count(res)
    if trapped:
        probs.append("%d standing cells can be walked to but cannot walk back out of any mouth" % trapped)
    if probs:
        raise CaveSystemError("%s: the widened volume cannot be walked: %s" % (sysspec["id"], "; ".join(probs)))
    blocks = {tuple(r["block"]) for r in rooms}
    res["ores"] = [o_ for o_ in dress_ore(reg, rules, seed, keys, None) if (o_[0], o_[1], o_[2]) not in blocks]
    cells = set(zip(res["x"].tolist(), res["y"].tolist(), res["z"].tolist()))
    for (x, y, z) in res["lanterns"]:
        if (x, y, z) not in cells or (x, y - 1, z) in cells or (x, y + 1, z) not in cells:
            raise CaveSystemError("%s: the base lantern at %s no longer stands on a floor" % (sysspec["id"], (x, y, z)))
    stats.update({"base_cells": int(len(base_keys)), "cells": int(len(keys)), "added_cells": int(len(keys) - len(base_keys)),
                  "room_cells": {r["id"]: int(len(np.unique(reg.key(*nest_room_cells(r, seed))))) for r in rooms}})
    res["widen"] = stats
    res["width_targets"] = W
    return res


def site_nests(spec, sysspec, res):
    """[room record] for one system, sited on a WIDENED result with no rooms: nodes of side branches (dead ends), in a seeded order,
    each tried with a few headings square to the passage and a few sizes; a room is taken when room_problems finds nothing and it
    stands `spacing` from every other. The most `count[1]` are taken; fewer than `count[0]` fails closed."""
    rules = spec["rules"]
    nr = rules["nests"]
    reg, net, b = res["region"], res["net"], res["builder"]
    seed = b.seed
    keys = res["keys"]
    xs, ys, zs = reg.unkey(keys)
    colmin = {}
    for x, y, z in zip(xs.tolist(), ys.tolist(), zs.tolist()):
        colmin.setdefault((x, z), []).append(y)
    nbr = {}
    for i, j in net.edges:
        nbr.setdefault(i, []).append(j)
        nbr.setdefault(j, []).append(i)
    W = res["width_targets"]
    themes = sysspec.get("nest_themes") or []
    if len(themes) < nr["count"][1]:
        raise CaveSystemError("%s: %d nest themes for up to %d rooms" % (sysspec["id"], len(themes), nr["count"][1]))
    cands = []
    for bi, br in enumerate(net.branches):
        if br["kind"] not in ("side", "descent", "ascent"):
            continue
        nodes = br["nodes"]
        for k in range(10, len(nodes) - 3, 5):
            cands.append((br["kind"] != "side", h32(seed, 501, nodes[k]), nodes[k]))
    cands.sort()
    rooms = []
    why_not = {"candidates": len(cands)}
    for _s, _h, i in cands:
        if len(rooms) >= nr["count"][1]:
            break
        n = net.n[i]
        if any(math.hypot(n[0] - c["x"], n[2] - c["z"]) <= max(c["a"], c["b"]) * 1.5 + 20 for c in list(res["caverns"]) + list(res["halls"])):
            continue
        if any(math.hypot(n[0] - r["centre"][0], n[2] - r["centre"][2]) < nr["spacing"] for r in rooms):
            continue
        nb = nbr.get(i) or []
        if len(nb) != 2:
            continue
        a, c = net.n[nb[0]], net.n[nb[1]]
        hd = math.atan2(c[2] - a[2], c[0] - a[0])
        x0, z0 = int(round(n[0])), int(round(n[2]))
        ys_ = [y for y in colmin.get((x0, z0), []) if abs(y - n[1]) <= 3]
        if not ys_:
            continue
        yf = min(ys_)
        rng = rnd(seed, "nest", i)
        done = False
        for side in (1, -1):
            for jit in (0.0, 0.35, -0.35):
                ang = hd + side * math.pi / 2 + jit
                for _t in range(3):
                    # radii whose noisy walls (+-wall_noise) still measure across[0] to across[1]
                    r_lo = nr["across"][0] / 2.0 / (1 - nr["wall_noise"])
                    r_hi = nr["across"][1] / 2.0 / (1 + nr["wall_noise"])
                    ra = rng.uniform(r_lo, r_hi)
                    rb = rng.uniform(r_lo, ra)
                    tall = rng.randint(nr["tall"][0], nr["tall"][1])
                    ls = rng.uniform(nr["spur_len"][0], nr["spur_len"][1])
                    wall = W[i] / 2.0 * 1.2
                    dcen = wall + ls + ra
                    cx, cz = int(round(n[0] + dcen * math.cos(ang))), int(round(n[2] + dcen * math.sin(ang)))
                    if any(math.hypot(cx - r["centre"][0], cz - r["centre"][2]) < nr["spacing"] for r in rooms):
                        continue
                    ex, ez = n[0] + (wall + ls + 2) * math.cos(ang), n[2] + (wall + ls + 2) * math.sin(ang)
                    sr = int(math.floor(0.7 * min(ra, rb)))
                    room = {"id": "%s%s_%d" % (NEST_PREFIX, sysspec["id"], len(rooms) + 1), "theme": themes[len(rooms)]["theme"],
                            "centre": [cx, yf, cz], "radius": [round(ra, 2), round(rb, 2)], "wall_noise": nr["wall_noise"],
                            "angle": round(ang, 4), "tall": tall,
                            "spur": [[round(n[0], 2), yf, round(n[2], 2)], [round(ex, 2), yf, round(ez, 2)]],
                            "spur_width": nr["spur_width"], "spur_height": nr["spur_height"], "attach_radius": round(wall + 2, 2),
                            "block": [cx, yf - 1, cz], "spawn_range": sr, "cancel_range": int(math.ceil(max(ra, rb))) + 1,
                            "across": "%d by %d" % (round(2 * ra), round(2 * rb)), "attach_node": i}
                    others = keys
                    rp = room_problems(reg, rules, room, seed, others, res["mouths"])
                    if rp:
                        for q_ in rp:
                            why_not[q_.split(": ", 1)[1][:24]] = why_not.get(q_.split(": ", 1)[1][:24], 0) + 1
                        continue
                    rk = np.unique(reg.key(*nest_room_cells(room, seed)))
                    # the cancel sphere stops short of every passage
                    dmin = 1e9
                    bx_, by_, bz_ = room["block"]
                    near = (np.abs(xs - bx_) <= room["cancel_range"] + 1) & (np.abs(zs - bz_) <= room["cancel_range"] + 1)
                    if near.any():
                        dmin = float(np.sqrt((xs[near] - bx_) ** 2 + (ys[near] - by_) ** 2 + (zs[near] - bz_) ** 2).min())
                    if dmin <= room["cancel_range"]:
                        continue
                    room["cells"] = int(len(rk))
                    rooms.append(room)
                    done = True
                    break
                if done:
                    break
            if done:
                break
    if len(rooms) < nr["count"][0]:
        raise CaveSystemError("%s: only %d nest room(s) could be sited, %d wanted (%s)" % (sysspec["id"], len(rooms), nr["count"][0], why_not))
    for r in rooms:
        r["place"] = "%s, a nest room off a side branch" % sysspec["name"]
        r["sited_by"] = "python tools/cave_systems.py nests --site (2026-10-23), on the widened volume"
    return rooms


def trap_count(res):
    """Standing cells the first mouth's walk reaches from which no mouth can be walked back to (a one-way drop into a dead end)."""
    reg = res["region"]
    cells = set(zip(res["x"].tolist(), res["y"].tolist(), res["z"].tolist()))
    stand, reached, out = walk_sets(cells, res["mouths"], reg.gnd)
    return sum(1 for p in reached if p not in out)


def walk_sets(cells, mouths, gnd):
    """(standing cells, those the first mouth's walk reaches, those from which some mouth can be walked back to)."""
    stand = standing_cells(cells, gnd)
    rev = {}
    for (x, y, z) in stand:
        for dx, dz in NB4:
            for dy in (0, 1, -1, -2, -3):
                p = (x + dx, y + dy, z + dz)
                if p not in stand:
                    continue
                if dy == 1 and not ((x, y + 2, z) in cells or y + 2 > gnd(x, z)):
                    continue
                if dy < 0 and not ((x + dx, y + 1, z + dz) in cells or y + 1 > gnd(x + dx, z + dz)):
                    continue
                rev.setdefault(p, []).append((x, y, z))
                break
    out, srcs = set(), []
    for m in mouths:
        near = [p for p in stand if abs(p[0] - m["x"]) <= 3 and abs(p[2] - m["z"]) <= 3]
        if near:
            srcs.append(max(near, key=lambda p: p[1]))
    q = deque(srcs)
    out.update(srcs)
    while q:
        c = q.popleft()
        for a in rev.get(c, ()):
            if a not in out:
                out.add(a)
                q.append(a)
    if not srcs:
        return stand, set(), set()
    return stand, set(walk_from(stand, cells, srcs[0], gnd)), out


def prune_unwalkable(cells, base_set, mouths, gnd, rounds=8):
    """Drop the added cells of every column holding a standing cell that the first mouth cannot walk to, or that cannot walk back
    out of some mouth, until none is left (the base is never touched). Returns (cells, cells dropped, base standing cells left bad)."""
    dropped = 0
    for _ in range(rounds):
        stand, reached, back = walk_sets(cells, mouths, gnd)
        bad = [p for p in stand if p not in reached or p not in back]
        if not bad:
            return cells, dropped, 0
        cols = {(p[0], p[2]) for p in bad}
        rm = {c for c in cells if (c[0], c[2]) in cols and c not in base_set}
        if not rm:
            return cells, dropped, len(bad)
        cells = cells - rm
        dropped += len(rm)
    stand, reached, back = walk_sets(cells, mouths, gnd)
    return cells, dropped, sum(1 for p in stand if p not in reached or p not in back)


def passage_widths(res, keys, zone, sample=4):
    """Measured widths: at every `sample`-th node outside the mouth zones and the caverns, the run of carved cells one above the
    floor along the line square to the passage through the node. Returns a list of ints."""
    reg, net = res["region"], res["net"]
    xs, ys, zs = reg.unkey(np.asarray(keys))
    cells = set(zip(xs.tolist(), ys.tolist(), zs.tolist()))
    nbr = {}
    for i, j in net.edges:
        nbr.setdefault(i, []).append(j)
        nbr.setdefault(j, []).append(i)
    out = []
    for i in range(0, len(net.n), sample):
        n = net.n[i]
        if any(math.hypot(n[0] - m["x"], n[2] - m["z"]) <= zone for m in res["mouths"]):
            continue
        if any(math.hypot(n[0] - c["x"], n[2] - c["z"]) <= max(c["a"], c["b"]) * 1.4 + 4 for c in list(res["caverns"]) + list(res["halls"])):
            continue
        nb = nbr.get(i) or []
        if not nb:
            continue
        a = net.n[nb[0]]
        b = net.n[nb[-1]] if len(nb) > 1 else n
        dx, dz = (b[0] - a[0]), (b[2] - a[2])
        L = math.hypot(dx, dz)
        if L < 0.5:
            continue
        px, pz = -dz / L, dx / L
        x0, z0 = int(round(n[0])), int(round(n[2]))
        col = [y for y in range(int(round(n[1])) - 3, int(round(n[1])) + 4) if (x0, y, z0) in cells]
        if not col:
            continue
        fy = min(col) + 1
        w = 0
        for side in (1, -1):
            for s in range(1 if side == 1 else 1, 30):
                x, z = int(round(n[0] + px * s * side)), int(round(n[2] + pz * s * side))
                if (x, fy, z) in cells:
                    w += 1
                else:
                    break
        if (x0, fy, z0) in cells:
            out.append(w + 1)
    return out


def system_pack(spec, sysspec, res):
    rules = spec["rules"]
    base = (res["base_x"], res["base_y"], res["base_z"]) if "base_x" in res else None
    files, stats = tile_functions(sysspec["id"], res["region"], rules, res["x"], res["y"], res["z"], res["ores"], res["lanterns"], base)
    return files, stats


def summarise(spec, sysspec, res, files, stats):
    net = res["net"]
    ore_n = {}
    for (_x, _y, _z, b) in res["ores"]:
        ore_n[b] = ore_n.get(b, 0) + 1
    lines = sum(len(v) for v in files.values())
    exec_lines = 0
    for name, v in files.items():
        if name.endswith("_carve"):
            base = name[:-6]
            exec_lines = max(exec_lines, (len(files.get(base + "_air", ())) + len(files.get(base + "_wide", ()))) * 2
                             + len(files[base + "_shell"]) + len(files[base + "_dress"]))
    xs, zs = res["x"], res["z"]
    wd = res.get("widen")
    if wd is not None:
        zone = spec["rules"]["mouth_zone"]
        wb = passage_widths(res, res["base_keys"], zone)
        ww = passage_widths(res, res["keys"], zone)

        def dist(ws):
            ws = np.array(ws)
            return {"samples": int(len(ws)), "p05": int(np.percentile(ws, 5)), "p25": int(np.percentile(ws, 25)), "median": int(np.median(ws)),
                    "p75": int(np.percentile(ws, 75)), "p95": int(np.percentile(ws, 95)), "max": int(ws.max()),
                    "3-4": int(((ws >= 3) & (ws <= 4)).sum()), "5-9": int(((ws >= 5) & (ws <= 9)).sum()),
                    "10-15": int(((ws >= 10) & (ws <= 15)).sum()), "over_15": int((ws > 15).sum()), "under_3": int((ws < 3).sum())}
        wd = dict(wd, measured_width_base=dist(wb), measured_width_widened=dist(ww),
                  live_cells_sha256=cells_digest(res["base_x"], res["base_y"], res["base_z"]))
    return {
        "id": sysspec["id"], "name": sysspec["name"], "centre": sysspec["centre"], "radius": sysspec["radius"],
        "centreline_blocks": round(net.length), "nodes": len(net.n), "branches": len(net.branches),
        "caverns": [{"x": round(c["x"]), "z": round(c["z"]), "floor_y": c["yf"], "across": [round(c["a"] * 2), round(c["b"] * 2)],
                     "tall": round(c["tall"])} for c in res["caverns"]],
        "halls": len(res["halls"]),
        "mouths": [dict(m) for m in res["mouths"]],
        "levels_used": sorted({min(range(len(rules_levels(spec))), key=lambda q: abs(rules_levels(spec)[q]["y"] - n[1])) for n in net.n if n[5] >= 0}),
        "carved_cells": int(len(res["x"])), "ore_blocks": len(res["ores"]), "ore_by_block": ore_n, "lanterns": len(res["lanterns"]),
        "lines": lines, "lines_by_kind": stats, "max_chain_per_tile": exec_lines,
        "bounds": [int(xs.min()), int(res["y"].min()), int(zs.min()), int(xs.max()), int(res["y"].max()), int(zs.max())],
        "clipped": res["removed"], "disconnected_dropped": res["disconnected"],
        "functions": len(files), "seed_attempt": res.get("attempt"), "rejected_attempts": res.get("rejected"), "walk_far": res.get("walk_far"),
        "widen": wd,
    }


def rules_levels(spec):
    return spec["rules"]["levels"]


# ------------------------------------------------------------------ the pack and the steps

def tile_name_box(name, tile):
    sysid, tx, tz, kind = name.rsplit("_", 3)
    x0, z0 = int(tx) * tile, int(tz) * tile
    return sysid, kind, (x0, z0, x0 + tile - 1, z0 + tile - 1)


def index_lines(files):
    """The order the run step uses: every shell, then every carve, tiles in name order."""
    shells = sorted(k for k in files if k.endswith("_shell"))
    carves = sorted(k for k in files if k.endswith("_carve"))
    return shells + carves


def write_pack(files, index, out=OUT):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "data" / NS / "function" / FOLDER).mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: the cave systems (tools/cave_systems.py, data/cave_systems.json)"}}, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    for name, lines in files.items():
        (out / "data" / NS / "function" / FOLDER / (name + ".mcfunction")).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (out / "data" / NS / "function" / FOLDER / "index.txt").write_text("\n".join(index) + "\n", encoding="utf-8", newline="\n")


def check_files(files, rules):
    bad = []
    for name, lines in files.items():
        for p in FL.check_lines(lines, name):
            bad.append((name, p))
    return bad


def placement_steps(spec=None, out=OUT):
    """For tools/reapply.py step R9CS: per tile hold its box, run its function, release it (the shells first, then the carves)."""
    spec = spec or load()
    tile = spec["rules"]["tile"]
    idx = Path(out) / "data" / NS / "function" / FOLDER / "index.txt"
    if not idx.is_file():
        raise SystemExit("no %s: run `python tools/cave_systems.py build` (reapply.py prepare) first" % idx)
    steps = []
    for name in [x for x in idx.read_text(encoding="utf-8").split("\n") if x.strip()]:
        _sid, _kind, box = tile_name_box(name, tile)
        hold = "%d %d %d %d" % box
        steps += [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s/%s" % (F, name)), ("cmd", "forceload remove " + hold)]
    return steps


def build_all(spec=None, only=None, g=None, progress=None):
    spec = spec or load()
    g = g or G.Ground()
    results = {}
    files_all = {}
    summary = []
    for s in spec["systems"]:
        if only and s["id"] != only:
            continue
        res = generate(spec, s, g)
        files, stats = system_pack(spec, s, res)
        files_all.update(files)
        results[s["id"]] = res
        summary.append(summarise(spec, s, res, files, stats))
        if progress:
            progress(summary[-1])
    return results, files_all, summary


def build(spec=None, only=None, out=OUT, plan=PLAN):
    spec = spec or load()
    results, files, summary = build_all(spec, only, progress=lambda s: print("  %-12s %5d blocks of centreline, %d caverns, %d mouths, %d cells, %d lines" % (
        s["id"], s["centreline_blocks"], len(s["caverns"]), len(s["mouths"]), s["carved_cells"], s["lines"])))
    bad = check_files(files, spec["rules"])
    if bad:
        for n, p in bad[:10]:
            print("REFUSED %s: %s" % (n, p))
        raise SystemExit("%d function problem(s): nothing written" % len(bad))
    probs = nest_problems(spec)
    if probs:
        for q in probs[:10]:
            print("REFUSED:", q)
        raise SystemExit("the nest rooms' records in data/ do not match the rooms (python tools/cave_systems.py nests --write): nothing written")
    write_pack(files, index_lines(files), out)
    plan = Path(plan)
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(json.dumps(plan_json(spec, results, summary), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    tot_lines = sum(s["lines"] for s in summary)
    tot_cells = sum(s["carved_cells"] for s in summary)
    print("wrote %s: %d functions, %d command lines, %d blocks carved; plan %s" % (Path(out).relative_to(ROOT) if str(out).startswith(str(ROOT)) else out, len(files), tot_lines, tot_cells,
                                                                                    Path(plan).relative_to(ROOT) if str(plan).startswith(str(ROOT)) else plan))
    return results, files, summary


def plan_json(spec, results, summary):
    systems = {}
    for s in summary:
        res = results[s["id"]]
        net = res["net"]
        systems[s["id"]] = dict(s, nodes_xyzwh=[[round(n[0], 1), round(n[1], 1), round(n[2], 1), round(n[3], 1), round(n[4], 1), n[5]] for n in net.n],
                                edges=net.edges,
                                branches=[{"id": b["id"], "kind": b["kind"], "level": b["level"], "length": round(b["length"]), "start": b["start"],
                                           "end": b["end"], "joined": b["joined"]} for b in net.branches])
    return {"schema": "cobblers.derived.cave_systems/1", "generated_by": GENERATED, "systems": systems}


# ------------------------------------------------------------------ site: where could a system go

def attractors():
    """[(x, z, name)] points near which a mouth should stand: every route path (densified to 8 blocks), every town footprint's
    edge, every settlement centre in data/placements.json."""
    out = []
    rp = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    for name, pts in rp.items():
        for a, b in zip(pts, pts[1:]):
            n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) // 8)
            for i in range(n + 1):
                t = i / max(n, 1)
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, name))
    for (tid, tx, tz, mnx, mnz, mxx, mxz) in towns():
        for x in range(mnx, mxx + 1, 8):
            out += [(x, mnz, tid), (x, mxz, tid)]
        for z in range(mnz, mxz + 1, 8):
            out += [(mnx, z, tid), (mxx, z, tid)]
    pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]
    for k, v in pl.items():
        if "centre" in v:
            out.append((v["centre"][0], v["centre"][1], k))
    return out


def mouth_candidates(spec, sysspec, g=None, want=5, spacing=260, lo=50, hi=130):
    """Mouths proposed for a system: free ground in the same free component as the centre, 50 to 130 blocks from a town edge, a
    settlement or a route, spread at least `spacing` apart, nearest-to-ideal first. Nothing is written."""
    rules = spec["rules"]
    reg = Region(rules, sysspec, g)
    cx, cz = sysspec["centre"]
    S = 4
    fc = reg.free_c[::S, ::S]
    h, w = fc.shape
    lab = np.zeros(fc.shape, np.int32)
    start = None
    best = 1e18
    for r in range(h):
        for c in np.nonzero(fc[r])[0]:
            d = (c * S + reg.x0 - cx) ** 2 + (r * S + reg.z0 - cz) ** 2
            if d < best:
                best, start = d, (r, int(c))
    q = deque([start])
    lab[start] = 1
    while q:
        a, b = q.popleft()
        for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x, y = a + da, b + db
            if 0 <= x < h and 0 <= y < w and fc[x, y] and not lab[x, y]:
                lab[x, y] = 1
                q.append((x, y))
    at = attractors()
    A = np.array([(a[0], a[1]) for a in at])
    names = [a[2] for a in at]
    cands = []
    for r in range(0, h, 2):
        for c in np.nonzero(lab[r])[0][::2]:
            x, z = c * S + reg.x0, r * S + reg.z0
            if math.hypot(x - cx, z - cz) > sysspec["radius"] - 40 or reg.gnd(x, z) < 85:
                continue
            d = np.hypot(A[:, 0] - x, A[:, 1] - z)
            j = int(d.argmin())
            if lo <= d[j] <= hi:
                cands.append((abs(d[j] - 85) + 0.02 * math.hypot(x - cx, z - cz), x, z, names[j], float(d[j])))
    cands.sort()
    out = []
    for c in cands:
        if all(math.hypot(c[1] - o[1], c[2] - o[2]) >= spacing for o in out):
            out.append(c)
        if len(out) >= want:
            break
    return out


def cmd_site(spec, only):
    g = G.Ground()
    for s in spec["systems"]:
        if only and s["id"] != only:
            continue
        reg = Region(spec["rules"], s, g)
        print("%s: centre %s radius %d: %.0f%% of the box is free ground" % (s["id"], s["centre"], s["radius"], 100.0 * reg.free_c.mean()))
        for m in s["mouths"]:
            ix, iz = m["x"] - reg.x0, m["z"] - reg.z0
            ok = reg.inside(m["x"], m["z"]) and bool(reg.free_c[iz, ix])
            print("  mouth %-10s (%d, %d) ground y%d  free %s" % (m["id"], m["x"], m["z"], reg.gnd(m["x"], m["z"]) if reg.inside(m["x"], m["z"]) else -1, ok))
        for (sc, x, z, nm, d) in mouth_candidates(spec, s, g):
            print("  candidate (%d, %d) %.0f from %s, ground y%d" % (x, z, d, nm, reg.gnd(x, z)))
    return 0


# ------------------------------------------------------------------ the picture

def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _depth_colour(y, lo=-40, hi=140):
    """Floor height -> colour: violet (deep) through blue and teal to yellow (shallow)."""
    t = min(1.0, max(0.0, (y - lo) / float(hi - lo)))
    stops = [(0.0, (90, 30, 150)), (0.3, (40, 70, 220)), (0.6, (30, 200, 170)), (1.0, (255, 235, 60))]
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b:
            f = (t - a) / (b - a)
            return tuple(int(ca[i] + (cb[i] - ca[i]) * f) for i in range(3))
    return stops[-1][1]


def _relief(H):
    """Grey hillshade of a ground grid, the sea in navy."""
    gy, gx = np.gradient(H.astype(float))
    shade = np.clip(0.5 + 0.10 * (gx - gy), 0, 1)
    base = np.clip((H - 55) / 220.0, 0, 1)
    v = (70 + 90 * base + 60 * shade).astype(np.uint8)
    img = np.stack([v, v, v], axis=-1)
    img[H <= 63] = (26, 48, 92)
    return img


def cmd_map(spec, only):
    from PIL import Image, ImageDraw
    g = G.Ground()
    results, files, summary = build_all(spec, only, g)
    IMAGES.mkdir(parents=True, exist_ok=True)
    tw = towns()
    pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]
    f_big, f_mid, f_small = _font(22), _font(15), _font(12)
    by_id = {s["id"]: s for s in summary}
    palette = {0: (255, 90, 60), 1: (255, 200, 30), 2: (70, 235, 130)}
    for k, s in enumerate(spec["systems"]):
        if only and s["id"] != only:
            continue
        res, sm = results[s["id"]], by_id[s["id"]]
        reg = res["region"]
        pad = 90
        xs, zs = res["x"], res["z"]
        bx0, bz0 = max(int(xs.min()) - pad, reg.x0), max(int(zs.min()) - pad, reg.z0)
        bx1, bz1 = min(int(xs.max()) + pad, reg.x1), min(int(zs.max()) + pad, reg.z1)
        H = reg.H[bz0 - reg.z0:bz1 - reg.z0 + 1, bx0 - reg.x0:bx1 - reg.x0 + 1]
        img = _relief(H).astype(np.float64)
        bl = reg.blocked[bz0 - reg.z0:bz1 - reg.z0 + 1, bx0 - reg.x0:bx1 - reg.x0 + 1] & (H > 63)
        img[bl] = img[bl] * 0.72 + np.array([150, 40, 40]) * 0.28
        img = img.astype(np.uint8)
        w, h = img.shape[1], img.shape[0]
        top = np.full((h, w), -9999, np.int32)
        np.maximum.at(top, (zs - bz0, xs - bx0), res["y"].astype(np.int32))
        rows, cols = np.nonzero(top > -9999)
        lut = {}
        for r, c in zip(rows.tolist(), cols.tolist()):
            yv = int(top[r, c])
            if yv not in lut:
                lut[yv] = _depth_colour(yv)
            img[r, c] = lut[yv]
        title_h = 74
        W = max(w, 900)
        im = Image.new("RGB", (W, h + title_h), (18, 18, 22))
        im.paste(Image.fromarray(img), (0, title_h))
        d = ImageDraw.Draw(im)

        def px(x, z):
            return (x - bx0, z - bz0 + title_h)
        for (tid, tx, tz, mnx, mnz, mxx, mxz) in tw:
            if bx0 - 150 <= tx <= bx1 + 150 and bz0 - 150 <= tz <= bz1 + 150:
                a, b2 = px(mnx, mnz), px(mxx, mxz)
                d.rectangle([a, b2], outline=(255, 255, 255), fill=(40, 90, 200))
                d.text((a[0], a[1] - 15), tid, fill=(255, 255, 255), font=f_small)
        for sk, sv in pl.items():
            c = sv.get("centre")
            if c and bx0 <= c[0] <= bx1 and bz0 <= c[1] <= bz1:
                p = px(c[0], c[1])
                d.rectangle([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill=(120, 170, 255), outline=(255, 255, 255))
                d.text((p[0] + 6, p[1] - 6), sk, fill=(200, 220, 255), font=f_small)
        for c in res["caverns"]:
            p = px(c["x"], c["z"])
            d.ellipse([p[0] - c["a"], p[1] - c["b"], p[0] + c["a"], p[1] + c["b"]], outline=(255, 255, 255), width=1)
            d.text((p[0] - 14, p[1] - 8), "C%d" % (c["id"] + 1), fill=(255, 255, 255), font=f_mid)
        for m in res["mouths"]:
            p = px(m["x"], m["z"])
            d.ellipse([p[0] - 9, p[1] - 9, p[0] + 9, p[1] + 9], outline=(255, 40, 40), fill=(255, 255, 255), width=3)
            d.text((p[0] + 12, p[1] - 8), "%s (%d, %d)" % (m["id"], m["x"], m["z"]), fill=(255, 255, 255), font=f_mid)
        # scale bar, north arrow and the depth legend
        d.rectangle([14, title_h + h - 30, 14 + 200, title_h + h - 24], fill=(255, 255, 255))
        d.text((14, title_h + h - 52), "200 blocks", fill=(255, 255, 255), font=f_mid)
        d.line([(w - 30, title_h + 60), (w - 30, title_h + 20)], fill=(255, 255, 255), width=3)
        d.text((w - 38, title_h + 62), "N", fill=(255, 255, 255), font=f_mid)
        for q, yv in enumerate((120, 80, 40, 0, -40)):
            x0 = 14 + q * 96
            d.rectangle([x0, title_h + 12, x0 + 22, title_h + 30], fill=_depth_colour(yv), outline=(255, 255, 255))
            d.text((x0 + 28, title_h + 12), "y%d" % yv, fill=(255, 255, 255), font=f_small)
        d.text((14, title_h + 34), "passage coloured by its shallowest floor; red tint: kept clear (towns, routes, water, the Rift); C: cavern",
               fill=(230, 230, 230), font=f_small)
        d.text((10, 6), s["name"], fill=(255, 255, 255), font=f_big)
        d.text((10, 36), "%d blocks of centreline, %d caverns, %d mouths, %d branches, %s blocks carved, %d ore blocks, floors y%d to y%d"
               % (sm["centreline_blocks"], len(sm["caverns"]), len(sm["mouths"]), sm["branches"], format(sm["carved_cells"], ","), sm["ore_blocks"],
                  int(res["y"].min()), int(res["y"].max())), fill=(235, 235, 235), font=f_mid)
        p = IMAGES / ("%s.png" % s["id"])
        im.save(p, optimize=True)
        print("wrote", p.relative_to(ROOT))
    # the whole western half
    sc = 6
    Hw = g.box(0, 0, 4095, 8191)
    hh, ww = Hw.shape[0] // sc * sc, Hw.shape[1] // sc * sc
    sm_ = Hw[:hh, :ww].reshape(hh // sc, sc, ww // sc, sc).mean(axis=(1, 3))
    img = _relief(sm_)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    for (tid, tx, tz, *_r) in tw:
        if tx < 4096:
            d.rectangle([tx / sc - 3, tz / sc - 3, tx / sc + 3, tz / sc + 3], fill=(70, 130, 255), outline=(255, 255, 255))
            d.text((tx / sc + 6, tz / sc - 6), tid, fill=(200, 220, 255), font=f_small)
    for k, s in enumerate(spec["systems"]):
        if only and s["id"] != only:
            continue
        res = results[s["id"]]
        c = palette[k % 3]
        cx, cz = s["centre"]
        d.ellipse([(cx - s["radius"]) / sc, (cz - s["radius"]) / sc, (cx + s["radius"]) / sc, (cz + s["radius"]) / sc], outline=c, width=2)
        for i, j in res["net"].edges:
            a, b2 = res["net"].n[i], res["net"].n[j]
            d.line([(a[0] / sc, a[2] / sc), (b2[0] / sc, b2[2] / sc)], fill=c, width=2)
        for ccv in res["caverns"]:
            d.ellipse([ccv["x"] / sc - 4, ccv["z"] / sc - 4, ccv["x"] / sc + 4, ccv["z"] / sc + 4], outline=(255, 255, 255))
        for m in res["mouths"]:
            d.ellipse([m["x"] / sc - 5, m["z"] / sc - 5, m["x"] / sc + 5, m["z"] / sc + 5], outline=(255, 255, 255), fill=c, width=2)
        d.text((max(4, (cx - s["radius"]) / sc), (cz - s["radius"]) / sc - 20), "%s (%d blocks)" % (s["name"], by_id[s["id"]]["centreline_blocks"]),
               fill=c, font=f_mid)
    lim = spec["rules"]["write_limit_x"]
    d.line([(lim / sc, 0), (lim / sc, im.size[1])], fill=(255, 255, 255), width=2)
    d.text((lim / sc - 330, 6), "x %d: the eastern half is another builder's" % lim, fill=(255, 255, 255), font=f_mid)
    d.rectangle([12, im.size[1] - 34, 12 + 1000 // sc, im.size[1] - 28], fill=(255, 255, 255))
    d.text((12, im.size[1] - 58), "1000 blocks   blue squares: towns   white rings: mouths   white circles: caverns", fill=(255, 255, 255), font=f_mid)
    p = IMAGES / "west_map.png"
    im.save(p, optimize=True)
    print("wrote", p.relative_to(ROOT))
    return 0


# ------------------------------------------------------------------ CLI

def nest_meta(sysspec):
    """Every recorded room of a system with the fields tools/nest_rooms.py needs to write its records."""
    return [dict(r, owner_file="data/cave_systems.json", generated_by=GENERATED, step="R9CS") for r in sysspec.get("nest_rooms") or []]


def nest_problems(spec):
    rooms = [r for s in spec["systems"] for r in nest_meta(s)]
    import nest_rooms as NR
    return NR.record_problems(rooms, NEST_PREFIX) if rooms else []


def cmd_nests(spec, site, write, jar):
    import nest_rooms as NR
    if site:
        g = G.Ground()
        for s in spec["systems"]:
            res = generate(spec, s, g, rooms=[])
            rooms = site_nests(spec, s, res)
            s["nest_rooms"] = rooms
            for r in rooms:
                print("%s %s: centre %s, %s across, tall %d, block %s, spawn_range %d, theme %s"
                      % (s["id"], r["id"], r["centre"], r["across"], r["tall"], r["block"], r["spawn_range"], r["theme"]))
        SPEC.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("wrote the rooms into %s" % SPEC.relative_to(ROOT))
    if write:
        import battle_sim
        species = NR.load_species(jar or battle_sim.find_jar())
        rooms = [r for s in spec["systems"] for r in nest_meta(s)]
        themes = {t["theme"]: t for s in spec["systems"] for t in s.get("nest_themes") or []}
        habs, ents = NR.sync(rooms, themes, species, NEST_PREFIX)
        for h in habs:
            print("%s: %s, %d-%d: %s" % (h["id"], h["display_name"], h["level_band"]["minimum"], h["level_band"]["maximum"],
                                         ", ".join("%s %s" % (e["pokemon"], e["level"]) for e in h["entries"])))
        print("wrote %d Habitat Block records and %d pools (%d entries) into data/habitat_blocks.json and data/spawns.json" % (len(rooms), len(habs), len(ents)))
    probs = nest_problems(load())
    for q in probs:
        print("PROBLEM:", q)
    return 1 if probs else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("site", "report", "build", "map", "nests"))
    p.add_argument("system", nargs="?")
    p.add_argument("--source-root")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    p.add_argument("--site", action="store_true", help="nests: site the rooms anew into data/cave_systems.json (moves rooms: never once applied)")
    p.add_argument("--write", action="store_true", help="nests: write their Habitat Block and pool records (needs a Cobblemon jar)")
    p.add_argument("--jar", help="nests --write: the Cobblemon jar the species and evolutions are read from (default tools/battle_sim.py find_jar)")
    a = p.parse_args(argv)
    spec = load()
    if a.mode == "site":
        return cmd_site(spec, a.system)
    if a.mode == "nests":
        return cmd_nests(spec, a.site, a.write, a.jar)
    if a.mode == "map":
        return cmd_map(spec, a.system)
    if a.mode == "report":
        results, files, summary = build_all(spec, a.system)
        for s in summary:
            print(json.dumps({k: v for k, v in s.items() if k not in ("mouths",)}, indent=1))
        return 0
    build(spec, a.system)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
