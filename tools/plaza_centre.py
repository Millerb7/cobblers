#!/usr/bin/env python
"""Plaza centres: each town's middle -- a centrepiece, market stalls, benches, lamps and planters -- as functions.

The owner, 2026-10-03: "TOWN SQUARES AND TRADERS. Finish them properly. Market squares, stalls, the civic centre of
each town. Several still read as streets with buildings rather than places with a middle ... every town should have
somewhere a player goes to spend money." docs/world-building/TOWN_SQUARES_SURVEY.md found two towns with a real middle
(Fossick, Northlight) and twelve without one; docs/world-building/TOWN_CENTERS.md section 3 specified this generator
(step R13) on 2026-09-25 and nobody wrote it. tools/place_town.py only paves a plaza, and tools/town_dressing.py masks
the plaza out of every piece, so until now nothing could stand on one.

What it reads (never a world):
  data/plaza_centres.json    the authored squares: per town the square (rect, floor y, centrepiece), the centrepiece's
                             kind and palette, the stalls (the CONTRACT below) and the furniture
  derived/towns/<town>_plan.json   the plan tools/town_plan.py computed from the heightmap: plaza rect and y, street
                             cells, lots, anchors, lamps (Pallet has no plan: its roads are read from its settlement)
  data/placements.json       buildings (footprints and doors, as tools/place_town.py seats them), earthworks, waystones
  data/traders.json, data/markets.json, data/npc_seats.json, data/ambient.json, data/scenes.json,
  derived/signposts.json, data/route_paths.json, data/town_dressing.json     everything else that stands near a plaza
  tools/ground.py            the heightmap, rounded, for any cell off the plaza's paving

Where a piece may stand (the build refuses and names the piece and the cell otherwise):
  inside the square's rect; off every street cell and its verge, every lot and anchor, every building footprint and
  the block round it, every earthwork column that stands above the floor, every lamp and the cell round it, the
  waystone and its pad, every street mouth projected 6 into the square, every door apron (5 wide, 4 deep), every
  desire line (3 wide) between the mouths, the doors and the waystone, every NPC (trader, market keeper, seat,
  working Pokemon) and the two blocks round it, every walked route line and the two blocks round it, every signpost,
  scene prop and dressing piece. A flush piece (a carpet laid on the paving) may cross a desire line or a mouth, never
  a street cell, a lamp or the waystone. Coverage: at most `coverage_max` of the square's cells (TOWN_CENTERS rule 5).

THE CONTRACT (with the trader builder; do not rename):
  data/plaza_centres.json towns.<town>.square = {"rect": [x0, z0, x1, z1], "y": <floor>, "centrepiece": [x, y, z]}
  towns.<town>.stalls = [{"id": "<town>_stall_<n>", "at": [x, y, z], "facing": "north|south|east|west",
                          "keeper_at": [x, y, z, yaw], "sells": "<theme word>"}]
  `at` is the counter's middle block; `facing` is the side the customers stand on; `keeper_at` is where the keeper's
  FEET go: the block under it is the square's floor, it and the block above it are air, it is behind the counter and
  the yaw faces the customers (Minecraft yaw: 0 south, 90 west, 180 north, -90 east). `y` in `at` is the counter
  block's y, which is the keeper's feet y. The build recomputes all of it from the piece and REFUSES on any drift, so
  the record cannot say one thing while the function builds another.

Spawn-neutral: no block data/spawn_blocks.json lists (water, bells, leaves, flowers, wool, lightning rods, iron
blocks ...): a square must not decide what spawns in a town (TOWN_CENTERS rule 7). Every block is in the data's
`blocks.ids`, each checked against the 1.21.1 client jar's blockstates when that jar is present (`check-ids`).

Light: every stall and every roofed centrepiece carries its own lantern, and a lamp post stands only where the plan's
flush lamps and the pieces' own lanterns leave a cell of the square unlit in the simple model below (Manhattan
distance, no occlusion); the build refuses a lamp post within LAMP_DOUBLE of another light (a doubled lamp) and a
square cell left dark. tools/light_plan.py does NOT yet model these blocks: see the report's `needs`.

Order: R13, after the towns (R8), the donors (R9) and the bridges (R9G), before the lights (R16) and the dressing
(R16B). Writes: build/datapacks/cobblers_plaza_centres (cobblers:plaza_centres/<town>, index.txt), and the model of
every block it writes in derived/plaza_centres/<town>.json, for tools/town_audit.py and tools/light_plan.py to read.

  python tools/plaza_centre.py build [--source-root <root>]
  python tools/plaza_centre.py map <town> [--margin 6]        # authoring aid: the square and what keeps it clear
  python tools/plaza_centre.py check-ids [--jar <client jar>]  # every allowed block against the jar's blockstates
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402

DATA = ROOT / "data" / "plaza_centres.json"
PACK = ROOT / "build" / "datapacks" / "cobblers_plaza_centres"
FUNCS = PACK / "data" / "cobblers" / "function" / "plaza_centres"
REPORT = ROOT / "derived" / "plaza_centres"

WAYSTONE_PAD = 3          # the stone and its arrival pad
LAMP_MARGIN = 1
STREET_VERGE = 1
MOUTH_DEPTH = 6           # a street mouth is kept clear this far into the square
APRON = (5, 4)            # a door apron: wide, deep
DESIRE_HALF = 1           # a desire line is 3 wide
NPC_MARGIN = 2
WALKED_MARGIN = 2         # 3+ from every walked route line, the rule the market keepers were sited by
BUILDING_MARGIN = 1
LIGHT_REACH = 14          # a lantern's 15 falls to 1 at 14 blocks (Manhattan)
LAMP_DOUBLE = 5           # a lamp post this close to another light doubles it
FLUSH_KINDS = {"carpet_eye"}

DIRS = ("north", "east", "south", "west")
STEP = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
YAW = {"south": 0, "west": 90, "north": 180, "east": -90}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rect_cells(rect, margin=0):
    x0, z0, x1, z1 = rect
    return {(x, z) for x in range(x0 - margin, x1 + margin + 1) for z in range(z0 - margin, z1 + margin + 1)}


def grow(cells, margin):
    if margin <= 0:
        return set(cells)
    out = set()
    for x, z in cells:
        for dx in range(-margin, margin + 1):
            for dz in range(-margin, margin + 1):
                out.add((x + dx, z + dz))
    return out


def line_cells(a, b):
    (ax, az), (bx, bz) = a, b
    n = int(max(abs(bx - ax), abs(bz - az)))
    return {(round(ax + (bx - ax) * i / max(n, 1)), round(az + (bz - az) * i / max(n, 1))) for i in range(n + 1)}


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


def xz_points(v):
    """Every (x, z) in a position-ish value: [x, z], [x, y, z], {"x":, "z":}, {"at": ...}, or a list of them."""
    if not v:
        return []
    if isinstance(v, dict):
        if "x" in v and "z" in v:
            return [(int(math.floor(v["x"])), int(math.floor(v["z"])))]
        return [c for k in ("at", "position", "from", "to") for c in xz_points(v.get(k))]
    if isinstance(v, list) and v and all(isinstance(t, (int, float)) for t in v):
        if len(v) == 2:
            return [(int(math.floor(v[0])), int(math.floor(v[1])))]
        if len(v) >= 3:
            return [(int(math.floor(v[0])), int(math.floor(v[2])))]
        return []
    if isinstance(v, list):
        return [c for t in v for c in xz_points(t)]
    return []


# ------------------------------------------------------------------------------------------------------- the town
CMD = re.compile(r"(?:fill|setblock)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+))?")


def earthwork_columns(cmds, floor_y):
    """Columns an earthwork writes ABOVE the floor (a command that only paves or digs does not stand on the square)."""
    cols = set()
    for c in cmds or []:
        if c.lstrip().startswith("#"):
            continue
        m = CMD.search(c)
        if not m:
            continue
        xa, ya, za = int(m.group(1)), int(m.group(2)), int(m.group(3))
        xb, yb, zb = (int(m.group(4)), int(m.group(5)), int(m.group(6))) if m.group(4) else (xa, ya, za)
        if max(ya, yb) <= floor_y or " minecraft:air" in c and "replace" not in c:
            continue
        cols |= {(x, z) for x in range(min(xa, xb), max(xa, xb) + 1) for z in range(min(za, zb), max(za, zb) + 1)}
    return cols


def doors(settlement, doc):
    """{placement id: {"front": (x, z), "facing": f, "role": r}} for every building seated from a template file: the
    cell one outside its entrance, as tools/place_town.py computes it. A donor placed by resource id (the gyms) has no
    file here, so its door is unknown and it is not listed."""
    import place_town as PT
    plan = (doc["settlements"][settlement].get("plan") or {})
    roles = {a["id"]: a["role"] for a in plan.get("anchors") or []}
    out = {}
    for p in doc["placements"]:
        if p.get("settlement") != settlement or not p.get("file") or not p.get("position"):
            continue
        info = PT.template_info(ROOT / p["file"])
        if info["entrance_pos"] is None:
            continue
        rot = PT.rotation_for(info["entrance"], p["facing"])
        mnx, mnz, _w, _d = PT.footprint(info["size"], rot)
        px, pz = p["position"]["x"] - mnx, p["position"]["z"] - mnz
        rx, rz = PT.rotate(info["entrance_pos"][0], info["entrance_pos"][2], rot)
        sx, sz = STEP[p["facing"]]
        role = roles.get(p.get("lot")) or ("pokecenter" if "pokecenter" in p["id"] else
                                           "pokemart" if "pokemart" in p["id"] else p.get("kind") or "building")
        out[p["id"]] = {"door": (px + rx, pz + rz), "front": (px + rx + sx, pz + rz + sz), "facing": p["facing"],
                        "role": role}
    return out


def road_cells(settlement, doc):
    """{(x, z): y or None} of a planless settlement's authored roads, laid the way tools/place_town.py lays them."""
    out = {}
    for r in doc["settlements"][settlement].get("roads") or []:
        pts = r.get("polyline")
        if not pts:
            continue                                   # a road that follows a routed leg is outside the town's middle
        half = r["width"] // 2
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            n = int(max(abs(bx - ax), abs(bz - az))) + 1
            for i in range(n):
                t = i / max(n - 1, 1)
                cx, cz = round(ax + (bx - ax) * t), round(az + (bz - az) * t)
                for dx in range(-half, half + 1):
                    for dz in range(-half, half + 1):
                        out[(cx + dx, cz + dz)] = None
    return out


class Town:
    """One settlement's square and everything that keeps a piece off a cell, from the plan (never a world)."""

    def __init__(self, settlement, rec, doc, ground, refs):
        import town_dressing as TD
        self.settlement = settlement
        self.rec = rec
        self.doc = doc
        self.ground = ground
        sq = rec["square"]
        self.rect = tuple(sq["rect"])
        self.y = int(sq["y"])
        self.paved = bool(rec.get("on_plaza", True))
        s = doc["settlements"][settlement]
        plan_path = ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)
        if (s.get("plan") or {}) and not plan_path.is_file():
            raise SystemExit("no %s: run python tools/town_plan.py %s first" % (plan_path, settlement))
        self.plan = load_json(plan_path) if (s.get("plan") or {}) else {}
        pz = self.plan.get("plaza")
        if self.paved:
            if not pz or list(pz["rect"]) != list(self.rect) or int(pz["y"]) != self.y:
                raise SystemExit("%s: the square %s y%d is not the plan's plaza %s: a square on the plaza must be the "
                                 "plaza, so a replanned plaza carries its square or the build refuses"
                                 % (settlement, list(self.rect), self.y, pz and (pz["rect"], pz["y"])))
        self.street_y = {}
        for st in (self.plan.get("streets") or {}).values():
            for z, y, xa, xb in st.get("cells") or []:
                for x in range(xa, xb + 1):
                    self.street_y[(x, z)] = int(y)
        if not self.plan:
            self.street_y.update(road_cells(settlement, doc))
        self.why = {}
        self.soft = {}                                    # kept clear of standing pieces, not of flush ones

        def mark(cells, why, soft=False):
            tgt = self.soft if soft else self.why
            for c in cells:
                tgt.setdefault(c, why)
        streets = set(self.street_y)
        mark(streets, "street")
        mark(grow(streets, STREET_VERGE) - set(rect_cells(self.rect)) if self.paved else grow(streets, STREET_VERGE),
             "street verge")
        # a street cell that runs over the plaza is a street: its verge on the plaza is a walking line, kept clear of
        # standing pieces
        mark(grow({c for c in streets if c in rect_cells(self.rect)}, STREET_VERGE), "street verge", soft=True)
        for lot in self.plan.get("lots") or []:
            mark(rect_cells(lot["rect"], 1), "lot %s" % lot["id"])
        for an in self.plan.get("anchors") or []:
            mark(rect_cells(an["rect"], 1), "anchor %s" % an["id"])
        self.lamps = []
        for lamp in self.plan.get("lamps") or []:
            # the plan's `at` is the position over the lamp; the lamp itself is set flush in the paving under it
            self.lamps.append((lamp["at"][0], lamp["at"][1] - 1, lamp["at"][2]))
            mark(grow({(lamp["at"][0], lamp["at"][2])}, LAMP_MARGIN), "lamp")
        self.footprints = TD.building_footprints(settlement, doc)
        for bid, r in self.footprints.items():
            mark(rect_cells(r, BUILDING_MARGIN), "building %s" % bid)
        for q in doc["placements"]:
            if q.get("settlement") == settlement and q.get("kind") == "earthwork":
                cols = earthwork_columns(q.get("commands"), self.y)
                mark(grow(cols, 1), "earthwork %s" % q["id"])
                for c in q.get("commands") or []:
                    m = re.match(r"\s*setblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+minecraft:(?:sea_)?lantern", c)
                    if m:
                        self.lamps.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
        way = s.get("waystone") or (s.get("plan") or {}).get("waystone")
        self.waystone = tuple(way["position"][:2]) if way else None
        if self.waystone:
            mark(grow({self.waystone}, WAYSTONE_PAD), "waystone and its pad")
        # NPCs: traders, market keepers, seats, working Pokemon
        box = rect_cells(self.rect, 12)
        self.npcs = []
        for t in refs["traders"]:
            if t.get("position"):
                self.npcs.append(((t["position"]["x"], t["position"]["z"]), "trader %s" % t["id"]))
        for c in refs["markets"]:
            if c.get("at"):
                self.npcs.append(((c["at"][0], c["at"][2]), "market keeper %s" % c["id"]))
        for st in refs["seats"]:
            if st.get("at"):
                self.npcs.append(((int(math.floor(st["at"][0])), int(math.floor(st["at"][2]))), "seat %s" % st["id"]))
        for w in refs["ambient"]:
            for key in ("at", "route", "spots", "box"):
                for c in xz_points(w.get(key)):
                    self.npcs.append((c, "working Pokemon %s" % w["id"]))
        for (x, z), why in self.npcs:
            if (x, z) in box:
                mark(grow({(x, z)}, NPC_MARGIN), why)
        for pts in refs["walked"].values():
            near = [tuple(p) for p in pts if tuple(p) in box]
            if near:
                mark(grow(set(near), WALKED_MARGIN), "walked route line")
        for p in refs["signposts"]:
            mark(grow({(p["x"], p["z"])}, NPC_MARGIN), "signpost %s" % p["id"])
        for sc in refs["scenes"]:
            for q in sc.get("props") or []:
                mark(grow({(int(math.floor(q["at"][0])), int(math.floor(q["at"][2])))}, NPC_MARGIN), "scene prop")
            if sc.get("area"):
                a0, a1 = sc["area"]["from"], sc["area"]["to"]
                mark(rect_cells((min(a0[0], a1[0]), min(a0[2], a1[2]), max(a0[0], a1[0]), max(a0[2], a1[2])), NPC_MARGIN),
                     "event site %s" % sc["id"])
        dressing = (refs["dressing"].get("towns") or {}).get(settlement)
        if dressing:
            class _Open:
                def blocked(self, x, z):
                    return None
            entries = ([dict(dressing["landmark"], id=dressing["landmark"].get("id", "landmark"))]
                       if dressing.get("landmark") else []) + list(dressing.get("pieces") or [])
            for e in entries:
                blocks, _f = TD.place(e, settlement, ground, _Open())
                mark(grow({(b[0], b[2]) for b in blocks}, 1), "dressing %s" % e["id"])
        # the walking lines: street mouths, door aprons and the desire lines between them and the waystone
        self.doors = doors(settlement, doc)
        portals = []
        r = self.rect
        rc = rect_cells(r)
        by_street = {}
        for sid, st in (self.plan.get("streets") or {}).items():
            by_street[sid] = {(x, z) for z, _y, xa, xb in st.get("cells") or [] for x in range(xa, xb + 1)}
        if not self.plan:
            by_street["roads"] = set(self.street_y)
        for sid, cells in by_street.items():
            sides = {}
            for (sx, sz) in cells:
                if (sx, sz) in rc or not (r[0] - 1 <= sx <= r[2] + 1 and r[1] - 1 <= sz <= r[3] + 1):
                    continue
                dx = 1 if sx < r[0] else -1 if sx > r[2] else 0
                dz = 1 if sz < r[1] else -1 if sz > r[3] else 0
                if dx and dz:
                    continue
                proj = {(sx + dx * k, sz + dz * k) for k in range(1, MOUTH_DEPTH + 1)}
                mark(grow(proj & rc, 1), "street mouth", soft=True)
                sides.setdefault((dx, dz), []).append((sx + dx, sz + dz))
            # one portal per street per side: the mouth's middle
            for pts in sides.values():
                mx, mz = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
                portals.append((min(pts, key=lambda p: (p[0] - mx) ** 2 + (p[1] - mz) ** 2), "street %s" % sid))
        for bid, d in self.doors.items():
            fx, fz = d["front"]
            if not (r[0] - 8 <= fx <= r[2] + 8 and r[1] - 8 <= fz <= r[3] + 8):
                continue
            sx, sz = STEP[d["facing"]]
            w, dp = APRON
            apron = {(fx + sx * k + (-sz) * j, fz + sz * k + sx * j) for k in range(dp) for j in range(-(w // 2), w // 2 + 1)}
            mark(apron, "door apron %s" % bid, soft=True)
            portals.append(((min(max(fx, r[0]), r[2]), min(max(fz, r[1]), r[3])), "door %s" % bid))
        if self.waystone and self.waystone in rc:
            portals.append((self.waystone, "waystone"))
        # the desire lines (TOWN_CENTERS rule 2): a straight 3-wide line between every two portals, except two ends of
        # one street that runs through the square, whose own paving is already the line between them
        thin = []
        for p, tag in portals:
            if all(abs(p[0] - q[0]) + abs(p[1] - q[1]) > 4 for q, _t in thin):
                thin.append((p, tag))
        self.portals = thin
        for i, (a, ta) in enumerate(thin):
            for b, tb in thin[i + 1:]:
                if ta == tb and ta.startswith("street "):
                    continue
                mark(grow(line_cells(a, b), DESIRE_HALF) & rc, "desire line", soft=True)

    def floor_at(self, x, z):
        """The y of the floor block under (x, z): the square's paving, a street's, else the heightmap."""
        if self.paved and self.rect[0] <= x <= self.rect[2] and self.rect[1] <= z <= self.rect[3]:
            return self.y
        if self.street_y.get((x, z)) is not None:
            return self.street_y[(x, z)]
        return self.ground(x, z)

    def blocked(self, x, z, flush=False):
        r = self.rect
        if not (r[0] <= x <= r[2] and r[1] <= z <= r[3]):
            return "outside the square"
        why = self.why.get((x, z))
        if flush and why in ("street verge",):
            why = None
        if why:
            return why
        if not flush:
            return self.soft.get((x, z))
        return None


# ------------------------------------------------------------------------------------------------------ the pieces
def turn_xz(x, z, facing):
    """Local (x, z), front towards -z (north), turned so the front faces `facing`."""
    for _ in range(DIRS.index(facing)):
        x, z = -z, x
    return x, z


def turn_state(state, facing):
    """A block state's facing, axis and side properties turned with the piece; any block-entity data kept as is."""
    import town_dressing as TD
    nbt = ""
    if "{" in state:
        state, nbt = state[:state.index("{")], state[state.index("{"):]
    return TD.turn_state(state, facing) + nbt


def sign(wood, facing, lines):
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
    return "minecraft:%s_wall_sign[facing=%s]{front_text:{messages:[%s]}}" % (wood, facing, q)


class Piece:
    """Blocks as (local x, dy, local z, state); dy 0 is the block above the floor. `keeper` and `customer` are local
    cells of a stall; `lights` the local (x, dy, z) of every lantern the piece carries."""

    def __init__(self, relief=1, flush=False):
        self.blocks = []
        self.relief = relief
        self.flush = flush
        self.keeper = None
        self.customer = None

    def put(self, x, dy, z, state):
        self.blocks.append((x, dy, z, state))

    def column(self, x, z, dy0, dy1, state):
        for dy in range(dy0, dy1 + 1):
            self.put(x, dy, z, state)


def pal(town, spec, key, default):
    return (spec.get("palette") or {}).get(key) or (town.get("palette") or {}).get(key) or default


def piece_stall(town, spec, goods):
    """A market stall, 3 by 3: the counter at the front with the goods on it, a keeper's cell behind it between the back
    posts, the stock stacked at the back, a slab roof under an awning, and a lantern hanging over the counter."""
    p = Piece()
    wood = pal(town, spec, "wood", "spruce")
    counter = pal(town, spec, "counter", "minecraft:stripped_%s_log[axis=x]" % wood)
    post = "minecraft:%s_fence" % wood
    roof = "minecraft:%s_slab[type=bottom]" % wood
    awning = spec.get("awning") or pal(town, spec, "awning", "minecraft:red_carpet")
    g = goods[spec["sells"]]
    for x in (-1, 0, 1):
        p.put(x, 0, 0, counter)
        for z in (0, 1, 2):
            p.put(x, 3, z, roof)
            p.put(x, 4, z, awning)
    p.put(0, 1, 0, g["counter"][0])
    p.put(0, 2, 0, "minecraft:lantern[hanging=true]")
    for x in (-1, 1):
        p.column(x, 0, 1, 2, post)                     # the front posts stand on the counter's ends
        p.column(x, 1, 0, 2, post)                     # the back posts from the floor, either side of the keeper
    for i, x in enumerate((-1, 0, 1)):
        p.put(x, 0, 2, g["stock"][i % len(g["stock"])])
    p.put(-1, 1, 2, g["stock"][-1])
    p.keeper = (0, 1)
    p.customer = (0, -1)
    return p


def piece_bench(town, spec, goods):
    """A bench of three stairs, its sitters looking to the front."""
    p = Piece()
    wood = pal(town, spec, "wood", "spruce")
    seat = pal(town, spec, "bench", "minecraft:%s_stairs" % wood)
    for x in range(-(int(spec.get("length", 3)) // 2), int(spec.get("length", 3)) - int(spec.get("length", 3)) // 2):
        p.put(x, 0, 0, "%s[facing=south]" % seat)
    return p


def piece_lamp_post(town, spec, goods):
    p = Piece()
    post = pal(town, spec, "post", "minecraft:%s_fence" % pal(town, spec, "wood", "spruce"))
    p.column(0, 0, 0, 1, post)
    p.put(0, 2, 0, "minecraft:lantern[hanging=false]")
    return p


def piece_flush_lamp(town, spec, goods):
    """A sea lantern set flush into the paving, the plan's own lamp (tools/town_plan.py): for a dark cell on a walking
    line, where a post would stand in the way."""
    p = Piece(flush=True)
    p.put(0, -1, 0, "minecraft:sea_lantern")
    return p


def piece_planter(town, spec, goods):
    """A raised bed, 1 by 3, of moss with azalea and fern: green without a leaf or a flower (both spawn conditions)."""
    p = Piece()
    bed = pal(town, spec, "planter_bed", "minecraft:moss_block")
    plants = pal(town, spec, "planter_plants", ["minecraft:azalea", "minecraft:fern", "minecraft:azalea"])
    for i, x in enumerate((-1, 0, 1)):
        p.put(x, 0, 0, bed)
        p.put(x, 1, 0, plants[i % len(plants)])
    return p


def piece_notice_board(town, spec, goods):
    """A board on two posts with the town's sign on its front."""
    p = Piece()
    wood = pal(town, spec, "wood", "spruce")
    post = "minecraft:%s_fence" % wood
    board = "minecraft:%s_planks" % wood
    for x in (-1, 1):
        p.put(x, 0, 0, post)
    for x in (-1, 0, 1):
        p.put(x, 1, 0, board)
    p.put(0, 2, 0, "minecraft:%s_slab[type=bottom]" % wood)
    p.put(0, 1, -1, sign(wood if wood != "bamboo" else "bamboo", "north", spec.get("lines") or []))
    return p


def piece_stone_lantern(town, spec, goods):
    """A garden lantern: a wall post, a lantern on it."""
    p = Piece()
    p.put(0, 0, 0, pal(town, spec, "lantern_post", "minecraft:stone_brick_wall"))
    p.put(0, 1, 0, "minecraft:lantern[hanging=false]")
    return p


def piece_well(town, spec, goods):
    """A roofed well, 3 by 3: a rim round a capped shaft, two posts and a roof with a chain down to the cap. Dry (no
    water: a spawn condition): "the fen water is not for drinking"."""
    p = Piece()
    rim = pal(town, spec, "well_rim", "minecraft:mud_bricks")
    cap = pal(town, spec, "well_cap", "minecraft:packed_mud")
    wood = pal(town, spec, "wood", "mangrove")
    for x in (-1, 0, 1):
        for z in (-1, 0, 1):
            p.put(x, 0, z, cap if (x, z) == (0, 0) else rim)
            p.put(x, 3, z, "minecraft:%s_slab[type=bottom]" % wood)
    for x in (-1, 1):
        p.column(x, 0, 1, 2, "minecraft:%s_fence" % wood)
    p.put(0, 1, 0, "minecraft:chain")
    p.put(0, 2, 0, "minecraft:chain")
    p.put(0, 2, -1, "minecraft:lantern[hanging=true]")
    return p


def piece_brazier(town, spec, goods):
    """A raised blackstone basin, 5 by 5, with the fire two blocks up, behind a wall rim: no feet in it. No magma, no
    lava (spawn conditions)."""
    p = Piece()
    base = pal(town, spec, "brazier_base", "minecraft:polished_blackstone_bricks")
    rim = pal(town, spec, "brazier_rim", "minecraft:polished_blackstone_wall")
    for x in range(-2, 3):
        for z in range(-2, 3):
            edge = abs(x) == 2 or abs(z) == 2
            p.put(x, 0, z, base)
            p.put(x, 1, z, rim if edge else "minecraft:blackstone")
            if not edge:
                p.put(x, 2, z, "minecraft:campfire[lit=true]" if (x, z) == (0, 0)
                      else "minecraft:polished_blackstone_slab[type=bottom]" if abs(x) + abs(z) == 1
                      else "minecraft:gilded_blackstone")
    return p


def piece_pylon(town, spec, goods):
    """A relay pylon, 3 by 3 and 9 high: copper grate corner legs, cut-copper collars, a cap and end rods on top.
    Never a lightning rod (a spawn condition)."""
    p = Piece()
    leg = pal(town, spec, "pylon_leg", "minecraft:waxed_copper_grate")
    collar = pal(town, spec, "pylon_collar", "minecraft:waxed_cut_copper")
    h = int(spec.get("height", 7))
    for x in (-1, 1):
        for z in (-1, 1):
            p.column(x, z, 0, h - 1, leg)
    for dy in (0, 3, h - 1):
        for x, z in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            p.put(x, dy, z, collar)
    p.put(0, 0, 0, collar)
    p.put(0, h - 1, 0, collar)
    p.put(0, h, 0, "minecraft:end_rod[facing=up]")
    p.put(0, h + 1, 0, "minecraft:end_rod[facing=up]")
    p.relief = 0
    return p


def piece_sighting_post(town, spec, goods):
    """A plinth with a pointer aimed along the front: the brass sighting post at the array."""
    p = Piece()
    p.put(0, 0, 0, pal(town, spec, "plinth", "minecraft:waxed_cut_copper"))
    p.put(0, 1, 0, "minecraft:end_rod[facing=north]")
    return p


def piece_onix_run(town, spec, goods):
    """A low segmented stone serpent, humps no higher than 3, curling from its tail to its head at the front."""
    p = Piece()
    mats = pal(town, spec, "onix_stone", ["minecraft:cobblestone", "minecraft:andesite", "minecraft:stone",
                                          "minecraft:polished_andesite", "minecraft:tuff"])
    # the body, 2 by 2 segments from the tail (back) to the neck, rising and falling, then the head at the front:
    # 6 wide and 11 long
    segs = [(1, 4, 1), (2, 2, 2), (1, 0, 3), (-1, -1, 2), (-2, -3, 1)]
    segs = segs[-int(spec.get("segments", len(segs))):]    # a shorter serpent drops segments from the tail
    for i, (cx, cz, h) in enumerate(segs):
        for x in (cx, cx + 1):
            for z in (cz, cz + 1):
                p.column(x, z, 0, h - 1, mats[i % len(mats)])
    for x in (-2, -1, 0):                               # the head, at the front
        for z in (-5, -4):
            p.column(x, z, 0, 1, "minecraft:polished_andesite")
    p.put(-2, 1, -5, "minecraft:chiseled_stone_bricks")   # the eyes
    p.put(0, 1, -5, "minecraft:chiseled_stone_bricks")
    p.put(-1, 2, -4, "minecraft:stone_brick_slab[type=bottom]")   # the horn ridge
    return p


def piece_standing_stones(town, spec, goods):
    """An arc of standing stones, each 3 high, opening to the front: one stone per material in `stones`."""
    p = Piece()
    stones = spec.get("stones") or pal(town, spec, "stones", [])
    n = len(stones)
    for i, mat in enumerate(stones):
        a = math.pi * (i / max(n - 1, 1))
        x = int(round(-7 * math.cos(a)))
        z = int(round(4 * math.sin(a)))
        p.column(x, z, 0, 2, mat)
    return p


def piece_boat_hull(town, spec, goods):
    """An upturned hull on trestles, 7 long and 3 wide, its keel along x."""
    p = Piece()
    wood = pal(town, spec, "wood", "oak")
    for x in (-2, 2):
        for z in (-1, 1):
            p.put(x, 0, z, "minecraft:%s_fence" % wood)
    for x in range(-3, 4):
        p.put(x, 1, -1, "minecraft:%s_slab[type=top]" % wood)
        p.put(x, 1, 1, "minecraft:%s_slab[type=top]" % wood)
        p.put(x, 1, 0, "minecraft:%s_planks" % wood)
        p.put(x, 2, 0, "minecraft:stripped_%s_log[axis=x]" % wood)
        if abs(x) < 3:
            p.put(x, 2, -1, "minecraft:%s_stairs[facing=south]" % wood)
            p.put(x, 2, 1, "minecraft:%s_stairs[facing=north]" % wood)
    return p


def piece_net_rack(town, spec, goods):
    """Two posts and a bar with a net (iron bars) hung between them."""
    p = Piece()
    wood = pal(town, spec, "wood", "oak")
    for x in (-1, 1):
        p.column(x, 0, 0, 2, "minecraft:%s_fence" % wood)
    p.put(0, 2, 0, "minecraft:%s_fence" % wood)
    p.put(0, 1, 0, "minecraft:iron_bars")
    return p


def piece_barrel_stack(town, spec, goods):
    """A chandler's stack: barrels, two by two, one and two high."""
    p = Piece()
    for i, (x, z) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
        p.column(x, z, 0, 1 if i % 2 == 0 else 0, "minecraft:barrel[facing=up]")
    return p


def piece_carpet_eye(town, spec, goods):
    """A flush eye laid in carpet on the paving: the crossing stays flat. White and yellow carpet are spawn
    conditions, so the eye's white is light grey."""
    p = Piece(flush=True)
    rx, rz = int(spec.get("rx", 6)), int(spec.get("rz", 3))
    for x in range(-rx, rx + 1):
        for z in range(-rz, rz + 1):
            e = (x / rx) ** 2 + (z / rz) ** 2
            if e > 1.0:
                continue
            d2 = x * x + z * z
            st = ("minecraft:black_carpet" if d2 <= 1 else "minecraft:purple_carpet" if d2 <= 4
                  else "minecraft:light_gray_carpet" if e <= 0.6 else "minecraft:gray_carpet")
            p.put(x, 0, z, st)
    return p


def piece_plinth(town, spec, goods):
    """A quartz plinth, 1 by 1 and 2 high, with an end rod on it."""
    p = Piece()
    p.put(0, 0, 0, pal(town, spec, "plinth", "minecraft:quartz_bricks"))
    p.put(0, 1, 0, "minecraft:quartz_pillar[axis=y]")
    p.put(0, 2, 0, "minecraft:end_rod[facing=up]")
    return p


def piece_pavilion(town, spec, goods):
    """An open tea pavilion, 5 by 5: four corner posts, a slab roof, a low table with seats, a lantern hung in it."""
    p = Piece()
    wood = pal(town, spec, "wood", "cherry")
    for x in (-2, 2):
        for z in (-2, 2):
            p.column(x, z, 0, 2, "minecraft:stripped_%s_log[axis=y]" % wood)
    for x in range(-2, 3):
        for z in range(-2, 3):
            p.put(x, 3, z, "minecraft:%s_slab[type=bottom]" % wood if (abs(x) == 2 or abs(z) == 2)
                  else "minecraft:%s_planks" % wood)
    p.put(0, 0, 0, "minecraft:%s_trapdoor[half=top,open=false]" % wood)          # the low table
    p.put(0, 0, -1, "minecraft:%s_stairs[facing=north]" % wood)                    # seats on two sides
    p.put(0, 0, 1, "minecraft:%s_stairs[facing=south]" % wood)
    p.put(0, 2, 0, "minecraft:lantern[hanging=true]")
    p.put(0, 1, 0, "minecraft:decorated_pot")                                       # the teapot
    return p


def piece_parterre(town, spec, goods):
    """A hedged bed, 5 by 3: a low wall of mossy stone round moss with azalea and fern: a garden's green with no leaf
    and no flower (spawn conditions)."""
    p = Piece()
    rim = pal(town, spec, "parterre_rim", "minecraft:mossy_stone_brick_wall")
    for x in range(-2, 3):
        for z in (-1, 0, 1):
            if abs(x) == 2 or abs(z) == 1:
                p.put(x, 0, z, rim)
            else:
                p.put(x, 0, z, "minecraft:moss_block")
                p.put(x, 1, z, "minecraft:azalea" if x == 0 else "minecraft:fern")
    return p


def piece_pergola(town, spec, goods):
    """A pergola, 5 by 5: four posts, open beams, two benches facing in, a lantern hung in the middle."""
    p = Piece()
    wood = pal(town, spec, "wood", "dark_oak")
    for x in (-2, 2):
        for z in (-2, 2):
            p.column(x, z, 0, 2, "minecraft:%s_fence" % wood)
    for x in range(-2, 3):
        p.put(x, 3, -2, "minecraft:stripped_%s_log[axis=x]" % wood)
        p.put(x, 3, 2, "minecraft:stripped_%s_log[axis=x]" % wood)
    for z in (-1, 0, 1):
        p.put(0, 3, z, "minecraft:stripped_%s_log[axis=z]" % wood)
    for x in (-1, 0, 1):                                # two benches facing each other across the middle
        p.put(x, 0, -1, "minecraft:%s_stairs[facing=north]" % wood)
        p.put(x, 0, 1, "minecraft:%s_stairs[facing=south]" % wood)
    p.put(0, 2, 0, "minecraft:lantern[hanging=true]")
    return p


def piece_first_step(town, spec, goods):
    """The "first step" stone at the Route 1 mouth: a low mossy stone with a sign."""
    p = Piece()
    p.put(0, 0, 0, "minecraft:mossy_cobblestone")
    p.put(0, 0, -1, sign("oak", "north", spec.get("lines") or []))
    return p


PIECES = {
    "stall": piece_stall, "bench": piece_bench, "lamp_post": piece_lamp_post, "flush_lamp": piece_flush_lamp,
    "planter": piece_planter,
    "notice_board": piece_notice_board, "stone_lantern": piece_stone_lantern, "well": piece_well,
    "brazier": piece_brazier, "pylon": piece_pylon, "sighting_post": piece_sighting_post, "onix_run": piece_onix_run,
    "standing_stones": piece_standing_stones, "boat_hull": piece_boat_hull, "net_rack": piece_net_rack,
    "barrel_stack": piece_barrel_stack, "carpet_eye": piece_carpet_eye, "plinth": piece_plinth,
    "pavilion": piece_pavilion, "parterre": piece_parterre, "pergola": piece_pergola, "first_step": piece_first_step,
}


def entries_of(rec):
    """Every piece of a town, in build order: the centrepiece, its companions, the stalls, then the furniture."""
    out = []
    c = rec["centrepiece"]
    out.append(dict(c, id=c.get("id", "%s_centrepiece" % rec["_town"]), role="centrepiece"))
    out += [dict(q, role="centre") for q in rec.get("centre_extras") or []]
    out += [dict(q, kind="stall", role="stall") for q in rec.get("stalls") or []]
    out += [dict(q, role="furniture") for q in rec.get("pieces") or []]
    out += [dict(q, kind="path", role="link") for q in rec.get("links") or []]
    return out


def seat(town, rec, spec, goods):
    """{blocks: [(x, y, z, state)], cols, floor, keeper, customer} for one piece, or SystemExit naming the obstacle."""
    kind = spec["kind"]
    if kind == "path":
        return seat_path(town, spec)
    if kind not in PIECES:
        raise SystemExit("%s/%s: unknown piece kind %r (known: %s)" % (town.settlement, spec["id"], kind,
                                                                       ", ".join(sorted(PIECES))))
    if kind == "stall":
        ox, _oy, oz = spec["at"]
    else:
        ox, oz = spec["at"][0], spec["at"][-1]
    facing = spec.get("facing", "north")
    if facing not in DIRS:
        raise SystemExit("%s/%s: facing %r is not one of %s" % (town.settlement, spec["id"], facing, DIRS))
    piece = PIECES[kind](rec, spec, goods)
    last = {}
    for x, dy, z, s in piece.blocks:
        last[(x, dy, z)] = s
    world = []
    for (x, dy, z), s in last.items():
        tx, tz = turn_xz(x, z, facing)
        world.append((ox + tx, dy, oz + tz, turn_state(s, facing)))
    cols = sorted({(x, z) for x, _dy, z, _s in world})
    for x, z in cols:
        why = town.blocked(x, z, flush=piece.flush)
        if why:
            raise SystemExit("%s/%s: cell (%d, %d) is not free: %s" % (town.settlement, spec["id"], x, z, why))
    g = {c: town.floor_at(*c) for c in cols}
    if max(g.values()) - min(g.values()) > piece.relief:
        raise SystemExit("%s/%s: the floor under it varies by %d blocks (this piece allows %d)"
                         % (town.settlement, spec["id"], max(g.values()) - min(g.values()), piece.relief))
    floor = max(g.values()) + 1
    blocks = []
    footing = {}
    for x, dy, z, s in world:
        footing[(x, z)] = min(footing.get((x, z), dy), dy)
    for (x, z), low in footing.items():
        if low <= 0:
            for y in range(g[(x, z)] + 1, floor + low):
                blocks.append((x, y, z, pal(rec, spec, "foundation", "minecraft:packed_mud")))
    blocks += [(x, floor + dy, z, s) for x, dy, z, s in world]
    out = {"blocks": blocks, "cols": cols, "floor": floor, "flush": piece.flush, "facing": facing, "origin": (ox, oz)}
    for key in ("keeper", "customer"):
        loc = getattr(piece, key)
        if loc is not None:
            tx, tz = turn_xz(loc[0], loc[1], facing)
            out[key] = (ox + tx, oz + tz)
    return out


PATH_MAY_CROSS = ("street", "street verge", "walked route line", "outside the square")


def seat_path(town, spec):
    """A link of paving from a street to the square, laid flush: each cell's floor block becomes the surface, at that
    cell's own floor (the plan's street or plaza level, else the heightmap). It may cross a street's verge, a walked
    route line and ground outside the square, and nothing else on the mask."""
    w = int(spec.get("width", 3))
    cells = grow(line_cells(tuple(spec["from"]), tuple(spec["to"])), w // 2)
    for x, z in sorted(cells):
        why = town.why.get((x, z))                     # the hard mask only: every soft line is walking, as a path is
        if why and why not in PATH_MAY_CROSS:
            raise SystemExit("%s/%s: cell (%d, %d) is not free: %s" % (town.settlement, spec["id"], x, z, why))
        if (x, z) in town.street_y:
            raise SystemExit("%s/%s: cell (%d, %d) is already a street: a link only joins one to the square"
                             % (town.settlement, spec["id"], x, z))
    blocks = [(x, town.floor_at(x, z), z, spec["surface"]) for x, z in sorted(cells)]
    for x, y, z, _s in blocks:
        for n in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if n in cells and abs(town.floor_at(*n) - y) > 1:
                raise SystemExit("%s/%s: a step of more than one block at (%d, %d)" % (town.settlement, spec["id"], x, z))
    cols = sorted(cells)
    return {"blocks": blocks, "cols": cols, "floor": min(b[1] for b in blocks) + 1, "flush": True,
            "facing": "north", "origin": tuple(spec["from"])}


# --------------------------------------------------------------------------------------------- light and walking
def lights_of(blocks):
    return [(x, y, z) for x, y, z, s in blocks if block_name(s) in ("minecraft:lantern", "minecraft:campfire",
                                                                      "minecraft:end_rod", "minecraft:sea_lantern")]


def dark_cells(town, occupied, lights, streets=False):
    """Cells of the square whose standing position (floor + 1) no light reaches, in the Manhattan model. A street cell
    running over the square is the street lamps' (tools/town_plan.py spaces them by LIGHT_REACH), so it is counted only
    with streets=True, as a finding for the report."""
    out = []
    x0, z0, x1, z1 = town.rect
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if (x, z) in occupied or (((x, z) in town.street_y) != streets):
                continue
            y = town.floor_at(x, z) + 1
            if not any(abs(lx - x) + abs(ly - y) + abs(lz - z) < LIGHT_REACH + 1 for lx, ly, lz in lights):
                out.append((x, z))
    return out


def walk(town, start, occupied, reach=None, only=None):
    """{cell: steps} reachable on foot from `start` over the town's paving and ground: a step changes the floor by at
    most one block, and never enters a building footprint or a piece's column."""
    bx0, bz0, bx1, bz1 = reach or (town.rect[0] - 90, town.rect[1] - 90, town.rect[2] + 90, town.rect[3] + 90)
    walls = set()
    for r in town.footprints.values():
        if r[2] < bx0 or r[0] > bx1 or r[3] < bz0 or r[1] > bz1:
            continue
        walls |= rect_cells(r)
    seen = {start: 0}
    q = deque([start])
    while q:
        c = q.popleft()
        y = town.floor_at(*c)
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dz)
            if n in seen or n in walls or n in occupied or (only is not None and n not in only):
                continue
            if not (bx0 <= n[0] <= bx1 and bz0 <= n[1] <= bz1):
                continue
            if abs(town.floor_at(*n) - y) > 1:
                continue
            seen[n] = seen[c] + 1
            q.append(n)
    return seen


def unpaved_to_square(town, start, occupied, paved, reachable):
    """The fewest unpaved cells a walk from `start` to the square must cross (a 0-1 search over the cells `walk` found
    reachable): how far a door's way to the square leaves the town's paving."""
    best = {start: 0 if start in paved else 1}
    parent = {start: None}
    q = deque([start])
    target = rect_cells(town.rect)
    while q:
        c = q.popleft()
        if c in target:
            cells = []
            while c is not None:
                if c not in paved:
                    cells.append(list(c))
                c = parent[c]
            return {"count": len(cells), "cells": cells[::-1]}
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dz)
            if n not in reachable or abs(town.floor_at(*n) - town.floor_at(*c)) > 1:
                continue
            w = 0 if n in paved else 1
            if best[c] + w < best.get(n, 10 ** 9):
                best[n] = best[c] + w
                parent[n] = c
                (q.appendleft if w == 0 else q.append)(n)
    return None


# --------------------------------------------------------------------------------------------------------- the build
def ground_for(settlement, base, doc, source_root):
    """The settlement's ground (tools/ground.py for_settlement): the heightmap, or the sea town's decks at the sea level.
    A settlement with its own ground gets a fresh copy, because for_settlement writes into the Ground it is given."""
    import ground as G
    if (doc["settlements"][settlement].get("ground")) is None:
        return base
    return G.for_settlement(settlement, source_root, doc)


def refs_of():
    walked = load_json(ROOT / "data" / "route_paths.json")["paths"]
    sp = ROOT / "derived" / "signposts.json"
    if not sp.is_file():
        raise SystemExit("no %s: run python tools/signposts.py function first" % sp)
    return {
        "traders": load_json(ROOT / "data" / "traders.json").get("traders") or [],
        "markets": [c for c in load_json(ROOT / "data" / "markets.json").get("counters") or [] if c.get("status") == "sited"],
        "seats": load_json(ROOT / "data" / "npc_seats.json").get("seats") or [],
        "ambient": load_json(ROOT / "data" / "ambient.json").get("workers") or [],
        "walked": walked,
        "signposts": load_json(sp)["posts"],
        "scenes": load_json(ROOT / "data" / "scenes.json")["scenes"],
        "dressing": load_json(ROOT / "data" / "town_dressing.json"),
    }


def goods_of(data):
    """{theme: {"counter": [...], "stock": [...]}}, a theme written {"like": other} taking the other's goods."""
    raw = data["goods"]
    out = {}
    for k, v in raw.items():
        seen = [k]
        while "like" in v:
            if v["like"] in seen or v["like"] not in raw:
                raise SystemExit("goods %r: `like` %r is a loop or names no theme" % (k, v["like"]))
            seen.append(v["like"])
            v = raw[v["like"]]
        out[k] = v
    return out


def plan_town(settlement, rec, doc, ground, refs, data):
    """(commands, report) for one town, or SystemExit on the first rule a piece breaks."""
    rec = dict(rec, _town=settlement)
    town = Town(settlement, rec, doc, ground, refs)
    goods = goods_of(data)
    allowed = set(data["blocks"]["ids"])
    spawn = set(load_json(ROOT / "data" / "spawn_blocks.json")["blocks"])
    taken = {}
    seated = []
    for spec in entries_of(rec):
        if spec["kind"] == "stall" and spec.get("sells") not in goods:
            raise SystemExit("%s/%s: sells %r, which data/plaza_centres.json `goods` has no stock for"
                             % (settlement, spec["id"], spec.get("sells")))
        st = seat(town, rec, spec, goods)
        for c in st["cols"]:
            if c in taken and not (st["flush"] or taken[c][1]):
                raise SystemExit("%s/%s overlaps %s at %s" % (settlement, spec["id"], taken[c][0], c))
        for c in st["cols"]:
            if c not in taken or not st["flush"]:
                taken[c] = (spec["id"], st["flush"])
        bad = sorted({block_name(s) for _x, _y, _z, s in st["blocks"]} - allowed)
        if bad:
            raise SystemExit("%s/%s: blocks not in data/plaza_centres.json `blocks`: %s" % (settlement, spec["id"], bad))
        spawny = sorted({block_name(s) for _x, _y, _z, s in st["blocks"]} & spawn)
        if spawny:
            raise SystemExit("%s/%s: spawn-condition blocks (data/spawn_blocks.json): %s" % (settlement, spec["id"], spawny))
        seated.append((spec, st))
    occupied = {c for c, (_pid, flush) in taken.items() if not flush}
    rect_n = (town.rect[2] - town.rect[0] + 1) * (town.rect[3] - town.rect[1] + 1)
    cover = len(occupied) / rect_n
    cap = float(rec.get("coverage_max", 0.15))
    if cover > cap:
        raise SystemExit("%s: furniture covers %.1f%% of the square, over its cap of %.0f%%" % (settlement, 100 * cover, 100 * cap))
    # the contract: every stall's record must be what the piece builds
    for spec, st in seated:
        if spec["kind"] != "stall":
            continue
        kx, kz = st["keeper"]
        want_at = [spec["at"][0], st["floor"], spec["at"][2]]
        want_keeper = [kx, st["floor"], kz, YAW[st["facing"]]]
        if list(spec["at"]) != want_at or list(spec.get("keeper_at") or []) != want_keeper:
            raise SystemExit("%s/%s: the record says at %s keeper_at %s, the stall builds at %s keeper_at %s"
                             % (settlement, spec["id"], spec["at"], spec.get("keeper_at"), want_at, want_keeper))
        if not re.fullmatch(r"%s_stall_\d+" % re.escape(settlement), spec["id"]):
            raise SystemExit("%s: stall id %r is not <town>_stall_<n>" % (settlement, spec["id"]))
    cp = seated[0][1]
    want_cp = [cp["origin"][0], cp["floor"], cp["origin"][1]]
    if list(rec["square"].get("centrepiece") or []) != want_cp:
        raise SystemExit("%s: square.centrepiece is %s, the centrepiece stands at %s"
                         % (settlement, rec["square"].get("centrepiece"), want_cp))
    # light: the plan's lamps and every lantern the pieces carry; then no doubled lamp post and no dark cell
    piece_lights = []
    for spec, st in seated:
        mine = lights_of(st["blocks"])
        if spec["kind"] in ("lamp_post", "flush_lamp"):
            for lx, ly, lz in mine:
                near = [l for l in town.lamps + piece_lights if abs(l[0] - lx) + abs(l[2] - lz) < LAMP_DOUBLE]
                if near:
                    raise SystemExit("%s/%s: a lamp post %d blocks from the light at %s doubles it"
                                     % (settlement, spec["id"], abs(near[0][0] - lx) + abs(near[0][2] - lz), list(near[0])))
        piece_lights += mine
    dark = dark_cells(town, occupied, town.lamps + piece_lights)
    if dark:
        raise SystemExit("%s: %d cell(s) of the square are unlit in the model, e.g. %s: add a lamp_post"
                         % (settlement, len(dark), dark[:4]))
    # walking: every stall's customer cell, the centrepiece and every bench from the Centre's and the Mart's doors
    starts = {d["role"]: (bid, d["front"]) for bid, d in town.doors.items() if d["role"] in ("pokecenter", "pokemart")}
    if "pokecenter" not in starts:
        raise SystemExit("%s: no Pokemon Center door found (a placement with a template file and role pokecenter)" % settlement)
    reach = {}
    for role, (bid, front) in sorted(starts.items()):
        seen = walk(town, front, occupied)
        on_square = [seen[c] for c in rect_cells(town.rect) if c in seen]
        if not on_square:
            raise SystemExit("%s: the square cannot be reached on foot from %s's door at %s" % (settlement, bid, front))
        # and on the town's own paving alone (its streets, the square, the anchors' lots): a door whose way to the
        # square crosses unpaved ground is named in the report
        paved = set(town.street_y) | rect_cells(town.rect)
        paved |= {c for spec_, st_ in seated if spec_["kind"] == "path" for c in st_["cols"]}
        for an in town.plan.get("anchors") or []:
            paved |= rect_cells(an["rect"], 1)
        reach[role] = {"door": list(front), "steps_to_square": min(on_square),
                       "unpaved_cells_on_the_way": unpaved_to_square(town, front, occupied, paved, seen)}
        for spec, st in seated:
            goal = st.get("customer")
            if goal is not None:
                goals = [goal]
            else:
                goals = [n for c in st["cols"] for n in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1))
                         if n not in occupied]
            if st["flush"]:
                goals = list(st["cols"])
            if not any(g in seen for g in goals):
                raise SystemExit("%s/%s: cannot be reached on foot from %s's door" % (settlement, spec["id"], bid))
    # the function
    cmds = ["# Generated by tools/plaza_centre.py from data/plaza_centres.json (%s, %s). Re-run to rebuild."
            % (settlement, rec.get("name", settlement))]
    dark_street = dark_cells(town, occupied, town.lamps + piece_lights, streets=True)
    report = {"settlement": settlement, "name": rec.get("name"), "square": rec["square"], "class": rec.get("class"),
              "coverage": round(cover, 3), "reach": reach, "pieces": [], "lights": [list(l) for l in piece_lights],
              "dark_street_cells": [list(c) for c in dark_street],
              "needs": ["tools/town_audit.py reads this model: its blocked_above check on the plaza would otherwise "
                        "report every piece as a block standing on the road",
                        "tools/light_plan.py models these blocks (this build's light model is Manhattan, no occlusion)"]}
    for spec, st in seated:
        cols, ys = st["cols"], [b[1] for b in st["blocks"]]
        cmds.append("# %s: %s (%s)" % (spec["id"], spec["kind"], (spec.get("why") or spec.get("sells") or "")[:100]))
        if spec["kind"] == "path":
            # plants off the link first, so none is left standing on paving
            for x, y, z, _s in st["blocks"]:
                cmds.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:replaceable" % (x, y + 1, z, x, y + 2, z))
        if not st["flush"]:
            # plants and snow out of the piece's columns first (the plan cleared the plaza; a rebuild may not have)
            for x, z in cols:
                cmds.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:replaceable"
                            % (x, st["floor"], z, x, max(ys) + 1, z))
        for x, y, z, s in sorted(st["blocks"], key=lambda b: (b[1], b[0], b[2])):
            cmds.append("setblock %d %d %d %s" % (x, y, z, s))
        top = max(st["blocks"], key=lambda b: (b[1], b[0], b[2]))
        row = {"id": spec["id"], "kind": spec["kind"], "role": spec["role"], "at": spec.get("at"), "facing": st["facing"],
               "floor_y": st["floor"], "flush": st["flush"], "columns": [list(c) for c in cols],
               "blocks": [[x, y, z, s] for x, y, z, s in st["blocks"]],
               "check": "execute if block %d %d %d %s" % (top[0], top[1], top[2], block_name(top[3]))}
        if spec["kind"] == "stall":
            row.update({"keeper_at": spec["keeper_at"], "customer": list(st["customer"]), "sells": spec["sells"]})
        report["pieces"].append(row)
    return cmds, report


def build(a):
    import ground as G
    data = load_json(DATA)
    doc = load_json(ROOT / "data" / "placements.json")
    g = G.Ground(a.source_root)
    refs = refs_of()
    out = {}
    for settlement, rec in data["towns"].items():
        if settlement not in doc["settlements"]:
            raise SystemExit("data/plaza_centres.json builds a square for %r, which data/placements.json has no "
                             "settlement for" % settlement)
        out[settlement] = plan_town(settlement, rec, doc, ground_for(settlement, g, doc, a.source_root), refs, data)
    if PACK.exists():
        shutil.rmtree(PACK)
    FUNCS.mkdir(parents=True)
    (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                      "Cobblers: town squares, their centrepieces and market stalls (tools/plaza_centre.py)"}},
                                      indent=2) + "\n", encoding="utf-8")
    if REPORT.exists():
        shutil.rmtree(REPORT)
    REPORT.mkdir(parents=True)
    names = []
    for settlement, (cmds, report) in out.items():
        cmds = function_limits.ensure_loaded(cmds)
        refused = function_limits.check_lines(cmds, settlement)
        if refused:
            raise SystemExit("%s: %d command(s) the server would refuse: %s" % (settlement, len(refused), refused[:3]))
        (FUNCS / ("%s.mcfunction" % settlement)).write_text("\n".join(cmds) + "\n", encoding="utf-8")
        (REPORT / ("%s.json" % settlement)).write_text(json.dumps(report, indent=1), encoding="utf-8")
        names.append(settlement)
        stalls = sum(1 for p in report["pieces"] if p["kind"] == "stall")
        print("%-12s %-14s %3d pieces, %d stalls, %5d blocks, cover %4.1f%%, Centre door %s steps, Mart door %s steps"
              % (settlement, report["name"], len(report["pieces"]), stalls,
                 sum(len(p["blocks"]) for p in report["pieces"]), 100 * report["coverage"],
                 report["reach"].get("pokecenter", {}).get("steps_to_square", "-"),
                 report["reach"].get("pokemart", {}).get("steps_to_square", "-")))
    (FUNCS / "index.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    checks = [p["check"] for s in names for p in load_json(REPORT / ("%s.json" % s))["pieces"]]
    (REPORT / "checks.txt").write_text("\n".join(checks) + "\n", encoding="utf-8")
    print("wrote", PACK)


def placement_steps():
    """R13's actions, listed from the committed data (not the build), so the step exists whether or not the pack is
    built here; the prepare's function-pack check fails if a town's function is missing."""
    towns = list(load_json(DATA).get("towns") or {})
    return [("fn", "cobblers:plaza_centres/%s" % s) for s in towns]


def show_map(a):
    import ground as G
    data = load_json(DATA)
    doc = load_json(ROOT / "data" / "placements.json")
    rec = dict(data["towns"][a.town], _town=a.town)
    town = Town(a.town, rec, doc, ground_for(a.town, G.Ground(a.source_root), doc, a.source_root), refs_of())
    x0, z0, x1, z1 = town.rect
    m = a.margin
    sym = {"street": "=", "street verge": "-", "street mouth": "m", "desire line": ":", "lamp": "*",
           "waystone and its pad": "W", "walked route line": "~"}
    doors = {d["front"]: d["role"][4].upper() if d["role"].startswith("poke") else "D" for d in town.doors.values()}
    built = REPORT / ("%s.json" % a.town)
    if built.is_file():
        # the last build's pieces over the mask: S stall, K keeper, c customer cell, @ centrepiece, + other piece
        for p in load_json(built)["pieces"]:
            ch = {"stall": "S", "path": "#"}.get(p["kind"], "@" if p["role"] == "centrepiece" else "+")
            for c in p["columns"]:
                doors[tuple(c)] = ch
            if p.get("keeper_at"):
                doors[(p["keeper_at"][0], p["keeper_at"][2])] = "K"
                doors[tuple(p["customer"])] = "c"
    print("%s x%d..%d z%d..%d y%d; '.' free, '=' street, '-' verge, m mouth, : desire, * lamp, W waystone pad, ~ walked "
          "line, L lot, A anchor, B building, E earthwork, N npc, s signpost, d dressing, C/M/D door fronts"
          % (a.town, x0, x1, z0, z1, town.y))
    print("      " + "".join(str(x % 100 // 10) if x % 10 == 0 else " " for x in range(x0 - m, x1 + m + 1)))
    print("      " + "".join(str(x % 10) for x in range(x0 - m, x1 + m + 1)))
    for z in range(z0 - m, z1 + m + 1):
        row = []
        for x in range(x0 - m, x1 + m + 1):
            if (x, z) in doors:
                row.append(doors[(x, z)])
                continue
            inside = x0 <= x <= x1 and z0 <= z <= z1
            why = town.why.get((x, z)) or (town.soft.get((x, z)) if inside else None)
            if why is None:
                row.append("." if inside else " ")
                continue
            ch = sym.get(why) or {"lot": "L", "anchor": "A", "building": "B", "earthwork": "E", "trader": "N",
                                  "market": "N", "seat": "N", "working": "N", "signpost": "s", "dressing": "d",
                                  "door": "a", "scene": "p", "event": "p"}.get(why.split(" ")[0], "x")
            row.append(ch if inside else ch.lower() if ch.isalpha() else ch)
        print("%5d %s" % (z, "".join(row)))


def resolve(a):
    """Authoring aid: for every piece that names `near` and no `at`, the nearest position where it fits (off the mask,
    a block clear of every other piece, a stall's customer cell free), then lamp posts where the square is still dark.
    Prints the result; --write puts it into data/plaza_centres.json. `build` checks the result independently of how it
    was found, so a hand-moved piece is held to the same rules."""
    import ground as G
    data = load_json(DATA)
    doc = load_json(ROOT / "data" / "placements.json")
    g = G.Ground(a.source_root)
    refs = refs_of()
    for settlement, rec0 in data["towns"].items():
        if a.town and settlement not in a.town:
            continue
        rec = dict(rec0, _town=settlement)
        town = Town(settlement, rec, doc, ground_for(settlement, g, doc, a.source_root), refs)
        taken, near_taken, lights = set(), set(), list(town.lamps)

        def fits(spec):
            try:
                st = seat(town, rec, spec, goods_of(data))
            except SystemExit:
                return None
            cols = set(st["cols"])
            if not st["flush"] and (cols & near_taken):
                return None
            if st.get("customer") and (st["customer"] in taken or town.blocked(*st["customer"], flush=True)):
                return None
            return st
        for spec in entries_of(rec):
            if spec["kind"] == "path":
                continue                                # a link names its own cells
            if spec.get("at") is None and spec.get("near") is None:
                raise SystemExit("%s/%s has neither at nor near" % (settlement, spec.get("id")))
            st = None
            if spec.get("at") is not None:
                st = fits(spec)
                if st is None:
                    print("%s/%s: does not fit at %s" % (settlement, spec["id"], spec["at"]))
            if st is None and spec.get("near") is not None:
                nx, nz = spec["near"]
                for x, z in sorted(((x, z) for x in range(nx - a.radius, nx + a.radius + 1)
                                    for z in range(nz - a.radius, nz + a.radius + 1)),
                                   key=lambda c: ((c[0] - nx) ** 2 + (c[1] - nz) ** 2, c)):
                    trial = dict(spec, at=[x, 0, z] if spec["kind"] == "stall" else [x, z])
                    st = fits(trial)
                    if st:
                        break
                if st is None:
                    print("%s/%s: nothing fits within %d of %s" % (settlement, spec["id"], a.radius, spec["near"]))
                    continue
            if not st["flush"]:
                taken |= set(st["cols"])
                near_taken |= grow(set(st["cols"]), 1)
            lights += lights_of(st["blocks"])
            ox, oz = st["origin"]
            target = _find(rec0, spec)
            if spec["kind"] == "stall":
                kx, kz = st["keeper"]
                target["at"] = [ox, st["floor"], oz]
                target["keeper_at"] = [kx, st["floor"], kz, YAW[st["facing"]]]
            else:
                target["at"] = [ox, oz]
            if spec["role"] == "centrepiece":
                rec0["square"]["centrepiece"] = [ox, st["floor"], oz]
            moved = math.hypot(ox - spec["near"][0], oz - spec["near"][1]) if spec.get("near") else 0.0
            print("%s/%s %s at %s%s" % (settlement, spec["id"], spec["kind"], target["at"],
                                        "  (MOVED %.0f from near)" % moved if moved > 4 else ""))
        # lamp posts where the plan's lamps and the pieces' lanterns leave the square dark
        n = len([q for q in rec0.get("pieces") or [] if q["kind"] in ("lamp_post", "flush_lamp")])
        while True:
            dark = dark_cells(town, taken, lights)
            if not dark:
                break
            best = None
            # a lamp post where one stands free, else a lamp flush in the paving on a walking line
            for kind, rise in (("lamp_post", 2), ("flush_lamp", 1)):
                for x, z in sorted(rect_cells(town.rect)):
                    if any(abs(l[0] - x) + abs(l[2] - z) < LAMP_DOUBLE for l in lights):
                        continue
                    lit = sum(1 for (cx, cz) in dark if abs(cx - x) + abs(cz - z) + rise <= LIGHT_REACH)
                    if not lit or (best is not None and lit <= best[0]):
                        continue
                    st = fits({"id": "probe", "kind": kind, "at": [x, z], "role": "furniture"})
                    if st:
                        best = (lit, x, z, st, kind)
                if best is not None:
                    break
            if best is None:
                print("%s: %d dark cell(s) and nowhere to light them from, e.g. %s" % (settlement, len(dark), dark[:3]))
                break
            n += 1
            _lit, x, z, st, kind = best
            rec0.setdefault("pieces", []).append({"id": "%s_lamp_%d" % (settlement, n), "kind": kind, "at": [x, z],
                                                  "why": "lights a part of the square no other light reaches"})
            taken |= set(st["cols"])
            near_taken |= grow(set(st["cols"]), 1)
            lights += lights_of(st["blocks"])
            print("%s: %s at %s" % (settlement, kind, [x, z]))
    if a.write:
        DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", DATA)


def _find(rec, spec):
    """The record in the town's data that `spec` was made from."""
    if spec["role"] == "centrepiece":
        return rec["centrepiece"]
    for key in ("centre_extras", "stalls", "pieces"):
        for q in rec.get(key) or []:
            if q.get("id") == spec["id"]:
                return q
    raise SystemExit("no record for %s" % spec["id"])


def check_ids(a):
    """Every id in `blocks.ids` against the client jar's blockstates."""
    import zipfile
    import town_character as TC
    jar = Path(a.jar) if a.jar else TC.default_vanilla_jar()
    if not jar or not Path(jar).is_file():
        raise SystemExit("no 1.21.1 client jar found: pass --jar")
    names = set(zipfile.ZipFile(jar).namelist())
    bad = [i for i in load_json(DATA)["blocks"]["ids"]
           if i.startswith("minecraft:") and "assets/minecraft/blockstates/%s.json" % i.split(":", 1)[1] not in names]
    print("%d ids, %d not in %s%s" % (len(load_json(DATA)["blocks"]["ids"]), len(bad), jar, (": %s" % bad) if bad else ""))
    return 1 if bad else 0


def main(argv=None):
    from terrain import env_source_root
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    m = sub.add_parser("map")
    m.add_argument("town")
    m.add_argument("--margin", type=int, default=6)
    c = sub.add_parser("check-ids")
    c.add_argument("--jar", default=None)
    r = sub.add_parser("resolve")
    r.add_argument("town", nargs="*")
    r.add_argument("--radius", type=int, default=14)
    r.add_argument("--write", action="store_true")
    for q in (b, m, c, r):
        q.add_argument("--source-root", default=None, help="the heightmap's source root (default: terrain's)")
    a = p.parse_args(argv)
    a.source_root = a.source_root or env_source_root()
    if a.cmd == "build":
        build(a)
        return 0
    if a.cmd == "map":
        show_map(a)
        return 0
    if a.cmd == "resolve":
        resolve(a)
        return 0
    return check_ids(a)


if __name__ == "__main__":
    sys.exit(main())
