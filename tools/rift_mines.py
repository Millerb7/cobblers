#!/usr/bin/env python
"""The Rift dig camp as a mining town, and the mega stone mine in its spur, from data/rift_mines.json.

The owner, 2026-09-27: "MEGA STONE MINES AND CAVES in the Rift dig camp's spur ... the seam visible early, gated deeper
around badge five or six" and "THE RIFT MINING TOWN LARGER - small caving systems, quarries, worked faces". The data
file says which town that is (the dig camp, not the Craters' mining town) and why; this tool only builds what it says.

One voxel model over the spur, ground from tools/ground.py (the canonical heightmap, rounded; never a world):

  envelope   every cut (the seam cut, the quarries, the worked face), tube (adit, decline, drifts, galleries), room
             (the adit hall), shaft, pocket (crystal faces, drift ends) and chamber, rasterised as data/rift_mines.json
             `geometry` defines them
  carve      the envelope, less a little rock left at the edges of the gated galleries and chambers (roughness)
  shell      every cell within 2 of the envelope, not carved, at or under the ground: written as rock, so nothing this
             build opens is bounded by anything it did not write (natural caves, the export's gravel)
  fittings   frames, lanterns, rails (powered rail: see the data's rail_why), crystals, the gate's plug and grille
  surface    Forge Row, its rock houses, lamp posts, ore piles, derricks and the headframe over the shaft

The gated section (every feature with "gated": true) is reached only through the company gate at the foot of the
decline: a solid plug the build writes, faced with a grille. The pack's advancements put a player who holds the flag
(data/rift_mines.json flag) through it, and turn back anyone without the flag found inside the gated section (the zone
check of docs/mechanics/RIFT_ZONES.md section 4, here for one pocket). Creative and spectator players are left alone.

The Mega chambers are shells. Their guardians are data only (`guardian.mode`); nothing is spawned.

  python tools/rift_mines.py report [--source-root DIR]     the model's checks and counts; nothing written
  python tools/rift_mines.py build  [--source-root DIR]     -> build/datapacks/cobblers_rift_mines, derived/rift_mines/plan.json

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
                     for y in range(f["from_y"], m.ground(x, z))}
        elif f["kind"] == "pocket":
            cells = pocket_cells(f["at"], f["r"])
        elif f["kind"] == "chamber":
            cells = chamber_cells(f["centre"], f["r"], f["height"])
        else:
            raise MineError("feature %s: unknown kind %r" % (f["id"], f["kind"]))
        for c in cells:
            m.mark(*c, fid, gated)


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


def gate(m):
    pal = m.spec["palette"]
    g = m.spec["mine"]["gate"]
    x0, y0, z0, x1, y1, z1 = g["plug"]
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                if m.is_carved(x, y, z):
                    raise MineError("the plug at (%d, %d, %d) is inside a carved space" % (x, y, z))
                m.fit[(x, y, z)] = pick(pal["rubble"], m.spec["seed"], x, y, z, 61)
    gr = g["grille"]
    gx = gr["x"]
    for z in range(gr["z"][0] - 1, gr["z"][1] + 2):
        for y in range(gr["y"][0] - 1, gr["y"][1] + 2):
            inner = gr["z"][0] <= z <= gr["z"][1] and gr["y"][0] <= y <= gr["y"][1]
            m.fit[(gx, y, z)] = "minecraft:iron_bars" if inner else pal["post"] + ("[axis=y]" if gr["y"][0] <= y <= gr["y"][1] else "[axis=z]")
    # a lantern either side of the grille, in the alcove
    kx0, ky0, kz0, kx1, ky1, kz1 = g["knock"]
    hang_lantern(m, kx1, ky0, kz0)
    hang_lantern(m, kx1, ky0, kz1)


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
    g = spec["mine"]["gate"]
    probs = []
    # cover over every gated cell's shell
    gi = np.argwhere(m.gated)
    tops = {}
    for i, k, j in gi:
        tops[(i, k)] = max(tops.get((i, k), -1), j)
    thin = [(i + m.X0, k + m.Z0) for (i, k), j in tops.items()
            if (m.S0[i, k] if m.cut_of[i, k] < 0 else m.cut_floor[i, k]) - (j + m.Y0 + SHELL_R) < spec["cover_min"]]
    if thin:
        probs.append("%d gated columns with under %d of rock over the shell, e.g. %s" % (len(thin), spec["cover_min"], thin[:3]))
    # gated and ungated envelopes kept apart by more than two shells
    ung = m.env & ~m.gated
    touch = dilate(m.gated, 2 * SHELL_R) & ung
    if touch.any():
        i, k, j = np.argwhere(touch)[0]
        probs.append("the gated envelope comes within %d of the ungated at (%d, %d, %d)"
                     % (2 * SHELL_R, i + m.X0, j + m.Y0, k + m.Z0))
    # the gate: knock box walkable and ungated, arrival and exit gated, turn-back ungated and walkable
    ax, ay, az, _ = g["arrive"]
    if not (walkable(m, int(ax), ay, int(az)) and m.gated[m.ix(int(ax), ay, int(az))]):
        probs.append("the gate's arrival %s is not a walkable gated cell" % g["arrive"][:3])
    tx, ty, tz, _ = g["turn_back"]
    if not (walkable(m, int(tx), ty, int(tz)) and not m.gated[m.ix(int(tx), ty, int(tz))]):
        probs.append("the turn-back point %s is not a walkable ungated cell" % g["turn_back"][:3])
    kx0, ky0, kz0, kx1, ky1, kz1 = g["knock"]
    for x in range(kx0, kx1 + 1):
        for z in range(kz0, kz1 + 1):
            if not walkable(m, x, ky0, z) or m.gated[m.ix(x, ky0, z)]:
                probs.append("the knock box's floor (%d, %d, %d) is not a walkable ungated cell" % (x, ky0, z))
    ex0, ey0, ez0, ex1, ey1, ez1 = g["exit"]
    for x in range(ex0, ex1 + 1):
        for z in range(ez0, ez1 + 1):
            if not m.gated[m.ix(x, ey0, z)]:
                probs.append("the exit box cell (%d, %d, %d) is not gated" % (x, ey0, z))
    # every gated envelope cell, and every carved gated cell, reachable from the arrival through its own kind
    start = m.ix(int(ax), ay, int(az))
    for what, cg in (("envelope", m.env & m.gated), ("carved", m.carve & m.gated)):
        lost = cg & ~reach(cg, start)
        if lost.any():
            i, k, j = np.argwhere(lost)[0]
            probs.append("%d %s gated cells not reachable from the arrival, e.g. (%d, %d, %d)"
                         % (int(lost.sum()), what, i + m.X0, j + m.Y0, k + m.Z0))
    # slopes: no tube segment steeper than 0.6
    for f in spec["mine"]["features"]:
        if f["kind"] == "tube":
            for (x0, y0, z0), (x1, y1, z1) in zip(f["path"], f["path"][1:]):
                L = math.hypot(x1 - x0, z1 - z0)
                if L and abs(y1 - y0) / L > 0.6:
                    probs.append("%s: a segment climbs %.2f per block" % (f["id"], abs(y1 - y0) / L))
    # rock left in no gated cell's way on the floor: every tube's feet cells carved (roughness never takes the floor)
    return probs


def zone_boxes(m):
    """The zone check's boxes: each gated feature's carved cells' bounds, one block round, feet-1 to top+1."""
    out = []
    for fid, f in enumerate(m.feats):
        if not f["gated"]:
            continue
        cells = np.argwhere((m.own == fid) & m.env)
        if not len(cells):
            continue
        (i0, k0, j0), (i1, k1, j1) = cells.min(axis=0), cells.max(axis=0)
        out.append({"id": f["id"], "min": [int(i0 + m.X0 - 1), int(j0 + m.Y0 - 1), int(k0 + m.Z0 - 1)],
                    "max": [int(i1 + m.X0 + 1), int(j1 + m.Y0 + 1), int(k1 + m.Z0 + 1)]})
    return out


def zone_problems(m, boxes):
    """A zone box must hold no ungated carved cell and nothing over the ground: it would turn back a player standing
    in front of the gate, or on the surface."""
    probs = []
    ung = m.carve & ~m.gated
    for b in boxes:
        (x0, y0, z0), (x1, y1, z1) = b["min"], b["max"]
        sub = ung[x0 - m.X0:x1 - m.X0 + 1, z0 - m.Z0:z1 - m.Z0 + 1, y0 - m.Y0:y1 - m.Y0 + 1]
        if sub.any():
            probs.append("zone box %s holds ungated carved cells" % b["id"])
        tops = np.minimum(m.S0, m.cut_floor)[x0 - m.X0:x1 - m.X0 + 1, z0 - m.Z0:z1 - m.Z0 + 1]
        if y1 + 1 >= tops.min():
            probs.append("zone box %s reaches y%d, at or over the ground (y%d) somewhere under it" % (b["id"], y1, tops.min()))
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


def gate_files(m, boxes):
    spec = m.spec
    g = spec["mine"]["gate"]
    flag = spec["flag"]["advancement"]
    has = "@s[advancements={%s=true}]" % flag
    lacks = "@s[gamemode=!creative,gamemode=!spectator,advancements={%s=false}]" % flag
    ax, ay, az, ayaw = g["arrive"]
    tx, ty, tz, tyaw = g["turn_back"]

    def box_cond(b):
        (x0, y0, z0), (x1, y1, z1) = b
        return {"condition": "minecraft:entity_properties", "entity": "this",
                "predicate": {"location": {"dimension": "minecraft:overworld", "position": {
                    "x": {"min": x0, "max": x1 + 1}, "y": {"min": y0, "max": y1 + 1}, "z": {"min": z0, "max": z1 + 1}}}}}

    def adv(conds, reward):
        return {"criteria": {"here": {"trigger": "minecraft:location", "conditions": {"player": conds}}},
                "rewards": {"function": reward}}

    k = g["knock"]
    e = g["exit"]
    zone = [box_cond((b["min"], b["max"])) for b in boxes]
    files = {
        "advancement/%s/gate_knock.json" % FOLDER: adv([box_cond((k[:3], k[3:]))], "%s:%s/gate/knock" % (NS, FOLDER)),
        "advancement/%s/gate_exit.json" % FOLDER: adv([box_cond((e[:3], e[3:]))], "%s:%s/gate/exit" % (NS, FOLDER)),
        "advancement/%s/zone.json" % FOLDER: adv([{"condition": "minecraft:any_of", "terms": zone}] if len(zone) > 1 else zone,
                                                 "%s:%s/gate/zone" % (NS, FOLDER)),
    }
    badge = spec["flag"]["badge"]
    fn = {
        "gate/knock": [
            "# the company gate (tools/rift_mines.py): a player holding %s is put through; anyone else is told" % flag,
            "advancement revoke @s only %s:%s/gate_knock" % (NS, FOLDER),
            "execute if entity %s run tp @s %s %d %s %d 0" % (has, ax, ay, az, ayaw),
            "execute if entity %s run title @s actionbar %s" % (has, text("The grille swings aside, and shuts behind you.", color="gray")),
            "execute unless entity %s run title @s actionbar %s" % (has, text("Sealed by the company. The deep galleries open with the %s badge." % ordinal(badge), color="gold"))],
        "gate/exit": [
            "# the way out from behind the gate: anyone, flag or not",
            "advancement revoke @s only %s:%s/gate_exit" % (NS, FOLDER),
            "tp @s %s %d %s %d 0" % (tx, ty, tz, tyaw)],
        "gate/zone": [
            "# the zone check: anyone in the gated galleries without the flag is turned back to the front of the gate",
            "advancement revoke @s only %s:%s/zone" % (NS, FOLDER),
            "execute if entity %s run function %s:%s/gate/turn_back" % (lacks, NS, FOLDER)],
        "gate/turn_back": [
            "# a mount first, then the player (docs/mechanics/RIFT_ZONES.md section 4)",
            "execute on vehicle run tp @s %s %d %s" % (tx, ty, tz),
            "tp @s %s %d %s %d 0" % (tx, ty, tz, tyaw),
            "title @s actionbar %s" % text("Turned back: the deep galleries open with the %s badge." % ordinal(badge), color="gold")],
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


def write(m, lns, boxes):
    if OUT.exists():
        shutil.rmtree(OUT)
    base = OUT / "data" / NS
    fn = base / "function" / FOLDER
    fn.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: the Rift dig camp's mines, quarries and the mega stone mine (tools/rift_mines.py)"}},
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
                part = FL.ensure_loaded(["# Generated by tools/rift_mines.py: %s, tile %d %d" % (pas, t[0], t[1])]
                                        + body[j:j + PART])
                bad = FL.check_lines(part, name)
                if bad:
                    raise MineError("function %s would be refused: %s" % (name, bad[:3]))
                (fn / (name + ".mcfunction")).write_text("\n".join(part) + "\n", encoding="utf-8")
                order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    files, gfn = gate_files(m, boxes)
    for rel, obj in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")
    for name, body in gfn.items():
        p = fn / (name + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(body) + "\n", encoding="utf-8")
    head, go, carts = cart_files(m)
    (fn / "carts.mcfunction").write_text("\n".join(head) + "\n", encoding="utf-8")
    (fn / "carts_go.mcfunction").write_text("\n".join(go) + "\n", encoding="utf-8")
    return order, carts


# ------------------------------------------------------------------ driver

def model(source_root=None, spec=None):
    spec = spec or load()
    g = G.Ground(source_root)
    m = Model(spec, g)
    rasterise(m)
    carve(m)
    near = shell(m)
    build_blocks(m, near)
    frames(m)
    n_rails = tracks(m)
    n_cryst = crystals(m)
    gate(m)
    n_glint = glints(m)
    surface(m)
    # a fitting or a surface block never lands where the shell is not, unless it is carved or over the ground
    m.counts = {"envelope cells": int(m.env.sum()), "carved cells": int(m.carve.sum()),
                "gated carved cells": int((m.carve & m.gated).sum()), "shell cells": len(m.blocks),
                "rails": n_rails, "mega stone crystals": n_cryst, "dormant crystal glints": n_glint,
                "fittings": len(m.fit), "surface blocks": len(m.surf)}
    return m, near


def summary(m, boxes):
    spec = m.spec
    feats = {f["id"]: f for f in spec["mine"]["features"]}
    out = {"schema": "cobblers.derived.rift_mines/1", "counts": m.counts, "zone_boxes": boxes,
           "gate": spec["mine"]["gate"], "flag": spec["flag"]["advancement"],
           "seam": {"cut": spec["mine"]["seam"]["cut"], "face_z": spec["town"]["cuts"][0]["rect"][1] - 1,
                    "x": [spec["town"]["cuts"][0]["rect"][0], spec["town"]["cuts"][0]["rect"][2]]},
           "chambers": [{"id": f["id"], "centre": f["centre"], "heart": f.get("_heart"), "guardian": f["guardian"]}
                        for f in spec["mine"]["features"] if f["kind"] == "chamber"],
           "cuts": [{"id": c["id"], "rect": c["rect"], "floor": c["floor"]} for c in spec["town"]["cuts"]],
           "drifts": [{"id": k, "path": v["path"]} for k, v in feats.items() if k.startswith("drift_") and not v.get("gated")],
           "houses": [{"id": h["id"], "rect": h["rect"]} for h in spec["town"]["houses"]]}
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=("report", "build"))
    p.add_argument("--source-root")
    p.add_argument("--server-dir", help="accepted for tools/reapply.py prepare's sake; not read")
    a = p.parse_args(argv)
    m, near = model(a.source_root)
    boxes = zone_boxes(m)
    probs = check(m, near) + zone_problems(m, boxes)
    for k, v in m.counts.items():
        print("  %-26s %d" % (k, v))
    print("  %-26s %d" % ("zone boxes", len(boxes)))
    if probs:
        for pr in probs:
            print("PROBLEM:", pr)
        raise SystemExit("%d problem(s): nothing written" % len(probs))
    if a.mode == "report":
        return 0
    lns = lines(m)
    order, carts = write(m, lns, boxes)
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    s = summary(m, boxes)
    s["functions"] = order
    s["carts"] = carts
    s["commands"] = {p_: len(v) for p_, v in lns.items()}
    PLAN.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
    print("wrote %s: %d block functions, %s commands; %d carts; plan %s"
          % (OUT.relative_to(ROOT), len(order), sum(s["commands"].values()), len(carts), PLAN.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
