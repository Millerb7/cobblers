#!/usr/bin/env python
"""The Windward Deep's city, and Hoopa's relic area as seen from outside.

The pit (tools/rift_deep.py) is five terraced rings stepping 17 down to a floor at y0, empty. This stands the city
on it, as docs/world-building/DEEP_CITY.md designs it and data/deep_city.json lays it out: buildings for the
families against every riser, their roofs flush with the street above; the Haven Compact's HQ down the west risers
with its tower over the lip; a stair tower round every lift bank and at the Sink Gate; the Core spire and its
bridges; the lighting layers; the Centre and Mart; and the relic area's surface beside the Deep, CAPPED: the sealed
entrance, the lookout and the Compact's dig. The shrine, ring, arches and standing stones went underground on
2026-10-02 (tools/relic_underground.py, the owner: "the relic site underground"), and the cordon was replaced by that
tool's zone check; the old surface build is kept verbatim in tools/relic_surface_superseded.py for R9RU's undo.

It builds shells. The rooms the story needs are left empty and labelled (data/deep_city.json rooms); Hoopa's
cradle, the passage to it, the HQ's basement and its shaft are reserved volumes nothing is written into.

Ground comes from the pit's ring model (rift_deep.model(), the owner's traced region and the canonical heightmap)
and, for the relic area, its traced region and tools/ground.py. Never from a world; `verify` reads a world only to
check what was built.

    python tools/deep_city.py build  --source-root <root>
    python tools/deep_city.py rooms                        # the resolved rooms, from the last build's plan
    python tools/deep_city.py verify --world <stopped world copy>

The offline audit of the output against independent plan data is tools/deep_city_audit.py.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from collections import deque
from pathlib import Path

import numpy as np

import function_limits as FL
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "deep_city.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_deep_city"
PLAN = ROOT / "derived" / "deep_city" / "plan.json"
TILE = 64
PART = 3000
FOLDER = "deep_city"

WORLD_READS = {"verify", "main"}

D4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
FACE = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}
DIR = {v: k for k, v in FACE.items()}
CONNECTS = ("_pane", "iron_bars")


class CityError(Exception):
    pass


def hsh(a, b, c, salt=0):
    x = ((a * 73856093) ^ (b * 19349663) ^ (c * 83492791) ^ (salt * 2654435761)) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13
    x = (x * 3266489917) & 0xFFFFFFFF
    return x ^ (x >> 16)


def unit(a, b, c, salt=0):
    return hsh(a, b, c, salt) / 4294967296.0


def bearing(x, z, cx, cz):
    """Compass degrees from the pit's centre: 0 north (-z), 90 east (+x)."""
    return (math.degrees(math.atan2(x - cx, -(z - cz))) + 360.0) % 360.0


def ang_diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


# ------------------------------------------------------------------ blocks

class Palette:
    """Material keys from data/deep_city.json to block ids. A modded block falls back to its vanilla stand-in only
    when a list of the server's installed ids is given and lacks it (tools/rift_deep.py's rule)."""

    def __init__(self, spec, have=None):
        self.mat = spec["materials"]
        self.em = spec["lights"]["emitters"]
        self.have = have

    def __call__(self, key):
        if key in self.mat:
            e = self.mat[key]
        elif key in self.em:
            e = self.em[key]
        else:
            return key
        b = e["block"]
        if self.have is not None and not b.startswith("minecraft:") and b.split("[")[0] not in self.have:
            return e.get("fallback", b)
        return b

    def level(self, block):
        """Light level of a block, from data/deep_city.json lights.emitters (0 when not an emitter)."""
        base = block.split("[")[0]
        for e in self.em.values():
            if e["block"].split("[")[0] == base or e.get("fallback", "").split("[")[0] == base:
                return int(e["level"]) if not (base.endswith("_bulb") and "lit=false" in block) else 0
        return 0


def stair(block, facing):
    return "%s[facing=%s,half=bottom,shape=straight,waterlogged=false]" % (block, facing)


# ------------------------------------------------------------------ the canvas

class Canvas:
    """Every block the city writes, keyed by position; a later write replaces an earlier one. Phase 1 is structure,
    phase 2 what hangs on it (ladders, hatches, doors, panes, signs, lamps), written after every phase-1 block so a
    ladder never meets a missing wall."""

    def __init__(self):
        self.v = {}
        self.owner = {}
        self.exterior = set()

    def put(self, x, y, z, b, phase=1, owner=None, exterior=False):
        self.v[(x, y, z)] = (b, phase)
        if owner:
            self.owner[(x, y, z)] = owner
        if exterior:
            self.exterior.add((x, y, z))
        else:
            self.exterior.discard((x, y, z))

    def col(self, x, z, y0, y1, b, phase=1, owner=None):
        for y in range(y0, y1 + 1):
            self.put(x, y, z, b, phase, owner)

    def get(self, x, y, z):
        e = self.v.get((x, y, z))
        return e[0] if e else None

    def drop(self, x, y, z):
        self.v.pop((x, y, z), None)


def connect_panes(cv):
    """Panes and bars take their connections from their neighbours on the canvas: a fill or setblock never updates
    a pane placed before its neighbour, so a railing written plainly is a row of posts."""
    out = []
    for (x, y, z), (b, ph) in list(cv.v.items()):
        base = b.split("[")[0]
        if not base.endswith(CONNECTS):
            continue
        st = {}
        for (dx, dz), name in FACE.items():
            n = cv.get(x + dx, y, z + dz)
            nb = n.split("[")[0] if n else ""
            st[name] = "true" if (nb.endswith(CONNECTS) or (n and _solid(nb))) else "false"
        out.append(((x, y, z), "%s[east=%s,north=%s,south=%s,west=%s,waterlogged=false]"
                    % (base, st["east"], st["north"], st["south"], st["west"]), ph))
    for p, b, ph in out:
        cv.v[p] = (b, ph)


def _solid(base):
    return base and base != "minecraft:air" and not base.endswith(
        ("_pane", "iron_bars", "_stairs", "_slab", "_trapdoor", "_door", "ladder", "_sign", "end_rod", "lantern", "chain",
         "_rod", "scaffolding", "_button"))


# ------------------------------------------------------------------ the model

def city_model(source_root, spec):
    import rift_deep as RD
    m = RD.model(source_root)
    X0, Z0, X1, Z1 = m["box"]
    mask, ring, inside, H = m["mask"], m["ring"], m["inside"], m["H"]
    T = np.where(mask, m["tread_y"], -9999).astype(np.int32)
    W = m["width"]
    within = inside - np.maximum(ring, 0) * W
    lifts = RD.lift_sites(m)
    cx, cz = m["centre"]
    # the tread grid tools/rift_deep.py lays (L1): kept, and counted as light
    L1 = set()
    rdspec = m["spec"]
    every = rdspec["light"]["every"]
    margin = rdspec["tread"]["rock_margin"]
    zz, xx = np.nonzero(mask & (within >= margin))
    for z, x in zip(zz.tolist(), xx.tolist()):
        wx, wz = x + X0, z + Z0
        if wx % every == 0 and wz % every == 0:
            L1.add((wx, int(T[z, x]), wz))
    return {"rd": m, "X0": X0, "Z0": Z0, "shape": mask.shape, "mask": mask, "ring": ring, "T": T, "H": H,
            "sheer": m["sheer"], "within": within, "lifts": lifts, "cx": cx, "cz": cz, "L1": L1}


def riser_field(M, depth):
    """For every pit column, the distance (4-connected, over columns at its own level) to the nearest foot of a riser,
    and the height of the street at the top of that riser: the roof a building here has to meet."""
    mask, T, H = M["mask"], M["T"], M["H"]
    nz, nx = mask.shape
    dist = np.full(mask.shape, 9999, np.int32)
    roof = np.full(mask.shape, -9999, np.int32)
    q = deque()
    zz, xx = np.nonzero(mask)
    for z, x in zip(zz.tolist(), xx.tolist()):
        t = T[z, x]
        hi = -9999
        for dx, dz in D4:
            a, b = z + dz, x + dx
            if not (0 <= a < nz and 0 <= b < nx):
                continue
            lv = T[a, b] if mask[a, b] else H[a, b]
            if lv >= t + 2:
                hi = max(hi, int(lv))
        if hi > -9999:
            dist[z, x] = 0
            roof[z, x] = hi
            q.append((z, x))
    while q:
        z, x = q.popleft()
        d = dist[z, x] + 1
        if d >= depth:
            continue
        for dx, dz in D4:
            a, b = z + dz, x + dx
            if 0 <= a < nz and 0 <= b < nx and mask[a, b] and T[a, b] == T[z, x] and dist[a, b] > d:
                dist[a, b] = d
                roof[a, b] = roof[z, x]
                q.append((a, b))
    return dist, roof


# ------------------------------------------------------------------ towers

def ring_cells():
    """The 16 cells of a 5x5 stair round a 3x3 core, from the middle of the back row, turning right."""
    cells = [(2, 0), (3, 0), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (3, 4), (2, 4), (1, 4), (0, 4), (0, 3), (0, 2),
             (0, 1), (0, 0), (1, 0)]
    return cells


RIGHT = {(0, -1): (1, 0), (1, 0): (0, 1), (0, 1): (-1, 0), (-1, 0): (0, -1)}      # back direction -> right hand


def frame(anchor, back):
    """local (i, j) -> world (x, z); j = 0 is the back row of the interior, i = 0 its left end."""
    r = RIGHT[back]
    ax, az = anchor

    def w(i, j):
        return ax + i * r[0] - j * back[0], az + i * r[1] - j * back[1]
    return w


def local_dir(back, di, dj):
    r = RIGHT[back]
    return FACE[(di * r[0] - dj * back[0], di * r[1] - dj * back[1])]


def stair_plan(R):
    """{cell: [s, ...]} steps at height s (1..R) on each ring cell, the landing cell, and the open cells over which
    the roof must stay off so the last steps have headroom."""
    cells = ring_cells()
    steps = {}
    for s in range(1, R + 1):
        steps.setdefault(cells[(s - 1) % 16], []).append(s)
    top = cells[(R - 1) % 16]
    if top[1] != 0:
        raise CityError("a rise of %d puts the landing off the back row" % R)
    opened = [cells[(s - 1) % 16] for s in (R - 2, R - 1)]
    return steps, top, opened


def climb_cells(R):
    """The ring cells whose roof must be off so the stair can be WALKED, not only stood on: the two opened cells and the
    cell of step R-3 (2026-10-03). A player stepping up from a step at height s to s+1 needs air three above s in the
    column he is leaving (feet s+1, head s+2.8 while the stair lifts him); under a roof at R, step R-3 has two (R-2,
    R-1) and the climber hits it. The descent is the same move backwards. stair_plan's `opened` is unchanged, because
    place_tower sites the lifts by it and a moved tower is a moved city."""
    cells = ring_cells()
    _steps, top, opened = stair_plan(R)
    extra = cells[(R - 4) % 16] if R >= 4 else None
    return list(opened) + ([extra] if extra is not None and extra not in opened and extra != top else [])


def place_tower(M, g, gu, L=None, U=None, claimed=None, want=None, max_try=None):
    """Site a 7x7 stair tower: the lower lift L inside it where the steps leave its rider headroom and the roof
    covers it, the upper lift U inside it too if it can be, the back against the riser, a door onto the street."""
    mask, T = M["mask"], M["T"]
    X0, Z0 = M["X0"], M["Z0"]
    R = gu - g
    steps, top, opened = stair_plan(R)
    cells = ring_cells()
    best = None

    def colT(x, z):
        a, b = z - Z0, x - X0
        if 0 <= a < mask.shape[0] and 0 <= b < mask.shape[1] and mask[a, b]:
            return int(T[a, b])
        return None

    def ok_cell(c):
        """A ring cell a lift can stand in: its rider has two blocks of headroom under the steps, and the roof above
        it is closed (not the open well, not the landing), and it is not the light core."""
        if 1 <= c[0] <= 3 and 1 <= c[1] <= 3:
            return False
        return c not in opened and c != top and min(steps.get(c, [R + 99])) >= 3

    for back in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        anchors = []
        if L is not None:
            for c in cells:
                if not ok_cell(c):
                    continue
                i, j = c
                r = RIGHT[back]
                ax = L[0] - i * r[0] + j * back[0]
                az = L[2] - i * r[1] + j * back[1]
                anchors.append((ax, az))
        else:
            anchors = want(back)
        for anchor in anchors:
            w = frame(anchor, back)
            foot = [(i, j) for i in range(-1, 6) for j in range(-1, 6)]
            lv = {}
            bad = False
            for i, j in foot:
                x, z = w(i, j)
                t = colT(x, z)
                if t not in (g, gu) or (claimed is not None and (x, z) in claimed):
                    bad = True
                    break
                lv[(i, j)] = t
            if bad:
                continue
            u_cell, u_wall = None, None
            if U is not None:
                for i, j in foot:
                    if w(i, j) == (U[0], U[2]):
                        if 0 <= i <= 4 and 0 <= j <= 4:
                            u_cell = (i, j)
                        else:
                            u_wall = (i, j)
                if u_cell is not None and not ok_cell(u_cell):
                    continue
                if u_wall is not None:
                    i, j = u_wall
                    inner = (min(4, max(0, i)), min(4, max(0, j)))
                    corner = i in (-1, 5) and j in (-1, 5)
                    if corner or not ok_cell(inner) or lv[u_wall] != gu:
                        continue
            # the back faces the riser: the back half in the upper ring, the front half in the lower
            score = sum(1 for (i, j), t in lv.items() if (t == gu) == (j <= 1)) - sum(1 for (i, j), t in lv.items() if t == gu and j >= 3) * 3
            # the landing's way out: over the wall behind it, onto the street above (the upper ring or a roof)
            li, lj = top
            bx, bz = w(li, -2)
            beyond = colT(bx, bz)
            if beyond is None and M.get("outside_ok"):
                beyond = gu
            if beyond not in (gu,) and lv[(li, -1)] != gu:
                continue
            # a door onto the lower street
            door = None
            for di, dj, inner in ([(2, 5, (2, 4)), (1, 5, (1, 4)), (3, 5, (3, 4)), (-1, 3, (0, 3)), (5, 3, (4, 3)),
                                   (-1, 4, (0, 4)), (5, 4, (4, 4)), (-1, 2, (0, 2)), (5, 2, (4, 2))]):
                # the wall is on the lower street and the cell inside has headroom at the floor
                if lv[(di, dj)] != g or min(steps.get(inner, [99])) < 3:
                    continue
                ox, oz = w(di + (1 if di == 5 else -1 if di == -1 else 0), dj + (1 if dj == 5 else 0))
                if colT(ox, oz) != g or (claimed is not None and (ox, oz) in claimed):
                    continue
                door = (di, dj)
                break
            if door is None:
                continue
            key = (U is None or u_cell is not None or u_wall is not None, score)
            if best is None or key > best[0]:
                best = (key, dict(anchor=anchor, back=back, u_cell=u_cell, u_wall=u_wall, door=door, levels=lv,
                                  R=R, g=g, gu=gu, top=top, opened=opened, steps=steps))
    return best[1] if best else None


def build_tower(cv, P, M, t, name, palette, sign=None, pylon=4, walls_to=None, exits=(), roof=True, owner="tower"):
    w = frame(t["anchor"], t["back"])
    g, gu, R = t["g"], t["gu"], t["R"]
    steps, top = t["steps"], t["top"]
    # the roof comes off over climb_cells, not only stair_plan's `opened` (a climber needs three of head room on the
    # step he leaves); where a lift stands under that roof its landing wins and the cell stays roofed, and is reported
    opened = list(t["opened"])
    lift_cols = {(p[0], p[2]) for p in (t.get("L"), t.get("U")) if p}
    if roof and opened:
        wf = frame(t["anchor"], t["back"])
        for c in climb_cells(t["R"]):
            if c in opened:
                continue
            if wf(*c) in lift_cols:
                t["headroom_blocked_by_lift"] = list(wf(*c))
                continue
            opened.append(c)
    t["climb_opened"] = [list(c) for c in opened]
    wall_b, roof_b, win_b = P(palette["wall"]), P("tread"), P("glass_conduit")
    stair_b = "minecraft:polished_deepslate_stairs"
    lifts = set()
    if t.get("L"):
        lifts.add((t["L"][0], t["L"][1], t["L"][2]))
    if t.get("U"):
        lifts.add((t["U"][0], t["U"][1], t["U"][2]))
    cells = ring_cells()
    top_y = walls_to if walls_to is not None else gu
    for i in range(-1, 6):
        for j in range(-1, 6):
            x, z = w(i, j)
            t_col = t["levels"][(i, j)]
            upper = t_col == gu and gu != g
            hi = (gu - 1) if upper else top_y
            is_wall = i in (-1, 5) or j in (-1, 5)
            is_core = 1 <= i <= 3 and 1 <= j <= 3
            if is_wall:
                for y in range(g + 1, hi + 1):
                    b = wall_b
                    if j == 5 and 1 <= i <= 3 and g + 3 <= y <= top_y - 2:
                        b = win_b
                    if y == top_y and not upper and roof:
                        b = roof_b
                    cv.put(x, y, z, b, owner=owner)
                continue
            if is_core:
                for y in range(g + 1, top_y + pylon + 1):
                    b = P("sea_lantern") if (i, j) == (2, 2) else (P("glass_dark") if i != 2 and j != 2 else P("glass_conduit"))
                    cv.put(x, y, z, b, owner=owner, exterior=y > top_y)
                if (i, j) == (2, 2) and pylon > 0:
                    cv.put(x, top_y + pylon + 1, z, "minecraft:end_rod[facing=up]", 2, owner=owner, exterior=True)
                continue
            # a ring cell of the stair
            if upper:
                for y in range(g + 1, gu):
                    cv.put(x, y, z, "minecraft:air", owner=owner)
            for s in steps.get((i, j), []):
                k = cells.index((i, j))
                pi, pj = cells[(k - 1) % 16]
                face = local_dir(t["back"], i - pi, j - pj)
                cv.put(x, g + s, z, stair(stair_b, face), owner=owner)
            if roof and not upper:
                if (i, j) in opened:
                    pass
                elif (i, j) == top:
                    pass                                    # the last step is the landing, at roof height
                else:
                    cv.put(x, top_y, z, roof_b, owner=owner)
            elif roof and upper and (i, j) in opened:
                cv.put(x, gu, z, "minecraft:air", owner=owner)
    # the door
    di, dj = t["door"]
    x, z = w(di, dj)
    for y in (g + 1, g + 2):
        cv.put(x, y, z, "minecraft:air", owner=owner)
    if t.get("u_wall"):
        x, z = w(*t["u_wall"])
        for y in (g + 1, g + 2):
            cv.put(x, y, z, "minecraft:air", owner=owner)
    # the exits from the spire's stair onto its decks: the wall cell on the outward side of the step's own ring cell.
    # A ring cell lies on the 5x5 perimeter, so at least one of the four sides is the wall; a corner cell has two and
    # the i side is taken.
    for s_ in exits:
        ci, cj = cells[(s_ - 1) % 16]
        x, z = w(*_outward_wall(ci, cj, "%s: the exit at step %d" % (name, s_)))
        for y in (g + s_ + 1, g + s_ + 2):
            cv.put(x, y, z, "minecraft:air", owner=owner)
    # guard rail round the open well, clear of the landing and the wall behind it
    if roof:
        guard = set()
        for oi, oj in opened:
            for di_, dj_ in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c = (oi + di_, oj + dj_)
                if c in opened or c == top or c == (top[0], top[1] - 1):
                    continue
                if 1 <= c[0] <= 3 and 1 <= c[1] <= 3:
                    continue
                if -1 <= c[0] <= 5 and -1 <= c[1] <= 5:
                    guard.add(c)
        lift_xz = {(lx, lz) for lx, _ly, lz in lifts}
        for c in guard:
            x, z = w(*c)
            if (x, z) in lift_xz:
                continue
            ty = gu if t["levels"][c] == gu else top_y
            cv.put(x, ty + 1, z, P("rail"), 2, owner=owner, exterior=True)
    # a sign by the door
    if sign:
        x, z = w(di, dj)
        ox, oz = w(di + (1 if di == 5 else -1 if di == -1 else 0), dj + (1 if dj == 5 else 0))
        face = FACE[(ox - x, oz - z)]
        lines = ['{"text":"%s"}' % s.replace('"', "'") for s in (sign + ["", "", "", ""])[:4]]
        cv.put(ox, g + 3, oz, "minecraft:warped_wall_sign[facing=%s,waterlogged=false]{front_text:{messages:['%s','%s','%s','%s']}}"
               % ((face,) + tuple(lines)), 2, owner=owner)
    # never a lift, never the air its rider stands in
    for lx, ly, lz in lifts:
        cv.drop(lx, ly, lz)
        for y in (ly + 1, ly + 2):
            if cv.get(lx, y, lz) not in (None, "minecraft:air"):
                raise CityError("%s would write %s over the lift at %s" % (name, cv.get(lx, y, lz), (lx, ly, lz)))
    cols = {w(i, j) for i in range(-1, 6) for j in range(-1, 6)}
    return cols


# ------------------------------------------------------------------ buildings

class Lot:
    def __init__(self, lid, cols, level, district):
        self.id, self.cols, self.level, self.district = lid, cols, level, district
        self.room = None
        self.sealed = False
        self.kind = "home"
        self.door = None
        self.ladder = None


def build_lot(cv, P, spec, lot, roof_of, lot_of, M, rooms_out):
    d = spec["districts"][lot.district]
    bspec = spec["buildings"]
    storey = bspec["storey"]
    g = lot.level
    cols = lot.cols
    X0, Z0 = M["X0"], M["Z0"]
    h = hsh(lot.cols_min[0], lot.cols_min[1], g, 11)
    wall = P(d.get("wall_alt") if d.get("wall_alt") and h % 3 == 0 else d["wall"])
    trim, win = P(d["trim"]), P(d["window"])
    floor_b = P(d["floor"])
    roof_b, edge_b = P(d["roof"]), P("tread_edge")
    pier_every = bspec["pier_every"][h % len(bspec["pier_every"])]
    inner_light = P(d["interior_light"])
    roof_light = P(d["floor_light"])
    band = (P("violet"), P("glass_band"))
    tall = h % 2 == 0
    boundary, facade = set(), set()
    for (x, z) in cols:
        for dx, dz in D4:
            n = (x + dx, z + dz)
            if n not in cols:
                boundary.add((x, z))
                a, b = n[1] - Z0, n[0] - X0
                if (0 <= a < M["shape"][0] and 0 <= b < M["shape"][1] and M["mask"][a, b] and M["T"][a, b] == g
                        and n not in lot_of and n not in M["claimed"]):
                    facade.add((x, z))
    # the door: the facade column nearest the facade's middle
    if facade:
        fx = sum(c[0] for c in facade) / len(facade)
        fz = sum(c[1] for c in facade) / len(facade)
        door = min(facade, key=lambda c: ((c[0] - fx) ** 2 + (c[1] - fz) ** 2, c))
        lot.door = door
    corners = {c for c in boundary if sum((c[0] + dx, c[1] + dz) not in cols for dx, dz in D4) >= 2}
    order = sorted(facade)
    pier = {c for k, c in enumerate(order) if (c[0] + c[1]) % pier_every == 0}
    # the ladder: an inner column against the back wall, away from the door
    interior = [c for c in cols if c not in boundary]

    # where a lot's roof steps (a building against two risers of different heights), the higher part's side over
    # the lower roof is an outside wall too
    def low_side(c):
        return min([roof_of[(c[0] + dx, c[1] + dz)] for dx, dz in D4 if (c[0] + dx, c[1] + dz) in cols]
                   + [roof_of[c]])

    lad = None
    if interior and not lot.sealed:
        cand = []
        for (x, z) in interior:
            if low_side((x, z)) < roof_of[(x, z)]:
                continue                                # its own side opens above the lower roof
            for dx, dz in D4:
                n = (x + dx, z + dz)
                # the wall it hangs on stands the ladder's whole height
                if n in boundary and n not in facade and roof_of[n] >= roof_of[(x, z)]:
                    far = ((x - lot.door[0]) ** 2 + (z - lot.door[1]) ** 2) if lot.door else 0
                    cand.append((M["dist"][z - Z0, x - X0], -far, x, z, dx, dz))
        if cand:
            _, _, x, z, dx, dz = min(cand)
            lad = (x, z, FACE[(-dx, -dz)])
            lot.ladder = lad
    tops = {}
    for (x, z) in cols:
        r = roof_of[(x, z)]
        tops[(x, z)] = r
        is_b0 = (x, z) in boundary
        nlow = low_side((x, z))
        for y in range(g + 1, r):
            k = y - g
            is_b = is_b0 or y >= nlow
            if is_b:
                b = wall
                if (x, z) in corners or (x, z) in pier:
                    b = trim
                elif (x, z) in facade:
                    base = g + ((k - 1) // storey) * storey
                    row = y - base
                    if (y - g) % 16 == 8:
                        b = band[0] if (x + z) % 2 == 0 else band[1]
                    elif row in (2, 3) or (tall and row == 4 and y < r - 1):
                        b = win
                if lot.door == (x, z) and y in (g + 1, g + 2):
                    b = "minecraft:air"
                cv.put(x, y, z, b, owner=lot.id, exterior=(x, z) in facade and b in band)
            else:
                if k % storey == 0 and y <= r - 3:
                    if lad and (x, z) == (lad[0], lad[1]):
                        continue
                    lit = hsh(x, y, z, 5) % 9 == 0
                    cv.put(x, y, z, inner_light if lit else floor_b, owner=lot.id)
        # the roof is the street above
        if lad and (x, z) == (lad[0], lad[1]):
            continue
        rl = hsh(x, r, z, 7) % 13 == 0 and not is_b0
        cv.put(x, r, z, roof_light if rl else (edge_b if (x, z) in facade else roof_b), owner=lot.id, exterior=rl)
    # every storey lit: the slab over it carries a light at the interior's middle
    if interior:
        mx = sum(c[0] for c in interior) / len(interior)
        mz = sum(c[1] for c in interior) / len(interior)
        mid = min(interior, key=lambda c: ((c[0] - mx) ** 2 + (c[1] - mz) ** 2, c))
        if lad and mid == (lad[0], lad[1]):
            mid = None
        if mid:
            r = tops[mid]
            for y in range(g + storey, r - 2, storey):
                cv.put(mid[0], y, mid[1], inner_light, owner=lot.id)
    if lad:
        x, z, face = lad
        r = tops[(x, z)]
        for y in range(g + 1, r):
            cv.put(x, y, z, "minecraft:ladder[facing=%s,waterlogged=false]" % face, 2, owner=lot.id)
        cv.put(x, r, z, "%s[facing=%s,half=top,open=false,powered=false,waterlogged=false]" % (P("hatch"), face), 2,
               owner=lot.id)
    # a lamp over the door (L7)
    if lot.door:
        x, z = lot.door
        for dx, dz in D4:
            n = (x + dx, z + dz)
            if n not in cols and n not in lot_of and n not in M["claimed"]:
                a, b = n[1] - Z0, n[0] - X0
                if M["mask"][a, b] and M["T"][a, b] == g:
                    cv.put(n[0], g + 3, n[1], "minecraft:end_rod[facing=%s]" % FACE[(dx, dz)], 2, owner=lot.id,
                           exterior=True)
                    break
        if lot.sealed:
            face = None
            for dx, dz in D4:
                if (x + dx, z + dz) not in cols:
                    face = FACE[(dx, dz)]
                    break
            face = face or "north"
            cv.put(x, g + 1, z, "minecraft:iron_door[facing=%s,half=lower,hinge=left,open=false,powered=false]" % face,
                   2, owner=lot.id)
            cv.put(x, g + 2, z, "minecraft:iron_door[facing=%s,half=upper,hinge=left,open=false,powered=false]" % face,
                   2, owner=lot.id)
            # a sealed story room's own sign beside its door (data/deep_city.json rooms[].sign, 2026-10-03): on the
            # facade one block to the named side of the door, at head height, facing the street. Fails closed when
            # the facade there is not this building's wall or the street cell in front of it is taken
            sg = (lot.room or {}).get("sign")
            if sg:
                sx_, sz_ = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}[sg["side"]]
                fx, fz = {v: k for k, v in FACE.items()}[face]
                wall_c = (x + sx_, z + sz_)
                sign_c = (x + sx_ + fx, z + sz_ + fz)
                if wall_c not in cols or cv.get(wall_c[0], g + 2, wall_c[1]) in (None, "minecraft:air"):
                    raise CityError("room %s: no wall at %s to hang its sign on" % (lot.room["id"], wall_c))
                if sign_c in cols or cv.get(sign_c[0], g + 2, sign_c[1]) not in (None, "minecraft:air"):
                    raise CityError("room %s: the sign's cell %s is taken" % (lot.room["id"], sign_c))
                lines = ['{"text":"%s"}' % s.replace('"', "'") for s in (list(sg["lines"]) + ["", "", "", ""])[:4]]
                cv.put(sign_c[0], g + 2, sign_c[1],
                       "minecraft:warped_wall_sign[facing=%s,waterlogged=false]{front_text:{messages:['%s','%s','%s','%s']}}"
                       % ((face,) + tuple(lines)), 2, owner=lot.id, exterior=True)
                rooms_out_sign = [sign_c[0], g + 2, sign_c[1]]
                lot.room = dict(lot.room, sign_at=rooms_out_sign)
    # furniture for the families' homes (not in a story room: those are the story's to dress)
    if d.get("furnish") and lot.room is None and interior:
        mx = sum(c[0] for c in interior) / len(interior)
        mz = sum(c[1] for c in interior) / len(interior)
        t = min(interior, key=lambda c: (abs(c[0] - mx) + abs(c[1] - mz), c))
        if not (lad and t == (lad[0], lad[1])):
            cv.put(t[0], g + 1, t[1], "handcrafted:dark_oak_table", 2, owner=lot.id)
            cv.put(t[0], g + 2, t[1], "beautify:lamp_candelabra", 2, owner=lot.id)
            for dx, dz in ((1, 0), (-1, 0)):
                c = (t[0] + dx, t[1] + dz)
                if c in interior and not (lad and c == (lad[0], lad[1])):
                    cv.put(c[0], g + 1, c[1], "handcrafted:dark_oak_chair[facing=%s]" % FACE[(-dx, -dz)], 2,
                           owner=lot.id)
    if lot.room is not None:
        xs = [c[0] for c in cols]
        zs = [c[1] for c in cols]
        rooms_out.append({"id": lot.room["id"], "who": lot.room.get("who"), "note": lot.room.get("note"),
                          "district": lot.district, "level": g, "box": [min(xs), g + 1, min(zs), max(xs), max(tops.values()) - 1, max(zs)],
                          "door": [lot.door[0], g + 1, lot.door[1]] if lot.door else None, "sealed": lot.sealed,
                          "sign": lot.room.get("sign_at"),
                          "storeys": storeys(g, min(tops.values()), storey)})
    return tops, facade


def storeys(g, roof, storey):
    """[[lowest, highest] air y of each storey]: floors at g, g + storey, ... while a floor leaves 3 under the roof."""
    floors = [g] + [y for y in range(g + storey, roof - 2, storey)]
    return [[f + 1, (floors[k + 1] - 1) if k + 1 < len(floors) else roof - 1] for k, f in enumerate(floors)]


# ------------------------------------------------------------------ the build

def build(source_root, server_dir=None):
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    have = None
    if server_dir:
        import rift_deep as RD
        have = RD.installed_blocks(server_dir)
    P = Palette(spec, have)
    M = city_model(source_root, spec)
    X0, Z0 = M["X0"], M["Z0"]
    mask, T, H = M["mask"], M["T"], M["H"]
    NZ, NX = mask.shape
    cx, cz = M["cx"], M["cz"]
    bspec = spec["buildings"]
    zone = bspec["zone_depth"]
    dist, roofs = riser_field(M, 40)
    M["dist"] = dist
    counts = {}

    def count(k, v=1):
        counts[k] = counts.get(k, 0) + v

    def inpit(x, z):
        a, b = z - Z0, x - X0
        return 0 <= a < NZ and 0 <= b < NX and bool(mask[a, b])

    def t_at(x, z):
        return int(T[z - Z0, x - X0]) if inpit(x, z) else None

    def claimed_grid():
        taken = np.zeros(mask.shape, bool)
        for xq, zq in claimed:
            if 0 <= zq - Z0 < NZ and 0 <= xq - X0 < NX:
                taken[zq - Z0, xq - X0] = True
        return taken

    def free_boxes(ok):
        """(x0, z0, x1, z1) -> whether every cell of that box is in the pit and `ok`: a summed table built once, where
        the site searches tested every cell of every candidate box (7.8 million tests for the Centre and Mart)."""
        bad = np.zeros((NZ + 1, NX + 1), np.int64)
        bad[1:, 1:] = (~(ok & mask)).cumsum(0).cumsum(1)

        def free(x0, z0, x1, z1):
            a0, a1, b0, b1 = z0 - Z0, z1 - Z0, x0 - X0, x1 - X0
            return bool(0 <= a0 and a1 < NZ and 0 <= b0 and b1 < NX
                        and bad[a1 + 1, b1 + 1] - bad[a0, b1 + 1] - bad[a1 + 1, b0] + bad[a0, b0] == 0)
        return free

    cv = Canvas()
    claimed = set()
    M["claimed"] = claimed
    checks = []
    plan = {"towers": [], "rooms": [], "reserved": spec["reserved"], "services": [], "keep_clear": {}}

    # ---- keep clear: Victory Road's mouth and the plaza before it, every lift block and its rider's headroom
    vr = json.loads((ROOT / "data" / "vr_caves.json").read_text(encoding="utf-8"))
    mx, my, mz = vr["mouth"]["at"]
    kc = spec["keep_clear"]
    mt, mp = kc["mouth_tunnel"], kc["mouth_plaza"]
    tunnel = [mx - mt["half_width"], my - 1, mz - mt["north"], mx + mt["half_width"], my + mt["height"], mz + mt["south"]]
    plaza = [mx - mp["half_width"], 1, mz, mx + mp["half_width"], mp["height"], mz + mp["south"]]
    plan["keep_clear"] = {"mouth_tunnel": tunnel, "mouth_plaza": plaza}
    # the plaza is held open on the floor; the tunnel runs under ring 0's rock, so only its own volume is kept
    plaza_cols = {(x, z) for x in range(plaza[0], plaza[3] + 1) for z in range(plaza[2], plaza[5] + 1)}
    claimed |= plaza_cols
    reserved_boxes = [r["box"] for r in spec["reserved"]]

    # ---- the lift banks' stair towers
    rdspec = M["rd"]["spec"]
    rings = rdspec["rings"]["treads"]
    dnames = {0: "rimside", 1: "works", 2: "quarter", 3: "relay", 4: "core"}
    tower_cols = set()
    aprons = set()

    def tower_aprons(t):
        """The street in front of a tower's door and behind its landing, kept from the lots so both stay open."""
        w = frame(t["anchor"], t["back"])
        di, dj = t["door"]
        oi, oj = (1 if di == 5 else -1 if di == -1 else 0), (1 if dj == 5 else 0)
        out = set()
        for k_ in (1, 2, 3):
            for lat in (-1, 0, 1):
                out.add(w(di + oi * k_ + (lat if oj else 0), dj + oj * k_ + (lat if oi else 0)))
        li = t["top"][0]
        for jj in (-2, -3):
            for ii in (li - 1, li, li + 1):
                out.add(w(ii, jj))
        return out

    def door_out(t):
        w = frame(t["anchor"], t["back"])
        di, dj = t["door"]
        return list(w(di + (1 if di == 5 else -1 if di == -1 else 0), dj + (1 if dj == 5 else 0)))

    for k, lower, upper in M["lifts"]:
        g, gu = lower[1], upper[1]
        t = place_tower(M, g, gu, L=lower, U=upper, claimed=tower_cols | claimed)
        if t is None:
            raise CityError("no stair tower fits the lift bank at %s / %s" % (lower[:3], upper[:3]))
        t["L"], t["U"] = lower[:3], upper[:3]
        lo_name = spec["districts"][dnames[k + 1]]["name"]
        up_name = spec["districts"][dnames[k]]["name"]
        cols = build_tower(cv, P, M, t, "tower %d" % len(plan["towers"]), spec["districts"][dnames[k + 1]],
                           sign=[lo_name.upper(), "y%d" % g, "stairs up to", "%s y%d" % (up_name, gu)])
        tower_cols |= cols
        aprons |= tower_aprons(t) - cols
        w = frame(t["anchor"], t["back"])
        plan["towers"].append({"kind": "lift bank", "boundary": k, "lower_lift": list(lower[:3]), "upper_lift": list(upper[:3]),
                               "from": g, "to": gu, "door": list(w(*t["door"])), "door_out": door_out(t), "footprint": [list(c) for c in sorted(cols)][:1]
                               + [list(c) for c in sorted(cols)][-1:],
                               "upper_lift_lands": "inside" if (t["u_cell"] or t["u_wall"]) else "NOT IN THE TOWER",
                               "roof_open_over": [list(w(*c)) for c in t["climb_opened"]],
                               "headroom_blocked_by_lift": t.get("headroom_blocked_by_lift")})
        if t.get("headroom_blocked_by_lift"):
            count("stair towers whose top step is NOT walkable (a lift under the roof over step R-3)")
        checks.append((lower[0], gu, lower[2], [P("tread"), P("rib_teal"), P(spec["districts"][dnames[k + 1]]["wall"])], "lift landing roof"))
        checks.append((w(2, 2)[0], g + 2, w(2, 2)[1], [P("sea_lantern")], "tower core"))
        count("stair towers round lift banks")
        if not (t["u_cell"] or t["u_wall"]):
            count("upper lifts left outside their tower")
    claimed |= tower_cols | aprons

    # ---- the Sink Gate: a stair tower from the lip to ring 0 where the approach from the sink arrives
    regions = json.loads((ROOT / "data" / "rift_regions.json").read_text(encoding="utf-8"))["regions"]
    sk = regions[spec["sink_gate"]["toward_region"]]["seed"]
    sink_b = bearing(sk[0], sk[1], cx, cz)
    edge = []
    zz, xx = np.nonzero(mask & (T == rings[0]) & (dist == 0))
    for z, x in zip(zz.tolist(), xx.tolist()):
        wx, wz = x + X0, z + Z0
        edge.append((ang_diff(bearing(wx, wz, cx, cz), sink_b), wx, wz))
    edge.sort()
    gate = None
    for _d, ex_, ez_ in edge[:400]:
        # the lip behind this column, and a rise the stair can land on the back row
        outs = [int(H[ez_ + dz - Z0, ex_ + dx - X0]) for dx, dz in D4 if not inpit(ex_ + dx, ez_ + dz)]
        if not outs:
            continue
        lip = min(outs)
        if not 15 <= lip - rings[0] <= 19:
            continue

        def want(back, ex_=ex_, ez_=ez_):
            # the landing's wall behind it is this edge column; the landing is the top cell
            out = []
            steps_, top_, _o = stair_plan(lip - rings[0])
            r = RIGHT[back]
            i, j = top_[0], -1
            out.append((ex_ - i * r[0] + j * back[0], ez_ - i * r[1] + j * back[1]))
            return out
        M["outside_ok"] = True
        t = place_tower(M, rings[0], lip, claimed=claimed - aprons, want=want)
        M["outside_ok"] = False
        if t is None:
            continue
        w = frame(t["anchor"], t["back"])
        li, lj = t["top"]
        bx, bz = w(li, -2)
        if inpit(bx, bz) or int(H[bz - Z0, bx - X0]) != lip:
            continue
        gate = t
        break
    if gate is None:
        raise CityError("no site for the Sink Gate on ring 0 facing the sink")
    cols = build_tower(cv, P, M, gate, "the Sink Gate", spec["districts"]["rimside"],
                       sign=["THE SINK GATE", "Rimside y%d" % rings[0], "up to the", "Rift floor y%d" % gate["gu"]])
    ap = {c for c in tower_aprons(gate) - cols if inpit(*c)}
    aprons |= ap
    claimed |= cols | ap
    w = frame(gate["anchor"], gate["back"])
    gate_bearing = bearing(*w(2, 2), cx, cz)
    plan["sink_gate"] = {"door": list(w(*gate["door"])), "door_out": door_out(gate), "from": gate["g"], "to": gate["gu"], "bearing": round(gate_bearing, 1),
                         "exit": list(w(gate["top"][0], -2)),
                         "roof_open_over": [list(w(*c)) for c in gate["climb_opened"]]}
    count("the Sink Gate")

    # ---- the Centre and Mart, by the Sink Gate
    import place_town as PT
    for key in ("centre", "mart"):
        s = spec["services"][key]
        info = PT.template_info(ROOT / s["file"])
        best = None
        free = free_boxes(mask & (T == rings[0]) & ~claimed_grid() & (dist < 26))
        zz, xx = np.nonzero(mask & (T == rings[0]) & (dist <= 1))
        for z, x in zip(zz.tolist(), xx.tolist()):
            wx, wz = x + X0, z + Z0
            bd = ang_diff(bearing(wx, wz, cx, cz), gate_bearing)
            if bd > s["search_degrees"] or bd < 3:
                continue
            vx, vz = cx - wx, cz - wz
            facing = FACE[(1 if vx > 0 else -1, 0)] if abs(vx) >= abs(vz) else FACE[(0, 1 if vz > 0 else -1)]
            rot = PT.rotation_for(info["entrance"], facing)
            mnx, mnz, fw, fd = PT.footprint(info["size"], rot)
            f = DIR[facing]
            # the back row on this riser column, the front towards the street
            for off in range(0, max(fw, fd)):
                if f[0]:
                    x0 = wx if f[0] > 0 else wx - fw + 1
                    z0 = wz - off
                else:
                    z0 = wz if f[1] > 0 else wz - fd + 1
                    x0 = wx - off
                x1, z1 = x0 + fw - 1, z0 + fd - 1
                if not free(x0, z0, x1, z1):
                    continue
                # the street in front of the entrance: two rows of ring 0, nobody's
                if f[0]:
                    fr = [(x1 + k if f[0] > 0 else x0 - k, zq) for zq in range(z0, z1 + 1) for k in (1, 2)]
                else:
                    fr = [(xq, z1 + k if f[1] > 0 else z0 - k) for xq in range(x0, x1 + 1) for k in (1, 2)]
                if not all(t_at(*c) == rings[0] and c not in claimed for c in fr):
                    continue
                cand = (bd, x0, z0)
                if best is None or cand < best[0]:
                    best = (cand, dict(x0=x0, z0=z0, x1=x1, z1=z1, rot=rot, mnx=mnx, mnz=mnz, facing=facing, info=info))
        if best is None:
            raise CityError("no ring-0 site for the %s near the Sink Gate" % key)
        b = best[1]
        for xq in range(b["x0"] - 1, b["x1"] + 2):
            for zq in range(b["z0"] - 1, b["z1"] + 2):
                if t_at(xq, zq) == rings[0]:
                    claimed.add((xq, zq))
        plan["services"].append({"id": key, "template": s["template"], "file": s["file"],
                                 "box": [b["x0"], rings[0], b["z0"], b["x1"], rings[0] + info["size"][1], b["z1"]],
                                 "rotation": b["rot"], "facing": b["facing"]})
        count("services (%s)" % key)
    services = [dict(q) for q in plan["services"]]

    # ---- the Core spire, grown upward as Heaven's Arena (docs/world-building/HEAVENS_ARENA.md, site A)
    sp = spec["spire"]
    ar = spec.get("arena")
    rad = (ar or sp)["radius"]
    floor_lifts = [lo for k, lo, up in M["lifts"] if lo[1] == rings[-1]]
    best = None
    free = free_boxes(mask & (T == rings[-1]) & ~claimed_grid())
    zz, xx = np.nonzero(mask & (T == rings[-1]) & ~M["sheer"])
    for z, x in zip(zz.tolist(), xx.tolist()):
        wx, wz = x + X0, z + Z0
        if any(abs(wx - lx) + abs(wz - lz) < rad + 12 for lx, _ly, lz, _o in floor_lifts):
            continue
        if not free(wx - rad - 1, wz - rad - 1, wx + rad + 1, wz + rad + 1):
            continue
        cand = (int(dist[z, x]), -abs(wx - cx) - abs(wz - cz))
        if best is None or cand > best[0]:
            best = (cand, (wx, wz))
    if best is None:
        raise CityError("no room for the spire on the Core's floor")
    scx, scz = best[1]
    g0 = rings[-1]
    if ar:
        # the arena's tiers are the pit's own 15-then-17 grammar continued upward; the crown caps the drum
        decks = [int(t) for t in ar["tiers"]]
        top = int(ar["crown"])
        if decks != sorted(set(decks)) or decks[0] != g0 + 15:
            raise CityError("the arena's tiers must rise from y%d: %s" % (g0 + 15, decks))
        if min(b_ - a_ for a_, b_ in zip(decks, decks[1:])) < 11 or top - decks[-1] < 11:
            raise CityError("the arena leaves a tier under 11 of clear: %s, crown y%d" % (decks, top))
        hq_top = spec["hq"]["tower"]["top"]
        if top >= hq_top:
            raise CityError("the arena's crown y%d would meet the HQ tower's y%d: the HQ stays the dominant building"
                            % (top, hq_top))
        if top + 2 >= 150:
            raise CityError("the arena's beacon at y%d breaks the audit's y150 ceiling" % (top + 2))
        shell_top, crown = top, top
        lit_courses = set(decks) | {crown}                      # a lit course at every tier: the ladder, seen outside
        dark_courses = {d_ + 8 for d_ in decks}
        deck_ys = decks + [crown]
        core_top = crown - 1                                    # the shaft's walls stop one under the crown deck
    else:
        top = sp["top"]
        decks = list(range(g0 + 15, top, sp["deck_every"]))
        shell_top, crown = top, None
        lit_courses = {y for y in range(g0 + 1, top + 1) if (y - g0) % 16 == 0}
        dark_courses = {y for y in range(g0 + 1, top + 1) if (y - g0) % 8 == 4}
        deck_ys = decks
        core_top = decks[-1] + 2
    spire_cols = set()
    for dx in range(-rad - 1, rad + 2):
        for dz in range(-rad - 1, rad + 2):
            r = math.hypot(dx, dz)
            x, z = scx + dx, scz + dz
            if r >= rad + 0.5:
                continue
            spire_cols.add((x, z))
            a = math.degrees(math.atan2(dx, -dz)) % 360
            if r >= rad - 0.5:
                rib = ang_diff(a, round(a / 45.0) * 45.0) < 360.0 / (2 * math.pi * rad) * 0.75
                door = min(abs(dx), abs(dz)) <= 1
                for y in range(g0 + 1, shell_top + 1):
                    if door and y <= g0 + 4:
                        continue
                    if rib:
                        b = P("rib_teal")
                    elif y in lit_courses:
                        b = P("sea_lantern")
                    elif y in dark_courses:
                        b = P("glass_dark")
                    else:
                        b = P("glass_conduit")
                    cv.put(x, y, z, b, owner="spire", exterior=b == P("sea_lantern"))
                if rib:
                    cv.put(x, shell_top + 1, z, P("crystal"), 2, owner="spire")
            elif max(abs(dx), abs(dz)) > 3:
                for y in deck_ys:
                    lit = (dx * 3 + dz) % 5 == 0
                    cv.put(x, y, z, P("sea_lantern") if lit else P("tread"), owner="spire", exterior=True)
            cv.put(x, g0, z, P("tread") if (dx + dz) % 4 else P("violet"), owner="spire", exterior=(dx + dz) % 4 == 0)
    # the crown's balustrade on the shell's own ring (the arena), or the top deck's parapet (the spire): a glass
    # railing at every edge where a walk surface drops two or more, L2's language. Never over a rib's crystal.
    for dx in range(-rad - 1, rad + 2):
        for dz in range(-rad - 1, rad + 2):
            r = math.hypot(dx, dz)
            if ar:
                if not (rad - 0.5 <= r < rad + 0.5):
                    continue
                y_ = crown + 1
            else:
                if not (rad - 1.5 <= r < rad - 0.5):
                    continue
                y_ = decks[-1] + 1
            x, z = scx + dx, scz + dz
            if cv.get(x, y_, z) in (None, "minecraft:air"):
                cv.put(x, y_, z, P("rail"), 2, owner="spire", exterior=True)
    # the stair round the spire's core, from the floor to the top deck, a door onto every deck. With the back to the
    # north, interior (0, 0) is the north-west inner corner
    stair_top = crown if ar else decks[-1]
    R = stair_top - g0
    steps_ = {}
    cells = ring_cells()
    for s in range(1, R + 1):
        steps_.setdefault(cells[(s - 1) % 16], []).append(s)
    lv = {(i, j): g0 for i in range(-1, 6) for j in range(-1, 6)}
    spire_tower = dict(anchor=(scx - 2, scz - 2), back=(0, -1), g=g0, gu=stair_top, R=R, steps=steps_,
                       top=cells[(R - 1) % 16], opened=[], levels=lv, door=(2, 5), u_cell=None, u_wall=None)
    build_tower(cv, P, M, spire_tower, "the spire", spec["districts"]["core"], pylon=0, walls_to=core_top,
                exits=[d_ - g0 for d_ in decks], roof=False, owner="spire")
    if ar:
        # the crown deck closes the stair well over every ring cell whose last step is FOUR or more below it, so the
        # climber's head and the step above it are never under a floor; the arrival stays open. It was three until
        # 2026-10-03: a climber stepping up off step crown-3 needs air at the crown over that step (climb_cells), and
        # the deck there made the crown unreachable on foot
        for c in cells:
            if max(steps_[c]) + g0 > crown - 4:
                continue
            x, z = frame(spire_tower["anchor"], spire_tower["back"])(*c)
            cv.put(x, crown, z, P("tread"), owner="spire")
    # the beacon over the core: a gold base flush in the deck, nothing of iron (Meltan), the beam turned cyan
    beacon_base = crown if ar else core_top
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            cv.put(scx + dx, beacon_base, scz + dz, "minecraft:gold_block", owner="spire")
    cv.put(scx, beacon_base + 1, scz, "minecraft:beacon", 2, owner="spire")
    cv.put(scx, beacon_base + 2, scz, P("glass_conduit"), 2, owner="spire")
    claimed |= spire_cols
    plan["spire"] = {"centre": [scx, scz], "radius": rad, "top": shell_top, "decks": decks,
                     "beacon": [scx, beacon_base + 1, scz]}
    checks.append((scx, beacon_base + 1, scz, ["minecraft:beacon"], "spire beacon"))
    checks.append((scx, g0 + 20, scz, [P("sea_lantern")], "spire core"))
    count("the spire")
    if ar:
        plan["arena"] = arena_plan(cv, P, ar, spec, scx, scz, g0, rad, decks, crown, beacon_base, spire_tower, count,
                                   checks)

    # ---- bridges at y15 from the spire to Relay Row
    by = sp["bridge_y"]
    bridges = []
    bridge_cols = set()
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        path = []
        ok_ = False
        for tt in range(rad - 1, 140):
            x, z = scx + d[0] * tt, scz + d[1] * tt
            tv = t_at(x, z)
            if tv is None:
                break
            if any(_in_box((x + d[1] * o, y_, z + d[0] * o), plaza) for o in (-1, 0, 1) for y_ in (by, by + 1)):
                break
            if tv > by:
                break
            path.append((x, z))
            if tv == by and tt > rad + 1:
                ok_ = True
                break
        if not ok_:
            continue
        cols_ = [(x + d[1] * o, z + d[0] * o, o) for x, z in path for o in (-1, 0, 1)]
        if any((x, z) in tower_cols or (x, z) in plan_service_cols(services) for x, z, _o in cols_):
            continue
        for k_, (x, z) in enumerate(path):
            for o in (-1, 0, 1):
                bx_, bz_ = x + d[1] * o, z + d[0] * o
                if (bx_, bz_) in spire_cols and math.hypot(bx_ - scx, bz_ - scz) < rad - 0.5:
                    continue
                on_ring = t_at(bx_, bz_) == by
                if not on_ring:
                    lit = o == 0 and k_ % 3 == 0
                    cv.put(bx_, by, bz_, P("sea_lantern") if lit else (P("tread_edge") if o else P("tread")),
                           owner="bridge", exterior=lit)
                if (bx_, bz_) in spire_cols:
                    for y in (by + 1, by + 2, by + 3):
                        cv.put(bx_, y, bz_, "minecraft:air", owner="bridge")
                elif o and not on_ring:
                    cv.put(bx_, by + 1, bz_, P("rail"), 2, owner="bridge", exterior=True)
                bridge_cols.add((bx_, bz_))
        bridges.append({"toward": FACE[d], "from": list(path[0]), "to": list(path[-1]), "length": len(path)})
        count("bridges")
    plan["bridges"] = bridges

    # ---- approaches: a 3-wide way from every tower door, the Sink Gate, the Centre, the Mart and round the spire
    #      out to the open street, kept from the lots so no building walls a door into a courtyard
    def approach(start, level):
        if t_at(*start) != level:
            return set()
        par = {start: None}
        q = deque([start])
        end = None
        while q:
            c = q.popleft()
            if dist[c[1] - Z0, c[0] - X0] >= zone:
                end = c
                break
            for dx, dz in D4:
                n = (c[0] + dx, c[1] + dz)
                if n not in par and t_at(*n) == level and n not in tower_cols and n not in spire_cols \
                        and n not in plan_service_cols(services):
                    par[n] = c
                    q.append(n)
        if end is None:
            raise CityError("no way out to the street from %s at y%d" % (start, level))
        path = []
        while end is not None:
            path.append(end)
            end = par[end]
        out = set()
        for x, z in path:
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    n = (x + dx, z + dz)
                    if t_at(*n) == level and n not in tower_cols and n not in spire_cols:
                        out.add(n)
        return out

    starts = []
    for t_ in plan["towers"]:
        starts.append((tuple(t_["door_out"]), t_["from"]))
    starts.append((tuple(plan["sink_gate"]["door_out"]), plan["sink_gate"]["from"]))
    for s in services:
        x0, y0, z0, x1, _y1, z1 = s["box"]
        f = DIR[s["facing"]]
        if f[0]:
            starts.append((((x1 + 1) if f[0] > 0 else (x0 - 1), (z0 + z1) // 2), y0))
        else:
            starts.append((((x0 + x1) // 2, (z1 + 1) if f[1] > 0 else (z0 - 1)), y0))
    for dx, dz in D4:
        starts.append(((scx + dx * (rad + 1), scz + dz * (rad + 1)), g0))
    for st_, lv_ in starts:
        ap = approach(st_, lv_)
        aprons |= ap
        claimed |= ap
    plan["approaches"] = len(starts)

    # ---- the lots: seeds along every riser, cells round them
    lot_zone = (dist < zone) & mask
    for (x, z) in claimed | bridge_cols:
        a, b = z - Z0, x - X0
        if 0 <= a < NZ and 0 <= b < NX:
            lot_zone[a, b] = False
    # the HQ first: its bearing window on every ring and the floor
    hq = spec["hq"]
    b0, b1 = hq["bearing"]
    brg = np.zeros(mask.shape, np.float32)
    zz, xx = np.nonzero(mask)
    for z, x in zip(zz.tolist(), xx.tolist()):
        brg[z, x] = bearing(x + X0, z + Z0, cx, cz)
    in_hq = lot_zone & (brg >= b0) & (brg <= b1) & ~M["sheer"]
    f0, f1 = hq.get("floor_bearing", hq["bearing"])
    in_hq_floor = lot_zone & (brg >= f0) & (brg <= f1) & ~M["sheer"]
    lots = []
    lot_of = {}
    for lv_ in rings:
        sel = (in_hq_floor if lv_ == rings[-1] else in_hq) & (T == lv_)
        comp = _largest_component(sel)
        if not comp:
            continue
        cols_ = {(x + X0, z + Z0) for z, x in comp}
        lot = Lot("hq_%d" % lv_, cols_, lv_, "hq")
        lot.kind = "hq"
        lots.append(lot)
        for c in cols_:
            lot_of[c] = lot
            lot_zone[c[1] - Z0, c[0] - X0] = False
    # the HQ tower, over the sited column, inside the ring-0 section
    hq0 = next((l_ for l_ in lots if l_.level == rings[0]), None)
    if hq0 is None:
        raise CityError("the HQ has no ring-0 section in its bearing window")
    tx_, tz_ = hq["tower"]["at"]
    ts = hq["tower"]["size"]
    tower_box = None
    for off in sorted(((ox, oz) for ox in range(-12, 13) for oz in range(-12, 13)), key=lambda o: abs(o[0]) + abs(o[1])):
        x0, z0 = tx_ + off[0] - ts // 2, tz_ + off[1] - ts // 2
        box_cols = {(x, z) for x in range(x0, x0 + ts) for z in range(z0, z0 + ts)}
        if box_cols <= hq0.cols:
            tower_box = (x0, z0, x0 + ts - 1, z0 + ts - 1)
            break
    if tower_box is None:
        raise CityError("the HQ tower does not fit in the HQ's ring-0 section")
    hq_tower_cols = {(x, z) for x in range(tower_box[0], tower_box[2] + 1) for z in range(tower_box[1], tower_box[3] + 1)}
    hq0.cols -= hq_tower_cols
    for c in hq_tower_cols:
        lot_of.pop(c, None)
    claimed |= hq_tower_cols
    # the generic lots
    seeds = []
    zz, xx = np.nonzero(lot_zone & (dist == 7))
    order = sorted(zip(zz.tolist(), xx.tolist()), key=lambda p: (int(T[p[0], p[1]]), brg[p[0], p[1]]))
    grid = {}
    fr = bspec["frontage"]
    for z, x in order:
        wx, wz = x + X0, z + Z0
        gk = (wx // fr, wz // fr)
        near = False
        for ax in range(gk[0] - 1, gk[0] + 2):
            for az in range(gk[1] - 1, gk[1] + 2):
                for sx, sz, st_ in grid.get((ax, az), []):
                    if st_ == T[z, x] and (sx - wx) ** 2 + (sz - wz) ** 2 < fr * fr:
                        near = True
        if near:
            continue
        grid.setdefault(gk, []).append((wx, wz, int(T[z, x])))
        seeds.append((wx, wz, int(T[z, x])))
    members = {}
    zz, xx = np.nonzero(lot_zone)
    sgrid = {}
    for n_, (sx, sz, st_) in enumerate(seeds):
        sgrid.setdefault((sx // fr, sz // fr), []).append(n_)
    for z, x in zip(zz.tolist(), xx.tolist()):
        wx, wz = x + X0, z + Z0
        tv = int(T[z, x])
        gk = (wx // fr, wz // fr)
        bestn, bd = None, None
        for ax in range(gk[0] - 2, gk[0] + 3):
            for az in range(gk[1] - 2, gk[1] + 3):
                for n_ in sgrid.get((ax, az), []):
                    sx, sz, st_ = seeds[n_]
                    if st_ != tv:
                        continue
                    d2 = (sx - wx) ** 2 + (sz - wz) ** 2
                    if bd is None or d2 < bd:
                        bestn, bd = n_, d2
        if bestn is not None:
            members.setdefault(bestn, []).append((wx, wz))
    for n_ in sorted(members):
        sx, sz, st_ = seeds[n_]
        depth = bspec["depths"][hsh(sx, sz, st_, 3) % len(bspec["depths"])]
        cols_ = {(x, z) for x, z in members[n_] if dist[z - Z0, x - X0] < depth}
        cols_ = _largest_component_set(cols_)
        if len(cols_) < bspec["min_columns"]:
            continue
        sheer_lot = bool(M["sheer"][sz - Z0, sx - X0])
        ring_k = int(M["ring"][sz - Z0, sx - X0])
        district = "stacks" if sheer_lot else dnames[ring_k]
        lot = Lot("lot_%d_%d_%d" % (sx, st_, sz), cols_, st_, district)
        lots.append(lot)
        for c in cols_:
            lot_of[c] = lot
    for lot in lots:
        xs = [c[0] for c in lot.cols]
        zs = [c[1] for c in lot.cols]
        lot.cols_min = (min(xs), min(zs))
        lot.centroid = (sum(xs) / len(xs), sum(zs) / len(zs))
        lot.bearing = bearing(lot.centroid[0], lot.centroid[1], cx, cz)
    # the story's rooms: HQ sections by ring, and named lots by ring and bearing
    used = set()
    for room in spec["rooms"]:
        if room["in"] == "hq":
            lv_ = rings[room["ring"]]
            lot = next((l_ for l_ in lots if l_.kind == "hq" and l_.level == lv_), None)
            if lot is None:
                raise CityError("room %s: the HQ has no section on ring %d" % (room["id"], room["ring"]))
            lot.room = lot.room or room
            lot.rooms = getattr(lot, "rooms", []) + [room]
            lot.sealed = lot.sealed or bool(room.get("sealed"))
        elif room["in"] == "lot":
            lv_ = rings[room["ring"]]
            cand = [l_ for l_ in lots if l_.kind == "home" and l_.level == lv_ and l_.id not in used
                    and l_.district == dnames[room["ring"]]]
            if not cand:
                raise CityError("room %s: no lot on ring %d" % (room["id"], room["ring"]))
            lot = min(cand, key=lambda l_: (ang_diff(l_.bearing, room["bearing"]), l_.id))
            lot.room = room
            lot.kind = "room"
            used.add(lot.id)
    # every lot's roof per column
    roof_of = {}
    for lot in lots:
        for (x, z) in lot.cols:
            r = int(roofs[z - Z0, x - X0])
            if lot.level == rings[0]:
                r = min(max(r, rings[0] + 12), rings[0] + 24)
            roof_of[(x, z)] = r
    rooms_out = []
    lot_tops = {}
    all_facades = {}
    for lot in lots:
        tops, facade = build_lot(cv, P, spec, lot, roof_of, lot_of, M, rooms_out)
        lot_tops.update(tops)
        all_facades[lot.id] = facade
        count("buildings (%s)" % spec["districts"][lot.district]["name"])
        if lot.kind == "hq" and getattr(lot, "rooms", None):
            sts = storeys(lot.level, min(tops.values()), bspec["storey"])
            for room in lot.rooms:
                si = room.get("storey", 0)
                lo, hi = sts[si]
                xs = [c[0] for c in lot.cols]
                zs = [c[1] for c in lot.cols]
                rooms_out[:] = [r_ for r_ in rooms_out if r_["id"] != room["id"]]
                rooms_out.append({"id": room["id"], "who": room.get("who"), "note": room.get("note"), "district": "hq",
                                  "level": lot.level, "box": [min(xs), lo, min(zs), max(xs), hi, max(zs)],
                                  "door": [lot.door[0], lot.level + 1, lot.door[1]] if lot.door and si == 0 else None,
                                  "sealed": bool(room.get("sealed")), "storey": si,
                                  "section_columns": len(lot.cols),
                                  "sign": (lot.room or {}).get("sign_at") if si == 0 else None})
    # the shaft head is NOT the city's (2026-10-02). This build used to lay a reinforced-deepslate hatch on the ring-0
    # section's columns nearest the sited column (3427, 3308); the tower box and the pit's edge left only (3427, 3308)
    # and (3427, 3309), both boundary columns, so the hatch lay under the section's own west wall where no shaft can
    # open. The secure shaft is now a stair from storey 0's south-west corner, carved with the records room by
    # tools/relic_underground.py (R9RU, data/relic_underground.json geometry.hq), which also lays those two cells back
    # to rock on a world that has the hatch. The stair's head is reserved (data/deep_city.json hq_shaft_head).
    plan["hq_shaft_head"] = "tools/relic_underground.py, data/relic_underground.json geometry.hq"
    # the HQ tower
    x0, z0, x1, z1 = tower_box
    base = rings[0] + 1
    ttop = hq["tower"]["top"]
    vx, vz = cx - (x0 + x1) / 2.0, cz - (z0 + z1) / 2.0
    face = (1 if vx > 0 else -1, 0) if abs(vx) >= abs(vz) else (0, 1 if vz > 0 else -1)
    sym_c = ((x0 + x1) // 2, ttop - 14, (z0 + z1) // 2)
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            edge_ = x in (x0, x1) or z in (z0, z1)
            corner = x in (x0, x1) and z in (z0, z1)
            on_face = (face[0] == 1 and x == x1) or (face[0] == -1 and x == x0) or (face[1] == 1 and z == z1) or \
                (face[1] == -1 and z == z0)
            for y in range(base, ttop + 1):
                if edge_:
                    if corner or (x + z) % 4 == 0:
                        b = P("rib_teal")
                    elif (y - base) % 6 == 0:
                        b = P("panel_black")
                    else:
                        b = P("glass_dark")
                    if on_face and not corner:
                        u = (z - sym_c[2]) if face[0] else (x - sym_c[0])
                        v = y - sym_c[1]
                        rr = math.hypot(u, v)
                        if 3.5 <= rr <= 4.6 or (v == 0 and abs(u) <= 5):
                            b = P("sea_lantern")
                        elif rr < 3.5 or (abs(v) <= 1 and abs(u) <= 5):
                            b = P("panel_black")
                    cv.put(x, y, z, b, owner="hq_tower", exterior=b == P("sea_lantern"))
                elif (y - base) % 6 == 0 and y > base:
                    lit = (x - x0 + z - z0) % 5 == 0
                    cv.put(x, y, z, P("sea_lantern") if lit else P("deep_stone"), owner="hq_tower")
            cv.put(x, ttop + 1, z, P("panel_black") if not (x in (x0, x1) or z in (z0, z1)) else P("rib_teal"),
                   owner="hq_tower")
    for x, z in ((x0, z0), (x0, z1), (x1, z0), (x1, z1)):
        cv.put(x, ttop + 2, z, "minecraft:end_rod[facing=up]", 2, owner="hq_tower", exterior=True)
    ys = list(range(base, ttop, 6))
    rooms_out.append({"id": "hq_tower", "who": "the Compact", "note": "the tower's storeys, empty; no way in is built",
                      "district": "hq", "level": base, "box": [x0 + 1, base, z0 + 1, x1 - 1, ttop, z1 - 1], "door": None,
                      "sealed": True, "storeys": [[y + 1, y + 5] for y in ys]})
    plan["hq"] = {"tower": list(tower_box), "top": ttop, "symbol_face": FACE[face], "symbol_centre": list(sym_c),
                  "sections": {l_.level: len(l_.cols) for l_ in lots if l_.kind == "hq"}}
    checks.append((sym_c[0] + (5 if face[0] > 0 else -5 if face[0] < 0 else 0), sym_c[1],
                   sym_c[2] + (5 if face[1] > 0 else -5 if face[1] < 0 else 0), [P("sea_lantern"), P("rib_teal")], "hq symbol"))
    count("the HQ tower")
    # the cordon round the HQ's lower door on the Core
    hq_floor = next((l_ for l_ in lots if l_.kind == "hq" and l_.level == rings[-1]), None)
    if hq_floor and hq_floor.door:
        dx_, dz_ = hq_floor.door
        ring_cols = set()
        for x in range(dx_ - 5, dx_ + 6):
            for z in range(dz_ - 5, dz_ + 6):
                if max(abs(x - dx_), abs(z - dz_)) == 5 and t_at(x, z) == rings[-1] and (x, z) not in lot_of \
                        and (x, z) not in claimed:
                    ring_cols.add((x, z))
        for x, z in ring_cols:
            cv.put(x, rings[-1] + 1, z, P("glass_dark"), owner="hq_cordon")
            cv.put(x, rings[-1] + 2, z, P("bars"), 2, owner="hq_cordon")
            cv.put(x, rings[-1] + 3, z, P("bars"), 2, owner="hq_cordon")
            if (x + z) % 4 == 0:
                cv.put(x, rings[-1] + 4, z, "minecraft:end_rod[facing=up]", 2, owner="hq_cordon", exterior=True)
        count("HQ cordon columns", len(ring_cols))

    # ---- the walk surface: what each column is walked on at, for railings, sidewalks and light
    WS = {}
    zz, xx = np.nonzero(mask)
    lot_cols = set(lot_of)
    # built things with their own edges; the kept-clear plaza is open floor and stays in
    built = (claimed - plaza_cols - aprons) | bridge_cols
    for z, x in zip(zz.tolist(), xx.tolist()):
        c = (x + X0, z + Z0)
        if c in lot_cols:
            WS[c] = lot_tops.get(c)
        elif c in built:
            continue
        else:
            WS[c] = int(T[z, x])
    lift_cols = set()
    for k, lo, up in M["lifts"]:
        for p in (lo, up):
            lift_cols |= {(p[0] + dx, p[2] + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
    hatch_cols = {(l_.ladder[0], l_.ladder[1]) for l_ in lots if l_.ladder}
    rails = set()
    for c, y in WS.items():
        if y is None or c in lift_cols or c in hatch_cols:
            continue
        for dx, dz in D4:
            ny = WS.get((c[0] + dx, c[1] + dz))
            if ny is not None and ny <= y - 2:
                rails.add(c)
                break
    for c in rails:
        y = WS[c]
        cv.put(c[0], y + 1, c[1], P("rail"), 2, owner="rail", exterior=True)
        if (c[0] + c[1]) % 3 == 0 and (c[0], y, c[1]) not in M["L1"]:
            cv.put(c[0], y, c[1], P("sea_lantern"), owner="rail", exterior=True)
            count("contour lights (L2)")
    count("railing columns", len(rails))

    # ---- sidewalks, the Works' conduit, the front row, the plaza
    street = {c: y for c, y in WS.items() if c not in lot_cols}
    fac_cols = set()
    for lot in lots:
        fac_cols |= all_facades[lot.id]
    side = {}
    for (x, z) in fac_cols:
        lot = lot_of.get((x, z))
        g = lot.level
        dname = lot.district
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                n = (x + dx, z + dz)
                if street.get(n) == g and n not in rails and (n[0], g, n[1]) not in M["L1"]:
                    side[n] = spec["districts"][dname]["sidewalk"]
    for (x, z), b in side.items():
        cv.put(x, street[(x, z)], z, b, owner="sidewalk")
    count("sidewalk columns", len(side))
    st_spec = spec["streets"]
    conduit_ring = rings[st_spec["conduit_ring"]]
    n_con = 0
    for (x, z), y in street.items():
        if y == conduit_ring and dist[z - Z0, x - X0] == st_spec["conduit_at"] and (x, z) not in rails \
                and (x, y, z) not in M["L1"] and (x, z) not in lift_cols:
            cv.put(x, y, z, P("sea_lantern") if (x + z) % 2 == 0 else P("glass_conduit"), owner="conduit",
                   exterior=(x + z) % 2 == 0)
            n_con += 1
    count("Works conduit columns (L4)", n_con)
    # the plaza: the sheer floor, paved
    pl = spec["plaza"]
    pave, grid_b = pl["paving"], P("plaza_grid") if "plaza_grid" in spec["materials"] else pl["grid"]
    if have is not None and grid_b not in have:
        grid_b = pl["grid_fallback"]
    n_pl = 0
    for (x, z), y in street.items():
        if y == rings[-1] and M["sheer"][z - Z0, x - X0] and (x, y, z) not in M["L1"] and (x, z) not in side:
            if cv.get(x, y, z) is None:
                cv.put(x, y, z, grid_b if (x % pl["grid_every"] == 0 or z % pl["grid_every"] == 0) else pave, owner="plaza")
                n_pl += 1
    count("plaza columns paved", n_pl)
    # the front row: stalls, pylons, benches and masts, spaced along the street's outer band
    feats = []
    fr_every = st_spec["front_row_every"]
    taken = {}
    edge_d = _edge_distance(rails, street)
    for (x, z), y in sorted(street.items(), key=lambda kv: (kv[1], kv[0][1], kv[0][0])):
        a, b = z - Z0, x - X0
        if M["sheer"][a, b] or dist[a, b] < st_spec["front_row_from"] or edge_d.get((x, z), 99) < 3:
            continue
        ring_k = int(M["ring"][a, b])
        kind = spec["districts"][dnames[ring_k]]["front_row"]
        if kind == "none" or (x, z) in lift_cols or (x, z) in side:
            continue
        if any(abs(x - lx) + abs(z - lz) < 6 for lx, lz in lift_cols):
            continue
        gk = (x // fr_every, z // fr_every)
        if any((sx - x) ** 2 + (sz - z) ** 2 < fr_every ** 2 for ax in (gk[0] - 1, gk[0], gk[0] + 1)
               for az in (gk[1] - 1, gk[1], gk[1] + 1) for sx, sz, sy in taken.get((ax, az), []) if sy == y):
            continue
        fp = [(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)]
        if not all(street.get(c) == y and c not in rails and c not in side and c not in aprons for c in fp):
            continue
        taken.setdefault(gk, []).append((x, z, y))
        _feature(cv, P, kind, x, y, z)
        feats.append(kind)
    for k_ in sorted(set(feats)):       # sorted: a set of strings iterates in PYTHONHASHSEED order, and this is the
        count("front row: %s" % k_, feats.count(k_))     # only thing that made derived/deep_city/plan.json vary

    # ---- the relic area
    relic = build_relic(cv, P, spec, source_root, count, checks)
    plan["relic"] = relic

    # ---- light: the fixtures, modelled, then filled in where a street is under its target
    targets = spec["lights"]["targets"]
    walk = {}
    for c, y in WS.items():
        if y is None:
            continue
        a, b = c[1] - Z0, c[0] - X0
        if c in lot_cols:
            walk[c] = (y, targets["roof"])
        elif M["sheer"][a, b]:
            walk[c] = (y, targets["plaza"])
        else:
            walk[c] = (y, targets["street"])
    for c in bridge_cols:
        walk[c] = (by, targets["street"])
    em = []
    for (x, y, z), (b, _ph) in cv.v.items():
        lvl = P.level(b)
        if lvl and (x, y, z) in cv.exterior:
            em.append((x, y, z, lvl))
    for (x, y, z) in M["L1"]:
        if cv.get(x, y, z) is None:
            em.append((x, y, z, 15))
    light = LightModel(walk, X0, Z0, mask.shape)
    for e in em:
        light.stamp(*e)
    before = light.summary()
    forbid = lift_cols | rails | hatch_cols

    def floor_light_for(c):
        a, b = c[1] - Z0, c[0] - X0
        if c in lot_cols:
            dname = lot_of[c].district
        elif c in bridge_cols:
            dname = "relay"
        elif M["sheer"][a, b]:
            dname = "stacks"
        else:
            dname = dnames[int(M["ring"][a, b])]
        return P(spec["districts"][dname]["floor_light"])

    def set_light(p, y):
        if p not in walk or walk[p][0] != y or p in forbid or (p[0], y, p[1]) in M["L1"]:
            return False
        cur = cv.get(p[0], y, p[1])
        if cur is not None and (P.level(cur) or cv.owner.get((p[0], y, p[1])) in ("front",)):
            return False
        lb = floor_light_for(p)
        cv.put(p[0], y, p[1], lb, owner="fill_light", exterior=True)
        light.stamp(p[0], y, p[1], P.level(lb) or 15)
        return True

    # first a lattice, so the floor lights read as a laid pattern: a flush 15 lights the cell above it at 14, so a
    # target t is met within manhattan r = 14 - t, and the lattice (x + (2r+1) z) mod (2r^2 + 2r + 1) = 0 puts every
    # cell of an open floor within r of exactly one light (r = 2 on streets, 6 on roofs and the plaza)
    n_lat = 0
    for c in sorted(walk, key=lambda c: (walk[c][0], c[1], c[0])):
        y, tgt = walk[c]
        r = 14 - tgt
        if (c[0] + (2 * r + 1) * c[1]) % (2 * r * r + 2 * r + 1) == 0 and light.at(c) < 15:
            n_lat += set_light(c, y)
    count("lattice floor lights", n_lat)
    # then whatever the lattice could not reach (a lattice cell under a building, a railing, a lift), filled in
    n_fill = 0
    for c in sorted(walk, key=lambda c: (walk[c][0], c[1], c[0])):
        y, tgt = walk[c]
        if light.at(c) >= tgt:
            continue
        for dx, dz in ((1, 1), (2, 0), (0, 1), (1, 0), (0, 0), (-1, 1), (0, 2)):
            if set_light((c[0] + dx, c[1] + dz), y):
                n_fill += 1
                break
    count("fill-in floor lights", n_fill)
    plan["light"] = {"before_fill": before, "after_fill": light.summary(), "model": "manhattan distance, no occlusion: optimistic next to walls, NOT measured"}

    # ---- panes join what stands beside them; nothing on a lift, nothing in a kept-clear or reserved box
    connect_panes(cv)
    for k, lo, up in M["lifts"]:
        for p in (lo, up):
            cv.drop(p[0], p[1], p[2])
            for y in (p[1] + 1, p[1] + 2):
                if cv.get(p[0], y, p[2]) not in (None, "minecraft:air"):
                    cv.drop(p[0], y, p[2])
                    count("writes dropped over a lift's headroom")
    for (x, y, z) in list(cv.v):
        if _in_box((x, y, z), tunnel) and y == tunnel[1] and cv.v[(x, y, z)][1] == 1 \
                and cv.owner.get((x, y, z)) in ("plaza", "fill_light", "sidewalk"):
            cv.drop(x, y, z)                    # the floor paving stops at the tunnel's own floor
            count("floor writes left out of the tunnel mouth")
            continue
        if _in_box((x, y, z), tunnel) or _in_box((x, y, z), plaza):
            raise CityError("the city writes %s into Victory Road's keep-clear at %s" % (cv.v[(x, y, z)][0], (x, y, z)))
        for bx in reserved_boxes:
            if _in_box((x, y, z), bx):
                raise CityError("the city writes into a reserved volume at %s" % ((x, y, z),))
    for (x, y, z) in list(cv.v):
        if (x, y, z) in M["L1"]:
            b = cv.v[(x, y, z)][0]
            if not P.level(b):
                cv.drop(x, y, z)
    # checks for verify: a sample of everything written
    for (x, y, z), (b, ph) in cv.v.items():
        if unit(x, y, z, 91) < 0.002:
            checks.append((x, y, z, [b.split("{")[0]], "block"))
    kinds = {}
    for lot in lots:
        kinds[lot.district] = kinds.get(lot.district, 0) + 1
    plan.update({"counts": counts, "checks": checks, "rooms": sorted(rooms_out, key=lambda r: r["id"]),
                 "buildings": kinds, "lots": [{"id": l_.id, "district": l_.district, "level": l_.level, "kind": l_.kind,
                                               "room": l_.room["id"] if l_.room else None, "columns": len(l_.cols),
                                               "door": list(l_.door) if l_.door else None,
                                               "ladder": list(l_.ladder[:2]) if l_.ladder else None}
                                              for l_ in lots]})
    return cv, plan, services, spec


def _outward_wall(ci, cj, what):
    """The 7x7 shaft's wall cell on the outward side of a ring cell of its stair (build_tower's exits use the same
    rule): a ring cell lies on the 5x5 perimeter, so at least one side is the wall, and a corner takes the i side."""
    if ci == 0:
        return -1, cj
    if ci == 4:
        return 5, cj
    if cj == 0:
        return ci, -1
    if cj == 4:
        return ci, 5
    raise CityError("%s: %s is not on the stair's ring" % (what, (ci, cj)))


def arena_plan(cv, P, ar, spec, scx, scz, g0, rad, decks, crown, beacon_base, spire_tower, count, checks):
    """Heaven's Arena's tiers as a record of geometry: for every tier, the opening its stair arrives by and one 3x3
    cell across the floor from it, reserved and checked clear. No trainer, no yaw, no ladder: the fights are a
    separate system and are not built (data/deep_city.json arena.not_built)."""
    w = frame(spire_tower["anchor"], spire_tower["back"])
    cells = ring_cells()
    orbit = int(ar["stand_orbit"])
    cw, ch = (int(v) for v in ar["stand_clear"])
    half = cw // 2
    inner, outer = (ar["core"] + 1) // 2, rad - 1
    tiers = []
    for n, y in enumerate(decks, 1):
        ci, cj = cells[(y - g0 - 1) % 16]
        wx, wz = w(*_outward_wall(ci, cj, "the arena's tier %d" % n))
        vx, vz = wx - scx, wz - scz
        L = math.hypot(vx, vz) or 1.0
        sx = scx - int(round(vx / L * orbit))
        sz = scz - int(round(vz / L * orbit))
        r = math.hypot(sx - scx, sz - scz)
        if not (inner <= r <= outer) or max(abs(sx - scx), abs(sz - scz)) <= ar["core"] // 2:
            raise CityError("the arena's tier %d stand at %s is off its annulus (r=%.1f, %d..%d)"
                            % (n, (sx, sz), r, inner, outer))
        for dx in range(-half, half + 1):
            for dz in range(-half, half + 1):
                if cv.get(sx + dx, y, sz + dz) is None:
                    raise CityError("the arena's tier %d stand has no floor under %s" % (n, (sx + dx, y, sz + dz)))
                for yy in range(y + 1, y + ch + 1):
                    b = cv.get(sx + dx, yy, sz + dz)
                    if b not in (None, "minecraft:air"):
                        raise CityError("the arena's tier %d stand is not clear: %s at %s"
                                        % (n, b, (sx + dx, yy, sz + dz)))
        tiers.append({"tier": n, "y": y, "door": [wx, y + 1, wz], "stand": [sx, y + 1, sz],
                      "clear": [sx - half, y + 1, sz - half, sx + half, y + ch, sz + half], "trainer": None})
        checks.append((sx, y, sz, [P("tread"), P("sea_lantern")], "arena tier floor"))
    count("Heaven's Arena: tiers", len(tiers))
    return {"name": ar["name"], "design": ar["design"], "site": ar["site"], "centre": [scx, scz], "radius": rad,
            "lobby": g0, "annulus": [inner, outer], "tiers": tiers, "crown": crown,
            "beacon": [scx, beacon_base + 1, scz], "lift": ar["lift"],
            "buildings_displaced": 0, "stair_towers_displaced": 0,
            "fights": "not built: geometry only. Every tier's stand is a reserved and checked-clear 3x3 cell with no "
                      "trainer, no yaw, no faces, no eye_contact and no sight_distance "
                      "(docs/research/notes/rct-arena-capabilities.md; experiment A1 is unproven).",
            "not_built": ar["not_built"]}


def plan_service_cols(services):
    out = set()
    for s in services:
        x0, _y0, z0, x1, _y1, z1 = s["box"]
        out |= {(x, z) for x in range(x0 - 1, x1 + 2) for z in range(z0 - 1, z1 + 2)}
    return out


def _in_box(p, b):
    x, y, z = p
    return b[0] <= x <= b[3] and b[1] <= y <= b[4] and b[2] <= z <= b[5]


def _largest_component(sel):
    seen = np.zeros(sel.shape, bool)
    best = []
    zz, xx = np.nonzero(sel)
    for z0, x0 in zip(zz.tolist(), xx.tolist()):
        if seen[z0, x0]:
            continue
        comp = []
        q = deque([(z0, x0)])
        seen[z0, x0] = True
        while q:
            z, x = q.popleft()
            comp.append((z, x))
            for dx, dz in D4:
                a, b = z + dz, x + dx
                if 0 <= a < sel.shape[0] and 0 <= b < sel.shape[1] and sel[a, b] and not seen[a, b]:
                    seen[a, b] = True
                    q.append((a, b))
        if len(comp) > len(best):
            best = comp
    return best


def _largest_component_set(cols):
    cols = set(cols)
    best = set()
    seen = set()
    for c in sorted(cols):
        if c in seen:
            continue
        comp = set()
        q = deque([c])
        seen.add(c)
        while q:
            x, z = q.popleft()
            comp.add((x, z))
            for dx, dz in D4:
                n = (x + dx, z + dz)
                if n in cols and n not in seen:
                    seen.add(n)
                    q.append(n)
        if len(comp) > len(best):
            best = comp
    return best


def _edge_distance(rails, street):
    d = {c: 0 for c in rails}
    q = deque(rails)
    while q:
        c = q.popleft()
        if d[c] >= 4:
            continue
        for dx, dz in D4:
            n = (c[0] + dx, c[1] + dz)
            if n in street and n not in d and street[n] == street.get(c, street[n]):
                d[n] = d[c] + 1
                q.append(n)
    return d


def _feature(cv, P, kind, x, y, z):
    if kind == "stall":
        # a market stall: four copper posts, a canopy, a counter and a lamp under it
        for dx, dz in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            for h in (1, 2):
                cv.put(x + dx, y + h, z + dz, P("rib_teal"), owner="front")
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                cv.put(x + dx, y + 3, z + dz, "minecraft:waxed_oxidized_cut_copper_slab[type=bottom,waterlogged=false]",
                       owner="front")
        cv.put(x, y + 1, z, "minecraft:barrel[facing=up,open=false]", owner="front")
        cv.put(x, y + 2, z, "minecraft:lantern[hanging=false,waterlogged=false]", 2, owner="front", exterior=True)
    elif kind == "pylon":
        for h in range(1, 6):
            cv.put(x, y + h, z, P("sea_lantern") if h == 3 else P("rib_teal"), owner="front", exterior=h == 3)
        cv.put(x, y + 6, z, "minecraft:end_rod[facing=up]", 2, owner="front", exterior=True)
        for dx, dz in ((1, 0), (-1, 0)):
            cv.put(x + dx, y + 5, z + dz, "minecraft:chain[axis=x]", 2, owner="front")
    elif kind == "bench":
        cv.put(x - 1, y + 1, z, stair("minecraft:waxed_cut_copper_stairs", "north"), owner="front")
        cv.put(x + 1, y + 1, z, stair("minecraft:waxed_cut_copper_stairs", "north"), owner="front")
        cv.put(x, y + 1, z, P("rib_teal"), owner="front")
        cv.put(x, y + 2, z, P("rib_teal"), owner="front")
        cv.put(x, y + 3, z, P("bulb"), owner="front", exterior=True)
    elif kind == "mast":
        cv.put(x, y + 1, z, P("violet"), owner="front", exterior=True)
        for h in range(2, 7):
            cv.put(x, y + h, z, P("bars"), 2, owner="front")
        cv.put(x, y + 7, z, "minecraft:end_rod[facing=up]", 2, owner="front", exterior=True)


class LightModel:
    """Block light one above every walk cell, modelled from the emitters by manhattan distance and no occlusion."""

    def __init__(self, walk, X0, Z0, shape):
        self.walk = walk
        self.X0, self.Z0 = X0, Z0
        self.levels = sorted({y for y, _t in walk.values()})
        self.grid = {y: np.zeros(shape, np.int8) for y in self.levels}
        self.shape = shape
        self.k = {}

    def _kernel(self, r):
        if r not in self.k:
            a = np.arange(-r, r + 1)
            self.k[r] = r - (np.abs(a)[None, :] + np.abs(a)[:, None])
        return self.k[r]

    def stamp(self, x, y, z, lvl):
        for wy in self.levels:
            dy = abs((wy + 1) - y)
            r = lvl - 1 - dy
            if r < 0:
                continue
            k = self._kernel(r) + 1
            a, b = z - self.Z0, x - self.X0
            z0, z1 = max(0, a - r), min(self.shape[0], a + r + 1)
            x0, x1 = max(0, b - r), min(self.shape[1], b + r + 1)
            if z0 >= z1 or x0 >= x1:
                continue
            sub = k[z0 - (a - r):z1 - (a - r), x0 - (b - r):x1 - (b - r)]
            g = self.grid[wy]
            np.maximum(g[z0:z1, x0:x1], sub.astype(np.int8), out=g[z0:z1, x0:x1])

    def at(self, c):
        y, _t = self.walk[c]
        a, b = c[1] - self.Z0, c[0] - self.X0
        if not (0 <= a < self.shape[0] and 0 <= b < self.shape[1]):
            return 0
        return int(self.grid[y][a, b])

    def summary(self):
        out = {}
        for c, (y, tgt) in self.walk.items():
            v = self.at(c)
            key = "target %d" % tgt
            s = out.setdefault(key, {"cells": 0, "met": 0, "under_8": 0, "zero": 0})
            s["cells"] += 1
            s["met"] += v >= tgt
            s["under_8"] += v < 8
            s["zero"] += v == 0
        return out


# ------------------------------------------------------------------ the relic area

def build_relic(cv, P, spec, source_root, count, checks):
    import ground as G
    import rift_deep as RD
    rs = spec["relic_area"]
    m, (RX0, RZ0, RX1, RZ1), _n = RD.region_mask(rs["region"], source_root)
    g = G.load(source_root)
    H = g.box(RX0, RZ0, RX1, RZ1)

    def inr(x, z):
        a, b = z - RZ0, x - RX0
        return 0 <= a < m.shape[0] and 0 <= b < m.shape[1] and bool(m[a, b])

    def gr(x, z):
        return int(H[z - RZ0, x - RX0])

    out = {"reserved_below": [r["id"] for r in spec["reserved"] if r["id"] == "hoopa_cradle"]}
    own = "relic"
    # THE RELIC SITE IS UNDERGROUND (the owner, 2026-10-01; data/relic_underground.json, RELIC_UNDERGROUND.md).
    # The shrine platform, the six ring arches, the plinth and its ring, the standing stones, the processional way
    # and the Compact's cordon are NOT BUILT here any more: the first five stand in the hall under this ground
    # (tools/relic_underground.py), and the cordon is replaced by that file's zone check. This surface keeps only the
    # Compact's cap: the sealed entrance, the lookout and the dig (data/deep_city.json relic_area.capped).
    # The shrine's disc, the way and the stones' footprints are still COMPUTED, writing nothing, because the dig's
    # placement is keyed to them (`keep` below): the dig the world already holds must not move when this is rebuilt.
    # What the old build left in a world is taken off by R9RU's undo (tools/relic_underground.py), not by this file.
    sh = rs["shrine"]
    scx, scz = sh["centre"]
    rad = sh["radius"]
    disc = [(x, z) for x in range(scx - rad, scx + rad + 1) for z in range(scz - rad, scz + rad + 1)
            if math.hypot(x - scx, z - scz) <= rad + 0.5 and inr(x, z)]
    base = int(np.median([gr(x, z) for x, z in disc]))
    out["shrine"] = {"centre": [scx, scz], "radius": rad, "base": base, "built": False,
                     "moved_to": "data/relic_underground.json"}
    # the sealed entrance: a sunken forecourt down to a doorway walled with reinforced deepslate behind bars
    se = rs["sealed_entrance"]
    ex, ez = se["at"]
    f = DIR[se["facing"]]
    if f != (1, 0):
        raise CityError("the sealed entrance is drawn facing east only")
    depth = se["depth"]
    gb = int(np.median([gr(x, z) for x in range(ex, ex + 10) for z in range(ez - 3, ez + 4) if inr(x, z)]))
    yf = gb - depth
    for x in range(ex, ex + 10):
        for z in range(ez - 3, ez + 4):
            if not inr(x, z):
                raise CityError("the sealed entrance's forecourt leaves the relic area at %s" % ((x, z),))
            wall = z in (ez - 3, ez + 3) or x == ex
            step = max(0, min(depth, x - (ex + 5)))           # the stair rises eastward out of the forecourt
            fy = yf + step
            gy = gr(x, z)
            if wall:
                for y in range(yf, max(gy, gb) + 2):
                    cv.put(x, y, z, P("ancient_stone"), owner=own)
                continue
            cv.put(x, fy, z, "minecraft:polished_tuff" if step == 0 else stair("minecraft:tuff_brick_stairs", "east"),
                   owner=own)
            for y in range(fy + 1, max(gy, gb) + 2):
                cv.put(x, y, z, "minecraft:air", owner=own)
    # the doorway in the west wall: crying obsidian frame, reinforced deepslate seal, iron bars in front
    for z in range(ez - 2, ez + 3):
        for y in range(yf + 1, yf + 6):
            frame_ = z in (ez - 2, ez + 2) or y == yf + 5
            cv.put(ex, y, z, P("rift_seep") if frame_ else P("seal"), owner=own, exterior=frame_)
            if not frame_:
                cv.put(ex + 1, y, z, P("bars"), 2, owner=own)
    for z in (ez - 2, ez + 2):
        cv.put(ex + 1, yf + 4, z, "minecraft:end_rod[facing=up]", 2, owner=own, exterior=True)
    out["sealed_entrance"] = {"door": [ex, yf + 1, ez], "seal": [ex, yf + 1, ez - 1, ex, yf + 4, ez + 1],
                              "forecourt_floor": yf, "facing": "east",
                              "behind": "rock, uncarved: the cavern below stays sealed (reserved hoopa_cradle)"}
    checks.append((ex, yf + 2, ez, [P("seal")], "relic seal"))
    count("relic sealed entrance")
    # the lookout over the Deep
    lx, lz = rs["lookout"]["at"]
    look = [(x, z) for x in range(lx - 2, lx + 3) for z in range(lz - 2, lz + 3) if inr(x, z)]
    ly = max(gr(x, z) for x, z in look)
    for x, z in look:
        for y in range(gr(x, z) + 1, ly + 1):
            cv.put(x, y, z, P("ancient_stone"), owner=own)
        cv.put(x, ly, z, "minecraft:polished_tuff", owner=own)
        if x == lx + 2 or abs(z - lz) == 2:
            cv.put(x, ly + 1, z, P("rail"), 2, owner=own)
    cv.put(lx, ly + 1, lz, "minecraft:lantern[hanging=false,waterlogged=false]", 2, owner=own, exterior=True)
    out["lookout"] = [lx, ly, lz]
    # the processional way's and the standing stones' footprints: computed, NOT BUILT (see the top of this function).
    # The shrine they served is underground; the dig below keeps clear of where they stood, exactly as it always has
    way = set()
    for x in range(scx + rad, lx - 2):
        for z in (lz - 1, lz, lz + 1):
            zc = round(scz + (lz - scz) * (x - scx - rad) / max(1, lx - 2 - scx - rad)) + (z - lz)
            if inr(x, zc):
                way.add((x, zc))
    stn = rs["stones"]
    stones = []
    for k in range(stn["count"]):
        a = math.radians(22.5 + k * 360.0 / stn["count"])
        sx_, sz_ = int(round(scx + stn["orbit"] * math.sin(a))), int(round(scz - stn["orbit"] * math.cos(a)))
        fp = [(sx_ + dx, sz_ + dz) for dx in (0, 1) for dz in (0, 1)]
        if not all(inr(*p) for p in fp) or any(p in way for p in fp):
            continue
        stones.append({"at": [sx_, sz_]})
    out["not_built"] = {"why": "the relic site is underground (data/relic_underground.json); R9RU takes the old "
                               "surface build off a world that has it",
                        "elements": ["shrine platform", "six ring arches", "plinth and relic ring", "standing stones",
                                     "processional way", "the Compact cordon"]}
    # the Compact's dig: trenches, spoil heaps, fallen fragments, crates, survey stakes
    keep = {(x, z) for x, z in disc} | {(x, z) for x in range(ex - 1, ex + 11) for z in range(ez - 4, ez + 5)} | set(look)
    keep |= way | {(s["at"][0] + dx, s["at"][1] + dz) for s in stones for dx in range(-2, 10) for dz in range(-2, 10)}
    cells = sorted((x, z) for x in range(RX0, RX1 + 1) for z in range(RZ0, RZ1 + 1) if inr(x, z)
                   and math.hypot(x - scx, z - scz) > rad + 4)
    rng = sorted(cells, key=lambda c: hsh(c[0], 0, c[1], 17))
    deb = rs["debris"]
    placed = {"trenches": 0, "heaps": 0, "fragments": 0}
    used = set()

    def free(fp):
        return all(inr(x, z) and (x, z) not in keep and (x, z) not in used for x, z in fp)

    all_cells = [(x, z) for x in range(RX0, RX1 + 1) for z in range(RZ0, RZ1 + 1) if inr(x, z)]
    boundary = {(x, z) for x, z in all_cells if any(not inr(x + dx, z + dz) for dx, dz in D4)}
    near_edge = {(x + dx, z + dz) for x, z in boundary for dx in range(-4, 5) for dz in range(-4, 5)
                 if abs(dx) + abs(dz) < 4}
    for c in rng:
        if all(placed[k] >= deb[k] for k in placed):
            break
        x, z = c
        if c in near_edge:
            continue
        roll = hsh(x, 1, z, 19) % 3
        if roll == 0 and placed["trenches"] < deb["trenches"]:
            along = hsh(x, 2, z, 19) % 2
            fp = [(x + (i if along else j), z + (j if along else i)) for i in range(0, 8) for j in range(0, 3)]
            if not free(fp) or max(gr(*p) for p in fp) - min(gr(*p) for p in fp) > 2:
                continue
            for p in fp:
                gy = gr(*p)
                cv.put(p[0], gy, p[1], "minecraft:air", owner=own)
                cv.put(p[0], gy - 1, p[1], "minecraft:air", owner=own)
                cv.put(p[0], gy - 2, p[1], "minecraft:coarse_dirt", owner=own)
            px_, pz_ = fp[0]
            cv.put(px_, gr(px_, pz_) + 1, pz_, P("rib_teal"), owner=own)
            cv.put(px_, gr(px_, pz_) + 2, pz_, "minecraft:end_rod[facing=up]", 2, owner=own, exterior=True)
            used |= {(p[0] + dx, p[1] + dz) for p in fp for dx in (-2, -1, 0, 1, 2) for dz in (-2, -1, 0, 1, 2)}
            placed["trenches"] += 1
        elif roll == 1 and placed["heaps"] < deb["heaps"]:
            fp = [(x + dx, z + dz) for dx in range(-2, 3) for dz in range(-2, 3) if abs(dx) + abs(dz) <= 3]
            if not free(fp):
                continue
            for p in fp:
                hgt = 3 - (abs(p[0] - x) + abs(p[1] - z))
                gy = gr(*p)
                for y in range(gy + 1, gy + max(1, hgt) + 1):
                    b = ("minecraft:gravel", "minecraft:cobbled_deepslate", "minecraft:tuff")[hsh(p[0], y, p[1], 23) % 3]
                    cv.put(p[0], y, p[1], b, owner=own)
            if hsh(x, 3, z, 19) % 2 == 0 and free([(x + 3, z)]):
                cv.put(x + 3, gr(x + 3, z) + 1, z, "minecraft:barrel[facing=up,open=false]", owner=own)
            used |= {(p[0] + dx, p[1] + dz) for p in fp for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
            placed["heaps"] += 1
        elif roll == 2 and placed["fragments"] < deb["fragments"]:
            fp = [(x + dx, z) for dx in range(-2, 3)]
            if not free(fp):
                continue
            for i, p in enumerate(fp):
                gy = gr(*p)
                lift = 1 if i in (1, 2, 3) else 0
                cv.put(p[0], gy + lift, p[1], P("hoopa_gold"), owner=own)
                if lift:
                    cv.put(p[0], gy, p[1], P("hoopa_gold"), owner=own)
            used |= {(p[0] + dx, p[1] + dz) for p in fp for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
            placed["fragments"] += 1
    out["debris"] = placed
    for k_, v_ in placed.items():
        count("relic %s" % k_, v_)
    # no cordon: the owner rejected the fence (2026-10-01, "turned back by the zone check rather than barriers"). The
    # zone check is data/relic_underground.json's, and it is underground; the relic area's surface is open ground
    return out


# regions_seed() and _ring_voxels() served only the cordon and the ring arches; they moved with the superseded surface
# build to tools/relic_surface_superseded.py, verbatim, where R9RU's undo derives what to take off a world.


# ------------------------------------------------------------------ writing the pack

def emit(cv, services, plan):
    if OUT.exists():
        shutil.rmtree(OUT)
    fn = OUT / "data" / "cobblers" / "function" / FOLDER
    fn.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                                          "Cobblers: the Windward Deep's city and the relic area (tools/deep_city.py)"}},
                                                indent=2) + "\n", encoding="utf-8")
    order = []
    ncmd = 0
    for phase in (1, 2):
        tiles = {}
        for (x, y, z), (b, ph) in cv.v.items():
            if ph == phase:
                tiles.setdefault((x // TILE, z // TILE), {})[(x, y, z)] = b
        for t in sorted(tiles):
            body = _compress(tiles[t])
            for k in range(0, len(body), PART):
                name = "p%d_%d_%d%s" % (phase, t[0], t[1], "" if k == 0 else "_%d" % (k // PART + 1))
                out = FL.ensure_loaded(["# Generated by tools/deep_city.py: phase %d, tile %d %d" % ((phase,) + t)] + body[k:k + PART])
                probs = FL.check_lines(out, name)
                if probs:
                    raise CityError("function %s would be refused: %s" % (name, probs[:3]))
                (fn / (name + ".mcfunction")).write_text("\n".join(out) + "\n", encoding="utf-8")
                order.append(name)
                ncmd += len(body[k:k + PART])
        if phase == 1:
            # the Centre and Mart go down after the structure and before the fixtures
            lines = ["# Generated by tools/deep_city.py: the Centre and Mart on Rimside"]
            import place_town as PT
            for s in services:
                src = ROOT / s["file"]
                ns, path_ = s["template"].split(":")
                dest = OUT / "data" / ns / "structure" / (path_ + ".nbt")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
                info = PT.template_info(src)
                x0, y0, z0, x1, y1, z1 = s["box"]
                mnx, mnz, fw, fd = PT.footprint(info["size"], s["rotation"])
                px, pz = x0 - mnx, z0 - mnz
                oy = y0 - info["grade_layer"]
                lines.append("place template %s %d %d %d %s none 1.0 0" % (s["template"], px, oy, pz, s["rotation"]))
                for (jx, jy, jz), final, _o in info["jigsaws"]:
                    rx, rz = PT.rotate(jx, jz, s["rotation"])
                    state = final if final != "minecraft:structure_void" else "minecraft:air"
                    lines.append("setblock %d %d %d %s" % (px + rx, oy + jy, pz + rz, state))
                for (lx, ly, lz) in info["loot"]:
                    rx, rz = PT.rotate(lx, lz, s["rotation"])
                    lines.append("data remove block %d %d %d LootTable" % (px + rx, oy + ly, pz + rz))
                lines.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:flowers" % (x0, y0, z0, x1, y1, z1))
            out = FL.ensure_loaded(lines)
            probs = FL.check_lines(out, "services")
            if probs:
                raise CityError("function services would be refused: %s" % probs[:3])
            (fn / "services.mcfunction").write_text("\n".join(out) + "\n", encoding="utf-8")
            order.append("services")
            ncmd += len(lines) - 1
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    plan = dict(plan)
    plan["functions"] = order
    plan["commands"] = ncmd
    PLAN.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    return order, ncmd


def _compress(vox):
    """Runs along x at each (y, z) of one block, then identical runs stacked in y: fewer commands than blocks."""
    rows = {}
    for (x, y, z), b in vox.items():
        rows.setdefault((b, y, z), []).append(x)
    runs = {}
    for (b, y, z), xs in rows.items():
        xs.sort()
        s = p = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == p + 1:
                p = x
                continue
            runs.setdefault((b, z, s, p), []).append(y)
            if x is not None:
                s = p = x
    out = []
    for (b, z, x0, x1), ys in sorted(runs.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        ys.sort()
        s = p = ys[0]
        for y in ys[1:] + [None]:
            if y is not None and y == p + 1:
                p = y
                continue
            if x0 == x1 and s == p:
                out.append("setblock %d %d %d %s" % (x0, s, z, b))
            else:
                out.append("fill %d %d %d %d %d %d %s" % (x0, s, z, x1, p, z, b))
            if y is not None:
                s = p = y
    return out


# ------------------------------------------------------------------ checking a world

def verify(world):
    import build_audit
    import runtime_guard
    runtime_guard.check(world, "read")
    if not PLAN.is_file():
        print("FAIL: no derived/deep_city/plan.json: run the build first")
        return 1
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    kinds = {c[4] for c in p["checks"]}
    # no "relic ring": the ring is underground (tools/relic_underground.py) and its own verify checks it
    need = {"lift landing roof", "tower core", "spire beacon", "relic seal", "block"}
    if not need <= kinds:
        print("FAIL: the plan checks %s, missing %s" % (sorted(kinds), sorted(need - kinds)))
        return 1
    W = build_audit.World(world)
    by, bad = {}, {}
    for x, y, z, allowed, what in p["checks"]:
        got = W.block(x, y, z)
        ok = got in [a.split("[")[0] for a in allowed]
        by.setdefault(what, [0, 0])[0 if ok else 1] += 1
        if not ok:
            bad.setdefault(what, []).append((x, y, z, got))
    for k in sorted(by):
        good, wrong = by[k]
        print("%-18s %6d of %6d as planned%s" % (k, good, good + wrong, ("   e.g. %s" % bad[k][:2]) if wrong else ""))
    total = sum(b for _, b in by.values())
    print("the Deep's city: %s" % ("clean" if total == 0 else "%d MISMATCHES" % total))
    return 0 if total == 0 else 1


def rooms():
    if not PLAN.is_file():
        print("no derived/deep_city/plan.json: run the build first")
        return 1
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    for r in p["rooms"]:
        print("%-22s %-10s box %-38s door %-20s %s" % (r["id"], r["district"], r["box"], r.get("door"),
                                                      "SEALED" if r.get("sealed") else ""))
    for r in p["reserved"]:
        print("%-22s reserved   box %s" % (r["id"], r["box"]))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "verify", "rooms"))
    ap.add_argument("--source-root")
    ap.add_argument("--server-dir")
    ap.add_argument("--world")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        if not a.world:
            ap.error("verify needs --world")
        return verify(a.world)
    if a.cmd == "rooms":
        return rooms()
    import os
    src = a.source_root or env_source_root()
    cv, plan, services, spec = build(src, a.server_dir)
    order, ncmd = emit(cv, services, plan)
    for k, v in sorted(plan["counts"].items()):
        print("  %-48s %9d" % (k, v))
    print("  %-48s %9d" % ("blocks written", len(cv.v)))
    for k, v in plan["light"]["after_fill"].items():
        print("  light, %-40s %d of %d cells met (%d under 8)" % (k, v["met"], v["cells"], v["under_8"]))
    print("the Deep's city: %d functions, %d commands" % (len(order), ncmd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
