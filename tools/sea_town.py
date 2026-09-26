#!/usr/bin/env python
"""The sea town ("Pacifidlog", working name): a raft town in the Sound, from data/sea_town.json.

docs/world-building/LONG_ISLE.md section 4 is the design; data/sea_town.json is the authored layout (rafts, bridges,
walks, buildings, stations, racks, signs, lamps' rules, the Centre and the Mart). This tool translates it; it decides
nothing the data does not say. It writes, into data/placements.json:

  the settlement   `sea_town`, with "ground": "sea_deck" (tools/ground.py lays the deck over the heightmap inside the
                   town, so tools/town_plan.py and tools/place_town.py seat the Centre and the Mart on the deck at the
                   sea level, never on the seabed), a plan whose plaza is the town square, the two service anchors and
                   the discovery waystone
  two services     the CobbleTowns Centre and Mart (MIT, kits/structures/campaign/f4/services/towns), re-materialed in
                   the placement (place_town writes the copy into the build pack)
  six earthworks   one per district: posts to the seabed, a double log deck on every raft (sub-deck at sea level - 1),
                   bamboo bridges, the piers, walks, wharf, boardwalk, breakwater and jetty, the huts, stilt houses,
                   the inn, the guild hall, the smokehouse, the boat shed, the lookout, the fishing stations, the boat
                   racks, the signs and every lantern; the old rafts' earthwork ends by putting back the water
                   tools/place_town.py clears round the Centre and the Mart

and the Mart's clerk position into data/traders.json (its record `sea_town_mart`). The re-application builds the town
with every other place (reapply.py R8: prep_sea_town, then towns/sea_town); `reapply.py prepare` runs `check`, which
fails when the committed placements or clerk no longer match what this data generates.

Ground is the canonical heightmap (tools/ground.py, rounded), never a world: a post runs from round(h) + 1 up to the
sub-deck, and the deck replaces the top water layer at data/world.json's sea level. `plan` refuses a deck over land or
over water shallower than its kind's rule, overlapping elements, a bridge that joins nothing, a building off its raft,
and any open deck cell at the walk level below rules.min_light in the lantern model (a lantern gives 15, falling one
a block, walls ignored, which is why the bar is 5 and not 1). Nothing it places decides a spawn except the water it
puts back (data/spawn_block_policy.json, scope sea_town): no bell, no lily pad, no coral, no white bed, no carpet, no
flowing water.

  python tools/sea_town.py plan    [--source-root <root>]    # check the plan on the heightmap and report; writes nothing
  python tools/sea_town.py write   [--source-root <root>]    # write the settlement, services, earthworks and clerk
  python tools/sea_town.py check   [--source-root <root>]    # exit 1 when the committed data is stale (reapply prepare)
  python tools/sea_town.py verify  --world <stopped world copy>   # the model against a saved world, block by block
  python tools/sea_town.py verify  --rcon <server dir>            # the same over RCON, on a sample (lock held)

verify also looks for the phase 1 failures LONG_ISLE.md names: a deck cell missing or a block off its plan y, water
standing on a deck (a leak), and flowing water under or beside the town.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

PLAN = ROOT / "data" / "sea_town.json"
PLACEMENTS = ROOT / "data" / "placements.json"
TRADERS = ROOT / "data" / "traders.json"
DERIVED = ROOT / "derived" / "sea_town"
CLEAR_TOP = 76                    # the highest block the town writes is the lookout's lanterns (y74)
DIRS = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
OPPOSITE = {"north": "south", "south": "north", "west": "east", "east": "west"}
CLERK_JIGSAW = "cobblemoncitytowns:shopkeeper_main"
CLERK_TEMPLATE = "bca:stores/store_workers/shopkeeper_ds_general"

# The ground rule (tools/ground_rule.py): the functions here that read a world, each only to check, never to decide a
# position: verify reads a stopped world copy to compare it with the model.
WORLD_READS = {"main", "verify_world"}


# ----------------------------------------------------------------------------------------------------------- helpers

def load(path=PLAN):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sea_level(world):
    import terrain as T
    return int(T.sea_level(world))


def cells(rect):
    x0, z0, x1, z1 = rect
    return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


def inside(rect, x, z, margin=0):
    return rect[0] - margin <= x <= rect[2] + margin and rect[1] - margin <= z <= rect[3] + margin


def grow(rect, n):
    return [rect[0] - n, rect[1] - n, rect[2] + n, rect[3] + n]


def cell_of(x, z):
    """The planning cell: rows A-H north to south (z), columns 1-8 west to east (x), 1,024 blocks each."""
    return "ABCDEFGH"[int(z) // 1024] + str(int(x) // 1024 + 1)


def axis_block(block, axis):
    """A log, wood or bamboo block laid along an axis; anything else unchanged."""
    base = block.split("[")[0]
    if base.endswith(("_log", "_wood")) or base.endswith("bamboo_block"):
        return "%s[axis=%s]" % (base, axis)
    return block


def long_axis(rect):
    return "x" if rect[2] - rect[0] >= rect[3] - rect[1] else "z"


def runs(cellset):
    """[(z, x0, x1)]: a set of (x, z) as runs along x, for compact fills."""
    rows = {}
    for x, z in cellset:
        rows.setdefault(z, []).append(x)
    out = []
    for z in sorted(rows):
        xs = sorted(rows[z])
        a = b = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == b + 1:
                b = x
                continue
            out.append((z, a, b))
            if x is not None:
                a = b = x
    return out


class Writer:
    """Commands in order, and the model of what they leave: {(x, y, z): block}. Air removes a position."""

    def __init__(self):
        self.cmds = []
        self.model = {}

    def note(self, text):
        self.cmds.append("# " + text)

    def fill(self, x0, y0, z0, x1, y1, z1, block, model=True):
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        z0, z1 = min(z0, z1), max(z0, z1)
        self.cmds.append("fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, block))
        if not model:
            return
        air = block.split("[")[0] == "minecraft:air"
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    if air:
                        self.model.pop((x, y, z), None)
                    else:
                        self.model[(x, y, z)] = block

    def set(self, x, y, z, block):
        self.cmds.append("setblock %d %d %d %s" % (x, y, z, block))
        if block.split("[")[0] == "minecraft:air":
            self.model.pop((x, y, z), None)
        else:
            self.model[(x, y, z)] = block

    def fill_cells(self, cellset, y, block):
        for z, a, b in runs(cellset):
            self.fill(a, y, z, b, y, z, block)


# ------------------------------------------------------------------------------------------------------------ layout

def bridge_rect(a, b, width, at=None):
    """The rect of a bridge across the water between rects a and b, centred on their overlap (or on `at`)."""
    ax0, az0, ax1, az1 = a
    bx0, bz0, bx1, bz1 = b
    half = width // 2
    if ax1 < bx0 or bx1 < ax0:                           # side by side along x: the bridge runs along x
        lo, hi = max(az0, bz0), min(az1, bz1)
        g0, g1 = (ax1 + 1, bx0 - 1) if ax1 < bx0 else (bx1 + 1, ax0 - 1)
        c = at if at is not None else (lo + hi) // 2
        if hi - lo + 1 < width or not (lo <= c - half and c + half <= hi):
            return None, "their z ranges overlap by %d, too little for a %d-wide bridge at %s" % (hi - lo + 1, width, c)
        return [g0, c - half, g1, c + half], "x"
    if az1 < bz0 or bz1 < az0:
        lo, hi = max(ax0, bx0), min(ax1, bx1)
        g0, g1 = (az1 + 1, bz0 - 1) if az1 < bz0 else (bz1 + 1, az0 - 1)
        c = at if at is not None else (lo + hi) // 2
        if hi - lo + 1 < width or not (lo <= c - half and c + half <= hi):
            return None, "their x ranges overlap by %d, too little for a %d-wide bridge at %s" % (hi - lo + 1, width, c)
        return [c - half, g0, c + half, g1], "z"
    return None, "they overlap or touch diagonally; nothing to bridge"


def elements(plan):
    """[{id, district, kind, rect, axis, materials, decor, landfall, min_depth}] for every deck element, bridges
    included, in build order. Raises SystemExit on a bridge that cannot be drawn."""
    rules = plan["rules"]
    out = []
    for r in plan["rafts"]:
        kind = "square" if r.get("square") else "raft"
        out.append({"id": r["id"], "district": r["district"], "kind": kind, "rect": r["rect"], "axis": "x",
                    "mat": kind, "decor": False, "landfall": False, "min_depth": rules["min_depth"]["raft"], "rec": r})
    for w in plan["walks"]:
        out.append({"id": w["id"], "district": w["district"], "kind": w["kind"], "rect": w["rect"],
                    "axis": long_axis(w["rect"]), "mat": w["kind"], "decor": bool(w.get("decor")),
                    "landfall": bool(w.get("landfall")),
                    "min_depth": w.get("min_depth", rules["min_depth"].get(w["kind"], 1)), "rec": w})
    by_id = {e["id"]: e for e in out}
    for i, b in enumerate(plan["bridges"]):
        a_id, b_id = b["between"]
        if a_id not in by_id or b_id not in by_id:
            raise SystemExit("bridge %s: %s is not a raft or walk" % (b["between"], a_id if a_id not in by_id else b_id))
        rect, axis = bridge_rect(by_id[a_id]["rect"], by_id[b_id]["rect"], rules["bridge_width"], b.get("at"))
        if rect is None:
            raise SystemExit("bridge %s - %s: %s" % (a_id, b_id, axis))
        district = by_id[a_id]["district"]
        out.append({"id": "bridge_%s_%s" % (a_id, b_id), "district": district, "kind": "bridge", "rect": rect,
                    "axis": axis, "mat": "bridge", "decor": False, "landfall": False,
                    "min_depth": rules["min_depth"]["bridge"], "between": [a_id, b_id],
                    "length": (rect[2] - rect[0] + 1) if axis == "x" else (rect[3] - rect[1] + 1), "rec": b})
    return out


def deck_ground(world):
    """(deck y, set of (x, z)) for tools/ground.py's "sea_deck" ground: every deck cell of the plan. Pure geometry
    from data/sea_town.json and the sea level in data/world.json; no heightmap and no world."""
    plan = load()
    out = set()
    for e in elements(plan):
        if not e["decor"]:
            out |= cells(e["rect"])
    return sea_level(world), out


def service_geometry(svc):
    """{rotation, footprint, px, pz, grade, grade_cells (world x, z of non-air blocks at the grade layer), door,
    front, clerk (template x, y, z of the shopkeeper jigsaw, or None)} for a service placed at svc["position"]."""
    import nbt
    import place_town as PT
    path = ROOT / svc["file"]
    info = PT.template_info(path)
    rot = PT.rotation_for(info["entrance"], svc["facing"])
    mnx, mnz, w, d = PT.footprint(info["size"], rot)
    x0, z0 = svc["position"]
    px, pz = x0 - mnx, z0 - mnz
    _, doc = nbt.load(path)
    pal = doc["palette"]
    grade = info["grade_layer"]
    at_grade, clerk = set(), None
    for b in doc["blocks"]:
        name = pal[b["state"]]["Name"]
        tx, ty, tz = b["pos"]
        if name == "minecraft:jigsaw" and (b.get("nbt") or {}).get("name") == CLERK_JIGSAW:
            clerk = (tx, ty, tz)
        if ty == grade and name not in ("minecraft:air", "minecraft:structure_void", "minecraft:cave_air"):
            if name == "minecraft:jigsaw" and ((b.get("nbt") or {}).get("final_state") or "minecraft:air").startswith("minecraft:air"):
                continue
            rx, rz = PT.rotate(tx, tz, rot)
            at_grade.add((px + rx, pz + rz))
    ex, ez = info["entrance_pos"][0], info["entrance_pos"][2]
    rx, rz = PT.rotate(ex, ez, rot)
    door = (px + rx, pz + rz)
    sx, sz = DIRS[svc["facing"]]
    return {"rotation": rot, "footprint": [x0, z0, x0 + w - 1, z0 + d - 1], "px": px, "pz": pz, "grade": grade,
            "grade_cells": at_grade, "door": door, "front": [(door[0] + sx * k, door[1] + sz * k) for k in (1, 2)],
            "clerk_template": clerk}


# --------------------------------------------------------------------------------------------------------- buildings

def door_cell(b, side):
    x0, z0, x1, z1 = b["rect"]
    at = (b.get("door_at") or {}).get(side)
    if side in ("north", "south"):
        x = at if at is not None else (x0 + x1) // 2
        return (x, z0 if side == "north" else z1)
    z = at if at is not None else (z0 + z1) // 2
    return (x0 if side == "west" else x1, z)


def hut(W, b, pal, floor_y, beds=0):
    """A walled hut on its own floor: log corners, three blocks of wall, doors and windows, a gable roof of stairs
    along its longer side, a floor lantern inside. Returns the doors' outside cells."""
    x0, z0, x1, z1 = b["rect"]
    wy0, wy1 = floor_y + 1, floor_y + 3
    W.fill(x0, floor_y, z0, x1, floor_y, z1, pal["floor"])
    W.fill(x0 + 1, wy0, z0, x1 - 1, wy1, z0, pal["wall"])
    W.fill(x0 + 1, wy0, z1, x1 - 1, wy1, z1, pal["wall"])
    W.fill(x0, wy0, z0 + 1, x0, wy1, z1 - 1, pal["wall"])
    W.fill(x1, wy0, z0 + 1, x1, wy1, z1 - 1, pal["wall"])
    for x, z in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
        W.fill(x, wy0, z, x, wy1, z, axis_block(pal["corner"], "y"))
    W.fill(x0 + 1, wy0, z0 + 1, x1 - 1, wy1, z1 - 1, "minecraft:air")
    outside = []
    doors = b.get("doors") or []
    for side in doors:
        dx, dz = door_cell(b, side)
        if pal.get("door"):
            W.set(dx, wy0, dz, "%s[facing=%s,half=lower,hinge=left,open=false,powered=false]" % (pal["door"], side))
            W.set(dx, wy0 + 1, dz, "%s[facing=%s,half=upper,hinge=left,open=false,powered=false]" % (pal["door"], side))
        else:
            W.fill(dx, wy0, dz, dx, wy0 + 1, dz, "minecraft:air")
        sx, sz = DIRS[side]
        outside.append((side, (dx + sx, dz + sz)))
    if pal.get("window"):
        for side in ("north", "south", "west", "east"):
            if side in doors:
                continue
            length = (x1 - x0 + 1) if side in ("north", "south") else (z1 - z0 + 1)
            if length < 5:
                continue
            wx, wz = door_cell({"rect": b["rect"]}, side)
            conn = "east=true,west=true" if side in ("north", "south") else "north=true,south=true"
            W.set(wx, wy0 + 1, wz, "%s[%s]" % (pal["window"], conn))
    roof(W, b["rect"], wy1 + 1, pal)
    # inside: a lantern on the floor in one back corner, a barrel in the other, beds along the back wall
    back = "south" if "north" in doors else "north"
    bz = z1 - 1 if back == "south" else z0 + 1
    W.set(x0 + 1, wy0, bz, "minecraft:lantern[hanging=false]")
    if not beds:
        W.set(x1 - 1, wy0, bz, "minecraft:barrel[facing=up,open=false]")
    for k in range(beds):
        bx = x0 + 2 + 2 * k
        if bx >= x1:
            break
        hz, fz = (z1 - 1, z1 - 2) if back == "south" else (z0 + 1, z0 + 2)
        W.set(bx, wy0, fz, "minecraft:red_bed[facing=%s,occupied=false,part=foot]" % back)
        W.set(bx, wy0, hz, "minecraft:red_bed[facing=%s,occupied=false,part=head]" % back)
    return outside


def roof(W, rect, y0, pal):
    """A gable roof of stairs over rect grown by one, ridge along the longer side, gable ends in the wall block."""
    x0, z0, x1, z1 = rect
    along_x = (x1 - x0) >= (z1 - z0)
    stairs = pal["roof_stairs"]
    k = 0
    while True:
        y = y0 + k
        if along_x:
            a, c = z0 - 1 + k, z1 + 1 - k
            if a > c:
                break
            if a == c:
                W.fill(x0 - 1, y, a, x1 + 1, y, a, pal["roof"])
                break
            W.fill(x0 - 1, y, a, x1 + 1, y, a, "%s[facing=south,half=bottom,shape=straight,waterlogged=false]" % stairs)
            W.fill(x0 - 1, y, c, x1 + 1, y, c, "%s[facing=north,half=bottom,shape=straight,waterlogged=false]" % stairs)
            if c - a > 1:
                W.fill(x0, y, a + 1, x0, y, c - 1, pal["wall"])
                W.fill(x1, y, a + 1, x1, y, c - 1, pal["wall"])
                if x1 - x0 > 1:
                    W.fill(x0 + 1, y, a + 1, x1 - 1, y, c - 1, "minecraft:air")
        else:
            a, c = x0 - 1 + k, x1 + 1 - k
            if a > c:
                break
            if a == c:
                W.fill(a, y, z0 - 1, a, y, z1 + 1, pal["roof"])
                break
            W.fill(a, y, z0 - 1, a, y, z1 + 1, "%s[facing=east,half=bottom,shape=straight,waterlogged=false]" % stairs)
            W.fill(c, y, z0 - 1, c, y, z1 + 1, "%s[facing=west,half=bottom,shape=straight,waterlogged=false]" % stairs)
            if c - a > 1:
                W.fill(a + 1, y, z0, c - 1, y, z0, pal["wall"])
                W.fill(a + 1, y, z1, c - 1, y, z1, pal["wall"])
                if z1 - z0 > 1:
                    W.fill(a + 1, y, z0 + 1, c - 1, y, z1 - 1, "minecraft:air")
        k += 1


def stilts(W, b, g, floor_y, deck_cells, level, mats):
    """Mangrove stilts from the seabed to under the floor at the corners and side middles, and roots round the corner
    stilts at the waterline (never on a deck cell)."""
    x0, z0, x1, z1 = b["rect"]
    post = axis_block(mats["stilt"]["post"], "y")
    pts = {(x0, z0), (x1, z0), (x0, z1), (x1, z1), ((x0 + x1) // 2, z0), ((x0 + x1) // 2, z1),
           (x0, (z0 + z1) // 2), (x1, (z0 + z1) // 2)}
    for x, z in sorted(pts):
        W.fill(x, g(x, z) + 1, z, x, floor_y - 1, z, post)
    for cx, cz, sx, sz in ((x0, z0, -1, -1), (x1, z0, 1, -1), (x0, z1, -1, 1), (x1, z1, 1, 1)):
        for x, z in ((cx + sx, cz), (cx, cz + sz), (cx + sx, cz + sz)):
            if (x, z) in deck_cells:
                continue
            lo = max(g(x, z) + 1, level - 2)
            if lo <= level:
                W.fill(x, lo, z, x, level, z, "%s[waterlogged=true]" % mats["stilt"]["roots"])


def guild_decor(W, b, floor_y):
    """The guild hall's inside: rod racks on the north wall, the catch in barrels, a smoker."""
    x0, z0, x1, z1 = b["rect"]
    y = floor_y + 1
    for x in range(x0 + 2, x0 + 6):
        W.set(x, y, z0 + 1, "minecraft:spruce_fence")
        W.set(x, y + 1, z0 + 1, "minecraft:spruce_fence")
    for x in (x1 - 4, x1 - 3):
        W.set(x, y, z1 - 1, "minecraft:barrel[facing=up,open=false]")
    W.set(x1 - 2, y, z1 - 1, "minecraft:smoker[facing=north,lit=false]")
    W.set(x0 + 7, y, z0 + 1, "minecraft:lantern[hanging=false]")


def smokehouse_decor(W, b, floor_y):
    x0, z0, x1, z1 = b["rect"]
    W.set((x0 + x1) // 2, floor_y + 1, (z0 + z1) // 2,
          "minecraft:campfire[facing=north,lit=true,signal_fire=false,waterlogged=false]")


def boat_shed(W, b, level, mats):
    """An open shed: spruce posts at the corners and every four along the long sides, a slab roof, lanterns under it."""
    x0, z0, x1, z1 = b["rect"]
    top = level + 4
    posts = set()
    for x in list(range(x0, x1 + 1, 4)) + [x1]:
        posts |= {(x, z0), (x, z1)}
    for x, z in sorted(posts):
        W.fill(x, level + 1, z, x, top, z, "minecraft:spruce_log[axis=y]")
    W.fill(x0, top + 1, z0, x1, top + 1, z1, "minecraft:spruce_slab[type=bottom,waterlogged=false]")
    lamps = []
    for x in range(x0 + 4, x1, 6):
        for z in (z0 + 2, z1 - 2):
            W.set(x, top, z, mats["lamp"]["hanging"])
            lamps.append((x, top, z))
    return lamps


def lookout(W, b, level):
    """A log tower 9 high over a 5 x 5 base: corner posts, a ladder up a log spine, a railed platform with lanterns."""
    x0, z0, x1, z1 = b["rect"]
    top = level + 10                                          # the platform's floor
    for x, z in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
        W.fill(x, level + 1, z, x, top - 1, z, "minecraft:spruce_log[axis=y]")
    lx, lz = (x0 + x1) // 2, (z0 + z1) // 2
    W.fill(lx, level + 1, lz + 1, lx, top - 1, lz + 1, "minecraft:spruce_log[axis=y]")
    W.fill(x0, top, z0, x1, top, z1, "minecraft:spruce_planks")
    W.fill(lx, level + 1, lz, lx, top, lz, "minecraft:ladder[facing=north,waterlogged=false]")
    for x in range(x0, x1 + 1):
        for z in (z0, z1):
            W.set(x, top + 1, z, "minecraft:spruce_fence")
    for z in range(z0 + 1, z1):
        for x in (x0, x1):
            W.set(x, top + 1, z, "minecraft:spruce_fence")
    lamps = []
    for x, z in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
        W.set(x, top + 2, z, "minecraft:lantern[hanging=false]")
        lamps.append((x, top + 2, z))
    return lamps


# ------------------------------------------------------------------------------------------------------------ build

def build(plan, g, world):
    """Everything the town is, from the plan and the heightmap: {district: Writer}, and a report. Raises SystemExit on
    any rule the plan breaks."""
    level = sea_level(world)
    walk = level + 1
    rules = plan["rules"]
    mats = plan["materials"]
    els = elements(plan)
    by_id = {e["id"]: e for e in els}
    problems = []

    # --- the ground under every element, and the depth rules
    depth_report = {}
    for e in els:
        gs = [g(x, z) for x, z in cells(e["rect"])]
        lo, hi = min(gs), max(gs)
        depth_report[e["id"]] = {"kind": e["kind"], "rect": e["rect"], "seabed_y": [lo, hi],
                                 "depth": [level - hi, level - lo]}
        if e["landfall"]:
            if hi > rules["landfall_max_ground"]:
                problems.append("%s comes ashore on ground y%d, above the deck (the most allowed is y%d)"
                                % (e["id"], hi, rules["landfall_max_ground"]))
        elif level - hi < e["min_depth"]:
            problems.append("%s stands over %d blocks of water at its shallowest (ground y%d); its rule is %d"
                            % (e["id"], level - hi, hi, e["min_depth"]))
    # --- no two deck elements share a cell
    owner = {}
    for e in els:
        for c in cells(e["rect"]):
            if c in owner:
                problems.append("%s overlaps %s at %s" % (e["id"], owner[c], c))
                break
            owner[c] = e["id"]
    deck = {c for c, i in owner.items() if not by_id[i]["decor"]}
    # --- connectivity: every element joins the square, or is one of the districts reached by boat
    adj = {e["id"]: set() for e in els if not e["decor"]}
    for (x, z), i in owner.items():
        if by_id[i]["decor"]:
            continue
        for dx, dz in DIRS.values():
            j = owner.get((x + dx, z + dz))
            if j and j != i and not by_id[j]["decor"]:
                adj[i].add(j)
    comps, seen = [], set()
    for i in adj:
        if i in seen:
            continue
        stack, comp = [i], set()
        while stack:
            k = stack.pop()
            if k in comp:
                continue
            comp.add(k)
            stack += list(adj[k] - comp)
        seen |= comp
        comps.append(comp)
    square = next(r["id"] for r in plan["rafts"] if r.get("square"))
    by_boat = set(rules.get("by_boat") or ("current_gate", "mainland_jetty"))
    for comp in comps:
        districts = {by_id[i]["district"] for i in comp}
        if square in comp:
            if districts & by_boat:
                problems.append("%s is joined to the square, but it is meant to be reached by boat" % sorted(districts & by_boat))
        elif not (len(districts) == 1 and districts <= by_boat):
            problems.append("%s is not joined to the square (districts %s)" % (sorted(comp), sorted(districts)))
    # --- services: seated on their raft with a margin, their door on the deck
    services = {}
    for s in plan["services"]:
        geo = service_geometry(s)
        raft = by_id[s["raft"]]["rect"]
        fp = geo["footprint"]
        if not (inside(raft, fp[0], fp[1], -2) and inside(raft, fp[2], fp[3], -2)):
            problems.append("%s footprint %s is not inside its raft %s with 2 blocks to spare (tools/place_town.py "
                            "clears 2 blocks round a building)" % (s["id"], fp, raft))
        for c in geo["front"]:
            if c not in deck:
                problems.append("%s: the cell in front of its door %s is not deck" % (s["id"], c))
        services[s["id"]] = dict(geo, rec=s)
    # --- buildings on rafts sit inside them; stilt buildings stand in water, off the decks
    blds = plan["buildings"]
    for b in blds:
        r = b["rect"]
        if b["type"] in ("stilt_house", "inn"):
            gs = [g(x, z) for x, z in cells(r)]
            if level - max(gs) < rules["min_depth"]["stilt_house"]:
                problems.append("%s stands on ground y%d, not in water" % (b["id"], max(gs)))
            if cells(r) & set(owner):
                problems.append("%s overlaps a deck" % b["id"])
        else:
            if not all(c in deck for c in cells(grow(r, 1))):
                problems.append("%s is not on a deck with a block to spare all round" % b["id"])
    rects = [(b["id"], b["rect"]) for b in blds] + [(k, v["footprint"]) for k, v in services.items()]
    for i, (a, ra) in enumerate(rects):
        for bb, rb in rects[i + 1:]:
            if not (ra[2] < rb[0] or rb[2] < ra[0] or ra[3] < rb[1] or rb[3] < ra[1]):
                problems.append("%s overlaps %s" % (a, bb))
    if problems:
        raise SystemExit("data/sea_town.json breaks its rules:\n  " + "\n  ".join(problems))

    square_rect = by_id[square]["rect"]
    service_rects = [v["footprint"] for v in services.values()]
    grade = set().union(*(v["grade_cells"] for v in services.values())) if services else set()
    writers = {d["id"]: Writer() for d in plan["districts"]}
    for d in plan["districts"]:
        writers[d["id"]].note("%s (tools/sea_town.py from data/sea_town.json): %s" % (d["name"], d["what"]))
    occupied = set()                                  # walk-level cells something stands on
    lamps = []                                        # (x, y, z) of every outdoor lantern
    junction = {}                                     # element id -> its cells that touch another element
    for (x, z), i in owner.items():
        for dx, dz in DIRS.values():
            j = owner.get((x + dx, z + dz))
            if j and j != i:
                junction.setdefault(i, set()).add((x, z))

    def protected(x, z):
        return inside(square_rect, x, z) or any(inside(r, x, z) for r in service_rects)

    # --- 1. clear the air over every deck and stilt building, never over the square or a service
    for e in els:
        W = writers[e["district"]]
        free = {c for c in cells(e["rect"]) if not protected(*c)}
        if free == cells(e["rect"]):
            W.fill(e["rect"][0], walk, e["rect"][1], e["rect"][2], CLEAR_TOP, e["rect"][3], "minecraft:air")
        else:
            for z, a, b in runs(free):
                W.fill(a, walk, z, b, CLEAR_TOP, z, "minecraft:air")
    for b in blds:
        if b["type"] in ("stilt_house", "inn"):
            r = grow(b["rect"], 1)
            writers[b["district"]].fill(r[0], walk, r[1], r[2], CLEAR_TOP, r[3], "minecraft:air")
    # --- 2. posts to the seabed: rafts every raft_post_every along the edges, walks both edges every walk_post_every
    posts = 0
    for e in els:
        if e["decor"]:
            continue
        W = writers[e["district"]]
        x0, z0, x1, z1 = e["rect"]
        m = mats[e["mat"]]
        if e["kind"] in ("raft", "square"):
            step = rules["raft_post_every"]
            pts = {(x, z) for x in list(range(x0, x1 + 1, step)) + [x1] for z in (z0, z1)}
            pts |= {(x, z) for z in list(range(z0, z1 + 1, step)) + [z1] for x in (x0, x1)}
            top = level - 2
        elif e["kind"] == "bridge":
            if e["length"] < 7:
                continue
            mid = ((x0 + x1) // 2, (z0 + z1) // 2)
            pts = {(mid[0], z0), (mid[0], z1)} if e["axis"] == "x" else {(x0, mid[1]), (x1, mid[1])}
            top = level - 1
        else:
            step = rules["walk_post_every"]
            if e["axis"] == "x":
                pts = {(x, z) for x in list(range(x0, x1 + 1, step)) + [x1] for z in (z0, z1)}
            else:
                pts = {(x, z) for z in list(range(z0, z1 + 1, step)) + [z1] for x in (x0, x1)}
            top = level - 1
        for x, z in sorted(pts):
            gy = g(x, z)
            if gy + 1 <= top:
                W.fill(x, gy + 1, z, x, top, z, axis_block(m["post"], "y"))
                posts += 1
    # --- 3. the sub-deck under every raft and the square: the second layer of logs, and what a building stands on
    for e in els:
        if e["kind"] in ("raft", "square"):
            W = writers[e["district"]]
            x0, z0, x1, z1 = e["rect"]
            W.fill(x0, level - 1, z0, x1, level - 1, z1, axis_block(mats[e["mat"]]["sub"], "z"))
    # --- 4. the decks: logs along x with a frame of stripped logs; bridges and walks along their length
    for e in els:
        W = writers[e["district"]]
        x0, z0, x1, z1 = e["rect"]
        m = mats[e["mat"]]
        if e["kind"] == "square":
            continue                                           # paved by the town plan (its plaza), not here
        if e["kind"] == "raft":
            inner = cells([x0 + 1, z0 + 1, x1 - 1, z1 - 1]) - grade
            if inner == cells([x0 + 1, z0 + 1, x1 - 1, z1 - 1]):
                W.fill(x0 + 1, level, z0 + 1, x1 - 1, level, z1 - 1, axis_block(m["deck"], "x"))
            else:
                W.fill_cells(inner, level, axis_block(m["deck"], "x"))
            W.fill(x0, level, z0, x1, level, z0, axis_block(m["frame"], "x"))
            W.fill(x0, level, z1, x1, level, z1, axis_block(m["frame"], "x"))
            W.fill(x0, level, z0 + 1, x0, level, z1 - 1, axis_block(m["frame"], "z"))
            W.fill(x1, level, z0 + 1, x1, level, z1 - 1, axis_block(m["frame"], "z"))
            continue
        across = "z" if e["axis"] == "x" else "x"
        W.fill(x0, level, z0, x1, level, z1, axis_block(m["deck"], across if e["kind"] != "bridge" else e["axis"]))
        if m.get("frame") and min(x1 - x0, z1 - z0) >= 2:
            if e["axis"] == "x":
                W.fill(x0, level, z0, x1, level, z0, axis_block(m["frame"], "x"))
                W.fill(x0, level, z1, x1, level, z1, axis_block(m["frame"], "x"))
            else:
                W.fill(x0, level, z0, x0, level, z1, axis_block(m["frame"], "z"))
                W.fill(x1, level, z0, x1, level, z1, axis_block(m["frame"], "z"))
    # --- 5. the buildings
    stilt_floor = plan["levels"]["stilt_floor"]
    indoor_lights = 0
    for b in blds:
        W = writers[b["district"]]
        pal = plan["hut_palettes"].get(b.get("palette") or "")
        if b["type"] in ("hut", "guild_hall", "smokehouse"):
            outs = hut(W, b, pal, level)
            indoor_lights += 1
            if b["type"] == "guild_hall":
                guild_decor(W, b, level)
            if b["type"] == "smokehouse":
                smokehouse_decor(W, b, level)
            for _side, c in outs:
                if c not in deck:
                    raise SystemExit("%s: its door opens onto %s, which is not deck" % (b["id"], c))
        elif b["type"] in ("stilt_house", "inn"):
            stilts(W, b, g, stilt_floor, deck, level, mats)
            outs = hut(W, b, pal, stilt_floor, beds=int(b.get("beds") or 0))
            indoor_lights += 1
            for side, (ox, oz) in outs:
                if (ox, oz) not in deck:
                    raise SystemExit("%s: its door opens onto %s, which is not deck" % (b["id"], (ox, oz)))
                W.set(ox, walk, oz, "minecraft:mangrove_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]"
                      % OPPOSITE[side])
                occupied.add((ox, oz))
        elif b["type"] == "boat_shed":
            lamps += boat_shed(W, b, level, mats)
        elif b["type"] == "lookout":
            lamps += lookout(W, b, level)
        else:
            raise SystemExit("%s: unknown building type %r" % (b["id"], b["type"]))
        if b["type"] != "boat_shed":
            occupied |= cells(b["rect"])
    for v in services.values():
        occupied |= cells(v["footprint"])
    # --- 6. the yard: the slipway into the water and the hull in frame
    yard = plan.get("yard") or {}
    if yard:
        W = writers["boatwrights_yard"]
        sx0, sz0, sx1, sz1 = yard["slipway"]["rect"]
        if yard["slipway"]["down"] != "west":
            raise SystemExit("the slipway can only run down to the west (the wharf's open side)")
        for k, x in enumerate(range(sx1, sx0 - 1, -1)):
            y = level - 1 - k
            if any(g(x, z) >= y for z in range(sz0, sz1 + 1)):
                raise SystemExit("the slipway step at x%d, y%d meets the seabed" % (x, y))
            W.fill(x, y, sz0, x, y, sz1, "minecraft:spruce_stairs[facing=east,half=bottom,shape=straight,waterlogged=true]")
        (kx0, kz), (kx1, _) = yard["hull"]["keel"]
        W.fill(kx0, walk, kz, kx1, walk, kz, "minecraft:stripped_spruce_log[axis=x]")
        for x in range(kx0 + 1, kx1, 2):
            for dz in (-1, 1):
                W.fill(x, walk, kz + dz, x, walk + 1, kz + dz, "minecraft:spruce_fence")
            if kx0 + 2 < x < kx1 - 2:
                for dz in (-2, 2):
                    W.set(x, walk + 1, kz + dz, "minecraft:spruce_fence")
                    W.set(x, walk + 2, kz + dz, "minecraft:spruce_fence")
        W.fill(kx0, walk + 1, kz, kx0, walk + 3, kz, "minecraft:stripped_spruce_log[axis=y]")
        W.fill(kx1, walk + 1, kz, kx1, walk + 2, kz, "minecraft:stripped_spruce_log[axis=y]")
        occupied |= {(x, kz + dz) for x in range(kx0, kx1 + 1) for dz in (-2, -1, 0, 1, 2)}
    # moored rafts: decor on the water
    for e in els:
        if e["decor"]:
            x0, z0, x1, z1 = e["rect"]
            writers[e["district"]].fill(x0, level, z0, x1, level, z1, axis_block(mats[e["mat"]]["deck"], "x"))
    # --- 7. racks, stations, signs
    for r in plan.get("racks") or []:
        W = writers[district_of(r["at"], els, owner)]
        x, z = r["at"]
        n = r["length"]
        if r["along"] != "x":
            raise SystemExit("%s: racks run along x" % r["id"])
        for cx in range(x, x + n + 1):
            if (cx, z) not in deck:
                raise SystemExit("%s: %s is not deck" % (r["id"], (cx, z)))
        for cx in (x, x + n - 1):
            W.fill(cx, walk, z, cx, walk + 2, z, "minecraft:spruce_fence")
        W.fill(x + 1, walk, z, x + n - 2, walk, z, "minecraft:spruce_slab[type=bottom,waterlogged=false]")
        W.fill(x + 1, walk + 2, z, x + n - 2, walk + 2, z, "minecraft:spruce_slab[type=bottom,waterlogged=false]")
        items = ",".join('{Slot:%db,id:"minecraft:oak_boat",count:1}' % k for k in range(int(r["boats"])))
        W.set(x + n, walk, z, "minecraft:barrel[facing=up,open=false]{Items:[%s]}" % items)
        occupied |= {(cx, z) for cx in range(x, x + n + 1)}
    stations = station_list(plan, by_id)
    for s in stations:
        W = writers[district_of(s["seat"], els, owner)]
        for c in (s["seat"], s["barrel"], s["post"]):
            if c not in deck or c in occupied:
                raise SystemExit("fishing station at %s: %s is not free deck" % (s["seat"], c))
        W.set(s["seat"][0], walk, s["seat"][1], "minecraft:spruce_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]"
              % OPPOSITE[s["water"]])
        W.set(s["barrel"][0], walk, s["barrel"][1], "minecraft:barrel[facing=up,open=false]")
        W.set(s["post"][0], walk, s["post"][1], mats["lamp"]["post"])
        W.set(s["post"][0], walk + 1, s["post"][1], mats["lamp"]["light"])
        lamps.append((s["post"][0], walk + 1, s["post"][1]))
        occupied |= {s["seat"], s["barrel"], s["post"]}
    import signposts
    signed = set()
    for sg in plan.get("signs") or []:
        x, z = sg["at"]
        in_building = any(inside(bd["rect"], x, z, -1) for bd in blds)
        if ((x, z) in occupied and not in_building) or (x, z) in signed or not ((x, z) in deck or in_building):
            raise SystemExit("sign %s at %s is not on free deck or inside a building" % (sg["id"], (x, z)))
        writers[district_of((x, z), els, owner) if (x, z) in owner else
                next(bd["district"] for bd in blds if inside(bd["rect"], x, z))].set(
            x, walk, z, signposts.sign_nbt({"rotation": sg["rotation"], "front": sg["front"], "back": sg["back"]}, sg["wood"]))
        occupied.add((x, z))
        signed.add((x, z))
    # --- 8. lanterns on posts
    wx, wz = plan["waystone"]["position"]
    occupied |= {(wx, wz)}
    lamp_cells = set()
    for e in els:
        if e["decor"]:
            continue
        spots = lamp_spots(e, plan, rules, junction.get(e["id"], set()), occupied, blds, services)
        for x, z in spots:
            if (x, z) in occupied or (x, z) in lamp_cells:
                continue
            W = writers[e["district"]]
            W.set(x, walk, z, mats["lamp"]["post"])
            W.set(x, walk + 1, z, mats["lamp"]["light"])
            lamps.append((x, walk + 1, z))
            lamp_cells.add((x, z))
    occupied |= lamp_cells
    # --- 9. the water tools/place_town.py clears round each service (from sea level - 2 up), put back under the deck
    for v in services.values():
        r = grow(v["footprint"], 2)
        writers[by_id[v["rec"]["raft"]]["district"]].fill(r[0], level - 2, r[1], r[2], level - 2, r[3],
                                                          "minecraft:water replace minecraft:air", model=False)
    # --- the light model: every open deck cell at the walk level
    open_cells = [c for c in deck if c not in occupied]
    worst, dark = 15, []
    for x, z in open_cells:
        best = 0
        for lx, ly, lz in lamps:
            d = abs(lx - x) + abs(lz - z) + abs(ly - walk)
            if d < 15 and 15 - d > best:
                best = 15 - d
                if best >= 12:
                    break
        worst = min(worst, best)
        if best < rules["min_light"]:
            dark.append(((x, z), best))
    if dark:
        dark.sort(key=lambda q: q[1])
        where = {}
        for c, _l in dark:
            where[owner.get(c)] = where.get(owner.get(c), 0) + 1
        print("dark cells by element: %s" % where)
        raise SystemExit("%d open deck cells are below min_light %d in the lantern model (darkest: %s); add lamps to "
                         "data/sea_town.json" % (len(dark), rules["min_light"], dark[:8]))
    report = {"deck_y": level, "walk_y": walk, "elements": len(els), "deck_cells": len(deck), "posts": posts,
              "lanterns_outdoor": len(lamps), "lit_indoors": indoor_lights, "stations": len(stations),
              "min_modelled_light": worst, "open_deck_cells": len(open_cells), "depths": depth_report,
              "services": {k: {"rotation": v["rotation"], "footprint": v["footprint"], "door": list(v["door"])}
                           for k, v in services.items()},
              "commands": {k: len(w.cmds) for k, w in writers.items()},
              "bridges": [{"between": e["between"], "rect": e["rect"], "length": e["length"]} for e in els if e["kind"] == "bridge"]}
    return writers, services, report, {"deck": deck, "lamps": lamps, "square": square_rect, "level": level}


def district_of(c, els, owner):
    i = owner.get(tuple(c))
    if i is None:
        raise SystemExit("%s is not on any deck" % (c,))
    return next(e["district"] for e in els if e["id"] == i)


def station_list(plan, by_id):
    """[{seat, barrel, post, water}]: each station's three cells along its edge and the side the water is on."""
    out = []
    st = plan.get("stations") or {}
    for run in st.get("runs") or []:
        e = by_id[run["walk"]]
        x0, z0, x1, z1 = e["rect"]
        if e["axis"] != "x":
            raise SystemExit("station run on %s: runs follow a walk along x" % run["walk"])
        step = -run["every"] if run["to"] < run["from"] else run["every"]
        for k, x in enumerate(range(run["from"], run["to"] + (1 if step > 0 else -1), step)):
            side = run["sides"][k % len(run["sides"])]
            z = z0 if side == "north" else z1
            out.append({"seat": (x, z), "barrel": (x + 1, z), "post": (x - 1, z), "water": side})
    for s in st.get("at") or []:
        x, z = s["at"]
        if s["water"] in ("west", "east"):
            out.append({"seat": (x, z), "barrel": (x, z + 1), "post": (x, z - 1), "water": s["water"]})
        else:
            out.append({"seat": (x, z), "barrel": (x + 1, z), "post": (x - 1, z), "water": s["water"]})
    return out


def lamp_spots(e, plan, rules, junction, occupied, blds, services):
    """Where an element's lantern posts go. A raft, a wide walk and the wharf: every corner of the ring one block in,
    and every lamp_every along it. A narrow walk: every lamp_every along its length on alternate edges, unless fishing
    stations light it. A long bridge: one at its middle. Never within two of where another deck joins, on a
    building or next to one, or where something already stands."""
    x0, z0, x1, z1 = e["rect"]
    n = rules["lamp_every"]
    rec = e["rec"]
    if rec.get("lamps"):
        return [tuple(c) for c in rec["lamps"]]
    spots = []
    w, d = x1 - x0 + 1, z1 - z0 + 1
    if e["kind"] == "bridge":
        if e["length"] >= rules["bridge_lamp_from_length"]:
            if e["axis"] == "x":
                spots.append(((x0 + x1) // 2, z0))
            else:
                spots.append((x0, (z0 + z1) // 2))
        return spots
    runs_on = {r["walk"] for r in (plan.get("stations") or {}).get("runs") or []}
    if e["kind"] in ("raft",) or min(w, d) >= 7:
        a0, b0, a1, b1 = x0 + 1, z0 + 1, x1 - 1, z1 - 1
        ring = []
        for x in range(a0, a1 + 1):
            ring += [(x, b0), (x, b1)]
        for z in range(b0 + 1, b1):
            ring += [(a0, z), (a1, z)]
        corners = {(a0, b0), (a1, b0), (a0, b1), (a1, b1)}
        for x, z in ring:
            on = (x, z) in corners or ((x - a0) % n == 0 and z in (b0, b1)) or ((z - b0) % n == 0 and x in (a0, a1))
            if on:
                spots.append((x, z))
        # and a field of posts over the open middle of a big deck (the wharf), where the ring cannot reach; on a raft
        # the middle is its hut and these fall away
        for x in range(a0 + n, a1 - 1, n):
            for z in range(b0 + n, b1 - 1, n):
                spots.append((x, z))
    elif e["id"] not in runs_on:
        if e["axis"] == "x":
            for k, x in enumerate(range(x0 + n // 2, x1 + 1, n)):
                spots.append((x, z0 if k % 2 == 0 else z1))
        else:
            for k, z in enumerate(range(z0 + n // 2, z1 + 1, n)):
                spots.append((x0 if k % 2 == 0 else x1, z))
    reach = 2 if (e["kind"] == "raft" or min(w, d) >= 7) else 1        # keep a join's mouth clear
    near_join = lambda x, z: any(max(abs(x - jx), abs(z - jz)) <= reach for jx, jz in junction)
    near_building = lambda x, z: any(inside(b["rect"], x, z, 1) for b in blds) or \
        any(inside(v["footprint"], x, z, 1) for v in services.values())
    ok = lambda x, z: inside(e["rect"], x, z) and not near_join(x, z) and not near_building(x, z) and (x, z) not in occupied
    out = []
    for x, z in spots:
        # a spot a join, a building or a station takes moves along its edge to the nearest free cell, up to three
        # blocks either way; otherwise it is dropped (the light model then says whether the rest is enough)
        edge_along_x = z in (z0, z1, z0 + 1, z1 - 1) if e["kind"] == "raft" or min(w, d) >= 7 else e["axis"] == "x"
        step = (1, 0) if edge_along_x else (0, 1)
        for k in (0, 1, -1, 2, -2, 3, -3):
            c = (x + step[0] * k, z + step[1] * k)
            if ok(*c):
                out.append(c)
                break
    # extra posts the data names where the rules leave a corner dim: authored, so only checked to be free deck
    for x, z in rec.get("extra_lamps") or []:
        if not inside(e["rect"], x, z) or (x, z) in occupied:
            raise SystemExit("%s: extra lamp %s is not free deck on it" % (e["id"], (x, z)))
        out.append((x, z))
    return out


# -------------------------------------------------------------------------------------------------- placements data

def settlement_record(plan, services, report, footprint):
    sq = next(r for r in plan["rafts"] if r.get("square"))
    anchors = []
    for sid, v in services.items():
        s = v["rec"]
        anchors.append({"id": sid, "role": s["role"], "template": s["template"], "rect": v["footprint"],
                        "facing": s["facing"], "why": s["why"]})
    return {
        "centre": list(plan["site"]["centre"]),
        "footprint_from": "data/towns.json",
        "status": plan["status"],
        "ground": "sea_deck",
        "ground_why": "the town stands on its decks at the sea level, not on the seabed: tools/ground.py lays every deck "
                      "cell of data/sea_town.json over the heightmap at data/world.json's sea level, so tools/town_plan.py "
                      "and tools/place_town.py seat the Centre and the Mart on the raft",
        "generated_by": "tools/sea_town.py write, from data/sea_town.json; edit that file, not this record",
        "plan": {
            "reading": "Out in the Sound, where the desert shore and the jungle island meet across the water, a town floats: "
                       "sixteen log rafts on the jungle island's shelf, joined by bamboo bridges, a hut on each. The Centre "
                       "and the Mart stand on the two largest, either side of the square with its waystone. Fishers' Row "
                       "runs 120 blocks west off the shelf into the deepest water, a station every eight blocks, the "
                       "Fishing Guild at its root. North-east against the jungle shore is the boatwright's wharf with a hull "
                       "in frame; south along the shore the Stilt Quarter's houses and the inn stand in the shallows on "
                       "mangrove stilts. There is no road in: boats put out from a jetty on the dunes' beach to the north, "
                       "and far to the south-west a breakwater and a lookout watch the bay's mouth.",
            "entries": [{"from": "the sea: a boat from the mainland jetty on the South-East Dunes' beach",
                         "at": [7172, 6711], "street": None}],
            "exits": [],
            "footprint": {"rect": footprint, "why": "every district: the jetty's landing in the north, the rafts, the "
                                                    "yard and the Stilt Quarter, Fishers' Row to the west and the Current "
                                                    "Gate at the bay's mouth to the south-west"},
            "streets": [],
            "plaza": {"rect": sq["rect"], "y": report["deck_y"], "surface": plan["materials"]["square"]["surface"],
                      "why": sq["why"]},
            "anchors": anchors,
            "house_lots": {"along": [], "why": "no lots: every building is authored in data/sea_town.json and built by "
                                               "the town's earthworks"},
            "waystone": {"position": list(plan["waystone"]["position"]), "facing": plan["waystone"]["facing"],
                         "note": plan["waystone"]["note"]},
            "paving": {"main": plan["materials"]["raft"]["deck"], "plaza": plan["materials"]["square"]["surface"],
                       "lamp": "none", "why": "log decks and a planked square; the lanterns are on posts, placed by the "
                                              "earthworks (tools/sea_town.py), never set into the deck"},
            "lighting": {"posts": [], "note": "%d lanterns on posts and at fishing stations, and one inside every "
                                              "building; the lantern model leaves no open deck cell below light %d"
                                              % (report["lanterns_outdoor"], report["min_modelled_light"])},
            "no_prep": "nothing is levelled: the square is paved at the sea level over water by the town plan, and "
                       "every other deck is an earthwork",
        },
    }


def placement_records(plan, writers, services):
    import function_limits
    out = []
    for sid, v in services.items():
        s = v["rec"]
        x0, z0 = s["position"]
        out.append({"id": sid, "settlement": plan["settlement"], "template": s["template"], "file": s["file"],
                    "cell": cell_of(x0, z0), "kind": "service", "lot": sid, "position": {"x": x0, "z": z0},
                    "facing": s["facing"], "anchor_mode": "corner", "y_mode": "surface", "rotation": v["rotation"],
                    "mirror": "none", "status": "planned", "chosen_because": s["why"],
                    "donor_source": {"licence": "MIT (CobbleTowns, our kit)"},
                    "materials": plan["service_materials"][s["materials"]],
                    "materials_why": plan["service_materials"]["why"]})
    dist = {d["id"]: d for d in plan["districts"]}
    for did, W in writers.items():
        body = [c for c in W.cmds if not c.startswith("#")]
        if not body:
            continue
        # every command must be one the server runs: checked with the chunks held, as the town function holds them
        refused = function_limits.check_lines(function_limits.ensure_loaded(W.cmds), "sea_town_%s" % did)
        if refused:
            raise SystemExit("sea_town_%s: %d command(s) the server would refuse: %s" % (did, len(refused), refused[:3]))
        xs = [int(k[0]) for k in W.model] or [0]
        zs = [int(k[2]) for k in W.model] or [0]
        out.append({"id": "sea_town_%s" % did, "settlement": plan["settlement"], "kind": "earthwork",
                    "cell": cell_of((min(xs) + max(xs)) // 2, (min(zs) + max(zs)) // 2), "status": "planned",
                    "chosen_because": "the owner, 2026-09-26: \"add the sea town from hoenn\". %s: %s. Generated by "
                                      "tools/sea_town.py from data/sea_town.json" % (dist[did]["name"], dist[did]["what"]),
                    "commands": W.cmds})
    return out


def clerk_record(plan, services, level):
    import place_town as PT
    mart = next(v for v in services.values() if v["rec"]["role"] == "pokemart")
    tx, ty, tz = mart["clerk_template"]
    rx, rz = PT.rotate(tx, tz, mart["rotation"])
    pos = {"x": mart["px"] + rx, "y": level - mart["grade"] + ty + 1, "z": mart["pz"] + rz}
    s = mart["rec"]
    return {"id": "sea_town_mart", "settlement": plan["settlement"], "cell": cell_of(pos["x"], pos["z"]),
            "template": CLERK_TEMPLATE,
            "source": {"pack": "COBBLEVERSE-DP-v31.zip", "path": "data/bca/structure/stores/store_workers/shopkeeper_ds_general.nbt",
                       "licence": "Cobbleverse, no redistribution: placed by resource id from the installed pack"},
            "position": pos, "building": s["id"], "facing": s["facing"], "status": "planned",
            "chosen_because": "the Mart's clerk, behind its counter: %s's shopkeeper jigsaw, which a template placed by "
                              "command never fills" % s["template"],
            "stock": "mart"}


def footprint_of(writers, services, plan):
    xs, zs = [], []
    for W in writers.values():
        for (x, _y, z) in W.model:
            xs.append(x)
            zs.append(z)
    for v in services.values():
        fp = v["footprint"]
        xs += [fp[0], fp[2]]
        zs += [fp[1], fp[3]]
    return [min(xs), min(zs), max(xs), max(zs)]


def generate(source_root=None):
    import ground as G
    plan = load()
    g = G.Ground(source_root)
    writers, services, report, model = build(plan, g, g.world)
    fp = footprint_of(writers, services, plan)
    report["footprint"] = fp
    settlement = settlement_record(plan, services, report, fp)
    recs = placement_records(plan, writers, services)
    clerk = clerk_record(plan, services, report["deck_y"])
    report["clerk"] = clerk["position"]
    return plan, settlement, recs, clerk, report, writers, model


def apply(doc, trad, plan, settlement, recs, clerk):
    """doc and trad with this town's records replaced in place (order kept, new ones appended)."""
    sid = plan["settlement"]
    doc["settlements"][sid] = settlement
    old = [i for i, q in enumerate(doc["placements"]) if q.get("settlement") == sid]
    keep = [q for q in doc["placements"] if q.get("settlement") != sid]
    at = old[0] if old else len(keep)
    doc["placements"] = keep[:at] + recs + keep[at:]
    ts = trad["traders"]
    i = next((k for k, t in enumerate(ts) if t.get("id") == clerk["id"]), None)
    if i is None:
        ts.append(clerk)
    else:
        ts[i] = clerk
    return doc, trad


def dump(doc, indent):
    return json.dumps(doc, indent=indent, ensure_ascii=False) + "\n"


# ------------------------------------------------------------------------------------------------------------ verify

def expected(writers, model):
    """{(x, y, z): block} the town should hold: every earthwork's final blocks, and the square's paving."""
    out = {}
    for W in writers.values():
        out.update(W.model)
    level = model["level"]
    x0, z0, x1, z1 = model["square"]
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            out.setdefault((x, level, z), "minecraft:jungle_planks")
    return out


def verify_world(world_dir, writers, model):
    """Compare the model with a stopped world copy, block by block (names only), and look for water on a deck and
    flowing water round the town."""
    import runtime_guard
    import structure_nbt as SN
    world = runtime_guard.check(world_dir, "read")
    exp = expected(writers, model)
    level = model["level"]
    boxes = {}
    for (x, y, z) in exp:
        k = (x // 64, z // 64)
        b = boxes.setdefault(k, [x, y, z, x, y, z])
        b[0], b[1], b[2] = min(b[0], x), min(b[1], y), min(b[2], z)
        b[3], b[4], b[5] = max(b[3], x), max(b[4], y), max(b[5], z)
    got = {}
    flowing = 0
    for b in boxes.values():
        cap = SN.capture(world, (b[0], min(b[1], level - 3), b[2]), (b[3], b[4], b[5]))
        for pos, (name, props) in cap.blocks.items():
            got[pos] = name
            if name == "minecraft:water" and dict(props).get("level", "0") != "0":
                flowing += 1
    same = {"minecraft:grass_block": {"minecraft:dirt"}}
    bad, ok = [], 0
    for pos, blk in exp.items():
        want = blk.split("[")[0].split("{")[0]
        have = got.get(pos, "minecraft:air")
        if have == want or have in same.get(want, ()):
            ok += 1
        elif len(bad) < 20:
            bad.append("%s holds %s, the plan says %s" % (pos, have, want))
    wet = sorted((x, z) for x, z in model["deck"] if got.get((x, level + 1, z)) == "minecraft:water")
    return {"expected_blocks": len(exp), "matching": ok, "mismatches": len(exp) - ok, "first_mismatches": bad,
            "water_on_deck": len(wet), "water_on_deck_first": wet[:10], "flowing_water": flowing}


def verify_rcon(server_dir, writers, model, sample_every=5):
    """Over RCON on a running server, a district at a time with its chunks held: every lantern and every sample_every-th
    other block of the model tested by name with `execute if block`, and a sample of deck cells tested for water
    standing on them."""
    import time
    import place_town as PT
    import runtime_guard
    rcon, pw = runtime_guard.rcon(server_dir)
    level = model["level"]
    exp = expected(writers, model)
    out = {"tested": 0, "failed": 0, "first_failed": [], "deck_cells_tested_for_water": 0, "water_on_deck": 0,
           "water_on_deck_first": [], "districts": {}}
    parts = {d: dict(W.model) for d, W in writers.items()}
    x0, z0, x1, z1 = model["square"]
    parts["old_rafts"].update({k: v for k, v in exp.items() if x0 <= k[0] <= x1 and z0 <= k[2] <= z1 and k[1] == level})
    for did, part in parts.items():
        if not part:
            continue
        keys = sorted(part)
        pick = [k for i, k in enumerate(keys) if "lantern" in part[k] or i % sample_every == 0]
        xs = [k[0] for k in keys]
        zs = [k[2] for k in keys]
        held = (min(xs) - 2, min(zs) - 2, max(xs) + 2, max(zs) + 2)
        deck = sorted(c for c in model["deck"] if inside(held, c[0], c[1]))[::sample_every]
        rcon.run(PT.forceload_commands(held, "add"), pw)
        try:
            pending = sorted({(x >> 4, z >> 4) for x, _, z in keys})
            deadline = time.time() + 180
            while pending and time.time() < deadline:
                replies = rcon.run(["execute if loaded %d 0 %d" % (cx * 16, cz * 16) for cx, cz in pending], pw)
                pending = [c for c, r in zip(pending, replies) if "passed" not in r]
                if pending:
                    time.sleep(1)
            if pending:
                raise SystemExit("%s: %d chunks were still not loaded after three minutes" % (did, len(pending)))
            tests = ["execute if block %d %d %d %s" % (x, y, z, part[(x, y, z)].split("[")[0].split("{")[0])
                     for x, y, z in pick]
            bad = [t for t, r in zip(tests, rcon.run(tests, pw)) if "passed" not in r]
            wet_t = ["execute if block %d %d %d minecraft:water" % (x, level + 1, z) for x, z in deck]
            wet = [t for t, r in zip(wet_t, rcon.run(wet_t, pw)) if "passed" in r]
        finally:
            rcon.run(PT.forceload_commands(held, "remove"), pw)
        out["districts"][did] = {"tested": len(tests), "failed": len(bad), "water_on_deck": len(wet)}
        out["tested"] += len(tests)
        out["failed"] += len(bad)
        out["first_failed"] += bad[:20 - len(out["first_failed"])]
        out["deck_cells_tested_for_water"] += len(wet_t)
        out["water_on_deck"] += len(wet)
        out["water_on_deck_first"] += wet[:10 - len(out["water_on_deck_first"])]
    if not out["tested"]:
        raise SystemExit("nothing was tested: the model is empty")
    return out


# -------------------------------------------------------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "write", "check", "verify"):
        q = sub.add_parser(name)
        q.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"),
                       help="heightmap root: the only source of ground (tools/ground.py)")
        if name == "verify":
            g = q.add_mutually_exclusive_group(required=True)
            g.add_argument("--world", help="a STOPPED world copy (never the live save)")
            g.add_argument("--rcon", metavar="SERVER_DIR", help="a running server, under the coordination lock")
    a = p.parse_args(argv)
    plan, settlement, recs, clerk, report, writers, model = generate(a.source_root)
    DERIVED.mkdir(parents=True, exist_ok=True)
    if a.cmd == "plan":
        (DERIVED / "plan.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "depths"}, indent=1))
        for i, d in report["depths"].items():
            print("  %-28s %-10s depth %2d..%2d  seabed y%d..y%d" % (i, d["kind"], d["depth"][0], d["depth"][1],
                                                                     d["seabed_y"][0], d["seabed_y"][1]))
        return 0
    doc_text = PLACEMENTS.read_text(encoding="utf-8")
    trad_text = TRADERS.read_text(encoding="utf-8")
    doc, trad = apply(json.loads(doc_text), json.loads(trad_text), plan, settlement, recs, clerk)
    new_doc, new_trad = dump(doc, 2), dump(trad, 2)
    if a.cmd == "write":
        PLACEMENTS.write_text(new_doc, encoding="utf-8", newline="\n")
        TRADERS.write_text(new_trad, encoding="utf-8", newline="\n")
        (DERIVED / "plan.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        n = sum(len(r.get("commands") or []) for r in recs)
        print("wrote %s: %d placements (%d earthwork commands), clerk at %s" % (plan["settlement"], len(recs), n, clerk["position"]))
        return 0
    if a.cmd == "check":
        stale = []
        if json.loads(new_doc) != json.loads(doc_text):
            stale.append("data/placements.json")
        if json.loads(new_trad) != json.loads(trad_text):
            stale.append("data/traders.json")
        if stale:
            print("STALE: %s no longer match(es) what data/sea_town.json generates; run python tools/sea_town.py write"
                  % " and ".join(stale))
            return 1
        print("sea_town: data/placements.json and data/traders.json match data/sea_town.json")
        return 0
    res = verify_world(a.world, writers, model) if a.world else verify_rcon(a.rcon, writers, model)
    (DERIVED / "verify.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    clean = not res.get("mismatches") and not res.get("failed") and not res.get("water_on_deck") and not res.get("flowing_water")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
