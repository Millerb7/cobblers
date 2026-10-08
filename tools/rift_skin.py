#!/usr/bin/env python
"""The Rift's block pass: everything a height cannot carry, laid over the sculpted shape.

The shape is in the heightmap (tools/rift_heightmap.py), so this pass never cuts or raises ground. It only:

  - skins what can be seen: the surface of every column the sculpt moved, and the exposed face below it
  - lays the one-block crack grooves on the floor, the veins and the debris
  - hangs the sky tear and its shards, and sets the portal-sheet glimpses
  - opens the entrance paths, rails the brink beside them, and marks each guard's trailhead
  - paints the biome to the lip

Everything is chosen by an integer hash of the coordinate, so it is vectorised and identical on every rebuild.
Ground comes from the canonical (sculpted) heightmap, never from a world; `verify` reads a world only to check.

    python tools/rift_skin.py build  --source-root <root> [--server-dir <server>]
    python tools/rift_skin.py verify --world <stopped world copy>
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

import function_limits as FL

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "rift_skin.json"
SCULPT = ROOT / "derived" / "rift_sculpt" / "plan.json"
BASIN = ROOT / "derived" / "rift_sculpt" / "basin.npy"
OUT = ROOT / "build" / "datapacks" / "cobblers_rift"
BIOME_PACK = ROOT / "build" / "datapacks" / "cobblers_rift_biome"
PLAN = ROOT / "derived" / "rift_skin" / "plan.json"
TILE = 64           # 16 chunks: one function force-loads a small square, not a strip of the Rift
PART = 3500         # one function is one tick, and a tick over 60s is a crash to the watchdog

WORLD_READS = {"verify", "entity_count", "main"}


class SkinError(Exception):
    pass


# ---------------------------------------------------------------- deterministic, vectorised noise


def h3(x, y, z, salt):
    """A stable integer hash of a block coordinate. Vectorised, and the same on every machine and run."""
    a = (np.asarray(x, np.int64) * 73856093) ^ (np.asarray(y, np.int64) * 19349663) \
        ^ (np.asarray(z, np.int64) * 83492791) ^ np.int64(salt * 2654435761)
    a &= np.int64(0x7FFFFFFF)
    a = (a ^ (a >> 15)) * np.int64(2246822519)
    a &= np.int64(0x7FFFFFFF)
    a = (a ^ (a >> 13)) * np.int64(3266489917)
    return (a & np.int64(0x7FFFFFFF))


def unit(x, y, z, salt):
    return h3(x, y, z, salt) / float(0x7FFFFFFF)


def installed_blocks(server_dir):
    import glob
    import re
    import zipfile
    if not server_dir:
        return None
    import runtime_guard
    runtime_guard.require_lock("read the server's mod jars")
    mods = runtime_guard.check(Path(server_dir) / "mods", "read the mod jars in")
    ids = set()
    for jar in glob.glob(str(mods / "*.jar")):
        try:
            z = zipfile.ZipFile(jar)
        except (zipfile.BadZipFile, OSError):  # not a readable jar
            continue
        for n in z.namelist():
            m = re.match(r"assets/([^/]+)/blockstates/([^/]+)\.json$", n)
            if m:
                ids.add("%s:%s" % m.groups())
    return ids


def pick(block, fallback, have):
    if block.startswith("minecraft:") or have is None or block in have:
        return block
    return fallback


# ---------------------------------------------------------------- the build


class Skin:
    def __init__(self):
        self.lines = []        # command strings, in order
        self.entities = []
        self.checks = []       # (x, y, z, [allowed], what)
        self.counts = {}
        self.views = {}
        self.biome_cells = []

    def count(self, what, n=1):
        self.counts[what] = self.counts.get(what, 0) + n


def route_lip_crossing(route_id, pts_in_basin, pts, ring, bi):
    """The index on a route's dense walked line where it passes the lip, nearest the gap that entrance measures to.

    The entrance's own gap is measured off the applied rim (tools/rift_heightmap.py measured_entrances), and
    Victory Road was re-routed after the sculpt was applied (35f2a56), so the station the gap is centred on and
    the station the route actually crosses are 44 stations apart. The sculpt cannot move (it is in the heightmap)
    and the route is deliberate, so the BUILD meets the route here: the ramp and the trailhead marker are laid on
    the walked line at its crossing, inside the same measured gap.
    """
    cross = [i for i in range(1, len(pts)) if pts_in_basin[i] and not pts_in_basin[i - 1]]
    if not cross:
        raise SkinError("route %s never crosses the lip: its entrance cannot be laid on it" % route_id)
    gx, gz = ring[bi]
    return min(cross, key=lambda i: (pts[i][0] - gx) ** 2 + (pts[i][1] - gz) ** 2)


def brink_columns(rpts, k0, k1, wide, H, Bq, basin, X0, Z0, shape, min_drop, path_cols):
    """The columns at the brink of a real drop beside a walked line, found by the rule that refused the ramp.

    The ramp lays a column only when its ground is within ONE block of the walked line's (Minecraft's step
    height), and beside Victory Road's crossing it refused 33 columns because the sculpt dropped the floor 18
    blocks one block off the line. That refusal already knows where the edge is, so this reuses it rather than
    inventing a second edge-finder: from the walked line outward, the scan stops at the first column the step
    rule refuses, and the column is a BRINK only if it is `min_drop` or more BELOW the line -- a drop a fall
    hurts on, not a kerb.

    It stops on a column the sculpt raised outside the basin: that is the rim parapet, which is already the
    barrier, and the ramp refuses it for the same reason. It scans both sides, so it is a sweep over the
    crossing rather than a list aimed at the one drop we know about.

    Where the line runs diagonally the brink steps diagonally with it, and two walls on a diagonal do not
    touch: the corner between them is open, and a railing with a hole in it is not a railing. So a diagonal
    pair is closed with the in-between column on the OUTWARD side (the larger dot product with the scan's own
    outward vector), and only if that column is itself over the drop and is not path or walked line.

    THEN the scan is closed against the path the pass actually lays, because a scan along the walked line's own
    normals is a list and the path is not: an independent sweep of the laid path columns against the heightmap
    found four columns a walker could step straight off and no station's normal pointed at -- (3556,5303) and
    (3557,5302) from path at (3556,5304)/(3557,5303), and (3573,5285) from path at (3574,5285). So every path
    column near the crossing has its four orthogonal neighbours checked, and any that is `min_drop` or more
    below the surface a player stands on is a brink column too. After this there is no path column in the
    crossing with an unrailed step-off, which is the property the railing is for.

    Returns [(x, z, y_low, cy)] ordered along the route (nearest station, then distance), deduplicated, with no
    column of the walked line itself and none the entrance pass lays path on.
    """
    reach = wide + wide // 2          # the ramp's outermost column, plus the path's own width again
    online = {(x, z) for x, z in rpts}
    found, seen = [], set()

    def drop_at(x, z, cy):
        ix, iz = x - X0, z - Z0
        if not (0 <= ix < shape[1] and 0 <= iz < shape[0]):
            return None
        if H[iz, ix] > Bq[iz, ix] and not basin[iz, ix]:
            return None
        y = int(H[iz, ix])
        return y if cy - y >= min_drop else None

    for k in range(k0, k1):
        ax, az = rpts[k - 1]
        bx, bz = rpts[k + 1]
        dx, dz = bx - ax, bz - az
        ln = math.hypot(dx, dz) or 1.0
        ux, uz = -dz / ln, dx / ln
        cx, cz = rpts[k]
        cy = int(H[cz - Z0, cx - X0])
        for side in (-1, 1):
            for m in range(1, reach + 1):
                x = int(round(cx + ux * side * m))
                z = int(round(cz + uz * side * m))
                ix, iz = x - X0, z - Z0
                if not (0 <= ix < shape[1] and 0 <= iz < shape[0]):
                    break
                if H[iz, ix] > Bq[iz, ix] and not basin[iz, ix]:
                    break                                  # the parapet: already the barrier
                y = int(H[iz, ix])
                if cy - y >= min_drop:
                    if (x, z) not in seen and (x, z) not in online:
                        seen.add((x, z))
                        found.append((x, z, y, cy, cx, cz, ux * side, uz * side))
                    break
                if abs(y - cy) > 1:
                    break                                  # a step the ramp refused, but not a fall

    out = []
    for i, rec in enumerate(found):
        x, z, y, cy, cx, cz, ox, oz = rec
        out.append((x, z, y, cy))
        if i + 1 >= len(found):
            continue
        nx, nz = found[i + 1][0], found[i + 1][1]
        if abs(nx - x) != 1 or abs(nz - z) != 1:
            continue                                       # already orthogonal, or not adjacent at all
        best = None
        for fx, fz in ((x, nz), (nx, z)):
            if (fx, fz) in seen or (fx, fz) in online:
                continue
            fy = drop_at(fx, fz, cy)
            if fy is None:
                continue
            score = (fx - cx) * ox + (fz - cz) * oz        # the one further out from the walked line
            if best is None or score > best[0]:
                best = (score, fx, fz, fy)
        if best:
            _, fx, fz, fy = best
            seen.add((fx, fz))
            out.append((fx, fz, fy, cy))

    # closed against the laid path, not just the walked line's normals (see the docstring)
    stations = [rpts[k] for k in range(k0, k1)]
    near = set()
    for sx, sz in stations:
        for dx in range(-reach, reach + 1):
            for dz in range(-reach, reach + 1):
                c = (sx + dx, sz + dz)
                if c in path_cols:
                    near.add(c)
    for px, pz in sorted(near):
        pix, piz = px - X0, pz - Z0
        if not (0 <= pix < shape[1] and 0 <= piz < shape[0]):
            continue
        py = int(H[piz, pix])                              # the surface the entrance pass lays the path on
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = px + dx, pz + dz
            if (nx, nz) in seen or (nx, nz) in online or (nx, nz) in path_cols:
                continue
            ny = drop_at(nx, nz, py)
            if ny is None:
                continue
            seen.add((nx, nz))
            out.append((nx, nz, ny, py))

    def along(rec):                                        # order along the route, so the lamps space evenly
        x, z = rec[0], rec[1]
        k = min(range(len(stations)), key=lambda i: (stations[i][0] - x) ** 2 + (stations[i][1] - z) ** 2)
        return (k, (stations[k][0] - x) ** 2 + (stations[k][1] - z) ** 2, x, z)

    return sorted(out, key=along)


def dense_route(route_id):
    paths = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]
    pts = paths.get(route_id)
    if not pts:
        raise SkinError("data/route_paths.json holds no walked line for route %s" % route_id)
    return [(int(x), int(z)) for x, z in pts]


def lake_surface(shape, X0, Z0, H):
    """Columns inside a lake basin whose ground is below that lake's water level, on the skin's own grid.

    WHY. `tools/paint_maps.py` already lays a proper lake bed: inside each landmark's `water_body`
    basin, every column whose ground is under `level_y` is painted GRAVEL or CLAY, and the bank above
    it SAND. That paint is baked into the world at export. The skin then runs as a datapack pass at
    re-apply (R1) and, until 2026-09-30, filled EVERY column it touched right up to its own top - the
    submerged ones included - so 268,972 columns of painted lake bed were overwritten with distortion
    stone, deepslate, cobblestone and crystal block. That is 14.79% of the skin's 1,818,375 surface
    fills, and it is what the owner saw from the air over Shrew Lake at (3009, 4008): the bed reading
    as mottled dark purple instead of sand or gravel, with the shore above the waterline correct.

    Proved, not assumed: at that column the emitted pack held
    `fill 3009 102 4008 3009 104 4008 legendarymonuments:distortion_stone`, and a probe of the staging
    world found water at y105 and distortion_stone at y104. Shrew Lake's `level_y` is 106.

    The recorded hypothesis (FLIGHT_FINDINGS_2026-09-29.md F5) blamed the water-shape pass for
    changing heights without re-materialising the surface, and said "the material decision lives in
    the water-shape tool, unread". It does not. The water shape protects the Rift outright
    (data/water_shape.json `protect.rift`), the paint gets the bed right, and the skin overwrites it.
    The lake is not even inside the Rift's own polygons in data/regions.json - the skin reaches past
    them, because its extent is every column the SCULPT moved, which is a different shape.
    """
    from PIL import Image, ImageDraw
    lm = json.loads((ROOT / "data" / "landmarks.json").read_text(encoding="utf-8"))
    wet = np.zeros(shape, bool)
    for l in lm["landmarks"]:
        wb = l.get("water_body")
        if not wb:
            continue
        img = Image.new("L", (shape[1], shape[0]), 0)
        d = ImageDraw.Draw(img)
        for ring in wb["basin_polygons"]:
            d.polygon([(q[0] - X0, q[1] - Z0) for q in ring], fill=1)
        wet |= np.asarray(img).astype(bool) & (H < wb["level_y"])
    return wet


# ---------------------------------------------------------------- the portal sheets: glimpses through a tear
#
# The owner (2026-09-22): "glimpses only: sheets set deep inside a narrow tear in a solid face, the rock hiding every
# edge. Never standing in the open, never in a fissure." The first placement (to 2026-10-05) did not do that: it put
# nine sheets at evenly spaced ring stations whatever the face was there, carved one column of air two blocks behind
# the ring line with no opening to the air, and hung a 5 x 5 panel there with a yaw that mirrored the face normal and
# a translation that was not rotated with it. On every diagonal face the panel stood edge-on and stuck out of the rock
# into the open, which is what the owner saw at (4166.5, 118, 5121.5): "floating, reading as a random portal".
#
# Now: a site is a ring station on a SHEER stretch where the face is one cliff step; the sheet faces the basin along
# the nearest axis (so its 5 x 5 rectangle is exactly 25 cells of one block layer, nothing rotated), it stands some
# blocks behind the face, and a tear one block wide and three tall runs from the face to it. In the Rift's own surface
# model (a cell is rock iff y <= H, the sculpted heightmap; never a world) every cell of the rectangle and a margin
# round it is rock but the tear, and so are the tear's walls. A station that fails is refused and the next is tried.
#
# The model's limit, stated: below the skin's band (face_depth) the rock is whatever the export made, so the step
# also fills any void in each enclosure box with the seal rock before it carves the tear. Later re-apply steps that
# dig (the Deep, Victory Road, the mines, the zones' walls) are NOT checked here: that is the world probe's job.

SHEET_W = 5         # the panel: 5 wide, 5 tall, one block layer (scale 5 x 5 x 1 of the nether_portal model)
SHEET_H = 5


def sheet_facing(nx, nz):
    """The nearest axis to the inward (toward the basin) normal, as (fx, fz), and the panel's block axis."""
    if abs(nx) >= abs(nz):
        return (1 if nx > 0 else -1, 0), "z"      # facing along x: the panel lies in the z-y plane (axis=z)
    return (0, 1 if nz > 0 else -1), "x"          # facing along z: the panel lies in the x-y plane (axis=x)


def old_sheet_slots(ring, nrm, H, X0, Z0, shape, count):
    """The cells the first placement carved to air, by its own logic: count stations evenly round the ring, one
    column two blocks outside the ring line, from 2 to 7 above the ring station's ground. Kept so the sheets step can
    put back the rock it took, on a world R1 already ran on."""
    out = []
    step = max(1, len(ring) // (count + 1))
    for i in range(count):
        k = (i + 1) * step
        rx, rz = ring[k]
        nx, nz = nrm[k]
        ix, iz = rx - X0, rz - Z0
        if not (0 <= ix < shape[1] and 0 <= iz < shape[0]):
            continue
        y = int(H[iz, ix])
        sx, sz = int(round(rx - nx * 2)), int(round(rz - nz * 2))
        out.append((sx, sz, [y + dy for dy in range(2, 8)]))
    return out


def site_sheet(k, ring, nrm, H, basin, wet, X0, Z0, shape, ps):
    """(site, None) for a sheet at ring station k, or (None, why it is refused). Model only: rock iff y <= H."""
    tr = ps["tear"]
    mg = ps["margin"]
    rx, rz = ring[k]
    (fx, fz), axis = sheet_facing(*nrm[k])
    tx, tz = -fz, fx

    def h(x, z):
        ix, iz = x - X0, z - Z0
        if not (0 <= ix < shape[1] and 0 <= iz < shape[0]):
            return None
        return int(H[iz, ix])

    # the face: walking outward from inside the basin, the first column whose ground stands a sheet's height and
    # its margins above the column in front of it. A sheer stretch is one cliff step, so this is one column.
    face = None
    for d in range(tr["search"], -tr["search"] - 1, -1):
        a, b = h(rx + fx * d, rz + fz * d), h(rx + fx * (d + 1), rz + fz * (d + 1))
        if a is None or b is None:
            continue
        if a - b >= SHEET_H + 1 + mg:
            face = d
            break
    if face is None:
        return None, "no single cliff step tall enough"
    front = (rx + fx * (face + 1), rz + fz * (face + 1))
    ys = h(*front) + 1                                  # the panel's bottom row is the eye-level course over the floor
    # the viewer stands in front: basin floor, dry, not raised over the tear's mouth
    for j in range(1, tr["approach"] + 1):
        x, z = rx + fx * (face + j), rz + fz * (face + j)
        hj = h(x, z)
        if hj is None or not basin[z - Z0, x - X0] or wet[z - Z0, x - X0] or hj > ys:
            return None, "no dry floor in front of the face"
    lo, hi = ys + tr["y"][0], ys + tr["y"][1]           # the tear's courses, inside the panel's five

    def layer(m):                                       # the centre of the m-th block layer behind the face
        return rx + fx * (face - m), rz + fz * (face - m)

    def rock_to(x, z, y):
        g = h(x, z)
        return g is not None and y <= g

    for ks in range(tr["depth"][0], tr["depth"][1] + 1):
        w = tr["width"]
        tear = {(layer(m)[0] + tx * u, y, layer(m)[1] + tz * u)
                for m in range(ks + 1) for u in range(w) for y in range(lo, hi + 1)}
        ok = True
        # the tear's walls, roof and sill, all the way from the face to the sheet
        for m in range(ks + 1):
            cx, cz = layer(m)
            for u in range(-1, w + 1):
                for y in range(lo - 1, hi + 2):
                    if not rock_to(cx + tx * u, cz + tz * u, y):
                        ok = False
        # the sheet's layer, the one in front and the one behind: the rectangle and its margin, all rock
        half = SHEET_W // 2 + mg
        for m in (ks - 1, ks, ks + 1):
            cx, cz = layer(m)
            for u in range(-half, half + 1):
                for y in range(ys - mg, ys + SHEET_H + mg):
                    if not rock_to(cx + tx * u, cz + tz * u, y):
                        ok = False
        if ok:
            sx, sz = layer(ks)
            return {"station": k, "x": sx, "y": ys, "z": sz, "axis": axis, "facing": [fx, fz],
                    "face": list(layer(0)), "depth": ks, "section": w * (hi - lo + 1),
                    "tear": sorted(tear),
                    "view": [front[0] + fx * (tr["approach"] - 1), ys, front[1] + fz * (tr["approach"] - 1)]}, None
    return None, "the rock round the sheet is not solid at any depth up to %d" % tr["depth"][1]


def sheet_panel(site):
    """The cells the summoned panel passes through, from the summon's own geometry: the entity at the centre cell's
    bottom, translated half a block back on its thin axis and 2.5 along its wide one, scaled 5 x 5 x 1."""
    x, y, z = site["x"], site["y"], site["z"]
    half = SHEET_W // 2
    if site["axis"] == "x":
        return [(x + u, y + dy, z) for u in range(-half, half + 1) for dy in range(SHEET_H)]
    return [(x, y + dy, z + u) for u in range(-half, half + 1) for dy in range(SHEET_H)]


def sheet_enclosure_faults(site, H, X0, Z0, shape):
    """The build's guard. Every cell within one block of the panel (its whole box, grown by one in all three axes)
    must be rock after the step, in the model, except the tear's own cells; the tear must reach the panel and open to
    the air at its mouth; and no more than the tear's cross-section of the panel may show. Reads the summon's
    geometry (sheet_panel) and the carved cells, not the search that chose them."""
    def air_after(x, y, z):
        if (x, y, z) in tear:
            return True
        ix, iz = x - X0, z - Z0
        if not (0 <= ix < shape[1] and 0 <= iz < shape[0]):
            return True
        return y > int(H[iz, ix])

    tear = {tuple(c) for c in site["tear"]}
    panel = sheet_panel(site)
    xs, ys_, zs = zip(*panel)
    faults = []
    for x in range(min(xs) - 1, max(xs) + 2):
        for y in range(min(ys_) - 1, max(ys_) + 2):
            for z in range(min(zs) - 1, max(zs) + 2):
                if air_after(x, y, z) and (x, y, z) not in tear:
                    faults.append("open cell %s beside the panel" % ((x, y, z),))
    shown = [c for c in panel if c in tear]
    if not shown:
        faults.append("the tear never reaches the panel: nothing shows")
    if len(shown) > site["section"]:
        faults.append("%d of the panel's %d cells show, more than a tear's cross-section" % (len(shown), len(panel)))
    fx, fz = site["facing"]
    mouth = [c for c in tear if (c[0] + fx, c[1], c[2] + fz) not in tear]
    if not mouth or not all(air_after(c[0] + fx, c[1], c[2] + fz) for c in mouth):
        faults.append("the tear does not open to the air at the face")
    return faults


def build(source_root, server_dir=None):
    import ground as G
    import terrain as T
    from PIL import Image

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    if not SCULPT.is_file():
        raise SkinError("no derived/rift_sculpt/plan.json: run tools/rift_heightmap.py --apply first")
    sc = json.loads(SCULPT.read_text(encoding="utf-8"))
    have = installed_blocks(server_dir)
    seed = spec["seed"]
    pal = spec["palette"]
    rock = [pick(b, f, have) for b, f in zip(pal["rock"], pal["rock_fallbacks"])]
    streak = pick(pal["streak"]["block"], pal["streak"]["fallback"], have)
    BL = {"vein_core": pick(pal["vein_core"]["block"], pal["vein_core"]["fallback"], have),
          "vein_bed": pick(pal["vein_bed"]["block"], pal["vein_bed"]["fallback"], have),
          "vein_seep": pal["vein_seep"]["block"],
          "crystal": pick(pal["crystal"]["block"], pal["crystal"]["fallback"], have)}

    g = G.load(source_root)
    X0, X1, Z0, Z1 = sc["box"]
    H = g.box(X0, Z0, X1, Z1)
    shape = H.shape
    plan = Skin()

    world = T.load_world(str(ROOT / "data" / "world.json"))
    base_name = world["heightmap"]["rift_sculpted_from"]["path"]
    before = T.sample_to_height(np.array(Image.open(Path(source_root) / base_name)), world)
    B = np.round(before[Z0:Z1 + 1, X0:X1 + 1]).astype(int)
    touched = H != B
    plan.count("columns the sculpt moved", int(touched.sum()))

    basin = np.load(BASIN) if BASIN.is_file() else None
    if basin is None or basin.shape != shape:
        raise SkinError("derived/rift_sculpt/basin.npy is missing or the wrong shape: re-run rift_heightmap --apply")

    # ---- the skin: the surface and the exposed face, in bands of rock
    sk = spec["skin"]
    low = np.minimum.reduce([np.roll(H, 1, 0), np.roll(H, -1, 0), np.roll(H, 1, 1), np.roll(H, -1, 1)])
    zz, xx = np.nonzero(touched)
    wx = xx + X0
    wz = zz + Z0
    # the skin stops ONE COURSE SHORT on a column a lake covers, so the bed tools/paint_maps.py painted
    # survives (see lake_surface above). Capping `top` and not skipping the column keeps the Rift's rock
    # under the water where it belongs; only the face the bed is made of is left alone.
    wet = lake_surface(shape, X0, Z0, H)
    top = np.where(wet[zz, xx], H[zz, xx] - 1, H[zz, xx])
    bottom = np.maximum(low[zz, xx] + 1, top - sk["face_depth"])
    bottom = np.minimum(bottom, top - sk["depth"] + 1)
    plan.count("skin columns under a lake, capped one short", int(wet[zz, xx].sum()))
    # a column whose whole band is under the cap has nothing left to skin: drop it rather than emit an
    # inverted fill, which /fill would happily run backwards.
    live = bottom <= top
    dropped = int((~live).sum())
    if dropped:
        plan.count("skin columns dropped entirely (band below the lake cap)", dropped)
    zz, xx, wx, wz = zz[live], xx[live], wx[live], wz[live]
    top, bottom = top[live], bottom[live]
    band = sk["band"]
    segs = []
    for lo, hi, wxi, wzi in zip(bottom.tolist(), top.tolist(), wx.tolist(), wz.tolist()):
        y = lo
        while y <= hi:
            y2 = min(hi, y + band - 1 - (y % band))
            segs.append((wxi, y, wzi, y2))
            y = y2 + 1
    # the hash once over every band, not twice per band on scalars (1.9 million calls, 12 s); the same integer maths
    sx, sy, sz = (np.array([s[k] for s in segs], np.int64) for k in range(3))
    u11, u12 = unit(sx, sy // band, sz, 11).tolist(), unit(sx, sy // band, sz, 12).tolist()
    for (wxi, y, wzi, y2), u, s in zip(segs, u11, u12):
        b = streak if s < 1.0 / pal["streak"]["one_in"] else rock[min(len(rock) - 1, int(u * len(rock)))]
        plan.lines.append("fill %d %d %d %d %d %d %s" % (wxi, y, wzi, wxi, y2, wzi, b))
    n_fill = len(segs)
    plan.count("skin columns", len(wx))
    plan.count("skin fills", n_fill)

    # ---- the crack grooves on the floor: one block deep, vectorised Voronoi edges
    cr = spec["cracks"]
    cell = cr["cell"]
    floor = basin & ~touched
    fz, fx = np.nonzero(floor)
    fwx, fwz = fx + X0, fz + Z0
    ci, cj = fwx // cell, fwz // cell
    d1 = np.full(fwx.shape, 1e18)
    d2 = np.full(fwx.shape, 1e18)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            i2, j2 = ci + di, cj + dj
            cx = i2 * cell + unit(i2, 0, j2, 21) * cell
            cz = j2 * cell + unit(i2, 1, j2, 22) * cell
            d = (fwx - cx) ** 2 + (fwz - cz) ** 2
            newer = d < d1
            d2 = np.where(newer, d1, np.minimum(d2, d))
            d1 = np.where(newer, d, d1)
    edge = (np.sqrt(d2) - np.sqrt(d1)) < 1.0
    ex, ez = fwx[edge], fwz[edge]
    ey = H[fz[edge], fx[edge]]
    glow = unit(ex, 0, ez, 23) < 1.0 / cr["glow_one_in"]
    for x, y, z, gl in zip(ex.tolist(), ey.tolist(), ez.tolist(), glow.tolist()):
        plan.lines.append("setblock %d %d %d %s" % (x, y, z, BL["vein_seep"] if gl else rock[0]))
    plan.count("crack groove columns", int(edge.sum()))
    plan.count("crack grooves that glow", int(glow.sum()))

    # ---- debris outside the rim
    deb = spec["debris"]
    ring = sc["ring"]
    nrm = sc["normals"]
    nd = 0
    for i in range(0, len(ring), 2):
        rx, rz = ring[i]
        nx, nz = nrm[i]
        for d in range(2, deb["reach"], 2):
            x, z = int(round(rx - nx * d)), int(round(rz - nz * d))
            ix, iz = x - X0, z - Z0
            if not (0 <= ix < shape[1] and 0 <= iz < shape[0]) or touched[iz, ix] or basin[iz, ix]:
                continue
            p = deb["density"] * (1 - d / deb["reach"]) ** deb["falloff"]
            if unit(x, 0, z, 31) >= p:
                continue
            y = int(H[iz, ix])
            hgt = deb["lump_height"][1] if unit(x, 1, z, 32) < 1.0 / deb["lump_one_in"] else 1
            b = rock[int(unit(x, 2, z, 33) * len(rock))]
            plan.lines.append("fill %d %d %d %d %d %d %s" % (x, y + 1, z, x, y + hgt, z, b))
            nd += 1
    plan.count("debris lumps", nd)

    # ---- veins along the lip
    vs = spec["veins"]
    nv = 0
    i = 0
    while i < len(ring):
        i += int(vs["along_lip"]["every"][0] + unit(i, 0, 0, 41) *
                 (vs["along_lip"]["every"][1] - vs["along_lip"]["every"][0]))
        if i >= len(ring):
            break
        ln = int(vs["along_lip"]["length"][0] + unit(i, 1, 0, 42) *
                 (vs["along_lip"]["length"][1] - vs["along_lip"]["length"][0]))
        for k in range(ln):
            j = (i + k) % len(ring)
            rx, rz = ring[j]
            nx, nz = nrm[j]
            off = 4 + 10 * unit(j, 2, 0, 43)
            x, z = int(round(rx + nx * off)), int(round(rz + nz * off))
            ix, iz = x - X0, z - Z0
            if not (0 <= ix < shape[1] and 0 <= iz < shape[0]) or not basin[iz, ix]:
                continue
            y = int(H[iz, ix])
            b = BL["vein_core"] if k % 9 == 0 else BL["vein_bed"]
            plan.lines.append("setblock %d %d %d %s" % (x, y, z, b))
            plan.checks.append((x, y, z, [b.split("[")[0]], "vein"))
            nv += 1
    plan.count("vein blocks", nv)

    # ---- the sky tear, over the Rift's long axis, and the shards above it
    st = spec["sky_tear"]
    halo = pick(st["halo"]["block"], st["halo"]["fallback"], have)
    shard_rock = pick(st["shards"]["rock"], st["shards"]["rock_fallback"], have)
    bz, bx = np.nonzero(basin)
    ax0, az0 = float(bx.min() + X0), float(bz.min() + Z0)
    ax1, az1 = float(bx.max() + X0), float(bz.max() + Z0)
    L = math.hypot(ax1 - ax0, az1 - az0)
    ux, uz = (ax1 - ax0) / L, (az1 - az0) / L
    px, pz = -uz, ux
    mid_y = sum(st["y"]) // 2
    tear_pts = []
    wob = 0.0
    for k in range(0, int(L)):
        wob += (unit(k, 0, 0, 51) - 0.5) * 1.6
        wob = max(-70.0, min(70.0, wob))
        tear_pts.append((ax0 + ux * k + px * wob, az0 + uz * k + pz * wob))

    def tear_line(pts, width, salt):
        n = 0
        for k, (tx, tz) in enumerate(pts):
            w = width + int(unit(k, 1, 0, salt) * 4) - 2
            yc = mid_y + int(8 * math.sin(k / 90.0))
            for dw in range(-(w // 2), w - w // 2):
                x, z = int(round(tx + px * dw)), int(round(tz + pz * dw))
                core = abs(dw) <= max(1, w // 4)
                plan.lines.append("fill %d %d %d %d %d %d %s" % (
                    x, yc, z, x, yc + st["thickness"] - 1, z, st["core"] if core else halo))
                n += st["thickness"]
                if k % 400 == 0 and dw == 0:
                    plan.checks.append((x, yc, z, [st["core"]], "sky tear"))
        return n

    plan.count("sky tear blocks", tear_line(tear_pts, st["main_width"], 52))
    s = 60.0
    side = 1
    while s < L - 60:
        side = -side
        ang = math.radians(30 + unit(int(s), 2, 0, 53) * 30)
        bpts, ss, tt = [], s, 0.0
        for _ in range(int(60 + unit(int(s), 3, 0, 54) * 90)):
            ss += math.sin(ang) * 0.8
            tt += side * math.cos(ang)
            if ss >= L:
                break
            bx_, bz_ = tear_pts[int(ss)]
            bpts.append((bx_ + px * tt, bz_ + pz * tt))
        plan.count("sky tear blocks", tear_line(bpts, st["branch_width"], 55))
        s += 70 + unit(int(s), 4, 0, 56) * 140
    sh = st["shards"]
    ns = 0
    for i in range(sh["count"]):
        k = int(unit(i, 0, 0, 57) * (len(tear_pts) - 1))
        tx, tz = tear_pts[k]
        off = (unit(i, 1, 0, 58) - 0.5) * 2 * sh["drift"]
        tx, tz = tx + px * off, tz + pz * off
        yb = mid_y + int(sh["above"][0] + unit(i, 2, 0, 59) * (sh["above"][1] - sh["above"][0]))
        w = int(sh["width"][0] + unit(i, 3, 0, 60) * (sh["width"][1] - sh["width"][0]))
        hh = int(sh["height"][0] + unit(i, 4, 0, 61) * (sh["height"][1] - sh["height"][0]))
        for ds in range(-(w // 2), w - w // 2):
            for dt in range(-(w // 2), w - w // 2):
                rr = math.hypot(ds / (w / 2.0), dt / (w / 2.0))
                if rr >= 1:
                    continue
                x, z = int(round(tx + ds)), int(round(tz + dt))
                hi = yb + int(hh * (1 - rr ** 1.7))
                loy = yb - int(hh * 0.35 * (1 - rr))
                if hi < loy:
                    continue
                plan.lines.append("fill %d %d %d %d %d %d %s" % (x, loy, z, x, hi, z, shard_rock))
                ns += hi - loy + 1
                if ds == 0 and dt == 0:
                    plan.checks.append((x, hi, z, [shard_rock], "sky shard"))
    plan.count("sky shard blocks", ns)

    # ---- the entrances: the path surface and the guard's trailhead, from the sculpt's own ramps
    ent = sc["entrances"]
    path_cols = set()       # every column the entrance pass lays path on: the railing never stands in one
    rail_todo = []
    for e in ent:
        bi = e["ring"]
        rx, rz = ring[bi]
        nx, nz = nrm[bi]
        half = e.get("gap", 30)
        for j in range(-half, half + 1):
            k = (bi + j) % len(ring)
            qx, qz = ring[k]
            mx, mz = nrm[k]
            f = 1 - abs(j) / (half + 1.0)
            if f < 0.25:
                continue
            wide = max(1, int(e.get("width", 4) * f))
            for d in range(-14, 30):
                for dw in range(-(wide // 2), wide - wide // 2):
                    x = int(round(qx + mx * d - mz * dw))
                    z = int(round(qz + mz * d + mx * dw))
                    ix, iz = x - X0, z - Z0
                    if not (0 <= ix < shape[1] and 0 <= iz < shape[0]):
                        continue
                    y = int(H[iz, ix])
                    plan.lines.append("setblock %d %d %d minecraft:dirt_path" % (x, y, z))
                    path_cols.add((x, z))
                    plan.count("entrance path columns")
                    if j == 0 and d == 0 and dw == 0:
                        plan.checks.append((x, y, z, ["minecraft:dirt_path"], "entrance path"))
        # ---- an entrance that names a route: the ramp and the marker go where the route really crosses the lip.
        # The apron above is centred on the station the applied gap is measured at; Victory Road's crossing is 44
        # stations along the same gap, so the walker met unmarked ground and the marker stood 53 blocks away. The
        # sculpt (heightmap) and the corridor (data/routes.json) are both fixed, so this pass moves instead. A
        # column the sculpt RAISED outside the basin is the parapet: the ramp refuses it rather than climbing it.
        gx, gz = int(round(rx - nx * 16)), int(round(rz - nz * 16))
        if e.get("snap_route"):
            rpts = dense_route(e["snap_route"])
            inb = []
            for px, pz in rpts:
                pix, piz = px - X0, pz - Z0
                inb.append(0 <= pix < shape[1] and 0 <= piz < shape[0] and bool(basin[piz, pix]))
            ci = route_lip_crossing(e["snap_route"], inb, rpts, ring, bi)
            wide = max(1, int(e.get("width", 4)))
            k0, k1 = max(1, ci - 14), min(len(rpts) - 1, ci + 30)
            rail_todo.append((e, rpts, k0, k1, wide))
            laid = 0
            for k in range(k0, k1):
                ax, az = rpts[k - 1]
                bx2, bz2 = rpts[k + 1]
                dx, dz = bx2 - ax, bz2 - az
                ln = math.hypot(dx, dz) or 1.0
                ux, uz = -dz / ln, dx / ln
                cx, cz2 = rpts[k]
                cy = int(H[cz2 - Z0, cx - X0])
                for dw in range(-(wide // 2), wide - wide // 2):
                    x = int(round(rpts[k][0] + ux * dw))
                    z = int(round(rpts[k][1] + uz * dw))
                    ix, iz = x - X0, z - Z0
                    if not (0 <= ix < shape[1] and 0 <= iz < shape[0]):
                        continue
                    if H[iz, ix] > B[iz, ix] and not basin[iz, ix]:
                        plan.count("%s: ramp columns refused on raised rim" % e["id"])
                        continue
                    y = int(H[iz, ix])
                    # the ramp is a walking surface, so it is only as wide as the ground a player can walk: one
                    # block of step, Minecraft's own, not a tolerance. Beside this crossing the sculpt dropped the
                    # floor 18 blocks one block off the walked line, and a 4-wide stripe painted the drop as path.
                    if abs(y - cy) > 1:
                        plan.count("%s: ramp columns off the walking surface" % e["id"])
                        continue
                    plan.lines.append("setblock %d %d %d minecraft:dirt_path" % (x, y, z))
                    path_cols.add((x, z))
                    laid += 1
                    if k == ci and dw == 0:
                        plan.checks.append((x, y, z, ["minecraft:dirt_path"], "entrance path"))
            plan.count("entrance path columns", laid)
            plan.count("%s: ramp columns on the walked line" % e["id"], laid)
            gx, gz = rpts[max(0, ci - 16)]
            plan.views["%s: the route's crossing" % e["id"]] = [rpts[ci][0], int(H[rpts[ci][1] - Z0, rpts[ci][0] - X0]) + 2, rpts[ci][1]]
        gix, giz = gx - X0, gz - Z0
        gy = int(H[giz, gix]) + 1 if (0 <= gix < shape[1] and 0 <= giz < shape[0]) else 150
        plan.entities.append(
            'summon minecraft:armor_stand %.1f %d %.1f {CustomName:\'"%s (placeholder)"\','
            'CustomNameVisible:1b,NoGravity:1b,Invulnerable:1b,Tags:["%s","%s"]}'
            % (gx + 0.5, gy, gz + 0.5, e.get("guard", "Rift guard"), spec["portal_sheets"]["tag"], "rift_fx_all"))
        plan.views["%s: the trailhead" % e["id"]] = [gx, gy + 2, gz]
    plan.count("entrance trailheads", len(ent))

    # ---- the railing on the brink beside a snapped entrance (owner, 2026-10-01: "mark it rather than re-routing")
    # It stands in the FIRST column the drop refuses, outside the walking surface, never in a column the entrance
    # pass lays path on and never on the walked line, so the route's walkable width does not change by a block.
    # Each rail block is carried by a pier of the skin's own rock from the real ground at the bottom of the drop
    # up to the walked line's level, so nothing floats and the pier reads as a rib on a face that is already rock.
    # COVERS only entrances with `snap_route`: the apron entrances have no walked line to find a brink beside.
    rl = spec["entrance_railing"]
    nrail = npier = nlamp = 0
    for e, rpts, k0, k1, wide in rail_todo:
        brink = brink_columns(rpts, k0, k1, wide, H, B, basin, X0, Z0, shape, rl["min_drop"], path_cols)
        kept = [(x, z, ylow, cy) for x, z, ylow, cy in brink if (x, z) not in path_cols]
        plan.count("%s: railing columns in a path column, skipped" % e["id"], len(brink) - len(kept))
        for i, (x, z, ylow, cy) in enumerate(kept):
            y = ylow + 1
            while y <= cy:                                   # the pier, in the skin's own five-block bands
                y2 = min(cy, y + band - 1 - (y % band))
                b = streak if unit(x, y // band, z, 12) < 1.0 / pal["streak"]["one_in"] \
                    else rock[min(len(rock) - 1, int(unit(x, y // band, z, 11) * len(rock)))]
                plan.lines.append("fill %d %d %d %d %d %d %s" % (x, y, z, x, y2, z, b))
                npier += y2 - y + 1
                y = y2 + 1
            for c in range(rl["courses"]):
                plan.lines.append("setblock %d %d %d %s" % (x, cy + 1 + c, z, rl["rail"]))
            nrail += 1
            if i % rl["lamp_every"] == 0:                    # a lamp post, as the dig camp's own posts are made
                plan.lines.append("setblock %d %d %d %s" % (x, cy + 1 + rl["courses"], z, rl["rail"]))
                plan.lines.append("setblock %d %d %d %s" % (x, cy + 2 + rl["courses"], z, rl["lamp"]))
                nlamp += 1
            if i == len(kept) // 2:
                plan.checks.append((x, cy + 1, z, [rl["rail"]], "railing rail"))
                plan.checks.append((x, cy, z, sorted(set(rock)) + [streak], "railing pier"))
        plan.count("%s: railing columns" % e["id"], len(kept))
        if kept:
            mx, mz, _, mcy = kept[len(kept) // 2]
            plan.views["%s: the railing on the brink" % e["id"]] = [mx, mcy + 3, mz]
    plan.count("railing rail blocks", nrail)
    plan.count("railing pier blocks", npier)
    plan.count("railing lanterns", nlamp)

    # ---- the portal sheets: glimpses set deep in a tear in a solid face. Their OWN step (R1S, cobblers:rift/sheets),
    # so they can be re-sited without the whole R1 pass: nothing of them is in plan.lines or plan.entities.
    ps = spec["portal_sheets"]
    seal_rock = pick(spec["water"]["seal"]["block"], spec["water"]["seal"]["fallback"], have)
    sheer = [k for a_, b_, kind in sc["segments"] if kind == "sheer" for k in range(int(math.ceil(a_)), int(b_))
             if k < len(ring)]
    near_entrance = set()
    for e in ent:
        reach = e.get("gap", 30) + ps["entrance_clearance"]
        near_entrance.update((e["ring"] + j) % len(ring) for j in range(-reach, reach + 1))
    refused = {}
    sites = []
    bins = ps["count"]
    for b_ in range(bins):
        part = sheer[b_ * len(sheer) // bins:(b_ + 1) * len(sheer) // bins]
        mid = len(part) // 2
        order_ = [part[mid + (d + 1) // 2 * (1 if d % 2 else -1)] for d in range(len(part))
                  if 0 <= mid + (d + 1) // 2 * (1 if d % 2 else -1) < len(part)]
        got = None
        for k in order_:
            if k in near_entrance:
                refused["beside an entrance"] = refused.get("beside an entrance", 0) + 1
                continue
            site, why = site_sheet(k, ring, nrm, H, basin, wet, X0, Z0, shape, ps)
            if site is None:
                refused[why] = refused.get(why, 0) + 1
                continue
            got = site
            break
        if got is not None:
            sites.append(got)
    for why, n in sorted(refused.items()):
        plan.count("portal sheet stations refused: %s" % why, n)
    if len(sites) < ps["count"]:
        print("  portal sheets: only %d of %d stretches have a face that encloses a sheet" % (len(sites), ps["count"]))
    # the guard: a sheet whose rectangle is not enclosed fails the build, whatever chose it
    for st_ in sites:
        faults = sheet_enclosure_faults(st_, H, X0, Z0, shape)
        if faults:
            raise SkinError("portal sheet at %s is not enclosed: %s" % ((st_["x"], st_["y"], st_["z"]), faults[:4]))
    old = old_sheet_slots(ring, nrm, H, X0, Z0, shape, ps["count"])
    sl = []          # the step's block lines, in order: put back the old slots, seal the enclosures, carve the tears
    for x, z, cells in old:
        g = int(H[z - Z0, x - X0])
        for y in cells:
            if y > g:
                continue                      # the model has air there: the old carve took nothing
            b = rock[min(len(rock) - 1, int(unit(x, y // band, z, 11) * len(rock)))]
            sl.append("fill %d %d %d %d %d %d %s replace minecraft:air" % (x, y, z, x, y, z, b))
            plan.count("portal sheets: old slot cells put back")
    for st_ in sites:
        panel = sheet_panel(st_)
        xs, ys_, zs = zip(*panel)
        fx, fz = st_["facing"]
        # any cave the export left in the rock the model says encloses the sheet becomes rock: the panel's box grown
        # by one (the guard's box), and the tear's walls from the face in. Only cells the search proved are rock in
        # the model, so the fill can never build into the open.
        sl.append("fill %d %d %d %d %d %d %s replace #cobblers:rift_void" % (
            min(xs) - 1, min(ys_) - 1, min(zs) - 1, max(xs) + 1, max(ys_) + 1, max(zs) + 1, seal_rock))
        tx_, ty_, tz_ = zip(*st_["tear"])
        sl.append("fill %d %d %d %d %d %d %s replace #cobblers:rift_void" % (
            min(tx_) - abs(fz), min(ty_) - 1, min(tz_) - abs(fx), max(tx_) + abs(fz), max(ty_) + 1, max(tz_) + abs(fx),
            seal_rock))
        for x, y, z in st_["tear"]:
            sl.append("setblock %d %d %d minecraft:air" % (x, y, z))
        plan.count("portal sheet tear cells", len(st_["tear"]))
    se = []
    for st_ in sites:
        if st_["axis"] == "x":
            scale, trans = "5f,5f,1f", "-2.5f,0f,-0.5f"
        else:
            scale, trans = "1f,5f,5f", "-0.5f,0f,-2.5f"
        se.append(
            'summon minecraft:block_display %.1f %d %.1f {block_state:{Name:"%s",Properties:{axis:"%s"}},'
            'brightness:{sky:15,block:15},view_range:%.1ff,width:6f,height:6f,'
            'transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],'
            'translation:[%s],scale:[%s]},Tags:["%s","%s"]}'
            % (st_["x"] + 0.5, st_["y"], st_["z"] + 0.5, ps["block"], st_["axis"], ps["view_range"],
               trans, scale, ps["tag"], ps["sheet_tag"]))
    plan.sheet_lines, plan.sheet_entities, plan.sheet_sites, plan.old_slots = sl, se, sites, old
    plan.count("portal sheets", len(sites))
    plan.views["a glimpse"] = sites[0]["view"] if sites else [0, 0, 0]

    # ---- the seal: any void the export left right behind a new face becomes rock
    seal = spec["water"]["seal"]
    seal_b = pick(seal["block"], seal["fallback"], have)
    ns = 0
    for lo, hi, wxi, wzi in zip(bottom.tolist(), top.tolist(), wx.tolist(), wz.tolist()):
        plan.lines.append("fill %d %d %d %d %d %d %s replace #cobblers:rift_void" % (
            wxi, lo - seal["depth"], wzi, wxi, hi, wzi, seal_b))
        ns += 1
    plan.count("seal fills", ns)

    # ---- the biome, only where a whole cell is inside the lip
    # Minecraft stores a biome per 4x4x4 cell aligned to the WORLD grid. A cell aligned to the box origin instead
    # straddles two real cells, and fillbiome rounds outward: the first run bled the Rift's biome two blocks past
    # the lip at 12 of 24 sampled points. So the grid is offset to a multiple of the cell size.
    bc = spec["biome"]["cell"]
    ox_, oz_ = (-X0) % bc, (-Z0) % bc
    ins = basin[oz_:, ox_:].astype(np.uint8)
    cz_, cx_ = ins.shape[0] // bc, ins.shape[1] // bc
    blocks_ok = ins[:cz_ * bc, :cx_ * bc].reshape(cz_, bc, cx_, bc).min(axis=(1, 3))
    gz_, gx_ = np.nonzero(blocks_ok)
    plan.biome_cells = [[int(x * bc + X0 + ox_), int(z * bc + Z0 + oz_)]
                        for z, x in zip(gz_.tolist(), gx_.tolist())]
    assert all(x % bc == 0 and z % bc == 0 for x, z in plan.biome_cells[:64]), "biome cells are not world-aligned"
    plan.count("biome cells", len(plan.biome_cells))

    # ---- sampled checks on the skin itself
    keep = np.nonzero(unit(wx, top, wz, 71) < 0.004)[0]
    for i in keep.tolist():
        y = int(top[i])
        b = streak if unit(int(wx[i]), y // band, int(wz[i]), 12) < 1.0 / pal["streak"]["one_in"] \
            else rock[min(len(rock) - 1, int(unit(int(wx[i]), y // band, int(wz[i]), 11) * len(rock)))]
        plan.checks.append((int(wx[i]), y, int(wz[i]), [b], "skin surface"))

    plan.spec, plan.sc, plan.H, plan.box, plan.basin = spec, sc, H, (X0, X1, Z0, Z1), basin
    plan.rock, plan.streak, plan.BL, plan.have = rock, streak, BL, have
    plan.touched = touched
    return plan


def settle_checks(plan):
    """Point every check at the block the build actually leaves.

    The passes overwrite each other on purpose: a vein is laid over the skin, the tear's halo over its core. A
    check recorded when a block was written asserts an intent that a later line has since replaced, and the audit
    reports a mismatch for a build that is correct. So the lines are replayed over the sampled positions only, and
    each check takes the last block written there (2026-09-22: 215 such mismatches, every one galar_particle_block).
    """
    want = {(x, y, z) for x, y, z, _, _ in plan.checks}
    cols = {(x, z) for x, y, z in want}
    final = {}
    for ln in plan.lines:
        t = ln.split()
        x, z = int(t[1]), int(t[3])
        if (x, z) not in cols:
            continue
        if t[0] == "setblock":
            if (x, int(t[2]), z) in want:
                final[(x, int(t[2]), z)] = t[4]
        elif t[0] == "fill":
            y0, y1 = int(t[2]), int(t[5])
            if len(t) > 8 and t[8] == "replace":
                continue                      # the seal only fills voids: it never replaces a block we placed
            for y in range(min(y0, y1), max(y0, y1) + 1):
                if (x, y, z) in want:
                    final[(x, y, z)] = t[7]
    out, moved = [], 0
    for x, y, z, allowed, what in plan.checks:
        b = final.get((x, y, z))
        if b and b not in allowed:
            moved += 1
        out.append((x, y, z, [b] if b else allowed, what))
    plan.checks = out
    plan.count("checks re-pointed at the block the build leaves", moved)
    return moved


def write(plan):
    """Emit the datapacks: the blocks in order, the biome, and the entity lifecycle."""
    import shutil
    settle_checks(plan)
    spec = plan.spec
    for d in (OUT, BIOME_PACK):
        if d.exists():
            shutil.rmtree(d)
    fn = OUT / "data" / "cobblers" / "function" / "rift"
    fn.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "Cobblers: the Rift's skin"}}, indent=2) + "\n",
        encoding="utf-8")
    tags = OUT / "data" / "cobblers" / "tags" / "block"
    tags.mkdir(parents=True)
    (tags / "rift_void.json").write_text(json.dumps(
        {"values": ["minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:water",
                    "minecraft:lava", "minecraft:bubble_column"]}, indent=2) + "\n", encoding="utf-8")

    # Tiled, not just chunked by count. Ordered by a scan across the Rift, a 40,000-command function spans the
    # whole width, force-loads a strip of it at once, and the watchdog kills the server in chunk loading -- which
    # is what happened on the first run. A tile keeps each function's force-load compact.
    tiles = {}
    for ln in plan.lines:
        t = ln.split()
        x, z = int(t[1]), int(t[3])
        tiles.setdefault((x // TILE, z // TILE), []).append(ln)
    order = []
    for t in sorted(tiles):
        body = tiles[t]
        for k in range(0, len(body), PART):
            name = "blocks_%d_%d%s" % (t[0], t[1], "" if k == 0 else "_%d" % (k // PART + 1))
            lines = FL.ensure_loaded(["# Generated by tools/rift_skin.py: tile %d %d" % t] + body[k:k + PART])
            probs = FL.check_lines(lines, name)
            if probs:
                raise SkinError("function %s would be refused: %s" % (name, probs[:3]))
            (fn / (name + ".mcfunction")).write_text("\n".join(lines) + "\n", encoding="utf-8")
            order.append(name)

    # the biome, in its own pack so the world loads it before the functions run
    bf = BIOME_PACK / "data" / "cobblers" / "worldgen" / "biome"
    bf.mkdir(parents=True)
    (BIOME_PACK / "pack.mcmeta").write_text(json.dumps(
        {"pack": {"pack_format": 48, "description": "Cobblers: the Rift biome"}}, indent=2) + "\n",
        encoding="utf-8")
    src = ROOT / "kits" / "biome-kits" / "the_rift.json"
    if not src.is_file():
        raise SkinError("kits/biome-kits/the_rift.json is missing: the biome the owner flew is the authored one")
    (bf / "the_rift.json").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    bfn = BIOME_PACK / "data" / "cobblers" / "function" / "rift"
    bfn.mkdir(parents=True)
    y0, y1 = spec["biome"]["y"]
    c = spec["biome"]["cell"]
    # Tiled and force-loaded by hand. fillbiome silently does nothing on an unloaded chunk, and
    # function_limits.ensure_loaded does not recognise its coordinates, so the first run painted no biome at all
    # and reported no error (2026-09-22).
    btiles = {}
    for x, z in plan.biome_cells:
        btiles.setdefault((x // TILE, z // TILE), []).append(
            "fillbiome %d %d %d %d %d %d %s" % (x, y0, z, x + c - 1, y1, z + c - 1, spec["biome"]["id"]))
    border = []
    for t_ in sorted(btiles):
        body = btiles[t_]
        x0, z0 = t_[0] * TILE, t_[1] * TILE
        box = "%d %d %d %d" % (x0, z0, x0 + TILE - 1, z0 + TILE - 1)
        for k in range(0, len(body), PART):
            name = "biome_%d_%d%s" % (t_[0], t_[1], "" if k == 0 else "_%d" % (k // PART + 1))
            lines = (["# Generated by tools/rift_skin.py: tile %d %d" % t_, "forceload add " + box]
                     + body[k:k + PART] + ["forceload remove " + box])
            (bfn / (name + ".mcfunction")).write_text("\n".join(lines) + "\n", encoding="utf-8")
            border.append(name)

    # the entities: force-load, wait, kill by tag, summon, count
    tag = "rift_fx_all"
    xs = [int(e.split()[2].split(".")[0]) for e in plan.entities]
    zs = [int(e.split()[4].split(".")[0]) for e in plan.entities]
    fx = ["# Generated by tools/rift_skin.py: the Rift's entities"]
    boxes = sorted({(x >> 4 << 4, z >> 4 << 4) for x, z in zip(xs, zs)})
    for bx, bz in boxes:
        fx.append("forceload add %d %d %d %d" % (bx - 16, bz - 16, bx + 31, bz + 31))
    fx.append("schedule function cobblers:rift/fx_go 60t replace")
    (fn / "fx.mcfunction").write_text("\n".join(fx) + "\n", encoding="utf-8")
    # kill by tag only, whatever the entity type, so a re-run never stacks a guard on a guard; then count what
    # is actually there, which is what the audit reads
    go = ["# Generated by tools/rift_skin.py",
          "scoreboard objectives add cobblers.rift_fx dummy",
          "kill @e[tag=%s]" % tag] + plan.entities + [
        "execute store result score #%s cobblers.rift_fx if entity @e[tag=%s]" % (tag, tag)]
    for bx, bz in boxes:
        go.append("forceload remove %d %d %d %d" % (bx - 16, bz - 16, bx + 31, bz + 31))
    (fn / "fx_go.mcfunction").write_text("\n".join(go) + "\n", encoding="utf-8")

    # the portal sheets, their own step (R1S): force-load every chunk they or the old slots touch, wait for the
    # entities to load, then kill every sheet (the old ones carry rift_fx and rift_fx_all, the new rift_fx and
    # rift_sheet; only block_displays, so the trailhead stands that also carry rift_fx stay), put back the old slots,
    # seal and carve, summon, count. The new sheets do NOT carry rift_fx_all, so re-running R1's fx_go leaves them.
    ps = spec["portal_sheets"]
    pts = [(x, z) for x, z, _ in plan.old_slots] + [(c[0], c[2]) for s_ in plan.sheet_sites for c in s_["tear"]] \
        + [(c[0], c[2]) for s_ in plan.sheet_sites for c in sheet_panel(s_)]
    sboxes = sorted({(x >> 4 << 4, z >> 4 << 4) for x, z in pts})
    hold = ["forceload add %d %d %d %d" % (bx - 16, bz - 16, bx + 31, bz + 31) for bx, bz in sboxes]
    probs = FL.check_lines(hold + plan.sheet_lines, "sheets_go")
    if probs:
        raise SkinError("the sheets step would be refused: %s" % probs[:3])
    (fn / "sheets.mcfunction").write_text("\n".join(
        ["# Generated by tools/rift_skin.py: the Rift's portal sheets (re-apply step R1S)"] + hold
        + ["schedule function cobblers:rift/sheets_go 60t replace"]) + "\n", encoding="utf-8")
    sg = ["# Generated by tools/rift_skin.py",
          "# chunks-loaded-by: cobblers:rift/sheets (its forceload of every sheet box, checked above with these lines)",
          "scoreboard objectives add cobblers.rift_fx dummy",
          "kill @e[type=minecraft:block_display,tag=%s]" % ps["tag"]] + plan.sheet_lines + plan.sheet_entities + [
        "execute store result score #%s cobblers.rift_fx if entity @e[type=minecraft:block_display,tag=%s]"
        % (ps["sheet_tag"], ps["tag"])]
    sg += ["forceload remove %d %d %d %d" % (bx - 16, bz - 16, bx + 31, bz + 31) for bx, bz in sboxes]
    (fn / "sheets_go.mcfunction").write_text("\n".join(sg) + "\n", encoding="utf-8")

    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    (bfn / "index.txt").write_text("\n".join(border) + "\n", encoding="utf-8")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps({
        "checks": [[x, y, z, a, w] for x, y, z, a, w in plan.checks],
        "entities_expected": len(plan.entities),
        "entity_area_tag": tag,
        "sheets_expected": len(plan.sheet_entities),
        "sheet_tag": spec["portal_sheets"]["sheet_tag"],
        "sheets": [{k: s_[k] for k in ("station", "x", "y", "z", "axis", "facing", "face", "depth", "tear", "view")}
                   for s_ in plan.sheet_sites],
        "old_sheet_slots": [[x, z, cells] for x, z, cells in plan.old_slots],
        "commands": len(plan.lines),
        "biome_cells": len(plan.biome_cells),
        "counts": plan.counts,
        "views": plan.views,
    }), encoding="utf-8")
    return order, border, len(plan.entities)


def entity_count(world, tag):
    """Entities of any type carrying the tag (rift_fx_all: the trailhead guards; rift_sheet: the sheets), from the entity region files."""
    import nbt
    n = 0
    for p in sorted((Path(world) / "entities").glob("r.*.*.mca")):
        for _, _, ch in nbt.region_chunks(p):
            for e in ch.get("Entities") or []:
                if tag in (e.get("Tags") or []):
                    n += 1
    return n


FN_REF = re.compile(r"(?:^|\s)function ([a-z0-9_.-]+:[a-z0-9_./-]+)")
NUM3 = r"(-?\d+) (-?\d+) (-?\d+)"
LATER_FILL = re.compile(r"fill %s %s (\S+)(?: (replace|keep|destroy|hollow|outline)(?: (\S+))?)?$" % (NUM3, NUM3))
LATER_SET = re.compile(r"setblock %s (\S+)(?: (replace|keep|destroy))?$" % NUM3)
OWN_STEPS = ("R1", "R1B")          # the steps this pack's functions run in (tools/reapply.py steps())


def later_owned(points):
    """{(x, y, z): step id} for the sampled positions a LATER re-apply step writes over, from those steps' own
    generated functions, in the order tools/reapply.py runs them. Never from a world.

    The skin is laid first (R1), and later steps rebuild parts of it on purpose: the League's lot and skirt (R8B)
    re-level the apex oval, a town's prep levels its lots (R8), the Windward Deep (R9B) is dug through the floor.
    A skin sample there asserts an intent a later step has replaced, and the verify reported it as a mismatch
    (EXP-026 run 4: 13 such cells, 11 of them the League's skirt). A write counts only when it is certain to replace
    the planned block: a plain setblock or fill, `destroy`, `hollow` (it writes its whole box), or `replace`/`keep`
    whose filter is that exact block (or air, for keep). A tag filter, an `execute` prefix and a `place template`
    are not replayed, so what they write stays expected here and a real overlap still shows as a mismatch."""
    import reapply
    try:
        todo = reapply.steps()
    except SystemExit as e:                                   # an unprepared pack: fail closed, say why
        raise SkinError("cannot tell which later steps rebuild the skin: %s" % e)
    ids = [s[0] for s in todo]
    if not all(s in ids for s in OWN_STEPS):
        raise SkinError("tools/reapply.py has no step %s: the skin's place in the order is unknown" % (OWN_STEPS,))
    start = max(ids.index(s) for s in OWN_STEPS) + 1
    files = {}
    for pack in sorted(p for p in reapply.PACKS.iterdir() if p.is_dir()) if reapply.PACKS.is_dir() else []:
        root = pack / "data"
        for f in root.rglob("*.mcfunction"):
            rel = f.relative_to(root).parts
            if len(rel) > 2 and rel[1] == "function":
                files.setdefault("%s:%s" % (rel[0], "/".join(rel[2:])[:-len(".mcfunction")]), []).append(f)
    by_chunk = {}
    for (x, y, z), planned in points.items():
        by_chunk.setdefault((x >> 4, z >> 4), []).append(((x, y, z), planned))
    owned = {}

    def hit(sid, a, b, blk, mode, filt):
        x0, y0, z0 = (min(a[i], b[i]) for i in range(3))
        x1, y1, z1 = (max(a[i], b[i]) for i in range(3))
        for cx in range(x0 >> 4, (x1 >> 4) + 1):
            for cz in range(z0 >> 4, (z1 >> 4) + 1):
                for (x, y, z), planned in by_chunk.get((cx, cz), ()):
                    if not (x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1) or (x, y, z) in owned:
                        continue
                    if mode == "outline" and x0 < x < x1 and y0 < y < y1 and z0 < z < z1:
                        continue
                    if mode == "replace" and filt and filt.split("[")[0] not in {b_.split("[")[0] for b_ in planned}:
                        continue
                    if mode == "keep" and not any(b_ in ("minecraft:air", "minecraft:cave_air") for b_ in planned):
                        continue
                    owned[(x, y, z)] = sid

    for sid, _title, acts in todo[start:]:
        seen, stack = set(), [v for kind, v in reversed(acts) if kind == "fn"]
        while stack:
            fid = stack.pop()
            if fid in seen:
                continue
            seen.add(fid)
            for f in files.get(fid, ()):
                for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
                    ln = ln.strip()
                    if not ln or ln.startswith("#"):
                        continue
                    if ln.startswith("fill "):
                        m = LATER_FILL.match(ln)
                        if m:
                            g = [int(v) for v in m.groups()[:6]]
                            hit(sid, g[:3], g[3:6], m.group(7), m.group(8), m.group(9))
                    elif ln.startswith("setblock "):
                        m = LATER_SET.match(ln)
                        if m:
                            g = [int(v) for v in m.groups()[:3]]
                            hit(sid, g, g, m.group(4), m.group(5) if m.group(5) == "keep" else None, None)
                    else:
                        stack.extend(FN_REF.findall(ln))
    return owned


def verify(world):
    """Fail closed: the plan's own samples, every kind of thing the build makes, and the entity count."""
    import build_audit
    import runtime_guard
    runtime_guard.check(world, "read")
    if not PLAN.is_file():
        print("FAIL: no derived/rift_skin/plan.json: run the build first")
        return 1
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    kinds = {c[4] for c in p["checks"]}
    need = {"skin surface", "vein", "sky tear", "sky shard", "entrance path", "railing rail"}
    if not need <= kinds:
        print("FAIL: the plan checks %s, which is not everything the build makes (%s missing)" % (
            sorted(kinds), sorted(need - kinds)))
        return 1
    if not p.get("entities_expected") or not p.get("biome_cells"):
        print("FAIL: the plan expects %s entities and %s biome cells" % (
            p.get("entities_expected"), p.get("biome_cells")))
        return 1
    # the samples a later step rebuilds are that step's to check, not the skin's
    try:
        owned = later_owned({(x, y, z): allowed for x, y, z, allowed, _ in p["checks"]})
    except SkinError as e:
        print("FAIL: %s" % e)
        return 1
    if owned:
        steps_ = {}
        for sid in owned.values():
            steps_[sid] = steps_.get(sid, 0) + 1
        print("%-24s %7d samples, left to the later step that rebuilds them (%s)" % (
            "rebuilt later", len(owned), ", ".join("%s %d" % kv for kv in sorted(steps_.items()))))
    left = {c[4] for c in p["checks"] if (c[0], c[1], c[2]) not in owned}
    if not need <= left:
        print("FAIL: later steps rebuild every sample of %s: nothing of it is left to check" % sorted(need - left))
        return 1
    W = build_audit.World(world)
    by, bad = {}, {}
    for x, y, z, allowed, what in p["checks"]:
        if (x, y, z) in owned:
            continue
        got = W.block(x, y, z)
        ok = got in allowed
        by.setdefault(what, [0, 0])[0 if ok else 1] += 1
        if not ok:
            bad.setdefault(what, []).append((x, y, z, got))
    for k in sorted(by):
        good, wrong = by[k]
        print("%-24s %7d of %7d as planned%s" % (k, good, good + wrong, ("   e.g. %s" % bad[k][:2]) if wrong else ""))
    n = entity_count(world, p["entity_area_tag"])
    print("%-24s %7d, expected %d" % ("entities", n, p["entities_expected"]))
    ns_ = entity_count(world, p.get("sheet_tag", "rift_sheet"))
    print("%-24s %7d, expected %d" % ("portal sheets", ns_, p.get("sheets_expected", 0)))
    total = sum(b for _, b in by.values()) + (0 if n == p["entities_expected"] else 1) \
        + (0 if ns_ == p.get("sheets_expected", 0) else 1)
    print("rift skin: %s" % ("clean" if total == 0 else "%d MISMATCHES" % total))
    return 0 if total == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "verify"))
    ap.add_argument("--source-root")
    ap.add_argument("--server-dir")
    ap.add_argument("--world")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        if not a.world:
            ap.error("verify needs --world <stopped world copy>")
        return verify(a.world)
    plan = build(a.source_root, a.server_dir)
    order, border, nfx = write(plan)
    for k, v in sorted(plan.counts.items()):
        print("  %-40s %9d" % (k, v))
    print("  %-40s %9d" % ("commands", len(plan.lines)))
    print("rift skin: %d block functions, %d biome functions, %d entities" % (len(order), len(border), nfx))
    if a.server_dir is None:
        print("  mod blocks NOT checked against a server's jars (no --server-dir)")
    print("  views:", json.dumps(plan.views))
    return 0


if __name__ == "__main__":
    sys.exit(main())
