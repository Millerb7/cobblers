#!/usr/bin/env python
"""Offline audit of the lake skin and the lake hooks (tools/lake_life.py -> build/datapacks/cobblers_lake_life).

Independent of tools/lake_life.py: nothing is imported from it and nothing is read from derived/lake_life/plan.json.
The pack's functions are parsed (tools/water_life_replay.py: setblock, fill, `fill ... replace <filter>`,
`execute if block ... run fill`) and REPLAYED in index order over a world made only from the canonical heightmap
(tools/ground.py, rounded) and tools/water_mask.py's painting rule. Every expectation comes from that world and from
data/: the spec's numbers in data/lake_life.json (the authored record, not the generator's code), data/water_shape.json,
data/portals.json, data/legendaries.json, data/towns.json, data/placements.json, data/ferries.json,
data/ferry_docks.json, data/routes.json, data/bridges.json, data/foliage.json, data/rewards.json, and the OTHER packs'
own functions (cobblers_portals, cobblers_legendaries, cobblers_sea_drift, cobblers_sea_life).

  place      every write is in a lake column (ground < level inside its basin) or on that lake's bank (a dry column
             beside one); a cane is on a bank, nothing else is
  plants     every seagrass, tall seagrass, kelp and kelp plant stands in a cell that held lake water, on a full
             block (or its own lower half / kelp stem); every kelp stem has kelp above it; lily pads float on water;
             a cane stands on the column's own ground with water beside its soil
  kelp       every kelp top at most level - skin.kelp.top_below_surface (and that number at least 3: WATER_LIFE 1,
             "never within 2 of the surface"), at age 25 so it never grows toward the surface
  zones      seagrass only on the shelf (data zones.shelf_depths), kelp, gravel and cobble only in the drop-off band
             (drop_from_depth to the lake's data/water_shape.json drop_depth), mud and clay only deeper
  silt       every write filtered on #cobblers:lake_bed is one cell AT the column's ground (its top bed block) and
             is a full block, and the tag holds only full blocks: no column's top changes height. No other write
             replaces a natural block
  clear      no write within a dive portal's arch apron (5 by 5) grown by exclusions.portal_clearance_blocks, or in
             a column the portals pack writes; no write in a column the legendaries pack writes or within
             exclusions.mouth_clearance_blocks of a grotto's 3 by 3 shaft; no skin write (bed, plants, structures)
             in a legendary's spawn_free_zone; none in a town footprint grown by its water_shape margin, a route
             corridor (protect.road_half_width_blocks), a bridge box grown by bridge_margin_blocks, an event site
             box, a landmark tree's glade, a dock deck or ferry point grown by the data's margins, or near a
             placement standing outside every town
  blocks     no minecraft:light, bubble column, soul sand or magma block; nothing in a water cell that leaves it dry
             (a door, a bed, a fence gate, a waterloggable block without waterlogged=true): a dry cell under water is
             a place to breathe, which is the bypass WATER_LIFE's Departures forbid
  hooks      every data hook's lake has hook writes; every hook site has a light within lights.within_blocks: the
             trio's grotto mouths (Arrow's stone ring, Tilpey's gold light), the deepest survey weight (Viltri), a
             drowned-tree trunk (a soul lantern, Marshy Marsh), the skiffs' hulls, the chained lantern, the field case
  cache      every barrel has a data/rewards.json record whose container is it and whose trigger box holds it and a
             water cell beside it; every lake_life_* record's container is a barrel the pack writes
  nonempty   every painted lake (water_mask.bodies() with a basin) gets skin writes
  foreign    no column in common with cobblers_sea_life, cobblers_sea_drift, cobblers_portals, cobblers_legendaries
  limits     tools/function_limits.py finds nothing the server would refuse

What this does NOT cover: whether kelp, seagrass and lanterns hold in a lake in game (proof P6), whether a light is
seen from the surface (P4), the soil under a cane (paint decides it; the pack guards on vanilla's tags), and any
world that is not the canonical heightmap: a placement or a later pass that put blocks in a lake is not in this
world. A lake the data does not paint (no basin_polygons) is not seen at all.

  python tools/lake_life_audit.py [--source-root DIR] [--pack DIR]   writes derived/lake_life/audit.json; exit 1 on any
                                                                     problem
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL       # noqa: E402
import water_life_replay as R      # noqa: E402

ROOT = R.ROOT
PACK = ROOT / "build" / "datapacks" / "cobblers_lake_life"
FN = ("data", "cobblers", "function", "lake_life")
OUT = ROOT / "derived" / "lake_life" / "audit.json"
FOREIGN = ("cobblers_sea_life", "cobblers_sea_drift", "cobblers_portals", "cobblers_legendaries")
SKIN = ("1bed", "2plants", "3structure")
PLANTS = ("minecraft:seagrass", "minecraft:tall_seagrass", "minecraft:kelp", "minecraft:kelp_plant")
CHECKS = ("place", "plants", "kelp", "zones", "silt", "clear", "blocks", "hooks", "cache", "nonempty", "foreign",
          "limits", "parse")


class Ctx:
    """Everything the checks read, gathered once. Tests build one by hand over a synthetic terrain."""

    def __init__(self, terrain, spec, shape, portals=(), legendaries=(), towns=(), placements=(), docks=(),
                 routes=(), bridges=(), event_sites=(), trees=(), rewards=(), foreign=None):
        self.t = terrain
        self.spec = spec
        self.shape = shape
        self.portals = list(portals)            # [(id, (x, z))] dive portals
        self.legendaries = list(legendaries)    # [{"id", "mouth": [x, z], "spawn_free_zone": [x0, z0, x1, z1]}]
        self.towns = list(towns)                # [(id, box)] grown
        self.placements = list(placements)      # [(id, (x, z))] outside every town footprint
        self.docks = list(docks)                # [(id, [(x, z)], margin)]
        self.routes = list(routes)              # [(id, [(x, z)], half)]
        self.bridges = list(bridges)            # [(id, box)] grown
        self.event_sites = list(event_sites)    # [(id, box)]
        self.trees = list(trees)                # [(id, (x, z), radius)]
        self.rewards = list(rewards)
        self.foreign = foreign or {}            # {pack: set of columns or None (absent)}

    def drop_depth(self, lake):
        for b in self.shape.get("lakes", {}).get("bodies", []):
            if b["id"] == lake:
                return int(b["drop_depth"])
        return None


def load_ctx(source_root=None):
    import ground as G
    import water_mask as WM
    t = R.Terrain(G.load(source_root), WM.sea_level(), WM.bodies())
    spec = R.load("lake_life.json")
    shape = R.load("water_shape.json")
    prot = shape["protect"]
    portals = [(p["id"], tuple(p["at"])) for p in R.load("portals.json")["portals"] if p["gate"] == "dive"]
    leg = [{"id": e["id"], "mouth": e.get("mouth"), "spawn_free_zone": e.get("spawn_free_zone")}
           for e in R.load("legendaries.json")["encounters"]]
    tdoc = R.load("towns.json")
    towns = R.town_boxes(tdoc, prot)
    raw = [(t["footprint"]["min_x"], t["footprint"]["min_z"], t["footprint"]["max_x"], t["footprint"]["max_z"])
           for t in tdoc["towns"] if "min_x" in (t.get("footprint") or {})]
    placements = []
    for p in R.load("placements.json")["placements"]:
        pos = p.get("position")
        if not pos or "x" not in pos:
            continue
        if not any(R.in_box(b, pos["x"], pos["z"]) for b in raw):
            placements.append((p["id"], (pos["x"], pos["z"])))
    ex = spec["exclusions"]
    docks = []
    for d in R.load("ferry_docks.json")["docks"]:
        pts = [tuple(d["near"])] if d.get("near") else []
        if (d.get("shore") or {}).get("at"):
            pts.append(tuple(d["shore"]["at"]))
        docks.append(("ferry_docks:" + d["id"], pts, int(ex["dock_margin_blocks"])))
    for label, body, cols, _sub in __import__("water_mask").sited_claims():
        if label.startswith("dock ") and label.endswith(" deck"):
            docks.append((label, [tuple(c) for c in cols], int(ex["dock_margin_blocks"])))
    for d in R.load("ferries.json")["docks"]:
        pts = [tuple(d["near"])] if d.get("near") else []
        for k in ("landing", "ferryman"):
            if (d.get(k) or {}).get("at"):
                a = d[k]["at"]
                pts.append((a[0], a[-1]))
        docks.append(("ferries:" + d["id"], pts, int(ex["ferry_point_margin_blocks"])))
        # keep_clear is the dock's own deck and step: a deck, so the deck margin
        kc = [(x, z) for b in d.get("keep_clear") or [] for x in range(b[0], b[2] + 1) for z in range(b[1], b[3] + 1)]
        if kc:
            docks.append(("ferries:%s keep_clear" % d["id"], kc, int(ex["dock_margin_blocks"])))
    sm = int(ex["scene_margin_blocks"])
    for s in R.load("scenes.json")["scenes"]:
        a = s.get("area") or {}
        if "from" in a:
            f, t_ = a["from"], a["to"]
            docks.append(("scene " + s["id"], [(x, z) for x in range(min(f[0], t_[0]), max(f[0], t_[0]) + 1)
                                               for z in range(min(f[2], t_[2]), max(f[2], t_[2]) + 1)], sm))
    for tr in R.load("route_trainers.json")["trainers"]:
        if tr.get("seat"):
            docks.append(("seat " + tr["id"], [(tr["seat"][0], tr["seat"][2])], int(ex["seat_margin_blocks"])))
    for hb in R.load("habitat_blocks.json")["blocks"]:
        p = hb.get("position") or {}
        if "x" in p:
            docks.append(("habitat " + hb["id"], [(p["x"], p["z"])], int(ex["habitat_margin_blocks"])))
    half = int(prot["road_half_width_blocks"])
    routes = [(r["id"], [(int(p["x"]), int(p["z"])) for p in r["corridor"]["polyline"]], half)
              for r in R.load("routes.json")["routes"]]
    bm = int(prot["bridge_margin_blocks"])
    bridges = []
    for b in R.load("bridges.json")["bridges"]:
        hw = int(b["walkway_half_width"]) + 2           # the walkway and its two curbs
        if b["axis"] == "z":
            box = (b["centre"] - hw, b["along_from"], b["centre"] + hw, b["along_to"])
        else:
            box = (b["along_from"], b["centre"] - hw, b["along_to"], b["centre"] + hw)
        bridges.append((b["id"], (box[0] - bm, box[1] - bm, box[2] + bm, box[3] + bm)))
    events = [(e["id"], tuple(e["box"])) for e in prot.get("event_sites", [])]
    trees = [(t["id"], tuple(t["site"]), float(t["glade_radius"])) for t in R.load("foliage.json")["landmark_trees"]
             if t.get("site") and t.get("glade_radius")]
    rewards = R.load("rewards.json")["rewards"]
    foreign = {name: R.pack_columns(ROOT / "build" / "datapacks" / name) for name in FOREIGN}
    return Ctx(t, spec, shape, portals, leg, towns, placements, docks, routes, bridges, events, trees, rewards,
               foreign)


def lake_tags(pack):
    tags = {}
    tdir = Path(pack) / "data" / "cobblers" / "tags" / "block"
    for f in tdir.glob("*.json") if tdir.is_dir() else []:
        tags["#cobblers:" + f.stem] = set(json.loads(f.read_text(encoding="utf-8"))["values"])
    return tags


# ------------------------------------------------------------------------------------------------------- checks


def _cell_body(ctx, x, z):
    gy, lv, body = ctx.t.column(x, z)
    if body == "sea":
        return gy, None, None
    return gy, lv, body


def _bank_body(ctx, x, z):
    """The lake a dry column is the bank of (a Chebyshev neighbour is a lake column of it), or None."""
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx or dz:
                _, lv, body = _cell_body(ctx, x + dx, z + dz)
                if body is not None:
                    return body
    return None


def check_place(ctx, W, P):
    """Every write in a lake column or on its bank; a cane only on a bank."""
    bad, cane_wet = [], []
    seen = set()
    for cmd, cell, grp, _prev in W.landed + [(c, cell, None, None) for c, cell in W.dead]:
        x, y, z = cell
        if (x, z, R.bid(cmd.block)) in seen:
            continue
        seen.add((x, z, R.bid(cmd.block)))
        _, lv, body = _cell_body(ctx, x, z)
        cane = R.bid(cmd.block) == "minecraft:sugar_cane"
        if body is None:
            if _bank_body(ctx, x, z) is None:
                bad.append(cell)
        elif cane:
            cane_wet.append(cell)
    for c in bad[:5]:
        P["place"].append("%s at %s is in no lake column and on no lake's bank" % (W.w.get(c, "a write"), c))
    if len(bad) > 5:
        P["place"].append("... %d writes outside every lake and bank in all" % len(bad))
    for c in cane_wet[:3]:
        P["place"].append("a cane at %s is in a lake column, not on the bank" % (c,))
    return {"outside_lakes": len(bad)}


def check_plants(ctx, W, P):
    bad = defaultdict(list)
    n = defaultdict(int)
    for (x, y, z), b in W.w.items():
        i = R.bid(b)
        if i not in PLANTS and i not in ("minecraft:lily_pad", "minecraft:sugar_cane"):
            continue
        n[i] += 1
        below = W.at(x, y - 1, z)
        bi = R.bid(below)
        gy, lv, body = _cell_body(ctx, x, z)
        if i in PLANTS:
            if body is None or not (gy < y <= lv):
                bad[i].append(((x, y, z), "not in a cell of lake water (ground y%d, level %s)" % (gy, lv)))
                continue
        if i == "minecraft:seagrass" and not R.is_full(below):
            bad[i].append(((x, y, z), "on %s" % below))
        elif i == "minecraft:tall_seagrass":
            half = R.props(b).get("half")
            if half == "lower" and not R.is_full(below):
                bad[i].append(((x, y, z), "lower half on %s" % below))
            if half == "upper" and not (bi == i and R.props(below).get("half") == "lower"):
                bad[i].append(((x, y, z), "upper half over %s" % below))
            if half == "lower":
                up = W.at(x, y + 1, z)
                if not (R.bid(up) == i and R.props(up).get("half") == "upper"):
                    bad[i].append(((x, y, z), "lower half with %s above" % up))
        elif i in ("minecraft:kelp", "minecraft:kelp_plant"):
            if not (R.is_full(below) or bi == "minecraft:kelp_plant"):
                bad[i].append(((x, y, z), "on %s" % below))
            if i == "minecraft:kelp_plant" and R.bid(W.at(x, y + 1, z)) not in ("minecraft:kelp", "minecraft:kelp_plant"):
                bad[i].append(((x, y, z), "a stem with %s above it: it turns into a growing head" % W.at(x, y + 1, z)))
        elif i == "minecraft:lily_pad":
            if not R.holds_water(below) or R.is_full(below):
                bad[i].append(((x, y, z), "over %s, not water" % below))
            if body is None or y != lv + 1:
                bad[i].append(((x, y, z), "not on a lake's surface (level %s)" % lv))
        elif i == "minecraft:sugar_cane":
            if bi == "minecraft:sugar_cane":
                continue
            cgy, clv, cbody = _cell_body(ctx, x, z)
            if y - 1 != cgy or below != R.NATURAL:
                bad[i].append(((x, y, z), "not on its column's own ground y%d (on %s)" % (cgy, below)))
                continue
            wet = any(R.holds_water(W.at(x + dx, y - 1, z + dz)) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if not wet:
                bad[i].append(((x, y, z), "no water beside its soil at y%d" % (y - 1)))
    for i, lst in sorted(bad.items()):
        for c, why in lst[:3]:
            P["plants"].append("%s at %s: %s" % (i, c, why))
        if len(lst) > 3:
            P["plants"].append("... %d %s problems in all" % (len(lst), i))
    return {k: v for k, v in n.items()}


def check_kelp(ctx, W, P):
    gap = int(ctx.spec["skin"]["kelp"]["top_below_surface"])
    if gap < 3:
        P["kelp"].append("data/lake_life.json skin.kelp.top_below_surface is %d: WATER_LIFE 1 says never within 2 of "
                         "the surface, which is level - 3 at the highest" % gap)
    tops, worst = 0, None
    for (x, y, z), b in W.w.items():
        if R.bid(b) != "minecraft:kelp":
            continue
        tops += 1
        _, lv, body = _cell_body(ctx, x, z)
        if lv is None:
            continue
        if y > lv - gap:
            P["kelp"].append("kelp top at (%d, %d, %d) is %d under the surface y%d, closer than %d"
                             % (x, y, z, lv - y, lv, gap))
        if R.props(b).get("age") != "25":
            P["kelp"].append("kelp top at (%d, %d, %d) has age %s, not 25: it grows toward the surface"
                             % (x, y, z, R.props(b).get("age")))
        worst = max(worst or -99, y - lv)
    if len(P["kelp"]) > 8:
        P["kelp"][:] = P["kelp"][:8] + ["... %d kelp problems in all" % len(P["kelp"])]
    return {"kelp_tops": tops, "highest_top_minus_level": worst}


def check_zones(ctx, W, P):
    z_ = ctx.spec["zones"]
    shelf = set(int(v) for v in z_["shelf_depths"])
    d0 = int(z_["drop_from_depth"])
    bad = defaultdict(int)
    first = {}
    for (x, y, z), b in W.w.items():
        i = R.bid(b)
        _, lv, body = _cell_body(ctx, x, z)
        if body is None:
            continue
        gy = ctx.t.column(x, z)[0]
        depth = lv - gy
        dd = ctx.drop_depth(body)
        if dd is None:
            bad["no drop_depth for %s" % body] += 1
            continue
        grp = W.group.get((x, y, z))
        ok = True
        if i in ("minecraft:seagrass", "minecraft:tall_seagrass"):
            ok = depth in shelf
        elif i in ("minecraft:kelp", "minecraft:kelp_plant"):
            ok = d0 <= depth <= dd
        elif grp == "1bed" and i in ("minecraft:gravel", "minecraft:cobblestone"):
            ok = d0 <= depth <= dd
        elif grp == "1bed" and i in ("minecraft:mud", "minecraft:clay"):
            ok = depth > dd
        if not ok:
            k = "%s at depth outside its zone in %s" % (i, body)
            bad[k] += 1
            first.setdefault(k, ((x, y, z), depth, dd))
    for k, v in sorted(bad.items()):
        if k in first:
            c, depth, dd = first[k]
            P["zones"].append("%s: %d cells, e.g. %s %d deep (drop_depth %d)" % (k, v, c, depth, dd))
        else:
            P["zones"].append("%s (%d)" % (k, v))
    return {}


def check_silt(ctx, W, parsed, tags, P):
    tag = tags.get("#cobblers:lake_bed")
    if tag is None:
        P["silt"].append("the pack has no #cobblers:lake_bed tag")
        tag = set()
    for t in sorted(tag):
        if not R.is_full(t) or t in ("minecraft:sand", "minecraft:red_sand", "minecraft:gravel"):
            # sand and gravel fall: replacing one leaves the column; but the bed's own sand is ground the export
            # already holds, so only a non-full member is a fault
            if not R.is_full(t):
                P["silt"].append("#cobblers:lake_bed holds %s, which is not a full block" % t)
    n = 0
    for name, cmds in parsed:
        for c in cmds:
            if c.filter != "#cobblers:lake_bed":
                continue
            x0, y0, z0, x1, y1, z1 = c.box
            n += 1
            if y0 != y1:
                P["silt"].append("%s:%d fills more than one layer of the bed: %s" % (name, c.line, c.text[:80]))
                continue
            for (x, z) in c.columns():
                gy = ctx.t.column(x, z)[0]
                if y0 != gy:
                    P["silt"].append("%s:%d replaces y%d at (%d, %d), whose ground is y%d: not the top bed block"
                                     % (name, c.line, y0, x, z, gy))
                    break
            if not R.is_full(c.block):
                P["silt"].append("%s:%d writes %s into the bed, not a full block" % (name, c.line, c.block))
    carve = [(cmd, cell) for cmd, cell, grp, prev in W.landed
             if prev == R.NATURAL and cmd.filter != "#cobblers:lake_bed"]
    for cmd, cell in carve[:5]:
        P["silt"].append("%s:%d replaces natural ground at %s with %s" % (cmd.fn, cmd.line, cell, cmd.block))
    if len(P["silt"]) > 10:
        P["silt"][:] = P["silt"][:10] + ["... %d silt problems in all" % len(P["silt"])]
    return {"bed_writes": n, "natural_replaced_otherwise": len(carve)}


def _write_columns(W):
    cols = defaultdict(set)
    for cmd, cell, grp, _ in W.landed:
        cols[(cell[0], cell[2])].add(grp)
    for cmd, cell in W.dead:
        cols[(cell[0], cell[2])].add(R.group_of(cmd.fn))
    return cols


def check_clear(ctx, W, P, cols=None):
    cols = cols if cols is not None else _write_columns(W)
    ex = ctx.spec["exclusions"]
    pc = int(ex["portal_clearance_blocks"])
    mc = int(ex["mouth_clearance_blocks"])
    hits = defaultdict(list)

    def flag(what, c):
        hits[what].append(c)

    ix = R.ColumnIndex(cols)
    for pid, (px, pz) in ctx.portals:
        for c in ix.in_box(R.chebyshev_box(px, pz, 2 + pc)):
            flag("dive portal %s's 5 by 5 apron + %d" % (pid, pc), c)
    for e in ctx.legendaries:
        if e.get("mouth"):
            mx, mz = e["mouth"]
            for c in ix.in_box(R.chebyshev_box(mx, mz, 1 + mc)):
                flag("%s's 3 by 3 grotto shaft + %d" % (e["id"], mc), c)
        sfz = e.get("spawn_free_zone")
        if sfz:
            for c in ix.in_box(tuple(sfz)):
                if cols[c] & set(SKIN):
                    flag("%s's spawn_free_zone (skin)" % e["id"], c)
    for tid, box in ctx.towns:
        for c in ix.in_box(box):
            flag("town %s (footprint + margin)" % tid, c)
    for bid_, box in ctx.bridges + ctx.event_sites:
        for c in ix.in_box(box):
            flag("box %s" % bid_, c)
    for tid, (tx, tz), rad in ctx.trees:
        for c in ix.in_box(R.chebyshev_box(tx, tz, int(math.ceil(rad)))):
            if math.hypot(c[0] - tx, c[1] - tz) <= rad:
                flag("landmark tree %s's glade" % tid, c)
    for did, pts, m in ctx.docks:
        for c in ix.near_points(pts, m):
            flag("%s + %d" % (did, m), c)
    pm = int(ex["placement_margin_blocks"])
    for pid, (px, pz) in ctx.placements:
        for c in ix.in_box(R.chebyshev_box(px, pz, pm)):
            flag("placement %s + %d" % (pid, pm), c)
    for rid, pts, half in ctx.routes:
        for c in R.near_polyline(ix, pts, half):
            flag("route %s's corridor (half %d)" % (rid, half), c)
    for what, cs in sorted(hits.items()):
        cs = sorted(set(cs))
        P["clear"].append("%d write columns in %s, e.g. %s" % (len(cs), what, cs[0]))
    return {"write_columns": len(cols)}


def check_blocks(ctx, W, P):
    seen = defaultdict(int)
    dry = []
    for (x, y, z), b in W.w.items():
        i = R.bid(b)
        if i in R.FORBIDDEN:
            seen[i] += 1
        if ctx.t.base(x, y, z) == R.WATER and not R.is_full(b) and not R.holds_water(b) and not R.is_air(b):
            dry.append(((x, y, z), b))
        if ctx.t.base(x, y, z) == R.WATER and R.is_air(b):
            dry.append(((x, y, z), b))
    for i, n in sorted(seen.items()):
        P["blocks"].append("%d %s written (WATER_LIFE: never a light block or a bubble column, nor what makes one)"
                           % (n, i))
    for c, b in dry[:5]:
        P["blocks"].append("%s at %s leaves a dry cell in the water: a place to breathe" % (b, c))
    if len(dry) > 5:
        P["blocks"].append("... %d dry cells in the water in all" % len(dry))
    return {"dry_cells_in_water": len(dry)}


def _lights(W, within_ids):
    return [(c, b) for c, b in W.w.items() if R.light_level(b) > 0 and R.bid(b) in within_ids]


def _near(points, targets, r):
    for (x, y, z) in points:
        for (a, b, c) in targets:
            if max(abs(x - a), abs(y - b), abs(z - c)) <= r:
                return True
    return False


def check_hooks(ctx, W, P):
    L = ctx.spec["lights"]
    r = int(L["within_blocks"])
    ids = {"minecraft:" + b for b in L["blocks"]}
    lights = [c for c, b in _lights(W, ids)]
    pal = ctx.spec["palette"]
    by_lake = defaultdict(list)
    for cell, grp in W.group.items():
        if grp in ("4hooks", "5lights"):
            _, lv, body = _cell_body(ctx, cell[0], cell[2])
            by_lake[body].append(cell)
    res = {"lights": len(lights), "hook_cells": {k: len(v) for k, v in by_lake.items() if k}}
    leg = {e["id"]: e for e in ctx.legendaries}
    portals = dict(ctx.portals)
    for h in ctx.spec["hooks"]:
        cells = by_lake.get(h["lake"], [])
        if not cells:
            P["hooks"].append("%s: no hook writes in %s" % (h["id"], h["lake"]))
            continue
        lake_lights = [c for c in lights if _cell_body(ctx, c[0], c[2])[2] == h["lake"]]
        kind = h["kind"]
        sites = []
        if kind in ("stone_ring", "gold_light"):
            lid = (h.get("around") or h.get("near"))["legendary"]
            m = leg.get(lid, {}).get("mouth")
            if not m:
                P["hooks"].append("%s: data/legendaries.json %s has no mouth" % (h["id"], lid))
                continue
            gy = ctx.t.column(m[0], m[1])[0]
            sites = [(m[0], gy + 1, m[1])]
            what = "%s's grotto mouth" % lid
        elif kind == "buoy_line":
            wts = [c for c in cells if R.bid(W.w[c]) == pal["weight"]]
            sites = [min(wts, key=lambda c: c[1])] if wts else []
            what = "the deepest survey weight"
        elif kind == "drowned_ring":
            trunks = [c for c in cells if R.bid(W.w[c]) == R.bid(ctx.spec["skin"]["drowned_trees"]["trunk"])]
            n_tr = len({(c[0], c[2]) for c in trunks if R.props(W.w[c]).get("axis") == "y"})
            if n_tr < int(h["min_trees"]):
                P["hooks"].append("%s: %d upright trunks, under the data's min_trees %d" % (h["id"], n_tr,
                                                                                          int(h["min_trees"])))
            souls = [c for c in lake_lights if R.bid(W.w[c]) == pal["soul_lantern"]]
            if not souls:
                P["hooks"].append("%s: no soul lantern in %s" % (h["id"], h["lake"]))
            elif not _near(souls, trunks, r):
                P["hooks"].append("%s: no soul lantern within %d of a drowned trunk" % (h["id"], r))
            continue
        elif kind == "skiff":
            sites = [c for c in cells if R.bid(W.w[c]) == pal["hull"]]
            what = "the skiff's hull"
        elif kind == "chained_lantern":
            ch = [c for c in cells if R.bid(W.w[c]) == pal["chain"]]
            sites = [min(ch, key=lambda c: c[1])] if ch else []
            what = "the chain's foot"
        elif kind == "float_line":
            sites = [c for c in cells if R.bid(W.w[c]) == pal["case"]]
            what = "the field case"
        else:
            P["hooks"].append("%s: a hook kind the audit does not know: %s" % (h["id"], kind))
            continue
        if not sites:
            P["hooks"].append("%s: no site found for its kind %s in %s" % (h["id"], kind, h["lake"]))
            continue
        if not _near(sites, lights, r):
            near = min((max(abs(a - x), abs(b - y), abs(c - z)) for (x, y, z) in sites for (a, b, c) in lights),
                       default=None)
            P["hooks"].append("%s: no light within %d of %s (nearest light %s blocks)" % (h["id"], r, what, near))
    return res


def check_cache(ctx, W, P):
    barrels = [c for c, b in W.w.items() if R.bid(b) == "minecraft:barrel"]
    recs = [r for r in ctx.rewards if r["id"].startswith("lake_life")]
    at = {tuple(r["container"]["at"]): r for r in recs if (r.get("container") or {}).get("at")}
    for c in barrels:
        r = at.get(c)
        if r is None:
            P["cache"].append("the barrel at %s has no data/rewards.json record" % (c,))
            continue
        lo, hi = r["trigger"]["min"], r["trigger"]["max"]
        inside = lambda q: all(lo[i] <= q[i] <= hi[i] for i in range(3))       # noqa: E731
        if not inside(c):
            P["cache"].append("%s's trigger box does not hold its barrel %s" % (r["id"], c))
        nb = [(c[0] + a, c[1] + b, c[2] + d) for a, b, d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1))]
        if not any(inside(q) and R.holds_water(W.at(*q)) for q in nb):
            P["cache"].append("%s's trigger box holds no water cell beside the barrel: no place to swim to it"
                              % r["id"])
    for r in recs:
        c = tuple((r.get("container") or {}).get("at") or ())
        if c not in barrels:
            P["cache"].append("%s's container %s is not a barrel this pack writes" % (r["id"], c))
    return {"barrels": len(barrels), "records": len(recs)}


def check_nonempty(ctx, W, P):
    per = defaultdict(int)
    for cmd, cell, grp, _ in W.landed:
        if grp in SKIN:
            _, lv, body = _cell_body(ctx, cell[0], cell[2])
            if body:
                per[body] += 1
    for k in sorted(ctx.t.bodies):
        if not per.get(k):
            P["nonempty"].append("%s: no skin write lands in it" % k)
    if not ctx.t.bodies:
        P["nonempty"].append("no painted lake to check")
    return {"skin_writes_per_lake": dict(per)}


def check_foreign(ctx, W, P, cols=None):
    """No cell in common with another pack, and no column in common unless every one of our cells there stands over
    a full block that pack wrote as its highest (a sealed roof: the legendaries' chambers and sleeves under a lake
    bed). The sealed columns are counted and reported, not failed."""
    ours = {cell for _c, cell, _g, _p in W.landed} | {cell for _c, cell in W.dead}
    res = {}
    for name in FOREIGN:
        fc = ctx.foreign.get(name)
        if fc is None:
            res[name] = "absent: not checked"
            continue
        cells, sealed, open_ = R.foreign_overlap(ours, fc)
        res[name] = {"cells": len(cells), "columns_over_a_sealed_roof": len(sealed), "columns_open": len(open_)}
        if cells:
            P["foreign"].append("%d columns where we write a cell %s also writes, e.g. %s" % (len(cells), name,
                                                                                            cells[0]))
        if open_:
            P["foreign"].append("%d columns in common with %s not over a sealed roof of it, e.g. %s"
                                % (len(open_), name, sorted(open_)[0]))
    return res


def audit(ctx, pack=PACK):
    P = {k: [] for k in CHECKS}
    fn_dir = Path(pack).joinpath(*FN)
    try:
        parsed, unlisted = R.parse_pack(fn_dir)
    except R.ReplayError as e:
        P["parse"].append(str(e))
        return {"problems": P}
    for u in unlisted:
        P["parse"].append("%s.mcfunction is on disk but not in the index: it never runs" % u)
    tags = lake_tags(pack)
    W = R.World(ctx.t, tags)
    try:
        n = R.replay(W, parsed)
    except R.ReplayError as e:
        P["parse"].append(str(e))
        return {"problems": P}
    res = {"functions": len(parsed), "commands": n, "cells": len(W.w), "dead_writes": len(W.dead),
           "conditional": W.conditional}
    cols = _write_columns(W)
    res["place"] = check_place(ctx, W, P)
    res["plants"] = check_plants(ctx, W, P)
    res["kelp"] = check_kelp(ctx, W, P)
    res["zones"] = check_zones(ctx, W, P)
    res["silt"] = check_silt(ctx, W, parsed, tags, P)
    res["clear"] = check_clear(ctx, W, P, cols)
    res["blocks"] = check_blocks(ctx, W, P)
    res["hooks"] = check_hooks(ctx, W, P)
    res["cache"] = check_cache(ctx, W, P)
    res["nonempty"] = check_nonempty(ctx, W, P)
    res["foreign"] = check_foreign(ctx, W, P, cols)
    for name, _cmds in parsed:
        lines = (fn_dir / (name + ".mcfunction")).read_text(encoding="utf-8").splitlines()
        for pr in FL.check_lines(lines, name)[:3]:
            P["limits"].append(str(pr))
    res["problems"] = P
    return res


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", default=None)
    p.add_argument("--pack", default=str(PACK))
    a = p.parse_args(argv)
    ctx = load_ctx(a.source_root)
    res = audit(ctx, Path(a.pack))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, indent=1, default=str) + "\n")
    probs = [(k, v) for k, lst in res["problems"].items() for v in lst]
    print(json.dumps({k: v for k, v in res.items() if k not in ("problems",)}, default=str)[:1500])
    for k, v in probs[:40]:
        print("PROBLEM [%s] %s" % (k, v))
    print("%d problems -> %s" % (len(probs), OUT.relative_to(ROOT)))
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
