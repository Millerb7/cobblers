#!/usr/bin/env python
"""Hollin's Apricorn Farm, from data/apricorn_farm.json: seven terraced groves of working apricorn trees round a farmyard
at (2068, 5570), with a farmhouse, a barn, two drying sheds, a water tower, a farm stall, lanes, gates, lanterns and
signs; the farmer and the stall's CobbleDollars merchant.

The owner, 2026-10-05: "make an apricorn farm at 2068 5570, make it big and elaborate."

Nothing here is new machinery:

  the blocks     vanilla 1.21.1 and Cobblemon 1.8.0 blocks (data/apricorn_farm.json blocks.ids, each cobblemon id read
                 from the jar's blockstates). Every Y from tools/ground.py (the canonical heightmap, rounded), never a
                 world. A grove's terrace floor is the median ground of its plot, cut and filled to it; a building's
                 floor is max(ground under its footprint) + 1 on a foundation (tools/old_orchard.py's convention); a
                 path, post, sign or object stands on its own column's ground. Logs, leaves and plants are cleared over
                 each feature first.
  the trees      the seven designs of docs/world-building/WORLDGEN_RECOVERY.md section c (EXP-019's frame), authored
                 as layer grids in the data. A fruit's `facing` points AT a leaf in its own layer, because
                 ApricornBlock.canSurvive needs #cobblemon:apricorn_leaves at pos.relative(facing) (read from the
                 1.8.0 jar; data/apricorn_farm.json apricorn_facts). Planted fruit regrows on its own (randomTick:
                 1 in 5, age < 3); a ripe one gives its apricorn on a right-click and goes back to age 0.
  the farmer     a conversation in data/dialogue.json (dlg_apricorn_farmer) compiled into cobblers_dialogue by
                 tools/compile_dialogue.py --all, placed by tools/reapply.py's "npc" action from npc_placements()
                 (step R18AF, after R17N), turned to her yaw, as the Old Orchard's keeper is.
  the stall      a CobbleDollars merchant (data/markets.json stall_merchant's entity, VillagerData and CobbleMerchantShop
                 shape; tools/traders.py summon_line), summoned by this pack's merchant function and de-duplicated by
                 tag 100 ticks later, as tools/markets.py's stall merchants are.

The checks here are the builder's guards and fail the build: blocks outside blocks.ids; spawn-condition blocks other
than the seven fruits (which data/spawn_block_policy.json must still whitelist); a write on a wet column; a fruit with
no leaf to face; a tree, post or object on a path, gate or another piece; a gate whose outside ground is more than one
block from its terrace floor; the farmer's or the keeper's spot without two blocks of room; the siting rules
(data/apricorn_farm.json rules). The independent audit is another agent's (data/apricorn_farm.json audit_checklist).

  python tools/apricorn_farm.py build [--source-root R] [--out DIR]    write build/datapacks/cobblers_apricorn_farm
  python tools/apricorn_farm.py plan  [--source-root R]                the numbers and the steps; writes nothing
  python tools/apricorn_farm.py --report                               the same as plan

The re-application (tools/reapply.py): placement_steps() is R9AF (BEFORE R9E with the other block passes);
entity_steps() is R18AF (after R17N): the farmer, then the stall merchant.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "apricorn_farm.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_apricorn_farm"
SCHEMA = "cobblers.apricorn-farm/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
COLOURS = ("red", "blue", "yellow", "green", "pink", "white", "black")
LEAVES = "cobblemon:apricorn_leaves[distance=1,persistent=true,waterlogged=false]"
LOG_Y = "cobblemon:apricorn_log[axis=y]"
LOG_X = "cobblemon:apricorn_log[axis=x]"
LANTERN = "minecraft:lantern[hanging=false,waterlogged=false]"
CLEAR_TAGS = ("#minecraft:logs", "#minecraft:leaves", "#minecraft:replaceable")
DIRS = (("north", 0, -1), ("east", 1, 0), ("south", 0, 1), ("west", -1, 0))
MERCHANT_KIND = "cobbledollars:cobble_merchant"
MERCHANT_DEDUPE_WAIT = 100
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class FarmError(SystemExit):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise FarmError("%s: schema must be %s" % (path, SCHEMA))
    cols = [gr["colour"] for gr in doc["groves"]]
    if len(cols) != len(set(cols)) or not set(cols) <= set(COLOURS):
        raise FarmError("groves: each colour at most once, from %s" % (COLOURS,))
    for c in COLOURS:
        layers = doc["tree_designs"].get(c)
        if not layers or any(len(l) != 7 or any(len(r) != 7 for r in l) for l in layers):
            raise FarmError("tree_designs.%s: layers of seven rows of seven" % c)
    for s in doc["sheds"]:
        if any(c not in COLOURS for c in s["colours"]):
            raise FarmError("%s: an unknown colour" % s["id"])
    for it in doc["merchant"]["stock"]:
        if not isinstance(it["price"], int) or it["price"] <= 0:
            raise FarmError("merchant %s: a price is a positive whole number" % it["item"])
    return doc


def base(state):
    return state.split("[")[0].split("{")[0]


def fruit(colour, facing, age):
    return "cobblemon:%s_apricorn[age=%d,facing=%s]" % (colour, age, facing)


def hash01(x, z, salt=0):
    h = (x * 73856093) ^ (z * 19349663) ^ (salt * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0x1000000)


def fruit_age(x, y, z):
    """Five in eight ripe (age 3), the rest 0, 1 or 2: fixed per cell."""
    r = hash01(x * 31 + y, z, 7)
    return 3 if r < 0.625 else int((r - 0.625) / 0.125)


def sign(wood, lines, rotation=None, wall=None):
    import southern_residents as SR
    spec = {"wood": wood, "lines": lines}
    if wall:
        spec["wall"] = wall
    else:
        spec["rotation"] = rotation
    return SR.sign({"sign": spec})


def fence_state(block, conn):
    return "%s[east=%s,north=%s,south=%s,west=%s,waterlogged=false]" % (
        block, *("true" if d in conn else "false" for d in ("east", "north", "south", "west")))


# ------------------------------------------------------------------------------------------------------------ the plan
class Plan:
    """Blocks in two passes, {(x, y, z): state}: the structure bottom up, then what hangs on it (fruit, signs, lanterns,
    doors) top down. `owner` names the piece that wrote each cell; `reserved` the columns a piece claims at ground
    level (a footprint, a terrace, a post), so a path or a later piece cannot land on it unseen."""

    def __init__(self, doc, g, wet):
        self.doc, self.g, self.wet = doc, g, wet
        self.cx, self.cz = doc["site"]["centre"]
        self.solid, self.hung, self.doors, self.clears = {}, {}, [], []
        self.owner = {}
        self.reserved = {}
        self.allowed = set(doc["blocks"]["ids"])
        self.facts = {"groves": {}, "buildings": {}, "fruit": {c: 0 for c in COLOURS}, "path_skipped": 0}

    def W(self, lx, lz):
        return self.cx + lx, self.cz + lz

    def gl(self, lx, lz):
        return self.g(self.cx + lx, self.cz + lz)

    def _check(self, x, z, state, who):
        if base(state) not in self.allowed:
            raise FarmError("%s: %s is not in data/apricorn_farm.json blocks.ids" % (who, base(state)))
        if self.wet(x, z):
            raise FarmError("%s: (%d, %d) is wet" % (who, x, z))

    def put(self, x, y, z, state, who, over=False):
        self._check(x, z, state, who)
        k = (x, y, z)
        if not over and k in self.owner and self.owner[k] != who:
            raise FarmError("%s writes %s, which %s already wrote" % (who, k, self.owner[k]))
        self.hung.pop(k, None)
        self.solid[k] = state
        self.owner[k] = who

    def hang(self, x, y, z, state, who):
        self._check(x, z, state, who)
        k = (x, y, z)
        if k in self.owner and self.owner[k] != who:
            raise FarmError("%s hangs at %s, which %s already wrote" % (who, k, self.owner[k]))
        self.solid.pop(k, None)
        self.hung[k] = state
        self.owner[k] = who

    def door(self, x, y, z, block, facing, who, hinge="left"):
        for half, d in (("lower", 0), ("upper", 1)):
            st = "%s[facing=%s,half=%s,hinge=%s,open=false,powered=false]" % (block, facing, half, hinge)
            self._check(x, z, st, who)
            self.solid.pop((x, y + d, z), None)
            self.hung.pop((x, y + d, z), None)
            self.owner[(x, y + d, z)] = who
            self.doors.append(((x, y + d, z), st))

    def reserve(self, x, z, who):
        if (x, z) in self.reserved and self.reserved[(x, z)] != who:
            raise FarmError("%s claims (%d, %d), which %s holds" % (who, x, z, self.reserved[(x, z)]))
        self.reserved[(x, z)] = who

    def clear(self, x0, z0, x1, z1, y0, y1):
        if y1 >= y0:
            self.clears.append((min(x0, x1), y0, min(z0, z1), max(x0, x1), y1, max(z0, z1)))

    def blocks(self):
        out = dict(self.solid)
        out.update(self.hung)
        out.update(dict(self.doors))
        return out


# ------------------------------------------------------------------------------------------------------------ trees
def tree(p, x, y0, z, colour, who):
    """One apricorn tree of its colour's design, its first layer at y0 (the floor + 1), centred on (x, z). Returns the
    number of fruit."""
    layers = p.doc["tree_designs"][colour]
    n = 0
    for i, rows in enumerate(layers):
        y = y0 + i
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                bx, bz = x + c - 3, z + r - 3
                if ch == "L":
                    p.put(bx, y, bz, LOG_Y, who)
                elif ch == "X":
                    p.put(bx, y, bz, LOG_X, who)
                elif ch == "#":
                    p.put(bx, y, bz, LEAVES, who)
    for i, rows in enumerate(layers):
        y = y0 + i
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch != "A":
                    continue
                bx, bz = x + c - 3, z + r - 3
                face = None
                for d, dx, dz in DIRS:
                    rr, cc = r + dz, c + dx
                    if 0 <= rr < 7 and 0 <= cc < 7 and rows[rr][cc] == "#":
                        face = d
                        break
                if face is None:
                    raise FarmError("tree_designs.%s layer %d: the fruit at row %d col %d has no leaf beside it"
                                    % (colour, i + 1, r, c))
                p.hang(bx, y, bz, fruit(colour, face, fruit_age(bx, y, bz)), who)
                n += 1
    return n


def tree_cells(doc, colour):
    """{(dx, dz)} every column a design writes, relative to its trunk."""
    return {(c - 3, r - 3) for rows in doc["tree_designs"][colour] for r, row in enumerate(rows)
            for c, ch in enumerate(row) if ch != "."}


# ------------------------------------------------------------------------------------------------------------ groves
def post(p, x, z, y, who, height=2):
    """A lantern post: spruce fence `height` high from y, a lantern on top."""
    for d in range(height):
        p.put(x, y + d, z, fence_state("minecraft:spruce_fence", ()), who)
    p.hang(x, y + height, z, LANTERN, who)
    p.clear(x, z, x, z, y, y + height)


def grove(p, gr):
    L = p.doc["grove_layout"]
    hx, hz = L["half_x"], L["half_z"]
    gcx, gcz = gr["centre"]
    colour = gr["colour"]
    who = "grove_" + colour
    x0, z0 = p.W(gcx - hx, gcz - hz)
    x1, z1 = p.W(gcx + hx, gcz + hz)
    G = {(x, z): p.g(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    lo, hi = min(G.values()), max(G.values())
    med = statistics.median(G.values())
    # the gate: on the side facing the lane, at an alley end (or between tree columns on a north/south side)
    side = gr["gate_side"]
    if side in ("east", "west"):
        gx = x1 if side == "east" else x0
        ox = gx + (1 if side == "east" else -1)
        spots = [((gx, p.cz + gcz + az), (ox, p.cz + gcz + az), 0) for pair in L["alleys_z"] for az in pair]
    else:
        gz = z0 if side == "north" else z1
        oz = gz + (-1 if side == "north" else 1)
        xs = {0} | {round((a + b) / 2) for a, b in zip(L["tree_x"], L["tree_x"][1:])}
        spots = [((p.cx + gcx + ax, gz), (p.cx + gcx + ax, oz), abs(ax)) for ax in xs]
    # the floor: of the levels that leave some gate within one block of its outside ground (walkable both ways), the
    # one with the least earthwork, then the one nearest the median
    best = None
    for F in range(lo, hi + 1):
        ok = [(abs(p.g(*o) - F), pref, gt, o) for gt, o, pref in spots if abs(p.g(*o) - F) <= 1]
        if not ok:
            continue
        key = (sum(abs(gy - F) for gy in G.values()), abs(F - med))
        if best is None or key < best[0]:
            best = (key, F, min(ok))
    if best is None:
        raise FarmError("%s: no floor in y%d-%d leaves a gate within one block of its outside ground" % (who, lo, hi))
    _k, F, (diff, _pref, gate, outside) = best
    facing = side
    p.clear(x0, z0, x1, z1, lo + 1, max(hi, F) + 16)
    for (x, z) in G:
        p.reserve(x, z, who)
    edge = lambda x, z: x in (x0, x1) or z in (z0, z1)
    tops = {}
    for (x, z), gy in G.items():
        if edge(x, z):
            if (x, z) == gate:
                for y in range(F + 1, gy + 1):
                    p.put(x, y, z, "minecraft:air", who)
                p.put(x, F, z, L["wall"], who)
                tops[(x, z)] = F
                continue
            mossy = hash01(x, z, 3) < 0.3
            wb = L["wall_mossy"] if mossy else L["wall"]
            # lower outside: a retaining wall from the ground up to the floor; higher outside: a revetment from the
            # floor up to the ground (the column's own exposed face); level: one course in place of the top block
            ys = range(gy + 1, F + 1) if gy < F else range(F, gy + 1)
            for y in ys:
                p.put(x, y, z, wb, who)
            tops[(x, z)] = max(gy, F)
        else:
            for y in range(gy + 1, F):
                p.put(x, y, z, L["fill"], who)
            for y in range(F + 1, gy + 1):
                p.put(x, y, z, "minecraft:air", who)
            p.put(x, F, z, L["floor"], who)
    # the alleys and the mulch rings
    for pair in L["alleys_z"]:
        for az in pair:
            for ax in range(-hx + 1, hx):
                x, z = p.W(gcx + ax, gcz + az)
                p.put(x, F, z, "minecraft:dirt_path", who, over=True)
    trees, fruit_n = [], 0
    for tz in L["tree_z"]:
        for tx in L["tree_x"]:
            x, z = p.W(gcx + tx, gcz + tz)
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    p.put(x + dx, F, z + dz, L["mulch"], who, over=True)
            trees.append((x, z))
    # nothing of a tree may stand on an alley, the inner ring or another tree's column
    alley = {p.cz + gcz + az for pair in L["alleys_z"] for az in pair}
    cells = tree_cells(p.doc, colour)
    for x, z in trees:
        for dx, dz in cells:
            cx, cz = x + dx, z + dz
            if cz in alley or not (x0 < cx < x1 and z0 < cz < z1):
                raise FarmError("%s: the tree at (%d, %d) reaches (%d, %d), an alley or the fence" % (who, x, z, cx, cz))
        fruit_n += tree(p, x, F + 1, z, colour, who)
    p.facts["fruit"][colour] += fruit_n
    # the fence round the top of the wall, connected along each side, with the gate
    ring = [c for c in G if edge(*c)]
    ringset = set(ring)
    for (x, z) in ring:
        y = tops[(x, z)] + 1
        if (x, z) == gate:
            p.put(x, y, z, "%s[facing=%s,in_wall=false,open=false,powered=false]" % (L["gate"], facing), who)
            continue
        conn = []
        for d, dx, dz in DIRS:
            n = (x + dx, z + dz)
            if n in ringset and tops[n] + 1 == y:
                conn.append(d)
        p.put(x, y, z, fence_state(L["fence"], conn), who)
    # alley posts, the trough and the harvest bench
    for ax, az in L["posts"]:
        x, z = p.W(gcx + ax, gcz + az)
        post(p, x, z, F + 1, who)
    for ax, az in L["trough"]:
        x, z = p.W(gcx + ax, gcz + az)
        p.put(x, F + 1, z, "minecraft:water_cauldron[level=3]", who)
    for ax, az, st in L["harvest_bench"]:
        x, z = p.W(gcx + ax, gcz + az)
        p.put(x, F + 1, z, st, who)
    # the inside of the gate is open ground
    ix = gate[0] + (outside[0] - gate[0]) * -1
    iz = gate[1] + (outside[1] - gate[1]) * -1
    for y in (F + 1, F + 2):
        if (ix, y, iz) in p.owner and base(p.blocks()[(ix, y, iz)]) != "minecraft:air":
            raise FarmError("%s: the cell inside the gate %s is taken" % (who, (ix, y, iz)))
    # the sign post outside, beside the gate, and the spur from the gate to the lane
    if side in ("east", "west"):
        sx, sz = outside[0], outside[1] - 2
        rot = 12 if side == "east" else 4
    else:
        sx, sz = outside[0] + 2, outside[1]
        rot = 8 if side == "north" else 0
    sy = p.g(sx, sz) + 1
    p.reserve(sx, sz, who + "_sign")
    p.put(sx, sy, sz, "minecraft:stripped_spruce_log[axis=y]", who)
    p.hang(sx, sy + 1, sz, sign("spruce", gr["sign"], rotation=rot), who)
    p.clear(sx, sz, sx, sz, sy, sy + 1)
    p.facts["groves"][colour] = {"floor": F, "ground": [lo, hi], "box": [x0, z0, x1, z1], "gate": list(gate),
                                 "gate_outside_diff": diff, "trees": len(trees), "fruit": fruit_n,
                                 "cut": sum(max(0, gy - F) for gy in G.values()),
                                 "fill": sum(max(0, F - gy) for gy in G.values())}
    return outside


# ------------------------------------------------------------------------------------------------------------ buildings
def footprint(p, fp):
    x0, z0 = p.W(fp[0], fp[1])
    x1, z1 = p.W(fp[2], fp[3])
    return x0, z0, x1, z1


def level_floor(p, fp, who, floor_block, foundation):
    """Floor y F = max(ground under the footprint) + 1, a foundation under every lower column, the floor block at F."""
    x0, z0, x1, z1 = footprint(p, fp)
    cols = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    F = max(p.g(x, z) for x, z in cols) + 1
    for x, z in cols:
        p.reserve(x, z, who)
        for y in range(p.g(x, z) + 1, F):
            p.put(x, y, z, foundation, who)
        p.put(x, F, z, floor_block, who)
    return F, (x0, z0, x1, z1)


def step_out(p, x, z, F, facing_in, who):
    """A stair step at the floor's level outside a doorway, its high side toward the door, on a foundation."""
    gy = p.g(x, z)
    if gy >= F:
        return
    for y in range(gy + 1, F):
        p.put(x, y, z, "minecraft:cobblestone", who)
    p.put(x, F, z, "minecraft:cobblestone_stairs[facing=%s,half=bottom,shape=straight,waterlogged=false]" % facing_in, who)
    p.reserve(x, z, who)


def roof(p, box, Wt, ridge, mat, gable, who):
    x0, z0, x1, z1 = box
    k = 0
    if ridge == "x":
        while True:
            a, b = z0 - 1 + k, z1 + 1 - k
            y = Wt + 1 + k
            if a > b:
                break
            for x in range(x0 - 1, x1 + 2):
                if a == b:
                    p.put(x, y, a, "%s_slab[type=bottom,waterlogged=false]" % mat, who)
                else:
                    p.put(x, y, a, "%s_stairs[facing=south,half=bottom,shape=straight,waterlogged=false]" % mat, who)
                    p.put(x, y, b, "%s_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]" % mat, who)
            for z in range(a + 1, b):
                for x in (x0, x1):
                    p.put(x, y, z, gable, who)
            k += 1
    else:
        while True:
            a, b = x0 - 1 + k, x1 + 1 - k
            y = Wt + 1 + k
            if a > b:
                break
            for z in range(z0 - 1, z1 + 2):
                if a == b:
                    p.put(a, y, z, "%s_slab[type=bottom,waterlogged=false]" % mat, who)
                else:
                    p.put(a, y, z, "%s_stairs[facing=east,half=bottom,shape=straight,waterlogged=false]" % mat, who)
                    p.put(b, y, z, "%s_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]" % mat, who)
            for x in range(a + 1, b):
                for z in (z0, z1):
                    p.put(x, y, z, gable, who)
            k += 1
    return Wt + k


def building(p, b):
    who = b["id"]
    F, box = level_floor(p, b["footprint"], who, b["floor"], b["foundation"])
    x0, z0, x1, z1 = box
    H = b["wall_height"]
    Wt = F + H
    p.clear(x0 - 2, z0 - 2, x1 + 2, z1 + 2, F + 1, Wt + max(x1 - x0, z1 - z0) // 2 + 6)
    d = b["door"]
    width = d.get("width", 1)
    dh = d.get("height", 2)
    side = d["side"]
    if side in ("east", "west"):
        dxw = x1 if side == "east" else x0
        dz = p.cz + d["at"]
        door_cells = {(dxw, dz + i - width // 2) for i in range(width)}
    else:
        dzw = z1 if side == "south" else z0
        dx = p.cx + d["at"]
        door_cells = {(dx + i - width // 2, dzw) for i in range(width)}
    w = b.get("windows") or {}
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if not (x in (x0, x1) or z in (z0, z1)):
                continue
            corner = x in (x0, x1) and z in (z0, z1)
            along_x = z in (z0, z1)
            off = (x - x0) if along_x else (z - z0)
            for dy in range(1, H + 1):
                y = F + dy
                if (x, z) in door_cells and dy <= dh:
                    if width == 1:
                        continue
                    p.put(x, y, z, "minecraft:air", who)
                    continue
                if corner:
                    st = b["corner"]
                elif dy == 1 and b.get("plinth"):
                    st = b["plinth"]
                elif (w and dy == w["dy"] and off % w["every"] == 1 and not corner
                      and all(abs(off - ((c[0] - x0) if along_x else (c[1] - z0))) > 1 for c in door_cells
                              if (c[1] == z if along_x else c[0] == x))):
                    st = ("minecraft:glass_pane[east=true,north=false,south=false,waterlogged=false,west=true]" if along_x
                          else "minecraft:glass_pane[east=false,north=true,south=true,waterlogged=false,west=false]")
                else:
                    st = b["wall"]
                p.put(x, y, z, st, who)
    top = roof(p, box, Wt, b["ridge"], b["roof"], b["gable"], who)
    facing_in = {"east": "west", "west": "east", "north": "south", "south": "north"}[side]
    out_d = {"east": (1, 0), "west": (-1, 0), "north": (0, -1), "south": (0, 1)}[side]
    for (x, z) in sorted(door_cells):
        if width == 1:
            p.door(x, F + 1, z, b["door_block"], facing_in, who)
        step_out(p, x + out_d[0], z + out_d[1], F, facing_in, who)
        p.clear(x + out_d[0], z + out_d[1], x + out_d[0], z + out_d[1], F + 1, F + dh)
    for lx, dy, lz, st in b.get("furnish") or []:
        p.put(x0 + lx, F + dy, z0 + lz, st, who)
    for lx, dy, lz, facing, lines in b.get("wall_signs") or []:
        p.hang(x0 + lx, F + dy, z0 + lz, sign("spruce", lines, wall=facing), who)
    ch = b.get("chimney")
    if ch:
        cx, cz = x0 + ch["at"][0], z0 + ch["at"][1]
        p.reserve(cx, cz, who)
        cy = p.g(cx, cz)
        for y in range(cy + 1, top + ch["top"] + 1):
            p.put(cx, y, cz, "minecraft:cobblestone", who, over=True)
        p.put(cx, top + ch["top"] + 1, cz, "minecraft:campfire[facing=north,lit=true,signal_fire=false,waterlogged=false]", who)
    p.facts["buildings"][who] = {"floor": F, "walls_top": Wt, "roof_top": top, "box": list(box)}
    return F


def shed(p, s):
    who = s["id"]
    F, box = level_floor(p, s["footprint"], who, "minecraft:coarse_dirt", "minecraft:cobblestone")
    x0, z0, x1, z1 = box
    p.clear(x0 - 2, z0 - 2, x1 + 2, z1 + 2, F + 1, F + 6)
    xs = sorted({x0, x0 + (x1 - x0) // 2, x1})
    for x in xs:
        for z in (z0, z1):
            for dy in (1, 2, 3):
                p.put(x, F + dy, z, fence_state("minecraft:spruce_fence", ()), who)
    for x in range(x0 - 1, x1 + 2):
        for z in range(z0 - 1, z1 + 2):
            p.put(x, F + 4, z, "minecraft:spruce_slab[type=bottom,waterlogged=false]", who)
    zc = (z0 + z1) // 2
    bunches = list(range(x0 + 1, x1, 2))
    if len(bunches) != len(s["colours"]):
        raise FarmError("%s: %d bunches under the roof, %d colours" % (who, len(bunches), len(s["colours"])))
    for x, colour in zip(bunches, s["colours"]):
        p.put(x, F + 3, zc, LEAVES, who)
        for fz, face in ((zc - 1, "south"), (zc + 1, "north")):
            p.hang(x, F + 3, fz, fruit(colour, face, fruit_age(x, F + 3, fz)), who)
            p.facts["fruit"][colour] += 1
    for x in range(x0 + 1, x0 + 4):
        p.put(x, F + 1, z1, "minecraft:barrel[facing=up,open=false]", who)
    p.put(x1 - 1, F + 1, z1, "minecraft:hay_block[axis=y]", who)
    p.put(x1 - 2, F + 1, z1, "minecraft:composter[level=0]", who)
    p.hang(xs[1] + 1, F + 3, zc, "minecraft:lantern[hanging=true,waterlogged=false]", who)
    p.facts["buildings"][who] = {"floor": F, "box": list(box)}


def stall(p):
    st = p.doc["stall"]
    who = "stall"
    F, box = level_floor(p, st["footprint"], who, "minecraft:spruce_planks", "minecraft:cobblestone")
    x0, z0, x1, z1 = box
    p.clear(x0 - 1, z0 - 1, x1 + 1, z1 + 1, F + 1, F + 5)
    for x in (x0, x1):
        for z in (z0, z1):
            for dy in (1, 2, 3):
                p.put(x, F + dy, z, fence_state("minecraft:spruce_fence", ()), who)
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            p.put(x, F + 4, z, "cobblemon:apricorn_slab[type=bottom,waterlogged=false]", who)
    zc = (z0 + z1) // 2
    # the counter on the avenue side (east), the display branch behind the keeper
    p.put(x1, F + 1, zc - 1, "minecraft:barrel[facing=up,open=false]", who)
    p.put(x1, F + 1, zc, "cobblemon:apricorn_planks", who)
    p.put(x1, F + 1, zc + 1, "minecraft:barrel[facing=up,open=false]", who)
    p.put(x0 + 1, F + 1, zc, LOG_Y, who)
    p.put(x0 + 1, F + 2, zc, LEAVES, who)
    for fz, face, colour in ((zc - 1, "south", "red"), (zc + 1, "north", "yellow")):
        p.hang(x0 + 1, F + 2, fz, fruit(colour, face, 3), who)
        p.facts["fruit"][colour] += 1
    p.hang(x0 + 1, F + 3, zc, "minecraft:lantern[hanging=false,waterlogged=false]", who)
    p.facts["buildings"][who] = {"floor": F, "box": list(box)}
    return F


def water_tower(p):
    t = p.doc["water_tower"]
    who = "water_tower"
    x0, z0, x1, z1 = footprint(p, t["footprint"])
    cols = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    B = max(p.g(x, z) for x, z in cols)
    legs = int(t["legs"])
    p.clear(x0 - 1, z0 - 1, x1 + 1, z1 + 1, min(p.g(x, z) for x, z in cols) + 1, B + legs + 5)
    for x, z in cols:
        p.reserve(x, z, who)
    for x in (x0, x1):
        for z in (z0, z1):
            for y in range(p.g(x, z) + 1, B + 1):
                p.put(x, y, z, "minecraft:cobblestone", who)
            for y in range(B + 1, B + legs + 1):
                p.put(x, y, z, "minecraft:spruce_log[axis=y]", who)
    deck = B + legs + 1
    for x, z in cols:
        p.put(x, deck, z, "minecraft:spruce_planks", who)
        if x in (x0, x1) or z in (z0, z1):
            for dy in (1, 2):
                p.put(x, deck + dy, z, "minecraft:spruce_planks", who)
        else:
            p.put(x, deck + 1, z, "minecraft:water_cauldron[level=3]", who)
    p.hang(x0, deck + 3, z0, LANTERN, who)
    p.hang(x1, deck + 3, z1, LANTERN, who)
    p.facts["buildings"][who] = {"base": B, "deck": deck, "box": [x0, z0, x1, z1]}


def ground_objects(p, name, at, blocks):
    ax, az = at
    for dx, dy, dz, st in blocks:
        x, z = p.W(ax + dx, az + dz)
        gy = p.g(x, z)
        p.reserve(x, z, name)
        p.put(x, gy + dy, z, st, name)
        p.clear(x, z, x, z, gy + 1, gy + max(dy, 1) + 1)


def arch(p):
    a = p.doc["arch"]
    who = "arch"
    z = p.cz + a["at_z"]
    xa, xb = p.cx - a["half_span"], p.cx + a["half_span"]
    T = max(p.g(xa, z), p.g(xb, z)) + a["height"]
    for x in (xa, xb):
        p.reserve(x, z, who)
        for y in range(p.g(x, z) + 1, T + 1):
            p.put(x, y, z, "minecraft:stripped_spruce_log[axis=y]", who)
    for x in range(xa, xb + 1):
        p.put(x, T + 1, z, "minecraft:spruce_log[axis=x]", who)
    p.clear(xa, z - 1, xb, z + 1, min(p.g(xa, z), p.g(xb, z)) + 1, T + 3)
    p.hang(p.cx, T + 1, z - 1, sign("spruce", a["sign"], wall="north"), who)
    for x in (xa + 1, xb - 1):
        p.hang(x, T, z, "minecraft:lantern[hanging=true,waterlogged=false]", who)
    p.facts["buildings"][who] = {"beam": T + 1}


def standing_sign(p, spec, who):
    x, z = p.W(*spec["at"])
    y = p.g(x, z) + 1
    p.reserve(x, z, who)
    p.put(x, y, z, "minecraft:stripped_spruce_log[axis=y]", who)
    p.hang(x, y + 1, z, sign("spruce", spec["lines"], rotation=spec["rotation"]), who)
    p.clear(x, z, x, z, y, y + 1)


def paths(p, spurs):
    """Every path: the top block of its own column swapped (the height never changes), plants cleared off it. A path
    never lands on a column another piece holds: those cells are skipped and counted."""
    import southern_residents as SR
    P = p.doc["paths"]
    cols = []
    for seg in P["segments"]:
        pts = seg["points"]
        for a, b in zip(pts, pts[1:]):
            cols += [(p.cx + dx, p.cz + dz) for dx, dz in SR._segment_cols(a, b, P["half_width"])]
    for (ox, oz), (lx, lz) in spurs:
        cols += [(x, z) for x, z in SR._segment_cols((ox, oz), (lx, lz), 0)]
    done = set()
    for x, z in cols:
        if (x, z) in done:
            continue
        done.add((x, z))
        if (x, z) in p.reserved:
            p.facts["path_skipped"] += 1
            continue
        gy = p.g(x, z)
        p.put(x, gy, z, P["block"], "path", over=True)
        p.clear(x, z, x, z, gy + 1, gy + 2)
    p.path_cols = done - set(p.reserved)


def spot(p, lx, lz, who):
    """(x, y, z) feet on the column's ground, or on a levelled floor where a piece wrote one."""
    x, z = p.W(lx, lz)
    blocks = p.blocks()
    y = p.g(x, z) + 1
    while base(blocks.get((x, y, z), "minecraft:air")) != "minecraft:air":
        y += 1
    for k in ((x, y, z), (x, y + 1, z)):
        if base(blocks.get(k, "minecraft:air")) != "minecraft:air":
            raise FarmError("%s's spot %s is not two blocks of air" % (who, (x, y, z)))
    if y - 1 != p.g(x, z) and (x, y - 1, z) not in blocks:
        raise FarmError("%s's spot %s has nothing under it" % (who, (x, y, z)))
    return x, y, z


def plan(doc, g, wet=None):
    if wet is None:
        import resident_encounters as RE
        wet = RE.Wet(g, [tuple(doc["site"]["centre"])])
    p = Plan(doc, g, wet)
    spurs = []
    for gr in doc["groves"]:
        outside = grove(p, gr)
        side = gr["gate_side"]
        if side in ("east", "west"):
            lane_x = p.cx + (23 if outside[0] > p.cx else -23)
            spurs.append((outside, (lane_x, outside[1])))
        else:
            spurs.append((outside, (p.cx, outside[1] - 1)))
    for b in doc["buildings"]:
        building(p, b)
    for s in doc["sheds"]:
        shed(p, s)
    stall(p)
    water_tower(p)
    for o in doc["yard_objects"]:
        ground_objects(p, o["name"], o["at"], o["blocks"])
    arch(p)
    standing_sign(p, doc["track_sign"], "track_sign")
    standing_sign(p, doc["harvest_sign"], "harvest_sign")
    for lx, lz in doc["lantern_posts"]["at"]:
        x, z = p.W(lx, lz)
        p.reserve(x, z, "lantern_post")
        post(p, x, z, p.g(x, z) + 1, "lantern_post_%d_%d" % (lx, lz), int(doc["lantern_posts"]["height"]))
    paths(p, spurs)
    for (ox, oz), _l in spurs:
        if (ox, oz) not in p.path_cols:
            raise FarmError("the gate spur at (%d, %d) is not a path" % (ox, oz))
    for lx, lz in doc["lantern_posts"]["at"]:
        if p.W(lx, lz) in p.path_cols:
            raise FarmError("the lantern post at local (%d, %d) is on a path" % (lx, lz))
    n = doc["npc"]
    npc = spot(p, n["at"][0], n["at"][1], "the farmer")
    m = doc["merchant"]
    merchant = spot(p, m["at"][0], m["at"][1], "the stall keeper")
    for who, xyz in (("the farmer", npc), ("the stall keeper", merchant)):
        if (xyz[0], xyz[2]) in p.path_cols:
            raise FarmError("%s stands on a path at %s" % (who, xyz))
    return p, npc, merchant


# ------------------------------------------------------------------------------------------------------------ the checks
def check(doc, p):
    """Problems, as strings: the spawn-block policy and the siting rules. The writes' own guards (allow-list, wet
    columns, overlaps, fruit attachment, gates, spots) already raised in plan()."""
    import numpy as np
    import southern_residents as SR
    probs = []
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    allowed = set(doc["blocks"]["spawn_conditions_allowed"])
    written = {base(s) for s in p.blocks().values()}
    bad = sorted((written & spawn) - allowed)
    if bad:
        probs.append("writes spawn-condition blocks %s (data/spawn_blocks.json)" % bad)
    policy = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    # the scope rule (tests/test_system_contracts.py C4): an entry whose scope names this place
    white = {b for w in policy["whitelist"] if "apricorn_farm" in (w.get("scope") or "") for b in w.get("blocks") or []}
    if (written & allowed) - white:
        probs.append("%s: no data/spawn_block_policy.json entry scoped to apricorn_farm whitelists them"
                     % sorted((written & allowed) - white))
    for bad_id in ("minecraft:chest", "minecraft:water") + tuple("minecraft:%s_bed" % c for c in ("white", "red")):
        if bad_id in written:
            probs.append("writes %s" % bad_id)
    cols = {(k[0], k[2]) for k in p.blocks()}
    for c in p.clears:
        cols |= {(c[0], c[2]), (c[3], c[5])}
    C = np.array(sorted(cols), float)
    x0, z0 = C.min(axis=0)
    x1, z1 = C.max(axis=0)
    rules = doc["rules"]
    # a box another file centres on this farm's own site is that file's keep-out of this farm, not a place here
    # (2026-10-05: data/pokemon_farm.json rules.keep_out holds such a box, and its centre is (2068, 5570) itself)
    cx, cz = doc["site"]["centre"]
    pts = [(a, b, f) for a, b, f in SR.authored_points({"residents": []}, own_file=DATA)
           if f != "regions.json" and math.hypot(a - cx, b - cz) > 1]
    near = [(a, b, f) for a, b, f in pts if x0 - 400 <= a <= x1 + 400 and z0 - 400 <= b <= z1 + 400]
    best = (1e9, None)
    for a, b, f in near:
        d = float(np.min(np.hypot(C[:, 0] - a, C[:, 1] - b)))
        if d < best[0]:
            best = (d, (a, b, f))
    p.facts["nearest_authored"] = best
    if best[0] < rules["authored_clearance"]:
        probs.append("(%s, %s) in data/%s is %.0f from a written column (needs %d)"
                     % (best[1][0], best[1][1], best[1][2], best[0], rules["authored_clearance"]))
    cp, cb = SR.corridor_check("apricorn_farm", cols, rules["route_clearance"])
    probs += cp
    p.facts["nearest_corridor"] = cb[0]
    paths_ = [q for pl in json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"].values()
              for q in pl]
    P = np.array([q[:2] for q in paths_], float)
    P = P[(P[:, 0] > x0 - 1000) & (P[:, 0] < x1 + 1000) & (P[:, 1] > z0 - 1000) & (P[:, 1] < z1 + 1000)]
    dp = 1e9
    for i in range(0, len(P), 512):
        blk = P[i:i + 512]
        d = np.hypot(C[:, None, 0] - blk[None, :, 0], C[:, None, 1] - blk[None, :, 1])
        dp = min(dp, float(d.min()))
    p.facts["nearest_route_path"] = dp
    if dp < rules["route_clearance"]:
        probs.append("a written column is %.0f from a route path (needs %d)" % (dp, rules["route_clearance"]))
    for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        dx = np.maximum(np.maximum(f["min_x"] - C[:, 0], C[:, 0] - f["max_x"]), 0)
        dz = np.maximum(np.maximum(f["min_z"] - C[:, 1], C[:, 1] - f["max_z"]), 0)
        d = float(np.min(np.hypot(dx, dz)))
        if d < rules["town_clearance"]:
            probs.append("within %.0f of town %s (needs %d)" % (d, t["id"], rules["town_clearance"]))
    for k, zone in json.loads((ROOT / "data" / "rift_zones.json").read_text(encoding="utf-8"))["zones"].items():
        for bx in zone.get("boxes") or []:
            if np.any((C[:, 0] >= bx[0]) & (C[:, 0] <= bx[2]) & (C[:, 1] >= bx[1]) & (C[:, 1] <= bx[3])):
                probs.append("inside Rift zone %s" % k)
                break
    return probs


# ------------------------------------------------------------------------------------------------------------ the pack
def _runs(blocks, top_down=False):
    """setblock and fill lines for {(x, y, z): state}, one fill per run of one state along x."""
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


def hold_box(p):
    ks = list(p.blocks())
    xs = [k[0] for k in ks] + [c[0] for c in p.clears] + [c[3] for c in p.clears]
    zs = [k[2] for k in ks] + [c[2] for c in p.clears] + [c[5] for c in p.clears]
    return min(xs), min(zs), max(xs), max(zs)


def part_of(who):
    if who.startswith("grove_"):
        return who
    if who == "path" or who.startswith("lantern_post") or who in ("track_sign", "harvest_sign"):
        return "lanes"
    return "yard"


PARTS = ["grove_" + c for c in COLOURS] + ["yard", "lanes"]


def build_parts(doc, p):
    """{part: lines}: a clear function first, then each part's structure (bottom up), what hangs (top down) and its
    doors. Every part is marked as held by its caller (the build function, or R9AF's forceload)."""
    ns, fo = doc["namespace"], doc["folder"]
    mark = "# chunks-loaded-by: %s:%s/build (and tools/reapply.py R9AF's forceload of the farm's box)" % (ns, fo)
    out = {}
    clear = ["# Generated by tools/apricorn_farm.py from data/apricorn_farm.json. Re-run to rebuild; do not edit.",
             "# 1. the fruit a previous build hung, FIRST: a fill that takes away a leaf updates the fruit hanging on it,",
             "#    which can no longer survive and breaks with its drop (ApricornBlock.canSurvive), so a rebuild would",
             "#    scatter every ripe apricorn on the ground. A fill replacing the fruit itself drops nothing.",
             "# 2. then logs, leaves and plants off every piece's box, before anything is written", mark]
    for (x0, y0, z0, x1, y1, z1) in p.clears:
        clear.append("fill %d %d %d %d %d %d minecraft:air replace #cobblemon:apricorns" % (x0, y0, z0, x1, y1, z1))
    for (x0, y0, z0, x1, y1, z1) in p.clears:
        for tag in CLEAR_TAGS:
            clear.append("fill %d %d %d %d %d %d minecraft:air replace %s" % (x0, y0, z0, x1, y1, z1, tag))
    out["clear"] = function_limits.split_fills(clear)
    doors = dict(p.doors)
    for part in PARTS:
        solid = {k: v for k, v in p.solid.items() if part_of(p.owner[k]) == part and k not in doors}
        hung = {k: v for k, v in p.hung.items() if part_of(p.owner[k]) == part}
        dd = [(k, v) for k, v in p.doors if part_of(p.owner[k]) == part]
        if not (solid or hung or dd):
            continue
        lines = ["# Generated by tools/apricorn_farm.py from data/apricorn_farm.json: %s. Do not edit." % part, mark,
                 "# the structure, bottom up"]
        lines += _runs(solid)
        lines.append("# what hangs on it: fruit (after its leaf), signs, lanterns, from the top")
        lines += _runs(hung, top_down=True)
        if dd:
            lines.append("# the doors, lower half then upper")
            lines += ["setblock %d %d %d %s" % (k + (st,)) for k, st in dd]
        out[part] = function_limits.split_fills(lines)
    return out


def merchant_data(doc):
    m = doc["merchant"]
    mk = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))["stall_merchant"]
    return {"CustomName": json.dumps({"text": m["name"]}, ensure_ascii=False),
            "VillagerData": dict(mk["villager_data"]),
            "CobbleMerchantShop": [{"Category": m["category"],
                                    "Offers": [{"Item": {"count": 1, "id": it["item"]}, "Price": str(it["price"])}
                                               for it in m["stock"]]}],
            "NoAI": True, "PersistenceRequired": True, "Invulnerable": True, "Silent": True,
            "Rotation": [float(m["yaw"]), 0.0],
            "Tags": [m["tag"], m["tag"] + "_new"]}


def merchant_functions(doc, merchant):
    import traders as TR
    ns, fo = doc["namespace"], doc["folder"]
    m = doc["merchant"]
    x, y, z = merchant
    tag, new = m["tag"], m["tag"] + "_new"
    place = ["# Generated by tools/apricorn_farm.py: the stall merchant (R18AF). The step holds the stall's chunk.",
             "# chunks-loaded-by: tools/reapply.py R18AF",
             TR.summon_line(MERCHANT_KIND, x, y, z, merchant_data(doc)),
             "schedule function %s:%s/merchant_done %dt replace" % (ns, fo, MERCHANT_DEDUPE_WAIT)]
    done = ["# Generated by tools/apricorn_farm.py; %d ticks after the summon: one merchant, the older copies killed"
            % MERCHANT_DEDUPE_WAIT,
            "execute if entity @e[tag=%s,tag=%s] run kill @e[tag=%s,tag=!%s]" % (tag, new, tag, new),
            "tag @e[tag=%s,tag=%s] remove %s" % (tag, new, new)]
    return {"merchant": place, "merchant_done": done}


def files(doc, g, wet=None, check_rules=True):
    p, npc, merchant = plan(doc, g, wet)
    if check_rules:
        probs = check(doc, p)
        if probs:
            raise FarmError("apricorn_farm: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    ns, fo = doc["namespace"], doc["folder"]
    parts = build_parts(doc, p)
    box = hold_box(p)
    build = ["# Generated by tools/apricorn_farm.py from data/apricorn_farm.json: the whole farm, held while it builds.",
             "forceload add %d %d %d %d" % box]
    build += ["function %s:%s/%s" % (ns, fo, k) for k in ["clear"] + [q for q in PARTS if q in parts]]
    build.append("forceload remove %d %d %d %d" % box)
    fns = {"build": build}
    fns.update(parts)
    fns.update(merchant_functions(doc, merchant))
    total = 0
    for name, lines in fns.items():
        bad = function_limits.check_lines(lines, name)
        if bad:
            raise FarmError("%s: %d command(s) the server would refuse: %s" % (name, len(bad), bad[:3]))
        total += sum(1 for l in lines if l.strip() and not l.startswith("#"))
    if total > function_limits.CHAIN_LIMIT:
        raise FarmError("the build runs %d commands, over maxCommandChainLength %d" % (total, function_limits.CHAIN_LIMIT))
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, fo, k): "\n".join(v) + "\n" for k, v in fns.items()}
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: Hollin's Apricorn Farm (tools/apricorn_farm.py)"}}, indent=2) + "\n"
    return out, {"plan": p, "npc": npc, "merchant": merchant, "box": box, "commands": total}


# ------------------------------------------------------------------------------------------------------------ the steps
def _planned(doc=None, g=None):
    import ground as G
    doc = doc or load()
    g = g or G.load()
    p, npc, merchant = plan(doc, g)
    return doc, g, p, npc, merchant


def placement_steps(doc=None, g=None):
    """R9AF, BEFORE R9E: hold the farm's box, build every part, release (R9SO's shape)."""
    doc, g, p, _n, _m = _planned(doc, g)
    hold = "%d %d %d %d" % hold_box(p)
    return [("cmd", "forceload add " + hold), ("wait", 3), ("fn", "%s:%s/build" % (doc["namespace"], doc["folder"])),
            ("cmd", "forceload remove " + hold)]


def npc_placements(doc=None, g=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for tools/reapply.py's "npc" action (R18AF)."""
    doc, g, p, npc, _m = _planned(doc, g)
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    conv = next((c for c in dl["conversations"] if c["id"] == doc["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        raise FarmError("%s is not a conversation with an NPC in data/dialogue.json" % doc["npc"]["conversation"])
    return [(conv["id"], tuple(npc), "%s:%s" % (doc["namespace"], conv["npc_id"]), doc["npc"]["yaw"])]


def entity_steps(doc=None, g=None):
    """R18AF, after R17N: the farmer (the "npc" action: spawned once, turned to her yaw), then the stall merchant,
    summoned with a "new" tag inside a forceload of its chunk; its done function, 100 ticks on, kills older copies."""
    doc, g, p, npc, merchant = _planned(doc, g)
    steps = [("npc", n) for n in npc_placements(doc, g)]
    x, _y, z = merchant
    steps += [("cmd", "forceload add %d %d" % (x, z)), ("wait", 3),
              ("fn", "%s:%s/merchant" % (doc["namespace"], doc["folder"])), ("wait", 7),
              ("cmd", "forceload remove %d %d" % (x, z))]
    return steps


# ------------------------------------------------------------------------------------------------------------ CLI
def write(out_files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in out_files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


def report(doc, res, g):
    p = res["plan"]
    lines = []
    for c, f in p.facts["groves"].items():
        lines.append("grove %-6s floor y%d (ground y%d-%d), gate %s (outside ground off by %d), %d trees, %d fruit, "
                     "cut %d / fill %d blocks" % (c, f["floor"], f["ground"][0], f["ground"][1], tuple(f["gate"]),
                                                  f["gate_outside_diff"], f["trees"], f["fruit"], f["cut"], f["fill"]))
    for b, f in p.facts["buildings"].items():
        lines.append("%-12s %s" % (b, json.dumps(f)))
    fr = p.facts["fruit"]
    lines.append("fruit: %d in all (%s)" % (sum(fr.values()), ", ".join("%s %d" % kv for kv in fr.items())))
    blocks = p.blocks()
    lines.append("blocks written: %d; hold box %s; commands %d; path cells skipped on held columns: %d"
                 % (len(blocks), res["box"], res["commands"], p.facts["path_skipped"]))
    na = p.facts.get("nearest_authored")
    if na:
        lines.append("nearest authored x/z (regions.json outline vertices excepted): %.0f, %s; nearest corridor box %.0f; "
                     "nearest route path %.0f" % (na[0], na[1], p.facts["nearest_corridor"], p.facts["nearest_route_path"]))
    lines.append("the farmer stands at %s; the stall keeper at %s" % (res["npc"], res["merchant"]))
    lines.append("R9AF: %s" % json.dumps([list(s) for s in placement_steps(doc, g)]))
    lines.append("R18AF: %d actions" % len(entity_steps(doc, g)))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", choices=("build", "plan"), default=None)
    ap.add_argument("--report", action="store_true", help="the same as plan: print, write nothing")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--source-root")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    out_files, res = files(doc, g)
    if a.report or a.cmd in (None, "plan"):
        print("\n".join(report(doc, res, g)))
        return 0
    write(out_files, a.out)
    print("apricorn_farm: %d files -> %s (%d commands, %d fruit)"
          % (len(out_files), a.out, res["commands"], sum(res["plan"].facts["fruit"].values())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
