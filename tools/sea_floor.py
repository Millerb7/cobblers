#!/usr/bin/env python
"""The open sea's floor: kelp forests and seagrass meadows on the shelf of every marine region, from
data/sea_floor.json (docs/world-building/WATER_LIFE_GAP.md; docs/world-building/OCEAN.md section 4 'Kelp, seagrass,
coral'; data/regions.json marine_regions[].flora).

WHY. `cobblers_sea_life` dresses five shaped coasts out to 40 blocks from land and the Relic reef: about 74,000 of the
map's 21.9M sea columns (0.34%). A WorldPainter export grows nothing under water, so the rest of the sea, the shelf a
player crosses on every ride, is bare sand and gravel. This pack is the tranche OCEAN.md's flora table calls for and
nobody built.

Everything is decided from the data file, the canonical heightmap (tools/ground.py, rounded; it IS the applied water
export), the marine regions' own polygons, flora lists and shelf widths in data/regions.json, and tools/sea_life.py's
model, which supplies the exclusions (its Exclusions: towns, routes, bridges, the Rift, Victory Road, lakes, docks,
ferry lanes, gate lines, portals, legendaries, adopted sites, placements, Pacifidlog, the First Cast hole, the Relic
swim lines, the Seaward Drift and Driftmouth Isle, the Deep) and every cell that pack writes, so the two share no
column. Never a world. Nothing here changes a height.

  kelp       forests in patches on the seabed y28-58, tops at most sea - 3, age 25 (never grows past it); per region's
             rules: none in the warm south within 220 of land, none under the frozen north
  seagrass   meadows on the seabed y40-60, a few tall; never inside a gate line's clearance

Every write is `fill ... replace minecraft:water`: it can only turn sea water into a plant.

WHAT THIS DOES NOT COVER (CLAUDE.md "Our list is not the world"): anything in the sea no data file or helper lists.
The water filter is what keeps those safe; a kelp column that meets one stops there. Coral is not written (the policy
whitelists live coral for cobblers_sea_life's Relic reef only); rivers are not dressed (no tool knows a river's water
surface per column; WATER_LIFE_GAP.md).

  python tools/sea_floor.py report [--source-root DIR]   the numbers, per region; nothing written
  python tools/sea_floor.py build  [--source-root DIR]   -> build/datapacks/cobblers_sea_floor, derived/sea_floor/plan.json

Run order on a world: every function in build/datapacks/cobblers_sea_floor/data/cobblers/function/sea_floor/index.txt,
by reapply.py R9SF, after R9SL.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import rift_mines as RM        # noqa: E402  (its function size, PART)
import sea_life as SL          # noqa: E402  (its model: the exclusions and its own writes)
import water_shape as WS       # noqa: E402  (noise, hashing, chamfer distance)

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "sea_floor.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_sea_floor"
PLAN = ROOT / "derived" / "sea_floor" / "plan.json"
NS = "cobblers"
FOLDER = "sea_floor"
PASSES = ("flora",)
TILE = 64          # the planning tile; a seagrass run never crosses one
FN_TILE = 128      # the function tile: a multiple of TILE, so no run crosses a function either
WATER = "minecraft:water"
FLORA_IDS = ("minecraft:kelp", "minecraft:kelp_plant", "minecraft:seagrass", "minecraft:tall_seagrass")


class FloorError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def regions_doc():
    return json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ inputs

def land_distance(H, sea, spec):
    """Coarse distance from land, in blocks, on a grid `coarse_blocks` wide: (N/c, N/c) float32."""
    ld = spec["land_distance"]
    c = int(ld["coarse_blocks"])
    N = H.shape[0]
    n = N // c
    land = (H >= sea).reshape(n, c, n, c).any(axis=(1, 3))
    d = WS.distance(land, None, max_iter=int(math.ceil(ld["max_blocks"] / c)) + 2) * c
    return d


def region_labels(N, spec, coarse):
    """(labels full-resolution int8, coarse labels, names). Label i+1 is names[i]; 0 is none. Polygons are applied in
    data/sea_life.json finds.region_order (that pack's order, so the two agree on overlaps); unassigned coarse cells
    take the nearest label by spreading."""
    doc = regions_doc()
    polys = {r["id"]: r.get("polygons") or [] for r in doc["marine_regions"]}
    names = [r for r in SL.load()["finds"]["region_order"] if r in spec["regions"]]
    missing = [r for r in spec["regions"] if r not in names and r not in ("from", "unassigned_why")]
    if missing:
        raise FloorError("regions in data/sea_floor.json not in data/sea_life.json finds.region_order: %s" % missing)
    lab = np.zeros((N, N), np.int8)
    for i, rid in enumerate(names):
        if not polys.get(rid):
            raise FloorError("marine region %s has no polygons in data/regions.json" % rid)
        img = Image.new("L", (N, N), 0)
        d = ImageDraw.Draw(img)
        for ring in polys[rid]:
            d.polygon([(float(p[0]), float(p[1])) for p in ring], fill=1)
        m = np.array(img).astype(bool)
        lab[m & (lab == 0)] = i + 1
        del img, m
    n = N // coarse
    # the coarse label: the label at each coarse cell's first column, then spread into the cells that have none
    cl = lab[::coarse, ::coarse].copy()
    for _ in range(4 * n):
        z = cl == 0
        if not z.any():
            break
        changed = False
        for dz, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sh = np.zeros_like(cl)
            a0, a1 = max(0, dz), n + min(0, dz)
            b0, b1 = max(0, dx), n + min(0, dx)
            sh[a0:a1, b0:b1] = cl[a0 - dz:a1 - dz, b0 - dx:b1 - dx]
            fill = (cl == 0) & (sh != 0)
            if fill.any():
                cl[fill] = sh[fill]
                changed = True
        if not changed:
            break
    return lab, cl, names


def dilate(mask, r):
    """Square (Chebyshev) dilation by r, separable, with no float grid."""
    out = mask.copy()
    for axis in (0, 1):
        cur = out.copy()
        for k in range(1, r + 1):
            if axis == 0:
                cur[k:, :] |= out[:-k, :]
                cur[:-k, :] |= out[k:, :]
            else:
                cur[:, k:] |= out[:, :-k]
                cur[:, :-k] |= out[:, k:]
        out = cur
    return out


# ------------------------------------------------------------------ the model

class Model:
    def __init__(self, spec, sl):
        self.spec = spec
        self.sl = sl
        self.H = sl.H
        self.N = sl.N
        self.sea = sl.sea
        self.problems = []
        self.kelp = []          # (x, z, ground, top)
        self.grass = []         # (x, z, ground, tall)
        self.lines = {p: [] for p in PASSES}
        self.stats = {}


def exclusion(m):
    """The columns this pack may not write, and why, as (mask, {reason: columns}) over the whole map."""
    sl, spec, N = m.sl, m.spec, m.N
    own = spec["ownership"]
    X = sl.ex.X | sl.reserved
    why = {"sea_life's exclusions (towns, routes, the Rift, lakes, docks, ferry lanes, portals, ...)": int(X.sum())}
    cols = np.zeros((N, N), bool)
    for (x, _y, z) in sl.writes:
        cols[z, x] = True
    near = dilate(cols, int(own["sea_life_margin_blocks"]))
    why["within %d of a cell cobblers_sea_life writes" % own["sea_life_margin_blocks"]] = int((near & ~X).sum())
    X = X | near
    # the coasts cobblers_sea_life owns, out to its kelp reach plus the coarse grid's error
    slspec = sl.spec
    reach = int(slspec["shore"]["kelp"]["from_land_blocks"]) + 2 * int(spec["land_distance"]["coarse_blocks"])
    boxes = {f["id"]: f["box"] for f in sl.wspec["coasts"]["flats"]}
    boxes.update({s["id"]: s["box"] for s in sl.wspec["coasts"]["skerries"]})
    c = int(spec["land_distance"]["coarse_blocks"])
    coast = np.zeros((N, N), bool)
    for co in slspec["shore"]["coasts"]:
        x0, z0, x1, z1 = boxes[co["id"]]
        x0, z0, x1, z1 = max(0, x0), max(0, z0), min(N, x1), min(N, z1)
        dl = m.DL[z0 // c:(z1 + c - 1) // c, x0 // c:(x1 + c - 1) // c].repeat(c, 0).repeat(c, 1)
        oz, ox = z0 - (z0 // c) * c, x0 - (x0 // c) * c
        dl = dl[oz:oz + (z1 - z0), ox:ox + (x1 - x0)]
        coast[z0:z1, x0:x1] |= dl <= reach
    why["a shaped coast cobblers_sea_life dresses, within %d of land" % reach] = int((coast & ~X).sum())
    X = X | coast
    # the Relic reef
    rr = sl.wspec["coasts"]["relic_reef"]
    R = float(rr["outer_radius"][1] + rr["drop_width_blocks"] + own["reef_margin_blocks"])
    cx, cz = rr["centre"]
    x0, z0 = max(0, int(cx - R) - 1), max(0, int(cz - R) - 1)
    x1, z1 = min(N, int(cx + R) + 2), min(N, int(cz + R) + 2)
    ZZ, XX = np.mgrid[z0:z1, x0:x1]
    disc = np.zeros((N, N), bool)
    disc[z0:z1, x0:x1] = np.hypot(XX - cx, ZZ - cz) <= R
    why["the Relic reef and %d round it" % own["reef_margin_blocks"]] = int((disc & ~X).sum())
    X = X | disc
    m.sl_cols = cols
    return X, why


def plan(m):
    spec, sl, N, sea = m.spec, m.sl, m.N, m.sea
    seed = int(spec["seed"])
    c = int(spec["land_distance"]["coarse_blocks"])
    m.DL = land_distance(m.H, sea, spec)
    lab, cl, names = region_labels(N, spec, c)
    m.names = names
    X, why = exclusion(m)
    m.excluded_why = why
    rdoc = {r["id"]: r for r in regions_doc()["marine_regions"]}
    kp, sg = spec["kelp"], spec["seagrass"]
    k_lo, k_hi = kp["ground_y"]
    g_lo, g_hi = sg["ground_y"]
    tmax_all = sea - int(kp["max_top_below_surface"])
    rules = {}
    for i, rid in enumerate(names):
        r = spec["regions"][rid]
        rules[i + 1] = {
            "id": rid,
            "reach": float(rdoc[rid]["seabed_plan"]["shelf_width_blocks"]),
            "kelp": bool(r.get("kelp")), "kelp_beyond": float(r.get("kelp_beyond_land_blocks") or 0),
            "seagrass": bool(r.get("seagrass")), "frozen": r.get("frozen"),
        }
    st = {rid: {"sea_columns": 0, "excluded": 0, "outside_reach": 0, "frozen": 0, "kelp_columns": 0,
                "seagrass_columns": 0, "tall_seagrass": 0, "sea_life_flora_columns": 0, "assigned_by_nearest": 0}
          for rid in names}
    st["none"] = {"sea_columns": 0}
    # cobblers_sea_life's own flora columns, by region, for the gap report
    slflora = np.zeros((N, N), bool)
    for (x, _y, z), (b, _p, _o) in sl.writes.items():
        if SL.bid(b) in FLORA_IDS or "coral" in b or "sea_pickle" in b:
            slflora[z, x] = True
    gate = sl.ex.gate
    lake = sl.ex.lake
    for z0 in range(0, N, TILE):
        for x0 in range(0, N, TILE):
            z1, x1 = z0 + TILE, x0 + TILE
            G = m.H[z0:z1, x0:x1].astype(np.int32)
            wet = (G < sea) & ~lake[z0:z1, x0:x1]
            if not wet.any():
                continue
            L = lab[z0:z1, x0:x1]
            Lc = cl[z0 // c:z1 // c, x0 // c:x1 // c].repeat(c, 0).repeat(c, 1)
            near = L == 0
            L = np.where(near, Lc, L)
            dl = m.DL[z0 // c:z1 // c, x0 // c:x1 // c].repeat(c, 0).repeat(c, 1)
            Xt = X[z0:z1, x0:x1]
            ZZ, XX = np.mgrid[z0:z1, x0:x1]
            for li in np.unique(L[wet]):
                li = int(li)
                if li == 0:
                    st["none"]["sea_columns"] += int((wet & (L == 0)).sum())
                    continue
                ru = rules[li]
                s = st[ru["id"]]
                inr = wet & (L == li)
                s["sea_columns"] += int(inr.sum())
                s["assigned_by_nearest"] += int((inr & near).sum())
                s["sea_life_flora_columns"] += int((inr & slflora[z0:z1, x0:x1]).sum())
                ok = inr & ~Xt
                s["excluded"] += int((inr & Xt).sum())
                within = ok & (dl <= ru["reach"])
                s["outside_reach"] += int((ok & ~within).sum())
                if ru["frozen"]:
                    fz = (ZZ < ru["frozen"]["north_of_z"]) & (dl >= ru["frozen"]["from_land_blocks"])
                    s["frozen"] += int((within & fz).sum())
                    within &= ~fz
                kelp = np.zeros_like(within)
                if ru["kelp"]:
                    nz = WS.value_noise(XX, ZZ, kp["patch_scale_blocks"], seed + 1)
                    dens = WS._hash01(XX, ZZ, seed + 2)
                    kelp = within & (G >= k_lo) & (G <= k_hi) & (G < tmax_all) & (dl > ru["kelp_beyond"]) \
                        & (nz > kp["patch_over"]) & (dens < kp["density"])
                    hh = WS._hash01(XX, ZZ, seed + 3)
                    a, b = kp["height_share"]
                    for k_, i in np.argwhere(kelp):
                        g = int(G[k_, i])
                        room = tmax_all - g
                        top = g + max(1, int(round((a + (b - a) * hh[k_, i]) * room)))
                        m.kelp.append((int(i + x0), int(k_ + z0), g, min(top, tmax_all)))
                    s["kelp_columns"] += int(kelp.sum())
                if ru["seagrass"]:
                    nz = WS.value_noise(XX, ZZ, sg["patch_scale_blocks"], seed + 4)
                    hole = WS._hash01(XX, ZZ, seed + 5)
                    tall = WS._hash01(XX, ZZ, seed + 6)
                    gm = within & ~kelp & ~gate[z0:z1, x0:x1] & (G >= g_lo) & (G <= g_hi) \
                        & (nz > sg["patch_over"]) & (hole >= sg["hole_share"])
                    for k_, i in np.argwhere(gm):
                        g = int(G[k_, i])
                        t = bool(sea - g >= 3 and tall[k_, i] < sg["tall_share"])
                        m.grass.append((int(i + x0), int(k_ + z0), g, t))
                        s["tall_seagrass"] += int(t)
                    s["seagrass_columns"] += int(gm.sum())
    m.stats = st
    m.X = X


def lines(m):
    """Kelp: a stem fill and a head, per column. Seagrass: runs along x of the same ground y inside one tile, one fill
    each; tall seagrass as its two halves. Every write is `replace minecraft:water`."""
    out = []
    age = int(m.spec["kelp"]["age"])
    flt = m.spec["writes"]["filter"]
    if flt != WATER:
        raise FloorError("writes.filter must be %s" % WATER)
    for (x, z, g, top) in sorted(m.kelp, key=lambda t: (t[1] // TILE, t[0] // TILE, t[1], t[0])):
        if top > g + 1:
            out.append("fill %d %d %d %d %d %d minecraft:kelp_plant replace %s" % (x, g + 1, z, x, top - 1, z, flt))
        out.append("fill %d %d %d %d %d %d minecraft:kelp[age=%d] replace %s" % (x, top, z, x, top, z, age, flt))
    rows = {}
    for (x, z, g, t) in m.grass:
        rows.setdefault((z, x // TILE), []).append((x, g, t))
    for (z, _tx) in sorted(rows, key=lambda k: (k[0] // TILE, k[1], k[0])):
        cells = sorted(rows[(z, _tx)])
        n = 0
        while n < len(cells):
            x, g, t = cells[n]
            if t:
                out.append("fill %d %d %d %d %d %d minecraft:tall_seagrass[half=lower] replace %s" % (x, g + 1, z, x, g + 1, z, flt))
                out.append("fill %d %d %d %d %d %d minecraft:tall_seagrass[half=upper] replace %s" % (x, g + 2, z, x, g + 2, z, flt))
                n += 1
                continue
            k = n
            while k + 1 < len(cells) and cells[k + 1][0] == cells[k][0] + 1 and cells[k + 1][1] == g and not cells[k + 1][2]:
                k += 1
            out.append("fill %d %d %d %d %d %d minecraft:seagrass replace %s" % (x, g + 1, z, cells[k][0], g + 1, z, flt))
            n = k + 1
    m.lines = {"flora": out}
    return m.lines


def checks(m):
    """The builder's own checks. The independent audit is another hand's."""
    p = m.problems
    sea = m.sea
    tmax = sea - int(m.spec["kelp"]["max_top_below_surface"])
    for (x, z, g, top) in m.kelp:
        if top > tmax:
            p.append("kelp at (%d, %d) tops at y%d, above sea - %d" % (x, z, top, sea - tmax))
        if top <= g:
            p.append("kelp at (%d, %d) has no room" % (x, z))
        if m.X[z, x] or m.sl_cols[z, x]:
            p.append("kelp at (%d, %d) is in an exclusion" % (x, z))
    for (x, z, g, t) in m.grass:
        if g + (2 if t else 1) > sea - 1:
            p.append("seagrass at (%d, %d) reaches above the water" % (x, z))
        if m.X[z, x] or m.sl_cols[z, x]:
            p.append("seagrass at (%d, %d) is in an exclusion" % (x, z))
        if m.sl.ex.gate[z, x]:
            p.append("seagrass at (%d, %d) inside a gate line's clearance" % (x, z))
    for rid in m.names:
        s = m.stats[rid]
        if not (s["kelp_columns"] or s["seagrass_columns"]):
            p.append("region %s got nothing" % rid)
    n = sum(len(v) for v in m.lines.values())
    if n > int(m.spec["budget"]["max_commands"]):
        p.append("%d commands, over the budget of %d" % (n, m.spec["budget"]["max_commands"]))


def model(source_root=None, spec=None, sl=None):
    spec = spec or load()
    sl = sl or SL.model(source_root)
    m = Model(spec, sl)
    plan(m)
    lines(m)
    checks(m)
    return m


def summary(m):
    tot = {k: sum(m.stats[r][k] for r in m.names) for k in ("sea_columns", "excluded", "outside_reach", "frozen",
                                                            "kelp_columns", "seagrass_columns", "tall_seagrass",
                                                            "sea_life_flora_columns")}
    tot["sea_columns"] += m.stats["none"]["sea_columns"]
    return {
        "sea_level": m.sea,
        "regions": m.stats,
        "totals": tot,
        "excluded_why": m.excluded_why,
        "commands": {k: len(v) for k, v in m.lines.items()},
        "problems": m.problems[:40],
        "problem_count": len(m.problems),
    }


def write(m, out=OUT):
    """tools/rift_mines.py write_blocks' layout (pack.mcmeta, one folder, index.txt, every function holding its own
    chunks and checked by tools/function_limits.py) with a 128-block function tile: the sea is wide and thin, and a
    64-block tile made 2,835 functions, each one RCON call in reapply.py."""
    if out.exists():
        shutil.rmtree(out)
    fn = out / "data" / NS / "function" / FOLDER
    fn.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
        "Cobblers: the open sea's floor - kelp forests and seagrass meadows (tools/sea_floor.py)"}}, indent=2) + "\n",
        encoding="utf-8")
    order = []
    for n, pas in enumerate(PASSES):
        tiles = {}
        for ln in m.lines[pas]:
            t = ln.split()
            tiles.setdefault((int(t[1]) // FN_TILE, int(t[3]) // FN_TILE), []).append(ln)
        for t in sorted(tiles):
            body = tiles[t]
            for j in range(0, len(body), RM.PART):
                name = "%d%s_%d_%d%s" % (n + 1, pas, t[0], t[1], "" if j == 0 else "_%d" % (j // RM.PART + 1))
                part = FL.ensure_loaded(["# Generated by tools/sea_floor.py: %s, tile %d %d" % (pas, t[0], t[1])]
                                        + body[j:j + RM.PART])
                bad = FL.check_lines(part, name)
                if bad:
                    raise FloorError("function %s would be refused: %s" % (name, bad[:3]))
                (fn / (name + ".mcfunction")).write_text("\n".join(part) + "\n", encoding="utf-8")
                order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    return order


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=("report", "build"))
    p.add_argument("--source-root", default=None)
    a = p.parse_args(argv)
    m = model(a.source_root)
    s = summary(m)
    print(json.dumps(s, indent=1))
    if a.cmd == "build":
        if m.problems:
            print("NOT BUILT: %d problems" % len(m.problems))
            return 1
        order = write(m)
        s["functions"] = ["%s:%s/%s" % (NS, FOLDER, f) for f in order]
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
        print("wrote %s (%d functions) and %s" % (OUT.relative_to(ROOT), len(order), PLAN.relative_to(ROOT)))
    return 1 if m.problems else 0


if __name__ == "__main__":
    sys.exit(main())
