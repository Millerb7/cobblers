#!/usr/bin/env python
"""Offline plan audit of the Rift mines: nothing overlaps another build or path, and the gated galleries are sealed
except through their gate. Independent of tools/rift_mines.py's model: it rasterises data/rift_mines.json itself, by
the `geometry` the data file states, and takes every expectation about other builds from THEIR data (the camp's plan
and placements, the Rift sculpt's entrance ramp, data/towns.json), never from the generated output. The generated pack
is then replayed and checked against those expectations.

The plan (data only):
  overlap     every column this build may write (its envelope and its shell, two round it; its houses, piles, street,
              lamp posts, derricks, headframe, tracks) keeps `keep_clear.margin` from: the camp's streets, plaza,
              anchors and lots (derived/towns/rift_dig_camp_plan.json), every donor and earthwork the placements
              give the camp, the excavation haul road's path (the ramp tools/rift_skin.py paves, from the sculpt's
              ring), the data's own keep-clear boxes, and every other settlement's footprint. Forge Row may meet the
              camp track end to end; it may not overlap it
  separation  the gated envelope never comes within 2 of the ungated envelope (the cuts, the adit, the hall, the
              decline, the drifts): the plug is the only thing between them
  gate        the knock box is walkable ungated floor, the arrival and exit are gated, the turn-back point walkable
              ungated floor; open the plug and the knock box reaches the arrival; the plug is neither envelope
  cover       at least cover_min of rock over every gated column's shell, under the ground or a cut's floor
  connected   every gated envelope cell is reachable from the arrival inside the gated envelope
The output (build/datapacks/cobblers_rift_mines, replayed in index order):
  inside      every block write falls in a column the plan may write, inside the grid
  no stray    no cell near the gated section ends as air unless it is gated envelope
  sealed      every cell next to the gated envelope, and every plug cell, ends as a block this build wrote, not air,
              not a fluid: the seal is the build's own rock, not whatever the export left there
  zone        the zone check's boxes (read from the pack's advancement) hold every gated envelope cell, and no ungated
              envelope cell, no knock or turn-back cell and nothing at or over the ground
  blocks      no written block is named by a spawn condition (data/spawn_blocks.json), no water, no lava
  limits      tools/function_limits.py finds nothing the server would refuse

Fails closed: no pack, an empty index, no camp plan or no gated cell is a failure, not a pass.

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


def floor_of_cut(cut, x, z):
    x0, z0, x1, z1 = cut["rect"]
    b = cut.get("bench") or {}
    if cut["kind"] == "pit":
        dists = [x - x0, x1 - x, z - z0, z1 - z]
    else:
        side = {"west": x - x0, "east": x1 - x, "north": z - z0, "south": z1 - z}
        dists = [side[s] for s in cut.get("benches") or []]
    lvl = max(0, b.get("levels", 1) - 1 - min(dists) // b.get("run", 1)) if dists else 0
    y = cut["floor"] + b.get("rise", 0) * lvl
    rp = cut.get("ramp")
    if rp and rp["x"][0] <= x <= rp["x"][1] and rp["z"][0] <= z <= rp["z"][1]:
        y = half_up(cut["floor"] + (rp["z"][1] - z) / (rp["z"][1] - rp["z"][0]) * (rp["top"] - cut["floor"]))
    return y


def plan(spec, ground):
    """(gated set, ungated set, effective ground {(x, z): y}, cut columns) from the data alone."""
    gated, ungated, eff, cutcols = set(), set(), {}, set()
    for cut in spec["town"]["cuts"]:
        x0, z0, x1, z1 = cut["rect"]
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                yf, g = floor_of_cut(cut, x, z), ground(x, z)
                if g > yf:
                    eff[(x, z)] = min(eff.get((x, z), g), yf)
                    cutcols.add((x, z))
                    ungated.update((x, y, z) for y in range(yf + 1, g + 7))
    for f in spec["mine"]["features"]:
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
        (gated if f.get("gated") else ungated).update(cells)
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
    st = t["street"]
    street = {(x, z) for x in range(st["from"][0], st["to"][0] + 1)
              for z in range(st["from"][1] - st["width"] // 2, st["from"][1] + st["width"] // 2 + 1)}
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
    pl = spec["mine"]["gate"]["plug"]
    cols |= {(x, z) for x in range(pl[0], pl[3] + 1) for z in range(pl[2], pl[5] + 1)}
    return cols, street


# ------------------------------------------------------------------ replaying the output

CMD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")


def replay(grid):
    """(final {(x, y, z): block}, writes outside the grid, function files) from the pack, in its index order."""
    idx = FN / "index.txt"
    if not idx.is_file():
        raise SystemExit("no %s: run `python tools/rift_mines.py build` first" % idx.relative_to(ROOT))
    names = [n for n in idx.read_text(encoding="utf-8").split("\n") if n.strip()]
    if not names:
        raise SystemExit("%s lists no function: nothing was generated" % idx.relative_to(ROOT))
    final, outside, files = {}, [], []
    for n in names:
        f = FN / (n + ".mcfunction")
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


def zone_boxes():
    adv = PACK / "data" / "cobblers" / "advancement" / "rift_mines" / "zone.json"
    if not adv.is_file():
        raise SystemExit("no zone advancement at %s" % adv.relative_to(ROOT))
    doc = json.loads(adv.read_text(encoding="utf-8"))
    conds = doc["criteria"]["here"]["conditions"]["player"]
    terms = conds[0]["terms"] if conds and conds[0].get("condition") == "minecraft:any_of" else conds
    out = []
    for t in terms:
        p = t["predicate"]["location"]["position"]
        # a position range reads the player's feet as a double; max is the far face of the last block
        out.append(((p["x"]["min"], p["y"]["min"], p["z"]["min"]), (p["x"]["max"] - 1, p["y"]["max"] - 1, p["z"]["max"] - 1)))
    return out


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
    if not gated:
        probs.append("the data has no gated cell: nothing to audit")
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
    p2, n2, gate_cells = plan_problems(spec, gated, ungated, top)
    probs += p2
    notes.update(n2)
    knock, plug, (tx, ty, tz) = gate_cells
    probs += output_problems(spec, grid, gated, ungated, top, cols, knock, plug, (tx, ty, tz), notes)
    return probs, notes


def plan_problems(spec, gated, ungated, top):
    """Separation, the gate, connection and cover, on the data's own envelopes. Pure: no files, no heightmap."""
    probs, notes = [], {}
    # ---- separation and the gate
    near_gated = set()
    for x, y, z in gated:
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                for dz in range(-2, 3):
                    near_gated.add((x + dx, y + dy, z + dz))
    close = near_gated & ungated
    if close:
        probs.append("separation: %d ungated envelope cells within 2 of the gated envelope, e.g. %s"
                     % (len(close), sorted(close)[:3]))
    gt = spec["mine"]["gate"]
    px0, py0, pz0, px1, py1, pz1 = gt["plug"]
    plug = {(x, y, z) for x in range(px0, px1 + 1) for y in range(py0, py1 + 1) for z in range(pz0, pz1 + 1)}
    if plug & (gated | ungated):
        probs.append("gate: the plug overlaps the envelope at %s" % sorted(plug & (gated | ungated))[:3])
    k = gt["knock"]
    knock = {(x, y, z) for x in range(k[0], k[3] + 1) for y in range(k[1], k[4] + 1) for z in range(k[2], k[5] + 1)}
    for x, y, z in knock:
        if y == k[1] and not standable(ungated, x, y, z):
            probs.append("gate: the knock box's floor cell %s is not walkable ungated floor" % ((x, y, z),))
    e = gt["exit"]
    exitbox = {(x, y, z) for x in range(e[0], e[3] + 1) for y in range(e[1], e[4] + 1) for z in range(e[2], e[5] + 1)}
    if not exitbox <= gated:
        probs.append("gate: %d exit box cells are not gated envelope" % len(exitbox - gated))
    ax, ay, az = int(math.floor(gt["arrive"][0])), gt["arrive"][1], int(math.floor(gt["arrive"][2]))
    tx, ty, tz = int(math.floor(gt["turn_back"][0])), gt["turn_back"][1], int(math.floor(gt["turn_back"][2]))
    if not standable(gated, ax, ay, az):
        probs.append("gate: the arrival %s is not walkable gated floor" % ((ax, ay, az),))
    if not standable(ungated, tx, ty, tz):
        probs.append("gate: the turn-back point %s is not walkable ungated floor" % ((tx, ty, tz),))
    if (ax, ay, az) in exitbox:
        probs.append("gate: the arrival is inside the exit box (a player would bounce straight back out)")
    # with the plug open, the knock box reaches the arrival; that is the gate. Separation proves it is the only way.
    open_ = gated | ungated | plug
    seen, stack = {min(knock)}, [min(knock)]
    while stack:
        x, y, z = stack.pop()
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            q = (x + d[0], y + d[1], z + d[2])
            if q in open_ and q not in seen:
                seen.add(q)
                stack.append(q)
    if (ax, ay, az) not in seen:
        probs.append("gate: even with the plug open, the knock box does not reach the arrival")

    # ---- connected
    seen, stack = {(ax, ay, az)} & gated, [(ax, ay, az)]
    while stack and seen:
        x, y, z = stack.pop()
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            q = (x + d[0], y + d[1], z + d[2])
            if q in gated and q not in seen:
                seen.add(q)
                stack.append(q)
    if len(seen) != len(gated):
        probs.append("connected: %d gated envelope cells not reachable from the arrival" % (len(gated) - len(seen)))

    # ---- cover
    tops = {}
    for x, y, z in gated:
        tops[(x, z)] = max(tops.get((x, z), -999), y)
    thin = [(c, top(*c) - y) for c, y in tops.items() if top(*c) - y < spec["cover_min"] + SHELL]
    if thin:
        probs.append("cover: %d gated columns with under %d of rock over the shell, e.g. %s"
                     % (len(thin), spec["cover_min"], thin[:3]))
    notes["least rock over a gated column (shell included)"] = min(top(*c) - y for c, y in tops.items()) if tops else None
    return probs, notes, (knock, plug, (tx, ty, tz))


def output_problems(spec, grid, gated, ungated, top, cols, knock, plug, turn, notes):
    """The generated pack, replayed, against the plan."""
    probs = []
    tx, ty, tz = turn
    # ---- the output
    final, outside, files = replay(grid)
    notes["cells written"] = len(final)
    if outside:
        probs.append("inside: %d writes outside the data's grid, e.g. %s" % (len(outside), outside[:3]))
    stray_cols = {(x, z) for x, _y, z in final} - cols
    if stray_cols:
        probs.append("inside: %d written columns the plan does not cover, e.g. %s" % (len(stray_cols), sorted(stray_cols)[:3]))
    xs = [c[0] for c in gated]
    zs = [c[2] for c in gated]
    ys = [c[1] for c in gated]
    box = (min(xs) - 3, max(xs) + 3, min(ys) - 3, max(ys) + 3, min(zs) - 3, max(zs) + 3) if gated else None
    stray = [c for c, b in final.items() if b in AIRS and box and box[0] <= c[0] <= box[1] and box[2] <= c[1] <= box[3]
             and box[4] <= c[2] <= box[5] and c not in gated and c not in ungated and c[1] <= top(c[0], c[2])]
    if stray:
        probs.append("no stray: %d air cells under the ground near the gated section that are not envelope, e.g. %s"
                     % (len(stray), sorted(stray)[:3]))
    ring = set()
    for x, y, z in gated:
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            q = (x + d[0], y + d[1], z + d[2])
            if q not in gated:
                ring.add(q)
    unsealed = [c for c in ring | plug if final.get(c) is None or final[c] in AIRS or final[c].split("[")[0] in FLUIDS]
    if unsealed:
        probs.append("sealed: %d cells round the gated envelope or in the plug end unwritten, air or fluid, e.g. %s"
                     % (len(unsealed), sorted(unsealed)[:3]))
    notes["cells sealing the gated section"] = len(ring)
    open_gated = sum(1 for c in gated if final.get(c) in AIRS)
    notes["gated envelope cells left open"] = open_gated
    if gated and open_gated < 0.8 * len(gated):
        probs.append("sealed: only %d of %d gated envelope cells end open" % (open_gated, len(gated)))

    # ---- zone
    boxes = zone_boxes()
    notes["zone boxes"] = len(boxes)

    def in_boxes(c):
        return any(b[0][0] <= c[0] <= b[1][0] and b[0][1] <= c[1] <= b[1][1] and b[0][2] <= c[2] <= b[1][2] for b in boxes)
    missed = [c for c in gated if not in_boxes(c)]
    if missed:
        probs.append("zone: %d gated envelope cells outside every zone box, e.g. %s" % (len(missed), sorted(missed)[:3]))
    caught = [c for c in ungated | knock | {(tx, ty, tz), (tx, ty + 1, tz)} if in_boxes(c)]
    if caught:
        probs.append("zone: %d ungated, knock or turn-back cells inside a zone box, e.g. %s" % (len(caught), sorted(caught)[:3]))
    for (x0, y0, z0), (x1, y1, z1) in boxes:
        lowest = min(top(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1))
        if y1 >= lowest:
            probs.append("zone: a box reaching y%d stands at or over the ground (y%d) at x%d-%d z%d-%d"
                         % (y1, lowest, x0, x1, z0, z1))

    # ---- blocks
    sb = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]
    used = sorted({b.split("[")[0] for b in final.values()})
    bad = [b for b in used if b in sb or b in FLUIDS]
    if bad:
        probs.append("blocks: written blocks that decide spawns or are fluids: %s" % bad)
    notes["distinct blocks written"] = len(used)

    # ---- limits
    for f in sorted(FN.rglob("*.mcfunction")):
        for n, c, w in FL.check_file(f):
            probs.append("limits: %s line %d: %s" % (f.name, n, w))
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
