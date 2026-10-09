#!/usr/bin/env python
"""The Drowned Quarry's offline audit: the emitted pack REPLAYED block by block against the plan, re-derived here.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/drowned_quarry.py for
geometry. It reads data/drowned_quarry.json, the canonical heightmap (tools/ground.py), the lake's painted basin
(tools/water_mask.py: data/landmarks.json lake_tilpey), data/legendaries.json, data/spawns.json, data/spawn_blocks.json,
data/world_probes.json and the Cobblemon 1.8.0 jar, derives the place it expects with its own predicate (a brush walked
along the road's centre line, not the generator's rectangle union), builds a block array of the NATURAL world (rock up to
the ground, lake water over a painted column up to the lake's level, air elsewhere), REPLAYS the generated carve
functions' fills and setblocks into it, and compares. The only thing taken from the generator is its output (the pack
and the steps it hands tools/reapply.py), which is what is being checked. Mutating the generator's geometry (a hall one
block taller, a void cut under thin cover, a floor over air, a shell that skips a layer) fails a named check here with
data/drowned_quarry.json untouched; tests/test_drowned_quarry.py does exactly that.

What is checked, each from the data and the heightmap, never from the pack:

  footprint    no write lands outside the planned box (the void and its floor, widened by the margin)
  void         what the carve opens in natural rock is exactly the planned void (less the full blocks the dressing puts
               in it, counted); nothing outside the plan is opened; the pillars stand
  flooded      every planned void voxel holds water or a waterlogged block after the carve: no air anywhere in the build
  waterlog     every non-full block the pack writes is waterlogged
  seal         past the portal every voxel within the margin of the void is rock (written or natural) or the void itself:
               no air, no unwritten natural cavity and no lake water touches the flooded working anywhere but the open
               cutting west of the portal
  containment  a flood fill from the Gyarados's spot through every non-solid voxel reaches the lake and reaches NO air
               voxel: the only water the build adds is joined to the lake and to nothing dry
  mouth        the road's open cutting lies under the lake's PAINTED water (tools/water_mask.py claim), the floor is
               the stated depth under the surface, and the portal is where the first run's roof becomes rock
  reach        26-neighbour shortest swim, through the replayed water, from the nearest place a player can breathe
               (a wadeable shelf column) to the portal, the hall's door and the Gyarados's spot, against the air each rung
               of the water ladder holds (no mount, Surf, Dive) at the measured swim speeds
  gyarados     the spot is in the sump's water; the scaled model (read from the jar) fits the air over it and the pit
  wake         nothing outside the cave and no part of the road is within the trigger radius of the spot
  level        the level is above the band and the six-badge cap by the stated margins and exactly the eight-badge
               cap, so the level cap is the gate; the gate flag is a real progression flag
  palette      every block the pack writes is vanilla, not a spawn-conditioning block in data/spawn_blocks.json, and not
               concrete (contract C4)
  keeper       the summon guard keys on the tag and the species; a guardian is never held, woken, settled or killed; the
               return clock is written only by load and the keeper's first sighting; the wake merges Unbattleable 0b and
               no PoseType; the chain acts, then de-duplicates, then releases; the step holds nothing across the chain
  probes       every block probe in data/world_probes.json agrees with the replayed world
  functions    every function passes tools/function_limits.py and is reached from the load tag or the steps

NOT checked, and it needs a running server (docs/world-building/DROWNED_QUARRY.md 'Not verified'): that the fills land,
that nothing under the ground is a natural cavity the shell did not reach (the shell is the proof: it is filled before
the void and reaches margin blocks beyond it), that the lake's painted water is in the exported world, that the Gyarados
is twice normal size, sleeps, wakes and can be battled under water, and what a player sees.

  python tools/drowned_quarry_audit.py [--pack build/datapacks/cobblers_drowned_quarry] [--source-root R]
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import re
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data" / "drowned_quarry.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_drowned_quarry"
JAR_DIR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods")
AIR, WATER, SOLID, PART = 0, 1, 2, 3          # PART: a non-full block, which must be waterlogged
NONFULL = re.compile(r"(lantern|chain|_wall|_slab|_stairs|_fence|_trapdoor|_pane|iron_bars|ladder|torch)\b")
FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)(?: (\w+))?\s*$")
SETB = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)(?: (\w+))?\s*$")
CALL = re.compile(r"^function ([a-z0-9_.-]+:[a-z0-9_./-]+)\s*$")


def classify(block):
    name = block.split("[")[0]
    if name == "minecraft:air":
        return AIR
    if name == "minecraft:water":
        return WATER
    if NONFULL.search(name):
        return PART
    return SOLID


# ------------------------------------------------------------------ the expectation, derived here


def expected(doc, ground, level):
    """(box, void, pillars, floor_layer_cols, pit_cols, G, lake, notes): the planned place, by the audit's own predicate."""
    g = doc["geometry"]
    m, fl = g["margin"], g["floor_y"]
    hw, rh = g["road"]["half_width"], g["road"]["height"]
    hall, pit = g["hall"], g["pit"]
    pts = g["road"]["points"]
    pad = m + 3
    xs = [p[0] for p in pts] + hall["x"] + [pit["centre"][0] - pit["radius"], pit["centre"][0] + pit["radius"]]
    zs = [p[1] for p in pts] + hall["z"] + [pit["centre"][1] - pit["radius"], pit["centre"][1] + pit["radius"]]
    x0, x1 = min(xs) - hw - pad, max(xs) + hw + pad
    z0, z1 = min(zs) - hw - pad, max(zs) + hw + pad
    y0 = fl - pit["depth"] - pad
    y1 = max(fl + max(hall["height"], rh) + pad, level + 1)
    nx, nz, ny = x1 - x0 + 1, z1 - z0 + 1, y1 - y0 + 1
    G = ground.box(x0, z0, x1, z1)
    void = np.zeros((ny, nz, nx), bool)
    # the road: a (2*hw+1) square brush walked cell by cell along the centre line
    cols = np.zeros((nz, nx), bool)
    for (xa, za), (xb, zb) in zip(pts, pts[1:]):
        n = max(abs(xb - xa), abs(zb - za))
        for i in range(n + 1):
            cx = xa + (xb - xa) * i // max(n, 1)
            cz = za + (zb - za) * i // max(n, 1)
            cols[cz - hw - z0:cz + hw + 1 - z0, cx - hw - x0:cx + hw + 1 - x0] = True
    void[fl + 1 - y0:fl + rh + 1 - y0] |= cols[None]
    pillars = np.zeros_like(void)
    hallc = np.zeros((nz, nx), bool)
    hallc[hall["z"][0] - z0:hall["z"][1] + 1 - z0, hall["x"][0] - x0:hall["x"][1] + 1 - x0] = True
    void[fl + 1 - y0:fl + hall["height"] + 1 - y0] |= hallc[None]
    h = hall["pillars"]["half"]
    for px in hall["pillars"]["xs"]:
        for pz in hall["pillars"]["zs"]:
            pillars[fl - y0:fl + hall["height"] + 1 - y0, pz - h - z0:pz + h + 1 - z0, px - h - x0:px + h + 1 - x0] = True
    void &= ~pillars
    pc = np.zeros((nz, nx), bool)
    zz, xx = np.mgrid[z0:z1 + 1, x0:x1 + 1]
    pc = np.hypot(xx - pit["centre"][0], zz - pit["centre"][1]) <= pit["radius"] + 1e-9
    void[fl - pit["depth"] + 1 - y0:fl + 1 - y0] |= pc[None]
    floor_cols = void[fl + 1 - y0] & ~pc
    return (x0, y0, z0, x1, y1, z1), void, pillars, floor_cols, pc, G


def natural_world(doc, box, G):
    """Class array of the NATURAL world over the box: rock up to the ground, lake water above a painted column up to the
    lake's level, air elsewhere. Returns (cls, lake_level, painted)."""
    import water_mask as W
    x0, y0, z0, x1, y1, z1 = box
    b = W.bodies()[doc["water_body"]]
    level = b["level_y"]
    painted = np.zeros(G.shape, bool)
    for zi in range(G.shape[0]):
        z = z0 + zi
        for xi in range(G.shape[1]):
            if G[zi, xi] < level and W.in_polygons(b["basin"], x0 + xi, z):
                painted[zi, xi] = True
    Y = np.arange(y0, y1 + 1)[:, None, None]
    cls = np.full((y1 - y0 + 1, G.shape[0], G.shape[1]), AIR, np.int8)
    cls[Y <= G[None]] = SOLID
    cls[(Y > G[None]) & (Y <= level) & painted[None]] = WATER
    return cls, level, painted


# ------------------------------------------------------------------ the replay


def read_functions(pack):
    fns = {}
    base = Path(pack) / "data"
    for f in base.rglob("*.mcfunction"):
        rel = f.relative_to(base).parts
        fns["%s:%s" % (rel[0], "/".join(rel[2:])[:-len(".mcfunction")])] = f.read_text(encoding="utf-8").splitlines()
    return fns


def replay(fns, entry, box, cls, problems):
    """Run `entry` (and the functions it calls) over a copy of `cls`. Returns (cls, written boolean array, pal, names):
    `pal` holds, per voxel, the index in `names` of the last block written there (-1 = natural)."""
    x0, y0, z0, x1, y1, z1 = box
    out = cls.copy()
    written = np.zeros(cls.shape, bool)
    pal = np.full(cls.shape, -1, np.int16)
    names = []
    seen = set()
    outside = [0]

    def idx(block):
        if block not in names:
            names.append(block)
        return names.index(block)

    def run(name):
        if name in seen:
            return
        seen.add(name)
        for raw in fns[name]:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            c = CALL.match(line)
            if c:
                run(c.group(1))
                continue
            m = FILL.match(line)
            if m:
                a = [int(v) for v in m.groups()[:6]]
                xa, xb = sorted((a[0], a[3]))
                ya, yb = sorted((a[1], a[4]))
                za, zb = sorted((a[2], a[5]))
                if xa < x0 or xb > x1 or za < z0 or zb > z1 or ya < y0 or yb > y1:
                    outside[0] += 1
                    continue
                sl = (slice(ya - y0, yb - y0 + 1), slice(za - z0, zb - z0 + 1), slice(xa - x0, xb - x0 + 1))
                out[sl] = classify(m.group(7))
                written[sl] = True
                pal[sl] = idx(m.group(7))
                continue
            s_ = SETB.match(line)
            if s_:
                x, y, z = int(s_.group(1)), int(s_.group(2)), int(s_.group(3))
                if not (x0 <= x <= x1 and z0 <= z <= z1 and y0 <= y <= y1):
                    outside[0] += 1
                    continue
                out[y - y0, z - z0, x - x0] = classify(s_.group(4))
                written[y - y0, z - z0, x - x0] = True
                pal[y - y0, z - z0, x - x0] = idx(s_.group(4))
                continue
            problems.append("replay: %s has a line the audit cannot read: %s" % (name, line[:80]))
    run(entry)
    if outside[0]:
        problems.append("footprint: %d write(s) outside the audit's whole box, ignored" % outside[0])
    return out, written, pal, names


def dilate(mask, m):
    out = mask
    for axis in range(3):
        acc = out.copy()
        for k in range(1, m + 1):
            a = np.roll(out, k, axis)
            b = np.roll(out, -k, axis)
            idx = [slice(None)] * 3
            idx[axis] = slice(0, k)
            a[tuple(idx)] = False
            idx[axis] = slice(-k, None)
            b[tuple(idx)] = False
            acc |= a | b
        out = acc
    return out


# ------------------------------------------------------------------ reach: shortest swim through the replayed water

STEPS = [(dx, dy, dz, math.sqrt(dx * dx + dy * dy + dz * dz)) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
         if (dx, dy, dz) != (0, 0, 0)]


def shortest(open_, sources, targets, box):
    """Multi-source Dijkstra over `open_` (bool [y,z,x]) with 26-neighbour moves. A diagonal move needs both axis-aligned
    neighbours it cuts past open on at least one side (a swimmer cannot squeeze between two solid corners). Returns the
    distance in blocks to each target (or None)."""
    ny, nz, nx = open_.shape
    dist = {}
    pq = []
    for s in sources:
        dist[s] = 0.0
        heapq.heappush(pq, (0.0, s))
    want = set(targets)
    got = {}
    while pq and len(got) < len(want):
        d, (y, z, x) = heapq.heappop(pq)
        if d > dist.get((y, z, x), 1e18):
            continue
        if (y, z, x) in want:
            got[(y, z, x)] = d
        for dx, dy, dz, w in STEPS:
            ny_, nz_, nx_ = y + dy, z + dz, x + dx
            if not (0 <= ny_ < ny and 0 <= nz_ < nz and 0 <= nx_ < nx) or not open_[ny_, nz_, nx_]:
                continue
            if (dx and dy and dz) or (dx and dz) or (dx and dy) or (dy and dz):
                # a corner cut: at least one of the face neighbours on each used axis pair must be open
                ok = True
                if dx and dy:
                    ok &= bool(open_[y, z, x + dx] or open_[y + dy, z, x])
                if dx and dz:
                    ok &= bool(open_[y, z, x + dx] or open_[y, z + dz, x])
                if dy and dz:
                    ok &= bool(open_[y, z + dz, x] or open_[y + dy, z, x])
                if not ok:
                    continue
            nd = d + w
            key = (ny_, nz_, nx_)
            if nd < dist.get(key, 1e18):
                dist[key] = nd
                heapq.heappush(pq, (nd, key))
    return {t: got.get(t) for t in targets}


# ------------------------------------------------------------------ the jar (optional)


def jar_model(species):
    """(hitbox (width, height), cube bounds in blocks (x, y, z)) from the Cobblemon 1.8.0 jar, or None when it is absent."""
    jars = sorted(JAR_DIR.glob("Cobblemon-fabric-1.8*.jar")) if JAR_DIR.is_dir() else []
    if not jars:
        return None
    z = zipfile.ZipFile(jars[0])
    sp = [n for n in z.namelist() if n.endswith("/species/%s.json" % species) or re.search(r"/species/[^/]+/%s\.json$" % species, n)]
    if not sp:
        return None
    d = json.loads(z.read(sp[0]))
    geo = [n for n in z.namelist() if re.search(r"/pokemon/models/\d+_%s/%s(_male)?\.geo\.json$" % (species, species), n)]
    if not geo:
        return None
    g = json.loads(z.read(sorted(geo)[0]))
    mn, mx = [1e9] * 3, [-1e9] * 3
    for geom in g["minecraft:geometry"]:
        for bone in geom["bones"]:
            for c in bone.get("cubes", []):
                for i in range(3):
                    mn[i] = min(mn[i], c["origin"][i])
                    mx[i] = max(mx[i], c["origin"][i] + c["size"][i])
    return (d["hitbox"]["width"], d["hitbox"]["height"]), [(mx[i] - mn[i]) / 16.0 for i in range(3)]


# ------------------------------------------------------------------ the audit


def audit(doc=None, ground=None, pack=PACK, jar=True):
    import ground as G_
    doc = doc or json.loads(DATA.read_text(encoding="utf-8"))
    ground = ground or G_.load()
    problems, notes = [], []
    g, mo = doc["geometry"], doc["monster"]
    m, fl = g["margin"], g["floor_y"]
    fns = read_functions(pack)
    if "cobblers:%s/carve" % doc["folder"] not in fns:
        return ["pack: no carve function in %s" % pack], notes
    import water_mask as W0
    level0 = W0.bodies()[doc["water_body"]]["level_y"]
    box, void, pillars, floor_cols, pit_cols, G = expected(doc, ground, level0)
    x0, y0, z0, x1, y1, z1 = box
    nat, level, painted = natural_world(doc, box, G)
    after, written, pal, names = replay(fns, "cobblers:%s/carve" % doc["folder"], box, nat, problems)
    notes.append("lake %s level y%d; box x%d..%d z%d..%d y%d..%d; planned void %d voxels, %d pillars"
                 % (doc["water_body"], level, x0, x1, z0, z1, y0, y1, int(void.sum()), int(pillars.sum())))

    # footprint: the planned void, its floor layer and the pit floor, widened by the margin
    plan = void | pillars
    foot = dilate(plan, m)
    stray = written & ~foot
    if stray.any():
        ys, zs, xs = np.nonzero(stray)
        problems.append("footprint: %d written voxel(s) outside the planned box (first x%d y%d z%d)"
                        % (int(stray.sum()), int(xs[0]) + x0, int(ys[0]) + y0, int(zs[0]) + z0))

    # void: what the carve opens in natural rock is the planned void (less dressing's full blocks)
    nat_solid = nat == SOLID
    opened = nat_solid & (after != SOLID)
    extra = opened & ~void
    if extra.any():
        ys, zs, xs = np.nonzero(extra)
        problems.append("void: %d natural rock voxel(s) opened that the plan does not (first x%d y%d z%d)"
                        % (int(extra.sum()), int(xs[0]) + x0, int(ys[0]) + y0, int(zs[0]) + z0))
    not_open = void & nat_solid & (after == SOLID)
    dress_full = int(not_open.sum())
    total_void = int(void.sum())
    notes.append("void: %d of %d planned void voxels hold a full block the dressing placed (%.1f%%)"
                 % (dress_full, total_void, 100.0 * dress_full / max(1, total_void)))
    if dress_full > 0.08 * total_void:
        problems.append("void: the dressing fills %d of %d void voxels (over 8%%): the rooms are not rooms" % (dress_full, total_void))
    if not (after[pillars] == SOLID).all():
        problems.append("void: %d pillar voxel(s) are not solid after the carve" % int((after[pillars] != SOLID).sum()))

    # flooded: no air in the build, every planned void voxel holds water, a waterlogged block or a full block
    air_in = void & (after == AIR)
    if air_in.any():
        ys, zs, xs = np.nonzero(air_in)
        problems.append("flooded: %d planned void voxel(s) hold AIR after the carve (first x%d y%d z%d)"
                        % (int(air_in.sum()), int(xs[0]) + x0, int(ys[0]) + y0, int(zs[0]) + z0))
    for b in names:
        if classify(b) == PART and "waterlogged=true" not in b:
            problems.append("waterlog: %s is a non-full block the pack writes without waterlogged=true" % b)

    # seal: every voxel within the margin of the void that is natural rock under the top-two-blocks line must have been
    # WRITTEN solid by the pack (the shell), whatever the natural rock holds; and none within the margin is air
    px = g["road"]["portal_x"]
    X = np.arange(x0, x1 + 1)[None, None, :]
    Yv = np.arange(y0, y1 + 1)[:, None, None]
    near = dilate(void & (X >= px), m) & ~void & ~pillars
    under = Yv <= (G[None] - g["keep_natural_top"])
    unshelled = near & under & ~(written & (after == SOLID))
    if unshelled.any():
        ys, zs, xs = np.nonzero(unshelled)
        problems.append("seal: %d voxel(s) of rock within %d of the flooded working past the portal were not written solid by the carve "
                        "(first x%d y%d z%d): a natural cavity there would not be sealed"
                        % (int(unshelled.sum()), m, int(xs[0]) + x0, int(ys[0]) + y0, int(zs[0]) + z0))
    near_air = near & (after == AIR)
    if near_air.any():
        ys, zs, xs = np.nonzero(near_air)
        problems.append("seal: %d AIR voxel(s) within %d of the flooded working past the portal (first x%d y%d z%d)"
                        % (int(near_air.sum()), m, int(xs[0]) + x0, int(ys[0]) + y0, int(zs[0]) + z0))
    # the portal is where the roof first has margin + 1 blocks of ground over it for good: derived here from the heightmap
    cover = np.where(void, G[None] - Yv, 10 ** 6).min(axis=(0, 1))
    first_ok = None
    for xi in range(len(cover) - 1, -1, -1):
        if cover[xi] >= m + 1:
            first_ok = xi + x0
        else:
            break
    notes.append("mouth: the roof has margin+1 = %d blocks of ground over it for good from x%s; the record's portal_x is %d"
                 % (m + 1, first_ok, px))
    if first_ok != px:
        problems.append("mouth: portal_x %d is not where the roof first has %d blocks of ground over it for good (x%s)" % (px, m + 1, first_ok))
    # no air touches any void or waterlogged voxel anywhere (6-neighbour)
    wet = void | (after == WATER) & written
    air = after == AIR
    for axis in range(3):
        for sh in (1, -1):
            nb = np.roll(air, sh, axis)
            idx = [slice(None)] * 3
            idx[axis] = slice(0, 1) if sh == 1 else slice(-1, None)
            nb[tuple(idx)] = False
            leak = nb & void
            if leak.any():
                ys, zs, xs = np.nonzero(leak)
                problems.append("seal: %d void voxel(s) touch air (a leak into dry space), first x%d y%d z%d"
                                % (int(leak.sum()), int(xs[0]) + x0, int(ys[0]) + y0, int(zs[0]) + z0))
    # containment: flood from the spot through the CARVED space only (non-solid and not the lake's natural water). It must
    # touch the lake only at the open cutting, and no air voxel may be in it or touch it.
    spot = mo["spot"]
    sx, sy, sz = int(math.floor(spot[0])), int(spot[1]), int(math.floor(spot[2]))
    open_ = after != SOLID
    carved = open_ & ~(nat == WATER)
    if not carved[sy - y0, sz - z0, sx - x0]:
        problems.append("gyarados: the spot x%d y%d z%d is not in the carved water" % (sx, sy, sz))
    else:
        reach = np.zeros_like(open_)
        stack = [(sy - y0, sz - z0, sx - x0)]
        reach[stack[0]] = True
        ny, nz, nx = open_.shape
        iface = []
        while stack:
            y, z, x = stack.pop()
            for dy, dz, dx in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                a_, b_, c_ = y + dy, z + dz, x + dx
                if not (0 <= a_ < ny and 0 <= b_ < nz and 0 <= c_ < nx):
                    iface.append(("box border", c_ + x0, a_ + y0, b_ + z0))
                    continue
                if reach[a_, b_, c_]:
                    continue
                if carved[a_, b_, c_]:
                    reach[a_, b_, c_] = True
                    stack.append((a_, b_, c_))
                elif open_[a_, b_, c_]:
                    iface.append(("lake", c_ + x0, a_ + y0, b_ + z0))
        cut_off = void & (after != SOLID) & ~reach & ~(nat == WATER)
        if cut_off.any():
            ys, zs, xs = np.nonzero(cut_off)
            problems.append("void: %d planned void voxel(s) are cut off from the rest (first x%d y%d z%d): a sealed pocket"
                            % (int(cut_off.sum()), int(xs[0]) + x0, int(ys[0]) + y0, int(zs[0]) + z0))
        n_air = int((reach & (after == AIR)).sum())
        if n_air:
            ys, zs, xs = np.nonzero(reach & (after == AIR))
            problems.append("containment: the carved water holds %d AIR voxel(s) (first x%d y%d z%d)" % (n_air, int(xs[0]) + x0, int(ys[0]) + y0, int(zs[0]) + z0))
        borders = [i for i in iface if i[0] == "box border"]
        if borders:
            problems.append("containment: the carved water reaches the audit box's border at %s" % (borders[0][1:],))
        lake = [i for i in iface if i[0] == "lake"]
        if not lake:
            problems.append("containment: the carved water never meets the lake: the way in is not open")
        deep = [i for i in lake if i[1] > px]
        if deep:
            problems.append("containment: the carved water meets the lake %d time(s) east of portal_x %d (first x%d y%d z%d): a hole in the roof or the wall"
                            % (len(deep), px, deep[0][1], deep[0][2], deep[0][3]))
        # every non-solid voxel that touches the carved water is the lake's WATER, never air
        air_touch = [i for i in iface if after[i[2] - y0, i[3] - z0, i[1] - x0] == AIR]
        if air_touch:
            problems.append("containment: the carved water touches AIR at x%d y%d z%d" % air_touch[0][1:])
        notes.append("containment: %d carved voxels reachable from the spot, %d interface voxels with the lake (x %d..%d), 0 air"
                     % (int(reach.sum()), len(lake), min([i[1] for i in lake] or [0]), max([i[1] for i in lake] or [0])))

    # mouth: the open cutting is under the lake's PAINTED water; depths
    import water_mask as W
    pts = g["road"]["points"]
    cut_cols = [(x, z) for x in range(pts[0][0], px) for z in range(pts[0][1] - g["road"]["half_width"], pts[0][1] + g["road"]["half_width"] + 1)]
    probs = W.claim(doc["water_body"], cut_cols, ground, min_submersion=0, label="open cutting")
    problems += ["mouth: " + p for p in probs[:3]]
    z_c = pts[0][1]
    depth_floor = level - fl
    notes.append("mouth: floor y%d is %d blocks under the surface (lake level y%d); the first road column x%d has ground y%d, "
                 "the portal x%d ground y%d over a roof at y%d"
                 % (fl, depth_floor, level, pts[0][0], ground(pts[0][0], z_c), px, ground(px, z_c), fl + g["road"]["height"]))
    if depth_floor < 20:
        problems.append("mouth: the floor is only %d under the surface, not a depth worth the name" % depth_floor)
    roof = fl + g["road"]["height"]
    thin = [(x, z) for x in range(px, pts[-1][0] + 1) for z in range(z0, z1 + 1) if void[roof - y0, z - z0, x - x0] and G[z - z0, x - x0] - roof < m + 1]
    if thin:
        problems.append("mouth: %d road column(s) from the portal in have less than %d blocks of ground over the roof (first %s)"
                        % (len(thin), m + 1, thin[0]))

    # reach
    air_cfg = doc["gate"]["numbers"]
    v5, v10 = air_cfg["swim_blocks_per_s"], air_cfg["dive_blocks_per_s"]
    # sources: the lake's top water voxel over ANY painted column in the corridor: a swimmer breathes at the surface wherever it is, and
    # surface swimming costs fatigue, not air
    corridor = np.zeros(open_.shape, bool)
    cz = pts[0][1]
    corridor[:, max(0, cz - 45 - z0):cz + 46 - z0, :] = True
    corridor &= (np.arange(x0, x1 + 1)[None, None, :] >= pts[0][0] - 12)
    walk = open_ & corridor
    sources = []
    for zi in range(max(0, cz - 45 - z0), min(G.shape[0], cz + 46 - z0)):
        for xi in range(G.shape[1]):
            if painted[zi, xi]:
                sources.append((level - y0, zi, xi))
    sources = [s for s in sources if walk[s]]
    notes.append("reach: %d breathable surface voxels (the lake's top water over every painted column of the corridor) feed the search" % len(sources))
    targets = {"portal": (fl + 3 - y0, pts[0][1] - z0, px - x0),
               "hall door": (fl + 3 - y0, pts[-1][1] - z0, g["hall"]["x"][0] - x0),
               "the Gyarados": (sy - y0, sz - z0, sx - x0)}
    # a coarse prune keeps the search small: the lake outside the road's corridor is not part of the shortest way
    dist = shortest(walk & (open_), sources, list(targets.values()), box)
    d = {k: dist[v] for k, v in targets.items()}
    for k, v in d.items():
        if v is None:
            problems.append("reach: no swim from the shelf to %s" % k)
    if all(v is not None for v in d.values()):
        nm, sf = air_cfg["no_mount_air_s"], air_cfg["surf_air_s"]
        rows = []
        for k, v in d.items():
            rows.append("%s %.0f blocks: one way %.1f s swimming / %.1f s Dive, round trip %.1f s / %.1f s"
                        % (k, v, v / v5, v / v10, 2 * v / v5, 2 * v / v10))
        notes.append("reach: " + "; ".join(rows))
        notes.append("reach: air held: no mount %d s, Surf %d s, Dive flat" % (nm, sf))
        # no mount: dead (first hit at nm, the lethal second one a second later) before the hall's door one way
        if d["hall door"] / v5 <= nm + 1:
            problems.append("reach: a swimmer with no mount reaches the hall door in %.1f s of %d s (+1 s) of air" % (d["hall door"] / v5, nm))
        # Surf: arrives with air left but needs more to leave than it has: it cannot go there and come back, let alone fight
        if 2 * d["the Gyarados"] / v5 <= sf:
            problems.append("reach: a Surf swimmer can reach the Gyarados and return in %.1f s of %d s of air" % (2 * d["the Gyarados"] / v5, sf))
        notes.append("reach: a Surf swimmer reaches the Gyarados with %.1f s of air left and needs %.1f s to leave; a no-mount swimmer is out of air %.1f s "
                     "before the hall door; a Dive swimmer arrives in %.1f s with air held flat"
                     % (sf - d["the Gyarados"] / v5, d["the Gyarados"] / v5, d["hall door"] / v5 - nm, d["the Gyarados"] / v10))
        # a Dive swimmer has flat air: the only budget is distance; it must be finite
        if d["the Gyarados"] > 400:
            problems.append("reach: the way is %.0f blocks: longer than a player will swim for a Pokemon" % d["the Gyarados"])

    # gyarados: the model fits
    r = pit_radius = g["pit"]["radius"]
    cx, cz2 = g["pit"]["centre"]
    in_pit = math.hypot(spot[0] - (cx + 0.5), spot[2] - (cz2 + 0.5)) <= r + 0.5
    if not (in_pit and g["floor_y"] - g["pit"]["depth"] < sy <= g["floor_y"]):
        problems.append("gyarados: the spot %s is not inside the sump" % (spot,))
    mod = jar_model(mo["species"]) if jar else None
    if mod is None:
        notes.append("gyarados: the jar's model not read (jar absent or species not found): fit NOT checked")
    else:
        (hw_, hh_), cube = mod
        s = mo["scale_modifier"]
        need_h, need_w = cube[1] * s, max(cube[0], cube[2]) * s
        avail_h = (fl + g["hall"]["height"]) - (g["floor_y"] - g["pit"]["depth"])
        notes.append("gyarados: model cube bounds %.1f x %.1f x %.1f at scale %s = %.1f x %.1f x %.1f; hitbox %.1f x %.1f; "
                     "air over the sump floor %d, pit %d across" % (cube[0], cube[1], cube[2], s, cube[0] * s, cube[1] * s, cube[2] * s,
                                                                    hw_ * s, hh_ * s, avail_h, 2 * r + 1))
        if need_h > avail_h + 1e-6:
            problems.append("gyarados: the model needs %.1f blocks of height at scale %s and the sump and hall give %d" % (need_h, s, avail_h))
        if need_w > 2 * r + 1:
            problems.append("gyarados: the model needs %.1f across and the pit is %d" % (need_w, 2 * r + 1))
        col = after[:, sz - z0, sx - x0]
        top = sy
        while top + 1 <= y1 and col[top + 1 - y0] != SOLID:
            top += 1
        if top - sy + 1 < math.ceil(hh_ * s):
            problems.append("gyarados: the hitbox (%.1f high) does not fit the %d blocks of water over the spot" % (hh_ * s, top - sy + 1))

    # wake: nothing outside the cave and no road is within the trigger of the spot
    tr = mo["trigger_radius"]
    road_cols_only = void.copy()
    Xg, Zg = np.arange(x0, x1 + 1)[None, None, :], np.arange(z0, z1 + 1)[None, :, None]
    Yg = np.arange(y0, y1 + 1)[:, None, None]
    outside_hall = ~((Xg >= g["hall"]["x"][0]) & (Xg <= g["hall"]["x"][1]) & (Zg >= g["hall"]["z"][0]) & (Zg <= g["hall"]["z"][1]))
    dd = np.sqrt((Xg + 0.5 - spot[0]) ** 2 + (Yg - spot[1]) ** 2 + (Zg + 0.5 - spot[2]) ** 2)
    road_near = road_cols_only & outside_hall & (dd <= tr + 1)
    if road_near.any():
        problems.append("wake: %d voxel(s) of the road lie within %d of the spot, so the road wakes it" % (int(road_near.sum()), tr))
    standing = np.sqrt((np.arange(x0, x1 + 1)[None, :] + 0.5 - spot[0]) ** 2 + (G + 1 - spot[1]) ** 2 + (np.arange(z0, z1 + 1)[:, None] + 0.5 - spot[2]) ** 2)
    if (standing <= tr + 1).any():
        problems.append("wake: ground a player can stand on is within %d of the spot" % (tr + 1))
    else:
        notes.append("wake: nearest standing ground %.1f blocks from the spot, trigger %d" % (float(standing.min()), tr))
    hall_air = void & ~outside_hall
    in_trigger = hall_air & (dd <= tr)
    notes.append("wake: %d of the hall's %d water voxels are inside the trigger" % (int(in_trigger.sum()), int(hall_air.sum())))
    if not in_trigger.any():
        problems.append("wake: no part of the hall is inside the trigger")

    # level and gate
    caps = json.loads((ROOT / "data" / "legendaries.json").read_text(encoding="utf-8"))["level_caps"]["upper_bound_by_badges"]
    sp = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    band = next(s for s in sp["subregions"] if s["id"] == "tilpey_waters")["level_band"]
    lv = mo["level"]
    notes.append("level: %d; lake band %d-%d; caps by badges 6/7/8: %s/%s/%s" % (lv, band["minimum"], band["maximum"], caps["6"], caps["7"], caps["8"]))
    if lv < band["maximum"] + 10:
        problems.append("level: %d is under the lake's own band top %d + 10" % (lv, band["maximum"]))
    if lv < caps["6"] + 10:
        problems.append("level: %d is under the six-badge cap %d + 10 (the badge Dive is taught at)" % (lv, caps["6"]))
    if lv != caps["8"]:
        problems.append("level: %d is not the eight-badge cap %d: the level cap would not gate the catch at gym8_cleared" % (lv, caps["8"]))
    if lv <= caps["7"]:
        problems.append("level: %d is catchable at seven badges (cap %d)" % (lv, caps["7"]))
    flags = {f["id"] for f in json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))["flags"]}
    for fk in ("dive_flag",):
        if doc["gate"][fk] not in flags:
            problems.append("gate: %s %r is not a flag in data/progression.json" % (fk, doc["gate"][fk]))
    if doc["monster"]["catch_gate"] not in flags:
        problems.append("gate: catch_gate %r is not a flag in data/progression.json" % doc["monster"]["catch_gate"])

    # palette
    sb = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]
    used = {b.split("[")[0] for b in names}
    for b in sorted(used):
        if not b.startswith("minecraft:"):
            problems.append("palette: %s is not vanilla" % b)
        if b in sb and b != "minecraft:water":     # water IS the lake; every water spawn names it
            problems.append("palette: %s is a spawn-conditioning block in data/spawn_blocks.json" % b)
        if "concrete" in b or "barrier" in b:
            problems.append("palette: %s (contract C4: no concrete; no barrier)" % b)
    notes.append("palette: %d distinct blocks, none spawn-conditioning: %s" % (len(used), ", ".join(sorted(x.split(":")[1] for x in used))))

    problems += keeper_checks(doc, fns, pack)
    problems += probe_checks(doc, pal, names, after, box)
    problems += function_checks(doc, fns, pack)
    return problems, notes


def nat_water_mask(nat):
    return nat == WATER


# ------------------------------------------------------------------ the keeper, the chain, the step, the probes


def text_of(fns, name):
    return "\n".join(fns.get(name, []))


def keeper_checks(doc, fns, pack):
    out = []
    ns, fo = doc["namespace"], doc["folder"]
    mo = doc["monster"]
    P = "%s:%s" % (ns, fo)
    need = ("load", "keeper", "keep", "hold", "wake", "settle", "spawn", "spawn_at", "bind", "place", "place_look", "place_act", "place_done")
    for n in need:
        if "%s/%s" % (P, n) not in fns:
            out.append("keeper: function %s/%s is missing" % (P, n))
    if out:
        return out
    keep, hold, wake = text_of(fns, P + "/keep"), text_of(fns, P + "/hold"), text_of(fns, P + "/wake")
    spawn, bind, load_ = text_of(fns, P + "/spawn"), text_of(fns, P + "/bind"), text_of(fns, P + "/load")
    act = text_of(fns, P + "/place_act")
    tag, gtag = mo["tag"], mo["guardian_tag"]
    # the summon guard: tag and species, never a bare distance
    if re.search(r"if entity @e\[[^\]]*distance=\.\.\d+\]\s+run function .*spawn", keep):
        out.append("keeper: a spawn guarded by a bare distance (R14C's failure)")
    if "type=cobblemon:pokemon,tag=%s" % tag not in keep or ('Species:"cobblemon:%s"' % mo["species"]) not in keep:
        out.append("keeper: keep does not key on the tag AND the species")
    if 'Species:"cobblemon:%s"' % mo["species"] not in spawn:
        out.append("keeper: the freshly spawned one is not found by species")
    if "tag=!%s" % gtag not in keep or "tag=!%s" % gtag not in hold + keep:
        out.append("keeper: a guardian is not excluded (hold/kill must carry tag=!%s)" % gtag)
    for n in ("wake", "settle", "bind", "hold"):
        if "kill" in text_of(fns, "%s/%s" % (P, n)):
            out.append("keeper: %s kills something" % n)
    if re.search(r"run kill @e\[(?![^\]]*tag=!%s)" % re.escape(gtag), keep):
        out.append("keeper: keep kills a Pokemon that may be a guardian")
    for n in ("keeper", "hold", "wake", "settle", "spawn", "spawn_at"):
        if "#gone" in text_of(fns, "%s/%s" % (P, n)):
            out.append("keeper: %s writes the return clock: only load, keep and bind may" % n)
    if "unless score #gone" not in load_:
        out.append("keeper: load must set the return clock only when it was never set (a restart must not move it)")
    if "scoreboard players set #resp" not in load_ or str(doc["monster"]["keeper"]["cooldown_ticks"]) not in load_:
        out.append("keeper: load does not set the return clock's length from the record")
    if "matches ..%d" % (mo["keeper"]["absent_passes"] - 1) not in keep:
        out.append("keeper: keep does not wait absent_passes loaded passes before it counts the Pokemon gone")
    if "distance=..%d" % mo["keeper"]["spawn_clear"] not in keep or "run return 0" not in keep:
        out.append("keeper: it does not refuse to return in front of a player")
    if "Unbattleable:0b" not in wake or "PoseType" in wake or "Unbattleable:1b" in wake:
        out.append("keeper: the wake must merge Unbattleable 0b and no PoseType")
    if "NoAI:0b" in wake:
        out.append("keeper: the wake must leave NoAI on (the serpent holds its sump)")
    D_ = mo["dormant_tag"]
    if not re.search(r"@s\[tag=%s\] if entity @a\[[^\]]*distance=\.\.%d[^\]]*\] run function %s/wake" % (re.escape(D_), mo["trigger_radius"], re.escape(P)), hold):
        out.append("keeper: hold does not wake a DORMANT one for a player inside the trigger radius")
    if not re.search(r"@s\[tag=!%s\] unless entity @a\[[^\]]*distance=\.\.%d[^\]]*\] run function %s/settle" % (re.escape(D_), mo["keeper"]["settle_radius"], re.escape(P)), hold):
        out.append("keeper: hold does not settle an AWAKE one only when nobody is within the settle radius")
    kp = text_of(fns, P + "/keeper")
    if not re.search(r"store result score #now \S+ run time query gametime", kp) or "schedule function %s/keeper" % P not in kp:
        out.append("keeper: the keeper loop neither reads the game time nor reschedules itself")
    if "distance=..%d" % mo["trigger_radius"] not in hold:
        out.append("keeper: hold does not wake at the record's trigger radius")
    if "$spawnpokemonat" not in text_of(fns, P + "/spawn_at") or "level=%d" % mo["level"] not in text_of(fns, P + "/spawn_at"):
        out.append("keeper: the spawn is not a macro line of the record's level")
    if "scale_modifier=%s" % mo["scale_modifier"] not in text_of(fns, P + "/spawn_at"):
        out.append("keeper: the spawn does not carry the record's scale_modifier")
    if "spawnpokemonat" in "\n".join(l for n, ls in fns.items() for l in ls if not l.startswith("$") and not l.startswith("#")):
        out.append("keeper: a plain spawnpokemonat line outside the macro (spawns nothing at server start, EXP-046)")
    if "uncatchable" in text_of(fns, P + "/spawn_at"):
        out.append("keeper: the spawn is uncatchable: the level cap is the gate")
    # chain: act guarded by the tag, de-duplication, release
    if "unless entity @e[type=cobblemon:pokemon,tag=%s]" % tag not in act:
        out.append("chain: the act summons without checking for the tagged Gyarados")
    done = text_of(fns, P + "/place_done")
    if "forceload remove" not in done or "kill @e" not in done:
        out.append("chain: place_done neither de-duplicates nor releases")
    # the step
    import drowned_quarry as _dq  # the STEPS are the generator's output, which is what is checked
    steps = _dq.placement_steps(doc)
    kinds = [s[0] for s in steps]
    if kinds[:4] != ["cmd", "wait", "fn", "cmd"] or not steps[0][1].startswith("forceload add") or not steps[3][1].startswith("forceload remove"):
        out.append("step: it does not hold, carve and release before the chain starts")
    if steps[0][1].split(" ", 2)[2] != steps[3][1].split(" ", 2)[2]:
        out.append("step: the forceload released is not the forceload held")
    if ("fn", "%s/place" % P) not in steps or steps[-1][0] != "check":
        out.append("step: the chain is not started and read back")
    if not any(s == ("fn", P + "/carve") for s in steps):
        out.append("step: the carve is not run")
    return out


def probe_checks(doc, pal, names, after, box):
    out = []
    x0, y0, z0, x1, y1, z1 = box
    p = ROOT / "data" / "world_probes.json"
    places = json.loads(p.read_text(encoding="utf-8"))["places"] if p.exists() else {}
    rows = places.get("drowned_quarry")
    if not rows:
        return ["probes: data/world_probes.json has no 'drowned_quarry' place (run tools/drowned_quarry.py probes --write)"]
    nb = ne = 0
    for r in rows:
        if "block" in r:
            nb += 1
            x, y, z, want = r["block"]
            if not (x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1):
                out.append("probes: %s is outside the audited box" % r["what"])
                continue
            pi = int(pal[y - y0, z - z0, x - x0])
            got = names[pi] if pi >= 0 else None
            cl = after[y - y0, z - z0, x - x0]
            if want == "minecraft:water":
                ok = cl == WATER
            elif got is not None:
                ok = got == want
            else:
                # not written by the pack: only a natural solid may be expected, as stone (the shell)
                ok = cl == SOLID and want == "minecraft:stone"
            if not ok:
                out.append("probes: %s at %d %d %d expects %s, the replay has %s" % (r["what"], x, y, z, want, got or cl))
        else:
            ne += 1
            if r["count"] != 1 or doc["monster"]["tag"] not in r["entity"]:
                out.append("probes: the entity probe does not count the one tagged Gyarados")
    if nb < 6 or ne != 1:
        out.append("probes: %d block probe(s) and %d entity probe(s): too few to say the place is in the world" % (nb, ne))
    return out


def function_checks(doc, fns, pack):
    import function_limits
    out = []
    for name, lines in fns.items():
        for n, cmd, why in function_limits.check_lines(lines, where=name):
            out.append("functions: %s:%d %s: %s" % (name, n, cmd[:60], why))
    # every function is reached from the load tag, a step or another function's text
    P = "%s:%s" % (doc["namespace"], doc["folder"])
    import drowned_quarry as _dq
    reached = {P + "/load"} | {v for kind, v in _dq.placement_steps(doc) if kind == "fn"}
    text = "\n".join(l for ls in fns.values() for l in ls if not l.strip().startswith("#"))
    refs = set(re.findall(r"([a-z0-9_.-]+:[a-z0-9_./-]+)", text))
    for name in sorted(fns):
        if name not in reached and name not in refs:
            out.append("functions: %s is run by nothing" % name)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--source-root")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    import ground as G
    doc = json.loads(Path(a.data).read_text(encoding="utf-8"))
    problems, notes = audit(doc, G.load(a.source_root), Path(a.pack))
    if not a.quiet:
        for n in notes:
            print("  note: " + n)
    for p in problems:
        print("PROBLEM " + p)
    print("drowned_quarry_audit: %s" % ("%d problem(s)" % len(problems) if problems else "clean"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
