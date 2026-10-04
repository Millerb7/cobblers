#!/usr/bin/env python
"""Town dressing: each town's landmark and set dressing, from data/town_dressing.json, as datapack functions.

The owner's brief (docs/world-building/TOWN_CHARACTER.md): every town gets a signature landmark that says its
purpose from a distance, and set dressing that expresses it (workshops, stalls, props, work in progress). The pieces
are authored as data: a kind from the library below, a position, a facing and a palette. This tool turns them into
one function per town, `cobblers:town_dressing/<settlement>`, in the pack `cobblers_town_dressing`.

Where a piece stands:
  ground   the heightmap, rounded (tools/ground.py), never a world. A piece stands on the highest ground under its
           footprint, and a column lower than that gets a foundation course of the piece's base block down to the
           ground, so nothing floats and nothing is buried
  clear    a piece may not touch the town's plan. Refused (the build stops and names the piece) when any cell of its
           footprint is on a street or the plaza (and the verge beside them), on a house lot or an anchor lot (the
           Centre, the Mart, the gym, an open square), within three blocks of a building's footprint, on another
           earthwork's cells or a lamp, within two blocks of the waystone, a trader, a signpost, a scene prop or a
           route event site (data/scenes.json area), on
           painted water, within four blocks of a painted tree (build/paint objects: a piece in a trunk would leave
           the crown hanging), or within three blocks of a routed leg; or when the ground under it varies by more
           than the piece allows
  order    the function runs after the towns, the pack donors and the lights (tools/reapply.py R16B), so nothing
           placed later erases it; it writes only its own cells, clearing trees and plants from them first

tools/town_dressing_audit.py checks the written function against the plan independently: it recomputes every
lot, street and building footprint from data/placements.json and the templates, and never uses this tool's mask.

The pieces use vanilla 1.21.1 blocks only (data/town_dressing.json `blocks`, each checked against the 1.21.1 client
jar's block states), and none that data/spawn_blocks.json lists as a spawn condition: dressing must not decide what
spawns in a town (docs/world-building/TOWN_CENTERS.md rule 7).

  python tools/town_dressing.py build [--source-root <root>]             # the pack, into build/datapacks
  authoring aids (they write nothing):
  python tools/town_dressing.py map <settlement> [--step 3] [--at x,z --radius 40]   # the free ground
  python tools/town_dressing.py fit <settlement> <kind> --near x,z [--facing east]   # where a piece fits
  python tools/town_dressing.py build --suggest       # for each piece that does not fit, the nearest place it does
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)

import function_limits  # noqa: E402

PACK = ROOT / "build" / "datapacks" / "cobblers_town_dressing"
FUNCS = PACK / "data" / "cobblers" / "function" / "town_dressing"
REPORT = ROOT / "derived" / "town_dressing"
DATA = ROOT / "data" / "town_dressing.json"

# clearances (blocks) the generator keeps; the audit checks the plan's own rule (no overlap at all)
STREET_VERGE = 1
LOT_MARGIN = 1
BUILDING_MARGIN = 3          # tools/place_town.py clears trees and plants two blocks round every building on a rebuild
EARTHWORK_MARGIN = 1
POINT_MARGIN = 2             # waystone, traders, signposts, scene props
LEG_MARGIN = 3
TOWN_REACH = 24              # how far past the town's recorded footprint a piece may stand


# ----------------------------------------------------------------------------------------------------------- plan
def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def town_plan(settlement):
    p = ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)
    if not p.is_file():
        raise SystemExit("no %s: run python tools/town_plan.py %s first" % (p, settlement))
    return load_json(p)


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


def building_footprints(settlement, doc):
    """{placement id: (x0, z0, x1, z1)} of every building the settlement places, as its placer seats it: a town
    building (tools/place_town.py) from its minimum corner, a pack donor (tools/place_donor.py) turned about its
    position (place_donor.footprint, the one helper every keep-clear reads)."""
    import place_donor as PD
    import town_character as TC
    templates = TC.Templates(TC.default_pack_dir(), TC.default_vanilla_jar())
    out = {}
    for q in doc["placements"]:
        if q.get("settlement") != settlement or q.get("kind") == "earthwork" or not q.get("position"):
            continue
        size, where = PD.template_size(q, templates)
        if size is None:
            raise SystemExit("%s: template %s cannot be read (%s), so its footprint is unknown; refusing to dress "
                             "round a building of unknown size" % (q["id"], q.get("template") or q.get("pack_template"), where))
        out[q["id"]] = PD.footprint(q, size)
    return out


CMD_XZ = re.compile(r"(?:fill|setblock)\s+(-?\d+)\s+-?\d+\s+(-?\d+)(?:\s+(-?\d+)\s+-?\d+\s+(-?\d+))?")


def command_columns(cmds):
    cols = set()
    for c in cmds or []:
        m = CMD_XZ.search(c)
        if not m:
            continue
        xa, za = int(m.group(1)), int(m.group(2))
        xb, zb = (int(m.group(3)), int(m.group(4))) if m.group(3) else (xa, za)
        cols |= {(x, z) for x in range(min(xa, xb), max(xa, xb) + 1) for z in range(min(za, zb), max(za, zb) + 1)}
    return cols


def leg_cells(box):
    p = ROOT / "derived" / "routes" / "critical_legs.json"
    if not p.is_file():
        raise SystemExit("no %s: run python tools/critical_legs.py first" % p)
    x0, z0, x1, z1 = box
    out = set()
    for leg in load_json(p)["legs"]:
        pts = leg.get("polyline") or []
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            n = int(max(abs(bx - ax), abs(bz - az))) + 1
            for i in range(n + 1):
                t = i / max(n, 1)
                x, z = round(ax + (bx - ax) * t), round(az + (bz - az) * t)
                if x0 <= x <= x1 and z0 <= z <= z1:
                    out.add((x, z))
    return out


def points(settlement, doc):
    """(x, z) of the waystone, the traders, the signposts and the scene props that stand in or near a settlement."""
    s = doc["settlements"][settlement]
    out = []
    way = s.get("waystone") or (s.get("plan") or {}).get("waystone")
    if way:
        out.append(tuple(way["position"][:2]))
    for t in load_json(ROOT / "data" / "traders.json").get("traders") or []:
        if t.get("settlement") == settlement and t.get("position"):
            out.append((t["position"]["x"], t["position"]["z"]))
    sp = ROOT / "derived" / "signposts.json"
    if not sp.is_file():
        raise SystemExit("no %s: run python tools/signposts.py function first" % sp)
    out += [(p["x"], p["z"]) for p in load_json(sp)["posts"]]
    for sc in load_json(ROOT / "data" / "scenes.json")["scenes"]:
        out += [(int(math.floor(q["at"][0])), int(math.floor(q["at"][2]))) for q in sc.get("props") or []]
    return out


def town_box(settlement):
    towns = {t["id"]: t for t in load_json(ROOT / "data" / "towns.json")["towns"]}
    fp = towns[settlement]["footprint"]
    return (fp["min_x"] - TOWN_REACH, fp["min_z"] - TOWN_REACH, fp["max_x"] + TOWN_REACH, fp["max_z"] + TOWN_REACH)


class Mask:
    """Every cell a piece may not touch in one settlement, and why, from the plan (never from a world)."""

    def __init__(self, settlement, doc, wet=None):
        self.settlement = settlement
        self.box = town_box(settlement)
        plan = town_plan(settlement)
        self.why = {}

        def mark(cells, why):
            for c in cells:
                self.why.setdefault(c, why)
        streets = set()
        for st in (plan.get("streets") or {}).values():
            for z, _y, xa, xb in st.get("cells") or []:
                streets |= {(x, z) for x in range(xa, xb + 1)}
        mark(streets, "street")
        if plan.get("plaza"):
            mark(rect_cells(plan["plaza"]["rect"]), "plaza")
        mark(grow(streets, STREET_VERGE) | (rect_cells(plan["plaza"]["rect"], STREET_VERGE) if plan.get("plaza") else set()),
             "street verge")
        for lot in plan.get("lots") or []:
            mark(rect_cells(lot["rect"], LOT_MARGIN), "lot %s" % lot["id"])
        for an in plan.get("anchors") or []:
            mark(rect_cells(an["rect"], LOT_MARGIN), "anchor %s" % an["id"])
        for lamp in plan.get("lamps") or []:
            mark({(lamp["at"][0], lamp["at"][2])}, "lamp")
        for bid, rect in building_footprints(settlement, doc).items():
            mark(rect_cells(rect, BUILDING_MARGIN), "building %s" % bid)
        for q in doc["placements"]:
            if q.get("settlement") == settlement and q.get("kind") == "earthwork":
                mark(grow(command_columns(q.get("commands")), EARTHWORK_MARGIN), "earthwork %s" % q["id"])
        for x, z in points(settlement, doc):
            if self.box[0] - 4 <= x <= self.box[2] + 4 and self.box[1] - 4 <= z <= self.box[3] + 4:
                mark(rect_cells((x, z, x, z), POINT_MARGIN), "waystone, trader, signpost or prop at %d,%d" % (x, z))
        mark(grow(leg_cells(self.box), LEG_MARGIN), "routed leg")
        # the route event sites (data/scenes.json area, tools/route_events.py): Route 2's Geodude cart stands just
        # north of Brock's town, and R12 builds it after this step
        for sc in load_json(ROOT / "data" / "scenes.json")["scenes"]:
            if sc.get("area"):
                a0, a1 = sc["area"]["from"], sc["area"]["to"]
                mark(rect_cells((a0[0], a0[2], a1[0], a1[2]), POINT_MARGIN), "event site %s" % sc["id"])
        self.wet = wet

    def blocked(self, x, z):
        if not (self.box[0] <= x <= self.box[2] and self.box[1] <= z <= self.box[3]):
            return "outside the town's reach"
        if (x, z) in self.why:
            return self.why[(x, z)]
        if self.wet is not None:
            return self.wet(x, z)
        return None


# ------------------------------------------------------------------------------------------------------ the pieces
DIRS = ("north", "east", "south", "west")
TURN = {"north": 0, "east": 1, "south": 2, "west": 3}


def turn_xz(x, z, facing):
    """Local (x, z), front towards -z (north), turned so the front faces `facing`."""
    k = TURN[facing]
    for _ in range(k):
        x, z = -z, x
    return x, z


def turn_state(state, facing):
    """Turn a block state's facing and axis properties with the piece."""
    k = TURN[facing]
    if not k or "[" not in state:
        return state
    name, props = state[:-1].split("[", 1)
    out = []
    for kv in props.split(","):
        key, val = kv.split("=")
        if key == "facing" and val in DIRS:
            val = DIRS[(DIRS.index(val) + k) % 4]
        elif key == "axis" and val in ("x", "z") and k % 2:
            val = "z" if val == "x" else "x"
        elif key in DIRS:
            # fence and wall connections: the side named turns too
            key = DIRS[(DIRS.index(key) + k) % 4]
        elif key == "rotation":
            val = str((int(val) + 4 * k) % 16)
        out.append("%s=%s" % (key, val))
    return "%s[%s]" % (name, ",".join(out))


def fence(name, *sides):
    """A fence or wall block joined on the named sides (local directions)."""
    return "%s[%s]" % (name, ",".join("%s=true" % s for s in sides)) if sides else name


class Piece:
    """Blocks as (local x, dy, local z, state), dy from the piece's floor (the block above its ground)."""

    def __init__(self, relief=1, base=None):
        self.blocks = []
        self.relief = relief
        self.base = base

    def put(self, x, dy, z, state):
        self.blocks.append((x, dy, z, state))

    def column(self, x, z, dy0, dy1, state):
        for dy in range(dy0, dy1 + 1):
            self.put(x, dy, z, state)


def pal(spec, key, default):
    return (spec.get("palette") or {}).get(key, default)


def piece_crates(spec, h):
    """A stack of crates and barrels, 2 by 2, one to three high."""
    p = Piece(relief=1)
    crate, barrel = pal(spec, "crate", "minecraft:stripped_spruce_wood"), "minecraft:barrel[facing=up]"
    for i, (x, z) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
        n = 1 + (h(i) % 3 if i < 2 else h(i) % 2)
        for dy in range(n):
            p.put(x, dy, z, barrel if (h(i, dy) % 3 == 0) else crate)
    return p


def piece_barrels(spec, h):
    """A row of barrels, a composter and a cauldron: the yard of a working house."""
    p = Piece(relief=1)
    goods = ["minecraft:barrel[facing=up]", "minecraft:barrel[facing=up]", "minecraft:composter",
             pal(spec, "tub", "minecraft:cauldron"), "minecraft:barrel[facing=north]"]
    for x in range(int(spec.get("length", 3))):
        p.put(x, 0, 0, goods[h(x) % len(goods)])
        if h(x, 1) % 3 == 0:
            p.put(x, 1, 0, "minecraft:barrel[facing=up]")
    return p


def piece_stall(spec, h):
    """A market stall: a counter facing the front, goods on it, four posts and an awning."""
    p = Piece(relief=1)
    wood = pal(spec, "wood", "spruce")
    counter = pal(spec, "counter", "minecraft:stripped_%s_log[axis=x]" % wood)
    post = "minecraft:%s_fence" % wood
    roof = "minecraft:%s_slab[type=bottom]" % wood
    awning = pal(spec, "awning", "minecraft:red_carpet")
    goods = spec.get("goods") or ["minecraft:decorated_pot", "minecraft:flower_pot", "minecraft:barrel[facing=up]"]
    for x in (-1, 0, 1):
        p.put(x, 0, 0, counter)
        p.put(x, 3, 0, roof)
        p.put(x, 3, 1, roof)
        p.put(x, 4, 0, awning)
        p.put(x, 4, 1, awning)
    for x in (-1, 1):
        p.column(x, 1, 0, 2, post)                     # the back posts from the ground
        p.column(x, 0, 1, 2, post)                     # the front posts stand on the counter's ends
    p.put(0, 1, 0, goods[h(0) % len(goods)])           # the goods on the counter, between the posts
    p.put(0, 0, 1, pal(spec, "stool", "minecraft:%s_stairs[facing=north]" % wood))
    return p


def piece_bench(spec, h):
    """A trade's workbench: the stations in a row, front to the street."""
    p = Piece(relief=1)
    for x, state in enumerate(spec.get("stations") or ["minecraft:crafting_table"]):
        p.put(x, 0, 0, state)
    return p


def piece_stone_pile(spec, h):
    """Cut stone waiting to be laid: blocks two high, slabs and stairs on top, a few loose."""
    p = Piece(relief=1)
    blocks = spec.get("blocks") or ["minecraft:stone_bricks", "minecraft:polished_andesite", "minecraft:smooth_stone"]
    slab = pal(spec, "slab", "minecraft:stone_brick_slab[type=bottom]")
    stair = pal(spec, "stair", "minecraft:stone_brick_stairs[facing=north]")
    L = int(spec.get("length", 3))
    for x in range(L):
        for z in (0, 1):
            n = 1 + h(x, z) % 2
            for dy in range(n):
                p.put(x, dy, z, blocks[h(x, z, dy) % len(blocks)])
            p.put(x, n, z, slab if h(x, z, 7) % 2 else stair)
    return p


def piece_log_pile(spec, h):
    """Timber or reed bundles laid crosswise, two high."""
    p = Piece(relief=1)
    log = pal(spec, "log", "minecraft:spruce_log[axis=x]")
    top = pal(spec, "top", log)
    L = int(spec.get("length", 3))
    for x in range(L):
        p.put(x, 0, 0, log)
        p.put(x, 0, 1, log)
        if 0 < x < L - 1 or h(x) % 2:
            p.put(x, 1, 0, top)
    return p


def piece_wall_in_progress(spec, h):
    """A wall being built: courses stepping down from one end, scaffolding in front, the next blocks at its foot."""
    p = Piece(relief=1)
    stone = pal(spec, "stone", "minecraft:stone_bricks")
    L, H = int(spec.get("length", 6)), int(spec.get("height", 4))
    for x in range(L):
        top = max(1, H - (x * H) // L)                # stepped: full at the start, one course at the end
        for dy in range(top):
            p.put(x, dy, 0, stone)
    for x in range(0, L, 3):                           # scaffolding towers on the front face
        for dy in range(H):
            p.put(x, dy, -1, "minecraft:scaffolding[bottom=false,distance=0,waterlogged=false]")
    p.put(L - 1, 0, -2, pal(spec, "loose", "minecraft:stone_brick_slab[type=bottom]"))
    return p


def piece_crane(spec, h):
    """A builders' derrick: a timber mast on a stone plinth, a jib out to the front, a cut block on a chain."""
    p = Piece(relief=2, base=pal(spec, "plinth", "minecraft:polished_andesite"))
    mast = pal(spec, "mast", "minecraft:stripped_spruce_log[axis=y]")
    jib = pal(spec, "jib", "minecraft:stripped_spruce_log[axis=z]")
    H, J = int(spec.get("height", 16)), int(spec.get("reach", 7))
    plinth = pal(spec, "plinth", "minecraft:polished_andesite")
    for x in (-1, 0, 1):
        for z in (-1, 0, 1):
            p.put(x, 0, z, plinth)
    p.column(0, 0, 1, H, mast)
    for z in range(-J, 3):                             # the jib, forward over the yard, a short tail behind
        p.put(0, H + 1, z, jib)
    p.put(0, H, 2, pal(spec, "counterweight", "minecraft:stone_bricks"))
    p.put(0, H - 1, 2, pal(spec, "counterweight", "minecraft:stone_bricks"))
    drop = int(spec.get("drop", 8))
    p.column(0, -J, H - drop + 1, H, "minecraft:chain[axis=y]")
    p.put(0, H - drop, -J, pal(spec, "load", "minecraft:chiseled_stone_bricks"))
    for z in (-2, -4):                                 # the brace under the jib
        p.put(0, H, z, "minecraft:spruce_fence")
    p.put(0, H + 2, 0, "minecraft:lantern[hanging=false]")
    return p


def piece_kiln(spec, h):
    """A lime kiln: a squat stone block with a furnace mouth to the front and smoke from its top."""
    p = Piece(relief=1)
    stone = pal(spec, "stone", "minecraft:cobblestone")
    trim = pal(spec, "trim", "minecraft:stone_bricks")
    for x in (-1, 0, 1):
        for z in (-1, 0, 1):
            for dy in range(3):
                p.put(x, dy, z, trim if (dy == 2 or (abs(x) == 1 and abs(z) == 1)) else stone)
    p.put(0, 0, -1, pal(spec, "mouth", "minecraft:blast_furnace[facing=north,lit=false]"))
    p.put(0, 3, 0, "minecraft:campfire[lit=true,signal_fire=false,facing=north,waterlogged=false]")
    return p


def piece_banner_pole(spec, h):
    """A flag on a pole: the rescue depot's red flag, a garrison's colours."""
    p = Piece(relief=1)
    post = pal(spec, "post", "minecraft:spruce_fence")
    H = int(spec.get("height", 4))
    p.column(0, 0, 0, H - 1, post)
    p.put(0, H, 0, "%s[rotation=0]" % pal(spec, "banner", "minecraft:red_banner"))
    return p


def piece_rope_coils(spec, h):
    """Rope and tackle: chains laid over barrels, a coil on a slab."""
    p = Piece(relief=1)
    p.put(0, 0, 0, "minecraft:barrel[facing=up]")
    p.put(1, 0, 0, pal(spec, "slab", "minecraft:spruce_slab[type=bottom]"))
    p.put(0, 1, 0, "minecraft:chain[axis=x]")
    p.put(1, 0, 1, "minecraft:barrel[facing=up]")
    p.put(1, 1, 1, "minecraft:chain[axis=z]")
    return p


def piece_stilt_tower(spec, h):
    """A watchtower on stilts: four legs, a railed platform, a roof and a lantern, a ladder up one leg."""
    p = Piece(relief=2)
    leg = pal(spec, "leg", "minecraft:mangrove_log[axis=y]")
    wood = pal(spec, "wood", "mangrove")
    H = int(spec.get("height", 10))
    for x in (-1, 1):
        for z in (-1, 1):
            p.column(x, z, 0, H + 3, leg)
    for x in (-2, -1, 0, 1, 2):
        for z in (-2, -1, 0, 1, 2):
            if abs(x) != 1 or abs(z) != 1:                  # the legs run through the platform
                p.put(x, H, z, "minecraft:%s_planks" % wood)
            p.put(x, H + 4, z, "minecraft:%s_slab[type=bottom]" % wood)
    # the rail: the north, west and east edges between the legs, and the south-west corner; the south edge east of it
    # is open, where the ladder arrives
    for x in (-2, 0, 2):
        p.put(x, H + 1, -2, fence("minecraft:%s_fence" % wood, "east", "west"))
    for x in (-2, 2):
        p.put(x, H + 1, 0, fence("minecraft:%s_fence" % wood, "north", "south"))
    p.put(-2, H + 1, 2, fence("minecraft:%s_fence" % wood, "north"))
    p.put(0, H + 3, 0, "minecraft:lantern[hanging=true]")
    # the ladder climbs the south-east leg's south face, and comes up through a gap in the platform beside it
    for dy in range(0, H):
        p.put(1, dy, 2, "minecraft:ladder[facing=south]")
    p.blocks = [b for b in p.blocks if not (b[0] == 1 and b[2] == 2 and b[1] == H and "planks" in b[3])]
    p.put(1, H, 2, "minecraft:ladder[facing=south]")
    return p


def piece_rack(spec, h):
    """A drying rack: two posts and a rail, bundles standing against it and laid along its top."""
    p = Piece(relief=1)
    wood = pal(spec, "wood", "spruce")
    L = int(spec.get("length", 4))
    post = "minecraft:%s_fence" % wood
    for x in (0, L - 1):
        p.column(x, 0, 0, 1, post)
    for x in range(L):
        sides = [s for s, ok in (("west", x > 0), ("east", x < L - 1)) if ok]
        p.put(x, 2, 0, fence(post, *sides))
    hang = pal(spec, "hang", "minecraft:bamboo_block[axis=y]")
    for x in range(1, L - 1):
        p.put(x, 0, 0, hang)
    for x in range(L):
        if h(x) % 2 == 0:
            p.put(x, 0, -1, pal(spec, "foot", "minecraft:bamboo_block[axis=y]"))
    return p


def piece_smoke_rack(spec, h):
    """Fish or eels curing over a fire: a fire in a fence frame under a slab roof."""
    p = Piece(relief=1)
    wood = pal(spec, "wood", "mangrove")
    for x in (-1, 1):
        for z in (-1, 1):
            p.column(x, z, 0, 2, "minecraft:%s_fence" % wood)
    for x in (-1, 0, 1):
        for z in (-1, 0, 1):
            p.put(x, 3, z, "minecraft:%s_slab[type=bottom]" % wood)
    p.put(0, 0, 0, "minecraft:campfire[lit=true,signal_fire=false,facing=north,waterlogged=false]")
    p.put(0, 2, 0, pal(spec, "curing", "minecraft:dried_kelp_block"))
    return p


def piece_target_post(spec, h):
    """A training target on a post."""
    p = Piece(relief=1)
    p.column(0, 0, 0, 1, pal(spec, "post", "minecraft:dark_oak_fence"))
    p.put(0, 2, 0, "minecraft:target")
    return p


def piece_casts(spec, h):
    """The trackers' board: casts of prints in pots on a mud-brick shelf."""
    p = Piece(relief=1)
    L = int(spec.get("length", 3))
    for x in range(L):
        p.put(x, 0, 0, pal(spec, "shelf", "minecraft:mud_bricks"))
        p.put(x, 1, 0, "minecraft:decorated_pot" if h(x) % 2 else "minecraft:flower_pot")
    return p


def piece_beacon(spec, h):
    """A signal beacon: a stone tower with a fire burning at its head, a smoke column seen for miles."""
    p = Piece(relief=2)
    body, band = pal(spec, "body", "minecraft:polished_granite"), pal(spec, "band", "minecraft:terracotta")
    top = pal(spec, "wall", "minecraft:granite_wall")
    H = int(spec.get("height", 11))
    for dy in range(H):
        for x in (-1, 0, 1):
            for z in (-1, 0, 1):
                p.put(x, dy, z, band if dy % 4 == 3 else body)
    for x in (-1, 1):
        for z in (-1, 1):
            p.put(x, H, z, top)
    p.put(0, H, 0, "minecraft:hay_block[axis=y]")          # under a campfire, a hay bale makes signal smoke
    p.put(0, H + 1, 0, "minecraft:campfire[lit=true,signal_fire=true,facing=north,waterlogged=false]")
    return p


def piece_instrument_mast(spec, h):
    """A crater instrument tower: a climbable lattice of basalt legs round a blackstone core, girdered every five
    blocks, a railed deck, a copper dish and feed horn aimed at the cone, and a copper antenna with a light and rods.
    (Rebuilt 2026-09-27: the first, a 3 by 3 stump twelve high, the owner found underwhelming.)"""
    p = Piece(relief=2)
    body = pal(spec, "body", "minecraft:polished_blackstone_bricks")
    leg = "minecraft:polished_basalt[axis=y]"
    girder = "minecraft:polished_blackstone_brick_slab[type=top]"
    H = int(spec.get("height", 22))
    ring = [(x, z) for x in range(-2, 3) for z in range(-2, 3) if max(abs(x), abs(z)) == 2]
    for x in range(-2, 3):
        for z in range(-2, 3):
            p.put(x, 0, z, "minecraft:chiseled_polished_blackstone" if abs(x) == 2 and abs(z) == 2 else body)
    for x in (-2, 2):
        for z in (-2, 2):
            p.column(x, z, 1, H, leg)
    p.column(0, 0, 1, H + 1, body)                                   # the core, up through the deck
    for dy in range(5, H, 5):                                        # girders between the legs
        for x, z in ring:
            if abs(x) != 2 or abs(z) != 2:
                p.put(x, dy, z, girder)
    for dy in range(1, H + 2):                                       # the ladder, on the core's back face
        p.put(0, dy, 1, "minecraft:ladder[facing=south]")
    for x in range(-2, 3):                                           # the deck, open where the ladder comes up
        for z in range(-2, 3):
            if (x, z) not in ((0, 0), (0, 1)):
                p.put(x, H + 1, z, body)
    for x, z in ring:                                                # the rail: posts, lanterns at the back corners
        if z == -2 and abs(x) < 2:
            continue                                                 # the dish stands at the front
        if z == 2 and abs(x) == 2:
            p.put(x, H + 2, z, "minecraft:lantern[hanging=false]")
        else:
            p.put(x, H + 2, z, "minecraft:polished_blackstone_wall")
    # the dish: a copper disc on the deck's front edge, the feed horn out in front, a strut back to the core
    for x in range(-2, 3):
        for dy in range(H + 2, H + 7):
            r = max(abs(x), abs(dy - (H + 4)))
            if r == 2 and abs(x) == 2 and abs(dy - (H + 4)) == 2:
                continue                                             # round the corners off
            p.put(x, dy, -2, "minecraft:waxed_copper_block" if r == 2 else "minecraft:waxed_exposed_copper")
    p.put(0, H + 4, -1, "minecraft:waxed_cut_copper")
    p.put(0, H + 4, -3, "minecraft:end_rod[facing=north]")
    # the antenna: copper up from the core, a light, rods
    for dy in range(H + 2, H + 7):
        p.put(0, dy, 0, "minecraft:waxed_copper_grate" if dy % 2 else "minecraft:waxed_cut_copper")
    p.put(0, H + 7, 0, "minecraft:pearlescent_froglight[axis=y]")
    p.column(0, 0, H + 8, H + 10, "minecraft:end_rod[facing=up]")
    return p


def piece_core_rack(spec, h):
    """Core samples standing in a frame: columns of the rim's layers, labelled by a lectern."""
    p = Piece(relief=1)
    layers = spec.get("layers") or ["minecraft:basalt[axis=y]", "minecraft:tuff", "minecraft:blackstone",
                                    "minecraft:calcite", "minecraft:smooth_basalt"]
    L = int(spec.get("length", 4))
    for x in range(L):
        for dy in range(3):
            p.put(x, dy, 0, layers[(x + dy + h(x)) % len(layers)])
    p.put(-1, 0, 0, pal(spec, "label", "minecraft:lectern[facing=north,has_book=false,powered=false]"))
    return p


def piece_field_lab(spec, h):
    """A field laboratory under a canopy: brewing stands, a cauldron, a survey table."""
    p = Piece(relief=1)
    wood = pal(spec, "wood", "acacia")
    p.put(-1, 0, 0, "minecraft:%s_planks" % wood)
    p.put(-1, 1, 0, "minecraft:brewing_stand")
    p.put(0, 0, 0, "minecraft:cauldron")
    p.put(1, 0, 0, "minecraft:cartography_table")
    p.put(1, 1, 0, "minecraft:flower_pot")
    for x in (-2, 2):
        for z in (0, 1):
            p.column(x, z, 0, 2, "minecraft:%s_fence" % wood)
    for x in (-2, -1, 0, 1, 2):
        for z in (0, 1):
            p.put(x, 3, z, "minecraft:%s_slab[type=bottom]" % wood)
    return p


def piece_fumarole(spec, h):
    """A vent in the rock: a fire smoking inside a knee-high ring of basalt and blackstone, on blackstone ground."""
    p = Piece(relief=1)
    for x in (-1, 0, 1):
        for z in (-1, 0, 1):
            p.put(x, -1, z, "minecraft:blackstone")          # the ground round the vent, scorched
            if (x, z) != (0, 0):
                p.put(x, 0, z, "minecraft:smooth_basalt" if h(x, z) % 2 else "minecraft:basalt[axis=y]")
                if h(x, z, 1) % 3 == 0:
                    p.put(x, 1, z, "minecraft:polished_blackstone_slab[type=bottom]")
    p.put(0, 0, 0, "minecraft:campfire[lit=true,signal_fire=false,facing=north,waterlogged=false]")
    return p


def piece_bonfire(spec, h):
    """A big open fire (a cold town's): five lit campfires in a cross inside a knee-high ring of stone, split spruce
    log-ends on the diagonals, stone-brick slabs at the ring's corners."""
    p = Piece(relief=1)
    stone, log = pal(spec, "stone", "minecraft:cobblestone"), pal(spec, "log", "minecraft:spruce_log[axis=y]")
    fire = "minecraft:campfire[lit=true,signal_fire=false,facing=north,waterlogged=false]"
    for x in range(-2, 3):
        for z in range(-2, 3):
            edge = abs(x) == 2 or abs(z) == 2
            if edge and abs(x) == 2 and abs(z) == 2:
                p.put(x, 0, z, "minecraft:stone_brick_slab[type=bottom,waterlogged=false]")
            elif edge:
                p.put(x, 0, z, stone)
            elif x == 0 or z == 0:
                p.put(x, 0, z, fire)
            else:
                p.put(x, 0, z, log)
    return p


def piece_spire(spec, h):
    """A listening spire: a white shaft tapering from three by three to a cross to a single column, lit slots of purple
    glass in its lower stage, two purple listening rings up the shaft, and a glowing purple lens with rods at its head.
    (Rebuilt 2026-09-27: the first, a single quartz column eighteen high, the owner found underwhelming.)"""
    p = Piece(relief=2)
    H = int(spec.get("height", 30))
    T1, T2 = max(6, H * 9 // 20), max(10, H * 3 // 4)             # where the 3 by 3 and the cross end
    pillar, face = "minecraft:quartz_pillar[axis=y]", "minecraft:smooth_quartz"
    glass = "minecraft:purple_stained_glass"
    for x in range(-2, 3):                                          # the stepped plinth
        for z in range(-2, 3):
            p.put(x, 0, z, pal(spec, "plinth", "minecraft:polished_diorite"))
    for x in range(-1, 2):
        for z in range(-1, 2):
            p.put(x, 1, z, "minecraft:calcite")
    for x in (-2, 2):
        for z in (-2, 2):
            p.put(x, 1, z, "minecraft:amethyst_cluster[facing=up,waterlogged=false]")
    for dy in range(2, T1 + 1):                                     # the lower stage, 3 by 3
        slot = dy % 6 in (3, 4, 5)
        for x in range(-1, 2):
            for z in range(-1, 2):
                if (x, z) == (0, 0):
                    p.put(x, dy, z, "minecraft:sea_lantern" if slot else pillar)
                elif abs(x) == 1 and abs(z) == 1:
                    p.put(x, dy, z, pillar)
                else:
                    p.put(x, dy, z, glass if slot else ("minecraft:chiseled_quartz_block" if dy % 6 == 0 else face))
    for x in range(-1, 2):                                          # the collar
        for z in range(-1, 2):
            p.put(x, T1 + 1, z, "minecraft:chiseled_quartz_block")
    arms = ((0, -1), (1, 0), (0, 1), (-1, 0))
    for dy in range(T1 + 2, T2 + 1):                                # the middle stage, a cross
        p.put(0, dy, 0, pillar)
        for x, z in arms:
            p.put(x, dy, z, "minecraft:quartz_bricks")
    p.column(0, 0, T2 + 1, H, pillar)                               # the upper stage, one column

    def listening_ring(dy, spokes):
        for x in range(-2, 3):
            for z in range(-2, 3):
                if max(abs(x), abs(z)) == 2 and not (abs(x) == 2 and abs(z) == 2):
                    p.put(x, dy, z, glass)
        if spokes:
            for (x, z), f in zip(arms, ("north", "east", "south", "west")):
                p.put(x, dy, z, "minecraft:end_rod[facing=%s]" % f)
    listening_ring((T1 + T2) // 2, False)                           # round the cross
    listening_ring((T2 + H) // 2, True)                             # round the single column, on rods
    for x in range(-1, 2):                                          # the lens: a lit purple orb on a calcite seat
        for z in range(-1, 2):
            p.put(x, H + 1, z, "minecraft:calcite")
            for dy in (H + 2, H + 3, H + 4):
                p.put(x, dy, z, glass)
    p.put(0, H + 3, 0, "minecraft:sea_lantern")
    for (x, z), f in zip(((0, -2), (2, 0), (0, 2), (-2, 0)), ("north", "east", "south", "west")):
        p.put(x, H + 3, z, "minecraft:end_rod[facing=%s]" % f)
    p.put(0, H + 5, 0, "minecraft:chiseled_quartz_block")
    p.column(0, 0, H + 6, H + 8, "minecraft:end_rod[facing=up]")
    return p


def piece_memory_stone(spec, h):
    """A memory stone: a polished plinth carrying a stone of the kind the Rift leaves, and a crystal."""
    p = Piece(relief=1)
    p.put(0, 0, 0, pal(spec, "plinth", "minecraft:polished_diorite"))
    p.put(0, 1, 0, pal(spec, "stone", "minecraft:chiseled_quartz_block"))
    p.put(0, 2, 0, "minecraft:amethyst_cluster[facing=up,waterlogged=false]")
    return p


def piece_reading_stall(spec, h):
    """A reading stall: shelves of records, a lectern, a bench, under a slab roof."""
    p = Piece(relief=1)
    wood = pal(spec, "wood", "birch")
    p.put(-1, 0, 0, "minecraft:bookshelf")
    p.put(-1, 1, 0, "minecraft:chiseled_bookshelf[facing=north,slot_0_occupied=true,slot_1_occupied=false,"
                    "slot_2_occupied=true,slot_3_occupied=true,slot_4_occupied=false,slot_5_occupied=true]")
    p.put(0, 0, 0, "minecraft:lectern[facing=north,has_book=false,powered=false]")
    p.put(1, 0, 0, "minecraft:bookshelf")
    p.put(0, 0, -1, "minecraft:%s_stairs[facing=south]" % wood)
    for x in (-1, 1):
        p.put(x, 2, 0, "minecraft:%s_fence" % wood)
    for x in (-1, 0, 1):
        p.put(x, 3, 0, "minecraft:%s_slab[type=bottom]" % wood)
        p.put(x, 3, -1, "minecraft:%s_slab[type=bottom]" % wood)
    p.put(0, 2, 0, "minecraft:lantern[hanging=true]")
    return p


def piece_instrument_stand(spec, h):
    """An instrument on a stand: a copper tube on a calcite post, aimed along the rows."""
    p = Piece(relief=1)
    p.put(0, 0, 0, pal(spec, "base", "minecraft:calcite"))
    p.put(0, 1, 0, pal(spec, "post", "minecraft:diorite_wall"))
    p.put(0, 2, 0, pal(spec, "head", "minecraft:waxed_cut_copper"))
    p.put(0, 2, -1, "minecraft:end_rod[facing=north]")
    return p


def piece_palisade(spec, h):
    """A palisade: stakes of different heights, fenced tops."""
    p = Piece(relief=1)
    stake = pal(spec, "stake", "minecraft:stripped_spruce_log[axis=y]")
    L = int(spec.get("length", 6))
    for x in range(L):
        n = 2 + h(x) % 2
        p.column(x, 0, 0, n - 1, stake)
        p.put(x, n, 0, "minecraft:spruce_fence")
    return p


def piece_sandbags(spec, h):
    """A sandbag wall, an L two courses high."""
    p = Piece(relief=1)
    bag, cap = pal(spec, "bag", "minecraft:packed_mud"), pal(spec, "cap", "minecraft:mud_brick_slab[type=bottom]")
    L = int(spec.get("length", 5))
    for x in range(L):
        p.put(x, 0, 0, bag)
        p.put(x, 1, 0, cap)
    for z in (1, 2):
        p.put(0, 0, z, bag)
        p.put(0, 1, z, cap)
    return p


PIECES = {
    "crates": piece_crates, "barrels": piece_barrels, "stall": piece_stall, "bench": piece_bench,
    "stone_pile": piece_stone_pile, "log_pile": piece_log_pile, "wall_in_progress": piece_wall_in_progress,
    "crane": piece_crane, "kiln": piece_kiln, "banner_pole": piece_banner_pole, "rope_coils": piece_rope_coils,
    "stilt_tower": piece_stilt_tower, "rack": piece_rack, "smoke_rack": piece_smoke_rack,
    "target_post": piece_target_post, "casts": piece_casts, "beacon": piece_beacon,
    "instrument_mast": piece_instrument_mast, "core_rack": piece_core_rack, "field_lab": piece_field_lab,
    "fumarole": piece_fumarole, "spire": piece_spire, "memory_stone": piece_memory_stone,
    "reading_stall": piece_reading_stall, "instrument_stand": piece_instrument_stand, "palisade": piece_palisade,
    "sandbags": piece_sandbags, "bonfire": piece_bonfire,
}


def h32(*v):
    x = 0x9E3779B9
    for i, t in enumerate(v):
        x ^= (int(t) * (73856093, 19349663, 83492791, 2654435761)[i % 4]) & 0xFFFFFFFF
        x = (x * 0x5BD1E995) & 0xFFFFFFFF
        x ^= x >> 15
    return x


def block_name(state):
    return state.split("[", 1)[0].split("{", 1)[0]


# --------------------------------------------------------------------------------------------------------- the build
def place(spec, settlement, ground, mask):
    """[(x, y, z, state)] for one piece, seated on the ground, or SystemExit naming what is in the way."""
    kind = spec["kind"]
    if kind not in PIECES:
        raise SystemExit("%s: unknown piece kind %r (known: %s)" % (spec["id"], kind, ", ".join(sorted(PIECES))))
    ox, oz = spec["at"]
    facing = spec.get("facing", "north")
    piece = PIECES[kind](spec, lambda *v: h32(ox, oz, *v))
    last = {}
    for x, dy, z, s in piece.blocks:                   # a position written twice keeps its last block
        last[(x, dy, z)] = s
    world = [(ox + turn_xz(x, z, facing)[0], dy, oz + turn_xz(x, z, facing)[1], turn_state(s, facing))
             for (x, dy, z), s in last.items()]
    cols = sorted({(x, z) for x, _dy, z, _s in world})
    for x, z in cols:
        why = mask.blocked(x, z)
        if why:
            raise SystemExit("%s/%s: cell (%d, %d) is not free: %s" % (settlement, spec["id"], x, z, why))
    g = {c: ground(*c) for c in cols}
    relief = max(g.values()) - min(g.values())
    if relief > piece.relief:
        raise SystemExit("%s/%s: the ground under it varies by %d blocks (this piece allows %d): move it"
                         % (settlement, spec["id"], relief, piece.relief))
    floor = max(g.values()) + 1
    out = []
    # the course under a column on falling ground: the piece's own plinth, else the town's stone, else packed mud
    base = piece.base or spec.get("foundation") or "minecraft:packed_mud"
    footing = {}
    for x, dy, z, s in world:
        footing[(x, z)] = min(footing.get((x, z), dy), dy)
    for (x, z), low in footing.items():
        # a foundation course from the ground up to the floor, under every column that stands on the floor; a
        # column whose lowest block is higher (a jib, a hanging load, an awning) overhangs and stands on nothing
        if low <= 0:
            for y in range(g[(x, z)] + 1, floor + low):
                out.append((x, y, z, base))
    out += [(x, floor + dy, z, s) for x, dy, z, s in world]
    return out, floor


def nearest_fit(spec, settlement, ground, mask, radius=16, taken=()):
    """The nearest position to spec["at"] where the piece fits, or None: an authoring aid (build --suggest)."""
    ox, oz = spec["at"]
    for x, z in sorted(((x, z) for x in range(ox - radius, ox + radius + 1) for z in range(oz - radius, oz + radius + 1)),
                       key=lambda c: (c[0] - ox) ** 2 + (c[1] - oz) ** 2):
        try:
            blocks, _f = place(dict(spec, at=[x, z]), settlement, ground, mask)
        except SystemExit:
            continue
        if not any((b[0], b[2]) in taken for b in blocks):
            return [x, z]
    return None


def commands_for(settlement, entries, ground, mask, allowed_blocks, suggest=None):
    cmds = ["# Generated by tools/town_dressing.py from data/town_dressing.json (%s). Re-run to rebuild." % settlement]
    report = {"settlement": settlement, "pieces": []}
    taken = {}
    for spec in entries:
        if suggest is not None:
            try:
                place(spec, settlement, ground, mask)
                clash = any((b[0], b[2]) in taken for b in place(spec, settlement, ground, mask)[0])
            except SystemExit as e:
                clash = str(e)
            if clash:
                at = nearest_fit(spec, settlement, ground, mask, taken=taken)
                suggest.append((settlement, spec["id"], spec["at"], at, clash))
                if at is None:
                    continue
                spec = dict(spec, at=at)
        blocks, floor = place(spec, settlement, ground, mask)
        bad = sorted({block_name(s) for _x, _y, _z, s in blocks} - allowed_blocks)
        if bad:
            raise SystemExit("%s/%s: blocks not in data/town_dressing.json `blocks`: %s" % (settlement, spec["id"], bad))
        cols = sorted({(x, z) for x, _y, z, _s in blocks})
        for c in cols:
            if c in taken:
                raise SystemExit("%s/%s overlaps %s at %s" % (settlement, spec["id"], taken[c], c))
        for c in cols:
            taken[c] = spec["id"]
        ys = [y for _x, y, _z, _s in blocks]
        xs, zs = [c[0] for c in cols], [c[1] for c in cols]
        cmds.append("# %s: %s (%s)" % (spec["id"], spec["kind"], spec.get("why", "")[:120]))
        # trees and plants out of the piece's own columns first, from its floor to over its top
        for x0, x1, z in _runs(cols):
            cmds.append("fill %d %d %d %d %d %d minecraft:air replace #minecraft:replaceable" % (x0, floor - 1, z, x1, max(ys) + 1, z))
            for tag in ("#minecraft:logs", "#minecraft:leaves"):
                cmds.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, floor, z, x1, max(ys) + 2, z, tag))
        # the lowest blocks first, so a ladder or a lantern has what it hangs on
        for x, y, z, s in sorted(blocks, key=lambda b: (b[1], b[0], b[2])):
            cmds.append("setblock %d %d %d %s" % (x, y, z, s))
        top = max(blocks, key=lambda b: (b[1], b[0], b[2]))
        report["pieces"].append({"id": spec["id"], "kind": spec["kind"], "at": spec["at"], "facing": spec.get("facing", "north"),
                                 "floor_y": floor, "columns": cols, "blocks": len(blocks),
                                 "box": [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)],
                                 # one block to test in the world after the run: the piece's highest
                                 "check": "execute if block %d %d %d %s" % (top[0], top[1], top[2], block_name(top[3]))})
    return cmds, report


def _runs(cols):
    rows = {}
    for x, z in cols:
        rows.setdefault(z, []).append(x)
    out = []
    for z, xs in sorted(rows.items()):
        xs.sort()
        a = b = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == b + 1:
                b = x
                continue
            out.append((a, b, z))
            if x is not None:
                a = b = x
    return out


TREE_REACH = 4              # a painted tree's trunk and the lower crown round it


def wet_fn(ground_obj):
    """(x, z) -> "painted water" or "painted tree" (within TREE_REACH of one), from build/paint, else None.

    The export paints trees as objects (tools/paint_maps.py objects_*.png, one pixel per trunk): a piece set into one
    would cut its trunk and leave its crown hanging, so pieces keep off them."""
    import numpy as np
    from PIL import Image
    import elder_trees
    wet = elder_trees.painted_water(ground_obj.heights, ground_obj.world)
    man = load_json(ROOT / "build" / "paint" / "manifest.json")
    trees = np.zeros(wet.shape, dtype=bool)
    for layer in man.get("objects") or []:
        trees |= np.asarray(Image.open(ROOT / "build" / "paint" / layer["map"])) > 0
    ox, oz = ground_obj.ox, ground_obj.oz

    def at(x, z):
        if wet[z - oz, x - ox]:
            return "painted water"
        if trees[max(0, z - oz - TREE_REACH):z - oz + TREE_REACH + 1, max(0, x - ox - TREE_REACH):x - ox + TREE_REACH + 1].any():
            return "painted tree"
        return None
    return at


def build(a):
    import ground as G
    data = load_json(DATA)
    allowed = set(data["blocks"]["ids"])
    doc = load_json(ROOT / "data" / "placements.json")
    g = G.Ground(a.source_root)
    wet = wet_fn(g)
    if PACK.exists():
        import shutil
        shutil.rmtree(PACK)
    FUNCS.mkdir(parents=True)
    suggest = [] if getattr(a, "suggest", False) else None
    (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description":
                                      "Cobblers: town landmarks and set dressing (tools/town_dressing.py)"}}, indent=2) + "\n",
                                      encoding="utf-8")
    REPORT.mkdir(parents=True, exist_ok=True)
    names = []
    for settlement, town in data["towns"].items():
        if settlement not in doc["settlements"]:
            raise SystemExit("data/town_dressing.json dresses %r, which data/placements.json has no plan for" % settlement)
        if doc["settlements"][settlement].get("ground"):
            raise SystemExit("%s stands on %s ground; the dressing seats pieces on the heightmap only"
                             % (settlement, doc["settlements"][settlement]["ground"]))
        mask = Mask(settlement, doc, wet)
        entries = ([dict(town["landmark"], id=town["landmark"].get("id", "landmark"))] if town.get("landmark") else []) \
            + list(town.get("pieces") or [])
        if town.get("foundation"):
            # the course under a piece standing on falling ground, in the town's own stone
            entries = [dict(e, foundation=e.get("foundation") or town["foundation"]) for e in entries]
        cmds, report = commands_for(settlement, entries, g, mask, allowed, suggest)
        cmds = function_limits.ensure_loaded(cmds)
        refused = function_limits.check_lines(cmds, settlement)
        if refused:
            raise SystemExit("%s: %d command(s) the server would refuse: %s" % (settlement, len(refused), refused[:3]))
        (FUNCS / ("%s.mcfunction" % settlement)).write_text("\n".join(cmds) + "\n", encoding="utf-8")
        (REPORT / ("%s.json" % settlement)).write_text(json.dumps(report, indent=1), encoding="utf-8")
        names.append(settlement)
        print("%-12s %3d pieces, %5d blocks, %5d commands" % (settlement, len(report["pieces"]),
                                                              sum(p["blocks"] for p in report["pieces"]), len(cmds)))
    (FUNCS / "index.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    # the spot checks for after the run, one per piece, each answered "Test passed" when the piece stands
    checks = []
    for s in names:
        checks += [q["check"] for q in load_json(REPORT / ("%s.json" % s))["pieces"]]
    (REPORT / "checks.txt").write_text("\n".join(checks) + "\n", encoding="utf-8")
    if suggest:
        for s, pid, old, new, why in suggest:
            print("MOVE %s/%s from %s to %s (%s)" % (s, pid, old, new, why))
        import shutil
        shutil.rmtree(PACK)
        raise SystemExit("%d piece(s) do not fit where data/town_dressing.json puts them: nothing written" % len(suggest))
    print("wrote", PACK)


def show_map(a):
    import ground as G
    doc = load_json(ROOT / "data" / "placements.json")
    g = G.Ground(a.source_root)
    mask = Mask(a.settlement, doc, wet_fn(g))
    x0, z0, x1, z1 = mask.box
    if a.at:
        cx, cz = (int(v) for v in a.at.split(","))
        x0, z0, x1, z1 = cx - a.radius, cz - a.radius, cx + a.radius, cz + a.radius
    sym = {"street": "=", "plaza": "#", "street verge": "-", "lamp": "*", "routed leg": "~", "painted water": "w",
           "painted tree": "t", "outside the town's reach": " "}
    st = a.step
    print("map of %s x%d..%d z%d..%d, one character every %d blocks; on free cells the ground's y mod 10, else "
          "= street, # plaza, - verge, L lot, A anchor, B building, E earthwork, ~ leg, w water, t tree, x other"
          % (a.settlement, x0, x1, z0, z1, st))
    print("      " + "".join(str(x // 10 % 100).rjust(2)[0] if (x - x0) % (10 * st) == 0 else " " for x in range(x0, x1 + 1, st)))
    print("      " + "".join(str(x // 10 % 10) if (x - x0) % (10 * st) == 0 else " " for x in range(x0, x1 + 1, st)))
    for z in range(z0, z1 + 1, st):
        row = []
        for x in range(x0, x1 + 1, st):
            why = mask.blocked(x, z)
            if why is None:
                row.append(str(g(x, z) % 10))
            else:
                row.append(sym.get(why, {"lot": "L", "anchor": "A", "building": "B", "earthwork": "E"}.get(why.split(" ")[0], "x")))
        print("%5d %s" % (z, "".join(row)))


def fit(a):
    """The nearest position to --near where a piece fits, for authoring data/town_dressing.json."""
    import ground as G
    doc = load_json(ROOT / "data" / "placements.json")
    g = G.Ground(a.source_root)
    mask = Mask(a.settlement, doc, wet_fn(g))
    spec = json.loads(a.spec) if a.spec else {}
    spec.update({"id": "fit", "kind": a.kind, "facing": a.facing})
    cx, cz = (int(v) for v in a.near.split(","))
    cands = sorted(((x, z) for x in range(cx - a.radius, cx + a.radius + 1) for z in range(cz - a.radius, cz + a.radius + 1)),
                   key=lambda c: (c[0] - cx) ** 2 + (c[1] - cz) ** 2)
    found = 0
    for x, z in cands:
        try:
            _b, floor = place(dict(spec, at=[x, z]), a.settlement, g, mask)
        except SystemExit:
            continue
        print("at [%d, %d] facing %s: floor y%d, %.0f from %d,%d" % (x, z, a.facing, floor, math.hypot(x - cx, z - cz), cx, cz))
        found += 1
        if found >= a.count:
            return 0
    print("nothing fits within %d of %d,%d" % (a.radius, cx, cz))
    return 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("build")
    q.add_argument("--source-root", default=env_source_root())
    q.add_argument("--suggest", action="store_true",
                   help="authoring: for a piece that does not fit, print the nearest place it does; writes nothing")
    q = sub.add_parser("map")
    q.add_argument("settlement")
    q.add_argument("--source-root", default=env_source_root())
    q.add_argument("--at")
    q.add_argument("--radius", type=int, default=40)
    q.add_argument("--step", type=int, default=1)
    q = sub.add_parser("fit")
    q.add_argument("settlement")
    q.add_argument("kind")
    q.add_argument("--near", required=True)
    q.add_argument("--facing", default="north")
    q.add_argument("--spec", help="extra piece fields as JSON, e.g. '{\"length\": 5}'")
    q.add_argument("--radius", type=int, default=30)
    q.add_argument("--count", type=int, default=3)
    q.add_argument("--source-root", default=env_source_root())
    a = p.parse_args(argv)
    return {"build": build, "map": show_map, "fit": fit}[a.cmd](a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
