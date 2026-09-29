#!/usr/bin/env python
"""Offline plan audit of the Rift mines: nothing overlaps another build or path, the seam's one crystal sits behind the
company grille inside its per-player ward, and the staging refill fills exactly the retired gated section. Independent
of tools/rift_mines.py's model: it rasterises data/rift_mines.json itself, by the `geometry` the data file states, and
takes every expectation about other builds from THEIR data (the camp's plan and placements, the Rift sculpt's entrance
ramp, data/towns.json), never from the generated output. The generated packs are then replayed and checked against
those expectations.

The gated galleries, chambers and Heart were retired on 2026-09-27 (docs/world-building/SOUTHERN_RIFT_MEGA.md decisions
1-2: the mega stone mine is the gulch's). What was checked on them (separation, gate, zone) is gone with them; nothing
may be gated now, and the retired envelope is checked only as the refill's target.

The plan (data only):
  pocket      the spur pocket is re-measured from the canonical heightmap by the data's own words (`pocket`: every
              column at or under floor_y 4-connected to a seed): every traced quarry lies inside it and keeps `inset`
              clear of its edge, the columns each quarry takes are counted against it, no street or house stands in a
              quarry, no house stands on more than 3 blocks of relief, and the camp track's end still reaches the seam
              yard and the adit's mouth on foot without crossing one (the causeway between the two quarries)
  overlap     every column this build may write (its envelope and its shell, two round it; its houses, piles, streets,
              lamp posts, derricks, headframe, tracks, the collapse) keeps `keep_clear.margin` from: the camp's streets,
              plaza, anchors and lots (derived/towns/rift_dig_camp_plan.json), every donor and earthwork the placements
              give the camp, the excavation haul road's path (the ramp tools/rift_skin.py paves, from the sculpt's
              ring), the data's own keep-clear boxes, and every other settlement's footprint. Forge Row may meet the
              camp track end to end; it may not overlap it
  nothing     no live feature is gated, and none carries crystals: the seam's one crystal is the tease's
  gated
  tease       the grille's cells are envelope and close drift C whole (with them shut, the face's front cannot be reached
              from the adit through the envelope); the face box is not envelope and its front meets the pocket; the ward
              box (read from the pack's advancement) holds the grille, the pocket and the face box with ward_margin to
              spare, and its function gives the effect only to a player lacking the flag
  collapse    the collapse box is not envelope
The output (build/datapacks/cobblers_rift_mines, replayed in index order):
  inside      every block write falls in a column the plan may write, inside the grid
  no stray    no cell under the ground ends as air unless it is envelope
  sealed      every cell next to the envelope, under the ground and not envelope, ends as a block this build wrote,
              not air, not a fluid
  crystal     exactly the tease's crystals are written, all in the face box; no gate, knock, exit or zone advancement
              is left in the pack
  blocks      no written block is named by a spawn condition (data/spawn_blocks.json), no water, no lava, no meteorid
              ore (they drop evolution stones)
  limits      tools/function_limits.py finds nothing the server would refuse
The refill (build/datapacks/cobblers_rift_mines_refill, staging only):
  exact       its writes are exactly the retired gated envelope, every one rock (no air, no fluid), none in a live
              envelope cell or the collapse

Fails closed: no pack, an empty index, no camp plan, no tease crystal, no retired envelope or no refill is a failure,
not a pass.

  python tools/rift_mines_audit.py [--source-root DIR]      writes derived/rift_mines/audit.json; exit 1 on any problem
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as GR            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "rift_mines.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_rift_mines"
FN = PACK / "data" / "cobblers" / "function" / "rift_mines"
REFILL_FN = ROOT / "build" / "datapacks" / "cobblers_rift_mines_refill" / "data" / "cobblers" / "function" / "rift_mines_refill"
CAMP_PLAN = ROOT / "derived" / "towns" / "rift_dig_camp_plan.json"
SCULPT_PLAN = ROOT / "derived" / "rift_sculpt" / "plan.json"
OUT = ROOT / "derived" / "rift_mines" / "audit.json"
SHELL = 2
FLUIDS = ("minecraft:water", "minecraft:lava", "minecraft:flowing_water", "minecraft:flowing_lava")
AIRS = ("minecraft:air", "minecraft:cave_air", "minecraft:void_air")


def half_up(v):
    return int(math.floor(v + 0.5))


class Grid:
    """A boolean volume over the data's grid, indexed [x, z, y] in world coordinates through at()."""

    def __init__(self, spec):
        (self.x0, self.x1), (self.z0, self.z1), (self.y0, self.y1) = spec["grid"]["x"], spec["grid"]["z"], spec["grid"]["y"]
        self.shape = (self.x1 - self.x0 + 1, self.z1 - self.z0 + 1, self.y1 - self.y0 + 1)

    def new(self, dtype=bool):
        return np.zeros(self.shape, dtype)

    def has(self, x, y, z):
        return self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1 and self.y0 <= y <= self.y1

    def idx(self, x, y, z):
        return x - self.x0, z - self.z0, y - self.y0


# ------------------------------------------------------------------ the audit's own rasterising, from the data's words

def stamp_tube(path, r, height):
    """Per the data: n = ceil(4 * horizontal length) + 1 points per segment; each stamps a (2r+1)^2 square of columns
    round (floor(x+.5), floor(z+.5)) from feet floor(y+.5) up `height` blocks."""
    cells = set()
    for a, b in zip(path, path[1:]):
        length = math.sqrt((b[0] - a[0]) ** 2 + (b[2] - a[2]) ** 2)
        n = int(math.ceil(4 * length)) + 1 if length > 0 else 1
        for s in range(n):
            f = 0.0 if n == 1 else s / (n - 1)
            px, py, pz = (half_up(a[q] + (b[q] - a[q]) * f) for q in range(3))
            for x in range(px - r, px + r + 1):
                for z in range(pz - r, pz + r + 1):
                    cells.update((x, y, z) for y in range(py, py + height))
    return cells


def stamp_pocket(c, r):
    cells = set()
    for x in range(c[0] - r - 1, c[0] + r + 2):
        for z in range(c[2] - r - 1, c[2] + r + 2):
            q = (x - c[0]) ** 2 + (z - c[2]) ** 2
            if q <= (r + 0.5) ** 2:
                hi = c[1] + (r + 1 if q <= (r - 0.5) ** 2 else r)
                cells.update((x, y, z) for y in range(c[1], hi + 1))
    return cells


def stamp_chamber(c, r, height):
    cells = set()
    big = r + 0.5
    for x in range(c[0] - r - 1, c[0] + r + 2):
        for z in range(c[2] - r - 1, c[2] + r + 2):
            d = math.sqrt((x - c[0]) ** 2 + (z - c[2]) ** 2)
            if d <= big:
                rise = max(3, int(math.floor((height - 1) * math.sqrt(max(0.0, 1.0 - (d / big) ** 2)) + 0.5)))
                cells.update((x, y, z) for y in range(c[1], c[1] + rise + 1))
    return cells


def in_ring(ring, x, z):
    """Per the data (geometry `traced`): the column's centre inside the ring by the even-odd rule."""
    px, pz, hit = x + 0.5, z + 0.5, False
    for i in range(len(ring)):
        ax, az = ring[i]
        bx, bz = ring[(i + 1) % len(ring)]
        if (az > pz) != (bz > pz) and px < ax + (pz - az) / (bz - az) * (bx - ax):
            hit = not hit
    return hit


def stamp_swathe(path, width):
    """Per the data (geometry `swathe`): n = ceil(4 * length) + 1 samples a segment, each stamping the square of
    Chebyshev radius width // 2 round its rounded centre."""
    r, cols = width // 2, set()
    for (x0, z0), (x1, z1) in zip(path, path[1:]):
        L = math.hypot(x1 - x0, z1 - z0)
        n = int(math.ceil(4 * L)) + 1 if L > 0 else 1
        for s in range(n):
            t = s / (n - 1) if n > 1 else 0.0
            cx, cz = half_up(x0 + (x1 - x0) * t), half_up(z0 + (z1 - z0) * t)
            cols |= {(cx + dx, cz + dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1)}
    return cols


def columns_of_cut(cut):
    """Per the data (geometry `cut`): the footprint of one cut, by its kind."""
    k = cut["kind"]
    if k in ("pit", "hillside"):
        x0, z0, x1, z1 = cut["rect"]
        return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    if k == "traced":
        ring = cut["outline"]
        xs, zs = [p[0] for p in ring], [p[1] for p in ring]
        return {(x, z) for x in range(min(xs) - 1, max(xs) + 2) for z in range(min(zs) - 1, max(zs) + 2)
                if in_ring(ring, x, z)}
    if k == "trench":
        return stamp_swathe(cut["path"], cut["width"])
    raise SystemExit("unknown cut kind %r in %s" % (k, cut["id"]))


def edge_steps(cols):
    """Per the data: the 4-neighbour steps to the nearest column outside the footprint, less one."""
    from collections import deque
    e, q = {}, deque()
    for (x, z) in cols:
        if any((x + dx, z + dz) not in cols for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            e[(x, z)] = 0
            q.append((x, z))
    while q:
        x, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c = (x + dx, z + dz)
            if c in cols and c not in e:
                e[c] = e[(x, z)] + 1
                q.append(c)
    return e


def ramp_floor(rp, floor):
    """Per the data (geometry `ramp`): y from `top` at the path's start to `floor` at its end, by the fraction of the
    path's length; each column takes its nearest sample's y, ties to the earlier sample."""
    if not rp:
        return {}
    r = rp["width"] // 2
    segs = [(p, q, math.hypot(q[0] - p[0], q[1] - p[1])) for p, q in zip(rp["path"], rp["path"][1:])]
    total = sum(s[2] for s in segs) or 1.0
    near, ys, run = {}, {}, 0.0
    for (x0, z0), (x1, z1), L in segs:
        n = int(math.ceil(4 * L)) + 1 if L > 0 else 1
        for s in range(n):
            t = s / (n - 1) if n > 1 else 0.0
            cx, cz = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
            y = half_up(rp["top"] + (floor - rp["top"]) * ((run + L * t) / total))
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    c = (half_up(cx) + dx, half_up(cz) + dz)
                    dd = math.hypot(c[0] - cx, c[1] - cz)
                    if c not in near or dd < near[c]:
                        near[c], ys[c] = dd, y
        run += L
    return ys


def floors_of_cut(cut, ground):
    """{(x, z): y_f} for one cut, from the data's `geometry` words alone."""
    cols = columns_of_cut(cut)
    if cut["kind"] == "trench":
        return {(x, z): ground(x, z) - cut["depth"] for (x, z) in cols}
    b = cut.get("bench") or {}
    steps = edge_steps(cols) if cut["kind"] == "traced" else None
    out = {}
    for (x, z) in cols:
        if cut["kind"] == "traced":
            dists = [steps[(x, z)]]
        elif cut["kind"] == "pit":
            x0, z0, x1, z1 = cut["rect"]
            dists = [x - x0, x1 - x, z - z0, z1 - z]
        else:
            x0, z0, x1, z1 = cut["rect"]
            side = {"west": x - x0, "east": x1 - x, "north": z - z0, "south": z1 - z}
            dists = [side[s] for s in cut.get("benches") or []]
        lvl = max(0, b.get("levels", 1) - 1 - min(dists) // b.get("run", 1)) if dists else 0
        out[(x, z)] = cut["floor"] + b.get("rise", 0) * lvl
    for c, y in ramp_floor(cut.get("ramp"), cut["floor"]).items():
        if c in out:
            out[c] = y
    return out


def stamp(f, ground):
    k = f["kind"]
    if k == "tube":
        cells = stamp_tube(f["path"], f["r"], f["height"])
        if f.get("pocket"):
            cells |= stamp_pocket(f["pocket"]["at"], f["pocket"]["r"])
    elif k == "room":
        b = f["box"]
        cells = {(x, y, z) for x in range(b[0], b[3] + 1) for y in range(b[1], b[4] + 1) for z in range(b[2], b[5] + 1)}
    elif k == "shaft":
        (cx, cz), r = f["centre"], f["r"]
        cells = {(x, y, z) for x in range(cx - r, cx + r + 1) for z in range(cz - r, cz + r + 1)
                 for y in range(f["from_y"], ground(x, z))}
    elif k == "pocket":
        cells = stamp_pocket(f["at"], f["r"])
    elif k == "chamber":
        cells = stamp_chamber(f["centre"], f["r"], f["height"])
    else:
        raise SystemExit("unknown feature kind %r in %s" % (k, f["id"]))
    return cells


def plan(spec, ground):
    """(gated set, ungated set, effective ground {(x, z): y}, cut columns) from the data alone."""
    gated, ungated, eff, cutcols = set(), set(), {}, set()
    for cut in spec["town"]["cuts"]:
        for (x, z), yf in floors_of_cut(cut, ground).items():
            g = ground(x, z)
            if g > yf:
                eff[(x, z)] = min(eff.get((x, z), g), yf)
                cutcols.add((x, z))
                ungated.update((x, y, z) for y in range(yf + 1, g + 7))
    for f in spec["mine"]["features"]:
        (gated if f.get("gated") else ungated).update(stamp(f, ground))
    return gated, ungated - gated, eff, cutcols


# ------------------------------------------------------------------ what else is there, from its own data

def camp_cells(placements, camp_plan):
    """{(x, z): what} for every column the camp's own builds use."""
    out = {}

    def rect(r, what):
        for x in range(r[0], r[2] + 1):
            for z in range(r[1], r[3] + 1):
                out[(x, z)] = what
    for sid, st in camp_plan["streets"].items():
        for z, _y, xa, xb in st["cells"]:
            for x in range(xa, xb + 1):
                out[(x, z)] = "camp street %s" % sid
    rect(camp_plan["plaza"]["rect"], "camp plaza")
    for a in camp_plan["anchors"]:
        rect(a["rect"], "camp anchor %s" % a["id"])
    for lot in camp_plan["lots"]:
        rect(lot["rect"], "camp lot %s" % lot["id"])
    for lamp in camp_plan.get("lamps") or []:
        out[(lamp["at"][0], lamp["at"][2])] = "camp lamp"
    for q in placements["placements"]:
        if q.get("settlement") != "rift_dig_camp":
            continue
        pos, size = q.get("position"), q.get("size")
        if pos and size:
            rect([pos["x"], pos["z"], pos["x"] + size[0] - 1, pos["z"] + size[2] - 1], "camp donor %s" % q["id"])
        for c in q.get("commands") or []:
            mm = re.match(r"(?:setblock|fill) (-?\d+) -?\d+ (-?\d+)(?: (-?\d+) -?\d+ (-?\d+))?", c)
            if mm:
                xa, za = int(mm.group(1)), int(mm.group(2))
                xb, zb = (int(mm.group(3)), int(mm.group(4))) if mm.group(3) else (xa, za)
                rect([min(xa, xb), min(za, zb), max(xa, xb), max(za, zb)], "camp earthwork %s" % q["id"])
    return out


def haul_road(source_root=None):
    """The columns tools/rift_skin.py paves for the excavation haul road, from the sculpt's ring (its own loop)."""
    if SCULPT_PLAN.is_file():
        sc = json.loads(SCULPT_PLAN.read_text(encoding="utf-8"))
        ring, nrm = sc["ring"], sc["normals"]
        ent = next(e for e in sc["entrances"] if e["id"] == "excavation_haul_road")
    else:
        import rift_heightmap as RH
        b = RH.build(source_root)
        X0, _X1, Z0, _Z1 = b["box"]
        ring = [[int(x) + X0, int(z) + Z0] for z, x in b["ring"]]
        nrm = [[nx, nz] for nz, nx in b["nrm"]]
        bi, e, _d = next(t for t in b["ent"] if t[1]["id"] == "excavation_haul_road")
        ent = dict(e, ring=bi)
    cols = set()
    bi, half = ent["ring"], ent.get("gap", 30)
    for j in range(-half, half + 1):
        k = (bi + j) % len(ring)
        (qx, qz), (mx, mz) = ring[k], nrm[k]
        f = 1 - abs(j) / (half + 1.0)
        if f < 0.25:
            continue
        wide = max(1, int(ent.get("width", 4) * f))
        for d in range(-14, 30):
            for dw in range(-(wide // 2), wide - wide // 2):
                cols.add((int(round(qx + mx * d - mz * dw)), int(round(qz + mz * d + mx * dw))))
    return cols


def plan_columns(spec, gated, ungated, cutcols):
    """{(x, z)} every column the build may write, and the subset that is its street."""
    env = {(x, z) for x, _y, z in gated | ungated} | cutcols
    cols = set()
    for x, z in env:
        for dx in range(-SHELL, SHELL + 1):
            for dz in range(-SHELL, SHELL + 1):
                cols.add((x + dx, z + dz))
    t = spec["town"]
    street = set()
    for st in t["streets"]:
        street |= stamp_swathe(st["polyline"], st["width"])
    cols |= street
    for h in t["houses"]:
        x0, z0, x1, z1 = h["rect"]
        cols |= {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    for p in t["ore_piles"]:
        (cx, cz), (rx, rz) = p["centre"], p["r"]
        cols |= {(x, z) for x in range(int(cx - rx) - 1, int(cx + rx) + 2) for z in range(int(cz - rz) - 1, int(cz + rz) + 2)}
    for x, z in t["lamp_posts"]:
        cols.add((x, z))
    for d in t["derricks"]:
        x, z = d["at"]
        cols |= {(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
        cols |= {(x + d["boom"][0] * k, z + d["boom"][1] * k) for k in range(d["reach"] + 1)}
    for tr in t["tracks"]:
        (xa, za), (xb, zb) = tr["from"], tr["to"]
        cols |= {(x, z) for x in range(min(xa, xb), max(xa, xb) + 1) for z in range(min(za, zb), max(za, zb) + 1)}
    hf = spec["mine"]["headframe"]
    cols |= {(hf["at"][0] + dx, hf["at"][1] + dz) for dx in range(-3, 4) for dz in range(-3, 4)}
    pl = spec["mine"]["collapse"]["box"]
    cols |= {(x, z) for x in range(pl[0], pl[3] + 1) for z in range(pl[2], pl[5] + 1)}
    fb = spec["mine"]["tease"]["face"]["box"]
    cols |= {(x, z) for x in range(fb[0], fb[3] + 1) for z in range(fb[2], fb[5] + 1)}
    return cols, street


# ------------------------------------------------------------------ replaying the output

CMD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")


def replay(grid, fn_dir=None):
    """(final {(x, y, z): block}, writes outside the grid, function files) from the pack, in its index order."""
    fn_dir = fn_dir or FN
    idx = fn_dir / "index.txt"
    if not idx.is_file():
        raise SystemExit("no %s: run `python tools/rift_mines.py build` first" % idx.relative_to(ROOT))
    names = [n for n in idx.read_text(encoding="utf-8").split("\n") if n.strip()]
    if not names:
        raise SystemExit("%s lists no function: nothing was generated" % idx.relative_to(ROOT))
    final, outside, files = {}, [], []
    for n in names:
        f = fn_dir / (n + ".mcfunction")
        files.append(f)
        for ln in f.read_text(encoding="utf-8").splitlines():
            m = CMD.match(ln.strip())
            if not m:
                continue
            a = [int(v) for v in m.groups()[1:4]]
            b = [int(v) for v in m.groups()[4:7]] if m.group(5) else a
            blk = m.group(8)
            for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                    for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
                        if not grid.has(x, y, z):
                            outside.append((x, y, z))
                        final[(x, y, z)] = blk
    return final, outside, files


def adv_box(name):
    """The one position box of an advancement in the pack, as ((x0, y0, z0), (x1, y1, z1)) of blocks, or None."""
    adv = PACK / "data" / "cobblers" / "advancement" / "rift_mines" / name
    if not adv.is_file():
        return None
    doc = json.loads(adv.read_text(encoding="utf-8"))
    conds = doc["criteria"]["here"]["conditions"]["player"]
    p = conds[0]["predicate"]["location"]["position"]
    # a position range reads the player's feet as a double; max is the far face of the last block
    return ((p["x"]["min"], p["y"]["min"], p["z"]["min"]), (p["x"]["max"] - 1, p["y"]["max"] - 1, p["z"]["max"] - 1))


# ------------------------------------------------------------------ the audit

def standable(open_, x, y, z):
    return (x, y, z) in open_ and (x, y + 1, z) in open_ and (x, y - 1, z) not in open_


def audit(source_root=None):
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    grid = Grid(spec)
    g = GR.Ground(source_root)
    ground = g
    probs, notes = [], {}
    gated, ungated, eff, cutcols = plan(spec, ground)
    top = lambda x, z: eff.get((x, z), ground(x, z))

    # ---- overlap
    if not CAMP_PLAN.is_file():
        raise SystemExit("no %s: run `python tools/town_plan.py rift_dig_camp` first" % CAMP_PLAN.relative_to(ROOT))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    camp = camp_cells(placements, json.loads(CAMP_PLAN.read_text(encoding="utf-8")))
    cols, street = plan_columns(spec, gated, ungated, cutcols)
    margin = spec["keep_clear"]["margin"]
    others = dict(camp)
    for b in spec["keep_clear"]["boxes"]:
        x0, z0, x1, z1 = b["rect"]
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                others.setdefault((x, z), "keep-clear %s" % b["id"])
    road = haul_road(source_root)
    for c in road:
        others.setdefault(c, "the excavation haul road")
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    for t in towns:
        fp = t.get("footprint") or {}
        if t["id"] == "rift_dig_camp" or "min_x" not in fp:
            continue
        if fp["max_x"] < grid.x0 - 10 or fp["min_x"] > grid.x1 + 10 or fp["max_z"] < grid.z0 - 10 or fp["min_z"] > grid.z1 + 10:
            continue
        for x in range(fp["min_x"], fp["max_x"] + 1):
            for z in range(fp["min_z"], fp["max_z"] + 1):
                others.setdefault((x, z), "settlement %s" % t["id"])
    hits = {}
    for (x, z) in cols:
        for dx in range(-margin, margin + 1):
            for dz in range(-margin, margin + 1):
                what = others.get((x + dx, z + dz))
                if what is None:
                    continue
                if (x, z) in street and what.startswith(("camp street", "camp lamp")) and (dx, dz) != (0, 0):
                    continue            # Forge Row meets the camp track end to end
                hits.setdefault(what, (x, z))
    for what, at in sorted(hits.items()):
        probs.append("overlap: the build's column %s comes within %d of %s" % (at, margin, what))
    notes["columns the build may write"] = len(cols)
    notes["camp cells kept clear"] = len(camp)
    notes["haul road columns kept clear"] = len(road)
    probs += pocket_problems(spec, grid, ground, notes)
    p2, n2 = plan_problems(spec, gated, ungated)
    probs += p2
    notes.update(n2)
    probs += output_problems(spec, grid, gated, ungated, top, cols, notes)
    probs += refill_problems(spec, grid, ungated, ground, notes)
    return probs, notes


def measure_pocket(spec, grid, ground):
    """The spur pocket, re-measured from the canonical heightmap by the data's own words: every column of the grid at
    or under `floor_y`, 4-connected to `seed`. Independent of anything this build emits."""
    from collections import deque
    pk = spec["pocket"]
    sx, sz = pk["seed"]
    if ground(sx, sz) > pk["floor_y"]:
        raise SystemExit("the pocket's seed (%d, %d) is above floor_y %d on this heightmap" % (sx, sz, pk["floor_y"]))
    seen = {(sx, sz)}
    q = deque(seen)
    while q:
        x, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c = (x + dx, z + dz)
            if c in seen or not (grid.x0 <= c[0] <= grid.x1 and grid.z0 <= c[1] <= grid.z1):
                continue
            if ground(c[0], c[1]) <= pk["floor_y"]:
                seen.add(c)
                q.append(c)
    return seen


def pocket_problems(spec, grid, ground, notes):
    """The reshape's own claim: the traced quarries are cut from the pocket the heightmap has, they keep `inset` clear
    of its edge, and the camp can still walk from the track's end to the seam yard without crossing a quarry."""
    pk = spec["pocket"]
    probs = []
    pocket = measure_pocket(spec, grid, ground)
    notes["pocket columns measured"] = len(pocket)
    if len(pocket) != pk["measured"]["columns"]:
        probs.append("pocket: the heightmap gives %d columns, data/rift_mines.json records %d"
                     % (len(pocket), pk["measured"]["columns"]))
    inset, allcut, traced = pk["inset"], set(), {}
    for cut in spec["town"]["cuts"]:
        cols = columns_of_cut(cut)
        allcut |= cols
        if cut["kind"] != "traced":
            continue
        traced[cut["id"]] = cols
        out = cols - pocket
        if out:
            probs.append("pocket: %s has %d columns outside the pocket, e.g. %s"
                         % (cut["id"], len(out), sorted(out)[0]))
        near = [c for c in cols
                if any((c[0] + dx, c[1] + dz) not in pocket for dx in range(-inset, inset + 1)
                       for dz in range(-inset, inset + 1) if abs(dx) + abs(dz) <= inset)]
        if near:
            probs.append("pocket: %s has %d columns within %d of the pocket's edge, e.g. %s"
                         % (cut["id"], len(near), inset, sorted(near)[0]))
        notes["%s columns" % cut["id"]] = len(cols)
    notes["traced share of the pocket"] = round(100.0 * len(set().union(*traced.values())) / len(pocket), 1) if traced else 0
    notes["every cut's share of the pocket"] = round(100.0 * len(allcut & pocket) / len(pocket), 1)
    # on foot from the camp track's end to the seam yard, over ground no cut but the seam yard's own has taken
    seam = columns_of_cut(next(c for c in spec["town"]["cuts"] if c["id"] == spec["mine"]["seam"]["cut"]))
    land = (pocket - allcut) | seam
    start = tuple(spec["town"]["streets"][0]["polyline"][0])
    if start not in land:
        probs.append("pocket: Forge Row starts at %s, which is not open ground" % (start,))
    else:
        from collections import deque
        saw, q = {start}, deque([start])
        while q:
            x, z = q.popleft()
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c = (x + dx, z + dz)
                if c in land and c not in saw:
                    saw.add(c)
                    q.append(c)
        yard = tuple(spec["town"]["streets"][0]["polyline"][-1])
        adit = (spec["mine"]["features"][0]["path"][0][0], spec["mine"]["features"][0]["path"][0][2])
        for name, c in (("the street's end at the seam yard", yard), ("the adit's mouth", adit)):
            if c not in saw:
                probs.append("pocket: %s %s cannot be reached on foot from Forge Row's start without crossing a quarry"
                             % (name, c))
        notes["ground walkable from Forge Row's start"] = len(saw)
    # the streets and the town stand on ground, not in a quarry
    for st in spec["town"]["streets"]:
        inside = stamp_swathe(st["polyline"], st["width"]) & (allcut - seam)
        if inside:
            probs.append("pocket: street %s runs through a quarry at %s (%d columns)"
                         % (st["id"], sorted(inside)[0], len(inside)))
    for h in spec["town"]["houses"]:
        x0, z0, x1, z1 = h["rect"]
        rect = {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
        inside = rect & (allcut - seam)
        if inside:
            probs.append("pocket: house %s stands in a quarry at %s" % (h["id"], sorted(inside)[0]))
        hs = [ground(x, z) for (x, z) in rect]
        if max(hs) - min(hs) > 3:
            probs.append("pocket: house %s stands on %d blocks of relief" % (h["id"], max(hs) - min(hs)))
    return probs


def plan_problems(spec, gated, ungated):
    """Nothing gated, the tease and the collapse, on the data's own envelopes. Pure: no files but the ward's advancement."""
    probs, notes = [], {}
    if gated:
        probs.append("gated: %d gated envelope cells; the spur's gated section is retired (SOUTHERN_RIFT_MEGA.md decision 1)"
                     % len(gated))
    crys = [f["id"] for f in spec["mine"]["features"] if f.get("crystals")]
    if crys:
        probs.append("gated: features still carry crystals: %s (the seam's one crystal is the tease's)" % crys)
    t = spec["mine"].get("tease")
    if not t:
        probs.append("tease: the data has no tease: nothing to audit")
        return probs, notes
    gr = t["grille"]
    grille = {(x, y, gr["z"]) for x in range(gr["x"][0], gr["x"][1] + 1) for y in range(gr["y"][0], gr["y"][1] + 1)}
    if not grille <= ungated:
        probs.append("tease: %d grille cells are not in the drift" % len(grille - ungated))
    fb = t["face"]["box"]
    face = {(x, y, z) for x in range(fb[0], fb[3] + 1) for y in range(fb[1], fb[4] + 1) for z in range(fb[2], fb[5] + 1)}
    if face & ungated:
        probs.append("tease: the face box overlaps the envelope at %s" % sorted(face & ungated)[:3])
    step = {"south": (0, 0, 1), "north": (0, 0, -1), "east": (1, 0, 0), "west": (-1, 0, 0)}[t["face"]["front"]]
    front = {(x + step[0], y + step[1], z + step[2]) for x, y, z in face} - face
    if not front & ungated:
        probs.append("tease: the face's front meets no envelope cell")
    # with the grille shut, the face's front is cut off from the adit's mouth
    open_ = ungated - grille
    start = next(iter(sorted(front & ungated)), None)
    seen = {start} if start else set()
    stack = list(seen)
    while stack:
        x, y, z = stack.pop()
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            q = (x + d[0], y + d[1], z + d[2])
            if q in open_ and q not in seen:
                seen.add(q)
                stack.append(q)
    adit = tuple(spec["mine"]["features"][0]["path"][0])
    notes["envelope cells behind the grille"] = len(seen)
    if adit in seen:
        probs.append("tease: the face's front is reached from the adit's mouth %s without passing the grille" % (adit,))
    if not seen:
        probs.append("tease: nothing open in front of the face")
    # the ward, from the pack's own advancement
    ward = adv_box("tease_ward.json")
    if ward is None:
        probs.append("tease: no ward advancement in the pack")
    else:
        (wx0, wy0, wz0), (wx1, wy1, wz1) = ward
        wm = t["ward_margin"]
        need = grille | face | seen
        short = [c for c in need if not (wx0 + wm <= c[0] <= wx1 - wm and wy0 + wm <= c[1] <= wy1 - wm and wz0 + wm <= c[2] <= wz1 - wm)]
        if short:
            probs.append("tease: %d grille, face or pocket cells are within %d of the ward's edge, e.g. %s" % (len(short), wm, sorted(short)[:3]))
        notes["tease ward"] = [list(ward[0]), list(ward[1])]
        wf = FN / "tease" / "ward.mcfunction"
        body = wf.read_text(encoding="utf-8") if wf.is_file() else ""
        if "advancements={%s=false}" % spec["flag"]["advancement"] not in body or "mining_fatigue" not in body:
            probs.append("tease: the ward's function does not give the effect only to a player lacking %s" % spec["flag"]["advancement"])
    cb = spec["mine"]["collapse"]["box"]
    col = {(x, y, z) for x in range(cb[0], cb[3] + 1) for y in range(cb[1], cb[4] + 1) for z in range(cb[2], cb[5] + 1)}
    if col & ungated:
        probs.append("collapse: the collapse overlaps the envelope at %s" % sorted(col & ungated)[:3])
    return probs, notes


def output_problems(spec, grid, gated, ungated, top, cols, notes):
    """The generated pack, replayed, against the plan."""
    probs = []
    final, outside, files = replay(grid)
    notes["cells written"] = len(final)
    # the grille itself stands in the output: its cells are envelope, so air there is not stray and nothing else would
    # notice a pack that shut drift C with nothing (the test author's finding)
    t = spec["mine"].get("tease")
    if t:
        gr = t["grille"]
        bars = [(x, y, gr["z"]) for x in range(gr["x"][0], gr["x"][1] + 1) for y in range(gr["y"][0], gr["y"][1] + 1)]
        missing = [c for c in bars if (final.get(c) or "").split("[")[0] != "minecraft:iron_bars"]
        if missing:
            probs.append("tease: %d grille cells are not iron bars in the output, e.g. %s" % (len(missing), missing[:3]))
    if outside:
        probs.append("inside: %d writes outside the data's grid, e.g. %s" % (len(outside), outside[:3]))
    stray_cols = {(x, z) for x, _y, z in final} - cols
    if stray_cols:
        probs.append("inside: %d written columns the plan does not cover, e.g. %s" % (len(stray_cols), sorted(stray_cols)[:3]))
    env = gated | ungated
    stray = [c for c, b in final.items() if b in AIRS and c not in env and c[1] <= top(c[0], c[2])]
    if stray:
        probs.append("no stray: %d air cells under the ground that are not envelope, e.g. %s" % (len(stray), sorted(stray)[:3]))
    ring = set()
    for x, y, z in env:
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            q = (x + d[0], y + d[1], z + d[2])
            if q not in env and q[1] <= top(q[0], q[2]):
                ring.add(q)
    unsealed = [c for c in ring if final.get(c) is None or final[c] in AIRS or final[c].split("[")[0] in FLUIDS]
    if unsealed:
        probs.append("sealed: %d cells next to the envelope under the ground end unwritten, air or fluid, e.g. %s"
                     % (len(unsealed), sorted(unsealed)[:3]))
    notes["cells sealing the envelope"] = len(ring)
    # ---- the one crystal, and nothing left of the gate
    t = spec["mine"]["tease"]
    fb = t["face"]["box"]
    crystals = [c for c, b in final.items() if b.split("[")[0] == "mega_showdown:mega_stone_crystal"]
    notes["mega stone crystals written"] = len(crystals)
    if len(crystals) != t["face"]["crystals"]:
        probs.append("crystal: %d mega_stone_crystal written, the tease has %d" % (len(crystals), t["face"]["crystals"]))
    if any(not (fb[0] <= x <= fb[3] and fb[1] <= y <= fb[4] and fb[2] <= z <= fb[5]) for x, y, z in crystals):
        probs.append("crystal: a crystal written outside the tease's face box")
    for gone in ("gate_knock.json", "gate_exit.json", "gate_ward.json", "zone.json"):
        if (PACK / "data" / "cobblers" / "advancement" / "rift_mines" / gone).is_file():
            probs.append("crystal: the retired gate's advancement %s is still in the pack" % gone)
    rest = FN / "tease" / "restore.mcfunction"
    body = rest.read_text(encoding="utf-8") if rest.is_file() else ""
    if "replace #cobblers:" not in body or body.count("mega_stone_crystal") != t["face"]["crystals"]:
        probs.append("crystal: the tease's restore is not a filtered fill with %d guarded crystal setblocks" % t["face"]["crystals"])
    # ---- blocks
    sb = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]
    used = sorted({b.split("[")[0] for b in final.values()})
    bad = [b for b in used if b in sb or b in FLUIDS or (b.startswith("mega_showdown:mega_meteorid_") and b.endswith("_ore"))]
    if bad:
        probs.append("blocks: written blocks that decide spawns, are fluids or drop evolution stones: %s" % bad)
    notes["distinct blocks written"] = len(used)
    # ---- limits
    for f in sorted(FN.rglob("*.mcfunction")):
        for n, c, w in FL.check_file(f):
            probs.append("limits: %s line %d: %s" % (f.name, n, w))
    return probs


def refill_problems(spec, grid, ungated, ground, notes):
    """The staging refill writes rock into exactly the retired gated envelope, and nowhere the live build uses."""
    probs = []
    ret = spec.get("retired_gated_section") or {}
    env = set()
    for f in ret.get("features") or []:
        env |= stamp(f, ground)
    notes["retired gated envelope cells"] = len(env)
    if not env:
        probs.append("refill: the data has no retired gated envelope: nothing to refill")
        return probs
    final, outside, _files = replay(grid, REFILL_FN)
    if outside:
        probs.append("refill: %d writes outside the grid" % len(outside))
    if set(final) != env:
        probs.append("refill: writes %d cells, the retired envelope has %d (%d missing, %d extra)"
                     % (len(final), len(env), len(env - set(final)), len(set(final) - env)))
    soft = [c for c, b in final.items() if b in AIRS or b.split("[")[0] in FLUIDS]
    if soft:
        probs.append("refill: %d cells written air or fluid" % len(soft))
    cb = spec["mine"]["collapse"]["box"]
    live = [c for c in final if c in ungated or (cb[0] <= c[0] <= cb[3] and cb[1] <= c[1] <= cb[4] and cb[2] <= c[2] <= cb[5])]
    if live:
        probs.append("refill: %d cells in the live envelope or the collapse, e.g. %s" % (len(live), sorted(live)[:3]))
    for f in sorted(REFILL_FN.rglob("*.mcfunction")):
        for n, c, w in FL.check_file(f):
            probs.append("limits: %s line %d: %s" % (f.name, n, w))
    notes["refill cells written"] = len(final)
    return probs


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root")
    a = p.parse_args(argv)
    probs, notes = audit(a.source_root)
    for k, v in notes.items():
        print("  %-48s %s" % (k, v))
    for pr in probs:
        print("PROBLEM:", pr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"problems": probs, "notes": notes}, indent=1) + "\n", encoding="utf-8")
    print("%s: %d problem(s)" % ("CLEAN" if not probs else "FAILED", len(probs)))
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
