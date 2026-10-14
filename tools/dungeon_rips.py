#!/usr/bin/env python
"""Where the dungeon rips stand (data/dungeon_rips.json): the siting rules, the search that finds a site, the check.

A rip no longer belongs to a dungeon (docs/mechanics/DUNGEON_DRAW.md 2.6): a click at any rip draws a dungeon by the
player's progression, so a rip is a place in the world, found, and nothing else. tools/dungeon.py reads this file and
emits the rip's plane, ground, oval, click, particles and advancement; this tool decides WHERE and checks the decision.

  python tools/dungeon_rips.py check                  every rip against every rule below; exit 1 on a problem
  python tools/dungeon_rips.py find <region id> [--top N] [--stride N]
                                                       candidate sites in a region, best first (nothing written)
  python tools/dungeon_rips.py record <region id> <mid_x> <z> --id ID --name NAME --theme THEME
                                                       print the complete record for one chosen site (nothing written)

THE RULES a region rip (kind "region") is held to, each with where its number comes from:

  ground      every number is tools/ground.py's (the canonical heightmap, ROUNDED), never a world. The rip's footprint is a
              9 x 7 window (the 5-wide plane with two blocks either side, from one block behind the plane to five in
              front: the plane, the click, the scorched patch, the exit point) and it is FLAT: round(ground) is one value
              over all 63 columns, so the oval stands on level ground and the plane (frame.y = ground + 1 .. + 4) is air
              above the heightmap, which is what rip.restore records.
  dry         no column of the window under painted water: tools/water_mask.py level_at (the sea at data/world.json
              vertical.sea_level, and every lake or tarn basin at its own level) and every column at least WET_MARGIN
              above the sea.
  clearance   no authored x/z within CLEARANCE (30) blocks of the window, from every data/*.json (tools/hidden_sites.py
              authored_points: the same sweep the hidden legendary sites use), the rips' own records excepted; and ROUTE_CLEARANCE
              (60) from a route path vertex (data/route_paths.json), so a rip is off the road and the critical path's corridor.
  precinct    outside every data/spawn_suppression.json spawn_free_zones box and every town footprint, each with CLEARANCE
              round it: a rip is a wild place and a wild place is not inside a spawn-free precinct.
  region      the window's four corners inside the region's polygon (data/regions.json), so a rip stands in the region it
              names.
  spread      at least SPREAD (300) blocks from every other standing rip. (The 13 test rips on the old mine's trail, kind
              "test_trail", were RETIRED 2026-10-13 and live under retired_rips: they are not standing, so they are not held to
              it and nothing is held to a distance from them.)
  gate        NOT a rule. A rip may stand in a place the player cannot yet reach (the owner, 2026-10-13: "every area in game
              should be capable of spawning a rift, so leave it even if its gated"). data/rift_zones.json says which Rift
              zone a window stands in and what its pass is; the check records that as the rip's `reachable_after` and prints it
              as information. A record that disagrees with the zones is a problem (a stale record), a gated rip is not.

What this does NOT cover (CLAUDE.md "Our list is not the world"): the gate reads data/rift_zones.json's live zones only,
not the Gulch's own zone (data/gulch_mine.json, gym 6) or any other gate a player meets on the way (a ferry, a badge-locked
route); anything in the world that no file in data/ authors, a
tree or a boulder in the plane (rip.restore puts air there), a donor template's outbuilding, a mod's structure. The
clearance is from our records, not from the world; the rip is checked on the heightmap and never on a save. Nether rips are
NOT sited: the Nether has no heightmap (docs/research/notes/nether-rip-siting.md) and the engine places rips in the
overworld only.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "dungeon_rips.json"
SCHEMA = "cobblers.dungeon_rips/1"
CLEARANCE = 30
ROUTE_CLEARANCE = 60
SPREAD = 300
WET_MARGIN = 3
PLANE_W = 5          # frame.x1 - frame.x0 + 1: the oval's three columns and one either side
PLANE_H = 4
# the window round a rip, relative to the plane's middle column and its z: x -4..+4, z -1..+5
WIN = (-4, -1, 4, 5)
ROUTE_FILES = ("data/route_paths.json",)
STANDING_RIPS = False   # the rips open and close (tools/rip_scheduler.py); see probes()
ZONES = ROOT / "data" / "rift_zones.json"


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def mid_x(frame):
    return (frame["x0"] + frame["x1"]) // 2


def window(frame):
    m, z = mid_x(frame), frame["z"]
    return (m + WIN[0], z + WIN[1], m + WIN[2], z + WIN[3])


def in_ring(poly, x, z):
    c, j = False, len(poly) - 1
    for i in range(len(poly)):
        xi, zi = poly[i][0], poly[i][1]
        xj, zj = poly[j][0], poly[j][1]
        if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / float(zj - zi) + xi):
            c = not c
        j = i
    return c


def region_polys():
    doc = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
    return {r["id"]: r["polygons"] for r in doc["regions"]}


def in_region(polys, x, z):
    return any(in_ring(ring, x, z) for ring in polys)


def zone_gates():
    """[(zone id, zone name, [box], pass)] for the live Rift zones in data/rift_zones.json: a zone with boxes and a pass.
    A box is [x0, z0, x1, z1]; z5's second set (also_boxes) is part of the zone. z3 is superseded and has no boxes."""
    doc = json.loads(ZONES.read_text(encoding="utf-8"))
    out = []
    for zid, z in doc["zones"].items():
        boxes = list(z.get("boxes") or []) + list((z.get("also_boxes") or {}).get("boxes") or [])
        if boxes and z.get("pass"):
            out.append((zid, z["name"], boxes, z["pass"]))
    return out


def gate_of(frame, zones=None):
    """The `reachable_after` record for the rip whose window is `frame`'s: the Rift zone the window (any corner or its
    centre) stands in, and that zone's pass as data/rift_zones.json states it; None when it stands in no live zone.
    Information, not a rule: a gated rip is allowed."""
    zones = zones if zones is not None else zone_gates()
    win = window(frame)
    pts = [(win[0], win[1]), (win[2], win[1]), (win[0], win[3]), (win[2], win[3]), (mid_x(frame), frame["z"] + 2)]
    for zid, name, boxes, ps in zones:
        if any(b[0] <= x <= b[2] and b[1] <= z <= b[3] for b in boxes for x, z in pts):
            g = {"zone": zid, "zone_name": name, "kind": ps["kind"]}
            for k in ("threshold", "advancements", "flags"):
                if k in ps:
                    g[k] = ps[k]
            g["from"] = "data/rift_zones.json zones.%s (boxes and pass)" % zid
            return g
    return None


def gate_text(g):
    need = ("%s badges" % g["threshold"] if g["kind"] == "badges" else "%s species caught" % g["threshold"] if g["kind"] == "caught"
            else "flag " + ", ".join(g.get("flags") or ["?"]))
    return "inside Rift zone %s (%s): a player reaches it after %s" % (g["zone"], g["zone_name"], need)


def precinct_boxes():
    """[(x0, z0, x1, z1, why)]: the spawn-free zones and every town footprint, as the data authors them."""
    out = []
    sup = json.loads((ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))
    for z in sup.get("spawn_free_zones") or []:
        b = z["box"]
        out.append((b[0], b[1], b[2], b[3], "spawn_free_zones " + z["id"]))
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    for t in towns:
        f = t.get("footprint") or {}
        if all(k in f for k in ("min_x", "min_z", "max_x", "max_z")):
            out.append((f["min_x"], f["min_z"], f["max_x"], f["max_z"], "town " + t["id"]))
    return out


def box_distance(win, b):
    x0, z0, x1, z1 = win
    bx0, bz0, bx1, bz1 = b[:4]
    dx = max(bx0 - x1, 0, x0 - bx1)
    dz = max(bz0 - z1, 0, z0 - bz1)
    return math.hypot(dx, dz)


def points(rip_ids=()):
    """[(x, z, file)]: every authored coordinate in data/ (tools/hidden_sites.py authored_points) but the rips' own: their
    records, and the presence probes this tool writes about them (data/world_probes.json places.dungeon_rips), which are
    the rips' coordinates over again and would be 0 blocks from the rip they describe."""
    import glob
    import os
    import hidden_sites as H
    out = []
    files = sorted(glob.glob(str(ROOT / "data" / "*.json"))) + sorted(glob.glob(str(ROOT / "data" / "*" / "*.json")))
    for f in files:
        doc = json.loads(Path(f).read_text(encoding="utf-8"))
        rel = os.path.relpath(f, ROOT).replace("\\", "/")
        if rel == "data/world_probes.json":
            doc["places"].pop("dungeon_rips", None)
        H._walk(doc, out, rel, set(rip_ids))
    return out


def nearest(win, pts, files=None):
    """(distance from the window's edge, x, z, file) of the nearest authored point (optionally of `files` only)."""
    import hidden_sites as H
    sel = [p for p in pts if files is None or p[2] in files]
    return H.nearest_authored(win, sel)


def site_problems(g, rip_id, region_id, frame, pts, polys, boxes, others, test_trail=False):
    """[problem] for one region rip's site, against every rule in the module docstring."""
    import water_mask as W
    bad = []
    win = window(frame)
    h = g.box(*win)
    gy = int(h[0][0])
    if int(h.min()) != int(h.max()):
        bad.append("%s: the window x%d..%d z%d..%d is not flat (round(ground) %d..%d)" % (rip_id, win[0], win[2], win[1], win[3], h.min(), h.max()))
    if frame["y"] != int(h.min()) + 1:
        bad.append("%s: frame.y %d is not ground + 1 (%d)" % (rip_id, frame["y"], int(h.min()) + 1))
    if int(h.min()) < W.sea_level() + WET_MARGIN:
        bad.append("%s: ground y%d is within %d of the sea (y%d)" % (rip_id, h.min(), WET_MARGIN, W.sea_level()))
    bodies = W.bodies()
    for x in range(win[0], win[2] + 1):
        for z in range(win[1], win[3] + 1):
            body, _lvl = W.level_at(x, z, g, bodies)
            if body is not None:
                bad.append("%s: (%d, %d) is under painted water (%s)" % (rip_id, x, z, body))
                break
        else:
            continue
        break
    near = nearest(win, pts)
    if near and near[0] < CLEARANCE:
        bad.append("%s: authored (%d, %d) in %s is %.0f from the window; the rule is %d" % (rip_id, near[1], near[2], near[3], near[0], CLEARANCE))
    rn = nearest(win, pts, ROUTE_FILES)
    if rn and rn[0] < ROUTE_CLEARANCE:
        bad.append("%s: a route vertex (%d, %d) is %.0f from the window; the rule is %d" % (rip_id, rn[1], rn[2], rn[0], ROUTE_CLEARANCE))
    for b in boxes:
        if box_distance(win, b) < CLEARANCE:
            bad.append("%s: %.0f blocks from %s; the rule is %d" % (rip_id, box_distance(win, b), b[4], CLEARANCE))
    ps = polys.get(region_id)
    if ps is None:
        bad.append("%s: region %r is not in data/regions.json" % (rip_id, region_id))
    else:
        for cx, cz in ((win[0], win[1]), (win[2], win[1]), (win[0], win[3]), (win[2], win[3])):
            if not in_region(ps, cx, cz):
                bad.append("%s: corner (%d, %d) is outside region %s" % (rip_id, cx, cz, region_id))
                break
    if not test_trail:
        for oid, ox, oz in others:
            d = math.hypot(mid_x(frame) - ox, frame["z"] - oz)
            if d < SPREAD:
                bad.append("%s: %.0f blocks from %s; the spread is %d" % (rip_id, d, oid, SPREAD))
    return bad


def _buckets(pts, size=64):
    b = {}
    for p in pts:
        b.setdefault((int(p[0]) // size, int(p[1]) // size), []).append(p)
    return b


def _nearest_in(buckets, win, reach, size=64):
    """Distance from the window's edge to the nearest point within `reach` of it, else reach + 1 (bucketed: a
    candidate looks at its neighbouring cells only)."""
    x0, z0, x1, z1 = win
    best = reach + 1.0
    for cx in range((x0 - reach) // size, (x1 + reach) // size + 1):
        for cz in range((z0 - reach) // size, (z1 + reach) // size + 1):
            for p in buckets.get((cx, cz), ()):
                dx = max(x0 - p[0], 0, p[0] - x1)
                dz = max(z0 - p[1], 0, p[1] - z1)
                d = math.hypot(dx, dz)
                if d < best:
                    best = d
    return best


def find(g, region_id, top=8, stride=8, others=(), rip_ids=(), shared=None):
    """Candidate sites in a region, best first: [(score, mid_x, z, gy, nearest_authored, nearest_route)]. The score
    prefers distance from anything authored (capped at 150, so a far corner does not beat a good middle), then nearness to
    the region's centre of mass. `shared` caches the points and buckets across regions."""
    import numpy as np
    from PIL import Image, ImageDraw
    import water_mask as W
    polys = region_polys()[region_id]
    if shared is None:
        shared = {}
    if "pts" not in shared:
        shared["pts"] = points(rip_ids)
        shared["b_all"] = _buckets(shared["pts"])
        shared["b_route"] = _buckets([p for p in shared["pts"] if p[2] in ROUTE_FILES])
        shared["boxes"] = precinct_boxes()
        shared["bodies"] = W.bodies()
    boxes, bodies, b_all, b_route = shared["boxes"], shared["bodies"], shared["b_all"], shared["b_route"]
    xs = [p[0] for ring in polys for p in ring]
    zs = [p[1] for ring in polys for p in ring]
    bx0, bx1, bz0, bz1 = max(0, int(min(xs))), min(8191, int(max(xs))), max(0, int(min(zs))), min(8191, int(max(zs)))
    R = np.round(g.heights[bz0 - g.oz:bz1 - g.oz + 1, bx0 - g.ox:bx1 - g.ox + 1]).astype(np.int16)

    def run(a, n, axis, fn):
        out = None
        for k in range(n):
            sl = [slice(None), slice(None)]
            sl[axis] = slice(k, a.shape[axis] - n + 1 + k)
            s = a[tuple(sl)]
            out = s if out is None else fn(out, s)
        return out
    mn = run(run(R, 9, 1, np.minimum), 7, 0, np.minimum)
    mx = run(run(R, 9, 1, np.maximum), 7, 0, np.maximum)
    flat = (mn == mx) & (mn >= W.sea_level() + WET_MARGIN)
    # the region as a raster over the same box, so the four corners are an array lookup
    mask = Image.new("L", (bx1 - bx0 + 1, bz1 - bz0 + 1), 0)
    dr = ImageDraw.Draw(mask)
    for ring in polys:
        dr.polygon([(p[0] - bx0, p[1] - bz0) for p in ring], fill=1)
    M = np.array(mask, dtype=bool)
    Hm, Wm = flat.shape
    iy, ix = np.mgrid[0:Hm, 0:Wm]
    keep = flat & (ix % stride == 0) & (iy % stride == 0)
    keep &= M[iy, ix] & M[iy, ix + 8] & M[iy + 6, ix] & M[iy + 6, ix + 8] & M[iy + 3, ix + 4]
    ys, xs_ = np.nonzero(keep)
    cx = sum(p[0] for p in polys[0]) / len(polys[0])
    cz = sum(p[1] for p in polys[0]) / len(polys[0])
    out = []
    for iy_, ix_ in zip(ys, xs_):
        m = bx0 + int(ix_) + 4
        z = bz0 + int(iy_) + 1
        win = (m - 4, z - 1, m + 4, z + 5)
        d = _nearest_in(b_all, win, 150)
        if d < CLEARANCE:
            continue
        dr_ = _nearest_in(b_route, win, ROUTE_CLEARANCE)
        if dr_ < ROUTE_CLEARANCE:
            continue
        if any(box_distance(win, b) < CLEARANCE for b in boxes):
            continue
        if any(math.hypot(m - ox, z - oz) < SPREAD for _oid, ox, oz in others):
            continue
        wet = False
        for xx in range(win[0], win[2] + 1, 4):
            for zz in range(win[1], win[3] + 1, 3):
                if W.level_at(xx, zz, g, bodies)[0] is not None:
                    wet = True
        if wet:
            continue
        gy = int(mn[iy_, ix_])
        out.append((min(d, 150.0) - 0.02 * math.hypot(m - cx, z - cz), m, z, gy, round(d), round(dr_)))
    out.sort(reverse=True)
    return out[:top]


def record(g, rip_id, name, region_id, m, z, theme, pts=None):
    """The complete record for a region rip at plane middle column `m`, plane row `z` (frame.y = round(ground) + 1)."""
    import dungeon as D
    gy = g(m, z + 1)
    f = {"x0": m - 2, "x1": m + 2, "z": z, "y": gy + 1, "height": PLANE_H}
    win = window(f)
    h = g.box(*win)
    rec = {
        "id": rip_id, "name": name, "kind": "region", "region": region_id, "scorch_theme": theme,
        "frame": f,
        "ground": {"y": gy, "window": list(win), "heights": [int(h.min()), int(h.max())],
                   "heightmap_value": round(float(g.heights[z + 1 - g.oz, m - g.ox]), 2),
                   "rule": "tools/ground.py, the canonical heightmap ROUNDED: round(ground) is %d over all %d columns of x%d..%d z%d..%d "
                           "(tools/dungeon_rips.py, 2026-10-13); the plane stands at ground + 1 and is air above the heightmap"
                           % (gy, h.size, win[0], win[2], win[1], win[3])},
        "outside": [m + 0.5, gy + 1, z + 3.5, 0],
        "click": [m, gy + 1, z + 1],
        "oval": {"width": 3.0, "height": 4.0, "in_front": 0.06},
        "plume": False,
    }
    rec["restore"] = D.rip_restore_measured(rec, g)
    gate = gate_of(f)
    if gate:
        rec["reachable_after"] = gate
    if pts is not None:
        near = nearest(win, pts)
        rn = nearest(win, pts, ROUTE_FILES)
        rec["siting"] = {"nearest_authored": {"distance": round(near[0]), "x": int(near[1]), "z": int(near[2]), "file": near[3]},
                         "nearest_route_vertex": ({"distance": round(rn[0]), "x": int(rn[1]), "z": int(rn[2])} if rn else None)}
    return rec


def problems(doc=None, g=None):
    """[problem] over the whole file: shape, ids, order, and every region rip's site."""
    doc = doc if doc is not None else load()
    bad = []
    if doc.get("schema") != SCHEMA:
        bad.append("schema must be %s" % SCHEMA)
    rips = doc["rips"]
    ids = [r["id"] for r in rips]
    retired = doc.get("retired_rips") or []
    if len(set(ids)) != len(ids) or {r["id"] for r in retired} & set(ids):
        bad.append("two rips share an id")
    for r in rips:
        if not r["id"].startswith("rip_"):
            bad.append("%s: a rip id starts rip_ (id_authorship keys every data/ id; a bare region name would collide)" % r["id"])
        f = r["frame"]
        if f["x1"] - f["x0"] + 1 != PLANE_W or f["height"] != PLANE_H:
            bad.append("%s: the plane is %d wide and %d high" % (r["id"], PLANE_W, PLANE_H))
        if r["click"][0] != mid_x(f) or r["click"][2] != f["z"] + 1:
            bad.append("%s: the click is the plane's middle column, one block in front" % r["id"])
        if r["kind"] not in ("test_trail", "region"):
            bad.append("%s: kind %r" % (r["id"], r["kind"]))
    zones = zone_gates()
    for r in rips:
        want = gate_of(r["frame"], zones)
        if r.get("reachable_after") != want:
            bad.append("%s: reachable_after is %s, data/rift_zones.json puts the rip at %s (python tools/dungeon_rips.py check; "
                       "a gated rip is allowed, a stale record is not)" % (r["id"], r.get("reachable_after"), want))
    if g is None:
        return bad
    polys = region_polys()
    boxes = precinct_boxes()
    pts = points(ids + [r["id"] for r in retired])
    region_rips = [r for r in rips if r["kind"] == "region"]
    for r in region_rips:
        others = [(o["id"], mid_x(o["frame"]), o["frame"]["z"]) for o in rips if o is not r and o["kind"] != "test_trail"]
        bad += site_problems(g, r["id"], r["region"], r["frame"], pts, polys, boxes, others)
        if r["outside"] != [mid_x(r["frame"]) + 0.5, r["frame"]["y"], r["frame"]["z"] + 3.5, 0]:
            bad.append("%s: outside is the point three blocks south of the click, facing south" % r["id"])
    return bad


def probes(doc=None, skip=()):
    """{"dungeon_rips": [probe]} in data/world_probes.json's shape, for tools/presence_audit.py --only extra: per standing
    rip its interaction, its oval and the themed core block under it (what R16DR leaves in the world), and once the oval's
    item and model value; per RETIRED rip (2026-10-13) the opposite: no interaction, no oval, the ground under where the oval
    stood back to retired.ground and the plane's bottom middle cell back to rip.restore. The probes are written from the same
    record and the same rip_tag / rip_scorch_cells the pack is, so they prove the WORLD against the plan, not the plan.
    A count of 0 proves little by itself (an entity not yet loaded is also 0): presence_audit holds the chunk first."""
    import dungeon as D
    ddoc = D.load()
    doc = doc if doc is not None else load()
    out = []
    # 2026-10-14: the rips no longer stand (tools/rip_scheduler.py opens a few at random and closes them), so there is nothing a
    # presence probe may expect at a candidate: it holds the click and the oval while open and the original ground while closed,
    # and which it is depends on the clock. The probes of a standing rip are kept behind STANDING_RIPS (False) for the day a rip
    # stands again; the retired rips' probes below are unchanged
    for r in (doc["rips"] if STANDING_RIPS else []):
        if r["id"] in skip:
            continue
        tag, oval = D.rip_tag(r), ddoc["engine"]["rip_art"]["tag"]
        hold = list(r["click"])
        out.append({"what": "%s: its interaction (after R16DR's entity chain)" % r["name"],
                    "entity": "@e[type=minecraft:interaction,tag=%s]" % tag, "count": 1, "hold": hold})
        out.append({"what": "%s: its oval (one item_display, in front of the opening)" % r["name"],
                    "entity": "@e[type=minecraft:item_display,tag=%s,tag=%s]" % (tag, oval), "count": 1, "hold": hold})
        x, y, z, blk = D.rip_scorch_cells(r)[0]
        out.append({"what": "%s: the themed ground under the oval (%s)" % (r["name"], blk), "block": [x, y, z, blk], "expect": True})
        if len(out) == 3:
            art = ddoc["engine"]["rip_art"]
            out.append({"what": "%s: its oval is the right item and model value (%s with custom_model_data %d)" % (r["name"], art["item"], art["custom_model_data"]),
                        "entity": "@e[type=minecraft:item_display,tag=%s,tag=%s,nbt={item:{id:\"%s\",components:{\"minecraft:custom_model_data\":%d}}}]"
                                  % (tag, oval, art["item"], art["custom_model_data"]),
                        "count": 1, "hold": hold})
    for r in doc.get("retired_rips") or []:
        tag, oval = D.rip_tag(r), ddoc["engine"]["rip_art"]["tag"]
        hold = list(r["click"])
        out.append({"what": "%s (RETIRED): no interaction (after R16DR's retire sweep)" % r["name"],
                    "entity": "@e[type=minecraft:interaction,tag=%s]" % tag, "count": 0, "hold": hold})
        out.append({"what": "%s (RETIRED): no oval" % r["name"],
                    "entity": "@e[type=minecraft:item_display,tag=%s,tag=%s]" % (tag, oval), "count": 0, "hold": hold})
        x, y, z, _blk = D.rip_scorch_cells(r)[0]
        back = r["retired"]["ground"]["%d,%d" % (x, z)].split("[")[0]
        out.append({"what": "%s (RETIRED): the ground under where the oval stood is back (%s)" % (r["name"], back),
                    "block": [x, y, z, back], "expect": True})
        f = r["frame"]
        plane = r["restore"][str(mid_x(f))][0].split("[")[0]
        out.append({"what": "%s (RETIRED): the plane's bottom middle cell is what the plane held before (%s, rip.restore)" % (r["name"], plane),
                    "block": [mid_x(f), f["y"], f["z"], plane], "expect": True})
    return {"dungeon_rips": out}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    f = sub.add_parser("find")
    f.add_argument("region")
    f.add_argument("--top", type=int, default=6)
    f.add_argument("--stride", type=int, default=8)
    fa = sub.add_parser("find-all", help="the best candidates in every region that has no region rip yet")
    fa.add_argument("--top", type=int, default=3)
    fa.add_argument("--stride", type=int, default=8)
    pr = sub.add_parser("probes", help="the presence probes for data/world_probes.json (--write puts them there)")
    pr.add_argument("--write", action="store_true")
    r = sub.add_parser("record")
    r.add_argument("region")
    r.add_argument("mid_x", type=int)
    r.add_argument("z", type=int)
    r.add_argument("--id", required=True)
    r.add_argument("--name", required=True)
    r.add_argument("--theme", required=True)
    a = ap.parse_args(argv)
    import ground as G
    g = G.load()
    doc = load()
    if a.cmd == "check":
        bad = problems(doc, g)
        for b in bad:
            print("PROBLEM " + b)
        for r in doc["rips"]:
            if r.get("reachable_after"):
                print("INFO %s: %s (information, not a problem: a gated rip is allowed)" % (r["id"], gate_text(r["reachable_after"])))
        print("%d rips (%d region), %d retired, %d gated, %d problem(s)" % (
            len(doc["rips"]), sum(r["kind"] == "region" for r in doc["rips"]), len(doc.get("retired_rips") or []),
            sum(bool(r.get("reachable_after")) for r in doc["rips"]), len(bad)))
        return 1 if bad else 0
    if a.cmd == "probes":
        pb = probes(doc)
        if a.write:
            wp = ROOT / "data" / "world_probes.json"
            d = json.loads(wp.read_text(encoding="utf-8"))
            d["places"].update(pb)
            wp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for k, v in pb.items():
            print(k, len(v), "probes", "(written)" if a.write else "")
        return 0
    others = [(o["id"], mid_x(o["frame"]), o["frame"]["z"]) for o in doc["rips"] if o["kind"] != "test_trail"]
    every_id = [o["id"] for o in doc["rips"]] + [o["id"] for o in doc.get("retired_rips") or []]
    if a.cmd == "find":
        for sc, m, z, gy, d, dr in find(g, a.region, a.top, a.stride, others, every_id):
            print("score %.1f  mid_x %d  z %d  ground y%d  nearest authored %d  nearest route vertex %d" % (sc, m, z, gy, d, dr))
        return 0
    if a.cmd == "find-all":
        shared = {}
        have = {o["region"] for o in doc["rips"] if o["kind"] == "region"}
        for rid in region_polys():
            if rid in have:
                continue
            res = find(g, rid, a.top, a.stride, others, every_id, shared)
            print(rid, "(no candidate)" if not res else "")
            for sc, m, z, gy, d, dr in res:
                print("   score %.1f  mid_x %d  z %d  ground y%d  nearest authored %d  nearest route vertex %d" % (sc, m, z, gy, d, dr))
            sys.stdout.flush()
        return 0
    print(json.dumps(record(g, a.id, a.name, a.region, a.mid_x, a.z, a.theme, points(every_id)), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
