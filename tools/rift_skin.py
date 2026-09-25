#!/usr/bin/env python
"""The Rift's block pass: everything a height cannot carry, laid over the sculpted shape.

The shape is in the heightmap (tools/rift_heightmap.py), so this pass never cuts or raises ground. It only:

  - skins what can be seen: the surface of every column the sculpt moved, and the exposed face below it
  - lays the one-block crack grooves on the floor, the veins and the debris
  - hangs the sky tear and its shards, and sets the portal-sheet glimpses
  - opens the entrance paths and marks each guard's trailhead
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
    top = H[zz, xx]
    bottom = np.maximum(low[zz, xx] + 1, top - sk["face_depth"])
    bottom = np.minimum(bottom, top - sk["depth"] + 1)
    band = sk["band"]
    n_fill = 0
    for lo, hi, wxi, wzi in zip(bottom.tolist(), top.tolist(), wx.tolist(), wz.tolist()):
        y = lo
        while y <= hi:
            y2 = min(hi, y + band - 1 - (y % band))
            u = unit(wxi, y // band, wzi, 11)
            b = streak if unit(wxi, y // band, wzi, 12) < 1.0 / pal["streak"]["one_in"] \
                else rock[min(len(rock) - 1, int(u * len(rock)))]
            plan.lines.append("fill %d %d %d %d %d %d %s" % (wxi, y, wzi, wxi, y2, wzi, b))
            n_fill += 1
            y = y2 + 1
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
                    plan.count("entrance path columns")
                    if j == 0 and d == 0 and dw == 0:
                        plan.checks.append((x, y, z, ["minecraft:dirt_path"], "entrance path"))
        gx, gz = int(round(rx - nx * 16)), int(round(rz - nz * 16))
        gix, giz = gx - X0, gz - Z0
        gy = int(H[giz, gix]) + 1 if (0 <= gix < shape[1] and 0 <= giz < shape[0]) else 150
        plan.entities.append(
            'summon minecraft:armor_stand %.1f %d %.1f {CustomName:\'"%s (placeholder)"\','
            'CustomNameVisible:1b,NoGravity:1b,Invulnerable:1b,Tags:["%s","%s"]}'
            % (gx + 0.5, gy, gz + 0.5, e.get("guard", "Rift guard"), spec["portal_sheets"]["tag"], "rift_fx_all"))
        plan.views["%s: the trailhead" % e["id"]] = [gx, gy + 2, gz]
    plan.count("entrance trailheads", len(ent))

    # ---- the portal sheets: glimpses set deep in a tear in a solid face
    ps = spec["portal_sheets"]
    sheer = [i for i, (a, b, k) in enumerate(sc["segments"]) if k == "sheer"]
    sites = []
    step = max(1, len(ring) // (ps["count"] + 1))
    for i in range(ps["count"]):
        k = (i + 1) * step
        rx, rz = ring[k]
        nx, nz = nrm[k]
        ix, iz = rx - X0, rz - Z0
        if not (0 <= ix < shape[1] and 0 <= iz < shape[0]):
            continue
        y = int(H[iz, ix])
        # a narrow slot into the face, and the sheet two blocks deeper than its mouth
        sx, sz = int(round(rx - nx * 2)), int(round(rz - nz * 2))
        for dy in range(2, 8):
            plan.lines.append("fill %d %d %d %d %d %d minecraft:air" % (sx, y + dy, sz, sx, y + dy, sz))
        yaw = math.degrees(math.atan2(-nx, nz))
        plan.entities.append(
            'summon minecraft:block_display %.1f %.1f %.1f {block_state:{Name:"%s"},'
            'brightness:{sky:15,block:15},view_range:%.1ff,width:6f,height:6f,'
            'transformation:{left_rotation:[0f,%.4ff,0f,%.4ff],right_rotation:[0f,0f,0f,1f],'
            'translation:[-2.5f,0f,0f],scale:[5f,5f,1f]},Tags:["%s","%s"]}'
            % (sx + 0.5, y + 2.0, sz + 0.5, ps["block"], ps["view_range"],
               math.sin(math.radians(yaw) / 2), math.cos(math.radians(yaw) / 2),
               ps["tag"], "rift_fx_all"))
        sites.append([sx, y + 3, sz])
    plan.count("portal sheets", len(sites))
    plan.views["a glimpse"] = sites[0] if sites else [0, 0, 0]

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

    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    (bfn / "index.txt").write_text("\n".join(border) + "\n", encoding="utf-8")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps({
        "checks": [[x, y, z, a, w] for x, y, z, a, w in plan.checks],
        "entities_expected": len(plan.entities),
        "entity_area_tag": tag,
        "commands": len(plan.lines),
        "biome_cells": len(plan.biome_cells),
        "counts": plan.counts,
        "views": plan.views,
    }), encoding="utf-8")
    return order, border, len(plan.entities)


def entity_count(world, tag):
    """Entities of any type carrying the tag (the sheets and the trailhead guards), from the entity region files."""
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
    need = {"skin surface", "vein", "sky tear", "sky shard", "entrance path"}
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
    total = sum(b for _, b in by.values()) + (0 if n == p["entities_expected"] else 1)
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
