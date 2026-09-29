#!/usr/bin/env python
"""Wayside shrines: small local offering places on the approaches of towns people pass through, as datapack functions.

The owner's brief (2026-09-28): "shrines near towns that people visit. Small, local, believable, not legendary
shrines." Each is a few to a few dozen vanilla blocks: a cairn with offerings, a roadside niche, a standing stone
with a lantern and flowers, a small roofed altar at a lookout. They are authored as data (data/shrines.json: a kind
from the library below, a position, a facing, a palette and the reason it stands there) and this tool turns each
into one function, `cobblers:shrines/<id>`, in the pack `cobblers_shrines`. Their stories and dedications are
Codex's: the data gives each a neutral working name and "story": "for Codex", and nothing here invents more.

Where a shrine stands:
  ground   the heightmap, rounded (tools/ground.py), never a world. A shrine stands on the highest ground under its
           footprint; a lower column gets a foundation course of its base block down to the ground
  clear    refused (the build stops and names the shrine and the reason) when any footprint cell is:
           - in or within 64 of a settlement the brief excludes (data/shrines.json rules.excluded_settlements);
           - on a town plan's street, plaza, verge, lot, anchor, lamp, earthwork, building (grown by 3), point or
             event site (tools/town_dressing.py Mask, for every planned settlement near the shrine);
           - within 3 of any placed building of any settlement (data/placements.json, its template's footprint),
             within 1 of any earthwork's written columns;
           - within 3 of a routed leg: derived/routes/critical_legs.json and every data/routes.json corridor
             polyline;
           - within 3 of a waystone, trader, signpost, scene prop, route trainer, Habitat Block, ferry dock or
             ambient worker's station or route, or on a route event site (data/scenes.json area) grown by 3;
           - within 3 of any block another built pack writes at an absolute position (every fill, setblock, place
             and summon under build/datapacks, this pack excepted): the other builds, whatever made them;
           - painted water, or within 4 of a painted tree or object (build/paint);
           - on or within 8 of a column the pending water export changes (derived/water_shape/changed.npy; the
             owner, 2026-09-28: nothing built that the export would invalidate). A missing file refuses the build;
           - on ground varying by more than the shrine allows
  order    the functions run after the towns, the donors, the lights, the dressing and the working Pokemon
           (tools/reapply.py R16D); each writes only its own columns, clearing trees and plants from them first,
           and force-loads what it writes (tools/function_limits.py)

tools/shrines_audit.py checks the written functions independently (its own reading of the plans, the legs, the water,
the other packs and the spawn conditions). The blocks are vanilla 1.21.1 only (data/shrines.json `blocks`); none may be
a spawn condition in data/spawn_blocks.json, which the audit checks (this tool does not read that file).

  python tools/shrines.py build [--source-root <root>]        # the pack, into build/datapacks
  authoring aids (they write nothing):
  python tools/shrines.py fit <kind> --near x,z [--facing south | --face-leg] [--leg-band 5,12] [--radius 24]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import town_dressing as TD  # noqa: E402
from town_dressing import Piece, block_name, h32, turn_state, turn_xz  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_shrines"
FUNCS = PACK / "data" / "cobblers" / "function" / "shrines"
REPORT = ROOT / "derived" / "shrines"
DATA = ROOT / "data" / "shrines.json"
WATER_CHANGED = ROOT / "derived" / "water_shape" / "changed.npy"
ID = re.compile(r"^[a-z0-9_]+$")

# ------------------------------------------------------------------------------------------------------- the kinds
DIRS = ("north", "east", "south", "west")


def pal(spec, key, default):
    return (spec.get("palette") or {}).get(key, default)


def shrine_cairn(spec, h):
    """A wayside cairn: stones piled three courses on a 3 by 3 base, a capstone, offerings at its foot in front."""
    p = Piece(relief=1)
    stones = pal(spec, "stones", ["minecraft:cobblestone", "minecraft:stone", "minecraft:andesite"])
    slab = pal(spec, "slab", "minecraft:cobblestone_slab[type=bottom]")
    for x in (-1, 0, 1):
        for z in (-1, 0, 1):
            p.put(x, 0, z, stones[h(x, z) % len(stones)])
    for x, z in ((0, 0), (-1, 0), (1, 0), (0, 1)):          # the second course, heavier at the back
        p.put(x, 1, z, stones[h(x, z, 1) % len(stones)])
    p.put(-1, 1, 1, slab)
    p.put(1, 1, 1, slab)
    p.put(0, 2, 0, stones[h(0, 0, 2) % len(stones)])
    p.put(0, 2, 1, slab)
    p.put(0, 3, 0, pal(spec, "cap", "minecraft:chiseled_stone_bricks"))
    # the offerings on the base's front ledge: a pot in the middle, a candle and a second offering either side
    p.put(0, 1, -1, pal(spec, "offering", "minecraft:decorated_pot[facing=north]"))
    p.put(-1, 1, -1, pal(spec, "candle", "minecraft:candle[candles=3,lit=true]"))
    p.put(1, 1, -1, pal(spec, "offering_2", "minecraft:potted_fern"))
    return p


def shrine_lantern_stone(spec, h):
    """A standing stone with a lantern on its head, a buttress behind, pots of flowers and candles at its foot."""
    p = Piece(relief=1)
    stone = pal(spec, "stone", "minecraft:stone_bricks")
    p.column(0, 0, 0, 2, stone)
    p.put(0, 3, 0, pal(spec, "cap", "minecraft:chiseled_stone_bricks"))
    p.put(0, 4, 0, "minecraft:lantern[hanging=false]")
    p.put(0, 0, 1, stone)                                   # the buttress, stepped against the stone's back
    p.put(0, 1, 1, pal(spec, "stair", "minecraft:stone_brick_stairs[facing=north]"))
    p.put(-1, 0, -1, pal(spec, "flowers", "minecraft:potted_azure_bluet"))
    p.put(1, 0, -1, pal(spec, "flowers_2", "minecraft:potted_oxeye_daisy"))
    p.put(0, 0, -1, pal(spec, "candle", "minecraft:white_candle[candles=2,lit=true]"))
    return p


def shrine_niche(spec, h):
    """A roadside niche: a walled box on a plinth, open to the road, a roof of stairs, a candle and a lantern inside."""
    p = Piece(relief=1)
    wall = pal(spec, "wall", "minecraft:mud_bricks")
    roof = pal(spec, "roof", "minecraft:dark_oak_stairs")
    for x in (-1, 0, 1):
        for z in (-1, 0):
            p.put(x, 0, z, wall)                            # the plinth
    for dy in (1, 2):
        for x in (-1, 1):
            p.put(x, dy, -1, wall)                          # the side walls, both rows
            p.put(x, dy, 0, wall)
        p.put(0, dy, 0, wall)                               # the back
    p.put(0, 1, 0, pal(spec, "icon", "minecraft:chiseled_stone_bricks"))   # what the niche keeps, in its back wall
    p.put(0, 1, -1, pal(spec, "candle", "minecraft:candle[candles=1,lit=true]"))
    p.put(0, 2, -1, "minecraft:lantern[hanging=true]")
    for x in (-1, 0, 1):                                    # a ridged roof: the front row sloping down to the road
        p.put(x, 3, -1, "%s[facing=south]" % block_name(roof))
        p.put(x, 3, 0, "%s[facing=north]" % block_name(roof))
    p.put(-2, 0, -1, pal(spec, "offering", "minecraft:flower_pot"))
    return p


def shrine_roofed_altar(spec, h):
    """A small roofed altar at a lookout: a paved floor, four posts, a slab roof, an altar block with candles."""
    floor = pal(spec, "floor", "minecraft:smooth_stone")
    p = Piece(relief=1, base=floor)
    post = pal(spec, "post", "minecraft:spruce_fence")
    roof = pal(spec, "roof", "minecraft:spruce_slab[type=bottom]")
    for x in (-1, 0, 1):
        for z in (-1, 0, 1):
            p.put(x, 0, z, floor)
            p.put(x, 3, z, roof)
    p.put(0, 3, 0, pal(spec, "roof_centre", "minecraft:stone_bricks"))   # a full block the finial stands on
    for x in (-1, 1):
        for z in (-1, 1):
            p.column(x, z, 1, 2, post)
    p.put(0, 4, 0, pal(spec, "finial", "minecraft:stone_brick_wall"))
    p.put(0, 1, 0, pal(spec, "altar", "minecraft:chiseled_stone_bricks"))
    p.put(0, 2, 0, pal(spec, "candle", "minecraft:candle[candles=4,lit=true]"))
    p.put(0, 1, 1, pal(spec, "offering", "minecraft:decorated_pot[facing=north]"))
    return p


KINDS = {"cairn": shrine_cairn, "lantern_stone": shrine_lantern_stone, "niche": shrine_niche,
         "roofed_altar": shrine_roofed_altar}


# ------------------------------------------------------------------------------------------------------ clearance
def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def raster_polyline(pts, box):
    """Cells of a polyline ([(x, z), ...]) inside box (x0, z0, x1, z1), a step at most one block."""
    x0, z0, x1, z1 = box
    out = set()
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        if max(ax, bx) < x0 - 1 or min(ax, bx) > x1 + 1 or max(az, bz) < z0 - 1 or min(az, bz) > z1 + 1:
            continue
        n = int(max(abs(bx - ax), abs(bz - az))) + 1
        for i in range(n + 1):
            t = i / max(n, 1)
            x, z = round(ax + (bx - ax) * t), round(az + (bz - az) * t)
            if x0 <= x <= x1 and z0 <= z <= z1:
                out.add((x, z))
    return out


def legs():
    """Every routed leg as a list of (x, z): the critical legs and every data/routes.json corridor polyline."""
    p = ROOT / "derived" / "routes" / "critical_legs.json"
    if not p.is_file():
        raise SystemExit("no %s: run python tools/critical_legs.py first" % p)
    out = [[tuple(q) for q in leg.get("polyline") or []] for leg in load_json(p)["legs"]]
    for r in load_json(ROOT / "data" / "routes.json")["routes"]:
        out.append([(q["x"], q["z"]) for q in (r.get("corridor") or {}).get("polyline") or []])
    return [l for l in out if len(l) > 1]


POINT_FILES = ("traders.json", "route_trainers.json", "habitat_blocks.json", "ferries.json", "rewards.json",
               "bridges.json", "ambient.json")
POINT_KEYS = ("at", "position", "pos", "station", "spot", "stand", "dock", "landing", "route", "path", "from", "to")


def _points_in(obj, out):
    """Every (x, z) a data record names: a dict with numeric x and z, or a coordinate list under a known key."""
    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if isinstance(obj, dict):
        if num(obj.get("x")) and num(obj.get("z")):
            out.append((int(math.floor(obj["x"])), int(math.floor(obj["z"]))))
        for k, v in obj.items():
            if k in POINT_KEYS and isinstance(v, list) and v:
                if len(v) in (2, 3) and all(num(t) for t in v):
                    out.append((int(math.floor(v[0])), int(math.floor(v[-1]))))
                elif all(isinstance(t, list) and len(t) in (2, 3) and all(num(u) for u in t) for t in v):
                    out += [(int(math.floor(t[0])), int(math.floor(t[-1]))) for t in v]
            _points_in(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _points_in(v, out)


def data_points():
    out = []
    for f in POINT_FILES:
        p = ROOT / "data" / f
        if p.is_file():
            _points_in(load_json(p), out)
    sp = ROOT / "derived" / "signposts.json"
    if not sp.is_file():
        raise SystemExit("no %s: run python tools/signposts.py function first" % sp)
    out += [(q["x"], q["z"]) for q in load_json(sp)["posts"]]
    doc = load_json(ROOT / "data" / "placements.json")
    for s in doc["settlements"].values():
        way = s.get("waystone") or (s.get("plan") or {}).get("waystone")
        if way:
            out.append(tuple(way["position"][:2]))
    for sc in load_json(ROOT / "data" / "scenes.json")["scenes"]:
        out += [(int(math.floor(q["at"][0])), int(math.floor(q["at"][2]))) for q in sc.get("props") or []]
    return out


WRITE = re.compile(r"\b(fill|setblock|clone|summon \S+|place (?:template|feature|structure|jigsaw) \S+)\s+"
                   r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+))?")


def built_rects(skip=("cobblers_shrines",)):
    """numpy (n, 4) of (x0, z0, x1, z1) every other built pack writes or summons at an absolute position."""
    import numpy as np
    rows = []
    base = ROOT / "build" / "datapacks"
    if not base.is_dir():
        raise SystemExit("no %s: the other builds cannot be checked (run reapply.py prepare)" % base)
    for pack in sorted(p for p in base.iterdir() if p.is_dir() and p.name not in skip):
        for f in pack.rglob("*.mcfunction"):
            for m in WRITE.finditer(f.read_text(encoding="utf-8", errors="replace")):
                g = m.groups()          # once: seven .group() calls a match over ~4M writes was 1.2 s
                x, z = int(math.floor(float(g[1]))), int(math.floor(float(g[3])))
                if g[0] in ("fill", "clone") and g[4] is not None:
                    xb, zb = int(g[4]), int(g[6])
                    rows.append((min(x, xb), min(z, zb), max(x, xb), max(z, zb)))
                else:
                    rows.append((x, z, x, z))
    return np.array(rows, dtype=np.int64).reshape(-1, 4)


class Clearance:
    """Why each cell of a window may not hold a shrine, from plan data and the other packs (never from a world)."""

    def __init__(self, ground, data, window, cache=None):
        import numpy as np
        from PIL import Image
        import elder_trees
        cache = cache if cache is not None else {}
        self.rules = data["rules"]
        R = self.rules
        self.window = window
        wx0, wz0, wx1, wz1 = window
        self.g = ground
        self.why = {}

        def inwin(c):
            return wx0 <= c[0] <= wx1 and wz0 <= c[1] <= wz1

        def mark(cells, why):
            for c in cells:
                if inwin(c):
                    self.why.setdefault(c, why)

        def grow_rect(r, m):
            return (r[0] - m, r[1] - m, r[2] + m, r[3] + m)

        def rect_in(r):
            x0, z0, x1, z1 = max(r[0], wx0), max(r[1], wz0), min(r[2], wx1), min(r[3], wz1)
            return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}

        towns = {t["id"]: t for t in load_json(ROOT / "data" / "towns.json")["towns"]}
        doc = cache.setdefault("doc", load_json(ROOT / "data" / "placements.json"))
        self.excluded = []
        for s in R["excluded_settlements"]:
            fp = towns[s]["footprint"]
            r = grow_rect((fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"]), R["excluded_margin"])
            self.excluded.append((s, r))
            mark(rect_in(r), "excluded settlement %s" % s)
        # a settlement on its own ground (the cavern, the islet, the sea decks) is not heightmap ground
        for s, rec in doc["settlements"].items():
            if rec.get("ground") and s in towns:
                fp = towns[s]["footprint"]
                mark(rect_in(grow_rect((fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"]), R["excluded_margin"])),
                     "settlement %s stands on %s ground" % (s, rec["ground"]))
        # the town plans near the window: tools/town_dressing.py's Mask (streets, verges, lots, anchors, lamps,
        # buildings, earthworks, points, legs and event sites inside the town's reach)
        for s in doc["settlements"]:
            if s not in towns or not (ROOT / "derived" / "towns" / ("%s_plan.json" % s)).is_file():
                continue
            fp = towns[s]["footprint"]
            reach = TD.TOWN_REACH + 8
            if fp["max_x"] + reach < wx0 or fp["min_x"] - reach > wx1 or fp["max_z"] + reach < wz0 or fp["min_z"] - reach > wz1:
                continue
            key = ("mask", s)
            if key not in cache:
                cache[key] = TD.Mask(s, doc).why
            for c, why in cache[key].items():
                if inwin(c):
                    self.why.setdefault(c, "%s: %s" % (s, why))
        # every placed building of every settlement, and every earthwork's written columns
        if "buildings" not in cache:
            rects = []
            for s in sorted({q.get("settlement") for q in doc["placements"] if q.get("settlement")}):
                rects += [(bid, r) for bid, r in TD.building_footprints(s, doc).items()]
            ew = [(q["id"], TD.command_columns(q.get("commands"))) for q in doc["placements"] if q.get("kind") == "earthwork"]
            cache["buildings"], cache["earthworks"] = rects, ew
        for bid, r in cache["buildings"]:
            mark(rect_in(grow_rect(r, R["building_margin"])), "building %s" % bid)
        for eid, cols in cache["earthworks"]:
            mark(TD.grow({c for c in cols if wx0 - 2 <= c[0] <= wx1 + 2 and wz0 - 2 <= c[1] <= wz1 + 2}, 1),
                 "earthwork %s" % eid)
        # the routed legs
        if "legs" not in cache:
            cache["legs"] = legs()
        m = R["leg_margin"]
        for leg in cache["legs"]:
            mark(TD.grow(raster_polyline(leg, grow_rect(window, m)), m), "routed leg")
        # the points and the event sites
        if "points" not in cache:
            cache["points"] = data_points()
        m = R["point_margin"]
        for x, z in cache["points"]:
            if wx0 - m <= x <= wx1 + m and wz0 - m <= z <= wz1 + m:
                mark(rect_in((x - m, z - m, x + m, z + m)), "a waystone, trader, signpost, prop, NPC or station at %d,%d" % (x, z))
        for sc in load_json(ROOT / "data" / "scenes.json")["scenes"]:
            if sc.get("area"):
                a0, a1 = sc["area"]["from"], sc["area"]["to"]
                mark(rect_in(grow_rect((min(a0[0], a1[0]), min(a0[2], a1[2]), max(a0[0], a1[0]), max(a0[2], a1[2])), m)),
                     "event site %s" % sc["id"])
        # the other builds: every absolute write of every other built pack
        if "built" not in cache:
            cache["built"] = built_rects()
        b = cache["built"]
        m = R["build_margin"]
        hit = b[(b[:, 2] + m >= wx0) & (b[:, 0] - m <= wx1) & (b[:, 3] + m >= wz0) & (b[:, 1] - m <= wz1)]
        for r in hit:
            mark(rect_in(grow_rect(tuple(int(v) for v in r), m)), "another pack's build at %d,%d" % (r[0], r[1]))
        # the painted water and trees, and the pending water export
        if "wet" not in cache:
            cache["wet"] = elder_trees.painted_water(ground.heights, ground.world)
            man = load_json(ROOT / "build" / "paint" / "manifest.json")
            trees = np.zeros(cache["wet"].shape, dtype=bool)
            for layer in man.get("objects") or []:
                trees |= np.asarray(Image.open(ROOT / "build" / "paint" / layer["map"])) > 0
            cache["trees"] = trees
            if not WATER_CHANGED.is_file():
                raise SystemExit("no %s: the pending water export's changes cannot be kept clear of; refusing"
                                 % WATER_CHANGED)
            cache["changed"] = np.load(WATER_CHANGED, mmap_mode="r")
        self.wet, self.trees, self.changed = cache["wet"], cache["trees"], cache["changed"]
        self.ox, self.oz = ground.ox, ground.oz

    def blocked(self, x, z):
        wx0, wz0, wx1, wz1 = self.window
        if not (wx0 <= x <= wx1 and wz0 <= z <= wz1):
            return "outside the window this clearance was computed for"
        if (x, z) in self.why:
            return self.why[(x, z)]
        ix, iz = x - self.ox, z - self.oz
        if self.wet[iz, ix]:
            return "painted water"
        t, w = self.rules["tree_reach"], self.rules["water_change_margin"]
        if self.trees[max(0, iz - t):iz + t + 1, max(0, ix - t):ix + t + 1].any():
            return "painted tree or object"
        if self.changed[max(0, iz - w):iz + w + 1, max(0, ix - w):ix + w + 1].any():
            return "within %d of a column the pending water export changes" % w
        return None


# --------------------------------------------------------------------------------------------------------- the build
def place(spec, ground, clear):
    """[(x, y, z, state)] for one shrine seated on the ground, and its floor; or SystemExit naming what is in the way."""
    kind = spec["kind"]
    if kind not in KINDS:
        raise SystemExit("%s: unknown shrine kind %r (known: %s)" % (spec["id"], kind, ", ".join(sorted(KINDS))))
    ox, oz = spec["at"]
    facing = spec.get("facing", "north")
    if facing not in DIRS:
        raise SystemExit("%s: facing %r is not one of %s" % (spec["id"], facing, DIRS))
    piece = KINDS[kind](spec, lambda *v: h32(ox, oz, *v))
    last = {}
    for x, dy, z, s in piece.blocks:
        last[(x, dy, z)] = s
    world = [(ox + turn_xz(x, z, facing)[0], dy, oz + turn_xz(x, z, facing)[1], turn_state(s, facing))
             for (x, dy, z), s in last.items()]
    cols = sorted({(x, z) for x, _dy, z, _s in world})
    for x, z in cols:
        why = clear.blocked(x, z)
        if why:
            raise SystemExit("%s: cell (%d, %d) is not free: %s" % (spec["id"], x, z, why))
    g = {c: ground(*c) for c in cols}
    relief = max(g.values()) - min(g.values())
    if relief > piece.relief:
        raise SystemExit("%s: the ground under it varies by %d blocks (this kind allows %d): move it"
                         % (spec["id"], relief, piece.relief))
    floor = max(g.values()) + 1
    base = piece.base or pal(spec, "foundation", "minecraft:cobblestone")
    footing = {}
    for x, dy, z, _s in world:
        footing[(x, z)] = min(footing.get((x, z), dy), dy)
    out = []
    for (x, z), low in footing.items():
        if low <= 0:
            for y in range(g[(x, z)] + 1, floor + low):
                out.append((x, y, z, base))
    out += [(x, floor + dy, z, s) for x, dy, z, s in world]
    return out, floor


def window_for(spec, pad=8):
    x, z = spec["at"]
    return (x - pad, z - pad, x + pad, z + pad)


def commands_for(spec, blocks, floor):
    cmds = ["# Generated by tools/shrines.py from data/shrines.json (%s). Re-run to rebuild." % spec["id"],
            "# %s: %s (%s)" % (spec["id"], spec["kind"], spec["name"])]
    cols = sorted({(x, z) for x, _y, z, _s in blocks})
    ys = [y for _x, y, _z, _s in blocks]
    for x0, x1, z in TD._runs(cols):
        cmds.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:replaceable" % (x0, floor - 1, z, x1, max(ys) + 1, z))
        for tag in ("#minecraft:logs", "#minecraft:leaves"):
            cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, floor, z, x1, max(ys) + 2, z, tag))
    for x, y, z, s in sorted(blocks, key=lambda b: (b[1], b[0], b[2])):
        cmds.append("setblock %d %d %d %s" % (x, y, z, s))
    return cmds


def validate_data(data):
    problems = []
    seen = set()
    for s in data.get("shrines") or []:
        sid = s.get("id", "?")
        if not ID.match(sid) or sid in seen:
            problems.append("%s: id must be unique lowercase [a-z0-9_]" % sid)
        seen.add(sid)
        for k in ("name", "settlement", "kind", "at", "facing", "why", "story", "palette"):
            if k not in s:
                problems.append("%s: missing %r" % (sid, k))
        if s.get("story") != "for Codex":
            problems.append("%s: its story is Codex's to write: \"story\": \"for Codex\"" % sid)
        if s.get("settlement") in data["rules"]["excluded_settlements"]:
            problems.append("%s: stands at %s, which the brief excludes" % (sid, s["settlement"]))
    if not data.get("shrines"):
        problems.append("data/shrines.json lists no shrine")
    return problems


def build(a):
    import ground as G
    data = load_json(DATA)
    problems = validate_data(data)
    if problems:
        raise SystemExit("data/shrines.json: " + "; ".join(problems))
    allowed = set(data["blocks"]["ids"])
    towns = {t["id"]: t for t in load_json(ROOT / "data" / "towns.json")["towns"]}
    g = G.Ground(a.source_root)
    cache = {}
    if PACK.exists():
        shutil.rmtree(PACK)
    FUNCS.mkdir(parents=True)
    (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                      "Cobblers: wayside shrines (tools/shrines.py)"}}, indent=2) + "\n", encoding="utf-8")
    REPORT.mkdir(parents=True, exist_ok=True)
    report, names, taken = {"shrines": []}, [], {}
    for spec in data["shrines"]:
        fp = towns[spec["settlement"]]["footprint"]
        cx, cz = (fp["min_x"] + fp["max_x"]) / 2, (fp["min_z"] + fp["max_z"]) / 2
        half = (fp["max_x"] - fp["min_x"]) / 2
        far = math.hypot(spec["at"][0] - cx, spec["at"][1] - cz) - half
        if far > data["rules"]["max_from_town"]:
            raise SystemExit("%s: %.0f blocks past %s's footprint; a shrine on its approach stands within %d"
                             % (spec["id"], far, spec["settlement"], data["rules"]["max_from_town"]))
        clear = Clearance(g, data, window_for(spec), cache)
        blocks, floor = place(spec, g, clear)
        bad = sorted({block_name(s) for _x, _y, _z, s in blocks} - allowed)
        if bad:
            raise SystemExit("%s: blocks not in data/shrines.json `blocks`: %s" % (spec["id"], bad))
        cols = sorted({(x, z) for x, _y, z, _s in blocks})
        for c in cols:
            if c in taken:
                raise SystemExit("%s overlaps %s at %s" % (spec["id"], taken[c], c))
            taken[c] = spec["id"]
        cmds = function_limits.ensure_loaded(commands_for(spec, blocks, floor))
        refused = function_limits.check_lines(cmds, spec["id"])
        if refused:
            raise SystemExit("%s: %d command(s) the server would refuse: %s" % (spec["id"], len(refused), refused[:3]))
        (FUNCS / ("%s.mcfunction" % spec["id"])).write_text("\n".join(cmds) + "\n", encoding="utf-8")
        names.append(spec["id"])
        top = max(blocks, key=lambda b: (b[1], b[0], b[2]))
        xs, ys, zs = [b[0] for b in blocks], [b[1] for b in blocks], [b[2] for b in blocks]
        report["shrines"].append({"id": spec["id"], "kind": spec["kind"], "settlement": spec["settlement"],
                                  "at": spec["at"], "facing": spec.get("facing", "north"), "floor_y": floor,
                                  "columns": cols, "blocks": len(blocks),
                                  "box": [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)],
                                  "check": "execute if block %d %d %d %s" % (top[0], top[1], top[2], block_name(top[3]))})
        print("%-28s %-13s at %5d %5d y%d  %3d blocks, %3d commands" % (spec["id"], spec["kind"], spec["at"][0],
                                                                        spec["at"][1], floor, len(blocks), len(cmds)))
    (FUNCS / "index.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    (REPORT / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (REPORT / "checks.txt").write_text("\n".join(s["check"] for s in report["shrines"]) + "\n", encoding="utf-8")
    print("wrote", PACK)
    return 0


# ---------------------------------------------------------------------------------------------- authoring aids
def _facing_to(ax, az, bx, bz):
    """The cardinal direction from (ax, az) towards (bx, bz)."""
    dx, dz = bx - ax, bz - az
    if abs(dx) >= abs(dz):
        return "east" if dx > 0 else "west"
    return "south" if dz > 0 else "north"


def _leg_distance(x, z, all_legs):
    """(distance, nearest point) from (x, z) to the nearest routed leg, measured to its segments."""
    best = (1e18, None)
    for leg in all_legs:
        for (ax, az), (bx, bz) in zip(leg, leg[1:]):
            vx, vz = bx - ax, bz - az
            L = vx * vx + vz * vz
            t = 0.0 if L == 0 else max(0.0, min(1.0, ((x - ax) * vx + (z - az) * vz) / L))
            px, pz = ax + t * vx, az + t * vz
            d = math.hypot(x - px, z - pz)
            if d < best[0]:
                best = (d, (px, pz))
    return best


def _fits(kind, near, radius, facing, g, data, cache, count, spec_extra=None, face_leg=False, leg_band=None):
    cx, cz = near
    clear = Clearance(g, data, (cx - radius - 4, cz - radius - 4, cx + radius + 4, cz + radius + 4), cache)
    cands = sorted(((x, z) for x in range(cx - radius, cx + radius + 1) for z in range(cz - radius, cz + radius + 1)),
                   key=lambda c: (c[0] - cx) ** 2 + (c[1] - cz) ** 2)
    found = []
    for x, z in cands:
        f = facing
        dleg, near_pt = _leg_distance(x, z, cache["legs"])
        if leg_band and not (leg_band[0] <= dleg <= leg_band[1]):
            continue
        if face_leg:
            f = _facing_to(x, z, near_pt[0], near_pt[1])
        spec = dict(spec_extra or {}, id="fit", kind=kind, at=[x, z], facing=f)
        try:
            _b, floor = place(spec, g, clear)
        except SystemExit:
            continue
        found.append((x, z, f, floor, dleg))
        if len(found) >= count:
            break
    return found


def fit(a):
    import ground as G
    data = load_json(DATA)
    g = G.Ground(a.source_root)
    cx, cz = (int(v) for v in a.near.split(","))
    cache = {"legs": legs()}
    band = [float(v) for v in a.leg_band.split(",")] if a.leg_band else None
    found = _fits(a.kind, (cx, cz), a.radius, a.facing, g, data, cache, a.count, face_leg=a.face_leg, leg_band=band)
    for x, z, f, floor, dleg in found:
        print("at [%d, %d] facing %s: floor y%d, %.0f from %d,%d, %.1f from a leg"
              % (x, z, f, floor, math.hypot(x - cx, z - cz), cx, cz, dleg))
    if not found:
        print("nothing fits within %d of %d,%d" % (a.radius, cx, cz))
        return 1
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("build")
    q.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    q = sub.add_parser("fit")
    q.add_argument("kind")
    q.add_argument("--near", required=True)
    q.add_argument("--facing", default="north")
    q.add_argument("--face-leg", action="store_true", help="face each candidate towards the nearest routed leg")
    q.add_argument("--leg-band", help="min,max distance from the nearest routed leg, e.g. 5,12")
    q.add_argument("--radius", type=int, default=24)
    q.add_argument("--count", type=int, default=5)
    q.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"))
    a = p.parse_args(argv)
    return {"build": build, "fit": fit}[a.cmd](a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
