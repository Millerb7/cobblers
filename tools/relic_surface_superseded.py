#!/usr/bin/env python
"""SUPERSEDED: the relic area's SURFACE build as tools/deep_city.py wrote it until 2026-10-02. Never built.

The owner, 2026-10-01: "THE RELIC SITE UNDERGROUND, reachable only through the Compact HQ, turned back by the zone
check rather than barriers." tools/deep_city.py no longer builds the shrine platform, the six ring arches, the
plinth and its ring, the standing stones, the processional way or the Compact cordon; the shrine is in the hall
tools/relic_underground.py carves, and the cordon is that tool's zone check.

WHY THIS CODE IS KEPT. A world that was applied before the change (staging, 2026-10-01 17:10, R9DC) still holds
every block this function wrote, and a data edit changes nothing in a world. R9RU's undo pass
(tools/relic_underground.py) takes them off, and the only faithful record of WHICH cells they are is the generator
that wrote them: the world may not be read to find out (CLAUDE.md, "Ground comes from the heightmap, never from a
world"). So this is build_relic() from tools/deep_city.py at c63b67a, VERBATIM below the marker line -- nothing in its
body is edited, so that its write set is exactly the one the world received. It is called by nothing that emits a
pack for R9DC; tools/relic_underground.py calls it to know what to undo, and tools/relic_underground_audit.py to check
that the undo covers it.

It writes everything the old build_relic wrote, the parts that stay (the sealed entrance, the lookout, the dig) as well
as the parts that went: the undo subtracts whatever the CURRENT tools/deep_city.py still writes, so the parts that
stay are never touched.
"""
from __future__ import annotations

import json
import math

import numpy as np

from deep_city import CityError, D4, DIR, ROOT, ang_diff, hsh, stair


def _old_build(source_root, spec=None, P=None):
    """(canvas, record) of the superseded surface build on a fresh canvas: record is build_relic()'s own `out`
    (the shrine's base, the ring's centre and radius, the cordon's gate), which the capped plan no longer carries."""
    import copy
    import deep_city as DC
    spec = copy.deepcopy(spec or json.loads(DC.SPEC.read_text(encoding="utf-8")))
    # data/deep_city.json moved the arches, the ring and the cordon under relic_area.superseded_surface when they
    # stopped being built; the verbatim body below reads them where they used to be
    ra = spec["relic_area"]
    for k, v in (ra.get("superseded_surface") or {}).items():
        if k != "why":
            ra.setdefault(k, v)
    P = P or DC.Palette(spec)
    cv = DC.Canvas()
    rec = build_relic(cv, P, spec, source_root, lambda *_a, **_k: None, [])
    return cv, rec


def old_write_set(source_root, spec=None, P=None):
    """{(x, y, z): block} for every cell the superseded surface build wrote, on a fresh canvas."""
    cv, _rec = _old_build(source_root, spec, P)
    return {k: v[0] for k, v in cv.v.items()}


def old_record(source_root, spec=None, P=None):
    """build_relic()'s record of the superseded surface: {"shrine": {centre, radius, base}, "ring": {centre [x, y, z],
    radius, top}, "cordon": {gate [[x, z], ...], ...}, ...}. Where the old ring and cordon stood, for a world check
    (tools/presence_audit.py relic) that must not depend on the current, capped tools/deep_city.py plan."""
    _cv, rec = _old_build(source_root, spec, P)
    return rec


# ---------------------------------------------------------------- verbatim from tools/deep_city.py at c63b67a

def build_relic(cv, P, spec, source_root, count, checks):
    import ground as G
    import rift_deep as RD
    rs = spec["relic_area"]
    m, (RX0, RZ0, RX1, RZ1), _n = RD.region_mask(rs["region"], source_root)
    g = G.load(source_root)
    H = g.box(RX0, RZ0, RX1, RZ1)

    def inr(x, z):
        a, b = z - RZ0, x - RX0
        return 0 <= a < m.shape[0] and 0 <= b < m.shape[1] and bool(m[a, b])

    def gr(x, z):
        return int(H[z - RZ0, x - RX0])

    out = {"reserved_below": [r["id"] for r in spec["reserved"] if r["id"] == "hoopa_cradle"]}
    own = "relic"
    # the shrine: a stepped round platform at its median ground
    sh = rs["shrine"]
    scx, scz = sh["centre"]
    rad = sh["radius"]
    disc = [(x, z) for x in range(scx - rad, scx + rad + 1) for z in range(scz - rad, scz + rad + 1)
            if math.hypot(x - scx, z - scz) <= rad + 0.5 and inr(x, z)]
    base = int(np.median([gr(x, z) for x, z in disc]))
    tops = {}
    for x, z in disc:
        r = math.hypot(x - scx, z - scz)
        band = 0 if r > rad * 0.69 else (1 if r > rad * 0.38 else 2)
        top = base + band
        gy = gr(x, z)
        for y in range(min(gy, top) + 1 if gy < top else top + 1, max(gy, top) + 1):
            cv.put(x, y, z, "minecraft:air" if y > top else P("ancient_stone"), owner=own)
        for y in range(top + 1, top + 7):
            cv.put(x, y, z, "minecraft:air", owner=own)
        b = {0: P("ancient_stone"), 1: "minecraft:polished_tuff", 2: "minecraft:chiseled_tuff_bricks"}[band]
        a = math.degrees(math.atan2(x - scx, -(z - scz))) % 360
        if abs(r - rad * 0.69) < 0.7 and ang_diff(a, round(a / 30.0) * 30.0) < 4:
            b = P("rift_seep")
        cv.put(x, top, z, b, owner=own, exterior=b == P("rift_seep"))
        tops[(x, z)] = top
    out["shrine"] = {"centre": [scx, scz], "radius": rad, "base": base}
    count("relic shrine columns", len(disc))
    # six ring arches round it, each an upright ring you look through from the middle
    ar = rs["arches"]
    arches = []
    for k in range(ar["count"]):
        a = math.radians(30 + k * 360.0 / ar["count"])
        ax, az = scx + ar["orbit"] * math.sin(a), scz - ar["orbit"] * math.cos(a)
        n = (math.sin(a), -math.cos(a))
        tvec = (-n[1], n[0])
        R_ = ar["radius"]
        cy = base + R_ + 1
        pts = _ring_voxels(ax, cy, az, n, tvec, R_, 0.5)
        for (x, y, z, ang) in pts:
            if not inr(x, z):
                continue
            b = P("distortion")
            if ang_diff(ang, 90) < 12:
                b = P("rift_seep")
            elif int(ang) % 90 in range(40, 50):
                b = P("glass_band")
            cv.put(x, y, z, b, owner=own, exterior=b == P("rift_seep"))
        arches.append([round(ax), round(az)])
    out["arches"] = arches
    count("relic arches", len(arches))
    # the plinth and the relic ring, broken, facing the dig camp and the Deep
    rg = rs["ring"]
    top2 = base + 2
    for dx in range(-2, 3):
        for dz in range(-2, 3):
            x, z = scx + dx, scz + dz
            for y in range(top2 + 1, top2 + rg["plinth"] + 1):
                corner = abs(dx) == 2 and abs(dz) == 2
                cv.put(x, y, z, P("rift_seep") if corner else "minecraft:chiseled_tuff_bricks", owner=own, exterior=corner)
    cy = top2 + rg["plinth"] + rg["radius"] + 1
    n = (1.0, 0.0)
    tvec = (0.0, 1.0)
    ring_top = 0
    for (x, y, z, ang) in _ring_voxels(scx, cy, scz, n, tvec, rg["radius"], 1.0):
        if ang_diff(ang, 60) < rg["gap_degrees"] / 2.0:
            continue
        rr = math.hypot(z - scz, y - cy)
        b = P("rift_seep") if rr < rg["radius"] - 0.3 else P("hoopa_gold")
        cv.put(x, y, z, b, owner=own, exterior=b == P("rift_seep"))
        ring_top = max(ring_top, y)
    out["ring"] = {"centre": [scx, cy, scz], "radius": rg["radius"], "top": ring_top}
    checks.append((scx, cy - rg["radius"], scz, [P("hoopa_gold"), P("rift_seep")], "relic ring"))
    # the sealed entrance: a sunken forecourt down to a doorway walled with reinforced deepslate behind bars
    se = rs["sealed_entrance"]
    ex, ez = se["at"]
    f = DIR[se["facing"]]
    if f != (1, 0):
        raise CityError("the sealed entrance is drawn facing east only")
    depth = se["depth"]
    gb = int(np.median([gr(x, z) for x in range(ex, ex + 10) for z in range(ez - 3, ez + 4) if inr(x, z)]))
    yf = gb - depth
    for x in range(ex, ex + 10):
        for z in range(ez - 3, ez + 4):
            if not inr(x, z):
                raise CityError("the sealed entrance's forecourt leaves the relic area at %s" % ((x, z),))
            wall = z in (ez - 3, ez + 3) or x == ex
            step = max(0, min(depth, x - (ex + 5)))           # the stair rises eastward out of the forecourt
            fy = yf + step
            gy = gr(x, z)
            if wall:
                for y in range(yf, max(gy, gb) + 2):
                    cv.put(x, y, z, P("ancient_stone"), owner=own)
                continue
            cv.put(x, fy, z, "minecraft:polished_tuff" if step == 0 else stair("minecraft:tuff_brick_stairs", "east"),
                   owner=own)
            for y in range(fy + 1, max(gy, gb) + 2):
                cv.put(x, y, z, "minecraft:air", owner=own)
    # the doorway in the west wall: crying obsidian frame, reinforced deepslate seal, iron bars in front
    for z in range(ez - 2, ez + 3):
        for y in range(yf + 1, yf + 6):
            frame_ = z in (ez - 2, ez + 2) or y == yf + 5
            cv.put(ex, y, z, P("rift_seep") if frame_ else P("seal"), owner=own, exterior=frame_)
            if not frame_:
                cv.put(ex + 1, y, z, P("bars"), 2, owner=own)
    for z in (ez - 2, ez + 2):
        cv.put(ex + 1, yf + 4, z, "minecraft:end_rod[facing=up]", 2, owner=own, exterior=True)
    out["sealed_entrance"] = {"door": [ex, yf + 1, ez], "seal": [ex, yf + 1, ez - 1, ex, yf + 4, ez + 1],
                              "forecourt_floor": yf, "facing": "east",
                              "behind": "rock, uncarved: the cavern below stays sealed (reserved hoopa_cradle)"}
    checks.append((ex, yf + 2, ez, [P("seal")], "relic seal"))
    count("relic sealed entrance")
    # the lookout over the Deep
    lx, lz = rs["lookout"]["at"]
    look = [(x, z) for x in range(lx - 2, lx + 3) for z in range(lz - 2, lz + 3) if inr(x, z)]
    ly = max(gr(x, z) for x, z in look)
    for x, z in look:
        for y in range(gr(x, z) + 1, ly + 1):
            cv.put(x, y, z, P("ancient_stone"), owner=own)
        cv.put(x, ly, z, "minecraft:polished_tuff", owner=own)
        if x == lx + 2 or abs(z - lz) == 2:
            cv.put(x, ly + 1, z, P("rail"), 2, owner=own)
    cv.put(lx, ly + 1, lz, "minecraft:lantern[hanging=false,waterlogged=false]", 2, owner=own, exterior=True)
    out["lookout"] = [lx, ly, lz]
    # the processional way from the shrine to the lookout, flush in the ground
    way = set()
    for x in range(scx + rad, lx - 2):
        for z in (lz - 1, lz, lz + 1):
            zc = round(scz + (lz - scz) * (x - scx - rad) / max(1, lx - 2 - scx - rad)) + (z - lz)
            if inr(x, zc):
                cv.put(x, gr(x, zc), zc, P("ancient_stone"), owner=own)
                for y in range(gr(x, zc) + 1, gr(x, zc) + 4):
                    cv.put(x, y, zc, "minecraft:air", owner=own)
                way.add((x, zc))
    # the standing stones round the shrine, two of them fallen
    stn = rs["stones"]
    stones = []
    for k in range(stn["count"]):
        a = math.radians(22.5 + k * 360.0 / stn["count"])
        sx_, sz_ = int(round(scx + stn["orbit"] * math.sin(a))), int(round(scz - stn["orbit"] * math.cos(a)))
        fp = [(sx_ + dx, sz_ + dz) for dx in (0, 1) for dz in (0, 1)]
        if not all(inr(*p) for p in fp) or any(p in way for p in fp):
            continue
        h = stn["height"][0] + hsh(sx_, 0, sz_, 31) % (stn["height"][1] - stn["height"][0] + 1)
        if len(stones) < stn["fallen"] and k % 3 == 1:
            # fallen: lying along the ground, tangent to the circle
            tx, tz = (1, 0) if abs(math.cos(a)) > 0.7 else (0, 1)
            for i in range(h):
                for p in ((sx_ + tx * i, sz_ + tz * i), (sx_ + tx * i + tz, sz_ + tz * i + tx)):
                    if inr(*p):
                        cv.put(p[0], gr(*p) + 1, p[1], P("ancient_stone") if i % 3 else "minecraft:chiseled_tuff", owner=own)
            stones.append({"at": [sx_, sz_], "fallen": True})
            continue
        for x, z in fp:
            gy = gr(x, z)
            for y in range(gy + 1, gy + h + 1):
                b = P("ancient_stone")
                if y == gy + h:
                    b = "minecraft:chiseled_tuff"
                elif y == gy + h // 2 + 1:
                    b = P("rift_seep")
                cv.put(x, y, z, b, owner=own, exterior=b == P("rift_seep"))
        stones.append({"at": [sx_, sz_], "height": h})
    out["stones"] = stones
    count("relic standing stones", len(stones))
    # the Compact's dig: trenches, spoil heaps, fallen fragments, crates, survey stakes
    keep = {(x, z) for x, z in disc} | {(x, z) for x in range(ex - 1, ex + 11) for z in range(ez - 4, ez + 5)} | set(look)
    keep |= way | {(s["at"][0] + dx, s["at"][1] + dz) for s in stones for dx in range(-2, 10) for dz in range(-2, 10)}
    cells = sorted((x, z) for x in range(RX0, RX1 + 1) for z in range(RZ0, RZ1 + 1) if inr(x, z)
                   and math.hypot(x - scx, z - scz) > rad + 4)
    rng = sorted(cells, key=lambda c: hsh(c[0], 0, c[1], 17))
    deb = rs["debris"]
    placed = {"trenches": 0, "heaps": 0, "fragments": 0}
    used = set()

    def free(fp):
        return all(inr(x, z) and (x, z) not in keep and (x, z) not in used for x, z in fp)

    all_cells = [(x, z) for x in range(RX0, RX1 + 1) for z in range(RZ0, RZ1 + 1) if inr(x, z)]
    boundary = {(x, z) for x, z in all_cells if any(not inr(x + dx, z + dz) for dx, dz in D4)}
    near_edge = {(x + dx, z + dz) for x, z in boundary for dx in range(-4, 5) for dz in range(-4, 5)
                 if abs(dx) + abs(dz) < 4}
    for c in rng:
        if all(placed[k] >= deb[k] for k in placed):
            break
        x, z = c
        if c in near_edge:
            continue
        roll = hsh(x, 1, z, 19) % 3
        if roll == 0 and placed["trenches"] < deb["trenches"]:
            along = hsh(x, 2, z, 19) % 2
            fp = [(x + (i if along else j), z + (j if along else i)) for i in range(0, 8) for j in range(0, 3)]
            if not free(fp) or max(gr(*p) for p in fp) - min(gr(*p) for p in fp) > 2:
                continue
            for p in fp:
                gy = gr(*p)
                cv.put(p[0], gy, p[1], "minecraft:air", owner=own)
                cv.put(p[0], gy - 1, p[1], "minecraft:air", owner=own)
                cv.put(p[0], gy - 2, p[1], "minecraft:coarse_dirt", owner=own)
            px_, pz_ = fp[0]
            cv.put(px_, gr(px_, pz_) + 1, pz_, P("rib_teal"), owner=own)
            cv.put(px_, gr(px_, pz_) + 2, pz_, "minecraft:end_rod[facing=up]", 2, owner=own, exterior=True)
            used |= {(p[0] + dx, p[1] + dz) for p in fp for dx in (-2, -1, 0, 1, 2) for dz in (-2, -1, 0, 1, 2)}
            placed["trenches"] += 1
        elif roll == 1 and placed["heaps"] < deb["heaps"]:
            fp = [(x + dx, z + dz) for dx in range(-2, 3) for dz in range(-2, 3) if abs(dx) + abs(dz) <= 3]
            if not free(fp):
                continue
            for p in fp:
                hgt = 3 - (abs(p[0] - x) + abs(p[1] - z))
                gy = gr(*p)
                for y in range(gy + 1, gy + max(1, hgt) + 1):
                    b = ("minecraft:gravel", "minecraft:cobbled_deepslate", "minecraft:tuff")[hsh(p[0], y, p[1], 23) % 3]
                    cv.put(p[0], y, p[1], b, owner=own)
            if hsh(x, 3, z, 19) % 2 == 0 and free([(x + 3, z)]):
                cv.put(x + 3, gr(x + 3, z) + 1, z, "minecraft:barrel[facing=up,open=false]", owner=own)
            used |= {(p[0] + dx, p[1] + dz) for p in fp for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
            placed["heaps"] += 1
        elif roll == 2 and placed["fragments"] < deb["fragments"]:
            fp = [(x + dx, z) for dx in range(-2, 3)]
            if not free(fp):
                continue
            for i, p in enumerate(fp):
                gy = gr(*p)
                lift = 1 if i in (1, 2, 3) else 0
                cv.put(p[0], gy + lift, p[1], P("hoopa_gold"), owner=own)
                if lift:
                    cv.put(p[0], gy, p[1], P("hoopa_gold"), owner=own)
            used |= {(p[0] + dx, p[1] + dz) for p in fp for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
            placed["fragments"] += 1
    out["debris"] = placed
    for k_, v_ in placed.items():
        count("relic %s" % k_, v_)
    # the cordon: tinted glass under iron bars along the whole traced edge, copper posts with lamps, the gate shut
    cd = rs["cordon"]
    ring_ = sorted(boundary)
    dp = regions_seed(cd["gate_toward"])
    gate = sorted(ring_, key=lambda c: ((c[0] - dp[0]) ** 2 + (c[1] - dp[1]) ** 2, c))[:5]
    n_post = 0
    for k_, (x, z) in enumerate(ring_):
        gy = gr(x, z)
        post = hsh(x, 5, z, 29) % cd["post_every"] == 0 or (x, z) in gate[:1] or (x, z) in gate[-1:]
        if post:
            for y in range(gy + 1, gy + cd["height"] + 1):
                cv.put(x, y, z, P("rib_teal"), owner="cordon")
            cv.put(x, gy + cd["height"] + 1, z, P("sea_lantern") if (x, z) in gate else "minecraft:end_rod[facing=up]",
                   2 if (x, z) not in gate else 1, owner="cordon", exterior=True)
            n_post += 1
        else:
            cv.put(x, gy + 1, z, P("glass_dark"), owner="cordon")
            for y in range(gy + 2, gy + cd["height"] + 1):
                cv.put(x, y, z, P("bars"), 2, owner="cordon")
    out["cordon"] = {"columns": len(ring_), "posts": n_post, "gate": [list(c) for c in gate], "gate_state": "shut"}
    count("relic cordon columns", len(ring_))
    return out


def regions_seed(region):
    r = json.loads((ROOT / "data" / "rift_regions.json").read_text(encoding="utf-8"))["regions"][region]
    x0, z0, x1, z1 = r["bbox"]
    return ((x0 + x1) / 2.0, (z0 + z1) / 2.0)


def _ring_voxels(cx, cy, cz, n, t, R, half):
    """Voxels of an upright ring of radius R centred (cx, cy, cz), its plane's normal the horizontal unit vector n,
    t the horizontal in-plane unit vector; half is half its thickness along n. -> [(x, y, z, angle from +t)]"""
    out = []
    span = int(R + 2)
    for x in range(int(math.floor(cx - span)), int(math.ceil(cx + span)) + 1):
        for z in range(int(math.floor(cz - span)), int(math.ceil(cz + span)) + 1):
            for y in range(int(cy - span), int(cy + span) + 1):
                dx, dz, dy = x - cx, z - cz, y - cy
                u = dx * n[0] + dz * n[1]
                if abs(u) > half:
                    continue
                v = dx * t[0] + dz * t[1]
                rr = math.hypot(v, dy)
                if R - 0.75 <= rr <= R + 0.5:
                    out.append((x, y, z, math.degrees(math.atan2(dy, v)) % 360))
    return out
