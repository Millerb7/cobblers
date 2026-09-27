#!/usr/bin/env python
"""The Rift dig camp as a mining town, and the mega stone seam in its spur, from data/rift_mines.json.

The owner, 2026-09-27: "THE RIFT MINING TOWN LARGER - small caving systems, quarries, worked faces". The mega stone
mine first built here moved to the gulch the same day (docs/world-building/SOUTHERN_RIFT_MEGA.md decisions 1-2,
data/gulch_mine.json): the camp keeps its seam, found early and not usable yet. The data file says which town this is
(the dig camp, not the Craters' mining town) and why; this tool only builds what it says.

One voxel model over the spur, ground from tools/ground.py (the canonical heightmap, rounded; never a world):

  envelope   every cut (the seam cut, the quarries, the worked face), tube (adit, decline, drifts), room (the adit
             hall), shaft and pocket (drift ends), rasterised as data/rift_mines.json `geometry` defines them
  carve      the envelope
  shell      every cell within 2 of the envelope, not carved, at or under the ground: written as rock, so nothing this
             build opens is bounded by anything it did not write (natural caves, the export's gravel)
  fittings   frames, lanterns, rails (powered rail: see the data's rail_why), the collapse at the decline's foot, the
             company grille across drift C and the one crystal's face behind it
  surface    Forge Row, its rock houses, lamp posts, ore piles, derricks and the headframe over the shaft

The tease (data `mine.tease`): one mega_stone_crystal in the seam at the end of the prospect drift, behind a grille.
The pack's ward advancement gives anyone in survival or adventure who lacks the flag (data `flag`, gym6_cleared)
Mining Fatigue IV near it; with the flag it lifts for that player. The crystal's face restores on approach once a day
(the pack's own tick driver, STONE_ECONOMY.md 5.3).

  python tools/rift_mines.py report [--source-root DIR]     the model's checks and counts; nothing written
  python tools/rift_mines.py build  [--source-root DIR]     -> build/datapacks/cobblers_rift_mines, derived/rift_mines/plan.json,
                                                            and build/datapacks/cobblers_rift_mines_refill (STAGING ONLY: rock
                                                            back into the retired gated section, retired_gated_section)

The offline audit, independent of this tool's model, is tools/rift_mines_audit.py.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "rift_mines.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_rift_mines"
PLAN = ROOT / "derived" / "rift_mines" / "plan.json"
REFILL = ROOT / "build" / "datapacks" / "cobblers_rift_mines_refill"
NS = "cobblers"
FOLDER = "rift_mines"
TAG = "cobblers_rift_mines"
TILE = 64
PART = 3500
PASSES = ("shell", "air", "fittings", "surface")
AIR = "minecraft:air"
SHELL_R = 2
CLEAR_ABOVE = 6          # a cut is cleared this far over the ground (the Rift skin's lumps and crystals stand on it)
ROUGH = 0.3


class MineError(Exception):
    pass


def rnd(v):
    """Round half up, the way the data's geometry says (never Python's banker's rounding)."""
    return int(math.floor(v + 0.5))


def h32(*vals):
    a = 0x811C9DC5
    for v in vals:
        a = ((a ^ (int(v) & 0xFFFFFFFF)) * 0x01000193) & 0xFFFFFFFF
        a ^= a >> 15
        a = (a * 0x2C1B3C6D) & 0xFFFFFFFF
        a ^= a >> 12
    return a


def u(*vals):
    return h32(*vals) / 4294967296.0


def pick(pal, *key):
    return pal[h32(*key) % len(pal)]


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the model

class Model:
    def __init__(self, spec, ground):
        self.spec = spec
        gx, gz, gy = spec["grid"]["x"], spec["grid"]["z"], spec["grid"]["y"]
        self.X0, self.X1, self.Z0, self.Z1, self.Y0, self.Y1 = gx[0], gx[1], gz[0], gz[1], gy[0], gy[1]
        self.nx, self.nz, self.ny = self.X1 - self.X0 + 1, self.Z1 - self.Z0 + 1, self.Y1 - self.Y0 + 1
        self.S0 = ground.box(self.X0, self.Z0, self.X1, self.Z1).T.copy()       # (x, z) ground Y
        shape = (self.nx, self.nz, self.ny)
        self.env = np.zeros(shape, bool)
        self.own = np.full(shape, -1, np.int16)
        self.gated = np.zeros(shape, bool)
        self.carve = None
        self.feats = []                      # feature records, index = own id
        self.cut_floor = np.full((self.nx, self.nz), 9999, np.int32)   # y_f where a cut lowers the ground
        self.cut_of = np.full((self.nx, self.nz), -1, np.int16)
        self.blocks = {}                     # (x, y, z) -> block, the shell's rock
        self.fit = {}                        # (x, y, z) -> block, written after the air
        self.surf = {}                       # (x, y, z) -> block, written last
        self.problems = []

    # -- coordinates
    def ix(self, x, y, z):
        return x - self.X0, z - self.Z0, y - self.Y0

    def inside(self, x, y, z):
        return self.X0 <= x <= self.X1 and self.Z0 <= z <= self.Z1 and self.Y0 <= y <= self.Y1

    def ground(self, x, z):
        return int(self.S0[x - self.X0, z - self.Z0])

    def top(self, x, z):
        """The walkable top block of a column after the cuts: a cut's floor where it lowers the ground."""
        i, k = x - self.X0, z - self.Z0
        return int(min(self.S0[i, k], self.cut_floor[i, k]))

    def is_carved(self, x, y, z):
        return self.inside(x, y, z) and bool(self.carve[self.ix(x, y, z)])

    def add_feature(self, rec, gated):
        self.feats.append(rec)
        return len(self.feats) - 1

    def mark(self, x, y, z, fid, gated):
        if not self.inside(x, y, z):
            raise MineError("%s reaches (%d, %d, %d), outside the grid %s"
                            % (self.feats[fid]["id"], x, y, z, self.spec["grid"]))
        i, k, j = self.ix(x, y, z)
        self.env[i, k, j] = True
        if self.own[i, k, j] < 0:
            self.own[i, k, j] = fid
        if gated:
            self.gated[i, k, j] = True


# ------------------------------------------------------------------ rasterising (data/rift_mines.json `geometry`)

def tube_cells(path, r, height):
    out = set()
    for (x0, y0, z0), (x1, y1, z1) in zip(path, path[1:]):
        L = math.hypot(x1 - x0, z1 - z0)
        n = int(math.ceil(4 * L)) + 1 if L > 0 else 1
        for s in range(n):
            t = s / (n - 1) if n > 1 else 0.0
            cx, cz, feet = rnd(x0 + (x1 - x0) * t), rnd(z0 + (z1 - z0) * t), rnd(y0 + (y1 - y0) * t)
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    for y in range(feet, feet + height):
                        out.add((cx + dx, y, cz + dz))
    return out


def room_cells(box):
    x0, y0, z0, x1, y1, z1 = box
    return {(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)}


def pocket_cells(at, r):
    cx, feet, cz = at
    out = set()
    for dx in range(-r - 1, r + 2):
        for dz in range(-r - 1, r + 2):
            d2 = dx * dx + dz * dz
            if d2 > (r + 0.5) ** 2:
                continue
            top = feet + r + 1 if d2 <= (r - 0.5) ** 2 else feet + r
            for y in range(feet, top + 1):
                out.add((cx + dx, y, cz + dz))
    return out


def chamber_cells(centre, r, height):
    cx, feet, cz = centre
    out = set()
    R = r + 0.5
    for dx in range(-r - 1, r + 2):
        for dz in range(-r - 1, r + 2):
            d = math.hypot(dx, dz)
            if d > R:
                continue
            top = feet + max(3, int(math.floor((height - 1) * math.sqrt(max(0.0, 1 - (d / R) ** 2)) + 0.5)))
            for y in range(feet, top + 1):
                out.add((cx + dx, y, cz + dz))
    return out


def cut_floor(cut, x, z):
    x0, z0, x1, z1 = cut["rect"]
    b = cut.get("bench") or {}
    rise, run, levels = b.get("rise", 0), b.get("run", 1), b.get("levels", 1)
    if cut["kind"] == "pit":
        e = min(x - x0, x1 - x, z - z0, z1 - z)
    else:
        sides = {"west": x - x0, "east": x1 - x, "north": z - z0, "south": z1 - z}
        e = min([sides[s] for s in cut.get("benches") or []], default=None)
    level = 0 if e is None else max(0, levels - 1 - e // run)
    yf = cut["floor"] + rise * level
    ramp = cut.get("ramp")
    if ramp and ramp["x"][0] <= x <= ramp["x"][1] and ramp["z"][0] <= z <= ramp["z"][1]:
        za, zb = ramp["z"]
        ry = rnd(cut["floor"] + (zb - z) / (zb - za) * (ramp["top"] - cut["floor"]))
        yf = ry                      # the ramp is a causeway down through the benches, never a staircase of them
    return yf


def rasterise(m):
    spec = m.spec
    for cut in spec["town"]["cuts"]:
        fid = m.add_feature({"id": cut["id"], "kind": "cut", "gated": False, "rec": cut}, False)
        x0, z0, x1, z1 = cut["rect"]
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                yf = cut_floor(cut, x, z)
                g = m.ground(x, z)
                if g <= yf:
                    continue
                i, k = x - m.X0, z - m.Z0
                m.cut_floor[i, k] = min(m.cut_floor[i, k], yf)
                m.cut_of[i, k] = fid
                for y in range(yf + 1, g + CLEAR_ABOVE + 1):
                    m.mark(x, y, z, fid, False)
    for f in spec["mine"]["features"]:
        gated = bool(f.get("gated"))
        fid = m.add_feature({"id": f["id"], "kind": f["kind"], "gated": gated, "rec": f}, gated)
        for c in feature_cells(f, m.ground):
            m.mark(*c, fid, gated)


def feature_cells(f, ground):
    """The envelope cells of one mine feature, as data/rift_mines.json geometry says; `ground(x, z)` for a shaft."""
    if f["kind"] == "tube":
        cells = tube_cells(f["path"], f["r"], f["height"])
        if f.get("pocket"):
            cells |= pocket_cells(f["pocket"]["at"], f["pocket"]["r"])
    elif f["kind"] == "room":
        cells = room_cells(f["box"])
    elif f["kind"] == "shaft":
        cx, cz = f["centre"]
        r = f["r"]
        cells = {(x, y, z) for x in range(cx - r, cx + r + 1) for z in range(cz - r, cz + r + 1)
                 for y in range(f["from_y"], ground(x, z))}
    elif f["kind"] == "pocket":
        cells = pocket_cells(f["at"], f["r"])
    elif f["kind"] == "chamber":
        cells = chamber_cells(f["centre"], f["r"], f["height"])
    else:
        raise MineError("feature %s: unknown kind %r" % (f["id"], f["kind"]))
    return cells


# ------------------------------------------------------------------ carve, shell

def dilate(a, n):
    out = a.copy()
    for ax in range(3):
        src = out.copy()
        for k in range(1, n + 1):
            sl_a = [slice(None)] * 3
            sl_b = [slice(None)] * 3
            sl_a[ax], sl_b[ax] = slice(k, None), slice(None, -k)
            out[tuple(sl_a)] |= src[tuple(sl_b)]
            out[tuple(sl_b)] |= src[tuple(sl_a)]
    return out


def run_bottoms(mask):
    """For each True cell, the y index of the bottom of its vertical run."""
    bottom = np.full(mask.shape, -1, np.int32)
    prev = np.full(mask.shape[:2], -1, np.int32)
    for j in range(mask.shape[2]):
        col = mask[:, :, j]
        start = np.where(col & (prev < 0), j, prev)
        start = np.where(col, start, -1)
        bottom[:, :, j] = start
        prev = start
    return bottom


def carve(m):
    c = m.env.copy()
    rough_kinds = {i for i, f in enumerate(m.feats) if f["gated"] and f["kind"] in ("tube", "pocket", "chamber")}
    if rough_kinds:
        edge = m.env & ~(np.roll(m.env, 1, 0) & np.roll(m.env, -1, 0) & np.roll(m.env, 1, 1) & np.roll(m.env, -1, 1)
                         & np.roll(m.env, 1, 2) & np.roll(m.env, -1, 2))
        bottoms = run_bottoms(m.env)
        js = np.arange(m.ny)[None, None, :]
        high = (js - bottoms) >= 3
        cand = np.argwhere(edge & high & np.isin(m.own, list(rough_kinds)))
        # top down, and only a cell with nothing carved over it: the rock left hangs from the ceiling, never floats
        for i, k, j in sorted(cand.tolist(), key=lambda c_: -c_[2]):
            if j + 1 < m.ny and c[i, k, j + 1]:
                continue
            x, y, z = i + m.X0, j + m.Y0, k + m.Z0
            if u(m.spec["seed"], x, y, z, 7) < ROUGH:
                c[i, k, j] = False
    m.carve = c


def shell(m):
    """Every cell within SHELL_R of the envelope, not carved, at or under the ground."""
    near = dilate(m.env, SHELL_R) & ~m.carve
    ys = np.arange(m.ny)[None, None, :] + m.Y0
    near &= ys <= m.S0[:, :, None]
    return near


# ------------------------------------------------------------------ blocks

def rock_for(m, x, y, z, fid):
    pal = m.spec["palette"]
    if fid >= 0 and m.feats[fid]["kind"] == "cut":
        cut = m.feats[fid]["rec"]
        if cut.get("veins") and u(m.spec["seed"], x, y, z, 11) < m.spec["town"]["vein_share"]:
            return pick(cut["veins"], m.spec["seed"], x, y, z, 12)
        return pick(pal["cut_face"], m.spec["seed"], x, y, z, 13)
    return pick(pal["rock_lower"] if y < pal["rock_split_y"] else pal["rock_upper"], m.spec["seed"], x, y, z, 14)


NEIGH6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def owner_near(m, x, y, z):
    """The feature of the nearest carved cell (first found in rings of 1 and 2), or -1."""
    for rad in (1, 2):
        for dx in range(-rad, rad + 1):
            for dy in range(-rad, rad + 1):
                for dz in range(-rad, rad + 1):
                    if max(abs(dx), abs(dy), abs(dz)) != rad:
                        continue
                    q = (x + dx, y + dy, z + dz)
                    if m.inside(*q):
                        i, k, j = m.ix(*q)
                        if m.carve[i, k, j]:
                            return int(m.own[i, k, j])
    return -1


def build_blocks(m, near):
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    seam = m.spec["mine"]["seam"]
    seam_fid = next(i for i, f in enumerate(m.feats) if f["id"] == seam["cut"])
    sx0 = m.feats[seam_fid]["rec"]["rect"][0]
    glint_fids = {i for i, f in enumerate(m.feats) if f["rec"].get("seam_glints")}
    for i, k, j in np.argwhere(near):
        x, y, z = int(i + m.X0), int(j + m.Y0), int(k + m.Z0)
        above = m.inside(x, y + 1, z) and m.carve[i, k, j + 1]
        fid = owner_near(m, x, y, z)
        f = m.feats[fid] if fid >= 0 else None
        if above:
            fa = m.feats[int(m.own[i, k, j + 1])]
            if fa["kind"] == "cut":
                b = pick(pal["cut_floor"], seed, x, y, z, 21)
            elif fa["kind"] == "chamber":
                b = pick(pal["chamber_floor"], seed, x, y, z, 22)
            else:
                b = pick(pal[fa["rec"].get("floor", "gallery_floor")], seed, x, y, z, 23)
        else:
            b = rock_for(m, x, y, z, fid)
        exposed = any(m.is_carved(x + dx, y + dy, z + dz) for dx, dy, dz in NEIGH6)
        if exposed and f is not None and not above:
            if fid == seam_fid:
                band = seam["band"]["base_y"] + seam["band"]["per_x"] * (x - sx0) + seam["band"]["per_z"] * z
                if abs(y - band) <= seam["band"]["half"]:
                    b = pal["meteorid_radiated"] if u(seed, x, y, z, 31) < seam["radiated_share"] else pal["meteorid"]
            elif fid in glint_fids or (f["gated"] and f["kind"] in ("pocket", "chamber")):
                share = 0.5 if f["kind"] == "pocket" or fid in glint_fids else 0.08
                if u(seed, x, y, z, 32) < share:
                    b = pal["meteorid_radiated"] if u(seed, x, y, z, 33) < 0.3 else pal["meteorid"]
        m.blocks[(x, y, z)] = b


# ------------------------------------------------------------------ fittings

def feet_at(m, x, z, lo=None, hi=None):
    """The lowest carved y in a column (optionally inside [lo, hi]), or None."""
    i, k = x - m.X0, z - m.Z0
    col = np.nonzero(m.carve[i, k, :])[0]
    for j in col:
        y = int(j + m.Y0)
        if (lo is None or y >= lo) and (hi is None or y <= hi):
            return y
    return None


def hang_lantern(m, x, feet, z):
    """A lantern under the ceiling of the carved run that starts at `feet`."""
    y = feet
    while m.is_carved(x, y + 1, z):
        y += 1
    if y - feet >= 3:
        m.fit[(x, y, z)] = "minecraft:lantern[hanging=true,waterlogged=false]"
        return True
    return False


def frames(m):
    pal = m.spec["palette"]
    for f in m.spec["mine"]["features"]:
        if f["kind"] != "tube":
            continue
        every = f.get("frames")
        light = f.get("light_every")
        if not every and not light:
            continue
        r, h = f["r"], f["height"]
        dist = 0.0
        for (x0, y0, z0), (x1, y1, z1) in zip(f["path"], f["path"][1:]):
            L = math.hypot(x1 - x0, z1 - z0)
            if L == 0:
                continue
            ux, uz = (x1 - x0) / L, (z1 - z0) / L
            axis = abs(ux) > 0.99 or abs(uz) > 0.99
            px, pz = -uz, ux
            s = 3.0
            while s <= L - 3:
                t = s / L
                cx, cz, feet = rnd(x0 + (x1 - x0) * t), rnd(z0 + (z1 - z0) * t), rnd(y0 + (y1 - y0) * t)
                n = int(dist + s)
                if axis and every and not f.get("gated") and n % every == 0:
                    for side in (-1, 1):
                        wx, wz = cx + rnd(px * (r + 1) * side), cz + rnd(pz * (r + 1) * side)
                        for y in range(feet, feet + h):
                            if not m.is_carved(wx, y, wz) and (wx, y, wz) in m.blocks:
                                m.fit[(wx, y, wz)] = pal["post"] + "[axis=y]"
                    for off in range(-(r + 1), r + 2):
                        bx, bz = cx + rnd(px * off), cz + rnd(pz * off)
                        yb = feet + h
                        if not m.is_carved(bx, yb, bz) and (bx, yb, bz) in m.blocks:
                            m.fit[(bx, yb, bz)] = pal["beam"]
                if light and n % light == 0:
                    hang_lantern(m, cx, feet, cz)
                s += 1.0
            dist += L
    # the hall: pillars from floor to ceiling, lanterns on a grid
    for f in m.spec["mine"]["features"]:
        if f["kind"] != "room":
            continue
        x0, y0, z0, x1, y1, z1 = f["box"]
        for px, pz in m.spec["town"].get("hall_pillars") or []:
            if x0 <= px <= x1 and z0 <= pz <= z1:
                for y in range(y0, y1 + 1):
                    m.fit[(px, y, pz)] = pal["post"] + "[axis=y]"
                m.fit[(px, y1, pz)] = pal["beam"]
        step = f.get("light_every") or 6
        for x in range(x0 + 3, x1 - 1, step):
            for z in range(z0 + 3, z1 - 1, step):
                if (x, y1, z) not in m.fit:
                    m.fit[(x, y1, z)] = "minecraft:lantern[hanging=true,waterlogged=false]"


def tracks(m):
    pal = m.spec["palette"]
    n = 0
    for t in m.spec["town"]["tracks"]:
        (xa, za), (xb, zb) = t["from"], t["to"]
        if xa != xb and za != zb:
            raise MineError("track %s is not straight along x or z: a powered rail cannot turn" % t["id"])
        shape = "north_south" if xa == xb else "east_west"
        y = t["feet"]
        for x in range(min(xa, xb), max(xa, xb) + 1):
            for z in range(min(za, zb), max(za, zb) + 1):
                if m.is_carved(x, y, z):
                    if m.is_carved(x, y - 1, z):
                        raise MineError("track %s at (%d, %d, %d) has no floor under it" % (t["id"], x, y, z))
                elif m.top(x, z) + 1 == y:
                    m.surf[(x, y - 1, z)] = "minecraft:gravel"          # ballast where the track leaves the cut
                else:
                    raise MineError("track %s at (%d, %d, %d) is neither in a carved space nor on the ground (y%d)"
                                    % (t["id"], x, y, z, m.top(x, z)))
                if (x, y, z) in m.fit:
                    raise MineError("track %s runs into a fitting at (%d, %d, %d)" % (t["id"], x, y, z))
                m.fit[(x, y, z)] = "%s[shape=%s,powered=false,waterlogged=false]" % (pal["rail"], shape)
                n += 1
    return n


FACINGS = ("north", "south", "west", "east")


def crystals(m):
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    count = 0
    for f in m.spec["mine"]["features"]:
        n = f.get("crystals")
        if not n:
            continue
        if f["kind"] == "pocket":
            cx, feet, cz = f["at"]
            spots = [(cx + dx, feet, cz + dz) for dx in range(-f["r"], f["r"] + 1) for dz in range(-f["r"], f["r"] + 1)
                     if dx * dx + dz * dz <= (f["r"] - 0.5) ** 2 and (dx, dz) != (0, 0)]
        else:
            cx, feet, cz = f["centre"]
            # the crystal heart: a plinth at the far side of the chamber from where its drift comes in
            drift = next((d for d in m.spec["mine"]["features"] if d["kind"] == "tube" and d.get("gated")
                          and math.hypot(d["path"][-1][0] - cx, d["path"][-1][2] - cz) <= f["r"] + 1), None)
            if drift is None:
                raise MineError("chamber %s: no gated drift ends in it" % f["id"])
            ex, _ey, ez = drift["path"][-2]
            L = math.hypot(cx - ex, cz - ez) or 1.0
            hx, hz = rnd(cx + (cx - ex) / L * (f["r"] - 3)), rnd(cz + (cz - ez) / L * (f["r"] - 3))
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    corner = dx != 0 and dz != 0
                    m.fit[(hx + dx, feet - 1, hz + dz)] = pal["meteorid_chiseled"] if corner else pal["meteorid_polished"]
            spots = [(hx + dx, feet, hz + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)]
            f["_heart"] = [hx, feet, hz]
        spots = [s for s in spots if m.is_carved(*s) and m.is_carved(s[0], s[1] + 1, s[2])]
        spots.sort(key=lambda s: h32(seed, s[0], s[1], s[2], 41))
        if len(spots) < n:
            raise MineError("%s: room for %d crystals, %d asked" % (f["id"], len(spots), n))
        for x, y, z in spots[:n]:
            m.fit[(x, y, z)] = "%s[facing=%s]" % (pal["mega_stone_crystal"], FACINGS[h32(seed, x, z, 42) % 4])
            if (x, y - 1, z) not in m.fit:
                m.fit[(x, y - 1, z)] = pal["meteorid_radiated"]
            count += 1
    return count


def glints(m):
    """Dormant crystal out of the seam: in carved cells beside an exposed meteorid face, pointing away from it."""
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    share = m.spec["mine"]["seam"]["glint_share"]
    met = {pal["meteorid"], pal["meteorid_radiated"]}
    n = 0
    dirs = {(1, 0, 0): "east", (-1, 0, 0): "west", (0, 0, 1): "south", (0, 0, -1): "north", (0, 1, 0): "up"}
    for (x, y, z), b in sorted(m.blocks.items()):
        if b not in met or (x, y, z) in m.fit:
            continue
        for (dx, dy, dz), face in dirs.items():
            q = (x + dx, y + dy, z + dz)
            if m.is_carved(*q) and q not in m.fit and u(seed, x, y, z, dx, dz, 51) < share:
                # only where a player is not walking: off the floor of a tube, or anywhere on a cut's face
                if dy == 1 and m.feats[int(m.own[m.ix(*q)])]["kind"] != "cut":
                    continue
                m.fit[q] = "%s[facing=%s]" % (pal["dormant_crystal"], face)
                n += 1
                break
    return n


def collapse(m):
    """The rubble at the decline's foot: the old gate's plug, with nothing behind it (data mine.collapse)."""
    pal = m.spec["palette"]
    x0, y0, z0, x1, y1, z1 = m.spec["mine"]["collapse"]["box"]
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                if m.is_carved(x, y, z):
                    raise MineError("the collapse at (%d, %d, %d) is inside a carved space" % (x, y, z))
                m.fit[(x, y, z)] = pick(pal["rubble"], m.spec["seed"], x, y, z, 61)


def face_cells(spec, face, k):
    """{(x, y, z): block} for the tease face's variant k: meteorid everywhere, `radiated` radiated cells within 1 of the
    front, and the crystals on the front plane's bottom row (face cells ordered by h32(seed, k, x, y, z, 71))."""
    pal = spec["palette"]
    seed = spec["seed"]
    x0, y0, z0, x1, y1, z1 = face["box"]
    front = face["front"]

    def depth(c):
        return {"west": c[0] - x0, "east": x1 - c[0], "north": c[2] - z0, "south": z1 - c[2]}[front]
    cells = [(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)]
    order = sorted(cells, key=lambda c: h32(seed, k, c[0], c[1], c[2], 71))
    out = {c: pal["meteorid"] for c in cells}
    for c in [c for c in order if depth(c) <= 1][:face["radiated"]]:
        out[c] = pal["meteorid_radiated"]
    visible = [c for c in order if depth(c) == 0 and c[1] == y0]
    if len(visible) < face["crystals"]:
        raise MineError("the tease face has room for %d crystals, %d asked" % (len(visible), face["crystals"]))
    for c in visible[:face["crystals"]]:
        out[c] = "%s[facing=%s]" % (pal["mega_stone_crystal"], front)
    return out


def tease(m):
    """The company grille across drift C and the crystal's face behind it (data mine.tease)."""
    t = m.spec["mine"]["tease"]
    g = t["grille"]
    for x in range(g["x"][0], g["x"][1] + 1):
        for y in range(g["y"][0], g["y"][1] + 1):
            if not m.is_carved(x, y, g["z"]):
                raise MineError("the grille cell (%d, %d, %d) is not in the drift" % (x, y, g["z"]))
            m.fit[(x, y, g["z"])] = "minecraft:iron_bars"
    x0, y0, z0, x1, y1, z1 = t["face"]["box"]
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                if m.is_carved(x, y, z):
                    raise MineError("the tease face cell (%d, %d, %d) is carved" % (x, y, z))
    for c, b in face_cells(m.spec, t["face"], 0).items():
        m.fit[c] = b
    return t["face"]["crystals"]


# ------------------------------------------------------------------ the surface: street, houses, piles, posts, derricks

def surface(m):
    s = m.spec["town"]
    pal = m.spec["palette"]
    seed = m.spec["seed"]
    st = s["street"]
    (xa, za), (xb, zb) = st["from"], st["to"]
    half = st["width"] // 2
    for x in range(xa, xb + 1):
        for z in range(za - half, za + half + 1):
            y = m.ground(x, z)
            m.surf[(x, y, z)] = st["surface"]
            for yy in range(y + 1, y + 4):
                m.surf[(x, yy, z)] = AIR
    for x, z in s["lamp_posts"]:
        y = m.top(x, z)
        m.surf[(x, y + 1, z)] = "minecraft:cobbled_deepslate_wall"
        m.surf[(x, y + 2, z)] = "minecraft:cobbled_deepslate_wall"
        m.surf[(x, y + 3, z)] = "minecraft:lantern[hanging=false,waterlogged=false]"
    for hrec in s["houses"]:
        house(m, hrec)
    for p in s["ore_piles"]:
        pile(m, p)
    for d in s["derricks"]:
        derrick(m, d)
    headframe(m)


ROLE_FITTINGS = {
    "forge": ["minecraft:furnace[facing=south]", "minecraft:furnace[facing=south]", "minecraft:blast_furnace[facing=south]",
              "minecraft:anvil[facing=east]", "minecraft:smithing_table", "minecraft:grindstone[face=floor,facing=south]",
              "minecraft:crafting_table"],
    "assay": ["minecraft:crafting_table", "minecraft:stonecutter[facing=south]", "minecraft:barrel[facing=up]",
              "minecraft:barrel[facing=up]", "minecraft:chest[facing=south]"],
    "bunkhouse": ["minecraft:barrel[facing=up]", "minecraft:barrel[facing=up]", "minecraft:barrel[facing=up]",
                  "minecraft:polished_deepslate_slab[type=bottom]", "minecraft:polished_deepslate_slab[type=bottom]"],
    "canteen": ["minecraft:smoker[facing=south]", "minecraft:smoker[facing=south]", "minecraft:barrel[facing=up]",
                "minecraft:cauldron", "minecraft:barrel[facing=up]"],
    "store": ["minecraft:barrel[facing=up]", "minecraft:barrel[facing=up]", "minecraft:barrel[facing=up]",
              "minecraft:chest[facing=south]", "minecraft:barrel[facing=up]"],
    "smelter": ["minecraft:blast_furnace[facing=north]", "minecraft:blast_furnace[facing=north]",
                "minecraft:blast_furnace[facing=north]", "minecraft:furnace[facing=north]", "minecraft:cauldron"],
    "tools": ["minecraft:grindstone[face=floor,facing=north]", "minecraft:chipped_anvil[facing=east]",
              "minecraft:smithing_table", "minecraft:barrel[facing=up]"],
    "tally": ["minecraft:crafting_table", "minecraft:barrel[facing=up]", "minecraft:polished_deepslate_slab[type=bottom]",
              "minecraft:chest[facing=west]"],
}
DOOR = "minecraft:waxed_weathered_copper_door"


def house(m, hrec):
    """A rock house: cobbled deepslate footing, brick walls on basalt corners, iron-bar windows, a copper door, a
    deepslate tile roof with a parapet. No timber in the structure."""
    x0, z0, x1, z1 = hrec["rect"]
    cols = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    floor = max(m.top(x, z) for x, z in cols)
    low = min(m.top(x, z) for x, z in cols)
    wall = hrec["walls"]
    door_side = hrec["door"]
    for x, z in cols:
        for y in range(low - 1, floor + 1):
            m.surf[(x, y, z)] = "minecraft:cobbled_deepslate"
        m.surf[(x, floor, z)] = "minecraft:polished_deepslate"
        for y in range(floor + 1, floor + 8):
            m.surf[(x, y, z)] = AIR
    top = floor + 5
    for x, z in cols:
        edge = x in (x0, x1) or z in (z0, z1)
        corner = x in (x0, x1) and z in (z0, z1)
        if edge:
            for y in range(floor + 1, top):
                m.surf[(x, y, z)] = pal_post() if corner else (
                    "minecraft:cobbled_deepslate" if y == floor + 1 else wall)
            m.surf[(x, top, z)] = "minecraft:deepslate_tiles"
            m.surf[(x, top + 1, z)] = "minecraft:cobbled_deepslate_wall" if (x + z) % 2 == 0 or corner else AIR
        else:
            m.surf[(x, top, z)] = "minecraft:deepslate_tile_slab[type=top,waterlogged=false]"
    # windows: every third block of each wall, clear of corners and door
    cx, cz = (x0 + x1) // 2, (z0 + z1) // 2
    door = {"south": (cx, z1), "north": (cx, z0), "east": (x1, cz), "west": (x0, cz)}[door_side]
    for x, z in cols:
        if not (x in (x0, x1) or z in (z0, z1)) or (x in (x0, x1) and z in (z0, z1)):
            continue
        along = z - z0 if x in (x0, x1) else x - x0
        if along % 3 == 1 and abs(x - door[0]) + abs(z - door[1]) > 1:
            m.surf[(x, floor + 3, z)] = "minecraft:iron_bars"
    facing = {"south": "north", "north": "south", "east": "west", "west": "east"}[door_side]
    m.surf[(door[0], floor + 1, door[1])] = "%s[facing=%s,half=lower,hinge=left,open=false,powered=false]" % (DOOR, facing)
    m.surf[(door[0], floor + 2, door[1])] = "%s[facing=%s,half=upper,hinge=left,open=false,powered=false]" % (DOOR, facing)
    # fittings along the wall opposite the door, then the side walls
    back = {"south": [(x, z0 + 1) for x in range(x0 + 1, x1)], "north": [(x, z1 - 1) for x in range(x0 + 1, x1)],
            "east": [(x0 + 1, z) for z in range(z0 + 1, z1)], "west": [(x1 - 1, z) for z in range(z0 + 1, z1)]}[door_side]
    items = ROLE_FITTINGS[hrec["role"]]
    for (x, z), b in zip(back, items):
        m.surf[(x, floor + 1, z)] = b
    m.surf[(cx, top - 1, cz)] = "minecraft:lantern[hanging=true,waterlogged=false]"
    if hrec.get("chimney"):
        hx, hz = (x1 - 1, z0 + 1) if door_side == "south" else (x1 - 1, z1 - 1)
        for y in range(top, top + 4):
            m.surf[(hx, y, hz)] = "minecraft:cobbled_deepslate"
        m.surf[(hx, top + 4, hz)] = "minecraft:campfire[lit=true,signal_fire=false,facing=north,waterlogged=false]"
    # a lantern on the floor inside the door, so the room is never dark
    ix, iz = {"south": (cx + 1, z1 - 1), "north": (cx + 1, z0 + 1), "east": (x1 - 1, cz + 1), "west": (x0 + 1, cz + 1)}[door_side]
    m.surf[(ix, floor + 1, iz)] = "minecraft:lantern[hanging=false,waterlogged=false]"


def pal_post():
    return "minecraft:polished_basalt[axis=y]"


def pile(m, p):
    seed = m.spec["seed"]
    px, pz = p["centre"]
    rx, rz = p["r"]
    for x in range(int(px - rx) - 1, int(px + rx) + 2):
        for z in range(int(pz - rz) - 1, int(pz + rz) + 2):
            d = math.hypot((x - px) / rx, (z - pz) / rz)
            if d >= 1:
                continue
            h = int(rnd(p["h"] * (1 - d) + (h32(seed, x, z, 3) % 3 - 1) * 0.4))
            if h <= 0:
                continue
            base = m.top(x, z)
            for kk in range(h):
                m.surf[(x, base + 1 + kk, z)] = pick(p["blocks"], seed, x, z, kk, len(p["id"]))


def derrick(m, d):
    x, z = d["at"]
    y = m.top(x, z)
    H = d["height"]
    for yy in range(y + 1, y + H + 1):
        m.surf[(x, yy, z)] = "minecraft:polished_basalt[axis=y]"
    bx, bz = d["boom"]
    axis = "x" if bx else "z"
    for k in range(1, d["reach"] + 1):
        m.surf[(x + bx * k, y + H, z + bz * k)] = "minecraft:polished_basalt[axis=%s]" % axis
    ex, ez = x + bx * d["reach"], z + bz * d["reach"]
    for yy in range(y + H - d["drop"], y + H):
        m.surf[(ex, yy, ez)] = "minecraft:chain[axis=y,waterlogged=false]"
    m.surf[(ex, y + H - d["drop"] - 1, ez)] = "minecraft:cauldron"
    m.surf[(x, y + H + 1, z)] = "minecraft:lantern[hanging=false,waterlogged=false]"
    # guy stays: a basalt foot each side of the mast
    for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if (sx, sz) != (bx, bz):
            m.surf[(x + sx, y + 1, z + sz)] = "minecraft:polished_blackstone_bricks"


def headframe(m):
    hf = m.spec["mine"]["headframe"]
    shaft = next(f for f in m.spec["mine"]["features"] if f["id"] == hf["over"])
    cx, cz = shaft["centre"]
    r = shaft["r"]
    g = max(m.ground(x, z) for x in range(cx - r - 2, cx + r + 3) for z in range(cz - r - 2, cz + r + 3))
    # the grate over the shaft, at each column's ground
    for x in range(cx - r, cx + r + 1):
        for z in range(cz - r, cz + r + 1):
            m.surf[(x, m.ground(x, z), z)] = "minecraft:iron_trapdoor[facing=north,half=top,open=false,powered=false,waterlogged=false]"
    H = hf["height"]
    for dx, dz in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
        x, z = cx + dx, cz + dz
        for y in range(m.ground(x, z) + 1, g + H + 1):
            m.surf[(x, y, z)] = "minecraft:polished_basalt[axis=y]"
    for y in (g + 6, g + H):
        for k in range(-2, 3):
            for (x, z) in ((cx + k, cz - 2), (cx + k, cz + 2), (cx - 2, cz + k), (cx + 2, cz + k)):
                if (x, y, z) not in m.surf:
                    m.surf[(x, y, z)] = "minecraft:deepslate_brick_slab[type=bottom,waterlogged=false]"
    for k in (-1, 0, 1):
        m.surf[(cx + k, g + H, cz)] = "minecraft:polished_basalt[axis=x]"
    for y in range(m.ground(cx, cz) + 1, g + H):
        m.surf[(cx, y, cz)] = "minecraft:chain[axis=y,waterlogged=false]"
    for y in range(shaft["from_y"] + 1, m.ground(cx, cz)):
        m.fit[(cx, y, cz)] = "minecraft:chain[axis=y,waterlogged=false]"
    for dx, dz in ((-2, -2), (2, 2)):
        m.surf[(cx + dx, g + H + 1, cz + dz)] = "minecraft:lantern[hanging=false,waterlogged=false]"


# ------------------------------------------------------------------ checks on the model

def reach(mask, start):
    """The cells of `mask` 6-connected to `start`."""
    seen = np.zeros(mask.shape, bool)
    if not mask[start]:
        return seen
    seen[start] = True
    stack = [start]
    while stack:
        i, k, j = stack.pop()
        for di, dk, dj in NEIGH6:
            q = (i + di, k + dk, j + dj)
            if 0 <= q[0] < mask.shape[0] and 0 <= q[1] < mask.shape[1] and 0 <= q[2] < mask.shape[2] \
                    and mask[q] and not seen[q]:
                seen[q] = True
                stack.append(q)
    return seen


def walkable(m, x, y, z):
    return m.is_carved(x, y, z) and m.is_carved(x, y + 1, z) and not m.is_carved(x, y - 1, z)


def check(m, near):
    spec = m.spec
    probs = []
    # nothing is gated any more (SOUTHERN_RIFT_MEGA.md decision 1): a gated feature would be a section nobody can enter
    if m.gated.any():
        probs.append("%d gated cells: the spur's gated section is retired (data retired_gated_section)" % int(m.gated.sum()))
    # the tease: the grille closes drift C whole, the face's front meets the pocket behind it, and the ward holds both
    t = spec["mine"]["tease"]
    g = t["grille"]
    x0, y0, z0, x1, y1, z1 = t["face"]["box"]
    front = {"south": [(x, y, z1 + 1) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)],
             "north": [(x, y, z0 - 1) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)],
             "east": [(x1 + 1, y, z) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)],
             "west": [(x0 - 1, y, z) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)]}[t["face"]["front"]]
    if not any(m.is_carved(*c) for c in front):
        probs.append("the tease face's front meets no carved cell")
    open_ = m.carve.copy()
    for x in range(g["x"][0], g["x"][1] + 1):
        for y in range(g["y"][0], g["y"][1] + 1):
            open_[m.ix(x, y, g["z"])] = False
    fz = z1 + 1 if t["face"]["front"] == "south" else z0 - 1
    past = reach(open_, m.ix(x0, y0, fz))
    adit = m.ix(spec["mine"]["features"][0]["path"][0][0], spec["mine"]["features"][0]["path"][0][1],
                spec["mine"]["features"][0]["path"][0][2])
    if past[adit]:
        probs.append("the tease face can be reached from the adit without passing the grille")
    # slopes: no tube segment steeper than 0.6
    for f in spec["mine"]["features"]:
        if f["kind"] == "tube":
            for (x0, y0, z0), (x1, y1, z1) in zip(f["path"], f["path"][1:]):
                L = math.hypot(x1 - x0, z1 - z0)
                if L and abs(y1 - y0) / L > 0.6:
                    probs.append("%s: a segment climbs %.2f per block" % (f["id"], abs(y1 - y0) / L))
    # rock left in no gated cell's way on the floor: every tube's feet cells carved (roughness never takes the floor)
    return probs


# ------------------------------------------------------------------ lines and the pack

def column_runs(x, z, ys):
    """[(y0, y1, block)] vertical runs of one block."""
    ys = sorted(ys)
    out = []
    n = 0
    while n < len(ys):
        y0, b = ys[n]
        k = n
        while k + 1 < len(ys) and ys[k + 1][0] == ys[k][0] + 1 and ys[k + 1][1] == b:
            k += 1
        out.append((y0, ys[k][0], b))
        n = k + 1
    return out


def cmd(x, y0, y1, z, b):
    return "fill %d %d %d %d %d %d %s" % (x, y0, z, x, y1, z, b) if y1 > y0 else "setblock %d %d %d %s" % (x, y0, z, b)


def lines(m):
    out = {p: [] for p in PASSES}
    cols = {}
    for (x, y, z), b in m.blocks.items():
        cols.setdefault((x, z), []).append((y, b))
    for (x, z) in sorted(cols):
        out["shell"] += [cmd(x, a, c, z, b) for a, c, b in column_runs(x, z, cols[(x, z)])]
    for i, k in np.argwhere(m.carve.any(axis=2)):
        js = np.nonzero(m.carve[i, k])[0]
        x, z = int(i + m.X0), int(k + m.Z0)
        out["air"] += [cmd(x, a, c, z, AIR) for a, c, _b in column_runs(x, z, [(int(j + m.Y0), AIR) for j in js])]
    # fittings: solid ones first, then the ones that hang or stand on them
    delicate = ("lantern", "rail", "crystal", "chain", "iron_bars")
    fits = sorted(m.fit.items(), key=lambda kv: (any(d in kv[1] for d in delicate), kv[0][1], kv[0][0], kv[0][2]))
    out["fittings"] = ["setblock %d %d %d %s" % (x, y, z, b) for (x, y, z), b in fits]
    solid = [(p, b) for p, b in m.surf.items() if not any(d in b for d in delicate + ("door", "campfire", "trapdoor"))]
    soft = [(p, b) for p, b in m.surf.items() if any(d in b for d in delicate + ("door", "campfire", "trapdoor"))]
    scols = {}
    for (x, y, z), b in solid:
        scols.setdefault((x, z), []).append((y, b))
    for (x, z) in sorted(scols):
        out["surface"] += [cmd(x, a, c, z, b) for a, c, b in column_runs(x, z, scols[(x, z)])]
    out["surface"] += ["setblock %d %d %d %s" % (x, y, z, b) for (x, y, z), b in sorted(soft, key=lambda kv: (kv[0][1], kv[0]))]
    return out


def text(s, **style):
    return json.dumps(dict({"text": s}, **style), ensure_ascii=False)


def box_cond(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    return {"condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"location": {"dimension": "minecraft:overworld", "position": {
                "x": {"min": x0, "max": x1 + 1}, "y": {"min": y0, "max": y1 + 1}, "z": {"min": z0, "max": z1 + 1}}}}}


def ward_box(spec):
    """The grille, the pocket behind it and the face box, grown by ward_margin: ([x0, y0, z0], [x1, y1, z1])."""
    t = spec["mine"]["tease"]
    g, fb, wm = t["grille"], t["face"]["box"], t["ward_margin"]
    drift = next(f for f in spec["mine"]["features"] if f["id"] == t["drift"])
    px, py, pz = drift["pocket"]["at"]
    pr = drift["pocket"]["r"]
    lo = [min(g["x"][0], fb[0], px - pr), min(g["y"][0], fb[1], py), min(g["z"], fb[2], pz - pr)]
    hi = [max(g["x"][1], fb[3], px + pr), max(g["y"][1], fb[4], py + pr + 1), max(g["z"], fb[5], pz + pr)]
    return [v - wm for v in lo], [v + wm for v in hi]


def tease_files(m):
    """The ward (per player: only a player lacking the flag), the tick driver and the tease face's restore."""
    spec = m.spec
    t = spec["mine"]["tease"]
    flag = spec["flag"]["advancement"]
    F = "%s:%s" % (NS, FOLDER)
    lo, hi = ward_box(spec)
    files = {"advancement/%s/tease_ward.json" % FOLDER: {
        "criteria": {"here": {"trigger": "minecraft:location", "conditions": {"player": [box_cond(lo, hi)]}}},
        "rewards": {"function": "%s/tease/ward" % F}}}
    x0, y0, z0, x1, y1, z1 = t["face"]["box"]
    gx0, gy0, gz0, gx1, gy1, gz1 = x0 - 1, y0 - 1, z0 - 1, x1 + 1, y1 + 1, z1 + 1
    vol = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (gx0, gy0, gz0, gx1 - gx0, gy1 - gy0, gz1 - gz0)
    ap = t["approach"]
    near = "@a[x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d]" % (ap[0], ap[1], ap[2], ap[3] - ap[0], ap[4] - ap[1], ap[5] - ap[2])
    tag = "#%s:%s" % (NS, t["resettable_tag"])
    fn = {
        "tease/ward": [
            "# near the seam's one crystal (data/rift_mines.json mine.tease.ward_why): Mining Fatigue IV for a player in",
            "# survival or adventure who lacks %s, refreshed each second the location trigger fires. Per player: with" % flag,
            "# the flag it lifts, and the grille and the crystal can be taken",
            "advancement revoke @s only %s:%s/tease_ward" % (NS, FOLDER),
            "execute if entity @s[gamemode=!creative,gamemode=!spectator,advancements={%s=false}] run effect give @s "
            "minecraft:mining_fatigue 3 3 true" % flag],
        "load": ["scoreboard objectives add rm.t dummy",
                 "scoreboard players set #period rm.t %d" % t["period_ticks"],
                 "execute unless score #tease rm.t matches -2147483648.. run scoreboard players set #tease rm.t 0"],
        "tick": ["scoreboard players add #clock rm.t 1",
                 "execute if score #clock rm.t matches 100.. run function %s/tease/drive" % F],
        "tease/drive": [
            "# restore on approach (STONE_ECONOMY.md 5.3): only while a player is near the seam, the period has passed,",
            "# both corners are loaded, and nobody and no Pokemon stands in the box or one block round it",
            "scoreboard players set #clock rm.t 0",
            "execute unless entity %s run return 0" % near,
            "execute store result score #now rm.t run time query gametime",
            "scoreboard players operation #d rm.t = #now rm.t",
            "scoreboard players operation #d rm.t -= #tease rm.t",
            "execute if score #d rm.t < #period rm.t run return 0",
            "execute unless loaded %d %d %d run return 0" % (gx0, gy0, gz0),
            "execute unless loaded %d %d %d run return 0" % (gx1, gy1, gz1),
            "execute if entity @a[%s] run return 0" % vol,
            "execute if entity @e[type=cobblemon:pokemon,%s] run return 0" % vol,
            "function %s/tease/restore" % F,
            "scoreboard players operation #tease rm.t = #now rm.t"],
        "tease/restore": ["# chunks-loaded-by: %s/tease/drive (execute if loaded, both corners of the box)" % F,
                          "fill %d %d %d %d %d %d %s replace %s" % (x0, y0, z0, x1, y1, z1, spec["palette"]["meteorid"], tag)]
                         + ["execute if block %d %d %d %s run setblock %d %d %d %s" % (x, y, z, tag, x, y, z, b)
                            for (x, y, z), b in sorted(face_cells(spec, t["face"], 1).items(), key=lambda kv: ("crystal" in kv[1], kv[0]))
                            if b != spec["palette"]["meteorid"]],
    }
    return files, fn


def ordinal(n):
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth"}.get(n, str(n))


def cart_files(m):
    carts = []
    for x, z in m.spec["town"]["carts"]:
        rail = next(((xx, yy, zz) for (xx, yy, zz), b in m.fit.items() if xx == x and zz == z and "rail" in b), None)
        if rail is None:
            raise MineError("cart at (%d, %d) stands on no rail" % (x, z))
        carts.append(rail)
    chunks = sorted({(x >> 4, z >> 4) for x, _y, z in carts})
    add = ["forceload add %d %d" % (cx * 16, cz * 16) for cx, cz in chunks]
    rem = ["forceload remove %d %d" % (cx * 16, cz * 16) for cx, cz in chunks]
    head = ["# the mine carts (tools/rift_mines.py): entities, so an export erases them; their chunks are force-loaded",
            "# here and they are summoned 60 ticks on, when the chunks are ready (the Rift's fx pattern)"] + add + [
        "schedule function %s:%s/carts_go 60t replace" % (NS, FOLDER)]
    go = ["# chunks-loaded-by: %s:%s/carts" % (NS, FOLDER),
          "kill @e[type=minecraft:minecart,tag=%s]" % TAG]
    for x, y, z in carts:
        go.append("summon minecraft:minecart %.1f %d %.1f {Tags:[\"%s\"],Invulnerable:1b}" % (x + 0.5, y, z + 0.5, TAG))
    go += rem
    return head, go, carts


def write_blocks(out, lns, passes, title, desc):
    """A pack of block functions, tiled by TILE and split at PART, each holding its chunks; returns the index."""
    if out.exists():
        shutil.rmtree(out)
    fn = out / "data" / NS / "function" / out.name.replace("cobblers_", "")
    fn.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": desc}}, indent=2) + "\n",
                                     encoding="utf-8")
    order = []
    for n, pas in enumerate(passes):
        tiles = {}
        for ln in lns[pas]:
            t = ln.split()
            tiles.setdefault((int(t[1]) // TILE, int(t[3]) // TILE), []).append(ln)
        for t in sorted(tiles):
            body = tiles[t]
            for j in range(0, len(body), PART):
                name = "%d%s_%d_%d%s" % (n + 1, pas, t[0], t[1], "" if j == 0 else "_%d" % (j // PART + 1))
                part = FL.ensure_loaded(["# Generated by %s: %s, tile %d %d" % (title, pas, t[0], t[1])] + body[j:j + PART])
                bad = FL.check_lines(part, name)
                if bad:
                    raise MineError("function %s would be refused: %s" % (name, bad[:3]))
                (fn / (name + ".mcfunction")).write_text("\n".join(part) + "\n", encoding="utf-8")
                order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    return fn, order


def write(m, lns):
    fn, order = write_blocks(OUT, lns, PASSES, "tools/rift_mines.py",
                             "Cobblers: the Rift dig camp's mines, quarries and the mega stone seam (tools/rift_mines.py)")
    base = OUT / "data" / NS
    files, tfn = tease_files(m)
    for rel, obj in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")
    for name, body in tfn.items():
        bad = FL.check_lines(body, name)
        if bad:
            raise MineError("function %s would be refused: %s" % (name, bad[:3]))
        p = fn / (name + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(body) + "\n", encoding="utf-8")
    tags = OUT / "data" / "minecraft" / "tags" / "function"
    tags.mkdir(parents=True)
    (tags / "load.json").write_text(json.dumps({"values": ["%s:%s/load" % (NS, FOLDER)]}, indent=2) + "\n", encoding="utf-8")
    (tags / "tick.json").write_text(json.dumps({"values": ["%s:%s/tick" % (NS, FOLDER)]}, indent=2) + "\n", encoding="utf-8")
    bt = base / "tags" / "block"
    bt.mkdir(parents=True)
    t = m.spec["mine"]["tease"]
    (bt / ("%s.json" % t["resettable_tag"])).write_text(json.dumps({"values": t["resettable"]}, indent=2) + "\n", encoding="utf-8")
    head, go, carts = cart_files(m)
    (fn / "carts.mcfunction").write_text("\n".join(head) + "\n", encoding="utf-8")
    (fn / "carts_go.mcfunction").write_text("\n".join(go) + "\n", encoding="utf-8")
    return order, carts


# ------------------------------------------------------------------ the staging refill

def retired_envelope(spec, ground):
    """Every envelope cell of the retired gated section, rasterised by the same geometry as the live features."""
    cells = set()
    for f in spec["retired_gated_section"]["features"]:
        cells |= feature_cells(f, ground)
    return cells


def refill_lines(spec, ground):
    """Rock back into exactly the retired gated envelope: one fill per vertical run, the rock palette by height."""
    pal = spec["palette"]
    seed = spec["seed"]
    cols = {}
    for x, y, z in retired_envelope(spec, ground):
        b = pick(pal["rock_lower"] if y < pal["rock_split_y"] else pal["rock_upper"], seed, x, y, z, 14)
        cols.setdefault((x, z), []).append((y, b))
    out = []
    for (x, z) in sorted(cols):
        out += [cmd(x, a, c, z, b) for a, c, b in column_runs(x, z, cols[(x, z)])]
    return {"refill": out}, sum(len(v) for v in cols.values())


# ------------------------------------------------------------------ driver

def model(source_root=None, spec=None):
    spec = spec or load()
    g = G.Ground(source_root)
    m = Model(spec, g)
    m.groundfn = g
    rasterise(m)
    carve(m)
    near = shell(m)
    build_blocks(m, near)
    frames(m)
    n_rails = tracks(m)
    n_cryst = crystals(m)
    collapse(m)
    n_cryst += tease(m)
    n_glint = glints(m)
    surface(m)
    m.counts = {"envelope cells": int(m.env.sum()), "carved cells": int(m.carve.sum()),
                "gated carved cells": int((m.carve & m.gated).sum()), "shell cells": len(m.blocks),
                "rails": n_rails, "mega stone crystals": n_cryst, "dormant crystal glints": n_glint,
                "fittings": len(m.fit), "surface blocks": len(m.surf)}
    return m, near


def summary(m):
    spec = m.spec
    feats = {f["id"]: f for f in spec["mine"]["features"]}
    lo, hi = ward_box(spec)
    out = {"schema": "cobblers.derived.rift_mines/2", "counts": m.counts, "flag": spec["flag"]["advancement"],
           "collapse": spec["mine"]["collapse"]["box"],
           "tease": {"grille": spec["mine"]["tease"]["grille"], "face": spec["mine"]["tease"]["face"]["box"],
                     "ward": [lo, hi]},
           "seam": {"cut": spec["mine"]["seam"]["cut"], "face_z": spec["town"]["cuts"][0]["rect"][1] - 1,
                    "x": [spec["town"]["cuts"][0]["rect"][0], spec["town"]["cuts"][0]["rect"][2]]},
           "cuts": [{"id": c["id"], "rect": c["rect"], "floor": c["floor"]} for c in spec["town"]["cuts"]],
           "drifts": [{"id": k, "path": v["path"]} for k, v in feats.items() if k.startswith("drift_")],
           "houses": [{"id": h["id"], "rect": h["rect"]} for h in spec["town"]["houses"]]}
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("report", "build"))
    p.add_argument("--source-root")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    m, near = model(a.source_root)
    probs = check(m, near)
    for k, v in m.counts.items():
        print("  %-26s %d" % (k, v))
    if probs:
        for pr in probs:
            print("PROBLEM:", pr)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    if a.mode == "report":
        return 0
    lns = lines(m)
    order, carts = write(m, lns)
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    s = summary(m)
    s["functions"] = order
    s["carts"] = carts
    s["commands"] = {p_: len(v) for p_, v in lns.items()}
    rl, n_refill = refill_lines(m.spec, m.groundfn)
    _fn, rorder = write_blocks(REFILL, rl, ("refill",), "tools/rift_mines.py (refill)",
                               "Cobblers: STAGING ONLY. Rock back into the Rift spur's retired gated galleries (tools/rift_mines.py)")
    s["refill"] = {"pack": REFILL.name, "functions": rorder, "cells": n_refill, "commands": len(rl["refill"])}
    PLAN.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
    print("wrote %s: %d block functions, %s commands; %d carts; plan %s"
          % (OUT.relative_to(ROOT), len(order), sum(s["commands"].values()), len(carts), PLAN.relative_to(ROOT)))
    print("wrote %s (STAGING ONLY): %d functions, %d cells of rock" % (REFILL.relative_to(ROOT), len(rorder), n_refill))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
