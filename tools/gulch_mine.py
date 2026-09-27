#!/usr/bin/env python
"""The southern Rift's mega site, prototype slice, from data/gulch_mine.json (docs/world-building/SOUTHERN_RIFT_MEGA.md
section 10 and the owner's twelve decisions of 2026-09-27, section 11).

What it builds, all from the data file and the canonical heightmap (tools/ground.py, rounded; never a world):

  the gate     the Gulch lookout's rockfall across the sculpt's gulch_mouth gap (data `gate.band`, traced from the
               sculpt's lip ring by `trace`), a plug with the company's grille in the middle, a graded road through it,
               and the advancements: knock (a player holding cobblers:flag/gym6_cleared is put through), exit, the
               Mining Fatigue ward round the plug, and the zone check over the whole gulch zone (data `zone.polygon`)
  the town     the 61-square at (4308, 4848) paved and dressed, a yard cut into the slope south of it with the Cutters'
               workshop, a bunkhouse, the assay counter and the adit head; three Cutter villagers (vanilla trades:
               4 raw mega stone + 1 diamond -> one keyed stone, unlimited, nothing bought)
  the mine     the Cutters' adit, the Tally Hall (lit) and the Cutting Floor (dark) as caverns at real scale, joined by
               a drift; a shell of rock round everything carved, so nothing this build opens meets a natural void
  the faces    two crystal faces in the Cutting Floor, each a 7 x 5 x 7 box of meteorid holding 3 mega_stone_crystal,
               restored on approach every 30 minutes by the pack's own tick driver (STONE_ECONOMY.md 5.3: filtered
               fill, guarded setblocks, both corners loaded, nobody and no Pokemon in the box)
  the Megas    two roaming Megas for the Cutting Floor, spawned by the keeper (spawnpokemonat ... uncatchable), tagged,
               leashed like the recovery guardians, owed again when a face of their hall restores after they fainted
  the floor    four raw stones, once per player, on first reaching the Tally Hall (an advancement)

  python tools/gulch_mine.py trace  [--source-root DIR]   the ring-derived geometry (band, zone polygon) as JSON, for
                                                          authoring data/gulch_mine.json; nothing written
  python tools/gulch_mine.py report [--source-root DIR]   the model's checks and counts; nothing written
  python tools/gulch_mine.py build  [--source-root DIR]   -> build/datapacks/cobblers_gulch_mine, derived/gulch_mine/plan.json

The offline audit, independent of this tool's model, is tools/gulch_mine_audit.py. Recipes raised to 4 raw stones are
tools/mega_recipes.py's (generated from the local jar, never committed).
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402
import rift_mines as RM        # noqa: E402  (the tube rasteriser, hashing and run-length helpers; not its model)

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "gulch_mine.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_gulch_mine"
PLAN = ROOT / "derived" / "gulch_mine" / "plan.json"
SCULPT_PLAN = ROOT / "derived" / "rift_sculpt" / "plan.json"
NS = "cobblers"
FOLDER = "gulch_mine"
TILE = 64
PART = 3500
PASSES = ("earth", "shell", "air", "fittings", "surface", "faces")
AIR = "minecraft:air"
SHELL_R = 2
LANTERN_HANG = "minecraft:lantern[hanging=true,waterlogged=false]"
LANTERN_STAND = "minecraft:lantern[hanging=false,waterlogged=false]"
SOFT = ("lantern", "crystal", "chain", "iron_bars", "door", "campfire", "trapdoor", "rail")
PASSABLE = ("lantern", "door", "chain", "rail", "carpet")

rnd, h32, u, pick = RM.rnd, RM.h32, RM.u, RM.pick


class GulchError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ rasterising, in the words of the data's `geometry`

def hall_phases(seed, hid):
    """Three phases for a hall's ragged outline: phase_k = h32(seed, len(id), sum of the id's code points, k) / 2^32
    turns (data geometry.hall)."""
    key = sum(ord(c) for c in hid)
    return [h32(seed, len(hid), key, k) / 4294967296.0 * 2 * math.pi for k in range(3)]


def hall_columns(h, seed):
    """{(x, z): (feet, top)} for a hall, as data/gulch_mine.json geometry.hall says."""
    cx, cz = h["centre"]
    R, rag, feet0, bowl, height = h["radius"], h["ragged"], h["feet"], h["bowl"], h["height"]
    ph = hall_phases(seed, h["id"])
    out = {}
    reach = int(math.ceil(R * (1 + rag) + 1))
    for x in range(cx - reach, cx + reach + 1):
        for z in range(cz - reach, cz + reach + 1):
            dx, dz = x - cx, z - cz
            d = math.hypot(dx, dz)
            th = math.atan2(dz, dx)
            n = 0.5 * math.sin(3 * th + ph[0]) + 0.3 * math.sin(5 * th + ph[1]) + 0.2 * math.sin(7 * th + ph[2])
            Rt = R * (1 + rag * n) + 0.5
            if d > Rt:
                continue
            q = d / Rt
            feet = feet0 + int(math.floor(bowl * q * q + 0.5))
            top = max(feet + 3, feet0 + int(math.floor(height * math.sqrt(max(0.0, 1 - q * q)) + 0.5)))
            out[(x, z)] = (feet, top)
    return out


def road_columns(road):
    """{(x, z): surface y} for the graded road (geometry.road)."""
    best = {}
    half = road["half"]
    pts = road["path"]
    for (x0, z0, y0), (x1, z1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, z1 - z0)
        n = int(math.ceil(4 * L)) + 1 if L > 0 else 1
        for s in range(n):
            t = s / (n - 1) if n > 1 else 0.0
            px, pz, py = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, y0 + (y1 - y0) * t
            cx, cz = rnd(px), rnd(pz)
            for dx in range(-half, half + 1):
                for dz in range(-half, half + 1):
                    c = (cx + dx, cz + dz)
                    dd = (c[0] - px) ** 2 + (c[1] - pz) ** 2
                    if c not in best or dd < best[c][0]:
                        best[c] = (dd, rnd(py))
    return {c: v[1] for c, v in best.items()}


def band_columns(band):
    """{(x, z): j} for the rockfall: each listed ring point claims the columns within 1 (Chebyshev) of its point moved
    d = -1, 0, 1 along its inward normal; the first point in list order that claims a column keeps it."""
    out = {}
    for p in band["points"]:
        j, x, z, nx, nz = p
        for d in (-1, 0, 1):
            cx, cz = rnd(x + nx * d), rnd(z + nz * d)
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    out.setdefault((cx + a, cz + b), j)
    return out


def point_in(poly, px, pz):
    c = False
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        if (z0 > pz) != (z1 > pz):
            xi = x0 + (pz - z0) * (x1 - x0) / (z1 - z0)
            if px < xi:
                c = not c
    return c


def zone_boxes(poly):
    """The zone polygon as boxes of columns: a column is in when its centre is inside (even-odd); each z row's runs are
    merged down the rows while identical. [(x0, z0, x1, z1)]."""
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    X0, X1, Z0, Z1 = int(math.floor(min(xs))) - 1, int(math.ceil(max(xs))) + 1, int(math.floor(min(zs))) - 1, int(math.ceil(max(zs))) + 1
    boxes, open_ = [], {}
    for z in range(Z0, Z1 + 2):
        row = set()
        start = None
        for x in range(X0, X1 + 2):
            ins = x <= X1 and z <= Z1 and point_in(poly, x + 0.5, z + 0.5)
            if ins and start is None:
                start = x
            if not ins and start is not None:
                row.add((start, x - 1))
                start = None
        for r in list(open_):
            if r not in row:
                boxes.append((r[0], open_[r], r[1], z - 1))
                del open_[r]
        for r in row:
            if r not in open_:
                open_[r] = z
    return sorted(boxes, key=lambda b: (b[1], b[0]))


# ------------------------------------------------------------------ the model

class Model:
    def __init__(self, spec, ground):
        self.spec = spec
        gx, gz, gy = spec["grid"]["x"], spec["grid"]["z"], spec["grid"]["y"]
        self.X0, self.X1, self.Z0, self.Z1, self.Y0, self.Y1 = gx[0], gx[1], gz[0], gz[1], gy[0], gy[1]
        self.nx, self.nz, self.ny = self.X1 - self.X0 + 1, self.Z1 - self.Z0 + 1, self.Y1 - self.Y0 + 1
        self.S0 = ground.box(self.X0, self.Z0, self.X1, self.Z1).T.copy()
        shape = (self.nx, self.nz, self.ny)
        self.env = np.zeros(shape, bool)          # carved underground space (halls, tubes)
        self.own = np.full(shape, -1, np.int16)
        self.protect = np.zeros(shape, bool)      # face boxes: never carved, written by the faces pass
        self.carve = None
        self.feats = []
        self.surface = {}                         # (x, z) -> surface y of an earthwork column (plaza, yard, road)
        self.earth_kind = {}                      # (x, z) -> earthwork id
        self.hall_cols = {}                       # hall id -> {(x, z): (feet, top)}
        self.blocks, self.fit, self.surf, self.earth, self.faces = {}, {}, {}, {}, {}
        self.counts = {}

    def ix(self, x, y, z):
        return x - self.X0, z - self.Z0, y - self.Y0

    def inside(self, x, y, z):
        return self.X0 <= x <= self.X1 and self.Z0 <= z <= self.Z1 and self.Y0 <= y <= self.Y1

    def ground(self, x, z):
        return int(self.S0[x - self.X0, z - self.Z0])

    def top(self, x, z):
        """The walkable top block of a column: an earthwork's surface where there is one, else the ground."""
        return self.surface.get((x, z), self.ground(x, z))

    def is_carved(self, x, y, z):
        return self.inside(x, y, z) and bool(self.carve[self.ix(x, y, z)])

    def mark(self, x, y, z, fid):
        if not self.inside(x, y, z):
            raise GulchError("%s reaches (%d, %d, %d), outside the grid %s" % (self.feats[fid]["id"], x, y, z, self.spec["grid"]))
        i, k, j = self.ix(x, y, z)
        self.env[i, k, j] = True
        if self.own[i, k, j] < 0:
            self.own[i, k, j] = fid


def earthworks(m):
    """The plaza, the yard cut and the road: each column's surface level (data `town.square`, `town.yard`, `gate.road`)."""
    t = m.spec["town"]
    sq = t["square"]
    x0, z0, x1, z1 = sq["rect"]
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            m.surface[(x, z)] = sq["surface_y"]
            m.earth_kind[(x, z)] = "square"
    yd = t["yard"]
    x0, z0, x1, z1 = yd["rect"]
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if (x, z) not in m.surface:
                m.surface[(x, z)] = yd["surface_y"]
                m.earth_kind[(x, z)] = "yard"
    for c, y in road_columns(m.spec["gate"]["road"]).items():
        if c not in m.surface:
            m.surface[c] = y
            m.earth_kind[c] = "road"
    for (x, z), y in m.surface.items():
        if not (m.X0 <= x <= m.X1 and m.Z0 <= z <= m.Z1):
            raise GulchError("earthwork column (%d, %d) outside the grid" % (x, z))


def rasterise(m):
    spec = m.spec
    seed = spec["seed"]
    for h in spec["mine"]["halls"]:
        fid = len(m.feats)
        m.feats.append({"id": h["id"], "kind": "hall", "rec": h})
        cols = hall_columns(h, seed)
        m.hall_cols[h["id"]] = cols
        for (x, z), (feet, top) in cols.items():
            for y in range(feet, top + 1):
                m.mark(x, y, z, fid)
    for d in spec["mine"]["drifts"]:
        fid = len(m.feats)
        m.feats.append({"id": d["id"], "kind": "tube", "rec": d})
        for c in RM.tube_cells(d["path"], d["r"], d["height"]):
            m.mark(*c, fid)
    for f in spec["mine"]["faces"]:
        x0, y0, z0, x1, y1, z1 = f["box"]
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    if not m.inside(x, y, z):
                        raise GulchError("face %s leaves the grid" % f["id"])
                    m.protect[m.ix(x, y, z)] = True
    m.carve = m.env & ~m.protect


def shell(m):
    """Every cell within SHELL_R of the carved space or a face box, not carved, not a face box, at or under the top."""
    near = RM.dilate(m.env | m.protect, SHELL_R) & ~m.carve & ~m.protect
    tops = np.array([[m.top(i + m.X0, k + m.Z0) for k in range(m.nz)] for i in range(m.nx)])
    ys = np.arange(m.ny)[None, None, :] + m.Y0
    near &= ys <= tops[:, :, None]
    return near, tops


# ------------------------------------------------------------------ blocks

NEIGH6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def feat_of(m, x, y, z):
    if m.inside(x, y, z):
        i, k, j = m.ix(x, y, z)
        return int(m.own[i, k, j])
    return -1


def build_blocks(m, near):
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    for i, k, j in np.argwhere(near):
        x, y, z = int(i + m.X0), int(j + m.Y0), int(k + m.Z0)
        above = m.inside(x, y + 1, z) and m.carve[i, k, j + 1]
        if above:
            f = m.feats[feat_of(m, x, y + 1, z)]
            key = f["rec"].get("floor", "drift_floor")
            b = pick(pal[key], seed, x, y, z, 21)
        else:
            b = pick(pal["rock_lower"] if y < pal["rock_split_y"] else pal["rock_upper"], seed, x, y, z, 14)
            # meteorid in the Cutting Floor's walls: the seam the faces are cut from
            for dx, dy, dz in NEIGH6:
                fid = feat_of(m, x + dx, y + dy, z + dz)
                if fid >= 0 and m.is_carved(x + dx, y + dy, z + dz):
                    share = m.feats[fid]["rec"].get("meteorid_share", 0)
                    if share and u(seed, x, y, z, 31) < share:
                        b = pal["meteorid_radiated"] if u(seed, x, y, z, 33) < 0.3 else pal["meteorid"]
                    break
        m.blocks[(x, y, z)] = b


def feet_at(m, x, z, lo=None, hi=None):
    i, k = x - m.X0, z - m.Z0
    for j in np.nonzero(m.carve[i, k, :])[0]:
        y = int(j + m.Y0)
        if (lo is None or y >= lo) and (hi is None or y <= hi):
            return y
    return None


def ceiling_over(m, x, feet, z):
    y = feet
    while m.is_carved(x, y + 1, z):
        y += 1
    return y


def hang_lantern(m, x, feet, z, min_air=4):
    y = ceiling_over(m, x, feet, z)
    if y - feet >= min_air - 1 and (x, y, z) not in m.fit:
        m.fit[(x, y, z)] = LANTERN_HANG
        return True
    return False


def fittings(m):
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    n_light = 0
    for d in m.spec["mine"]["drifts"]:
        every = d.get("light_every")
        if not every:
            continue
        s_tot = 0.0
        for (x0, y0, z0), (x1, y1, z1) in zip(d["path"], d["path"][1:]):
            L = math.hypot(x1 - x0, z1 - z0)
            s = 2.0
            while s <= L - 1:
                if int(s_tot + s) % every == 0:
                    t = s / L
                    cx, cz, feet = rnd(x0 + (x1 - x0) * t), rnd(z0 + (z1 - z0) * t), rnd(y0 + (y1 - y0) * t)
                    f = feet_at(m, cx, cz, feet - 2, feet + 2)
                    if f is not None and hang_lantern(m, cx, f, cz):
                        n_light += 1
                s += 1.0
            s_tot += L
    for h in m.spec["mine"]["halls"]:
        cols = m.hall_cols[h["id"]]
        cx, cz = h["centre"]
        lit = h.get("light_every")
        if lit:
            for x in range(cx - 40, cx + 41, lit):
                for z in range(cz - 40, cz + 41, lit):
                    if (x, z) in cols:
                        feet, top = cols[(x, z)]
                        if top - feet >= 6 and m.is_carved(x, top, z) and not m.is_carved(x, top + 1, z):
                            m.fit[(x, top, z)] = LANTERN_HANG
                            n_light += 1
        for px, pz in h.get("pillars") or []:
            if (px, pz) not in cols:
                raise GulchError("hall %s: pillar (%d, %d) is outside the hall" % (h["id"], px, pz))
            feet, top = cols[(px, pz)]
            for y in range(feet, top + 1):
                if m.is_carved(px, y, pz):
                    m.fit[(px, y, pz)] = pal["post"] + "[axis=y]"
            m.fit[(px, top, pz)] = pal["beam"]
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if m.is_carved(px + dx, top, pz + dz):
                    m.fit[(px + dx, top, pz + dz)] = pal["beam"]
        for p in h.get("props") or []:
            x, z = p["at"]
            feet = feet_at(m, x, z)
            if feet is None:
                raise GulchError("hall %s: prop at (%d, %d) stands on nothing carved" % (h["id"], x, z))
            m.fit[(x, feet, z)] = p["block"]
    # the portal frame where the adit leaves the yard
    pf = m.spec["mine"]["portal"]
    (xa, za), (xb, zb), y0, y1 = pf["posts"][0], pf["posts"][1], pf["y"][0], pf["y"][1]
    for x, z in ((xa, za), (xb, zb)):
        for y in range(y0, y1 + 1):
            m.fit[(x, y, z)] = pal["post"] + "[axis=y]"
    for x in range(min(xa, xb), max(xa, xb) + 1):
        for z in range(min(za, zb), max(za, zb) + 1):
            m.fit[(x, y1 + 1, z)] = pal["beam"]
    m.counts["mine lanterns"] = n_light


def face_block(m, f, k):
    """{(x, y, z): block} for face `f`'s variant k: the host everywhere, radiated meteorid in `radiated` cells, and the
    crystals: one on the front plane's bottom row, the rest hidden at least 2 deep (data geometry.face)."""
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    x0, y0, z0, x1, y1, z1 = f["box"]
    cells = [(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)]
    front = f["front"]
    axis, val = {"west": ("x", x0), "east": ("x", x1), "north": ("z", z0), "south": ("z", z1)}[front]

    def depth(c):
        return {"west": c[0] - x0, "east": x1 - c[0], "north": c[2] - z0, "south": z1 - c[2]}[front]
    fid = sum(ord(ch) for ch in f["id"])
    order = sorted(cells, key=lambda c: h32(seed, fid, k, c[0], c[1], c[2]))
    out = {}
    rad = [c for c in order if depth(c) <= 1][:f["radiated"]]
    for c in rad:
        out[c] = pal["meteorid_radiated"]
    visible = [c for c in order if depth(c) == 0 and c[1] == y0 and c not in out
               and not (c[0] in (x0, x1) and axis == "z") and not (c[2] in (z0, z1) and axis == "x")]
    hidden = [c for c in order if depth(c) >= 2 and c not in out and c[1] < y1]
    n = f["crystals"]
    if not visible or len(hidden) < n - 1:
        raise GulchError("face %s: no room for its crystals" % f["id"])
    crys = [visible[0]] + hidden[:n - 1]
    for c in crys:
        out[c] = "%s[facing=%s]" % (pal["mega_stone_crystal"], front if c == visible[0] else RM.FACINGS[h32(seed, c[0], c[2], 42) % 4])
    return out, crys


def surface_build(m):
    """The plaza, the yard's houses, the lamp posts, the rockfall and plug, the grille."""
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    t = m.spec["town"]
    # earthworks: fill under, surface block, air over
    for (x, z), ys in sorted(m.surface.items()):
        g = m.ground(x, z)
        kind = m.earth_kind[(x, z)]
        rec = t["square"] if kind == "square" else t["yard"] if kind == "yard" else m.spec["gate"]["road"]
        for y in range(g + 1, ys):
            m.earth[(x, y, z)] = pick(pal["fill"], seed, x, y, z, 71)
        m.earth[(x, ys, z)] = surface_block(m, kind, rec, x, z)
        clear = rec["clear_above"]
        for y in range(ys + 1, max(g, ys) + clear + 1):
            if not m.is_carved(x, y, z):
                m.earth[(x, y, z)] = AIR
    # the square's centre: the crystal case
    sq = t["square"]
    cx, cz = sq["centre"]
    y = sq["surface_y"]
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            corner = abs(dx) == 2 and abs(dz) == 2
            m.surf[(cx + dx, y + 1, cz + dz)] = pal["meteorid_chiseled"] if corner else pal["meteorid_polished"]
    m.surf[(cx, y + 2, cz)] = pal["meteorid_brick"]
    m.surf[(cx, y + 3, cz)] = pal["dormant_crystal"] + "[facing=up]"
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        m.surf[(cx + dx, y + 2, cz + dz)] = pal["meteorid_polished"]
        m.surf[(cx + dx, y + 3, cz + dz)] = "minecraft:glass"
    m.surf[(cx, y + 4, cz)] = "minecraft:glass"
    for x, z in t["lamp_posts"]:
        yy = m.top(x, z)
        m.surf[(x, yy + 1, z)] = "minecraft:cobbled_deepslate_wall"
        m.surf[(x, yy + 2, z)] = "minecraft:cobbled_deepslate_wall"
        m.surf[(x, yy + 3, z)] = LANTERN_STAND
    for hrec in t["houses"]:
        house(m, hrec)
    gate_build(m)


def surface_block(m, kind, rec, x, z):
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    if kind == "square":
        x0, z0, x1, z1 = rec["rect"]
        e = min(x - x0, x1 - x, z - z0, z1 - z)
        if e < rec["border"]:
            return pal["square_border"]
        if (x - x0) % rec["band_every"] == 0 or (z - z0) % rec["band_every"] == 0:
            return pal["square_band"]
        return pick(pal["square_field"], seed, x, z, 81)
    if kind == "yard":
        return pick(pal["yard_floor"], seed, x, z, 82)
    return pick(pal["road"], seed, x, z, 83)


ROLE_FITTINGS = {
    "cutting": ["minecraft:stonecutter[facing=north]", "minecraft:smithing_table", "minecraft:grindstone[face=floor,facing=north]",
                "minecraft:stonecutter[facing=north]", "minecraft:barrel[facing=up]", "minecraft:anvil[facing=east]",
                "minecraft:stonecutter[facing=north]", "minecraft:smithing_table", "minecraft:grindstone[face=floor,facing=north]",
                "minecraft:stonecutter[facing=north]", "minecraft:barrel[facing=up]", "minecraft:anvil[facing=east]",
                "minecraft:stonecutter[facing=north]", "minecraft:smithing_table", "minecraft:grindstone[face=floor,facing=north]",
                "minecraft:stonecutter[facing=north]", "minecraft:barrel[facing=up]", "minecraft:anvil[facing=east]",
                "minecraft:stonecutter[facing=north]", "minecraft:smithing_table", "minecraft:barrel[facing=up]"],
    "bunkhouse": ["minecraft:barrel[facing=up]", "minecraft:barrel[facing=up]", "minecraft:barrel[facing=up]",
                  "minecraft:polished_deepslate_slab[type=bottom,waterlogged=false]",
                  "minecraft:polished_deepslate_slab[type=bottom,waterlogged=false]"],
    "assay": ["minecraft:crafting_table", "minecraft:stonecutter[facing=north]", "minecraft:barrel[facing=up]",
              "minecraft:barrel[facing=up]", "minecraft:chest[facing=north,type=single,waterlogged=false]"],
}
DOOR = "minecraft:waxed_weathered_copper_door"


def house(m, hrec):
    """A rock house on the yard (tools/rift_mines.py's rock house, sized by the data): cobbled deepslate footing,
    masonry walls on basalt corners, iron-bar windows, a copper door, a deepslate tile roof with a parapet."""
    x0, z0, x1, z1 = hrec["rect"]
    cols = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    floor = max(m.top(x, z) for x, z in cols)
    low = min(m.top(x, z) for x, z in cols)
    H = hrec.get("wall_height", 5)
    wall = hrec["walls"]
    for x, z in cols:
        for y in range(low - 1, floor + 1):
            m.surf[(x, y, z)] = "minecraft:cobbled_deepslate"
        m.surf[(x, floor, z)] = "minecraft:polished_deepslate"
        for y in range(floor + 1, floor + H + 3):
            m.surf[(x, y, z)] = AIR
    top = floor + H
    for x, z in cols:
        edge = x in (x0, x1) or z in (z0, z1)
        corner = x in (x0, x1) and z in (z0, z1)
        if edge:
            for y in range(floor + 1, top):
                m.surf[(x, y, z)] = "minecraft:polished_basalt[axis=y]" if corner else (
                    "minecraft:cobbled_deepslate" if y == floor + 1 else wall)
            m.surf[(x, top, z)] = "minecraft:deepslate_tiles"
            m.surf[(x, top + 1, z)] = "minecraft:cobbled_deepslate_wall" if (x + z) % 2 == 0 or corner else AIR
        else:
            m.surf[(x, top, z)] = "minecraft:deepslate_tile_slab[type=top,waterlogged=false]"
    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
    door = {"south": (cx, z1), "north": (cx, z0), "east": (x1, cz), "west": (x0, cz)}[hrec["door"]]
    for x, z in cols:
        if not (x in (x0, x1) or z in (z0, z1)) or (x in (x0, x1) and z in (z0, z1)):
            continue
        along = z - z0 if x in (x0, x1) else x - x0
        if along % 3 == 1 and abs(x - door[0]) + abs(z - door[1]) > 1:
            m.surf[(x, floor + 3, z)] = "minecraft:iron_bars"
    facing = {"south": "north", "north": "south", "east": "west", "west": "east"}[hrec["door"]]
    m.surf[(door[0], floor + 1, door[1])] = "%s[facing=%s,half=lower,hinge=left,open=false,powered=false]" % (DOOR, facing)
    m.surf[(door[0], floor + 2, door[1])] = "%s[facing=%s,half=upper,hinge=left,open=false,powered=false]" % (DOOR, facing)
    back = {"south": [(x, z0 + 1) for x in range(x0 + 1, x1)], "north": [(x, z1 - 1) for x in range(x0 + 1, x1)],
            "east": [(x0 + 1, z) for z in range(z0 + 1, z1)], "west": [(x1 - 1, z) for z in range(z0 + 1, z1)]}[hrec["door"]]
    for (x, z), b in zip(back, ROLE_FITTINGS[hrec["role"]]):
        m.surf[(x, floor + 1, z)] = b
    for cnt in hrec.get("counters") or []:
        (xa, za), (xb, zb) = cnt
        for x in range(min(xa, xb), max(xa, xb) + 1):
            for z in range(min(za, zb), max(za, zb) + 1):
                m.surf[(x, floor + 1, z)] = m.spec["palette"]["meteorid_polished"]
    step = hrec.get("light_every", 6)
    for x in range(x0 + 2, x1 - 1, step):
        for z in range(z0 + 2, z1 - 1, step):
            m.surf[(x, top - 1, z)] = LANTERN_HANG
    m.surf[(cx, top - 1, cz)] = LANTERN_HANG


def gate_build(m):
    g = m.spec["gate"]
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    band = band_columns(g["band"])
    ground_at = {p[0]: m.ground(int(p[1]), int(p[2])) for p in g["band"]["points"]}
    pl = g["plug"]
    n_rock = 0
    for (x, z), j in sorted(band.items()):
        if not (m.X0 <= x <= m.X1 and m.Z0 <= z <= m.Z1):
            raise GulchError("the rockfall column (%d, %d) is outside the grid" % (x, z))
        in_plug = abs(j) <= pl["half_j"]
        if in_plug and x > pl["max_x"] and pl["trim_z"][0] <= z <= pl["trim_z"][1]:
            continue                     # the plug's face is flat by the grille, so it stands in one plane (data gate.plug)
        base = m.top(x, z)
        ring_top = pl["top_y"] if in_plug else ground_at[j] + g["band"]["height"]
        if base >= ring_top:
            continue                     # a crag column already stands higher than the rockfall would
        topy = max(ring_top, base + g["band"]["min_rise"])
        for y in range(base + 1, topy + 1):
            m.surf[(x, y, z)] = pick(pal["rubble"], seed, x, y, z, 61)
            n_rock += 1
    gr = g["grille"]
    for z in range(gr["z"][0] - 1, gr["z"][1] + 2):
        for y in range(gr["y"][0], gr["y"][1] + 2):
            inner = gr["z"][0] <= z <= gr["z"][1] and y <= gr["y"][1]
            if inner:
                m.surf[(gr["x"], y, z)] = "minecraft:iron_bars"
            elif y <= gr["y"][1]:
                m.surf[(gr["x"], y, z)] = pal["post"] + "[axis=y]"
            else:
                m.surf[(gr["x"], y, z)] = pal["post"] + "[axis=z]"
    for x, z in g["lamp_posts"]:
        yy = m.top(x, z)
        m.surf[(x, yy + 1, z)] = "minecraft:cobbled_deepslate_wall"
        m.surf[(x, yy + 2, z)] = "minecraft:cobbled_deepslate_wall"
        m.surf[(x, yy + 3, z)] = LANTERN_STAND
    m.counts["rockfall and plug blocks"] = n_rock


# ------------------------------------------------------------------ checks on the model

def standable_mask(m, extra_solid):
    """open = carved, or above the column's top and not written solid by the surface passes. Returns (open, stand)."""
    op = m.carve.copy()
    tops = np.array([[m.top(i + m.X0, k + m.Z0) for k in range(m.nz)] for i in range(m.nx)])
    ys = np.arange(m.ny)[None, None, :] + m.Y0
    op |= ys > tops[:, :, None]
    for (x, y, z), b in extra_solid.items():
        if m.inside(x, y, z):
            i, k, j = m.ix(x, y, z)
            op[i, k, j] = (b == AIR) or any(p in b for p in PASSABLE)
    stand = op & np.roll(op, -1, 2) & ~np.roll(op, 1, 2)
    stand[:, :, 0] = False
    stand[:, :, -1] = False
    return op, stand


def walk(m, stand, op, start):
    """Cells a player reaches from `start` (x, y, z): a step to a neighbouring column up 1 (with head room) or down up to 3."""
    seen = set()
    s = m.ix(*start)
    if not stand[s]:
        return seen
    dq = deque([s])
    seen.add(s)
    nx, nz, ny = stand.shape
    while dq:
        i, k, j = dq.popleft()
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, k + dk
            if not (0 <= a < nx and 0 <= b < nz):
                continue
            for dj in (0, 1, -1, -2, -3):
                c = j + dj
                if not (0 <= c < ny) or not stand[a, b, c]:
                    continue
                if dj == 1 and not (j + 2 < ny and op[i, k, j + 2]):
                    continue                        # no room to jump up
                if dj < 0 and not all(op[a, b, c + q] for q in range(1, -dj + 2) if c + q < ny):
                    continue
                q = (a, b, c)
                if q not in seen:
                    seen.add(q)
                    dq.append(q)
                break
    return seen


def check(m, near, tops):
    spec = m.spec
    probs = []
    out = [c for d in (m.earth, m.surf, m.fit, m.faces) for c in d if not m.inside(*c)]
    if out:
        probs.append("%d writes outside the grid, e.g. %s" % (len(out), sorted(out)[:3]))
    cover_min = spec["cover_min"]
    # cover over every hall column
    for h in spec["mine"]["halls"]:
        thin = [(x, z) for (x, z), (feet, top) in m.hall_cols[h["id"]].items() if m.top(x, z) - (top + SHELL_R) < cover_min]
        if thin:
            probs.append("hall %s: %d columns with under %d of rock over the shell, e.g. %s" % (h["id"], len(thin), cover_min, thin[:3]))
    # nothing carved at or above a column's top, except at the adit's portal in the yard
    px0, pz0, px1, pz1 = spec["mine"]["portal"]["open_rect"]
    portal = {(x, z) for x in range(px0, px1 + 1) for z in range(pz0, pz1 + 1)}
    br = [(int(i + m.X0), int(j + m.Y0), int(k + m.Z0)) for i, k, j in np.argwhere(m.carve)
          if j + m.Y0 >= tops[i, k] - 1 and (int(i + m.X0), int(k + m.Z0)) not in portal]
    if br:
        probs.append("%d carved cells within a block of the surface outside the portal, e.g. %s" % (len(br), br[:3]))
    for d in spec["mine"]["drifts"]:
        for (x0, y0, z0), (x1, y1, z1) in zip(d["path"], d["path"][1:]):
            L = math.hypot(x1 - x0, z1 - z0)
            if L and abs(y1 - y0) / L > 0.6:
                probs.append("%s: a segment climbs %.2f per block" % (d["id"], abs(y1 - y0) / L))
    # the walk: from the square, and from the gate's arrival, to every place the player must reach
    solid = dict(m.earth)
    solid.update(m.surf)
    solid.update(m.fit)
    solid.update({c: "rock" for c in m.faces})
    op, stand = standable_mask(m, solid)
    sq = spec["town"]["square"]
    start = (sq["centre"][0] + 4, sq["surface_y"] + 1, sq["centre"][1])
    reach = walk(m, stand, op, start)
    ax, ay, az, _ = spec["gate"]["arrive"]
    reach_gate = walk(m, stand, op, (int(math.floor(ax)), ay, int(math.floor(az))))
    must = {"the square from the gate's arrival": [start]}
    for h in spec["mine"]["halls"]:
        cx, cz = h["centre"]
        must["%s's floor" % h["id"]] = [(cx, feet_at(m, cx, cz), cz)]
    for f in spec["mine"]["faces"]:
        must["%s's front" % f["id"]] = [tuple(f["stand"])]
    for s in spec["megas"]["slots"]:
        must["%s's anchor" % s["id"]] = [tuple(s["_anchor"])]
    for c in spec["cutters"]["benches"]:
        must["the counter before %s" % c["id"]] = [tuple(c["customer"])]
    for what, cells in must.items():
        pool = reach_gate if what.startswith("the square") else reach
        for c in cells:
            if None in c or m.ix(*c) not in pool:
                probs.append("walk: %s %s is not reached" % (what, c))
    m.counts["cells walked from the square"] = len(reach)
    m.counts["cells walked from the gate"] = len(reach_gate)
    # the anchors have head room for a large Pokemon
    for s in spec["megas"]["slots"]:
        x, y, z = s["_anchor"]
        room = ceiling_over(m, x, y, z) - y + 1 if y is not None else 0
        if room < s["head_room"]:
            probs.append("mega %s: %d of head room at its anchor, %d wanted" % (s["id"], room, s["head_room"]))
    return probs


def zone_problems(m, boxes):
    spec = m.spec
    probs = []

    def inz(x, z):
        return any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for b in boxes)
    g = spec["gate"]
    for what, (x, z) in (("arrival", (int(math.floor(g["arrive"][0])), int(math.floor(g["arrive"][2])))),):
        if not inz(x, z):
            probs.append("zone: the %s (%d, %d) is outside the zone" % (what, x, z))
    e = g["exit"]
    for x in range(e[0], e[3] + 1):
        for z in range(e[2], e[5] + 1):
            if not inz(x, z):
                probs.append("zone: exit box column (%d, %d) is outside the zone" % (x, z))
    k = g["knock"]
    for x in range(k[0], k[3] + 1):
        for z in range(k[2], k[5] + 1):
            if inz(x, z):
                probs.append("zone: knock box column (%d, %d) is inside the zone" % (x, z))
    tx, tz = int(math.floor(g["turn_back"][0])), int(math.floor(g["turn_back"][2]))
    if inz(tx, tz):
        probs.append("zone: the turn-back point is inside the zone")
    # every carved cell and every town write inside
    cols = {(int(i + m.X0), int(k + m.Z0)) for i, k in np.argwhere(m.carve.any(axis=2))}
    cols |= {(x, z) for x, _y, z in list(m.surf) + list(m.fit) if m.spec["town"]["square"] and (x, z) not in band_columns(g["band"])}
    out = sorted(c for c in cols if not inz(*c) and not (g["outside_ok"][0] <= c[0] <= g["outside_ok"][2]
                                                            and g["outside_ok"][1] <= c[1] <= g["outside_ok"][3]))
    if out:
        probs.append("zone: %d built columns outside the zone, e.g. %s" % (len(out), out[:3]))
    return probs


# ------------------------------------------------------------------ the pack

def lines(m):
    out = {p: [] for p in PASSES}

    def cols_of(d):
        cols = {}
        for (x, y, z), b in d.items():
            cols.setdefault((x, z), []).append((y, b))
        return cols

    ec = cols_of(m.earth)
    for (x, z) in sorted(ec):
        out["earth"] += [RM.cmd(x, a, c, z, b) for a, c, b in RM.column_runs(x, z, ec[(x, z)])]
    sc = cols_of(m.blocks)
    for (x, z) in sorted(sc):
        out["shell"] += [RM.cmd(x, a, c, z, b) for a, c, b in RM.column_runs(x, z, sc[(x, z)])]
    for i, k in np.argwhere(m.carve.any(axis=2)):
        js = np.nonzero(m.carve[i, k])[0]
        x, z = int(i + m.X0), int(k + m.Z0)
        out["air"] += [RM.cmd(x, a, c, z, AIR) for a, c, _b in RM.column_runs(x, z, [(int(j + m.Y0), AIR) for j in js])]
    fits = sorted(m.fit.items(), key=lambda kv: (any(d in kv[1] for d in SOFT), kv[0][1], kv[0][0], kv[0][2]))
    out["fittings"] = ["setblock %d %d %d %s" % (x, y, z, b) for (x, y, z), b in fits]
    solid = {p: b for p, b in m.surf.items() if not any(d in b for d in SOFT)}
    soft = [(p, b) for p, b in m.surf.items() if any(d in b for d in SOFT)]
    scs = cols_of(solid)
    for (x, z) in sorted(scs):
        out["surface"] += [RM.cmd(x, a, c, z, b) for a, c, b in RM.column_runs(x, z, scs[(x, z)])]
    out["surface"] += ["setblock %d %d %d %s" % (x, y, z, b) for (x, y, z), b in sorted(soft, key=lambda kv: (kv[0][1], kv[0]))]
    out["faces"] = ["setblock %d %d %d %s" % (x, y, z, b) for (x, y, z), b in sorted(m.faces.items(), key=lambda kv: ("crystal" in kv[1], kv[0]))]
    return out


def text(s, **style):
    return json.dumps(dict({"text": s}, **style), ensure_ascii=False)


def box_cond(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    return {"condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"location": {"dimension": "minecraft:overworld", "position": {
                "x": {"min": x0, "max": x1 + 1}, "y": {"min": y0, "max": y1 + 1}, "z": {"min": z0, "max": z1 + 1}}}}}


def adv(conds, reward):
    return {"criteria": {"here": {"trigger": "minecraft:location", "conditions": {"player": conds}}},
            "rewards": {"function": reward}}


def ordinal(n):
    return RM.ordinal(n)


def gate_files(m, boxes):
    spec = m.spec
    g = spec["gate"]
    flag = spec["flag"]["advancement"]
    badge = spec["flag"]["badge"]
    has = "@s[advancements={%s=true}]" % flag
    lacks = "@s[gamemode=!creative,gamemode=!spectator,advancements={%s=false}]" % flag
    ax, ay, az, ayaw = g["arrive"]
    tx, ty, tz, tyaw = g["turn_back"]
    k, e, w = g["knock"], g["exit"], g["ward"]
    zmin, zmax = spec["zone"]["y"]
    zone = [box_cond((b[0], zmin, b[1]), (b[2], zmax, b[3])) for b in boxes]
    F = "%s:%s" % (NS, FOLDER)
    files = {
        "advancement/%s/gate_ward.json" % FOLDER: adv([box_cond(w[:3], w[3:])], "%s/gate/ward" % F),
        "advancement/%s/gate_knock.json" % FOLDER: adv([box_cond(k[:3], k[3:])], "%s/gate/knock" % F),
        "advancement/%s/gate_exit.json" % FOLDER: adv([box_cond(e[:3], e[3:])], "%s/gate/exit" % F),
        "advancement/%s/zone.json" % FOLDER: adv([{"condition": "minecraft:any_of", "terms": zone}], "%s/gate/zone" % F),
    }
    fl = spec["floor"]
    files["advancement/%s/floor.json" % FOLDER] = adv([box_cond(fl["box"][:3], fl["box"][3:])], "%s/floor" % F)
    fn = {
        "gate/ward": [
            "# near the gulch gate (data/gulch_mine.json gate.ward_why): Mining Fatigue IV, refreshed each second the",
            "# location trigger fires, so the plug and the rock round it cannot be dug through",
            "advancement revoke @s only %s:%s/gate_ward" % (NS, FOLDER),
            "execute if entity @s[gamemode=!creative,gamemode=!spectator] run effect give @s minecraft:mining_fatigue 3 3 true"],
        "gate/knock": [
            "# the Gulch lookout's gate (tools/gulch_mine.py): a player holding %s is put through; anyone else is told" % flag,
            "advancement revoke @s only %s:%s/gate_knock" % (NS, FOLDER),
            "execute if entity %s run tp @s %s %d %s %d 0" % (has, ax, ay, az, ayaw),
            "execute if entity %s run title @s actionbar %s" % (has, text("The lookout lifts the grille, and drops it behind you.", color="gray")),
            "execute unless entity %s run title @s actionbar %s" % (has, text("Closed by the lookout. The gulch opens with the %s badge." % ordinal(badge), color="gold"))],
        "gate/exit": [
            "# the way out from behind the gate: anyone, flag or not",
            "advancement revoke @s only %s:%s/gate_exit" % (NS, FOLDER),
            "tp @s %s %d %s %d 0" % (tx, ty, tz, tyaw)],
        "gate/zone": [
            "# the zone check (docs/mechanics/RIFT_ZONES.md section 4): anyone in the gulch zone without the flag is",
            "# turned back to the front of the gate",
            "advancement revoke @s only %s:%s/zone" % (NS, FOLDER),
            "execute if entity %s run function %s/gate/turn_back" % (lacks, F)],
        "gate/turn_back": [
            "# a mount first, then the player",
            "execute on vehicle run tp @s %s %d %s" % (tx, ty, tz),
            "tp @s %s %d %s %d 0" % (tx, ty, tz, tyaw),
            "title @s actionbar %s" % text("Turned back: the gulch opens with the %s badge." % ordinal(badge), color="gold")],
        "floor": [
            "# once per player, on first reaching the Tally Hall (SOUTHERN_RIFT_MEGA.md 7.5, the floor): enough raw stone for",
            "# one keyed stone. The advancement is never revoked, so it is given once",
            "give @s %s %d" % (fl["item"], fl["count"]),
            "title @s actionbar %s" % text(fl["message"], color="gray")],
    }
    return files, fn


def cutter_files(m):
    c = m.spec["cutters"]
    off = c["offer"]
    tag, new = c["tag"], c["tag"] + "_new"
    F = "%s:%s" % (NS, FOLDER)
    xs = [b["at"][0] for b in c["benches"]]
    zs = [b["at"][2] for b in c["benches"]]
    box = (min(xs) - 2, min(zs) - 2, max(xs) + 2, max(zs) + 2)
    load = ["# the Cutters (tools/gulch_mine.py, the traders.py pattern): force-load the workshop, wait for its saved",
            "# villagers to load (40 ticks), summon, and 100 ticks on keep one per bench",
            "forceload add %d %d %d %d" % box,
            "schedule function %s/cutters_place 40t replace" % F]
    place = ["# chunks-loaded-by: %s/cutters" % F]
    done = ["# chunks-loaded-by: %s/cutters" % F]
    for b in c["benches"]:
        recipes = []
        for s in b["stones"]:
            recipes.append("{buy:{id:\"%s\",count:%d},buyB:{id:\"%s\",count:%d},sell:{id:\"%s\",count:1},uses:0,maxUses:%d,"
                           "rewardExp:0b,xp:0,priceMultiplier:0.0f,specialPrice:0,demand:0}"
                           % (off["raw"], off["raw_count"], off["fee"], off["fee_count"], s, off["max_uses"]))
        x, y, z = b["at"]
        name = json.dumps({"text": b["name"]}, ensure_ascii=False).replace("'", "\\'")
        place.append("summon minecraft:villager %.1f %d %.1f {Tags:[\"%s\",\"%s\",\"%s_%s\"],NoAI:1b,Invulnerable:1b,"
                     "PersistenceRequired:1b,Silent:1b,Rotation:[%.1ff,0.0f],CustomName:'%s',CustomNameVisible:1b,"
                     "VillagerData:{profession:\"%s\",level:5,type:\"%s\"},Xp:250,Offers:{Recipes:[%s]}}"
                     % (x + 0.5, y, z + 0.5, tag, new, tag, b["id"], b["yaw"], name, c["profession"], c["villager_type"],
                        ",".join(recipes)))
        done.append("execute positioned %.1f %d %.1f if entity @e[type=minecraft:villager,tag=%s,tag=%s_%s,distance=..1.5] "
                    "run kill @e[type=minecraft:villager,tag=%s_%s,tag=!%s]" % (x + 0.5, y, z + 0.5, new, tag, b["id"], tag, b["id"], new))
    place.append("schedule function %s/cutters_done 100t replace" % F)
    done += ["tag @e[type=minecraft:villager,tag=%s] remove %s" % (new, new), "forceload remove %d %d %d %d" % box]
    return {"cutters": load, "cutters_place": place, "cutters_done": done}


def keeper_files(m):
    """The tick driver: the faces' restore on approach, the Megas' keeper and leash."""
    spec = m.spec
    F = "%s:%s" % (NS, FOLDER)
    ap = spec["driver"]["approach"]
    near = "@a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d]" % (ap[0], ap[1], ap[2], ap[3] - ap[0], ap[4] - ap[1], ap[5] - ap[2])
    period = spec["faces"]["period_ticks"]
    fn = {}
    load = ["# the gulch mine's driver state (tools/gulch_mine.py): scores survive a restart in the world's scoreboard,",
            "# so a restore that has happened is not repeated (STONE_ECONOMY.md P-4)",
            "scoreboard objectives add gm.t dummy", "scoreboard objectives add gm.last dummy",
            "scoreboard objectives add gm.var dummy", "scoreboard objectives add gm.owe dummy",
            "scoreboard objectives add gm.abs dummy",
            "scoreboard players set #period gm.t %d" % period, "scoreboard players set #eight gm.t 8"]
    for f in spec["mine"]["faces"]:
        load.append("execute unless score #%s gm.last matches -2147483648.. run scoreboard players set #%s gm.last %d"
                    % (f["id"], f["id"], -f["offset_ticks"]))
        load.append("execute unless score #%s gm.var matches -2147483648.. run scoreboard players set #%s gm.var 0" % (f["id"], f["id"]))
    for s in spec["megas"]["slots"]:
        load.append("execute unless score #%s gm.owe matches -2147483648.. run scoreboard players set #%s gm.owe 0" % (s["id"], s["id"]))
        load.append("execute unless score #%s gm.abs matches -2147483648.. run scoreboard players set #%s gm.abs 0" % (s["id"], s["id"]))
    fn["load"] = load
    fn["tick"] = ["# every tick: two counters; the work runs only when a player is near (SOUTHERN_RIFT_MEGA.md 7.6)",
                  "scoreboard players add #clock gm.t 1",
                  "scoreboard players add #leash gm.t 1",
                  "execute if score #leash gm.t matches %d.. run function %s/leash" % (spec["megas"]["leash_every_ticks"], F),
                  "execute if score #clock gm.t matches %d.. run function %s/drive" % (spec["driver"]["every_ticks"], F)]
    drive = ["scoreboard players set #clock gm.t 0",
             "execute unless entity %s run return 0" % near,
             "execute store result score #now gm.t run time query gametime"]
    for f in spec["mine"]["faces"]:
        drive.append("function %s/faces/check_%s" % (F, f["id"]))
    for s in spec["megas"]["slots"]:
        drive.append("function %s/megas/keep_%s" % (F, s["id"]))
    fn["drive"] = drive
    leash = ["scoreboard players set #leash gm.t 0",
             "execute unless entity %s run return 0" % near]
    slots = {s["id"]: s for s in spec["megas"]["slots"]}
    for s in spec["megas"]["slots"]:
        x, y, z = s["_anchor"]
        leash.append("execute as @e[type=cobblemon:pokemon,tag=%s.%s] positioned %d %d %d unless entity @s[distance=..%d] "
                     "run tp @s %d %d %d" % (spec["megas"]["tag"], s["id"], x, y, z, s["leash"], x, y, z))
    fn["leash"] = leash
    hall_slots = {}
    for s in spec["megas"]["slots"]:
        hall_slots.setdefault(s["hall"], []).append(s)
    for f in spec["mine"]["faces"]:
        x0, y0, z0, x1, y1, z1 = f["box"]
        gx0, gy0, gz0, gx1, gy1, gz1 = x0 - 1, y0 - 1, z0 - 1, x1 + 1, y1 + 1, z1 + 1
        vol = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (gx0, gy0, gz0, gx1 - gx0, gy1 - gy0, gz1 - gz0)
        fn["faces/check_%s" % f["id"]] = [
            "# restore on approach (STONE_ECONOMY.md 5.3): the period has passed, both corners are loaded, and nobody and",
            "# no Pokemon stands in the box or one block round it",
            "scoreboard players operation #d gm.t = #now gm.t",
            "scoreboard players operation #d gm.t -= #%s gm.last" % f["id"],
            "execute if score #d gm.t < #period gm.t run return 0",
            "execute unless loaded %d %d %d run return 0" % (gx0, gy0, gz0),
            "execute unless loaded %d %d %d run return 0" % (gx1, gy1, gz1),
            "execute if entity @a[%s] run return 0" % vol,
            "execute if entity @e[type=cobblemon:pokemon,%s] run return 0" % vol,
            "function %s/faces/restore_%s" % (F, f["id"])]
        restore = ["# a variant other than the last one: random value 0..7, moved on by one if it repeats",
                   "execute store result score #v gm.t run random value 0..7",
                   "execute if score #v gm.t = #%s gm.var run scoreboard players add #v gm.t 1" % f["id"],
                   "scoreboard players operation #v gm.t %= #eight gm.t",
                   "scoreboard players operation #%s gm.var = #v gm.t" % f["id"]]
        for k in range(spec["faces"]["variants"]):
            restore.append("execute if score #v gm.t matches %d run function %s/faces/%s_v%d" % (k, F, f["id"], k))
        restore.append("scoreboard players operation #%s gm.last = #now gm.t" % f["id"])
        for s in hall_slots.get(f["hall"], []):
            restore.append("# the hall's Mega comes back with the fresh face, if it is gone (SOUTHERN_RIFT_MEGA.md 6.2)")
            restore.append("execute unless entity @e[type=cobblemon:pokemon,tag=%s.%s] run scoreboard players set #%s gm.owe 1"
                           % (spec["megas"]["tag"], s["id"], s["id"]))
        fn["faces/restore_%s" % f["id"]] = restore
        tagname = "#%s:%s" % (NS, spec["faces"]["resettable_tag"])
        for k in range(spec["faces"]["variants"]):
            content, _cr = face_block(m, f, k)
            body = ["# chunks-loaded-by: %s/faces/check_%s (execute if loaded, both corners of the box)" % (F, f["id"]),
                    "fill %d %d %d %d %d %d %s replace %s" % (x0, y0, z0, x1, y1, z1, m.spec["palette"]["meteorid"], tagname)]
            for (x, y, z), b in sorted(content.items(), key=lambda kv: ("crystal" in kv[1], kv[0])):
                body.append("execute if block %d %d %d %s run setblock %d %d %d %s" % (x, y, z, tagname, x, y, z, b))
            fn["faces/%s_v%d" % (f["id"], k)] = body
    for s in spec["megas"]["slots"]:
        x, y, z = s["_anchor"]
        t = "%s.%s" % (spec["megas"]["tag"], s["id"])
        fn["megas/keep_%s" % s["id"]] = [
            "execute unless loaded %d %d %d run return 0" % (x, y, z),
            "execute store result score #n gm.t if entity @e[type=cobblemon:pokemon,tag=%s]" % t,
            "# a duplicate (a spawn that raced a slow entity load): the extra goes",
            "execute if score #n gm.t matches 2.. run kill @e[type=cobblemon:pokemon,tag=%s,limit=1,sort=furthest]" % t,
            "execute if score #n gm.t matches 1.. run scoreboard players set #%s gm.abs 0" % s["id"],
            "execute if score #n gm.t matches 0 run scoreboard players add #%s gm.abs 1" % s["id"],
            "# spawned only when owed (its hall's face restored while it was gone), absent on two passes in a row (entities",
            "# load a moment after their chunk), and with nobody within %d of its anchor" % spec["megas"]["spawn_clear"],
            "execute if score #%s gm.abs matches 2.. if score #%s gm.owe matches 1 unless entity @a[x=%d,y=%d,z=%d,distance=..%d] "
            "run function %s/megas/spawn_%s" % (s["id"], s["id"], x, y, z, spec["megas"]["spawn_clear"], F, s["id"])]
        fn["megas/spawn_%s" % s["id"]] = [
            "# a wild Mega: its species, the Mega aspect, uncatchable (EXP-036's command, from a function: EXP-042)",
            "spawnpokemonat %d %d %d %s %s uncatchable level=%d" % (x, y, z, s["species"], s["aspect"], s["level"]),
            "execute positioned %d %d %d as @e[type=cobblemon:pokemon,tag=!%s,distance=..2,limit=1,sort=nearest] run function %s/megas/bind_%s"
            % (x, y, z, spec["megas"]["tag"], F, s["id"]),
            "scoreboard players set #%s gm.owe 0" % s["id"],
            "scoreboard players set #%s gm.abs 0" % s["id"]]
        fn["megas/bind_%s" % s["id"]] = [
            "tag @s add %s" % spec["megas"]["tag"],
            "tag @s add %s" % t,
            "data merge entity @s {PersistenceRequired:1b}"]
    return fn


def write(m, lns, boxes):
    if OUT.exists():
        shutil.rmtree(OUT)
    base = OUT / "data" / NS
    fn = base / "function" / FOLDER
    fn.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: the southern Rift's mega site, prototype slice (tools/gulch_mine.py)"}},
                                     indent=2) + "\n", encoding="utf-8")
    order = []
    for n, pas in enumerate(PASSES):
        tiles = {}
        for ln in lns[pas]:
            t = ln.split()
            tiles.setdefault((int(t[1]) // TILE, int(t[3]) // TILE), []).append(ln)
        for t in sorted(tiles):
            body = tiles[t]
            for j in range(0, len(body), PART):
                name = "%d%s_%d_%d%s" % (n + 1, pas, t[0], t[1], "" if j == 0 else "_%d" % (j // PART + 1))
                part = FL.ensure_loaded(["# Generated by tools/gulch_mine.py: %s, tile %d %d" % (pas, t[0], t[1])] + body[j:j + PART])
                bad = FL.check_lines(part, name)
                if bad:
                    raise GulchError("function %s would be refused: %s" % (name, bad[:3]))
                (fn / (name + ".mcfunction")).write_text("\n".join(part) + "\n", encoding="utf-8")
                order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    files, gfn = gate_files(m, boxes)
    for rel, obj in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")
    allfn = dict(gfn)
    allfn.update(cutter_files(m))
    allfn.update(keeper_files(m))
    for name, body in allfn.items():
        bad = FL.check_lines(body, name)
        if bad:
            raise GulchError("function %s would be refused: %s" % (name, bad[:3]))
        p = fn / (name + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(body) + "\n", encoding="utf-8")
    tags = OUT / "data" / "minecraft" / "tags" / "function"
    tags.mkdir(parents=True)
    (tags / "load.json").write_text(json.dumps({"values": ["%s:%s/load" % (NS, FOLDER)]}, indent=2) + "\n", encoding="utf-8")
    (tags / "tick.json").write_text(json.dumps({"values": ["%s:%s/tick" % (NS, FOLDER)]}, indent=2) + "\n", encoding="utf-8")
    bt = base / "tags" / "block"
    bt.mkdir(parents=True)
    (bt / ("%s.json" % m.spec["faces"]["resettable_tag"])).write_text(
        json.dumps({"values": m.spec["faces"]["resettable"]}, indent=2) + "\n", encoding="utf-8")
    return order


# ------------------------------------------------------------------ trace: the ring-derived geometry, for authoring

def sculpt_ring(source_root=None):
    if SCULPT_PLAN.is_file():
        sc = json.loads(SCULPT_PLAN.read_text(encoding="utf-8"))
        return sc["ring"], sc["normals"], {e["id"]: e for e in sc["entrances"]}
    import rift_heightmap as RH
    b = RH.build(source_root)
    X0, _X1, Z0, _Z1 = b["box"]
    ring = [[int(x) + X0, int(z) + Z0] for z, x in b["ring"]]
    nrm = [[round(float(nx), 4), round(float(nz), 4)] for nz, nx in b["nrm"]]
    return ring, nrm, {e["id"]: dict(e, ring=bi) for bi, e, _d in b["ent"]}


def trace(spec, source_root=None):
    ring, nrm, ent = sculpt_ring(source_root)
    T = len(ring)
    e = ent[spec["gate"]["band"]["entrance"]]
    bi, gap = e["ring"], e["gap"]
    pts = [[j, ring[(bi + j) % T][0], ring[(bi + j) % T][1], nrm[(bi + j) % T][0], nrm[(bi + j) % T][1]]
           for j in range(-gap, gap + 1)]
    zt = spec["zone"]["trace"]

    def nearest(p):
        return min(range(T), key=lambda k: (ring[k][0] - p[0]) ** 2 + (ring[k][1] - p[1]) ** 2)
    kA, kB = nearest(zt["from_near"]), nearest(zt["to_near"])
    poly = []
    run = []
    gap_run = None
    for i in range((kB - kA) % T + 1):
        k = (kA + i) % T
        j = k - bi
        in_gap = -gap <= j <= gap
        x, z = ring[k]
        # the normals point into the basin: inset across the gap, outset along the rim
        d = zt["gap_inset"] if in_gap else -zt["rim_outset"]
        x, z = round(x + nrm[k][0] * d, 1), round(z + nrm[k][1] * d, 1)
        if gap_run is not None and in_gap != gap_run:
            poly += simplify(run, zt["tolerance_gap"] if gap_run else zt["tolerance"])
            run = []
        gap_run = in_gap
        run.append([x, z])
    poly += simplify(run, zt["tolerance_gap"] if gap_run else zt["tolerance"])
    return {"entrance": spec["gate"]["band"]["entrance"], "ring_index": bi, "gap": gap, "points": pts,
            "zone_from": [kA, ring[kA]], "zone_to": [kB, ring[kB]], "polygon": poly}


def simplify(p, tol):
    """Douglas-Peucker on [x, z] points."""
    if len(p) < 3:
        return list(p)
    (x0, z0), (x1, z1) = p[0], p[-1]
    L = math.hypot(x1 - x0, z1 - z0) or 1e-9
    best, bi = -1.0, 0
    for i in range(1, len(p) - 1):
        d = abs((x1 - x0) * (z0 - p[i][1]) - (x0 - p[i][0]) * (z1 - z0)) / L
        if d > best:
            best, bi = d, i
    if best > tol:
        return simplify(p[:bi + 1], tol)[:-1] + simplify(p[bi:], tol)
    return [p[0], p[-1]]


# ------------------------------------------------------------------ driver

def model(source_root=None, spec=None):
    spec = spec or load()
    g = G.Ground(source_root)
    m = Model(spec, g)
    earthworks(m)
    rasterise(m)
    near, tops = shell(m)
    build_blocks(m, near)
    fittings(m)
    for f in spec["mine"]["faces"]:
        content, crys = face_block(m, f, 0)
        x0, y0, z0, x1, y1, z1 = f["box"]
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    m.faces[(x, y, z)] = content.get((x, y, z), spec["palette"]["meteorid"])
    surface_build(m)
    for s in spec["megas"]["slots"]:
        x, z = s["anchor"]
        hall = next(h for h in spec["mine"]["halls"] if h["id"] == s["hall"])
        s["_anchor"] = [x, feet_at(m, x, z, hall["feet"] - 1, hall["feet"] + hall["bowl"] + 2), z]
    m.counts.update({"carved cells": int(m.carve.sum()), "shell cells": len(m.blocks), "earthwork cells": len(m.earth),
                     "fittings": len(m.fit), "surface blocks": len(m.surf), "face cells": len(m.faces),
                     "crystals per restore": sum(f["crystals"] for f in spec["mine"]["faces"])})
    for h in spec["mine"]["halls"]:
        cols = m.hall_cols[h["id"]]
        m.counts["%s columns" % h["id"]] = len(cols)
        m.counts["%s air cells" % h["id"]] = sum(t - f + 1 for f, t in cols.values())
    return m, near, tops


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("trace", "report", "build"))
    p.add_argument("--source-root")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    spec = load()
    if a.mode == "trace":
        print(json.dumps(trace(spec, a.source_root)))
        return 0
    m, near, tops = model(a.source_root, spec)
    boxes = zone_boxes(spec["zone"]["polygon"])
    probs = check(m, near, tops) + zone_problems(m, boxes)
    for k, v in m.counts.items():
        print("  %-34s %s" % (k, v))
    print("  %-34s %d" % ("zone boxes", len(boxes)))
    if probs:
        for pr in probs:
            print("PROBLEM:", pr)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    if a.mode == "report":
        return 0
    lns = lines(m)
    order = write(m, lns, boxes)
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    plan = {"schema": "cobblers.derived.gulch_mine/1", "counts": m.counts, "functions": order,
            "commands": {k: len(v) for k, v in lns.items()}, "zone_boxes": boxes,
            "anchors": {s["id"]: s["_anchor"] for s in spec["megas"]["slots"]},
            "faces": {f["id"]: f["box"] for f in spec["mine"]["faces"]},
            "halls": {h["id"]: {"centre": h["centre"], "columns": len(m.hall_cols[h["id"]])} for h in spec["mine"]["halls"]}}
    PLAN.write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8")
    print("wrote %s: %d block functions, %d commands; plan %s"
          % (OUT.relative_to(ROOT), len(order), sum(plan["commands"].values()), PLAN.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
