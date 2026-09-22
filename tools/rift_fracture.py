#!/usr/bin/env python
"""The Rift as a fracture: one prototype stretch (data/rift_fracture.json, docs/mechanics/RIFT_FRACTURE.md).

Everything is decided from the canonical heightmap (tools/ground.py) and committed data; nothing reads a world to
decide (the ground rule). A world is read only by `verify`, to check.

  scarps       the gentle walls cut into a sheer lip riser (23+ blocks where the depth allows: a lethal drop) and
               shattered steps down to the floor, jittered along the length; tilted plates with cracks on the treads;
               the lip undercut where it overhangs; side fissures running back into the plateau. Cut only: the rim
               and the floor edge stay where they are
  veins        a branching glowing crack from a line along the floor, branches climbing the risers: sea lantern core
               (cyan-white, light 15), galar particle halo (violet, light 15), crying obsidian where they thin; one
               open wound 9 wide, part crusted with purple glass
  crystals     distortion crystals where a branch leaves the main vein
  sky crack    a sample of the candidate fracture in the sky over the stretch, y360-400, every part 8 thick
  portal       block_display sheets of the nether portal texture: a torn window in the lip riser, a pool lying in the
               wound, a curtain in a fissure; each with light blocks round it. Summoned by a re-runnable function that
               force-loads, waits for the entities to load, kills its own tag and summons
  biome        cobblers:the_rift painted only on 4x4 cells wholly inside the lip

  python tools/rift_fracture.py --source-root <root>                 plan and write the packs
  python tools/rift_fracture.py verify --world <stopped world copy>  blocks and entities read back; fails closed

Outputs: build/datapacks/cobblers_rift_fracture (server pack), build/datapacks/cobblers_rift_biome (world pack: the
biome), derived/rift_fracture/plan.json (what verify checks, the view points).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import function_limits as FL  # noqa: E402

BUILD = ROOT / "build" / "datapacks"
PACK = BUILD / "cobblers_rift_fracture"
BIOME_PACK = BUILD / "cobblers_rift_biome"
PLAN = ROOT / "derived" / "rift_fracture" / "plan.json"
TILE = 128
PACK_FORMAT = 48
# verify reads a world to CHECK a result, never to decide one (CLAUDE.md, the ground rule; tools/ground_rule.py)
WORLD_READS = {"verify", "entity_count", "main"}


class FractureError(RuntimeError):
    pass


# ------------------------------------------------------------------ data


def installed_blocks(server_dir):
    """Every block id the server's jars define (their blockstates). None when no server is given: the palette's mod
    blocks are then used unchecked, and the build says so."""
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
        except Exception:
            continue
        for n in z.namelist():
            m = re.match(r"assets/([^/]+)/blockstates/([^/]+)\.json$", n)
            if m:
                ids.add("%s:%s" % m.groups())
    return ids


def palette(spec, have):
    """{role: block} with each mod block's fallback used when the pack does not have it; [(role, fallback reason)]."""
    out, used_fallback = {}, []
    for role, p in spec["palette"].items():
        if role == "never":
            continue
        b = p["block"]
        if not b.startswith("minecraft:") and have is not None and b not in have:
            used_fallback.append((role, b, p["fallback"]))
            b = p["fallback"]
        out[role] = b
    sc = spec["sky_crack"]
    halo = sc["halo"]
    if not halo.startswith("minecraft:") and have is not None and halo not in have:
        halo = sc["halo_fallback"]
    out["sky_core"], out["sky_halo"] = sc["core"], halo
    return out, used_fallback


# ------------------------------------------------------------------ geometry


class Frame:
    def __init__(self, a, b):
        self.a = a
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        self.L = L
        self.u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        self.v = (-self.u[1], self.u[0])

    def xz(self, s, t):
        return (self.a[0] + self.u[0] * s + self.v[0] * t, self.a[1] + self.u[1] * s + self.v[1] * t)

    def st(self, x, z):
        dx, dz = x - self.a[0], z - self.a[1]
        return dx * self.u[0] + dz * self.u[1], dx * self.v[0] + dz * self.v[1]


def stations(g, fr, every, hw):
    """Per station along the stretch: floor y and its t, and each side's rim t and y and floor-edge t."""
    out = []
    s = 0.0
    while s <= fr.L + 1e-6:
        prof = [(t, g(*map(round, fr.xz(s, t)))) for t in range(-hw, hw + 1)]
        mid = [p for p in prof if abs(p[0]) <= 90]
        t0, F = min(mid, key=lambda p: (p[1], abs(p[0])))
        sides = {}
        for sgn in (-1, 1):
            best, bt, since, edge = -1, t0, 0, None
            t = t0
            while abs(t) <= hw:
                h = g(*map(round, fr.xz(s, t)))
                if edge is None and h > F + 3:
                    edge = t
                if h > best:
                    best, bt, since = h, t, 0
                else:
                    since += 1
                if since >= 12 and best > F + 15:
                    break
                t += sgn
            sides[sgn] = {"rim_t": bt, "rim_y": best, "edge_t": edge if edge is not None else bt}
        out.append({"s": s, "t0": t0, "floor": F, "sides": sides})
        s += every
    return out


# ------------------------------------------------------------------ the plan


class Plan:
    def __init__(self):
        self.top = {}        # (x, z) -> new ground y where it is cut
        self.old = {}        # (x, z) -> heightmap ground y
        self.carve = {}      # (x, z) -> [(y0, y1)] extra air ranges (undercut, pits)
        self.put = {}        # (x, y, z) -> block
        self.entities = []   # summon commands
        self.checks = []     # (x, y, z, [allowed], what)
        self.counts = {}

    def count(self, what, n=1):
        self.counts[what] = self.counts.get(what, 0) + n


def rng_for(seed, *k):
    """A random stream fixed by the seed and the key: crc32, not hash(), which Python randomises per process for
    strings, so a rebuild after a re-export would lay a different Rift."""
    import zlib
    return random.Random(zlib.crc32(repr((seed,) + k).encode()))


def build(source_root, server_dir=None):
    import ground
    g = ground.load(source_root)
    spec = json.loads((ROOT / "data" / "rift_fracture.json").read_text(encoding="utf-8"))
    have = installed_blocks(server_dir)
    pal, fallbacks = palette(spec, have)
    st_spec = spec["stretch"]
    fr = Frame(tuple(st_spec["from"]), tuple(st_spec["to"]))
    hw = st_spec["half_width"]
    every = st_spec["station_every"]
    sts = stations(g, fr, every, hw)
    seed = spec["veins"]["seed"]
    rng = random.Random(seed)
    sc = spec["scarp"]
    plan = Plan()

    # Victory Road's t at each station, so floor cracks and the wound keep off it
    R = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))
    vr = next(r for r in R["routes"] if r["id"] == "victory_road")
    vpts = [(p["x"], p["z"]) if isinstance(p, dict) else (p[0], p[-1]) for p in vr["corridor"]["polyline"]]
    road = [fr.st(*p) for p in vpts]
    road = [(s, t) for s, t in road if -40 <= s <= fr.L + 40 and abs(t) <= hw]

    def road_t(s):
        near = [p for p in road if abs(p[0] - s) < 25]
        return min(near, key=lambda p: abs(p[0] - s))[1] if near else None

    # step layout per 32-block group: count, riser weights, tread splits
    groups = {}

    def group(k):
        gk = k // 8
        if gk not in groups:
            r = rng_for(seed, "group", gk)
            n = r.randint(*sc["steps"]["count"])
            w = [r.uniform(0.6, 1.4) for _ in range(n)]
            splits = sorted(r.uniform(0.15, 0.95) for _ in range(n - 1))
            groups[gk] = (n, [x / sum(w) for x in w], [0.0] + splits + [1.0], r.random() < 1 / sc["undercut"]["one_in_stations"])
        return groups[gk]

    def station(s):
        return sts[max(0, min(len(sts) - 1, int(round(s / every))))]

    def level(s, side, q):
        """The new ground y at distance q in from the rim (0 at the rim, run at the floor edge), or None beyond."""
        stt = station(s)
        sd = stt["sides"][side]
        run = abs(sd["rim_t"] - sd["edge_t"])
        if q < 0 or q > run:
            return None
        D = sd["rim_y"] - stt["floor"]
        if D < 8:
            return None
        D1 = max(sc["lip_riser"]["min"], min(sc["lip_riser"]["max"], sc["lip_riser"]["fraction_of_depth"] * D))
        D1 = min(D1, D - 4)
        n, weights, splits, _ = group(int(round(s / every)))
        jit = rng_for(seed, "jit", int(s) // 6, side).randint(-sc["steps"]["riser_jitter"], sc["steps"]["riser_jitter"])
        rim = sd["rim_y"]

        def slope(qq):
            return rim - D * qq / run

        # the staircase sits UNDER the old slope, so cutting only ever removes: the lip tread ends where the slope
        # has fallen D1 (so the lip riser is D1 high), and each lower tread's level is the slope's height at its
        # far end (so each lower riser is the slope's fall across the tread before it)
        q1 = D1 / D * run
        bounds = [0.0, q1] + [q1 + (run - q1) * f for f in splits[1:-1]] + [run]
        bounds = [b + (jit if 1 < i < len(bounds) - 1 else 0) for i, b in enumerate(bounds)]
        for i in range(len(bounds) - 1):
            if q < bounds[i + 1] or i == len(bounds) - 2:
                return int(round(min(rim - D1, slope(bounds[i + 1]))))
        return int(round(slope(run)))

    # the columns of the stretch
    xs, zs = zip(*[fr.xz(s, t) for s in (0, fr.L) for t in (-hw, hw)])
    X0, X1, Z0, Z1 = int(min(xs)), int(max(xs)) + 1, int(min(zs)), int(max(zs)) + 1
    H = g.box(X0, Z0, X1, Z1)
    inside = {}
    for z in range(Z0, Z1 + 1):
        for x in range(X0, X1 + 1):
            s, t = fr.st(x, z)
            if not (0 <= s <= fr.L and abs(t) <= hw):
                continue
            stt = station(s)
            side = 1 if t >= stt["t0"] else -1
            sd = stt["sides"][side]
            q = (sd["rim_t"] - t) * side
            h = int(H[z - Z0, x - X0])
            plan.old[(x, z)] = h
            inside[(x, z)] = (s, t, side, q)
            y = level(s, side, q)
            if y is not None and y < h:
                plan.top[(x, z)] = y

    # plates and cracks on the treads, and cracks across the plateau just behind the lip
    pc = sc["plate"]["cell"]
    centres = {}

    def centre(i, j):
        if (i, j) not in centres:
            r = rng_for(seed, "cell", i, j)
            centres[(i, j)] = (i * pc + r.uniform(0, pc), j * pc + r.uniform(0, pc), r.uniform(-1, 1), r.uniform(-1, 1),
                               r.randint(*sc["plate"]["tilt"]), r.randint(*sc["plate"]["crack_depth"]))
        return centres[(i, j)]

    for (x, z), (s, t, side, q) in inside.items():
        i, j = int(x // pc), int(z // pc)
        cand = sorted(((cx - x) ** 2 + (cz - z) ** 2, (cx, cz, a, b, tilt, cd))
                      for di in (-1, 0, 1) for dj in (-1, 0, 1)
                      for cx, cz, a, b, tilt, cd in [centre(i + di, j + dj)])
        (d1, c1), (d2, _) = cand[0], cand[1]
        edge = math.sqrt(d2) - math.sqrt(d1) < 1.2
        cx, cz, a, b, tilt, cd = c1
        if (x, z) in plan.top:
            # a tilted plate: lower on one side, by up to `tilt`
            fx = ((x - cx) * a + (z - cz) * b) / pc
            y = plan.top[(x, z)] - max(0, int(round((fx + 1) / 2 * tilt)))
            if edge:
                y -= cd
            plan.top[(x, z)] = min(y, plan.old[(x, z)])
        elif -12 <= q < -sc["undercut"]["depth"] and edge:
            plan.top[(x, z)] = plan.old[(x, z)] - 3        # the ground cracking before the edge
            plan.count("plateau cracks")

    # the undercut lip, where the group says so
    for (x, z), (s, t, side, q) in inside.items():
        if -sc["undercut"]["depth"] <= q < 0 and group(int(round(s / every)))[3]:
            stt = station(s)
            sd = stt["sides"][side]
            y0 = level(s, side, 0)
            if y0 is None:
                continue
            top = plan.old[(x, z)] - sc["undercut"]["overhang_top"]
            if top > y0 + 2:
                plan.carve.setdefault((x, z), []).append((y0 + 1, top))
                plan.count("undercut columns")

    # side fissures back into the plateau
    fis = sc["fissures"]
    fissure_lines = []
    for side in (-1, 1):
        r = rng_for(seed, "fissure", side)
        for _ in range(r.randint(*fis["per_side"])):
            s = r.uniform(30, fr.L - 30)
            stt = station(s)
            sd = stt["sides"][side]
            y0 = level(s, side, 0)
            if y0 is None:
                continue
            ang = math.radians(r.uniform(-25, 25))
            length = r.randint(*fis["length"])
            w0 = r.randint(*fis["width"])
            pts = []
            ss, tt = s, sd["rim_t"]
            for k in range(length):
                ss += math.sin(ang) + r.uniform(-0.3, 0.3)
                tt += side * math.cos(ang)
                pts.append((ss, tt, max(1, int(round(w0 * (1 - k / length) + 0.5)))))
            fissure_lines.append((side, y0, pts))
            for k, (ss, tt, w) in enumerate(pts):
                floor_y = y0 + int(k / length * 10)
                for dw in range(-(w // 2), w - w // 2):
                    x, z = map(round, fr.xz(ss, tt + dw))
                    if (x, z) in plan.old:
                        plan.top[(x, z)] = min(plan.top.get((x, z), plan.old[(x, z)]), floor_y)
                        if k % 4 == 0 and dw == 0:
                            plan.put[(x, floor_y, z)] = pal["vein_core"]
                        else:
                            plan.put[(x, floor_y, z)] = pal["vein_seep"]
            plan.count("fissures")

    # dressing: every cut column's new surface, and the riser faces it exposes
    def top_of(x, z):
        return plan.top.get((x, z), plan.old.get((x, z)))

    for (x, z), y in plan.top.items():
        s, t, side, q = inside[(x, z)]
        stt = station(s)
        D = max(1, stt["sides"][side]["rim_y"] - stt["floor"])
        frac = (stt["sides"][side]["rim_y"] - y) / D
        tread = pal["tread"] if frac > 0.55 else pal["face_lower"] if frac > 0.3 else pal["face_upper"]
        plan.put.setdefault((x, y, z), tread)
        low = min((top_of(x + dx, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))
                   if top_of(x + dx, z + dz) is not None), default=y)
        if low < y - 1:
            for yy in range(low + 1, y):
                f2 = (stt["sides"][side]["rim_y"] - yy) / D
                if f2 > 0.3:
                    plan.put.setdefault((x, yy, z), pal["face_lower"] if f2 < 0.7 else pal["tread"])
                elif (yy // 3) % 2 == 0:
                    plan.put.setdefault((x, yy, z), pal["face_upper"])   # tuff bands in the torn upper face

    # veins: a line along the floor off the road, branches out and up the risers
    vs = spec["veins"]
    vr_rng = random.Random(seed + 1)
    main_vein = []
    wob = 0.0
    for k in range(int(fr.L) + 1):
        s = float(k)
        stt = station(s)
        rt = road_t(s)
        wob += vr_rng.uniform(-0.6, 0.6)
        wob = max(-10, min(10, wob))
        t = stt["t0"] + wob
        if rt is not None and abs(t - rt) < 12:
            t = rt + (12 if t >= rt else -12)
        main_vein.append((s, t))

    def paint_line(pts, width, kind):
        n = 0
        for s, t in pts:
            for dw in range(-(width // 2), width - width // 2):
                x, z = map(round, fr.xz(s, t + dw))
                y = top_of(x, z)
                if y is None:
                    continue
                edge = abs(dw) == width // 2 and width >= 3
                blk = pal["vein_halo"] if edge else pal["vein_core"] if kind != "thin" else (
                    pal["vein_core"] if (int(s) % 3) else pal["vein_seep"])
                plan.put[(x, y, z)] = blk
                plan.put[(x, y - 1, z)] = blk
                n += 1
        return n

    plan.count("vein columns (main)", paint_line(main_vein, vs["main_width"], "main"))
    # the open wound: pick the stretch of the main line whose floor is widest
    ws = vs["wound"]
    best = max(range(20, int(fr.L) - ws["length"] - 20, 5),
               key=lambda k0: sum(abs(station(k)["sides"][1]["edge_t"] - station(k)["sides"][-1]["edge_t"])
                                  for k in range(k0, k0 + ws["length"], 10)))
    wound = main_vein[best: best + ws["length"]]
    crust_to = int(len(wound) * 0.6)
    pool_at = None
    for i, (s, t) in enumerate(wound):
        for dw in range(-(ws["width"] // 2), ws["width"] - ws["width"] // 2):
            x, z = map(round, fr.xz(s, t + dw))
            y = top_of(x, z)
            if y is None:
                continue
            bottom = y - ws["depth"]
            plan.carve.setdefault((x, z), []).append((bottom + 1, y))
            plan.put[(x, bottom, z)] = pal["vein_halo"] if abs(dw) < ws["width"] // 2 else pal["vein_seep"]
            for yy in range(bottom + 1, y + 1):
                plan.put.pop((x, yy, z), None)
            if i < crust_to:
                plan.put[(x, y, z)] = pal["wound_crust"]
                plan.put[(x, y - 1, z)] = pal["vein_core"]
        if i == crust_to + (len(wound) - crust_to) // 2:
            pool_at = (s, t)
    plan.count("wound length", len(wound))

    # branches
    branch_pts = []
    s = vr_rng.uniform(*vs["branch_every"])
    side = 1
    while s < fr.L - 10:
        side = -side
        k = int(s)
        bs, bt = main_vein[k]
        ang = math.radians(vr_rng.uniform(*vs["branch_angle"])) * (1 if vr_rng.random() < 0.5 else -1)
        pts, width = [], 2
        ss, tt = bs, bt
        splits = []
        for step in range(400):
            ss += math.sin(ang) * 0.9 + vr_rng.uniform(-0.25, 0.25)
            tt += side * math.cos(ang)
            if not 0 <= ss <= fr.L or abs(tt) > hw:
                break
            x, z = map(round, fr.xz(ss, tt))
            if (x, z) not in inside:
                break
            q = inside[(x, z)][3]
            pts.append((ss, tt))
            if q <= 0:
                break
            if step > 12 and vr_rng.random() < vs["split_chance"] / 20:
                splits.append((ss, tt, ang))
        branch_pts.append((bs, bt))
        plan.count("vein columns (branches)", paint_line(pts, width, "branch"))
        # up the riser where the branch meets the lip: a seam in the face
        if pts:
            x, z = map(round, fr.xz(*pts[-1]))
            y = top_of(x, z)
            if y is not None:
                for yy in range(y, y + vr_rng.randint(*vs["up_the_face"])):
                    for dz in (0,):
                        plan.put[(x, yy, z)] = pal["vein_core"] if yy % 2 else pal["vein_halo"]
                plan.count("seams up the face")
        for ss0, tt0, a0 in splits:
            a1 = a0 + math.radians(vr_rng.choice((-1, 1)) * vr_rng.uniform(20, 40))
            sub = []
            ss, tt = ss0, tt0
            for step in range(vr_rng.randint(20, 50)):
                ss += math.sin(a1) * 0.9
                tt += side * math.cos(a1)
                x, z = map(round, fr.xz(ss, tt))
                if (x, z) not in inside or inside[(x, z)][3] <= 0:
                    break
                sub.append((ss, tt))
            plan.count("vein columns (splits)", paint_line(sub, 1, "thin"))
        s += vr_rng.uniform(*vs["branch_every"])

    # crystals where a branch leaves the main vein
    for bs, bt in branch_pts:
        r = rng_for(seed, "crystal", int(bs))
        for _ in range(r.randint(3, 7)):
            x, z = map(round, fr.xz(bs + r.uniform(-3, 3), bt + r.uniform(-3, 3)))
            y = top_of(x, z)
            if y is None or (x, y, z) in plan.put and plan.put[(x, y, z)] in (pal["vein_core"], pal["vein_halo"]):
                continue
            blk = pal["crystal"]
            plan.put[(x, y + 1, z)] = blk + ("[facing=up]" if blk.startswith("legendarymonuments") else "[facing=up]")
            plan.count("crystals")

    # portal sheets, each with light blocks round it
    fxs = spec["portal_sheets"]
    tag = fxs["tag"]
    area = "rift_fx_" + st_spec["id"]

    def quat_y(phi):
        return (0.0, math.sin(phi / 2), 0.0, math.cos(phi / 2))

    def quat_mul(a, b):
        ax, ay, az, aw = a
        bx, by, bz, bw = b
        return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)

    def rotate(qt, v):
        x, y, z, w = qt
        vx, vy, vz = v
        # v' = q v q*
        ix = w * vx + y * vz - z * vy
        iy = w * vy + z * vx - x * vz
        iz = w * vz + x * vy - y * vx
        iw = -x * vx - y * vy - z * vz
        return (ix * w + iw * -x + iy * -z - iz * -y, iy * w + iw * -y + iz * -x - ix * -z,
                iz * w + iw * -z + ix * -y - iy * -x)

    def sheet(pos, qt, scale, what):
        """A sheet centred on pos: the model (portal, axis x: 1 x 1 in x-y, thin in z) scaled, rotated by qt."""
        half = (scale[0] / 2, 0.0 if what != "pool" else scale[1] / 2, 0.5 * scale[2])
        c = rotate(qt, half)
        tr = [-c[0], -c[1], -c[2]]
        f = lambda v: "[%s]" % ",".join("%.4ff" % a for a in v)
        big = max(scale)
        plan.entities.append(
            "summon minecraft:block_display %.2f %.2f %.2f {block_state:{Name:\"minecraft:nether_portal\",Properties:"
            "{axis:\"x\"}},brightness:{sky:15,block:15},view_range:2.0f,width:%.1ff,height:%.1ff,Tags:[\"%s\",\"%s\"],"
            "transformation:{left_rotation:%s,right_rotation:[0f,0f,0f,1f],translation:%s,scale:%s}}"
            % (pos[0], pos[1], pos[2], big + 2, big + 2, tag, area, f(qt), f(tr), f(scale)))
        plan.count("portal sheets")

    def lights(points):
        for x, y, z in points:
            if (x, y, z) not in plan.put:
                plan.put[(x, y, z)] = "minecraft:light[level=15]"
                plan.count("light blocks")

    phi = math.atan2(-fr.u[1], fr.u[0])   # model x along the stretch
    # 1. a torn window in the lip riser: the undercut group with the deepest lip on the east (+t) side
    cand = [st_ for st_ in sts if group(int(round(st_["s"] / every)))[3] and 40 < st_["s"] < fr.L - 40]
    win = max(cand or sts, key=lambda st_: st_["sides"][1]["rim_y"] - st_["floor"])
    sdw = win["sides"][1]
    y0 = level(win["s"], 1, 0) or sdw["rim_y"] - 20
    wx, wz = fr.xz(win["s"], sdw["rim_t"] - 2)
    height = max(8, min(16, sdw["rim_y"] - y0 - 2))
    sheet((wx, y0 + 1, wz), quat_y(phi), (12.0, float(height), 1.0), "window")
    lights([(round(fr.xz(win["s"] + d, sdw["rim_t"] - 4)[0]), y0 + 1 + hy, round(fr.xz(win["s"] + d, sdw["rim_t"] - 4)[1]))
            for d in (-5, 0, 5) for hy in (2, int(height) - 2)])
    views = {"window": [round(wx), y0 + 6, round(wz)]}
    # 2. a pool lying in the open part of the wound
    if pool_at:
        px, pz = fr.xz(*pool_at)
        py = top_of(round(px), round(pz))
        qt = quat_mul(quat_y(phi), (0.7071, 0.0, 0.0, 0.7071))
        sheet((px, py - ws["depth"] + 1.05, pz), qt, (14.0, 6.0, 1.0), "pool")
        lights([(round(fr.xz(pool_at[0] + d, pool_at[1] + e)[0]), py + 1, round(fr.xz(pool_at[0] + d, pool_at[1] + e)[1]))
                for d in (-6, 0, 6) for e in (-5, 5)])
        views["pool"] = [round(px), py + 4, round(pz)]
    # 3. a curtain filling the widest fissure's mouth
    side, fy0, pts = max(fissure_lines, key=lambda f: len(f[2]))
    ms, mt, _ = pts[3]
    fx, fz = fr.xz(ms, mt)
    fang = math.atan2(-(fr.xz(*pts[8][:2])[1] - fz), fr.xz(*pts[8][:2])[0] - fx)
    sheet((fx, fy0 + 1, fz), quat_y(fang), (6.0, 10.0, 1.0), "curtain")
    lights([(round(fx), fy0 + 2, round(fz)), (round(fx), fy0 + 8, round(fz))])
    views["curtain"] = [round(fx), fy0 + 5, round(fz)]

    # the sky crack sample
    skc = spec["sky_crack"]
    sk = random.Random(seed + 7)
    y_lo, y_hi = skc["y"]
    mid_y = (y_lo + y_hi) // 2

    def crack_line(pts, width):
        n = 0
        for i, (s, t) in enumerate(pts):
            w = width + sk.randint(-2, 1)
            th = skc["thickness"] + sk.randint(-1, 2)
            yc = mid_y + int(8 * math.sin(s / 90.0))
            for dw in range(-(w // 2), w - w // 2):
                x, z = map(round, fr.xz(s, t + dw))
                core = abs(dw) <= max(1, w // 5)
                for yy in range(yc - th // 2, yc + th - th // 2):
                    inner = core and abs(yy - yc) <= th // 4
                    plan.put[(x, yy, z)] = pal["sky_core"] if inner else pal["sky_halo"]
                    n += 1
        return n

    skmain, tt = [], 0.0
    for k in range(-60, int(fr.L) + 60):
        tt += sk.uniform(-0.8, 0.8)
        tt = max(-25, min(25, tt))
        skmain.append((float(k), tt))
    plan.count("sky crack blocks", crack_line(skmain, skc["main_width"]))
    s = 30.0
    side = 1
    while s < fr.L:
        side = -side
        ang = math.radians(sk.uniform(30, 60))
        bpts, ss, tt = [], s, skmain[int(s) + 60][1]
        for _ in range(sk.randint(60, 150)):
            ss += math.sin(ang) * 0.8
            tt += side * math.cos(ang)
            bpts.append((ss, tt))
        plan.count("sky crack blocks", crack_line(bpts, skc["branch_width"]))
        s += sk.uniform(70, 140)
    views["sky crack, under it"] = [round(fr.xz(fr.L / 2, 0)[0]), mid_y - 60, round(fr.xz(fr.L / 2, 0)[1])]

    # checks: sampled from the final plan
    rs = random.Random(seed + 9)
    for (x, z), y in plan.top.items():
        if rs.random() < 0.02:
            plan.checks.append((x, y + 1, z, ["minecraft:air"], "cut: air above the new ground"))
    for (x, y, z), b in plan.put.items():
        base = b.split("[")[0]
        if base in (pal["vein_core"], pal["vein_halo"]) and rs.random() < 0.1:
            plan.checks.append((x, y, z, [base], "vein"))
        elif base in (pal["sky_core"], pal["sky_halo"]) and rs.random() < 0.01:
            plan.checks.append((x, y, z, [base], "sky crack"))
        elif base == "minecraft:light" and rs.random() < 0.5:
            plan.checks.append((x, y, z, [base], "light block"))
    plan.fx_area = area
    plan.fx_box = None
    plan.views = views
    plan.frame = fr
    plan.stations = sts
    plan.fallbacks = fallbacks
    plan.pal = pal
    plan.spec = spec
    plan.inside = inside
    return plan


# ------------------------------------------------------------------ writing


def biome_cells(plan):
    """4x4 biome cells whose 16 columns are all inside the lip (q >= 0)."""
    cols = {k for k, v in plan.inside.items() if v[3] >= 0}
    cells = set()
    for x, z in cols:
        cells.add((x >> 2, z >> 2))
    return sorted(c for c in cells if all((c[0] * 4 + i, c[1] * 4 + j) in cols for i in range(4) for j in range(4)))


def block_functions(plan):
    tiles = {}

    def add(x, z, line):
        tiles.setdefault((x // TILE, z // TILE), []).append(line)

    for (x, z), y in plan.top.items():
        old = plan.old[(x, z)]
        if y < old:
            add(x, z, "fill %d %d %d %d %d %d minecraft:air" % (x, y + 1, z, x, old + 3, z))
    for (x, z), ranges in plan.carve.items():
        for y0, y1 in ranges:
            if y1 >= y0:
                add(x, z, "fill %d %d %d %d %d %d minecraft:air" % (x, y0, z, x, y1, z))
    # blocks in columns, as vertical runs
    cols = {}
    for (x, y, z), b in plan.put.items():
        cols.setdefault((x, z), {})[y] = b
    for (x, z), col in cols.items():
        run = None
        for y in sorted(col) + [None]:
            b = col.get(y) if y is not None else None
            if run and y is not None and b == run[2] and y == run[1] + 1:
                run[1] = y
                continue
            if run:
                add(x, z, ("setblock %d %d %d %s" % (x, run[0], z, run[2])) if run[0] == run[1] else
                    "fill %d %d %d %d %d %d %s" % (x, run[0], z, x, run[1], z, run[2]))
            run = [y, y, b] if y is not None else None
    out, order = {}, []
    for t in sorted(tiles):
        name = "blocks_%d_%d" % t
        lines = FL.ensure_loaded(["# Generated by tools/rift_fracture.py: the chasm stretch, tile %d %d" % t] + tiles[t])
        probs = FL.check_lines(lines, name)
        if probs:
            raise FractureError("function %s would be refused: %s" % (name, probs[:3]))
        out[name] = lines
        order.append(name)
    return out, order


def biome_functions(plan, spec):
    cells = biome_cells(plan)
    y0, y1 = spec["biome"]["y"]
    rows = {}
    for cx, cz in cells:
        rows.setdefault(cz, []).append(cx)
    cmds = {}
    for cz, cxs in rows.items():
        cxs.sort()
        start = prev = cxs[0]
        for cx in cxs[1:] + [None]:
            if cx is not None and cx == prev + 1 and cx - start < 2:
                prev = cx
                continue
            x0, x1, z0, z1 = start * 4, prev * 4 + 3, cz * 4, cz * 4 + 3
            cmds.setdefault((x0 // TILE, z0 // TILE), []).append(
                "fillbiome %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, spec["biome"]["id"]))
            if cx is not None:
                start = prev = cx
    out, order = {}, []
    for t, lines in sorted(cmds.items()):
        name = "biome_%d_%d" % t
        x0, z0 = t[0] * TILE, t[1] * TILE
        out[name] = (["# Generated by tools/rift_fracture.py: cobblers:the_rift inside the lip, tile %d %d" % t,
                      "forceload add %d %d %d %d" % (x0, z0, x0 + TILE - 1, z0 + TILE - 1)] + lines +
                     ["forceload remove %d %d %d %d" % (x0, z0, x0 + TILE - 1, z0 + TILE - 1)])
        order.append(name)
    return out, order, len(cells)


def fx_functions(plan):
    """Force-load the sheets' chunks, wait for their entities to load (they arrive ~20 ticks after the chunk), kill this
    area's tag, summon, then count. Re-running never duplicates."""
    import re
    ns = "cobblers"
    boxes = []
    for c in plan.entities:
        m = re.match(r"summon \S+ (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)", c)
        x, z = float(m.group(1)), float(m.group(3))
        # a sheet's chunks and its neighbours (the largest sheet is 16 long): a few chunks each, far under 256
        boxes.append("%d %d %d %d" % (int(x) - 24, int(z) - 24, int(x) + 24, int(z) + 24))
    area = plan.fx_area
    wait = plan.spec["portal_sheets"]["wait_ticks"]
    # the area tag is this stretch's alone, so the selector needs no volume: every sheet's chunks are loaded
    sel = "@e[type=minecraft:block_display,tag=%s]" % area
    sid = plan.spec["stretch"]["id"]
    return {
        "fx_%s" % sid: [
            "# Generated by tools/rift_fracture.py: the portal sheets of %s. Force-load, then wait %d ticks for the "
            "chunks' entities to load before killing and summoning (an entity loads ~20 ticks after its chunk)" % (area, wait)]
            + ["forceload add %s" % b for b in boxes]
            + ["schedule function %s:rift_fracture/fx_%s_go %dt replace" % (ns, sid, wait)],
        "fx_%s_go" % sid: [
            "# chunks-loaded-by: %s:rift_fracture/fx_%s" % (ns, sid),
            "kill %s" % sel] + plan.entities + [
            "scoreboard objectives add cobblers.rift_fx dummy",
            "execute store result score #%s cobblers.rift_fx if entity %s" % (area, sel)]
            + ["forceload remove %s" % b for b in boxes],
    }, sel, len(plan.entities)


def biome_json(spec):
    b = spec["biome"]
    return {"has_precipitation": b["has_precipitation"], "temperature": b["temperature"], "downfall": b["downfall"],
            "effects": b["effects"], "spawners": {}, "spawn_costs": {}, "carvers": {}, "features": []}


def write(plan):
    spec = plan.spec
    bf, border = block_functions(plan)
    biof, biorder, ncells = biome_functions(plan, spec)
    fxf, sel, nfx = fx_functions(plan)
    for d in (PACK, BIOME_PACK):
        if d.exists():
            shutil.rmtree(d)
    fdir = PACK / "data" / "cobblers" / "function" / "rift_fracture"
    fdir.mkdir(parents=True)
    (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                      "Cobblers: the Rift as a fracture, prototype stretch (tools/rift_fracture.py)"}}) + "\n",
                                      encoding="utf-8")
    for name, lines in {**bf, **biof, **fxf}.items():
        (fdir / (name + ".mcfunction")).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (fdir / "index.txt").write_text("\n".join(border + biorder + ["fx_%s" % spec["stretch"]["id"]]) + "\n",
                                    encoding="utf-8", newline="\n")
    ns, path = spec["biome"]["id"].split(":")
    bdir = BIOME_PACK / "data" / ns / "worldgen" / "biome"
    bdir.mkdir(parents=True)
    (bdir / (path + ".json")).write_text(json.dumps(biome_json(spec), indent=2) + "\n", encoding="utf-8")
    (BIOME_PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Rift biome (tools/rift_fracture.py)"}}) + "\n", encoding="utf-8")
    fr = plan.frame
    lip_out = []
    for st_ in plan.stations[::10]:
        for side in (-1, 1):
            sd = st_["sides"][side]
            x, z = fr.xz(st_["s"], sd["rim_t"] + side * 3)
            xi, zi = fr.xz(st_["s"], sd["rim_t"] - side * 6)
            lip_out.append({"outside": [round(x), round(z)], "inside": [round(xi), round(zi)], "rim_y": sd["rim_y"]})
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps({
        "counts": plan.counts, "fallbacks": plan.fallbacks, "palette": plan.pal, "views": plan.views,
        "checks": plan.checks, "entities_expected": nfx, "entity_area_tag": plan.fx_area, "entity_selector": sel,
        "biome_cells": ncells, "biome_edge_samples": lip_out,
        "block_functions": border, "biome_functions": biorder,
        "commands": sum(len(v) for v in {**bf, **biof, **fxf}.values()),
        "blocks_placed": sum(1 for b in plan.put.values() if b != "minecraft:air"),
        "columns_cut": len(plan.top),
        "blocks_removed": sum(plan.old[k] + 3 - v for k, v in plan.top.items() if v < plan.old[k]),
    }, indent=0), encoding="utf-8")
    return border, biorder, nfx


# ------------------------------------------------------------------ verify


def entity_count(world, area_tag, x0=None):
    """block_display entities carrying area_tag, read from the world's entity region files."""
    import nbt
    n = 0
    for p in sorted((Path(world) / "entities").glob("r.*.*.mca")):
        for _, _, ch in nbt.region_chunks(p):
            for e in ch.get("Entities") or []:
                if e.get("id") == "minecraft:block_display" and area_tag in (e.get("Tags") or []):
                    n += 1
    return n


def verify(world):
    import build_audit
    import runtime_guard
    runtime_guard.check(world, "read")
    if not PLAN.is_file():
        print("FAIL: no derived/rift_fracture/plan.json: run the build first")
        return 1
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    kinds = {c[4] for c in p["checks"]}
    need = {"cut: air above the new ground", "vein", "sky crack", "light block"}
    if not need <= kinds or not p.get("entities_expected"):
        print("FAIL: the plan checks %s and expects %s entities: not everything the build makes" %
              (sorted(kinds), p.get("entities_expected")))
        return 1
    W = build_audit.World(world)
    by, bad = {}, {}
    for x, y, z, allowed, what in p["checks"]:
        got = W.block(x, y, z)
        ok = got in allowed
        by.setdefault(what, [0, 0])[0 if ok else 1] += 1
        if not ok:
            bad.setdefault(what, []).append((x, y, z, got))
    for k in sorted(by):
        good, wrong = by[k]
        print("%-32s %6d of %6d as planned%s" % (k, good, good + wrong, ("   e.g. %s" % bad[k][:2]) if wrong else ""))
    n = entity_count(world, p["entity_area_tag"])
    print("%-32s %6d, expected %d" % ("portal sheets (entities)", n, p["entities_expected"]))
    total = sum(b for _, b in by.values()) + (0 if n == p["entities_expected"] else 1)
    print("rift fracture: %s" % ("clean" if total == 0 else "%d MISMATCHES" % total))
    return 0 if total == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "verify"))
    ap.add_argument("--source-root")
    ap.add_argument("--world")
    ap.add_argument("--server-dir", help="check the palette's mod blocks against this server's jars (needs the lock)")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        if not a.world:
            ap.error("verify needs --world <stopped world copy>")
        return verify(a.world)
    plan = build(a.source_root, a.server_dir)
    border, biorder, nfx = write(plan)
    p = json.loads(PLAN.read_text(encoding="utf-8"))
    print("rift fracture (%s): %d block functions, %d biome functions, %d commands" %
          (plan.spec["stretch"]["id"], len(border), len(biorder), p["commands"]))
    print("  columns cut %d, blocks removed %d, blocks placed %d, biome cells %d, portal sheets %d" %
          (p["columns_cut"], p["blocks_removed"], p["blocks_placed"], p["biome_cells"], nfx))
    print("  counts:", ", ".join("%s %d" % kv for kv in sorted(plan.counts.items())))
    if plan.fallbacks:
        print("  fallbacks used:", plan.fallbacks)
    if not a.server_dir:
        print("  mod blocks NOT checked against a server's jars (no --server-dir)")
    print("  views:", plan.views)
    return 0


if __name__ == "__main__":
    sys.exit(main())
