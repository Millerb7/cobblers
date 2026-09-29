#!/usr/bin/env python
"""Offline audit of the evolution-stone faces (build/datapacks/cobblers_mines against data/mines.json).

Independent of tools/mines.py's model: it never imports it. The pack is replayed, and what it wrote is checked against
data/mines.json's own rule words (`geometry.rules`), the canonical heightmap (tools/ground.py, rounded) and other
systems' data and output. From the rules text alone, per face: the frame (anchor, front; u along the face, d into the
rock), the floor F (the lower median of the natural ground over the first apron row), the half-width and the set-back
columns (the rule's h32, typed here from its definition), the body, the apron and the envelope a face may write in.

  pack        one build function per site in the data, and for every face a check, a restore, a rock function and one
              function per variant; the load and tick tags; nothing passes on an empty pack or an empty build
  owner       every written column lies in exactly one face's envelope (u within the knoll's reach, d from one before
              the apron to the knoll's back): nothing is written where no face may write
  floor       no pit: the bottom course stands at F+1 over every body column (a bottom course under F+1 is a floor dug
              below the natural ground's median in front of the face); every apron and set-back cell at F is solid
              and F+1, F+2 are open (a lantern excepted); the apron is levelled by at most max_fill and max_cut
  bottom      the face's `bottom` block (a contrasting rock, not its host) directly under every body column; no ore of
              the face at or under it, in the build or in any variant
  body        every body cell (F+2 .. F+height+1) is host rock or the face's ore; the ground under F in a body column is
              host rock up to F (the formation does not float); every body column has a solid cell over its top row
              (cover)
  top         no solid cell built over the ground higher than T0+1 = F+height+3; no column built up more than max_build over its ground; the
              top cell of every built-up column outside the apron is the cap (the site's cap, else host rock)
  rock        faces/<id>_rock is only `fill ... <block> replace #cobblers:face_resettable` lines, and the cells it fills
              are exactly the build's formation rock of that face (body, bottom course, rock and cap: every host,
              bottom, cap or ore cell except the apron's floor and fill), each with the block the build wrote (host
              where the build left ore); the restore runs it before any variant
  variants    each faces/<id>_v<k> is only `execute if block P <host> run setblock P <ore>` lines, P a body cell above
              the bottom course, as many as the yield allows; exactly visible_min of them on the face line at F+2 or
              F+3 away from its ends and open to the air in front; the rest one or more behind the face line and under
              the body's top row; the build's ore is variant 0; the variants are not all the same
  guard       each check: the period against the face's last restore, four loaded corners spanning the face's written
              bounds, no player and no Pokemon in a volume covering those bounds grown by one, all before the restore;
              the restore runs the rock, draws `random value 0..7`, never repeats the last variant, and stamps the time
  driver      the tick runs the drive every `every_ticks`; the drive runs each site only while a player is inside an
              approach box that holds every face's written bounds with at least half the approach margin to spare;
              the load sets the period to the data's (at least 600 s)
  tag         the resettable tag holds air, cave air, every host, bottom, cap and ore the faces use, and no container
  walk        from the stand (u 0, two rows out, F+1), over the replayed writes on the ground, a walker stepping at most
              one block up or down reaches a column the build did not write
  ring        each surface face's anchor within its site's ring round the town's centre (data/towns.json)
  roads       no written column within the site's road_clear (at least 25 at a surface site) of a street or the plaza
              (the town plan's cells and the data polylines, tools/town_dressing_audit.py's plan recomputation) or of a
              routed leg (derived/routes/critical_legs.json, measured to its segments here); none within 3 of a
              data/routes.json corridor
  plan        no written column on a lot, an anchor lot, a building's footprint or a route event site, an earthwork's
              command columns, a lamp, a trader's spot, a signpost, painted water, a town dressing write or a working
              Pokemon's point; none within water_changed_reach (at least 8) of a column the pending water export
              changes (the file missing is a failure); in the cavern, none within tree_reach of a tree's trunk, on a
              light write, or within tunnel_reach of the tunnel's line
  blocks      only the blocks the rules name (host, ore, bottom, cap, floor, air; bedrock and lanterns where the site
              says); no block data/spawn_blocks.json names as a spawn condition; bedrock only at a bedrock_skin site,
              under the ground, never in front of the face and never next to a written air cell
  exchange    data/traders.json has the Exchange in the Mining Town: stock "stones", buys false, every stone the faces
              carry on sale, nothing else; no evolution stone in CobbleDollars' bank.json (so nothing buys one back)
  step        tools/reapply.py has R9O running every site's build function, and the pack in SERVER_PACKS and WORLD_LOCAL
  limits      tools/function_limits.py finds nothing the server would refuse

Validity, not behaviour: nothing here shows a face in a running world (how it looks, that the ore drops, that the
restore's filtered fill runs).

  python tools/mines_audit.py [--source-root DIR]      writes derived/mines/audit.json; exit 1 on any problem
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as GR            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "mines.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_mines"
FN = PACK / "data" / "cobblers" / "function" / "mines"
OUT = ROOT / "derived" / "mines" / "audit.json"
CMD = re.compile(r"^(fill|setblock) (-?\d+) (-?\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+))? (\S+)")
ROCK_FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+) replace (\S+)$")
GUARDED = re.compile(r"^execute if block (-?\d+) (-?\d+) (-?\d+) (\S+) run setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$")
VOLUME = re.compile(r"x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)")
AIRS = ("minecraft:air", "minecraft:cave_air")
LANTERN = "minecraft:lantern"
BEDROCK = "minecraft:bedrock"
CONTAINERS = ("chest", "barrel", "shulker", "hopper", "dispenser", "dropper", "furnace", "smoker", "crafter")
# floors under the data's own reaches: the design's minimums, so an edit of data/mines.json cannot loosen the audit
WATER_REACH_MIN = 8
TREE_REACH_MIN = 3
TUNNEL_REACH_MIN = 4
ROAD_CLEAR_MIN = 25          # the owner, 2026-09-28: every surface face 25 from any street, the plaza, a routed leg
LEG_MARGIN = 3               # tools/town_dressing.py LEG_MARGIN: the clearance from a data/routes.json corridor


def name_of(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def lines_of(name):
    p = FN / (name + ".mcfunction")
    return p.read_text(encoding="utf-8").splitlines() if p.is_file() else None


def replay(lines, into):
    for ln in lines:
        m = CMD.match(ln.strip())
        if not m:
            continue
        a = [int(v) for v in m.groups()[1:4]]
        b = [int(v) for v in m.groups()[4:7]] if m.group(5) else a
        for x in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
            for y in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                for z in range(min(a[2], b[2]), max(a[2], b[2]) + 1):
                    into[(x, y, z)] = m.group(8)


# ------------------------------------------------------------------ the rules text's own terms

def h32(*vals):
    """The rules text's h32: a 32-bit FNV-style mix of integers (tools/rift_mines.py defines the same mix)."""
    a = 0x811C9DC5
    for v in vals:
        a = ((a ^ (int(v) & 0xFFFFFFFF)) * 0x01000193) & 0xFFFFFFFF
        a ^= a >> 15
        a = (a * 0x2C1B3C6D) & 0xFFFFFFFF
        a ^= a >> 12
    return a


def face_int(s):
    """A face id as the integer the rule's h32 takes: its length and its code points by position."""
    return len(s) * 1000003 + sum(ord(c) * (i + 1) for i, c in enumerate(s))


def frame(anchor, front):
    """(xz(u, d), uv(x, z)) from the rules: north, the player stands north and the rock runs +z; south -z; west +x;
    east -x; u runs +x on a north or south face and +z on a west or east face."""
    ax, az = anchor
    if front == "north":
        return (lambda u, d: (ax + u, az + d)), (lambda x, z: (x - ax, z - az))
    if front == "south":
        return (lambda u, d: (ax + u, az - d)), (lambda x, z: (x - ax, az - z))
    if front == "west":
        return (lambda u, d: (ax + d, az + u)), (lambda x, z: (z - az, x - ax))
    if front == "east":
        return (lambda u, d: (ax - d, az + u)), (lambda x, z: (z - az, ax - x))
    return None, None


def terms(face, geo, seed, ground):
    """The face's terms from the rules text: F, hw, the set-back, the body, the apron and the envelope."""
    xz, uv = frame(face["anchor"], face["front"])
    A, Mg, BD = geo["apron_rows"], geo["apron_margin"], geo["body_depth"]
    half = geo["width_max"] // 2 + Mg
    gs = sorted(ground(*xz(u, -1)) for u in range(-half, half + 1))
    F = gs[(len(gs) - 1) // 2]
    fi = face_int(face["id"])
    width = geo["width_min"] + h32(seed, fi, 1) % (geo["width_max"] - geo["width_min"] + 1)
    hw = width // 2
    sb = {u: 1 if abs(u) < hw and h32(seed, fi, 2, u) % 3 == 0 else 0 for u in range(-hw, hw + 1)}
    body = {(u, d) for u in sb for d in range(sb[u], sb[u] + BD)}
    apron = {(u, d) for u in range(-hw - Mg, hw + Mg + 1) for d in range(-A, 0)} | {(u, 0) for u in sb if sb[u]}
    reach = hw + max(geo["knoll_side"], Mg + 1)
    env = (-reach, -A - 1, reach, BD + 1 + geo["knoll_back"])
    return {"xz": xz, "uv": uv, "F": F, "hw": hw, "sb": sb, "body": body, "apron": apron, "env": env,
            "top": F + geo["height"] + 3}


def in_env(t, x, z):
    u, d = t["uv"](x, z)
    u0, d0, u1, d1 = t["env"]
    return u0 <= u <= u1 and d0 <= d <= d1


def seg_distance(px, pz, ax, az, bx, bz):
    vx, vz = bx - ax, bz - az
    L = vx * vx + vz * vz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * vx + (pz - az) * vz) / L))
    return math.hypot(px - (ax + t * vx), pz - (az + t * vz))


def seg_distances(C, a, b):
    """Distances of the (n, 2) points C to the segment a-b."""
    a = np.asarray(a, float)
    v = np.asarray(b, float) - a
    L = float(v @ v)
    t = np.zeros(len(C)) if L == 0 else np.clip(((C - a) @ v) / L, 0.0, 1.0)
    return np.hypot(*(C - (a + t[:, None] * v)).T)


def polylines_near(lines, cols, reach):
    """{(x, z): distance} of the written columns within `reach` of any segment of the polylines."""
    if not cols or not lines:
        return {}
    C = np.array(sorted(cols), float)
    lo, hi = C.min(0) - reach - 1, C.max(0) + reach + 1
    best = np.full(len(C), np.inf)
    for pts in lines:
        for a, b in zip(pts, pts[1:]):
            if max(a[0], b[0]) < lo[0] or min(a[0], b[0]) > hi[0] or max(a[1], b[1]) < lo[1] or min(a[1], b[1]) > hi[1]:
                continue
            best = np.minimum(best, seg_distances(C, a, b))
    return {(int(C[i][0]), int(C[i][1])): float(best[i]) for i in np.nonzero(best <= reach)[0]}


def cells_near(cells, cols, reach):
    """{(x, z): distance} of the written columns within `reach` (Euclidean) of any of the cells."""
    if not cols or not cells:
        return {}
    C = np.array(sorted(cols), float)
    lo, hi = C.min(0) - reach - 1, C.max(0) + reach + 1
    R = np.array([c for c in cells if lo[0] <= c[0] <= hi[0] and lo[1] <= c[1] <= hi[1]], float)
    if not len(R):
        return {}
    out = {}
    for i in range(0, len(C), 256):
        blk = C[i:i + 256]
        d = np.sqrt(((blk[:, None, :] - R[None, :, :]) ** 2).sum(-1).min(1))
        for j in np.nonzero(d <= reach)[0]:
            out[(int(blk[j][0]), int(blk[j][1]))] = float(d[j])
    return out


def route_legs():
    """([critical leg polylines], [data corridor polylines], critical legs file present)."""
    crit, corr = [], []
    p = ROOT / "derived" / "routes" / "critical_legs.json"
    if p.is_file():
        crit = [[tuple(q) for q in leg.get("polyline") or []] for leg in json.loads(p.read_text(encoding="utf-8"))["legs"]]
    rp = ROOT / "data" / "routes.json"
    if rp.is_file():
        for r in json.loads(rp.read_text(encoding="utf-8")).get("routes") or []:
            corr.append([(q["x"], q["z"]) for q in (r.get("corridor") or {}).get("polyline") or []])
    return [l for l in crit if len(l) > 1], [l for l in corr if len(l) > 1], p.is_file()


# ------------------------------------------------------------------ the audit

def audit(source_root=None):
    probs, notes = [], {}
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    sites = spec.get("sites") or []
    if not sites or not any(s.get("faces") for s in sites):
        return ["data/mines.json has no site with a face: nothing to audit is not a clean audit"], notes
    if not FN.is_dir():
        return ["no pack %s: run `python tools/mines.py build` first" % FN.relative_to(ROOT)], notes
    rs = spec["restore"]
    geo = spec["geometry"]
    keep = spec.get("keep_clear") or {}
    seed = spec["seed"]
    H = geo["height"]
    tagname = "#cobblers:%s" % rs["resettable_tag"]
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])

    # ---- tag
    tagp = PACK / "data" / "cobblers" / "tags" / "block" / ("%s.json" % rs["resettable_tag"])
    tag = set(json.loads(tagp.read_text(encoding="utf-8"))["values"]) if tagp.is_file() else set()
    if not tag:
        probs.append("tag: no %s" % tagp.relative_to(ROOT))
    for need in AIRS:
        if need not in tag:
            probs.append("tag: lacks %s" % need)
    for v in tag:
        if any(c in v for c in CONTAINERS):
            probs.append("tag: %s is a container; a restore would delete it and its contents" % v)
    for tagfile, want in (("load.json", "cobblers:mines/load"), ("tick.json", "cobblers:mines/tick")):
        p = PACK / "data" / "minecraft" / "tags" / "function" / tagfile
        if not p.is_file() or want not in json.loads(p.read_text(encoding="utf-8")).get("values", []):
            probs.append("tags: %s does not run %s" % (tagfile, want))

    # ---- driver
    tick = lines_of("tick") or []
    every = rs["every_ticks"]
    if not any(re.fullmatch(r"execute if score #clock mn\.t matches %d\.\. run function cobblers:mines/drive" % every, l) for l in tick):
        probs.append("driver: the tick does not run the drive every %d ticks" % every)
    load = lines_of("load") or []
    per = [int(m.group(1)) for l in load for m in [re.fullmatch(r"scoreboard players set #period mn\.t (\d+)", l)] if m]
    if per != [rs["period_ticks"]] or rs["period_ticks"] < 12000:
        probs.append("driver: the load sets the period %s; the data says %d and the design at least 12000 (600 s)" % (per, rs["period_ticks"]))
    drive = lines_of("drive") or []
    approach = {}
    for l in drive:
        m = re.fullmatch(r"execute if entity @a\[x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)\] run function cobblers:mines/site_(\w+)", l)
        if m:
            x, y, z, dx, dy, dz = (int(v) for v in m.groups()[:6])
            approach[m.group(7)] = (x, y, z, x + dx, y + dy, z + dz)

    # ---- ground
    g = GR.Ground(source_root)
    cav = None
    cplan = ROOT / "derived" / "cavern" / "plan.json"
    if any(s.get("ground") == "cavern_floor" for s in sites):
        if not cplan.is_file():
            return probs + ["no derived/cavern/plan.json: the cavern floor is the ground of the Displaced City's faces"], notes
        cj = json.loads(cplan.read_text(encoding="utf-8"))
        cav = (tuple(cj["cavern"]), np.load(ROOT / "derived" / "cavern" / "plan.npz")["floor"].astype(int), cj)

    def ground_of(site):
        if site.get("ground") != "cavern_floor":
            return g
        (cx0, cz0, cx1, cz1), floor, _cj = cav

        def gc(x, z):
            if cx0 <= x <= cx1 and cz0 <= z <= cz1:
                return int(floor[z - cz0, x - cx0])
            return g(x, z)
        return gc

    # ---- other systems' data
    import town_dressing_audit as TDA
    import town_character as TC
    import elder_trees
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    towns = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8")).get("towns") or []}
    templates = TC.Templates(TC.default_pack_dir(), TC.default_vanilla_jar())
    wet = elder_trees.painted_water(g.heights, g.world)
    wpath = ROOT / "derived" / "water_shape" / "changed.npy"
    changed = np.load(wpath, mmap_mode="r") if wpath.is_file() else None
    if changed is None:
        probs.append("plan: no derived/water_shape/changed.npy; the water export rule cannot be checked, which is a failure")
    traders = json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))
    signs = ROOT / "derived" / "signposts.json"
    posts = [(p["x"], p["z"]) for p in json.loads(signs.read_text(encoding="utf-8"))["posts"]] if signs.is_file() else None
    if posts is None:
        probs.append("plan: no derived/signposts.json (tools/signposts.py function)")
    dress_cols = set()
    dfn = ROOT / "build" / "datapacks" / "cobblers_town_dressing" / "data" / "cobblers" / "function" / "town_dressing"
    dressed = json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8"))["towns"]
    for s in dressed:
        f = dfn / ("%s.mcfunction" % s)
        if f.is_file():
            w = {}
            replay([l for l in f.read_text(encoding="utf-8").splitlines() if not l.startswith("forceload")], w)
            dress_cols |= {(x, z) for x, _y, z in w}
        elif any(site["settlement"] == s for site in sites):
            probs.append("plan: %s is dressed but %s is not built, so the faces cannot be checked against it" % (s, f.name))
    amb_pts = set()
    ap = ROOT / "derived" / "ambient" / "plan.json"
    if ap.is_file():
        for w in json.loads(ap.read_text(encoding="utf-8"))["workers"]:
            for p in w.get("points") or []:
                amb_pts.add((int(np.floor(p[0])), int(np.floor(p[2]))))
    else:
        probs.append("plan: no derived/ambient/plan.json (tools/ambient.py build)")

    crit, corridors, have_critical = route_legs()
    if not have_critical:
        probs.append("legs: no derived/routes/critical_legs.json: the routed legs cannot be checked (fail closed)")
    water_reach = max(WATER_REACH_MIN, int(keep.get("water_changed_reach", 0)))
    tree_reach = max(TREE_REACH_MIN, int(keep.get("tree_reach", 0)))
    tunnel_reach = max(TUNNEL_REACH_MIN, int(keep.get("tunnel_reach", 0)))

    total_writes, total_faces = 0, 0
    for site in sites:
        sid = site["id"]
        s = site["settlement"]
        ground = ground_of(site)
        faces = site.get("faces") or []
        if not faces:
            probs.append("%s: no face" % sid)
        body_lines = lines_of("build_%s" % sid)
        if body_lines is None:
            probs.append("%s: no build function build_%s" % (sid, sid))
            continue
        world = {}
        replay([l for l in body_lines if not l.startswith("forceload")], world)
        if not world:
            probs.append("%s: the build function writes nothing" % sid)
            continue
        total_writes += len(world)
        cols = {(x, z) for x, _y, z in world}

        # the rules' terms of every face, and which face each written column belongs to
        T = []
        for face in faces:
            if not face.get("anchor") or face.get("front") not in ("north", "south", "west", "east"):
                probs.append("%s: no anchor or no front in the data" % face["id"])
                T.append(None)
                continue
            T.append(terms(face, geo, seed, ground))
        owner = {}
        for c in cols:
            hit = [i for i, t in enumerate(T) if t and in_env(t, *c)]
            if len(hit) > 1:
                hit.sort(key=lambda i: math.hypot(c[0] - faces[i]["anchor"][0], c[1] - faces[i]["anchor"][1]))
            if hit:
                owner[c] = hit[0]
        stray = sorted(cols - set(owner))
        if stray:
            probs.append("%s: owner: %d written column(s) in no face's envelope, e.g. %s" % (sid, len(stray), stray[0]))

        def is_air(c):
            b = world.get(c)
            if b is not None:
                return name_of(b) in AIRS
            return c[1] > ground(c[0], c[2])

        # ring: the anchor round the town's centre
        if site.get("ground") != "cavern_floor":
            ring = site.get("ring")
            t = towns.get(s)
            if not ring:
                probs.append("%s: ring: a surface site with no ring round its town's centre" % sid)
            elif not t or not t.get("centre"):
                probs.append("%s: ring: data/towns.json has no centre for %s" % (sid, s))
            else:
                for face in faces:
                    if not face.get("anchor"):
                        continue
                    r = math.hypot(face["anchor"][0] - t["centre"]["x"], face["anchor"][1] - t["centre"]["z"])
                    if not ring[0] <= r <= ring[1]:
                        probs.append("%s: ring: the anchor %s is %.1f from %s's centre, outside the ring %s"
                                     % (face["id"], face["anchor"], r, s, ring))

        # roads: streets, the plaza and the routed legs
        rc = site.get("road_clear", keep.get("road_clear", 0))
        if site.get("ground") != "cavern_floor" and rc < ROAD_CLEAR_MIN:
            probs.append("%s: roads: road_clear %s at a surface site; the owner's rule is %d" % (sid, rc, ROAD_CLEAR_MIN))
        planp = ROOT / "derived" / "towns" / ("%s_plan.json" % s)
        if not planp.is_file():
            probs.append("%s: no town plan %s" % (sid, planp.relative_to(ROOT)))
        else:
            plan = json.loads(planp.read_text(encoding="utf-8"))
            pdata = (doc.get("settlements", {}).get(s) or {}).get("plan") or {}
            rects, unknown = TDA.footprints(s, doc, templates)
            if unknown:
                probs.append("%s: buildings with templates this audit cannot read: %s" % (sid, unknown))
            why = TDA.forbidden(plan, pdata, rects, TDA.event_sites())
            roads = {c: w for c, w in TDA.forbidden(plan, pdata, {}, ()).items() if w.startswith("street") or w == "plaza"}
            for kind in ("street", "plaza"):
                near = cells_near({c for c, w in roads.items() if w.startswith(kind)}, cols, rc)
                if near:
                    c = min(near, key=near.get)
                    probs.append("%s: roads: %d written column(s) within %d of a %s, e.g. %s at %.1f"
                                 % (sid, len(near), rc, kind, c, near[c]))
            for q in doc["placements"]:
                if q.get("settlement") == s and q.get("kind") == "earthwork":
                    ew = {}
                    replay(q.get("commands") or [], ew)
                    for x, _y, z in ew:
                        why.setdefault((x, z), "earthwork %s" % q["id"])
            for lamp in plan.get("lamps") or []:
                why.setdefault((lamp["at"][0], lamp["at"][2]), "lamp")
            hit = {}
            for c in cols:
                if c in why:
                    hit.setdefault(why[c], []).append(c)
            for w, cs in sorted(hit.items()):
                probs.append("%s: plan: %d written column(s) on %s, e.g. %s" % (sid, len(cs), w, sorted(cs)[0]))
        near = polylines_near(crit, cols, rc)
        if near:
            c = min(near, key=near.get)
            probs.append("%s: roads: %d written column(s) within %d of a routed leg, e.g. %s at %.1f"
                         % (sid, len(near), rc, c, near[c]))
        near = polylines_near(corridors, cols, LEG_MARGIN)
        if near:
            probs.append("%s: roads: %d written column(s) within %d of a data/routes.json corridor, e.g. %s"
                         % (sid, len(near), LEG_MARGIN, min(near, key=near.get)))
        for t_ in traders.get("traders") or []:
            p = t_.get("position") or {}
            if any(abs(x - p.get("x", 10 ** 9)) <= 1 and abs(z - p.get("z", 10 ** 9)) <= 1 for x, z in cols):
                probs.append("%s: plan: a write within 1 of trader %s" % (sid, t_["id"]))
        for px, pz in posts or []:
            if any(abs(x - px) <= 1 and abs(z - pz) <= 1 for x, z in cols):
                probs.append("%s: plan: a write within 1 of the signpost at %d,%d" % (sid, px, pz))
        on_dress = cols & dress_cols
        if on_dress:
            probs.append("%s: plan: %d written column(s) under a town dressing write, e.g. %s" % (sid, len(on_dress), sorted(on_dress)[0]))
        near_amb = {c for c in cols if any((c[0] + dx, c[1] + dz) in amb_pts for dx in (-1, 0, 1) for dz in (-1, 0, 1))}
        if near_amb:
            probs.append("%s: plan: %d written column(s) within 1 of a working Pokemon's point" % (sid, len(near_amb)))
        if site.get("ground") != "cavern_floor":
            wetc = [c for c in cols if 0 <= c[1] - g.oz < wet.shape[0] and 0 <= c[0] - g.ox < wet.shape[1]
                    and wet[c[1] - g.oz, c[0] - g.ox]]
            if wetc:
                probs.append("%s: plan: %d written column(s) on painted water, e.g. %s" % (sid, len(wetc), sorted(wetc)[0]))
            if changed is not None:
                n = water_reach
                bad = []
                for x, z in cols:
                    sub = changed[max(0, z - n):z + n + 1, max(0, x - n):x + n + 1]
                    if np.asarray(sub).any():
                        bad.append((x, z))
                if bad:
                    probs.append("%s: plan: %d written column(s) within %d of a column the water export changes, e.g. %s"
                                 % (sid, len(bad), n, sorted(bad)[0]))
        else:
            (_b, _f, cj) = cav
            for tr in cj.get("tree_positions") or []:
                tx, _ty, tz = tr["at"]
                if any(abs(x - tx) <= tree_reach and abs(z - tz) <= tree_reach for x, z in cols):
                    probs.append("%s: plan: a write within %d of the cavern tree at %d,%d" % (sid, tree_reach, tx, tz))
            lf = ROOT / "build" / "datapacks" / "cobblers_cavern" / "data" / "cobblers" / "function" / "cavern" / "40_light.mcfunction"
            if not lf.is_file():
                probs.append("%s: plan: no cavern light function to check against" % sid)
            else:
                lw = {}
                replay([l for l in lf.read_text(encoding="utf-8").splitlines() if not l.startswith("forceload")], lw)
                on = cols & {(x, z) for x, _y, z in lw}
                if on:
                    probs.append("%s: plan: %d written column(s) on a cavern light write, e.g. %s" % (sid, len(on), sorted(on)[0]))
            near = polylines_near([[tuple(p) for p in cj["tunnel"]["waypoints"]]], cols, tunnel_reach)
            if near:
                probs.append("%s: plan: %d written column(s) within %d of the cavern tunnel's line, e.g. %s"
                             % (sid, len(near), tunnel_reach, min(near, key=near.get)))

        # blocks: the whole site
        for c, b in world.items():
            if name_of(b) in spawn:
                probs.append("%s: blocks: %s at %s is a spawn condition" % (sid, b, c))
                break
        bed = [c for c, b in world.items() if name_of(b) == BEDROCK]
        if bed and not site.get("bedrock_skin"):
            probs.append("%s: blocks: %d bedrock cells at a site whose data gives it no bedrock skin" % (sid, len(bed)))
        for c in bed:
            if any(name_of(world.get((c[0] + dx, c[1] + dy, c[2] + dz), "x")) in AIRS
                   for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))):
                probs.append("%s: blocks: bedrock at %s shows in the cut" % (sid, c))
                break
        for c in bed:
            if c[1] >= ground(c[0], c[2]):
                probs.append("%s: blocks: bedrock at %s is not under the ground (y%d)" % (sid, c, ground(c[0], c[2])))
                break

        # ---- faces
        if sid not in approach:
            probs.append("%s: the drive never runs this site" % sid)
        for i, face in enumerate(faces):
            total_faces += 1
            t = T[i]
            if t is None:
                continue
            fid = face["id"]
            host, ore, yld = face["host"], face["ore"], face["yield"]
            bottom = face.get("bottom")
            cap = face.get("cap") or site.get("cap") or host
            floor_block = face.get("floor") or site.get("floor_block")
            xz, uv, F, hw, sb = t["xz"], t["uv"], t["F"], t["hw"], t["sb"]
            if ore not in spec["stones"][face["stone"]]["ores"]:
                probs.append("%s: %s is not a %s stone ore" % (fid, ore, face["stone"]))
            if not bottom:
                probs.append("%s: bottom: the data names no bottom block" % fid)
                bottom = "<none>"
            elif bottom in (host, floor_block, ore):
                probs.append("%s: bottom: the bottom block %s does not contrast with the host, floor or ore" % (fid, bottom))
            for what, b in (("host", host), ("ore", ore), ("bottom", bottom), ("cap", cap)):
                if b not in tag:
                    probs.append("%s: tag: its %s %s is not in the resettable tag, so the restore cannot put it back" % (fid, what, b))
            mine = {c: b for c, b in world.items() if owner.get((c[0], c[2])) == i}
            if not mine:
                probs.append("%s: the build writes nothing for this face" % fid)
                continue
            bcols = sorted({xz(u, d) for (u, d) in t["body"]})
            bcolset = set(bcols)
            acols = {xz(u, d) for (u, d) in t["apron"]}

            # floor: no pit
            miss = [c for c in bcols if name_of(world.get((c[0], F + 1, c[1]), "x")) != bottom]
            if miss:
                ys = sorted({y for (x, y, z), b in mine.items() if name_of(b) == bottom and (x, z) in bcolset})
                if ys and max(ys) < F + 1:
                    probs.append("%s: floor: a pit: the bottom course is at y%d, so the floor is y%d, under y%d, the natural "
                                 "ground's median over the first apron row" % (fid, max(ys), max(ys) - 1, F))
                elif not ys:
                    probs.append("%s: bottom: no bottom course: no %s under the body at y%d (F+1)" % (fid, bottom, F + 1))
                else:
                    probs.append("%s: bottom: %d body column(s) with no %s at y%d (F+1), e.g. %s"
                                 % (fid, len(miss), bottom, F + 1, miss[0]))
            dug, shut = [], []
            for (x, z) in sorted(acols):
                if is_air((x, F, z)):
                    dug.append((x, F, z))
                for y in (F + 1, F + 2):
                    b = world.get((x, y, z))
                    if not is_air((x, y, z)) and not (b and name_of(b) == LANTERN):
                        shut.append((x, y, z))
                gy = ground(x, z)
                if F - gy > geo["max_fill"]:
                    probs.append("%s: floor: the apron at %s is built up %d over its ground, over max_fill %d"
                                 % (fid, (x, z), F - gy, geo["max_fill"]))
                if gy - F > geo["max_cut"] and not site.get("bedrock_skin"):
                    probs.append("%s: floor: the apron at %s is dug %d under its ground, over max_cut %d"
                                 % (fid, (x, z), gy - F, geo["max_cut"]))
            if dug:
                probs.append("%s: floor: a pit: %d apron cell(s) at the floor y%d are open, e.g. %s (dug below the natural "
                             "ground's median in front of the face)" % (fid, len(dug), F, dug[0]))
            if shut:
                probs.append("%s: floor: %d apron cell(s) over the floor are not open, e.g. %s" % (fid, len(shut), shut[0]))

            # body, its foot, its cover
            other = [(x, y, z) for (x, z) in bcols for y in range(F + 2, F + H + 2)
                     if name_of(world.get((x, y, z), "x")) not in (host, ore)]
            if other:
                c = other[0]
                probs.append("%s: body: %d body cell(s) not its host or ore, e.g. %s = %s" % (fid, len(other), c, world.get(c)))
            floating = [(x, y, z) for (x, z) in bcols for y in range(ground(x, z) + 1, F + 1)
                        if name_of(world.get((x, y, z), "x")) != host]
            if floating:
                probs.append("%s: body: %d cell(s) between the ground and the floor under the body not host rock (the "
                             "formation floats), e.g. %s" % (fid, len(floating), floating[0]))
            bare = [(x, z) for (x, z) in bcols if is_air((x, F + H + 2, z))]
            if bare:
                probs.append("%s: cover: %d body column(s) with no cover over the top row, e.g. %s" % (fid, len(bare), bare[0]))

            # ore at or under the bottom course, ore off the body
            low = sorted(c for c, b in mine.items() if name_of(b) == ore and c[1] <= F + 1)
            if low:
                probs.append("%s: bottom: ore at or below the bottom course (y%d) at %s" % (fid, F + 1, low[0]))
            bodycells = {(x, y, z) for (x, z) in bcols for y in range(F + 2, F + H + 2)}
            built_ore = {c for c, b in mine.items() if name_of(b) == ore}
            off = sorted(built_ore - bodycells)
            if off:
                probs.append("%s: variants: the build sets ore off the body at %s" % (fid, off[0]))

            # the top, the build-up, the cap
            bycol = {}
            for (x, y, z), b in mine.items():
                bycol.setdefault((x, z), []).append((y, b))
            high = sorted(c for c, b in mine.items() if c[1] > t["top"] and c[1] > ground(c[0], c[2])
                          and name_of(b) not in AIRS)
            if high:
                probs.append("%s: top: %d solid cell(s) over the formation's top y%d, e.g. %s" % (fid, len(high), t["top"], high[0]))
            for (x, z), ys in sorted(bycol.items()):
                gy = ground(x, z)
                up = [(y, b) for y, b in ys if y > gy and name_of(b) not in AIRS and name_of(b) != LANTERN]
                if not up:
                    continue
                ytop, btop = max(up)
                if ytop - gy > geo["max_build"]:
                    probs.append("%s: top: column %s built up %d over its ground, over max_build %d"
                                 % (fid, (x, z), ytop - gy, geo["max_build"]))
                if (x, z) not in acols and name_of(btop) != cap:
                    probs.append("%s: top: the top of built-up column %s is %s, not the cap %s" % (fid, (x, z), btop, cap))

            # blocks the rules name, and the bedrock's side
            allowed = {host, ore, bottom, cap, floor_block, *AIRS}
            if site.get("bedrock_skin"):
                allowed.add(BEDROCK)
            if site.get("lanterns"):
                allowed.add(LANTERN)
            foreign = sorted(c for c, b in mine.items() if name_of(b) not in allowed)
            if foreign:
                probs.append("%s: blocks: %d cell(s) of a block the rules do not name, e.g. %s = %s"
                             % (fid, len(foreign), foreign[0], mine[foreign[0]]))
            front_bed = sorted(c for c, b in mine.items() if name_of(b) == BEDROCK and uv(c[0], c[2])[1] < 0)
            if front_bed:
                probs.append("%s: blocks: bedrock in front of the face at %s" % (fid, front_bed[0]))

            # rock: the formation, restored exactly
            want = {}
            for c, b in mine.items():
                n = name_of(b)
                if n not in (host, ore, bottom, cap):
                    continue
                x, y, z = c
                if (x, z) in acols and y <= F and not (y == F == ground(x, z)):
                    continue                        # the apron's floor and fill: levelling, not formation
                want[c] = host if n == ore else n
            rock_lines = lines_of("faces/%s_rock" % fid)
            rock = {}
            if rock_lines is None:
                probs.append("%s: rock: no faces/%s_rock" % (fid, fid))
            else:
                for l in rock_lines:
                    if not l.strip() or l.startswith("#"):
                        continue
                    m = ROCK_FILL.match(l)
                    if not m or m.group(8) != tagname:
                        probs.append("%s: rock: not a fill filtered by %s: %s" % (fid, tagname, l))
                        continue
                    a = [int(v) for v in m.group(1, 2, 3)]
                    bb = [int(v) for v in m.group(4, 5, 6)]
                    for x in range(min(a[0], bb[0]), max(a[0], bb[0]) + 1):
                        for y in range(min(a[1], bb[1]), max(a[1], bb[1]) + 1):
                            for z in range(min(a[2], bb[2]), max(a[2], bb[2]) + 1):
                                rock[(x, y, z)] = name_of(m.group(7))
                lost = sorted(set(want) - set(rock))
                if lost:
                    probs.append("%s: rock: %d formation cell(s) the restore never puts back, e.g. %s = %s"
                                 % (fid, len(lost), lost[0], want[lost[0]]))
                extra = sorted(set(rock) - set(want))
                if extra:
                    probs.append("%s: rock: the restore fills %d cell(s) that are not the formation's rock, e.g. %s = %s (build: %s)"
                                 % (fid, len(extra), extra[0], rock[extra[0]], world.get(extra[0])))
                wrong = sorted(c for c in set(rock) & set(want) if rock[c] != want[c])
                if wrong:
                    probs.append("%s: rock: %d cell(s) restored as another block than the build's, e.g. %s = %s, built %s"
                                 % (fid, len(wrong), wrong[0], rock[wrong[0]], want[wrong[0]]))

            # variants
            nvar = rs["variants"]
            seen = set()
            v0 = None
            for k in range(nvar):
                v = lines_of("faces/%s_v%d" % (fid, k))
                if v is None:
                    probs.append("%s: variants: no variant %d" % (fid, k))
                    continue
                ores = []
                for l in v:
                    if not l.strip() or l.startswith("#"):
                        continue
                    m = GUARDED.match(l)
                    if (not m or m.group(1, 2, 3) != m.group(5, 6, 7) or name_of(m.group(4)) != host
                            or m.group(8) != ore):
                        probs.append("%s v%d: variants: not an ore setblock guarded by its host: %s" % (fid, k, l))
                        continue
                    ores.append(tuple(int(q) for q in m.group(1, 2, 3)))
                ores = sorted(set(ores))
                if k == 0:
                    v0 = set(ores)
                seen.add(tuple(ores))
                if not (yld["ore_min"] <= len(ores) <= yld["ore_max"]):
                    probs.append("%s v%d: variants: %d ore, the yield is %d-%d" % (fid, k, len(ores), yld["ore_min"], yld["ore_max"]))
                for c in ores:
                    if c[1] <= F + 1:
                        probs.append("%s v%d: bottom: ore at or below the bottom course (y%d) at %s" % (fid, k, F + 1, c))
                    elif c not in bodycells:
                        probs.append("%s v%d: variants: ore off the body at %s" % (fid, k, c))
                line, rest = [], []
                for c in ores:
                    if c not in bodycells:
                        continue
                    u, d = uv(c[0], c[2])
                    (line if d == sb.get(u) else rest).append((c, u, d))
                shown = [c for c, u, d in line if c[1] in (F + 2, F + 3) and abs(u) <= hw - 1
                         and is_air((xz(u, d - 1)[0], c[1], xz(u, d - 1)[1]))]
                vm = yld.get("visible_min", 1)
                if len(shown) < vm:
                    probs.append("%s v%d: variants: %d ore showing on the face line at eye height (F+2, F+3) open to the "
                                 "air, the data asks %d" % (fid, k, len(shown), vm))
                if len(line) > vm:
                    probs.append("%s v%d: variants: %d ore on the face line, the rule puts visible_min %d there and the "
                                 "rest behind it" % (fid, k, len(line), vm))
                for c, u, d in rest:
                    if d - sb.get(u, 0) < 1 or c[1] >= F + H + 1:
                        probs.append("%s v%d: variants: a hidden ore at %s is not one or more behind the face line and "
                                     "under the body's top row" % (fid, k, c))
            if v0 is not None and v0 != built_ore:
                probs.append("%s: variants: the build's ore %s is not variant 0 %s" % (fid, sorted(built_ore)[:3], sorted(v0)[:3]))
            if len(seen) < nvar - 1:
                probs.append("%s: variants: only %d different layouts in %d variants" % (fid, len(seen), nvar))

            # the written bounds, the guard, the approach
            allc = list(mine) + list(rock)
            xs, ys_, zs = [c[0] for c in allc], [c[1] for c in allc], [c[2] for c in allc]
            bnd = (min(xs), min(ys_), min(zs), max(xs), max(ys_), max(zs))
            chk = [l for l in (lines_of("faces/check_%s" % fid) or []) if l and not l.startswith("#")]
            call = "function cobblers:mines/faces/restore_%s" % fid
            if call not in chk:
                probs.append("%s: guard: its check never calls the restore" % fid)
            else:
                pre = chk[:chk.index(call)]
                if "execute if score #d mn.t < #period mn.t run return 0" not in pre:
                    probs.append("%s: guard: the check lacks, before the restore: execute if score #d mn.t < #period mn.t" % fid)
                if "scoreboard players operation #d mn.t -= #%s mn.last" % fid not in pre:
                    probs.append("%s: guard: the check does not measure from this face's last restore" % fid)
                vols = {}
                for who, pat in (("player", r"^execute if entity @a\[(.*)\] run return 0$"),
                                 ("Pokemon", r"^execute if entity @e\[type=cobblemon:pokemon,(.*)\] run return 0$")):
                    ms = [re.match(pat, l) for l in pre]
                    ms = [VOLUME.fullmatch(m.group(1)) for m in ms if m]
                    if not ms or not ms[0]:
                        probs.append("%s: guard: the check lacks, before the restore, a %s guard over the formation "
                                     "(execute if entity %s[...] run return 0)" % (fid, who, "@a" if who == "player" else "@e[type=cobblemon:pokemon"))
                        continue
                    x, y, z, dx, dy, dz = (int(q) for q in ms[0].groups())
                    vols[who] = (x, y, z, x + dx, y + dy, z + dz)
                for who, vol in vols.items():
                    if not (vol[0] <= bnd[0] - 1 and vol[1] <= bnd[1] - 1 and vol[2] <= bnd[2] - 1
                            and vol[3] >= bnd[3] + 1 and vol[4] >= bnd[4] + 1 and vol[5] >= bnd[5] + 1):
                        probs.append("%s: guard: the %s guard %s does not cover the written bounds %s grown by one"
                                     % (fid, who, vol, bnd))
                corners = set()
                for l in pre:
                    m = re.fullmatch(r"execute unless loaded (-?\d+) (-?\d+) (-?\d+) run return 0", l)
                    if m:
                        corners.add((int(m.group(1)), int(m.group(3))))
                cx = {c[0] for c in corners}
                cz = {c[1] for c in corners}
                if (len(corners) < 4 or not cx or min(cx) > bnd[0] or max(cx) < bnd[3] or min(cz) > bnd[2]
                        or max(cz) < bnd[5] or corners != {(a, b) for a in (min(cx), max(cx)) for b in (min(cz), max(cz))}):
                    probs.append("%s: guard: the check's execute unless loaded corners %s do not span the written bounds %s"
                                 % (fid, sorted(corners), bnd))
            a = approach.get(sid)
            half = rs["approach_margin"] // 2
            if a and not (a[0] <= bnd[0] - half and a[2] <= bnd[2] - half and a[3] >= bnd[3] + half and a[5] >= bnd[5] + half
                          and a[1] <= bnd[1] and a[4] >= bnd[4]):
                probs.append("%s: the approach box %s does not hold the written bounds %s with %d to spare" % (fid, a, bnd, half))

            # the restore
            rst = lines_of("faces/restore_%s" % fid) or []
            rcall = "function cobblers:mines/faces/%s_rock" % fid
            vcalls = [n for n, l in enumerate(rst) if re.fullmatch(r"execute if score #v mn\.t matches \d+ run function "
                                                                    r"cobblers:mines/faces/%s_v\d+" % re.escape(fid), l)]
            if rcall not in rst or (vcalls and rst.index(rcall) > min(vcalls)):
                probs.append("%s: rock: the restore does not put the formation back before the ore" % fid)
            if "execute store result score #v mn.t run random value 0..%d" % (nvar - 1) not in rst:
                probs.append("%s: the restore draws no random variant" % fid)
            if "execute if score #v mn.t = #%s mn.var run scoreboard players add #v mn.t 1" % fid not in rst:
                probs.append("%s: the restore may repeat the last variant" % fid)
            if "scoreboard players operation #%s mn.last = #now mn.t" % fid not in rst:
                probs.append("%s: the restore does not stamp its time" % fid)
            for k in range(nvar):
                if "execute if score #v mn.t matches %d run function cobblers:mines/faces/%s_v%d" % (k, fid, k) not in rst:
                    probs.append("%s: the restore never runs variant %d" % (fid, k))
            if "function cobblers:mines/faces/check_%s" % fid not in (lines_of("site_%s" % sid) or []):
                probs.append("%s: its site never checks it" % fid)

            # walk: from the stand out onto unwritten ground
            sx, sz = xz(0, -2)
            start = (sx, F + 1, sz)
            if not walk_out(start, world, cols, ground):
                probs.append("%s: walk: no walk from the stand %s out onto unwritten ground stepping at most one block"
                             % (fid, start))
    notes["sites"] = len(sites)
    notes["faces"] = total_faces
    notes["cells written by the build functions"] = total_writes
    if total_writes == 0 or total_faces == 0:
        probs.append("nothing written: an empty build passes nothing")

    # ---- the Exchange
    pol = (traders.get("stock_policy") or {}).get("stones") or {}
    ex = [t for t in traders.get("traders") or [] if t.get("stock") == "stones"]
    if len(ex) != 1 or ex[0].get("settlement") != "mining_town":
        probs.append("exchange: %d stones clerk(s); the design has one, in the Mining Town" % len(ex))
    if pol.get("buys") is not False:
        probs.append("exchange: stock_policy.stones does not say buys: false")
    want = {spec["stones"][f["stone"]]["item"] for s in sites for f in s["faces"]}
    have = set(pol.get("items") or [])
    if have != want:
        probs.append("exchange: sells %s; the faces carry %s" % (sorted(have), sorted(want)))
    for bank in (ROOT / "base-pack" / "cobbleverse" / "config" / "cobbledollars" / "bank.json",
                 ROOT / "modpack" / "config" / "cobbledollars" / "bank.json"):
        if bank.is_file():
            items = {e.get("item") for e in json.loads(bank.read_text(encoding="utf-8")).get("bank") or []}
            if items & want:
                probs.append("exchange: %s buys %s back" % (bank.relative_to(ROOT), sorted(items & want)))
    notes["stones on sale at the Exchange"] = len(have)

    # ---- the step
    import reapply
    try:
        step = [s for s in reapply.steps() if s[0] == "R9O"]
    except SystemExit as e:
        step = []
        probs.append("step: tools/reapply.py steps() could not list its steps: %s" % e)
    if not step:
        probs.append("step: tools/reapply.py has no R9O")
    else:
        run = [v for k, v in step[0][2] if k == "fn"]
        need = ["cobblers:mines/build_%s" % s["id"] for s in sites]
        if run != need:
            probs.append("step: R9O runs %s, the data's sites need %s" % (run, need))
    if "cobblers_mines" not in reapply.SERVER_PACKS or "cobblers_mines" not in reapply.WORLD_LOCAL:
        probs.append("step: cobblers_mines is not a world-local server pack")

    # ---- limits
    for f in sorted(FN.rglob("*.mcfunction")):
        for n, c, w in FL.check_file(f):
            probs.append("limits: %s line %d: %s" % (f.name, n, w))
    return probs, notes


def walk_out(start, world, cols, ground):
    """True when a walker from `start` (feet cell) reaches a column the build did not write, stepping one block up or
    down at most. Solid is a written block that is not air, or the ground where nothing is written."""
    def solid(x, y, z):
        b = world.get((x, y, z))
        if b is not None:
            return name_of(b) not in AIRS
        return y <= ground(x, z)

    if solid(*start) or solid(start[0], start[1] + 1, start[2]) or not solid(start[0], start[1] - 1, start[2]):
        return False
    seen = {start}
    dq = deque([start])
    while dq:
        x, y, z = dq.popleft()
        if (x, z) not in cols:
            return True
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                n = (x + dx, y + dy, z + dz)
                if n in seen:
                    continue
                if solid(*n) or solid(n[0], n[1] + 1, n[2]) or not solid(n[0], n[1] - 1, n[2]):
                    continue
                if dy == 1 and solid(x, y + 2, z):
                    continue
                seen.add(n)
                dq.append(n)
                break
        if len(seen) > 20000:
            break
    return False


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root")
    a = p.parse_args(argv)
    probs, notes = audit(a.source_root)
    for k, v in notes.items():
        print("  %-48s %s" % (k, v))
    for pr in probs:
        print("PROBLEM:", pr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"problems": probs, "notes": notes}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("%s: %d problem(s)" % ("CLEAN" if not probs else "FAILED", len(probs)))
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())
