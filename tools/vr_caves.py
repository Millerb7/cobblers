#!/usr/bin/env python
"""Victory Road as one cave network, from data/vr_caves.json.

There is no path. Caverns are scattered through a band round the old spine's line, joined by meandering tunnels into
a graph with loops, and six zones (the Dark, the Drowned Gallery, the Slagworks, the Bloom, the Raw Tear, the
Abandoned Cut) fight over every column: each zone's hold falls off from its core, noise pushes the borders about, and
the strongest wins. The floor climbs with progress from the Deep's mouth (y1) to the foot of the exit (y64), no
column more than one block above its neighbour, and the last stretch is a ravine open to the sky onto the League's
apron. Everything is one voxel model, checked whole before anything is written:

  cover      at least cover.min of canonical ground over every roof's shell (tools/ground.py, never a world)
  clearance  rock between the network and the Deep's traced pit (except the mouth) and the EXP-033 rig
  policy     every spawn-conditioning block the model uses is whitelisted in data/spawn_block_policy.json for
             Victory Road with a reason
  seal       every open cell (air, fluid, fitting) has all six neighbours in the model, or is open to the sky over
             the ravine or to the pit at the mouth
  fluids     water and lava bounded on every side but up; the lava falls' sources on every side but down
  walk-out   from the mouth a player can walk, swim and fall to the apron; from anywhere reachable they can get back
             to the mouth or on to the apron; every floor cell is reachable; no floor cell touches lava without a lip
  records    data/habitat_blocks.json holds the Habitat Block tiles and data/rewards.json the finds where the model
             puts them (`records --write` writes both from the model)

Written pass-major (shell, air, floor, fluid, fittings) across every tile, as tools/vr_regions.py did.

  python tools/vr_caves.py report  [--source-root DIR]                 the checks and the counts; nothing written
  python tools/vr_caves.py records --write [--source-root DIR]         Habitat Block tiles and finds into data/
  python tools/vr_caves.py build   [--source-root DIR] [--server-dir DIR]   -> build/datapacks/cobblers_vr_caves
  python tools/vr_caves.py clear   [--source-root DIR]                 -> build/datapacks/cobblers_vr_clear: staging
             only, rock back into every cell the retired spine and regions wrote that the network does not
  python tools/vr_caves.py verify --world <stopped world copy> [--source-root DIR]   every cell of the model
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL                        # noqa: E402
from victory_road import installed_blocks, pick     # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "vr_caves.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_vr_caves"
CLEAR_OUT = ROOT / "build" / "datapacks" / "cobblers_vr_clear"
PLAN = ROOT / "derived" / "vr_caves" / "plan.json"
OLD_PACKS = (("cobblers_victory_road", "victory_road"), ("cobblers_vr_regions", "vr_regions"))
TILE = 64
PART = 3500
GX0, GX1, GZ0, GZ1, GY0, GY1 = 3340, 3820, 2460, 3120, -24, 116
NX, NZ, NY = GX1 - GX0 + 1, GZ1 - GZ0 + 1, GY1 - GY0 + 1
PASSES = ("shell", "air", "floor", "fluid", "fittings")
SHELL, AIRP, FLOORP, FLUIDP, FITP = 1, 2, 3, 4, 5
AIR, WATER, LAVA = "minecraft:air", "minecraft:water", "minecraft:lava"
OPEN = {AIR, WATER, LAVA, "minecraft:rail", "minecraft:moss_carpet", "minecraft:cave_vines",
        "minecraft:cave_vines_plant", "minecraft:spore_blossom", "minecraft:pointed_dripstone"}
PASSABLE = OPEN - {LAVA, "minecraft:pointed_dripstone"}
ROCK = "legendarymonuments:distortion_deepslate"
SCOPE = "Victory Road"

# The ground rule (tools/ground_rule.py): verify reads a stopped world copy to CHECK the build, never to place it.
WORLD_READS = {"verify", "main"}


class CaveError(Exception):
    pass


def base(b):
    return b.split("[", 1)[0]


# ------------------------------------------------------------------ noise, deterministic

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


def unit3(x, y, z, salt):
    """Per-cell hash in [0, 1) for numpy arrays."""
    a = (np.asarray(x, np.int64) * 73856093) ^ (np.asarray(y, np.int64) * 19349663) ^ (np.asarray(z, np.int64) * 83492791) \
        ^ np.int64((salt * 2654435761) & 0x7FFFFFFF)
    a &= 0x7FFFFFFF
    a = (a ^ (a >> 15)) * np.int64(2246822519) & 0x7FFFFFFF
    a = (a ^ (a >> 13)) * np.int64(3266489917) & 0x7FFFFFFF
    return (a & 0xFFFFFF) / float(0x1000000)


def field(seed, xs, zs, scale, octaves=3):
    """A smooth noise field in about [-1, 1] over the grid: sums of rotated sines, cheap and deterministic."""
    out = np.zeros(xs.shape, float)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        for k in range(3):
            th = u(seed, o, k, 1) * math.pi
            ph = u(seed, o, k, 2) * 2 * math.pi
            f = (2 ** o) / scale
            out += amp * np.sin((xs * math.cos(th) + zs * math.sin(th)) * f * 2 * math.pi + ph)
            tot += amp
        amp *= 0.5
    return out / tot * 1.7


def shifts(a, fill):
    """The four horizontal neighbours of a 2D array, padded with fill."""
    p = np.pad(a, 1, constant_values=fill)
    return p[2:, 1:-1], p[:-2, 1:-1], p[1:-1, 2:], p[1:-1, :-2]


def dilate(m, n):
    for _ in range(n):
        a, b, c, d = shifts(m, False)
        m = m | a | b | c | d
    return m


# ------------------------------------------------------------------ the plan in two dimensions

class Net:
    pass


def guide_progress(pts, XS, ZS):
    """Distance to the guide polyline and progress along it (0 at the mouth, 1 at its last point), per column."""
    d = np.full(XS.shape, 1e9)
    s = np.zeros(XS.shape)
    total = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    acc = 0.0
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        vx, vz = bx - ax, bz - az
        L2 = vx * vx + vz * vz
        L = math.sqrt(L2)
        t = np.clip(((XS - ax) * vx + (ZS - az) * vz) / L2, 0, 1)
        dd = np.hypot(XS - (ax + t * vx), ZS - (az + t * vz))
        better = dd < d
        d = np.where(better, dd, d)
        s = np.where(better, (acc + t * L) / total, s)
        acc += L
    return d, s


def plan2d(spec, source_root, have, rest_node=None):
    import ground as G
    import rift_deep as RD
    rng_seed = spec["seed"]
    net = Net()
    xs = np.arange(GX0, GX1 + 1)
    zs = np.arange(GZ0, GZ1 + 1)
    XS, ZS = np.meshgrid(xs, zs, indexing="ij")
    net.XS, net.ZS = XS, ZS
    g = G.load(source_root)
    ground = np.rint(g.box(GX0, GZ0, GX1, GZ1).astype(float)).astype(int).T      # [x, z]
    ex = spec["exit"]
    lx0, lz0, lx1, lz1 = ex["lot_rect"]
    in_lot = (XS >= lx0) & (XS <= lx1) & (ZS >= lz0) & (ZS <= lz1)
    ground = np.where(in_lot, ex["lot_y"], ground)
    net.ground, net.in_lot = ground, in_lot

    # the band, the pit and the rig
    dist, prog = guide_progress(spec["guide"]["points"], XS, ZS)
    band = dist <= spec["guide"]["band"]
    m, (PX0, PZ0, _a, _b), _n = RD.region_mask("the_deep", source_root)
    pit = np.zeros(XS.shape, bool)
    zi, xi = np.nonzero(m)
    px, pz = xi + PX0 - GX0, zi + PZ0 - GZ0
    ok = (px >= 0) & (px < NX) & (pz >= 0) & (pz < NZ)
    pit[px[ok], pz[ok]] = True
    net.pit = pit
    mx, my, mz = spec["mouth"]["at"]
    mouth_strip = (np.abs(XS - mx) <= 9) & (ZS >= mz - 60) & (ZS <= mz + 1)
    keep_out = dilate(pit, spec["clearance"]["pit"]) & ~mouth_strip
    rb = spec["rig"]["box"]
    c = spec["clearance"]["rig"]
    rig = (XS >= rb[0] - c) & (XS <= rb[3] + c) & (ZS >= rb[2] - c) & (ZS <= rb[5] + c)
    # nothing nearer the League than the foot of the climb but the ravine itself: under the lot the ground leaves no
    # headroom, and a cavern beside the ravine would be dragged up to its floor
    beyond = ZS < spec["exit"]["foot"][2] - 12
    env = (band | mouth_strip) & ~keep_out & ~rig & ~beyond
    net.env, net.prog, net.mouth_strip = env, prog, mouth_strip
    # under the pit's rim street the rock top is the tread at y66, not the heightmap
    net.roof_ground = np.where(pit & ~mouth_strip, 60, np.where(mouth_strip & pit, 66, ground))

    # zones: each core's hold, pushed about by noise; the Dark holds a constant floor
    zones = spec["zones"]
    W = []
    for zi_, z in enumerate(zones):
        if z["core"] is None:
            W.append(np.full(XS.shape, 0.30))
            continue
        cx, cz = z["core"]
        nx_ = field(rng_seed + 11 * zi_, XS, ZS, 90) * spec["collide"]["noise"]
        d = np.hypot(XS - cx, ZS - cz) / float(z["reach"])
        W.append(np.exp(-d * d) * (1 + nx_))
    W = np.array(W)
    order = np.argsort(-W, axis=0)
    first, second = order[0], order[1]
    w1 = np.take_along_axis(W, first[None], 0)[0]
    w2 = np.take_along_axis(W, second[None], 0)[0]
    dither = (w1 - w2) < spec["collide"]["dither"]
    coin = unit3(XS, 0, ZS, 77) < 0.5 * np.clip((spec["collide"]["dither"] - (w1 - w2)) / spec["collide"]["dither"], 0, 1)
    net.zone = np.where(dither & coin, second, first)
    net.W, net.strength = W, w1
    net.zones = zones

    # caverns: the fixed ones (each zone's core, the rest station, the mouth hall, the foot of the exit) and a
    # Poisson scatter through the band
    cv = spec["caverns"]
    nodes = []

    def add(x, z, r, hgt, kind, zone=None, floor=None):
        nodes.append({"x": int(x), "z": int(z), "r": int(r), "h": int(hgt), "kind": kind, "zone": zone, "floor": floor})

    add(mx, mz - 44, 16, 16, "mouth_hall", floor=2)
    fx, fy, fz = ex["foot"]
    add(fx, fz, 14, 12, "foot", floor=fy)
    for zi_, z in enumerate(zones):
        if z["core"] is not None:
            add(z["core"][0], z["core"][1], z["radius"], z["height"], "core", zone=zi_)
    # the rest station is first guessed at the middle of the guide; in a braided cave the shortest way through need
    # not pass there, so build() then hands the job to whichever existing cavern sits at the middle of the walked
    # route (rest_node). The node list is the same either way, so the network does not change under it.
    ii = np.argwhere(env & (np.abs(prog - 0.5) < 0.03) & (dist < 20))
    if len(ii) == 0:
        raise CaveError("no column at the middle of the guide for the rest station")
    i0, k0 = ii[len(ii) // 2]
    add(GX0 + int(i0), GZ0 + int(k0), 17, 12, "rest")
    cand = np.argwhere(env & (dist < spec["guide"]["band"] - 12))
    order_ = sorted(range(len(cand)), key=lambda n: u(rng_seed, int(cand[n][0]), int(cand[n][1])))
    for n in order_:
        i, k = cand[n]
        x, z = GX0 + int(i), GZ0 + int(k)
        if all(math.hypot(x - q["x"], z - q["z"]) >= cv["spacing"] for q in nodes):
            r = cv["radius"][0] + int((cv["radius"][1] - cv["radius"][0]) * u(rng_seed, x, z, 3))
            hh = cv["height"][0] + int((cv["height"][1] - cv["height"][0]) * u(rng_seed, x, z, 4))
            add(x, z, r, hh, "cavern")
    # floors by progress, zone and a little chance; heights cut to the rock over them
    fl = spec["floor"]
    for q in nodes:
        i, k = q["x"] - GX0, q["z"] - GZ0
        if q["zone"] is None and q["kind"] in ("cavern", "rest"):
            q["zone"] = int(net.zone[i, k])
        s = float(prog[i, k])
        trend = fl["from"] + (fl["to"] - fl["from"]) * (max(0.0, min(1.0, s)) ** fl["curve"])
        if q["floor"] is None:
            off = zones[q["zone"]].get("floor_offset", 0) if q["zone"] is not None else 0
            q["floor"] = int(round(trend + off + (u(rng_seed, q["x"], q["z"], 5) - 0.5) * 6))
        q["floor"] = max(1, q["floor"])
        r = q["r"]
        sub = net.roof_ground[max(0, i - r):i + r + 1, max(0, k - r):k + r + 1]
        top = int(sub.min()) - spec["cover"]["min"] - spec["cover"]["shell"]
        q["h"] = max(6, min(q["h"], top - q["floor"]))
        if q["floor"] + 6 > top:
            raise CaveError("cavern at (%d, %d) has no room under the rock: floor %d, roof limit %d"
                            % (q["x"], q["z"], q["floor"], top))
    if rest_node is not None:
        for q in nodes:
            if q["kind"] == "rest":
                q["kind"] = "cavern"
        # a zone's core that takes the rest station is still its zone's core for the find (rest_and_finds)
        nodes[rest_node]["was"] = nodes[rest_node]["kind"]
        nodes[rest_node]["kind"] = "rest"
    net.nodes = nodes

    # tunnels: a spanning tree, then loops
    tn = spec["tunnels"]
    pairs = []
    for a in range(len(nodes)):
        for b in range(a + 1, len(nodes)):
            d = math.hypot(nodes[a]["x"] - nodes[b]["x"], nodes[a]["z"] - nodes[b]["z"])
            if d <= tn["reach"]:
                pairs.append((d, a, b))
    pairs.sort()
    parent = list(range(len(nodes)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    edges, rest = [], []
    for d, a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
            edges.append((a, b))
        else:
            rest.append((d, a, b))
    if len({find(a) for a in range(len(nodes))}) != 1:
        raise CaveError("the caverns do not join into one network within %d blocks" % tn["reach"])
    for d, a, b in rest:
        if u(rng_seed, a, b, 6) < tn["loops"]:
            edges.append((a, b))
    # grades: pull the floors of a too-steep tunnel's ends together; the mouth hall and the foot stay put
    fixed = {n for n, q in enumerate(nodes) if q["kind"] in ("mouth_hall", "foot")}
    for _ in range(400):
        bad = 0
        for a, b in edges:
            A, B = nodes[a], nodes[b]
            L = max(1.0, math.hypot(A["x"] - B["x"], A["z"] - B["z"]) - 0.6 * (A["r"] + B["r"]))
            dy = B["floor"] - A["floor"]
            lim = fl["max_grade"] * L
            if abs(dy) > lim:
                bad += 1
                fix = (abs(dy) - lim) / 2.0 + 0.5
                sa = 1 if dy > 0 else -1
                if a not in fixed:
                    A["floor"] = int(round(A["floor"] + sa * fix * (1 if b not in fixed else 2)))
                if b not in fixed:
                    B["floor"] = int(round(B["floor"] - sa * fix * (1 if a not in fixed else 2)))
        if not bad:
            break
    else:
        raise CaveError("tunnel grades would not settle under %s" % fl["max_grade"])
    net.edges = edges

    # rasterise: caverns and tunnels into a floor, a height and a footprint
    wsum = np.zeros(XS.shape)
    fsum = np.zeros(XS.shape)
    hmax = np.zeros(XS.shape)
    owner = np.full(XS.shape, -1)        # the cavern a column belongs to, if any
    ownrr = np.full(XS.shape, 9.0)
    tunnel_of = np.full(XS.shape, -1)
    for n, q in enumerate(nodes):
        R = q["r"]
        i0, i1 = max(0, q["x"] - GX0 - int(R * 1.65)), min(NX, q["x"] - GX0 + int(R * 1.65) + 1)
        k0, k1 = max(0, q["z"] - GZ0 - int(R * 1.65)), min(NZ, q["z"] - GZ0 + int(R * 1.65) + 1)
        sx, sz = XS[i0:i1, k0:k1], ZS[i0:i1, k0:k1]
        th = np.arctan2(sz - q["z"], sx - q["x"])
        p1, p2 = u(rng_seed, n, 7) * 6.28, u(rng_seed, n, 8) * 6.28
        p3 = u(rng_seed, n, 18) * 6.28
        # ragged, not round: three harmonics and a fine noise, so no cavern reads as a circle on a map
        loc = R * (1 + 0.22 * np.sin(2 * th + p1) + 0.13 * np.sin(5 * th + p2) + 0.07 * np.sin(9 * th + p3)
                   + 0.10 * field(rng_seed + 40 + n, sx, sz, 11, 1))
        rr = np.hypot(sx - q["x"], sz - q["z"]) / loc
        inside = rr <= 1.0
        w = np.where(inside, (1.0 - rr) ** 2 + 0.05, 0)
        terr = spec["caverns"]["terrace"] * field(rng_seed + n, sx, sz, 23, 2)
        f = q["floor"] + np.rint(terr * rr)
        hh = 4 + (q["h"] - 4) * np.sqrt(np.clip(1 - rr ** 3, 0, 1))
        wsum[i0:i1, k0:k1] += w
        fsum[i0:i1, k0:k1] += w * f
        hmax[i0:i1, k0:k1] = np.where(inside, np.maximum(hmax[i0:i1, k0:k1], hh), hmax[i0:i1, k0:k1])
        better = inside & (rr < ownrr[i0:i1, k0:k1])
        owner[i0:i1, k0:k1] = np.where(better, n, owner[i0:i1, k0:k1])
        ownrr[i0:i1, k0:k1] = np.where(better, rr, ownrr[i0:i1, k0:k1])
    tunnels = []
    for e, (a, b) in enumerate(edges):
        A, B = nodes[a], nodes[b]
        L = math.hypot(A["x"] - B["x"], A["z"] - B["z"])
        nxp, nzp = -(B["z"] - A["z"]) / L, (B["x"] - A["x"]) / L
        # a gallery, not a tube: the line is bent at several points by independent amounts (Catmull-Rom through
        # them), its width swells into pockets, and its height changes with it
        nb = max(2, int(L / 22))
        ctrl = [(A["x"], A["z"])]
        for m in range(1, nb):
            t = m / float(nb)
            off = (u(rng_seed, a, b, m, 9) * 2 - 1) * tn["meander"] * math.sin(math.pi * t)
            ctrl.append((A["x"] + (B["x"] - A["x"]) * t + nxp * off, A["z"] + (B["z"] - A["z"]) * t + nzp * off))
        ctrl.append((B["x"], B["z"]))
        pts_ = [ctrl[0]] + ctrl + [ctrl[-1]]
        steps = int(L * 1.5) + 2
        hw0 = tn["half_width"][0] + (tn["half_width"][1] - tn["half_width"][0]) * u(rng_seed, a, b, 10)
        th0 = tn["height"][0] + (tn["height"][1] - tn["height"][0]) * u(rng_seed, a, b, 11)
        pocket = u(rng_seed, a, b, 19)
        path = []
        for sidx in range(steps + 1):
            t = sidx / float(steps)
            seg = min(len(ctrl) - 2, int(t * (len(ctrl) - 1)))
            lt = t * (len(ctrl) - 1) - seg
            p0, p1_, p2_, p3_ = pts_[seg], pts_[seg + 1], pts_[seg + 2], pts_[seg + 3]
            cr = lambda c: 0.5 * ((2 * p1_[c]) + (-p0[c] + p2_[c]) * lt + (2 * p0[c] - 5 * p1_[c] + 4 * p2_[c] - p3_[c]) * lt * lt
                                  + (-p0[c] + 3 * p1_[c] - 3 * p2_[c] + p3_[c]) * lt ** 3)
            px_, pz_ = cr(0), cr(1)
            swell = 3.5 * max(0.0, math.sin(t * math.pi * 2 * (1 + 2 * pocket) + a)) ** 4
            hw = max(2.0, hw0 + 1.5 * math.sin(t * 11 + a) + swell)
            f = A["floor"] + (B["floor"] - A["floor"]) * t
            path.append((px_, pz_, hw, f, th0 + 1.5 * math.sin(t * 7 + b) + swell))
        tunnels.append({"a": a, "b": b, "path": path})
        for (px_, pz_, hw, f, hh) in path[::1]:
            ri = int(hw) + 2
            i0, i1 = max(0, int(px_) - GX0 - ri), min(NX, int(px_) - GX0 + ri + 1)
            k0, k1 = max(0, int(pz_) - GZ0 - ri), min(NZ, int(pz_) - GZ0 + ri + 1)
            sx, sz = XS[i0:i1, k0:k1], ZS[i0:i1, k0:k1]
            d = np.hypot(sx - px_, sz - pz_) / hw
            inside = d <= 1.0
            w = np.where(inside, 0.35 * (1 - d) + 0.02, 0)
            wsum[i0:i1, k0:k1] += w
            fsum[i0:i1, k0:k1] += w * f
            hmax[i0:i1, k0:k1] = np.where(inside, np.maximum(hmax[i0:i1, k0:k1], hh * np.sqrt(np.clip(1 - d * d * 0.6, 0.3, 1))),
                                          hmax[i0:i1, k0:k1])
            tunnel_of[i0:i1, k0:k1] = np.where(inside & (tunnel_of[i0:i1, k0:k1] < 0), e, tunnel_of[i0:i1, k0:k1])
    net.tunnels = tunnels
    foot = wsum > 0
    F = np.where(foot, np.rint(fsum / np.maximum(wsum, 1e-9)), 0).astype(int)
    H = hmax
    # the mouth: from the pit's face at the Deep's floor north into the mouth hall
    ms = mouth_strip & (np.abs(XS - mx) <= 3) & (ZS >= mz - 44) & (ZS <= mz + 1)
    tt = np.clip((mz - ZS) / 44.0, 0, 1)
    F = np.where(ms, np.rint(my + (nodes[0]["floor"] - my) * tt), F).astype(int)
    H = np.where(ms, np.maximum(H, 6), H)
    foot = foot | ms
    # one body of cave: a ragged outline can pinch off an island beside its cavern, sealed and unreachable.
    # Keep the component the mouth is in; everything else goes back to rock.
    seen = np.zeros(foot.shape, bool)
    si, sk = mx - GX0, mz - 3 - GZ0
    dq = deque([(si, sk)])
    seen[si, sk] = True
    while dq:
        i, k = dq.popleft()
        for a2, b2 in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ii, kk = i + a2, k + b2
            if 0 <= ii < NX and 0 <= kk < NZ and foot[ii, kk] and not seen[ii, kk]:
                seen[ii, kk] = True
                dq.append((ii, kk))
    net.islands = int((foot & ~seen).sum())
    foot = seen
    net.owner, net.ownrr, net.tunnel_of = owner, ownrr, tunnel_of
    net.foot, net.F, net.H = foot, F, H
    return net


# ------------------------------------------------------------------ flats, smoothing, the ravine

def reach_bounds(net, mask, h, cap=110):
    """(h - d, h + d) for d the steps through the footprint from mask: what a flat at height h forces round it."""
    BIG = 10 ** 6
    d = np.where(mask, 0, BIG)
    for _ in range(cap):
        a, b, c, e = shifts(d, BIG)
        nd = np.where(net.foot, np.minimum(d, np.minimum(np.minimum(a, b), np.minimum(c, e)) + 1), BIG)
        if (nd == d).all():
            break
        d = nd
    return h - d, h + d


def lock_flats(net, spec):
    """Areas whose floor has to be flat before smoothing: the ravine (laid first), the rest station, the lakes and
    the lava pools. Each is only laid if it can coexist with every flat already laid (no two flats further apart in
    height than in steps): an impossible pair is a cliff the smoothing would have to invent, so the later, less
    important one is skipped and counted instead."""
    zones = spec["zones"]
    BIG = 10 ** 6
    lock = net.lock.copy()
    lowB = np.full(net.F.shape, -BIG)
    upB = np.full(net.F.shape, BIG)
    # the ravine's own locks bound everything
    for h in np.unique(net.F[lock]):
        lo, hi = reach_bounds(net, lock & (net.F == h), int(h))
        lowB, upB = np.maximum(lowB, lo), np.minimum(upB, hi)
    net.lakes, net.pools, net.rest, net.skipped_flats = [], [], None, []

    def fits(mask, h):
        return bool(((lowB[mask] <= h) & (upB[mask] >= h)).all())

    def lay(mask, h):
        nonlocal lowB, upB, lock
        net.F = np.where(mask, h, net.F)
        lock |= mask
        lo, hi = reach_bounds(net, mask, h)
        lowB, upB = np.maximum(lowB, lo), np.minimum(upB, hi)

    order = sorted(range(len(net.nodes)), key=lambda n: (net.nodes[n]["kind"] != "rest", net.nodes[n]["kind"] != "core", n))
    for n in order:
        q = net.nodes[n]
        zid = q["zone"]
        zname = zones[zid]["id"] if zid is not None else None
        mine = net.owner == n
        if q["kind"] == "rest":
            half = spec["rest"]["size"] // 2 + 2
            box = (np.abs(net.XS - q["x"]) <= half) & (np.abs(net.ZS - q["z"]) <= half)
            net.foot = net.foot | box
            net.H = np.where(box, np.maximum(net.H, 7), net.H)
            if not fits(box, q["floor"]):
                raise CaveError("the rest station cannot sit flat at y%d at (%d, %d)" % (q["floor"], q["x"], q["z"]))
            lay(box, q["floor"])
            net.rest = (q["x"], q["floor"], q["z"])
        elif zname == "drowned" and (q["kind"] == "core" or u(spec["seed"], n, 12) < zones[zid]["features"]["lakes"]["share"]):
            lake = mine & (net.ownrr <= 0.9) & net.foot
            if not lake.any() or not fits(lake, q["floor"]):
                net.skipped_flats.append(("lake", q["x"], q["z"]))
                continue
            lay(lake, q["floor"])
            net.lakes.append((n, q["floor"]))
        elif zname == "slagworks" and q["kind"] in ("core", "cavern"):
            pr = zones[zid]["features"]["pools"]["radius"]
            ang = u(spec["seed"], n, 13) * 6.28
            px = q["x"] + int(round(math.cos(ang) * q["r"] * 0.35))
            pz = q["z"] + int(round(math.sin(ang) * q["r"] * 0.35))
            flat = (np.hypot(net.XS - px, net.ZS - pz) <= pr + 3) & mine & net.foot
            if flat.sum() < 0.8 * math.pi * (pr + 3) ** 2 or not fits(flat, q["floor"]):
                net.skipped_flats.append(("pool", px, pz))
                continue
            lay(flat, q["floor"])
            net.pools.append((n, px, q["floor"], pz, pr))
    net.lock = lock


def smooth(net):
    """No floor column more than one block above or below a neighbour; locked flats hold.

    Lowering alone is enough for that (a <= b + 1 for every ordered pair is both directions at once), but a locked
    flat cannot be lowered, so its neighbours must be kept within reach of it: bounds are propagated out from every
    locked column through the footprint first (at least F_lock - d, at most F_lock + d), then the lowering clamp runs
    inside them. Two locks further apart in height than in steps cannot both hold: that is reported, not smoothed."""
    F, foot, lock = net.F.copy(), net.foot, net.lock
    BIG = 10 ** 6
    lowB = np.where(lock & foot, F, -BIG)
    upB = np.where(lock & foot, F, BIG)
    for _ in range(2000):
        a, b, c, d = shifts(lowB, -BIG)
        nl = np.where(foot, np.maximum(lowB, np.maximum(np.maximum(a, b), np.maximum(c, d)) - 1), -BIG)
        a, b, c, d = shifts(upB, BIG)
        nu = np.where(foot, np.minimum(upB, np.minimum(np.minimum(a, b), np.minimum(c, d)) + 1), BIG)
        if (nl == lowB).all() and (nu == upB).all():
            break
        lowB, upB = nl, nu
    clash = foot & (lowB > upB)
    if clash.any():
        i, k = np.argwhere(clash)[0]
        raise CaveError("two locked flats are closer in steps than in height near (%d, %d): at least %d and at most %d"
                        % (GX0 + i, GZ0 + k, lowB[i, k], upB[i, k]))
    F = np.where(foot, np.clip(F, lowB, upB), F)
    for _ in range(4000):
        a, b, c, d = shifts(np.where(foot, F, BIG), BIG)
        lo = np.minimum(np.minimum(a, b), np.minimum(c, d))
        nf = np.where(foot & ~lock, np.maximum(lowB, np.minimum(F, lo + 1)), F)
        if (nf == F).all():
            break
        F = nf
    else:
        raise CaveError("the floor would not settle")
    net.F = F.astype(int)


def ravine(net, spec):
    """The climb out: from the foot cavern up through the Rift floor, open to the sky, onto the apron."""
    ex = spec["exit"]
    x, yt, zt = ex["at"]
    fx, fy, fz = ex["foot"]
    half = ex["width"] // 2
    net.open_sky = np.zeros(net.F.shape, bool)
    for z in range(zt, fz + 1):
        t = (fz - z) / float(fz - zt)
        yz = int(round(fy + (yt - fy) * min(1.0, t * 1.12)))        # flush with the apron over the last stretch
        w = half + (0 if z <= 2512 else int(round(1.5 + 1.5 * math.sin(z * 0.21))))
        cx = x + (0 if z <= 2512 else int(round(4 * math.sin((z - 2512) * 0.07))))
        for xx in range(cx - w, cx + w + 1):
            i, k = xx - GX0, z - GZ0
            net.F[i, k] = yz
            net.foot[i, k] = True
            net.open_sky[i, k] = z < fz - 2
            net.lock[i, k] = True
    net.exit_cells = [(xx, yt, z) for z in range(zt, zt + 3) for xx in range(x - 2, x + 3)]


# ------------------------------------------------------------------ the volume

class Blocks:
    def __init__(self):
        self.names = [None]
        self.index = {}

    def __call__(self, b):
        if b not in self.index:
            self.index[b] = len(self.names)
            self.names.append(b)
        return self.index[b]


def build_model(spec, source_root, have, rest_node=None):
    net = plan2d(spec, source_root, have, rest_node)
    net.lock = np.zeros(net.F.shape, bool)
    ravine(net, spec)
    lock_flats(net, spec)
    smooth(net)
    zones = spec["zones"]
    pals = []
    for z in zones:
        pal = {k: pick(v, (z.get("fallbacks") or {}).get(v, v), have) for k, v in z["palette"].items()}
        pals.append(pal)
    B = Blocks()
    vol = np.zeros((NX, NZ, NY), np.int16)
    pas = np.zeros((NX, NZ, NY), np.int8)
    F, foot = net.F, net.foot
    cover = spec["cover"]
    # ceilings: floor plus height, under the rock; the ravine open
    # under the LOWEST ground within two columns: a column's shell rises to cover its neighbours' ceilings, so a
    # ceiling capped only by its own ground can lift a neighbour's shell into that neighbour's cover
    pg = np.pad(net.roof_ground, 2, mode="edge")
    gmin = np.minimum.reduce([pg[2 + a:NX + 2 + a, 2 + c:NZ + 2 + c] for a in range(-2, 3) for c in range(-2, 3)])
    Cc = np.minimum(F + np.rint(net.H).astype(int), gmin - cover["min"] - cover["shell"])
    Cc = np.where(net.open_sky, net.ground + 3, Cc)
    low = foot & ~net.open_sky & (Cc - F < 3)
    if low.any():
        i, k = np.argwhere(low)[0]
        raise CaveError("%d columns have under three blocks of headroom under the rock, e.g. (%d, %d): floor %d, "
                        "roof %d" % (low.sum(), GX0 + i, GZ0 + k, F[i, k], Cc[i, k]))
    net.C = Cc
    # beds: how far below the floor a column is dug (lakes, pools)
    bed = np.zeros(F.shape, int)
    for n, W_ in net.lakes:
        z = zones[net.nodes[n]["zone"]]
        mine = (net.owner == n) & (net.ownrr <= 0.8) & foot
        depth = z["features"]["lakes"]["depth"]
        q = net.nodes[n]
        dep = np.rint(1 + (depth - 1) * np.clip(1 - net.ownrr / 0.8, 0, 1) ** 0.8).astype(int)
        isl = np.hypot(net.XS - q["x"], net.ZS - q["z"]) <= (2.5 if q["kind"] == "core" else 0)
        bed = np.where(mine & ~isl, np.maximum(bed, dep), bed)
    for n, px, W_, pz, pr in net.pools:
        dd = np.hypot(net.XS - px, net.ZS - pz)
        ring_ok = net.foot & net.lock & (F == W_)
        # a pool only where its whole disc and lip were laid flat: otherwise lava would meet bare floor
        if not ring_ok[dd <= pr + 1].all():
            continue
        bed = np.where(dd <= pr, zones[net.nodes[n]["zone"]]["features"]["pools"]["depth"], bed)
    # a lake column only holds water if every neighbour is at the waterline or above, or water itself
    for _ in range(50):
        a, b, c, d = shifts(np.where(foot, F, -99), -99)
        wet = bed > 0
        aw, bw, cw, dw = shifts(wet, False)
        leak = wet & (((a < F) & ~aw) | ((b < F) & ~bw) | ((c < F) & ~cw) | ((d < F) & ~dw))
        if not leak.any():
            break
        bed = np.where(leak, 0, bed)
    net.bed = bed
    # the shell: over every footprint column and two round it, from under the deepest bed to over the highest roof
    f2 = dilate(foot, 2)
    big = 10 ** 6
    lo_src = np.where(foot, F - 1 - bed, big)
    # an open column's 'ceiling' is the sky; what its neighbours' shells have to cover is only up to the ground
    hi_src = np.where(foot, np.where(net.open_sky, np.where(net.in_lot, spec["exit"]["lot_y"] - 1, net.ground), Cc), -big)
    lo, hi = lo_src.copy(), hi_src.copy()
    for _ in range(2):
        for arr, fn, fill in ((lo, np.minimum, big), (hi, np.maximum, -big)):
            pass
    lo_d, hi_d = lo_src.copy(), hi_src.copy()
    for _ in range(2):
        a, b, c, d = shifts(lo_d, big)
        lo_d = np.minimum(lo_d, np.minimum(np.minimum(a, b), np.minimum(c, d)))
        a, b, c, d = shifts(hi_d, -big)
        hi_d = np.maximum(hi_d, np.maximum(np.maximum(a, b), np.maximum(c, d)))
        # diagonals too
    pa = np.pad(lo_d, 1, constant_values=big)
    lo_d = np.minimum.reduce([pa[1 + di:NX + 1 + di, 1 + dk:NZ + 1 + dk] for di in (-1, 0, 1) for dk in (-1, 0, 1)])
    pa = np.pad(hi_d, 1, constant_values=-big)
    hi_d = np.maximum.reduce([pa[1 + di:NX + 1 + di, 1 + dk:NZ + 1 + dk] for di in (-1, 0, 1) for dk in (-1, 0, 1)])
    shell_lo = lo_d - 2
    shell_hi = hi_d + 2
    # the ravine's walls stop at the ground (the sky is its roof), and at y87 on the apron
    open_near = near_open(net)
    sky_top = np.where(net.in_lot, spec["exit"]["lot_y"] - 1, net.ground)
    # beside the ravine the walls stop at the ground; everywhere else a shell stops at its own cover, which the
    # ceiling cap (lowest ground within two) guarantees is above every neighbour's ceiling
    shell_hi = np.where(open_near, np.minimum(shell_hi, sky_top),
                        np.minimum(shell_hi, net.roof_ground - cover["min"]))
    net.sky_top = sky_top
    zone = net.zone
    wall_noise = field(spec["seed"] + 500, net.XS, net.ZS, 17, 2)
    cols = np.argwhere(f2)
    for i, k in cols:
        zi_ = zone[i, k]
        pal = pals[zi_]
        wb = B(pal["wall_alt"] if wall_noise[i, k] > 0.55 else pal["wall"])
        y0, y1 = int(shell_lo[i, k]), int(shell_hi[i, k])
        if y1 < y0:
            continue
        vol[i, k, y0 - GY0:y1 - GY0 + 1] = wb
        pas[i, k, y0 - GY0:y1 - GY0 + 1] = SHELL
    net.shell_lo, net.shell_hi = shell_lo, shell_hi
    # air and floors
    fnoise = field(spec["seed"] + 600, net.XS, net.ZS, 7, 2)
    for i, k in np.argwhere(foot):
        pal = pals[zone[i, k]]
        f, c = F[i, k], Cc[i, k]
        fb = pal["floor_alt"] if fnoise[i, k] > 0.6 else pal["floor"]
        if zones[zone[i, k]]["id"] == "slagworks" and fnoise[i, k] < -1 + 2 * zones[zone[i, k]]["features"]["magma"]:
            fb = pal["burn"]
        vol[i, k, f - GY0:c - GY0 + 1] = B(AIR)
        pas[i, k, f - GY0:c - GY0 + 1] = AIRP
        if bed[i, k] > 0:
            d = bed[i, k]
            zid = zones[zone[i, k]]["id"]
            bb = pal.get("bed", pal["floor"])
            vol[i, k, f - 1 - d - GY0] = B(bb)
            pas[i, k, f - 1 - d - GY0] = FLOORP
        else:
            vol[i, k, f - 1 - GY0] = B(fb)
            pas[i, k, f - 1 - GY0] = FLOORP
    net.vol, net.pas, net.B, net.pals = vol, pas, B, pals
    features(net, spec)
    return net


def near_open(net):
    """Columns within five of the ravine, diagonals included: its walls, which rise to the ground, not a roof."""
    if not hasattr(net, "_near_open"):
        m = net.open_sky
        for _ in range(5):
            p = np.pad(m, 1, constant_values=False)
            m = np.logical_or.reduce([p[1 + a:NX + 1 + a, 1 + c:NZ + 1 + c] for a in (-1, 0, 1) for c in (-1, 0, 1)])
        net._near_open = m
    return net._near_open


def put(net, x, y, z, b, p):
    i, k, j = x - GX0, z - GZ0, y - GY0
    net.vol[i, k, j] = net.B(b)
    net.pas[i, k, j] = p


def at(net, x, y, z):
    i, k, j = x - GX0, z - GZ0, y - GY0
    if not (0 <= i < NX and 0 <= k < NZ and 0 <= j < NY):
        return None
    c = net.vol[i, k, j]
    return net.B.names[c] if c else None


def features(net, spec):
    zones, pals, F, C, foot, bed = spec["zones"], net.pals, net.F, net.C, net.foot, net.bed
    seed = spec["seed"]
    zid = {z["id"]: n for n, z in enumerate(zones)}
    net.finds, net.falls, net.lights = {}, [], []
    # water and lava into the dug beds
    for n, W_ in net.lakes:
        pass
    for i, k in np.argwhere(bed > 0):
        x, z = GX0 + i, GZ0 + k
        zname = zones[net.zone[i, k]]["id"]
        f = F[i, k]
        fluid = LAVA if any(math.hypot(x - px, z - pz) <= pr for _n, px, _w, pz, pr in net.pools) else WATER
        for y in range(f - bed[i, k], f):
            put(net, x, y, z, fluid, FLUIDP)
    # lips round the pools, and the falls
    for n, px, W_, pz, pr in net.pools:
        pal = pals[net.nodes[n]["zone"]]
        for i, k in np.argwhere((np.hypot(net.XS - px, net.ZS - pz) > pr) & (np.hypot(net.XS - px, net.ZS - pz) <= pr + 1) & foot):
            put(net, GX0 + i, F[i, k], GZ0 + k, pal["lip"], FLOORP)
        nf = zones[net.nodes[n]["zone"]]["features"]["falls"]
        for f in range(min(nf, 2)):
            ang = u(seed, n, f, 14) * 6.28
            fx, fz = px + int(round(math.cos(ang) * 2)), pz + int(round(math.sin(ang) * 2))
            i, k = fx - GX0, fz - GZ0
            top = int(C[i - 1:i + 2, k - 1:k + 2].max())
            for y in range(C[i, k] + 1, top + 1):
                put(net, fx, y, fz, AIR, AIRP)
            for di in (-1, 0, 1):
                for dk in (-1, 0, 1):
                    for y in range(top + 1, top + 3):
                        if (di, dk) != (0, 0) or y > top + 1:
                            if net.pas[i + di, k + dk, y - GY0] in (0, SHELL):
                                put(net, fx + di, y, fz + dk, pal["wall"], SHELL)
            put(net, fx, top + 1, fz, LAVA, FITP)
            net.falls.append((fx, top + 1, fz))
    XS, ZS = net.XS, net.ZS
    ceil_room = C - F
    # per-zone dressing, column by column, by a hash
    hsh = unit3(XS, 1, ZS, 900)
    hsh2 = unit3(XS, 2, ZS, 901)
    taken = np.zeros(F.shape, bool)
    taken |= bed > 0
    # the rest station's footprint and a ring round it stay clear
    if net.rest:
        rx, ry, rz = net.rest
        half = spec["rest"]["size"] // 2 + 2
        taken |= (np.abs(XS - rx) <= half) & (np.abs(ZS - rz) <= half)
    taken |= dilate(net.open_sky, 2)
    taken |= (np.abs(XS - spec["mouth"]["at"][0]) <= 5) & (ZS >= spec["mouth"]["at"][2] - 50)
    near_tunnel_center = np.zeros(F.shape, bool)
    for tnl in net.tunnels:
        for (px, pz, hw, f, hh) in tnl["path"]:
            i, k = int(round(px)) - GX0, int(round(pz)) - GZ0
            if 0 <= i < NX and 0 <= k < NZ:
                near_tunnel_center[i, k] = True
    # the Dark: dripstone teeth and stubs
    dark = (net.zone == zid["the_dark"]) & foot & ~taken & (ceil_room >= 8)
    for i, k in np.argwhere(dark & (hsh < zones[zid["the_dark"]]["features"]["dripstone"])):
        x, z = GX0 + i, GZ0 + k
        pal = pals[zid["the_dark"]]
        ln = 1 + int(3 * hsh2[i, k])
        c = C[i, k]
        for y in range(c - ln + 1, c + 1):
            put(net, x, y, z, pal["accent"], FLOORP)
        put(net, x, c - ln, z, pal["tip"] + "[vertical_direction=down,thickness=tip]", FITP)
        taken[i, k] = True
    # the Raw Tear: spires, teeth, veins in the floor
    tz = zid["raw_tear"]
    pal = pals[tz]
    tear = (net.zone == tz) & foot & ~taken
    for i, k in np.argwhere(tear & (hsh < zones[tz]["features"]["spires"]) & (ceil_room >= 10) & ~near_tunnel_center):
        x, z = GX0 + i, GZ0 + k
        hgt = 3 + int(6 * hsh2[i, k])
        for y in range(F[i, k], min(F[i, k] + hgt, C[i, k] - 3)):
            put(net, x, y, z, pal["crystal"], FLOORP)
        taken[i, k] = True
    for i, k in np.argwhere(tear & (hsh2 < zones[tz]["features"]["teeth"]) & (ceil_room >= 9)):
        x, z = GX0 + i, GZ0 + k
        ln = 2 + int(5 * hsh[i, k])
        for y in range(max(C[i, k] - ln + 1, F[i, k] + 4), C[i, k] + 1):
            put(net, x, y, z, pal["crystal"], FLOORP)
    vn = np.abs(field(seed + 700, XS, ZS, 21, 2))
    for i, k in np.argwhere(tear & (vn < zones[tz]["features"]["veins"]) & ~taken):
        put(net, GX0 + i, F[i, k] - 1, GZ0 + k, pal["vein"], FLOORP)
        net.lights.append((GX0 + i, F[i, k] - 1, GZ0 + k))
    # the Bloom: mushrooms, vines, blossoms, bushes, carpet, puddles
    bz = zid["bloom"]
    pal = pals[bz]
    fb = zones[bz]["features"]
    bloom = (net.zone == bz) & foot & ~taken
    mush = []
    for i, k in np.argwhere(bloom & (hsh < fb["mushrooms"]) & (ceil_room >= 9)):
        x, z = GX0 + i, GZ0 + k
        rc = 2 + int(3 * hsh2[i, k])
        f0 = F[i, k]
        fp = [(x + a, z + b) for a in range(-rc, rc + 1) for b in range(-rc, rc + 1) if math.hypot(a, b) <= rc]
        if not all(foot[a - GX0, b - GZ0] and not taken[a - GX0, b - GZ0] and abs(F[a - GX0, b - GZ0] - f0) <= 1 for a, b in fp):
            continue
        hs = min(9, min(C[a - GX0, b - GZ0] for a, b in fp) - f0 - 2)
        if hs < 4:
            continue
        cap = pal["cap_red"] if hsh2[i, k] < 0.5 else pal["cap_brown"]
        for y in range(f0, f0 + hs):
            put(net, x, y, z, pal["stem"], FLOORP)
        for a, b in fp:
            edge = math.hypot(a - x, b - z) > rc - 1
            light = (not edge) and u(seed, a, b, 15) < 0.25 and (a, b) != (x, z)
            put(net, a, f0 + hs, b, pal["cap_light"] if light else cap, FLOORP)
            if light:
                net.lights.append((a, f0 + hs, b))
            if edge and hs > 5:
                put(net, a, f0 + hs - 1, b, cap, FLOORP)
        for a, b in fp:
            taken[a - GX0, b - GZ0] = True
        taken[i, k] = True
        mush.append((rc, hs, x, z))
    net.mushrooms = mush
    for i, k in np.argwhere(bloom & (hsh2 < fb["vines"]) & (ceil_room >= 5)):
        x, z = GX0 + i, GZ0 + k
        c = C[i, k]
        ln = 1 + int(4 * hsh[i, k])
        if c - ln < F[i, k] + 2 or any(at(net, x, y, z) != AIR for y in range(c - ln, c + 1)):
            continue
        for n_, y in enumerate(range(c, c - ln, -1)):
            tip = n_ == ln - 1
            put(net, x, y, z, "minecraft:cave_vines[age=25,berries=true]" if tip else
                "minecraft:cave_vines_plant[berries=%s]" % ("true" if u(x, y, z, 16) < 0.4 else "false"), FITP)
        net.lights.append((x, c - ln + 1, z))
    for i, k in np.argwhere(bloom & (hsh < fb["blossoms"] + fb["mushrooms"]) & (hsh >= fb["mushrooms"])):
        x, z = GX0 + i, GZ0 + k
        if at(net, x, C[i, k], z) == AIR:
            put(net, x, C[i, k], z, "minecraft:spore_blossom", FITP)
    for i, k in np.argwhere(bloom & ~taken & (hsh2 > 1 - fb["bushes"])):
        x, z = GX0 + i, GZ0 + k
        if at(net, x, F[i, k], z) == AIR and bed[i, k] == 0:
            put(net, x, F[i, k], z, "minecraft:flowering_azalea" if hsh[i, k] < 0.4 else "minecraft:azalea", FITP)
            taken[i, k] = True
    # puddles: one deep, on dead-flat ground
    for i, k in np.argwhere(bloom & ~taken & (hsh > 1 - fb["puddles"])):
        cells = [(i + a, k + b) for a in range(-2, 3) for b in range(-2, 3) if a * a + b * b <= 5]
        f0 = F[i, k]
        ring = [(i + a, k + b) for a in range(-3, 4) for b in range(-3, 4)]
        if not all(foot[a, b] and F[a, b] == f0 and not taken[a, b] and bed[a, b] == 0 for a, b in ring):
            continue
        for a, b in cells:
            put(net, GX0 + a, f0 - 2, GZ0 + b, pal["puddle_bed"], FLOORP)
            put(net, GX0 + a, f0 - 1, GZ0 + b, WATER, FLUIDP)
            taken[a, b] = True
    for i, k in np.argwhere(bloom & ~taken & (hsh2 < fb["carpet"])):
        x, z = GX0 + i, GZ0 + k
        if at(net, x, F[i, k], z) == AIR and at(net, x, F[i, k] - 1, z) == pal["floor"]:
            put(net, x, F[i, k], z, pal["carpet"], FITP)
    # the Drowned Gallery: pillars in the lakes, lights on the bed
    dz = zid["drowned"]
    pal = pals[dz]
    for i, k in np.argwhere((net.zone == dz) & (bed >= 4) & (hsh < zones[dz]["features"]["pillars"])):
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                ii, kk = i + a, k + b
                if foot[ii, kk] and bed[ii, kk] > 0:
                    for y in range(F[ii, kk] - bed[ii, kk] - 1, C[ii, kk] + 1):
                        put(net, GX0 + ii, y, GZ0 + kk, pal["pillar"], FLOORP)
                    taken[ii, kk] = True
    for i, k in np.argwhere((net.zone == dz) & (bed >= 3) & (hsh2 < zones[dz]["features"]["bed_lights"]) & ~taken):
        put(net, GX0 + i, F[i, k] - bed[i, k] - 1, GZ0 + k, pal["light"], FLOORP)
        net.lights.append((GX0 + i, F[i, k] - bed[i, k] - 1, GZ0 + k))
    # the Abandoned Cut: props and a rail line along its tunnels, spoil heaps, lanterns
    cz_ = zid["abandoned_cut"]
    pal = pals[cz_]
    fc = zones[cz_]["features"]
    for tnl in net.tunnels:
        path = tnl["path"]
        for sidx in range(2, len(path) - 2):
            px, pz, hw, f, hh = path[sidx]
            i, k = int(round(px)) - GX0, int(round(pz)) - GZ0
            if not (0 <= i < NX and 0 <= k < NZ) or net.zone[i, k] != cz_ or taken[i, k] or bed[i, k] or net.owner[i, k] >= 0:
                continue
            dx = path[sidx + 1][0] - path[sidx - 1][0]
            dzv = path[sidx + 1][1] - path[sidx - 1][1]
            if sidx % fc["props"] == 0:
                nrm = math.hypot(dx, dzv) or 1
                qx, qz = -dzv / nrm, dx / nrm
                cells = []
                for t in range(-int(hw) - 1, int(hw) + 2):
                    a, b = int(round(px + qx * t)), int(round(pz + qz * t))
                    if foot[a - GX0, b - GZ0]:
                        cells.append((a, b))
                if len(cells) < 3:
                    continue
                beam_y = min(C[a - GX0, b - GZ0] for a, b in cells)
                if beam_y - max(F[a - GX0, b - GZ0] for a, b in cells) < 4:
                    continue
                axis = "x" if abs(qx) > abs(qz) else "z"
                for a, b in cells:
                    put(net, a, beam_y, b, pal["beam"] + "[axis=%s]" % axis, FLOORP)
                for a, b in (cells[0], cells[-1]):
                    for y in range(F[a - GX0, b - GZ0], beam_y):
                        put(net, a, y, b, pal["post"] + "[axis=y]", FLOORP)
                    taken[a - GX0, b - GZ0] = True
                if (sidx // fc["props"]) % 2 == 0:
                    mid = cells[len(cells) // 2]
                    put(net, mid[0], beam_y - 1, mid[1], pal["lamp"] + "[hanging=true]", FITP)
                    net.lights.append((mid[0], beam_y - 1, mid[1]))
            elif fc["rails"] and at(net, GX0 + i, F[i, k], GZ0 + k) == AIR and at(net, GX0 + i, F[i, k] - 1, GZ0 + k) not in (None, AIR) \
                    and u(seed, i, k, 17) > 0.1:
                shape = "east_west" if abs(dx) >= abs(dzv) else "north_south"
                put(net, GX0 + i, F[i, k], GZ0 + k, pal["rail"] + "[shape=%s]" % shape, FITP)
                taken[i, k] = True
    for i, k in np.argwhere((net.zone == cz_) & foot & ~taken & (hsh < fc["spoil"]) & (ceil_room >= 6)):
        for a in range(-2, 3):
            for b in range(-2, 3):
                hgt = 2 - int(math.hypot(a, b))
                ii, kk = i + a, k + b
                if hgt <= 0 or not foot[ii, kk] or taken[ii, kk] or bed[ii, kk]:
                    continue
                for y in range(F[ii, kk], F[ii, kk] + hgt):
                    if at(net, GX0 + ii, y, GZ0 + kk) == AIR:
                        put(net, GX0 + ii, y, GZ0 + kk, pal["spoil"], FLOORP)
                taken[ii, kk] = True
    net.taken = taken
    rest_and_finds(net, spec)


def rest_and_finds(net, spec):
    """The rest station, and a find in each zone's core cavern (the Cut's is the Digger)."""
    zones, F, C = spec["zones"], net.F, net.C
    rs = spec["rest"]
    rx, ry, rz = net.rest
    half = rs["size"] // 2
    have = net.have
    wall = pick(rs["wall"], rs["wall_fallback"], have)
    floor = pick(rs["floor"], rs["floor_fallback"], have)
    light = pick(spec["light"]["block"], spec["light"]["fallback"], have)
    for x in range(rx - half, rx + half + 1):
        for z in range(rz - half, rz + half + 1):
            edge = abs(x - rx) == half or abs(z - rz) == half
            door = edge and (abs(x - rx) <= 1 or abs(z - rz) <= 1)
            put(net, x, ry - 1, z, light if (x - rx) % 3 == 0 and (z - rz) % 3 == 0 and not edge else floor, FLOORP)
            if edge and not door:
                for y in range(ry, ry + 4):
                    put(net, x, y, z, wall, FLOORP)
    put(net, rx, ry - 1, rz, rs["marker"], FLOORP)
    net.rest_box = [rx - half, ry, rz - half, rx + half, rz + half]
    # the finds: in the core cavern of each zone, on the floor, clear of everything
    net.finds = {}
    for n, q in enumerate(net.nodes):
        if q["kind"] != "core" and q.get("was") != "core":
            continue
        zname = zones[q["zone"]]["id"]
        mine = (net.owner == n) & net.foot & ~net.taken & (net.bed == 0)
        if zname == "drowned":
            spots = [(q["x"], q["z"])] if net.bed[q["x"] - GX0, q["z"] - GZ0] == 0 else []
        else:
            want = {"slagworks": 0.7, "raw_tear": 0.8, "bloom": 0.5, "abandoned_cut": 0.45}[zname]
            cand = np.argwhere(mine & (np.abs(net.ownrr - want) < 0.08))
            spots = [(GX0 + i, GZ0 + k) for i, k in cand]
            if zname == "bloom" and net.mushrooms:
                rc, hs, mx, mz = max(net.mushrooms)
                spots = [(mx + rc + 1, mz)] + spots
            if zname == "slagworks":
                burn = net.pals[q["zone"]]["burn"]
                spots = [s for s in spots if at(net, s[0], F[s[0] - GX0, s[1] - GZ0] - 1, s[1]) == burn] or spots
        spots = [s for s in spots if at(net, s[0], F[s[0] - GX0, s[1] - GZ0], s[1]) == AIR
                 and C[s[0] - GX0, s[1] - GZ0] - F[s[0] - GX0, s[1] - GZ0] >= 3]
        if not spots:
            raise CaveError("no spot for %s's find in its core cavern" % zname)
        sx, sz = spots[0]
        sy = int(F[sx - GX0, sz - GZ0])
        sx, sy, sz = int(sx), int(sy), int(sz)
        if zname == "abandoned_cut":
            net.finds[zname] = {"npc": [sx, sy, sz]}
        else:
            put(net, sx, sy, sz, "minecraft:barrel[facing=up]", FITP)
            net.finds[zname] = {"cache": [sx, sy, sz]}


# ------------------------------------------------------------------ checks over the volume

def open_mask(net):
    names = net.B.names
    is_open = np.array([n is not None and base(n) in OPEN for n in names])
    return is_open[net.vol] & (net.vol > 0)


def allowed_outside(net, spec, i, k, j):
    """A neighbour outside the model is allowed open: the sky over the ravine, or the pit at the mouth."""
    x, z, y = GX0 + i, GZ0 + k, GY0 + j
    if 0 <= i < NX and 0 <= k < NZ and y > net.sky_top[i, k] and dilate_cache(net)[i, k]:
        return True
    mx, my, mz = spec["mouth"]["at"]
    return z >= mz + 1 and abs(x - mx) <= 6 and my - 1 <= y <= my + 10


def dilate_cache(net):
    if not hasattr(net, "_open3"):
        net._open3 = dilate(net.open_sky, 3)
    return net._open3


def check_seal(net, spec):
    op = open_mask(net)
    inm = net.vol > 0
    leaks = []
    for axis, step in ((0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1)):
        nb = np.zeros_like(inm)
        sl_src = [slice(None)] * 3
        sl_dst = [slice(None)] * 3
        if step == 1:
            sl_dst[axis], sl_src[axis] = slice(0, -1), slice(1, None)
        else:
            sl_dst[axis], sl_src[axis] = slice(1, None), slice(0, -1)
        nb[tuple(sl_dst)] = inm[tuple(sl_src)]
        bad = op & ~nb
        for i, k, j in np.argwhere(bad):
            di = [0, 0, 0]
            di[axis] = step
            if not allowed_outside(net, spec, i + di[0], k + di[1], j + di[2]):
                leaks.append(((GX0 + i, GY0 + j, GZ0 + k), (GX0 + i + di[0], GY0 + j + di[2], GZ0 + k + di[1])))
                if len(leaks) > 50:
                    break
    return leaks


def check_fluids(net):
    names = net.B.names
    falls = set(net.falls)
    spill = []
    for fluid in (WATER, LAVA):
        if fluid not in net.B.index:
            continue
        code = net.B.index[fluid]
        for i, k, j in np.argwhere(net.vol == code):
            p = (GX0 + i, GY0 + j, GZ0 + k)
            for (di, dk, dj), side in (((1, 0, 0), "x"), ((-1, 0, 0), "x"), ((0, 1, 0), "z"), ((0, -1, 0), "z"),
                                       ((0, 0, 1), "up"), ((0, 0, -1), "down")):
                c = net.vol[i + di, k + dk, j + dj]
                b = names[c] if c else None
                if b is None:
                    spill.append((p, side, "outside"))
                    continue
                bb = base(b)
                if bb == fluid or bb not in OPEN:
                    continue
                if side == "up" and bb == AIR and p not in falls:
                    continue
                if side == "down" and p in falls and bb == AIR:
                    continue
                spill.append((p, side, b))
    return spill


def walkout(net, spec):
    names = net.B.names
    cls = np.zeros(len(names), np.int8)       # 0 rock, 1 passable, 2 water, 3 lava, 4 open-not-passable
    for c, n in enumerate(names):
        if n is None:
            continue
        b = base(n)
        cls[c] = 2 if b == WATER else 3 if b == LAVA else 1 if b in PASSABLE else 4 if b in OPEN else 0
    V = cls[net.vol]
    inm = net.vol > 0
    mx, my, mz = spec["mouth"]["at"]

    def kind(i, k, j):
        if not (0 <= i < NX and 0 <= k < NZ and 0 <= j < NY):
            return 0
        if inm[i, k, j]:
            return V[i, k, j]
        return 1 if allowed_outside(net, spec, i, k, j) else 0

    def passable(i, k, j):
        return kind(i, k, j) in (1, 2)

    def solid(i, k, j):
        return kind(i, k, j) == 0

    def stand(i, k, j):
        return passable(i, k, j) and passable(i, k, j + 1) and (solid(i, k, j - 1) or kind(i, k, j) == 2)

    def settle(i, k, j):
        for _ in range(60):
            if kind(i, k, j) == 3:
                return None
            if stand(i, k, j):
                return (i, k, j)
            if not passable(i, k, j - 1) and kind(i, k, j - 1) != 3:
                return None
            j -= 1
        return None

    start = settle(mx - GX0, mz - 3 - GZ0, int(net.F[mx - GX0, mz - 3 - GZ0]) - GY0)
    if start is None:
        return {"error": "no footing inside the mouth"}
    ex, ey, ez = spec["exit"]["at"]
    exits = set()
    for xx in range(ex - 3, ex + 4):
        for zz in range(ez, ez + 4):
            s = settle(xx - GX0, zz - GZ0, ey + 2 - GY0)
            if s:
                exits.add(s)
    edges = {}
    seen = {start}
    dq = deque([start])
    while dq:
        p = dq.popleft()
        i, k, j = p
        out = []
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if passable(i + di, k + dk, j) and passable(i + di, k + dk, j + 1):
                s = settle(i + di, k + dk, j)
                if s:
                    out.append(s)
            if stand(i + di, k + dk, j + 1) and passable(i, k, j + 2):
                out.append((i + di, k + dk, j + 1))
        if kind(i, k, j) == 2:
            for dj in (1, -1):
                if passable(i, k, j + dj) and passable(i, k, j + dj + 1):
                    out.append((i, k, j + dj))
        edges[p] = out
        for q in out:
            if q not in seen and inm[q[0], q[1], q[2]] or (q not in seen and allowed_outside(net, spec, *q) and
                                                         abs(GX0 + q[0] - mx) < 12):
                if q not in seen:
                    seen.add(q)
                    dq.append(q)
    back = {}
    for p, qs in edges.items():
        for q in qs:
            back.setdefault(q, []).append(p)
    sinks = {start} | (exits & seen)
    home = set(sinks)
    dq = deque(sinks)
    while dq:
        q = dq.popleft()
        for p in back.get(q, ()):
            if p not in home:
                home.add(p)
                dq.append(p)
    traps = [p for p in seen if p not in home]
    floors = []
    for i, k in np.argwhere(net.foot):
        j = int(net.F[i, k]) - GY0
        if stand(i, k, j):
            floors.append((i, k, j))
    unreached = [p for p in floors if p not in seen]
    nolip = []
    for p in seen:
        i, k, j = p
        if kind(i, k, j) == 2 or not solid(i, k, j - 1):
            continue
        for di, dk in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if kind(i + di, k + dk, j) == 3 or kind(i + di, k + dk, j - 1) == 3:
                nolip.append(p)
    # the walked route, for the fights: a shortest path mouth -> exit
    route = []
    reached_exit = [e for e in exits if e in seen]
    if reached_exit:
        prev = {start: None}
        dq = deque([start])
        goal = None
        targets = set(reached_exit)
        while dq:
            p = dq.popleft()
            if p in targets:
                goal = p
                break
            for q in edges.get(p, ()):
                if q not in prev:
                    prev[q] = p
                    dq.append(q)
        while goal is not None:
            route.append(goal)
            goal = prev[goal]
        route.reverse()
    w = lambda p: (int(GX0 + p[0]), int(GY0 + p[2]), int(GZ0 + p[1]))
    return {"reachable": len(seen), "exit_reached": bool(reached_exit), "traps": len(traps),
            "trap_sample": [w(p) for p in traps[:3]], "floor_cells": len(floors), "unreached_floor": len(unreached),
            "unreached_sample": [w(p) for p in unreached[:3]], "lava_without_lip": len(nolip),
            "nolip_sample": [w(p) for p in nolip[:3]], "route": [w(p) for p in route]}


def place_fights(net, spec, route):
    """Ten stands at even spacing along the walked route, stepping round the rest station, lit to calm.

    Not five and five: in a braided cave the rest station sits wherever a cavern crosses the route nearest its
    middle, so the fights are spread by distance and fall either side of it as the route puts them."""
    tr, lt = spec["trainers"], spec["light"]
    have = net.have
    stand_b = pick(tr["stand"], tr["stand_fallback"], have)
    light = pick(lt["block"], lt["fallback"], have)
    n = tr["count"]
    L = len(route)
    lo, hi = int(L * 0.04), int(L * 0.94)
    stands = []
    for _half in (0,):
        for m in range(n):
            idx = lo + int((hi - lo) * (m + 0.5) / n)
            best = None
            rb_ = net.rest_box
            # never nearer than min_apart (the spec's rule); if nothing along the route fits, the build stops
            for apart in (tr["min_apart"],):
                for d in range(0, 90):
                    for cand in (idx + d, idx - d):
                        if lo <= cand < hi:
                            x, y, z = route[cand]
                            in_rest = rb_[0] - 3 <= x <= rb_[3] + 3 and rb_[2] - 3 <= z <= rb_[4] + 3
                            ok = not in_rest and at(net, x, y - 1, z) not in (None, AIR, WATER, LAVA) and \
                                at(net, x, y, z) == AIR and all(math.hypot(x - a, z - c) >= apart for a, _b, c in stands)
                            if ok:
                                best = (int(x), int(y), int(z))
                                break
                    if best:
                        break
                if best:
                    break
            if best is None:
                raise CaveError("no stand fits near route index %d" % idx)
            stands.append(best)
    lit = []
    for (x, y, z) in stands:
        put(net, x, y - 1, z, stand_b, FLOORP)
        r = lt["stand_radius"]
        for a in range(x - r, x + r + 1):
            for c in range(z - r, z + r + 1):
                if (a % lt["stand_spacing"]) or (c % lt["stand_spacing"]) or math.hypot(a - x, c - z) > r or (a, c) == (x, z):
                    continue
                i, k = a - GX0, c - GZ0
                if not net.foot[i, k] or net.bed[i, k]:
                    continue
                fy = int(net.F[i, k]) - 1
                if base(at(net, a, fy, c) or "") in (AIR, WATER, LAVA) or at(net, a, fy + 1, c) != AIR:
                    continue
                put(net, a, fy, c, light, FLOORP)
                lit.append((a, fy, c))
    # the Dark's caverns: a sparse lattice, so their size can be seen
    sp = lt["dark_caverns"]
    dz = [z["id"] for z in spec["zones"]].index("the_dark")
    for i, k in np.argwhere(net.foot & (net.owner >= 0) & (net.zone == dz) & (net.bed == 0)):
        x, z = GX0 + i, GZ0 + k
        if x % sp or z % sp:
            continue
        fy = int(net.F[i, k]) - 1
        if at(net, x, fy + 1, z) == AIR and base(at(net, x, fy, z) or "") not in OPEN:
            put(net, x, fy, z, light, FLOORP)
            lit.append((x, fy, z))
    net.stands = stands
    net.lights += lit
    return stands


# ------------------------------------------------------------------ Habitat Block tiles

def tiles(net, spec):
    """Habitat Blocks laid greedily over the floor at several scales: big tiles first, each where it takes in the
    most floor no tile has yet, then smaller ones into the seams they leave. No two circles overlap (their centres
    are at least the sum of their ranges apart; EXP-021: an overlap spawns nothing). One size alone covered at most
    about three quarters of an irregular cave, whatever the size; the seams are where the pack's own cave pools
    show through, at their own levels."""
    ranges = spec["spawns"]["tile_ranges"]
    rig = spec["rig"]
    zones = spec["zones"]
    floor = (net.foot & ~net.open_sky).astype(float)
    total = int(floor.sum())
    uncovered = floor.copy()
    base_ok = net.foot & ~net.open_sky & (net.bed == 0)
    chosen = []
    for R in ranges:
        Px, Pz = NX + 2 * R + 1, NZ + 2 * R + 1
        disc = np.zeros((Px, Pz))
        for a in range(-R, R + 1):
            for c in range(-R, R + 1):
                if a * a + c * c < R * R:
                    disc[a % Px, c % Pz] = 1.0
        Dk = np.fft.rfft2(disc)
        allowed = base_ok & (np.hypot(net.XS - rig["habitat"][0], net.ZS - rig["habitat"][2]) >= R + rig["range"])
        for (x, z, r2, _n) in chosen:
            allowed &= np.hypot(net.XS - x, net.ZS - z) >= R + r2
        min_new = max(12, int(0.12 * math.pi * R * R))
        for _ in range(600):
            U = np.zeros((Px, Pz))
            U[:NX, :NZ] = uncovered
            cnt = np.fft.irfft2(np.fft.rfft2(U) * Dk, s=(Px, Pz))[:NX, :NZ]
            cnt = np.where(allowed, cnt, -1)
            i, k = np.unravel_index(int(np.argmax(cnt)), cnt.shape)
            if cnt[i, k] < min_new:
                break
            x, z = GX0 + int(i), GZ0 + int(k)
            chosen.append((x, z, R, int(round(cnt[i, k]))))
            uncovered = np.where(np.hypot(net.XS - x, net.ZS - z) < R, 0, uncovered)
            allowed &= np.hypot(net.XS - x, net.ZS - z) >= 2 * R
    out = []
    for (x, z, R, n) in chosen:
        i, k = x - GX0, z - GZ0
        zi_ = int(net.zone[i, k])
        zname = zones[zi_]["id"]
        core = zones[zi_]["core"] is not None and float(net.W[zi_, i, k]) >= spec["spawns"]["core_share"]
        pool = "vrc_cave" if zname == "the_dark" else ("vrc_%s_core" % zname if core else "vrc_%s" % zname)
        out.append({"x": x, "y": int(net.F[i, k]) - 1, "z": z, "range": R, "pool": pool, "covers": n})
    share = 1.0 - float(uncovered.sum()) / max(1, total)
    return out, share


# ------------------------------------------------------------------ build

def whitelisted():
    pol = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    out = {}
    for w in pol.get("whitelist") or []:
        # a whitelisting without a reason is not a decision (test_vr_caves found an empty why passing)
        if SCOPE.lower() in str(w.get("scope", "")).lower() and isinstance(w.get("why"), str) and w["why"].strip():
            for b in w["blocks"]:
                out[b] = w["why"]
    return out


def build(source_root=None, server_dir=None, strict=True):
    source_root = source_root or os.environ.get("COBBLERS_SOURCE_ROOT")
    if not source_root:
        raise CaveError("no --source-root and no COBBLERS_SOURCE_ROOT: the heightmap lives under it")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    have = installed_blocks(server_dir)
    Net.have = have
    # two passes: the rest station belongs on the walked route, which is only known once the cave is built. The
    # second pass makes the plain cavern the route crosses nearest its middle the rest station; nothing else moves.
    net = build_model(spec, source_root, have)
    route = walkout(net, spec).get("route") or []
    if route:
        rx, rz = net.rest[0], net.rest[2]
        if min(math.hypot(x - rx, z - rz) for x, _y, z in route) > 12:
            mid = len(route) // 2
            best = None
            # a plain cavern or a dry zone's core (a rest room in the lava or the lake would be neither)
            dry = {n for n, z in enumerate(spec["zones"]) if z["id"] not in ("slagworks", "drowned")}
            for n, q in enumerate(net.nodes):
                if q["kind"] not in ("cavern", "rest") and not (q["kind"] == "core" and q["zone"] in dry):
                    continue
                hits = [m for m, (x, _y, z) in enumerate(route) if math.hypot(x - q["x"], z - q["z"]) <= 8]
                if hits:
                    score = min(abs(m - mid) for m in hits)
                    if best is None or score < best[0]:
                        best = (score, n)
            if best is None:
                raise CaveError("no plain cavern lies on the walked route for the rest station")
            net = build_model(spec, source_root, have, best[1])
    counts = {"caverns": len(net.nodes), "tunnels": len(net.edges), "lakes": len(net.lakes), "lava pools": len(net.pools),
              "island columns dropped": net.islands, "flats skipped": len(net.skipped_flats),
              "footprint columns": int(net.foot.sum()), "cells in the model": int((net.vol > 0).sum())}
    problems = []
    # cover
    top = np.where(net.foot | dilate(net.foot, 2), net.shell_hi, -999)
    roofed = dilate(net.foot, 2) & ~near_open(net)
    thin = roofed & (net.roof_ground - top < spec["cover"]["min"])
    if thin.any():
        i, k = np.argwhere(thin)[0]
        problems.append("%d columns with under %d of rock over the shell, e.g. (%d, %d)"
                        % (thin.sum(), spec["cover"]["min"], GX0 + i, GZ0 + k))
    counts["least cover"] = int((net.roof_ground - top)[roofed].min())
    # policy
    trig = json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"]
    ok = whitelisted()
    used = sorted({base(n) for n in net.B.names[1:]})
    policy = [b for b in used if b in trig]
    for b in policy:
        if b not in ok:
            problems.append("%s conditions spawns (%s) and is not whitelisted for %r in data/spawn_block_policy.json"
                            % (b, trig[b][0], SCOPE))
    # seal, fluids, walk-out
    leaks = check_seal(net, spec)
    if leaks:
        problems.append("%d open faces touch unauthored rock, e.g. %s -> %s" % (len(leaks), leaks[0][0], leaks[0][1]))
    spill = check_fluids(net)
    if spill:
        problems.append("%d fluid faces open, e.g. %s" % (len(spill), spill[0]))
    walk = walkout(net, spec)
    if walk.get("error") or not walk["exit_reached"] or walk["traps"] or walk["unreached_floor"] or walk["lava_without_lip"]:
        problems.append("walk-out: %s" % json.dumps({k: v for k, v in walk.items() if k != "route"}))
    stands = place_fights(net, spec, walk["route"]) if walk.get("route") else []
    tl, share = tiles(net, spec)
    counts["habitat tiles"] = len(tl)
    counts["floor inside a tile (%)"] = int(round(100 * share))
    records = check_records(net, spec, tl)
    if records and strict:
        problems += records
    counts["water cells"] = int((net.vol == net.B.index.get(WATER, -1)).sum())
    counts["lava cells"] = int((net.vol == net.B.index.get(LAVA, -1)).sum())
    plan = {"counts": counts, "policy": policy, "walk": {k: v for k, v in walk.items() if k != "route"},
            "route_length": len(walk.get("route") or []), "stands": [list(s) for s in stands],
            "rest": net.rest_box, "finds": net.finds, "falls": [list(f) for f in net.falls],
            "tiles": tl, "records": records, "problems": problems,
            "exit": spec["exit"]["at"], "mouth": spec["mouth"]["at"]}
    if problems and strict:
        raise CaveError("; ".join(problems))
    return plan, spec, net


def check_records(net, spec, tl):
    hb = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))
    mine = {b["id"]: b for b in hb.get("blocks") or [] if b["id"].startswith("vrc_")}
    out = []
    want = {"vrc_%02d" % n: t for n, t in enumerate(sorted(tl, key=lambda t: (t["z"], t["x"])))}
    if set(want) != set(mine):
        out.append("data/habitat_blocks.json holds %d vrc_* tiles, the model %d: run `vr_caves.py records --write`"
                   % (len(mine), len(want)))
    else:
        for bid, t in want.items():
            b = mine[bid]
            if b["position"] != {"x": t["x"], "y": t["y"], "z": t["z"]} or b["pool"] != "cobblers:%s" % t["pool"] or \
                    b["range_of_influence"] != t["range"]:
                out.append("%s differs from the model" % bid)
    rw = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
    by = {r["id"]: r for r in rw["rewards"]}
    find_of = {z["id"]: z.get("find") for z in spec["zones"]}
    for zname, f in net.finds.items():
        r = by.get(find_of.get(zname))
        if not r:
            out.append("no data/rewards.json record %s for %s's find" % (find_of.get(zname), zname))
        elif "cache" in f and (r.get("container") or {}).get("at") != f["cache"]:
            out.append("vr_%s's container is at %s, the model puts it at %s" % (zname, (r.get("container") or {}).get("at"), f["cache"]))
        elif "npc" in f and r.get("npc_at") != f["npc"]:
            out.append("vr_%s's NPC is at %s, the model puts it at %s" % (zname, r.get("npc_at"), f["npc"]))
    return out


def write_records(plan, spec):
    """The model's Habitat Block tiles into data/habitat_blocks.json and its finds into data/rewards.json."""
    p = ROOT / "data" / "habitat_blocks.json"
    hb = json.loads(p.read_text(encoding="utf-8"))
    hb["blocks"] = [b for b in hb["blocks"] if not (b["id"].startswith("vrc_") or b["id"].startswith("vr_"))]
    for n, t in enumerate(sorted(plan["tiles"], key=lambda t: (t["z"], t["x"]))):
        hb["blocks"].append({
            "id": "vrc_%02d" % n,
            "place": "Victory Road's cave, tile %d (%s)" % (n, t["pool"]),
            "pool": "cobblers:%s" % t["pool"], "style": "natural", "replace_spawns": True,
            "range_of_influence": t["range"], "position": {"x": t["x"], "y": t["y"], "z": t["z"]}, "status": "planned",
            "why": "One tile of the lattice tools/vr_caves.py lays over the network (data/vr_caves.json spawns): written "
                   "by `vr_caves.py records --write` from the model, and checked against it on every build."})
    hb["status"] = "Victory Road's cave tiled with %d blocks; behaviour in sealed rock is EXP-033" % len(plan["tiles"])
    p.write_text(json.dumps(hb, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    p = ROOT / "data" / "rewards.json"
    rw = json.loads(p.read_text(encoding="utf-8"))
    zone_of = {z.get("find"): z["id"] for z in spec["zones"]}
    for r in rw["rewards"]:
        f = plan["finds"].get(zone_of.get(r["id"]))
        if not f:
            continue
        if "cache" in f:
            x, y, z = f["cache"]
            r["container"]["at"] = [x, y, z]
            r["trigger"] = {"min": [x - 2, y, z - 2], "max": [x + 2, y + 3, z + 2]}
        if "npc" in f:
            r["npc_at"] = f["npc"]
    p.write_text(json.dumps(rw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ lines

def runs(i, k, ys):
    x, z = GX0 + i, GZ0 + k
    out = []
    n = 0
    while n < len(ys):
        y0, b = ys[n]
        m = n
        while m + 1 < len(ys) and ys[m + 1][0] == ys[m][0] + 1 and ys[m + 1][1] == b:
            m += 1
        y1 = ys[m][0]
        out.append("fill %d %d %d %d %d %d %s" % (x, y0, z, x, y1, z, b) if y1 > y0 else "setblock %d %d %d %s" % (x, y0, z, b))
        n = m + 1
    return out


def lines(net):
    names = net.B.names
    out = {p: [] for p in PASSES}
    shell_block = {}
    cols = np.argwhere((net.vol > 0).any(axis=2))
    fits = []
    lava_fall = set(net.falls)
    for i, k in cols:
        col_v, col_p = net.vol[i, k], net.pas[i, k]
        js = np.nonzero(col_v)[0]
        # shell: every model cell of the column gets the column's wall first
        walls = [names[col_v[j]] for j in js if col_p[j] == SHELL]
        wb = walls[0] if walls else names[col_v[js[0]]] if col_p[js[0]] == SHELL else None
        if wb is None:
            wb = next((names[col_v[j]] for j in js if col_p[j] == SHELL), ROCK)
        out["shell"] += runs(i, k, [(GY0 + j, wb) for j in js])
        for pas, key in ((AIRP, "air"), (FLOORP, "floor"), (FLUIDP, "fluid")):
            ys = [(GY0 + j, names[col_v[j]]) for j in js if col_p[j] == pas]
            if ys:
                out[key] += runs(i, k, ys)
        # shell cells whose final block is not the column's wall (a zone boundary inside a column) go in floor
        ys = [(GY0 + j, names[col_v[j]]) for j in js if col_p[j] == SHELL and names[col_v[j]] != wb]
        if ys:
            out["floor"] += runs(i, k, ys)
        for j in js:
            if col_p[j] == FITP:
                fits.append((GX0 + i, GY0 + j, GZ0 + k, names[col_v[j]]))
    fits.sort(key=lambda f: ((f[0], f[1], f[2]) in lava_fall, f[0] // TILE, f[2] // TILE, -f[1], f[0], f[2]))
    out["fittings"] = ["setblock %d %d %d %s" % f for f in fits]
    return out


def write(lns, out, folder, label):
    import shutil
    if out.exists():
        shutil.rmtree(out)
    fn = out / "data" / "cobblers" / "function" / folder
    fn.mkdir(parents=True)
    (out / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: %s" % label}},
                                                indent=2) + "\n", encoding="utf-8")
    order = []
    for n, pas in enumerate(lns):
        tiles_ = {}
        for ln in lns[pas]:
            t = ln.split()
            tiles_.setdefault((int(t[1]) // TILE, int(t[3]) // TILE), []).append(ln)
        for t in sorted(tiles_):
            body = tiles_[t]
            for j in range(0, len(body), PART):
                name = "%d%s_%d_%d%s" % (n + 1, pas, t[0], t[1], "" if j == 0 else "_%d" % (j // PART + 1))
                part = FL.ensure_loaded(["# Generated by tools/vr_caves.py: %s, tile %d %d" % (pas, t[0], t[1])] + body[j:j + PART])
                probs = FL.check_lines(part, name)
                if probs:
                    raise CaveError("function %s would be refused: %s" % (name, probs[:3]))
                (fn / (name + ".mcfunction")).write_text("\n".join(part) + "\n", encoding="utf-8")
                order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    return order


# ------------------------------------------------------------------ clear (staging only)

CMD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")


def clear_lines(net, spec, also=()):
    """Rock into every cell the retired spine and regions wrote that the network does not write itself.

    Staging only: a fresh export never had them. `also` adds function folders of earlier cuts of this network
    already applied to the staging world, so a re-cut leaves no void where the previous one had air. Cells in the pit
    past the mouth, above the canonical ground, and in the League's lot above its surface are left alone (the pit is
    the Deep's, the sky is nobody's, the lot is R8B's)."""
    touched = np.zeros((NX, NZ, NY), bool)
    dirs = [(ROOT / "build" / "datapacks" / pack / "data" / "cobblers" / "function" / folder, folder)
            for pack, folder in OLD_PACKS] + [(Path(a), "an earlier cut") for a in also]
    for d, folder in dirs:
        if not d.is_dir():
            raise CaveError("no %s: rebuild the retired pack to know what it wrote (%s)" % (d, folder))
        for f in sorted(d.glob("*.mcfunction")):
            for ln in f.read_text(encoding="utf-8").splitlines():
                m = CMD.match(ln)
                if not m:
                    continue
                v = [int(t) for t in m.groups()[1:7] if t is not None]
                if len(v) == 3:
                    v = v + v
                x0, y0, z0, x1, y1, z1 = min(v[0], v[3]), min(v[1], v[4]), min(v[2], v[5]), max(v[0], v[3]), max(v[1], v[4]), max(v[2], v[5])
                touched[max(0, x0 - GX0):x1 - GX0 + 1, max(0, z0 - GZ0):z1 - GZ0 + 1, max(0, y0 - GY0):y1 - GY0 + 1] = True
    touched &= ~(net.vol > 0)
    mz = spec["mouth"]["at"][2]
    touched[:, mz + 1 - GZ0:, :] = False
    yy = np.arange(NY)[None, None, :] + GY0
    touched &= yy <= np.where(net.in_lot, spec["exit"]["lot_y"] - 1, net.ground)[:, :, None]
    out = []
    for i, k in np.argwhere(touched.any(axis=2)):
        js = np.nonzero(touched[i, k])[0]
        out += runs(i, k, [(GY0 + j, ROCK) for j in js])
    return out, int(touched.sum())


# ------------------------------------------------------------------ verify

def verify(world, source_root):
    import build_audit
    import runtime_guard
    runtime_guard.check(world, "read")
    plan, spec, net = build(source_root, None, strict=False)
    W = build_audit.World(world)
    names = net.B.names
    skip = set()
    for (fx, fy, fz) in net.falls:
        for y in range(fy - 40, fy + 1):
            skip.add((fx, y, fz))
    for n, px, W_, pz, pr in net.pools:
        for a in range(px - pr - 3, px + pr + 4):
            for c in range(pz - pr - 3, pz + pr + 4):
                for y in (W_, W_ + 1):
                    skip.add((a, y, c))
    for t in plan["tiles"]:
        skip.add((t["x"], t["y"], t["z"]))
    bad, n = {}, 0
    for i, k, j in np.argwhere(net.vol > 0):
        p = (GX0 + i, GY0 + j, GZ0 + k)
        if p in skip:
            continue
        n += 1
        want = base(names[net.vol[i, k, j]])
        got = W.block(*p)
        if got != want:
            bad.setdefault((want, got), []).append(p)
    for (want, got), ps in sorted(bad.items(), key=lambda kv: -len(kv[1]))[:20]:
        print("  %7d cells: planned %s, world has %s   e.g. %s" % (len(ps), want, got, ps[:2]))
    total = sum(len(v) for v in bad.values())
    print("Victory Road caves, every cell: %d of %d as planned%s" % (n - total, n, "" if not total else ", %d MISMATCHES" % total))
    return 0 if total == 0 else 1


def show(plan):
    for k, v in plan["counts"].items():
        print("  %-30s %9s" % (k, v))
    print("  walk-out   %s" % json.dumps(plan["walk"]))
    print("  route %d blocks, stands %s" % (plan["route_length"], plan["stands"]))
    print("  rest %s  finds %s" % (plan["rest"], json.dumps(plan["finds"])))
    print("  policy %s" % ", ".join(plan["policy"]))
    for p in plan["problems"]:
        print("  PROBLEM %s" % p)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("report", "records", "build", "clear", "verify"))
    ap.add_argument("--source-root")
    ap.add_argument("--server-dir")
    ap.add_argument("--world")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--also", action="append", default=[],
                    help="clear: the function folder of an earlier cut of the network already applied to the world")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "verify":
            if not a.world:
                ap.error("verify needs --world")
            return verify(a.world, a.source_root)
        plan, spec, net = build(a.source_root, a.server_dir, strict=a.cmd in ("build", "clear"))
    except CaveError as exc:
        print("vr_caves: %s" % exc)
        return 1
    show(plan)
    if a.cmd == "records":
        if not a.write:
            print("records: pass --write to write data/habitat_blocks.json and data/rewards.json")
            return 0
        write_records(plan, spec)
        print("records: %d tiles and %d finds written" % (len(plan["tiles"]), len(plan["finds"])))
        return 0
    if a.cmd == "report":
        return 1 if [p for p in plan["problems"] if "records" not in p and "vrc_" not in p and "rewards.json" not in p] else 0
    if a.cmd == "clear":
        lns, n = clear_lines(net, spec, a.also)
        order = write({"clear": lns}, CLEAR_OUT, "vr_clear", "Victory Road schema 2, cleared (staging only)")
        print("clear: %d cells back to rock, %d functions, %d commands" % (n, len(order), len(lns)))
        return 0
    lns = lines(net)
    order = write(lns, OUT, "vr_caves", "Victory Road's caves")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan), encoding="utf-8")
    print("Victory Road caves: %d functions, %d commands" % (len(order), sum(len(v) for v in lns.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
