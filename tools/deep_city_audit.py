#!/usr/bin/env python
"""Audit the Deep's city as generated, offline, against plan data it did not come from.

tools/deep_city.py builds the city; this reads what it actually wrote -- every fill, setblock and place template in
build/datapacks/cobblers_deep_city -- and checks it against data it did not decide:

  the pit and its terraces   tools/rift_deep.py model() and lift_sites(): the owner's traced region, the canonical
                             heightmap and data/rift_deep.json
  the relic area             its traced region (data/rift_regions.json) and tools/ground.py
  Victory Road's mouth       data/vr_caves.json mouth
  the sealed volumes         data/rift_regions.json sited (the cradle, the passage, the HQ's basement), with the
                             envelopes DEEP_CITY.md gives them, derived here -- not data/deep_city.json's own boxes

What must hold:

  inside     every write stands on a column of the pit or of the relic area, nowhere else
  terraces   in the pit nothing is written below its column's tread, except the stair towers cutting into a riser
             beside a lift (never below the lower street), and nothing above y150; in the relic area nothing deeper
             than 6 under the ground or higher than 32 over it
  sealed     nothing is written into the cradle's volume, the passage, the basement or the shaft
  mouth      nothing in Victory Road's mouth tunnel, and nothing but air over the plaza in front of it
  lifts      nothing but air written into a lift block or the two blocks its rider stands in; the up-lift lands on a
             floor (a block written at its target) and the down-lift lands in the open (air at its target)
  streets    on every ring and the floor, the lifts at that level are joined by open ground: the city has not walled a
             street off
  cordon     NO edge column of the relic area carries a fence, and nothing in it stands over the capped surface's
             kept pieces: the cordon was rejected and the shrine is underground (2026-10-02, relic_underground.py)
  nonempty   the output writes something on every ring, the floor and the relic area

  python tools/deep_city_audit.py [--source-root <root>]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "build" / "datapacks" / "cobblers_deep_city"
FN = PACK / "data" / "cobblers" / "function" / "deep_city"

NUM = r"(-?\d+)"
FILL = re.compile(r"fill %s %s %s %s %s %s (\S+)" % ((NUM,) * 6))
SETB = re.compile(r"setblock %s %s %s (\S+)" % ((NUM,) * 3))
PLACE = re.compile(r"place template (\S+) %s %s %s (\S+)" % ((NUM,) * 3))
# blocks no one stands on: matched on the end of the id (a sea_lantern is a floor, a lantern is not)
NOT_SOLID = ("minecraft:air", "_pane", "iron_bars", "ladder", "_wall_sign", "end_rod", "minecraft:lantern",
             "minecraft:chain", "_trapdoor", "_door", "beautify:lamp_candelabra", "handcrafted:dark_oak_chair",
             "handcrafted:dark_oak_table")
PASSABLE = ("minecraft:air", "ladder", "_wall_sign")


def not_solid(b):
    return b.endswith(NOT_SOLID)
CEILING = 150
RELIC_DOWN, RELIC_UP = 6, 32
RELIC_CAPPED_OVER, RELIC_CAPPED_REACH = 3, 9     # the capped surface's tallest kept piece (see the cordon check)
CRADLE_REACH = 40            # a chamber of up to 16 and the Displaced City's 24-block rock shell (DEEP_CITY.md)
CRADLE_ABOVE_FLOOR = 60      # a chamber and its shell over the floor; capped under the relic ground below


def base(b):
    return b.split("[")[0].split("{")[0]


def parse(lines, templates=None):
    """[(x0, y0, z0, x1, y1, z1, block)] for every block write in the lines. A placed template is one box of its
    stored size, turned as the command turns it, written as 'template:<id>'."""
    out = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        m = FILL.match(s)
        if m:
            v = list(map(int, m.groups()[:6]))
            out.append((min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]),
                        max(v[2], v[5]), m.group(7)))
            continue
        m = SETB.match(s)
        if m:
            x, y, z = map(int, m.groups()[:3])
            out.append((x, y, z, x, y, z, m.group(4)))
            continue
        m = PLACE.match(s)
        if m:
            tid, x, y, z, rot = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
            sx, sy, sz = (templates or {}).get(tid, (1, 1, 1))
            corners = [_rot(dx, dz, rot) for dx in (0, sx - 1) for dz in (0, sz - 1)]
            xs, zs = [x + c[0] for c in corners], [z + c[1] for c in corners]
            out.append((min(xs), y, min(zs), max(xs), y + sy - 1, max(zs), "template:" + tid))
    return out


def _rot(x, z, rot):
    return {"none": (x, z), "clockwise_90": (-z, x), "180": (-x, -z), "counterclockwise_90": (z, -x)}[rot]


def sealed_volumes(regions, relic_ground_min, pit_tread_at):
    """The volumes nothing may be written into, from data/rift_regions.json sited and DEEP_CITY.md's envelopes."""
    s = regions["sited"]
    cx, cz = s["hoopa_cradle"]["centre"]
    fy = s["hoopa_cradle"]["floor_y"]
    hx, hy, hz = s["haven_compact_hq"]["at"]
    px, py, pz = s["cradle_passage"]["to"]
    top = min(fy + CRADLE_ABOVE_FLOOR, relic_ground_min - 8)
    shaft_top = pit_tread_at(hx, hz) - 1
    return {
        "hoopa_cradle": (cx - CRADLE_REACH, fy - 24, cz - CRADLE_REACH, cx + CRADLE_REACH, top, cz + CRADLE_REACH),
        "cradle_passage": (min(px, hx) - 8, min(py, hy) - 4, min(pz, hz) - 8, max(px, hx) + 8, max(py, hy) + 12,
                           max(pz, hz) + 8),
        "hq_basement": (hx - 10, hy - 4, hz - 10, hx + 10, hy + 16, hz + 10),
        "hq_secure_shaft": (hx - 4, hy, hz - 4, hx + 4, shaft_top, hz + 4),
    }


def audit(writes, M):
    """writes: parse() output. M: the independent plan -- X0, Z0, pit (bool, z by x), T (tread y), relic (bool),
    H (ground y), lifts [(lower (x, y, z), upper (x, y, z))], mouth (x, y, z), sealed {name: box}.
    -> (problems, stats)."""
    X0, Z0 = M["X0"], M["Z0"]
    pit, T, relic, H = M["pit"], M["T"], M["relic"], M["H"]
    NZ, NX = pit.shape
    mx, my, mz = M["mouth"]
    tunnel = (mx - 5, my - 1, mz - 90, mx + 5, my + 7, mz)
    plaza = (mx - 32, 1, mz + 1, mx + 32, 40, mz + 60)
    problems = []
    stats = {"writes": len(writes), "levels_written": set(), "relic_writes": 0}
    cols = {}                                           # (x, z) -> [(y0, y1, block)]
    lifts = [(tuple(lo), tuple(up)) for lo, up in M["lifts"]]
    lower_near = {}
    for lo, up in lifts:
        for dx in range(-8, 9):
            for dz in range(-8, 9):
                k = (lo[0] + dx, lo[2] + dz)
                lower_near[k] = min(lower_near.get(k, 9999), lo[1])

    def bad(kind, msg):
        problems.append((kind, msg))

    for (x0, y0, z0, x1, y1, z1, b) in writes:
        bb = base(b)
        air = bb == "minecraft:air"
        for name, box in M["sealed"].items():
            if not (x1 < box[0] or x0 > box[3] or y1 < box[1] or y0 > box[4] or z1 < box[2] or z0 > box[5]):
                bad("sealed", "%s written into %s at %s" % (bb, name, (x0, y0, z0, x1, y1, z1)))
        if not (x1 < tunnel[0] or x0 > tunnel[3] or y1 < tunnel[1] or y0 > tunnel[4] or z1 < tunnel[2] or z0 > tunnel[5]):
            bad("mouth", "%s written into Victory Road's mouth tunnel at %s" % (bb, (x0, y0, z0, x1, y1, z1)))
        if not air and not (x1 < plaza[0] or x0 > plaza[3] or y1 < plaza[1] or y0 > plaza[4] or z1 < plaza[2] or z0 > plaza[5]):
            bad("mouth", "%s standing on the plaza before Victory Road's mouth at %s" % (bb, (x0, y0, z0, x1, y1, z1)))
        if y1 > CEILING:
            bad("terraces", "%s above y%d at %s" % (bb, CEILING, (x0, y1, z0)))
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                a, c = z - Z0, x - X0
                inside = 0 <= a < NZ and 0 <= c < NX
                if inside and pit[a, c]:
                    low = int(T[a, c])
                    if (x, z) in lower_near:
                        low = min(low, lower_near[(x, z)] + 1)
                    if y0 < low:
                        bad("terraces", "%s at y%d under the tread y%d at (%d, %d)" % (bb, y0, low, x, z))
                    stats["levels_written"].add(int(T[a, c]))
                elif inside and relic[a, c]:
                    g = int(H[a, c])
                    if y0 < g - RELIC_DOWN or y1 > g + RELIC_UP:
                        bad("relic", "%s at y%d-%d, ground y%d, at (%d, %d)" % (bb, y0, y1, g, x, z))
                    stats["relic_writes"] += 1
                else:
                    bad("inside", "%s written outside the pit and the relic area at (%d, %d)" % (bb, x, z))
                cols.setdefault((x, z), []).append((y0, y1, bb))

    def at(x, y, z):
        """What the output writes at a position: the block, or None."""
        for y0, y1, bb in cols.get((x, z), []):
            if y0 <= y <= y1:
                return bb
        return None

    # the lifts: nothing but air on them or in their rider's space; both ends land somewhere a player can stand
    for lo, up in lifts:
        for p in (lo, up):
            for dy in (0, 1, 2):
                w = at(p[0], p[1] + dy, p[2])
                if w is not None and w != "minecraft:air":
                    bad("lifts", "%s written %s the lift at %s" % (w, "on" if dy == 0 else "over", p))
        # the up-lift sends its rider to the upper street's height at the same column: a floor must be there
        land = at(lo[0], up[1], lo[2])
        if land is None or not_solid(land):
            bad("lifts", "the up-lift at %s lands on %s at y%d, not a floor" % (lo, land or "nothing written", up[1]))
        # the down-lift sends its rider into the lower street's height at its own column, which is inside the upper
        # ring's rock unless the city opened it
        for dy in (1, 2):
            w = at(up[0], lo[1] + dy, up[2])
            if w is None:
                a, c = up[2] - Z0, up[0] - X0
                if pit[a, c] and int(T[a, c]) > lo[1] + dy:
                    bad("lifts", "the down-lift at %s lands in rock at y%d" % (up, lo[1] + dy))
            elif not any(w.endswith(p_) for p_ in PASSABLE):
                bad("lifts", "the down-lift at %s lands in %s at y%d" % (up, w, lo[1] + dy))

    # the streets: at each level the lifts standing there are joined by open ground
    def blocked(x, y, z):
        w = at(x, y, z)
        return w is not None and not any(w.endswith(p_) for p_ in PASSABLE)

    def surface(x, z, lv):
        a, c = z - Z0, x - X0
        if not (0 <= a < NZ and 0 <= c < NX):
            return False
        w = at(x, lv, z)
        if w is not None:
            return not not_solid(w) or w.startswith("template:")
        if not pit[a, c]:
            return False
        # the tread itself, or the rock of a higher ring where the city has cut a room into its riser
        return int(T[a, c]) == lv or (int(T[a, c]) > lv and at(x, lv + 1, z) == "minecraft:air")

    def open_(x, z, lv):
        return surface(x, z, lv) and not blocked(x, lv + 1, z) and not blocked(x, lv + 2, z)

    levels = {}
    for lo, up in lifts:
        levels.setdefault(lo[1], []).append(lo)
        levels.setdefault(up[1], []).append(up)
    floor_y = min(levels) if levels else 0
    levels.setdefault(floor_y, []).append((mx, floor_y, mz + 2))
    for lv, pts in sorted(levels.items()):
        start = pts[0]
        seen = {(start[0], start[2])}
        q = deque([(start[0], start[2])])
        if not open_(start[0], start[2], lv):
            bad("streets", "the lift at %s is not standing on open ground" % (start,))
            continue
        while q:
            x, z = q.popleft()
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, z + dz)
                if n not in seen and open_(n[0], n[1], lv):
                    seen.add(n)
                    q.append(n)
        for p in pts[1:]:
            if (p[0], p[2]) not in seen:
                bad("streets", "at y%d, %s cannot be walked to from %s" % (lv, p, start))
        stats.setdefault("street_cells", {})[lv] = len(seen)

    # the cordon: NO edge column of the relic area carries a fence. Until 2026-10-02 this check demanded the fence on
    # every edge column; the owner then rejected it ("turned back by the zone check rather than barriers", 2026-10-01)
    # and the relic site went underground (data/relic_underground.json), so the same test now fails on any fence.
    # A fenced column is one where the three blocks over its ground are all written and none is passable -- the
    # shape of the old fence (glass then two of bars, or a post), measured from the mask and the heightmap alone
    edge = []
    zz, xx = np.nonzero(relic)
    for z, x in zip(zz.tolist(), xx.tolist()):
        if any(not (0 <= z + dz < NZ and 0 <= x + dx < NX) or not relic[z + dz, x + dx]
               for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            edge.append((x + X0, z + Z0, int(H[z, x])))
    fenced = [(x, z) for x, z, g in edge if all(blocked(x, g + dy, z) for dy in (1, 2, 3))]
    if fenced:
        bad("cordon", "%d of %d edge columns of the relic area are fenced, e.g. %s: the cordon was rejected"
            % (len(fenced), len(edge), fenced[:3]))
    # and the shrine itself is not on the surface. What the cap keeps is all ground-hugging, and each piece's height is
    # set over ground it stands on or beside: a spoil heap is 3 over its own ground, a trench's marker and end rod 2,
    # a fragment 1, the lookout's rail and lantern 1 over the highest ground of its 5x5, the sealed entrance's walls 1
    # over the median ground of its 10x7 forecourt. So no kept block stands more than RELIC_CAPPED_OVER (3) over the
    # highest ground within RELIC_CAPPED_REACH (9, the forecourt's span) of it. The ring stood 22 over the shrine's
    # median ground, the arches 10 and the standing stones 5 to 8 over their own: all above that line
    hmax = H.copy()
    r_ = RELIC_CAPPED_REACH
    pad = np.pad(H, r_, mode="edge")
    for dz in range(-r_, r_ + 1):
        for dx in range(-r_, r_ + 1):
            hmax = np.maximum(hmax, pad[r_ + dz:r_ + dz + NZ, r_ + dx:r_ + dx + NX])
    high = 0
    for (x, z), spans in cols.items():
        a, c = z - Z0, x - X0
        if not (0 <= a < NZ and 0 <= c < NX) or not relic[a, c] or pit[a, c]:
            continue
        solid = [y1 for _y0, y1, bb in spans if bb != "minecraft:air"]
        if solid and max(solid) > int(hmax[a, c]) + RELIC_CAPPED_OVER:
            high += 1
            if high <= 3:
                bad("cordon", "a block at y%d stands %d over the highest ground near (%d, %d): the shrine is underground"
                    % (max(solid), max(solid) - int(hmax[a, c]), x, z))
    stats["relic_high"] = high
    stats["cordon_edge"] = len(edge)

    # nonempty: something on every level of the pit and in the relic area
    want = set(M.get("levels") or [])
    missing = want - stats["levels_written"]
    if missing:
        bad("nonempty", "nothing written on the levels %s" % sorted(missing))
    if relic.any() and stats["relic_writes"] == 0:
        bad("nonempty", "nothing written in the relic area")
    if not writes:
        bad("nonempty", "the output writes nothing")
    stats["levels_written"] = sorted(stats["levels_written"])
    return problems, stats


def load_plan(source_root):
    """The independent plan: the pit's rings and lifts, the relic area and its ground, the mouth, the sealed
    volumes, in one frame covering both regions."""
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as G
    import rift_deep as RD
    m = RD.model(source_root)
    lifts = [(lo[:3], up[:3]) for _k, lo, up in RD.lift_sites(m)]
    rm, (RX0, RZ0, RX1, RZ1), _n = RD.region_mask("relic_area_shrine", source_root)
    PX0, PZ0, PX1, PZ1 = m["box"]
    X0, Z0, X1, Z1 = min(PX0, RX0), min(PZ0, RZ0), max(PX1, RX1), max(PZ1, RZ1)
    shape = (Z1 - Z0 + 1, X1 - X0 + 1)
    pit = np.zeros(shape, bool)
    T = np.full(shape, -9999, np.int32)
    relic = np.zeros(shape, bool)
    pit[PZ0 - Z0:PZ1 - Z0 + 1, PX0 - X0:PX1 - X0 + 1] = m["mask"]
    T[PZ0 - Z0:PZ1 - Z0 + 1, PX0 - X0:PX1 - X0 + 1] = np.where(m["mask"], m["tread_y"], -9999)
    relic[RZ0 - Z0:RZ1 - Z0 + 1, RX0 - X0:RX1 - X0 + 1] = rm
    H = G.load(source_root).box(X0, Z0, X1, Z1)
    vr = json.loads((ROOT / "data" / "vr_caves.json").read_text(encoding="utf-8"))
    regions = json.loads((ROOT / "data" / "rift_regions.json").read_text(encoding="utf-8"))
    relic_min = int(H[relic].min())
    sealed = sealed_volumes(regions, relic_min, lambda x, z: int(T[z - Z0, x - X0]))
    return {"X0": X0, "Z0": Z0, "pit": pit, "T": T, "relic": relic, "H": H, "lifts": lifts,
            "mouth": tuple(vr["mouth"]["at"]), "sealed": sealed, "levels": list(m["treads"])}


def output_lines():
    idx = FN / "index.txt"
    if not idx.is_file():
        raise SystemExit("no %s: run `python tools/deep_city.py build` first" % idx)
    lines = []
    for name in idx.read_text(encoding="utf-8").split():
        lines += (FN / (name + ".mcfunction")).read_text(encoding="utf-8").splitlines()
    templates = {}
    sys.path.insert(0, str(ROOT / "tools"))
    import structure_nbt
    for f in (PACK / "data").rglob("*.nbt"):
        rel = f.relative_to(PACK / "data").parts
        tid = "%s:%s" % (rel[0], "/".join(rel[2:])[:-4])
        templates[tid] = tuple(int(v) for v in structure_nbt.load(f)["size"])
    return lines, templates


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    a = ap.parse_args(argv)
    if not a.source_root:
        ap.error("needs --source-root or COBBLERS_SOURCE_ROOT: the plan comes from the heightmap")
    lines, templates = output_lines()
    writes = parse(lines, templates)
    M = load_plan(a.source_root)
    problems, stats = audit(writes, M)
    print("writes %d; levels written %s; relic columns written %d; relic edge %d"
          % (stats["writes"], stats["levels_written"], stats["relic_writes"], stats["cordon_edge"]))
    for lv, n in sorted((stats.get("street_cells") or {}).items()):
        print("  open street joining the lifts at y%-3d %7d columns" % (lv, n))
    for name, box in M["sealed"].items():
        print("  sealed %-16s %s" % (name, box))
    kinds = {}
    for k, msg in problems:
        kinds.setdefault(k, []).append(msg)
    for k in ("inside", "terraces", "sealed", "mouth", "lifts", "streets", "relic", "cordon", "nonempty"):
        got = kinds.get(k, [])
        print("%-9s %s" % (k, "clean" if not got else "%d PROBLEM(S): %s" % (len(got), "; ".join(got[:3]))))
    print("the Deep's city audit: %s" % ("CLEAN" if not problems else "%d PROBLEMS" % len(problems)))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
