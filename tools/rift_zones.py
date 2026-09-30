#!/usr/bin/env python
"""The Rift's zones: who may stand where, the walls that say so, and the gatehouses in them.

  python tools/rift_zones.py trace --source-root <root>   # re-derive the boxes and spans into data/rift_zones.json
  python tools/rift_zones.py report                       # fail-closed audit of the DATA (exit 1 on any problem)
  python tools/rift_zones.py build --source-root <root>   # emit build/datapacks/cobblers_rift_zones

WHAT THIS IS. docs/mechanics/RIFT_ZONES.md is the design; data/rift_zones.json is the data, and records every
place this implementation and that design disagree. docs/world-building/RIFT_ZONES_BUILD.md is the build note.
Nothing here has been installed, run on a server or seen by a player.

THE RUNG (CLAUDE.md principle 6). A datapack with functions, rungs 5 and 6, and no rung above. Cobblemon has no
player-zone concept; no installed addon gates an area; Cobbleverse ships none; no config key expresses "a player
without X may not stand here". A vanilla minecraft:location advancement does, and its reward function acts. This
is not a guess: tools/gulch_mine.py already runs the identical shape for the gulch (data/gulch_mine.json zone,
gate), so the rung is proven in this repository rather than assumed from documentation.

THE GROUND RULE (CLAUDE.md, "Ground comes from the heightmap"). Every y in this tool comes from tools/ground.py
or from a measurement made on it. Nothing reads a world. The zone shapes come from the owner's annotated map
(land_8k_16_annotated_rift.png), flood-filled from data/rift_regions.json's own seeds, which is measured plan
data; `trace` refuses to go on unless every fill reproduces that file's recorded bbox exactly.

FAIL-CLOSED. `report` compares data/rift_zones.json against OTHER files -- data/rift_regions.json,
data/gulch_mine.json, data/landmarks.json, data/placements.json, data/progression.json, data/spawn_blocks.json,
data/legendaries.json and the canonical heightmap -- and never against anything this tool emitted. It exits 1 on
the first category of problem it finds and prints every problem it found.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "rift_zones.json"
REGIONS = ROOT / "data" / "rift_regions.json"
PACKS = ROOT / "build" / "datapacks"
NS = "cobblers"
FOLDER = "rift_zones"
PACK = "cobblers_rift_zones"


class ZoneError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


_NUMS = __import__("re").compile(r"\[\s*(-?\d+(?:\.\d+)?(?:\s*,\s*-?\d+(?:\.\d+)?)*)\s*\]")


def jdump(obj, path):
    """indent=2, but an array of plain numbers stays on one line.

    data/rift_zones.json holds 373 boxes and 1,459 wall columns. At four lines a coordinate pair that is
    8,700 lines of mostly single digits, which every later reader pays for. Collapsed it is about 1,100."""
    s = json.dumps(obj, indent=2, ensure_ascii=False)
    s = _NUMS.sub(lambda m: "[%s]" % ", ".join(x.strip() for x in m.group(1).split(",")), s)
    Path(path).write_text(s + "\n", encoding="utf-8")


# ----------------------------------------------------------------- geometry

def point_in(poly, px, pz):
    """even-odd, the same test tools/gulch_mine.py and tools/subregion_boxes.py use"""
    c = False
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        if (z0 > pz) != (z1 > pz):
            if px < x0 + (pz - z0) * (x1 - x0) / (z1 - z0):
                c = not c
    return c


def runs_to_boxes(cells, grid, ox, oz):
    """{(ix, iz)} grid cells -> [(x0, z0, x1, z1)] block boxes, rows merged down while identical."""
    if not cells:
        return []
    izs = sorted({c[1] for c in cells})
    boxes, open_ = [], {}
    for iz in range(min(izs), max(izs) + 2):
        row, start = set(), None
        ixs = sorted(c[0] for c in cells if c[1] == iz)
        prev = None
        for ix in ixs:
            if start is None:
                start = ix
            elif ix != prev + 1:
                row.add((start, prev))
                start = ix
            prev = ix
        if start is not None:
            row.add((start, prev))
        for r in list(open_):
            if r not in row:
                z0 = open_.pop(r)
                boxes.append((ox + r[0] * grid, oz + z0 * grid,
                              ox + (r[1] + 1) * grid - 1, oz + iz * grid - 1))
        for r in row:
            open_.setdefault(r, iz)
    return sorted(boxes, key=lambda b: (b[1], b[0]))


def mask_to_cells(mask, X0, Z0, grid):
    """coverage per grid cell: {(ix, iz): columns covered}, cell origin snapped to the grid"""
    H, W = mask.shape
    gx0 = (X0 // grid) * grid
    gz0 = (Z0 // grid) * grid
    nz = (Z0 + H - gz0 + grid - 1) // grid
    nx = (X0 + W - gx0 + grid - 1) // grid
    pad = np.zeros((nz * grid, nx * grid), np.int32)
    pad[Z0 - gz0:Z0 - gz0 + H, X0 - gx0:X0 - gx0 + W] = mask
    cov = pad.reshape(nz, grid, nx, grid).sum(axis=(1, 3))
    return cov, gx0, gz0


def outward_from(mask, X0, Z0, at):
    """The nearest column OUTSIDE the zone to the guard's surveyed site, and the unit direction to it.

    The guard stands where the data sites it -- data/rift_sculpt.json's own entrances for G1 and G2,
    docs/mechanics/RIFT_ZONES.md's survey for G4 and G5 -- and is NOT snapped to the zone's edge. Two of the
    four are well inside the traced boundary (G2's descent at (3738, 5082) is 145 blocks inside the Rift's
    coarse extent hull), and moving an authored guard 145 blocks to suit a hull would be the tool overruling
    the data. So the direction and the turn-back distance are measured instead: whatever is outside, however
    far, is where an unqualified player is put."""
    H, W = mask.shape
    ax, az = at
    ix, iz = ax - X0, az - Z0
    if not (0 <= ix < W and 0 <= iz < H and mask[iz, ix]):
        raise ZoneError("the guard site (%d, %d) is not inside its own zone" % (ax, az))
    zz, xx = np.nonzero(~mask)
    if len(zz) == 0:
        raise ZoneError("the zone covers the whole frame; no outside column")
    d = (xx - ix) ** 2 + (zz - iz) ** 2
    i = int(np.argmin(d))
    ox, oz = int(xx[i]) + X0, int(zz[i]) + Z0
    dx, dz = ox - ax, oz - az
    n = math.hypot(dx, dz)
    if n < 1e-6:
        raise ZoneError("outward direction at the guard site is degenerate")
    return (ox, oz), (dx / n, dz / n), n


def yaw_towards(dx, dz):
    """Minecraft yaw looking along (dx, dz): 0 = +z, 90 = -x, 180 = -z, -90 = +x."""
    return round(math.degrees(math.atan2(-dx, dz)), 1)


# ----------------------------------------------------------------- the traced regions

def annotated(spec, source_root):
    from PIL import Image
    p = Path(source_root) / spec["source"]["file"]
    if not p.is_file():
        raise ZoneError("no annotated map at %s (it is a source input, gitignored; pass --source-root)" % p)
    got = hashlib.sha256(p.read_bytes()).hexdigest()
    if got != spec["source"]["sha256"]:
        raise ZoneError("annotated map sha256 %s, data says %s" % (got[:16], spec["source"]["sha256"][:16]))
    return np.array(Image.open(p).convert("RGB"))


def nudge_candidates(wall, px, pz, limit=40):
    """Every non-outline pixel near (px, pz), nearest first."""
    H, W = wall.shape
    out = []
    if not wall[pz, px]:
        out.append((px, pz))
    for r in range(1, limit + 1):
        ring = []
        for dz in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dz), abs(dx)) != r:
                    continue
                nz, nx = pz + dz, px + dx
                if 0 <= nz < H and 0 <= nx < W and not wall[nz, nx]:
                    ring.append((dz * dz + dx * dx, nx, nz))
        out += [(x, z) for _, x, z in sorted(ring)]
    return out


def nudge(wall, px, pz, limit=40):
    """The nearest non-outline pixel to (px, pz). Two of data/rift_regions.json's eleven seeds -- `gate`
    (3560, 2650) and `relic_area_shrine` (3340, 3310) -- sit on pure black, because that file's seeds are
    region centres and the owner's annotation writes each region's NAME across it in the same black the
    outlines use (its own source.label_text says so). A centre that lands on a letter is not a fill seed.
    The nudge is bounded and the bbox check below is what proves it did not cross into a neighbour."""
    H, W = wall.shape
    if not wall[pz, px]:
        return px, pz, 0
    for r in range(1, limit + 1):
        for dz in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dz), abs(dx)) != r:
                    continue
                nz, nx = pz + dz, px + dx
                if 0 <= nz < H and 0 <= nx < W and not wall[nz, nx]:
                    return nx, nz, r
    raise ZoneError("no non-outline pixel within %d of the seed" % limit)


def fill_region(rgb, wall, seed, origin, expect=None):
    """Flood fill from the seed over non-outline pixels; returns (mask, bbox, columns) in block space.

    When `expect` is the region's recorded bbox, the fill is tried from each non-outline pixel near the seed,
    nearest first, and only a fill that reproduces that bbox EXACTLY is accepted. A seed sitting on the
    annotation's own lettering can otherwise leak into the pocket on the far side of a letter stroke, which is
    what relic_area_shrine (3340, 3310) does: its nearest free pixel is west of an 'l' and fills 3150-3342
    instead of 3285-3429. The recorded bbox is the check that catches it."""
    ox, oz = origin
    H, W = wall.shape
    cands = nudge_candidates(wall, seed[0] - ox, seed[1] - oz)
    if not cands:
        raise ZoneError("no non-outline pixel near the seed")
    last = None
    for (px, pz) in (cands if expect else cands[:1]):
        got = _fill_from(wall, px, pz, origin)
        if expect is None or list(got[1]) == list(expect):
            return got
        last = got
    raise ZoneError("no seed near (%d, %d) fills to the recorded bbox %s (nearest gave %s)"
                    % (seed[0], seed[1], list(expect), list(last[1]) if last else None))


def _fill_from(wall, px, pz, origin):
    ox, oz = origin
    H, W = wall.shape
    seen = np.zeros(wall.shape, bool)
    seen[pz, px] = True
    q = deque([(pz, px)])
    minx = maxx = px
    minz = maxz = pz
    n = 0
    while q:
        z, x = q.popleft()
        n += 1
        if x < minx:
            minx = x
        if x > maxx:
            maxx = x
        if z < minz:
            minz = z
        if z > maxz:
            maxz = z
        for nz, nx in ((z + 1, x), (z - 1, x), (z, x + 1), (z, x - 1)):
            if 0 <= nz < H and 0 <= nx < W and not seen[nz, nx] and not wall[nz, nx]:
                seen[nz, nx] = True
                q.append((nz, nx))
    return seen, (minx + ox, minz + oz, maxx + ox, maxz + oz), n


def trace_regions(spec, source_root, wanted):
    """{region id: (mask, bbox, columns)} for the wanted regions, checked against data/rift_regions.json."""
    rr = load(REGIONS)
    world = load(ROOT / "data" / "world.json")
    origin = (world["grid"]["origin_x"], world["grid"]["origin_z"])
    rgb = annotated(spec, source_root)
    dark = rgb.max(axis=2)
    # the outline is drawn black; the threshold is the one that reproduces every recorded bbox exactly.
    best, best_thr, best_bad = None, None, None
    for thr in range(2, 25):
        wall = dark <= thr
        got, bad = {}, []
        for rid in wanted:
            rec = rr["regions"][rid]
            try:
                got[rid] = fill_region(rgb, wall, tuple(rec["seed"]), origin, rec["bbox"])
            except ZoneError as e:
                bad.append("%s: %s" % (rid, e))
                continue
            if list(got[rid][1]) != rec["bbox"]:
                bad.append("%s: fill bbox %s, data bbox %s" % (rid, list(got[rid][1]), rec["bbox"]))
                continue
            n, ref = got[rid][2], rec["columns_with_label_holes"]
            if abs(n - ref) > 0.02 * ref:
                bad.append("%s: fill %d columns, data columns_with_label_holes %d (>2%%)" % (rid, n, ref))
        if not bad:
            return got, thr, origin
        if best_bad is None or len(bad) < len(best_bad):
            best, best_thr, best_bad = got, thr, bad
    raise ZoneError("no outline threshold in 2..24 reproduces data/rift_regions.json; best was %d with %d "
                    "mismatch(es):\n    %s" % (best_thr, len(best_bad), "\n    ".join(best_bad)))


# ----------------------------------------------------------------- the heightmap

def ground_of(source_root):
    sys.path.insert(0, str(ROOT / "tools"))
    import ground as GD
    return GD.load(source_root)


def fill_polygon(polys, X0, Z0, shape):
    """Boolean mask of the polygon interior over the frame, even-odd, scanline."""
    H, W = shape
    m = np.zeros(shape, bool)
    for iz in range(H):
        zc = Z0 + iz + 0.5
        cuts = []
        for p in polys:
            n = len(p)
            for i in range(n):
                (x0, z0), (x1, z1) = p[i], p[(i + 1) % n]
                if (z0 > zc) != (z1 > zc):
                    cuts.append(x0 + (zc - z0) * (x1 - x0) / (z1 - z0))
        cuts.sort()
        for i in range(0, len(cuts) - 1, 2):
            a = int(math.ceil(cuts[i] - 0.5)) - X0
            b = int(math.floor(cuts[i + 1] - 0.5)) - X0
            if b >= a:
                m[iz, max(0, a):min(W, b + 1)] = True
    return m


def claim_interior(seeds, interior):
    """Every interior column goes to the nearest seed label: a multi-source breadth-first growth.

    WHY. The eleven regions of data/rift_regions.json do NOT tile the Rift. Measured 2026-09-30: the four
    live zones' traced regions hold 616,887 columns and the gulch 61,330, against a Rift interior of about
    1.4 million -- the owner drew named PLACES with unclaimed ground between them, and where two of them meet
    the outlines do not touch (the excavation site and the relic area share a frontier 3 columns wide). Zones
    built as plain unions of regions would therefore leave most of the Rift unzoned, and an unzoned column is
    a way round the gate: a player could walk from the dig camp to Victory Road over ground no zone claims.

    So each zone claims the interior ground nearest its own traced regions. The boundaries stay exactly where
    the owner's outlines put them -- the growth is equidistant between two regions -- and no interior column
    is left unclaimed. Ties go to the lower zone order, so the result does not depend on iteration order.

    `seeds` is [(label, mask)] in order; returns an int array, 0 unclaimed, otherwise 1-based label index."""
    lab = np.zeros(interior.shape, np.int16)
    for i, (_, m) in enumerate(seeds):
        lab[(lab == 0) & m & interior] = i + 1
    while True:
        grown = False
        for i in range(len(seeds)):
            cur = lab == i + 1
            n = np.zeros_like(cur)
            n[1:, :] |= cur[:-1, :]
            n[:-1, :] |= cur[1:, :]
            n[:, 1:] |= cur[:, :-1]
            n[:, :-1] |= cur[:, 1:]
            take = n & interior & (lab == 0)
            if take.any():
                lab[take] = i + 1
                grown = True
        if not grown:
            return lab


def grow(mask, d):
    """mask dilated by d columns, 4-connected; no scipy dependency."""
    m = mask.copy()
    for _ in range(d):
        n = m.copy()
        n[1:, :] |= m[:-1, :]
        n[:-1, :] |= m[1:, :]
        n[:, 1:] |= m[:, :-1]
        n[:, :-1] |= m[:, 1:]
        m = n
    return m


def frontier(inner, outer, X0, Z0, reach):
    """The columns of `inner` that lie within `reach` of `outer`: the traced boundary the two zones share.

    This is the wall line. It is a curve, not a straight cut, because the boundary the owner drew is a curve
    and a wall on a straight line would leave open ground at both ends and cross rock in the middle. The two
    masks never touch -- the annotation's outline is drawn BETWEEN them, a few pixels wide -- so `outer` is
    grown by `reach` before the test. Returned sorted by (z, x); the wall fills each column independently,
    so no path order is needed."""
    near = grow(outer, reach) & inner
    zz, xx = np.nonzero(near)
    return sorted(((int(x) + X0, int(z) + Z0) for z, x in zip(zz, xx)), key=lambda p: (p[1], p[0]))


def cut_span(g, cut, mask, X0, Z0):
    """The reach of a cut line: the longest unbroken run of columns ON the line that lie inside the traced
    mask of the zone the wall closes.

    NOT a ground test. The canonical heightmap is the terrain BEFORE data/rift_sculpt.json raises the rim
    into crags and parapets; that sculpt lives in derived/rift_sculpt/plan.json, which an isolated agent
    may not read (CLAUDE.md). So on this heightmap the Rift's shoulders never reach floor + 32 and a
    ground rule runs away: measured 2026-09-30, the throat line spanned 710 blocks that way against the
    322 docs/mechanics/RIFT_ZONES.md section 2 surveyed. The traced region edge is the honest boundary and
    it is the same edge the zone's own boxes stop at, so the wall closes exactly what the zone claims.

    Returns ([lo, hi], floor_y, side) where side is the offset of the sampled line from `at`."""
    H, W = mask.shape
    best = None
    for side in (0, -1, 1):
        if cut["axis"] == "x":
            i = cut["at"] + side - X0
            if not 0 <= i < W:
                continue
            line = mask[:, i]
            base = Z0
        else:
            i = cut["at"] + side - Z0
            if not 0 <= i < H:
                continue
            line = mask[i, :]
            base = X0
        idx = np.nonzero(line)[0]
        if len(idx) == 0:
            continue
        runs, s = [], idx[0]
        for k in range(1, len(idx)):
            if idx[k] != idx[k - 1] + 1:
                runs.append((s, idx[k - 1]))
                s = idx[k]
        runs.append((s, idx[-1]))
        lo, hi = max(runs, key=lambda r: r[1] - r[0])
        if best is None or (hi - lo) > (best[0][1] - best[0][0]):
            best = ([int(lo) + base, int(hi) + base], side)
    if best is None:
        raise ZoneError("cut %s: no traced column lies on it" % cut["id"])
    span, side = best
    tx, tz = cut["through"]
    return span, int(g(tx, tz)), side


# ----------------------------------------------------------------- trace

def zone_masks(spec, regions, X0, Z0, shape, interior=None, gulch_region=None):
    """{zone id: bool mask} over the shared frame, disjoint by construction.

    Each zone's seed is the union of the traced regions it names, split by its cut if it has one. When
    `interior` is given, the seeds then claim the whole Rift interior between them (claim_interior), so the
    zones tile it and leave nothing unzoned."""
    gulch = load(ROOT / "data" / "gulch_mine.json")["zone"]["polygon"]
    cuts = {c["id"]: c for c in spec["cuts"]}
    out = {}
    for zid, z in spec["zones"].items():
        if z.get("status") == "SUPERSEDED, nothing emitted":
            continue
        m = np.zeros(shape, bool)
        parts = [(r, None) for r in z["regions"]]
        for extra in z.get("also_regions", []):
            parts.append((extra["id"], extra["cut"]))
        if z.get("cut"):
            parts = [(r, z["cut"]) for r, _ in parts]
        for rid, cut in parts:
            sub = regions[rid][0].copy()
            if cut:
                c = cuts[cut["id"]]
                idx = np.arange(shape[0])[:, None] + Z0 if c["axis"] == "z" else np.arange(shape[1])[None, :] + X0
                sub &= (idx < c["at"]) if cut["keep"] == "less" else (idx >= c["at"])
            m |= sub
        out[zid] = m
    if interior is None:
        return out
    # the gulch's built zone is not ours: it is excluded from the interior, and its own traced region seeds
    # a label of its own so unclaimed ground beside it goes to the gulch rather than to one of our zones
    gmask = fill_polygon([gulch], X0, Z0, shape)
    inner = interior & ~gmask
    order = sorted(out, key=lambda z: spec["zones"][z]["order"])
    seeds = [(z, out[z] & inner) for z in order]
    if gulch_region is not None:
        seeds.append(("gulch", gulch_region & inner))
    lab = claim_interior(seeds, inner)
    return {z: (lab == i + 1) for i, z in enumerate(order)}, lab, inner


def cmd_trace(a):
    spec = load()
    wanted = []
    for z in spec["zones"].values():
        if z.get("status", "").startswith("SUPERSEDED"):
            continue
        wanted += list(z["regions"]) + [e["id"] for e in z.get("also_regions", [])]
    # the gulch's region is traced too, not to make a zone of ours but so the ground beside its built zone is
    # claimed by the gulch rather than by one of ours
    wanted.append("mega_stone_mine_the_gulch")
    wanted = sorted(set(wanted))
    regions, thr, origin = trace_regions(spec, a.source_root, wanted)
    print("outline threshold %d; every traced bbox matches data/rift_regions.json" % thr)

    # the frame must hold the traced regions AND the Rift's whole extent AND every guard site: the extent
    # reaches z5388 where the traced regions stop at z5079, and G2's descent (3738, 5082) is in that tail.
    land0 = load(ROOT / "data" / "landmarks.json")
    rift0 = [l for l in land0["landmarks"] if l["id"] == "rift"][0]
    pts = [(p[0], p[1]) for poly in rift0["extent"]["polygons"] for p in poly]
    pts += [tuple(z["guard"]["at"]) for z in spec["zones"].values() if z.get("guard")]
    bb = [regions[r][1] for r in wanted]
    X0 = min([b[0] for b in bb] + [p[0] for p in pts]) - 4
    Z0 = min([b[1] for b in bb] + [p[1] for p in pts]) - 4
    X1 = max([b[2] for b in bb] + [p[0] for p in pts]) + 4
    Z1 = max([b[3] for b in bb] + [p[1] for p in pts]) + 4
    shape = (Z1 - Z0 + 1, X1 - X0 + 1)
    cropped = {r: (regions[r][0][Z0 - origin[1]:Z1 - origin[1] + 1, X0 - origin[0]:X1 - origin[0] + 1],
                   regions[r][1], regions[r][2]) for r in wanted}

    land = load(ROOT / "data" / "landmarks.json")
    rift = [l for l in land["landmarks"] if l["id"] == "rift"][0]
    interior = fill_polygon(rift["extent"]["polygons"], X0, Z0, shape)
    greg = regions.get("mega_stone_mine_the_gulch")
    gcrop = greg[0][Z0 - origin[1]:Z1 - origin[1] + 1, X0 - origin[0]:X1 - origin[0] + 1] if greg else None
    masks, lab, inner = zone_masks(spec, cropped, X0, Z0, shape, interior, gcrop)
    unclaimed = int((inner & (lab == 0)).sum())
    print("the Rift's interior: %d columns (data/landmarks.json rift.extent); %d left unclaimed"
          % (int(inner.sum()), unclaimed))
    if unclaimed:
        raise ZoneError("%d interior columns belong to no zone: an unzoned column is a way round every gate"
                        % unclaimed)
    spec["interior"] = {"columns": int(inner.sum()),
                        "from": "data/landmarks.json rift.extent.polygons, less data/gulch_mine.json's zone",
                        "why": "the ground the zones must tile. Every column of it belongs to exactly one zone."}
    g = ground_of(a.source_root)
    grid = spec["grid"]

    # one coverage pass so the zones cannot overlap: a cell goes to the zone that covers most of it
    order = sorted(masks, key=lambda z: spec["zones"][z]["order"])
    covs = {}
    for zid in order:
        covs[zid], gx0, gz0 = mask_to_cells(masks[zid], X0, Z0, grid)
    stack = np.stack([covs[z] for z in order])
    best = stack.argmax(axis=0)
    total = stack.sum(axis=0)
    half = grid * grid / 2.0
    for i, zid in enumerate(order):
        cells = {(int(x), int(z)) for z, x in zip(*np.nonzero((best == i) & (stack[i] >= half) & (total > 0)))}
        boxes = runs_to_boxes(cells, grid, gx0, gz0)
        z = spec["zones"][zid]
        z["boxes"] = [list(b) for b in boxes]
        z["boxes_columns"] = int(masks[zid].sum())
        z["boxes_from"] = ("union of the traced regions %s at grid %d, a cell kept when this zone covers at least "
                           "half of it and more of it than any other zone, so the zones cannot overlap"
                           % (", ".join(z["regions"]), grid))
        print("%-4s %-34s %5d boxes  %8d traced columns" % (zid, z["name"], len(boxes), z["boxes_columns"]))

    # the wall lines: the traced frontier each walled zone shares with the zone on the other side
    walled = {z["wall"]: zid for zid, z in spec["zones"].items() if z.get("wall")}
    reach = spec["wall"]["frontier_reach"]
    for c in spec["cuts"]:
        zid = walled.get(c["id"])
        if zid is None:
            raise ZoneError("cut %s closes no zone" % c["id"])
        other = [s for s in c["separates"] if s != zid]
        if len(other) != 1 or other[0] not in masks:
            raise ZoneError("cut %s: separates %s does not name one other live zone" % (c["id"], c["separates"]))
        line, used = [], None
        for r in range(2, reach + 1):
            line = frontier(masks[zid], masks[other[0]], X0, Z0, r)
            if line:
                used = r
                break
        if not line:
            raise ZoneError("cut %s: %s and %s share no frontier within %d blocks. Either they are not "
                            "neighbours or the band of unclaimed ground between them is wider than a wall "
                            "should bridge; check data/rift_regions.json's two bboxes." % (c["id"], zid, other[0], reach))
        c["frontier_reach_used"] = used
        # only the part of the frontier that crosses walkable floor becomes a wall. The rest runs up the
        # Rift's own walls, and docs/mechanics/RIFT_FRACTURE.md is explicit that there the scarps are the
        # barrier. Ground from tools/ground.py; floor_y is the ground at the cut's surveyed `through` point.
        floor = int(g(*c["through"]))
        band = spec["wall"]["floor_band"]
        whole = len(line)
        line = [p for p in line if g(p[0], p[1]) <= floor + band]
        if not line:
            raise ZoneError("cut %s: no frontier column stands on walkable floor (floor y%d + %d)"
                            % (c["id"], floor, band))
        c["frontier_columns"] = whole
        c["on_scarp"] = whole - len(line)
        c["on_scarp_why"] = ("frontier columns whose ground stands more than %d above the floor at `through`. "
                             "No wall is built on them: docs/mechanics/RIFT_FRACTURE.md, 'the scarps are the "
                             "barrier'. %d of %d columns here." % (band, whole - len(line), whole))
        xs = [p[0] for p in line]
        zs = [p[1] for p in line]
        c["closes"] = zid
        c["against"] = other[0]
        c["line"] = [list(p) for p in line]
        c["columns"] = len(line)
        c["bbox"] = [min(xs), min(zs), max(xs), max(zs)]
        c["floor_y"] = int(g(*c["through"]))
        c["across"] = max(max(xs) - min(xs), max(zs) - min(zs)) + 1
        c["span"] = [min(zs), max(zs)] if c["axis"] == "x" else [min(xs), max(xs)]
        c["line_why"] = ("the columns of %s's traced mask within %d of %s's: the boundary the owner drew between "
                         "the two regions, which is where the wall closes a pass instead of crossing open ground "
                         "(docs/mechanics/RIFT_FRACTURE.md, 'the scarps are the barrier'). Not a straight line and "
                         "not a ground test: see tools/rift_zones.py frontier()." % (zid, reach, other[0]))
        print("wall %-14s closes %-3s against %-3s: %4d columns, bbox %s, %d across, floor y%d"
              % (c["id"], zid, other[0], len(line), c["bbox"], c["across"], c["floor_y"]))

    # the guards, and the places round them
    gh = spec["gatehouse"]
    for zid in order:
        z = spec["zones"][zid]
        if not z.get("guard"):
            continue
        bx, bz = z["guard"]["at"]
        (ox, oz), (dx, dz), dist = outward_from(masks[zid], X0, Z0, (bx, bz))
        inx, inz = -dx, -dz
        z["guard"]["block"] = [bx, bz]
        z["guard"]["ground_y"] = int(g(bx, bz))
        z["guard"]["outward"] = [round(dx, 4), round(dz, 4)]
        z["guard"]["outside_at"] = [ox, oz]
        z["guard"]["outside_distance"] = int(round(dist))
        z["guard"]["block_why"] = ("the guard stands on its surveyed site, unmoved. The outward direction and the "
                                   "distance to the nearest column outside the zone (%d blocks) are measured from "
                                   "the traced mask." % round(dist))
        fy = int(g(bx, bz)) + 1

        # the places are measured against the RASTERISED BOXES, not the mask, because the boxes are what the
        # advancement tests. A guard standing a few blocks from the edge can otherwise have its arrival land in
        # an 8-block cell that did not make the majority cut, and the player would arrive already outside.
        bxs = [tuple(b) for b in z["boxes"]]

        def inb(x, zz):
            return any(q[0] <= x <= q[2] and q[1] <= zz <= q[3] for q in bxs)

        def walk(px, pz, ux, uz, want, limit=96):
            for n in range(0, limit + 1):
                qx, qz = int(round(px + ux * n)), int(round(pz + uz * n))
                if inb(qx, qz) == want:
                    return qx, qz, n
            raise ZoneError("%s: no column %s the boxes within %d of the guard along (%.2f, %.2f)"
                            % (zid, "inside" if want else "outside", limit, ux, uz))

        sx, sz, _ = walk(bx, bz, inx, inz, True)
        ax, az, _ = walk(sx, sz, inx, inz, True)
        ax, az = int(round(sx + inx * gh["arrive_in"])), int(round(sz + inz * gh["arrive_in"]))
        if not inb(ax, az):
            ax, az = sx, sz
        ex, ez = int(round(sx + inx * gh["exit_in"])), int(round(sz + inz * gh["exit_in"]))
        if not inb(ex, ez):
            ex, ez = sx, sz
        # outward may be a long way: G1 and G2 stand at sculpted rim entrances that are well inside the Rift's
        # coarse extent hull, so the first column outside the BOXES can be hundreds of blocks off. 600 is under
        # the Rift's own width, so a failure here means the geometry is wrong rather than the limit too small.
        qx, qz, _ = walk(bx, bz, dx, dz, False, 600)
        tx, tz = int(round(qx + dx * gh["turn_back_out"])), int(round(qz + dz * gh["turn_back_out"]))
        if inb(tx, tz):
            tx, tz = qx, qz
        z["arrive"] = [ax + 0.5, int(g(ax, az)) + 1, az + 0.5, yaw_towards(inx, inz)]
        z["turn_back"] = [tx + 0.5, int(g(tx, tz)) + 1, tz + 0.5, yaw_towards(dx, dz)]
        z["exit"] = [ex, int(g(ex, ez)) + 1, ez, ex, int(g(ex, ez)) + 2, ez]
        z["places_why"] = ("feet levels from tools/ground.py at each column: the arrival %d blocks inside facing in; "
                           "the turn-back %d blocks PAST the nearest outside column (%d, %d), facing away, so it is "
                           "outside the zone however far inside the guard stands; the exit box %d inside on the "
                           "walkway. Guard feet at y%d."
                           % (gh["arrive_in"], gh["turn_back_out"], ox, oz, gh["exit_in"], fy))
    spec["status"] = ("traced 2026-09-30 from %s at outline threshold %d; boxes and spans are measured, nothing is "
                      "built, nothing installed, not seen in game" % (spec["source"]["file"], thr))
    jdump(spec, SPEC)
    print("wrote %s" % SPEC)
    return 0


# ----------------------------------------------------------------- report

def cmd_report(a, quiet=False):
    """Returns 0 only when there is neither a problem nor an owed dependency.

    A PROBLEM is something wrong in this data. An OWED item is something another file must still supply --
    today, the rift_crisis_resolved flag and its setter, which are Codex's story data (data/rift_zones.json
    zones.z5.needs_progression). Both make `report` exit 1, because neither may be forgotten. Only a PROBLEM
    stops `build`: an advancement that does not exist yet fails CLOSED, since a condition on a missing
    advancement never matches and nobody is granted the pass."""
    spec = load()
    P, OWED = [], []

    def bad(msg):
        P.append(msg)

    def owed(msg):
        OWED.append(msg)

    rr = load(REGIONS)
    gulch = load(ROOT / "data" / "gulch_mine.json")
    land = load(ROOT / "data" / "landmarks.json")
    prog = load(ROOT / "data" / "progression.json")
    rift = [l for l in land["landmarks"] if l["id"] == "rift"][0]
    ext = rift["extent"]["polygons"][0]
    grid = spec["grid"]
    live = {z: r for z, r in spec["zones"].items() if not str(r.get("status", "")).startswith("SUPERSEDED")}

    # 1. every live zone is traced, and the superseded one is empty
    for zid, z in spec["zones"].items():
        sup = str(z.get("status", "")).startswith("SUPERSEDED")
        if sup:
            if z.get("boxes"):
                bad("%s is superseded but carries %d boxes" % (zid, len(z["boxes"])))
            if not z.get("superseded_by"):
                bad("%s is superseded with no superseded_by" % zid)
            continue
        if not z.get("boxes"):
            bad("%s has no boxes: run `python tools/rift_zones.py trace --source-root <root>`" % zid)
        for k in ("arrive", "turn_back", "exit"):
            if z.get(k) is None:
                bad("%s has no %s" % (zid, k))
        if not z.get("pass"):
            bad("%s has no pass" % zid)
        if not z.get("guard"):
            bad("%s has no guard" % zid)
        for b in z.get("boxes") or []:
            if b[0] % grid or b[1] % grid or (b[2] + 1) % grid or (b[3] + 1) % grid:
                bad("%s box %s is off the %d grid" % (zid, b, grid))
    if P:
        return fail(P)

    # 2. the zones do not overlap, and every box lies inside the Rift
    def boxes_of(z):
        return [tuple(b) for b in z["boxes"]]

    ids = sorted(live)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            for b in boxes_of(live[ids[i]]):
                for c in boxes_of(live[ids[j]]):
                    if b[0] <= c[2] and c[0] <= b[2] and b[1] <= c[3] and c[1] <= b[3]:
                        bad("%s and %s overlap at %s / %s" % (ids[i], ids[j], b, c))
                        break
                else:
                    continue
                break
    for zid, z in live.items():
        out = 0
        for b in boxes_of(z):
            cx, cz = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
            if not point_in(ext, cx, cz):
                out += 1
        if out:
            bad("%s: %d of %d boxes have their centre outside the Rift's extent (data/landmarks.json rift)"
                % (zid, out, len(z["boxes"])))

    # 3. each zone contains the traced regions it claims: every named region's own seed falls inside its boxes.
    #    (The converse is deliberately NOT checked: a zone also claims the interior ground nearest its regions,
    #    because the eleven regions do not tile the Rift -- see tools/rift_zones.py claim_interior.)
    for zid, z in live.items():
        named = list(z["regions"]) + [e["id"] for e in z.get("also_regions", [])]
        for rid in named:
            sx, sz = rr["regions"][rid]["seed"]
            cut = None
            for e in z.get("also_regions", []):
                if e["id"] == rid:
                    cut = e["cut"]
            cut = cut or z.get("cut")
            if cut:
                c = [q for q in spec["cuts"] if q["id"] == cut["id"]][0]
                v = sz if c["axis"] == "z" else sx
                if (cut["keep"] == "less") != (v < c["at"]):
                    continue           # the seed is on the far side of this zone's own cut
            if not any(b[0] <= sx <= b[2] and b[1] <= sz <= b[3] for b in boxes_of(z)):
                bad("%s names region %s but its seed (%d, %d) is not inside %s's boxes" % (zid, rid, sx, sz, zid))

    # 4. no live zone overlaps the gulch's built zone
    gz = gulch["zone"]["polygon"]
    for zid, z in live.items():
        hit = [b for b in boxes_of(z) if point_in(gz, (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)]
        if hit:
            bad("%s: %d boxes fall inside data/gulch_mine.json's built zone (first %s)" % (zid, len(hit), hit[0]))

    # 5. the places: arrival and exit inside their zone, turn-back outside it
    def inside(z, x, zz):
        """Half-open on the upper side, as box_cond() writes the predicate (max = x1 + 1). A teleport target is
        a block CENTRE, x + 0.5, so an inclusive integer test calls the box's own last block outside."""
        return any(b[0] <= x < b[2] + 1 and b[1] <= zz < b[3] + 1 for b in boxes_of(z))

    for zid, z in live.items():
        ax, _, az, _ = z["arrive"]
        tx, _, tz, _ = z["turn_back"]
        e = z["exit"]
        if not inside(z, ax, az):
            bad("%s: the arrival (%s, %s) is not inside the zone" % (zid, ax, az))
        if inside(z, tx, tz):
            bad("%s: the turn-back point (%s, %s) is INSIDE the zone, so it would loop" % (zid, tx, tz))
        if not inside(z, e[0], e[2]):
            bad("%s: the exit box is not inside the zone" % zid)

    # 6. the cuts are measured and span real ground
    for c in spec["cuts"]:
        if c.get("span") is None:
            bad("cut %s has no measured span: run trace" % c["id"])
            continue
        if c["across"] < 60:
            bad("cut %s spans only %d blocks: too narrow to be a rim-to-rim crossing" % (c["id"], c["across"]))
        lo, hi = c["span"]
        tx, tz = c["through"]
        v = tz if c["axis"] == "x" else tx
        if not lo <= v <= hi:
            bad("cut %s: its own through point is not on its span" % c["id"])

    # 7. every guard stands on its wall's span, if it has one
    cuts = {c["id"]: c for c in spec["cuts"]}
    for zid, z in live.items():
        w = z.get("wall")
        if not w or cuts[w].get("span") is None:
            continue
        gb = z["guard"].get("block")
        if not gb:
            bad("%s: the guard has no traced block" % zid)
            continue
        c = cuts[w]
        v = gb[1] if c["axis"] == "x" else gb[0]
        lo, hi = c["span"]
        if not lo - 24 <= v <= hi + 24:
            bad("%s: guard block %s is off the %s wall's span %s" % (zid, gb, w, c["span"]))

    # 8. RIFT_ZONES.md section 2a: no caught-count zone holds a story-required site
    cradle = rr["sited"]["hoopa_cradle"]["centre"]
    for zid, z in live.items():
        if (z.get("pass") or {}).get("kind") == "caught" and inside(z, cradle[0], cradle[1]):
            bad("%s gates on caught count and contains Hoopa's cradle %s (RIFT_ZONES.md 2a forbids it)" % (zid, cradle))
    z2 = live.get("z2")
    if z2 and not inside(z2, cradle[0], cradle[1]):
        bad("Hoopa's cradle %s is not in z2 (RIFT_ZONES.md 2a requires it)" % cradle)

    # 9. the badge flags a pass names exist in data/progression.json
    have = json.dumps(prog)
    for zid, z in live.items():
        for adv in (z.get("pass") or {}).get("advancements", []) or []:
            flag = adv.split("/")[-1]
            if ('"%s"' % flag) not in have:
                if z.get("needs_progression"):
                    owed("%s's pass names %s and data/progression.json has no %s. %s"
                         % (zid, adv, flag, z["needs_progression"]["change_node"]))
                else:
                    bad("%s's pass names %s, and %s is not in data/progression.json" % (zid, adv, flag))

    # 10. no wall block is a block a spawn condition names
    sb = ROOT / "data" / "spawn_blocks.json"
    if sb.is_file():
        named = json.dumps(load(sb))
        pal = spec["wall"]["palette"]
        blocks = set(pal["body"]) | set(pal["crest"]) | set(pal["glass"]) | set(spec["gatehouse"]["blocks"].values())
        for b in sorted(blocks):
            if b != "minecraft:barrier" and ('"%s"' % b) in named:
                bad("wall block %s is named by data/spawn_blocks.json" % b)

    # 11. what the data says it settles must still be true
    s = spec["settles"]
    if list(rr["sited"]["hoopa_cradle"]["centre"]) != [3357, 3306]:
        bad("data/rift_regions.json moved Hoopa's cradle; settles.hoopa_cradle is stale")
    if point_in(ext, 3297.5, 2603.5):
        bad("FACTION.md's (3297, 2603) is inside the Rift after all; settles.hoopa_cradle is wrong")
    if "rift_crisis_resolved" not in have:
        owed("the setter for rift_crisis_resolved: it is the finale's quest stage, story data this tool must "
             "not invent. Until it exists z5 is shut to everyone, which is closed, not open.")
    if s["registeel_region"]["answer"].startswith("the zone system does NOT") and z2:
        leg = load(ROOT / "data" / "legendaries.json")
        txt = json.dumps(leg)
        if '"gym7_cleared"' not in txt:
            bad("data/legendaries.json no longer gates Registeel on gym7_cleared; settles.registeel_region is stale")

    if P:
        return fail(P, OWED)
    if quiet:
        return 0 if not OWED else 1
    n = sum(len(z["boxes"]) for z in live.values())
    print("rift_zones report OK: %d live zones, %d boxes, %d superseded, %d cuts measured, %d disagreements recorded"
          % (len(live), n, len(spec["zones"]) - len(live), len(spec["cuts"]), len(spec["disagreements"])))
    for zid in sorted(live, key=lambda z: spec["zones"][z]["order"]):
        z = live[zid]
        p = z["pass"]
        k = p["kind"]
        v = p.get("threshold") or ", ".join(p.get("flags", []))
        print("  %-4s %-34s %-8s %-18s %5d boxes  guard %s at %s"
              % (zid, z["name"], k, v, len(z["boxes"]), z["guard"]["id"], z["guard"].get("block")))
    for c in spec["cuts"]:
        print("  wall %-14s closes %-3s: %4d columns on floor, %d on scarp (no wall), %d across"
              % (c["id"], c["closes"], c["columns"], c["on_scarp"], c["across"]))
    if OWED:
        print("rift_zones report: no problem, but %d OWED dependenc(ies); exit 1" % len(OWED), file=sys.stderr)
        for o in OWED:
            print("  OWED %s" % o, file=sys.stderr)
        return 1
    return 0


def fail(problems, owed=()):
    """2, not 1: a PROBLEM stops `build`, an OWED dependency does not. See cmd_report's docstring."""
    print("rift_zones report FAILED: %d problem(s), %d owed" % (len(problems), len(owed)), file=sys.stderr)
    for p in problems:
        print("  PROBLEM %s" % p, file=sys.stderr)
    for o in owed:
        print("  OWED %s" % o, file=sys.stderr)
    return 2


# ----------------------------------------------------------------- build

def text(s, **style):
    return json.dumps(dict({"text": s}, **style), ensure_ascii=False)


def box_cond(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    return {"condition": "minecraft:entity_properties", "entity": "this",
            "predicate": {"location": {"dimension": "minecraft:overworld", "position": {
                "x": {"min": x0, "max": x1 + 1}, "y": {"min": y0, "max": y1 + 1},
                "z": {"min": z0, "max": z1 + 1}}}}}


def adv(conds, reward):
    return {"criteria": {"here": {"trigger": "minecraft:location", "conditions": {"player": conds}}},
            "rewards": {"function": reward}}


def wall_columns(g, spec, cut):
    """[(x, z, crest_y)] for one cross-wall: the traced frontier's own columns, each to its own ground + rise.

    The line is data/rift_zones.json cuts[].line, the frontier the two zones share, already filtered to the
    columns that stand on walkable floor. Each column's crest is its OWN ground plus the rise, so the wall
    follows the ground it crosses instead of standing on one number; `floor_y` is the floor at the cut's
    surveyed `through` point and is the minimum, so a dip in the floor does not put a hole in the wall."""
    rise = spec["wall"]["rise_over_floor"]
    floor = cut["floor_y"]
    return [(x, z, max(g(x, z), floor) + rise) for x, z in cut["line"]]


def cmd_build(a):
    spec = load()
    rc = cmd_report(argparse.Namespace())
    if rc == 2:
        raise ZoneError("report found problems; nothing built")
    if rc:
        print("rift_zones build: going on despite the owed dependencies above. An advancement that does not "
              "exist yet never matches, so the zone it gates stays SHUT: that fails closed.", file=sys.stderr)
    g = ground_of(a.source_root)
    cuts = {c["id"]: c for c in spec["cuts"]}
    gh = spec["gatehouse"]
    ymin, ymax = spec["y"]
    ex = spec["exempt"]
    F = "%s:%s" % (NS, FOLDER)
    files, fn, index = {}, {}, []
    live = {z: r for z, r in spec["zones"].items() if not str(r.get("status", "")).startswith("SUPERSEDED")}

    load_lines = ["# one dummy objective per zone; never reset, never unset by this pack"]
    for zid, z in sorted(live.items(), key=lambda kv: kv[1]["order"]):
        obj = spec["pass"]["objective_prefix"] + zid
        load_lines.append("scoreboard objectives add %s %s" % (obj, spec["pass"]["criterion"]))
    fn["load"] = load_lines

    for zid, z in sorted(live.items(), key=lambda kv: kv[1]["order"]):
        obj = spec["pass"]["objective_prefix"] + zid
        boxes = [box_cond((b[0], ymin, b[1]), (b[2], ymax, b[3])) for b in z["boxes"]]
        files["data/%s/advancement/%s/%s_zone.json" % (NS, FOLDER, zid)] = adv(
            [{"condition": "minecraft:any_of", "terms": boxes}], "%s/%s/zone" % (F, zid))
        e = z["exit"]
        files["data/%s/advancement/%s/%s_exit.json" % (NS, FOLDER, zid)] = adv(
            [box_cond(e[:3], e[3:])], "%s/%s/exit" % (F, zid))

        ax, ay, az, ayaw = z["arrive"]
        tx, ty, tz, tyaw = z["turn_back"]
        p = z["pass"]
        short = ("the %s badge" % ordinal(p["threshold"])) if p["kind"] == "badges" else (
            "%d species caught" % p["threshold"] if p["kind"] == "caught" else "the Rift's crisis resolved")
        fn["%s/zone" % zid] = [
            "# %s's zone check (docs/mechanics/RIFT_ZONES.md section 4, data/rift_zones.json). The advancement tests" % zid,
            "# LOCATION ONLY; the pass is tested here, because minecraft:entity_scores does not match an unset score",
            "# and putting it in the advancement would fail open for every player who never met a guard.",
            "advancement revoke @s only %s:%s/%s_zone" % (NS, FOLDER, zid),
            "execute if entity %s unless score @s %s matches 1.. run function %s/%s/turn_back" % (ex, obj, F, zid)]
        fn["%s/turn_back" % zid] = [
            "# a bed or respawn anchor set inside the zone goes first, so a respawn cannot loop (RIFT_ZONES.md 4)",
            "execute if entity @s[gamemode=!creative] run spawnpoint @s %d %d %d" % (int(tx), int(ty), int(tz)),
            "# the mount first, then the player (UNPROVEN that Cobblemon riding survives this)",
            "execute on vehicle run tp @s %s %d %s" % (tx, ty, tz),
            "tp @s %s %d %s %s 0" % (tx, ty, tz, tyaw),
            "title @s actionbar %s" % text("Turned back: %s opens with %s." % (z["name"], short), color="gold")]
        fn["%s/exit" % zid] = [
            "# the way out, for anyone, pass or not",
            "advancement revoke @s only %s:%s/%s_exit" % (NS, FOLDER, zid),
            "tp @s %s %d %s %s 0" % (tx, ty, tz, tyaw)]
        fn["%s/grant" % zid] = [
            "# called by %s's dialogue once it has decided the player qualifies (Codex writes the dialogue)." % z["guard"]["id"],
            "scoreboard players set @s %s 1" % obj,
            "execute on vehicle run tp @s %s %d %s" % (ax, ay, az),
            "tp @s %s %d %s %s 0" % (ax, ay, az, ayaw),
            "title @s actionbar %s" % text("%s lets you through." % z["guard"]["id"], color="gray")]
        if p["kind"] == "badges":
            need = "".join(",advancements={%s=true}" % adv_ for adv_ in p["advancements"])
            fn["%s/qualify" % zid] = [
                "# the server checks the badges itself, so dialogue may call this instead of grant",
                "execute if entity @s[gamemode=!spectator%s] run function %s/%s/grant" % (need, F, zid),
                "execute unless entity @s[%s] run title @s actionbar %s"
                % (need[1:], text("%s is not satisfied: %s is needed." % (z["guard"]["id"], short), color="gold"))]
        elif p["kind"] == "flag":
            need = "".join(",advancements={%s=true}" % adv_ for adv_ in p["advancements"])
            fn["%s/qualify" % zid] = [
                "execute if entity @s[gamemode=!spectator%s] run function %s/%s/grant" % (need, F, zid),
                "execute unless entity @s[%s] run title @s actionbar %s"
                % (need[1:], text("%s is not satisfied: %s is needed." % (z["guard"]["id"], short), color="gold"))]
        else:
            fn["%s/qualify" % zid] = [
                "# no server-side qualify for a caught-count zone: no command or predicate reads species owned",
                "# (data/rift_zones.json zones.%s.qualify_why). Only %s's dialogue can test it." % (zid, z["guard"]["id"]),
                "say [rift_zones] %s must be granted by %s's dialogue, not by a command" % (zid, z["guard"]["id"])]

    # the walls and the gatehouse shells
    for zid, z in sorted(live.items(), key=lambda kv: kv[1]["order"]):
        w = z.get("wall")
        gb = z["guard"]["block"]
        if w:
            c = cuts[w]
            cols = wall_columns(g, spec, c)
            body = spec["wall"]["palette"]["body"]
            crest = spec["wall"]["palette"]["crest"]
            # the walkway through the wall is left out of the fill, so the gatehouse opens it
            keep = set()
            for d in range(-gh["walkway"] - 1, gh["walkway"] + 2):
                keep.add((gb[0] + d, gb[1]))
                keep.add((gb[0], gb[1] + d))
            lines = ["# the %s cross-wall (data/rift_zones.json cuts[%s]): %d columns on walkable floor, core %d,"
                     % (w, w, c["columns"], spec["wall"]["core"]),
                     "# each column to its own ground + %d. %d further frontier columns stand on scarp and carry no"
                     % (spec["wall"]["rise_over_floor"], c["on_scarp"]),
                     "# wall (RIFT_FRACTURE.md, 'the scarps are the barrier').",
                     "# Ground from tools/ground.py, never from a world (CLAUDE.md)."]
            for (x, z_, top) in cols:
                if (x, z_) in keep:
                    continue
                base = g(x, z_)
                lines.append("fill %d %d %d %d %d %d %s" % (x, base, z_, x, top - 1, z_, body[(x + z_) % len(body)]))
                lines.append("setblock %d %d %d %s" % (x, top, z_, crest[(x // 7 + z_ // 5) % len(crest)]))
            name = "wall_%s" % w
            fn[name] = lines
            index.append(name)
        # the gatehouse shell at the guard's block: every guard has one, walled zone or not. G2's stands at the
        # sculpted Victory Road descent, where the Rift's own rim is the barrier and no cross-wall is built.
        dx, dz = [-v for v in z["guard"]["outward"]]
        fy = z["guard"]["ground_y"] + 1
        sh = gh["blocks"]
        gl = ["# the %s gatehouse shell (RIFT_ZONES.md section 6): a one-wide roofed walkway, a two-high barrier"
              % z["guard"]["id"],
              "# behind the guard, and an armour stand where Codex's NPC will stand (data/rift_sculpt.json's policy)."]
        px, pz = (0, 1) if abs(dx) > abs(dz) else (1, 0)
        for t in range(-2, gh["exit_in"] + 2):
            cx = int(round(gb[0] + dx * t))
            cz = int(round(gb[1] + dz * t))
            gl.append("fill %d %d %d %d %d %d %s" % (cx - px, fy - 1, cz - pz, cx + px, fy - 1, cz + pz, sh["shell"]))
            gl.append("fill %d %d %d %d %d %d %s" % (cx - px, fy, cz - pz, cx - px, fy + 1, cz - pz, sh["shell"]))
            gl.append("fill %d %d %d %d %d %d %s" % (cx + px, fy, cz + pz, cx + px, fy + 1, cz + pz, sh["shell"]))
            gl.append("fill %d %d %d %d %d %d minecraft:air" % (cx, fy, cz, cx, fy + 1, cz))
            gl.append("setblock %d %d %d %s" % (cx, fy + 2, cz, sh["shell"]))
        bx = int(round(gb[0] + dx)), int(round(gb[1] + dz))
        gl.append("# the barrier directly behind the guard: this is what actually stops a player")
        gl.append("fill %d %d %d %d %d %d %s" % (bx[0], fy, bx[1], bx[0], fy + gh["barrier_height"] - 1, bx[1],
                                                 sh["barrier"]))
        gl.append("setblock %d %d %d %s" % (gb[0], fy + 2, gb[1], sh["lamp"]))
        gl.append("summon minecraft:armor_stand %d %d %d {Invulnerable:1b,NoGravity:1b,CustomNameVisible:1b,"
                  "CustomName:'%s',Tags:[\"cobblers_rift_guard\",\"%s\"]}"
                  % (gb[0], fy, gb[1], text("%s (placeholder)" % z["guard"]["id"]), z["guard"]["id"]))
        name = "gatehouse_%s" % zid
        fn[name] = gl
        index.append(name)

    out = PACKS / PACK
    for p in sorted(out.rglob("*")) if out.is_dir() else []:
        pass
    (out / "data" / NS / "function" / FOLDER).mkdir(parents=True, exist_ok=True)
    (out / "data" / NS / "advancement" / FOLDER).mkdir(parents=True, exist_ok=True)
    (out / "data" / "minecraft" / "tags" / "function").mkdir(parents=True, exist_ok=True)
    jdump({"pack": {"pack_format": 48, "description": "Cobblers: the Rift's zones (data/rift_zones.json)"}},
          out / "pack.mcmeta")
    for rel, obj in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        jdump(obj, p)
    for name, lines in fn.items():
        p = out / "data" / NS / "function" / FOLDER / (name + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    jdump({"values": ["%s/load" % F]}, out / "data" / "minecraft" / "tags" / "function" / "load.json")
    (out / "data" / NS / "function" / FOLDER / "index.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    print("wrote %s: %d advancements, %d functions, %d build functions in index.txt"
          % (out, len(files), len(fn), len(index)))
    return 0


def ordinal(n):
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
            6: "sixth", 7: "seventh", 8: "eighth"}.get(n, "%dth" % n)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trace", help="re-derive the boxes and spans into data/rift_zones.json")
    t.add_argument("--source-root")
    sub.add_parser("report", help="fail-closed audit of the data")
    b = sub.add_parser("build", help="emit build/datapacks/" + PACK)
    b.add_argument("--source-root")
    a = p.parse_args(argv)
    try:
        rc = {"trace": cmd_trace, "report": cmd_report, "build": cmd_build}[a.cmd](a)
        return 1 if rc else 0
    except ZoneError as e:
        print("rift_zones: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
