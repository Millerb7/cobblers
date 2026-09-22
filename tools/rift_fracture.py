#!/usr/bin/env python
"""The Rift as a fracture: one prototype stretch (data/rift_fracture.json, docs/mechanics/RIFT_FRACTURE.md).

Everything is decided from the canonical heightmap (tools/ground.py) and committed data; nothing reads a world to
decide (the ground rule). A world is read only by `verify`, to check.

  scarps       the gentle walls cut into a sheer lip riser (23+ blocks where the depth allows: a lethal drop) and
               shattered steps down to the floor, jittered along the length; tilted plates with cracks on the treads;
               the lip undercut where it overhangs; side fissures running back into the plateau. Cut only: the rim
               and the floor edge stay where they are
  veins        a branching glowing crack from a line along the floor, branches climbing the risers: a violet bed of galar
               particle blocks one down (light 15) under a slot holding dormant crystals (mint-white, light 15) or
               open, crying obsidian at its edges and where it thins; one open wound 9 wide, part crusted with glass
  crystals     distortion crystals where a branch leaves the main vein
  sky crack    a sample of the candidate fracture in the sky over the stretch, y360-400, every part 8 thick
  portal       block_display sheets of the nether portal texture, as glimpses only: two sheets deep inside a narrow tear
               in a solid lip face (the rock hides every edge), and a pool lying in the wound; light blocks round them.
               Summoned by a re-runnable function that force-loads, waits for the entities to load, kills its own tag
               and summons
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
        self.caps = {}       # (x, z) -> y of the glass cap over a crack (the surface a walker stands on)
        self.crag = {}       # (x, z) -> top y of the upthrust rock built on the plateau
        self.path = {}       # (x, z) -> surface y of an entrance's path
        self.water = []      # (x, y, z) water sources: the deliberate falls
        self.wound_floor = {}  # (x, z) -> the surface a walker stands on in the wound (its crust or its floor)
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

    # the rim's character along each side: crags, the sheer drop or broken plates, in irregular lengths
    rim = spec["rim"]
    segs = {}
    for side_ in (-1, 1):
        r = rng_for(seed, "segments", side_)
        kinds = list(rim["mix"])
        wts = [rim["mix"][k] for k in kinds]
        s0, prev, out = -30.0, None, []
        while s0 < fr.L + 30:
            ln = r.uniform(*rim["segment_length"])
            k = r.choices(kinds, wts)[0]
            if k == prev:
                k = r.choices(kinds, wts)[0]
            out.append((s0, s0 + ln, k))
            prev, s0 = k, s0 + ln
        segs[side_] = out

    # the entrances: where a settlement's road crosses this stretch's rim, a gap in the crags
    P = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    entrances = []
    for e in spec.get("entrances") or []:
        e_side = -1 if e["side"] == "west" else 1
        st_ = P["settlements"][e["settlement"]]
        e_road = next(r for r in (st_.get("roads") or []) + ((st_.get("plan") or {}).get("streets") or [])
                      if r.get("id") == e["road"])
        pts = [fr.st(*p) for p in e_road["polyline"]]
        near = [s for s, t in pts if 0 <= s <= fr.L and abs(t - station(s)["sides"][e_side]["rim_t"]) < 80]
        if not near:
            raise FractureError("entrance %s: its road does not cross this stretch's %s rim" % (e["id"], e["side"]))
        entrances.append((e_side, sum(near) / len(near), e))

    def seg(side_, s):
        for e_side, es, e in entrances:
            if e_side == side_ and abs(s - es) <= e["gap"]:
                return "gap"
        return next((k for a, b, k in segs[side_] if a <= s < b), "sheer")

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
        capsp = spec["caps"]
        glow = rng_for(seed, "capglow", round(cx), round(cz)).randrange(capsp["glow_one_in"]) == 0
        if (x, z) in plan.top:
            # a tilted plate: lower on one side, by up to `tilt`
            fx = ((x - cx) * a + (z - cz) * b) / pc
            y = min(plan.top[(x, z)] - max(0, int(round((fx + 1) / 2 * tilt))), plan.old[(x, z)])
            plan.top[(x, z)] = y
            if edge and seg(side, s) != "gap":
                # the crack between plates, capped at the plate's surface so nothing that walks falls in
                plan.top[(x, z)] = y - cd
                plan.caps[(x, z)] = y
                plan.put[(x, y, z)] = capsp["glow"] if glow else capsp["dark"]
                if glow:
                    plan.put[(x, y - cd, z)] = pal["vein_seep"]
                plan.count("capped crack columns")
        elif -12 <= q < -sc["undercut"]["depth"] and edge and seg(side, s) in ("sheer", "plates"):
            old = plan.old[(x, z)]
            plan.top[(x, z)] = old - 3        # the ground cracking before the edge, capped flush
            plan.caps[(x, z)] = old
            plan.put[(x, old, z)] = capsp["glow"] if glow else capsp["dark"]
            if glow:
                plan.put[(x, old - 3, z)] = pal["vein_seep"]
            plan.count("plateau cracks")

    # the undercut lip, where the group says so
    for (x, z), (s, t, side, q) in inside.items():
        if -sc["undercut"]["depth"] <= q < 0 and group(int(round(s / every)))[3] and seg(side, s) == "sheer":
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
            if seg(side, s) not in ("sheer", "plates"):
                continue
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
                        cap = plan.caps.pop((x, z), None)          # a fissure opens any crack it cuts through
                        if cap is not None:
                            plan.put.pop((x, cap, z), None)
                        if k % 4 == 0 and dw == 0:
                            plan.put[(x, floor_y, z)] = pal["vein_bed"]
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

    # the upthrust rim: slabs shoved up where the ground tore, high at the lip and dipping back into the plateau
    rimpal = rim["materials"]
    streak = rim["streak"]["block"]
    if have is not None and streak not in have:
        streak = rim["streak"]["fallback"]
    seams_n = 0

    def raise_col(x, z, top, seam=False):
        base = plan.old.get((x, z))
        if base is None or top <= base or (x, z) in plan.top:
            return
        if top > plan.crag.get((x, z), base):
            plan.crag[(x, z)] = top

    def slab(side, s_c, length, width, height, dip, set_back, r, peak=False):
        nonlocal seams_n
        lean = r.uniform(-0.35, 0.35)
        seam = (not peak) and r.randrange(rim["seams"]["one_in_slabs"]) == 0
        for ds in range(-length // 2, length // 2 + 1):
            s = s_c + ds
            if not 0 <= s <= fr.L or seg(side, s) == "gap":
                continue
            sd = station(s)["sides"][side]
            for dq in range(1, width + 1):
                t = sd["rim_t"] + side * (dq + set_back)
                x, z = map(round, fr.xz(s, t))
                if peak:
                    rr = math.hypot(ds / (length / 2), (dq - width / 2) / (width / 2))
                    if rr >= 1:
                        continue
                    h = height * (1 - rr ** 1.6)
                else:
                    u_ = 2 * ds / length - lean
                    f_len = max(0.0, 1 - abs(u_) ** 2.2)
                    h = height * f_len * (1 - dip * dq / width)
                h += rng_for(seed, "jag", x, z).randint(-3, 3)
                if h < 3:
                    continue
                raise_col(x, z, plan.old.get((x, z), 0) + int(h))
                if seam and dq == 1 and ds % 7 == 0:
                    seams_n += 1
                    plan.seams = getattr(plan, "seams", [])
                    plan.seams.append((x, z, plan.old.get((x, z), 0), int(h)))

    for side in (-1, 1):
        r = rng_for(seed, "slabs", side)
        for a, b, kind in segs[side]:
            if kind not in ("crags", "plates"):
                continue
            p = rim[kind]
            s = a + r.uniform(0, p["every"][1])
            while s < b:
                slab(side, s, r.randint(*p["length"]), r.randint(*p["width"]), r.randint(*p["height"]),
                     r.uniform(*p.get("dip", [0.0, 0.5])), r.randint(*p["set_back"]), r)
                plan.count("%s slabs" % kind)
                s += r.uniform(*p["every"])
    pk = rim["peaks"]
    pside = -1 if pk["side"] == "west" else 1
    r = rng_for(seed, "peaks")
    crag_spans = [(a, b) for a, b, k in segs[pside] if k == "crags" and b > 20 and a < fr.L - 20]
    for i in range(pk["count"]):
        if not crag_spans:
            break
        a, b = crag_spans[i % len(crag_spans)]
        s_c = r.uniform(max(a, 20), min(b, fr.L - 20))
        rad = r.randint(*pk["radius"])
        slab(pside, s_c, 2 * rad + 6, 2 * rad, r.randint(*pk["height"]), 0, 2, r, peak=True)
        plan.count("peaks")
    for (x, z), top in plan.crag.items():
        base = plan.old[(x, z)]
        for y in range(base + 1, top + 1):
            band = (y // 4 + x // 9 + z // 11) % len(rimpal)
            b_ = rimpal[band]
            if rng_for(seed, "streak", x // 6, y // 4, z // 6).randrange(rim["streak"]["one_in_bands"]) == 0:
                b_ = streak
            plan.put[(x, y, z)] = b_
    for x, z, base, h in getattr(plan, "seams", []):
        for y in range(base + 2, base + int(h * 0.7)):
            plan.put[(x, y, z)] = pal["vein_bed"] if (y // 3) % 2 else pal["vein_seep"]
    plan.count("crag columns", len(plan.crag))

    # the entrances: a switchback down the scarp through the gap, the guard at the trailhead in the open
    views_extra = {}
    for e_side, es, e in entrances:
        stt = station(es)
        sd = stt["sides"][e_side]
        t_start = sd["rim_t"] - e_side * 14            # out on the plateau
        t_end = sd["edge_t"] - e_side * 4              # in on the floor
        legs, hwid = e["legs"], e["leg_half_width"]
        corners = [(es - hwid if k % 2 == 0 else es + hwid, t_start + (t_end - t_start) * k / legs) for k in range(legs + 1)]
        corners[0] = (es, t_start)
        pts = []
        for (s1, t1), (s2, t2) in zip(corners, corners[1:]):
            n = int(max(abs(s2 - s1), abs(t2 - t1)) * 2) + 1
            pts += [(s1 + (s2 - s1) * i / n, t1 + (t2 - t1) * i / n) for i in range(n)]
        total = len(pts)
        y_start = plan.old.get(tuple(map(round, fr.xz(es, t_start))))
        y_end = top_of(*map(round, fr.xz(es, t_end)))
        for i, (s, t) in enumerate(pts):
            y = int(round(y_start + (y_end - y_start) * i / max(1, total - 1)))
            for dw in range(-(e["width"] // 2), e["width"] - e["width"] // 2):
                for ds_ in (-0.5, 0, 0.5):
                    x, z = map(round, fr.xz(s + ds_, t + dw))
                    if (x, z) not in plan.old or plan.path.get((x, z), -999) >= y:
                        continue
                    plan.path[(x, z)] = y
        by_col = {}
        for (px, py, pz) in plan.put:
            if (px, pz) in plan.path:
                by_col.setdefault((px, pz), []).append(py)
        for (x, z), y in plan.path.items():
            # nothing of the scarp's dressing, caps or crags stays on the path or above it
            for yy in by_col.get((x, z), []):
                if yy >= y - 1:
                    plan.put.pop((x, yy, z), None)
            plan.crag.pop((x, z), None)
            plan.caps.pop((x, z), None)
            old = plan.old[(x, z)]
            if y <= old:
                plan.top[(x, z)] = y                     # cut down to the path; the ground below it stays
            else:
                plan.top.pop((x, z), None)
                for yy in range(old + 1, y):             # built out from the face: a ledge of rock
                    plan.put[(x, yy, z)] = e["fill"]
            plan.put[(x, y, z)] = e["surface"]
            plan.carve.setdefault((x, z), []).append((y + 1, y + 4))
        gx, gz = fr.xz(es, t_start - e_side * 2)
        gy = plan.old.get((round(gx), round(gz)), 120) + 1
        plan.entities.append('summon minecraft:armor_stand %.1f %d %.1f {CustomName:\'"%s (placeholder)"\','
                             'CustomNameVisible:1b,NoGravity:1b,Invulnerable:1b,Tags:["%s","%s"]}'
                             % (gx, gy, gz, e["guard"], spec["portal_sheets"]["tag"], "rift_fx_" + st_spec["id"]))
        plan.count("entrance path columns", len(plan.path))
        views_extra["%s: the trailhead" % e["id"]] = [round(gx), gy + 2, round(gz)]

    # the deliberate waterfall: off the highest sheer lip on its side, away from the entrances
    wf = spec["waterfalls"]
    sides_ = (-1, 1) if wf["side"] == "either" else ((-1,) if wf["side"] == "west" else (1,))
    cands = [(st_, sd_) for sd_ in sides_ for st_ in sts
             if seg(sd_, st_["s"]) == "sheer" and 30 < st_["s"] < fr.L - 30
             and all(abs(st_["s"] - es) > e["gap"] + 30 for _, es, e in entrances)]
    for st_, wside in sorted(cands, key=lambda c_: -c_[0]["sides"][c_[1]]["rim_y"])[:wf["count"]]:
        sd = st_["sides"][wside]
        for dd in (0, 1):
            x, z = map(round, fr.xz(st_["s"] + dd, sd["rim_t"] + wside * 1))
            if (x, z) in plan.old:
                plan.water.append((x, plan.old[(x, z)], z))
                plan.put[(x, plan.old[(x, z)], z)] = "minecraft:water"
        views_extra["waterfall"] = [round(fr.xz(st_["s"], sd["rim_t"] - wside * 30)[0]), sd["rim_y"] - 10,
                                    round(fr.xz(st_["s"], sd["rim_t"] - wside * 30)[1])]
        plan.count("waterfalls")
    plan.views_extra = views_extra

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
                if y is None or (x, z) in plan.path or (x, z) in plan.caps:
                    continue
                # a crack, not a tiled path (owner, 2026-09-22: sea lanterns read as recognisable): the light is a bed
                # of violet one down, and the slot above it holds a standing crystal or stays open; the vein's edge
                # is crying obsidian flush with the ground
                edge = abs(dw) == width // 2 and width >= 3
                if edge or (kind == "thin" and int(s) % 3 == 0):
                    plan.put[(x, y, z)] = pal["vein_seep"]
                    continue
                plan.put[(x, y - 1, z)] = pal["vein_bed"]
                cr = rng_for(seed, "slot", x, z).random()
                plan.put[(x, y, z)] = (pal["vein_core"] + "[facing=up]") if cr < 0.6 else "minecraft:air"
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
            if y is None or (x, z) in plan.path:
                continue
            # the open end climbs out in one-block steps, so anything that drops into the pool can walk out
            from_end = len(wound) - 1 - i
            depth_here = ws["depth"] if from_end >= 6 else (from_end + 1) // 2
            if depth_here == 0:
                continue
            bottom = y - depth_here
            plan.wound_floor[(x, z)] = bottom if i >= crust_to else y
            plan.carve.setdefault((x, z), []).append((bottom + 1, y))
            plan.put[(x, bottom, z)] = pal["vein_halo"] if abs(dw) < ws["width"] // 2 else pal["vein_seep"]
            for yy in range(bottom + 1, y + 1):
                plan.put.pop((x, yy, z), None)
            if i < crust_to:
                plan.put[(x, y, z)] = pal["wound_crust"]
                plan.put[(x, y - 1, z)] = pal["vein_bed"]
        if i == crust_to + (len(wound) - crust_to - 6) // 2:
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
            if y is not None and (x, z) not in plan.caps:
                for yy in range(y, y + vr_rng.randint(*vs["up_the_face"])):
                    for dz in (0,):
                        plan.put[(x, yy, z)] = pal["vein_bed"] if yy % 2 else pal["vein_seep"]
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
            if y is None or (x, z) in plan.path or (x, z) in plan.caps or (x, y, z) in plan.put and \
                    plan.put[(x, y, z)].split("[")[0] in (pal["vein_core"], pal["vein_bed"], pal["vein_seep"]):
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
    # 1. a glimpse: a narrow jagged tear in the lip riser's solid face (a group with no undercut, the deepest lip on
    # the east side), and the portal deep inside it. Two sheets at different depths behind the tear, each wider than
    # it, so the rock hides every edge and the swirl shows only as the tear's own ragged shape, layered in depth.
    # Owner, 2026-09-22: a sheet standing in the open read as a nether portal, and one in a fissure as tacky
    gl = random.Random(seed + 11)
    cand = [st_ for st_ in sts if not group(int(round(st_["s"] / every)))[3] and 40 < st_["s"] < fr.L - 40]
    win = max(cand or sts, key=lambda st_: st_["sides"][1]["rim_y"] - st_["floor"])
    sdw = win["sides"][1]
    y0 = level(win["s"], 1, 0) or sdw["rim_y"] - 20
    rim_t = sdw["rim_t"]
    depth = 5
    tall = max(8, min(18, sdw["rim_y"] - y0 - 6))
    sc_, w = win["s"], 1
    tear = set()
    for yy in range(y0 + 2, y0 + 2 + tall):
        edge_rows = yy - (y0 + 2) < 2 or (y0 + 2 + tall) - yy <= 2
        w = 1 if edge_rows else max(1, min(3, w + gl.choice((-1, 0, 1))))
        sc_ += gl.choice((-0.5, 0, 0, 0.5))
        for k2 in range(2, 2 * depth + 1):             # half-block steps into the rock, so the diagonal has no gaps
            for j2 in range(0, 2 * w):
                x, z = map(round, fr.xz(sc_ + j2 / 2 - w / 2, rim_t + k2 / 2))
                tear.add((x, yy, z))
    for x, yy, z in tear:
        plan.put[(x, yy, z)] = "minecraft:air"
    plan.count("glimpse tear blocks", len(tear))
    # the tear's lips weep: crying obsidian on a third of the face cells round the opening
    for x, yy, z in sorted(tear):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c = (x + dx, yy, z + dz)
            if c not in tear and gl.random() < 0.08:
                plan.put.setdefault(c, pal["vein_seep"])
    for d_in, width, turn in ((depth - 0.8, 7.0, 0.0), (depth - 2.6, 5.0, math.radians(9))):
        cx, cz = fr.xz(win["s"], rim_t + d_in)
        sheet((cx, y0 + 1, cz), quat_y(phi + turn), (width, float(tall + 2), 1.0), "glimpse")
    lights([(x, yy, z) for x, yy, z in sorted(tear) if (yy - y0) % 5 == 0][:6])
    ox, oz = fr.xz(win["s"], rim_t - 14)
    views = {"glimpse (tear in the east lip)": [round(ox), y0 + 4, round(oz)]}
    views.update(plan.views_extra)
    # 2. a pool lying in the open part of the wound
    if pool_at:
        px, pz = fr.xz(*pool_at)
        py = top_of(round(px), round(pz))
        qt = quat_mul(quat_y(phi), (0.7071, 0.0, 0.0, 0.7071))
        sheet((px, py - ws["depth"] + 1.05, pz), qt, (14.0, 6.0, 1.0), "pool")
        lights([(round(fr.xz(pool_at[0] + d, pool_at[1] + e)[0]), py + 1, round(fr.xz(pool_at[0] + d, pool_at[1] + e)[1]))
                for d in (-6, 0, 6) for e in (-5, 5)])
        views["pool"] = [round(px), py + 4, round(pz)]
    # no sheet in the fissures: the owner found it tacky (2026-09-22); they keep their depth and their seep

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

    # nothing that walks may be trapped: fill every pocket the build made to its spill level
    plan.frame, plan.spec = fr, spec
    plan.count("columns raised so everything can walk out", make_walkable(plan, rimpal))

    # checks: sampled from the final plan
    rs = random.Random(seed + 9)
    for (x, z), y in plan.top.items():
        near_fall = any(abs(x - wx) < 24 and abs(z - wz) < 24 for wx, wy, wz in plan.water)
        if rs.random() < 0.02 and not near_fall and (x, z) not in plan.caps:
            plan.checks.append((x, y + 1, z, ["minecraft:air"], "cut: air above the new ground"))
    for (x, y, z), b in plan.put.items():
        base = b.split("[")[0]
        if base in (pal["vein_core"], pal["vein_bed"]) and rs.random() < 0.1:
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
    plan.entrance_spans = [(e_side, es, e["gap"]) for e_side, es, e in entrances]
    return plan


# ------------------------------------------------------------------ can everything walk out?

RING = ((1, 0), (-1, 0), (0, 1), (0, -1))


def surfaces(plan):
    """(x, z) -> the y a walker stands on after the build: the cut ground, a crack's glass cap, a crag's top, a path,
    the wound's crust or floor, one lower where a vein slot is left open."""
    surf = {k: plan.top.get(k, h) for k, h in plan.old.items()}
    for layer in (plan.caps, plan.crag, plan.path, plan.wound_floor):
        surf.update(layer)
    for (x, y, z), b in plan.put.items():
        if b == "minecraft:air" and surf.get((x, z)) == y and (x, z) not in plan.caps:
            surf[(x, z)] = y - 1
    return surf


def make_walkable(plan, material):
    """Raise, as little as possible, every column a walker could not leave, until a step of one block leads out:
    a priority flood from the stretch's edges, lowest first (depression filling with a slope of one block). A pocket
    between crags fills with crag rock; a pocket cut off on the scarp keeps the ground it had instead of being cut."""
    import heapq
    surf = surfaces(plan)
    fr, hw = plan.frame, plan.spec["stretch"]["half_width"]
    exits = [c for c in surf if (lambda st: st[0] < 3 or st[0] > fr.L - 3 or abs(st[1]) > hw - 3)(fr.st(*c))]
    heap = [(surf[c], c) for c in exits]
    heapq.heapify(heap)
    seen = set(exits)
    raised = {}
    while heap:
        h, c = heapq.heappop(heap)
        for dx, dz in RING:
            n = (c[0] + dx, c[1] + dz)
            if n not in surf or n in seen:
                continue
            seen.add(n)
            nh = surf[n]
            if nh < h - 1:
                nh = h - 1
                raised[n] = nh
            heapq.heappush(heap, (nh, n))
    for (x, z), y in raised.items():
        old = plan.old[(x, z)]
        was = surf[(x, z)]
        plan.caps.pop((x, z), None)
        plan.wound_floor.pop((x, z), None)
        if y <= old and (x, z) not in plan.crag:
            plan.top[(x, z)] = y                 # cut less: the ground it had stays
            for yy in range(was, y + 1):
                plan.put.pop((x, yy, z), None)
        else:
            plan.top.pop((x, z), None)
            for yy in range(max(old, was) + 1, y + 1):
                plan.put[(x, yy, z)] = material[(yy // 4 + x // 9 + z // 11) % len(material)]
            plan.crag[(x, z)] = y
    return len(raised)


def trap_cells(plan):
    """Every column a walker cannot leave: it can step up one block and fall any distance, and leaving means reaching
    the edge of the stretch. Returns (all traps, traps the build made or touches). Fails closed: the build refuses
    to write any trap of its own."""
    surf = surfaces(plan)
    fr, hw = plan.frame, plan.spec["stretch"]["half_width"]
    exits = [c for c in surf if (lambda st: st[0] < 3 or st[0] > fr.L - 3 or abs(st[1]) > hw - 3)(fr.st(*c))]
    reach, stack = set(exits), list(exits)
    while stack:
        c = stack.pop()
        cy = surf[c]
        for dx, dz in RING:
            n = (c[0] + dx, c[1] + dz)
            if n in surf and n not in reach and cy <= surf[n] + 1:     # from n a walker gets to c
                reach.add(n)
                stack.append(n)
    traps = [c for c in surf if c not in reach]
    changed = (set(plan.top) | set(plan.caps) | set(plan.crag) | set(plan.path) | set(plan.wound_floor)
               | {(x, z) for x, _, z in plan.put})
    ours = [c for c in traps if c in changed or any((c[0] + dx, c[1] + dz) in changed for dx, dz in RING)]
    return traps, ours


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
    # the seal: every void within `depth` behind a new surface made rock at run time, before any carving, so no
    # cave water runs into the cuts (the first prototype's audit found it did)
    seal = plan.spec["seal"]
    ring = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for (x, z) in sorted(set(plan.top) | {(x + dx, z + dz) for x, z in plan.top for dx, dz in ring}):
        own = plan.top.get((x, z), plan.old.get((x, z)))
        if own is None:
            continue
        low = min(v for v in (plan.top.get((x + dx, z + dz), plan.old.get((x + dx, z + dz)))
                              for dx, dz in ((0, 0),) + ring) if v is not None)
        if (x, z) in plan.top:
            # a cut column's own ground, voids only, up to its planned surface: a re-run after an earlier plan that
            # cut deeper here (or after a re-export) comes out the same
            add(x, z, "fill %d %d %d %d %d %d %s replace #cobblers:rift_void" % (
                x, own - seal["restore"], z, x, own, z, seal["block"]))
        elif own - 1 >= low - seal["depth"]:
            add(x, z, "fill %d %d %d %d %d %d %s replace #cobblers:rift_void" % (
                x, low - seal["depth"], z, x, own - 1, z, seal["block"]))
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
    sel = "@e[tag=%s]" % area     # every entity of this stretch, sheets and trailhead guards alike
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
    traps, ours = trap_cells(plan)
    plan.count("trap cells in untouched terrain", len(traps) - len(ours))
    if ours:
        raise FractureError("%d columns the build makes or touches cannot be walked out of (a mob stepping in stays): "
                            "e.g. %s" % (len(ours), sorted(ours)[:5]))
    bf, border = block_functions(plan)
    biof, biorder, ncells = biome_functions(plan, spec)
    fxf, sel, nfx = fx_functions(plan)
    for d in (PACK, BIOME_PACK):
        if d.exists():
            shutil.rmtree(d)
    fdir = PACK / "data" / "cobblers" / "function" / "rift_fracture"
    fdir.mkdir(parents=True)
    tdir = PACK / "data" / "cobblers" / "tags" / "block"
    tdir.mkdir(parents=True)
    (tdir / "rift_void.json").write_text(json.dumps({"values": ["minecraft:air", "minecraft:cave_air", "minecraft:water",
                                                                "minecraft:lava"]}, indent=2) + "\n", encoding="utf-8")
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
    """Entities of any type carrying area_tag (the sheets and the trailhead guards), read from the entity region files."""
    import nbt
    n = 0
    for p in sorted((Path(world) / "entities").glob("r.*.*.mca")):
        for _, _, ch in nbt.region_chunks(p):
            for e in ch.get("Entities") or []:
                if area_tag in (e.get("Tags") or []):
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
