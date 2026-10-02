#!/usr/bin/env python
"""The Seaward Drift: a mine tunnel from the foothill plateau to a built isle in the northern sea, with a strip mine off
it, from data/sea_drift.json (the owner, 2026-10-02: "make another mine tunnel with a strip mine attached to it near
1455 113 1795, it would be cool if it spit out near the beach around 330 70 1584 ... make a small island with some cool
water spawns around it").

Everything is decided from the data file, the canonical heightmap (tools/ground.py, rounded; never a world) and the sea
level in data/world.json. One voxel model over the whole run:

  the isle      Driftmouth Isle, raised out of y26 seabed with tools/islet.py's island_top (Relic Island's shape at this
                radius, crown and seed) and a talus skirt below its waterline; a shingle beach (gravel: sand is a spawn
                condition), dirt and grass above; a pad levelled for the headhouse; four sea stacks on the diagonals
  the drift     three straight legs from a box-cut on the plateau to the isle's stairwell, 5 wide and 5 high. Its floor
                is a PROFILE the tool computes: an open cut falling one in `incline_run` until the cover is reached
                (the portal), then the even grade from the portal to the stairwell's foot, pushed down wherever the
                cover needs it (never steeper than one in `max_run`). Every fall is one block, taken on a stair (and an
                ascending powered rail in the middle column), never within `quiet_cells` of a corner, the junction or
                the end
  the cover     solid blocks between any cell this build opens and any water, Chebyshev: shell_r + export_tolerance +
                natural_seabed (data `cover`), derived here and checked on every opened cell against the painted water
                over the effective ground (the heightmap, with the isle's built ground laid over it)
  the strips    a 3-wide corridor north off the drift at `junction_x` and 1-wide, 2-high branches every third block both
                sides, ending in a chamber with the miners' barrel; copper, lapis and gold ore in the faces (none that is
                a spawn condition), richer toward the far end, a seam at every branch end, some hidden in the walls
  the well      the drift's end climbs to the isle's crown in a scissor stair (flights of `flight_steps`, landings at the
                ends, a one-block spine between the rows); the drift's end is lowered so the flights come out whole
  the shell     every cell within shell_r of anything opened, not opened, at or under the effective ground: rock
  fittings      stairs, powered rail, timber sets (basalt posts, copper beam), hanging lanterns, the barrels
  surface       the portal's stone-brick headwall at the cut, lantern posts at its head, the headhouse over the well
                (stone brick, spruce corners and roof, a fenced stair hole, a door west), a lantern post and a path to
                the shingle

The Habitat Blocks (data/habitat_blocks.json), the caches' advancements (data/rewards.json) and the waters' pool
(data/spawns.json) are records in those files, written by `records --write` from this model and placed by their own
packs: cobblers_habitats, cobblers_rewards, cobblers_spawns. This pack only writes the rock the blocks sit in.

  python tools/sea_drift.py report  [--source-root DIR]     the model's checks and numbers; nothing written
  python tools/sea_drift.py build   [--source-root DIR]     -> build/datapacks/cobblers_sea_drift, derived/sea_drift/plan.json
  python tools/sea_drift.py records [--write]               the habitat-block, reward and pool records (print, or
                                                            replace this build's own records in the three files)

Run order on a world: every function in build/datapacks/cobblers_sea_drift/data/cobblers/function/sea_drift/index.txt in
that order (island, clear, shell, air, fittings, surface), then cobblers_habitats (the isle's blocks sit in the island's
rock), with the rewards and spawns packs installed.

The offline audit, independent of this tool's model, is tools/sea_drift_audit.py.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
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


HANG = "minecraft:lantern[hanging=true,waterlogged=false]"
STAND = "minecraft:lantern[hanging=false,waterlogged=false]"


# ------------------------------------------------------------------ the isle (built ground)

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
    hx0, hz0, hx1, hz1 = isl["headhouse"]["box"]
    for x in range(hx0 - 2, hx1 + 3):
        for z in range(hz0 - 2, hz1 + 3):
            if (x, z) not in cols or cols[(x, z)][1] != "core":
                raise DriftError("the headhouse pad (%d, %d) is not on the isle's core" % (x, z))
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


# ------------------------------------------------------------------ the path and its profile

def path_cells(vertices):
    """[(x, z, (dx, dz))] one per column along the route, and the indices of the corner cells."""
    cells, corners = [], []
    for k, ((x0, z0), (x1, z1)) in enumerate(zip(vertices, vertices[1:])):
        if x0 != x1 and z0 != z1:
            raise DriftError("route leg %d is not straight along x or z" % k)
        n = max(abs(x1 - x0), abs(z1 - z0))
        d = ((x1 > x0) - (x1 < x0), (z1 > z0) - (z1 < z0))
        if k:
            corners.append(len(cells))
        for i in range(n):
            cells.append((x0 + d[0] * i, z0 + d[1] * i, d))
    x1, z1 = vertices[-1]
    cells.append((x1, z1, cells[-1][2]))
    return cells, corners


class Model:
    def __init__(self, spec, g):
        self.spec, self.g = spec, g
        self.sea = int(T.sea_level(g.world))
        self.C = cover_blocks(spec)
        self.r, self.H, self.SR = spec["tube"]["r"], spec["tube"]["height"], spec["shell_r"]
        self.isle = isle_columns(spec, g, self.sea)
        vs = spec["route"]["vertices"]
        sm = spec["strip_mine"]
        isl = spec["island"]
        hx0, hz0, hx1, hz1 = isl["headhouse"]["box"]
        half = isl["radius"] + isl["skirt"] + 2
        xs = [v[0] for v in vs] + [isl["centre"]["x"] - half, isl["centre"]["x"] + half, hx0, hx1,
                                   sm["junction_x"] - sm["branch_length"] - 3, sm["junction_x"] + sm["branch_length"] + 3]
        zs = [v[1] for v in vs] + [isl["centre"]["z"] - half, isl["centre"]["z"] + half, hz0, hz1,
                                   sm["corridor_to_z"] - 2 * sm["chamber"]["r"] - 2]
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


def caps(m, cells):
    """The highest feet each path cell may have: its whole cross-section and C round it under the effective ground by
    C blocks of cover over the drift's roof."""
    reach = m.r + m.C
    out = []
    for x, z, _d in cells:
        w = m.geff[x - reach - m.X0:x + reach + 1 - m.X0, z - reach - m.Z0:z + reach + 1 - m.Z0]
        out.append(int(w.min()) - m.C - (m.H - 1))
    return out


def quiet_zones(m, cells, corners):
    q = m.spec["grade"]["quiet_cells"]
    jx = m.spec["strip_mine"]["junction_x"]
    sj = next(i for i, (x, z, _d) in enumerate(cells) if x == jx and z == m.spec["route"]["vertices"][0][1])
    zones = [(c - q, c + q) for c in corners] + [(sj - q, sj + q), (len(cells) - 1 - q, len(cells) - 1)]
    return zones, sj


def profile(m, cells, corners, end_feet=None):
    """Feet per path cell: the open cut, then min(the even grade, the cover's lookahead envelope), monotone, quiet
    zones flat. Returns (feet list, portal index, junction index, the lookahead's end)."""
    gr = m.spec["grade"]
    cap = caps(m, cells)
    L = len(cells)
    x0, z0, _ = cells[0]
    feet0 = m.G(x0, z0) + 1
    inc = [feet0 - s // gr["incline_run"] for s in range(L)]
    s_p = next((s for s in range(L) if inc[s] <= cap[s]), None)
    if s_p is None:
        raise DriftError("the open cut never reaches cover")
    U = [0.0] * L
    U[L - 1] = float(cap[L - 1])
    for s in range(L - 2, -1, -1):
        U[s] = min(float(cap[s]), U[s + 1] + 1.0 / gr["max_run"])
    end = int(math.floor(U[L - 1])) if end_feet is None else end_feet
    if end > U[L - 1]:
        raise DriftError("the drift's end feet %d is over its cap %.1f" % (end, U[L - 1]))
    P = [0] * L
    for s in range(L):
        if s < s_p:
            P[s] = inc[s]
            continue
        lin = inc[s_p] + 0.999 + (end - inc[s_p]) * (s - s_p) / float(L - 1 - s_p)   # floored: a step only once a whole block is lost
        v = int(math.floor(min(U[s], lin) + 1e-9))
        P[s] = v if s == s_p else min(v, P[s - 1])
    zones, sj = quiet_zones(m, cells, corners)
    for a, b in zones:
        for s in range(a, b + 1):
            if 0 < s < L and P[s] < P[s - 1]:
                if s < s_p:
                    raise DriftError("a quiet zone (%d..%d) falls in the open cut" % (a, b))
                lo = P[s]
                for t in range(a - 1, s):
                    P[t] = min(P[t], lo)
    P[L - 1 - gr["quiet_cells"]:] = [P[L - 1]] * (gr["quiet_cells"] + 1)
    for s in range(1, L):
        if P[s] > P[s - 1] or P[s - 1] - P[s] > 1:
            raise DriftError("profile breaks at cell %d (%d -> %d)" % (s, P[s - 1], P[s]))
        if s >= s_p and P[s] > cap[s]:
            raise DriftError("cell %d (%d, %d) feet %d over its cap %d" % (s, cells[s][0], cells[s][1], P[s], cap[s]))
    for a, b in zones:
        for s in range(max(a, 1), b + 1):
            if s < L and P[s] < P[s - 1]:
                raise DriftError("a stair at cell %d is inside a quiet zone (%d..%d)" % (s, a, b))
    return P, s_p, sj, cap


# ------------------------------------------------------------------ the openings

def drift(m):
    spec = m.spec
    cells, corners = path_cells(spec["route"]["vertices"])
    sw = spec["island"]["stairwell"]
    K = sw["flight_steps"]
    F_top = spec["island"]["pad_y"] + 1
    P0, _sp, _sj, _cap = profile(m, cells, corners)
    n = int(math.ceil((F_top - P0[-1]) / float(K)))
    end = F_top - K * n
    P, s_p, sj, cap = profile(m, cells, corners, end_feet=end)
    m.cells, m.corners, m.P, m.s_p, m.sj, m.cap, m.flights = cells, corners, P, s_p, sj, cap, n
    r, H = m.r, m.H
    square = set(corners) | {len(cells) - 1}
    for s, (x, z, d) in enumerate(cells):
        # a cell opens the line across the drift, so a column's floor is its own cell's feet and a stair is never
        # undercut by the next cell's; a corner (flat by the quiet zone) and the end open the whole square
        if s in square:
            xa, xb, za, zb = x - r, x + r, z - r, z + r
        elif d[1] == 0:
            xa, xb, za, zb = x, x, z - r, z + r
        else:
            xa, xb, za, zb = x - r, x + r, z, z
        top = P[s] + H - 1
        if s < s_p:
            top = max(top, max(m.G(a, b) for a in range(xa, xb + 1) for b in range(za, zb + 1)))
            for a in range(-r - CLEAR_MARGIN, r + CLEAR_MARGIN + 1):
                for b in range(-r - CLEAR_MARGIN, r + CLEAR_MARGIN + 1):
                    m.open_cut.add((x + a, z + b))
        m.carve(xa, xb, za, zb, P[s], top)
    m.steps = [s for s in range(1, len(cells)) if P[s] < P[s - 1]]


def strips(m):
    sm = m.spec["strip_mine"]
    jx = sm["junction_x"]
    zr = m.spec["route"]["vertices"][0][1]
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


def well(m):
    """The scissor stair from the drift's end feet to the pad: [(kind, data)] for the fittings."""
    isl = m.spec["island"]
    sw = isl["stairwell"]
    K, hr = sw["flight_steps"], sw["headroom"]
    ex0, ex1 = sw["east_landing_x"]
    wx0, wx1 = sw["west_landing_x"]
    za, zb = sw["rows_z"]
    if ex0 - K - 1 != wx1:
        raise DriftError("the flights (%d steps) do not span the landings %s and %s" % (K, sw["west_landing_x"], sw["east_landing_x"]))
    if zb - za != 4 or sw["spine_z"] != za + 2:
        raise DriftError("the stairwell rows must be 4 apart with the spine between them")
    f = m.P[-1]
    zl0, zl1 = za - 1, zb + 1
    m.landings, m.flight_steps = [], []
    m.carve(ex0, ex1, zl0, zl1, f, f + hr - 1)
    m.landings.append(("east", f))
    for i in range(m.flights):
        start = f + K * i
        west = i % 2 == 0
        row = za if west else zb
        for j in range(1, K + 1):
            x = ex0 - j if west else wx1 + j
            y = start + j - 1
            m.carve(x, x, row - 1, row + 1, y, y + hr)
            m.flight_steps.append((x, y, row, "west" if west else "east", i, j))
        feet = start + K
        if west:
            m.carve(wx0, wx1, zl0, zl1, feet, feet + hr - 1)
            m.landings.append(("west", feet))
        else:
            m.carve(ex0, ex1, zl0, zl1, feet, feet + hr - 1)
            m.landings.append(("east", feet))
    if m.landings[-1][1] != isl["pad_y"] + 1:
        raise DriftError("the well tops out at feet %d, not the pad's %d" % (m.landings[-1][1], isl["pad_y"] + 1))


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
    # the air: every opened cell at or under the effective ground (over it the open cut and the hall are air already)
    ug = m.env & under_ground(m)
    for i, k in np.argwhere(ug.any(axis=2)):
        x, z = int(i + m.X0), int(k + m.Z0)
        js = np.nonzero(ug[i, k])[0]
        out["air"] += [RM.cmd(x, a, c, z, AIR) for a, c, _b in RM.column_runs(x, z, [(int(j + m.Y0), AIR) for j in js])]
    fittings(m, sh)
    surface(m)
    delicate = ("lantern", "rail", "fence", "barrel")
    fits = sorted(m.fit.items(), key=lambda kv: (any(d in kv[1] for d in delicate), kv[0][1], kv[0][0], kv[0][2]))
    out["fittings"] = ["setblock %d %d %d %s" % (x, y, z, b) for (x, y, z), b in fits]
    solid = [(p, b) for p, b in m.surf.items() if not any(d in b for d in delicate)]
    soft = [(p, b) for p, b in m.surf.items() if any(d in b for d in delicate)]
    scols = {}
    for (x, y, z), b in solid:
        scols.setdefault((x, z), []).append((y, b))
    for (x, z) in sorted(scols):
        out["surface"] += [RM.cmd(x, a, c, z, b) for a, c, b in RM.column_runs(x, z, scols[(x, z)])]
    out["surface"] += ["setblock %d %d %d %s" % (x, y, z, b) for (x, y, z), b in sorted(soft, key=lambda kv: (kv[0][1], kv[0]))]
    return out


def fittings(m, sh):
    spec = m.spec
    pal = spec["palette"]
    r, H = m.r, m.H
    zones, _sj = quiet_zones(m, m.cells, m.corners)

    def quiet(s):
        return any(a <= s <= b for a, b in zones)

    def stair_block(y):
        return pal["stair_upper"] if y >= pal["rock_split_y"] else pal["stair_lower"]

    steps = set(m.steps)
    m.rails = 0
    for s, (x, z, d) in enumerate(m.cells):
        px, pz = -d[1], d[0]
        y = m.P[s]
        if s in steps:
            back = NAME[(-d[0], -d[1])]
            for o in range(-r, r + 1):
                if o == 0 and s >= m.s_p and not quiet(s):
                    continue
                m.fit[(x + px * o, y, z + pz * o)] = stair(stair_block(y), back)
        if s >= m.s_p and not quiet(s):
            if s in steps:
                shape = "ascending_" + NAME[(-d[0], -d[1])]
            else:
                shape = "east_west" if d[1] == 0 else "north_south"
            m.fit[(x, y, z)] = "%s[shape=%s,powered=false,waterlogged=false]" % (pal["rail"], shape)
            m.rails += 1
        n = s - m.s_p
        if s >= m.s_p and n % spec["lights"]["every"] == spec["lights"]["every"] // 2:
            m.fit[(x, y + H - 1, z)] = HANG
        if (s >= m.s_p + 2 and n % spec["lights"]["frames_every"] == 0 and not quiet(s)
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
    # the strips: corridor lanterns, one at every branch end, one in the chamber; the barrel
    sm = spec["strip_mine"]
    jx, f = sm["junction_x"], m.strip_feet
    zr = spec["route"]["vertices"][0][1]
    for z in range(zr - r - 1, sm["corridor_to_z"] - 1, -spec["lights"]["every"]):
        m.fit[(jx, f + sm["drift_height"] - 1, z)] = HANG
    for br in m.branches:
        m.fit[(br["end_x"], f + sm["branch_height"] - 1, br["z"])] = HANG
    cx, cz = m.chamber
    cr = sm["chamber"]["r"]
    m.fit[(cx, f + sm["chamber"]["height"] - 1, cz)] = HANG
    m.strip_barrel = (cx, f, cz - cr)
    m.fit[m.strip_barrel] = "minecraft:barrel[facing=south,open=false]"
    # the well: stairs on every step, a lantern on every landing and halfway up every flight
    isl = spec["island"]
    sw = isl["stairwell"]
    for (x, y, row, facing, i, j) in m.flight_steps:
        for zz in (row - 1, row, row + 1):
            m.fit[(x, y, zz)] = stair(stair_block(y), facing)
        if (j == (sw["flight_steps"] + 1) // 2 and y + sw["headroom"] + 1 <= isl["pad_y"]
                and m.opened(x, y + sw["headroom"], row) and not m.opened(x, y + sw["headroom"] + 1, row)):
            m.fit[(x, y + sw["headroom"], row)] = HANG
    zc = sw["spine_z"]
    for side, feet in m.landings[:-1]:                 # the top landing is the hall's floor; the hall has its own
        lx = sum(sw["east_landing_x" if side == "east" else "west_landing_x"]) // 2
        ytop = feet + sw["headroom"] - 1
        if not m.opened(lx, ytop + 1, zc):
            m.fit[(lx, ytop, zc)] = HANG


def surface(m):
    spec, pal = m.spec, m.spec["palette"]
    isl = spec["island"]
    pad = isl["pad_y"]
    x0, z0, x1, z1 = isl["headhouse"]["box"]
    wh = isl["headhouse"]["wall_height"]
    sw = isl["stairwell"]
    zc = sw["spine_z"]
    # the hall: walls, roof, an open door west, air inside, a floor where the stair hole is not
    hole = set()
    for x in range(x0 + 1, x1):
        for z in range(z0 + 1, z1):
            if m.opened(x, pad, z):
                hole.add((x, z))
    top_side = m.landings[-1][0]
    landing_x = sw["east_landing_x" if top_side == "east" else "west_landing_x"]
    landing = {(x, z) for x in range(landing_x[0], landing_x[1] + 1) for z in range(sw["rows_z"][0] - 1, sw["rows_z"][1] + 2)}
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            wall = x in (x0, x1) or z in (z0, z1)
            corner = x in (x0, x1) and z in (z0, z1)
            for y in range(pad + 1, pad + wh + 1):
                if corner:
                    m.surf[(x, y, z)] = pal["corner"] + "[axis=y]"
                elif wall:
                    door = x == x0 and abs(z - zc) <= 1 and y <= pad + 3
                    m.surf[(x, y, z)] = AIR if door else pick(pal["wall"], spec["seed"], x, y, z, 51)
                else:
                    m.surf[(x, y, z)] = AIR
            m.surf[(x, pad + wh + 1, z)] = pal["roof"]
            if not wall and (x, z) not in hole:
                m.surf[(x, pad, z)] = pal["floor"]
    for (x, z) in hole:
        for (a, b) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + a, z + b)
            if q in hole or q in landing or not (x0 < q[0] < x1 and z0 < q[1] < z1):
                continue
            m.surf[(q[0], pad + 1, q[1])] = pal["fence"]
    m.hole = hole
    for lx in (x0 + 4, x1 - 4):
        m.surf[(lx, pad + wh, zc)] = HANG
    m.isle_barrel = (x0 + 1, pad + 1, z0 + 1)
    m.surf[m.isle_barrel] = "minecraft:barrel[facing=east,open=false]"
    # outside: a lantern post either side of the door, and a path west to the shingle
    for z in (zc - 2, zc + 2):
        x = x0 - 2
        g = m.G(x, z)
        m.surf[(x, g + 1, z)] = pal["fence"]
        m.surf[(x, g + 2, z)] = pal["fence"]
        m.surf[(x, g + 3, z)] = STAND
    m.path = []
    x = x0 - 1
    while True:
        tops = [m.isle.get((x, z)) for z in (zc - 1, zc, zc + 1)]
        if any(t is None or t[0] <= m.sea + 2 for t in tops):
            break
        for z in (zc - 1, zc, zc + 1):
            t = m.isle[(x, z)][0]
            if (x, t + 1, z) not in m.surf:
                m.surf[(x, t, z)] = pal["path"]
                m.path.append((x, t, z))
        x -= 1
    # the portal: a stone-brick headwall over the drift's opening where the cut goes under a roof, and lantern posts
    # at the cut's head
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
    x, z, d = m.cells[0]
    px, pz = -d[1], d[0]
    for side in (-1, 1):
        cx, cz = x + px * (m.r + 2) * side, z + pz * (m.r + 2) * side
        g = int(m.base[cx - m.X0, cz - m.Z0])
        m.surf[(cx, g + 1, cz)] = pal["fence"]
        m.surf[(cx, g + 2, cz)] = pal["fence"]
        m.surf[(cx, g + 3, cz)] = STAND


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
    # under the sea: the drift's own least cover over a wet column, and where
    m.sea_cells = [s for s, (x, z, _d) in enumerate(m.cells) if m.wl[x - m.X0, z - m.Z0] >= 0]
    # habitat blocks sit in the isle's rock with rock on all six sides and nothing opened near
    hab = habitat_positions(m)
    for (x, y, z, hid, _pl) in hab:
        for a, b, c in ((0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            if (x + a, y + b, z + c) not in m.isle_cells:
                p.append("habitat %s: (%d, %d, %d) is not inside the isle's rock" % (hid, x + a, y + b, z + c))
                break
        if dilate_hit(m, x, y, z, m.SR + 1):
            p.append("habitat %s: within reach of the drift's openings" % hid)
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
    well(m)
    m.lines = blocks(m)
    checks(m)
    return m


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
    return {
        "cover_required": m.C,
        "cover_min_measured": m.min_cover,
        "route_cells": L, "portal_cell": m.s_p, "portal": list(m.portal),
        "mouth_feet": m.P[0], "end_feet": m.P[-1], "stairs": len(m.steps), "rails": m.rails,
        "sea_cells": len(m.sea_cells), "deepest_feet_under_sea": min(sea_feet) if sea_feet else None,
        "first_sea_cell": list(m.cells[m.sea_cells[0]][:2]) if m.sea_cells else None,
        "flights": m.flights, "landings": m.landings,
        "strip_feet": m.strip_feet, "branches": len(m.branches),
        "branch_exposed_ores": [b["exposed"] for b in m.branches],
        "ores": ores,
        "isle": {"columns": len(m.isle), "core_columns": core, "core_above_water": above,
                 "crown_y": max(t for (t, k, _b) in m.isle.values() if k in ("core", "pad")),
                 "centre_ground_y": m.isle[(isl["centre"]["x"], isl["centre"]["z"])][0],
                 "seabed_under_centre": m.isle[(isl["centre"]["x"], isl["centre"]["z"])][2],
                 "blocks": len(m.isle_cells)},
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
    x, y, z = m.portal
    out.append((x, y + m.H, z, "minecraft:stone_bricks", "the portal's headwall over the drift's opening"))
    s = next(s for s in m.steps if s > m.s_p + 10)
    cx, cz, d = m.cells[s]
    px, pz = -d[1], d[0]
    out.append((cx + px, m.P[s], cz + pz, m.spec["palette"]["stair_upper"] if m.P[s] >= m.spec["palette"]["rock_split_y"]
                else m.spec["palette"]["stair_lower"], "a stair on the drift's floor"))
    if m.sea_cells:
        s = min(m.sea_cells, key=lambda t: m.G(m.cells[t][0], m.cells[t][1]) - m.P[t])
        cx, cz, _d = m.cells[s]
        out.append((cx, m.P[s] + m.H - 1, cz, "minecraft:air", "the drift's roof row under the sea's least cover"))
        out.append((cx, m.P[s] + m.H, cz, "a rock block (stone, deepslate, tuff, andesite or cobbled deepslate)",
                    "the rock over it; the sea floor at y%d" % m.G(cx, cz)))
    out.append(tuple(m.strip_barrel) + ("minecraft:barrel", "the strips' cache"))
    out.append(tuple(m.isle_barrel) + ("minecraft:barrel", "the isle's cache in the headhouse"))
    isl = m.spec["island"]
    x0, z0, _x1, _z1 = isl["headhouse"]["box"]
    out.append((x0, isl["pad_y"] + 1, isl["stairwell"]["spine_z"], "minecraft:air", "the headhouse's west door"))
    for h in habitat_positions(m)[:2]:
        out.append((h[0], h[1], h[2], "cobblemon:habitat_block (after cobblers_habitats)", h[3]))
    return [{"x": a, "y": b, "z": c, "expect": e, "what": w} for a, b, c, e, w in out]


def write(m):
    fn, order = RM.write_blocks(OUT, m.lines, PASSES, "tools/sea_drift.py",
                                "Cobblers: the Seaward Drift, its strip mine and Driftmouth Isle (tools/sea_drift.py)")
    return order


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
            place = "Driftmouth Isle: in the headhouse over the drift's stairwell, its north-west corner"
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
    # NEVER this pool's own entries: on 2026-10-02 the encounter rebuild removed Binacle, Clauncher and Dragonair from
    # every other table, and this loop went on finding the positions it had itself written - reading its own output as
    # input. The other tables come first; a species no other table carries takes its position from Cobblemon's own
    # spawn files (tools/position_types.py, the source tools/build_encounters.py uses), and says so.
    for e in spawns["entries"]:
        if e.get("scope") != w["pool"]:
            see(e)
    upstream = None
    for ro in w["roster"]:
        for sp in [ro["pokemon"]] + [e["pokemon"] for e in ro["evolutions"]]:
            if sp not in pos:
                if upstream is None:
                    import position_types
                    jar = position_types.default_jar()
                    if jar is None:
                        raise DriftError("%s is in no other table of data/spawns.json, and COBBLERS_SERVER_ROOT is unset, "
                                         "so Cobblemon's own spawn files cannot be read for it" % sp)
                    upstream = position_types.upstream_positions(jar)
                import position_types
                pos[sp] = position_types.choose(sp, upstream)[0]
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
    p.add_argument("cmd", choices=("report", "build", "records"))
    p.add_argument("--source-root", default=None)
    p.add_argument("--write", action="store_true", help="records: replace this build's records in the three files")
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
