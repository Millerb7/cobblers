#!/usr/bin/env python
"""The Seaward Drift: a straight road under the land and the sea from Foothill Gate on the plateau to Driftmouth Light
on Driftmouth Isle, a powered minecart line down its middle, with a strip mine off it, from data/sea_drift.json.

The owner, 2026-10-02: "make another mine tunnel with a strip mine attached to it near 1455 113 1795 ... make a small
island with some cool water spawns around it"; then, after riding the first line: "if we remake the tunnel, make it a
straight shot to the island for sure ... if we could make it feel like a bike tunnel from the games that would be sick";
and "make the house you come out a light house as well". The rule that placed the ends is data `rebuild`.

Everything is decided from the data file, the canonical heightmap (tools/ground.py, rounded; never a world) and the sea
level in data/world.json. One voxel model over the whole run:

  the isle      Driftmouth Isle, raised out of the seabed with tools/islet.py's island_top (Relic Island's shape at this
                radius, crown and seed) and a talus skirt below its waterline; a shingle beach (gravel: sand is a spawn
                condition), dirt and grass above; a pad levelled for the lighthouse; four sea stacks on the diagonals
  the road      ONE straight leg along the line's axis, 5 wide and 5 high, from the gatehouse to the lighthouse's hall.
                Its floor is a PROFILE the tool computes: flat through the gatehouse; an open cut falling one in
                `incline_run` until the cover is reached (the portal); then the long coast, the even grade down to the
                lowest point the cover allows under the sea, pushed down wherever the cover needs it (never steeper
                than one in `max_run`); a flat bottom; then a straight climb of one in one up into the hall. Every
                change of level is one block, taken on a stair beside the rail (an ascending powered rail in the
                middle), never within `quiet_cells` of the strip mine's junction, the bottom or the ends
  the cover     solid blocks between any cell this build opens and any water, Chebyshev: shell_r + export_tolerance +
                natural_seabed (data `cover`), derived here and checked on every opened cell against the painted water
                over the effective ground (the heightmap, with the isle's built ground laid over it). Down the coast
                the floor also keeps that cover under the ground; on the climb, under the isle's dry crown and the
                lighthouse pad, only the water's cover and one block of roof are required
  the strips    a 3-wide corridor north off the road at `junction_x` and 1-wide, 2-high branches every third block both
                sides, ending in a chamber with the miners' barrel; copper, lapis and gold ore in the faces (none that is
                a spawn condition), richer toward the far end, a seam at every branch end, some hidden in the walls
  the shell     every cell within shell_r of anything opened, not opened, at or under the effective ground: rock
  the road dress  data `road`: a paved floor either side of the rail, its lane edges dashed in calcite, lanterns in
                pairs over the footpaths, timber sets, distance boards on the walls counting down to either gate
  the line      a rail line a ridden minecart can use (data `rail_line`): straight from a stop in the gatehouse to a
                stop in the lighthouse's hall; every climb and at least every `boost_every`-th flat rail a powered rail
                with its own lever sealed in the rock under its bed; detector rails between; at each end an unpowered
                powered rail against the building's wall with a launch button, parted from the line by one activator
                rail. Levers go before rails and rails go in line order, as a player lays track
  surface       Foothill Gate over the line's head (stone brick, spruce, doors north and south, a named sign over each),
                the portal's headwall, and Driftmouth Light: the keeper's hall the road climbs into (the stop against
                its west wall, a door south to a path down to the shingle) and the striped tower beside it, a spiral
                stair round a lit core up to a glazed lantern room with the lamp

The Habitat Blocks (data/habitat_blocks.json), the caches' advancements (data/rewards.json) and the waters' pool
(data/spawns.json) are records in those files, written by `records --write` from this model and placed by their own
packs: cobblers_habitats, cobblers_rewards, cobblers_spawns. This pack only writes the rock the blocks sit in.

  python tools/sea_drift.py report  [--source-root DIR]     the model's checks and numbers; nothing written
  python tools/sea_drift.py build   [--source-root DIR]     -> build/datapacks/cobblers_sea_drift, derived/sea_drift/plan.json
  python tools/sea_drift.py records [--write]               the habitat-block, reward and pool records (print, or
                                                            replace this build's own records in the three files)
  python tools/sea_drift.py cleanup [--old-rev REV] [--out DIR]
                                                            STAGING ONLY, one-off: the first drift (the L-shaped tunnel,
                                                            its well and the isle at z1586, as built from REV) put back
                                                            to the heightmap world wherever this build does not write;
                                                            -> build/staging/cobblers_sea_drift_cleanup (outside
                                                            build/datapacks, so tools/reapply.py's coverage check never
                                                            asks a step for it)

Run order on a world: every function in build/datapacks/cobblers_sea_drift/data/cobblers/function/sea_drift/index.txt in
that order (island, clear, shell, air, fittings, surface), then cobblers_habitats (the isle's blocks sit in the island's
rock), with the rewards and spawns packs installed. On staging-2026-10-01, which holds the first drift, the cleanup's
functions run first.

The offline audit, independent of this tool's model, is tools/sea_drift_audit.py.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground as G             # noqa: E402
import islet as I              # noqa: E402
import rift_mines as RM        # noqa: E402  (hashing, column runs and the tiled pack writer; not its model)
import terrain as T            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "sea_drift.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_sea_drift"
CLEANUP_OUT = ROOT / "build" / "staging" / "cobblers_sea_drift_cleanup"
OLD_REV = "aa4851a"              # the commit whose tools/sea_drift.py and data/sea_drift.json built the first drift
PLAN = ROOT / "derived" / "sea_drift" / "plan.json"
HABITATS = ROOT / "data" / "habitat_blocks.json"
REWARDS = ROOT / "data" / "rewards.json"
SPAWNS = ROOT / "data" / "spawns.json"
NS = "cobblers"
FOLDER = "sea_drift"
PASSES = ("island", "clear", "shell", "air", "fittings", "surface")
AIR = "minecraft:air"
CLEAR_UP = 24                    # trees are cleared this far over the ground round the open cut
CLEAR_MARGIN = 4
NAME = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}
HABITAT_PREFIX = "driftmouth_"
REWARD_PREFIX = "sea_drift_"

h32, u, pick = RM.h32, RM.u, RM.pick


class DriftError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cover_blocks(spec):
    """Solid blocks required between anything opened and any water (data `cover`: the three parts, summed here)."""
    c = spec["cover"]
    return int(spec["shell_r"]) + int(c["export_tolerance"]) + int(c["natural_seabed"])


def stair(block, facing):
    return "%s[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (block, facing)


def wall_sign(wood, facing, lines):
    """A wall sign facing `facing`, hung on the block behind it; four lines of plain text (JSON text components)."""
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
    return "minecraft:%s_wall_sign[facing=%s,waterlogged=false]{front_text:{messages:[%s]}}" % (wood, facing, q)


HANG = "minecraft:lantern[hanging=true,waterlogged=false]"
STAND = "minecraft:lantern[hanging=false,waterlogged=false]"


def lighthouse(spec):
    return spec["island"]["lighthouse"]


# ------------------------------------------------------------------ the isle (built ground)

def pad_boxes(spec):
    lh = lighthouse(spec)
    return [lh["hall"]["box"], lh["tower"]["box"]]


def isle_columns(spec, g, sea):
    """{(x, z): (top, kind, bed)} for every column the isle build raises; kind is core, skirt, pad or stack."""
    isl = spec["island"]
    cx, cz = isl["centre"]["x"], isl["centre"]["z"]
    R, skirt = int(isl["radius"]), int(isl["skirt"])
    half = R + skirt + 2
    top, r = I.island_top(None, sea, seed=spec["seed"], radius=R, top=isl["crown_y"], half=half)
    bed = g.box(cx - half, cz - half, cx + half, cz + half)
    cols = {}
    edge = sea - 4                                   # where islet.py's shape meets the water (its t -> 0)
    for j in range(2 * half + 1):
        for i in range(2 * half + 1):
            x, z, b = cx - half + i, cz - half + j, int(bed[j, i])
            if not np.isnan(top[j, i]):
                t = int(top[j, i])
                if t > b:
                    cols[(x, z)] = (t, "core", b)
            elif r[j, i] <= R + skirt:
                t = int(math.floor(edge - (r[j, i] - R) / skirt * (edge - b) + 0.5))
                if t > b:
                    cols[(x, z)] = (t, "skirt", b)
    for bx0, bz0, bx1, bz1 in pad_boxes(spec):
        for x in range(bx0 - 2, bx1 + 3):
            for z in range(bz0 - 2, bz1 + 3):
                if (x, z) not in cols or cols[(x, z)][1] not in ("core", "pad"):
                    raise DriftError("the lighthouse pad (%d, %d) is not on the isle's core" % (x, z))
                cols[(x, z)] = (int(isl["pad_y"]), "pad", cols[(x, z)][2])
    for st in isl["stacks"]:
        sx, sz, sr = st["x"], st["z"], st["r"]
        for x in range(sx - sr - 1, sx + sr + 2):
            for z in range(sz - sr - 1, sz + sr + 2):
                d = math.hypot(x - sx, z - sz) + 0.9 * (u(spec["seed"], x, z, 31) - 0.5)
                if d > sr + 0.5:
                    continue
                if (x, z) in cols and cols[(x, z)][1] != "skirt":
                    raise DriftError("stack %s overlaps the isle at (%d, %d)" % (st["id"], x, z))
                b = g(x, z)              # a stack may stand on the skirt's toe: it is built from the seabed all the same
                t = st["top"] - (h32(spec["seed"], x, z, 32) % 3 if d > sr - 1 else 0)
                cols[(x, z)] = (int(t), "stack", b)
    return cols


def isle_block(spec, sea, x, y, z, top, kind):
    """The block the isle build writes at one cell of one of its columns (islet.py's layers, a shingle beach)."""
    pal = spec["palette"]
    if kind == "stack":
        return pick(pal["stack_rock"], spec["seed"], x, y, z, 33)
    beach = spec["island"]["beach"]
    if kind == "skirt":
        return beach if y == top else "minecraft:stone"
    if sea - 2 <= y <= sea + 2 and y >= top - 3:
        return beach
    if top > sea + 2 and y == top:
        return "minecraft:grass_block"
    if top > sea + 2 and y >= top - 3:
        return "minecraft:dirt"
    return "minecraft:stone"


# ------------------------------------------------------------------ the road and its profile

def route(spec):
    """The line's two ends, ((x0, z0), (x1, z1)), on one axis: the road is ONE straight leg (the owner: "a straight
    shot to the island")."""
    vs = spec["route"]["vertices"]
    if len(vs) != 2:
        raise DriftError("the route has %d vertices: the road is one straight leg, two ends" % len(vs))
    (x0, z0), (x1, z1) = vs
    if x0 != x1 and z0 != z1:
        raise DriftError("the route's ends (%d, %d) and (%d, %d) are not on one axis" % (x0, z0, x1, z1))
    return (x0, z0), (x1, z1)


def path_cells(spec):
    """[(x, z, (dx, dz))] one per column from the gatehouse's stop to the hall's stop."""
    (x0, z0), (x1, z1) = route(spec)
    n = max(abs(x1 - x0), abs(z1 - z0))
    d = ((x1 > x0) - (x1 < x0), (z1 > z0) - (z1 < z0))
    return [(x0 + d[0] * i, z0 + d[1] * i, d) for i in range(n + 1)]


def check_straight(cells):
    """The road's own guard: every cell one step along one axis from the one before it."""
    for (a, b, _d), (c, e, _f) in zip(cells, cells[1:]):
        if abs(c - a) + abs(e - b) != 1 or (cells[0][0] != cells[-1][0] and e != cells[0][1]) \
                or (cells[0][1] != cells[-1][1] and c != cells[0][0]):
            raise DriftError("the road is not straight between (%d, %d) and (%d, %d)" % (a, b, c, e))


class Model:
    def __init__(self, spec, g):
        self.spec, self.g = spec, g
        self.sea = int(T.sea_level(g.world))
        self.C = cover_blocks(spec)
        self.r, self.H, self.SR = spec["tube"]["r"], spec["tube"]["height"], spec["shell_r"]
        self.isle = isle_columns(spec, g, self.sea)
        (ax, az), (bx, bz) = route(spec)
        sm = spec["strip_mine"]
        isl = spec["island"]
        half = isl["radius"] + isl["skirt"] + 2
        boxes = pad_boxes(spec) + [spec["gatehouse"]["box"]]
        xs = [ax, bx, isl["centre"]["x"] - half, isl["centre"]["x"] + half,
              sm["junction_x"] - sm["branch_length"] - 3, sm["junction_x"] + sm["branch_length"] + 3]
        zs = [az, bz, isl["centre"]["z"] - half, isl["centre"]["z"] + half,
              sm["corridor_to_z"] - 2 * sm["chamber"]["r"] - 2]
        for b in boxes:
            xs += [b[0], b[2]]
            zs += [b[1], b[3]]
        m = self.r + self.C + self.SR + 4
        self.X0, self.X1, self.Z0, self.Z1 = min(xs) - m, max(xs) + m, min(zs) - m, max(zs) + m
        self.Y0, self.Y1 = 0, 124
        self.nx, self.nz, self.ny = self.X1 - self.X0 + 1, self.Z1 - self.Z0 + 1, self.Y1 - self.Y0 + 1
        base = g.box(self.X0, self.Z0, self.X1, self.Z1).T.astype(np.int32)       # (x, z) heightmap ground
        self.base = base
        geff = base.copy()
        for (x, z), (t, _k, _b) in self.isle.items():
            geff[x - self.X0, z - self.Z0] = t
        self.geff = geff
        self.wl = self.water_levels()
        shape = (self.nx, self.nz, self.ny)
        self.env = np.zeros(shape, bool)          # every cell this build opens
        self.strip = np.zeros(shape, bool)        # the strip mine's part of it
        self.open_cut = set()                     # (x, z) columns of the open cut, cleared of trees
        self.fit, self.surf = {}, {}
        self.notes, self.problems = {}, []

    # -- coordinates
    def ix(self, x, y, z):
        return x - self.X0, z - self.Z0, y - self.Y0

    def G(self, x, z):
        return int(self.geff[x - self.X0, z - self.Z0])

    def opened(self, x, y, z):
        return bool(self.env[self.ix(x, y, z)])

    def water_levels(self):
        """(x, z) -> the painted water surface over the effective ground, or -1 where dry: the lakes whose basins reach
        the model (tools/water_mask.py's rule), then the sea."""
        import water_mask as WM
        wl = np.where(self.geff < self.sea, self.sea, -1).astype(np.int32)
        for bid, b in WM.bodies().items():
            if not b["basin"]:
                continue
            pts = [p for poly in b["basin"] for p in poly]
            bx0, bx1 = min(p[0] for p in pts), max(p[0] for p in pts)
            bz0, bz1 = min(p[1] for p in pts), max(p[1] for p in pts)
            x0, x1, z0, z1 = max(bx0, self.X0), min(bx1, self.X1), max(bz0, self.Z0), min(bz1, self.Z1)
            for x in range(int(x0), int(x1) + 1):
                for z in range(int(z0), int(z1) + 1):
                    i, k = x - self.X0, z - self.Z0
                    if self.geff[i, k] < b["level_y"] and WM.in_polygons(b["basin"], x, z):
                        wl[i, k] = max(wl[i, k], int(b["level_y"]))
                        self.notes.setdefault("lakes_in_reach", set()).add(bid)
        return wl

    def carve(self, x0, x1, z0, z1, y0, y1, strip=False):
        a = self.ix(x0, y0, z0)
        b = self.ix(x1, y1, z1)
        if min(a) < 0 or b[0] >= self.nx or b[1] >= self.nz or b[2] >= self.ny:
            raise DriftError("opening (%d..%d, %d..%d, %d..%d) leaves the model" % (x0, x1, y0, y1, z0, z1))
        self.env[a[0]:b[0] + 1, a[1]:b[1] + 1, a[2]:b[2] + 1] = True
        if strip:
            self.strip[a[0]:b[0] + 1, a[1]:b[1] + 1, a[2]:b[2] + 1] = True


def window(m, x, z, d, along, across):
    """The (x, z) slice of an (x, z) array round a road cell: `along` the road and `across` it."""
    if d[1] == 0:
        return (slice(x - along - m.X0, x + along + 1 - m.X0), slice(z - across - m.Z0, z + across + 1 - m.Z0))
    return (slice(x - across - m.X0, x + across + 1 - m.X0), slice(z - along - m.Z0, z + along + 1 - m.Z0))


def caps(m, cells):
    """The highest feet each road cell may have down the coast: its whole cross-section and C round it under the
    effective ground by C blocks of cover over the road's roof."""
    reach = m.r + m.C
    out = []
    for x, z, d in cells:
        out.append(int(m.geff[window(m, x, z, d, reach, reach)].min()) - m.C - (m.H - 1))
    return out


def climb_caps(m, cells):
    """The highest feet each road cell may have on the climb into the isle: C clear of every wet column within C of its
    cross-section (the water's cover), and its roof one block under the ground over its own cross-section."""
    out = []
    for x, z, d in cells:
        wet = m.wl[window(m, x, z, d, m.C, m.r + m.C)] >= 0
        gw = m.geff[window(m, x, z, d, m.C, m.r + m.C)]
        water = int(gw[wet].min()) - m.C - (m.H - 1) if wet.any() else 10 ** 6
        roof = int(m.geff[window(m, x, z, d, 0, m.r)].min()) - m.H
        out.append(min(water, roof))
    return out


def in_box(x, z, box):
    x0, z0, x1, z1 = box
    return x0 < x < x1 and z0 < z < z1


def profile(m, cells):
    """Feet per road cell: flat in the gatehouse, the open cut, the coast (min(the even grade, the cover's lookahead
    envelope), monotone), a flat bottom, the climb of one in one, flat in the hall. Returns (feet list, portal index,
    junction index, bottom (first, last), climb's top index, the caps)."""
    spec = m.spec
    gr = spec["grade"]
    q = int(gr["quiet_cells"])
    L = len(cells)
    cap = caps(m, cells)
    ccap = climb_caps(m, cells)
    gate = spec["gatehouse"]["box"]
    hall = lighthouse(spec)["hall"]["box"]
    n_gate = 0
    while n_gate < L and gate[0] <= cells[n_gate][0] <= gate[2] and gate[1] < cells[n_gate][1] < gate[3]:
        n_gate += 1
    if n_gate < q + 2:
        raise DriftError("the gatehouse holds %d cells of the line, fewer than its stop needs" % n_gate)
    inside = {s for s, (x, z, _d) in enumerate(cells) if in_box(x, z, hall)}
    F0 = int(spec["gatehouse"]["floor_y"]) + 1
    for x, z, _d in cells[:n_gate]:
        if m.G(x, z) != F0 - 1:
            raise DriftError("the gatehouse floor y%d is not the ground y%d at (%d, %d)" % (F0 - 1, m.G(x, z), x, z))
    F_stop = int(spec["island"]["pad_y"]) + 1
    inc = [F0 if s < n_gate else F0 - (s - n_gate + 1) // gr["incline_run"] for s in range(L)]
    s_p = next((s for s in range(n_gate, L) if inc[s] <= cap[s]), None)
    if s_p is None:
        raise DriftError("the open cut never reaches cover")
    s_top = L - 1 - q
    climb = [F_stop - max(0, s_top - s) for s in range(L)]
    # the climb fits where it is under its cap, or inside the hall; its foot may be no further east than that
    s_c = s_top
    while s_c - 1 > s_p and (s_c - 1 in inside or climb[s_c - 1] <= ccap[s_c - 1]):
        s_c -= 1
    capd = [float(cap[s]) if s not in inside else 1e9 for s in range(L)]
    U = [0.0] * L
    U[L - 1] = capd[L - 1]
    for s in range(L - 2, -1, -1):
        U[s] = min(capd[s], U[s + 1] + 1.0 / gr["max_run"])
    E = sb0 = sb1 = None
    for e in range(F_stop - 1, -60, -1):
        b1 = s_top - (F_stop - e)
        b0 = b1 - q
        if b0 <= s_p + q:
            break
        if b1 + 1 < s_c:
            continue                                  # the climb would start where it breaks its cover
        if e <= math.floor(min(U[s_p:b1 + 1]) + 1e-9) and all(e <= cap[s] for s in range(b0, b1 + 1)):
            E, sb0, sb1 = e, b0, b1
            break
    if E is None:
        raise DriftError("the climb into the isle cannot meet the coast under cover (the climb fits from cell %d, "
                         "x%d)" % (s_c, cells[s_c][0]))
    P = [0] * L
    for s in range(L):
        if s < s_p:
            P[s] = inc[s]
        elif s <= sb0:
            lin = inc[s_p] + 0.999 + (E - inc[s_p]) * (s - s_p) / float(sb0 - s_p)   # floored: a step once a block is lost
            v = int(math.floor(min(U[s], lin) + 1e-9))
            P[s] = v if s == s_p else min(v, P[s - 1])
        elif s <= sb1:
            P[s] = E
        else:
            P[s] = climb[s]
    sj = next(i for i, (x, z, _d) in enumerate(cells) if x == spec["strip_mine"]["junction_x"])
    zones = [(sj - q, sj + q)]
    for a, b in zones:
        for s in range(a, b + 1):
            if 0 < s < L and P[s] < P[s - 1]:
                if s < s_p:
                    raise DriftError("a quiet zone (%d..%d) falls in the open cut" % (a, b))
                lo = P[s]
                for t in range(a - 1, s):
                    P[t] = min(P[t], lo)
    zones += [(sb0, sb1), (s_top, L - 1), (0, n_gate - 1)]
    for s in range(1, L):
        if abs(P[s] - P[s - 1]) > 1:
            raise DriftError("profile breaks at cell %d (%d -> %d)" % (s, P[s - 1], P[s]))
        if s <= sb1 and P[s] > P[s - 1]:
            raise DriftError("the road climbs at cell %d before its bottom" % s)
        if s > sb1 and P[s] < P[s - 1]:
            raise DriftError("the road falls at cell %d on its climb" % s)
        if s_p <= s <= sb1 and P[s] > cap[s]:
            raise DriftError("cell %d (%d, %d) feet %d over its cap %d" % (s, cells[s][0], cells[s][1], P[s], cap[s]))
        if s > sb1 and s not in inside and P[s] > ccap[s]:
            raise DriftError("climb cell %d (%d, %d) feet %d over its cap %d" % (s, cells[s][0], cells[s][1], P[s], ccap[s]))
    for a, b in zones:
        for s in range(max(a, 1), b + 1):
            if s < L and P[s] != P[s - 1] and not (s == a):
                raise DriftError("a step at cell %d is inside a quiet zone (%d..%d)" % (s, a, b))
    m.n_gate, m.inside, m.zones, m.ccap = n_gate, inside, zones, ccap
    return P, s_p, sj, (sb0, sb1), s_top, cap


# ------------------------------------------------------------------ the openings

def drift(m):
    spec = m.spec
    cells = path_cells(spec)
    check_straight(cells)
    P, s_p, sj, bottom, s_top, cap = profile(m, cells)
    m.cells, m.P, m.s_p, m.sj, m.bottom, m.s_top, m.cap = cells, P, s_p, sj, bottom, s_top, cap
    r, H = m.r, m.H
    for s, (x, z, d) in enumerate(cells):
        # a cell opens the line across the road, so a column's floor is its own cell's feet and a stair is never
        # undercut by the next cell's
        if d[1] == 0:
            xa, xb, za, zb = x, x, z - r, z + r
        else:
            xa, xb, za, zb = x - r, x + r, z, z
        top = P[s] + H - 1
        if m.n_gate <= s < s_p:
            top = max(top, max(m.G(a, b) for a in range(xa, xb + 1) for b in range(za, zb + 1)))
            for a in range(-r - CLEAR_MARGIN, r + CLEAR_MARGIN + 1):
                for b in range(-r - CLEAR_MARGIN, r + CLEAR_MARGIN + 1):
                    m.open_cut.add((x + a, z + b))
        m.carve(xa, xb, za, zb, P[s], top)
    # a stair stands in the lower of two cells a block apart, facing the higher
    m.stairs = {}
    for s in range(len(cells)):
        d = cells[s][2]
        if s > 0 and P[s] == P[s - 1] - 1:
            m.stairs[s] = NAME[(-d[0], -d[1])]
        if s + 1 < len(cells) and P[s + 1] == P[s] + 1:
            m.stairs[s] = NAME[d]
    m.steps = sorted(m.stairs)


def strips(m):
    sm = m.spec["strip_mine"]
    jx = sm["junction_x"]
    zr = route(m.spec)[0][1]
    f = m.P[m.sj]
    m.strip_feet = f
    dr, dh = sm["drift_r"], sm["drift_height"]
    z_start = zr - m.r - 1
    m.carve(jx - dr, jx + dr, sm["corridor_to_z"], z_start, f, f + dh - 1, strip=True)
    cr, ch = sm["chamber"]["r"], sm["chamber"]["height"]
    cz = sm["corridor_to_z"] - cr
    m.carve(jx - cr, jx + cr, cz - cr, cz + cr, f, f + ch - 1, strip=True)
    m.chamber = (jx, cz)
    rows = []
    zb = sm["first_branch_z"]
    while zb - sm["corridor_to_z"] >= 2:
        rows.append(zb)
        zb -= sm["branch_every"]
    m.branch_rows = rows
    L, bh = sm["branch_length"], sm["branch_height"]
    m.branches = []
    for k, zb in enumerate(rows):
        for sgn in (1, -1):
            xa, xb = jx + sgn * (dr + 1), jx + sgn * (dr + L)
            m.carve(min(xa, xb), max(xa, xb), zb, zb, f, f + bh - 1, strip=True)
            m.branches.append({"k": k, "z": zb, "side": "east" if sgn > 0 else "west", "end_x": xb, "sgn": sgn})


# ------------------------------------------------------------------ the shell, ores and the passes' blocks

def dilate(a, n):
    out = a.copy()
    for axis in range(3):
        cur = out.copy()
        for k in range(1, n + 1):
            sl_a = [slice(None)] * 3
            sl_b = [slice(None)] * 3
            sl_a[axis], sl_b[axis] = slice(k, None), slice(None, -k)
            cur[tuple(sl_a)] |= out[tuple(sl_b)]
            cur[tuple(sl_b)] |= out[tuple(sl_a)]
        out = cur
    return out


def under_ground(m):
    ys = np.arange(m.Y0, m.Y1 + 1)[None, None, :]
    return ys <= m.geff[:, :, None]


def shell_cells(m):
    return dilate(m.env, m.SR) & ~m.env & under_ground(m)


def ore_for(m, x, y, z, exposed):
    """An ore for a strip-mine wall cell, or None: richer and goldier toward the corridor's far end."""
    sm = m.spec["strip_mine"]
    o = sm["ores"]
    span = float(sm["first_branch_z"] - sm["corridor_to_z"])
    t = min(1.0, max(0.0, (sm["first_branch_z"] - z) / span))
    share = (o["share_near"] + (o["share_far"] - o["share_near"]) * t) if exposed else o["hidden_share"]
    if u(m.spec["seed"], x, y, z, 41) >= share:
        return None
    return deep(m, pick(o["far"] if t >= 0.5 else o["near"], m.spec["seed"], x, y, z, 42), y)


def deep(m, ore, y):
    if y < m.spec["palette"]["rock_split_y"]:
        return m.spec["strip_mine"]["ores"]["deep_variant"] % ore.split(":")[1]
    return ore


def rock(m, x, y, z):
    pal = m.spec["palette"]
    return pick(pal["rock_upper"] if y >= pal["rock_split_y"] else pal["rock_lower"], m.spec["seed"], x, y, z, 21)


def blocks(m):
    """{pass: [commands]} for the whole build."""
    spec, sea = m.spec, m.sea
    out = {p: [] for p in PASSES}
    # the isle
    m.isle_cells = {}
    hab = set((h[0], h[1], h[2]) for h in habitat_positions(m))
    for (x, z), (top, kind, b) in sorted(m.isle.items()):
        ys = []
        for y in range(b + 1, top + 1):
            blk = isle_block(spec, sea, x, y, z, top, kind)
            if (x, y, z) in hab:
                blk = spec["palette"]["stack_rock"][0]
            ys.append((y, blk))
            m.isle_cells[(x, y, z)] = blk
        out["island"] += [RM.cmd(x, a, c, z, bl) for a, c, bl in RM.column_runs(x, z, ys)]
    # the trees over the open cut
    for (x, z) in sorted(m.open_cut):
        gy = int(m.base[x - m.X0, z - m.Z0])
        out["clear"].append(RM.cmd(x, gy + 1, gy + CLEAR_UP, z, AIR))
    # the shell, with the strips' ores
    sh = shell_cells(m)
    near_strip = dilate(m.strip, m.SR) & ~dilate(m.env & ~m.strip, m.SR)
    exposed = dilate(m.strip, 1)
    m.ore_cells = {}
    cols = {}
    for i, k, j in np.argwhere(sh):
        x, z, y = int(i + m.X0), int(k + m.Z0), int(j + m.Y0)
        blk = None
        if near_strip[i, k, j]:
            ex = bool(exposed[i, k, j]) and (abs(int(m.strip[min(i + 1, m.nx - 1), k, j]) + int(m.strip[max(i - 1, 0), k, j])
                                               + int(m.strip[i, min(k + 1, m.nz - 1), j]) + int(m.strip[i, max(k - 1, 0), j])
                                               + int(m.strip[i, k, min(j + 1, m.ny - 1)]) + int(m.strip[i, k, max(j - 1, 0)])) > 0)
            blk = ore_for(m, x, y, z, ex)
            if blk:
                m.ore_cells[(x, y, z)] = (blk, ex)
        if blk is None:
            blk = rock(m, x, y, z)
        cols.setdefault((x, z), []).append((y, blk))
    # every branch ends on a seam
    o = spec["strip_mine"]["ores"]
    f = m.strip_feet
    for br in m.branches:
        face = [(br["end_x"] + br["sgn"], y, z) for y in range(f - 1, f + 3) for z in (br["z"] - 1, br["z"], br["z"] + 1)]
        face.sort(key=lambda c: h32(spec["seed"], c[0], c[1], c[2], 43))
        t = min(1.0, max(0.0, (spec["strip_mine"]["first_branch_z"] - br["z"])
                         / float(spec["strip_mine"]["first_branch_z"] - spec["strip_mine"]["corridor_to_z"])))
        for (x, y, z) in face[:o["end_seam"]]:
            if not sh[m.ix(x, y, z)]:
                continue
            blk = deep(m, pick(o["far"] if t >= 0.5 else o["near"], spec["seed"], x, y, z, 44), y)
            cols[(x, z)] = [(yy, bb) for yy, bb in cols[(x, z)] if yy != y] + [(y, blk)]
            ex = any(m.strip[m.ix(x + a, y + b, z + c)] for a, b, c in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))
            m.ore_cells[(x, y, z)] = (blk, ex)
    m.shell_n = int(sh.sum())
    for (x, z) in sorted(cols):
        out["shell"] += [RM.cmd(x, a, c, z, bl) for a, c, bl in RM.column_runs(x, z, cols[(x, z)])]
    # the air: every opened cell at or under the effective ground (over it the open cut and the buildings are air)
    ug = m.env & under_ground(m)
    for i, k in np.argwhere(ug.any(axis=2)):
        x, z = int(i + m.X0), int(k + m.Z0)
        js = np.nonzero(ug[i, k])[0]
        out["air"] += [RM.cmd(x, a, c, z, AIR) for a, c, _b in RM.column_runs(x, z, [(int(j + m.Y0), AIR) for j in js])]
    fittings(m, sh)
    surface(m)
    # the line's blocks where a building writes its own (its air) go in the surface pass instead
    for p in [p for p in m.fit if p in m.surf and (p in m.rail_order or p in m.line_extras)]:
        m.surf[p] = m.fit.pop(p)
    delicate = ("lantern", "rail", "fence", "barrel", "lever", "button", "sign", "glass")

    def order(kv):
        """Solids first; then the power (levers, buttons), so a rail placed later finds its source; then the other
        delicate blocks; then the rails in the line's order, so each new rail meets the one before it, as a player
        lays track (vanilla re-shapes a placed rail from its neighbours)."""
        (x, y, z), b = kv
        if (x, y, z) in m.rail_order:
            return (3, m.rail_order[(x, y, z)], 0, 0)
        if "lever" in b or "button" in b:
            return (1, y, x, z)
        return (2 if any(d in b for d in delicate) else 0, y, x, z)
    out["fittings"] = ["setblock %d %d %d %s" % (x, y, z, b) for (x, y, z), b in sorted(m.fit.items(), key=order)]
    solid = [(p, b) for p, b in m.surf.items() if not any(d in b for d in delicate)]
    soft = [(p, b) for p, b in m.surf.items() if any(d in b for d in delicate)]
    scols = {}
    for (x, y, z), b in solid:
        scols.setdefault((x, z), []).append((y, b))
    for (x, z) in sorted(scols):
        out["surface"] += [RM.cmd(x, a, c, z, b) for a, c, b in RM.column_runs(x, z, scols[(x, z)])]
    out["surface"] += ["setblock %d %d %d %s" % (x, y, z, b) for (x, y, z), b in sorted(soft, key=order)]
    return out


def fittings(m, sh):
    spec = m.spec
    pal, road = spec["palette"], spec["road"]
    r, H = m.r, m.H

    def quiet(s):
        return any(a <= s <= b for a, b in m.zones)

    def stair_block(y):
        return pal["stair_upper"] if y >= pal["rock_split_y"] else pal["stair_lower"]

    L = len(m.cells)
    steps = set(m.steps)
    m.boards, m.lane_cells = [], 0
    for s, (x, z, d) in enumerate(m.cells):
        px, pz = -d[1], d[0]
        y = m.P[s]
        if s in m.stairs:
            for o in range(-r, r + 1):
                if o == 0:
                    continue                         # the middle column carries the rail line's ascending rail
                m.fit[(x + px * o, y, z + pz * o)] = stair(stair_block(y), m.stairs[s])
        else:
            # the paved road: the footpaths' floor either side of the rail's bed, the lane edges dashed in calcite
            for o in range(-r, r + 1):
                if o == 0:
                    continue
                fx, fz = x + px * o, z + pz * o
                if not sh[m.ix(fx, y - 1, fz)]:
                    continue
                dash = abs(o) == 1 and (s % (road["dash_on"] + road["dash_off"])) < road["dash_on"]
                m.fit[(fx, y - 1, fz)] = road["lane"] if dash else (
                    road["surface_upper"] if y - 1 >= pal["rock_split_y"] else road["surface_lower"])
                m.lane_cells += dash
        n = s - m.s_p
        if s >= m.s_p and n % spec["lights"]["every"] == spec["lights"]["every"] // 2:
            for o in (-r, r):                         # a pair of road lamps over the footpaths
                lx, lz = x + px * o, z + pz * o
                if m.opened(lx, y + H - 1, lz) and sh[m.ix(lx, y + H, lz)]:
                    m.fit[(lx, y + H - 1, lz)] = HANG
        if (s >= m.s_p + 2 and n % spec["lights"]["frames_every"] == 0 and not quiet(s) and s not in m.inside
                and not ({s - 1, s, s + 1} & steps)):
            for side in (-1, 1):
                wx, wz = x + px * (r + 1) * side, z + pz * (r + 1) * side
                for yy in range(y, y + H):
                    if sh[m.ix(wx, yy, wz)]:
                        m.fit[(wx, yy, wz)] = pal["post"] + "[axis=y]"
            for o in range(-(r + 1), r + 2):
                bx, bz = x + px * o, z + pz * o
                if sh[m.ix(bx, y + H, bz)]:
                    m.fit[(bx, y + H, bz)] = pal["beam"]
        # the distance boards: one each wall every boards_every cells, counting to the gate ahead on that side
        if s >= m.s_p and s not in m.inside and not quiet(s) and (s - m.s_p) % road["boards_every"] == road["boards_every"] // 2:
            for side, (dest, left) in ((1, (lighthouse(spec)["display_name"], L - 1 - s)),
                                       (-1, (spec["gatehouse"]["display_name"], s))):
                sx, sz = x + px * r * side, z + pz * r * side
                wx, wz = x + px * (r + 1) * side, z + pz * (r + 1) * side
                if m.opened(sx, y + 2, sz) and sh[m.ix(wx, y + 2, wz)] and (sx, y + 2, sz) not in m.fit:
                    m.fit[(sx, y + 2, sz)] = wall_sign(pal["sign_wood"], NAME[(-px * side, -pz * side)],
                                                       [dest, "{:,} blocks".format(left), spec["road"]["board_line"], ""])
                    m.boards.append((sx, y + 2, sz, dest, left))
    # the strips: corridor lanterns, one at every branch end, one in the chamber; the barrel
    sm = spec["strip_mine"]
    jx, f = sm["junction_x"], m.strip_feet
    zr = route(spec)[0][1]
    for z in range(zr - r - 1, sm["corridor_to_z"] - 1, -spec["lights"]["every"]):
        m.fit[(jx, f + sm["drift_height"] - 1, z)] = HANG
    for br in m.branches:
        m.fit[(br["end_x"], f + sm["branch_height"] - 1, br["z"])] = HANG
    cx, cz = m.chamber
    cr = sm["chamber"]["r"]
    m.fit[(cx, f + sm["chamber"]["height"] - 1, cz)] = HANG
    m.strip_barrel = (cx, f, cz - cr)
    m.fit[m.strip_barrel] = "minecraft:barrel[facing=south,open=false]"
    rail_line(m, sh)


# ------------------------------------------------------------------ the rail line

N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
LEVER = "minecraft:lever[face=ceiling,facing=north,powered=true]"


def boost_every(spec):
    """At least every this many rails on the flat is a powered rail (data rail_line boost_every)."""
    return int(spec["rail_line"]["boost_every"])


def line_cells(m):
    """[(x, y, z)] the rail line in route order, the gatehouse's stop first: the road's centre, end to end."""
    return [(x, m.P[s], z) for s, (x, z, _d) in enumerate(m.cells)]


def rail_shapes(cells):
    """The shape each rail must have to join its neighbours on the line: ascending toward a neighbour one block up,
    straight between opposite neighbours. A turn is refused: the line is straight."""
    out = []
    for i, (x, y, z) in enumerate(cells):
        dirs = []
        for k in (i - 1, i + 1):
            if not 0 <= k < len(cells):
                continue
            a, b, c = cells[k]
            d = (a - x, c - z)
            if abs(d[0]) + abs(d[1]) != 1 or abs(b - y) > 1:
                raise DriftError("the rail line breaks between (%d, %d, %d) and (%d, %d, %d)" % (x, y, z, a, b, c))
            dirs.append((d, b - y))
        straight = len(dirs) == 1 or dirs[0][0] == (-dirs[1][0][0], -dirs[1][0][1])
        up = [d for d, dy in dirs if dy == 1]
        if len(up) > 1 or (up and not straight):
            raise DriftError("the rail at (%d, %d, %d) cannot climb to both neighbours or climb into a turn" % (x, y, z))
        if up:
            out.append("ascending_" + NAME[up[0]])
        elif straight:
            out.append("east_west" if dirs[0][0][1] == 0 else "north_south")
        else:
            ns = next(d for d, _dy in dirs if d[1])
            ew = next(d for d, _dy in dirs if d[0])
            out.append("%s_%s" % (NAME[ns], NAME[ew]))
    return out


def refuse_turn(cell, shape):
    """The line is straight: a rail that would turn is a fault in the line, never a curve to lay."""
    raise DriftError("the rail at %s is a curve (%s): the line is straight" % (cell, shape))


def lever_cell(m, sh, x, y, z):
    """Where the hidden power of a powered rail at (x, y, z) goes, or None: the rock cell under the rail's bed, under
    the ground (the shell's, or the ground's own rock) with no opened cell beside it, so the lever on its ceiling is
    sealed in rock."""
    p, bed = (x, y - 2, z), (x, y - 1, z)
    if p in m.fit or bed[1] > m.G(x, z) or m.opened(*bed) or m.opened(*p):
        return None
    if any(m.opened(p[0] + a, p[1] + b, p[2] + c) for a, b, c in N6):
        return None
    return p


def write_power(m, p):
    m.fit[p] = LEVER


def write_rail(m, p, block):
    m.fit[p] = block


def rail_line(m, sh):
    """The line's rails, their levers, both stops' buttons, into m.fit (moved to the surface pass where a building's
    own blocks would overwrite them). Each stop's buffer is its building's wall, written by surface()."""
    rl = m.spec["rail_line"]
    pal = m.spec["palette"]
    cells = line_cells(m)
    shapes = rail_shapes(cells)
    n = len(cells)
    kinds = ["filler"] * n
    for i, s in enumerate(shapes):
        if s.startswith("ascending_"):
            kinds[i] = "booster"
        elif s not in ("east_west", "north_south"):
            refuse_turn(cells[i], s)
            kinds[i] = "curve"
    for i in (0, 1, n - 2, n - 1):
        if kinds[i] != "filler" or cells[i][1] != cells[1 if i < 2 else n - 2][1]:
            raise DriftError("the line's stop or station at %s is not on the flat" % (cells[i],))
    kinds[0] = kinds[-1] = "stop"
    kinds[1] = kinds[-2] = "station"
    for i in (2, n - 3):                       # never a detector rail beside the station: a passing cart would power it
        kinds[i] = "booster"
    every = boost_every(m.spec)
    levers, run, m.rail_max_unboosted = {}, 0, 0
    for i, (x, y, z) in enumerate(cells):
        ahead = 0                                  # rails that cannot be boosted next (a curve, were one ever laid)
        while i + 1 + ahead < n and kinds[i + 1 + ahead] == "curve":
            ahead += 1
        if kinds[i] == "filler" and run + 1 + ahead >= every:
            lv = lever_cell(m, sh, x, y, z)
            if lv:
                kinds[i] = "booster"
        if kinds[i] == "booster":
            lv = lever_cell(m, sh, x, y, z)
            if lv is None:
                raise DriftError("no sealed place for the power under the powered rail at (%d, %d, %d)" % (x, y, z))
            levers[i] = lv
            run = 0
            continue
        run += 1
        m.rail_max_unboosted = max(m.rail_max_unboosted, run)
    if m.rail_max_unboosted >= every:
        raise DriftError("%d rails run unboosted, at least %d" % (m.rail_max_unboosted, every))
    for i in sorted(levers):
        write_power(m, levers[i])
    blk = {"booster": "%s[shape=%%s,powered=true,waterlogged=false]" % pal["rail"],
           "stop": "%s[shape=%%s,powered=false,waterlogged=false]" % pal["rail"],
           "station": "%s[shape=%%s,powered=false,waterlogged=false]" % rl["station"],
           "filler": "%s[shape=%%s,powered=false,waterlogged=false]" % rl["filler"],
           "curve": "minecraft:rail[shape=%s,waterlogged=false]"}      # never written: refuse_turn() stops it first
    m.rail_order = {}
    for i, (p, k, s) in enumerate(zip(cells, kinds, shapes)):
        if p in m.fit:
            raise DriftError("the rail at %s would replace %s" % (p, m.fit[p]))
        write_rail(m, p, blk[k] % s)
        m.rail_order[p] = i
    m.line, m.line_kinds, m.levers = cells, kinds, levers
    m.rails = n
    # the stops: the building's wall beyond each end is the buffer; a button on the floor beside the stop launches
    m.line_extras = set()
    m.stops = []
    boxes = (m.spec["gatehouse"]["box"], lighthouse(m.spec)["hall"]["box"])
    for (end, nxt), box in zip(((0, 1), (n - 1, n - 2)), boxes):
        (x, y, z), (a, _b, c) = cells[end], cells[nxt]
        bx, bz = 2 * x - a, 2 * z - c
        x0, z0, x1, z1 = box
        if not ((bx in (x0, x1) and z0 < bz < z1) or (bz in (z0, z1) and x0 < bx < x1)):
            raise DriftError("the stop at (%d, %d, %d) is not against its building's wall" % (x, y, z))
        button = (x + (1 if a == x else 0), y, z + (1 if c == z else 0))   # one across the line, on the floor
        if not m.opened(*button) or m.opened(button[0], y - 1, button[2]):
            raise DriftError("no floor for the stop button at %s" % (button,))
        m.fit[button] = "%s[face=floor,facing=%s,powered=false]" % (rl["button"], NAME[(a - x, c - z)])
        m.line_extras.add(button)
        m.stops.append({"rail": [x, y, z], "buffer": [bx, y, bz], "button": list(button)})


# ------------------------------------------------------------------ the buildings

def building(m, box, floor_y, wall_height, line_feet, doors):
    """A stone-brick hall with spruce corners and roof over `box`: walls from floor_y + 1, air inside, a floor where the
    line does not show through it, open doors [(x, z) cells in the wall] three high. Writes into m.surf; returns the
    interior cells (x, z)."""
    pal, seed = m.spec["palette"], m.spec["seed"]
    x0, z0, x1, z1 = box
    inner = []
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            wall = x in (x0, x1) or z in (z0, z1)
            corner = x in (x0, x1) and z in (z0, z1)
            for y in range(floor_y + 1, floor_y + wall_height + 1):
                if m.opened(x, y, z) and wall:
                    continue                           # the line passes through this wall
                if corner:
                    m.surf[(x, y, z)] = pal["corner"] + "[axis=y]"
                elif wall:
                    door = (x, z) in doors and y <= floor_y + 3
                    m.surf[(x, y, z)] = AIR if door else pick(pal["wall"], seed, x, y, z, 51)
                else:
                    m.surf[(x, y, z)] = AIR
            m.surf[(x, floor_y + wall_height + 1, z)] = pal["roof"]
            if not wall:
                inner.append((x, z))
                if not m.opened(x, floor_y, z) and line_feet.get((x, z)) != floor_y + 1:
                    m.surf[(x, floor_y, z)] = pal["floor"]
            elif (x, z) in doors:
                m.surf[(x, floor_y, z)] = pal["floor"]
    return inner


def lantern_post(m, x, z, ground):
    pal = m.spec["palette"]
    m.surf[(x, ground + 1, z)] = pal["fence"]
    m.surf[(x, ground + 2, z)] = pal["fence"]
    m.surf[(x, ground + 3, z)] = STAND


def surface(m):
    spec, pal = m.spec, m.spec["palette"]
    line_feet = {(x, z): m.P[s] for s, (x, z, _d) in enumerate(m.cells)}
    r = m.r
    for s, (x, z, d) in enumerate(m.cells):         # the whole cross-section shares its cell's feet
        for o in range(-r, r + 1):
            line_feet[(x - d[1] * o, z + d[0] * o)] = m.P[s]
    # -- Foothill Gate: over the line's head, the stop against its far wall, doors north and south, a sign over each
    gh = spec["gatehouse"]
    gx0, gz0, gx1, gz1 = gh["box"]
    fy = gh["floor_y"]
    gdoors = {(x, z) for x in range(gh["doors_x"][0], gh["doors_x"][1] + 1) for z in (gz0, gz1)}
    building(m, gh["box"], fy, gh["wall_height"], line_feet, gdoors)
    m.gate_signs = []
    sx = (gh["doors_x"][0] + gh["doors_x"][1]) // 2
    for z, out, facing in ((gz0, -1, "north"), (gz1, 1, "south")):
        p = (sx, fy + 4, z + out)
        m.surf[p] = wall_sign(pal["sign_wood"], facing, gh["sign"])
        m.gate_signs.append(p)
        for lx in (gh["doors_x"][0] - 2, gh["doors_x"][1] + 2):
            lantern_post(m, lx, z + 2 * out, m.G(lx, z + 2 * out))
    for lx in (gx0 + 3, gx1 - 3):
        m.surf[(lx, fy + gh["wall_height"], (gz0 + gz1) // 2 - 3)] = HANG
        m.surf[(lx, fy + gh["wall_height"], (gz0 + gz1) // 2 + 3)] = HANG
    # -- the portal: a stone-brick headwall over the road's opening where the cut goes under a roof
    s = m.s_p
    x, z, d = m.cells[s]
    px, pz = -d[1], d[0]
    y = m.P[s]
    for o in range(-(m.r + 1), m.r + 2):
        cx, cz = x + px * o, z + pz * o
        top = m.G(cx, cz)
        for yy in range(y, top + 1):
            if not m.opened(cx, yy, cz):
                m.surf[(cx, yy, cz)] = "minecraft:stone_bricks"
    m.portal = (x, y, z)
    # -- Driftmouth Light: the keeper's hall the road climbs into, and the tower
    isl = spec["island"]
    lh = isl["lighthouse"]
    pad = isl["pad_y"]
    hb = lh["hall"]
    hx0, hz0, hx1, hz1 = hb["box"]
    hdoors = {(x, hz1) for x in range(hb["door_x"][0], hb["door_x"][1] + 1)}
    tb = lh["tower"]
    tx0, tz0, tx1, tz1 = tb["box"]
    if tz1 != hz0 or not (hx0 <= tx0 and tx1 <= hx1) or tx1 - tx0 != 6 or tz1 - tz0 != 6:
        raise DriftError("the tower %s must be 7 by 7 and stand on the hall's north wall %s" % (tb["box"], hb["box"]))
    tdoor = tuple(tb["door"])
    if tdoor != (tx0 + 3, hz0):
        raise DriftError("the tower's door %s is not the middle of its south wall, the hall's north wall" % (tdoor,))
    inner = building(m, hb["box"], pad, hb["wall_height"], line_feet, hdoors | {tdoor})
    # the hole the road climbs out of, fenced where it is not the landing (the road's own floor at the stop's level)
    hole = {(x, z) for (x, z) in inner if m.opened(x, pad, z)}
    for (x, z) in hole:
        for (a, b) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + a, z + b)
            if q in hole or q not in inner or line_feet.get(q) == pad + 1:
                continue
            m.surf[(q[0], pad + 1, q[1])] = pal["fence"]
    m.hole = hole
    zc = (hz0 + hz1) // 2
    for lx in (hx0 + 3, hx1 - 3):
        m.surf[(lx, pad + hb["wall_height"], zc)] = HANG
    m.isle_barrel = (hx0 + 1, pad + 1, hz0 + 1)
    m.surf[m.isle_barrel] = "minecraft:barrel[facing=east,open=false]"
    dx = (hb["door_x"][0] + hb["door_x"][1]) // 2
    m.light_signs = [(dx, pad + 4, hz1 + 1)]
    m.surf[(dx, pad + 4, hz1 + 1)] = wall_sign(pal["sign_wood"], "south", lh["sign"])
    for lx in (hb["door_x"][0] - 2, hb["door_x"][1] + 2):
        lantern_post(m, lx, hz1 + 2, m.G(lx, hz1 + 2))
    # outside the door: a path south to the shingle
    m.path = []
    z = hz1 + 1
    while True:
        tops = [m.isle.get((x, z)) for x in range(hb["door_x"][0], hb["door_x"][1] + 1)]
        if any(t is None or t[0] <= m.sea + 2 for t in tops):
            break
        for x in range(hb["door_x"][0], hb["door_x"][1] + 1):
            t = m.isle[(x, z)][0]
            if (x, t + 1, z) not in m.surf and (x, t, z) not in m.surf:
                m.surf[(x, t, z)] = pal["path"]
                m.path.append((x, t, z))
        z += 1
    tower(m, lh, pad, tdoor)


def tower(m, lh, pad, tdoor):
    """The lighthouse's tower: striped walls, a spiral stair round a lit core from the hall's door to the lantern room,
    the glazed lantern room with the lamp, a gallery round it and a copper cap."""
    pal, seed = m.spec["palette"], m.spec["seed"]
    tb = lh["tower"]
    tx0, tz0, tx1, tz1 = tb["box"]
    feet_lr = int(tb["lantern_room_feet"])
    band = int(tb["band"])
    # lamps round the foot, under the gallery's overhang
    for lx, lz in ((tx0 - 2, tz0 - 2), (tx1 + 2, tz0 - 2), (tx0 - 2, tz1 - 2), (tx1 + 2, tz1 - 2)):
        lantern_post(m, lx, lz, m.G(lx, lz))
    # the walls, in bands, to the lantern room's floor; the door into the hall
    for x in range(tx0, tx1 + 1):
        for z in range(tz0, tz1 + 1):
            if x in (tx0, tx1) or z in (tz0, tz1):
                for y in range(pad + 1, feet_lr):
                    if (x, z) == tdoor and y <= pad + 2:
                        m.surf[(x, y, z)] = AIR
                        continue
                    m.surf[(x, y, z)] = tb["bands"][((y - pad - 1) // band) % len(tb["bands"])]
            else:
                for y in range(pad + 1, feet_lr + 3):
                    m.surf[(x, y, z)] = AIR
    # the core: 3 by 3 of stone brick, a light in each face every core_light_every blocks
    ix0, iz0 = tx0 + 1, tz0 + 1
    for i in range(1, 4):
        for j in range(1, 4):
            for y in range(pad + 1, feet_lr - 1):
                m.surf[(ix0 + i, y, iz0 + j)] = pal["core"]
    m.core_lights = []
    for y in range(pad + 3, feet_lr - 1, int(tb["core_light_every"])):
        for (i, j) in ((1, 2), (3, 2), (2, 1), (2, 3)):
            m.surf[(ix0 + i, y, iz0 + j)] = tb["core_light"]
            m.core_lights.append((ix0 + i, y, iz0 + j))
    # the spiral: round the ring from the door's cell, a stair on each side cell (one block up), a landing at each corner
    ring = [(2, 4), (3, 4), (4, 4), (4, 3), (4, 2), (4, 1), (4, 0), (3, 0), (2, 0), (1, 0), (0, 0), (0, 1), (0, 2), (0, 3),
            (0, 4), (1, 4)]
    if (ix0 + 2, iz0 + 4) != (tdoor[0], tdoor[1] - 1):
        raise DriftError("the tower's door does not open on the spiral's first cell")
    cur, k, last = pad + 1, 1, {}
    m.spiral = []
    while cur < feet_lr:
        i, j = ring[k % 16]
        pi, pj = ring[(k - 1) % 16]
        x, z = ix0 + i, iz0 + j
        if i in (0, 4) and j in (0, 4):
            m.surf[(x, cur - 1, z)] = pal["landing"]
            last[(i, j)] = cur - 1
        else:
            m.surf[(x, cur, z)] = stair(pal["tower_stair"], NAME[(i - pi, j - pj)])
            last[(i, j)] = cur
            cur += 1
        m.spiral.append((x, z, cur))
        k += 1
    # the lantern room's floor, open over the spiral's last flight
    for i in range(5):
        for j in range(5):
            if (i, j) in last and last[(i, j)] >= feet_lr - 3:
                continue
            m.surf[(ix0 + i, feet_lr - 1, iz0 + j)] = pal["landing"]
    # the gallery: a cornice one block out, a railing on it
    for x in range(tx0 - 1, tx1 + 2):
        for z in range(tz0 - 1, tz1 + 2):
            if x in (tx0 - 1, tx1 + 1) or z in (tz0 - 1, tz1 + 1):
                m.surf[(x, feet_lr - 1, z)] = pal["landing"]
                m.surf[(x, feet_lr, z)] = pal["fence"]
            elif x in (tx0, tx1) or z in (tz0, tz1):
                m.surf[(x, feet_lr - 1, z)] = pal["landing"]
    # the lantern room: glazed all round, the lamp two high in its middle, a copper cap
    for x in range(tx0, tx1 + 1):
        for z in range(tz0, tz1 + 1):
            edge = x in (tx0, tx1) or z in (tz0, tz1)
            corner = x in (tx0, tx1) and z in (tz0, tz1)
            for y in range(feet_lr, feet_lr + 3):
                if corner:
                    m.surf[(x, y, z)] = pal["beam"]
                elif edge:
                    m.surf[(x, y, z)] = tb["glazing"]
    lx, lz = ix0 + 2, iz0 + 2
    m.lamp = [(lx, feet_lr, lz), (lx, feet_lr + 1, lz)]
    for p in m.lamp:
        m.surf[p] = tb["lamp"]
    for k, y in enumerate(range(feet_lr + 3, feet_lr + 7)):
        for x in range(tx0 + k, tx1 - k + 1):
            for z in range(tz0 + k, tz1 - k + 1):
                m.surf[(x, y, z)] = pal["beam"]
    m.tower_top = feet_lr + 6


# ------------------------------------------------------------------ the Habitat Blocks' places

def habitat_positions(m):
    """[(x, y, z, id, place)] for every Habitat Block the isle carries, in the isle's rock."""
    spec = m.spec
    w = spec["waters"]
    out = []
    for st in spec["island"]["stacks"]:
        b = m.isle[(st["x"], st["z"])][2]
        out.append((st["x"], m.sea - w["high_below_sea"], st["z"], "%sstack_%s_high" % (HABITAT_PREFIX, st["id"]),
                    "Driftmouth Isle, the %s sea stack: inside its rock, 4 under the sea (the surface and the upper water)" % st["id"].upper()))
        out.append((st["x"], b + w["low_above_seabed"], st["z"], "%sstack_%s_low" % (HABITAT_PREFIX, st["id"]),
                    "Driftmouth Isle, the %s sea stack: inside its rock, 10 over the seabed (the deep water and the floor)" % st["id"].upper()))
    for k, (x, z) in enumerate(w["shore"]):
        out.append((x, m.sea - w["high_below_sea"], z, "%sshore_%s" % (HABITAT_PREFIX, "north" if z < spec["island"]["centre"]["z"] else "south"),
                    "Driftmouth Isle: inside its own shore rock, 4 under the sea"))
    return out


# ------------------------------------------------------------------ checks

def checks(m):
    p = []
    # cover: every opened column against the painted water within C, Chebyshev
    C = m.C
    wet = m.wl >= 0
    wb = np.where(wet, m.geff + 1, 10 ** 6)
    pad = np.pad(wb, C, mode="edge")
    mn = np.full_like(wb, 10 ** 6)
    for a in range(2 * C + 1):
        for b in range(2 * C + 1):
            mn = np.minimum(mn, pad[a:a + m.nx, b:b + m.nz])
    anyenv = m.env.any(axis=2)
    top_env = np.where(anyenv, m.Y0 + m.ny - 1 - np.argmax(m.env[:, :, ::-1], axis=2), -999)
    gap = np.where(anyenv & (mn < 10 ** 6), mn - 1 - top_env, 10 ** 6)
    m.min_cover = int(gap.min())
    if m.min_cover < C:
        i, k = np.unravel_index(np.argmin(gap), gap.shape)
        p.append("cover: %d solid blocks between the opening at (%d, %d) and the water, under the %d required"
                 % (m.min_cover, i + m.X0, k + m.Z0, C))
    m.sea_cells = [s for s, (x, z, _d) in enumerate(m.cells) if m.wl[x - m.X0, z - m.Z0] >= 0]
    # habitat blocks sit in the isle's rock with rock on all six sides and nothing opened near
    hab = habitat_positions(m)
    for (x, y, z, hid, _pl) in hab:
        for a, b, c in ((0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            if (x + a, y + b, z + c) not in m.isle_cells:
                p.append("habitat %s: (%d, %d, %d) is not inside the isle's rock" % (hid, x + a, y + b, z + c))
                break
        if dilate_hit(m, x, y, z, m.SR + 1):
            p.append("habitat %s: within reach of the road's openings" % hid)
    # every branch shows at least one ore
    for br in m.branches:
        cells = [c for c, (_b, ex) in m.ore_cells.items() if ex and c[2] in (br["z"] - 1, br["z"], br["z"] + 1)
                 and (c[0] - m.spec["strip_mine"]["junction_x"]) * br["sgn"] > m.spec["strip_mine"]["drift_r"]]
        br["exposed"] = len(cells)
        if not cells:
            p.append("branch %s %d shows no ore" % (br["side"], br["z"]))
    m.problems = p
    return p


def dilate_hit(m, x, y, z, n):
    i, k, j = m.ix(x, y, z)
    return bool(m.env[max(0, i - n):i + n + 1, max(0, k - n):k + n + 1, max(0, j - n):j + n + 1].any())


# ------------------------------------------------------------------ the build

def model(source_root=None, spec=None):
    spec = spec or load()
    g = G.load(source_root)
    m = Model(spec, g)
    drift(m)
    strips(m)
    m.lines = blocks(m)
    checks(m)
    return m


def trip_seconds(m):
    """The least time a cart can take, end to end: the cited cap of 8 blocks a second on each axis, over the line's
    horizontal length (its climbs add nothing on the other axis: they are made along the line)."""
    return len(m.cells) / 8.0


def summary(m):
    isl = m.spec["island"]
    above = sum(1 for (t, k, _b) in m.isle.values() if k in ("core", "pad") and t > m.sea)
    core = sum(1 for (t, k, _b) in m.isle.values() if k in ("core", "pad"))
    ores = {}
    for (_c, (b, ex)) in m.ore_cells.items():
        key = b.split(":")[1] + (" exposed" if ex else " hidden")
        ores[key] = ores.get(key, 0) + 1
    sea_feet = [m.P[s] for s in m.sea_cells]
    L = len(m.cells)
    prof = [{"s": s, "x": m.cells[s][0], "z": m.cells[s][1], "feet": m.P[s], "ground": m.G(m.cells[s][0], m.cells[s][1]),
             "water": int(m.wl[m.cells[s][0] - m.X0, m.cells[s][1] - m.Z0])} for s in list(range(0, L, 50)) + [L - 1]]
    hab = [{"id": h[3], "x": h[0], "y": h[1], "z": h[2]} for h in habitat_positions(m)]
    sb0, sb1 = m.bottom
    return {
        "cover_required": m.C,
        "cover_min_measured": m.min_cover,
        "route_cells": L, "trip_seconds_at_8_per_second": trip_seconds(m),
        "ends": [list(m.cells[0][:2]), list(m.cells[-1][:2])],
        "portal_cell": m.s_p, "portal": list(m.portal),
        "mouth_feet": m.P[0], "bottom": {"feet": m.P[sb0], "from_x": m.cells[sb0][0], "to_x": m.cells[sb1][0]},
        "climb": {"cells": m.s_top - sb1, "from_feet": m.P[sb1], "to_feet": m.P[m.s_top]},
        "coast_grade": "1 in %.1f" % ((sb0 - m.s_p) / float(max(1, m.P[m.s_p] - m.P[sb0]))),
        "end_feet": m.P[-1], "stairs": len(m.steps), "rails": m.rails,
        "rail_line": {"kinds": {k: m.line_kinds.count(k) for k in sorted(set(m.line_kinds))},
                      "levers": len(m.levers), "max_unboosted_run": m.rail_max_unboosted,
                      "boost_every": boost_every(m.spec), "stops": m.stops},
        "road": {"lane_dash_cells": m.lane_cells, "boards": len(m.boards)},
        "sea_cells": len(m.sea_cells), "deepest_feet_under_sea": min(sea_feet) if sea_feet else None,
        "first_sea_cell": list(m.cells[m.sea_cells[0]][:2]) if m.sea_cells else None,
        "strip_feet": m.strip_feet, "branches": len(m.branches),
        "branch_exposed_ores": [b["exposed"] for b in m.branches],
        "ores": ores,
        "isle": {"columns": len(m.isle), "core_columns": core, "core_above_water": above,
                 "crown_y": max(t for (t, k, _b) in m.isle.values() if k in ("core", "pad")),
                 "centre_ground_y": m.isle[(isl["centre"]["x"], isl["centre"]["z"])][0],
                 "seabed_under_centre": m.isle[(isl["centre"]["x"], isl["centre"]["z"])][2],
                 "blocks": len(m.isle_cells)},
        "lighthouse": {"lamp": [list(p) for p in m.lamp], "tower_top_y": m.tower_top, "spiral_steps": len(m.spiral),
                       "nearest_shore": nearest_shore(m, m.lamp[0][0], m.lamp[0][2])},
        "habitat_blocks": hab,
        "strip_barrel": list(m.strip_barrel), "isle_barrel": list(m.isle_barrel),
        "shell_cells": m.shell_n,
        "lakes_in_reach": sorted(m.notes.get("lakes_in_reach", [])),
        "profile": prof,
        "problems": m.problems,
        "commands": {k: len(v) for k, v in m.lines.items()},
    }


def probes(m):
    """In-world checks for the integrating session: (x, y, z, expected block id, what)."""
    out = []
    pal, rl = m.spec["palette"], m.spec["rail_line"]
    x, y, z = m.portal
    out.append((x, y + m.H, z, "minecraft:stone_bricks", "the portal's headwall over the road's opening"))
    s = next(s for s in m.steps if s > m.s_p + 10)
    cx, cz, d = m.cells[s]
    px, pz = -d[1], d[0]
    out.append((cx + px, m.P[s], cz + pz, pal["stair_upper"] if m.P[s] >= pal["rock_split_y"] else pal["stair_lower"],
                "a stair on the road's floor"))
    s = next(s for s in range(m.s_p + 1, len(m.cells)) if s not in m.stairs and (s % (m.spec["road"]["dash_on"] + m.spec["road"]["dash_off"])) == 0)
    cx, cz, d = m.cells[s]
    out.append((cx - d[1], m.P[s] - 1, cz + d[0], m.spec["road"]["lane"], "a lane dash beside the rail"))
    if m.sea_cells:
        s = min(m.sea_cells, key=lambda t: m.G(m.cells[t][0], m.cells[t][1]) - m.P[t])
        cx, cz, _d = m.cells[s]
        out.append((cx, m.P[s] + m.H - 1, cz, "minecraft:air", "the road's roof row under the sea's least cover"))
        out.append((cx, m.P[s] + m.H, cz, "a rock block (stone, deepslate, tuff, andesite or cobbled deepslate)",
                    "the rock over it; the sea floor at y%d" % m.G(cx, cz)))
    out.append(tuple(m.strip_barrel) + ("minecraft:barrel", "the strips' cache"))
    out.append(tuple(m.isle_barrel) + ("minecraft:barrel", "the isle's cache in the keeper's hall"))
    b = m.boards[0]
    out.append(b[:3] + ("minecraft:%s_wall_sign" % pal["sign_wood"], "a distance board: %s, %d blocks" % (b[3], b[4])))
    for p in m.gate_signs[:1]:
        out.append(p + ("minecraft:%s_wall_sign" % pal["sign_wood"], "Foothill Gate's sign over its north door"))
    lh = m.spec["island"]["lighthouse"]
    out.append(m.light_signs[0] + ("minecraft:%s_wall_sign" % pal["sign_wood"], "Driftmouth Light's sign over the hall's door"))
    out.append(m.lamp[0] + (lh["tower"]["lamp"], "the lighthouse's lamp, in the glazed lantern room"))
    tx0, tz0, _tx1, _tz1 = lh["tower"]["box"]
    out.append((tx0 + 3, lh["tower"]["lantern_room_feet"] + 1, tz0, lh["tower"]["glazing"], "the lantern room's glazing, north face"))
    hx0, _hz0, _hx1, hz1 = lh["hall"]["box"]
    out.append((lh["hall"]["door_x"][0], m.spec["island"]["pad_y"] + 1, hz1, "minecraft:air", "the keeper's hall's south door"))
    for h in habitat_positions(m)[:2]:
        out.append((h[0], h[1], h[2], "cobblemon:habitat_block (after cobblers_habitats)", h[3]))
    # the rail line: both stops, a climb's powered rail and its lever, a flat booster, a detector
    for st, where in zip(m.stops, ("Foothill Gate", "Driftmouth Light's hall")):
        out.append(tuple(st["rail"]) + ("%s[shape=east_west,powered=false]" % pal["rail"],
                                        "the stop in %s: unpowered until its button is pressed" % where))
        out.append(tuple(st["buffer"]) + ("a solid full block (the building's wall)", "the buffer at %s's stop" % where))
        out.append(tuple(st["button"]) + ("%s[face=floor]" % rl["button"], "the launch button in %s" % where))
    shown = set()
    for p, k in zip(m.line, m.line_kinds):
        b = m.surf.get(p) or m.fit.get(p)
        tag = "climb" if k == "booster" and "ascending" in b else k
        if tag in shown or tag in ("stop", "station"):
            continue
        shown.add(tag)
        out.append(p + (b, "the rail line: a %s" % {"climb": "climb's powered rail (powered=true)", "booster": "flat booster (powered=true)",
                                                    "filler": "detector rail"}[tag]))
        if k == "booster":
            lv = m.levers[m.line.index(p)]
            out.append(lv + (LEVER, "the sealed lever powering the rail two blocks over it"))
    i = m.s_top - 10                                 # the climb into the isle, under its crown
    out.append(m.line[i] + (m.fit.get(m.line[i]) or m.surf.get(m.line[i]), "the climb into the isle: an ascending powered rail"))
    out.append(m.levers[i] + (LEVER, "its sealed lever"))
    return [{"x": a, "y": b, "z": c, "expect": e, "what": w} for a, b, c, e, w in out]


def nearest_shore(m, x, z, reach=300):
    """The nearest column of the heightmap's own dry ground (the isle is built, so none of it is), and its distance."""
    reach = min(reach, x - m.g.ox, z - m.g.oz)
    b = m.g.box(x - reach, z - reach, x + reach, z + reach)
    js, is_ = np.nonzero(b >= m.sea)
    if not len(js):
        return None
    d = np.hypot(is_ - reach, js - reach)
    k = int(np.argmin(d))
    return {"x": x - reach + int(is_[k]), "z": z - reach + int(js[k]), "blocks": round(float(d[k]))}


def write(m):
    fn, order = RM.write_blocks(OUT, m.lines, PASSES, "tools/sea_drift.py",
                                "Cobblers: the Seaward Drift, its strip mine, Driftmouth Isle and its light (tools/sea_drift.py)")
    return order


# ------------------------------------------------------------------ the one-off staging cleanup of the first drift

def written_cells(lines):
    """{(x, y, z): block} every cell a pack's commands write, the last write winning."""
    out = {}
    for ln in lines:
        t = ln.split(" ", 7)
        if t[0] == "fill":
            x0, y0, z0, x1, y1, z1 = (int(v) for v in t[1:7])
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    for y in range(min(y0, y1), max(y0, y1) + 1):
                        out[(x, y, z)] = t[7]
        elif t[0] == "setblock":
            out[(int(t[1]), int(t[2]), int(t[3]))] = ln.split(" ", 4)[4]
    return out


def old_model(rev=OLD_REV, source_root=None):
    """The first drift's model, built by its own generator and data from `rev` (git show), with today's helpers."""
    tmp = Path(tempfile.mkdtemp(prefix="sea_drift_old_"))
    for rel, name in (("tools/sea_drift.py", "sea_drift_old.py"), ("data/sea_drift.json", "sea_drift_old.json")):
        txt = subprocess.run(["git", "show", "%s:%s" % (rev, rel)], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout
        (tmp / name).write_text(txt, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("sea_drift_old", tmp / "sea_drift_old.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    old = mod.model(source_root, spec=json.loads((tmp / "sea_drift_old.json").read_text(encoding="utf-8")))
    return mod, old


def natural(g, sea, x, y, z, surface):
    """The heightmap world's block at a cell: air over the ground and the sea, water from the ground to the sea level,
    rock under the ground. `surface` puts the export's layers back on an open column (grass on the ground, three of
    dirt): ASSUMED, the foothill woods' surface (data/spawns.json foothill_woods) round the first drift's mouth."""
    gy = g(x, z)
    if y > gy:
        return "minecraft:water" if y <= sea else AIR
    if surface and y == gy:
        return "minecraft:grass_block"
    if surface and y >= gy - 3:
        return "minecraft:dirt"
    return "minecraft:stone" if y >= 48 else "minecraft:deepslate"


ROCKS = {"minecraft:%s" % b for b in ("stone", "andesite", "tuff", "deepslate", "cobbled_deepslate", "cobblestone")}


def rocklike(b):
    """A block the first drift wrote that is rock already: its shell's rock and its ore."""
    i = bid_of(b)
    return i in ROCKS or i.endswith("_ore")


def cleanup(new, rev=OLD_REV, source_root=None):
    """{"restore": [commands]} that put every cell the first drift's pack wrote, and this build does not write, back
    to the heightmap world (rock, water to the sea level, air), and a count of what is touched. Rock the first drift
    wrote under the ground (its shell and ore) is left: it is rock already."""
    mod, old = old_model(rev, source_root)
    g, sea = new.g, new.sea
    olds = written_cells([ln for p in mod.PASSES for ln in old.lines[p]])
    news = written_cells([ln for p in PASSES for ln in new.lines[p]])
    oenv = {(int(i + old.X0), int(j + old.Y0), int(k + old.Z0)) for i, k, j in np.argwhere(old.env)}
    cut_cols = {(x, z) for (x, z) in old.open_cut} | {(x, z) for (x, y, z) in oenv if y > g(x, z) - 6}
    todo = {}
    counts = {"void_to_rock": 0, "fittings_and_buildings_under_ground_to_rock": 0, "cut_to_ground": 0,
              "isle_and_buildings_to_water": 0, "isle_and_buildings_to_air": 0, "already_natural_rock_left": 0}
    for p in set(olds) | oenv:
        if p in news:
            continue
        x, y, z = p
        b = olds.get(p, AIR)
        gy = g(x, z)
        if y <= gy and p not in oenv and rocklike(b):
            counts["already_natural_rock_left"] += 1
            continue
        nat = natural(g, sea, x, y, z, (x, z) in cut_cols and gy >= sea)
        if nat == AIR and bid_of(b) == AIR:
            continue                                   # air over the ground, opened or cleared: natural already
        if nat in ("minecraft:stone", "minecraft:deepslate"):
            nat = mod.rock(old, x, y, z)               # the first drift's own rock, as the shell round the void
        todo[p] = nat
        if y > gy:
            counts["isle_and_buildings_to_water" if nat == "minecraft:water" else "isle_and_buildings_to_air"] += 1
        elif (x, z) in cut_cols and gy - y <= 3 and gy >= sea:
            counts["cut_to_ground"] += 1
        elif p in oenv:
            counts["void_to_rock"] += 1
        else:
            counts["fittings_and_buildings_under_ground_to_rock"] += 1
    cols = {}
    for (x, y, z), b in todo.items():
        cols.setdefault((x, z), []).append((y, b))
    out = []
    for (x, z) in sorted(cols):
        out += [RM.cmd(x, a, c, z, b) for a, c, b in RM.column_runs(x, z, cols[(x, z)])]
    return {"restore": out}, counts, old


def bid_of(b):
    return b.split("[")[0].split("{")[0]


# ------------------------------------------------------------------ the records in shared files

def records(m):
    spec = m.spec
    w = spec["waters"]
    pool = "cobblers:%s" % w["pool"]
    habs = []
    for (x, y, z, hid, place) in habitat_positions(m):
        habs.append({"id": hid, "place": place, "pool": pool, "style": "activated", "replace_spawns": False,
                     "position": {"x": x, "y": y, "z": z}, "mimic": spec["palette"]["stack_rock"][0],
                     "activated": {"spawn_range": w["spawn_range"], "chance": 1.0, "trigger": "TICK",
                                   "cancel_range": w["cancel_range"], "max_spawns_per_activation": w["max_spawns_per_activation"],
                                   "max_spawns": w["max_spawns"]},
                     "status": "planned",
                     "why": "data/sea_drift.json waters: written by tools/sea_drift.py records --write from its model, in "
                            "rock its island pass writes (the mimic is that rock). Keeps up to %d of the isle's water roster "
                            "alive within %d and cancels the pack's natural spawns within %d (the Magikarp). In-water "
                            "activated spawning is not verified" % (w["max_spawns"], w["spawn_range"], w["cancel_range"])})
    verified = {}
    for r in json.loads(REWARDS.read_text(encoding="utf-8"))["rewards"]:
        if str(r.get("id", "")).startswith(REWARD_PREFIX):
            continue
        for it in r.get("contents", []):
            if it.get("verification"):
                verified.setdefault(it["item"], it["verification"])
    rew = []
    for key, at in (("strips", m.strip_barrel), ("isle", m.isle_barrel)):
        c = spec["caches"][key]
        x, y, z = at
        if key == "strips":
            cx, cz = m.chamber
            cr = spec["strip_mine"]["chamber"]["r"]
            trig = {"min": [cx - cr, y, cz - cr], "max": [cx + cr, y + 2, cz + cr]}
            place = "the Seaward Drift's strip mine: the chamber at the corridor's far end, against its north wall"
        else:
            trig = {"min": [x, y, z], "max": [x + 2, y + 2, z + 2]}
            place = "Driftmouth Isle: in Driftmouth Light's keeper's hall, its north-west corner by the tower door"
        missing = [it["item"] for it in c["contents"] if it["item"] not in verified]
        if missing:
            raise DriftError("cache %s: %s verified by no other record in data/rewards.json" % (key, missing))
        rew.append({"id": c["reward"], "kind": "cache", "place": place,
                    "contents": [dict(it, verification=verified[it["item"]]) for it in c["contents"]],
                    "message": c["message"],
                    "why": "data/sea_drift.json caches: the find that pays for the walk, as the old mine's barrels",
                    "built_by": "tools/sea_drift.py (the barrel, in cobblers_sea_drift's %s pass)" % ("fittings" if key == "strips" else "surface"),
                    "trigger": trig, "container": {"block": "minecraft:barrel", "at": [x, y, z]}})
    return habs, rew, pool_records(spec)


def pool_records(spec, spawns=None):
    """The waters' habitat record and its top-level entries for data/spawns.json, each species' spawnable position
    taken from its existing entries there."""
    spawns = spawns or json.loads(SPAWNS.read_text(encoding="utf-8"))
    w = spec["waters"]
    pos = {}

    def see(e):
        k = (e.get("pokemon") or e.get("species") or "").lower()
        if e.get("spawnable_position") and k not in pos:
            pos[k] = e["spawnable_position"]
    # NEVER this pool's own entries as a source: on 2026-10-02 the encounter rebuild removed Binacle, Clauncher and
    # Dragonair from every other table, and this loop went on finding the positions it had itself written - reading its
    # own output as input. The other tables come first; a species no other table carries takes its position from
    # Cobblemon's own spawn files (tools/position_types.py, the source tools/build_encounters.py uses), and says so.
    for e in spawns["entries"]:
        if e.get("scope") != w["pool"]:
            see(e)
    kept = {}
    upstream = None
    for ro in w["roster"]:
        for sp in [ro["pokemon"]] + [e["pokemon"] for e in ro["evolutions"]]:
            if sp not in pos:
                if upstream is None:
                    import position_types
                    jar = position_types.default_jar()
                    if jar is None:
                        # The jar cannot be read (COBBLERS_SERVER_ROOT unset). The position this pool's record already
                        # holds was chosen from the jar when it was written; it is KEPT, never re-derived, and named, so
                        # that a run with the jar re-checks it (tools/sea_drift_audit.py judges it against the jar).
                        old = next((e for e in spawns["entries"] if e.get("scope") == w["pool"] and e["species"] == sp
                                    and e.get("spawnable_position")), None)
                        if old is None:
                            raise DriftError("%s is in no other table of data/spawns.json, COBBLERS_SERVER_ROOT is unset "
                                             "and this pool holds no position for it" % sp)
                        pos[sp] = kept[sp] = old["spawnable_position"]
                        continue
                    upstream = position_types.upstream_positions(jar)
                import position_types
                pos[sp] = position_types.choose(sp, upstream)[0]
    if kept:
        print("pool: positions KEPT from this pool's own records (no jar to read): %s" % ", ".join(sorted(kept)), file=sys.stderr)
    lo, hi = w["level_band"]["minimum"], w["level_band"]["maximum"]
    level = "%d-%d" % (lo, hi)
    rar = spawns["rarity"]
    hab_entries, top = [], []
    for ro in w["roster"]:
        for k, (sp, stage) in enumerate([(ro["pokemon"], None)] + [(e["pokemon"], e) for e in ro["evolutions"]]):
            if sp not in pos:
                raise DriftError("%s has no spawnable position in data/spawns.json: it cannot be placed by rule" % sp)
            if stage is None:
                bucket, weight, ambient, why = rar[ro["rarity"]]["bucket"], float(rar[ro["rarity"]]["family_weight"]), True, "base stage"
            elif stage["level"] <= lo:
                raise DriftError("%s evolves at %d, inside the band: give it a stage split" % (sp, stage["level"]))
            else:
                bucket, weight, ambient, why = "authored-only", 0, False, "evolution requires level %d; band begins at %d" % (stage["level"], lo)
            hab_entries.append({"species": sp.capitalize(), "pokemon": sp, "family": ro["family"],
                                "family_priority": ro["rarity"], "ambient": ambient, "eligibility_reason": why,
                                "level": level, "bucket": bucket, "weight": weight, "conditions": {}})
            # "authored-only" is the established bucket INSIDE a habitat's pool (247 nested entries used it before
            # this file existed) but not one the schema allows on a top-level entry record, where every weight-0
            # record carries "ultra-rare" (264 of them). validate_data caught the top-level four, 2026-10-02.
            top.append({"id": "habitat.%s.%s" % (w["pool"], sp), "species": sp,
                        "bucket": "ultra-rare" if bucket == "authored-only" else bucket, "level": level,
                        "weight": weight, "ambient": ambient, "scope": w["pool"], "mechanism": "habitat_block",
                        "conditions": {}, "eligibility_reason": why, "spawnable_position": pos[sp]})
    isl = spec["island"]
    hab = {"id": w["pool"], "display_name": "%s waters" % isl["display_name"],
           "intended_location": "the water round %s (%d, %d): ten activated Habitat Blocks in its four sea stacks and its "
                                "shore rock (data/habitat_blocks.json %s*), each keeping up to %d alive within %d"
                                % (isl["display_name"], isl["centre"]["x"], isl["centre"]["z"], HABITAT_PREFIX,
                                   w["max_spawns"], w["spawn_range"]),
           "mechanism": "habitat_block", "replace_spawns": False,
           "level_band": {"minimum": lo, "maximum": hi},
           "why": "data/sea_drift.json waters: %s %s" % (w["level_band_why"], w["roster_why"]),
           "placement_status": "pending_or_authored_world_asset",
           "entries": hab_entries}
    return {"habitat": hab, "entries": top}


def write_records(habs, rew, pool):
    def put(path, key, recs, prefix):
        doc = json.loads(path.read_text(encoding="utf-8"))
        ids = {r["id"] for r in recs}
        doc[key] = [r for r in doc[key] if r.get("id") not in ids and not str(r.get("id", "")).startswith(prefix)] + recs
        return doc
    hd = put(HABITATS, "blocks", habs, HABITAT_PREFIX)
    rd = put(REWARDS, "rewards", rew, REWARD_PREFIX)
    sd = json.loads(SPAWNS.read_text(encoding="utf-8"))
    pid = pool["habitat"]["id"]
    sd["habitats"] = [h for h in sd["habitats"] if h.get("id") != pid] + [pool["habitat"]]
    sd["entries"] = [e for e in sd["entries"] if e.get("scope") != pid] + pool["entries"]
    for path, doc in ((HABITATS, hd), (REWARDS, rd), (SPAWNS, sd)):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:      # the files' own LF, on any platform
            fh.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=("report", "build", "records", "cleanup"))
    p.add_argument("--source-root", default=None)
    p.add_argument("--write", action="store_true", help="records: replace this build's records in the three files")
    p.add_argument("--old-rev", default=OLD_REV, help="cleanup: the commit that built the first drift")
    p.add_argument("--out", default=None, help="cleanup: the pack folder (default build/staging/cobblers_sea_drift_cleanup)")
    a = p.parse_args(argv)
    m = model(a.source_root)
    s = summary(m)
    if a.cmd == "records":
        habs, rew, pool = records(m)
        if a.write:
            write_records(habs, rew, pool)
            print("wrote %d habitat blocks, %d rewards, 1 pool with %d entries" % (len(habs), len(rew), len(pool["entries"])))
        else:
            print(json.dumps({"habitat_blocks": habs, "rewards": rew, "pool": pool}, indent=1))
        return 0
    if a.cmd == "cleanup":
        lines, counts, _old = cleanup(m, a.old_rev, a.source_root)
        out = Path(a.out) if a.out else CLEANUP_OUT
        _fn, order = RM.write_blocks(out, lines, ("restore",), "tools/sea_drift.py cleanup",
                                     "Cobblers STAGING ONLY: the first Seaward Drift (%s) put back to the heightmap world"
                                     % a.old_rev)
        print(json.dumps(counts))
        print("wrote %s: %d functions, %d commands (cobblers:%s/...)" % (out, len(order), len(lines["restore"]),
                                                                       out.name.replace("cobblers_", "")))
        return 0
    brief = {k: v for k, v in s.items() if k not in ("profile", "branch_exposed_ores")}
    print(json.dumps(brief, indent=1, default=list))
    if a.cmd == "build":
        if m.problems:
            print("NOT BUILT: %d problems" % len(m.problems))
            return 1
        order = write(m)
        s["functions"] = ["%s:%s/%s" % (NS, FOLDER, f) for f in order]
        s["probes"] = probes(m)
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(s, indent=1, default=list) + "\n", encoding="utf-8")
        print("wrote %s (%d functions) and %s" % (OUT.relative_to(ROOT), len(order), PLAN.relative_to(ROOT)))
    return 1 if m.problems else 0


if __name__ == "__main__":
    sys.exit(main())
