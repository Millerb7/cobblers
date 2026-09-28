#!/usr/bin/env python
"""The southern Rift's mega site, prototype slice, from data/gulch_mine.json (docs/world-building/SOUTHERN_RIFT_MEGA.md
section 10, the owner's twelve decisions of 2026-09-27, section 11, and the owner's redesign, section 13).

What it builds, all from the data file and the canonical heightmap (tools/ground.py, rounded; never a world):

  the gate     the Gulch lookout's rockslide wall across the sculpt's gulch_mouth gap, to the crag tops (data
               `gate.band`, traced from the sculpt's lip ring by `trace`; `band.wall` its crest and talus), a plug with
               the company's grille at the end of a slot through it, a graded road, and the advancements: knock (a
               player holding cobblers:flag/gym6_cleared is put through), exit, the Mining Fatigue ward round the plug,
               and the zone check over the whole gulch zone (data `zone.polygon`)
  the town     the 61-square at (4308, 4848) paved and dressed, a yard cut into the slope south of it with the Cutters'
               workshop, a bunkhouse, the assay counter and the adit head; three Cutter villagers (vanilla trades:
               cutters.offer.raw_count raw mega stones + 1 diamond -> one keyed stone, unlimited, nothing bought);
               the cove town round it (data `cove`: lapidaries, the workers' quarter, the miners' camp, the extraction
               works), grown by accretion in `layout` and read from the data by `build`, and a cutting into the
               sunken east floor
  the mine     the Cutters' adit, the Tally Hall (lit) and the Cutting Floor (dark) as caverns at real scale, joined by
               a drift; a shell of rock round everything carved, so nothing this build opens meets a natural void
  the faces    two crystal faces in the Cutting Floor, each a 7 x 5 x 7 box of meteorid holding 3 mega_stone_crystal:
               scenery, written once by the build and warded for good every tick (the restore cycle is retired)
  the Megas    the Cutting Floor's two roaming Megas (and any farm den's, data `farms`), spawned by the keeper through
               the macro megas/spawn_at (EXP-046), uncatchable, claimed at once, tagged, leashed like the recovery
               guardians; each den's respawn clock is the game time its Mega was first seen gone, and it spawns
               respawn_ticks later with nobody near. A farm den's Mega also rolls a raw-stone drop when beaten
               (battle_fainted callback, by its Pokemon UUID) or killed (the attacker watch); none are in the data yet

  python tools/gulch_mine.py trace  [--source-root DIR]   the ring-derived geometry (band, zone polygon) as JSON, for
                                                          authoring data/gulch_mine.json; nothing written
  python tools/gulch_mine.py layout [--map]               the cove town's accretion, printed for data cove.buildings
                                                          and cove.lamp_posts (--map: a picture on stderr); nothing
                                                          written
  python tools/gulch_mine.py report [--fresh-layout]      the model's checks and counts (with a fresh layout in
                                                          place of the data's); nothing written
  python tools/gulch_mine.py build  [--source-root DIR]   -> build/datapacks/cobblers_gulch_mine, derived/gulch_mine/plan.json

The offline audit, independent of this tool's model, is tools/gulch_mine_audit.py. Recipes raised to the Cutters' raw
count are tools/mega_recipes.py's (generated from the local jar, never committed).
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


def band_cells(band):
    """{(x, z): (j, d)} for the rockslide wall (data geometry.band): each listed ring point claims the columns within 1
    (Chebyshev) of its point moved d = -spread_out .. spread_in along its inward normal (d < 0 is outward, onto the
    plateau). A column keeps the claim with the least talus drop, max(0, -d - core); among equals the first, in list
    order and d ascending."""
    w = band["wall"]
    out, drop = {}, {}
    for p in band["points"]:
        j, x, z, nx, nz = p
        for d in range(-w["spread_out"], w["spread_in"] + 1):
            dr = max(0, -d - w["core"])
            cx, cz = rnd(x + nx * d), rnd(z + nz * d)
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    c = (cx + a, cz + b)
                    if c not in out or dr < drop[c]:
                        out[c], drop[c] = (j, d), dr
    return out


def band_columns(band):
    """{(x, z): j} for the rockslide wall's columns (band_cells without the offset)."""
    return {c: jd[0] for c, jd in band_cells(band).items()}


def wall_crest(band, j):
    """The wall's crest at ring point j: the crag tops at the gap's two ends (data band.wall.top, at j = -gap and +gap),
    joined in a straight line."""
    lo, hi = band["wall"]["top"]
    js = [p[0] for p in band["points"]]
    j0, j1 = min(js), max(js)
    return lo + (hi - lo) * (j - j0) / float(j1 - j0)


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
    # the cove's cuttings (data cove.paths, rasterised as the road is): a graded way through the rim of the sunken
    # east floor, which no walker could otherwise enter or leave
    for p in (m.spec.get("cove") or {}).get("paths", []):
        for c, y in road_columns(p).items():
            if c not in m.surface:
                m.surface[c] = y
                m.earth_kind[c] = "path:" + p["id"]
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
        rec = t["square"] if kind == "square" else t["yard"] if kind == "yard" else m.spec["gate"]["road"] \
            if kind == "road" else next(p for p in m.spec["cove"]["paths"] if "path:" + p["id"] == kind)
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
    cove_build(m)
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


# ------------------------------------------------------------------ the cove town (SOUTHERN_RIFT_MEGA.md 13)

COVE_ROLES = {
    "dwelling": ["minecraft:barrel[facing=up]", "minecraft:crafting_table", "minecraft:polished_deepslate_slab[type=bottom,waterlogged=false]",
                 "minecraft:chest[facing=north,type=single,waterlogged=false]"],
    "canteen": ["minecraft:smoker[facing=north,lit=false]", "minecraft:barrel[facing=up]", "minecraft:cauldron",
                "minecraft:smoker[facing=north,lit=false]", "minecraft:barrel[facing=up]", "minecraft:barrel[facing=up]",
                "minecraft:polished_deepslate_slab[type=bottom,waterlogged=false]", "minecraft:polished_deepslate_slab[type=bottom,waterlogged=false]"],
    "washhouse": ["minecraft:water_cauldron[level=3]", "minecraft:water_cauldron[level=3]", "minecraft:cauldron",
                  "minecraft:barrel[facing=up]"],
    "winch": ["minecraft:grindstone[face=floor,facing=north]", "minecraft:chain[axis=x]", "minecraft:chain[axis=x]",
              "minecraft:barrel[facing=up]", "minecraft:anvil[facing=east]"],
    "toolshed": ["minecraft:smithing_table", "minecraft:grindstone[face=floor,facing=north]", "minecraft:barrel[facing=up]",
                 "minecraft:anvil[facing=east]", "minecraft:barrel[facing=up]"],
    "crusher": ["minecraft:piston[facing=down,extended=false]", "minecraft:grindstone[face=floor,facing=north]",
                "minecraft:piston[facing=down,extended=false]", "minecraft:anvil[facing=east]",
                "minecraft:piston[facing=down,extended=false]", "minecraft:grindstone[face=floor,facing=north]",
                "minecraft:barrel[facing=up]"],
    "sorting": ["minecraft:stonecutter[facing=north]", "minecraft:barrel[facing=up]", "minecraft:stonecutter[facing=north]",
                "minecraft:barrel[facing=up]", "minecraft:chest[facing=north,type=single,waterlogged=false]"],
    "lapidary": ["minecraft:stonecutter[facing=north]", "minecraft:grindstone[face=floor,facing=north]",
                 "minecraft:stonecutter[facing=north]", "minecraft:smithing_table", "minecraft:barrel[facing=up]"],
}
COVE_HOUSES = ("dwelling", "canteen", "washhouse", "winch", "toolshed", "crusher", "sorting", "lapidary")
ROLE_FITTINGS.update(COVE_ROLES)
OUT_DIR = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def door_cell(rect, side):
    """The door's column of a house rect (tools/gulch_mine.py house(): the middle of the door side)."""
    x0, z0, x1, z1 = rect
    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
    return {"south": (cx, z1), "north": (cx, z0), "east": (x1, cz), "west": (x0, cz)}[side]


def rect_cols(r):
    return [(x, z) for x in range(r[0], r[2] + 1) for z in range(r[1], r[3] + 1)]


def cove_reach(b):
    """The columns a cove record may write (data geometry.cove): a house its rect and its door's landing steps (up to 3
    out); a headframe, a heap, a pile or a sluice its rect."""
    cols = set(rect_cols(b["rect"]))
    if b["kind"] in COVE_HOUSES:
        dx, dz = OUT_DIR[b["door"]]
        x, z = door_cell(b["rect"], b["door"])
        for k in range(1, 4):
            for s in (-1, 0, 1):
                cols.add((x + dx * k + (s if dz else 0), z + dz * k + (s if dx else 0)))
    return cols


def cove_blocked(m):
    """Columns no cove building may take: the square, the yard, the road, the adit's portal, the gate's wall and ward,
    the lamp posts, each grown by the data's clearances (cove.clear)."""
    spec = m.spec
    cl = spec["cove"]["clear"]
    out = set()

    def grow(cols, r):
        for x, z in cols:
            for a in range(-r, r + 1):
                for b in range(-r, r + 1):
                    out.add((x + a, z + b))
    t = spec["town"]
    grow(rect_cols(t["square"]["rect"]), cl["square"])
    grow(rect_cols(t["yard"]["rect"]), cl["square"])
    grow(road_columns(spec["gate"]["road"]), cl["road"])
    for p in spec["cove"].get("paths", []):
        grow(road_columns(p), cl["road"])
    grow(rect_cols(spec["mine"]["portal"]["open_rect"]), cl["square"])
    grow(band_columns(spec["gate"]["band"]), cl["square"])
    w = spec["gate"]["ward"]
    grow(rect_cols([w[0], w[2], w[3], w[5]]), 0)
    grow([tuple(p) for p in t["lamp_posts"] + spec["gate"]["lamp_posts"]], 1)
    return out


def cove_layout(m):
    """The cove town's buildings grown by accretion (SOUTHERN_RIFT_MEGA.md 13: "The layout follows the cove's shape and
    grows by accretion, not a grid"): each section starts at its seeds and adds one building at a time beside one
    already placed, across an alley of alley[0]..alley[1], at a random offset along the side, of a size in its kind's
    range, turned at random, kept only where every column is in the cove (inside the zone by zone_margin, ground at or
    under max_ground, nothing blocked) and, for a house, its ground spans at most max_range. Deterministic from
    cove.seed. An authoring step (like `trace`): its output is pasted into data cove.buildings, which `build` reads."""
    import random
    spec = m.spec
    cv = spec["cove"]
    rng = random.Random(cv["seed"])
    boxes = zone_boxes(spec["zone"]["polygon"])
    zc = set()
    for b in boxes:
        for x in range(b[0], b[2] + 1):
            for z in range(b[1], b[3] + 1):
                zc.add((x, z))
    zm = cv["zone_margin"]
    inner = {c for c in zc if all((c[0] + a, c[1] + b) in zc for a in (-zm, 0, zm) for b in (-zm, 0, zm))}
    blocked = cove_blocked(m)
    for h in spec["town"]["houses"]:
        blocked |= set(rect_cols(h["rect"]))

    def ok_col(c):
        return (c in inner and c not in blocked and m.X0 + 2 <= c[0] <= m.X1 - 2 and m.Z0 + 2 <= c[1] <= m.Z1 - 2
                and m.ground(*c) <= cv["max_ground"])
    taken = set()
    out = []
    for sec in cv["sections"]:
        kinds = []
        for k in sec["kinds"]:
            kinds += [k] * k["count"]
        placed = []
        n_by_kind = {}
        for k in kinds:
            for _attempt in range(600):
                w = rng.randint(k["size"][0], k["size"][1])
                d = rng.randint(k["size"][2], k["size"][3])
                if rng.random() < 0.5:
                    w, d = d, w
                if placed and rng.random() < (0.25 if k.get("scatter") else 0.9):
                    p = rng.choice(placed)["rect"]
                    side = rng.choice(("north", "south", "east", "west"))
                    gap = rng.randint(cv["alley"][0], cv["alley"][1])
                    if side in ("north", "south"):
                        x0 = rng.randint(p[0] - w + 3, p[2] - 2)
                        z0 = p[1] - gap - d if side == "north" else p[3] + gap + 1
                    else:
                        z0 = rng.randint(p[1] - d + 3, p[3] - 2)
                        x0 = p[0] - gap - w if side == "west" else p[2] + gap + 1
                    toward = {"north": "south", "south": "north", "east": "west", "west": "east"}[side]
                else:
                    sx, sz = rng.choice(sec["seeds"])
                    x0, z0 = sx - w // 2 + rng.randint(-4, 4), sz - d // 2 + rng.randint(-4, 4)
                    toward = None
                rect = [x0, z0, x0 + w - 1, z0 + d - 1]
                cols = rect_cols(rect)
                if not all(ok_col(c) for c in cols):
                    continue
                g = [m.ground(*c) for c in cols]
                if max(g) - min(g) > (cv["max_range"] if k["kind"] in COVE_HOUSES else cv["max_range_open"]):
                    continue
                pad = cv["alley"][0]
                if any((x + a, z + b) in taken for x, z in cols for a in (-pad, 0, pad) for b in (-pad, 0, pad)):
                    continue
                rec = {"id": "%s_%s_%d" % (sec["id"], k["kind"], n_by_kind.get(k["kind"], 0) + 1),
                       "section": sec["id"], "kind": k["kind"], "rect": rect}
                if k["kind"] in COVE_HOUSES:
                    if toward is None:
                        sq = spec["town"]["square"]["centre"]
                        cx, cz = (rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0
                        dx, dz = sq[0] - cx, sq[1] - cz
                        toward = ("east" if dx > 0 else "west") if abs(dx) > abs(dz) else ("south" if dz > 0 else "north")
                    # the door and its landing must be free cove ground too
                    rec["door"] = toward
                    reach = cove_reach(rec) - set(cols)
                    if not all(ok_col(c) and c not in taken for c in reach):
                        continue
                    # the ground just past the steps is no more than 3 under the floor: the last step (floor - 2)
                    # is then one step up from it
                    ddx, ddz = OUT_DIR[toward]
                    dcx, dcz = door_cell(rect, toward)
                    beyond = [(dcx + ddx * 4 + (s if ddz else 0), dcz + ddz * 4 + (s if ddx else 0)) for s in (-1, 0, 1)]
                    if not all(ok_col(c) and c not in taken and m.top(*c) >= max(g) - 3 for c in beyond):
                        continue
                    rec["walls"] = rng.choice(cv["walls"])
                    rec["wall_height"] = rng.randint(k.get("wall_height", [4, 5])[0], k.get("wall_height", [4, 5])[1])
                if k["kind"] == "headframe":
                    rec["height"] = rng.randint(k["height"][0], k["height"][1])
                if k["kind"] in ("spoil_heap", "ore_pile"):
                    rec["height"] = rng.randint(k["height"][0], k["height"][1])
                if k["kind"] == "sluice":
                    rec["head"] = rng.choice(("low", "high"))
                taken |= cove_reach(rec)
                n_by_kind[k["kind"]] = n_by_kind.get(k["kind"], 0) + 1
                placed.append(rec)
                out.append(rec)
                break
    # a lamp post at each house door's side, two out and three along (clear of its steps), where the column is free
    # cove ground with nothing taken round it
    lamps = []
    for b in out:
        if b["kind"] not in COVE_HOUSES:
            continue
        dx, dz = OUT_DIR[b["door"]]
        x, z = door_cell(b["rect"], b["door"])
        c = (x + dx * 2 + (3 if dz else 0), z + dz * 2 + (3 if dx else 0))
        if ok_col(c) and not any((c[0] + a, c[1] + e) in taken for a in (-1, 0, 1) for e in (-1, 0, 1)):
            lamps.append(list(c))
            taken.add(c)
    return out, lamps


def cove_house(m, b):
    """A cove house: tools/gulch_mine.py's rock house, and a landing of steps from its door down to the ground outside."""
    hrec = {"rect": b["rect"], "door": b["door"], "walls": b["walls"], "role": b["kind"], "wall_height": b["wall_height"]}
    house(m, hrec)
    cols = rect_cols(b["rect"])
    floor = max(m.top(x, z) for x, z in cols)
    dx, dz = OUT_DIR[b["door"]]
    x, z = door_cell(b["rect"], b["door"])
    for k in range(1, 4):
        lvl = floor - (k - 1)
        for s in (-1, 0, 1):
            c = (x + dx * k + (s if dz else 0), z + dz * k + (s if dx else 0))
            g = m.top(*c)
            for y in range(g + 1, lvl + 1):
                m.surf[(c[0], y, c[1])] = "minecraft:cobbled_deepslate" if y < lvl else "minecraft:polished_deepslate"


def headframe(m, b):
    """A pit headframe (no timber: the rock town): basalt legs at the rect's corners to `height`, copper girts every 4,
    a copper head with a sheave of iron bars round a copper hub, chains to a capped shaft collar on the ground."""
    x0, z0, x1, z1 = b["rect"]
    cols = rect_cols(b["rect"])
    g0 = max(m.top(x, z) for x, z in cols)
    top = g0 + b["height"]
    for x, z in cols:
        for y in range(m.top(x, z) + 1, g0 + 1):
            m.surf[(x, y, z)] = "minecraft:cobbled_deepslate"
    for x, z in ((x0, z0), (x0, z1), (x1, z0), (x1, z1)):
        for y in range(g0 + 1, top + 1):
            m.surf[(x, y, z)] = "minecraft:polished_basalt[axis=y]"
    for y in range(g0 + 4, top + 1, 4):
        for x in range(x0 + 1, x1):
            m.surf[(x, y, z0)] = "minecraft:waxed_cut_copper"
            m.surf[(x, y, z1)] = "minecraft:waxed_cut_copper"
        for z in range(z0 + 1, z1):
            m.surf[(x0, y, z)] = "minecraft:waxed_cut_copper"
            m.surf[(x1, y, z)] = "minecraft:waxed_cut_copper"
    for x, z in cols:
        m.surf[(x, top + 1, z)] = "minecraft:waxed_cut_copper_slab[type=bottom,waterlogged=false]"
    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
    along_x = (x1 - x0) >= (z1 - z0)
    for a in (-1, 0, 1):
        for h in (1, 2, 3):
            c = (cx + a, top + 1 + h, cz) if along_x else (cx, top + 1 + h, cz + a)
            m.surf[c] = "minecraft:waxed_copper_block" if (a == 0 and h == 2) else "minecraft:iron_bars"
    for y in range(g0 + 2, top + 1):
        m.surf[(cx, y, cz)] = "minecraft:chain[axis=y]"
    for a in (-1, 0, 1):
        for e in (-1, 0, 1):
            if a or e:
                m.surf[(cx + a, g0 + 1, cz + e)] = "minecraft:stone_bricks"
    m.surf[(cx, g0 + 1, cz)] = "minecraft:iron_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]"


def heap(m, b, palette_key):
    """A spoil heap or an ore pile: a cone over the rect's centre, height `height` at the middle falling to 0 at the
    rect's inscribed circle, one block of h32 noise; blocks from the data's palette."""
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    x0, z0, x1, z1 = b["rect"]
    cx, cz = (x0 + x1) / 2.0, (z0 + z1) / 2.0
    r = min(x1 - x0, z1 - z0) / 2.0 + 0.5
    for x, z in rect_cols(b["rect"]):
        q = math.hypot(x - cx, z - cz) / r
        if q > 1:
            continue
        hgt = int(math.floor(b["height"] * (1 - q) + 0.5)) + (h32(seed, x, z, 91) % 2 if q < 0.8 else 0)
        g = m.top(x, z)
        for y in range(g + 1, g + hgt + 1):
            m.surf[(x, y, z)] = pick(pal[palette_key], seed, x, y, z, 92)


def sluice(m, b):
    """A dry sluice (no fluid: the audit forbids one): a trough along the rect's long axis on basalt trestles, stone
    brick sides, a smooth floor with iron-trapdoor riffles every 2, a water cauldron at its head."""
    x0, z0, x1, z1 = b["rect"]
    along_x = (x1 - x0) >= (z1 - z0)
    L = (x1 - x0 + 1) if along_x else (z1 - z0 + 1)
    cols = rect_cols(b["rect"])
    base = max(m.top(x, z) for x, z in cols)
    for i in range(L):
        t = i if b["head"] == "low" else L - 1 - i
        rise = 1 + (t * 2) // max(1, L - 1)             # the head stands 2 higher than the foot
        for j in range(3):
            x, z = (x0 + i, z0 + j) if along_x else (x0 + j, z0 + i)
            g = m.top(x, z)
            fl = base + rise
            if i % 4 == 0 or i == L - 1:
                for y in range(g + 1, fl):
                    m.surf[(x, y, z)] = "minecraft:polished_basalt[axis=y]"
            if j == 1:
                m.surf[(x, fl, z)] = "minecraft:smooth_stone"
                if i % 2 == 1:
                    m.surf[(x, fl + 1, z)] = "minecraft:iron_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]"
            else:
                m.surf[(x, fl, z)] = "minecraft:stone_bricks"
                m.surf[(x, fl + 1, z)] = "minecraft:stone_brick_wall"
    hx, hz = ((x1 if b["head"] == "low" else x0), z0 + 1) if along_x else (x0 + 1, (z1 if b["head"] == "low" else z0))
    top_head = base + 3
    m.surf[(hx, top_head + 1, hz)] = "minecraft:water_cauldron[level=3]"


def cove_build(m):
    cv = m.spec.get("cove")
    if not cv:
        return
    for b in cv["buildings"]:
        k = b["kind"]
        if k in COVE_HOUSES:
            cove_house(m, b)
        elif k == "headframe":
            headframe(m, b)
        elif k == "spoil_heap":
            heap(m, b, "spoil")
        elif k == "ore_pile":
            heap(m, b, "ore")
        elif k == "sluice":
            sluice(m, b)
        else:
            raise GulchError("cove: %s is of no kind the builder knows (%s)" % (b["id"], k))
    for x, z in cv["lamp_posts"]:
        yy = m.top(x, z)
        m.surf[(x, yy + 1, z)] = "minecraft:cobbled_deepslate_wall"
        m.surf[(x, yy + 2, z)] = "minecraft:cobbled_deepslate_wall"
        m.surf[(x, yy + 3, z)] = LANTERN_STAND


def wall_top(g, x, z, j, d, seed):
    """The rockslide's top over column (x, z), claimed by ring point j at offset d (data geometry.band): the plug's flat
    top in the plug's columns; elsewhere the crest line less a jag of 0..jag-1 (h32 of the column), less `batter` per
    block outward past the core (the talus on the plateau side)."""
    wall, pl = g["band"]["wall"], g["plug"]
    if abs(j) <= pl["half_j"]:
        return pl["top_y"]
    crest = int(math.floor(wall_crest(g["band"], j) + 0.5)) - h32(seed, x, z, 63) % wall["jag"]
    return crest - wall["batter"] * max(0, -d - wall["core"])


def gate_build(m):
    g = m.spec["gate"]
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    band = band_cells(g["band"])
    wall = g["band"]["wall"]
    pl = g["plug"]
    n_rock = 0
    for (x, z), (j, d) in sorted(band.items()):
        if not (m.X0 <= x <= m.X1 and m.Z0 <= z <= m.Z1):
            raise GulchError("the rockfall column (%d, %d) is outside the grid" % (x, z))
        in_plug = abs(j) <= pl["half_j"]
        if in_plug and x > pl["max_x"] and pl["trim_z"][0] <= z <= pl["trim_z"][1]:
            continue                     # the gate's slot: the plug's face is flat by the grille, in one plane (data gate.plug)
        base = m.top(x, z)
        top = wall_top(g, x, z, j, d, seed)
        if base >= top:
            continue                     # a crag column already stands higher than the wall would
        topy = max(top, base + wall["min_rise"])
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
    for b in spec.get("cove", {}).get("buildings", []):
        if b["kind"] in COVE_HOUSES:
            x, z = door_cell(b["rect"], b["door"])
            must["%s's door" % b["id"]] = [(x, max(m.top(*c) for c in rect_cols(b["rect"])) + 1, z)]
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
    band = band_columns(g["band"])      # once: inside the comprehension it was rebuilt per cell, 260 of the build's 270 s
    cols |= {(x, z) for x, _y, z in list(m.surf) + list(m.fit) if m.spec["town"]["square"] and (x, z) not in band}
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
    }
    # the Mega farms' zone checks (SOUTHERN_RIFT_MEGA.md 13): the same flag, each farm its own boxes and turn-back point
    for fa in spec.get("farms", []):
        fz = fa["zone"]
        fboxes = zone_boxes(fz["polygon"])
        fzone = [box_cond((b[0], zmin, b[1]), (b[2], zmax, b[3])) for b in fboxes]
        files["advancement/%s/farm_%s_zone.json" % (FOLDER, fa["id"])] = adv(
            [{"condition": "minecraft:any_of", "terms": fzone}], "%s/farms/%s/zone" % (F, fa["id"]))
        bx, by, bz, byaw = fz["turn_back"]
        fn["farms/%s/zone" % fa["id"]] = [
            "# %s's zone check: anyone in it without %s is turned back to the data's point outside it" % (fa["id"], flag),
            "advancement revoke @s only %s:%s/farm_%s_zone" % (NS, FOLDER, fa["id"]),
            "execute if entity %s run function %s/farms/%s/turn_back" % (lacks, F, fa["id"])]
        fn["farms/%s/turn_back" % fa["id"]] = [
            "execute on vehicle run tp @s %s %d %s" % (bx, by, bz),
            "tp @s %s %d %s %d 0" % (bx, by, bz, byaw),
            "title @s actionbar %s" % text("Turned back: %s is closed until the %s badge." % (fa["name"], ordinal(badge)), color="gold")]
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


STORE = "cobblers:gulch_mine"          # the dens' Pokemon UUIDs and the hitters' UUIDs (farm dens only)


def den_level(spec, site, d):
    """A den's Mega's level: its own, else its farm tier's (data farm_tiers[].level; the mine's slots state their own)."""
    if "level" in d:
        return d["level"]
    farm = next(f for f in spec["farms"] if f["id"] == site)
    return spec["farm_tiers"][d.get("tier", farm["tier"])]["level"]


def dens(spec):
    """[(site, den)]: the mine's slots (site "mine"), then each farm's dens (site = the farm's id)."""
    out = [("mine", s) for s in spec["megas"]["slots"]]
    for fa in spec.get("farms", []):
        out += [(fa["id"], d) for d in fa["dens"]]
    return out


def den_anchor(d):
    """A den's anchor [x, y, z]: the model's `_anchor` for a mine slot (its hall's floor), the data's own for a farm den."""
    return d["_anchor"] if "_anchor" in d else d["anchor"]


def den_rules(spec, site, d):
    """(respawn ticks, drop percent) for a den: a mine slot has the data's megas.respawn_ticks and no drop; a farm den
    its tier's (data farm_tiers), unless the den states its own."""
    if site == "mine":
        return d.get("respawn_ticks", spec["megas"]["respawn_ticks"]), 0
    fa = next(f for f in spec["farms"] if f["id"] == site)
    tier = spec["farm_tiers"][d.get("tier", fa["tier"])]
    return d.get("respawn_ticks", tier["respawn_ticks"]), d.get("drop_percent", tier["drop_percent"])


def site_near(spec, site):
    """The selector for a player inside a site's approach box (data driver.approach, farms[].approach)."""
    ap = spec["driver"]["approach"] if site == "mine" else next(f for f in spec["farms"] if f["id"] == site)["approach"]
    return "@a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d]" % (ap[0], ap[1], ap[2], ap[3] - ap[0], ap[4] - ap[1], ap[5] - ap[2])


def face_ward_box(spec, f):
    x0, y0, z0, x1, y1, z1 = f["box"]
    w = spec["faces"]["ward_margin"]
    return [x0 - w, y0 - w, z0 - w, x1 + w, y1 + w, z1 + w]


def keeper_files(m):
    """The tick driver: the wards, the Megas' keeper, leash, respawn clock and drop roll (SOUTHERN_RIFT_MEGA.md 13)."""
    spec = m.spec
    F = "%s:%s" % (NS, FOLDER)
    mg = spec["megas"]
    tag = mg["tag"]
    farm_tag = mg["farm_tag"]
    all_dens = dens(spec)
    sites = ["mine"] + [f["id"] for f in spec.get("farms", [])]
    fn = {}
    load = ["# the gulch mine's driver state (tools/gulch_mine.py): scores survive a restart in the world's scoreboard.",
            "# The respawn clock of each den (#<den> gm.gone, the game time its Mega was first seen gone; -1 while one is",
            "# there) is set here only when it has never been set, so a restart never moves it",
            "scoreboard objectives add gm.t dummy", "scoreboard objectives add gm.gone dummy",
            "scoreboard objectives add gm.abs dummy", "scoreboard objectives add gm.alive dummy",
            "scoreboard objectives add gm.hit dummy", "scoreboard objectives add gm.resp dummy",
            "scoreboard objectives add gm.pct dummy",
            "# retired with the faces' restore and the owed Megas (SOUTHERN_RIFT_MEGA.md 13)",
            "scoreboard objectives remove gm.last", "scoreboard objectives remove gm.var",
            "scoreboard objectives remove gm.owe",
            "scoreboard players set #16 gm.t 16"]
    if any(s_ != "mine" for s_, _d in all_dens):
        # the farm dens' storage (the drop roll): hex digits for megas/pid, and the dens' UUID list, kept across restarts
        load += ["data modify storage %s hex set value %s" % (STORE, json.dumps(list("0123456789abcdef"))),
                 "execute unless data storage %s dens run data modify storage %s dens set value []" % (STORE, STORE)]
    for site, d in all_dens:
        resp, pct = den_rules(spec, site, d)
        i = d["id"]
        load += ["scoreboard players set #%s gm.resp %d" % (i, resp),
                 "execute unless score #%s gm.gone matches -2147483648.. run scoreboard players set #%s gm.gone 0" % (i, i),
                 "execute unless score #%s gm.abs matches -2147483648.. run scoreboard players set #%s gm.abs 0" % (i, i)]
        if site != "mine":
            load += ["scoreboard players set #%s gm.pct %d" % (i, pct),
                     "execute unless score #%s gm.alive matches -2147483648.. run scoreboard players set #%s gm.alive 0" % (i, i),
                     "execute unless score #%s gm.hit matches -2147483648.. run scoreboard players set #%s gm.hit -1" % (i, i)]
    fn["load"] = load
    wd = spec["gate"]["ward"]
    tick = ["# the gate's ward every tick, not only when its location trigger fires (every 20 ticks): milk clears Mining",
            "# Fatigue at once (the test author's gate-clock sweep, contract C14)",
            "execute as @a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d,gamemode=!creative,gamemode=!spectator] run effect give @s "
            "minecraft:mining_fatigue 3 3 true" % (wd[0], wd[1], wd[2], wd[3] - wd[0], wd[4] - wd[1], wd[5] - wd[2]),
            "# the crystal faces are scenery, warded for good (SOUTHERN_RIFT_MEGA.md 13: the restore cycle is retired)"]
    for f in spec["mine"]["faces"]:
        b = face_ward_box(spec, f)
        tick.append("execute as @a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d,gamemode=!creative,gamemode=!spectator] run effect give @s "
                    "minecraft:mining_fatigue 3 3 true" % (b[0], b[1], b[2], b[3] - b[0], b[4] - b[1], b[5] - b[2]))
    if any(s_ != "mine" for s_, _d in dens(spec)):
        # only with a farm den: megas/watch is generated only then, and a tick naming a missing function fails to load
        # whole (the gate, the keeper and the ward with it)
        tick += ["# who is hurting a farm Mega (megas/watch; a kill outside a battle is settled from it by the keeper)",
                 "execute as @e[type=cobblemon:pokemon,tag=%s] run function %s/megas/watch" % (farm_tag, F)]
    tick += ["# two counters; the keeper and the leash run only where a player is near (SOUTHERN_RIFT_MEGA.md 6.2)",
             "scoreboard players add #clock gm.t 1",
             "scoreboard players add #leash gm.t 1",
             "execute if score #leash gm.t matches %d.. run function %s/leash" % (mg["leash_every_ticks"], F),
             "execute if score #clock gm.t matches %d.. run function %s/drive" % (spec["driver"]["every_ticks"], F)]
    fn["tick"] = tick
    drive = ["scoreboard players set #clock gm.t 0",
             "execute store result score #now gm.t run time query gametime"]
    leash = ["scoreboard players set #leash gm.t 0"]
    for site in sites:
        drive.append("execute if entity %s run function %s/drive_%s" % (site_near(spec, site), F, site))
        leash.append("execute if entity %s run function %s/leash_%s" % (site_near(spec, site), F, site))
        fn["drive_%s" % site] = ["function %s/megas/keep_%s" % (F, d["id"]) for s_, d in all_dens if s_ == site]
        fn["leash_%s" % site] = []
        for s_, d in all_dens:
            if s_ != site:
                continue
            x, y, z = den_anchor(d)
            fn["leash_%s" % site].append(
                "execute as @e[type=cobblemon:pokemon,tag=%s.%s] positioned %d %d %d unless entity @s[distance=..%d] "
                "run tp @s %d %d %d" % (tag, d["id"], x, y, z, d["leash"], x, y, z))
    fn["drive"] = drive
    fn["leash"] = leash
    # EXP-046: `spawnpokemonat` written in a function spawns nothing when the function was parsed at server start, and
    # works once a /reload has parsed it again; a macro line is parsed when it runs (.claude/rules/datapacks.md)
    fn["megas/spawn_at"] = ["$spawnpokemonat $(x) $(y) $(z) $(species) $(aspect) uncatchable level=$(level)"]
    for site, d in all_dens:
        x, y, z = den_anchor(d)
        i = d["id"]
        t = "%s.%s" % (tag, i)
        farm = site != "mine"
        fn["megas/keep_%s" % i] = [
            "# den %s (%s): one Mega, kept; when it is gone, the respawn clock (SOUTHERN_RIFT_MEGA.md 13): it comes back" % (i, site),
            "# gm.resp ticks after it was first seen gone, with nobody within %d of its anchor. Nothing a player can" % mg["spawn_clear"],
            "# repeat moves the clock: only a Mega seen in the den clears it, and only this keeper starts it",
            "execute unless loaded %d %d %d run scoreboard players set #%s gm.abs 0" % (x, y, z, i),
            "execute unless loaded %d %d %d run return 0" % (x, y, z),
            "execute store result score #n gm.t if entity @e[type=cobblemon:pokemon,tag=%s]" % t,
            "# a duplicate (a spawn that raced a slow entity load): the one furthest from the anchor goes",
            "execute if score #n gm.t matches 2.. positioned %d %d %d run kill @e[type=cobblemon:pokemon,tag=%s,limit=1,sort=furthest]"
            % (x, y, z, t),
            "execute if score #n gm.t matches 1.. run scoreboard players set #%s gm.abs 0" % i,
            "execute if score #n gm.t matches 1.. run scoreboard players operation #%s gm.alive = #now gm.t" % i,
            "execute if score #n gm.t matches 1.. run scoreboard players set #%s gm.gone -1" % i,
            "execute if score #n gm.t matches 1.. run return 0",
            "# absent on two passes in a row (entities load a moment after their chunk) before it counts as gone",
            "scoreboard players add #%s gm.abs 1" % i,
            "execute if score #%s gm.abs matches ..1 run return 0" % i,
            "execute if score #%s gm.gone matches -1 run function %s/megas/gone_%s" % (i, F, i),
            "scoreboard players operation #d gm.t = #now gm.t",
            "scoreboard players operation #d gm.t -= #%s gm.gone" % i,
            "execute if score #d gm.t < #%s gm.resp run return 0" % i,
            "execute if entity @a[x=%d,y=%d,z=%d,distance=..%d] run return 0" % (x, y, z, mg["spawn_clear"]),
            "function %s/megas/spawn_%s" % (F, i)]
        gone = ["# first seen gone: the clock starts now",
                "scoreboard players operation #%s gm.gone = #now gm.t" % i]
        if farm:
            gone += ["# killed outside a battle by a player or a player's Pokemon: they hurt it after it was last seen alive",
                     "execute if score #%s gm.hit >= #%s gm.alive run function %s/drops/slain_%s" % (i, i, F, i)]
        fn["megas/gone_%s" % i] = gone
        fn["megas/spawn_%s" % i] = [
            "# a wild Mega: its species, the Mega aspect, uncatchable, through the macro (EXP-046), claimed at once",
            "function %s/megas/spawn_at {x:%d,y:%d,z:%d,species:\"%s\",aspect:\"%s\",level:%d}"
            % (F, x, y, z, d["species"], d["aspect"], den_level(spec, site, d)),
            "execute positioned %d %d %d as @e[type=cobblemon:pokemon,tag=!%s,distance=..2,limit=1,sort=nearest] run function %s/megas/bind_%s"
            % (x, y, z, tag, F, i),
            "scoreboard players set #%s gm.gone -1" % i,
            "scoreboard players set #%s gm.abs 0" % i]
        bind = ["tag @s add %s" % tag, "tag @s add %s" % t]
        if farm:
            bind.append("tag @s add %s" % farm_tag)
        bind.append("data merge entity @s {PersistenceRequired:1b}")
        if farm:
            bind += ["# its Pokemon UUID as text, the den's, for the battle_fainted callback (the entity is gone by then)",
                     "function %s/megas/pid" % F,
                     "data remove storage %s dens[{id:\"%s\"}]" % (STORE, i),
                     "data modify storage %s dens append value {id:\"%s\"}" % (STORE, i),
                     "data modify storage %s dens[{id:\"%s\"}].pid set from storage %s pid.s" % (STORE, i, STORE),
                     "scoreboard players set #%s gm.hit -1" % i,
                     "scoreboard players operation #%s gm.alive = #now gm.t" % i]
        fn["megas/bind_%s" % i] = bind
        if not farm:
            continue
        fn["megas/hit_%s" % i] = [
            "execute store result score #%s gm.hit run time query gametime" % i,
            "# (guarded: a filtered set that matches nothing appends a new element)",
            "execute if data storage %s dens[{id:\"%s\"}] run data modify storage %s dens[{id:\"%s\"}].who set from entity "
            "@a[tag=cobblers.gm_slayer,limit=1] UUID" % (STORE, i, STORE, i)]
        pct_line = ["execute store result score #r gm.t run random value 1..100",
                    "execute if score #r gm.t > #%s gm.pct run return 0" % i]
        fn["drops/roll_%s" % i] = [
            "# a battle win over den %s's Mega: its UUID is spent (one roll per Mega), then gm.pct in 100" % i,
            "data remove storage %s dens[{id:\"%s\"}].pid" % (STORE, i)] + pct_line + [
            "$execute as $(who) at @s run function %s/drops/give" % F]
        fn["drops/slain_%s" % i] = [
            "# den %s's Mega killed outside a battle: one roll per Mega (its UUID not yet spent), for the player who hurt it" % i,
            "execute unless data storage %s dens[{id:\"%s\"}].pid run return 0" % (STORE, i),
            "execute unless data storage %s dens[{id:\"%s\"}].who run return 0" % (STORE, i),
            "data remove storage %s dens[{id:\"%s\"}].pid" % (STORE, i)] + pct_line + [
            "execute as @a run function %s/drops/hitter_%s" % (F, i)]
        fn["drops/hitter_%s" % i] = [
            "# as each player: the one whose UUID is the hitter's gets the drop (a set that changes nothing succeeds 0)",
            "data modify storage %s me set from entity @s UUID" % STORE,
            "execute store success score #diff gm.t run data modify storage %s me set from storage %s dens[{id:\"%s\"}].who"
            % (STORE, STORE, i),
            "execute if score #diff gm.t matches 0 at @s run function %s/drops/give" % F]
    farm_dens = [d for s_, d in all_dens if s_ != "mine"]
    if not farm_dens:
        # the drop roll's functions and its callback exist only with a farm den to serve: with none (the farms wait on
        # the owner's zone decision) they would be functions nothing runs, which prepare refuses
        return fn
    fn["megas/watch"] = [
        "# as a farm Mega, every tick: its attacker, if a player or a player's Pokemon, is noted on its den",
        "# (tools/blackout_pack.py recovery/watch's pattern; vanilla keeps the attacker 100 ticks past the last blow)",
        "tag @a remove cobblers.gm_slayer",
        "execute on attacker if entity @s[type=player] run tag @s add cobblers.gm_slayer",
        "execute on attacker if entity @s[type=cobblemon:pokemon] on owner if entity @s[type=player] run tag @s add cobblers.gm_slayer",
        "execute unless entity @a[tag=cobblers.gm_slayer] run return 0"] + [
        "execute if entity @s[tag=%s.%s] run function %s/megas/hit_%s" % (tag, d["id"], F, d["id"]) for d in farm_dens] + [
        "tag @a remove cobblers.gm_slayer"]
    fn["drops/fainted"] = [
        "# from data/cobblemon/callbacks/battle_fainted/cobblers_gulch_drops.molang: $(pid) the fainted wild Pokemon's UUID",
        "# as text, $(who) the first player in the battle. A farm den's Mega, matched by the UUID its bind stored, rolls"] + [
        "$execute if data storage %s dens[{id:\"%s\",pid:\"$(pid)\"}] run return run function %s/drops/roll_%s {who:\"$(who)\"}"
        % (STORE, d["id"], F, d["id"]) for d in farm_dens]
    dr = spec["drops"]
    fn["drops/give"] = [
        "# as the victor, at their feet: one raw stone only they can pick up (vanilla 1.21.1 ItemEntity: Owner)",
        "summon minecraft:item ~ ~ ~ {Item:{id:\"%s\",count:%d},PickupDelay:0,Tags:[\"cobblers.gm_drop_new\"]}" % (dr["item"], dr["count"]),
        "data modify entity @e[type=minecraft:item,tag=cobblers.gm_drop_new,limit=1,sort=nearest] Owner set from entity @s UUID",
        "tag @e[type=minecraft:item,tag=cobblers.gm_drop_new] remove cobblers.gm_drop_new",
        "title @s actionbar %s" % text(dr["message"], color="gray")]
    # a Pokemon's UUID as the text Cobblemon's MoLang `pokemon.id` gives (tools/blackout_pack.py recovery/pid): each int's
    # eight hex digits, least significant first (scoreboard %= and /= floor, so a negative int's two's complement digits
    # come out right), joined 8-4-4-4-12
    pid = ["# as a Pokemon entity: its Pokemon UUID as text, into %s pid.s" % STORE]
    pid += ["execute store result score #u%d gm.t run data get entity @s Pokemon.UUID[%d]" % (w, w) for w in range(4)]
    for w in range(4):
        for p in range(7, -1, -1):
            pid += ["scoreboard players operation #n gm.t = #u%d gm.t" % w,
                    "scoreboard players operation #n gm.t %= #16 gm.t",
                    "execute store result storage %s hx.i int 1 run scoreboard players get #n gm.t" % STORE,
                    'data modify storage %s hx.k set value "c%d%d"' % (STORE, w, p),
                    "function %s/megas/pid_hex with storage %s hx" % (F, STORE),
                    "scoreboard players operation #u%d gm.t /= #16 gm.t" % w]
    pid.append("function %s/megas/pid_join with storage %s px" % (F, STORE))
    fn["megas/pid"] = pid
    fn["megas/pid_hex"] = ["$data modify storage %s px.$(k) set from storage %s hex[$(i)]" % (STORE, STORE)]
    dd = lambda w, ps: "".join("$(c%d%d)" % (w, p) for p in ps)
    fn["megas/pid_join"] = ['$data modify storage %s pid.s set value "%s-%s-%s-%s-%s%s"' % (
        STORE, dd(0, range(8)), dd(1, range(4)), dd(1, range(4, 8)), dd(2, range(4)), dd(2, range(4, 8)), dd(3, range(8)))]
    return fn


def callback_files(spec):
    """The battle_fainted callback (Cobblemon fires callbacks only from data/cobblemon/callbacks/<event>/, a cobblers_
    file: .claude/rules/datapacks.md, EXP-042). tools/blackout_pack.py's own battle_fainted file is the working model.
    None while no farm den exists: it would call a roll that is not built."""
    if not any(s_ != "mine" for s_, _d in dens(spec)):
        return {}
    return {"data/cobblemon/callbacks/battle_fainted/cobblers_gulch_drops.molang": "\n".join([
        "'Generated by tools/gulch_mine.py. A wild Pokemon fainting in battle: if it is a farm den Mega (matched by its';",
        "'Pokemon UUID, stored when it was spawned), its raw-stone drop is rolled for the first player in the battle.';",
        "c.pokemon.actor.is_wild ? {",
        "  t.pk = c.pokemon.pokemon;",
        "  t.pid = t.pk.id;",
        "  t.done = 0;",
        "  for_each(t.a, c.players, {",
        "    t.done == 0 ? {",
        "      t.pl = t.a.player;",
        "      q.run_command('function %s:%s/drops/fainted {pid:\"' + t.pid + '\",who:\"' + t.pl.uuid + '\"}');" % (NS, FOLDER),
        "      t.done = 1;",
        "    };",
        "  });",
        "};",
        ""])}


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
    for rel, body in callback_files(m.spec).items():
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
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
                     "crystals in the faces": sum(f["crystals"] for f in spec["mine"]["faces"])})
    for h in spec["mine"]["halls"]:
        cols = m.hall_cols[h["id"]]
        m.counts["%s columns" % h["id"]] = len(cols)
        m.counts["%s air cells" % h["id"]] = sum(t - f + 1 for f, t in cols.values())
    return m, near, tops


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("trace", "layout", "report", "build"))
    p.add_argument("--source-root")
    p.add_argument("--map", action="store_true", help="layout: draw the cove's layout on stderr")
    p.add_argument("--fresh-layout", action="store_true", help="report: check a fresh `layout` instead of the data's")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    spec = load()
    if a.mode == "trace":
        print(json.dumps(trace(spec, a.source_root)))
        return 0
    if a.mode == "layout":
        m = Model(spec, G.Ground(a.source_root))
        earthworks(m)
        out, lamps = cove_layout(m)
        by = {}
        for b in out:
            by[(b["section"], b["kind"])] = by.get((b["section"], b["kind"]), 0) + 1
        for k, v in sorted(by.items()):
            print("#  %-12s %-12s %d" % (k[0], k[1], v), file=sys.stderr)
        if a.map:
            # a picture of the layout, 2 blocks a character: letters buildings, o the square and yard, = the road,
            # - the cove's floor left free, blank anything else
            letter = {"dwelling": "d", "canteen": "C", "washhouse": "w", "winch": "W", "toolshed": "t", "crusher": "X",
                      "sorting": "S", "lapidary": "L", "headframe": "H", "spoil_heap": "h", "ore_pile": "p", "sluice": "s"}
            cell = {}
            for b in out:
                for c in rect_cols(b["rect"]):
                    cell[c] = letter[b["kind"]]
            for x, z in lamps:
                cell[(x, z)] = "*"
            t = spec["town"]
            for r in (t["square"]["rect"], t["yard"]["rect"]):
                for c in rect_cols(r):
                    cell[c] = "o"
            for c in road_columns(spec["gate"]["road"]):
                cell[c] = "="
            boxes = zone_boxes(spec["zone"]["polygon"])
            for z in range(m.Z0, m.Z1 + 1, 2):
                row = []
                for x in range(m.X0, m.X1 + 1, 2):
                    ch = cell.get((x, z)) or cell.get((x + 1, z)) or cell.get((x, z + 1))
                    if ch is None:
                        inz = any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for b in boxes)
                        gy = m.ground(x, z)
                        # free cove floor as its ground's last digit, so a scarp shows
                        # and zone ground above the cove as a letter, a for y97-98, b for y99-100, ...
                        ch = str(gy % 10) if inz and gy <= spec["cove"]["max_ground"] else (
                            chr(ord("a") + min(25, (gy - 97) // 2)) if inz else " ")
                    row.append(ch)
                print("%4d %s" % (z, "".join(row)), file=sys.stderr)
        # printed as data/gulch_mine.json keeps it: a building a line, under cove
        print('    "buildings": [\n' + ",\n".join("      " + json.dumps(b) for b in out) + "\n    ],")
        print('    "lamp_posts": ' + json.dumps(lamps))
        return 0
    if a.fresh_layout:
        if a.mode != "report":
            raise SystemExit("--fresh-layout is for report only: build reads the data's cove.buildings")
        lm = Model(spec, G.Ground(a.source_root))
        earthworks(lm)
        spec["cove"]["buildings"], spec["cove"]["lamp_posts"] = cove_layout(lm)
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
