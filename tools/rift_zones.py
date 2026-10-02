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
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

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


def zone_axis(mask, X0, Z0, at):
    """The gate's in/out axis, the nearest column across its zone's boundary, and which side it stands on.

    The guard stands where the data sites it -- data/rift_sculpt.json's own entrances, or
    docs/mechanics/RIFT_ZONES.md's survey -- and is NOT snapped to the zone's edge. So the direction and the
    turn-back distance are measured instead, and there are two measured cases:

      side "inside"  -- the guard stands in its own zone (G1, G4, G5 and both of z2's posts). The axis
                        points at the nearest column OUTSIDE the zone, which is where an unqualified
                        player is put. Two of those sites are a long way in -- z2's rim_post_descent is 62
                        blocks and wilds_slip 153 -- and moving an authored guard to suit a coarse hull
                        would be the tool overruling the data.
      side "outside" -- the guard stands IN FRONT of its zone, which is what a gate on a road has to do.
                        The axis points at the nearest column INSIDE the zone. The owner, 2026-10-01, on
                        G2: "the gatehouse moves to the trailhead. A gate 300 blocks inside the basin is
                        passed before a player reaches what gates it." An outside-sited guard is met before
                        the zone's own location test can bounce the player, which is the whole point of
                        having a guard rather than a silent teleport.

    Returns ((x, z), (outward_dx, outward_dz), distance, side): the column is the nearest one across the
    boundary, and `outward` always points AWAY from the zone whichever side the guard is on."""
    H, W = mask.shape
    ax, az = at
    ix, iz = ax - X0, az - Z0
    if not (0 <= ix < W and 0 <= iz < H):
        raise ZoneError("the guard site (%d, %d) is outside the traced frame" % (ax, az))
    side = "inside" if mask[iz, ix] else "outside"
    zz, xx = np.nonzero(~mask if side == "inside" else mask)
    if len(zz) == 0:
        raise ZoneError("the zone has no column on the far side of the guard site; it covers the whole frame "
                        "or none of it")
    d = (xx - ix) ** 2 + (zz - iz) ** 2
    i = int(np.argmin(d))
    ex, ez = int(xx[i]) + X0, int(zz[i]) + Z0
    dx, dz = ex - ax, ez - az
    n = math.hypot(dx, dz)
    if n < 1e-6:
        raise ZoneError("the axis at the guard site is degenerate")
    dx, dz = dx / n, dz / n
    if side == "outside":                      # the near column is INSIDE, so that direction is inward
        dx, dz = -dx, -dz
    return (ex, ez), (dx, dz), n, side


def route_axis(route_id, at, span=8):
    """The in/out axis of a gate that stands on a route: the walked line's own heading there.

    A gate across a road must lie along the road, or its walkway runs off the surface and its knock box
    sits beside it rather than in front of the guard. The nearest-column axis zone_axis() measures is the
    right one for a gate in a wall and the wrong one for a gate on a road: at G2's trailhead the two are 39
    degrees apart (measured, and written into the record's axis_why), which would stand the gatehouse
    diagonally across Victory Road.

    The line is data/route_paths.json's dense walked line -- the same file tools/rift_skin.py lays this
    entrance's ramp and trailhead marker on (its route_lip_crossing), so gate, ramp and marker share one
    axis. The heading is averaged over `span` points either way so a single 8-connected step does not set
    it. Fails closed if the guard block is not ON the line: a gate beside a road is not a gate.

    Returns (outward_dx, outward_dz) -- away from the zone, which on a route means back the way the player
    came -- plus the index and the walked distance, so the record can say where on the route it stands."""
    paths = load(ROOT / "data" / "route_paths.json")["paths"]
    pts = paths.get(route_id)
    if not pts:
        raise ZoneError("data/route_paths.json holds no walked line for route %s; a gate cannot take its "
                        "axis from a route that is not there" % route_id)
    pts = [(int(p[0]), int(p[1])) for p in pts]
    ax, az = at
    i = min(range(len(pts)), key=lambda k: (pts[k][0] - ax) ** 2 + (pts[k][1] - az) ** 2)
    off = math.dist(pts[i], (ax, az))
    if off > 0.5:
        raise ZoneError("the guard site (%d, %d) is %.1f blocks off route %s's walked line (nearest point "
                        "%s). A gate takes its axis from the road it closes, so it has to stand on it."
                        % (ax, az, off, route_id, pts[i]))
    a = pts[max(0, i - span)]
    b = pts[min(len(pts) - 1, i + span)]
    dx, dz = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dz)
    if n < 1e-6:
        raise ZoneError("route %s doubles back on itself at (%d, %d); no heading" % (route_id, ax, az))
    walked = sum(math.dist(pts[k - 1], pts[k]) for k in range(1, i + 1))
    return (-dx / n, -dz / n), i, walked


def yaw_towards(dx, dz):
    """Minecraft yaw looking along (dx, dz): 0 = +z, 90 = -x, 180 = -z, -90 = +x."""
    return round(math.degrees(math.atan2(-dx, dz)), 1)


# ----------------------------------------------------------------- the traced regions

def resolve_source_root(source_root):
    """--source-root, else COBBLERS_SOURCE_ROOT, the way every other tool here resolves it.

    Added 2026-09-30: `trace` with neither crashed inside pathlib with
    "TypeError: expected str, bytes or os.PathLike object, not NoneType", which says nothing about what
    is missing. tools/terrain.py raises TerrainUnavailable with the variable's name for exactly this."""
    import os
    r = source_root or env_source_root()
    if not r:
        raise ZoneError("source_root is unset: pass --source-root or set COBBLERS_SOURCE_ROOT")
    return r


def annotated(spec, source_root):
    from PIL import Image
    p = Path(resolve_source_root(source_root)) / spec["source"]["file"]
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
    # reaches z5388 where the traced regions stop at z5079, and the Victory Road descent post (3738, 5082)
    # is in that tail. Since 2026-10-01 G2 itself stands further out again, at the trailhead (3548, 5322),
    # which is OUTSIDE the extent hull altogether -- so the guard sites have to be padded into the frame
    # here, not merely contained by the regions. The pad below is what makes that work.
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

    # the guards, their posts, and the places round them
    gh = spec["gatehouse"]

    def survey(zid, at, bxs, mask, on_route=None):
        """Every measured field one gate needs: the guard's block, the walkway's places and its knock box.

        Used for a zone's own guard and for each extra post (data/rift_zones.json zones.z2.posts). The places
        are measured against the RASTERISED BOXES, not the mask, because the boxes are what the advancement
        tests. A guard standing a few blocks from the edge can otherwise have its arrival land in an 8-block
        cell that did not make the majority cut, and the player would arrive already outside.

        `on_route` names a route in data/route_paths.json whose walked line sets the axis instead of the
        nearest column across the boundary: see route_axis(). The mask's own axis is still measured and the
        two must agree on which way is out, so a route that runs the other way past its zone fails closed
        rather than siting the gatehouse backwards."""
        bx, bz = at
        (ox, oz), (dx, dz), dist, side = zone_axis(mask, X0, Z0, (bx, bz))
        rinfo = None
        if on_route:
            (rdx, rdz), ri, rwalked = route_axis(on_route, (bx, bz))
            if rdx * dx + rdz * dz <= 0:
                raise ZoneError("%s: route %s heads the wrong way past its zone at (%d, %d). The walked line's "
                                "outward is (%.2f, %.2f) and the mask's is (%.2f, %.2f); a gate sited on that "
                                "axis would face the player into the zone it is meant to close."
                                % (zid, on_route, bx, bz, rdx, rdz, dx, dz))
            rinfo = (on_route, ri, rwalked, (dx, dz))
            dx, dz = rdx, rdz
        inx, inz = -dx, -dz

        def inb(x, zz):
            return any(q[0] <= x <= q[2] and q[1] <= zz <= q[3] for q in bxs)

        def walk(px, pz, ux, uz, want, limit=96):
            for n in range(0, limit + 1):
                qx, qz = int(round(px + ux * n)), int(round(pz + uz * n))
                if inb(qx, qz) == want:
                    return qx, qz, n
            raise ZoneError("%s: no column %s the boxes within %d of the guard along (%.2f, %.2f)"
                            % (zid, "inside" if want else "outside", limit, ux, uz))

        # how far along the axis the zone's BOXES begin. 0 at G1 and G4, 11 at G5 (whose block is in the
        # traced mask but not in the 8-grid majority raster), and for an outside-sited gate the stretch an
        # unqualified player still walks before the location test can bounce them. That stretch is why G2
        # moved out here: inside it, nothing ever met them.
        zx, zz_, zn = walk(bx, bz, inx, inz, True, 600)
        # EVERY gate, inside-sited or outside-sited, anchors its places on the GUARD'S OWN BLOCK, because
        # that is what cmd_build anchors the gatehouse on: walkway_path() runs from t = -knock_out to
        # t = exit_in + 1 measured from this block, and both arrive_in and exit_in lie inside that span.
        #
        # An inside-sited gate used to anchor on `zone_begins_at`, the first column inside the 8-grid BOXES,
        # so that its arrival could not land in a cell that missed the majority cut. At G5 that column is 11
        # blocks along the axis, which put the arrival 14 blocks inside the guard and the exit box 16 -- both
        # on open ground 8 blocks PAST the walkway's inner mouth, and neither on the gatehouse at all
        # (data/rift_zones.json measured_defects[gate_places_are_not_on_the_gatehouse_floor], second_part).
        # A minecraft:location box over ground a player's feet never occupy never fires, so that trade was
        # the wrong way round: the 8-grid raster not reaching the guard's own corner is a rasterisation
        # fact, not a place to teleport to. `zone_begins_at` and `zone_begins_in` are still measured, still
        # recorded, and still what cmd_report's boxes check reads.
        #
        # The columns are taken against the ROUNDED outward, which is the figure the record carries and the
        # one cmd_build reads back, so the places cannot round onto a different column than the shell does.
        ow = [round(dx, 4), round(dz, 4)]
        iw = (-ow[0], -ow[1])
        sx, sz = bx, bz
        ax, az = int(round(sx + iw[0] * gh["arrive_in"])), int(round(sz + iw[1] * gh["arrive_in"]))
        ex, ez = int(round(sx + iw[0] * gh["exit_in"])), int(round(sz + iw[1] * gh["exit_in"]))
        # fail closed if either place is not a column cmd_build will actually lay walkway on. This asks the
        # shell's own geometry, deliberately: these two places exist in order to be stood on IN the walkway,
        # and an advancement box beside it is an advancement that never fires. The INDEPENDENT measure of the
        # same property is tests/test_rift_zones.py place_problems(), which reads the emitted commands.
        wpath = set(walkway_path([bx, bz], ow, gh))
        for what, col in (("arrival", (ax, az)), ("exit box", (ex, ez))):
            if col not in wpath:
                raise ZoneError("%s: the %s column %s is not on the walkway cmd_build lays from (%d, %d) "
                                "along (%.4f, %.4f), which runs %s to %s. A minecraft:location box off the "
                                "walkway is one a player's feet never occupy."
                                % (zid, what, col, bx, bz, iw[0], iw[1],
                                   min(wpath), max(wpath)))
        # outward may be a long way: z2's two posts stand at sculpted rim entrances well inside the Rift's
        # coarse extent hull, so the first column outside the BOXES can be over a hundred blocks off. 600 is
        # under the Rift's own width, so a failure here means the geometry is wrong rather than the limit small.
        qx, qz, _ = walk(bx, bz, dx, dz, False, 600)
        tx, tz = int(round(qx + dx * gh["turn_back_out"])), int(round(qz + dz * gh["turn_back_out"]))
        if inb(tx, tz):
            tx, tz = qx, qz
        # THE WALKWAY'S OWN FLOOR LEVEL, and the feet level of every place that stands on the gatehouse.
        # cmd_build lays the shell flat: the floor at fy - 1 and the air at fy and fy + 1 for EVERY column of
        # the walkway, from the guard's own ground and nothing else. So the arrival, the exit box and the
        # knock box all take their y from here and not from tools/ground.py at their own column. Taking it
        # per-column is the defect this fixes: where the ground slopes along the walkway the two disagree,
        # and at the two sloping posts the boxes stood 1 and 2 blocks off the floor the player walks on
        # (data/rift_zones.json measured_defects[gate_places_are_not_on_the_gatehouse_floor]). The turn-back
        # is the one place that keeps its own column's ground: it stands turn_back_out = 8 blocks outward,
        # well past the gatehouse's outer mouth, on open terrain the shell never touches.
        fy = int(g(bx, bz)) + 1
        # the knock box: the walkway blocks OUTSIDE the guard, under the gatehouse's own roof, where a player
        # stands face to face with it. Its y is the walkway's, which the shell lays flat at the guard's own feet
        # level for every column of the gatehouse, so it does not follow the ground either side.
        kc = [(int(round(bx + dx * t)), int(round(bz + dz * t))) for t in range(1, gh["knock_out"] + 1)]
        knock = [min(p[0] for p in kc), fy, min(p[1] for p in kc),
                 max(p[0] for p in kc), fy + 1, max(p[1] for p in kc)]
        out = {
            "block": [bx, bz], "ground_y": int(g(bx, bz)),
            "side": side,
            "inward": [round(inx, 4), round(inz, 4)], "outward": ow,
            "edge_at": [ox, oz], "edge_distance": int(round(dist)),
            "zone_begins_at": [zx, zz_], "zone_begins_in": zn,
            "arrive": [ax + 0.5, fy, az + 0.5, yaw_towards(inx, inz)],
            "turn_back": [tx + 0.5, int(g(tx, tz)) + 1, tz + 0.5, yaw_towards(dx, dz)],
            "exit": [ex, fy, ez, ex, fy + 1, ez],
            "knock": knock,
        }
        if side == "inside":
            # unchanged fields for every gate that stands in its own zone, so their records do not churn
            out["outside_at"] = [ox, oz]
            out["outside_distance"] = int(round(dist))
            out["block_why"] = ("the guard stands on its surveyed site, unmoved, inside the zone it gates. The "
                                "outward direction and the distance to the nearest column outside the zone (%d "
                                "blocks) are measured from the traced mask." % round(dist))
            out["places_why"] = ("measured from the GUARD'S OWN BLOCK along the axis, every place that stands on "
                                 "the gatehouse at the walkway's own flat floor level y%d (the guard's ground + 1, "
                                 "which is what cmd_build lays for every column of the shell): the arrival %d "
                                 "blocks inside facing in; the exit box %d inside; the knock box the %d walkway "
                                 "blocks outside the guard, which is what calls the zone's qualify. All three are "
                                 "columns of walkway_path(), checked. Only the turn-back takes its y from "
                                 "tools/ground.py at its own column, because it stands %d blocks out on open "
                                 "terrain, PAST the nearest outside column (%d, %d) and facing away, so it is "
                                 "outside the zone however far inside the guard stands."
                                 % (fy, gh["arrive_in"], gh["exit_in"], gh["knock_out"],
                                    gh["turn_back_out"], ox, oz))
        else:
            out["inside_at"] = [ox, oz]
            out["inside_distance"] = int(round(dist))
            out["block_why"] = ("the guard stands on its surveyed site, unmoved, and that site is OUTSIDE the "
                                "zone it gates: the nearest column of the zone is (%d, %d), %d blocks away, and "
                                "the zone's own boxes begin %d blocks along the axis at (%d, %d). That stretch is "
                                "the point: a player walking in meets the gate before the zone's location test "
                                "can turn them back." % (ox, oz, round(dist), zn, zx, zz_))
            out["places_why"] = ("measured from the guard's own block along the axis, every place that stands on "
                                 "the gatehouse at the walkway's own flat floor level y%d (the guard's ground + 1, "
                                 "which is what cmd_build lays for every column of the shell): the arrival %d "
                                 "blocks past the barrier facing in; the exit box %d in on the walkway; the knock "
                                 "box the %d walkway blocks outside the guard, which is what calls the zone's "
                                 "qualify. All three are columns of walkway_path(), checked. Only the turn-back "
                                 "takes its y from tools/ground.py at its own column: it stands %d blocks outward "
                                 "on open terrain, already outside the zone, so an unqualified player is put back "
                                 "on the approach they walked up rather than teleported across the basin."
                                 % (fy, gh["arrive_in"], gh["exit_in"], gh["knock_out"], gh["turn_back_out"]))
        if rinfo:
            rid, ri, rwalked, maskdir = rinfo
            out["on_route"] = rid
            out["on_route_at"] = [round(rwalked, 2), ri]
            out["axis_why"] = ("the axis is route %s's own heading on data/route_paths.json's walked line at "
                               "point %d, %.0f blocks along it, averaged over 8 points either way: a gate across "
                               "a road lies along the road. The traced mask's own axis here is (%.4f, %.4f), %.0f "
                               "degrees off, which would stand the gatehouse diagonally across it; it is still "
                               "measured and still has to agree on which way is out (tools/rift_zones.py "
                               "survey)." % (rid, ri, rwalked, maskdir[0], maskdir[1],
                                             abs(math.degrees(math.atan2(maskdir[1], maskdir[0])
                                                              - math.atan2(dz, dx)))))
        return out

    for zid in order:
        z = spec["zones"][zid]
        if not z.get("guard"):
            continue
        bxs = [tuple(b) for b in z["boxes"]]
        s = survey(zid, z["guard"]["at"], bxs, masks[zid], z["guard"].get("on_route"))
        # the walkway's places belong to the zone, everything else to the guard record. Which keys survey
        # returns depends on the side the guard stands on, so the split is by name and not by a fixed list:
        # a gate outside its zone has inside_at where one inside it has outside_at.
        zone_keys = ("arrive", "turn_back", "exit", "knock", "places_why")
        for k in ("outside_at", "outside_distance", "inside_at", "inside_distance", "axis_why"):
            z["guard"].pop(k, None)
        for k, v in s.items():
            (z if k in zone_keys else z["guard"])[k] = v
        for post in z.get("posts", []):
            ps = survey("%s/%s" % (zid, post["id"]), post["at"], bxs, masks[zid], post.get("on_route"))
            post.update(ps)
    spec["status"] =("traced 2026-09-30 from %s at outline threshold %d; boxes and spans are measured, nothing is "
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
        for k in ("arrive", "turn_back", "exit", "knock"):
            if z.get(k) is None:
                bad("%s has no %s: run `python tools/rift_zones.py trace --source-root <root>`" % (zid, k))
        if not z.get("pass"):
            bad("%s has no pass" % zid)
        if not z.get("guard"):
            bad("%s has no guard" % zid)
        for po in z.get("posts", []):
            for k in ("block", "ground_y", "outward", "arrive", "turn_back", "exit", "knock"):
                if po.get(k) is None:
                    bad("%s post %s has no %s: run trace" % (zid, po["id"], k))
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
        for gname, gid, gd, arr, tb, eb, knock in gates_of(zid, z):
            ax, _, az, _ = arr
            tx, _, tz, _ = tb
            q = gd["block"]
            ow = gd["outward"]
            # the side-agnostic rule, which is what these places are FOR: the arrival and the exit box are on
            # the gatehouse's INWARD side of the guard, and the turn-back is on its outward side. The dot
            # product against the measured outward axis says so for any heading, diagonal included.
            for what, px, pz_, want_in in (("arrival", ax, az, True), ("exit box", eb[0], eb[2], True),
                                           ("turn-back point", tx, tz, False)):
                dot = (px - q[0]) * ow[0] + (pz_ - q[1]) * ow[1]
                if want_in and dot >= 0:
                    bad("%s (%s): the %s (%s, %s) is not on the inward side of the guard's block %s along the "
                        "measured axis %s; a player let through would be put back outside the barrier"
                        % (gname, gid, what, px, pz_, q, ow))
                if not want_in and dot <= 0:
                    bad("%s (%s): the %s (%s, %s) is not on the outward side of the guard's block %s along the "
                        "measured axis %s" % (gname, gid, what, px, pz_, q, ow))
            if inside(z, tx, tz):
                bad("%s (%s): the turn-back point (%s, %s) is INSIDE the zone, so it would loop"
                    % (gname, gid, tx, tz))
            # a gate that stands IN its zone has no excuse for an arrival or an exit box outside it: the
            # walkway is a few blocks long and the zone starts at the guard's feet. A gate that stands in
            # FRONT of its zone (gd["side"] == "outside", G2 since 2026-10-01) has both of them on the
            # approach by construction -- the zone begins gd["zone_begins_in"] blocks further along -- so
            # that pair of checks would be asking the geometry to be what the move deliberately changed.
            # 5a. the arrival and the exit box are columns of the gate's OWN walkway, at the walkway's own
            # flat floor level -- the guard's ground + 1, which is what cmd_build lays for every column of
            # the shell. This is the pair of properties measured_defects[gate_places_are_not_on_the_
            # gatehouse_floor] failed: a minecraft:location box over ground the player's feet never occupy
            # NEVER FIRES, so a box 1 block above the walkway's air, 2 blocks under its floor, or 8 blocks
            # past its inner mouth is a door that cannot be opened. Checked here against the walkway's own
            # geometry; measured independently off the emitted commands by tests/test_rift_zones.py.
            wpath = set(walkway_path(q, ow, spec["gatehouse"]))
            wfy = gd["ground_y"] + 1
            # the arrival is a teleport target, so its x and z are block CENTRES; the exit box is a block box
            acol = (int(arr[0] - 0.5), int(arr[2] - 0.5))
            for what, col in (("arrival", acol), ("exit box", (eb[0], eb[2]))):
                if col not in wpath:
                    bad("%s (%s): the %s column %s is not on its own gatehouse's walkway, which runs %s to "
                        "%s (%d columns). A location box off the walkway never fires."
                        % (gname, gid, what, col, min(wpath), max(wpath), len(wpath)))
            if int(arr[1]) != wfy:
                bad("%s (%s): the arrival is at y%s and the gatehouse's walkway floor is y%d"
                    % (gname, gid, arr[1], wfy))
            if eb[1] != wfy or eb[4] != wfy + 1:
                bad("%s (%s): the exit box spans y%d..y%d; the walkway floor is y%d and a player is two "
                    "blocks tall" % (gname, gid, eb[1], eb[4], wfy))
            if gd.get("side", "inside") == "inside":
                # The 8-grid raster need not reach the guard's own corner. At G5 the first column inside the
                # BOXES is zone_begins_in = 11 blocks along the axis -- further than the whole walkway is
                # long -- so demanding the arrival inside the boxes was demanding it OFF the gatehouse, and
                # that is how it came to stand 14 blocks in on open ground. A place on the gate's own
                # walkway satisfies this check; a place neither in the boxes nor on the walkway does not.
                if not inside(z, ax, az) and acol not in wpath:
                    bad("%s (%s): the arrival (%s, %s) is neither inside the zone nor on the gatehouse's "
                        "walkway" % (gname, gid, ax, az))
                if not inside(z, eb[0], eb[2]) and (eb[0], eb[2]) not in wpath:
                    bad("%s (%s): the exit box is neither inside the zone nor on the gatehouse's walkway"
                        % (gname, gid))
            else:
                if inside(z, q[0], q[1]):
                    bad("%s (%s): its record says side 'outside' and its block %s is inside the zone's boxes"
                        % (gname, gid, q))
            # 5b. the knock box: what calls qualify. It must be the walkway OUTSIDE the guard -- beside its
            # block, never on it, and never holding the arrival, which would put a granted player back in the
            # box that grants and loop. tools/reapply.py held the whole pack because nothing called qualify;
            # these are the checks that keep that from coming back silently.
            q = gd["block"]
            far = max(abs(knock[0] - q[0]), abs(knock[2] - q[1]), abs(knock[3] - q[0]), abs(knock[5] - q[1]))
            if far > spec["gatehouse"]["knock_out"]:
                bad("%s (%s): the knock box %s is %d blocks from the guard's block %s, past knock_out %d"
                    % (gname, gid, knock, far, q, spec["gatehouse"]["knock_out"]))
            if knock[0] <= q[0] <= knock[3] and knock[2] <= q[1] <= knock[5]:
                bad("%s (%s): the knock box %s covers the guard's own block %s" % (gname, gid, knock, q))
            if knock[0] <= ax < knock[3] + 1 and knock[2] <= az < knock[5] + 1:
                bad("%s (%s): the arrival (%s, %s) is inside the knock box, which would loop"
                    % (gname, gid, ax, az))
            if knock[4] - knock[1] != 1:
                bad("%s (%s): the knock box is %d blocks high, not 2 (a player's own height)"
                    % (gname, gid, knock[4] - knock[1] + 1))

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

    # 8b. EVERY sculpted way into a live zone is staffed by a guard that can grant that zone's pass.
    #     data/rift_sculpt.json cuts five descents through the Rift's rim and names a guard for each. Three of
    #     them lead into z2 and only one was staffed, so a player with eight badges who walked in at the other
    #     two was turned back by the zone check with no guard there to earn the pass from (RIFT_ZONES_BUILD.md
    #     'Open for the owner' item 1). A way in that no guard can open is a wall with no door; either staff it
    #     or do not cut it.
    sculpt = ROOT / "data" / "rift_sculpt.json"
    if sculpt.is_file():
        for e in load(sculpt).get("entrances", []):
            ex_, ez_ = e["near"]
            for zid, z in live.items():
                if not inside(z, ex_, ez_):
                    continue
                sited = [(g_, gd["block"]) for _n, g_, gd, _a, _t, _eb, _k in gates_of(zid, z)]
                if not any(max(abs(b[0] - ex_), abs(b[1] - ez_)) <= 8 for _g, b in sited):
                    bad("data/rift_sculpt.json cuts %s at (%d, %d) into %s and no guard stands within 8 blocks "
                        "of it (%s has %s). An unstaffed way in is a way nobody can ever pass."
                        % (e["id"], ex_, ez_, zid, zid, ", ".join("%s at %s" % (g_, b) for g_, b in sited)))

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
    # 9b. a caught-count zone's knock box calls a qualify that can only refuse: no command or predicate reads
    #     species owned (docs/research/CAUGHT_COUNT_AND_NPC_GUARDS.md; the VERIFIED custom stat counts BALL
    #     CAPTURES, not species). Its guard's dialogue must call <zone>/grant itself. Owed, not a problem: the
    #     zone is shut until it exists, which is closed, not open.
    for zid, z in sorted(live.items()):
        if (z.get("pass") or {}).get("kind") == "caught":
            owed("%s's grant: %s's dialogue must read %s and call cobblers:rift_zones/%s/grant. No command "
                 "reads species owned, so %s/qualify can only refuse and %s stays shut until Codex writes the "
                 "dialogue (docs/HANDOVER_CODEX.md item 23)."
                 % (zid, z["guard"]["id"], (z["pass"].get("molang") or "the Pokedex"), zid, zid, zid))
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
        for _n, gid, gd, _a, _t, _e, knock in gates_of(zid, z)[1:]:
            print("       + post %-22s %s at %s" % (_n.split("_", 1)[1], gid, gd.get("block")))
        for _n, gid, _gd, _a, _t, _e, knock in gates_of(zid, z):
            print("       knock %-40s -> %s/qualify" % (knock, _n.replace("_", "/", 1) if _n != zid else zid))
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


def gates_of(zid, z):
    """Every gate into one zone: its own guard first, then each staffed post.

    A post is a second (or third) guarded way into the SAME zone, granting the SAME pass on the SAME test,
    with its own walkway, knock box, arrival, exit and turn-back point. data/rift_zones.json zones.z2.posts
    exists because data/rift_sculpt.json cuts three ways down into Z2 and only one of them was staffed.
    Returns [(advancement name, the guard's name, the record, arrive, turn_back, exit, knock)]."""
    out = [(zid, z["guard"]["id"], z["guard"], z["arrive"], z["turn_back"], z["exit"], z["knock"])]
    for po in z.get("posts", []):
        out.append(("%s_%s" % (zid, po["id"]), po["guard_id"], po,
                    po["arrive"], po["turn_back"], po["exit"], po["knock"]))
    return out


def sel_box(b):
    """The selector arguments for a [x0, y0, z0, x1, y1, z1] block box: dx/dy/dz are SPANS, so a one-block
    column is dx=0, and the volume test covers whole blocks x0..x1."""
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (b[0], b[1], b[2], b[3] - b[0], b[4] - b[1], b[5] - b[2])


def wall_columns(g, spec, cut):
    """[(x, z, crest_y)] for one cross-wall: the traced frontier's own columns, each to its own ground + rise.

    The line is data/rift_zones.json cuts[].line, the frontier the two zones share, already filtered to the
    columns that stand on walkable floor. Each column's crest is its OWN ground plus the rise, so the wall
    follows the ground it crosses instead of standing on one number; `floor_y` is the floor at the cut's
    surveyed `through` point and is the minimum, so a dip in the floor does not put a hole in the wall."""
    rise = spec["wall"]["rise_over_floor"]
    floor = cut["floor_y"]
    return [(x, z, max(g(x, z), floor) + rise) for x, z in cut["line"]]


# ------------------------------------------- the walkway, and the measure of whether it can be walked
#
# These are deliberately two halves that do NOT share a derivation. walkway_path() and walkway_shell()
# DECIDE the shape; simulate_function(), standable_cells() and walk_pieces() MEASURE the emitted
# .mcfunction text and know nothing about either. The measuring half is what caught
# data/rift_zones.json measured_defects[gatehouse_walkway_is_not_continuous], and it would have caught it
# just as well had the shape been drawn by hand, because it reads the commands and not the geometry.

PASSABLE = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}


def walkway_path(block, outward, gh):
    """One gatehouse's walkway columns in order, outer mouth first, every step 4-CONNECTED to the last.

    THE BUG THIS FIXES (data/rift_zones.json measured_defects). The walkway's centre is the surveyed axis
    sampled at whole blocks, `round(block + inward * t)`. On any axis not aligned to x or z that sequence
    steps DIAGONALLY every few blocks -- (3548, 5323) to (3547, 5324) at G2 -- and two blocks that meet only
    at a corner are two blocks a player cannot walk between. The old shell emitted those centres as the
    walkway and walled the two columns perpendicular to the DOMINANT axis, which put obsidian on both of the
    corner's orthogonal joins, so every sideways shift sealed itself.

    So a diagonal step gets the column that joins its two ends, and the walkway stays ONE COLUMN WIDE: the
    corner makes an L, not a 2x2, and the check below fails closed if a 2x2 ever appears. A corridor widened
    until the diagonals stopped mattering would pass a flood fill and still be the wrong shape (the owner,
    2026-10-01).

    The joining column is taken on the axis the heading leans on, so the walkway stays on the surveyed line
    rather than bulging off it. Returns [(x, z)] from t = -knock_out (the outer mouth, open to the approach)
    to t = exit_in + 1 (the inner mouth)."""
    dx, dz = -outward[0], -outward[1]            # inward: t grows towards the zone
    centres = []
    for t in range(-gh["knock_out"], gh["exit_in"] + 2):
        c = (int(round(block[0] + dx * t)), int(round(block[1] + dz * t)))
        if not centres or c != centres[-1]:
            centres.append(c)                    # a near-diagonal axis rounds twice onto one column
    if len(centres) < 3:
        raise ZoneError("the walkway at %s is %d columns long; a gatehouse needs an outside, a barrier and "
                        "an inside" % (block, len(centres)))
    path = [centres[0]]
    for c in centres[1:]:
        ax, az = path[-1]
        sx, sz = c[0] - ax, c[1] - az
        if abs(sx) > 1 or abs(sz) > 1:
            raise ZoneError("the walkway at %s jumps %s from %s to %s; the axis is not a unit vector"
                            % (block, (sx, sz), (ax, az), c))
        if sx and sz:
            path.append((ax + sx, az) if abs(dx) >= abs(dz) else (ax, az + sz))
        path.append(c)
    on = set(path)
    for (x, z) in path:
        if (x + 1, z) in on and (x, z + 1) in on and (x + 1, z + 1) in on:
            raise ZoneError("the walkway at %s is two columns wide at (%d, %d): that is a widening, not a "
                            "corner, and a widened corridor passes a flood fill while being the wrong shape"
                            % (block, x, z))
    return path


def walkway_shell(path):
    """The columns that wall one walkway in: every 4-neighbour of it that is not walkway and not a mouth.

    Laid as the COMPLEMENT of the walked set rather than as a perpendicular pair per step. That is what makes
    it safe at a corner: the old per-step pair was computed from one step's own direction, so the pair of the
    step after a bend landed on the very column the bend needed, and one step's wall could overwrite the
    next step's walkway. A complement cannot seal the walkway, because the walkway is what it is the
    complement of.

    Four-neighbours and not eight: the outer diagonal of a bend is left open on purpose, because a player
    cannot walk through a corner either, which is the whole premise of walkway_path(). The two mouths -- one
    column beyond each end, continuing that end's own heading -- are left open, because they are the door."""
    on = set(path)
    mouths = {(2 * b[0] - a[0], 2 * b[1] - a[1]) for a, b in ((path[1], path[0]), (path[-2], path[-1]))}
    walls = set()
    for (x, z) in path:
        for n in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if n not in on and n not in mouths:
                walls.add(n)
    return sorted(walls, key=lambda p: (p[1], p[0]))


def x_runs(cells):
    """[(x0, x1, z)] -- cells merged into runs of consecutive x, so a floor is fills and not setblocks."""
    out = []
    for z in sorted({c[1] for c in cells}):
        xs = sorted(c[0] for c in cells if c[1] == z)
        a = prev = xs[0]
        for x in xs[1:]:
            if x != prev + 1:
                out.append((a, prev, z))
                a = x
            prev = x
        out.append((a, prev, z))
    return out


def simulate_function(lines):
    """{(x, y, z): block id} from an emitted .mcfunction's own fill/setblock lines, applied in order.

    THE MEASURING HALF. It reads the commands a gatehouse function actually contains and takes nothing from
    the geometry that wrote them; everything else (forceload, summon, execute, comments) is ignored. Only
    literal coordinates are understood, which is all these functions use -- a relative or selector coordinate
    raises rather than being silently skipped and counted as open ground."""
    world = {}
    for raw in lines:
        ln = raw.strip()
        if not ln or ln.startswith("#"):
            continue
        t = ln.split()
        if t[0] not in ("fill", "setblock"):
            continue
        n = 6 if t[0] == "fill" else 3
        for c in t[1:1 + n]:
            if not __import__("re").fullmatch(r"-?\d+", c):
                raise ZoneError("%s uses the non-literal coordinate %r; this measure reads literals only"
                                % (t[0], c))
        v = [int(c) for c in t[1:1 + n]]
        b = t[1 + n].split("[")[0].split("{")[0]
        if t[0] == "setblock":
            world[(v[0], v[1], v[2])] = b
        else:
            for x in range(min(v[0], v[3]), max(v[0], v[3]) + 1):
                for y in range(min(v[1], v[4]), max(v[1], v[4]) + 1):
                    for z in range(min(v[2], v[5]), max(v[2], v[5]) + 1):
                        world[(x, y, z)] = b
    return world


def standable_cells(world):
    """{(x, y, z)} feet positions a player can stand in: two passable blocks over a solid one.

    An unwritten block OVERHEAD counts as open, because a gatehouse writes only its own shell and the sky
    above a mouth is air. An unwritten block UNDERFOOT counts as nothing: the measure will not call a column
    standable on terrain this function never placed, so what it returns is the gatehouse's own floor."""
    out = set()
    for (x, y, z), b in world.items():
        if b not in PASSABLE:
            continue
        if world.get((x, y + 1, z), "minecraft:air") not in PASSABLE:
            continue
        below = world.get((x, y - 1, z))
        if below is None or below in PASSABLE:
            continue
        out.add((x, y, z))
    return out


def walk_pieces(cells):
    """`cells` split into the pieces a player can actually walk between, largest first.

    FOUR-connected, with a one-block step up or down. Not eight: a player cannot walk between two blocks that
    meet only at a corner, so an 8-connected fill would have called G2's four pieces one and reported the
    gatehouse sound. That is the entire defect."""
    left, pieces = set(cells), []
    while left:
        start = left.pop()
        q = deque([start])
        piece = [start]
        while q:
            (x, y, z) = q.popleft()
            for (nx, nz) in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                for ny in (y, y + 1, y - 1):
                    if (nx, ny, nz) in left:
                        left.discard((nx, ny, nz))
                        piece.append((nx, ny, nz))
                        q.append((nx, ny, nz))
        pieces.append(sorted(piece, key=lambda c: (c[2], c[0], c[1])))
    return sorted(pieces, key=lambda p: (-len(p), p[0]))


def cmd_walkable(a):
    """Flood-fill every emitted gatehouse function and print its pieces.

    Separate from `report` on purpose, in both directions: `report` never reads anything this tool emitted,
    and this reads nothing else."""
    out = PACKS / PACK / "data" / NS / "function" / FOLDER
    paths = sorted(out.glob("gatehouse_*.mcfunction"))
    if not paths:
        raise ZoneError("no gatehouse function in %s; run `build` first" % out)
    barrier_block = load()["gatehouse"]["blocks"]["barrier"]
    bad = 0
    for p in paths:
        world = simulate_function(p.read_text(encoding="utf-8").splitlines())
        pieces = walk_pieces(standable_cells(world))
        n_stand = sum(len(x) for x in pieces)
        barriers = sorted(k for k, b in world.items() if b == barrier_block)
        # the barrier is meant to be the ONLY break: with it opened the walkway must come out one piece.
        opened = dict(world)
        for k in barriers:
            opened[k] = "minecraft:air"
        whole = walk_pieces(standable_cells(opened))
        ok = len(pieces) == 2 and len(whole) == 1
        bad += 0 if ok else 1
        print("%-42s %2d standable, %d piece(s) %-12s %d barrier block(s), barrier open -> %d piece(s)  %s"
              % (p.stem, n_stand, len(pieces), [len(x) for x in pieces], len(barriers), len(whole),
                 "OK" if ok else "BROKEN"))
        if not ok or getattr(a, "verbose", False):
            for i, piece in enumerate(pieces):
                print("    piece %d: %s" % (i + 1, [(c[0], c[2]) for c in piece]))
    print("%d of %d gatehouses walkable end to end with the barrier as the only break"
          % (len(paths) - bad, len(paths)))
    return 1 if bad else 0


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

        ax, ay, az, ayaw = z["arrive"]
        tx, ty, tz, tyaw = z["turn_back"]
        p = z["pass"]
        short = ("the %s badge" % ordinal(p["threshold"])) if p["kind"] == "badges" else (
            "%d species caught" % p["threshold"] if p["kind"] == "caught" else "the Rift's crisis resolved")
        # every gate into this zone: its own guard, then each staffed post (data/rift_zones.json zones.*.posts).
        # They share the zone's pass and its test; each has its own walkway, knock box, arrival and exit, so a
        # player who comes in at a post is let through THERE and not teleported across the Rift.
        gates = gates_of(zid, z)
        # the knock boxes are the one place inside the zone where a passless player is NOT turned back: they are
        # standing in front of a guard, behind its barrier, being asked. Without this the zone check and the
        # knock advancement would both fire on the same tick and race.
        skip = "".join(" unless entity @s[%s]" % sel_box(k) for (_n, _g, _d, _a, _t, _e, k) in gates)
        fn["%s/zone" % zid] = [
            "# %s's zone check (docs/mechanics/RIFT_ZONES.md section 4, data/rift_zones.json). The advancement tests" % zid,
            "# LOCATION ONLY; the pass is tested here, because minecraft:entity_scores does not match an unset score",
            "# and putting it in the advancement would fail open for every player who never met a guard.",
            "# The %d knock box(es) in front of this zone's guards are excluded: there the guard answers instead." % len(gates),
            "advancement revoke @s only %s:%s/%s_zone" % (NS, FOLDER, zid),
            "execute if entity %s unless score @s %s matches 1..%s run function %s/%s/turn_back"
            % (ex, obj, skip, F, zid)]
        fn["%s/turn_back" % zid] = [
            "# a bed or respawn anchor set inside the zone goes first, so a respawn cannot loop (RIFT_ZONES.md 4)",
            "execute if entity @s[gamemode=!creative] run spawnpoint @s %d %d %d" % (int(tx), int(ty), int(tz)),
            "# the mount first, then the player (UNPROVEN that Cobblemon riding survives this)",
            "execute on vehicle run tp @s %s %d %s" % (tx, ty, tz),
            "tp @s %s %d %s %s 0" % (tx, ty, tz, tyaw),
            "title @s actionbar %s" % text("Turned back: %s opens with %s." % (z["name"], short), color="gold")]

        # one gate's own four functions, for the zone's guard and for every post
        for name, gid, _gd, arr, tb, eb, knock in gates:
            gax, gay, gaz, gayaw = arr
            gtx, gty, gtz, gtyaw = tb
            pre = zid if name == zid else "%s/%s" % (zid, name[len(zid) + 1:])
            files["data/%s/advancement/%s/%s_exit.json" % (NS, FOLDER, name)] = adv(
                [box_cond(eb[:3], eb[3:])], "%s/%s/exit" % (F, pre))
            files["data/%s/advancement/%s/%s_knock.json" % (NS, FOLDER, name)] = adv(
                [box_cond(knock[:3], knock[3:])], "%s/%s/knock" % (F, pre))
            fn["%s/knock" % pre] = [
                "# THE THING THAT CALLS QUALIFY. A player standing in the walkway in front of %s is asking to be" % gid,
                "# let through, so the guard answers. data/gulch_mine.json gate.knock is the same shape at the",
                "# gulch's grille; this is that, per zone. Without it nothing called qualify and the walls would",
                "# have sealed the Rift (tools/reapply.py EXCLUDED, 2026-09-30).",
                "advancement revoke @s only %s:%s/%s_knock" % (NS, FOLDER, name),
                "function %s/%s/qualify" % (F, pre)]
            fn["%s/exit" % pre] = [
                "# the way out past %s, for anyone, pass or not" % gid,
                "advancement revoke @s only %s:%s/%s_exit" % (NS, FOLDER, name),
                "tp @s %s %d %s %s 0" % (gtx, gty, gtz, gtyaw)]
            fn["%s/grant" % pre] = [
                "# the pass, and the way in past %s. Called by %s/qualify, and by %s's dialogue once Codex" % (gid, pre, gid),
                "# writes it (docs/HANDOVER_CODEX.md item 23): the dialogue never has to know the objective's name.",
                "scoreboard players set @s %s 1" % obj,
                "execute on vehicle run tp @s %s %d %s" % (gax, gay, gaz),
                "tp @s %s %d %s %s 0" % (gax, gay, gaz, gayaw),
                "title @s actionbar %s" % text("%s lets you through." % gid, color="gray")]
            if p["kind"] in ("badges", "flag") and p.get("advancements"):
                # ONE advancements={...} argument: a selector may not carry the key twice, and the earlier form
                # repeated it once per badge, which the parser rejects outright.
                inner = ",".join("%s=true" % a for a in p["advancements"])
                fn["%s/qualify" % pre] = [
                    "# the server tests the %s itself: %s." % (p["kind"], short),
                    "execute if entity @s[gamemode=!spectator,advancements={%s}] run function %s/%s/grant" % (inner, F, pre),
                    "execute unless entity @s[advancements={%s}] run title @s actionbar %s"
                    % (inner, text("%s is not satisfied: %s is needed." % (gid, short), color="gold"))]
            else:
                fn["%s/qualify" % pre] = [
                    "# no server-side test for a caught-count zone: no command or predicate reads species owned",
                    "# (data/rift_zones.json zones.%s.qualify_why). %s's dialogue reads" % (zid, gid),
                    "# q.player.pokedex.caught_count and calls %s/%s/grant itself. Until it exists this zone is" % (F, pre),
                    "# SHUT, which is closed, not open; `report` carries it as an OWED dependency.",
                    "title @s actionbar %s"
                    % text("%s counts your Pokedex: %s is needed." % (gid, short), color="gold")]

    # the walls and the gatehouse shells
    for zid, z in sorted(live.items(), key=lambda kv: kv[1]["order"]):
        w = z.get("wall")
        zgates = gates_of(zid, z)
        gb = z["guard"]["block"]
        if w:
            c = cuts[w]
            cols = wall_columns(g, spec, c)
            body = spec["wall"]["palette"]["body"]
            crest = spec["wall"]["palette"]["crest"]
            # every gate's walkway is left out of the fill, so its gatehouse opens it. The walkway's OWN
            # columns, from walkway_path(): the old cross of radius walkway+1 round the guard's block was an
            # axis cross, and on a diagonal axis it missed most of the walkway it was there to protect, so
            # the cross-wall filled the walkway's own columns as a second seal on top of the shell's.
            keep = set()
            for (_n, _gid, gd, _a, _t, _e, _k) in zgates:
                keep.update(walkway_path(gd["block"], gd["outward"], gh))
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
        # the gatehouse shell at each gate's block: every guard and every post has one, walled zone or not.
        # G2's stands on Victory Road at the trailhead, outside the Rift's rim, where the rim itself is the
        # barrier and no cross-wall is built; Z2's three posts stand at the three sculpted descents, for the
        # same reason.
        for (gname, gid, gd, _a, _t, _e, knock) in zgates:
            gq = gd["block"]
            fy = gd["ground_y"] + 1
            sh = gh["blocks"]
            # the walked set first, then the shell as its complement. Emitted in that order and in three
            # passes -- floor, walls, then the walkway's air and roof -- so that no column of the shell can
            # land on a column of the walkway: a per-step pair could, and did (measured_defects).
            path = walkway_path(gq, gd["outward"], gh)
            walls = walkway_shell(path)
            gl = ["# the %s gatehouse shell (RIFT_ZONES.md section 6): a one-wide roofed walkway, a two-high barrier"
                  % gid,
                  "# behind the guard, and an armour stand where Codex's NPC will stand (data/rift_sculpt.json's policy).",
                  "# The walkway blocks OUTSIDE the guard are the knock box %s: standing there runs %s's qualify."
                  % (knock, gid),
                  "# %d walkway columns from %s to %s, 4-connected (a diagonal step carries its own corner, so"
                  % (len(path), tuple(path[0]), tuple(path[-1])),
                  "# the walkway can be WALKED and not only teleported through), walled by %d columns."
                  % (len(walls))]
            for (x0, x1, z_) in x_runs(set(path) | set(walls)):
                gl.append("fill %d %d %d %d %d %d %s" % (x0, fy - 1, z_, x1, fy - 1, z_, sh["shell"]))
            for (x, z_) in walls:
                gl.append("fill %d %d %d %d %d %d %s" % (x, fy, z_, x, fy + 1, z_, sh["shell"]))
            for (x, z_) in path:
                gl.append("fill %d %d %d %d %d %d minecraft:air" % (x, fy, z_, x, fy + 1, z_))
                gl.append("setblock %d %d %d %s" % (x, fy + 2, z_, sh["shell"]))
            # the barrier is the walkway's OWN next column inward of the guard, not round(guard + inward):
            # where the step inward is a diagonal, those are two different columns and only the first of them
            # touches the guard. One column, and the only break the walkway is allowed to have.
            if tuple(gq) not in path or path.index(tuple(gq)) + 1 >= len(path):
                raise ZoneError("%s's guard block %s is not on its own walkway, or is its last column; the "
                                "barrier has nowhere to stand" % (gid, gq))
            bx = path[path.index(tuple(gq)) + 1]
            gl.append("# the barrier directly behind the guard: this is what actually stops a player")
            gl.append("fill %d %d %d %d %d %d %s" % (bx[0], fy, bx[1], bx[0], fy + gh["barrier_height"] - 1, bx[1],
                                                     sh["barrier"]))
            gl.append("setblock %d %d %d %s" % (gq[0], fy + 2, gq[1], sh["lamp"]))
            gl.append("summon minecraft:armor_stand %d %d %d {Invulnerable:1b,NoGravity:1b,CustomNameVisible:1b,"
                      "CustomName:'%s',Tags:[\"cobblers_rift_guard\",\"%s\"]}"
                      % (gq[0], fy, gq[1], text("%s (placeholder)" % gid), gname))
            name = "gatehouse_%s" % gname
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
    # Every function that writes blocks holds the chunks it writes, for its whole run. Without this the walls
    # and the gatehouses `fill` into chunks nobody has loaded, where a fill DOES NOTHING AND SAYS NOTHING - the
    # exact fault that left 0 of the Rift's 14 entities in the world on 2026-09-24. prepare's
    # tools/function_limits.py check found 9 such functions here on 2026-09-30, wall_throat among them writing
    # 890 blocks into chunks it never loaded. ensure_loaded also splits fills over the block limit.
    import function_limits as FL
    for name, lines in fn.items():
        p = out / "data" / NS / "function" / FOLDER / (name + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(FL.ensure_loaded(lines)) + "\n", encoding="utf-8")
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
    w = sub.add_parser("walkable", help="flood-fill the EMITTED gatehouse functions; exit 1 on any break "
                                        "that is not the barrier")
    w.add_argument("--verbose", action="store_true")
    a = p.parse_args(argv)
    try:
        rc = {"trace": cmd_trace, "report": cmd_report, "build": cmd_build,
              "walkable": cmd_walkable}[a.cmd](a)
        return 1 if rc else 0
    except ZoneError as e:
        print("rift_zones: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
