#!/usr/bin/env python
"""The lake skin and the lake hooks: cobblers_lake_life, from data/lake_life.json (docs/mechanics/WATER_LIFE.md sections
1 and 2, which turn WATER_BUILD_PLAN.md 3.3's "Skin (blocks)" list and 4.2's hook table into a build).

Every lake is a body tools/water_mask.bodies() returns. Its columns are the ones paint fills: inside its basin polygons
(rasterised as tools/paint_maps.py does, and checked against water_mask's ray cast at the edge) with round(ground)
below its level. Depth is level - round(ground) on the canonical heightmap (tools/ground.py: the applied water export),
so the zones are read off the applied bed, never restated:

  shelf      1-2 deep      seagrass (2 deep: some tall), lily pads at the surface; sugar cane on the bank beside it
  drop-off   3..drop_depth kelp in patches (top <= level - 3, age 25 so it never grows nearer), gravel and cobble scree
  floor      deeper        mud and clay silt replacing the top bed block only; sunken logs and stumps
  humps      local maxima  boulder piles (top under the surface) and a sunken log beside them
  Marshy     shelf humps   drowned trees: stripped dark oak trunks out of the water, roots on the bed

and the hooks (WATER_LIFE 2), each sited from what it leads to, never from a coordinate restated here: the Viltri
survey buoys, Shrew's torn float, line and field case, the standing stones round Mesprit's mouth, the drowned ring,
soul lantern and boardwalk at Azelf's pit, the gold light off the Weeping Elder island by Uxie's mouth, sunken skiffs
and a chained lantern by the other dive portals. Lights are lanterns, soul lanterns, sea pickles and glow lichen;
never minecraft:light, never a bubble column or what makes one.

Every write carries a filter on what it may replace: `replace minecraft:water` in the water, `replace minecraft:air`
over it, `replace #cobblers:lake_bed` (natural bed blocks, a tag this pack ships) for silt and scree. So nothing another
pack built in a lake is overwritten, whatever list it is or is not on. Sugar cane is guarded by `execute if block` on
vanilla's own soil tags (#minecraft:dirt, #minecraft:sand), because which block paint left on a bank is not known
offline; that guard reads the block, it never decides a position.

Exclusions come from the existing helpers: tools/water_shape.py build_protect (towns and margins, route corridors,
bridges, the Rift, Victory Road, the islet, the built water event sites), tools/portals.py sites (dive arches),
tools/legendaries.py geometry (sleeves, shafts) and the records' spawn_free_zone, tools/water_mask.py sited_claims (jetty
decks), and from data: data/ferries.json stops, data/scenes.json areas, data/route_trainers.json seats,
data/habitat_blocks.json positions, data/foliage.json landmark trees, data/routes.json water crossings, and placements
outside a town footprint. WHAT IT DOES NOT COVER: anything in a lake that no data file names. The write filters are the
guard for that.

  python tools/lake_life.py report  [--source-root DIR]     the model's checks and numbers; nothing written
  python tools/lake_life.py build   [--source-root DIR]     -> build/datapacks/cobblers_lake_life, derived/lake_life/plan.json
  python tools/lake_life.py records [--write]               the field case's data/rewards.json record (print, or
                                                            replace this tool's own lake_life_ records there)

Run order on a world: every function in build/datapacks/cobblers_lake_life/data/cobblers/function/lake_life/index.txt
in order (bed, plants, structure, hooks, lights), after the islet and the legendaries' chambers, before the towns.
The independent offline audit is another hand's (tools/lake_life_audit.py), reading the functions, the heightmap and the
data, never this model.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL   # noqa: E402
import ground as G             # noqa: E402
import legendaries as L        # noqa: E402
import portals as PO           # noqa: E402
import rift_mines as RM        # noqa: E402  (hashing and column runs; not its model)
import terrain as T            # noqa: E402
import water_mask as WM        # noqa: E402
import water_shape as W        # noqa: E402  (its protect mask and raster helpers)

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "lake_life.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_lake_life"
PLAN = ROOT / "derived" / "lake_life" / "plan.json"
REWARDS = ROOT / "data" / "rewards.json"
NS = "cobblers"
FOLDER = "lake_life"
PASSES = ("bed", "plants", "structure", "hooks", "lights")
TILE = 64
PART = 3500
WATER = "minecraft:water"
AIR = "minecraft:air"
BED_TAG = "#%s:lake_bed" % NS
REWARD_PREFIX = "lake_life_"
WORLD_READS = ()          # heightmap and data only; never a world
# the natural blocks a painted lake bed is made of: silt and scree replace only these
LAKE_BED = ["minecraft:sand", "minecraft:red_sand", "minecraft:gravel", "minecraft:clay", "minecraft:dirt",
            "minecraft:coarse_dirt", "minecraft:grass_block", "minecraft:podzol", "minecraft:mud", "minecraft:stone",
            "minecraft:andesite", "minecraft:diorite", "minecraft:granite", "minecraft:tuff", "minecraft:cobblestone",
            "minecraft:mossy_cobblestone", "minecraft:sandstone", "minecraft:deepslate", "minecraft:calcite",
            "minecraft:terracotta", "minecraft:rooted_dirt", "minecraft:moss_block"]
LIGHT_WORDS = ("lantern", "sea_pickle", "glow_lichen")
STATEFUL_WATERLOG = ("lantern", "chain", "slab", "fence", "stairs", "glow_lichen", "sea_pickle")
DIRS = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}

h32, u, pick = RM.h32, RM.u, RM.pick


class LakeLifeError(Exception):
    pass


def load(path=SPEC):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def data(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def h01(X, Z, seed, salt):
    """Per-column hash in [0, 1], vectorised and deterministic (no random, no hash())."""
    return W._hash01(np.asarray(X), np.asarray(Z), (int(seed) * 131 + int(salt)) & 0x7FFFFFFF)


def ray_cast(polys, xs, zs):
    """water_mask.in_polygons, vectorised over points: even-odd per ring, any ring."""
    xs = np.asarray(xs, np.float64)
    zs = np.asarray(zs, np.float64)
    out = np.zeros(xs.shape, bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        for poly in polys:
            c = np.zeros(xs.shape, bool)
            n = len(poly)
            for i in range(n):
                xi, zi = poly[i]
                xj, zj = poly[i - 1]
                cross = (zi > zs) != (zj > zs)
                if zj != zi:
                    c ^= cross & (xs < (xj - xi) * (zs - zi) / float(zj - zi) + xi)
            out |= c
    return out


# ------------------------------------------------------------------ the lakes

class Lake:
    """One painted lake over its basin's box: (z, x) arrays."""

    def __init__(self, bid, body, ground, shape_rec):
        self.id, self.level = bid, int(body["level_y"])
        self.basin = body["basin"]
        if not self.basin:
            raise LakeLifeError("%s: a level but no basin_polygons: nothing is painted there" % bid)
        if shape_rec is None or shape_rec.get("drop_depth") is None:
            raise LakeLifeError("%s: no drop_depth in data/water_shape.json lakes.bodies" % bid)
        self.drop = int(shape_rec["drop_depth"])
        pts = [p for r in self.basin for p in r]
        N = int(ground.heights.shape[0])
        self.box = W.clip_box(min(p[0] for p in pts) - 3, min(p[1] for p in pts) - 3,
                              max(p[0] for p in pts) + 4, max(p[1] for p in pts) + 4, N)
        x0, z0, x1, z1 = self.box
        self.x0, self.z0 = x0, z0
        self.gy = ground.box(x0, z0, x1 - 1, z1 - 1).astype(np.int32)
        inside = W.raster_polygons(self.basin, self.box)
        wet = inside & (self.gy < self.level)
        # paint rasterises; water_mask's point test ray-casts. Where they could disagree (the polygon's edge), a
        # column is wet only if both agree
        edge = wet & W.dilate4(~inside)
        zz, xx = np.nonzero(edge)
        if len(zz):
            ok = ray_cast(self.basin, xx + x0, zz + z0)
            wet[zz[~ok], xx[~ok]] = False
            self.edge_dropped = int((~ok).sum())
        else:
            self.edge_dropped = 0
        self.wet = wet
        self.depth = np.where(wet, self.level - self.gy, 0)
        dry = ~wet
        n4 = np.zeros(wet.shape, bool)
        n4[1:, :] |= wet[:-1, :]
        n4[:-1, :] |= wet[1:, :]
        n4[:, 1:] |= wet[:, :-1]
        n4[:, :-1] |= wet[:, 1:]
        self.bank = dry & (self.gy == self.level) & n4
        self.X = np.arange(x0, x1)[None, :].repeat(z1 - z0, 0)
        self.Z = np.arange(z0, z1)[:, None].repeat(x1 - x0, 1)
        self.excl_hook = np.zeros(wet.shape, bool)
        self.excl_skin = np.zeros(wet.shape, bool)
        self.excl_parts = {}

    def ix(self, x, z):
        return z - self.z0, x - self.x0

    def inbox(self, x, z):
        return self.x0 <= x < self.box[2] and self.z0 <= z < self.box[3]

    def is_wet(self, x, z):
        return self.inbox(x, z) and bool(self.wet[self.ix(x, z)])

    def g(self, x, z):
        return int(self.gy[self.ix(x, z)])

    def d(self, x, z):
        return int(self.depth[self.ix(x, z)]) if self.inbox(x, z) else 0

    def mark(self, part, box_or_mask, hook=True, skin=True):
        """Exclude a world box (x0, z0, x1, z1 inclusive) or a (z, x) mask over this lake's box."""
        if isinstance(box_or_mask, np.ndarray):
            m = box_or_mask
        else:
            bx0, bz0, bx1, bz1 = box_or_mask
            m = np.zeros(self.wet.shape, bool)
            a0, a1 = max(bz0 - self.z0, 0), min(bz1 - self.z0 + 1, m.shape[0])
            b0, b1 = max(bx0 - self.x0, 0), min(bx1 - self.x0 + 1, m.shape[1])
            if a1 <= a0 or b1 <= b0:
                return
            m[a0:a1, b0:b1] = True
        hit = m & (self.wet | self.bank)
        if not hit.any():
            return
        if hook:
            self.excl_hook |= m
        if skin or hook:
            self.excl_skin |= m
        self.excl_parts[part] = self.excl_parts.get(part, 0) + int(hit.sum())

    def free_hook(self, x, z):
        return self.inbox(x, z) and not self.excl_hook[self.ix(x, z)]

    def free_skin(self, x, z):
        return self.inbox(x, z) and not self.excl_skin[self.ix(x, z)]


def protect_mask(source_root):
    """tools/water_shape.py's own protect mask over the whole map (its Ctx, its build_protect), unchanged, built on
    the heightmap it was designed for: data/world.json heightmap.water_shaped_from (= water_shape.json applies_to).

    FINDING (2026-10-02): run on the canonical heightmap instead, build_protect's `rift_sculpt` part (every column
    that differs from the pre-Rift file within 200 of the Rift's box, grown by 8) also takes in every column the
    water export itself changed there, and it protected 85% of Arrow Lake, 49% of Shrew Lake and 97% of the
    Watering Hole. Fed its own input, it protects the Rift's changes only, as it did for the export."""
    from PIL import Image
    wp = ROOT / "data" / "world.json"
    world = T.load_world(wp)
    spec = json.loads(W.SPEC.read_text(encoding="utf-8"))
    hm = T.resolve_heightmap(world, wp, source_root)
    base = world["heightmap"].get("water_shaped_from") or {}
    if base.get("sha256") != spec["applies_to"]["heightmap_sha256"]:
        raise LakeLifeError("data/world.json heightmap.water_shaped_from is not the file data/water_shape.json applies to")
    pre = hm.parent / base["path"]
    if not pre.is_file() or W.sha256_file(pre) != base["sha256"]:
        raise LakeLifeError("%s is missing or does not hash to %s: water_shape's protect mask cannot be rebuilt on its "
                            "own input" % (pre, base["sha256"][:12]))
    raw = np.array(Image.open(pre))
    ctx = W.Ctx(world, spec, raw, raw, pre)
    W.build_protect(ctx)
    return ctx.P, dict(ctx.protect_parts), spec["protect"]


def exclusions(lakes, ground, spec, source_root=None):
    ex = spec["exclusions"]
    P, parts, pspec = protect_mask(source_root)
    for lk in lakes.values():
        lk.mark("water_shape_protect", P[W.sl(lk.box)].copy())
    # the dive portals: the apron the arch stands on, grown by the clearance, every height
    pdoc = PO.load()
    psites = PO.sites(pdoc, ground)
    cl = int(ex["portal_clearance_blocks"]) + PO.APRON_HALF
    portals = {}
    for pid, s in psites.items():
        if s["gate"] != "dive":
            continue
        x, z = s["at"]
        portals[pid] = s
        for lk in lakes.values():
            lk.mark("portal_arches", (x - cl, z - cl, x + cl, z + cl))
    # the legendaries' grottos: shaft + clearance for everything; sleeve footprint and spawn_free_zone for the skin
    ldoc = L.load()
    grottos = {}
    mc = int(ex["mouth_clearance_blocks"])
    for rec in L.emitted(ldoc):
        if rec["kind"] != "lake_grotto":
            continue
        g = L.geometry(rec, ldoc, ground)
        grottos[rec["id"]] = (rec, g)
        sx0, _sy0, sz0, sx1, _sy1, sz1 = g["shaft"]
        sf = g["sleeve_footprint"]
        for lk in lakes.values():
            lk.mark("grotto_mouths", (sx0 - mc, sz0 - mc, sx1 + mc, sz1 + mc))
            lk.mark("grotto_sleeves", tuple(sf), hook=False)
            if rec.get("spawn_free_zone"):
                lk.mark("spawn_free_zones", tuple(rec["spawn_free_zone"]), hook=False)
    # the jetty decks, from water_mask's own model of them
    dm = int(ex["dock_margin_blocks"])
    for label, _body, cols, _sub in WM.sited_claims():
        if not label.startswith("dock "):
            continue
        xs, zs = [c[0] for c in cols], [c[1] for c in cols]
        for lk in lakes.values():
            lk.mark("docks", (min(xs) - dm, min(zs) - dm, max(xs) + dm, max(zs) + dm))
    fm = int(ex["ferry_point_margin_blocks"])
    for d in data("ferries.json")["docks"]:
        pts = [d.get("near"), (d.get("ferryman") or {}).get("at"), (d.get("landing") or {}).get("at")]
        for p in pts:
            if not p:
                continue
            x, z = (p[0], p[1]) if len(p) == 2 else (p[0], p[2])
            for lk in lakes.values():
                lk.mark("ferry_stops", (int(x) - fm, int(z) - fm, int(x) + fm, int(z) + fm))
    sm = int(ex["scene_margin_blocks"])
    for s in data("scenes.json")["scenes"]:
        a = s.get("area")
        if not a or "from" not in a:
            continue
        f, t = a["from"], a["to"]
        for lk in lakes.values():
            lk.mark("scenes", (min(f[0], t[0]) - sm, min(f[2], t[2]) - sm, max(f[0], t[0]) + sm, max(f[2], t[2]) + sm))
    tm = int(ex["seat_margin_blocks"])
    for t in data("route_trainers.json")["trainers"]:
        p = t.get("seat")
        if p:
            for lk in lakes.values():
                lk.mark("trainer_seats", (p[0] - tm, p[2] - tm, p[0] + tm, p[2] + tm))
    hm_ = int(ex["habitat_margin_blocks"])
    for b in data("habitat_blocks.json")["blocks"]:
        p = b.get("position") or {}
        if "x" in p:
            for lk in lakes.values():
                lk.mark("habitat_blocks", (p["x"] - hm_, p["z"] - hm_, p["x"] + hm_, p["z"] + hm_))
    trees = {}
    for t in data("foliage.json").get("landmark_trees", []):
        x, z = t["site"]
        r = int(t.get("glade_radius") or 0)
        trees[t["id"]] = (x, z)
        for lk in lakes.values():
            m = (lk.X - x) ** 2 + (lk.Z - z) ** 2 <= r * r
            lk.mark("landmark_trees", m)
    hw = int(pspec["road_half_width_blocks"])
    lines = []
    for r in data("routes.json")["routes"]:
        for c in r.get("water_crossings") or []:
            lines.append([(c["start"]["x"], c["start"]["z"]), (c["end"]["x"], c["end"]["z"])])
    for lk in lakes.values():
        if lines:
            lk.mark("route_water_crossings", W.raster_lines(lines, lk.box, 2 * hw + 1))
    towns = [t.get("footprint") or {} for t in data("towns.json")["towns"]]
    pm = int(ex["placement_margin_blocks"])
    for q in data("placements.json")["placements"]:
        p = q.get("position") or {}
        if "x" not in p:
            continue
        if any(fp.get("min_x") is not None and fp["min_x"] <= p["x"] <= fp["max_x"] and fp["min_z"] <= p["z"] <= fp["max_z"]
               for fp in towns):
            continue
        for lk in lakes.values():
            lk.mark("placements", (p["x"] - pm, p["z"] - pm, p["x"] + pm, p["z"] + pm))
    return {"portals": portals, "grottos": grottos, "trees": trees, "protect_parts": parts}


# ------------------------------------------------------------------ the model

class Model:
    def __init__(self, spec, ground, source_root=None):
        self.spec, self.ground = spec, ground
        self.seed = int(spec["seed"])
        shape = {b["id"]: b for b in data("water_shape.json")["lakes"]["bodies"]}
        self.lakes = {}
        for bid, body in WM.bodies().items():
            self.lakes[bid] = Lake(bid, body, ground, shape.get(bid))
        self.ctx = exclusions(self.lakes, ground, spec, source_root)
        self.cells = {}            # (x, y, z) -> (block, filter, kind, owner, lake)
        self.canes = []            # (x, soil_y, z, height, lake)
        self.hooks = {}            # id -> {"sites": [(x, y, z)], ...}
        self.counts = {bid: {} for bid in self.lakes}
        self.problems = []
        self.cache = None

    def filt(self, lk, x, y, z):
        g = lk.g(x, z)
        if y == g:
            return "bed"
        if g < y <= lk.level:
            return "water"
        if y > max(g, lk.level):
            return "air"
        return None

    def put(self, lk, x, y, z, block, kind, owner):
        """One write, or False if the cell is taken or cannot be written (below the bed)."""
        if (x, y, z) in self.cells or not lk.inbox(x, z):
            return False
        f = self.filt(lk, x, y, z)
        if f is None:
            return False
        self.cells[(x, y, z)] = (block, f, kind, owner, lk.id)
        c = self.counts[lk.id]
        c[kind] = c.get(kind, 0) + 1
        return True

    def free(self, x, y, z):
        return (x, y, z) not in self.cells


def wl(block, under):
    """A block with its waterlogged state set to where it stands."""
    return "%s[waterlogged=%s]" % (block, "true" if under else "false")


def with_state(block, under, **st):
    st = dict(st)
    st["waterlogged"] = "true" if under else "false"
    return "%s[%s]" % (block, ",".join("%s=%s" % kv for kv in st.items()))


# ------------------------------------------------------------------ the hooks

def near_columns(lk, cx, cz, rmin, rmax, need):
    """[(dist, x, z)] round (cx, cz) in [rmin, rmax], wet, hook-free, passing need(x, z)."""
    out = []
    R = int(math.ceil(rmax))
    for dz in range(-R, R + 1):
        for dx in range(-R, R + 1):
            dd = math.hypot(dx, dz)
            if dd < rmin or dd > rmax:
                continue
            x, z = cx + dx, cz + dz
            if lk.is_wet(x, z) and lk.free_hook(x, z) and need(x, z):
                out.append((dd, x, z))
    return out


def relief(lk, cols):
    gs = [lk.g(x, z) for x, z in cols]
    return max(gs) - min(gs)


def hook_buoys(m, h, lk):
    pal = m.spec["palette"]
    sx, sz = h["from"]
    px, pz = m.ctx["portals"][h["toward"]["portal"]]["at"]
    cells, _step = W.line_cells((sx, sz), (px, pz))
    buoys = []
    since = None
    for i, (x, z) in enumerate(cells):
        if not lk.free_hook(x, z):
            if buoys:              # the portal's clearance: the line stops short of the arch
                break
            continue               # the platform's own site: the line starts outside it
        if not lk.is_wet(x, z) or lk.d(x, z) < int(h["min_depth"]):
            continue
        if since is None or i - since >= int(h["spacing_blocks"]):
            buoys.append((x, z))
            since = i
    if len(buoys) < 2:
        m.problems.append("%s: %d buoys fit between %s and the portal" % (h["id"], len(buoys), h["from"]))
        return
    low = max(buoys, key=lambda c: (lk.d(*c), -abs(c[0] - px) - abs(c[1] - pz)))
    sites = []
    for x, z in buoys:
        g = lk.g(x, z)
        m.put(lk, x, lk.level, z, pal["buoy"], "buoy", h["id"])
        m.put(lk, x, g + 1, z, pal["weight"], "weight", h["id"])
        bottom = g + 2
        if (x, z) == low:
            m.put(lk, x, g + 2, z, with_state(pal["lantern"], True, hanging="false"), "lantern", h["id"])
            bottom = g + 3
            sites.append((x, g + 1, z))
        for y in range(bottom, lk.level):
            m.put(lk, x, y, z, with_state(pal["chain"], True, axis="y"), "chain", h["id"])
    m.hooks[h["id"]] = {"lake": lk.id, "kind": h["kind"], "sites": sites, "buoys": [[x, lk.level, z] for x, z in buoys],
                        "lowest_marker": [low[0], lk.g(*low) + 1, low[1]], "leads_to": h["leads_to"]}


def chain_path(m, lk, a, b, owner):
    """A chain lying on the bed from column a to column b (both exclusive), x then z or z then x, whichever stays clear
    of every exclusion; vertical runs where the bed steps."""
    for order in ("xz", "zx"):
        path, (x, z) = [], a
        legs = ((b[0], None), (None, b[1])) if order == "xz" else ((None, b[1]), (b[0], None))
        for tx, tz in legs:
            while (tx is not None and x != tx) or (tz is not None and z != tz):
                if tx is not None:
                    x += 1 if tx > x else -1
                else:
                    z += 1 if tz > z else -1
                path.append((x, z))
        path = path[:-1]
        if all(lk.is_wet(x, z) and lk.free_hook(x, z) for x, z in path):
            break
    else:
        return None
    prev = a
    pal = m.spec["palette"]
    for (x, z) in path:
        axis = "x" if x != prev[0] else "z"
        g, gp = lk.g(x, z), lk.g(*prev)
        m.put(lk, x, g + 1, z, with_state(pal["chain"], True, axis=axis), "line", owner)
        if gp > g:
            for y in range(g + 2, gp + 2):
                m.put(lk, x, y, z, with_state(pal["chain"], True, axis="y"), "line", owner)
        elif gp < g:
            for y in range(gp + 2, g + 2):
                m.put(lk, prev[0], y, prev[1], with_state(pal["chain"], True, axis="y"), "line", owner)
        prev = (x, z)
    return path


def pickles(m, lk, x, z, n, owner, salt):
    """Up to n sea pickles on the bed round (x, z), within 2."""
    done = 0
    ring = sorted(((dx, dz) for dx in range(-2, 3) for dz in range(-2, 3) if (dx, dz) != (0, 0)),
                  key=lambda o: h32(m.seed, x + o[0], z + o[1], salt))
    for dx, dz in ring:
        if done >= n:
            break
        a, b = x + dx, z + dz
        if not (lk.is_wet(a, b) and lk.free_hook(a, b)):
            continue
        if m.put(lk, a, lk.g(a, b) + 1, b, "minecraft:sea_pickle[pickles=%d,waterlogged=true]" % (2 + h32(m.seed, a, b, salt + 1) % 3),
                 "sea_pickle", owner):
            done += 1
    return done


def hook_float(m, h, lk):
    pal = m.spec["palette"]
    portal = m.ctx["portals"][h["pit"]["portal"]]
    px, pz = portal["at"]
    far = ~W.grow(~lk.wet, int(h["shoal_min_from_dry_blocks"]))
    cand = lk.wet & far & (lk.depth <= int(h["shoal_max_depth"])) & ~lk.excl_hook
    zs, xs = np.nonzero(cand)
    if not len(zs):
        m.problems.append("%s: no shoal %d+ blocks from dry ground and at most %d deep" % (
            h["id"], h["shoal_min_from_dry_blocks"], h["shoal_max_depth"]))
        return
    k = int(np.argmin((xs + lk.x0 - px) ** 2 + (zs + lk.z0 - pz) ** 2))
    fx, fz = int(xs[k] + lk.x0), int(zs[k] + lk.z0)
    lo, hi = h["case_from_portal_blocks"]
    opts = near_columns(lk, px, pz, lo, hi, lambda x, z: all(lk.is_wet(x + a, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1))
                        and relief(lk, [(x + a, z + b) for a in (-1, 0, 1) for b in (-1, 0, 1)]) <= 1)
    if not opts:
        m.problems.append("%s: no flat floor %s from %s for the case" % (h["id"], h["case_from_portal_blocks"], h["pit"]["portal"]))
        return
    _dd, cx, cz = min(opts, key=lambda o: ((o[1] - fx) ** 2 + (o[2] - fz) ** 2, h32(m.seed, o[1], o[2], 71)))
    fg = lk.g(fx, fz)
    m.put(lk, fx, lk.level, fz, pal["float"], "float", h["id"])
    for y in range(fg + 1, lk.level):
        m.put(lk, fx, y, fz, with_state(pal["chain"], True, axis="y"), "line", h["id"])
    path = chain_path(m, lk, (fx, fz), (cx, cz), h["id"])
    if path is None:
        m.problems.append("%s: no clear line from the float (%d, %d) to the case (%d, %d)" % (h["id"], fx, fz, cx, cz))
        return
    cg = lk.g(cx, cz)
    m.put(lk, cx, cg + 1, cz, pal["case"] + "[facing=up,open=false]", "case", h["id"])
    n1 = pickles(m, lk, fx, fz, 3, h["id"], 81)
    lamp = None
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        a, b = cx + dx, cz + dz
        if lk.is_wet(a, b) and lk.free_hook(a, b) and m.free(a, lk.g(a, b) + 1, b):
            if m.put(lk, a, lk.g(a, b) + 1, b, with_state(pal["lantern"], True, hanging="false"), "lantern", h["id"]):
                lamp = (a, lk.g(a, b) + 1, b)
                break
    if not n1 or lamp is None:
        m.problems.append("%s: the float or the case has no light beside it" % h["id"])
    m.cache = {"hook": h, "at": (cx, cg + 1, cz)}
    m.hooks[h["id"]] = {"lake": lk.id, "kind": h["kind"], "sites": [(fx, lk.level, fz), (cx, cg + 1, cz)],
                        "float": [fx, lk.level, fz], "float_depth": int(lk.d(fx, fz)), "case": [cx, cg + 1, cz],
                        "case_depth": int(lk.d(cx, cz)), "line_columns": len(path), "leads_to": h["leads_to"]}


def hook_stones(m, h, lk):
    pal = m.spec["palette"]
    rec, g = m.ctx["grottos"][h["around"]["legendary"]]
    mx, mz = g["anchor"]
    n, R = int(h["stones"]), float(h["radius"])
    lo, hi = h["height"]
    stones = []
    for k in range(n):
        a = 2 * math.pi * k / n + (u(m.seed, k, 91) - 0.5) * 0.3
        x, z = mx + RM.rnd(R * math.cos(a)), mz + RM.rnd(R * math.sin(a))
        tx, tz = -math.sin(a), math.cos(a)
        t = (1, 0) if abs(tx) >= abs(tz) else (0, 1)
        hgt = lo + h32(m.seed, x, z, 92) % (hi - lo + 1)
        inward = (int(np.sign(mx - x)), 0) if abs(mx - x) >= abs(mz - z) else (0, int(np.sign(mz - z)))
        for j, (cx, cz) in enumerate(((x, z), (x + t[0], z + t[1]))):
            if not (lk.is_wet(cx, cz) and lk.free_hook(cx, cz)):
                m.problems.append("%s: stone %d column (%d, %d) is dry or excluded" % (h["id"], k, cx, cz))
                continue
            cg = lk.g(cx, cz)
            top = min(cg + hgt - j, lk.level - 2)
            for y in range(cg + 1, top + 1):
                m.put(lk, cx, y, cz, pick(pal["standing_stones"], m.seed, cx, y, cz, 93), "standing_stone", h["id"])
            if j == 0:
                # glow lichen on the stone's inner face, half way up
                lx, lz = cx + inward[0], cz + inward[1]
                y = cg + 1 + (top - cg) // 2
                face = DIRS[(-inward[0], -inward[1])]
                if lk.is_wet(lx, lz) and lk.free_hook(lx, lz) and lk.g(lx, lz) < y <= lk.level:
                    m.put(lk, lx, y, lz, "minecraft:glow_lichen[%s=true,waterlogged=true]" % face, "glow_lichen", h["id"])
        stones.append([x, z, hgt])
    inner = []
    for k in range(int(h["inner_lanterns"])):
        a = 2 * math.pi * (k + 0.5) / int(h["inner_lanterns"])
        x = mx + RM.rnd(h["inner_lantern_radius"] * math.cos(a))
        z = mz + RM.rnd(h["inner_lantern_radius"] * math.sin(a))
        if lk.is_wet(x, z) and lk.free_hook(x, z):
            if m.put(lk, x, lk.g(x, z) + 1, z, with_state(pal["lantern"], True, hanging="false"), "lantern", h["id"]):
                inner.append([x, lk.g(x, z) + 1, z])
    m.hooks[h["id"]] = {"lake": lk.id, "kind": h["kind"], "sites": [(mx, g["mouth_y"], mz)], "mouth": [mx, g["mouth_y"], mz],
                        "mouth_depth": lk.level - g["mouth_y"], "stones": stones, "inner_lanterns": inner,
                        "leads_to": h["leads_to"]}


def drowned_tree(m, lk, x, z, above, owner, kind, roots_skip=()):
    """A dead stripped trunk from the bed to `above` over the surface, roots on the bed round it."""
    blk = m.spec["skin"]["drowned_trees"]["trunk"]
    g = lk.g(x, z)
    for y in range(g + 1, lk.level + above + 1):
        m.put(lk, x, y, z, blk + "[axis=y]", kind, owner)
    for (dx, dz) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if (dx, dz) in roots_skip:
            continue
        for s in (1, 2):
            if s == 2 and h32(m.seed, x, z, dx, dz, 101) % 2:
                break
            a, b = x + dx * s, z + dz * s
            if not (lk.is_wet(a, b) and lk.free_skin(a, b) if kind == "drowned_tree" else lk.is_wet(a, b) and lk.free_hook(a, b)):
                break
            m.put(lk, a, lk.g(a, b) + 1, b, blk + "[axis=%s]" % ("x" if dx else "z"), kind + "_root", owner)
    # a dead branch stub over the water
    dx, dz = ((1, 0), (-1, 0), (0, 1), (0, -1))[h32(m.seed, x, z, 102) % 4]
    a, b = x + dx, z + dz
    free = lk.free_skin(a, b) if kind == "drowned_tree" else lk.free_hook(a, b)
    if lk.is_wet(a, b) and free and above >= 3:
        m.put(lk, a, lk.level + above - 1, b, blk + "[axis=%s]" % ("x" if dx else "z"), kind, owner)


def hook_ring(m, h, lk):
    pal = m.spec["palette"]
    rec, g = m.ctx["grottos"][h["around"]["legendary"]]
    mx, mz = g["anchor"]
    n = int(h["trees"])
    lo, hi = h["above_water"]
    trees = []
    for k in range(n):
        a = 2 * math.pi * k / n + (u(m.seed, k, 111) - 0.5) * 0.4
        for s in range(1, int(h["max_reach_blocks"]) + 1):
            x, z = mx + RM.rnd(s * math.cos(a)), mz + RM.rnd(s * math.sin(a))
            if not lk.is_wet(x, z):
                break
            if lk.d(x, z) <= int(h["rim_max_depth"]):
                if lk.free_hook(x, z):
                    trees.append((s, x, z, a))
                break
    if len(trees) < int(h["min_trees"]):
        m.problems.append("%s: %d trees found the pit's rim (min %d)" % (h["id"], len(trees), h["min_trees"]))
        return
    near = min(trees, key=lambda t: t[0])
    out = []
    for s, x, z, a in trees:
        above = lo + h32(m.seed, x, z, 112) % (hi - lo + 1)
        inward = (int(np.sign(mx - x)), 0) if abs(mx - x) >= abs(mz - z) else (0, int(np.sign(mz - z)))
        skip = (inward,) if (x, z) == near[1:3] else ()
        drowned_tree(m, lk, x, z, above, h["id"], "ring_tree", roots_skip=skip)
        out.append([x, lk.g(x, z) + 1, z, above])
    # the soul lantern in the near tree's roots, on its pit side, and the boardwalk from there down to the mouth
    _s, tx, tz, _a = near
    inward = (int(np.sign(mx - tx)), 0) if abs(mx - tx) >= abs(mz - tz) else (0, int(np.sign(mz - tz)))
    lx, lz = tx + inward[0], tz + inward[1]
    soul = None
    if lk.is_wet(lx, lz) and lk.free_hook(lx, lz):
        if m.put(lk, lx, lk.g(lx, lz) + 1, lz, with_state(pal["soul_lantern"], True, hanging="false"), "soul_lantern", h["id"]):
            soul = (lx, lk.g(lx, lz) + 1, lz)
    if soul is None:
        m.problems.append("%s: no soul lantern in the near tree's roots" % h["id"])
        return
    start = (tx + 2 * inward[0], tz + 2 * inward[1])
    cells, _st = W.line_cells(start, (mx, mz))
    ddx, ddz = mx - start[0], mz - start[1]
    side = (0, 1) if abs(ddx) >= abs(ddz) else (1, 0)
    walk = []
    for (x, z) in cells:
        if not lk.free_hook(x, z) or not lk.free_hook(x + side[0], z + side[1]):
            break
        walk.append((x, z))
    if len(walk) < 4:
        m.problems.append("%s: the boardwalk from (%d, %d) reaches %d columns" % (h["id"], start[0], start[1], len(walk)))
        return
    slab = with_state(pal["boardwalk"], True, type="bottom")
    lights = []
    for i, (x, z) in enumerate(walk):
        for (a, b) in ((x, z), (x + side[0], z + side[1])):
            if lk.is_wet(a, b):
                m.put(lk, a, lk.g(a, b) + 1, b, slab, "boardwalk", h["id"])
        last = i == len(walk) - 1
        if i % int(h["boardwalk_post_every"]) == 0 or last:
            a, b = x - side[0], z - side[1]
            if lk.is_wet(a, b) and lk.free_hook(a, b):
                pg = lk.g(a, b)
                post = with_state(pal["post"], True)
                m.put(lk, a, pg + 1, b, post, "boardwalk_post", h["id"])
                m.put(lk, a, pg + 2, b, post, "boardwalk_post", h["id"])
                if (i % int(h["boardwalk_light_every"]) == 0 or last) and pg + 3 <= lk.level:
                    if m.put(lk, a, pg + 3, b, with_state(pal["soul_lantern"], True, hanging="false"), "soul_lantern", h["id"]):
                        lights.append([a, pg + 3, b])
    end = walk[-1]
    m.hooks[h["id"]] = {"lake": lk.id, "kind": h["kind"],
                        "sites": [(tx, lk.g(tx, tz) + 1, tz), (end[0], lk.g(*end) + 1, end[1])],
                        "trees": out, "soul_lantern": list(soul), "boardwalk": {"from": list(start), "to": list(end),
                                                                                 "columns": len(walk), "lights": lights},
                        "mouth": [mx, g["mouth_y"], mz], "leads_to": h["leads_to"]}


def hook_gold(m, h, lk):
    pal = m.spec["palette"]
    rec, g = m.ctx["grottos"][h["near"]["legendary"]]
    mx, mz = g["anchor"]
    ex, ez = m.ctx["trees"][h["away_from"]["landmark_tree"]]
    dd = math.hypot(ex - mx, ez - mz)
    x = mx - RM.rnd(h["distance"] * (ex - mx) / dd)        # past the mouth, on the deep side of the apron's foot
    z = mz - RM.rnd(h["distance"] * (ez - mz) / dd)
    if not (lk.is_wet(x, z) and lk.free_hook(x, z)):
        m.problems.append("%s: (%d, %d) is dry or excluded" % (h["id"], x, z))
        return
    cg = lk.g(x, z)
    if lk.level - cg < 5:
        m.problems.append("%s: (%d, %d) is only %d deep" % (h["id"], x, z, lk.level - cg))
        return
    for y in (cg + 1, cg + 2):
        m.put(lk, x, y, z, pick(pal["cairn"], m.seed, x, y, z, 121), "cairn", h["id"])
    m.put(lk, x, cg + 3, z, with_state(pal["lantern"], True, hanging="false"), "lantern", h["id"])
    n = pickles(m, lk, x, z, 4, h["id"], 122)
    m.hooks[h["id"]] = {"lake": lk.id, "kind": h["kind"], "sites": [(x, cg + 3, z)], "light": [x, cg + 3, z],
                        "depth": lk.level - (cg + 3), "pickles": n, "mouth": [mx, g["mouth_y"], mz], "leads_to": h["leads_to"]}


def hook_skiff(m, h, lk):
    pal = m.spec["palette"]
    px, pz = m.ctx["portals"][h["near"]["portal"]]["at"]
    lo, hi = h["distance"]
    best = None
    for dd, x, z in near_columns(lk, px, pz, lo, hi, lambda x, z: True):
        for axis in ((1, 0), (0, 1)):
            side = (axis[1], axis[0])
            cols = [(x + axis[0] * i + side[0] * j, z + axis[1] * i + side[1] * j) for i in range(-3, 4) for j in (-1, 0, 1)]
            if not all(lk.is_wet(a, b) and lk.free_hook(a, b) and lk.d(a, b) >= 4 for a, b in cols):
                continue
            r = relief(lk, cols)
            if r > 2:
                continue
            key = (r, dd, h32(m.seed, x, z, axis[0], 131))
            if best is None or key < best[0]:
                best = (key, x, z, axis, cols)
    if best is None:
        m.problems.append("%s: no flat 3 by 7 floor %s from %s" % (h["id"], h["distance"], h["near"]["portal"]))
        return
    _k, x, z, axis, cols = best
    side = (axis[1], axis[0])
    y = max(lk.g(a, b) for a, b in cols) + 1
    hull, gun = pal["hull"], with_state(pal["gunwale"], True, type="bottom")
    for i in range(-3, 4):
        for j in (-1, 0, 1):
            a, b = x + axis[0] * i + side[0] * j, z + axis[1] * i + side[1] * j
            if j == 0 or abs(i) <= 2:
                m.put(lk, a, y, b, hull, "skiff", h["id"])
            if j != 0 and abs(i) <= 2:
                m.put(lk, a, y + 1, b, gun, "skiff", h["id"])
    a, b = x - axis[0], z - axis[1]
    m.put(lk, a, y + 1, b, gun, "skiff", h["id"])                       # the thwart
    a, b = x + axis[0], z + axis[1]
    m.put(lk, a, y + 1, b, with_state(pal["lantern"], True, hanging="false"), "lantern", h["id"])
    m.hooks[h["id"]] = {"lake": lk.id, "kind": h["kind"], "sites": [(a, y + 1, b)], "light": [a, y + 1, b],
                        "skiff_centre": [x, y, z], "axis": "x" if axis[0] else "z", "top_depth": lk.level - (y + 1),
                        "leads_to": h["leads_to"]}


def hook_chained(m, h, lk):
    pal = m.spec["palette"]
    px, pz = m.ctx["portals"][h["near"]["portal"]]["at"]
    lo, hi = h["distance"]
    af = int(h["above_floor"])
    opts = near_columns(lk, px, pz, lo, hi, lambda x, z: lk.d(x, z) >= af + 4)
    if not opts:
        m.problems.append("%s: no column %s from %s deep enough" % (h["id"], h["distance"], h["near"]["portal"]))
        return
    dd, x, z = min(opts, key=lambda o: (o[0], h32(m.seed, o[1], o[2], 141)))
    g = lk.g(x, z)
    ly = g + af
    m.put(lk, x, lk.level, z, pal["buoy"], "buoy", h["id"])
    for y in range(ly + 1, lk.level):
        m.put(lk, x, y, z, with_state(pal["chain"], True, axis="y"), "chain", h["id"])
    m.put(lk, x, ly, z, with_state(pal["lantern"], True, hanging="true"), "lantern", h["id"])
    m.hooks[h["id"]] = {"lake": lk.id, "kind": h["kind"], "sites": [(x, ly, z)], "light": [x, ly, z],
                        "depth": lk.level - ly, "floor_y": g, "leads_to": h["leads_to"]}


HOOKS = {"buoy_line": hook_buoys, "float_line": hook_float, "stone_ring": hook_stones, "drowned_ring": hook_ring,
         "gold_light": hook_gold, "skiff": hook_skiff, "chained_lantern": hook_chained}


# ------------------------------------------------------------------ the skin

def humps(m, lk, R, prom, spacing, maxn, mask, salt):
    """Local maxima of the bed: [(x, z)], greedy by prominence then hash, spaced."""
    A = np.where(lk.wet, lk.gy, -1000).astype(np.float64)
    M = W.running_max2d(A, R)
    mn = -W.running_max2d(-lk.gy.astype(np.float64), R + 3)
    cand = mask & lk.wet & (A == M) & ((lk.gy - mn) >= prom) & ~lk.excl_skin
    zs, xs = np.nonzero(cand)
    order = sorted(range(len(zs)), key=lambda i: (-(int(lk.gy[zs[i], xs[i]]) - int(mn[zs[i], xs[i]])),
                                                  h32(m.seed, int(xs[i]), int(zs[i]), salt)))
    out = []
    for i in order:
        x, z = int(xs[i] + lk.x0), int(zs[i] + lk.z0)
        if all((x - a) ** 2 + (z - b) ** 2 >= spacing * spacing for a, b in out):
            out.append((x, z))
            if len(out) >= maxn:
                break
    return out


def lay_log(m, lk, x, z, axis, n, blocks, owner, kind, need):
    cols = [(x + axis[0] * i, z + axis[1] * i) for i in range(n)]
    if not all(lk.is_wet(a, b) and lk.free_skin(a, b) and need(a, b) for a, b in cols):
        return False
    if relief(lk, cols) > int(m.spec["skin"]["logs"]["max_relief"]):
        return False
    y = max(lk.g(a, b) for a, b in cols) + 1
    if y > lk.level - 1 or not all(m.free(a, y, b) for a, b in cols):
        return False
    blk = pick(blocks, m.seed, x, z, 151) + "[axis=%s]" % ("x" if axis[0] else "z")
    for a, b in cols:
        m.put(lk, a, y, b, blk, kind, owner)
    return True


def skin(m, lk):
    sk = m.spec["skin"]
    s = m.seed
    X, Z = lk.X, lk.Z
    ok = lk.wet & ~lk.excl_skin
    d = lk.depth
    shelf = ok & (d >= 1) & (d <= 2)
    drop = ok & (d >= int(m.spec["zones"]["drop_from_depth"])) & (d <= lk.drop)
    floor = ok & (d > lk.drop)
    # structure first, so the plants grow round it
    # drowned trees on Marshy Marsh's shelf humps
    dt = sk["drowned_trees"]
    if lk.id == dt["lake"]:
        far = ~W.grow(~lk.wet, int(dt["min_from_dry_blocks"]))
        tops = humps(m, lk, int(dt["hump_radius_blocks"]), 1, int(dt["min_spacing_blocks"]), int(dt["max"]),
                     far & (d == 1), 161)
        lo, hi = dt["above_water"]
        for x, z in tops:
            drowned_tree(m, lk, x, z, lo + h32(s, x, z, 162) % (hi - lo + 1), "skin", "drowned_tree")
        lk.drowned = tops
    else:
        lk.drowned = []
    # boulder piles on the humps and shoals
    bo = sk["boulders"]
    lk.piles = humps(m, lk, int(bo["hump_radius_blocks"]), int(bo["prominence_blocks"]), int(bo["min_spacing_blocks"]),
                     int(bo["max_per_lake"]), d >= 2, 171)
    pr = int(bo["pile_radius"])
    for x, z in lk.piles:
        for dz in range(-pr, pr + 1):
            for dx in range(-pr, pr + 1):
                r = math.hypot(dx, dz) + 0.8 * (u(s, x + dx, z + dz, 172) - 0.5)
                if r > pr + 0.3:
                    continue
                a, b = x + dx, z + dz
                if not (lk.is_wet(a, b) and lk.free_skin(a, b)):
                    continue
                g = lk.g(a, b)
                hgt = 2 if r < 0.9 else 1
                for y in range(g + 1, min(g + hgt, lk.level - 1) + 1):
                    m.put(lk, a, y, b, pick(bo["blocks"], s, a, y, b, 173), "boulder", "skin")
        axis = ((1, 0), (0, 1))[h32(s, x, z, 174) % 2]
        sgn = 1 if h32(s, x, z, 175) % 2 else -1
        lay_log(m, lk, x + sgn * axis[1] * (pr + 2), z + sgn * axis[0] * (pr + 2), axis, 3, sk["logs"]["blocks"], "skin",
                "sunken_log", lambda a, b: lk.d(a, b) >= 2)
    # sunken logs and stumps on the floor
    lg = sk["logs"]
    zs, xs = np.nonzero(floor & (h01(X, Z, s, 181) < 1.0 / float(lg["per_floor_columns"])))
    for i in range(len(zs)):
        x, z = int(xs[i] + lk.x0), int(zs[i] + lk.z0)
        axis = ((1, 0), (0, 1))[h32(s, x, z, 182) % 2]
        n = lg["length"][0] + h32(s, x, z, 183) % (lg["length"][1] - lg["length"][0] + 1)
        lay_log(m, lk, x, z, axis, n, lg["blocks"], "skin", "sunken_log", lambda a, b: lk.d(a, b) > lk.drop)
    zs, xs = np.nonzero(floor & (h01(X, Z, s, 184) < 1.0 / float(lg["stumps_per_floor_columns"])))
    for i in range(len(zs)):
        x, z = int(xs[i] + lk.x0), int(zs[i] + lk.z0)
        g = lk.g(x, z)
        blk = pick(lg["blocks"], s, x, z, 185) + "[axis=y]"
        for y in range(g + 1, g + 2 + h32(s, x, z, 186) % 2):
            m.put(lk, x, y, z, blk, "stump", "skin")
    # kelp in patches in the drop-off band
    kp = sk["kelp"]
    nk = W.value_noise(X, Z, kp["patch_scale_blocks"], s + 1)
    zs, xs = np.nonzero(drop & (nk > kp["patch_threshold"]) & (h01(X, Z, s, 191) < kp["share_in_patch"]))
    tb = int(kp["top_below_surface"])
    for i in range(len(zs)):
        x, z = int(xs[i] + lk.x0), int(zs[i] + lk.z0)
        g = lk.g(x, z)
        room = lk.level - tb - g
        if room < 1:
            continue
        hgt = 1 + h32(s, x, z, 192) % min(room, int(kp["max_height"]))
        top = g + hgt
        if not all(m.free(x, y, z) for y in range(g + 1, top + 1)):
            continue
        for y in range(g + 1, top):
            m.put(lk, x, y, z, "minecraft:kelp_plant", "kelp", "skin")
        m.put(lk, x, top, z, "minecraft:kelp[age=25]", "kelp", "skin")
    # seagrass on the shelf, some tall where it is 2 deep
    sg = sk["seagrass"]
    ns = W.value_noise(X, Z, sg["patch_scale_blocks"], s + 2)
    zs, xs = np.nonzero(shelf & (ns > sg["patch_threshold"]) & (h01(X, Z, s, 201) < sg["share_in_patch"]))
    for i in range(len(zs)):
        x, z = int(xs[i] + lk.x0), int(zs[i] + lk.z0)
        g = lk.g(x, z)
        if not m.free(x, g + 1, z):
            continue
        if lk.level - g >= 2 and u(s, x, z, 202) < sg["tall_share_at_depth_2"] and m.free(x, g + 2, z):
            m.put(lk, x, g + 1, z, "minecraft:tall_seagrass[half=lower]", "tall_seagrass", "skin")
            m.put(lk, x, g + 2, z, "minecraft:tall_seagrass[half=upper]", "tall_seagrass", "skin")
        else:
            m.put(lk, x, g + 1, z, "minecraft:seagrass", "seagrass", "skin")
    # lily pads over the shelf
    lp = sk["lily_pad"]
    nl = W.value_noise(X, Z, lp["patch_scale_blocks"], s + 3)
    zs, xs = np.nonzero(shelf & (nl > lp["patch_threshold"]) & (h01(X, Z, s, 211) < lp["share_in_patch"]))
    for i in range(len(zs)):
        x, z = int(xs[i] + lk.x0), int(zs[i] + lk.z0)
        if m.free(x, lk.level, z):          # never over a tall seagrass's top or a structure at the surface
            m.put(lk, x, lk.level + 1, z, "minecraft:lily_pad", "lily_pad", "skin")
    # reeds on the bank
    rd = sk["reeds"]
    nr = W.value_noise(X, Z, rd["patch_scale_blocks"], s + 4)
    zs, xs = np.nonzero(lk.bank & ~lk.excl_skin & (nr > rd["patch_threshold"]) & (h01(X, Z, s, 221) < rd["share"]))
    for i in range(len(zs)):
        x, z = int(xs[i] + lk.x0), int(zs[i] + lk.z0)
        if not m.free(x, lk.level + 1, z):
            continue
        hgt = rd["height"][0] + h32(s, x, z, 222) % (rd["height"][1] - rd["height"][0] + 1)
        m.canes.append((x, lk.level, z, hgt, lk.id))
        for y in range(lk.level + 1, lk.level + hgt + 1):
            m.cells[(x, y, z)] = ("minecraft:sugar_cane", "air", "reeds", "skin", lk.id)
        c = m.counts[lk.id]
        c["reeds"] = c.get("reeds", 0) + 1
    # the bed: scree in the drop-off band, silt on the floor, the top bed block only
    sc = sk["scree"]
    zs, xs = np.nonzero(drop & (h01(X, Z, s, 231) < sc["share"]))
    for i in range(len(zs)):
        x, z = int(xs[i] + lk.x0), int(zs[i] + lk.z0)
        m.put(lk, x, lk.g(x, z), z, pick(sc["blocks"], s, x, z, 232), "scree", "skin")
    st = sk["silt"]
    nsi = W.value_noise(X, Z, st["patch_scale_blocks"], s + 5)
    kind = W.value_noise(X, Z, st["kind_scale_blocks"], s + 6)
    zs, xs = np.nonzero(floor & (nsi > st["patch_threshold"]))
    for i in range(len(zs)):
        x, z = int(xs[i] + lk.x0), int(zs[i] + lk.z0)
        b = st["blocks"][0] if kind[zs[i], xs[i]] < 0.5 else st["blocks"][1]
        m.put(lk, x, lk.g(x, z), z, b, "silt", "skin")


# ------------------------------------------------------------------ checks

def is_light(b):
    return any(w in b for w in LIGHT_WORDS)


KELP_TOP_BELOW = 3     # WATER_LIFE 1 "never within 2 of the surface": the top block at most level - 3
LIGHT_WITHIN = 8       # WATER_BUILD_PLAN 4.5 audit 2: a light within 8 blocks of every hook's site
FORBIDDEN = {"minecraft:light", "minecraft:bubble_column", "minecraft:soul_sand", "minecraft:magma_block"}


def checks(m):
    """Fail closed. The limits are this module's constants from the spec's text, not the data the build read, so a
    looser number in data/lake_life.json is caught rather than obeyed."""
    p = []
    spec = m.spec
    forbidden = FORBIDDEN | set(spec["lights"]["forbidden"])
    within = min(LIGHT_WITHIN, int(spec["lights"]["within_blocks"]))
    lights = [(x, y, z) for (x, y, z), v in m.cells.items() if is_light(v[0])]
    for (x, y, z), (b, f, kind, owner, lid) in m.cells.items():
        lk = m.lakes[lid]
        base = b.split("[")[0]
        if base in forbidden:
            p.append("(%d, %d, %d): %s is forbidden" % (x, y, z, base))
        wet, bank = lk.is_wet(x, z), lk.inbox(x, z) and bool(lk.bank[lk.ix(x, z)])
        if not (wet or bank):
            p.append("%s (%d, %d, %d) %s: not in a lake column or on its bank" % (lid, x, y, z, kind))
            continue
        excl = lk.excl_skin if owner == "skin" else lk.excl_hook
        if excl[lk.ix(x, z)]:
            p.append("%s (%d, %d, %d) %s by %s: inside an exclusion" % (lid, x, y, z, kind, owner))
        g = lk.g(x, z)
        if y < g:
            p.append("%s (%d, %d, %d) %s: under the bed" % (lid, x, y, z, kind))
        if y == g and (kind not in ("silt", "scree") or not wet):
            p.append("%s (%d, %d, %d) %s: replaces the bed but is not silt or scree" % (lid, x, y, z, kind))
        if kind in ("silt", "scree") and (y != g or base not in ("minecraft:mud", "minecraft:clay", "minecraft:gravel",
                                                                  "minecraft:cobblestone")):
            p.append("%s (%d, %d, %d): %s is not a full block on the top bed block (a height change)" % (lid, x, y, z, kind))
        under = wet and g < y <= lk.level
        if any(w in base for w in STATEFUL_WATERLOG) and "waterlogged=%s" % ("true" if under else "false") not in b:
            p.append("%s (%d, %d, %d) %s: waterlogged state disagrees with the water (%s)" % (lid, x, y, z, kind, b))
        if base in ("minecraft:seagrass", "minecraft:tall_seagrass", "minecraft:kelp", "minecraft:kelp_plant"):
            if not under:
                p.append("%s (%d, %d, %d) %s: not in water" % (lid, x, y, z, base))
            below = m.cells.get((x, y - 1, z))
            ok = y - 1 == g or (below is not None and (
                (base == "minecraft:tall_seagrass" and "half=upper" in b and "half=lower" in below[0]) or
                (base in ("minecraft:kelp", "minecraft:kelp_plant") and below[0] == "minecraft:kelp_plant")))
            if base == "minecraft:tall_seagrass" and "half=lower" in b and m.cells.get((x, y + 1, z), ("",))[0] != \
                    "minecraft:tall_seagrass[half=upper]":
                ok = False
            if not ok:
                p.append("%s (%d, %d, %d) %s: no solid support under it" % (lid, x, y, z, base))
            if base == "minecraft:kelp" and (y > lk.level - KELP_TOP_BELOW or "age=25" not in b):
                p.append("%s (%d, %d, %d): kelp top at %d deep or able to grow" % (lid, x, y, z, lk.level - y))
            if base == "minecraft:kelp_plant" and m.cells.get((x, y + 1, z), ("",))[0].split("[")[0] not in (
                    "minecraft:kelp", "minecraft:kelp_plant"):
                p.append("%s (%d, %d, %d): a kelp stem with no kelp over it" % (lid, x, y, z))
        if base == "minecraft:lily_pad" and (y != lk.level + 1 or not wet or (x, lk.level, z) in m.cells):
            p.append("%s (%d, %d, %d): a lily pad not on open surface water" % (lid, x, y, z))
        if base == "minecraft:sugar_cane" and not bank:
            p.append("%s (%d, %d, %d): sugar cane off the bank" % (lid, x, y, z))
        if wet and y > lk.level + 1 and kind not in ("drowned_tree", "ring_tree"):
            p.append("%s (%d, %d, %d) %s: stands over the water" % (lid, x, y, z, kind))
    for (x, sy, z, hgt, lid) in m.canes:
        lk = m.lakes[lid]
        if not lk.bank[lk.ix(x, z)] or sy != lk.g(x, z) or sy != lk.level:
            p.append("%s (%d, %d): a cane soil that is not a bank block level with the water" % (lid, x, z))
    for bid, lk in m.lakes.items():
        c = m.counts[bid]
        if not sum(v for k, v in c.items()):
            p.append("%s: no writes at all" % bid)
        for need in ("seagrass", "silt"):
            if not c.get(need):
                p.append("%s: no %s" % (bid, need))
    hooked = {h["lake"] for h in m.hooks.values()}
    for h in spec["hooks"]:
        if h["id"] not in m.hooks:
            p.append("hook %s was not built" % h["id"])
            continue
        for (x, y, z) in m.hooks[h["id"]]["sites"]:
            if not any(abs(a - x) <= within and abs(b - y) <= within and abs(c - z) <= within for a, b, c in lights):
                p.append("hook %s: no light within %d of its site (%d, %d, %d)" % (h["id"], within, x, y, z))
    for lid in ("lake_viltri", "shrew_lake", "arrow_lake", "marshy_marsh", "lake_tilpey", "peak_pond", "watering_hole",
                "ravine_head_tarn"):
        if lid in m.lakes and lid not in hooked:
            p.append("%s: WATER_LIFE 2 names a hook for it and none was built" % lid)
    # no write blocks a grotto mouth or a dive line: the shaft's columns and the apron's, every height
    for rid, (rec, g) in m.ctx["grottos"].items():
        sx0, _a, sz0, sx1, _b, sz1 = g["shaft"]
        for (x, y, z) in m.cells:
            if sx0 - 1 <= x <= sx1 + 1 and sz0 - 1 <= z <= sz1 + 1:
                p.append("%s: a write at (%d, %d, %d) over its mouth" % (rid, x, y, z))
                break
    for pid, s in m.ctx["portals"].items():
        x0, z0 = s["at"][0] - PO.APRON_HALF, s["at"][1] - PO.APRON_HALF
        for (x, y, z) in m.cells:
            if x0 <= x <= x0 + 4 and z0 <= z <= z0 + 4:
                p.append("%s: a write at (%d, %d, %d) over its arch" % (pid, x, y, z))
                break
    m.problems += p
    return m.problems


# ------------------------------------------------------------------ the pack

def runs(cells):
    """[(x0, y0, z0, x1, y1, z1, block, filter)]: vertical runs first, then runs along x inside a tile."""
    cols = {}
    for (x, y, z), (b, f) in cells.items():
        cols.setdefault((x, z, b, f), []).append(y)
    out, single = [], {}
    for (x, z, b, f), ys in cols.items():
        ys.sort()
        i = 0
        while i < len(ys):
            j = i
            while j + 1 < len(ys) and ys[j + 1] == ys[j] + 1:
                j += 1
            if j > i:
                out.append((x, ys[i], z, x, ys[j], z, b, f))
            else:
                single.setdefault((ys[i], z, b, f), []).append(x)
            i = j + 1
    for (y, z, b, f), xs in single.items():
        xs.sort()
        i = 0
        while i < len(xs):
            j = i
            while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1 and xs[j + 1] // TILE == xs[i] // TILE:
                j += 1
            out.append((xs[i], y, z, xs[j], y, z, b, f))
            i = j + 1
    return out


FILTER = {"water": WATER, "air": AIR, "bed": BED_TAG}


def pass_of(b, kind):
    if is_light(b):
        return "lights"
    if kind in ("silt", "scree"):
        return "bed"
    if kind in ("seagrass", "tall_seagrass", "kelp", "lily_pad", "reeds"):
        return "plants"
    if kind in ("sunken_log", "stump", "boulder", "drowned_tree", "drowned_tree_root"):
        return "structure"
    return "hooks"


def lines(m):
    per = {p: {} for p in PASSES}
    for (x, y, z), (b, f, kind, _o, _l) in m.cells.items():
        if kind == "reeds":
            continue
        per[pass_of(b, kind)][(x, y, z)] = (b, f)
    out = {p: [] for p in PASSES}
    for p in PASSES:
        rs = runs(per[p])
        # bottom first: a stem before its head, a support before what stands on it
        rs.sort(key=lambda r: (r[1], r[0], r[2]))
        out[p] = ["fill %d %d %d %d %d %d %s replace %s" % (r[:6] + (r[6], FILTER[r[7]])) for r in rs]
    tags = m.spec["skin"]["reeds"]["soil_tags"]
    for (x, sy, z, hgt, _l) in sorted(m.canes):
        for t in tags:
            out["plants"].append("execute if block %d %d %d %s if block %d %d %d minecraft:air run fill %d %d %d %d %d %d "
                                 "minecraft:sugar_cane replace minecraft:air" % (x, sy, z, t, x, sy + 1, z, x, sy + 1, z,
                                                                                 x, sy + hgt, z))
    return out


def write(m, lns):
    """The pack: pack.mcmeta, the bed tag, the functions tiled by TILE and split at PART, each holding its chunks."""
    if OUT.exists():
        shutil.rmtree(OUT)
    fn = OUT / "data" / NS / "function" / FOLDER
    fn.mkdir(parents=True)
    (OUT / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                                          "Cobblers: the lake skin and the lake hooks (tools/lake_life.py)"}},
                                                indent=2) + "\n", encoding="utf-8")
    tag = OUT / "data" / NS / "tags" / "block" / "lake_bed.json"
    tag.parent.mkdir(parents=True)
    tag.write_text(json.dumps({"replace": False, "values": LAKE_BED}, indent=2) + "\n", encoding="utf-8")
    order = []
    for n, pas in enumerate(PASSES):
        tiles = {}
        for ln in lns[pas]:
            mt = FL.WRITE.search(ln)
            if not mt:
                raise LakeLifeError("a line with no block write: %s" % ln[:80])
            tiles.setdefault((int(mt.group(2)) // TILE, int(mt.group(4)) // TILE), []).append(ln)
        for t in sorted(tiles):
            body = tiles[t]
            for j in range(0, len(body), PART):
                name = "%d%s_%d_%d%s" % (n + 1, pas, t[0], t[1], "" if j == 0 else "_%d" % (j // PART + 1))
                part = FL.ensure_loaded(["# Generated by tools/lake_life.py: %s, tile %d %d" % (pas, t[0], t[1])]
                                        + body[j:j + PART])
                bad = FL.check_lines(part, name)
                if bad:
                    raise LakeLifeError("function %s would be refused: %s" % (name, bad[:3]))
                (fn / (name + ".mcfunction")).write_text("\n".join(part) + "\n", encoding="utf-8")
                order.append(name)
    (fn / "index.txt").write_text("\n".join(order) + "\n", encoding="utf-8")
    return order


# ------------------------------------------------------------------ the model, the report, the records

def model(source_root=None, spec=None):
    spec = spec or load()
    g = G.load(source_root)
    m = Model(spec, g, source_root)
    for h in spec["hooks"]:
        if h["lake"] not in m.lakes:
            m.problems.append("hook %s: no lake %s" % (h["id"], h["lake"]))
            continue
        if h["kind"] not in HOOKS:
            m.problems.append("hook %s: unknown kind %s" % (h["id"], h["kind"]))
            continue
        HOOKS[h["kind"]](m, h, m.lakes[h["lake"]])
    for bid in sorted(m.lakes):
        skin(m, m.lakes[bid])
    m.lines = lines(m)
    checks(m)
    return m


def summary(m):
    lakes = {}
    for bid, lk in sorted(m.lakes.items()):
        lakes[bid] = {"level": lk.level, "drop_depth": lk.drop, "wet_columns": int(lk.wet.sum()),
                      "bank_columns": int(lk.bank.sum()), "edge_columns_dropped": lk.edge_dropped,
                      "excluded_wet_or_bank_columns": {k: v for k, v in sorted(lk.excl_parts.items())},
                      "writes": dict(sorted(m.counts[bid].items())), "boulder_piles": len(lk.piles),
                      "drowned_trees": len(lk.drowned)}
    hooks = {}
    for hid, h in m.hooks.items():
        hooks[hid] = {k: v for k, v in h.items() if k not in ("leads_to",)}
    return {"lakes": lakes, "hooks": hooks, "cells": len(m.cells), "canes": len(m.canes),
            "commands": {k: len(v) for k, v in m.lines.items()},
            "protect_parts": m.ctx["protect_parts"], "problems": m.problems}


def records(m):
    if m.cache is None:
        raise LakeLifeError("no field case was built, so there is no cache record")
    h = m.cache["hook"]
    c = h["cache"]
    verified = {}
    for r in json.loads(REWARDS.read_text(encoding="utf-8"))["rewards"]:
        if str(r.get("id", "")).startswith(REWARD_PREFIX):
            continue
        for it in r.get("contents", []):
            if it.get("verification"):
                verified.setdefault(it["item"], it["verification"])
    missing = [it["item"] for it in c["contents"] if it["item"] not in verified]
    if missing:
        raise LakeLifeError("%s: %s verified by no other record in data/rewards.json" % (c["reward"], missing))
    x, y, z = m.cache["at"]
    return [{"id": c["reward"], "kind": "cache",
             "place": "Shrew Lake: the surveyor's field case on the pit floor at (%d, %d, %d), %d deep, at the end of the "
                      "line from the torn float on the shoal" % (x, y, z, m.lakes[h["lake"]].level - y + 1),
             "contents": [dict(it, verification=verified[it["item"]]) for it in c["contents"]],
             "message": c["message"],
             "why": "data/lake_life.json hooks shrew_torn_float: WATER_LIFE 2's surveyor's field case (SQ-DIG-02's find)",
             "built_by": "tools/lake_life.py (the barrel, in cobblers_lake_life's hooks pass)",
             "trigger": {"min": [x - 2, y - 1, z - 2], "max": [x + 2, y + 2, z + 2]},
             "container": {"block": "minecraft:barrel", "at": [x, y, z]}}]


def write_records(rew):
    doc = json.loads(REWARDS.read_text(encoding="utf-8"))
    ids = {r["id"] for r in rew}
    doc["rewards"] = [r for r in doc["rewards"] if r.get("id") not in ids
                      and not str(r.get("id", "")).startswith(REWARD_PREFIX)] + rew
    with open(REWARDS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cmd", choices=("report", "build", "records"))
    p.add_argument("--source-root", default=None)
    p.add_argument("--write", action="store_true", help="records: replace this tool's records in data/rewards.json")
    a = p.parse_args(argv)
    m = model(a.source_root)
    s = summary(m)
    if a.cmd == "records":
        rew = records(m)
        if a.write:
            write_records(rew)
            print("wrote %d rewards" % len(rew))
        else:
            print(json.dumps(rew, indent=1))
        return 0
    print(json.dumps(s, indent=1, default=list))
    if a.cmd == "build":
        if m.problems:
            print("NOT BUILT: %d problems" % len(m.problems))
            return 1
        order = write(m, m.lines)
        s["functions"] = ["%s:%s/%s" % (NS, FOLDER, f) for f in order]
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(s, indent=1, default=list) + "\n", encoding="utf-8")
        print("wrote %s (%d functions) and %s" % (OUT.relative_to(ROOT), len(order), PLAN.relative_to(ROOT)))
    return 1 if m.problems else 0


if __name__ == "__main__":
    sys.exit(main())
