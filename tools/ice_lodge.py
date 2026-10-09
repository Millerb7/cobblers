#!/usr/bin/env python
"""The Merian Ice Lodge: the Merian hut's cirque floor given a frozen tarn, shelters over holes in the ice, a lodge on the
shore, drying racks and gear, and a holekeeper who knows the water. Everything from data/ice_lodge.json.

The owner, 2026-10-09: "MERIAN HUT becomes an ICE FISHING LODGE. It sits at the major river's source, and that is what
anyone living there would actually be doing. Holes cut in the ice, shelters, gear, someone who knows the water. Connect
it to fishing for prizes if that system exists by then."

WHAT THIS ADDS AND WHAT IT LEAVES. The hut's Pokemon Center (the waystone, the blackout checkpoint), its woodshed and
stable, the Hut Warden's larder and the three working or placed Pokemon are not touched: this pack writes south of the
yard (z >= 1042) and keeps clear of the cirque path. It is a second cluster, the water and what is done on it, 25 to 60
blocks from the apron.

THE PREMISE, MEASURED (data/ice_lodge.json premise_check): the major river's cut course starts at (3132, 1632), 690
blocks from the hut, and data/landmarks.json says no basin holds water in the Merian outline. The tarn is therefore
authored here as the cirque's own meltwater, and the keeper says where the creek comes up (a walk to the south-east).

FISHING FOR PRIZES. No prize system exists (docs/world-building/ICE_LODGE.md section 5): Cobblemon 1.8.0 has native
fishing loot (cobblemon:fishing/pokerod_treasure, gated on the bobber being in open water) and the dialogue compiler
can take a held item and grant a once-only reward, but nothing in this repository authors a fishing prize. This pack
builds the PLACE the hook needs, the Lead (the only open water, where the open-water predicate can hold), and the
catch board that the hook would write to. It grants nothing and sets no state but the keeper's dialogue cursor.

  python tools/ice_lodge.py build  [--source-root R] [--out DIR]   write the pack
  python tools/ice_lodge.py plan   [--source-root R]               print the numbers and the steps; writes nothing
  python tools/ice_lodge.py probes [--write]                       presence probes (data/world_probes.json ice_lodge)

The re-application is step R18IL (tools/reapply.py): the blocks, held in a forceload, then the keeper over RCON (her
class loads at boot from cobblers_ice_lodge, so the pack is installed before the restart).

Every Y comes from tools/ground.py (the canonical heightmap, rounded), never a world. The guards below fail the build;
they are not the audit (tools/ice_lodge_audit.py is, and it imports nothing from here).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import compile_dialogue as CD  # noqa: E402
import function_limits  # noqa: E402

DATA = ROOT / "data" / "ice_lodge.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_ice_lodge"
SCHEMA = "cobblers.ice-lodge/1"
NS = "cobblers"
FN = "ice_lodge"
QUEST = "ice_lodge"
PACK_FORMAT = 48          # Minecraft 1.21.1
SCOPE = "ice_lodge"       # the word a data/spawn_block_policy.json entry's scope must contain
CLEAR_TAG = "#minecraft:replaceable"
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()

LIGHT = {"minecraft:lantern": 15, "minecraft:soul_lantern": 10, "minecraft:campfire": 15}
ICE_FAMILY = ("minecraft:ice", "minecraft:packed_ice", "minecraft:blue_ice")


class IceError(SystemExit):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load(path=DATA):
    doc = load_json(path)
    if doc.get("schema") != SCHEMA:
        raise IceError("%s: schema must be %s" % (path, SCHEMA))
    ids = [s["id"] for s in doc["shelters"]] + [s["id"] for s in doc["stations"]] + [r["id"] for r in doc["racks"]]
    if len(ids) != len(set(ids)):
        raise IceError("shelter, station and rack ids must be unique")
    return doc


def base(state):
    return state.split("[")[0].split("{")[0]


def hash01(x, z, salt=0):
    """A fixed pseudo-random number in [0, 1) for a column: the same column always gives the same number."""
    h = (x * 73856093) ^ (z * 19349663) ^ (salt * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0x1000000)


def box_cells(b):
    x0, z0, x1, z1 = b
    return [(x, z) for x in range(min(x0, x1), max(x0, x1) + 1) for z in range(min(z0, z1), max(z0, z1) + 1)]


# ------------------------------------------------------------------------------------------------------------ the tarn
def tarn_mask(doc):
    out = set()
    for lobe in doc["tarn"]["lobes"]:
        cx, cz = lobe["c"]
        rx, rz = lobe["rx"], lobe["rz"]
        for x in range(cx - rx, cx + rx + 1):
            for z in range(cz - rz, cz + rz + 1):
                if ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2 <= 1.0:
                    out.add((x, z))
    return out


def edge_distance(mask):
    """{cell: 1 for a cell with a 4-neighbour outside the tarn, 2 for the next ring in, ...}."""
    dist, frontier = {}, [c for c in mask if any((c[0] + dx, c[1] + dz) not in mask for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    for c in frontier:
        dist[c] = 1
    d = 1
    while frontier:
        nxt = []
        for x, z in frontier:
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, z + dz)
                if n in mask and n not in dist:
                    dist[n] = d + 1
                    nxt.append(n)
        frontier, d = nxt, d + 1
    return dist


def depth_for(d, table):
    for upto, depth in table:
        if d <= upto:
            return depth
    return table[-1][1]


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """{(x, y, z): state} in three stages: the structure (bottom up), what hangs on or stands on it (top down), doors.
    A later put of a cell replaces an earlier one in its stage and in the dict, so layering is simply the order of calls."""

    def __init__(self, doc, g):
        self.doc, self.g = doc, g
        self.solid, self.hung, self.doors, self.clears = {}, {}, [], []
        self.allowed = set(doc["blocks"]["ids"])

    def _check(self, state):
        if base(state) not in self.allowed:
            raise IceError("%s is not in data/ice_lodge.json blocks.ids" % base(state))

    def put(self, x, y, z, state):
        self._check(state)
        self.hung.pop((x, y, z), None)
        self.solid[(x, y, z)] = state

    def hang(self, x, y, z, state):
        self._check(state)
        self.solid.pop((x, y, z), None)
        self.hung[(x, y, z)] = state

    def door(self, x, z, y, facing, hinge):
        for half, d in (("lower", 0), ("upper", 1)):
            st = "minecraft:spruce_door[facing=%s,half=%s,hinge=%s,open=false,powered=false]" % (facing, half, hinge)
            self._check(st)
            self.solid.pop((x, y + d, z), None)
            self.hung.pop((x, y + d, z), None)
            self.doors.append(((x, y + d, z), st))

    def clear(self, x0, z0, x1, z1, y0, y1):
        self.clears.append((min(x0, x1), y0, min(z0, z1), max(x0, x1), y1, max(z0, z1)))

    def blocks(self):
        out = dict(self.solid)
        out.update(self.hung)
        out.update(dict(self.doors))
        return out


def wall_sign(facing, lines):
    q = ",".join("'%s'" % json.dumps(t).replace("'", "\\'") for t in (list(lines) + ["", "", "", ""])[:4])
    return "minecraft:spruce_wall_sign[facing=%s,waterlogged=false]{front_text:{messages:[%s]},is_waxed:1b}" % (facing, q)


def pool(p, mask, walls):
    """Bed, water and ice for every tarn cell; the Lead and the holes are cut by their own callers."""
    t = p.doc["tarn"]
    sy, wt = t["surface_y"], t["water_top_y"]
    dist = edge_distance(mask)
    fr = t["frost"]
    for (x, z) in sorted(mask):
        depth = depth_for(dist[(x, z)], t["depth_by_distance_from_edge"])
        p.put(x, wt - depth, z, t["bed"])
        for y in range(wt - depth + 1, wt + 1):
            p.put(x, y, z, "minecraft:water")
        r = hash01(x, z, 11)
        if r < fr["blue_share"]:
            ice = fr["blue"]
        elif r < fr["blue_share"] + fr["share"]:
            ice = fr["block"]
        else:
            ice = t["ice"]
        p.put(x, sy, z, ice)
    xs = [c[0] for c in mask]
    zs = [c[1] for c in mask]
    p.clear(min(xs), min(zs), max(xs), max(zs), sy + 1, sy + 6)
    return dist


def lead(p, mask):
    d = p.doc["lead"]
    sy = p.doc["tarn"]["surface_y"]
    cells = box_cells(d["box"])
    for x, z in cells:
        if (x, z) not in mask:
            raise IceError("the Lead's column (%d, %d) is not in the tarn" % (x, z))
        p.put(x, sy, z, "minecraft:air")
    x0, z0, x1, z1 = d["box"]
    gap = {tuple(c) for c in d["gap"]}
    ring = [(x, z) for x in range(x0 - 1, x1 + 2) for z in range(z0 - 1, z1 + 2) if not (x0 <= x <= x1 and z0 <= z <= z1)]
    for x, z in ring:
        if (x, z) in gap:
            p.put(x, sy, z, p.doc["walks"]["block"])
        elif d.get("fence_ring"):
            if (x, z) not in mask:
                raise IceError("the Lead's fence ring column (%d, %d) is not on the ice" % (x, z))
            p.put(x, sy + 1, z, "minecraft:spruce_fence")
    (sx0, sz0), (sx1, sz1) = d["stub"]
    for x, z in box_cells([sx0, sz0, sx1, sz1]):
        p.put(x, sy, z, p.doc["walks"]["block"])
    px, pz = d["post"]
    p.put(px, sy + 1, pz, "minecraft:stripped_spruce_log[axis=y]")
    p.put(px, sy + 2, pz, "minecraft:stripped_spruce_log[axis=y]")
    gx, gz = d["sign_at"]
    p.hang(gx, sy + 1, gz, wall_sign("west", d["sign"]))
    return set(cells)


def walks(p):
    sy = p.doc["tarn"]["surface_y"]
    cells = set()
    for w in p.doc["walks"]["list"]:
        for x, z in box_cells(w["box"]):
            cells.add((x, z))
            p.put(x, sy, z, p.doc["walks"]["block"])
    return cells


def stations(p, mask, taken):
    sy = p.doc["tarn"]["surface_y"]
    for s in p.doc["stations"]:
        for key in ("hole", "stool"):
            c = tuple(s[key])
            if c not in mask:
                raise IceError("station %s: its %s %s is not on the ice" % (s["id"], key, c))
            if c in taken:
                raise IceError("station %s: its %s %s is on a walk, the Lead or a shelter" % (s["id"], key, c))
        hx, hz = s["hole"]
        p.put(hx, sy, hz, "minecraft:air")
        kx, kz = s["stool"]
        p.put(kx, sy + 1, kz, "minecraft:spruce_slab[type=bottom]")
        taken.add(tuple(s["hole"]))
        taken.add(tuple(s["stool"]))
        if "extra" in s:
            blk, (ex, ez) = s["extra"]
            if (ex, ez) not in mask or (ex, ez) in taken:
                raise IceError("station %s: its extra %s is not on free ice" % (s["id"], (ex, ez)))
            p.put(ex, sy + 1, ez, blk)
            taken.add((ex, ez))


DIRS = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}
OPPOSITE = {"north": "south", "south": "north", "west": "east", "east": "west"}


def shelters(p, mask, taken):
    sy = p.doc["tarn"]["surface_y"]
    sh = p.doc["shelter"]
    n = sh["size"] // 2
    for s in p.doc["shelters"]:
        cx, cz = s["c"]
        cells = [(cx + a, cz + b) for a in range(-n, n + 1) for b in range(-n, n + 1)]
        for c in cells:
            if c not in mask:
                raise IceError("%s: column %s is off the ice" % (s["id"], c))
            if c in taken:
                raise IceError("%s: column %s is already used" % (s["id"], c))
            taken.add(c)
        dx, dz = DIRS[s["door"]]
        door = (cx + dx * n, cz + dz * n)
        r = sh["frost_radius"]
        for x in range(cx - r, cx + r + 1):
            for z in range(cz - r, cz + r + 1):
                if abs(x - cx) + abs(z - cz) <= r and p.solid.get((x, sy, z)) in ICE_FAMILY:
                    p.put(x, sy, z, sh["floor"])
        for (x, z) in cells:
            ring = max(abs(x - cx), abs(z - cz)) == n
            p.put(x, sy, z, sh["floor"])
            if not ring:
                p.put(x, sy + 1, z, "minecraft:air")
                p.put(x, sy + 2, z, "minecraft:air")
                p.put(x, sy + 3, z, "minecraft:air")
                continue
            corner = abs(x - cx) == n and abs(z - cz) == n
            for h in (1, 2, 3):
                if corner:
                    p.put(x, sy + h, z, "minecraft:spruce_log[axis=y]")
                elif (x, z) == door and h <= 2:
                    p.put(x, sy + h, z, "minecraft:air")
                elif h == 2 and (x, z) in ((cx, cz - n), (cx, cz + n), (cx - n, cz), (cx + n, cz)):
                    # a window on each wall but the door's
                    ns = abs(z - cz) == n
                    p.put(x, sy + h, z, "minecraft:glass_pane[east=true,west=true]" if ns else "minecraft:glass_pane[north=true,south=true]")
                else:
                    p.put(x, sy + h, z, "minecraft:spruce_planks")
        p.door(door[0], door[1], sy + 1, s["door"], "left")
        # the hole: the centre column, water below, air above
        p.put(cx, sy, cz, "minecraft:air")
        # the seat at the back (opposite the door), the barrel beside it, one lantern from the ceiling over the hole
        bx, bz = cx - dx, cz - dz
        p.put(bx, sy + 1, bz, "minecraft:spruce_stairs[facing=%s,half=bottom]" % OPPOSITE[s["door"]])
        px, pz = -dz, dx                                                  # the perpendicular
        p.put(bx + px, sy + 1, bz + pz, "minecraft:barrel[facing=up]")
        for (x, z) in cells:
            if max(abs(x - cx), abs(z - cz)) <= n:
                p.put(x, sy + 4, z, "minecraft:spruce_planks")
                p.put(x, sy + 5, z, "minecraft:spruce_slab[type=bottom]")
        p.hang(cx, sy + 3, cz, "%s[hanging=true]" % sh["light"])
    return taken


# --------------------------------------------------------------------------------------------------------- the lodge
def lodge(p):
    L = p.doc["lodge"]
    x0, z0, x1, z1 = L["box"]
    f = L["floor_y"]
    rz = L["ridge_z"]
    wh = L["wall_height"]
    top = f + wh                               # the last wall course
    door_cells = {tuple(c) for c in L["door"]["cells"]}
    windows = {tuple(c) for c in L["windows"]}
    smoke = set(range(L["smoke_hole"][0], L["smoke_hole"][1] + 1))
    p.clear(x0 - 2, z0 - 7, x1 + 2, z1 + 7, f + 1, top + 8)
    hx, hz = L["hearth"]["campfire"]
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            p.put(x, f, z, "minecraft:spruce_planks")
    for x in range(hx - 1, hx + 2):
        for z in range(hz - 1, hz + 2):
            p.put(x, f, z, "minecraft:cobblestone")
    # walls
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if not (x in (x0, x1) or z in (z0, z1)):
                continue
            corner = x in (x0, x1) and z in (z0, z1)
            post = (z in (z0, z1) and (x - x0) % 4 == 0) or (x in (x0, x1) and (z - z0) % 4 == 0)
            for h in range(1, wh + 1):
                y = f + h
                if (x, z) in door_cells and h <= 2:
                    p.put(x, y, z, "minecraft:air")
                elif (x, z) in windows and h in (2, 3):
                    ns = z in (z0, z1)
                    p.put(x, y, z, "minecraft:glass_pane[east=true,west=true]" if ns else "minecraft:glass_pane[north=true,south=true]")
                elif corner or post:
                    p.put(x, y, z, "minecraft:spruce_log[axis=y]")
                elif h == 1:
                    p.put(x, y, z, "minecraft:cobblestone")
                else:
                    p.put(x, y, z, "minecraft:spruce_planks")
    # the gable ends: the triangle above the wall
    for k in range(0, 4):
        ytop = top + (5 - k) if k >= 1 else top + 4        # the roof's height at this row (the ridge matches row 1)
        for x in (x0, x1):
            for zz in (rz - k, rz + k):
                for y in range(top + 1, ytop):
                    p.put(x, y, zz, "minecraft:spruce_planks")
    # the roof: stairs up each slope, a ridge of planks, one block of overhang at each gable and each eave
    for x in range(x0 - 1, x1 + 2):
        for k in range(1, 6):
            y = top + (5 - k)
            p.put(x, y + 0, rz - k, "minecraft:spruce_stairs[facing=south,half=bottom]")
            p.put(x, y + 0, rz + k, "minecraft:spruce_stairs[facing=north,half=bottom]")
        if x not in smoke:
            p.put(x, top + 4, rz, "minecraft:spruce_planks")
    # the hearth
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if (dx, dz) != (0, 0):
                p.put(hx + dx, f + 1, hz + dz, L["hearth"]["ring"] + "[type=bottom]")
    p.put(hx, f + 1, hz, "minecraft:campfire[lit=true,signal_fire=false,facing=south]")
    # the doors: a pair, the hinges mirrored
    dc = sorted(door_cells)
    p.door(dc[0][0], dc[0][1], f + 1, L["door"]["facing"], "left")
    p.door(dc[1][0], dc[1][1], f + 1, L["door"]["facing"], "right")
    # the porch's mat just inside
    for x, z in ((dc[0][0], z1 - 1), (dc[1][0], z1 - 1), (dc[0][0], z1 - 2), (dc[1][0], z1 - 2)):
        p.put(x, f + 1, z, "minecraft:brown_carpet")
    # bunks: head to the north, foot to the south
    for b in L["bunks"]:
        hx_, hz_ = b["head"]
        p.put(hx_, f + 1, hz_ + 1, "%s[facing=north,occupied=false,part=foot]" % b["bed"])
        p.put(hx_, f + 1, hz_, "%s[facing=north,occupied=false,part=head]" % b["bed"])
    for t in L["tackle"]:
        p.put(t["at"][0], f + 1, t["at"][1], t["block"])
    for (x, z) in L["lanterns"]:
        p.put(x, f + 1, z, "minecraft:spruce_fence")
        p.hang(x, f + 2, z, "minecraft:lantern[hanging=false]")
    # the catch board: wall signs on the inside of the east wall
    bd = L["board"]
    for z, lines in zip(bd["z"], bd["lines"]):
        for y in bd["y"][:1]:
            p.hang(bd["sign_x"], y, z, wall_sign("west", lines))
    # the signs over the door, outside
    sz = z1 + 1
    p.hang(dc[0][0], f + 3, sz, wall_sign("south", L["sign_over_door"]))
    p.hang(dc[1][0], f + 3, sz, wall_sign("south", ["Pokemon Centre", "north-east,", "up the yard", ""]))


# ---------------------------------------------------------------------------------------------------- racks and gear
def racks(p):
    f = p.doc["lodge"]["floor_y"]
    for r in p.doc["racks"]:
        n = r["length"]
        x0, z = r["x0"], r["z"]
        p.clear(x0, z, x0 + n - 1, z, f + 1, f + 6)
        for x in (x0, x0 + n - 1):
            for h in (1, 2, 3):
                p.put(x, f + h, z, "minecraft:spruce_fence")
        for x in range(x0, x0 + n):
            p.put(x, f + 4, z, "minecraft:stripped_spruce_log[axis=x]")
        for x in range(x0 + 1, x0 + n - 1, 2):
            p.hang(x, f + 3, z, "minecraft:chain[axis=y]")
            p.put(x, f + 2, z, "minecraft:dried_kelp_block")
    c = p.doc["smoke_pit"]["c"]
    cx, cz = c
    p.clear(cx - 3, cz - 3, cx + 3, cz + 3, f + 1, f + 4)
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            p.put(cx + dx, f, cz + dz, "minecraft:cobblestone")
            if (dx, dz) != (0, 0):
                p.put(cx + dx, f + 1, cz + dz, "minecraft:cobblestone_slab[type=bottom]")
    p.put(cx, f + 1, cz, "minecraft:campfire[lit=true,signal_fire=false,facing=north]")
    p.put(cx + 3, f + 1, cz, "minecraft:hay_block[axis=y]")
    p.put(cx + 3, f + 1, cz + 1, "minecraft:hay_block[axis=y]")
    p.put(cx + 3, f + 2, cz, "minecraft:hay_block[axis=y]")


def yard(p):
    f = p.doc["lodge"]["floor_y"]
    y = p.doc["yard"]
    x0, z0, x1, z1 = y["frame"]["box"]
    p.clear(x0, z0, x1, z1, f + 1, f + 6)
    for x in (x0, x1):
        for z in (z0, z1):
            for h in (1, 2, 3):
                p.put(x, f + h, z, "minecraft:spruce_fence")
    for x in range(x0, x1 + 1):
        for z in (z0, z1):
            p.put(x, f + 4, z, "minecraft:stripped_spruce_log[axis=x]")
    for z in range(z0, z1 + 1):
        for x in (x0, x1):
            p.put(x, f + 4, z, "minecraft:stripped_spruce_log[axis=z]")
    sx, sz = y["ice_stack"]["c"]
    p.clear(sx, sz, sx + 2, sz + 1, f + 1, f + 4)
    for dx in range(0, 3):
        for dz in range(0, 2):
            p.put(sx + dx, f + 1, sz + dz, "minecraft:packed_ice")
            if dx < 2:
                p.put(sx + dx, f + 2, sz + dz, "minecraft:packed_ice")
    p.put(sx, f + 3, sz, "minecraft:snow_block")
    p.put(sx + 1, f + 3, sz, "minecraft:snow_block")
    kx, kz = y["sled"]["c"]
    p.clear(kx, kz, kx + 3, kz + 2, f + 1, f + 3)
    for dx in range(0, 4):
        p.put(kx + dx, f + 1, kz, "minecraft:spruce_slab[type=bottom]")
        p.put(kx + dx, f + 1, kz + 2, "minecraft:spruce_slab[type=bottom]")
    p.put(kx + 1, f + 1, kz + 1, "minecraft:spruce_planks")
    p.put(kx + 2, f + 1, kz + 1, "minecraft:spruce_planks")
    p.put(kx + 1, f + 2, kz + 1, "minecraft:barrel[facing=up]")
    p.put(kx + 2, f + 2, kz + 1, "minecraft:barrel[facing=up]")


# ------------------------------------------------------------------------------------------------------ connections
def connect(blocks):
    """Fences, panes: the faces that meet a neighbour of their own kind or a solid wall are set to true, so the
    pack does not depend on the server's shape updates running in any order."""
    fences = {k for k, s in blocks.items() if base(s) == "minecraft:spruce_fence"}
    panes = {k for k, s in blocks.items() if base(s) == "minecraft:glass_pane"}
    solid_names = ("planks", "log", "cobblestone", "packed_ice", "stone_bricks", "barrel", "loom", "table", "smoker", "composter")

    def solid(k):
        s = blocks.get(k)
        return s is not None and any(n in base(s) for n in solid_names) and "slab" not in base(s) and "stairs" not in base(s)

    for (x, y, z) in fences:
        st = {"north": (x, y, z - 1) in fences, "south": (x, y, z + 1) in fences, "east": (x + 1, y, z) in fences,
              "west": (x - 1, y, z) in fences}
        st = {d: (v or solid((x + DIRS[d][0], y, z + DIRS[d][1]))) for d, v in st.items()}
        blocks[(x, y, z)] = "minecraft:spruce_fence[%s,waterlogged=false]" % ",".join("%s=%s" % (d, str(v).lower()) for d, v in sorted(st.items()))
    return blocks


# ---------------------------------------------------------------------------------------------------------- the build
def plan(doc, g):
    p = Plan(doc, g)
    mask = tarn_mask(doc)
    dist = pool(p, mask, set())
    lead_cells = lead(p, mask)
    walk_cells = walks(p)
    taken = set(lead_cells) | walk_cells
    for x, z in box_cells([doc["lead"]["box"][0] - 1, doc["lead"]["box"][1] - 1, doc["lead"]["box"][2] + 1, doc["lead"]["box"][3] + 1]):
        taken.add((x, z))
    shelters(p, mask, taken)
    stations(p, mask, taken)
    lodge(p)
    racks(p)
    yard(p)
    blocks = connect(p.blocks())
    keeper = doc["keeper"]
    kx, kz = keeper["at"]
    npc = (kx, doc["lodge"]["floor_y"] + 1, kz)
    for y in (npc[1], npc[1] + 1):
        if blocks.get((kx, y, kz), "minecraft:air") != "minecraft:air":
            raise IceError("the keeper's spot %s is not two blocks of air (%s)" % (npc, blocks.get((kx, y, kz))))
    if blocks.get((kx, npc[1] - 1, kz)) is None:
        raise IceError("the keeper's floor is not written")
    return {"plan": p, "mask": mask, "dist": dist, "blocks": blocks, "npc": npc, "lead": lead_cells, "walks": walk_cells}


def guards(doc, g, pl):
    """Fail-closed siting rules (the builder's; the independent audit is tools/ice_lodge_audit.py)."""
    blocks = pl["blocks"]
    level = doc["site"]["level"]
    cols = {(x, z) for (x, y, z) in blocks}
    probs = []
    bad = sorted(c for c in cols if g(*c) != level)
    if bad:
        probs.append("%d written column(s) are not on the cirque floor y%d (ground %s); first %s"
                     % (len(bad), level, sorted({g(*c) for c in bad}), bad[:3]))
    # the water's containment: every tarn cell's neighbour column must be tarn or ground at the floor
    mask = pl["mask"]
    for (x, z) in mask:
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, z + dz)
            if n not in mask and g(*n) < level:
                probs.append("water at %s borders ground y%d at %s" % ((x, z), g(*n), n))
                break
    sx0, sz0, sx1, sz1 = doc["site"]["bounds"]
    out = sorted(c for c in cols if not (sx0 <= c[0] <= sx1 and sz0 <= c[1] <= sz1))
    if out:
        probs.append("%d column(s) outside site.bounds; first %s" % (len(out), out[:3]))
    for kc in doc["site"]["keep_clear"]:
        x0, z0, x1, z1 = kc["box"]
        hit = sorted(c for c in cols if x0 <= c[0] <= x1 and z0 <= c[1] <= z1)
        if hit:
            probs.append("writes %s inside %s" % (hit[:3], kc["id"]))
    # the spawn conditions: only what a policy entry scoped to this place allows
    sb = set(load_json(ROOT / "data" / "spawn_blocks.json")["blocks"])
    policy = load_json(ROOT / "data" / "spawn_block_policy.json")
    allowed = {b for w in policy["whitelist"] if SCOPE in (w.get("scope") or "") for b in w["blocks"]}
    named = sorted({base(s) for s in blocks.values()} & sb - allowed)
    if named:
        probs.append("writes spawn-condition block(s) %s that no data/spawn_block_policy.json entry scoped to %s allows"
                     % (named, SCOPE))
    # the melting rule: a light of level L kept L - 7 blocks (Manhattan) from every cell of plain ice
    margin = doc["tarn"]["light_rule"]["margin"]
    lim = doc["tarn"]["light_rule"]["melts_above_block_light"] - margin
    ice = [k for k, s in blocks.items() if s == "minecraft:ice"]
    for k, s in blocks.items():
        lv = LIGHT.get(base(s))
        if lv is None or (base(s) == "minecraft:campfire" and "lit=false" in s):
            continue
        if lv <= lim:
            continue
        d = min(abs(k[0] - i[0]) + abs(k[1] - i[1]) + abs(k[2] - i[2]) for i in ice)
        if d < lv - lim:
            probs.append("%s at %s is %d from plain ice (a level-%d light needs %d)" % (base(s), k, d, lv, lv - lim))
    # nobody else's authored x/z within the clearance
    import numpy as np
    import southern_residents as SR
    pts = [pt for pt in SR.authored_points({"residents": []}, own_file=DATA) if pt[2] not in ("regions.json", "route_paths.json", "world_probes.json")]
    pts = [pt for pt in pts if not (pt[2] == "landmarks.json" and (pt[0], pt[1]) == (2754, 1055))]
    P = np.array([(a, b) for a, b, _f in pts], float)
    C = np.array(sorted(cols), float)
    near = 1e9
    for i in range(0, len(C), 400):
        d = np.hypot(P[None, :, 0] - C[i:i + 400, None, 0], P[None, :, 1] - C[i:i + 400, None, 1])
        near = min(near, float(d.min()))
        if d.min() < doc["site"]["authored_clearance"]:
            j = np.unravel_index(np.argmin(d), d.shape)
            probs.append("(%d, %d) is %.1f from an x/z authored in data/%s (needs %d)"
                         % (C[i + j[0]][0], C[i + j[0]][1], d.min(), pts[j[1]][2], doc["site"]["authored_clearance"]))
            break
    if probs:
        raise IceError("the lodge's siting rules refuse the build:\n  " + "\n  ".join(probs))
    return {"nearest_authored_point": round(near, 1)}


# ---------------------------------------------------------------------------------------------------------- the pack
def runs(blocks, top_down=False):
    """setblock and fill lines for {(x, y, z): state}: one fill per run of one state along x."""
    out = []
    keys = sorted(blocks, key=lambda k: (-k[1] if top_down else k[1], k[2], k[0]))
    i = 0
    while i < len(keys):
        x, y, z = keys[i]
        st = blocks[keys[i]]
        j = i
        while (j + 1 < len(keys) and keys[j + 1] == (keys[j][0] + 1, y, z) and blocks[keys[j + 1]] == st
               and "{" not in st):
            j += 1
        if j == i:
            out.append("setblock %d %d %d %s" % (x, y, z, st))
        else:
            out.append("fill %d %d %d %d %d %d %s" % (x, y, z, keys[j][0], y, z, st))
        i = j + 1
    return out


def build_lines(doc, pl):
    p = pl["plan"]
    over = set(p.hung) | {k for k, _st in p.doors}
    structure = {k: st for k, st in pl["blocks"].items() if k not in over and k not in dict(p.doors)}
    hung = {k: pl["blocks"][k] for k in p.hung}
    out = ["# Generated by tools/ice_lodge.py from data/ice_lodge.json. Re-run to rebuild; do not edit.",
           "# The Merian Ice Lodge: the tarn (bed, water, ice), the Lead, the holes, the shelters, the lodge, the racks and gear.",
           "# 1. clear snow and plants over each feature's box (only what #minecraft:replaceable names)"]
    for x0, y0, z0, x1, y1, z1 in p.clears:
        out.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, CLEAR_TAG))
    out.append("# 2. the structure, bottom up")
    out += runs(structure)
    out.append("# 3. what hangs on it or stands on it, from the top: chain, lanterns, signs")
    out += runs(hung, top_down=True)
    out.append("# 4. the doors, lower half then upper")
    out += ["setblock %d %d %d %s" % (k + (st,)) for k, st in p.doors]
    return out


def conversation(doc):
    k = doc["keeper"]
    field = "quest.%s.keeper_cursor" % QUEST
    sp = "ketil"
    responses = [{"id": "r_%s" % t["id"], "text": t["ask"], "next": t["id"]} for t in k["topics"]]
    responses.append({"id": "r_leave", "text": k["leave"], "actions": [{"kind": "close_dialogue"}]})
    nodes = [{"id": "hub", "kind": "choice", "speaker": sp, "text": k["greeting"], "responses": responses}]
    nodes += [{"id": t["id"], "kind": "line", "speaker": sp, "text": t["says"], "next": "hub"} for t in k["topics"]]
    conv = {"id": "dlg_%s" % k["id"], "quest_id": QUEST, "npc_id": "npc_%s" % k["id"], "npc_name": k["name"],
            "scope": "player", "speakers": {sp: k["name"]},
            "cursor": {"progression_field": field, "initial_node": "hub"},
            "entry_rules": [{"priority": 10, "when": {"kind": "always"}, "node": "hub"}],
            "nodes": nodes}
    quest = {"id": QUEST, "progression_field_refs": [field], "transitions": [], "rewards": []}
    return conv, quest


def files(doc, g):
    pl = plan(doc, g)
    meta = guards(doc, g, pl)
    lines = function_limits.ensure_loaded(build_lines(doc, pl))
    bad = function_limits.check_lines(lines, "build")
    if bad:
        raise IceError("build: %d command(s) the server would refuse: %s" % (len(bad), bad[:3]))
    out = {
        "pack.mcmeta": {"pack": {"pack_format": PACK_FORMAT, "description": "Cobblers: the Merian Ice Lodge (tools/ice_lodge.py)"}},
        "data/%s/function/%s/build.mcfunction" % (NS, FN): lines,
    }
    fields = {fd["id"]: fd for fd in load_json(ROOT / "data" / "progression.json")["quest_fields"]}
    conv, quest = conversation(doc)
    got = CD.compile_conversation(conv, {quest["id"]: quest}, fields)
    clash = [k for k in got if k in out]
    if clash:
        raise IceError("the keeper's conversation writes %s twice" % clash)
    out.update(got)
    return out, pl, meta


def hold_box(doc):
    x0, z0, x1, z1 = doc["site"]["hold"]
    return "%d %d %d %d" % (x0, z0, x1, z1)


def placement_steps(doc=None, g=None):
    """For tools/reapply.py, step R18IL: hold the chunks, build, release, then the keeper (her class loads at boot)."""
    doc = doc or load()
    hold = hold_box(doc)
    return ([("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (NS, FN)),
             ("cmd", "forceload remove " + hold)]
            + [("npc", n) for n in npc_placements(doc, g)])


def npc_placements(doc=None, g=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for tools/reapply.py's "npc" action. She stands on the lodge floor
    (the floor_y in the record, which the generator checks is the heightmap ground at every column of the lodge)."""
    doc = doc or load()
    k = doc["keeper"]
    x, z = k["at"]
    return [("dlg_%s" % k["id"], (x, doc["lodge"]["floor_y"] + 1, z), "%s:npc_%s" % (NS, k["id"]), k["yaw"])]


def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, list):
            body = "\n".join(content) + "\n"
        elif isinstance(content, str):
            body = content
        else:
            body = json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        f.write_text(body, encoding="utf-8", newline="\n")


# -------------------------------------------------------------------------------------------------------------- probes
def presence_probes(doc, pl):
    """Presence probes in data/world_probes.json's shape. Each is a block the PLAN says is there; the audit re-derives
    the same plan from the record independently."""
    b = pl["blocks"]
    sy = doc["tarn"]["surface_y"]
    rows = []

    def add(what, x, y, z, state=None):
        rows.append({"what": what, "block": [x, y, z, state or b[(x, y, z)]], "expect": True})

    lx0, lz0, lx1, lz1 = doc["lead"]["box"]
    lcx, lcz = (lx0 + lx1) // 2, (lz0 + lz1) // 2
    add("the Lead: open water under open air (the only place the open-water check can hold)", lcx, sy - 1, lcz, "minecraft:water")
    add("the Lead: air at the surface", lcx, sy, lcz, "minecraft:air")
    add("the Lead: air over it too", lcx, sy + 1, lcz, "minecraft:air")
    s = doc["stations"][0]
    hx, hz = s["hole"]
    add("a fishing hole: air in the ice", hx, sy, hz, "minecraft:air")
    add("a fishing hole: water under it", hx, sy - 1, hz, "minecraft:water")
    add("its stool beside it", s["stool"][0], sy + 1, s["stool"][1])
    ice_cells = sorted(k for k, st in b.items() if st == "minecraft:ice" and k[1] == sy)
    for c in (ice_cells[0], ice_cells[len(ice_cells) // 2], ice_cells[-1]):
        add("clear ice on the tarn", c[0], c[1], c[2], "minecraft:ice")
    deep = max(pl["dist"], key=lambda c: (pl["dist"][c], c))
    add("the tarn's deepest column: water at the bed", deep[0], sy - 5, deep[1], "minecraft:water")
    add("... gravel under it", deep[0], sy - 6, deep[1], "minecraft:gravel")
    for s in doc["shelters"]:
        cx, cz = s["c"]
        add("%s: the hole in its floor" % s["id"], cx, sy, cz, "minecraft:air")
        add("%s: water under the hole" % s["id"], cx, sy - 1, cz, "minecraft:water")
        add("%s: its packed-ice floor" % s["id"], cx + 1, sy, cz + 1, "minecraft:packed_ice")
    L = doc["lodge"]
    for c in L["door"]["cells"]:
        add("the lodge door (lower half)", c[0], L["floor_y"] + 1, c[1], "minecraft:spruce_door[half=lower]")
    hx, hz = L["hearth"]["campfire"]
    add("the hearth's campfire", hx, L["floor_y"] + 1, hz, "minecraft:campfire")
    for bk in L["bunks"][:1] + L["bunks"][-1:]:
        add("%s: the bed's head" % bk["id"], bk["head"][0], L["floor_y"] + 1, bk["head"][1], bk["bed"].split("[")[0] + "[part=head]")
    lx, lz = L["lanterns"][0]
    add("a lodge lantern", lx, L["floor_y"] + 2, lz, "minecraft:lantern")
    for w in doc["walks"]["list"][:1]:
        x0, z0, x1, z1 = w["box"]
        add("the boardwalk spine", x0, sy, (z0 + z1) // 2, "minecraft:spruce_planks")
    r = doc["racks"][0]
    add("a drying rack's beam", r["x0"] + 3, L["floor_y"] + 4, r["z"], "minecraft:stripped_spruce_log")
    kx, ky, kz = pl["npc"]
    rows.append({"what": "Ketil Aune, the holekeeper, after R18IL", "entity": "@e[type=cobblemon:npc,x=%d,y=%d,z=%d,distance=..2]" % (kx, ky, kz),
                 "count": 1, "hold": [kx, ky, kz]})
    return {"ice_lodge": rows}


# -------------------------------------------------------------------------------------------------------------- main
def report(doc, pl, meta, out_files):
    b = pl["blocks"]
    xs, zs = [k[0] for k in b], [k[2] for k in b]
    ys = [k[1] for k in b]
    fn = out_files["data/%s/function/%s/build.mcfunction" % (NS, FN)]
    n = sum(1 for l in fn if l and not l.startswith("#"))
    ice = sum(1 for s in b.values() if s == "minecraft:ice")
    water = sum(1 for s in b.values() if s == "minecraft:water")
    return ["tarn: %d columns, %d water blocks, %d plain ice blocks, depth 2-5; the Lead %d columns; %d fishing holes + %d shelter holes"
            % (len(pl["mask"]), water, ice, len(pl["lead"]), len(doc["stations"]), len(doc["shelters"])),
            "blocks written %d (air %d); x%d..%d z%d..%d y%d..%d; build function: %d commands; nearest authored point %s"
            % (len(b), sum(1 for s in b.values() if s == "minecraft:air"), min(xs), max(xs), min(zs), max(zs), min(ys), max(ys), n,
               meta["nearest_authored_point"]),
            "the keeper stands at %s, yaw %d" % (pl["npc"], doc["keeper"]["yaw"]),
            "step R18IL: %s" % json.dumps([list(s[:2]) if s[0] != "npc" else ["npc", s[1][0], list(s[1][1]), s[1][2], s[1][3]]
                                           for s in placement_steps(doc)])]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "plan", "probes"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, pl, meta = files(doc, g)
    if a.cmd == "plan":
        print("\n".join(report(doc, pl, meta, out_files)))
        return 0
    if a.cmd == "probes":
        probes = presence_probes(doc, pl)
        if a.write:
            wp = ROOT / "data" / "world_probes.json"
            d = load_json(wp)
            d["places"].update(probes)
            wp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print("wrote %d place(s) into data/world_probes.json" % len(probes))
        for k, v in probes.items():
            print(k, len(v), "probes")
        return 0
    write(out_files, a.out)
    print("ice_lodge: %d files -> %s" % (len(out_files), a.out))
    print("\n".join(report(doc, pl, meta, out_files)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
