#!/usr/bin/env python
"""Offline audit of the evolution-stone faces (build/datapacks/cobblers_mines against data/mines.json).

Independent of tools/mines.py's model: it never imports it. The pack is replayed, and what it wrote is checked against
data/mines.json's own words and against other systems' data and output:

  pack        one build function per site in the data, and for every face a check, a restore and one function per
              variant; the load and tick tags; nothing passes on an empty pack or an empty build
  boxes       every face's box written whole at variant 0: host rock and its ore only, the ore count within the data's
              yield, at least visible_min of it on the front plane's bottom row
  variants    each variant function: first a fill of exactly the box with the host over #cobblers:face_resettable, then
              only guarded setblocks (`execute if block P #tag run setblock P <ore>`, P inside the box) of the face's
              ore, as many as the yield allows and at least visible_min on the front's bottom row
  guard       each check: the period against the face's last restore, the box's four corners (grown by one) loaded, no
              player and no Pokemon in the box grown by one, all before the restore is called; the restore draws
              `random value 0..7`, never repeats the last variant, and stamps the time
  driver      the tick runs the drive every `every_ticks`; the drive runs each site only while a player is inside an
              approach box that holds every face of the site with at least half the approach margin to spare; the
              load sets the period to the data's (at least 600 s)
  tag         the resettable tag holds air, cave air, every host and every ore the faces use, and no container
  cover       every box column's ground (the heightmap, rounded; the Displaced City cavern's floor from
              derived/cavern/plan.npz inside the cavern) at least 2 over the box top
  front       the cell in front of every box's front plane is written air from the box's bottom to its top, over a
              written solid floor
  walk        from the stand in front of each face, over the replayed writes on the ground, a walker stepping at most
              one block up or down reaches a column the build did not write
  plan        no written column on a lot, an anchor lot, a street (the plan's cells and the data polyline), the plaza,
              a building's footprint or a route event site (tools/town_dressing_audit.py's plan recomputation), an
              earthwork's command columns, a lamp, a trader's spot, a signpost, painted water, a town dressing write or
              a working Pokemon's point; none within 8 of a column the pending water export changes (the file missing is
              a failure); in the cavern, none within 3 of a tree's trunk, on a light write, or within 4 of the tunnel's
              line
  blocks      no written block that data/spawn_blocks.json names as a spawn condition; bedrock only at a site whose data
              says so, and never next to a written air cell (no bedrock shows in a cut)
  exchange    data/traders.json has the Exchange in the Mining Town: stock "stones", buys false, every stone the faces
              carry on sale, nothing else; no evolution stone in CobbleDollars' bank.json (so nothing buys one back)
  step        tools/reapply.py has R9O running every site's build function, and the pack in SERVER_PACKS and WORLD_LOCAL
  limits      tools/function_limits.py finds nothing the server would refuse

  python tools/mines_audit.py [--source-root DIR]      writes derived/mines/audit.json; exit 1 on any problem
"""
from __future__ import annotations

import argparse
import json
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
GUARDED = re.compile(r"^execute if block (-?\d+) (-?\d+) (-?\d+) (#\S+) run setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$")
AIRS = ("minecraft:air", "minecraft:cave_air")
CONTAINERS = ("chest", "barrel", "shulker", "hopper", "dispenser", "dropper", "furnace", "smoker", "crafter")
WATER_REACH = 8
TREE_REACH = 3
TUNNEL_REACH = 4


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


def front_cells(box, front):
    """The box's front plane, and the cells just in front of it, as {(x, y, z)} sets."""
    x0, y0, z0, x1, y1, z1 = box
    plane, before = set(), set()
    for y in range(y0, y1 + 1):
        if front in ("north", "south"):
            zf, zb = (z0, z0 - 1) if front == "north" else (z1, z1 + 1)
            for x in range(x0, x1 + 1):
                plane.add((x, y, zf))
                before.add((x, y, zb))
        else:
            xf, xb = (x0, x0 - 1) if front == "west" else (x1, x1 + 1)
            for z in range(z0, z1 + 1):
                plane.add((xf, y, z))
                before.add((xb, y, z))
    return plane, before


def bottom_front(box, front):
    """The front plane's bottom row without its two end cells (where the visible ore goes)."""
    x0, y0, z0, x1, _y1, z1 = box
    plane, _b = front_cells(box, front)
    out = set()
    for (x, y, z) in plane:
        if y != y0:
            continue
        if front in ("north", "south") and x in (x0, x1):
            continue
        if front in ("west", "east") and z in (z0, z1):
            continue
        out.add((x, y, z))
    return out


def in_box(c, box):
    x0, y0, z0, x1, y1, z1 = box
    return x0 <= c[0] <= x1 and y0 <= c[1] <= y1 and z0 <= c[2] <= z1


def audit(source_root=None):
    probs, notes = [], {}
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    sites = spec.get("sites") or []
    if not sites or not any(s.get("faces") for s in sites):
        return ["data/mines.json has no site with a face: nothing to audit is not a clean audit"], notes
    if not FN.is_dir():
        return ["no pack %s: run `python tools/mines.py build` first" % FN.relative_to(ROOT)], notes
    rs = spec["restore"]
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

    def ground(x, z, site):
        if site.get("ground") == "cavern_floor":
            (cx0, cz0, cx1, cz1), floor, _cj = cav
            if cx0 <= x <= cx1 and cz0 <= z <= cz1:
                return int(floor[z - cz0, x - cx0])
        return g(x, z)

    # ---- other systems' data
    import town_dressing_audit as TDA
    import town_character as TC
    import elder_trees
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
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

    total_writes, total_faces = 0, 0
    for site in sites:
        sid = site["id"]
        s = site["settlement"]
        body = lines_of("build_%s" % sid)
        if body is None:
            probs.append("%s: no build function build_%s" % (sid, sid))
            continue
        world = {}
        replay([l for l in body if not l.startswith("forceload")], world)
        if not world:
            probs.append("%s: the build function writes nothing" % sid)
            continue
        total_writes += len(world)
        cols = {(x, z) for x, _y, z in world}

        # plan
        planp = ROOT / "derived" / "towns" / ("%s_plan.json" % s)
        if not planp.is_file():
            probs.append("%s: no town plan %s" % (sid, planp.relative_to(ROOT)))
        else:
            plan = json.loads(planp.read_text(encoding="utf-8"))
            rects, unknown = TDA.footprints(s, doc, templates)
            if unknown:
                probs.append("%s: buildings with templates this audit cannot read: %s" % (sid, unknown))
            why = TDA.forbidden(plan, doc["settlements"][s].get("plan") or {}, rects, TDA.event_sites())
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
                probs.append("%s: %d written column(s) on %s, e.g. %s" % (sid, len(cs), w, sorted(cs)[0]))
        for t in traders.get("traders") or []:
            p = t.get("position") or {}
            if any(abs(x - p.get("x", 10 ** 9)) <= 1 and abs(z - p.get("z", 10 ** 9)) <= 1 for x, z in cols):
                probs.append("%s: a write within 1 of trader %s" % (sid, t["id"]))
        for px, pz in posts or []:
            if any(abs(x - px) <= 1 and abs(z - pz) <= 1 for x, z in cols):
                probs.append("%s: a write within 1 of the signpost at %d,%d" % (sid, px, pz))
        on_dress = cols & dress_cols
        if on_dress:
            probs.append("%s: %d written column(s) under a town dressing write, e.g. %s" % (sid, len(on_dress), sorted(on_dress)[0]))
        near_amb = {c for c in cols if any((c[0] + dx, c[1] + dz) in amb_pts for dx in (-1, 0, 1) for dz in (-1, 0, 1))}
        if near_amb:
            probs.append("%s: %d written column(s) within 1 of a working Pokemon's point" % (sid, len(near_amb)))
        if site.get("ground") != "cavern_floor":
            wetc = [c for c in cols if wet[c[1] - g.oz, c[0] - g.ox]]
            if wetc:
                probs.append("%s: %d written column(s) on painted water, e.g. %s" % (sid, len(wetc), sorted(wetc)[0]))
            if changed is not None:
                xs, zs = [c[0] for c in cols], [c[1] for c in cols]
                sub = np.array(changed[min(zs) - WATER_REACH:max(zs) + WATER_REACH + 1, min(xs) - WATER_REACH:max(xs) + WATER_REACH + 1])
                bad = []
                for x, z in cols:
                    i, j = z - (min(zs) - WATER_REACH), x - (min(xs) - WATER_REACH)
                    if sub[i - WATER_REACH:i + WATER_REACH + 1, j - WATER_REACH:j + WATER_REACH + 1].any():
                        bad.append((x, z))
                if bad:
                    probs.append("%s: %d written column(s) within %d of a column the water export changes, e.g. %s"
                                 % (sid, len(bad), WATER_REACH, sorted(bad)[0]))
        else:
            (_b, _f, cj) = cav
            for tr in cj.get("tree_positions") or []:
                tx, _ty, tz = tr["at"]
                if any(abs(x - tx) <= TREE_REACH and abs(z - tz) <= TREE_REACH for x, z in cols):
                    probs.append("%s: a write within %d of the cavern tree at %d,%d" % (sid, TREE_REACH, tx, tz))
            lf = ROOT / "build" / "datapacks" / "cobblers_cavern" / "data" / "cobblers" / "function" / "cavern" / "40_light.mcfunction"
            if not lf.is_file():
                probs.append("%s: no cavern light function to check against" % sid)
            else:
                lw = {}
                replay([l for l in lf.read_text(encoding="utf-8").splitlines() if not l.startswith("forceload")], lw)
                on = cols & {(x, z) for x, _y, z in lw}
                if on:
                    probs.append("%s: %d written column(s) on a cavern light write, e.g. %s" % (sid, len(on), sorted(on)[0]))
            wps = cj["tunnel"]["waypoints"]
            for (ax, az), (bx, bz) in zip(wps, wps[1:]):
                n = max(abs(bx - ax), abs(bz - az)) + 1
                for i in range(n + 1):
                    tx, tz = ax + (bx - ax) * i / n, az + (bz - az) * i / n
                    if any(abs(x - tx) <= TUNNEL_REACH and abs(z - tz) <= TUNNEL_REACH for x, z in cols):
                        probs.append("%s: a write within %d of the cavern tunnel's line near %d,%d" % (sid, TUNNEL_REACH, tx, tz))
                        break

        # blocks
        for c, b in world.items():
            if name_of(b) in spawn:
                probs.append("%s: %s at %s is a spawn condition" % (sid, b, c))
                break
        bed = [c for c, b in world.items() if name_of(b) == "minecraft:bedrock"]
        if bed and not site.get("bedrock_skin"):
            probs.append("%s: %d bedrock cells at a site whose data gives it no bedrock skin" % (sid, len(bed)))
        for c in bed:
            if any(world.get((c[0] + dx, c[1] + dy, c[2] + dz)) in AIRS
                   for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))):
                probs.append("%s: bedrock at %s shows in the cut" % (sid, c))
                break

        # faces
        if sid not in approach:
            probs.append("%s: the drive never runs this site" % sid)
        faces = site.get("faces") or []
        if not faces:
            probs.append("%s: no face" % sid)
        for face in faces:
            total_faces += 1
            fid, box, front = face["id"], face.get("box"), face.get("front")
            if not box or front not in ("north", "south", "west", "east"):
                probs.append("%s: no box or front" % fid)
                continue
            x0, y0, z0, x1, y1, z1 = box
            host, ore, y = face["host"], face["ore"], face["yield"]
            vis_row = bottom_front(box, front)
            dims = sorted((x1 - x0 + 1, z1 - z0 + 1))
            geo = spec["geometry"]
            if dims != sorted((geo["width"], geo["depth"])) or y1 - y0 + 1 != geo["height"]:
                probs.append("%s: box %s is not %d x %d x %d" % (fid, box, geo["width"], geo["depth"], geo["height"]))
            if ore not in spec["stones"][face["stone"]]["ores"]:
                probs.append("%s: %s is not a %s stone ore" % (fid, ore, face["stone"]))
            if host not in tag or ore not in tag:
                probs.append("%s: its host or ore is not in the resettable tag" % fid)
            a = approach.get(sid)
            half = rs["approach_margin"] // 2
            if a and not (a[0] <= x0 - half and a[2] <= z0 - half and a[3] >= x1 + half and a[5] >= z1 + half
                          and a[1] <= y0 and a[4] >= y1):
                probs.append("%s: the approach box %s does not hold the box with %d to spare" % (fid, a, half))
            # the build writes the box whole at variant 0
            cells = [(x, yy, z) for x in range(x0, x1 + 1) for yy in range(y0, y1 + 1) for z in range(z0, z1 + 1)]
            other = [c for c in cells if world.get(c) not in (host, ore)]
            if other:
                probs.append("%s: %d box cells not written as its host or ore, e.g. %s = %s" % (fid, len(other), other[0], world.get(other[0])))
            n0 = sum(1 for c in cells if world.get(c) == ore)
            if not (y["ore_min"] <= n0 <= y["ore_max"]) or sum(1 for c in vis_row if world.get(c) == ore) < y.get("visible_min", 1):
                probs.append("%s: variant 0 as built holds %d ore (%d on the front's bottom row)" % (fid, n0, sum(1 for c in vis_row if world.get(c) == ore)))
            # cover
            thin = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if ground(x, z, site) < y1 + 2]
            if thin:
                probs.append("%s: %d box columns with ground under the box top + 2, e.g. %s" % (fid, len(thin), thin[0]))
            # front: air before the face over a solid floor
            _plane, before = front_cells(box, front)
            open_ = [c for c in before if world.get(c) not in AIRS]
            if open_:
                probs.append("%s: %d cells before the face are not written air, e.g. %s" % (fid, len(open_), sorted(open_)[0]))
            floor = [(c[0], c[1] - 1, c[2]) for c in before if c[1] == y0]
            if any(world.get(c) in (None,) + AIRS for c in floor):
                probs.append("%s: the floor before the face is not written solid" % fid)
            # walk: from the middle cell before the face to a column the build did not write
            start = sorted((c for c in before if c[1] == y0), key=lambda c: (c[0], c[2]))[geo["width"] // 2]
            if not walk_out(start, world, cols, lambda x, z: ground(x, z, site)):
                probs.append("%s: no walk from %s out of the cut onto unwritten ground" % (fid, start))
            # variants
            nvar = rs["variants"]
            for k in range(nvar):
                v = lines_of("faces/%s_v%d" % (fid, k))
                if v is None:
                    probs.append("%s: no variant %d" % (fid, k))
                    continue
                cmds = [l for l in v if l.strip() and not l.startswith("#")]
                want_fill = "fill %d %d %d %d %d %d %s replace %s" % (x0, y0, z0, x1, y1, z1, host, tagname)
                if not cmds or cmds[0] != want_fill:
                    probs.append("%s v%d: the first command is not the filtered fill of exactly the box (%s)" % (fid, k, cmds[:1]))
                    continue
                ores = []
                for l in cmds[1:]:
                    m = GUARDED.match(l)
                    if not m or m.group(1, 2, 3) != m.group(5, 6, 7) or m.group(4) != tagname or m.group(8) != ore:
                        probs.append("%s v%d: an unguarded or foreign command: %s" % (fid, k, l))
                        continue
                    c = tuple(int(q) for q in m.group(1, 2, 3))
                    if not in_box(c, box):
                        probs.append("%s v%d: ore outside the box at %s" % (fid, k, c))
                    ores.append(c)
                if not (y["ore_min"] <= len(set(ores)) <= y["ore_max"]):
                    probs.append("%s v%d: %d ore, the yield is %d-%d" % (fid, k, len(set(ores)), y["ore_min"], y["ore_max"]))
                if len([c for c in ores if c in vis_row]) < y.get("visible_min", 1):
                    probs.append("%s v%d: no ore on the front's bottom row" % (fid, k))
            # check and restore
            chk = [l for l in (lines_of("faces/check_%s" % fid) or []) if l and not l.startswith("#")]
            call = "function cobblers:mines/faces/restore_%s" % fid
            if call not in chk:
                probs.append("%s: its check never calls the restore" % fid)
            else:
                pre = chk[:chk.index(call)]
                gx0, gy0, gz0, gx1, gy1, gz1 = x0 - 1, y0 - 1, z0 - 1, x1 + 1, y1 + 1, z1 + 1
                vol = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (gx0, gy0, gz0, gx1 - gx0, gy1 - gy0, gz1 - gz0)
                need = ["execute if score #d mn.t < #period mn.t run return 0",
                        "execute if entity @a[%s] run return 0" % vol,
                        "execute if entity @e[type=cobblemon:pokemon,%s] run return 0" % vol]
                need += ["execute unless loaded %d %d %d run return 0" % (cx, gy0, cz) for cx in (gx0, gx1) for cz in (gz0, gz1)]
                for n in need:
                    if n not in pre:
                        probs.append("%s: the check lacks, before the restore: %s" % (fid, n))
                if "scoreboard players operation #d mn.t -= #%s mn.last" % fid not in pre:
                    probs.append("%s: the check does not measure from this face's last restore" % fid)
            rst = lines_of("faces/restore_%s" % fid) or []
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
    """True when a walker from `start` (feet cell) reaches a column the build did not write. A column's standing height
    is over its highest solid cell at or under the walker's reach; solid is a written non-air block, or the ground
    where nothing is written."""
    def solid(x, y, z):
        b = world.get((x, y, z))
        if b is not None:
            return b not in AIRS
        return y <= ground(x, z)

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
